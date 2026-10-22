"""Find z-fighting in GLB assets: coplanar, same-facing faces from different parts/materials
(or duplicated faces) that overlap. Prints one line per asset and the worst offending pairs.

blender --background --factory-startup --python tools/find_zfighting.py -- <glb or dir> [...] [--json out.json]
"""
import bpy, sys, os, json
import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FIX = "--fix" in ARGS          # nudge the smaller surface of each fighting pair outward and re-export
ARGS = [a for a in ARGS if a != "--fix"]
# --opposite: coincident faces turned against each other (the bottom of a cushion on its frame,
# two sides of a thin panel) in different parts / materials. They fight wherever the material is
# double-sided (glTF doubleSided, the default for imported props); the smaller part is pushed
# along its own normal (into / behind the other) by the nudge.
OPPOSITE = "--opposite" in ARGS
ARGS = [a for a in ARGS if a != "--opposite"]
NUDGE = 0.005
if "--tol" in ARGS:
    i = ARGS.index("--tol"); PLANE_TOL = float(ARGS[i + 1]); ARGS = ARGS[:i] + ARGS[i + 2:]
if "--nudge" in ARGS:
    i = ARGS.index("--nudge"); NUDGE = float(ARGS[i + 1]); ARGS = ARGS[:i] + ARGS[i + 2:]
COS = None
if "--cos" in ARGS:   # cos of the largest angle between faces still counted as parallel
    i = ARGS.index("--cos"); COS = float(ARGS[i + 1]); ARGS = ARGS[:i] + ARGS[i + 2:]
OUT = None
if "--json" in ARGS:
    i = ARGS.index("--json"); OUT = ARGS[i + 1]; ARGS = ARGS[:i] + ARGS[i + 2:]
PLANE_TOL = globals().get("PLANE_TOL", 0.004)     # faces closer than this to the same plane fight in the depth buffer
NORMAL_TOL = COS if COS is not None else 0.995    # cos of the angle for "parallel"
MIN_AREA = 0.0005     # ignore slivers


def triangles():
    """World-space triangles: (N,3,3) vertices, owner ids, labels."""
    dg = bpy.context.evaluated_depsgraph_get()
    tris, owner, labels = [], [], []
    global TRI_OBJ, TRI_VERTS
    TRI_OBJ, TRI_VERTS = [], []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        if not me.loop_triangles:
            ev.to_mesh_clear(); continue
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        m = np.array(o.matrix_world); co = co @ m[:3, :3].T + m[:3, 3]
        idx = np.empty(len(me.loop_triangles) * 3, dtype=np.int64); me.loop_triangles.foreach_get("vertices", idx)
        mat = np.empty(len(me.loop_triangles), dtype=np.int64); me.loop_triangles.foreach_get("material_index", mat)
        t = co[idx.reshape(-1, 3)]
        vi = idx.reshape(-1, 3)
        for mi in np.unique(mat):
            name = me.materials[mi].name if mi < len(me.materials) and me.materials[mi] else "none"
            labels.append("%s/%s" % (o.name, name))
            sel = mat == mi
            tris.append(t[sel]); owner.append(np.full(sel.sum(), len(labels) - 1))
            TRI_OBJ.extend([o.name] * int(sel.sum())); TRI_VERTS.extend(vi[sel].tolist())
        ev.to_mesh_clear()
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros(0, dtype=int), labels
    return np.concatenate(tris), np.concatenate(owner), labels


def point_in_tri(p, a, b, c):
    v0, v1, v2 = c - a, b - a, p - a
    d00 = (v0 * v0).sum(-1); d01 = (v0 * v1).sum(-1); d11 = (v1 * v1).sum(-1)
    d20 = (v2 * v0).sum(-1); d21 = (v2 * v1).sum(-1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    u = (d11 * d20 - d01 * d21) / den; v = (d00 * d21 - d01 * d20) / den
    return (u > 0.02) & (v > 0.02) & (u + v < 0.98)


def analyse(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    t, owner, labels = triangles()
    if len(t) == 0:
        return {"asset": os.path.basename(path), "tris": 0, "pairs": []}
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    keep = area > MIN_AREA
    n0 = n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    if not OPPOSITE: keep &= n0[:, 2] > -0.7          # downward faces (undersides on floors/ground) are never seen
    tri_ids = np.nonzero(keep)[0]
    t, owner, n, area = t[keep], owner[keep], n[keep], area[keep]
    n = n / np.linalg.norm(n, axis=1)[:, None]
    owner_area = np.bincount(owner, weights=area, minlength=len(labels))
    moves = {}
    d = (n * t[:, 0]).sum(1)
    # Bucket by quantised normal + plane distance (and neighbouring distance buckets).
    qn = np.round(n * 20).astype(np.int64)
    qd = np.floor(d / PLANE_TOL).astype(np.int64)
    buckets = {}
    for i in range(len(t)):
        buckets.setdefault((qn[i, 0], qn[i, 1], qn[i, 2], qd[i]), []).append(i)
    centroid = t.mean(1)
    # Sample points inside each triangle (centroid + points toward each corner).
    # Centroid, points toward each corner (40 % and 85 % of the way) and toward each edge midpoint:
    # large triangles that overlap only partly (a slab corner under a path) are caught too.
    mids = (t + np.roll(t, -1, axis=1)) * 0.5
    samples = np.concatenate([centroid[:, None], (0.6 * centroid[:, None] + 0.4 * t), (0.15 * centroid[:, None] + 0.85 * t),
                              (0.2 * centroid[:, None] + 0.8 * mids)], axis=1)  # (N,10,3)
    pairs = {}
    for key, members in buckets.items():
        cand = []
        if OPPOSITE:
            # Plane (-n, -d): the opposite-facing bucket.
            for dq in (-2, -1, 0, 1):
                cand += buckets.get((-key[0], -key[1], -key[2], -key[3] + dq), [])
        else:
            for dq in (-1, 0, 1):
                cand += buckets.get((key[0], key[1], key[2], key[3] + dq), [])
        if len(cand) < (1 if OPPOSITE else 2):
            continue
        cand = np.array(cand)
        for i in members:
            others = cand[(cand != i)]
            if OPPOSITE:
                others = others[(np.abs(d[others] + d[i]) < PLANE_TOL) & ((n[others] @ n[i]) < -NORMAL_TOL) & (owner[others] != owner[i])]
            else:
                others = others[(np.abs(d[others] - d[i]) < PLANE_TOL) & ((n[others] @ n[i]) > NORMAL_TOL)]
            if len(others) == 0:
                continue
            # Any other triangle in the same plane whose interior overlaps (a clean mesh tiles a plane
            # without overlaps, so this catches stacked boxes and duplicated faces in one material too).
            if len(others) == 0:
                continue
            a, b, c = t[others, 0], t[others, 1], t[others, 2]
            hit = np.zeros(len(others), dtype=bool)
            for s in range(samples.shape[1]):
                hit |= point_in_tri(samples[i, s][None, :], a, b, c)
            for j in others[hit]:
                k = (min(owner[i], owner[j]), max(owner[i], owner[j]))
                rec = pairs.setdefault(k, {"area": 0.0, "at": centroid[i].round(2).tolist(), "n": n[i].round(2).tolist()})
                rec["area"] += float(area[i])
                # The smaller part (trim, detail) moves in front of the larger one.
                small = i if owner_area[owner[i]] <= owner_area[owner[j]] else j
                if owner[i] == owner[j] or owner_area[owner[i]] == owner_area[owner[j]]: small = i if area[i] < area[j] - 1e-9 else (j if area[j] < area[i] - 1e-9 else max(i, j))
                moves[int(tri_ids[small])] = n[small]
    out = sorted(({"a": labels[k[0]], "b": labels[k[1]], "area": round(v["area"] / 2, 4), "at": v["at"], "n": v["n"]} for k, v in pairs.items()), key=lambda r: -r["area"])
    if FIX and moves:
        from mathutils import Vector
        done = {}
        for tri, normal in moves.items():
            o = bpy.data.objects[TRI_OBJ[tri]]
            local = o.matrix_world.to_3x3().inverted() @ Vector(normal.tolist()) * NUDGE
            for v in TRI_VERTS[tri]:
                if (o.name, v) in done: continue
                done[(o.name, v)] = True
                o.data.vertices[v].co += local
        # Keep the baked vertex colours (AO) the kit / restaurant GLBs carry.
        try:
            bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_extras=True, export_yup=True, export_vertex_color='ACTIVE')
        except TypeError:
            bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_extras=True, export_yup=True)
        print("FIXED", os.path.basename(path), "moved", len(moves), "triangles", flush=True)
    return {"asset": os.path.basename(path), "tris": int(len(t)), "pairs": out}


files = []
for a in ARGS:
    if os.path.isdir(a):
        files += [os.path.join(a, f) for f in sorted(os.listdir(a)) if f.endswith(".glb")]
    else:
        files.append(a)
report = []
for f in files:
    r = analyse(f)
    report.append(r)
    total = sum(p["area"] for p in r["pairs"])
    print("ZF %-34s tris %7d  overlapping %.3f m2 in %d pairs" % (r["asset"], r["tris"], total, len(r["pairs"])), flush=True)
    for p in r["pairs"][:4]:
        print("     %.3f m2  %s  <->  %s  at %s n %s" % (p["area"], p["a"], p["b"], p["at"], p["n"]), flush=True)
if OUT:
    json.dump(report, open(OUT, "w"), indent=1)
