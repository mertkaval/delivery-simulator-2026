"""The courier's backpack: worn fit, body-fitted shoulder straps and the bag-handling clips.

Imported by tools/prepare_player.py (stages `player` and `bag`); it runs inside that script's
Blender session and uses its rig helpers (Rig, Limbs, sstep, ...: see bind()).

What it makes
  * Worn fit. The insulated delivery bag (assets/delivery/delivery_bag.glb, 0.44 x 0.34 x 0.46 m)
    sits between the shoulder blades, rigid on the UpperChest bone: its back panel 10 mm off the
    back at the closest point (Idle), its top level with the top of the shoulders. The plain
    backpack (world/city_assets/backpack.glb, 0.32 x 0.22 x 0.46 m) uses the same back plane and
    height, so one set of straps fits both.
  * Straps. Two skinned meshes, BackpackStrapL / BackpackStrapR, exported inside courier.glb: a
    padded strap from the bag's top tab over the shoulder and down the chest, a buckle, then
    webbing under the armpit back to the bag's bottom tab. They follow the body surface (built on
    the rest mesh, weights copied from the nearest torso skin, arm weights left out so the arm
    swings past them; both ends blend to 100 % UpperChest so they meet the rigid bag).
  * Clips (added to Clips.out like every other clip, so they are baked into courier.glb):
      Bag_TakeOff, Bag_Hold (loop), Bag_PackItem, Bag_TakeItem, Bag_PutOn,
      Carry_Idle (loop), Carry_Walk (loop), Handover, PlaceDown.
    The bag and the package are not bones, so their motion is written as data next to the clip
    (clips_blender.json -> clips.json): bag_track / package_track per frame (30 fps) as Godot
    Courier-root transforms [px, py, pz, qx, qy, qz, qw], flap_deg per frame, and events (bag
    socket back <-> track, which strap meshes show, package in hand / released / in bag).

Conventions: Blender courier space (faces -Y, +X = the courier's left, Z up). A bag / package
matrix maps its own Blender asset frame (front -Y, bottom-centre origin) to courier space.
Godot Courier root: p_g = (-x, z, y); basis_g = C R Gm^-1 (see to_godot()).
"""
import bpy, bmesh, os, math, json
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree


def bind(g):
    """Take prepare_player.py's helpers (Rig, Limbs, sstep, rotate_bone_world, ...)."""
    G = globals()
    for k, v in g.items():
        if not k.startswith("__") and k not in G:
            G[k] = v


# ----------------------------------------------------------------------------- constants
BAG_W, BAG_D, BAG_H = 0.44, 0.34, 0.46
FLAP_T = 0.022
HANDLE_Z = 0.497                 # centre line of the padded top grab handle (bag local)
GAP_MIN = 0.006                  # back panel to the back's envelope over all clips (closest point)
PLAIN_SHIFT = 0.06               # plain backpack back face (y 0.11) -> delivery bag back face (y 0.17)
PKG = Vector((0.20, 0.14, 0.30))  # nominal package (width x, depth y, height z), bottom-centre origin
STRAP_TOP = (0.105, 0.183, 0.425)  # bag-local strap ends (x sign per side), on the tabs
STRAP_BOT = (0.105, 0.186, 0.058)
ARM_KEYS = ("UpperArm", "LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Little")
FINGER_KEYS = ("Thumb", "Index", "Middle", "Ring", "Little")
ROOT_DIR = None                  # set in bind via ROOT
CURLS = {        # Index, Middle, Ring, Little, Thumb (deg per joint)
    "grip": ((62, 80, 50), (66, 84, 52), (70, 86, 52), (74, 86, 50), (18, 28, 30)),
    "hook": ((30, 42, 26), (34, 46, 28), (38, 48, 28), (42, 48, 26), (8, 6, 4)),
    "flat": ((6, 8, 5), (6, 8, 5), (8, 10, 6), (10, 12, 8), (14, 8, 4)),
    "tray": ((10, 14, 8), (10, 14, 8), (12, 16, 10), (14, 18, 10), (24, 10, 6)),
    "box": ((18, 24, 14), (20, 26, 14), (22, 28, 16), (24, 30, 16), (22, 14, 8)),
    "relaxed": ((14, 22, 12), (16, 24, 14), (18, 26, 14), (20, 28, 14), (10, 8, 4)),
    "pinch": ((30, 40, 30), (40, 55, 35), (55, 70, 45), (60, 75, 45), (30, 25, 20)),
}


def is_arm(n):
    return any(k in n for k in ARM_KEYS)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def rx(a):
    return Matrix.Rotation(math.radians(a), 4, 'X')


def ry(a):
    return Matrix.Rotation(math.radians(a), 4, 'Y')


def rz(a):
    return Matrix.Rotation(math.radians(a), 4, 'Z')


def T(v):
    return Matrix.Translation(Vector(v))


def to_godot(M):
    """Courier-space matrix of a glTF asset (bag / package) -> Godot Courier-root transform list."""
    C = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))
    Gm = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    R = C @ M.to_3x3().normalized() @ Gm.transposed()
    p = C @ M.to_translation()
    q = R.to_quaternion()
    return [round(p.x, 4), round(p.y, 4), round(p.z, 4), round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)]


def hermite(ts, vals, t, stops):
    """C1 cubic through keyed values (Vector / float), Catmull-Rom tangents, zero at stops/ends."""
    n = len(ts)
    if t <= ts[0]:
        return vals[0]
    if t >= ts[-1]:
        return vals[-1]
    i = max(j for j in range(n - 1) if ts[j] <= t)

    def tan(j):
        if j == 0 or j == n - 1 or stops[j]:
            return vals[j] * 0.0
        return (vals[j + 1] - vals[j - 1]) / (ts[j + 1] - ts[j - 1])
    h = ts[i + 1] - ts[i]
    s = (t - ts[i]) / h
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return vals[i] * h00 + tan(i) * (h * h10) + vals[i + 1] * h01 + tan(i + 1) * (h * h11)


def quat_track(ts, qs, t, stops):
    al = [qs[0].copy()]
    for q in qs[1:]:
        al.append(-q if al[-1].dot(q) < 0 else q.copy())
    v = hermite(ts, [Vector(q) for q in al], t, stops)
    return Quaternion(v).normalized()


class Keys:
    """Keyed scalar / Vector track: [(t, value)] or [(t, value, 'stop')]."""

    def __init__(self, keys):
        self.ts = [k[0] for k in keys]
        self.vs = [k[1] for k in keys]
        self.stops = [len(k) > 2 and k[2] == "stop" for k in keys]

    def at(self, t):
        v = hermite(self.ts, [Vector(x) if isinstance(x, (tuple, list, Vector)) else x for x in self.vs], t, self.stops)
        return v


# ----------------------------------------------------------------------------- the work
class BagWork:
    def __init__(self, C, R):
        self.C, self.R = C, R
        self.rig, self.limbs, self.arm, self.mesh = C.rig, C.limbs, C.arm, C.mesh
        self.idle = R["Idle"]
        self.walk = R["Walk"]
        self.bag_meta = {}
        self.vertex_data()

    # ------------------------------------------------------------------ body data
    def vertex_data(self):
        me = self.mesh.data
        names = {g.index: g.name for g in self.mesh.vertex_groups}
        n = len(me.vertices)
        self.wl = []
        self.w_arm = np.zeros(n)
        self.w_head = np.zeros(n)
        self.w_hand = np.zeros(n)
        for v in me.vertices:
            lst = [(names[g.group], g.weight) for g in v.groups if g.weight > 1e-4]
            self.wl.append(lst)
            for nm, w in lst:
                if is_arm(nm):
                    self.w_arm[v.index] += w
                if nm in ("Head", "LeftEye", "RightEye", "Jaw"):
                    self.w_head[v.index] += w
                if "Hand" in nm or any(k in nm for k in FINGER_KEYS):
                    self.w_hand[v.index] += w
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        self.tris = tri.reshape(-1, 3)
        self.torso_v = (self.w_arm < 0.3) & (self.w_head < 0.5)
        self.torso_t = self.tris[self.torso_v[self.tris].all(1)]
        self.rest_co = mesh_np(self.mesh, world=False)
        log("bag: body verts %d, torso tris %d / %d" % (n, len(self.torso_t), len(self.tris)))

    def posed(self, P):
        apply_pose(self.arm, P)
        return evaluated_np([self.mesh])[0]

    def bvh(self, co, tris):
        return BVHTree.FromPolygons([tuple(c) for c in co], tris.tolist())

    # ------------------------------------------------------------------ worn fit
    FIT_CLIPS = ["Idle_Loop", "Walk_Loop", "Walk_Back_Loop", "Jog_Mixamo_Loop", "Run_Loop", "Sprint_Loop", "Strafe_L_Loop",
                 "Jump_Start", "Jump_Loop", "Jump_Land", "Land_Hard", "Bike_Pedal_Loop", "Bike_Seated_Loop", "Turn_L_90"]

    def fit_worn(self):
        """Envelope fit: the back of the courier in UpperChest space over sampled frames of every
        locomotion / jump / bike clip; the bag's back panel clears all of them by GAP_MIN, tilted so
        it touches the envelope at the shoulder blades and at the lower back alike."""
        P = self.idle[0]
        W = self.C.W(P)
        co = self.posed(P)
        keep = (self.w_arm < 0.75) & (self.w_head < 0.5)
        torso = co[keep]
        s = torso[(np.abs(np.abs(torso[:, 0]) - 0.125) < 0.02) & (np.abs(torso[:, 1]) < 0.06)]
        z_sh = float(np.percentile(s[:, 2], 97))
        UC0 = W["UpperChest"]
        names = [n for n, _, _ in self.C.out]
        cloud, idle_local = [], None
        for nm in self.FIT_CLIPS:
            if nm not in names:
                continue
            poses = self.C.out[names.index(nm)][1]
            step = max(1, (len(poses) - 1) // 8)
            for k in range(0, len(poses), step):
                Pk = poses[k]
                ck = self.posed(Pk)[keep]
                Wk = self.rig.fk(Pk)
                M = np.array(Wk["UpperChest"].inverted())
                loc = ck @ M[:3, :3].T + M[:3, 3]
                cloud.append(loc)
                if idle_local is None and nm == "Idle_Loop":
                    idle_local = loc
        cloud = np.concatenate(cloud)
        best = None
        for tilt in np.arange(-6.0, 12.01, 0.5):
            B = T((0, 0.3, z_sh - BAG_H - 0.005)) @ rz(180) @ rx(tilt)
            Bl = np.array((UC0.inverted() @ B).inverted())
            L = cloud @ Bl[:3, :3].T + Bl[:3, 3]
            foot = (np.abs(L[:, 0]) < BAG_W / 2 - 0.005) & (L[:, 2] > 0.0) & (L[:, 2] < BAG_H) & (L[:, 1] > 0.0)
            g = L[foot, 1] - BAG_D / 2
            zz = L[foot, 2]
            up, lo = g[zz > BAG_H * 0.55], g[zz < BAG_H * 0.45]
            if not len(up) or not len(lo):
                continue
            shift = GAP_MIN - g.min()
            score = abs(up.min() - lo.min())
            if best is None or score < best[0]:
                best = (score, tilt, shift)
        _, tilt, shift = best
        B = T((0, 0.3, z_sh - BAG_H - 0.005)) @ rz(180) @ rx(tilt) @ T((0, -shift, 0))
        self.worn_idle = B
        self.O = UC0.inverted() @ B
        self.O_plain = self.O @ T((0, PLAIN_SHIFT, 0))
        Bl = np.array(self.O.inverted())
        L = idle_local @ Bl[:3, :3].T + Bl[:3, 3]
        foot = (np.abs(L[:, 0]) < BAG_W / 2 - 0.005) & (L[:, 2] > 0.0) & (L[:, 2] < BAG_H) & (L[:, 1] > 0.0)
        gi = L[foot, 1] - BAG_D / 2
        zi = L[foot, 2]
        log("bag: worn fit (envelope of %d points) tilt %.1f deg, shoulder top z %.3f, bag bottom z %.3f, Idle gaps upper %.3f lower %.3f"
            % (len(cloud), tilt, z_sh, B.to_translation().z, gi[zi > BAG_H * 0.55].min(), gi[zi < BAG_H * 0.45].min()))
        self.bag_meta["worn_tilt_deg"] = round(float(tilt), 2)
        return B

    # ------------------------------------------------------------------ bag-aware locomotion
    VARIANTS = ["Walk_Loop", "Walk_Back_Loop", "Jog_Mixamo_Loop", "Run_Loop", "Sprint_Loop", "Strafe_L_Loop", "Strafe_R_Loop",
                "Turn_L_90", "Turn_R_90", "Jump_Start", "Jump_Loop", "Jump_Land", "Land_Hard", "Interact", "PickUp"]
    ARM_X, ARM_R = 0.285, 0.05          # bag half width incl. side pockets; arm radius margin

    def arm_push(self, W, side):
        """World push vectors (elbow, wrist) that move the arm out of the worn bag's box."""
        B = self.worn(W)
        Bi = B.inverted()
        ymax = BAG_D / 2 + self.ARM_R
        out = []
        for p in (W[side + "LowerArm"].to_translation(),
                  (W[side + "LowerArm"].to_translation() + W[side + "Hand"].to_translation()) / 2,
                  W[side + "Hand"].to_translation(),
                  W[side + "Hand"] @ Vector((0, 0.09, 0))):
            l = Bi @ p
            push = Vector()
            if abs(l.x) < self.ARM_X and -BAG_D / 2 - self.ARM_R < l.y < ymax and -0.06 < l.z < BAG_H + 0.04:
                dx = self.ARM_X - abs(l.x)
                dy = ymax - l.y
                loc = Vector((math.copysign(dx, l.x), 0, 0)) if dx < dy else Vector((0, dy, 0))
                push = B.to_3x3().normalized() @ loc
            out.append(push)
        e = out[0] if out[0].length >= out[1].length else out[1]
        h = max(out[2:], key=lambda v: v.length)
        return e, h

    def bag_variant(self, name):
        names = [n for n, _, _ in self.C.out]
        if name not in names:
            return None
        src, meta0 = self.C.out[names.index(name)][1], self.C.out[names.index(name)][2]
        loop = meta0["loop"]
        n = len(src) - 1 if loop else len(src)
        raw = {s: [] for s in ("Left", "Right")}
        for k in range(n):
            W = self.rig.fk(src[k])
            Ui = W["UpperChest"].to_3x3().normalized().inverted()
            for side in ("Left", "Right"):
                e, h = self.arm_push(W, side)
                raw[side].append((Ui @ e, Ui @ h))

        def smooth(seq):
            m = len(seq)
            idx = (lambda i: i % m) if loop else (lambda i: min(max(i, 0), m - 1))
            grown = [max((seq[idx(i + j)] for j in range(-3, 4)), key=lambda v: v.length) for i in range(m)]
            return [sum((grown[idx(i + j)] * w for j, w in zip(range(-2, 3), (1, 2, 3, 2, 1))), Vector()) / 9.0 for i in range(m)]
        sm = {}
        for side in ("Left", "Right"):
            sm[side] = list(zip(smooth([r[0] for r in raw[side]]), smooth([r[1] for r in raw[side]])))
        out = []
        for k in range(n):
            P = {b: m.copy() for b, m in src[k].items()}
            W = self.rig.fk(P)
            R = W["UpperChest"].to_3x3().normalized()
            for side in ("Left", "Right"):
                e_l, h_l = sm[side][k]
                if e_l.length < 1e-4 and h_l.length < 1e-4:
                    continue
                E0 = W[side + "LowerArm"].to_translation()
                H0 = W[side + "Hand"].to_translation()
                q = self.rig.rot(W, side + "Hand")
                for it in range(4):
                    S = W[side + "UpperArm"].to_translation()
                    E = E0 + R @ e_l * 1.08
                    H = H0 + R @ h_l * 1.08
                    pole = (E - (S + H) / 2)
                    if pole.length < 1e-4:
                        pole = Vector((0, 1, 0))
                    W = self.limbs.arm(P, W, side, H, pole.normalized(), q)
                    e2, h2 = self.arm_push(W, side)
                    if e2.length < 0.004 and h2.length < 0.004:
                        break
                    Ri = R.inverted()
                    e_l, h_l = e_l + Ri @ e2, h_l + Ri @ h2
            out.append(P)
        if loop:
            out.append(dict(out[0]))
        meta = {k: v for k, v in meta0.items() if k in ("root_yaw_deg", "root_yaw_curve", "root_yaw_samples_30fps", "cycle_time_scale",
                                                     "root_motion_removed_m")}
        game = name[:-5] if name.endswith("_Loop") else name
        if game == "Jog_Mixamo":
            game = "Jog"
        meta["note"] = "%s with the backpack worn: the arms ease round the bag (%s)" % (game, meta0.get("note", "same legs and speed"))
        meta["bag_variant_of"] = game
        new = game + "_Bag" + ("_Loop" if loop else "")
        kw = {}
        if meta0["kind"] in ("locomotion", "standing"):
            ax = meta0.get("axis", (0, 1, 0))
            kw["axis"] = Vector(ax)
            kw["ground"] = 0.035 if game in ("Run", "Sprint") else 0.02
        self.C.add(new, out, loop, meta0["kind"], **meta, **kw)
        self.variants[new] = name
        return new

    def build_variants(self):
        self.variants = {}
        for nm in self.VARIANTS:
            self.bag_variant(nm)
        log("bag: arm variants", list(self.variants))

    def worn(self, W, plain=False):
        return W["UpperChest"] @ (self.O_plain if plain else self.O)

    # ------------------------------------------------------------------ straps
    def build_straps(self):
        """Body-fitted shoulder straps on the rest mesh, skinned like the skin under them."""
        rig = self.rig
        Wr = rig.fk(rig.identity())
        B = Wr["UpperChest"] @ self.O
        co = self.rest_co
        bvh = self.bvh(co, self.torso_t)
        mat = bpy.data.materials.get("Courier_Strap") or bpy.data.materials.new("Courier_Strap")
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
        bsdf.inputs["Roughness"].default_value = 0.78
        mat.diffuse_color = (0.03, 0.03, 0.034, 1)
        self.strap_objs = {}
        self.strap_mid = {}
        for side, sx in (("Left", 1), ("Right", -1)):
            ob, mid = self.one_strap(side, sx, B, bvh, mat)
            self.strap_objs[side] = ob
            self.strap_mid[side] = mid
        return self.strap_objs

    def surf(self, bvh, origin, direction, fallback):
        hit = bvh.ray_cast(Vector(origin), Vector(direction).normalized(), 1.0)
        if hit[0] is None:
            loc, nrm, _, _ = bvh.find_nearest(Vector(fallback))
            return loc + nrm * 0.02
        return hit[0] + hit[1] * 0.02

    def one_strap(self, side, sx, B, bvh, mat):
        top = B @ Vector((-sx * STRAP_TOP[0], STRAP_TOP[1], STRAP_TOP[2]))
        bot = B @ Vector((-sx * STRAP_BOT[0], STRAP_BOT[1], STRAP_BOT[2]))
        up = B.to_3x3() @ Vector((0, 0, 1))
        inward = B.to_3x3() @ Vector((0, 1, 0))
        X = lambda x: sx * x
        ctrl = [top, top + up * 0.04 + inward * 0.004,
                self.surf(bvh, (X(0.118), 0.035, 1.9), (0, 0, -1), (X(0.118), 0.035, 1.52)),
                self.surf(bvh, (X(0.118), -0.03, 1.9), (0, 0, -1), (X(0.118), -0.03, 1.5)),
                self.surf(bvh, (X(0.122), -0.6, 1.43), (0, 1, 0), (X(0.12), -0.1, 1.43)),
                self.surf(bvh, (X(0.128), -0.6, 1.35), (0, 1, 0), (X(0.13), -0.15, 1.35)),
                self.surf(bvh, (X(0.135), -0.6, 1.27), (0, 1, 0), (X(0.135), -0.15, 1.27)),
                self.surf(bvh, (X(0.6), -0.45, 1.23), (X(-0.75), 0.66, 0), (X(0.15), -0.08, 1.23)),
                self.surf(bvh, (X(0.6), 0.0, 1.20), (X(-1), 0, 0), (X(0.16), 0.0, 1.2)),
                self.surf(bvh, (X(0.5), 0.45, 1.15), (X(-0.75), -0.66, 0), (X(0.14), 0.07, 1.15)),
                bot + inward * 0.002 + Vector((X(0.03), 0, 0.03)), bot]
        # resample a Catmull-Rom through the control points at even arc length
        dense = []
        for i in range(len(ctrl) - 1):
            p0, p1, p2, p3 = ctrl[max(i - 1, 0)], ctrl[i], ctrl[i + 1], ctrl[min(i + 2, len(ctrl) - 1)]
            for k in range(20):
                s = k / 20
                dense.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
        dense.append(ctrl[-1])
        arc = [0.0]
        for a, b in zip(dense, dense[1:]):
            arc.append(arc[-1] + (b - a).length)
        total = arc[-1]
        N = 90
        pts = []
        for k in range(N + 1):
            d = total * k / N
            j = max(i for i in range(len(arc) - 1) if arc[i] <= d) if d < total else len(arc) - 2
            u = (d - arc[j]) / max(arc[j + 1] - arc[j], 1e-9)
            pts.append(dense[j].lerp(dense[j + 1], u))
        sarc = [total * k / N for k in range(N + 1)]
        # padded part: top anchor -> buckle on the lower chest (ctrl 6); webbing after it
        pad_end = None
        for k, p in enumerate(pts):
            if pad_end is None and (p - ctrl[6]).length < total / N * 0.75:
                pad_end = k
        if pad_end is None:
            pad_end = int(N * 0.55)
        thick = [0.012 if k <= pad_end else 0.0032 for k in range(N + 1)]
        width = [0.052 if k <= pad_end - 3 else (0.026 if k > pad_end + 1 else 0.04) for k in range(N + 1)]
        # project onto the skin (except where the strap leaves it for the bag's tabs)
        normals, alpha = [], []
        for k, p in enumerate(pts):
            a = min(ease(sarc[k] / 0.075), ease((total - sarc[k]) / 0.09))
            loc, nrm, idx, dist = bvh.find_nearest(p)
            clear = 0.0045 + thick[k] / 2
            onskin = loc + nrm * clear
            pts[k] = p.lerp(onskin, a)
            normals.append((nrm * a + inward * (1 - a)).normalized())
            alpha.append(a)
        for it in range(4):           # smooth along the strap, re-project
            sm = [pts[0]] + [(pts[k - 1] + pts[k] * 2 + pts[k + 1]) / 4 for k in range(1, N)] + [pts[N]]
            for k in range(1, N):
                if alpha[k] > 0.01:
                    loc, nrm, idx, dist = bvh.find_nearest(sm[k])
                    onskin = loc + nrm * (0.0045 + thick[k] / 2)
                    sm[k] = sm[k].lerp(onskin, alpha[k])
                    normals[k] = (nrm * alpha[k] + inward * (1 - alpha[k])).normalized()
            pts = sm
        # ribbon
        bm = bmesh.new()
        rings = []
        prof = [(1, -0.8), (1, 0.8), (0.6, 1), (-0.6, 1), (-1, 0.8), (-1, -0.8), (-0.6, -1), (0.6, -1)]
        for k, p in enumerate(pts):
            t = (pts[min(k + 1, N)] - pts[max(k - 1, 0)]).normalized()
            nn = (normals[k] - t * normals[k].dot(t)).normalized()
            b = t.cross(nn).normalized()
            ring = []
            for pn, pb in prof:
                ring.append(bm.verts.new(p + nn * (pn * thick[k] / 2) + b * (pb * width[k] / 2)))
            rings.append(ring)
        for a, b in zip(rings, rings[1:]):
            for i in range(len(prof)):
                bm.faces.new((a[i], a[(i + 1) % len(prof)], b[(i + 1) % len(prof)], b[i]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        # buckle (ladder lock) where the pad meets the webbing
        k = pad_end
        p = pts[k]
        t = (pts[k + 1] - pts[k - 1]).normalized()
        nn = (normals[k] - t * normals[k].dot(t)).normalized()
        b = t.cross(nn).normalized()
        ret = bmesh.ops.create_cube(bm, size=1.0)
        M = Matrix((t * 0.022, b * 0.046, nn * 0.007)).transposed().to_4x4()
        M.translation = p + nn * 0.004
        bmesh.ops.transform(bm, matrix=M, verts=ret["verts"])
        bm.normal_update()
        name = "BackpackStrap" + side[0]
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for f in me.polygons:
            f.use_smooth = True
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = self.arm
        self.skin_strap(ob, bvh, alpha, len(prof))
        md = ob.modifiers.new("Armature", 'ARMATURE')
        md.object = self.arm
        mid = [k for k in range(N + 1) if alpha[k] > 0.99]
        log("bag: strap %s: length %.3f m, pad end at %.3f m, %d verts" % (side, total, sarc[pad_end], len(me.vertices)))
        self.strap_info = getattr(self, "strap_info", {})
        self.strap_info[side] = {"N": N, "ring": len(prof), "mid": mid, "front_k": pad_end - 4}
        return ob, mid

    def skin_strap(self, ob, bvh, alpha, ring):
        """Weights from the nearest torso skin triangle (barycentric), ends -> 100 % UpperChest."""
        co = self.rest_co
        groups = {}
        nv = len(ob.data.vertices)
        for v in ob.data.vertices:
            loc, nrm, idx, dist = bvh.find_nearest(v.co)
            tri = self.torso_t[idx]
            a, b, c = (Vector(co[i]) for i in tri)
            w = barycentric(loc, a, b, c)
            acc = {}
            for i, wi in zip(tri, w):
                for nm, gw in self.wl[i]:
                    if is_arm(nm):
                        continue
                    acc[nm] = acc.get(nm, 0.0) + gw * wi
            k = min(v.index // ring, len(alpha) - 1) if v.index < len(alpha) * ring else None
            al = alpha[k] if k is not None else 1.0
            s = sum(acc.values()) or 1.0
            acc = {nm: gw / s * al for nm, gw in acc.items()}
            acc["UpperChest"] = acc.get("UpperChest", 0.0) + (1 - al)
            top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
            s = sum(w for _, w in top)
            for nm, gw in top:
                if nm not in groups:
                    groups[nm] = ob.vertex_groups.get(nm) or ob.vertex_groups.new(name=nm)
                groups[nm].add([v.index], gw / s, 'REPLACE')

    # ------------------------------------------------------------------ hands
    def hand_rot(self, side, d, n):
        h0, p0, L = self.C.hand_frame(side)
        d = d.normalized()
        n = (n - d * n.dot(d)).normalized()
        F0 = Matrix((h0, p0, h0.cross(p0))).transposed()
        F1 = Matrix((d, n, d.cross(n))).transposed()
        return (F1 @ F0.inverted()).to_quaternion() @ self.rig.rest_rot[side + "Hand"]

    def fingers(self, side, preset):
        """Local finger bases for a curl preset (same construction as Clips.grip_hand)."""
        out = {}
        R = self.rig.rest
        _, p0, _ = self.C.hand_frame(side)
        for f, angs in zip(("Index", "Middle", "Ring", "Little", "Thumb"), CURLS[preset]):
            parts = dict(FINGERS)[f]
            for i, (part, a) in enumerate(zip(parts, angs)):
                n_ = side + f + part
                if n_ not in R:
                    continue
                nxt = side + f + parts[i + 1] if i + 1 < len(parts) else None
                fd = ((R[nxt].to_translation() if nxt else R[n_] @ Vector((0, 0.03, 0))) - R[n_].to_translation()).normalized()
                ax = fd.cross(p0).normalized()
                out[n_] = Quaternion(self.rig.rest_rot[n_].inverted() @ ax, math.radians(a)).to_matrix().to_4x4()
        return out

    def grip_world(self, side, M, G, d, n, kind):
        """Wrist position + hand rotation for a grip given in the frame M (bag / package / chest)."""
        R3 = M.to_3x3().normalized()
        Gw = M @ Vector(G)
        dw = (R3 @ Vector(d)).normalized()
        nw = (R3 @ Vector(n))
        nw = (nw - dw * nw.dot(dw)).normalized()
        _, _, L = self.C.hand_frame(side)
        if kind == "wrap":
            wrist = Gw - dw * (0.80 * L) - nw * 0.034
        elif kind == "hook":
            wrist = Gw - dw * (0.62 * L) - nw * 0.028
        else:              # flat palm on a surface / tray
            wrist = Gw - dw * (0.50 * L) - nw * 0.022
        return wrist, self.hand_rot(side, dw, nw)

    # ------------------------------------------------------------------ the clip engine
    def perform(self, name, n_frames, base, spec, loop=False, kind="bag", **meta):
        """spec: dict of tracks (functions of t or Keys), see the clip methods."""
        rig, limbs = self.rig, self.limbs
        N = n_frames
        fr = []
        # pass 1: body (hips, spine, legs)
        for k in range(N + 1):
            t = k / FPS
            P = {n: m.copy() for n, m in base(k).items()}
            W = rig.fk(P)
            feet = {s: (W[s + "Foot"].to_translation(), W[s + "Foot"].to_quaternion(),
                        W[s + "LowerLeg"].to_translation() - (W[s + "UpperLeg"].to_translation() + W[s + "Foot"].to_translation()) / 2)
                    for s in ("Left", "Right")}
            moved = any(k in spec for k in ("hips", "yaw", "roll", "pitch", "twist", "flex", "side", "heel_Left", "heel_Right"))
            off = spec["hips"].at(t) if "hips" in spec else Vector()
            yaw = spec["yaw"].at(t) if "yaw" in spec else 0.0
            roll = spec["roll"].at(t) if "roll" in spec else 0.0
            pitch = spec["pitch"].at(t) if "pitch" in spec else 0.0
            hq = Quaternion(UP, math.radians(yaw)) @ Quaternion(Vector((0, 1, 0)), math.radians(roll)) @ Quaternion(LEFT, math.radians(pitch)) @ rig.rot(W, "Hips")
            W = rig.set_world(P, W, "Hips", Matrix.Translation(W["Hips"].to_translation() + off) @ hq.to_matrix().to_4x4())
            tw = spec["twist"].at(t) if "twist" in spec else 0.0
            fx = spec["flex"].at(t) if "flex" in spec else 0.0
            sb = spec["side"].at(t) if "side" in spec else 0.0
            for n, share in (("Spine", 0.30), ("Chest", 0.36), ("UpperChest", 0.34)):
                q = Quaternion(UP, math.radians(tw * share)) @ Quaternion(LEFT, math.radians(fx * share)) @ Quaternion(Vector((0, 1, 0)), math.radians(sb * share))
                W = rotate_bone_world(rig, P, W, n, q)
            for side in ("Left", "Right"):
                if not moved:
                    break
                ank, fq, kpole = feet[side]
                heel = spec["heel_" + side].at(t) if ("heel_" + side) in spec else 0.0
                if heel:
                    ball = (Matrix.Translation(ank) @ fq.to_matrix().to_4x4()) @ self.C.contacts[side]["ball"]
                    rq = Quaternion(LEFT, math.radians(heel))
                    ank = ball + rq @ (ank - ball)
                    fq = rq @ fq
                W = limbs.leg(P, W, side, ank, kpole.normalized() if kpole.length > 1e-4 else FWD, fq)
            if spec.get("neutral_shoulders", True):
                # the library Idle rolls the shoulders back (hands on the lower back): rest clavicles
                for s in ("Left", "Right"):
                    P[s + "Shoulder"] = Matrix.Identity(4)
                W = rig.fk(P)
            for s in ("Left", "Right"):       # shrug / shoulder roll
                if ("shrug_" + s) in spec:
                    W = rotate_bone_world(rig, P, W, s + "Shoulder", Quaternion(FWD, (1 if s == "Left" else -1) * math.radians(spec["shrug_" + s].at(t))))
            fr.append({"P": P, "W": W, "t": t})
        UC = [f["W"]["UpperChest"].copy() for f in fr]

        def uc_at(t):
            return UC[min(max(int(round(t * FPS)), 0), N)]
        # pass 2: objects (bag, package) in chest space, keyed in world at the key times
        objs = {}
        for key in ("bag", "pkg"):
            if key not in spec:
                continue
            keys = spec[key]
            ts, locs, stops = [], [], []
            for kk in keys:
                t, M = kk[0], kk[1]
                if isinstance(M, str) and M == "WORN":
                    L = self.O.copy()
                elif isinstance(M, tuple) and M[0] == "uc":       # already chest-local
                    L = M[1]
                elif isinstance(M, tuple) and M[0] == "world":    # fixed in the world (on the ground)
                    L = ("world", M[1])
                else:
                    L = uc_at(t).inverted() @ M
                ts.append(t)
                locs.append(L)
                stops.append(len(kk) > 2 and kk[2] == "stop")
            objs[key] = (ts, locs, stops)

        def obj_at(key, k):
            ts, locs, stops = objs[key]
            t = k / FPS
            Wl = []
            for L in locs:
                Wl.append(L[1] if isinstance(L, tuple) else UC[k] @ L)
            pos = hermite(ts, [M.to_translation() for M in Wl], t, stops)
            q = quat_track(ts, [M.to_quaternion() for M in Wl], t, stops)
            return Matrix.Translation(pos) @ q.to_matrix().to_4x4()
        # pass 3: hands, head
        out = []
        for k, f in enumerate(fr):
            P, W, t = f["P"], f["W"], f["t"]
            Bm = obj_at("bag", k) if "bag" in objs else None
            Pm = obj_at("pkg", k) if "pkg" in objs else None
            f["bag"], f["pkg"] = Bm, Pm
            f["hand_err"] = {}
            for side in ("Left", "Right"):
                if ("hand_" + side) not in spec:
                    continue
                keys = spec["hand_" + side]
                vals = [self.hand_spec(side, ks[1], P, W, Bm, Pm, UC[k]) for ks in keys]
                ts = [ks[0] for ks in keys]
                stops = [len(ks) > 2 and ks[2] == "stop" for ks in keys]
                wrist = hermite(ts, [v[0] for v in vals], t, stops)
                q = quat_track(ts, [v[1] for v in vals], t, stops)
                pole = hermite(ts, [v[2] for v in vals], t, stops).normalized()
                # fingers: piecewise blend between neighbouring keys
                i = max([j for j in range(len(ts)) if ts[j] <= t] or [0])
                j = min(i + 1, len(ts) - 1)
                u = 0.0 if j == i else ease((t - ts[i]) / (ts[j] - ts[i]))
                fa, fb = vals[i][3], vals[j][3]
                sh_ = W[side + "UpperArm"].to_translation()
                reach_ = (wrist - sh_).length / sum(self.limbs.len[side + "UpperArm"])
                W = self.limbs.arm(P, W, side, wrist, pole, q)
                f.setdefault("reach", {})[side] = (round(reach_, 2), tuple(round(c, 2) for c in wrist), tuple(round(c, 2) for c in sh_))
                for n_ in fa:
                    P[n_] = fa[n_].to_quaternion().slerp(fb.get(n_, fa[n_]).to_quaternion(), u).to_matrix().to_4x4()
                W = self.rig.fk(P)
                f["hand_err"][side] = (W[side + "Hand"].to_translation() - wrist).length
            if "look" in spec:
                W = self.look(P, W, spec["look"], t, Bm, Pm)
            f["W"] = W
            out.append(P)
        flap = [spec["flap"].at(k / FPS) if "flap" in spec else 0.0 for k in range(N + 1)]
        self.C.add(name, out, loop, kind, **meta)
        rec = {"frames": fr, "flap": flap, "events": spec.get("events", []), "loop": loop}
        self.clips[name] = rec
        errs = [(max(f["hand_err"].values()), k, max(f["hand_err"], key=f["hand_err"].get)) for k, f in enumerate(fr) if f["hand_err"]]
        if errs:
            bad = [(k, s_, round(e, 3), fr[k]["reach"][s_]) for e, k, s_ in errs if e > 0.01]
            log("bag: %s hand target error max %.3f m; frames > 1 cm: %s" % (name, max(errs)[0], bad[::4]))
        return rec

    def hand_spec(self, side, sp, P, W, Bm, Pm, UCm):
        """-> (wrist, rotation, elbow pole, finger bases)."""
        sx = 1 if side == "Left" else -1
        default_pole = (LEFT * (0.75 * sx) + Vector((0, 0.35, 0)) - UP * 0.55).normalized()
        typ = sp[0]
        if typ == "idle":
            base = self.idle[0] if len(sp) < 2 else sp[1]
            Wb = W
            wrist = Wb[side + "Hand"].to_translation()
            q = self.rig.rot(Wb, side + "Hand")
            el = Wb[side + "LowerArm"].to_translation()
            sh = Wb[side + "UpperArm"].to_translation()
            pole = (el - (sh + wrist) / 2).normalized()
            fing = {n: P[n].copy() for n in P if n.startswith(side) and any(k in n for k in FINGER_KEYS)}
            return wrist, q, pole, fing
        # ("bag" | "pkg" | "uc" | "world", (G, d, n, kind), curl, pole?)
        G, d, n, kind = sp[1]
        M = {"bag": Bm, "pkg": Pm, "uc": UCm, "ref": UCm @ self.UC0inv, "world": Matrix.Identity(4)}[typ]
        wrist, q = self.grip_world(side, M, G, d, n, kind)
        pole = sp[3] if len(sp) > 3 and sp[3] is not None else default_pole
        if typ == "uc" and len(sp) > 4 and sp[4] == "uc_pole":
            pole = UCm.to_3x3().normalized() @ pole
        return wrist, q, Vector(pole), self.fingers(side, sp[2])

    def look(self, P, W, keys, t, Bm, Pm):
        """keys: [(t, target, weight)]; target: Vector (world), 'bag', 'bag_in', 'pkg', None."""
        ts = [k[0] for k in keys]
        tg = []
        for k in keys:
            x = k[1]
            if isinstance(x, str):
                if x == "bag":
                    x = Bm @ Vector((0, 0, BAG_H * 0.55))
                elif x == "bag_in":
                    x = Bm @ Vector((0, 0.0, 0.33))
                elif x == "pkg":
                    x = Pm @ Vector((0, 0, PKG.z * 0.5))
            tg.append(Vector(x))
        target = hermite(ts, tg, t, [False] * len(ts))
        wgt = hermite(ts, [k[2] for k in keys], t, [False] * len(ts))
        head = W["Head"].to_translation() + Vector((0, -0.06, 0.07))
        d = (target - head).normalized()
        qh = self.rig.rot(W, "Head") @ self.rig.rest_rot["Head"].inverted()
        quc = self.rig.rot(W, "UpperChest") @ self.rig.rest_rot["UpperChest"].inverted()
        cur = qh @ FWD
        upc, lc = quc @ UP, quc @ LEFT

        def yp(v):
            fw = (v - upc * v.dot(upc))
            yaw = math.atan2(v.dot(lc), fw.dot(quc @ FWD))
            pitch = math.atan2(-v.dot(upc), fw.length)
            return yaw, pitch
        y0, p0 = yp(cur)
        y1, p1 = yp(d)
        dy = max(-1.25, min(1.25, y1 - y0)) * wgt
        dp = max(-0.9, min(0.9, p1 - p0)) * wgt
        for n, share in (("Neck", 0.4), ("Head", 0.6)):
            q = Quaternion(upc, dy * share) @ Quaternion(lc, dp * share)
            W = rotate_bone_world(self.rig, P, W, n, q)
        return W

    # ------------------------------------------------------------------ grips
    # bag-local grips: (G, d = wrist->knuckles, n = palm -> object, kind)
    def g_handle(self, x, d=(0, 1, -0.45), n=(0, -0.25, -1)):
        return ((x, 0.0, HANDLE_Z), d, n, "wrap")

    def g_handle_carry(self, x):
        """Briefcase grip at the side (bag hangs, straps towards the leg): fingers down."""
        return ((x, 0.0, HANDLE_Z), (0, 0.15, -1), (0, 1, 0.1), "wrap")

    def g_side_r(self, z=0.40):
        """Right palm flat on the bag's right side (held with the flap towards the courier)."""
        return ((BAG_W / 2 + 0.004, 0.0, z), (0, 0.55, -0.83), (-1, 0, 0), "flat")

    def g_flap_tip(self, theta, x=0.09, r=BAG_H - 0.01):
        """Right hand pinching the flap r m from its hinge (flap at theta deg, 0 = closed)."""
        tip = Vector((0, -BAG_D / 2, 0)) + (rx(theta) @ Vector((x, -FLAP_T / 2, r)))
        dn = rx(theta).to_3x3() @ Vector((0, 0, 1))
        return (tuple(tip), tuple(dn), (-1, 0, 0), "hook")

    def g_flap_front(self, x=0.09, z=0.33):
        """Right palm pressing the closed flap."""
        return ((x, -BAG_D / 2 - FLAP_T - 0.003, z), (0, 0.2, 1), (0, 1, 0), "flat")

    # ------------------------------------------------------------------ reference frames
    def hold_matrix(self, x=0.06, y=-0.46, z=0.74, psi=25.0, pitch=0.0):
        """Bag in front, flap (front) towards the courier: bag yaw psi relative to the worn bag."""
        return T((x, y, z)) @ rz(180 + psi) @ rx(pitch)

    def side_matrix(self, x=0.31, y=0.06, z=0.50, psi=-90.0, roll=0.0):
        return T((x, y, z)) @ rz(180 + psi) @ ry(roll)

    def pkg_carry(self, W, lower=0.0):
        """Two-handed carry in front of the belly (matches player_avatar carry_transform)."""
        return T((0, -0.33, 0.975 - lower))

    def carry_grip(self, side):
        sx = 1 if side == "Left" else -1
        return ((sx * (PKG.x / 2 + 0.002), 0.0, PKG.z * 0.42), (sx * -0.15, -0.55, -0.82), (-sx, 0, 0), "flat")

    def tray_grip(self):
        """Right palm under a package lying on its back (its back face down, top pointing away):
        palm centre 9 cm from the near end, fingers towards the far end."""
        return ((0.0, PKG.y / 2, PKG.z * 0.5), (0, 0, 1), (0, -1, 0), "flat")

    def push_grip(self):
        """Right palm flat on the near end (bottom face) of the lying package, fingers up."""
        return ((0.0, 0.0, -0.004), (0, -1, 0.0), (0, 0, 1), "flat")

    def pull_grip(self):
        """Right fingers hooked over the near top edge of the lying package."""
        return ((0.0, -PKG.y / 2, 0.03), (0, 0.3, 1), (0, 1, 0), "hook")

    # ------------------------------------------------------------------ the clips
    def run(self):
        """Worn fit -> straps -> clips -> clip metadata."""
        self.fit_worn()
        self.build_straps()
        self.build_clips()
        self.build_variants()
        for o in self.strap_objs.values():
            o.hide_render = True

    def build_clips(self):
        self.clips = {}
        self.UC0inv = self.C.W(self.idle[0])["UpperChest"].inverted()
        self.Lidle = len(self.idle) - 1
        self.bag_worn_idle()
        self.take_off()
        self.hold()
        self.pack_item()
        self.take_item()
        self.put_on()
        self.put_on_holding()
        self.strap_right()
        self.carry_idle()
        self.carry_walk()
        self.handover()
        self.place_down()
        self.write_meta()

    def idle_base(self, offset=0):
        L = self.Lidle
        return lambda k: self.idle[(k + offset) % L]

    def strap_front(self, side):
        """Chest-local point on the worn strap front (thumb hook), from the Idle pose."""
        if not hasattr(self, "_strap_front"):
            self._strap_front = {}
        if side not in self._strap_front:
            P = self.idle[0]
            W = self.C.W(P)
            apply_pose(self.arm, P)
            co = evaluated_np([self.strap_objs[side]])[0]
            inf = self.strap_info[side]
            k = inf["front_k"]
            ring = inf["ring"]
            c = Vector(co[k * ring: (k + 1) * ring].mean(0))
            self._strap_front[side] = (W["UpperChest"].inverted() @ c, W["UpperChest"].copy())
        return self._strap_front[side]

    # Hand key specs: ("idle",) | (frame, grip, curl[, elbow pole]) with frame "bag" / "pkg" (the
    # object), "uc" (chest-local grip), "ref" (grip given in the Idle-frame-0 courier pose, carried
    # by the chest). Grip = (point, wrist->knuckles, palm->object, "wrap" | "hook" | "flat").
    POLE_L = (0.8, 0.2, -0.6)
    POLE_R = (-0.8, 0.2, -0.6)

    def strap_hook(self, dz=0.0, dx=0.0, side="Right"):
        """Thumb hooked under the worn strap on the chest (chest-local grip)."""
        sf, _ = self.strap_front(side)
        sx = 1 if side == "Left" else -1
        return (tuple(sf + Vector((dx, -0.013, -0.005 + dz))), (-sx * 0.05, 0.15, 1), (0, 1, 0), "hook")

    def rest_arm(self, side):
        """Arm hanging relaxed beside the thigh (the library Idle keeps its hands on the lower
        back, where a worn bag is): a 'ref' hand spec."""
        sx = 1 if side == "Left" else -1
        return ("ref", ((sx * 0.205, -0.005, 0.875), (sx * 0.08, -0.12, -1), (-sx, 0.1, 0.0), "flat"), "relaxed", (sx * 0.25, 1.0, -0.1))

    def g_top_r(self, x=0.19):
        """Right palm on the top of the bag at its right corner nearest the courier."""
        return ((x, -0.10, BAG_H + 0.004), (0.25, 0.95, -0.15), (0, 0, -1), "flat")

    def bag_worn_idle(self):
        L = self.Lidle / FPS
        spec = {
            "hand_Left": [(0.0, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5)))],
            "hand_Right": [(0.0, ("uc", self.strap_hook(), "hook", (-0.9, 0.3, -0.5)))],
            "shrug_Left": Keys([(0.0, 2.0), (L, 2.0)]),
            "shrug_Right": Keys([(0.0, 2.0), (L, 2.0)]),
            "events": [],
        }
        return self.perform("Bag_Worn_Idle_Loop", self.Lidle, self.idle_base(), spec, loop=True, kind="standing",
                            note="Idle wearing the backpack: thumbs hooked under the shoulder straps (the library Idle's hands-behind pose would go through the bag)")

    def tilted_worn(self, deg, drop):
        """Worn bag hanging off the left shoulder only: rolled about the left top strap tab."""
        Wi = self.C.W(self.idle[0])
        worn = self.worn(Wi)
        pivot = worn @ Vector((-STRAP_TOP[0], STRAP_TOP[1], STRAP_TOP[2]))
        roll = T(pivot) @ Matrix.Rotation(math.radians(deg), 4, FWD) @ T(-pivot)
        return T(drop) @ roll @ worn

    def take_off(self):
        k2 = self.tilted_worn(-13, (0.02, 0.015, -0.03))
        k25 = self.side_matrix(x=0.36, y=0.20, z=0.76, psi=-52, roll=6)
        k3 = self.side_matrix(x=0.41, y=0.05, z=0.50, psi=-86, roll=3)
        k4 = self.hold_matrix(x=0.24, y=-0.38, z=0.64, psi=-35)
        spec = {
            "bag": [(0.0, "WORN"), (0.433, "WORN", "stop"), (0.54, k2), (0.64, k25), (0.77, k3), (0.96, k4),
                    (1.12, self.hold_matrix(z=0.745), "stop"), (1.30, self.hold_matrix(z=0.74), "stop")],
            "hips": Keys([(0.0, (0, 0, 0)), (0.30, (0.0, 0, 0)), (0.55, (-0.022, 0.0, -0.006)), (0.80, (-0.03, -0.008, -0.012)),
                          (1.10, (-0.004, -0.01, -0.008)), (1.30, (0, -0.008, -0.006))]),
            "twist": Keys([(0.0, 0.0), (0.30, -6.0), (0.50, 3.0), (0.74, 15.0), (0.96, 8.0), (1.20, 0.0), (1.30, 0.0)]),
            "flex": Keys([(0.0, 0.0), (0.30, 2.0), (0.74, 8.0), (1.10, 6.0), (1.30, 5.0)]),
            "side": Keys([(0.0, 0.0), (0.45, 3.0), (0.76, -6.0), (1.0, -2.0), (1.3, 0.0)]),
            "shrug_Right": Keys([(0.0, 0.0), (0.30, 6.0), (0.42, 9.0), (0.56, -2.0), (0.7, 0.0)]),
            "shrug_Left": Keys([(0.0, 0.0), (0.48, 5.0), (0.64, 0.0)]),
            "hand_Right": [(0.0, ("uc", self.strap_hook(), "hook", (-0.9, 0.3, -0.5))),
                           (0.14, ("uc", self.strap_hook(), "hook", (-0.9, 0.3, -0.5)), "stop"),
                           (0.32, ("uc", self.strap_hook(0.03, -0.03), "hook", (-0.8, 0.3, -0.5))),
                           (0.46, ("ref", ((-0.33, 0.05, 1.42), (0.15, 0.6, 0.78), (0.6, 0.0, -0.8), "hook"), "hook", (-0.5, 0.3, -0.8))),
                           (0.64, ("ref", ((-0.22, -0.10, 1.05), (0.3, -0.5, -0.8), (0.9, 0.2, 0.0), "flat"), "flat", (-0.8, 0.5, -0.4))),
                           (0.86, ("ref", ((-0.25, -0.30, 1.10), (0.4, -0.6, -0.7), (0.9, 0.2, 0.2), "flat"), "flat", (-0.8, 0.4, -0.4))),
                           (1.08, ("bag", self.g_top_r(), "flat"), "stop"),
                           (1.30, ("bag", self.g_top_r(), "flat"))],
            "hand_Left": [(0.0, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5))),
                          (0.24, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5)), "stop"),
                          (0.44, self.rest_arm("Left")),
                          (0.64, ("bag", self.g_handle_carry(0.0), "grip", (0.6, 0.4, -0.7))),
                          (0.78, ("bag", self.g_handle_carry(0.0), "grip", (0.6, 0.4, -0.7))),
                          (1.00, ("bag", self.g_handle(-0.03), "grip", self.POLE_L)),
                          (1.12, ("bag", self.g_handle(-0.045), "grip", self.POLE_L), "stop"),
                          (1.30, ("bag", self.g_handle(-0.045), "grip", self.POLE_L))],
            "look": [(0.0, (0, -1.5, 1.6), 0.0), (0.16, (-0.12, -0.3, 1.25), 0.7), (0.40, (-0.35, 0.0, 1.35), 0.6),
                     (0.62, "bag", 0.6), (0.85, "bag", 0.8), (1.05, "bag_in", 0.9), (1.30, "bag_in", 0.9)],
            "flap": Keys([(0.0, 0.0), (1.02, 0.0, "stop"), (1.17, 186.0), (1.24, 174.0), (1.30, 180.0, "stop")]),
            "events": [{"frame": 13, "do": "bag_socket", "to": "track"}, {"frame": 13, "do": "body_strap_r", "visible": False},
                       {"frame": 13, "do": "bag_strap_r", "visible": True}, {"frame": 13, "do": "bag_strap_l", "visible": False},
                       {"frame": 17, "do": "body_strap_l", "visible": False}, {"frame": 17, "do": "bag_strap_l", "visible": True}],
        }
        return self.perform("Bag_TakeOff", 39, self.idle_base(), spec, kind="bag",
                            note="right strap off, the bag slides down the left arm into the left hand, comes round to the front, flap drops open towards the courier")

    def hold(self):
        L = self.Lidle / FPS
        keys = []
        for i in range(5):
            a = 2 * math.pi * i / 4
            keys.append((L * i / 4, self.hold_matrix(z=0.74 + 0.004 * math.sin(a), psi=25 + 1.5 * math.sin(a + 0.6))))
        spec = {
            "bag": keys,
            "hips": Keys([(0.0, (0, -0.008, -0.006)), (L, (0, -0.008, -0.006))]),
            "flex": Keys([(0.0, 5.0), (L, 5.0)]),
            "hand_Left": [(0.0, ("bag", self.g_handle(-0.045), "grip", self.POLE_L))],
            "hand_Right": [(0.0, ("bag", self.g_top_r(), "flat"))],
            "look": [(0.0, "bag_in", 0.9), (L * 0.35, self.hold_matrix() @ Vector((-0.08, 0, 0.25)), 0.85),
                     (L * 0.7, self.hold_matrix() @ Vector((0.1, 0, 0.36)), 0.85), (L, "bag_in", 0.9)],
            "flap": Keys([(0.0, 180.0), (L * 0.5, 178.0), (L, 180.0)]),
            "events": [{"frame": 0, "do": "bag_socket", "to": "track"}, {"frame": 0, "do": "body_strap_r", "visible": False},
                       {"frame": 0, "do": "body_strap_l", "visible": False}, {"frame": 0, "do": "bag_strap_r", "visible": True},
                       {"frame": 0, "do": "bag_strap_l", "visible": True}],
        }
        return self.perform("Bag_Hold_Loop", self.Lidle, self.idle_base(39 % self.Lidle), spec, loop=True, kind="bag",
                            note="standing, the open bag held in front: left hand on the top handle, right palm on its side")

    def lying_at(self, x, y, z, pitch=0.0):
        """Package lying on its back (front up), its top pointing forward; box centre at (x, y, z)."""
        R = rz(180) @ rx(-90 + pitch)
        return Matrix.Translation(Vector((x, y, z))) @ R @ Matrix.Translation(-Vector((0, 0, PKG.z / 2)))

    def lying_in_bag(self, Bm, depth):
        """The lying package in the top compartment (top towards the back wall, back face on the
        shelf), depth 0 = fully in (2 cm inside the opening), negative = still sticking out."""
        R = Bm.to_3x3().normalized().to_4x4() @ rx(-90)
        c = Bm @ Vector((0.0, -BAG_D / 2 + 0.02 + PKG.z / 2 + depth, 0.267 + PKG.y / 2 + 0.006))
        return Matrix.Translation(c) @ R @ Matrix.Translation(-Vector((0, 0, PKG.z / 2)))

    def pack_start(self, Bp):
        """The package lying on the right palm beside the right hip, lined up with the bag."""
        return T((-0.03, 0.0, -0.05)) @ self.lying_in_bag(Bp, -0.30)

    def pack_item(self):
        Bh = self.hold_matrix()
        Bp = self.hold_matrix(y=-0.42, z=0.75, psi=45, pitch=3)
        spec = {
            "bag": [(0.0, Bh), (0.40, Bp), (0.66, Bp, "stop"), (1.0, Bh, "stop")],
            "pkg": [(0.0, self.pack_start(Bp)), (0.28, self.lying_in_bag(Bp, -0.27)),
                    (0.46, self.lying_in_bag(Bp, -0.10), "stop"), (0.64, self.lying_in_bag(Bp, 0.0), "stop")],
            "hips": Keys([(0.0, (0, -0.008, -0.006)), (0.5, (-0.01, -0.012, -0.008)), (1.0, (0, -0.008, -0.006))]),
            "twist": Keys([(0.0, 4.0), (0.4, 8.0), (0.64, 8.0), (1.0, 0.0)]),
            "flex": Keys([(0.0, 5.0), (0.5, 7.0), (1.0, 5.0)]),
            "hand_Left": [(0.0, ("bag", self.g_handle(-0.045), "grip", self.POLE_L))],
            "hand_Right": [(0.0, ("pkg", self.tray_grip(), "tray", (-0.8, 0.3, -0.5))),
                           (0.46, ("pkg", self.tray_grip(), "tray", (-0.8, 0.3, -0.5)), "stop"),
                           (0.54, ("pkg", self.push_grip(), "flat", (-0.8, 0.3, -0.5))),
                           (0.64, ("pkg", self.push_grip(), "flat", (-0.8, 0.3, -0.5)), "stop"),
                           (0.80, ("ref", ((-0.28, -0.24, 1.02), (0.3, -0.5, -0.8), (0.9, 0.2, 0.0), "flat"), "flat")),
                           (1.0, ("bag", self.g_top_r(), "flat"), "stop")],
            "look": [(0.0, "pkg", 0.8), (0.4, "pkg", 0.85), (0.64, "bag_in", 0.9), (1.0, "bag_in", 0.9)],
            "flap": Keys([(0.0, 180.0), (1.0, 180.0)]),
            "events": self.HELD_EVENTS + [{"frame": 0, "do": "package", "to": "track"}, {"frame": 19, "do": "package", "to": "bag", "slot": "top"}],
        }
        return self.perform("Bag_PackItem", 30, self.idle_base(5), spec, kind="bag",
                            note="left hand holds the bag; the right hand brings the package (lying on the palm) in and pushes it into the top compartment",
                            package_release_frame=19)

    def take_item(self):
        Bh = self.hold_matrix()
        Bp = self.hold_matrix(y=-0.42, z=0.75, psi=45, pitch=3)
        spec = {
            "bag": [(0.0, Bh), (0.30, Bp), (0.56, Bp, "stop"), (1.0, Bh, "stop")],
            "pkg": [(0.0, self.lying_in_bag(Bp, 0.0)), (0.30, self.lying_in_bag(Bp, 0.0), "stop"), (0.48, self.lying_in_bag(Bp, -0.12), "stop"),
                    (0.74, self.lying_in_bag(Bp, -0.27)), (1.0, self.pack_start(Bp), "stop")],
            "hips": Keys([(0.0, (0, -0.008, -0.006)), (0.4, (-0.01, -0.012, -0.008)), (1.0, (0, -0.008, -0.006))]),
            "twist": Keys([(0.0, 0.0), (0.3, 8.0), (0.7, 8.0), (1.0, 4.0)]),
            "flex": Keys([(0.0, 5.0), (0.4, 7.0), (1.0, 5.0)]),
            "hand_Left": [(0.0, ("bag", self.g_handle(-0.045), "grip", self.POLE_L))],
            "hand_Right": [(0.0, ("bag", self.g_top_r(), "flat")),
                           (0.18, ("ref", ((-0.28, -0.24, 1.10), (0.3, -0.6, -0.6), (0.9, 0.2, 0.2), "flat"), "flat")),
                           (0.30, ("pkg", self.pull_grip(), "hook", (-0.8, 0.3, -0.5)), "stop"),
                           (0.48, ("pkg", self.pull_grip(), "hook", (-0.8, 0.3, -0.5)), "stop"),
                           (0.58, ("pkg", self.tray_grip(), "tray", (-0.8, 0.3, -0.5))),
                           (1.0, ("pkg", self.tray_grip(), "tray", (-0.8, 0.3, -0.5)), "stop")],
            "look": [(0.0, "bag_in", 0.9), (0.45, "bag_in", 0.9), (0.75, "pkg", 0.8), (1.0, "pkg", 0.7)],
            "flap": Keys([(0.0, 180.0), (1.0, 180.0)]),
            "events": self.HELD_EVENTS + [{"frame": 9, "do": "package", "to": "track"}],
        }
        return self.perform("Bag_TakeItem", 30, self.idle_base(9), spec, kind="bag",
                            note="the right hand reaches into the top compartment, pulls the package out by its near edge and brings it out lying on the palm; the left hand holds the bag",
                            package_grab_frame=9)

    def put_on(self):
        k_tilt = self.tilted_worn(-15, (0.03, 0.025, -0.04))
        spec = {
            "bag": [(0.0, self.hold_matrix()), (0.10, self.hold_matrix(z=0.80, pitch=-26)), (0.24, self.hold_matrix(z=0.79, pitch=8)),
                    (0.34, self.hold_matrix(z=0.78), "stop"),
                    (0.52, self.hold_matrix(x=0.30, y=-0.36, z=0.72, psi=-55)),
                    (0.68, self.side_matrix(x=0.41, y=0.05, z=0.52, psi=-86, roll=3)),
                    (0.84, self.side_matrix(x=0.36, y=0.20, z=0.80, psi=-52, roll=8)),
                    (0.98, k_tilt), (1.10, "WORN", "stop"), (1.30, "WORN")],
            "hips": Keys([(0.0, (0, -0.008, -0.006)), (0.32, (0, -0.01, -0.01)), (0.68, (-0.03, -0.008, -0.012)), (0.92, (-0.02, 0.0, -0.006)),
                          (1.15, (0, 0, -0.004)), (1.3, (0, 0, 0))]),
            "twist": Keys([(0.0, 0.0), (0.32, 0.0), (0.68, 15.0), (0.88, 6.0), (1.02, -6.0), (1.18, 0.0), (1.3, 0.0)]),
            "flex": Keys([(0.0, 5.0), (0.20, 9.0), (0.32, 8.0), (0.68, 8.0), (1.0, 3.0), (1.3, 0.0)]),
            "side": Keys([(0.0, 0.0), (0.68, -6.0), (0.92, 3.0), (1.3, 0.0)]),
            "shrug_Left": Keys([(0.0, 0.0), (0.82, 0.0), (0.94, 6.0), (1.06, 0.0)]),
            "shrug_Right": Keys([(0.0, 0.0), (0.96, 0.0), (1.10, 8.0), (1.2, 2.0), (1.3, 0.0)]),
            "hand_Left": [(0.0, ("bag", self.g_handle(-0.045), "grip", self.POLE_L)), (0.32, ("bag", self.g_handle(-0.045), "grip", self.POLE_L)),
                          (0.52, ("bag", self.g_handle(-0.02), "grip", self.POLE_L)),
                          (0.68, ("bag", self.g_handle_carry(0.0), "grip", (0.6, 0.4, -0.7))),
                          (0.84, ("bag", self.g_handle_carry(0.0), "grip", (0.6, 0.4, -0.7))), (1.02, self.rest_arm("Left")),
                          (1.18, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5))), (1.3, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5)), "stop")],
            "hand_Right": [(0.0, ("bag", self.g_top_r(), "flat")),
                           (0.14, ("ref", ((-0.20, -0.30, 1.12), (0.3, -0.6, 0.5), (0.5, -0.6, 0.0), "flat"), "flat")),
                           (0.24, ("bag", self.g_flap_tip(25, r=0.30), "flat")), (0.32, ("bag", self.g_flap_front(), "flat"), "stop"),
                           (0.40, ("bag", self.g_flap_front(), "flat")),
                           (0.62, ("ref", ((-0.22, -0.10, 1.04), (0.2, -0.4, -0.9), (0.9, 0.2, 0.0), "flat"), "flat", (-0.8, 0.5, -0.4))),
                           (0.88, ("ref", ((-0.30, 0.12, 1.08), (0.1, 0.4, -0.9), (0.8, 0.0, 0.3), "flat"), "flat", (-0.6, 0.6, -0.4))),
                           (1.04, ("ref", ((-0.33, 0.05, 1.40), (0.15, 0.6, 0.78), (0.6, 0.0, -0.8), "hook"), "hook", (-0.5, 0.3, -0.8))),
                           (1.14, ("uc", self.strap_hook(), "hook", (-0.9, 0.3, -0.5))), (1.30, ("uc", self.strap_hook(), "hook", (-0.9, 0.3, -0.5)), "stop")],
            "look": [(0.0, "bag_in", 0.9), (0.22, "bag", 0.8), (0.55, "bag", 0.7), (0.8, "bag", 0.5), (1.05, (-0.25, -0.4, 1.3), 0.4),
                     (1.30, (0, -1.5, 1.6), 0.0)],
            "flap": Keys([(0.0, 180.0), (0.08, 180.0, "stop"), (0.20, 60.0), (0.27, 0.0, "stop"), (1.3, 0.0)]),
            "events": [{"frame": 0, "do": "bag_socket", "to": "track"}, {"frame": 0, "do": "body_strap_r", "visible": False},
                       {"frame": 0, "do": "body_strap_l", "visible": False}, {"frame": 0, "do": "bag_strap_r", "visible": True},
                       {"frame": 0, "do": "bag_strap_l", "visible": True},
                       {"frame": 29, "do": "body_strap_l", "visible": True}, {"frame": 29, "do": "bag_strap_l", "visible": False},
                       {"frame": 33, "do": "bag_socket", "to": "back"}, {"frame": 33, "do": "body_strap_r", "visible": True},
                       {"frame": 33, "do": "bag_strap_r", "visible": False}],
        }
        return self.perform("Bag_PutOn", 39, self.idle_base(3), spec, kind="bag",
                            note="a flick of the left hand swings the flap up, the right palm presses it shut, the bag swings to the left side and up onto the back (left arm through the left strap), right arm into the right strap, settle")

    def carry_spec(self, L):
        pk = self.pkg_carry(None)
        return {
            "pkg": [(0.0, pk), (L, pk)],
            "hand_Left": [(0.0, ("pkg", self.carry_grip("Left"), "box", self.POLE_L))],
            "hand_Right": [(0.0, ("pkg", self.carry_grip("Right"), "box", self.POLE_R))],
            "look": [(0.0, (0, -2.0, 1.45), 0.25), (L, (0, -2.0, 1.45), 0.25)],
            "flex": Keys([(0.0, -2.0), (L, -2.0)]),
        }

    def carry_idle(self):
        spec = self.carry_spec(self.Lidle / FPS)
        spec["events"] = [{"frame": 0, "do": "package", "to": "track"}]
        return self.perform("Carry_Idle_Loop", self.Lidle, self.idle_base(), spec, loop=True, kind="carry",
                            note="standing, a package held in front with both hands (forearms level)")

    def carry_walk(self):
        Lw = len(self.walk) - 1
        spec = self.carry_spec(Lw / FPS)
        del spec["flex"]
        spec["events"] = [{"frame": 0, "do": "package", "to": "track"}]
        spec["neutral_shoulders"] = False
        return self.perform("Carry_Walk_Loop", Lw, lambda k: self.walk[k % Lw], spec, loop=True, kind="locomotion",
                            note="Walk with a package held in front with both hands; legs, feet and speed exactly as Walk")

    def handover(self):
        pk = self.pkg_carry(None)
        spec = {
            "pkg": [(0.0, pk), (0.48, T((0, -0.50, 1.12)), "stop"), (0.64, T((0, -0.52, 1.13)), "stop"), (0.90, T((0, -0.72, 1.16)))],
            "hips": Keys([(0.0, (0, 0, 0)), (0.5, (0, -0.035, -0.008)), (0.75, (0, -0.03, -0.006)), (1.2, (0, 0, 0))]),
            "flex": Keys([(0.0, -2.0), (0.5, 9.0), (0.75, 7.0), (1.2, 0.0)]),
            "hand_Left": [(0.0, ("pkg", self.carry_grip("Left"), "box", self.POLE_L)), (0.64, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"),
                          (0.82, ("ref", ((0.24, -0.38, 1.08), (-0.1, -0.6, -0.8), (-0.9, 0, 0.2), "flat"), "flat")), (1.2, self.rest_arm("Left"), "stop")],
            "hand_Right": [(0.0, ("pkg", self.carry_grip("Right"), "box", self.POLE_R)), (0.64, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"),
                           (0.82, ("ref", ((-0.24, -0.38, 1.08), (0.1, -0.6, -0.8), (0.9, 0, 0.2), "flat"), "flat")), (1.2, self.rest_arm("Right"), "stop")],
            "look": [(0.0, (0, -2.0, 1.45), 0.25), (0.3, "pkg", 0.5), (0.55, (0, -0.95, 1.62), 0.8), (0.9, (0, -0.95, 1.62), 0.8), (1.2, (0, -1.2, 1.62), 0.5)],
            "events": [{"frame": 0, "do": "package", "to": "track"}, {"frame": 19, "do": "package", "to": "released"}],
        }
        return self.perform("Handover", 36, self.idle_base(), spec, kind="action",
                            note="offer the package forward with both hands, the customer takes it at frame 19, hands come back",
                            package_release_frame=19)

    def place_down(self):
        pk = self.pkg_carry(None)
        ground = T((0.02, -0.36, 0.0))
        spec = {
            "pkg": [(0.0, pk), (0.30, T((0, -0.40, 0.50))), (0.58, ("world", ground), "stop"), (1.2, ("world", ground))],
            "hips": Keys([(0.0, (0, 0, 0)), (0.58, (0, 0.10, -0.50), "stop"), (0.70, (0, 0.10, -0.48)), (1.2, (0, 0, 0))]),
            "pitch": Keys([(0.0, 0.0), (0.58, 42.0, "stop"), (0.70, 38.0), (1.2, 0.0)]),
            "flex": Keys([(0.0, -2.0), (0.58, 44.0, "stop"), (0.70, 40.0), (1.2, 0.0)]),
            "heel_Left": Keys([(0.0, 0.0), (0.58, 22.0), (0.75, 18.0), (1.2, 0.0)]),
            "heel_Right": Keys([(0.0, 0.0), (0.58, 22.0), (0.75, 18.0), (1.2, 0.0)]),
            "hand_Left": [(0.0, ("pkg", self.carry_grip("Left"), "box", self.POLE_L)), (0.60, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"),
                          (0.76, ("ref", ((0.22, -0.30, 1.05), (-0.2, -0.5, -0.8), (-0.9, 0, 0.1), "flat"), "flat")), (1.2, self.rest_arm("Left"), "stop")],
            "hand_Right": [(0.0, ("pkg", self.carry_grip("Right"), "box", self.POLE_R)), (0.60, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"),
                           (0.76, ("ref", ((-0.22, -0.30, 1.05), (0.2, -0.5, -0.8), (0.9, 0, 0.1), "flat"), "flat")), (1.2, self.rest_arm("Right"), "stop")],
            "look": [(0.0, (0, -2.0, 1.45), 0.25), (0.3, "pkg", 0.7), (0.7, "pkg", 0.75), (1.2, (0, -2.0, 1.55), 0.1)],
            "events": [{"frame": 0, "do": "package", "to": "track"}, {"frame": 18, "do": "package", "to": "released"}],
        }
        return self.perform("PlaceDown", 36, self.idle_base(), spec, kind="action",
                            note="squat and set the package on the ground in front (leave at door), release at frame 18, stand up",
                            package_release_frame=18)

    HELD_EVENTS = [{"frame": 0, "do": "bag_socket", "to": "track"}, {"frame": 0, "do": "body_strap_r", "visible": False},
                   {"frame": 0, "do": "body_strap_l", "visible": False}, {"frame": 0, "do": "bag_strap_r", "visible": True},
                   {"frame": 0, "do": "bag_strap_l", "visible": True}]

    def put_on_holding(self):
        """Bag_TakeItem's end pose (package on the right palm, bag in the left hand) -> the bag
        swung onto the back over the LEFT shoulder only (the right hand keeps the package) -> the
        two-handed carry (Carry_Idle pose). Bag_StrapRight puts the right arm in later."""
        Bp = self.hold_matrix(y=-0.42, z=0.75, psi=45, pitch=3)
        start = self.pack_start(Bp)
        pk = self.pkg_carry(None)
        k_tilt = self.tilted_worn(-10, (0.02, 0.02, -0.025))
        spec = {
            "bag": [(0.0, self.hold_matrix()), (0.10, self.hold_matrix(z=0.80, pitch=-26)), (0.24, self.hold_matrix(z=0.78, pitch=8)),
                    (0.34, self.hold_matrix(z=0.76), "stop"),
                    (0.52, self.hold_matrix(x=0.30, y=-0.36, z=0.70, psi=-55)),
                    (0.68, self.side_matrix(x=0.41, y=0.05, z=0.52, psi=-86, roll=3)),
                    (0.84, self.side_matrix(x=0.36, y=0.20, z=0.80, psi=-52, roll=8)),
                    (0.98, k_tilt), (1.08, "WORN", "stop"), (1.30, "WORN")],
            "pkg": [(0.0, start), (0.40, start), (0.80, T((-0.02, -0.03, 0.03)) @ start), (1.12, pk, "stop"), (1.30, pk)],
            "hips": Keys([(0.0, (0, -0.008, -0.006)), (0.34, (0, -0.01, -0.01)), (0.68, (-0.03, -0.008, -0.012)), (0.92, (-0.02, 0.0, -0.006)),
                          (1.15, (0, 0, -0.002)), (1.3, (0, 0, 0))]),
            "twist": Keys([(0.0, 4.0), (0.34, 2.0), (0.68, 15.0), (0.88, 6.0), (1.05, -3.0), (1.2, 0.0), (1.3, 0.0)]),
            "flex": Keys([(0.0, 5.0), (0.34, 6.0), (0.68, 8.0), (1.0, 3.0), (1.3, -2.0)]),
            "side": Keys([(0.0, 0.0), (0.68, -6.0), (0.92, 3.0), (1.3, 0.0)]),
            "shrug_Left": Keys([(0.0, 0.0), (0.82, 0.0), (0.96, 7.0), (1.10, 1.0), (1.3, 0.0)]),
            "hand_Left": [(0.0, ("bag", self.g_handle(-0.045), "grip", self.POLE_L)), (0.34, ("bag", self.g_handle(-0.045), "grip", self.POLE_L)),
                          (0.52, ("bag", self.g_handle(-0.02), "grip", self.POLE_L)),
                          (0.68, ("bag", self.g_handle_carry(0.0), "grip", (0.6, 0.4, -0.7))),
                          (0.86, ("bag", self.g_handle_carry(0.0), "grip", (0.6, 0.4, -0.7))),
                          (1.02, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5))),
                          (1.18, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"),
                          (1.30, ("pkg", self.carry_grip("Left"), "box", self.POLE_L))],
            "hand_Right": [(0.0, ("pkg", self.tray_grip(), "tray", (-0.8, 0.3, -0.5))), (0.86, ("pkg", self.tray_grip(), "tray", (-0.8, 0.3, -0.5))),
                           (1.12, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"), (1.30, ("pkg", self.carry_grip("Right"), "box", self.POLE_R))],
            "look": [(0.0, "bag_in", 0.8), (0.25, "bag", 0.8), (0.55, "bag", 0.7), (0.85, "bag", 0.5), (1.05, "pkg", 0.4), (1.30, (0, -2.0, 1.45), 0.25)],
            "flap": Keys([(0.0, 180.0), (0.08, 180.0, "stop"), (0.20, 60.0), (0.27, 0.0, "stop"), (1.3, 0.0)]),
            "events": self.HELD_EVENTS + [{"frame": 0, "do": "package", "to": "track"},
                                          {"frame": 32, "do": "bag_socket", "to": "back"}, {"frame": 32, "do": "body_strap_l", "visible": True},
                                          {"frame": 32, "do": "bag_strap_l", "visible": False}, {"frame": 32, "do": "bag_strap_r", "visible": False}],
        }
        return self.perform("Bag_PutOn_Holding", 39, self.idle_base(19), spec, kind="bag",
                            note="the right hand keeps the package; a flick of the left hand shuts the flap, the bag swings round the left side onto the left shoulder only (right strap stays off), both hands take the package (ends in the Carry_Idle pose). Follow with Handover / PlaceDown, then Bag_StrapRight")

    def strap_right(self):
        """Hands free, bag on the left shoulder only: the right arm goes back into the right strap,
        shrug, thumbs into the straps (ends in the Bag_Worn_Idle pose)."""
        spec = {
            "hips": Keys([(0.0, (0, 0, 0)), (0.4, (0.01, 0.0, -0.006)), (0.9, (0, 0, 0))]),
            "twist": Keys([(0.0, 0.0), (0.30, -10.0), (0.55, -4.0), (0.9, 0.0)]),
            "shrug_Right": Keys([(0.0, 0.0), (0.45, 0.0), (0.58, 8.0), (0.72, 1.0), (0.9, 2.0)]),
            "shrug_Left": Keys([(0.0, 0.0), (0.58, 4.0), (0.9, 2.0)]),
            "hand_Right": [(0.0, self.rest_arm("Right")),
                           (0.28, ("ref", ((-0.30, 0.12, 1.06), (0.1, 0.4, -0.9), (0.8, 0.0, 0.3), "flat"), "flat", (-0.6, 0.6, -0.4))),
                           (0.46, ("ref", ((-0.33, 0.05, 1.40), (0.15, 0.6, 0.78), (0.6, 0.0, -0.8), "hook"), "hook", (-0.5, 0.3, -0.8))),
                           (0.62, ("uc", self.strap_hook(0.02), "hook", (-0.9, 0.3, -0.5))),
                           (0.9, ("uc", self.strap_hook(), "hook", (-0.9, 0.3, -0.5)), "stop")],
            "hand_Left": [(0.0, self.rest_arm("Left")), (0.5, self.rest_arm("Left")),
                          (0.75, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5))),
                          (0.9, ("uc", self.strap_hook(side="Left"), "hook", (0.9, 0.3, -0.5)), "stop")],
            "look": [(0.0, (0, -1.5, 1.6), 0.0), (0.3, (-0.4, 0.0, 1.2), 0.35), (0.6, (-0.2, -0.4, 1.3), 0.3), (0.9, (0, -1.5, 1.6), 0.0)],
            "events": [{"frame": 0, "do": "bag_socket", "to": "back"}, {"frame": 0, "do": "body_strap_l", "visible": True},
                       {"frame": 0, "do": "body_strap_r", "visible": False}, {"frame": 14, "do": "body_strap_r", "visible": True}],
        }
        return self.perform("Bag_StrapRight", 27, self.idle_base(), spec, kind="bag",
                            note="bag on the left shoulder only: the right arm reaches back into the right strap and pulls it onto the shoulder (ends in the Bag_Worn_Idle pose)")

    # ------------------------------------------------------------------ data out
    def write_meta(self):
        for name, poses, meta in self.C.out:
            if name not in self.clips:
                continue
            rec = self.clips[name]
            fr = rec["frames"]
            if fr[0]["bag"] is not None:
                meta["bag_track"] = [to_godot(f["bag"]) for f in fr]
                meta["flap_deg"] = [round(x, 1) for x in rec["flap"]]
                meta["bag_model"] = "res://assets/delivery/delivery_bag_open.glb"
            if fr[0]["pkg"] is not None:
                meta["package_track"] = [to_godot(f["pkg"]) for f in fr]
                meta["package_box"] = [round(PKG.x, 3), round(PKG.z, 3), round(PKG.y, 3)]
            if rec["events"]:
                meta["events"] = rec["events"]
            if name in ("Bag_Hold_Loop",):
                meta["bag_socket"] = "track"
        Wi = self.C.W(self.idle[0])
        self.bag_meta.update({
            "worn_idle_frame0_courier_root": to_godot(self.worn(Wi)),
            "worn_plain_idle_frame0_courier_root": to_godot(self.worn(Wi, plain=True)),
            "bone": "UpperChest",
            "strap_meshes": ["BackpackStrapL", "BackpackStrapR"],
            "package_box_godot_xyz": [round(PKG.x, 3), round(PKG.z, 3), round(PKG.y, 3)],
        })

    # ------------------------------------------------------------------ plain backpack, worn version
    def export_plain_worn(self):
        """world/city_assets/backpack.glb without its free shoulder-strap loops (the body straps of
        courier.glb replace them) -> assets/player/backpack_plain_worn.glb, same frame / origin."""
        before = set(bpy.data.objects)
        new = import_any(os.path.join(ROOT, "world", "city_assets", "backpack.glb"))
        rub = next((o for o in new if o.name.split(".")[0] == "Rubber"), None)
        if rub is not None:
            bm = bmesh.new()
            bm.from_mesh(rub.data)
            dead = [v for v in bm.verts if v.co.z < 0.44 and v.co.y > 0.06]
            bmesh.ops.delete(bm, geom=dead, context='VERTS')
            bm.to_mesh(rub.data)
            bm.free()
        root = bpy.data.objects.new("PlainBackpack", None)
        bpy.context.scene.collection.objects.link(root)
        for o in new:
            if o.parent is None:
                o.parent = root
        path = os.path.join(OUT, "backpack_plain_worn.glb")
        select_only(new + [root], root)
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                                  export_animations=False, export_materials='EXPORT')
        log("bag: wrote", path)
        for o in new + [root]:
            bpy.data.objects.remove(o)

    # ------------------------------------------------------------------ QA
    def import_bags(self):
        out = {}
        for key, path in (("closed", os.path.join(ROOT, "assets", "delivery", "delivery_bag.glb")),
                          ("open", os.path.join(ROOT, "assets", "delivery", "delivery_bag_open.glb")),
                          ("plain", os.path.join(ROOT, "world", "city_assets", "backpack.glb"))):
            new = import_any(path)
            roots = [o for o in new if o.parent is None]
            if len(roots) > 1:
                e = bpy.data.objects.new("PlainRoot", None)
                bpy.context.scene.collection.objects.link(e)
                for r in roots:
                    r.parent = e
                new.append(e)
                roots = [e]
            for o in new:
                if o.type == 'MESH':
                    for m in o.data.materials:
                        if m and m.node_tree:
                            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                            if b:
                                c = b.inputs["Base Color"].default_value
                                m.diffuse_color = (c[0], c[1], c[2], 1)
            out[key] = {"root": roots[0], "objs": new, "by": {o.name.split(".")[0]: o for o in new}}
        # plain backpack: drop its free shoulder straps (the two webbing islands of "Rubber")
        rub = out["plain"]["by"].get("Rubber")
        if rub is not None:
            bm = bmesh.new()
            bm.from_mesh(rub.data)
            dead = [v for v in bm.verts if v.co.z < 0.44 and v.co.y > 0.06]
            bmesh.ops.delete(bm, geom=dead, context='VERTS')
            bm.to_mesh(rub.data)
            bm.free()
        for key in ("closed", "open"):
            for s in ("StrapL", "StrapR"):
                ob = out[key]["by"].get(s)
                if ob is not None:
                    out[key][s] = ob
        if out["open"]["by"].get("FlapStraps"):
            out["open"]["by"]["FlapStraps"].hide_render = True
        bpy.context.view_layer.update()
        self.bags = out
        return out

    def place(self, key, M, flap=None, straps=(True, True), show=True):
        b = self.bags[key]
        b["root"].matrix_world = M
        for o in b["objs"]:
            if o.type == 'MESH':
                o.hide_render = not show
        if key == "open" and b["by"].get("FlapStraps"):
            b["by"]["FlapStraps"].hide_render = True
        for s, vis in zip(("StrapL", "StrapR"), straps):
            if b.get(s) is not None:
                b[s].hide_render = not (show and vis)
        if flap is not None and b["by"].get("Flap"):
            fl = b["by"]["Flap"]
            fl.rotation_mode = 'XYZ'
            fl.rotation_euler = (math.radians(flap), 0, 0)
        bpy.context.view_layer.update()

    def hide_all_bags(self):
        for key in self.bags:
            self.place(key, Matrix.Identity(4), show=False)

    def pkg_object(self):
        if getattr(self, "_pkg", None):
            return self._pkg
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        o = bpy.context.active_object
        o.name = "QAPackage"
        o.data.transform(T((0, 0, 0.5)))
        o.data.transform(Matrix.Diagonal((PKG.x, PKG.y, PKG.z, 1)))
        m = bpy.data.materials.new("QAPkg")
        m.diffuse_color = (0.62, 0.45, 0.26, 1)
        o.data.materials.append(m)
        self._pkg = o
        return o

    def state_at(self, name, k):
        """Visibility state at frame k from the clip's events."""
        st = {"bag_socket": "back", "body_strap_r": True, "body_strap_l": True, "bag_strap_r": False, "bag_strap_l": False, "package": "none"}
        if name in ("Bag_Hold_Loop", "Bag_PackItem", "Bag_TakeItem"):
            st.update({"bag_socket": "track", "body_strap_r": False, "body_strap_l": False, "bag_strap_r": True, "bag_strap_l": True})
        if name in ("Bag_PutOn",):
            st.update({"bag_socket": "track", "body_strap_r": False, "body_strap_l": False, "bag_strap_r": True, "bag_strap_l": True})
        if name.startswith("Carry") or name in ("Handover", "PlaceDown"):
            st.update({"bag_socket": "back"})
        for e in self.clips[name]["events"]:
            if e["frame"] <= k:
                if e["do"] == "bag_socket":
                    st["bag_socket"] = e["to"]
                elif e["do"] == "package":
                    st["package"] = e["to"]
                else:
                    st[e["do"]] = e["visible"]
        return st

    def pose_scene(self, name, k, show_bag_worn=True):
        rec = self.clips[name]
        f = rec["frames"][k]
        P = self.C.out[[n for n, _, _ in self.C.out].index(name)][1][k]
        apply_pose(self.arm, P)
        st = self.state_at(name, k)
        W = self.rig.fk(P)
        self.hide_all_bags()
        if st["bag_socket"] == "back" and show_bag_worn:
            self.place("closed", self.worn(W), 0.0, straps=(False, False))
        elif f["bag"] is not None and st["bag_socket"] == "track":
            self.place("open", f["bag"], rec["flap"][k], straps=(st["bag_strap_l"], st["bag_strap_r"]))
        self.strap_objs["Left"].hide_render = not st["body_strap_l"]
        self.strap_objs["Right"].hide_render = not st["body_strap_r"]
        pk = self.pkg_object()
        pk.hide_render = f["pkg"] is None or st["package"] in ("none",) or (st["package"] == "released" and name == "Handover")
        if f["pkg"] is not None:
            pk.matrix_world = f["pkg"]
        bpy.context.view_layer.update()
        return st

    def qa(self, bike=None, worn=True, only=None):
        os.makedirs(QA, exist_ok=True)
        self.import_bags()
        cam = render_setup(400)
        sc = bpy.context.scene
        sc.render.resolution_x = 380
        sc.render.resolution_y = 380
        checker_ground()
        if bike:
            for o in bike["objects"]:
                o.hide_render = True
        views = {"side": ((1, 0, 0.08), 2.1), "34": ((-0.72, -0.66, 0.3), 2.1), "behind": ((-0.32, 1, 0.36), 2.1)}
        # --- the new clips
        for name in self.clips:
            if only and name not in only:
                continue
            n = len(self.clips[name]["frames"]) - 1
            idx = sorted(set(int(round(i * n / 5)) for i in range(6)))
            tiles = []
            for vname, (d, o) in views.items():
                for k in idx:
                    self.pose_scene(name, k)
                    tgt = (0, -0.1, 0.62 if name == "PlaceDown" else 0.95)
                    p = os.path.join(QA, "_tmp_%s_%s_%02d.png" % (name, vname, k))
                    shoot(cam, p, d, tgt, o)
                    tiles.append(p)
            compose(tiles, os.path.join(QA, "bag_clip_%s.png" % name), cols=len(idx))
            log("bag: QA sheet", name)
        # --- close-ups of the hands on the bag
        for ci, (name, k, d, tgt, o) in enumerate((("Bag_Hold_Loop", 0, (-0.6, -0.9, 0.8), (0.0, -0.32, 1.12), 0.75),
                                    ("Bag_Hold_Loop", 0, (0.15, 0.6, 0.9), (0.0, -0.32, 1.12), 0.75),
                                    ("Bag_PackItem", 14, (-0.6, -0.9, 0.8), (0.0, -0.32, 1.1), 0.8),
                                    ("Bag_TakeOff", 20, (1, 0.2, 0.3), (0.2, 0.0, 1.0), 1.0),
                                    ("Bag_TakeOff", 7, (-0.6, -1, 0.35), (-0.1, -0.05, 1.32), 0.6),
                                    ("Carry_Idle_Loop", 0, (-0.7, -0.8, 0.5), (0.0, -0.25, 1.05), 0.75),
                                    ("Bag_PutOn", 6, (-0.6, -0.9, 0.5), (0.0, -0.32, 0.9), 0.9))):
            self.pose_scene(name, k)
            shoot(cam, os.path.join(QA, "bag_close_%d_%s_%02d.png" % (ci, name, k)), d, tgt, o)
        # --- strap close-ups (worn): chest front / shoulder / armpit in the hardest poses
        names_ = [n for n, _, _ in self.C.out]
        for ci, (name, frac, d, tgt, o) in enumerate((("Bag_Worn_Idle_Loop", 0.0, (-0.5, -1, 0.25), (0, -0.05, 1.32), 0.62),
                                                    ("Bag_Worn_Idle_Loop", 0.0, (1, -0.15, 0.3), (0.05, 0.05, 1.3), 0.7),
                                                    ("Sprint_Bag_Loop", 0.45, (-0.6, -1, 0.3), (0, -0.05, 1.3), 0.75),
                                                    ("Run_Bag_Loop", 0.2, (1, -0.4, 0.2), (0.05, 0.05, 1.25), 0.8),
                                                    ("Land_Hard_Bag", 0.3, (-0.6, -1, 0.3), (0, -0.05, 1.05), 0.9),
                                                    ("PlaceDown", 0.5, (1, -0.5, 0.3), (0, -0.1, 0.8), 1.1),
                                                    ("Bike_Pedal_Loop", 0.0, (-0.3, -1, 0.35), (0, -0.1, 1.25), 0.75),
                                                    ("Bike_Pedal_Loop", 0.25, (1, 0.1, 0.1), (0, 0.05, 1.2), 0.9))):
            if name not in names_:
                continue
            poses = self.C.out[names_.index(name)][1]
            k = int(round(frac * (len(poses) - 1)))
            apply_pose(self.arm, poses[k])
            self.hide_all_bags()
            self.place("closed", self.worn(self.rig.fk(poses[k])), 0.0, straps=(False, False))
            self.strap_objs["Left"].hide_render = False
            self.strap_objs["Right"].hide_render = False
            self.pkg_object().hide_render = True
            if bike:
                for ob_ in bike["objects"]:
                    ob_.hide_render = not name.startswith("Bike")
            shoot(cam, os.path.join(QA, "bag_strap_close_%d_%s.png" % (ci, name)), d, tgt, o)
        if bike:
            for ob_ in bike["objects"]:
                ob_.hide_render = True
        # --- worn bag in the other clips (delivery bag; plain backpack on a few)
        names = [n for n, _, _ in self.C.out]
        wanted = ["Bag_Worn_Idle_Loop", "Walk_Bag_Loop", "Jog_Bag_Loop", "Run_Bag_Loop", "Sprint_Bag_Loop", "Walk_Back_Bag_Loop",
                  "Strafe_L_Bag_Loop", "Strafe_R_Bag_Loop", "Turn_L_90_Bag", "Jump_Start_Bag", "Jump_Bag_Loop", "Jump_Land_Bag",
                  "Land_Hard_Bag", "Interact_Bag", "PickUp_Bag", "Bike_Seated_Loop", "Bike_Pedal_Loop"]
        report = {}
        for name in wanted:
            if name not in names or not worn:
                continue
            poses = self.C.out[names.index(name)][1]
            n = len(poses) - 1
            idx = sorted(set(int(round(i * n / 4)) for i in range(4))) if n > 0 else [0]
            report[name] = self.check_clip(poses, bike if name.startswith("Bike") else None)
            for plain in ((False, True) if name in ("Walk_Bag_Loop", "Sprint_Bag_Loop", "Bike_Pedal_Loop", "Jump_Bag_Loop") else (False,)):
                tiles = []
                for vname, (d, osc) in (("side", ((1, 0, 0.08), 2.1)), ("behind", ((-0.32, 1, 0.36), 2.1)), ("34", ((-0.72, -0.66, 0.3), 2.1))):
                    for k in idx:
                        P = poses[k]
                        apply_pose(self.arm, P)
                        W = self.rig.fk(P)
                        self.hide_all_bags()
                        self.place("plain" if plain else "closed", self.worn(W, plain), 0.0, straps=(False, False))
                        self.strap_objs["Left"].hide_render = False
                        self.strap_objs["Right"].hide_render = False
                        self.pkg_object().hide_render = True
                        if bike and name.startswith("Bike"):
                            for o in bike["objects"]:
                                o.hide_render = False
                            if name == "Bike_Pedal_Loop":
                                self.C.pose_bike_crank(2 * math.pi * k / n)
                            else:
                                self.C.pose_bike_crank(0.0)
                        p = os.path.join(QA, "_tmp_w_%s_%s_%02d.png" % (name, vname, k))
                        shoot(cam, p, d, (0, 0.0, 0.85 if name.startswith("Bike") else 0.95), osc + (0.3 if name.startswith("Bike") else 0))
                        tiles.append(p)
                compose(tiles, os.path.join(QA, "bag_worn_%s%s.png" % (name, "_plain" if plain else "")), cols=len(idx))
            if bike:
                for o in bike["objects"]:
                    o.hide_render = True
            log("bag: worn check %s %s" % (name, json.dumps(report[name])))
        for name in self.clips:
            rec = self.clips[name]
            poses = self.C.out[names.index(name)][1]
            report[name] = self.check_clip(poses, None, rec, name)
            log("bag: clip check %s %s" % (name, json.dumps(report[name])))
        with open(os.path.join(QA, "bag_report.json"), "w") as fh:
            json.dump({"worn": self.bag_meta, "checks": report}, fh, indent=1)
        self.hide_all_bags()

    def check_clip(self, poses, bike=None, rec=None, name=None):
        """Per clip: arm / hand / head / torso skin vertices inside the worn (or held) bag box,
        strap vertices under the torso skin (penetration) or > 3 cm off it (floating)."""
        worst = {"arm_in_bag": 0, "head_in_bag": 0, "torso_in_bag": 0, "strap_in_skin": 0, "strap_max_depth_mm": 0.0,
                 "strap_float_mm": 0.0, "hand_in_bag_wall": 0, "bike_in_bag": 0}
        step = max(1, (len(poses) - 1) // 12)
        for k in range(0, len(poses), step):
            P = poses[k]
            apply_pose(self.arm, P)
            W = self.rig.fk(P)
            co = evaluated_np([self.mesh])[0]
            st = self.state_at(name, k) if rec else {"bag_socket": "back", "body_strap_l": True, "body_strap_r": True}
            if st["bag_socket"] == "back":
                Bm = self.worn(W)
            elif rec and rec["frames"][k]["bag"] is not None:
                Bm = rec["frames"][k]["bag"]
            else:
                Bm = None
            if Bm is not None:
                Inv = np.array(Bm.inverted())
                L = co @ Inv[:3, :3].T + Inv[:3, 3]
                sh = 0.006
                inside = (np.abs(L[:, 0]) < BAG_W / 2 - sh) & (np.abs(L[:, 1]) < BAG_D / 2 - sh) & (L[:, 2] > sh) & (L[:, 2] < BAG_H - sh)
                cavity = (np.abs(L[:, 0]) < BAG_W / 2 - 0.02) & (L[:, 1] < BAG_D / 2 - 0.02) & (L[:, 2] > 0.267) & (L[:, 2] < BAG_H - 0.02)
                if st["bag_socket"] != "back":
                    inside &= ~cavity
                worst["arm_in_bag"] = max(worst["arm_in_bag"], int((inside & (self.w_arm > 0.5)).sum()))
                worst["hand_in_bag_wall"] = max(worst["hand_in_bag_wall"], int((inside & (self.w_hand > 0.5)).sum()))
                worst["head_in_bag"] = max(worst["head_in_bag"], int((inside & (self.w_head > 0.5)).sum()))
                worst["torso_in_bag"] = max(worst["torso_in_bag"], int((inside & self.torso_v).sum()))
                na, nt = int((inside & (self.w_arm > 0.5)).sum()), int((inside & self.torso_v).sum())
                if na > 15 or nt > 15:
                    tl = L[inside & self.torso_v]
                    worst.setdefault("frames", []).append([k, na, nt] + ([round(float(tl[:, 2].min()), 2), round(float(tl[:, 2].max()), 2)] if len(tl) else []))
                if bike:
                    for o in bike["objects"]:
                        if o.type != 'MESH':
                            continue
                        vv = np.empty(len(o.data.vertices) * 3)
                        o.data.vertices.foreach_get("co", vv)
                        vv = vv.reshape(-1, 3)
                        Mi = np.array(Bm.inverted() @ o.matrix_world)
                        bc = vv @ Mi[:3, :3].T + Mi[:3, 3]
                        if len(bc):
                            ins = (np.abs(bc[:, 0]) < BAG_W / 2) & (np.abs(bc[:, 1]) < BAG_D / 2) & (bc[:, 2] > 0) & (bc[:, 2] < BAG_H)
                            worst["bike_in_bag"] = max(worst["bike_in_bag"], int(ins.sum()))
            if st.get("bag_socket") == "back" or (rec and name in ("Bag_TakeOff", "Bag_PutOn")):
                bvh = self.bvh(co, self.torso_t)
                for side in ("Left", "Right"):
                    if not st.get("body_strap_" + side[0].lower(), True):
                        continue
                    sco = evaluated_np([self.strap_objs[side]])[0]
                    inf = self.strap_info[side]
                    ring = inf["ring"]
                    deep, cnt, fl = 0.0, 0, 0.0
                    for kk in inf["mid"]:
                        ringpts = sco[kk * ring:(kk + 1) * ring]
                        c = Vector(ringpts.mean(0))
                        loc, nrm, idx, dist = bvh.find_nearest(c)
                        if loc is None:
                            continue
                        for p in ringpts:
                            dd = (Vector(p) - loc).dot(nrm)
                            if dd < -0.001:
                                cnt += 1
                                deep = max(deep, -dd)
                        fl = max(fl, dist)
                    worst["strap_in_skin"] = max(worst["strap_in_skin"], cnt)
                    worst["strap_max_depth_mm"] = max(worst["strap_max_depth_mm"], round(deep * 1000, 1))
                    worst["strap_float_mm"] = max(worst["strap_float_mm"], round(fl * 1000, 1))
        return worst


def barycentric(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
    d20, d21 = v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-14:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    u = 1.0 - v - w
    ws = [max(0.0, u), max(0.0, v), max(0.0, w)]
    s = sum(ws) or 1.0
    return tuple(x / s for x in ws)
