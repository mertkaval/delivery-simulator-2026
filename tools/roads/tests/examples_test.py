"""Every example scene (mrs.samples.ALL, the add-on's Load Example list) builds and validates with no problem: the
examples a user starts from are themselves proof that the tool works.
    blender --background tmp/roads/city/base.blend --python tools/roads/tests/examples_test.py -- <out_dir> [--only a,b]
For each example: build it, run the street-asset placement where the example has none of its own, validate (roads,
junctions, overlaps, placed objects, combination warnings, tongues). Writes <out_dir>/examples.json and prints
EXAMPLES OK or EXAMPLES FAIL with the problems."""
import bpy, json, os, sys, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "examples")); os.makedirs(OUT, exist_ok=True)
ONLY = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
from mrs import samples, validate, placement
from mrs.nodes import set_scene

report = {}; bad = 0
for name, fn in samples.ALL.items():
    if ONLY and name not in ONLY: continue
    t0 = time.time()
    try:
        sc = fn(); set_scene(sc)
        try: bpy.context.window.scene = sc
        except Exception: pass
        col = next(c for c in sc.collection.children if c.name.endswith("_Roads"))
        placed = bpy.data.collections.get(col.name + "_Placed")
        if placed is None or not len(placed.all_objects):
            placement.place_all(col, seed=1, style="avenue"); placed = bpy.data.collections.get(col.name + "_Placed")
        res = validate.validate(col, placed)
        probs = res["problems"]
        report[name] = {"roads": res["roads"], "junctions": res["junctions"], "placed": res.get("placed"), "counts": res["counts"],
                        "problems": probs[:60], "seconds": round(time.time() - t0, 1)}
        print("EXAMPLE %-20s roads %3d junctions %3d placed %4s problems %3d %s (%.0fs)" % (name, res["roads"], res["junctions"], res.get("placed"), len(probs),
              json.dumps(res["counts"]), time.time() - t0))
        for p in probs[:12]: print("   PROBLEM", p["check"], p["object"], p["message"][:180])
        bad += len(probs)
    except Exception:
        tb = traceback.format_exc(); report[name] = {"error": tb}; bad += 1
        print("EXAMPLE %-20s ERROR\n%s" % (name, tb))
with open(os.path.join(OUT, "examples.json"), "w") as f: json.dump(report, f, indent=1, default=str)
print("EXAMPLES OK" if not bad else "EXAMPLES FAIL (%d problems)" % bad)
