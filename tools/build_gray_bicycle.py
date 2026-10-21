"""Riderless gray bicycle extracted from the supplied "woman riding a gray bicycle" model.

blender --background --factory-startup --python tools/build_gray_bicycle.py [-- noqa]

Source: sketchup_assets/woman_riding_a_gray_bicycle.glb - one fused mesh (550k tris, one
material, an automatic texture atlas). Rider and bicycle share vertices where they touch, so
loose-part splitting cannot separate them (after welding it is one connected shell).

Extraction:
  1. Rider faces are classified per face from the base-colour texture: skin, the pink top, the
     olive skirt and the beige bag are saturated (HSV s > 0.13) while every bicycle surface is
     grey/black (s < 0.07); everything above z 1.30 (hair, head) and the white shoes (V > 0.82
     inside the two foot boxes) are rider too. Labels are smoothed over the face graph and small
     islands flipped, then the rider faces are deleted. Floating rider leftovers (waist
     drawstring) are removed as loose parts.
  2. Parts hidden by the rider are rebuilt simply: the saddle (completely inside the skirt), the
     leather grips between the bar collars and the grip ends (inside the fists). The 36-spoke
     lacing is regenerated as straight 3-sided spokes (the scanned spokes are wavy tubes that
     collapse under decimation).
  3. Rig split: front/rear wheel (tyre torus, rim, hub) by circle fits to the tread; the
     steering assembly (stem, bars, levers, upper cables, fork, front mudguard) is everything
     above the head-tube top or below the head-tube bottom ahead of the down tube; cuts are made
     with bisect planes so the seams are straight.
  4. Each part is decimated, the low parts are unwrapped together and base colour + normals are
     baked from the cleaned high-res mesh into one 1024 atlas.

Output: assets/bicycles/gray_bicycle.glb, metres, +Y forward in Blender (= Godot -Z), wheels on
the ground (z 0), origin midway between the hubs. Rig contract (same as the old bike):
  GrayBicycle (root, extras: wheelbase, wheel_radius, asset_source)
    Frame, Saddle                    static meshes
    SteeringPivot                    on the head-tube axis, local +Y (Godot) = steering axis
      ForkAndBars                    fork, mudguard, stem, bars, grips, levers
      WheelFront                     at the front hub, identity rotation, spins about local X
        FrontWheelMesh
    WheelRear                        at the rear hub, spins about local X
      RearWheelMesh
QA renders: world/vehicles/production/renders/gray_bicycle/.
"""
import bpy, bmesh, sys, os, math, json
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sketchup_assets", "woman_riding_a_gray_bicycle.glb")
OUT_DIR = os.path.join(ROOT, "assets", "bicycles")
OUT = os.path.join(OUT_DIR, "gray_bicycle.glb")
OUT_RIDER = os.path.join(OUT_DIR, "gray_bicycle_rider.glb")
QA_DIR = os.path.join(ROOT, "world", "vehicles", "production", "renders", "gray_bicycle")
REPORT = os.path.join(ROOT, "world", "vehicles", "production", "reports", "gray_bicycle.json")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_QA = "noqa" not in ARGS
TEX = 1024
WHEEL_RADIUS = 0.35            # target tyre radius in metres (700c x 50 tyre: 0.70 m)
RIDER_BUDGET = 14000
BUDGET = {"frame": 11000, "steer": 5200, "wheel_f": 3000, "wheel_r": 3400}

# Measured on the source (after the 180 deg turn so the bike faces +Y, ground at z 0).
HUB_F = (0.5772, 0.3732); R_F = 0.3667      # circle fit to the tread, residual < 2 mm
HUB_R = (-0.5783, 0.3678); R_R = 0.3676
HUB_X = 0.001
TYRE_TUBE = 0.0255                          # tyre cross-section radius (half width 0.025)
RIM_IN = 0.302                              # spoke nipples / rim inner edge
AXIS_P = np.array([0.0, 0.3395, 0.91])      # head-tube axis point (top of head tube)
AXIS_U = np.array([0.0, -0.3625, 1.0]); AXIS_U /= np.linalg.norm(AXIS_U)  # 70.1 deg head angle
AXIS_F = np.array([0.0, AXIS_U[2], -AXIS_U[1]])                            # forward normal
HEAD_TOP, HEAD_BOTTOM = 0.955, 0.69         # steering cuts (z) above / below the head tube
SEAT_CLAMP = Vector((0.0, -0.318, 0.903))   # top of the seat post (saddle clamp)
GRIP_COLLAR = (0.226, 0.371, 1.056)         # bar cut just inside the collar where the fist began (x mirrored)


def log(*a):
    print("[bike]", *a, flush=True)


# ----------------------------------------------------------------------------- helpers
def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def tris(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == 'MESH')


def verts(o):
    co = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def face_arrays(me):
    n = len(me.polygons)
    lt = np.empty(n, int); me.polygons.foreach_get("loop_total", lt)
    cen = np.empty(n * 3); me.polygons.foreach_get("center", cen)
    return lt, cen.reshape(-1, 3)


def face_pairs(me):
    n = len(me.polygons)
    lt = np.empty(n, int); me.polygons.foreach_get("loop_total", lt)
    le = np.empty(len(me.loops), int); me.loops.foreach_get("edge_index", le)
    lf = np.repeat(np.arange(n), lt)
    order = np.argsort(le, kind='stable')
    e, f = le[order], lf[order]
    same = e[1:] == e[:-1]
    return f[:-1][same], f[1:][same]


def components(mask, a, b):
    """Connected components of the faces in `mask` (face graph a-b); -1 outside the mask."""
    n = len(mask)
    keep = mask[a] & mask[b]
    aa = np.concatenate([a[keep], b[keep]]); bb = np.concatenate([b[keep], a[keep]])
    order = np.argsort(aa, kind='stable'); aa, bb = aa[order], bb[order]
    start = np.searchsorted(aa, np.arange(n)); end = np.searchsorted(aa, np.arange(n), side='right')
    lab = np.full(n, -1)
    cur = 0
    for f in np.nonzero(mask)[0]:
        if lab[f] >= 0:
            continue
        lab[f] = cur
        stack = [f]
        while stack:
            x = stack.pop()
            for y in bb[start[x]:end[x]]:
                if lab[y] < 0:
                    lab[y] = cur
                    stack.append(y)
        cur += 1
    return lab


def delete_faces(o, mask):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(mask)[0]], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(o.data); bm.free()


def split_off(o, mask, name):
    """New object holding the faces in `mask`; they are removed from `o`."""
    new = o.copy(); new.data = o.data.copy(); new.name = new.data.name = name
    bpy.context.scene.collection.objects.link(new)
    delete_faces(new, ~mask)
    delete_faces(o, mask)
    return new


def bisect(o, z, box, normal=(0, 0, 1)):
    """Planar cut (default horizontal at height z) through the faces whose centres lie in box."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    x0, x1, y0, y1, z0, z1 = box
    faces = [f for f in bm.faces if (lambda c: x0 < c.x < x1 and y0 < c.y < y1 and z0 < c.z < z1)(f.calc_center_median())]
    geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=Vector(normal) * z, plane_no=normal)
    bm.to_mesh(o.data); bm.free()


def decimate(o, target):
    cur = tris([o])
    if cur > target:
        select_only([o])
        m = o.modifiers.new("Decimate", 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.ratio = max(0.001, target / cur)
        m.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=m.name)
    log("  decimated", o.name, cur, "->", tris([o]))


def material(name, color, metallic=0.0, roughness=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def mesh_object(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


# ----------------------------------------------------------------------------- source
def load_source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    for o in meshes:
        mw = o.matrix_world.copy(); o.parent = None; o.data.transform(mw); o.matrix_world = Matrix.Identity(4)
    for o in list(bpy.data.objects):
        if o not in meshes:
            bpy.data.objects.remove(o)
    select_only(meshes)
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = o.data.name = "Source"
    o.data.transform(Matrix.Rotation(math.pi, 4, 'Z'))     # bicycle front -> +Y
    o.data.transform(Matrix.Translation((0, 0, -verts(o)[:, 2].min())))
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)   # weld the glTF primitive/UV splits
    bm.to_mesh(o.data); bm.free()
    log("source tris", tris([o]))
    return o


def face_colors(o):
    """Mean base-colour texel per face (the material maps UVMap through a x16 texture transform)."""
    me = o.data
    im = next(n.image for n in me.materials[0].node_tree.nodes
              if n.type == 'TEX_IMAGE' and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links))
    mapping = next(n for n in me.materials[0].node_tree.nodes if n.type == 'MAPPING')
    loc = mapping.inputs["Location"].default_value; scl = mapping.inputs["Scale"].default_value
    W, H = im.size
    px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); px = px.reshape(H, W, 4)
    uv = np.empty(len(me.loops) * 2); me.uv_layers["UVMap"].data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
    u = uv[:, 0] * scl[0] + loc[0]; v = uv[:, 1] * scl[1] + loc[1]
    x = np.clip((u % 1.0) * W, 0, W - 1).astype(int); y = np.clip((v % 1.0) * H, 0, H - 1).astype(int)
    lc = px[y, x, :3]
    lt, cen = face_arrays(me)
    fl = np.repeat(np.arange(len(lt)), lt)
    fc = np.zeros((len(lt), 3)); np.add.at(fc, fl, lc); fc /= lt[:, None]
    mx = fc.max(1); mn = fc.min(1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return s, mx, cen


def remove_rider(o):
    s, v, cen = face_colors(o)
    a, b = face_pairs(o.data)
    x, y, z = cen[:, 0], cen[:, 1], cen[:, 2]
    shoes = (v > 0.82) & (s < 0.2) & (((x > 0.03) & (y > -0.3) & (y < 0.2) & (z > 0.38) & (z < 0.72)) |
                                      ((x < -0.03) & (y > -0.4) & (y < 0.12) & (z > 0.0) & (z < 0.36)))
    r = ((s > 0.13) | (z > 1.30) | shoes).astype(float)
    for _ in range(3):                         # neighbour vote over the face graph
        acc = r.copy(); cnt = np.ones_like(r)
        np.add.at(acc, a, r[b]); np.add.at(cnt, a, 1)
        np.add.at(acc, b, r[a]); np.add.at(cnt, b, 1)
        r = acc / cnt
    rider = r > 0.5
    for _ in range(2):
        lab = components(rider, a, b); k = lab.max() + 1
        size = np.bincount(lab[lab >= 0], minlength=k)
        rider[(lab >= 0) & (size < 1500)[np.maximum(lab, 0)]] = False      # specks on the bike
        lab = components(~rider, a, b); k = lab.max() + 1
        size = np.bincount(lab[lab >= 0], minlength=k)
        touch = np.zeros(k, bool)
        m = (lab[a] >= 0) & rider[b]; touch[lab[a][m]] = True
        m = (lab[b] >= 0) & rider[a]; touch[lab[b][m]] = True
        rider[(lab >= 0) & ((size < 800) & touch)[np.maximum(lab, 0)]] = True  # holes in the rider
    log("rider faces", int(rider.sum()), "bicycle faces", int((~rider).sum()))
    rider_obj = split_off(o, rider, "Rider")
    # floating rider leftovers: loose shells above the bike that are not the grip ends
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    co = np.array([vv.co[:] for vv in bm.verts])
    seen = np.zeros(len(bm.verts), bool); parts = []
    for v0 in bm.verts:
        if seen[v0.index]:
            continue
        stack = [v0]; seen[v0.index] = True; ids = []
        while stack:
            vv = stack.pop(); ids.append(vv.index)
            for e in vv.link_edges:
                w = e.other_vert(vv)
                if not seen[w.index]:
                    seen[w.index] = True; stack.append(w)
        parts.append(ids)
    parts.sort(key=len, reverse=True)
    drop = set()
    for ids in parts[1:]:
        P = co[ids]
        if P[:, 2].max() > 0.9 and abs(P[:, 0].mean()) < 0.25:
            drop.update(ids)
            log("  leftover rider shell", len(ids), "verts at", P.mean(0).round(3), "-> rider")
    bm.free()
    if drop:   # the waist drawstring: hand it back to the rider
        mask = np.array([all(vi in drop for vi in p.vertices) for p in o.data.polygons])
        bits = split_off(o, mask, "RiderBits")
        select_only([rider_obj, bits], rider_obj); bpy.ops.object.join()
    return rider_obj


# ----------------------------------------------------------------------------- rig masks
def wheel_masks(cen):
    out = {}
    for name, (yc, zc), R in (("wheel_f", HUB_F, R_F), ("wheel_r", HUB_R, R_R)):
        d = np.hypot(cen[:, 1] - yc, cen[:, 2] - zc); dx = np.abs(cen[:, 0] - HUB_X)
        tyre = np.hypot(d - (R - TYRE_TUBE), dx) <= TYRE_TUBE + 0.0035
        rim = (d >= RIM_IN - 0.002) & (d <= R - TYRE_TUBE) & (dx <= 0.014)
        hub = ((d < 0.07) & (dx <= 0.03)) | ((d < 0.03) & (dx <= 0.048))
        spokes = (d >= 0.07) & (d < RIM_IN - 0.002) & (dx <= np.where(d < 0.12, 0.026, 0.022))
        out[name] = tyre | rim | hub
        out[name + "_spokes"] = spokes & ~out[name]
    return out


def steer_mask(cen):
    x, y, z = cen[:, 0], cen[:, 1], cen[:, 2]
    w = (cen - AXIS_P) @ AXIS_F
    dF = np.hypot(y - HUB_F[0], z - HUB_F[1])
    top = (z > HEAD_TOP) & (y > 0.2)
    bottom = (z < HEAD_BOTTOM) & (y > 0.3) & ((w > -0.02) | ((np.abs(x) > 0.033) & (dF < R_F)))
    return top | bottom


# ----------------------------------------------------------------------------- rebuilt parts
def build_saddle(mat):
    """Sport-comfort saddle on the seat-post clamp (the source saddle is inside the skirt)."""
    bm = bmesh.new()
    rings, seg = 18, 20
    L, rear, nose = 0.27, 0.125, 0.145
    prev = None; first = None
    for i in range(rings + 1):
        t = i / rings
        yy = SEAT_CLAMP.y - rear + L * t
        w = 0.042 + 0.118 * (1 - (min(max((t - 0.33) / 0.6, 0), 1) ** 1.4))
        if t < 0.14:
            w *= math.sqrt(max(0.0, 1 - ((0.14 - t) / 0.14) ** 2)) * 0.9 + 0.1
        if t > 0.94:
            w *= 0.55 + 0.45 * math.sqrt(max(0.0, 1 - ((t - 0.94) / 0.06) ** 2))
        hh = 0.018 + 0.006 * (1 - t)                       # half thickness
        zc = SEAT_CLAMP.z + 0.036 + 0.006 * math.sin(math.pi * t) - 0.004 * t
        ring = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            c, s = math.cos(a), math.sin(a)
            xx = 0.5 * w * math.copysign(abs(c) ** 0.6, c)
            zz = hh * math.copysign(abs(s) ** (0.45 if s > 0 else 0.7), s)
            if s > 0:
                zz -= 0.008 * (xx / (0.5 * w + 1e-6)) ** 2  # top rolls off at the sides
            ring.append(bm.verts.new((xx, yy, zc + zz)))
        if prev:
            for j in range(seg):
                bm.faces.new((prev[j], prev[(j + 1) % seg], ring[(j + 1) % seg], ring[j]))
        else:
            first = ring
        prev = ring
    bm.faces.new(list(reversed(first)))
    bm.faces.new(prev)
    # clamp and rails down to the post
    for xx in (-0.022, 0.022):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0035, radius2=0.0035, depth=0.17,
                              matrix=Matrix.Translation((xx, SEAT_CLAMP.y + 0.01, SEAT_CLAMP.z + 0.012)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation(SEAT_CLAMP + Vector((0, 0, 0.006))) @ Matrix.Diagonal((0.05, 0.045, 0.02, 1)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object("Saddle", bm, mat)


def stub_axis(o, side):
    """The grip end that sticks out behind each fist: centre, axis (pointing back), radius, extent."""
    V = verts(o)
    m = (V[:, 0] * side > 0.28) & (V[:, 2] > 1.0) & (V[:, 1] > 0.2)
    P = V[m]
    c = P.mean(0)
    _, _, vt = np.linalg.svd(P - c)
    ax = vt[0] if vt[0][1] < 0 else -vt[0]
    t = (P - c) @ ax
    radial = np.linalg.norm((P - c) - np.outer(t, ax), axis=1)
    return Vector(c), Vector(ax), float(np.median(radial)), float(t.min()), float(t.max())


def ring(bm_obj_name, at, axis, radius, depth, mat):
    bm = bmesh.new()
    q = axis.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius, radius2=radius, depth=depth,
                          matrix=Matrix.Translation(at) @ q)
    return mesh_object(bm_obj_name, bm, mat)


def build_grips(steer, mat, ring_mat):
    """Leather grips from the bar collars, swept back through the (removed) fists to bar-end plugs.
    The scanned grip ends behind the fists are measured and then replaced (their front edges are
    torn where the hands were)."""
    objs = []
    V = verts(steer)
    for side in (-1, 1):
        c, ax, r, tmin, tmax = stub_axis(steer, side)
        front = c + ax * tmin
        back = c + ax * (tmax - 0.010)
        p0 = Vector((side * GRIP_COLLAR[0], GRIP_COLLAR[1], GRIP_COLLAR[2]))
        d0 = Vector((side * 1.0, 0.05, 0.22)).normalized()
        # bar radius at the cut, for the lock-on ring that hides the seam
        sl = (V[:, 0] * side > GRIP_COLLAR[0] - 0.012) & (V[:, 0] * side <= GRIP_COLLAR[0] + 1e-4) &              (V[:, 2] > 1.02) & (V[:, 1] > 0.33) & (V[:, 1] < 0.43)
        S = V[sl][:, 1:]
        bar_r = float(np.clip(np.max(np.linalg.norm(S - (S.min(0) + S.max(0)) / 2, axis=1)) if len(S) else 0.02, 0.016, 0.028))
        cu = bpy.data.curves.new("GripCurve", 'CURVE'); cu.dimensions = '3D'
        cu.bevel_depth = r; cu.bevel_resolution = 3; cu.resolution_u = 8; cu.use_fill_caps = True
        sp = cu.splines.new('BEZIER'); sp.bezier_points.add(2)
        a, b, e = sp.bezier_points
        a.co = p0 - d0 * 0.004; a.handle_left = a.co - d0 * 0.03; a.handle_right = a.co + d0 * 0.05
        b.co = front; b.handle_left = front - ax * 0.05; b.handle_right = front + ax * 0.02
        e.co = back; e.handle_left = back - ax * 0.02; e.handle_right = back + ax * 0.02
        ob = bpy.data.objects.new("Grip", cu); bpy.context.scene.collection.objects.link(ob)
        select_only([ob]); bpy.ops.object.convert(target='MESH')
        ob = bpy.context.view_layer.objects.active
        ob.data.materials.clear(); ob.data.materials.append(mat)
        objs.append(ob)
        objs.append(ring("GripRing", p0 + d0 * 0.004, d0, min(bar_r * 1.08, 0.0225), 0.02, ring_mat))
        objs.append(ring("BarEndPlug", back + ax * 0.007, ax, r * 1.12, 0.016, ring_mat))
        log("  grip side %d: collar %s (bar r %.4f) -> bend %s -> end %s, grip r %.4f" % (
            side, tuple(round(v, 3) for v in p0), bar_r, tuple(round(v, 3) for v in front), tuple(round(v, 3) for v in back), r))
    # drop the torn scanned grip ends
    lt, cen = face_arrays(steer.data)
    delete_faces(steer, (np.abs(cen[:, 0]) > 0.28) & (cen[:, 2] > 1.0) & (cen[:, 1] > 0.2))
    select_only(objs); bpy.ops.object.join()
    g = bpy.context.view_layer.objects.active; g.name = "Grips"
    return g


def build_spokes(hub, mat, name, count=36):
    """Straight 3-sided spokes, 3-cross style lacing, alternating flanges."""
    yc, zc = hub
    bm = bmesh.new()
    rad = 0.0013
    for i in range(count):
        side = 1 if i % 2 == 0 else -1
        th = 2 * math.pi * i / count
        tr = th + (1 if (i // 2) % 2 == 0 else -1) * 2 * math.pi * 3 / count
        a = Vector((HUB_X + side * 0.024, yc + 0.022 * math.cos(th), zc + 0.022 * math.sin(th)))
        b = Vector((HUB_X + side * 0.002, yc + RIM_IN * math.cos(tr), zc + RIM_IN * math.sin(tr)))
        d = (b - a).normalized()
        u = d.orthogonal().normalized(); v = d.cross(u)
        ra = [bm.verts.new(a + (u * math.cos(k * 2.0944) + v * math.sin(k * 2.0944)) * rad) for k in range(3)]
        rb = [bm.verts.new(b + (u * math.cos(k * 2.0944) + v * math.sin(k * 2.0944)) * rad) for k in range(3)]
        for k in range(3):
            bm.faces.new((ra[k], ra[(k + 1) % 3], rb[(k + 1) % 3], rb[k]))
    o = mesh_object(name, bm, mat)
    for p in o.data.polygons:
        p.use_smooth = False
    return o


# ----------------------------------------------------------------------------- bake
def bake(hi, lows, prefix="GrayBicycle", size=TEX):
    """Join the low parts, unwrap them into one atlas and bake colour, metal/rough and normals
    from `hi` (which carries the source material)."""
    for i, o in enumerate(lows):
        attr = o.data.attributes.new("part", 'INT', 'FACE')
        attr.data.foreach_set("value", [i] * len(o.data.polygons))
        o.data.materials.clear()
    select_only(lows); bpy.ops.object.join()
    lo = bpy.context.view_layer.objects.active; lo.name = prefix + "Low"
    while lo.data.uv_layers:
        lo.data.uv_layers.remove(lo.data.uv_layers[0])
    lo.data.uv_layers.new(name="UVMap")
    for p in lo.data.polygons:
        p.use_smooth = True
    select_only([lo])
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    col = bpy.data.images.new(prefix + "_basecolor", size, size, alpha=False)
    nrm = bpy.data.images.new(prefix + "_normal", size, size, alpha=False)
    nrm.colorspace_settings.name = 'Non-Color'
    orm = bpy.data.images.new(prefix + "_metal_rough", size, size, alpha=False)
    orm.colorspace_settings.name = 'Non-Color'
    mat = bpy.data.materials.new(prefix)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = col
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = nrm
    tm = nt.nodes.new("ShaderNodeTexImage"); tm.image = orm
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    lo.data.materials.append(mat)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 2
    select_only([hi, lo], lo)
    opts = dict(use_selected_to_active=True, cage_extrusion=0.006, max_ray_distance=0.03, margin=6)
    src = hi.data.materials[0].node_tree
    out = next(n for n in src.nodes if n.type == 'OUTPUT_MATERIAL')
    src.links.new(next(n for n in src.nodes if n.type == 'BSDF_PRINCIPLED').outputs[0], out.inputs["Surface"])
    nt.nodes.active = tn
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', **opts)
    # The source paint is metallic (0.8): a DIFFUSE colour bake would come out ~5x too dark.
    # Bake the base-colour and metal/rough textures themselves through an emission shader.
    emit = src.nodes.new("ShaderNodeEmission")
    src.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    for img, node, target in ((col, tc, "Base Color"), (orm, tm, "SEPARATE_COLOR")):
        tex = next(n for n in src.nodes if n.type == 'TEX_IMAGE' and any(
            (l.to_socket.name == target) or (l.to_node.type == target) for l in n.outputs[0].links))
        src.links.new(tex.outputs["Color"], emit.inputs["Color"])
        nt.nodes.active = node
        bpy.ops.object.bake(type='EMIT', **opts)
    for img in (col, nrm, orm):
        img.pack()
        log("  baked", img.name)
    nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.nodes.active = tc
    # split back into the parts
    parts = []
    for i in range(len(lows) - 1):
        vals = np.empty(len(lo.data.polygons), int)
        lo.data.attributes["part"].data.foreach_get("value", vals)
        parts.append(split_off(lo, vals == i, "part%d" % i))
    parts.append(lo)
    for p in parts:
        p.data.attributes.remove(p.data.attributes["part"])
    return parts


# ----------------------------------------------------------------------------- main
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    src = load_source()
    rider = remove_rider(src)
    # straight steering cuts through the head-tube top (spacers) and the fork crown
    bisect(src, HEAD_TOP, (-0.08, 0.08, 0.2, 0.5, 0.9, 1.0))
    bisect(src, HEAD_BOTTOM, (-0.09, 0.09, 0.25, 0.75, 0.6, 0.78))
    # square off the bar collars: palm remnants hang past them (the new grips start there)
    for side in (-1, 1):
        lo_x, hi_x = sorted((side * 0.2, side * 0.3))
        bisect(src, GRIP_COLLAR[0], (lo_x, hi_x, 0.33, 0.43, 1.02, 1.1), normal=(side, 0, 0))
    lt, cen = face_arrays(src.data)
    ax = np.abs(cen[:, 0])
    delete_faces(src, (ax > GRIP_COLLAR[0]) & (ax < 0.29) & (cen[:, 1] > 0.33) & (cen[:, 1] < 0.43) & (cen[:, 2] > 1.02))
    lt, cen = face_arrays(src.data)
    wm = wheel_masks(cen)
    delete_faces(src, wm["wheel_f_spokes"] | wm["wheel_r_spokes"])        # regenerated below
    log("bicycle faces after spoke removal", len(src.data.polygons))
    lt, cen = face_arrays(src.data)
    wm = wheel_masks(cen)
    st = steer_mask(cen) & ~wm["wheel_f"] & ~wm["wheel_r"]
    hi = src.copy(); hi.data = src.data.copy(); hi.name = "BakeSource"
    bpy.context.scene.collection.objects.link(hi)
    frame = src; frame.name = frame.data.name = "Frame"
    wf = split_off(frame, wm["wheel_f"], "FrontWheelMesh")
    lt, cen = face_arrays(frame.data); wm2 = wheel_masks(cen)
    wr = split_off(frame, wm2["wheel_r"], "RearWheelMesh")
    lt, cen = face_arrays(frame.data)
    steer = split_off(frame, steer_mask(cen), "ForkAndBars")
    log("hi-res split: frame %d steer %d front %d rear %d" % (tris([frame]), tris([steer]), tris([wf]), tris([wr])))
    # rebuilt parts (source units; everything is transformed together at the end)
    m_saddle = material("GrayBicycle_Saddle", (0.02, 0.02, 0.021), 0.0, 0.5)
    m_grip = material("GrayBicycle_Grip", (0.16, 0.085, 0.04), 0.0, 0.62)
    m_spoke = material("GrayBicycle_Spokes", (0.55, 0.56, 0.58), 0.85, 0.32)
    saddle = build_saddle(m_saddle)
    grips = build_grips(steer, m_grip, m_saddle)
    spokes_f = build_spokes(HUB_F, m_spoke, "SpokesF")
    spokes_r = build_spokes(HUB_R, m_spoke, "SpokesR")
    # decimate and bake
    for o, key in ((frame, "frame"), (steer, "steer"), (wf, "wheel_f"), (wr, "wheel_r")):
        decimate(o, BUDGET[key])
    frame, steer, wf, wr = bake(hi, [frame, steer, wf, wr])
    bpy.data.objects.remove(hi)
    frame.name = frame.data.name = "Frame"; steer.name = steer.data.name = "ForkAndBars"
    wf.name = wf.data.name = "FrontWheelMesh"; wr.name = wr.data.name = "RearWheelMesh"
    for target, extra in ((steer, grips), (wf, spokes_f), (wr, spokes_r)):
        select_only([target, extra], target); bpy.ops.object.join()
    # metres, level, origin between the hubs, tyres on z 0
    k = WHEEL_RADIUS / ((R_F + R_R) / 2)
    tilt = math.atan2(HUB_F[1] - HUB_R[1], HUB_F[0] - HUB_R[0])
    mid = Vector((HUB_X, (HUB_F[0] + HUB_R[0]) / 2, (HUB_F[1] + HUB_R[1]) / 2))
    M = Matrix.Translation((0, 0, WHEEL_RADIUS)) @ Matrix.Scale(k, 4) @ Matrix.Rotation(-tilt, 4, 'X') @ Matrix.Translation(-mid)
    meshes = [frame, saddle, steer, wf, wr]
    for o in meshes:
        o.data.transform(M)
        o.data.update()
    hub_f = M @ Vector((HUB_X, HUB_F[0], HUB_F[1])); hub_r = M @ Vector((HUB_X, HUB_R[0], HUB_R[1]))
    ax_p = M @ Vector(AXIS_P + AXIS_U * ((0.80 - AXIS_P[2]) / AXIS_U[2]))     # mid head tube
    ax_u = (M.to_3x3() @ Vector(AXIS_U)).normalized()
    log("hubs", tuple(round(c, 4) for c in hub_f), tuple(round(c, 4) for c in hub_r), "scale %.4f" % k)
    # rig
    root = bpy.data.objects.new("GrayBicycle", None); bpy.context.scene.collection.objects.link(root)
    pivot = bpy.data.objects.new("SteeringPivot", None); bpy.context.scene.collection.objects.link(pivot)
    pivot.parent = root
    pivot.matrix_world = Matrix.Translation(ax_p) @ Matrix.Rotation(math.atan2(-ax_u.y, ax_u.z), 4, 'X')
    w_front = bpy.data.objects.new("WheelFront", None); bpy.context.scene.collection.objects.link(w_front)
    w_rear = bpy.data.objects.new("WheelRear", None); bpy.context.scene.collection.objects.link(w_rear)
    w_front.parent = pivot; w_rear.parent = root
    bpy.context.view_layer.update()
    w_front.matrix_world = Matrix.Translation(hub_f)
    w_rear.matrix_world = Matrix.Translation(hub_r)
    bpy.context.view_layer.update()
    for o, parent in ((frame, root), (saddle, root), (steer, pivot), (wf, w_front), (wr, w_rear)):
        o.data.transform(parent.matrix_world.inverted())
        o.parent = parent
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Matrix.Identity(4)
        for e in (pivot, w_front, w_rear):
            e.empty_display_type = 'PLAIN_AXES'; e.empty_display_size = 0.1
    bpy.context.view_layer.update()
    allv = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in meshes])
    wheelbase = float(hub_f.y - hub_r.y)
    info = {"path": "res://assets/bicycles/gray_bicycle.glb", "source": "sketchup_assets/woman_riding_a_gray_bicycle.glb",
            "triangles": tris(meshes), "parts": {o.name: tris([o]) for o in meshes},
            "wheelbase": round(wheelbase, 4), "wheel_radius": WHEEL_RADIUS, "scale_from_source": round(k, 4),
            "bbox_min": allv.min(0).round(3).tolist(), "bbox_max": allv.max(0).round(3).tolist(),
            "steering_pivot": [round(c, 4) for c in ax_p], "steering_axis": [round(c, 4) for c in ax_u],
            "head_angle_deg": round(90 - math.degrees(math.atan2(-ax_u.y, ax_u.z)), 1),
            "hub_front": [round(c, 4) for c in hub_f], "hub_rear": [round(c, 4) for c in hub_r],
            "texture": TEX, "facing": "+Y blender / -Z godot"}
    root["wheelbase"] = round(wheelbase, 4)
    root["wheel_radius"] = WHEEL_RADIUS
    root["asset_source"] = "woman_riding_a_gray_bicycle.glb, rider removed (tools/build_gray_bicycle.py)"
    log("info", json.dumps(info))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w") as f:
        json.dump(info, f, indent=2)
    select_only([root, pivot, w_front, w_rear] + meshes, root)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=False, export_animations=False, export_image_format='JPEG',
                              export_jpeg_quality=90, export_materials='EXPORT', export_extras=True)
    log("wrote", OUT, "%.2f MB" % (os.path.getsize(OUT) / 1e6))
    # The removed rider, kept as a static prop that sits exactly on this bicycle (NPC cyclists).
    rider_hi = rider.copy(); rider_hi.data = rider.data.copy(); bpy.context.scene.collection.objects.link(rider_hi)
    decimate(rider, RIDER_BUDGET)
    rider = bake(rider_hi, [rider], "GrayBicycleRider")[0]
    bpy.data.objects.remove(rider_hi)
    rider.name = rider.data.name = "RiderMesh"
    rider.data.transform(M)
    rroot = bpy.data.objects.new("GrayBicycleRider", None); bpy.context.scene.collection.objects.link(rroot)
    rider.parent = rroot
    rroot["asset_source"] = "woman_riding_a_gray_bicycle.glb, rider only, pose fits gray_bicycle.glb"
    info["rider_triangles"] = tris([rider])
    with open(REPORT, "w") as f:
        json.dump(info, f, indent=2)
    select_only([rroot, rider], rroot)
    bpy.ops.export_scene.gltf(filepath=OUT_RIDER, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=False, export_animations=False, export_image_format='JPEG',
                              export_jpeg_quality=90, export_materials='EXPORT', export_extras=True)
    log("wrote", OUT_RIDER, "%.2f MB" % (os.path.getsize(OUT_RIDER) / 1e6), "rider tris", tris([rider]))
    if DO_QA:
        qa()


# ----------------------------------------------------------------------------- QA
def qa():
    os.makedirs(QA_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=OUT)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_shadows = False
    sc.display.shading.show_cavity = True
    sc.render.resolution_x = sc.render.resolution_y = 900
    w = bpy.data.worlds.new("W"); sc.world = w; w.color = (0.34, 0.36, 0.40)
    for mat in bpy.data.materials:
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
                    mat.node_tree.nodes.active = n
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.clip_end = 100
    for o in bpy.data.objects:
        if o.type == 'EMPTY':
            log("  QA node", o.name, "parent", o.parent.name if o.parent else None,
                tuple(round(c, 3) for c in o.matrix_world.translation), tuple(round(c, 3) for c in o.matrix_world.to_euler()))

    def shoot(name, d, target=(0, 0, 0.55), ortho=2.0):
        d = Vector(d).normalized()
        cam.location = Vector(target) + d * 10
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = ortho
        sc.render.filepath = os.path.join(QA_DIR, name + ".png")
        bpy.ops.render.render(write_still=True)
    shoot("side_right", (1, 0, 0))
    shoot("side_left", (-1, 0, 0))
    shoot("front_34", (0.75, 0.75, 0.35))
    shoot("rear_34", (-0.7, -0.7, 0.4))
    shoot("front", (0, 1, 0.08), ortho=1.4)
    shoot("top", (0, 0.0001, 1))
    shoot("cockpit", (0.0, -0.55, 1.0), target=(0, 0.35, 0.95), ortho=0.9)
    # rig check: steer 25 deg left about the pivot's local axis, spin both wheels 40 deg
    pv = bpy.data.objects["SteeringPivot"]
    pv.rotation_mode = 'XYZ'
    pv.matrix_basis = pv.matrix_basis @ Matrix.Rotation(math.radians(25), 4, 'Z')
    for n in ("WheelFront", "WheelRear"):
        wn = bpy.data.objects[n]; wn.matrix_basis = wn.matrix_basis @ Matrix.Rotation(math.radians(40), 4, 'X')
    bpy.context.view_layer.update()
    shoot("rig_steer25_spin40_top", (0, 0.0001, 1))
    shoot("rig_steer25_spin40_34", (0.75, 0.75, 0.35))
    shoot("rig_steer25_spin40_side", (1, 0, 0))
    # the NPC variant: the extracted rider on the bicycle (must sit on saddle, bars and pedals)
    old = bpy.data.objects["GrayBicycle"]
    for o in [old] + list(old.children_recursive):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.gltf(filepath=OUT)
    bpy.ops.import_scene.gltf(filepath=OUT_RIDER)
    for mat in bpy.data.materials:
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
                    mat.node_tree.nodes.active = n
    shoot("rider_side", (1, 0, 0), target=(0, 0, 0.85), ortho=2.0)
    shoot("rider_34", (0.75, 0.75, 0.35), target=(0, 0, 0.85), ortho=2.2)


main()
