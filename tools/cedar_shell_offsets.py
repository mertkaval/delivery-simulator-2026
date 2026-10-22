"""Cedar House shell: consistent windings and lifted linings, so the house can be drawn single-sided.

The house GLB (world/cedar_house/assets/cedar_house.glb) arrives with double-sided materials and
inconsistent windings, and its finishes are open sheets lying exactly on the boxes behind them
(plaster on the wall boards, skirting on the plaster, oak boards on the joists). Drawn
double-sided, every such pair fought; drawn single-sided as authored, the faces wound the wrong
way vanished (foundation, steps, parts of the trim and the kitchen plaster).

  1. Closed islands (every edge shared by two faces) are re-wound to face out of the solid, except
     room shells (islands at least ROOM m in every direction, e.g. the interior plaster box), which
     keep the side their majority of faces was authored to face.
  2. A sheet face lying on a face of a solid (parallel, within --tol, either winding) is re-wound to
     face the way that solid's face does and lifted --dist in front of it.
  3. Other sheet faces get a back face (a flipped copy), so they stay visible from both sides.

house_asset.gd then culls back faces for every opaque material (glass and foliage stay double).

blender --background --factory-startup --python tools/cedar_shell_offsets.py -- [--dist 0.003] [--tol 0.0008] [--dry]
"""
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def opt(name, default):
    if name in ARGS:
        return float(ARGS[ARGS.index(name) + 1])
    return default
DIST = opt("--dist", 0.003)
TOL = opt("--tol", 0.0008)
ROOM = 1.2
DRY = "--dry" in ARGS
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "world", "cedar_house", "assets", "cedar_house.glb")
SKIP = ("glass", "leaf", "leaves")   # drawn double-sided anyway

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=PATH)
objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]


def key(co):
    return tuple(round(x * 10000) for x in co)


class Part:
    """One object: faces in world space with island data and the winding wanted for culling."""
    def __init__(self, o):
        self.o = o
        mats = [m.name.lower() if m else "" for m in o.data.materials]
        self.skip = any(any(s in m for s in SKIP) for m in mats)
        mw = o.matrix_world
        me = o.data
        self.n = len(me.polygons)
        self.centre = []
        self.normal = []
        self.area = []
        self.tris = []
        self.samples = []
        self.verts = []
        for p in me.polygons:
            vs = [mw @ me.vertices[v].co for v in p.vertices]
            c = sum(vs, Vector()) / len(vs)
            n = (vs[1] - vs[0]).cross(vs[2] - vs[0])
            for i in range(2, len(vs) - 1):
                n += (vs[i] - vs[0]).cross(vs[i + 1] - vs[0])
            a = n.length / 2
            n = n.normalized() if a > 0 else Vector((0, 0, 1))
            self.centre.append(c)
            self.normal.append(n)
            self.area.append(a)
            self.tris.append([(vs[0], vs[i], vs[i + 1]) for i in range(1, len(vs) - 1)])
            self.samples.append([c] + [c + (v - c) * 0.4 for v in vs])
            self.verts.append(list(p.vertices))
        # Islands by edge position.
        edge_faces = {}
        face_edges = []
        for i, p in enumerate(me.polygons):
            ks = []
            for a, b in p.edge_keys:
                k = tuple(sorted((key(mw @ me.vertices[a].co), key(mw @ me.vertices[b].co))))
                ks.append(k)
                edge_faces.setdefault(k, []).append(i)
            face_edges.append(ks)
        self.island = [-1] * self.n
        self.closed = []
        self.room = []
        for f in range(self.n):
            if self.island[f] >= 0:
                continue
            k = len(self.closed)
            stack = [f]
            members = []
            while stack:
                g = stack.pop()
                if self.island[g] >= 0:
                    continue
                self.island[g] = k
                members.append(g)
                for ek in face_edges[g]:
                    for h in edge_faces[ek]:
                        if self.island[h] < 0:
                            stack.append(h)
            closed = all(len(edge_faces[ek]) == 2 for g in members for ek in face_edges[g])
            pts = [self.centre[g] for g in members]
            size = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)]
            self.closed.append(closed)
            self.room.append(closed and min(size) >= ROOM)
        # Wanted facing (+1 keep, -1 flip) for closed islands. Outward comes from Blender's
        # recalc on a welded copy (concave solids too); the centre-of-area test is the fallback.
        self.want = [0] * self.n
        weld = bmesh.new()
        weld.from_mesh(me)
        bmesh.ops.remove_doubles(weld, verts=weld.verts, dist=0.0001)
        weld.faces.ensure_lookup_table()
        welded = len(weld.faces) == self.n
        for k in range(len(self.closed)):
            if not self.closed[k]:
                continue
            members = [g for g in range(self.n) if self.island[g] == k]
            if welded:
                faces = [weld.faces[g] for g in members]
                before = [f.normal.copy() for f in faces]
                bmesh.ops.recalc_face_normals(weld, faces=faces)
                outward = [1 if f.normal.dot(b) >= 0 else -1 for f, b in zip(faces, before)]
            else:
                tot = sum(self.area[g] for g in members) or 1e-9
                mid = sum((self.centre[g] * self.area[g] for g in members), Vector()) / tot
                outward = [1 if self.normal[g].dot(self.centre[g] - mid) >= 0 else -1 for g in members]
            if self.room[k]:
                # Room shell: keep the side most of its area was authored to face.
                vote = sum(o * self.area[g] for o, g in zip(outward, members))
                side = 1 if vote >= 0 else -1
                for o, g in zip(outward, members):
                    self.want[g] = 1 if o == side else -1
            else:
                for o, g in zip(outward, members):
                    self.want[g] = o
        weld.free()


parts = [Part(o) for o in objects]
# Middle of the house (plan): interior linings face it, exterior cladding faces away.
_arch = [c for p in parts if p.o.name.startswith("Architecture") for c in p.centre]
MIDDLE = sum(_arch, Vector()) / max(1, len(_arch)) if _arch else Vector()
INTERIOR = ("plaster", "oak_floor", "bathroom_tile")
EXTERIOR = ("sage_painted_cedar", "charcoal_shingles")


def side_of(part, face):
    """+1 interior finish, -1 exterior cladding, 0 unknown."""
    name = part.o.name.lower()
    mats = [m.name.lower() for m in part.o.data.materials if m]
    if name.startswith("interior__") or any(any(k in m for k in INTERIOR) for m in mats):
        return 1
    if name.startswith("exterior_detail__") or any(any(k in m for k in EXTERIOR) for m in mats):
        return -1
    return 0
flat = [(pi, f) for pi, p in enumerate(parts) for f in range(p.n)]
C = np.array([list(parts[pi].centre[f]) for pi, f in flat])
N = np.array([list(parts[pi].normal[f]) for pi, f in flat])
P0 = np.array([list(parts[pi].tris[f][0][0]) for pi, f in flat])


def inside(c, tri):
    p0, p1, p2 = [np.array(v) for v in tri]
    v0, v1, v2 = p2 - p0, p1 - p0, np.array(c) - p0
    d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-14:
        return False
    u = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return u > 0.01 and w > 0.01 and u + w < 0.99


lift = {}       # (part, face) -> world direction (the sheet's final normal)
backs = set()   # (part, face) sheets that get a flipped copy
stats = {"solid_flips": 0, "lifted": 0, "lift_m2": 0.0, "backed": 0, "back_m2": 0.0}
for idx, (pi, f) in enumerate(flat):
    p = parts[pi]
    if p.skip or p.closed[p.island[f]]:
        continue
    par = np.abs(N @ N[idx]) > 0.98
    near = np.abs(((C[idx] - P0) * N).sum(1)) < TOL
    # Which of the face's sample points lie on a solid's face / on an opposite sheet face: the
    # majority decides (one corner sample on a neighbouring strip is not a pairing).
    found = None
    partner = None
    on_solid = [None] * len(p.samples[f])
    on_sheet = [False] * len(p.samples[f])
    for j in np.nonzero(par & near)[0]:
        qi, g = flat[j]
        q = parts[qi]
        if (qi, q.island[g]) == (pi, p.island[f]) or q.skip:
            continue
        for si, smp in enumerate(p.samples[f]):
            if not any(inside(smp, t) for t in q.tris[g]):
                continue
            if q.closed[q.island[g]]:
                on_solid[si] = q.normal[g] * q.want[g]
            elif p.normal[f].dot(q.normal[g]) < 0:
                on_sheet[si] = True
                partner = (qi, g)
    half = len(p.samples[f]) // 2 + 1
    solid_hits = [d for d in on_solid if d is not None]
    if len(solid_hits) >= half:
        found = solid_hits[0]
    paired = found is None and sum(on_sheet) >= half
    if found is None and paired:
        # An interior lining against an exterior cladding sheet (a zero-thickness wall): the lining
        # faces the house's middle, the cladding faces away from it, whatever they were wound.
        mine, theirs = side_of(p, f), side_of(parts[partner[0]], partner[1])
        if mine != 0 and theirs != 0 and mine != theirs:
            inward = p.normal[f].dot(MIDDLE - p.centre[f]) > 0
            p.want[f] = 1 if inward == (mine > 0) else -1
        else:
            p.want[f] = 1
        stats["paired"] = stats.get("paired", 0) + 1
        continue
    if found is not None:
        lift[(pi, f)] = found
        p.want[f] = 1 if p.normal[f].dot(found) >= 0 else -1
        stats["lifted"] += 1
        stats["lift_m2"] += p.area[f]
    else:
        p.want[f] = 1
        backs.add((pi, f))
        stats["backed"] += 1
        stats["back_m2"] += p.area[f]
for p in parts:
    stats["solid_flips"] += sum(1 for f in range(p.n) if p.closed[p.island[f]] and p.want[f] < 0)
print("SHELL solids: %d faces re-wound; sheets: %d faces on solids (%.1f m2) lifted %.4f m, %d paired with a sheet, %d free sheet faces (%.1f m2) get a back face"
      % (stats["solid_flips"], stats["lifted"], stats["lift_m2"], DIST, stats.get("paired", 0), stats["backed"], stats["back_m2"]), flush=True)
if DRY:
    sys.exit(0)

for pi, p in enumerate(parts):
    o = p.o
    inv = o.matrix_world.inverted().to_3x3()
    me = o.data
    # Shading normals per corner (the importer's custom split normals), keyed by face and vertex.
    corner = me.corner_normals if hasattr(me, "corner_normals") else None
    shade = {}
    for f, poly in enumerate(me.polygons):
        for li in poly.loop_indices:
            n = corner[li].vector.copy() if corner is not None else me.loops[li].normal.copy()
            shade[(f, me.loops[li].vertex_index)] = n
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    push = {}
    for f in range(p.n):
        if (pi, f) in lift:
            d = inv @ lift[(pi, f)] * DIST
            for v in bm.faces[f].verts:
                push.setdefault(v.index, d)
    for v, d in push.items():
        bm.verts[v].co += d
    flipped = {f for f in range(p.n) if p.want[f] < 0}
    if flipped:
        bmesh.ops.reverse_faces(bm, faces=[bm.faces[f] for f in flipped])
    copies = {}   # new face index -> (source face, {new vert index: old vert index})
    originals = list(bm.faces)
    for f in [f for f in range(p.n) if (pi, f) in backs]:
        src = originals[f]
        old = [v for v in reversed(src.verts)]
        new_verts = [bm.verts.new(v.co) for v in old]
        g = bm.faces.new(new_verts)
        g.material_index = src.material_index
        g.smooth = src.smooth
        if uv is not None:
            uvs = {l.vert.index: l[uv].uv.copy() for l in src.loops}
            for l, ov in zip(g.loops, old):
                l[uv].uv = uvs[ov.index]
        bm.verts.index_update()
        bm.faces.index_update()
        copies[g.index] = (f, {nv.index: ov.index for nv, ov in zip(new_verts, old)})
    bm.to_mesh(me)
    bm.free()
    # Shading normals follow the final winding (the authored ones mostly pointed the visible way
    # already, whatever the winding): kept where they agree with the face, negated where not.
    loops_n = []
    for poly in me.polygons:
        geo = poly.normal
        for li in poly.loop_indices:
            v = me.loops[li].vertex_index
            if poly.index in copies:
                f, back = copies[poly.index]
                n = shade.get((f, back[v]), geo.copy())
            else:
                n = shade.get((poly.index, v), geo.copy())
            loops_n.append(n if n.dot(geo) >= 0 else -n)
    me.normals_split_custom_set(loops_n)
    me.update()
try:
    bpy.ops.export_scene.gltf(filepath=PATH, export_format="GLB", export_extras=True, export_yup=True, export_vertex_color="ACTIVE")
except TypeError:
    bpy.ops.export_scene.gltf(filepath=PATH, export_format="GLB", export_extras=True, export_yup=True)
print("SHELL exported", PATH, flush=True)
