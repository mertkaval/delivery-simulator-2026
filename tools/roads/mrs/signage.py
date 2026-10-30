"""Traffic-signal and traffic-sign factories for Mert Road Studio (Blender 5.2, headless-safe).

Built on assets.py primitives and hardware.py (atlas cells, bevel / UV finishing, game materials).

Signals  - `make_signal(name, style, ...)`: pole object (origin at the base, +Z up) with every signal head as its own
           child object `<name>_head<i>`. Heads face local -Y (the traffic they control approaches from -Y).
           Every lens is its own material `MRS_Lens_<Red|Amber|Green|PedRed|PedGreen|BikeRed|BikeAmber|BikeGreen>`:
           a Value node named `State` (0 = off, 1 = lit) -> Math MULTIPLY (`StateStrength`, x LENS_PEAK) -> Principled
           `Emission Strength`, and a ColorRamp driven by the same State darkens the base colour when off.
           `set_lens_state()` / `set_signal_state()` switch states, `bake_lens_states()` writes constants for export.
           Poles (galvanised, base plate + anchor bolts, ground-contact grime, mast-arm flange joint and brace) use
           MRS_HardwareAtlas; heads use MRS_SignalHousing (same atlas images: housing, visors, black back plate with a
           yellow retroreflective border, dark ped windows) + the lens materials.
Signs    - `make_sign(name, kind, ...)`: galvanised post with cap and ground-contact base, band clamps, back rails on
           larger plates, aluminium sign blank with a rolled rim (MRS_HardwareAtlas) and the face. Authoring version
           (default): coloured face + border bands + pictogram meshes (MRS_SignFace_<Colour>, plain colours) and
           editable FONT legends `<name>_text[<i>]` facing +Y; `bake_sign_text(obj)` converts legends to meshes.
           Game version (`game=True`, used by the library): the face is ONE polygon UV-mapped into MRS_SignAtlas
           (baked from the authoring geometry + text curves by `bake_sign_atlas()`), material MRS_SignFace_Atlas; no
           pictogram meshes or text children, street-name blades read correctly from both sides.
           `make_direction_board()` builds a two-post board (authoring or game).
Library  - `build_signage(game=True)` -> hidden objects in MRS_Signage (game signs; bakes the sign atlas when the specs
           changed); `demo_collection()` -> one of everything, visible authoring versions, in MRS_SignageDemo.
"""
import json, math, os, zlib
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, geometry
from .nodes import MRS, depsgraph
from . import assets as A
from . import hardware as HW
from .assets import (pmat, M, _box, _cyl, _tube, _lathe, _prism, _band, _shape, _inset, _xf, _arrow_pts, _stroke,
                     _figure, _ngon, _finish, _uv, S_POST, S_WHITE, S_BLACK, S_RED, S_BLUE, S_YELLOW,
                     S_GREEN, S_BACK, TAU)

LIB = MRS + "Signage"
DEMO = MRS + "SignageDemo"
LENS_PEAK = 3.5           # emission strength at State = 1 (saturated but not blown out with the Standard view transform)
S_ORANGE, S_BROWN, S_GREY, S_DARKGREY = 8, 9, 10, 11
CELL0 = 200               # while building: material_index CELL0 + hardware cell id = atlas cell (below: S_* face slots)
PLATE_Y = 0.055           # front of a post-mounted sign blank (post r 0.035 at y = 0, clamps + rails in between)
SIGN_ATLAS = MRS + "SignAtlas"
SIGN_FACE_ATLAS = MRS + "SignFace_Atlas"
SIGN_BAKE_VERSION = 4

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


def C(cell): return CELL0 + HW.CID[cell]


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


def _plain(name, rgb, rough=0.38, metal=0.0, coat=0.0):
    """Plain Principled (Base Color unlinked): mrs.export passes it through unchanged."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs["Base Color"].default_value = (*rgb[:3], 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if coat: b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*rgb[:3], 1); m.roughness = rough; m.metallic = metal
    return m


def _housing_material(rgb):
    """Default (0.08 grey) -> MRS_SignalHousing (hardware atlas images); other colours -> plain MRS_SignalHousing_<hex>."""
    if tuple(round(c, 3) for c in rgb) == (0.08, 0.08, 0.08): return HW.mat(HW.HOUSING)
    name = MRS + "SignalHousing_%02x%02x%02x" % tuple(int(max(0.0, min(1.0, c)) * 255) for c in rgb)
    return bpy.data.materials.get(name) or _plain(name, tuple(rgb[:3]), 0.45, 0.1)


def face_material(colour):
    """`MRS_SignFace_<Colour>`: clean sign sheeting, plain colour (no noise). `colour` is a FACE_RGB key or an RGB tuple."""
    if isinstance(colour, str):
        key = colour[:1].upper() + colour[1:]; rgb = FACE_RGB[key]
    else:
        rgb = tuple(colour[:3]); key = "%02x%02x%02x" % tuple(int(max(0.0, min(1.0, c)) * 255) for c in rgb)
    name = MRS + "SignFace_" + key
    m = bpy.data.materials.get(name)
    if m is None or (m.node_tree and any(n.type == "TEX_NOISE" for n in m.node_tree.nodes)): m = _plain(name, rgb, 0.36, coat=0.1)
    return m


def _sm_alive():
    """The signage material registry exists and its materials are still in this file (opening another .blend frees
    them: a registry filled before the open pointed at removed materials and the street-name kit sign failed)."""
    try:
        return bool(SM) and all(m.name is not None for m in SM["face"].values()) and SM["housing"].name is not None
    except (ReferenceError, KeyError):
        return False


def _materials():
    if not A.materials_alive(): A._materials()
    atlas = HW.mat(HW.ATLAS)
    SM.clear()
    SM.update(pole=atlas, steel=atlas, back=atlas, housing=_housing_material((0.08, 0.08, 0.08)), atlas=atlas,
              lens={k: lens_material(k) for k in LENS_RGB}, face={k: face_material(k) for k in FACE_RGB})
    return SM


def _sign_mats(extra=None):
    """Material for every S_* face slot (post, white, black, red, blue, yellow, green, back, orange, brown, grey, darkgrey [, extra]).
    Slots 0 (post) and 7 (back) are hardware atlas cells (galv / alu_mill); see _translate."""
    f = SM["face"]
    mats = [None, f["White"], f["Black"], f["Red"], f["Blue"], f["Yellow"], f["Green"], None, f["Orange"], f["Brown"], f["Grey"], f["DarkGrey"]]
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


def _translate(hm, slot_mats):
    """Raw build indices -> HM indices: >= CELL0 atlas cells, S_POST / S_BACK hardware cells, other slots face materials
    (flagged nobevel so 2 mm legends and borders keep their shape)."""
    bm = hm.bm; nb = hm.nb
    for f in bm.faces:
        i = f.material_index
        if i >= CELL0: f.material_index = HW.CID[HW.CELLS[i - CELL0][0]] + 1
        elif i == S_POST: f.material_index = hm.mi("galv")
        elif i == S_BACK: f.material_index = hm.mi("alu_mill")
        else: f.material_index = hm.mi(slot_mats[i]); f[nb] = 1


def _mesh_obj(name, builder, mats, bevel=0.0, col=None, parent=None, at=(0, 0, 0), atlas=None, post=None):
    """Build with builder(bm) using S_* / CELL0 indices (or builder(hm) when post == 'hm'), finish through hardware.to_mesh."""
    hm = HW.HM()
    hm.bm.faces.layers.int.new("mrs_face")
    builder(hm.bm)
    _translate(hm, mats)
    if post: post(hm)
    me = HW.to_mesh(hm, name, bevel, atlas or HW.mat(HW.ATLAS))
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


def _hood(bm, x, y0, zc, r, length, mi, droop=0.25, mi_in=None):
    """Sun visor over a lens: closed shell arc (top 3/4 of the circle) pointing -Y from y0, tapering and drooping."""
    n = 11; outer0, outer1, inner0, inner1 = [], [], [], []
    for k in range(n):
        ang = math.pi * (-0.12 + 1.24 * k / (n - 1)); c, s = math.cos(ang), math.sin(ang)
        outer0.append(bm.verts.new((x + r * c, y0, zc + r * s))); inner0.append(bm.verts.new((x + (r - 0.004) * c, y0, zc + (r - 0.004) * s)))
        r1 = r * 0.92; z1 = zc - droop * r
        outer1.append(bm.verts.new((x + r1 * c, y0 - length, z1 + r1 * s))); inner1.append(bm.verts.new((x + (r1 - 0.004) * c, y0 - length, z1 + (r1 - 0.004) * s)))
    n0 = len(bm.faces)
    _shell(bm, outer0, outer1, inner0, inner1, mi)
    if mi_in is not None:                                        # matte black inside the visor
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]:
            c = f.calc_center_median()
            if (Vector((c.x - x, 0, c.z - zc))).length < r - 0.002: f.material_index = mi_in


def _lens_disc(bm, x, yf, zc, r, mi_lens, mi_house, depth=0.035):
    """Lens cylinder proud of the housing face yf (towards -Y) with a bezel ring."""
    _tube(bm, [(x, yf, zc), (x, yf - depth, zc)], r, 20, mi_lens)
    _tube(bm, [(x, yf + 0.001, zc), (x, yf - 0.012, zc)], r + 0.014, 20, mi_house)


# ============================================================================== hardware: posts, clamps, rails, sign blanks
def _post(bm, x, y, z_top, r=0.035, cap=True):
    """Galvanised round post (ground-contact cell up to 1 m, loops every <= 1.9 m) with a black plastic cap."""
    n = 12
    def ring(z): return [(x + r * math.cos(TAU * k / n), y + r * math.sin(TAU * k / n), z) for k in range(n)]
    zs = [0.0, min(1.0, z_top)]
    m = max(1, int(math.ceil((z_top - zs[-1]) / 1.9)))
    up = [zs[-1] + (z_top - zs[-1]) * i / m for i in range(m + 1)]
    for (za, zb), cell in (((0.0, zs[1]), "galv_contact"),):
        vs = [[bm.verts.new(p) for p in ring(z)] for z in (za, zb)]
        for k in range(n):
            f = bm.faces.new((vs[0][k], vs[0][(k + 1) % n], vs[1][(k + 1) % n], vs[1][k])); f.material_index = C(cell); f.smooth = True
    vs = [[bm.verts.new(p) for p in ring(z)] for z in up]
    for a, b in zip(vs, vs[1:]):
        for k in range(n):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k])); f.material_index = C("galv"); f.smooth = True
    if cap: _lathe(bm, [(r + 0.004, z_top), (r + 0.004, z_top + 0.012), (r * 0.7, z_top + 0.022), (0.0, z_top + 0.026)], 12, C("black_plastic"), x, y)
    else: bm.faces.new(vs[-1]).material_index = C("galv")


def _clamp(bm, x, y_post, r, z, y_to, axis="y", w=0.022):
    """Band clamp around a post with a bracket to the sign back at y_to (axis 'x': bracket along +X)."""
    _cyl(bm, x, y_post, z - 0.016, z + 0.016, r + 0.003, r + 0.003, 10, C("galv_dark"))
    if axis == "y": _box(bm, x - w, y_post + r * 0.6, z - 0.014, x + w, y_to, z + 0.014, C("galv_dark"))
    else: _box(bm, x + r * 0.6, y_post - w, z - 0.014, y_to, y_post + w, z + 0.014, C("galv_dark"))


def _blank(bm, pts, a, mi, axis="y", depth=0.018, back_mi=None, rails=None, double=False):
    """Sign blank: 3 mm sheet whose front (at axis coordinate a) is the face, mill-aluminium back and edges, and a
    rolled rim lip `depth` deep. pts in (x, z) for axis 'y' (faces +Y) or (y, z) for axis 'x' (faces +X).
    double=True: the back is a face too (double-sided blade, sheet centred on a). Returns the face coordinate."""
    lay = bm.faces.layers.int.get("mrs_face"); nbl = bm.faces.layers.int.get("nobevel")
    t = 0.003; n_start = len(bm.faces)
    if len(pts) >= 32:                                           # discs: 24-gon blank (the face texture carries the round edge)
        cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
        rr = [math.hypot(p[0] - cx, p[1] - cz) for p in pts]
        if max(rr) - min(rr) < 1e-4:
            a0_ = math.atan2(pts[0][1] - cz, pts[0][0] - cx); pts = [(cx + rr[0] * math.cos(a0_ + TAU * k / 24), cz + rr[0] * math.sin(a0_ + TAU * k / 24)) for k in range(24)]
    if double: a0, a1 = a - t, a + t
    else: a0, a1 = a - t, a
    n0 = len(bm.faces); _prism(bm, pts, a0, a1, C("alu_mill"), axis); bm.faces.ensure_lookup_table()
    back, front = bm.faces[n0], bm.faces[n0 + 1]
    front.material_index = mi
    if lay is not None: front[lay] = 1
    if double:
        back.material_index = back_mi if back_mi is not None else mi
        if lay is not None: back[lay] = 2
    if not double:
        _lip(bm, pts, _inset(pts, 0.0025), a - depth, a - 0.001, C("alu_mill"), axis)
        for z_ in (rails or []):
            xs = _chord(pts, z_)
            if axis == "y" and xs and xs[1] - xs[0] > 0.12: _box(bm, xs[0] + 0.045, a - depth, z_ - 0.025, xs[1] - 0.045, a - t, z_ + 0.025, C("galv_dark"))
    if nbl is not None:
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n_start:]: f[nbl] = 1                     # 3 mm sheet and 2.5 mm lip: no chamfer
    return a1


def _border(bm, pts, zc, width, yf, mi):
    """Border band on the face, starting 0.2 mm in front of it (no vertex shared with the sheet, so the merge pass
    cannot weld and flip the face)."""
    _band(bm, [(x, z + zc) for x, z in pts], [(x, z + zc) for x, z in _inset(pts, width)], yf + 0.0002, yf + 0.002, mi)
    return yf + 0.002


def _lip(bm, outer, inner, a0, a1, mi, axis="y"):
    """Rolled-rim lip behind the sheet: outer and inner walls plus the back edge (the front ring is hidden by the sheet)."""
    def P(p, a): return (p[0], a, p[1]) if axis == "y" else (a, p[0], p[1])
    n = len(outer)
    o0 = [bm.verts.new(P(p, a0)) for p in outer]; o1 = [bm.verts.new(P(p, a1)) for p in outer]
    i0 = [bm.verts.new(P(p, a0)) for p in inner]; i1 = [bm.verts.new(P(p, a1)) for p in inner]
    for k in range(n):
        j = (k + 1) % n
        for q in ((o0[j], o0[k], i0[k], i0[j]), (o0[k], o0[j], o1[j], o1[k]), (i0[j], i0[k], i1[k], i1[j])): bm.faces.new(q).material_index = mi


def _chord(pts, z):
    """x range of a closed (x, z) outline at height z (None when the line misses it)."""
    xs = []
    for (x0, z0), (x1, z1) in zip(pts, pts[1:] + pts[:1]):
        if (z0 - z) * (z1 - z) <= 0 and abs(z1 - z0) > 1e-9: xs.append(x0 + (x1 - x0) * (z - z0) / (z1 - z0))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


_FACES = []          # face regions registered by the current build: {"axis", "plane", "dir", "outline" [(x|y, z)]}


def _face(axis, plane, pts, back=False):
    _FACES.append({"axis": axis, "plane": plane, "outline": [tuple(p) for p in pts], "back": back})


def _plate(bm, pts, zc, mi, post=True, y=PLATE_Y, x_post=0.0, rails=None):
    """Post + band clamps (+ back rails on large plates) + sign blank centred at height zc facing +Y. Returns the
    front y of the face."""
    P = [(x, z + zc) for x, z in pts]
    zs = [p[1] for p in P]; xs = [p[0] for p in P]
    top, bot = max(zs), min(zs); h = top - bot; w = max(xs) - min(xs)
    if post:                                                     # post ends where the plate is still >= 14 cm wide behind it
        pt = top - 0.03
        for k in range(1, 200):
            c = _chord(P, top - 0.005 * k)
            if c and c[0] <= x_post - 0.07 and c[1] >= x_post + 0.07: pt = top - 0.005 * k - 0.025; break
        _post(bm, x_post, 0.0, pt)
    cz = [zc] if h < 0.5 else [bot + h * 0.24, top - h * 0.24]
    if rails is None: rails = cz if w > 0.62 else []
    for z in cz: _clamp(bm, x_post, 0.0, 0.035, z, y - 0.003)
    yf = _blank(bm, P, y, mi, rails=rails)
    _face("y", yf, P)
    return yf


# ============================================================================== signal heads (origin = top centre of the housing, face -Y)
# raw indices while building a head: 0 housing, 1 dark window, 2 retroreflective border, 3 black back plate / visor inside, 4.. lenses
ARROW_LANES = (1, 4)      # lane uses that get arrow lenses: a lane that may only turn left (1) / right (4)


def _arrow_lens(bm, yf, zc, r, code, mi, depth=0.035):
    """A turn arrow in lens material on a dark lens face (front at yf - depth): pointing -X for a left turn (code 1),
    +X for a right turn (4)."""
    head = [(0.05 * r, -0.55 * r), (0.8 * r, 0.0), (0.05 * r, 0.55 * r)]
    shaft = [(-0.75 * r, -0.17 * r), (0.1 * r, -0.17 * r), (0.1 * r, 0.17 * r), (-0.75 * r, 0.17 * r)]
    for poly in (head, shaft):
        pts = [(x, zc + z) for x, z in poly] if code == 4 else [(-x, zc + z) for x, z in poly[::-1]]
        _prism(bm, pts, yf - depth - 0.004, yf - depth + 0.002, mi)


def _head_vehicle(bm, lens_size, mi_house, mi_glass, mi_reflect, mi_lenses, arrow=0):
    D = lens_size; pitch = 1.5 * D; w = 1.6 * D; d = 1.25 * D; n = len(mi_lenses); h = n * pitch + 0.03
    _box(bm, -w / 2, -d / 2, -h, w / 2, d / 2, 0.0, mi_house)                                   # housing
    for z in (-h * 0.25, -h * 0.75): _box(bm, w / 2, -0.02, z - 0.03, w / 2 + 0.008, 0.02, z + 0.03, mi_house)   # door hinges
    _box(bm, -0.025, -d / 2 + 0.02, -h - 0.012, 0.025, d / 2 - 0.02, -h, mi_house)               # drain boss
    yf = -d / 2
    bw, bh = w / 2 + 0.6 * D, 0.5 * D                                                           # backplate + reflective border
    plate = [(-bw, -h - bh), (bw, -h - bh), (bw, bh), (-bw, bh)]
    _prism(bm, plate, yf + 0.004, yf + 0.008, CELL0 + HW.CID["black_plastic"])
    _band(bm, plate, _inset(plate, 0.025), yf + 0.0, yf + 0.004, mi_reflect)
    for i, mi in enumerate(mi_lenses):
        zc = -0.015 - pitch * (i + 0.5)
        if arrow in ARROW_LANES:                                                                # dark lens, lit arrow
            _lens_disc(bm, 0.0, yf, zc, D / 2, mi_glass, mi_house); _arrow_lens(bm, yf, zc, D / 2, arrow, mi)
        else:
            _lens_disc(bm, 0.0, yf, zc, D / 2, mi, mi_house)
        _hood(bm, 0.0, yf - 0.002, zc, D / 2 + 0.03, 0.95 * D, mi_house, mi_in=CELL0 + HW.CID["black_plastic"])
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
        for s in (-1, 1): _box(bm, s * w / 2 - (0.004 if s > 0 else 0.0), yf - 0.1, zb + W * 0.35, s * w / 2 + (0.0 if s > 0 else 0.004), yf + 0.002, zt + 0.02, mi_house)
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
        _hood(bm, 0.0, yf - 0.002, zc, D / 2 + 0.025, 0.8 * D, mi_house, mi_in=CELL0 + HW.CID["black_plastic"])
    _cyl(bm, 0, 0, 0.0, 0.07, 0.025, 0.025, 10, mi_house); _cyl(bm, 0, 0, -h - 0.05, -h, 0.025, 0.025, 10, mi_house)
    return h


HEAD_BUILDERS = {"vehicle": _head_vehicle, "pedestrian": _head_pedestrian, "bicycle": _head_bicycle}
HEAD_HEIGHT = {"vehicle": lambda D: 3 * 1.5 * D + 0.03, "pedestrian": lambda D: 2 * (1.3 * D + 0.05) + 0.03, "bicycle": lambda D: 3 * 1.45 * 0.75 * D + 0.03}
HEAD_DEPTH = {"vehicle": lambda D: 1.25 * D, "pedestrian": lambda D: 0.9 * D, "bicycle": lambda D: 1.1 * 0.75 * D}


def _make_head(name, kind, lens_size, mats_house, col, parent, at, arrow=0):
    lenses = HEAD_LENSES[kind]; arrow = arrow if kind == "vehicle" and arrow in ARROW_LANES else 0
    hinfo = {}
    house = mats_house["housing"]; custom = house.name != HW.HOUSING
    lens_mats = [SM["lens"][k] for k in lenses]

    def build(bm):
        hinfo["h"] = HEAD_BUILDERS[kind](bm, lens_size, CELL0 + HW.CID["housing"], CELL0 + HW.CID["glass_dark"], CELL0 + HW.CID["yellow_refl"],
                                         list(range(4, 4 + len(lenses))), **({"arrow": arrow} if arrow else {}))
    slot = [None] * 4 + lens_mats
    o = _mesh_obj(name, build, slot, 0.004, col, parent, at, atlas=house)
    o["mrs_signal_head"] = {"kind": kind, "lenses": lenses, "lens_materials": [MRS + "Lens_" + k for k in lenses], "faces": "-Y", "arrow": arrow}
    return o, hinfo["h"]


# ============================================================================== signals
def make_signal(name, style="post", pole_height=4.0, arm_length=0.0, heads=("vehicle",), setback=0.0, lens_size=0.2,
                housing_color=(0.08, 0.08, 0.08), collection=None, arm_side=1.0, head_x=None, head_arrows=None):
    """Signal pole `name` (origin at the base, +Z up, heads facing -Y) with child head objects `<name>_head<i>`.
    style: post | mast_arm (arm along +X, or -X with arm_side = -1; `arm_length`) | pedestrian | bicycle | combined
    (vehicle + pedestrian head). `head_x`: distances along the arm of the hanging vehicle heads (one per lane: over
    the lane centres); default every 2.4 m back from the tip. `head_arrows`: each hanging vehicle head's lane use
    (junction.lane_use); a left-only (1) / right-only (4) lane's head shows arrow lenses. `setback` shifts the pole +Y
    behind the origin (kerb reference point). Returns the pole object."""
    if style not in SIGNAL_STYLES: raise ValueError("style %r not in %s" % (style, SIGNAL_STYLES))
    if not _sm_alive(): _materials()
    heads = tuple(heads)
    if heads == ("vehicle",):   # default per style
        heads = {"pedestrian": ("pedestrian",), "bicycle": ("bicycle",), "combined": ("vehicle", "pedestrian")}.get(style, heads)
    if style == "mast_arm" and arm_length <= 0: arm_length = 5.0
    xs = -1.0 if arm_side < 0 else 1.0          # the arm's side (geometry is built mirrored, not scaled: normals stay right)
    _fresh(name)
    col = collection or bpy.context.scene.collection
    house = _housing_material(housing_color); mats_house = {"housing": house}
    H = pole_height; D = lens_size; sy = setback
    r0, r1 = {"post": (0.075, 0.055), "combined": (0.075, 0.055), "mast_arm": (0.16, 0.11), "pedestrian": (0.06, 0.05), "bicycle": (0.06, 0.05)}[style]
    mounts = []   # (kind, (x, y, z) head origin, bracket geometry callback)
    arrows = {}   # mount index -> lane use of an arrow head

    # ---- plan the heads
    if style == "mast_arm":
        L = arm_length; z_root = H - 0.35; z_tip = H - 0.12
        def z_arm(x): return z_root + (z_tip - z_root) * x / L
        k = 0
        for kind in heads:
            if kind == "pedestrian":
                mounts.append((kind, (0.0, sy - r1 - HEAD_DEPTH[kind](D) / 2 - 0.05, min(H - 0.3, 2.9)), "side")); continue
            if head_x is not None and k < len(head_x): x = min(max(float(head_x[k]), 1.2), L - 0.3)
            else:
                x = L - 0.7 - 2.4 * k
                if x < 1.2: x = 1.2 + 0.4 * k
            if head_arrows is not None and k < len(head_arrows) and int(head_arrows[k]) in ARROW_LANES: arrows[len(mounts)] = int(head_arrows[k])
            k += 1
            mounts.append((kind, (x * xs, sy, z_arm(x) - 0.085 - 0.22), "hang"))
    else:
        ztop = H - 0.06
        for kind in heads:
            if kind == "pedestrian" and style in ("combined",): ztop = min(ztop, 2.75)
            if kind == "pedestrian" and style == "pedestrian": ztop = min(ztop, 2.9)
            if kind == "bicycle" and style == "bicycle": ztop = min(ztop, 2.7)
            mounts.append((kind, (0.0, sy - r1 - HEAD_DEPTH[kind](D) / 2 - 0.05, ztop), "side"))
            ztop = ztop - HEAD_HEIGHT[kind](D) - 0.3

    # ---- pole mesh: base plate + bolts, ground-contact base section, galvanised tapered shaft, cap; mast arm with flange joint
    def pole(hm):
        R = r0 * 3.0
        hm.cyl(0, sy, 0, 0.03, R, R, "galv_contact", 16)
        HW.anchor_bolts(hm, R * 0.74, 4, 0.03, 0.011 if R > 0.3 else 0.009, c="galv", y=sy)
        hm.lathe([(r0 * 1.5, 0.03), (r0 * 1.45, 0.06), (r0 * 1.3, 0.5), (r0 * 1.12, 0.56), (r0 * 1.05, 0.6)], "galv_contact", 16, y=sy)
        rr = lambda z: r0 + (r1 - r0) * (z - 0.6) / (H - 0.6)
        zs = [0.6, 1.0] + [1.0 + (H - 1.0) * i / max(1, int(math.ceil((H - 1.0) / 1.9))) for i in range(1, max(1, int(math.ceil((H - 1.0) / 1.9))) + 1)]
        n = 16
        rings = [[(rr(z) * math.cos(TAU * k / n), sy + rr(z) * math.sin(TAU * k / n), z) for k in range(n)] for z in zs]
        hm.loft(rings[:2], "galv_contact", caps=False); hm.loft(rings[1:], "galv", caps=False)
        hm.lathe([(r1 + 0.01, H), (r1 + 0.01, H + 0.02), (r1 * 0.6, H + 0.035), (0.0, H + 0.04)], "galv", 16, y=sy)
        if style == "mast_arm":
            hm.cyl(0, sy, H - 0.75, H - 0.1, r1 + 0.03, r1 + 0.03, "galv", 16)                                  # collar
            fx0, fx1 = sorted((0.0, (r1 + 0.05) * xs))
            hm.box(fx0, sy - 0.16, z_root - 0.17, fx1, sy + 0.16, z_root + 0.17, "galv")                             # flange plate
            for dy in (-0.11, 0.11):
                for dz in (-0.12, 0.12): hm.tube([((r1 + 0.05) * xs, sy + dy, z_root + dz), ((r1 + 0.068) * xs, sy + dy, z_root + dz)], 0.012, "galv_dark", 6)
            hm.taper(((r1 + 0.05) * xs, sy, z_root), (L * xs, sy, z_tip), 0.085, 0.05, "galv", 14, segs=max(1, int(math.ceil(L / 1.9))))   # arm
            hm.taper((0.0, sy, H - 1.4), (min(1.6, L * 0.35) * xs, sy, z_arm(min(1.6, L * 0.35)) - 0.06), 0.03, 0.03, "galv", 10)   # brace
            bx0, bx1 = sorted((-0.06 * xs, 0.3 * xs))
            hm.box(bx0, sy - 0.14, H - 1.5, bx1, sy + 0.14, H - 1.3, "galv")
        for kind, (x, y, z), how in mounts:
            if how == "hang":
                hm.cyl(x, y, z, z_arm(abs(x)), 0.03, 0.03, "galv", 10)
                ra = 0.085 + (0.05 - 0.085) * abs(x) / L + 0.012
                hm.taper((x - 0.05, y, z_arm(abs(x))), (x + 0.05, y, z_arm(abs(x))), ra, ra, "galv_dark", 14)        # hanger clamp around the arm
            else:
                hh = HEAD_HEIGHT[kind](D)
                for zz in (z - 0.08, z - hh + 0.08):
                    hm.tube([(0, sy, zz), (0, y + 0.02, zz)], 0.025, "galv", 8)
                    hm.cyl(0, sy, zz - 0.04, zz + 0.04, r1 + 0.012, r1 + 0.012, "galv_dark", 14)
        if any(k == "pedestrian" for k, _, _ in mounts):                                          # push-button unit
            hm.box(-0.06, sy - r1 - 0.09, 1.0, 0.06, sy, 1.2, "paint_yellow")
            hm.box(-0.035, sy - r1 - 0.092, 1.13, 0.035, sy - r1 - 0.09, 1.185, "black_plastic", nobevel=True)
            hm.tube([(0, sy - r1 - 0.09, 1.08), (0, sy - r1 - 0.105, 1.08)], 0.026, "stainless", 14)
    hm = HW.HM(); pole(hm)
    me = HW.to_mesh(hm, name, 0.006)
    pole_o = bpy.data.objects.new(name, me); col.objects.link(pole_o)

    # ---- heads (children)
    head_info = []
    for i, (kind, at, how) in enumerate(mounts):
        hname = "%s_head%d" % (name, i)
        ho, hh = _make_head(hname, kind, D, mats_house, col, pole_o, at, arrows.get(i, 0))
        head_info.append({"kind": kind, "lenses": HEAD_LENSES[kind], "mesh_names": [ho.data.name], "object": ho.name,
                          "lens_materials": [MRS + "Lens_" + k for k in HEAD_LENSES[kind]], "mount": how, "arrow": arrows.get(i, 0)})
    pole_o["mrs_signal"] = {"style": style, "pole_height": H, "arm_length": arm_length if style == "mast_arm" else 0.0, "arm_side": xs, "setback": sy,
                            "lens_size": D, "faces": "-Y", "housing": house.name, "heads": head_info}
    return pole_o


# ============================================================================== lane-use signs (mast arms)
LANE_SIGN = (0.6, 0.75, 0.025)        # plate width, height, border (m)


def _arrow_polys(code):
    """Arrow outlines (x right, y up, ~4 units tall) for a movement code: 1 left + 2 straight + 4 right; the same
    shapes as the lane arrows painted on the road (assets.py _markings)."""
    polys = [[(-0.1, 0.0), (0.1, 0.0), (0.1, 3.0 if code & 2 else 1.4), (-0.1, 3.0 if code & 2 else 1.4)]]
    if code & 2: polys.append([(-0.45, 3.0), (0.45, 3.0), (0.0, 4.0)])
    for bit, sgn in ((1, -1.0), (4, 1.0)):
        if not code & bit: continue
        bar = [(0.0, 1.2), (sgn * 0.9, 1.2), (sgn * 0.9, 1.4), (0.0, 1.4)]
        tri = [(sgn * 0.9, 0.9), (sgn * 1.5, 1.3), (sgn * 0.9, 1.7)]
        polys += [bar if sgn > 0 else bar[::-1], tri if sgn > 0 else tri[::-1]]
    return polys


def lane_use_sign(name, code, collection=None, parent=None, at=(0.0, 0.0, 0.0)):
    """A lane-use sign (white plate, black border and arrows for movement `code`) facing -Y like the signal heads,
    centred at `at` (in the parent's space). The mesh is shared per code (MRS_LaneUse_<code>)."""
    if not _sm_alive(): _materials()
    mn = MRS + "LaneUse_%d" % code
    me = bpy.data.meshes.get(mn)
    if me is None:
        bm = bmesh.new(); W, H, B = LANE_SIGN
        def quad(x0, z0, x1, z1, y, mi):
            f = bm.faces.new([bm.verts.new(v) for v in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]); f.material_index = mi
        quad(-W / 2, -H / 2, W / 2, H / 2, -0.012, 1)                                          # white face
        for x0, z0, x1, z1 in ((-W / 2, -H / 2, W / 2, -H / 2 + B), (-W / 2, H / 2 - B, W / 2, H / 2), (-W / 2, -H / 2, -W / 2 + B, H / 2), (W / 2 - B, -H / 2, W / 2, H / 2)):
            quad(x0, z0, x1, z1, -0.014, 0)                                                    # black border
        f = bm.faces.new([bm.verts.new(v) for v in ((W / 2, 0.0, -H / 2), (-W / 2, 0.0, -H / 2), (-W / 2, 0.0, H / 2), (W / 2, 0.0, H / 2))]); f.material_index = 2   # back
        k = (H - 3 * B) / 4.0                                                                  # arrows fill the plate inside the border
        for poly in _arrow_polys(code):
            try: f = bm.faces.new([bm.verts.new((x * k, -0.015, (y - 2.0) * k)) for x, y in poly]); f.material_index = 0
            except ValueError: pass
        bmesh.ops.recalc_face_normals(bm, faces=[f_ for f_ in bm.faces if f_.material_index != 2])
        for f_ in bm.faces:                                                                    # fronts face -Y, the back +Y
            want = Vector((0.0, 1.0 if f_.material_index == 2 else -1.0, 0.0))
            if f_.normal.dot(want) < 0: f_.normal_flip()
        me = bpy.data.meshes.new(mn); bm.to_mesh(me); bm.free()
        for m in (SM["face"]["Black"], SM["face"]["White"], SM["face"]["Grey"]): me.materials.append(m)
    o = bpy.data.objects.new(name, me); (collection or bpy.context.scene.collection).objects.link(o)
    if parent is not None: o.parent = parent
    o.location = at; o["mrs_lane_use"] = int(code)
    return o


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


def _rrect(w, h, r, n=4):
    """Rounded rectangle (x, z) centred at the origin."""
    pts = []
    for cx, cz, a in ((w / 2 - r, -h / 2 + r, -math.pi / 2), (w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, math.pi / 2), (-w / 2 + r, -h / 2 + r, math.pi)):
        pts += [(cx + r * math.cos(a + math.pi / 2 * k / n), cz + r * math.sin(a + math.pi / 2 * k / n)) for k in range(n + 1)]
    return pts


# ============================================================================== signs
SIGN_SIZE = {"stop": 0.8, "yield": 0.9, "speed_limit": 0.75, "one_way": 1.0, "no_entry": 0.75, "no_left_turn": 0.75, "no_right_turn": 0.75,
             "straight_only": 0.75, "turn_left_only": 0.75, "turn_right_only": 0.75, "bicycle_route": 0.75, "pedestrian_crossing": 0.65,
             "bus_stop": 0.7, "parking": 0.65, "no_parking": 0.75, "street_name": 0.9, "direction_board": 1.6, "roundabout": 0.75,
             "dead_end": 0.65, "children": 0.9, "roadworks": 0.9, "priority_road": 0.75, "give_way_ahead": 0.9, "speed_zone_end": 0.75}


def _game_faces(hm, name, sign_mat):
    """Game version: keep the tagged face polygons (sheet fronts / blade backs) with the sign-atlas material and drop
    every other face-material polygon (borders, pictograms)."""
    bm = hm.bm; lay = bm.faces.layers.int.get("mrs_face"); atlas_mi = hm.mi(sign_mat)
    drop = []
    for f in bm.faces:
        if f.material_index > HW.EXTRA0 and f.material_index != atlas_mi:
            m = hm.extra[f.material_index - HW.EXTRA0 - 1]
            if m.name.startswith(MRS + "SignFace_"):
                if f[lay] in (1, 2): f.material_index = atlas_mi; f[hm.nb] = 1
                else: drop.append(f)
    if drop: bmesh.ops.delete(bm, geom=drop, context="FACES")
    keep = [m for m in hm.extra if not m.name.startswith(MRS + "SignFace_") or m is sign_mat]
    remap = {HW.EXTRA0 + 1 + i: HW.EXTRA0 + 1 + keep.index(m) for i, m in enumerate(hm.extra) if m in keep}
    for f in bm.faces:
        if f.material_index > HW.EXTRA0: f.material_index = remap[f.material_index]
    hm.extra = keep


def _game_uv(o, cells):
    """UV the sign-atlas faces of `o` into its cell(s): u along the viewer's right, v up; back faces mirrored so a
    double-sided blade reads correctly from both sides."""
    me = o.data; slot = next((i for i, m in enumerate(me.materials) if m and m.name == SIGN_FACE_ATLAS), None)
    if slot is None: return 0
    bm = bmesh.new(); bm.from_mesh(me); uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap"); bm.normal_update()
    n = 0
    for f in bm.faces:
        if f.material_index != slot: continue
        nrm = f.normal; ax = "y" if abs(nrm.y) >= abs(nrm.x) else "x"; back = (nrm.y if ax == "y" else nrm.x) < 0
        c = f.calc_center_median()
        cell = min((cl for cl in cells if cl["axis"] == ax), key=lambda cl: abs((c.y if ax == "y" else c.x) - cl["plane"]) + (0 if (cl["v0"] - 0.01 <= c.z <= cl["v1"] + 0.01) else 10.0))
        for l in f.loops:
            p = l.vert.co
            a = (-p.x if ax == "y" else p.y)
            if back: a = cell["u0"] + cell["u1"] - a
            l[uv].uv = ((cell["px"][0] + cell["pad"] + (a - cell["u0"]) * cell["ppm"]) / cell["size"][0],
                        1.0 - (cell["px"][1] + cell["pad"] + (cell["v1"] - p.z) * cell["ppm"]) / cell["size"][1])
        n += 1
    bm.to_mesh(me); bm.free()
    return n


def make_sign(name, kind, text=None, value=None, pole_height=2.3, size=None, collection=None, double=False, face_color=None, game=False):
    """Sign post `name` of `kind` (see SIGN_KINDS): plate centred at `pole_height`, facing +Y, origin at the base.
    text: legend / street name / "left"|"right" for one_way / "DEST|12 km" lines for direction_board. value: number for
    speed_limit / speed_zone_end, arrow direction for direction_board. double: street_name with a second blade at 90 deg.
    face_color: optional RGB override of the plate colour. Legends are FONT children `<name>_text[<i>]`.
    game=True: the baked game version (face from MRS_SignAtlas; needs a cell for `name`, see bake_sign_atlas); falls
    back to the authoring version when the atlas has no cell for this sign."""
    if kind not in SIGN_KINDS: raise ValueError("kind %r not in %s" % (kind, SIGN_KINDS))
    if not _sm_alive(): _materials()
    cells = None
    if game:
        cells = sign_atlas_cells().get(name)
        if not cells: print("[signage] %s: no MRS_SignAtlas cell, building the authoring version" % name); game = False
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
            _post(bm, 0.0, 0.0, top - 0.02, cap=True)
            for i, nm in enumerate(names[:2 if double else 1]):
                w = max(0.84 * s, 0.072 * s * len(nm) + 0.3 * s); r = _rrect(w, 0.22 * s, 0.025 * s)
                zc = Z + (0.11 * s if i == 0 else -0.14 * s) if double else Z
                ax = "y" if i == 0 else "x"
                P = [(x, z + zc) for x, z in r]
                _clamp(bm, 0.0, 0.0, 0.035, zc, 0.037, axis=ax)
                yf = _blank(bm, P, 0.04, face(S_GREEN), ax, double=True)
                _face(ax, yf, P); _face(ax, 0.034, P, back=True)
                r1_ = _rrect(w - 0.026 * s, 0.22 * s - 0.026 * s, 0.012 * s); r2_ = _rrect(w - 0.036 * s, 0.22 * s - 0.036 * s, 0.008 * s)
                if i == 0:
                    _prism(bm, [(x, z + zc) for x, z in r1_], yf, yf + 0.001, S_WHITE)
                    _prism(bm, [(x, z + zc) for x, z in r2_], yf + 0.001, yf + 0.002, face(S_GREEN))
                    texts.append(("" if i == 0 else "1", nm, 0.11 * s, (0, yf + 0.002, zc), 0.0, "White", w - 0.12 * s, "CENTER"))
                else:
                    _prism(bm, [(y, z + zc) for y, z in r1_], yf, yf + 0.001, S_WHITE, "x")
                    _prism(bm, [(y, z + zc) for y, z in r2_], yf + 0.001, yf + 0.002, face(S_GREEN), "x")
                    texts.append(("1", nm, 0.11 * s, (yf + 0.002, 0, zc), -math.pi / 2, "White", w - 0.12 * s, "CENTER"))
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
    _FACES.clear()
    sign_mat = sign_atlas_material() if game else None
    o = _mesh_obj(name, build, mats, 0.0, col, post=(lambda hm: _game_faces(hm, name, sign_mat)) if game else None)
    faces = [dict(f) for f in _FACES]; _FACES.clear()
    meta["legends"] = [t for _, t, *_ in texts]
    if game:
        _game_uv(o, cells)
        meta["baked_legends"] = meta["legends"]; meta["legends"] = []; meta["game"] = True; meta["atlas"] = SIGN_ATLAS
    else:
        for suffix, t, ts, at, yaw, colour, mw, align in texts:
            _text_child(o, "%s_text%s" % (name, suffix), t, ts, at, yaw, colour, mw, 0.004, align, col)
    o["mrs_sign"] = meta
    _LAST_FACES[name] = faces
    return o


_LAST_FACES = {}


def make_direction_board(name, entries=(("CITY CENTRE", "ahead"), ("AIRPORT", "right"), ("HARBOUR", "left")), collection=None,
                         clearance=2.5, row_height=0.42, text_size=0.24, game=False):
    """Large green advance-direction board on two posts: one row per (destination, "ahead"|"left"|"right") entry,
    board underside at `clearance`. Faces +Y. Legends are FONT children `<name>_text<i>` (game=True: baked face)."""
    if not _sm_alive(): _materials()
    cells = None
    if game:
        cells = sign_atlas_cells().get(name)
        if not cells: print("[signage] %s: no MRS_SignAtlas cell, building the authoring version" % name); game = False
    _fresh(name)
    col = collection or bpy.context.scene.collection
    entries = [(str(a), str(b).lower()) for a, b in entries] or [("CITY CENTRE", "ahead")]
    n = len(entries); R = row_height; ts = text_size
    W = max(2.4, max(len(a) for a, _ in entries) * ts * 0.62 + 1.4); Hb = n * R + 0.16
    z0 = clearance; zc = z0 + Hb / 2; mats = _sign_mats(); px = W / 2 - 0.35; PY = 0.075

    def build(bm):
        for x in (-px, px):
            _cyl(bm, x, 0, 0, 0.03, 0.14, 0.14, 16, C("galv_contact"))
            for k in range(4):
                a = math.pi / 4 + TAU * k / 4; bx, by = x + 0.1 * math.cos(a), 0.1 * math.sin(a)
                _cyl(bm, bx, by, 0.03, 0.034, 0.02, 0.02, 10, C("galv")); _cyl(bm, bx, by, 0.034, 0.046, 0.016, 0.016, 6, C("galv"), smooth=False)
            n_ = 12
            def ring(z, r=0.055): return [(x + r * math.cos(TAU * k / n_), r * math.sin(TAU * k / n_), z) for k in range(n_)]
            zs = [0.03, 1.0] + [1.0 + (z0 + Hb - 0.08 - 1.0) * i / 2 for i in (1, 2)]
            vs = [[bm.verts.new(p) for p in ring(z)] for z in zs]
            for j, (a_, b_) in enumerate(zip(vs, vs[1:])):
                for k in range(n_):
                    f = bm.faces.new((a_[k], a_[(k + 1) % n_], b_[(k + 1) % n_], b_[k])); f.material_index = C("galv_contact" if j == 0 else "galv"); f.smooth = True
            _lathe(bm, [(0.06, z0 + Hb - 0.08), (0.06, z0 + Hb - 0.065), (0.03, z0 + Hb - 0.052), (0.0, z0 + Hb - 0.05)], 12, C("black_plastic"), x=x)
            for z in (z0 + 0.14, z0 + Hb - 0.16):                                                              # U-bolt clamps
                _cyl(bm, x, 0, z - 0.02, z + 0.02, 0.059, 0.059, 12, C("galv_dark"))
                _box(bm, x - 0.04, 0.05, z - 0.018, x + 0.04, PY - 0.003, z + 0.018, C("galv_dark"))
        pts = [(-W / 2, -Hb / 2), (W / 2, -Hb / 2), (W / 2, Hb / 2), (-W / 2, Hb / 2)]
        P = [(x, z + zc) for x, z in pts]
        yf = _blank(bm, P, PY, S_GREEN, rails=[z0 + 0.14, z0 + Hb - 0.16]); _face("y", yf, P)
        yf = _border(bm, pts, zc, 0.035, yf, S_WHITE)
        for i, (dest, d) in enumerate(entries):
            zr = z0 + Hb - 0.08 - R * (i + 0.5)
            if i: _prism(bm, [(-W / 2 + 0.08, zr + R / 2 - 0.006), (W / 2 - 0.08, zr + R / 2 - 0.006), (W / 2 - 0.08, zr + R / 2 + 0.006), (-W / 2 + 0.08, zr + R / 2 + 0.006)], yf, yf + 0.0015, S_WHITE)
            L = 0.3; arrow = _arrow_pts(L, 0.075, 0.22, 0.12)
            if d.startswith("l"): _prism(bm, _xf(arrow, _vrot(-1), _vx(-1) * (W / 2 - 0.5) - _vx(-1) * L / 2, zr), yf, yf + 0.002, S_WHITE)    # viewer's left column
            elif d.startswith("r"): _prism(bm, _xf(arrow, _vrot(1), _vx(1) * (W / 2 - 0.5) - _vx(1) * L / 2, zr), yf, yf + 0.002, S_WHITE)   # viewer's right column
            else: _prism(bm, _xf(arrow, 0.0, _vx(1) * (W / 2 - 0.35), zr - L / 2), yf, yf + 0.002, S_WHITE)
    _FACES.clear()
    sign_mat = sign_atlas_material() if game else None
    o = _mesh_obj(name, build, mats, 0.004, col, post=(lambda hm: _game_faces(hm, name, sign_mat)) if game else None)
    faces = [dict(f) for f in _FACES]; _FACES.clear(); _LAST_FACES[name] = faces
    yf = PY + 0.002 + 0.002
    meta = {"kind": "direction_board", "text": "\n".join("%s|%s" % e for e in entries), "value": "", "entries": ["%s|%s" % e for e in entries],
            "clearance": clearance, "width": W, "height": Hb, "faces": "+Y", "legends": [a for a, _ in entries]}
    if game:
        _game_uv(o, cells); meta["baked_legends"] = meta["legends"]; meta["legends"] = []; meta["game"] = True; meta["atlas"] = SIGN_ATLAS
    else:
        for i, (dest, d) in enumerate(entries):
            zr = z0 + Hb - 0.08 - R * (i + 0.5)
            tx = W / 2 - 0.85 if d.startswith("l") else W / 2 - 0.2      # viewer's left = world +X; text starts after a left arrow column
            _text_child(o, "%s_text%d" % (name, i), dest, ts, (tx, yf, zr), 0.0, "White", W - 1.3, 0.005, "LEFT", col)
    o["mrs_sign"] = meta
    return o


# ============================================================================== sign atlas (baked game faces)
SA_W = SA_H = 2048
SA_PAD = 6


def _sa_paths(tex_dir=None):
    d = tex_dir or HW.TEX_DIR
    return {k: os.path.join(d, "%s_%s.png" % (SIGN_ATLAS, k)) for k in ("albedo",)}, os.path.join(d, "sign_atlas.json")


_SA_CACHE = {}


def sign_atlas_cells(tex_dir=None):
    """{object name: [cell dicts]} of the current MRS_SignAtlas (empty when not baked)."""
    paths, js = _sa_paths(tex_dir)
    try: mt = os.path.getmtime(js)
    except OSError: return {}
    if _SA_CACHE.get("mtime") != mt:
        with open(js, encoding="utf-8") as f: _SA_CACHE["data"] = json.load(f)
        _SA_CACHE["mtime"] = mt
    return _SA_CACHE["data"].get("signs", {})


def sign_atlas_material(tex_dir=None):
    """MRS_SignFace_Atlas: Principled BSDF with the MRS_SignAtlas albedo only (printed sheeting is flat: constant
    roughness 0.38, no metal, no normal map -> one texture fetch in the engine)."""
    paths, _ = _sa_paths(tex_dir)
    m = bpy.data.materials.get(SIGN_FACE_ATLAS) or bpy.data.materials.new(SIGN_FACE_ATLAS)
    if m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs["Surface"])
    t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-400, 0); t.image = HW._image(paths["albedo"], "sRGB"); t.label = "albedo"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.38; b.inputs["Metallic"].default_value = 0.0
    m.use_backface_culling = True; m.diffuse_color = (0.6, 0.6, 0.6, 1.0); m.roughness = 0.38
    return m


def _library_specs():
    return [(nm, "sign", kw) for nm, kw in _sign_specs(MRS + "Sign_")] + [(MRS + "DirectionBoard", "board", {})]


def _specs_hash(specs):
    return zlib.crc32(json.dumps([SIGN_BAKE_VERSION, FACE_RGB, [(n, t, sorted((k, str(v)) for k, v in kw.items())) for n, t, kw in specs]]).encode()) & 0xFFFFFFFF


def sign_atlas_current(specs=None, tex_dir=None):
    specs = specs or _library_specs(); paths, js = _sa_paths(tex_dir)
    if not all(os.path.exists(p) for p in paths.values()) or not os.path.exists(js): return False
    try:
        with open(js, encoding="utf-8") as f: d = json.load(f)
    except (OSError, ValueError):
        return False
    return d.get("hash") == _specs_hash(specs)


def _face_rgb(mat):
    b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat and mat.node_tree else None
    return tuple(b.inputs["Base Color"].default_value[:3]) if b is not None else tuple(mat.diffuse_color[:3])


def _drawing(o, faces):
    """2D drawing of every face region of an authoring sign: per region a list of (polygon (u, v), depth, rgb)."""
    dg = bpy.context.evaluated_depsgraph_get()
    sources = [(o.data, Matrix.Identity(4))]
    tmp = []
    for ch in o.children:
        if ch.type == "FONT":
            me = bpy.data.meshes.new_from_object(ch.evaluated_get(dg)); tmp.append(me)
            if not me.materials:
                for m in ch.data.materials: me.materials.append(m)
            sources.append((me, ch.matrix_local.copy()))
    out = []
    for reg in faces:
        if reg.get("back"): out.append(None); continue
        ax = reg["axis"]; plane = reg["plane"]; us = [(-p[0] if ax == "y" else p[0]) for p in reg["outline"]]; vs = [p[1] for p in reg["outline"]]
        u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        polys = []
        for me, mx in sources:
            nm = mx.to_3x3().inverted().transposed()
            for p in me.polygons:
                m = me.materials[p.material_index] if p.material_index < len(me.materials) else None
                if m is None or not m.name.startswith(MRS + "SignFace_"): continue
                n = (nm @ p.normal).normalized()
                if abs(n.y if ax == "y" else n.x) < 0.9: continue
                pts = [mx @ me.vertices[i].co for i in p.vertices]
                d = sum((q.y if ax == "y" else q.x) for q in pts) / len(pts) - plane
                if d < -0.0005 or d > 0.03: continue
                uv = [((-q.x if ax == "y" else q.y), q.z) for q in pts]
                cu = sum(a for a, _ in uv) / len(uv); cv = sum(b for _, b in uv) / len(uv)
                if not (u0 - 0.01 <= cu <= u1 + 0.01 and v0 - 0.01 <= cv <= v1 + 0.01): continue
                polys.append((uv, d, _face_rgb(m)))
        out.append({"u0": u0, "u1": u1, "v0": v0, "v1": v1, "outline": [((-p[0] if ax == "y" else p[0]), p[1]) for p in reg["outline"]], "polys": polys,
                    "axis": ax, "plane": plane})
    for me in tmp: bpy.data.meshes.remove(me)
    return out


def _pip(pt, tris):
    x, y = pt
    for a, b, c in tris:
        d1 = (x - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (y - b[1]); d2 = (x - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (y - c[1]); d3 = (x - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (y - a[1])
        if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)): return True
    return False


def _tris(poly):
    idx = geometry.tessellate_polygon([[Vector((u, v, 0.0)) for u, v in poly]])
    return [(poly[a], poly[b], poly[c]) for a, b, c in idx]


def bake_sign_atlas(specs=None, tex_dir=None, samples=16, verbose=True):
    """Bake MRS_SignAtlas (2048 x 2048 albedo / ORM / normal + sign_atlas.json): every library sign is built in its
    authoring form (coloured face, border bands, pictogram meshes, FONT legends), its face regions are flattened to 2D
    (u = the viewer's right, v = up, stacked by depth) and rendered as flat emission into a cell (384 px/m, boards
    256 px/m) with an orthographic Cycles camera. Returns {name: cells}."""
    import time
    t0 = time.time(); specs = specs or _library_specs()
    paths, js = _sa_paths(tex_dir); os.makedirs(os.path.dirname(js), exist_ok=True)
    if not _sm_alive(): _materials()
    tmpc = bpy.data.collections.new(MRS + "SignAtlasTmp"); bpy.context.scene.collection.children.link(tmpc)
    drawings = {}
    try:
        for name, typ, kw in specs:
            tn = "MRSSA_" + name
            o = make_sign(tn, collection=tmpc, **kw) if typ == "sign" else make_direction_board(tn, collection=tmpc, **kw)
            bpy.context.view_layer.update()
            drawings[name] = (_drawing(o, _LAST_FACES.get(tn, [])), _LAST_FACES.get(tn, []))
            _remove_tree(o)
    finally:
        for ob in list(tmpc.objects): _remove_tree(ob)
        bpy.data.collections.remove(tmpc)
    # ---- pack (shelves, tallest first); shrink the density until everything fits
    items = []
    for name, (regs, faces) in drawings.items():
        for k, r in enumerate(regs):
            if r is not None: items.append((name, k, r))
    dens = 1.0
    while True:
        place = {}; x = y = shelf = 0; ok = True
        order = sorted(items, key=lambda it: -(it[2]["v1"] - it[2]["v0"]))
        for name, k, r in order:
            ppm = (320.0 if (r["u1"] - r["u0"]) > 1.5 else 480.0) * dens
            w = int(math.ceil((r["u1"] - r["u0"]) * ppm)) + 2 * SA_PAD; h = int(math.ceil((r["v1"] - r["v0"]) * ppm)) + 2 * SA_PAD
            if x + w > SA_W: x = 0; y += shelf; shelf = 0
            if y + h > SA_H: ok = False; break
            place[(name, k)] = (x, y, w, h, ppm); x += w; shelf = max(shelf, h)
        if ok: break
        dens *= 0.94
    # ---- bake scene: flat emission polygons in pixel units (1 unit = 1 px / 100), z = stacking
    sc = bpy.data.scenes.new(MRS + "SignAtlasBake"); col = bpy.data.collections.new(MRS + "SignAtlasBakeItems"); sc.collection.children.link(col)
    made = [col]; mats = {}

    def mat(rgb):
        key = tuple(round(c, 4) for c in rgb)
        if key not in mats:
            m = bpy.data.materials.new("MRSSA_ink"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
            em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*rgb, 1.0); out = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(em.outputs[0], out.inputs[0]); mats[key] = m; made.append(m)
        return mats[key]
    verts, faces_, fmat = [], [], []
    S_ = 0.01
    for (name, k), (x0, y0, w, h, ppm) in place.items():
        r = drawings[name][0][k]
        def P(u, v, z, r=r, x0=x0, y0=y0, ppm=ppm):
            return ((x0 + SA_PAD + (u - r["u0"]) * ppm) * S_, (SA_H - (y0 + SA_PAD + (r["v1"] - v) * ppm)) * S_, z)
        tris_all = [(_tris(poly), d, rgb) for poly, d, rgb in r["polys"]]
        cu = sum(a for a, _ in r["outline"]) / len(r["outline"]); cv = sum(b for _, b in r["outline"]) / len(r["outline"])
        a0 = r["outline"][0]; a1 = r["outline"][1]; mid = ((a0[0] + a1[0]) / 2, (a0[1] + a1[1]) / 2)
        probe = (mid[0] + (cu - mid[0]) * 0.012, mid[1] + (cv - mid[1]) * 0.012)
        hits = [(d, rgb) for tr, d, rgb in tris_all if _pip(probe, tr)]
        bg = max(hits)[1] if hits else (0.5, 0.5, 0.5)
        # bleed: the whole cell in the edge colour, then the drawing on top
        base = len(verts); verts += [((x0) * S_, (SA_H - y0 - h) * S_, 0.0), ((x0 + w) * S_, (SA_H - y0 - h) * S_, 0.0), ((x0 + w) * S_, (SA_H - y0) * S_, 0.0), (x0 * S_, (SA_H - y0) * S_, 0.0)]
        faces_.append((base, base + 1, base + 2, base + 3)); fmat.append(mat(bg))
        for i, (tr, d, rgb) in enumerate(tris_all):
            z = 0.1 + d * 100.0 + i * 1e-5
            for a, b, c in tr:
                base = len(verts); verts += [P(a[0], a[1], z), P(b[0], b[1], z), P(c[0], c[1], z)]; faces_.append((base, base + 1, base + 2)); fmat.append(mat(rgb))
    me = bpy.data.meshes.new("MRSSA_drawing"); me.from_pydata(verts, [], faces_)
    ml = list(mats.values())
    for m in ml: me.materials.append(m)
    idx = {id(m): i for i, m in enumerate(ml)}
    me.polygons.foreach_set("material_index", [idx[id(m)] for m in fmat]); me.update()
    ob = bpy.data.objects.new("MRSSA_drawing", me); col.objects.link(ob); made += [ob, me]
    cd = bpy.data.cameras.new("MRSSA_cam"); cd.type = "ORTHO"; cd.ortho_scale = SA_W * S_; cd.clip_start = 0.01; cd.clip_end = 100.0
    cam = bpy.data.objects.new("MRSSA_cam", cd); cam.location = (SA_W * S_ / 2, SA_H * S_ / 2, 50.0); col.objects.link(cam); made += [cam, cd]
    sc.camera = cam
    r_ = sc.render; r_.engine = "CYCLES"; r_.resolution_x, r_.resolution_y, r_.resolution_percentage = SA_W, SA_H, 100
    r_.film_transparent = False; r_.use_compositing = False; r_.use_sequencer = False
    cy = sc.cycles; cy.device = "CPU"; cy.samples = samples; cy.use_denoising = False; cy.use_adaptive_sampling = False
    cy.max_bounces = 0; cy.pixel_filter_type = "BLACKMAN_HARRIS"; cy.filter_width = 1.2; cy.seed = 0
    r_.image_settings.file_format = "OPEN_EXR"; r_.image_settings.color_depth = "32"
    exr = os.path.join(os.path.dirname(js), "_sign_atlas.exr"); r_.filepath = exr
    try:
        bpy.ops.render.render(write_still=True, scene=sc.name)
        im = bpy.data.images.load(exr); a = np.empty(im.size[0] * im.size[1] * im.channels, np.float32); im.pixels.foreach_get(a)
        a = a.reshape(im.size[1], im.size[0], im.channels)[::-1, :, :3]; bpy.data.images.remove(im)
    finally:
        for idb in reversed(made):
            try:
                if isinstance(idb, bpy.types.Object): bpy.data.objects.remove(idb)
                elif isinstance(idb, bpy.types.Mesh): bpy.data.meshes.remove(idb)
                elif isinstance(idb, bpy.types.Material): bpy.data.materials.remove(idb)
                elif isinstance(idb, bpy.types.Camera): bpy.data.cameras.remove(idb)
                elif isinstance(idb, bpy.types.Collection): bpy.data.collections.remove(idb)
            except ReferenceError:
                pass
        bpy.data.scenes.remove(sc)
        try: os.remove(exr)
        except OSError: pass
    HW._save_png(paths["albedo"], HW._srgb(a))
    out = {}
    for (name, k), (x0, y0, w, h, ppm) in place.items():
        r = drawings[name][0][k]
        out.setdefault(name, []).append({"px": [x0, y0, w, h], "pad": SA_PAD, "ppm": ppm, "u0": r["u0"], "u1": r["u1"], "v0": r["v0"], "v1": r["v1"],
                                         "axis": r["axis"], "plane": r["plane"], "size": [SA_W, SA_H], "region": k})
    with open(js, "w", encoding="utf-8") as f:
        json.dump({"version": SIGN_BAKE_VERSION, "hash": _specs_hash(specs), "size": [SA_W, SA_H], "density": round(dens, 4), "signs": out}, f, indent=1)
    _SA_CACHE.clear()
    if verbose: print("[signage] MRS_SignAtlas baked: %d faces, density x%.2f, %.1f s" % (len(place), dens, time.time() - t0), flush=True)
    return out


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


def build_signage(game=True, bake="auto", tex_dir=None):
    """Hidden library in MRS_Signage: one sign of every kind, one signal of every style and a direction board.
    game=True (default): signs and the board are the baked game versions (MRS_SignAtlas, baked when missing or when
    the specs changed; bake=True forces, False never bakes); game=False: editable authoring versions."""
    _materials()
    if game and (bake is True or (bake == "auto" and not sign_atlas_current(tex_dir=tex_dir))): bake_sign_atlas(tex_dir=tex_dir)
    col = _col(LIB, clear=True, hidden=True); out = {"signs": [], "signals": [], "boards": []}
    for nm, kw in _sign_specs(MRS + "Sign_"): out["signs"].append(make_sign(nm, collection=col, game=game, **kw))
    for nm, kw in _signal_specs(MRS + "Signal_"): out["signals"].append(make_signal(nm, collection=col, **kw))
    out["boards"].append(make_direction_board(MRS + "DirectionBoard", collection=col, game=game))
    bpy.context.view_layer.update()                       # evaluate child matrices before hiding (hidden objects are not evaluated)
    for lst in out.values():
        for o in lst:
            for ob in [o] + list(o.children_recursive): ob.hide_render = True; ob.hide_viewport = True
    return out


def demo_collection(origin=(0.0, 0.0, 0.0), sign_gap=4.0, signal_gap=4.0):
    """One of everything, visible, laid out in MRS_SignageDemo (authoring versions with editable legends): signs
    (facing +Y) in one row along X at y=0 (plus a custom street-name sign), signals (facing -Y) in a row at y=+14
    (seen from the sign row side), the direction board after the signals.
    Returns {"signs": [...], "signals": [...], "boards": [...], "positions": {name: (x, y, z)}}."""
    _materials(); col = _col(DEMO, clear=True, hidden=False); ox, oy, oz = origin
    out = {"signs": [], "signals": [], "boards": [], "positions": {}}
    specs = _sign_specs(MRS + "Demo_Sign_") + [(MRS + "Demo_Sign_StreetNameDoubleCustom", dict(kind="street_name", text="QUAY LANE|MILL ST", pole_height=2.6, double=True))]
    for i, (nm, kw) in enumerate(specs):
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
