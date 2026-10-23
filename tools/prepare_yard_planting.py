"""Front-yard planting kit for the residential lots -> assets/landscape/yard.glb.

Replaces the city kit's primitive lumpy blob shrubs (build_houses.py garden_bed) and the box
hedge with real planting:
  flower_bed_a..d   mulched foundation beds edged with bevelled granite setts, planted with
                    flowering geraniums (red / pink / lilac / orange, from the geranium pack) in two
                    staggered rows; 2.4 m (a-c, room for a boxwood ball at +x) and 1.6 m (d), 0.8 m deep.
  pot_geranium_*    rolled-rim pots (terracotta, charcoal glaze, cream stone) with a geranium, for
                    the foot of the porch steps (knee height: solid in game, PropColliders).
  boxwood_ball      clipped boxwood ball, 0.55 m.
  hedge_section     2.36 x 1.1 x 0.8 m clipped privet hedge section (same footprint as the old box,
                    so the boundary-hedge colliders are unchanged): a lumpy rounded core with a
                    seamless small-leaf texture plus leaf-spray cards that break the silhouette.

Run headless (never on the user's live Blender session):
  blender --background --factory-startup --python tools/prepare_yard_planting.py -- [--no-qa]
Sources: sketchup_assets/geranium_flowering_plants_free.glb (geraniums; its pots are not used).
The leaf textures for the hedge / boxwood are painted procedurally here (numpy).

Conventions as tools/prepare_landscape.py (whose helpers this script reuses): metres, origin at the
footprint centre on the ground, +Y forward in Blender = the street side (-Z) ... every asset is
symmetric enough that only the beds care: their long axis is X, front edge at +Y (Blender) which is
Godot -Z; CityLandscape turns them with the lot. COLOR_0 = wind data for foliage_wind.gdshader;
materials named yard_* are plain (stone, mulch, pots) in CityLandscape.material_for.
"""
import bpy, bmesh, sys, os, math, json, random
import numpy as np
from mathutils import Vector, Matrix, noise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lib = os.path.join(ROOT, "tools", "prepare_landscape.py")
_src = open(_lib).read().rsplit("\nmain()", 1)[0]
_ns = {"__name__": "landscape_lib", "__file__": _lib}
exec(compile(_src, _lib, "exec"), _ns)
globals().update({k: v for k, v in _ns.items() if not k.startswith("__")})

GERANIUM_SRC = os.path.join(ROOT, "sketchup_assets", "geranium_flowering_plants_free.glb")
OUT_GLB = os.path.join(OUT, "yard.glb")
DO_QA = "--no-qa" not in ARGS
rng = random.Random(4127)


def ylog(*a):
    print("[yard]", *a, flush=True)


# ----------------------------------------------------------------------------- textures
def paint_leaves(size, count, length, width, palette, bg, seed, wrap=True, alpha=False, region=None, twig=None):
    """Numpy leaf painter: `count` shaded elliptic leaves (length / width in px, +-30 %) in random
    orientations over `bg`. wrap=True makes the result tile seamlessly. Later leaves are drawn on top
    and brighter (outer layer), earlier ones darker (inner shade). region = (x0, y0, x1, y1, cx, cy)
    confines leaf centres to a spray around (cx, cy) for alpha cards."""
    r = np.random.default_rng(seed)
    px = np.zeros((size, size, 4), np.float32)
    px[..., :3] = bg
    px[..., 3] = 0.0 if alpha else 1.0
    if twig is not None:
        for (x0, y0, x1, y1, w) in twig:
            n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 2
            for t in np.linspace(0, 1, n):
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                xi, yi = int(x), int(y)
                ys, xs = slice(max(0, yi - w), min(size, yi + w + 1)), slice(max(0, xi - w), min(size, xi + w + 1))
                px[ys, xs, :3] = (0.22, 0.17, 0.1)
                px[ys, xs, 3] = 1.0
    for i in range(count):
        depth = i / max(1, count - 1)
        if region is None:
            cx, cy = r.uniform(0, size), r.uniform(0, size)
            ang = r.uniform(0, math.pi)
        else:
            # Spray: leaves on a fan round (ox, oy), radius R, opening `spread` round straight up;
            # denser and darker near the stem, sparse lighter tips (an irregular silhouette).
            ox, oy, R, spread = region
            rr = R * (0.15 + 0.85 * r.uniform(0, 1) ** 0.6)
            th = math.pi / 2 + r.uniform(-spread, spread) * (0.5 + 0.5 * rr / R)
            cx, cy = ox + rr * math.cos(th), oy + rr * math.sin(th)
            ang = th + r.uniform(-0.7, 0.7)
        a = length * r.uniform(0.7, 1.3) * 0.5
        b = width * r.uniform(0.75, 1.25) * 0.5
        col = np.array(palette[r.integers(len(palette))], np.float32) * r.uniform(0.85, 1.1)
        light = (0.55 + 0.6 * depth) * r.uniform(0.8, 1.15)
        ca, sa = math.cos(ang), math.sin(ang)
        rad = int(a) + 2
        ys = np.arange(int(cy) - rad, int(cy) + rad + 1)
        xs = np.arange(int(cx) - rad, int(cx) + rad + 1)
        X, Y = np.meshgrid(xs, ys)
        dx, dy = X - cx, Y - cy
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        # Leaf outline: pointed ellipse (narrower towards the tip).
        taper = 1.0 - 0.35 * np.clip(u / a, 0, 1)
        inside = (u / a) ** 2 + (v / (b * taper)) ** 2 <= 1.0
        if not inside.any():
            continue
        across = np.abs(v) / (b * taper + 1e-6)
        shade = light * (0.78 + 0.32 * (1.0 - across)) * (0.92 + 0.12 * (u / a))
        rib = across < 0.12
        shade = np.where(rib, shade * 1.12, shade)
        if wrap:
            Yi, Xi = Y % size, X % size
        else:
            ok = (X >= 0) & (X < size) & (Y >= 0) & (Y < size)
            inside &= ok
            Yi, Xi = np.clip(Y, 0, size - 1), np.clip(X, 0, size - 1)
        yy, xx = Yi[inside], Xi[inside]
        px[yy, xx, :3] = np.clip(col[None, :] * shade[inside][:, None], 0, 1)
        px[yy, xx, 3] = 1.0
    return px


HEDGE_GREENS = [(0.16, 0.30, 0.09), (0.20, 0.36, 0.11), (0.13, 0.26, 0.08), (0.24, 0.40, 0.13), (0.18, 0.33, 0.12)]


def hedge_textures():
    """Seamless dense small-leaf surface (1024, opaque) + a 2x2 sheet of leaf sprays (512, alpha)."""
    dense = paint_leaves(1024, 9000, 26, 11, HEDGE_GREENS, (0.035, 0.07, 0.025), 11)
    p_dense = write_png(dense, os.path.join(TMP, "yard_hedge_leaves.png"))
    sheet = np.zeros((512, 512, 4), np.float32)
    for k in range(4):
        tx, ty = (k % 2) * 256, (k // 2) * 256
        # A spray: twig from the bottom centre fanning up, leaves around it.
        twig = [(128, 8, 128 + (k - 1.5) * 12, 140, 1), (128, 60, 78 + k * 8, 170, 1), (128, 75, 180 - k * 6, 185, 1)]
        tile = paint_leaves(256, 150 + 25 * k, 26, 11, HEDGE_GREENS, (0.18, 0.3, 0.1), 40 + k, wrap=False, alpha=True,
                            region=(128, 6, 225, 0.85), twig=twig)
        sheet[ty:ty + 256, tx:tx + 256] = tile
    sheet = dilate(sheet)
    p_sheet = write_png(sheet, os.path.join(TMP, "yard_hedge_sprays.png"))
    return p_dense, p_sheet


def swatch_texture(name, tones, size=256, grain=0.06, seed=1):
    """2x2 swatches of `tones` with grain noise (stone setts / pot glazes); UVs pick a swatch."""
    r = np.random.default_rng(seed)
    px = np.ones((size, size, 4), np.float32)
    h = size // 2
    for k, tone in enumerate(tones[:4]):
        x, y = (k % 2) * h, (k // 2) * h
        n = r.normal(0, grain, (h, h, 1)).astype(np.float32)
        blot = np.kron(r.normal(0, grain * 0.8, (h // 16, h // 16, 1)), np.ones((16, 16, 1))).astype(np.float32)
        px[y:y + h, x:x + h, :3] = np.clip(np.array(tone, np.float32)[None, None, :] * (1 + n + blot), 0, 1)
    return write_png(px, os.path.join(TMP, name + ".png"))


def jpg_from(path_in, name, max_px):
    img = load_image(path_in)
    out = image_file(img, max_px, os.path.join(TMP, name + ".jpg"))
    bpy.data.images.remove(img)
    return out


# ----------------------------------------------------------------------------- geometry helpers
def mesh_obj(name, verts, faces, uvs=None, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        flat = []
        for f, fu in zip(faces, uvs):
            flat += list(fu)
        uvl.data.foreach_set("uv", np.array(flat, np.float32).ravel())
    if mat is not None:
        me.materials.append(mat)
    me.update()
    return new_obj(name, me)


def box_bm(bm, c, s, yaw=0.0, uv_tile=(0, 0), skip_bottom=True):
    """Bevel-free box into bm (bevelled afterwards by the caller); returns its verts."""
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    R = Matrix.Rotation(yaw, 3, "Z")
    pts = [Vector(c) + R @ Vector((x, y, z)) for z in (-hz, hz) for y in (-hy, hy) for x in (-hx, hx)]
    vs = [bm.verts.new(p) for p in pts]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for qi, q in enumerate(quads):
        if skip_bottom and qi == 0:
            continue
        out.append(bm.faces.new([vs[i] for i in q]))
    return vs, out


def box_uv(obj, scale, tile_of_face=None, tiles=2):
    """Box-projection UVs (metres * scale), optionally squeezed into a swatch tile per face."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers[0]
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u, v = [(co.y, co.z), (co.x, co.z), (co.x, co.y)][ax]
            if tile_of_face is None:
                uvl.data[li].uv = (u * scale, v * scale)
            else:
                t = tile_of_face(p)
                fu, fv = (u * scale) % 1.0, (v * scale) % 1.0
                uvl.data[li].uv = ((t % tiles + 0.08 + fu * 0.84) / tiles, (t // tiles + 0.08 + fv * 0.84) / tiles)


def smooth(obj, angle=60):
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        select_only([obj])
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    except Exception:
        pass


def set_flat_vcol(obj, r=0.0, g=0.0, b=0.0, a=1.0):
    set_vcol(obj.data, np.tile([r, g, b, a], (len(obj.data.vertices), 1)))


# ----------------------------------------------------------------------------- geraniums
GERANIUMS = [("red", "Geranium05_0"), ("pink", "Geranium_02_7"), ("lilac", "Geranium_03_8"), ("orange", "Geranium_01_6")]


def geranium_kit():
    """Import the geranium pack; returns {colour: plant object (origin at stem base)}, atlas material."""
    reset()
    bpy.ops.import_scene.gltf(filepath=GERANIUM_SRC)
    plants = {}
    tiles = []
    nrm_img = None
    for k, (colour, node) in enumerate(GERANIUMS):
        root = bpy.data.objects[node]
        meshes = [o for o in root.children_recursive if o.type == "MESH"]
        o = bake(meshes, "ger_" + colour)
        mat = meshes[0].data.materials[0]
        col, nrm = base_and_normal(mat)
        if nrm_img is None:
            nrm_img = nrm
        p = image_file(col, 512, os.path.join(TMP, "ger_%s.png" % colour), keep_alpha=True)
        tiles.append(read_png(p))
        # UVs into tile k of the 2x2 atlas.
        uvl = o.data.uv_layers[0]
        uv = np.empty(len(uvl.data) * 2, np.float32)
        uvl.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        if uv.min() < -0.01 or uv.max() > 1.01:
            ylog("WARNING geranium UVs outside 0..1", colour, uv.min(0), uv.max(0))
        uv = np.clip(uv, 0, 1)
        uv = (uv * 0.5 + np.array([(k % 2) * 0.5, (k // 2) * 0.5], np.float32))
        uvl.data.foreach_set("uv", uv.ravel())
        o.data.materials.clear()
        H = base_to_origin(o)
        ylog("geranium", colour, "tris", tris(o.data), "height %.2f" % H)
        plants[colour] = (o, H)
    atlas = np.zeros((1024, 1024, 4), np.float32)
    for k, t in enumerate(tiles):
        x, y = (k % 2) * 512, (k // 2) * 512
        atlas[y:y + 512, x:x + 512] = t
    atlas = dilate(atlas)
    pa = write_png(atlas, os.path.join(TMP, "yard_geranium_atlas.png"))
    pn_single = image_file(nrm_img, 512, os.path.join(TMP, "ger_n.png"), keep_alpha=False)
    n1 = read_png(pn_single.replace(".png", ".jpg")) if not os.path.exists(pn_single) else read_png(pn_single)
    natlas = np.tile(n1, (2, 2, 1))
    natlas[..., 3] = 1.0
    pn = write_png(natlas, os.path.join(TMP, "yard_geranium_n.png"))
    mat = make_material("yardleaf_geranium", load_image(pa, name="yard_geranium_atlas"),
                        load_image(pn, True, "yard_geranium_n"), cutout=True, rough=0.75)
    for o, H in plants.values():
        o.data.materials.append(mat)
    # Drop everything else from the pack.
    for ob in list(bpy.data.objects):
        if ob.name not in [p.name for p, _ in plants.values()]:
            delete([ob])
    return plants, mat


def plant_copy(plants, colour, at, height, yaw, name):
    src, H = plants[colour]
    o = copy_obj(src, name)
    s = height / H
    co = verts_np(o.data) * s
    R = np.array(Matrix.Rotation(yaw, 3, "Z"))
    co = co @ R.T + np.array(at)
    set_verts(o.data, co)
    generic_vcol(o, height, flutter=0.35, sway_scale=0.5)
    # generic_vcol's sway weights assume the base at z = 0; shift-insensitive enough for low plants.
    return o


# ----------------------------------------------------------------------------- materials
def materials(p_dense, p_sheet):
    """Two shared surfaces for everything but the hedge: `yard_ground` (plain) is one 1024 atlas -
    mulch (top half, two 1.2 m repeats wide), granite sett swatches (bottom left), pot glazes (bottom
    right) - and the foliage. Every bed / pot is then 2 draw calls (+ shadow) per cell, not 5."""
    m = {}
    p_stone = swatch_texture("yard_stone_swatch", [(0.56, 0.55, 0.52), (0.47, 0.46, 0.44), (0.62, 0.59, 0.54), (0.42, 0.41, 0.4)], seed=3)
    soil_src = os.path.join(ROOT, "world", "citykit", "textures", "garden_soil_albedo.png")
    p_mulch = jpg_from(soil_src, "yard_mulch", 512)
    p_pots = swatch_texture("yard_pot_swatch", [(0.69, 0.36, 0.22), (0.17, 0.19, 0.21), (0.84, 0.81, 0.74), (0.6, 0.31, 0.2)], grain=0.04, seed=5)
    atlas = np.ones((1024, 1024, 4), np.float32)
    mulch = read_png(p_mulch)
    atlas[512:, :512] = mulch
    atlas[512:, 512:] = mulch
    atlas[:512, :512] = np.kron(read_png(p_stone), np.ones((2, 2, 1)))
    atlas[:512, 512:] = np.kron(read_png(p_pots), np.ones((2, 2, 1)))
    atlas[..., 3] = 1.0
    pa = write_png(atlas, os.path.join(TMP, "yard_ground_atlas.png"))
    m["ground"] = make_material("yard_ground", load_image(pa, name="yard_ground_atlas"), rough=0.88)
    m["stone"] = m["mulch"] = m["pot"] = m["ground"]
    m["hedge"] = make_material("yardleaf_hedge", load_image(p_dense, name="yard_hedge_leaves"), rough=0.85)
    m["sprays"] = make_material("yardleaf_sprays", load_image(p_sheet, name="yard_hedge_sprays"), cutout=True, rough=0.8)
    return m


def to_quadrant(obj, u0, v0, su=0.5, sv=0.5):
    """Squeeze an object's 0..1 UVs into an atlas region."""
    uvl = obj.data.uv_layers[0]
    uv = np.empty(len(uvl.data) * 2, np.float32)
    uvl.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    uv[:, 0] = u0 + np.clip(uv[:, 0], 0, 1) * su
    uv[:, 1] = v0 + np.clip(uv[:, 1], 0, 1) * sv
    uvl.data.foreach_set("uv", uv.ravel())


def planar_uv(obj, x0, x1, y0, y1, u0, u1, v0, v1):
    """Top-down UVs: (x, y) in the given box -> the given atlas region."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers[0]
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            fx = min(1.0, max(0.0, (co.x - x0) / (x1 - x0)))
            fy = min(1.0, max(0.0, (co.y - y0) / (y1 - y0)))
            uvl.data[li].uv = (u0 + (u1 - u0) * fx, v0 + (v1 - v0) * fy)


# ----------------------------------------------------------------------------- pieces
def edging(L, W, mats, name):
    """Granite setts on edge round an L x W bed (outer size), sunk 2 cm, small random yaw / height."""
    bm = bmesh.new()
    sett, thick, tall = 0.17, 0.075, 0.1
    runs = []
    for sy in (-1, 1):
        runs.append(((-L / 2 + thick / 2, sy * (W / 2 - thick / 2)), (L / 2 - thick / 2, sy * (W / 2 - thick / 2)), 0.0))
    for sx in (-1, 1):
        runs.append(((sx * (L / 2 - thick / 2), -W / 2 + thick * 1.5), (sx * (L / 2 - thick / 2), W / 2 - thick * 1.5), math.pi / 2))
    faces_tile = {}
    for (x0, y0), (x1, y1), yaw in runs:
        length = math.hypot(x1 - x0, y1 - y0) + (thick if yaw == 0.0 else 0.0)
        n = max(1, round(length / (sett + 0.012)))
        step = length / n
        for i in range(n):
            t = (i + 0.5) / n
            cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            if yaw == 0.0:
                cx = -L / 2 + step * (i + 0.5)
            h = tall + rng.uniform(-0.012, 0.012)
            _, fs = box_bm(bm, (cx, cy, h / 2 - 0.02), (step - 0.012, thick, h), yaw + rng.uniform(-0.04, 0.04))
            tile = rng.randrange(4)
            for f in fs:
                faces_tile[f] = tile
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.012, segments=1, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = new_obj(name, me)
    o.data.materials.append(mats["stone"])
    # one swatch per sett: islands get a random tile
    isl = face_islands(o.data)
    tile_of = {i: rng.randrange(4) for i in set(isl.tolist())}
    pid_tile = {p.index: tile_of[int(isl[p.index])] for p in o.data.polygons}
    box_uv(o, 2.0, lambda p: pid_tile[p.index])
    to_quadrant(o, 0.0, 0.0)
    set_flat_vcol(o, 0, 0, 0, 1)
    return o


def mulch(L, W, mats, name, top=0.075):
    """Domed mulch surface inside the edging (its rim tucked under the setts)."""
    nx, ny = max(4, int(L / 0.2)), max(3, int(W / 0.2))
    verts, faces, uvs = [], [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = -L / 2 + 0.05 + (L - 0.1) * i / nx
            y = -W / 2 + 0.05 + (W - 0.1) * j / ny
            edge = min(i, nx - i, j, ny - j)
            z = (top - 0.03) + (0.03 if edge > 0 else 0.0) + 0.012 * noise.noise(Vector((x * 4, y * 4, 0.5)))
            verts.append((x, y, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    o = mesh_obj(name, verts, faces, None, mats["mulch"])
    planar_uv(o, -L / 2, L / 2, -W / 2, W / 2, 0.01, 0.99, 0.51, 0.99)
    set_flat_vcol(o, 0, 0, 0, 1)
    return o


def rounded_box_core(size, radii, cuts, mat, name, noise_amp=0.03, noise_freq=2.4, seed=0.0, ground=0.0):
    """Lumpy clipped-shrub core: subdivided box mapped onto an anisotropically rounded box, noise
    along the normal, everything below `ground` removed (it stands on the lawn)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    half = Vector(size) / 2
    rad = Vector(radii)
    for v in bm.verts:
        p = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        s = Vector((p.x / rad.x, p.y / rad.y, p.z / rad.z))
        hs = Vector((half.x / rad.x - 1, half.y / rad.y - 1, half.z / rad.z - 1))
        inner = Vector((max(-hs.x, min(hs.x, s.x)), max(-hs.y, min(hs.y, s.y)), max(-hs.z, min(hs.z, s.z))))
        d = s - inner
        if d.length > 1e-6:
            s = inner + d.normalized()
        p = Vector((s.x * rad.x, s.y * rad.y, s.z * rad.z))
        v.co = p
    bm.normal_update()
    for v in bm.verts:
        n = v.normal
        q = v.co * noise_freq + Vector((seed, seed * 0.7, seed * 1.3))
        amp = noise_amp * noise.noise(q) + noise_amp * 0.35 * noise.noise(q * 3.1)
        v.co += n * amp
    # Lift so the lowest ring sits `ground` below zero, then cut the bottom.
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z += -zmin - 0.12
    dead = [f for f in bm.faces if all(v.co.z < ground - 0.01 for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = new_obj(name, me)
    o.data.materials.append(mat)
    smooth(o, 80)
    return o


def spray_cards(core, count, size_rng, mat, name, seed, z_min=0.15, push=(0.0, 0.05), up_bias=0.35):
    """Leaf-spray cards rooted on the core surface, leaning outwards (silhouette and depth)."""
    r = np.random.default_rng(seed)
    me = core.data
    polys = [p for p in me.polygons if p.center.z > z_min]
    areas = np.array([p.area for p in polys])
    pick = r.choice(len(polys), size=count, p=areas / areas.sum())
    verts, faces, uvs, phase = [], [], [], []
    for k, pi in enumerate(pick):
        p = polys[pi]
        n = Vector(p.normal)
        base = Vector(p.center) + n * r.uniform(*push)
        outward = (n + Vector((r.normal(0, 0.35), r.normal(0, 0.35), up_bias + r.normal(0, 0.2)))).normalized()
        side = outward.cross(Vector((0, 0, 1)))
        if side.length < 0.1:
            side = Vector((1, 0, 0))
        side = side.normalized()
        twist = r.uniform(-0.6, 0.6)
        side = (Matrix.Rotation(twist, 3, outward) @ side).normalized()
        s = r.uniform(*size_rng)
        root = base - outward * s * 0.35
        a = root - side * s * 0.5
        b = root + side * s * 0.5
        c = b + outward * s
        d = a + outward * s
        i0 = len(verts)
        verts += [tuple(a), tuple(b), tuple(c), tuple(d)]
        faces.append((i0, i0 + 1, i0 + 2, i0 + 3))
        t = r.integers(4)
        tx, ty = (t % 2) * 0.5, (t // 2) * 0.5
        flip = r.random() < 0.5
        u0, u1 = (tx + 0.5, tx) if flip else (tx, tx + 0.5)
        uvs.append(((u0, ty), (u1, ty), (u1, ty + 0.5), (u0, ty + 0.5)))
        phase.append(r.random())
    o = mesh_obj(name, verts, faces, uvs, mat)
    # wind: tips flutter, roots still
    co = verts_np(o.data)
    H = max(0.01, co[:, 2].max())
    col = np.zeros((len(co), 4), np.float32)
    for k in range(len(faces)):
        for j, wgt in enumerate((0.0, 0.0, 1.0, 1.0)):
            vi = faces[k][j]
            col[vi] = (0.12 * co[vi, 2] / H, 0.6 * wgt, phase[k], 0.75 + 0.25 * co[vi, 2] / H)
    set_vcol(o.data, col)
    return o


def core_vcol(o, H):
    co = verts_np(o.data)
    ao = np.clip(0.55 + 0.45 * co[:, 2] / max(H, 0.01), 0, 1)
    set_vcol(o.data, np.stack([np.zeros(len(co)), np.zeros(len(co)), np.zeros(len(co)), ao], 1))


def hedge_section(mats):
    L, H, D = 2.36, 1.1, 0.8
    core = rounded_box_core((L, D, H + 0.12), (0.05, 0.16, 0.16), 6, mats["hedge"], "hedge_core", noise_amp=0.022, seed=3.0)
    # Keep the section inside its 2.36 m (x) / 0.8 m (y) box: neighbours leave a 4 cm gap.
    co = verts_np(core.data)
    co[:, 0] = np.clip(co[:, 0], -L / 2, L / 2)
    co[:, 1] = np.clip(co[:, 1], -D / 2 - 0.02, D / 2 + 0.02)
    set_verts(core.data, co)
    box_uv(core, 1.0 / 0.55)
    core_vcol(core, H)
    cards = spray_cards(core, 90, (0.16, 0.26), mats["sprays"], "hedge_sprays", 7, z_min=0.3, push=(-0.02, 0.02), up_bias=0.6)
    # cards may not reach past the section ends (no overlap with the neighbour's cards)
    cc = verts_np(cards.data)
    cc[:, 0] = np.clip(cc[:, 0], -L / 2 - 0.04, L / 2 + 0.04)
    cc[:, 2] = np.maximum(cc[:, 2], 0.05)
    set_verts(cards.data, cc)
    o = join_meshes([core, cards], "hedge_section")
    return o, {"height": H, "kind": "hedge", "length": L}


def boxwood_ball(mats, name="boxwood_ball", d=0.55, seed=5.0):
    core = rounded_box_core((d, d, d * 0.95), (d * 0.48, d * 0.48, d * 0.45), 4, mats["hedge"], name + "_core", noise_amp=0.018, noise_freq=5.0, seed=seed)
    box_uv(core, 1.0 / 0.4)
    H = verts_np(core.data)[:, 2].max()
    core_vcol(core, H)
    cards = spray_cards(core, 26, (0.1, 0.16), mats["sprays"], name + "_sprays", int(seed * 10), z_min=0.05, up_bias=0.1)
    o = join_meshes([core, cards], name)
    return o, {"height": float(H), "kind": "boxwood"}


def bed_layout(colours, L, ball):
    """Two staggered rows: taller plants at the back (by the house), shorter in front."""
    span = L - 0.45 - (0.55 if ball else 0.0)
    x0 = -L / 2 + 0.25
    back = [x0 + span * (k + 0.5) / 4 for k in range(4)]
    front = [x0 + span * (k + 1.0) / 4 for k in range(3)]
    out = []
    for k, x in enumerate(back):
        out.append((colours[k % len(colours)], x, 0.15, 0.6))
    for k, x in enumerate(front):
        out.append((colours[(k + 1) % len(colours)], x, -0.14, 0.48))
    return out


BEDS = [
    # id, length, flower colours (back row cycles through them, front row offset by one), boxwood ball
    ("flower_bed_a", 2.4, ["red", "pink"], True),
    ("flower_bed_b", 2.4, ["lilac", "pink", "orange"], True),
    ("flower_bed_c", 2.4, ["orange", "red"], True),
    ("flower_bed_d", 1.6, ["lilac", "red", "pink"], False),
]


def flower_bed(spec, plants, mats):
    bid, L, colours, with_ball = spec
    W = 0.8
    parts = [edging(L, W, mats, bid + "_edge"), mulch(L, W, mats, bid + "_mulch")]
    for k, (colour, x, y, h) in enumerate(bed_layout(colours, L, with_ball)):
        h *= 1.0 + rng.uniform(-0.08, 0.08)
        parts.append(plant_copy(plants, colour, (x + rng.uniform(-0.04, 0.04), y + rng.uniform(-0.03, 0.03), 0.035), h, rng.uniform(0, math.tau), "%s_p%d" % (bid, k)))
    # The boxwood ball at the +x end of the long beds is its own prop (boxwood_ball, placed by
    # CityLandscape.front_planting 0.88 m from the bed centre), so the bed stays two surfaces.
    o = join_meshes(parts, bid)
    H = verts_np(o.data)[:, 2].max()
    return o, {"height": float(H), "kind": "flower_bed", "length": L, "depth": W}


POTS = [("pot_geranium_red", "red", 0), ("pot_geranium_pink", "pink", 1), ("pot_geranium_lilac", "lilac", 2), ("pot_geranium_orange", "orange", 3)]


def pot_mesh(name, tile, mats):
    """Rolled-rim pot (lathe): 0.36 m tall, 0.4 m across the rim; soil disc inside."""
    prof = [(0.13, 0.0), (0.135, 0.01), (0.17, 0.27), (0.175, 0.28), (0.2, 0.285), (0.205, 0.3), (0.205, 0.345),
            (0.2, 0.36), (0.185, 0.36), (0.18, 0.345)]
    seg = 20
    verts, faces = [], []
    for (r, z) in prof:
        for s in range(seg):
            a = math.tau * s / seg
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(len(prof) - 1):
        for s in range(seg):
            a, b = i * seg + s, i * seg + (s + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    o = mesh_obj(name + "_pot", verts, faces, None, mats["pot"])
    smooth(o, 50)
    # UV: everything into the swatch tile
    tx, ty = (tile % 2) * 0.5, (tile // 2) * 0.5
    uvl = o.data.uv_layers.new(name="UVMap")
    for p in o.data.polygons:
        for li in p.loop_indices:
            co = o.data.vertices[o.data.loops[li].vertex_index].co
            ang = (math.atan2(co.y, co.x) / math.tau) % 1.0
            uvl.data[li].uv = (0.5 + (tx + 0.04 + 0.42 * ang) * 0.5, (ty + 0.04 + 0.42 * min(1.0, co.z / 0.36)) * 0.5)
    set_flat_vcol(o, 0, 0, 0, 1)
    soil = mesh_obj(name + "_soil", [(0.178 * math.cos(math.tau * s / seg), 0.178 * math.sin(math.tau * s / seg), 0.335) for s in range(seg)],
                    [tuple(range(seg))], None, mats["mulch"])
    planar_uv(soil, -0.2, 0.2, -0.2, 0.2, 0.3, 0.45, 0.6, 0.75)
    set_flat_vcol(soil, 0, 0, 0, 1)
    return [o, soil]


def potted(spec, plants, mats):
    pid, colour, tile = spec
    parts = pot_mesh(pid, tile, mats)
    parts.append(plant_copy(plants, colour, (0, 0, 0.30), 0.5, rng.uniform(0, math.tau), pid + "_plant"))
    o = join_meshes(parts, pid)
    H = verts_np(o.data)[:, 2].max()
    return o, {"height": float(H), "kind": "door_pot"}


# ----------------------------------------------------------------------------- QA
def qa_render(path, png):
    reset()
    bpy.ops.import_scene.gltf(filepath=path)
    sc = bpy.context.scene
    qa_neutral_vcols()
    objs = [o for o in sc.objects if o.type == "MESH"]
    x = 0.0
    for o in objs:
        co = np.array([o.matrix_world @ Vector(c) for c in o.bound_box])
        w = co[:, 0].max() - co[:, 0].min()
        o.location.x += x + w / 2 - (co[:, 0].max() + co[:, 0].min()) / 2
        x += w + 0.35
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    for m in bpy.data.materials:
        m.surface_render_method = "DITHERED"
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 1800, 700
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1); bg.inputs[1].default_value = 1.0
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(30)); sun.data.angle = 0.05
    gm = bpy.data.meshes.new("g"); gm.from_pydata([(-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0)], [], [(0, 1, 2, 3)])
    g = new_obj("ground", gm); gm.materials.append(make_material("ground", rgba=(0.2, 0.28, 0.12, 1)))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 35
    cx = x / 2
    for tag, loc, tx in [("front", (cx, -x * 1.0, x * 0.25), cx), ("close", (cx * 0.35, -2.6, 1.4), cx * 0.35),
                         ("pots", (x * 0.72, -2.4, 1.3), x * 0.72), ("hedge", (x * 0.93, -3.6, 1.7), x * 0.93)]:
        cam.location = loc
        tgt = Vector((tx, 0, 0.35))
        cam.rotation_euler = (tgt - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = png.replace(".png", "_%s.png" % tag)
        bpy.ops.render.render(write_still=True)


def main():
    p_dense, p_sheet = hedge_textures()
    plants, gmat = geranium_kit()
    mats = materials(p_dense, p_sheet)
    out = []
    for spec in BEDS:
        out.append(flower_bed(spec, plants, mats))
    for spec in POTS:
        out.append(potted(spec, plants, mats))
    out.append(boxwood_ball(mats))
    out.append(hedge_section(mats))
    for o, _ in plants.values():
        delete([o])
    report = {}
    for o, ex in out:
        ex["tris"] = tris(o.data)
        co = verts_np(o.data)
        ex["size"] = [round(float(v), 3) for v in (co.max(0) - co.min(0))]
        report[o.name] = dict(ex)
        ylog(o.name, json.dumps(ex))
    export_glb(out, OUT_GLB, "Yard")
    rp = os.path.join(QA, "landscape_report.json")
    old = json.load(open(rp)) if os.path.exists(rp) else {}
    old["yard"] = report
    json.dump(old, open(rp, "w"), indent=1)
    if DO_QA:
        qa_render(OUT_GLB, os.path.join(QA, "yard.png"))


main()
