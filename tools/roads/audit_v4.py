"""v4 audit: list every MRS_* asset collection (objects, dimensions, triangles, materials, custom
properties) and render one contact sheet per collection to tmp/roads/v4/audit/.

    blender -b tmp/roads/v3/street_block.blend --python tools/roads/audit_v4.py [-- --no-render]
"""
import bpy, os, sys, json, math
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
OUT = os.path.join(ROOT, "tmp", "roads", "v4", "audit"); os.makedirs(OUT, exist_ok=True)
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def tris(o):
    if o.type != "MESH": return 0
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def dims(o):
    if o.type != "MESH" or not len(o.data.vertices): return (0, 0, 0)
    xs = [v.co for v in o.data.vertices]
    return tuple(round(max(c[i] for c in xs) - min(c[i] for c in xs), 2) for i in range(3))


inv = {}
for col in sorted(bpy.data.collections, key=lambda c: c.name):
    if not col.name.startswith("MRS_") or col.name.startswith(("MRS_StreetBlock", "MRS_CityBlock", "MRS_Mountain", "MRS_Highway", "MRS_Village", "MRS_BridgeValley", "MRS_Export")): continue
    rows = []
    for o in sorted(col.objects, key=lambda o: o.name):
        rows.append({"name": o.name, "type": o.type, "dims": dims(o), "tris": tris(o) + sum(tris(c) for c in o.children),
                     "materials": sorted({s.material.name for s in o.material_slots if s.material}) if o.type == "MESH" else [],
                     "children": len(o.children), "props": {k: (o[k] if isinstance(o[k], (int, float, str)) else str(o[k])[:60]) for k in o.keys() if not k.startswith("_")}})
    inv[col.name] = rows
json.dump(inv, open(os.path.join(OUT, "inventory.json"), "w"), indent=1)
for c, rows in inv.items():
    print("== %s (%d)" % (c, len(rows)))
    for r in rows: print("   %-30s %-6s dims %-22s tris %6d mats %s" % (r["name"], r["type"], r["dims"], r["tris"], ",".join(r["materials"])[:70]))

if "--no-render" not in args:
    from mrs import qa
    sc = bpy.data.scenes.new("MRS_Audit"); bpy.context.window_manager  # noqa
    # background: render needs the active scene; reuse the file's active scene with a temp collection
    sc = bpy.context.scene
    for c in list(sc.collection.children): sc.collection.children.unlink(c)
    stage = bpy.data.collections.new("MRS_AuditStage"); sc.collection.children.link(stage)
    me = bpy.data.meshes.new("AuditGround"); me.from_pydata([(-500, -500, 0), (500, -500, 0), (500, 500, 0), (-500, 500, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("AuditGround", me); stage.objects.link(g)
    gm = bpy.data.materials.new("AuditGroundMat"); gm.diffuse_color = (0.45, 0.45, 0.45, 1); gm.use_nodes = True
    next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1); me.materials.append(gm)
    for cname, rows in inv.items():
        objs = [bpy.data.objects[r["name"]] for r in rows if r["type"] in ("MESH", "EMPTY", "CURVE") and bpy.data.objects[r["name"]].parent is None]
        if not objs: continue
        for o in list(stage.objects):
            if o.name != "AuditGround": stage.objects.unlink(o)
        x = 0.0; gap = 0.6; inst = []
        for o in objs:
            if o.type != "MESH": continue
            d = dims(o); w = max(d[0], 0.4)
            xs = [v.co.x for v in o.data.vertices]; cx = (max(xs) + min(xs)) / 2 if xs else 0.0
            c = bpy.data.objects.new("AU_" + o.name, o.data); stage.objects.link(c)
            c.location = (x + w / 2 - cx, 0, 0); c.hide_render = False
            for ch in o.children:
                if ch.type not in ("MESH", "FONT", "CURVE"): continue
                c2 = bpy.data.objects.new("AU_" + ch.name, ch.data); stage.objects.link(c2); c2.parent = c
                c2.matrix_parent_inverse = ch.matrix_parent_inverse.copy(); c2.location = ch.location; c2.rotation_euler = ch.rotation_euler; c2.scale = ch.scale
            inst.append((c, d)); x += w + gap
        if not inst: continue
        span = max(x, 2.0); hmax = max(max(d[2] for _, d in inst), 0.5)
        dist = max(span * 0.85, hmax * 2.2)
        qa.render(os.path.join(OUT, "%s.png" % cname[4:].lower()), (span / 2, -dist, hmax * 0.9 + dist * 0.18), (span / 2, 0, hmax * 0.4), 35, res=(1600, 500), samples=16, scene=sc)
        print("rendered", cname)
