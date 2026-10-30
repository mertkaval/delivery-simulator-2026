"""Parameter-limit sweeps for MRS_Road (phase B1 of docs/roads/READY.md).

    blender --background tmp/roads/city/base.blend --python tools/roads/limits/sweep.py -- <out_dir> [--params A,B] [--grid 21]
        [--selftest]

For every parameter: a dense grid over its declared socket range in every scenario (straight, curves of 60 m and 20 m
radius, a 7 % grade, an S-bend); each value passes only when every check (checks.py) passes in every scenario. Each
pass / fail boundary is refined by bisection to 1 % of the range and confirmed by testing five values on the safe side
of it again. The proposed limit is the refined boundary moved inward by MARGIN of the safe interval (the user's choice:
a safety margin inside the last passing value). Writes <out_dir>/road/<param>.json (every evaluation) and
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
}


def build_scenarios(col, overrides):
    rs = {}
    for k, (nm, pts) in enumerate(SCENARIOS.items()):
        o = roads.make_road("LS_" + nm, [(x + k * 400.0, y, z) for x, y, z in pts], col, "residential", Conform=False, Embankment=False, **overrides)
        rs[nm] = o
    return rs


def evaluate(rs, which):
    dg = bpy.context.evaluated_depsgraph_get(); res = {}
    for nm, o in rs.items():
        try: res[nm] = C.road_checks(o, dg, which)
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
    if not run(default):
        set_all(rs, name, default)
        return {"param": name, "type": typ, "default": default, "declared": [lo, hi], "status": "default fails", "evals": evals, "seconds": round(time.time() - t0, 1)}
    # the passing interval around the default, then each boundary refined by bisection
    vs = sorted(ok); below = [v for v in vs if v < default]; above = [v for v in vs if v > default]
    a = default
    fail_lo = None
    for v in reversed(below):
        if ok[v]: a = v
        else: fail_lo = v; break
    b = default; fail_hi = None
    for v in above:
        if ok[v]: b = v
        else: fail_hi = v; break
    tol = max((hi - lo) * REFINE, 1.0 if typ == "int" else 1e-4)
    def bisect(good, bad):
        while abs(bad - good) > tol:
            m = (good + bad) * 0.5
            if typ == "int":
                m = int(round(m))
                if m in (good, bad): break
            if run(m): good = m
            else: bad = m
        return good, bad
    if fail_lo is not None: a, fail_lo = bisect(a, fail_lo)
    if fail_hi is not None: b, fail_hi = bisect(b, fail_hi)
    # confirmation: five values between the boundary and the default must pass again
    confirm_fail = []
    for edge, other in ((a, b), (b, a)):
        for k in range(1, 6):
            v = edge + (other - edge) * 0.02 * k
            if not run(v): confirm_fail.append(v)
    safe = b - a
    lim_lo = lo if fail_lo is None else a + MARGIN * safe
    lim_hi = hi if fail_hi is None else b - MARGIN * safe
    if typ == "int":
        lim_lo = lo if fail_lo is None else int(math.ceil(lim_lo)); lim_hi = hi if fail_hi is None else int(math.floor(lim_hi))
    # failures outside the main interval (not monotonic) are kept in the record
    islands = sorted(v for v in vs if not ok[v] and a < v < b)
    set_all(rs, name, default)
    rec = {"param": name, "type": typ, "default": default, "declared": [lo, hi], "pass_interval": [a, b], "first_fail_below": fail_lo,
           "first_fail_above": fail_hi, "confirm_failures": confirm_fail, "islands": islands, "limit": [lim_lo, lim_hi],
           "status": "ok" if not confirm_fail and not islands else "check", "n_evals": len(evals), "seconds": round(time.time() - t0, 1), "evals": evals}
    log("%-26s %-5s declared [%g, %g] pass [%g, %g] fail below %s above %s -> limit [%g, %g] (%d evals x %d scenarios, %.0fs)%s" % (
        name, typ, lo, hi, a, b, fail_lo, fail_hi, lim_lo, lim_hi, len(evals), len(rs), time.time() - t0,
        "" if rec["status"] == "ok" else "  CHECK: confirm %s islands %s" % (confirm_fail, islands)))
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
    summary = {}
    for name, typ, d, lo, hi in params:
        rec = sweep_param(rs, name, typ, d, lo, hi, which, log)
        with open(os.path.join(OUT, "road", name.replace(" ", "_") + ".json"), "w") as f: json.dump(rec, f, indent=1, default=str)
        summary[name] = {k: rec.get(k) for k in ("type", "default", "declared", "pass_interval", "first_fail_below", "first_fail_above", "limit", "status", "n_evals")}
        with open(os.path.join(OUT, "road_summary.json"), "w") as f: json.dump(summary, f, indent=1, default=str)
    log("SWEEP done: %d params" % len(summary))

main()
