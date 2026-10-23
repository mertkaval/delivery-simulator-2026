"""Build one NPC from its spec (tools/npc/people.py) with the MPFB body, hair, face detail and the
garment library (tools/npc/garments.py); render QA views, save the master .blend.

  blender --background --python tools/npc/build_npc.py -- <person_id> [render|norender]
  (no --factory-startup: MPFB is a user extension)
Inside a live Blender: ns = {}; exec(open(BUILD).read(), ns); ns["build"]("concierge")
"""
import bpy, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix

HERE = r"C:\GodotProjects\delivery-simulator-2026\tools\npc"
_g = {}
exec(open(os.path.join(HERE, "garments.py"), encoding="utf-8").read(), _g)
Kit, smooth, Outfit, Decal, finish = _g["Kit"], _g["smooth"], _g["Outfit"], _g["Decal"], _g["finish"]
_p = {}
exec(open(os.path.join(HERE, "people.py"), encoding="utf-8").read(), _p)
PEOPLE = _p["PEOPLE"]

# ------------------------------------------------------------------ hair
MALE_LINE = ([0, 25, 45, 62, 72, 80, 88, 104, 116, 140, 180], [40, 37, 30, 18, -20, -14, 19, 19, -8, -26, -36])
FEMALE_LINE = ([0, 25, 45, 62, 74, 86, 104, 116, 140, 180], [38, 35, 28, 16, 4, 16, 16, -8, -26, -34])


def card_style(style):
    """(hairline, length(az, el), flow(az, el) -> (target, lift), n_cards, card width) of a short cut."""
    if style == "fade":                       # 6-7 cm swept-up top, faded back and sides
        top, side, lift_front, lift = 0.064, 0.008, 0.12, 0.06
    elif style == "classic":                  # side-parted 3-4 cm top, short tapered sides
        top, side, lift_front, lift = 0.04, 0.012, 0.03, 0.03
    elif style == "crop":                     # 2 cm all over
        top, side, lift_front, lift = 0.022, 0.012, 0.02, 0.02
    elif style == "buzz":
        top, side, lift_front, lift = 0.008, 0.006, 0.0, 0.0
    elif style == "curly_short":              # older lady's short set curls
        top, side, lift_front, lift = 0.045, 0.035, 0.25, 0.25
    else:
        raise ValueError(style)
    def length(az, el):
        L = np.interp(el, [-40, 0, 10, 18, 28, 40, 60], [side * 0.8, side, side * 1.3, side * 2.5 if top > 0.03 else side * 1.4, top * 0.65, top * 0.95, top])
        return L * (1 - 0.3 * smooth(70, 170, az)) * (1 - 0.15 * smooth(35, 5, az))
    def flow(az, el):
        k_top = float(smooth(14, 30, el))
        front = float(smooth(70, 20, az))
        if style == "classic":
            t = Vector((0.45, 1.0, 0.05))     # combed back and over to one side
        else:
            t = Vector((0.0, 1.0, 0.08))
        target = t * k_top + Vector((0.2, 0.45, -1.0)) * (1 - k_top)
        return target, lift + k_top * lift_front * front
    n = {"fade": 1700, "classic": 1600, "crop": 1500, "buzz": 1300, "curly_short": 1500}[style]
    width = (0.011, 0.019) if style != "buzz" else (0.006, 0.01)
    return length, flow, n, width


def tied_style(k, F, C, kind):
    """Sleek hair drawn back to a gather point G (bun / ponytail), returns (length, flow, G)."""
    eye_z = float((F["eye_l"][2] + F["eye_r"][2]) / 2)
    G = {"bun_high": Vector((0, C.y + 0.075, eye_z + 0.11)), "bun_low": Vector((0, C.y + 0.095, eye_z - 0.0)),
         "ponytail": Vector((0, C.y + 0.098, eye_z + 0.045))}[kind]
    def length(az, el):
        return 0.06
    def flow(az, el):
        return None, 0.015                    # the direction is set per card (towards G)
    return length, flow, G


def make_hair(k, F, hair, ear):
    style = hair["style"]
    dark, light = hair.get("dark", (12, 10, 9)), hair.get("light", (52, 44, 40))
    if style.startswith("mpfb:"):
        return None
    C, eye_z = k.head_frame(F)
    line = FEMALE_LINE if k.body_gender < 0.5 else MALE_LINE
    base = k.scalp_density(C, line)
    dens = lambda P: base(P) * (1 - ear(P))
    def shade(P):
        az, el = k.scalp_angles(P, C)
        return dens(P) * (0.82 + 0.16 * smooth(0, 25, el))
    k.paint_skin(shade, tuple(int(c * 0.8) for c in dark), lambda co: co[:, 2] > eye_z - 0.09, seed=13)
    if style.startswith(("bun", "ponytail")):
        _, _, G = tied_style(k, F, C, style)
        def length(az, el):
            return 0.2
        k.hair_cards(F, dens, length, None, n_cards=2000, width=(0.009, 0.014), segs=6, dark=dark, light=light, gather=G)
        k.hair_tie(G, style, dark, light)
    else:
        length, flow, n, width = card_style(style)
        card_dens = lambda P: dens(P) * smooth(7, 22, k.scalp_angles(P, C)[1]) if style in ("fade",) else dens(P)
        k.hair_cards(F, card_dens, length, flow, n_cards=n, width=width, dark=dark, light=light)
    return C


BEARDS = {"none": None, "stubble": (0.0, 0.18, 0.05), "short": (0.28, 0.40, 0.05), "full": (0.55, 0.35, 0.06),
          "moustache": (0.0, 0.0, 0.0)}


def make_beard(k, F, kind, rgb, ear):
    if kind in (None, "none"):
        return None
    hy, sn, mo = F["head"].y, F["sn"], F["mouth"]
    neck_z = F["menton"] - 0.022
    cheek, extra, shadow_amt = BEARDS[kind] if kind in BEARDS else BEARDS["short"]
    only_moustache = kind == "moustache"
    def density(P):
        x, y, z = np.abs(P[:, 0]), P[:, 1], P[:, 2]
        top = np.interp(x, [0.0, 0.022, 0.032, 0.048, 0.062, 0.08], [sn - 0.001, sn - 0.003, mo + 0.004, sn - 0.006, sn + 0.012, sn + 0.045])
        low = np.interp(y, [hy - 0.12, hy - 0.04, hy + 0.01], [neck_z, neck_z + 0.012, sn - 0.03])
        d = smooth(top + 0.002, top - 0.004, z) * smooth(low - 0.008, low + 0.012, z) * smooth(hy + 0.012, hy - 0.004, y)
        lip = ((x / 0.026) ** 2 + ((z - mo) / np.where(z > mo, 0.0042, 0.0095)) ** 2) < 1.0
        d = np.where(lip, 0.0, d)
        dense = smooth(0.045, 0.028, x)
        if only_moustache:
            m = (z > mo) & (x < 0.03) & (z < sn)
            return np.where(m, 0.75 * smooth(0.034, 0.024, x), 0.0) * (1 - ear(P))
        if kind == "stubble":
            return (d * (0.16 + 0.1 * dense)) * (1 - ear(P))
        shadow = shadow_amt * smooth(top + 0.018, top, z) * smooth(low - 0.008, low + 0.012, z) * smooth(hy + 0.012, hy - 0.004, y) * (~lip)
        return np.maximum(d * (cheek + extra * dense), shadow) * (1 - ear(P))
    def region(co):
        return (co[:, 2] > neck_z - 0.03) & (co[:, 2] < sn + 0.08) & (co[:, 1] < hy + 0.03) & (np.abs(co[:, 0]) < 0.1)
    k.paint_skin(density, rgb, region, seed=11)
    return density


# softer, more feminine head on top of MPFB's female macro (narrower jaw and chin, finer nose,
# higher arched brows, fuller lips); a spec's own targets override these
FEMININE = {"head/head-oval": 0.3, "chin/chin-width-decr": 0.3, "chin/chin-prominent-decr": 0.15, "chin/chin-height-decr": 0.1,
            "nose/nose-scale-horiz-decr": 0.2, "nose/nose-width1-decr": 0.15, "eyebrows/eyebrows-trans-up": 0.25,
            "eyebrows/eyebrows-angle-up": 0.2, "mouth/mouth-lowerlip-volume-incr": 0.15, "mouth/mouth-upperlip-volume-incr": 0.1,
            "cheek/l-cheek-bones-incr": 0.1, "cheek/r-cheek-bones-incr": 0.1, "forehead/forehead-scale-vert-decr": 0.1}


# ------------------------------------------------------------------ build
def build(pid, render=True):
    spec = PEOPLE[pid]
    t0 = time.time()
    name = spec["name"]
    k = Kit(name)
    b = spec["body"]
    targets = dict(FEMININE if b["macros"].get("gender", 0.5) < 0.5 else {})
    targets.update(b.get("targets", {}))
    k.human(macros=b["macros"], targets=targets, skin=b["skin"], eyes=b.get("eyes", "brown"),
            brows=b.get("brows", "eyebrow010" if b["macros"].get("gender", 0.5) < 0.5 else "eyebrow012"), hair=spec["hair"]["style"][5:] if spec["hair"]["style"].startswith("mpfb:") else None,
            height_m=b["height"])
    if b.get("tint"):
        k.tint_body_texture(b["tint"], gamma=b.get("gamma", 1.0))
    hair = spec["hair"]
    if hair["style"].startswith("mpfb:"):
        k.color_hair(hair.get("dark", (12, 10, 9)), hair.get("light", (52, 44, 40)), gamma=1.4, rough=0.6)
    brow = spec.get("brows", {})
    k.color_hair(brow.get("dark", hair.get("dark", (12, 10, 9))), brow.get("light", hair.get("light", (52, 44, 40))), gamma=1.3, rough=0.7,
                 part="Eyebrows", alpha_gamma=brow.get("alpha_gamma", 0.75))
    k.pose("rest")
    F = k.face_marks()
    ear = k.ear_mask(F)
    face = spec.get("face", {})
    bd = make_beard(k, F, face.get("beard", "none"), face.get("beard_rgb", hair.get("dark", (16, 12, 11))), ear)
    if brow.get("paint", 0.0) > 0:
        k.paint_brows(brow.get("dark", (10, 8, 7)), density=brow["paint"], widen=0.5)
    make_hair(k, F, hair, ear)
    k.skin_detail(F, age=face.get("age", 0.3), ao_strength=face.get("ao", 0.6), lips_mul=face.get("lips_mul", (0.9, 0.82, 0.82)),
                  lips_desat=face.get("lips_desat", 0.3), undereye=face.get("undereye", 0.3),
                  beard_zone=(lambda P: bd(P.reshape(-1, 3)).reshape(P.shape[:-1]) > 0.2) if bd else None)
    out = Outfit(k)
    def decal(d):
        d = dict(d)
        if "anchor" in d:                      # centre given as (x or y, offset above a landmark)
            c = d.pop("centre")
            d["centre"] = (c[0], out.L[d.pop("anchor")] + c[1])
        return Decal(**d)
    for item in spec["outfit"]:
        kind, args = item[0], dict(item[1])
        if "decals" in args:
            args["decals"] = [decal(d) for d in args["decals"]]
        out.add(kind, **args)
    masked = finish(k, out)
    k.pose("t")
    print("BUILT %s in %.0fs, masked %d" % (name, time.time() - t0, masked))
    files = []
    if render:
        k.pose("down")
        files = k.render("qa", ("front", "three_quarter", "back", "side", "face"))
        k.pose("t")
    path = k.save()
    print("SAVED", path)
    return k, out, files


if __name__ == "__main__" and "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    build(args[0], render=(len(args) < 2 or args[1] != "norender"))
