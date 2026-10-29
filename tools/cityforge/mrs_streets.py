"""Port Halden's streets by Mert Road Studio (Blender, headless): the CityForge plan -> MRS roads, junctions,
back lanes, rule-placed street assets -> per-chunk GLBs + records for the game (assets/cityforge/mrs) and the
plan for build_city.py with CityForge's own streets and street furniture taken out.

    blender --background --factory-startup --python tools/cityforge/mrs_streets.py -- <plan_dir> <out_dir>
            [--region x0,y0,x1,y1] [--no-place] [--no-export] [--blend <file.blend>] [--from-blend <saved build>] [--plan-only] [--profile]

The MRS base library (node groups, materials, asset collections) is built once into tmp/roads/city/base.blend
(~6 min); later runs open it."""
import bpy, json, os, sys, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PLAN, OUT = argv[0], argv[1]
opts = argv[2:]
def opt(name, default=None):
    return opts[opts.index(name) + 1] if name in opts else default

BASE = os.path.join(ROOT, "tmp", "roads", "city", "base.blend")
try: sys.stdout.reconfigure(line_buffering=True)      # progress lines reach a redirected log as they happen
except Exception: pass
os.makedirs(OUT, exist_ok=True)
t0 = time.time()
try:
    import mrs
    from mrs import city
    mrs = city.ensure_base(BASE, rebuild="--rebuild-base" in opts)
    region = tuple(float(v) for v in opt("--region").split(",")) if opt("--region") else None
    prof = None
    if "--profile" in opts:
        import cProfile; prof = cProfile.Profile(); prof.enable()
    if opt("--from-blend"):
        # rerun the export / plan from a saved build (no street rebuild); the placement report is not in the blend
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(opt("--from-blend")))
        net = city.load_state(PLAN, region)
    else:
        net = city.build(PLAN, region=region, place="--no-place" not in opts)
    print("TIMINGS", json.dumps(city.STATE["timings"], default=str)[:2000])
    if "--plan-only" in opts:
        print("PLAN_ONLY", json.dumps(city.plan_only(OUT), default=str))
    elif "--no-export" not in opts:
        stats = city.export(OUT)
        print("EXPORT", json.dumps(stats, default=str)[:3000])
    if prof is not None:
        import pstats, io
        prof.disable(); buf = io.StringIO(); pstats.Stats(prof, stream=buf).sort_stats("cumulative").print_stats(35); print(buf.getvalue()[:12000])
    blend = opt("--blend")
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend), compress=True)
        print("SAVED", blend)
    print("MRS_STREETS OK %.0fs" % (time.time() - t0))
except Exception:
    traceback.print_exc()
    print("MRS_STREETS FAILED")
    sys.exit(1)
