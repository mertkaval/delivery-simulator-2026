"""Combination sweep (phase B6): the tightest bend a road of a given width takes before its surface folds.
    blender --background tmp/roads/city/base.blend --python tools/roads/limits/bend_sweep.py -- <out_dir>
For road profiles from a narrow lane to a wide avenue, the bend radius R (a 120 degree arc between 30 m straights)
is bisected between a passing and a failing value (to 1 % of R) and confirmed by five larger radii; the checks are
the geometric ones of checks.py (eval, flipped, degenerate, fold, width). The outer half width H of a profile is the
widest side: half carriageway + kerb + sidewalk. Result: R_fail / H per profile; the rule (validate, the modifier
warning) is R >= max(R_fail / H) x H x (1 + MARGIN) (the user's 10 % of the boundary value).
Writes <out_dir>/bend_sweep.json."""
import bpy, json, math, os, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads")); sys.path.insert(0, HERE)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "limits"))
MARGIN = 0.10; REFINE = 0.01
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
import checks as C
from mrs import roads, nodes

PROFILES = [
    ("lane 1+0, no sidewalks", {"Lanes Forward": 1, "Lanes Backward": 0, "Sidewalk Left": False, "Sidewalk Right": False}),
    ("1+1, sidewalks 2 m", {}),
    ("1+1, sidewalks 8 m", {"Sidewalk Width Left": 8.0, "Sidewalk Width Right": 8.0}),
    ("2+2, sidewalks 3 m", {"Lanes Forward": 2, "Lanes Backward": 2, "Sidewalk Width Left": 3.0, "Sidewalk Width Right": 3.0}),
    ("2+2, median 2 m, parking", {"Lanes Forward": 2, "Lanes Backward": 2, "Median": 2.0, "Parking Left": 2.2, "Parking Right": 2.2}),
    ("3+3, buffered cycle lanes, sidewalks 4 m", {"Lanes Forward": 3, "Lanes Backward": 3, "Bike Left": "Buffered", "Bike Right": "Buffered",
                                                  "Sidewalk Width Left": 4.0, "Sidewalk Width Right": 4.0}),
    ("1+1, banked 12 deg", {"Superelevation": 12.0}),
    ("1+1, one sidewalk 6 m (asymmetric)", {"Sidewalk Left": False, "Sidewalk Width Right": 6.0}),
]
WHICH = ("eval", "flipped", "degenerate", "fold", "width")


def bend(R):
    """30 m straight, a 120 degree arc of radius R (points every <= 1 m), 30 m straight."""
    pts = [(-30.0, -R, 0.0), (0.0, -R, 0.0)]
    n = max(12, int(math.ceil(R * 2.0 * math.pi / 3.0)))
    for k in range(1, n + 1):
        a = -math.pi / 2 + (2.0 * math.pi / 3.0) * k / n
        pts.append((R * math.cos(a), R * math.sin(a), 0.0))
    a1 = -math.pi / 2 + 2.0 * math.pi / 3.0
    t = (-math.sin(a1), math.cos(a1))
    pts.append((pts[-1][0] + t[0] * 30.0, pts[-1][1] + t[1] * 30.0, 0.0))
    return pts


def run(col, ov, R):
    for o in list(col.objects): bpy.data.objects.remove(o)
    o = roads.make_road("BS_Road", bend(R), col, "residential", Conform=False, Embankment=False, **ov)
    dg = bpy.context.evaluated_depsgraph_get()
    try: res = C.road_checks(o, dg, WHICH)
    except Exception: res = {"exception": [traceback.format_exc(limit=2).strip().splitlines()[-1]]}
    probs = {k: v for k, v in res.items() if v}
    return not probs, probs, roads.road_widths(o)


def main():
    sc = bpy.data.scenes.new("BendSweep"); nodes.set_scene(sc)
    try: bpy.context.window.scene = sc
    except Exception: pass
    col = bpy.data.collections.new("BS_Roads"); sc.collection.children.link(col)
    out = {"profiles": []}; t0 = time.time()
    for label, ov in PROFILES:
        ok_hi, p_hi, w = run(col, ov, 200.0)
        H = max(w["half_l"] + w["curb"] + w["swl"], w["half_r"] + w["curb"] + w["swr"])
        rec = {"profile": label, "overrides": ov, "H": round(H, 3), "evals": []}
        if not ok_hi:
            rec["error"] = "fails at R 200 m: %s" % p_hi; out["profiles"].append(rec); print("PROFILE", label, rec["error"]); continue
        good, bad = 200.0, 0.5
        ok_lo, p_lo, _ = run(col, ov, bad); rec["evals"].append({"R": bad, "pass": ok_lo, "problems": p_lo})
        if ok_lo:
            rec["R_fail"] = None; rec["note"] = "passes down to R 0.5 m"
        else:
            while good - bad > max(REFINE * good, 0.01):
                m = (good + bad) * 0.5; ok, p, _ = run(col, ov, m); rec["evals"].append({"R": round(m, 4), "pass": ok, "problems": p})
                if ok: good = m
                else: bad = m; rec["fail_problems"] = p
            conf = [good * (1.0 + 0.05 * k) for k in range(1, 6)]
            cf = [r for r in conf if not run(col, ov, r)[0]]
            rec.update({"R_fail": round(bad, 3), "R_pass": round(good, 3), "ratio": round(bad / H, 4), "confirm_failures": [round(r, 3) for r in cf]})
        out["profiles"].append(rec)
        print("PROFILE %-42s H %.2f m  R_fail %s  ratio %s%s" % (label, H, rec.get("R_fail"), rec.get("ratio"),
              "" if not rec.get("confirm_failures") else "  CONFIRM FAILS %s" % rec["confirm_failures"]))
    ratios = [p["ratio"] for p in out["profiles"] if p.get("ratio") is not None]
    if ratios:
        out["ratio_max"] = max(ratios); out["rule_ratio"] = round(max(ratios) * (1.0 + MARGIN), 4)
        print("BEND RULE: R >= %.3f x H (worst R_fail / H %.3f, + 10 %%)" % (out["rule_ratio"], out["ratio_max"]))
    out["seconds"] = round(time.time() - t0, 1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "bend_sweep.json"), "w") as f: json.dump(out, f, indent=1, default=str)
    print("BEND_SWEEP done in %.0fs" % out["seconds"])

main()
