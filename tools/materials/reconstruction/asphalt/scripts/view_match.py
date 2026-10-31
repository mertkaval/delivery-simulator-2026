"""Find the video camera's view of the sphere: search the camera direction (and roll, perspective distance) whose view
of our Albedo map best correlates with the video's final render. Object mode samples the video's exact 3D fields, so
if Blender 5.2 computes the same noise / Voronoi as 3.2 the cracks and damaged patches line up.

    python -I view_match.py FRAME.png MAPS_DIR OUT_DIR

FRAME: the video frame with the Render Result (t2638_final_render.png). MAPS_DIR: albedo_pano.npy from sphere_maps.py.
Writes OUT_DIR/view_match.json (best camera: direction from the sphere centre, roll, distance in radii, correlation,
the score distribution) and view_match_check.png (video | best view of our albedo | a random view)."""
import json
import math
import os
import sys

import numpy as np
from PIL import Image


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def gauss_kernel(sigma):
    r = max(1, int(round(3 * sigma)))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    return k / k.sum()


def blur(a, sigma, wrap_x=False):
    """Separable Gaussian blur of a 2D array (edges: reflect; wrap_x for panoramas)."""
    if sigma <= 0: return a
    k = gauss_kernel(sigma); r = len(k) // 2
    p = np.pad(a, ((0, 0), (r, r)), mode="wrap" if wrap_x else "reflect")
    a = sum(k[i] * p[:, i:i + a.shape[1]] for i in range(len(k)))
    p = np.pad(a, ((r, r), (0, 0)), mode="reflect")
    return sum(k[i] * p[i:i + a.shape[0], :] for i in range(len(k)))


def masked_blur(a, m, sigma):
    return blur(a * m, sigma) / np.maximum(blur(m.astype(np.float64), sigma), 1e-6)


def render_region(frame):
    mx = frame.max(axis=2)
    blk = mx < 6 / 255
    cols = np.where(blk.mean(axis=0) > 0.25)[0]; rows = np.where(blk.mean(axis=1) > 0.25)[0]
    return cols.min(), cols.max(), rows.min(), rows.max()


def fit_circle(sub):
    sph = sub.max(axis=2) > 10 / 255
    pts = []
    for r in range(0, sph.shape[0], 2):
        c = np.nonzero(sph[r])[0]
        if len(c) > 20: pts += [(c.min(), r), (c.max(), r)]
    for c in range(0, sph.shape[1], 2):
        r = np.nonzero(sph[:, c])[0]
        if len(r) > 20: pts += [(c, r.min()), (c, r.max())]
    P = np.array(pts, float)
    A = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]; b = (P ** 2).sum(1)
    cx, cy, c0 = np.linalg.lstsq(A, b, rcond=None)[0]
    return cx, cy, math.sqrt(c0 + cx * cx + cy * cy)


def sample_bilinear(img, x, y):
    h, w = img.shape[:2]
    x = np.clip(x, 0, w - 1.001); y = np.clip(y, 0, h - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def reference_grid(frame_path, n):
    fr = np.asarray(Image.open(frame_path).convert("RGB")).astype(np.float64) / 255.0
    x0, x1, y0, y1 = render_region(fr)
    sub = fr[y0:y1 + 1, x0:x1 + 1]
    cx, cy, R = fit_circle(sub)
    lum = srgb_to_linear(sub) @ np.array([0.2126, 0.7152, 0.0722])
    lum = blur(lum, 0.5 * R / n)                                  # anti-alias before sampling the grid
    g = (np.arange(n) + 0.5) / n * 2 - 1
    X, Y = np.meshgrid(g, -g)                                     # x right, y up
    ref = sample_bilinear(lum, cx + X * R, cy - Y * R)
    return ref, X, Y, dict(region=[int(x0), int(y0), int(x1), int(y1)], cx=cx, cy=cy, R=R)


def cam_points(X, Y, d):
    """Hit points on the unit sphere in camera space (x right, y up, z toward the camera at (0, 0, d)); the
    silhouette sits at image radius 1. d = None: orthographic."""
    rho2 = X ** 2 + Y ** 2
    if d is None:
        z = np.sqrt(np.clip(1 - rho2, 0, None)); return np.stack([X, Y, z], -1), rho2 < 1
    t = math.tan(math.asin(1.0 / d))
    dirs = np.stack([X * t, Y * t, -np.ones_like(X)], -1); dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
    C = np.array([0.0, 0.0, d]); cd = dirs @ C
    disc = cd ** 2 - (d * d - 1)
    s = -cd - np.sqrt(np.clip(disc, 0, None))
    return C + s[..., None] * dirs, disc > 0


def rotations(D, roll):
    """Camera-to-object rotations: columns (right, up, back) for camera position directions D (K, 3) and rolls (K,)."""
    f = -D
    z = np.array([0.0, 0.0, 1.0])
    r = np.cross(f, z); bad = np.linalg.norm(r, axis=1) < 1e-6
    r[bad] = np.cross(f[bad], np.array([0.0, 1.0, 0.0]))
    r /= np.linalg.norm(r, axis=1, keepdims=True)
    u = np.cross(r, f)
    c = np.cos(roll)[:, None]; s = np.sin(roll)[:, None]
    r2 = c * r + s * u; u2 = -s * r + c * u
    return np.stack([r2, u2, D], axis=2)                            # (K, 3, 3): object = R @ camera


def pano_lookup(pano, P):
    """pano (h, w) equirectangular as rendered by sphere_maps.py: lat = asin(y), lon = atan2(x, -z)."""
    h, w = pano.shape
    lon = np.arctan2(P[..., 0], -P[..., 2]); lat = np.arcsin(np.clip(P[..., 1], -1, 1))
    col = (lon / (2 * np.pi) + 0.5) * w - 0.5; row = (0.5 - lat / np.pi) * h - 0.5
    ci = np.mod(np.round(col).astype(int), w); ri = np.clip(np.round(row).astype(int), 0, h - 1)
    return pano[ri, ci]


def fib_sphere(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n); th = np.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)


def score(ref_bp, mask, pano, Pc, Rs):
    """Pearson correlation of the band-passed reference with the log albedo seen through each rotation."""
    pts = Pc[mask]                                                 # (N, 3) camera space
    P = np.einsum("kij,nj->kni", Rs, pts)                         # (K, N, 3) object space
    v = pano_lookup(pano, P)
    v = v - v.mean(axis=1, keepdims=True)
    rb = ref_bp[mask]; rb = rb - rb.mean()
    return (v @ rb) / (np.linalg.norm(v, axis=1) * np.linalg.norm(rb) + 1e-12)


def view_image(pano, Pc, valid, R):
    P = Pc @ R.T
    out = pano_lookup(pano, P); out[~valid] = np.nan
    return out


def to_png(a, path_or_none=None, lo=None, hi=None):
    m = np.isfinite(a)
    lo = np.percentile(a[m], 1) if lo is None else lo; hi = np.percentile(a[m], 99) if hi is None else hi
    b = np.clip((np.where(m, a, lo) - lo) / (hi - lo + 1e-12), 0, 1)
    return Image.fromarray((b * 255).astype(np.uint8))


def main(frame, maps_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    alb = np.load(os.path.join(maps_dir, "albedo_pano.npy"))
    alum = alb @ np.array([0.2126, 0.7152, 0.0722])
    logp = np.log(alum + 2e-3)
    result = {}
    # ---- coarse: 64 px grid, perspective d = 3.09 (default 50 mm lens filling 95 %), all directions and rolls
    n = 64
    ref, X, Y, geo = reference_grid(frame, n)
    result["reference"] = geo
    mask = (X ** 2 + Y ** 2) < 0.85 ** 2
    lref = np.log(ref + 2e-3)
    sig = 5.0
    ref_bp = blur(lref, 0.7) - masked_blur(lref, mask, sig)
    pano_c = blur(logp, 2048 / 64 / 4, wrap_x=True)                 # a little anti-aliasing at this scale
    pano_c = pano_c[::4, ::4]
    D = fib_sphere(6000)
    rolls = np.radians(np.arange(0, 360, 6.0))
    best = []
    for d in (3.09,):
        Pc, valid = cam_points(X, Y, d)
        m = mask & valid
        for ro in rolls:
            Rs = rotations(D, np.full(len(D), ro))
            for k0 in range(0, len(D), 1500):
                s = score(ref_bp, m, pano_c, Pc, Rs[k0:k0 + 1500])
                for j in np.argsort(s)[-5:]:
                    best.append((float(s[j]), k0 + int(j), float(ro), d))
    best.sort(reverse=True)
    allc = np.array([b[0] for b in best])
    result["coarse_top"] = [dict(corr=b[0], D=D[b[1]].round(4).tolist(), roll_deg=round(math.degrees(b[2]), 1), d=b[3]) for b in best[:10]]
    print("coarse top:", json.dumps(result["coarse_top"][:5]))
    # ---- refine around the top 5 distinct candidates: 128 px grid, finer directions / roll / distance
    n2 = 128
    ref2, X2, Y2, _ = reference_grid(frame, n2)
    mask2 = (X2 ** 2 + Y2 ** 2) < 0.9 ** 2
    lref2 = np.log(ref2 + 2e-3)
    ref2_bp = blur(lref2, 0.7) - masked_blur(lref2, mask2, sig * 2)
    pano_f = blur(logp, 2048 / 128 / 4, wrap_x=True)[::2, ::2]
    seeds = []
    for b in best:
        Db = D[b[1]]
        if all(np.dot(Db, s[0]) < math.cos(math.radians(8)) or abs(b[2] - s[1]) > math.radians(20) for s in seeds):
            seeds.append((Db, b[2]))
        if len(seeds) >= 5: break
    refined = []
    for Db, rb in seeds:
        # local tangent grid of directions +-4 deg, rolls +-6 deg, distances
        t1 = np.cross(Db, [0, 0, 1.0]); t1 = t1 / (np.linalg.norm(t1) + 1e-9); t2 = np.cross(Db, t1)
        offs = np.radians(np.arange(-4, 4.01, 0.5))
        Ds = np.array([Db + a * t1 + b * t2 for a in offs for b in offs]); Ds /= np.linalg.norm(Ds, axis=1, keepdims=True)
        for d in (2.2, 2.6, 3.09, 3.6, 4.5, 6.0, 10.0, None):
            Pc, valid = cam_points(X2, Y2, d)
            m = mask2 & valid
            for ro in rb + np.radians(np.arange(-6, 6.01, 1.0)):
                Rs = rotations(Ds, np.full(len(Ds), ro))
                s = score(ref2_bp, m, pano_f, Pc, Rs)
                j = int(np.argmax(s)); refined.append((float(s[j]), Ds[j], float(ro), d))
    refined.sort(key=lambda r: -r[0])
    top = refined[0]
    result["refined_top"] = [dict(corr=r[0], D=np.round(r[1], 4).tolist(), roll_deg=round(math.degrees(r[2]), 2), d=r[3]) for r in refined[:8]]
    result["coarse_score_stats"] = dict(n=len(allc), median=float(np.median(allc)), p99=float(np.percentile(allc, 99)), max=float(allc.max()))
    # random-view control: the same statistic for unrelated views
    rng = np.random.default_rng(1)
    Pc, valid = cam_points(X2, Y2, top[3]); m = mask2 & valid
    Dr = rng.normal(size=(400, 3)); Dr /= np.linalg.norm(Dr, axis=1, keepdims=True)
    sr = score(ref2_bp, m, pano_f, Pc, rotations(Dr, rng.uniform(0, 2 * np.pi, 400)))
    result["random_views"] = dict(mean=float(sr.mean()), std=float(sr.std()), max=float(sr.max()))
    print("refined top:", json.dumps(result["refined_top"][:3]))
    print("random views:", json.dumps(result["random_views"]))
    # check image: video | best view (albedo) | best view band-passed | video band-passed
    n3 = 384
    ref3, X3, Y3, _ = reference_grid(frame, n3)
    Pc3, valid3 = cam_points(X3, Y3, top[3])
    Rb = rotations(top[1][None, :], np.array([top[2]]))[0]
    pano_v = blur(logp, 1.0, wrap_x=True)
    view = view_image(pano_v, Pc3, valid3, Rb)
    ims = [to_png(np.where(valid3, np.log(ref3 + 2e-3), np.nan)), to_png(view)]
    W = sum(i.width for i in ims) + 10
    canvas = Image.new("RGB", (W, n3), (20, 20, 20)); x = 0
    for i in ims: canvas.paste(i.convert("RGB"), (x, 0)); x += i.width + 10
    canvas.save(os.path.join(out_dir, "view_match_check.png"))
    result["best"] = dict(corr=top[0], D=np.round(top[1], 5).tolist(), roll_deg=round(math.degrees(top[2]), 2), d=top[3],
                          R_cam_to_obj=np.round(Rb, 6).tolist())
    with open(os.path.join(out_dir, "view_match.json"), "w") as f: json.dump(result, f, indent=1)
    print("best:", json.dumps(result["best"]))


if __name__ == "__main__":
    main(*sys.argv[1:4])
