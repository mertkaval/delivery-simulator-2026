"""Build the delivery-game assets (glyphs, food packages, courier bag) procedurally and export GLBs.

Run headless (never in the user's live Blender, it resets the scene between assets):
  "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background --factory-startup \
      --python tools/build_delivery_assets.py [-- --only glyphs,food_bag,pizza_box,drink_carrier,delivery_bag] [--no-qa]

Output (assets/delivery/):
  glyphs.glb              glyph_A..glyph_Z, glyph_0..glyph_9, glyph_dash/dot/slash/amp/space + number_plate
  food_bag.glb            kraft takeaway bag
  pizza_box.glb           corrugated pizza box
  drink_carrier.glb       two-cup carrier box
  delivery_bag.glb        insulated courier backpack, lid closed
  delivery_bag_open.glb   same bag, lid open 110 deg, two removable dividers
  qa/<name>.png           workbench front three-quarter renders (10 cm red reference cube), glyph sheet
  qa/build_report.json    tri counts, extras, glyph metrics

Conventions:
  * metres; Blender Z up. glTF export maps Blender +Y forward to Godot -Z, so every asset's FRONT
    faces Blender -Y = Godot +Z. Origins at the bottom centre (packages, bag).
  * Extras written on package/bag root nodes are in GODOT local coordinates (Y up, front +Z):
    Blender (x, y, z) -> Godot (x, z, -y). Godot exposes them as node metadata "extras".
  * LogoPanel / ReceiptTag nodes are oriented so their Godot local +Z is the panel's outward normal and
    local +Y is the text "up" direction (a Label3D child with identity transform reads correctly);
    their meshes carry 0..1 UVs (u right, v up).
  * Glyph nodes: identity transform; pen origin (left side bearing reference) at x=0, baseline/bottom of
    flat glyphs at z=0, cap height exactly 1.0, back face at y=0, front face toward -Y.
"""
import bpy, bmesh, os, sys, math, json, tempfile
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "delivery")
QA = os.path.join(OUT, "qa")
TMP = tempfile.mkdtemp(prefix="delivery_assets_")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY = set()
if "--only" in ARGS and ARGS.index("--only") + 1 < len(ARGS):
    ONLY = set(ARGS[ARGS.index("--only") + 1].split(","))
DO_QA = "--no-qa" not in ARGS
REPORT = {}


def log(*a):
    print("[delivery]", *a, flush=True)


def wanted(name):
    return not ONLY or name in ONLY


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def lin(c):
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def gd(v):
    """Blender vector -> Godot local coordinates (rounded list)."""
    return [round(float(v[0]), 5) + 0.0, round(float(v[2]), 5) + 0.0, round(float(-v[1]), 5) + 0.0]


def gd_size(s):
    return [round(float(s[0]), 5), round(float(s[2]), 5), round(float(s[1]), 5)]


# ----------------------------------------------------------------------------- materials / textures
def image_from(name, rgb):
    """rgb: (h, w, 3) float sRGB array, row 0 = bottom (v = 0). Saved to a temp PNG and made file-backed
    (the glTF exporter re-encodes GENERATED images with a double sRGB conversion)."""
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = np.clip(rgb, 0.0, 1.0)
    img.pixels.foreach_set(px.ravel())
    path = os.path.join(TMP, name + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    img.source = 'FILE'
    img.filepath = path
    img.reload()
    return img


def material(name, srgb, rough=0.5, metal=0.0, image=None):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    c = lin(srgb)
    bsdf.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    m.diffuse_color = (c[0], c[1], c[2], 1.0)
    m.roughness = rough
    m.metallic = metal
    if image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = image
        tex.location = (-420, 220)
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        nt.nodes.active = tex
    return m


def value_noise(h, w, cy, cx, rng):
    g = rng.random((cy + 1, cx + 1))
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    y = np.arange(h) * cy / h
    x = np.arange(w) * cx / w
    iy = y.astype(int)
    ix = x.astype(int)
    fy = y - iy
    fx = x - ix
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[np.ix_(iy, ix)]
    b = g[np.ix_(iy, ix + 1)]
    c = g[np.ix_(iy + 1, ix)]
    d = g[np.ix_(iy + 1, ix + 1)]
    top = a + (b - a) * fx[None, :]
    bot = c + (d - c) * fx[None, :]
    return top + (bot - top) * fy[:, None]


def paper_rgb(base, seed, size=256, blotch=0.07, fibre=0.06, grain=0.03, ripple=0.0):
    rng = np.random.default_rng(seed)
    n = (value_noise(size, size, 4, 4, rng) - 0.5) * blotch * 1.5
    n += (value_noise(size, size, 16, 16, rng) - 0.5) * blotch
    n += (value_noise(size, size, 96, 6, rng) - 0.5) * fibre * 2.0       # streaky fibres along u
    n += (rng.random((size, size)) - 0.5) * grain
    if ripple:
        n += np.sin(np.arange(size) / size * 2 * math.pi * 24)[None, :] * ripple
    rgb = np.array(base, np.float32)[None, None, :] * (1.0 + n)[..., None]
    return rgb


def pizza_print_rgb(size=512):
    """Circular red/white pizza graphic (disc fills the texture, v up)."""
    y, x = np.mgrid[0:size, 0:size]
    u = (x + 0.5) / size * 2 - 1
    v = (y + 0.5) / size * 2 - 1
    r = np.sqrt(u * u + v * v)
    a = np.arctan2(v, u)
    red = np.array((0.80, 0.08, 0.07))
    white = np.array((0.97, 0.95, 0.90))
    crust = np.array((0.82, 0.55, 0.25))
    sauce = np.array((0.75, 0.16, 0.08))
    cheese = np.array((0.98, 0.80, 0.32))
    pep = np.array((0.62, 0.07, 0.05))
    green = np.array((0.20, 0.55, 0.20))
    img = np.zeros((size, size, 3), np.float32) + white
    # outer red rim and checkered tablecloth band
    img[r > 0.94] = red
    band = (r > 0.76) & (r <= 0.94)
    chk = ((np.floor((a + math.pi) / (2 * math.pi) * 32) + np.floor((r - 0.76) / 0.09)) % 2) == 0
    img[band & chk] = red
    img[(r > 0.735) & (r <= 0.76)] = red
    # pizza in the middle
    img[r <= 0.62] = crust
    img[r <= 0.55] = sauce
    rng = np.random.default_rng(7)
    ch = value_noise(size, size, 10, 10, rng)
    img[(r <= 0.53) & (ch > 0.42)] = cheese
    for k in range(9):
        ang = k * 2 * math.pi / 9 + 0.3
        rad = 0.32 if k % 2 else 0.2
        if k == 8:
            rad = 0.0
        cx, cy = math.cos(ang) * rad, math.sin(ang) * rad
        img[((u - cx) ** 2 + (v - cy) ** 2) < 0.075 ** 2] = pep
    for k in range(7):
        ang = k * 2 * math.pi / 7 + 1.0
        cx, cy = math.cos(ang) * 0.42, math.sin(ang) * 0.42
        img[((u - cx) ** 2 / 0.05 ** 2 + (v - cy) ** 2 / 0.025 ** 2) < 1] = green
    # slice cut lines
    for k in range(4):
        ang = k * math.pi / 4
        d = np.abs(-math.sin(ang) * u + math.cos(ang) * v)
        img[(d < 0.008) & (r < 0.6)] = crust * 0.8
    return img


def cup_rgb(size=256):
    """Upper half (v 0.5..1): cup wrap (white with a coloured band). Lower half: striped straw paper."""
    img = np.zeros((size, size, 3), np.float32) + np.array((0.96, 0.96, 0.94))
    y, x = np.mgrid[0:size, 0:size]
    v = (y + 0.5) / size
    u = (x + 0.5) / size
    teal = np.array((0.05, 0.50, 0.50))
    red = np.array((0.85, 0.12, 0.10))
    cup = v >= 0.5
    cv = (v - 0.5) * 2  # 0 bottom .. 1 top of the cup
    img[cup & (cv > 0.30) & (cv < 0.62)] = teal
    img[cup & (cv > 0.875) & (cv < 0.975)] = teal
    img[cup & (np.abs(cv - 0.862) < 0.007)] = red
    img[cup & (np.abs(cv - 0.26) < 0.012)] = red
    straw = v < 0.5
    stripe = (np.floor((u * 4 + v * 16)) % 2) == 0
    img[straw & stripe] = red
    return img


# ----------------------------------------------------------------------------- mesh building
class Part:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()

    @property
    def uv(self):
        return self.bm.loops.layers.uv.verify()

    def mark(self):
        return set(self.bm.faces)

    def since(self, before):
        return [f for f in self.bm.faces if f not in before]


def box_uv(P, faces, scale=4.0):
    uv = P.uv
    P.bm.normal_update()
    for f in faces:
        n = f.normal
        a = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            if a == 0:
                uu, vv = (c.y if n.x > 0 else -c.y), c.z
            elif a == 1:
                uu, vv = (-c.x if n.y > 0 else c.x), c.z
            else:
                uu, vv = c.x, (c.y if n.z > 0 else -c.y)
            l[uv].uv = (uu * scale, vv * scale)


def rbox(P, size, center=(0.0, 0.0), z0=0.0, rv=0.0, sv=2, rb=0.0, sb=1, rt=0.0, st=1, open_top=False,
         mat=0, uvscale=4.0):
    """Box (size x, y, z) standing on z0, vertical edges rounded rv, bottom/top perimeter rounded rb/rt."""
    bm = P.bm
    before = P.mark()
    sx, sy, sz = size
    cx, cy = center
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res['verts']:
        v.co = Vector((v.co.x * sx + cx, v.co.y * sy + cy, (v.co.z + 0.5) * sz + z0))

    def cur():
        bm.normal_update()
        fs = P.since(before)
        return fs, {e for f in fs for e in f.edges}

    if rv > 0:
        fs, es = cur()
        ev = [e for e in es if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-7
              and abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-7 and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-7]
        bmesh.ops.bevel(bm, geom=ev, offset=rv, offset_type='OFFSET', segments=sv, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    for r, s, sign in ((rb, sb, -1), (rt, st, 1)):
        if r > 0:
            fs, es = cur()
            zt = z0 if sign < 0 else z0 + sz
            cap = [f for f in fs if f.normal.z * sign > 0.99 and abs(f.calc_center_median().z - zt) < 1e-6]
            ce = list({e for f in cap for e in f.edges})
            bmesh.ops.bevel(bm, geom=ce, offset=r, offset_type='OFFSET', segments=s, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
    if open_top:
        fs, es = cur()
        top = [f for f in fs if f.normal.z > 0.99 and abs(f.calc_center_median().z - (z0 + sz)) < 1e-6]
        bmesh.ops.delete(bm, geom=top, context='FACES_ONLY')
    fs, es = cur()
    for f in fs:
        f.material_index = mat
    box_uv(P, fs, uvscale)
    return fs


def rrect(w, d, r, segs, cx=0.0, cy=0.0):
    """Closed CCW rounded rectangle outline (list of (x, y))."""
    pts = []
    corners = ((w / 2 - r, -d / 2 + r, -90.0), (w / 2 - r, d / 2 - r, 0.0),
               (-w / 2 + r, d / 2 - r, 90.0), (-w / 2 + r, -d / 2 + r, 180.0))
    for (x0, y0, a0) in corners:
        for k in range(segs + 1):
            a = math.radians(a0 + 90.0 * k / segs)
            pts.append((cx + x0 + r * math.cos(a), cy + y0 + r * math.sin(a)))
    return pts


def outline_normals(pts):
    n = len(pts)
    out = []
    for i in range(n):
        p0 = Vector(pts[i - 1])
        p1 = Vector(pts[i])
        p2 = Vector(pts[(i + 1) % n])
        t = ((p1 - p0).normalized() + (p2 - p1).normalized()).normalized()
        out.append(Vector((t.y, -t.x)))
    return out


def band(P, pts, z0, z1, off, thick, mat=0, uvscale=4.0):
    """Strip around a closed CCW outline (tape, zipper): outer wall + top/bottom lips."""
    bm = P.bm
    before = P.mark()
    ns = outline_normals(pts)
    rows = []
    for (x, y), n in zip(pts, ns):
        p = Vector((x, y))
        i = p + n * off
        o = p + n * (off + thick)
        rows.append((bm.verts.new((i.x, i.y, z0)), bm.verts.new((o.x, o.y, z0)),
                     bm.verts.new((o.x, o.y, z1)), bm.verts.new((i.x, i.y, z1))))
    m = len(rows)
    for k in range(m):
        a = rows[k]
        b = rows[(k + 1) % m]
        bm.faces.new((a[1], b[1], b[2], a[2]))  # outer
        bm.faces.new((a[2], b[2], b[3], a[3]))  # top
        bm.faces.new((a[0], b[0], b[1], a[1]))  # bottom
    fs = P.since(before)
    for f in fs:
        f.material_index = mat
    box_uv(P, fs, uvscale)
    return fs


def frames(path, closed=False, side=None, up=None):
    n = len(path)
    T = []
    for i in range(n):
        if closed:
            a, b = path[(i - 1) % n], path[(i + 1) % n]
        else:
            a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        T.append((b - a).normalized())
    out = []
    if side is not None:
        side = Vector(side)
        for t in T:
            B = (side - t * side.dot(t)).normalized()
            out.append((t, B.cross(t), B))
        return out
    ref = Vector(up) if up is not None else Vector((0, 0, 1))
    N = ref - T[0] * ref.dot(T[0])
    if N.length < 1e-6:
        N = Vector((1, 0, 0)) - T[0] * T[0].x
    N.normalize()
    for t in T:
        N = (N - t * N.dot(t)).normalized()
        out.append((t, N, t.cross(N)))
    return out


def sweep(P, path, profile, closed=False, cap=True, side=None, up=None, twist=None, mat=0,
          uv_rect=(0.0, 0.0, 1.0, 1.0), v_scale=None, miter=False):
    """Sweep a CCW (u along N, v along B) profile along a path of Vectors."""
    bm = P.bm
    before = P.mark()
    path = [Vector(p) for p in path]
    F = frames(path, closed, side, up)
    rings = []
    n = len(path)
    for i, (p, (t, N, B)) in enumerate(zip(path, F)):
        ang = twist[i] if twist else 0.0
        c, s = math.cos(ang), math.sin(ang)
        k = 1.0
        if miter:
            tin = (p - path[i - 1]).normalized() if (closed or i > 0) else t
            k = 1.0 / max(0.72, tin.dot(t))
        ring = []
        for (u, v) in profile:
            uu = u * c - v * s
            vv = (u * s + v * c) * k
            ring.append(bm.verts.new(p + N * uu + B * vv))
        rings.append(ring)
    # arc length
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (path[i] - path[i - 1]).length)
    if closed:
        L.append(L[-1] + (path[0] - path[-1]).length)
    total = L[-1] if L[-1] > 0 else 1.0
    u0, v0, u1, v1 = uv_rect
    m = len(profile)
    uvl = P.uv

    def vcoord(i):
        return v0 + (v1 - v0) * (L[i] / total if v_scale is None else L[i] * v_scale)

    segs = range(n) if closed else range(n - 1)
    for i in segs:
        r0 = rings[i]
        r1 = rings[(i + 1) % n]
        for j in range(m):
            f = bm.faces.new((r0[j], r0[(j + 1) % m], r1[(j + 1) % m], r1[j]))
            uvs = ((j / m, vcoord(i)), ((j + 1) / m, vcoord(i)), ((j + 1) / m, vcoord(i + 1)), (j / m, vcoord(i + 1)))
            for l, (uu, vv) in zip(f.loops, uvs):
                l[uvl].uv = (u0 + (u1 - u0) * uu, vv)
    if cap and not closed:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            f = bm.faces.new(list(reversed(ring)) if rev else ring)
            for l in f.loops:
                l[uvl].uv = (u0 + (u1 - u0) * 0.5, v0)
    fs = P.since(before)
    for f in fs:
        f.material_index = mat
    return fs


def lathe(P, prof, segs, center=(0.0, 0.0), mat=0, uv_rect=(0.0, 0.0, 1.0, 1.0)):
    """Revolve (r, z) profile (bottom -> top) about the vertical axis at center."""
    bm = P.bm
    before = P.mark()
    cx, cy = center
    rings = []
    for (r, z) in prof:
        if r < 1e-7:
            rings.append([bm.verts.new((cx, cy, z))])
        else:
            rings.append([bm.verts.new((cx + r * math.cos(2 * math.pi * j / segs),
                                        cy + r * math.sin(2 * math.pi * j / segs), z)) for j in range(segs)])
    L = [0.0]
    for i in range(1, len(prof)):
        L.append(L[-1] + math.hypot(prof[i][0] - prof[i - 1][0], prof[i][1] - prof[i - 1][1]))
    tot = L[-1] or 1.0
    u0, v0, u1, v1 = uv_rect
    uvl = P.uv
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        va, vb = v0 + (v1 - v0) * L[i] / tot, v0 + (v1 - v0) * L[i + 1] / tot
        for j in range(segs):
            ua, ub = u0 + (u1 - u0) * j / segs, u0 + (u1 - u0) * (j + 1) / segs
            if len(a) > 1 and len(b) > 1:
                f = bm.faces.new((a[j], a[(j + 1) % segs], b[(j + 1) % segs], b[j]))
                uvs = ((ua, va), (ub, va), (ub, vb), (ua, vb))
            elif len(b) == 1:
                f = bm.faces.new((a[j], a[(j + 1) % segs], b[0]))
                uvs = ((ua, va), (ub, va), ((ua + ub) / 2, vb))
            else:
                f = bm.faces.new((a[0], b[(j + 1) % segs], b[j]))
                uvs = (((ua + ub) / 2, va), (ub, vb), (ua, vb))
            for l, uv in zip(f.loops, uvs):
                l[uvl].uv = uv
    fs = P.since(before)
    for f in fs:
        f.material_index = mat
    return fs


def prism_y(P, poly, y0, y1, mat=0, uvscale=4.0):
    """Extrude a CCW (x, z) polygon (seen from -Y) between y0 (front) and y1 (back, y1 > y0)."""
    bm = P.bm
    before = P.mark()
    fr = [bm.verts.new((x, y0, z)) for (x, z) in poly]
    bk = [bm.verts.new((x, y1, z)) for (x, z) in poly]
    bm.faces.new(fr)
    bm.faces.new(list(reversed(bk)))
    m = len(poly)
    for i in range(m):
        j = (i + 1) % m
        bm.faces.new((fr[j], fr[i], bk[i], bk[j]))
    fs = P.since(before)
    bm.normal_update()
    # make sure the front cap faces -Y
    for f in fs:
        f.material_index = mat
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    box_uv(P, fs, uvscale)
    return fs


def to_object(P, mats, parent=None, smooth=35.0, location=(0, 0, 0)):
    me = bpy.data.meshes.new(P.name)
    P.bm.to_mesh(me)
    P.bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(P.name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = location
    if parent is not None:
        ob.parent = parent
    finish_shading(me, smooth)
    return ob


def finish_shading(me, smooth):
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
    else:
        me.shade_flat()


def bm_from_object(ob):
    P = Part(ob.name)
    P.bm.from_mesh(ob.data)
    return P


def replace_mesh(ob, P, smooth=35.0):
    mats = list(ob.data.materials)
    old = ob.data
    me = bpy.data.meshes.new(P.name)
    P.bm.to_mesh(me)
    P.bm.free()
    for m in mats:
        me.materials.append(m)
    ob.data = me
    bpy.data.meshes.remove(old)
    finish_shading(me, smooth)


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = ob.name
    if old.users == 0:
        bpy.data.meshes.remove(old)


def boolean_cut(ob, cutters):
    solvers = [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items]
    for c in cutters:
        md = ob.modifiers.new("cut", 'BOOLEAN')
        md.operation = 'DIFFERENCE'
        md.object = c
        if 'EXACT' in solvers:
            md.solver = 'EXACT'
        c.hide_render = True
        apply_modifiers(ob)
    for c in cutters:
        me = c.data
        bpy.data.objects.remove(c)
        bpy.data.meshes.remove(me)


def cutter_cyl(radius, depth, loc, axis='Z', segs=16):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius, depth=depth)
    me = bpy.data.meshes.new("cutter")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cutter", me)
    bpy.context.scene.collection.objects.link(ob)
    if axis == 'X':
        ob.rotation_euler = (0, math.pi / 2, 0)
    elif axis == 'Y':
        ob.rotation_euler = (math.pi / 2, 0, 0)
    ob.location = loc
    return ob


def cutter_box(size, loc, rv=0.0):
    P = Part("cutter")
    rbox(P, size, (0, 0), -size[2] / 2, rv=rv, sv=3)
    me = bpy.data.meshes.new("cutter")
    P.bm.to_mesh(me)
    P.bm.free()
    ob = bpy.data.objects.new("cutter", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    return ob


def panel(name, mat, w, h, center, normal, up, parent=None, curl=0.0, rows=1, double=False):
    """Flat (or bottom-curled) rectangle. Local frame: Godot +Z (= Blender local -Y) is the outward normal,
    local +Z (Godot +Y) is 'up'. Returns (object, surface centre point in parent space)."""
    n = Vector(normal).normalized()
    upv = Vector(up).normalized()
    Y = -n
    Z = upv
    X = Y.cross(Z)
    rot = Matrix((X, Y, Z)).transposed().to_4x4()
    P = Part(name)
    bm = P.bm
    uvl = P.uv
    front = []
    back = []
    for r in range(rows + 1):
        t = r / rows
        z = -h / 2 + h * t
        out = curl * (1.0 - t) ** 2
        front.append((bm.verts.new((-w / 2, -out, z)), bm.verts.new((w / 2, -out, z)), t))
        if double:
            back.append((bm.verts.new((-w / 2, -out + 0.0003, z)), bm.verts.new((w / 2, -out + 0.0003, z)), t))
    for r in range(rows):
        a, b = front[r], front[r + 1]
        f = bm.faces.new((a[0], a[1], b[1], b[0]))
        for l, uv in zip(f.loops, ((0, a[2]), (1, a[2]), (1, b[2]), (0, b[2]))):
            l[uvl].uv = uv
        if double:
            a, b = back[r], back[r + 1]
            f = bm.faces.new((a[0], b[0], b[1], a[1]))
            for l, uv in zip(f.loops, ((0, a[2]), (0, b[2]), (1, b[2]), (1, a[2]))):
                l[uvl].uv = uv
    if double:  # close the paper edges
        for side in (0, 1):
            for r in range(rows):
                a, b = front[r][side], front[r + 1][side]
                c, d = back[r][side], back[r + 1][side]
                f = bm.faces.new((a, c, d, b) if side == 0 else (a, b, d, c))
        for (fa, fb, _), (ba, bb, _), top in ((front[0], back[0], False), (front[-1], back[-1], True)):
            bm.faces.new((fa, fb, bb, ba) if top else (fa, ba, bb, fb))
    ob = to_object(P, [mat], parent=parent, smooth=0)
    ob.matrix_world = Matrix.Translation(Vector(center)) @ rot
    mid = Vector(center) + (rot.to_3x3() @ Vector((0, -curl * 0.25, 0)))
    return ob, mid


def root_empty(name):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(e)
    return e


def mesh_tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def scene_tris():
    return sum(mesh_tris(o) for o in bpy.context.scene.objects if o.type == 'MESH')


def scene_bounds(objs=None):
    bpy.context.view_layer.update()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in (objs or bpy.context.scene.objects):
        if o.type != 'MESH' or o.hide_render:
            continue
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def export(name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".glb")
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False, export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_materials='EXPORT', export_image_format='AUTO', export_cameras=False,
                              export_lights=False)
    lo, hi = scene_bounds()
    info = {"file": "res://assets/delivery/%s.glb" % name, "tris": scene_tris(),
            "bbox_godot_size": gd_size(hi - lo), "bbox_blender_min": [round(x, 4) for x in lo],
            "bbox_blender_max": [round(x, 4) for x in hi]}
    log("EXPORTED", name, info)
    return info


# ----------------------------------------------------------------------------- QA rendering
def qa_setup(res_x=900, res_y=900):
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_WORKBENCH'
    except TypeError:
        pass
    try:
        scene.view_settings.view_transform = 'Standard'
    except TypeError:
        pass
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_backface_culling = True
    try:
        sh.show_cavity = True
        sh.cavity_type = 'WORLD'
    except (AttributeError, TypeError):
        pass
    try:
        sh.show_shadows = False
        sh.use_world_space_lighting = False
    except AttributeError:
        pass
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("QAWorld")
    scene.world.color = (0.32, 0.33, 0.35)
    os.makedirs(QA, exist_ok=True)
    gdi = os.path.join(QA, ".gdignore")
    if not os.path.exists(gdi):
        open(gdi, "w").close()


def ref_cube(loc):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.1)
    me = bpy.data.meshes.new("QARefCube")
    bm.to_mesh(me)
    bm.free()
    m = bpy.data.materials.new("QARed")
    m.diffuse_color = (0.85, 0.03, 0.03, 1)
    me.materials.append(m)
    ob = bpy.data.objects.new("QARefCube", me)
    ob.location = Vector(loc) + Vector((0, 0, 0.05))
    bpy.context.scene.collection.objects.link(ob)
    return ob


def qa_render(name, views=(("", (1.0, -1.7, 0.95)), ("_back", (-1.1, 1.6, 1.0))), lens=60, pad=1.12):
    if not DO_QA:
        return
    qa_setup()
    scene = bpy.context.scene
    lo, hi = scene_bounds()
    cube = ref_cube((lo.x - 0.075, lo.y + 0.05, 0.0))
    lo, hi = scene_bounds()
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.01
    cam.data.clip_end = 100
    scene.camera = cam
    target = (lo + hi) / 2
    radius = (hi - lo).length / 2
    fov = cam.data.angle
    dist = radius / math.sin(fov / 2) * pad
    for suffix, d in views:
        dirv = Vector(d).normalized()
        cam.location = target + dirv * dist
        cam.rotation_euler = (-dirv).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(QA, name + suffix + ".png")
        bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    bpy.data.objects.remove(cube)


# ----------------------------------------------------------------------------- 1. glyphs
EXTRUDE = 0.012      # Blender text 'extrude' (half depth of the straight wall)
BEVEL = 0.002
BOLD = 0.024         # outline offset in em units: emboldens the bundled regular font (no bold face ships)
MAX_GLYPH_TRIS = 300
GLYPHS = [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"] + [
    ("dash", "-"), ("dot", "."), ("slash", "/"), ("amp", "&"), ("space", " ")]


def text_mesh(body, res=12, offset=0.0, extrude=0.0, bevel=0.0, fill='BOTH', poly=None):
    if poly is None:
        cu = bpy.data.curves.new("tmp", 'FONT')
        cu.body = body
        cu.size = 1.0
        cu.align_x = 'LEFT'
    else:
        cu = bpy.data.curves.new("tmp", 'CURVE')
        cu.dimensions = '2D'
        sp = cu.splines.new('POLY')
        sp.points.add(len(poly) - 1)
        for pt, (x, y) in zip(sp.points, poly):
            pt.co = (x, y, 0.0, 1.0)
        sp.use_cyclic_u = True
    cu.fill_mode = fill
    cu.resolution_u = res
    cu.offset = offset
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 0
    ob = bpy.data.objects.new("tmp", cu)
    bpy.context.scene.collection.objects.link(ob)
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return me


def mesh_extent(me, axis):
    vals = [v.co[axis] for v in me.vertices]
    return (min(vals), max(vals)) if vals else (0.0, 0.0)


def one_with_flag():
    """The bundled font's '1' is a bare stem (reads as 'I' on house numbers): rebuild it with a flag.
    Returns the outline polygon in em units (not emboldened)."""
    me = text_mesh("1")
    x0, x1 = mesh_extent(me, 0)
    y0, y1 = mesh_extent(me, 1)
    bpy.data.meshes.remove(me)
    w = x1 - x0
    d = Vector((-0.8, -0.6))
    p = Vector((0.6, -0.8))
    D = Vector((x0, y1))
    E = D + d * 0.21
    F = E + p * (w * 0.95)
    G = F + (-d) * ((x0 - F.x) / 0.8)
    return [(x0, y0), (x1, y0), (x1, y1), (D.x, D.y), (E.x, E.y), (F.x, F.y), (G.x, G.y)]


def glyph_candidate(ch, res, s, M, poly=None):
    """Front cap + front chamfer + side wall from Blender's curve fill; a flat back cap is added here
    (drops the back chamfer, which is never seen on mounted lettering, to afford smoother curves)."""
    me = text_mesh(ch, res, BOLD, EXTRUDE / s, BEVEL / s, fill='FRONT', poly=poly)
    if poly is not None:
        xa, xb = mesh_extent(me, 0)
        if xb - xa < (max(q[0] for q in poly) - min(q[0] for q in poly)) + BOLD:
            bpy.data.meshes.remove(me)   # winding made the offset shrink the outline: reverse it
            me = text_mesh(ch, res, BOLD, EXTRUDE / s, BEVEL / s, fill='FRONT', poly=list(reversed(poly)))
    me.transform(M)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    ymax = max(v.co.y for v in bm.verts)
    boundary = [e for e in bm.edges if e.is_boundary]
    res_f = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=boundary,
                                    normal=Vector((0, 1, 0)))
    caps = [g for g in res_f['geom'] if isinstance(g, bmesh.types.BMFace)]
    left = [e for e in bm.edges if e.is_boundary]
    if left:   # self-touching emboldened outlines (B, M, Q, 4) leave small loops unfilled
        res_h = bmesh.ops.holes_fill(bm, edges=left, sides=0)
        holes = res_h['faces']
        bmesh.ops.triangulate(bm, faces=holes)
        caps += [f for f in bm.faces if f.is_valid and abs(f.calc_center_median().y - ymax) < 1e-6
                 and f not in caps]
    bm.normal_update()
    flip = [f for f in caps if f.normal.y < 0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, -ymax, 0))
    open_edges = sum(1 for e in bm.edges if e.is_boundary)
    bm.to_mesh(me)
    bm.free()
    tris = sum(len(pp.vertices) - 2 for pp in me.polygons)
    return me, tris, open_edges


def build_glyphs():
    reset()
    font_name = bpy.data.curves.new("probe", 'FONT').font.name
    paint = material("GlyphPaint", (1.0, 1.0, 1.0), 0.4, 0.0)
    plate_mat = material("PlateMetal", (0.07, 0.10, 0.22), 0.38, 0.75)
    # scale so the emboldened, bevelled 'H' is exactly 1.0 m tall
    s = 1.0 / 0.73
    for _ in range(5):
        me = text_mesh("H", 12, BOLD, EXTRUDE / s, BEVEL / s)
        y0, y1 = mesh_extent(me, 1)
        bpy.data.meshes.remove(me)
        s = 1.0 / (y1 - y0)
    zshift = -y0 * s
    xshift = BOLD * s + BEVEL
    me = text_mesh("H")
    h_max = mesh_extent(me, 0)[1]
    bpy.data.meshes.remove(me)
    M = (Matrix.Translation((xshift, 0.0, zshift)) @ Matrix.Scale(s, 4)
         @ Matrix.Rotation(math.radians(90), 4, 'X'))
    one_poly = one_with_flag()
    metrics = {}
    objs = []
    for key, ch in GLYPHS:
        me = text_mesh(ch + "H")
        adv_raw = mesh_extent(me, 0)[1] - h_max
        bpy.data.meshes.remove(me)
        advance = adv_raw * s + 2 * xshift
        name = "glyph_" + key
        if ch == " ":
            ob = root_empty(name)
            ob.empty_display_size = 0.1
            ob["char"] = ch
            ob["advance"] = round(advance, 5)
            ob["width"] = 0.0
            ob["lsb"] = 0.0
            ob["depth"] = 0.0
            metrics[key] = {"advance": round(advance, 5), "width": 0.0, "tris": 0, "res": 0}
            objs.append(ob)
            continue
        chosen = None
        for res in (6, 5, 4, 3, 2, 1):
            me, tris, open_edges = glyph_candidate(ch, res, s, M, one_poly if ch == "1" else None)
            if tris <= MAX_GLYPH_TRIS or res == 1:
                chosen = (me, res, tris, open_edges)
                break
            bpy.data.meshes.remove(me)
        me, res, tris, open_edges = chosen
        me.name = name
        me.materials.clear()
        me.materials.append(paint)
        finish_shading(me, 40.0)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        x0, x1 = mesh_extent(me, 0)
        z0, z1 = mesh_extent(me, 2)
        yb0, yb1 = mesh_extent(me, 1)
        depth = yb1 - yb0
        ob["char"] = ch
        ob["advance"] = round(advance, 5)
        ob["width"] = round(x1 - x0, 5)
        ob["lsb"] = round(x0, 5)
        ob["depth"] = round(depth, 5)
        metrics[key] = {"advance": round(advance, 5), "width": round(x1 - x0, 5), "lsb": round(x0, 5),
                        "z": [round(z0, 4), round(z1, 4)], "tris": tris, "res": res, "open_edges": open_edges}
        objs.append(ob)
    # number plate: 1 x 1 x 0.02, rounded corners, bevelled edges, origin back-centre, front -Y
    P = Part("number_plate")
    bm = P.bm
    res_c = bmesh.ops.create_cube(bm, size=1.0)
    for v in res_c['verts']:
        v.co = Vector((v.co.x * 1.0, v.co.y * 1.0, v.co.z * 0.02))
    bm.normal_update()
    zed = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-7]
    bmesh.ops.bevel(bm, geom=zed, offset=0.08, offset_type='OFFSET', segments=5, profile=0.5,
                    affect='EDGES', clamp_overlap=True)
    flat = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-7]
    bmesh.ops.bevel(bm, geom=flat, offset=0.004, offset_type='OFFSET', segments=1, profile=0.5,
                    affect='EDGES', clamp_overlap=True)
    bm.transform(Matrix.Translation((0, -0.01, 0)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    bm.normal_update()
    uvl = P.uv
    for f in bm.faces:
        for l in f.loops:
            l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.z + 0.5)
    plate = to_object(P, [plate_mat], smooth=40.0)
    plate["width"] = 1.0
    plate["height"] = 1.0
    plate["depth"] = 0.02
    info = export("glyphs")
    info.update({"font": font_name + " (Blender bundled default font, OFL) emboldened with a %.3f em outline"
                 " offset; '1' rebuilt with a flag" % BOLD,
                 "scale_from_em": round(s, 5), "glyph_depth": round(depth, 5), "extrude_param": EXTRUDE,
                 "bevel": BEVEL,
                 "glyphs": metrics, "max_glyph_tris": max(m["tris"] for m in metrics.values())})
    REPORT["glyphs"] = info
    if DO_QA:
        qa_glyphs(objs, plate, metrics)


def qa_glyphs(objs, plate, metrics):
    cols, sx, sz = 9, 1.75, 1.5
    w = (cols - 1) * sx + 1.6 + 0.6
    h = 4 * sz + 1.05 + 0.25
    qa_setup(1800, int(1800 * h / w))
    scene = bpy.context.scene
    plate.hide_render = True
    for i, ob in enumerate(objs):
        ob.location = ((i % cols) * sx, 0, -(i // cols) * sz)
    cube = ref_cube((-0.45, 0, -0.05))
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = w * 1.03
    cam.location = (-0.6 + w / 2, -20, 1.2 - h / 2)
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_end = 100
    scene.camera = cam
    scene.render.filepath = os.path.join(QA, "glyphs.png")
    bpy.ops.render.render(write_still=True)
    # sample house number "221B" and shop text "A&B 12/3" on scaled plates (uses advances)
    for ob in objs:
        ob.hide_render = True
    cube.location = (-0.9, -0.1, -0.5)
    samples = []
    for text, zc in (("221B", 0.0), ("A&B 12/3-4.", -1.9)):
        cap = 1.0
        total = sum(metrics[next(k for k, c in GLYPHS if c == ch)]["advance"] for ch in text)
        pl = plate.copy()
        scene.collection.objects.link(pl)
        pl.hide_render = False
        pl.scale = (total + 0.5, 1, cap + 0.5)
        pl.location = (total / 2, 0, zc + cap / 2)
        samples.append(pl)
        x = 0.0
        for ch in text:
            key = next(k for k, c in GLYPHS if c == ch)
            src = next(o for o in objs if o.name == "glyph_" + key)
            if src.type == 'MESH':
                g = src.copy()
                scene.collection.objects.link(g)
                g.hide_render = False
                g.location = (x, -0.02, zc)
                samples.append(g)
            x += metrics[key]["advance"]
    cam.data.type = 'PERSP'
    cam.data.lens = 40
    cam.location = (7.0, -13.0, 2.6)
    tgt = Vector((4.3, 0, -0.4))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    scene.render.filepath = os.path.join(QA, "glyphs_sample.png")
    bpy.ops.render.render(write_still=True)


# ----------------------------------------------------------------------------- 2. food packages
def package_extras(root, logo_ob, logo_mid, logo_n, logo_size, rec_ob, rec_mid, rec_n, rec_size):
    root["logo_center"] = gd(logo_mid)
    root["logo_normal"] = gd(logo_n)
    root["logo_size"] = [logo_size[0], logo_size[1]]
    root["receipt_center"] = gd(rec_mid)
    root["receipt_normal"] = gd(rec_n)
    root["receipt_size"] = [rec_size[0], rec_size[1]]
    root["extras_space"] = "godot_local"
    return {k: root[k] if not hasattr(root[k], "to_list") else root[k].to_list()
            for k in ("logo_center", "logo_normal", "logo_size", "receipt_center", "receipt_normal", "receipt_size")}


def logo_and_receipt(root, logo_c, logo_n, logo_up, logo_size, rec_c, rec_n, rec_up):
    logo_mat = material("LogoPanel", (0.94, 0.93, 0.89), 0.6)
    rec_mat = material("ReceiptPaper", (0.985, 0.985, 0.975), 0.75)
    logo, logo_mid = panel("LogoPanel", logo_mat, logo_size[0], logo_size[1], logo_c, logo_n, logo_up, parent=root)
    rec, rec_mid = panel("ReceiptTag", rec_mat, 0.075, 0.13, rec_c, rec_n, rec_up, parent=root,
                         curl=0.006, rows=6, double=True)
    return package_extras(root, logo, logo_mid, Vector(logo_n), logo_size, rec, rec_mid, Vector(rec_n), (0.075, 0.13))


def build_food_bag():
    reset()
    kraft = material("Kraft", (1, 1, 1), 0.88, 0.0,
                     image_from("kraft", paper_rgb((0.80, 0.62, 0.43), 11, 256, 0.06, 0.03, 0.03)))
    root = root_empty("FoodBag")
    W, D, H = 0.26, 0.16, 0.31
    G = 0.012
    rng = np.random.default_rng(3)

    def ring(z, inset=0.0, g=None, crease=0.0):
        gz = G * min(1.0, z / 0.04) if g is None else g
        hw, hd = W / 2 - inset - crease, D / 2 - inset - crease
        return [(-hw, -hd), (-hw / 2, -hd), (0, -hd), (hw / 2, -hd), (hw, -hd),
                (hw - gz / 2, -hd / 2), (hw - gz, 0), (hw - gz / 2, hd / 2),
                (hw, hd), (hw / 2, hd), (0, hd), (-hw / 2, hd), (-hw, hd),
                (-hw + gz / 2, hd / 2), (-hw + gz, 0), (-hw + gz / 2, -hd / 2)]

    P = Part("Bag")
    bm = P.bm
    zs = [0.0, 0.035, 0.10, 0.17, 0.24, 0.274, 0.282, 0.292, H]
    rings = []
    for z in zs:
        pts = ring(z, crease=0.0022 if abs(z - 0.282) < 1e-6 else 0.0)
        ns = outline_normals(pts)
        row = []
        for j, ((x, y), n) in enumerate(zip(pts, ns)):
            jitter = 0.0
            front = j <= 4
            if 0.0 < z < H and not front:
                jitter = float(rng.normal(0.0, 0.0011))
            row.append(bm.verts.new((x + n.x * jitter, y + n.y * jitter, z)))
        rings.append(row)
    m = len(rings[0])
    before = P.mark()
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    # inside: short inner wall + floor so the open top does not show through
    zi = H - 0.09
    inner_top = [bm.verts.new((x, y, H)) for (x, y) in ring(H, 0.0015)]
    inner_bot = [bm.verts.new((x, y, zi)) for (x, y) in ring(zi, 0.0015, g=G)]
    for j in range(m):
        k = (j + 1) % m
        bm.faces.new((inner_bot[j], inner_top[j], inner_top[k], inner_bot[k]))
        bm.faces.new((rings[-1][j], rings[-1][k], inner_top[k], inner_top[j]))
    bm.faces.new(inner_bot)
    fs = P.since(before)
    box_uv(P, fs, 3.0)
    # rolled lip around the rim
    pts = ring(H)
    ns = outline_normals(pts)
    lip = [Vector((x + n.x * 0.0022, y + n.y * 0.0022, H - 0.0012)) for (x, y), n in zip(pts, ns)]
    circ = [(0.0045 * math.cos(2 * math.pi * k / 6), 0.0045 * math.sin(2 * math.pi * k / 6)) for k in range(6)]
    sweep(P, lip, circ, closed=True, up=(0, 0, 1), miter=True, v_scale=4.0)
    # twisted paper handles (2-lobed profile rotating along the path)
    lobed = [(0.003 * (1 + 0.32 * math.cos(2 * a)) * math.cos(a), 0.003 * (1 + 0.32 * math.cos(2 * a)) * math.sin(a))
             for a in (2 * math.pi * k / 6 for k in range(6))]
    for sgn in (-1, 1):
        yy = sgn * (D / 2 - 0.0075)
        raw = [Vector((-0.05, yy, 0.276)), Vector((-0.05, yy, H + 0.012))]
        for k in range(1, 30):
            th = math.pi - math.pi * k / 30
            raw.append(Vector((0.05 * math.cos(th), yy, H + 0.012 + 0.06 * math.sin(th))))
        raw += [Vector((0.05, yy, H + 0.012)), Vector((0.05, yy, 0.276))]
        # resample uniformly
        L = [0.0]
        for i in range(1, len(raw)):
            L.append(L[-1] + (raw[i] - raw[i - 1]).length)
        nseg = 46
        path = []
        for k in range(nseg + 1):
            t = L[-1] * k / nseg
            i = max(1, next((i for i in range(1, len(L)) if L[i] >= t), len(L) - 1))
            f = (t - L[i - 1]) / max(1e-9, L[i] - L[i - 1])
            path.append(raw[i - 1].lerp(raw[i], f))
        twist = [math.radians(45) * k for k in range(len(path))]
        sweep(P, path, lobed, closed=False, cap=True, side=(0, 1, 0), twist=twist, v_scale=6.0)
    body = to_object(P, [kraft], parent=root, smooth=50.0)
    extras = logo_and_receipt(root, (0, -D / 2 - 0.001, 0.215), (0, -1, 0), (0, 0, 1), (0.16, 0.10),
                              (0.06, -D / 2 - 0.001, 0.09), (0, -1, 0), (0, 0, 1))
    info = export("food_bag")
    info["extras"] = extras
    REPORT["food_bag"] = info
    qa_render("food_bag")


def build_pizza_box():
    reset()
    card = material("Cardboard", (1, 1, 1), 0.85, 0.0,
                    image_from("cardboard", paper_rgb((0.84, 0.68, 0.48), 21, 256, 0.05, 0.02, 0.025, 0.01)))
    lidprint = material("LidPrint", (1, 1, 1), 0.7, 0.0, image_from("lidprint", pizza_print_rgb(512)))
    root = root_empty("PizzaBox")
    S = 0.36
    P = Part("Box")
    rbox(P, (S, S, 0.031), (0, 0), 0.0, rv=0.0015, sv=1, rb=0.0015, sb=1, open_top=True, uvscale=2.5)
    rbox(P, (S + 0.002, S + 0.002, 0.016), (0, 0), 0.029, rv=0.0015, sv=1, rt=0.002, st=1, uvscale=2.5)
    # front tab hanging from the lid over the base front wall
    tab = [(-0.056, 0.031), (-0.047, 0.0095), (-0.039, 0.0062), (0.039, 0.0062), (0.047, 0.0095), (0.056, 0.031)]
    prism_y(P, tab, -S / 2 - 0.0034, -S / 2 - 0.0004, uvscale=2.5)
    rbox(P, (0.03, 0.002, 0.004), (0, -S / 2 - 0.0042), 0.0075, rv=0.0009, sv=1, uvscale=2.5)   # finger lip
    box = to_object(P, [card, lidprint], parent=root, smooth=30.0)
    # vent holes in the lid side flaps and the hinge crease on the lid top
    cutters = []
    for sx in (-1, 1):
        for yy in (-0.09, 0.0, 0.09):
            cutters.append(cutter_cyl(0.0055, 0.012, (sx * (S / 2 + 0.001), yy, 0.037), 'X', 12))
    cutters.append(cutter_box((S - 0.03, 0.003, 0.004), (0, S / 2 - 0.009, 0.0455)))
    boolean_cut(box, cutters)
    # printed disc (LidPrint) 0.5 mm above the lid top
    P = bm_from_object(box)
    bm = P.bm
    uvl = P.uv
    R = 0.165
    zt = 0.045 + 0.0005
    vs = [bm.verts.new((R * math.cos(2 * math.pi * k / 40), R * math.sin(2 * math.pi * k / 40), zt)) for k in range(40)]
    f = bm.faces.new(vs)
    f.material_index = 1
    for l in f.loops:
        l[uvl].uv = (l.vert.co.x / (2 * R) + 0.5, l.vert.co.y / (2 * R) + 0.5)
    replace_mesh(box, P, smooth=30.0)
    extras = logo_and_receipt(root, (0, 0, 0.045 + 0.001), (0, 0, 1), (0, 1, 0), (0.18, 0.18),
                              (0.135, -0.06, 0.045 + 0.001), (0, 0, 1), (0, 1, 0))
    info = export("pizza_box")
    info["extras"] = extras
    REPORT["pizza_box"] = info
    qa_render("pizza_box", views=(("", (1.0, -1.7, 1.25)), ("_back", (-1.1, 1.6, 0.9))))


def build_drink_carrier():
    reset()
    card = material("Cardboard", (1, 1, 1), 0.85, 0.0,
                    image_from("cardboard", paper_rgb((0.84, 0.68, 0.48), 21, 256, 0.05, 0.02, 0.025, 0.01)))
    cup_mat = material("CupPaper", (1, 1, 1), 0.6, 0.0, image_from("cuppaper", cup_rgb(256)))
    lid_mat = material("LidPlastic", (0.95, 0.95, 0.95), 0.3, 0.0)
    mats = [card, cup_mat, lid_mat]
    root = root_empty("DrinkCarrier")
    W, D, HW = 0.245, 0.14, 0.145
    # tray (open box, 3 mm walls)
    P = Part("Carrier")
    rbox(P, (W, D, HW), (0, 0), 0.0, rv=0.008, sv=2, rb=0.002, sb=1, open_top=True, uvscale=3.0)
    tray = to_object(P, mats, parent=root, smooth=30.0)
    md = tray.modifiers.new("solid", 'SOLIDIFY')
    md.thickness = 0.003
    md.offset = -1.0
    md.use_even_offset = True
    md.use_rim = True
    apply_modifiers(tray)
    # cup insert deck with two holes
    P = Part("Deck")
    rbox(P, (W - 0.007, D - 0.007, 0.003), (0, 0), 0.096, rv=0.005, sv=2, uvscale=3.0)
    deck = to_object(P, mats, smooth=30.0)
    boolean_cut(deck, [cutter_cyl(0.0418, 0.02, (sx * 0.06, 0, 0.0975), 'Z', 20) for sx in (-1, 1)])
    # centre handle card with a hand hole
    P = Part("Handle")
    prism_y(P, [(-0.05, 0.098), (0.05, 0.098), (0.05, 0.176), (0.035, 0.192), (-0.035, 0.192), (-0.05, 0.176)],
            -0.0015, 0.0015, uvscale=3.0)
    handle = to_object(P, mats, smooth=30.0)
    handle.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Z'))
    boolean_cut(handle, [cutter_box((0.012, 0.038, 0.02), (0, 0, 0.168)),
                         cutter_cyl(0.01, 0.012, (0, -0.019, 0.168), 'X', 12),
                         cutter_cyl(0.01, 0.012, (0, 0.019, 0.168), 'X', 12)])
    P = bm_from_object(tray)
    P.bm.from_mesh(deck.data)
    P.bm.from_mesh(handle.data)
    for o in (deck, handle):
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    # cups, lids, straws
    for sx in (-1, 1):
        c = (sx * 0.06, 0.0)
        lathe(P, [(0.0335, 0.004), (0.0405, 0.09), (0.0465, 0.172)], 20, c, mat=1, uv_rect=(0, 0.5, 1, 1.0))
        lathe(P, [(0.0455, 0.168), (0.0488, 0.1705), (0.0488, 0.1785), (0.0457, 0.181), (0.0415, 0.1835),
                  (0.0365, 0.1875), (0.012, 0.1885), (0.0, 0.1885)], 20, c, mat=2)
        base = Vector((c[0], 0.0, 0.13))
        tip = Vector((c[0] + sx * 0.012, 0.009, 0.224))
        circ = [(0.0035 * math.cos(2 * math.pi * k / 6), 0.0035 * math.sin(2 * math.pi * k / 6)) for k in range(6)]
        sweep(P, [base, base.lerp(tip, 0.5), tip], circ, cap=True, up=(1, 0, 0), mat=1, uv_rect=(0, 0.02, 1, 0.48))
    replace_mesh(tray, P, smooth=40.0)
    tray.name = "Carrier"
    extras = logo_and_receipt(root, (-0.042, -D / 2 - 0.001, 0.085), (0, -1, 0), (0, 0, 1), (0.14, 0.07),
                              (0.075, -D / 2 - 0.001, 0.0725), (0, -1, 0), (0, 0, 1))
    info = export("drink_carrier")
    info["extras"] = extras
    REPORT["drink_carrier"] = info
    qa_render("drink_carrier")


# ----------------------------------------------------------------------------- 3. delivery bag
BAG_W, BAG_D, BAG_HB, BAG_LID = 0.42, 0.34, 0.40, 0.04
WALL = 0.02
CORNER = 0.035


def bag_materials():
    return [material("BagFabric", (0.95, 0.33, 0.10), 0.78, 0.0),
            material("Reflective", (0.78, 0.79, 0.81), 0.3, 0.6),
            material("BagTrim", (0.035, 0.035, 0.04), 0.82, 0.0),
            material("LogoPanel", (0.94, 0.93, 0.89), 0.6, 0.0)]


def build_bag(open_lid):
    reset()
    mats = bag_materials()
    fabric, reflective, trim, logo_mat = mats
    W, D, HB = BAG_W, BAG_D, BAG_HB
    root = root_empty("DeliveryBag")
    # body: open rounded box, solidified inward (outer fabric, inner silver lining, rim trim)
    P = Part("BagBody")
    rbox(P, (W, D, HB), (0, 0), 0.0, rv=CORNER, sv=3, rb=0.03, sb=2, open_top=True, mat=0, uvscale=3.0)
    body = to_object(P, [fabric, reflective, trim], parent=root, smooth=40.0)
    md = body.modifiers.new("solid", 'SOLIDIFY')
    md.thickness = WALL
    md.offset = -1.0
    md.use_even_offset = True
    md.use_rim = True
    md.material_offset = 1
    md.material_offset_rim = 2
    apply_modifiers(body)
    P = bm_from_object(body)
    outline = rrect(W, D, CORNER, 3)
    band(P, outline, 0.06, 0.08, 0.0003, 0.0016, mat=1)        # reflective strips
    band(P, outline, 0.335, 0.355, 0.0003, 0.0016, mat=1)
    band(P, outline, 0.387, 0.4, 0.0003, 0.0045, mat=2)        # zipper tape
    rbox(P, (0.012, 0.004, 0.032), (0.135, -D / 2 - 0.004), 0.36, rv=0.002, sv=1, mat=2)   # zipper pull
    rbox(P, (0.016, 0.005, 0.008), (0.135, -D / 2 - 0.004), 0.388, mat=1)
    # shoulder straps on the back (+Y)
    strap = [(0.007, -0.0235), (0.007, 0.0235), (0.003, 0.0275), (-0.003, 0.0275),
             (-0.007, 0.0235), (-0.007, -0.0235), (-0.003, -0.0275), (0.003, -0.0275)]
    for sx in (-1, 1):
        x = sx * 0.1
        path = []
        for k in range(15):
            t = k / 14
            z = 0.382 - t * 0.33
            y = D / 2 + 0.006 + 0.05 * math.sin(math.pi * t) ** 1.3 * (1.15 - 0.3 * t)
            path.append(Vector((x, y, z)))
        sweep(P, path, strap, cap=True, side=(1, 0, 0), mat=2, v_scale=3.0)
        rbox(P, (0.06, 0.008, 0.035), (x, D / 2 + 0.002), 0.36, rv=0.003, sv=1, mat=2)      # top anchor
        rbox(P, (0.05, 0.01, 0.03), (x, D / 2 + 0.003), 0.035, rv=0.004, sv=1, mat=2)       # buckle
        rbox(P, (0.03, 0.006, 0.008), (x, D / 2 + 0.008), 0.047, mat=1)
    replace_mesh(body, P, smooth=40.0)
    # lid: hinge on the back top edge, origin at the hinge
    P = Part("Lid")
    rbox(P, (W, D, BAG_LID), (0, -D / 2), 0.0, rv=CORNER, sv=3, rb=0.004, sb=1, rt=0.014, st=2, mat=0, uvscale=3.0)
    P.bm.normal_update()
    for f in P.bm.faces:
        if f.normal.z < -0.9:
            f.material_index = 1       # silver lining under the lid
    pip = [Vector((x, y, 0.026)) for (x, y) in rrect(W + 0.001, D + 0.001, CORNER + 0.0005, 3, 0, -D / 2)]
    circ = [(0.0035 * math.cos(2 * math.pi * k / 6), 0.0035 * math.sin(2 * math.pi * k / 6)) for k in range(6)]
    sweep(P, pip, circ, closed=True, up=(0, 0, 1), mat=2, miter=True, v_scale=3.0)
    # grab handle across the lid top
    hp = []
    for k in range(13):
        t = k / 12
        hp.append(Vector((-0.075 + 0.15 * t, -D / 2, BAG_LID + 0.003 + 0.032 * math.sin(math.pi * t) ** 0.6)))
    hprof = [(0.004, -0.014), (0.004, 0.014), (0.0015, 0.016), (-0.0015, 0.016),
             (-0.004, 0.014), (-0.004, -0.014), (-0.0015, -0.016), (0.0015, -0.016)]
    sweep(P, hp, hprof, cap=True, side=(0, 1, 0), mat=2, v_scale=3.0)
    for sx in (-1, 1):
        rbox(P, (0.03, 0.04, 0.005), (sx * 0.08, -D / 2), BAG_LID - 0.001, rv=0.004, sv=1, mat=2)
    lid = to_object(P, [fabric, reflective, trim], parent=root, smooth=40.0, location=(0, D / 2, HB))
    lid.name = "Lid"
    lid.data.name = "Lid"
    if open_lid:
        lid.rotation_euler = (math.radians(-110), 0, 0)
    # logo panel on the front
    logo_c = (0, -D / 2 - 0.001, 0.215)
    logo, logo_mid = panel("LogoPanel", logo_mat, 0.26, 0.16, logo_c, (0, -1, 0), (0, 0, 1), parent=root)
    root["logo_center"] = gd(logo_mid)
    root["logo_normal"] = gd((0, -1, 0))
    root["logo_size"] = [0.26, 0.16]
    root["lid_hinge"] = gd((0, D / 2, HB))
    root["lid_open_deg"] = 110.0
    root["extras_space"] = "godot_local"
    extras = {k: list(root[k]) if hasattr(root[k], "__len__") and not isinstance(root[k], str) else root[k]
              for k in ("logo_center", "logo_normal", "logo_size", "lid_hinge", "lid_open_deg")}
    name = "delivery_bag_open" if open_lid else "delivery_bag"
    if open_lid:
        iw, idp = W - 2 * WALL, D - 2 * WALL
        floor = WALL
        lower_z, upper_z, t = 0.08, 0.22, 0.012
        rr = CORNER - WALL - 0.002
        P = Part("DividerLower")
        rbox(P, (iw - 0.004, idp - 0.004, t), (0, 0), lower_z, rv=rr, sv=2, mat=0, uvscale=3.0)
        band(P, rrect(iw - 0.004, idp - 0.004, rr, 2), lower_z - 0.0005, lower_z + t + 0.0005, 0.0, 0.0015, mat=1)
        rbox(P, (0.05, 0.004, 0.018), (0, -idp / 2 + 0.012), lower_z + t, rv=0.0015, sv=1, mat=1)   # pull tab
        to_object(P, [reflective, trim], parent=root, smooth=40.0)
        P = Part("DividerUpper")
        rbox(P, (iw - 0.004, idp - 0.004, t), (0, 0), upper_z, rv=rr, sv=2, mat=0, uvscale=3.0)
        band(P, rrect(iw - 0.004, idp - 0.004, rr, 2), upper_z - 0.0005, upper_z + t + 0.0005, 0.0, 0.0015, mat=1)
        rbox(P, (t, idp - 0.004, upper_z - (lower_z + t)), (0, 0), lower_z + t, mat=0, uvscale=3.0)
        rbox(P, (t + 0.003, 0.003, upper_z - (lower_z + t)), (0, -idp / 2 + 0.0035), lower_z + t, mat=1)
        rbox(P, (0.05, 0.004, 0.018), (0, -idp / 2 + 0.012), upper_z + t, rv=0.0015, sv=1, mat=1)
        to_object(P, [reflective, trim], parent=root, smooth=40.0)
        hx = (iw / 2 - t / 2) / 2 + t / 2
        comps = {
            "bottom": ((0, 0, (floor + lower_z) / 2), (iw, idp, lower_z - floor)),
            "middle_left": ((-hx, 0, (lower_z + t + upper_z) / 2), (iw / 2 - t / 2, idp, upper_z - lower_z - t)),
            "middle_right": ((hx, 0, (lower_z + t + upper_z) / 2), (iw / 2 - t / 2, idp, upper_z - lower_z - t)),
            "top": ((0, 0, (upper_z + t + HB) / 2), (iw, idp, HB - upper_z - t)),
        }
        comp_extras = {}
        for k, (c, sz) in comps.items():
            comp_extras[k] = {"center": gd(c), "size": gd_size(sz)}
            slot = root_empty("Slot_" + "".join(p.capitalize() for p in k.split("_")))
            slot.parent = root
            slot.location = (c[0], c[1], c[2] - sz[2] / 2)
        root["compartments"] = comp_extras
        extras["compartments"] = comp_extras
    info = export(name)
    info["extras"] = extras
    info["nodes"] = sorted(o.name for o in bpy.context.scene.objects)
    REPORT[name] = info
    if open_lid:
        qa_render(name, views=(("", (0.9, -1.5, 1.5)), ("_back", (-1.1, 1.6, 1.0)), ("_top", (0.05, -0.35, 1.0))))
        if DO_QA:   # cutaway: dividers and slots only
            for o in bpy.context.scene.objects:
                if o.name in ("BagBody", "Lid", "LogoPanel"):
                    o.hide_render = True
            qa_render(name + "_dividers", views=(("", (0.9, -1.5, 0.7)),))
    else:
        qa_render(name)


# ----------------------------------------------------------------------------- main
def main():
    if wanted("glyphs"):
        build_glyphs()
    if wanted("food_bag"):
        build_food_bag()
    if wanted("pizza_box"):
        build_pizza_box()
    if wanted("drink_carrier"):
        build_drink_carrier()
    if wanted("delivery_bag"):
        build_bag(False)
        build_bag(True)
    os.makedirs(QA, exist_ok=True)
    rp = os.path.join(QA, "build_report.json")
    old = {}
    if os.path.exists(rp):
        try:
            old = json.load(open(rp))
        except Exception:
            old = {}
    old.update(REPORT)
    with open(rp, "w") as fh:
        json.dump(old, fh, indent=1, default=lambda o: list(o) if hasattr(o, "__len__") else str(o))
    for k, v in REPORT.items():
        log("SUMMARY", k, "tris", v["tris"], "size(godot xyz)", v["bbox_godot_size"])
    log("DONE")


main()
