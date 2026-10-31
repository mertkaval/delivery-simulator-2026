"""Side-by-side comparisons and numbers for VALIDATION.md (system Python: python -I compare.py ROOT).

Reads the video reference frames (evidence/all/frames), the renders (renders/, written by video_scene.py) and the
round renders kept in tmp/materials_asphalt; writes comparisons/*.png and comparisons/metrics.json."""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import view_match as vm  # noqa: E402

REF_REGION = (630, 98, 1931, 1399)          # the Render Result square in t2638 (view_match.render_region)
REF_CIRCLE = (648.6, 635.6, 616.2)          # sphere centre / radius in that square (circle fit, residual 0.44 px)
OUR_CIRCLE = (650.5, 650.5, 650.5 * 0.95)   # our 1301 px renders: centred, 95 % fill


def font(size):
    try: return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()


def panel(images, labels, out, height=None, gap=8, bar=34, title=None):
    ims = [im if isinstance(im, Image.Image) else Image.open(im).convert("RGB") for im in images]
    h = height or max(i.height for i in ims)
    ims = [i if i.height == h else i.resize((round(i.width * h / i.height), h), Image.LANCZOS) for i in ims]
    top = bar + (bar if title else 0)
    W = sum(i.width for i in ims) + gap * (len(ims) - 1)
    c = Image.new("RGB", (W, h + top), (18, 18, 18)); d = ImageDraw.Draw(c); x = 0
    if title: d.text((10, 6), title, fill=(255, 210, 90), font=font(20))
    for i, lab in zip(ims, labels):
        c.paste(i, (x, top)); d.text((x + 8, top - bar + 7), lab, fill=(235, 235, 235), font=font(18)); x += i.width + gap
    if out.lower().endswith(".jpg"): c.save(out, quality=90, subsampling=0)
    else: c.save(out)
    return out


def window(path, circle, win, size=420, resample=Image.NEAREST):
    im = Image.open(path).convert("RGB"); cx, cy, R = circle; x0, x1, y0, y1 = win
    return im.crop((int(cx + x0 * R), int(cy - y1 * R), int(cx + x1 * R), int(cy - y0 * R))).resize((size, size), resample)


def lum_log(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255
    return np.log(vm.srgb_to_linear(a) @ np.array([0.2126, 0.7152, 0.0722]) + 0.004)


WINDOWS = {"lit": (0.3, 0.7, 0.2, 0.6), "centre": (-0.2, 0.2, -0.2, 0.2), "right": (0.45, 0.8, -0.3, 0.05)}


def relief(path, circle):
    """Std of band-passed log luminance (fine: < 1.5 px, mid: 1.5-6 px) and mean luminance per window."""
    L = lum_log(path); cx, cy, R = circle
    hp1 = L - vm.blur(L, 1.5); hp2 = vm.blur(L, 1.5) - vm.blur(L, 6)
    out = {}
    for k, (x0, x1, y0, y1) in WINDOWS.items():
        sl = (slice(int(cy - y1 * R), int(cy - y0 * R)), slice(int(cx + x0 * R), int(cx + x1 * R)))
        out[k] = {"fine": round(float(hp1[sl].std()), 3), "mid": round(float(hp2[sl].std()), 3),
                  "mean_lum": round(float(np.exp(L[sl]).mean()), 3)}
    return out


def sectors(path):
    """Mean display-linear luminance in 12 sectors x 2 rings of the sphere (lighting fit)."""
    ref, X, Y, _ = vm.reference_grid(path, 64)
    m = (X ** 2 + Y ** 2) < 0.92 ** 2
    lp = vm.masked_blur(ref, m, 3.0)
    ang = np.degrees(np.arctan2(Y, X)) % 360; rad = np.sqrt(X ** 2 + Y ** 2); out = []
    for r0, r1 in ((0.0, 0.5), (0.5, 0.92)):
        for a0 in range(0, 360, 30):
            s = m & (ang >= a0) & (ang < a0 + 30) & (rad >= r0) & (rad < r1); out.append(float(lp[s].mean()))
    return np.array(out)


def chroma(path, circle):
    a = np.asarray(Image.open(path).convert("RGB")).astype(float) / 255; lin = vm.srgb_to_linear(a); cx, cy, R = circle; out = {}
    for k, (x0, x1, y0, y1) in (("lit", (0.3, 0.7, 0.2, 0.6)), ("centre", (-0.2, 0.2, -0.2, 0.2)), ("dark", (-0.7, -0.3, 0.1, 0.5))):
        w = lin[int(cy - y1 * R):int(cy - y0 * R), int(cx + x0 * R):int(cx + x1 * R)].reshape(-1, 3).mean(0)
        out[k] = [round(float(v), 3) for v in w / w.mean()]
    return out


def main(root):
    A = os.path.join(root, "tools/materials/reconstruction/asphalt")
    T = os.path.join(root, "tmp/materials_asphalt")
    R_ = lambda n: os.path.join(A, "renders", n)
    C_ = lambda n: os.path.join(A, "comparisons", n)
    os.makedirs(os.path.join(A, "comparisons"), exist_ok=True); os.makedirs(T, exist_ok=True)
    frames = os.path.join(A, "evidence/all/frames")
    ref_full = Image.open(os.path.join(frames, "t2638_final_render.png")).convert("RGB").crop(REF_REGION)
    ref_png = os.path.join(T, "ref_t2638_render.png"); ref_full.save(ref_png)
    intro = Image.open(os.path.join(frames, "t0003_intro_final_render.png")).convert("RGB")
    metrics = {}
    # 1 final: video | ours | ours albedo
    panel([ref_png, R_("PM_Asphalt_video.png"), R_("PM_Asphalt_flat.png")],
          ["video 26:38 F12 render (Cycles 3.2, machine_shop_02 HDRI)", "PM_Asphalt (Cycles 5.2, studio HDRI desaturated, fitted key)",
           "PM_Asphalt albedo only (no lighting)"], C_("cmp_final_video_vs_PM_Asphalt.jpg"), height=900,
          title="Same scene and framing, different patches (5.2 does not reproduce the exact field of the video: VALIDATION.md)")
    # 2 rounds
    r1 = os.path.join(T, "r1/PM_Asphalt_video.png")
    rounds = [ref_png] + ([r1] if os.path.exists(r1) else []) + [R_("PM_Asphalt_fw0.1_video.png"), R_("PM_Asphalt_video.png")]
    labs = ["video 26:38"] + (["round 1: 1024 px, FW 0.1, studio tint"] if os.path.exists(r1) else []) + \
           ["final lighting, FW 0.1 (the 5.2 default)", "final: FW 1.0 (3.2 relief), neutral fill"]
    panel(rounds, labs, C_("cmp_rounds.jpg"), height=640,
          title="Iterations: lighting fitted to the reference, then the bump filter width (the only material-side change)")
    # 3 zoom windows at the video's pixel scale
    tiles, labels = [], []
    for lab, p, circ in (("video 26:38", ref_png, REF_CIRCLE), ("FW 0.1 (5.2 default)", R_("PM_Asphalt_fw0.1_video.png"), OUR_CIRCLE),
                         ("FW 1.0 (final)", R_("PM_Asphalt_video.png"), OUR_CIRCLE)):
        col = Image.new("RGB", (420, 850), (18, 18, 18))
        col.paste(window(p, circ, WINDOWS["lit"]), (0, 0)); col.paste(window(p, circ, WINDOWS["centre"]), (0, 430))
        tiles.append(col); labels.append(lab)
    bt = os.path.join(T, "bumptest/e_dn_fw2.0_video.png")
    if os.path.exists(bt):
        col = Image.new("RGB", (420, 850), (18, 18, 18))
        col.paste(window(bt, OUR_CIRCLE, WINDOWS["lit"]), (0, 0)); col.paste(window(bt, OUR_CIRCLE, WINDOWS["centre"]), (0, 430))
        tiles.append(col); labels.append("FW 2.0 (too strong; round-2 light)")
    panel(tiles, labels, C_("cmp_zoom_bump_filter_width.jpg"),
          title="Same windows (lit upper right / centre), same pixel scale, nearest-neighbour: Bump Filter Width")
    # 4 close-up
    panel([os.path.join(A, "evidence/all/crops/c_t2510_viewport_closeup_reference.png"), R_("PM_AsphaltTutorial_closeup.png"),
           R_("PM_Asphalt_closeup.png")],
          ["video 25:10 viewport close-up (10 samples, roughness 0.5)", "PM_AsphaltTutorial, state at 25:10 (roughness 0.5)",
           "PM_Asphalt final (roughness ramp)"], C_("cmp_closeup.jpg"), height=760,
          title="Damaged patch close-up: pebbles (4D Voronoi 110), recessed edges, cracks; a different patch, similar zoom")
    # 5 intro overlay
    panel([intro.crop(REF_REGION) if intro.size == (2560, 1440) else intro, R_("PM_Asphalt_video.png")],
          ["video 00:03 intro overlay of the final render", "PM_Asphalt"], C_("cmp_intro_vs_PM_Asphalt.jpg"), height=800)
    # 6 literal twin vs controls
    a = np.asarray(Image.open(R_("PM_AsphaltTutorial_video.png")).convert("RGB")).astype(float)
    b = np.asarray(Image.open(R_("PM_Asphalt_video.png")).convert("RGB")).astype(float)
    d = np.abs(a - b); diff = Image.fromarray(np.clip(d * 10, 0, 255).astype(np.uint8))
    fa = np.asarray(Image.open(R_("PM_AsphaltTutorial_flat.png")).convert("RGB")).astype(float)
    fb = np.asarray(Image.open(R_("PM_Asphalt_flat.png")).convert("RGB")).astype(float)
    metrics["literal_vs_controls"] = {"render_mean_abs_8bit": round(float(d.mean()), 4), "render_max_abs_8bit": int(d.max()),
                                      "render_pixels_differing_gt2": round(float((d.max(axis=2) > 2).mean()), 5),
                                      "albedo_mean_abs_8bit": round(float(np.abs(fa - fb).mean()), 4),
                                      "albedo_max_abs_8bit": int(np.abs(fa - fb).max())}
    panel([R_("PM_AsphaltTutorial_video.png"), R_("PM_Asphalt_video.png"), diff],
          ["PM_AsphaltTutorial (ColorRamps, literal)", "PM_Asphalt (Map Range / Mix, controls)", "|difference| x 10"],
          C_("cmp_literal_vs_controls.jpg"), height=700)
    # 7 numbers
    S_ref = sectors(ref_png); S_our = sectors(R_("PM_Asphalt_video.png"))
    metrics["lighting_sectors"] = {"reference_inner": np.round(S_ref[:12], 3).tolist(), "reference_outer": np.round(S_ref[12:], 3).tolist(),
                                   "ours_inner": np.round(S_our[:12], 3).tolist(), "ours_outer": np.round(S_our[12:], 3).tolist(),
                                   "log_rms": round(float(np.sqrt(np.mean((np.log(S_our + 0.003) - np.log(S_ref + 0.003)) ** 2))), 3)}
    metrics["relief"] = {"video": relief(ref_png, REF_CIRCLE), "PM_Asphalt_fw1.0": relief(R_("PM_Asphalt_video.png"), OUR_CIRCLE),
                         "PM_Asphalt_fw0.1": relief(R_("PM_Asphalt_fw0.1_video.png"), OUR_CIRCLE),
                         "PM_AsphaltTutorial": relief(R_("PM_AsphaltTutorial_video.png"), OUR_CIRCLE)}
    if os.path.exists(bt): metrics["relief"]["PM_Asphalt_fw2.0_round2_light"] = relief(bt, OUR_CIRCLE)
    metrics["chroma"] = {"video": chroma(ref_png, REF_CIRCLE), "PM_Asphalt": chroma(R_("PM_Asphalt_video.png"), OUR_CIRCLE),
                         "PM_Asphalt_albedo": chroma(R_("PM_Asphalt_flat.png"), OUR_CIRCLE)}
    fl = np.asarray(Image.open(R_("PM_Asphalt_flat.png")).convert("RGB")).astype(float) / 255
    cx, cy, R = OUR_CIRCLE; yy, xx = np.indices(fl.shape[:2]); disk = np.hypot(xx - cx, yy - cy) < 0.9 * R
    lin = vm.srgb_to_linear(fl)[disk]
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    metrics["albedo_stats"] = {"mean_linear_rgb": np.round(lin.mean(0), 4).tolist(),
                               "lum_p5_p50_p95": np.round(np.percentile(lum, [5, 50, 95]), 4).tolist(),
                               "share_below_0.004": round(float((lum < 0.004).mean()), 4)}
    # 8 the road tool (road_check.py renders) and the view search (view_match.py check images)
    rc = [os.path.join(T, "road_check", "PM_Asphalt_mrs_road_%s.png" % e) for e in ("eevee", "cycles")]
    if all(os.path.exists(x) for x in rc):
        panel(rc, ["MRS residential road, Asphalt Material = PM_Asphalt (EEVEE)", "same road (Cycles)"], C_("cmp_mrs_road_eevee_cycles.jpg"))
    rr = [R_("PM_Asphalt_road.png"), R_("PM_Asphalt_baked_road.png")]
    if all(os.path.exists(x) for x in rr):
        panel(rr, ["PM_Asphalt live, object mode (7 x 20 m strip, eye 1.7 m, city HDRI)", "UV-mode bake (4 m tile, 1024 px) as an image material"],
              C_("cmp_road_live_vs_baked.jpg"))
    vmv = os.path.join(T, "match", "view_match_check.png"); vms = os.path.join(T, "synth", "match", "view_match_check.png")
    if os.path.exists(vmv) and os.path.exists(vms):
        panel([vmv, vms], ["video 26:38 | best view of our albedo (corr 0.21: no match)", "control: our render | recovered view (corr 0.63)"],
              C_("cmp_view_search.jpg"))
    with open(C_("metrics.json"), "w") as f: json.dump(metrics, f, indent=1)
    print(json.dumps(metrics, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "../../../../..")))
