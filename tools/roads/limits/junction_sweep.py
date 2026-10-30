"""Junction limit sweeps (phase B2 of docs/roads/READY.md): approach angle x road width x corner radius x arms.

    blender --background tmp/roads/city/base.blend --python tools/roads/limits/junction_sweep.py -- <out_dir> [--tag before]
        [--quick]

Layouts: a 2-arm bend junction (two roads leaving one point at angle A), a 3-arm junction (a straight through road and a branch at angle A from it) and a 4-arm crossing (the cross
road at angle A); presets residential (one lane each way, 2 m sidewalks) and arterial (two lanes each way, bike lanes,
wider sidewalks); corner radius R. For every build: the junction builds (no exception), mrs.validate finds no problem
on the junction and its roads (markings, signals, end markings, crossings) and no two surfaces overlap
(validate.check_overlaps, 1 m grid, OVERLAP_MIN cells), and the junction's own surface does not fold over itself.
Angles are swept densely; each preset / radius / arms boundary is bisected to 0.5 degrees and confirmed.
Writes <out_dir>/junction_<tag>.json."""
import bpy, json, math, os, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads")); sys.path.insert(0, HERE)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "limits"))
TAG = argv[argv.index("--tag") + 1] if "--tag" in argv else "run"
QUICK = "--quick" in argv
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
import checks as C
from mrs import roads, nodes, junction, validate
from mrs.nodes import mod_input_set
if "--no-angle-limit" in argv: junction.MIN_APPROACH_ANGLE = 1.0       # find where the geometry itself fails

L = 70.0
PRESETS = {"residential": {}, "arterial": {"Lanes Forward": 2, "Lanes Backward": 2, "Bike Left": "Painted", "Bike Right": "Painted",
                                            "Sidewalk Width Left": 3.0, "Sidewalk Width Right": 3.0}}


def build(sc_col, arms, angle, preset, radius, control):
    """Fresh roads + junction for one case; returns (junction object or None, roads, error)."""
    for o in list(sc_col.all_objects): bpy.data.objects.remove(o, do_unlink=True)
    for c in list(sc_col.children): bpy.data.collections.remove(c)
    over = dict(Conform=False, Embankment=False, Props=None, Trees=None, Streetlights=None, Scatter=None, **PRESETS[preset])
    dirs = {2: [0.0, angle], 3: [0.0, 180.0, angle], 4: [0.0, 180.0, angle, angle + 180.0]}[arms]
    rs = []
    for k, a in enumerate(dirs):
        d = (math.cos(math.radians(a)), math.sin(math.radians(a)))
        rs.append(roads.make_road("JS_R%d" % k, [(d[0] * L, d[1] * L, 0.0), (0.0, 0.0, 0.0)], sc_col, "residential", **over))
    try:
        j = junction.build_junction("JS_J", (0.0, 0.0, 0.0), rs, sc_col, corner_radius=radius, control=control, traffic_lights=(control == "signals"),
                                    crossing="zebra", snap=1.0, z=0.0)
        return j, rs, None
    except Exception as e:
        return None, rs, "%s: %s" % (type(e).__name__, str(e)[:200])


def check_case(col, j, rs, err):
    if err: return {"build": [err]}
    dg = bpy.context.evaluated_depsgraph_get(); validate._CACHE.clear()
    out = []
    by = {r.name: r for r in rs}
    inst = validate._instances(dg)
    for r in rs: validate.check_road(r, dg, inst, out)
    validate.check_junction(j, dg, out, by)
    validate.check_overlaps(col, dg, out)
    res = {"validate": ["%s %s" % (p["check"], p["message"]) for p in out if p["check"] != "overlap"],
           "overlap": ["%s" % p["message"] for p in out if p["check"] == "overlap"]}
    md = C.mesh_data(j, dg)
    res["junction_fold"] = C.check_fold(md)
    res["junction_flipped"] = C.check_flipped(md)
    for r in rs:
        rmd = C.mesh_data(r, dg)
        f = C.check_fold(rmd)
        if f: res.setdefault("road_fold", []).extend("%s: %s" % (r.name, x) for x in f)
    return res


def ok(res): return all(not v for v in res.values())


def build_pair(sc_col, gap, preset, control):
    """Two 3-arm junctions `gap` m apart (centre to centre) joined by one road, each on a 70 m through road: the
    connecting road keeps gap - trim1 - trim2. Returns (junctions, roads, error, remaining)."""
    for o in list(sc_col.all_objects): bpy.data.objects.remove(o, do_unlink=True)
    over = dict(Conform=False, Embankment=False, Props=None, Trees=None, Streetlights=None, Scatter=None, **PRESETS[preset])
    rs = []; js = []
    for k, y in enumerate((0.0, gap)):
        rs.append(roads.make_road("JS_W%d" % k, [(-L, y, 0.0), (0.0, y, 0.0)], sc_col, "residential", **over))
        rs.append(roads.make_road("JS_E%d" % k, [(L, y, 0.0), (0.0, y, 0.0)], sc_col, "residential", **over))
    link = roads.make_road("JS_LINK", [(0.0, 0.0, 0.0), (0.0, gap, 0.0)], sc_col, "residential", **over); rs.append(link)
    try:
        for k, y in enumerate((0.0, gap)):
            js.append(junction.build_junction("JS_J%d" % k, (0.0, y, 0.0), [rs[2 * k], rs[2 * k + 1], link], sc_col, corner_radius=6.0, control=control,
                                              traffic_lights=(control == "signals"), crossing="zebra", snap=1.0, z=0.0))
        from mrs.nodes import mod_input_get
        rem = gap - mod_input_get(link.modifiers["MRS_Road"], "Trim Start") - mod_input_get(link.modifiers["MRS_Road"], "Trim End")
        return js, rs, None, rem
    except Exception as e:
        return js, rs, "%s: %s" % (type(e).__name__, str(e)[:240]), None


def check_pair(col, js, rs, err):
    if err: return {"build": [err]}
    dg = bpy.context.evaluated_depsgraph_get(); validate._CACHE.clear(); out = []
    by = {r.name: r for r in rs}; inst = validate._instances(dg)
    for r in rs: validate.check_road(r, dg, inst, out)
    for j in js: validate.check_junction(j, dg, out, by)
    validate.check_overlaps(col, dg, out)
    res = {"validate": ["%s %s" % (p["check"], p["message"]) for p in out if p["check"] != "overlap"],
           "overlap": [p["message"] for p in out if p["check"] == "overlap"]}
    for j in js:
        md = C.mesh_data(j, dg); res.setdefault("junction_fold", []).extend(C.check_fold(md))
    return res


def length_sweep(col, records):
    """The shortest road between two junctions that still passes every check, per preset and control."""
    summary = {}
    for preset in PRESETS:
        for control in ("signals", "stop", "priority"):
            def run(gap):
                js, rs, err, rem = build_pair(col, gap, preset, control)
                try: res = check_pair(col, js, rs, err)
                except Exception as e: res = {"check_exception": ["%s: %s" % (type(e).__name__, str(e)[:200])]}
                rec = {"mode": "length", "preset": preset, "control": control, "gap": round(gap, 3), "remaining": rem, "pass": ok(res),
                       "problems": {k: v[:4] for k, v in res.items() if v}}
                records.append(rec); return rec
            gaps = [10.0 + 2.5 * k for k in range(29)]          # 10 .. 80 m centre to centre
            res = {g: run(g) for g in gaps}
            good = max(gaps); bad = None
            for g in sorted(gaps, reverse=True):
                if res[g]["pass"]: good = g
                else: bad = g; break
            if bad is not None:
                while good - bad > 0.25:
                    m = (good + bad) * 0.5
                    if run(m)["pass"]: good = m
                    else: bad = m
            conf = [run(good + 0.5 * k) for k in range(1, 6)]
            rem_good = next(r["remaining"] for r in reversed(records) if r["gap"] == round(good, 3) and r["preset"] == preset and r["control"] == control and r["pass"])                 if any(r["gap"] == round(good, 3) and r["pass"] and r["preset"] == preset and r["control"] == control for r in records) else None
            key = "%s %s" % (preset, control)
            first_bad = next((r for r in records if r["preset"] == preset and r["control"] == control and r["gap"] == round(bad, 3)), None) if bad else None
            summary[key] = {"min_pass_gap": good, "max_fail_gap": bad, "remaining_at_min": rem_good, "confirm_fail": [r["gap"] for r in conf if not r["pass"]],
                            "fail_reason": first_bad["problems"] if first_bad else None}
            print("LENGTH %-24s min gap %.2f m (remaining %s m), last fail %s: %s%s" % (key, good, "%.2f" % rem_good if rem_good is not None else "?", bad,
                  json.dumps(first_bad["problems"])[:300] if first_bad else "", "  CONFIRM FAIL" if summary[key]["confirm_fail"] else ""))
    return summary


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.data.scenes.new("JunctionSweep"); nodes.set_scene(sc)
    try: bpy.context.window.scene = sc
    except Exception: pass
    col = bpy.data.collections.new("JS_Roads"); sc.collection.children.link(col)
    junction._pending.clear() if hasattr(junction, "_pending") else None
    records = []; t0 = time.time()
    if "--length" in argv:
        summary = length_sweep(col, records)
        with open(os.path.join(OUT, "junction_length_%s.json" % TAG), "w") as f: json.dump({"summary": summary, "records": records}, f, indent=1, default=str)
        print("LENGTH_SWEEP done %d builds %.0fs" % (len(records), time.time() - t0)); return
    def run(arms, angle, preset, radius, control="signals"):
        j, rs, err = build(col, arms, angle, preset, radius, control)
        try: res = check_case(col, j, rs, err)
        except Exception as e: res = {"check_exception": ["%s: %s" % (type(e).__name__, str(e)[:200])]}
        rec = {"arms": arms, "angle": round(angle, 3), "preset": preset, "radius": radius, "control": control,
                                                   "pass": ok(res), "problems": {k: v[:4] for k, v in res.items() if v}}
        records.append(rec); return rec["pass"]
    # self-test: right angles pass for every preset / arms
    ARMS = tuple(int(a) for a in (argv[argv.index("--arms") + 1] if "--arms" in argv else "2,3,4").split(","))
    for arms in ARMS:
        for preset in PRESETS:
            p = run(arms, 90.0, preset, 6.0)
            print("SELFTEST arms %d %s 90 deg: %s %s" % (arms, preset, "OK" if p else "FAIL", "" if p else json.dumps(records[-1]["problems"])[:600]))
    angles = [5.0 + 2.5 * k for k in range(35)] if not QUICK else [20.0, 30.0, 45.0, 60.0, 90.0]
    radii = [3.0, 6.0, 12.0] if not QUICK else [6.0]
    summary = {}
    for arms in ARMS:
        for preset in PRESETS:
            for radius in radii:
                res = {a: run(arms, a, preset, radius) for a in angles}
                fails = [a for a in angles if not res[a]]; passes_ = [a for a in angles if res[a]]
                # the boundary: the largest failing angle below the smallest all-pass run up to 90
                good = 90.0; bad = None
                for a in sorted(angles, reverse=True):
                    if res[a]: good = a
                    else: bad = a; break
                if bad is not None:
                    while good - bad > 0.5:
                        m = (good + bad) * 0.5
                        if run(arms, m, preset, radius): good = m
                        else: bad = m
                    conf = [good + 0.5 * k for k in range(1, 6)]
                    conf_fail = [a for a in conf if not run(arms, a, preset, radius)]
                else:
                    conf_fail = []
                key = "%d-arm %s R%g" % (arms, preset, radius)
                summary[key] = {"min_pass_angle": good, "max_fail_angle": bad, "grid_fails": fails, "confirm_fail": conf_fail}
                print("JUNCTION %-26s min angle %.1f (last fail %s) grid fails %s%s" % (key, good, bad, fails, "  CONFIRM FAIL %s" % conf_fail if conf_fail else ""))
                with open(os.path.join(OUT, "junction_%s.json" % TAG), "w") as f: json.dump({"summary": summary, "records": records}, f, indent=1, default=str)
    print("JUNCTION_SWEEP done %d builds %.0fs" % (len(records), time.time() - t0))

main()
