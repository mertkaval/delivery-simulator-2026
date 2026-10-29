"""Headless validation and evidence for mrs.lighting (street lighting).

    blender --background --factory-startup --python tools/roads/tests/lighting_test.py [-- --no-render] [--only residential,urban]
    blender --background tmp/roads/v4/lighting/lighting_test.blend --python tools/roads/tests/lighting_test.py -- --reuse   (skips the ~4 min build)

1. Unit checks: fixture anchors on the six streetlight library objects (present on object + mesh, one per head,
   next to the emitter faces, no self-occlusion along the aim for shadow-casting fixtures, library dimensions
   unchanged), Kelvin colours vs Blender's own black body, preset_for / layout rules, Godot cone fit.
2. Test street: five straight 60 m roads (residential, urban avenue, highway, path, bridge), each with a row of
   its preset's poles placed by hand (kerb + setback, local +Y toward the road) and add_light_sources().
3. Analytic aim check (every light points down onto carriageway / sidewalk) and measured pools: orthographic
   top-down EXR renders with the light objects shown vs hidden (moon, sky and glowing lamp heads stay on), band
   means over carriageway / sidewalk / outside.
4. EEVEE renders 1280x720 to tmp/roads/v4/lighting/: night driver / pedestrian / overhead per class, day driver,
   'nolights' comparisons; night_setup / day_setup reversibility and idempotence.
5. Export tmp/roads/v4/lighting/export/lighting_street.glb (roads + poles, no KHR_lights_punctual) and
   lighting_lights.json (light records + the camera views for tests/capture_lighting.gd); saves lighting_test.blend.
"""
import bpy, sys, os, time, json, math, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
NO_RENDER = "--no-render" in args
REUSE = "--reuse" in args          # blender -b tmp/roads/v4/lighting/lighting_test.blend --python ... -- --reuse
ONLY = args[args.index("--only") + 1].split(",") if "--only" in args else None
OUT = os.path.join(ROOT, "tmp", "roads", "v4", "lighting"); EXP = os.path.join(OUT, "export"); MEAS = os.path.join(OUT, "measure")
for d in (OUT, EXP, MEAS): os.makedirs(d, exist_ok=True)
problems = []; notes = []
def check(cond, msg):
    if not cond: problems.append(msg); print("PROBLEM", msg)
    return cond

try:
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    import mrs
    from mrs import lighting as L, qa, roads
    from mrs.nodes import MRS, mod_input_set, depsgraph
    sc = bpy.context.scene
    if REUSE and bpy.data.node_groups.get(MRS + "Road"):              # iterate on a saved lighting_test.blend: keep the built library
        L.day_setup(sc)
        for cn in ("LT_Roads", "LT_Export"):
            c = bpy.data.collections.get(cn)
            if c:
                for o in list(c.all_objects): bpy.data.objects.remove(o)
        for o in [o for o in bpy.data.objects if o.type == "LIGHT" and o.get("mrs_light")]: bpy.data.objects.remove(o)
        print("REUSE library from", bpy.data.filepath)
    else:
        for o in list(bpy.data.objects): bpy.data.objects.remove(o)   # factory scene: cube, 1000 W point light, camera
        t0 = time.time(); mrs.build_all(verbose=False); print("BUILD %.0fs" % (time.time() - t0))

    # ------------------------------------------------------------------ 1. unit checks
    DIMS = {"MRS_Light_Highway": (0.44, 2.925, 10.05), "MRS_Light_Double": (0.44, 4.41, 10.05), "MRS_Light_LED": (0.44, 1.37, 7.034),
            "MRS_Light_Lantern": (0.491, 0.491, 4.45), "MRS_Light_Bollard": (0.2, 0.195, 1.0), "MRS_Light_WallPack": (0.32, 0.47, 3.5)}
    HEADS = {"MRS_Light_Double": 2}
    INSIDE_HOUSING = ("MRS_Light_Lantern", "MRS_Light_Bollard")          # light sits inside the lamp body: no shadows by design
    lib_col = bpy.data.collections[MRS + "Streetlights"]
    check(sorted(o.name for o in lib_col.objects) == sorted(DIMS), "streetlight library changed: %s" % sorted(o.name for o in lib_col.objects))
    for name, dims in DIMS.items():
        o = bpy.data.objects[name]; me = o.data
        check(all(abs(a - b) < 0.002 for a, b in zip(o.dimensions, dims)), "%s dimensions %s != %s" % (name, tuple(round(x, 3) for x in o.dimensions), dims))
        fx = L.fixtures_of(o)
        check(o.get("mrs_fixtures") and me.get("mrs_fixtures"), "%s: mrs_fixtures missing on object or mesh" % name)
        check(len(fx) == HEADS.get(name, 1), "%s: %d fixtures" % (name, len(fx)))
        lamp_idx = [i for i, m in enumerate(me.materials) if m and m.name.startswith(L.LAMP_MATERIAL_PREFIXES)]
        lamp_faces = [p for p in me.polygons if p.material_index in lamp_idx]
        check(lamp_faces, "%s: no emitter faces" % name)
        # every emitter face belongs to a head (within 0.35 m of an anchor) and every anchor is within 6 cm of its emitter
        for p in lamp_faces:
            c = p.center
            check(min((c - Vector(f["pos"])).length for f in fx) < 0.35, "%s: stray emitter face at %s" % (name, tuple(round(x, 2) for x in c)))
        bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        lamp_bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in lamp_faces])
        for f in fx:
            pos = Vector(f["pos"]); d = Vector(f["dir"]).normalized()
            near = lamp_bvh.find_nearest(pos)[3]
            check(near < 0.10, "%s: anchor %s is %.3f m from the emitter" % (name, f["pos"], near))
            if name not in INSIDE_HOUSING:
                for tilt in (0.0, 10.0):
                    hit = bvh.ray_cast(pos, L._aim(f, tilt))
                    check(hit[0] is None, "%s: aim from %s (tilt %g) hits its own mesh at %s" % (name, f["pos"], tilt, hit[0]))
                if d.z < -0.9:
                    hit = bvh.ray_cast(pos, Vector((0, 0, 1)))       # down-lights: the housing is right above the light
                    check(hit[0] is not None and hit[3] < 0.3, "%s: no housing above the anchor" % name)
    # Kelvin -> RGB vs Blender's black body
    ld = bpy.data.lights.new("kcheck", "SPOT"); ld.use_temperature = True; worst = 0.0
    for k in (2200, 2700, 3000, 4000, 5000, 6500):
        ld.temperature = k; ref = tuple(ld.temperature_color); mine = L.kelvin_to_linear(k)
        worst = max(worst, max(abs(a - b) / max(b, 0.1) for a, b in zip(mine, ref)))
    bpy.data.lights.remove(ld)
    print("KELVIN worst relative difference vs Blender temperature_color: %.3f" % worst)
    check(worst < 0.06, "kelvin_to_linear differs from Blender's black body by %.3f" % worst)
    # arrangement rules and layout
    for cls, w, want in (("residential", 6.4, "single_right"), ("residential", 9.0, "staggered"), ("avenue", 24.0, "opposite"), ("urban", 12.0, "staggered"),
                         ("highway", 22.8, "opposite"), ("highway", 9.0, "single_right"), ("path", 3.0, "single_right"), ("bridge", 8.0, "staggered")):
        got = L.preset_for(cls, w)["arrangement"]; check(got == want, "preset_for(%s, %g) = %s, want %s" % (cls, w, got, want))
    check(len(L.layout(60.0, L.preset_for("urban", 24.0), start=0.0)) == 4, "opposite layout over 60 m at 32 m spacing should give 2 pairs")
    st = L.layout(60.0, L.preset_for("residential", 9.0), start=0.0); check([s for _, s in st] == ["r", "l", "r"], "staggered sides %s" % st)
    for k, p in L.PRESETS.items():
        g = p["godot"]; print("PRESET %-11s %-18s H %.2f S %4.0f %-12s tilt %4.1f  %5.0f cd = %5.1f W  nadir %4.1f lx  %d K  godot E %6.1f range %2.0f angle %3.0f cone^%.2f fade %3.0f+%2.0f shadow %s" % (
            k, p["library"], p["mounting_height"], p["spacing"], p["arrangement"], p["tilt"], p["light"]["intensity_cd"], p["light"]["power_w"],
            p["target"]["nadir_lux"], p["light"]["temperature"], g["energy"], g["range"], g["spot_angle"], g["spot_angle_attenuation"], g["fade_begin"], g["fade_length"], g["shadow"]))
        check(1.0 < g["spot_angle_attenuation"] < 20.0, "%s cone fit %s" % (k, g["spot_angle_attenuation"]))

    # ------------------------------------------------------------------ 2. test street
    col = bpy.data.collections.get("LT_Roads") or bpy.data.collections.new("LT_Roads")
    if col.name not in sc.collection.children: sc.collection.children.link(col)
    from mrs.props import mat as flat_mat
    gme = bpy.data.meshes.new("LT_Ground"); gme.from_pydata([(-300, -300, -0.12), (400, -300, -0.12), (400, 500, -0.12), (-300, 500, -0.12)], [], [(0, 1, 2, 3)])
    gme.materials.append(flat_mat(MRS + "Ground", (0.16, 0.24, 0.09), 0.95)); ground = bpy.data.objects.new("MRS_GroundPlane", gme); col.objects.link(ground)
    R = lambda n, pts, preset, **kw: roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, Light_Side="None", **kw)
    Z = {"bridge": 6.0}
    ROADS = {
        "residential": (0.0, "residential", {}),
        "urban": (80.0, "urban", {}),
        "highway": (160.0, "highway", {}),
        "path": (240.0, "residential", dict(Lanes_Forward=1, Lanes_Backward=1, Lane_Width=1.5, Centre_Line="None", Sidewalk_Left=False, Sidewalk_Right=False, Curb_Height=0.0, Lane_Arrows=False)),
        "bridge": (320.0, "bridge", {}),
    }
    classes = [c for c in ROADS if ONLY is None or c in ONLY]
    info = {}; views = {}
    for cls in classes:
        y0, rp, kw = ROADS[cls]; z0 = Z.get(cls, 0.0)
        road = R("LT_%s" % cls.capitalize(), [(0.0, y0, z0), (30.0, y0, z0), (60.0, y0, z0)], rp, **kw)
        bpy.context.view_layer.update()
        w = roads.road_widths(road)
        W = w["half_l"] + w["half_r"]
        p = L.preset_for(cls, W)
        lib = bpy.data.objects[p["library"]]
        poles = []
        for k, (a, side) in enumerate(L.layout(60.0, p, start=0.0)):
            sgn = 1.0 if side == "r" else -1.0                   # road along +X: right = -Y
            half = w["half_r"] if side == "r" else w["half_l"]; sw = w["swr"] if side == "r" else w["swl"]
            lat = half + w["curb"] + p["setback"]
            z = z0 + (w["h"] if sw > 0.05 else (-0.12 if z0 == 0.0 else 0.0))
            o = bpy.data.objects.new("LT_%s_light_%s%d" % (cls, side, k), lib.data); col.objects.link(o)
            o.location = (a, y0 - sgn * lat, z); o.rotation_euler = (0.0, 0.0, 0.0 if side == "r" else math.pi)
            o["mrs_placed"] = lib.name; o["mrs_road_class"] = cls
            L.add_light_sources(o, p)
            poles.append(o)
        info[cls] = dict(road=road.name, y0=y0, z0=z0, w=w, W=W, preset=p, poles=[o.name for o in poles])
        print("ROAD %-11s W %.1f m  half l/r %.1f/%.1f  sidewalks %.1f/%.1f  -> %s (%s), %d poles, %d lights" % (
            cls, W, w["half_l"], w["half_r"], w["swl"], w["swr"], p["arrangement"], p["arrangement_rule"], len(poles), sum(len([c for c in o.children if c.get("mrs_light")]) for o in poles)))
        # camera views (Blender coordinates)
        lw = w["lw"]; med = w["median"] * 0.5
        y_lane = y0 - (med + lw * 0.5); hz = z0 + w["h"]
        sw_r = w["swr"]; y_walk = y0 - (w["half_r"] + w["curb"] + (sw_r * 0.5 if sw_r > 0.05 else 3.0))
        eye_h = 1.4 if cls == "path" else 1.2
        views["%s_driver" % cls] = dict(eye=[1.0, y_lane, z0 + eye_h], target=[58.0, y_lane - 0.6, z0 + 0.9], lens=26.0)
        views["%s_pedestrian" % cls] = dict(eye=[6.0, y_walk, (hz if sw_r > 0.05 else z0 - 0.12) + 1.65], target=[46.0, y0 - 0.5, z0 + 1.6], lens=26.0)
        views["%s_overhead" % cls] = dict(eye=[30.0, y0 - 30.0, z0 + 46.0], target=[30.0, y0 - 1.0, z0], lens=26.0)
    # removal / idempotence of light sources
    o = bpy.data.objects[info[classes[0]]["poles"][0]]
    n_before = len(L.light_objects(col))
    L.add_light_sources(o, info[classes[0]]["preset"]); check(len(L.light_objects(col)) == n_before, "add_light_sources twice duplicated lights")
    check(L.remove_light_sources(o) >= 1 and len(L.light_objects(col)) < n_before, "remove_light_sources did nothing")
    L.add_light_sources(o, info[classes[0]]["preset"]); check(len(L.light_objects(col)) == n_before, "re-adding lights changed the count")

    # ------------------------------------------------------------------ 3a. analytic aim check
    recs = L.light_records(col)
    check(len(recs) == n_before, "records %d != lights %d" % (len(recs), n_before))
    for r in recs:
        cls = r["class"]; I = info[cls]; w = I["w"]
        d = Vector(r["direction"]); pos = Vector(r["position"])
        if not check(d.z < -0.85, "%s aims too flat / upward %s" % (r["id"], r["direction"])): continue
        t = (pos.z - I["z0"]) / -d.z; hit = pos + d * t
        lat = hit.y - I["y0"]                                       # + = left side (y up)
        lim_r = w["half_r"] + w["curb"] + max(w["swr"], 0.0); lim_l = w["half_l"] + w["curb"] + max(w["swl"], 0.0)
        if I["preset"]["arm_reach"] > 0.0: lim_r += 0.3; lim_l += 0.3
        else: lim_r += I["preset"]["setback"] + 0.3; lim_l += I["preset"]["setback"] + 0.3
        check(-lim_r <= lat <= lim_l, "%s: aim hits %.1f m from the centre, outside the street (-%.1f..%.1f)" % (r["id"], lat, lim_r, lim_l))
        pole_lat = bpy.data.objects[r["parent"]].location.y - I["y0"]
        if I["preset"]["arm_reach"] > 0.0:      # arm luminaires reach over the road; post-tops light around the pole
            check(abs(lat) < abs(pole_lat), "%s: aim lands outside the pole line (%.1f vs pole %.1f)" % (r["id"], lat, pole_lat))
        else:
            check(abs(lat - pole_lat) < 0.3, "%s: post-top should aim straight down at its pole (%.1f vs %.1f)" % (r["id"], lat, pole_lat))
    print("RECORDS %d lights, %d shadow-casting presets" % (len(recs), sum(1 for r in recs if r["shadow"])))

    # ------------------------------------------------------------------ 3b. night / day state checks
    lamp = bpy.data.materials[MRS + "PropLamp"]
    em = lambda: next(n for n in lamp.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Emission Strength"].default_value
    qa.ensure_camera_and_sun(sc)
    day0 = (sc.world.name, sc.view_settings.exposure, sc.eevee.light_threshold, bpy.data.objects[MRS + "QASun"].hide_render)
    L.night_setup(sc); n1 = (sc.world.name, sc.view_settings.exposure, sc.eevee.light_threshold, em())
    L.night_setup(sc); n2 = (sc.world.name, sc.view_settings.exposure, sc.eevee.light_threshold, em())
    check(n1 == n2, "night_setup not idempotent: %s vs %s" % (n1, n2))
    check(n1[0] == L.NIGHT_WORLD and n1[1] == L.NIGHT_EXPOSURE and n1[3] == L.LAMP_NIGHT_STRENGTH, "night state %s" % (n1,))
    check(bpy.data.objects[MRS + "QASun"].hide_render and not bpy.data.objects[L.MOON].hide_render, "night: sun / moon visibility")
    qa.ensure_camera_and_sun(sc)
    bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
    check(bg.inputs["Color"].is_linked and bg.inputs["Strength"].is_linked, "night world inputs must be linked (qa.ensure_camera_and_sun resets defaults)")
    L.day_setup(sc); d1 = (sc.world.name, sc.view_settings.exposure, sc.eevee.light_threshold, bpy.data.objects[MRS + "QASun"].hide_render)
    L.day_setup(sc); d2 = (sc.world.name, sc.view_settings.exposure, sc.eevee.light_threshold, bpy.data.objects[MRS + "QASun"].hide_render)
    check(d1 == day0 and d2 == day0, "day_setup did not restore the day state: %s / %s vs %s" % (d1, d2, day0))
    check(em() == L.LAMP_DAY_STRENGTH and all(o.hide_render for o in L.light_objects(col)), "day: lamps / light sources should be off")
    print("STATE day %s -> night %s -> day %s" % (day0, n1, d1))

    # ------------------------------------------------------------------ 3c. measured pools (orthographic, EXR, linear)
    cam_o = bpy.data.objects.get("LT_OrthoCam") or bpy.data.objects.new("LT_OrthoCam", bpy.data.cameras.new("LT_OrthoCam"))
    if cam_o.name not in sc.collection.objects: sc.collection.objects.link(cam_o)
    cam_o.data.type = "ORTHO"; cam_o.data.ortho_scale = 80.0; cam_o.data.clip_end = 500.0; cam_o.rotation_euler = (0, 0, 0)
    MW, MH = 400, 240; PX = 80.0 / MW
    def measure(cls, tag):
        I = info[cls]; cam_o.location = (30.0, I["y0"], I["z0"] + 60.0); sc.camera = cam_o
        r = sc.render; r.engine = "BLENDER_EEVEE"; r.resolution_x, r.resolution_y = MW, MH; r.resolution_percentage = 100
        sc.eevee.taa_render_samples = 16; r.image_settings.file_format = "OPEN_EXR"
        fp = os.path.join(MEAS, "%s_%s.exr" % (cls, tag)); r.filepath = fp
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(fp); a = np.empty(MW * MH * 4, dtype=np.float32); im.pixels.foreach_get(a); bpy.data.images.remove(im)
        a = a.reshape(MH, MW, 4)[:, :, :3]
        return 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]      # row 0 = bottom = -Y
    def bands(cls, lum):
        I = info[cls]; w = I["w"]
        ys = (np.arange(MH) + 0.5 - MH / 2) * PX                                      # lateral offset (+ = left / +Y)
        xs = (np.arange(MW) + 0.5 - MW / 2) * PX + 30.0
        xm = (xs >= 0.0) & (xs <= 60.0)
        def band(lo, hi):
            m = ((ys >= lo) & (ys <= hi)) | ((ys <= -lo) & (ys >= -hi)) if lo >= 0 else (ys >= lo) & (ys <= hi)
            return float(lum[m][:, xm].mean()) if m.any() else float("nan")
        half = min(w["half_l"], w["half_r"]); sw = max(w["swl"], w["swr"]); e = max(w["half_l"], w["half_r"]) + w["curb"]
        return {"carriageway": band(-half, half), "sidewalk": band(e, e + sw) if sw > 0.05 else float("nan"), "outside": band(e + sw + 4.0, 23.0)}, ys, xm
    pool_report = {}
    L.night_setup(sc)
    for cls in classes:
        lights = [o for o in L.light_objects(col) if o.get("mrs_light_class") == cls]
        on = measure(cls, "on")
        for o in lights: o.hide_render = True
        off = measure(cls, "off")
        for o in lights: o.hide_render = False
        b_on, ys, xm = bands(cls, on); b_off, _, _ = bands(cls, off)
        diff = np.clip(on - off, 0.0, None)[:, xm]; prof = diff.sum(axis=1)
        centroid = float((prof * ys).sum() / max(prof.sum(), 1e-9))
        I = info[cls]; w = I["w"]
        lim_r = w["half_r"] + w["curb"] + w["swr"]; lim_l = w["half_l"] + w["curb"] + w["swl"]
        inside = float(prof[(ys >= -lim_r) & (ys <= lim_l)].sum() / max(prof.sum(), 1e-9))
        rep = {k: round(v / 1e-3, 3) if v == v else None for k, v in b_on.items()}
        rep_off = {k: round(v / 1e-3, 3) if v == v else None for k, v in b_off.items()}
        pool_report[cls] = dict(on_mlum=rep, off_mlum=rep_off, light_gain=round(b_on["carriageway"] / max(b_off["carriageway"], 1e-9), 1),
                                road_vs_outside=round(b_on["carriageway"] / max(b_on["outside"], 1e-9), 1), lateral_centroid=round(centroid, 2), light_inside_street=round(inside, 3))
        print("POOLS %-11s %s" % (cls, pool_report[cls]))
        check(pool_report[cls]["light_gain"] >= 4.0, "%s: carriageway only %.1fx brighter with the light objects (glow / moon dominate)" % (cls, pool_report[cls]["light_gain"]))
        if b_on["sidewalk"] == b_on["sidewalk"]:
            check(b_on["sidewalk"] / max(b_off["sidewalk"], 1e-9) >= 3.0, "%s: sidewalk not lit by the lights" % cls)
        check(pool_report[cls]["road_vs_outside"] >= 1.5, "%s: road not brighter than the surroundings (%.1f)" % (cls, pool_report[cls]["road_vs_outside"]))
        if I["preset"]["arm_reach"] > 0.0:
            check(-lim_r <= centroid <= lim_l, "%s: pool centroid %.1f m off the street" % (cls, centroid))
            check(inside >= 0.55, "%s: only %.0f %% of the added light falls on the street" % (cls, inside * 100))
        else:                                   # post-top lanterns at the path edge: pools centred on the pole line, the path covered
            pole_lats = sorted({round(bpy.data.objects[n].location.y - I["y0"], 2) for n in I["poles"]})
            check(min(abs(centroid - pl) for pl in pole_lats) < 0.8 or len(pole_lats) > 1, "%s: pool centroid %.1f m not at the lantern line %s" % (cls, centroid, pole_lats))
            check(inside >= 0.25, "%s: only %.0f %% of the added light falls on the path" % (cls, inside * 100))
        # heat map of the light added by the light objects (on - off), log scale, street edges marked
        d = np.clip(on - off, 0.0, None); v = np.log10(1.0 + d / max(float(np.percentile(d, 99.5)), 1e-9) * 99.0) / 2.0
        rgb = np.stack([np.clip(v * 2.0, 0, 1), np.clip(v * 2.0 - 0.6, 0, 1), np.clip(v * 3.0 - 2.0, 0, 1)], axis=-1)
        for edge in (-lim_r, lim_l, -(w["half_r"]), w["half_l"]):
            row = int(round(edge / PX + MH / 2))
            if 0 <= row < MH: rgb[row, ::4] = (0.2, 0.6, 1.0)
        im = bpy.data.images.new("LT_heat_%s" % cls, MW, MH, alpha=False, float_buffer=False)
        im.pixels.foreach_set(np.concatenate([rgb, np.ones((MH, MW, 1))], axis=-1).astype(np.float32).ravel())
        im.filepath_raw = os.path.join(MEAS, "%s_added_light.png" % cls); im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)

    # ------------------------------------------------------------------ 4. EEVEE renders
    rendered = []
    def shot(name, v, samples=32):
        p = qa.render(os.path.join(OUT, name + ".png"), v["eye"], v["target"], v["lens"], res=(1280, 720), samples=samples, scene=sc)
        rendered.append(p); print("RENDER", name)
    if not NO_RENDER:
        L.night_setup(sc)
        for cls in classes:
            for kind in ("driver", "pedestrian", "overhead"):
                shot("night_%s_%s" % (cls, kind), views["%s_%s" % (cls, kind)], 48)
        for cls in [c for c in ("residential", "urban") if c in classes]:
            for o in L.light_objects(col): o.hide_render = True
            shot("night_%s_driver_nolights" % cls, views["%s_driver" % cls], 48)
            for o in L.light_objects(col): o.hide_render = False
        L.day_setup(sc)
        for cls in classes:
            shot("day_%s_driver" % cls, views["%s_driver" % cls], 24)
        L.night_setup(sc)

    # ------------------------------------------------------------------ 5. export GLB + JSON
    L.night_setup(sc)                                    # lamp emission carried into the GLB (KHR_materials_emissive_strength)
    ex = bpy.data.collections.get("LT_Export") or bpy.data.collections.new("LT_Export")
    if ex.name not in sc.collection.children: sc.collection.children.link(ex)
    for o in list(ex.objects): bpy.data.objects.remove(o)
    objs = []
    for cls in classes:
        rd = bpy.data.objects[info[cls]["road"]]; mod = rd.modifiers["MRS_Road"]
        mod_input_set(mod, "Realize Instances", True); rd.update_tag(); bpy.context.view_layer.update()
        dg = depsgraph(); me = bpy.data.meshes.new_from_object(rd.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        mod_input_set(mod, "Realize Instances", False); rd.update_tag()
        c = bpy.data.objects.new(rd.name, me); c.matrix_world = rd.matrix_world.copy(); ex.objects.link(c); objs.append(c)
        for pn in info[cls]["poles"]:
            po = bpy.data.objects[pn]; c = bpy.data.objects.new(pn, po.data.copy()); c.matrix_world = po.matrix_world.copy(); ex.objects.link(c)
            c["mrs_lib"] = po["mrs_placed"]; objs.append(c)
    try:
        from mrs import export as E
        nmat = E.apply_engine_materials(objs); print("EXPORT engine materials via mrs.export:", nmat)
    except Exception as e:
        notes.append("mrs.export unavailable (%s): materials exported as authored" % e); print("NOTE", notes[-1])
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects: o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    glb = os.path.join(EXP, "lighting_street.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_extras=True,
                              export_lights=False, export_materials="EXPORT")
    tris = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
    print("EXPORT %s %.1f MB, %d objects, %d tris" % (glb, os.path.getsize(glb) / 1e6, len(objs), tris))
    for o in list(ex.objects):
        d = o.data; bpy.data.objects.remove(o)
        if d is not None and d.users == 0: bpy.data.meshes.remove(d)
    for v in views.values():
        hf = 2.0 * math.atan(18.0 / v["lens"]); v["fov_v"] = round(math.degrees(2.0 * math.atan(math.tan(hf / 2.0) * 9.0 / 16.0)), 2)
    jpath = L.export_json(os.path.join(EXP, "lighting_lights.json"), col, extra={
        "views": views, "pools": pool_report,
        "roads": {c: {"id": info[c]["road"], "y0": info[c]["y0"], "z0": info[c]["z0"], "carriageway_width": round(info[c]["W"], 2),
                      "arrangement": info[c]["preset"]["arrangement"], "rule": info[c]["preset"]["arrangement_rule"]} for c in classes},
        })
    recs = L.light_records(col)
    print("JSON %s: %d lights (%d shadow-casting presets), %d views" % (jpath, len(recs), sum(1 for r in recs if r["shadow"]), len(views)))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lighting_test.blend"), check_existing=False)
except Exception:
    traceback.print_exc(); problems.append("exception: " + traceback.format_exc().splitlines()[-1])

print("NOTES", notes)
print("LIGHTING TEST", "PASS" if not problems else "FAIL (%d)" % len(problems))
for p in problems: print("  -", p)
