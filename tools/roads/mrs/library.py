"""Asset Browser package (v5): the working Road Studio pieces as Blender assets with catalogs, rendered
thumbnails and short descriptions, in one self-contained .blend (images packed) next to its
`blender_assets.cats.txt`.

Catalogs (Mert Road Studio/...):
  Roads            one 40 m road per preset (residential, urban, highway, rural, service, bridge): the MRS_Road
                   Geometry Nodes modifier with every input live (lanes, widths, cycleways, kerbs, ramps,
                   driveways, materials ...); edit the curve or the modifier, the road regenerates
  Footbridges      Girder / Truss / Box footbridges solved over a demo avenue: MRS_Footbridge modifier live
                   (style, width, railings, lighting, materials); re-solve against your road with footbridge.make
  Furniture        the sidewalk furniture library (benches, bins, racks, shelter, bollards, cabinets ...)
  Lighting         streetlight families (Highway, Double, LED, Lantern, Bollard, WallPack) with light anchors
  Signs            regulatory / warning / information signs (baked game versions) and direction boards
  Barriers         guardrail, jersey, parapet, railing, fence, hedge (2 m tiling segments)
  Trees            the game's landscape-kit trees (LOD0 + LOD1) and plants
  Buildings        a city-kit shop frontage (facade modules, signs, service yard)

    blender --background --factory-startup --python tools/roads/tests/asset_library_test.py
"""
import bpy, os, math, uuid, json
from mathutils import Vector
from .nodes import MRS

ROOT_CAT = "Mert Road Studio"
CATALOGS = ["Roads", "Footbridges", "Furniture", "Lighting", "Signs", "Barriers", "Trees", "Plants", "Buildings"]
UUID_NS = uuid.UUID("6f9b8f4e-2c1d-4c55-9a51-4d52535f7635")          # stable catalog ids


def catalog_uuid(name):
    return str(uuid.uuid5(UUID_NS, ROOT_CAT + "/" + name))


def write_catalogs(directory):
    lines = ["# This is an Asset Catalog Definition file for Blender.", "#", "# Empty lines and lines starting with `#` will be ignored.",
             "# The first non-ignored line should be the version indicator.", "# Other lines are of the format \"UUID:catalog/path/for/assets:simple catalog name\"", "",
             "VERSION 1", "", "%s:%s:%s" % (catalog_uuid(""), ROOT_CAT, ROOT_CAT)]
    for c in CATALOGS:
        lines.append("%s:%s/%s:%s-%s" % (catalog_uuid(c), ROOT_CAT, c, ROOT_CAT, c))
    p = os.path.join(directory, "blender_assets.cats.txt")
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return p


ROAD_TEXT = {"residential": "Two-lane residential street, 2 m sidewalks, dashed centre line",
             "urban": "Urban street: lanes, parking / cycle options, wide sidewalks, kerbs and ramps at junctions",
             "highway": "Dual carriageway with shoulders, edge lines and barriers",
             "rural": "Rural two-lane road with soft shoulders and embankments",
             "service": "Narrow service road / lane",
             "bridge": "Elevated deck on pillars with parapets"}


def _mark(o, cat, desc, tags=()):
    o.asset_mark()
    o.asset_data.catalog_id = catalog_uuid(cat)
    o.asset_data.description = desc
    o.asset_data.author = "Mert Road Studio"
    for t in tags:
        if t not in o.asset_data.tags: o.asset_data.tags.new(t)
    return o


def build_assets(col):
    """Create / collect the asset objects in collection `col` (sources stay where the library builders put them).
    Returns [(object, catalog, description)]."""
    from . import roads, footbridge, signage
    out = []
    # --- roads: one per preset
    for i, (pre, txt) in enumerate(ROAD_TEXT.items()):
        nm = "MRS_Asset_Road_" + pre
        old = bpy.data.objects.get(nm)
        if old: bpy.data.objects.remove(old)
        o = roads.make_road(nm, [(0, i * 40.0, 0), (20, i * 40.0, 0), (40, i * 40.0, 0)], col, pre, Conform=False, Embankment=False)
        out.append((o, "Roads", "%s. Geometry Nodes road (MRS_Road): every input stays live." % txt, ("road", pre)))
    # --- footbridges over a demo avenue (one per style)
    av = bpy.data.objects.get("MRS_Asset_FBAvenue")
    if av: bpy.data.objects.remove(av)
    av = roads.make_road("MRS_Asset_FBAvenue", [(-200, 0, 0), (0, 0, 0), (200, 0, 0)], col, "urban", Conform=False, Embankment=False,
                         Sidewalk_Width_Left=4.0, Sidewalk_Width_Right=4.0)
    footbridge.ensure_group()
    for k, style in enumerate(footbridge.STYLES):
        try:
            fb, plan = footbridge.make("MRS_Asset_Footbridge_" + style, av, 70.0 + 130.0 * k, col, style=style)
        except TypeError:
            fb, plan = footbridge.make("MRS_Asset_Footbridge_" + style, av, 70.0 + 130.0 * k, col)
            footbridge.mod_input_set(fb.modifiers[footbridge.MOD], "Style", style); footbridge.rebuild_all(col)
        out.append((fb, "Footbridges", "%s footbridge (MRS_Footbridge): ramps + stairs, railings, LED handrail, deck lights; status %s. "
                    "Re-solve over your road with footbridge.make(name, road, along, collection)." % (style, plan.get("status")), ("footbridge", style.lower())))
    # --- library objects by collection
    groups = [("Furniture", MRS + "Furniture", "Sidewalk furniture"), ("Lighting", MRS + "Streetlights", "Streetlight"),
              ("Signs", MRS + "Signage", "Sign"), ("Barriers", MRS + "Barriers", "Road barrier segment (2 m, tiles along a road)"),
              ("Trees", MRS + "GameTrees", "Game landscape tree"), ("Plants", MRS + "GamePlants", "Game landscape plant")]
    for cat, cname, what in groups:
        c = bpy.data.collections.get(cname)
        if c is None: continue
        for o in sorted(c.objects, key=lambda x: x.name):
            if o.type not in ("MESH", "EMPTY", "CURVE") or o.parent is not None: continue
            nice = o.name.replace(MRS, "").replace("F_", "").replace("GTree_", "").replace("GPlant_", "").replace("_", " ")
            lod = " (LOD1)" if o.name.endswith("_LOD1") else ""
            out.append((o, cat, "%s: %s%s." % (what, nice.replace(" LOD1", ""), lod), (cat.lower(),)))
    # --- a frontage building (city kit) over a residential street
    try:
        from . import frontage
        st = bpy.data.objects.get("MRS_Asset_FrontStreet")
        if st: bpy.data.objects.remove(st)
        st = roads.make_road("MRS_Asset_FrontStreet", [(0, -80, 0), (40, -80, 0), (80, -80, 0)], col, "residential", Conform=False, Embankment=False,
                             Sidewalk_Width_Left=4.5)
        frontage.make_shop({"id": "MRS_Asset_Shop", "road": st.name, "side": "l", "along": 30.0, "bays": 4, "floors": 2, "name": "Halden Grocer",
                            "number": 24, "street": "Maple St"}, col)
        shop = bpy.data.objects["MRS_Asset_Shop"]
        out.append((shop, "Buildings", "Shop frontage assembled from the game's city-kit facade modules (Kit* materials map to CityKit in Godot); "
                    "rebuild any size / position with frontage.make_shop(spec, roads_collection).", ("building", "shop", "citykit")))
    except Exception as e:
        print("library: frontage asset skipped:", e)
    for o, cat, desc, tags in out: _mark(o, cat, desc, tags)
    return out


# ============================================================================ thumbnails
def _thumb_scene():
    sc = bpy.data.scenes.get("MRS_Thumbs") or bpy.data.scenes.new("MRS_Thumbs")
    r = sc.render
    try: r.engine = "BLENDER_EEVEE"
    except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
    r.resolution_x = r.resolution_y = 256; r.resolution_percentage = 100; r.film_transparent = True
    r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGBA"
    sc.eevee.taa_render_samples = 16
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.get("MRS_ThumbWorld") or bpy.data.worlds.new("MRS_ThumbWorld"); w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[0].default_value = (0.75, 0.78, 0.82, 1); bg.inputs[1].default_value = 1.0
    sc.world = w
    cam = bpy.data.objects.get("MRS_ThumbCam")
    if cam is None:
        cam = bpy.data.objects.new("MRS_ThumbCam", bpy.data.cameras.new("MRS_ThumbCam")); sc.collection.objects.link(cam)
    sc.camera = cam
    sun = bpy.data.objects.get("MRS_ThumbSun")
    if sun is None:
        ld = bpy.data.lights.new("MRS_ThumbSun", "SUN"); ld.energy = 3.0
        sun = bpy.data.objects.new("MRS_ThumbSun", ld); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    return sc, cam


def render_thumbnail(o, path, sc, cam, view=(1.0, -1.25, 0.8)):
    """Frame `o` (evaluated bounds) from a 3/4 view and render a 256 px PNG with a transparent film."""
    tmp = bpy.data.collections.get("MRS_ThumbItem") or bpy.data.collections.new("MRS_ThumbItem")
    if tmp.name not in sc.collection.children: sc.collection.children.link(tmp)
    for x in list(tmp.objects): tmp.objects.unlink(x)
    tmp.objects.link(o)
    hidden = []
    for ch in o.children_recursive:
        if ch.name not in tmp.objects: tmp.objects.link(ch); hidden.append(ch)
    vis = {x.name: (x.hide_render, x.hide_viewport) for x in [o] + list(o.children_recursive)}
    for x in [o] + list(o.children_recursive): x.hide_render = False; x.hide_viewport = False    # library sources are hidden
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    ev = o.evaluated_get(dg)
    pts = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    for ch in hidden:
        e2 = ch.evaluated_get(dg); pts += [e2.matrix_world @ Vector(c) for c in e2.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2; size = max((hi - lo).length, 0.3)
    cam.data.lens = 50.0; cam.data.clip_end = max(1000.0, size * 10)
    d = Vector(view).normalized()
    cam.location = c + d * size * 1.25
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    for x in list(tmp.objects): tmp.objects.unlink(x)
    for nm, (hr, hv) in vis.items():
        x = bpy.data.objects.get(nm)
        if x is not None: x.hide_render = hr; x.hide_viewport = hv
    return path


def set_preview(o, png):
    img = bpy.data.images.load(png, check_existing=False)
    w, h = img.size
    px = list(img.pixels[:])
    pv = o.preview_ensure()
    pv.image_size = (w, h)
    pv.image_pixels_float = px
    bpy.data.images.remove(img)
    return (w, h)


def build_library(out_blend, thumbs_dir=None):
    """Build every asset into a fresh 'MRS_AssetLibrary' scene, render the thumbnails, pack the images, write
    the catalogs next to `out_blend` and save it. Returns a summary dict."""
    from . import nodes
    d = os.path.dirname(os.path.abspath(out_blend)); os.makedirs(d, exist_ok=True)
    thumbs_dir = thumbs_dir or os.path.join(d, "thumbnails"); os.makedirs(thumbs_dir, exist_ok=True)
    sc = bpy.data.scenes.get("MRS_AssetLibrary") or bpy.data.scenes.new("MRS_AssetLibrary")
    nodes.set_scene(sc)
    col = bpy.data.collections.get("MRS_AssetLibrary_Roads") or bpy.data.collections.new("MRS_AssetLibrary_Roads")
    if col.name not in sc.collection.children: sc.collection.children.link(col)
    items = build_assets(col)
    tsc, cam = _thumb_scene()
    summary = {"assets": [], "catalogs": {}}
    for o, cat, desc, tags in items:
        png = os.path.join(thumbs_dir, "%s.png" % o.name)
        try:
            render_thumbnail(o, png, tsc, cam, view=(0.8, 1.4, 0.55) if cat == "Signs" else (1.0, -1.25, 0.8)); size = set_preview(o, png)   # signs face +Y
        except Exception as e:
            size = None; print("thumbnail failed", o.name, e)
        summary["assets"].append({"name": o.name, "catalog": cat, "description": desc, "thumbnail": os.path.basename(png), "preview": size})
        summary["catalogs"][cat] = summary["catalogs"].get(cat, 0) + 1
    nodes.set_scene(sc)
    cats = write_catalogs(d)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack_all:", e)
    missing = [im.name for im in bpy.data.images if im.source == "FILE" and im.packed_file is None and im.users > 0]
    summary["unpacked_images"] = missing
    for g in bpy.data.node_groups: g.use_fake_user = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True, copy=True)
    summary["blend"] = out_blend; summary["blend_mb"] = round(os.path.getsize(out_blend) / 1e6, 1); summary["catalog_file"] = cats
    json.dump(summary, open(os.path.join(d, "library.json"), "w"), indent=1)
    return summary
