"""Riderless gray bicycle extracted from the supplied "woman riding a gray bicycle" model.

blender --background --factory-startup --python tools/build_gray_bicycle.py [-- noqa]
blender ... tools/build_gray_bicycle.py -- drivetrain [noqa]   only the drivetrain stage, applied to
    assets/bicycles/archive/v1/gray_bicycle.glb (the pre-drivetrain bike, backed up on first run)
blender ... tools/build_gray_bicycle.py -- dryrun [noqa]        full rebuild into tmp/bike_dryrun/

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
Drivetrain stage (drivetrain_stage, end of main()): the scanned crank (one pedal floating above
the bottom bracket, the other crank a rod fused to the down tube), chainring shards and the
rotor/cassette shards at the rear hub are cut away; modelled instead: 42T chainring + 5-arm
spider + 172.5 mm crank arms + spindle, platform pedals (100 x 90 x 20 mm, pins), a 7-speed
internal-gear rear hub with roller brake and 18T cog, a chain loop on a 54 mm chainline, BB cups,
an eccentric-BB shell and a down-tube sleeve (frame paint) over the torn junction. Added nodes:
    Crank            empty at the BB axis, child of the root, identity rotation; turns about local X.
                     At rest the RIGHT crank points forward (Godot -Z), the left one back.
                     Forward pedalling = negative rotation about X (Godot rotation.x decreasing).
      CrankMesh      ring, spider, arms, spindle, bolts, pedal spindles
      PedalL/PedalR  empties at the pedal spindle centres (rider's left = -X)
        PedalL_Body / PedalR_Body   origin on the spindle: set PedalX.rotation.x = -Crank.rotation.x
    Seat             top of the saddle at the sit bones (SEAT_BACK forward of its rear edge)
    SteeringPivot/GripL, SteeringPivot/GripR   grip centres (turn with the bars)
    Chain            static chain loop (on the root)
Root extras add crank_length, seat_height, bb_height. SADDLE_RAISE moves the saddle, the Seat
marker and the seat post up/down along the seat-tube axis.
QA renders: world/vehicles/production/renders/gray_bicycle/ (incl. drivetrain_*, crank_*, rear_hub_*).
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
if "dryrun" in ARGS:   # full rebuild into tmp/bike_dryrun (checks the pipeline without touching assets)
    OUT_DIR = os.path.join(ROOT, "tmp", "bike_dryrun")
    OUT = os.path.join(OUT_DIR, "gray_bicycle.glb")
    OUT_RIDER = os.path.join(OUT_DIR, "gray_bicycle_rider.glb")
    QA_DIR = os.path.join(OUT_DIR, "renders")
    REPORT = os.path.join(OUT_DIR, "gray_bicycle.json")
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
    mat.diffuse_color = (*color, 1)     # workbench QA renders show the viewport colour
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


# ----------------------------------------------------------------------------- drivetrain
# Everything below works in the finished bicycle's space: metres, +Y forward (Godot -Z), +X =
# rider's right (drive side), ground at z 0. The scanned crank was one pedal floating above the
# bottom bracket and a rod for the other crank, so the whole drivetrain is modelled instead.
BB_Y, BB_Z = -0.155, 0.273      # bottom-bracket axis (circle fits to the scanned shell ends + chainring)
CRANK_LEN = 0.1725              # BB axis -> pedal spindle (172.5 mm)
CHAINLINE = 0.054               # chainring / rear cog plane (x); the scanned chainstays flare to ~x 0.05 behind the BB
ARM_X = (0.064, 0.078)          # right crank arm faces (left arm mirrored, 2 mm further out: no spider)
PEDAL_X = 0.146                 # pedal body centre (x), i.e. 292 mm between pedal centres
RING_TEETH, COG_TEETH = 42, 18  # 1/2" pitch chain; 7-speed internal hub (one rear cog)
PITCH = 0.0127
SADDLE_RAISE = -0.050           # down (-) / up (+) along the seat-tube axis (m): -5 cm fits the courier (tools/prepare_player.py fit) and clears the downtown bike racks
SEAT_BACK = 0.085               # Seat marker: this far forward of the saddle's rear edge (sit bones)
for _a in ARGS:                 # "raise=0.03" overrides SADDLE_RAISE for a test build
    if _a.startswith("raise="):
        SADDLE_RAISE = float(_a.split("=", 1)[1])


def final_transform():
    """Source -> finished bicycle space (same as main(): metres, level, tyres on z 0)."""
    k = WHEEL_RADIUS / ((R_F + R_R) / 2)
    tilt = math.atan2(HUB_F[1] - HUB_R[1], HUB_F[0] - HUB_R[0])
    mid = Vector((HUB_X, (HUB_F[0] + HUB_R[0]) / 2, (HUB_F[1] + HUB_R[1]) / 2))
    return Matrix.Translation((0, 0, WHEEL_RADIUS)) @ Matrix.Scale(k, 4) @ Matrix.Rotation(-tilt, 4, 'X') @ Matrix.Translation(-mid)


def get_material(name, color, metallic, roughness):
    mat = bpy.data.materials.get(name)
    return mat if mat else material(name, color, metallic, roughness)


def yz(r, a):
    return r * math.cos(a), r * math.sin(a)


def inset(outline, d):
    """Offset a CCW (y, z) outline inwards by d."""
    n = len(outline)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(outline[i - 1]), Vector(outline[i]), Vector(outline[(i + 1) % n])
        e0, e1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        nin = Vector((-e0.y, e0.x)) + Vector((-e1.y, e1.x))
        out.append(tuple(p1 + nin.normalized() * d) if nin.length > 1e-9 else tuple(p1))
    return out


def prism(bm, outline, x0, x1, c=(0.0, 0.0), chamfer=0.0):
    """Extrude a CCW (y, z) outline (relative to centre c) along X from x0 to x1, optionally
    with chamfered edges (inset end rings)."""
    if chamfer > 0:
        layers = [(x0, inset(outline, chamfer)), (x0 + chamfer, outline), (x1 - chamfer, outline), (x1, inset(outline, chamfer))]
    else:
        layers = [(x0, outline), (x1, outline)]
    rings = [[bm.verts.new((x, c[0] + p[0], c[1] + p[1])) for p in ol] for x, ol in layers]
    n = len(outline)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((ra[i], ra[(i + 1) % n], rb[(i + 1) % n], rb[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def ring_prism(bm, outer, inner, x0, x1, c=(0.0, 0.0)):
    """Flat ring between two CCW outlines with the same point count, extruded along X."""
    n = len(outer)
    o0 = [bm.verts.new((x0, c[0] + p[0], c[1] + p[1])) for p in outer]
    o1 = [bm.verts.new((x1, c[0] + p[0], c[1] + p[1])) for p in outer]
    i0 = [bm.verts.new((x0, c[0] + p[0], c[1] + p[1])) for p in inner]
    i1 = [bm.verts.new((x1, c[0] + p[0], c[1] + p[1])) for p in inner]
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((o0[k], o0[j], o1[j], o1[k]))      # outer wall
        bm.faces.new((i1[k], i1[j], i0[j], i0[k]))      # inner wall
        bm.faces.new((o1[k], o1[j], i1[j], i1[k]))      # +x face
        bm.faces.new((i0[k], i0[j], o0[j], o0[k]))      # -x face


def x_cylinder(bm, x0, x1, c, r, segs=12):
    """Cylinder along X between x0 and x1 centred on (y, z) = c."""
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=abs(x1 - x0),
                          matrix=Matrix.Translation(((x0 + x1) / 2, c[0], c[1])) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))


def box(bm, centre, size):
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*size, 1)))


def circle(r, n, a0=0.0):
    return [yz(r, a0 + 2 * math.pi * i / n) for i in range(n)]


def toothed(teeth, r_root, r_tip, a0=0.0):
    """Gear outline: per tooth a root point and a (slightly flattened) tip pair."""
    out = []
    p = 2 * math.pi / teeth
    for i in range(teeth):
        a = a0 + i * p
        out += [yz(r_root, a), yz(r_tip, a + 0.38 * p), yz(r_tip, a + 0.62 * p)]
    return out


def stadium(c1, r1, c2, r2, n1=12, n2=8):
    """CCW outline around two circles (big end c1, small end c2) joined by tangent lines."""
    c1, c2 = Vector(c1), Vector(c2)
    d = c2 - c1
    th = math.atan2(d.y, d.x)
    al = math.acos((r1 - r2) / d.length)
    out = [tuple(c1 + Vector(yz(r1, th + al + (2 * math.pi - 2 * al) * i / n1))) for i in range(n1 + 1)]
    out += [tuple(c2 + Vector(yz(r2, th - al + 2 * al * i / n2))) for i in range(n2 + 1)]
    return out


def star(arms, r_hub, r_tip, w_root, w_tip, r_valley, a0=0.0):
    out = []
    for k in range(arms):
        a = a0 + 2 * math.pi * k / arms
        ar, at = math.asin(min(0.95, w_root / r_hub)), math.asin(w_tip / r_tip)
        out += [yz(r_hub, a - ar), yz(r_tip, a - at), yz(r_tip, a + at), yz(r_hub, a + ar),
                yz(r_valley, a + math.pi / arms)]
    return out


def finish_mesh(name, bm, mat, smooth_axis_walls=False):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = mesh_object(name, bm, mat)
    for p in o.data.polygons:   # cylinder walls smooth, flat caps / gear flanks
        p.use_smooth = smooth_axis_walls and abs(p.normal.x) < 0.2
    return o


def chain_path(c1, r1, c2, r2):
    """Closed chain centre-line (y, z) around the chainring (c1, r1) and the rear cog (c2, r2)."""
    c1, c2 = Vector(c1), Vector(c2)
    d = c2 - c1
    phi = math.atan2(d.y, d.x)
    beta = math.acos((r1 - r2) / d.length)
    a_top, a_bot = phi + beta, phi - beta          # normals of the two straight runs
    if math.sin(a_top) < math.sin(a_bot):
        a_top, a_bot = a_bot, a_top

    def arc(c, r, a, b, through, n):
        tau = 2 * math.pi
        s = 1 if ((through - a) % tau) < ((b - a) % tau) else -1
        span = ((b - a) * s) % tau
        return [tuple(c + Vector(yz(r, a + s * span * i / n))) for i in range(n + 1)]

    pts = arc(c2, r2, a_top, a_bot, phi, 12)[:-1]                     # around the cog (rear side)
    p_bot2, p_bot1 = c2 + Vector(yz(r2, a_bot)), c1 + Vector(yz(r1, a_bot))
    pts += [tuple(p_bot2.lerp(p_bot1, t / 8)) for t in range(8)]       # lower run
    pts += arc(c1, r1, a_bot, a_top, phi + math.pi, 24)[:-1]          # around the chainring (front)
    p_top1, p_top2 = c1 + Vector(yz(r1, a_top)), c2 + Vector(yz(r2, a_top))
    pts += [tuple(p_top1.lerp(p_top2, t / 8)) for t in range(8)]       # upper run
    return pts


def build_chain(mat, x_ring, x_cog, hub):
    r1 = PITCH / (2 * math.sin(math.pi / RING_TEETH))
    r2 = PITCH / (2 * math.sin(math.pi / COG_TEETH))
    pts = chain_path((BB_Y, BB_Z), r1, hub, r2)
    bm = bmesh.new()
    n = len(pts)
    rings = []
    y0, y1 = hub[0], BB_Y
    for i, p in enumerate(pts):
        a, b = Vector(pts[i - 1]), Vector(pts[(i + 1) % n])
        t = (b - a).normalized()
        nn = Vector((-t.y, t.x))                       # in-plane normal
        x = x_cog + (x_ring - x_cog) * min(1.0, max(0.0, (p[0] - y0) / (y1 - y0)))
        hw, hh = 0.0037, 0.0041
        rings.append([bm.verts.new((x + sx * hw, p[0] + nn.x * sz * hh, p[1] + nn.y * sz * hh))
                      for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for i in range(n):
        ra, rb = rings[i], rings[(i + 1) % n]
        for k in range(4):
            bm.faces.new((ra[k], ra[(k + 1) % 4], rb[(k + 1) % 4], rb[k]))
    o = finish_mesh("Chain", bm, mat)
    return o, r1, r2


def sample_paint(o, face_mask):
    """Mean base colour, metallic and roughness of the faces in face_mask from o's baked atlas."""
    me = o.data
    nt = me.materials[0].node_tree
    def img_for(pred):
        return next((n.image for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image and any(pred(l) for l in n.outputs[0].links)), None)
    col = img_for(lambda l: l.to_socket.name == "Base Color")
    orm = img_for(lambda l: l.to_node.type == 'SEPARATE_COLOR')
    lt = np.empty(len(me.polygons), int); me.polygons.foreach_get("loop_total", lt)
    lf = np.repeat(np.arange(len(lt)), lt)
    uv = np.empty(len(me.loops) * 2); me.uv_layers.active.data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)[face_mask[lf]]

    def mean(im):
        W, H = im.size
        px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); px = px.reshape(H, W, 4)
        xs = np.clip((uv[:, 0] % 1.0) * W, 0, W - 1).astype(int); ys = np.clip((uv[:, 1] % 1.0) * H, 0, H - 1).astype(int)
        return np.median(px[ys, xs, :3], axis=0)
    c = mean(col) if col is not None and len(uv) else np.array([0.55, 0.55, 0.55])
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)     # sRGB texels -> linear factor
    mr = mean(orm) if orm is not None and len(uv) else np.array([1.0, 0.45, 0.6])
    log("drivetrain: frame paint sampled from %d loops: colour %s metallic %.2f roughness %.2f" % (len(uv), c.round(3), mr[2], mr[1]))
    return tuple(float(v) for v in c), float(mr[2]), float(mr[1])


def drivetrain_stage(root, pivot, w_rear, frame, saddle, steer, rear_mesh):
    """Replace the scanned crank/pedals with a modelled drivetrain, rebuild the rear hub
    (7-speed internal hub, 18T cog, disc rotor), add the Seat / GripL / GripR markers and the
    optional saddle height change. All objects are in their final parents' space on entry."""
    m_crank = get_material("GrayBicycle_Crank", (0.025, 0.025, 0.027), 0.6, 0.4)
    m_steel = get_material("GrayBicycle_Steel", (0.62, 0.62, 0.64), 0.9, 0.28)
    m_chain = get_material("GrayBicycle_Chain", (0.13, 0.13, 0.135), 0.85, 0.45)
    m_pedal = get_material("GrayBicycle_Pedal", (0.028, 0.028, 0.03), 0.0, 0.65)
    bb = (BB_Y, BB_Z)
    # 1. scanned crank, chainring, pedals and the floating pedal: everything outboard of the BB
    #    shell around the bottom bracket, except the chainstays.
    hub_r = w_rear.matrix_world.translation
    lt, cen = face_arrays(frame.data)
    P = cen[:, 1:] - np.array(bb)
    d = np.array([hub_r.y - BB_Y, hub_r.z - BB_Z]); L = np.linalg.norm(d); u = d / L
    t = P @ u; h = P @ np.array([-u[1], u[0]])
    r = np.linalg.norm(P, axis=1)
    x, y, z = cen[:, 0], cen[:, 1], cen[:, 2]
    stay = (np.abs(h) < 0.024) & (t > 0.035) & (np.abs(x) < 0.057)
    # the down tube (fat, ~45 mm) and the seat tube also meet the shell: keep their surfaces
    fv = verts(frame)
    bbv = np.array([0.0, BB_Y, BB_Z])
    dt_pts = fv[(np.abs(fv[:, 0]) < 0.012) & (fv[:, 1] > -0.08) & (fv[:, 1] < 0.2) & (fv[:, 2] > 0.3) & (fv[:, 2] < 0.7)]
    dt_dir = np.array([0.0, *np.polyfit(dt_pts[:, 1], dt_pts[:, 2], 1)[:1]]); dt_dir = np.array([0, 1.0, dt_dir[1]]); dt_dir /= np.linalg.norm(dt_dir)
    dt_c = np.array([0.0, dt_pts[:, 1].mean(), dt_pts[:, 2].mean()])
    st_dir = np.array(final_transform() @ SEAT_CLAMP) - bbv; st_dir /= np.linalg.norm(st_dir)

    def line_dist(pts, c, u):
        rel = pts - c
        return np.linalg.norm(rel - np.outer(rel @ u, u), axis=1)
    # the down tube is oval: half height b from its top/bottom surface points, half width a from
    # its side points; the scanned rod hangs just outside that ellipse
    n_dt = np.array([0.0, -dt_dir[2], dt_dir[1]])
    b_dt = float(np.median(np.abs((dt_pts - dt_c) @ n_dt)))
    side = fv[(np.abs((fv - dt_c) @ n_dt) < 0.006) & ((fv - dt_c) @ dt_dir > -0.25) & ((fv - dt_c) @ dt_dir < 0.1)]
    a_dt = float(np.percentile(np.abs(side[:, 0]), 90)) if len(side) else 0.04
    ell = (np.abs(cen[:, 0]) / (a_dt + 0.006)) ** 4 + (np.abs((cen - dt_c) @ n_dt) / (b_dt + 0.008)) ** 4   # rounded box
    tubes = (ell < 1.0) | ((line_dist(cen, bbv, st_dir) < 0.032) & ((cen - bbv) @ st_dir > 0.02))
    log("drivetrain: down tube axis through %s dir %s, half width %.3f half height %.3f" % (dt_c.round(3), dt_dir.round(3), a_dt, b_dt))
    # right: crank, chainring and chain outboard of the shell; left: the crank arm (|x| > 48 mm)
    # (the wide down-tube / shell junction on the left is kept)
    rod_low = (np.abs(x) > 0.010) & (y > -0.12) & (y < -0.015) & (r > 0.08) & ~tubes   # scanned crank rods under the tube
    crank = (r < 0.245) & ~stay & (((x > 0.034) & ~(tubes & (x < 0.05))) | (x < -0.058) | rod_low)
    crank |= (r < 0.245) & (z < 0.205) & (y > -0.215)                      # shards under the BB
    # the left scanned "crank" rod rising beside the down tube: everything left of the tube and above its top
    z_top = dt_c[2] + (y - dt_c[1]) * dt_dir[2] / dt_dir[1] + b_dt / dt_dir[1]      # tube top at y
    rod = (y > -0.115) & (y < -0.04) & (z > z_top + 0.012) & (z < 0.56) & (x < -0.024)
    crank |= rod & ~tubes
    # rear dropouts: the scan's rotor / caliper shards between the dropouts (the hub is rebuilt)
    crank |= (np.hypot(y - hub_r.y, z - hub_r.z) < 0.14) & (np.abs(x) < 0.054)
    # decimated slivers: long triangles from the tube down to the rods' lower ends (centres on the tube)
    fvo = np.array([v.co[:] for v in frame.data.vertices])
    z_bot = dt_c[2] + (fvo[:, 1] - dt_c[1]) * dt_dir[2] / dt_dir[1] - b_dt / dt_dir[1]   # tube underside
    low = (fvo[:, 1] > -0.135) & (fvo[:, 1] < 0.0) & (fvo[:, 2] < z_bot - 0.006) & (np.abs(fvo[:, 0]) > 0.01)
    lt2 = np.empty(len(frame.data.polygons), int); frame.data.polygons.foreach_get("loop_total", lt2)
    lv = np.empty(len(frame.data.loops), int); frame.data.loops.foreach_get("vertex_index", lv)
    crank |= np.add.reduceat(low[lv].astype(int), np.r_[0, np.cumsum(lt2)[:-1]]) > 0
    log("drivetrain: removing %d scanned crank/pedal faces" % int(crank.sum()))
    delete_faces(frame, crank)
    # small scan fragments (rotor / spoke remnants) hanging around the rear dropouts. Connectivity
    # is judged on a welded copy (an imported GLB is split along every UV seam).
    from mathutils.kdtree import KDTree
    bm = bmesh.new(); bm.from_mesh(frame.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.verts.ensure_lookup_table()
    seen = set(); junk = []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        stack = [v0]; seen.add(v0.index); ids = []
        while stack:
            v = stack.pop(); ids.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index); stack.append(w)
        if len(ids) < 60 and all(math.hypot(v.co.y - hub_r.y, v.co.z - hub_r.z) < 0.32 for v in ids):
            junk += [v.co.copy() for v in ids]
    bm.free()
    if junk:
        kd = KDTree(len(junk))
        for i, co in enumerate(junk):
            kd.insert(co, i)
        kd.balance()
        bm = bmesh.new(); bm.from_mesh(frame.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if kd.find(v.co)[2] < 2e-5], context='VERTS')
        bm.to_mesh(frame.data); bm.free()
    log("drivetrain: removed %d fragment vertices at the rear dropouts" % len(junk))
    # BB cups (static, part of the frame)
    bm = bmesh.new()
    for s in (-1, 1):
        x_cylinder(bm, s * 0.031, s * 0.0385, bb, 0.0255, 20)          # shell end cap
        x_cylinder(bm, s * 0.0385, s * 0.042, bb, 0.0215, 20)          # bearing cup
    cups = finish_mesh("BBCups", bm, m_crank, True)
    # The crank rods were scanned fused to the down-tube / shell junction; with them gone the
    # junction is torn. Wrap it in a modelled eccentric-BB shell and a down-tube sleeve painted
    # like the frame (colour / metal / roughness sampled from the frame's own atlas).
    lt, cen2 = face_arrays(frame.data)
    paint = sample_paint(frame, np.ones(len(cen2), bool))          # median over the whole frame
    m_paint = get_material("GrayBicycle_FramePaint", paint[0], paint[1], paint[2])
    bm = bmesh.new()
    x_cylinder(bm, -0.040, 0.040, bb, 0.031, 28)                                    # eccentric BB shell
    p_far = dt_c + dt_dir * ((BB_Y + 0.15 - dt_c[1]) / dt_dir[1])     # on the fitted tube axis
    p_bb = bbv
    rings = []
    n_sec = 20
    for k, (t, grow) in enumerate(((0.0, 0.004), (0.35, 0.004), (0.7, 0.003), (0.92, 0.0015), (1.0, -0.004))):
        c = p_bb + (p_far - p_bb) * t
        ring_v = []
        for j in range(n_sec):
            a = 2 * math.pi * j / n_sec
            ca, sa = math.cos(a), math.sin(a)
            u = math.copysign(abs(ca) ** 0.5, ca) * (a_dt + grow)        # superellipse (rounded box)
            v = math.copysign(abs(sa) ** 0.5, sa) * (b_dt + grow)
            ring_v.append(bm.verts.new(tuple(c + np.array([u, 0, 0]) + n_dt * v)))
        rings.append(ring_v)
    for ra, rb in zip(rings, rings[1:]):
        for j in range(n_sec):
            bm.faces.new((ra[j], ra[(j + 1) % n_sec], rb[(j + 1) % n_sec], rb[j]))
    bm.faces.new(list(reversed(rings[0])))
    sleeve = finish_mesh("BBSleeve", bm, m_paint)
    for p in sleeve.data.polygons:
        p.use_smooth = True
    select_only([frame, cups, sleeve], frame); bpy.ops.object.join()

    # 2. crank assembly at rest: RIGHT arm forward (+Y), left arm back.
    parts = []
    bm = bmesh.new()
    r_ring = PITCH / (2 * math.sin(math.pi / RING_TEETH))
    ring_out = toothed(RING_TEETH, r_ring - 0.0042, r_ring + 0.0045)
    ring_prism(bm, ring_out, circle(0.0655, len(ring_out)), CHAINLINE - 0.00175, CHAINLINE + 0.00175, bb)
    prism(bm, star(5, 0.024, 0.0725, 0.011, 0.0065, 0.026), CHAINLINE + 0.0018, ARM_X[0] + 0.001, bb, 0.0012)
    prism(bm, stadium((0, 0), 0.0185, (CRANK_LEN, 0), 0.0125), ARM_X[0], ARM_X[1], bb, 0.0025)
    prism(bm, stadium((0, 0), 0.0185, (-CRANK_LEN, 0), 0.0125), -ARM_X[1] - 0.002, -ARM_X[0] - 0.002, bb, 0.0025)
    parts.append(finish_mesh("CrankArms", bm, m_crank))
    bm = bmesh.new()
    x_cylinder(bm, -ARM_X[0] - 0.002, ARM_X[0], bb, 0.012, 16)                      # spindle
    for s, xa in ((1, ARM_X[1]), (-1, -ARM_X[1] - 0.002)):
        x_cylinder(bm, xa, xa + s * 0.0025, bb, 0.0095, 16)                           # crank bolt caps
        x_cylinder(bm, xa, s * (PEDAL_X - 0.04), (BB_Y + s * CRANK_LEN, BB_Z), 0.0062, 10)   # pedal spindles
    for k in range(5):                                                                 # chainring bolts
        c = Vector(bb) + Vector(yz(0.0685, 2 * math.pi * k / 5))
        x_cylinder(bm, CHAINLINE - 0.0035, ARM_X[0] - 0.003, c, 0.0042, 8)
    parts.append(finish_mesh("CrankSteel", bm, m_steel, True))
    select_only(parts, parts[0]); bpy.ops.object.join()
    crank_mesh = bpy.context.view_layer.objects.active
    crank_mesh.name = crank_mesh.data.name = "CrankMesh"

    # 3. platform pedals: 100 x 90 x 20 mm, origin on the spindle axis
    def pedal(name, side):
        bm = bmesh.new()
        for sy in (-1, 1):
            box(bm, (0, sy * 0.045, 0), (0.090, 0.010, 0.020))                   # front / rear cage
        for sx in (-1, 1):
            box(bm, (sx * 0.040, 0, 0), (0.010, 0.082, 0.015))                   # end plates
        x_cylinder(bm, -0.045, 0.045, (0, 0), 0.0105, 12)                        # spindle housing
        for sy in (-1, 1):                                                         # cross webs
            box(bm, (0, sy * 0.022, 0), (0.072, 0.004, 0.012))
        body = finish_mesh(name, bm, m_pedal)
        bm = bmesh.new()
        for sy in (-1, 1):
            for sx in (-0.028, 0.0, 0.028):
                for sz in (-1, 1):
                    box(bm, (sx, sy * 0.045, sz * 0.0115), (0.003, 0.003, 0.004))  # traction pins
        pins = finish_mesh(name + "Pins", bm, m_steel)
        select_only([body, pins], body); bpy.ops.object.join()
        return body

    # 4. hierarchy: Crank (empty at the BB axis, identity rotation, turns about local X)
    def empty(name, parent, at):
        e = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(e)
        e.empty_display_type = 'PLAIN_AXES'; e.empty_display_size = 0.05
        e.parent = parent
        e.matrix_world = Matrix.Translation(at)
        return e

    crank = empty("Crank", root, Vector((0, BB_Y, BB_Z)))
    bpy.context.view_layer.update()
    crank_mesh.data.transform(crank.matrix_world.inverted())
    crank_mesh.parent = crank; crank_mesh.matrix_parent_inverse = Matrix.Identity(4); crank_mesh.matrix_basis = Matrix.Identity(4)
    pedals = {}
    for name, s in (("PedalR", 1), ("PedalL", -1)):
        e = empty(name, crank, Vector((s * PEDAL_X, BB_Y + s * CRANK_LEN, BB_Z)))
        body = pedal(name + "_Body", s)
        body.parent = e; body.matrix_parent_inverse = Matrix.Identity(4); body.matrix_basis = Matrix.Identity(4)
        pedals[name] = e

    # 5. rear hub: the scan left a hole with rotor/cassette shards; 7-speed internal-gear hub,
    #    18T cog on the chainline, 160 mm disc rotor on the left (spokes are kept).
    me = rear_mesh.data
    lt, cen = face_arrays(me)
    mi = np.empty(len(me.polygons), int); me.polygons.foreach_get("material_index", mi)
    spoke_slot = [i for i, m in enumerate(me.materials) if m and m.name.startswith("GrayBicycle_Spokes")]
    # everything inside the rim except the regenerated spokes (rim inner edge: RIM_IN * scale = 0.288)
    hub_junk = (np.hypot(cen[:, 1], cen[:, 2]) < 0.278) & (np.abs(cen[:, 0]) < 0.07) & ~np.isin(mi, spoke_slot)
    log("drivetrain: rear hub shards removed: %d faces" % int(hub_junk.sum()))
    delete_faces(rear_mesh, hub_junk)
    o = (0.0, 0.0)
    bm = bmesh.new()
    x_cylinder(bm, -0.032, 0.031, o, 0.027, 20)                                     # hub shell
    for s in (-1, 1):
        x_cylinder(bm, s * 0.024 - 0.002, s * 0.024 + 0.002, o, 0.035, 20)         # spoke flanges
    x_cylinder(bm, 0.031, CHAINLINE - 0.001, o, 0.019, 16)                          # cog carrier
    x_cylinder(bm, -0.046, -0.032, o, 0.040, 24)                                    # roller-brake drum
    for k in range(4):                                                               # cooling fins
        xf = -0.0445 + 0.0034 * k
        x_cylinder(bm, xf, xf + 0.0012, o, 0.046, 24)
    # brake reaction arm along the left chainstay (towards the BB)
    ca = math.atan2(BB_Z - hub_r.z, BB_Y - hub_r.y)
    arm = stadium((0, 0), 0.016, (0.11 * math.cos(ca), 0.11 * math.sin(ca)), 0.007, 8, 6)
    prism(bm, arm, -0.052, -0.047, o, 0.001)
    hub_parts = [finish_mesh("RearHub", bm, m_crank, True)]   # 7-speed internal hub + roller brake
    bm = bmesh.new()
    r_cog = PITCH / (2 * math.sin(math.pi / COG_TEETH))
    cog = toothed(COG_TEETH, r_cog - 0.0040, r_cog + 0.0040)
    ring_prism(bm, cog, circle(0.0185, len(cog)), CHAINLINE - 0.0012, CHAINLINE + 0.0012)
    x_cylinder(bm, -0.068, 0.068, o, 0.0055, 10)                                    # axle + nuts
    for s in (-1, 1):
        x_cylinder(bm, s * 0.058, s * 0.066, o, 0.0085, 6)
    hub_parts.append(finish_mesh("RearHubSteel", bm, m_steel))
    for o in hub_parts:   # built around the hub centre: place them at the hub before joining
        o.data.transform(rear_mesh.matrix_world)
    select_only([rear_mesh] + hub_parts, rear_mesh); bpy.ops.object.join()
    rear_mesh = bpy.context.view_layer.objects.active

    # 6. chain (static, on the root): chainring -> 18T cog
    hub_pos = (hub_r.y, hub_r.z)
    chain, r1, r2 = build_chain(m_chain, CHAINLINE, CHAINLINE, hub_pos)
    chain.parent = root; chain.matrix_parent_inverse = root.matrix_world.inverted()

    # 7. saddle height (along the seat-tube axis) and the Seat marker
    clamp = final_transform() @ SEAT_CLAMP
    axis = (clamp - Vector((0, BB_Y, BB_Z))).normalized()
    if abs(SADDLE_RAISE) > 1e-6:
        off = axis * SADDLE_RAISE
        saddle.data.transform(Matrix.Translation(off))
        # the seat post above the frame's seat collar stretches with it
        fv = verts(frame)
        rel = fv - np.array(clamp)
        along = rel @ np.array(axis)
        radial = np.linalg.norm(rel - np.outer(along, np.array(axis)), axis=1)
        post = (along > -0.045) & (radial < 0.03)
        for i in np.nonzero(post)[0]:
            frame.data.vertices[int(i)].co += off
        log("saddle raised %.3f m along the seat tube (%d seat-post vertices moved)" % (SADDLE_RAISE, int(post.sum())))
    S = np.array([saddle.matrix_world @ v.co for v in saddle.data.vertices])
    y_sit = S[:, 1].min() + SEAT_BACK
    top = S[(np.abs(S[:, 0]) < 0.02) & (np.abs(S[:, 1] - y_sit) < 0.015)]
    seat_pos = Vector((0.0, y_sit, float(top[:, 2].max())))
    seat = empty("Seat", root, seat_pos)

    # 8. grip centres (on the SteeringPivot: they turn with the bars)
    me = steer.data
    gslot = [i for i, m in enumerate(me.materials) if m and m.name.startswith("GrayBicycle_Grip")]
    mi = np.empty(len(me.polygons), int); me.polygons.foreach_get("material_index", mi)
    gv = sorted({v for p in me.polygons if p.material_index in gslot for v in p.vertices})
    G = np.array([steer.matrix_world @ me.vertices[i].co for i in gv])
    grips = {}
    for name, s in (("GripL", -1), ("GripR", 1)):
        side = G[G[:, 0] * s > 0]
        c = side.mean(0)
        _, _, vt = np.linalg.svd(side - c)
        grips[name] = (Vector(c), Vector(vt[0] if vt[0][0] * s > 0 else -vt[0]))
        e = empty(name, pivot, Vector(c))
    bpy.context.view_layer.update()
    info = {
        "crank_length": CRANK_LEN, "bb_height": BB_Z, "bb": [0.0, BB_Y, BB_Z],
        "seat_height": round(seat_pos.z, 4), "seat": [round(c, 4) for c in seat_pos],
        "seat_to_bb": round((seat_pos - Vector((0, BB_Y, BB_Z))).length, 4),
        "seat_tube_axis": [round(c, 4) for c in axis], "saddle_raise": SADDLE_RAISE,
        "pedal_centre_x": PEDAL_X, "chainline": CHAINLINE, "chainring_teeth": RING_TEETH, "cog_teeth": COG_TEETH,
        "grips": {k: {"centre": [round(c, 4) for c in v[0]], "axis_outward": [round(c, 4) for c in v[1]]} for k, v in grips.items()},
    }
    root["crank_length"] = CRANK_LEN
    root["seat_height"] = round(seat_pos.z, 4)
    root["bb_height"] = BB_Z
    log("drivetrain info", json.dumps(info))
    return info, rear_mesh


def export_bike(root):
    """Export via a temp file: the open Godot editor briefly locks the GLB while it reimports."""
    import shutil, time
    select_only([root] + list(root.children_recursive), root)
    tmp = os.path.join(ROOT, "tmp", "gray_bicycle_export.glb")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=tmp, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=False, export_animations=False, export_image_format='JPEG',
                              export_jpeg_quality=90, export_materials='EXPORT', export_extras=True)
    for attempt in range(60):
        try:
            shutil.copyfile(tmp, OUT)
            break
        except OSError:
            time.sleep(1.0)
    else:
        raise RuntimeError("could not write " + OUT)
    os.remove(tmp)
    log("wrote", OUT, "%.2f MB" % (os.path.getsize(OUT) / 1e6))


def godot_xyz(v):
    """Blender bike space -> Godot bike space (glTF: x, z, -y)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


def drivetrain_only():
    """Apply the drivetrain stage to the existing GLB (keeps the baked atlas; backs it up first)."""
    import shutil
    assets = os.path.join(ROOT, "assets", "bicycles")
    arch = os.path.join(assets, "archive", "v1")
    os.makedirs(arch, exist_ok=True)
    gd = os.path.join(assets, "archive", ".gdignore")
    if not os.path.exists(gd):
        open(gd, "w").close()
    for f in ("gray_bicycle.glb", "gray_bicycle_GrayBicycle_basecolor.jpg", "gray_bicycle_GrayBicycle_metal_rough.jpg",
              "gray_bicycle_GrayBicycle_normal.jpg"):
        if not os.path.exists(os.path.join(arch, f)) and os.path.exists(os.path.join(assets, f)):
            shutil.copy2(os.path.join(assets, f), os.path.join(arch, f))
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(REPORT):
        shutil.copy2(os.path.join(ROOT, "world", "vehicles", "production", "reports", "gray_bicycle.json"), REPORT)
    src = os.path.join(arch, "gray_bicycle.glb")      # always start from the pre-drivetrain bike
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src)
    ob = bpy.data.objects
    info, _ = drivetrain_stage(ob["GrayBicycle"], ob["SteeringPivot"], ob["WheelRear"], ob["Frame"], ob["Saddle"],
                               ob["ForkAndBars"], ob["RearWheelMesh"])
    root = ob["GrayBicycle"]
    meshes = [o for o in root.children_recursive if o.type == 'MESH']
    with open(REPORT) as f:
        rep = json.load(f)
    rep.update(info)
    rep["triangles"] = tris(meshes)
    rep["parts"] = {o.name: tris([o]) for o in meshes}
    rep["nodes_godot"] = {o.name: {"parent": o.parent.name, "position_bike_space": godot_xyz(o.matrix_world.translation)}
                          for o in root.children_recursive if o.type == 'EMPTY'}
    rep["crank_rest"] = "right crank points forward (Godot -Z), left back; Crank turns about its local X"
    rep["pedalling"] = "forward pedalling = Crank.rotation.x decreasing (rotate_x(-angle)); keep pedals level with PedalL/PedalR.rotation.x = -Crank.rotation.x"
    with open(REPORT, "w") as f:
        json.dump(rep, f, indent=2)
    export_bike(root)


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
    dt_info, wr = drivetrain_stage(root, pivot, w_rear, frame, saddle, steer, wr)
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
    info.update(dt_info)
    every = [o for o in root.children_recursive if o.type == 'MESH']
    info["triangles"] = tris(every)
    info["parts"] = {o.name: tris([o]) for o in every}
    info["nodes_godot"] = {o.name: {"parent": o.parent.name, "position_bike_space": godot_xyz(o.matrix_world.translation)}
                           for o in root.children_recursive if o.type == 'EMPTY'}
    info["crank_rest"] = "right crank points forward (Godot -Z), left back; Crank turns about its local X"
    info["pedalling"] = "forward pedalling = Crank.rotation.x decreasing (rotate_x(-angle)); keep pedals level with PedalL/PedalR.rotation.x = -Crank.rotation.x"
    root["wheelbase"] = round(wheelbase, 4)
    root["wheel_radius"] = WHEEL_RADIUS
    root["asset_source"] = "woman_riding_a_gray_bicycle.glb, rider removed (tools/build_gray_bicycle.py)"
    log("info", json.dumps(info))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w") as f:
        json.dump(info, f, indent=2)
    export_bike(root)
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
    # drivetrain closeups and the crank at 0/90/180/270 deg of forward pedalling (pedals level)
    bbc = (0, BB_Y, BB_Z)
    shoot("drivetrain_right", (1, 0, 0), target=(0, BB_Y - 0.12, BB_Z + 0.02), ortho=0.75)
    shoot("drivetrain_left", (-1, 0, 0), target=bbc, ortho=0.6)
    ground = next(o for o in bpy.data.objects if o.name.startswith("Plane"))
    ground.hide_render = True
    shoot("drivetrain_below", (0.0001, 0.0, -1), target=(0, BB_Y - 0.15, BB_Z), ortho=0.8)
    ground.hide_render = False
    shoot("drivetrain_rear34", (0.55, -0.75, 0.35), target=(0, BB_Y - 0.15, BB_Z), ortho=0.85)
    shoot("drivetrain_front34", (0.7, 0.6, 0.3), target=bbc, ortho=0.6)
    shoot("rear_hub_right", (1, 0, 0.0), target=(0, -0.5508, 0.35), ortho=0.35)
    shoot("rear_hub_rear", (0.0, -1, 0.15), target=(0, -0.5508, 0.35), ortho=0.35)
    crank = bpy.data.objects.get("Crank")
    if crank:
        pedals = [bpy.data.objects[n] for n in ("PedalL", "PedalR")]
        for deg in (0, 90, 180, 270):
            crank.matrix_basis = Matrix.Translation(crank.matrix_basis.translation) @ Matrix.Rotation(-math.radians(deg), 4, 'X')
            for p in pedals:   # forward pedalling = negative X; pedals counter-rotate and stay level
                p.matrix_basis = Matrix.Translation(p.matrix_basis.translation) @ Matrix.Rotation(math.radians(deg), 4, 'X')
            bpy.context.view_layer.update()
            shoot("crank_%03d_right" % deg, (1, 0, 0), target=bbc, ortho=0.6)
            shoot("crank_%03d_34" % deg, (0.7, 0.6, 0.3), target=bbc, ortho=0.7)
            pr = bpy.data.objects["PedalR"].matrix_world
            log("  crank %d: PedalR at %s, pedal body up axis %s" % (deg, tuple(round(c, 3) for c in pr.translation),
                                                                    tuple(round(c, 3) for c in pr.to_3x3() @ Vector((0, 0, 1)))))
        for o in [crank] + pedals:
            o.matrix_basis = Matrix.Translation(o.matrix_basis.translation)
        bpy.context.view_layer.update()
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


if "drivetrain" in ARGS:
    drivetrain_only()
    if DO_QA:
        qa()
else:
    main()
