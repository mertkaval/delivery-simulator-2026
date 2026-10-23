"""NPC01 - middle-aged woman: burgundy knit cardigan over a cream scoop-neck top, charcoal
pressed trousers, black ballet flats, short natural afro.  Run inside Blender (live or headless)."""
import bpy, math, os
import numpy as np
from mathutils import Vector

KIT = r"C:\GodotProjects\delivery-simulator-2026\tools\npc\npc_kit.py"
ns = {}
exec(open(KIT, encoding="utf-8").read(), ns)
Kit, smooth = ns["Kit"], ns["smooth"]

NAME = "NPC01_MiddleAgedWoman"


def build_body(k):
    k.human(
        macros={"gender": 0.0, "age": 0.69, "muscle": 0.42, "weight": 0.58, "proportions": 0.55, "height": 0.45,
                "cupsize": 0.42, "firmness": 0.5, "african": 0.92, "caucasian": 0.05, "asian": 0.03},
        targets={"head/head-round": 0.25, "nose/nose-flaring-incr": 0.3, "nose/nose-width1-incr": 0.25,
                 "cheek/l-cheek-volume-incr": 0.15, "cheek/r-cheek-volume-incr": 0.15, "stomach/stomach-pregnant-incr": 0.15},
        skin="middleage_african_female", eyes="brown", brows="eyebrow006", hair="afro01", height_m=1.64)
    k.tint_body_texture((0.80, 0.76, 0.76), gamma=1.05)
    k.color_hair((14, 10, 9), (52, 40, 33), gamma=1.6, rough=0.75)


def landmarks(k):
    r = k.rig
    def head(b): return r.matrix_world @ r.data.bones[b].head_local
    def tail(b): return r.matrix_world @ r.data.bones[b].tail_local
    L = dict(hip=head("thigh_l").z, knee=head("calf_l").z, ankle=head("foot_l").z, waist=head("spine_01").z,
             chest=head("spine_03").z, neck=head("neck_01").z, shoulder=head("upperarm_l").z)
    L["crotch"] = L["hip"] - 0.07
    return L


def build_clothes(k):
    L = landmarks(k)
    TORSO = {"pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "neck_01", "upperarm_l", "upperarm_r"}
    ARMS = {"upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r"}
    LEGS = {"pelvis", "spine_01", "thigh_l", "thigh_r", "calf_l", "calf_r"}
    neck_n = Vector((0, -0.25, 1)).normalized()

    # 1) cream scoop-neck top, short cap sleeves; hem just over the trouser waistband
    scoop_low, scoop_top, scoop_w = L["neck"] - 0.085, L["neck"] - 0.012, 0.075
    rise = L["waist"] - 0.035                              # trouser waist (mid-rise)
    top_hem = rise - 0.015                                 # top ends just inside the waistband
    def keep_top(c, bone):
        return bone in TORSO and top_hem - 0.02 < c.z < scoop_top + 0.01
    # U-scoop neckline (half-ellipse) on the front, fading out over the shoulders
    cuts = [(Vector((0, 0, scoop_top)), Vector((0, 0, 1)), None), (Vector((0, 0, top_hem)), Vector((0, 0, -1)), None)]
    def scoop(c):
        u = min(abs(c.x) / scoop_w, 1.0)
        line = scoop_low + (scoop_top - scoop_low) * (1 - math.sqrt(1 - u * u))
        f = float(smooth(0.0, -0.05, c.y))
        return c.z - (scoop_top - (scoop_top - line) * f) if f > 0 else -1.0
    for s in ("l", "r"):
        p, d = k.bone_pt("upperarm_" + s, 0.22)
        cuts.append((p, d, {"upperarm_" + s}))
    top = k.shell("Top", keep_top, cuts, offset=0.003, trims=(scoop,))
    k.drape_front(top, z_top=L["neck"] - 0.07, z_bottom=L["waist"] - 0.03)

    # 2) burgundy cardigan worn open: long sleeves to the wrist, front edges ~12 cm apart at the
    #    bust widening to the hem, shallow V into the back-neck collar
    hem = L["hip"] - 0.005
    def keep_cardi(c, bone):
        if bone not in TORSO | ARMS or c.z < hem - 0.02:
            return False
        if bone == "neck_01" and c.z > L["neck"] + 0.01:
            return False
        return True
    cuts = [(Vector((0, 0, L["neck"] + 0.012)), neck_n, None), (Vector((0, 0, hem)), Vector((0, 0, -1)), lambda c: abs(c.x) < 0.24)]
    for s in ("l", "r"):
        p, d = k.bone_pt("lowerarm_" + s, 0.97)
        cuts.append((p, d, {"lowerarm_" + s}))
    cardi = k.shell("Cardigan", keep_cardi, cuts, offset=0.009)
    k.hang(cardi, z_from=L["waist"] - 0.02, z_band=(hem, L["waist"] - 0.02), axis_y=0.0, x_max=0.19, fade=0.06)
    k.drape_front(cardi, z_top=L["neck"] - 0.07, z_bottom=L["waist"] - 0.03, x_max=0.2)
    zs, ws = [hem, 1.19 - 1.357 + L["neck"], L["neck"] + 0.02], [0.088, 0.063, 0.074]
    edge_w = lambda z: np.interp(z, zs, ws)                 # half-width of the front opening
    k.trim(cardi, lambda c: float(edge_w(c.z)) * float(smooth(-0.01, -0.05, c.y)) - abs(c.x))

    # 3) charcoal trousers: mid-rise waist to ankle, straight legs below the knee
    def keep_trousers(c, bone):
        return bone in LEGS and L["ankle"] - 0.02 < c.z < rise + 0.02
    cuts = [(Vector((0, 0, rise)), Vector((0, 0, 1)), None)]
    for s in ("l", "r"):
        p, d = k.bone_pt("calf_" + s, 0.93)
        cuts.append((p, d, {"calf_" + s}))
    trousers = k.shell("Trousers", keep_trousers, cuts, offset=0.006)
    knee_r = {}
    for s, sx in (("l", 1), ("r", -1)):
        kc = k.rig.matrix_world @ k.rig.data.bones["calf_" + s].head_local
        ac = k.rig.matrix_world @ k.rig.data.bones["foot_" + s].head_local
        knee_r[s] = (kc, ac)
    def straighten(co, n):
        s = "l" if co.x > 0 else "r"
        kc, ac = knee_r[s]
        if co.z > kc.z + 0.05:
            return Vector((0, 0, 0))
        t = max(0.0, min(1.0, (kc.z - co.z) / max(kc.z - ac.z, 0.1)))
        axis = kc.lerp(ac, t)
        rad = Vector((co.x - axis.x, co.y - axis.y, 0))
        want = 0.068 - 0.010 * t          # straight, slightly tapering trouser leg
        w = smooth(kc.z + 0.05, kc.z - 0.05, co.z)
        if rad.length < 1e-4:
            return Vector((0, 0, 0))
        return rad.normalized() * max(0.0, want - rad.length) * float(w)
    k.inflate(trousers, straighten)
    k.bridge_crotch(trousers, L["crotch"])

    # 4) ballet flats: smooth shoe last (no toe shapes), low heel counter, vamp over the toe joints
    flats = k.shoe("Flats", heel_z=0.046, slope=0.17, offset=0.0025)
    return dict(top=top, cardi=cardi, trousers=trousers, flats=flats, L=L, hem=hem, edge_w=edge_w, rise=rise)


def materials(k, g):
    L = g["L"]
    sm = smooth
    # cream top: fine jersey knit
    k.pattern_uv(g["top"], lambda c: "front" if c.y < 0.0 else "back")
    k.paint_fabric(g["top"], (232, 225, 210), weave="twill", heather=0.03, rough=0.9, sheen=0.3, size=1024, seed=2)
    # cardigan: burgundy heather knit with ribbed cuffs and hem band, button placket, patch pockets
    cardi = g["cardi"]
    def cardi_label(c):
        if abs(c.x) > 0.19 and c.z > L["chest"] - 0.12:
            return "sleeve_l" if c.x > 0 else "sleeve_r"
        return "front_l" if (c.y < 0.0 and c.x > 0) else ("front_r" if c.y < 0.0 else "back")
    k.pattern_uv(cardi, cardi_label)
    hem, edge_w, rise = g["hem"], g["edge_w"], g["rise"]
    pockets = [(sx * 0.145, L["hip"] + 0.115) for sx in (1, -1)]      # patch pockets (x, z centre)
    btn_z = np.linspace(hem + 0.018, L["neck"] - 0.165, 7)

    def band(P):
        """distance outward from the front opening edge, front panels only (<0 off the band)"""
        front = P[..., 1] < -0.045
        return np.where(front, np.abs(P[..., 0]) - edge_w(P[..., 2]), -1.0)

    def cardi_h(P, N, M):
        h = np.zeros(P.shape[:2], np.float32)
        z = P[..., 2]
        # ribbed hem band and cuffs (ribs run along the length of the garment)
        hb = z < hem + 0.04
        h += np.where(hb, 0.00022 * np.abs(np.sin(2 * np.pi * np.arctan2(P[..., 0], -P[..., 1]) * 0.16 / 0.0042)), 0)
        h += np.where(np.abs(z - (hem + 0.04)) < 0.0015, -0.00025, 0)
        for s in ("l", "r"):
            p, d = k.bone_pt("lowerarm_" + s, 0.97)
            p = np.array(p, np.float32); d = np.array(d, np.float32)
            along = (P - p) @ d
            side = (P[..., 0] > 0) == (s == "l")
            cuff = (along > -0.065) & (along < 0.0) & side
            h += np.where(cuff, 0.00022 * np.abs(np.sin(2 * np.pi * np.arctan2(P[..., 1], P[..., 2] - p[2]) * 0.045 / 0.0035)), 0)
            h += np.where(side & (np.abs(along + 0.065) < 0.0015), -0.00025, 0)
        # front band along the opening (fine cross-ribs), seam line at its inner edge
        e = band(P)
        on = (e >= 0) & (e < 0.021)
        h += np.where(on, 0.00025 + 0.00012 * np.abs(np.sin(2 * np.pi * z / 0.0032)), 0)
        h += np.where(np.abs(e - 0.021) < 0.0013, -0.0003, 0)
        # patch pockets with a ribbed top band
        front = P[..., 1] < -0.02
        for px, pz in pockets:
            d = np.maximum(np.abs(P[..., 0] - px) - 0.042, np.abs(z - pz) - 0.05)
            inside = front & (d < 0)
            h += np.where(inside, 0.0003, 0) + np.where(front & (np.abs(d) < 0.0012), -0.00025, 0)
            top = inside & (z > pz + 0.05 - 0.016)
            h += np.where(top, 0.00015 * np.abs(np.sin(2 * np.pi * P[..., 0] / 0.0042)), 0)
        # buttonholes on the wearer's right band
        for bz in btn_z:
            hole = (P[..., 0] < 0) & on & (np.abs(e - 0.0105) < 0.0012) & (np.abs(z - bz) < 0.007)
            h += np.where(hole, -0.0005, 0)
        return h

    def cardi_c(P, N, M, rgb, r):
        e = band(P)
        z = P[..., 2]
        for bz in btn_z:                       # dark horn buttons on the wearer's left band
            d = np.sqrt((e - 0.0105) ** 2 + (z - bz) ** 2)
            b = (P[..., 0] > 0) & (e >= 0) & (d < 0.0068)
            ring = d[b] / 0.0068
            rgb[b] = np.array([0.075, 0.050, 0.042]) * (0.75 + 0.5 * ring)[:, None]
            holes = b & (np.minimum(np.hypot(np.abs(e - 0.0105) - 0.0018, np.abs(z - bz) - 0.0018), 1) < 0.0009)
            rgb[holes] *= 0.3
            r[b] = 0.3
        # seams read at a distance: shade the pocket outlines and the band's inner edge
        front = P[..., 1] < -0.02
        for px, pz in pockets:
            d = np.maximum(np.abs(P[..., 0] - px) - 0.042, np.abs(z - pz) - 0.05)
            rgb[front & (np.abs(d) < 0.002)] *= 0.62
            rgb[front & (d < 0) & (d > -0.006)] *= 0.88
        rgb[np.abs(e - 0.021) < 0.0016] *= 0.7
        rgb[np.abs(z - (hem + 0.04)) < 0.0016] *= 0.75
        return rgb, r
    k.paint_fabric(cardi, (64, 13, 22), height_fn=cardi_h, color_fn=cardi_c, weave="knit", heather=0.09, rough=0.92, sheen=0.25, seed=4)
    # trousers: charcoal twill, pressed front crease, waistband with belt loops, slant pockets, fly
    tr = g["trousers"]
    k.pattern_uv(tr, lambda c: ("L" if c.x > 0 else "R") + ("front" if c.y < 0 else "back"))
    def tr_h(P, N, M):
        h = np.zeros(P.shape[:2], np.float32)
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        for s, sx in (("l", 1), ("r", -1)):
            kc = k.rig.matrix_world @ k.rig.data.bones["calf_" + s].head_local
            crease = (np.abs(x - kc.x) < 0.0025) & (y < kc.y - 0.02) & (np.sign(x) == sx) & (z < rise - 0.06)
            h += np.where(crease, 0.0006 * (1 - np.abs(x - kc.x) / 0.0025), 0)
            # slant pocket opening: waistband at x=0.085 down to the side seam
            t = np.clip((rise - 0.035 - z) / 0.12, 0, 1)
            lx = sx * (0.085 + 0.065 * t)
            pk = (y < -0.02) & (z < rise - 0.035) & (z > rise - 0.155) & (np.abs(x - lx) < 0.0016)
            h += np.where(pk, -0.0005, 0)
        wb = z > rise - 0.035
        h += np.where(np.abs(z - (rise - 0.035)) < 0.0018, -0.0004, 0) + np.where(wb, 0.0001, 0)
        ang = np.arctan2(x, -y)
        for a in (-2.6, -1.25, -0.55, 0.55, 1.25, 2.6, np.pi):
            loop = wb & (np.abs(np.angle(np.exp(1j * (ang - a)))) * 0.15 < 0.005)
            h += np.where(loop, 0.0006, 0)
        fly = (y < -0.05) & (np.abs(x - 0.022) < 0.0014) & (z > L["crotch"] + 0.04) & (z < rise - 0.035)
        h += np.where(fly, -0.0003, 0)
        return h
    k.paint_fabric(tr, (46, 46, 48), height_fn=tr_h, weave="twill", heather=0.06, rough=0.78, sheen=0.25, seed=6)
    # flats: black leather
    k.flats_mat = k.plain("M_%s_Flats" % k.name, (14, 14, 15), rough=0.32, coat=0.25)
    g["flats"].data.materials.clear()
    g["flats"].data.materials.append(k.flats_mat)


def rig_and_mask(k, g):
    k.rig_garment(g["top"], thickness=0.0015)
    k.rig_garment(g["cardi"], thickness=0.003)
    k.rig_garment(g["trousers"], thickness=0.002)
    k.rig_garment(g["flats"], thickness=0.0025)
    return k.hide_under([g["top"], g["cardi"], g["trousers"], g["flats"]],
                        open_fn=lambda go, co: not (go == g["top"] and co.z < 1.0))


def run(stage="all"):
    k = Kit(NAME)
    build_body(k)
    k.pose("rest")
    k.skin_detail(k.face_marks(), age=0.65, ao_strength=0.5, lips_mul=(0.9, 0.8, 0.8), lips_desat=0.25)
    g = build_clothes(k)
    materials(k, g)
    n = rig_and_mask(k, g)
    k.pose("t")
    return k, g, n
