"""MRS foliage v5: Blender side of the Blender / Godot foliage comparison harness, plus the metrics.

Identical tree instances at identical cameras in both renderers (Godot side: tests/capture_foliage_v5.gd),
under a matched light rig (sun 3.5 W/m2 = Godot 1.114, uniform world (0.55, 0.68, 0.85) = Godot ambient
colour, Standard view transform = Godot linear tonemap), transparent film so the alpha channel is the
canopy silhouette.

  blender -b --factory-startup --python tools/roads/tests/foliage_v5_test.py -- render <variant> [opts]
      variant: lod0 | lod1 (the kit meshes with the v4 game material) | v5lod0 | v5lod1 | v5imp (v5 material /
      re-baked MRS LOD1 + hemi-octahedral impostor) | cycles (LOD0, Cycles path tracing: no mipmaps, reference)
      opts: --species a,b  --heights 1.7,7  --dists 8,20  --samples 64  --plants (hedge / boxwood shots only)
      writes tmp/roads/v5/foliage/harness.json (the shot list the Godot side reads) and
      tmp/roads/v5/foliage/blender_<variant>/<shot>.png
  blender -b --factory-startup --python tools/roads/tests/foliage_v5_test.py -- bake
      re-bakes assets/roads/foliage/ (game_trees.bake_foliage_assets)
  blender -b --factory-startup --python tools/roads/tests/foliage_v5_test.py -- video <path.json> <out_dir> [--samples 16]
      renders a camera path of the street block (tmp/roads/v4final/street_block_v4.blend, v4 QA light rig, v5 materials
      with --v5) to PNG frames f_<frame>.png (--step 2: every second frame)
  python tools/roads/tests/foliage_v5_test.py measure <dir> [<dir> ...]     (plain Python: numpy + PIL)
      per image: coverage (mean alpha), canopy linear luminance / sRGB colour (alpha >= 0.75, unpremultiplied),
      blotchiness (std of the 4x4-block luminance inside the canopy / its mean), silhouette IoU against the
      reference directory (first argument) -> <dir>/metrics.json
  python tools/roads/tests/foliage_v5_test.py table <ref_dir> <dir> ... -> markdown tables (stdout)
  python tools/roads/tests/foliage_v5_test.py sweep <ref_dir> <dir> ...  distance sweeps (capture_foliage_v5.gd sweep): per
      species the largest step-to-step change of coverage / luminance (2 m steps), and the largest one beyond what the
      reference (forced LOD0: the smooth change with distance) does at the same step = the LOD pop
  python tools/roads/tests/foliage_v5_test.py check     asserts the v5 acceptance limits on the measured harness
"""
import sys, os, json, math, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "tmp", "roads", "v5", "foliage")
SPECIES = ["plane_tree", "linden_a", "maple_a", "walnut_spring", "grove_a"]
DISTS = [8, 20, 40, 70, 120, 200]
HEIGHTS = [1.7, 7.0, 25.0]
AZIMUTH = 25.0            # camera azimuth off the -Y axis (not aligned with the old crossed impostor cards)
LENS = 30.0
RES = (1280, 720)
SUN_ROT = (52.0, 0.0, -35.0)
SUN_STRENGTH = 3.5
WORLD = (0.55, 0.68, 0.85)
PLANTS = ["hedge_section", "boxwood_ball", "shrub_b"]

try:
    import bpy
except ImportError:
    bpy = None


def _args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    return a


def _opt(args, name, default=None):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default


def shot_list(heights_by_species, plant_heights, species=SPECIES, heights=HEIGHTS, dists=DISTS):
    """Every camera of the harness (Blender Z-up coordinates)."""
    shots = []
    az = math.radians(AZIMUTH)
    for sid in species:
        H = heights_by_species[sid]
        for h in heights:
            for d in dists:
                shots.append({"name": "%s_d%03d_h%02d" % (sid, d, round(h)), "kind": "tree", "id": sid, "dist": d, "height": h,
                              "eye": [d * math.sin(az), -d * math.cos(az), h], "target": [0.0, 0.0, round(H * 0.55, 3)], "lens": LENS})
    for pid in PLANTS:
        ph = plant_heights.get(pid, 1.0)
        for d in (2.5, 6.0, 14.0):
            shots.append({"name": "%s_d%04.1f" % (pid, d), "kind": "plant", "id": pid, "dist": d, "height": 1.7,
                          "eye": [d * math.sin(az), -d * math.cos(az), 1.7], "target": [0.0, 0.0, round(ph * 0.5, 3)], "lens": LENS})
    # light-rig calibration: a grey (0.5) and a green (0.05, 0.12, 0.03) Lambert sphere
    for k, col in (("grey", [0.5, 0.5, 0.5]), ("green", [0.05, 0.12, 0.03])):
        shots.append({"name": "calib_%s" % k, "kind": "calib", "id": k, "color": col, "dist": 7.0, "height": 1.0,
                      "eye": [7.0 * math.sin(az), -7.0 * math.cos(az), 1.0], "target": [0.0, 0.0, 1.0], "lens": LENS})
    return shots


# ============================================================================= Blender
def _setup_scene(samples, engine="EEVEE"):
    for n in ("Cube", "Light", "Camera"):
        if bpy.data.objects.get(n): bpy.data.objects.remove(bpy.data.objects[n])
    sc = bpy.context.scene
    w = bpy.data.worlds.new("FoliageWorld"); w.use_nodes = True; sc.world = w
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*WORLD, 1.0); bg.inputs[1].default_value = 1.0
    ld = bpy.data.lights.new("FoliageSun", "SUN"); ld.energy = SUN_STRENGTH; ld.angle = math.radians(2.0)
    sun = bpy.data.objects.new("FoliageSun", ld); sc.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(v) for v in SUN_ROT)
    cam = bpy.data.objects.new("FoliageCam", bpy.data.cameras.new("FoliageCam")); sc.collection.objects.link(cam)
    cam.data.lens = LENS; cam.data.sensor_width = 36.0; cam.data.sensor_fit = "AUTO"; cam.data.clip_end = 3000.0; cam.data.clip_start = 0.05
    sc.camera = cam
    r = sc.render
    if engine == "CYCLES":
        r.engine = "CYCLES"
        sc.cycles.samples = samples; sc.cycles.use_denoising = False
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for dt in ("OPTIX", "CUDA"):
                try:
                    prefs.compute_device_type = dt; prefs.get_devices()
                    if any(d.type == dt for d in prefs.devices):
                        for d in prefs.devices: d.use = d.type == dt
                        sc.cycles.device = "GPU"; break
                except TypeError:
                    continue
        except Exception as e:
            print("cycles device:", e)
    else:
        try: r.engine = "BLENDER_EEVEE"
        except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
        sc.eevee.taa_render_samples = samples
    r.film_transparent = True
    r.resolution_x, r.resolution_y = RES; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGBA"; r.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0; sc.view_settings.gamma = 1.0
    return sc, cam


def _look(cam, eye, target, lens):
    from mathutils import Vector
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def _calib_sphere(sc, col):
    me = bpy.data.meshes.new("calib")
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    m = bpy.data.materials.new("calib_mat"); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*col, 1.0); b.inputs["Roughness"].default_value = 1.0
    b.inputs["Specular IOR Level"].default_value = 0.0
    me.materials.append(m)
    o = bpy.data.objects.new("calib", me); o.location = (0, 0, 1.0); sc.collection.objects.link(o)
    return o


def render_variant(variant, args):
    sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
    from mrs import game_trees as gt
    samples = int(_opt(args, "--samples", "64"))
    v5 = variant.startswith("v5")
    gt.build_game_trees(plants=True, version=5 if v5 else 4)
    if variant == "v5imp":
        gt.build_impostor_library()
    sc, cam = _setup_scene(samples, "CYCLES" if variant == "cycles" else "EEVEE")
    heights = {sid: float(bpy.data.objects[gt.MRS + "GTree_" + sid]["mrs_tree_height"]) for sid in gt.TREES}
    pheights = {pid: float(bpy.data.objects[gt.MRS + "GPlant_" + pid]["mrs_height"]) for pid in PLANTS if bpy.data.objects.get(gt.MRS + "GPlant_" + pid)}
    all_shots = shot_list(heights, pheights)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "harness.json"), "w") as f:
        json.dump({"shots": all_shots, "res": RES, "sun_rot": SUN_ROT, "sun_strength": SUN_STRENGTH, "world": WORLD,
                   "heights": heights, "plant_heights": pheights}, f, indent=1)
    sp = _opt(args, "--species"); hs = _opt(args, "--heights"); ds = _opt(args, "--dists")
    want = [s for s in all_shots if (not sp or s["id"] in sp.split(",") or s["kind"] != "tree")
            and (not hs or s["kind"] != "tree" or any(abs(s["height"] - float(x)) < 0.01 for x in hs.split(",")))
            and (not ds or s["kind"] != "tree" or str(s["dist"]) in ds.split(","))]
    if "--plants" in args: want = [s for s in want if s["kind"] in ("plant", "calib")]
    if "--trees" in args: want = [s for s in want if s["kind"] in ("tree", "calib")]
    if "--nospec" in args:
        for m in bpy.data.materials:
            for n in (m.node_tree.nodes if m.node_tree else []):
                if n.type == "BSDF_PRINCIPLED": n.inputs["Specular IOR Level"].default_value = 0.0
    if "--notrans" in args:
        for m in bpy.data.materials:
            for n in (m.node_tree.nodes if m.node_tree else []):
                if n.type == "MIX_SHADER" and abs(n.inputs[0].default_value - 0.25) < 1e-4 and not n.inputs[0].is_linked: n.inputs[0].default_value = 0.0
    if "--thin" in args:
        for m in bpy.data.materials:
            if not m.get("mrs_v5") or m.get("mrs_kind") != "leaves": continue
            try: m.thickness_mode = "SLAB"
            except Exception as e: print("thickness_mode", e)
            out = next(n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL")
            v = m.node_tree.nodes.new("ShaderNodeValue"); v.outputs[0].default_value = 0.0
            m.node_tree.links.new(v.outputs[0], out.inputs["Thickness"])
    if _opt(args, "--rig") == "v4":
        # the street-block QA rig (mrs.qa.ensure_camera_and_sun): same sun / world, AgX view transform
        sc.view_settings.view_transform = "AgX"
    if "--noshadow" in args:
        bpy.data.lights["FoliageSun"].use_shadow = False
    out = os.path.join(OUT, "blender_" + variant + ("_" + _opt(args, "--tag") if _opt(args, "--tag") else "")); os.makedirs(out, exist_ok=True)
    cur = None; obj = None
    t0 = time.time()
    for s in want:
        key = (s["kind"], s["id"])
        if key != cur:
            if obj is not None:
                bpy.data.objects.remove(obj)
            cur = key
            if s["kind"] == "calib":
                obj = _calib_sphere(sc, s["color"])
            elif s["kind"] == "plant":
                src = bpy.data.objects[gt.MRS + "GPlant_" + s["id"]]
                obj = bpy.data.objects.new("H_" + s["id"], src.data); sc.collection.objects.link(obj)
            else:
                name = gt.MRS + "GTree_" + s["id"] + ("_LOD1" if variant in ("lod1", "v5lod1") else "")
                if variant == "v5imp": name = gt.MRS + "GTree_" + s["id"] + "_IMP"
                src = bpy.data.objects[name]
                obj = bpy.data.objects.new("H_" + s["id"], src.data); sc.collection.objects.link(obj)
                if variant == "v5imp":
                    gt.impostor_face_camera(obj, cam)
            obj.hide_render = False; obj.hide_viewport = False
        _look(cam, s["eye"], s["target"], s["lens"])
        if variant == "v5imp" and s["kind"] == "tree":
            bpy.context.view_layer.update(); gt.impostor_face_camera(obj, cam)
        sc.render.filepath = os.path.join(out, s["name"] + ".png")
        bpy.ops.render.render(write_still=True)
    print("RENDERED %d shots of %s in %.1fs" % (len(want), variant, time.time() - t0))


HEDGE_LAYOUT = [["hedge_section", -4.8, 0.0], ["hedge_section", -2.4, 0.0], ["hedge_section", 0.0, 0.0], ["hedge_section", 2.4, 0.0],
                ["hedge_section", 4.8, 0.0], ["boxwood_ball", -3.0, -1.6], ["boxwood_ball", 0.0, -1.6], ["boxwood_ball", 3.0, -1.6], ["shrub_b", 6.8, -1.2]]


def render_hedges(version):
    """The hedge scene of capture_foliage_v5.gd (hedges mode) under the v4 QA light rig (mrs.qa: sun 3.5, world
    (0.55, 0.68, 0.85), AgX) with the v4 or v5 game materials -> tmp/roads/v5/foliage/hedges/blender_v<version>.png"""
    sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
    from mrs import game_trees as gt, qa
    for n in ("Cube", "Light", "Camera"):
        if bpy.data.objects.get(n): bpy.data.objects.remove(bpy.data.objects[n])
    gt.build_game_trees(plants=True, version=version)
    sc = bpy.context.scene
    me = bpy.data.meshes.new("ground"); me.from_pydata([(-450, -450, -0.12), (450, -450, -0.12), (450, 450, -0.12), (-450, 450, -0.12)], [], [(0, 1, 2, 3)])
    gm = bpy.data.materials.new("ground"); gm.use_nodes = True
    b = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); b.inputs["Base Color"].default_value = (0.16, 0.24, 0.09, 1); b.inputs["Roughness"].default_value = 0.95
    me.materials.append(gm); sc.collection.objects.link(bpy.data.objects.new("ground", me))
    for pid, x, y in HEDGE_LAYOUT:
        o = bpy.data.objects.new("H_" + pid, bpy.data.objects[gt.MRS + "GPlant_" + pid].data); sc.collection.objects.link(o)
        o.location = (x, y, 0); o.scale = (1.15,) * 3 if pid == "boxwood_ball" else (1, 1, 1)
    out = os.path.join(OUT, "hedges"); os.makedirs(out, exist_ok=True)
    qa.render(os.path.join(out, "blender_v%d.png" % version), (1.0, -7.5, 1.7), (0.5, 0.0, 0.7), 30.0, scene=sc, samples=32)


def render_video(path_json, out_dir, args):
    """Camera path (list of {eye, target, lens} per frame, Blender coords) through the v4 street block."""
    samples = int(_opt(args, "--samples", "16"))
    blend = _opt(args, "--blend", os.path.join(ROOT, "tmp", "roads", "v4final", "street_block_v4.blend"))
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.data.scenes.get("MRS_StreetBlock") or bpy.context.scene
    if bpy.context.window is not None: bpy.context.window.scene = sc
    sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
    from mrs import qa, game_trees as gt
    if "--v5" in args:
        print("v5 materials:", gt.upgrade_materials(version=5))
    cam, _ = qa.ensure_camera_and_sun(sc)
    with open(path_json) as f:
        frames = json.load(f)["frames"]
    r = sc.render
    try: r.engine = "BLENDER_EEVEE"
    except TypeError: r.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = samples
    w, h = (int(x) for x in _opt(args, "--res", "1280x720").split("x"))
    r.resolution_x, r.resolution_y = w, h; r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGB"; r.image_settings.color_depth = "8"
    out_dir = os.path.abspath(out_dir)        # a relative render path is not resolved against the cwd
    os.makedirs(out_dir, exist_ok=True)
    step = int(_opt(args, "--step", "1"))
    t0 = time.time()
    for i in range(0, len(frames), step):
        fr = frames[i]
        qa.look(cam, fr["eye"], fr["target"], fr.get("lens", 30.0))
        r.filepath = os.path.join(out_dir, "f_%04d.png" % i)
        bpy.ops.render.render(write_still=True, scene=sc.name)
    print("VIDEO %d frames in %.1fs" % (len(range(0, len(frames), step)), time.time() - t0))


# ============================================================================= metrics (plain Python)
def _load(path):
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
    return im


def _lin(c):
    import numpy as np
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _srgb(c):
    import numpy as np
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def measure_image(path, bg=None, ref_alpha=None):
    """bg: linear background colour mixed into the edge pixels (Godot's resolved transparent clear colour);
    None for straight-alpha images (Blender film transparent)."""
    import numpy as np
    im = _load(path)
    a = im[..., 3]
    rgb = _lin(im[..., :3])
    if bg is not None:
        rgb = (rgb - (1.0 - a[..., None]) * np.array(bg)[None, None, :]) / np.maximum(a[..., None], 1e-3)
    m = a >= 0.75
    res = {"coverage": float(a.mean()), "pixels": float(a.sum())}
    if m.sum() >= 4:
        lum = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
        res["lum"] = float(lum[m].mean())
        res["rgb"] = [float(x) for x in rgb[m].mean(0)]
        res["srgb"] = [int(round(x * 255)) for x in _srgb(rgb[m].mean(0))]
        # blotchiness: luminance of 4x4 blocks fully inside the canopy, std / mean
        H, W = a.shape; h4, w4 = H // 4, W // 4
        lb = lum[:h4 * 4, :w4 * 4].reshape(h4, 4, w4, 4).mean((1, 3))
        mb = m[:h4 * 4, :w4 * 4].reshape(h4, 4, w4, 4).all((1, 3))
        if mb.sum() >= 4:
            res["blotch"] = float(lb[mb].std() / max(lb[mb].mean(), 1e-4))
    if ref_alpha is not None:
        def down(x):
            H, W = x.shape; return x[:H // 4 * 4, :W // 4 * 4].reshape(H // 4, 4, W // 4, 4).mean((1, 3))
        p, q = down(a) > 0.5, down(ref_alpha) > 0.5
        u = (p | q).sum()
        res["iou"] = float((p & q).sum() / u) if u else 1.0
    return res


def measure_dirs(dirs, bg_for=None):
    import numpy as np
    ref = dirs[0]
    out_all = {}
    for d in dirs:
        bg = None
        meta = os.path.join(d, "capture.json")
        if os.path.exists(meta):
            with open(meta) as f:
                bg = json.load(f).get("bg_linear")
        res = {}
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".png"): continue
            rp = os.path.join(ref, fn)
            ra = _load(rp)[..., 3] if os.path.exists(rp) else None
            res[fn[:-4]] = measure_image(os.path.join(d, fn), bg, ra)
        with open(os.path.join(d, "metrics.json"), "w") as f:
            json.dump(res, f, indent=1)
        out_all[d] = res
        print("measured", d, len(res))
    return out_all


def _metrics(d):
    with open(os.path.join(d, "metrics.json")) as f:
        return json.load(f)


def table(ref, dirs, group="dist", heights=(1.7, 7.0, 25.0)):
    """Markdown: per distance (rows) and height, coverage / luminance relative to the reference and IoU."""
    R = _metrics(ref)
    D = {d: _metrics(d) for d in dirs}
    lines = []
    for h in heights:
        hdr = "| d (m) | " + " | ".join("%s cov / lum / IoU / blotch" % os.path.basename(d) for d in [ref] + dirs) + " |"
        lines.append("\neye %.1f m (mean over species; cov and lum relative to %s)\n" % (h, os.path.basename(ref)))
        lines.append(hdr); lines.append("|" + "---|" * (len(dirs) + 2))
        for dist in DISTS:
            row = ["%d" % dist]
            for d in [ref] + dirs:
                M = R if d == ref else D[d]
                cs, ls, ious, bl = [], [], [], []
                for sid in SPECIES:
                    k = "%s_d%03d_h%02d" % (sid, dist, round(h))
                    if k not in M or k not in R: continue
                    r0, m = R[k], M[k]
                    if r0["coverage"] > 0: cs.append(m["coverage"] / r0["coverage"])
                    if "lum" in m and "lum" in r0: ls.append(m["lum"] / r0["lum"])
                    if "iou" in m: ious.append(m["iou"])
                    if "blotch" in m: bl.append(m["blotch"])
                f = lambda v: ("%.2f" % (sum(v) / len(v))) if v else "-"
                row.append("%s / %s / %s / %s" % (f(cs), f(ls), f(ious), f(bl)))
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def sweep_report(ref, dirs):
    import re
    def series(d):
        out = {}
        for fn in sorted(os.listdir(d)):
            m = re.match(r"(.+)_d(\d{3})\.png$", fn)
            if not m: continue
            r = measure_image(os.path.join(d, fn), (json.load(open(os.path.join(d, "capture.json"))).get("bg_linear") if os.path.exists(os.path.join(d, "capture.json")) else None))
            out.setdefault(m.group(1), []).append((int(m.group(2)), r["coverage"], r.get("lum", 0.0)))
        return out
    R = series(ref)
    res = {}
    for d in [ref] + dirs:
        S = R if d == ref else series(d)
        res[d] = {}
        for sid, pts in S.items():
            ref_pts = {p[0]: p for p in R.get(sid, [])}
            worst = (0.0, 0, 0.0)
            worst_extra = (0.0, 0)
            gaps = 0
            for (d0, c0, l0), (d1, c1, l1) in zip(pts, pts[1:]):
                jc = abs(c1 - c0) / max(c0, 1e-6)
                jl = abs(l1 - l0) / max(l0, 1e-6) if l0 > 0 else 0.0
                if jc > worst[0]: worst = (jc, d1, jl)
                if d0 in ref_pts and d1 in ref_pts:
                    rc = abs(ref_pts[d1][1] - ref_pts[d0][1]) / max(ref_pts[d0][1], 1e-6)
                    if jc - rc > worst_extra[0]: worst_extra = (jc - rc, d1)
                if d1 in ref_pts and c1 < 0.7 * ref_pts[d1][1]: gaps += 1
            res[d][sid] = {"max_cov_jump": round(worst[0], 3), "at_m": worst[1], "pop": round(worst_extra[0], 3), "pop_at_m": worst_extra[1],
                           "steps_below_70pct_cov": gaps}
        print(os.path.basename(d), json.dumps(res[d]))
    with open(os.path.join(OUT, "sweep_report.json"), "w") as f: json.dump(res, f, indent=1)
    return res


def check():
    """Acceptance limits of the v5 foliage (fails loudly): Godot v5 vs Blender v5 LOD0 at every harness distance and eye
    height - LOD0 coverage and luminance within 6 %, LOD1 within 6 % from 70 m, impostor within 6 % at 200 m,
    auto LOD coverage never below 0.9 (no missing trees); Blender v5 coverage within 5 % of Cycles."""
    def M(n): return json.load(open(os.path.join(OUT, n, "metrics.json")))
    R = M("blender_v5lod0")
    errs = []
    def mean(v): return sum(v) / len(v)
    for var, dists, tol in [("godot_after_lod0", DISTS, 0.06), ("godot_after_lod1", [70, 120, 200], 0.06), ("godot_after_imp", [200], 0.06), ("godot_after_auto", DISTS, 0.06)]:
        D = M(var)
        for h in HEIGHTS:
            for dist in dists:
                ks = ["%s_d%03d_h%02d" % (s, dist, round(h)) for s in SPECIES]
                cov = mean([D[k]["coverage"] / R[k]["coverage"] for k in ks]); lum = mean([D[k]["lum"] / R[k]["lum"] for k in ks])
                if abs(cov - 1) > tol or abs(lum - 1) > tol: errs.append("%s d%d h%.0f cov %.3f lum %.3f" % (var, dist, h, cov, lum))
    C = M("blender_cycles")
    for k, c in C.items():
        if k in R and not k.startswith("calib") and abs(c["coverage"] / R[k]["coverage"] - 1) > 0.05 and R[k]["coverage"] > 0.002:
            errs.append("blender v5 vs cycles %s %.3f" % (k, c["coverage"] / R[k]["coverage"]))
    print("FOLIAGE_V5 CHECK", "FAILED" if errs else "OK", len(errs))
    for e in errs[:40]: print("  ", e)
    return not errs


if __name__ == "__main__":
    args = _args()
    mode = args[0] if args else "render"
    if bpy is not None:
        import traceback
        try:
            if mode == "render":
                render_variant(args[1] if len(args) > 1 else "lod0", args)
            elif mode == "bake":
                sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
                from mrs import game_trees as gt
                gt.bake_foliage_assets(args)
            elif mode == "video":
                render_video(args[1], args[2], args)
            elif mode == "hedges":
                render_hedges(int(args[1]) if len(args) > 1 else 5)
            print("FOLIAGE_V5 OK")
        except Exception:
            traceback.print_exc(); print("FOLIAGE_V5 FAILED")
    else:
        if mode == "measure":
            measure_dirs(args[1:])
        elif mode == "table":
            print(table(args[1], args[2:]))
        elif mode == "sweep":
            sweep_report(args[1], args[2:])
        elif mode == "check":
            sys.exit(0 if check() else 1)
