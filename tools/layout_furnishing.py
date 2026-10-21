"""Resolve and check the Cedar House furnishing (world/cedar_house/furnishing.json).

Run headless:
  blender --background --factory-startup --python tools/layout_furnishing.py -- [--render <dir>] [--no-write]

* imports the house (world/cedar_house/assets/cedar_house.glb) and every prop at its placement;
* props with "snap": true are dropped onto whatever is under them (house counters, tables,
  shelves or props placed earlier in the list): rays from p (centre and four inset corners),
  the highest hit wins, so items stand on a surface instead of floating or sinking;
* reports props that intersect the house walls/fixtures (collisions.json boxes) or each other,
  props inside door swings and walkways, and writes the resolved heights back (unless --no-write);
* --render <dir>: first-person workbench views of every room for QA.
Coordinates are house coordinates in Blender axes (see the json header).
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOUSE = os.path.join(ROOT, "world", "cedar_house")
LAYOUT = os.path.join(HOUSE, "furnishing.json")
CATALOG = os.path.join(ROOT, "assets", "interiors", "catalog.json")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = ARGS[ARGS.index("--render") + 1] if "--render" in ARGS else None
WRITE = "--no-write" not in ARGS

# Clear zones: door swings (hinge, leaf length, swing side) and walkways that must stay free.
KEEP_CLEAR = {
    "front door swing": (0.37, 1.64, -5.50, -4.40),
    "rear door swing": (0.56, 1.82, 4.40, 5.50),
    "bedroom 1 door swing": (1.85, 2.80, -4.98, -3.85),
    "bedroom 2 door swing": (1.85, 2.80, -0.33, 0.80),
    "bathroom door swing": (1.85, 2.80, 3.52, 4.65),
    "hall walkway": (0.45, 1.25, -5.40, 5.40),
    "living-kitchen passage": (-1.90, -0.50, -1.00, 0.20),
}
FLOOR_PROPS_ONLY = 1.2   # walkway checks only consider props reaching below this height
# Expected contacts: the dishwasher takes the place of a base-cabinet module and keeps its collider.
ALLOWED = {("dishwasher", "Base cabinet")}


def log(*a):
    print("[layout]", *a, flush=True)


def world_bounds(objs):
    pts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(o.matrix_world)
        pts.append(co @ m[:3, :3].T + m[:3, 3])
    p = np.concatenate(pts)
    return p.min(0), p.max(0)


def overlap(a_lo, a_hi, b_lo, b_hi):
    d = np.minimum(a_hi, b_hi) - np.maximum(a_lo, b_lo)
    return d if (d > 0).all() else None


def main():
    layout = json.load(open(LAYOUT))
    catalog = {e["id"]: e for e in json.load(open(CATALOG))["props"]}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(HOUSE, "assets", "cedar_house.glb"))
    house = [o for o in bpy.data.objects if o.type == 'MESH']
    for o in house:
        o["house"] = True
    sources = {}
    placed = []   # (item, objects, lo, hi)
    for item in layout["items"]:
        pid = item["id"]
        if pid not in catalog:
            log("MISSING prop", pid)
            continue
        if pid not in sources:
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, catalog[pid]["path"].replace("res://", "")))
            new = [o for o in bpy.data.objects if o not in before]
            for o in new:
                o.hide_set(True)
                o.hide_render = True
            sources[pid] = [o for o in new if o.type == 'MESH']
        objs = []
        for src in sources[pid]:
            o = src.copy()
            bpy.context.scene.collection.objects.link(o)
            o.hide_set(True)
            o.hide_render = False
            objs.append(o)
        x, y, z = item["p"]
        s = float(item.get("s", 1.0))
        yaw = math.radians(float(item.get("yaw", 0.0)))
        base = Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Scale(s, 4)
        for o, src in zip(objs, sources[pid]):
            o.matrix_world = base @ src.matrix_world
        bpy.context.view_layer.update()
        support = None
        if item.get("snap"):
            lo, hi = world_bounds(objs)
            dg = bpy.context.evaluated_depsgraph_get()
            best = None
            cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
            hx, hy = (hi[0] - lo[0]) * 0.3, (hi[1] - lo[1]) * 0.3
            for dx, dy in ((0, 0), (hx, hy), (-hx, hy), (hx, -hy), (-hx, -hy)):
                ok, loc, nrm, idx, hit, mat = bpy.context.scene.ray_cast(dg, Vector((cx + dx, cy + dy, z)), Vector((0, 0, -1)), distance=3.0)
                if ok and (best is None or loc.z > best[0]):
                    best = (loc.z, hit.name)
            if best:
                dz = best[0] - lo[2]
                for o in objs:
                    o.matrix_world = Matrix.Translation((0, 0, dz)) @ o.matrix_world
                item["p"][2] = round(z + dz, 4)
                support = best[1]
            else:
                log("SNAP MISS", pid, item["p"])
        for o in objs:
            o.hide_set(False)
        bpy.context.view_layer.update()
        lo, hi = world_bounds(objs)
        placed.append((item, objs, lo, hi, support))
        item["support"] = support if support else None
        if item["support"] is None:
            item.pop("support")
    # ---------------------------------------------------------------- checks
    boxes = []
    for c in json.load(open(os.path.join(HOUSE, "assets", "collisions.json"))):
        if "ramp" in c or c["name"] in ("Lot", "Foundation", "FloorStructure", "Porch foundation", "Porch walking slab",
                                         "Sidewalk", "Rear deck") or c["name"].startswith("Side path"):
            continue
        p, d = np.array(c["p"]), np.array(c["d"])
        boxes.append((c["name"], p - d / 2, p + d / 2))
    problems = 0
    for item, objs, lo, hi, support in placed:
        size = hi - lo
        shrink = np.array([0.01, 0.01, 0.01])
        for name, blo, bhi in boxes:
            if (item["id"], name) in ALLOWED:
                continue
            d = overlap(lo + shrink, hi - shrink, blo, bhi)
            if d is not None and d.min() > 0.015:
                log("CLIP %-22s (%s) with house %-22s by %s" % (item["id"], item["room"], name, np.round(d, 3)))
                problems += 1
        if lo[2] < 1.2 + 0.732 * 0 and size.max() > 0.3:
            for zone, (x0, x1, y0, y1) in KEEP_CLEAR.items():
                if lo[2] - 0.732 > FLOOR_PROPS_ONLY:
                    continue
                d = overlap(lo[:2], hi[:2], np.array([x0, y0]), np.array([x1, y1]))
                if d is not None and d.min() > 0.02:
                    log("BLOCK %-21s (%s) intrudes into %s by %s" % (item["id"], item["room"], zone, np.round(d, 3)))
                    problems += 1
    for i, (a, ao, alo, ahi, asup) in enumerate(placed):
        for b, bo, blo, bhi, bsup in placed[i + 1:]:
            if asup or bsup:
                continue   # decor resting on a surface (shelves, counters): only furniture is checked
            d = overlap(alo, ahi, blo, bhi)
            if d is not None and d.min() > 0.02:
                log("OVERLAP %s/%s and %s/%s by %s" % (a["id"], a["room"], b["id"], b["room"], np.round(d, 3)))
                problems += 1
    log("%d props placed, %d problems" % (len(placed), problems))
    if WRITE:
        with open(LAYOUT, "w") as f:
            json.dump(layout, f, indent=1)
        log("wrote", LAYOUT)
    if RENDER:
        render_views(RENDER)


VIEWS = {
    # name: (eye xyz, look-at xyz) in house coordinates; eye 1.62 m above the floor
    "living_from_hall": ((0.9, -4.6, 2.35), (-3.0, -2.6, 1.3)),
    "living_from_kitchen": ((-1.6, -0.2, 2.35), (-2.4, -4.6, 1.2)),
    "living_tv": ((-1.2, -2.0, 2.35), (-3.8, -3.6, 1.6)),
    "kitchen_counter": ((-1.0, 2.6, 2.35), (-2.2, 5.3, 1.6)),
    "kitchen_dining": ((0.9, 3.8, 2.35), (-3.0, 0.8, 1.3)),
    "bedroom1": ((2.3, -4.6, 2.35), (3.6, -2.0, 1.2)),
    "bedroom2": ((2.3, -0.1, 2.35), (3.6, 2.6, 1.1)),
    "bathroom": ((2.2, 3.4, 2.35), (3.6, 5.2, 1.0)),
    "hall": ((0.8, -4.9, 2.35), (1.6, 2.5, 1.6)),
    "porch": ((1.1, -9.8, 1.9), (0.0, -6.5, 1.2)),
}


def render_views(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_shadows = True
    try:
        sh.show_cavity = True
    except AttributeError:
        pass
    sc.render.resolution_x, sc.render.resolution_y = 960, 600
    sc.world = bpy.data.worlds.new("W")
    # hide the ceiling and roof so the studio light reaches the rooms
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.get("house") and (o.name.startswith("Interior__Plaster") or "Shingles" in o.name):
            o.hide_render = True
    cam = bpy.data.objects.new("QA", bpy.data.cameras.new("QA"))
    sc.collection.objects.link(cam)
    cam.data.lens = 16
    cam.data.clip_start = 0.05
    sc.camera = cam
    for name, (eye, at) in VIEWS.items():
        cam.location = eye
        cam.rotation_euler = (Vector(at) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out_dir, "lay_%s.png" % name)
        bpy.ops.render.render(write_still=True)


main()
