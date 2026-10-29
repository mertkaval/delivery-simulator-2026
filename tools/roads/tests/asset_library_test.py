"""v5 package test: build the Road Studio Asset Browser library (catalogs, thumbnails, descriptions, packed
images), then verify it in a separate fresh Blender process:
  1. the library file: every asset has a catalog listed in blender_assets.cats.txt, a description and a preview;
     no image is external / missing;
  2. a factory-startup file: append the assets, evaluate them, change parameters (road lanes / sidewalk /
     driveway, footbridge style / width) and check the generated geometry follows.

    blender --background --factory-startup --python tools/roads/tests/asset_library_test.py [-- --verify-only]
Output: tmp/roads/v5/library/ (MertRoadStudio_Library.blend, blender_assets.cats.txt, thumbnails/, results.json)
"""
import bpy, sys, os, json, subprocess, traceback, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.environ.get("MRS_LIB_OUT") or os.path.join(ROOT, "tmp", "roads", "v5", "library")
LIB = os.path.join(OUT, "MertRoadStudio_Library.blend")
BASE = os.path.join(ROOT, "tmp", "roads", "v4", "base_built.blend")
os.makedirs(OUT, exist_ok=True)


def verify():
    """Runs in a second Blender process (--verify)."""
    import mrs
    from mrs import nodes
    res = {"problems": []}
    def check(c, m):
        if not c: res["problems"].append(m); print("PROBLEM", m)
    cats = {}
    for line in open(os.path.join(OUT, "blender_assets.cats.txt"), encoding="utf-8"):
        if line.strip() and not line.startswith(("#", "VERSION")):
            u, path, _ = line.strip().split(":", 2); cats[u] = path
    # 1. the library file itself: metadata, previews, packed images
    bpy.ops.wm.open_mainfile(filepath=LIB)
    assets = [o for o in bpy.data.objects if o.asset_data]
    by_cat = {}
    for o in assets:
        cp = cats.get(o.asset_data.catalog_id)
        check(cp is not None, "%s: catalog id not in the catalog file" % o.name)
        check(bool(o.asset_data.description), "%s: no description" % o.name)
        pv = o.preview
        check(pv is not None and pv.image_size[0] >= 128, "%s: no thumbnail" % o.name)
        by_cat[cp] = by_cat.get(cp, 0) + 1
    ext = [im.name for im in bpy.data.images if im.source == "FILE" and im.packed_file is None and im.users > 0]
    check(not ext, "images not packed: %s" % ext[:6])
    res["library"] = {"assets": len(assets), "by_catalog": by_cat, "images": len(bpy.data.images), "unpacked": ext, "node_groups": len(bpy.data.node_groups)}
    print("LIBRARY", res["library"])
    # 2. a fresh file: append every asset, evaluate, change parameters
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(LIB, link=False, assets_only=True) as (src, dst):
        dst.objects = list(src.objects)
    sc = bpy.context.scene
    for o in dst.objects:
        if o is not None: sc.collection.objects.link(o)
    objs = {o.name: o for o in dst.objects if o is not None}
    res["appended"] = len(objs)
    dg = bpy.context.evaluated_depsgraph_get()
    def tris(o):
        dg.update(); ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh(); n = sum(len(p.vertices) - 2 for p in me.polygons); ev.to_mesh_clear(); return n
        except RuntimeError:
            return 0
    def width(o):
        dg.update(); ev = o.evaluated_get(dg); me = ev.to_mesh()
        ys = [(o.matrix_world @ v.co).y for v in me.vertices]; ev.to_mesh_clear()
        return round(max(ys) - min(ys), 3) if ys else 0.0
    empty = [n for n, o in objs.items() if o.type in ("MESH", "CURVE") and tris(o) == 0]
    check(not empty, "appended assets evaluate to nothing: %s" % empty[:6])
    missing_img = sorted({im.name for im in bpy.data.images if im.source == "FILE" and (im.packed_file is None and not os.path.exists(bpy.path.abspath(im.filepath)))})
    check(not missing_img, "missing images after append: %s" % missing_img[:6])
    road = objs.get("MRS_Asset_Road_urban")
    tests = {}
    if road is not None:
        mod = road.modifiers["MRS_Road"]
        w0 = width(road); t0 = tris(road)
        nodes.mod_input_set(mod, "Lanes Forward", 3); road.update_tag(); w1 = width(road)
        nodes.mod_input_set(mod, "Sidewalk Width Right", 5.0); road.update_tag(); w2 = width(road)
        nodes.mod_input_set(mod, "Bike Right", "Protected"); road.update_tag(); t3 = tris(road)
        tests["road_urban"] = {"width_m": w0, "lanes_fwd_3": w1, "sidewalk_5": w2, "tris": t0, "tris_protected_bike": t3}
        check(w1 > w0 + 2.5 and w2 > w1 + 1.0 and t3 != t0, "road parameters do not regenerate the appended road: %s" % tests["road_urban"])
    fb = objs.get("MRS_Asset_Footbridge_Girder")
    if fb is not None:
        mod = next(m for m in fb.modifiers if m.type == "NODES")
        t0 = tris(fb)
        nodes.mod_input_set(mod, "Style", "Truss"); fb.update_tag(); t1 = tris(fb)
        tests["footbridge"] = {"tris_girder": t0, "tris_truss": t1}
        check(t0 > 1000 and t1 != t0, "footbridge style change did not regenerate: %s" % tests["footbridge"])
    res["parameter_tests"] = tests
    print("FRESH", {"appended": res["appended"], "tests": tests, "missing_images": missing_img})
    json.dump(res, open(os.path.join(OUT, "verify.json"), "w"), indent=1)
    print("VERIFY", "OK" if not res["problems"] else "FAILED %d" % len(res["problems"]))


if "--verify" in args:
    try: verify()
    except Exception: traceback.print_exc(); print("VERIFY CRASHED")
else:
    try:
        import mrs
        from mrs import library, qa
        t0 = time.time()
        if os.path.exists(BASE): bpy.ops.wm.open_mainfile(filepath=BASE)
        else: mrs.build_all()
        from mrs import road as _road; _road.build_road_group()          # current road group (driveways)
        summ = library.build_library(LIB)
        summ["build_s"] = round(time.time() - t0, 1)
        print("BUILT", {k: v for k, v in summ.items() if k != "assets"})
        thumbs = [os.path.join(OUT, "thumbnails", a["thumbnail"]) for a in summ["assets"] if a.get("preview")]
        pick = []
        for cat in library.CATALOGS:
            pick += [p for p, a in zip(thumbs, [a for a in summ["assets"] if a.get("preview")]) if a["catalog"] == cat][:4]
        if pick: qa.sheet(pick, os.path.join(OUT, "thumbnails_sheet.jpg"), cols=6)
        B = bpy.app.binary_path
        r = subprocess.run([B, "--background", "--factory-startup", "--python", os.path.abspath(__file__), "--", "--verify"], capture_output=True, text=True, timeout=1800)
        for line in r.stdout.splitlines():
            if line.startswith(("LIBRARY", "FRESH", "VERIFY", "PROBLEM")): print(line[:600])
        v = json.load(open(os.path.join(OUT, "verify.json"))) if os.path.exists(os.path.join(OUT, "verify.json")) else {"problems": ["verify crashed"]}
        json.dump({"build": summ, "verify": v}, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        print("ASSET_LIBRARY", "OK" if not v.get("problems") else "FAILED")
    except Exception:
        traceback.print_exc(); print("ASSET_LIBRARY CRASHED")
