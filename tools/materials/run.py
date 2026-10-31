"""procmat command line (headless Blender; never the user's open Blender):

    blender --background --factory-startup --python tools/materials/run.py -- build <key|all> [--render DIR] [--bake DIR]
            [--save FILE.blend] [--dump DIR] [--views sphere,road] [--engine EEVEE|CYCLES] [--res 800] [--samples 64]
            [--hdri city] [--strength 1.0] [--rotation 0] [--lights] [--tile 4.0] [--bake-res 1024] [--bake-samples 16]
            [--assets] [--periodicity] [--scene]
    blender --background --factory-startup --python tools/materials/run.py -- list

build   : imports procmat and its material modules (procmat.asphalt, procmat.cobblestone, procmat.glass when they
          exist: a missing one is skipped with a message), builds <key> (or every library module with "all"),
          checks the contract, then in this order: --save (a clean library .blend, materials with fake users,
          --assets marks them as assets), --dump (graphdump Markdown per material), --render (rig.preview renders,
          object mode) and --bake (seamless UV-mode tiles + seam metric + a 2 x 2 tile preview; --periodicity adds the
          direct repeat test: a bake with the UVs shifted by (0.5, 0.25) must equal the rolled tile).
views   : sphere, sphere45, plane, plane_hd (300 x 300 quads, for displacement), cube, pane (vertical glass pane),
          road (7 m x 20 m strip, eye level 1.7 m), road_top.
--scene : with --save, the saved file's scene becomes "PM_Library": one preview object per material (a 1 m icosphere,
          a vertical pane for glass materials, the displaced cobblestone on a plane with a
          Simple subdivision modifier, 256 x 256 quads at render), a camera and a
          bundled-HDRI world (the EXR is referenced, not packed), EEVEE.
Prints "RUN OK" / "RUN FAIL" at the end; the exit code is 0 / 1.
"""
import argparse
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass

import bpy  # noqa: E402

import procmat  # noqa: E402
from procmat import bake as B, core, graphdump, rig  # noqa: E402


def _args(argv):
    p = argparse.ArgumentParser(prog="run.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build <key|all>")
    b.add_argument("key")
    b.add_argument("--render"); b.add_argument("--bake"); b.add_argument("--save"); b.add_argument("--dump")
    b.add_argument("--views", default="sphere,road"); b.add_argument("--engine", default="EEVEE")
    b.add_argument("--res", type=int, default=800); b.add_argument("--samples", type=int, default=64)
    b.add_argument("--hdri", default="city"); b.add_argument("--strength", type=float, default=1.0)
    b.add_argument("--rotation", type=float, default=0.0); b.add_argument("--lights", action="store_true")
    b.add_argument("--tile", type=float, default=4.0); b.add_argument("--bake-res", type=int, default=1024)
    b.add_argument("--bake-samples", type=int, default=16); b.add_argument("--assets", action="store_true")
    b.add_argument("--periodicity", action="store_true"); b.add_argument("--scene", action="store_true")
    sub.add_parser("list", help="list the material modules")
    return p.parse_args(argv)


def _clean_factory_scene():
    """A --factory-startup file holds the default Cube / Light / Camera: drop them before saving a library."""
    if bpy.data.filepath: return
    for n in ("Cube", "Light", "Camera"):
        o = bpy.data.objects.get(n)
        if o is not None: bpy.data.objects.remove(o)
    for coll, n in ((bpy.data.meshes, "Cube"), (bpy.data.materials, "Material"), (bpy.data.cameras, "Camera"), (bpy.data.lights, "Light")):
        d = coll.get(n)
        if d is not None and d.users == 0: coll.remove(d)


def _preview_scene(mats, hdri="city"):
    """The library's preview scene in the file's own scene (renamed PM_Library): one object per material in a grid,
    a camera framing them, the bundled HDRI world. Returns the scene."""
    import math
    from mathutils import Vector
    sc = bpy.context.scene; sc.name = "PM_Library"
    for c in list(sc.collection.children):                 # the factory file's empty "Collection"
        if not c.all_objects and not c.children: bpy.data.collections.remove(c)
    rig.set_engine(sc, "EEVEE", 64); rig.world(sc, hdri, 1.0, 0.0)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    try: sc.view_settings.view_transform = "AgX"
    except TypeError: pass
    cols = 5; dx = 2.8; dy = 3.2; objs = []
    for i, m in enumerate(mats):
        cx = (i % cols - (cols - 1) / 2.0) * dx; cy = (i // cols) * dy
        name = "PMV_" + m.name[3:]
        if (m.get("procmat") or "").startswith("PM_Glass") or m.name.startswith("PM_Glass"):
            ob = rig.pane(sc, 1.6, 2.0, (cx, cy, 0.0), name)
        elif m.displacement_method in ("DISPLACEMENT", "BOTH"):
            ob = rig.plane(sc, 2.0, 1.0, 0, (cx, cy, 0.0), name); ob.rotation_euler = (math.radians(60.0), 0.0, 0.0); ob.location.z = 1.0
            sub = ob.modifiers.new("PMV_Dense", "SUBSURF"); sub.subdivision_type = "SIMPLE"   # dense at render, small file
            sub.levels = 6; sub.render_levels = 8
        else:
            ob = rig.icosphere(sc, 6, 1.0, (cx, cy, 1.0), name)
        rig.assign(ob, m); ob["pm_material"] = m.name; objs.append(ob)
    rows = (len(mats) + cols - 1) // cols
    c = Vector((0.0, (rows - 1) * dy / 2.0, 1.0))
    cam = bpy.data.objects.new("PMV_Camera", bpy.data.cameras.new("PMV_Camera")); rig.collection(sc).objects.link(cam)
    cam.data.lens = 35.0; rig.look_at(cam, c + Vector((0.0, -15.5, 6.0)), c); sc.camera = cam
    return sc


def main(argv):
    a = _args(argv)
    status = procmat.discover()
    print("[run] modules:", json.dumps(status))
    if a.cmd == "list":
        for k, m in sorted(procmat.MATERIALS.items()):
            print("  %-14s %s%s" % (k, m.__name__, "" if getattr(m, "LIBRARY", True) else "  (not in 'all')"))
        return True
    keys = procmat.library_keys() if a.key == "all" else [a.key]
    if not keys:
        print("[run] no library material modules yet"); return False
    ok = True; built = []
    for k in keys:
        t = time.time()
        try:
            mats = procmat.build(k)
        except Exception:
            print("[run] build %s FAILED:\n%s" % (k, traceback.format_exc())); ok = False; continue
        for m in mats:
            prob = core.check_contract(m)
            print("[run] built %-24s %5.1fs contract %s" % (m.name, time.time() - t, "OK" if not prob else "PROBLEMS %s" % prob))
            ok &= not prob
        built += mats
    if a.save:
        _clean_factory_scene()
        if a.scene: print("[run] preview scene", _preview_scene(built, a.hdri).name, len(built), "objects")
        if a.assets:
            for m in built:
                try: m.asset_mark(); m.asset_data.tags.new("procmat")
                except Exception as e: print("[run] asset_mark %s: %s" % (m.name, e))
        path = os.path.abspath(a.save); os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=True, relative_remap=False)   # bundled HDRI: absolute path
        print("[run] saved", path)
    if a.dump:
        for m in built: print("[run] dump", graphdump.write(m, os.path.join(a.dump, "%s_NODES.md" % m.name)))
    if a.render:
        views = [v.strip() for v in a.views.split(",") if v.strip()]
        for m in built:
            try:
                out = rig.preview(m, a.render, views, a.engine, a.res, a.samples, a.hdri, a.strength, a.rotation, lights=a.lights)
                print("[run] rendered", m.name, json.dumps({k: os.path.basename(v) for k, v in out.items()}))
            except Exception:
                print("[run] render %s FAILED:\n%s" % (m.name, traceback.format_exc())); ok = False
    if a.bake:
        for m in built:
            try:
                paths = B.bake(m, a.bake, tile=a.tile, res=a.bake_res, samples=a.bake_samples)
                for key in ("albedo", "normal"):
                    if key in paths: print("[run] seam %s %s %s" % (m.name, key, json.dumps(B.seam_metric(paths[key]))))
                if "albedo" in paths: B.tile_preview(paths["albedo"], 2)
                if a.periodicity:
                    pr = B.periodicity(m, os.path.join(a.bake, "periodicity"), tile=a.tile, res=512, samples=a.bake_samples)
                    good = B.is_periodic(pr); ok &= good
                    print("[run] periodicity %s %s %s" % (m.name, "OK" if good else "FAIL",
                                                          json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "files"} for k, v in pr.items()})))
            except Exception:
                print("[run] bake %s FAILED:\n%s" % (m.name, traceback.format_exc())); ok = False
    return ok


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        good = main(argv)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc(); good = False
    print("RUN OK" if good else "RUN FAIL")
    sys.stdout.flush()
    sys.exit(0 if good else 1)
