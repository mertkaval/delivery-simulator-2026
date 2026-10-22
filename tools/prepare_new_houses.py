"""Convert the three supplied house models into game-ready residential house types.

"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" --background --factory-startup \
    --python tools/prepare_new_houses.py -- [house_suburban house_duplex house_farmhouse] [--probe] [--no-bake]

Sources (raw, Godot-ignored) in source_assets/incoming_2026_10_21/:
  suburban_house.glb -> assets/houses/house_suburban(.glb, _far.glb)   gambrel 1.5-storey with side carport
  duplex_house.glb   -> assets/houses/house_duplex(...)                  up/down two-flat, brick + siding
  house.glb          -> assets/houses/house_farmhouse(...)               farmhouse cottage with deep porch

Contract (same as world/citykit/build_houses.py, read by HouseInstancer / ResidentialLayout):
  * metres, Y-up glTF; origin at the front-centre of the footprint on the ground; the street
    facade faces Godot +Z (Blender -Y); the house extends to Godot z = -D.
  * one mesh per material, named Kit<Material>, so CityKit.material() supplies the shared
    world-triplanar PBR materials and HouseInstancer tints body/trim/door/roof per instance.
    No source textures survive (every surface maps to the shared 1024 px kit library).
  * near LOD (<= ~20k tris) with baked AO in vertex colour; _far LOD (~1/3) for 45-110 m;
    beyond that the instancer's own wall+roof massing.
  * glTF extras on the root empty and assets/houses/houses.json: door (Godot local x, floor y, z),
    step height, w/d/h, collision boxes and stair ramp, massing (eave, rise, ridge axis).
Pipeline per house: bake transforms, drop junk (scale figures, ground plane, door hardware),
scale to real size, turn to face the street, ground at y=0, remap materials, merge doubles,
remove faces nobody can see (ray visibility with opaque windows and the ground as blocker),
flip back-facing faces / double thin single-sided panels, limited dissolve, collapse decimate
to budget, push coplanar overlapping detail faces 6 mm out (no z-fighting), smooth-by-angle
normals, AO bake, far LOD, export, QA renders (assets/houses/qa/, .gdignore).
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source_assets", "incoming_2026_10_21")
OUT = os.path.join(ROOT, "assets", "houses")
QA = os.path.join(OUT, "qa")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PROBE = "--probe" in ARGS
BAKE = "--no-bake" not in ARGS
ONLY = [a for a in ARGS if not a.startswith("--")]

# Godot local (x, y, z) <-> Blender (x, -z, y)
def g2b(x, y, z):
    return Vector((x, -z, y))

# Render priority for coplanar overlaps: the higher one is pushed 6 mm towards the viewer.
RANK = {"KitGlass": 0, "KitSidingPaint": 1, "KitLapSiding": 1, "KitBrickRed": 1, "KitConcrete": 1, "KitPlinthDark": 1,
        "KitAsphaltShingles": 1, "KitDeckBoards": 1, "KitTrimPaint": 2, "KitDoorPaint": 3, "KitRailBlack": 3,
        "KitFrameDark": 3, "KitDoorWood": 3, "KitLampGlow": 4}

HOUSES = {
    "house_suburban": {
        "src": "suburban_house.glb", "scale": 1.0, "yaw": 180.0,
        # source point that becomes the origin (front wall plane, footprint centre x, ground)
        "origin": (7.915, 0.50, 0.0),
        "materials": {"floor": "KitDeckBoards", "glass": "KitGlass", "material": "KitPlinthDark", "roof": "KitAsphaltShingles",
                      "siding": "KitSidingPaint", "white": "KitTrimPaint"},
        "drop_materials": [],
        "drop_island_tris": 3000,       # 1.75 m scale figures (5 of them)
        # The front door leaf beside its sidelight is white trim in the source: paint it per house.
        "recolour_regions": [("KitTrimPaint", "KitDoorPaint", (-3.92, 0.02, -3.13), (-2.97, 2.40, -3.03))],
        "budget": 20000, "far_ratio": 0.33,
        # porch, carport and side-deck floors lie on the lawn (y = 0): raised 4 cm
        "lift_floor": ("KitDeckBoards",),
        # corner boards the automatic pass cannot see: the 7 cm wall return under the right-hand
        # eave (x 7.915 / z -5.576), Godot (lo, hi) boxes
        "extra_boards": [((7.915, 3.14, -5.686), (7.970, 4.10, -5.576), ()), ((7.890, 3.14, -5.576), (7.970, 4.10, -5.541), ("-z",)),
                         ((7.905, 3.14, -3.511), (7.970, 3.20, -3.476), ())],
    },
    "house_duplex": {
        "src": "duplex_house.glb", "scale": 0.0254, "yaw": 0.0,
        "origin": (-8.07, -315.75, 0.0),     # source units are inches
        "materials": {"Wood01": "KitTrimPaint", "Translucent_Glass_Gray": "KitGlass", "soffit": "KitTrimPaint",
                      "Concrete05": "KitConcrete", "Bricks026": "KitBrickRed", "Siding03": "KitLapSiding",
                      "block01": "KitConcrete", "Roof01": "KitAsphaltShingles", "Shutter": "KitDoorPaint"},
        "drop_materials": ["Color_M08", "Handle", "edge_color000255"],
        "drop_island_tris": 0,
        "budget": 12000, "far_ratio": 0.4,
    },
    "house_farmhouse": {
        "src": "house.glb", "scale": 1.0, "yaw": 0.0,
        "origin": (0.595, -3.10, 0.07),  # gable-wing front wall, footprint centre, lawn level
        "materials": {"window": "KitGlass", "woodfloor": "KitDeckBoards", "foof": "KitAsphaltShingles",
                      "Material.014": "KitTrimPaint", "door1": "KitDoorPaint", "door2": "KitGlass",
                      "panesl": "KitLapSiding", "slats": "KitDoorPaint", "slats_wood": "KitDoorPaint"},
        "drop_materials": ["Material.013", "black_stuff"],
        # The source door is an alpha-textured storm door over a see-through opening: clear the
        # opening (a solid leaf with a glazed upper light is added back by farmhouse_door).
        "drop_regions": [("*", (-1.40, 0.53, -2.2), (-0.61, 2.60, -1.55))],
        "drop_island_tris": 0,
        "budget": 8000, "far_ratio": 0.4,
    },
}


# ------------------------------------------------------------------ helpers
def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def load_joined(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.polygons)]
    for o in meshes:
        o.data = o.data.copy()
        o.data.transform(o.matrix_world)
    for o in list(bpy.data.objects):
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    for o in meshes:
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    ctx = bpy.context
    for o in meshes:
        o.select_set(True)
    ctx.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    obj = ctx.view_layer.objects.active
    obj.name = "House"
    return obj


def island_faces(bm):
    seen = set()
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, group = [f], []
        seen.add(f.index)
        while stack:
            a = stack.pop()
            group.append(a)
            for e in a.edges:
                for b in e.link_faces:
                    if b.index not in seen:
                        seen.add(b.index)
                        stack.append(b)
        yield group


def remap_materials(obj, mapping, drop):
    """Delete faces of dropped materials, rename the rest to Kit materials (merged slots)."""
    me = obj.data
    names = [m.name if m else "" for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    kill = [f for f in bm.faces if names[f.material_index] in drop]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    targets = []
    for n in names:
        if n in drop:
            targets.append(None)
            continue
        if n not in mapping:
            raise RuntimeError("unmapped material %r" % n)
        targets.append(mapping[n])
    uniq = sorted({t for t in targets if t})
    index = [uniq.index(targets[f.material_index]) for f in bm.faces]
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    for n in uniq:
        mat = bpy.data.materials.get(n) or bpy.data.materials.new(n)
        me.materials.append(mat)
    # (materials.clear() resets the face material indices)
    me.polygons.foreach_set("material_index", index)
    me.update()
    # Source vertex colours / extra attributes are not part of the contract.
    for a in list(me.color_attributes):
        me.color_attributes.remove(a)
    return uniq


def drop_region(obj, mat, lo, hi):
    """Delete faces of `mat` whose centre lies in the Godot-local box lo..hi."""
    mi = -1 if mat == "*" else [m.name for m in obj.data.materials].index(mat)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        gx, gy, gz = c.x, c.z, -c.y
        if mi in (-1, f.material_index) and lo[0] <= gx <= hi[0] and lo[1] <= gy <= hi[1] and lo[2] <= gz <= hi[2]:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    print("drop_region", mat, len(kill))


def recolour_region(obj, src, dst, lo, hi):
    """Move faces of `src` whose centre lies in the Godot-local box lo..hi to material `dst`."""
    me = obj.data
    names = [m.name for m in me.materials]
    if dst not in names:
        me.materials.append(bpy.data.materials.get(dst) or bpy.data.materials.new(dst))
        names.append(dst)
    si, di = names.index(src), names.index(dst)
    bm = bmesh.new()
    bm.from_mesh(me)
    n = 0
    for f in bm.faces:
        c = f.calc_center_median()
        gx, gy, gz = c.x, c.z, -c.y
        if f.material_index == si and lo[0] <= gx <= hi[0] and lo[1] <= gy <= hi[1] and lo[2] <= gz <= hi[2]:
            f.material_index = di
            n += 1
    bm.to_mesh(me)
    bm.free()
    print("recolour_region", src, dst, n)


def drop_big_islands(obj, min_tris):
    if not min_tris:
        return 0
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    kill = []
    for group in island_faces(bm):
        if sum(len(f.verts) - 2 for f in group) >= min_tris:
            kill.extend(group)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return len(kill)


def place(obj, cfg, origin):
    s, yaw = cfg["scale"], math.radians(cfg["yaw"])
    m = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Scale(s, 4) @ Matrix.Translation(-Vector(origin))
    obj.data.transform(m)


def cleanup(obj, merge=0.0008):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    # Duplicate faces (same vertex set) and degenerate faces.
    seen, dupes = {}, []
    for f in bm.faces:
        key = tuple(sorted(v.index for v in f.verts))
        if key in seen or f.calc_area() < 1e-7:
            dupes.append(f)
        else:
            seen[key] = f
    bmesh.ops.delete(bm, geom=dupes, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    # Underground faces (basement walls below grade) are never seen.
    under = [f for f in bm.faces if max(v.co.z for v in f.verts) < -0.02]
    bmesh.ops.delete(bm, geom=under, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()


def fib_dirs(n):
    out = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        out.append(Vector((math.cos(g * i) * r, math.sin(g * i) * r, z)))
    return out


DIRS = fib_dirs(64)


def visibility_pass(obj):
    """Ray-visibility from outside: delete hidden faces, flip faces seen only from behind,
    double faces that are seen from both sides. Windows count as opaque (the game's window
    shader is opaque) and the ground plane blocks rays inside the footprint."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    lo = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts))) - Vector((1, 1, 1))
    hi = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts))) + Vector((1, 1, 1))

    def exit_t(p, d):
        t = 1e9
        for k in range(3):
            if abs(d[k]) > 1e-9:
                t = min(t, ((hi[k] if d[k] > 0 else lo[k]) - p[k]) / d[k])
        return t

    def seen(face, n):
        pts = [face.calc_center_median()]
        if face.calc_area() > 0.03:
            pts += [pts[0].lerp(v.co, 0.7) for v in face.verts]
        for p0 in pts:
            if p0.z < -0.01:
                continue
            p = p0 + n * 0.002
            for d in DIRS:
                if d.dot(n) < 0.08:
                    continue
                t = exit_t(p, d)
                if d.z < 0 and p.z > 0:
                    tg = -p.z / d.z
                    if tg < t:
                        continue        # reaches the ground under/around the house first
                if bvh.ray_cast(p, d, t)[0] is None:
                    return True
        return False

    kill, flip, double = [], [], []
    for f in bm.faces:
        n = f.normal.copy()
        if n.length < 0.5:
            kill.append(f)
            continue
        front = seen(f, n)
        back = seen(f, -n)
        if front and back:
            double.append(f)
        elif back:
            flip.append(f)
        elif not front:
            kill.append(f)
    # A face of a flat surface whose coplanar neighbour (same material) is visible is visible too:
    # the ray samples miss small triangles in corners (under the porch roof, beside columns), and
    # deleting them punched triangular holes into the ends of the siding courses (the saw-tooth).
    killed = set(kill)
    keep_n = {f: f.normal.copy() for f in bm.faces}
    stack = [f for f in bm.faces if f not in killed]
    while stack:
        f = stack.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g in killed and g.material_index == f.material_index and keep_n[g].length > 0.5 \
                        and keep_n[g].dot(keep_n[f]) > 0.9995 and g.calc_area() < 0.06:
                    killed.discard(g)
                    stack.append(g)
    kill = [f for f in kill if f in killed]
    for f in flip:
        f.normal_flip()
    # Doubled faces get their own (reversed) copy of the vertices so they never share winding.
    created = 0
    for f in double:
        verts = [bm.verts.new(v.co) for v in reversed(f.verts)]
        try:
            nf = bm.faces.new(verts)
            nf.material_index = f.material_index
            nf.smooth = f.smooth
            created += 1
        except ValueError:
            pass
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    return {"deleted": len(kill), "flipped": len(flip), "doubled": created}


def dissolve(obj, angle=0.6):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle), use_dissolve_boundaries=False,
                             verts=bm.verts, edges=bm.edges, delimit={"MATERIAL", "NORMAL"})
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def select_only(obj):
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        if o is not None:
            o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def decimate(obj, budget):
    t = tri_count(obj)
    if t <= budget:
        return t
    select_only(obj)
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = budget / t
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return tri_count(obj)


def drop_small_islands(obj, diag):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    kill = []
    for group in island_faces(bm):
        pts = [v.co for f in group for v in f.verts]
        lo = Vector(map(min, *pts)) if len(pts) > 1 else pts[0]
        hi = Vector(map(max, *pts)) if len(pts) > 1 else pts[0]
        if (hi - lo).length < diag:
            kill.extend(group)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()


def fix_coplanar(obj, tol=0.004, push=0.006):
    """Same test as tests/zfighting_test.gd: same-facing, coplanar (within 4 mm), overlapping
    triangles. Same material: drop the smaller one. Different materials: push the higher-rank
    one 6 mm out along its normal (split off so its neighbours don't move)."""
    mats = [m.name for m in obj.data.materials]
    total = {"dropped": 0, "pushed": 0}
    for it in range(3):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        info, buckets = [], {}
        for f in bm.faces:
            n = f.normal
            a = f.calc_area()
            if a < 0.0005 or n.z < -0.7:
                info.append(None)
                continue
            c = f.calc_center_median()
            d = n.dot(f.verts[0].co)
            key = (round(n.x * 20), round(n.y * 20), round(n.z * 20), math.floor(d / tol))
            info.append((n.copy(), c, a))
            buckets.setdefault(key, []).append(f.index)

        def inside(p, f):
            a, b, c = (v.co for v in f.verts[:3])
            v0, v1, v2 = c - a, b - a, p - a
            d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
            den = d00 * d11 - d01 * d01
            if abs(den) < 1e-12:
                return False
            u = (d11 * d20 - d01 * d21) / den
            v = (d00 * d21 - d01 * d20) / den
            return u > 0.02 and v > 0.02 and u + v < 0.98

        drop, push_set = set(), set()
        for key, ids in buckets.items():
            cand = []
            for dq in (-1, 0, 1):
                cand += buckets.get((key[0], key[1], key[2], key[3] + dq), [])
            if len(cand) < 2:
                continue
            for i in ids:
                fi = bm.faces[i]
                ni, ci, ai = info[i]
                samples = [ci] + [ci.lerp(v.co, 0.4) for v in fi.verts]
                for j in cand:
                    if j == i or j in drop or i in drop:
                        continue
                    nj, cj, aj = info[j]
                    if nj.dot(ni) < 0.995 or abs(ni.dot(cj - ci)) >= tol:
                        continue
                    fj = bm.faces[j]
                    if not any(inside(p, fj) for p in samples):
                        continue
                    mi, mj = mats[fi.material_index], mats[fj.material_index]
                    if mi == mj:
                        drop.add(i if ai <= aj else j)
                    elif {mi, mj} == {"KitGlass", "KitDoorPaint"}:
                        push_set.add(i if mi == "KitGlass" else j)   # door lights sit on the leaf
                    else:
                        push_set.add(i if RANK.get(mi, 2) >= RANK.get(mj, 2) else j)
        push_set -= drop
        if not drop and not push_set:
            bm.free()
            break
        faces = [bm.faces[i] for i in push_set]
        normals = [f.normal.copy() for f in faces]
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context="FACES_ONLY")
        if faces:
            res = bmesh.ops.split(bm, geom=faces, use_only_faces=True)
            new_faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
            # split keeps order: match by centre
            for f in new_faces:
                n = f.normal
                for v in f.verts:
                    v.co += n * push
        total["dropped"] += len(drop)
        total["pushed"] += len(push_set)
        bm.to_mesh(obj.data)
        bm.free()
    return total


# ------------------------------------------------------------------ conflict fixes (no z-fighting)
# Tolerances shared with tests/house_conflict_test.gd: faces of different parts closer than TOL
# (1.5 cm, within a few degrees) that overlap count as a conflict. Detail layers are lifted to
# LAYER_GAP in front of what they cover by extruding them (with real side faces, no floating
# decals); flat floors at the lawn level are raised; boards half sunk into a wall are cut at its
# face; open siding corners get corner boards.
DEBUG_LAYERS = False
TOL = 0.015
LAYER_GAP = 0.018
NUDGE = 0.006          # one paint, one plane: the smaller piece moves this far in front
FIGHT = 0.004
BODY = {"KitSidingPaint", "KitLapSiding", "KitBrickRed", "KitPlinthDark"}
# Layer order where coplanar faces overlap: higher ranks are lifted in front of lower ones.
LAYER = {"KitSidingPaint": 1, "KitLapSiding": 1, "KitBrickRed": 1, "KitConcrete": 1, "KitPlinthDark": 1,
         "KitAsphaltShingles": 1, "KitDeckBoards": 1, "KitGlass": 2, "KitTrimPaint": 3, "KitRailBlack": 4,
         "KitFrameDark": 4, "KitDoorWood": 4, "KitDoorPaint": 4, "KitLampGlow": 5}


def tri_inside(p, a, b, c, margin=0.02):
    v0, v1, v2 = c - a, b - a, p - a
    d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-14:
        return False
    u = (d11 * d20 - d01 * d21) / den
    v = (d00 * d21 - d01 * d20) / den
    return u > margin and v > margin and u + v < 1 - margin


def face_samples(f, n=6):
    """Barycentric grid over the (triangulated) face: long thin triangles are covered too."""
    vs = [v.co for v in f.verts]
    pts = []
    for k in range(1, len(vs) - 1):
        a, b, c = vs[0], vs[k], vs[k + 1]
        for i in range(n):
            for j in range(n - i):
                u, v = (i + 0.33) / n, (j + 0.33) / n
                if u + v < 0.999:
                    pts.append(a + (b - a) * u + (c - a) * v)
    return pts


def clip_convex_2d(subject, clip):
    """Sutherland-Hodgman: convex polygon `subject` clipped by convex counter-clockwise `clip`."""
    out = subject
    n = len(clip)
    for k in range(n):
        a, b = clip[k], clip[(k + 1) % n]
        if not out:
            break
        inp, out = out, []
        def inside(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12
        for i in range(len(inp)):
            p, q = inp[i], inp[(i + 1) % len(inp)]
            ip, iq = inside(p), inside(q)
            if ip:
                out.append(p)
            if ip != iq:
                dx, dy = q[0] - p[0], q[1] - p[1]
                ex, ey = b[0] - a[0], b[1] - a[1]
                den = dx * ey - dy * ex
                if abs(den) > 1e-15:
                    t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
                    out.append((p[0] + dx * t, p[1] + dy * t))
    return out


def poly_area_2d(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))


def overlapping_pairs(bm, mats, tol=TOL, same_material=False, min_area=2e-6, cos_max=0.98):
    """Same-facing faces of different materials (or of one material, `same_material`) within
    ~10 degrees whose projections overlap (exact convex clipping) and lie closer than tol there:
    [(i, j, signed distance of j in front of i along i's normal)]."""
    bm.faces.ensure_lookup_table()
    info = []
    cells = {}
    cs = 0.5
    for f in bm.faces:
        n = f.normal
        if n.length < 0.5 or f.calc_area() < 1e-6:
            info.append(None)
            continue
        vs = [v.co.copy() for v in f.verts]
        info.append((n.copy(), vs))
        lo = [min(v[k] for v in vs) - tol for k in range(3)]
        hi = [max(v[k] for v in vs) + tol for k in range(3)]
        nk = (round(n.x * 6), round(n.y * 6), round(n.z * 6))
        c0 = [math.floor(lo[k] / cs) for k in range(3)]
        c1 = [math.floor(hi[k] / cs) for k in range(3)]
        for x in range(c0[0], c1[0] + 1):
            for y in range(c0[1], c1[1] + 1):
                for z in range(c0[2], c1[2] + 1):
                    cells.setdefault((x, y, z, nk), []).append(f.index)
    seen = set()
    out = []
    for key, ids in cells.items():
        x, y, z, nk = key
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    other = cells.get((x, y, z, (nk[0] + dx, nk[1] + dy, nk[2] + dz)))
                    if other:
                        cand += other
        for i in ids:
            ni, vi = info[i]
            mi = bm.faces[i].material_index
            # orthonormal basis of i's plane
            ref = Vector((1, 0, 0)) if abs(ni.x) < 0.9 else Vector((0, 1, 0))
            u = ni.cross(ref).normalized()
            w = ni.cross(u)
            o = vi[0]
            pi = [((v - o).dot(u), (v - o).dot(w)) for v in vi]
            if poly_area_2d(pi) < 0:
                pi = list(reversed(pi))
            for j in cand:
                if j == i:
                    continue
                pk = (i, j) if i < j else (j, i)
                if pk in seen:
                    continue
                nj, vj = info[j]
                if ni.dot(nj) < cos_max:
                    continue
                if (bm.faces[j].material_index == mi) != same_material:
                    continue
                seen.add(pk)
                # quick reject: all of j's vertices beyond tol on one side of i's plane
                ds = [ni.dot(v - o) for v in vj]
                if min(ds) > tol or max(ds) < -tol:
                    continue
                pj = [((v - o).dot(u), (v - o).dot(w)) for v in vj]
                if poly_area_2d(pj) < 0:
                    pj = list(reversed(pj))
                poly = clip_convex_2d(pj, pi)
                if len(poly) < 3 or abs(poly_area_2d(poly)) < min_area:
                    continue
                # separation of j's plane above i's plane at the overlap's corners
                den = nj.dot(ni)
                seps = []
                for (a, b) in poly:
                    q = o + u * a + w * b
                    seps.append(nj.dot(vj[0] - q) / den)
                if min(abs(t) for t in seps) >= tol:
                    continue
                out.append((i, j, sum(seps) / len(seps), abs(poly_area_2d(poly))))
    return out


def extrude_regions(bm, amounts):
    """amounts: {face index: distance}. Connected faces of one material with about the same
    amount are extruded together along their normal (side faces made, the old cap removed)."""
    bm.faces.ensure_lookup_table()
    todo = {bm.faces[i]: a for i, a in amounts.items()}
    done = set()
    moved = 0
    for f0, a0 in list(todo.items()):
        if f0 in done:
            continue
        region, stack = [], [f0]
        done.add(f0)
        while stack:
            f = stack.pop()
            region.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g in todo and g not in done and g.material_index == f0.material_index and \
                            abs(todo[g] - a0) < 0.003 and g.normal.dot(f0.normal) > 0.99:
                        done.add(g)
                        stack.append(g)
        amount = max(todo[f] for f in region)
        n = Vector((0, 0, 0))
        for f in region:
            n += f.normal * f.calc_area()
        n.normalize()
        res = bmesh.ops.extrude_face_region(bm, geom=region)
        for v in [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]:
            v.co += n * amount
        bmesh.ops.delete(bm, geom=region, context="FACES_ONLY")
        moved += len(region)
    return moved


def flat_regions(bm):
    """Face -> region id: connected faces of one material lying in one plane (one board front,
    one wall panel, one muntin face)."""
    region = {}
    rid = 0
    for f0 in bm.faces:
        if f0 in region:
            continue
        n0 = f0.normal
        d0 = n0.dot(f0.verts[0].co)
        stack = [f0]
        region[f0] = rid
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in region or g.material_index != f0.material_index:
                        continue
                    if g.normal.dot(n0) < 0.9995 or abs(n0.dot(g.verts[0].co) - d0) > 0.001:
                        continue
                    region[g] = rid
                    stack.append(g)
        rid += 1
    return region


def extrude_region_list(bm, regions, sides=None):
    """regions: [(faces, distance)] -> each flat region extruded along its normal (side faces
    made - collected into `sides` - and the old cap removed)."""
    moved = 0
    for faces, amount in regions:
        faces = [f for f in faces if f.is_valid]
        if not faces:
            continue
        n = Vector((0, 0, 0))
        for f in faces:
            n += f.normal * f.calc_area()
        if n.length < 1e-9:
            continue
        n.normalize()
        res = bmesh.ops.extrude_face_region(bm, geom=faces)
        for v in [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]:
            v.co += n * amount
        if sides is not None:
            for g in res["geom"]:
                if isinstance(g, bmesh.types.BMFace):
                    g.normal_update()
                    if abs(g.normal.dot(n)) < 0.5:
                        sides.add(g)
        bmesh.ops.delete(bm, geom=faces, context="FACES_ONLY")
        moved += len(faces)
    return moved


def layer_fix(obj, passes=6):
    """Lift overlapping flat pieces LAYER_GAP in front of what they overlap: a detail (higher
    LAYER) in front of the surface it covers; of two layered pieces of one paint (crossing
    muntins, stacked boards) one is moved in front of the other. Whole flat pieces move (with real
    side faces), so boards never end up stepped. Exact duplicates are deleted."""
    mats = [m.name for m in obj.data.materials]
    total = {"lifted": 0, "dropped": 0, "passes": 0, "left": 0}
    start = max(1, len(obj.data.polygons))
    for it in range(passes):
        if len(obj.data.polygons) > 1.5 * start:
            total["stopped"] = "growth"            # never let the passes run away
            break
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        region = flat_regions(bm)
        gl = bm.faces.layers.int.get("gen")
        gen_regions = {r for f, r in region.items() if gl is not None and f[gl]}
        area = {}
        for f, r in region.items():
            area[r] = area.get(r, 0.0) + f.calc_area()
        need, state, drop, nudge = {}, {}, set(), {}
        pairs = [(i, j, d, a, False) for i, j, d, a in overlapping_pairs(bm, mats)] +                 [(i, j, d, a, True) for i, j, d, a in overlapping_pairs(bm, mats, same_material=True)]
        if DEBUG_LAYERS:
            import collections
            cc = collections.Counter((mats[bm.faces[i].material_index], mats[bm.faces[j].material_index], round(d, 3)) for i, j, d, a, sm in pairs)
            print("LAYERDBG pass", it, len(pairs), cc.most_common(8))
        for i, j, dist, ov, same in pairs:
            fi, fj = bm.faces[i], bm.faces[j]
            ri, rj = region[fi], region[fj]
            if ri == rj:
                continue
            if same:
                # One paint in two layers: the face behind is hidden where they overlap - delete
                # it when it is (nearly) all covered. Pieces of one paint in exactly one plane
                # (crossing muntins) shade identically and are left alone; a piece of it within
                # 1.5 cm in front of another is lifted to LAYER_GAP.
                back, front = (j, i) if dist < 0 else (i, j)
                if ov >= 0.9 * bm.faces[back].calc_area():
                    drop.add(back)
                    continue
                # Pieces of one paint in one plane (crossing muntins, a board laid over a frame)
                # share the depth buffer: the smaller piece is nudged NUDGE in front. Layers of
                # one paint already more than FIGHT apart are left alone (same shading; lifting
                # them cascades through stacked casings without end).
                if abs(dist) >= FIGHT or it > 0:
                    continue        # (nudged once, in the first pass: repeated nudges cascade)
                small, big = (ri, rj) if area[ri] <= area[rj] else (rj, ri)
                if state.get(small) == "fixed":
                    if state.get(big) == "fixed":
                        total["left"] += 1
                        continue
                    small, big = big, small
                if small in gen_regions:
                    continue
                state[small] = "moving"
                state.setdefault(big, "fixed")
                sep = -dist if small == ri else dist
                nudge.setdefault(small, max(0.0, NUDGE - sep))
                continue
            else:
                mi, mj = mats[fi.material_index], mats[fj.material_index]
                ki, kj = LAYER.get(mi, 3), LAYER.get(mj, 3)
                if {mi, mj} == {"KitGlass", "KitDoorPaint"}:
                    ki, kj = (5, 4) if mi == "KitGlass" else (4, 5)   # door lights sit on the leaf
                if ki == kj:
                    ki, kj = (ki + 1, kj) if area[ri] < area[rj] else (ki, kj + 1)
                mover, other = (ri, rj) if ki > kj else (rj, ri)
            if mover in gen_regions:
                # generated boards stay where they were built; a detail piece against one moves
                # instead, wall cladding is left (the board stands in front of it)
                if other in gen_regions or mats[bm.faces[i if other == ri else j].material_index] in BODY:
                    continue
                mover, other = other, mover
            sep = -dist if mover == ri else dist        # mover's distance in front of the other
            if state.get(mover) == "fixed" and same:
                total["left"] += 1
                continue
            state[mover] = "moving"
            state.setdefault(other, "fixed")
            if sep < LAYER_GAP - 1e-4:
                need[mover] = max(need.get(mover, 0.0), LAYER_GAP - sep)
        for r, a in nudge.items():
            if r not in need and a > 0:
                need[r] = a
        if not need and not drop:
            bm.free()
            break
        faces_of = {}
        for f, r in region.items():
            if r in need:
                faces_of.setdefault(r, []).append(f)
        dropped = [bm.faces[i] for i in drop]
        sides = set()
        total["lifted"] += extrude_region_list(bm, [(faces_of[r], a) for r, a in need.items() if r in faces_of], sides)
        bmesh.ops.delete(bm, geom=[f for f in dropped if f.is_valid], context="FACES_ONLY")
        # The new side faces of a lifted piece can land on another surface's plane (a casing's
        # inner edge on the window reveal): those are covered by that surface - delete them
        # instead of lifting again (which never converges).
        if sides:
            bm.faces.ensure_lookup_table()
            bm.normal_update()
            hit = set()
            for pr in overlapping_pairs(bm, mats) + overlapping_pairs(bm, mats, same_material=True):
                for k in (pr[0], pr[1]):
                    if bm.faces[k] in sides:
                        hit.add(bm.faces[k])
            bmesh.ops.delete(bm, geom=list(hit), context="FACES_ONLY")
            total["sides_removed"] = total.get("sides_removed", 0) + len(hit)
        total["dropped"] += len(drop)
        total["passes"] = it + 1
        bm.to_mesh(obj.data)
        bm.free()
    return total


def ground_fix(obj, lift_mats=("KitDeckBoards",), lift=0.04):
    """The lawn's top is y = 0: floors lying on it (porch, carport, deck at grade) are raised
    `lift` with real fascia sides; other upward slivers at the lawn level are removed."""
    mats = [m.name for m in obj.data.materials]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    raise_faces, kill = {}, []
    for f in bm.faces:
        if max(v.co.z for v in f.verts) < 0.003 and mats[f.material_index] not in lift_mats:
            kill.append(f)          # wholly at or below grade: under the lawn
            continue
        if f.normal.z >= 0.95 and mats[f.material_index] not in lift_mats and min(v.co.z for v in f.verts) < 0.016                 and max(v.co.z for v in f.verts) < 0.15:
            kill.append(f)          # an upward sliver dipping to the lawn level
            continue
        if f.normal.z < 0.95 or max(abs(v.co.z) for v in f.verts) > 0.02:
            continue
        if mats[f.material_index] in lift_mats:
            raise_faces[f.index] = lift
        else:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES_ONLY")
    bm.faces.ensure_lookup_table()
    raise_faces = {f.index: lift for f in bm.faces if f.normal.z >= 0.95 and max(abs(v.co.z) for v in f.verts) <= 0.02
                   and mats[f.material_index] in lift_mats}
    tops = [[v.co.copy() for v in f.verts] for f in bm.faces if f.index in raise_faces]
    n = extrude_regions(bm, raise_faces)
    # walls, posts and trims that started on the old floor level now end on the raised floor
    lifted = 0
    if tops:
        for v in bm.verts:
            if not (-0.005 < v.co.z < lift - 0.001):
                continue
            if all(mats[f.material_index] in lift_mats for f in v.link_faces):
                continue
            for t in tops:
                if any(tri_inside_2d(v.co, t[0], t[k], t[k + 1]) for k in range(1, len(t) - 1)):
                    v.co.z = lift
                    lifted += 1
                    break
    # slivers of walls / trims left at or under the raised floor are hidden by it
    buried = []
    if tops:
        for f in bm.faces:
            if mats[f.material_index] in lift_mats or max(v.co.z for v in f.verts) > lift + 0.002:
                continue
            c = f.calc_center_median()
            if any(tri_inside_2d(c, t[0], t[k], t[k + 1]) for t in tops for k in range(1, len(t) - 1)):
                buried.append(f)
        bmesh.ops.delete(bm, geom=buried, context="FACES_ONLY")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    return {"raised": n, "removed": len(kill) + len(buried), "lifted_verts": lifted if tops else 0}


def tri_inside_2d(p, a, b, c):
    def side(p1, p2, p3):
        return (p1.x - p3.x) * (p2.y - p3.y) - (p2.x - p3.x) * (p1.y - p3.y)
    d1, d2, d3 = side(p, a, b), side(p, b, c), side(p, c, a)
    neg = d1 < -1e-9 or d2 < -1e-9 or d3 < -1e-9
    pos = d1 > 1e-9 or d2 > 1e-9 or d3 > 1e-9
    return not (neg and pos)


def unsink(obj, detail=("KitTrimPaint", "KitDoorPaint", "KitRailBlack", "KitFrameDark", "KitDoorWood")):
    """Boards / shutters / frames that sit half inside a wall: the vertices behind the wall face
    (where a wall face is right in front of them) are moved onto that face, so the piece starts
    at the wall instead of crossing it."""
    mats = [m.name for m in obj.data.materials]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    wall = bmesh.new()
    wall.from_mesh(obj.data)
    kill = [f for f in wall.faces if mats[f.material_index] not in BODY]
    bmesh.ops.delete(wall, geom=kill, context="FACES_ONLY")
    wall.faces.ensure_lookup_table()
    wall.normal_update()
    if not wall.faces:
        wall.free(); bm.free()
        return 0
    bvh = BVHTree.FromBMesh(wall)
    moved = 0
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen or mats[f0.material_index] not in detail:
            continue
        island, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen and mats[g.material_index] in detail:
                        seen.add(g.index)
                        stack.append(g)
        verts = {v for f in island for v in f.verts}
        plan, lip = {}, {}
        front = behind = 0
        for v in verts:
            hit = bvh.find_nearest(v.co, 0.12)
            if hit[0] is None:
                continue
            p, n = hit[0], wall.faces[hit[2]].normal
            s = n.dot(v.co - p)
            on_face = (v.co - p).cross(n).length < 0.002
            if s > 0.005:
                front += 1
                if s < 0.05 and on_face:
                    lip[v] = p.copy()
            elif s < -0.005:
                behind += 1
                if on_face:
                    plan[v] = p.copy()
        if front and plan and front >= behind:
            for v, p in plan.items():
                v.co = p
                moved += 1
        elif behind > front and lip:
            for v, p in lip.items():      # mostly inside: the few cm poking through go back
                v.co = p
                moved += 1
    bm.to_mesh(obj.data)
    bm.free(); wall.free()
    return moved


def auto_corner_boards(obj, depth=0.035, width=0.11, inside=0.045, mat="KitTrimPaint"):
    """Corner boards over every vertical corner where two perpendicular, axis-aligned walls of
    lap siding meet: an L of two closed boards at outside corners (the board on one face also
    covers the end of the other), a square strip at inside corners. Covers the raw ends and the
    groove notches of the courses."""
    mats = [m.name for m in obj.data.materials]
    if mat not in mats:
        obj.data.materials.append(bpy.data.materials.get(mat) or bpy.data.materials.new(mat))
        mats.append(mat)
    mi = mats.index(mat)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    gen = bm.faces.layers.int.get("gen") or bm.faces.layers.int.new("gen")
    siding = {"KitSidingPaint", "KitLapSiding"}
    edges = []      # (axis of the wall normal 0=x/1=y, sign, plane offset, other coord, z0, z1, centre)
    for f in bm.faces:
        if mats[f.material_index] not in siding:
            continue
        n = f.normal
        ax = 0 if abs(n.x) > 0.995 else (1 if abs(n.y) > 0.995 else -1)
        if ax < 0:
            continue
        c = f.calc_center_median()
        for e in f.edges:
            a, b = e.verts[0].co, e.verts[1].co
            d = b - a
            if d.length < 0.05 or abs(d.z) / d.length < 0.995:
                continue
            other = [g for g in e.link_faces if g is not f]
            if other and all(mats[g.material_index] in siding and g.normal.dot(n) > 0.99 for g in other):
                continue        # inner edge of a wall
            far = max(abs(v.co[1 - ax] - a[1 - ax]) for v in f.verts)    # how far the wall runs on
            edges.append((ax, 1 if n[ax] > 0 else -1, a[ax], a[1 - ax], min(a.z, b.z), max(a.z, b.z), c, far))
    # corner lines: an x-facing wall edge and a y-facing wall edge at the same (x, y)
    lines = {}
    xs = [e for e in edges if e[0] == 0]
    ys = [e for e in edges if e[0] == 1]
    grid = {}
    for e in ys:
        grid.setdefault((round(e[3] / 0.05), round(e[2] / 0.05)), []).append(e)
    for ex in xs:
        xa, yb = ex[2], ex[3]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ey in grid.get((round(xa / 0.05) + dx, round(yb / 0.05) + dy), []):
                    if abs(ey[3] - xa) > 0.025 or abs(ey[2] - yb) > 0.025:
                        continue
                    z0, z1 = max(ex[4], ey[4]), min(ex[5], ey[5])
                    if z1 - z0 < 0.005:
                        continue
                    # wall A (normal sx along x at x = xa), wall B (normal sy along y at y = yb)
                    sx, sy = ex[1], ey[1]
                    cA, cB = ex[6], ey[6]
                    convex = (cB.x - xa) * sx < 0 and (cA.y - yb) * sy < 0
                    concave = (cB.x - xa) * sx > 0 and (cA.y - yb) * sy > 0
                    if not (convex or concave):
                        continue
                    key = (round(xa / 0.02), round(yb / 0.02), sx, sy, convex)
                    line = lines.setdefault(key, [xa, yb, sx, sy, convex, [], 0.0, 0.0])
                    line[5].append((z0, z1))
                    line[6], line[7] = max(line[6], ex[7]), max(line[7], ey[7])
    boards = 0
    # Courses of one wall that run on a few cm past the other wall's face ("boards poking past
    # the corner") are cut back to the corner line.
    pure = [v for v in bm.verts if v.link_faces and all(mats[f.material_index] in siding for f in v.link_faces)]
    trimmed = 0
    for key, (xa, yb, sx, sy, convex, spans, far_a, far_b) in lines.items():
        if not convex or far_a < 0.09 or far_b < 0.09:
            continue
        z0 = min(z for z, _ in spans) - 0.01
        z1 = max(z for _, z in spans) + 0.01
        for v in pure:
            if not (z0 <= v.co.z <= z1):
                continue
            if abs(v.co.y - yb) < 0.03 and 0 < (v.co.x - xa) * sx < 0.04:
                v.co.x = xa
                trimmed += 1
            elif abs(v.co.x - xa) < 0.03 and 0 < (v.co.y - yb) * sy < 0.04:
                v.co.y = yb
                trimmed += 1
    print("corner trim", trimmed)

    def box(x0, x1, y0, y1, z0, z1):
        """Closed box, faces wound outward (counter-clockwise seen from outside)."""
        vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
        for q in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
            f = bm.faces.new([vs[k] for k in q])
            f.material_index = mi
            f[gen] = 1

    for key, (xa, yb, sx, sy, convex, spans, far_a, far_b) in lines.items():
        if far_a < 0.09 or far_b < 0.09:
            continue        # a reveal / jamb (both walls must run on from the corner)
        spans.sort()
        merged = []
        for z0, z1 in spans:
            if merged and z0 <= merged[-1][1] + 0.035:
                merged[-1][1] = max(merged[-1][1], z1)
            else:
                merged.append([z0, z1])
        for z0, z1 in merged:
            # stop 2.5 cm short of the courses' ends: plinth caps and eave trims sit there
            z0, z1 = z0 + 0.025, z1 - 0.01
            if z1 - z0 < 0.12:
                continue
            if convex:
                # board on wall A (x = xa): x from xa out by depth; y from the corner in by width,
                # out past the corner by depth (covering board B's end)
                ax0, ax1 = sorted((xa, xa + sx * depth))
                ay0, ay1 = sorted((yb - sy * width, yb + sy * depth))
                box(ax0, ax1, ay0, ay1, z0, z1)
                bx0, bx1 = sorted((xa - sx * width, xa))
                by0, by1 = sorted((yb, yb + sy * depth))
                box(bx0, bx1, by0, by1, z0, z1)
            else:
                cx0, cx1 = sorted((xa, xa + sx * inside))
                cy0, cy1 = sorted((yb, yb + sy * inside))
                box(cx0, cx1, cy0, cy1, z0, z1)
            boards += 1
    bm.to_mesh(obj.data)
    bm.free()
    return boards


SKIN = BODY | {"KitGlass", "KitDoorPaint", "KitDoorWood"}


def cross_depth(ta, tb, pierce=0.01):
    """How far two triangles cross each other (0 if they only touch): the smaller of the depths
    each one reaches on its less deep side of the other's plane, where they really intersect."""
    na = (ta[1] - ta[0]).cross(ta[2] - ta[0])
    nb = (tb[1] - tb[0]).cross(tb[2] - tb[0])
    if na.length < 1e-12 or nb.length < 1e-12:
        return 0.0
    na.normalize(); nb.normalize()
    da = [nb.dot(p - tb[0]) for p in ta]
    db = [na.dot(p - ta[0]) for p in tb]
    for d in (da, db):
        if max(d) < pierce or min(d) > -pierce:
            return 0.0
    line = na.cross(nb)
    if line.length < 1e-6:
        return 0.0
    line.normalize()

    def seg(t, d):
        ts = []
        for k in range(3):
            k2 = (k + 1) % 3
            if (d[k] > 0) != (d[k2] > 0):
                s = d[k] / (d[k] - d[k2])
                ts.append(line.dot(t[k].lerp(t[k2], s)))
        return (min(ts), max(ts)) if len(ts) >= 2 else (0, -1)
    sa, sb = seg(ta, da), seg(tb, db)
    if min(sa[1], sb[1]) - max(sa[0], sb[0]) < 0.02:
        return 0.0
    return min(min(max(da), -min(da)), min(max(db), -min(db)))


def final_purge(obj, max_island=0.6):
    """Last resort after the lifting passes: a detail piece (not wall cladding) that still lies
    within 1.5 cm on another material, or crosses a facade skin face by more than 1 cm, is
    removed - the whole flat piece if small, else that face."""
    mats = [m.name for m in obj.data.materials]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    kill = set()
    for i, j, dist, ov in overlapping_pairs(bm, mats):
        mi, mj = mats[bm.faces[i].material_index], mats[bm.faces[j].material_index]
        if mi in BODY and mj in BODY:
            continue
        ki, kj = LAYER.get(mi, 3), LAYER.get(mj, 3)
        kill.add(bm.faces[i] if (ki, -bm.faces[i].calc_area()) > (kj, -bm.faces[j].calc_area()) else bm.faces[j])
    # piercing: skin faces against faces of another material
    cells = {}
    cs = 0.5
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        lo = [math.floor(min(v[k] for v in vs) / cs) for k in range(3)]
        hi = [math.floor(max(v[k] for v in vs) / cs) for k in range(3)]
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    cells.setdefault((x, y, z), []).append(f)
    seen = set()
    box = {}
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        box[f] = ([min(v[k] for v in vs) for k in range(3)], [max(v[k] for v in vs) for k in range(3)])
    for fl in cells.values():
        skins = [a for a in fl if mats[a.material_index] in SKIN]
        if not skins:
            continue
        others = [b for b in fl if mats[b.material_index] != "KitAsphaltShingles"]
        for a in skins:
            ma = mats[a.material_index]
            la, ha = box[a]
            for b in others:
                mb = mats[b.material_index]
                if mb == ma:
                    continue
                lb, hb = box[b]
                if any(lb[k] > ha[k] or hb[k] < la[k] for k in range(3)):
                    continue
                key = (a.index, b.index) if a.index < b.index else (b.index, a.index)
                if key in seen:
                    continue
                seen.add(key)
                if abs(a.normal.dot(b.normal)) > 0.985:
                    continue
                if cross_depth([v.co for v in a.verts], [v.co for v in b.verts]) > 0.01:
                    if mb in BODY and ma not in BODY:
                        kill.add(a)
                    elif ma in BODY and mb not in BODY:
                        kill.add(b)
                    else:
                        kill.add(a if a.calc_area() < b.calc_area() else b)
    # grow small pieces to their whole island (same material, connected)
    out = set()
    for f in kill:
        if f in out:
            continue
        isl, stack = [], [f]
        seenf = {f}
        while stack and len(isl) < 400:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seenf and h.material_index == f.material_index:
                        seenf.add(h)
                        stack.append(h)
        if mats[f.material_index] not in BODY and not stack and sum(g.calc_area() for g in isl) < max_island:
            out.update(isl)
        else:
            out.add(f)
    gen = bm.faces.layers.int.get("gen")
    if gen is not None:
        out = {f for f in out if not f[gen]}
    bmesh.ops.delete(bm, geom=list(out), context="FACES_ONLY")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    return len(out)


def extra_boards(obj, boxes, mat="KitTrimPaint"):
    """Closed trim boxes (Godot local lo/hi corners), tagged as generated boards."""
    if not boxes:
        return 0
    mats = [m.name for m in obj.data.materials]
    mi = mats.index(mat)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    gen = bm.faces.layers.int.get("gen") or bm.faces.layers.int.new("gen")
    for lo, hi, skip in boxes:
        before = set(bm.faces)
        add_box(bm, mi, lo, hi, skip=skip)
        for f in bm.faces:
            if f not in before:
                f[gen] = 1
    bm.to_mesh(obj.data)
    bm.free()
    return len(boxes)


def same_paint_push(obj, push=0.007, passes=2):
    """Last pass for pieces of one paint that still overlap in one plane (< FIGHT): the smaller
    face is split off and set `push` in front (small faces only), or deleted when the other face
    covers it. Same colour either way; only the shared depth goes."""
    mats = [m.name for m in obj.data.materials]
    total = 0
    for it in range(passes):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        move, kill = {}, set()
        for i, j, dist, ov in overlapping_pairs(bm, mats, tol=FIGHT, same_material=True):
            fi, fj = bm.faces[i], bm.faces[j]
            small = fi if fi.calc_area() <= fj.calc_area() else fj
            if small in move or small in kill:
                continue
            other = fj if small is fi else fi
            if other in move:
                continue
            if ov >= 0.9 * small.calc_area():
                kill.add(small)
            elif small.calc_area() < 0.05:
                sep = -dist if small is fi else dist        # small's height above the other
                move[small] = max(0.0, push - sep)
        if not move and not kill:
            bm.free()
            break
        bmesh.ops.delete(bm, geom=list(kill), context="FACES_ONLY")
        faces = [f for f in move if f.is_valid]
        for f in faces:
            res = bmesh.ops.split(bm, geom=[f], use_only_faces=True)
            for g in [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]:
                n = g.normal.copy()
                for v in g.verts:
                    v.co += n * move[f]
        total += len(kill) + len(faces)
        bm.to_mesh(obj.data)
        bm.free()
    return total


def end_boards(obj, mat="KitTrimPaint"):
    """Trim boards over the raw end grain of modelled siding courses that end without a corner
    (wall steps, ends under the eaves): thin vertical siding faces whose normal runs along the
    wall, with nothing of another material in front of them."""
    mats = [m.name for m in obj.data.materials]
    if "KitSidingPaint" not in mats:
        return 0
    if mat not in mats:
        obj.data.materials.append(bpy.data.materials.get(mat) or bpy.data.materials.new(mat))
        mats.append(mat)
    mi = mats.index(mat)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    gen = bm.faces.layers.int.get("gen") or bm.faces.layers.int.new("gen")
    bvh = BVHTree.FromBMesh(bm)
    bm.faces.ensure_lookup_table()
    groups = {}
    for f in bm.faces:
        if mats[f.material_index] != "KitSidingPaint":
            continue
        n = f.normal
        ax = 0 if abs(n.x) > 0.99 else (1 if abs(n.y) > 0.99 else -1)
        if ax < 0:
            continue
        vs = [v.co for v in f.verts]
        thin = 1 - ax
        lo_t, hi_t = min(v[thin] for v in vs), max(v[thin] for v in vs)
        if hi_t - lo_t > 0.05:
            continue
        c = f.calc_center_median()
        covered = True
        for p in face_samples(f, 8) + [c] + [v.co.lerp(c, 0.1) for v in f.verts]:
            hit = bvh.ray_cast(p + n * 0.001, n, 0.2)
            if hit[0] is None or mats[bm.faces[hit[2]].material_index] in BODY:
                covered = False
                break
        if covered:
            continue
        # which way the wall faces (its boards' front faces next to this end): the board goes
        # on that side only, never into the wall
        side = 0
        for e in f.edges:
            for g2 in e.link_faces:
                if g2 is not f and abs(g2.normal[thin]) > 0.9:
                    side = 1 if g2.normal[thin] > 0 else -1
        if side == 0:
            continue
        key = (ax, 1 if n[ax] > 0 else -1, round(c[ax] / 0.01), round((lo_t + hi_t) / 2 / 0.03), side)
        g = groups.setdefault(key, [c[ax], lo_t, hi_t, [], n.copy()])
        g[1], g[2] = min(g[1], lo_t), max(g[2], hi_t)
        g[3].append((min(v.z for v in vs), max(v.z for v in vs)))
    made = 0
    for (ax, sgn, _, _, side), (plane, lo_t, hi_t, spans, n) in groups.items():
        spans.sort()
        merged = []
        for z0, z1 in spans:
            if merged and z0 <= merged[-1][1] + 0.04:
                merged[-1][1] = max(merged[-1][1], z1)
            else:
                merged.append([z0, z1])
        thin = 1 - ax
        for z0, z1 in merged:
            z0, z1 = z0 + 0.025, z1 - 0.01          # clear of plinth caps / eave trims
            if z1 - z0 < 0.03:
                continue
            lo = [0, 0, z0]
            hi = [0, 0, z1]
            lo[ax], hi[ax] = sorted((plane, plane + sgn * 0.025))
            lo[thin], hi[thin] = (lo_t - 0.002, hi_t + 0.035) if side > 0 else (lo_t - 0.035, hi_t + 0.002)
            vs = [bm.verts.new((x, y, z)) for z in (lo[2], hi[2]) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])]
            for q in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
                fn = bm.faces.new([vs[k] for k in q])
                fn.material_index = mi
                fn[gen] = 1
            made += 1
    bm.to_mesh(obj.data)
    bm.free()
    return made


def smooth_by_angle(obj, deg=32.0):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for f in bm.faces:
        f.smooth = True
    lim = math.radians(deg)
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(1.0) > lim:
            e.smooth = False
        elif e.link_faces[0].material_index != e.link_faces[1].material_index:
            e.smooth = False
    bm.to_mesh(obj.data)
    bm.free()


def bake_ao(obj):
    scene = bpy.context.scene
    try:
        scene.render.engine = "CYCLES"
    except TypeError as err:
        print("engine:", err)
    scene.cycles.samples = 48
    scene.cycles.device = "CPU"
    me = obj.data
    if "AO" not in me.color_attributes:
        me.color_attributes.new("AO", "FLOAT_COLOR", "CORNER")
    me.color_attributes.active_color = me.color_attributes["AO"]
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.light_settings.distance = 0.8
    for m in me.materials:
        m.use_nodes = True
    # Ground plane so walls darken towards the grade, like the kit houses.
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.005))
    ground = bpy.context.active_object
    select_only(obj)
    try:
        bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    finally:
        bpy.data.objects.remove(ground, do_unlink=True)
    # Keep AO subtle on the large flat walls (0.35 floor), as the kit does.
    attr = me.color_attributes["AO"]
    data = np.empty(len(attr.data) * 4, dtype=np.float32)
    attr.data.foreach_get("color", data)
    data = data.reshape(-1, 4)
    data[:, :3] = 0.35 + 0.65 * data[:, :3]
    data[:, 3] = 1.0
    attr.data.foreach_set("color", data.ravel())


def split_by_material(obj):
    select_only(obj)
    if len(obj.data.materials) > 1:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
    parts = list(bpy.context.selected_objects)
    for p in parts:
        used = {poly.material_index for poly in p.data.polygons}
        mat = p.data.materials[used.pop()] if used else p.data.materials[0]
        p.data.materials.clear()
        p.data.materials.append(mat)
        p.name = mat.name
        p.data.name = mat.name
    return [p for p in parts if len(p.data.polygons)]


def export(parts, path, extras):
    root = bpy.data.objects.new("HouseRoot", None)
    bpy.context.scene.collection.objects.link(root)
    for k, v in extras.items():
        root[k] = v
    for p in parts:
        p.parent = root
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        if o is not None:
            o.select_set(False)
    root.select_set(True)
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = root
    kwargs = dict(filepath=path, use_selection=True, export_format="GLB", export_yup=True, export_apply=True,
                  export_normals=True, export_texcoords=False, export_extras=True)
    try:
        bpy.ops.export_scene.gltf(**kwargs, export_vertex_color="ACTIVE")
    except TypeError:
        bpy.ops.export_scene.gltf(**kwargs, export_colors=True)
    for p in parts:
        p.parent = None
    bpy.data.objects.remove(root, do_unlink=True)


def bounds(obj):
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return Vector(co.min(0)), Vector(co.max(0))


# ------------------------------------------------------------------ probes
def probe(obj):
    """Material hits along the front facade (Godot local coordinates) for setting door data."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    mats = [m.name for m in obj.data.materials]
    lo, hi = bounds(obj)
    print("PROBE bounds (blender)", tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi))

    def hit(p, d):
        r = bvh.ray_cast(Vector(p), Vector(d))
        if r[0] is None:
            return "-"
        return "%s@%.2f" % (mats[bm.faces[r[2]].material_index][3:9], (r[0] - Vector(p)).length)
    for gy in (0.3, 0.7, 1.0, 1.5, 2.2):
        row = []
        x = lo.x
        while x < hi.x:
            row.append("%.1f:%s" % (x, hit((x, lo.y - 2, gy), (0, 1, 0))))
            x += 0.5
        print("PROBE front y=%.1f" % gy, " ".join(row))
    bm.free()


def heightmap(obj, step=0.5):
    """Top-down map of the highest surface (Godot local x across, z down the page from the front)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    lo, hi = bounds(obj)
    xs = [lo.x + step * (i + 0.5) for i in range(int((hi.x - lo.x) / step) + 1)]
    print("HMAP x:", " ".join("%5.1f" % x for x in xs[::2]))
    y = lo.y + step / 2
    while y < hi.y:
        row = []
        for x in xs:
            r = bvh.ray_cast(Vector((x, y, 30)), Vector((0, 0, -1)))
            row.append("%d" % min(9, round(r[0].z)) if r[0] is not None and r[0].z > 0.25 else ".")
        print("HMAP z=%6.2f %s" % (-y, "".join(row)))
        y += step
    bm.free()


def probe_x(obj, x0, x1, step, heights, zfront):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    mats = [m.name for m in obj.data.materials]
    for gy in heights:
        row = []
        x = x0
        while x <= x1 + 1e-6:
            r = bvh.ray_cast(Vector((x, -zfront - 3, gy)), Vector((0, 1, 0)))
            row.append("%.2f:%s" % (x, "-" if r[0] is None else "%s@z%.2f" % (mats[bm.faces[r[2]].material_index][3:8], -r[0].y)))
            x += step
        print("PROBEX y=%.2f" % gy, " ".join(row))
    # floor heights in front of the facade (downward rays), Godot z = 0.5 .. 4
    for gz in [i * 0.25 for i in range(-12, 9)]:
        row = []
        x = x0
        while x <= x1 + 1e-6:
            r = bvh.ray_cast(Vector((x, -gz, 2.0)), Vector((0, 0, -1)))
            row.append("%.2f" % (r[0].z if r[0] is not None else -9))
            x += step
        print("PROBEFLOOR z=%.2f" % gz, " ".join(row))
    bm.free()


# ------------------------------------------------------------------ main
def prepare(name, cfg):
    obj = load_joined(os.path.join(SRC, cfg["src"]))
    stats = {"source_tris": tri_count(obj)}
    stats["figures_removed_faces"] = drop_big_islands(obj, cfg["drop_island_tris"])
    remap_materials(obj, cfg["materials"], cfg["drop_materials"])
    place(obj, cfg, cfg["origin"])
    cleanup(obj)
    for mat, lo, hi in cfg.get("drop_regions", []):
        drop_region(obj, mat, lo, hi)
    for src, dst, lo, hi in cfg.get("recolour_regions", []):
        recolour_region(obj, src, dst, lo, hi)
    if PROBE:
        probe(obj)
        heightmap(obj)
        if name in PROBE_X:
            probe_x(obj, *PROBE_X[name])
        return None
    stats["after_cleanup_tris"] = tri_count(obj)
    stats["visibility"] = visibility_pass(obj)
    cleanup(obj)
    stats["after_visibility_tris"] = tri_count(obj)
    dissolve(obj)
    stats["after_dissolve_tris"] = tri_count(obj)
    extra = EXTRA.get(name)
    if extra:
        extra(obj)
    stats["near_tris"] = decimate(obj, cfg["budget"])
    # Conflict fixes (tests/house_conflict_test.gd): floors off the lawn, boards out of the walls,
    # detail layers lifted in front of what they cover, corner boards on the siding corners.
    stats["ground"] = ground_fix(obj, cfg.get("lift_floor", ()))
    stats["unsink"] = unsink(obj)
    stats["layers"] = layer_fix(obj)
    stats["purged_early"] = final_purge(obj)
    stats["corner_boards"] = auto_corner_boards(obj)
    stats["end_boards"] = end_boards(obj) + extra_boards(obj, cfg.get("extra_boards", ()))
    stats["layers_after_boards"] = layer_fix(obj)
    stats["ground_final"] = ground_fix(obj, ())
    stats["purged"] = final_purge(obj)
    stats["same_paint"] = same_paint_push(obj)
    stats["near_tris"] = tri_count(obj)
    smooth_by_angle(obj)
    if BAKE:
        bake_ao(obj)
    lo, hi = bounds(obj)
    meta = dict(METADATA[name])
    meta.update({"bounds_min": [round(lo.x, 3), round(lo.z, 3), round(-hi.y, 3)],
                 "bounds_max": [round(hi.x, 3), round(hi.z, 3), round(-lo.y, 3)]})
    extras = {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in meta.items()}
    far = obj.copy()
    far.data = obj.data.copy()
    near_parts = split_by_material(obj)
    stats["near_materials"] = sorted(p.name for p in near_parts)
    export(near_parts, os.path.join(OUT, name + ".glb"), extras)
    for p in near_parts:
        p.name = "near_" + p.name
    # Far LOD (45-110 m): no small hardware, collapsed to ~1/3, same materials and AO.
    bpy.context.scene.collection.objects.link(far)
    drop_small_islands(far, 0.35)
    # Planar simplification only (no collapse): vertices stay where the near LOD has them, so the
    # lifted layers, corner boards and raised floors keep their separations.
    bm = bmesh.new()
    bm.from_mesh(far.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(4.0), use_dissolve_boundaries=False,
                             verts=bm.verts, edges=bm.edges, delimit={"MATERIAL"})
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(far.data)
    bm.free()
    stats["far_tris"] = tri_count(far)
    # Fix anything the simplification brought within the tolerances again.
    stats["far_ground"] = ground_fix(far, cfg.get("lift_floor", ()))
    stats["far_layers"] = layer_fix(far)
    stats["far_purged"] = final_purge(far)
    stats["far_same_paint"] = same_paint_push(far)
    stats["far_tris"] = tri_count(far)
    far_parts = split_by_material(far)
    export(far_parts, os.path.join(OUT, name + "_far.glb"), extras)
    for p in far_parts:
        p.name = "far_" + p.name
    stats["size_m"] = [round(hi.x - lo.x, 2), round(hi.z - lo.z, 2), round(hi.y - lo.y, 2)]
    qa_render(name, near_parts, far_parts)
    return {"stats": stats, "meta": meta}


def duplex_steps(obj):
    """The SketchUp porch slab stops 0.51 m above grade with no steps: add a two-tread concrete
    stair in front of the ground-floor door (1.4 m wide, 0.17 m rises, 0.28 m treads)."""
    me = obj.data
    mi = [m.name for m in me.materials].index("KitConcrete")
    bm = bmesh.new()
    bm.from_mesh(me)
    x0, x1 = -1.45, -0.05
    for k, (top, z0, z1) in enumerate([(0.34, 0.0, 0.28), (0.17, 0.28, 0.56)]):
        lo = g2b(x0, 0.0, z1)
        hi = g2b(x1, top, z0 - (0.02 if k == 0 else 0.0))
        res = bmesh.ops.create_cube(bm, size=1.0)
        verts = res["verts"]
        c = (lo + hi) / 2
        sz = Vector((abs(hi.x - lo.x), abs(hi.y - lo.y), abs(hi.z - lo.z)))
        for v in verts:
            v.co = Vector((c.x + v.co.x * sz.x, c.y + v.co.y * sz.y, c.z + v.co.z * sz.z))
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = mi
        # bottom faces sit on the ground and are never seen
        bottom = [f for f in {f for v in verts for f in v.link_faces} if f.normal.z < -0.9]
        bmesh.ops.delete(bm, geom=bottom, context="FACES_ONLY")
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


def add_quad(bm, mi, x0, x1, y0, y1, z):
    """Street-facing (+Z Godot) rectangle in Godot local coordinates."""
    vs = [bm.verts.new(g2b(x, y, z)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.y > 0:     # must face Blender -Y (Godot +Z)
        f.normal_flip()
    f.material_index = mi
    return f


def add_box(bm, mi, lo, hi, skip=(), inward=False):
    """Axis-aligned box in Godot local coordinates, faces wound outward (inward: a hole's reveals);
    skip: '+x', '-z', ..."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    sides = {"-x": [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
             "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], "+y": [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
             "-z": [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]}
    want = {"-x": (-1, 0, 0), "+x": (1, 0, 0), "-y": (0, -1, 0), "+y": (0, 1, 0), "-z": (0, 0, -1), "+z": (0, 0, 1)}
    for key, pts in sides.items():
        if key in skip:
            continue
        f = bm.faces.new([bm.verts.new(g2b(*q)) for q in pts])
        f.normal_update()
        w = g2b(*want[key])
        if (f.normal.dot(w) < 0) != inward:
            f.normal_flip()
        f.material_index = mi


def farmhouse_door(obj):
    """Solid leaf in the cleared storm-door opening: the glazed upper light is a real opening in
    the leaf (glass 2 cm behind its face, painted reveals), the lower panel stands 2 cm proud."""
    me = obj.data
    names = [m.name for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    door, glass = names.index("KitDoorPaint"), names.index("KitGlass")
    x0, x1, y0, y1, z = -1.45, -0.56, 0.52, 2.62, -1.80     # leaf, 3 cm behind the frame face
    gx0, gx1, gy0, gy1 = -1.31, -0.70, 1.52, 2.42
    for a, b, c, d in ((x0, x1, y0, gy0), (x0, x1, gy1, y1), (x0, gx0, gy0, gy1), (gx1, x1, gy0, gy1)):
        add_quad(bm, door, a, b, c, d, z)
    add_box(bm, door, (gx0, gy0, z - 0.02), (gx1, gy1, z), skip=("+z", "-z"), inward=True)
    add_quad(bm, glass, gx0, gx1, gy0, gy1, z - 0.02)
    add_box(bm, door, (-1.31, 0.70, z), (-0.70, 1.36, z + 0.02), skip=("-z",))     # raised panel
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


def snap_up(obj, lo, hi, y, keep=("KitDeckBoards",)):
    """Vertices (of faces not in `keep`) inside the Godot box lo..hi are lifted to height y: walls,
    door frames and posts standing on a porch deck end on its surface instead of passing it."""
    mats = [m.name for m in obj.data.materials]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    n = 0
    for v in bm.verts:
        gx, gy, gz = v.co.x, v.co.z, -v.co.y
        if not (lo[0] <= gx <= hi[0] and lo[1] <= gy <= hi[1] and lo[2] <= gz <= hi[2]):
            continue
        if any(mats[f.material_index] in keep for f in v.link_faces):
            continue
        v.co.z = y
        n += 1
    bm.to_mesh(obj.data)
    bm.free()
    return n


def farmhouse_extra(obj):
    farmhouse_door(obj)
    # Porch deck top at 0.517: the front walls, door frame and posts started 1.2 cm below it.
    print("snap_up", snap_up(obj, (-1.95, 0.48, -4.45), (5.25, 0.5165, 0.05), 0.518))


EXTRA = {"house_duplex": duplex_steps, "house_farmhouse": farmhouse_extra}
PROBE_X = {"house_farmhouse": (-2.5, 1.5, 0.25, (0.3, 0.8, 1.6, 2.4, 2.8), 0.0), "house_duplex": (-3.0, 1.0, 0.25, (0.3, 0.8, 1.6, 2.4, 2.7), 0.0), "house_suburban": (-5.6, -3.0, 0.1, (0.1, 0.4, 0.7, 1.2, 2.0, 2.2, 2.35, 2.45, 2.6), 0.5)}
# Godot local metres (x right, y up, z towards the street). door = (x, floor y, z of the door
# leaf); ramp = [x0, x1, top, z_top, z_bottom]; boxes/hull = [[centre], [size]] collision
# (hull replaces HouseInstancer's single body box); number = beside-door house number spot;
# massing = [eave, rise, ridge axis, width, depth] for the instancer's far wall+roof boxes.
METADATA = {
    "house_suburban": {
        "lot": 18.0, "w": 16.43, "d": 14.68, "h": 7.0, "door": [-3.43, 0.04, -3.08], "step_height": 0.04,
        "ramp": [], "boxes": [],
        "hull": [[[2.425, 2.75, -4.55], [10.75, 5.5, 8.1]], [[2.0, 2.75, -0.25], [4.5, 5.5, 0.5]],
                 [[-4.475, 2.6, -5.8], [3.05, 5.2, 5.6]], [[-1.0, 2.5, -9.3], [6.0, 5.0, 1.4]]],
        "number": [-5.05, 1.6, -2.95], "massing": [3.0, 4.0, "x", 15.0, 9.5],
    },
    "house_duplex": {
        "lot": 12.5, "w": 10.2, "d": 16.32, "h": 8.03, "door": [-0.75, 0.51, -1.89], "door2": [-0.75, 3.22, -1.89],
        "step_height": 0.17, "ramp": [-1.45, -0.05, 0.51, 0.0, 0.84],
        "boxes": [[[-2.35, 0.255, -0.95], [4.9, 0.51, 1.9]], [[2.45, 0.255, -15.05], [4.7, 0.51, 1.9]]],
        "hull": [[[0.0, 3.0, -8.0], [9.6, 6.0, 12.2]], [[2.45, 3.0, -0.95], [4.7, 6.0, 1.9]],
                 [[-2.35, 3.0, -15.05], [4.9, 6.0, 1.9]]],
        "number": [-1.62, 2.05, -1.85], "massing": [5.9, 2.13, "z", 9.6, 16.0],
    },
    "house_farmhouse": {
        "lot": 12.5, "w": 10.35, "d": 7.1, "h": 6.8, "door": [-1.0, 0.52, -1.78], "step_height": 0.14,
        "ramp": [-1.75, 0.5, 0.52, 0.0, 0.95],
        "boxes": [[[1.65, 0.26, -0.89], [6.9, 0.52, 1.78]]],
        "hull": [[[-3.4, 3.0, -3.45], [3.2, 6.0, 6.9]], [[1.6, 3.0, -4.34], [6.8, 6.0, 5.12]]],
        "number": [-1.0, 2.85, -1.72], "massing": [3.64, 3.16, "x", 10.35, 7.1],
    },
}


QA_COLOURS = {"KitSidingPaint": "6f7f8f", "KitLapSiding": "6f7f8f", "KitTrimPaint": "f2f0ea", "KitGlass": "2c3a40",
              "KitAsphaltShingles": "4a4036", "KitConcrete": "b9b6ae", "KitPlinthDark": "2a2c2e", "KitDeckBoards": "8a6d4f",
              "KitDoorPaint": "7a1f1f", "KitBrickRed": "8c4a3a", "KitRailBlack": "15181a", "KitDoorWood": "7a4a2a"}


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x < 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


def qa_render(name, near_parts, far_parts):
    """Seven views of the near LOD (+ far LOD three-quarter, door close-up, collision overlay)."""
    scene = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            pass
    scene.render.resolution_x, scene.render.resolution_y = 1000, 700
    for m in bpy.data.materials:
        m.use_nodes = True
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = srgb(QA_COLOURS.get(m.name, "808080"))
            bsdf.inputs["Roughness"].default_value = 0.2 if m.name == "KitGlass" else 0.7
            if m.name == "KitGlass":
                bsdf.inputs["Metallic"].default_value = 0.4
    world = bpy.data.worlds.get("QAWorld") or bpy.data.worlds.new("QAWorld")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.8, 1)
    bg.inputs[1].default_value = 0.8
    sun = bpy.data.objects.new("QASun", bpy.data.lights.new("QASun", "SUN"))
    scene.collection.objects.link(sun)
    sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(52), 0, math.radians(-35))
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 4, -0.003))
    ground = bpy.context.active_object
    gm = bpy.data.materials.new("QAGround")
    gm.use_nodes = True
    next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = srgb("5f7f4a")
    ground.data.materials.append(gm)
    meta = METADATA[name]
    marks = []
    door = meta.get("door")
    if door:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=g2b(door[0], door[1] + 1.0, door[2] + 0.12))
        dm = bpy.data.materials.new("QADoor")
        dm.use_nodes = True
        next(n for n in dm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (1, 0, 0.6, 1)
        bpy.context.active_object.data.materials.append(dm)
        marks.append(bpy.context.active_object)
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 32
    pts = []
    for p in near_parts:
        pts += [p.matrix_world @ Vector(c) for c in p.bound_box]
    lo = Vector(map(min, *pts))
    hi = Vector(map(max, *pts))
    c = (lo + hi) / 2
    r = (hi - lo).length * 0.5

    def shot(tag, direction, dist=2.3, target=None, lens=32):
        cam.data.lens = lens
        t = target or c
        d = Vector(direction).normalized()
        cam.location = t + d * r * dist
        cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(QA, "%s_%s.png" % (name, tag))
        bpy.ops.render.render(write_still=True)

    for p in far_parts:
        p.hide_render = True
    shot("front", (0, -1, 0.12))
    shot("back", (0, 1, 0.2))
    shot("left", (-1, 0, 0.15))
    shot("right", (1, 0, 0.15))
    shot("front_left", (-0.8, -1, 0.35))
    shot("rear_right", (0.8, 1, 0.45))
    shot("top", (0.0, -0.05, 1), 2.0)
    if door:
        tgt = g2b(door[0], door[1] + 1.1, door[2])
        cam.data.lens = 24
        cam.location = tgt + Vector((1.2, -5.5, 0.6))
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(QA, "%s_door.png" % name)
        bpy.ops.render.render(write_still=True)
    # Collision overlay: boxes as translucent red, ramp in blue.
    boxes = []
    for b in meta.get("hull", []) + meta.get("boxes", []):
        (cx, cy, cz), (sx, sy, sz) = b
        bpy.ops.mesh.primitive_cube_add(size=1, location=g2b(cx, cy, cz))
        o = bpy.context.active_object
        o.scale = (sx, sz, sy)
        o.display_type = "WIRE"
        boxes.append(o)
    cm = bpy.data.materials.new("QACol")
    cm.use_nodes = True
    bsdf = next(n for n in cm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (1, 0.1, 0.1, 1)
    bsdf.inputs["Alpha"].default_value = 0.35
    try:
        cm.surface_render_method = "BLENDED"
    except Exception:
        pass
    for o in boxes:
        o.data.materials.append(cm)
    if boxes:
        shot("collision", (-0.8, -1, 0.5))
    for o in boxes + marks:
        bpy.data.objects.remove(o, do_unlink=True)
    for p in near_parts:
        p.hide_render = True
    for p in far_parts:
        p.hide_render = False
    shot("far_lod", (-0.8, -1, 0.35))
    for p in far_parts:
        p.hide_render = True
    for p in near_parts:
        p.hide_render = False
    bpy.data.objects.remove(ground, do_unlink=True)
    bpy.data.objects.remove(sun, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)


if __name__ == "__main__":
    os.makedirs(QA, exist_ok=True)
    open(os.path.join(QA, ".gdignore"), "w").close()
    report_path = os.path.join(OUT, "houses.json")
    report = json.load(open(report_path)) if os.path.exists(report_path) else {}
    for name, cfg in HOUSES.items():
        if ONLY and name not in ONLY:
            continue
        result = prepare(name, cfg)
        if result:
            report[name] = result
            print("NEWHOUSE", name, json.dumps(result["stats"]))
    if not PROBE:
        # Merge with what other (parallel) runs wrote meanwhile.
        latest = json.load(open(report_path)) if os.path.exists(report_path) else {}
        latest.update({k: v for k, v in report.items() if not ONLY or k in ONLY})
        json.dump(latest, open(report_path, "w"), indent=1)
