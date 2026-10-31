"""PM_Asphalt in Mert Road Studio (proof that the road tool can use it; nothing is saved, the game is not touched).

    blender --background --factory-startup tmp/roads/city/base.blend --python road_check.py -- --library LIB.blend --out DIR

LIB.blend: a procmat library saved by run.py (build asphalt --save LIB.blend). In base.blend (opened read-only, never
saved) this script: appends PM_Asphalt from the library (core.append_materials), builds a residential road with the
road tool's own make_road() in a new scene, assigns PM_Asphalt to the road's "Asphalt Material" socket
(road_adapter.assign: Asphalt Condition -> Default), checks the evaluated road mesh, checks that the road tool's
apply_material_preset() leaves the PM inputs alone (no shared input names), set_road() + road_adapter.reapply(), bakes
an in-memory copy named MRS_* with the road tool's own bake_tiles() (contract compatibility), and renders the road at
eye level in EEVEE and Cycles. Prints ROAD_CHECK OK / FAIL lines and writes DIR/road_check.json."""
import argparse
import json
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
RESULTS = []


def check(name, ok, info=None):
    RESULTS.append({"check": name, "ok": bool(ok), "info": info})
    print("ROAD_CHECK %s %s: %s" % ("OK" if ok else "FAIL", name, json.dumps(info, default=str)[:600]))
    return ok


def main(argv):
    p = argparse.ArgumentParser(); p.add_argument("--library", required=True); p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True); t0 = time.time()
    check("base library opened", bpy.data.filepath.replace("\\", "/").endswith("tmp/roads/city/base.blend") and "MRS_Road" in bpy.data.node_groups,
          bpy.data.filepath)
    sys.dont_write_bytecode = True                      # nothing is written under tools/roads (read-only here)
    sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
    from mrs import roads, nodes as mrs_nodes, materials as mrs_materials
    sys.path.insert(0, os.path.join(ROOT, "tools", "materials"))
    from procmat import core, imaging, rig, road_adapter as RA
    mats = core.append_materials(os.path.abspath(a.library), ["PM_Asphalt"])
    mat = bpy.data.materials.get("PM_Asphalt")
    check("PM_Asphalt appended from the saved library, contract intact", mat is not None and not core.check_contract(mat),
          {"appended": [m.name for m in mats], "problems": core.check_contract(mat) if mat else "missing"})
    sc = bpy.data.scenes.new("PM_AsphaltRoadCheck"); mrs_nodes.set_scene(sc)
    col = bpy.data.collections.new("PMA_Roads"); sc.collection.children.link(col)
    road = roads.make_road("PMA_Road", [(-30.0, 0.0, 0.0), (0.0, 0.0, 0.0), (30.0, 0.0, 0.0)], col, "residential",
                           Conform=False, Embankment=False)
    ev0 = RA.evaluated_materials(road)
    check("road built by the road tool, its own asphalt", any(k.startswith("MRS_Asphalt") for k in ev0), ev0)
    rep = RA.assign(road, "Asphalt Material", mat)
    ev1 = RA.evaluated_materials(road)
    check("assign(Asphalt Material, PM_Asphalt): the evaluated road surface carries PM_Asphalt",
          ev1.get("PM_Asphalt", 0) > 0 and not any(k.startswith("MRS_Asphalt") for k in ev1), {"report": rep, "evaluated": ev1})
    node = core.group_node(mat)
    snap = lambda: {s.name: (tuple(s.default_value) if hasattr(s.default_value, "__len__") else s.default_value)
                    for s in node.inputs if hasattr(s, "default_value")}
    before = snap()
    for preset in ("heavy_wear", "wet"):
        mrs_materials.apply_material_preset(preset)
    check("the road tool's material presets leave PM_Asphalt's inputs alone (no shared input names)", snap() == before,
          {k: v for k, v in snap().items() if before.get(k) != v})
    roads.set_road(road)
    ev2 = RA.evaluated_materials(road)
    RA.reapply(col)
    ev3 = RA.evaluated_materials(road)
    check("set_road() puts MRS_* back, reapply() restores PM_Asphalt", "PM_Asphalt" not in ev2 and ev3.get("PM_Asphalt", 0) > 0,
          {"after set_road": ev2, "after reapply": ev3})
    # the road tool's own baker on the PM contract (it only looks up MRS_<suffix> names: an in-memory copy)
    try:
        cp = mat.copy(); cp.name = "MRS_PMAsphaltCheck"
        with bpy.context.temp_override(scene=sc, view_layer=sc.view_layers[0]):
            res = mrs_materials.bake_tiles(os.path.join(a.out, "bake_tiles"), res=512, samples=8, tile=4.0, materials=["PMAsphaltCheck"])
        paths = res.get("MRS_PMAsphaltCheck", {})
        seam = imaging.seam_metric(paths["albedo"]) if "albedo" in paths else None
        check("the road tool's bake_tiles() bakes the PM contract (copy named MRS_PMAsphaltCheck): albedo / normal / roughness, seamless",
              set(paths) >= {"albedo", "normal", "roughness"} and seam is not None and imaging.is_seamless(seam),
              {"maps": sorted(paths), "seam_albedo": seam})
        bpy.data.materials.remove(cp)
    except Exception as e:  # reported, not hidden
        check("the road tool's bake_tiles() bakes the PM contract", False, repr(e))
    # eye-level renders of the road (the test scene only)
    cam = bpy.data.objects.new("PMA_Camera", bpy.data.cameras.new("PMA_Camera")); col.objects.link(cam); cam.data.lens = 30.0
    rig.look_at(cam, (-33.0, -2.2, 1.7), (0.0, 1.0, 0.0)); sc.camera = cam
    rig.world(sc, "city", 1.0, 0.0)
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    try: sc.view_settings.view_transform = "AgX"
    except TypeError: pass
    out = {}
    for eng, smp in (("EEVEE", 64), ("CYCLES", 96)):
        rig.set_engine(sc, eng, smp)
        out[eng] = rig.render(os.path.join(a.out, "PM_Asphalt_mrs_road_%s.png" % eng.lower()), scene=sc)
        check("eye-level render of an MRS road with PM_Asphalt (%s)" % eng, imaging.stats(out[eng])["std"] > 0.02, dict(imaging.stats(out[eng]), path=out[eng]))
    ok = all(r["ok"] for r in RESULTS)
    with open(os.path.join(a.out, "road_check.json"), "w") as f:
        json.dump({"ok": ok, "seconds": round(time.time() - t0, 1), "checks": RESULTS}, f, indent=1, default=str)
    print("ROAD_CHECK %s (%d checks, %.1fs; base.blend not saved)" % ("ALL OK" if ok else "FAILED", len(RESULTS), time.time() - t0))
    return ok


if __name__ == "__main__":
    good = main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    sys.stdout.flush()
    sys.exit(0 if good else 1)
