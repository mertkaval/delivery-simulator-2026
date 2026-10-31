"""procmat.core: node-tree builder, contract groups / materials and the coordinates every material samples.

The contract (shared with Mert Road Studio, tools/roads/mrs/materials.py; decisions D2-D4):

    material PM_<Name>  ->  ONE ShaderNodeGroup named "MRS" (label = the group's name)
                            "BSDF"  -> Material Output > Surface
                            "Displacement" (vector) or "Height" (float) -> Material Output > Displacement, only when
                            the material asks for displacement (contract_material(displacement=...))
    group inputs  "Use UV"    0 = object space in metres (Object texture coordinates)
                              1 = UVMap x Tile Size, every 4D Noise / Voronoi sampled on a seamless 4D torus
                  "Tile Size" metres covered by UV 0..1 in UV mode (the repeat of a baked tile)
                  + the material's own inputs (one size / scale control in metres, colours, amounts ...)
    group outputs "BSDF", "Albedo" (+ "Metallic", "Height", "Displacement", "Alpha" when the material has them)

Only bpy is imported; nothing from the road tool (decision D1).
"""
import contextlib
import math

import bpy

PREFIX = "PM_"                 # node groups and materials are PM_<Name> (D3)
GROUP_NODE = "MRS"             # name of the one group node in a contract material (road tool convention)
TWO_PI = 2.0 * math.pi
TORUS_AXIS = (0.53, 0.71, 0.46)  # the torus is tilted off the noise lattice axes (same values as the road tool's _G):
TORUS_ANGLE = 0.83               # an axis-aligned circle picks up the cell grid as column banding

TYPES = {"FLOAT": "NodeSocketFloat", "INT": "NodeSocketInt", "BOOL": "NodeSocketBool", "COLOR": "NodeSocketColor",
         "VECTOR": "NodeSocketVector", "SHADER": "NodeSocketShader"}
OUTPUT_TYPES = {"BSDF": "SHADER", "Albedo": "COLOR", "Metallic": "FLOAT", "Roughness": "FLOAT", "Height": "FLOAT",
                "Alpha": "FLOAT", "Displacement": "VECTOR", "Normal": "VECTOR"}
CONTRACT_INPUTS = (
    ("Use UV", "FLOAT", 0.0, 0.0, 1.0,
     "0 = object space in metres; 1 = UVMap x Tile Size, every 4D texture sampled on a seamless torus (baked tiles repeat)"),
    ("Tile Size", "FLOAT", 4.0, 0.05, 1000.0, "Metres covered by UV 0..1 in UV mode: the repeat length of a baked tile"),
)
CONTRACT_PANEL = "Mapping"


def pm_name(name):
    """'Asphalt' -> 'PM_Asphalt' (names that already carry the prefix are kept)."""
    return name if name.startswith(PREFIX) else PREFIX + name


def _key(sockets, key):
    """Socket names may be passed with underscores for spaces (Base_Color -> 'Base Color')."""
    if isinstance(key, str) and key not in sockets and "_" in key:
        alt = key.replace("_", " ")
        if alt in sockets: return alt
    return key


def _rgba(v):
    if isinstance(v, (int, float)): return (float(v), float(v), float(v), 1.0)
    v = tuple(float(x) for x in v)
    return v + (1.0,) if len(v) == 3 else v


def _coerce(sock, v):
    t = sock.type
    if t == "RGBA": return _rgba(v)
    if t == "VECTOR":
        n = len(sock.default_value)
        if isinstance(v, (int, float)): return (float(v),) * n
        v = tuple(float(x) for x in v)
        return v[:n] if len(v) >= n else v + (0.0,) * (n - len(v))
    return v


def _enabled(s):
    return getattr(s, "enabled", True)


def find_socket(sockets, key, node=None):
    """A socket by index, identifier or name (an enabled one first: Mix / Map Range carry hidden namesakes)."""
    if isinstance(key, int): return sockets[key]
    for s in sockets:
        if s.identifier == key: return s
    named = [s for s in sockets if s.name == key]
    for s in named:
        if _enabled(s): return s
    if named: return named[0]
    raise KeyError("%s has no socket %r: %s" % (getattr(node, "name", "?"), key, [s.identifier for s in sockets]))


# ======================================================================================== node-tree builder
_EXTRA_H = {"ShaderNodeValToRGB": 140, "ShaderNodeTexNoise": 80, "ShaderNodeTexVoronoi": 100, "ShaderNodeTexGabor": 60,
            "ShaderNodeMix": 60, "ShaderNodeMath": 40, "ShaderNodeVectorMath": 40, "ShaderNodeMapRange": 70,
            "ShaderNodeVectorRotate": 50, "ShaderNodeAttribute": 70, "ShaderNodeTexWhiteNoise": 40, "ShaderNodeTexWave": 90,
            "ShaderNodeTexBrick": 90, "ShaderNodeBump": 40, "ShaderNodeDisplacement": 40}


def _height(n):
    if n.bl_idname == "ShaderNodeBsdfPrincipled": return 520
    vis = sum(1 for s in list(n.inputs) + list(n.outputs) if _enabled(s) and not s.hide and s.bl_idname != "NodeSocketVirtual")
    return 40 + 22 * vis + _EXTRA_H.get(n.bl_idname, 20)


class Builder:
    """Thin shader node-tree builder. Math helpers return output sockets so graphs read like formulas;
    texture / ramp / BSDF helpers return the node (pick .outputs["Fac"], ["Color"], ["Distance"] ...).
    Every argument that takes a value also takes a socket (it is linked instead)."""

    def __init__(self, tree):
        self.tree = tree
        self._frames = []

    # ---------------------------------------------------------------- nodes, sockets, frames
    def node(self, idname, label=None, name=None, note=None, **props):
        """A new node (properties set in the given order, e.g. data_type before linking). `note` is stored as the
        node's custom property "pm_note" (evidence tag, shown by graphdump)."""
        n = self.tree.nodes.new(idname)
        if name: n.name = name
        if label: n.label = label
        for k, v in props.items(): setattr(n, k, v)
        if note: n["pm_note"] = note
        if self._frames: n.parent = self._frames[-1]
        return n

    n = node

    def new_frame(self, label, color=None, parent=None):
        f = self.tree.nodes.new("NodeFrame"); f.label = label; f.shrink = True
        try: f.label_size = 18
        except (AttributeError, TypeError): pass
        if color is not None: f.use_custom_color = True; f.color = color[:3]
        if parent is not None: f.parent = parent
        return f

    @contextlib.contextmanager
    def frame(self, label, color=None):
        """with b.frame("Cracks"): ...  nodes created inside are parented to a new frame (frames nest)."""
        f = self.new_frame(label, color, self._frames[-1] if self._frames else None)
        self._frames.append(f)
        try: yield f
        finally: self._frames.pop()

    @contextlib.contextmanager
    def into(self, frame):
        """Re-enter an existing frame (or None = top level)."""
        saved = self._frames; self._frames = [frame] if frame is not None else []
        try: yield frame
        finally: self._frames = saved

    def input(self, node, key):
        return find_socket(node.inputs, _key(node.inputs, key), node)

    def output(self, node, key=0):
        return find_socket(node.outputs, _key(node.outputs, key), node)

    def set(self, node, key, value):
        """Set an input's default value, or link it when `value` is a socket (a node means its first output).
        Colours accept 3 or 4 components or a grey float; vectors accept a float or a tuple."""
        s = self.input(node, key)
        if value is None: return s
        if isinstance(value, (bpy.types.Node, Dual)): value = value.outputs[0]
        if isinstance(value, bpy.types.NodeSocket): self.tree.links.new(value, s)
        else: s.default_value = _coerce(s, value)
        return s

    inp = set

    def link(self, a, b):
        if isinstance(a, (bpy.types.Node, Dual)): a = a.outputs[0]
        return self.tree.links.new(a, b)

    def value(self, v, label=None):
        n = self.node("ShaderNodeValue", label); n.outputs[0].default_value = v; return n.outputs[0]

    def rgb(self, color, label=None):
        n = self.node("ShaderNodeRGB", label); n.outputs[0].default_value = _rgba(color); return n.outputs[0]

    # ---------------------------------------------------------------- math
    def math(self, op, a, b=0.0, c=None, clamp=False, label=None):
        n = self.node("ShaderNodeMath", label, operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b) if c is None else (a, b, c)): self.set(n, i, v)
        return n.outputs[0]

    m = math

    def add(self, a, b): return self.math("ADD", a, b)
    def sub(self, a, b): return self.math("SUBTRACT", a, b)
    def mul(self, a, b): return self.math("MULTIPLY", a, b)
    def div(self, a, b): return self.math("DIVIDE", a, b)
    def minimum(self, a, b): return self.math("MINIMUM", a, b)
    def maximum(self, a, b): return self.math("MAXIMUM", a, b)
    def power(self, a, b): return self.math("POWER", a, b)
    def fract(self, a): return self.math("FRACT", a)
    def invert(self, a): return self.math("SUBTRACT", 1.0, a)

    def madd(self, a, b, c):
        """a * b + c"""
        return self.math("MULTIPLY_ADD", a, b, c)

    def lerp(self, t, a, b):
        """a + t (b - a) for floats (a Mix node in FLOAT mode)."""
        return self.mixf(t, a, b)

    def clamp(self, v, lo=0.0, hi=1.0, label=None):
        n = self.node("ShaderNodeClamp", label, clamp_type="MINMAX")
        self.set(n, "Value", v); self.set(n, "Min", lo); self.set(n, "Max", hi)
        return n.outputs[0]

    def vmath(self, op, a, b=None, c=None, scale=None, label=None):
        n = self.node("ShaderNodeVectorMath", label, operation=op)
        self.set(n, 0, a)
        if b is not None: self.set(n, 1, b)
        if c is not None: self.set(n, 2, c)
        if scale is not None: self.set(n, "Scale", scale)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def combine(self, x=0.0, y=0.0, z=0.0, label=None):
        n = self.node("ShaderNodeCombineXYZ", label)
        self.set(n, "X", x); self.set(n, "Y", y); self.set(n, "Z", z)
        return n.outputs[0]

    def separate(self, v, label=None):
        n = self.node("ShaderNodeSeparateXYZ", label); self.set(n, "Vector", v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def separate_color(self, c, label=None):
        n = self.node("ShaderNodeSeparateColor", label); self.set(n, "Color", c)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def gray(self, v):
        """A float as a grey colour (Combine Color)."""
        n = self.node("ShaderNodeCombineColor"); self.set(n, 0, v); self.set(n, 1, v); self.set(n, 2, v)
        return n.outputs[0]

    # ---------------------------------------------------------------- mix / ramps / ranges
    _MIX = {"FLOAT": ("A_Float", "B_Float", "Result_Float"), "VECTOR": ("A_Vector", "B_Vector", "Result_Vector"),
            "RGBA": ("A_Color", "B_Color", "Result_Color")}

    def mix(self, fac, a, b, data_type="RGBA", blend="MIX", clamp_result=False, clamp_factor=True, label=None):
        """Mix node (Blender 4+/5): data_type FLOAT / VECTOR / RGBA; blend (RGBA only): MIX, DARKEN, LIGHTEN,
        MULTIPLY, OVERLAY, LINEAR_LIGHT, ... Returns the Result socket of that type."""
        n = self.node("ShaderNodeMix", label, data_type=data_type)
        if data_type == "RGBA": n.blend_type = blend; n.clamp_result = clamp_result
        n.clamp_factor = clamp_factor
        ia, ib, o = self._MIX[data_type]
        self.set(n, "Factor_Float", fac); self.set(n, ia, a); self.set(n, ib, b)
        return find_socket(n.outputs, o, n)

    def mixf(self, fac, a, b, label=None): return self.mix(fac, a, b, "FLOAT", label=label)
    def mixv(self, fac, a, b, label=None): return self.mix(fac, a, b, "VECTOR", label=label)
    def mixc(self, fac, a, b, blend="MIX", clamp=False, label=None): return self.mix(fac, a, b, "RGBA", blend, clamp, label=label)

    def ramp(self, fac, stops=((0.0, 0.0), (1.0, 1.0)), interpolation="LINEAR", label=None, note=None):
        """Color Ramp: stops = [(position, colour or grey float), ...]; interpolation LINEAR / CONSTANT / EASE /
        B_SPLINE / CARDINAL. Returns the node (outputs "Color", "Alpha")."""
        n = self.node("ShaderNodeValToRGB", label, note=note)
        cr = n.color_ramp; cr.interpolation = interpolation
        stops = sorted(((float(p), c) for p, c in stops), key=lambda s: s[0])
        els = cr.elements
        while len(els) > 1: els.remove(els[-1])
        els[0].position = stops[0][0]; els[0].color = _rgba(stops[0][1])
        for pos, col in stops[1:]:
            e = els.new(pos); e.color = _rgba(col)
        self.set(n, "Fac", fac)
        return n

    def map_range(self, v, a0, a1, b0=0.0, b1=1.0, clamp=True, interp="LINEAR", label=None):
        n = self.node("ShaderNodeMapRange", label, data_type="FLOAT", interpolation_type=interp); n.clamp = clamp
        self.set(n, "Value", v); self.set(n, "From Min", a0); self.set(n, "From Max", a1); self.set(n, "To Min", b0); self.set(n, "To Max", b1)
        return n.outputs["Result"]

    def smoothstep(self, v, a, b, label=None):
        """0 at a, 1 at b (a may be greater than b), smooth in between (Map Range, SMOOTHSTEP, clamped)."""
        return self.map_range(v, a, b, 0.0, 1.0, True, "SMOOTHSTEP", label)

    # ---------------------------------------------------------------- shading
    def bump(self, height, strength=1.0, distance=1.0, normal=None, invert=False, label=None, note=None):
        """Bump node; chain bumps by passing the previous Normal as `normal`. Returns the Normal socket."""
        n = self.node("ShaderNodeBump", label, note=note, invert=invert)
        self.set(n, "Strength", strength); self.set(n, "Distance", distance); self.set(n, "Height", height)
        if normal is not None: self.set(n, "Normal", normal)
        return n.outputs["Normal"]

    def principled(self, label=None, note=None, **inputs):
        """Principled BSDF with inputs by name (Base_Color= or **{"Base Color": ...}). Returns the node."""
        n = self.node("ShaderNodeBsdfPrincipled", label, note=note)
        for k, v in inputs.items(): self.set(n, k, v)
        return n

    def group(self, tree, label=None, **inputs):
        """A nested group node (tree or its name)."""
        n = self.node("ShaderNodeGroup", label)
        n.node_tree = tree if isinstance(tree, bpy.types.NodeTree) else bpy.data.node_groups[tree]
        for k, v in inputs.items(): self.set(n, k, v)
        return n

    # ---------------------------------------------------------------- layout
    def layout(self, dx=280.0, gap=28.0, band_gap=140.0):
        """Arrange the tree: columns by longest distance to an output (outputs right, inputs left), one horizontal
        band per top-level frame (frames never overlap), nodes in a column ordered by their consumers' height.
        Unused sockets of Group Input nodes are hidden."""
        nt = self.tree
        nodes = [x for x in nt.nodes if x.bl_idname != "NodeFrame"]
        if not nodes: return
        for gi in (x for x in nodes if x.bl_idname == "NodeGroupInput"):
            for s in gi.outputs: s.hide = not s.is_linked
        cons = {x.name: set() for x in nodes}; prods = {x.name: set() for x in nodes}
        for l in nt.links:
            a, b = l.from_node.name, l.to_node.name
            if a in cons and b in cons and a != b: cons[a].add(b); prods[b].add(a)
        depth = {}; left = {k: len(v) for k, v in cons.items()}
        queue = [k for k, c in left.items() if c == 0]
        for k in queue: depth[k] = 0
        i = 0
        while i < len(queue):
            k = queue[i]; i += 1
            for p in prods[k]:
                depth[p] = max(depth.get(p, 0), depth[k] + 1); left[p] -= 1
                if left[p] == 0: queue.append(p)
        for x in nodes: depth.setdefault(x.name, 0)

        def top(x):
            f = x.parent
            while f is not None and f.parent is not None: f = f.parent
            return f
        tops = [x for x in nt.nodes if x.bl_idname == "NodeFrame" and x.parent is None]
        rank = {f.name: r + 1 for r, f in enumerate(tops)}
        order = {x.name: r for r, x in enumerate(nt.nodes)}
        bands = {}
        for x in nodes:
            f = top(x)
            bands.setdefault(rank.get(f.name, 0) if f is not None else 0, {}).setdefault(depth[x.name], []).append(x)
        ypos = {}; y0 = 0.0
        for r in sorted(bands):
            band = bands[r]; lowest = y0
            for d in sorted(band):
                col = band[d]
                def key(x):
                    ys = [ypos[c] for c in cons[x.name] if c in ypos]
                    return (-(sum(ys) / len(ys)) if ys else 0.0, order[x.name])
                col.sort(key=key)
                y = y0
                for x in col:
                    loc = (-d * dx, y)
                    if hasattr(x, "location_absolute"): x.location_absolute = loc
                    else: x.location = loc
                    ypos[x.name] = y
                    y -= _height(x) + gap
                lowest = min(lowest, y)
            y0 = lowest - band_gap


# ======================================================================================== groups
def _socket_type(t):
    return TYPES.get(t.upper(), t) if isinstance(t, str) else t


def add_socket(tree, name, in_out, stype, default=None, minv=None, maxv=None, desc="", parent=None, subtype=None):
    s = tree.interface.new_socket(name, in_out=in_out, socket_type=_socket_type(stype), description=desc or "", parent=parent)
    if default is not None and hasattr(s, "default_value"):
        try: s.default_value = _rgba(default) if s.socket_type == "NodeSocketColor" else default
        except (TypeError, ValueError, AttributeError): pass
    if minv is not None and hasattr(s, "min_value"): s.min_value = minv
    if maxv is not None and hasattr(s, "max_value"): s.max_value = maxv
    if subtype:
        try: s.subtype = subtype
        except (TypeError, ValueError, AttributeError): pass
    return s


def _rows(spec):
    """Flatten an input spec into [(panel or None, row)]: rows are (name, type, default, min, max, desc[, subtype]),
    a panel is ("Panel name", [rows])."""
    out = []
    for item in spec:
        if len(item) == 2 and isinstance(item[1], (list, tuple)) and item[1] and isinstance(item[1][0], (list, tuple)):
            out += [(item[0], r) for r in item[1]]
        else:
            out.append((None, item))
    return out


def new_group(name, inputs=(), outputs=("BSDF", "Albedo"), contract=True, scale="Scale", uv_map="UVMap", closed_panels=True):
    """A shader group PM_<Name> with an interface, rebuilt in place when it exists (materials keep pointing at it).

    inputs : rows (name, type, default, min, max, description[, subtype]) or panels ("Panel", [rows]);
             type = FLOAT / INT / BOOL / COLOR / VECTOR / SHADER or a NodeSocket idname.
    outputs: names ("BSDF", "Albedo", "Metallic", "Height", "Displacement", "Alpha" have known types) or (name, type).
    contract=True appends "Use UV" and "Tile Size" (panel "Mapping") unless listed, and requires BSDF + Albedo.
    scale  : name of the input that scales every texture coordinate (Coordinates.V / W); missing = no scale.
    Returns a Group builder (G.tree, G.I(name), G.out(name, socket), G.coords, G.layout())."""
    name = pm_name(name)
    tree = bpy.data.node_groups.get(name)
    if tree is not None and tree.bl_idname == "ShaderNodeTree":
        tree.nodes.clear(); tree.interface.clear()
    else:
        if tree is not None: bpy.data.node_groups.remove(tree)
        tree = bpy.data.node_groups.new(name, "ShaderNodeTree")
    outs = [(o, OUTPUT_TYPES.get(o, "FLOAT")) if isinstance(o, str) else tuple(o) for o in outputs]
    if contract:
        have = {o[0] for o in outs}
        for req in ("BSDF", "Albedo"):
            if req not in have: raise ValueError("%s: a contract group needs a %r output" % (name, req))
    for o, t in outs: add_socket(tree, o, "OUTPUT", t)
    panels = {}
    rows = _rows(inputs)
    names = {r[0] for _, r in rows}
    if contract:
        rows += [(CONTRACT_PANEL, r) for r in CONTRACT_INPUTS if r[0] not in names]
    for pname, r in rows:
        parent = None
        if pname:
            parent = panels.get(pname)
            if parent is None:
                parent = tree.interface.new_panel(pname, default_closed=bool(closed_panels and pname == CONTRACT_PANEL))
                panels[pname] = parent
        nm, st, d = r[0], r[1], r[2] if len(r) > 2 else None
        add_socket(tree, nm, "INPUT", st, d, r[3] if len(r) > 3 else None, r[4] if len(r) > 4 else None,
                   r[5] if len(r) > 5 else "", parent, r[6] if len(r) > 6 else None)
    G = Group(tree)
    if contract or "Use UV" in input_names(tree):
        G.coords = Coordinates(G, "Use UV", "Tile Size", scale if scale in input_names(tree) else None, uv_map)
    return G


def input_names(tree):
    return [i.name for i in tree.interface.items_tree if getattr(i, "item_type", "SOCKET") == "SOCKET" and i.in_out == "INPUT"]


def output_names(tree):
    return [i.name for i in tree.interface.items_tree if getattr(i, "item_type", "SOCKET") == "SOCKET" and i.in_out == "OUTPUT"]


class Group(Builder):
    """Builder for one group tree: I(name) reads a group input (one Group Input node per frame, unused sockets hidden
    by layout()), out(name, value) feeds the Group Output, coords is the Coordinates helper (contract groups)."""

    def __init__(self, tree):
        super().__init__(tree)
        self.go = self.node("NodeGroupOutput")
        self._gis = {}
        self.coords = None

    @property
    def C(self):
        return self.coords

    def I(self, name):
        f = self._frames[-1] if self._frames else None
        key = f.name if f is not None else ""
        gi = self._gis.get(key)
        if gi is None:
            gi = self.node("NodeGroupInput"); self._gis[key] = gi
        return gi.outputs[name]

    def out(self, name, value):
        s = self.go.inputs[name]
        if isinstance(value, (bpy.types.Node, Dual)): value = value.outputs[0]
        if isinstance(value, bpy.types.NodeSocket): self.tree.links.new(value, s)
        else: s.default_value = _coerce(s, value)
        return s

    def finish(self):
        """layout() and a check that every declared output is fed. Returns the tree."""
        self.layout()
        missing = [s.name for s in self.go.inputs if s.bl_idname != "NodeSocketVirtual" and not s.is_linked]
        if missing: print("[procmat] %s: outputs not linked: %s" % (self.tree.name, missing))
        return self.tree


# ======================================================================================== coordinates
def _seed_vec(seed):
    return (seed * 1.731, seed * 3.117, seed * 2.297)


class Dual:
    """Two texture nodes behind one node-like object: n3 (3D, object mode) and n4 (4D torus, UV mode).
    dual.outputs["Distance"] (or [0]) is a Mix of the two by Use UV, created on first use."""

    def __init__(self, b, use, n3, n4):
        self.b, self.use, self.n3, self.n4 = b, use, n3, n4
        self._mixed = {}
        self.name = n4.name; self.bl_idname = n4.bl_idname

    @property
    def outputs(self):
        return self

    def __contains__(self, key):
        return key in self.n4.outputs

    def __getitem__(self, key):
        if isinstance(key, int): key = [s for s in self.n4.outputs if _enabled(s)][key].identifier
        if key not in self._mixed:
            s3 = find_socket(self.n3.outputs, key, self.n3); s4 = find_socket(self.n4.outputs, key, self.n4)
            t = {"VALUE": "FLOAT", "INT": "FLOAT", "RGBA": "RGBA", "VECTOR": "VECTOR"}.get(s4.type, "FLOAT")
            self._mixed[key] = self.b.mix(self.use, s3, s4, t, label="object 3D | UV 4D")
        return self._mixed[key]


class Coordinates:
    """Where every texture of a contract group samples.

    use   Use UV (0/1) socket, keep = 1 - use (1 in object mode; multiply position-dependent effects by it)
    tile  Tile Size (m) socket
    obj   Object texture coordinates (metres for an unscaled object)
    uv    the UVMap attribute (0..1 on a bake plane)
    P     metres in both modes: obj, or uv x Tile Size          (px, py, pz: its components)
    V, W  the 4D sample point, already multiplied by the group's scale input:
            object mode: V = obj x scale,                        W = 0
            UV mode:     V = rotate(R cos u, R sin u, R cos v),  W = R sin v,  R = Tile Size / 2 pi,
                         u = 2 pi UV.x, v = 2 pi UV.y: a flat (Clifford) torus, arc length = metres, so a 4D
                         Noise / Voronoi has the same feature size as in object mode and repeats every Tile Size.
    Nodes are built on first use, in a frame "Coordinates"."""

    def __init__(self, b, use_uv="Use UV", tile="Tile Size", scale=None, uv_map="UVMap", tilt=True):
        self.b = b; self._src = {"use": use_uv, "tile": tile, "scale": scale}; self.uv_map = uv_map; self.tilt = tilt
        self._c = None; self._frame = None

    # -- construction
    def _val(self, v):
        if isinstance(v, str): return self.b.I(v) if hasattr(self.b, "I") else None
        return v

    @contextlib.contextmanager
    def _ctx(self):
        if self._frame is None:
            with self.b.into(None):
                self._frame = self.b.new_frame("Coordinates: object metres, or UVMap x Tile Size on a seamless 4D torus")
        with self.b.into(self._frame): yield

    def _build(self):
        if self._c is not None: return self._c
        b = self.b; c = {}
        with self._ctx():
            c["use"] = self._val(self._src["use"]); c["tile"] = self._val(self._src["tile"]); c["scale"] = self._val(self._src["scale"])
            tc = b.node("ShaderNodeTexCoord"); c["obj"] = tc.outputs["Object"]
            uvn = b.node("ShaderNodeAttribute", "UV", attribute_name=self.uv_map); c["uv"] = uvn.outputs["Vector"]
            c["P"] = b.mixv(c["use"], c["obj"], b.vmath("SCALE", c["uv"], scale=c["tile"]), label="P (m)")
            ux, uy, _ = b.separate(c["uv"])
            c["R"] = b.div(c["tile"], TWO_PI)
            au = b.mul(ux, TWO_PI); av = b.mul(uy, TWO_PI)
            c["cu"], c["su"], c["cv"], c["sv"] = b.math("COSINE", au), b.math("SINE", au), b.math("COSINE", av), b.math("SINE", av)
        self._c = c
        with self._ctx():
            c["V"], c["W"] = self._vw(1.0, 1.0, 1.0)
        return c

    def _vw(self, sx, sy, sz):
        """(V, W) with per-axis stretch (object x/y/z; UV u/v)."""
        b = self.b; c = self._c
        aniso = not (isinstance(sx, (int, float)) and isinstance(sy, (int, float)) and sx == 1.0 and sy == 1.0)
        Ru = b.mul(c["R"], sx) if aniso else c["R"]; Rv = b.mul(c["R"], sy) if aniso else c["R"]
        Vt = b.combine(b.mul(c["cu"], Ru), b.mul(c["su"], Ru), b.mul(c["cv"], Rv), label="torus")
        if self.tilt:
            rot = b.node("ShaderNodeVectorRotate", "tilt off the lattice", rotation_type="AXIS_ANGLE")
            b.set(rot, "Vector", Vt); b.set(rot, "Axis", TORUS_AXIS); b.set(rot, "Angle", TORUS_ANGLE); Vt = rot.outputs[0]
        Wt = b.mul(c["sv"], Rv)
        obj = c["obj"]
        if aniso or not (isinstance(sz, (int, float)) and sz == 1.0):
            obj = b.vmath("MULTIPLY", obj, b.combine(sx, sy, sz))
        V = b.mixv(c["use"], obj, Vt); W = b.mixf(c["use"], 0.0, Wt)
        if c["scale"] is not None:
            V = b.vmath("SCALE", V, scale=c["scale"], label="V"); W = b.mul(W, c["scale"])
        return V, W

    def __getattr__(self, k):
        if k in ("use", "tile", "obj", "uv", "P", "V", "W", "scale"):
            return self._build()[k]
        if k in ("px", "py", "pz"):
            c = self._build()
            if "px" not in c:
                with self._ctx(): c["px"], c["py"], c["pz"] = self.b.separate(c["P"])
            return c[k]
        if k == "keep":
            c = self._build()
            if "keep" not in c:
                with self._ctx(): c["keep"] = self.b.sub(1.0, c["use"])
            return c["keep"]
        raise AttributeError(k)

    @property
    def VW(self):
        return (self.V, self.W)

    # -- sample points
    def stretch(self, sx, sy, sz=1.0):
        """Anisotropic (V, W): x (UV u) x sx, y (UV v) x sy, z x sz (object mode). Still seamless in UV mode."""
        self._build()
        with self._ctx(): return self._vw(sx, sy, sz)

    def warp(self, color, amount, at=None, blend="LINEAR_LIGHT"):
        """Tutorial-style vector distortion: Mix (Linear Light, Factor `amount`) of the coordinates (A) with a
        colour (B), e.g. noise4(...).outputs["Color"]: V' = V + amount (2 B - 1). W is unchanged. Returns (V', W).
        Seamless in UV mode when `color` is (built from 4D textures on these coordinates)."""
        V, W = at or (self.V, self.W)
        return self.b.mixc(amount, V, color, blend, label="warp"), W

    def offset(self, dv=(0.0, 0.0, 0.0), dw=0.0, at=None):
        """(V + dv, W + dw): decorrelate layers (any constant keeps UV mode seamless)."""
        V, W = at or (self.V, self.W)
        return self.b.vmath("ADD", V, dv), (self.b.add(W, dw) if dw else W)

    # -- 4D textures
    def noise4(self, scale=5.0, detail=2.0, roughness=0.5, lacunarity=2.0, distortion=0.0, noise_type="FBM", normalize=True,
               at=None, seed=0.0, exact3d=False, label=None, note=None, **extra):
        """4D Noise Texture at (V, W) (default the group coordinates; `at` takes a (V, W) pair from warp / stretch /
        offset). `seed` shifts W (another slice, still seamless). extra: Offset=, Gain= for the multifractal types.
        exact3d=True: object mode samples a 3D Noise at V (the tutorials' exact field), UV mode the 4D torus; outputs
        are mixed by Use UV (both evaluated). Returns the node (outputs "Fac", "Color") or a Dual with the same outputs."""
        b = self.b; V, W = at or (self.V, self.W)

        def make(dims):
            n = b.node("ShaderNodeTexNoise", label, note=note, noise_dimensions=dims, noise_type=noise_type)
            try: n.normalize = normalize
            except (AttributeError, TypeError): pass
            if dims == "4D":
                b.set(n, "Vector", V); b.set(n, "W", b.add(W, seed) if seed else W)
            else:
                b.set(n, "Vector", b.vmath("ADD", V, _seed_vec(seed)) if seed else V)
            b.set(n, "Scale", scale); b.set(n, "Detail", detail)
            b.set(n, "Roughness", roughness); b.set(n, "Lacunarity", lacunarity); b.set(n, "Distortion", distortion)
            for k, v in extra.items(): b.set(n, k, v)
            return n
        return Dual(b, self.use, make("3D"), make("4D")) if exact3d else make("4D")

    def voronoi4(self, scale=5.0, feature="F1", metric="EUCLIDEAN", randomness=1.0, exponent=None, smoothness=None,
                 detail=None, roughness=None, lacunarity=None, normalize=None, at=None, seed=0.0, exact3d=False, label=None, note=None):
        """4D Voronoi Texture at (V, W). feature F1 / F2 / SMOOTH_F1 / DISTANCE_TO_EDGE / N_SPHERE_RADIUS;
        metric EUCLIDEAN / MANHATTAN / CHEBYCHEV / MINKOWSKI (exponent). exact3d as for noise4 (a 2D slice of 4D
        cells varies more in cell size and edge width than 3D cells: exact3d keeps the tutorials' 3D cells in object
        mode). Returns the node (outputs "Distance", "Color", "Position", "W", "Radius") or a Dual."""
        b = self.b; V, W = at or (self.V, self.W)

        def make(dims):
            n = b.node("ShaderNodeTexVoronoi", label, note=note, voronoi_dimensions=dims, feature=feature, distance=metric)
            if normalize is not None: n.normalize = normalize
            if dims == "4D":
                b.set(n, "Vector", V); b.set(n, "W", b.add(W, seed) if seed else W)
            else:
                b.set(n, "Vector", b.vmath("ADD", V, _seed_vec(seed)) if seed else V)
            b.set(n, "Scale", scale); b.set(n, "Randomness", randomness)
            for k, v in (("Exponent", exponent), ("Smoothness", smoothness), ("Detail", detail), ("Roughness", roughness), ("Lacunarity", lacunarity)):
                if v is not None: b.set(n, k, v)
            return n
        return Dual(b, self.use, make("3D"), make("4D")) if exact3d else make("4D")

    # -- periodic patterns (textures without a 4D variant, D5)
    def periodic(self, size):
        """(size', n): a repeat length snapped to Tile Size / n in UV mode (so a pattern built with FRACT / FLOOR of
        P / size' tiles), and the count n to wrap cell indices with (`wrap`); object mode: size untouched, n = 1e6."""
        b = self.b
        with self._ctx():
            n = b.maximum(b.math("ROUND", b.div(self.tile, size)), 1.0)
            return b.mixf(self.use, size, b.div(self.tile, n)), b.mixf(self.use, 1.0e6, n)

    def wrap(self, idx, n):
        """Cell index modulo n (per-cell randoms repeat with the tile)."""
        return self.b.math("FLOORED_MODULO", idx, n)

    def snap_scale(self, scale, period=1.0):
        """A texture Scale for a periodic 3D texture fed with P (metres): in UV mode snapped so that whole periods fit
        the tile (period / scale = Tile Size / n); object mode keeps `scale`. `period` = the texture's repeat at
        Scale 1 in input units: Wave bands (X / Y / Z / diagonal) 2 pi / 20 = 0.31416 (distortion and detail must be 0
        in UV mode: drive Phase Offset from a noise4 instead), Checker 2.0. Returns a socket."""
        b = self.b
        with self._ctx():
            n = b.maximum(b.math("ROUND", b.div(b.mul(self.tile, scale), period)), 1.0)
            return b.mixf(self.use, scale, b.div(b.mul(n, period), self.tile))

    def seamless(self, make, blend=0.15):
        """Fallback for 3D-only textures (Gabor, Wave with distortion, Brick, Magic ...): make(P) builds the texture at a
        metre position P and returns a socket (or a tuple of sockets). Object mode: make(object coords). UV mode: four
        samples f(P), f(P - (T,0)), f(P - (0,T)), f(P - (T,T)) with P = fract(UV) x T, cross-faded (smoothstep) over the
        last `blend` of the tile in u and v, so the result repeats exactly every Tile Size. Cost: 4 evaluations;
        contrast drops slightly inside the blend band. Returns a socket (or tuple)."""
        b = self.b; c = self._build()
        with self._ctx():
            ux, uy, _ = b.separate(c["uv"])
            fu = b.fract(ux); fv = b.fract(uy)
            T = c["tile"]
            Pw = b.mixv(c["use"], c["obj"], b.combine(b.mul(fu, T), b.mul(fv, T), 0.0), label="P wrapped")
            wu = b.mul(c["use"], b.smoothstep(fu, 1.0 - blend, 1.0)); wv = b.mul(c["use"], b.smoothstep(fv, 1.0 - blend, 1.0))
            shifted = [Pw] + [b.vmath("SUBTRACT", Pw, b.combine(b.mul(T, sx), b.mul(T, sy), 0.0)) for sx, sy in ((1.0, 0.0), (0.0, 1.0), (1.0, 1.0))]
        samples = [make(p) for p in shifted]
        single = not isinstance(samples[0], (tuple, list))
        if single: samples = [(s,) for s in samples]
        out = []
        with self._ctx():
            for k in range(len(samples[0])):
                s00, s10, s01, s11 = (s[k] for s in samples)
                t = {"VALUE": "FLOAT", "INT": "FLOAT", "RGBA": "RGBA", "VECTOR": "VECTOR"}.get(s00.type, "FLOAT")
                top = b.mix(wu, s00, s10, t); bot = b.mix(wu, s01, s11, t)
                out.append(b.mix(wv, top, bot, t, label="seamless"))
        return out[0] if single else tuple(out)


# ======================================================================================== materials
def material(m):
    """A Material from a Material, its name or its name without the PM_ prefix."""
    if isinstance(m, bpy.types.Material): return m
    mat = bpy.data.materials.get(m) or bpy.data.materials.get(pm_name(m))
    if mat is None: raise KeyError("no material %r" % m)
    return mat


def group_node(mat):
    """The contract group node ("MRS") of a material, or None."""
    mat = material(mat)
    return mat.node_tree.nodes.get(GROUP_NODE) if mat.node_tree else None


def set_inputs(target, **values):
    """Set inputs of a material's "MRS" node (or of any node) by name; underscores stand for spaces.
    Returns the names that were not found."""
    node = target if isinstance(target, bpy.types.Node) else group_node(target)
    missing = []
    for k, v in values.items():
        k2 = _key(node.inputs, k)
        if k2 not in node.inputs: missing.append(k); continue
        s = node.inputs[k2]
        s.default_value = _coerce(s, v)
    return missing


def contract_material(name, group, displacement=None, viewport=None, roughness=None, metallic=None, settings=None,
                      fake_user=True, **defaults):
    """Material PM_<Name> holding ONE group node named "MRS" (label = group name), BSDF -> Material Output Surface.

    group        : the PM_ group (tree or name)
    defaults     : group input values for this material (underscores for spaces: Tile_Size=8.0)
    displacement : None/False = surface only (bump in the BSDF). True / "BOTH" / "DISPLACEMENT" / "BUMP": the group's
                   "Displacement" output (vector) - or its "Height" output through a Displacement node (midlevel 0,
                   scale 1) - feeds Material Output > Displacement and material.displacement_method is set
                   (True = BOTH). Use it on subdivided preview meshes; road meshes are coarse, keep None there.
    viewport / roughness / metallic : viewport display values (also what the road tool's glTF export falls back to)
    settings     : other material attributes, e.g. {"surface_render_method": "DITHERED"} (errors ignored)
    The material gets a fake user (kept in saved libraries) and the custom property "procmat" = group name."""
    name = pm_name(name)
    tree = group if isinstance(group, bpy.types.NodeTree) else bpy.data.node_groups[pm_name(group)]
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = tree; g.name = GROUP_NODE; g.label = tree.name; g.width = 280
    g.location = (0.0, 0.0)
    missing = set_inputs(g, **defaults)
    if missing: print("[procmat] %s: unknown inputs %s" % (name, missing))
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (420.0, 0.0)
    nt.links.new(g.outputs["BSDF"], out.inputs["Surface"])
    method = "BUMP"
    if displacement:
        method = "BOTH" if displacement is True else str(displacement)
        if "Displacement" in g.outputs:
            nt.links.new(g.outputs["Displacement"], out.inputs["Displacement"])
        elif "Height" in g.outputs:
            d = nt.nodes.new("ShaderNodeDisplacement"); d.location = (220.0, -260.0)
            d.inputs["Midlevel"].default_value = 0.0; d.inputs["Scale"].default_value = 1.0
            nt.links.new(g.outputs["Height"], d.inputs["Height"]); nt.links.new(d.outputs[0], out.inputs["Displacement"])
        else:
            print("[procmat] %s: displacement asked but %s has no Displacement / Height output" % (name, tree.name))
    try: m.displacement_method = method
    except (AttributeError, TypeError): pass
    if viewport is None:
        cands = [g.inputs[k] for k in ("Base Color", "Color", "Albedo", "Tint") if k in g.inputs]
        cands += [s for s in g.inputs if s.name.endswith("Color") and s not in cands]
        for s in cands:
            if s.type == "RGBA": viewport = tuple(s.default_value); break
    m.diffuse_color = _rgba(viewport if viewport is not None else (0.5, 0.5, 0.5, 1.0))
    if roughness is not None: m.roughness = roughness
    if metallic is not None: m.metallic = metallic
    for k, v in (settings or {}).items():
        try: setattr(m, k, v)
        except (AttributeError, TypeError, ValueError) as e: print("[procmat] %s: setting %s: %s" % (name, k, e))
    m.use_fake_user = fake_user
    m["procmat"] = tree.name
    return m


def append_materials(blend_path, names=None, link=False):
    """Load materials (with their PM_ groups) from a saved library .blend (run.py --save) into the open file:
    names = material names, or None for every PM_ material. link=True links instead of appending. Returns them."""
    with bpy.data.libraries.load(blend_path, link=link) as (src, dst):
        dst.materials = [n for n in src.materials if (n in names if names else n.startswith(PREFIX))]
    return [m for m in dst.materials if m is not None]


def check_contract(mat):
    """Problems with a material's contract (an empty list = OK)."""
    mat = material(mat); p = []
    if not mat.name.startswith(PREFIX): p.append("name does not start with %s" % PREFIX)
    nt = mat.node_tree
    if nt is None: return p + ["no node tree"]
    groups = [x for x in nt.nodes if x.bl_idname == "ShaderNodeGroup"]
    if len(groups) != 1: p.append("%d group nodes (want 1)" % len(groups))
    node = nt.nodes.get(GROUP_NODE)
    if node is None or node.bl_idname != "ShaderNodeGroup" or node.node_tree is None:
        return p + ["no group node named %r" % GROUP_NODE]
    if node.label != node.node_tree.name: p.append("label %r != group name %r" % (node.label, node.node_tree.name))
    for k in ("Use UV", "Tile Size"):
        if k not in node.inputs: p.append("group input %r missing" % k)
    for k in ("BSDF", "Albedo"):
        if k not in node.outputs: p.append("group output %r missing" % k)
    outs = [x for x in nt.nodes if x.type == "OUTPUT_MATERIAL"]
    if not outs: return p + ["no Material Output"]
    surf = outs[0].inputs["Surface"]
    if not surf.is_linked or surf.links[0].from_node != node or surf.links[0].from_socket.name != "BSDF":
        p.append("Material Output Surface is not fed by MRS.BSDF")
    return p
