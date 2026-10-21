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
    stats["coplanar"] = fix_coplanar(obj)
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
    stats["far_tris"] = decimate(far, int(stats["near_tris"] * cfg["far_ratio"]))
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


def farmhouse_door(obj):
    me = obj.data
    names = [m.name for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    door, glass = names.index("KitDoorPaint"), names.index("KitGlass")
    add_quad(bm, door, -1.45, -0.56, 0.52, 2.62, -1.80)            # leaf, 3 cm behind the frame face
    add_quad(bm, glass, -1.31, -0.70, 1.52, 2.42, -1.786)          # upper glazed light
    add_quad(bm, door, -1.31, -0.70, 0.70, 1.36, -1.786)           # raised lower panel
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


EXTRA = {"house_duplex": duplex_steps, "house_farmhouse": farmhouse_door}
PROBE_X = {"house_farmhouse": (-2.5, 1.5, 0.25, (0.3, 0.8, 1.6, 2.4, 2.8), 0.0), "house_duplex": (-3.0, 1.0, 0.25, (0.3, 0.8, 1.6, 2.4, 2.7), 0.0), "house_suburban": (-5.6, -3.0, 0.1, (0.1, 0.4, 0.7, 1.2, 2.0, 2.2, 2.35, 2.45, 2.6), 0.5)}
# Godot local metres (x right, y up, z towards the street). door = (x, floor y, z of the door
# leaf); ramp = [x0, x1, top, z_top, z_bottom]; boxes/hull = [[centre], [size]] collision
# (hull replaces HouseInstancer's single body box); number = beside-door house number spot;
# massing = [eave, rise, ridge axis, width, depth] for the instancer's far wall+roof boxes.
METADATA = {
    "house_suburban": {
        "lot": 18.0, "w": 16.43, "d": 14.68, "h": 7.0, "door": [-3.43, 0.0, -3.08], "step_height": 0.0,
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
