"""Parks, monuments and sports assets for Delivery Simulator 2026.

Converts the raw Sketchfab GLBs in source_assets/incoming_2026_10_21/ (Godot-ignored) into
game-ready GLBs in assets/monuments/:

  ataturk_monument.glb    standing bronze Atatürk (mustafa_ataturk.glb) on a stepped granite plinth
  ataturk_equestrian.glb  equestrian Atatürk (mustafa_kemal_ataturk_horse_statue.glb): bronze +
                          granite pedestal, AO baked into vertex colours (the source has no textures)
  ataturk_bust.glb        park memorial wall with the bronze bust (busto_de_ataturk.glb), cropped
                          out of the scanned ground and set on a clean travertine platform
  sculpture_open_arms.glb / sculpture_stretch.glb
                          figure scans recast as park sculptures (bronze / brushed steel) on plinths
  statue_jenner.glb       the Edward Jenner statue scan (statue_in_hyde_park_london.glb)
  fountain_putti.glb      the Lužánky fountain with three putti (fountain_with_three_putts_...glb)
  basketball_court.glb    fenced street basketball court (street_basketball_court.glb)

Run headless (never on the live Blender session):
  blender --background --factory-startup --python tools/prepare_monuments.py -- [--only id,id] [--no-qa]

Conventions (as tools/prepare_prop_packs.py):
  * metres; Blender Z up / Godot Y up; transforms applied; origin at the footprint centre on the
    ground (min Z = 0). FRONT faces Blender -Y, which the glTF exporter turns into Godot +Z.
  * triangle budgets: sculptures <= 15k, fountain <= 20k, bust <= 10k; textures <= 2048.
    Godot generates the mesh LODs on import (meshes/generate_lods).
  * collision is not exported as geometry: assets/monuments/monuments.json lists simple boxes and
    cylinders (Godot coordinates relative to the asset origin) that CityMonuments builds.
  * QA renders (workbench, texture colour, 1.75 m reference figure) go to assets/monuments/qa/.
"""
import bpy, bmesh, sys, os, math, json, time, tempfile
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source_assets", "incoming_2026_10_21")
OUT = os.path.join(ROOT, "assets", "monuments")
QA = os.path.join(OUT, "qa")
TMP = tempfile.mkdtemp(prefix="monuments_")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY = set()
if "--only" in ARGS:
    ONLY = set(ARGS[ARGS.index("--only") + 1].split(","))
DO_QA = "--no-qa" not in ARGS
CATALOG = os.path.join(OUT, "monuments.json")
RESULTS = {}


def log(*a):
    print("[monuments]", *a, flush=True)


# ----------------------------------------------------------------------------- scene / mesh helpers

def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(name):
    t0 = time.time()
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, name))
    log("imported", name, "in %.1fs" % (time.time() - t0))
    return {o.name: o for o in bpy.context.scene.objects}


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def pts(obj):
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(obj.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def select_only(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def bake(objs, name, uv_from=None):
    """World-space static copy of the meshes, joined into one object (materials kept).
    uv_from: {object name: uv layer name} picks the UV layer each part keeps as 'UVMap'."""
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        if not me.polygons:
            continue
        me.transform(o.matrix_world)
        keep = (uv_from or {}).get(o.name)
        uvl = me.uv_layers
        if len(uvl):
            want = uvl.get(keep) if keep else uvl[0]
            if want is None:
                want = uvl[0]
            data = np.empty(len(me.loops) * 2)
            want.data.foreach_get("uv", data)
            while len(uvl):
                uvl.remove(uvl[0])
            nl = uvl.new(name="UVMap")
            nl.data.foreach_set("uv", data)
        else:
            uvl.new(name="UVMap")
        n = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(n)
        parts.append(n)
    if len(parts) > 1:
        select_only(parts)
        bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    return obj


def transform(obj, m):
    obj.data.transform(m)
    obj.data.update()


def ground(obj, centre=None):
    """Origin at the footprint centre (bbox xy, or `centre`) on the ground (min z = 0)."""
    p = pts(obj)
    lo, hi = p.min(0), p.max(0)
    c = centre if centre is not None else (lo[:2] + hi[:2]) * 0.5
    transform(obj, Matrix.Translation((-c[0], -c[1], -lo[2])))


def delete_faces(obj, keep):
    """keep(centroids[N,3], normals[N,3]) -> bool[N]; faces that fail are deleted."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    c = np.array([f.calc_center_median() for f in bm.faces])
    n = np.array([f.normal for f in bm.faces])
    k = keep(c, n)
    bmesh.ops.delete(bm, geom=[f for f, kk in zip(bm.faces, k) if not kk], context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def bisect(obj, co, no):
    """Cut along the plane and drop everything on the -no side."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_inner=True)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def decimate(obj, budget):
    if tris(obj) <= budget:
        return
    for _ in range(4):
        m = obj.modifiers.new("decimate", 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.ratio = max(0.005, budget / tris(obj) * 0.97)
        m.use_collapse_triangulate = True
        select_only([obj])
        bpy.ops.object.modifier_apply(modifier=m.name)
        if tris(obj) <= budget:
            break


def smooth(obj, angle=40):
    me = obj.data
    if me.has_custom_normals:
        select_only([obj])
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(angle))
    except AttributeError:
        pass


def weld(obj, dist=0.0005):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(obj.data)
    bm.free()


def box_mesh(name, parts, mat_index=0):
    """parts: [(centre (x,y,z), size (x,y,z), material_index), ...] -> one mesh object."""
    bm = bmesh.new()
    for c, s, mi in parts:
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((c[0] + v.co.x * s[0], c[1] + v.co.y * s[1], c[2] + v.co.z * s[2]))
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = mi
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    me.uv_layers.new(name="UVMap")
    return obj


def box_uv(obj, tile=1.2, faces=None):
    """World-planar UVs (dominant normal axis), `tile` metres per texture repeat."""
    me = obj.data
    uv = me.uv_layers[0].data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    for p in me.polygons:
        if faces is not None and not faces[p.index]:
            continue
        a = int(np.argmax(np.abs(p.normal)))
        ax = [(1, 2), (0, 2), (0, 1)][a]
        for li in p.loop_indices:
            v = co[me.loops[li].vertex_index]
            uv[li].uv = (v[ax[0]] / tile, v[ax[1]] / tile)


# ----------------------------------------------------------------------------- images / materials

def img_px(img, size=None):
    """Pixels as float32 [h, w, 4], downscaled in Blender first (box filter) when `size` is given."""
    if size and (img.size[0] > size[0] or img.size[1] > size[1]):
        img.scale(size[0], size[1])
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


_serial = [0]


def save_img(px, name, noncolor=False, alpha=False):
    h, w = px.shape[:2]
    tmp = bpy.data.images.new(name, w, h, alpha=True)
    if noncolor:
        tmp.colorspace_settings.name = 'Non-Color'
    tmp.pixels.foreach_set(np.ascontiguousarray(px, np.float32).ravel())
    name = name.replace(".", "_")
    # stable names: Godot extracts embedded images as <asset>_<image name>.<ext>
    path = os.path.join(TMP, "%s.%s" % (name, "png" if alpha else "jpg"))
    tmp.file_format = 'PNG' if alpha else 'JPEG'
    if not alpha:
        tmp.alpha_mode = 'NONE'
    tmp.filepath_raw = path
    try:
        bpy.context.scene.render.image_settings.quality = 90
    except Exception:
        pass
    tmp.save()
    bpy.data.images.remove(tmp)
    img = bpy.data.images.load(path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    if not alpha:
        img.alpha_mode = 'NONE'
    return img


def dilate(px, iters=12, floor=0.035):
    """Scan atlases sit on black: push island colours outwards into the background so the
    downscaled texture and the decimated (seam-crossing) triangles never sample black."""
    rgb = px[..., :3]
    valid = rgb.sum(-1) > floor
    out = rgb.copy()
    for _ in range(iters):
        acc = np.zeros_like(out)
        cnt = np.zeros(valid.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            v = np.roll(valid, (dy, dx), (0, 1))
            acc += np.roll(out, (dy, dx), (0, 1)) * v[..., None]
            cnt += v
        grow = (~valid) & (cnt > 0)
        out[grow] = acc[grow] / cnt[grow][:, None]
        valid = valid | grow
    px = px.copy()
    px[..., :3] = out
    return px


def resized(img, size, name, noncolor=False, alpha=False, pad=False, metal_scale=None):
    """Downscale to fit `size` (aspect kept, never up); pad: dilate islands (scan atlases);
    metal_scale: ORM maps whose source graph scaled the metallic (B) channel get it baked in."""
    w, h = img.size
    k = min(1.0, size[0] / w, size[1] / h)
    px = img_px(img, (max(4, int(w * k)), max(4, int(h * k))))
    if pad:
        px = dilate(px)
    if metal_scale is not None:
        px = px.copy()
        px[..., 2] *= metal_scale
    return save_img(px, name, noncolor, alpha)


def pbr(name, base=None, color=(0.8, 0.8, 0.8), metal=0.0, rough=0.5, orm=None, normal=None,
        normal_strength=1.0, mask=False):
    """Principled material in the shape the glTF exporter maps 1:1 (base colour [* factor],
    ORM image with G = roughness and B = metallic, tangent-space normal map, alpha MASK)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if base is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = base
        t.interpolation = 'Linear'
        if tuple(color) != (1, 1, 1):
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(t.outputs["Color"], mix.inputs[6])
            mix.inputs[7].default_value = (*color, 1.0)
            nt.links.new(mix.outputs[2], b.inputs["Base Color"])
        else:
            nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        if mask:
            lt = nt.nodes.new('ShaderNodeMath')
            lt.operation = 'LESS_THAN'
            lt.inputs[1].default_value = 0.5
            sub = nt.nodes.new('ShaderNodeMath')
            sub.operation = 'SUBTRACT'
            sub.inputs[0].default_value = 1.0
            nt.links.new(t.outputs["Alpha"], lt.inputs[0])
            nt.links.new(lt.outputs[0], sub.inputs[1])
            nt.links.new(sub.outputs[0], b.inputs["Alpha"])
            mat.surface_render_method = 'DITHERED'
    if orm is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = orm
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(t.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    if normal is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = normal
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return mat


def first_image(mat, socket):
    b = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    stack = [b.inputs[socket]] if b else []
    if b is None:  # unlit (emission) scans: the only image texture is the colour
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE':
                return n.image
        return None
    while stack:
        s = stack.pop()
        for l in s.links:
            if l.from_node.type == 'TEX_IMAGE':
                return l.from_node.image
            stack += list(l.from_node.inputs)
    return None


def set_materials(obj, mats):
    obj.data.materials.clear()
    for m in mats:
        obj.data.materials.append(m)


def tile_noise(n, scale, rng):
    """Tileable smooth noise in [-1, 1] (FFT low-pass of white noise), feature size ~ scale px."""
    f = np.fft.fftfreq(n)
    k = np.sqrt(f[:, None] ** 2 + f[None, :] ** 2)
    spec = np.fft.fft2(rng.standard_normal((n, n))) * np.exp(-(k * scale) ** 2)
    out = np.real(np.fft.ifft2(spec))
    return out / (np.abs(out).max() + 1e-9)


def stone_texture(name, base, seed, speckle=True, n=512):
    """Granite / travertine albedo: mottling plus dark and light grains, tileable."""
    rng = np.random.default_rng(seed)
    big = tile_noise(n, 40, rng)
    mid = tile_noise(n, 8, rng)
    px = np.ones((n, n, 4), np.float32)
    shade = 1.0 + 0.07 * big + 0.05 * mid
    rgb = np.array(base, np.float32)[None, None, :] * shade[..., None]
    if speckle:
        s = rng.random((n, n))
        dark = (s < 0.06).astype(np.float32)
        light = (s > 0.965).astype(np.float32)
        for arr in (dark, light):
            arr += 0.5 * (np.roll(arr, 1, 0) + np.roll(arr, 1, 1))
        rgb *= (1.0 - 0.45 * np.clip(dark, 0, 1))[..., None]
        rgb += 0.12 * np.clip(light, 0, 1)[..., None]
    else:  # travertine: horizontal pores
        pores = tile_noise(n, 2, rng)
        rgb *= (1.0 - 0.18 * np.clip(pores - 0.55, 0, 1) * 3)[..., None]
    px[..., :3] = np.clip(rgb, 0, 1)
    px = px[::-1]  # Blender stores bottom row first; orientation does not matter for stone
    return save_img(px, name)


GRANITE = (0.47, 0.46, 0.44)
TRAVERTINE = (0.71, 0.65, 0.55)


# ----------------------------------------------------------------------------- export / catalog / QA

def export(objs, aid, extras):
    root = bpy.data.objects.new(aid, None)
    bpy.context.scene.collection.objects.link(root)
    for o in objs:
        o.parent = root
    for k, v in extras.items():
        root[k] = v
    path = os.path.join(OUT, aid + ".glb")
    select_only([root] + objs, root)
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
              export_extras=True, export_animations=False, export_image_format='AUTO',
              export_materials='EXPORT', export_cameras=False, export_lights=False)
    try:
        bpy.ops.export_scene.gltf(export_vertex_color='ACTIVE', **kw)
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)
    allp = np.concatenate([pts(o) for o in objs])
    lo, hi = allp.min(0), allp.max(0)
    texs = sorted({"%s %dx%d" % (n.image.name, *n.image.size) for o in objs for s in o.material_slots if s.material
                   for n in s.material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image})
    entry = {"path": "res://assets/monuments/%s.glb" % aid,
             "tris": int(sum(tris(o) for o in objs)),
             # Godot axes: x width, y height, z depth
             "size": [round(float(hi[0] - lo[0]), 3), round(float(hi[2] - lo[2]), 3), round(float(hi[1] - lo[1]), 3)],
             "textures": texs, "file_kb": round(os.path.getsize(path) / 1024)}
    entry.update(extras)
    RESULTS[aid] = entry
    log("EXPORTED %-22s tris %6d size %s kb %d tex %s" % (aid, entry["tris"], entry["size"], entry["file_kb"], texs))
    if DO_QA:
        for o in bpy.context.scene.objects:   # only the exported asset appears in the QA sheet
            if o not in objs:
                o.hide_render = True
        qa_render(objs, aid, lo, hi)
    return root


def gbox(c, s):
    """Collision box from Blender centre/size to Godot (x, z, -y)."""
    return {"type": "box", "center": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)],
            "size": [round(s[0], 3), round(s[2], 3), round(s[1], 3)]}


def gcyl(c, r, h):
    return {"type": "cylinder", "center": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)], "radius": round(r, 3), "height": round(h, 3)}


def qa_render(objs, aid, lo, hi):
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_WORKBENCH'
    except TypeError:
        pass
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_backface_culling = False
    scene.render.resolution_x = scene.render.resolution_y = 640
    # 1.75 m reference figure (red) beside the asset
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.22, radius2=0.18, depth=1.45)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.725))
    r2 = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.13)
    bmesh.ops.translate(bm, verts=r2["verts"], vec=(0, 0, 1.6))
    me = bpy.data.meshes.new("ref")
    bm.to_mesh(me)
    bm.free()
    ref = bpy.data.objects.new("ref", me)
    rm = bpy.data.materials.new("ref")
    rm.diffuse_color = (0.85, 0.08, 0.06, 1)
    me.materials.append(rm)
    ref.location = (lo[0] - 0.6, lo[1] - 0.3, 0)
    scene.collection.objects.link(ref)
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = 'ORTHO'
    size = hi - lo
    span = float(max(size[0] + 1.6, size[1], size[2])) * 1.2
    cam.data.ortho_scale = span
    cam.data.clip_end = 2000
    centre = Vector(((lo[0] + hi[0]) * 0.5 - 0.4, (lo[1] + hi[1]) * 0.5, size[2] * 0.5))
    views = [("front", (0, -1, 0.12)), ("three_quarter", (0.8, -1, 0.5)), ("right", (1, 0, 0.12)),
             ("back", (0, 1, 0.12)), ("left", (-1, 0, 0.12)), ("rear_quarter", (-0.8, 1, 0.5)), ("top", (0, -0.001, 1))]
    tiles = []
    for vn, d in views:
        dv = Vector(d).normalized()
        cam.location = centre + dv * (span * 3)
        cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        f = os.path.join(TMP, "qa_%s_%s.png" % (aid, vn))
        scene.render.filepath = f
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(f)
        tiles.append(img_px(im)[..., :3].copy())
        bpy.data.images.remove(im)
    h, w = tiles[0].shape[:2]
    sheet = np.ones((h * 2, w * 4, 4), np.float32) * 0.12
    for i, t in enumerate(tiles):
        r, c = divmod(i, 4)
        sheet[(1 - r) * h:(2 - r) * h, c * w:(c + 1) * w, :3] = t  # pixel rows are bottom-up
    os.makedirs(QA, exist_ok=True)
    tmp = bpy.data.images.new("sheet", w * 4, h * 2, alpha=True)
    tmp.pixels.foreach_set(sheet.ravel())
    tmp.filepath_raw = os.path.join(QA, aid + ".png")
    tmp.file_format = 'PNG'
    tmp.save()
    bpy.data.images.remove(tmp)
    for o in (cam, ref):
        bpy.data.objects.remove(o)


# ----------------------------------------------------------------------------- bronze texture repair

def bronze_atlas(px, patch):
    """Photogrammetry atlas of a bronze statue: every non-bronze pixel (bright stone, foliage,
    white seam fills) becomes bronze with the original's luminance detail; `patch` (u0, v0, u1, v1)
    is painted plain bronze for the untextured seam strips. Returns (pixels, mean bronze)."""
    rgb = px[..., :3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    good = (lum < 0.16) & (lum > 0.012) & (rgb[..., 0] >= rgb[..., 1] * 0.98) & (rgb[..., 0] >= rgb[..., 2])
    mean = rgb[good].mean(0)
    mlum = float(lum[good].mean())
    # detail: high-passed luminance (local contrast), clamped
    blur = lum.copy()
    for _ in range(3):
        blur = (blur + np.roll(blur, 2, 0) + np.roll(blur, -2, 0) + np.roll(blur, 2, 1) + np.roll(blur, -2, 1)) / 5.0
    detail = np.clip((lum - blur) * 1.6, -0.35, 0.35)
    fill = mean[None, None, :] * (1.0 + detail[..., None] * 2.0)
    bad = ~good
    out = rgb.copy()
    out[bad] = fill[bad]
    # a little warmth variation so the fill is not flat
    h, w = lum.shape
    u0, v0, u1, v1 = patch
    ys, ye = int(v0 * h), int(v1 * h)
    xs, xe = int(u0 * w), int(u1 * w)
    rng = np.random.default_rng(7)
    n = tile_noise(max(ye - ys, xe - xs), 6, rng)
    out[ys:ye, xs:xe] = mean[None, None, :] * (1.0 + 0.18 * n[:ye - ys, :xe - xs, None])
    # the scan's bronze is near-black and slightly violet: re-grade it to a warm statuary bronze
    target = np.array([0.30, 0.215, 0.145], np.float32)
    out = out * (target / mean)[None, None, :]
    px = px.copy()
    px[..., :3] = np.clip(out, 0, 1)
    return px, mean, mlum


# ============================================================================= assets

def plinth_square(granite, bronze_plain):
    """Atatürk Square plinth: three granite steps, moulded pedestal, bronze cornice band and an
    inscription panel on the front (-Y) face. Pedestal front face at y = -1.3."""
    parts = []
    z = 0.0
    for w in (7.0, 5.8, 4.6):
        parts.append(((0, 0, z + 0.15), (w, w, 0.3), 0))
        z += 0.3
    parts.append(((0, 0, z + 0.12), (3.1, 3.1, 0.24), 0))       # base moulding
    z += 0.24
    parts.append(((0, 0, z + 1.45), (2.6, 2.6, 2.9), 0))        # shaft
    parts.append(((0, -1.3, z + 1.2), (1.7, 0.04, 1.0), 1))     # inscription panel (bronze)
    z += 2.9
    parts.append(((0, 0, z + 0.07), (2.95, 2.95, 0.14), 1))     # bronze cornice band
    z += 0.14
    parts.append(((0, 0, z + 0.1), (2.75, 2.75, 0.2), 0))       # cap slab
    z += 0.2
    obj = box_mesh("MonumentPlinth", parts)
    set_materials(obj, [granite, bronze_plain])
    box_uv(obj, 1.3)
    return obj, z


def build_ataturk_monument():
    new_scene()
    by = import_glb("mustafa_ataturk.glb")
    src = by["Object_5"].data.materials[0]
    atlas = first_image(src, "Base Color")
    px = img_px(atlas, (2048, 1024))
    patch = (0.62, 0.62, 0.98, 0.98)   # empty grey corner of the atlas -> plain bronze
    px, mean, mlum = bronze_atlas(px, patch)
    log("bronze mean", mean, "lum", mlum)
    tex = save_img(px, "ataturk_bronze")
    bronze = pbr("AtaturkBronze", tex, (1, 1, 1), metal=0.55, rough=0.42)
    # Seam fills (Object_2 / Object_4) and the cast base (Object_3) are untextured: map them into
    # the plain bronze patch with a planar projection so they read as the same metal.
    fig = bake([by["Object_5"], by["Object_3"], by["Object_2"], by["Object_4"]], "AtaturkFigure")
    # Faces from the untextured parts are the ones with material GeneratedMat4 (slot 1).
    mats = [s.material.name if s.material else "" for s in fig.material_slots]
    me = fig.data
    uv = me.uv_layers[0].data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    for p in me.polygons:
        if mats[p.material_index] != src.name:
            for li in p.loop_indices:
                v = co[me.loops[li].vertex_index]
                fu = (v[0] * 0.05 + v[2] * 0.031) % 1.0
                fv = (v[1] * 0.05 + v[2] * 0.017) % 1.0
                uv[li].uv = (patch[0] + 0.02 + fu * (patch[2] - patch[0] - 0.04),
                             patch[1] + 0.02 + fv * (patch[3] - patch[1] - 0.04))
            p.material_index = 0
    set_materials(fig, [bronze])
    # Real scale: the figure (with its cast base) stands 4.8 m; it faces source -X -> turn to -Y.
    p = pts(fig)
    s = 4.8 / float(p[:, 2].max() - p[:, 2].min())
    transform(fig, Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Diagonal((s, s, s, 1)))
    # centre on the cast base (lowest 4 %)
    p = pts(fig)
    z0 = p[:, 2].min()
    base = p[p[:, 2] < z0 + 0.04 * (p[:, 2].max() - z0)]
    ground(fig, (base[:, :2].min(0) + base[:, :2].max(0)) * 0.5)
    decimate(fig, 14000)
    smooth(fig, 50)
    granite = pbr("Granite", stone_texture("granite", GRANITE, 11), (1, 1, 1), rough=0.62)
    plain = pbr("BronzePlaque", None, (0.16, 0.10, 0.06), metal=0.8, rough=0.38)
    plinth, top = plinth_square(granite, plain)
    p = pts(fig)
    foot = p[:, :2].min(0), p[:, :2].max(0)
    log("figure footprint", foot, "height", p[:, 2].max())
    transform(fig, Matrix.Translation((0, 0, top - 0.03)))
    total = top + 4.8
    col = [gbox((0, 0, 0.15), (7.0, 7.0, 0.3)), gbox((0, 0, 0.45), (5.8, 5.8, 0.3)), gbox((0, 0, 0.75), (4.6, 4.6, 0.3)),
           gbox((0, 0, 0.9 + (top - 0.9) * 0.5), (2.95, 2.95, top - 0.9)),
           gbox((0, 0, top + 2.4), (1.3, 1.1, 4.8))]
    export([plinth, fig], "ataturk_monument", {
        "kind": "monument", "source": "mustafa_ataturk.glb", "height": round(total, 3), "plinth_top": round(top, 3),
        "panel_front_z": 1.32, "panel_centre_y": round(0.9 + 0.24 + 1.2, 3), "collision": col})


def build_equestrian():
    new_scene()
    by = import_glb("mustafa_kemal_ataturk_horse_statue.glb")
    obj = bake([by["model.001"]], "EquestrianStatue")
    # Real scale: 1.9 m model -> 8.6 m monument (horse and rider ~4.3 m on a 4.3 m pedestal).
    s = 4.5
    transform(obj, Matrix.Diagonal((s, s, s, 1)))
    ground(obj)
    p = pts(obj)
    log("equestrian size", p.max(0) - p.min(0))
    # The pedestal steps end at source z ~ 0.0 (0.948 above the base) -> above that is bronze.
    split = 0.95 * s
    decimate(obj, 15000)
    weld(obj)
    smooth(obj, 35)
    me = obj.data
    granite = pbr("Granite", stone_texture("granite", GRANITE, 11), (1, 1, 1), rough=0.6)
    bronze = pbr("EquestrianBronze", None, (1, 1, 1), metal=0.75, rough=0.4)
    set_materials(obj, [granite, bronze])
    upper = np.zeros(len(me.polygons), bool)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    for poly in me.polygons:
        c = poly.center
        upper[poly.index] = c.z > split
        poly.material_index = 1 if upper[poly.index] else 0
    box_uv(obj, 1.3, ~upper)
    # Ambient occlusion -> vertex colours (bronze: patina in the hollows; granite: soft contact shadow)
    ao = bake_ao(obj)
    for a in list(me.color_attributes):
        me.color_attributes.remove(a)
    attr = me.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
    bronze_hi = np.array([0.36, 0.24, 0.13])
    bronze_lo = np.array([0.10, 0.075, 0.05])
    patina = np.array([0.16, 0.23, 0.19])
    stone = np.array([1.0, 1.0, 1.0])
    cols = np.zeros((len(me.loops), 4), np.float32)
    for poly in me.polygons:
        for li in poly.loop_indices:
            a = ao[li]
            if upper[poly.index]:
                c = bronze_lo + (bronze_hi - bronze_lo) * a ** 1.4
                c = c + (patina - c) * max(0.0, 0.55 - a) * 0.9
            else:
                c = stone * (0.45 + 0.55 * a ** 0.8)
            cols[li, :3] = c
            cols[li, 3] = 1
    attr.data.foreach_set("color", cols.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.active_color_index = 0
    me.color_attributes.render_color_index = 0
    p = pts(obj)
    lo, hi = p.min(0), p.max(0)
    # pedestal block collision (the block is 0.52 x 0.86 source = 2.34 x 3.87) + steps + statue
    lower = p[p[:, 2] < split * 0.5]
    plo, phi = lower.min(0), lower.max(0)
    col = [gbox(((plo[0] + phi[0]) / 2, (plo[1] + phi[1]) / 2, split * 0.5), (phi[0] - plo[0], phi[1] - plo[1], split)),
           gbox((0, 0, split + 2.0), (1.4, 3.2, 4.0))]
    export([obj], "ataturk_equestrian", {"kind": "monument", "source": "mustafa_kemal_ataturk_horse_statue.glb",
                                          "height": round(float(hi[2]), 3), "pedestal_top": round(split, 3), "collision": col})


def bake_ao(obj):
    """Per-loop ambient occlusion in [0, 1] (Cycles AO bake to a colour attribute)."""
    me = obj.data
    scene = bpy.context.scene
    try:
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 64
        attr = me.color_attributes.new("AO", 'FLOAT_COLOR', 'CORNER')
        me.color_attributes.active_color = attr
        mats = [s.material for s in obj.material_slots]
        select_only([obj])
        bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
        c = np.empty(len(me.loops) * 4, np.float32)
        attr.data.foreach_get("color", c)
        ao = c.reshape(-1, 4)[:, 0].copy()
        me.color_attributes.remove(attr)
        log("AO baked: mean %.2f min %.2f" % (ao.mean(), ao.min()))
        return np.clip(ao / max(0.2, float(np.percentile(ao, 95))), 0, 1)
    except Exception as e:  # fall back to flat
        log("AO bake failed:", e)
        return np.ones(len(me.loops), np.float32)


def build_bust():
    new_scene()
    by = import_glb("busto_de_ataturk.glb")
    obj = bake([by["Object_5"]], "AtaturkBustMemorial")
    src = obj.data.materials[0]
    tex = resized(first_image(src, "Base Color"), (2048, 2048), "bust_scan", pad=True)
    # Crop: the scanned pavement (below z 0.2), the pole and the litter right of the wall (x > 1.97),
    # and the ragged pavement ends.
    bisect(obj, (0, 0, 0.2), (0, 0, 1))
    delete_faces(obj, lambda c, n: (c[:, 0] < 1.94) & (c[:, 0] > -1.62) & (c[:, 1] > -0.6))
    decimate(obj, 9500)
    smooth(obj, 35)
    trav = pbr("Travertine", stone_texture("travertine", TRAVERTINE, 5, speckle=False), (1, 1, 1), rough=0.7)
    scan = pbr("BustScan", tex, (1, 1, 1), metal=0.0, rough=0.62)
    set_materials(obj, [scan])
    p = pts(obj)
    lo, hi = p.min(0), p.max(0)
    log("bust crop", lo, hi)
    # Clean platform under the wall and pillar, a step in front.
    x0, x1 = lo[0] - 0.12, hi[0] + 0.12
    y0, y1 = -0.95, hi[1] + 0.12
    plat = box_mesh("MemorialPlatform", [(((x0 + x1) / 2, (y0 + y1) / 2, 0.11), (x1 - x0, y1 - y0, 0.22), 0)])
    set_materials(plat, [trav])
    box_uv(plat, 1.1)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for o in (obj, plat):
        transform(o, Matrix.Translation((-cx, -cy, 0)))
    p = pts(obj)
    wall = p[p[:, 2] > 0.4]
    wl, wh = wall.min(0), wall.max(0)
    col = [gbox((0, 0, 0.11), (x1 - x0, y1 - y0, 0.22)),
           gbox(((wl[0] + wh[0]) / 2, (wl[1] + wh[1]) / 2, 0.9), (wh[0] - wl[0], wh[1] - wl[1], 1.4))]
    export([plat, obj], "ataturk_bust", {"kind": "memorial", "source": "busto_de_ataturk.glb",
                                         "height": round(float(p[:, 2].max()), 3), "collision": col})


def build_sculpture(srcname, aid, finish):
    new_scene()
    by = import_glb(srcname)
    meshes = [o for o in by.values() if o.type == 'MESH']
    obj = bake(meshes, aid)
    src = obj.data.materials[0]
    base = img_px(first_image(src, "Base Color"), (1024, 1024))
    # recast as metal: luminance detail through the finish's colour ramp
    lum = base[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lum = (lum - lum.min()) / max(1e-6, float(np.percentile(lum, 99.5) - lum.min()))
    lo_c, hi_c = np.array(finish["dark"], np.float32), np.array(finish["light"], np.float32)
    rgb = lo_c + (hi_c - lo_c) * np.clip(lum, 0, 1)[..., None] ** 0.75
    px = base.copy()
    px[..., :3] = rgb
    tex = save_img(px, aid + "_metal")
    mat = pbr(finish["name"], tex, (1, 1, 1), metal=finish["metal"], rough=finish["rough"])
    set_materials(obj, [mat])
    weld(obj)
    decimate(obj, 12000)
    smooth(obj, 50)
    ground(obj)
    p = pts(obj)
    feet = p[p[:, 2] < 0.08]
    cxy = (feet[:, :2].min(0) + feet[:, :2].max(0)) * 0.5
    transform(obj, Matrix.Translation((-cxy[0], -cxy[1], 0.55)))
    granite = pbr("Granite", stone_texture("granite", GRANITE, 11), (1, 1, 1), rough=0.6)
    plinth = box_mesh("SculpturePlinth", [((0, 0, 0.04), (1.25, 1.25, 0.08), 0), ((0, 0, 0.3), (1.0, 1.0, 0.5), 0)])
    set_materials(plinth, [granite])
    box_uv(plinth, 1.1)
    h = float(pts(obj)[:, 2].max())
    col = [gbox((0, 0, 0.3), (1.0, 1.0, 0.6)), gbox((0, 0, 0.55 + (h - 0.55) * 0.5), (0.5, 0.4, h - 0.55))]
    export([plinth, obj], aid, {"kind": "sculpture", "source": srcname, "height": round(h, 3), "collision": col})


def build_jenner():
    new_scene()
    by = import_glb("statue_in_hyde_park_london.glb")
    meshes = [o for o in by.values() if o.type == 'MESH']
    obj = bake(meshes, "JennerStatue")
    src = obj.data.materials[0]
    tex = resized(first_image(src, "Base Color"), (2048, 2048), "jenner_scan", pad=True)
    p = pts(obj)
    z0 = p[:, 2].min()
    # drop the scanned ground: cut 0.2 m above the lowest point, keep the plinth and balustrade
    bisect(obj, (0, 0, z0 + 0.2), (0, 0, 1))
    decimate(obj, 15000)
    smooth(obj, 35)
    mat = pbr("JennerScan", tex, (1, 1, 1), rough=0.65)
    set_materials(obj, [mat])
    ground(obj)
    transform(obj, Matrix.Translation((0, 0, 0.06)))   # ragged scan foot sinks into the slab
    p = pts(obj)
    lo, hi = p.min(0), p.max(0)
    # pedestal is the central block (x ~ -1.2..0.4 source); find it from the 1.0-1.5 m band
    band = p[(p[:, 2] > 1.0) & (p[:, 2] < 1.5)]
    blo, bhi = band.min(0), band.max(0)
    ctr = ((blo[0] + bhi[0]) / 2, (blo[1] + bhi[1]) / 2)
    transform(obj, Matrix.Translation((-ctr[0], -ctr[1], 0)))
    p = pts(obj)
    lo, hi = p.min(0), p.max(0)
    low = p[p[:, 2] < 1.0]
    llo, lhi = low.min(0), low.max(0)
    slab = box_mesh("JennerSlab", [(((llo[0] + lhi[0]) / 2, (llo[1] + lhi[1]) / 2, 0.06),
                                    (lhi[0] - llo[0] + 0.3, lhi[1] - llo[1] + 0.3, 0.12), 0)])
    set_materials(slab, [pbr("Granite", stone_texture("granite", (0.56, 0.55, 0.52), 13), (1, 1, 1), rough=0.65)])
    box_uv(slab, 1.2)
    col = [gbox(((llo[0] + lhi[0]) / 2, (llo[1] + lhi[1]) / 2, 0.5), (lhi[0] - llo[0], lhi[1] - llo[1], 1.0)),
           gbox((0, 0, 1.6), (bhi[0] - blo[0], bhi[1] - blo[1], 3.2))]
    export([slab, obj], "statue_jenner", {"kind": "statue", "source": "statue_in_hyde_park_london.glb",
                                     "height": round(float(hi[2]), 3), "collision": col})


def build_fountain():
    new_scene()
    by = import_glb("fountain_with_three_putts_brno_luzanky.glb")
    meshes = [o for o in by.values() if o.type == 'MESH']
    obj = bake(meshes, "PuttiFountain")
    src = obj.data.materials[0]
    base = resized(first_image(src, "Base Color"), (2048, 2048), "fountain_base", pad=True)
    orm = resized(first_image(src, "Roughness"), (1024, 1024), "fountain_orm", noncolor=True, metal_scale=0.0)
    nrm = resized(first_image(src, "Normal"), (2048, 2048), "fountain_normal", noncolor=True)
    mat = pbr("FountainStone", base, (1, 1, 1), orm=orm, normal=nrm)
    set_materials(obj, [mat])
    weld(obj)
    decimate(obj, 18000)
    smooth(obj, 45)
    p = pts(obj)
    lo, hi = p.min(0), p.max(0)
    # basin centre from the outermost ring
    rim = p[p[:, 2] < lo[2] + 0.2]
    c = (rim[:, :2].min(0) + rim[:, :2].max(0)) * 0.5
    transform(obj, Matrix.Translation((-c[0], -c[1], -lo[2])))
    p = pts(obj)
    r = np.hypot(p[:, 0], p[:, 1])
    R = float(r.max())
    # radial profile: rim top and the basin floor just inside it
    prof = []
    for k in range(40):
        a, b = R * k / 40, R * (k + 1) / 40
        sel = p[(r >= a) & (r < b)]
        prof.append((round(a, 2), round(float(sel[:, 2].max()), 3) if len(sel) else None, round(float(sel[:, 2].min()), 3) if len(sel) else None))
    log("fountain radius %.2f profile" % R, prof)
    rim_band = p[r > R - 0.12]
    rim_top = float(np.percentile(rim_band[:, 2], 90))
    # The scan has no hollow basin: the putti rocks stand on a solid 0.23 m drum with drain
    # grates. The water is a shallow film just over the drum top, the rocks rising through it.
    water = rim_top + 0.012
    inner = R - 0.09
    col = [gcyl((0, 0, rim_top * 0.5), R, rim_top), gcyl((0, 0, 1.3), 0.75, 2.6)]
    export([obj], "fountain_putti", {"kind": "fountain", "source": "fountain_with_three_putts_brno_luzanky.glb",
                                     "height": round(float(p[:, 2].max()), 3), "radius": round(R, 3), "rim_top": round(rim_top, 3),
                                     "water_y": round(water, 3), "water_radius": round(inner, 3), "collision": col})


def mapping_of(mat):
    """(uv map name, scale xy) used by the material's colour texture (UV Map / Mapping nodes)."""
    uvname, scale = None, (1.0, 1.0)
    for n in mat.node_tree.nodes:
        if n.type == 'UVMAP':
            uvname = n.uv_map
        if n.type == 'MAPPING':
            s = n.inputs['Scale'].default_value
            scale = (s[0], s[1])
    return uvname, scale


GATE = (-5.75, -4.45)   # court gate opening (x, centred court coordinates)


def build_court():
    new_scene()
    by = import_glb("street_basketball_court.glb")
    meshes = [o for o in by.values() if o.type == 'MESH']
    groups = {"CourtSurface": [], "CourtFence": [], "CourtHoops": [], "CourtNets": []}
    uv_from = {}
    scales = {}
    for o in meshes:
        m = o.data.materials[0]
        uvname, scale = mapping_of(m)
        if m.name in ("M_Fence", "BCourt_Markngs"):
            uvname = "UVMap.001"   # their first UV set is degenerate; the textures belong to the 2nd
        uv_from[o.name] = uvname
        scales[o.name] = scale
        g = ("CourtSurface" if m.name in ("Concrete", "BCourt_Markngs") else
             "CourtFence" if m.name in ("Light_iron", "M_Fence") else
             "CourtNets" if m.name.startswith("rope") else "CourtHoops")
        groups[g].append(o)
    # materials, rebuilt once each with resized maps
    newmat = {}
    for o in meshes:
        m = o.data.materials[0]
        if m.name in newmat:
            continue
        base = first_image(m, "Base Color")
        rough = first_image(m, "Roughness")
        nrm = first_image(m, "Normal")
        size = {"M_Hoop": 1024, "Light_iron": 1024, "M_Fence": 1024, "Concrete": 2048, "BCourt_Markngs": 2048}.get(m.name, 512)
        alpha = m.name in ("M_Fence", "BCourt_Markngs")
        b = resized(base, (size, size), "court_" + m.name, alpha=alpha) if base else None
        metal = {"Concrete": 0.0, "M_Hoop": 0.706}.get(m.name)   # the source's Math multiply on metallic
        orm = resized(rough, (size // 2, size // 2), "court_%s_orm" % m.name, noncolor=True, metal_scale=metal) if rough else None
        nm = resized(nrm, (size // 2, size // 2), "court_%s_nrm" % m.name, noncolor=True) if nrm else None
        newmat[m.name] = pbr("Court_" + m.name, b, (1, 1, 1), orm=orm, normal=nm, mask=alpha,
                             rough=0.9 if m.name.startswith("rope") else 0.6)
    out = []
    for g, objs in groups.items():
        if not objs:
            continue
        # bake the Mapping node scale into each part's UVs before joining
        parts = []
        for o in objs:
            mname = o.data.materials[0].name
            part = bake([o], g + "_part", {o.name: uv_from[o.name]})
            sx, sy = scales[o.name]
            if (sx, sy) != (1.0, 1.0):
                uvd = np.empty(len(part.data.loops) * 2)
                part.data.uv_layers[0].data.foreach_get("uv", uvd)
                uvd = uvd.reshape(-1, 2) * np.array([sx, sy])
                part.data.uv_layers[0].data.foreach_set("uv", uvd.ravel())
            set_materials(part, [newmat[mname]])
            parts.append(part)
        if len(parts) > 1:
            select_only(parts)
            bpy.ops.object.join()
        obj = parts[0]
        obj.name = g
        obj.data.name = g
        budget = {"CourtFence": 9000, "CourtHoops": 5000, "CourtNets": 3000, "CourtSurface": 100}[g]
        # Keep the flat chain-link quads intact: decimate only the iron frame.
        if g == "CourtFence":
            iron = [i for i, s in enumerate(obj.material_slots) if s.material.name == "Court_Light_iron"]
            vg = obj.vertex_groups.new(name="iron")
            ids = {v for p in obj.data.polygons if p.material_index in iron for v in p.vertices}
            vg.add(list(ids), 1.0, 'REPLACE')
            m = obj.modifiers.new("decimate", 'DECIMATE')
            m.ratio = budget / tris(obj)
            m.vertex_group = "iron"
            m.use_collapse_triangulate = True
            select_only([obj])
            bpy.ops.object.modifier_apply(modifier=m.name)
            obj.vertex_groups.clear()
        else:
            decimate(obj, budget)
        out.append(obj)
    # markings plane sits on the concrete: lift it 8 mm so it never z-fights
    surf = next(o for o in out if o.name == "CourtSurface")
    me = surf.data
    mk = [i for i, s in enumerate(surf.material_slots) if s.material.name == "Court_BCourt_Markngs"]
    for poly in me.polygons:
        if poly.material_index in mk:
            for v in poly.vertices:
                me.vertices[v].co.z += 0.008
    allp = np.concatenate([pts(o) for o in out])
    lo, hi = allp.min(0), allp.max(0)
    c = (lo[:2] + hi[:2]) * 0.5
    for o in out:
        transform(o, Matrix.Translation((-c[0], -c[1], -lo[2])))
        smooth(o, 40)
    allp = np.concatenate([pts(o) for o in out])
    lo, hi = allp.min(0), allp.max(0)
    fence = pts(next(o for o in out if o.name == "CourtFence"))
    flo, fhi = fence.min(0), fence.max(0)
    hoops = pts(next(o for o in out if o.name == "CourtHoops"))
    log("court bounds", lo, hi, "fence", flo, fhi)
    H = 3.9
    t = 0.12
    col = [gbox(((flo[0] + fhi[0]) / 2, flo[1] + 0.06, H / 2), (fhi[0] - flo[0], t, H)),   # back fence
           gbox((flo[0] + 0.06, (flo[1] + fhi[1]) / 2, H / 2), (t, fhi[1] - flo[1], H)),   # side fences
           gbox((fhi[0] - 0.06, (flo[1] + fhi[1]) / 2, H / 2), (t, fhi[1] - flo[1], H))]
    # front fence (+y) in two runs either side of the gate opening (GATE, x range)
    front_y = float(np.median(fence[(fence[:, 1] > (flo[1] + fhi[1]) / 2) & (fence[:, 2] > 3.0)][:, 1]))
    g0, g1 = GATE
    for a, b in ((flo[0], g0), (g1, fhi[0])):
        col.append(gbox(((a + b) / 2, front_y, H / 2), (b - a, t, H)))
    for side in (-1, 1):
        sel = hoops[(hoops[:, 1] * side > 0) & (hoops[:, 2] < 1.0)]
        if len(sel):
            pl, ph = sel.min(0), sel.max(0)
            col.append(gbox(((pl[0] + ph[0]) / 2, (pl[1] + ph[1]) / 2, 1.5), (max(0.25, ph[0] - pl[0]), max(0.25, ph[1] - pl[1]), 3.0)))
    export(out, "basketball_court", {"kind": "court", "source": "street_basketball_court.glb",
                                     "fence": [round(float(flo[0]), 3), round(float(-fhi[1]), 3), round(float(fhi[0]), 3), round(float(-flo[1]), 3)],
                                     "front_fence_y": round(front_y, 3), "collision": col})


ASSETS = {
    "ataturk_monument": build_ataturk_monument,
    "ataturk_equestrian": build_equestrian,
    "ataturk_bust": build_bust,
    "sculpture_open_arms": lambda: build_sculpture("open_arms_in_the_park.glb", "sculpture_open_arms",
                                                   {"name": "PolishedBronze", "dark": (0.08, 0.045, 0.02), "light": (0.62, 0.42, 0.22), "metal": 0.9, "rough": 0.32}),
    "sculpture_stretch": lambda: build_sculpture("park_stretch.glb", "sculpture_stretch",
                                                 {"name": "BrushedSteel", "dark": (0.22, 0.23, 0.24), "light": (0.78, 0.79, 0.80), "metal": 0.95, "rough": 0.3}),
    "statue_jenner": build_jenner,
    "fountain_putti": build_fountain,
    "basketball_court": build_court,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(QA, exist_ok=True)
    gd = os.path.join(QA, ".gdignore")
    if not os.path.exists(gd):
        open(gd, "w").close()
    old = {}
    if os.path.exists(CATALOG):
        with open(CATALOG) as f:
            old = json.load(f).get("assets", {})
    for aid, fn in ASSETS.items():
        if ONLY and aid not in ONLY:
            continue
        t0 = time.time()
        fn()
        log("built", aid, "in %.1fs" % (time.time() - t0))
    old.update(RESULTS)
    with open(CATALOG, "w") as f:
        json.dump({"convention": "metres, origin at footprint centre on the ground, front +Z (Godot); "
                                 "collision boxes/cylinders in Godot coordinates relative to the origin",
                   "assets": old}, f, indent=1, ensure_ascii=False)
    log("catalog", CATALOG)


main()
