"""Convert the October 2026 interior packs (source_assets/incoming_2026_10_21/) into game-ready
props for the Cedar House interior and the restaurants, and strip the Cedar House placeholder
furniture that the new props replace.

Run headless (never on a live Blender session):
  blender --background --factory-startup --python tools/prepare_interiors.py -- \
      [--packs kitchen,sofa,tv,shelf,plants,trailer,bakery,foodbar,house] [--only id1,id2] [--no-qa]

Output:
  assets/interiors/<category>/<id>.glb   one prop per file (categories: kitchen, living, bedroom,
                                          bath, decor, plants, bakery, restaurant, exterior)
  assets/interiors/qa/<id>.png           three-quarter front render with a 1 m red reference stick
  assets/interiors/catalog.json          {"convention": ..., "props": [...]} (entries merged by id)
  world/cedar_house/assets/cedar_house.glb + collisions.json  (pack "house": the furniture the new
                                          props replace is removed; the originals stay in
                                          world/cedar_house/archive/)

Prop convention (same as tools/prepare_prop_packs.py):
  * metres, Blender Z up / Godot Y up; transforms applied; one mesh per prop, one surface per material.
  * origin = centre of the footprint on the floor (bbox centre in X/Y, lowest point at 0). Wall props
    (origin "back") have the origin at the centre of their back face, Z = 0 at the floor they were
    modelled above, so placing them at floor height against a wall reproduces the authored height.
  * FRONT faces Blender -Y = Godot +Z.
  * textures <= 1024 px (<= 512 px for small props); alpha cut-outs exported as glTF MASK.
  * node extras: prop_id, category, collision, size, source.
"""
import bpy, bmesh, sys, os, math, json, tempfile, time, shutil, random
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source_assets", "incoming_2026_10_21")
OUT = os.path.join(ROOT, "assets", "interiors")
QA = os.path.join(OUT, "qa")
CATALOG = os.path.join(OUT, "catalog.json")
HOUSE_DIR = os.path.join(ROOT, "world", "cedar_house")
TMP = tempfile.mkdtemp(prefix="interiors_")

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def _arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        return ARGS[i + 1] if i + 1 < len(ARGS) else default
    return default


ONLY = set(filter(None, (_arg("--only", "") or "").split(",")))
PACKS = set(filter(None, (_arg("--packs", "") or "").split(",")))
DO_QA = "--no-qa" not in ARGS

CONVENTION = {
    "units": "metres",
    "up": "Blender +Z / Godot +Y",
    "origin": "floor centre of the footprint; origin 'back' props: centre of the back face at floor level",
    "front": "front faces Blender -Y = Godot +Z",
    "size": "[x_width, y_height_up, z_depth] in Godot axes, metres",
    "mesh": "single static MeshInstance per prop, one surface per material, transforms applied",
    "alpha": "foliage uses alpha scissor (glTF MASK); glass uses alpha blend",
    "metadata": "glTF node extras on the prop node: prop_id, category, collision, size, source",
}


# ----------------------------------------------------------------------------- specs
def P(id, cat, nodes=None, size=1.0, front="-Y", budget=3000, tex=512, collision=False, origin="floor",
      region=None, use="", inside=None, post=None):
    """size: float = uniform scale, ("z", h) = scale to height h, ("max", w) = longest horizontal
    side w. region: callable(lo, hi) -> bool selecting loose parts of the baked pack."""
    return dict(id=id, cat=cat, nodes=nodes or [], size=size, front=front, budget=budget, tex=tex,
                collision=collision, origin=origin, region=region, use=use, inside=inside, post=post)


KITCHEN = [
    P("fridge", "kitchen", ["Fridge"], ("z", 1.80), budget=4000, tex=1024, collision=True),
    P("kitchen_range", "kitchen", ["Oven", "Stove"], ("z", 0.92), budget=5000, tex=1024, collision=True),
    P("dishwasher", "kitchen", ["Dishwasher"], ("z", 0.82), budget=3000, tex=1024, collision=True),
    P("coffee_machine", "kitchen", ["Coffee Machine"], ("z", 0.36), budget=1500, tex=512),
    P("airfryer", "kitchen", ["Airfryer"], ("z", 0.33), budget=2000),
    P("blender", "kitchen", ["Blender"], ("z", 0.40), budget=2000),
    P("toaster", "kitchen", ["Toaster"], ("z", 0.20), budget=1500),
    P("canisters", "kitchen", ["CeramicSiloCanister"], ("z", 0.24), budget=1500),
    P("spice_jars", "kitchen", ["SpiceJars"], ("z", 0.12), budget=1200),
    P("spice_grinder", "kitchen", ["SpiceGrinder"], ("z", 0.20), budget=800),
    P("tall_spice_bottles", "kitchen", ["TallSpiceBottles"], ("z", 0.17), budget=1200),
    P("almond_bottles", "kitchen", ["AlmondBottles"], ("z", 0.24), budget=1200),
    P("olive_oil_bottle", "kitchen", ["OliveBottle"], ("z", 0.30), budget=700),
    P("coffee_jar", "kitchen", ["VacuumCoffeJar"], ("z", 0.17), budget=800),
    P("utensil_holder", "kitchen", ["Utensils"], ("z", 0.34), budget=1800),
    P("paper_towel", "kitchen", ["Paper Towel"], ("z", 0.30), budget=800),
    P("detergent", "kitchen", ["Detergent"], ("z", 0.27), budget=800),
    P("sponge", "kitchen", ["Spoonge"], ("max", 0.11), budget=300),
    P("cutting_board", "kitchen", ["CuttingWood"], ("max", 0.42), budget=600),
    P("chef_knife", "kitchen", ["ChefKnife"], ("max", 0.31), budget=600),
    P("measuring_cups", "kitchen", ["MeasuringCups"], ("max", 0.28), budget=900),
    P("plate", "kitchen", ["Plate"], ("max", 0.27), budget=900),
    P("bowl", "kitchen", ["Bowl"], ("max", 0.17), budget=900),
    P("fruit_bowl", "kitchen", ["Fruit Bowl"], ("max", 0.32), budget=3000),
    P("wine_rack", "kitchen", ["WineBox"], ("z", 0.34), budget=2500),
    P("cookbook_pile", "kitchen", ["Cooking BookPile"], ("max", 0.32), budget=800),
    P("cookbook", "kitchen", ["CookingBook"], ("max", 0.27), budget=500),
    P("book_flat", "decor", ["Book3"], ("max", 0.36), budget=500),
    P("faux_succulent", "plants", ["FauxPlant"], ("z", 0.22), budget=1800),
    P("hanging_plant", "plants", ["Plant"], ("z", 0.60), budget=4000, post="hanger"),
]

# sofa_set.glb: SketchUp inches; one mesh per material across the whole set -> loose-part regions
# (source XY, inches). Sofa faces -Y, the wide armchair -X, the small armchair +X.
SOFA = [
    P("sofa", "living", size=0.0254, front="-Y", budget=3000, tex=512, collision=True,
      region=lambda c: -40 < c[0] < 40 and c[1] > -20),
    P("armchair_wide", "living", size=0.0254, front="-X", budget=2500, collision=True,
      region=lambda c: c[0] > 40 and c[1] < -20),
    P("armchair", "living", size=0.0254, front="+X", budget=2500, collision=True,
      region=lambda c: c[0] < -40 and c[1] < -20),
    P("coffee_table", "living", size=0.0254, budget=1500, collision=True,
      region=lambda c: -30 < c[0] < 30 and c[1] < -20),
    P("side_table_lamp", "living", size=0.0254, budget=2000, collision=True,
      region=lambda c: c[0] < -40 and c[1] > -20),
]

# tv_unit.glb: one composition against a wall (front -Y, wall at +Y); 1120 meshes, untextured.
TV_SCALE = 1.7


def tv_class(lo, hi, mats):
    c = (lo + hi) / 2
    s = hi - lo
    if 'tecido_malibu' in mats:
        return 'pouf'
    if s[2] > 1.0:
        return 'panel'      # slatted wall panel (not used)
    if c[0] < -0.44 and c[2] > 0.28:
        return 'mirror'     # round mirror + floating drawer console under it
    if c[2] > 0.9:
        return 'wallshelf'
    if -0.30 < c[0] < 0.34 and 0.36 < c[2] < 0.85:
        return 'tv'
    return 'console'


TV = [
    P("tv_console", "living", ["console"], TV_SCALE, budget=9000, collision=True),
    P("tv_screen", "living", ["tv"], TV_SCALE, budget=1500),
    P("wall_shelf_decor", "decor", ["wallshelf"], TV_SCALE, budget=4000, origin="back_keepz"),
    P("hall_mirror_console", "decor", ["mirror"], TV_SCALE, budget=2500, origin="back_keepz"),
    P("pouf", "living", ["pouf"], TV_SCALE, budget=5000, collision=True),
]

# decor_shelf.glb: four shelving units side by side (metres), split by X.
SHELF = [
    P("cube_shelf", "living", size=1.0, budget=3000, tex=1024, collision=True, region=lambda c: c[0] < -1.45),
    P("bookcase_staggered", "living", size=1.0, budget=3000, tex=1024, collision=True,
      region=lambda c: -1.45 <= c[0] < -0.1),
    P("sideboard", "living", size=1.0, budget=3000, tex=1024, collision=True, region=lambda c: -0.1 <= c[0] < 1.3),
    P("etagere", "living", size=1.0, budget=2500, tex=1024, collision=True, region=lambda c: c[0] >= 1.3),
]

PLANTS = [
    P("planter_box_a", "plants", ["Flower"], 0.6, budget=4000, tex=512),
    P("planter_box_b", "plants", ["Flower1"], 0.6, budget=4000, tex=512),
    P("planter_box_c", "plants", ["Flower5"], 0.6, budget=4000, tex=512),
    P("planter_trough_a", "plants", ["Flower2"], 0.6, budget=5000, tex=512),
    P("planter_trough_b", "plants", ["Flower3"], 0.6, budget=5000, tex=512),
    P("planter_trough_c", "plants", ["Flower4"], 0.6, budget=5000, tex=512),
]

F = 0.85  # trailer_park_props furniture is modelled ~18 % oversize
TRAILER = [
    P("bed_blue", "bedroom", ["Bed"], 0.78, front="+Y", collision=True, tex=512),
    P("bed_plaid", "bedroom", ["Bed_01"], F, front="+Y", collision=True, tex=512),
    P("bed_fur", "bedroom", ["Bed_02"], F, front="+Y", collision=True, tex=512),
    P("armchair_reading", "bedroom", ["Armchair"], F, front="-X", collision=True),
    P("chair_wood", "bedroom", ["Chair"], F, front="-X", collision=True),
    P("side_table_small", "bedroom", ["Table_02"], F, collision=True),
    P("lamp_table", "bedroom", ["Lamp"], ("z", 0.55)),
    P("lamp_table_b", "bedroom", ["Lamp_01"], ("z", 0.52)),
    P("alarm_clock", "bedroom", ["alarm_clock"], ("z", 0.14)),
    P("alarm_clock_b", "bedroom", ["alarm_clock_01"], ("z", 0.13)),
    P("radio", "bedroom", ["Radio_01"], ("z", 0.22)),
    P("clothes_rack", "bedroom", ["Clothings"], F),
    P("wall_clock", "decor", ["Clock"], ("z", 0.36), front="-X", origin="back"),
    P("book_stack", "decor", ["Books"], ("max", 0.30)),
    P("photo_frame", "decor", ["Photo_frame"], ("z", 0.18)),
    P("photo_frame_b", "decor", ["Photo_frame_01"], ("z", 0.18)),
    P("photo_frame_c", "decor", ["Photo_frame_02"], ("z", 0.18)),
    P("picture_frames_wall", "decor", ["Picture_frames", "Picture_frames_001", "Picture_frames_002",
                                       "Picture_frames_003", "Picture_frames_004", "Picture_frames_005",
                                       "Picture_frames_006"], 1.4, front="-X", origin="back"),
    P("vase_a", "decor", ["Vase"], ("z", 0.26)),
    P("vase_b", "decor", ["Vase_01"], ("z", 0.30)),
    P("vase_c", "decor", ["Vase_02"], ("z", 0.24)),
    P("vase_d", "decor", ["Vase_03"], ("z", 0.22)),
    P("vase_e", "decor", ["Vase_04"], ("z", 0.24)),
    P("flowers_vase", "decor", ["Flowers"], ("z", 0.50)),
    P("figurine", "decor", ["figurine"], ("z", 0.14)),
    P("potted_plant_floor", "plants", ["Plants"], ("z", 0.85), budget=1500),
    P("potted_plant_tall", "plants", ["Plants_01"], ("z", 1.05), budget=1500),
    P("cereal_box", "kitchen", ["Cereal"], ("z", 0.30)),
    P("coffee_can", "kitchen", ["Coffe"], ("z", 0.14)),
    P("mug", "kitchen", ["Cup"], ("z", 0.10)),
    P("mug_b", "kitchen", ["Cup_03"], ("z", 0.09)),
    P("dish_stack", "kitchen", ["Dishes_01"], ("max", 0.27)),
    P("casserole_pot", "kitchen", ["Casserole", "Casserole_T"], ("max", 0.30)),
    P("skillet", "kitchen", ["Skillet"], ("max", 0.45)),
    P("stewpot", "kitchen", ["stewpot", "stewpot_T"], ("max", 0.24)),
    P("cutlery_holder", "kitchen", ["cutlery_holder"], ("z", 0.22)),
    P("knife_block", "kitchen", ["knife _holder"], ("z", 0.24)),
    P("oil_bottles", "kitchen", ["olive_oil", "olive_oil_01"], ("z", 0.28)),
    P("spice_tins", "kitchen", ["Spices", "Spices_01", "Spices_02", "Spices_03"], ("z", 0.12)),
    P("cookware_rail", "kitchen", ["Cookware"], ("z", 0.50), front="+X", origin="back"),
    P("shampoo", "bath", ["Champoo"], ("z", 0.22)),
    P("shampoo_b", "bath", ["Champoo_01"], ("z", 0.21)),
    P("soap_bar", "bath", ["soap"], ("max", 0.09)),
    P("toothbrush_cup", "bath", ["vaso", "brush", "brush_01", "toothpaste_brush"], ("z", 0.17)),
    P("toilet_paper_holder", "bath", ["toilet_paper"], ("z", 0.16), front="+X", origin="back"),
    P("bin_small", "bath", ["trash_can"], ("z", 0.30)),
    P("watering_can", "exterior", ["Watering_can"], ("z", 0.25)),
    P("ac_unit", "exterior", ["air-conditioning.006"], ("z", 0.55), front="+X", origin="back"),
    P("fuse_box", "exterior", ["Fuse_box"], ("z", 0.50), origin="back"),
    P("garbage_bag", "exterior", ["Garbage_bag"], ("z", 0.55)),
    P("garbage_bag_b", "exterior", ["Garbage_bag_02"], ("z", 0.50)),
]

BAKE_SCALE = 0.0012
BAKERY = [P(n.replace("-", "_"), "bakery", [n], BAKE_SCALE, budget=1200, tex=512)
          for n in ["bread-1", "bread-2", "bread-3", "bread-4", "bread-roll-1", "bread-roll-2", "bread-roll-3",
                    "bread-roll-4", "pastry-1", "pastry-2", "pastry-3", "pastry-4"]]

FOODBAR = [
    # The café service counter of the Katydid food bar (display vitrine, register, grinder, food):
    # customers stand on its -X side in the source.
    P("food_bar_counter", "restaurant", size=0.29, front="-X", budget=9000, tex=1024, collision=True,
      region=lambda c: -0.4 < c[0] < 2.95 and -18.4 < c[1] < -0.85 and 11.3 < c[2] < 17.0,
      inside=(-0.4, 2.95, -18.4, -0.85, 11.3, 17.0)),
]


# ----------------------------------------------------------------------------- helpers
def log(*a):
    print("[interiors]", *a, flush=True)


def tris_of(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def world_pts(o):
    co = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(o.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def bounds(obj):
    p = world_pts(obj)
    return p.min(0), p.max(0)


def select_only(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def subtree(o):
    return [o] + list(o.children_recursive)


_img_cache = {}


def new_scene_state():
    _img_cache.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    new_scene_state()
    t0 = time.time()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    log("imported", os.path.basename(path), "in %.1fs" % (time.time() - t0))


def bake(src_objs, name):
    """World-space static copy of the meshes, joined into one object."""
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in src_objs:
        if o.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        if not me.polygons:
            bpy.data.meshes.remove(me)
            continue
        me.transform(o.matrix_world)
        n = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(n)
        parts.append(n)
    if not parts:
        raise RuntimeError("no meshes for " + name)
    if len(parts) > 1:
        for p in parts:
            if p.data.uv_layers:
                p.data.uv_layers[0].name = "UVMap"
        select_only(parts)
        bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    return obj


def islands(bm):
    bm.faces.ensure_lookup_table()
    seen = set()
    out = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]
        seen.add(f.index)
        comp = []
        while stack:
            x = stack.pop()
            comp.append(x)
            for v in x.verts:
                for g in v.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        out.append(comp)
    return out


def keep_parts(obj, test, with_mats=False):
    """Delete every loose part for which test(lo, hi[, material names]) is False.
    Returns the kept part count."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    names = [s.material.name if s.material else "" for s in obj.material_slots]
    kill = []
    kept = 0
    for comp in islands(bm):
        pts = np.array([tuple(v.co) for f in comp for v in f.verts])
        ok = test(pts.min(0), pts.max(0), {names[f.material_index] for f in comp} if names else set())             if with_mats else test(pts.min(0), pts.max(0))
        if ok:
            kept += 1
        else:
            kill += comp
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]  # wire edges / stray vertices of the source
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return kept


def weld(obj, dist):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(obj.data)
    bm.free()
    me = obj.data
    if me.has_custom_normals:
        select_only([obj])
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    try:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(35))
    except AttributeError:
        pass


def drop_unused_slots(obj):
    select_only([obj])
    try:
        bpy.ops.object.material_slot_remove_unused()
    except RuntimeError:
        pass


def part_split(obj, protect_tris=48, protect_size=0.3):
    """Per loose part: True = protected (simple or large flat part: boards, boxes, carcass panels)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    flags = []
    for comp in islands(bm):
        n = sum(len(f.verts) - 2 for f in comp)
        pts = np.array([tuple(v.co) for f in comp for v in f.verts])
        ext = float((pts.max(0) - pts.min(0)).max())
        flags.append(((ext >= protect_size and n <= 400) or (n <= protect_tris and ext >= 0.08), n))
    bm.free()
    return flags


def collapse(obj, budget):
    for _ in range(4):
        cur = tris_of(obj)
        if cur <= budget:
            break
        m = obj.modifiers.new("decimate", 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.use_collapse_triangulate = True
        m.ratio = max(0.005, budget / cur * 0.97)
        select_only([obj])
        bpy.ops.object.modifier_apply(modifier=m.name)


def decimate(obj, budget):
    """Collapse to the budget. Simple or large loose parts (boards, boxes, carcass panels) are split
    off and kept as they are, so thin carcasses never fold; only the dense decor/organic parts are
    collapsed. Falls back to collapsing everything if the protected parts alone are too heavy."""
    t = tris_of(obj)
    if t <= budget:
        return False
    flags = part_split(obj)
    light = sum(n for p, n in flags if p)
    heavy = t - light
    log("  decimate %s: %d tris, protected %d, dense %d" % (obj.name, t, light, heavy))
    if heavy > 0 and light < budget * 0.8 and light > 0:
        dense = obj.copy()
        dense.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(dense)
        for target, keep_protected in ((obj, True), (dense, False)):
            bm = bmesh.new()
            bm.from_mesh(target.data)
            kill = [f for (p, n), comp in zip(flags, islands(bm)) if p != keep_protected for f in comp]
            bmesh.ops.delete(bm, geom=kill, context='FACES')
            bm.to_mesh(target.data)
            bm.free()
        collapse(dense, budget - light)
        select_only([obj, dense], active=obj)
        bpy.ops.object.join()
    else:
        collapse(obj, budget)
    me = obj.data
    if me.has_custom_normals:
        select_only([obj])
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    try:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(40))
    except AttributeError:
        pass
    return True


def thin_foliage(obj, budget, leaf_mats):
    """Foliage packs (~150k tris of individual leaves a plant): drop whole leaves at random (every
    loose part of a leaf material) so that the kept leaves, collapsed to ~4 tris each, take about
    2/3 of the budget; pots, soil and stems are only decimated."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    rng = random.Random(7)
    comps = islands(bm)
    names = [s.material.name if s.material else "" for s in obj.material_slots]
    leaves = [c for c in comps if names[c[0].material_index] in leaf_mats]
    leaf_tris = sum(len(f.verts) - 2 for c in leaves for f in c)
    target = budget * 0.65
    per_leaf = leaf_tris / max(1, len(leaves))
    keep_n = int(min(len(leaves), target / max(4.0, min(per_leaf, 6.0))))
    log("  foliage: %d leaves, %.1f tris each, keeping %d" % (len(leaves), per_leaf, keep_n))
    rng.shuffle(leaves)
    # the kept leaves grow so the thinned plant keeps most of its foliage cover
    grow = min(2.2, max(1.0, (len(leaves) / max(1, keep_n)) ** 0.38))
    for c in leaves[:keep_n]:
        vs = {v for f in c for v in f.verts}
        centre = sum((v.co for v in vs), Vector()) / len(vs)
        for v in vs:
            v.co = centre + (v.co - centre) * grow
    kill = [f for c in leaves[keep_n:] for f in c]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return len(leaves), keep_n


def _pow2(n):
    return int(2 ** max(2, round(math.log2(max(n, 4)))))


def processed_image(img, max_px, keep_alpha, noncolor):
    key = (img.name, max_px, keep_alpha)
    if key in _img_cache:
        path = _img_cache[key]
    else:
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        s = min(1.0, max_px / max(w, h))
        tw, th = min(max_px, _pow2(w * s)), min(max_px, _pow2(h * s))
        tmp = bpy.data.images.new("tmp_resize", w, h, alpha=True, float_buffer=False)
        if noncolor:
            tmp.colorspace_settings.name = 'Non-Color'
        tmp.pixels.foreach_set(px)
        if (tw, th) != (w, h):
            tmp.scale(tw, th)
        ext = "png" if keep_alpha else "jpg"
        path = os.path.join(TMP, "%d.%s" % (len(_img_cache), ext))
        tmp.file_format = 'PNG' if keep_alpha else 'JPEG'
        if not keep_alpha:
            tmp.alpha_mode = 'NONE'
        try:
            tmp.save(filepath=path, quality=88)
        except TypeError:
            tmp.filepath_raw = path
            tmp.save()
        bpy.data.images.remove(tmp)
        _img_cache[key] = path
    new = bpy.data.images.load(path, check_existing=False)
    new.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    if not keep_alpha:
        new.alpha_mode = 'NONE'
    return new


def upstream_images(node, seen=None):
    seen = seen if seen is not None else set()
    out = []
    if node.name in seen:
        return out
    seen.add(node.name)
    if node.type == 'TEX_IMAGE' and node.image:
        out.append(node)
    for i in node.inputs:
        for l in i.links:
            out += upstream_images(l.from_node, seen)
    return out


def principled(mat):
    if not mat.node_tree:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)


def image_has_cutout(img):
    w, h = img.size
    if w * h == 0 or img.channels < 4:
        return False
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    a = px[3::4]
    return float((a < 0.5).mean()) > 0.002


def process_materials(obj, spec):
    """Per-prop material copies: textures resized (<= spec tex), alpha mode fixed for glTF."""
    info = []
    first_uv = obj.data.uv_layers[0].name if obj.data.uv_layers else None
    for si, slot in enumerate(obj.material_slots):
        src = slot.material
        if src is None:
            continue
        mat = src.copy()
        mat.name = "%s_%s" % (spec["id"], src.name)
        slot.material = mat
        if not mat.node_tree:
            continue
        bsdf = principled(mat)
        alpha_img_node = None
        mode = "OPAQUE"
        if bsdf is not None:
            a_in = bsdf.inputs["Alpha"]
            if a_in.is_linked:
                imgs = upstream_images(a_in.links[0].from_node)
                if imgs and image_has_cutout(imgs[0].image):
                    alpha_img_node = imgs[0]
                    mode = "MASK"
                elif imgs:
                    mat.node_tree.links.remove(a_in.links[0])
                    a_in.default_value = 1.0
            elif a_in.default_value < 0.999:
                mode = "BLEND"
        for n in list(mat.node_tree.nodes):
            if n.type != 'TEX_IMAGE' or n.image is None:
                continue
            vin = n.inputs["Vector"]
            if vin.is_linked:
                fn = vin.links[0].from_node
                if fn.type == 'UVMAP' and fn.uv_map and fn.uv_map != first_uv:
                    # Godot imports one UV set per material: drop maps on secondary UV sets
                    for l in list(n.outputs[0].links) + list(n.outputs[1].links):
                        if l.to_node.type in ('SEPARATE_COLOR', 'NORMAL_MAP'):
                            mat.node_tree.nodes.remove(l.to_node)
                    mat.node_tree.nodes.remove(n)
                    continue
            noncolor = n.image.colorspace_settings.name in ('Non-Color', 'Linear', 'Raw') or \
                n.image.colorspace_settings.is_data
            keep_alpha = alpha_img_node is not None and n.image == alpha_img_node.image
            n.image = processed_image(n.image, spec["tex"], keep_alpha, noncolor)
            n.image.name = "%s_%d" % (spec["id"], len(info))
            info.append("%dx%d" % tuple(n.image.size))
        if mode == "MASK" and bsdf is not None:
            nt = mat.node_tree
            link = bsdf.inputs["Alpha"].links[0]
            from_sock = link.from_socket
            nt.links.remove(link)
            lt = nt.nodes.new('ShaderNodeMath')
            lt.operation = 'LESS_THAN'
            lt.inputs[1].default_value = 0.5
            sub = nt.nodes.new('ShaderNodeMath')
            sub.operation = 'SUBTRACT'
            sub.inputs[0].default_value = 1.0
            nt.links.new(from_sock, lt.inputs[0])
            nt.links.new(lt.outputs[0], sub.inputs[1])
            nt.links.new(sub.outputs[0], bsdf.inputs["Alpha"])
            mat.surface_render_method = 'DITHERED'
        spec.setdefault("_alpha", []).append(mode)
    uvl = obj.data.uv_layers
    while len(uvl) > 1:
        uvl.remove(uvl[len(uvl) - 1])
    if len(uvl):
        uvl[0].active = True
        uvl[0].active_render = True
    return info


def merge_same_materials(obj):
    """Join material slots that share a base material (e.g. 'Wood.001' / 'Wood')."""
    me = obj.data
    names = [s.material.name if s.material else "" for s in obj.material_slots]
    first = {}
    remap = []
    for i, n in enumerate(names):
        base = n.split(".")[0]
        key = (base, s_key(obj.material_slots[i].material))
        if key not in first:
            first[key] = i
        remap.append(first[key])
    if len(set(remap)) == len(remap):
        return
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    idx = np.array(remap, np.int32)[idx]
    me.polygons.foreach_set("material_index", idx)
    used = sorted(set(remap))
    # drop unused slots from the end
    for i in reversed(range(len(obj.material_slots))):
        if i not in used:
            obj.active_material_index = i
            select_only([obj])
            bpy.ops.object.material_slot_remove()
    me.update()


def s_key(mat):
    """Materials that render the same (same image or same base colour)."""
    if mat is None or not mat.node_tree:
        return None
    b = principled(mat)
    imgs = tuple(sorted(n.image.name for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image))
    col = tuple(round(x, 3) for x in b.inputs["Base Color"].default_value) if b else None
    return (imgs, col if not imgs else None)


# ----------------------------------------------------------------------------- QA render
def render_qa(obj, pid, dims):
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_WORKBENCH'
    except TypeError:
        pass
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_backface_culling = False
    scene.render.resolution_x = scene.render.resolution_y = 384
    scene.world = scene.world or bpy.data.worlds.new("W")
    w, d, h = dims
    stick_me = bpy.data.meshes.new("ref")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.01 + 0.01 * max(w, h), radius2=0.01 + 0.01 * max(w, h), depth=1.0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.5))
    bm.to_mesh(stick_me)
    bm.free()
    stick = bpy.data.objects.new("ref", stick_me)
    stick.location = (-(w / 2 + max(0.06, 0.08 * max(w, h))), 0, 0)
    sm = bpy.data.materials.new("ref")
    sm.diffuse_color = (0.9, 0.05, 0.05, 1)
    stick_me.materials.append(sm)
    scene.collection.objects.link(stick)
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    hidden = [o for o in scene.objects if o not in (obj, cam, stick) and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    cam.data.type = 'ORTHO'
    span = max(w + abs(stick.location.x), d, h, 0.25)
    cam.data.ortho_scale = span * 1.35
    dirv = Vector((0.75, -1.4, 0.75)).normalized() * (50 + span * 4)
    target = Vector((-abs(stick.location.x) * 0.25, 0, max(h, 0.25) * 0.5))
    cam.location = target + dirv
    cam.rotation_euler = (-dirv).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = 1000
    scene.camera = cam
    scene.render.filepath = os.path.join(QA, pid + ".png")
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    for o in (cam, stick):
        bpy.data.objects.remove(o)


# ----------------------------------------------------------------------------- per-prop pipeline
FRONT_ROT = {"-Y": 0.0, "+Y": math.pi, "-X": math.pi / 2, "+X": -math.pi / 2}
RESULTS = []
KEEP = {}


def wanted(pid):
    return not ONLY or pid in ONLY


def finish_prop(obj, spec, source_name, src_tris, keep=False, foliage=None):
    """obj: baked world-space mesh in source units. Orient, scale, decimate, origin, export."""
    pid = spec["id"]
    t0 = time.time()
    lo, hi = bounds(obj)
    # centre in X/Y only: "back_keepz" props keep their height above the source floor (z = 0)
    c = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0.0))
    obj.data.transform(Matrix.Translation(-c))
    obj.data.transform(Matrix.Rotation(FRONT_ROT[spec["front"]], 4, 'Z'))
    lo, hi = bounds(obj)
    size = spec["size"]
    if isinstance(size, tuple):
        dims = hi - lo
        s = size[1] / (dims[2] if size[0] == "z" else max(dims[0], dims[1]))
    else:
        s = float(size)
    obj.data.transform(Matrix.Scale(s, 4))
    if spec.get("post") == "hanger":
        add_hanger(obj)
    if foliage:
        thin_foliage(obj, spec["budget"], foliage)
    decimated = decimate(obj, spec["budget"])
    drop_unused_slots(obj)
    merge_same_materials(obj)
    lo, hi = bounds(obj)
    if spec["origin"] == "back_keepz":
        obj.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -hi[1], 0.0)))
    elif spec["origin"] == "back":
        obj.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -hi[1], -lo[2])))
    else:
        obj.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    obj.data.update()
    lo, hi = bounds(obj)
    dims = hi - lo
    texinfo = process_materials(obj, spec)
    size_godot = [round(float(dims[0]), 3), round(float(dims[2]), 3), round(float(dims[1]), 3)]
    obj["prop_id"] = pid
    obj["category"] = spec["cat"]
    obj["collision"] = bool(spec["collision"])
    obj["size"] = size_godot
    obj["source"] = source_name
    os.makedirs(os.path.join(OUT, spec["cat"]), exist_ok=True)
    path = os.path.join(OUT, spec["cat"], pid + ".glb")
    select_only([obj])
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_image_format='AUTO', export_materials='EXPORT', export_cameras=False,
                              export_lights=False)
    t = tris_of(obj)
    entry = {"id": pid, "category": spec["cat"], "path": "res://assets/interiors/%s/%s.glb" % (spec["cat"], pid),
             "source": source_name, "size": size_godot, "bounds_min": [round(float(lo[0]), 3), round(float(lo[2]), 3), round(float(-hi[1]), 3)],
             "tris": t, "source_tris": src_tris, "materials": len(obj.material_slots),
             "textures": sorted(set(texinfo)), "kb": round(os.path.getsize(path) / 1024.0, 1),
             "collision": bool(spec["collision"]), "origin": spec["origin"]}
    RESULTS.append(entry)
    log("EXPORTED %-22s tris %6d (src %7d%s) size %s mats %d tex %s %.0f KB %.1fs" % (
        pid, t, src_tris, ", decimated" if decimated else "", size_godot, len(obj.material_slots),
        entry["textures"], entry["kb"], time.time() - t0))
    if DO_QA:
        os.makedirs(QA, exist_ok=True)
        render_qa(obj, pid, (float(dims[0]), float(dims[1]), float(dims[2])))
    if keep:
        KEEP[pid] = obj
        return obj
    me = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(me)
    return None


def nodes_objs(names):
    out = []
    for n in names:
        o = bpy.data.objects.get(n)
        if o is None:
            raise KeyError("node %r not found" % n)
        out += [x for x in subtree(o) if x.type == 'MESH']
    return out


def run_named(specs, glb, keep=False, foliage=None):
    todo = [s for s in specs if wanted(s["id"])]
    if not todo:
        return
    import_glb(os.path.join(SRC, glb))
    for s in todo:
        objs = nodes_objs(s["nodes"])
        obj = bake(objs, s["id"])
        finish_prop(obj, s, glb, tris_of(obj), keep=keep, foliage=foliage)


def run_regions(specs, glb, scale_hint=1.0):
    todo = [s for s in specs if wanted(s["id"])]
    if not todo:
        return
    import_glb(os.path.join(SRC, glb))
    all_mesh = [o for o in bpy.data.objects if o.type == 'MESH']
    whole = bake(all_mesh, "whole")
    for s in todo:
        obj = whole.copy()
        obj.data = whole.data.copy()
        bpy.context.scene.collection.objects.link(obj)
        obj.name = s["id"]
        box = s["inside"]
        n = keep_parts(obj, lambda lo, hi, f=s["region"], b=box: f((lo + hi) / 2) and (b is None or inside(lo, hi, b)))
        log("  %s: %d loose parts" % (s["id"], n))
        finish_prop(obj, s, glb, tris_of(obj))


def run_tv():
    todo = [s for s in TV if wanted(s["id"])]
    if not todo:
        return
    import_glb(os.path.join(SRC, "tv_unit.glb"))
    whole = bake([o for o in bpy.data.objects if o.type == 'MESH'], "whole")
    weld(whole, 0.0003)  # the source is polygon soup: weld so loose parts are whole objects
    for s in todo:
        obj = whole.copy()
        obj.data = whole.data.copy()
        bpy.context.scene.collection.objects.link(obj)
        obj.name = s["id"]
        n = keep_parts(obj, lambda lo, hi, mats, g=s["nodes"]: tv_class(lo, hi, mats) in g, with_mats=True)
        log("  %s: %d loose parts" % (s["id"], n))
        if s["id"] == "tv_screen":
            add_tv_stand(obj)
        finish_prop(obj, s, "tv_unit.glb", tris_of(obj))


def add_hanger(obj, drop=0.5):
    """Macrame hanger for the hanging plant: three jute cords from the pot rim to a ceiling ring."""
    lo, hi = bounds(obj)
    cx, cy, top = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2]
    r = min(hi[0] - lo[0], hi[1] - lo[1]) * 0.36
    apex = Vector((cx, cy, top + drop))
    bm = bmesh.new()
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        base = Vector((cx + math.cos(a) * r, cy + math.sin(a) * r, top - 0.06))
        d = apex - base
        mid = (apex + base) / 2
        rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=5, radius1=0.004, radius2=0.004, depth=d.length,
                              matrix=Matrix.Translation(mid) @ rot)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.012, radius2=0.012, depth=0.04,
                          matrix=Matrix.Translation(apex + Vector((0, 0, 0.02))))
    me = bpy.data.meshes.new("hanger")
    bm.to_mesh(me)
    bm.free()
    h = bpy.data.objects.new("hanger", me)
    bpy.context.scene.collection.objects.link(h)
    me.materials.append(simple_mat("Jute", (0.42, 0.33, 0.2), 0.9))
    if obj.data.uv_layers:
        me.uv_layers.new(name=obj.data.uv_layers[0].name)
    select_only([obj, h], active=obj)
    bpy.ops.object.join()


def add_tv_stand(obj):
    """The source TV is wall mounted; give it a pedestal foot so it can stand on a console."""
    lo, hi = bounds(obj)
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    bm = bmesh.new()
    foot_z = lo[2] - 0.035   # source units (TV scale 1.7): ~6 cm neck under the panel
    # neck
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((cx, cy + 0.004, (lo[2] + foot_z) / 2 + 0.01)) @
                          Matrix.Diagonal((0.035, 0.012, lo[2] - foot_z + 0.02, 1)))
    # base plate
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((cx, cy - 0.01, foot_z + 0.003)) @
                          Matrix.Diagonal((0.17, 0.09, 0.006, 1)))
    me = bpy.data.meshes.new("stand")
    bm.to_mesh(me)
    bm.free()
    stand = bpy.data.objects.new("stand", me)
    bpy.context.scene.collection.objects.link(stand)
    mat = bpy.data.materials.new("TvStandMetal")
    mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
    b.inputs["Metallic"].default_value = 0.7
    b.inputs["Roughness"].default_value = 0.35
    me.materials.append(mat)
    if obj.data.uv_layers and not me.uv_layers:
        me.uv_layers.new(name=obj.data.uv_layers[0].name)
    select_only([obj, stand], active=obj)
    bpy.ops.object.join()


# ----------------------------------------------------------------------------- bakery assemblies
def simple_mat(name, rgb, rough=0.7, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return mat


def basket_mesh(rx, ry, h, rim=0.012, segs=28):
    """Oval wicker bread basket: tapered open shell with a rolled rim and thickness."""
    bm = bmesh.new()
    rings = [(0.0, 0.78), (h * 0.35, 0.9), (h, 1.0)]
    vs = []
    for z, k in rings:
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new((math.cos(a) * rx * k, math.sin(a) * ry * k, z)))
        vs.append(ring)
    for r in range(len(vs) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((vs[r][i], vs[r][j], vs[r + 1][j], vs[r + 1][i]))
    bm.faces.new(list(reversed(vs[0])))
    # rim torus-ish band
    top = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        top.append(bm.verts.new((math.cos(a) * (rx + rim), math.sin(a) * (ry + rim), h + rim * 0.6)))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((vs[-1][i], vs[-1][j], top[j], top[i]))
    me = bpy.data.meshes.new("basket")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("basket", me)
    bpy.context.scene.collection.objects.link(o)
    m = o.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = 0.006
    select_only([o])
    bpy.ops.object.modifier_apply(modifier=m.name)
    # simple cylindrical UVs so the object joins cleanly with the textured breads
    me.uv_layers.new(name="UVMap")
    me.materials.append(simple_mat("Wicker", (0.33, 0.19, 0.07), 0.85))
    # linen napkin on the floor of the basket
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=segs, radius=1.0)
    for v in bm.verts:
        v.co.x *= rx * 0.86
        v.co.y *= ry * 0.86
        v.co.z = 0.012
    nme = bpy.data.meshes.new("napkin")
    bm.to_mesh(nme)
    bm.free()
    n = bpy.data.objects.new("napkin", nme)
    bpy.context.scene.collection.objects.link(n)
    nme.uv_layers.new(name="UVMap")
    nme.materials.append(simple_mat("Linen", (0.8, 0.74, 0.62), 0.9))
    select_only([o, n], active=o)
    bpy.ops.object.join()
    return o


def tray_mesh(w, d, h=0.022, wood=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, h * 0.25)) @ Matrix.Diagonal((w, d, h * 0.5, 1)))
    for sx, sy, ww, dd in ((0, d / 2, w, 0.008), (0, -d / 2, w, 0.008), (w / 2, 0, 0.008, d), (-w / 2, 0, 0.008, d)):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((sx, sy, h * 0.5)) @ Matrix.Diagonal((ww, dd, h, 1)))
    me = bpy.data.meshes.new("tray")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("tray", me)
    bpy.context.scene.collection.objects.link(o)
    me.uv_layers.new(name="UVMap")
    if wood:
        me.materials.append(simple_mat("TrayWood", (0.36, 0.2, 0.09), 0.6))
    else:
        me.materials.append(simple_mat("TraySteel", (0.55, 0.55, 0.56), 0.35, 0.85))
    return o


def place_copy(pid, x, y, z, yaw=0.0, tilt=0.0):
    src = KEEP[pid]
    o = src.copy()
    o.data = src.data.copy()
    bpy.context.scene.collection.objects.link(o)
    o.matrix_world = Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'X')
    return o


def assemble(pid, cat, parts, base=None):
    objs = ([base] if base else []) + parts
    for o in objs:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
        o.data.uv_layers[0].name = "UVMap"
    select_only(objs, active=objs[0])
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    obj = objs[0]
    obj.name = pid
    spec = P(pid, cat, size=1.0, budget=100000, tex=512)
    spec["_assembled"] = True
    # finish_prop re-centres and exports; materials were already processed on the parts
    finish_assembly(obj, spec)


def finish_assembly(obj, spec):
    pid = spec["id"]
    lo, hi = bounds(obj)
    obj.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    obj.data.update()
    lo, hi = bounds(obj)
    dims = hi - lo
    size_godot = [round(float(dims[0]), 3), round(float(dims[2]), 3), round(float(dims[1]), 3)]
    obj["prop_id"] = pid
    obj["category"] = spec["cat"]
    obj["collision"] = False
    obj["size"] = size_godot
    obj["source"] = "baked_goods.glb (assembled)"
    os.makedirs(os.path.join(OUT, spec["cat"]), exist_ok=True)
    path = os.path.join(OUT, spec["cat"], pid + ".glb")
    select_only([obj])
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_image_format='AUTO', export_materials='EXPORT', export_cameras=False,
                              export_lights=False)
    entry = {"id": pid, "category": spec["cat"], "path": "res://assets/interiors/%s/%s.glb" % (spec["cat"], pid),
             "source": "baked_goods.glb (assembled)", "size": size_godot, "tris": tris_of(obj),
             "materials": len(obj.material_slots), "kb": round(os.path.getsize(path) / 1024.0, 1),
             "collision": False, "origin": "floor"}
    RESULTS.append(entry)
    log("ASSEMBLED %-20s tris %6d size %s mats %d %.0f KB" % (pid, entry["tris"], size_godot,
                                                              entry["materials"], entry["kb"]))
    if DO_QA:
        render_qa(obj, pid, (float(dims[0]), float(dims[1]), float(dims[2])))
    bpy.data.objects.remove(obj)


def footprint(pid):
    lo, hi = bounds(KEEP[pid])
    return hi - lo


def run_bakery():
    todo = [s for s in BAKERY if wanted(s["id"])]
    if todo:
        run_named(BAKERY, "baked_goods.glb", keep=True)
    if not ONLY and len(KEEP) == len(BAKERY):
        rolls = ["bread_roll_1", "bread_roll_2", "bread_roll_3", "bread_roll_4"]
        loaves = ["bread_1", "bread_2", "bread_3", "bread_4"]
        pastries = ["pastry_1", "pastry_2", "pastry_3", "pastry_4"]
        rng = random.Random(3)
        # bread basket: loaf lying across the back, rolls in front
        b = basket_mesh(0.17, 0.12, 0.085)
        parts = [place_copy("bread_3", 0.0, 0.035, 0.03, yaw=math.pi / 2 + 0.15, tilt=0.12)]
        for i, (x, y) in enumerate(((-0.08, -0.04), (0.0, -0.06), (0.08, -0.035), (-0.03, 0.02))):
            parts.append(place_copy(rolls[i % 4], x, y, 0.035 + (0.02 if i == 3 else 0.0), yaw=rng.uniform(0, 6.28)))
        assemble("bread_basket", "bakery", parts, b)
        # bakery display trays (0.40 x 0.30): loaves, rolls, mixed pastries
        t = tray_mesh(0.42, 0.30, wood=True)
        parts = [place_copy(loaves[i], -0.14 + i * 0.095, 0.0, 0.012, yaw=math.pi / 2 * 0 + rng.uniform(-0.08, 0.08))
                 for i in range(3)]
        assemble("tray_breads", "bakery", parts, t)
        t = tray_mesh(0.42, 0.30)
        parts = []
        for i in range(8):
            parts.append(place_copy(rolls[i % 4], -0.15 + (i % 4) * 0.1, -0.065 + (i // 4) * 0.13, 0.012,
                                    yaw=rng.uniform(0, 6.28)))
        assemble("tray_rolls", "bakery", parts, t)
        t = tray_mesh(0.42, 0.30)
        parts = []
        for i in range(6):
            parts.append(place_copy(pastries[i % 4], -0.13 + (i % 3) * 0.13, -0.07 + (i // 3) * 0.14, 0.012,
                                    yaw=rng.uniform(-0.4, 0.4) + (math.pi if i % 2 else 0)))
        assemble("tray_pastries", "bakery", parts, t)
        t = tray_mesh(0.42, 0.30)
        parts = []
        for i in range(9):
            parts.append(place_copy(pastries[3] if i % 2 == 0 else pastries[2], -0.14 + (i % 3) * 0.14,
                                    -0.09 + (i // 3) * 0.09, 0.012, yaw=rng.uniform(0, 6.28)))
        assemble("tray_cookies", "bakery", parts, t)


# ----------------------------------------------------------------------------- Cedar House
# Placeholder furniture of the original build that the new props replace (house coordinates,
# Blender axes): x0, x1, y0, y1, z0, z1. A loose part is removed when its bounding box lies
# inside one of these boxes; parts inside KEEP_BOXES always stay.
REMOVE_BOXES = {
    "sofa": (-3.40, -0.60, -5.05, -3.95, 0.76, 1.85),
    "coffee_table": (-2.70, -1.30, -3.40, -2.60, 0.70, 1.35),   # legs stand on the floor (z 0.73)
    "bookcase": (-0.60, -0.02, -2.05, -0.85, 0.70, 2.55),
    "range": (-3.90, -3.00, 3.00, 3.86, 0.70, 1.82),
    "refrigerator": (-3.90, -2.88, -0.10, 0.80, 0.70, 2.72),
    "cabinet_for_dishwasher": (-2.32, -1.58, 4.50, 5.30, 0.70, 1.58),
    "fruit_bowl": (-1.45, -0.95, 1.40, 1.90, 1.52, 1.80),
    "bed_1": (2.12, 3.78, -3.90, -1.74, 0.74, 1.92),
    "bed_2": (2.12, 3.78, 0.85, 3.00, 0.74, 1.92),
}
KEEP_BOXES = [(2.18, 2.46, -2.04, -1.76, 1.25, 1.56), (2.19, 2.47, 2.74, 3.02, 1.25, 1.56)]  # bedside lamps
REMOVE_COLLISIONS = ["Sofa base", "Coffee table", "Bookcase", "Range", "Refrigerator", "Bed frame"]


def inside(lo, hi, b, pad=0.0):
    return (lo[0] >= b[0] - pad and hi[0] <= b[1] + pad and lo[1] >= b[2] - pad and hi[1] <= b[3] + pad
            and lo[2] >= b[4] - pad and hi[2] <= b[5] + pad)


def run_house():
    if ONLY:
        return
    arch = os.path.join(HOUSE_DIR, "archive")
    os.makedirs(arch, exist_ok=True)
    with open(os.path.join(arch, ".gdignore"), "w") as f:
        f.write("")
    orig_glb = os.path.join(arch, "cedar_house_v1.glb")
    orig_col = os.path.join(arch, "collisions_v1.json")
    if not os.path.isfile(orig_glb):
        shutil.copy2(os.path.join(HOUSE_DIR, "assets", "cedar_house.glb"), orig_glb)
    if not os.path.isfile(orig_col):
        shutil.copy2(os.path.join(HOUSE_DIR, "assets", "collisions.json"), orig_col)
    import_glb(orig_glb)
    removed = {k: 0 for k in REMOVE_BOXES}
    before = sum(tris_of(o) for o in bpy.data.objects if o.type == 'MESH')
    for o in list(bpy.data.objects):
        if o.type != 'MESH' or not o.name.startswith("Furniture__"):
            continue
        m = o.matrix_world.copy()

        def test(lo, hi, m=m):
            p = np.array([tuple(m @ Vector(lo)), tuple(m @ Vector(hi))])
            l, h = p.min(0), p.max(0)
            if any(inside(l, h, k, 0.002) for k in KEEP_BOXES):
                return True
            for name, b in REMOVE_BOXES.items():
                if inside(l, h, b):
                    removed[name] += 1
                    return False
            return True
        keep_parts(o, test)
        if not o.data.polygons:
            log("  %s is empty after the strip: removed" % o.name)
            bpy.data.objects.remove(o)
    after = sum(tris_of(o) for o in bpy.data.objects if o.type == 'MESH')
    log("house furniture parts removed:", removed, "tris %d -> %d" % (before, after))
    bpy.ops.export_scene.gltf(filepath=os.path.join(HOUSE_DIR, "assets", "cedar_house.glb"), export_format='GLB',
                              use_selection=False, export_extras=True, export_yup=True, export_apply=True,
                              export_animations=False, export_cameras=False, export_lights=False)
    with open(orig_col) as f:
        col = json.load(f)
    kept = [c for c in col if c["name"] not in REMOVE_COLLISIONS]
    target = os.path.join(HOUSE_DIR, "assets", "collisions.json")
    current = json.load(open(target)) if os.path.isfile(target) else None
    if current != kept:
        with open(target, "w") as f:
            json.dump(kept, f)
    log("collisions %d -> %d" % (len(col), len(kept)))


# ----------------------------------------------------------------------------- catalog
def write_catalog():
    if not RESULTS:
        return
    old = []
    if os.path.isfile(CATALOG):
        try:
            with open(CATALOG) as f:
                old = json.load(f).get("props", [])
        except (ValueError, OSError):
            old = []
    new_ids = {e["id"] for e in RESULTS}
    props = [e for e in old if e["id"] not in new_ids] + RESULTS
    props.sort(key=lambda e: (e["category"], e["id"]))
    with open(CATALOG, "w") as f:
        json.dump({"convention": CONVENTION, "props": props}, f, indent=1)
    log("catalog:", len(props), "props ->", CATALOG)


def main():
    def pack(name):
        return not PACKS or name in PACKS

    os.makedirs(QA, exist_ok=True)
    with open(os.path.join(QA, ".gdignore"), "w") as f:
        f.write("")
    if pack("kitchen"):
        run_named(KITCHEN, "kitchen_decor_pack.glb")
    if pack("sofa"):
        run_regions(SOFA, "sofa_set.glb")
    if pack("tv"):
        run_tv()
    if pack("shelf"):
        run_regions(SHELF, "decor_shelf.glb")
    if pack("plants"):
        run_named(PLANTS, "stylized_plant_pots_set__3dmodel_fbx__textures.glb",
                  foliage={"Material.004", "Material.013", "Material.017"})
    if pack("trailer"):
        run_named(TRAILER, "trailer_park_props.glb")
    if pack("foodbar"):
        run_regions(FOODBAR, "food_bar.glb")
    if pack("bakery"):
        run_bakery()
    if pack("house"):
        run_house()
    write_catalog()


main()
