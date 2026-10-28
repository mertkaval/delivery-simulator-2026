"""MRS_Road v3: the Geometry Nodes road group (one modifier on a curve object).

v3 builds every surface strip as an analytic sweep: a grid whose vertices sample the rail (Sample
Curve: position, tangent, tilted normal) at their own station and place themselves at
P = C(along) + N * lateral(along) + U * height(lateral, along). Because the lateral position is a
function of `along`, the cross-section can change along the road: lane-count transitions with a
taper, ramps at crossings, and per-station attributes for the shaders.

Panels: Output, Terrain, Profile (lanes, transition, shoulders, bus lane, parking, median, curbs,
sidewalks, planting strip, crown, superelevation), Cycleway (per side: None / Painted / Buffered /
Protected / Two-Way, widths, buffer, separator, symbols), Markings, Structure, Roadside, Scatter,
Materials, Junction (trims, clears, height locks, ramps - set by the junction builder).

Named frames inside: Road_Profile, Lane_Transitions, Road_Surface, Cycleway, Sidewalk_Curb,
Pedestrian_Ramps, Structure, Lane_Markings, Roadside, Landscape_Scatter, Road_Surface_Masks.

Attributes on the mesh: `lat`, `along` (m), `u` (0..1 across a strip), `half_l`, `half_r` (asphalt
half widths at the station), `side` (normal vector), `upv`, `drain` (0..1 gutter nearness), `kind`
(0 asphalt 1 marking 2 concrete 3 structure 4 embankment 5 bike 6 paving 7 tactile 8 crossing 9 bus),
`UVMap` = (lat, along).
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
        ("Driving Side", "NodeSocketMenu", "Right", None, None, "Right-hand or left-hand traffic (which side the forward lanes use)"),
        ("Lanes Forward", "NodeSocketInt", 1, 0, 6, "Lanes in the curve direction (0 = one-way against the curve)"),
        ("Lanes Backward", "NodeSocketInt", 1, 0, 6, "Lanes against the curve direction (0 = one-way)"),
        ("Lane Width", "NodeSocketFloat", 3.2, 2.0, 6.0, "Width of one lane (m)"),
        ("Transition", "NodeSocketBool", False, None, None, "Lane counts change along the road (taper section)"),
        ("Lanes Forward End", "NodeSocketInt", 2, 0, 6, "Forward lanes after the transition"),
        ("Lanes Backward End", "NodeSocketInt", 1, 0, 6, "Backward lanes after the transition"),
        ("Transition Start", "NodeSocketFloat", 40.0, 0.0, 2000.0, "Metres from the (trimmed) start where the taper begins"),
        ("Taper Length", "NodeSocketFloat", 30.0, 5.0, 200.0, "Length of the taper (m)"),
        ("Shoulder", "NodeSocketFloat", 0.0, 0.0, 3.0, "Paved shoulder each side (m)"),
        ("Bus Lane Forward", "NodeSocketBool", False, None, None, "Outer forward lane is a coloured bus lane"),
        ("Bus Lane Backward", "NodeSocketBool", False, None, None, "Outer backward lane is a coloured bus lane"),
        ("Parking Left", "NodeSocketFloat", 0.0, 0.0, 3.0, "Parallel parking width (0 = none)"),
        ("Parking Right", "NodeSocketFloat", 0.0, 0.0, 3.0, "Parallel parking width (0 = none)"),
        ("Median", "NodeSocketFloat", 0.0, 0.0, 8.0, "Raised median width (0 = none)"),
        ("Median Height", "NodeSocketFloat", 0.15, 0.0, 1.0, ""),
        ("Curb Width", "NodeSocketFloat", 0.25, 0.1, 0.6, "Curb stone width (m)"),
        ("Curb Height", "NodeSocketFloat", 0.15, 0.0, 0.4, "Curb / sidewalk height (m)"),
        ("Curb Bevel", "NodeSocketFloat", 0.04, 0.0, 0.2, "Chamfer on the curb edge (m)"),
        ("Sidewalk Left", "NodeSocketBool", True, None, None, ""), ("Sidewalk Right", "NodeSocketBool", True, None, None, ""),
        ("Sidewalk Width Left", "NodeSocketFloat", 2.0, 0.5, 8.0, "Total width incl. the planting strip"), ("Sidewalk Width Right", "NodeSocketFloat", 2.0, 0.5, 8.0, ""),
        ("Planting Strip Left", "NodeSocketFloat", 0.0, 0.0, 3.0, "Grass / furniture strip between curb and paving (m)"),
        ("Planting Strip Right", "NodeSocketFloat", 0.0, 0.0, 3.0, ""),
        ("Crown", "NodeSocketFloat", 2.0, 0.0, 6.0, "Cross-fall from the centre to the edges (%)"),
        ("Superelevation", "NodeSocketFloat", 4.0, 0.0, 12.0, "Maximum banking in bends (degrees, 0 = flat)"),
        ("Resolution", "NodeSocketFloat", 1.0, 0.2, 10.0, "Sampling step along the road (m)"),
    ]),
    ("Cycleway", [
        ("Bike Left", "NodeSocketMenu", "None", None, None, "None / Painted / Buffered / Protected / Two-Way"),
        ("Bike Right", "NodeSocketMenu", "None", None, None, ""),
        ("Bike Width", "NodeSocketFloat", 1.6, 1.0, 3.0, "One direction (m); Two-Way uses twice"),
        ("Bike Buffer", "NodeSocketFloat", 0.5, 0.2, 1.5, "Painted buffer / separator strip width (m)"),
        ("Separator", "NodeSocketMenu", "Curb", None, None, "Protected: Curb / Posts / Planters"),
        ("Separator Spacing", "NodeSocketFloat", 3.0, 1.0, 12.0, "Posts / planters spacing (m)"),
        ("Bike Symbol Spacing", "NodeSocketFloat", 15.0, 4.0, 60.0, "Bicycle symbols + direction arrows (m)"),
        ("Bike Setback", "NodeSocketFloat", 4.0, 0.0, 20.0, "Symbols kept this far from trimmed ends (m)"),
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
        ("Markings Collection", "NodeSocketCollection", None, None, None, "Arrow / tick / symbol meshes (MRS_Markings)"),
    ]),
    ("Structure", [
        ("Mode", "NodeSocketMenu", "Ground", None, None, "Ground: on the terrain. Elevated: deck on pillars"),
        ("Deck Thickness", "NodeSocketFloat", 1.2, 0.3, 4.0, ""),
        ("Pillar Spacing", "NodeSocketFloat", 24.0, 4.0, 120.0, ""),
        ("Pillars", "NodeSocketCollection", None, None, None, "Pillar meshes, 1 m tall, scaled to the ground"),
        ("Barrier Left", "NodeSocketMenu", "None", None, None, ""), ("Barrier Right", "NodeSocketMenu", "None", None, None, ""),
        ("Barriers", "NodeSocketCollection", None, None, None, "2 m barrier segments"),
    ]),
    ("Roadside", [
        ("Props", "NodeSocketCollection", None, None, None, "Random roadside props (the rule-based placer handles furniture)"),
        ("Prop Spacing", "NodeSocketFloat", 28.0, 2.0, 200.0, ""), ("Prop Offset", "NodeSocketFloat", 0.5, 0.0, 10.0, "Lateral offset behind the curb (m)"),
        ("Prop Side", "NodeSocketMenu", "None", None, None, ""), ("Prop Seed", "NodeSocketInt", 0, 0, 10000, ""),
        ("Streetlights", "NodeSocketCollection", None, None, None, ""),
        ("Light Spacing", "NodeSocketFloat", 30.0, 5.0, 200.0, ""), ("Light Side", "NodeSocketMenu", "None", None, None, ""),
        ("Trees", "NodeSocketCollection", None, None, None, ""),
        ("Tree Spacing", "NodeSocketFloat", 12.0, 2.0, 100.0, ""), ("Tree Side", "NodeSocketMenu", "None", None, None, ""),
        ("Tree Offset", "NodeSocketFloat", 1.0, 0.0, 10.0, "Beyond the sidewalk edge (m); ignored when a planting strip exists"),
        ("Manholes", "NodeSocketCollection", None, None, None, ""), ("Manhole Spacing", "NodeSocketFloat", 45.0, 5.0, 300.0, ""),
        ("Drains", "NodeSocketCollection", None, None, None, "Gully gratings at the curb"), ("Drain Spacing", "NodeSocketFloat", 25.0, 5.0, 200.0, ""),
    ]),
    ("Scatter", [
        ("Scatter", "NodeSocketCollection", None, None, None, "Grass clumps / rocks on the embankments and planting strips"),
        ("Scatter Density", "NodeSocketFloat", 0.4, 0.0, 10.0, "Per square metre"),
        ("Scatter Seed", "NodeSocketInt", 0, 0, 10000, ""),
    ]),
    ("Materials", [
        ("Asphalt Material", "NodeSocketMaterial", None, None, None, ""), ("Marking Material", "NodeSocketMaterial", None, None, None, ""),
        ("Concrete Material", "NodeSocketMaterial", None, None, None, "Curbs, median, edges"), ("Paving Material", "NodeSocketMaterial", None, None, None, "Sidewalk slabs"),
        ("Tactile Material", "NodeSocketMaterial", None, None, None, "Ramps at crossings"), ("Cycleway Material", "NodeSocketMaterial", None, None, None, ""),
        ("Bus Lane Material", "NodeSocketMaterial", None, None, None, ""), ("Structure Material", "NodeSocketMaterial", None, None, None, ""),
        ("Embankment Material", "NodeSocketMaterial", None, None, None, "Also the planting strips"),
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
        ("Ramp Start", "NodeSocketBool", False, None, None, "Curb ramp + tactile paving at the start crossing"),
        ("Ramp End", "NodeSocketBool", False, None, None, "Curb ramp + tactile paving at the end crossing"),
        ("Ramp Offset", "NodeSocketFloat", 0.6, 0.0, 10.0, "Crossing starts this far from the trimmed end (m)"),
        ("Ramp Width", "NodeSocketFloat", 2.5, 1.0, 6.0, "Crossing width along the road (m)"),
    ]),
]
KIND = dict(asphalt=0, marking=1, concrete=2, structure=3, embankment=4, bike=5, paving=6, tactile=7, crossing=8, bus=9)
BARRIERS = ["None", "Guardrail", "Jersey", "Parapet", "Railing", "Hedge", "Fence"]
SIDES = ["None", "Left", "Right", "Both", "Alternate"]
BIKE = ["None", "Painted", "Buffered", "Protected", "Two-Way"]


def _coll_index(coll_name, obj_name):
    """Collection Info lists children sorted by object name: the pick index of `obj_name` in the
    collection as it exists at build time (-1 when missing)."""
    col = bpy.data.collections.get(coll_name)
    names = sorted(o.name for o in col.objects) if col else []
    return names.index(obj_name) if obj_name in names else -1


def build_profile_group():
    """`Road_Profile`: the cross-section boundaries at a station as functions of the lane counts (with the
    taper transition), cycleway layout, parking, median, curbs, sidewalks and planting strips."""
    g = new_tree("Road_Profile")
    spec = [("Along", "NodeSocketFloat", 0.0), ("Lanes Forward", "NodeSocketInt", 1), ("Lanes Backward", "NodeSocketInt", 1), ("Lane Width", "NodeSocketFloat", 3.2),
            ("Transition", "NodeSocketBool", False), ("Lanes Forward End", "NodeSocketInt", 1), ("Lanes Backward End", "NodeSocketInt", 1), ("Transition Start", "NodeSocketFloat", 0.0),
            ("Taper Length", "NodeSocketFloat", 30.0), ("Shoulder", "NodeSocketFloat", 0.0), ("Right Hand", "NodeSocketBool", True), ("Bike Left", "NodeSocketInt", 0), ("Bike Right", "NodeSocketInt", 0),
            ("Bike Width", "NodeSocketFloat", 1.6), ("Bike Buffer", "NodeSocketFloat", 0.5), ("Parking Left", "NodeSocketFloat", 0.0), ("Parking Right", "NodeSocketFloat", 0.0),
            ("Median", "NodeSocketFloat", 0.0), ("Curb Width", "NodeSocketFloat", 0.25), ("Sidewalk Left", "NodeSocketBool", True), ("Sidewalk Right", "NodeSocketBool", True),
            ("Sidewalk Width Left", "NodeSocketFloat", 2.0), ("Sidewalk Width Right", "NodeSocketFloat", 2.0), ("Planting Strip Left", "NodeSocketFloat", 0.0),
            ("Planting Strip Right", "NodeSocketFloat", 0.0), ("Crown", "NodeSocketFloat", 2.0)]
    for nm, st, d in spec: sock(g, nm, "INPUT", st, d)
    keys = ["lanes_r", "lanes_l", "carr_r", "carr_l", "sh_r", "sh_l", "buf0_r", "buf0_l", "bike0_r", "bike0_l", "bike1_r", "bike1_l",
            "park0_r", "park0_l", "park1_r", "park1_l", "half_r", "half_l", "curb_r", "curb_l", "plant_r", "plant_l", "sw_r", "sw_l", "half_max", "crown"]
    for k in keys: sock(g, k, "OUTPUT", "NodeSocketFloat")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = lambda k: gi.outputs[k]
    def smooth01(v): return tb.math("MULTIPLY", v, tb.math("MULTIPLY", v, tb.math("SUBTRACT", 3.0, tb.math("MULTIPLY", 2.0, v))))
    lw = I("Lane Width"); med_half = tb.math("MULTIPLY", I("Median"), 0.5)
    t = smooth01(tb.map_range(tb.math("SUBTRACT", I("Along"), I("Transition Start")), 0.0, I("Taper Length"), 0.0, 1.0))
    def lanes(start, end):
        n = tb.math("ADD", start, tb.math("MULTIPLY", tb.math("SUBTRACT", end, start), t))
        return tb.switch(I("Transition"), start, n, "FLOAT")
    lf = lanes(I("Lanes Forward"), I("Lanes Forward End")); lb = lanes(I("Lanes Backward"), I("Lanes Backward End"))
    w = {}
    w["lanes_r"] = tb.switch(I("Right Hand"), lb, lf, "FLOAT"); w["lanes_l"] = tb.switch(I("Right Hand"), lf, lb, "FLOAT")
    for s in ("r", "l"):
        idx = I("Bike Right" if s == "r" else "Bike Left")
        on = tb.compare("GREATER_THAN", idx, 0, "INT"); two = tb.compare("EQUAL", idx, 4, "INT")
        bw = tb.switch(on, 0.0, tb.switch(two, I("Bike Width"), tb.math("MULTIPLY", I("Bike Width"), 2.0), "FLOAT"), "FLOAT")
        buf = tb.switch(tb.compare("GREATER_THAN", idx, 1, "INT"), 0.0, I("Bike Buffer"), "FLOAT")
        prot = tb.compare("GREATER_THAN", idx, 2, "INT")
        pk = I("Parking Right" if s == "r" else "Parking Left")
        w["carr_" + s] = tb.math("ADD", med_half, tb.math("MULTIPLY", w["lanes_" + s], lw))
        w["sh_" + s] = tb.math("ADD", w["carr_" + s], I("Shoulder"))
        sh = w["sh_" + s]
        w["buf0_" + s] = tb.switch(prot, sh, tb.math("ADD", sh, pk), "FLOAT")
        w["bike0_" + s] = tb.math("ADD", w["buf0_" + s], buf); w["bike1_" + s] = tb.math("ADD", w["bike0_" + s], bw)
        w["park0_" + s] = tb.switch(prot, w["bike1_" + s], sh, "FLOAT"); w["park1_" + s] = tb.math("ADD", w["park0_" + s], pk)
        w["half_" + s] = tb.switch(prot, w["park1_" + s], w["bike1_" + s], "FLOAT")
        w["curb_" + s] = tb.math("ADD", w["half_" + s], I("Curb Width"))
        swon = I("Sidewalk Right" if s == "r" else "Sidewalk Left"); sww = I("Sidewalk Width Right" if s == "r" else "Sidewalk Width Left")
        pstrip = I("Planting Strip Right" if s == "r" else "Planting Strip Left")
        w["plant_" + s] = tb.math("ADD", w["curb_" + s], tb.switch(swon, 0.0, tb.math("MINIMUM", pstrip, tb.math("SUBTRACT", sww, 1.0)), "FLOAT"))
        w["sw_" + s] = tb.math("ADD", w["curb_" + s], tb.switch(swon, 0.0, sww, "FLOAT"))
    w["half_max"] = tb.math("MAXIMUM", w["half_l"], w["half_r"])
    w["crown"] = tb.math("MULTIPLY", tb.math("MULTIPLY", I("Crown"), 0.01), w["half_max"])
    for k in keys: tb.link(w[k], go.inputs[k])
    return g


def build_sweep_group():
    """`Road_Sweep`: one strip of the road. A grid of Stations x Samples vertices; each vertex samples the
    rail at its station and places itself at C + N * lateral + U * height. The lateral / height inputs are
    FIELDS evaluated on the grid, where `u`, `v`, `along` are already stored (so callers express them with
    Named Attribute nodes). Orient: 0 up, 1 down, 2 outward, 3 inward (face normals)."""
    g = new_tree("Road_Sweep")
    sock(g, "Rail", "INPUT", "NodeSocketGeometry")
    for nm, st, d in (("Stations", "NodeSocketInt", 10), ("Samples", "NodeSocketInt", 2), ("Length", "NodeSocketFloat", 10.0), ("X0", "NodeSocketFloat", 0.0), ("X1", "NodeSocketFloat", 1.0),
                      ("Z0", "NodeSocketFloat", 0.0), ("Z1", "NodeSocketFloat", 0.0), ("Z Extra", "NodeSocketFloat", 0.0), ("Z Scale", "NodeSocketFloat", 1.0),
                      ("Kind", "NodeSocketFloat", 0.0), ("Orient", "NodeSocketInt", 0), ("Half L", "NodeSocketFloat", 0.0), ("Half R", "NodeSocketFloat", 0.0),
                      ("Alt Selection", "NodeSocketBool", False), ("Alt Kind", "NodeSocketFloat", 0.0)):
        sock(g, nm, "INPUT", st, d)
    sock(g, "Material", "INPUT", "NodeSocketMaterial"); sock(g, "Alt Material", "INPUT", "NodeSocketMaterial")
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = lambda k: gi.outputs[k]
    grid = tb.n("GeometryNodeMeshGrid"); tb.inp(grid, "Size X", 1.0); tb.inp(grid, "Size Y", 1.0); tb.inp(grid, "Vertices X", I("Samples")); tb.inp(grid, "Vertices Y", I("Stations"))
    gp = tb.n("GeometryNodeInputPosition").outputs[0]
    geo = tb.store(grid.outputs[0], "u", tb.math("ADD", tb.separate(gp)[0], 0.5))
    geo = tb.store(geo, "v", tb.math("ADD", tb.separate(gp)[1], 0.5))
    geo = tb.store(geo, "along", tb.math("MULTIPLY", tb.named("v"), I("Length")))
    u = tb.named("u"); along = tb.named("along")
    lat = tb.math("ADD", I("X0"), tb.math("MULTIPLY", u, tb.math("SUBTRACT", I("X1"), I("X0"))))
    geo = tb.store(geo, "lat", lat)
    z = tb.math("MULTIPLY", tb.math("ADD", tb.math("ADD", I("Z0"), tb.math("MULTIPLY", u, tb.math("SUBTRACT", I("Z1"), I("Z0")))), I("Z Extra")), I("Z Scale"))
    sc_ = tb.n("GeometryNodeSampleCurve", mode="LENGTH", data_type="FLOAT"); sc_.use_all_curves = True
    tb.inp(sc_, "Curves", I("Rail")); tb.inp(sc_, "Length", along)
    N = sc_.outputs["Normal"]; Tn = sc_.outputs["Tangent"]
    U = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", N, Tn))
    P = tb.vmath("ADD", sc_.outputs["Position"], tb.vmath("ADD", tb.vmath("SCALE", N, scale=tb.named("lat")), tb.vmath("SCALE", U, scale=z)))
    setp = tb.n("GeometryNodeSetPosition"); tb.inp(setp, "Geometry", geo); tb.inp(setp, "Position", P)
    geo = tb.store(setp.outputs[0], "side", N, "FLOAT_VECTOR"); geo = tb.store(geo, "upv", U, "FLOAT_VECTOR")
    geo = tb.store(geo, "half_l", I("Half L")); geo = tb.store(geo, "half_r", I("Half R"))
    nrm = tb.n("GeometryNodeInputNormal").outputs[0]
    upa = tb.named("upv", "FLOAT_VECTOR"); sidea = tb.named("side", "FLOAT_VECTOR")
    outward = tb.vmath("SCALE", sidea, scale=tb.math("SIGN", tb.named("lat")))
    expected = tb.switch(tb.compare("EQUAL", I("Orient"), 0, "INT"), tb.switch(tb.compare("EQUAL", I("Orient"), 1, "INT"), tb.switch(tb.compare("EQUAL", I("Orient"), 2, "INT"), tb.vmath("SCALE", outward, scale=-1.0), outward, "VECTOR"), tb.vmath("SCALE", upa, scale=-1.0), "VECTOR"), upa, "VECTOR")
    ff = tb.n("GeometryNodeFlipFaces"); tb.inp(ff, "Mesh", geo); tb.inp(ff, "Selection", tb.compare("LESS_THAN", tb.vmath("DOT_PRODUCT", nrm, expected), 0.0))
    sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", ff.outputs[0]); tb.inp(sm, "Material", I("Material"))
    sm2 = tb.n("GeometryNodeSetMaterial"); tb.inp(sm2, "Geometry", sm.outputs[0]); tb.inp(sm2, "Selection", I("Alt Selection")); tb.inp(sm2, "Material", I("Alt Material"))
    out = tb.store(sm2.outputs[0], "kind", tb.switch(I("Alt Selection"), I("Kind"), I("Alt Kind"), "FLOAT"), "FLOAT", "FACE")
    tb.link(out, go.inputs[0])
    return g


def build_road_group():
    build_profile_group(); build_sweep_group()
    g = new_tree(MRS + "Road")
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    add_inputs(g, INPUTS)
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    tb = T(g)
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    I = lambda k: gi.outputs[k]
    neg = lambda s: tb.math("MULTIPLY", s, -1.0)
    R = lambda node: next((o for o in node.outputs if o.enabled), node.outputs[0])
    up = (0.0, 0.0, 1.0)
    def smooth01(v): return tb.math("MULTIPLY", v, tb.math("MULTIPLY", v, tb.math("SUBTRACT", 3.0, tb.math("MULTIPLY", 2.0, v))))

    # ---------------------------------------------------------------- quality / global switches
    tb.frame_("Output: quality by viewport / render, global menus")
    q_view = tb.menu_switch(I("Viewport Quality"), [("Preview", 2.5), ("Final", 1.0)], "FLOAT", "viewport quality")
    q_rend = tb.menu_switch(I("Render Quality"), [("Preview", 2.5), ("Final", 1.0)], "FLOAT", "render quality")
    is_vp = tb.n("GeometryNodeIsViewport").outputs[0]
    step = tb.math("MULTIPLY", I("Resolution"), tb.switch(is_vp, q_rend, q_view, "FLOAT"))
    elevated = tb.menu_switch(I("Mode"), [("Ground", False), ("Elevated", True)], "BOOLEAN", "mode")
    grounded = tb.boolean("NOT", elevated)
    rht = tb.menu_switch(I("Driving Side"), [("Right", True), ("Left", False)], "BOOLEAN", "driving side")
    bike_l = tb.menu_switch(I("Bike Left"), [(nm, i) for i, nm in enumerate(BIKE)], "INT", "bike left")
    bike_r = tb.menu_switch(I("Bike Right"), [(nm, i) for i, nm in enumerate(BIKE)], "INT", "bike right")
    sep_kind = tb.menu_switch(I("Separator"), [("Curb", 0), ("Posts", 1), ("Planters", 2)], "INT", "separator")
    c_idx = tb.menu_switch(I("Centre Line"), [("None", 0), ("Solid", 1), ("Dashed", 2), ("Double", 3)], "INT", "centre line")

    # ---------------------------------------------------------------- Road_Profile: the cross-section as functions of `along`
    tb.frame_("Road_Profile + Lane_Transitions: cross-section boundaries as functions of the station")
    lw = I("Lane Width"); med_half = tb.math("MULTIPLY", I("Median"), 0.5)
    H = I("Curb Height"); bev = tb.math("MINIMUM", I("Curb Bevel"), tb.math("MULTIPLY", H, 0.9))
    def bike_flags(idx):
        on = tb.compare("GREATER_THAN", idx, 0, "INT")
        buf = tb.switch(tb.compare("GREATER_THAN", idx, 1, "INT"), 0.0, I("Bike Buffer"), "FLOAT")
        return buf, None, tb.compare("GREATER_THAN", idx, 2, "INT"), on
    bl_buf, bl_w, bl_prot, bl_on = bike_flags(bike_l); br_buf, br_w, br_prot, br_on = bike_flags(bike_r)
    PROFILE_KEYS = ["lanes_r", "lanes_l", "carr_r", "carr_l", "sh_r", "sh_l", "buf0_r", "buf0_l", "bike0_r", "bike0_l", "bike1_r", "bike1_l",
                    "park0_r", "park0_l", "park1_r", "park1_l", "half_r", "half_l", "curb_r", "curb_l", "plant_r", "plant_l", "sw_r", "sw_l", "half_max", "crown"]
    profile_inputs = {"Lanes Forward": I("Lanes Forward"), "Lanes Backward": I("Lanes Backward"), "Lane Width": lw, "Transition": I("Transition"),
                      "Lanes Forward End": I("Lanes Forward End"), "Lanes Backward End": I("Lanes Backward End"), "Transition Start": I("Transition Start"),
                      "Taper Length": I("Taper Length"), "Shoulder": I("Shoulder"), "Right Hand": rht, "Bike Left": bike_l, "Bike Right": bike_r,
                      "Bike Width": I("Bike Width"), "Bike Buffer": I("Bike Buffer"), "Parking Left": I("Parking Left"), "Parking Right": I("Parking Right"),
                      "Median": I("Median"), "Curb Width": I("Curb Width"), "Sidewalk Left": I("Sidewalk Left"), "Sidewalk Right": I("Sidewalk Right"),
                      "Sidewalk Width Left": I("Sidewalk Width Left"), "Sidewalk Width Right": I("Sidewalk Width Right"),
                      "Planting Strip Left": I("Planting Strip Left"), "Planting Strip Right": I("Planting Strip Right"), "Crown": I("Crown")}

    def W(along):
        """Every lateral boundary of the cross-section at station `along` (right = +lat): one Road_Profile group node."""
        node = tb.group("Road_Profile", Along=along, **profile_inputs)
        return {k: node.outputs[k] for k in PROFILE_KEYS}
    ZERO = tb.math("MULTIPLY", 0.0, 1.0)

    # ---------------------------------------------------------------- terrain geometry
    tb.frame_("Terrain: object + collection, relative space")
    t_obj = tb.n("GeometryNodeObjectInfo", transform_space="RELATIVE"); tb.inp(t_obj, "Object", I("Terrain"))
    t_col = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(t_col, "Collection", I("Terrain Collection"))
    t_real = tb.n("GeometryNodeRealizeInstances"); tb.inp(t_real, "Geometry", tb.join(t_obj.outputs["Geometry"], t_col.outputs[0]))
    terrain = t_real.outputs[0]

    def ray_down(pos):
        rc = tb.n("GeometryNodeRaycast", data_type="FLOAT")
        tb.inp(rc, "Target Geometry", terrain); tb.inp(rc, "Source Position", tb.vmath("ADD", pos, (0.0, 0.0, 500.0)))
        tb.inp(rc, "Ray Direction", (0.0, 0.0, -1.0)); tb.inp(rc, "Ray Length", 2000.0)
        return rc.outputs["Is Hit"], tb.separate(rc.outputs["Hit Position"])[2]

    # ---------------------------------------------------------------- the rail
    tb.frame_("Rail: trim, resample, conform to terrain, smooth, junction height locks, bank")
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
    sp0 = tb.n("GeometryNodeSplineParameter"); rlen0 = tb.n("GeometryNodeCurveLength"); tb.inp(rlen0, "Curve", res.outputs[0])
    w_s = smooth01(tb.map_range(sp0.outputs["Length"], 0.0, I("Lock Length"), 1.0, 0.0))
    w_e = smooth01(tb.map_range(tb.math("SUBTRACT", rlen0.outputs[0], sp0.outputs["Length"]), 0.0, I("Lock Length"), 1.0, 0.0))
    z1 = tb.switch(I("Lock Start"), blur_z.outputs[0], tb.math("ADD", blur_z.outputs[0], tb.math("MULTIPLY", tb.math("SUBTRACT", I("Lock Start Z"), blur_z.outputs[0]), w_s)), "FLOAT")
    z2 = tb.switch(I("Lock End"), z1, tb.math("ADD", z1, tb.math("MULTIPLY", tb.math("SUBTRACT", I("Lock End Z"), z1), w_e)), "FLOAT")
    conformed = tb.n("GeometryNodeSetPosition"); tb.inp(conformed, "Geometry", res.outputs[0]); tb.inp(conformed, "Position", tb.combine(px, py, z2))
    tang = tb.n("GeometryNodeInputTangent").outputs[0]
    idx = tb.n("GeometryNodeInputIndex").outputs[0]
    dsize = tb.n("GeometryNodeAttributeDomainSize", component="CURVE"); tb.inp(dsize, "Geometry", conformed.outputs[0])
    nxt = tb.n("GeometryNodeSampleIndex", data_type="FLOAT_VECTOR", domain="POINT"); tb.inp(nxt, "Geometry", conformed.outputs[0]); tb.inp(nxt, "Value", tang)
    tb.inp(nxt, "Index", tb.math("MINIMUM", tb.math("ADD", idx, 1.0), tb.math("SUBTRACT", dsize.outputs["Point Count"], 1.0)))
    ang = tb.math("ARCTAN2", tb.separate(tb.vmath("CROSS_PRODUCT", tang, nxt.outputs[0]))[2], tb.vmath("DOT_PRODUCT", tang, nxt.outputs[0]))
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
    rail_len = tb.n("GeometryNodeCurveLength"); tb.inp(rail_len, "Curve", rail)
    L = rail_len.outputs[0]
    n_stations = tb.math("ADD", tb.math("FLOOR", tb.math("DIVIDE", L, step)), 2.0)

    # ---------------------------------------------------------------- Road_Surface: analytic grid sweeps
    tb.frame_("Road_Surface: grid sweep - every vertex samples the rail at its station and places itself")
    ORIENT = {"up": 0, "down": 1, "out": 2, "in": 3}
    def sweep(x_fn, material, kind, label, orient="up", samples=2, zf=None, zscale_fn=None, mat_sel=None):
        """A strip (one Road_Sweep group node). x_fn(along, w) -> (x0, x1, z0, z1) as fields of the `along`
        attribute; zf(lat, along, w) -> extra height; zscale_fn(along) -> height scale; mat_sel(along, lat) ->
        (selection, material, kind) to override faces."""
        along = tb.named("along"); w = W(along)
        x0, x1, z0, z1 = x_fn(along, w)
        lat = tb.math("ADD", x0, tb.math("MULTIPLY", tb.named("u"), tb.math("SUBTRACT", x1, x0)))
        kw = dict(Rail=rail, Stations=n_stations, Samples=samples, Length=L, X0=x0, X1=x1, Z0=z0, Z1=z1, Kind=float(KIND[kind]), Orient=ORIENT[orient],
                  Material=material)
        kw["Half L"] = w["half_l"]; kw["Half R"] = w["half_r"]
        if zf is not None: kw["Z Extra"] = zf(lat, along, w)
        if zscale_fn is not None: kw["Z Scale"] = zscale_fn(along)
        if mat_sel is not None:
            sel, mat2, kind2 = mat_sel(along, lat)
            kw["Alt Selection"] = sel; kw["Alt Material"] = mat2; kw["Alt Kind"] = float(KIND[kind2])
        else:
            kw["Alt Material"] = material
        node = tb.group("Road_Sweep", **kw); node.label = label
        return node.outputs[0]

    def camber(lat, along, w):
        half = tb.switch(tb.compare("LESS_THAN", lat, 0.0), w["half_r"], w["half_l"], "FLOAT")
        return tb.math("MULTIPLY", w["crown"], tb.math("SUBTRACT", 1.0, tb.math("POWER", tb.math("DIVIDE", tb.math("ABSOLUTE", lat), tb.math("MAXIMUM", half, 0.01)), 2.0)))

    def ramp_factor(along):
        """Sidewalk height factor: dips to 4 % over the crossing span with 1 m flanks at ramped ends."""
        def dip(d):
            centre = tb.math("ADD", I("Ramp Offset"), tb.math("MULTIPLY", I("Ramp Width"), 0.5)); hw = tb.math("MULTIPLY", I("Ramp Width"), 0.5)
            return smooth01(tb.map_range(tb.math("ABSOLUTE", tb.math("SUBTRACT", d, centre)), hw, tb.math("ADD", hw, 1.0), 1.0, 0.0))
        f = tb.math("MAXIMUM", tb.switch(I("Ramp Start"), 0.0, dip(along), "FLOAT"), tb.switch(I("Ramp End"), 0.0, dip(tb.math("SUBTRACT", L, along)), "FLOAT"))
        return tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", f, 0.96))
    def tactile_sel(along, lat):
        return tb.compare("LESS_THAN", ramp_factor(along), 0.5), I("Tactile Material"), "tactile"

    surf = []
    surf.append(sweep(lambda a, w: (neg(w["half_l"]), w["half_r"], 0.0, 0.0), I("Asphalt Material"), "asphalt", "asphalt", samples=11, zf=camber))
    tb.frame_("Cycleway + bus lanes: coloured surfacing on the asphalt")
    for s, sgn, on in (("r", 1.0, br_on), ("l", -1.0, bl_on)):
        geo = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["bike0_" + s], sgn), tb.math("MULTIPLY", w["bike1_" + s], sgn), 0.003, 0.003), I("Cycleway Material"), "bike", "cycleway " + s, samples=3, zf=camber)
        surf.append(tb.switch(on, tb.empty(), geo, "GEOMETRY"))
    for s, sgn, on in (("r", 1.0, tb.switch(rht, I("Bus Lane Backward"), I("Bus Lane Forward"), "BOOLEAN")), ("l", -1.0, tb.switch(rht, I("Bus Lane Forward"), I("Bus Lane Backward"), "BOOLEAN"))):
        geo = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", tb.math("SUBTRACT", w["carr_" + s], lw), sgn), tb.math("MULTIPLY", w["carr_" + s], sgn), 0.003, 0.003), I("Bus Lane Material"), "bus", "bus lane " + s, samples=3, zf=camber)
        surf.append(tb.switch(tb.boolean("AND", on, tb.compare("GREATER_THAN", W(ZERO)["lanes_" + s], 0.5)), tb.empty(), geo, "GEOMETRY"))
    tb.frame_("Sidewalk_Curb + Pedestrian_Ramps: curb face / bevel / top, planting strip, paving, edge; heights scaled by the ramps")
    rf = ramp_factor
    for s, sgn, on in (("r", 1.0, I("Sidewalk Right")), ("l", -1.0, I("Sidewalk Left"))):
        surf.append(sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["half_" + s], sgn), tb.math("MULTIPLY", w["half_" + s], sgn), 0.0, tb.math("SUBTRACT", H, bev)), I("Concrete Material"), "concrete", "curb face " + s, orient="in", zscale_fn=rf))
        surf.append(sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["half_" + s], sgn), tb.math("MULTIPLY", tb.math("ADD", w["half_" + s], bev), sgn), tb.math("SUBTRACT", H, bev), H), I("Concrete Material"), "concrete", "curb bevel " + s, zscale_fn=rf))
        surf.append(sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", tb.math("ADD", w["half_" + s], bev), sgn), tb.math("MULTIPLY", w["curb_" + s], sgn), H, H), I("Concrete Material"), "concrete", "curb top " + s, zscale_fn=rf))
        plant = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["curb_" + s], sgn), tb.math("MULTIPLY", w["plant_" + s], sgn), H, H), I("Embankment Material"), "embankment", "planting strip " + s, zscale_fn=rf)
        slab = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["plant_" + s], sgn), tb.math("MULTIPLY", w["sw_" + s], sgn), H, H), I("Paving Material"), "paving", "sidewalk " + s, samples=3, zscale_fn=rf, mat_sel=tactile_sel)
        edge = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["sw_" + s], sgn), tb.math("MULTIPLY", w["sw_" + s], sgn), H, 0.0), I("Concrete Material"), "concrete", "sidewalk edge " + s, orient="out", zscale_fn=rf)
        pstrip = I("Planting Strip Right") if s == "r" else I("Planting Strip Left")
        surf.append(tb.switch(on, tb.empty(), tb.join(tb.switch(tb.compare("GREATER_THAN", pstrip, 0.05), tb.empty(), plant, "GEOMETRY"), slab, edge), "GEOMETRY"))
        surf.append(tb.switch(on, sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["curb_" + s], sgn), tb.math("MULTIPLY", w["curb_" + s], sgn), H, 0.0), I("Concrete Material"), "concrete", "curb back " + s, orient="out", zscale_fn=rf), tb.empty(), "GEOMETRY"))
        sep = tb.join(sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["buf0_" + s], sgn), tb.math("MULTIPLY", w["buf0_" + s], sgn), 0.0, 0.1), I("Concrete Material"), "concrete", "separator face " + s, orient="in"),
                      sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["buf0_" + s], sgn), tb.math("MULTIPLY", w["bike0_" + s], sgn), 0.1, 0.1), I("Concrete Material"), "concrete", "separator top " + s),
                      sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["bike0_" + s], sgn), tb.math("MULTIPLY", w["bike0_" + s], sgn), 0.1, 0.0), I("Concrete Material"), "concrete", "separator back " + s, orient="out"))
        prot = br_prot if s == "r" else bl_prot
        surf.append(tb.switch(tb.boolean("AND", prot, tb.compare("EQUAL", sep_kind, 0, "INT")), tb.empty(), sep, "GEOMETRY"))
    MH = I("Median Height")
    med = tb.join(sweep(lambda a, w: (neg(med_half), neg(med_half), w["crown"], tb.math("ADD", w["crown"], MH)), I("Concrete Material"), "concrete", "median face L", orient="in"),
                  sweep(lambda a, w: (neg(med_half), med_half, tb.math("ADD", w["crown"], MH), tb.math("ADD", w["crown"], MH)), I("Concrete Material"), "concrete", "median top"),
                  sweep(lambda a, w: (med_half, med_half, tb.math("ADD", w["crown"], MH), w["crown"]), I("Concrete Material"), "concrete", "median face R", orient="in"))
    has_median = tb.compare("GREATER_THAN", I("Median"), 0.05)
    surf.append(tb.switch(has_median, tb.empty(), med, "GEOMETRY"))

    # ---------------------------------------------------------------- Structure
    tb.frame_("Structure: deck under the road, pillars scaled to the terrain, barriers")
    DT = I("Deck Thickness")
    deck = tb.join(sweep(lambda a, w: (neg(w["sw_l"]), neg(w["sw_l"]), 0.0, neg(DT)), I("Structure Material"), "structure", "deck side L", orient="out"),
                   sweep(lambda a, w: (neg(w["sw_l"]), w["sw_r"], neg(DT), neg(DT)), I("Structure Material"), "structure", "deck bottom", orient="down"),
                   sweep(lambda a, w: (w["sw_r"], w["sw_r"], neg(DT), 0.0), I("Structure Material"), "structure", "deck side R", orient="out"))
    deck_geo = tb.switch(elevated, tb.empty(), deck, "GEOMETRY")

    def points_along(spacing, clear_s, clear_e):
        """Points along the rail every `spacing` m, clear of both ends; with `along`, `tangent`, `side`."""
        t2 = tb.n("GeometryNodeTrimCurve", mode="LENGTH"); tb.inp(t2, "Curve", rail)
        tb.inp(t2, "Start_001", clear_s); tb.inp(t2, "End_001", tb.math("SUBTRACT", L, clear_e))
        c2p = tb.n("GeometryNodeCurveToPoints", mode="LENGTH"); tb.inp(c2p, "Curve", t2.outputs[0]); tb.inp(c2p, "Length", spacing)
        side = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", c2p.outputs["Tangent"], up))
        pts = tb.store(c2p.outputs["Points"], "tangent", c2p.outputs["Tangent"], "FLOAT_VECTOR")
        return tb.store(pts, "side", side, "FLOAT_VECTOR")

    pil = points_along(I("Pillar Spacing"), tb.math("ADD", I("Clear Start"), 4.0), tb.math("ADD", I("Clear End"), 4.0))
    ppos = tb.n("GeometryNodeInputPosition").outputs[0]
    phit, phz = ray_down(ppos)
    pil_h0 = tb.math("MAXIMUM", tb.math("SUBTRACT", tb.math("SUBTRACT", tb.separate(ppos)[2], DT), tb.switch(phit, 0.0, phz, "FLOAT")), 0.1)
    pts0 = tb.store(pil, "pil_h", pil_h0); pil_h = tb.named("pil_h")
    pil_pts = tb.n("GeometryNodeSetPosition"); tb.inp(pil_pts, "Geometry", pts0); tb.inp(pil_pts, "Offset", tb.combine(0.0, 0.0, neg(tb.math("ADD", pil_h, DT))))
    pcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(pcoll, "Collection", I("Pillars")); tb.inp(pcoll, "Separate Children", True); tb.inp(pcoll, "Reset Children", True)
    palign = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(palign, "Vector", tb.named("tangent", "FLOAT_VECTOR"))
    piop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(piop, "Points", pil_pts.outputs[0]); tb.inp(piop, "Instance", pcoll.outputs[0]); tb.inp(piop, "Pick Instance", True)
    tb.inp(piop, "Rotation", palign.outputs[0]); tb.inp(piop, "Scale", tb.combine(tb.math("ADD", 1.0, tb.math("MULTIPLY", tb.math("ADD", I("Lanes Forward"), I("Lanes Backward")), 0.12)), 1.0, pil_h))
    pillars = tb.switch(elevated, tb.empty(), piop.outputs[0], "GEOMETRY")

    bcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(bcoll, "Collection", I("Barriers")); tb.inp(bcoll, "Separate Children", True); tb.inp(bcoll, "Reset Children", True)
    barriers = []
    for s, sgn, menu in (("r", 1.0, I("Barrier Right")), ("l", -1.0, I("Barrier Left"))):
        bidx = tb.menu_switch(menu, [(nm, -1 if nm == "None" else _coll_index(MRS + "Barriers", MRS + nm)) for nm in BARRIERS], "INT", "barrier")
        bp = points_along(2.0, I("Clear Start"), I("Clear End"))
        w = W(tb.named("along"))
        moved = tb.n("GeometryNodeSetPosition"); tb.inp(moved, "Geometry", bp)
        tb.inp(moved, "Offset", tb.vmath("ADD", tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=tb.math("MULTIPLY", tb.math("SUBTRACT", w["sw_" + s], 0.25), sgn)), tb.combine(0.0, 0.0, H)))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.vmath("SCALE", tb.named("tangent", "FLOAT_VECTOR"), scale=sgn))
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", moved.outputs[0]); tb.inp(io, "Instance", bcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", bidx); tb.inp(io, "Rotation", al.outputs[0])
        barriers.append(tb.switch(tb.compare("LESS_THAN", bidx, 0, "INT"), io.outputs[0], tb.empty(), "GEOMETRY"))

    # ---------------------------------------------------------------- embankments and cut walls
    tb.frame_("Terrain: embankment slopes to the raycast terrain height, walls in deep cuts")
    EW = I("Embankment Width"); soft = I("Embankment Softness")
    emb = []; walls = []
    for s, sgn in (("r", 1.0), ("l", -1.0)):
        geo = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["sw_" + s], sgn), tb.math("MULTIPLY", tb.math("ADD", w["sw_" + s], EW), sgn), 0.0, 0.0), I("Embankment Material"), "embankment", "embankment " + s, samples=7)
        vpos = tb.n("GeometryNodeInputPosition").outputs[0]
        vhit, vhz = ray_down(vpos)
        f = tb.named("u")
        f_mix = tb.map_range(soft, 0.0, 1.0, f, smooth01(f))
        vx, vy, vz = tb.separate(vpos)
        depth = tb.math("SUBTRACT", vhz, vz)
        wall_here = tb.boolean("AND", I("Retaining Wall"), tb.compare("GREATER_THAN", depth, I("Wall Threshold")))
        z_new = tb.math("SUBTRACT", tb.math("ADD", vz, tb.math("MULTIPLY", depth, f_mix)), tb.math("MULTIPLY", f, 0.12))
        set_ = tb.n("GeometryNodeSetPosition"); tb.inp(set_, "Geometry", geo); tb.inp(set_, "Selection", vhit); tb.inp(set_, "Position", tb.combine(vx, vy, z_new))
        del_ = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(del_, "Geometry", set_.outputs[0]); tb.inp(del_, "Selection", wall_here)
        emb.append(del_.outputs[0])
        # wall: a 1 m strip whose top row (u = 1) is raised to the terrain height
        wgeo = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", w["sw_" + s], sgn), tb.math("MULTIPLY", w["sw_" + s], sgn), 0.0, 1.0), I("Structure Material"), "structure", "retaining wall " + s, orient="in")
        wpos = tb.n("GeometryNodeInputPosition").outputs[0]
        whit, whz = ray_down(tb.vmath("ADD", wpos, tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=tb.math("MULTIPLY", 0.3, sgn))))
        wx, wy, wz = tb.separate(wpos)
        base = tb.math("SUBTRACT", wz, tb.named("u"))            # the road-edge height at this station
        wdepth = tb.math("SUBTRACT", whz, base)
        wset = tb.n("GeometryNodeSetPosition"); tb.inp(wset, "Geometry", wgeo); tb.inp(wset, "Selection", tb.boolean("AND", whit, tb.compare("GREATER_THAN", tb.named("u"), 0.5)))
        tb.inp(wset, "Position", tb.combine(wx, wy, tb.math("ADD", base, tb.math("MAXIMUM", wdepth, 0.0))))
        keep_wall = tb.boolean("AND", I("Retaining Wall"), tb.compare("GREATER_THAN", wdepth, I("Wall Threshold")))
        wdel = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(wdel, "Geometry", wset.outputs[0]); tb.inp(wdel, "Selection", tb.boolean("NOT", keep_wall))
        walls.append(wdel.outputs[0])
    emb_on = tb.boolean("AND", I("Embankment"), tb.boolean("AND", grounded, I("Conform")))
    emb_geo = tb.switch(emb_on, tb.empty(), tb.join(*emb, *walls), "GEOMETRY")

    # ---------------------------------------------------------------- Lane_Markings
    tb.frame_("Lane_Markings: thin sweeps at lateral functions of the station, dashes cut by 'along'")
    mw = I("Marking Width"); mw2 = tb.math("MULTIPLY", mw, 0.5)
    def marking(xc_fn, dashed, label, on_fn=None, zlift=0.004):
        geo = sweep(lambda a, w: (tb.math("SUBTRACT", xc_fn(a, w), mw2), tb.math("ADD", xc_fn(a, w), mw2), zlift, zlift), I("Marking Material"), "marking", label, zf=camber)
        sel = None
        if dashed is not None:
            period = tb.math("ADD", I("Dash Length"), I("Dash Gap"))
            sel = tb.boolean("AND", tb.compare("GREATER_THAN", tb.math("MODULO", tb.named("along"), period), I("Dash Length")), dashed)
        if on_fn is not None:
            off = tb.boolean("NOT", on_fn(tb.named("along"), W(tb.named("along"))))
            sel = off if sel is None else tb.boolean("OR", sel, off)
        if sel is None: return geo
        delete = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(delete, "Geometry", geo); tb.inp(delete, "Selection", sel)
        return delete.outputs[0]
    marks = []
    c_single = marking(lambda a, w: ZERO, tb.compare("EQUAL", c_idx, 2, "INT"), "centre line")
    dbl = tb.join(marking(lambda a, w: neg(tb.math("ADD", med_half, mw)), None, "double L"), marking(lambda a, w: tb.math("ADD", med_half, mw), None, "double R"))
    centre_geo = tb.switch(tb.compare("EQUAL", c_idx, 0, "INT"), tb.switch(tb.compare("EQUAL", c_idx, 3, "INT"), c_single, dbl, "GEOMETRY"), tb.empty(), "GEOMETRY")
    w0 = W(ZERO)
    two_way = tb.boolean("AND", tb.compare("GREATER_THAN", w0["lanes_r"], 0.5), tb.compare("GREATER_THAN", w0["lanes_l"], 0.5))
    marks.append(tb.switch(tb.boolean("AND", two_way, tb.boolean("NOT", has_median)), tb.empty(), centre_geo, "GEOMETRY"))
    for k in (1, 2, 3, 4, 5):
        for s, sgn in (("r", 1.0), ("l", -1.0)):
            marks.append(marking(lambda a, w, k=k, sgn=sgn: tb.math("MULTIPLY", tb.math("ADD", med_half, tb.math("MULTIPLY", lw, float(k))), sgn), tb.boolean("OR", True, True), "lane line %d%s" % (k, s),
                                 on_fn=lambda a, w, k=k, s=s: tb.boolean("AND", I("Lane Lines"), tb.compare("LESS_THAN", float(k) + 0.5, w["lanes_" + s]))))
    for s, sgn in (("r", 1.0), ("l", -1.0)):
        marks.append(tb.switch(I("Edge Lines"), tb.empty(), marking(lambda a, w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("SUBTRACT", w["carr_" + s], tb.math("ADD", mw, 0.05)), sgn), None, "edge line " + s), "GEOMETRY"))
        on = br_on if s == "r" else bl_on
        marks.append(tb.switch(on, tb.empty(), marking(lambda a, w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("ADD", w["bike0_" + s], mw), sgn), None, "bike line in " + s), "GEOMETRY"))
        marks.append(tb.switch(on, tb.empty(), marking(lambda a, w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("SUBTRACT", w["bike1_" + s], mw), sgn), None, "bike line out " + s), "GEOMETRY"))
        buf_on = tb.boolean("AND", on, tb.compare("GREATER_THAN", (br_buf if s == "r" else bl_buf), 0.05))
        hatch = sweep(lambda a, w, s=s, sgn=sgn: (tb.math("MULTIPLY", tb.math("ADD", w["buf0_" + s], 0.05), sgn), tb.math("MULTIPLY", tb.math("SUBTRACT", w["bike0_" + s], 0.05), sgn), 0.004, 0.004), I("Marking Material"), "marking", "buffer hatch " + s, zf=camber)
        hd = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(hd, "Geometry", hatch); tb.inp(hd, "Selection", tb.compare("GREATER_THAN", tb.math("MODULO", tb.named("along"), 1.0), 0.15))
        marks.append(tb.switch(buf_on, tb.empty(), hd.outputs[0], "GEOMETRY"))
        pk = I("Parking Right") if s == "r" else I("Parking Left")
        marks.append(tb.switch(tb.compare("GREATER_THAN", pk, 0.05), tb.empty(), marking(lambda a, w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("ADD", w["park0_" + s], mw), sgn), None, "parking line " + s), "GEOMETRY"))
        idx_ = bike_r if s == "r" else bike_l
        geo = marking(lambda a, w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("MULTIPLY", tb.math("ADD", w["bike0_" + s], w["bike1_" + s]), 0.5), sgn), tb.boolean("OR", True, True), "bike centre " + s)
        marks.append(tb.switch(tb.compare("EQUAL", idx_, 4, "INT"), tb.empty(), geo, "GEOMETRY"))

    tb.frame_("Lane_Markings: instanced symbols (ticks, bicycle symbols, separator posts, arrows)")
    mcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(mcoll, "Collection", I("Markings Collection")); tb.inp(mcoll, "Separate Children", True); tb.inp(mcoll, "Reset Children", True)
    A = lambda nm: _coll_index(MRS + "Markings", MRS + nm)
    def instance_marks(points, lat_fn, index, rot_sign=1.0, scale=None, z_lift=0.004):
        w = W(tb.named("along")); xc = lat_fn(w)
        mv = tb.n("GeometryNodeSetPosition"); tb.inp(mv, "Geometry", points)
        tb.inp(mv, "Offset", tb.vmath("ADD", tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=xc), tb.combine(0.0, 0.0, tb.math("ADD", camber(xc, tb.named("along"), w), z_lift))))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.vmath("SCALE", tb.named("tangent", "FLOAT_VECTOR"), scale=rot_sign))
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", mv.outputs[0]); tb.inp(io, "Instance", mcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", index); tb.inp(io, "Rotation", al.outputs[0])
        if scale is not None: tb.inp(io, "Scale", scale)
        return io.outputs[0]
    inst_marks = []
    for s, sgn in (("r", 1.0), ("l", -1.0)):
        pk = I("Parking Right") if s == "r" else I("Parking Left")
        tp = points_along(I("Bay Length"), I("Clear Start"), I("Clear End"))
        ticks = instance_marks(tp, lambda w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("MULTIPLY", tb.math("ADD", w["park0_" + s], w["park1_" + s]), 0.5), sgn), A("MarkTick"), scale=tb.combine(tb.math("SUBTRACT", pk, 0.1), mw, 1.0))
        inst_marks.append(tb.switch(tb.boolean("AND", I("Parking Ticks"), tb.compare("GREATER_THAN", pk, 0.05)), tb.empty(), ticks, "GEOMETRY"))
        on = br_on if s == "r" else bl_on
        idx_ = bike_r if s == "r" else bike_l
        bp = points_along(I("Bike Symbol Spacing"), I("Bike Setback"), I("Bike Setback"))
        fwd = tb.switch(rht, -sgn, sgn, "FLOAT")              # RHT: the right side flows with the curve direction
        sym = instance_marks(bp, lambda w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("MULTIPLY", tb.math("ADD", w["bike0_" + s], w["bike1_" + s]), 0.5), sgn), A("BikeSymbol"), rot_sign=fwd)
        two = tb.compare("EQUAL", idx_, 4, "INT")
        sym_a = instance_marks(bp, lambda w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("ADD", w["bike0_" + s], tb.math("MULTIPLY", tb.math("SUBTRACT", w["bike1_" + s], w["bike0_" + s]), 0.25)), sgn), A("BikeSymbol"), rot_sign=1.0)
        sym_b = instance_marks(bp, lambda w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("ADD", w["bike0_" + s], tb.math("MULTIPLY", tb.math("SUBTRACT", w["bike1_" + s], w["bike0_" + s]), 0.75)), sgn), A("BikeSymbol"), rot_sign=-1.0)
        inst_marks.append(tb.switch(on, tb.empty(), tb.switch(two, sym, tb.join(sym_a, sym_b), "GEOMETRY"), "GEOMETRY"))
        prot = br_prot if s == "r" else bl_prot
        sp_ = points_along(I("Separator Spacing"), I("Clear Start"), I("Clear End"))
        posts = instance_marks(sp_, lambda w, s=s, sgn=sgn: tb.math("MULTIPLY", tb.math("MULTIPLY", tb.math("ADD", w["buf0_" + s], w["bike0_" + s]), 0.5), sgn), tb.switch(tb.compare("EQUAL", sep_kind, 1, "INT"), A("SepPlanter"), A("SepPost"), "INT"), z_lift=0.0)
        inst_marks.append(tb.switch(tb.boolean("AND", prot, tb.compare("GREATER_THAN", sep_kind, 0, "INT")), tb.empty(), posts, "GEOMETRY"))
    # lane arrows before a junction: the lanes that ARRIVE at that end (RHT: right side arrives at the end)
    for at_end in (True, False):
        dist = tb.math("SUBTRACT", L, I("Arrow Distance")) if at_end else I("Arrow Distance")
        w = W(dist)
        arriving_right = rht if at_end else tb.boolean("NOT", rht)
        n_l = tb.switch(arriving_right, w["lanes_l"], w["lanes_r"], "FLOAT")
        sgn = tb.switch(arriving_right, -1.0, 1.0, "FLOAT")
        samp = tb.n("GeometryNodeSampleCurve", mode="LENGTH", data_type="FLOAT"); samp.use_all_curves = True; tb.inp(samp, "Curves", rail); tb.inp(samp, "Length", dist)
        pts = tb.n("GeometryNodePoints"); tb.inp(pts, "Count", tb.math("ROUND", n_l))
        pidx = tb.n("GeometryNodeInputIndex").outputs[0]
        s_side = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", samp.outputs["Tangent"], up))
        xl = tb.math("MULTIPLY", tb.math("ADD", med_half, tb.math("MULTIPLY", tb.math("ADD", pidx, 0.5), lw)), sgn)
        tb.inp(pts, "Position", tb.vmath("ADD", samp.outputs["Position"], tb.vmath("ADD", tb.vmath("SCALE", s_side, scale=xl), tb.combine(0.0, 0.0, tb.math("ADD", camber(xl, dist, w), 0.004)))))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.vmath("SCALE", samp.outputs["Tangent"], scale=1.0 if at_end else -1.0))
        is_inner = tb.compare("EQUAL", pidx, 0, "INT"); is_outer = tb.compare("EQUAL", pidx, tb.math("SUBTRACT", tb.math("ROUND", n_l), 1.0), "INT")
        # the inner lane turns toward the centre side (left in RHT), the outer lane away from it
        inner_arrow = tb.switch(arriving_right, A("ArrowStraightRight"), A("ArrowStraightLeft"), "INT"); outer_arrow = tb.switch(arriving_right, A("ArrowStraightLeft"), A("ArrowStraightRight"), "INT")
        aidx = tb.switch(tb.compare("EQUAL", tb.math("ROUND", n_l), 1, "INT"), tb.switch(is_inner, tb.switch(is_outer, A("ArrowStraight"), outer_arrow, "INT"), inner_arrow, "INT"), A("ArrowStraight"), "INT")
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", pts.outputs[0]); tb.inp(io, "Instance", mcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", aidx); tb.inp(io, "Rotation", al.outputs[0])
        trim_here = I("Trim End") if at_end else I("Trim Start")
        on = tb.boolean("AND", I("Lane Arrows"), tb.boolean("AND", tb.compare("GREATER_THAN", trim_here, 0.5), tb.compare("GREATER_THAN", L, tb.math("MULTIPLY", I("Arrow Distance"), 2.0))))
        inst_marks.append(tb.switch(on, tb.empty(), io.outputs[0], "GEOMETRY"))
    # merge arrows where a lane ends: right side traffic flows toward the end (RHT) -> arrow 8 m before the taper; left side after it
    for right_side in (True, False):
        sgn = 1.0 if right_side else -1.0
        start = tb.switch(rht, I("Lanes Backward"), I("Lanes Forward"), "INT") if right_side else tb.switch(rht, I("Lanes Forward"), I("Lanes Backward"), "INT")
        end = tb.switch(rht, I("Lanes Backward End"), I("Lanes Forward End"), "INT") if right_side else tb.switch(rht, I("Lanes Forward End"), I("Lanes Backward End"), "INT")
        flows_to_end = rht if right_side else tb.boolean("NOT", rht)
        drops = tb.compare("GREATER_THAN", start, end, "INT")
        before = tb.math("SUBTRACT", I("Transition Start"), 8.0); after = tb.math("ADD", tb.math("ADD", I("Transition Start"), I("Taper Length")), 8.0)
        dist = tb.switch(flows_to_end, after, before, "FLOAT")
        samp = tb.n("GeometryNodeSampleCurve", mode="LENGTH", data_type="FLOAT"); samp.use_all_curves = True; tb.inp(samp, "Curves", rail); tb.inp(samp, "Length", dist)
        pts = tb.n("GeometryNodePoints"); tb.inp(pts, "Count", 1)
        s_side = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", samp.outputs["Tangent"], up))
        # the dropped lane is the outermost one at the wide end
        xl = tb.math("MULTIPLY", tb.math("ADD", med_half, tb.math("MULTIPLY", tb.math("SUBTRACT", tb.math("MAXIMUM", start, end), 0.5), lw)), sgn)
        tb.inp(pts, "Position", tb.vmath("ADD", samp.outputs["Position"], tb.vmath("ADD", tb.vmath("SCALE", s_side, scale=xl), tb.combine(0.0, 0.0, 0.004))))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.vmath("SCALE", samp.outputs["Tangent"], scale=tb.switch(flows_to_end, -1.0, 1.0, "FLOAT")))
        # merge toward the centre: a right-side lane merges left (seen in its driving direction)
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", pts.outputs[0]); tb.inp(io, "Instance", mcoll.outputs[0]); tb.inp(io, "Pick Instance", True)
        tb.inp(io, "Instance Index", A("ArrowMergeLeft") if right_side else A("ArrowMergeRight")); tb.inp(io, "Rotation", al.outputs[0])
        inst_marks.append(tb.switch(tb.boolean("AND", I("Transition"), drops), tb.empty(), io.outputs[0], "GEOMETRY"))

    # ---------------------------------------------------------------- Roadside
    tb.frame_("Roadside: optional random props, streetlights, trees, manholes, drains")
    def pick_side(menu): return tb.menu_switch(menu, [(nm, i) for i, nm in enumerate(SIDES)], "INT", "side")
    def side_points(spacing, side_idx, off_fn_l, off_fn_r, up_l, up_r, clear_extra=0.0):
        outs = []
        for sgn, off_fn, upz, keep_idx in ((-1.0, off_fn_l, up_l, (1, 3, 4)), (1.0, off_fn_r, up_r, (2, 3, 4))):
            pts = points_along(spacing, tb.math("ADD", I("Clear Start"), clear_extra), tb.math("ADD", I("Clear End"), clear_extra))
            pidx = tb.n("GeometryNodeInputIndex").outputs[0]
            alt_keep = tb.compare("EQUAL", tb.math("MODULO", pidx, 2.0), 0.0 if sgn < 0 else 1.0)
            keep = tb.boolean("OR", tb.compare("EQUAL", side_idx, keep_idx[0], "INT"), tb.compare("EQUAL", side_idx, keep_idx[1], "INT"))
            keep = tb.boolean("OR", keep, tb.boolean("AND", tb.compare("EQUAL", side_idx, 4, "INT"), alt_keep))
            w = W(tb.named("along"))
            mv = tb.n("GeometryNodeSetPosition"); tb.inp(mv, "Geometry", pts)
            tb.inp(mv, "Offset", tb.vmath("ADD", tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=tb.math("MULTIPLY", off_fn(w), sgn)), tb.combine(0.0, 0.0, upz)))
            st = tb.store(mv.outputs[0], "sgn", sgn)
            dl = tb.n("GeometryNodeDeleteGeometry", domain="POINT", mode="ALL"); tb.inp(dl, "Geometry", st); tb.inp(dl, "Selection", tb.boolean("NOT", keep))
            outs.append(dl.outputs[0])
        return tb.join(*outs)
    def instance_facing_road(points, collection, seed, random_pick=True, yaw_jitter=0.0, scale_jitter=0.0):
        coll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(coll, "Collection", collection); tb.inp(coll, "Separate Children", True); tb.inp(coll, "Reset Children", True)
        facing = tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=neg(tb.named("sgn")))
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
    up_l = tb.switch(I("Sidewalk Left"), 0.0, H, "FLOAT"); up_r = tb.switch(I("Sidewalk Right"), 0.0, H, "FLOAT")
    verge = lambda s: (lambda w: tb.math("ADD", w["curb_" + s], tb.switch(I("Sidewalk Right") if s == "r" else I("Sidewalk Left"), 0.6, 0.3, "FLOAT")))
    props = instance_facing_road(side_points(I("Prop Spacing"), pick_side(I("Prop Side")), lambda w: tb.math("ADD", verge("l")(w), I("Prop Offset")), lambda w: tb.math("ADD", verge("r")(w), I("Prop Offset")), up_l, up_r, 3.0), I("Props"), I("Prop Seed"))
    lights = instance_facing_road(side_points(I("Light Spacing"), pick_side(I("Light Side")), verge("l"), verge("r"), up_l, up_r, 6.0), I("Streetlights"), tb.math("ADD", I("Prop Seed"), 1.0))
    has_strip = lambda s: tb.compare("GREATER_THAN", I("Planting Strip Right") if s == "r" else I("Planting Strip Left"), 0.6)
    tree_off = lambda s: (lambda w: tb.switch(has_strip(s), tb.math("ADD", w["sw_" + s], I("Tree Offset")), tb.math("MULTIPLY", tb.math("ADD", w["curb_" + s], w["plant_" + s]), 0.5), "FLOAT"))
    tree_up = lambda s: tb.switch(has_strip(s), 0.0, H, "FLOAT")
    trees = instance_facing_road(side_points(I("Tree Spacing"), pick_side(I("Tree Side")), tree_off("l"), tree_off("r"), tree_up("l"), tree_up("r"), 8.0), I("Trees"), tb.math("ADD", I("Prop Seed"), 2.0), yaw_jitter=3.14, scale_jitter=0.2)
    c2m_pts = points_along(I("Manhole Spacing"), tb.math("ADD", I("Clear Start"), 6.0), tb.math("ADD", I("Clear End"), 6.0))
    rndf = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(rndf, "Min", -0.8); tb.inp(rndf, "Max", 0.8); tb.inp(rndf, "Seed", tb.math("ADD", I("Prop Seed"), 7.0))
    wm = W(tb.named("along")); mx = tb.math("MULTIPLY", R(rndf), tb.math("MULTIPLY", wm["carr_r"], 0.9))
    mp = tb.n("GeometryNodeSetPosition"); tb.inp(mp, "Geometry", c2m_pts); tb.inp(mp, "Offset", tb.vmath("ADD", tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=mx), tb.combine(0.0, 0.0, tb.math("ADD", camber(mx, tb.named("along"), wm), 0.002))))
    mcoll2 = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(mcoll2, "Collection", I("Manholes")); tb.inp(mcoll2, "Separate Children", True); tb.inp(mcoll2, "Reset Children", True)
    rndi = tb.n("FunctionNodeRandomValue", data_type="INT"); tb.inp(rndi, "Min", 0); tb.inp(rndi, "Max", 100); tb.inp(rndi, "Seed", I("Prop Seed"))
    miop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(miop, "Points", mp.outputs[0]); tb.inp(miop, "Instance", mcoll2.outputs[0]); tb.inp(miop, "Pick Instance", True); tb.inp(miop, "Instance Index", R(rndi))
    drains = []
    dcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(dcoll, "Collection", I("Drains")); tb.inp(dcoll, "Separate Children", True); tb.inp(dcoll, "Reset Children", True)
    for s, sgn in (("r", 1.0), ("l", -1.0)):
        dp = points_along(I("Drain Spacing"), tb.math("ADD", I("Clear Start"), 2.0), tb.math("ADD", I("Clear End"), 2.0))
        wd = W(tb.named("along")); xd = tb.math("MULTIPLY", tb.math("SUBTRACT", wd["half_" + s], 0.3), sgn)
        dm = tb.n("GeometryNodeSetPosition"); tb.inp(dm, "Geometry", dp); tb.inp(dm, "Offset", tb.vmath("ADD", tb.vmath("SCALE", tb.named("side", "FLOAT_VECTOR"), scale=xd), tb.combine(0.0, 0.0, 0.002)))
        al = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(al, "Vector", tb.named("tangent", "FLOAT_VECTOR"))
        io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", dm.outputs[0]); tb.inp(io, "Instance", dcoll.outputs[0]); tb.inp(io, "Pick Instance", True); tb.inp(io, "Rotation", al.outputs[0])
        drains.append(io.outputs[0])

    # ---------------------------------------------------------------- Landscape_Scatter
    tb.frame_("Landscape_Scatter: grass / rocks on embankment and planting-strip faces")
    surfaces = tb.join(*surf, deck_geo, emb_geo)
    dist = tb.n("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM"); tb.inp(dist, "Mesh", surfaces)
    tb.inp(dist, "Selection", tb.compare("EQUAL", tb.named("kind"), float(KIND["embankment"]))); tb.inp(dist, "Density", I("Scatter Density")); tb.inp(dist, "Seed", I("Scatter Seed"))
    scoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(scoll, "Collection", I("Scatter")); tb.inp(scoll, "Separate Children", True); tb.inp(scoll, "Reset Children", True)
    srnd = tb.n("FunctionNodeRandomValue", data_type="INT"); tb.inp(srnd, "Min", 0); tb.inp(srnd, "Max", 100); tb.inp(srnd, "Seed", I("Scatter Seed"))
    srot = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(srot, "Min", 0.0); tb.inp(srot, "Max", 6.283); tb.inp(srot, "Seed", tb.math("ADD", I("Scatter Seed"), 5.0))
    sscl = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(sscl, "Min", 0.5); tb.inp(sscl, "Max", 1.0); tb.inp(sscl, "Seed", tb.math("ADD", I("Scatter Seed"), 9.0))
    sio = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(sio, "Points", dist.outputs["Points"]); tb.inp(sio, "Instance", scoll.outputs[0]); tb.inp(sio, "Pick Instance", True)
    tb.inp(sio, "Instance Index", R(srnd)); tb.inp(sio, "Rotation", tb.combine(0.0, 0.0, R(srot))); tb.inp(sio, "Scale", tb.combine(R(sscl), R(sscl), R(sscl)))
    scatter = tb.switch(tb.compare("GREATER_THAN", I("Scatter Density"), 0.001), tb.empty(), sio.outputs[0], "GEOMETRY")

    # ---------------------------------------------------------------- Road_Surface_Masks + assembly
    tb.frame_("Road_Surface_Masks + assembly: drain attribute, UVMap, collision filter, realize")
    mesh_all = tb.join(surfaces, *marks)
    mesh = tb.switch(I("Collision Only"), mesh_all, surfaces, "GEOMETRY")
    lat_a = tb.named("lat"); hl = tb.named("half_l"); hr = tb.named("half_r")
    half_here = tb.switch(tb.compare("LESS_THAN", lat_a, 0.0), hr, hl, "FLOAT")
    drain = tb.map_range(tb.math("SUBTRACT", half_here, tb.math("ABSOLUTE", lat_a)), 0.0, 1.2, 1.0, 0.0)
    mesh = tb.store(mesh, "drain", drain)
    uv = tb.store(mesh, "UVMap", tb.combine(lat_a, tb.named("along"), 0.0), "FLOAT2", "CORNER")
    smooth = tb.n("GeometryNodeSetShadeSmooth"); tb.inp(smooth, "Geometry", uv); tb.inp(smooth, "Shade Smooth", tb.compare("EQUAL", tb.named("kind"), float(KIND["embankment"])))
    inst = tb.join(*inst_marks, props, lights, trees, miop.outputs[0], *drains, *barriers, pillars, scatter)
    realized = tb.n("GeometryNodeRealizeInstances"); tb.inp(realized, "Geometry", inst)
    pil_real = tb.n("GeometryNodeRealizeInstances"); tb.inp(pil_real, "Geometry", pillars)
    inst_out = tb.switch(I("Collision Only"), tb.switch(I("Realize Instances"), inst, realized.outputs[0], "GEOMETRY"), pil_real.outputs[0], "GEOMETRY")
    tb.link(tb.join(smooth.outputs[0], inst_out), go.inputs[0])
    for pname, rows in INPUTS:
        for row in rows:
            if row[1] == "NodeSocketMenu":
                item = next(i for i in g.interface.items_tree if getattr(i, "name", "") == row[0])
                try: item.default_value = row[2]
                except Exception as e: print("menu default", row[0], e)
    return g
