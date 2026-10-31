"""procmat.graphdump: a Markdown description of a shader node group or material, for the NODES.md documents.

    text = dump(bpy.data.materials["PM_Asphalt"])     # the material tree, then every group it uses (recursively)
    text = dump(bpy.data.node_groups["PM_Asphalt"])   # one group
    write(target, path)                               # the same, to a file

Sections per tree: interface (sockets, defaults, min / max, descriptions), node inventory (type, label, frame,
settings and input values that differ from a freshly created node of the same type, colour-ramp stops, the
builder's evidence note "pm_note"), connections (from node.socket -> to node.socket).
"""
import bpy

_SKIP = {"rna_type", "name", "label", "location", "location_absolute", "width", "height", "dimensions", "parent", "select",
         "show_options", "show_preview", "hide", "mute", "show_texture", "use_custom_color", "color", "bl_idname", "bl_label",
         "bl_description", "bl_icon", "bl_static_type", "bl_width_default", "bl_width_min", "bl_width_max", "bl_height_default",
         "bl_height_min", "bl_height_max", "type", "inputs", "outputs", "internal_links", "warning_propagation",
         "is_active_output", "image_user", "texture_mapping", "color_mapping", "interface", "node_tree", "color_ramp",
         "image", "object", "text", "shrink", "label_size", "is_active", "select_extend"}


def _fmt(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, float): return "" if abs(v) > 1e30 else "%.4g" % v
    if isinstance(v, int): return str(v)
    if isinstance(v, str): return v
    if isinstance(v, bpy.types.ID): return v.name
    try:
        seq = list(v)
        return "(" + ", ".join(_fmt(x) for x in seq) + ")"
    except TypeError:
        return str(v)


def _same(a, b):
    if isinstance(a, (str, bool, int)) and not isinstance(a, float) and isinstance(b, (str, bool, int)):
        return a == b
    if isinstance(a, str) or isinstance(b, str) or a is None or b is None:
        return a == b
    if isinstance(a, float) or isinstance(b, float):
        try: return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError): return False
    try:
        la, lb = list(a), list(b)
        return len(la) == len(lb) and all(_same(x, y) for x, y in zip(la, lb))
    except TypeError:
        return a == b


def _esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


class _Ref:
    """Freshly created nodes of each type, to tell non-default settings apart."""
    def __init__(self):
        self.tree = None; self.nodes = {}

    def get(self, idname):
        if idname not in self.nodes:
            if self.tree is None: self.tree = bpy.data.node_groups.new("PM_GraphDumpRef", "ShaderNodeTree")
            try: self.nodes[idname] = self.tree.nodes.new(idname)
            except RuntimeError: self.nodes[idname] = None
        return self.nodes[idname]

    def close(self):
        if self.tree is not None: bpy.data.node_groups.remove(self.tree)


def _sock_label(node, sock, outputs):
    coll = node.outputs if outputs else node.inputs
    same = [s for s in coll if s.name == sock.name and getattr(s, "enabled", True)]
    return sock.name if len(same) <= 1 else sock.identifier


def _settings(node, ref):
    out = []
    for p in node.bl_rna.properties:
        k = p.identifier
        if k in _SKIP or p.is_readonly or p.type in ("POINTER", "COLLECTION"): continue
        try: v = getattr(node, k)
        except AttributeError: continue
        rv = getattr(ref, k, None) if ref is not None else None
        if ref is None or not _same(v, rv): out.append("%s=%s" % (k, _fmt(v)))
    if node.bl_idname == "ShaderNodeValToRGB":
        cr = node.color_ramp
        stops = ", ".join("%.3g:%s" % (e.position, _fmt(tuple(round(c, 3) for c in e.color))) for e in cr.elements)
        out.append("ramp[%s]=%s" % (cr.interpolation, stops))
    for ptr in ("node_tree", "image", "object"):
        v = getattr(node, ptr, None)
        if isinstance(v, bpy.types.ID): out.append("%s=%s" % (ptr, v.name))
    return out


def _inputs(node, ref):
    out = []
    iface = {}
    if node.bl_idname == "ShaderNodeGroup" and node.node_tree is not None:
        iface = {i.identifier: i for i in node.node_tree.interface.items_tree if getattr(i, "item_type", "SOCKET") == "SOCKET" and i.in_out == "INPUT"}
    for s in node.inputs:
        if s.is_linked or not getattr(s, "enabled", True) or s.hide or not hasattr(s, "default_value"): continue
        v = s.default_value
        if node.bl_idname == "ShaderNodeGroup":
            it = iface.get(s.identifier); d = getattr(it, "default_value", None) if it is not None else None
        else:
            rs = None
            if ref is not None:
                rs = next((x for x in ref.inputs if x.identifier == s.identifier), None)
            d = getattr(rs, "default_value", None) if rs is not None else None
        if d is None or not _same(v, d): out.append("%s=%s" % (_sock_label(node, s, False), _fmt(v)))
    return out


def _frame_of(node):
    f = node.parent; names = []
    while f is not None: names.append(f.label or f.name); f = f.parent
    return " / ".join(reversed(names))


def _tree_md(tree, title, ref, level=2):
    h = "#" * level
    L = ["%s %s" % (h, title), ""]
    items = [i for i in tree.interface.items_tree] if hasattr(tree, "interface") else []
    socks = [i for i in items if getattr(i, "item_type", "SOCKET") == "SOCKET"]
    if socks:
        L += ["%s# Interface" % h, "", "| socket | in/out | type | default | min | max | panel | description |", "|---|---|---|---|---|---|---|---|"]
        for i in sorted(socks, key=lambda i: (i.in_out != "INPUT", i.index if hasattr(i, "index") else 0)):
            d = getattr(i, "default_value", None)
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                _esc(i.name), i.in_out.lower(), i.socket_type.replace("NodeSocket", ""), _fmt(d) if d is not None else "",
                _fmt(getattr(i, "min_value", "")) if hasattr(i, "min_value") else "", _fmt(getattr(i, "max_value", "")) if hasattr(i, "max_value") else "",
                _esc(i.parent.name) if getattr(i, "parent", None) is not None and i.parent.name else "", _esc(i.description)))
        L.append("")
    nodes = [n for n in tree.nodes if n.bl_idname != "NodeFrame"]
    frames = [n for n in tree.nodes if n.bl_idname == "NodeFrame"]
    order = {n.name: k for k, n in enumerate(tree.nodes)}
    nodes.sort(key=lambda n: (_frame_of(n), order[n.name]))
    counts = {}
    for n in nodes: counts[n.bl_idname] = counts.get(n.bl_idname, 0) + 1
    L += ["%s# Nodes (%d; frames %d)" % (h, len(nodes), len(frames)), "",
          "Types: " + ", ".join("%s x%d" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))), "",
          "| node | type | label | frame | settings (non-default) | input values (non-default, unlinked) | note |", "|---|---|---|---|---|---|---|"]
    for n in nodes:
        rn = ref.get(n.bl_idname)
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (_esc(n.name), n.bl_idname, _esc(n.label), _esc(_frame_of(n)),
                                                       _esc("; ".join(_settings(n, rn))), _esc("; ".join(_inputs(n, rn))),
                                                       _esc(n.get("pm_note", "")) if hasattr(n, "get") else ""))
    L += ["", "%s# Connections (%d)" % (h, len(tree.links)), "", "| from | to |", "|---|---|"]
    for l in sorted(tree.links, key=lambda l: (order.get(l.to_node.name, 0), l.to_socket.identifier)):
        L.append("| %s.%s | %s.%s |" % (_esc(l.from_node.name), _esc(_sock_label(l.from_node, l.from_socket, True)),
                                       _esc(l.to_node.name), _esc(_sock_label(l.to_node, l.to_socket, False))))
    L.append("")
    return L


def dump(target, recurse=True):
    """Markdown for a material (its tree, then each group it uses, nested groups once each) or a node group."""
    ref = _Ref()
    try:
        L = []; seen = set(); todo = []
        if isinstance(target, bpy.types.Material):
            L += ["# Material %s" % target.name, ""]
            for k in ("displacement_method", "surface_render_method", "use_backface_culling", "diffuse_color", "roughness", "metallic"):
                if hasattr(target, k): L.append("- %s: %s" % (k, _fmt(getattr(target, k))))
            if target.get("procmat"): L.append("- procmat group: %s" % target["procmat"])
            L.append("")
            if target.node_tree is not None:
                L += _tree_md(target.node_tree, "Material tree", ref, 2)
                todo += [n.node_tree for n in target.node_tree.nodes if n.bl_idname == "ShaderNodeGroup" and n.node_tree]
        else:
            todo.append(target)
        while todo:
            t = todo.pop(0)
            if t.name in seen: continue
            seen.add(t.name)
            L += _tree_md(t, "Group %s" % t.name, ref, 2)
            if recurse: todo += [n.node_tree for n in t.nodes if n.bl_idname == "ShaderNodeGroup" and n.node_tree]
        return "\n".join(L)
    finally:
        ref.close()


def write(target, path, recurse=True):
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(dump(target, recurse))
    return path
