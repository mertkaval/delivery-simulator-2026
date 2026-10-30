"""Parameter-limit sweeps for MRS_Road (phase B1 of docs/roads/READY.md).

    blender --background tmp/roads/city/base.blend --python tools/roads/limits/sweep.py -- <out_dir> [--params A,B] [--grid 21]
        [--selftest]

For every parameter: a dense grid over its declared socket range in every scenario (straight, curves of 60 m and 20 m
radius, a 7 % grade, an S-bend); each value passes only when every check (checks.py) passes in every scenario. Each
pass / fail boundary is refined by bisection to 1 % of the range and confirmed by testing five values on the safe side
of it again. The proposed limit is the refined boundary moved inward by 10 % of the boundary value (the user's choice). Writes <out_dir>/road/<param>.json (every evaluation) and
<out_dir>/road_summary.json."""
import bpy, json, math, os, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads")); sys.path.insert(0, HERE)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "roads", "limits"))
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
GRID = int(arg("--grid", 21)); MARGIN = 0.10; REFINE = 0.01
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
import checks as C
from mrs import roads, nodes
from mrs.nodes import mod_input_set, mod_input_get

# ---------------------------------------------------------------- parameters under test (the user-set road inputs)
SKIP = {"Trim Start", "Trim End", "Tongue Start", "Tongue End", "Clear Start", "Clear End", "Lock Start Z", "Lock End Z", "Bank Start",
        "Bank End", "Mark Clear Start", "Mark Clear End", "Turns Start", "Turns End", "Ramp Offset", "Ramp Width",   # derived: set by junctions
        "Prop Seed", "Scatter Seed",                                                                              # seeds: any value
        "Tunnel Start", "Tunnel End", "Transition Start"}                                                         # positions along the road (scenario tests)


def margin_of(v, typ):
    """The user's safety margin: 10 % of the boundary value itself (whole steps for integers, at least 1 mm)."""
    return math.floor(MARGIN * abs(v)) if typ == "int" else max(MARGIN * abs(v), 0.001)


def road_params():
    """[(name, type, default, lo, hi)] of MRS_Road's numeric inputs (the declared ranges in road.py)."""
    g = bpy.data.node_groups["MRS_Road"]; out = []
    for it in g.interface.items_tree:
        if it.item_type != "SOCKET" or it.in_out != "INPUT" or it.socket_type not in ("NodeSocketFloat", "NodeSocketInt"): continue
        if it.name in SKIP: continue
        out.append((it.name, "int" if it.socket_type == "NodeSocketInt" else "float", it.default_value, it.min_value, it.max_value))
    return out


# ---------------------------------------------------------------- scenarios
def arc(cx, cy, r, a0, a1, n=24, z=0.0):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n), z) for k in range(n + 1)]

SCENARIOS = {
    "straight": [(0, 0, 0), (60, 0, 0), (120, 0, 0)],
    "curve60": arc(0, 0, 60.0, -math.pi / 2, 0.0),
    "curve20": arc(0, 0, 20.0, -math.pi / 2, math.pi / 4),
    "grade7": [(0, 0, 0), (60, 0, 4.2), (120, 0, 8.4)],
    "sbend": [(0, 0, 0), (30, 0, 0), (50, 15, 0), (70, 30, 0), (100, 30, 0)],
    "paint": arc(0, 0, 80.0, -math.pi / 2, 0.15),
}
# the paint road carries every instanced marking on a banked curve: arrows at a junction end, buffered cycle lanes
# (symbols, hatching), parking ticks, bus-lane letters, a lane added through a hatched taper
SCENARIO_OVERRIDES = {"paint": {"Lanes Forward": 2, "Lanes Backward": 2, "Bike Left": "Buffered", "Bike Right": "Buffered", "Parking Left": 2.2, "Parking Right": 2.2,
                                "Parking Ticks": True, "Bus Lane Forward": True, "Bus Lane Text": "BUS", "Transition": True, "Lanes Forward End": 3,
                                "Lanes Backward End": 2, "Transition Start": 25.0, "Taper Length": 20.0, "Trim End": 6.0, "Turns End": 7, "Mark Clear End": 4.0,
                                "Lane Arrows": True, "Superelevation": 6.0}}


GROUND_Z = -0.1          # the scenarios' flat terrain (m): below the roads, as a city's ground beside its streets
GROUND = None


def build_scenarios(col, overrides):
    global GROUND
    me = bpy.data.meshes.new("LS_Ground"); me.from_pydata([(-200.0, -200.0, GROUND_Z), (2600.0, -200.0, GROUND_Z), (2600.0, 200.0, GROUND_Z), (-200.0, 200.0, GROUND_Z)], [], [(0, 1, 2, 3)])
    GROUND = bpy.data.objects.new("LS_Ground", me); col.objects.link(GROUND)
    rs = {}
    for k, (nm, pts) in enumerate(SCENARIOS.items()):
        o = roads.make_road("LS_" + nm, [(x + k * 400.0, y, z) for x, y, z in pts], col, "residential", Conform=False, Embankment=False, terrain=GROUND,
                            **dict(overrides, **SCENARIO_OVERRIDES.get(nm, {})))
        rs[nm] = o
    return rs


def scene_ground(p):
    return GROUND_Z


def evaluate(rs, which):
    dg = bpy.context.evaluated_depsgraph_get(); res = {}
    for nm, o in rs.items():
        try: res[nm] = C.road_checks(o, dg, which, scene_ground)
        except Exception as e: res[nm] = {"exception": [traceback.format_exc(limit=2).strip().splitlines()[-1]]}
    return res


def passes(res):
    return all(not p for r in res.values() for p in r.values())


def problems(res):
    return {nm: {k: v for k, v in r.items() if v} for nm, r in res.items() if any(r.values())}


def set_all(rs, name, value):
    for o in rs.values(): mod_input_set(o.modifiers["MRS_Road"], name, value); o.update_tag()


def sweep_param(rs, name, typ, default, lo, hi, which, log):
    """Grid, boundary bisection and confirmation for one parameter. Returns the record."""
    t0 = time.time(); evals = []
    # each scenario road keeps the value it was built with (furnished / scenario overrides): that is its "default",
    # tested as it is and restored afterwards (restoring the socket default changed the scenarios for every later input)
    orig = {nm: mod_input_get(o.modifiers["MRS_Road"], name) for nm, o in rs.items()}
    def restore():
        for nm, o in rs.items(): mod_input_set(o.modifiers["MRS_Road"], name, orig[nm]); o.update_tag()
    def run_orig():
        restore(); res = evaluate(rs, which); ok_ = passes(res)
        evals.append({"value": "built", "pass": ok_, "problems": problems(res)}); return ok_
    def run(v):
        v = int(round(v)) if typ == "int" else float(v)
        set_all(rs, name, v); res = evaluate(rs, which); ok = passes(res)
        evals.append({"value": v, "pass": ok, "problems": problems(res)}); return ok
    if typ == "int":
        grid = list(range(int(lo), int(hi) + 1)) if hi - lo <= 40 else sorted({int(round(lo + (hi - lo) * k / (GRID - 1))) for k in range(GRID)})
    else:
        span = hi - lo
        # wide ranges: a log-spaced grid as well (small values matter most)
        grid = sorted({lo + span * k / (GRID - 1) for k in range(GRID)} | ({lo + (hi - lo) * (10 ** (2 * k / (GRID - 1)) - 1) / 99 for k in range(GRID)} if hi > 20 * max(lo, 0.1) else set()))
    ok = {v: run(v) for v in grid}
    if not run_orig():
        restore()
        return {"param": name, "type": typ, "default": default, "declared": [lo, hi], "status": "default fails", "evals": evals, "seconds": round(time.time() - t0, 1)}
    vals = set(round(float(v), 9) for v in orig.values() if isinstance(v, (int, float)) and not isinstance(v, bool))
    if len(vals) == 1: ok[(int if typ == "int" else float)(vals.pop())] = True        # every road built with one value: it passes
    # a boundary is found to within REFINE of its own value (at least 1 mm; integers to adjacent values)
    tol = lambda g, b: 1.0 if typ == "int" else max(REFINE * max(abs(g), abs(b)), 0.001)
    def bisect(good, bad):
        while abs(bad - good) > tol(good, bad):
            m = (good + bad) * 0.5
            if typ == "int":
                m = int(round(m))
                if m in (good, bad): break
            if run(m): good = m
            else: bad = m
        return good, bad
    # every passing region of the grid, each pass / fail boundary bisected (a region is [a, b]; a_fail / b_fail is
    # the failing value next to it, None at the declared bound)
    vs = sorted(ok); regions = []; cur = None
    for k, v in enumerate(vs):
        if ok[v]:
            if cur is None: cur = [v, v, vs[k - 1] if k > 0 else None, None]
            cur[1] = v
        elif cur is not None:
            cur[3] = v; regions.append(cur); cur = None
    if cur is not None: regions.append(cur)
    refined = []
    for a, b, fa, fb in regions:
        if fa is not None: a, fa = bisect(a, fa)
        if fb is not None: b, fb = bisect(b, fb)
        refined.append([a, b, fa, fb])
    # confirmation: five values inside each refined boundary pass again
    confirm_fail = []
    for a, b, fa, fb in refined:
        for edge, other, failed in ((a, b, fa), (b, a, fb)):
            if failed is None: continue
            for k in range(1, 6):
                v = edge + (other - edge) * 0.02 * k
                if not run(v): confirm_fail.append(v)
    if not refined:                                        # the built values pass, no single grid value does
        restore()
        return {"param": name, "type": typ, "default": default, "declared": [lo, hi], "status": "no passing value", "evals": evals, "seconds": round(time.time() - t0, 1)}
    main = next(r for r in refined if r[0] - 1e-9 <= default <= r[1] + 1e-9) if any(r[0] - 1e-9 <= default <= r[1] + 1e-9 for r in refined) else refined[0]
    def shrink(r):
        a, b, fa, fb = r
        la = a if fa is None else a + margin_of(a, typ); lb = b if fb is None else b - margin_of(b, typ)
        return [la, lb] if la <= lb else [(a + b) * 0.5, (a + b) * 0.5]
    allowed = [shrink(r) for r in refined]
    a, b, fail_lo, fail_hi = main
    lim_lo, lim_hi = min(x[0] for x in allowed), max(x[1] for x in allowed)
    gaps = [[allowed[k][1], allowed[k + 1][0]] for k in range(len(allowed) - 1)]
    islands = []
    restore()
    rec = {"param": name, "type": typ, "default": default, "declared": [lo, hi], "pass_interval": [a, b], "regions": refined, "allowed": allowed, "gaps": gaps,
           "first_fail_below": fail_lo, "first_fail_above": fail_hi, "confirm_failures": confirm_fail, "islands": islands, "limit": [lim_lo, lim_hi],
           "status": "ok" if not confirm_fail else "check", "n_evals": len(evals), "seconds": round(time.time() - t0, 1), "evals": evals}
    log("%-26s %-5s declared [%g, %g] regions %s -> allowed %s (%d evals x %d scenarios, %.0fs)%s" % (
        name, typ, lo, hi, [[round(r[0], 3), round(r[1], 3)] for r in refined], [[round(x, 3) for x in r] for r in allowed], len(evals), len(rs), time.time() - t0,
        "" if rec["status"] == "ok" else "  CHECK: confirm failures %s" % confirm_fail))
    return rec


def main():
    os.makedirs(os.path.join(OUT, "road"), exist_ok=True)
    sc = bpy.data.scenes.new("LimitSweep"); nodes.set_scene(sc)
    try: bpy.context.window.scene = sc
    except Exception: pass
    col = bpy.data.collections.new("LS_Roads"); sc.collection.children.link(col)
    which = tuple((arg("--checks") or "eval,flipped,degenerate,fold,width,paint,validate,props").split(","))
    # every roadside feature on, so its parameters are exercised (the residential preset leaves the sides empty)
    furnished = {"Light Side": "Both", "Tree Side": "Alternate", "Prop Side": "Both", "Planting Strip Left": 1.2, "Planting Strip Right": 1.2,
                 "Lane Arrows": True, "Edge Lines": True, "Centre Line": "Dashed"}
    rs = build_scenarios(col, {"Props": None, "Trees": None, "Streetlights": None, "Scatter": None} if "--bare" in argv else furnished)
    log = print
    # self-test: every check passes on the defaults in every scenario
    res = evaluate(rs, which)
    log("SELFTEST defaults:", "OK" if passes(res) else json.dumps(problems(res))[:2000])
    if "--selftest" in argv or not passes(res): return
    params = road_params()
    only = arg("--params")
    if only: params = [p for p in params if p[0] in only.split(",")]
    part = arg("--part")                                   # "k/n": every n-th parameter from the k-th (parallel runs)
    if part:
        k, n = (int(x) for x in part.split("/")); params = params[k::n]
    summary_path = os.path.join(OUT, "road_summary%s.json" % ("_part%s" % part.replace("/", "of") if part else ""))
    summary = json.load(open(summary_path)) if os.path.exists(summary_path) and "--resume" in argv else {}
    params = [p for p in params if p[0] not in summary]
    for name, typ, d, lo, hi in params:
        rec = sweep_param(rs, name, typ, d, lo, hi, which, log)
        with open(os.path.join(OUT, "road", name.replace(" ", "_") + ".json"), "w") as f: json.dump(rec, f, indent=1, default=str)
        summary[name] = {k: rec.get(k) for k in ("type", "default", "declared", "pass_interval", "regions", "allowed", "gaps", "first_fail_below", "first_fail_above", "limit", "status", "n_evals")}
        with open(summary_path, "w") as f: json.dump(summary, f, indent=1, default=str)
    log("SWEEP done: %d params" % len(summary))

main()
