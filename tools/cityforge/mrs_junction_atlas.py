"""Every junction of an MRS city build, checked and seen (Blender, headless, on the .blend saved by mrs_streets.py --blend):
mrs.validate over every road, junction and speed sign (report JSON), the back-lane mouths checked for their dropped
kerb, and a top-down render of every junction on labelled contact sheets (failing junctions marked).

    blender --background <city.blend> --python tools/cityforge/mrs_junction_atlas.py -- <out_dir> [--no-render] [--size 384]
        [--plan <city.json>]   (the plan's buildings: none may stand on a street surface)"""
import bpy, json, math, os, sys, time
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0]); os.makedirs(OUT, exist_ok=True)
SIZE = int(argv[argv.index("--size") + 1]) if "--size" in argv else 384
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
t0 = time.time()
import mrs
from mrs import qa, lighting, validate, structures
from mrs.placement import _project, RoadModel
sc = bpy.context.scene
col = bpy.data.collections["PH_Roads"]; placed = bpy.data.collections.get("PH_Roads_Placed")
def footprints(plan_path):
    """The plan's buildings as world footprints [(id, corners, ground z)] (plan metres -> Blender: city.B)."""
    from mrs import city
    plan = json.load(open(plan_path)); out = []
    def rect(bid, pos, w, d, yaw, z):
        c, s_ = math.cos(yaw), math.sin(yaw); p = city.B(pos[0], pos[1])
        out.append((bid, [(p.x + lx * c - ly * s_, p.y + lx * s_ + ly * c) for lx, ly in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))], z))
    for k in ("houses", "shops", "warehouses", "public"):
        for b in plan.get(k, []): rect(b["id"], b["pos"], b["size"][0], b["size"][1], b.get("yaw", 0.0), b.get("h"))
    for b in plan.get("garages", []): rect(b["id"], b["pos"], 6.4, 6.4, b.get("yaw", 0.0), b.get("h"))
    for t in plan.get("towers", []): rect(t["id"], t["pos"], t["podium"][0] - 4.0, t["podium"][0] - 4.0, math.radians(t["angle"]), t.get("h"))
    return out
FOOT = footprints(argv[argv.index("--plan") + 1]) if "--plan" in argv else None
rep = validate.validate(col, placed, footprints=FOOT)
rep["buildings_checked"] = len(FOOT or [])
# back-lane mouths: every lane end that opens onto a street has a driveway (dropped kerb) on that street there
mouths = []; bad_mouths = []
STREETS = [(r, RoadModel(r), [pt for _a, pt in structures.centre_line(r)]) for r in col.objects
           if r.type == "CURVE" and "MRS_Road" in r.modifiers and not r.name.startswith("PH_L_") and r.get("mrs_driveways")]
for o in col.objects:
    if not o.name.startswith("PH_L_"): continue
    from mrs.roads import road_ends
    for p, t, is_start in road_ends(o):
        # follow the lane out of its end (road_ends' tangent points back into it) until it reaches a street's centre line:
        # the mouth is where the lane meets the street, not the perpendicular foot of its end (slanted streets)
        out = -Vector((t.x, t.y, 0.0)).normalized(); best = None
        near = [(r, m) for r, m, pts in STREETS if min((Vector((x.x, x.y)) - Vector((p.x, p.y))).length for x in pts) < 45.0]
        for k in range(0, 61):
            q0 = p + out * (k * 0.5)
            for r, m in near:
                a = _project(m, q0); q, tt, rr = structures.road_sample(r, a)
                d = (Vector((q.x, q.y)) - Vector((q0.x, q0.y))).length
                if d < 0.6 and (best is None or d < best[0]): best = (d, r, a)
            if best is not None: break
        if best is None: continue
        mouths.append(o.name)
        if not validate.driveway_at(best[1], best[2], tol=2.0):
            bad_mouths.append({"lane": o.name, "street": best[1].name, "station": round(best[2], 1)})
rep["lane_mouths"] = len(mouths); rep["lane_mouths_without_kerb"] = bad_mouths
bad = {}
for p in rep["problems"]: bad.setdefault(p["object"], []).append(p["check"])
J = sorted([o for o in col.all_objects if o.type == "MESH" and o.get("mrs_junction")], key=lambda o: o.name)
def meta(o): m = o["mrs_junction"]; return m.to_dict() if hasattr(m, "to_dict") else dict(m)
rep["junction_list"] = [{"id": o.name, "type": meta(o).get("type"), "control": meta(o).get("control"), "approaches": len(meta(o).get("approaches", [])),
                         "problems": bad.get(o.name, [])} for o in J]
json.dump(rep, open(os.path.join(OUT, "validation.json"), "w"), indent=1, default=str)
print("ATLAS validation: %d problems %s; lane mouths %d, without kerb %d" % (len(rep["problems"]), json.dumps(rep["counts"]), len(mouths), len(bad_mouths)))
if "--no-render" not in argv:
    probe = bpy.data.objects.get("PH_GroundProbe")
    if probe is not None and not any(o.name.startswith("Terrain_") for o in bpy.data.objects):     # (the assembled map has the real terrain)
        probe.hide_render = False
        from mrs.props import mat
        probe.data.materials.clear(); probe.data.materials.append(mat("PH_Grass", (0.12, 0.2, 0.07), 0.95)); probe.location.z = -0.6
    try: lighting.day_setup(sc)
    except Exception as e: print("day setup", e)
    paths = []
    for k, o in enumerate(J):
        m = meta(o); at = Vector(m["at"]); z = m.get("z", at.z)
        reach = max([a.get("trim", 10.0) for a in m.get("approaches", [])] + [m.get("radius", 10.0) + 6.0]) + 14.0
        eye = Vector((at.x, at.y + 0.01, z + reach / math.tan(math.radians(17.0))))
        path = os.path.join(OUT, "j", "%s.png" % o.name)
        qa.render(path, eye, Vector((at.x, at.y, z)), lens=58.0, res=(SIZE, SIZE), samples=6, scene=sc)
        paths.append((path, o.name, bad.get(o.name, [])))
        if k % 20 == 0: print("ATLAS render %d / %d (%.0fs)" % (k + 1, len(J), time.time() - t0))
    try:
        from PIL import Image, ImageDraw
        cols, rows = 6, 5; per = cols * rows
        for sh in range(0, len(paths), per):
            chunk = paths[sh:sh + per]
            img = Image.new("RGB", (cols * SIZE, rows * (SIZE + 22)), (20, 20, 20)); dr = ImageDraw.Draw(img)
            for i, (p, name, probs) in enumerate(chunk):
                x = (i % cols) * SIZE; y = (i // cols) * (SIZE + 22)
                img.paste(Image.open(p).convert("RGB"), (x, y + 22))
                dr.text((x + 6, y + 4), name + ("  " + ",".join(sorted(set(probs))) if probs else "  ok"), fill=(255, 90, 80) if probs else (200, 230, 200))
            img.save(os.path.join(OUT, "junctions_%02d.jpg" % (sh // per)), quality=88)
    except ImportError:          # Blender's Python has no PIL: the sheets are made by tools/cityforge/contact_sheet.py
        json.dump([[p, name + ("  " + ",".join(sorted(set(probs))) if probs else "  ok"), bool(probs)] for p, name, probs in paths],
                  open(os.path.join(OUT, "sheet_manifest.json"), "w"))
        print("ATLAS: sheets -> python tools/cityforge/contact_sheet.py %s" % os.path.join(OUT, "sheet_manifest.json"))
print("ATLAS %s %.0fs" % ("OK" if not rep["problems"] and not bad_mouths else "PROBLEMS", time.time() - t0))
