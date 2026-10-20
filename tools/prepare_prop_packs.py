"""Convert the downloaded prop packs (Sketchfab GLBs in sketchup_assets/ plus the house-plants
.blend) into game-ready single-prop GLBs for Godot.

Run headless (never on a live Blender session):
  blender --background --factory-startup --python tools/prepare_prop_packs.py -- \
      [--house-plants <path to Sketchfab_2023_04_19_23_25_22.blend>] \
      [--packs street,road,plants,restaurant,geranium,potted,house] [--only id1,id2] [--no-qa]

The house-plants pack is C:/Users/<user>/Downloads/house-plants.zip; extract it into its own empty
folder outside the project and pass the source/*.blend with --house-plants. Its objects are
appended with bpy.data.libraries.load (the .blend is never opened as the main file and no
scripts are run). Without --house-plants that pack is skipped and its catalog entries are kept.

Output (one prop per file):
  assets/sketchup/props/<category>/<id>.glb   categories: street, road, plants, restaurant
  assets/sketchup/props/qa/<id>.png           front three-quarter workbench render (texture colour)
  assets/sketchup/props/catalog.json          {"convention": ..., "props": [...]} (entries merged by id)

Prop convention (also written to catalog.json):
  * metres, Z up in Blender / Y up in Godot; all transforms, modifiers and armatures applied;
    a single static mesh object per prop (one surface per material).
  * origin = centre of the footprint on the ground: bbox centre in X/Y, min Z = 0.
  * FRONT (sign face, bench seat, post-box slot, lamp arm reaching over the road) faces Blender -Y.
    The glTF exporter maps Blender +Y forward to Godot -Z, so the front faces Godot +Z
    (the default Node3D "back" axis, i.e. what a camera looking down -Z sees).
  * triangle budgets: small props <= 3000, plants <= 4000, lights / signs / traffic light <= 5000.
  * textures <= 1024 px (<= 512 px for small props); PBR maps kept; atlas textures are cropped to the
    UV island bounds of the prop; foliage alpha is exported as glTF alphaMode MASK (Godot alpha scissor),
    glass stays BLEND.
  * node extras (Godot metadata): prop_id, category, collision, suggested_use, source.
"""
import bpy, bmesh, sys, os, math, json, tempfile, time
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sketchup_assets")
OUT = os.path.join(ROOT, "assets", "sketchup", "props")
QA = os.path.join(OUT, "qa")
CATALOG = os.path.join(OUT, "catalog.json")
TMP = tempfile.mkdtemp(prefix="prop_packs_")

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def _arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        return ARGS[i + 1] if i + 1 < len(ARGS) else default
    return default


HOUSE_BLEND = _arg("--house-plants")
ONLY = set(filter(None, (_arg("--only", "") or "").split(",")))
PACKS = set(filter(None, (_arg("--packs", "") or "").split(",")))
DO_QA = "--no-qa" not in ARGS

BUDGET = {"small": 3000, "plant": 4000, "large": 5000}

CONVENTION = {
    "units": "metres",
    "up": "Blender +Z / Godot +Y",
    "origin": "centre of the footprint on the ground (bbox centre in the horizontal plane, lowest point at 0)",
    "front": "front (sign face, bench seat, post-box slot, lamp arm over the road) faces Blender -Y = Godot +Z",
    "size": "[x_width, y_height_up, z_depth] in Godot axes, metres",
    "mesh": "single static MeshInstance per prop, one surface per material, transforms applied",
    "alpha": "foliage uses alpha scissor (glTF MASK, cutoff 0.5); glass uses alpha blend",
    "metadata": "glTF node extras on the prop node: prop_id, category, collision, suggested_use, source",
    "collision": "true = give it a static collider (box/cylinder from size); false = decorative, no collider",
}

# ----------------------------------------------------------------------------- prop specs
# Each spec: id, cat, nodes (source node names; whole subtrees unless direct=True), front (source
# direction that is the prop's front: -Y, +Y, -X, +X), scale, budget, tex, collision, use,
# cut (remove geometry below source z=0, e.g. buried sign posts), stand (rotate a flat-lying
# object upright: its +Z face becomes the front).


def P(id, cat, nodes, use, collision, front="-Y", scale=1.0, budget="small", tex=512, cut=False,
      direct=False, stand=False, drop=None):
    return dict(id=id, cat=cat, nodes=nodes, use=use, collision=collision, front=front, scale=scale,
                budget=budget, tex=tex, cut=cut, direct=direct, stand=stand, drop=drop or [])


STREET = [
    P("bench_wood", "street", ["Wood Bench_36", "Bench Support_37"], "sidewalk bench", True, front="+X"),
    P("wheelie_bin_green", "street", ["Body.002_16", "Lid.008_18", "Grey Handle.005_19", "Wheels.002_17"],
      "kerb-side wheelie bin", True, front="+X"),
    P("wheelie_bin_blue", "street", ["Body_8", "Lid.006_10", "Grey Handle.003_11", "Wheels_9"],
      "kerb-side wheelie bin", True, front="+X"),
    P("dumpster_large", "street", ["Big Bin Body_38", "Big Bin Lid Right_39"], "alley / restaurant back-door dumpster",
      True, front="+X"),
    P("litter_bin_green", "street", ["Red Trash Can.003_43"], "sidewalk litter bin", True),
    P("litter_bin_red", "street", ["Red Trash Can.004_44"], "sidewalk litter bin", True),
    P("bollard_metal", "street", ["Metal Bolard_20"], "pedestrian bollard", True),
    P("bollard_concrete", "street", ["Cement Bolard_22"], "pedestrian bollard", True),
    P("bollard_yellow", "street", ["Yellow Bolard_21"], "parking bollard", True),
    P("fire_hydrant", "street", ["Fire Hydrant_52"], "kerb-side fire hydrant", True),
    P("post_box_red", "street", ["Post Box_55"], "sidewalk post box", True, front="+X"),
    P("path_lamp", "street", ["Street Light_54"], "park / footpath lamp", True, front="+X", budget="large", tex=1024),
    P("cardboard_box_small", "street", ["Box 1_23"], "delivery parcel", False),
    P("cardboard_box_medium", "street", ["Box 3_24"], "delivery parcel", False),
    P("cardboard_box_large", "street", ["Box 4_25"], "delivery parcel", True),
    P("cardboard_box_handles", "street", ["Box2_26"], "delivery parcel", False),
    P("trash_bag", "street", ["Bag 5_31"], "kerb-side rubbish bag", False),
    P("concrete_barrier", "road", ["Concrete Barrier_53"], "road-works / lane barrier", True, front="+X"),
    P("traffic_cone", "road", ["Cone 2_46"], "road-works cone", True),
    P("traffic_cone_small", "road", ["Cone_45"], "road-works cone", False),
    P("delineator_post", "road", ["Delineator Post_51"], "lane delineator post", True),
]


def SIGN(id, group, use):
    return P(id, "road", [group], use, True, front="-X", budget="large", tex=512, cut=True, direct=True)


ROAD = [
    P("street_light", "road", ["StreetLampSingle"], "kerb-side street light", True, budget="large", tex=1024),
    P("street_light_double", "road", ["StreetLampDouble"], "median street light", True, budget="large", tex=1024),
    P("traffic_light", "road", ["Traffic Light"], "junction traffic light (static prop)", True, budget="large",
      tex=1024),
    P("water_barrier_orange", "road", ["PVCBarriersA"], "road-works water barrier", True),
    P("water_barrier_white", "road", ["PVCBarriersB"], "road-works water barrier", True),
    P("guardrail_2m", "road", ["Railing2m"], "roadside guardrail segment", True, cut=True),
    P("guardrail_double_2m", "road", ["RailingDouble2M"], "roadside guardrail segment", True, cut=True),
    P("guardrail_end", "road", ["Railing_StartCap"], "guardrail end piece", True, cut=True),
    SIGN("sign_stop", "Rambu Prohibition_A1", "junction stop sign"),
    SIGN("sign_give_way", "Rambu Prohibition_A2", "junction give-way sign"),
    SIGN("sign_no_entry", "Rambu Prohibition_A5", "one-way street end sign"),
    SIGN("sign_no_vehicles", "Rambu Prohibition_A8", "pedestrian zone sign"),
    SIGN("sign_no_u_turn", "Rambu Prohibition_C14", "junction sign"),
    SIGN("sign_no_right_turn", "Rambu Prohibition_C16", "junction sign"),
    SIGN("sign_speed_limit_50", "Rambu Prohibition_D3", "speed limit sign"),
    SIGN("sign_parking", "FacilitiesAndUtilities_A15", "parking area sign"),
    SIGN("sign_pedestrian_crossing", "FacilitiesAndUtilities_A14", "zebra crossing sign"),
    SIGN("sign_bus_stop", "FacilitiesAndUtilities_A12", "bus stop sign"),
    SIGN("sign_hospital", "FacilitiesAndUtilities_B9", "hospital direction sign"),
    SIGN("sign_restaurant", "FacilitiesAndUtilities_C6", "restaurant sign"),
    SIGN("sign_one_way", "FacilitiesAndUtilities_D7", "one-way street sign"),
    SIGN("sign_roundabout", "CommandSigns_A6", "roundabout sign"),
    SIGN("sign_ahead_only", "CommandSigns_A5", "junction sign"),
    SIGN("sign_warning_traffic_lights", "Rambu Warning_D13", "warning sign before lights"),
    SIGN("sign_warning_crossroad", "Rambu Warning_D15", "warning sign before junction"),
    SIGN("sign_warning_pedestrians", "Rambu Warning_A15", "warning sign near crossing"),
    SIGN("sign_warning_children", "Rambu Warning_A5", "school zone sign"),
    SIGN("sign_warning_winding_road", "Rambu Warning_E13", "warning sign before bends"),
]

# low_poly_plants_pack: every top-level node is assigned to the nearest pot (anchor) in XY.
LOWPOLY_PLANTS = [
    ("plant_lp_a", ["Cylinder", "Cylinder.001"]),
    ("plant_lp_b", ["Cylinder.002", "Cylinder.003"]),
    ("plant_lp_c", ["Cylinder.004", "Cylinder.005"]),
    ("plant_lp_d", ["Cylinder.006", "Cylinder.007"]),
    ("plant_lp_e", ["Cylinder.008", "Cylinder.009"]),
    ("plant_lp_f", ["Cylinder.010", "Cylinder.011"]),
]
LOWPOLY_NAMES = {  # anchor id -> (final id, use, collision[, scale]), identified from the QA renders
    "plant_lp_a": ("potted_snake_plant", "doorstep plant", False),
    "plant_lp_b": ("potted_spider_plant", "windowsill / doorstep plant", False, 0.6),
    "plant_lp_c": ("potted_pothos", "doorstep plant", False),
    "plant_lp_d": ("planter_haworthia", "doorstep planter", False, 0.6),
    "plant_lp_e": ("potted_palm", "doorstep plant", False),
    "plant_lp_f": ("potted_fern", "doorstep plant", False),
}

GERANIUM = [
    P("planter_geranium_red", "plants", ["Geranium05_0", "Pots_3_3"], "doorstep plant", False, budget="plant", tex=1024),
    P("planter_geranium_orange", "plants", ["Geranium_01_6", "Pots_2_2"], "doorstep plant", False, budget="plant", tex=1024),
    P("planter_geranium_pink", "plants", ["Geranium_02_7", "Pots_1_1"], "doorstep plant", False, budget="plant", tex=1024),
    P("planter_geranium_purple", "plants", ["Geranium_03_8", "Pots_4_4"], "doorstep plant", False, budget="plant", tex=1024),
    P("planter_geranium_bowl", "plants", ["Geranium_04_9", "Pots_5_5"], "doorstep plant", False, budget="plant", tex=1024),
]

POTTED = [
    P("planter_grass_round", "plants", ["Pot"], "shop-front planter", False, budget="plant", tex=1024),
    P("planter_bamboo_round", "plants", ["Pot_10"], "shop-front planter", False, budget="plant", tex=1024),
    P("planter_grass_square", "plants", ["Pot_12"], "shop-front planter", False, budget="plant", tex=1024),
    P("planter_box_grass", "plants", ["Pot_3"], "sidewalk planter box", True, budget="plant", tex=1024),
    P("planter_bamboo_square", "plants", ["Pot_4"], "shop-front planter", False, budget="plant", tex=1024),
]

HOUSE = [
    P("potted_aloe", "plants", ["Aloe_Vera_A", "Vase_B", "Vase_B_Dirt"], "windowsill / doorstep plant", False,
      budget="plant", tex=512),
    P("potted_cactus", "plants", ["Cactus_A", "Vase_C", "Vase_C_Dirt"], "windowsill / doorstep plant", False,
      budget="plant", tex=512),
    P("potted_money_tree", "plants", ["Money_Tree"], "doorstep plant", False, budget="plant", tex=1024),
    P("potted_orchid", "plants", ["Orchid_A", "Vase_A", "Vase_A_Dirt"], "windowsill plant", False, budget="plant",
      tex=512),
    P("potted_mint", "plants", ["Pot_Plant_A", "Mint"], "windowsill herb pot", False, budget="plant", tex=512),
    P("window_flower_box", "plants", ["FlowerBox_A", "Flowerbox_A_Dirt", "Flowerbox_A_Plants"],
      "window-sill flower box", False, budget="plant", tex=512),
]

HOUSE_SEAT = {"Aloe_Vera_A": "Vase_B_Dirt", "Cactus_A": "Vase_C_Dirt", "Orchid_A": "Vase_A_Dirt"}

RESTAURANT = [
    P("restaurant_booth", "restaurant", ["SM_Tables"], "restaurant table", True, tex=1024),
    P("restaurant_stool", "restaurant", ["SM_Chair"], "restaurant bar stool", True, scale=1.3),
    P("jukebox", "restaurant", ["SM_Jukebox"], "restaurant interior prop", True, tex=1024),
    P("drinks_fridge", "restaurant", ["SM_Fridge"], "restaurant kitchen fridge", True, tex=1024),
    P("kitchen_counter", "restaurant", ["SM_KitchenCounter"], "restaurant kitchen counter", True, tex=1024),
    P("kitchen_oven", "restaurant", ["SM_KitchenOven", "SM_KitchenOvenDoor"], "restaurant kitchen oven", True,
      tex=1024),
    P("vegetable_counter", "restaurant", ["SM_VegetableCounter"], "restaurant kitchen counter", True, tex=1024),
    P("donut_display", "restaurant", ["SM_DonutCounter"], "counter-top display case", False),
    P("wet_floor_sign", "restaurant", ["SM_FloorSign"], "restaurant entrance sign", False),
    P("parking_lot_lamp", "restaurant", ["SM_OutsideLamp"], "restaurant car-park lamp", True, front="-X", budget="large", tex=1024),
    P("restaurant_dumpster", "restaurant", ["SM_TrashBin"], "restaurant back-door dumpster", True, tex=1024),
    P("restaurant_trash_bag", "restaurant", ["SM_Trash"], "back-door rubbish bag", False),
    P("wall_poster_food", "restaurant", ["SM_Signs01"], "restaurant wall poster", False, stand=True),
]

# ----------------------------------------------------------------------------- helpers


def log(*a):
    print("[props]", *a, flush=True)


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


def new_scene_state():
    _img_cache.clear()  # image names (Image_0, Image_1, ...) repeat between packs
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src = bpy.data.collections.new("SRC")
    bpy.context.scene.collection.children.link(src)
    return src


def move_all_to(coll):
    sc = bpy.context.scene.collection
    for o in list(sc.objects):
        coll.objects.link(o)
        sc.objects.unlink(o)


def import_glb(name):
    src = new_scene_state()
    t0 = time.time()
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, name))
    move_all_to(src)
    src.hide_render = True
    log("imported", name, "in %.1fs" % (time.time() - t0))
    return src


def append_blend(path, names):
    src = new_scene_state()
    with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
        data_to.objects = [n for n in data_from.objects if n in names]
    for o in data_to.objects:
        if o is not None:
            src.objects.link(o)
    src.hide_render = True
    bpy.context.view_layer.update()  # appended objects have stale matrix_world until evaluated
    log("appended", len(data_to.objects), "objects from", os.path.basename(path))
    return src


def bake(src_objs, name):
    """World-space static copy of the meshes (modifiers/armatures applied), joined into one object."""
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in src_objs:
        if o.type != 'MESH' or o.hide_render or o.hide_viewport or o.hide_get():
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        if not me.polygons:
            continue
        me.transform(o.matrix_world)
        n = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(n)
        parts.append(n)
    if not parts:
        raise RuntimeError("no meshes for " + name)
    if len(parts) > 1:
        # all parts need a common UV layer name for a clean join
        for p in parts:
            if p.data.uv_layers:
                p.data.uv_layers[0].name = "UVMap"
        select_only(parts)
        bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    return obj


def cut_below_ground(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
    bm.to_mesh(obj.data)
    bm.free()


def decimate(obj, budget):
    t = tris_of(obj)
    if t <= budget:
        return False
    for _ in range(4):
        m = obj.modifiers.new("decimate", 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.ratio = max(0.01, budget / tris_of(obj) * 0.97)
        m.use_collapse_triangulate = True
        select_only([obj])
        bpy.ops.object.modifier_apply(modifier=m.name)
        if tris_of(obj) <= budget:
            break
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


# ----------------------------------------------------------------------------- materials / textures
_img_cache = {}


def _pow2(n):
    return int(2 ** max(2, round(math.log2(max(n, 4)))))


def bake_mapping(px, mapping):
    """Resample so that new(uv) = old(Mapping(uv)) on [0,1]^2 (wrapping), i.e. the glTF
    KHR_texture_transform the importer turned into a Mapping node is baked into the pixels.
    Exact for the flips/90-degree rotations these packs use."""
    loc, rot, scl = mapping
    h, w = px.shape[:2]
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    uu, vv = np.meshgrid(u, v)
    x, y = uu * scl[0], vv * scl[1]
    c, s = math.cos(rot), math.sin(rot)
    xr, yr = c * x - s * y + loc[0], s * x + c * y + loc[1]
    xi = (np.floor(np.mod(xr, 1.0) * w).astype(int)).clip(0, w - 1)
    yi = (np.floor(np.mod(yr, 1.0) * h).astype(int)).clip(0, h - 1)
    return px[yi, xi]


def processed_image(img, max_px, crop, keep_alpha, noncolor, mapping=None):
    key = (img.name, max_px, crop, keep_alpha, mapping)
    if key in _img_cache:
        path = _img_cache[key]
    else:
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        if mapping:
            px = bake_mapping(px, mapping)
        if crop:
            u0, v0, u1, v1 = crop
            x0, x1 = int(math.floor(u0 * w)), int(math.ceil(u1 * w))
            y0, y1 = int(math.floor(v0 * h)), int(math.ceil(v1 * h))
            px = px[y0:y1, x0:x1].copy()
        ch, cw = px.shape[:2]
        s = min(1.0, max_px / max(cw, ch))
        tw, th = min(max_px, _pow2(cw * s)), min(max_px, _pow2(ch * s))
        tmp = bpy.data.images.new("tmp_resize", cw, ch, alpha=True, float_buffer=False)
        if noncolor:
            tmp.colorspace_settings.name = 'Non-Color'
        tmp.pixels.foreach_set(px.ravel())
        if (tw, th) != (cw, ch):
            tmp.scale(tw, th)
        ext = "png" if keep_alpha else "jpg"
        path = os.path.join(TMP, "%d.%s" % (len(_img_cache), ext))
        tmp.file_format = 'PNG' if keep_alpha else 'JPEG'
        if not keep_alpha:
            tmp.alpha_mode = 'NONE'
        try:
            tmp.save(filepath=path, quality=90)
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


def uv_crop_for(obj, slot_index):
    me = obj.data
    if not me.uv_layers:
        return None
    uv = me.uv_layers[0].data
    loops = [li for p in me.polygons if p.material_index == slot_index for li in p.loop_indices]
    if not loops:
        return None
    a = np.empty(len(uv) * 2)
    uv.foreach_get("uv", a)
    a = a.reshape(-1, 2)[loops]
    lo, hi = a.min(0), a.max(0)
    if lo.min() < -0.001 or hi.max() > 1.001:
        return None  # tiling texture
    pad = 0.01
    lo = np.clip(lo - pad, 0, 1)
    hi = np.clip(hi + pad, 0, 1)
    if (hi - lo).prod() > 0.55:
        return None
    return (round(float(lo[0]), 4), round(float(lo[1]), 4), round(float(hi[0]), 4), round(float(hi[1]), 4)), loops


def remap_uv(obj, loops, crop):
    u0, v0, u1, v1 = crop
    uv = obj.data.uv_layers[0].data
    for li in loops:
        u, v = uv[li].uv
        uv[li].uv = ((u - u0) / (u1 - u0), (v - v0) / (v1 - v0))


def uv_source(img_node):
    """Name of the UV map an image node samples (via an optional Mapping node), or None for the default."""
    vin = img_node.inputs["Vector"]
    if not vin.is_linked:
        return None
    n = vin.links[0].from_node
    if n.type == 'MAPPING' and n.inputs["Vector"].is_linked:
        n = n.inputs["Vector"].links[0].from_node
    if n.type == 'UVMAP':
        return n.uv_map or None
    return None


def unlink_uvmap(mat, img_node):
    vin = img_node.inputs["Vector"]
    n = vin.links[0].from_node
    if n.type == 'UVMAP':
        mat.node_tree.links.remove(vin.links[0])
    elif n.type == 'MAPPING' and n.inputs["Vector"].is_linked:
        mat.node_tree.links.remove(n.inputs["Vector"].links[0])


def same_uv(obj, slot_index, a, b):
    me = obj.data
    if a not in me.uv_layers or b not in me.uv_layers:
        return False
    loops = [li for p in me.polygons if p.material_index == slot_index for li in p.loop_indices]
    ua = np.empty(len(me.loops) * 2)
    ub = np.empty(len(me.loops) * 2)
    me.uv_layers[a].data.foreach_get("uv", ua)
    me.uv_layers[b].data.foreach_get("uv", ub)
    ua, ub = ua.reshape(-1, 2)[loops], ub.reshape(-1, 2)[loops]
    return bool(np.allclose(ua, ub, atol=1e-4))


def process_materials(obj, spec):
    """Per-prop material copies: resized/cropped textures, alpha mode fixed for glTF export."""
    info = []
    remapped = set()
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
        crop_info = uv_crop_for(obj, si)
        crop = None
        if crop_info:
            crop, loops = crop_info
        bsdf = principled(mat)
        alpha_mode = "OPAQUE"
        alpha_img_node = None
        if bsdf is not None:
            a_in = bsdf.inputs["Alpha"]
            if a_in.is_linked:
                imgs = upstream_images(a_in.links[0].from_node)
                if imgs and image_has_cutout(imgs[0].image):
                    alpha_img_node = imgs[0]
                    alpha_mode = "MASK"
                elif imgs:
                    mat.node_tree.links.remove(a_in.links[0])
                    a_in.default_value = 1.0
                else:
                    alpha_mode = "BLEND?"
            elif a_in.default_value < 0.999:
                alpha_mode = "BLEND"
        base_img = None
        if bsdf is not None and bsdf.inputs["Base Color"].is_linked:
            ims = upstream_images(bsdf.inputs["Base Color"].links[0].from_node)
            base_img = ims[0] if ims else None
        for n in list(mat.node_tree.nodes):
            if n.type != 'TEX_IMAGE' or n.image is None:
                continue
            uvname = uv_source(n)
            if uvname and uvname != first_uv:
                # Godot imports one UV set per material: keep the map if it matches UV0, else drop it
                if same_uv(obj, si, first_uv, uvname):
                    unlink_uvmap(mat, n)
                else:
                    spec.setdefault("_dropped", []).append("%s:%s(%s)" % (src.name, n.image.name, uvname))
                    for l in list(n.outputs[0].links) + list(n.outputs[1].links):
                        if l.to_node.type in ('SEPARATE_COLOR', 'SEPARATE_RGB', 'NORMAL_MAP'):
                            mat.node_tree.nodes.remove(l.to_node)
                    mat.node_tree.nodes.remove(n)
                    continue
            noncolor = n.image.colorspace_settings.name in ('Non-Color', 'Linear', 'Raw') or \
                n.image.colorspace_settings.is_data
            keep_alpha = (n is alpha_img_node) or (alpha_img_node is not None and n.image == alpha_img_node.image)
            mapping = None
            vin = n.inputs["Vector"]
            if vin.is_linked and vin.links[0].from_node.type == 'MAPPING':
                mp = vin.links[0].from_node
                loc = tuple(round(x, 5) for x in mp.inputs["Location"].default_value)
                rot = round(mp.inputs["Rotation"].default_value[2], 5)
                scl = tuple(round(x, 5) for x in mp.inputs["Scale"].default_value)
                if loc[:2] != (0, 0) or rot != 0 or scl[:2] != (1, 1):
                    mapping = (loc[:2], rot, scl[:2])
                mat.node_tree.links.remove(vin.links[0])
            n.image = processed_image(n.image, spec["tex"], crop, keep_alpha, noncolor, mapping)
            n.image.name = "%s_%d" % (spec["id"], len(info))
            n.interpolation = 'Linear'
            info.append("%s:%dx%d" % (mat.name, *n.image.size))
        if crop and si not in remapped:
            remap_uv(obj, loops, crop)
            remapped.add(si)
        if alpha_mode == "MASK" and bsdf is not None:
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
        if base_img is not None:
            mat.node_tree.nodes.active = base_img
        spec.setdefault("_alpha", []).append("%s=%s" % (src.name, alpha_mode))
    # every texture now samples UV0: drop the extra UV sets (Godot uses a single UV set per material)
    uvl = obj.data.uv_layers
    while len(uvl) > 1:
        uvl.remove(uvl[len(uvl) - 1])
    if len(uvl):
        uvl[0].active = True
        uvl[0].active_render = True
    return info


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
    try:
        sh.show_cavity = False
    except AttributeError:
        pass
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("W")
    # 1 m reference stick (red) beside the prop
    w, d, h = dims
    stick_me = bpy.data.meshes.new("ref")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.02, radius2=0.02, depth=1.0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.5))
    bm.to_mesh(stick_me)
    bm.free()
    stick = bpy.data.objects.new("ref", stick_me)
    stick.location = (-(w / 2 + max(0.15, 0.08 * max(w, h))), 0, 0)
    sm = bpy.data.materials.new("ref")
    sm.diffuse_color = (0.9, 0.05, 0.05, 1)
    stick_me.materials.append(sm)
    scene.collection.objects.link(stick)
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    span = max(w + 2 * abs(stick.location.x) * 0.5, d, h)
    cam.data.ortho_scale = span * 1.35
    dirv = Vector((0.75, -1.4, 0.75)).normalized() * (50 + span * 4)  # from the front-right; front is -Y
    target = Vector((-abs(stick.location.x) * 0.25, 0, h * 0.5))
    cam.location = target + dirv
    cam.rotation_euler = (-dirv).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = 1000
    scene.camera = cam
    scene.render.filepath = os.path.join(QA, pid + ".png")
    bpy.ops.render.render(write_still=True)
    for o in (cam, stick):
        bpy.data.objects.remove(o)


# ----------------------------------------------------------------------------- per-prop pipeline
FRONT_ROT = {"-Y": 0.0, "+Y": math.pi, "-X": math.pi / 2, "+X": -math.pi / 2}
RESULTS = []


def wanted(pid):
    return not ONLY or pid in ONLY


def build_prop(spec, src_objs, source_name):
    pid = spec["id"]
    t0 = time.time()
    obj = bake(src_objs, pid)
    src_tris = tris_of(obj)
    m = Matrix.Identity(4)
    if spec["stand"]:
        m = Matrix.Rotation(math.pi / 2, 4, 'X') @ m  # +Z face -> -Y
    m = Matrix.Rotation(FRONT_ROT[spec["front"]], 4, 'Z') @ m
    m = Matrix.Scale(spec["scale"], 4) @ m
    # rotate/scale about the footprint centre so the cut plane (z=0) is preserved
    lo, hi = bounds(obj)
    c = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0.0))
    if spec["stand"]:
        c.z = (lo[2] + hi[2]) / 2
    obj.data.transform(Matrix.Translation(-c))
    if spec["cut"]:
        cut_below_ground(obj)
    obj.data.transform(m)
    decimated = decimate(obj, BUDGET[spec["budget"]])
    lo, hi = bounds(obj)
    obj.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    obj.data.update()
    lo, hi = bounds(obj)
    dims = hi - lo
    pts = world_pts(obj)
    top = pts[pts[:, 2] > lo[2] + 0.85 * dims[2]]
    spec["_top"] = "top-centroid xy=(%.2f, %.2f)" % tuple(top[:, :2].mean(0)) if len(top) else ""
    texinfo = process_materials(obj, spec)
    obj["prop_id"] = pid
    obj["category"] = spec["cat"]
    obj["collision"] = bool(spec["collision"])
    obj["suggested_use"] = spec["use"]
    obj["source"] = source_name
    os.makedirs(os.path.join(OUT, spec["cat"]), exist_ok=True)
    path = os.path.join(OUT, spec["cat"], pid + ".glb")
    select_only([obj])
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_image_format='AUTO', export_materials='EXPORT', export_cameras=False,
                              export_lights=False)
    t = tris_of(obj)
    entry = {
        "id": pid, "category": spec["cat"],
        "path": "res://assets/sketchup/props/%s/%s.glb" % (spec["cat"], pid),
        "source": source_name,
        "size": [round(float(dims[0]), 3), round(float(dims[2]), 3), round(float(dims[1]), 3)],
        "tris": t, "suggested_use": spec["use"], "collision": bool(spec["collision"]),
    }
    RESULTS.append(entry)
    log("EXPORTED %-28s tris %6d (src %6d%s) size %s mats %d alpha %s %s tex %s  %.1fs" % (
        pid, t, src_tris, ", decimated" if decimated else "", entry["size"], len(obj.material_slots),
        spec.get("_alpha"), spec.get("_top"), sorted(set(texinfo)), time.time() - t0))
    if spec.get("_dropped"):
        log("  dropped secondary-UV textures for %s: %s" % (pid, spec["_dropped"]))
    if DO_QA:
        os.makedirs(QA, exist_ok=True)
        render_qa(obj, pid, (float(dims[0]), float(dims[1]), float(dims[2])))
    # clean up this prop
    mats = [s.material for s in obj.material_slots if s.material]
    me = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(me)
    for mt in mats:
        for n in mt.node_tree.nodes if mt.node_tree else []:
            if n.type == 'TEX_IMAGE' and n.image and n.image.users <= 1:
                bpy.data.images.remove(n.image)
        bpy.data.materials.remove(mt)


def objs_for(spec, by_name):
    out = []
    for n in spec["nodes"]:
        if n not in by_name:
            raise KeyError("node %r not found for %s" % (n, spec["id"]))
        o = by_name[n]
        if spec["direct"]:
            out += [o] + [c for c in o.children if c.type == 'MESH']
        else:
            out += subtree(o)
    drop = set(spec["drop"])
    return [o for o in out if o.name not in drop]


def run_named(specs, glb, source):
    todo = [s for s in specs if wanted(s["id"])]
    if not todo:
        return
    import_glb(glb)
    by_name = {o.name: o for o in bpy.data.objects}
    for s in todo:
        build_prop(s, objs_for(s, by_name), source)


def run_lowpoly_plants():
    specs = []
    for pid, anchors in LOWPOLY_PLANTS:
        fid, use, col, *rest = LOWPOLY_NAMES.get(pid, (pid, "doorstep plant", False))
        # this pack is modelled large (pots 0.4-0.7 m); the spider plant and haworthia are scaled down
        specs.append((P(fid, "plants", anchors, use, col, budget="plant", tex=1024, scale=rest[0] if rest else 1.0),
                      anchors))
    if not any(wanted(s["id"]) for s, _ in specs):
        return
    import_glb("low_poly_plants_pack.glb")
    root = bpy.data.objects["RootNode"]
    tops = list(root.children)

    def centre(o):
        pts = np.concatenate([world_pts(x) for x in subtree(o) if x.type == 'MESH' and x.data.vertices])
        return (pts.min(0) + pts.max(0)) / 2

    anchor_c = {pid: centre(bpy.data.objects[a[0]]) for pid, a in LOWPOLY_PLANTS}
    groups = {pid: [] for pid, _ in LOWPOLY_PLANTS}
    for o in tops:
        c = centre(o)
        best = min(anchor_c, key=lambda k: (anchor_c[k][0] - c[0]) ** 2 + (anchor_c[k][1] - c[1]) ** 2)
        groups[best] += subtree(o)
    for (spec, anchors), (pid, _) in zip(specs, LOWPOLY_PLANTS):
        if wanted(spec["id"]):
            build_prop(spec, groups[pid], "low_poly_plants_pack.glb")


def run_house():
    todo = [s for s in HOUSE if wanted(s["id"])]
    if not todo:
        return
    if not HOUSE_BLEND or not os.path.isfile(HOUSE_BLEND):
        log("house-plants .blend not given (--house-plants); skipping that pack")
        return
    names = {n for s in todo for n in s["nodes"]}
    append_blend(HOUSE_BLEND, names)
    by_name = {o.name: o for o in bpy.data.objects}
    # the aloe, cactus and orchid ship without pots: seat them in the pack's empty vases
    for plant, dirt in HOUSE_SEAT.items():
        if plant in by_name and dirt in by_name:
            p, d = by_name[plant], by_name[dirt]
            plo, phi = bounds(p)
            dlo, dhi = bounds(d)
            off = Vector((((dlo + dhi) / 2 - (plo + phi) / 2)[0], ((dlo + dhi) / 2 - (plo + phi) / 2)[1],
                          dhi[2] - 0.015 - plo[2]))
            p.matrix_world = Matrix.Translation(off) @ p.matrix_world
    for s in todo:
        build_prop(s, objs_for(s, by_name), "house-plants.zip (Sketchfab_2023_04_19_23_25_22.blend)")


def write_catalog():
    old = []
    if os.path.isfile(CATALOG):
        try:
            with open(CATALOG) as f:
                old = json.load(f).get("props", [])
        except (ValueError, OSError):
            old = []
    new_ids = {e["id"] for e in RESULTS}
    props = [e for e in old if e["id"] not in new_ids] + RESULTS
    order = {"street": 0, "road": 1, "plants": 2, "restaurant": 3}
    props.sort(key=lambda e: (order.get(e["category"], 9), e["id"]))
    with open(CATALOG, "w") as f:
        json.dump({"convention": CONVENTION, "props": props}, f, indent=1)
    log("catalog:", len(props), "props ->", CATALOG)


def main():
    def pack(name):
        return not PACKS or name in PACKS

    if pack("street"):
        run_named(STREET, "pbr_street_props_pack_game_ready.glb", "pbr_street_props_pack_game_ready.glb")
    if pack("road"):
        run_named(ROAD, "road_pack_not_including_the_road.glb", "road_pack_not_including_the_road.glb")
    if pack("plants"):
        run_lowpoly_plants()
    if pack("geranium"):
        run_named(GERANIUM, "geranium_flowering_plants_free.glb", "geranium_flowering_plants_free.glb")
    if pack("potted"):
        run_named(POTTED, "optimized_potted_plants.glb", "optimized_potted_plants.glb")
    if pack("house"):
        run_house()
    if pack("restaurant"):
        run_named(RESTAURANT, "low_poly_psx_style_restaurant_props_-_asset_pack.glb",
                  "low_poly_psx_style_restaurant_props_-_asset_pack.glb")
    write_catalog()


main()
