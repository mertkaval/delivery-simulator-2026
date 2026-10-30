"""MRS_Road tongues + MRS_AreaJunction with real roads (the CRM 2.1 junction workflow), on the base library.
    blender --background <base.blend> --python tools/roads/tests/road_tongue_test.py -- <out_dir> [--rebuild-groups] [--no-render]
(--rebuild-groups rebuilds the road and area-junction groups from the current code first: a library older than the code.)
Four residential roads drawn to a crossing with 10 m tongues and one junction object: the junction's asphalt reaches
each road's trimmed end, its roadside matches the roads' kerb + sidewalk width, tongues disappear under it; a tongue
size change moves the road end and the junction with it. Prints ROAD_TONGUE OK."""
import bpy, math, os, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "road_tongue")); os.makedirs(OUT, exist_ok=True)
RENDER = "--no-render" not in argv
import mrs
from mrs import areajunction as AJ, roads, nodes
from mrs.nodes import mod_input_set, mod_input_get
if "--rebuild-groups" in argv:
    from mrs import road
    road.build_road_group(); AJ.build_all()
else:
    AJ.build_all()

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

sc = bpy.data.scenes.new("RT_Scene"); nodes.set_scene(sc)
try: bpy.context.window.scene = sc
except Exception: pass
rc = bpy.data.collections.new("Roads"); sc.collection.children.link(rc)
jc = bpy.data.collections.new("Junctions"); sc.collection.children.link(jc)
Z, L, TG = 1.0, 60.0, 10.0
R = {}
for name, d in (("RT_E", (1, 0)), ("RT_W", (-1, 0)), ("RT_N", (0, 1)), ("RT_S", (0, -1))):
    pts = [(d[0] * L, d[1] * L, Z), (-d[0] * 2.0, -d[1] * 2.0, Z)]                     # drawn to 2 m past the centre (overlap)
    R[name] = roads.make_road(name, pts, rc, "residential", Conform=False, Embankment=False, Tongue_End=TG, Props=None, Trees=None, Streetlights=None)
J = AJ.add_area_junction("RT_Junction", (0.0, 0.0, Z), rc, jc)


def surf(o):
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles()
    M = o.matrix_world; verts = [M @ v.co for v in me.vertices]
    mats = [m.name if m else "" for m in me.materials]
    tris = [(tuple(t.vertices), mats[me.polygons[t.polygon_index].material_index] if mats else "") for t in me.loop_triangles]
    ev.to_mesh_clear(); return verts, tris


def top(objs, x, y):
    """(z, material) of the highest surface over (x, y) among objs."""
    best = None
    for o in objs:
        v, t = surf(o)
        if not t: continue
        bvh = BVHTree.FromPolygons(v, [a for a, _ in t]); h = bvh.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)), 200.0)
        if h[0] is not None and (best is None or h[0].z > best[0]): best = (h[0].z, t[h[2]][1])
    return best

allo = list(R.values()) + [J]
w = roads.road_widths(R["RT_E"]); half = w["half_r"]; outer = w["half_r"] + w["curb"] + w["swr"]
print("road half %.2f, kerb + sidewalk to %.2f" % (half, outer))
c = top(allo, 0.0, 0.0); check(c is not None and c[1].startswith("MRS_Asphalt") and abs(c[0] - Z) < 0.05, "centre: junction asphalt at the road level %s" % (c,))
t = top(allo, 0.0, -9.0); check(t is not None and not t[1].startswith("MRS_Tongue"), "inside the south tongue: no tongue showing (%s)" % (t,))
e = top(allo, 15.0, 1.6); check(e is not None and e[1].startswith("MRS_Asphalt") and e[0] > Z + 0.01, "past the tongue the road itself carries on, crowned (%s)" % (e,))
s_ = top(allo, 8.1, 0.0); check(s_ is not None and abs(s_[0] - Z) < 0.01, "no step where road and junction meet: the crown fades out at a tongue (%s)" % (s_,))
jx = top([J], 8.03, 1.6); check(jx is not None and jx[1].startswith("MRS_Asphalt") and jx[0] < Z, "the junction runs on under the road's first centimetres, just below it (no hairline crack: %s)" % (jx,))
k = top(allo, 9.0, half + 0.5 * (outer - half)); check(k is not None and abs(k[0] - Z) > 0.05 and not k[1].startswith("MRS_Tongue"), "tongue roadside covered by the raised junction roadside (%s)" % (k,))
r = mod_input_get(J.modifiers[0], "Inner Radius")
cr = top(allo, half + 0.3, half + 0.3); check(cr is not None and cr[1].startswith("MRS_Asphalt"), "the kerb corner is rounded (asphalt at the corner %s)" % (cr,))
for o in R.values(): mod_input_set(o.modifiers["MRS_Road"], "Tongue End", 16.0); o.update_tag()
J.update_tag()
m = top(allo, 0.0, -12.5); check(m is not None and m[1].startswith("MRS_Asphalt") and abs(m[0] - Z) < 0.01, "longer tongues: the junction grows with them (%s)" % (m,))
if RENDER:
    from mrs import qa
    for nm, eye, tgt, lens in (("rt_top", (0, 0, 70), (0, 0.01, Z), 32.0), ("rt_corner", (22, 18, 10), (2, 2, Z), 28.0)):
        qa.render(os.path.join(OUT, nm + ".png"), Vector(eye), Vector(tgt), lens, res=(1280, 800), samples=12, scene=sc); print("RENDER", nm)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "road_tongue.blend"), copy=True, compress=True)
print("ROAD_TONGUE %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
sys.exit(1 if fails else 0)
