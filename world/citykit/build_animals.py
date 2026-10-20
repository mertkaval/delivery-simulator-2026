"""City animals as low-poly part rigs for procedural animation in Godot (AnimalLife).

Every animal faces -Z (Godot forward), y up, metres. Moving parts are separate pieces whose
origin is their pivot: legs hang from the hip, heads turn at the neck, tails wag at the root,
wings flap at the shoulder (wings extend along +X; Godot mirrors them for the left side).
Coat and feather materials are near-white and tinted per animal.

  dog_body / dog_head / dog_leg / dog_tail      medium dog (~0.6 m at the shoulder)
  cat_body / cat_head / cat_leg / cat_tail      house cat
  pigeon_body, crow_body, gull_body, bird_wing  birds (wing shared, scaled and tinted)

Run headless:  blender --background --factory-startup --python build_animals.py
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\GodotProjects\delivery-simulator-2026\world\citykit"
SRC = os.path.join(HERE, "build_restaurants.py")
R = {"__name__": "restaurants_lib", "__file__": SRC, "BUILD": False}
exec(compile(open(SRC).read(), SRC, "exec"), R)
H = R["H"]
H["OUT"] = os.path.join(HERE, "animals")
H["PALETTE"].update({"Fur": ("efe9e0", 0.85), "FurLight": ("f6f3ee", 0.85), "Feather": ("eef0f0", 0.7),
                     "FeatherTip": ("e6e6e6", 0.7), "Beak": ("d9a531", 0.4), "Eye": ("0c0c0c", 0.1),
                     "Nose": ("161616", 0.3), "NeckSheen": ("5f8f6a", 0.3), "Paw": ("3a2e28", 0.8)})
near, prism, blob, loft = H["near"], H["prism"], H["blob"], H["loft"]


def eye(m, x, y, z, r=0.012):
    blob(m, x, y, z, r, r, r, "Eye", seg=6, rings=3)


# ------------------------------------------------------------------------------ dog

def dog_body(m):
    """Torso, chest and neck; hips at (+-0.09, 0.42, +-0.25), neck top at (0, 0.62, -0.36)."""
    blob(m, 0, 0.45, 0.02, 0.15, 0.15, 0.36, "Fur", seg=12, rings=7, seed=0.3)
    blob(m, 0, 0.47, -0.22, 0.15, 0.17, 0.16, "Fur", seg=10, rings=6, seed=0.8)
    blob(m, 0, 0.4, -0.12, 0.11, 0.08, 0.2, "FurLight", seg=10, rings=4, seed=1.1)  # belly
    loft(m, [(0, 0.5, -0.3, 0.09, 0.1), (0, 0.6, -0.36, 0.08, 0.09), (0, 0.66, -0.4, 0.07, 0.08)], "Fur", n=10)
    if near():
        loft(m, [(0, 0.52, -0.31, 0.1, 0.11), (0, 0.55, -0.32, 0.1, 0.11)], "AccentPaint", n=10)  # collar


def dog_head(m):
    """Head pivoting at the neck top: skull, muzzle, nose, floppy ears, eyes."""
    blob(m, 0, 0.06, -0.05, 0.1, 0.1, 0.12, "Fur", seg=10, rings=6, seed=0.2)
    loft(m, [(0, 0.02, -0.13, 0.055, 0.05), (0, 0.0, -0.22, 0.045, 0.04), (0, -0.005, -0.25, 0.035, 0.03)], "FurLight", n=8)
    blob(m, 0, 0.01, -0.255, 0.025, 0.02, 0.02, "Nose", seg=6, rings=3)
    for sx in (-1, 1):
        prism(m, (sx * 0.08, 0.12, -0.03), (sx * 0.11, -0.02, 0.0), 0.07, 0.02, "Fur", up=(sx, 0, 0))
        eye(m, sx * 0.045, 0.08, -0.15, 0.014)


def dog_leg(m):
    """Leg hanging from its pivot (hip/shoulder) to the paw on the ground 0.42 m below."""
    loft(m, [(0, -0.42, 0.0, 0.035, 0.035), (0, -0.25, 0.01, 0.04, 0.045), (0, -0.06, 0.0, 0.06, 0.07), (0, 0.02, 0, 0.055, 0.06)], "Fur", n=8)
    blob(m, 0, -0.41, -0.025, 0.04, 0.025, 0.055, "FurLight", seg=6, rings=3)


def dog_tail(m):
    """Tail from its root curving up and back (+z)."""
    prism(m, (0, 0, 0), (0, 0.1, 0.16), 0.05, 0.05, "Fur")
    prism(m, (0, 0.1, 0.16), (0, 0.22, 0.24), 0.035, 0.035, "FurLight")


# ------------------------------------------------------------------------------ cat

def cat_body(m):
    """Slender cat torso; hips at (+-0.05, 0.2, +-0.13), neck top at (0, 0.28, -0.17)."""
    blob(m, 0, 0.22, 0.0, 0.08, 0.085, 0.2, "Fur", seg=10, rings=6, seed=0.5)
    blob(m, 0, 0.2, 0.0, 0.06, 0.05, 0.14, "FurLight", seg=8, rings=4, seed=1.4)
    loft(m, [(0, 0.24, -0.15, 0.05, 0.05), (0, 0.29, -0.18, 0.045, 0.045)], "Fur", n=8)


def cat_head(m):
    blob(m, 0, 0.04, -0.03, 0.065, 0.058, 0.06, "Fur", seg=10, rings=6, seed=0.9)
    blob(m, 0, 0.02, -0.08, 0.03, 0.025, 0.025, "FurLight", seg=6, rings=3)
    blob(m, 0, 0.03, -0.1, 0.008, 0.006, 0.006, "Nose", seg=5, rings=3)
    for sx in (-1, 1):
        m.face([(sx * 0.02, 0.08, -0.03), (sx * 0.06, 0.08, -0.02), (sx * 0.048, 0.13, -0.025)], "Fur", (0, 0.3, -1))
        m.face([(sx * 0.02, 0.08, -0.02), (sx * 0.06, 0.08, -0.01), (sx * 0.048, 0.13, -0.015)], "Fur", (0, 0.3, 1))
        eye(m, sx * 0.028, 0.05, -0.075, 0.01)
        if near():
            for k in (-1, 1):
                prism(m, (sx * 0.02, 0.02, -0.095), (sx * 0.08, 0.02 + k * 0.012, -0.09), 0.002, 0.002, "FurLight")  # whiskers


def cat_leg(m):
    loft(m, [(0, -0.2, 0.0, 0.018, 0.02), (0, -0.1, 0.0, 0.022, 0.025), (0, 0.01, 0.0, 0.03, 0.035)], "Fur", n=6)
    blob(m, 0, -0.195, -0.012, 0.022, 0.014, 0.03, "FurLight", seg=6, rings=3)


def cat_tail(m):
    pts = [(0, 0, 0), (0, 0.06, 0.1), (0, 0.18, 0.16), (0, 0.3, 0.14), (0, 0.36, 0.08)]
    for i in range(len(pts) - 1):
        prism(m, pts[i], pts[i + 1], 0.03 - i * 0.004, 0.03 - i * 0.004, "Fur")


# ------------------------------------------------------------------------------ birds

def bird_body(m, size, beak_len, neck_sheen, tail_len):
    """Plump body with head, beak, eyes, tail and legs; shoulders at (+-0.6*size, 0.15*size, -0.02)."""
    s = size
    blob(m, 0, 0.12 * s, 0.0, 0.075 * s, 0.07 * s, 0.13 * s, "Feather", seg=10, rings=6, seed=0.4)
    blob(m, 0, 0.21 * s, -0.09 * s, 0.045 * s, 0.045 * s, 0.05 * s, "Feather", seg=8, rings=5, seed=0.2)
    if neck_sheen:
        blob(m, 0, 0.17 * s, -0.07 * s, 0.052 * s, 0.04 * s, 0.045 * s, "NeckSheen", seg=8, rings=4, seed=1.2)
    prism(m, (0, 0.205 * s, -0.13 * s), (0, 0.195 * s, -(0.13 + beak_len) * s), 0.018 * s, 0.016 * s, "Beak")
    for sx in (-1, 1):
        eye(m, sx * 0.03 * s, 0.22 * s, -0.11 * s, 0.008 * s)
        prism(m, (sx * 0.025 * s, 0.07 * s, 0.0), (sx * 0.025 * s, 0.0, -0.01 * s), 0.01 * s, 0.01 * s, "Beak")  # legs
    prism(m, (0, 0.13 * s, 0.1 * s), (0, 0.1 * s, (0.1 + tail_len) * s), 0.08 * s, 0.015 * s, "FeatherTip")


def pigeon_body(m):
    bird_body(m, 1.0, 0.03, True, 0.1)


def crow_body(m):
    bird_body(m, 1.35, 0.07, False, 0.13)


def gull_body(m):
    bird_body(m, 1.5, 0.06, False, 0.08)


def bird_wing(m):
    """Right wing from the shoulder pivot along +x: covert panel and a fringe of primaries."""
    pts = [(0, 0, -0.04), (0.16, 0.005, -0.05), (0.27, 0.0, -0.02), (0.27, 0.0, 0.03), (0.12, 0.0, 0.07), (0, 0, 0.06)]
    m.face(pts, "Feather", (0, 1, 0))
    m.face(list(reversed(pts)), "Feather", (0, -1, 0))
    tip = [(0.2, 0.002, -0.035), (0.36, 0.0, 0.0), (0.33, 0.0, 0.05), (0.2, 0.002, 0.045)]
    m.face(tip, "FeatherTip", (0, 1, 0))
    m.face(list(reversed(tip)), "FeatherTip", (0, -1, 0))


PIECES = {"dog_body": dog_body, "dog_head": dog_head, "dog_leg": dog_leg, "dog_tail": dog_tail,
          "cat_body": cat_body, "cat_head": cat_head, "cat_leg": cat_leg, "cat_tail": cat_tail,
          "pigeon_body": pigeon_body, "crow_body": crow_body, "gull_body": gull_body, "bird_wing": bird_wing}
H["ALL"].clear()
H["ALL"].update(PIECES)
H["HOUSES"].clear()
H["HOUSES"].update(PIECES)

if globals().get("PREVIEW"):
    print(H["preview"](globals().get("NAMES"), spacing=globals().get("SPACING", 1.0)))
elif globals().get("BUILD", True):
    H["build"](globals().get("NAMES"), globals().get("BAKE", True))
