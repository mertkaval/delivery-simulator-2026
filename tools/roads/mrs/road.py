"""MRS_Road v2: the Geometry Nodes road group (one modifier on a curve object).

Panels: Output (viewport / render quality, export switches), Terrain (raycast conforming, smoothing,
embankments, cut walls), Profile (asymmetric lanes, shoulders, bike lanes, parking, median, curbs with
bevel, sidewalks, crown camber, superelevation), Markings (centre / lane / edge lines, bike lane, parking
ticks, lane arrows at junctions), Structure (ground or elevated deck with pillars, barriers), Roadside
(props, streetlights, trees, manholes, drains), Scatter (embankment vegetation), Materials, Junction.

Attributes left on the mesh: `lat` (lateral metres), `along` (metres along the road), `side` (right
vector), `kind` (0 asphalt, 1 marking, 2 concrete, 3 structure, 4 embankment, 5 bike lane), `UVMap`.
"""
import bpy, math
from .nodes import T, MRS, new_tree, sock, add_inputs

INPUTS = [
    ("Output", [
        ("Viewport Quality", "NodeSocketMenu", "Preview", None, None, "Mesh density in the viewport"),
        ("Render Quality", "NodeSocketMenu", "Final", None, None, "Mesh density at render time"),
        ("Realize Instances", "NodeSocketBool", False, None, None, "Props become real geometry (export)"),
        ("Collision Only", "NodeSocketBool", False, None, None, "Only drivable / walkable surfaces, no markings or props (collision export)"),
    ]),
    ("Terrain", [
        ("Terrain", "NodeSocketObject", None, None, None, "Terrain mesh the road is projected onto"),
        ("Terrain Collection", "NodeSocketCollection", None, None, None, "Or a collection of terrain pieces"),
        ("Conform", "NodeSocketBool", True, None, None, "Project the road onto the terrain (ground mode)"),
        ("Height Offset", "NodeSocketFloat", 0.08, -2.0, 5.0, "Road surface above the terrain hit (m)"),
        ("Smoothing", "NodeSocketInt", 4, 0, 40, "Blur iterations on the projected heights and the banking"),
        ("Embankment", "NodeSocketBool", True, None, None, "Slopes from the road edge down (or up) to the terrain"),
        ("Embankment Width", "NodeSocketFloat", 6.0, 0.5, 40.0, "Horizontal reach of the slope (m)"),
        ("Embankment Softness", "NodeSocketFloat", 0.6, 0.0, 1.0, "0 straight slope, 1 rounded shoulder"),
        ("Retaining Wall", "NodeSocketBool", True, None, None, "Vertical wall where the cut is deeper than the threshold"),
        ("Wall Threshold", "NodeSocketFloat", 1.5, 0.2, 20.0, "Cut depth that switches the slope to a wall (m)"),
    ]),
    ("Profile", [
        ("Lanes Forward", "NodeSocketInt", 1, 0, 6, "Lanes on the right of the centre (driving direction of the curve)"),
        ("Lanes Backward", "NodeSocketInt", 1, 0, 6, "Lanes on the left of the centre"),
        ("Lane Width", "NodeSocketFloat", 3.2, 2.0, 6.0, "Width of one lane (m)"),
        ("Shoulder", "NodeSocketFloat", 0.0, 0.0, 3.0, "Paved shoulder each side (m)"),
        ("Bike Lane Left", "NodeSocketFloat", 0.0, 0.0, 3.0, "Bike lane width (0 = none)"),
        ("Bike Lane Right", "NodeSocketFloat", 0.0, 0.0, 3.0, "Bike lane width (0 = none)"),
        ("Parking Left", "NodeSocketFloat", 0.0, 0.0, 3.0, "Parallel parking width (0 = none)"),
        ("Parking Right", "NodeSocketFloat", 0.0, 0.0, 3.0, "Parallel parking width (0 = none)"),
        ("Median", "NodeSocketFloat", 0.0, 0.0, 8.0, "Raised median width (0 = none)"),
        ("Median Height", "NodeSocketFloat", 0.15, 0.0, 1.0, ""),
        ("Curb Width", "NodeSocketFloat", 0.25, 0.1, 0.6, "Curb stone width (m)"),
        ("Curb Height", "NodeSocketFloat", 0.15, 0.0, 0.4, "Curb / sidewalk height (m)"),
        ("Curb Bevel", "NodeSocketFloat", 0.04, 0.0, 0.2, "Chamfer on the curb edge (m)"),
        ("Sidewalk Left", "NodeSocketBool", True, None, None, ""), ("Sidewalk Right", "NodeSocketBool", True, None, None, ""),
        ("Sidewalk Width Left", "NodeSocketFloat", 2.0, 0.5, 8.0, ""), ("Sidewalk Width Right", "NodeSocketFloat", 2.0, 0.5, 8.0, ""),
        ("Crown", "NodeSocketFloat", 2.0, 0.0, 6.0, "Cross-fall from the centre to the edges (%)"),
        ("Superelevation", "NodeSocketFloat", 4.0, 0.0, 12.0, "Maximum banking in bends (degrees, 0 = flat)"),
        ("Resolution", "NodeSocketFloat", 1.0, 0.2, 10.0, "Sampling step along the road (m)"),
    ]),
    ("Markings", [
        ("Centre Line", "NodeSocketMenu", "Dashed", None, None, ""),
        ("Lane Lines", "NodeSocketBool", True, None, None, "Dashed lines between lanes"),
        ("Edge Lines", "NodeSocketBool", False, None, None, "Solid lines at the carriageway edge"),
        ("Parking Ticks", "NodeSocketBool", True, None, None, "Bay dividers in the parking strip"),
        ("Bay Length", "NodeSocketFloat", 5.5, 3.0, 12.0, ""),
        ("Lane Arrows", "NodeSocketBool", True, None, None, "Turn arrows in each lane before a junction"),
        ("Arrow Distance", "NodeSocketFloat", 9.0, 3.0, 40.0, "Arrow centre before the trimmed end (m)"),
        ("Marking Width", "NodeSocketFloat", 0.12, 0.05, 0.4, ""), ("Dash Length", "NodeSocketFloat", 3.0, 0.3, 12.0, ""), ("Dash Gap", "NodeSocketFloat", 6.0, 0.3, 20.0, ""),
        ("Markings Collection", "NodeSocketCollection", None, None, None, "Arrow and tick meshes (MRS_Markings)"),
    ]),
    ("Structure", [
        ("Mode", "NodeSocketMenu", "Ground", None, None, "Ground: on the terrain. Elevated: deck on pillars"),
        ("Deck Thickness", "NodeSocketFloat", 1.2, 0.3, 4.0, ""),
        ("Pillar Spacing", "NodeSocketFloat", 24.0, 4.0, 120.0, ""),
        ("Pillars", "NodeSocketCollection", None, None, None, "Pillar meshes, 1 m tall, scaled to the ground"),
        ("Barrier Left", "NodeSocketMenu", "None", None, None, ""), ("Barrier Right", "NodeSocketMenu", "None", None, None, ""),
        ("Barriers", "NodeSocketCollection", None, None, None, "2 m barrier segments: guardrail, jersey, parapet, railing"),
    ]),
    ("Roadside", [
        ("Props", "NodeSocketCollection", None, None, None, "Collection of roadside props (one is picked per point)"),
        ("Prop Spacing", "NodeSocketFloat", 28.0, 2.0, 200.0, ""), ("Prop Offset", "NodeSocketFloat", 0.5, 0.0, 10.0, "Lateral offset behind the curb (m)"),
        ("Prop Side", "NodeSocketMenu", "Alternate", None, None, ""), ("Prop Seed", "NodeSocketInt", 0, 0, 10000, ""),
        ("Streetlights", "NodeSocketCollection", None, None, None, ""),
        ("Light Spacing", "NodeSocketFloat", 30.0, 5.0, 200.0, ""), ("Light Side", "NodeSocketMenu", "Alternate", None, None, ""),
        ("Trees", "NodeSocketCollection", None, None, None, ""),
        ("Tree Spacing", "NodeSocketFloat", 12.0, 2.0, 100.0, ""), ("Tree Side", "NodeSocketMenu", "None", None, None, ""),
        ("Tree Offset", "NodeSocketFloat", 1.0, 0.0, 10.0, "Beyond the sidewalk / verge edge (m)"),
        ("Manholes", "NodeSocketCollection", None, None, None, ""), ("Manhole Spacing", "NodeSocketFloat", 45.0, 5.0, 300.0, ""),
        ("Drains", "NodeSocketCollection", None, None, None, "Gully gratings at the curb"), ("Drain Spacing", "NodeSocketFloat", 25.0, 5.0, 200.0, ""),
    ]),
    ("Scatter", [
        ("Scatter", "NodeSocketCollection", None, None, None, "Grass clumps / rocks on the embankments"),
        ("Scatter Density", "NodeSocketFloat", 0.4, 0.0, 10.0, "Per square metre"),
        ("Scatter Seed", "NodeSocketInt", 0, 0, 10000, ""),
    ]),
    ("Materials", [
        ("Asphalt Material", "NodeSocketMaterial", None, None, None, ""), ("Marking Material", "NodeSocketMaterial", None, None, None, ""),
        ("Concrete Material", "NodeSocketMaterial", None, None, None, ""), ("Bike Lane Material", "NodeSocketMaterial", None, None, None, ""),
        ("Structure Material", "NodeSocketMaterial", None, None, None, ""), ("Embankment Material", "NodeSocketMaterial", None, None, None, ""),
    ]),
    ("Junction", [
        ("Trim Start", "NodeSocketFloat", 0.0, 0.0, 200.0, "Length cut off at the start (set by junctions)"),
        ("Trim End", "NodeSocketFloat", 0.0, 0.0, 200.0, "Length cut off at the end (set by junctions)"),
        ("Clear Start", "NodeSocketFloat", 0.0, 0.0, 60.0, "No roadside instances this close to the start"),
        ("Clear End", "NodeSocketFloat", 0.0, 0.0, 60.0, "No roadside instances this close to the end"),
        ("Lock Start", "NodeSocketBool", False, None, None, "Blend the start height to Lock Start Z (junction level)"),
        ("Lock Start Z", "NodeSocketFloat", 0.0, -1000.0, 1000.0, ""),
        ("Lock End", "NodeSocketBool", False, None, None, "Blend the end height to Lock End Z (junction level)"),
        ("Lock End Z", "NodeSocketFloat", 0.0, -1000.0, 1000.0, ""),
        ("Lock Length", "NodeSocketFloat", 14.0, 1.0, 80.0, "Blend distance from the trimmed end (m)"),
    ]),
]
KIND = dict(asphalt=0, marking=1, concrete=2, structure=3, embankment=4, bike=5)
BARRIERS = ["None", "Guardrail", "Jersey", "Parapet", "Railing", "Hedge", "Fence"]


def _coll_index(coll_name, obj_name):
    """Collection Info lists children sorted by object name: the pick index of `obj_name` in the
    collection as it exists at build time (-1 when missing)."""
    col = bpy.data.collections.get(coll_name)
    names = sorted(o.name for o in col.objects) if col else []
    return names.index(obj_name) if obj_name in names else -1
SIDES = ["None", "Left", "Right", "Both", "Alternate"]


def build_road_group():
    g = new_tree(MRS + "Road")
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    add_inputs(g, INPUTS)
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    tb = T(g)
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    I = lambda k: gi.outputs[k]
    neg = lambda s: tb.math("MULTIPLY", s, -1.0)
    R = lambda node: next((o for o in node.outputs if o.enabled), node.outputs[0])     # the live output of a Random Value node
    up = (0.0, 0.0, 1.0)

    # ---------------------------------------------------------------- quality
    tb.frame_("Output: quality by viewport / render")
    q_view = tb.menu_switch(I("Viewport Quality"), [("Preview", 2.5), ("Final", 1.0)], "FLOAT", "viewport quality")
    q_rend = tb.menu_switch(I("Render Quality"), [("Preview", 2.5), ("Final", 1.0)], "FLOAT", "render quality")
    is_vp = tb.n("GeometryNodeIsViewport").outputs[0]
    qf = tb.switch(is_vp, q_rend, q_view, "FLOAT")
    step = tb.math("MULTIPLY", I("Resolution"), qf)

    # ---------------------------------------------------------------- widths
    tb.frame_("Profile: widths from the inputs (right = forward lanes)")
    med_half = tb.math("MULTIPLY", I("Median"), 0.5)
    lw = I("Lane Width")
    carr_r = tb.math("ADD", med_half, tb.math("MULTIPLY", I("Lanes Forward"), lw))          # carriageway edge (lanes only)
    carr_l = tb.math("ADD", med_half, tb.math("MULTIPLY", I("Lanes Backward"), lw))
    sh_r = tb.math("ADD", carr_r, I("Shoulder")); sh_l = tb.math("ADD", carr_l, I("Shoulder"))
    bike_r = tb.math("ADD", sh_r, I("Bike Lane Right")); bike_l = tb.math("ADD", sh_l, I("Bike Lane Left"))
    half_r = tb.math("ADD", bike_r, I("Parking Right")); half_l = tb.math("ADD", bike_l, I("Parking Left"))   # asphalt edge
    curb_r = tb.math("ADD", half_r, I("Curb Width")); curb_l = tb.math("ADD", half_l, I("Curb Width"))
    sw_r = tb.math("ADD", curb_r, tb.switch(I("Sidewalk Right"), 0.0, I("Sidewalk Width Right"), "FLOAT"))
    sw_l = tb.math("ADD", curb_l, tb.switch(I("Sidewalk Left"), 0.0, I("Sidewalk Width Left"), "FLOAT"))
    H = I("Curb Height"); bev = tb.math("MINIMUM", I("Curb Bevel"), tb.math("MULTIPLY", H, 0.9))
    half_max = tb.math("MAXIMUM", half_l, half_r)
    crown_h = tb.math("MULTIPLY", tb.math("MULTIPLY", I("Crown"), 0.01), half_max)                 # camber height at the centre
    elevated = tb.menu_switch(I("Mode"), [("Ground", False), ("Elevated", True)], "BOOLEAN", "mode")
    grounded = tb.boolean("NOT", elevated)

    # ---------------------------------------------------------------- terrain geometry
    tb.frame_("Terrain: object + collection, relative space")
    t_obj = tb.n("GeometryNodeObjectInfo", transform_space="RELATIVE"); tb.inp(t_obj, "Object", I("Terrain"))
    t_col = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(t_col, "Collection", I("Terrain Collection"))
    t_real = tb.n("GeometryNodeRealizeInstances"); tb.inp(t_real, "Geometry", tb.join(t_obj.outputs["Geometry"], t_col.outputs[0]))
    terrain = t_real.outputs[0]

    def ray_down(pos):
        """Raycast straight down from 500 m above `pos` onto the terrain: (is_hit, hit_z)."""
        rc = tb.n("GeometryNodeRaycast", data_type="FLOAT")
        tb.inp(rc, "Target Geometry", terrain); tb.inp(rc, "Source Position", tb.vmath("ADD", pos, (0.0, 0.0, 500.0)))
        tb.inp(rc, "Ray Direction", (0.0, 0.0, -1.0)); tb.inp(rc, "Ray Length", 2000.0)
        hz = tb.separate(rc.outputs["Hit Position"])[2]
        return rc.outputs["Is Hit"], hz

    # ---------------------------------------------------------------- the rail
    tb.frame_("Rail: trim, resample, conform to terrain, smooth, bank, along / side attributes")
    clen = tb.n("GeometryNodeCurveLength"); tb.inp(clen, "Curve", I("Geometry"))
    trim = tb.n("GeometryNodeTrimCurve", mode="LENGTH"); tb.inp(trim, "Curve", I("Geometry"))
    tb.inp(trim, "Start_001", I("Trim Start")); tb.inp(trim, "End_001", tb.math("SUBTRACT", clen.outputs[0], I("Trim End")))
    res = tb.n("GeometryNodeResampleCurve"); tb.inp(res, "Curve", trim.outputs[0])
    try: res.inputs["Mode"].default_value = "Length"
    except Exception: res.mode = "LENGTH"
    tb.inp(res, "Length", step)
    pos = tb.n("GeometryNodeInputPosition").outputs[0]
    px, py, pz = tb.separate(pos)
    hit, hz = ray_down(pos)
    conform = tb.boolean("AND", I("Conform"), tb.boolean("AND", hit, grounded))
    z_target = tb.switch(conform, pz, tb.math("ADD", hz, I("Height Offset")), "FLOAT")
    blur_z = tb.n("GeometryNodeBlurAttribute", data_type="FLOAT"); tb.inp(blur_z, "Value", z_target); tb.inp(blur_z, "Iterations", I("Smoothing"))
    # junction locks: within Lock Length of a trimmed end the height blends to the junction level
    sp0 = tb.n("GeometryNodeSplineParameter"); rlen0 = tb.n("GeometryNodeCurveLength"); tb.inp(rlen0, "Curve", res.outputs[0])
    def smooth01(v): return tb.math("MULTIPLY", v, tb.math("MULTIPLY", v, tb.math("SUBTRACT", 3.0, tb.math("MULTIPLY", 2.0, v))))
    w_s = smooth01(tb.map_range(sp0.outputs["Length"], 0.0, I("Lock Length"), 1.0, 0.0))
    w_e = smooth01(tb.map_range(tb.math("SUBTRACT", rlen0.outputs[0], sp0.outputs["Length"]), 0.0, I("Lock Length"), 1.0, 0.0))
    z1 = tb.switch(I("Lock Start"), blur_z.outputs[0], tb.math("ADD", blur_z.outputs[0], tb.math("MULTIPLY", tb.math("SUBTRACT", I("Lock Start Z"), blur_z.outputs[0]), w_s)), "FLOAT")
    z2 = tb.switch(I("Lock End"), z1, tb.math("ADD", z1, tb.math("MULTIPLY", tb.math("SUBTRACT", I("Lock End Z"), z1), w_e)), "FLOAT")
    conformed = tb.n("GeometryNodeSetPosition"); tb.inp(conformed, "Geometry", res.outputs[0]); tb.inp(conformed, "Position", tb.combine(px, py, z2))
    # banking from the signed turning angle between neighbouring tangents
    tang = tb.n("GeometryNodeInputTangent").outputs[0]
    idx = tb.n("GeometryNodeInputIndex").outputs[0]
    dsize = tb.n("GeometryNodeAttributeDomainSize", component="CURVE"); tb.inp(dsize, "Geometry", conformed.outputs[0])
    nxt = tb.n("GeometryNodeSampleIndex", data_type="FLOAT_VECTOR", domain="POINT"); tb.inp(nxt, "Geometry", conformed.outputs[0]); tb.inp(nxt, "Value", tang)
    tb.inp(nxt, "Index", tb.math("MINIMUM", tb.math("ADD", idx, 1.0), tb.math("SUBTRACT", dsize.outputs["Point Count"], 1.0)))
    t1 = nxt.outputs[0]
    cz = tb.separate(tb.vmath("CROSS_PRODUCT", tang, t1))[2]
    dotp = tb.vmath("DOT_PRODUCT", tang, t1)
    ang = tb.math("ARCTAN2", cz, dotp)
    curv = tb.math("DIVIDE", ang, step)
    max_bank = tb.math("RADIANS", I("Superelevation"))
    bank = tb.math("MULTIPLY", tb.math("MINIMUM", tb.math("MAXIMUM", tb.math("MULTIPLY", curv, 7.0), neg(max_bank)), max_bank), -1.0)
    blur_b = tb.n("GeometryNodeBlurAttribute", data_type="FLOAT"); tb.inp(blur_b, "Value", bank); tb.inp(blur_b, "Iterations", tb.math("ADD", I("Smoothing"), 2.0))
    normal_mode = tb.n("GeometryNodeSetCurveNormal"); tb.inp(normal_mode, "Curve", conformed.outputs[0])
    for attempt in ("Z Up", "Z_UP"):
        try: normal_mode.inputs["Mode"].default_value = attempt; break
        except Exception: continue
    tilt = tb.n("GeometryNodeSetCurveTilt"); tb.inp(tilt, "Curve", normal_mode.outputs[0]); tb.inp(tilt, "Tilt", blur_b.outputs[0])
    sp = tb.n("GeometryNodeSplineParameter")
    tang2 = tb.n("GeometryNodeInputTangent").outputs[0]
    side_v = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", tang2, up))
    rail = tb.store(tilt.outputs[0], "along", sp.outputs["Length"])
    rail = tb.store(rail, "side", side_v, "FLOAT_VECTOR")
    rail = tb.store(rail, "road_z", tb.separate(tb.n("GeometryNodeInputPosition").outputs[0])[2])
    rail_len = tb.n("GeometryNodeCurveLength"); tb.inp(rail_len, "Curve", rail)

    # ---------------------------------------------------------------- strips
    tb.frame_("Strips: a profile line (x = lateral, z = up) swept with Curve to Mesh, oriented, tagged")
    def strip(x0, z0, x1, z1, material, kind, label, orient="up", samples=2, zf=None):
        line = tb.n("GeometryNodeCurvePrimitiveLine", label)
        # Curve to Mesh: profile X -> curve normal side (lateral), profile Y -> world DOWN with Z-up normals, profile Z -> along the tangent
        tb.inp(line, "Start", tb.combine(x0, neg(z0) if isinstance(z0, bpy.types.NodeSocket) else -z0, 0.0)); tb.inp(line, "End", tb.combine(x1, neg(z1) if isinstance(z1, bpy.types.NodeSocket) else -z1, 0.0))
        prof = line.outputs[0]
        if samples > 2:
            rs = tb.n("GeometryNodeResampleCurve"); tb.inp(rs, "Curve", prof)
            try: rs.inputs["Mode"].default_value = "Count"
            except Exception: rs.mode = "COUNT"
            tb.inp(rs, "Count", samples); prof = rs.outputs[0]
        ppos = tb.n("GeometryNodeInputPosition").outputs[0]
        ppx = tb.separate(ppos)[0]
        if zf is not None:
            sp_ = tb.n("GeometryNodeSetPosition"); tb.inp(sp_, "Geometry", prof); tb.inp(sp_, "Offset", tb.combine(0.0, neg(zf(ppx)), 0.0)); prof = sp_.outputs[0]
            ppx = tb.separate(tb.n("GeometryNodeInputPosition").outputs[0])[0]
        prof = tb.store(prof, "lat", ppx)
        c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", rail); tb.inp(c2m, "Profile Curve", prof)
        geo = c2m.outputs[0]
        nrm = tb.n("GeometryNodeInputNormal").outputs[0]
        if orient == "up":
            sel = tb.compare("LESS_THAN", tb.separate(nrm)[2], 0.0)
        else:
            lat = tb.named("lat"); side_a = tb.named("side", "FLOAT_VECTOR")
            outward = tb.vmath("SCALE", side_a, scale=tb.math("SIGN", lat))
            d = tb.vmath("DOT_PRODUCT", nrm, outward)
            sel = tb.compare("LESS_THAN", d, 0.0) if orient == "out" else tb.compare("GREATER_THAN", d, 0.0)
        ff = tb.n("GeometryNodeFlipFaces"); tb.inp(ff, "Mesh", geo); tb.inp(ff, "Selection", sel)
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", ff.outputs[0]); tb.inp(sm, "Material", material)
        return tb.store(sm.outputs[0], "kind", float(KIND[kind]), "FLOAT", "FACE")

    camber = lambda x: tb.math("MULTIPLY", crown_h, tb.math("SUBTRACT", 1.0, tb.math("POWER", tb.math("DIVIDE", tb.math("ABSOLUTE", x), half_max), 2.0)))
    surf = []
    # asphalt: the whole carriageway incl. shoulders and parking, cambered (bike lanes get their own material strip on top)
    surf.append(strip(neg(half_l), 0.0, half_r, 0.0, I("Asphalt Material"), "asphalt", "asphalt", samples=11, zf=camber))
    for sgn, sh, bk, bw in ((1.0, sh_r, bike_r, I("Bike Lane Right")), (-1.0, sh_l, bike_l, I("Bike Lane Left"))):
        geo = strip(tb.math("MULTIPLY", sh, sgn), 0.003, tb.math("MULTIPLY", bk, sgn), 0.003, I("Bike Lane Material"), "bike", "bike lane", samples=3, zf=camber)
        surf.append(tb.switch(tb.compare("GREATER_THAN", bw, 0.05), tb.empty(), geo, "GEOMETRY"))
    # curbs: face, bevel, top; sidewalk slab and outer edge; both sides
    for sgn, half, curb, sw, on in ((1.0, half_r, curb_r, sw_r, I("Sidewalk Right")), (-1.0, half_l, curb_l, sw_l, I("Sidewalk Left"))):
        x_in = tb.math("MULTIPLY", half, sgn); x_bev = tb.math("MULTIPLY", tb.math("ADD", half, bev), sgn); x_out = tb.math("MULTIPLY", curb, sgn)
        surf.append(strip(x_in, 0.0, x_in, tb.math("SUBTRACT", H, bev), I("Concrete Material"), "concrete", "curb face", orient="in"))
        surf.append(strip(x_in, tb.math("SUBTRACT", H, bev), x_bev, H, I("Concrete Material"), "concrete", "curb bevel"))
        surf.append(strip(x_bev, H, x_out, H, I("Concrete Material"), "concrete", "curb top"))
        x_sw = tb.math("MULTIPLY", sw, sgn)
        slab = strip(x_out, H, x_sw, H, I("Concrete Material"), "concrete", "sidewalk")
        edge = strip(x_sw, H, x_sw, 0.0, I("Concrete Material"), "concrete", "sidewalk edge", orient="out")
        surf.append(tb.switch(on, tb.empty(), tb.join(slab, edge), "GEOMETRY"))
        # no sidewalk: the curb's outer face goes back down
        surf.append(tb.switch(on, strip(x_out, H, x_out, 0.0, I("Concrete Material"), "concrete", "curb back", orient="out"), tb.empty(), "GEOMETRY"))
    # median: raised kerbed strip
    MH = I("Median Height")
    med_top = tb.math("ADD", crown_h, MH)                 # the median sits on the crown of the camber
    med = tb.join(strip(neg(med_half), crown_h, neg(med_half), med_top, I("Concrete Material"), "concrete", "median face L", orient="in"),
                  strip(neg(med_half), med_top, med_half, med_top, I("Concrete Material"), "concrete", "median top"),
                  strip(med_half, med_top, med_half, crown_h, I("Concrete Material"), "concrete", "median face R", orient="in"))
    has_median = tb.compare("GREATER_THAN", I("Median"), 0.05)
    surf.append(tb.switch(has_median, tb.empty(), med, "GEOMETRY"))

    # ---------------------------------------------------------------- structure: elevated deck
    tb.frame_("Structure: deck under the road, pillars scaled to the terrain, barriers")
    DT = I("Deck Thickness")
    deck = tb.join(strip(neg(sw_l), 0.0, neg(sw_l), neg(DT), I("Structure Material"), "structure", "deck side L", orient="out"),
                   strip(neg(sw_l), neg(DT), sw_r, neg(DT), I("Structure Material"), "structure", "deck bottom", orient="up"),
                   strip(sw_r, neg(DT), sw_r, 0.0, I("Structure Material"), "structure", "deck side R", orient="out"))
    # deck bottom must face down: flip it (orient "up" selected faces with normal.z < 0 to flip, so flip all again)
    ffb = tb.n("GeometryNodeFlipFaces"); tb.inp(ffb, "Mesh", deck)
    deck_geo = tb.switch(elevated, tb.empty(), ffb.outputs[0], "GEOMETRY")

    def points_along(spacing, clear_s, clear_e):
        t2 = tb.n("GeometryNodeTrimCurve", mode="LENGTH"); tb.inp(t2, "Curve", rail)
        tb.inp(t2, "Start_001", clear_s); tb.inp(t2, "End_001", tb.math("SUBTRACT", rail_len.outputs[0], clear_e))
        c2p = tb.n("GeometryNodeCurveToPoints", mode="LENGTH"); tb.inp(c2p, "Curve", t2.outputs[0]); tb.inp(c2p, "Length", spacing)
        side = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", c2p.outputs["Tangent"], up))
        return c2p, side

    pil, pil_side = points_along(I("Pillar Spacing"), tb.math("ADD", I("Clear Start"), 4.0), tb.math("ADD", I("Clear End"), 4.0))
    ppos = tb.n("GeometryNodeInputPosition").outputs[0]
    phit, phz = ray_down(ppos)
    ground_z = tb.switch(phit, 0.0, phz, "FLOAT")
    pil_h = tb.math("MAXIMUM", tb.math("SUBTRACT", tb.math("SUBTRACT", tb.separate(ppos)[2], DT), ground_z), 0.1)
    # the height is captured on the points first: fields evaluate in the context of the node that uses them,
    # and after Set Position the point already sits on the ground
    pts0 = tb.store(pil.outputs["Points"], "pil_h", pil_h)
    pil_h = tb.named("pil_h")
    pil_pts = tb.n("GeometryNodeSetPosition"); tb.inp(pil_pts, "Geometry", pts0); tb.inp(pil_pts, "Offset", tb.combine(0.0, 0.0, neg(tb.math("ADD", pil_h, DT))))
    pcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(pcoll, "Collection", I("Pillars")); tb.inp(pcoll, "Separate Children", True); tb.inp(pcoll, "Reset Children", True)
    palign = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(palign, "Vector", pil.outputs["Tangent"])
    piop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(piop, "Points", pil_pts.outputs[0]); tb.inp(piop, "Instance", pcoll.outputs[0]); tb.inp(piop, "Pick Instance", True)
    tb.inp(piop, "Rotation", palign.outputs[0]); tb.inp(piop, "Scale", tb.combine(tb.math("ADD", 1.0, tb.math("MULTIPLY", tb.math("ADD", I("Lanes Forward"), I("Lanes Backward")), 0.12)), 1.0, pil_h))
    pillars = tb.switch(elevated, tb.empty(), piop.outputs[0], "GEOMETRY")

    # barriers: 2 m segments on both edges, picked by menu
    bcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(bcoll, "Collection", I("Barriers")); tb.inp(bcoll, "Separate Children", True); tb.inp(bcoll, "Reset Children", True)
    barriers = []
    for sgn, sw, menu in ((1.0, sw_r, I("Barrier Right")), (-1.0, sw_l, I("Barrier Left"))):
        bidx = tb.menu_switch(menu, [(nm, -1 if nm == "None" else _coll_index(MRS + "Barriers", MRS + nm)) for nm in BARRIERS], "INT", "barrier")
        bp, bside = points_along(2.0, I("Clear Start"), I("Clear End"))
        moved = tb.n("GeometryNodeSetPosition"); tb.inp(moved, "Geometry", bp.outputs["Points"])
        tb.inp(moved, "Offset", tb.vmath("ADD", tb.vmath("SCALE", bside, scale=tb.math("MULTIPLY", tb.math("SUBTRACT", sw, 0.25), sgn)), tb.combine(0.0, 0.0, H)))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.vmath("SCALE", bp.outputs["Tangent"], scale=sgn))
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", moved.outputs[0]); tb.inp(io, "Instance", bcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", bidx); tb.inp(io, "Rotation", al.outputs[0])
        barriers.append(tb.switch(tb.compare("LESS_THAN", bidx, 0, "INT"), io.outputs[0], tb.empty(), "GEOMETRY"))

    # ---------------------------------------------------------------- embankments and cut walls (ground mode)
    tb.frame_("Terrain: embankment slopes to the raycast terrain height, walls in deep cuts")
    EW = I("Embankment Width"); soft = I("Embankment Softness")
    emb = []; walls = []
    for sgn, sw in ((1.0, sw_r), (-1.0, sw_l)):
        x0 = tb.math("MULTIPLY", sw, sgn); x1 = tb.math("MULTIPLY", tb.math("ADD", sw, EW), sgn)
        geo = strip(x0, 0.0, x1, 0.0, I("Embankment Material"), "embankment", "embankment", samples=7)
        vpos = tb.n("GeometryNodeInputPosition").outputs[0]
        vhit, vhz = ray_down(vpos)
        lat = tb.named("lat")
        f = tb.map_range(tb.math("ABSOLUTE", lat), sw, tb.math("ADD", sw, EW), 0.0, 1.0)
        f_soft = tb.math("MULTIPLY", f, tb.math("MULTIPLY", f, tb.math("SUBTRACT", 3.0, tb.math("MULTIPLY", 2.0, f))))      # smoothstep
        f_mix = tb.map_range(soft, 0.0, 1.0, f, f_soft)
        road_z = tb.named("road_z")
        depth = tb.math("SUBTRACT", vhz, road_z)                                   # + cut (terrain above), - fill
        wall_here = tb.boolean("AND", I("Retaining Wall"), tb.compare("GREATER_THAN", depth, I("Wall Threshold")))
        z_new = tb.math("SUBTRACT", tb.math("ADD", road_z, tb.math("MULTIPLY", depth, f_mix)), tb.math("MULTIPLY", f, 0.12))   # outer edge dives under the terrain
        vx, vy, vz = tb.separate(vpos)
        set_ = tb.n("GeometryNodeSetPosition"); tb.inp(set_, "Geometry", geo); tb.inp(set_, "Selection", vhit); tb.inp(set_, "Position", tb.combine(vx, vy, z_new))
        # delete slope faces that are walls (face evaluates the point field)
        del_ = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(del_, "Geometry", set_.outputs[0]); tb.inp(del_, "Selection", wall_here)
        emb.append(del_.outputs[0])
        # wall: vertical from the road edge up to the terrain (a 1 m tall strip whose top is set to the terrain height)
        wgeo = strip(x0, 0.0, x0, 1.0, I("Structure Material"), "structure", "retaining wall", orient="in")
        wpos = tb.n("GeometryNodeInputPosition").outputs[0]
        whit, whz = ray_down(tb.vmath("ADD", wpos, tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=tb.math("MULTIPLY", 0.3, sgn))))
        wtop = tb.compare("GREATER_THAN", tb.math("SUBTRACT", tb.separate(wpos)[2], tb.named("road_z")), 0.5)
        wdepth = tb.math("SUBTRACT", whz, tb.named("road_z"))
        wset = tb.n("GeometryNodeSetPosition"); tb.inp(wset, "Geometry", wgeo); tb.inp(wset, "Selection", tb.boolean("AND", wtop, whit))
        wx, wy, wz = tb.separate(wpos)
        tb.inp(wset, "Position", tb.combine(wx, wy, tb.math("ADD", tb.named("road_z"), tb.math("MAXIMUM", wdepth, 0.0))))
        keep_wall = tb.boolean("AND", I("Retaining Wall"), tb.compare("GREATER_THAN", wdepth, I("Wall Threshold")))
        wdel = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(wdel, "Geometry", wset.outputs[0]); tb.inp(wdel, "Selection", tb.boolean("NOT", keep_wall))
        walls.append(wdel.outputs[0])
    emb_on = tb.boolean("AND", I("Embankment"), tb.boolean("AND", grounded, I("Conform")))
    emb_geo = tb.switch(emb_on, tb.empty(), tb.join(*emb, *walls), "GEOMETRY")

    # ---------------------------------------------------------------- markings
    tb.frame_("Markings: thin strips at lateral offsets on the camber, dashes cut by 'along'")
    mw = I("Marking Width"); mw2 = tb.math("MULTIPLY", mw, 0.5)
    def marking(xc, dashed, label):
        zc = tb.math("ADD", camber(xc), 0.004)
        geo = strip(tb.math("SUBTRACT", xc, mw2), zc, tb.math("ADD", xc, mw2), zc, I("Marking Material"), "marking", label)
        if dashed is None: return geo
        along_a = tb.named("along")
        period = tb.math("ADD", I("Dash Length"), I("Dash Gap"))
        gap_sel = tb.compare("GREATER_THAN", tb.math("MODULO", along_a, period), I("Dash Length"))
        delete = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(delete, "Geometry", geo); tb.inp(delete, "Selection", tb.boolean("AND", gap_sel, dashed))
        return delete.outputs[0]
    marks = []
    c_mode = I("Centre Line")
    c_idx = tb.menu_switch(c_mode, [("None", 0), ("Solid", 1), ("Dashed", 2), ("Double", 3)], "INT", "centre line")   # one switch per menu socket
    c_single = marking(0.0, tb.compare("EQUAL", c_idx, 2, "INT"), "centre line")
    dbl = tb.join(marking(neg(tb.math("ADD", med_half, mw)), None, "double L"), marking(tb.math("ADD", med_half, mw), None, "double R"))
    centre_geo = tb.switch(tb.compare("EQUAL", c_idx, 0, "INT"), tb.switch(tb.compare("EQUAL", c_idx, 3, "INT"), c_single, dbl, "GEOMETRY"), tb.empty(), "GEOMETRY")
    two_way = tb.boolean("AND", tb.compare("GREATER_THAN", I("Lanes Forward"), 0, "INT"), tb.compare("GREATER_THAN", I("Lanes Backward"), 0, "INT"))
    marks.append(tb.switch(tb.boolean("AND", two_way, tb.boolean("NOT", has_median)), tb.empty(), centre_geo, "GEOMETRY"))
    for k in (1, 2, 3, 4, 5):
        for sgn, n_l in ((1.0, I("Lanes Forward")), (-1.0, I("Lanes Backward"))):
            x = tb.math("MULTIPLY", tb.math("ADD", med_half, tb.math("MULTIPLY", lw, float(k))), sgn)
            geo = marking(x, tb.boolean("OR", True, True), "lane line %d" % k)
            on = tb.boolean("AND", I("Lane Lines"), tb.compare("LESS_THAN", k, n_l, "INT"))
            marks.append(tb.switch(on, tb.empty(), geo, "GEOMETRY"))
    for sgn, carr in ((1.0, carr_r), (-1.0, carr_l)):
        geo = marking(tb.math("MULTIPLY", tb.math("SUBTRACT", carr, tb.math("ADD", mw, 0.05)), sgn), None, "edge line")
        marks.append(tb.switch(I("Edge Lines"), tb.empty(), geo, "GEOMETRY"))
    # bike lane boundary lines and parking strip lines
    for sgn, sh, bk, bw, pk, pw in ((1.0, sh_r, bike_r, I("Bike Lane Right"), half_r, I("Parking Right")), (-1.0, sh_l, bike_l, I("Bike Lane Left"), half_l, I("Parking Left"))):
        geo = marking(tb.math("MULTIPLY", tb.math("ADD", sh, mw), sgn), None, "bike line")
        marks.append(tb.switch(tb.compare("GREATER_THAN", bw, 0.05), tb.empty(), geo, "GEOMETRY"))
        geo = marking(tb.math("MULTIPLY", tb.math("ADD", bk, mw), sgn), None, "parking line")
        marks.append(tb.switch(tb.compare("GREATER_THAN", pw, 0.05), tb.empty(), geo, "GEOMETRY"))
    # parking ticks: instanced unit quads (MRS_MarkTick: 1 m along x, 1 m along y) every Bay Length
    mcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(mcoll, "Collection", I("Markings Collection")); tb.inp(mcoll, "Separate Children", True); tb.inp(mcoll, "Reset Children", True)
    ticks = []
    for sgn, bk, pw in ((1.0, bike_r, I("Parking Right")), (-1.0, bike_l, I("Parking Left"))):
        tp, tside = points_along(I("Bay Length"), I("Clear Start"), I("Clear End"))
        xc = tb.math("ADD", bk, tb.math("MULTIPLY", pw, 0.5))
        mv = tb.n("GeometryNodeSetPosition"); tb.inp(mv, "Geometry", tp.outputs["Points"])
        tb.inp(mv, "Offset", tb.vmath("ADD", tb.vmath("SCALE", tside, scale=tb.math("MULTIPLY", xc, sgn)), tb.combine(0.0, 0.0, tb.math("ADD", camber(xc), 0.004))))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tp.outputs["Tangent"])
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", mv.outputs[0]); tb.inp(io, "Instance", mcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", _coll_index(MRS + "Markings", MRS + "MarkTick")); tb.inp(io, "Rotation", al.outputs[0]); tb.inp(io, "Scale", tb.combine(tb.math("SUBTRACT", pw, 0.1), mw, 1.0))
        ticks.append(tb.switch(tb.boolean("AND", I("Parking Ticks"), tb.compare("GREATER_THAN", pw, 0.05)), tb.empty(), io.outputs[0], "GEOMETRY"))
    # lane arrows before a junction: forward lanes at the end, backward lanes at the start
    arrows = []
    for sgn, n_l, at_end in ((1.0, I("Lanes Forward"), True), (-1.0, I("Lanes Backward"), False)):
        L = rail_len.outputs[0]
        dist = tb.math("SUBTRACT", L, I("Arrow Distance")) if at_end else I("Arrow Distance")
        samp = tb.n("GeometryNodeSampleCurve", mode="LENGTH", data_type="FLOAT"); tb.inp(samp, "Curves", rail); tb.inp(samp, "Length", dist)
        pts = tb.n("GeometryNodePoints"); tb.inp(pts, "Count", n_l)
        pidx = tb.n("GeometryNodeInputIndex").outputs[0]
        s_side = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", samp.outputs["Tangent"], up))
        xl = tb.math("MULTIPLY", tb.math("ADD", med_half, tb.math("MULTIPLY", tb.math("ADD", pidx, 0.5), lw)), sgn)
        tb.inp(pts, "Position", tb.vmath("ADD", samp.outputs["Position"], tb.vmath("ADD", tb.vmath("SCALE", s_side, scale=xl), tb.combine(0.0, 0.0, tb.math("ADD", camber(xl), 0.004)))))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.vmath("SCALE", samp.outputs["Tangent"], scale=sgn))
        # inner lane straight+left, outer lane straight+right, middle / single lane straight (indices by sorted name)
        A = lambda nm: _coll_index(MRS + "Markings", MRS + nm)
        is_inner = tb.compare("EQUAL", pidx, 0, "INT"); is_outer = tb.compare("EQUAL", pidx, tb.math("SUBTRACT", n_l, 1.0), "INT")
        aidx = tb.switch(tb.compare("EQUAL", n_l, 1, "INT"), tb.switch(is_inner, tb.switch(is_outer, A("ArrowStraight"), A("ArrowStraightRight"), "INT"), A("ArrowStraightLeft"), "INT"), A("ArrowStraight"), "INT")
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", pts.outputs[0]); tb.inp(io, "Instance", mcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", aidx); tb.inp(io, "Rotation", al.outputs[0])
        trim_here = I("Trim End") if at_end else I("Trim Start")
        on = tb.boolean("AND", I("Lane Arrows"), tb.boolean("AND", tb.compare("GREATER_THAN", trim_here, 0.5), tb.compare("GREATER_THAN", L, tb.math("MULTIPLY", I("Arrow Distance"), 2.0))))
        arrows.append(tb.switch(on, tb.empty(), io.outputs[0], "GEOMETRY"))

    # ---------------------------------------------------------------- roadside instances
    tb.frame_("Roadside: props, streetlights, trees, manholes, drains")
    def pick_side(menu):
        return tb.menu_switch(menu, [(nm, i) for i, nm in enumerate(SIDES)], "INT", "side")
    def side_points(spacing, side_idx, offset_l, offset_r, up_l, up_r, clear_extra=0.0):
        """Points on the left and right verge selected by a SIDES index; returns the joined points with
        'sgn' (-1 left / +1 right) and the tangent stored."""
        outs = []
        for sgn, off, upz, keep_idx in ((-1.0, offset_l, up_l, (1, 3, 4)), (1.0, offset_r, up_r, (2, 3, 4))):
            c2p, side = points_along(spacing, tb.math("ADD", I("Clear Start"), clear_extra), tb.math("ADD", I("Clear End"), clear_extra))
            pidx = tb.n("GeometryNodeInputIndex").outputs[0]
            alt_keep = tb.compare("EQUAL", tb.math("MODULO", pidx, 2.0), 0.0 if sgn < 0 else 1.0)
            keep = tb.boolean("OR", tb.compare("EQUAL", side_idx, keep_idx[0], "INT"), tb.compare("EQUAL", side_idx, keep_idx[1], "INT"))
            keep = tb.boolean("OR", keep, tb.boolean("AND", tb.compare("EQUAL", side_idx, 4, "INT"), alt_keep))
            mv = tb.n("GeometryNodeSetPosition"); tb.inp(mv, "Geometry", c2p.outputs["Points"])
            tb.inp(mv, "Offset", tb.vmath("ADD", tb.vmath("SCALE", side, scale=tb.math("MULTIPLY", off, sgn)), tb.combine(0.0, 0.0, upz)))
            st = tb.store(mv.outputs[0], "sgn", sgn); st = tb.store(st, "tangent", c2p.outputs["Tangent"], "FLOAT_VECTOR"); st = tb.store(st, "side", side, "FLOAT_VECTOR")
            dl = tb.n("GeometryNodeDeleteGeometry", domain="POINT", mode="ALL"); tb.inp(dl, "Geometry", st); tb.inp(dl, "Selection", tb.boolean("NOT", keep))
            outs.append(dl.outputs[0])
        return tb.join(*outs)
    def instance_facing_road(points, collection, seed, random_pick=True, yaw_jitter=0.0, scale_jitter=0.0):
        coll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(coll, "Collection", collection); tb.inp(coll, "Separate Children", True); tb.inp(coll, "Reset Children", True)
        sgn_a = tb.named("sgn"); side_a = tb.named("side", "FLOAT_VECTOR")
        facing = tb.vmath("SCALE", side_a, scale=neg(sgn_a))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", facing)
        rot = al.outputs[0]
        if yaw_jitter > 0:
            rj = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(rj, "Min", -yaw_jitter); tb.inp(rj, "Max", yaw_jitter); tb.inp(rj, "Seed", tb.math("ADD", seed, 3.0))
            raa = tb.n("FunctionNodeAxisAngleToRotation"); tb.inp(raa, "Axis", up); tb.inp(raa, "Angle", R(rj))
            rz2 = tb.n("FunctionNodeRotateRotation", rotation_space="GLOBAL"); tb.inp(rz2, "Rotation", rot); tb.inp(rz2, "Rotate By", raa.outputs[0])
            rot = rz2.outputs[0]
        rnd = tb.n("FunctionNodeRandomValue", data_type="INT"); tb.inp(rnd, "Min", 0); tb.inp(rnd, "Max", 100); tb.inp(rnd, "Seed", seed)
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", points); tb.inp(io, "Instance", coll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", R(rnd) if random_pick else 0); tb.inp(io, "Rotation", rot)
        if scale_jitter > 0:
            sj = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(sj, "Min", 1.0 - scale_jitter); tb.inp(sj, "Max", 1.0 + scale_jitter); tb.inp(sj, "Seed", tb.math("ADD", seed, 11.0))
            tb.inp(io, "Scale", tb.combine(R(sj), R(sj), R(sj)))
        return io.outputs[0]
    # verge offsets: on the sidewalk slab when there is one, else just beyond the curb; height = curb top or 0
    v_l = tb.switch(I("Sidewalk Left"), tb.math("ADD", curb_l, 0.3), tb.math("ADD", curb_l, 0.6), "FLOAT"); v_r = tb.switch(I("Sidewalk Right"), tb.math("ADD", curb_r, 0.3), tb.math("ADD", curb_r, 0.6), "FLOAT")
    up_l = tb.switch(I("Sidewalk Left"), 0.0, H, "FLOAT"); up_r = tb.switch(I("Sidewalk Right"), 0.0, H, "FLOAT")
    props = instance_facing_road(side_points(I("Prop Spacing"), pick_side(I("Prop Side")), tb.math("ADD", v_l, I("Prop Offset")), tb.math("ADD", v_r, I("Prop Offset")), up_l, up_r, 3.0), I("Props"), I("Prop Seed"))
    lights = instance_facing_road(side_points(I("Light Spacing"), pick_side(I("Light Side")), v_l, v_r, up_l, up_r, 6.0), I("Streetlights"), tb.math("ADD", I("Prop Seed"), 1.0))
    trees = instance_facing_road(side_points(I("Tree Spacing"), pick_side(I("Tree Side")), tb.math("ADD", sw_l, I("Tree Offset")), tb.math("ADD", sw_r, I("Tree Offset")), 0.0, 0.0, 8.0), I("Trees"), tb.math("ADD", I("Prop Seed"), 2.0), yaw_jitter=3.14, scale_jitter=0.25)
    # manholes: random lateral position in the carriageway; drains at the curb line on both sides
    c2m_pts, side_m = points_along(I("Manhole Spacing"), tb.math("ADD", I("Clear Start"), 6.0), tb.math("ADD", I("Clear End"), 6.0))
    rndf = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(rndf, "Min", -0.8); tb.inp(rndf, "Max", 0.8); tb.inp(rndf, "Seed", tb.math("ADD", I("Prop Seed"), 7.0))
    mx = tb.math("MULTIPLY", R(rndf), tb.math("MULTIPLY", carr_r, 0.9))
    mp = tb.n("GeometryNodeSetPosition"); tb.inp(mp, "Geometry", c2m_pts.outputs["Points"]); tb.inp(mp, "Offset", tb.vmath("ADD", tb.vmath("SCALE", side_m, scale=mx), tb.combine(0.0, 0.0, tb.math("ADD", camber(mx), 0.002))))
    mcoll2 = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(mcoll2, "Collection", I("Manholes")); tb.inp(mcoll2, "Separate Children", True); tb.inp(mcoll2, "Reset Children", True)
    rndi = tb.n("FunctionNodeRandomValue", data_type="INT"); tb.inp(rndi, "Min", 0); tb.inp(rndi, "Max", 100); tb.inp(rndi, "Seed", I("Prop Seed"))
    miop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(miop, "Points", mp.outputs[0]); tb.inp(miop, "Instance", mcoll2.outputs[0]); tb.inp(miop, "Pick Instance", True); tb.inp(miop, "Instance Index", R(rndi))
    drains = []
    dcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(dcoll, "Collection", I("Drains")); tb.inp(dcoll, "Separate Children", True); tb.inp(dcoll, "Reset Children", True)
    for sgn, half in ((1.0, half_r), (-1.0, half_l)):
        dp, dside = points_along(I("Drain Spacing"), tb.math("ADD", I("Clear Start"), 2.0), tb.math("ADD", I("Clear End"), 2.0))
        xd = tb.math("MULTIPLY", tb.math("SUBTRACT", half, 0.3), sgn)
        dm = tb.n("GeometryNodeSetPosition"); tb.inp(dm, "Geometry", dp.outputs["Points"]); tb.inp(dm, "Offset", tb.vmath("ADD", tb.vmath("SCALE", dside, scale=xd), tb.combine(0.0, 0.0, 0.002)))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", dp.outputs["Tangent"])
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", dm.outputs[0]); tb.inp(io, "Instance", dcoll.outputs[0]); tb.inp(io, "Pick Instance", True); tb.inp(io, "Rotation", al.outputs[0])
        drains.append(io.outputs[0])

    # ---------------------------------------------------------------- scatter on the embankment faces
    tb.frame_("Scatter: grass / rocks on embankment faces")
    kind_a = tb.named("kind")
    dist = tb.n("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM"); tb.inp(dist, "Mesh", emb_geo)
    tb.inp(dist, "Selection", tb.compare("EQUAL", kind_a, float(KIND["embankment"]))); tb.inp(dist, "Density", I("Scatter Density")); tb.inp(dist, "Seed", I("Scatter Seed"))
    scoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(scoll, "Collection", I("Scatter")); tb.inp(scoll, "Separate Children", True); tb.inp(scoll, "Reset Children", True)
    srnd = tb.n("FunctionNodeRandomValue", data_type="INT"); tb.inp(srnd, "Min", 0); tb.inp(srnd, "Max", 100); tb.inp(srnd, "Seed", I("Scatter Seed"))
    srot = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(srot, "Min", 0.0); tb.inp(srot, "Max", 6.283); tb.inp(srot, "Seed", tb.math("ADD", I("Scatter Seed"), 5.0))
    sscl = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(sscl, "Min", 0.5); tb.inp(sscl, "Max", 1.0); tb.inp(sscl, "Seed", tb.math("ADD", I("Scatter Seed"), 9.0))
    sio = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(sio, "Points", dist.outputs["Points"]); tb.inp(sio, "Instance", scoll.outputs[0]); tb.inp(sio, "Pick Instance", True)
    tb.inp(sio, "Instance Index", R(srnd)); tb.inp(sio, "Rotation", tb.combine(0.0, 0.0, R(srot))); tb.inp(sio, "Scale", tb.combine(R(sscl), R(sscl), R(sscl)))
    scatter = tb.switch(tb.compare("GREATER_THAN", I("Scatter Density"), 0.001), tb.empty(), sio.outputs[0], "GEOMETRY")

    # ---------------------------------------------------------------- assembly
    tb.frame_("Assembly: UVMap (lateral, along), kind filter for collision, instances realized for export")
    surfaces = tb.join(*surf, deck_geo, emb_geo)
    mesh_all = tb.join(surfaces, *marks)
    mesh = tb.switch(I("Collision Only"), mesh_all, surfaces, "GEOMETRY")
    uv = tb.store(mesh, "UVMap", tb.combine(tb.named("lat"), tb.named("along"), 0.0), "FLOAT2", "CORNER")
    smooth = tb.n("GeometryNodeSetShadeSmooth"); tb.inp(smooth, "Geometry", uv); tb.inp(smooth, "Shade Smooth", tb.compare("EQUAL", tb.named("kind"), float(KIND["embankment"])))
    inst = tb.join(*ticks, *arrows, props, lights, trees, miop.outputs[0], *drains, *barriers, pillars, scatter)
    realized = tb.n("GeometryNodeRealizeInstances"); tb.inp(realized, "Geometry", inst)
    pil_real = tb.n("GeometryNodeRealizeInstances"); tb.inp(pil_real, "Geometry", pillars)
    inst_out = tb.switch(I("Collision Only"), tb.switch(I("Realize Instances"), inst, realized.outputs[0], "GEOMETRY"), pil_real.outputs[0], "GEOMETRY")
    tb.link(tb.join(smooth.outputs[0], inst_out), go.inputs[0])
    # menu defaults can only be set once the socket is linked to its Menu Switch
    for pname, rows in INPUTS:
        for row in rows:
            if row[1] == "NodeSocketMenu":
                item = next(i for i in g.interface.items_tree if getattr(i, "name", "") == row[0])
                try: item.default_value = row[2]
                except Exception as e: print("menu default", row[0], e)
    return g
