"""Mert Road Studio trees (Blender 5.2, headless-safe).

One editable Geometry Nodes group, **Tree_Variants**, grows a whole tree from a handful of inputs
(panels Trunk / Branches / Foliage / Variation / Detail / Materials):

* trunk: a curve resampled along Z, bent by 4D noise + lean, tapered with a root flare, swept with a
  circle profile (cylindrical UVs: u around, v in metres along the axis), bark micro-displacement;
* branches: lines instanced on the trunk above *Start Height* (golden-angle yaw, tilted upward, length
  profile per foliage style), realised, drooped toward the tips (quadratic), tapered, swept; optional
  second level (sub-branches sampled along the first level);
* foliage: noise-displaced icosphere "leaf blobs" at the branch tips plus leaf cards distributed over
  the blobs (random orientation, poking outward); a `foliage_tint` point attribute (per cluster) and a
  `leaf_card` attribute (0 blob / 1 card / 2 palm frond) drive the foliage shader; the Palm style
  replaces blobs by bent, V-folded fronds around the trunk top (dead fronds hang down, tint ~1);
* randomness: every Random Value / noise is seeded from *Seed* (bounded jitter), so the same inputs
  always give the same mesh; Quality = Low gives fewer clusters, lower-res cards/blobs and no level 2.

`build_tree_materials()` builds the shader groups MRS_BarkShader / MRS_FoliageShader and the
materials MRS_Bark* / MRS_Foliage* (one "MRS" group node each, like the road materials).
`build_trees()` bakes 12 trees (6 species x 2) into MRS_Trees, 2 shrubs into MRS_Shrubs, and _LOD1
versions into MRS_Trees_LOD1 / MRS_Shrubs_LOD1 (hidden library objects, origin at the trunk base).
Importing this module has no side effects.
"""
import math
import bpy
from .nodes import T, MRS, new_tree, sock, panel, mod_input_set, depsgraph, scene
from .props import collection

GROUP = "Tree_Variants"
STYLES = ("Round", "Conical", "Columnar", "Spreading", "Palm", "Shrub")
QUALITIES = ("Full", "Low")
TAU = 2.0 * math.pi
GOLDEN = 2.399963229728653

# (name, socket type, default, min, max, description) per panel; menus are added by hand
INPUT_SPEC = [
    ("Trunk", [("Height", "NodeSocketFloat", 12.0, 0.2, 40.0, "Trunk height in metres (before Height Jitter)"),
               ("Base Radius", "NodeSocketFloat", 0.4, 0.01, 3.0, "Trunk radius at the ground"),
               ("Taper", "NodeSocketFloat", 0.75, 0.0, 1.0, "0 = cylinder, 1 = pointed tip"),
               ("Lean", "NodeSocketFloat", 0.0, -1.0, 1.0, "Top offset along +X as a fraction of the height"),
               ("Trunk Noise", "NodeSocketFloat", 0.3, 0.0, 2.0, "Sideways wander of the trunk and bark ridge depth")]),
    ("Branches", [("Count", "NodeSocketInt", 14, 0, 200, "Level-1 branches (Low quality uses 60 %)"),
                  ("Start Height", "NodeSocketFloat", 0.3, 0.0, 0.95, "Lowest branch as a fraction of the trunk height"),
                  ("Length", "NodeSocketFloat", 4.5, 0.0, 20.0, "Longest level-1 branch in metres (the style sets the profile)"),
                  ("Droop", "NodeSocketFloat", 0.3, 0.0, 2.0, "Tip drop: 0.5 x Droop x branch length"),
                  ("Up Tilt", "NodeSocketFloat", 0.7, 0.0, 4.0, "Upward component of the branch direction (0 flat, 3 steep)"),
                  ("Radius", "NodeSocketFloat", 0.12, 0.005, 1.0, "Branch radius at the trunk"),
                  ("Levels", "NodeSocketInt", 2, 1, 2, "2 adds sub-branches (Full quality only)")]),
    ("Foliage", [("Cluster Count", "NodeSocketInt", 40, 0, 400, "Leaf clusters (approximate; Palm: fronds). Low quality uses 45 %"),
                 ("Cluster Size", "NodeSocketFloat", 1.4, 0.05, 6.0, "Cluster radius in metres (Palm: frond length)"),
                 ("Leaf Density", "NodeSocketFloat", 1.0, 0.0, 5.0, "Leaf cards per cluster (1 = about 8)"),
                 ("Leaf Size", "NodeSocketFloat", 0.9, 0.02, 5.0, "Leaf card edge in metres (Palm: frond width / length)"),
                 ("Color Variation", "NodeSocketFloat", 0.6, 0.0, 1.0, "Spread of the per-cluster foliage_tint attribute")]),
    ("Variation", [("Seed", "NodeSocketInt", 1, 0, 100000, "Drives every random value and noise"),
                   ("Height Jitter", "NodeSocketFloat", 0.1, 0.0, 0.5, "Height x (1 +- jitter)"),
                   ("Canopy Jitter", "NodeSocketFloat", 0.25, 0.0, 1.0, "Branch length, cluster size and position jitter")]),
]
INPUT_NAMES = ["Height", "Base Radius", "Taper", "Lean", "Trunk Noise", "Count", "Start Height", "Length", "Droop", "Up Tilt", "Radius", "Levels",
               "Style", "Cluster Count", "Cluster Size", "Leaf Density", "Leaf Size", "Color Variation", "Seed", "Height Jitter", "Canopy Jitter",
               "Quality", "Bark", "Foliage"]


# ============================================================================== node helpers
def _rand(tb, lo, hi, seed, k, id_sock=None, kind="FLOAT"):
    """Random Value seeded by (Seed + k); ID = index unless given. kind FLOAT / FLOAT_VECTOR / BOOLEAN."""
    node = tb.n("FunctionNodeRandomValue", data_type=kind)
    if kind == "BOOLEAN":
        tb.inp(node, "Probability", lo)
    else:
        for nm, v in (("Min", lo), ("Max", hi)):
            s = next(s for s in node.inputs if s.name == nm and s.enabled)
            if isinstance(v, bpy.types.NodeSocket): tb.link(v, s)
            else: s.default_value = v
    tb.inp(node, "Seed", tb.math("ADD", seed, float(k)))
    if id_sock is not None: tb.inp(node, "ID", id_sock)
    return next(o for o in node.outputs if o.enabled)


def _noise(tb, vec, scale, w, detail=3.0, rough=0.5, color=False):
    n = tb.n("ShaderNodeTexNoise", noise_dimensions="4D")
    tb.inp(n, "Vector", vec); tb.inp(n, "W", w); tb.inp(n, "Scale", scale); tb.inp(n, "Detail", detail); tb.inp(n, "Roughness", rough)
    return n.outputs["Color"] if color else n.outputs["Fac"]


def _capture(tb, geo, items, domain="POINT"):
    """Capture fields on `geo`: items = [(name, socket, type)]. Returns (geometry, [attribute sockets])."""
    node = tb.n("GeometryNodeCaptureAttribute", domain=domain)
    for nm, _, ty in items: node.capture_items.new(ty, nm)
    tb.inp(node, "Geometry", geo)
    outs = []
    for i, (nm, s, ty) in enumerate(items):
        tb.link(s, node.inputs[2 + i]); outs.append(node.outputs[2 + i])
    return node.outputs[0], outs


def _circle(tb, res):
    c = tb.n("GeometryNodeCurvePrimitiveCircle", mode="RADIUS"); tb.inp(c, "Resolution", res); tb.inp(c, "Radius", 1.0)
    u = tb.n("GeometryNodeSplineParameter").outputs["Factor"]
    geo, (cu,) = _capture(tb, c.outputs[0], [("u", u, "FLOAT")])
    return geo, cu


def _sweep(tb, curves, ring_res, label):
    """Curves -> tube mesh with a cylindrical UVMap (u around, v = metres along the curve)."""
    sp = tb.n("GeometryNodeSplineParameter")
    cgeo, (fac, vlen) = _capture(tb, curves, [("fac", sp.outputs["Factor"], "FLOAT"), ("len", sp.outputs["Length"], "FLOAT")])
    prof, cu = _circle(tb, ring_res)
    c2m = tb.n("GeometryNodeCurveToMesh", label); tb.inp(c2m, "Curve", cgeo); tb.inp(c2m, "Profile Curve", prof); tb.inp(c2m, "Fill Caps", True)
    # Blender 5.x: the profile scale is an explicit input (a node made from Python does not get the implicit Radius field)
    tb.inp(c2m, "Scale", tb.n("GeometryNodeInputRadius").outputs[0])
    return tb.store(c2m.outputs[0], "UVMap", tb.combine(cu, vlen, 0.0), "FLOAT2", "CORNER")


def _line(tb, res, end=(1.0, 0.0, 0.0)):
    ln = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(ln, "Start", (0.0, 0.0, 0.0)); tb.inp(ln, "End", end)
    rs = tb.n("GeometryNodeResampleCurve"); tb.inp(rs, "Curve", ln.outputs[0]); tb.inp(rs, "Count", res)
    return rs.outputs[0]


def _trim(tb, curves, a, b):
    n = tb.n("GeometryNodeTrimCurve", mode="FACTOR"); tb.inp(n, "Curve", curves); tb.inp(n, "Start", a); tb.inp(n, "End", b)
    return n.outputs[0]


def _to_points(tb, curves, count):
    n = tb.n("GeometryNodeCurveToPoints", mode="COUNT"); tb.inp(n, "Curve", curves); tb.inp(n, "Count", count)
    return n


def _instance(tb, points, inst, rotation=None, scale=None):
    n = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(n, "Points", points); tb.inp(n, "Instance", inst)
    if rotation is not None: tb.inp(n, "Rotation", rotation)
    if scale is not None: tb.inp(n, "Scale", scale)
    r = tb.n("GeometryNodeRealizeInstances"); tb.inp(r, "Geometry", n.outputs[0])
    return r.outputs[0]


def _droop(tb, curves, droop):
    """Quadratic tip drop (0.5 x Droop x spline length at the tip) applied to realised branch curves."""
    f = tb.n("GeometryNodeSplineParameter").outputs["Factor"]; L = tb.n("GeometryNodeSplineLength").outputs["Length"]
    dz = tb.math("MULTIPLY", tb.math("MULTIPLY", droop, -0.5), tb.math("MULTIPLY", L, tb.math("MULTIPLY", f, f)))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", curves); tb.inp(sp, "Offset", tb.combine(0.0, 0.0, dz))
    return sp.outputs[0]


def _branch_radius(tb, curves, radius, ref_len, k):
    f = tb.n("GeometryNodeSplineParameter").outputs["Factor"]; L = tb.n("GeometryNodeSplineLength").outputs["Length"]
    rel = tb.math("DIVIDE", L, tb.math("MAXIMUM", ref_len, 0.01))
    r = tb.math("ADD", tb.math("MULTIPLY", tb.math("MULTIPLY", radius, k), tb.math("MULTIPLY", rel, tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", f, 0.85)))), 0.006)
    n = tb.n("GeometryNodeSetCurveRadius"); tb.inp(n, "Curve", curves); tb.inp(n, "Radius", r)
    return n.outputs[0]


def _normalize(tb, v): return tb.vmath("NORMALIZE", v)


def _align_x(tb, vec):
    n = tb.n("FunctionNodeAlignRotationToVector", axis="X", pivot_axis="AUTO"); tb.inp(n, "Vector", vec); tb.inp(n, "Factor", 1.0)
    return n.outputs[0]


def _euler(tb, vec):
    n = tb.n("FunctionNodeEulerToRotation"); tb.inp(n, "Euler", vec); return n.outputs[0]


def _select(tb, idx, values, kind="FLOAT"):
    """Pick values[round(idx)] with a chain of Switch nodes (a group Menu socket may feed only ONE Menu
    Switch node - several, even with identical items, leave the socket without items - so the Style
    menu is turned into an index once and everything else selects on that index)."""
    out = values[0]
    for i in range(1, len(values)):
        out = tb.switch(tb.compare("GREATER_THAN", idx, i - 0.5), out, values[i], kind)
    return out


# ============================================================================== the Tree_Variants group
def build_tree_group():
    """(Re)build the Tree_Variants geometry-nodes group. Returns the node tree."""
    if bpy.data.materials.get(MRS + "Bark") is None or bpy.data.materials.get(MRS + "Foliage") is None: build_tree_materials()
    g = new_tree(GROUP)
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    I = {}
    panels = {}
    for pname, rows in INPUT_SPEC:
        p = panels[pname] = panel(g, pname, closed=(pname not in ("Trunk", "Foliage")))
        if pname == "Foliage":
            I["Style"] = sock(g, "Style", "INPUT", "NodeSocketMenu", desc="Canopy style: Round / Conical / Columnar / Spreading / Palm / Shrub", parent=p)
        for nm, st, d, lo, hi, desc in rows:
            I[nm] = sock(g, nm, "INPUT", st, d, lo, hi, desc, parent=p)
    p = panels["Detail"] = panel(g, "Detail", closed=True)
    I["Quality"] = sock(g, "Quality", "INPUT", "NodeSocketMenu", desc="Full, or Low: fewer clusters, lower-res leaf blobs/cards, no branch level 2", parent=p)
    p = panels["Materials"] = panel(g, "Materials", closed=True)
    I["Bark"] = sock(g, "Bark", "INPUT", "NodeSocketMaterial", parent=p); I["Foliage"] = sock(g, "Foliage", "INPUT", "NodeSocketMaterial", parent=p)
    I["Bark"].default_value = bpy.data.materials[MRS + "Bark"]; I["Foliage"].default_value = bpy.data.materials[MRS + "Foliage"]

    tb = T(g)
    tb.frame_("Inputs, seed and quality")
    gi = tb.n("NodeGroupInput")
    In = lambda n: next(s for s in gi.outputs if s.name == n)
    seed = In("Seed")
    zero = tb.n("FunctionNodeInputInt", "constant id"); zero.integer = 0; zero = zero.outputs[0]
    hj = _rand(tb, -1.0, 1.0, seed, 1, zero)
    H = tb.math("MULTIPLY", In("Height"), tb.math("ADD", 1.0, tb.math("MULTIPLY", In("Height Jitter"), hj)))
    qf = tb.menu_switch(In("Quality"), [("Full", 1.0), ("Low", 0.0)], kind="FLOAT", label="Quality factor")
    low = tb.compare("LESS_THAN", qf, 0.5)
    full = tb.boolean("NOT", low)
    trunk_res = tb.switch(low, 16, 8, "INT"); ring_res = tb.switch(low, 12, 7, "INT")
    br_res = tb.switch(low, 6, 4, "INT"); br_ring = tb.switch(low, 6, 4, "INT"); blob_sub = tb.switch(low, 2, 1, "INT")
    n1f = tb.math("MAXIMUM", tb.math("ROUND", tb.math("MULTIPLY", In("Count"), tb.switch(low, 1.0, 0.6))), 1.0)
    cluster_target = tb.math("MULTIPLY", In("Cluster Count"), tb.switch(low, 1.0, 0.45))
    leaf_density = tb.math("MULTIPLY", In("Leaf Density"), tb.switch(low, 1.0, 0.4))
    levels2 = tb.boolean("AND", tb.compare("GREATER_THAN", In("Levels"), 1.5), full)
    style_idx = tb.menu_switch(In("Style"), [(s, float(i)) for i, s in enumerate(STYLES)], kind="FLOAT", label="style index")
    by_style = lambda values, kind="FLOAT": _select(tb, style_idx, values, kind)
    is_palm = tb.compare("GREATER_THAN", by_style([1.0 if s == "Palm" else 0.0 for s in STYLES]), 0.5)
    has_branches = tb.boolean("AND", tb.boolean("NOT", is_palm), tb.compare("GREATER_THAN", In("Count"), 0.5))
    pos = tb.n("GeometryNodeInputPosition").outputs[0]
    normal = tb.n("GeometryNodeInputNormal").outputs[0]
    index = tb.n("GeometryNodeInputIndex").outputs[0]
    seedf = tb.math("MULTIPLY", seed, 0.731)

    # ---------------------------------------------------------------- trunk
    tb.frame_("Trunk: line -> resample -> noise wander + lean -> taper -> sweep -> bark ridges")
    tline = _line(tb, trunk_res, tb.combine(0.0, 0.0, H))
    fac = tb.n("GeometryNodeSplineParameter").outputs["Factor"]
    # the base stays vertical (fac^1.5 / fac^2.4) so the bottom ring of the swept tube lies flat on z = 0
    wander = tb.vmath("SCALE", tb.vmath("SUBTRACT", _noise(tb, pos, 0.25, seedf, 2.0, 0.5, color=True), (0.5, 0.5, 0.5)),
                      scale=tb.math("MULTIPLY", In("Trunk Noise"), tb.math("MULTIPLY", tb.math("POWER", fac, 1.5), 2.0)))
    wx, wy, _ = tb.separate(wander)
    lean = tb.math("MULTIPLY", In("Lean"), tb.math("MULTIPLY", H, tb.math("POWER", fac, 2.4)))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", tline); tb.inp(sp, "Offset", tb.combine(tb.math("ADD", wx, lean), wy, 0.0))
    trunk_curve = sp.outputs[0]
    flare = tb.math("ADD", 1.0, tb.math("MULTIPLY", 0.9, tb.math("POWER", tb.math("SUBTRACT", 1.0, fac), 12.0)))
    r = tb.math("MULTIPLY", In("Base Radius"), tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", fac, In("Taper"))), flare))
    scr = tb.n("GeometryNodeSetCurveRadius"); tb.inp(scr, "Curve", trunk_curve); tb.inp(scr, "Radius", tb.math("MAXIMUM", r, 0.015))
    trunk_curve = scr.outputs[0]
    trunk_mesh = _sweep(tb, trunk_curve, ring_res, "Trunk tube")
    ridge = _noise(tb, tb.vmath("MULTIPLY", pos, (1.0, 1.0, 0.3)), 5.0, tb.math("ADD", seedf, 3.0), 2.0, 0.5)
    ridge_amp = tb.math("MULTIPLY", tb.math("SUBTRACT", ridge, 0.5), tb.math("MULTIPLY", In("Base Radius"), tb.math("MULTIPLY", 0.3, tb.math("ADD", 0.3, In("Trunk Noise")))))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", trunk_mesh); tb.inp(sp, "Offset", tb.vmath("SCALE", normal, scale=ridge_amp))
    trunk_mesh = sp.outputs[0]

    # ---------------------------------------------------------------- branches level 1
    tb.frame_("Branches level 1: points on the trunk above Start Height, golden-angle yaw, up tilt, style length profile, droop")
    c2p = _to_points(tb, _trim(tb, trunk_curve, In("Start Height"), 0.93), n1f)
    bp = c2p.outputs["Points"]
    tnorm = tb.math("DIVIDE", index, tb.math("MAXIMUM", tb.math("SUBTRACT", n1f, 1.0), 1.0))
    yaw = tb.math("ADD", tb.math("MULTIPLY", index, GOLDEN), _rand(tb, -0.6, 0.6, seed, 11))
    tilt = tb.math("ADD", tb.math("MULTIPLY", In("Up Tilt"), tb.math("ADD", 0.7, tb.math("MULTIPLY", tnorm, 0.6))), _rand(tb, -0.15, 0.15, seed, 12))
    bdir = _normalize(tb, tb.combine(tb.math("COSINE", yaw), tb.math("SINE", yaw), tilt))
    prof = by_style([  # Round, Conical, Columnar, Spreading, Palm, Shrub: branch length factor over the trunk (tnorm 0 bottom .. 1 top)
        tb.math("ADD", 0.55, tb.math("MULTIPLY", 0.45, tb.math("SINE", tb.math("MULTIPLY", math.pi, tb.math("ADD", 0.1, tb.math("MULTIPLY", tnorm, 0.8)))))),
        tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", tnorm, 0.85)),
        tb.math("SUBTRACT", 0.85, tb.math("MULTIPLY", tnorm, 0.35)),
        tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", tnorm, 0.35)),
        0.0,
        tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", tnorm, 0.3))])
    L1 = tb.math("MULTIPLY", In("Length"), tb.math("MULTIPLY", prof, tb.math("ADD", 1.0, tb.math("MULTIPLY", In("Canopy Jitter"), _rand(tb, -1.0, 1.0, seed, 13)))))
    l1 = _instance(tb, bp, _line(tb, br_res), _align_x(tb, bdir), tb.combine(L1, L1, L1))
    l1 = _droop(tb, l1, In("Droop"))
    l1 = _branch_radius(tb, l1, In("Radius"), In("Length"), 1.0)
    l1_mesh = _sweep(tb, l1, br_ring, "Branch tubes L1")
    cand1 = _to_points(tb, _trim(tb, l1, 0.45, 1.0), 3).outputs["Points"]

    # ---------------------------------------------------------------- branches level 2
    tb.frame_("Branches level 2: sub-branches sampled along level 1 (Full quality, Levels = 2)")
    plen_geo, (plen,) = _capture(tb, l1, [("plen", tb.n("GeometryNodeSplineLength").outputs["Length"], "FLOAT")])
    c2p2 = _to_points(tb, _trim(tb, plen_geo, 0.35, 0.9), 2)
    ang = tb.math("MULTIPLY", _rand(tb, 0.7, 1.4, seed, 21), tb.math("SIGN", _rand(tb, -1.0, 1.0, seed, 22)))
    rz = tb.n("FunctionNodeAxisAngleToRotation"); tb.inp(rz, "Axis", (0.0, 0.0, 1.0)); tb.inp(rz, "Angle", ang)
    rv = tb.n("FunctionNodeRotateVector"); tb.inp(rv, "Vector", c2p2.outputs["Tangent"]); tb.inp(rv, "Rotation", rz.outputs[0])
    d2 = _normalize(tb, tb.vmath("ADD", rv.outputs[0], tb.combine(0.0, 0.0, tb.math("ADD", 0.25, tb.math("MULTIPLY", In("Up Tilt"), 0.3)))))
    L2 = tb.math("MULTIPLY", plen, _rand(tb, 0.35, 0.55, seed, 23))
    l2 = _instance(tb, c2p2.outputs["Points"], _line(tb, 4), _align_x(tb, d2), tb.combine(L2, L2, L2))
    l2 = _droop(tb, l2, In("Droop"))
    l2 = _branch_radius(tb, l2, In("Radius"), In("Length"), 0.45)
    l2_mesh = tb.switch(levels2, tb.empty(), _sweep(tb, l2, 4, "Branch tubes L2"), "GEOMETRY")
    cand2 = tb.switch(levels2, tb.empty(), _to_points(tb, _trim(tb, l2, 0.4, 1.0), 2).outputs["Points"], "GEOMETRY")
    cand_top = _to_points(tb, _trim(tb, trunk_curve, 0.86, 1.0), 2).outputs["Points"]

    # ---------------------------------------------------------------- foliage clusters
    tb.frame_("Foliage: thin the candidate points to Cluster Count, tint, lumpy icosphere blobs, leaf cards on the blobs")
    cand = tb.join(cand1, cand2, cand_top)
    n_cand = tb.math("ADD", tb.math("MULTIPLY", n1f, 3.0), tb.math("ADD", tb.switch(levels2, 0.0, tb.math("MULTIPLY", n1f, 4.0)), 2.0))
    keep_p = tb.math("MINIMUM", tb.math("DIVIDE", cluster_target, tb.math("MAXIMUM", n_cand, 1.0)), 1.0)
    keep = _rand(tb, keep_p, None, seed, 31, kind="BOOLEAN")
    sep = tb.n("GeometryNodeSeparateGeometry", domain="POINT"); tb.inp(sep, "Geometry", cand); tb.inp(sep, "Selection", keep)
    cl = sep.outputs["Selection"]
    tint = tb.math("ADD", 0.5, tb.math("MULTIPLY", tb.math("SUBTRACT", _rand(tb, 0.0, 1.0, seed, 32), 0.5), In("Color Variation")))
    cl = tb.store(cl, "foliage_tint", tint); cl = tb.store(cl, "leaf_card", 0.0)
    jit = tb.vmath("SCALE", _rand(tb, (-1.0, -1.0, -1.0), (1.0, 1.0, 1.0), seed, 33, kind="FLOAT_VECTOR"), scale=tb.math("MULTIPLY", In("Canopy Jitter"), tb.math("MULTIPLY", In("Cluster Size"), 0.6)))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", cl); tb.inp(sp, "Offset", jit); cl = sp.outputs[0]
    shape = by_style([(1.0, 1.0, 0.78), (1.3, 1.3, 0.4), (0.85, 0.85, 1.1), (1.2, 1.2, 0.65), (1.0, 1.0, 1.0), (1.0, 1.0, 0.85)], "VECTOR")  # cluster squash per style
    csize = tb.math("MULTIPLY", In("Cluster Size"), tb.math("ADD", 1.0, tb.math("MULTIPLY", In("Canopy Jitter"), _rand(tb, -0.6, 0.6, seed, 34))))
    ico = tb.n("GeometryNodeMeshIcoSphere"); tb.inp(ico, "Radius", 1.0); tb.inp(ico, "Subdivisions", blob_sub)
    ico_uv = tb.store(ico.outputs[0], "UVMap", ico.outputs["UV Map"], "FLOAT2", "CORNER")
    # yaw only (plus a little tilt) so the per-style squash stays horizontal (flat plates on a pine)
    blobs = _instance(tb, cl, ico_uv, _euler(tb, _rand(tb, (-0.3, -0.3, 0.0), (0.3, 0.3, TAU), seed, 35, kind="FLOAT_VECTOR")), tb.vmath("SCALE", shape, scale=csize))
    lump = _noise(tb, pos, tb.math("DIVIDE", 1.6, In("Cluster Size")), tb.math("ADD", seedf, 5.0), 2.0, 0.5)
    lump2 = _noise(tb, pos, tb.math("DIVIDE", 4.5, In("Cluster Size")), tb.math("ADD", seedf, 6.0), 1.0, 0.5)
    lump_amp = tb.math("MULTIPLY", tb.math("ADD", tb.math("MULTIPLY", tb.math("SUBTRACT", lump, 0.5), 0.8), tb.math("MULTIPLY", tb.math("SUBTRACT", lump2, 0.5), 0.3)), In("Cluster Size"))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", blobs); tb.inp(sp, "Offset", tb.vmath("SCALE", normal, scale=lump_amp)); blobs = sp.outputs[0]
    ss = tb.n("GeometryNodeSetShadeSmooth", domain="FACE"); tb.inp(ss, "Geometry", blobs); tb.inp(ss, "Shade Smooth", True); blobs = ss.outputs[0]
    dens = tb.math("DIVIDE", tb.math("MULTIPLY", leaf_density, 0.75), tb.math("MULTIPLY", In("Cluster Size"), In("Cluster Size")))
    dp = tb.n("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM"); tb.inp(dp, "Mesh", blobs); tb.inp(dp, "Density", dens); tb.inp(dp, "Seed", tb.math("ADD", seed, 36.0))
    card_pts = tb.store(dp.outputs["Points"], "leaf_card", 1.0)
    rr = tb.n("FunctionNodeRotateRotation", rotation_space="LOCAL"); tb.inp(rr, "Rotation", dp.outputs["Rotation"])
    tb.inp(rr, "Rotate By", _euler(tb, _rand(tb, (-0.7, -0.7, 0.0), (0.7, 0.7, TAU), seed, 37, kind="FLOAT_VECTOR")))
    card = tb.n("GeometryNodeMeshGrid"); tb.inp(card, "Size X", In("Leaf Size")); tb.inp(card, "Size Y", In("Leaf Size")); tb.inp(card, "Vertices X", 2); tb.inp(card, "Vertices Y", 2)
    card_uv = tb.store(card.outputs[0], "UVMap", card.outputs["UV Map"], "FLOAT2", "CORNER")
    cs = _rand(tb, 0.7, 1.3, seed, 38)
    iop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(iop, "Points", card_pts); tb.inp(iop, "Instance", card_uv); tb.inp(iop, "Rotation", rr.outputs[0]); tb.inp(iop, "Scale", tb.combine(cs, cs, cs))
    ti = tb.n("GeometryNodeTranslateInstances"); tb.inp(ti, "Instances", iop.outputs[0]); tb.inp(ti, "Translation", tb.combine(0.0, 0.0, tb.math("MULTIPLY", In("Leaf Size"), 0.3))); tb.inp(ti, "Local Space", True)
    rl = tb.n("GeometryNodeRealizeInstances"); tb.inp(rl, "Geometry", ti.outputs[0])
    foliage_std = tb.join(blobs, rl.outputs[0])

    # ---------------------------------------------------------------- palm fronds
    tb.frame_("Palm: fronds (bent, V-folded, tapered grids) around the trunk top, crown, coconuts")
    smp = tb.n("GeometryNodeSampleCurve", mode="FACTOR"); tb.inp(smp, "Curves", trunk_curve); tb.inp(smp, "Factor", 1.0); tb.inp(smp, "Curve Index", 0)
    top = smp.outputs["Position"]
    nf = tb.math("MAXIMUM", tb.math("ROUND", cluster_target), 4.0)
    fpts = tb.n("GeometryNodePoints"); tb.inp(fpts, "Count", nf); tb.inp(fpts, "Position", top)
    fyaw = tb.math("ADD", tb.math("MULTIPLY", index, tb.math("DIVIDE", TAU, nf)), _rand(tb, -0.25, 0.25, seed, 41))
    fpitch = _rand(tb, -0.95, 0.7, seed, 42)
    dead = tb.compare("LESS_THAN", fpitch, -0.78)
    ftint = tb.switch(dead, tint, 0.97)
    fp = tb.store(fpts.outputs[0], "foliage_tint", ftint); fp = tb.store(fp, "leaf_card", 2.0)
    Lf = tb.math("MULTIPLY", In("Cluster Size"), _rand(tb, 0.8, 1.15, seed, 43))
    grid = tb.n("GeometryNodeMeshGrid"); tb.inp(grid, "Size X", 1.0); tb.inp(grid, "Size Y", 1.0); tb.inp(grid, "Vertices X", tb.switch(low, 11, 5, "INT")); tb.inp(grid, "Vertices Y", tb.switch(low, 5, 3, "INT"))
    gx, gy, _ = tb.separate(pos)
    s = tb.math("ADD", gx, 0.5)
    width = tb.math("ADD", 0.12, tb.math("MULTIPLY", 0.88, tb.math("POWER", tb.math("MAXIMUM", tb.math("SINE", tb.math("MULTIPLY", s, math.pi)), 0.0), 0.7)))
    ny = tb.math("MULTIPLY", gy, width)
    nz = tb.math("SUBTRACT", tb.math("MULTIPLY", -0.55, tb.math("MULTIPLY", s, s)), tb.math("MULTIPLY", tb.math("ABSOLUTE", gy), tb.math("MULTIPLY", width, 0.35)))
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", grid.outputs[0]); tb.inp(sp, "Position", tb.combine(s, ny, nz))
    frond = tb.store(sp.outputs[0], "UVMap", grid.outputs["UV Map"], "FLOAT2", "CORNER")
    fronds = _instance(tb, fp, frond, _euler(tb, tb.combine(0.0, tb.math("MULTIPLY", fpitch, -1.0), fyaw)), tb.combine(Lf, tb.math("MULTIPLY", Lf, In("Leaf Size")), Lf))
    crown = tb.n("GeometryNodeMeshIcoSphere"); tb.inp(crown, "Radius", tb.math("MULTIPLY", In("Base Radius"), 1.6)); tb.inp(crown, "Subdivisions", blob_sub)
    ctr = tb.n("GeometryNodeTransform"); tb.inp(ctr, "Geometry", crown.outputs[0]); tb.inp(ctr, "Translation", tb.vmath("ADD", top, (0.0, 0.0, -0.05)))
    cpts = tb.n("GeometryNodePoints"); tb.inp(cpts, "Count", 5)
    ca = tb.math("MULTIPLY", index, 1.2566)
    tb.inp(cpts, "Position", tb.vmath("ADD", top, tb.combine(tb.math("MULTIPLY", tb.math("COSINE", ca), 0.3), tb.math("MULTIPLY", tb.math("SINE", ca), 0.3), -0.35)))
    coco = tb.n("GeometryNodeMeshIcoSphere"); tb.inp(coco, "Radius", 0.13); tb.inp(coco, "Subdivisions", 1)
    coconuts = tb.switch(low, _instance(tb, cpts.outputs[0], coco.outputs[0]), tb.empty(), "GEOMETRY")
    palm_wood = tb.join(ctr.outputs[0], coconuts)

    # ---------------------------------------------------------------- assemble
    tb.frame_("Assemble: wood (Bark) + leaves (Foliage)")
    branches = tb.switch(has_branches, tb.empty(), tb.join(l1_mesh, l2_mesh), "GEOMETRY")
    wood = tb.join(trunk_mesh, branches, tb.switch(is_palm, tb.empty(), palm_wood, "GEOMETRY"))
    ss = tb.n("GeometryNodeSetShadeSmooth", domain="FACE"); tb.inp(ss, "Geometry", wood); tb.inp(ss, "Shade Smooth", True)
    sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", ss.outputs[0]); tb.inp(sm, "Material", In("Bark"))
    leaves = tb.switch(is_palm, foliage_std, fronds, "GEOMETRY")
    lx, ly, lz = tb.separate(pos)   # shrubs: nothing below the ground
    clamp = tb.n("GeometryNodeSetPosition"); tb.inp(clamp, "Geometry", leaves); tb.inp(clamp, "Position", tb.combine(lx, ly, tb.math("MAXIMUM", lz, 0.02)))
    sm2 = tb.n("GeometryNodeSetMaterial"); tb.inp(sm2, "Geometry", clamp.outputs[0]); tb.inp(sm2, "Material", In("Foliage"))
    go = tb.n("NodeGroupOutput"); tb.link(tb.join(sm.outputs[0], sm2.outputs[0]), go.inputs[0])
    # the menu sockets learn their items from the linked Menu Switch nodes on the next tree update
    for attempt in range(2):
        try:
            I["Style"].default_value = "Round"; I["Quality"].default_value = "Full"; break
        except TypeError:
            try: g.interface_update(bpy.context)
            except Exception: pass
            try: bpy.context.view_layer.update()
            except Exception: pass
    return g


# ============================================================================== shaders
def _mixc(tb, fac, a, b):
    n = tb.n("ShaderNodeMix", data_type="RGBA"); tb.inp(n, "Factor_Float", fac); tb.inp(n, "A_Color", a); tb.inp(n, "B_Color", b)
    return next(o for o in n.outputs if o.identifier == "Result_Color")


def _smooth(tb, v, a, b): return tb.map_range(v, a, b, 0.0, 1.0, interp="SMOOTHSTEP")


def _snoise(tb, vec, scale, detail=3.0, rough=0.5, color=False):
    n = tb.n("ShaderNodeTexNoise", noise_dimensions="3D"); tb.inp(n, "Vector", vec); tb.inp(n, "Scale", scale); tb.inp(n, "Detail", detail); tb.inp(n, "Roughness", rough)
    return n.outputs["Color"] if color else n.outputs["Fac"]


def _attr(tb, name):
    n = tb.n("ShaderNodeAttribute"); n.attribute_name = name; return n


def _bark_shader():
    g = new_tree(MRS + "BarkShader", "ShaderNodeTree")
    sock(g, "BSDF", "OUTPUT", "NodeSocketShader")
    for nm, st, d, lo, hi, desc in (
            ("Bark Color", "NodeSocketColor", (0.30, 0.22, 0.15, 1.0), None, None, "Ridge colour"),
            ("Crevice Color", "NodeSocketColor", (0.09, 0.06, 0.04, 1.0), None, None, "Colour deep in the cracks"),
            ("Scale", "NodeSocketFloat", 1.0, 0.1, 10.0, "Pattern scale (fibres per metre around the trunk)"),
            ("Crack Depth", "NodeSocketFloat", 0.85, 0.0, 1.0, "Vertical crack network strength"),
            ("Fibre Contrast", "NodeSocketFloat", 0.6, 0.0, 1.0, "Stretched fibre noise contrast"),
            ("Bump Strength", "NodeSocketFloat", 1.0, 0.0, 2.0, ""),
            ("Roughness", "NodeSocketFloat", 0.85, 0.0, 1.0, ""),
            ("Lenticels", "NodeSocketFloat", 0.0, 0.0, 1.0, "Horizontal dark marks (birch)"),
            ("Lenticel Color", "NodeSocketColor", (0.06, 0.05, 0.045, 1.0), None, None, ""),
            ("Moss", "NodeSocketFloat", 0.15, 0.0, 1.0, "Green tint near the ground"),
            ("Moss Color", "NodeSocketColor", (0.16, 0.24, 0.07, 1.0), None, None, "")):
        sock(g, nm, "INPUT", st, d, lo, hi, desc)
    tb = T(g)
    tb.frame_("Coordinates: UV (u around, v metres) -> seamless ring + axis")
    gi = tb.n("NodeGroupInput"); I = lambda n: gi.outputs[n]
    uv = _attr(tb, "UVMap").outputs["Vector"]
    u, v, _ = tb.separate(uv)
    ang = tb.math("MULTIPLY", u, TAU); cx = tb.math("COSINE", ang); cy = tb.math("SINE", ang)
    obj = tb.n("ShaderNodeTexCoord").outputs["Object"]
    _, _, oz = tb.separate(obj)
    tb.frame_("Fibres, cracks, lenticels")
    fib_vec = tb.vmath("SCALE", tb.combine(tb.math("MULTIPLY", cx, 1.2), tb.math("MULTIPLY", cy, 1.2), tb.math("MULTIPLY", v, 0.22)), scale=I("Scale"))
    fibre = _snoise(tb, fib_vec, 4.0, 6.0, 0.7)
    # crack network: large plates (tall cells) + a finer secondary network; both wobble with the fibre noise
    wob = tb.vmath("SCALE", tb.combine(fibre, fibre, 0.0), scale=0.25)
    vor = tb.n("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    tb.inp(vor, "Vector", tb.vmath("ADD", tb.vmath("SCALE", tb.combine(cx, cy, tb.math("MULTIPLY", v, 0.3)), scale=tb.math("MULTIPLY", I("Scale"), 1.7)), wob))
    tb.inp(vor, "Scale", 1.0)
    vor2 = tb.n("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    tb.inp(vor2, "Vector", tb.vmath("ADD", tb.vmath("SCALE", tb.combine(cx, cy, tb.math("MULTIPLY", v, 0.45)), scale=tb.math("MULTIPLY", I("Scale"), 4.0)), wob))
    tb.inp(vor2, "Scale", 1.0)
    crack = tb.math("MAXIMUM", tb.map_range(vor.outputs["Distance"], 0.0, 0.11, 1.0, 0.0, interp="SMOOTHSTEP"),
                    tb.math("MULTIPLY", 0.6, tb.map_range(vor2.outputs["Distance"], 0.0, 0.07, 1.0, 0.0, interp="SMOOTHSTEP")))
    crack = tb.math("MULTIPLY", crack, _smooth(tb, _snoise(tb, obj, 0.8, 2.0), 0.2, 0.5))
    # bark plates between the cracks: each plate a slightly different tone
    plate = _snoise(tb, tb.vmath("SCALE", tb.combine(cx, cy, tb.math("MULTIPLY", v, 0.3)), scale=I("Scale")), 2.0, 1.0)
    depth = tb.math("MINIMUM", tb.math("ADD", tb.math("MULTIPLY", crack, I("Crack Depth")), tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, fibre), I("Fibre Contrast"))), 1.0)
    col = _mixc(tb, depth, I("Bark Color"), I("Crevice Color"))
    big = _snoise(tb, obj, 0.4, 2.0)
    k = tb.math("MULTIPLY", tb.math("ADD", 0.7, tb.math("ADD", tb.math("MULTIPLY", big, 0.35), tb.math("MULTIPLY", plate, 0.3))), tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", depth, 0.45)))
    col = tb.vmath("SCALE", col, scale=k)
    # lenticels (birch): horizontally stretched dark marks + faint horizontal peel lines
    lnoise = _snoise(tb, tb.vmath("SCALE", tb.combine(tb.math("MULTIPLY", cx, 0.5), tb.math("MULTIPLY", cy, 0.5), tb.math("MULTIPLY", v, 9.0)), scale=I("Scale")), 3.0, 2.0)
    lmask = tb.math("MULTIPLY", _smooth(tb, lnoise, 0.55, 0.62), I("Lenticels"))
    col = _mixc(tb, lmask, col, I("Lenticel Color"))
    peel = _snoise(tb, tb.vmath("SCALE", tb.combine(tb.math("MULTIPLY", cx, 0.15), tb.math("MULTIPLY", cy, 0.15), tb.math("MULTIPLY", v, 30.0)), scale=I("Scale")), 2.0, 1.0)
    col = _mixc(tb, tb.math("MULTIPLY", _smooth(tb, peel, 0.6, 0.7), tb.math("MULTIPLY", I("Lenticels"), 0.35)), col, tb.vmath("SCALE", col, scale=0.55))
    mz = tb.math("MULTIPLY", tb.map_range(oz, 0.0, 2.5, 1.0, 0.0), tb.math("MULTIPLY", I("Moss"), _smooth(tb, _snoise(tb, obj, 2.0, 2.0), 0.45, 0.6)))
    col = _mixc(tb, mz, col, I("Moss Color"))
    tb.frame_("Bump + BSDF")
    height = tb.math("ADD", tb.math("MULTIPLY", fibre, 0.6), tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, crack), 0.4))
    bump = tb.n("ShaderNodeBump"); tb.inp(bump, "Strength", I("Bump Strength")); tb.inp(bump, "Distance", 0.3); tb.inp(bump, "Height", height)
    rough = tb.math("ADD", tb.math("SUBTRACT", I("Roughness"), tb.math("MULTIPLY", fibre, 0.15)), tb.math("MULTIPLY", crack, 0.1))
    b = tb.n("ShaderNodeBsdfPrincipled"); tb.inp(b, "Base Color", col); tb.inp(b, "Roughness", rough); tb.inp(b, "Normal", bump.outputs[0]); tb.inp(b, "Specular IOR Level", 0.3)
    go = tb.n("NodeGroupOutput"); tb.link(b.outputs[0], go.inputs[0])
    return g


def _foliage_shader():
    g = new_tree(MRS + "FoliageShader", "ShaderNodeTree")
    sock(g, "BSDF", "OUTPUT", "NodeSocketShader")
    for nm, st, d, lo, hi, desc in (
            ("Leaf Color", "NodeSocketColor", (0.10, 0.30, 0.07, 1.0), None, None, "Shaded / inner leaves"),
            ("Leaf Color 2", "NodeSocketColor", (0.32, 0.46, 0.11, 1.0), None, None, "Sunlit / outer leaves"),
            ("Tint Variation", "NodeSocketFloat", 0.7, 0.0, 1.0, "How far the per-cluster foliage_tint attribute pushes between the two colours"),
            ("Translucency", "NodeSocketFloat", 0.35, 0.0, 1.0, "Backlit leaf glow (translucent BSDF mix)"),
            ("Roughness", "NodeSocketFloat", 0.55, 0.0, 1.0, ""),
            ("Leaf Shape", "NodeSocketFloat", 0.0, 0.0, 2.0, "Card mask: 0 broad lobed leaves, 1 needle star, 2 pinnate frond"),
            ("Leaf Scale", "NodeSocketFloat", 1.0, 0.1, 5.0, "Mask pattern scale on the cards"),
            ("Alpha Clip", "NodeSocketFloat", 1.0, 0.0, 1.0, "1 = cut the leaf shape out of the cards / holes in the blobs"),
            ("Autumn", "NodeSocketFloat", 0.0, 0.0, 1.0, "Clusters with a high tint turn to Autumn Color"),
            ("Autumn Color", "NodeSocketColor", (0.75, 0.28, 0.05, 1.0), None, None, "")):
        sock(g, nm, "INPUT", st, d, lo, hi, desc)
    tb = T(g)
    tb.frame_("Colour: two tones by foliage_tint + fine noise, autumn turn")
    gi = tb.n("NodeGroupInput"); I = lambda n: gi.outputs[n]
    tint = _attr(tb, "foliage_tint").outputs["Fac"]; card = _attr(tb, "leaf_card").outputs["Fac"]
    obj = tb.n("ShaderNodeTexCoord").outputs["Object"]
    fine = _snoise(tb, obj, 2.5, 2.0)
    w = tb.math("ADD", 0.5, tb.math("MULTIPLY", I("Tint Variation"), tb.math("ADD", tb.math("MULTIPLY", tb.math("SUBTRACT", tint, 0.5), 1.6), tb.math("MULTIPLY", tb.math("SUBTRACT", fine, 0.5), 0.5))))
    col = _mixc(tb, tb.math("MINIMUM", tb.math("MAXIMUM", w, 0.0), 1.0), I("Leaf Color"), I("Leaf Color 2"))
    aut = tb.math("MULTIPLY", I("Autumn"), _smooth(tb, tint, 0.3, 0.9))
    col = _mixc(tb, aut, col, tb.vmath("SCALE", I("Autumn Color"), scale=tb.math("ADD", 0.75, tb.math("MULTIPLY", fine, 0.5))))
    tb.frame_("Masks: broad lobes / needle star / pinnate frond on the cards, noise holes in the blobs")
    uv = _attr(tb, "UVMap").outputs["Vector"]
    u, v, _ = tb.separate(uv)
    cu = tb.math("SUBTRACT", u, 0.5); cv = tb.math("SUBTRACT", v, 0.5)
    rad = tb.math("MULTIPLY", tb.math("SQRT", tb.math("ADD", tb.math("MULTIPLY", cu, cu), tb.math("MULTIPLY", cv, cv))), 2.0)
    pvec = tb.vmath("ADD", tb.vmath("SCALE", tb.combine(u, v, 0.0), scale=tb.math("MULTIPLY", 3.0, I("Leaf Scale"))), tb.vmath("SCALE", obj, scale=0.5))
    # broad: a bunch of lobed leaves = irregular outline (low-frequency noise) with notches (higher-frequency noise)
    edge = tb.math("ADD", rad, tb.math("MULTIPLY", tb.math("SUBTRACT", _snoise(tb, pvec, 1.6, 2.0), 0.5), 0.9))
    notch = tb.math("ADD", tb.math("MULTIPLY", tb.math("SUBTRACT", _snoise(tb, pvec, 5.0, 1.0), 0.5), 0.5), tb.math("MULTIPLY", rad, 0.55))
    a_broad = tb.math("MULTIPLY", tb.math("LESS_THAN", edge, 0.9), tb.math("LESS_THAN", notch, 0.42))
    # needle tuft: 16 radial needles tapering toward the tips around a filled centre
    angle = tb.math("ADD", tb.math("ARCTAN2", cv, cu), tb.math("MULTIPLY", tb.math("SUBTRACT", _snoise(tb, pvec, 1.2, 1.0), 0.5), 0.9))  # wobbly, irregular needles
    stripe = tb.math("MULTIPLY", tb.math("ABSOLUTE", tb.math("SUBTRACT", tb.math("FRACT", tb.math("MULTIPLY", angle, 14.0 / TAU)), 0.5)), 2.0)
    ray_len = tb.math("ADD", 0.55, tb.math("MULTIPLY", _snoise(tb, tb.vmath("SCALE", tb.combine(tb.math("MULTIPLY", angle, 3.0), 0.0, 0.0), scale=1.0), 1.0, 1.0), 0.5))
    a_needle = tb.math("MULTIPLY", tb.math("LESS_THAN", rad, ray_len), tb.math("MAXIMUM", tb.math("LESS_THAN", rad, 0.3), tb.math("LESS_THAN", stripe, tb.math("SUBTRACT", 0.75, tb.math("MULTIPLY", rad, 0.6)))))
    across = tb.math("MULTIPLY", tb.math("ABSOLUTE", cv), 2.0)
    rib = tb.math("LESS_THAN", across, 0.07)
    # leaflets slant toward the tip and separate toward the edge (feathery), the outer tips are jagged
    leaflets = tb.math("LESS_THAN", tb.math("FRACT", tb.math("SUBTRACT", tb.math("MULTIPLY", u, 22.0), tb.math("MULTIPLY", across, 0.9))), tb.math("SUBTRACT", 0.8, tb.math("MULTIPLY", across, 0.45)))
    tipcut = tb.math("LESS_THAN", across, tb.math("ADD", 0.72, tb.math("MULTIPLY", _snoise(tb, tb.vmath("SCALE", tb.combine(tb.math("MULTIPLY", u, 40.0), 0.0, 0.0), scale=1.0), 1.0, 1.0), 0.5)))
    a_frond = tb.math("MAXIMUM", rib, tb.math("MULTIPLY", leaflets, tb.math("MULTIPLY", tb.math("GREATER_THAN", u, 0.12), tipcut)))
    # blobs: gaps between the leaf masses, cut much harder toward the silhouette (Facing) so the outline is ragged, not a sphere
    facing = tb.n("ShaderNodeLayerWeight"); tb.inp(facing, "Blend", 0.5)
    a_blob = tb.math("GREATER_THAN", _snoise(tb, obj, tb.math("DIVIDE", 5.0, I("Leaf Scale")), 2.0), tb.math("ADD", 0.22, tb.math("MULTIPLY", facing.outputs["Facing"], 0.5)))
    a_card = tb.math("ADD", tb.math("MULTIPLY", a_broad, tb.math("LESS_THAN", I("Leaf Shape"), 0.5)),
                     tb.math("ADD", tb.math("MULTIPLY", a_needle, tb.math("MULTIPLY", tb.math("GREATER_THAN", I("Leaf Shape"), 0.5), tb.math("LESS_THAN", I("Leaf Shape"), 1.5))),
                             tb.math("MULTIPLY", a_frond, tb.math("GREATER_THAN", I("Leaf Shape"), 1.5))))
    is_blob = tb.math("LESS_THAN", card, 0.5); is_frond = tb.math("GREATER_THAN", card, 1.5)
    a = tb.math("ADD", tb.math("MULTIPLY", a_blob, is_blob),
                tb.math("ADD", tb.math("MULTIPLY", a_frond, is_frond), tb.math("MULTIPLY", a_card, tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, is_blob), tb.math("SUBTRACT", 1.0, is_frond)))))
    alpha = tb.math("ADD", tb.math("SUBTRACT", 1.0, I("Alpha Clip")), tb.math("MULTIPLY", I("Alpha Clip"), a))
    tb.frame_("BSDF: principled + translucent, alpha via transparent mix")
    rough = tb.math("ADD", I("Roughness"), tb.math("MULTIPLY", tb.math("SUBTRACT", fine, 0.5), 0.3))
    # leafy shading on the blobs: a noise bump breaks the smooth sphere lighting into individual leaf masses
    leafy = tb.n("ShaderNodeBump"); tb.inp(leafy, "Strength", tb.math("MULTIPLY", is_blob, 1.0)); tb.inp(leafy, "Distance", 0.25)
    tb.inp(leafy, "Height", _snoise(tb, obj, tb.math("DIVIDE", 7.0, I("Leaf Scale")), 4.0, 0.65))
    b = tb.n("ShaderNodeBsdfPrincipled"); tb.inp(b, "Base Color", col); tb.inp(b, "Roughness", rough); tb.inp(b, "Specular IOR Level", 0.35); tb.inp(b, "Normal", leafy.outputs[0])
    tl = tb.n("ShaderNodeBsdfTranslucent"); tb.inp(tl, "Color", tb.vmath("SCALE", col, scale=1.3))
    mx = tb.n("ShaderNodeMixShader"); tb.inp(mx, "Fac", tb.math("MULTIPLY", I("Translucency"), 0.45)); tb.link(b.outputs[0], mx.inputs[1]); tb.link(tl.outputs[0], mx.inputs[2])
    tr = tb.n("ShaderNodeBsdfTransparent")
    mx2 = tb.n("ShaderNodeMixShader"); tb.inp(mx2, "Fac", alpha); tb.link(tr.outputs[0], mx2.inputs[1]); tb.link(mx.outputs[0], mx2.inputs[2])
    go = tb.n("NodeGroupOutput"); tb.link(mx2.outputs[0], go.inputs[0])
    return g


def _group_material(name, group, rgb, **vals):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (320, 0)
    gn = nt.nodes.new("ShaderNodeGroup"); gn.node_tree = bpy.data.node_groups[MRS + group]; gn.name = "MRS"; gn.label = MRS + group; gn.width = 260
    for k, v in vals.items(): gn.inputs[k].default_value = v
    nt.links.new(gn.outputs[0], out.inputs[0])
    m.diffuse_color = (*rgb, 1.0)
    return m


BARK_VARIANTS = {
    "Bark": dict(rgb=(0.30, 0.22, 0.15)),
    "Bark_Pine": dict(rgb=(0.36, 0.2, 0.12), vals={"Bark Color": (0.38, 0.21, 0.12, 1), "Crevice Color": (0.08, 0.05, 0.035, 1), "Crack Depth": 0.9, "Fibre Contrast": 0.35, "Scale": 0.8}),
    "Bark_Birch": dict(rgb=(0.82, 0.8, 0.75), vals={"Bark Color": (0.84, 0.82, 0.76, 1), "Crevice Color": (0.3, 0.28, 0.25, 1), "Crack Depth": 0.25, "Fibre Contrast": 0.25, "Lenticels": 1.0, "Bump Strength": 0.3, "Roughness": 0.7, "Moss": 0.05}),
    "Bark_Palm": dict(rgb=(0.45, 0.38, 0.27), vals={"Bark Color": (0.46, 0.38, 0.26, 1), "Crevice Color": (0.14, 0.1, 0.06, 1), "Crack Depth": 0.35, "Fibre Contrast": 0.8, "Scale": 1.6, "Moss": 0.0}),
    "Bark_Poplar": dict(rgb=(0.42, 0.42, 0.37), vals={"Bark Color": (0.44, 0.44, 0.38, 1), "Crevice Color": (0.12, 0.11, 0.09, 1), "Crack Depth": 0.5, "Fibre Contrast": 0.3, "Scale": 1.2}),
}
FOLIAGE_VARIANTS = {
    "Foliage": dict(rgb=(0.12, 0.32, 0.08)),
    "Foliage_Maple": dict(rgb=(0.2, 0.4, 0.09), vals={"Leaf Color": (0.14, 0.33, 0.06, 1), "Leaf Color 2": (0.42, 0.5, 0.12, 1)}),
    "Foliage_MapleAutumn": dict(rgb=(0.7, 0.3, 0.06), vals={"Leaf Color": (0.25, 0.3, 0.05, 1), "Leaf Color 2": (0.6, 0.45, 0.08, 1), "Autumn": 1.0, "Autumn Color": (0.78, 0.22, 0.04, 1), "Tint Variation": 0.9}),
    "Foliage_Poplar": dict(rgb=(0.22, 0.42, 0.1), vals={"Leaf Color": (0.16, 0.34, 0.08, 1), "Leaf Color 2": (0.45, 0.55, 0.16, 1), "Leaf Scale": 1.3}),
    "Foliage_Pine": dict(rgb=(0.05, 0.18, 0.08), vals={"Leaf Color": (0.03, 0.13, 0.06, 1), "Leaf Color 2": (0.13, 0.3, 0.12, 1), "Leaf Shape": 1.0, "Translucency": 0.15, "Roughness": 0.7},),
    "Foliage_Palm": dict(rgb=(0.15, 0.4, 0.12), vals={"Leaf Color": (0.1, 0.3, 0.08, 1), "Leaf Color 2": (0.35, 0.55, 0.15, 1), "Leaf Shape": 2.0, "Autumn": 1.0, "Autumn Color": (0.5, 0.36, 0.14, 1), "Tint Variation": 0.5}),
    "Foliage_Birch": dict(rgb=(0.35, 0.55, 0.15), vals={"Leaf Color": (0.22, 0.4, 0.09, 1), "Leaf Color 2": (0.55, 0.65, 0.2, 1), "Leaf Scale": 1.6, "Translucency": 0.5}),
    "Foliage_Shrub": dict(rgb=(0.1, 0.27, 0.08), vals={"Leaf Color": (0.07, 0.22, 0.06, 1), "Leaf Color 2": (0.22, 0.4, 0.1, 1), "Leaf Scale": 1.8}),
}


def build_tree_materials():
    """Shader groups MRS_BarkShader / MRS_FoliageShader + materials MRS_Bark*, MRS_Foliage*. Returns {name: material}."""
    _bark_shader(); _foliage_shader()
    out = {}
    for nm, spec in BARK_VARIANTS.items():
        out[nm] = _group_material(MRS + nm, "BarkShader", spec["rgb"], **spec.get("vals", {}))
    for nm, spec in FOLIAGE_VARIANTS.items():
        m = out[nm] = _group_material(MRS + nm, "FoliageShader", spec["rgb"], **spec.get("vals", {}))
        m.surface_render_method = "DITHERED"; m.use_backface_culling = False
        for attr, val in (("use_transparent_shadow", True), ("use_backface_culling_shadow", False)):
            if hasattr(m, attr):
                try: setattr(m, attr, val)
                except Exception: pass
    return out


# ============================================================================== species and variants
SPECIES = {
    "Oak": dict(Style="Round", Height=12.0, **{"Base Radius": 0.45, "Taper": 0.75, "Lean": 0.05, "Trunk Noise": 0.35, "Count": 13, "Start Height": 0.28, "Length": 4.2, "Droop": 0.3,
                "Up Tilt": 0.8, "Radius": 0.13, "Levels": 2, "Cluster Count": 50, "Cluster Size": 1.1, "Leaf Density": 1.8, "Leaf Size": 1.0, "Color Variation": 0.6,
                "Height Jitter": 0.08, "Canopy Jitter": 0.25}, Bark="Bark", Foliage="Foliage"),
    "Maple": dict(Style="Spreading", Height=10.5, **{"Base Radius": 0.4, "Taper": 0.8, "Lean": 0.0, "Trunk Noise": 0.3, "Count": 11, "Start Height": 0.3, "Length": 4.3, "Droop": 0.2,
                  "Up Tilt": 0.55, "Radius": 0.12, "Levels": 2, "Cluster Count": 50, "Cluster Size": 1.05, "Leaf Density": 1.8, "Leaf Size": 1.0, "Color Variation": 0.6,
                  "Height Jitter": 0.08, "Canopy Jitter": 0.25}, Bark="Bark", Foliage="Foliage_Maple"),
    "Poplar": dict(Style="Columnar", Height=16.5, **{"Base Radius": 0.32, "Taper": 0.85, "Lean": 0.0, "Trunk Noise": 0.15, "Count": 30, "Start Height": 0.1, "Length": 3.2, "Droop": 0.0,
                   "Up Tilt": 2.0, "Radius": 0.07, "Levels": 1, "Cluster Count": 44, "Cluster Size": 0.75, "Leaf Density": 1.3, "Leaf Size": 0.7, "Color Variation": 0.5,
                   "Height Jitter": 0.06, "Canopy Jitter": 0.2}, Bark="Bark_Poplar", Foliage="Foliage_Poplar"),
    "Pine": dict(Style="Conical", Height=14.5, **{"Base Radius": 0.38, "Taper": 1.0, "Lean": 0.0, "Trunk Noise": 0.12, "Count": 26, "Start Height": 0.22, "Length": 3.6, "Droop": 0.35,
                 "Up Tilt": 0.1, "Radius": 0.08, "Levels": 1, "Cluster Count": 54, "Cluster Size": 0.85, "Leaf Density": 1.6, "Leaf Size": 0.55, "Color Variation": 0.4,
                 "Height Jitter": 0.08, "Canopy Jitter": 0.2}, Bark="Bark_Pine", Foliage="Foliage_Pine"),
    "Palm": dict(Style="Palm", Height=9.0, **{"Base Radius": 0.26, "Taper": 0.2, "Lean": 0.35, "Trunk Noise": 0.25, "Count": 0, "Start Height": 0.5, "Length": 1.0, "Droop": 0.0,
                 "Up Tilt": 0.5, "Radius": 0.05, "Levels": 1, "Cluster Count": 22, "Cluster Size": 3.4, "Leaf Density": 1.0, "Leaf Size": 0.5, "Color Variation": 0.5,
                 "Height Jitter": 0.1, "Canopy Jitter": 0.2}, Bark="Bark_Palm", Foliage="Foliage_Palm"),
    "Birch": dict(Style="Round", Height=13.0, **{"Base Radius": 0.22, "Taper": 0.8, "Lean": 0.08, "Trunk Noise": 0.3, "Count": 16, "Start Height": 0.3, "Length": 3.4, "Droop": 0.75,
                  "Up Tilt": 1.0, "Radius": 0.06, "Levels": 2, "Cluster Count": 46, "Cluster Size": 0.8, "Leaf Density": 1.8, "Leaf Size": 0.7, "Color Variation": 0.5,
                  "Height Jitter": 0.08, "Canopy Jitter": 0.3}, Bark="Bark_Birch", Foliage="Foliage_Birch"),
    "ShrubRound": dict(Style="Shrub", Height=0.5, **{"Base Radius": 0.07, "Taper": 0.3, "Lean": 0.0, "Trunk Noise": 0.2, "Count": 12, "Start Height": 0.1, "Length": 1.2, "Droop": 0.1,
                       "Up Tilt": 1.3, "Radius": 0.025, "Levels": 1, "Cluster Count": 20, "Cluster Size": 0.6, "Leaf Density": 1.2, "Leaf Size": 0.4, "Color Variation": 0.5,
                       "Height Jitter": 0.1, "Canopy Jitter": 0.25}, Bark="Bark", Foliage="Foliage_Shrub"),
    "ShrubHedge": dict(Style="Shrub", Height=0.6, **{"Base Radius": 0.08, "Taper": 0.3, "Lean": 0.0, "Trunk Noise": 0.2, "Count": 18, "Start Height": 0.1, "Length": 1.5, "Droop": 0.15,
                       "Up Tilt": 0.9, "Radius": 0.03, "Levels": 1, "Cluster Count": 28, "Cluster Size": 0.65, "Leaf Density": 1.2, "Leaf Size": 0.42, "Color Variation": 0.45,
                       "Height Jitter": 0.1, "Canopy Jitter": 0.25}, Bark="Bark", Foliage="Foliage_Shrub"),
}
# (object name, species, overrides)
VARIANTS = [
    ("MRS_Tree_Oak_A", "Oak", {"Seed": 11}),
    ("MRS_Tree_Oak_B", "Oak", {"Seed": 23, "Height": 10.5, "Count": 12, "Lean": -0.06, "Cluster Count": 46}),
    ("MRS_Tree_Maple_A", "Maple", {"Seed": 31}),
    ("MRS_Tree_Maple_B", "Maple", {"Seed": 47, "Height": 9.5, "Length": 4.0, "Cluster Count": 44, "Foliage": "Foliage_MapleAutumn"}),
    ("MRS_Tree_Poplar_A", "Poplar", {"Seed": 53}),
    ("MRS_Tree_Poplar_B", "Poplar", {"Seed": 67, "Height": 14.5, "Count": 28, "Cluster Count": 42}),
    ("MRS_Tree_Pine_A", "Pine", {"Seed": 71}),
    ("MRS_Tree_Pine_B", "Pine", {"Seed": 89, "Height": 16.5, "Length": 3.2, "Count": 30, "Cluster Count": 50}),
    ("MRS_Tree_Palm_A", "Palm", {"Seed": 97}),
    ("MRS_Tree_Palm_B", "Palm", {"Seed": 101, "Height": 7.0, "Lean": 0.55, "Cluster Count": 20, "Cluster Size": 3.0}),
    ("MRS_Tree_Birch_A", "Birch", {"Seed": 113}),
    ("MRS_Tree_Birch_B", "Birch", {"Seed": 127, "Height": 11.0, "Lean": -0.12, "Droop": 0.9, "Cluster Count": 40}),
]
SHRUB_VARIANTS = [
    ("MRS_Shrub_Round", "ShrubRound", {"Seed": 131}),
    ("MRS_Shrub_Hedge", "ShrubHedge", {"Seed": 137}),
]


def variant_params(species, overrides=None):
    """Complete modifier-input dict for a species (+ overrides); material names resolved to materials."""
    p = dict(SPECIES[species]); p.update(overrides or {})
    for k in ("Bark", "Foliage"):
        if isinstance(p[k], str): p[k] = bpy.data.materials[MRS + p[k]]
    return p


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def _fix_uv_seam(me, bark_slots):
    """Cylindrical UVs wrap at u = 0/1: on faces that straddle the seam move the low u's up by one."""
    uv = me.uv_layers.get("UVMap")
    if uv is None: return
    data = uv.data
    for p in me.polygons:
        if p.material_index not in bark_slots: continue
        us = [data[l].uv.x for l in p.loop_indices]
        if max(us) - min(us) > 0.5:
            for l in p.loop_indices:
                if data[l].uv.x < 0.5: data[l].uv.x += 1.0


def realize_tree(params, quality="Full", name="MRS_TreeBake"):
    """Evaluate Tree_Variants with `params` on a temporary object and return a new standalone mesh."""
    g = bpy.data.node_groups.get(GROUP) or build_tree_group()
    src = bpy.data.meshes.new(name + "_src"); ob = bpy.data.objects.new(name + "_tmp", src)
    sc = scene(); sc.collection.objects.link(ob)
    mod = ob.modifiers.new("Tree", "NODES"); mod.node_group = g
    for k, v in params.items(): mod_input_set(mod, k, v)
    mod_input_set(mod, "Quality", quality)
    try:
        dg = depsgraph()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        bpy.data.objects.remove(ob); bpy.data.meshes.remove(src)
    me.name = name
    # drop empty material slots (geometry that had no material before Set Material) and remap
    # (Mesh.materials.pop re-indexes the polygons itself)
    for i in reversed([i for i, m in enumerate(me.materials) if m is None]): me.materials.pop(index=i)
    bark_slots = {i for i, m in enumerate(me.materials) if m is not None and m.name.startswith(MRS + "Bark")}
    _fix_uv_seam(me, bark_slots)
    me.update()
    return me


def _library_object(col, name, me):
    me.name = name
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.hide_viewport = True; o.hide_render = True
    return o


def build_trees():
    """Bake every variant (Full into MRS_Trees / MRS_Shrubs, Low into MRS_Trees_LOD1 / MRS_Shrubs_LOD1).
    Returns {"Trees": col, "Trees_LOD1": col, "Shrubs": col, "Shrubs_LOD1": col}."""
    build_tree_materials(); build_tree_group()
    cols = {k: collection(MRS + k) for k in ("Trees", "Trees_LOD1", "Shrubs", "Shrubs_LOD1")}
    for key, variants in (("Trees", VARIANTS), ("Shrubs", SHRUB_VARIANTS)):
        for name, species, over in variants:
            params = variant_params(species, over)
            _library_object(cols[key], name, realize_tree(params, "Full", name))
            _library_object(cols[key + "_LOD1"], name + "_LOD1", realize_tree(params, "Low", name + "_LOD1"))
    return cols


build_groups = build_trees
