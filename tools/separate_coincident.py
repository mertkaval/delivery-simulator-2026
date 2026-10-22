"""Separate coincident faces in a GLB: a face lying on a face of another material / object (centroid
within --tol of its plane, parallel within ~11 degrees, either facing) is split off and pushed along
its own normal by --dist. Of each pair, the part (object/material) with the smaller total area
moves, so labels, caps, fillings and trims step clear of the body they were modelled on.

Catches what tools/find_zfighting.py misses on imported props: curved shells (bottle glass and the
liquid in it, label wraps) and duplicated faces whose samples straddle triangle edges.

blender --background --factory-startup --python tools/separate_coincident.py -- <glb> [...] [--tol 0.0008] [--dist 0.0015] [--dry] [--same]
--same: same-facing pairs only (for single-sided assets, where back-to-back faces cannot fight).
"""
import os
import sys

import bmesh
import bpy
import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def opt(name, default):
    if name in ARGS:
        i = ARGS.index(name)
        value = ARGS[i + 1]
        del ARGS[i:i + 2]
        return float(value)
    return default
TOL = opt("--tol", 0.0008)
DIST = opt("--dist", 0.0015)
DRY = "--dry" in ARGS
SAME = "--same" in ARGS
ARGS = [a for a in ARGS if a not in ("--dry", "--same")]


def faces_of(objects):
    """(object, face index, owner label, normal, centroid, area, triangles) of every face, world space."""
    out = []
    for o in objects:
        me = o.data
        mw = o.matrix_world
        rot = mw.to_3x3()
        for p in me.polygons:
            if p.area < 1e-7:
                continue
            n = (rot @ p.normal).normalized()
            vs = [mw @ me.vertices[v].co for v in p.vertices]
            tris = [(vs[0], vs[k], vs[k + 1]) for k in range(1, len(vs) - 1)]
            label = "%s/%s" % (o.name, me.materials[p.material_index].name if me.materials and me.materials[p.material_index] else "-")
            c = mw @ p.center
            # Sample points: the centre and points 40 % of the way to each corner (a centre on the
            # other face's triangle diagonal counts as inside neither triangle).
            samples = [np.array(c)] + [np.array(c + (v - c) * 0.4) for v in vs]
            out.append((o, p.index, label, np.array(n), np.array(c), p.area, tris, samples))
    return out


def inside(c, tri):
    p0, p1, p2 = [np.array(v) for v in tri]
    v0, v1, v2 = p2 - p0, p1 - p0, c - p0
    d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-14:
        return False
    u = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return u > 0.01 and w > 0.01 and u + w < 0.99


def process(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    F = faces_of(objects)
    if not F:
        return
    N = np.array([f[3] for f in F])
    P = np.array([np.array(f[6][0][0]) for f in F])   # a point on each face's plane
    C = np.array([f[4] for f in F])
    labels = [f[2] for f in F]
    owner_area = {}
    for f in F:
        owner_area[f[2]] = owner_area.get(f[2], 0.0) + f[5]
    move = {}   # (object name, face index) -> normal (local)
    area = 0.0
    for i, f in enumerate(F):
        par = (N @ N[i]) > 0.98 if SAME else np.abs(N @ N[i]) > 0.98
        near = np.abs(((C[i] - P) * N).sum(1)) < TOL
        for j in np.nonzero(par & near)[0]:
            if labels[j] == labels[i]:
                continue
            if not any(inside(s, t) for s in f[7] for t in F[j][6]):
                continue
            # The smaller part moves (ties: the later label), both faces of the pair are not moved.
            small = i if (owner_area[labels[i]], labels[i]) < (owner_area[labels[j]], labels[j]) else j
            g = F[small]
            move[(g[0].name, g[1])] = True
            area += f[5]
            break
    print("COINCIDENT %-30s %.4f m2, %d faces to move" % (os.path.basename(path), area, len(move)), flush=True)
    if DRY or not move:
        return
    for o in objects:
        idx = [k[1] for k in move if k[0] == o.name]
        if not idx:
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        faces = [bm.faces[k] for k in idx]
        res = bmesh.ops.split(bm, geom=faces, use_only_faces=False)
        faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
        bm.normal_update()
        push = {}
        for f in faces:
            for v in f.verts:
                push[v] = push.get(v, f.normal * 0.0) + f.normal
        for v, n in push.items():
            if n.length > 1e-9:
                v.co += n.normalized() * DIST
        bm.to_mesh(o.data)
        bm.free()
    try:
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_extras=True, export_yup=True, export_vertex_color="ACTIVE")
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_extras=True, export_yup=True)
    print("SEPARATED", os.path.basename(path), len(move), "faces by", DIST, flush=True)


for a in ARGS:
    process(a)
