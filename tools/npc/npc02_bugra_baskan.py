"""NPC02 - Bugra Baskan: young Turkish man, navy heathered crew-neck tee, dark grey washed slim
jeans, grey knit sneakers with white soles, black hair short at the sides with volume on top,
thick brows, short dark beard and moustache.  Run inside Blender (live or headless)."""
import bpy, math, os
import numpy as np
from mathutils import Vector

KIT = r"C:\GodotProjects\delivery-simulator-2026\tools\npc\npc_kit.py"
ns = {}
exec(open(KIT, encoding="utf-8").read(), ns)
Kit, smooth = ns["Kit"], ns["smooth"]

NAME = "NPC02_BugraBaskan"
HAIR = "short02"


def build_body(k):
    k.human(
        macros={"gender": 1.0, "age": 0.52, "muscle": 0.58, "weight": 0.48, "proportions": 0.6, "height": 0.6,
                "caucasian": 0.82, "african": 0.03, "asian": 0.15},
        targets={"nose/nose-hump-incr": 0.35, "nose/nose-scale-vert-incr": 0.2, "eyebrows/eyebrows-trans-down": 0.25,
                 "chin/chin-width-incr": 0.2, "head/head-oval": 0.2, "stomach/stomach-pregnant-decr": 0.3},
        skin="young_caucasian_male", eyes="darkbrown", brows="eyebrow009", hair=HAIR, height_m=1.78)
    k.tint_body_texture((0.93, 0.83, 0.72), gamma=1.12)          # warm olive Mediterranean tone
    k.color_hair((8, 7, 7), (34, 28, 25), gamma=1.5, rough=0.55)
    k.color_hair((10, 8, 7), (40, 32, 28), gamma=1.3, rough=0.7, part="Eyebrows")


def face_marks(k):
    """Nose tip from the rest-pose midline profile (its most forward point); nose base, mouth and
    chin sit at fixed offsets below it on MPFB heads (read off the profile: -15, -28, -79 mm)."""
    co = k.body_rest()
    head = k.rig.matrix_world @ k.rig.data.bones["head"].head_local
    mid = co[(np.abs(co[:, 0]) < 0.006) & (co[:, 1] < head.y) & (co[:, 2] > head.z - 0.06) & (co[:, 2] < head.z + 0.06)]
    tip = float(mid[np.argmin(mid[:, 1]), 2])
    return dict(head=head, tip=tip, sn=tip - 0.015, mouth=tip - 0.028, menton=tip - 0.079)


def beard(k):
    F = face_marks(k)
    hy, sn, mo = F["head"].y, F["sn"], F["mouth"]
    neck_z = F["menton"] - 0.022

    def density(P):
        x, y, z = np.abs(P[:, 0]), P[:, 1], P[:, 2]
        # upper edge: moustache under the nose, down to the mouth corners, up the cheek to the sideburn
        top = np.interp(x, [0.0, 0.022, 0.032, 0.048, 0.062, 0.08], [sn - 0.001, sn - 0.003, mo + 0.004, sn - 0.006, sn + 0.012, sn + 0.045])
        # lower edge: a clean neckline just above the Adam's apple, rising back to the ear lobe
        low = np.interp(y, [hy - 0.12, hy - 0.04, hy + 0.01], [neck_z, neck_z + 0.012, sn - 0.03])
        d = smooth(top + 0.002, top - 0.004, z) * smooth(low - 0.004, low + 0.006, z) * smooth(hy + 0.012, hy - 0.004, y)
        # lips stay clear
        lip = ((x / 0.026) ** 2 + ((z - mo) / np.where(z > mo, 0.0085, 0.0095)) ** 2) < 1.0
        d = np.where(lip, 0.0, d)
        # moustache and chin goatee denser, cheeks shorter
        dense = smooth(0.045, 0.028, x)
        return d * (0.42 + 0.48 * dense)

    def region(co):
        return (co[:, 2] > neck_z - 0.03) & (co[:, 2] < sn + 0.08) & (co[:, 1] < hy + 0.03) & (np.abs(co[:, 0]) < 0.1)
    return k.paint_skin(density, (16, 12, 11), region, seed=11), F


def arm_hair(k):
    """Sparse dark hair on the forearms (back of the arm)."""
    segs = []
    for s in ("l", "r"):
        a, d = k.bone_pt("lowerarm_" + s, 0.0)
        b, _ = k.bone_pt("lowerarm_" + s, 0.95)
        segs.append((np.array(a, np.float32), np.array(b, np.float32)))

    def density(P):
        out = np.zeros(len(P), np.float32)
        for a, b in segs:
            ab = b - a
            t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
            near = np.linalg.norm(P - (a + t[:, None] * ab), axis=1) < 0.06
            out = np.maximum(out, near * smooth(0.0, 0.25, t) * smooth(1.0, 0.85, t) * 0.32)
        return out

    def region(co):
        m = np.zeros(len(co), bool)
        for a, b in segs:
            ab = b - a
            t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1)
            m |= np.linalg.norm(co - (a + t[:, None] * ab), axis=1) < 0.07
        return m
    return k.paint_skin(density, (22, 16, 13), region, seed=12, grain=0)


def landmarks(k):
    r = k.rig
    def head(b): return r.matrix_world @ r.data.bones[b].head_local
    L = dict(hip=head("thigh_l").z, knee=head("calf_l").z, ankle=head("foot_l").z, waist=head("spine_01").z,
             chest=head("spine_03").z, neck=head("neck_01").z, neck_y=head("neck_01").y, shoulder=head("upperarm_l").z)
    L["crotch"] = L["hip"] - 0.075
    return L


def seg_dist(px, pz, a, b):
    """distance from points (px, pz) to the 2D segment a-b (x, z)"""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    t = np.clip(((px - ax) * dx + (pz - az) * dz) / max(dx * dx + dz * dz, 1e-9), 0, 1)
    return np.hypot(px - (ax + t * dx), pz - (az + t * dz))


def build_clothes(k):
    L = landmarks(k)
    TORSO = {"pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "neck_01", "upperarm_l", "upperarm_r"}
    LEGS = {"pelvis", "spine_01", "thigh_l", "thigh_r", "calf_l", "calf_r"}

    # 1) navy crew-neck tee: hem over the jeans waistband, sleeves to mid upper arm, loose sleeves
    hem = L["hip"] + 0.005
    def collar_z(x, y):
        f = np.clip((L["neck_y"] - y) / 0.07, 0, 1) ** 1.5
        return L["neck"] + 0.012 - 0.046 * f * np.clip(1 - (np.asarray(x) / 0.085) ** 2, 0, 1)
    def keep_tee(c, bone):
        return bone in TORSO and hem - 0.02 < c.z < L["neck"] + 0.03
    cuts = [(Vector((0, 0, hem)), Vector((0, 0, -1)), None)]
    for s_ in ("l", "r"):
        p, d = k.bone_pt("upperarm_" + s_, 0.52)
        cuts.append((p, d, {"upperarm_" + s_}))
    tee = k.shell("Tee", keep_tee, cuts, offset=0.010, trims=(lambda c: c.z - float(collar_z(c.x, c.y)),))
    k.hang(tee, z_from=L["chest"] - 0.02, z_band=(hem, L["chest"] - 0.02), axis_y=0.0, x_max=0.19, fade=0.08)
    k.drape_front(tee, z_top=L["neck"] - 0.06, z_bottom=L["waist"] - 0.02, x_max=0.19, slope=0.4)
    arms = {}
    for s_ in ("l", "r"):
        arms[s_] = (k.bone_pt("upperarm_" + s_, 0.0), k.bone_pt("upperarm_" + s_, 0.52)[0])
    def sleeve(co, n):
        s_ = "l" if co.x > 0 else "r"
        (a, d), b = arms[s_]
        t = (co - a).dot(d) / max((b - a).length, 1e-4)
        if t < 0.15 or abs(co.x) < 0.16:
            return Vector((0, 0, 0))
        rad = co - (a + d * (co - a).dot(d))
        if rad.length < 1e-4:
            return Vector((0, 0, 0))
        return rad.normalized() * (0.014 * float(smooth(0.15, 0.6, t)))    # sleeve opens away from the arm
    k.inflate(tee, sleeve)

    # 2) dark grey washed slim jeans: low-mid rise, straight slim leg, hem breaking on the sneaker
    rise = L["waist"] - 0.05
    jhem = L["ankle"] + 0.012
    def keep_jeans(c, bone):
        return bone in LEGS and jhem - 0.03 < c.z < rise + 0.02
    cuts = [(Vector((0, 0, rise)), Vector((0, 0, 1)), None), (Vector((0, 0, jhem)), Vector((0, 0, -1)), lambda c: c.z < L["knee"])]
    jeans = k.shell("Jeans", keep_jeans, cuts, offset=0.006)
    knee_r = {}
    for s_ in ("l", "r"):
        knee_r[s_] = (k.rig.matrix_world @ k.rig.data.bones["calf_" + s_].head_local, k.rig.matrix_world @ k.rig.data.bones["foot_" + s_].head_local)
    def straighten(co, n):
        s_ = "l" if co.x > 0 else "r"
        kc, ac = knee_r[s_]
        if co.z > kc.z + 0.06:
            return Vector((0, 0, 0))
        t = max(0.0, min(1.0, (kc.z - co.z) / max(kc.z - ac.z, 0.1)))
        axis = kc.lerp(ac, t)
        rad = Vector((co.x - axis.x, co.y - axis.y, 0))
        want = 0.060 - 0.010 * t + 0.010 * float(smooth(0.85, 1.0, t))     # slim, then a soft break over the shoe
        w = smooth(kc.z + 0.06, kc.z - 0.04, co.z)
        if rad.length < 1e-4:
            return Vector((0, 0, 0))
        return rad.normalized() * max(0.0, want - rad.length) * float(w)
    k.inflate(jeans, straighten)
    k.bridge_crotch(jeans, L["crotch"])

    # 3) grey knit sneakers (MPFB shoes06, recoloured in materials())
    shoes = k.add_asset("clothes/shoes06/shoes06.mhclo")
    return dict(tee=tee, jeans=jeans, shoes=shoes, L=L, hem=hem, rise=rise, jhem=jhem, collar_z=collar_z)


def materials(k, g):
    L, hem, rise, jhem, collar_z = g["L"], g["hem"], g["rise"], g["jhem"], g["collar_z"]
    # tee: navy slub jersey, ribbed crew collar, twin-needle hems, shoulder seams
    tee = g["tee"]
    k.pattern_uv(tee, lambda c: ("sleeve_l" if c.x > 0 else "sleeve_r") if abs(c.x) > 0.2 else ("front" if c.y < 0 else "back"))
    sleeve_ends = [k.bone_pt("upperarm_" + s_, 0.52) for s_ in ("l", "r")]
    def tee_h(P, N, M):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        h = np.zeros(P.shape[:2], np.float32)
        e = collar_z(x, y) - z                                   # distance below the neckline
        col = (e >= 0) & (e < 0.016)
        h += np.where(col, 0.00022 * np.abs(np.sin(2 * np.pi * np.arctan2(x, y - L["neck_y"]) * 0.07 / 0.0026)), 0)
        h += np.where(np.abs(e - 0.016) < 0.0012, -0.0003, 0)
        for off in (0.018, 0.024):                                # twin-needle hem
            h += np.where(np.abs(z - (hem + off)) < 0.0007, -0.00025, 0)
        for (p, d) in sleeve_ends:
            p = np.array(p, np.float32); d = np.array(d, np.float32)
            along = (P - p) @ d
            side = np.sign(P[..., 0]) == np.sign(p[0])
            for off in (-0.018, -0.024):
                h += np.where(side & (np.abs(along - off) < 0.0007), -0.00025, 0)
        h += np.where((np.abs(np.abs(x) - 0.175) < 0.0012) & (z > L["shoulder"] - 0.02), -0.0003, 0)   # shoulder seams
        return h
    k.paint_fabric(tee, (30, 36, 66), height_fn=tee_h, weave="knit", heather=0.11, rough=0.88, sheen=0.35, seed=21)
    # jeans: dark grey denim, wash on thighs and knees, whiskers, 5 pockets, fly, yoke, loops, rivets
    jeans = g["jeans"]
    k.pattern_uv(jeans, lambda c: ("L" if c.x > 0 else "R") + ("front" if c.y < 0 else "back"))
    def stitches(P):
        """(distance field, kind) for every topstitch line"""
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        front, back = y < -0.01, y > 0.01
        lines = []
        for sx in (1, -1):
            # front scoop pocket opening: waistband at x 0.085 curving out to the side seam
            a = seg_dist(x * sx, z, (0.085, rise - 0.035), (0.11, rise - 0.075))
            b = seg_dist(x * sx, z, (0.11, rise - 0.075), (0.17, rise - 0.095))
            lines.append((np.where(front, np.minimum(a, b), 1), "pocket"))
            # back patch pocket: pentagon outline
            cx, top, bot = 0.075, rise - 0.075, rise - 0.205
            pts = [(cx - 0.065, top), (cx + 0.065, top), (cx + 0.06, bot + 0.02), (cx, bot), (cx - 0.06, bot + 0.02), (cx - 0.065, top)]
            d = np.min([seg_dist(x * sx, z, pts[i], pts[i + 1]) for i in range(5)], axis=0)
            lines.append((np.where(back, d, 1), "pocket"))
            # yoke seam across the back
            lines.append((np.where(back, seg_dist(x * sx, z, (0.0, rise - 0.075), (0.17, rise - 0.045)), 1), "seam"))
        # fly J-stitch (wearer's left of centre)
        fly = np.minimum(seg_dist(x, z, (0.032, rise - 0.035), (0.032, L["crotch"] + 0.06)),
                         seg_dist(x, z, (0.032, L["crotch"] + 0.06), (0.004, L["crotch"] + 0.035)))
        lines.append((np.where(front, fly, 1), "seam"))
        lines.append((np.abs(z - (rise - 0.035)), "seam"))       # waistband
        lines.append((np.abs(z - (jhem + 0.016)), "seam"))       # hem
        return lines
    def jeans_h(P, N, M):
        h = np.zeros(P.shape[:2], np.float32)
        for d, kind in stitches(P):
            h += np.where(d < 0.0012, -0.0004, 0)
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        ang = np.arctan2(x, -y)
        wb = z > rise - 0.035
        for a in (-2.7, -1.3, -0.45, 0.45, 1.3, 2.7, np.pi):
            loop = wb & (np.abs(np.angle(np.exp(1j * (ang - a)))) * 0.16 < 0.006)
            h += np.where(loop, 0.0007, 0)
        return h
    def jeans_c(P, N, M, rgb, r):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        front = y < -0.01
        # wash: lighter on the thigh fronts and knees, whiskers at the hips, darker behind the knee
        thigh = front & (z > L["knee"] - 0.05) & (z < L["crotch"])
        wash = np.where(thigh, 0.22 * smooth(L["knee"] - 0.05, L["knee"] + 0.12, z) * smooth(L["crotch"], L["crotch"] - 0.08, z), 0)
        wash += np.where(front, 0.12 * np.exp(-((z - L["knee"]) / 0.05) ** 2), 0)
        for i in range(5):
            wz = L["crotch"] + 0.012 - i * 0.016
            dz = z - (wz - 0.12 * (np.abs(x) - 0.05))
            whisker = front & (np.abs(x) > 0.04) & (np.abs(x) < 0.12 - i * 0.012)
            wash += np.where(whisker, 0.07 * (1 - i * 0.18) * np.exp(-(dz / 0.004) ** 2) * smooth(0.04, 0.07, np.abs(x)), 0)
        wash -= np.where(~front & (np.abs(z - L["knee"]) < 0.04), 0.08, 0)
        rgb = np.clip(rgb * (1 + wash)[..., None], 0, 1)
        for d, kind in stitches(P):
            th = d < 0.0009
            rgb[th] = rgb[th] * 0.35 + np.array([0.30, 0.30, 0.29]) * 0.65
            r[th] = 0.7
        for sx in (1, -1):                                        # rivets
            for (rx, rz) in ((0.085, rise - 0.037), (0.17, rise - 0.093)):
                m = front & (np.hypot(x * sx - rx, z - rz) < 0.0035)
                rgb[m] = np.array([0.55, 0.55, 0.56])
                r[m] = 0.25
        m = front & (np.hypot(x, z - (rise - 0.018)) < 0.007)    # shank button
        rgb[m] = np.array([0.48, 0.48, 0.5])
        r[m] = 0.2
        return rgb, r
    k.paint_fabric(jeans, (58, 60, 64), height_fn=jeans_h, color_fn=jeans_c, weave="denim", heather=0.10, rough=0.85, sheen=0.15, seed=22)
    # sneakers: blue knit upper -> heathered grey, the logo painted out, sock darkened (under the jeans)
    def sneaker(rgb, a):
        mx, mn = rgb.max(-1), rgb.min(-1)
        sat = (mx - mn) / np.maximum(mx, 1e-4)
        blue = (rgb[..., 2] > rgb[..., 0] * 1.25) & (sat > 0.25)
        lum = rgb @ np.array([0.3, 0.55, 0.15], np.float32)
        grey = np.clip(0.40 + (lum - 0.12) * 1.6, 0.18, 0.75)[..., None] * np.array([0.98, 1.0, 1.02], np.float32)
        out = np.where(blue[..., None], grey, rgb)
        h, w = rgb.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        logo = (xx / w > 0.42) & (xx / w < 0.54) & (1 - yy / h > 0.76) & (1 - yy / h < 0.84)
        if blue.any():
            out[logo] = np.median(grey[blue], axis=0)
        sock = (xx / w > 0.76) & (1 - yy / h > 0.84)
        out[sock] = out[sock] * 0.35
        return out
    k.recolor(g["shoes"], sneaker, "sneakers")


def rig_and_mask(k, g):
    k.rig_garment(g["tee"], thickness=0.002)
    k.rig_garment(g["jeans"], thickness=0.0025)
    return k.hide_under([g["tee"], g["jeans"], g["shoes"]])


def run(stage="all"):
    k = Kit(NAME)
    build_body(k)
    k.pose("rest")
    texels, F = beard(k)
    arm_hair(k)
    g = build_clothes(k)
    materials(k, g)
    n = rig_and_mask(k, g)
    k.pose("t")
    return k, g, n
