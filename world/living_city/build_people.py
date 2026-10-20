"""Rainline citizens v2: twelve skinned, animated people with distinct bodies, faces,
hairstyles, clothing and accessories. Replaces citizen_0..5 and adds citizen_6..11.

Runtime contract (LivingCitizen / LivingAssets / tests) is unchanged:
  * one Skeleton3D, bones Hips Chest Neck Head + Thigh/Shin/Foot/UpperArm/Forearm L/R (14)
  * clips Idle Walk Brisk Wait Talk Sit Carry Cycle, looping, 32-frame cycles at 30 fps
  * citizen_N.glb, citizen_N_lod1.glb, citizen_N_lod2.glb with decreasing triangles
Geometry is authored for a 1.80 m figure and then scaled per person (height, build),
so bone positions, weights and foot planting stay consistent.

HEADLESS ONLY (uses the shared helper's clear(), which empties the scene):
  blender --background --factory-startup --python world/living_city/build_people.py [-- 0 3 7]
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
helper = open(os.path.join(HERE, '..', 'build_city_assets.py'), encoding='utf-8-sig').read().split('\ndef vehicle(')[0]
exec(compile(helper.replace("'city_assets'", "'assets'"), 'living_geometry', 'exec'), globals())

CLIPS = ['Idle', 'Walk', 'Brisk', 'Wait', 'Talk', 'Sit', 'Carry', 'Cycle']
SKIN_TONES = {'pale': (.66, .46, .36), 'light': (.60, .40, .29), 'olive': (.50, .33, .21), 'tan': (.42, .26, .16),
              'brown': (.30, .17, .10), 'deep': (.18, .10, .065)}
HAIR_COLOURS = {'black': (.018, .015, .014), 'dark': (.045, .028, .018), 'brown': (.11, .06, .03), 'auburn': (.22, .07, .03),
                'blonde': (.42, .30, .15), 'grey': (.36, .35, .34), 'silver': (.55, .55, .54)}

# Twelve people. top/bottom colours are linear RGB.
PEOPLE = [
    dict(sex='m', height=1.80, build=1.05, skin='light', hair='crop', hair_col='brown', top='hivis', top_col=(.75, .23, .03), bottom='trousers', bottom_col=(.05, .06, .07), shoes='boots', extra=[]),
    dict(sex='f', height=1.66, build=.95, skin='olive', hair='ponytail', hair_col='dark', top='long_coat', top_col=(.42, .33, .20), bottom='trousers', bottom_col=(.02, .022, .026), shoes='shoes', extra=['tote']),
    dict(sex='m', height=1.77, build=1.0, skin='brown', hair='curly', hair_col='black', top='hoodie', top_col=(.16, .17, .18), bottom='jeans', bottom_col=(.05, .09, .18), shoes='sneakers', extra=['backpack']),
    dict(sex='f', height=1.62, build=1.0, skin='pale', hair='bob', hair_col='blonde', top='puffer', top_col=(.06, .20, .12), bottom='jeans', bottom_col=(.08, .12, .22), shoes='sneakers', extra=[]),
    dict(sex='m', height=1.71, build=1.15, skin='light', hair='receding', hair_col='grey', top='jacket', top_col=(.05, .08, .16), bottom='trousers', bottom_col=(.30, .25, .17), shoes='shoes', extra=['glasses', 'beard']),
    dict(sex='f', height=1.70, build=.92, skin='deep', hair='bun', hair_col='black', top='blazer', top_col=(.42, .05, .05), bottom='skirt', bottom_col=(.02, .02, .025), shoes='shoes', extra=['crossbody']),
    dict(sex='m', height=1.86, build=.95, skin='olive', hair='swept', hair_col='black', top='shirt', top_col=(.80, .80, .78), bottom='trousers', bottom_col=(.03, .05, .11), shoes='shoes', extra=[]),
    dict(sex='f', height=1.58, build=1.08, skin='light', hair='bob', hair_col='silver', top='long_coat', top_col=(.25, .38, .48), bottom='trousers', bottom_col=(.18, .18, .19), shoes='shoes', extra=['glasses']),
    dict(sex='m', height=1.74, build=1.0, skin='tan', hair='cap', hair_col='dark', top='tshirt', top_col=(.30, .04, .06), bottom='jeans', bottom_col=(.03, .04, .07), shoes='sneakers', extra=[]),
    dict(sex='f', height=1.68, build=1.0, skin='brown', hair='afro', hair_col='dark', top='denim', top_col=(.12, .20, .34), bottom='jeans', bottom_col=(.015, .015, .02), shoes='sneakers', extra=['crossbody']),
    dict(sex='m', height=1.79, build=1.08, skin='pale', hair='bald', hair_col='brown', top='jacket', top_col=(.02, .02, .022), bottom='jeans', bottom_col=(.05, .08, .15), shoes='boots', extra=['beard']),
    dict(sex='f', height=1.64, build=.92, skin='light', hair='long', hair_col='auburn', top='hoodie', top_col=(.42, .33, .55), bottom='leggings', bottom_col=(.015, .015, .018), shoes='sneakers', extra=['headphones']),
]

WEIGHTS = {}


def register(o, rule):
    WEIGHTS[o.name] = rule
    return o


def E(fn, rule, *args, **kwargs):
    return register(fn(*args, **kwargs), rule)


def blend(y, a, b, lo, hi):
    t = max(0, min(1, (y - lo) / (hi - lo)))
    return {a: 1 - t, b: t}


def weight(rule, p):
    x, y, z = p
    if rule == 'torso':
        return blend(y, 'Hips', 'Chest', .98, 1.37)
    if rule.startswith('arm'):
        side = rule[-1]
        if y > 1.31:
            return blend(abs(x), 'Chest', 'UpperArm' + side, .14, .255)
        return blend(y, 'Forearm' + side, 'UpperArm' + side, 1.06, 1.22)
    if rule.startswith('leg'):
        if y > .82:
            return blend(y, 'Thigh' + rule[-1], 'Hips', .82, .96)
        return blend(y, 'Shin' + rule[-1], 'Thigh' + rule[-1], .43, .61)
    if rule == 'skirt':
        # Skirts follow the hips, with a little thigh influence at the hem.
        side = 'L' if x < 0 else 'R'
        t = max(0, min(1, (.9 - y) / .35))
        return {'Hips': 1 - .5 * t, 'Thigh' + side: .5 * t}
    return {rule: 1}


def sculpted_head(jaw, female, index):
    """Head surface as rings of 32 vertices from the neck to the crown, displaced along the
    radial normal by anatomical features. Returns (verts, faces, front) where front(x, y) is
    the undisplaced face surface depth, used to seat the eyes, brows, nostrils and lips."""
    base = [(1.532, -.02, .036, .045), (1.55, -.014, jaw * .86, .062), (1.585, -.001, jaw, .072), (1.625, .003, .077, .080),
            (1.666, .008, .080, .081), (1.709, .010, .079, .081), (1.75, .013, .073, .076), (1.778, .016, .06, .064),
            (1.795, .018, .038, .042), (1.802, .019, .01, .012)]

    def interp(y):
        for (y0, z0, a0, b0), (y1, z1, a1, b1) in zip(base, base[1:]):
            if y <= y1:
                t = (y - y0) / (y1 - y0)
                return z0 + (z1 - z0) * t, a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
        return base[-1][1:]

    def front(x, y):
        zc, rx, rz = interp(y)
        return zc - rz * math.sqrt(max(0.0, 1.0 - (x / rx) ** 2))

    def g(dx, sx, dy, sy):
        return math.exp(-(dx / sx) ** 2 - (dy / sy) ** 2)

    # Per-person variation: nose size, cheekbones, chin.
    nose_k = .85 + .3 * ((index * 37) % 10) / 10
    cheek_k = .8 + .4 * ((index * 53) % 10) / 10
    chin_k = (.75 if female else 1.0) + .3 * ((index * 71) % 10) / 10
    nose = [(1.598, 0.0), (1.604, .016), (1.611, .025), (1.62, .023), (1.637, .015), (1.654, .0095), (1.67, .005), (1.682, 0.0)]

    def nose_height(y):
        if y <= nose[0][0] or y >= nose[-1][0]:
            return 0.0
        for (y0, h0), (y1, h1) in zip(nose, nose[1:]):
            if y <= y1:
                return h0 + (h1 - h0) * (y - y0) / (y1 - y0)
        return 0.0

    def displacement(x, y, theta):
        f = max(0.0, -math.sin(theta))
        side = abs(math.cos(theta))
        d = 0.0
        for s in (-1, 1):
            d -= .0085 * g(x - s * .031, .015, y - 1.664, .0105) * f                 # eye socket
            d += .0055 * g(x - s * .03, .022, y - 1.689, .0065) * f                  # brow ridge
            d += .0065 * cheek_k * g(x - s * .05, .016, y - 1.638, .013) * f ** .5   # cheekbone
            d -= .0035 * g(x - s * .045, .014, y - 1.603, .014) * f                  # cheek hollow
            d += .0075 * nose_k * g(x - s * .0155, .0062, y - 1.611, .0062) * f      # nostril wing
            d -= .0018 * g(x - s * .029, .005, y - 1.598, .018) * f                  # nasolabial fold
            d -= .004 * g(x - s * .072, .012, y - 1.692, .016) * side                # temple
            d += (.0035 if not female else .0018) * g(x - s * .062, .012, y - 1.566, .012) * side  # jaw angle
        width = .0105 if y < 1.625 else .0078
        d += nose_k * nose_height(y) * math.exp(-(x / width) ** 2) * f              # nose bridge and tip
        d += .003 * g(x, .012, y - 1.684, .008) * f                                  # glabella
        d += .0055 * g(x, .03, y - 1.58, .018) * f                                   # muzzle over the teeth
        d -= .0026 * g(x, .02, y - 1.5795, .0022) * f                                # mouth line
        d -= .0012 * g(x, .004, y - 1.594, .006) * f                                 # philtrum
        d += .0075 * chin_k * g(x, .02, y - 1.547, .011) * f                         # chin
        d -= .002 * g(x, .02, y - 1.563, .004) * f                                   # mentolabial fold
        d += .002 * g(x, .05, y - 1.73, .03) * f                                     # forehead
        return d

    ys = [1.532, 1.545, 1.558, 1.569, 1.578, 1.586, 1.594, 1.602, 1.61, 1.62, 1.63, 1.641, 1.652, 1.661,
          1.669, 1.678, 1.689, 1.702, 1.72, 1.745, 1.77, 1.79]
    # 40 vertices per ring, packed towards the face (theta = 3pi/2 is straight ahead).
    n = 40
    thetas = []
    for j in range(n):
        u = -1.0 + 2.0 * j / n
        thetas.append(1.5 * math.pi + math.pi * math.copysign(abs(u) ** 1.6, u))
    verts, faces = [], []
    for y in ys:
        zc, rx, rz = interp(y)
        for j in range(n):
            theta = thetas[j]
            x, z = rx * math.cos(theta), zc + rz * math.sin(theta)
            d = displacement(x, y, theta)
            verts.append((x + math.cos(theta) * d, y, z + math.sin(theta) * d))
    for i in range(len(ys) - 1):
        for j in range(n):
            k = (j + 1) % n
            faces.append((i * n + j, i * n + k, (i + 1) * n + k, (i + 1) * n + j))
    pole = len(verts)
    verts.append((0.0, 1.802, .019))
    top = (len(ys) - 1) * n
    for j in range(n):
        faces.append((top + j, top + (j + 1) % n, pole))
    return verts, faces, front


def sculpt(index, person):
    clear()
    WEIGHTS.clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    female = person['sex'] == 'f'
    skin = mat(f'CitizenSkin_{index}', SKIN_TONES[person['skin']], .55)
    hair = mat(f'CitizenHair_{index}', HAIR_COLOURS[person['hair_col']], .62)
    top = mat(f'CitizenTop_{index}', person['top_col'], .45 if person['top'] in ('puffer', 'hivis') else .85)
    bottom = mat(f'CitizenBottom_{index}', person['bottom_col'], .8)
    sole = mat('CitizenSole', (.02, .022, .025), .85)
    white = mat('CitizenWhite', (.78, .78, .76), .6)
    eye_white = mat('CitizenEyeWhite', (.72, .70, .66), .25)
    iris = mat('CitizenIris', (.03, .022, .016), .2)
    lip = mat(f'CitizenLip_{index}', tuple(c * .78 for c in SKIN_TONES[person['skin']]), .5)
    trim = mat('CitizenTrim', (.08, .09, .095), .6)
    chest = .182 if female else .208
    waist = .138 if female else .165
    hip = .175 if female else .155
    long_top = person['top'] in ('long_coat',)
    sleeve_end = {'tshirt': 1.27, 'shirt': 1.08}.get(person['top'], .905)

    # Torso garment (continuous with hips), bust shaping for women, hood/quilting by type.
    rings = [(.88, 0, .008, hip * .95, .102), (.98, 0, 0, hip, .11), (1.08, 0, 0, waist, .10),
             (1.22, 0, -.014 if female else -.012, chest * .95, .118 if female else .113), (1.32, 0, -.004, chest, .112),
             (1.40, 0, 0, chest * .97, .104), (1.445, 0, .01, chest * .82, .09), (1.475, 0, .012, .072, .066)]
    if long_top:
        # Long coats hang wider at the hips so legs stay inside mid-stride.
        rings[0] = (.88, 0, .015, hip * 1.12, .118)
        rings[1] = (.98, 0, .004, hip * 1.1, .118)
    if person['top'] == 'puffer':
        # Quilted baffles: the jacket surface itself swells between stitch lines.
        ys = [.88 + i * .03 for i in range(21)]
        base = list(rings)

        def interp(y):
            for (y0, x0, z0, a0, b0), (y1, x1, z1, a1, b1) in zip(base, base[1:]):
                if y <= y1:
                    t = (y - y0) / (y1 - y0)
                    return (y, x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, a0 + (a1 - a0) * t, b0 + (b1 - b0) * t)
            return base[-1]
        rings = []
        for i, y in enumerate(ys):
            _, x, z, rx, rz = interp(y)
            swell = 1.13 if i % 4 in (1, 2) else 1.06
            rings.append((y, x, z, rx * swell, rz * swell))
        rings.append((1.475, 0, .012, .08, .074))
    E(loft, 'torso', 'Top', rings, top, 32)
    if long_top:
        E(loft, 'Hips', 'Coat skirt', [(.52, 0, .035, hip * 1.32, .16), (.72, 0, .025, hip * 1.2, .145), (.9, 0, .01, hip * 1.04, .116)], top, 32)
    if person['top'] == 'hoodie':
        E(ellipsoid, 'Chest', 'Hood', (0, 1.47, .085), (.115, .07, .065), top, n=20, m=10)
        E(panel, 'torso', 'Kangaroo pocket', (0, 1.03, -.1), (.18, .09, .012), top, .005)
        for x in (-.03, .03):
            E(tube, 'Chest', 'Drawstring', [(x, 1.44, -.1), (x, 1.31, -.113)], .004, white, 6)
    if person['top'] in ('shirt', 'blazer', 'jacket', 'long_coat', 'denim'):
        for side in (-1, 1):
            E(tube, 'Chest', 'Collar', [(side * .05, 1.475, -.035), (side * .085, 1.45, -.07), (side * .045, 1.405, -.105)], [.008, .013, .005], top if person['top'] != 'blazer' else white, 10)
    if person['top'] == 'blazer':
        E(panel, 'Chest', 'Shirt front', (0, 1.36, -.106), (.08, .16, .01), white, .004)
        for side in (-1, 1):
            E(tube, 'Chest', 'Lapel', [(side * .03, 1.42, -.112), (side * .075, 1.3, -.118), (side * .06, 1.2, -.112)], .012, top, 8)
    if person['top'] in ('shirt', 'blazer', 'jacket', 'long_coat', 'denim'):
        E(tube, 'torso', 'Placket', [(0, .9 if not long_top else .55, -.104), (0, 1.29, -.124), (0, 1.43, -.095)], .004, trim, 6)
    if person['top'] == 'hivis':
        tape = mat('CitizenReflective', (.65, .69, .48), .35)
        for x in (-.10, .10):
            E(tube, 'torso', 'Reflective tape', [(x, .96, -.108), (x, 1.35, -.104)], .016, tape, 8)
        E(loft, 'torso', 'Reflective band', [(1.0, 0, 0, hip * 1.02, .113), (1.03, 0, 0, hip * 1.02, .113)], tape, 32)

    # Lower body.
    for side in (-1, 1):
        s = 'L' if side < 0 else 'R'
        legcol = bottom if person['bottom'] != 'skirt' else skin
        tight = .82 if person['bottom'] == 'leggings' else 1.0
        E(loft, 'leg' + s, 'Leg', [(.12, side * .091, .004, .045 * tight, .047 * tight), (.26, side * .093, .005, .051 * tight, .055 * tight),
                                   (.43, side * .096, .012, .059 * tight, .066 * tight), (.53, side * .099, 0, .063 * tight, .07 * tight),
                                   (.68, side * .098, .002, .076 * tight, .083 * tight), (.83, side * .094, .004, .086, .093), (.97, side * .086, .006, .088, .10)], legcol, 24)
        if person['bottom'] == 'jeans':
            E(tube, 'leg' + s, 'Outseam', [(side * .145, .14, .0), (side * .15, .6, .0), (side * .175, .95, .0)], .003, mat('CitizenStitch', (.5, .36, .12), .7), 5)
        # Footwear.
        if person['shoes'] == 'sneakers':
            E(loft, 'Foot' + s, 'Sneaker', [(.012, side * .093, -.045, .062, .135), (.045, side * .093, -.047, .063, .136), (.09, side * .093, -.04, .058, .118), (.13, side * .093, .005, .046, .07), (.155, side * .093, .015, .043, .047)], top if index % 2 else white, 24)
            E(loft, 'Foot' + s, 'Sneaker sole', [(.0, side * .093, -.045, .064, .138), (.025, side * .093, -.045, .065, .139)], white, 24)
        elif person['shoes'] == 'boots':
            E(loft, 'Foot' + s, 'Boot', [(.012, side * .093, -.043, .062, .13), (.06, side * .093, -.045, .064, .133), (.12, side * .093, -.01, .055, .08), (.2, side * .095, .01, .05, .056)], mat('CitizenLeather', (.09, .055, .03), .55), 24)
            E(loft, 'Foot' + s, 'Boot sole', [(.0, side * .093, -.043, .064, .134), (.02, side * .093, -.043, .065, .135)], sole, 24)
        else:
            E(loft, 'Foot' + s, 'Shoe', [(.012, side * .093, -.045, .057, .128), (.05, side * .093, -.047, .06, .132), (.095, side * .093, -.035, .052, .1), (.135, side * .093, .008, .043, .06)], mat('CitizenLeather', (.06, .035, .02), .4), 24)
            E(loft, 'Foot' + s, 'Shoe sole', [(.0, side * .093, -.045, .058, .13), (.014, side * .093, -.045, .059, .131)], sole, 24)
        # Arms: sleeve to sleeve_end, bare forearm below for t-shirts and rolled shirts.
        pts = [(side * .158, 1.375, .01), (side * .205, 1.37, .003), (side * .236, 1.30, .006), (side * .263, 1.17, .007), (side * .274, 1.10, -.005), (side * .276, .98, -.013), (side * .277, .905, -.02)]
        radii = [.068, .073, .067, .060, .055, .044, .035]
        cut = next(i for i, p in enumerate(pts) if p[1] <= sleeve_end + 1e-6)
        bulk = 1.12 if person['top'] == 'puffer' else 1.0
        E(tube, 'arm' + s, 'Sleeve', pts[:cut + 1], [r * bulk for r in radii[:cut + 1]], top, 22)
        if cut < len(pts) - 1:
            E(tube, 'arm' + s, 'Forearm skin', pts[cut:], [r * .82 for r in radii[cut:]], skin, 18)
            E(torus, 'arm' + s, 'Cuff', pts[cut], radii[cut] * .95, .012, top, axis='y', n=16, m=6)
        E(ellipsoid, 'Forearm' + s, 'Palm', (side * .278, .863, -.02), (.034, .050, .025), skin, n=18, m=12)
        for finger in range(4):
            xx = side * .278 + (finger - 1.5) * .013
            end = .796 + abs(finger - 1.5) * .006
            E(tube, 'Forearm' + s, 'Finger', [(xx, .85, -.025), (xx, .817, -.028), (xx, end, -.037)], [.008, .007, .0045], skin, 8)
        E(tube, 'Forearm' + s, 'Thumb', [(side * .254, .884, -.025), (side * .239, .855, -.035), (side * .241, .827, -.043)], [.012, .009, .006], skin, 8)
    if person['bottom'] == 'skirt':
        E(loft, 'skirt', 'Skirt', [(.56, 0, .01, .2, .14), (.75, 0, .005, .185, .125), (.95, 0, .005, hip * 1.02, .11), (1.02, 0, 0, waist * 1.04, .102)], bottom, 32)
    elif person['top'] == 'shirt':
        # Tucked shirt: the belt line is visible; other tops cover the waistband.
        E(loft, 'Hips', 'Waistband', [(.96, 0, .006, hip * 1.03, .113), (1.0, 0, .004, waist * 1.07, .108)], bottom, 28)
        E(loft, 'Hips', 'Belt', [(.985, 0, .004, hip * 1.05, .115), (1.0, 0, .004, hip * 1.04, .114)], mat('CitizenLeather', (.06, .035, .02), .4), 28)

    # Neck and head: readable features at street distance.
    E(tube, 'Neck', 'Neck', [(0, 1.43, .015), (0, 1.56, .014)], [.058 if not female else .052, .052 if not female else .047], skin, 18)
    jaw = .062 if female else .068
    # Sculpted head: one smooth surface with eye sockets, brow ridge, nose, cheekbones,
    # muzzle, lips, chin and jaw (replaces the old stacked-ellipse head and stuck-on nose).
    v, f, front = sculpted_head(jaw, female, index)
    E(mesh, 'Head', 'Head', v, f, skin, True)
    for side in (-1, 1):
        E(ellipsoid, 'Head', 'Ear', (side * .080, 1.64, .012), (.013, .028, .019), skin, n=14, m=10)
        ex = side * .031
        ez = front(ex, 1.664)  # undisplaced face surface at the eye: the eyeball sits in its socket
        E(ellipsoid, 'Head', 'Eye white', (ex, 1.664, ez + .0075), (.0128, .0088, .0088), eye_white, n=16, m=10)
        E(ellipsoid, 'Head', 'Iris', (ex, 1.664, ez - .0011), (.0056, .0058, .0016), iris, n=14, m=6)
        E(tube, 'Head', 'Upper lid', [(side * .018, 1.6685, ez + .001), (side * .031, 1.6735, ez - .0022), (side * .045, 1.6675, ez + .002)], .0026, lip, 8)
        E(tube, 'Head', 'Lower lid', [(side * .02, 1.6585, ez + .0008), (side * .031, 1.6555, ez - .0006), (side * .043, 1.659, ez + .0016)], .0016, skin, 8)
        brow = .0042 if not female else .003
        bz = front(side * .032, 1.69) - .0065
        E(tube, 'Head', 'Brow', [(side * .015, 1.687, bz + .002), (side * .032, 1.6925, bz), (side * .05, 1.688, bz + .006)], brow, hair, 8)
        E(ellipsoid, 'Head', 'Nostril', (side * .0068, 1.6045, front(side * .0068, 1.605) - .0105), (.0024, .0012, .0024), iris, n=8, m=4)
    mz = front(0, 1.581) - .0065
    E(tube, 'Head', 'Upper lip', [(-.022, 1.5835, mz + .006), (-.009, 1.5855, mz - .0004), (0, 1.5845, mz - .0012), (.009, 1.5855, mz - .0004), (.022, 1.5835, mz + .006)], [.0022, .0034, .0034, .0034, .0022], lip, 8)
    E(tube, 'Head', 'Lower lip', [(-.019, 1.5775, mz + .006), (0, 1.5745, mz - .0002), (.019, 1.5775, mz + .006)], [.0026, .0046, .0026], lip, 8)

    hair_style(index, person, hair, top)
    for extra in person['extra']:
        accessory(extra, index, hair, top, trim, white)


HEAD_PROFILE = [(1.62, .080), (1.666, .081), (1.709, .078), (1.75, .066), (1.783, .043), (1.80, .012)]


def head_radius(y):
    """Cranium half-width at height y (matches the Head loft) so hair hugs the skull."""
    pts = HEAD_PROFILE
    if y <= pts[0][0]:
        return pts[0][1]
    for (y0, r0), (y1, r1) in zip(pts, pts[1:]):
        if y <= y1:
            return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
    return pts[-1][1]


def cap_rings(lower_front, lower_back, top_y, rx, rz, z0=.016, rings=8, n=36, bulge=1.0, lower_side=None, thickness=.009, bumps=0.0):
    """Hair shell hugging the cranium. The hairline sits at lower_front over the forehead,
    lower_side at the temples and lower_back at the nape; thickness is the hair volume."""
    lower_side = lower_side if lower_side is not None else (lower_front + lower_back) / 2
    # The cranium is fitted by an ellipsoid (centre y 1.66, radii .081/.136/.082); hair is that
    # ellipsoid grown by `thickness`, so crowns are round and the shell hugs the skull.
    cy, ry, rxh, rzh = 1.66, .136, .081, .082
    extra = max(0.0, top_y - 1.796)  # volume on top (afros, curls)
    verts, faces = [], []
    for r in range(rings):
        t = r / (rings - 1)  # 0 at the hairline, 1 at the crown
        for j in range(n):
            a = j * math.tau / n
            f = -math.sin(a)  # 1 at the face, 0 at the sides, -1 at the back
            low = lower_side + (lower_front - lower_side) * f if f > 0 else lower_side + (lower_side - lower_back) * f
            theta_low = math.acos(max(-1.0, min(1.0, (low - cy) / ry)))
            theta = theta_low * (1 - t)
            grow = thickness * bulge
            lift = extra * max(0.0, math.cos(theta))
            bump = bumps * (math.sin(a * 9 + r * 1.7) * math.sin(r * 2.3 + a * 4) * .5 + .5) if bumps else 0.0
            # Superellipse (exponent .8) gives a full, rounded crown rather than an egg tip.
            st = math.copysign(abs(math.sin(theta)) ** .8, math.sin(theta))
            ct = math.copysign(abs(math.cos(theta)) ** .8, math.cos(theta))
            x = (rxh + grow + bump) * st * math.cos(a)
            y = cy + (ry + grow + lift) * ct
            z = z0 + (rzh + grow + bump) * st * math.sin(a)
            verts.append((x, y, z))
    for r in range(rings - 1):
        for j in range(n):
            faces.append((r * n + j, r * n + (j + 1) % n, (r + 1) * n + (j + 1) % n, (r + 1) * n + j))
    return verts, faces


def hair_style(index, person, hair, top):
    """Hairline heights (front/temple/nape) follow a real hairline ~5 cm above the brows."""
    style = person['hair']
    if style == 'bald':
        # Shaved-scalp shadow: a hair-coloured film just above the skin at low opacity read.
        v, f = cap_rings(1.735, 1.6, 1.80, .088, .09, lower_side=1.66, thickness=.0015)
        E(mesh, 'Head', 'Shaved scalp', v, f, mat(f'CitizenStubble_{index}', tuple(c * .5 + .5 * s for c, s in zip(HAIR_COLOURS[person['hair_col']], SKIN_TONES[person['skin']])), .7), True)
        return
    if style == 'cap':
        v, f = cap_rings(1.725, 1.64, 1.815, .088, .09, lower_side=1.665, thickness=.011)
        E(mesh, 'Head', 'Cap crown', v, f, top, True)
        E(panel, 'Head', 'Cap peak', (0, 1.728, -.11), (.14, .01, .075), top, .005)
        v, f = cap_rings(1.70, 1.585, 1.73, .088, .09, lower_side=1.64, thickness=.006, rings=3)
        E(mesh, 'Head', 'Hair below cap', v, f, hair, True)
        return
    if style == 'receding':
        v, f = cap_rings(1.765, 1.6, 1.79, .088, .09, lower_side=1.65, thickness=.006, rings=5)
        E(mesh, 'Head', 'Receding hair', v, f, hair, True)
        return
    if style == 'curly':
        # Tight curls: dense, bumpy, slightly higher volume shell.
        v, f = cap_rings(1.728, 1.6, 1.835, .088, .09, lower_side=1.655, thickness=.018, bumps=.006, rings=10, n=48)
        E(mesh, 'Head', 'Curly hair', v, f, hair, True)
        return
    if style == 'afro':
        v, f = cap_rings(1.725, 1.58, 1.88, .088, .09, lower_side=1.64, thickness=.045, bumps=.008, rings=10, n=48)
        E(mesh, 'Head', 'Afro', v, f, hair, True)
        return
    front = {'crop': 1.73, 'swept': 1.735, 'bob': 1.715, 'ponytail': 1.73, 'bun': 1.73, 'long': 1.72}[style]
    side = {'crop': 1.655, 'swept': 1.655, 'bob': 1.6, 'ponytail': 1.66, 'bun': 1.66, 'long': 1.6}[style]
    back = {'crop': 1.6, 'swept': 1.6, 'bob': 1.56, 'ponytail': 1.6, 'bun': 1.6, 'long': 1.55}[style]
    thick = {'crop': .008, 'swept': .012, 'bob': .014, 'ponytail': .008, 'bun': .008, 'long': .012}[style]
    v, f = cap_rings(front, back, 1.82, .088, .09, lower_side=side, thickness=thick)
    E(mesh, 'Head', 'Hair', v, f, hair, True)
    if style == 'swept':
        E(ellipsoid, 'Head', 'Quiff', (0, 1.785, -.045), (.055, .025, .045), hair, n=14, m=8)
    if style == 'bob':
        # Chin-length sides and back falling outside the ears; open at the face.
        v, f = open_loft([(1.565, .1, .1), (1.62, .101, .101), (1.69, .097, .098)], .022, math.radians(-40), math.radians(220))
        E(mesh, 'Head', 'Bob', v, f, hair, True)
    if style == 'ponytail':
        E(ellipsoid, 'Head', 'Hair tie', (0, 1.715, .1), (.018, .018, .014), hair, n=10, m=6)
        E(tube, 'Head', 'Ponytail', [(0, 1.715, .105), (0, 1.67, .13), (0, 1.57, .125), (0, 1.48, .105)], [.022, .027, .021, .01], hair, 12)
    if style == 'bun':
        E(ellipsoid, 'Head', 'Bun', (0, 1.765, .095), (.04, .038, .04), hair, n=14, m=10)
    if style == 'long':
        E(loft, 'Chest', 'Long hair', [(1.36, 0, .075, .1, .03), (1.5, 0, .08, .104, .04), (1.6, 0, .07, .1, .06)], hair, 24)
        v, f = open_loft([(1.5, .1, .098), (1.6, .1, .1), (1.69, .096, .097)], .02, math.radians(-40), math.radians(220))
        E(mesh, 'Head', 'Long hair sides', v, f, hair, True)


def open_loft(rings, z0, a0, a1, n=24):
    """Elliptical bands from angle a0 to a1 only (e.g. back and sides, leaving the face open).
    Two-sided: outer and inner walls so the open edge never shows a culled back face."""
    verts, faces = [], []
    for wall, scale in ((0, 1.0), (1, .93)):
        base = len(verts)
        for y, rx, rz in rings:
            for j in range(n + 1):
                a = a0 + (a1 - a0) * j / n
                verts.append((rx * scale * math.cos(a), y, z0 + rz * scale * math.sin(a)))
        for i in range(len(rings) - 1):
            for j in range(n):
                q = (base + i * (n + 1) + j, base + i * (n + 1) + j + 1, base + (i + 1) * (n + 1) + j + 1, base + (i + 1) * (n + 1) + j)
                faces.append(q if wall == 0 else tuple(reversed(q)))
    return verts, faces

def accessory(kind, index, hair, top, trim, white):
    if kind == 'backpack':
        E(panel, 'Chest', 'Backpack', (0, 1.2, .19), (.30, .42, .16), mat('CitizenBag', (.27, .11, .06), .85), .05)
        for x in (-.09, .09):
            # Over the shoulder, down the chest surface, then round under the arm to the pack.
            E(tube, 'Chest', 'Strap', [(x, 1.465, .07), (x, 1.455, -.07), (x * 1.15, 1.32, -.123), (x * 1.55, 1.17, -.112), (x * 1.95, 1.1, -.02), (x * 1.6, 1.08, .1)], .011, trim, 6)
    elif kind == 'tote':
        E(panel, 'ForearmR', 'Tote bag', (.30, .88, .0), (.06, .32, .3), mat('CitizenCanvas', (.55, .5, .4), .9), .02)
        E(tube, 'ForearmR', 'Tote handle', [(.29, 1.04, -.1), (.29, 1.2, .0), (.29, 1.04, .1)], .008, trim, 6)
    elif kind == 'crossbody':
        E(tube, 'Chest', 'Crossbody strap', [(-.15, 1.42, -.04), (0, 1.25, -.12), (.15, 1.05, -.1)], .008, trim, 6)
        E(panel, 'Hips', 'Crossbody bag', (.17, 1.0, -.07), (.05, .14, .18), mat('CitizenLeather', (.09, .055, .03), .55), .015)
    elif kind == 'glasses':
        frame = mat('CitizenGlassesFrame', (.02, .02, .02), .3)
        for side in (-1, 1):
            E(tube, 'Head', 'Lens rim', [(side * .016, 1.672, -.083), (side * .046, 1.672, -.081), (side * .046, 1.656, -.081), (side * .016, 1.656, -.083), (side * .016, 1.672, -.083)], .0018, frame, 5)
            E(tube, 'Head', 'Temple arm', [(side * .047, 1.668, -.08), (side * .08, 1.668, .0)], .0016, frame, 4)
        E(tube, 'Head', 'Bridge', [(-.016, 1.668, -.084), (.016, 1.668, -.084)], .0016, frame, 4)
    elif kind == 'beard':
        E(loft, 'Head', 'Beard', [(1.535, 0, -.03, .045, .05), (1.56, 0, -.035, .066, .066), (1.6, 0, -.03, .074, .072), (1.625, 0, -.01, .078, .074)], hair, 28)
        E(tube, 'Head', 'Moustache', [(-.025, 1.592, -.078), (0, 1.596, -.082), (.025, 1.592, -.078)], .0055, hair, 8)
    elif kind == 'headphones':
        E(tube, 'Head', 'Headband', [(-.09, 1.66, .01), (-.07, 1.79, .01), (0, 1.83, .015), (.07, 1.79, .01), (.09, 1.66, .01)], .009, trim, 8)
        for side in (-1, 1):
            E(ellipsoid, 'Head', 'Ear cup', (side * .092, 1.64, .012), (.018, .036, .033), mat('CitizenHeadphone', (.75, .74, .72), .4), n=14, m=8)


def bone_defs(scale, width):
    d = [('Hips', (0, .91, 0), (0, 1.08, 0), None), ('Chest', (0, 1.08, 0), (0, 1.44, 0), 'Hips'),
         ('Neck', (0, 1.44, .01), (0, 1.55, .01), 'Chest'), ('Head', (0, 1.55, .01), (0, 1.79, .02), 'Neck')]
    for side in (-1, 1):
        s = 'L' if side < 0 else 'R'
        d += [('Thigh' + s, (side * .086, .93, 0), (side * .096, .52, 0), 'Hips'), ('Shin' + s, (side * .096, .52, 0), (side * .093, .14, .01), 'Thigh' + s),
              ('Foot' + s, (side * .093, .14, .01), (side * .093, .07, -.14), 'Shin' + s), ('UpperArm' + s, (side * .19, 1.412, 0), (side * .27, 1.145, 0), 'Chest'),
              ('Forearm' + s, (side * .27, 1.145, 0), (side * .278, .855, -.02), 'UpperArm' + s)]
    f = lambda p: (p[0] * width, p[1] * scale, p[2] * width)
    return [(n, f(h), f(t), parent) for n, h, t, parent in d]


def smooth(x):
    return x * x * (3 - 2 * x)


def pose_clip(rig, clip, phase):
    """Hand-authored procedural keys. Rotations: bone-local X pitch, Y twist, Z side bend."""
    B = rig.pose.bones
    for pb in B:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    moving = clip in ('Walk', 'Brisk', 'Carry')
    amp = 1.3 if clip == 'Brisk' else 1.0
    for s, shift, side in (('L', 0.0, -1), ('R', math.pi, 1)):
        p = phase + shift
        # Relaxed arms hang slightly away from the body with soft elbows.
        B['UpperArm' + s].rotation_euler.z = side * -.07
        B['Forearm' + s].rotation_euler.x = -.18
        if moving:
            B['Thigh' + s].rotation_euler.x = math.sin(p) * .44 * amp + .04
            swing = max(0.0, math.cos(p + .35))
            B['Shin' + s].rotation_euler.x = -(.08 + .78 * amp * swing ** 1.6)
            B['Foot' + s].rotation_euler.x = -.22 * math.sin(p + .5) * amp
            B['UpperArm' + s].rotation_euler.x = -math.sin(p) * .34 * amp
            B['Forearm' + s].rotation_euler.x = -(.22 + .26 * max(0.0, -math.sin(p)) * amp)
        if clip == 'Idle':
            B['Thigh' + s].rotation_euler.x = .02 * math.sin(phase * .5 + shift)
        if clip == 'Wait':
            # Weight on one leg, other knee relaxed; hands loosely clasped in front.
            B['Thigh' + s].rotation_euler.z = side * (.04 if s == 'L' else -.02)
            B['Shin' + s].rotation_euler.x = -.18 if s == 'R' else -.02
            B['UpperArm' + s].rotation_euler.x = .32
            B['UpperArm' + s].rotation_euler.z = side * .18
            B['Forearm' + s].rotation_euler.x = .95
        if clip == 'Talk':
            gesture = .55 + .35 * math.sin(phase * (2 if s == 'R' else 1) + shift)
            B['UpperArm' + s].rotation_euler.x = .25 + (.15 * math.sin(phase + shift) if s == 'R' else .05)
            B['Forearm' + s].rotation_euler.x = gesture if s == 'R' else .65
        if clip == 'Carry':
            B['UpperArm' + s].rotation_euler.x = .38
            B['UpperArm' + s].rotation_euler.z = side * .12
            B['Forearm' + s].rotation_euler.x = 1.05
        if clip == 'Sit':
            B['Thigh' + s].rotation_euler.x = 1.45
            B['Shin' + s].rotation_euler.x = -1.45
            B['UpperArm' + s].rotation_euler.x = .45
            B['Forearm' + s].rotation_euler.x = .55
        if clip == 'Cycle':
            w = math.sin(p)
            B['Thigh' + s].rotation_euler.x = 1.1 - w * .28
            B['Shin' + s].rotation_euler.x = -1.55 - w * .42
            B['Foot' + s].rotation_euler.x = .15 * w
            B['UpperArm' + s].rotation_euler.x = 1.2
            B['Forearm' + s].rotation_euler.x = .35
    # Torso, pelvis and head.
    if moving:
        B['Hips'].rotation_euler.y = .09 * math.sin(phase) * amp      # pelvis twist with the stride
        B['Hips'].rotation_euler.z = .045 * math.sin(phase)            # hip drop on the swing side
        B['Chest'].rotation_euler.y = -.12 * math.sin(phase) * amp     # shoulders counter-rotate
        B['Chest'].rotation_euler.x = .05 * amp + (.08 if clip == 'Carry' else 0)
        B['Head'].rotation_euler.y = .05 * math.sin(phase)            # keeps the gaze steady
        B['Head'].rotation_euler.x = -.03 + .015 * math.cos(2 * phase)
    elif clip == 'Cycle':
        B['Chest'].rotation_euler.x = -.28
        B['Head'].rotation_euler.x = .2
    else:
        breathe = math.sin(phase)
        B['Chest'].rotation_euler.x = .012 * breathe
        B['Hips'].rotation_euler.z = .02 * math.sin(phase * .5)
        B['Head'].rotation_euler.y = (.35 * math.sin(phase * .5) if clip == 'Wait' else .06 * math.sin(phase * .5))
        B['Head'].rotation_euler.x = .03 * math.sin(phase) if clip == 'Talk' else 0
    if clip == 'Sit':
        B['Hips'].location.y = -.45


REPORT = {}


def consolidate(index, objects):
    """Skinned meshes cannot batch, so every material is a draw call per citizen.
    Fold detail materials into at most seven: skin, hair, top, bottom, dark, light, accent."""
    dark = mat('CitizenDark', (.03, .026, .023), .55)
    light = mat('CitizenLight', (.76, .75, .73), .45)
    accent = None
    groups = {'CitizenLip': f'CitizenSkin_{index}', 'CitizenStubble': f'CitizenHair_{index}'}
    for o in objects:
        name = o.data.materials[0].name
        if name.startswith(('CitizenSole', 'CitizenIris', 'CitizenTrim', 'CitizenLeather', 'CitizenStitch', 'CitizenGlassesFrame')):
            target = dark
        elif name.startswith(('CitizenWhite', 'CitizenEyeWhite', 'CitizenHeadphone')):
            target = light
        elif name.startswith(('CitizenBag', 'CitizenCanvas', 'CitizenReflective')):
            accent = accent or o.data.materials[0]
            target = accent
        else:
            key = next((k for k in groups if name.startswith(k)), None)
            target = bpy.data.materials[groups[key]] if key else None
        if target is not None:
            o.data.materials[0] = target


def rig_and_save(index, person):
    scale = person['height'] / 1.80
    width = person['build'] * (.97 if person['sex'] == 'f' else 1.0)
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    consolidate(index, objects)
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = 'CitizenRig'
    rig.data.edit_bones.remove(rig.data.edit_bones[0])
    for name, head, tail, parent in bone_defs(scale, width):
        b = rig.data.edit_bones.new(name)
        b.head = P(head)
        b.tail = P(tail)
        if parent:
            b.parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in objects:
        rule = WEIGHTS[o.name]
        for v in o.data.vertices:
            for bone, value in weight(rule, (v.co.x, v.co.z, -v.co.y)).items():
                if value > .0001:
                    vg = o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone)
                    vg.add([v.index], value, 'REPLACE')
        # Body proportions after weighting: weights were computed on the 1.80 m reference.
        for v in o.data.vertices:
            v.co.x *= width
            v.co.y *= width
            v.co.z *= scale
        o.parent = rig
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = 'CitizenSkinnedBody'
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(body.data)
    bm.free()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.1519, island_margin=.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    mod = body.modifiers.new('Weighted skin deformation', 'ARMATURE')
    mod.object = rig
    rig.animation_data_create()
    for clip in CLIPS:
        action = bpy.data.actions.new(clip)
        rig.animation_data.action = action
        moving = clip in ('Walk', 'Brisk', 'Carry')
        for frame in range(1, 34, 2):
            phase = (frame - 1) / 32 * math.tau
            pose_clip(rig, clip, phase)
            if moving:
                # Root height keeps the lowest sole on the ground: planted feet, natural bob.
                bpy.context.view_layer.update()
                evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
                m = evaluated.to_mesh()
                sole = min((evaluated.matrix_world @ v.co).z for v in m.vertices)
                evaluated.to_mesh_clear()
                rig.pose.bones['Hips'].location.y += .002 - sole
            for pb in rig.pose.bones:
                pb.keyframe_insert('rotation_euler', frame=frame, group=pb.name)
                pb.keyframe_insert('location', frame=frame, group=pb.name)
        track = rig.animation_data.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 1, action)
        track.mute = True
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.scene.frame_set(1)
    bpy.context.scene.render.fps = 30
    name = 'citizen_%d' % index
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'source', name + '.blend'))
    for level, ratio in ((0, 1), (1, .48), (2, .20)):
        if level:
            bpy.context.view_layer.objects.active = body
            dec = body.modifiers.new('LOD simplification', 'DECIMATE')
            dec.ratio = ratio / (1 if level == 1 else .48)
            bpy.ops.object.modifier_move_up(modifier=dec.name)
            bpy.ops.object.modifier_apply(modifier=dec.name)
        body.data.validate(clean_customdata=False)
        tri = sum(len(p.vertices) - 2 for p in body.data.polygons)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name + ('_lod%d' % level if level else '') + '.glb'), export_format='GLB',
                                  export_animations=True, export_animation_mode='ACTIONS', export_nla_strips=True, export_force_sampling=True, export_apply=False)
        REPORT[name + ('_lod%d' % level if level else '')] = {'triangles': tri, 'bones': len(rig.data.bones), 'clips': CLIPS,
                                                               'height': person['height'], 'outfit': [person['top'], person['bottom'], person['shoes']], 'hair': person['hair']}
        print('PERSON', name, level, tri, flush=True)


indices = [int(a) for a in sys.argv[sys.argv.index('--') + 1:]] if '--' in sys.argv else list(range(len(PEOPLE)))
for index in indices:
    sculpt(index, PEOPLE[index])
    rig_and_save(index, PEOPLE[index])
manifest = os.path.join(OUT, 'source', 'people_manifest.json')
old = json.load(open(manifest)) if os.path.exists(manifest) else {}
old.update(REPORT)
json.dump(old, open(manifest, 'w'), indent=2)
