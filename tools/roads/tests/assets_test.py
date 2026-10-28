"""Headless validation of the Mert Road Studio asset library (mrs/assets.py).

    blender --background --factory-startup --python tools/roads/tests/assets_test.py

Builds every collection, checks counts / fixed indices / mesh hygiene, renders a catalogue contact sheet
(overview + 6 close-up groups) to tmp/roads/assets/catalogue_*.png and saves tmp/roads/assets/mrs_assets.blend
with every object marked as an asset.
"""
import math, os, sys, time
ROOT = "C:/GodotProjects/delivery-simulator-2026"
sys.path.insert(0, ROOT + "/tools/roads")
import bpy, bmesh
from mathutils import Vector
import mrs.assets as A
from mrs.nodes import MRS
from mrs import qa

OUT = os.path.join(ROOT, "tmp", "roads", "assets"); os.makedirs(OUT, exist_ok=True)
QUICK = "--quick" in sys.argv  # skip renders / previews (mesh checks only)

# ---- clean factory scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
t0 = time.time()
cols = A.build_assets()
print("build_assets: %.1f s" % (time.time() - t0))

# ---- counts and fixed indices
MIN = {"Props": 14, "Streetlights": 6, "Trees": 8, "Signs": 20, "TrafficLights": 4, "Barriers": 6, "Pillars": 3, "Scatter": 8, "Manholes": 3, "Drains": 2, "Markings": 6, "Structures": 8}
fails = []
for c, n in MIN.items():
    k = len(cols[c].objects)
    if k < n: fails.append("%s has %d objects, need >= %d" % (c, k, n))
names = lambda c: [o.name for o in cols[c].objects]
if names("Barriers")[:4] != ["MRS_Guardrail", "MRS_Jersey", "MRS_Parapet", "MRS_Railing"]: fails.append("barrier order: %s" % names("Barriers")[:4])
if "MRS_Hedge" not in names("Barriers") or "MRS_Fence" not in names("Barriers"): fails.append("hedge/fence missing")
if names("Markings") != ["MRS_ArrowStraight", "MRS_ArrowLeft", "MRS_ArrowRight", "MRS_ArrowStraightLeft", "MRS_ArrowStraightRight", "MRS_MarkTick"]: fails.append("marking order: %s" % names("Markings"))
for nm in ("MRS_GantryPost", "MRS_GantryBeam", "MRS_GantrySign", "MRS_Pylon", "MRS_Abutment", "MRS_TunnelPortal", "MRS_BusStopShelter", "MRS_Crosswalk_Signal"):
    if nm not in names("Structures"): fails.append("structure missing: " + nm)
grass = [n for n in names("Scatter") if "Grass" in n or "Wildflower" in n]
if len(grass) < len(names("Scatter")) / 2: fails.append("scatter should be mostly grass: %s" % names("Scatter"))
for c in ("Props", "Signs", "Streetlights", "TrafficLights", "Trees"):
    if len(set(names(c))) != len(names(c)): fails.append("duplicate names in " + c)

# ---- per-object mesh hygiene
report = {}
for c, col in cols.items():
    for o in col.objects:
        me = o.data; d = o.dimensions; problems = []
        if len(me.materials) < 1: problems.append("no material")
        if not me.uv_layers: problems.append("no UV")
        if not (0.05 <= max(d) <= 14.0): problems.append("dimensions %.3f x %.3f x %.3f" % tuple(d))
        if any(p.area < 1e-9 for p in me.polygons): problems.append("zero-area face")
        used = {v for p in me.polygons for v in p.vertices}
        if len(used) != len(me.vertices): problems.append("%d loose verts" % (len(me.vertices) - len(used)))
        if c != "Markings" and not (50 <= len(me.vertices) <= 3000): problems.append("%d verts" % len(me.vertices))
        if any(p.material_index >= len(me.materials) for p in me.polygons): problems.append("material index out of range")
        if c in ("Pillars",) or o.name == "MRS_Pylon":
            zs = [v.co.z for v in me.vertices]
            if abs(min(zs)) > 1e-4 or abs(max(zs) - 1.0) > 1e-4: problems.append("pillar z range %.3f..%.3f" % (min(zs), max(zs)))
        if c == "Barriers":
            ys = [v.co.y for v in me.vertices]
            if abs(max(ys) - 1.0) > 0.25 or abs(min(ys) + 1.0) > 0.25: problems.append("barrier y range %.2f..%.2f" % (min(ys), max(ys)))
        if c == "Manholes" and abs(d.z - 0.015) > 0.008: problems.append("manhole thickness %.3f" % d.z)
        if c == "Drains" and (abs(d.z - 0.01) > 0.003 or abs(d.x - 0.5) > 0.02 or abs(d.y - 0.4) > 0.02): problems.append("drain size %.2f x %.2f x %.3f" % tuple(d))
        if c == "Signs":
            zs = [v.co.z for v in me.vertices]
            if not (2.2 <= max(zs) <= 3.0): problems.append("sign top %.2f" % max(zs))
        if not o.hide_viewport or not o.hide_render: problems.append("not hidden")
        if c == "Streetlights" and not any(m.name == MRS + "PropLamp" for m in me.materials if m): problems.append("no lamp material")
        report[o.name] = (c, len(me.vertices), len(me.polygons), tuple(round(x, 2) for x in d))
        if problems: fails.append("%s: %s" % (o.name, ", ".join(problems)))

# custom sign API
cs = A.custom_sign("NO THROUGH\nROAD", "rect", (0.05, 0.3, 0.1), 0.9)
if cs is None or len(cs.data.vertices) < 50 or not cs.data.uv_layers: fails.append("custom_sign broken")
cs2 = A.custom_sign("ZONE 30", "circle", (0.9, 0.9, 0.9), 0.7)
for o in (cs, cs2): bpy.data.objects.remove(o)

print("\n".join("  %-28s %-13s %5d v %5d f  %s" % (n, *r) for n, r in sorted(report.items(), key=lambda kv: (kv[1][0], kv[0]))))
if fails:
    print("\nFAILURES:\n  " + "\n  ".join(fails))
    if QUICK: sys.exit(1)

# ---- catalogue: visible linked duplicates on a grid, per-collection rows
cat = bpy.data.collections.get("Catalogue") or bpy.data.collections.new("Catalogue")
if cat.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(cat)
GROUPS = [("props", ["Props"]), ("lights_signals", ["Streetlights", "TrafficLights"]), ("trees", ["Trees"]), ("signs", ["Signs"]),
          ("barriers_pillars", ["Barriers", "Pillars", "Manholes", "Drains"]), ("scatter_structures", ["Scatter", "Markings", "Structures"])]
placed = {}  # collection -> list of (object, bbox min, bbox max)
y = 0.0
for gname, members in GROUPS:
    for c in members:
        objs = list(cols[c].objects); x = 0.0; row_depth = 0.0
        for src in objs:
            d = src.dimensions; gap = max(0.6, 0.25 * max(d.x, d.y))
            dup = bpy.data.objects.new(src.name + ".cat", src.data); cat.objects.link(dup)
            dup.location = (x + d.x / 2, y + d.y / 2, 0.0)
            xs = [v.co.x for v in src.data.vertices]; ys = [v.co.y for v in src.data.vertices]; zs = [v.co.z for v in src.data.vertices]
            dup.location = (x - min(xs), y - min(ys), -min(zs))
            lo = Vector(dup.location) + Vector((min(xs), min(ys), min(zs))); hi = Vector(dup.location) + Vector((max(xs), max(ys), max(zs)))
            placed.setdefault(c, []).append((dup, lo, hi))
            x += d.x + gap; row_depth = max(row_depth, d.y)
        y += row_depth + 2.5

# ground plane + lighting
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200.0); gm = bpy.data.meshes.new("Ground"); bm.to_mesh(gm); bm.free()
ground = bpy.data.objects.new("Ground", gm); cat.objects.link(ground); ground.location = (60, 30, -0.002)
gm.materials.append(A.pmat(MRS + "CatalogueGround", (0.42, 0.42, 0.4), 0.9, var=0.08, scale=0.3))
scene = bpy.context.scene
cam, sun = qa.ensure_camera_and_sun(scene)
sun.data.energy = 4.0; sun.rotation_euler = (math.radians(48), 0, math.radians(150))  # light from the +Y side (the road side the props face)
try: scene.render.engine = "BLENDER_EEVEE"
except TypeError: scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = False


def frame(objs, direction=(0.35, 1.0, 0.5), lens=35.0, pad=1.12, aspect=16 / 9.0):
    """Camera eye/target that fits the bounding boxes of `objs` seen from `direction` (projected extents)."""
    lo = Vector((min(b[1].x for b in objs), min(b[1].y for b in objs), min(b[1].z for b in objs)))
    hi = Vector((max(b[2].x for b in objs), max(b[2].y for b in objs), max(b[2].z for b in objs)))
    c = (lo + hi) / 2; d = Vector(direction).normalized()
    right = d.cross(Vector((0, 0, 1))).normalized(); up = right.cross(d).normalized()
    corners = [Vector((x, y, z)) - c for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    hr = max(abs(p.dot(right)) for p in corners); vr = max(abs(p.dot(up)) for p in corners); dp = max(abs(p.dot(d)) for p in corners)
    hfov = 2 * math.atan(36.0 / (2 * lens)); vfov = 2 * math.atan(36.0 / aspect / (2 * lens))
    dist = max(hr / math.tan(hfov / 2), vr / math.tan(vfov / 2)) * pad + dp
    return tuple(c + d * dist), tuple(c), lens


def render(name, eye, target, lens, res=(1280, 720), samples=32):
    path = os.path.join(OUT, "catalogue_%s.png" % name)
    qa.render(path, eye, target, lens, res=res, samples=samples, scene=scene); print("rendered", path)
    return path


if not QUICK:
    paths = []
    allb = [b for lst in placed.values() for b in lst]
    eye, tgt, lens = frame(allb, (0.2, 1.0, 0.7), 35.0, 1.05); paths.append(render("overview", eye, tgt, lens, res=(1920, 1080)))
    for gname, members in GROUPS:
        bb = [b for c in members for b in placed[c]]
        eye, tgt, lens = frame(bb, (0.3, 1.0, 0.45) if gname in ("props", "signs", "barriers_pillars", "scatter_structures") else (0.45, 1.0, 0.35), 40.0, 1.05)
        paths.append(render(gname, eye, tgt, lens))
    # chunked close-ups (<= 6 objects each) for inspection of every object
    CHUNK = {"Props": (6, (0.25, 1.0, 0.4)), "Streetlights": (6, (0.6, 1.0, 0.3)), "TrafficLights": (4, (-0.8, 1.0, 0.35)), "Signs": (6, (0.1, 1.0, 0.2)),
             "Barriers": (6, (-1.0, 0.7, 0.5)), "Pillars": (3, (0.3, 1.0, 0.5)), "Structures": (4, (0.3, 1.0, 0.45)), "Scatter": (5, (0.2, 1.0, 0.5)),
             "Manholes": (3, (0.2, 0.6, 1.0)), "Drains": (2, (0.2, 0.6, 1.0)), "Trees": (5, (0.3, 1.0, 0.3))}
    for c, (n, direction) in CHUNK.items():
        lst = placed[c]
        for i in range(0, len(lst), n):
            eye, tgt, lens = frame(lst[i:i + n], direction, 45.0, 1.08); paths.append(render("%s_%d" % (c.lower(), i // n + 1), eye, tgt, lens, res=(1280, 720), samples=24))

# ---- assets + save
t0 = time.time()
n = A.mark_assets(os.path.join(OUT, "blender_assets.cats.txt"), previews=not QUICK)
print("marked %d assets in %.1f s" % (n, time.time() - t0))
blend = os.path.join(OUT, "mrs_assets.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
print("saved", blend)

print("\nSUMMARY")
for c in A.COLLECTIONS: print("  %-14s %3d objects" % (c, len(cols[c].objects)))
print("  total          %3d objects, %d assets" % (sum(len(cols[c].objects) for c in A.COLLECTIONS), n))
print("RESULT:", "FAIL" if fails else "PASS")
if fails: sys.exit(1)
