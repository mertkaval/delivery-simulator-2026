"""Street lighting for Mert Road Studio (Blender 5.2): road-class presets, fixture anchors, real light
sources on placed streetlights, light records for the game JSON and reversible night / day setups.

    import mrs.lighting as L
    p = L.preset_for("urban", carriageway_width=21.0)      # copy of a preset, arrangement chosen by width / height
    for along, side in L.layout(road_length, p): ...         # pole stations ('l' / 'r'); the placement engine places poles
    lamps = L.add_light_sources(pole, p)                     # SPOT objects <pole>_Lamp<i>, parented to the pole
    L.night_setup(scene); ...; L.day_setup(scene)            # idempotent, reversible
    recs = L.light_records(collection)                       # game JSON records (Blender Z-up coordinates)

Units and reasoning (see docs/roads/LIGHTING.md; no claim of standards compliance)
- Blender light power is radiometric-looking "W". This module treats Blender irradiance (W/m^2) x 683 as
  lux (the photopic 555 nm efficacy) so luminaire intensities in candela convert to spot power as
  P = 4*pi*I / 683 (a Blender spot of P W has the axial intensity of a point light of P W: P / 4pi W/sr,
  measured: EEVEE and Cycles both follow E = P / (4*pi*d^2) on the axis, white Lambert = E / pi).
- Real road luminaires have asymmetric optics (light thrown across and along the road, little behind the pole);
  a spot is symmetric, so the preset tilt (10-15 deg toward the road) stands in for the street-side throw.
- Intensities are chosen from typical luminaire outputs and give nadir illuminances of roughly 15-45 lux,
  i.e. the order of magnitude of lit streets; uniformity is that of a plain spot cone (no IES / batwing).
- The night camera exposure NIGHT_EXPOSURE (+7 EV) maps ~20 lux on asphalt to mid grey, as an eye or a
  camera adapted to street lighting would; the moon / sky are lifted above a real full moon so the
  space between pools stays readable (documented artistic choice).
- Godot: SpotLight3D with spot_attenuation 2.0 is inverse square; Lambert white at distance d receives
  energy / d^2 (Godot folds pi into the light). Matching the Blender night render at tonemap exposure 1
  gives energy = P * 2^EV / (4*pi^2) (GODOT_ENERGY_PER_W).
"""
import json, math, copy
import bpy
from mathutils import Vector, Quaternion, Matrix

MRS = "MRS_"
LM_PER_W = 683.0
NIGHT_EXPOSURE = 7.0                     # EV added by night_setup (scene view_settings.exposure)
GODOT_CALIBRATION = 1.0                  # measured correction Godot / Blender (tests/capture_lighting.gd)
GODOT_ENERGY_PER_W = 2.0 ** NIGHT_EXPOSURE / (4.0 * math.pi ** 2) * GODOT_CALIBRATION
MOON_STRENGTH = 0.004                    # W/m^2 ~ 2.7 lux: full moon (~0.25 lux) + urban sky glow, lifted for readability
SKY_STRENGTH = 0.0005                    # night sky radiance scale: x 2^7 gives a navy zenith ~0.006-0.02 and a dim warm horizon
LAMP_NIGHT_STRENGTH = 40.0               # emission strength of MRS_PropLamp* / MRS_Lamp* at night (luminaire luminance ~ 27,000 cd/m^2)
LAMP_DAY_STRENGTH = 0.0                  # streetlights are switched off by day
LAMP_MATERIAL_PREFIXES = (MRS + "PropLamp", MRS + "Lamp")
STATE_KEY = "mrs_lighting_state"
NIGHT_SKY_HORIZON = (0.41, 0.30, 0.27)    # x SKY_STRENGTH: warm urban glow at the horizon
NIGHT_SKY_ZENITH = (0.09, 0.14, 0.31)     # x SKY_STRENGTH: deep blue overhead
MOON_COLOR = (0.62, 0.72, 1.0)            # linear; moonlight reads blue to a dark-adapted eye
MOON_ROTATION = (55.0, 0.0, 130.0)        # degrees (XYZ euler of the sun lamp)
MOON = MRS + "Moon"
NIGHT_WORLD = MRS + "NightWorld"
DAY_WORLD = MRS + "World"
ARRANGEMENTS = ("single_left", "single_right", "opposite", "staggered")


# ============================================================================== colour
def _cie_xyz(lam):
    """CIE 1931 2-degree colour matching functions, multi-lobe Gaussian fit (Wyman, Sloan, Shirley 2013); lam in nm."""
    g = lambda x, mu, s1, s2: math.exp(-0.5 * ((x - mu) * (s1 if x < mu else s2)) ** 2)
    x = 0.362 * g(lam, 442.0, 0.0624, 0.0374) + 1.056 * g(lam, 599.8, 0.0264, 0.0323) - 0.065 * g(lam, 501.1, 0.0490, 0.0382)
    y = 0.821 * g(lam, 568.8, 0.0213, 0.0247) + 0.286 * g(lam, 530.9, 0.0613, 0.0322)
    z = 1.217 * g(lam, 437.0, 0.0845, 0.0278) + 0.681 * g(lam, 459.0, 0.0385, 0.0725)
    return x, y, z


def kelvin_to_linear(kelvin):
    """Black-body colour as linear Rec.709 / sRGB primaries, normalised to luminance 1 (as Blender's
    Light.temperature_color), so the light's power is unchanged by its colour."""
    X = Y = Z = 0.0
    for lam in range(380, 781, 5):
        l = lam * 1e-9
        b = 1.0 / (l ** 5 * (math.exp(1.4388e-2 / (l * kelvin)) - 1.0))
        x, y, z = _cie_xyz(lam); X += b * x; Y += b * y; Z += b * z
    X, Z = X / Y, Z / Y; Y = 1.0
    r = 3.2406 * X - 1.5372 * Y - 0.4986 * Z
    g = -0.9689 * X + 1.8758 * Y + 0.0415 * Z
    b = 0.0557 * X - 0.2040 * Y + 1.0570 * Z
    r, g, b = max(r, 0.0), max(g, 0.0), max(b, 0.0)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (r / lum, g / lum, b / lum)


def linear_to_srgb(c):
    """Linear colour -> sRGB-encoded colour with its maximum at 1 (Godot light_color is sRGB-encoded). Returns
    (srgb, scale) where scale = max(linear) is folded into the Godot energy."""
    m = max(c) or 1.0
    enc = lambda v: 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return tuple(round(enc(v / m), 4) for v in c), m


def power_from_candela(cd):
    """Blender spot / point power (W) for an axial luminous intensity in candela (683 lm/W convention)."""
    return 4.0 * math.pi * cd / LM_PER_W


def fit_godot_cone(blend):
    """Godot's spot cone falloff is 1 - rim^n with rim = (1 - cos a) / (1 - cos cutoff); Blender's (EEVEE and
    Cycles, measured) is smoothstep((cos a - cos cutoff) / ((1 - cos cutoff) * blend)). Both depend only on
    u = (cos a - cos cutoff) / (1 - cos cutoff), so the best exponent n depends on the blend alone."""
    if blend <= 0.02: return 40.0
    best = (1e9, 1.0)
    for k in range(4, 600):
        n = k * 0.05; err = 0.0
        for i in range(1, 101):
            u = i / 100.0; x = min(1.0, u / blend); f = x * x * (3.0 - 2.0 * x)
            err += (f - (1.0 - (1.0 - u) ** n)) ** 2
        if err < best[0]: best = (err, n)
    return round(best[1], 2)


# ============================================================================== presets
def _preset(cls, library, height, reach, setback, spacing, arrangement, tilt, cd, size, blend, kelvin, radius, rng, shadow,
            fade_begin, fade_length, why, kind="SPOT", area=(0.6, 0.2)):
    lin = kelvin_to_linear(kelvin); srgb, scale = linear_to_srgb(lin)
    p_w = power_from_candela(cd)
    return {
        "class": cls, "library": library, "mounting_height": height, "arm_reach": reach, "setback": setback, "spacing": spacing,
        "arrangement": arrangement, "tilt": tilt,
        "light": {"type": kind, "intensity_cd": cd, "power_w": round(p_w, 2), "spot_size": size, "spot_blend": blend, "radius": radius,
                  "area_size": list(area), "temperature": kelvin, "color": [round(v, 4) for v in lin], "shadow": shadow, "range": rng},
        "godot": {"type": "spot", "energy": round(p_w * GODOT_ENERGY_PER_W * scale, 2), "color": list(srgb), "range": rng, "attenuation": 2.0,
                  "spot_angle": size * 0.5, "spot_angle_attenuation": fit_godot_cone(blend), "shadow": shadow,
                  "fade_begin": fade_begin, "fade_length": fade_length, "shadow_fade": round(fade_begin * 0.5, 1)},
        "target": {"nadir_lux": round(cd / height ** 2, 1), "spacing_to_height": round(spacing / height, 2)},
        "reasoning": why,
    }


PRESETS = {
    "residential": _preset(
        "residential", "MRS_Light_LED", 6.97, 0.9, 0.5, 30.0, "single_right", 15.0, 1000.0, 140.0, 0.40, 3000, 0.12, 25.0, True, 60.0, 20.0,
        "7 m LED column, short arm; one side while the carriageway is no wider than the mounting height. 1000 cd "
        "(a ~4,000 lm LED luminaire) gives ~20 lux under the lamp and a few lux mid-span at 30 m (~4.3 H). Warm 3000 K "
        "is common in residential streets. 140 deg cone so the pool reaches mid-span."),
    "urban": _preset(
        "urban", "MRS_Light_Highway", 9.82, 2.4, 0.6, 32.0, "opposite", 10.0, 3200.0, 150.0, 0.45, 4000, 0.10, 35.0, True, 80.0, 25.0,
        "Avenue: 10 m columns with a 2.4 m arm, opposite pairs on wide carriageways. 3200 cd (~12,000 lm) gives ~33 lux "
        "under each lamp, spacing 32 m (~3.3 H). Neutral 4000 K for colour rendering in commercial streets."),
    "highway": _preset(
        "highway", "MRS_Light_Highway", 9.82, 2.4, 2.0, 40.0, "single_right", 15.0, 4500.0, 150.0, 0.45, 4000, 0.10, 40.0, True, 120.0, 30.0,
        "Highway: 10 m columns 2 m behind the edge (barrier zone), 15 deg uptilt to throw light across the lanes. "
        "4500 cd (~18,000 lm) gives ~47 lux at nadir, spacing 40 m (~4 H). Longer fade distances: lights are seen far ahead."),
    "path": _preset(
        "path", "MRS_Light_Lantern", 3.66, 0.0, 0.4, 18.0, "single_right", 0.0, 260.0, 170.0, 0.60, 2700, 0.09, 15.0, False, 45.0, 15.0,
        "Sidewalk / park / footbridge: 4.45 m post-top lantern, lamp at 3.7 m, 18 m spacing (~4.9 H). 260 cd (~1,500 lm) "
        "gives ~19 lux below the lantern; 2700 K warm. The light sits inside the glazed housing, so it casts no shadows "
        "(the housing would self-shadow; cheaper too). 170 deg cone also lights faces and facades."),
    "bridge": _preset(
        "bridge", "MRS_Light_LED", 6.97, 0.9, 0.9, 24.0, "staggered", 15.0, 1400.0, 140.0, 0.40, 4000, 0.12, 25.0, True, 70.0, 20.0,
        "Road bridge: lower 7 m LED columns just in front of the parapet (0.9 m behind the kerb on a 1.8 m sidewalk whose "
        "outer 0.55 m is the parapet), staggered "
        "every 24 m (~3.4 H) so both sidewalks and the deck are covered. 1400 cd gives ~29 lux at nadir."),
    # fixture presets (not road classes): small luminaires the placement may use on paths, plazas and walls
    "bollard": _preset(
        "bollard", "MRS_Light_Bollard", 0.81, 0.0, 0.3, 6.0, "single_right", 0.0, 25.0, 175.0, 0.6, 3000, 0.08, 6.0, False, 30.0, 10.0,
        "1 m bollard: ~150 lm ring at 0.8 m, 25 cd -> ~38 lux at its foot, falling to a few lux 3 m away; no shadows (light inside the body)."),
    "wallpack": _preset(
        "wallpack", "MRS_Light_WallPack", 3.22, 0.3, 0.0, 15.0, "single_right", 0.0, 500.0, 120.0, 0.4, 4000, 0.1, 15.0, True, 45.0, 15.0,
        "3.5 m wall pack (yards, underpasses, building fronts): forward-down aim (dir in the anchor), 500 cd, 120 deg."),
}
ALIASES = {"avenue": "urban", "boulevard": "urban", "arterial": "urban", "commercial": "urban", "street": "residential",
           "service": "residential", "rural": "residential", "local": "residential", "motorway": "highway", "expressway": "highway",
           "sidewalk": "path", "park": "path", "footpath": "path", "footbridge": "path", "pedestrian": "path", "cycleway": "path"}
# library object -> default preset when a placed light has no class
LIBRARY_PRESET = {"MRS_Light_LED": "residential", "MRS_Light_Highway": "urban", "MRS_Light_Double": "highway",
                  "MRS_Light_Lantern": "path", "MRS_Light_Bollard": "bollard", "MRS_Light_WallPack": "wallpack"}
ROAD_CLASSES = ("residential", "urban", "highway", "path", "bridge")


def get_preset(name_or_preset):
    if isinstance(name_or_preset, dict): return name_or_preset
    key = ALIASES.get(str(name_or_preset).lower(), str(name_or_preset).lower())
    if key not in PRESETS: raise KeyError("unknown lighting preset %r (have %s)" % (name_or_preset, ", ".join(PRESETS)))
    return PRESETS[key]


def preset_for(road_class, carriageway_width):
    """A copy of the road class's preset with the arrangement chosen from the carriageway width W (kerb to kerb,
    m) and the mounting height H: W <= H one side, W <= 1.5 H staggered, wider opposite (a common rule of thumb).
    Paths keep one side up to 1.5 H. The choice and the rule are recorded in "arrangement_rule"."""
    p = copy.deepcopy(get_preset(road_class)); H = p["mounting_height"]; W = float(carriageway_width)
    if W <= H: arr, why = "single_right", "W %.1f <= H %.1f: one side" % (W, H)
    elif W <= 1.5 * H: arr, why = "staggered", "H %.1f < W %.1f <= 1.5 H: staggered" % (H, W)
    else: arr, why = "opposite", "W %.1f > 1.5 H %.1f: opposite pairs" % (W, 1.5 * H)
    if p["class"] == "path" and W <= 1.5 * H: arr, why = "single_right", "path W %.1f <= 1.5 H: one side" % W
    if W > 3.0 * H: why += "; W > 3 H: the centre gets dark - consider median twin-arm MRS_Light_Double"
    p["arrangement"] = arr; p["arrangement_rule"] = why; p["carriageway_width"] = W
    return p


def layout(length, preset, start=None, end=None):
    """Pole stations along a road of `length` m: [(along, side)], side 'l' / 'r' (placement convention, looking
    along the curve). `spacing` is the distance between consecutive poles (between pairs for 'opposite')."""
    p = get_preset(preset); s = float(p["spacing"]); arr = p["arrangement"]
    a = s * 0.5 if start is None else float(start); b = length if end is None else float(end)
    out = []; k = 0
    while a <= b + 1e-6:
        if arr == "single_left": out.append((a, "l"))
        elif arr == "single_right": out.append((a, "r"))
        elif arr == "opposite": out += [(a, "r"), (a, "l")]
        else: out.append((a, "r" if k % 2 == 0 else "l"))
        a += s; k += 1
    return out


# ============================================================================== fixtures
def fixtures_of(obj):
    """Fixture anchors of a streetlight (library object, a placed copy sharing its mesh, or via obj['mrs_placed'])."""
    for src in (obj, getattr(obj, "data", None), bpy.data.objects.get(obj.get("mrs_placed", "") or "")):
        if src is None: continue
        v = src.get("mrs_fixtures")
        if v: return json.loads(v) if isinstance(v, str) else list(v)
    return []


def _aim(fx, tilt_deg):
    """Fixture aim tilted by `tilt_deg` toward the arm (the horizontal direction from the pole to the head; +Y,
    the road side, for heads on the pole axis)."""
    d = Vector(fx["dir"]).normalized(); p = Vector(fx["pos"])
    arm = Vector((p.x, p.y, 0.0))
    arm = arm.normalized() if arm.length > 0.05 else Vector((0.0, 1.0, 0.0))
    axis = d.cross(arm)
    if axis.length < 1e-6 or abs(tilt_deg) < 1e-6: return d
    return (Quaternion(axis.normalized(), math.radians(tilt_deg)) @ d).normalized()


# ============================================================================== light sources
def add_light_sources(obj, preset, name_prefix=None):
    """Real light sources for a placed streetlight: one light object per fixture anchor, parented to `obj`, named
    `<prefix>_Lamp<i>` (prefix defaults to obj.name), aimed along the anchor's dir tilted by the preset's tilt.
    Custom props: mrs_light = 1, mrs_light_class and the Godot parameters (mrs_godot_*). Re-running replaces the
    previous lights. The emissive lamp mesh is untouched (decorative only). Returns the light objects."""
    p = get_preset(preset); L = p["light"]; G = p["godot"]
    remove_light_sources(obj)
    fx = fixtures_of(obj)
    if not fx: raise ValueError("%s has no fixture anchors (mrs_fixtures); rebuild the streetlights with mrs.assets.build_assets()" % obj.name)
    prefix = name_prefix or obj.name
    cols = list(obj.users_collection) or [bpy.context.scene.collection]
    out = []
    for i, f in enumerate(fx):
        name = "%s_Lamp%d" % (prefix, i)
        kind = L.get("type", "SPOT")
        ld = bpy.data.lights.new(name, kind)
        ld.energy = L["power_w"]; ld.color = (1.0, 1.0, 1.0)
        ld.use_temperature = True; ld.temperature = L["temperature"]
        ld.use_shadow = bool(L["shadow"])
        ld.use_custom_distance = True; ld.cutoff_distance = L["range"]      # EEVEE influence = Godot range (else light_threshold cuts weak lights)
        ld.use_shadow_jitter = True                                          # soft shadows from the head size (EEVEE)
        if kind == "SPOT":
            ld.spot_size = math.radians(L["spot_size"]); ld.spot_blend = L["spot_blend"]; ld.shadow_soft_size = L["radius"]
        elif kind == "AREA":
            ld.shape = "RECTANGLE"; ld.size, ld.size_y = L["area_size"]
        else:
            ld.shadow_soft_size = L["radius"]
        lo = bpy.data.objects.new(name, ld)
        for c in cols: c.objects.link(lo)
        lo.parent = obj; lo.matrix_parent_inverse = Matrix.Identity(4)
        aim = _aim(f, p["tilt"])
        lo.location = Vector(f["pos"])
        lo.rotation_mode = "QUATERNION"; lo.rotation_quaternion = aim.to_track_quat("-Z", "Y")
        lo.hide_render = obj.hide_render or _state(bpy.context.scene).get("mode") == "day"     # off when created by day
        lo["mrs_light"] = 1; lo["mrs_light_class"] = p["class"]; lo["mrs_light_index"] = i
        lo["mrs_light_type"] = "spot" if kind != "POINT" else "omni"
        lo["mrs_power_w"] = L["power_w"]; lo["mrs_temperature"] = L["temperature"]
        # an AREA light is a Lambertian emitter: axial intensity P / pi (a spot: P / 4 pi) and a cosine lobe (Godot cone exponent 1 at 90 deg)
        lo["mrs_godot_energy"] = G["energy"] * (4.0 if kind == "AREA" else 1.0); lo["mrs_godot_color"] = list(G["color"]); lo["mrs_godot_range"] = G["range"]
        lo["mrs_godot_attenuation"] = G["attenuation"]; lo["mrs_godot_spot_angle"] = G["spot_angle"] if kind != "AREA" else 90.0
        lo["mrs_godot_spot_angle_attenuation"] = G["spot_angle_attenuation"] if kind != "AREA" else 1.0; lo["mrs_godot_shadow"] = bool(G["shadow"])
        lo["mrs_godot_fade_begin"] = G["fade_begin"]; lo["mrs_godot_fade_length"] = G["fade_length"]; lo["mrs_godot_shadow_fade"] = G["shadow_fade"]
        out.append(lo)
    obj["mrs_light_class"] = p["class"]
    return out


def remove_light_sources(obj):
    """Delete the light objects (and their unused light data) parented to `obj`. Returns the number removed."""
    n = 0
    for ch in list(obj.children):
        if ch.get("mrs_light") and ch.type == "LIGHT":
            d = ch.data; bpy.data.objects.remove(ch); n += 1
            if d is not None and d.users == 0: bpy.data.lights.remove(d)
    return n


def add_lights_for_collection(collection, preset=None):
    """Light sources for every placed streetlight in `collection` (objects with mrs_placed = MRS_Light_*). The
    preset is `preset`, else the object's mrs_light_class / mrs_road_class, else LIBRARY_PRESET[library]."""
    out = []
    for o in list(collection.all_objects):
        lib = o.get("mrs_placed", "") or ""
        if o.type != "MESH" or not lib.startswith(MRS + "Light_"): continue
        pr = preset or o.get("mrs_light_class") or o.get("mrs_road_class") or LIBRARY_PRESET.get(lib, "residential")
        out += add_light_sources(o, pr)
    return out


def light_objects(collection=None):
    objs = collection.all_objects if collection is not None else bpy.data.objects
    return [o for o in objs if o.type == "LIGHT" and o.get("mrs_light")]


def _world_matrix(o):
    """World matrix from the parent chain (valid before the depsgraph has evaluated newly created objects)."""
    m = o.matrix_basis.copy()
    while o.parent is not None:
        m = o.parent.matrix_basis @ o.matrix_parent_inverse @ m; o = o.parent
    return m


def light_records(collection=None):
    """Game records for every mrs_light in `collection` (all objects when None). Coordinates stay in Blender
    Z-up like the rest of the street model; Godot (Y-up) = (x, z, -y), stated in each record's `axes`.
    Fields: id, parent, library, class, type (spot|omni), position, direction (unit, the aim), color (sRGB, max 1,
    Godot light_color), color_linear, temperature, energy (Godot light_energy), power_w (Blender), range,
    attenuation, spot_angle (half angle, deg), spot_angle_attenuation, shadow, fade_begin, fade_length, shadow_fade."""
    recs = []
    for o in sorted(light_objects(collection), key=lambda x: x.name):
        mw = _world_matrix(o); pos = mw.translation; d = (mw.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
        par = o.parent; ld = o.data
        # lights not made by add_light_sources (e.g. other generators tagging mrs_light) are derived from the light data
        kelvin = o.get("mrs_temperature") or (ld.temperature if getattr(ld, "use_temperature", False) else None)
        lin = kelvin_to_linear(kelvin) if kelvin else tuple(ld.color)
        srgb, scale = linear_to_srgb(lin)
        typ = o.get("mrs_light_type") or ("omni" if ld.type == "POINT" else "spot")
        energy = o.get("mrs_godot_energy")
        if energy is None: energy = ld.energy * GODOT_ENERGY_PER_W * scale * (4.0 if ld.type == "AREA" else 1.0)
        rng = o.get("mrs_godot_range") or (ld.cutoff_distance if getattr(ld, "use_custom_distance", False) else 20.0)
        angle = o.get("mrs_godot_spot_angle") or (math.degrees(ld.spot_size) * 0.5 if ld.type == "SPOT" else 90.0)
        cone = o.get("mrs_godot_spot_angle_attenuation") or (fit_godot_cone(ld.spot_blend) if ld.type == "SPOT" else 1.0)
        recs.append({
            "id": o.name, "parent": par.name if par else "", "library": (par.get("mrs_placed", par.name) if par else ""),
            "class": o.get("mrs_light_class", ""), "type": typ,
            "axes": "z_up (godot: x, z, -y)",
            "position": [round(v, 3) for v in pos], "direction": [round(v, 4) for v in d],
            "color": list(o.get("mrs_godot_color", srgb)), "color_linear": [round(v, 4) for v in lin],
            "temperature": kelvin, "energy": round(float(energy), 3),
            "power_w": round(float(ld.energy), 3), "range": float(rng),
            "attenuation": float(o.get("mrs_godot_attenuation", 2.0)), "spot_angle": float(angle),
            "spot_angle_attenuation": float(cone), "shadow": bool(o.get("mrs_godot_shadow", False)),
            "fade_begin": float(o.get("mrs_godot_fade_begin", 60.0)), "fade_length": float(o.get("mrs_godot_fade_length", 20.0)),
            "shadow_fade": float(o.get("mrs_godot_shadow_fade", 30.0)),
        })
    return recs


def lights_model(collection=None):
    """The `lights` block for the street-model JSON (records + conventions)."""
    from mathutils import Euler
    moon_dir = (Euler(tuple(math.radians(a) for a in MOON_ROTATION)).to_matrix() @ Vector((0.0, 0.0, -1.0))).normalized()
    k = 2.0 ** NIGHT_EXPOSURE
    return {"version": 1, "units": "m", "axes": "Blender Z-up; Godot = (x, z, -y)",
            "godot_energy_per_w": round(GODOT_ENERGY_PER_W, 4), "night_exposure_ev": NIGHT_EXPOSURE,
            "night": {"exposure_ev": NIGHT_EXPOSURE, "lamp_emission": LAMP_NIGHT_STRENGTH,
                      "moon": {"strength_w_m2": MOON_STRENGTH, "color_linear": list(MOON_COLOR), "direction": [round(v, 4) for v in moon_dir],
                               "godot_energy": round(MOON_STRENGTH * k / math.pi, 4)},
                      "sky": {"strength": SKY_STRENGTH, "horizon_linear": list(NIGHT_SKY_HORIZON), "zenith_linear": list(NIGHT_SKY_ZENITH),
                              "godot_horizon_linear": [round(c * SKY_STRENGTH * k, 5) for c in NIGHT_SKY_HORIZON],
                              "godot_zenith_linear": [round(c * SKY_STRENGTH * k, 5) for c in NIGHT_SKY_ZENITH]}},
            "presets": {k: {"library": v["library"], "arrangement": v["arrangement"], "spacing": v["spacing"]} for k, v in PRESETS.items()},
            "lights": light_records(collection)}


def export_json(path, collection=None, extra=None):
    m = lights_model(collection)
    if extra: m.update(extra)
    with open(path, "w", encoding="utf-8") as f: json.dump(m, f, indent=1)
    return path


# ============================================================================== night / day
def _lamp_materials():
    return [m for m in bpy.data.materials if m.name.startswith(LAMP_MATERIAL_PREFIXES)]


def _window_glow(night):
    """City-kit glazing (frontage.py KitGlass): a warm lit interior at night, as the game's window shader does."""
    m = bpy.data.materials.get("KitGlass")
    if m is None or not m.use_nodes: return
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    # night_setup adds NIGHT_EXPOSURE (+7 EV, x128): 0.006 reads as a warm lit interior (~0.8) instead of white panes
    if b is not None: b.inputs["Emission Strength"].default_value = 0.006 if night else 0.02


def set_lamp_strength(strength):
    """Emission strength of every lamp material (Principled 'Emission Strength' or Emission node 'Strength')."""
    n = 0
    for m in _lamp_materials():
        if not m.use_nodes or m.node_tree is None: continue
        for nd in m.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED" and not nd.inputs["Emission Strength"].is_linked:
                nd.inputs["Emission Strength"].default_value = strength; n += 1
            elif nd.type == "EMISSION" and not nd.inputs["Strength"].is_linked:
                nd.inputs["Strength"].default_value = strength; n += 1
    return n


def _night_world(sky_strength):
    """Dark sky: zenith deep blue, horizon with a warm urban glow. Colour / strength come from linked nodes, so
    qa.ensure_camera_and_sun (which sets the Background node's default values) cannot turn it back to day."""
    w = bpy.data.worlds.get(NIGHT_WORLD) or bpy.data.worlds.new(NIGHT_WORLD)
    w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (600, 0)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.location = (400, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-600, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-400, 0)
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-200, 0)
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*NIGHT_SKY_HORIZON, 1)
    ramp.color_ramp.elements[1].position = 0.35; ramp.color_ramp.elements[1].color = (*NIGHT_SKY_ZENITH, 1)
    val = nt.nodes.new("ShaderNodeValue"); val.name = val.label = "Night Sky Strength"; val.location = (100, -200)
    val.outputs[0].default_value = sky_strength
    nt.links.new(tc.outputs["Generated"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"]); nt.links.new(val.outputs[0], bg.inputs["Strength"])
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def _moon(scene, strength):
    o = bpy.data.objects.get(MOON)
    if o is None:
        ld = bpy.data.lights.new(MOON, "SUN"); o = bpy.data.objects.new(MOON, ld)
    if o.name not in scene.collection.objects: scene.collection.objects.link(o)
    ld = o.data
    ld.energy = strength; ld.angle = math.radians(1.5); ld.use_shadow = True
    ld.use_temperature = False; ld.color = MOON_COLOR
    o.rotation_euler = tuple(math.radians(a) for a in MOON_ROTATION)
    o["mrs_moon"] = 1
    return o


def _state(scene):
    try: return json.loads(scene.get(STATE_KEY, "{}"))
    except Exception: return {}


def _capture(scene):
    vs = scene.view_settings; ee = scene.eevee
    return {"world": scene.world.name if scene.world else "", "view_transform": vs.view_transform, "look": vs.look,
            "exposure": vs.exposure, "gamma": vs.gamma,
            "eevee": {k: getattr(ee, k) for k in ("light_threshold", "use_shadows", "shadow_ray_count", "shadow_step_count", "shadow_pool_size", "shadow_resolution_scale")},
            "suns": {o.name: o.hide_render for o in scene.objects if o.type == "LIGHT" and o.data.type == "SUN" and not o.get("mrs_moon")}}


def night_setup(scene=None, exposure=NIGHT_EXPOSURE, moon=MOON_STRENGTH, sky=SKY_STRENGTH, lamp_strength=LAMP_NIGHT_STRENGTH):
    """Night: dark sky world with horizon glow, a dim soft moon, day suns hidden, AgX view at +`exposure` EV,
    EEVEE shadows on (jittered soft shadows, larger shadow pool, low light threshold), streetlight sources on,
    lamp emission up. The day state is stored on the scene once; repeated calls only re-apply (idempotent)."""
    scene = scene or bpy.context.scene
    st = _state(scene)
    if st.get("mode") != "night":
        st = {"mode": "night", "saved": _capture(scene)}
    scene.world = _night_world(sky)
    vs = scene.view_settings; vs.view_transform = "AgX"; vs.look = "None"; vs.exposure = exposure; vs.gamma = 1.0
    ee = scene.eevee
    ee.use_shadows = True; ee.shadow_ray_count = 2; ee.shadow_step_count = 8; ee.shadow_resolution_scale = 1.0
    ee.shadow_pool_size = "1024"; ee.light_threshold = 0.001
    for name in st["saved"]["suns"]:
        o = bpy.data.objects.get(name)
        if o: o.hide_render = True
    m = _moon(scene, moon); m.hide_render = False; m.hide_viewport = False
    for o in light_objects(): o.hide_render = False
    set_lamp_strength(lamp_strength)
    _window_glow(True)
    scene[STATE_KEY] = json.dumps(st)
    return scene


def day_setup(scene=None, lamp_strength=LAMP_DAY_STRENGTH):
    """Day: restore what night_setup saved (world, view, exposure, EEVEE settings, sun visibility), hide the moon,
    switch the streetlight sources off (hide_render) and the lamp emission down. Idempotent."""
    scene = scene or bpy.context.scene
    st = _state(scene)
    sv = st.get("saved") if st.get("mode") == "night" else None
    if sv:
        w = bpy.data.worlds.get(sv["world"]) if sv["world"] else None
        scene.world = w
        vs = scene.view_settings
        try: vs.view_transform = sv["view_transform"]; vs.look = sv["look"]
        except TypeError: vs.view_transform = "AgX"; vs.look = "None"
        vs.exposure = sv["exposure"]; vs.gamma = sv["gamma"]
        for k, v in sv["eevee"].items():
            try: setattr(scene.eevee, k, v)
            except (TypeError, AttributeError): pass
        for name, hidden in sv["suns"].items():
            o = bpy.data.objects.get(name)
            if o: o.hide_render = hidden
    elif scene.world is not None and scene.world.name == NIGHT_WORLD:
        scene.world = bpy.data.worlds.get(DAY_WORLD); scene.view_settings.exposure = 0.0
    m = bpy.data.objects.get(MOON)
    if m: m.hide_render = True; m.hide_viewport = True
    _window_glow(False)
    for o in light_objects(): o.hide_render = True
    set_lamp_strength(lamp_strength)
    scene[STATE_KEY] = json.dumps({"mode": "day"})
    return scene


def is_night(scene=None):
    return _state(scene or bpy.context.scene).get("mode") == "night"
