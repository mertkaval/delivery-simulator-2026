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
print("GRADING_TEST %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
sys.exit(1 if fails else 0)
