"""mrs.grading on a synthetic terrain (plain Python + numpy, no Blender): a valley with a river and a hill.
    python -P tools/roads/tests/grading_test.py
Checks: profiles keep their max grade and pinned node heights, a bridge deck clears the water by its clearance,
the graded ground meets the road surfaces and never exceeds the cut / fill batters next to them, wet cells keep
their bed. Prints GRADING_TEST OK."""
import math, os, sys, types
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
pkg = types.ModuleType("mrs"); pkg.__path__ = [os.path.join(ROOT, "tools", "roads", "mrs")]; sys.modules["mrs"] = pkg
import mrs.grading as G

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

n, cell = 161, 4.0
yy, xx = np.mgrid[0:n, 0:n] * cell
valley = 12.0 * (1.0 - np.exp(-((xx - 320.0) / 70.0) ** 2))            # banks at 12 m, a valley floor at 0
hill = 30.0 * np.exp(-(((xx - 520.0) / 50.0) ** 2 + ((yy - 320.0) / 60.0) ** 2))
h0 = valley + hill + 0.01 * yy
water = np.abs(xx - 320.0) < 18.0
F = G.Field(h0, cell, water=water, water_level=np.full_like(h0, 3.0))

nodes = {"w": (80.0, 320.0), "c": (420.0, 320.0), "e": (600.0, 320.0)}
edges = [{"a": "w", "b": "c", "pts": G.densify([nodes["w"], nodes["c"]], 2.0), "max_grade": 0.06, "bridge": True, "clearance": 4.0},
         {"a": "c", "b": "e", "pts": G.densify([nodes["c"], nodes["e"]], 2.0), "max_grade": 0.10, "smooth": 30.0}]
zn, zs = G.network_profiles(F, nodes, edges)
for e, z in zip(edges, zs):
    s = G._stations(e["pts"]); g = float(np.max(np.abs(np.diff(z) / np.diff(s))))
    check(g <= e["max_grade"] + 1e-6, "edge %s-%s keeps its max grade (%.3f <= %.2f)" % (e["a"], e["b"], g, e["max_grade"]))
    check(abs(z[0] - zn[e["a"]]) < 1e-6 and abs(z[-1] - zn[e["b"]]) < 1e-6, "edge %s-%s ends on its node heights" % (e["a"], e["b"]))
wet = np.array([F.wet(x, y) for x, y in edges[0]["pts"]])
clear = float(np.min(zs[0][wet])) - 3.0
check(clear >= 4.0 - 1e-6, "the bridge deck clears the water by %.2f m (>= 4)" % clear)
hill_cut = float(np.max([F(x, y) - z for (x, y), z in zip(edges[1]["pts"], zs[1])]))
check(hill_cut > 1.0, "the road over the hill is cut in, not draped (%.1f m)" % hill_cut)

# grade the ground to a 10 m wide corridor along the second edge
own = np.zeros_like(h0, bool); surf = np.zeros_like(h0)
P = np.array(edges[1]["pts"]); Z = zs[1]
for j in range(n):
    for i in range(n):
        x, y = i * cell, j * cell
        if 420.0 <= x <= 600.0 and abs(y - 320.0) <= 5.0:
            k = int(np.argmin(np.abs(P[:, 0] - x))); own[j, i] = True; surf[j, i] = Z[k]
g = G.grade(h0, own, surf, cell, slope=0.5, sink=0.3, water=water)
check(np.allclose(g[own], surf[own] - 0.3), "the ground lies 0.3 m under the road surface")
d_up = d_dn = 0.0
for j in range(n):
    for i in range(n):
        if own[j, i] or water[j, i]: continue
        x, y = i * cell, j * cell
        if not (420.0 <= x <= 600.0): continue
        dist = abs(y - 320.0) - 5.0
        k = int(np.argmin(np.abs(P[:, 0] - x)))
        if dist <= 0: continue
        run = dist + cell; cut_allow = 1.0 * min(run, 6.0) + 2.0 * max(run - 6.0, 0.0)
        d_up = max(d_up, (g[j, i] - Z[k]) - cut_allow); d_dn = max(d_dn, (Z[k] - g[j, i]) - 0.5 * run)
check(d_up <= 1e-6 and d_dn <= 1e-6, "cut (1:1, 2:1 past 6 m) and fill (1:2) batters hold beside the road (%.3f, %.3f)" % (d_up, d_dn))
deep = max((h0[j, i] - Z[int(np.argmin(np.abs(P[:, 0] - i * cell)))]) for j in range(n) for i in range(n) if 470 <= i * cell <= 570 and abs(j * cell - 320) < 40)
wide1 = sum(1 for j in range(n) if abs(j * cell - 320) > 5 and abs(g[j, 130] - h0[j, 130]) > 0.01) * cell
print("   deepest natural ground over the road %.1f m, graded width at x=520: %.0f m" % (deep, wide1))
check(np.allclose(g[water & ~own], h0[water & ~own]), "the river bed keeps its height")
far = (np.abs(yy - 320.0) > 120.0)
check(np.allclose(g[far], h0[far]), "the terrain far from the road is untouched")
# ---------------------------------------------------------------- landing-aware design (network_profiles_landed)
# a T on a 15 % hillside: a through street across the slope and a stem straight up it, junction footprints (trims)
# and landings at the junction end; the built road (rail_model: trim, blur, constant-height lock, crown fade) must
# stay within the stem's 12 % in every 10 m window, with the junction end level at the node height
hill = G.Field(np.fromfunction(lambda j, i: 0.15 * j * 2.0, (200, 200)), 2.0)
Gd, trim, flat, LLk, ch = 0.118, 12.0, 4.9, 9.0, 0.11
gl = min(0.03, (Gd - 1.5 * ch / LLk) / G.LOCK_K); vc = 0.7 * 100.0 * (Gd - gl); land = LLk + 4.0
stem = G.insert_stations([(200.0, 100.0), (200.0, 160.0), (200.0, 220.0)], [trim, trim + flat, trim + land, trim + land + vc])
through = [(120.0, 100.0), (200.0, 100.0), (280.0, 100.0)]
nodes_t = {"J": (200.0, 100.0), "N": (200.0, 220.0), "W": (120.0, 100.0), "E": (280.0, 100.0)}
edges_t = [{"a": "J", "b": "N", "pts": stem, "max_grade": Gd, "smooth": 30.0, "ends": ((trim, land), (0.0, 0.0)), "land_grade": gl, "vc": vc, "flat": (flat, 0.0)},
           {"a": "W", "b": "J", "pts": through[:2], "max_grade": Gd, "smooth": 30.0, "ends": ((0.0, 0.0), (trim, land)), "land_grade": gl, "vc": vc, "flat": (0.0, flat)},
           {"a": "J", "b": "E", "pts": through[1:], "max_grade": Gd, "smooth": 30.0, "ends": ((trim, land), (0.0, 0.0)), "land_grade": gl, "vc": vc, "flat": (flat, 0.0)}]
info = {}
zn_t, zs_t = G.network_profiles_landed(hill, nodes_t, edges_t, info=info)
seg_ok = all(np.all(np.abs(np.diff(z)) <= gk * np.diff(G._stations(e["pts"])) + 1e-9) for e, z, gk in zip(edges_t, zs_t, info["caps"]))
check(seg_ok and not info["residual"] and not info["infeasible"], "landed design: every segment within its cap, no residual, nothing infeasible (%d sweeps)" % info["iterations"])
s0 = G._stations(stem); lvl = np.abs(zs_t[0][s0 <= trim + flat] - zn_t["J"]).max()
check(lvl < 1e-9, "the stem is level at the node height over the junction footprint and its platform (%.2e)" % lvl)
P3 = [(x, y, z) for (x, y), z in zip(stem, zs_t[0])]
o = G.rail_model(P3, trim, 0.0, True, False, zn_t["J"], 0.0, LLk, ch)
w_built = max(G.window_grades(o[1], o[3])[0], G.window_grades(o[1], o[2])[0])
check(w_built <= Gd + 1e-6, "the built stem (blur, lock, crown) climbs at most %.1f %% over 10 m (%.2f %%)" % (100 * Gd, 100 * w_built))
check(abs(o[3][0] - zn_t["J"]) < 1e-9, "the stem meets the junction exactly at its height (lock offset %.2e)" % abs(o[3][0] - zn_t["J"]))
# the old point-to-point budget on the same stem: centre to centre within the cap, but the built street is steeper
z_old = G.profile(hill, stem, zn_t["J"], G.node_heights(hill, {"N": (200.0, 220.0)})["N"], Gd, 30.0)
o_old = G.rail_model([(x, y, z) for (x, y), z in zip(stem, z_old)], trim, 0.0, True, False, zn_t["J"] + 0.8, 0.0, 14.0, ch)
check(max(G.window_grades(o_old[1], o_old[3])[0], G.window_grades(o_old[1], o_old[2])[0]) > Gd, "control: a 14 m lock to an offset junction plane over the old profile breaks the cap")
# infeasible: a short link between two nodes the earthwork bound keeps 6 m apart in height
cliff = {"A": (0.0, 0.0), "B": (30.0, 0.0)}
cf = G.Field(np.fromfunction(lambda j, i: np.where(i * 2.0 > 15.0, 6.0, 0.0), (20, 40)), 2.0)
info2 = {}
G.network_profiles_landed(cf, cliff, [{"a": "A", "b": "B", "pts": G.insert_stations([(0.0, 0.0), (30.0, 0.0)], [12.0, 18.0]), "max_grade": 0.12,
                                       "ends": ((8.0, 4.0), (8.0, 4.0)), "land_grade": 0.0, "flat": (4.0, 4.0)}], info=info2, max_move=1.0)
check(info2["infeasible"] == [0] and info2["residual"], "an edge the earthwork bound cannot satisfy is reported infeasible (residual %.2f m)" % max(info2["residual"].values(), default=0.0))

print("GRADING_TEST %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
sys.exit(1 if fails else 0)
