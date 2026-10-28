"""Node-tree building helpers shared by every Mert Road Studio group (Blender 5.2)."""
import bpy

MRS = "MRS_"


class T:
    """Node-tree builder: new nodes in a left-to-right flow, optional frames, typed sockets by identifier."""
    def __init__(self, tree):
        self.t = tree; self.x = 0; self.y = 0; self.frame = None

    def frame_(self, label):
        f = self.t.nodes.new("NodeFrame"); f.label = label; self.frame = f; self.y -= 500; self.x = 0; return f

    def n(self, idname, label=None, **props):
        node = self.t.nodes.new(idname)
        node.location = (self.x, self.y); self.x += 200
        if self.x > 4200: self.x = 0; self.y -= 320
        if self.frame: node.parent = self.frame
        if label: node.label = label
        for k, v in props.items(): setattr(node, k, v)
        return node

    def link(self, a, b):
        self.t.links.new(a, b)

    def inp(self, node, key, value):
        """Set or link an input by identifier (or name)."""
        sock = node.inputs.get(key)
        if sock is None:
            sock = next((s for s in node.inputs if s.identifier == key), None)
        if sock is None: raise KeyError("%s has no input %s: %s" % (node.name, key, [s.identifier for s in node.inputs]))
        if isinstance(value, bpy.types.NodeSocket): self.link(value, sock)
        else: sock.default_value = value
        return sock

    def math(self, op, a, b=0.0, c=None):
        node = self.n("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b) if c is None else (a, b, c)): self.inp(node, node.inputs[i].identifier, v)
        return node.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        node = self.n("ShaderNodeVectorMath", operation=op)
        self.inp(node, node.inputs[0].identifier, a)
        if b is not None: self.inp(node, node.inputs[1].identifier, b)
        if scale is not None: self.inp(node, "Scale", scale)
        return node.outputs[0]

    def combine(self, x=0.0, y=0.0, z=0.0):
        node = self.n("ShaderNodeCombineXYZ")
        self.inp(node, "X", x); self.inp(node, "Y", y); self.inp(node, "Z", z)
        return node.outputs[0]

    def separate(self, v):
        node = self.n("ShaderNodeSeparateXYZ"); self.inp(node, "Vector", v)
        return node.outputs[0], node.outputs[1], node.outputs[2]

    def compare(self, op, a, b, data_type="FLOAT"):
        node = self.n("FunctionNodeCompare", operation=op, data_type=data_type)
        self.inp(node, node.inputs[0].identifier, a); self.inp(node, node.inputs[1].identifier, b)
        return node.outputs[0]

    def boolean(self, op, a, b=None):
        node = self.n("FunctionNodeBooleanMath", operation=op)
        self.inp(node, node.inputs[0].identifier, a)
        if b is not None: self.inp(node, node.inputs[1].identifier, b)
        return node.outputs[0]

    def switch(self, cond, false_v, true_v, kind="FLOAT"):
        node = self.n("GeometryNodeSwitch", input_type=kind)
        self.inp(node, "Switch", cond); self.inp(node, "False", false_v); self.inp(node, "True", true_v)
        return node.outputs[0]

    def menu_switch(self, menu, items, kind="GEOMETRY", label=None):
        """A Menu Switch: `items` = [(name, value_or_socket)]. The group's menu socket linked to `menu`
        takes its entries from this node (the first menu switch linked defines them)."""
        node = self.n("GeometryNodeMenuSwitch", label, data_type=kind)
        while len(node.enum_definition.enum_items) < len(items): node.enum_definition.enum_items.new("item")
        for it, (nm, _) in zip(node.enum_definition.enum_items, items): it.name = nm
        self.inp(node, "Menu", menu)
        for (nm, v) in items:
            if v is not None: self.inp(node, nm, v)
        return node.outputs[0]

    def named(self, name, kind="FLOAT"):
        node = self.n("GeometryNodeInputNamedAttribute", data_type=kind); self.inp(node, "Name", name)
        return node.outputs[0]

    def store(self, geo, name, value, kind="FLOAT", domain="POINT"):
        node = self.n("GeometryNodeStoreNamedAttribute", data_type=kind, domain=domain)
        self.inp(node, "Geometry", geo); self.inp(node, "Name", name); self.inp(node, "Value", value)
        return node.outputs[0]

    def join(self, *geos):
        node = self.n("GeometryNodeJoinGeometry")
        for g in geos: self.link(g, node.inputs[0])
        return node.outputs[0]

    def empty(self):
        return self.n("GeometryNodeJoinGeometry").outputs[0]

    def group(self, name, **inputs):
        node = self.n("GeometryNodeGroup" if self.t.bl_idname == "GeometryNodeTree" else "ShaderNodeGroup")
        node.node_tree = bpy.data.node_groups[name]
        for k, v in inputs.items(): self.inp(node, k, v)
        return node

    def map_range(self, v, a0, a1, b0, b1, clamp=True, interp="LINEAR"):
        node = self.n("ShaderNodeMapRange", interpolation_type=interp); node.clamp = clamp
        self.inp(node, "Value", v); self.inp(node, "From Min", a0); self.inp(node, "From Max", a1); self.inp(node, "To Min", b0); self.inp(node, "To Max", b1)
        return node.outputs[0]


def new_tree(name, kind="GeometryNodeTree"):
    """A fresh tree with this name; an existing one is rebuilt in place so modifiers and materials that
    reference it keep working (socket identifiers are re-issued in order, so values survive too)."""
    g = bpy.data.node_groups.get(name)
    if g is not None and g.bl_idname == kind:
        g.nodes.clear(); g.interface.clear()
    else:
        if g is not None: bpy.data.node_groups.remove(g)
        g = bpy.data.node_groups.new(name, kind)
    if kind == "GeometryNodeTree": g.is_modifier = True
    return g


def sock(tree, name, in_out, stype, default=None, minv=None, maxv=None, desc="", parent=None, subtype=None):
    s = tree.interface.new_socket(name, in_out=in_out, socket_type=stype, description=desc, parent=parent)
    if default is not None:
        try: s.default_value = default
        except Exception: pass
    if minv is not None and hasattr(s, "min_value"): s.min_value = minv
    if maxv is not None and hasattr(s, "max_value"): s.max_value = maxv
    if subtype and hasattr(s, "subtype"):
        try: s.subtype = subtype
        except Exception: pass
    return s


def panel(tree, name, closed=False, desc=""):
    return tree.interface.new_panel(name, description=desc, default_closed=closed)


def add_inputs(tree, spec):
    """spec: [("Panel name", [(name, socket type, default, min, max, desc), ...]), ...]"""
    out = {}
    for pname, rows in spec:
        p = panel(tree, pname, closed=(pname not in ("Profile", "Terrain"))) if pname else None
        for row in rows:
            name, st, d, lo, hi, desc = row[:6]
            out[name] = sock(tree, name, "INPUT", st, d, lo, hi, desc, parent=p, subtype=(row[6] if len(row) > 6 else None))
    return out


def mod_input_set(mod, name, value):
    """Modifier input by socket name (Blender 5.x: mod.properties.inputs.<identifier>.value)."""
    item = next(i for i in mod.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT" and i.name == name)
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        entry = getattr(props.inputs, item.identifier, None)
        if entry is None:
            try: entry = props.inputs[item.identifier]
            except Exception: entry = None
        if entry is not None:
            entry.value = value; return
    mod[item.identifier] = value


def mod_input_get(mod, name):
    item = next(i for i in mod.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT" and i.name == name)
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        entry = getattr(props.inputs, item.identifier, None)
        if entry is not None: return entry.value
    v = mod.get(item.identifier)
    return v if v is not None else getattr(item, "default_value", None)


# ------------------------------------------------------------------ scene / depsgraph (works headless too)
_SCENE = {"name": None}


def set_scene(sc):
    """Make `sc` the working scene: the window scene in the UI, a remembered scene headless
    (background Blender has no window, so bpy.context.scene cannot be assigned)."""
    _SCENE["name"] = sc.name
    win = getattr(bpy.context, "window", None)
    if win is not None:
        try: win.scene = sc
        except Exception: pass


def scene():
    sc = bpy.data.scenes.get(_SCENE["name"]) if _SCENE["name"] else None
    return sc or bpy.context.scene


def depsgraph():
    """Evaluated depsgraph of the working scene (updated first when it is not the context scene)."""
    sc = scene()
    if sc == bpy.context.scene: return bpy.context.evaluated_depsgraph_get()
    vl = sc.view_layers[0]; vl.update()
    return vl.depsgraph
