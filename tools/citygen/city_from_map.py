"""Combined prototype: a City Map Generator street plan (headless, seeded) + Building Shell lots,
each grid district in its own cultural style around a radial plaza."""
import bpy, bmesh, sys, os, json, math, random
sys.path.insert(0, os.path.dirname(__file__))
import evalkit as k
from mathutils import Vector, Matrix
k.enable("procedural_building_shell")
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
SRC = os.path.join(os.path.dirname(k.OUT), "mapgen", "quarters_seed3.json")
m = json.load(open(SRC))
S = 4.0                                   # map unit -> metres
CX, CY = m["layout"]["radials"][0][0], m["layout"]["radials"][0][1]
HX, HY = 170, 120                         # window half-size (map units) round the plaza


def W(p):                                 # map -> Blender (y flipped)
    return Vector(((p[0] - CX) * S, -(p[1] - CY) * S, 0))


def inside(p, pad=0):
    return abs(p[0] - CX) <= HX + pad and abs(p[1] - CY) <= HY + pad


def colour_mat(name, rgba, rough=0.85):
    mt = bpy.data.materials.new(name)
    p = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = rgba
    p.inputs["Roughness"].default_value = rough
    mt.diffuse_color = rgba
    return mt


def flat_mesh(name, polys, z, color, coll):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for poly in polys:
        vs = [bm.verts.new(W(p) + Vector((0, 0, z))) for p in poly]
        if len(vs) >= 3:
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    me.materials.append(colour_mat(name + "_mat", color, 0.9))
    return o


def ribbon(name, lines, width, z, color, coll):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for line in lines:
        pts = [W(p) for p in line if inside(p, 30)]
        for a, b in zip(pts, pts[1:]):
            d = b - a
            if d.length < 0.01:
                continue
            n = Vector((-d.y, d.x, 0)).normalized() * width * 0.5
            bm.faces.new([bm.verts.new(v + Vector((0, 0, z))) for v in (a - n, b - n, b + n, a + n)])
        for p in pts:   # round joints
            bmesh.ops.create_circle(bm, cap_ends=True, radius=width * 0.5, segments=10, matrix=Matrix.Translation(p + Vector((0, 0, z - 0.001))))
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    me.materials.append(colour_mat(name + "_mat", color))
    return o


coll = bpy.data.collections.new("CityFromMap")
bpy.context.scene.collection.children.link(coll)
flat_mesh("Ground", [[(CX - HX - 40, CY - HY - 40), (CX + HX + 40, CY - HY - 40), (CX + HX + 40, CY + HY + 40), (CX - HX - 40, CY + HY + 40)]], -0.05, (0.36, 0.38, 0.33, 1), coll)
if m["parks"]:
    flat_mesh("Parks", m["parks"], 0.02, (0.25, 0.42, 0.2, 1), coll)
for nm in ("sea", "river"):
    if len(m[nm]) > 2:
        flat_mesh(nm.title(), [m[nm]], 0.03, (0.18, 0.35, 0.5, 1), coll)
WIDTH = {"minor": 10.0, "major": 14.0, "main": 18.0}
for cls in ("minor", "major", "main"):
    ribbon("Sidewalk_" + cls, m[cls], WIDTH[cls] + 6.0, 0.05, (0.62, 0.6, 0.56, 1), coll)
for cls in ("minor", "major", "main"):
    ribbon("Road_" + cls, m[cls], WIDTH[cls], 0.08 + {"minor": 0, "major": 0.005, "main": 0.01}[cls], (0.13, 0.13, 0.14, 1), coll)

GRIDS = m["layout"]["grids"]
CULTURES = ["turkish", "european", "japanese", "latin"]
STYLE = {
    "turkish": dict(floors=(3, 4), window_type="TALL", ground_floor_windows="STOREFRONT", facade_pilasters=True, pilaster_style="CORNERS", roof_parapet=True,
                    walls=[(0.86, 0.80, 0.68), (0.93, 0.89, 0.80), (0.80, 0.66, 0.50)], roof=(0.55, 0.27, 0.18)),
    "european": dict(floors=(4, 4), window_type="RECTANGULAR", ground_floor_windows="STOREFRONT_WIDE", facade_pilasters=True, pilaster_style="BETWEEN_WINDOWS", roof_parapet=True,
                     walls=[(0.84, 0.72, 0.52), (0.78, 0.62, 0.55), (0.88, 0.84, 0.74), (0.70, 0.74, 0.70)], roof=(0.30, 0.31, 0.33)),
    "japanese": dict(floors=(2, 3), window_type="SQUARE", ground_floor_windows="REGULAR", facade_pilasters=False, pilaster_style="CORNERS", roof_parapet=False,
                     walls=[(0.82, 0.82, 0.80), (0.55, 0.55, 0.56), (0.42, 0.33, 0.26), (0.90, 0.90, 0.88)], roof=(0.22, 0.24, 0.27)),
    "latin": dict(floors=(1, 2), window_type="RECTANGULAR", ground_floor_windows="REGULAR", facade_pilasters=True, pilaster_style="CORNERS", roof_parapet=True,
                  walls=[(0.93, 0.55, 0.55), (0.35, 0.75, 0.72), (0.98, 0.82, 0.35), (0.60, 0.80, 0.45), (0.95, 0.68, 0.40)], roof=(0.70, 0.40, 0.25)),
}
mats = {}


def mat(name, rgb):
    if name not in mats:
        mats[name] = colour_mat(name, (*rgb, 1), 0.8)
    return mats[name]


def culture_of(c):
    rx, ry, rs = m["layout"]["radials"][0][:3]
    if math.hypot(c[0] - rx, c[1] - ry) < rs * 0.33:
        return "plaza"
    best = min(range(len(GRIDS)), key=lambda i: math.hypot(c[0] - GRIDS[i][0], c[1] - GRIDS[i][1]))
    return CULTURES[best % len(CULTURES)]


def min_rect(poly):
    """Minimum-area rectangle of a lot: width, depth, angle of the width edge, centre (map units)."""
    best = None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        ca, sa = math.cos(-ang), math.sin(-ang)
        xs = [p[0] * ca - p[1] * sa for p in poly]
        ys = [p[0] * sa + p[1] * ca for p in poly]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if best is None or area < best[0]:
            cxr, cyr = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
            cx = cxr * math.cos(ang) - cyr * math.sin(ang)
            cy = cxr * math.sin(ang) + cyr * math.cos(ang)
            best = (area, max(xs) - min(xs), max(ys) - min(ys), ang, (cx, cy))
    return best[1:]


road_pts = [(p[0], p[1]) for cls in ("minor", "major", "main") for line in m[cls] for p in line if inside(p, 40)]


def nearest_road(c):
    return min(road_pts, key=lambda r: (r[0] - c[0]) ** 2 + (r[1] - c[1]) ** 2)


random.seed(7)
op = bpy.ops.mesh.procedural_building_shell
lots = [l for l in m["lots"] if len(l) >= 3 and all(inside(p) for p in l)]
count = {}
with k.Timer() as t:
    for i, lot in enumerate(lots[:900]):
        c = (sum(p[0] for p in lot) / len(lot), sum(p[1] for p in lot) / len(lot))
        cult = culture_of(c)
        if cult == "plaza":
            continue
        st = STYLE[cult]
        w, d, ang, (cx, cy) = min_rect(lot)
        w, d = w * S * 0.86, d * S * 0.86
        if w < d:
            w, d, ang = d, w, ang + math.pi / 2
        if cult == "japanese":
            w, d = min(w, 14.0), min(d, 12.0)
        w, d = max(5.0, min(w, 40.0)), max(5.0, min(d, 26.0))
        kw = dict(width=w, depth=d, floors=random.randint(*st["floors"]), floor_height=3.4 if cult == "latin" else 3.2, window_type=st["window_type"],
                  windows_per_floor=max(1, int(w / 3.2)), ground_floor_windows=st["ground_floor_windows"], facade_pilasters=st["facade_pilasters"],
                  pilaster_style=st["pilaster_style"], roof_parapet=st["roof_parapet"], building_profile="NONE", interior_fill="NONE",
                  back_exit=False, floor_slabs=False, has_patio=(cult == "latin" and random.random() < 0.4), seed=i)
        before = set(bpy.data.objects)
        op(**kw)
        o = next(x for x in bpy.data.objects if x not in before)
        for c_ in list(o.users_collection):
            c_.objects.unlink(o)
        coll.objects.link(o)
        # the front (local -Y, the door side) faces the nearest road
        r = nearest_road(c)
        to_road = Vector((r[0] - c[0], -(r[1] - c[1]), 0)).normalized()     # Blender space
        base = -ang                                                           # width edge along the lot's edge (y flipped)
        cands = [base + q * math.pi / 2 for q in range(4)]
        def front(a):
            return Vector((math.sin(a), -math.cos(a), 0))                     # local -Y rotated by a
        a = max(cands, key=lambda a_: front(a_).dot(to_road))
        o.rotation_euler.z = a
        off = Vector((-w / 2, -d / 2, 0))
        off.rotate(o.rotation_euler)
        o.location = W((cx, cy)) + off + Vector((0, 0, 0.1))
        o.material_slots[0].material = mat("Walls_%s_%d" % (cult, i % len(st["walls"])), st["walls"][i % len(st["walls"])])
        o.material_slots[2].material = mat("Roof_" + cult, st["roof"])
        o.material_slots[3].material = mat("Frame_" + cult, (0.2, 0.18, 0.16) if cult == "japanese" else (0.92, 0.92, 0.9))
        count[cult] = count.get(cult, 0) + 1
print("CITYMAP lots in window", len(lots), "built", count, "in %.1fs" % t.s, k.stats(list(coll.objects)))
k.light_scene(3.5)
k.render("citymap_overview", Vector((-560, -620, 520)), Vector((0, 0, 0)), lens=32, clip_end=8000)
k.render("citymap_top", Vector((0, -1, 1300)), Vector((0, 0, 0)), lens=40, clip_end=8000)
k.render("citymap_street", Vector((-30, -40, 1.7)), Vector((40, 60, 8)), lens=24)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(k.OUT, "citymap_test.blend"))
