"""CityForge house catalogue: 100+ house types in five culture styles plus the Vancouver mix.

    blender --background --factory-startup --python tools/cityforge/houses.py -- <out_dir> [--only prefix] [--sheet]

Shells come from the Building Tools add-on (tools/thirdparty/building_tools, MIT): floorplan,
floors with slabs, real window and door frames (glass panes, timber lattices), balconies, front
steps and the standard roofs. Each culture adds its own parts on top (geo.Mesh, same conventions as
kit.py): Turkish cumba bays and deep eaves, Japanese irimoya roofs, engawa and hisashi, Korean
hanok roofs with upturned eaves, German half-timbering, French mansards with dormers, Italian and
French shutters, British bay windows and chimneys, porches. Every type has a LOD1 (shell, roof,
flat window panes) for the far city.

Outputs (front faces +Y, origin at the ground centre of the footprint):
  houses.glb          H_<id> and H_<id>_LOD1 for every type (CF_* material names, see
                      world/cityforge/cityforge_materials.gd)
  houses.json         the catalogue: culture, type, footprint, storeys, height, door position, tags
  houses_lod1.json    LOD1 geometry for the build's merged far meshes
  house_catalogue.blend   the catalogue laid out by culture, with the baked library materials
"""
import bpy, bmesh, sys, os, json, math, itertools
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "thirdparty"))
sys.path.insert(0, HERE)
import building_tools
from geo import Mesh, to_object
import kit

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0]) if argv else os.path.join(ROOT, "assets", "cityforge")
ONLY = argv[argv.index("--only") + 1] if "--only" in argv else ""
SHEET = "--sheet" in argv
os.makedirs(OUT, exist_ok=True)
try:
    building_tools.register()
except ValueError:
    pass


def _quiet_popup(message, title="Error", icon="ERROR"):
    """Building Tools reports problems in a popup menu, which crashes Blender in background mode."""
    print("BTOOLS", title, message)


import importlib
for _mod in ("btools.utils.util_common", "btools.building.roof.roof_types", "btools.building.stairs.stairs_types",
             "btools.building.multigroup.multigroup_types", "btools.building.customobj"):
    importlib.import_module("building_tools." + _mod).popup_message = _quiet_popup

# --- materials ---------------------------------------------------------------------------------
PREVIEW = {"CF_Stucco": (0.85, 0.82, 0.74), "CF_Siding": (0.8, 0.78, 0.7), "CF_Brick": (0.42, 0.18, 0.12), "CF_BrickLondon": (0.55, 0.43, 0.27),
           "CF_BrickPainted": (0.88, 0.88, 0.86), "CF_Ashlar": (0.76, 0.72, 0.64), "CF_Cedar": (0.45, 0.31, 0.2), "CF_Yakisugi": (0.08, 0.07, 0.06),
           "CF_LightWood": (0.62, 0.47, 0.3), "CF_Plaster": (0.92, 0.9, 0.84), "CF_TimberDark": (0.18, 0.12, 0.08), "CF_Roof": (0.25, 0.25, 0.27),
           "CF_RoofSlate": (0.2, 0.22, 0.25), "CF_RoofTerracotta": (0.6, 0.28, 0.15), "CF_RoofKawara": (0.2, 0.21, 0.23), "CF_RoofSeam": (0.4, 0.42, 0.43),
           "CF_RoofFlat": (0.4, 0.4, 0.4), "CF_Trim": (0.93, 0.92, 0.88), "CF_Glass": (0.15, 0.22, 0.27), "CF_Door": (0.45, 0.28, 0.18),
           "CF_Concrete": (0.6, 0.6, 0.58), "CF_Metal": (0.15, 0.16, 0.17), "CF_Shutter": (0.18, 0.32, 0.25), "CF_Paper": (0.93, 0.9, 0.82),
           "CF_Lacquer": (0.5, 0.1, 0.08), "CF_Brick_": (0.4, 0.2, 0.15)}
MATS = {}


def mat(name):
    if name not in MATS:
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        c = PREVIEW.get(name, (0.7, 0.7, 0.7))
        b.inputs["Base Color"].default_value = (*c, 1.0)
        b.inputs["Roughness"].default_value = 0.1 if name == "CF_Glass" else 0.75
        MATS[name] = m
    return MATS[name]


class Lazy(dict):
    def __missing__(self, key):
        self[key] = mat(key)
        return self[key]


LAZY = Lazy()

# --- Building Tools helpers -------------------------------------------------------------------
GROUPS = ["slabs", "walls", "columns", "frame", "window", "window_bars", "window_panes", "window_louvers",
          "door", "door_panes", "door_panels", "door_louvers", "stairs", "balcony", "railing_posts",
          "railing_walls", "railing_rails", "roof", "roof_hangs", "custom"]


def bm_of(obj):
    return bmesh.from_edit_mesh(obj.data)


def face_info(f):
    zs = [v.co.z for v in f.verts]
    xy = [Vector((v.co.x, v.co.y)) for v in f.verts]
    w = max((a - b).length for a in xy for b in xy)
    return dict(c=f.calc_center_median().copy(), n=f.normal.copy(), w=w, h=max(zs) - min(zs), z0=min(zs))


def near(f, c, n, tol=0.05):
    return (f.calc_center_median() - c).length < tol and f.normal.dot(n) > 0.99


def select_where(obj, pred):
    bm = bm_of(obj)
    n = 0
    for f in bm.faces:
        s = bool(pred(f))
        f.select_set(s)
        n += s
    bmesh.update_edit_mesh(obj.data)
    return n


def split_into_bays(obj, faces, bay):
    """Cut wall faces into vertical strips about `bay` wide (Building Tools puts one component per face)."""
    bm = bm_of(obj)
    targets = [f for f in bm.faces if any(near(f, w["c"], w["n"]) for w in faces)]
    for f in targets:
        info = face_info(f)
        n = max(1, int(round(info["w"] / bay)))
        if n < 2: continue
        t = Vector((-f.normal.y, f.normal.x, 0)).normalized()
        xs = [v.co for v in f.verts]
        d0, d1 = min(v.dot(t) for v in xs), max(v.dot(t) for v in xs)
        geom = [f] + list(f.edges) + list(f.verts)
        for i in range(1, n):
            r = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=t * (d0 + (d1 - d0) * i / n), plane_no=t)
            geom = list({*geom, *r["geom"]} & ({*bm.faces} | {*bm.edges} | {*bm.verts}))
    bmesh.update_edit_mesh(obj.data)
    bm = bm_of(obj)
    return [face_info(f) for f in bm.faces if abs(f.normal.z) < 0.05 and face_info(f)["h"] > 1.5]


def shell(spec, lod):
    """Building Tools: floorplan, floors and (for BT roofs) the roof. Returns (object, wall faces, eave z)."""
    if bpy.context.mode != "OBJECT": bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.cursor.location = (0, 0, 0)
    w, d = spec["plan"]
    bpy.ops.btools.add_floorplan(props=dict(type="RECTANGULAR", width=w, length=d))
    obj = bpy.context.active_object
    obj.bt_materials.clear()
    for i, g in enumerate(GROUPS):
        mt = obj.bt_materials.add(); mt.name = g; mt.index = i; mt.auto_map = False
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.btools.add_floors(props=dict(floor_count=spec["storeys"], floor_height=spec["floor_h"], slab_thickness=0.22, slab_outset=spec.get("slab_outset", 0.05)))
    bm = bm_of(obj)
    walls = [face_info(f) for f in bm.faces if abs(f.normal.z) < 0.05 and face_info(f)["h"] > 1.5]
    top = max(v.co.z for v in bm.verts)
    rk, rh, ro, rm = spec["roof"]
    if rk in ("GABLE", "HIP", "FLAT"):
        select_where(obj, lambda f: f.normal.z > 0.9 and abs(f.calc_center_median().z - top) < 0.01)
        props = dict(type=rk, height=rh, outset=ro, thickness=0.16)
        if rk == "GABLE": props["gable_type"] = "BOX"
        if rk == "FLAT": props.update(add_border=True, border=0.25, height=0.5)
        bpy.ops.btools.add_roof(props=props)
    return obj, walls, top


def facade(obj, spec, walls, top):
    """Doors, windows, balconies, steps on the shell. Returns the window rectangles (BT coordinates)."""
    fh = spec["floor_h"] + 0.22
    floor_of = lambda w: int(round((w["z0"] - 0.22) / fh))
    bays = [b for b in split_into_bays(obj, walls, spec.get("bay", 3.0)) if b["z0"] + b["h"] <= top + 0.05]   # not gable ends
    front = [b for b in bays if b["n"].y < -0.95]
    used = set()
    windows = []
    # the door: the front ground-floor bay nearest the requested position
    g0 = [b for b in front if floor_of(b) == 0]
    door = None
    if g0:
        want = spec.get("door_x", 0.0) * spec["plan"][0] / 2
        db = min(g0, key=lambda b: abs(b["c"].x - want))
        used.add(id(db))
        select_where(obj, lambda f: near(f, db["c"], db["n"]))
        dw = spec.get("door_w", 1.0)
        fill = spec.get("door_fill", "PANELS")
        props = dict(fill_type=fill, size_offset=dict(size=(dw, 2.15)), frame_thickness=0.1, frame_depth=0.06, door_depth=0.1)
        if fill == "PANELS": props["panel_fill"] = dict(panel_count_x=1, panel_count_y=3)
        else: props["glass_fill"] = dict(pane_count_x=2 if dw > 1.4 else 1, pane_count_y=3)
        if dw > 1.4: props["double_door"] = True
        bpy.ops.btools.add_door(props=props)
        door = (db["c"].x, db["c"].y, db["z0"])
    # balconies on upper floors
    if spec.get("balconies"):
        for b in front:
            if floor_of(b) >= 1 and abs(b["c"].x) < spec["plan"][0] * 0.3 and id(b) not in used:
                used.add(id(b))
                select_where(obj, lambda f: near(f, b["c"], b["n"]))
                bpy.ops.btools.add_balcony(props=dict(depth=1.2, size_offset=dict(size=(min(b["w"] - 0.3, 3.2), 0.1)), has_railing=True))
                windows.append((b, (min(b["w"] - 0.6, 1.8), 2.2), -0.25))
    # bays hidden behind a cumba or bay window get no frames
    hide = spec.get("hide_bays", lambda b, fl: False)
    ww, wh = spec.get("win", (1.2, 1.4))
    sel = [b for b in bays if id(b) not in used and b["w"] > ww + 0.3 and not hide(b, floor_of(b))]
    if sel:
        select_where(obj, lambda f: any(near(f, b["c"], b["n"]) for b in sel))
        fill = spec.get("win_fill", "GLASS_PANES")
        props = dict(fill_type=fill, array=dict(count=1), size_offset=dict(size=(ww, wh), offset=(0.0, 0.15)),
                     frame_thickness=0.08, frame_depth=0.05, window_depth=0.1)
        if fill == "GLASS_PANES": props["glass_fill"] = dict(pane_count_x=spec.get("panes", (2, 2))[0], pane_count_y=spec.get("panes", (2, 2))[1], pane_margin=0.04)
        elif fill == "BAR": props["bar_fill"] = dict(bar_count_x=6, bar_count_y=1, bar_width=0.04, bar_depth=0.04)
        elif fill == "LOUVER": props["louver_fill"] = dict(louver_count=8, louver_margin=0.05, louver_depth=0.05)
        bpy.ops.btools.add_window(props=props)
        for b in sel: windows.append((b, (ww, wh), 0.15))
    bpy.ops.object.mode_set(mode="OBJECT")
    return windows, door, bays


def bt_materials(obj, spec):
    """Map the add-on's material groups (a per-face attribute) to CF materials for this style."""
    me = obj.data
    attr = me.attributes.get(".bt_material_group_index")
    if attr is None: return
    roles = {"walls": spec["wall"], "slabs": spec.get("slab_mat", "CF_Concrete"), "columns": spec.get("trim", "CF_Trim"),
             "frame": spec.get("frame", spec.get("trim", "CF_Trim")), "window": spec.get("frame", spec.get("trim", "CF_Trim")),
             "window_bars": spec.get("bars", "CF_TimberDark"), "window_panes": "CF_Glass", "window_louvers": spec.get("shutter", "CF_Shutter"),
             "door": spec.get("frame", spec.get("trim", "CF_Trim")), "door_panes": "CF_Glass", "door_panels": spec.get("door_mat", "CF_Door"),
             "door_louvers": "CF_Door", "stairs": "CF_Concrete", "balcony": spec.get("balcony_mat", "CF_Concrete"),
             "railing_posts": spec.get("rail", "CF_Metal"), "railing_walls": spec.get("rail", "CF_Metal"), "railing_rails": spec.get("rail", "CF_Metal"),
             "roof": spec["roof"][3], "roof_hangs": spec["wall"] if spec["roof"][0] == "GABLE" else spec.get("fascia", spec.get("trim", "CF_Trim")),
             "custom": "CF_Trim"}
    me.materials.clear()
    names = []
    for g in obj.bt_materials:
        nm = roles.get(g.name.lower(), "CF_Trim")
        if nm not in names:
            names.append(nm)
            me.materials.append(LAZY[nm])
    slot = {i: names.index(roles.get(g.name.lower(), "CF_Trim")) for i, g in enumerate(obj.bt_materials)}
    vals = [0] * len(me.polygons)
    attr.data.foreach_get("value", vals)
    for p, v in zip(me.polygons, vals):
        p.material_index = slot.get(v, 0)


# --- culture parts (geo.Mesh, Building Tools coordinates: front wall at y = -d/2) ---------------
def front_face(spec):
    w, d = spec["plan"]
    f = kit.Face("front", -w / 2, -d / 2, w / 2, d / 2)
    # kit.Face "front" is +Y; in BT coordinates the front is -Y: use "back" (its P() mirrors u)
    return kit.Face("back", -w / 2, -d / 2, w / 2, d / 2)


def add_cumba(m, spec, lod):
    """Turkish cumba: a closed timber bay window projecting over the street on each upper floor."""
    w, d = spec["plan"]
    fh = spec["floor_h"] + 0.22
    cw, cd = min(3.8, w * 0.45), 1.15
    for fl in range(1, spec["storeys"]):
        z0, z1 = fl * fh + 0.1, (fl + 1) * fh - 0.05
        y0 = -d / 2 - cd
        m.box(-cw / 2, y0, z0, cw / 2, -d / 2, z1, spec["wall"], zb=0.0)
        # windows on the three sides
        for side, (a, b) in (("front", (-cw / 2, cw / 2)),):
            pass
        F = kit.Face("back", -cw / 2, y0, cw / 2, -d / 2)
        n = 3
        for k in range(n):
            u = -cw / 2 + cw * (k + 0.5) / n
            kit.window(m, F, u, z0 + 0.7, cw / n - 0.35, 1.5, lod, frame=spec.get("frame", "CF_Trim"))
        for side in ("left", "right"):
            Fs = kit.Face(side, -cw / 2, y0, cw / 2, -d / 2)
            kit.window(m, Fs, 0.0, z0 + 0.7, cd - 0.3, 1.5, lod, mullion=False, frame=spec.get("frame", "CF_Trim"))
        # corbel brackets under the bay and a small hipped cap
        if not lod:
            for x in (-cw / 2 + 0.25, 0.0, cw / 2 - 0.25):
                m.poly([(x - 0.06, -d / 2, z0), (x - 0.06, y0 + 0.05, z0), (x - 0.06, -d / 2, z0 - 0.7)], spec.get("trim", "CF_Trim"))
                m.poly([(x + 0.06, -d / 2, z0), (x + 0.06, -d / 2, z0 - 0.7), (x + 0.06, y0 + 0.05, z0)], spec.get("trim", "CF_Trim"))
                m.poly([(x - 0.06, y0 + 0.05, z0), (x + 0.06, y0 + 0.05, z0), (x + 0.06, -d / 2, z0 - 0.7), (x - 0.06, -d / 2, z0 - 0.7)], spec.get("trim", "CF_Trim"))
        if fl < spec["storeys"] - 1:            # the top bay tucks under the eaves
            m.box(-cw / 2 - 0.08, y0 - 0.08, z1, cw / 2 + 0.08, -d / 2, z1 + 0.12, spec["roof"][3])


def add_half_timber(m, spec, lod, from_floor=1):
    """Fachwerk / Tudor: dark oak posts, rails and braces on the upper floors of every wall."""
    if lod: return
    w, d = spec["plan"]
    fh = spec["floor_h"] + 0.22
    T = "CF_TimberDark"
    for fl in range(from_floor, spec["storeys"]):
        z0, z1 = fl * fh, (fl + 1) * fh
        for side in ("front", "back", "left", "right"):
            F = kit.Face({"front": "back", "back": "front", "left": "left", "right": "right"}[side], -w / 2, -d / 2, w / 2, d / 2)
            L = F.length
            F.box(m, -L / 2, z0, -0.01, L / 2, z0 + 0.18, 0.05, T)               # sill beam
            F.box(m, -L / 2, z1 - 0.2, -0.01, L / 2, z1, 0.05, T)                # head beam
            n = max(2, int(L / 1.6))
            for k in range(n + 1):
                u = -L / 2 + L * k / n
                F.box(m, u - 0.09, z0, -0.01, u + 0.09, z1, 0.05, T)
            for k in range(n):
                if k % 2: continue
                u0, u1 = -L / 2 + L * k / n + 0.09, -L / 2 + L * (k + 1) / n - 0.09
                # a diagonal brace as a thin quad strip
                a, b = F.P(u0, z0 + 0.18, 0.05), F.P(u1, z1 - 0.2, 0.05)
                a2, b2 = F.P(u0 + 0.16, z0 + 0.18, 0.05), F.P(u1, z1 - 0.36, 0.05)
                m.poly([a, a2, b2, b] if side in ("front", "right") else [b, b2, a2, a], T)


def add_shutters(m, spec, windows, lod):
    if lod: return
    S = spec.get("shutter", "CF_Shutter")
    for b, (ww, wh), off in windows:
        if b["n"].z > 0.5: continue
        n = b["n"]
        t = Vector((-n.y, n.x, 0)).normalized()
        cz = b["c"].z + off
        for s in (-1, 1):
            cx = b["c"] + t * s * (ww / 2 + 0.28) + n * 0.03
            x0, y0 = cx.x - abs(t.x) * 0.25 - abs(n.x) * 0.03, cx.y - abs(t.y) * 0.25 - abs(n.y) * 0.03
            x1, y1 = cx.x + abs(t.x) * 0.25 + abs(n.x) * 0.03, cx.y + abs(t.y) * 0.25 + abs(n.y) * 0.03
            m.box(x0, y0, cz - wh / 2, x1, y1, cz + wh / 2, S)


def add_chimneys(m, spec, top, lod, count=1):
    w, d = spec["plan"]
    for k in range(count):
        x = (-w / 2 + 0.5) if k == 0 else (w / 2 - 0.5)
        kit.chimney(m, x, 0.0, top - 0.5, top + spec["roof"][1] + 1.0, lod)


def add_bay_window(m, spec, lod):
    """British canted bay on the ground floor, beside the door, with a small slate roof."""
    w, d = spec["plan"]
    bw, bd = 2.6, 0.8
    cx = w / 2 - bw / 2 - 0.6
    z0, z1 = 0.25, spec["floor_h"]
    y0 = -d / 2 - bd
    m.box(cx - bw / 2, y0, -0.3, cx + bw / 2, -d / 2, z0, "CF_Concrete")
    m.box(cx - bw / 2, y0, z0, cx + bw / 2, -d / 2, z0 + 0.6, spec["wall"], zb=0.0)
    F = kit.Face("back", cx - bw / 2, y0, cx + bw / 2, -d / 2)
    if lod:
        F.pane(m, -bw / 2 + 0.1, z0 + 0.6, bw / 2 - 0.1, z1 - 0.15, 0.03, "CF_Glass")
    else:
        F.box(m, -bw / 2 + 0.05, z0 + 0.6, -0.05, bw / 2 - 0.05, z1 - 0.15, 0.0, "CF_Glass")
        for u in (-bw / 2 + 0.05, -bw / 6, bw / 6, bw / 2 - 0.05):
            F.box(m, u - 0.06, z0 + 0.6, 0.0, u + 0.06, z1 - 0.15, 0.06, spec.get("frame", "CF_Trim"))
        F.box(m, -bw / 2, z0 + 0.55, 0.0, bw / 2, z0 + 0.65, 0.08, spec.get("frame", "CF_Trim"))
    m.box(cx - bw / 2, y0, z1 - 0.15, cx + bw / 2, -d / 2, z1, spec.get("trim", "CF_Trim"))
    for side in ("left", "right"):
        Fs = kit.Face(side, cx - bw / 2, y0, cx + bw / 2, -d / 2)
        Fs.box(m, -bd / 2 + 0.05, z0 + 0.6, -0.04, bd / 2 - 0.05, z1 - 0.15, 0.0, "CF_Glass") if not lod else None
    kit.hip(m, cx - bw / 2, cx + bw / 2, y0, -d / 2 + 0.3, z1, 0.6, 0.12, roof=spec["roof"][3])


def add_modern(m, spec, top, lod):
    """Modern Japanese / Korean house details: door canopy, timber slat screen, a cantilevered
    balcony with a glass balustrade on the upper floor, AC units, a roof-terrace railing."""
    w, d = spec["plan"]
    fh = spec["floor_h"] + 0.22
    y = -d / 2
    m.box(-1.6, y - 1.2, 2.55, 1.2, y, 2.7, "CF_Concrete")                       # canopy over the door
    if not lod:
        for k in range(9):                                                      # slat screen beside the door
            x = 1.5 + k * 0.14
            m.box(x, y - 0.12, 0.25, x + 0.06, y - 0.06, 2.5, "CF_LightWood")
    if spec["storeys"] > 1:
        m.box(-w / 2 + 0.6, y - 1.3, fh + 0.05, -0.4, y, fh + 0.25, "CF_Concrete")     # balcony slab
        if not lod:
            m.box(-w / 2 + 0.6, y - 1.32, fh + 0.25, -0.4, y - 1.26, fh + 1.25, "CF_Glass")
            m.box(-w / 2 + 0.6, y - 1.34, fh + 1.2, -0.4, y - 1.24, fh + 1.28, "CF_Metal")
    if not lod:
        for k in range(min(spec["storeys"], 3)):                               # AC units on the side wall
            z = 0.4 + k * fh
            m.box(w / 2, -1.0, z, w / 2 + 0.3, -0.2, z + 0.6, "CF_Trim")
            m.box(w / 2 + 0.3, -0.9, z + 0.1, w / 2 + 0.31, -0.3, z + 0.5, "CF_Metal")
    if spec["roof"][0] == "FLAT" and not lod:                                   # open metal railing round the roof terrace
        for (x0, y0, x1, y1) in ((-w / 2 + 0.2, -d / 2 + 0.2, w / 2 - 0.2, -d / 2 + 0.25), (-w / 2 + 0.2, d / 2 - 0.25, w / 2 - 0.2, d / 2 - 0.2)):
            m.box(x0, y0, top + 1.45, x1, y1, top + 1.52, "CF_Metal")
            n = int((x1 - x0) / 1.5)
            for k in range(n + 1):
                x = x0 + (x1 - x0) * k / max(n, 1)
                m.box(x - 0.03, y0, top + 0.5, x + 0.03, y1, top + 1.45, "CF_Metal")


def add_engawa(m, spec, lod):
    """Japanese engawa: a raised timber veranda along the front with posts and a pent roof (hisashi)."""
    w, d = spec["plan"]
    ed = 1.1
    m.box(-w / 2, -d / 2 - ed, -0.2, w / 2, -d / 2, 0.45, "CF_LightWood")
    z = spec["floor_h"] - 0.1
    if not lod:
        for k in range(5):
            x = -w / 2 + 0.12 + (w - 0.24) * k / 4
            m.box(x - 0.08, -d / 2 - ed + 0.05, 0.45, x + 0.08, -d / 2 - ed + 0.21, z, "CF_TimberDark")
    add_hisashi(m, spec, -d / 2 - ed - 0.35, z, lod)


def add_hisashi(m, spec, y_out, z, lod):
    """A pent roof (hisashi) across the front at height z, out to y_out."""
    w, d = spec["plan"]
    m.poly([(-w / 2 - 0.2, y_out, z), (w / 2 + 0.2, y_out, z), (w / 2 + 0.2, -d / 2, z + 0.7), (-w / 2 - 0.2, -d / 2, z + 0.7)][::-1], spec["roof"][3])
    m.poly([(-w / 2 - 0.2, y_out, z - 0.12), (-w / 2 - 0.2, -d / 2, z + 0.58), (w / 2 + 0.2, -d / 2, z + 0.58), (w / 2 + 0.2, y_out, z - 0.12)][::-1], "CF_TimberDark")


def curved_roof(m, spec, top, lift=0.55, irimoya=True, mat="CF_RoofKawara"):
    """Hip roof with eaves that sweep up at the corners (Korean giwa / Japanese kawara), with a
    small gable (irimoya) on top. Built as a grid of quads so the eave line can curve."""
    w, d = spec["plan"]
    rh, ro = spec["roof"][1], spec["roof"][2]
    xa, xb, ya, yb = -w / 2 - ro, w / 2 + ro, -d / 2 - ro, d / 2 + ro
    ze = top - 0.25
    zr = top + rh
    half = (yb - ya) / 2
    r0, r1 = xa + half * 0.8, xb - half * 0.8
    if r1 < r0: r0 = r1 = 0.0
    n = 10

    def eave(t):            # t 0..1 along an eave edge: lifted towards both corners
        return ze + lift * (abs(2 * t - 1) ** 3)

    def strip(p0, p1, q0, q1, steps):
        for i in range(steps):
            a, b = i / steps, (i + 1) / steps
            e0 = (p0[0] + (p1[0] - p0[0]) * a, p0[1] + (p1[1] - p0[1]) * a, eave(a))
            e1 = (p0[0] + (p1[0] - p0[0]) * b, p0[1] + (p1[1] - p0[1]) * b, eave(b))
            r_0 = (q0[0] + (q1[0] - q0[0]) * a, q0[1] + (q1[1] - q0[1]) * a, zr)
            r_1 = (q0[0] + (q1[0] - q0[0]) * b, q0[1] + (q1[1] - q0[1]) * b, zr)
            m.poly([e0, e1, r_1, r_0], mat)
            m.poly([(e0[0], e0[1], e0[2] - 0.18), (r_0[0], r_0[1], r_0[2] - 0.18), (r_1[0], r_1[1], r_1[2] - 0.18), (e1[0], e1[1], e1[2] - 0.18)], "CF_TimberDark")
    ym = 0.0
    strip((xa, ya), (xb, ya), (r0, ym), (r1, ym), n)          # front slope
    strip((xb, yb), (xa, yb), (r1, ym), (r0, ym), n)          # back slope
    strip((xa, yb), (xa, ya), (r0, ym), (r0, ym), 4)          # hips
    strip((xb, ya), (xb, yb), (r1, ym), (r1, ym), 4)
    # ridge beam and the irimoya gable on top
    m.box(r0 - 0.3, -0.18, zr - 0.05, r1 + 0.3, 0.18, zr + 0.25, mat)
    if irimoya and r1 - r0 > 1.0:
        kit.gable_x(m, r0 - 0.4, r1 + 0.4, -half * 0.35, half * 0.35, zr - 0.05, 0.9, 0.15, gable_mat="CF_TimberDark", roof=mat)
    # eave fascia
    for (x0, y0, x1, y1) in ((xa, ya, xb, ya), (xa, yb, xb, yb)):
        for i in range(n):
            a, b = i / n, (i + 1) / n
            p, q = (x0 + (x1 - x0) * a, y0), (x0 + (x1 - x0) * b, y0)
            m.poly([(p[0], p[1], eave(a) - 0.18), (q[0], q[1], eave(b) - 0.18), (q[0], q[1], eave(b)), (p[0], p[1], eave(a))] if y0 < 0 else
                   [(q[0], q[1], eave(b) - 0.18), (p[0], p[1], eave(a) - 0.18), (p[0], p[1], eave(a)), (q[0], q[1], eave(b))], "CF_TimberDark")


def mansard(m, spec, top, lod):
    """French mansard: steep slate slopes to a low top, dormers on the front slope."""
    w, d = spec["plan"]
    rh = spec["roof"][1]
    inset = 0.9
    z1 = top + rh
    a = [(-w / 2 - 0.15, -d / 2 - 0.15), (w / 2 + 0.15, -d / 2 - 0.15), (w / 2 + 0.15, d / 2 + 0.15), (-w / 2 - 0.15, d / 2 + 0.15)]
    b = [(-w / 2 + inset, -d / 2 + inset), (w / 2 - inset, -d / 2 + inset), (w / 2 - inset, d / 2 - inset), (-w / 2 + inset, d / 2 - inset)]
    for k in range(4):
        p0, p1 = a[k], a[(k + 1) % 4]
        q0, q1 = b[k], b[(k + 1) % 4]
        m.poly([(p0[0], p0[1], top), (p1[0], p1[1], top), (q1[0], q1[1], z1), (q0[0], q0[1], z1)], spec["roof"][3])
    m.poly([(q[0], q[1], z1 + 0.6) for q in b], "CF_RoofSeam")
    for k in range(4):
        q0, q1 = b[k], b[(k + 1) % 4]
        m.poly([(q0[0], q0[1], z1), (q1[0], q1[1], z1), (q1[0], q1[1], z1 + 0.6), (q0[0], q0[1], z1 + 0.6)], "CF_RoofSeam")
    m.box(-w / 2 - 0.25, -d / 2 - 0.25, top - 0.2, w / 2 + 0.25, d / 2 + 0.25, top + 0.05, "CF_Trim")     # cornice
    # dormers
    nd = max(1, int(w / 3.2))
    for k in range(nd):
        x = -w / 2 + w * (k + 0.5) / nd
        y = -d / 2 + 0.25
        m.box(x - 0.6, y - 0.1, top + 0.3, x + 0.6, y + 0.9, top + 1.9, spec["wall"], zb=0.0)
        F = kit.Face("back", x - 0.6, y - 0.1, x + 0.6, y + 0.9)
        kit.window(m, F, 0.0, top + 0.55, 0.75, 1.1, lod, frame=spec.get("frame", "CF_Trim"))
        sub = Mesh()
        kit.gable_y(sub, x - 0.7, x + 0.7, y - 0.2, y + 0.9, top + 1.9, 0.6, 0.08, gable_mat=spec["wall"], roof=spec["roof"][3])
        m.append(sub)


def add_porch(m, spec, lod):
    w, d = spec["plan"]
    pw = min(w - 0.6, 5.0)
    sub = Mesh()
    kit.porch(sub, -pw / 2, pw / 2, d / 2, 2.2, 0.45, spec["floor_h"] - 0.2, lod, cols=3, roof="shed", col_w=0.3)
    sub2 = Mesh()
    sub2.append(sub, math.pi)               # kit faces +Y: turn it to the BT front (-Y)
    m.append(sub2)


def add_steps(m, spec, door, lod):
    if door is None: return
    x, y, z0 = door
    h = 0.45
    for k in range(3):
        m.box(x - 0.8, y - 0.3 * (k + 1), -0.3, x + 0.8, y - 0.3 * k, h - k * 0.15, "CF_Concrete")


def add_plinth(m, spec, mat="CF_Ashlar", h=0.6):
    w, d = spec["plan"]
    m.box(-w / 2 - 0.05, -d / 2 - 0.05, -0.6, w / 2 + 0.05, d / 2 + 0.05, h, mat, top=False, zb=-0.6)


def add_lod1_panes(m, windows):
    for b, (ww, wh), off in windows:
        n = b["n"]
        t = Vector((-n.y, n.x, 0)).normalized()
        c = b["c"] + n * 0.03
        cz = c.z + off
        p = [c + t * (-ww / 2), c + t * (ww / 2)]
        q = [(p[0].x, p[0].y, cz - wh / 2), (p[1].x, p[1].y, cz - wh / 2), (p[1].x, p[1].y, cz + wh / 2), (p[0].x, p[0].y, cz + wh / 2)]
        m.poly(q, "CF_Glass")


# --- the styles ----------------------------------------------------------------------------------
def T(culture, kind, plans, storeys, wall, roof, **kw):
    return dict(culture=culture, kind=kind, plans=plans, storeys=storeys, wall=wall, roof=roof, **kw)


STYLES = [
    # Turkish: Ottoman konak with cumba bays, apartman blocks, detached stucco houses, timber yali
    T("turkish", "konak", [(10.0, 9.0), (11.0, 10.0), (9.5, 9.5)], [2, 3], ["CF_Stucco", "CF_Plaster", "CF_Siding"],
      ("HIP", 1.6, 0.9, "CF_RoofTerracotta"), extras=["cumba", "plinth"], win=(0.9, 1.6), bay=2.2, frame="CF_Trim", door_fill="PANELS"),
    T("turkish", "apartman", [(12.0, 12.0), (11.0, 13.0)], [4, 5], ["CF_Stucco"], ("HIP", 1.8, 0.6, "CF_RoofTerracotta"),
      extras=["plinth"], balconies=True, win=(1.3, 1.5), bay=2.6, door_fill="GLASS_PANES", door_w=1.6),
    T("turkish", "mustakil", [(10.0, 9.0), (11.5, 9.5)], [1, 2], ["CF_Stucco", "CF_BrickPainted"], ("HIP", 1.8, 0.7, "CF_RoofTerracotta"),
      extras=["shutters", "steps"], win=(1.0, 1.4), bay=2.4, shutter="CF_Shutter"),
    T("turkish", "yali", [(11.0, 9.5), (12.0, 10.0)], [2, 3], ["CF_Siding"], ("HIP", 1.4, 1.0, "CF_RoofTerracotta"),
      extras=["cumba"], win=(0.9, 1.7), bay=2.0),
    # Japanese: machiya and minka in dark timber, modern boxes, irimoya roofs, engawa and lattice
    T("japanese", "machiya", [(7.5, 11.0), (8.0, 12.0)], [2], ["CF_Yakisugi", "CF_Cedar"], ("GABLE", 2.0, 0.7, "CF_RoofKawara"),
      extras=["hisashi"], win=(1.4, 1.1), win_fill="BAR", bay=2.2, frame="CF_TimberDark", trim="CF_TimberDark", door_fill="GLASS_PANES", door_w=1.8),
    T("japanese", "minka", [(11.0, 9.0), (12.0, 9.5)], [1, 2], ["CF_Plaster", "CF_Cedar"], ("IRIMOYA", 2.6, 0.9, "CF_RoofKawara"),
      extras=["engawa", "plinth_low"], win=(1.6, 1.2), win_fill="BAR", bay=2.4, frame="CF_TimberDark", trim="CF_TimberDark", door_fill="GLASS_PANES", door_w=1.8),
    T("japanese", "modern", [(9.0, 10.0), (8.0, 11.0)], [2, 3], ["CF_Plaster", "CF_LightWood"], ("FLAT", 0.4, 0.2, "CF_RoofFlat"),
      extras=["modern"], win=(1.6, 1.0), bay=2.6, frame="CF_Metal", door_fill="PANELS", door_x=-0.15),
    T("japanese", "nagaya", [(13.0, 8.0), (12.0, 8.5)], [2], ["CF_Cedar", "CF_Yakisugi"], ("GABLE", 1.8, 0.6, "CF_RoofKawara"),
      extras=["hisashi"], win=(1.2, 1.1), win_fill="BAR", bay=2.0, frame="CF_TimberDark", trim="CF_TimberDark", door_fill="GLASS_PANES"),
    T("japanese", "shed", [(9.0, 10.0), (10.0, 9.5)], [2], ["CF_Yakisugi", "CF_Plaster"], ("SHED", 2.0, 0.6, "CF_RoofSeam"),
      win=(1.4, 1.2), bay=2.6, frame="CF_Metal"),
    # Korean: hanok with giwa roofs, dasedae villas in red brick, modern concrete
    T("korean", "hanok", [(12.0, 8.0), (13.0, 8.5), (11.0, 7.5)], [1], ["CF_Plaster"], ("HANOK", 2.4, 1.3, "CF_RoofKawara"),
      extras=["plinth_stone", "posts"], win=(1.5, 1.3), win_fill="BAR", bay=2.6, frame="CF_TimberDark", trim="CF_TimberDark", door_fill="GLASS_PANES", door_w=1.6),
    T("korean", "villa", [(12.0, 12.0), (11.0, 12.5)], [4], ["CF_Brick", "CF_BrickLondon"], ("FLAT", 0.5, 0.2, "CF_RoofFlat"),
      balconies=True, win=(1.4, 1.4), bay=2.6, frame="CF_Metal", rail="CF_Metal", door_fill="GLASS_PANES", door_w=1.6),
    T("korean", "modern", [(10.0, 10.0), (11.0, 9.0)], [2, 3], ["CF_Concrete", "CF_Plaster"], ("FLAT", 0.5, 0.2, "CF_RoofFlat"),
      extras=["modern"], win=(1.8, 1.4), bay=2.8, frame="CF_Metal", door_x=-0.15),
    T("korean", "hanok_large", [(15.0, 9.0), (14.0, 8.5)], [1], ["CF_Plaster"], ("HANOK", 2.8, 1.5, "CF_RoofKawara"),
      extras=["plinth_stone", "posts"], win=(1.5, 1.4), win_fill="BAR", bay=2.6, frame="CF_TimberDark", trim="CF_TimberDark", door_fill="GLASS_PANES", door_w=1.8),
    T("korean", "townhouse", [(8.0, 12.0), (9.0, 12.0)], [3], ["CF_Brick", "CF_Plaster"], ("FLAT", 0.5, 0.2, "CF_RoofFlat"),
      extras=["modern"], win=(1.4, 1.3), bay=2.4, frame="CF_Metal", door_x=-0.2),
    # European: German Fachwerk, French maison with mansard, Italian casa
    T("european", "fachwerk", [(8.5, 11.0), (9.0, 12.0)], [2, 3], ["CF_Plaster"], ("GABLE", 4.5, 0.4, "CF_RoofTerracotta"),
      extras=["half_timber", "plinth"], win=(0.9, 1.3), bay=1.8, frame="CF_TimberDark", door_fill="PANELS"),
    T("european", "maison", [(11.0, 10.0), (12.0, 10.5)], [2, 3], ["CF_Ashlar", "CF_Stucco"], ("MANSARD", 2.4, 0.2, "CF_RoofSlate"),
      extras=["shutters"], win=(1.0, 1.9), bay=2.2, shutter="CF_Shutter", door_fill="GLASS_PANES", door_w=1.5),
    T("european", "casa", [(11.0, 10.0), (12.0, 11.0)], [2, 3], ["CF_Stucco"], ("HIP", 1.4, 0.6, "CF_RoofTerracotta"),
      extras=["shutters"], win=(1.0, 1.7), bay=2.3, shutter="CF_Shutter", balconies=True),
    T("european", "townhouse", [(8.0, 11.0), (9.0, 12.0)], [3, 4], ["CF_Stucco", "CF_Ashlar", "CF_BrickPainted"], ("GABLE", 3.6, 0.3, "CF_RoofSlate"),
      extras=["shutters", "plinth"], win=(1.0, 1.8), bay=2.0, shutter="CF_Shutter", door_x=-0.5),
    # British: semi-detached pairs, Victorian bays, Georgian, Tudor revival
    T("british", "semi", [(13.0, 9.0), (12.5, 9.5)], [2], ["CF_BrickLondon", "CF_Brick"], ("HIP", 2.6, 0.35, "CF_RoofSlate"),
      extras=["bay_window", "chimneys2"], win=(1.0, 1.5), bay=2.4, door_x=-0.35),
    T("british", "victorian", [(8.0, 11.0), (8.5, 12.0)], [2, 3], ["CF_Brick", "CF_BrickLondon"], ("GABLE", 3.2, 0.3, "CF_RoofSlate"),
      extras=["bay_window", "chimneys"], win=(1.0, 1.7), bay=2.2, door_x=-0.6),
    T("british", "georgian", [(12.0, 9.0), (11.0, 9.0)], [2, 3], ["CF_BrickLondon", "CF_Stucco"], ("HIP", 2.2, 0.3, "CF_RoofSlate"),
      extras=["chimneys2", "steps"], win=(1.0, 1.8), bay=2.2, panes=(3, 3)),
    T("british", "tudor", [(10.0, 12.0), (9.5, 11.5)], [2], ["CF_Brick"], ("GABLE", 4.0, 0.4, "CF_Roof"),
      extras=["half_timber", "chimneys"], win=(1.2, 1.3), bay=2.2, panes=(3, 2)),
    # Vancouver mix (the original city style)
    T("mixed", "craftsman", [(10.0, 12.0), (9.5, 11.5)], [1, 2], ["CF_Siding"], ("GABLE", 3.0, 0.6, "CF_Roof"),
      extras=["porch", "chimneys"], win=(1.2, 1.4), bay=2.4),
    T("mixed", "vancouver_special", [(11.0, 12.0)], [2], ["CF_Stucco", "CF_Siding"], ("GABLE", 1.4, 0.7, "CF_Roof"),
      balconies=True, win=(1.6, 1.3), bay=2.8, extras=["plinth"]),
    T("mixed", "foursquare", [(10.0, 10.0), (10.5, 10.5)], [2], ["CF_Siding", "CF_BrickPainted"], ("HIP", 2.4, 0.6, "CF_Roof"),
      extras=["porch", "chimneys"], win=(1.1, 1.5), bay=2.4),
    T("mixed", "ranch", [(13.0, 9.0), (12.0, 9.5)], [1], ["CF_Siding", "CF_Brick"], ("HIP", 1.6, 0.6, "CF_Roof"),
      win=(1.6, 1.3), bay=2.8),
    T("mixed", "west_coast", [(11.0, 10.0)], [2], ["CF_Cedar"], ("SHED", 2.2, 0.8, "CF_RoofSeam"), win=(1.8, 1.6), bay=3.0, frame="CF_Metal"),
]


def variants():
    """Every style x plan x storeys x wall material, in a stable order (the catalogue ids)."""
    out = []
    for st in STYLES:
        for plan, storeys, wall in itertools.product(st["plans"], st["storeys"], st["wall"]):
            spec = dict(st)
            spec.update(plan=plan, storeys=storeys, wall=wall)
            spec["floor_h"] = {"apartman": 2.8, "villa": 2.8, "machiya": 2.7, "hanok": 3.1}.get(st["kind"], 2.9)
            spec["id"] = "%s_%s_%d" % (st["culture"][:3], st["kind"], len([o for o in out if o["kind"] == st["kind"] and o["culture"] == st["culture"]]) + 1)
            out.append(spec)
    return out


def build_one(spec, lod):
    rk = spec["roof"][0]
    bt_spec = dict(spec)
    if rk not in ("GABLE", "HIP", "FLAT"): bt_spec["roof"] = ("NONE",) + tuple(spec["roof"][1:])
    obj, walls, top = shell(bt_spec, lod)
    extras = spec.get("extras", [])
    w, d = spec["plan"]
    fh = spec["floor_h"] + 0.22
    if "cumba" in extras:
        cw = min(3.6, w * 0.45)
        spec["hide_bays"] = lambda b, fl: fl >= 1 and b["n"].y < -0.95 and abs(b["c"].x) < cw / 2 + 0.2
    if "bay_window" in extras:
        bwx = w / 2 - 1.3 - 0.6
        spec["hide_bays"] = lambda b, fl: fl == 0 and b["n"].y < -0.95 and abs(b["c"].x - bwx) < 1.5
    if lod:
        bpy.ops.object.mode_set(mode="EDIT")
        bays = [b for b in split_into_bays(obj, walls, spec.get("bay", 3.0)) if b["z0"] + b["h"] <= top + 0.05]
        bpy.ops.object.mode_set(mode="OBJECT")
        hide = spec.get("hide_bays", lambda b, fl: False)
        ww, wh = spec.get("win", (1.2, 1.4))
        windows = [(b, (ww, wh), 0.15) for b in bays if b["w"] > ww + 0.3 and not hide(b, int(round((b["z0"] - 0.22) / fh)))]
        door = None
    else:
        windows, door, bays = facade(obj, spec, walls, top)
    bt_materials(obj, spec)
    m = Mesh()
    if lod: add_lod1_panes(m, windows)
    if "cumba" in extras: add_cumba(m, spec, lod)
    if "half_timber" in extras: add_half_timber(m, spec, lod, 1 if spec["storeys"] > 1 else 0)
    if "shutters" in extras: add_shutters(m, spec, windows, lod)
    if "chimneys" in extras: add_chimneys(m, spec, top, lod, 1)
    if "chimneys2" in extras: add_chimneys(m, spec, top, lod, 2)
    if "bay_window" in extras: add_bay_window(m, spec, lod)
    if "engawa" in extras: add_engawa(m, spec, lod)
    if "hisashi" in extras: add_hisashi(m, spec, -d / 2 - 0.9, fh - 0.2, lod)
    if "porch" in extras: add_porch(m, spec, lod)
    if "plinth" in extras: add_plinth(m, spec, "CF_Ashlar", 0.5)
    if "plinth_stone" in extras: add_plinth(m, spec, "CF_Ashlar", 0.7)
    if "plinth_low" in extras: add_plinth(m, spec, "CF_Concrete", 0.4)
    if "modern" in extras: add_modern(m, spec, top, lod)
    if "posts" in extras and not lod:
        for k in range(int(w / 2.6) + 1):
            x = -w / 2 + min(w, 2.6 * k)
            m.box(x - 0.12, -d / 2 - 0.12, 0.7, x + 0.12, -d / 2 + 0.12, top, "CF_TimberDark")
    if "steps" in extras and not lod: add_steps(m, spec, door, lod)
    if rk == "IRIMOYA": curved_roof(m, spec, top, 0.25, True)
    if rk == "HANOK": curved_roof(m, spec, top, 0.7, True)
    if rk == "MANSARD": mansard(m, spec, top, lod)
    if rk == "SHED":
        rh, ro = spec["roof"][1], spec["roof"][2]
        m.poly([(-w / 2 - ro, d / 2 + ro, top), (w / 2 + ro, d / 2 + ro, top), (w / 2 + ro, -d / 2 - ro, top + rh), (-w / 2 - ro, -d / 2 - ro, top + rh)][::-1], spec["roof"][3])
        m.poly([(-w / 2 - ro, d / 2 + ro, top - 0.15), (-w / 2 - ro, -d / 2 - ro, top + rh - 0.15), (w / 2 + ro, -d / 2 - ro, top + rh - 0.15), (w / 2 + ro, d / 2 + ro, top - 0.15)][::-1], "CF_TimberDark")
        for x in (-w / 2, w / 2):
            tri = [(x, d / 2, top), (x, -d / 2, top), (x, -d / 2, top + rh * (d / (d + 2 * ro)))]
            m.poly(tri if x > 0 else tri[::-1], spec["wall"], zb=0.0)
        m.poly([(-w / 2, -d / 2, top), (w / 2, -d / 2, top), (w / 2, -d / 2, top + rh * (d / (d + 2 * ro))), (-w / 2, -d / 2, top + rh * (d / (d + 2 * ro)))][::-1], spec["wall"], zb=0.0)
    if m.f:
        extra = to_object(m, "extras", LAZY, weld=True)
        bpy.context.scene.collection.objects.link(extra)
        bpy.ops.object.select_all(action="DESELECT")
        extra.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.join()
    # merge coplanar faces (bay cuts, window insets) without touching the silhouette or materials
    if not lod:
        dm = obj.modifiers.new("planar", "DECIMATE")
        dm.decimate_type = "DISSOLVE"
        dm.angle_limit = math.radians(0.5)
        dm.delimit = {"MATERIAL", "NORMAL"}
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=dm.name)
    # BT front is -Y: turn the house so its front faces +Y, and sit it on the ground
    obj.rotation_euler = (0, 0, math.pi)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    for a in [a for a in obj.data.attributes if a.name.startswith(".bt")]:
        try: obj.data.attributes.remove(a)
        except Exception: pass
    obj.data.uv_layers.clear() if hasattr(obj.data.uv_layers, "clear") else None
    zt = max(v.co.z for v in obj.data.vertices)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    door_local = None if door is None else (-door[0], -door[1] + 0.05, 0.0)
    return obj, dict(height=round(zt, 2), tris=tris, door=door_local)


def textured_preview():
    """Give the CF materials the baked library textures (box-projected) for the Blender catalogue."""
    lib = os.path.join(ROOT, "assets", "cityforge", "materials")
    names = {"CF_Stucco": "stucco", "CF_Siding": "siding", "CF_Brick": "brick_red", "CF_BrickLondon": "brick_london",
             "CF_BrickPainted": "brick_painted", "CF_Ashlar": "ashlar", "CF_Cedar": "cedar_planks", "CF_Yakisugi": "yakisugi",
             "CF_LightWood": "light_wood", "CF_Plaster": "stucco", "CF_Roof": "shingle_asphalt", "CF_RoofSlate": "slate",
             "CF_RoofTerracotta": "terracotta", "CF_RoofKawara": "kawara", "CF_RoofSeam": "standing_seam", "CF_Concrete": "concrete",
             "CF_Door": "light_wood", "CF_RoofFlat": "concrete"}
    for cf, tex in names.items():
        m = MATS.get(cf)
        if m is None or not os.path.exists(os.path.join(lib, tex + "_albedo.jpg")): continue
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

        def img(suffix, colour):
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = bpy.data.images.load(os.path.join(lib, tex + suffix), check_existing=True)
            n.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
            n.projection = "BOX"
            n.projection_blend = 0.15
            nt.links.new(mp.outputs[0], n.inputs["Vector"])
            return n
        a = img("_albedo.jpg", True)
        tint = bsdf.inputs["Base Color"].default_value[:]
        mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0 if cf in ("CF_Stucco", "CF_Siding", "CF_BrickPainted", "CF_Plaster", "CF_Roof", "CF_RoofSeam") else 0.0
        nt.links.new(a.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = tint
        nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
        o = img("_orm.jpg", False)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(o.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nn = img("_normal.png", False)
        nt.links.new(nn.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])


def export_glb(path, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_normals=True, export_texcoords=False)


def main():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    specs = [s for s in variants() if s["id"].startswith(ONLY)]
    catalogue, lod1_geo, objs = [], {}, []
    col = bpy.data.collections.new("HouseCatalogue")
    bpy.context.scene.collection.children.link(col)
    import time
    t0 = time.time()
    for k, spec in enumerate(specs):
        try:
            o0, info = build_one(dict(spec), 0)
            o0.name = "H_" + spec["id"]
            o1, info1 = build_one(dict(spec), 1)
            o1.name = "H_" + spec["id"] + "_LOD1"
        except Exception as e:
            import traceback; traceback.print_exc()
            print("HOUSE FAILED", spec["id"], e)
            for o in list(bpy.context.scene.collection.objects): bpy.data.objects.remove(o)
            continue
        for o in (o0, o1):
            for c in list(o.users_collection): c.objects.unlink(o)
            col.objects.link(o)
        objs += [o0, o1]
        me = o1.data
        lod1_geo[spec["id"]] = {"v": [[round(c, 3) for c in v.co] for v in me.vertices],
                                "f": [list(p.vertices) for p in me.polygons],
                                "m": [me.materials[p.material_index].name if me.materials else "CF_Trim" for p in me.polygons]}
        w, d = spec["plan"]
        catalogue.append({"id": spec["id"], "culture": spec["culture"], "kind": spec["kind"], "w": w, "d": d, "storeys": spec["storeys"],
                          "height": info["height"], "wall": spec["wall"], "roof": spec["roof"][3], "door": info["door"] or [0.0, d / 2 + 0.05, 0.0],
                          "tris": info["tris"], "tris_lod1": info1["tris"]})
        print("HOUSE %3d %-26s %5d tris (LOD1 %4d)  %.0fs" % (k, spec["id"], info["tris"], info1["tris"], time.time() - t0))
    for o in objs: o.location = (0, 0, 0)
    export_glb(os.path.join(OUT, "houses.glb"), objs)
    json.dump(catalogue, open(os.path.join(OUT, "houses.json"), "w"), indent=1)
    json.dump(lod1_geo, open(os.path.join(OUT, "houses_lod1.json"), "w"), separators=(",", ":"))
    # the catalogue laid out by culture, textured, for review in Blender
    rows = {}
    for o, c in zip(objs[0::2], catalogue):
        r = rows.setdefault(c["culture"], [])
        o.location = (len(r) * 16.0, -["turkish", "japanese", "korean", "european", "british", "mixed"].index(c["culture"]) * 22.0, 0)
        r.append(o)
    for o in objs[1::2]: o.hide_render = True; o.hide_set(True)
    textured_preview()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "tmp", "cityforge", "house_catalogue.blend"))
    print("CATALOGUE", len(catalogue), "types,", sum(c["tris"] for c in catalogue) // max(1, len(catalogue)), "tris average")


main()
