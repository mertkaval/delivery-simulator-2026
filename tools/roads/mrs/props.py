"""Collections the road group instances from: props, streetlights, trees, manholes, drains, markings
(arrows, bay tick), pillars, barriers, scatter. Built as simple meshes here; `assets.py` replaces the
props with the detailed generated library."""
import bpy, bmesh, math
from .nodes import MRS


def _box(bm, x0, y0, z0, x1, y1, z1):
    v = [bm.verts.new((x, y, z)) for x, y, z in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)): bm.faces.new([v[i] for i in f])


def _cyl(bm, x, y, z0, z1, r0, r1, n=10):
    a = [bm.verts.new((x + r0 * math.cos(2 * math.pi * i / n), y + r0 * math.sin(2 * math.pi * i / n), z0)) for i in range(n)]
    b = [bm.verts.new((x + r1 * math.cos(2 * math.pi * i / n), y + r1 * math.sin(2 * math.pi * i / n), z1)) for i in range(n)]
    for i in range(n): bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(a))); bm.faces.new(b)


def _poly(bm, pts, z=0.0):
    bm.faces.new([bm.verts.new((x, y, z)) for x, y in pts])


def collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    for o in list(col.objects): bpy.data.objects.remove(o)
    col.hide_render = True
    return col


def mat(name, rgb, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None) or m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (*rgb, 1); bsdf.inputs["Roughness"].default_value = rough; bsdf.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*rgb, 1)
    return m


def make(col, name, builder, material, order=None):
    bm = bmesh.new(); builder(bm); me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(material)
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.hide_render = True; o.hide_viewport = True
    return o


def build_prop_collections():
    metal = mat(MRS + "PropMetal", (0.2, 0.21, 0.22), 0.45, 0.8); green = mat(MRS + "PropGreen", (0.12, 0.3, 0.1), 0.8)
    wood = mat(MRS + "PropWood", (0.45, 0.3, 0.18), 0.7); concrete = mat(MRS + "PropConcrete", (0.55, 0.55, 0.53), 0.85)
    paint = bpy.data.materials.get(MRS + "Paint") or mat(MRS + "Paint", (0.9, 0.9, 0.85), 0.5)
    grey = mat(MRS + "PropGrey", (0.3, 0.3, 0.3), 0.7); bark = mat(MRS + "PropBark", (0.3, 0.22, 0.15), 0.9)
    # generic props (one picked per point, +Y faces the road)
    col = collection(MRS + "Props")
    def bollard(bm): _cyl(bm, 0, 0, 0, 0.9, 0.09, 0.09); _cyl(bm, 0, 0, 0.9, 1.0, 0.1, 0.06)
    def bench(bm): _box(bm, -0.9, -0.25, 0.42, 0.9, 0.25, 0.47); _box(bm, -0.9, -0.3, 0.47, 0.9, -0.22, 0.9); _box(bm, -0.8, -0.28, 0.0, -0.72, 0.25, 0.42); _box(bm, 0.72, -0.28, 0.0, 0.8, 0.25, 0.42)
    def bin_(bm): _cyl(bm, 0, 0, 0, 0.95, 0.28, 0.3, 12); _cyl(bm, 0, 0, 0.95, 1.0, 0.31, 0.2, 12)
    def hydrant(bm): _cyl(bm, 0, 0, 0, 0.6, 0.12, 0.11, 8); _cyl(bm, 0, 0, 0.6, 0.75, 0.14, 0.08, 8); _box(bm, -0.22, -0.06, 0.4, 0.22, 0.06, 0.5)
    def sign(bm): _cyl(bm, 0, 0, 0, 2.6, 0.04, 0.04, 6); _box(bm, -0.3, -0.02, 2.0, 0.3, 0.02, 2.6)
    for nm, fn, m in (("MRS_Bollard", bollard, metal), ("MRS_Bench", bench, wood), ("MRS_Bin", bin_, metal), ("MRS_Hydrant", hydrant, mat(MRS + "PropRed", (0.7, 0.1, 0.08), 0.5)), ("MRS_Sign", sign, metal)):
        make(col, nm, fn, m)
    # streetlights: arm reaches over the road (+Y)
    col = collection(MRS + "Streetlights")
    def streetlight(bm):
        _cyl(bm, 0, 0, 0, 0.5, 0.18, 0.15); _cyl(bm, 0, 0, 0.5, 8.0, 0.1, 0.06); _box(bm, -0.05, 0.0, 7.9, 0.05, 2.2, 8.0); _box(bm, -0.22, 1.8, 7.8, 0.22, 2.6, 8.05)
    def lamp_short(bm): _cyl(bm, 0, 0, 0, 0.3, 0.12, 0.1); _cyl(bm, 0, 0, 0.3, 4.5, 0.06, 0.05); _cyl(bm, 0, 0, 4.5, 4.9, 0.18, 0.22, 8)
    make(col, "MRS_Streetlight", streetlight, metal); make(col, "MRS_LampShort", lamp_short, metal)
    # trees
    col = collection(MRS + "Trees")
    def tree(bm):
        _cyl(bm, 0, 0, 0, 3.0, 0.16, 0.12, 8)
        for z, r in ((3.0, 2.2), (4.6, 1.7), (6.0, 1.0)): _cyl(bm, 0, 0, z, z + 1.8, r, r * 0.35, 9)
    def tree_round(bm): _cyl(bm, 0, 0, 0, 2.6, 0.14, 0.11, 8); _cyl(bm, 0, 0, 2.2, 4.0, 1.4, 2.4, 10); _cyl(bm, 0, 0, 4.0, 6.2, 2.4, 0.6, 10)
    make(col, "MRS_Conifer", tree, green); make(col, "MRS_TreeRound", tree_round, green)
    # manholes, drains
    col = collection(MRS + "Manholes")
    make(col, "MRS_Manhole", lambda bm: _cyl(bm, 0, 0, 0.0, 0.015, 0.33, 0.33, 16), metal)
    col = collection(MRS + "Drains")
    def gully(bm): _box(bm, -0.25, -0.2, 0.0, 0.25, 0.2, 0.012)
    make(col, "MRS_Gully", gully, metal)
    # markings: arrows for every movement set (straight, left, right, straight+left, straight+right, left+right, all), unit tick
    # (the road group picks them by name: tools/roads/mrs/road.py arrow_index)
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
    make(col, "MRS_ArrowLeftRight", lambda bm: (shaft(bm, 1.4), turn(bm, -1), turn(bm, 1)), paint)
    make(col, "MRS_ArrowAll", lambda bm: (shaft(bm), head(bm), turn(bm, -1), turn(bm, 1)), paint)
    make(col, "MRS_MarkTick", lambda bm: _poly(bm, [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)], 0.0), paint)
    # merge arrows (lane ends): a bent shaft toward the remaining lane
    def merge(bm, sgn):
        _poly(bm, [(-0.1, 0.0), (0.1, 0.0), (0.1, 1.6), (-0.1, 1.6)], 0.0)
        pts = [(0.0, 1.5), (sgn * 0.9, 2.6), (sgn * 1.05, 2.45), (0.15 * -sgn + 0.0, 1.35)]
        _poly(bm, pts if sgn > 0 else pts[::-1], 0.0)
        tri = [(sgn * 0.6, 2.75), (sgn * 1.3, 2.35), (sgn * 1.25, 3.0)]
        _poly(bm, tri if sgn > 0 else tri[::-1], 0.0)
    make(col, "MRS_ArrowMergeLeft", lambda bm: merge(bm, -1), paint); make(col, "MRS_ArrowMergeRight", lambda bm: merge(bm, 1), paint)
    # bicycle symbol (two wheels, frame, rider dash) + a small direction arrow ahead of it, 1.6 m long along +Y
    def bike(bm):
        for cy in (-0.45, 0.45):
            n = 16
            outer = [(0.28 * math.cos(2 * math.pi * i / n), cy + 0.28 * math.sin(2 * math.pi * i / n)) for i in range(n)]
            inner = [(0.2 * math.cos(2 * math.pi * i / n), cy + 0.2 * math.sin(2 * math.pi * i / n)) for i in range(n)]
            for i in range(n):
                _poly(bm, [outer[i], outer[(i + 1) % n], inner[(i + 1) % n], inner[i]], 0.0)
        _poly(bm, [(-0.04, -0.45), (0.04, -0.45), (0.04, 0.45), (-0.04, 0.45)], 0.0)            # frame tube
        _poly(bm, [(-0.04, 0.0), (0.04, 0.0), (0.3, 0.5), (0.22, 0.52)], 0.0)                     # seat stay
        _poly(bm, [(0.2, 0.52), (0.42, 0.52), (0.42, 0.6), (0.2, 0.6)], 0.0)                      # saddle
        _poly(bm, [(-0.15, 1.0), (0.15, 1.0), (0.15, 1.5), (-0.15, 1.5)], 0.0); _poly(bm, [(-0.4, 1.5), (0.4, 1.5), (0.0, 1.95)], 0.0)   # arrow
    make(col, "MRS_BikeSymbol", bike, paint)
    # separator post (flexible bollard) and planter for protected cycleways (instanced from the markings collection)
    make(col, "MRS_SepPost", lambda bm: (_cyl(bm, 0, 0, 0, 0.9, 0.05, 0.045, 8), _cyl(bm, 0, 0, 0.0, 0.05, 0.12, 0.12, 8)), mat(MRS + "PropWhite", (0.9, 0.9, 0.9), 0.5))
    make(col, "MRS_SepPlanter", lambda bm: (_box(bm, -0.3, -0.6, 0.0, 0.3, 0.6, 0.5), _box(bm, -0.25, -0.55, 0.5, 0.25, 0.55, 0.62)), concrete)
    for word in ("BUS", "TAXI", "ONLY"):        # lane words (placeholder quads; assets.py paints the letters)
        make(col, "MRS_Text" + word, lambda bm: _poly(bm, [(-0.7, -1.2), (0.7, -1.2), (0.7, 1.2), (-0.7, 1.2)], 0.0), paint)
    # pillars: 1 m tall, scaled in z (and x with the road width)
    col = collection(MRS + "Pillars")
    def pillar(bm): _box(bm, -1.2, -0.6, 0.0, 1.2, 0.6, 1.0); _box(bm, -1.6, -0.9, 0.0, 1.6, 0.9, 0.06)
    def pier_round(bm): _cyl(bm, -0.9, 0, 0, 1.0, 0.5, 0.5, 14); _cyl(bm, 0.9, 0, 0, 1.0, 0.5, 0.5, 14)
    make(col, "MRS_Pillar", pillar, concrete); make(col, "MRS_PierRound", pier_round, concrete)
    # barriers: 2 m segments along +Y, road side at -X... the group aligns +Y with the road direction
    col = collection(MRS + "Barriers")
    def guardrail(bm):
        _box(bm, -0.04, -0.05, 0.0, 0.04, 0.05, 0.75)
        _box(bm, -0.06, -1.0, 0.5, -0.02, 1.0, 0.65); _box(bm, -0.06, -1.0, 0.35, -0.02, 1.0, 0.45)
    def jersey(bm):
        for y0, y1 in ((-1.0, 1.0),):
            v = [bm.verts.new(p) for p in ((-0.3, y0, 0), (0.3, y0, 0), (0.3, y0, 0.25), (0.12, y0, 0.55), (0.1, y0, 0.81), (-0.1, y0, 0.81), (-0.12, y0, 0.55), (-0.3, y0, 0.25))]
            w = [bm.verts.new((p.co.x, y1, p.co.z)) for p in v]
            bm.faces.new(v[::-1]); bm.faces.new(w)
            for i in range(len(v)): bm.faces.new((v[i], v[(i + 1) % len(v)], w[(i + 1) % len(v)], w[i]))
    def parapet(bm): _box(bm, -0.2, -1.0, 0.0, 0.2, 1.0, 1.1); _box(bm, -0.25, -1.0, 1.1, 0.25, 1.0, 1.18)
    def railing(bm):
        _box(bm, -0.03, -0.03, 0.0, 0.03, 0.03, 1.1); _box(bm, -0.02, -1.0, 1.05, 0.02, 1.0, 1.1); _box(bm, -0.015, -1.0, 0.55, 0.015, 1.0, 0.58)
    make(col, "MRS_Guardrail", guardrail, metal); make(col, "MRS_Jersey", jersey, concrete); make(col, "MRS_Parapet", parapet, concrete); make(col, "MRS_Railing", railing, metal)
    # scatter: grass clump, rock
    col = collection(MRS + "Scatter")
    def grass(bm):
        for i in range(5):
            a = 2 * math.pi * i / 5; x, y = 0.12 * math.cos(a), 0.12 * math.sin(a)
            _poly(bm, [(x - 0.03, y), (x + 0.03, y), (x + 0.4 * math.cos(a) * 0.3, y + 0.4 * math.sin(a) * 0.3)], 0.0)
            v = bm.verts[-3:]; v[2].co.z = 0.35
    def rock(bm): _cyl(bm, 0, 0, 0, 0.25, 0.3, 0.2, 7)
    def grass_big(bm):
        for i in range(8):
            a = 2 * math.pi * i / 8 + 0.3; x, y = 0.2 * math.cos(a), 0.2 * math.sin(a)
            _poly(bm, [(x - 0.04, y), (x + 0.04, y), (x + 0.5 * math.cos(a) * 0.3, y + 0.5 * math.sin(a) * 0.3)], 0.0)
            v = bm.verts[-3:]; v[2].co.z = 0.5
    def pebble(bm): _cyl(bm, 0, 0, 0, 0.1, 0.12, 0.08, 6)
    # the pick is uniform over the collection, so grass gets more entries than rocks
    make(col, "MRS_Grass", grass, green); make(col, "MRS_GrassBig", grass_big, green); make(col, "MRS_Grass2", grass, green)
    make(col, "MRS_GrassBig2", grass_big, green); make(col, "MRS_Pebble", pebble, grey); make(col, "MRS_Rock", rock, grey)
    return {c: bpy.data.collections[MRS + c] for c in ("Props", "Streetlights", "Trees", "Manholes", "Drains", "Markings", "Pillars", "Barriers", "Scatter")}
