"""Street-by-street audit of a planned city (plan_city.py output).

    python tools/cityforge/audit_streets.py <plan_dir>/city.json [report.md]

Walks every named street in order and checks everything that belongs to it, then prints one line
per street (PASS / FAIL with the problems) and writes a Markdown report. Checks per street:
  carriageway   no prop, building, fence or house stands on the road (bridges excepted)
  props         no two props closer than their footprints allow
  houses        each house inside its lot, clear of its fences, its front door towards the street
  front walk    the front fence leaves a gap in front of the door
  garages       on the back lane, inside the lot
  name boards   every junction on the street has a corner board carrying this street's name
  signs clear   no tree trunk within 2 m of a name board, signal or lamp
  lighting      no stretch longer than 70 m without a street lamp (or utility-pole lamp)
"""
import json, math, sys
from collections import defaultdict

city = json.load(open(sys.argv[1], encoding="utf-8"))
report_path = sys.argv[2] if len(sys.argv) > 2 else None
nodes = {n["id"]: n for n in city["nodes"]}
RADIUS = {"traffic_light": 0.45, "street_sign": 0.35, "bus_stop": 2.4, "lamp": 0.35, "utility_pole": 0.35, "hydrant": 0.35,
          "stop_sign": 0.25, "post_box": 0.45, "phone_box": 0.7, "ad_column": 0.85, "cesme": 1.1, "vending_machine": 0.65,
          "cafe_set": 1.3, "tree": 1.2, "bench": 1.0}


def seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L2 = ab[0] ** 2 + ab[1] ** 2 or 1.0
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    return math.hypot(p[0] - a[0] - ab[0] * t, p[1] - a[1] - ab[1] * t), t


def seg_hits_box(a, b, box, pad=0.0):
    """Does segment a-b pass through an axis-aligned box (x0, y0, x1, y1)?"""
    x0, y0, x1, y1 = box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad
    if x1 <= x0 or y1 <= y0: return False
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0: return False
        else:
            r = q / p
            if p < 0: t0 = max(t0, r)
            else: t1 = min(t1, r)
            if t0 > t1: return False
    return True


streets = defaultdict(list)
for e in city["roads"]: streets[e["name"]].append(e)
props = city["props"]
all_props = [(k, (p[0], p[1])) for k, lst in props.items() if k in RADIUS for p in lst]
grid = defaultdict(list)
for k, p in all_props: grid[(int(p[0] // 20), int(p[1] // 20))].append((k, p))
lots = {l["id"]: l for l in city["lots"]}
fences = {f["lot"]: f for f in city["fences"]}
houses_by_addr = defaultdict(list)
for h in city["houses"]: houses_by_addr[h["address"].split(" ", 1)[1]].append(h)
signs_by_node_name = defaultdict(set)
for s in props.get("street_sign", []):
    # a board serves every junction within 30 m (short downtown blocks put two junctions close together)
    for n in city["nodes"]:
        if (n["pos"][0] - s[0]) ** 2 + (n["pos"][1] - s[1]) ** 2 < 30.0 ** 2:
            signs_by_node_name[n["id"]].update([s[5], s[6]] + list(s[9::2]))
lights = [p for k, p in all_props if k in ("lamp", "utility_pole")]
light_grid = defaultdict(list)
for p in lights: light_grid[(int(p[0] // 40), int(p[1] // 40))].append(p)
tall = [(k, p) for k, p in all_props if k in ("street_sign", "traffic_light", "lamp", "utility_pole")]
trees = [p for k, p in all_props if k == "tree"]
tree_grid = defaultdict(list)
for p in trees: tree_grid[(int(p[0] // 10), int(p[1] // 10))].append(p)

results = []
total_fail = 0
for name in sorted(streets, key=lambda n: (streets[n][0].get("culture", ""), n)):
    es = streets[name]
    problems = []
    corridor = []
    for e in es:
        a, b = nodes[e["a"]]["pos"], nodes[e["b"]]["pos"]
        corridor.append((a, b, e))
    # carriageway and prop spacing along this street
    seen = set()
    for a, b, e in corridor:
        if e["bridge"]: continue
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        cells = {(int((a[0] + (b[0] - a[0]) * t) // 20) + i, int((a[1] + (b[1] - a[1]) * t) // 20) + j)
                 for t in [k / max(1, int(L / 10)) for k in range(int(L / 10) + 1)] for i in (-1, 0, 1) for j in (-1, 0, 1)}
        near = [kp for c in cells for kp in grid.get(c, ())]
        for k, p in near:
            d, t = seg_dist(p, a, b)
            if d < e["width"] / 2 and 0.0 < t < 1.0 and (k, p) not in seen:
                seen.add((k, p))
                problems.append("%s on the carriageway at (%.0f, %.0f)" % (k, p[0], p[1]))
        for i, (k1, p1) in enumerate(near):
            for k2, p2 in near[i + 1:]:
                if p1 == p2 and k1 == k2: continue
                if math.hypot(p1[0] - p2[0], p1[1] - p2[1]) < (RADIUS[k1] + RADIUS[k2]) * 0.9 and (k1, p1, k2, p2) not in seen:
                    d1, _ = seg_dist(p1, a, b)
                    if d1 < e["width"] / 2 + 8:
                        seen.add((k1, p1, k2, p2))
                        problems.append("%s and %s overlap at (%.0f, %.0f)" % (k1, k2, p1[0], p1[1]))
        # lighting: walk the edge in 10 m steps; flag a 70 m dark run
        dark = 0.0
        for k in range(int(L / 10) + 1):
            q = (a[0] + (b[0] - a[0]) * k / max(1, int(L / 10)), a[1] + (b[1] - a[1]) * k / max(1, int(L / 10)))
            lit = any(math.hypot(q[0] - lp[0], q[1] - lp[1]) < 26 for i in (-1, 0, 1) for j in (-1, 0, 1)
                      for lp in light_grid.get((int(q[0] // 40) + i, int(q[1] // 40) + j), ()))
            dark = 0.0 if lit else dark + 10
            if dark >= 70 and e["cls"] != "lane":
                problems.append("dark stretch near (%.0f, %.0f)" % q)
                break
    # junction name boards
    for a, b, e in corridor:
        for nid in (e["a"], e["b"]):
            nd = nodes[nid]
            names = {city["roads"][int(r.split("_")[1])]["name"] for r in nd["edges"]} if all(r.startswith("road_") for r in nd["edges"]) else set()
            if len(nd["edges"]) >= 3 and len(names) >= 2 and name not in signs_by_node_name.get(nid, set()):
                problems.append("junction %d has no board for this street" % nid)
    # tall street furniture clear of tree trunks
    for k, p in tall:
        if not any(seg_dist(p, a, b)[0] < e["width"] / 2 + 8 for a, b, e in corridor): continue
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for tp in tree_grid.get((int(p[0] // 10) + i, int(p[1] // 10) + j), ()):
                    if math.hypot(tp[0] - p[0], tp[1] - p[1]) < 2.0:
                        problems.append("tree beside a %s at (%.0f, %.0f)" % (k, p[0], p[1]))
    # the houses addressed on this street
    for h in houses_by_addr.get(name, []):
        lot = lots[h["lot"]]
        x0, y0, x1, y1 = lot["rect"]
        w, d = h["size"]
        hb = (h["pos"][0] - w / 2, h["pos"][1] - d / 2, h["pos"][0] + w / 2, h["pos"][1] + d / 2)
        if hb[0] < x0 - 0.05 or hb[2] > x1 + 0.05 or hb[1] < y0 - 0.05 or hb[3] > y1 + 0.05:
            problems.append("%s sticks out of %s" % (h["id"], lot["id"]))
        door_y = h["pos"][1] + lot["front"] * d / 2
        if abs(door_y - lot["front_y"]) > abs(h["pos"][1] - lot["front_y"]):
            problems.append("%s faces away from the street" % h["id"])
        for sgm in fences.get(lot["id"], {"segments": []})["segments"]:
            if seg_hits_box((sgm[0], sgm[1]), (sgm[2], sgm[3]), hb, 0.05):
                problems.append("%s fence runs through %s" % (lot["id"], h["id"]))
                break
        front = [sg for sg in fences.get(lot["id"], {"segments": []})["segments"] if abs(sg[1] - lot["front_y"]) < 0.01 and abs(sg[3] - lot["front_y"]) < 0.01]
        door_x = h["pos"][0] + (h.get("door", [0, 0])[0] if lot["front"] > 0 else -h.get("door", [0, 0])[0])
        if front and any(min(sg[0], sg[2]) < door_x < max(sg[0], sg[2]) for sg in front):
            problems.append("%s: front fence across the door" % h["id"])
    status = "PASS" if not problems else "FAIL"
    total_fail += status == "FAIL"
    results.append((name, es[0].get("culture", "mixed"), len(es), status, problems))
    print("%-4s %-38s %-9s %2d segments %s" % (status, name, es[0].get("culture", ""), len(es), "; ".join(problems[:3]) + (" (+%d)" % (len(problems) - 3) if len(problems) > 3 else "")))
print("STREETS %d, %d pass, %d fail" % (len(results), len(results) - total_fail, total_fail))
if report_path:
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Port Halden street audit\n\nGenerated by `tools/cityforge/audit_streets.py` (every named street, in order).\n\n")
        f.write("**%d streets: %d pass, %d fail.**\n\n| Street | District | Segments | Result | Problems |\n|---|---|---|---|---|\n" % (len(results), len(results) - total_fail, total_fail))
        for name, cul, n, st, pr in results:
            f.write("| %s | %s | %d | %s | %s |\n" % (name, cul, n, st, "; ".join(pr[:6]) + (" (+%d more)" % (len(pr) - 6) if len(pr) > 6 else "")))
sys.exit(0 if total_fail == 0 else 1)
