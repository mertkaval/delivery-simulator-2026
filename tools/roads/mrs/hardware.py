"""Street-hardware materials for Mert Road Studio (Blender 5.2, headless-safe).

    import mrs.hardware as HW
    mats = HW.build_hardware_materials()     # bakes on first use -> {name: material}

Two texture products, both generated with numpy (periodic spectral noise, periodic Worley cells, so every
pattern is seamless by construction; no Cycles render, ~10 s for everything):

* `MRS_HardwareAtlas` (2048 x 1024, 256 px/m, albedo / ORM / normal PNGs): tiling cells for the streetlights,
  signal poles and heads, sign hardware and barriers (galvanised, painted, die-cast, cast iron, concrete, wood,
  foliage, plastics, reflective sheeting). Some cells are *ground-anchored* (v = height above the object's
  origin: grime, splash and damp only where the part meets the ground), *top-anchored* (streaks under a coping)
  or *edge* variants (chips / worn paint) that `finish()` gives to the chamfer faces of the bevel pass, so wear
  sits only on exposed edges and at ground contact. `MRS_SignalHousing` reads the same images (signal heads keep
  that material name for the signage contract).
* Tileable game materials `MRS_HW_*` (PaintedSteel, Galvanized, Stainless, Concrete, DeckAntiSlip,
  LEDDiffuser): separate seamless textures meant for metre UVs (the footbridge's UVMap = (lateral m, along m)).
  A Mapping node (scale 1 / tile size) on the UV becomes KHR_texture_transform in glTF (Godot: uv1_scale). Faces
  without UVs (Curve to Mesh tubes: every UV is (0, 0)) sample the texture corner, which is blended to the mean
  colour / roughness and a flat normal, so they read as the average material instead of a random texel.
  `MRS_HW_Glass` is a plain alpha-blended Principled (no textures) that the exporter passes through with
  alphaMode BLEND.

Mesh building: `HM` (bmesh + per-face atlas cell or extra material) and `make_object()` / `finish()` (normals,
ground-face removal, chamfers with edge cells, atlas UVs, material slots [atlas] + extras). Every image-textured
material is a plain Principled BSDF fed by Image Texture nodes, so `mrs.export.engine_material` passes it
through and the glTF exporter writes baseColor / metallicRoughness / normal textures.
"""
import json, math, os, random, zlib
import bpy, bmesh
import numpy as np
from mathutils import Vector
from .nodes import MRS

TAU = math.pi * 2.0
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEX_DIR = os.path.join(ROOT, "tmp", "roads", "materials", "hardware")
ATLAS = MRS + "HardwareAtlas"
HOUSING = MRS + "SignalHousing"
GLASS = MRS + "HW_Glass"
AW, AH, PPM = 2048, 1024, 256
BAKE_VERSION = 5
REPORT = {}

# ============================================================================== atlas layout
# name, x, y, w, h (px, top-left origin), mode ("tile" | "ground": v = height above the origin | "top": v anchored at
# the island top), grain ("u" = long side along u), fallback cell (horizontal faces of anchored cells), edge variant
CELLS = [
    ("galv", 0, 0, 512, 256, "tile", None, None, None),
    ("galv_contact", 512, 0, 512, 256, "ground", None, "galv", None),
    ("paint_dark", 1024, 0, 256, 256, "tile", None, None, "paint_dark_edge"),
    ("paint_dark_edge", 1280, 0, 256, 256, "tile", None, None, None),
    ("paint_dark_contact", 1536, 0, 512, 256, "ground", None, "paint_dark", None),
    ("concrete", 0, 256, 512, 256, "tile", None, None, "concrete_edge"),
    ("concrete_contact", 512, 256, 512, 256, "ground", None, "concrete", None),
    ("concrete_edge", 1024, 256, 256, 256, "tile", None, None, None),
    ("concrete_streak", 1280, 256, 512, 256, "top", None, "concrete", None),
    ("alu_cast", 1792, 256, 256, 256, "tile", None, None, "alu_cast_edge"),
    ("stainless", 0, 512, 256, 256, "tile", "u", None, None),
    ("alu_mill", 256, 512, 256, 256, "tile", "u", None, None),
    ("alu_cast_edge", 512, 512, 256, 256, "tile", None, None, None),
    ("iron_black", 768, 512, 256, 256, "tile", None, None, "iron_black_edge"),
    ("iron_black_edge", 1024, 512, 256, 256, "tile", None, None, None),
    ("housing", 1280, 512, 256, 256, "tile", None, None, None),
    ("wood", 1536, 512, 512, 256, "tile", "u", None, None),
    ("foliage", 0, 768, 512, 256, "tile", None, None, None),
    ("wood_contact", 512, 768, 512, 256, "ground", None, "wood", None),
    ("galv_dark", 1024, 768, 256, 256, "tile", None, None, None),
    ("paint_yellow", 1280, 768, 128, 128, "tile", None, None, None),
    ("white_refl", 1408, 768, 128, 128, "tile", None, None, None),
    ("yellow_refl", 1280, 896, 128, 128, "tile", None, None, None),
    ("red_refl", 1408, 896, 128, 128, "tile", None, None, None),
    ("rubber", 1536, 768, 128, 128, "tile", None, None, None),
    ("black_plastic", 1664, 768, 128, 128, "tile", None, None, None),
    ("void", 1536, 896, 128, 128, "tile", None, None, None),
    ("glass_dark", 1664, 896, 128, 128, "tile", None, None, None),
    ("paint_grey", 1792, 768, 256, 256, "tile", None, None, None),
]
CELL = {c[0]: c for c in CELLS}
CID = {c[0]: i for i, c in enumerate(CELLS)}
EXTRA0 = 1000                     # material_index >= EXTRA0 (+1 shift while building) = extra material, not an atlas cell

# tileable game materials: name -> (recipe, tile metres, px)
TILEABLES = {
    "PaintedSteel": ("paint_steel", 2.0, 1024),
    "Galvanized": ("galv", 2.0, 1024),
    "Stainless": ("stainless", 1.0, 512),
    "Concrete": ("concrete", 2.0, 1024),
    "DeckAntiSlip": ("deck", 2.0, 1024),
    "LEDDiffuser": ("led", 0.5, 256),
}


def cell_uv_rect(name):
    _, x, y, w, h = CELL[name][:5]
    return x / AW, 1.0 - (y + h) / AH, (x + w) / AW, 1.0 - y / AH


# ============================================================================== numpy texture synthesis (periodic)
def _lin(hexs):
    h = hexs.lstrip("#"); c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return np.array([x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c], np.float32)


def _srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def _nz(h, w, wl_px, seed, aniso=(1.0, 1.0), octaves=1, gain=0.5):
    """Periodic band-limited noise (zero mean, unit std): Gaussian-filtered white noise in the Fourier domain, so it
    tiles exactly over (h, w). wl_px = feature size in pixels; aniso stretches features along (x, y)."""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    out = np.zeros((h, w), np.float64); amp = 1.0
    for o in range(octaves):
        wl = max(0.6, wl_px / (2.0 ** o))
        f2 = (fx * wl * aniso[0]) ** 2 + (fy * wl * aniso[1]) ** 2
        n = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((h, w))) * np.exp(-2.0 * f2)))
        out += amp * n / (n.std() + 1e-12); amp *= gain
    return (out / (out.std() + 1e-12)).astype(np.float32)


def _worley(h, w, cell_px, seed):
    """Periodic jittered-grid Worley: (F1 px, F2 px, per-cell random 0..1)."""
    nx = max(1, int(round(w / cell_px))); ny = max(1, int(round(h / cell_px))); cx = w / nx; cy = h / ny
    rng = np.random.default_rng(seed); jx = rng.random((ny, nx)); jy = rng.random((ny, nx)); rid = rng.random((ny, nx))
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32); X += 0.5; Y += 0.5
    gx = np.floor(X / cx).astype(np.int64); gy = np.floor(Y / cy).astype(np.int64)
    f1 = np.full((h, w), 1e9, np.float32); f2 = np.full((h, w), 1e9, np.float32); cid = np.zeros((h, w), np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ix = gx + dx; iy = gy + dy; mx = ix % nx; my = iy % ny
            px = (ix + jx[my, mx]) * cx; py = (iy + jy[my, mx]) * cy
            d = np.hypot(X - px, Y - py).astype(np.float32)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d)); f1 = np.where(closer, d, f1); cid = np.where(closer, rid[my, mx], cid)
    return f1, f2, cid


def _ss(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0); return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim == 2: t = t[..., None]
    return a * (1.0 - t) + b * t


def _full(h, w, rgb): return np.broadcast_to(np.asarray(rgb, np.float32), (h, w, 3)).copy()


def _zmap(h, ppm):
    """Height above the cell bottom (metres) per row; row 0 = top of the cell."""
    return ((h - 1 - np.arange(h, dtype=np.float32) + 0.5) / ppm)[:, None]


# ---- recipes: (h, w, ppm, seed) -> {"albedo" (h, w, 3) linear, "rough", "metal", "height" (m)}
def r_galv(h, w, ppm, seed, aged=0.0):
    f1, f2, cid = _worley(h, w, 0.016 * ppm, seed)
    mott = _nz(h, w, 0.5 * ppm, seed + 1, octaves=2); pat = _ss(_nz(h, w, 0.25 * ppm, seed + 2, octaves=2), 0.6 - 0.9 * aged, 2.2) * (0.35 + 0.45 * aged)
    wr = _ss(_nz(h, w, 0.006 * ppm, seed + 3), 2.6 - 0.4 * aged, 3.2)
    lo, hi = ("#a1a7ab", "#b0b6b9") if aged < 0.5 else ("#8f9598", "#9ca2a5")
    alb = _mix(_full(h, w, _lin(lo)), _full(h, w, _lin(hi)), np.clip(cid * 0.8 + 0.06 * mott + 0.1, 0, 1))
    alb = _mix(alb, _full(h, w, _lin("#8d9295" if aged < 0.5 else "#7f8486")), pat * 0.5)
    alb = _mix(alb, _full(h, w, _lin("#cfd1ce")), wr * 0.4)
    rough = 0.34 + 0.07 * cid + 0.18 * pat + 0.2 * wr
    metal = 0.92 - 0.18 * pat - 0.4 * wr
    edge = _ss(f2 - f1, 1.2, 0.0)
    height = 0.00004 * edge + 0.00003 * _nz(h, w, 0.004 * ppm, seed + 4) + 0.0001 * wr
    return {"albedo": alb, "rough": rough, "metal": metal, "height": height}


def r_paint(hexc, rough=0.44, mottle=0.02, metal=0.0, dirt=0.05, peel=0.00004):
    def f(h, w, ppm, seed):
        base = _lin(hexc); m = _nz(h, w, 0.3 * ppm, seed, octaves=2)
        alb = _full(h, w, base) * (1.0 + mottle * m)[..., None]
        d = _ss(_nz(h, w, 0.12 * ppm, seed + 1, octaves=3), 0.8, 2.0)
        alb = _mix(alb, _full(h, w, _lin("#5a564e")), d * dirt)
        pe = _nz(h, w, max(1.5, 0.003 * ppm), seed + 2)
        return {"albedo": alb, "rough": rough + 0.03 * m + 0.1 * d * dirt * 4, "metal": np.full((h, w), metal, np.float32), "height": peel * pe}
    return f


def r_edge(base_fn, chip_hex, chip_rough=0.6, chip_metal=0.0, lift=1.08, cover=0.95):
    """Worn edge variant: lighter worn tone with chips to the substrate (used only on chamfer faces)."""
    def f(h, w, ppm, seed):
        r = base_fn(h, w, ppm, seed)
        ch = _ss(_nz(h, w, 0.018 * ppm, seed + 11, octaves=3), cover, cover + 0.3)
        alb = np.clip(r["albedo"] * lift, 0, 1)
        alb = _mix(alb, _full(h, w, _lin(chip_hex)), ch)
        return {"albedo": alb, "rough": _mix(r["rough"][..., None], np.full((h, w, 1), chip_rough, np.float32), ch)[..., 0],
                "metal": _mix(np.asarray(r["metal"], np.float32)[..., None] * np.ones((h, w, 1), np.float32), np.full((h, w, 1), chip_metal, np.float32), ch)[..., 0],
                "height": r["height"] - 0.0004 * ch}
    return f


def r_contact(base_fn, grime_hex, reach=0.42, strength=0.62, splash=0.5, wet_hex=None):
    """Ground-contact variant: grime / splash / damp fading out by `reach` metres above the bottom row (z = 0)."""
    def f(h, w, ppm, seed):
        r = base_fn(h, w, ppm, seed)
        z = _zmap(h, ppm)
        band = _ss(z, reach, 0.0) * (0.62 + 0.38 * np.clip(0.5 + 0.35 * _nz(h, w, 0.06 * ppm, seed + 21, octaves=2), 0, 1))
        sp = _ss(_nz(h, w, 0.012 * ppm, seed + 22), 1.0, 1.9) * _ss(z, reach * 0.65, 0.0)
        m = np.clip(band * strength + sp * splash * 0.6, 0, 1)
        alb = _mix(r["albedo"], _full(h, w, _lin(grime_hex)), m)
        if wet_hex is not None:
            wet = _ss(z, 0.035, 0.0) * (0.7 + 0.3 * np.clip(_nz(h, w, 0.03 * ppm, seed + 23), -1, 1))
            alb = _mix(alb, _full(h, w, _lin(wet_hex)), np.clip(wet, 0, 1) * 0.75)
        met = np.asarray(r["metal"], np.float32) * (1.0 - 0.75 * m)
        return {"albedo": alb, "rough": np.clip(r["rough"] + 0.16 * m, 0, 1), "metal": met, "height": r["height"] + 0.00025 * m * _nz(h, w, 0.01 * ppm, seed + 24)}
    return f


def r_streak(base_fn, hexc="#6c695f", reach=0.55):
    """Top-anchored weathering streaks (rain run-off under a coping)."""
    def f(h, w, ppm, seed):
        r = base_fn(h, w, ppm, seed)
        z_top = (np.arange(h, dtype=np.float32)[:, None] + 0.5) / ppm               # metres below the top row
        s = np.clip(0.5 + 0.5 * _nz(h, w, 0.05 * ppm, seed + 31, aniso=(1.0, 14.0), octaves=2), 0, 1)
        m = _ss(z_top, reach, 0.02) * _ss(s, 0.5, 0.9) * 0.32
        return {"albedo": _mix(r["albedo"], _full(h, w, _lin(hexc)), m), "rough": np.clip(r["rough"] + 0.05 * m, 0, 1), "metal": r["metal"], "height": r["height"]}
    return f


def r_concrete(h, w, ppm, seed, tone=("#928f87", "#9d9a92")):
    agg = _worley(h, w, max(1.5, 0.006 * ppm), seed)[2]
    blot = _nz(h, w, 0.35 * ppm, seed + 1, octaves=3)
    pore = _ss(_nz(h, w, max(0.8, 0.003 * ppm), seed + 2), 2.5, 3.1)
    alb = _mix(_full(h, w, _lin(tone[0])), _full(h, w, _lin(tone[1])), _ss(blot, -1.2, 1.2))
    alb = alb * (0.95 + 0.08 * agg)[..., None]
    alb = _mix(alb, _full(h, w, _lin("#5a5751")), pore * 0.6)
    return {"albedo": alb, "rough": 0.84 + 0.07 * agg, "metal": np.zeros((h, w), np.float32), "height": 0.0003 * agg - 0.0015 * pore + 0.0002 * blot}


def r_brushed(lo, hi, rough, metal=1.0, stretch=40.0):
    def f(h, w, ppm, seed):
        s = _nz(h, w, max(1.0, 0.0025 * ppm), seed, aniso=(stretch, 1.0))
        m = _nz(h, w, 0.3 * ppm, seed + 1)
        alb = _mix(_full(h, w, _lin(lo)), _full(h, w, _lin(hi)), np.clip(0.5 + 0.22 * s + 0.12 * m, 0, 1))
        return {"albedo": alb, "rough": rough + 0.04 * s + 0.03 * m, "metal": np.full((h, w), metal, np.float32), "height": 0.00004 * s}
    return f


def r_iron_black(h, w, ppm, seed):
    cast = _nz(h, w, 0.012 * ppm, seed, octaves=2); m = _nz(h, w, 0.25 * ppm, seed + 1)
    alb = _full(h, w, _lin("#1e1f21")) * (1.0 + 0.04 * m)[..., None]
    return {"albedo": alb, "rough": 0.42 + 0.04 * m + 0.02 * cast, "metal": np.zeros((h, w), np.float32), "height": 0.00007 * cast}


def r_wood(h, w, ppm, seed, vertical=False):
    """Weathered treated softwood; grain along x (or y when vertical)."""
    ax = (1.0, 10.0) if vertical else (10.0, 1.0)
    warp = _nz(h, w, 0.25 * ppm, seed, aniso=ax, octaves=2)
    coord = (np.arange(w, dtype=np.float32)[None, :] if vertical else np.arange(h, dtype=np.float32)[:, None]) / ppm
    grain = 0.5 + 0.5 * np.sin(TAU * (coord * 70.0 + 1.6 * warp))
    fine = _nz(h, w, max(1.0, 0.004 * ppm), seed + 1, aniso=(1.0, 30.0) if vertical else (30.0, 1.0))
    board = _nz(h, w, 0.6 * ppm, seed + 2, octaves=2)
    alb = _mix(_full(h, w, _lin("#7b6b58")), _full(h, w, _lin("#93826c")), _ss(board, -1.2, 1.2))
    alb = _mix(alb, _full(h, w, _lin("#5e5042")), _ss(grain, 0.6, 0.95) * 0.35 + 0.06 * np.clip(fine, 0, 2))
    grey = _ss(_nz(h, w, 0.2 * ppm, seed + 3, octaves=2), -0.2, 1.5) * 0.35
    alb = _mix(alb, _full(h, w, _lin("#8d8a83")), grey)
    crack = _ss(_nz(h, w, max(1.0, 0.003 * ppm), seed + 4, aniso=(1.0, 60.0) if vertical else (60.0, 1.0)), 2.4, 3.0)
    alb = _mix(alb, _full(h, w, _lin("#2e261e")), crack * 0.8)
    return {"albedo": alb, "rough": 0.72 + 0.08 * grain, "metal": np.zeros((h, w), np.float32), "height": 0.0004 * grain + 0.00015 * fine - 0.001 * crack}


def r_foliage(h, w, ppm, seed):
    f1, f2, cid = _worley(h, w, 0.02 * ppm, seed)
    cell = 0.02 * ppm
    leaf = _ss(f1, cell * 0.7, cell * 0.1)
    gap = _ss(f2 - f1, 0.0, 1.2)
    clump = _nz(h, w, 0.09 * ppm, seed + 2, octaves=2)
    deep = _ss(_nz(h, w, 0.16 * ppm, seed + 1, octaves=2), 0.9, 2.0)
    lc = _mix(_full(h, w, _lin("#344f24")), _full(h, w, _lin("#56732f")), np.clip(cid * 0.7 + 0.15 * clump + 0.15, 0, 1))
    lc = lc * (0.82 + 0.22 * leaf + 0.1 * np.clip(clump, -1.5, 1.5))[..., None]
    alb = _mix(_full(h, w, _lin("#1c2b14")), lc, np.clip(0.35 + 0.65 * gap, 0, 1) * (1.0 - 0.6 * deep))
    return {"albedo": alb, "rough": 0.62 + 0.15 * (1.0 - leaf), "metal": np.zeros((h, w), np.float32), "height": 0.006 * leaf * gap - 0.012 * deep}


def r_flat(hexc, rough, var=0.03, metal=0.0, pattern=None):
    def f(h, w, ppm, seed):
        n = _nz(h, w, max(1.0, 0.02 * ppm), seed)
        alb = _full(h, w, _lin(hexc)) * (1.0 + var * n)[..., None]
        hgt = 0.00005 * n
        if pattern == "prism":                                   # retroreflective micro-prism sheeting
            Y, X = np.mgrid[0:h, 0:w].astype(np.float32); p = max(2.0, 0.006 * ppm)
            tri = (np.abs(((X / p) % 1.0) - 0.5) + np.abs(((Y / p + 0.5 * np.floor(X / p)) % 1.0) - 0.5))
            alb = alb * (0.96 + 0.08 * tri)[..., None]; hgt = hgt + 0.00006 * tri
        return {"albedo": alb, "rough": np.full((h, w), rough, np.float32) + 0.02 * n, "metal": np.full((h, w), metal, np.float32), "height": hgt}
    return f


def r_deck(h, w, ppm, seed):
    """Anti-slip resin deck coating with calcined-bauxite grit; restrained lighter wear in large patches."""
    rng = np.random.default_rng(seed)
    grit = rng.random((h, w)).astype(np.float32)
    g2 = _worley(h, w, max(2.0, 0.004 * ppm), seed + 1)
    bump = _ss(g2[0], 0.55 * 0.004 * ppm, 0.0)
    wear = _ss(_nz(h, w, 0.6 * ppm, seed + 2, octaves=2), 0.3, 1.8) * 0.35
    alb = _mix(_full(h, w, _lin("#4a4c4e")), _full(h, w, _lin("#5c5d5d")), _ss(_nz(h, w, 0.3 * ppm, seed + 3), -1.5, 1.5))
    alb = _mix(alb, _full(h, w, _lin("#8c857b")), bump * (0.35 + 0.5 * g2[2]))
    alb = _mix(alb, _full(h, w, _lin("#26282a")), _ss(grit, 0.93, 1.0) * 0.6)
    alb = _mix(alb, _full(h, w, _lin("#6b6b68")), wear)
    return {"albedo": alb, "rough": 0.86 + 0.08 * bump - 0.1 * wear, "metal": np.zeros((h, w), np.float32), "height": 0.0007 * bump + 0.0001 * grit}


def r_led(h, w, ppm, seed):
    X = np.arange(w, dtype=np.float32)[None, :] / ppm; Y = np.arange(h, dtype=np.float32)[:, None] / ppm
    dots = np.exp(-(((X % 0.025) - 0.0125) ** 2 + ((Y % 0.025) - 0.0125) ** 2) / (2 * 0.004 ** 2))
    alb = _mix(_full(h, w, _lin("#e8e2d4")), _full(h, w, _lin("#fff6e4")), dots * 0.8)
    return {"albedo": alb, "rough": np.full((h, w), 0.32, np.float32), "metal": np.zeros((h, w), np.float32), "height": 0.00008 * dots}


_PAINT_DARK = r_paint("#3b4145", 0.44)
_ALU_CAST = r_paint("#8f9394", 0.46, mottle=0.02, metal=0.3, dirt=0.05)
_CONCRETE = r_concrete
RECIPES = {
    "galv": r_galv,
    "galv_dark": lambda h, w, p, s: r_galv(h, w, p, s, aged=0.8),
    "galv_contact": r_contact(r_galv, "#57554d", reach=0.45, strength=0.55, wet_hex="#3f3d37"),
    "paint_dark": _PAINT_DARK,
    "paint_dark_edge": r_edge(_PAINT_DARK, "#62676a", chip_rough=0.5, chip_metal=0.3, lift=1.12, cover=1.15),
    "paint_dark_contact": r_contact(_PAINT_DARK, "#4d473d", reach=0.4, strength=0.5, wet_hex="#2b2824"),
    "concrete": _CONCRETE,
    "concrete_contact": r_contact(_CONCRETE, "#4f4a40", reach=0.38, strength=0.6, splash=0.6, wet_hex="#3a362f"),
    "concrete_edge": r_edge(lambda h, w, p, s: r_concrete(h, w, p, s, ("#9d9a92", "#b4b1a8")), "#c4c0b6", chip_rough=0.92, lift=1.0, cover=0.7),
    "concrete_streak": r_streak(_CONCRETE),
    "alu_cast": _ALU_CAST,
    "alu_cast_edge": r_edge(_ALU_CAST, "#b4b8b9", chip_rough=0.35, chip_metal=0.8, lift=1.08, cover=1.1),
    "stainless": r_brushed("#a8acaf", "#ced2d4", 0.24),
    "alu_mill": r_brushed("#a6abae", "#b2b6b9", 0.42, metal=0.85, stretch=12.0),
    "iron_black": r_iron_black,
    "iron_black_edge": r_edge(r_iron_black, "#4b3a2e", chip_rough=0.75, chip_metal=0.3, lift=1.25, cover=1.05),
    "housing": r_flat("#18191b", 0.42, 0.04),
    "wood": r_wood,
    "wood_contact": r_contact(lambda h, w, p, s: r_wood(h, w, p, s, vertical=True), "#3a3128", reach=0.35, strength=0.6, wet_hex="#2a241e"),
    "foliage": r_foliage,
    "paint_yellow": r_paint("#e0a812", 0.4, mottle=0.03, dirt=0.03),
    "white_refl": r_flat("#e4e4de", 0.3, 0.02, pattern="prism"),
    "yellow_refl": r_flat("#f0b505", 0.32, 0.02, pattern="prism"),
    "red_refl": r_flat("#b5141c", 0.32, 0.02, pattern="prism"),
    "rubber": r_flat("#1b1b1b", 0.88, 0.05),
    "black_plastic": r_flat("#131415", 0.5, 0.04),
    "void": r_flat("#070707", 1.0, 0.0),
    "glass_dark": r_flat("#0b0c0e", 0.06, 0.02),
    "paint_grey": r_paint("#8f9496", 0.45),
    # tileable-only recipes
    "paint_steel": r_paint("#56636a", 0.42, mottle=0.025, dirt=0.03, peel=0.0001),
    "deck": r_deck,
    "led": r_led,
}


# ============================================================================== baking (numpy -> PNG)
def _save_png(path, rgb):
    """Write an (h, w, 3) array (row 0 = top, already display / data encoded, 0..1) as an 8-bit PNG."""
    h, w = rgb.shape[:2]
    im = bpy.data.images.new("_mrs_hw_png", w, h, alpha=False)
    a = np.ones((h, w, 4), np.float32); a[..., :3] = np.clip(rgb[::-1], 0.0, 1.0)
    im.pixels.foreach_set(a.ravel()); im.filepath_raw = path; im.file_format = "PNG"; im.save()
    bpy.data.images.remove(im)


def _normal(hgt, ppm, wrap=True):
    """OpenGL / glTF tangent-space normal from a height field in metres (row 0 = top, +v = up)."""
    hg = hgt.astype(np.float64)
    if wrap:
        du = (np.roll(hg, -1, 1) - np.roll(hg, 1, 1)) * ppm / 2.0
        dv = (np.roll(hg, 1, 0) - np.roll(hg, -1, 0)) * ppm / 2.0
    else:
        gr, gc = np.gradient(hg, 1.0 / ppm); du, dv = gc, -gr
    n = np.stack([-du, -dv, np.ones_like(hg)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5).astype(np.float32)


def _pack(r, h, w):
    alb = np.asarray(r["albedo"], np.float32)
    rough = np.clip(np.broadcast_to(np.asarray(r["rough"], np.float32), (h, w)), 0.02, 1.0)
    metal = np.clip(np.broadcast_to(np.asarray(r["metal"], np.float32), (h, w)), 0.0, 1.0)
    orm = np.stack([np.ones((h, w), np.float32), rough, metal], -1)
    return alb, orm, np.broadcast_to(np.asarray(r["height"], np.float32), (h, w))


def _paths(tex_dir, name):
    return {k: os.path.join(tex_dir, "%s_%s.png" % (name, k)) for k in ("albedo", "orm", "normal")}


def _layout_json():
    return {"version": BAKE_VERSION, "size": [AW, AH], "px_per_m": PPM,
            "cells": {c[0]: {"px": list(c[1:5]), "uv": [round(x, 6) for x in cell_uv_rect(c[0])], "mode": c[5], "grain": c[6], "fallback": c[7], "edge": c[8],
                             "metres": [c[3] / PPM, c[4] / PPM]} for c in CELLS},
            "tileables": {"MRS_HW_" + k: {"recipe": v[0], "tile_m": v[1], "px": v[2]} for k, v in TILEABLES.items()}}


def bake_current(tex_dir=None):
    tex_dir = tex_dir or TEX_DIR
    files = list(_paths(tex_dir, ATLAS).values()) + [p for k in TILEABLES for p in _paths(tex_dir, "MRS_HW_" + k).values()]
    if not all(os.path.exists(p) for p in files): return False
    try:
        with open(os.path.join(tex_dir, "hardware_layout.json"), encoding="utf-8") as f: lay = json.load(f)
    except (OSError, ValueError):
        return False
    return lay.get("version") == BAKE_VERSION and lay.get("cells") == _layout_json()["cells"] and lay.get("tileables") == _layout_json()["tileables"]


def bake_textures(tex_dir=None, verbose=True):
    """Generate MRS_HardwareAtlas_{albedo,orm,normal}.png and MRS_HW_<name>_{albedo,orm,normal}.png into tex_dir."""
    import time
    t0 = time.time(); tex_dir = os.path.abspath(tex_dir or TEX_DIR); os.makedirs(tex_dir, exist_ok=True)
    A = np.zeros((AH, AW, 3), np.float32); O = np.zeros((AH, AW, 3), np.float32); N = np.zeros((AH, AW, 3), np.float32)
    for name, x, y, w, h, mode, grain, fb, edge in CELLS:
        seed = zlib.crc32(name.encode()) & 0xFFFF
        r = RECIPES[name](h, w, PPM, seed)
        alb, orm, hgt = _pack(r, h, w)
        if grain == "v": pass
        A[y:y + h, x:x + w] = alb; O[y:y + h, x:x + w] = orm; N[y:y + h, x:x + w] = _normal(hgt, PPM, wrap=(mode == "tile"))
    P = _paths(tex_dir, ATLAS)
    _save_png(P["albedo"], _srgb(A)); _save_png(P["orm"], O); _save_png(P["normal"], N)
    if verbose: print("[hardware] atlas %dx%d  %.1f s" % (AW, AH, time.time() - t0), flush=True)
    for key, (recipe, tile_m, px) in TILEABLES.items():
        ppm = px / tile_m; seed = zlib.crc32(key.encode()) & 0xFFFF
        r = RECIPES[recipe](px, px, ppm, seed)
        alb, orm, hgt = _pack(r, px, px)
        nrm = _normal(hgt, ppm, wrap=True)
        # UV-less faces (Curve to Mesh: every UV = (0, 0)) sample the corner: blend a small wrapped corner patch to
        # the mean albedo / ORM and a flat normal, so they read as the average material
        Y, X = np.mgrid[0:px, 0:px].astype(np.float32) + 0.5
        d = np.hypot(np.minimum(X, px - X), np.minimum(Y, px - Y)); k = _ss(d, 7.0, 3.0)
        alb = _mix(alb, _full(px, px, alb.reshape(-1, 3).mean(0)), k); orm = _mix(orm, _full(px, px, orm.reshape(-1, 3).mean(0)), k)
        nrm = _mix(nrm, _full(px, px, (0.5, 0.5, 1.0)), k)
        P = _paths(tex_dir, "MRS_HW_" + key)
        _save_png(P["albedo"], _srgb(alb)); _save_png(P["orm"], orm); _save_png(P["normal"], nrm)
    with open(os.path.join(tex_dir, "hardware_layout.json"), "w", encoding="utf-8") as f: json.dump(_layout_json(), f, indent=1)
    if verbose: print("[hardware] textures written to %s in %.1f s" % (tex_dir, time.time() - t0), flush=True)
    return tex_dir


# ============================================================================== materials
def _image(path, colorspace):
    im = bpy.data.images.load(path, check_existing=True); im.reload()
    im.colorspace_settings.name = colorspace
    return im


def image_material(name, paths, tile_m=None, emission=0.0, backface=True):
    """Plain Principled BSDF fed by albedo / ORM (G roughness, B metallic) / normal image textures. tile_m: a Mapping
    node scales the UV by 1 / tile_m (metre UVs; exported as KHR_texture_transform). emission > 0: the albedo also
    drives Emission Color with that strength (KHR_materials_emissive_strength)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (500, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (150, 0); nt.links.new(b.outputs[0], out.inputs["Surface"])
    vec = None
    if tile_m:
        tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1000, 0)
        mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-800, 0); mp.inputs["Scale"].default_value = (1.0 / tile_m, 1.0 / tile_m, 1.0)
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"]); vec = mp.outputs[0]
    ta = nt.nodes.new("ShaderNodeTexImage"); ta.location = (-450, 250); ta.image = _image(paths["albedo"], "sRGB"); ta.label = "albedo"
    to = nt.nodes.new("ShaderNodeTexImage"); to.location = (-450, -50); to.image = _image(paths["orm"], "Non-Color"); to.label = "orm"
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.location = (-450, -350); tn.image = _image(paths["normal"], "Non-Color"); tn.label = "normal"
    if vec is not None:
        for t in (ta, to, tn): nt.links.new(vec, t.inputs["Vector"])
    sp = nt.nodes.new("ShaderNodeSeparateColor"); sp.location = (-150, -50)
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-150, -350)
    nt.links.new(ta.outputs["Color"], b.inputs["Base Color"]); nt.links.new(to.outputs["Color"], sp.inputs[0])
    nt.links.new(sp.outputs["Green"], b.inputs["Roughness"]); nt.links.new(sp.outputs["Blue"], b.inputs["Metallic"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if emission > 0:
        nt.links.new(ta.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = emission
    m.use_backface_culling = backface; m.diffuse_color = (0.4, 0.4, 0.4, 1.0); m.roughness = 0.5
    return m


def glass_material(name=GLASS, rgb=(0.62, 0.68, 0.70), alpha=0.18):
    """Alpha-blended glazing without textures (Base Color unlinked: export passes it through, glTF alphaMode BLEND)."""
    g = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if g.node_tree is None: g.use_nodes = True
    nt = g.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = (*rgb, 1.0); b.inputs["Roughness"].default_value = 0.04
    b.inputs["IOR"].default_value = 1.5; b.inputs["Alpha"].default_value = alpha
    try: g.surface_render_method = "BLENDED"
    except (AttributeError, TypeError): pass
    try: g.use_transparency_overlap = True
    except AttributeError: pass
    g.use_backface_culling = True; g.diffuse_color = (*rgb, alpha)
    return g


MATS = {}


def build_hardware_materials(bake="auto", tex_dir=None, verbose=True):
    """Bake the hardware textures when missing / outdated (bake=True always, False never) and (re)create the materials:
    MRS_HardwareAtlas, MRS_SignalHousing (same atlas images), MRS_HW_Glass and the tileable MRS_HW_PaintedSteel /
    Galvanized / Stainless / Concrete / DeckAntiSlip / LEDDiffuser. Returns {name: material}."""
    tex_dir = tex_dir or TEX_DIR
    if bake is True or (bake == "auto" and not bake_current(tex_dir)): bake_textures(tex_dir, verbose)
    out = {}
    P = _paths(tex_dir, ATLAS)
    out[ATLAS] = image_material(ATLAS, P)
    out[HOUSING] = image_material(HOUSING, P)
    out[GLASS] = glass_material()
    for key, (recipe, tile_m, px) in TILEABLES.items():
        nm = "MRS_HW_" + key
        out[nm] = image_material(nm, _paths(tex_dir, nm), tile_m=tile_m, emission=3.0 if key == "LEDDiffuser" else 0.0)
    MATS.clear(); MATS.update(out)
    return out


def mat(name):
    if name not in MATS or MATS[name].name != name: build_hardware_materials()
    return MATS[name]


# ============================================================================== mesh building
class HM:
    """bmesh under construction. Every face carries an atlas cell (str) or an extra material (bpy Material); the
    material_index stores cell id + 1 (or EXTRA0 + k + 1) so the bevel's new faces (index 0) can be found. Faces of
    thin plates / tubes get the 'nobevel' flag."""
    def __init__(self):
        self.bm = bmesh.new(); self.nb = self.bm.faces.layers.int.new("nobevel"); self.extra = []

    def mi(self, c):
        if isinstance(c, str): return CID[c] + 1
        if c not in self.extra: self.extra.append(c)
        return EXTRA0 + self.extra.index(c) + 1

    def since(self, n0):
        self.bm.faces.ensure_lookup_table(); return self.bm.faces[n0:]

    def _end(self, n0, nobevel):
        if nobevel:
            for f in self.since(n0): f[self.nb] = 1
        return n0

    def run(self, fn, c, *a, nobevel=False, **k):
        """Call an assets.py-style primitive fn(bm, *a, mi=..., **k)."""
        n0 = len(self.bm.faces); fn(self.bm, *a, mi=self.mi(c), **k); return self._end(n0, nobevel)

    def box(self, x0, y0, z0, x1, y1, z1, c, nobevel=False, **sides):
        from .assets import _box
        n0 = len(self.bm.faces)
        _box(self.bm, min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1), self.mi(c))
        if sides:
            fs = self.since(n0)                       # assets._box face order: z0, z1, y0, x1, y1, x0
            for key, i in (("bottom", 0), ("top", 1), ("back", 2), ("right", 3), ("front", 4), ("left", 5)):
                if key in sides: fs[i].material_index = self.mi(sides[key])
        return self._end(n0, nobevel)

    def cyl(self, x, y, z0, z1, r0, r1, c, n=16, smooth=True, caps=True, nobevel=None):
        from .assets import _cyl
        n0 = len(self.bm.faces); _cyl(self.bm, x, y, z0, z1, r0, r1, n, self.mi(c), smooth, caps)
        return self._end(n0, (n < 12) if nobevel is None else nobevel)

    def tube(self, pts, r, c, n=12, caps=True, smooth=True):
        from .assets import _tube
        n0 = len(self.bm.faces); _tube(self.bm, pts, r, n, self.mi(c), caps, smooth); return self._end(n0, True)

    def lathe(self, prof, c, n=16, x=0.0, y=0.0, smooth=True, caps=True, nobevel=None):
        from .assets import _lathe
        n0 = len(self.bm.faces); _lathe(self.bm, prof, n, self.mi(c), x, y, smooth, caps)
        return self._end(n0, (n < 12) if nobevel is None else nobevel)

    def prism(self, pts, a0, a1, c, axis="y", nobevel=False):
        from .assets import _prism
        n0 = len(self.bm.faces); _prism(self.bm, pts, a0, a1, self.mi(c), axis); return self._end(n0, nobevel)

    def band(self, outer, inner, a0, a1, c, axis="y", closed=True, nobevel=False):
        from .assets import _band
        n0 = len(self.bm.faces); _band(self.bm, outer, inner, a0, a1, self.mi(c), axis, closed); return self._end(n0, nobevel)

    def loft(self, rings, c, caps=True, smooth=True, nobevel=True):
        """Quads between consecutive rings (lists of equal-length point lists, closed loops) + end caps."""
        bm = self.bm; mi = self.mi(c); n0 = len(bm.faces)
        vr = [[bm.verts.new(Vector(p)) for p in r] for r in rings]; n = len(vr[0])
        for a, b in zip(vr, vr[1:]):
            for k in range(n):
                f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k])); f.material_index = mi; f.smooth = smooth
        if caps:
            bm.faces.new(vr[0][::-1]).material_index = mi; bm.faces.new(vr[-1]).material_index = mi
        return self._end(n0, nobevel)

    def taper(self, a, b, r0, r1, c, n=12, caps=True, segs=1):
        """Straight tapered round tube from a to b (segs rings along it, for UV chunking)."""
        a, b = Vector(a), Vector(b); d = (b - a).normalized()
        u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized(); v = d.cross(u)
        rings = []
        for i in range(segs + 1):
            t = i / segs; p = a.lerp(b, t); r = r0 + (r1 - r0) * t
            rings.append([p + (u * math.cos(TAU * k / n) + v * math.sin(TAU * k / n)) * r for k in range(n)])
        return self.loft(rings, c, caps=caps)

    def sweep(self, pts, radii, c, n=12, caps=True, smooth=True):
        """Round tube along a polyline with a radius per point (parallel-transport frames)."""
        pts = [Vector(p) for p in pts]; rings = []; u = None
        for i, p in enumerate(pts):
            if i == 0: d = (pts[1] - pts[0]).normalized()
            elif i == len(pts) - 1: d = (pts[-1] - pts[-2]).normalized()
            else: d = ((pts[i] - pts[i - 1]).normalized() + (pts[i + 1] - pts[i]).normalized()).normalized()
            if u is None:
                a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0)); u = d.cross(a).normalized()
            else:
                u = (u - d * u.dot(d)).normalized()
            v = d.cross(u)
            rings.append([p + (u * math.cos(TAU * k / n) + v * math.sin(TAU * k / n)) * radii[i] for k in range(n)])
        return self.loft(rings, c, caps=caps, smooth=smooth)

    def bisect(self, n0, z):
        """Cut the faces added since n0 with the horizontal plane at z (so cells can change at that height)."""
        fs = list(self.since(n0)); es = list({e for f in fs for e in f.edges}); vs = list({v for f in fs for v in f.verts})
        bmesh.ops.bisect_plane(self.bm, geom=fs + es + vs, plane_co=(0.0, 0.0, z), plane_no=(0.0, 0.0, 1.0))

    def paint(self, n0, c, pred):
        mi = self.mi(c)
        for f in self.since(n0):
            if pred(f): f.material_index = mi


def pole_rings(z0, z1, r0, r1, seg=1.9):
    """Ring heights for a tall shaft: a loop at least every `seg` metres (UV chunks keep 256 px/m)."""
    n = max(1, int(math.ceil((z1 - z0) / seg)))
    return [(z0 + (z1 - z0) * i / n, r0 + (r1 - r0) * i / n) for i in range(n + 1)]


def _pkey(n):
    ax = max(range(3), key=lambda i: abs(n[i])); return ax * 2 + (1 if n[ax] < 0 else 0)


def _proj(co, k):
    """Planar projection per dominant axis, unmirrored for a viewer facing the face (u right, v up; top faces u = +X, v = +Y)."""
    x, y, z = co
    return ((y, z), (-y, z), (-x, z), (x, z), (x, y), (-x, y))[k]


def atlas_uv(bm, name, faces=None):
    """UV atlas faces (material_index = cell id) into their cells. Islands = edge-connected faces with the same cell and
    projection axis, cut into chunks that fit the cell (no shrink for long poles: they carry loops every <= 1.9 m).
    tile: real scale (PPM), long side along the grain, seeded offset (8 px padding). ground: v = height above the
    origin (z = 0 is the cell's bottom row), u seeded; horizontal faces use the fallback cell. top: v anchored at the
    island's top."""
    uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    bm.normal_update(); bm.faces.ensure_lookup_table(); bm.faces.index_update()
    faces = [f for f in (faces if faces is not None else bm.faces)]
    fset = {f.index for f in faces}
    for f in faces:                                                  # horizontal faces of anchored cells -> fallback cell
        c = CELLS[f.material_index]
        if c[5] in ("ground", "top") and _pkey(f.normal) >= 4: f.material_index = CID[c[7]]
    keys = {f.index: (f.material_index, _pkey(f.normal)) for f in faces}
    parent = {i: i for i in fset}

    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in bm.edges:
        lf = [f for f in e.link_faces if f.index in fset]
        if len(lf) == 2 and keys[lf[0].index] == keys[lf[1].index]:
            ra, rb = find(lf[0].index), find(lf[1].index)
            if ra != rb: parent[max(ra, rb)] = min(ra, rb)
    groups = {}
    for f in faces: groups.setdefault(find(f.index), []).append(f)
    dens, k_isl = [], 0

    def bounds(p):
        xs = [a for a, b in p.values()]; ys = [b for a, b in p.values()]
        return min(xs), min(ys), max(xs), max(ys)
    for root in sorted(groups):
        fs = groups[root]; cid, pk = keys[root]
        cname, cx, cy, cw, ch, mode, grain, fb, edge = CELLS[cid]
        bottom = AH - cy - ch; pad = 6.0 if cw <= 128 else 8.0
        avw, avh = (cw - 2 * pad) / PPM, (ch - 2 * pad) / PPM
        pts = {l: _proj(l.vert.co, pk) for f in fs for l in f.loops}
        if mode == "ground":
            for l in pts: pts[l] = (pts[l][0], l.vert.co.z)
        a0, b0, a1, b1 = bounds(pts); w, h = max(a1 - a0, 1e-6), max(b1 - b0, 1e-6)
        rot = False
        if mode == "tile":
            if grain == "u": rot = h > w * 1.05
            elif grain == "v": rot = w > h * 1.05
            elif avw > avh * 1.01: rot = h > w * 1.01                # long side along the cell's long axis (chunks then fit)
            elif avh > avw * 1.01: rot = w > h * 1.01
            else: rot = False
        if rot:
            pts = {l: (b, -a) for l, (a, b) in pts.items()}; a0, b0, a1, b1 = bounds(pts); w, h = max(a1 - a0, 1e-6), max(b1 - b0, 1e-6)
        # chunks: split faces along u (and v for tile cells) by their centre so every chunk fits the cell
        cu = avw if w > avw * 1.001 else None
        cv = avh if (mode != "ground" and h > avh * 1.001) else None
        def greedy(faces_, axis, limit):
            """Split faces into runs along `axis` (0 = u, 1 = v): a new run starts when the next face would make the run
            longer than `limit` (faces are cut at the island's loops, so runs fit the cell)."""
            if not limit: return [faces_]
            ext = sorted(((min(pts[l][axis] for l in f.loops), max(pts[l][axis] for l in f.loops), f) for f in faces_), key=lambda e: e[0])
            runs, cur, start = [], [], None
            for lo_, hi_, f in ext:
                if cur and hi_ - start > limit * 1.0001: runs.append(cur); cur, start = [], None
                if start is None: start = lo_
                cur.append(f)
            if cur: runs.append(cur)
            return runs
        chunks = {}
        for i, run in enumerate(greedy(fs, 0, cu)):
            for j, sub in enumerate(greedy(run, 1, cv)): chunks[(i, j)] = sub
        for key in sorted(chunks):
            sub = chunks[key]; sp = {l: pts[l] for f in sub for l in f.loops}
            s0, t0, s1, t1 = bounds(sp); sw, sh = max(s1 - s0, 1e-6), max(t1 - t0, 1e-6)
            rnd = random.Random(zlib.crc32(("%s/%d" % (name, k_isl)).encode())); k_isl += 1
            if mode == "ground":
                sc = min(1.0, avw / sw); ox = rnd.random() * max(0.0, avw - sw * sc)
                for l, (a, b) in sp.items():
                    vv = min(max(b, 0.0), (ch - 2 * pad) / PPM)
                    l[uv].uv = ((cx + pad + (ox + (a - s0) * sc) * PPM) / AW, (bottom + pad + vv * PPM) / AH)
                dens.append((PPM * sc, sum(f.calc_area() for f in sub)))
                continue
            sc = min(1.0, avw / sw, avh / sh)
            ox = rnd.random() * (avw - sw * sc)
            oy = (avh - sh * sc) if mode == "top" else rnd.random() * (avh - sh * sc)
            for l, (a, b) in sp.items():
                l[uv].uv = ((cx + pad + (ox + (a - s0) * sc) * PPM) / AW, (bottom + pad + (oy + (b - t0) * sc) * PPM) / AH)
            dens.append((PPM * sc, sum(f.calc_area() for f in sub)))
    tot = sum(a for _, a in dens) or 1.0
    return {"islands": k_isl, "min_ppm": round(min((d for d, _ in dens), default=PPM), 1), "mean_ppm": round(sum(d * a for d, a in dens) / tot, 1)}


def finish(hm, name, bevel=0.0, drop_ground=True, sharp=0.55):
    """Normals, ground-face removal, chamfers (bevel faces take their largest neighbour's cell or its edge variant),
    atlas UVs (extra-material faces keep metre box UVs), then material_index -> slot (0 = atlas, 1.. = extras)."""
    from .assets import _finish
    bm = hm.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.normal_update()
    if drop_ground:
        g = [f for f in bm.faces if f.normal.z < -0.999 and all(abs(v.co.z) < 1e-5 for v in f.verts)]
        if g: bmesh.ops.delete(bm, geom=g, context="FACES")
    _finish(bm, bevel, recalc=False, sharp=sharp)
    new = [f for f in bm.faces if f.material_index == 0]
    for _ in range(6):
        left = []
        for f in new:
            nb = [g for e in f.edges for g in e.link_faces if g is not f and g.material_index > 0]
            cells = [g for g in nb if g.material_index < EXTRA0]          # prefer hardware cells: chamfers next to a lens / face stay housing
            if cells: nb = cells
            if nb:
                src = max(nb, key=lambda g: g.calc_area()).material_index
                if src < EXTRA0:
                    e_ = CELLS[src - 1][8]; f.material_index = CID[e_] + 1 if e_ else src
                else: f.material_index = src
            else: left.append(f)
        if not left: break
        new = left
    for f in new:
        if f.material_index == 0: f.material_index = 1
    for f in bm.faces: f.material_index -= 1
    bm.faces.ensure_lookup_table()
    atl = [f for f in bm.faces if f.material_index < EXTRA0]
    st = atlas_uv(bm, name, atl)
    for f in bm.faces: f.material_index = 0 if f.material_index < EXTRA0 else 1 + (f.material_index - EXTRA0)
    return st


def remove_mesh(name):
    old = bpy.data.meshes.get(name)
    if old is not None and old.users == 0: bpy.data.meshes.remove(old)


def to_mesh(hm, name, bevel=0.0, atlas=None, drop_ground=True):
    """Finish `hm` and return a new mesh datablock `name` with slots [atlas] + hm.extra."""
    st = finish(hm, name, bevel, drop_ground)
    remove_mesh(name)
    me = bpy.data.meshes.new(name); hm.bm.to_mesh(me); hm.bm.free()
    me.materials.append(atlas or mat(ATLAS))
    for m in hm.extra: me.materials.append(m)
    st["tris"] = sum(len(p.vertices) - 2 for p in me.polygons); st["materials"] = [m.name for m in me.materials]
    REPORT[name] = st
    return me


def make_object(col, name, builder, bevel=0.0, atlas=None, drop_ground=True, hidden=True):
    """Build with builder(hm), finish, link into `col` (hidden like the other MRS library objects)."""
    hm = HM(); builder(hm)
    me = to_mesh(hm, name, bevel, atlas, drop_ground)
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    if hidden: o.hide_render = True; o.hide_viewport = True
    return o


# ============================================================================== shared hardware parts
def anchor_bolts(hm, r, n=4, z=0.025, size=0.012, a0=math.pi / 4, c="galv", x=0.0, y=0.0):
    """Anchor bolts with washer + hex nut on a base plate (top at z)."""
    for k in range(n):
        a = a0 + TAU * k / n; bx, by = x + r * math.cos(a), y + r * math.sin(a)
        hm.cyl(bx, by, z, z + 0.004, size * 1.9, size * 1.9, c, 10, nobevel=True)                   # washer
        hm.cyl(bx, by, z + 0.004, z + 0.004 + size * 0.85, size * 1.6, size * 1.6, c, 6, smooth=False, nobevel=True)   # hex nut
        hm.cyl(bx, by, z + 0.004 + size * 0.85, z + 0.004 + size * 1.9, size * 0.85, size * 0.7, c, 8, nobevel=True)   # threaded end


def base_door(hm, r, z0, z1, width, facing=-1.0, c="galv", frame_c=None, lock_c="black_plastic"):
    """Service door on a round shaft (centred on the -Y side for facing=-1): raised curved panel with a frame and a lock."""
    ang = width / r; n = 6
    def ring(rr, z):
        return [(rr * math.sin(-ang / 2 + ang * i / n), facing * rr * math.cos(-ang / 2 + ang * i / n), z) for i in range(n + 1)]
    for rr, za, zb, cc in ((r + 0.006, z0 - 0.015, z1 + 0.015, frame_c or c), (r + 0.010, z0, z1, c)):
        bot = ring(rr, za); top = ring(rr, zb); inb = ring(r - 0.002, za); intp = ring(r - 0.002, zb)
        bm = hm.bm; mi = hm.mi(cc); n0 = len(bm.faces)
        vb = [bm.verts.new(p) for p in bot]; vt = [bm.verts.new(p) for p in top]; ib = [bm.verts.new(p) for p in inb]; it = [bm.verts.new(p) for p in intp]
        for i in range(n):
            for q in ((vb[i], vb[i + 1], vt[i + 1], vt[i]), (vt[i], vt[i + 1], it[i + 1], it[i]), (ib[i + 1], ib[i], vb[i], vb[i + 1])):
                f = bm.faces.new(q if facing < 0 else q[::-1]); f.material_index = mi; f.smooth = True
        for q in ((vb[0], vt[0], it[0], ib[0]), (vb[n], ib[n], it[n], vt[n])):
            f = bm.faces.new(q if facing < 0 else q[::-1]); f.material_index = mi
        hm._end(n0, True)
    zc = (z0 + z1) / 2 + (z1 - z0) * 0.25
    from .assets import _tube
    n0 = len(hm.bm.faces); _tube(hm.bm, [(0, facing * (r + 0.008), zc), (0, facing * (r + 0.02), zc)], 0.009, 8, hm.mi(lock_c)); hm._end(n0, True)
