"""Build the gadget/UI-prop GLBs (budget phone, store kiosk, drop arrow, pickup locker) procedurally.

Run headless (never in the user's live Blender, it resets the scene between assets):
  "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background --factory-startup \
      --python tools/build_gadgets.py [-- --only phone,kiosk,kiosk_stand,arrow,locker] [--no-qa]

Output (assets/gadgets/):
  budget_phone.glb        cheap chunky Android phone, origin at its centre, screen toward Godot +Z, long axis +Y
  store_kiosk.glb         countertop 24" monitor + keyboard/mouse on a mat + card terminal, origin bottom centre
  store_kiosk_stand.glb   the same monitor on a freestanding floor pedestal (screen centre 1.25 m)
  drop_arrow.glb          chunky downward arrow marker, origin at the tip, materials ArrowFill / ArrowRim
  pickup_locker.glb       online-order pickup shelving unit, SignPanel header, Slot_0..Slot_5 empties
  qa/<name>*.png          workbench QA renders (10 cm red reference cube; Screen/SignPanel show a UV test grid)
  qa/build_report.json    tri counts, sizes, extras, node names

Conventions (same as tools/build_delivery_assets.py; helpers are copied, that script runs main() on import):
  * metres; Blender Z up. glTF export maps Blender +Y forward to Godot -Z, so every asset's FRONT faces
    Blender -Y = Godot +Z.
  * Root extras are in GODOT local coordinates of the root empty (Y up, front +Z):
    Blender (x, y, z) -> Godot (x, z, -y). Godot exposes them as node metadata "extras" on the root empty
    (a child of the imported scene root).
  * Screen / SignPanel nodes: identity rotation, placed at the surface centre; their mesh is one flat quad in
    the node's local XY plane (Godot) facing local +Z, UV u 0..1 left->right and Blender v 0..1 bottom->top
    seen from the front (Godot UV.y = 1 - v, i.e. image row 0 at the top: a SubViewport texture shows upright).
"""
import bpy, bmesh, os, sys, math, json, tempfile
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "gadgets")
QA = os.path.join(OUT, "qa")
TMP = tempfile.mkdtemp(prefix="gadgets_")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY = set()
if "--only" in ARGS and ARGS.index("--only") + 1 < len(ARGS):
    ONLY = set(ARGS[ARGS.index("--only") + 1].split(","))
DO_QA = "--no-qa" not in ARGS
REPORT = {}


def log(*a):
    print("[gadgets]", *a, flush=True)


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
        attach_image(m, image)
    return m


def attach_image(m, image):
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = image
    tex.location = (-420, 220)
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.nodes.active = tex


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


def scuffed_plastic_rgb(base, seed, size=512):
    """Matte plastic: soft blotches, fine grain and a few faint light scuff strokes (tileable-ish)."""
    rng = np.random.default_rng(seed)
    n = (value_noise(size, size, 5, 5, rng) - 0.5) * 0.10
    n += (value_noise(size, size, 40, 40, rng) - 0.5) * 0.05
    n += (rng.random((size, size)) - 0.5) * 0.05
    add = np.zeros((size, size), np.float32)
    for k in range(70):
        x0, y0 = rng.random() * size, rng.random() * size
        ang = rng.normal(0.35, 0.6)
        ln = rng.uniform(6, 55)
        amp = rng.uniform(0.02, 0.06)
        for t in np.linspace(0.0, 1.0, int(ln * 2)):
            xi = int(x0 + math.cos(ang) * ln * t) % size
            yi = int(y0 + math.sin(ang) * ln * t) % size
            add[yi, xi] = max(add[yi, xi], amp * (1.0 - 0.5 * abs(t - 0.5)))
    rgb = np.array(base, np.float32)[None, None, :] * (1.0 + n)[..., None] + add[..., None]
    return rgb


def pegboard_rgb(base, size=256, holes=8):
    y, x = np.mgrid[0:size, 0:size]
    cell = size / holes
    fx = (x + 0.5) % cell - cell / 2
    fy = (y + 0.5) % cell - cell / 2
    rgb = np.zeros((size, size, 3), np.float32) + np.array(base, np.float32)
    rng = np.random.default_rng(5)
    rgb *= (1.0 + (value_noise(size, size, 6, 6, rng) - 0.5) * 0.06)[..., None]
    hole = (fx * fx + fy * fy) < (cell * 0.17) ** 2
    rgb[hole] = (0.06, 0.06, 0.065)
    return rgb


def uv_grid_rgb(size=512):
    """QA UV test grid (row 0 = bottom, v = 0): 8x8 checker, BIG red block + white corner at the TOP-LEFT,
    green block top-right, blue block bottom-left, black up-arrow in the middle."""
    y, x = np.mgrid[0:size, 0:size]
    u = (x + 0.5) / size
    v = (y + 0.5) / size
    chk = ((np.floor(u * 8) + np.floor(v * 8)) % 2) == 0
    img = np.zeros((size, size, 3), np.float32) + 0.88
    img[chk] = 0.58
    line = (np.abs(u * 8 - np.round(u * 8)) < 0.03) | (np.abs(v * 8 - np.round(v * 8)) < 0.03)
    img[line] = 0.3
    img[(u < 0.32) & (v > 0.68)] = (0.9, 0.05, 0.05)            # top-left marker
    img[(u < 0.09) & (v > 0.91)] = (1.0, 1.0, 1.0)
    img[(u > 0.82) & (v > 0.82)] = (0.05, 0.75, 0.15)           # top-right
    img[(u < 0.18) & (v < 0.18)] = (0.1, 0.25, 0.95)            # bottom-left
    arrow = ((v > 0.45) & (v < 0.66) & (np.abs(u - 0.5) < (0.66 - v) * 0.9)) | \
            ((v > 0.28) & (v <= 0.45) & (np.abs(u - 0.5) < 0.05))
    img[arrow] = (0.02, 0.02, 0.02)
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
    """Closed CCW rounded rectangle outline (list of (x, y)). Keep r < min(w, d) / 2."""
    pts = []
    corners = ((w / 2 - r, -d / 2 + r, -90.0), (w / 2 - r, d / 2 - r, 0.0),
               (-w / 2 + r, d / 2 - r, 90.0), (-w / 2 + r, -d / 2 + r, 180.0))
    for (x0, y0, a0) in corners:
        for k in range(segs + 1):
            a = math.radians(a0 + 90.0 * k / segs)
            pts.append((cx + x0 + r * math.cos(a), cy + y0 + r * math.sin(a)))
    return pts


def circle(r, segs, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * k / segs), cy + r * math.sin(2 * math.pi * k / segs)) for k in range(segs)]


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


def sweep(P, path, profile, closed=False, cap=True, side=None, up=None, mat=0, v_scale=None):
    """Sweep a CCW (u along N, v along B) profile along a path of Vectors."""
    bm = P.bm
    before = P.mark()
    path = [Vector(p) for p in path]
    F = frames(path, closed, side, up)
    rings = []
    n = len(path)
    for p, (t, N, B) in zip(path, F):
        rings.append([bm.verts.new(p + N * u + B * v) for (u, v) in profile])
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (path[i] - path[i - 1]).length)
    total = L[-1] if L[-1] > 0 else 1.0
    m = len(profile)
    uvl = P.uv

    def vcoord(i):
        return L[i] / total if v_scale is None else L[i] * v_scale

    for i in range(n - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(m):
            f = bm.faces.new((r0[j], r0[(j + 1) % m], r1[(j + 1) % m], r1[j]))
            uvs = ((j / m, vcoord(i)), ((j + 1) / m, vcoord(i)), ((j + 1) / m, vcoord(i + 1)), (j / m, vcoord(i + 1)))
            for l, uv in zip(f.loops, uvs):
                l[uvl].uv = uv
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
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
    for f in fs:
        f.material_index = mat
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    box_uv(P, fs, uvscale)
    return fs


def plate(P, pts, center, right, up, d0, d1, mat=0, back=False, sides=True, uvscale=8.0):
    """Prism of a CCW 2-D outline (u along `right`, v along `up`) placed at `center`, extruded along
    n = right x up from d0 to d1 (outer cap at d1 faces +n)."""
    bm = P.bm
    before = P.mark()
    right, up, c = Vector(right), Vector(up), Vector(center)
    n = right.cross(up)
    top = [bm.verts.new(c + right * u + up * v + n * d1) for (u, v) in pts]
    bm.faces.new(top)
    if sides or back:
        bot = [bm.verts.new(c + right * u + up * v + n * d0) for (u, v) in pts]
    if sides:
        m = len(pts)
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
    if back:
        bm.faces.new(list(reversed(bot)))
    fs = P.since(before)
    for f in fs:
        f.material_index = mat
    box_uv(P, fs, uvscale)
    return fs


def inset_poly(pts, d):
    """Offset a CCW polygon inward by d (mitred corners)."""
    n = len(pts)
    lines = []
    for i in range(n):
        a = Vector(pts[i])
        b = Vector(pts[(i + 1) % n])
        e = (b - a).normalized()
        nrm = Vector((-e.y, e.x))
        lines.append((a + nrm * d, e))
    out = []
    for i in range(n):
        p0, d0 = lines[i - 1]
        p1, d1 = lines[i]
        den = d0.x * d1.y - d0.y * d1.x
        t = ((p1.x - p0.x) * d1.y - (p1.y - p0.y) * d1.x) / den
        q = p0 + d0 * t
        out.append((q.x, q.y))
    return out


def text_into(P, body, height, center, right, up, lift, mat, offset=0.02, res=4):
    """Flat text (font cap height == `height`) centred at `center` on the plane (right, up), lifted along
    right x up by `lift`. Reads correctly when seen from the +n side."""
    cu = bpy.data.curves.new("tmp", 'FONT')
    cu.body = body
    cu.size = 1.0
    cu.align_x = 'LEFT'
    cu.fill_mode = 'BOTH'
    cu.resolution_u = res
    cu.offset = offset
    ob = bpy.data.objects.new("tmp", cu)
    bpy.context.scene.collection.objects.link(ob)
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    s = height / (max(ys) - min(ys))
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    right, up, c = Vector(right), Vector(up), Vector(center)
    n = right.cross(up)
    bm = P.bm
    vs = [bm.verts.new(c + right * ((v.co.x - mx) * s) + up * ((v.co.y - my) * s) + n * lift) for v in me.vertices]
    fs = []
    for p in me.polygons:
        try:
            f = bm.faces.new([vs[i] for i in p.vertices])
            f.material_index = mat
            fs.append(f)
        except ValueError:
            pass
    bpy.data.meshes.remove(me)
    box_uv(P, fs, 8.0)
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
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
    else:
        me.shade_flat()
    return ob


def screen_quad(name, mat, w, h, center, parent):
    """Flat quad, identity rotation, object origin at its centre. Faces Blender -Y (Godot +Z).
    UV u: 0 left -> 1 right, v: 0 bottom -> 1 top as seen from the front."""
    P = Part(name)
    bm = P.bm
    uvl = P.uv
    vs = [bm.verts.new((-w / 2, 0, -h / 2)), bm.verts.new((w / 2, 0, -h / 2)),
          bm.verts.new((w / 2, 0, h / 2)), bm.verts.new((-w / 2, 0, h / 2))]
    f = bm.faces.new(vs)
    for l, uv in zip(f.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        l[uvl].uv = uv
    ob = to_object(P, [mat], parent=parent, smooth=0, location=center)
    return ob


def root_empty(name):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(e)
    return e


def child_empty(name, parent, loc):
    e = root_empty(name)
    e.empty_display_size = 0.03
    e.parent = parent
    e.location = loc
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


def recenter_xy(root):
    """Shift root's children so the footprint (x, y) is centred on the origin."""
    lo, hi = scene_bounds()
    c = (lo + hi) / 2
    for o in root.children:
        o.location.x -= c.x
        o.location.y -= c.y
    bpy.context.view_layer.update()


def export(name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".glb")
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False, export_yup=True,
                              export_apply=True, export_extras=True, export_animations=False,
                              export_materials='EXPORT', export_image_format='AUTO', export_cameras=False,
                              export_lights=False)
    lo, hi = scene_bounds()
    info = {"file": "res://assets/gadgets/%s.glb" % name, "tris": scene_tris(),
            "tris_per_mesh": {o.name: mesh_tris(o) for o in bpy.context.scene.objects if o.type == 'MESH'},
            "bbox_godot_size": gd_size(hi - lo), "bbox_godot_min": gd((lo.x, hi.y, lo.z)),
            "bbox_godot_max": gd((hi.x, lo.y, hi.z)),
            "nodes": sorted(o.name for o in bpy.context.scene.objects),
            "materials": sorted(m.name for m in bpy.data.materials if m.users)}
    log("EXPORTED", name, info)
    return info


def extras_of(root):
    out = {}
    for k in root.keys():
        v = root[k]
        if hasattr(v, "to_dict"):
            v = v.to_dict()
        elif hasattr(v, "to_list"):
            v = v.to_list()
        elif isinstance(v, (list, tuple)):
            v = [x.to_list() if hasattr(x, "to_list") else x for x in v]
        out[k] = v
    return out


# ----------------------------------------------------------------------------- QA rendering
def show_grid(mats):
    """QA only (after export): put the UV test grid on the screen materials."""
    img = image_from("uv_grid", uv_grid_rgb(512))
    for m in mats:
        attach_image(m, img)
        m.diffuse_color = (1, 1, 1, 1)


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


def qa_render(name, views, lens=60, pad=1.12, cube=True, res=(900, 900), focus=None):
    if not DO_QA:
        return []
    qa_setup(*res)
    scene = bpy.context.scene
    lo, hi = scene_bounds()
    cub = ref_cube((lo.x - 0.09, lo.y + 0.05, lo.z)) if cube else None
    lo, hi = scene_bounds()
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.005
    cam.data.clip_end = 100
    scene.camera = cam
    target = (lo + hi) / 2
    radius = (hi - lo).length / 2
    fov = cam.data.angle
    dist = radius / math.sin(fov / 2) * pad
    if focus is not None:                  # (target point, distance) close-up
        target, dist = Vector(focus[0]), focus[1]
    out = []
    for suffix, d in views:
        dirv = Vector(d).normalized()
        cam.location = target + dirv * dist
        up = 'Y'
        cam.rotation_euler = (-dirv).to_track_quat('-Z', up).to_euler()
        path = os.path.join(QA, name + suffix + ".png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(os.path.relpath(path, ROOT).replace("\\", "/"))
    bpy.data.objects.remove(cam)
    if cub:
        bpy.data.objects.remove(cub)
    return out


# ----------------------------------------------------------------------------- 1. budget phone
PH_W, PH_H, PH_T = 0.074, 0.155, 0.0105
PH_CORNER, PH_EDGE = 0.0095, 0.0024
SCR_W, SCR_H = 0.0645, 0.136
SCR_GAP = 0.0004
SCR_TOP_BEZEL = 0.009            # bottom chin is the rest (0.155 - 0.136 - 0.009 = 0.010)


def rot_x(P, faces, angle, pivot=(0.0, 0.0, 0.0)):
    verts = list({v for f in faces for v in f.verts})
    bmesh.ops.rotate(P.bm, verts=verts, cent=Vector(pivot), matrix=Matrix.Rotation(angle, 3, 'X'))
    P.bm.normal_update()


def build_phone():
    reset()
    plastic = material("PhonePlastic", (1, 1, 1), 0.78, 0.0,
                       image_from("phone_scuff", scuffed_plastic_rgb((0.205, 0.21, 0.222), 41, 512)))
    mats = [plastic,
            material("PhoneGlass", (0.018, 0.019, 0.022), 0.07, 0.0),        # 1 black front glass / bezel
            material("PhoneDetailDark", (0.035, 0.036, 0.04), 0.5, 0.0),     # 2 speaker, ports, holes
            material("PhoneButtons", (0.16, 0.165, 0.175), 0.55, 0.2),        # 3 buttons, sim tray
            material("CameraIsland", (0.06, 0.062, 0.068), 0.25, 0.0),       # 4
            material("LensRing", (0.55, 0.56, 0.58), 0.3, 0.9),              # 5
            material("LensGlass", (0.02, 0.025, 0.045), 0.05, 0.0),          # 6
            material("Flash", (0.93, 0.88, 0.70), 0.35, 0.0),                # 7
            material("BrandPrint", (0.62, 0.63, 0.66), 0.45, 0.4)]           # 8
    screen_mat = material("ScreenMat", (0.012, 0.014, 0.018), 0.12, 0.0)
    W, H, T = PH_W, PH_H, PH_T
    root = root_empty("BudgetPhone")
    P = Part("PhoneBody")
    fs = rbox(P, (W, H, T), (0, 0), -T / 2, rv=PH_CORNER, sv=5, rb=PH_EDGE, sb=2, rt=PH_EDGE, st=2, mat=0)
    rot_x(P, fs, math.radians(90))          # long axis -> +Z, rbox top -> front (-Y)
    for f in fs:
        if f.normal.y < -0.999 and abs(f.calc_center_median().y + T / 2) < 1e-6:
            f.material_index = 1
    box_uv(P, fs, 6.0)
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    yf, yb = -T / 2, T / 2
    # ---- front: speaker slot and selfie camera in the top bezel
    zs = H / 2 - 0.0046
    plate(P, rrect(0.0115, 0.00125, 0.0006, 3), (0, yf, zs), X, Z, 0.0, 0.00008, mat=2, sides=False)
    plate(P, circle(0.00175, 14), (-0.0125, yf, zs), X, Z, 0.0, 0.00008, mat=4, sides=False)
    plate(P, circle(0.0011, 12), (-0.0125, yf, zs), X, Z, 0.0, 0.00014, mat=6, sides=False)
    plate(P, circle(0.0006, 8), (0.0105, yf, zs), X, Z, 0.0, 0.00008, mat=4, sides=False)   # proximity sensor
    # ---- back (seen from behind: right = -X): camera island top-left, flash, NOVA, speaker holes
    BR = -X
    icx, icz = 0.0235, H / 2 - 0.006 - 0.0155
    plate(P, rrect(0.0175, 0.031, 0.0084, 4), (icx, yb, icz), BR, Z, -0.0002, 0.0012, mat=4)
    plate(P, circle(0.0062, 20), (icx, yb, icz + 0.0062), BR, Z, 0.0011, 0.0019, mat=5)
    plate(P, circle(0.0047, 20), (icx, yb, icz + 0.0062), BR, Z, 0.0016, 0.00205, mat=6)
    plate(P, circle(0.0019, 10), (icx - 0.0012, yb, icz + 0.0072), BR, Z, 0.0, 0.00207, mat=4, sides=False)
    plate(P, circle(0.0023, 12), (icx, yb, icz - 0.0085), BR, Z, 0.0011, 0.00128, mat=7)
    text_into(P, "NOVA", 0.0062, (0, yb, -0.046), BR, Z, 0.00006, mat=8, offset=0.035)
    for k in range(2):                  # tiny regulatory print lines
        plate(P, rrect(0.014 - 0.004 * k, 0.0006, 0.00025, 1), (0, yb, -0.0535 - 0.0013 * k), BR, Z, 0.0, 0.00005,
              mat=8, sides=False)
    for row in range(2):
        for k in range(6):
            plate(P, circle(0.00055, 8), (-0.0055 * 2.5 + 0.0055 * k - 0.0, yb, -0.066 - 0.0022 * row),
                  BR, Z, 0.0, 0.00005, mat=2, sides=False)
    # ---- right side (+X): volume rocker above the power key
    xs = W / 2
    plate(P, rrect(0.0029, 0.0235, 0.0013, 3), (xs, 0.0002, 0.040), Y, Z, -0.0003, 0.00075, mat=3)
    plate(P, rrect(0.0029, 0.0112, 0.0013, 3), (xs, 0.0002, 0.014), Y, Z, -0.0003, 0.00075, mat=3)
    # ---- left side (-X): SIM tray outline + eject pin hole
    plate(P, rrect(0.0026, 0.0165, 0.0011, 3), (-xs, 0.0, 0.028), -Y, Z, 0.0, 0.00006, mat=3, sides=False)
    plate(P, circle(0.00045, 8), (-xs, 0.0, 0.0175), -Y, Z, 0.0, 0.00007, mat=2, sides=False)
    # ---- bottom (-Z, 'up' toward the front): USB-C, microphone; top (+Z): 3.5 mm jack
    zb = -H / 2
    plate(P, rrect(0.0089, 0.0032, 0.00155, 4), (0, 0, zb), X, -Y, 0.0, 0.00008, mat=2, sides=False)
    plate(P, rrect(0.0066, 0.0007, 0.0003, 1), (0, 0, zb), X, -Y, 0.0, 0.00012, mat=3, sides=False)
    plate(P, circle(0.0006, 8), (-0.0165, 0, zb), X, -Y, 0.0, 0.00008, mat=2, sides=False)
    plate(P, circle(0.0019, 14), (0.016, 0, H / 2), X, Y, 0.0, 0.00008, mat=2, sides=False)
    body = to_object(P, mats, parent=root, smooth=35.0)
    body.name = body.data.name = "PhoneBody"
    # ---- the screen: separate node, 0.4 mm in front of the glass
    sc = Vector((0.0, yf - SCR_GAP, H / 2 - SCR_TOP_BEZEL - SCR_H / 2))
    screen = screen_quad("Screen", screen_mat, SCR_W, SCR_H, sc, root)
    root["screen_center"] = gd(sc)
    root["screen_size"] = [SCR_W, SCR_H]
    root["screen_normal"] = [0.0, 0.0, 1.0]
    root["phone_size"] = [W, H, T]
    root["extras_space"] = "godot_local"
    info = export("budget_phone")
    info["extras"] = extras_of(root)
    show_grid([screen_mat])
    info["qa"] = qa_render("budget_phone", (("", (0.9, -1.7, 0.55)),), lens=70)
    info["qa"] += qa_render("budget_phone", (("_back", (-1.0, 1.7, 0.5)),), lens=70, cube=False)   # cube would hide it
    info["qa"] += qa_render("budget_phone", (("_closeup_front", (0.0, -1.0, 0.0)), ("_closeup_back", (0.0, 1.0, 0.0)),
                                             ("_closeup_side", (1.0, -0.35, -0.55))),
                            lens=85, pad=1.0, cube=False, res=(700, 1000))
    info["qa"] += qa_render("budget_phone", (("_closeup_bottom", (0.25, -0.75, -1.0)),), lens=85, cube=False,
                            res=(1000, 700), focus=((0.0, 0.0, -PH_H / 2), 0.16))
    REPORT["budget_phone"] = info


# ----------------------------------------------------------------------------- 2. store kiosk
MON_W, MON_H, MON_T = 0.542, 0.322, 0.014
MSCR_W, MSCR_H = 0.528, 0.297
MON_SIDE, MON_TOP = 0.007, 0.007     # bottom chin = 0.322 - 0.297 - 0.007 = 0.018
MSCR_GAP = 0.0005


def kiosk_materials():
    return {
        "shell": material("MonitorShell", (0.07, 0.072, 0.078), 0.45, 0.0),
        "bezel": material("MonitorBezel", (0.02, 0.021, 0.024), 0.35, 0.0),
        "stand": material("StandMetal", (0.30, 0.31, 0.33), 0.35, 0.85),
        "print": material("BrandPrint", (0.55, 0.56, 0.6), 0.4, 0.5),
        "led": material("PowerLED", (0.35, 0.75, 1.0), 0.3, 0.0),
        "kb": material("KeyboardBody", (0.10, 0.104, 0.112), 0.55, 0.0),
        "key": material("KeyCap", (0.035, 0.036, 0.04), 0.6, 0.0),
        "mat": material("DeskMat", (0.05, 0.055, 0.065), 0.92, 0.0),
        "mouse": material("MouseShell", (0.06, 0.062, 0.068), 0.4, 0.0),
        "wheel": material("MouseWheel", (0.18, 0.18, 0.19), 0.7, 0.0),
        "cable": material("Cable", (0.03, 0.03, 0.032), 0.6, 0.0),
        "term": material("TerminalBody", (0.12, 0.125, 0.135), 0.5, 0.0),
        "tscreen": material("TerminalDisplay", (0.03, 0.06, 0.09), 0.1, 0.0),
        "tkey": material("TerminalKey", (0.72, 0.73, 0.75), 0.5, 0.0),
        "red": material("KeyRed", (0.80, 0.12, 0.10), 0.5, 0.0),
        "yellow": material("KeyYellow", (0.92, 0.75, 0.12), 0.5, 0.0),
        "green": material("KeyGreen", (0.15, 0.62, 0.22), 0.5, 0.0),
        "screen": material("ScreenMat", (0.01, 0.012, 0.016), 0.1, 0.0),
    }


def build_monitor(root, M, zc, yf, desk_stand):
    """24" monitor. Housing centre at height zc, front bezel face at y = yf. Returns (Screen object, VESA y)."""
    order = ["shell", "bezel", "stand", "print", "led"]
    mats = [M[k] for k in order]
    P = Part("Monitor")
    fs = rbox(P, (MON_W, MON_H, MON_T), (0, 0), -MON_T / 2, rv=0.004, sv=2, rb=0.0015, sb=1, rt=0.0015, st=1, mat=0)
    rot_x(P, fs, math.radians(90))
    for f in fs:
        if f.normal.y < -0.999:
            f.material_index = 1
    bmesh.ops.translate(P.bm, verts=list({v for f in fs for v in f.verts}), vec=Vector((0, yf + MON_T / 2, zc)))
    yb = yf + MON_T
    # rear electronics bulge (tapered by its rounded back perimeter) + VESA plate
    fs = rbox(P, (0.38, 0.22, 0.03), (0, 0), -0.015, rv=0.03, sv=3, rt=0.012, st=2, mat=0)
    rot_x(P, fs, math.radians(-90))       # rounded top -> back (+Y)
    bmesh.ops.translate(P.bm, verts=list({v for f in fs for v in f.verts}), vec=Vector((0, yb + 0.015 - 0.002, zc - 0.01)))
    vesa_y = yb + 0.028 - 0.002
    fs = rbox(P, (0.11, 0.11, 0.008), (0, 0), 0.0, rv=0.006, sv=1, mat=2)
    rot_x(P, fs, math.radians(-90))
    bmesh.ops.translate(P.bm, verts=list({v for f in fs for v in f.verts}), vec=Vector((0, vesa_y - 0.001, zc - 0.01)))
    vesa_y += 0.007
    # chin: brand text and power LED
    zchin = zc - MON_H / 2 + (MON_H - MON_TOP - MSCR_H) / 2
    X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))
    text_into(P, "NOVA", 0.0075, (0, yf, zchin), X, Z, 0.00008, mat=3, offset=0.03)
    plate(P, circle(0.0012, 8), (MON_W / 2 - 0.02, yf, zchin), X, Z, 0.0, 0.0001, mat=4, sides=False)
    if desk_stand:
        neck_y = vesa_y + 0.018 + 0.012
        rbox(P, (0.075, 0.03, 0.065), (0, vesa_y + 0.01), zc - 0.045, rv=0.008, sv=2, mat=2)    # hinge arm
        rbox(P, (0.06, 0.024, zc + 0.02 - 0.012), (0, neck_y), 0.012, rv=0.008, sv=3, rt=0.004, st=1, mat=2)
        rbox(P, (0.26, 0.20, 0.012), (0, neck_y - 0.045), 0.0, rv=0.04, sv=4, rt=0.004, st=1, rb=0.001, sb=1, mat=2)
    mon = to_object(P, mats, parent=root, smooth=35.0)
    mon.name = mon.data.name = "Monitor"
    sc = Vector((0.0, yf - MSCR_GAP, zc - MON_H / 2 + (MON_H - MON_TOP - MSCR_H) + MSCR_H / 2))
    screen = screen_quad("Screen", M["screen"], MSCR_W, MSCR_H, sc, root)
    return screen, vesa_y


KB_W, KB_D = 0.43, 0.135


def build_keyboard(root, M, kx, ky, z0):
    """Full-size keyboard (main block + nav + numpad), front edge toward -Y, slight wedge."""
    P = Part("Keyboard")
    fs = rbox(P, (KB_W, KB_D, 0.011), (kx, ky), z0, rv=0.007, sv=2, rt=0.002, st=1, rb=0.001, sb=1, mat=0)
    yfront = ky - KB_D / 2
    rise = 0.007

    def ztop(y):
        return z0 + 0.011 + rise * (y - yfront) / KB_D

    for v in {v for f in fs for v in f.verts}:
        if v.co.z > z0 + 0.006:
            v.co.z += rise * (v.co.y - yfront) / KB_D
    p = 0.0174
    x0 = kx - 23 * p / 2
    yrow0 = ky + KB_D / 2 - 0.009 - p / 2

    def key(col, row, w=1.0, h=1.0):
        cx = x0 + (col + w / 2) * p
        cy = (yrow0 - (row + (0.3 if row > 0 else 0.0)) * p) - (h - 1) * p / 2
        rbox(P, (w * p - 0.0028, h * p - 0.0028, 0.0068), (cx, cy), ztop(cy) - 0.003, rv=0.0013, sv=1, mat=1)

    rows = [
        [1, -1, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.5, 1, 1, 1, 1],
        [1] * 13 + [2],
        [1.5] + [1] * 12 + [1.5],
        [1.75] + [1] * 11 + [2.25],
        [2.25] + [1] * 10 + [2.75],
        [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25],
    ]
    for r, widths in enumerate(rows):
        c = 0.0
        for w in widths:
            if w > 0:
                key(c, r, w)
            c += abs(w)
    nav = 15.5
    for k in range(3):
        key(nav + k, 0)
        key(nav + k, 1)
        key(nav + k, 2)
    key(nav + 1, 4)
    for k in range(3):
        key(nav + k, 5)
    num = 19.0
    for k in range(4):
        key(num + k, 1)
    for r in (2, 3, 4):
        for k in range(3):
            key(num + k, r)
    key(num + 3, 2, 1, 2)          # tall +
    key(num + 3, 4, 1, 2)          # tall Enter
    key(num, 5, 2)
    key(num + 2, 5)
    kb = to_object(P, [M["kb"], M["key"]], parent=root, smooth=35.0)
    return kb, (kx, ky + KB_D / 2, z0 + 0.008)


def build_mouse(root, M, mx, my, z0):
    P = Part("Mouse")
    bm = P.bm
    before = P.mark()
    res = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
    low = [v for v in res['verts'] if v.co.z < -1e-4]
    bmesh.ops.delete(bm, geom=low, context='VERTS')
    edges = [e for e in bm.edges if e.is_boundary]
    bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    L, Wm, Hm = 0.112, 0.062, 0.036

    def hfac(yn):
        return 0.70 + 0.30 * min(1.0, max(0.0, (yn + 1.0) / 1.6))

    for v in bm.verts:
        yn = v.co.y
        v.co = Vector((mx + v.co.x * Wm / 2, my + v.co.y * L / 2, z0 + v.co.z * Hm * hfac(yn)))
    fs = P.since(before)
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    for f in fs:
        f.material_index = 0
    box_uv(P, fs, 8.0)
    # scroll wheel in the front third
    yw = -0.026
    yn = yw / (L / 2)
    ztop = z0 + math.sqrt(max(0.0, 1 - yn * yn)) * Hm * hfac(yn)
    plate(P, circle(0.0058, 12), (mx, my + yw, ztop - 0.0028), Vector((0, 1, 0)), Vector((0, 0, 1)),
          -0.0035, 0.0035, mat=1, back=True)
    return to_object(P, [M["mouse"], M["wheel"]], parent=root, smooth=50.0)


def bezier(p0, p1, p2, p3, n=12):
    p0, p1, p2, p3 = map(Vector, (p0, p1, p2, p3))
    out = []
    for k in range(n):
        t = k / (n - 1)
        a = 1 - t
        out.append(p0 * a ** 3 + p1 * 3 * a * a * t + p2 * 3 * a * t * t + p3 * t ** 3)
    return out


def build_card_reader(root, M, cx, yfront, z0):
    """Handheld payment terminal resting tilted (25 deg) in a wedge cradle; front toward -Y."""
    order = ["term", "tscreen", "tkey", "red", "yellow", "green", "bezel"]
    mats = [M[k] for k in order]
    P = Part("CardReader")
    before = P.mark()
    Lt, Wt, Tt = 0.15, 0.074, 0.022
    rbox(P, (Wt, Lt, Tt), (0, Lt / 2), 0.0, rv=0.011, sv=3, rt=0.004, st=1, rb=0.004, sb=1, mat=0, uvscale=8.0)
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    plate(P, rrect(0.058, 0.046, 0.003, 2), (0, 0.112, Tt), X, Y, -0.0002, 0.0004, mat=6)       # display bezel
    plate(P, rrect(0.052, 0.040, 0.002, 2), (0, 0.112, Tt), X, Y, 0.0, 0.0006, mat=1, sides=False)
    for r in range(4):
        for c in range(3):
            rbox(P, (0.0135, 0.0088, 0.0028), (-0.0172 + 0.0172 * c, 0.083 - 0.0125 * r), Tt - 0.001,
                 rv=0.002, sv=1, mat=2, uvscale=8.0)
    for c, m in enumerate((3, 4, 5)):
        rbox(P, (0.0135, 0.0088, 0.0028), (-0.0172 + 0.0172 * c, 0.025), Tt - 0.001, rv=0.002, sv=1, mat=m)
    plate(P, rrect(0.052, 0.0028, 0.0012, 2), (0, 0, Tt * 0.55), X, Z, 0.0, 0.0002, mat=6, sides=False)   # chip slot
    fs = P.since(before)
    tilt = math.radians(25.0)
    verts = list({v for f in fs for v in f.verts})
    bmesh.ops.rotate(P.bm, verts=verts, cent=Vector((0, 0, 0)), matrix=Matrix.Rotation(tilt, 3, 'X'))
    zf = z0 + 0.016
    bmesh.ops.translate(P.bm, verts=verts, vec=Vector((cx, yfront, zf)))
    # chip slot sits on the front end, which is now facing -Y and down a bit: fine
    # wedge cradle under it (extruded along X)
    ta = math.tan(tilt)

    def zb(y):
        return zf + (y - yfront) * ta - 0.0015

    y0c, y1c = yfront + 0.012, yfront + Lt * math.cos(tilt) - 0.03
    prof = [(y0c, z0), (y1c, z0), (y1c, zb(y1c)), (y0c, zb(y0c))]
    plate(P, prof, (cx, 0, 0), Y, Z, -0.032, 0.032, mat=0, back=True)
    rbox(P, (0.082, y1c - y0c + 0.03, 0.006), (cx, (y0c + y1c) / 2), z0, rv=0.01, sv=2, rt=0.002, st=1, mat=0)
    # front lip that stops the terminal sliding off
    rbox(P, (0.07, 0.008, 0.02), (cx, yfront - 0.002), z0, rv=0.003, sv=1, rt=0.002, st=1, mat=0)
    ob = to_object(P, mats, parent=root, smooth=35.0)
    return ob


def kiosk_extras(root, screen):
    bpy.context.view_layer.update()
    c = screen.matrix_world.translation
    root["screen_center"] = gd(c)
    root["screen_size"] = [MSCR_W, MSCR_H]
    root["screen_normal"] = [0.0, 0.0, 1.0]
    root["extras_space"] = "godot_local"


def build_kiosk():
    reset()
    M = kiosk_materials()
    root = root_empty("StoreKiosk")
    zc = 0.300 - 0.0055     # screen centre 0.30 m above the counter
    screen, vesa_y = build_monitor(root, M, zc, 0.05, desk_stand=True)
    P = Part("DeskMat")
    rbox(P, (0.70, 0.26, 0.003), (-0.05, -0.155), 0.0, rv=0.02, sv=3, rt=0.001, st=1, mat=0)
    to_object(P, [M["mat"]], parent=root, smooth=35.0)
    kb, kb_back = build_keyboard(root, M, -0.12, -0.135, 0.003)
    build_mouse(root, M, 0.20, -0.14, 0.003)
    # keyboard cable to the stand
    P = Part("Cable")
    hexp = circle(0.0019, 6)
    neck_y = vesa_y + 0.03
    base_front = neck_y - 0.045 - 0.10
    path = bezier(kb_back, (kb_back[0], kb_back[1] + 0.03, 0.006), (-0.03, kb_back[1] + 0.005, 0.0049),
                  (-0.03, base_front - 0.008, 0.0049), 10)
    path += [Vector((-0.03, base_front + 0.004, 0.0142)), Vector((-0.028, base_front + 0.03, 0.0139)),
             Vector((-0.02, neck_y - 0.022, 0.0139)), Vector((-0.016, neck_y - 0.014, 0.022)),
             Vector((-0.015, neck_y - 0.008, 0.032))]
    sweep(P, path, hexp, cap=True, up=(0, 0, 1), v_scale=8.0)
    to_object(P, [M["cable"]], parent=root, smooth=60.0)
    build_card_reader(root, M, 0.40, -0.10, 0.0)
    recenter_xy(root)
    kiosk_extras(root, screen)
    lo, hi = scene_bounds()
    root["footprint"] = gd_size(hi - lo)
    info = export("store_kiosk")
    info["extras"] = extras_of(root)
    show_grid([M["screen"]])
    info["qa"] = qa_render("store_kiosk", (("", (1.0, -1.7, 0.95)), ("_back", (-1.1, 1.6, 1.0)),
                                           ("_front", (0.0, -1.0, 0.12))), lens=60)
    REPORT["store_kiosk"] = info


def build_kiosk_stand():
    reset()
    M = kiosk_materials()
    M["shelf"] = material("ShelfTop", (0.16, 0.165, 0.175), 0.6, 0.0)
    M["ped"] = material("PedestalSteel", (0.22, 0.225, 0.235), 0.4, 0.7)
    M["accent"] = material("AccentStripe", (0.95, 0.45, 0.08), 0.5, 0.0)
    root = root_empty("StoreKioskStand")
    zc = 1.25 - 0.0055
    screen, vesa_y = build_monitor(root, M, zc, 0.05, desk_stand=False)
    col_y0 = vesa_y + 0.006
    col_d = 0.07
    col_yc = col_y0 + col_d / 2
    shelf_top = 0.95
    P = Part("Pedestal")
    rbox(P, (0.56, 0.50, 0.018), (0, -0.05), 0.0, rv=0.06, sv=4, rt=0.006, st=2, rb=0.001, sb=1, mat=0)
    rbox(P, (0.12, col_d, zc + 0.06 - 0.018), (0, col_yc), 0.018, rv=0.012, sv=3, rt=0.004, st=1, mat=0)
    rbox(P, (0.09, 0.03, 0.10), (0, col_y0 - 0.008), zc - 0.06, rv=0.006, sv=1, mat=0)          # VESA arm
    # shelf (keyboard / payment counter) with a rounded front edge and two gussets
    shelf_y0, shelf_y1 = -0.31, col_y0
    rbox(P, (0.74, shelf_y1 - shelf_y0, 0.024), (0, (shelf_y0 + shelf_y1) / 2), shelf_top - 0.024,
         rv=0.03, sv=3, rt=0.006, st=2, rb=0.003, sb=1, mat=1)
    for sx in (-1, 1):
        prof = [(col_y0, shelf_top - 0.024), (col_y0, shelf_top - 0.26), (col_y0 - 0.02, shelf_top - 0.26),
                (shelf_y0 + 0.06, shelf_top - 0.024)]
        prof = list(reversed(prof))
        plate(P, prof, (sx * 0.045, 0, 0), Vector((0, 1, 0)), Vector((0, 0, 1)), -0.004, 0.004, mat=0, back=True)
    # accent stripe up the column front, below the shelf
    plate(P, rrect(0.03, 0.80, 0.0145, 3), (0, col_y0, 0.06 + 0.40), Vector((1, 0, 0)), Vector((0, 0, 1)),
          0.0, 0.0006, mat=2, sides=False)
    to_object(P, [M["ped"], M["shelf"], M["accent"]], parent=root, smooth=35.0)
    kb, kb_back = build_keyboard(root, M, -0.12, -0.17, shelf_top)
    build_mouse(root, M, 0.15, -0.19, shelf_top)
    P = Part("Cable")
    path = bezier(kb_back, (kb_back[0], kb_back[1] + 0.05, shelf_top + 0.0045), (-0.03, col_y0 - 0.03, shelf_top + 0.0019),
                  (-0.03, col_y0 - 0.002, shelf_top + 0.012), 12)
    sweep(P, path, circle(0.0019, 6), cap=True, up=(0, 0, 1), v_scale=8.0)
    to_object(P, [M["cable"]], parent=root, smooth=60.0)
    build_card_reader(root, M, 0.285, -0.13, shelf_top)
    recenter_xy(root)
    kiosk_extras(root, screen)
    root["shelf_height"] = shelf_top
    info = export("store_kiosk_stand")
    info["extras"] = extras_of(root)
    show_grid([M["screen"]])
    info["qa"] = qa_render("store_kiosk_stand", (("", (1.0, -1.7, 0.75)), ("_back", (-1.1, 1.6, 0.8)),
                                                 ("_front", (0.0, -1.0, 0.05))), lens=60)
    REPORT["store_kiosk_stand"] = info


# ----------------------------------------------------------------------------- 3. drop arrow
def build_arrow():
    reset()
    fill = material("ArrowFill", (1.0, 1.0, 1.0), 0.45, 0.0)
    rim = material("ArrowRim", (0.05, 0.05, 0.06), 0.6, 0.0)
    root = root_empty("DropArrow")
    outline = [(0.0, 0.0), (0.175, 0.205), (0.072, 0.205), (0.072, 0.45), (-0.072, 0.45), (-0.072, 0.205),
               (-0.175, 0.205)]
    P = Part("Arrow")
    bm = P.bm
    fs = prism_y(P, outline, -0.032, 0.032, mat=1)
    bmesh.ops.bevel(bm, geom=list({e for f in fs for e in f.edges}), offset=0.009, offset_type='OFFSET',
                    segments=2, profile=0.5, affect='EDGES', clamp_overlap=True)
    for f in bm.faces:                  # bevel faces inherit index 0: the whole outer shell is rim
        f.material_index = 1
    before = P.mark()
    inner = inset_poly(outline, 0.024)
    fs2 = prism_y(P, inner, -0.040, 0.040, mat=0)
    bmesh.ops.bevel(bm, geom=list({e for f in fs2 for e in f.edges}), offset=0.006, offset_type='OFFSET',
                    segments=2, profile=0.5, affect='EDGES', clamp_overlap=True)
    for f in P.since(before):
        f.material_index = 0
    # bevels trim the acute corners: scale back to exactly 0.35 x 0.45 with the (rounded) tip at z = 0
    xs = [v.co.x for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    sx, sz = 0.35 / (max(xs) - min(xs)), 0.45 / (max(zs) - min(zs))
    zmin = min(zs)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y, (v.co.z - zmin) * sz))
    box_uv(P, list(bm.faces), 2.0)
    ob = to_object(P, [fill, rim], parent=root, smooth=40.0)
    lo, hi = scene_bounds()
    root["tip"] = [0.0, 0.0, 0.0]
    root["size"] = gd_size(hi - lo)
    root["extras_space"] = "godot_local"
    info = export("drop_arrow")
    info["extras"] = extras_of(root)
    info["qa"] = qa_render("drop_arrow", (("", (1.0, -1.7, 0.6)), ("_back", (-1.1, 1.6, 0.5)),
                                          ("_front", (0.0, -1.0, 0.0))), lens=60)
    REPORT["drop_arrow"] = info


# ----------------------------------------------------------------------------- 4. pickup locker
LK_W, LK_D, LK_H = 1.6, 0.45, 1.9
LK_SHELVES = (1.10, 0.62, 0.14)     # shelf top surfaces, top shelf first
POST = 0.04


def build_locker():
    reset()
    steel = material("SteelFrame", (0.17, 0.18, 0.19), 0.45, 0.6)
    wood = material("ShelfWood", (1, 1, 1), 0.7, 0.0,
                    image_from("plywood", paper_rgb((0.80, 0.64, 0.44), 17, 256, 0.06, 0.12, 0.03)))
    peg = material("Pegboard", (1, 1, 1), 0.55, 0.3, image_from("pegboard", pegboard_rgb((0.74, 0.75, 0.76))))
    label = material("LabelStrip", (0.95, 0.95, 0.93), 0.5, 0.0)
    foot = material("RubberFoot", (0.03, 0.03, 0.03), 0.8, 0.0)
    sign_back = material("SignBacking", (0.10, 0.105, 0.11), 0.4, 0.5)
    sign_mat = material("SignMat", (0.96, 0.50, 0.10), 0.5, 0.0)
    mats = [steel, wood, peg, label, foot, sign_back]
    root = root_empty("PickupLocker")
    W, D, H = LK_W, LK_D, LK_H
    P = Part("Shelving")
    px, py = W / 2 - POST / 2, D / 2 - POST / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            rbox(P, (POST, POST, H - 0.02), (sx * px, sy * py), 0.02, rv=0.003, sv=1, rt=0.002, st=1, mat=0)
            plate(P, circle(0.016, 10), (sx * px, sy * py, 0.0), Vector((1, 0, 0)), Vector((0, 1, 0)),
                  0.0, 0.02, mat=4, back=True)
    inner_w = W - 2 * POST
    inner_d = D - 2 * POST
    for st in LK_SHELVES:
        board_t = 0.018
        rbox(P, (inner_w, D - 0.006, board_t), (0, 0), st - board_t, rv=0.002, sv=1, rt=0.0015, st=1, mat=1, uvscale=1.2)
        zb = st - board_t
        for sy in (-1, 1):
            rbox(P, (inner_w, 0.022, 0.045), (0, sy * (D / 2 - 0.011)), zb - 0.045, rv=0.002, sv=1, mat=0)   # step beams
        for sx in (-1, 1):
            rbox(P, (0.022, inner_d, 0.035), (sx * (W / 2 - POST / 2), 0), zb - 0.035, mat=0)                # side rails
        for sx in (-1, 1):           # label holders on the front beam, one per slot
            rbox(P, (0.12, 0.003, 0.032), (sx * W / 4, -D / 2 - 0.0015), zb - 0.04, mat=3)
    # top frame under the header + header backing board (sign mount)
    ztop = 1.56
    for sy in (-1, 1):
        rbox(P, (inner_w, 0.03, 0.04), (0, sy * (D / 2 - 0.015)), ztop, rv=0.002, sv=1, mat=0)
    for sx in (-1, 1):
        rbox(P, (0.03, inner_d, 0.04), (sx * (W / 2 - POST / 2), 0), ztop, mat=0)
    hb_y0 = -D / 2 + 0.002
    rbox(P, (W - 0.01, 0.018, H - 0.02 - (ztop + 0.04)), (0, hb_y0 + 0.009), ztop + 0.04, rv=0.003, sv=1,
         rt=0.004, st=1, mat=5)
    rbox(P, (W, D, 0.02), (0, 0), H - 0.02, rv=0.004, sv=1, rt=0.003, st=1, mat=0)                 # top cap
    # perforated back panel and side X-braces
    rbox(P, (inner_w, 0.003, ztop - 0.06), (0, D / 2 - 0.006), 0.06, mat=2, uvscale=5.0)
    flat = [(-0.0125, -0.0015), (0.0125, -0.0015), (0.0125, 0.0015), (-0.0125, 0.0015)]
    for sx in (-1, 1):
        x = sx * (W / 2 + 0.002)
        bays = [(0.06, LK_SHELVES[1] - 0.06), (LK_SHELVES[1] - 0.02, ztop)]
        for z0, z1 in bays:
            for a, b in (((x, -py, z0), (x, py, z1)), ((x, -py, z1), (x, py, z0))):
                sweep(P, [Vector(a), Vector(b)], flat, cap=True, side=(1, 0, 0), mat=0, v_scale=2.0)
    frame = to_object(P, mats, parent=root, smooth=35.0)
    # sign panel: separate node with UV 0..1, a few mm in front of the backing board
    sw, sh = W - 2 * POST - 0.03, (H - 0.02) - (ztop + 0.04) - 0.04
    sc = Vector((0, hb_y0 - 0.0008, ztop + 0.04 + 0.02 + sh / 2))
    sign = screen_quad("SignPanel", sign_mat, sw, sh, sc, root)
    slots = []
    for r, st in enumerate(LK_SHELVES):
        for c, sx in enumerate((-1, 1)):
            i = r * 2 + c
            loc = (sx * W / 4, 0.0, st)
            child_empty("Slot_%d" % i, root, loc)
            slots.append(gd(loc))
    root["slots"] = slots                      # index i == node Slot_i
    root["slot_order"] = "Slot_0/1 top shelf left/right (seen from the front), 2/3 middle, 4/5 bottom"
    root["slot_size"] = [round(W / 2 - POST - 0.01, 3), round(LK_SHELVES[0] - LK_SHELVES[1] - 0.063, 3), round(D - 0.02, 3)]
    root["sign_center"] = gd(sc)
    root["sign_size"] = [round(sw, 5), round(sh, 5)]
    root["sign_normal"] = [0.0, 0.0, 1.0]
    root["extras_space"] = "godot_local"
    info = export("pickup_locker")
    info["extras"] = extras_of(root)
    show_grid([sign_mat])
    info["qa"] = qa_render("pickup_locker", (("", (1.0, -1.7, 0.75)), ("_back", (-1.1, 1.6, 0.8)),
                                             ("_front", (0.0, -1.0, 0.05))), lens=60)
    REPORT["pickup_locker"] = info


# ----------------------------------------------------------------------------- main
def main():
    if wanted("phone"):
        build_phone()
    if wanted("kiosk"):
        build_kiosk()
    if wanted("kiosk_stand"):
        build_kiosk_stand()
    if wanted("arrow"):
        build_arrow()
    if wanted("locker"):
        build_locker()
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
