"""Street-asset library for Mert Road Studio v2 (Blender 5.2, headless-safe).

`build_assets()` (re)creates the collections the road group instances from - MRS_Props, MRS_Streetlights,
MRS_Trees, MRS_Signs, MRS_TrafficLights, MRS_Barriers, MRS_Pillars, MRS_Scatter, MRS_Manholes, MRS_Drains,
MRS_Markings (identical to props.py) - plus MRS_Structures (gantry, pylon, abutment, tunnel portal ...).
Every object is a single mesh with box UVs, bevelled hard edges, consistent normals and node materials
with a touch of noise variation. Conventions: origin at the base centre, local +Y faces the road, barriers
run along local Y (road side -X), pillars / pylon are 1 m tall units scaled in Z by the generator.
`mark_assets(catalog_file)` turns everything into Asset Browser assets with catalogs and previews.
"""
import math, os, random
import bpy, bmesh
from mathutils import Vector, Matrix, noise
from .nodes import depsgraph, set_scene, MRS
from .props import collection, _poly, make

TAU = math.pi * 2.0
M = {}  # material registry filled by _materials()

# catalog UUIDs (uuid4, kept stable so re-saves keep assets in the same catalogs)
CATALOGS = {
    "Props": "1605bc53-d27b-4bb7-a78c-dd668f738b38", "Streetlights": "bbd23199-e035-42cf-9167-131303d730bf",
    "Trees": "ac0a7faa-83f4-4ebb-b693-dff866d63a78", "Signs": "4f2f80bb-401e-427f-a981-d078e094737f",
    "TrafficLights": "7bbde216-2407-4b41-87df-519c8fccc194", "Barriers": "8df2a941-fcee-45ce-a33c-e0ace8590cff",
    "Pillars": "4dcad8d4-bdae-4506-8d11-a7d05f2a97b9", "Scatter": "408301e2-38d0-4d7a-97ad-d12a18a0530f",
    "Manholes": "34c59fc3-4a2e-45bc-802c-0798e945b8ba", "Drains": "b55006fa-5d39-4e1d-95c4-5c60cd56a7d8",
    "Markings": "e11fb747-7abf-4bc3-bbc0-0c5a42fed50e", "Structures": "a6c111b9-83c8-4b05-86c4-cc3505a7df04",
}
COLLECTIONS = tuple(CATALOGS)


# ============================================================================== materials
def pmat(name, rgb, rough=0.6, metal=0.0, var=0.12, scale=6.0, emit=None, emit_strength=0.0, alpha=1.0, rough_var=0.12):
    """Principled BSDF with object-space noise driving a colour ramp (tone) and the roughness."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (300, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-800, 0)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.location = (-600, 0)
    nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 4.0; nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-350, 50)
    lo = tuple(max(0.0, c * (1.0 - var)) for c in rgb); hi = tuple(min(1.0, c * (1.0 + var) + 0.03 * var) for c in rgb)
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (*lo, 1)
    ramp.color_ramp.elements[1].position = 0.65; ramp.color_ramp.elements[1].color = (*hi, 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-350, -300)
    mr.inputs["To Min"].default_value = max(0.0, rough - rough_var); mr.inputs["To Max"].default_value = min(1.0, rough + rough_var)
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    b.inputs["Metallic"].default_value = metal
    if emit is not None:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        try: m.surface_render_method = "BLENDED"
        except Exception: pass
    nt.links.new(b.outputs[0], out.inputs[0])
    m.diffuse_color = (*rgb, 1)
    return m


def _materials():
    P = MRS + "Prop"
    M.clear()
    M.update(
        metal=pmat(P + "Metal", (0.2, 0.21, 0.22), 0.45, 0.8, var=0.15), steel=pmat(P + "Steel", (0.55, 0.56, 0.58), 0.4, 0.9, var=0.18),
        iron=pmat(P + "Iron", (0.06, 0.06, 0.07), 0.55, 0.6, var=0.2), green=pmat(P + "Green", (0.12, 0.3, 0.1), 0.6, var=0.1),
        wood=pmat(P + "Wood", (0.45, 0.3, 0.18), 0.7, var=0.22, scale=14.0), concrete=pmat(P + "Concrete", (0.55, 0.55, 0.53), 0.85, var=0.12, scale=4.0),
        grey=pmat(P + "Grey", (0.3, 0.3, 0.3), 0.7, var=0.15), bark=pmat(P + "Bark", (0.3, 0.22, 0.15), 0.9, var=0.25, scale=10.0),
        red=pmat(P + "Red", (0.7, 0.1, 0.08), 0.5, var=0.08), yellow=pmat(P + "Yellow", (0.9, 0.7, 0.08), 0.5, var=0.08),
        blue=pmat(P + "Blue", (0.08, 0.2, 0.55), 0.5, var=0.08), black=pmat(P + "Black", (0.02, 0.02, 0.025), 0.5, var=0.1),
        white=pmat(P + "White", (0.9, 0.9, 0.88), 0.45, var=0.04), rubber=pmat(P + "Rubber", (0.05, 0.05, 0.05), 0.9, var=0.1),
        soil=pmat(P + "Soil", (0.16, 0.11, 0.07), 0.95, var=0.3, scale=20.0), rock=pmat(P + "Rock", (0.4, 0.38, 0.35), 0.9, var=0.35, scale=5.0),
        lamp=pmat(P + "Lamp", (1.0, 0.95, 0.8), 0.3, var=0.0, emit=(1.0, 0.93, 0.75), emit_strength=5.0),
        glass=pmat(P + "Glass", (0.75, 0.85, 0.9), 0.05, var=0.0, alpha=0.3, rough_var=0.02),
        lens_red=pmat(P + "LensRed", (0.9, 0.05, 0.02), 0.2, var=0.0, emit=(1.0, 0.05, 0.02), emit_strength=3.0),
        lens_amber=pmat(P + "LensAmber", (0.95, 0.55, 0.02), 0.2, var=0.0, emit=(1.0, 0.6, 0.05), emit_strength=3.0),
        lens_green=pmat(P + "LensGreen", (0.05, 0.8, 0.25), 0.2, var=0.0, emit=(0.1, 1.0, 0.35), emit_strength=3.0),
        sign_white=pmat(P + "SignWhite", (0.92, 0.92, 0.9), 0.35, var=0.03), sign_red=pmat(P + "SignRed", (0.75, 0.05, 0.04), 0.35, var=0.04),
        sign_blue=pmat(P + "SignBlue", (0.04, 0.18, 0.6), 0.35, var=0.04), sign_yellow=pmat(P + "SignYellow", (0.95, 0.75, 0.05), 0.35, var=0.04),
        sign_green=pmat(P + "SignGreen", (0.03, 0.3, 0.12), 0.35, var=0.04),
        leaf_conifer=pmat(P + "LeafConifer", (0.05, 0.17, 0.07), 0.85, var=0.3, scale=3.0), leaf_oak=pmat(P + "LeafOak", (0.1, 0.3, 0.07), 0.85, var=0.3, scale=3.0),
        leaf_poplar=pmat(P + "LeafPoplar", (0.18, 0.38, 0.1), 0.85, var=0.3, scale=3.0), leaf_palm=pmat(P + "LeafPalm", (0.14, 0.4, 0.12), 0.75, var=0.25, scale=3.0),
        leaf_maple=pmat(P + "LeafMaple", (0.62, 0.24, 0.05), 0.85, var=0.35, scale=3.0), leaf_birch=pmat(P + "LeafBirch", (0.35, 0.55, 0.15), 0.85, var=0.3, scale=3.0),
        leaf_bush=pmat(P + "LeafBush", (0.1, 0.27, 0.08), 0.85, var=0.3, scale=4.0), bark_birch=pmat(P + "BarkBirch", (0.82, 0.82, 0.78), 0.8, var=0.3, scale=12.0),
        grass=pmat(P + "Grass", (0.17, 0.4, 0.08), 0.85, var=0.35, scale=8.0), flower=pmat(P + "Flower", (0.92, 0.65, 0.1), 0.6, var=0.2),
        flower2=pmat(P + "Flower2", (0.6, 0.2, 0.7), 0.6, var=0.2),
    )
    M["paint"] = bpy.data.materials.get(MRS + "Paint") or pmat(MRS + "Paint", (0.9, 0.9, 0.85), 0.5, var=0.05)
    return M


# ============================================================================== bmesh primitives
def _box(bm, x0, y0, z0, x1, y1, z1, mi=0):
    v = [bm.verts.new((x, y, z)) for x, y, z in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f]).material_index = mi


def _cyl(bm, x, y, z0, z1, r0, r1, n=12, mi=0, smooth=True, caps=True):
    a = [bm.verts.new((x + r0 * math.cos(TAU * i / n), y + r0 * math.sin(TAU * i / n), z0)) for i in range(n)]
    b = [bm.verts.new((x + r1 * math.cos(TAU * i / n), y + r1 * math.sin(TAU * i / n), z1)) for i in range(n)]
    for i in range(n):
        f = bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i])); f.material_index = mi; f.smooth = smooth
    if caps:
        bm.faces.new(list(reversed(a))).material_index = mi; bm.faces.new(b).material_index = mi


def _tube(bm, pts, r, n=8, mi=0, caps=True, smooth=True):
    """Round tube along a polyline (parallel-transport frames)."""
    pts = [Vector(p) for p in pts]; rings = []; u = None
    for i, p in enumerate(pts):
        if i == 0: d = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1: d = (pts[-1] - pts[-2]).normalized()
        else: d = ((pts[i] - pts[i - 1]).normalized() + (pts[i + 1] - pts[i]).normalized()).normalized()
        if u is None:
            a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0)); u = d.cross(a).normalized()
        else:
            u = (u - d * u.dot(d)).normalized()
        v = d.cross(u)
        rings.append([bm.verts.new(p + (u * math.cos(TAU * k / n) + v * math.sin(TAU * k / n)) * r) for k in range(n)])
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k])); f.material_index = mi; f.smooth = smooth
    if caps:
        bm.faces.new(rings[0][::-1]).material_index = mi; bm.faces.new(rings[-1]).material_index = mi


def _lathe(bm, profile, n=16, mi=0, x=0.0, y=0.0, smooth=True, caps=True):
    """Revolve a (radius, z) profile around a vertical axis; radius 0 makes a pole vertex."""
    rings = []
    for r, z in profile:
        if r <= 1e-6: rings.append(bm.verts.new((x, y, z)))
        else: rings.append([bm.verts.new((x + r * math.cos(TAU * k / n), y + r * math.sin(TAU * k / n), z)) for k in range(n)])
    for a, b in zip(rings, rings[1:]):
        if isinstance(a, list) and isinstance(b, list):
            for k in range(n):
                f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k])); f.material_index = mi; f.smooth = smooth
        elif isinstance(a, list):
            for k in range(n):
                f = bm.faces.new((a[k], a[(k + 1) % n], b)); f.material_index = mi; f.smooth = smooth
        elif isinstance(b, list):
            for k in range(n):
                f = bm.faces.new((a, b[(k + 1) % n], b[k])); f.material_index = mi; f.smooth = smooth
    if caps:
        if isinstance(rings[0], list): bm.faces.new(rings[0][::-1]).material_index = mi
        if isinstance(rings[-1], list): bm.faces.new(rings[-1]).material_index = mi


def _prism(bm, pts, a0, a1, mi=0, axis="y"):
    """Extrude a 2D polygon between a0 and a1 along `axis`. pts are (x,z) for axis y, (x,y) for z, (y,z) for x."""
    def P(p, a):
        return (p[0], a, p[1]) if axis == "y" else ((p[0], p[1], a) if axis == "z" else (a, p[0], p[1]))
    v0 = [bm.verts.new(P(p, a0)) for p in pts]; v1 = [bm.verts.new(P(p, a1)) for p in pts]
    bm.faces.new(v0[::-1]).material_index = mi; bm.faces.new(v1).material_index = mi
    n = len(pts)
    for i in range(n): bm.faces.new((v0[i], v0[(i + 1) % n], v1[(i + 1) % n], v1[i])).material_index = mi


def _band(bm, outer, inner, a0, a1, mi=0, axis="y", closed=True):
    """Ring between two same-length polygons (border of a sign plate), extruded like _prism.
    closed=False makes an open strip (arch) with end caps."""
    def P(p, a):
        return (p[0], a, p[1]) if axis == "y" else ((p[0], p[1], a) if axis == "z" else (a, p[0], p[1]))
    n = len(outer)
    o0 = [bm.verts.new(P(p, a0)) for p in outer]; o1 = [bm.verts.new(P(p, a1)) for p in outer]
    i0 = [bm.verts.new(P(p, a0)) for p in inner]; i1 = [bm.verts.new(P(p, a1)) for p in inner]
    if not closed:
        bm.faces.new((o0[0], i0[0], i1[0], o1[0])).material_index = mi
        bm.faces.new((o0[-1], o1[-1], i1[-1], i0[-1])).material_index = mi
    for k in range(n if closed else n - 1):
        j = (k + 1) % n
        bm.faces.new((o1[k], o1[j], i1[j], i1[k])).material_index = mi
        bm.faces.new((o0[j], o0[k], i0[k], i0[j])).material_index = mi
        bm.faces.new((o0[k], o0[j], o1[j], o1[k])).material_index = mi
        bm.faces.new((i0[j], i0[k], i1[k], i1[j])).material_index = mi


def _ico(bm, center, radius, subdiv=3, scale=(1, 1, 1), amp=0.0, freq=1.0, seed=0, mi=0, zmin=None, smooth=True):
    """Icosphere (subdiv 3 = 162 verts, 4 = 642), optionally squashed and noise-displaced, clamped to zmin."""
    ret = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    c = Vector(center); off = Vector((seed * 13.7, seed * 7.1, seed * 3.3))
    for v in ret["verts"]:
        p = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
        if amp: p += p.normalized() * noise.noise(p * freq + off) * amp * radius
        v.co = c + p
        if zmin is not None and v.co.z < zmin: v.co.z = zmin
    for f in {f for v in ret["verts"] for f in v.link_faces}: f.material_index = mi; f.smooth = smooth
    return ret["verts"]


def _blade(bm, base, height, width, direction, bend=0.35, segs=3, mi=0):
    """A single bent, tapering grass blade (open ribbon)."""
    bx, by = base; dx, dy = direction; px, py = -dy, dx; rows = []
    for i in range(segs + 1):
        t = i / segs; z = height * t * (1.0 - 0.12 * t); lean = bend * height * t * t
        cx, cy = bx + dx * lean, by + dy * lean
        if i == segs: rows.append([bm.verts.new((cx, cy, z))])
        else:
            w = width * (1.0 - 0.8 * t) * 0.5
            rows.append([bm.verts.new((cx - px * w, cy - py * w, z)), bm.verts.new((cx + px * w, cy + py * w, z))])
    for a, b in zip(rows, rows[1:]):
        f = bm.faces.new((a[0], a[1], b[1], b[0]) if len(b) == 2 else (a[0], a[1], b[0])); f.material_index = mi; f.smooth = True


def _cone_tier(bm, z0, z1, r, n, rnd, mi):
    """Conifer tier: jittered outer ring, folded mid ring, tip; closed by a bottom cap."""
    a = []
    for k in range(n):
        ang = TAU * k / n; rr = r * (0.85 + 0.3 * rnd.random())
        a.append(bm.verts.new((rr * math.cos(ang), rr * math.sin(ang), z0 + 0.15 * r * rnd.random())))
    zm = z0 + (z1 - z0) * 0.45
    b = [bm.verts.new((r * 0.55 * math.cos(TAU * (k + 0.5) / n), r * 0.55 * math.sin(TAU * (k + 0.5) / n), zm + 0.1 * r * rnd.random())) for k in range(n)]
    tip = bm.verts.new((0.0, 0.0, z1))
    for k in range(n):
        j = (k + 1) % n
        for tri in ((a[k], a[j], b[k]), (a[j], b[j], b[k]), (b[k], b[j], tip)):
            f = bm.faces.new(tri); f.material_index = mi; f.smooth = True
    bm.faces.new(a[::-1]).material_index = mi


def _arc(p0, p1, c, n=8):
    """Quadratic bezier points p0 -> p1 with control c."""
    p0, p1, c = Vector(p0), Vector(p1), Vector(c)
    return [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t * t * p1 for t in (i / n for i in range(n + 1))]


# ---- 2D shape helpers (x, z) for sign plates and legends
def _ngon(n, r, rot=0.0): return [(r * math.cos(rot + TAU * i / n), r * math.sin(rot + TAU * i / n)) for i in range(n)]


def _shape(kind, s, w=None):
    if kind == "octagon": return _ngon(8, s / 2 / math.cos(math.pi / 8), math.pi / 8)
    if kind == "circle": return _ngon(32, s / 2)
    if kind == "triangle": return [(-0.577 * s, s / 2), (0.577 * s, s / 2), (0.0, -s / 2)]
    if kind == "triangle_up": return [(-0.577 * s, -s / 2), (0.0, s / 2), (0.577 * s, -s / 2)][::-1]
    if kind == "diamond": return [(0, s / 2), (-s / 2, 0), (0, -s / 2), (s / 2, 0)]
    if kind == "square": return [(-s / 2, -s / 2), (s / 2, -s / 2), (s / 2, s / 2), (-s / 2, s / 2)]
    w = w if w is not None else s * 1.6
    return [(-w / 2, -s / 2), (w / 2, -s / 2), (w / 2, s / 2), (-w / 2, s / 2)]


def _inset(pts, d):
    cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
    apo = 1e9
    for (x0, z0), (x1, z1) in zip(pts, pts[1:] + pts[:1]):
        ex, ez = x1 - x0, z1 - z0; L = math.hypot(ex, ez)
        apo = min(apo, abs(ex * (cz - z0) - ez * (cx - x0)) / L)
    k = max(0.05, (apo - d) / apo)
    return [(cx + (x - cx) * k, cz + (z - cz) * k) for x, z in pts]


def _xf(pts, ang=0.0, dx=0.0, dz=0.0, s=1.0):
    c, sn = math.cos(ang), math.sin(ang)
    return [((x * c - z * sn) * s + dx, (x * sn + z * c) * s + dz) for x, z in pts]


def _arrow_pts(L, ws, wh, hh):
    return [(-ws / 2, 0), (ws / 2, 0), (ws / 2, L - hh), (wh / 2, L - hh), (0, L), (-wh / 2, L - hh), (-ws / 2, L - hh)]


def _stroke(bm, pts, w, y0, y1, mi, ext=None):
    """Thick 2D polyline (x,z) as overlapping rectangular prisms along Y."""
    ext = w / 2 if ext is None else ext
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        dx, dz = x1 - x0, z1 - z0; L = math.hypot(dx, dz)
        if L < 1e-6: continue
        ux, uz = dx / L, dz / L; nx, nz = -uz * w / 2, ux * w / 2
        ax, az, bx, bz = x0 - ux * ext, z0 - uz * ext, x1 + ux * ext, z1 + uz * ext
        _prism(bm, [(ax + nx, az + nz), (bx + nx, bz + nz), (bx - nx, bz - nz), (ax - nx, az - nz)], y0, y1, mi)


def _figure(bm, cx, cz, h, y0, y1, mi, stride=0.22, arms=True):
    hr = 0.085 * h
    _prism(bm, _xf(_ngon(10, hr), dx=cx, dz=cz + h - hr), y0, y1, mi)
    w = 0.1 * h
    _stroke(bm, [(cx, cz + h - 2.2 * hr), (cx, cz + 0.45 * h)], w * 1.7, y0, y1, mi)
    _stroke(bm, [(cx, cz + 0.47 * h), (cx - stride * h, cz)], w, y0, y1, mi)
    _stroke(bm, [(cx, cz + 0.47 * h), (cx + stride * h * 0.8, cz)], w, y0, y1, mi)
    if arms:
        _stroke(bm, [(cx, cz + 0.74 * h), (cx + 0.24 * h, cz + 0.58 * h)], w * 0.8, y0, y1, mi)
        _stroke(bm, [(cx, cz + 0.74 * h), (cx - 0.2 * h, cz + 0.55 * h)], w * 0.8, y0, y1, mi)


# ---- text (font curve -> mesh), facing +Y, standing proud from y=0 to y=depth, centred on `at`
def _text_mesh(text, size, depth):
    cu = bpy.data.curves.new("MRS_tmp_text", type="FONT")
    cu.body = text; cu.size = size; cu.extrude = depth / 2; cu.resolution_u = 3; cu.align_x = "CENTER"; cu.fill_mode = "BOTH"
    ob = bpy.data.objects.new("MRS_tmp_text", cu); bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update(); dg = depsgraph()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob); bpy.data.curves.remove(cu)
    return me


def _text(bm, text, size, at=(0.0, 0.0, 0.0), rot_z=0.0, depth=0.002, mi=0, max_width=None):
    me = _text_mesh(text, size, depth)
    tb = bmesh.new(); tb.from_mesh(me); bpy.data.meshes.remove(me)
    if not tb.verts: tb.free(); return
    xs = [v.co.x for v in tb.verts]; ys = [v.co.y for v in tb.verts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2; w = max(xs) - min(xs)
    sx = min(1.0, max_width / w) if (max_width and w > 1e-6) else 1.0
    local = Matrix(((-sx, 0, 0, sx * cx), (0, 0, 1, depth / 2), (0, sx, 0, -sx * cy), (0, 0, 0, 1)))
    bmesh.ops.transform(tb, matrix=Matrix.Translation(Vector(at)) @ Matrix.Rotation(rot_z, 4, "Z") @ local, verts=tb.verts)
    lay = bm.faces.layers.int.get("nobevel"); tb.verts.index_update()
    vmap = {v.index: bm.verts.new(v.co) for v in tb.verts}
    for f in tb.faces:
        try: nf = bm.faces.new([vmap[v.index] for v in f.verts])
        except ValueError: continue
        nf.material_index = mi; nf.smooth = False
        if lay is not None: nf[lay] = 1
    tb.free()


# ============================================================================== finishing / object creation
def _uv(bm):
    """Simple box projection, 1 UV unit = 1 m."""
    uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    bm.normal_update()
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i])); a, b = ((1, 2), (0, 2), (0, 1))[ax]
        sgn = 1.0 if n[ax] >= 0 else -1.0
        for l in f.loops:
            co = l.vert.co; l[uv].uv = (co[a] * sgn, co[b]) if ax != 2 else (co[a], co[b] * sgn)


def _finish(bm, bevel=0.0, recalc=True, sharp=0.55):
    lay = bm.faces.layers.int.get("nobevel")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    if recalc and bm.faces: bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > 0.5
                 and not (lay is not None and any(f[lay] for f in e.link_faces))]
        if edges:
            verts = list({v for e in edges for v in e.verts})
            bmesh.ops.bevel(bm, geom=edges + verts, offset=bevel, offset_type="OFFSET", segments=1, profile=0.5, affect="EDGES", clamp_overlap=True, loop_slide=True)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    for e in bm.edges:
        if len(e.link_faces) == 2 and (e.calc_face_angle(0.0) > sharp or e.link_faces[0].smooth != e.link_faces[1].smooth): e.smooth = False
    if lay is not None: bm.faces.layers.int.remove(lay)
    _uv(bm)


def make2(col, name, builder, mats, bevel=0.0, recalc=True):
    """Build with `builder(bm)`, finish (normals, bevel, sharp edges, UVs) and link hidden into `col`."""
    bm = bmesh.new(); bm.faces.layers.int.new("nobevel")
    builder(bm)
    _finish(bm, bevel, recalc)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]): me.materials.append(m)
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.hide_render = True; o.hide_viewport = True
    return o


# ============================================================================== props
def _props():
    col = collection(MRS + "Props"); m = M

    def bollard_steel(bm):
        _lathe(bm, [(0.11, 0), (0.11, 0.05), (0.08, 0.05), (0.08, 0.95), (0.075, 1.0), (0.05, 1.05), (0.0, 1.06)], 16, 0)
        _cyl(bm, 0, 0, 0.78, 0.86, 0.083, 0.083, 16, 1)
    make2(col, "MRS_Bollard_Steel", bollard_steel, [m["steel"], m["white"]], 0.006)

    def bollard_iron(bm):
        _lathe(bm, [(0.14, 0), (0.14, 0.08), (0.1, 0.1), (0.09, 0.2), (0.11, 0.22), (0.09, 0.26), (0.08, 0.7), (0.1, 0.74), (0.085, 0.78), (0.08, 0.95), (0.11, 0.98), (0.11, 1.02), (0.06, 1.05), (0.0, 1.06)], 14, 0)
        _ico(bm, (0, 0, 1.14), 0.1, 2, mi=0)
    make2(col, "MRS_Bollard_Iron", bollard_iron, [m["iron"]], 0.006)

    def bollard_concrete(bm):
        _prism(bm, [(-0.18, -0.18), (0.18, -0.18), (0.18, 0.18), (-0.18, 0.18)], 0.0, 0.1, 0, "z")
        _lathe(bm, [(0.17, 0.1), (0.13, 0.75), (0.1, 0.8), (0.0, 0.8)], 4, 1, smooth=False)
        _cyl(bm, 0, 0, 0.5, 0.56, 0.146, 0.146, 4, 2, smooth=False)
    make2(col, "MRS_Bollard_Concrete", bollard_concrete, [m["concrete"], m["concrete"], m["red"]], 0.015)

    def bench_wood(bm):
        for x in (-0.82, 0.82):
            _box(bm, x - 0.02, -0.28, 0.0, x + 0.02, -0.2, 0.42, 0); _box(bm, x - 0.02, 0.2, 0.0, x + 0.02, 0.28, 0.42, 0)
            _box(bm, x - 0.02, -0.3, 0.38, x + 0.02, 0.3, 0.44, 0)
            _prism(bm, [(-0.3, 0.44), (-0.22, 0.44), (-0.3, 0.95), (-0.38, 0.95)], x - 0.02, x + 0.02, 0, "x")
            _box(bm, x - 0.03, -0.32, 0.0, x + 0.03, 0.32, 0.03, 0)
        for i in range(5): y = -0.22 + i * 0.11; _box(bm, -0.85, y, 0.44, 0.85, y + 0.08, 0.48, 1)
        for i in range(3):
            z = 0.52 + i * 0.14; t = (z - 0.44) / 0.51 * 0.08
            _prism(bm, [(-0.3 - t, z), (-0.22 - t, z), (-0.23 - t - 0.016, z + 0.1), (-0.31 - t - 0.016, z + 0.1)], -0.85, 0.85, 1, "x")
    make2(col, "MRS_Bench_Wood", bench_wood, [m["iron"], m["wood"]], 0.006)

    def bench_modern(bm):
        for x in (-0.7, 0.7): _box(bm, x - 0.2, -0.25, 0.0, x + 0.2, 0.25, 0.4, 0)
        for i in range(4): y = -0.24 + i * 0.125; _box(bm, -0.95, y, 0.4, 0.95, y + 0.1, 0.46, 1)
    make2(col, "MRS_Bench_Modern", bench_modern, [m["concrete"], m["wood"]], 0.012)

    def bin_round(bm):
        _lathe(bm, [(0.2, 0), (0.2, 0.06), (0.27, 0.06), (0.27, 0.88), (0.29, 0.9), (0.29, 0.93), (0.25, 0.95), (0.0, 0.95)], 18, 0)
        for z in (0.2, 0.45, 0.7): _cyl(bm, 0, 0, z, z + 0.03, 0.285, 0.285, 18, 0)
        _lathe(bm, [(0.3, 0.95), (0.3, 1.0), (0.22, 1.08), (0.0, 1.1)], 18, 1)
        _box(bm, -0.12, 0.2, 0.96, 0.12, 0.31, 1.04, 2)
    make2(col, "MRS_Bin_Round", bin_round, [m["steel"], m["metal"], m["black"]], 0.006)

    def bin_square(bm):
        _box(bm, -0.22, -0.22, 0.0, 0.22, 0.22, 0.1, 0); _box(bm, -0.25, -0.25, 0.1, 0.25, 0.25, 0.95, 1)
        _lathe(bm, [(0.37, 0.95), (0.37, 0.99), (0.3, 1.0), (0.0, 1.12)], 4, 1, smooth=False)
        _box(bm, -0.15, 0.25, 0.8, 0.15, 0.26, 0.93, 2); _box(bm, 0.25, -0.15, 0.8, 0.26, 0.15, 0.93, 2)
    make2(col, "MRS_Bin_Square", bin_square, [m["metal"], m["green"], m["black"]], 0.008)

    def hydrant(bm):
        _lathe(bm, [(0.14, 0), (0.14, 0.06), (0.1, 0.08), (0.1, 0.5), (0.13, 0.52), (0.13, 0.56), (0.1, 0.58), (0.1, 0.72), (0.12, 0.74), (0.08, 0.84), (0.0, 0.86)], 14, 0)
        _cyl(bm, 0, 0, 0.86, 0.92, 0.035, 0.035, 6, 1, smooth=False)
        for sx in (-1, 1): _tube(bm, [(sx * 0.09, 0, 0.42), (sx * 0.2, 0, 0.42)], 0.05, 10, 0); _tube(bm, [(sx * 0.2, 0, 0.42), (sx * 0.24, 0, 0.42)], 0.056, 10, 1)
        _tube(bm, [(0, 0.09, 0.36), (0, 0.19, 0.36)], 0.065, 10, 0); _tube(bm, [(0, 0.19, 0.36), (0, 0.22, 0.36)], 0.07, 10, 1)
    make2(col, "MRS_Hydrant", hydrant, [m["red"], m["iron"]], 0.006)

    def bike_rack(bm):
        for x in (-0.65, 0.0, 0.65):
            _tube(bm, [(x, -0.38, 0), (x, -0.38, 0.6), (x, -0.3, 0.72), (x, -0.15, 0.78), (x, 0.15, 0.78), (x, 0.3, 0.72), (x, 0.38, 0.6), (x, 0.38, 0)], 0.028, 10, 0)
            for y in (-0.38, 0.38): _cyl(bm, x, y, 0.0, 0.01, 0.06, 0.06, 10, 0)
    make2(col, "MRS_BikeRack", bike_rack, [m["steel"]])

    def planter(bm):
        _box(bm, -0.45, -0.45, 0.0, 0.45, 0.45, 0.5, 0); _box(bm, -0.48, -0.48, 0.5, 0.48, 0.48, 0.56, 0)
        _box(bm, -0.4, -0.4, 0.56, 0.4, 0.4, 0.57, 1)
        _ico(bm, (0.0, 0.0, 0.85), 0.4, 3, (1.1, 1.1, 0.8), 0.18, 2.5, 3, 2, zmin=0.57)
        _ico(bm, (0.2, -0.15, 1.0), 0.28, 2, (1, 1, 1), 0.15, 3.0, 4, 2); _ico(bm, (-0.22, 0.18, 0.95), 0.25, 2, (1, 1, 1), 0.15, 3.0, 5, 2)
        for i in range(6):
            a = TAU * i / 6; _ico(bm, (0.33 * math.cos(a), 0.33 * math.sin(a), 0.62 + 0.05 * (i % 2)), 0.04, 1, mi=3)
    make2(col, "MRS_Planter", planter, [m["concrete"], m["soil"], m["leaf_bush"], m["flower"]], 0.015)

    def bus_shelter(bm):
        for x in (-1.5, 1.5):
            for y in (-0.65, 0.65): _box(bm, x - 0.035, y - 0.035, 0.0, x + 0.035, y + 0.035, 2.4, 0)
        _box(bm, -1.65, -0.8, 2.4, 1.65, 0.85, 2.5, 0); _box(bm, -1.65, 0.8, 2.3, 1.65, 0.85, 2.5, 0)
        _box(bm, -1.46, -0.66, 0.1, 1.46, -0.654, 2.35, 1)
        for x in (-1.5, 1.5): _box(bm, x - 0.003, -0.62, 0.1, x + 0.003, 0.3, 2.35, 1)
        _box(bm, -1.5, -0.68, 0.0, 1.5, -0.6, 0.1, 0)
        for i in range(3): y = -0.5 + i * 0.1; _box(bm, -1.2, y, 0.45, 1.2, y + 0.08, 0.48, 2)
        for x in (-1.1, 1.1): _box(bm, x - 0.02, -0.5, 0.0, x + 0.02, -0.22, 0.45, 0)
        _box(bm, 1.3, -0.6, 0.6, 1.49, 0.2, 2.2, 3)
    make2(col, "MRS_BusShelter", bus_shelter, [m["metal"], m["glass"], m["wood"], m["blue"]], 0.008)

    def mailbox(bm):
        _lathe(bm, [(0.24, 0), (0.24, 0.12), (0.2, 0.14), (0.2, 1.28), (0.24, 1.32), (0.24, 1.38), (0.2, 1.42), (0.1, 1.5), (0.0, 1.52)], 18, 0)
        _box(bm, -0.14, 0.19, 1.12, 0.14, 0.21, 1.15, 1); _box(bm, -0.12, 0.19, 0.7, 0.12, 0.205, 0.95, 2)
    make2(col, "MRS_Mailbox", mailbox, [m["red"], m["black"], m["white"]], 0.006)

    def kiosk(bm):
        for x in (-0.5, 0.5):
            for y in (-0.5, 0.5): _box(bm, x - 0.04, y - 0.04, 0.0, x + 0.04, y + 0.04, 2.3, 0)
        _box(bm, -0.55, -0.55, 0.0, 0.55, 0.55, 0.08, 0); _box(bm, -0.55, -0.55, 2.3, 0.55, 0.55, 2.4, 0)
        _lathe(bm, [(0.8, 2.4), (0.8, 2.44), (0.2, 2.62), (0.0, 2.64)], 4, 0, smooth=False)
        _box(bm, -0.46, -0.504, 0.1, 0.46, -0.496, 2.2, 1); _box(bm, -0.504, -0.46, 0.1, -0.496, 0.46, 2.2, 1); _box(bm, 0.496, -0.46, 0.1, 0.504, 0.46, 2.2, 1)
        _box(bm, -0.46, 0.496, 0.1, 0.46, 0.504, 2.2, 1); _box(bm, -0.02, 0.5, 0.1, 0.02, 0.54, 2.2, 0)
        _box(bm, 0.1, 0.5, 1.0, 0.14, 0.58, 1.15, 0); _box(bm, -0.5, -0.5, 2.2, 0.5, 0.5, 2.3, 2)
    make2(col, "MRS_Kiosk", kiosk, [m["blue"], m["glass"], m["white"]], 0.008)

    def newspaper_box(bm):
        for x in (-0.18, 0.18):
            for y in (-0.15, 0.15): _box(bm, x - 0.02, y - 0.02, 0.0, x + 0.02, y + 0.02, 0.35, 0)
        _box(bm, -0.22, -0.2, 0.35, 0.22, 0.2, 1.1, 1); _box(bm, -0.18, 0.2, 0.7, 0.18, 0.206, 1.02, 2)
        _box(bm, -0.18, 0.2, 0.42, 0.18, 0.21, 0.62, 3); _box(bm, -0.06, 0.2, 0.62, 0.06, 0.24, 0.7, 0)
    make2(col, "MRS_NewspaperBox", newspaper_box, [m["metal"], m["yellow"], m["glass"], m["white"]], 0.006)

    def picnic_table(bm):
        for i in range(5): y = -0.37 + i * 0.15; _box(bm, -0.9, y, 0.72, 0.9, y + 0.13, 0.76, 0)
        for y in (-0.72, 0.6): _box(bm, -0.9, y, 0.44, 0.9, y + 0.13, 0.48, 0)
        for x in (-0.6, 0.6):
            _prism(bm, [(-0.3, 0.72), (-0.2, 0.72), (-0.7, 0.0), (-0.8, 0.0)], x - 0.025, x + 0.025, 1, "x")
            _prism(bm, [(0.3, 0.72), (0.2, 0.72), (0.7, 0.0), (0.8, 0.0)][::-1], x - 0.025, x + 0.025, 1, "x")
            _box(bm, x - 0.03, -0.75, 0.4, x + 0.03, 0.75, 0.44, 1); _box(bm, x - 0.03, -0.4, 0.68, x + 0.03, 0.4, 0.72, 1)
    make2(col, "MRS_PicnicTable", picnic_table, [m["wood"], m["wood"]], 0.006)

    def fence_post(bm):
        _box(bm, -0.06, -0.06, 0.0, 0.06, 0.06, 1.3, 0)
        _lathe(bm, [(0.085, 1.3), (0.0, 1.38)], 4, 0, smooth=False)
        for z in (0.4, 0.95): _box(bm, -0.5, 0.06, z, 0.5, 0.1, z + 0.1, 0)
    make2(col, "MRS_FencePost", fence_post, [m["wood"]], 0.01)

    def utility_pole(bm):
        _cyl(bm, 0, 0, 0, 9.0, 0.15, 0.1, 12, 0)
        _box(bm, -0.05, -0.95, 8.3, 0.05, 0.95, 8.4, 1)
        for y in (-0.75, 0.0, 0.75): _lathe(bm, [(0.05, 8.4), (0.05, 8.46), (0.035, 8.47), (0.05, 8.5), (0.05, 8.55), (0.0, 8.58)], 8, 2, y=y)
        for sy in (-1, 1): _tube(bm, [(0, sy * 0.1, 7.7), (0, sy * 0.8, 8.3)], 0.015, 6, 1)
        _cyl(bm, 0.38, 0, 7.0, 7.8, 0.22, 0.22, 14, 1); _box(bm, 0.1, -0.05, 7.4, 0.3, 0.05, 7.5, 1)
    make2(col, "MRS_UtilityPole", utility_pole, [m["wood"], m["metal"], m["white"]])
    return col


# ============================================================================== streetlights
def _pole(bm, h, r0=0.09, r1=0.05, mi=0, flange=True):
    if flange: _cyl(bm, 0, 0, 0, 0.03, 0.22, 0.22, 16, mi); _cyl(bm, 0, 0, 0.03, 0.6, 0.12, 0.1, 12, mi)
    _cyl(bm, 0, 0, 0.6 if flange else 0.0, h, r0, r1, 12, mi)


def _cobra(bm, y0, y1, z, mi_house, mi_lamp, w=0.14):
    _box(bm, -w, y0, z - 0.14, w, y1, z, mi_house)
    _prism(bm, [(-w, z - 0.14), (w, z - 0.14), (w * 0.7, z - 0.22), (-w * 0.7, z - 0.22)], y1 - 0.5, y1, mi_house)
    _box(bm, -w * 0.6, y1 - 0.45, z - 0.23, w * 0.6, y1 - 0.05, z - 0.22, mi_lamp)


def _streetlights():
    col = collection(MRS + "Streetlights"); m = M

    def highway(bm):
        _pole(bm, 9.4, 0.09, 0.055, 0); _tube(bm, _arc((0, 0, 9.3), (0, 2.4, 10.0), (0, 0.05, 10.0), 8), 0.045, 10, 0)
        _cobra(bm, 1.7, 2.7, 10.05, 0, 1)
    make2(col, "MRS_Light_Highway", highway, [m["steel"], m["lamp"]], 0.01)

    def double(bm):
        _pole(bm, 9.4, 0.1, 0.06, 0)
        for s in (1, -1):
            _tube(bm, _arc((0, 0, 9.3), (0, s * 1.9, 10.0), (0, 0, 10.0), 8), 0.045, 10, 0)
            if s > 0: _cobra(bm, 1.2, 2.2, 10.05, 0, 1)
            else:
                _box(bm, -0.14, -2.2, 9.91, 0.14, -1.2, 10.05, 0)
                _prism(bm, [(-0.14, 9.91), (0.14, 9.91), (0.1, 9.83), (-0.1, 9.83)], -2.2, -1.7, 0)
                _box(bm, -0.08, -2.15, 9.82, 0.08, -1.75, 9.83, 1)
    make2(col, "MRS_Light_Double", double, [m["steel"], m["lamp"]], 0.01)

    def lantern(bm):
        _lathe(bm, [(0.2, 0), (0.2, 0.05), (0.16, 0.08), (0.15, 0.35), (0.11, 0.42), (0.07, 0.5), (0.06, 1.0), (0.075, 1.05), (0.06, 1.1), (0.05, 3.25), (0.08, 3.3), (0.08, 3.38), (0.05, 3.42), (0.0, 3.42)], 14, 0)
        _lathe(bm, [(0.18, 3.42), (0.18, 3.47), (0.14, 3.47), (0.14, 3.5), (0.0, 3.5)], 4, 0, smooth=False)
        _lathe(bm, [(0.17, 3.5), (0.21, 4.0)], 4, 1, smooth=False, caps=False)
        for k in range(4):
            a = TAU * k / 4; _tube(bm, [(0.17 * math.cos(a), 0.17 * math.sin(a), 3.5), (0.21 * math.cos(a), 0.21 * math.sin(a), 4.0)], 0.012, 6, 0)
        _lathe(bm, [(0.25, 4.0), (0.25, 4.04), (0.08, 4.28), (0.08, 4.32), (0.0, 4.36)], 4, 0, smooth=False); _ico(bm, (0, 0, 4.4), 0.05, 2, mi=0)
        _ico(bm, (0, 0, 3.75), 0.09, 2, mi=2)
    make2(col, "MRS_Light_Lantern", lantern, [m["iron"], m["glass"], m["lamp"]], 0.006)

    def led(bm):
        _pole(bm, 7.0, 0.07, 0.05, 0); _tube(bm, [(0, 0, 6.95), (0, 0.9, 7.0)], 0.035, 8, 0)
        _prism(bm, [(-0.12, 7.03), (0.12, 7.03), (0.12, 6.97), (-0.12, 6.97)], 0.45, 1.15, 0)
        _box(bm, -0.1, 0.5, 6.965, 0.1, 1.1, 6.97, 1)
    make2(col, "MRS_Light_LED", led, [m["steel"], m["lamp"]], 0.008)

    def bollard_light(bm):
        _lathe(bm, [(0.1, 0), (0.1, 0.72), (0.09, 0.72)], 14, 0); _cyl(bm, 0, 0, 0.72, 0.9, 0.088, 0.088, 14, 1)
        _lathe(bm, [(0.1, 0.9), (0.1, 0.96), (0.06, 1.0), (0.0, 1.0)], 14, 0)
    make2(col, "MRS_Light_Bollard", bollard_light, [m["metal"], m["lamp"]], 0.006)

    def wall_pack(bm):
        _box(bm, -0.06, -0.06, 0.0, 0.06, 0.06, 3.5, 0); _box(bm, -0.15, -0.15, 0.0, 0.15, 0.15, 0.04, 0)
        _box(bm, -0.16, 0.06, 3.1, 0.16, 0.3, 3.35, 0)
        _prism(bm, [(-0.16, 3.1), (0.16, 3.1), (0.16, 3.35), (-0.16, 3.35)][::-1], 0.3, 0.32, 1)
    make2(col, "MRS_Light_WallPack", wall_pack, [m["metal"], m["lamp"]], 0.008)
    return col


# ============================================================================== trees
def _trees():
    col = collection(MRS + "Trees"); m = M

    def conifer(bm):
        rnd = random.Random(1); _cyl(bm, 0, 0, 0, 3.0, 0.2, 0.1, 10, 0)
        for i in range(6):
            t = i / 6; z0 = 1.3 + 7.2 * t; _cone_tier(bm, z0, z0 + 2.3, 2.1 * (1 - t) + 0.35, 24, rnd, 1)
    make2(col, "MRS_Tree_Conifer", conifer, [m["bark"], m["leaf_conifer"]])

    def spruce(bm):
        rnd = random.Random(7); _cyl(bm, 0, 0, 0, 2.0, 0.16, 0.08, 10, 0)
        for i in range(8):
            t = i / 8; z0 = 0.8 + 9.0 * t; _cone_tier(bm, z0, z0 + 2.0, 1.6 * (1 - t) + 0.3, 22, rnd, 1)
    make2(col, "MRS_Tree_Spruce", spruce, [m["bark"], m["leaf_conifer"]])

    def oak(bm):
        _lathe(bm, [(0.42, 0), (0.3, 0.3), (0.26, 1.5), (0.22, 2.6), (0.0, 2.7)], 10, 0)
        for p, s in (((0, 0, 4.4), 1), ((1.3, 0.6, 3.9), 2), ((-1.1, -0.6, 4.1), 3)): _tube(bm, [(0, 0, 2.3), p], 0.1, 7, 0)
        _ico(bm, (0, 0, 4.9), 2.3, 3, (1, 1, 0.8), 0.14, 1.2, 1, 1); _ico(bm, (1.5, 0.7, 4.2), 1.5, 3, (1, 1, 0.9), 0.15, 1.5, 2, 1)
        _ico(bm, (-1.3, -0.7, 4.5), 1.6, 3, (1, 1, 0.9), 0.15, 1.5, 3, 1)
    make2(col, "MRS_Tree_Oak", oak, [m["bark"], m["leaf_oak"]])

    def poplar(bm):
        _cyl(bm, 0, 0, 0, 3.5, 0.18, 0.08, 10, 0)
        _ico(bm, (0, 0, 6.2), 1.0, 4, (1, 1, 4.1), 0.1, 2.0, 4, 1)
    make2(col, "MRS_Tree_Poplar", poplar, [m["bark"], m["leaf_poplar"]])

    def palm(bm):
        pts = [(0.35 * (z / 7.0) ** 2, 0.0, z) for z in (0, 0.8, 1.6, 2.4, 3.2, 4.0, 4.8, 5.6, 6.4, 7.0)]
        _tube(bm, pts, 0.18, 10, 0); _ico(bm, (0.35, 0, 7.1), 0.3, 2, (1, 1, 0.8), mi=0)
        rnd = random.Random(3)
        for i in range(11):
            a = TAU * i / 11 + rnd.random() * 0.3; L = 2.8 + rnd.random() * 0.6; rows = []
            for k in range(7):
                t = k / 6; d = L * t; z = 7.2 + 1.1 * t - 1.6 * t * t; w = 0.28 * (1 - t) + 0.03
                cx, cy = 0.35 + d * math.cos(a), d * math.sin(a); px, py = -math.sin(a), math.cos(a)
                rows.append([bm.verts.new((cx - px * w, cy - py * w, z - 0.12 * (1 - t))), bm.verts.new((cx, cy, z)), bm.verts.new((cx + px * w, cy + py * w, z - 0.12 * (1 - t)))])
            for r0, r1 in zip(rows, rows[1:]):
                for j in range(2):
                    f = bm.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j])); f.material_index = 1; f.smooth = True
        for i in range(4): a = TAU * i / 4; _ico(bm, (0.35 + 0.25 * math.cos(a), 0.25 * math.sin(a), 6.95), 0.1, 1, mi=2)
    make2(col, "MRS_Tree_Palm", palm, [m["bark"], m["leaf_palm"], m["wood"]])

    def maple(bm):
        _lathe(bm, [(0.36, 0), (0.26, 0.3), (0.2, 2.2), (0.0, 2.4)], 10, 0)
        for p in ((0.8, 0.3, 3.6), (-0.7, -0.4, 3.8), (0.1, -0.8, 3.9)): _tube(bm, [(0, 0, 2.0), p], 0.08, 7, 0)
        _ico(bm, (0, 0, 4.6), 2.4, 3, (1, 1, 0.85), 0.14, 1.3, 5, 1); _ico(bm, (0.9, 0.3, 5.5), 1.5, 3, (1, 1, 0.9), 0.15, 1.6, 6, 1)
    make2(col, "MRS_Tree_Maple", maple, [m["bark"], m["leaf_maple"]])

    def birch(bm):
        _lathe(bm, [(0.16, 0), (0.12, 0.3), (0.09, 3.0), (0.05, 5.5), (0.0, 5.6)], 10, 0)
        for p in ((0.5, 0.2, 5.2), (-0.4, -0.3, 6.0)): _tube(bm, [(0, 0, 3.6), p], 0.04, 6, 0)
        _ico(bm, (0.1, 0, 5.3), 1.35, 3, (0.85, 0.85, 1.7), 0.12, 1.5, 8, 1); _ico(bm, (-0.5, -0.3, 6.4), 0.9, 3, (0.9, 0.9, 1.4), 0.12, 1.8, 9, 1)
    make2(col, "MRS_Tree_Birch", birch, [m["bark_birch"], m["leaf_birch"]])

    def bush(bm):
        _ico(bm, (0, 0, 0.7), 0.9, 3, (1.1, 1.0, 0.85), 0.16, 2.2, 11, 0, zmin=0.0)
        _ico(bm, (0.7, 0.3, 0.55), 0.65, 3, (1, 1, 0.9), 0.16, 2.5, 12, 0, zmin=0.0); _ico(bm, (-0.6, -0.4, 0.5), 0.6, 3, (1, 1, 0.9), 0.16, 2.5, 13, 0, zmin=0.0)
    make2(col, "MRS_Tree_Bush", bush, [m["leaf_bush"]])

    def sapling(bm):
        _cyl(bm, 0, 0, 0, 2.3, 0.035, 0.02, 8, 0); _ico(bm, (0, 0, 2.6), 0.55, 3, (1, 1, 1.4), 0.15, 3.0, 14, 1)
        _box(bm, 0.1, -0.025, 0.0, 0.15, 0.025, 1.7, 2); _box(bm, -0.01, -0.03, 1.4, 0.16, 0.03, 1.44, 3)
    make2(col, "MRS_Tree_Sapling", sapling, [m["bark"], m["leaf_oak"], m["wood"], m["rubber"]])
    return col


# ============================================================================== signs
S_POST, S_WHITE, S_BLACK, S_RED, S_BLUE, S_YELLOW, S_GREEN, S_BACK = range(8)


def _sign_mats():
    return [M["steel"], M["sign_white"], M["black"], M["sign_red"], M["sign_blue"], M["sign_yellow"], M["sign_green"], M["grey"]]


def _plate(bm, pts, zc, mi, post=True, y=0.045, x_post=0.0):
    """Post + clamp + plate (3 mm) centred at height zc facing +Y. Returns the front y of the plate."""
    top = zc + max(z for _, z in pts)
    if post:
        _cyl(bm, x_post, 0, 0, top - 0.04, 0.035, 0.035, 10, S_POST); _lathe(bm, [(0.038, top - 0.04), (0.0, top - 0.03)], 10, S_POST, x=x_post)
    _box(bm, x_post - 0.055, 0.0, zc - 0.03, x_post + 0.055, y - 0.001, zc + 0.03, S_POST)
    _prism(bm, [(x, z + zc) for x, z in pts], y - 0.004, y - 0.001, S_BACK)
    _prism(bm, [(x, z + zc) for x, z in pts], y - 0.001, y + 0.002, mi)
    return y + 0.002


def _border(bm, pts, zc, width, yf, mi):
    _band(bm, [(x, z + zc) for x, z in pts], [(x, z + zc) for x, z in _inset(pts, width)], yf, yf + 0.002, mi)
    return yf + 0.002


def _signs():
    col = collection(MRS + "Signs"); mats = _sign_mats(); Z = 2.4
    out = []

    def sign(name, fn):
        out.append(make2(col, "MRS_Sign_" + name, fn, mats))

    def stop(bm):
        pts = _shape("octagon", 0.8); yf = _plate(bm, pts, Z, S_RED); yf = _border(bm, pts, Z, 0.025, yf, S_WHITE)
        _text(bm, "STOP", 0.3, (0, yf, Z), mi=S_WHITE, max_width=0.62)
    sign("Stop", stop)

    def yield_(bm):
        pts = _shape("triangle", 0.9); yf = _plate(bm, pts, Z, S_WHITE); _border(bm, pts, Z, 0.1, yf, S_RED)
    sign("Yield", yield_)

    for v in (30, 50, 70, 90):
        def speed(bm, v=v):
            pts = _shape("circle", 0.75); yf = _plate(bm, pts, Z, S_WHITE); yf = _border(bm, pts, Z, 0.085, yf, S_RED)
            _text(bm, str(v), 0.36, (0, yf, Z), mi=S_BLACK)
        sign("Speed%d" % v, speed)

    def no_entry(bm):
        pts = _shape("circle", 0.75); yf = _plate(bm, pts, Z, S_RED); _prism(bm, [(-0.27, Z - 0.06), (0.27, Z - 0.06), (0.27, Z + 0.06), (-0.27, Z + 0.06)], yf, yf + 0.002, S_WHITE)
    sign("NoEntry", no_entry)

    def one_way(bm):
        pts = _shape("rect", 0.3, 1.0); yf = _plate(bm, pts, Z, S_BLUE)
        _prism(bm, _xf(_arrow_pts(0.8, 0.08, 0.18, 0.2), -math.pi / 2, -0.4, Z + 0.05), yf, yf + 0.002, S_WHITE)
        _text(bm, "ONE WAY", 0.07, (0, yf, Z - 0.08), mi=S_WHITE)
    sign("OneWay", one_way)

    def parking(bm):
        pts = _shape("square", 0.65); yf = _plate(bm, pts, Z, S_BLUE); yf = _border(bm, pts, Z, 0.02, yf, S_WHITE)
        _text(bm, "P", 0.45, (0, yf, Z), mi=S_WHITE)
    sign("Parking", parking)

    def no_parking(bm):
        pts = _shape("circle", 0.75); yf = _plate(bm, pts, Z, S_BLUE); yf = _border(bm, pts, Z, 0.07, yf, S_RED)
        _prism(bm, _xf([(-0.04, -0.34), (0.04, -0.34), (0.04, 0.34), (-0.04, 0.34)], math.radians(45), 0, Z), yf, yf + 0.002, S_RED)
    sign("NoParking", no_parking)

    def bus_stop(bm):
        pts = _shape("rect", 0.5, 0.7); yf = _plate(bm, pts, Z, S_WHITE); yf = _border(bm, pts, Z, 0.015, yf, S_BLACK)
        _text(bm, "BUS STOP", 0.09, (0, yf, Z - 0.16), mi=S_BLACK)
        _prism(bm, [(-0.22, Z - 0.05), (0.22, Z - 0.05), (0.22, Z + 0.17), (-0.22, Z + 0.17)], yf, yf + 0.002, S_BLACK)
        for x in (-0.14, 0.14): _prism(bm, _xf(_ngon(10, 0.04), dx=x, dz=Z - 0.06), yf, yf + 0.003, S_BLACK)
        for i in range(3): x = -0.16 + i * 0.12; _prism(bm, [(x, Z + 0.04), (x + 0.08, Z + 0.04), (x + 0.08, Z + 0.13), (x, Z + 0.13)], yf + 0.002, yf + 0.004, S_WHITE)
    sign("BusStop", bus_stop)

    def taxi(bm):
        pts = _shape("rect", 0.3, 0.8); yf = _plate(bm, pts, Z, S_YELLOW); yf = _border(bm, pts, Z, 0.015, yf, S_BLACK)
        _text(bm, "TAXI", 0.2, (0, yf, Z), mi=S_BLACK)
    sign("Taxi", taxi)

    def crossing(bm):
        pts = _shape("square", 0.65); yf = _plate(bm, pts, Z, S_BLUE); tri = _shape("triangle_up", 0.5)
        _prism(bm, [(x, z + Z - 0.02) for x, z in tri], yf, yf + 0.002, S_WHITE)
        _figure(bm, 0.02, Z - 0.22, 0.3, yf + 0.002, yf + 0.004, S_BLACK)
        for i in range(4): x = -0.18 + i * 0.1; _prism(bm, [(x, Z - 0.25), (x + 0.05, Z - 0.25), (x + 0.05, Z - 0.21), (x, Z - 0.21)], yf + 0.002, yf + 0.004, S_BLACK)
    sign("PedestrianCrossing", crossing)

    def children(bm):
        pts = _shape("triangle_up", 0.9); yf = _plate(bm, pts, Z, S_WHITE); yf = _border(bm, pts, Z, 0.08, yf, S_RED)
        _figure(bm, 0.07, Z - 0.3, 0.32, yf, yf + 0.002, S_BLACK, 0.3); _figure(bm, -0.09, Z - 0.3, 0.24, yf, yf + 0.002, S_BLACK, 0.3)
    sign("Children", children)

    def roundabout(bm):
        pts = _shape("circle", 0.75); yf = _plate(bm, pts, Z, S_BLUE); yf = _border(bm, pts, Z, 0.02, yf, S_WHITE)
        ring = _ngon(24, 0.2); _band(bm, [(x, z + Z) for x, z in ring], [(x, z + Z) for x, z in _ngon(24, 0.14)], yf, yf + 0.002, S_WHITE)
        for k in range(3):
            a = TAU * k / 3 + 0.4; tri = [(-0.07, -0.05), (0.07, -0.05), (0.0, 0.09)]
            _prism(bm, _xf(tri, a + math.pi / 2, 0.17 * math.cos(a), Z + 0.17 * math.sin(a)), yf, yf + 0.002, S_WHITE)
    sign("Roundabout", roundabout)

    def dead_end(bm):
        pts = _shape("square", 0.65); yf = _plate(bm, pts, Z, S_BLUE); yf = _border(bm, pts, Z, 0.02, yf, S_WHITE)
        _prism(bm, [(-0.05, Z - 0.26), (0.05, Z - 0.26), (0.05, Z + 0.14), (-0.05, Z + 0.14)], yf, yf + 0.002, S_WHITE)
        _prism(bm, [(-0.2, Z + 0.14), (0.2, Z + 0.14), (0.2, Z + 0.24), (-0.2, Z + 0.24)], yf, yf + 0.002, S_RED)
    sign("DeadEnd", dead_end)

    def give_way_ahead(bm):
        pts = _shape("triangle_up", 0.9); yf = _plate(bm, pts, Z, S_WHITE); yf = _border(bm, pts, Z, 0.08, yf, S_RED)
        tri = _shape("triangle", 0.3); _prism(bm, [(x, z + Z - 0.1) for x, z in tri], yf, yf + 0.002, S_BLACK)
        _prism(bm, [(x, z + Z - 0.1) for x, z in _inset(tri, 0.04)], yf + 0.002, yf + 0.004, S_WHITE)
        _text(bm, "AHEAD", 0.07, (0, yf, Z - 0.33), mi=S_BLACK)
    sign("GiveWayAhead", give_way_ahead)

    for nm, sgn in (("CurveLeft", -1), ("CurveRight", 1)):
        def curve(bm, sgn=sgn):
            pts = _shape("diamond", 0.9); yf = _plate(bm, pts, Z, S_YELLOW); yf = _border(bm, pts, Z, 0.02, yf, S_BLACK)
            _stroke(bm, [(0, Z - 0.22), (0, Z), (sgn * 0.05, Z + 0.1), (sgn * 0.16, Z + 0.17)], 0.07, yf, yf + 0.002, S_BLACK)
            tri = [(-0.09, -0.07), (0.09, -0.07), (0.0, 0.1)]
            _prism(bm, _xf(tri, -sgn * math.radians(62), sgn * 0.2, Z + 0.2), yf, yf + 0.002, S_BLACK)
        sign(nm, curve)

    def roadworks(bm):
        pts = _shape("triangle_up", 0.9); yf = _plate(bm, pts, Z, S_WHITE); yf = _border(bm, pts, Z, 0.08, yf, S_RED)
        _figure(bm, 0.0, Z - 0.3, 0.34, yf, yf + 0.002, S_BLACK, 0.2, arms=False)
        _stroke(bm, [(0.0, Z - 0.05), (0.14, Z - 0.17), (0.2, Z - 0.28)], 0.03, yf, yf + 0.002, S_BLACK)
        _prism(bm, [(0.1, Z - 0.3), (0.26, Z - 0.3), (0.2, Z - 0.2)][::-1], yf, yf + 0.002, S_BLACK)
    sign("Roadworks", roadworks)

    for nm, (a, b) in (("StreetName_A", ("MAPLE AVE", "3RD ST")), ("StreetName_B", ("HARBOUR RD", "KING ST"))):
        def blades(bm, a=a, b=b):
            _cyl(bm, 0, 0, 0, 2.75, 0.035, 0.035, 10, S_POST); _lathe(bm, [(0.04, 2.75), (0.0, 2.77)], 10, S_POST)
            r = [(-0.42, -0.1), (0.42, -0.1), (0.42, 0.1), (-0.42, 0.1)]
            _prism(bm, [(x, z + 2.62) for x, z in r], 0.035, 0.041, S_GREEN); _prism(bm, [(x, z + 2.62) for x, z in _inset(r, 0.012)], 0.041, 0.042, S_WHITE)
            _prism(bm, [(x, z + 2.62) for x, z in _inset(r, 0.016)], 0.042, 0.043, S_GREEN); _text(bm, a, 0.1, (0, 0.043, 2.62), mi=S_WHITE, max_width=0.72)
            _prism(bm, [(y, z + 2.4) for y, z in r], 0.035, 0.041, S_GREEN, "x"); _prism(bm, [(y, z + 2.4) for y, z in _inset(r, 0.012)], 0.041, 0.042, S_WHITE, "x")
            _prism(bm, [(y, z + 2.4) for y, z in _inset(r, 0.016)], 0.042, 0.043, S_GREEN, "x"); _text(bm, b, 0.1, (0.043, 0, 2.4), -math.pi / 2, mi=S_WHITE, max_width=0.72)
        sign(nm, blades)
    return col


def custom_sign(text, shape="rect", color=(0.05, 0.3, 0.1), size=0.9, name="MRS_Sign_Custom"):
    """A new sign object (post + plate + white text) linked to the scene collection, visible."""
    if not M: _materials()
    key = "%02x%02x%02x" % tuple(int(max(0.0, min(1.0, c)) * 255) for c in color[:3])
    face = pmat(MRS + "PropSignCustom_" + key, tuple(color[:3]), 0.35, var=0.04)
    mats = _sign_mats() + [face]; lines = [l for l in str(text).split("\n") if l.strip()] or [" "]
    h = size if shape != "rect" else size * 0.45
    pts = _shape(shape, h, size) if shape == "rect" else _shape(shape, size)
    zc = 2.4; n = len(lines)

    def build(bm):
        yf = _plate(bm, pts, zc, 8); yf = _border(bm, pts, zc, 0.02 * size, yf, S_WHITE)
        fit = 0.78 * (size if shape in ("rect", "square", "circle", "octagon") else size * 0.6)
        ts = min(h * 0.6 / n, 0.3 * size)
        for i, line in enumerate(lines):
            _text(bm, line, ts, (0, yf, zc + (n - 1) * ts * 0.6 - i * ts * 1.2), mi=S_WHITE, max_width=fit)
    bm = bmesh.new(); bm.faces.layers.int.new("nobevel"); build(bm); _finish(bm, 0.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for mm in mats: me.materials.append(mm)
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    return o


# ============================================================================== traffic lights
def _signal_head(bm, x, y, zb, mi_house, lenses, w=0.3, d=0.22):
    n = len(lenses); h = 0.05 + 0.3 * n
    _box(bm, x - d / 2, y - w / 2, zb, x + d / 2, y + w / 2, zb + h, mi_house)
    _box(bm, x - d / 2 - 0.01, y - w / 2 - 0.08, zb - 0.06, x - d / 2, y + w / 2 + 0.08, zb + h + 0.06, mi_house)
    for i, mi in enumerate(lenses):
        zc = zb + h - 0.025 - 0.15 - 0.3 * i
        _tube(bm, [(x - d / 2 - 0.005, y, zc), (x - d / 2 - 0.035, y, zc)], 0.1, 16, mi)
        _tube(bm, [(x - d / 2 - 0.01, y, zc), (x - d / 2 - 0.02, y, zc)], 0.115, 16, mi_house)
        a_, b_ = [], []
        for k in range(11):
            ang = math.pi * (-0.12 + 1.24 * k / 10)
            a_.append(bm.verts.new((x - d / 2 - 0.01, y + 0.125 * math.cos(ang), zc + 0.125 * math.sin(ang))))
            b_.append(bm.verts.new((x - d / 2 - 0.2, y + 0.115 * math.cos(ang), zc + 0.115 * math.sin(ang) - 0.03)))
        for k in range(10):
            f = bm.faces.new((a_[k], a_[k + 1], b_[k + 1], b_[k])); f.material_index = mi_house; f.smooth = True
    return zb + h


def _ped_unit(bm, x, y, zb, mi_house, mi_red, mi_green):
    _box(bm, x - 0.1, y - 0.13, zb, x + 0.1, y + 0.13, zb + 0.5, mi_house)
    _box(bm, x - 0.11, y - 0.1, zb + 0.28, x - 0.1, y + 0.1, zb + 0.46, mi_red); _box(bm, x - 0.11, y - 0.1, zb + 0.04, x - 0.1, y + 0.1, zb + 0.22, mi_green)
    _box(bm, x - 0.16, y - 0.14, zb + 0.46, x - 0.1, y + 0.14, zb + 0.5, mi_house); _box(bm, x - 0.16, y - 0.14, zb + 0.22, x - 0.1, y + 0.14, zb + 0.26, mi_house)


def _traffic_lights():
    col = collection(MRS + "TrafficLights"); m = M
    mats = [m["metal"], m["black"], m["lens_red"], m["lens_amber"], m["lens_green"], m["yellow"]]

    def vertical(bm):
        _cyl(bm, 0, 0, 0, 0.04, 0.16, 0.16, 12, 0); _cyl(bm, 0, 0, 0.04, 3.6, 0.07, 0.06, 12, 0)
        _signal_head(bm, 0.0, 0.0, 2.5, 1, (2, 3, 4)); _cyl(bm, 0, 0, 2.4, 2.5, 0.05, 0.05, 10, 0)
    make2(col, "MRS_Signal_Vertical", vertical, mats, 0.006)

    def pedestrian(bm):
        _cyl(bm, 0, 0, 0, 0.04, 0.16, 0.16, 12, 0); _cyl(bm, 0, 0, 0.04, 3.6, 0.07, 0.06, 12, 0)
        _signal_head(bm, 0.0, 0.0, 2.5, 1, (2, 3, 4)); _ped_unit(bm, 0.0, 0.0, 1.7, 1, 2, 4)
        _box(bm, -0.06, -0.08, 1.05, 0.08, 0.08, 1.25, 1); _tube(bm, [(-0.06, 0, 1.15), (-0.09, 0, 1.15)], 0.03, 10, 5)
    make2(col, "MRS_Signal_Pedestrian", pedestrian, mats, 0.006)

    def mast_arm(bm):
        _cyl(bm, 0, 0, 0, 0.05, 0.28, 0.28, 14, 0); _cyl(bm, 0, 0, 0.05, 6.4, 0.16, 0.1, 14, 0)
        _tube(bm, [(0, 0, 6.2), (0, 0.3, 6.25), (0, 5.0, 6.05)], 0.08, 10, 0)
        _tube(bm, [(0, 0.1, 5.0), (0, 2.2, 6.15)], 0.035, 8, 0)
        for y in (2.4, 4.6): _cyl(bm, 0, y, 4.9, 6.3, 0.03, 0.03, 8, 0); _signal_head(bm, 0.0, y, 4.0, 1, (2, 3, 4))
        _signal_head(bm, 0.0, 0.0, 3.0, 1, (2, 3, 4), w=0.26, d=0.2); _cyl(bm, 0, 0, 2.9, 3.0, 0.05, 0.05, 10, 0)
    make2(col, "MRS_Signal_MastArm", mast_arm, mats, 0.008)

    def push_button(bm):
        _cyl(bm, 0, 0, 0, 0.03, 0.12, 0.12, 12, 0); _cyl(bm, 0, 0, 0.03, 1.25, 0.05, 0.045, 12, 0)
        _box(bm, -0.06, -0.08, 0.95, 0.07, 0.08, 1.15, 1); _tube(bm, [(-0.06, 0, 1.05), (-0.09, 0, 1.05)], 0.03, 10, 5)
        _box(bm, -0.05, -0.1, 1.25, 0.05, 0.1, 1.4, 5); _box(bm, -0.051, -0.08, 1.28, -0.05, 0.08, 1.37, 1)
        _lathe(bm, [(0.055, 1.4), (0.0, 1.42)], 12, 0)
    make2(col, "MRS_Signal_PushButton", push_button, mats, 0.004)
    return col


# ============================================================================== barriers (2 m along Y, road side -X)
def _offset_polyline(pts, d):
    out = []
    for i, (x, z) in enumerate(pts):
        nx = nz = 0.0; segs = []
        if i > 0: segs.append((pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        if i < len(pts) - 1: segs.append((pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]))
        for dx, dz in segs:
            L = math.hypot(dx, dz); nx += dz / L; nz += -dx / L
        L = math.hypot(nx, nz); out.append((x + nx / L * d, z + nz / L * d))
    return out


def _barriers():
    col = collection(MRS + "Barriers"); m = M

    def guardrail(bm):
        front = [(-0.035, 0.76), (-0.1, 0.735), (-0.1, 0.675), (-0.045, 0.63), (-0.045, 0.585), (-0.1, 0.54), (-0.1, 0.48), (-0.035, 0.455)]
        back = _offset_polyline(front, 0.004)
        _prism(bm, front + back[::-1], -1.0, 1.0, 0)
        _box(bm, 0.0, -0.05, 0.0, 0.09, 0.05, 0.74, 1); _box(bm, -0.04, -0.06, 0.47, 0.0, 0.06, 0.745, 1)
        _tube(bm, [(-0.047, 0, 0.607), (-0.062, 0, 0.607)], 0.014, 8, 0)
        _box(bm, -0.108, -0.03, 0.688, -0.1, 0.03, 0.722, 2)
    make2(col, "MRS_Guardrail", guardrail, [m["steel"], m["metal"], m["white"]], 0.004)

    def jersey(bm):
        _prism(bm, [(-0.305, 0), (0.305, 0), (0.305, 0.075), (0.127, 0.33), (0.075, 0.81), (-0.075, 0.81), (-0.127, 0.33), (-0.305, 0.075)], -1.0, 1.0, 0)
        for y in (-0.6, 0.6): _box(bm, -0.03, y - 0.06, 0.78, 0.03, y + 0.06, 0.815, 1)
        _box(bm, -0.31, -0.1, 0.0, 0.31, 0.1, 0.05, 0)
    make2(col, "MRS_Jersey", jersey, [m["concrete"], m["metal"]], 0.012)

    def parapet(bm):
        _prism(bm, [(-0.3, 0), (0.22, 0), (0.22, 0.22), (-0.3, 0.22)], -1.0, 1.0, 0)
        _prism(bm, [(-0.3, 0.22), (0.22, 0.22), (0.22, 1.0), (-0.17, 1.0)], -1.0, 1.0, 0)
        _prism(bm, [(-0.3, 1.0), (0.3, 1.0), (0.3, 1.06), (0.27, 1.13), (0.0, 1.16), (-0.27, 1.13), (-0.3, 1.06)], -1.0, 1.0, 0)
        _box(bm, -0.32, -0.3, 1.0, 0.32, -0.28, 1.04, 0); _box(bm, 0.22, -0.9, 0.3, 0.25, 0.9, 0.9, 1)
    make2(col, "MRS_Parapet", parapet, [m["concrete"], m["concrete"]], 0.015)

    def railing(bm):
        _box(bm, -0.035, -0.035, 0.0, 0.035, 0.035, 1.1, 0); _box(bm, -0.07, -0.07, 0.0, 0.07, 0.07, 0.01, 0)
        for z, r in ((1.1, 0.025), (0.55, 0.012), (0.1, 0.012)): _tube(bm, [(0, -1.0, z), (0, 1.0, z)], r, 10, 0)
        for i in range(15):
            y = -1.0 + 0.125 * (i + 0.5)
            if abs(y) > 0.06: _cyl(bm, 0, y, 0.1, 1.1, 0.009, 0.009, 6, 0)
    make2(col, "MRS_Railing", railing, [m["steel"]])

    def hedge(bm):
        _ico(bm, (0, 0, 0.5), 1.0, 4, (0.32, 1.02, 0.52), 0.07, 3.0, 21, 0, zmin=0.0)
    make2(col, "MRS_Hedge", hedge, [m["leaf_bush"]])

    def fence(bm):
        _box(bm, -0.05, -0.05, 0.0, 0.05, 0.05, 1.15, 0); _lathe(bm, [(0.07, 1.15), (0.0, 1.21)], 4, 0, smooth=False)
        for z in (0.3, 0.85): _box(bm, -0.025, -1.0, z, 0.0, 1.0, z + 0.08, 0)
        for i in range(13):
            y = -1.0 + 0.155 * i + 0.03
            _box(bm, -0.045, y, 0.08, -0.025, y + 0.08, 1.0, 0)
            _prism(bm, [(y, 1.0), (y + 0.08, 1.0), (y + 0.04, 1.07)], -0.045, -0.025, 0, "x")
    make2(col, "MRS_Fence", fence, [m["wood"]], 0.004)
    return col


# ============================================================================== pillars (1 m tall units)
def _pillars():
    col = collection(MRS + "Pillars"); c = M["concrete"]; r = M["rubber"]

    def pads(bm, xs):
        for x in xs: _box(bm, x - 0.2, -0.2, 0.96, x + 0.2, 0.2, 1.0, 1)

    def rect_pier(bm):
        _box(bm, -1.6, -0.9, 0.0, 1.6, 0.9, 0.06, 0); _box(bm, -0.8, -0.5, 0.06, 0.8, 0.5, 0.84, 0)
        _prism(bm, [(-1.7, 0.84), (1.7, 0.84), (1.7, 0.94), (1.55, 0.96), (-1.55, 0.96), (-1.7, 0.94)], -0.6, 0.6, 0); pads(bm, (-1.2, 1.2))
    make2(col, "MRS_Pier_Rect", rect_pier, [c, r], 0.02)

    def twin_round(bm):
        for x in (-1.0, 1.0): _cyl(bm, x, 0, 0, 0.05, 0.6, 0.6, 16, 0); _cyl(bm, x, 0, 0.05, 0.82, 0.45, 0.45, 16, 0)
        _prism(bm, [(-1.7, 0.82), (1.7, 0.82), (1.7, 0.96), (-1.7, 0.96)], -0.6, 0.6, 0)
        _box(bm, -0.3, -0.35, 0.3, 0.3, 0.35, 0.5, 0); pads(bm, (-1.0, 1.0))
    make2(col, "MRS_Pier_TwinRound", twin_round, [c, r], 0.02)

    def hammerhead(bm):
        _box(bm, -1.0, -0.8, 0.0, 1.0, 0.8, 0.06, 0); _box(bm, -0.6, -0.45, 0.06, 0.6, 0.45, 0.72, 0)
        _prism(bm, [(-0.75, 0.72), (0.75, 0.72), (1.9, 0.88), (1.9, 0.96), (-1.9, 0.96), (-1.9, 0.88)], -0.5, 0.5, 0); pads(bm, (-1.3, 1.3))
    make2(col, "MRS_Pier_Hammerhead", hammerhead, [c, r], 0.02)
    return col


# ============================================================================== scatter / manholes / drains
def _grass(bm, n, h, spread, seed, mi=0, width=0.03):
    rnd = random.Random(seed)
    for i in range(n):
        a = TAU * i / n + rnd.random() * 0.5; d = spread * (0.3 + 0.7 * rnd.random())
        _blade(bm, (d * math.cos(a), d * math.sin(a)), h * (0.6 + 0.5 * rnd.random()), width, (math.cos(a), math.sin(a)), 0.25 + 0.3 * rnd.random(), 3, mi)


def _scatter():
    col = collection(MRS + "Scatter"); m = M
    for i, (n, h, s) in enumerate(((10, 0.3, 0.12), (14, 0.45, 0.16), (12, 0.6, 0.18), (16, 0.4, 0.22))):
        make2(col, "MRS_Grass%d" % (i + 1), lambda bm, n=n, h=h, s=s, i=i: _grass(bm, n, h, s, i + 1), [m["grass"]], recalc=False)

    def wildflower(bm):
        _grass(bm, 9, 0.3, 0.14, 9, 0)
        rnd = random.Random(5)
        for i in range(6):
            a = TAU * i / 6 + rnd.random(); d = 0.05 + 0.1 * rnd.random(); z = 0.26 + 0.14 * rnd.random(); x, y = d * math.cos(a), d * math.sin(a)
            _tube(bm, [(x, y, 0.0), (x * 1.2, y * 1.2, z)], 0.004, 5, 0); _ico(bm, (x * 1.2, y * 1.2, z + 0.02), 0.03, 1, (1, 1, 0.7), mi=1 + i % 2)
    make2(col, "MRS_Wildflower", wildflower, [m["grass"], m["flower"], m["flower2"]], recalc=False)

    def small_bush(bm):
        _ico(bm, (0, 0, 0.32), 0.42, 3, (1.1, 1.0, 0.8), 0.18, 3.0, 31, 0, zmin=0.0); _ico(bm, (0.3, 0.1, 0.22), 0.28, 2, (1, 1, 0.8), 0.18, 3.0, 32, 0, zmin=0.0)
    make2(col, "MRS_SmallBush", small_bush, [m["leaf_bush"]])

    make2(col, "MRS_Pebble", lambda bm: _ico(bm, (0, 0, 0.035), 0.07, 3, (1.3, 1.0, 0.6), 0.12, 6.0, 41, 0, zmin=0.0), [m["rock"]])
    make2(col, "MRS_Rock1", lambda bm: _ico(bm, (0, 0, 0.2), 0.35, 3, (1.3, 0.9, 0.7), 0.22, 2.5, 42, 0, zmin=0.0), [m["rock"]])
    make2(col, "MRS_Rock2", lambda bm: (_ico(bm, (0, 0, 0.3), 0.5, 3, (1.1, 1.3, 0.75), 0.25, 2.0, 43, 0, zmin=0.0), _ico(bm, (0.45, -0.2, 0.12), 0.22, 2, (1.2, 1.0, 0.7), 0.2, 3.0, 44, 0, zmin=0.0)), [m["rock"]])
    return col


def _manholes():
    col = collection(MRS + "Manholes"); m = M; T = 0.015

    def round1(bm):
        _cyl(bm, 0, 0, 0, T, 0.33, 0.33, 28, 0); _lathe(bm, [(0.3, T), (0.3, T + 0.003), (0.28, T + 0.003), (0.28, T), (0.3, T)], 28, 0, caps=False)
        for k in range(8):
            a = TAU * k / 8; _prism(bm, _xf([(-0.015, 0.06), (0.015, 0.06), (0.015, 0.26), (-0.015, 0.26)], a), T, T + 0.004, 1, "z")
    make2(col, "MRS_Manhole_Round1", round1, [m["iron"], m["metal"]])

    def round2(bm):
        _cyl(bm, 0, 0, 0, T, 0.35, 0.35, 28, 0); _cyl(bm, 0, 0, T, T + 0.003, 0.3, 0.3, 28, 1); _cyl(bm, 0, 0, T + 0.003, T + 0.006, 0.12, 0.12, 16, 0)
        for k in range(12):
            a = TAU * k / 12; _prism(bm, _xf([(-0.012, 0.16), (0.012, 0.16), (0.012, 0.27), (-0.012, 0.27)], a), T + 0.003, T + 0.006, 0, "z")
    make2(col, "MRS_Manhole_Round2", round2, [m["iron"], m["metal"]])

    def square(bm):
        _prism(bm, [(-0.33, -0.33), (0.33, -0.33), (0.33, 0.33), (-0.33, 0.33)], 0.0, T, 0, "z")
        _band(bm, [(-0.3, -0.3), (0.3, -0.3), (0.3, 0.3), (-0.3, 0.3)], [(-0.27, -0.27), (0.27, -0.27), (0.27, 0.27), (-0.27, 0.27)], T, T + 0.003, 1, "z")
        for i in range(4):
            for j in range(4):
                x, y = -0.24 + i * 0.13, -0.24 + j * 0.13
                _prism(bm, [(x, y), (x + 0.09, y), (x + 0.09, y + 0.09), (x, y + 0.09)], T, T + 0.003, 0, "z")
    make2(col, "MRS_Manhole_Square", square, [m["iron"], m["metal"]])
    return col


def _drains():
    col = collection(MRS + "Drains"); m = M

    def gully1(bm):
        _band(bm, [(-0.25, -0.2), (0.25, -0.2), (0.25, 0.2), (-0.25, 0.2)], [(-0.22, -0.17), (0.22, -0.17), (0.22, 0.17), (-0.22, 0.17)], 0.0, 0.01, 0, "z")
        _prism(bm, [(-0.22, -0.17), (0.22, -0.17), (0.22, 0.17), (-0.22, 0.17)], 0.0, 0.002, 1, "z")
        for i in range(7): x = -0.19 + i * 0.06; _box(bm, x, -0.17, 0.0, x + 0.025, 0.17, 0.01, 0)
    make2(col, "MRS_Gully1", gully1, [m["iron"], m["black"]])

    def gully2(bm):
        _band(bm, [(-0.25, -0.2), (0.25, -0.2), (0.25, 0.2), (-0.25, 0.2)], [(-0.22, -0.17), (0.22, -0.17), (0.22, 0.17), (-0.22, 0.17)], 0.0, 0.01, 0, "z")
        _prism(bm, [(-0.22, -0.17), (0.22, -0.17), (0.22, 0.17), (-0.22, 0.17)], 0.0, 0.002, 1, "z")
        _box(bm, -0.22, -0.012, 0.0, 0.22, 0.012, 0.01, 0)
        for i in range(7):
            y0 = -0.135 + i * 0.045; bar = [(-0.011, -0.05), (0.011, -0.05), (0.011, 0.05), (-0.011, 0.05)]
            _prism(bm, _xf(bar, 0.5, -0.11, y0), 0.0, 0.01, 0, "z"); _prism(bm, _xf(bar, -0.5, 0.11, y0), 0.0, 0.01, 0, "z")
    make2(col, "MRS_Gully2", gully2, [m["iron"], m["black"]])
    return col


# ============================================================================== markings (identical to props.py: order matters)
def _markings():
    paint = M["paint"]
    # markings: arrows (0 straight, 1 left, 2 right, 3 straight+left, 4 straight+right), 5 unit tick
    col = collection(MRS + "Markings")
    def shaft(bm, L=3.0): _poly(bm, [(-0.1, 0), (0.1, 0), (0.1, L), (-0.1, L)], 0.0)
    def head(bm, y=3.0): _poly(bm, [(-0.45, y), (0.45, y), (0.0, y + 1.0)], 0.0)
    def turn(bm, sgn):
        _poly(bm, [(0.0, 1.2), (0.0, 1.4), (sgn * 0.9, 1.4), (sgn * 0.9, 1.2)][::-1] if sgn < 0 else [(0.0, 1.2), (sgn * 0.9, 1.2), (sgn * 0.9, 1.4), (0.0, 1.4)], 0.0)
        tri = [(sgn * 0.9, 0.9), (sgn * 0.9, 1.7), (sgn * 1.5, 1.3)]
        _poly(bm, tri if sgn > 0 else tri[::-1], 0.0)
    make(col, "MRS_ArrowStraight", lambda bm: (shaft(bm), head(bm)), paint)
    make(col, "MRS_ArrowLeft", lambda bm: (shaft(bm, 1.4), turn(bm, -1)), paint)
    make(col, "MRS_ArrowRight", lambda bm: (shaft(bm, 1.4), turn(bm, 1)), paint)
    make(col, "MRS_ArrowStraightLeft", lambda bm: (shaft(bm), head(bm), turn(bm, -1)), paint)
    make(col, "MRS_ArrowStraightRight", lambda bm: (shaft(bm), head(bm), turn(bm, 1)), paint)
    make(col, "MRS_MarkTick", lambda bm: _poly(bm, [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)], 0.0), paint)
    for o in col.objects:  # markings are flat quads: give them the UV map the other assets have
        me = o.data
        if not me.uv_layers:
            uv = me.uv_layers.new(name="UVMap")
            for p in me.polygons:
                for li in p.loop_indices: co = me.vertices[me.loops[li].vertex_index].co; uv.data[li].uv = (co.x, co.y)
    return col


# ============================================================================== structures
def _structures():
    col = collection(MRS + "Structures"); m = M

    def gantry_post(bm):
        _box(bm, -0.45, -0.45, 0.0, 0.45, 0.45, 0.04, 0); _box(bm, -0.25, -0.25, 0.04, 0.25, 0.25, 7.0, 0)
        for x, y in ((-0.36, -0.36), (0.36, -0.36), (-0.36, 0.36), (0.36, 0.36)): _cyl(bm, x, y, 0.04, 0.1, 0.03, 0.03, 8, 0)
        _box(bm, -0.3, -0.3, 6.9, 0.3, 0.3, 7.0, 0)
        for z in (1.5, 3.0, 4.5, 6.0): _box(bm, -0.26, -0.26, z, 0.26, 0.26, z + 0.06, 0)
    make2(col, "MRS_GantryPost", gantry_post, [m["steel"]], 0.01)

    def gantry_beam(bm):
        for y in (-0.4, 0.4):
            for z in (-0.4, 0.4): _tube(bm, [(0, y, z), (1, y, z)], 0.05, 10, 0)
        for x in (0.0, 1.0):
            for y in (-0.4, 0.4): _tube(bm, [(x, y, -0.4), (x, y, 0.4)], 0.03, 8, 0)
            for z in (-0.4, 0.4): _tube(bm, [(x, -0.4, z), (x, 0.4, z)], 0.03, 8, 0)
        for y in (-0.4, 0.4): _tube(bm, [(0, y, -0.4), (1, y, 0.4)], 0.025, 6, 0)
        for z in (-0.4, 0.4): _tube(bm, [(0, -0.4, z), (1, 0.4, z)], 0.025, 6, 0)
    make2(col, "MRS_GantryBeam", gantry_beam, [m["steel"]])

    def gantry_sign(bm):
        r = [(-2.0, 0.0), (2.0, 0.0), (2.0, 1.5), (-2.0, 1.5)]
        _prism(bm, r, -0.006, 0.0, 7); _prism(bm, r, 0.0, 0.003, 6); _band(bm, r, _inset(r, 0.04), 0.003, 0.005, 1)
        _text(bm, "EXIT 12  ▲", 0.55, (0, 0.005, 0.75), mi=1, max_width=3.6)
        for x in (-1.5, 1.5): _box(bm, x - 0.04, -0.1, 0.1, x + 0.04, -0.006, 1.4, 0)
    make2(col, "MRS_GantrySign", gantry_sign, _sign_mats())

    def pylon(bm):
        for x in (-2.0, 2.0): _prism(bm, [(x - 0.35, 0.0), (x + 0.35, 0.0), (x + 0.25, 1.0), (x - 0.25, 1.0)], -0.3, 0.3, 0)
        _box(bm, -2.2, -0.28, 0.5, 2.2, 0.28, 0.58, 0); _box(bm, -2.3, -0.3, 0.94, 2.3, 0.3, 1.0, 0)
        for x in (-2.0, 2.0):
            for z in (0.7, 0.8, 0.9): _box(bm, x - 0.3, -0.06, z, x + 0.3, 0.06, z + 0.02, 1)
    make2(col, "MRS_Pylon", pylon, [m["concrete"], m["steel"]], 0.02)

    def abutment(bm):
        _box(bm, -5.0, -1.2, 0.0, 5.0, 0.0, 4.0, 0); _box(bm, -5.0, 0.0, 0.0, 5.0, 0.7, 3.2, 0)
        _box(bm, -5.6, -1.6, 0.0, 5.6, 0.2, 0.3, 0)
        for s in (-1, 1): _prism(bm, [(-1.2, 0.0), (-1.2, 4.0), (-4.2, 1.5), (-4.2, 0.0)], s * 5.0, s * 5.0 + s * 0.6, 0, "x")
        for x in (-3.0, 0.0, 3.0): _box(bm, x - 0.4, 0.1, 3.2, x + 0.4, 0.6, 3.3, 1)
    make2(col, "MRS_Abutment", abutment, [m["concrete"], m["rubber"]], 0.03)

    def tunnel_portal(bm):
        n = 24; inner = [(-6.0 * math.cos(math.pi * k / n), 6.0 * math.sin(math.pi * k / n)) for k in range(n + 1)]
        outer = []
        for x, z in inner:
            kx = 6.8 / abs(x) if abs(x) > 1e-6 else 1e9; kz = 7.2 / z if z > 1e-6 else 1e9; k = min(kx, kz)
            outer.append((x * k, z * k))
        _band(bm, outer, inner, 0.0, 1.0, 0, closed=False); _box(bm, -6.9, -0.12, 7.2, 6.9, 1.0, 7.6, 0)
        for s in (-1, 1): _box(bm, s * 6.5 - 0.3, -0.2, 0.0, s * 6.5 + 0.3, 0.0, 7.2, 0)
        _band(bm, inner, [(x * 0.95, z * 0.95) for x, z in inner], -0.06, 0.0, 1, closed=False)
    make2(col, "MRS_TunnelPortal", tunnel_portal, [m["concrete"], m["grey"]], 0.0)

    def bus_stop_shelter(bm):
        for x in (-2.0, 0.0, 2.0):
            for y in (-0.7, 0.7): _box(bm, x - 0.04, y - 0.04, 0.0, x + 0.04, y + 0.04, 2.5, 0)
        _box(bm, -2.2, -0.9, 2.5, 2.2, 0.95, 2.6, 0); _box(bm, -2.2, 0.9, 2.35, 2.2, 0.95, 2.6, 0)
        _box(bm, -1.96, -0.71, 0.1, 1.96, -0.704, 2.45, 1)
        for x in (-2.0, 2.0): _box(bm, x - 0.003, -0.66, 0.1, x + 0.003, 0.4, 2.45, 1)
        _box(bm, -2.0, -0.74, 0.0, 2.0, -0.66, 0.1, 0)
        for i in range(3): y = -0.55 + i * 0.1; _box(bm, -1.6, y, 0.45, 1.6, y + 0.08, 0.48, 2)
        for x in (-1.5, 0.0, 1.5): _box(bm, x - 0.02, -0.55, 0.0, x + 0.02, -0.27, 0.45, 0)
        _box(bm, 1.7, -0.65, 0.5, 1.96, 0.3, 2.3, 3)
        _cyl(bm, 2.6, 0.5, 0, 2.9, 0.035, 0.035, 10, 0); _box(bm, 2.3, 0.49, 2.4, 2.9, 0.51, 2.9, 3)
        _text(bm, "BUS", 0.18, (2.6, 0.51, 2.65), mi=4, max_width=0.5)
    make2(col, "MRS_BusStopShelter", bus_stop_shelter, [m["metal"], m["glass"], m["wood"], m["sign_blue"], m["sign_white"]], 0.008)

    def crosswalk_signal(bm):
        _cyl(bm, 0, 0, 0, 0.04, 0.16, 0.16, 12, 0); _cyl(bm, 0, 0, 0.04, 4.2, 0.07, 0.055, 12, 0)
        _tube(bm, [(0, 0, 4.1), (0, 1.6, 4.1)], 0.04, 8, 0)
        pts = _shape("diamond", 0.75); _box(bm, -0.05, 1.3, 3.65, 0.05, 1.42, 4.06, 0)
        _prism(bm, [(x, z + 3.3) for x, z in pts], 1.38, 1.4, 7); _prism(bm, [(x, z + 3.3) for x, z in pts], 1.4, 1.403, 5)
        _band(bm, [(x, z + 3.3) for x, z in pts], [(x, z + 3.3) for x, z in _inset(pts, 0.02)], 1.403, 1.405, 2)
        _figure(bm, 0.0, 3.08, 0.36, 1.403, 1.405, 2, 0.25)
        for s in (-1, 1): _cyl(bm, s * 0.3, 1.5, 4.12, 4.2, 0.08, 0.08, 10, 6); _lathe(bm, [(0.09, 4.2), (0.0, 4.22)], 10, 0, x=s * 0.3, y=1.5)
        _ped_unit(bm, 0.0, 0.0, 2.2, 1, 3, 4)
        _box(bm, -0.06, -0.08, 1.05, 0.08, 0.08, 1.25, 1); _tube(bm, [(-0.06, 0, 1.15), (-0.09, 0, 1.15)], 0.03, 10, 5)
    make2(col, "MRS_Crosswalk_Signal", crosswalk_signal, [m["metal"], m["black"], m["black"], m["lens_red"], m["lens_green"], m["sign_yellow"], m["lens_amber"], m["grey"]], 0.006)
    return col


# ============================================================================== entry points
def build_assets():
    """(Re)build every asset collection. Returns {short name: collection}."""
    _materials()
    _props(); _streetlights(); _trees(); _signs(); _traffic_lights(); _barriers(); _pillars(); _scatter(); _manholes(); _drains(); _markings(); _structures()
    return {c: bpy.data.collections[MRS + c] for c in COLLECTIONS}


build_groups = build_assets  # mrs.build_all() picks this up after the placeholder props


def mark_assets(catalog_file, previews=True):
    """Mark every library object as an asset, assign catalogs (written to `catalog_file`, which should be the
    blender_assets.cats.txt next to the saved .blend), tags and previews. Returns the number of assets."""
    catalog_file = os.path.abspath(catalog_file); os.makedirs(os.path.dirname(catalog_file), exist_ok=True)
    with open(catalog_file, "w", encoding="utf-8") as f:
        f.write("# This is an Asset Catalog Definition file for Blender.\n#\n# Empty lines and lines starting with `#` will be ignored.\n"
                "# The first non-ignored line should be the version indicator.\n# Other lines are of the format \"UUID:catalog/path/for/assets:simple catalog name\"\n\nVERSION 1\n\n")
        for c, cid in CATALOGS.items(): f.write("%s:MRS/%s:MRS-%s\n" % (cid, c, c))
    n = 0
    for c, cid in CATALOGS.items():
        col = bpy.data.collections.get(MRS + c)
        if col is None: continue
        for o in col.objects:
            if o.asset_data is None: o.asset_mark()
            ad = o.asset_data; ad.catalog_id = cid; ad.description = "Mert Road Studio %s: %s" % (c.lower(), o.name[4:])
            for t in ("mrs", "road", c.lower()): ad.tags.new(t, skip_if_exists=True)
            if previews:
                hv = o.hide_viewport; o.hide_viewport = False
                try: o.asset_generate_preview()
                except Exception as e: print("preview failed", o.name, e)
                o.hide_viewport = hv
            n += 1
    return n
