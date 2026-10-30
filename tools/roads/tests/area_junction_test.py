"""MRS_AreaJunction on synthetic footprints (no base library needed): four tongues meeting at a crossing, a mesh
extension (bus bay) and a curve extension (a lane into the junction), one junction object.
    blender --background --factory-startup --python tools/roads/tests/area_junction_test.py -- <out_dir> [--no-render]
Checks: the road surface covers every red footprint and nothing outside the filleted union; reflex corners are rounded
to Inner Radius (the corner arc's distance from the corner point); the roadside is the yellow area minus the road,
raised by Curb Height; Range off takes the object's own mesh bounds; Show off empties it; the result follows a moved
tongue (live). Prints AREA_JUNCTION OK."""
import bpy, bmesh, math, os, sys, time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "area_junction")); os.makedirs(OUT, exist_ok=True)
RENDER = "--no-render" not in argv
from mrs import areajunction as AJ
from mrs.nodes import mod_input_set, mod_input_get

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
AJ.build_all()
sc = bpy.context.scene
roads = bpy.data.collections.new("Roads"); sc.collection.children.link(roads)
juncs = bpy.data.collections.new("Junctions"); sc.collection.children.link(juncs)
Z = 1.0           # the tongues' common level (CRM: "level one")
ROAD_W, SIDE_W, TONGUE = 8.0, 2.0, 10.0


def tongue(name, start, direction):
    """A road tongue as MRS_Road makes one: red carriageway rectangle + yellow roadside strips, footprint attributes."""
    d = Vector(direction).normalized(); n = Vector((-d.y, d.x, 0.0)); s = Vector(start)
    me = bpy.data.meshes.new(name); bm = bmesh.new(); lay = bm.faces.layers.float.new("mrs_tongue")
    def quad(a0, a1, l0, l1, kind):
        vs = [bm.verts.new(s + d * a + n * l) for a, l in ((a0, l0), (a1, l0), (a1, l1), (a0, l1))]
        f = bm.faces.new(vs); f[lay] = kind
    hw = ROAD_W / 2
    quad(0.0, TONGUE, -hw, hw, 1.0); quad(0.0, TONGUE, hw, hw + SIDE_W, 2.0); quad(0.0, TONGUE, -hw - SIDE_W, -hw, 2.0)
    bm.to_mesh(me); bm.free()
    drop = me.attributes.new("mrs_drop", "FLOAT", "POINT")
    for i, v in enumerate(me.vertices): drop.data[i].value = AJ.TONGUE_DROP; v.co.z -= AJ.TONGUE_DROP
    me.materials.append(bpy.data.materials["MRS_TongueRoad"]); me.materials.append(bpy.data.materials["MRS_TongueSide"])
    for p in me.polygons: p.material_index = 0 if me.attributes["mrs_tongue"].data[p.index].value < 1.5 else 1
    o = bpy.data.objects.new(name, me); roads.objects.link(o); return o

# four tongues ending 2 m past the centre (they overlap, as CRM asks)
T = [tongue("T_E", (TONGUE - 2.0, 0, Z), (-1, 0, 0)), tongue("T_W", (-TONGUE + 2.0, 0, Z), (1, 0, 0)),
     tongue("T_N", (0, TONGUE - 2.0, Z), (0, -1, 0)), tongue("T_S", (0, -TONGUE + 2.0, Z), (0, 1, 0))]
for t in T: t.location = (0, 0, 0)
J = AJ.add_area_junction("AJ_Junction", (0.0, 0.0, 0.0), roads, juncs)
dg = bpy.context.evaluated_depsgraph_get()


def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh()
    verts = [o.matrix_world @ v.co for v in me.vertices]; me.calc_loop_triangles()
    mats = [m.name if m else "" for m in me.materials]
    tris = [(tuple(t.vertices), mats[me.polygons[t.polygon_index].material_index] if mats else "") for t in me.loop_triangles]
    ev.to_mesh_clear()
    return verts, tris


def surface_at(verts, tris, x, y, mat_prefix):
    sel = [t for t, m in tris if m.startswith(mat_prefix)]
    if not sel: return None
    bvh = BVHTree.FromPolygons(verts, sel)
    h = bvh.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)), 200.0)
    return None if h[0] is None else h[0].z

t0 = time.time(); verts, tris = evaluated(J); print("evaluated in %.2fs: %d verts %d tris" % (time.time() - t0, len(verts), len(tris)))
check(len(tris) > 0, "the junction builds a mesh from the four tongues")
_ev = J.evaluated_get(bpy.context.evaluated_depsgraph_get()); _me = _ev.to_mesh(); _fe = set()
for _p in _me.polygons: _fe.update(_p.edge_keys)
_loose = sum(1 for _e in _me.edges if _e.key not in _fe); _ev.to_mesh_clear()
check(_loose == 0, "no loose edges (a road end on the outer outline leaves none: %d)" % _loose)
# road everywhere a red footprint is (centre, arms) at the tongues' level
for x, y in ((0, 0), (5, 0), (-5, 0), (0, 5), (0, -5), (3.9, 3.0), (-3.0, -3.9)):
    z = surface_at(verts, tris, x, y, "MRS_Asphalt")
    check(z is not None and abs(z - Z) < 0.01, "road surface at (%.1f, %.1f): %s" % (x, y, "%.3f" % z if z is not None else "none"))
# dense raster (0.5 m): every cell inside a red footprint is asphalt at the level, every cell only in yellow is raised
# paving (a phantom outline would leave a hole or a sliver here)
def inside_rect(x, y, start, d, a0, a1, l0, l1):
    dx, dy = x - start[0], y - start[1]; along = dx * d[0] + dy * d[1]; lat = -dx * d[1] + dy * d[0]
    return a0 <= along <= a1 and l0 <= lat <= l1
TONG = [((TONGUE - 2.0, 0), (-1, 0)), ((-TONGUE + 2.0, 0), (1, 0)), ((0, TONGUE - 2.0), (0, -1)), ((0, -TONGUE + 2.0), (0, 1))]
bad = []; n_cells = 0
rcorner = mod_input_get(J.modifiers[0], "Inner Radius") + 0.3
for i in range(-36, 37):
    for j in range(-36, 37):
        x, y = i * 0.5 + 0.25, j * 0.5 + 0.25
        red = any(inside_rect(x, y, s_, d_, 0.3, TONGUE - 0.3, -ROAD_W / 2 + 0.3, ROAD_W / 2 - 0.3) for s_, d_ in TONG)
        yel = any(inside_rect(x, y, s_, d_, 0.3, TONGUE - 0.3, -ROAD_W / 2 - SIDE_W + 0.3, ROAD_W / 2 + SIDE_W - 0.3) for s_, d_ in TONG) and not red
        if yel and min(abs(abs(x) - ROAD_W / 2), abs(abs(y) - ROAD_W / 2)) < 0.4: continue        # the kerb line itself
        if yel and abs(x) < ROAD_W / 2 + rcorner and abs(y) < ROAD_W / 2 + rcorner: continue        # the filleted corners
        if not (red or yel): continue
        n_cells += 1
        za = surface_at(verts, tris, x, y, "MRS_Asphalt"); zp = surface_at(verts, tris, x, y, "MRS_Paving")
        if red and (za is None or abs(za - Z) > 0.01 or zp is not None): bad.append(("road", x, y, za, zp))
        if yel and (zp is None or abs(zp - (Z + mod_input_get(J.modifiers[0], "Curb Height"))) > 0.01): bad.append(("side", x, y, za, zp))
check(not bad, "dense raster: %d cells checked, %d wrong %s" % (n_cells, len(bad), bad[:4]))
# the corner (4, 4) is a reflex corner of the road region: filleted by Inner Radius 2 -> asphalt reaches the arc
r = mod_input_get(J.modifiers[0], "Inner Radius")
cx = 4.0 + r - r / math.sqrt(2.0)                                         # arc midpoint, on the corner's diagonal
z_in = surface_at(verts, tris, cx - 0.1, cx - 0.1, "MRS_Asphalt"); z_out = surface_at(verts, tris, cx + 0.15, cx + 0.15, "MRS_Asphalt")
check(z_in is not None and z_out is None, "the kerb corner is an arc of Inner Radius %.1f (asphalt to %.2f m along the diagonal)" % (r, cx))
# roadside: on the yellow strips, raised by Curb Height, never on the road
h = mod_input_get(J.modifiers[0], "Curb Height")
zs = surface_at(verts, tris, 7.0, 5.0, "MRS_Paving")
check(zs is not None and abs(zs - (Z + h)) < 0.01, "roadside top at the curb height (%s)" % ("%.3f" % zs if zs is not None else "none"))
check(surface_at(verts, tris, 0.0, 0.0, "MRS_Paving") is None, "no roadside over the road")
# Outer Radius 0: the back of the sidewalk is a sharp corner at (6, 6)
check(surface_at(verts, tris, 5.95, 5.95, "MRS_Paving") is not None, "the sidewalk's back corner is sharp with Outer Radius 0")
# Show off -> empty; Range off -> the cube (2 m) bounds: only tongue islands touching it (all four, they overlap the centre)
mod = J.modifiers[0]
mod_input_set(mod, "Show", False); J.update_tag(); verts0, tris0 = evaluated(J); mod_input_set(mod, "Show", True); J.update_tag()
check(len([t for t, m in tris0 if m]) == 0, "Show off: no junction mesh")
mod_input_set(mod, "Distance", 5.0); J.update_tag(); v3, t3 = evaluated(J)
check(all(surface_at(v3, t3, x, y, "MRS_Asphalt") is not None for x, y in ((6, 0), (-6, 0), (0, 6), (0, -6))),
      "Range 5 m takes the four tongues (a corner of each within 5 m)")
far = tongue("T_FAR", (60, 0, Z), (1, 0, 0)); J.update_tag(); vf, tf = evaluated(J)
check(surface_at(vf, tf, 65.0, 0.0, "MRS_Asphalt") is None, "a tongue outside the range is left alone")
mod_input_set(mod, "Distance", 40.0)
mod_input_set(mod, "Range", False)
for v in J.data.vertices: v.co = v.co * 5.0                     # CRM: scale the junction's cube in edit mode to cover the tongues
J.data.update(); J.update_tag(); vr, tr_ = evaluated(J)
check(surface_at(vr, tr_, 5.0, 0.0, "MRS_Asphalt") is not None and surface_at(vr, tr_, 65.0, 0.0, "MRS_Asphalt") is None, "Range off: the object's own mesh bounds select")
mod_input_set(mod, "Range", True); bpy.data.objects.remove(far)
# tongues that do not quite meet (a 4 x 4 m gap they enclose) still make one road: the hole is filled, no raised square
for t_ in T: t_.location = (0, 0, 0)
moves = ((T[0], (4.0, 0, 0)), (T[1], (-4.0, 0, 0)), (T[2], (0, 4.0, 0)), (T[3], (0, -4.0, 0)))
for t_, mv in moves: t_.location = mv
J.update_tag(); vg, tg = evaluated(J)
zc = surface_at(vg, tg, 0.0, 0.0, "MRS_Asphalt")
check(zc is not None and surface_at(vg, tg, 0.0, 0.0, "MRS_Paving") is None, "a gap the tongues enclose is filled as road (centre: %s)" % zc)
for t_ in T: t_.location = (0, 0, 0)
# live: move the east tongue 3 m east -> the road surface follows
T[0].location.x += 3.0; J.update_tag(); vl, tl = evaluated(J)
check(surface_at(vl, tl, 10.5, 0.0, "MRS_Asphalt") is not None and surface_at(verts, tris, 10.5, 0.0, "MRS_Asphalt") is None,
      "the junction follows a moved tongue (asphalt now reaches x = 10.5)")
T[0].location.x -= 3.0
# a mesh extension (bus bay) on the east arm's north side and a curve extension (a lane) to the south-west
bay = AJ.add_extension("AJ_BusBay", "square", roads, (7.0, 6.0, Z), (6.0, 4.0), **{"Roadside Size": 2.0})
lane = AJ.add_extension("AJ_Lane", "curve", roads, (0, 0, 0), points=[(-3.0, -3.0, Z), (-14.0, -14.0, Z)], **{"Road Size": 4.0, "Roadside Size": 1.5})
J.update_tag(); ve, te = evaluated(J)
check(surface_at(ve, te, 7.0, 6.5, "MRS_Asphalt") is not None, "the bus bay extension is road")
check(surface_at(ve, te, 7.0, 9.2, "MRS_Paving") is not None, "the bus bay has its roadside band behind it")
check(surface_at(ve, te, -9.0, -9.0, "MRS_Asphalt") is not None, "the curve extension is road")
lv = [v.z for v in ve]
check(min(lv) > Z - 0.01 and max(lv) < Z + 0.2, "every vertex at the tongues' level (z %.3f..%.3f; the bus bay object sits at z 1 with its mesh at 0)" % (min(lv), max(lv)))

# a road's own carriageway beyond the east tongue (an MRS_Road surface: lat + kind attributes) and a round extension
# whose roadside band reaches over it: the band stops at the carriageway (no raised slab across the road)
me_s = bpy.data.meshes.new("RoadSurface"); me_s.from_pydata([(8.0, -4.0, Z), (40.0, -4.0, Z), (40.0, 4.0, Z), (8.0, 4.0, Z)], [], [(0, 1, 2, 3)])
for nm_, val in (("lat", 0.0), ("kind", 0.0)):
    a_ = me_s.attributes.new(nm_, "FLOAT", "FACE" if nm_ == "kind" else "POINT")
    for d_ in a_.data: d_.value = val
surf_o = bpy.data.objects.new("RoadSurface", me_s); roads.objects.link(surf_o)
AJ.add_extension("AJ_Ring", "round", roads, (24.0, 0.0, Z), (6.0, 6.0), **{"Roadside Size": 3.0})
mod_input_set(J.modifiers[0], "Distance", 60.0); J.update_tag(); vs_, ts_ = evaluated(J)
check(surface_at(vs_, ts_, 28.5, 0.0, "MRS_Paving") is None, "an extension's band over a road's carriageway builds no roadside there")
check(surface_at(vs_, ts_, 24.0, 5.5, "MRS_Paving") is not None, "...but it does beside the carriageway")
check(surface_at(vs_, ts_, 24.0, 0.0, "MRS_Asphalt") is not None, "the extension itself is road")
if RENDER:
    from mrs import qa
    for name, eye, tgt, lens in (("aj_top", (0, 0, 60), (0, 0.01, 0), 30.0), ("aj_corner", (14, 12, 9), (2, 2, 1), 28.0)):
        try:
            qa.render(os.path.join(OUT, name + ".png"), Vector(eye), Vector(tgt), lens, res=(1280, 800), samples=8, scene=sc)
            print("RENDER", name)
        except Exception as e:
            print("render failed:", e)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "area_junction.blend"), copy=True)
print("AREA_JUNCTION %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
sys.exit(1 if fails else 0)
