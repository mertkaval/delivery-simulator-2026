"""Traffic-signal and traffic-sign factories for Mert Road Studio v2 (Blender 5.2, headless-safe).

Built on top of assets.py (same bmesh primitives, `pmat` materials, bevel/UV finishing, visual style).

Signals  - `make_signal(name, style, ...)`: pole object (origin at the base, +Z up) with every signal head as its own
           child object `<name>_head<i>`. Heads face local -Y (the traffic they control approaches from -Y).
           Every lens is its own material `MRS_Lens_<Red|Amber|Green|PedRed|PedGreen|BikeRed|BikeAmber|BikeGreen>`:
           a Value node named `State` (0 = off, 1 = lit) -> Math MULTIPLY (`StateStrength`, x LENS_PEAK) -> Principled
           `Emission Strength`, and a ColorRamp driven by the same State darkens the base colour when off.
           `set_lens_state()` / `set_signal_state()` switch states, `bake_lens_states()` writes constants for export.
Signs    - `make_sign(name, kind, ...)`: post + grey back + coloured face + border bands + pictogram mesh; legends are
           editable FONT children `<name>_text[<i>]` facing +Y (assets.py sign convention), `bake_sign_text(obj)`
           converts them to meshes for export.  `make_direction_board()` builds a two-post green board.
Library  - `build_signage()` -> hidden objects in MRS_Signage; `demo_collection()` -> one of everything, visible, in
           MRS_SignageDemo for the catalogue render.
"""
import math
import bpy, bmesh
from mathutils import Vector, Matrix
from .nodes import MRS, depsgraph
from . import assets as A
from .assets import (pmat, M, _box, _cyl, _tube, _lathe, _prism, _band, _shape, _inset, _xf, _arrow_pts, _stroke,
                     _figure, _ngon, _finish, _uv, _plate, _border, S_POST, S_WHITE, S_BLACK, S_RED, S_BLUE, S_YELLOW,
                     S_GREEN, S_BACK, TAU)

LIB = MRS + "Signage"
DEMO = MRS + "SignageDemo"
LENS_PEAK = 3.5           # emission strength at State = 1 (saturated but not blown out with the Standard view transform)
S_ORANGE, S_BROWN, S_GREY, S_DARKGREY = 8, 9, 10, 11

LENS_RGB = {   # pure linear colours: the display transform lifts small components a lot (0.1 linear -> 0.35 sRGB)
    "Red": (1.0, 0.02, 0.0), "Amber": (1.0, 0.45, 0.0), "Green": (0.0, 1.0, 0.05),
    "PedRed": (1.0, 0.03, 0.01), "PedGreen": (0.02, 1.0, 0.08),
    "BikeRed": (1.0, 0.02, 0.0), "BikeAmber": (1.0, 0.45, 0.0), "BikeGreen": (0.0, 1.0, 0.05),
}
HEAD_LENSES = {"vehicle": ["Red", "Amber", "Green"], "pedestrian": ["PedRed", "PedGreen"], "bicycle": ["BikeRed", "BikeAmber", "BikeGreen"]}
FACE_RGB = {
    "White": (0.92, 0.92, 0.9), "Black": (0.03, 0.03, 0.035), "Red": (0.75, 0.05, 0.04), "Blue": (0.04, 0.18, 0.6),
    "Yellow": (0.95, 0.75, 0.05), "Green": (0.03, 0.3, 0.12), "Orange": (0.95, 0.4, 0.05), "Brown": (0.4, 0.22, 0.1), "Grey": (0.45, 0.45, 0.45),
    "DarkGrey": (0.2, 0.2, 0.22),
}
SIGN_KINDS = ("stop", "yield", "speed_limit", "one_way", "no_entry", "no_left_turn", "no_right_turn", "straight_only", "turn_left_only",
              "turn_right_only", "bicycle_route", "pedestrian_crossing", "bus_stop", "parking", "no_parking", "street_name", "direction_board",
              "roundabout", "dead_end", "children", "roadworks", "priority_road", "give_way_ahead", "speed_zone_end")
SIGNAL_STYLES = ("post", "mast_arm", "pedestrian", "bicycle", "combined")
SM = {}  # signage material registry


# ============================================================================== materials
def lens_material(key):
    """`MRS_Lens_<key>`: emissive Principled BSDF whose strength is State (Value node) x LENS_PEAK."""
    if key not in LENS_RGB: raise KeyError("unknown lens %r, expected one of %s" % (key, sorted(LENS_RGB)))
    rgb = LENS_RGB[key]; name = MRS + "Lens_" + key
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (300, 0); b.name = "Lens"
    st = nt.nodes.new("ShaderNodeValue"); st.name = "State"; st.label = "State (0 off / 1 lit)"; st.location = (-700, 0)
    st.outputs[0].default_value = 0.0
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.name = "StateStrength"; mul.label = "State x peak"; mul.location = (-300, -200)
    mul.inputs[1].default_value = LENS_PEAK; mul.use_clamp = False
    nt.links.new(st.outputs[0], mul.inputs[0]); nt.links.new(mul.outputs[0], b.inputs["Emission Strength"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.name = "StateTone"; ramp.location = (-350, 150)
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*[c * 0.16 for c in rgb], 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (*[min(1.0, c * 0.95) for c in rgb], 1)
    nt.links.new(st.outputs[0], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.2; b.inputs["Coat Weight"].default_value = 0.15
    nt.links.new(b.outputs[0], out.inputs[0])
    m.diffuse_color = (*rgb, 1); m["mrs_lens"] = key; m["mrs_lens_peak"] = LENS_PEAK
    return m


def lens_state(mat):
    n = mat.node_tree.nodes.get("State") if mat.node_tree else None
    return float(n.outputs[0].default_value) if n else 0.0


def lens_strength(mat):
    """Effective emission strength of a lens material (follows State -> StateStrength -> Emission Strength)."""
    nt = mat.node_tree; b = nt.nodes.get("Lens"); sock = b.inputs["Emission Strength"]
    if not sock.is_linked: return float(sock.default_value)
    mul = sock.links[0].from_node
    if mul.name == "StateStrength": return lens_state(mat) * float(mul.inputs[1].default_value)
    return float(sock.default_value)


def set_lens_state(mat, state):
    """State 0..1. Also mirrors state x peak into the (linked) Emission Strength default, so an export that drops
    the link still carries the right constant."""
    st = mat.node_tree.nodes.get("State")
    if st is None: raise ValueError("%s has no State node" % mat.name)
    st.outputs[0].default_value = float(state)
    b = mat.node_tree.nodes.get("Lens")
    if b: b.inputs["Emission Strength"].default_value = float(state) * LENS_PEAK
    return mat


def set_signal_state(obj, lit="off"):
    """Switch lens states for every lens material used by `obj` (and its heads). `lit` is a colour word
    ("red" | "amber" | "green" | "off") or an iterable of lens keys to turn on; every other lens goes off.
    Lens materials are shared by every signal in the file, so this is effectively a scene-wide switch."""
    if isinstance(lit, str): on = {k for k in LENS_RGB if lit != "off" and k.lower().endswith(lit.lower())}
    else: on = set(lit)
    for o in [obj] + list(obj.children_recursive):
        if o.type != "MESH": continue
        for m in o.data.materials:
            if m and m.get("mrs_lens"): set_lens_state(m, 1.0 if m["mrs_lens"] in on else 0.0)
    return on


def bake_lens_states(materials=None):
    """Replace the State wiring with constants (for exporters that cannot follow links): Emission Strength =
    state x peak, Base Color = lit/dark tone. Returns the baked materials."""
    mats = materials or [m for m in bpy.data.materials if m.get("mrs_lens")]
    for m in mats:
        nt = m.node_tree; b = nt.nodes.get("Lens"); s = lens_state(m); rgb = LENS_RGB[m["mrs_lens"]]
        for sock in (b.inputs["Emission Strength"], b.inputs["Base Color"]):
            for l in list(sock.links): nt.links.remove(l)
        b.inputs["Emission Strength"].default_value = s * LENS_PEAK
        b.inputs["Base Color"].default_value = (*[c * (0.16 + 0.79 * s) for c in rgb], 1)
        m["mrs_lens_baked"] = True
    return mats


def _housing_material(rgb):
    if tuple(round(c, 3) for c in rgb) == (0.08, 0.08, 0.08): name = MRS + "SignalHousing"
    else: name = MRS + "SignalHousing_%02x%02x%02x" % tuple(int(max(0.0, min(1.0, c)) * 255) for c in rgb)
    return bpy.data.materials.get(name) or pmat(name, tuple(rgb[:3]), 0.5, 0.15, var=0.1, scale=8.0, rough_var=0.15)


def face_material(colour):
    """`MRS_SignFace_<Colour>` (noise-driven tone + roughness variation). `colour` is a FACE_RGB key or an RGB tuple."""
    if isinstance(colour, str):
        key = colour[:1].upper() + colour[1:]; rgb = FACE_RGB[key]
    else:
        rgb = tuple(colour[:3]); key = "%02x%02x%02x" % tuple(int(max(0.0, min(1.0, c)) * 255) for c in rgb)
    name = MRS + "SignFace_" + key
    return bpy.data.materials.get(name) or pmat(name, rgb, 0.35, var=0.05, scale=9.0, rough_var=0.14)


def _materials():
    if not M: A._materials()
    SM.clear()
    SM.update(pole=M["metal"], steel=M["steel"], back=M["grey"], housing=_housing_material((0.08, 0.08, 0.08)),
              glass=pmat(MRS + "SignalGlass", (0.015, 0.015, 0.02), 0.08, var=0.0, rough_var=0.03), reflect=face_material("Yellow"),
              lens={k: lens_material(k) for k in LENS_RGB}, face={k: face_material(k) for k in FACE_RGB})
    return SM


def _sign_mats(extra=None):
    """Material slots in S_* order (post, white, black, red, blue, yellow, green, back, orange, brown, grey [, extra])."""
    f = SM["face"]
    mats = [SM["steel"], f["White"], f["Black"], f["Red"], f["Blue"], f["Yellow"], f["Green"], SM["back"], f["Orange"], f["Brown"], f["Grey"], f["DarkGrey"]]
    if extra is not None: mats.append(extra)
    return mats


# ============================================================================== object helpers
def _col(name, clear=False, hidden=False):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    if clear:
        for name in [o.name for o in col.objects]:          # by name: removing a parent also removes its children
            o = bpy.data.objects.get(name)
            if o is not None: _remove_tree(o)
    col.hide_render = hidden
    return col


def _remove_tree(o):
    try: kids = [c.name for c in o.children]
    except ReferenceError: return
    for n in kids:
        c = bpy.data.objects.get(n)
        if c is not None: _remove_tree(c)
    data = o.data
    try: bpy.data.objects.remove(o)
    except ReferenceError: return
    if data is not None and data.users == 0:
        for coll in (bpy.data.meshes, bpy.data.curves):
            if data.name in coll and coll[data.name] == data: coll.remove(data); break


def _fresh(name):
    old = bpy.data.objects.get(name)
    if old: _remove_tree(old)


def _mesh_obj(name, builder, mats, bevel=0.0, col=None, parent=None, at=(0, 0, 0)):
    bm = bmesh.new(); bm.faces.layers.int.new("nobevel"); builder(bm); _finish(bm, bevel)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    o = bpy.data.objects.new(name, me); (col or bpy.context.scene.collection).objects.link(o)
    if parent is not None: o.parent = parent
    o.location = at
    return o


def _taper(bm, a, b, r0, r1, n=12, mi=0, caps=True):
    """Straight tapered tube from a to b."""
    a, b = Vector(a), Vector(b); d = (b - a).normalized()
    u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized(); v = d.cross(u)
    ra = [bm.verts.new(a + (u * math.cos(TAU * k / n) + v * math.sin(TAU * k / n)) * r0) for k in range(n)]
    rb = [bm.verts.new(b + (u * math.cos(TAU * k / n) + v * math.sin(TAU * k / n)) * r1) for k in range(n)]
    for k in range(n):
        f = bm.faces.new((ra[k], ra[(k + 1) % n], rb[(k + 1) % n], rb[k])); f.material_index = mi; f.smooth = True
    if caps: bm.faces.new(ra[::-1]).material_index = mi; bm.faces.new(rb).material_index = mi


def _shell(bm, o0, o1, i0, i1, mi, smooth=True):
    """Closed thin shell between an outer strip (o0 -> o1) and an inner strip (i0 -> i1), all lists of n verts."""
    n = len(o0)
    for k in range(n - 1):
        for quad in ((o0[k], o0[k + 1], o1[k + 1], o1[k]), (i0[k + 1], i0[k], i1[k], i1[k + 1]),
                     (o0[k + 1], o0[k], i0[k], i0[k + 1]), (o1[k], o1[k + 1], i1[k + 1], i1[k])):
            f = bm.faces.new(quad); f.material_index = mi; f.smooth = smooth
    bm.faces.new((o0[0], i0[0], i1[0], o1[0])).material_index = mi
    bm.faces.new((o0[-1], o1[-1], i1[-1], i0[-1])).material_index = mi


def _hood(bm, x, y0, zc, r, length, mi, droop=0.25):
    """Sun visor over a lens: closed shell arc (top 3/4 of the circle) pointing -Y from y0, tapering and drooping."""
    n = 13; outer0, outer1, inner0, inner1 = [], [], [], []
    for k in range(n):
        ang = math.pi * (-0.12 + 1.24 * k / (n - 1)); c, s = math.cos(ang), math.sin(ang)
        outer0.append(bm.verts.new((x + r * c, y0, zc + r * s))); inner0.append(bm.verts.new((x + (r - 0.006) * c, y0, zc + (r - 0.006) * s)))
        r1 = r * 0.92; z1 = zc - droop * r
        outer1.append(bm.verts.new((x + r1 * c, y0 - length, z1 + r1 * s))); inner1.append(bm.verts.new((x + (r1 - 0.006) * c, y0 - length, z1 + (r1 - 0.006) * s)))
    _shell(bm, outer0, outer1, inner0, inner1, mi)


def _lens_disc(bm, x, yf, zc, r, mi_lens, mi_house, depth=0.035):
    """Lens cylinder proud of the housing face yf (towards -Y) with a bezel ring."""
    _tube(bm, [(x, yf, zc), (x, yf - depth, zc)], r, 24, mi_lens)
    _tube(bm, [(x, yf + 0.001, zc), (x, yf - 0.012, zc)], r + 0.014, 24, mi_house)


# ============================================================================== signal heads (origin = top centre of the housing, face -Y)
def _head_vehicle(bm, lens_size, mi_house, mi_glass, mi_reflect, mi_lenses):
    D = lens_size; pitch = 1.5 * D; w = 1.6 * D; d = 1.25 * D; n = len(mi_lenses); h = n * pitch + 0.03
    _box(bm, -w / 2, -d / 2, -h, w / 2, d / 2, 0.0, mi_house)                                   # housing
    yf = -d / 2
    bw, bh = w / 2 + 0.6 * D, 0.5 * D                                                           # backplate + reflective border
    plate = [(-bw, -h - bh), (bw, -h - bh), (bw, bh), (-bw, bh)]
    _prism(bm, plate, yf - 0.004, yf, mi_house)
    _band(bm, plate, _inset(plate, 0.025), yf - 0.006, yf - 0.004, mi_reflect)
    for i, mi in enumerate(mi_lenses):
        zc = -0.015 - pitch * (i + 0.5)
        _lens_disc(bm, 0.0, yf - 0.006, zc, D / 2, mi, mi_house)
        _hood(bm, 0.0, yf - 0.002, zc, D / 2 + 0.03, 0.95 * D, mi_house)
    _cyl(bm, 0, 0, 0.0, 0.07, 0.03, 0.03, 10, mi_house)                                          # mount stubs
    _cyl(bm, 0, 0, -h - 0.05, -h, 0.03, 0.03, 10, mi_house)
    return h


def _ped_standing(bm, cx, cz, h, y0, y1, mi):
    hr = 0.085 * h; w = 0.1 * h
    _prism(bm, _xf(_ngon(10, hr), dx=cx, dz=cz + h - hr), y0, y1, mi)
    _prism(bm, [(cx - 0.12 * h, cz + 0.45 * h), (cx + 0.12 * h, cz + 0.45 * h), (cx + 0.12 * h, cz + h - 2.2 * hr), (cx - 0.12 * h, cz + h - 2.2 * hr)], y0, y1, mi)
    for s in (-1, 1):
        _stroke(bm, [(cx + s * 0.06 * h, cz + 0.46 * h), (cx + s * 0.06 * h, cz)], w, y0, y1, mi)
        _stroke(bm, [(cx + s * 0.12 * h, cz + h - 2.3 * hr), (cx + s * 0.17 * h, cz + 0.45 * h)], w * 0.8, y0, y1, mi)


def _head_pedestrian(bm, lens_size, mi_house, mi_glass, mi_reflect, mi_lenses):
    W = 1.3 * lens_size; w = W + 0.06; d = 0.9 * lens_size; h = 2 * (W + 0.05) + 0.03
    _box(bm, -w / 2, -d / 2, -h, w / 2, d / 2, 0.0, mi_house)
    yf = -d / 2
    for i, mi in enumerate(mi_lenses):
        zt = -0.015 - (W + 0.05) * i - 0.025; zb = zt - W
        win = [(-W / 2, zb), (W / 2, zb), (W / 2, zt), (-W / 2, zt)]
        _prism(bm, win, yf - 0.005, yf, mi_glass)                                                # dark window
        _band(bm, win, _inset(win, 0.012), yf - 0.009, yf - 0.005, mi_house)                      # window frame
        fh = W * 0.8; cz = zb + (W - fh) / 2
        if i == 0: _ped_standing(bm, 0.0, cz, fh, yf - 0.012, yf - 0.005, mi)
        else: _figure(bm, 0.0, cz, fh, yf - 0.012, yf - 0.005, mi, stride=0.3)
        _box(bm, -w / 2, yf - 0.1, zt + 0.004, w / 2, yf + 0.002, zt + 0.02, mi_house)             # visor
    _cyl(bm, 0, 0, 0.0, 0.07, 0.025, 0.025, 10, mi_house); _cyl(bm, 0, 0, -h - 0.05, -h, 0.025, 0.025, 10, mi_house)
    return h


def _bicycle_glyph(bm, cx, cz, s, y0, y1, mi):
    """Side-view bicycle, overall width ~s, in the x/z plane."""
    r = 0.22 * s; wx = 0.3 * s
    for sx in (-1, 1):
        ring = _ngon(16, r); _band(bm, _xf(ring, dx=cx + sx * wx, dz=cz + r), _xf(_ngon(16, r * 0.72), dx=cx + sx * wx, dz=cz + r), y0, y1, mi)
    w = 0.045 * s; z0 = cz + r
    _stroke(bm, [(cx - wx, z0), (cx - 0.05 * s, z0 + 0.42 * s), (cx + 0.25 * s, z0 + 0.42 * s)], w, y0, y1, mi)     # top tube + bars
    _stroke(bm, [(cx - wx, z0), (cx + 0.02 * s, z0), (cx + wx, z0)], w, y0, y1, mi)                            # chain stay
    _stroke(bm, [(cx + 0.02 * s, z0), (cx - 0.02 * s, z0 + 0.45 * s)], w, y0, y1, mi)                          # seat tube
    _stroke(bm, [(cx + wx, z0), (cx + 0.2 * s, z0 + 0.45 * s)], w, y0, y1, mi)                                 # fork
    _stroke(bm, [(cx - 0.08 * s, z0 + 0.47 * s), (cx + 0.03 * s, z0 + 0.47 * s)], w * 1.3, y0, y1, mi)         # saddle


def _head_bicycle(bm, lens_size, mi_house, mi_glass, mi_reflect, mi_lenses):
    D = 0.75 * lens_size; pitch = 1.45 * D; w = 1.7 * D; d = 1.1 * D; n = len(mi_lenses); h = n * pitch + 0.03
    _box(bm, -w / 2, -d / 2, -h, w / 2, d / 2, 0.0, mi_house)
    yf = -d / 2
    for i, mi in enumerate(mi_lenses):
        zc = -0.015 - pitch * (i + 0.5)
        _lens_disc(bm, 0.0, yf - 0.004, zc, D / 2, mi_glass, mi_house, depth=0.02)
        _bicycle_glyph(bm, 0.0, zc - 0.3 * D, 0.8 * D, yf - 0.03, yf - 0.024, mi)
        _hood(bm, 0.0, yf - 0.002, zc, D / 2 + 0.025, 0.8 * D, mi_house)
    _cyl(bm, 0, 0, 0.0, 0.07, 0.025, 0.025, 10, mi_house); _cyl(bm, 0, 0, -h - 0.05, -h, 0.025, 0.025, 10, mi_house)
    return h


HEAD_BUILDERS = {"vehicle": _head_vehicle, "pedestrian": _head_pedestrian, "bicycle": _head_bicycle}
HEAD_HEIGHT = {"vehicle": lambda D: 3 * 1.5 * D + 0.03, "pedestrian": lambda D: 2 * (1.3 * D + 0.05) + 0.03, "bicycle": lambda D: 3 * 1.45 * 0.75 * D + 0.03}
HEAD_DEPTH = {"vehicle": lambda D: 1.25 * D, "pedestrian": lambda D: 0.9 * D, "bicycle": lambda D: 1.1 * 0.75 * D}


def _make_head(name, kind, lens_size, mats_house, col, parent, at):
    lenses = HEAD_LENSES[kind]
    mats = [mats_house["housing"], SM["glass"], SM["reflect"]] + [SM["lens"][k] for k in lenses]
    hinfo = {}

    def build(bm):
        hinfo["h"] = HEAD_BUILDERS[kind](bm, lens_size, 0, 1, 2, list(range(3, 3 + len(lenses))))
    o = _mesh_obj(name, build, mats, 0.004, col, parent, at)
    o["mrs_signal_head"] = {"kind": kind, "lenses": lenses, "lens_materials": [MRS + "Lens_" + k for k in lenses], "faces": "-Y"}
    return o, hinfo["h"]


# ============================================================================== signals
def make_signal(name, style="post", pole_height=4.0, arm_length=0.0, heads=("vehicle",), setback=0.0, lens_size=0.2,
                housing_color=(0.08, 0.08, 0.08), collection=None):
    """Signal pole `name` (origin at the base, +Z up, heads facing -Y) with child head objects `<name>_head<i>`.
    style: post | mast_arm (arm along +X, `arm_length`) | pedestrian | bicycle | combined (vehicle + pedestrian head).
    `setback` shifts the pole +Y behind the origin (kerb reference point). Returns the pole object."""
    if style not in SIGNAL_STYLES: raise ValueError("style %r not in %s" % (style, SIGNAL_STYLES))
    if not SM: _materials()
    heads = tuple(heads)
    if heads == ("vehicle",):   # default per style
        heads = {"pedestrian": ("pedestrian",), "bicycle": ("bicycle",), "combined": ("vehicle", "pedestrian")}.get(style, heads)
    if style == "mast_arm" and arm_length <= 0: arm_length = 5.0
    _fresh(name)
    col = collection or bpy.context.scene.collection
    house = _housing_material(housing_color); mats_house = {"housing": house}
    H = pole_height; D = lens_size; sy = setback
    r0, r1 = {"post": (0.075, 0.055), "combined": (0.075, 0.055), "mast_arm": (0.16, 0.11), "pedestrian": (0.06, 0.05), "bicycle": (0.06, 0.05)}[style]
    mounts = []   # (kind, (x, y, z) head origin, bracket geometry callback)

    # ---- plan the heads
    if style == "mast_arm":
        L = arm_length; z_root = H - 0.35; z_tip = H - 0.12
        def z_arm(x): return z_root + (z_tip - z_root) * x / L
        k = 0
        for kind in heads:
            if kind == "pedestrian":
                mounts.append((kind, (0.0, sy - r1 - HEAD_DEPTH[kind](D) / 2 - 0.05, min(H - 0.3, 2.9)), "side")); continue
            x = L - 0.7 - 2.4 * k; k += 1
            if x < 1.2: x = 1.2 + 0.4 * k
            mounts.append((kind, (x, sy, z_arm(x) - 0.085 - 0.22), "hang"))
    else:
        ztop = H - 0.06
        for kind in heads:
            if kind == "pedestrian" and style in ("combined",): ztop = min(ztop, 2.75)
            if kind == "pedestrian" and style == "pedestrian": ztop = min(ztop, 2.9)
            if kind == "bicycle" and style == "bicycle": ztop = min(ztop, 2.7)
            mounts.append((kind, (0.0, sy - r1 - HEAD_DEPTH[kind](D) / 2 - 0.05, ztop), "side"))
            ztop = ztop - HEAD_HEIGHT[kind](D) - 0.3

    # ---- pole mesh
    def pole(bm):
        _cyl(bm, 0, sy, 0, 0.03, r0 * 3.0, r0 * 3.0, 16, 0); _cyl(bm, 0, sy, 0.03, 0.5, r0 * 1.5, r0 * 1.25, 14, 0)
        _cyl(bm, 0, sy, 0.5, H, r0, r1, 14, 0); _lathe(bm, [(r1 + 0.01, H), (r1 + 0.01, H + 0.02), (0.0, H + 0.04)], 14, 0, y=sy)
        if style == "mast_arm":
            _cyl(bm, 0, sy, H - 0.75, H - 0.1, r1 + 0.03, r1 + 0.03, 14, 0)                      # collar
            _taper(bm, (0.0, sy, z_root), (L, sy, z_tip), 0.085, 0.05, 12, 0)                   # arm
            _taper(bm, (0.0, sy, H - 1.4), (min(1.6, L * 0.35), sy, z_arm(min(1.6, L * 0.35)) - 0.06), 0.03, 0.03, 8, 0)   # brace
            _box(bm, -0.06, sy - 0.14, H - 1.5, 0.3, sy + 0.14, H - 1.3, 0)
        for kind, (x, y, z), how in mounts:
            if how == "hang":
                _cyl(bm, x, y, z, z_arm(x), 0.03, 0.03, 10, 0); _cyl(bm, x, y, z_arm(x) - 0.02, z_arm(x) + 0.1, 0.06, 0.06, 10, 0)
            else:
                hh = HEAD_HEIGHT[kind](D)
                for zz in (z - 0.08, z - hh + 0.08):
                    _tube(bm, [(0, sy, zz), (0, y + 0.02, zz)], 0.025, 8, 0)
                    _cyl(bm, 0, sy, zz - 0.04, zz + 0.04, r1 + 0.012, r1 + 0.012, 14, 0)
        if any(k == "pedestrian" for k, _, _ in mounts):                                          # push-button box
            _box(bm, -0.06, sy - r1 - 0.09, 1.0, 0.06, sy, 1.2, 0)
            _tube(bm, [(0, sy - r1 - 0.09, 1.1), (0, sy - r1 - 0.12, 1.1)], 0.03, 12, 1)
    pole_o = _mesh_obj(name, pole, [SM["pole"], SM["reflect"]], 0.008, col)

    # ---- heads (children)
    head_info = []
    for i, (kind, at, how) in enumerate(mounts):
        hname = "%s_head%d" % (name, i)
        ho, hh = _make_head(hname, kind, D, mats_house, col, pole_o, at)
        head_info.append({"kind": kind, "lenses": HEAD_LENSES[kind], "mesh_names": [ho.data.name], "object": ho.name,
                          "lens_materials": [MRS + "Lens_" + k for k in HEAD_LENSES[kind]], "mount": how})
    pole_o["mrs_signal"] = {"style": style, "pole_height": H, "arm_length": arm_length if style == "mast_arm" else 0.0, "setback": sy,
                            "lens_size": D, "faces": "-Y", "housing": house.name, "heads": head_info}
    return pole_o


# ============================================================================== sign legends (FONT children)
def _text_child(parent, name, text, size, at, yaw=0.0, colour="White", max_width=None, depth=0.004, align="CENTER", col=None):
    """FONT curve child of `parent` at local `at`, readable from the +Y side rotated by `yaw` (face normal = Rz(yaw)·+Y)."""
    cu = bpy.data.curves.new(name, "FONT"); cu.body = text; cu.size = size; cu.extrude = depth / 2; cu.align_x = align; cu.align_y = "CENTER"
    cu.fill_mode = "BOTH"; cu.resolution_u = 3; cu.materials.append(SM["face"][colour] if isinstance(colour, str) else colour)
    o = bpy.data.objects.new(name, cu); (col or bpy.context.scene.collection).objects.link(o)
    o.parent = parent; o.location = at; o.rotation_euler = (math.pi / 2, 0.0, math.pi + yaw)
    o["mrs_legend"] = {"text": text, "size": size, "colour": colour if isinstance(colour, str) else colour.name, "max_width": max_width or 0.0}
    if max_width:
        bpy.context.view_layer.update(); w = o.dimensions.x
        if w > max_width > 1e-6: o.scale.x = max_width / w
    return o


def bake_sign_text(obj):
    """Convert every FONT child of `obj` into a mesh object with the same name / parent / transform (for export).
    Returns the new mesh objects."""
    out = []
    for ch in list(obj.children_recursive):
        if ch.type != "FONT": continue
        dg = depsgraph(); me = bpy.data.meshes.new_from_object(ch.evaluated_get(dg))
        if not me.materials:
            for m in ch.data.materials: me.materials.append(m)
        bm = bmesh.new(); bm.from_mesh(me); _uv(bm); bm.to_mesh(me); bm.free()
        nm, parent, ml, cols, legend = ch.name, ch.parent, ch.matrix_local.copy(), list(ch.users_collection), ch.get("mrs_legend")
        legend = legend.to_dict() if legend is not None and hasattr(legend, "to_dict") else legend
        hv, hr = ch.hide_viewport, ch.hide_render
        _remove_tree(ch); me.name = nm
        o = bpy.data.objects.new(nm, me)
        for c in cols: c.objects.link(o)
        o.parent = parent; o.matrix_local = ml; o.hide_viewport = hv; o.hide_render = hr
        if legend: o["mrs_legend"] = legend
        o["mrs_legend_baked"] = True
        out.append(o)
    meta = obj.get("mrs_sign")
    if meta is not None: d = meta.to_dict(); d["text_baked"] = True; obj["mrs_sign"] = d
    return out


# ============================================================================== sign pictograms (x,z 2D, extruded along Y)
# Signs face +Y, so a viewer reading them has world -X on their RIGHT. `side` arguments are in viewer terms
# (+1 = viewer's right, -1 = viewer's left); `_vx(side)` is the matching world-X sign and `_vrot(side)` the
# rotation that turns a +Z arrow glyph towards that side.
def _vx(side): return -side
def _vrot(side): return side * math.pi / 2


def _turn_arrow(bm, Z, side, yf, mi, w=0.075):
    """Arrow going up then bending to the viewer's `side` (0: straight up)."""
    if side == 0:
        _prism(bm, _xf(_arrow_pts(0.5, w, 0.24, 0.17), 0.0, 0.0, Z - 0.25), yf, yf + 0.002, mi); return
    ws = _vx(side)
    _stroke(bm, [(-ws * 0.08, Z - 0.26), (-ws * 0.08, Z + 0.02), (-ws * 0.04, Z + 0.1), (ws * 0.04, Z + 0.14)], w, yf, yf + 0.002, mi)
    head = [(-0.11, -0.09), (0.11, -0.09), (0.0, 0.1)]
    _prism(bm, _xf(head, _vrot(side), ws * 0.14, Z + 0.14), yf, yf + 0.002, mi)


def _slash(bm, Z, yf, mi, half=0.3, w=0.075):
    _prism(bm, _xf([(-w / 2, -half), (w / 2, -half), (w / 2, half), (-w / 2, half)], math.radians(45), 0, Z), yf, yf + 0.002, mi)


# ============================================================================== signs
SIGN_SIZE = {"stop": 0.8, "yield": 0.9, "speed_limit": 0.75, "one_way": 1.0, "no_entry": 0.75, "no_left_turn": 0.75, "no_right_turn": 0.75,
             "straight_only": 0.75, "turn_left_only": 0.75, "turn_right_only": 0.75, "bicycle_route": 0.75, "pedestrian_crossing": 0.65,
             "bus_stop": 0.7, "parking": 0.65, "no_parking": 0.75, "street_name": 0.9, "direction_board": 1.6, "roundabout": 0.75,
             "dead_end": 0.65, "children": 0.9, "roadworks": 0.9, "priority_road": 0.75, "give_way_ahead": 0.9, "speed_zone_end": 0.75}


def make_sign(name, kind, text=None, value=None, pole_height=2.3, size=None, collection=None, double=False, face_color=None):
    """Sign post `name` of `kind` (see SIGN_KINDS): plate centred at `pole_height`, facing +Y, origin at the base.
    text: legend / street name / "left"|"right" for one_way / "DEST|12 km" lines for direction_board. value: number for
    speed_limit / speed_zone_end, arrow direction for direction_board. double: street_name with a second blade at 90 deg.
    face_color: optional RGB override of the plate colour. Legends are FONT children `<name>_text[<i>]`."""
    if kind not in SIGN_KINDS: raise ValueError("kind %r not in %s" % (kind, SIGN_KINDS))
    if not SM: _materials()
    _fresh(name)
    col = collection or bpy.context.scene.collection
    s = size or SIGN_SIZE[kind]; Z = pole_height
    extra = face_material(tuple(face_color)) if face_color is not None else None
    mats = _sign_mats(extra); S_EXTRA = len(mats) - 1
    texts = []   # (suffix, text, size, at, yaw, colour, max_width, align)
    meta = {"kind": kind, "text": text if text is not None else "", "value": value if value is not None else "", "size": s, "pole_height": Z,
            "double": bool(double), "faces": "+Y"}

    def face(default): return S_EXTRA if extra is not None else default

    def build(bm):
        if kind == "stop":
            pts = _shape("octagon", s); yf = _plate(bm, pts, Z, face(S_RED)); yf = _border(bm, pts, Z, 0.03 * s, yf, S_WHITE)
            texts.append(("", text or "STOP", 0.37 * s, (0, yf, Z), 0.0, "White", 0.78 * s, "CENTER"))
        elif kind == "yield":
            pts = _shape("triangle", s); yf = _plate(bm, pts, Z, face(S_WHITE)); _border(bm, pts, Z, 0.11 * s, yf, S_RED)
        elif kind == "speed_limit":
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.11 * s, yf, S_RED)
            v = str(value if value is not None else 50); texts.append(("", v, (0.5 if len(v) <= 2 else 0.4) * s, (0, yf, Z), 0.0, "Black", 0.62 * s, "CENTER"))
        elif kind == "speed_zone_end":
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.03 * s, yf, S_GREY)
            for dx in (-0.17 * s, 0.0, 0.17 * s):   # three diagonal bars, kept inside the disc (half-length 0.3 s at 45 deg)
                _prism(bm, _xf([(-0.02 * s, -0.3 * s), (0.02 * s, -0.3 * s), (0.02 * s, 0.3 * s), (-0.02 * s, 0.3 * s)], math.radians(45), dx, Z), yf, yf + 0.0015, S_BLACK)
            v = str(value if value is not None else 50); texts.append(("", v, 0.46 * s, (0, yf + 0.0015, Z), 0.0, "DarkGrey", 0.62 * s, "CENTER"))
        elif kind == "one_way":
            pts = _shape("rect", 0.3 * s, s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.012, yf, S_WHITE)
            side = -1 if (text or "").strip().lower() in ("left", "l") else 1
            _prism(bm, _xf(_arrow_pts(0.8 * s, 0.07 * s, 0.17 * s, 0.2 * s), _vrot(side), -_vx(side) * 0.4 * s, Z + 0.045 * s), yf, yf + 0.002, S_WHITE)
            texts.append(("", "ONE WAY", 0.075 * s, (0, yf, Z - 0.085 * s), 0.0, "White", 0.7 * s, "CENTER"))
        elif kind == "no_entry":
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_RED)); yf = _border(bm, pts, Z, 0.02 * s, yf, S_WHITE)
            _prism(bm, [(-0.36 * s, Z - 0.08 * s), (0.36 * s, Z - 0.08 * s), (0.36 * s, Z + 0.08 * s), (-0.36 * s, Z + 0.08 * s)], yf, yf + 0.002, S_WHITE)
        elif kind in ("no_left_turn", "no_right_turn"):
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.11 * s, yf, S_RED)
            _turn_arrow(bm, Z, -1 if kind == "no_left_turn" else 1, yf, S_BLACK); _slash(bm, Z, yf + 0.002, S_RED, 0.4 * s, 0.09 * s)
        elif kind in ("straight_only", "turn_left_only", "turn_right_only"):
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.025 * s, yf, S_WHITE)
            _turn_arrow(bm, Z, {"straight_only": 0, "turn_left_only": -1, "turn_right_only": 1}[kind], yf, S_WHITE, w=0.085)
        elif kind == "bicycle_route":
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.025 * s, yf, S_WHITE)
            _bicycle_glyph(bm, 0.0, Z - 0.28 * s, 0.75 * s, yf, yf + 0.002, S_WHITE)
        elif kind == "pedestrian_crossing":
            pts = _shape("square", s); yf = _plate(bm, pts, Z, face(S_BLUE)); tri = _shape("triangle_up", 0.77 * s)
            _prism(bm, [(x, z + Z - 0.03 * s) for x, z in tri], yf, yf + 0.002, S_WHITE)
            _figure(bm, 0.03 * s, Z - 0.34 * s, 0.46 * s, yf + 0.002, yf + 0.004, S_BLACK)
            for i in range(4):
                x = (-0.28 + i * 0.154) * s; _prism(bm, [(x, Z - 0.385 * s), (x + 0.077 * s, Z - 0.385 * s), (x + 0.077 * s, Z - 0.323 * s), (x, Z - 0.323 * s)], yf + 0.002, yf + 0.004, S_BLACK)
        elif kind == "bus_stop":
            pts = _shape("rect", 0.71 * s, s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.02 * s, yf, S_BLACK)
            texts.append(("", text or "BUS STOP", 0.13 * s, (0, yf, Z - 0.23 * s), 0.0, "Black", 0.8 * s, "CENTER"))
            _prism(bm, [(-0.31 * s, Z - 0.07 * s), (0.31 * s, Z - 0.07 * s), (0.31 * s, Z + 0.24 * s), (-0.31 * s, Z + 0.24 * s)], yf, yf + 0.002, S_BLACK)
            for x in (-0.2 * s, 0.2 * s): _prism(bm, _xf(_ngon(12, 0.057 * s), dx=x, dz=Z - 0.085 * s), yf, yf + 0.003, S_BLACK)
            for i in range(3):
                x = (-0.23 + i * 0.17) * s; _prism(bm, [(x, Z + 0.06 * s), (x + 0.114 * s, Z + 0.06 * s), (x + 0.114 * s, Z + 0.185 * s), (x, Z + 0.185 * s)], yf + 0.002, yf + 0.004, S_WHITE)
        elif kind == "parking":
            pts = _shape("square", s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.03 * s, yf, S_WHITE)
            texts.append(("", text or "P", 0.7 * s, (0, yf, Z), 0.0, "White", 0.7 * s, "CENTER"))
        elif kind == "no_parking":
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.095 * s, yf, S_RED); _slash(bm, Z, yf, S_RED, 0.45 * s, 0.1 * s)
        elif kind == "street_name":
            names = [t.strip() for t in (text or "MAIN ST").replace("\n", "|").split("|") if t.strip()] or ["MAIN ST"]
            if double and len(names) == 1: names.append(names[0])
            top = Z + (0.22 * s if double else 0.11 * s)
            _cyl(bm, 0, 0, 0, top - 0.02, 0.035, 0.035, 10, S_POST); _lathe(bm, [(0.04, top - 0.02), (0.0, top)], 10, S_POST)
            for i, nm in enumerate(names[:2 if double else 1]):
                w = max(0.84 * s, 0.072 * s * len(nm) + 0.3 * s); r = [(-w / 2, -0.11 * s), (w / 2, -0.11 * s), (w / 2, 0.11 * s), (-w / 2, 0.11 * s)]
                zc = Z + (0.11 * s if i == 0 else -0.14 * s) if double else Z
                if i == 0:
                    _prism(bm, [(x, z + zc) for x, z in r], 0.035, 0.041, face(S_GREEN)); _prism(bm, [(x, z + zc) for x, z in _inset(r, 0.013 * s)], 0.041, 0.042, S_WHITE)
                    _prism(bm, [(x, z + zc) for x, z in _inset(r, 0.018 * s)], 0.042, 0.043, face(S_GREEN))
                    texts.append(("" if i == 0 else "1", nm, 0.11 * s, (0, 0.043, zc), 0.0, "White", w - 0.12 * s, "CENTER"))
                else:
                    _prism(bm, [(y, z + zc) for y, z in r], 0.035, 0.041, face(S_GREEN), "x"); _prism(bm, [(y, z + zc) for y, z in _inset(r, 0.013 * s)], 0.041, 0.042, S_WHITE, "x")
                    _prism(bm, [(y, z + zc) for y, z in _inset(r, 0.018 * s)], 0.042, 0.043, face(S_GREEN), "x")
                    texts.append(("1", nm, 0.11 * s, (0.043, 0, zc), -math.pi / 2, "White", w - 0.12 * s, "CENTER"))
        elif kind == "direction_board":
            lines = [l for l in (text or "CITY CENTRE|12 km").split("\n") if l.strip()]
            rows = [(l.split("|")[0].strip(), l.split("|")[1].strip() if "|" in l else "") for l in lines]
            n = len(rows); R = 0.26 * s; W = max(1.1 * s, max(0.095 * s * len(a) for a, _ in rows) + 0.75 * s); Hb = n * R + 0.1 * s
            pts = [(-W / 2, -Hb / 2), (W / 2, -Hb / 2), (W / 2, Hb / 2), (-W / 2, Hb / 2)]
            yf = _plate(bm, pts, Z, face(S_GREEN)); yf = _border(bm, pts, Z, 0.02 * s, yf, S_WHITE)
            d = str(value or "right").lower(); ahead = d.startswith("a") or d.startswith("s"); side = -1 if d.startswith("l") else 1
            ax = _vx(side) * (W / 2 - 0.22 * s)                       # arrow column (world x) on the viewer's `side`
            L = 0.17 * s
            for i, (dest, dist) in enumerate(rows):
                zr = Z + Hb / 2 - 0.05 * s - R * (i + 0.5)
                if i: _prism(bm, [(-W / 2 + 0.05 * s, zr + R / 2 - 0.004), (W / 2 - 0.05 * s, zr + R / 2 - 0.004), (W / 2 - 0.05 * s, zr + R / 2 + 0.004), (-W / 2 + 0.05 * s, zr + R / 2 + 0.004)], yf, yf + 0.0015, S_WHITE)
                arrow = _arrow_pts(L, 0.045 * s, 0.13 * s, 0.07 * s)
                if ahead: _prism(bm, _xf(arrow, 0.0, ax, zr - L / 2), yf, yf + 0.002, S_WHITE)
                else: _prism(bm, _xf(arrow, _vrot(side), ax - _vx(side) * L / 2, zr), yf, yf + 0.002, S_WHITE)
                # left-aligned text starts at the viewer's left (world +X), after the arrow column when that is on the left
                tx = W / 2 - (0.42 * s if side < 0 else 0.1 * s)
                texts.append((str(i) if i else "", dest, 0.14 * s, (tx, yf, zr), 0.0, "White", W - 0.95 * s, "LEFT"))
                if dist:   # right-aligned distance ends just before the arrow column (or at the viewer's far right)
                    dx = -(W / 2 - 0.42 * s) if side > 0 else -(W / 2 - 0.08 * s)
                    texts.append(("_dist%d" % i, dist, 0.1 * s, (dx, yf, zr - 0.01 * s), 0.0, "White", 0.4 * s, "RIGHT"))
            meta["rows"] = ["%s|%s" % r for r in rows]
        elif kind == "roundabout":
            pts = _shape("circle", s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.025 * s, yf, S_WHITE)
            ring = _ngon(24, 0.27 * s); _band(bm, [(x, z + Z) for x, z in ring], [(x, z + Z) for x, z in _ngon(24, 0.19 * s)], yf, yf + 0.002, S_WHITE)
            for k in range(3):
                a = TAU * k / 3 + 0.4; tri = [(-0.09 * s, -0.07 * s), (0.09 * s, -0.07 * s), (0.0, 0.12 * s)]
                _prism(bm, _xf(tri, a + math.pi / 2, 0.23 * s * math.cos(a), Z + 0.23 * s * math.sin(a)), yf, yf + 0.002, S_WHITE)
        elif kind == "dead_end":
            pts = _shape("square", s); yf = _plate(bm, pts, Z, face(S_BLUE)); yf = _border(bm, pts, Z, 0.03 * s, yf, S_WHITE)
            _prism(bm, [(-0.077 * s, Z - 0.4 * s), (0.077 * s, Z - 0.4 * s), (0.077 * s, Z + 0.2 * s), (-0.077 * s, Z + 0.2 * s)], yf, yf + 0.002, S_WHITE)
            _prism(bm, [(-0.3 * s, Z + 0.2 * s), (0.3 * s, Z + 0.2 * s), (0.3 * s, Z + 0.36 * s), (-0.3 * s, Z + 0.36 * s)], yf, yf + 0.002, S_RED)
        elif kind == "children":
            pts = _shape("triangle_up", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.09 * s, yf, S_RED)
            _figure(bm, 0.08 * s, Z - 0.33 * s, 0.36 * s, yf, yf + 0.002, S_BLACK, 0.3); _figure(bm, -0.1 * s, Z - 0.33 * s, 0.27 * s, yf, yf + 0.002, S_BLACK, 0.3)
        elif kind == "roadworks":
            pts = _shape("triangle_up", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.09 * s, yf, S_RED)
            _figure(bm, 0.0, Z - 0.33 * s, 0.38 * s, yf, yf + 0.002, S_BLACK, 0.2, arms=False)
            _stroke(bm, [(0.0, Z - 0.055 * s), (0.155 * s, Z - 0.19 * s), (0.22 * s, Z - 0.31 * s)], 0.033 * s, yf, yf + 0.002, S_BLACK)
            _prism(bm, [(0.11 * s, Z - 0.33 * s), (0.29 * s, Z - 0.33 * s), (0.22 * s, Z - 0.22 * s)][::-1], yf, yf + 0.002, S_BLACK)
        elif kind == "priority_road":
            pts = _shape("diamond", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.02 * s, yf, S_GREY)
            _prism(bm, [(x, z + Z) for x, z in _shape("diamond", 0.6 * s)], yf, yf + 0.002, S_YELLOW)
        elif kind == "give_way_ahead":
            pts = _shape("triangle_up", s); yf = _plate(bm, pts, Z, face(S_WHITE)); yf = _border(bm, pts, Z, 0.09 * s, yf, S_RED)
            tri = _shape("triangle", 0.33 * s); _prism(bm, [(x, z + Z - 0.08 * s) for x, z in tri], yf, yf + 0.002, S_BLACK)
            _prism(bm, [(x, z + Z - 0.08 * s) for x, z in _inset(tri, 0.045 * s)], yf + 0.002, yf + 0.004, S_WHITE)
            texts.append(("", text or "AHEAD", 0.075 * s, (0, yf, Z - 0.355 * s), 0.0, "Black", 0.45 * s, "CENTER"))
    o = _mesh_obj(name, build, mats, 0.0, col)
    for suffix, t, ts, at, yaw, colour, mw, align in texts:
        _text_child(o, "%s_text%s" % (name, suffix), t, ts, at, yaw, colour, mw, 0.004, align, col)
    meta["legends"] = [t for _, t, *_ in texts]
    o["mrs_sign"] = meta
    return o


def make_direction_board(name, entries=(("CITY CENTRE", "ahead"), ("AIRPORT", "right"), ("HARBOUR", "left")), collection=None,
                         clearance=2.5, row_height=0.42, text_size=0.24):
    """Large green advance-direction board on two posts: one row per (destination, "ahead"|"left"|"right") entry,
    board underside at `clearance`. Faces +Y. Legends are FONT children `<name>_text<i>`."""
    if not SM: _materials()
    _fresh(name)
    col = collection or bpy.context.scene.collection
    entries = [(str(a), str(b).lower()) for a, b in entries] or [("CITY CENTRE", "ahead")]
    n = len(entries); R = row_height; ts = text_size
    W = max(2.4, max(len(a) for a, _ in entries) * ts * 0.62 + 1.4); Hb = n * R + 0.16
    z0 = clearance; zc = z0 + Hb / 2; mats = _sign_mats(); px = W / 2 - 0.35; PY = 0.075

    def build(bm):
        for x in (-px, px):
            _cyl(bm, x, 0, 0, 0.03, 0.14, 0.14, 12, S_POST); _cyl(bm, x, 0, 0.03, z0 + Hb - 0.08, 0.055, 0.05, 12, S_POST)
            _lathe(bm, [(0.055, z0 + Hb - 0.08), (0.0, z0 + Hb - 0.06)], 12, S_POST, x=x)
        for z in (z0 + 0.12, z0 + Hb - 0.14): _box(bm, -W / 2 + 0.05, -0.02, z - 0.03, W / 2 - 0.05, 0.04, z + 0.03, S_POST)
        pts = [(-W / 2, -Hb / 2), (W / 2, -Hb / 2), (W / 2, Hb / 2), (-W / 2, Hb / 2)]
        yf = _plate(bm, pts, zc, S_GREEN, post=False, y=PY); yf = _border(bm, pts, zc, 0.035, yf, S_WHITE)      # plate clear of the 55 mm posts
        for i, (dest, d) in enumerate(entries):
            zr = z0 + Hb - 0.08 - R * (i + 0.5)
            if i: _prism(bm, [(-W / 2 + 0.08, zr + R / 2 - 0.006), (W / 2 - 0.08, zr + R / 2 - 0.006), (W / 2 - 0.08, zr + R / 2 + 0.006), (-W / 2 + 0.08, zr + R / 2 + 0.006)], yf, yf + 0.0015, S_WHITE)
            L = 0.3; arrow = _arrow_pts(L, 0.075, 0.22, 0.12)
            if d.startswith("l"): _prism(bm, _xf(arrow, _vrot(-1), _vx(-1) * (W / 2 - 0.5) - _vx(-1) * L / 2, zr), yf, yf + 0.002, S_WHITE)    # viewer's left column
            elif d.startswith("r"): _prism(bm, _xf(arrow, _vrot(1), _vx(1) * (W / 2 - 0.5) - _vx(1) * L / 2, zr), yf, yf + 0.002, S_WHITE)   # viewer's right column
            else: _prism(bm, _xf(arrow, 0.0, _vx(1) * (W / 2 - 0.35), zr - L / 2), yf, yf + 0.002, S_WHITE)
    o = _mesh_obj(name, build, mats, 0.0, col)
    yf = PY + 0.002 + 0.002
    for i, (dest, d) in enumerate(entries):
        zr = z0 + Hb - 0.08 - R * (i + 0.5)
        tx = W / 2 - 0.85 if d.startswith("l") else W / 2 - 0.2      # viewer's left = world +X; text starts after a left arrow column
        _text_child(o, "%s_text%d" % (name, i), dest, ts, (tx, yf, zr), 0.0, "White", W - 1.3, 0.005, "LEFT", col)
    o["mrs_sign"] = {"kind": "direction_board", "text": "\n".join("%s|%s" % e for e in entries), "value": "", "entries": ["%s|%s" % e for e in entries],
                     "clearance": clearance, "width": W, "height": Hb, "faces": "+Y", "legends": [a for a, _ in entries]}
    return o


# ============================================================================== library / demo
def _sign_specs(prefix):
    """(name, kwargs) for one sign of every kind."""
    return [
        (prefix + "Stop", dict(kind="stop")), (prefix + "Yield", dict(kind="yield")), (prefix + "Speed50", dict(kind="speed_limit", value=50)),
        (prefix + "OneWay", dict(kind="one_way", text="right")), (prefix + "NoEntry", dict(kind="no_entry")),
        (prefix + "NoLeftTurn", dict(kind="no_left_turn")), (prefix + "NoRightTurn", dict(kind="no_right_turn")),
        (prefix + "StraightOnly", dict(kind="straight_only")), (prefix + "TurnLeftOnly", dict(kind="turn_left_only")),
        (prefix + "TurnRightOnly", dict(kind="turn_right_only")), (prefix + "BicycleRoute", dict(kind="bicycle_route")),
        (prefix + "PedestrianCrossing", dict(kind="pedestrian_crossing")), (prefix + "BusStop", dict(kind="bus_stop")),
        (prefix + "Parking", dict(kind="parking")), (prefix + "NoParking", dict(kind="no_parking")),
        (prefix + "StreetName", dict(kind="street_name", text="MAPLE AVE", pole_height=2.6)),
        (prefix + "StreetNameDouble", dict(kind="street_name", text="HARBOUR RD|KING ST", pole_height=2.6, double=True)),
        (prefix + "DirectionBoard", dict(kind="direction_board", text="CITY CENTRE|12 km\nAIRPORT|38 km", value="right")),
        (prefix + "Roundabout", dict(kind="roundabout")), (prefix + "DeadEnd", dict(kind="dead_end")), (prefix + "Children", dict(kind="children")),
        (prefix + "Roadworks", dict(kind="roadworks")), (prefix + "PriorityRoad", dict(kind="priority_road")),
        (prefix + "GiveWayAhead", dict(kind="give_way_ahead")), (prefix + "SpeedZoneEnd", dict(kind="speed_zone_end", value=50)),
    ]


def _signal_specs(prefix):
    return [
        (prefix + "Post", dict(style="post", pole_height=4.0)),
        (prefix + "MastArm", dict(style="mast_arm", pole_height=6.0, arm_length=5.5, heads=("vehicle", "vehicle"))),
        (prefix + "Pedestrian", dict(style="pedestrian", pole_height=3.6)),
        (prefix + "Bicycle", dict(style="bicycle", pole_height=3.6)),
        (prefix + "Combined", dict(style="combined", pole_height=4.2)),
    ]


def build_signage():
    """Hidden library: one sign of every kind, one signal of every style and a direction board in MRS_Signage."""
    _materials(); col = _col(LIB, clear=True, hidden=True); out = {"signs": [], "signals": [], "boards": []}
    for nm, kw in _sign_specs(MRS + "Sign_"): out["signs"].append(make_sign(nm, collection=col, **kw))
    for nm, kw in _signal_specs(MRS + "Signal_"): out["signals"].append(make_signal(nm, collection=col, **kw))
    out["boards"].append(make_direction_board(MRS + "DirectionBoard", collection=col))
    for lst in out.values():
        for o in lst:
            for ob in [o] + list(o.children_recursive): ob.hide_render = True; ob.hide_viewport = True
    return out


def demo_collection(origin=(0.0, 0.0, 0.0), sign_gap=4.0, signal_gap=4.0):
    """One of everything, visible, laid out in MRS_SignageDemo: signs (facing +Y) in one row along X at y=0,
    signals (facing -Y) in a row at y=+14 (seen from the sign row side), the direction board after the signals.
    Returns {"signs": [...], "signals": [...], "boards": [...], "positions": {name: (x, y, z)}}."""
    _materials(); col = _col(DEMO, clear=True, hidden=False); ox, oy, oz = origin
    out = {"signs": [], "signals": [], "boards": [], "positions": {}}
    for i, (nm, kw) in enumerate(_sign_specs(MRS + "Demo_Sign_")):
        o = make_sign(nm, collection=col, **kw)
        o.location = (ox + i * sign_gap, oy, oz); out["signs"].append(o); out["positions"][nm] = tuple(o.location)
    x = ox
    for nm, kw in _signal_specs(MRS + "Demo_Signal_"):
        o = make_signal(nm, collection=col, **kw)
        o.location = (x, oy + 14.0, oz); out["signals"].append(o); out["positions"][nm] = tuple(o.location)
        x += signal_gap + (kw.get("arm_length", 0.0) if kw["style"] == "mast_arm" else 0.0)
    b = make_direction_board(MRS + "Demo_DirectionBoard", collection=col); b.location = (x + 2.0, oy + 14.0, oz)
    out["boards"].append(b); out["positions"][b.name] = tuple(b.location)
    return out
