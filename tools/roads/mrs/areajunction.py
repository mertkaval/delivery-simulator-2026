"""Area junctions (the "tongue" workflow): roads end in tongues, and one junction object turns every tongue and extension
in its range into a single junction mesh, live in Geometry Nodes. This is a reconstruction of the workflow City Road Maker
2.1 demonstrates (tools/roads/crm_reconstruction); every rule below is a derived, parametric one.

Footprints   Any geometry in the junction's Roads collection whose faces carry `mrs_tongue` takes part: 1 = road
             (carriageway, drawn red), 2 = roadside (drawn yellow), 3 = island (a raised area cut out of the road:
             a roundabout's centre). `mrs_drop` is how far the footprint sits under the
             surface it stands for: the junction builds at position z + mrs_drop, after every object transform. Sources: MRS_Road's Tongue Start / Tongue End, MRS_ExtensionMesh (a mesh object's faces + a
             roadside band), MRS_ExtensionCurve (a curve swept to Road Size + Roadside Size).
MRS_AreaJunction (on any mesh object; its own mesh is the area when Range is off)
             road  = union of the road footprints (holes they enclose filled), every reflex corner filleted with Inner Radius
             side  = union of all footprints (a solid area: holes filled), reflex corners filleted with Outer Radius, minus
                     road, raised by Curb Height
             islands are cut out of the road and raised with the roadside
             the roadside never covers a road's own carriageway (an MRS_Road surface in the Roads collection), so an
             extension's band reaching past a tongue stops at the road's kerb line
             Heights come from the nearest footprint (tongues meeting at one level, as CRM asks).
MRS_RegionOutline (shared): footprint faces -> the outline loops of their union, reflex corners filleted.
"""
import bpy
from .nodes import MRS, T, new_tree, sock, panel

TONGUE_ROAD, TONGUE_SIDE, TONGUE_ISLAND = 1, 2, 3
CARRIAGEWAY_KINDS = (0, 1, 5, 8, 9)      # MRS_Road face kinds between the kerbs: asphalt, marking, bike, crossing, bus
TONGUE_DROP = 0.02          # tongues sit this far under the surface the junction builds (no z-fighting where covered)
TONGUE_OVERLAP = 0.05       # a road's tongue runs this far under the road's own surface: the junction overlaps the road end
SEAT = -0.002               # the junction 2 mm under the roads: where it overlaps a road end, the road's surface wins
PROBE = 0.05                # corner test: a point this far along the corner's bisector (m)
STRAIGHT = 0.02             # outline points turning less than this (|sin|) are dropped before filleting


def tongue_materials():
    """MRS_TongueRoad (red), MRS_TongueSide (yellow), MRS_TongueIsland (green): viewport guides, never exported."""
    out = []
    for name, rgb in (("TongueRoad", (0.62, 0.12, 0.12)), ("TongueSide", (0.85, 0.7, 0.18)), ("TongueIsland", (0.2, 0.55, 0.2))):
        m = bpy.data.materials.get(MRS + name) or bpy.data.materials.new(MRS + name)
        m.diffuse_color = rgb + (1.0,); m.use_nodes = True
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b: b.inputs["Base Color"].default_value = rgb + (1.0,); b.inputs["Roughness"].default_value = 0.8
        m["mrs_guide"] = True
        out.append(m)
    return out


def _ensure_mat(name, rgb):
    m = bpy.data.materials.get(MRS + name)
    if m is None:
        m = bpy.data.materials.new(MRS + name); m.diffuse_color = rgb + (1.0,)
    return m


# ------------------------------------------------------------------ shared outline
def build_region_outline():
    """MRS_RegionOutline: Mesh (flat footprint faces at z = 0) -> Curve (outline loops of their union, cyclic), reflex
    corners filleted with Radius over Count points; Region = the union as a triangulated mesh.
    Union by winding number, no boolean: every footprint island's outline loop is turned counter-clockwise (by its
    signed area) and one Fill Curve with the Non-Zero rule fills them all; the union's outline is the boundary of that
    single exact triangulation (a boolean of touching prisms left T-junction seams that read as phantom outlines).
    A footprint island is a simple polygon (no holes): a hole in the road is an island footprint (kind 3)."""
    g = new_tree(MRS + "RegionOutline"); tb = T(g)
    sock(g, "Mesh", "INPUT", "NodeSocketGeometry")
    sock(g, "Radius", "INPUT", "NodeSocketFloat", 2.0, 0.0, 100.0, "Fillet radius of the reflex corners (m)")
    sock(g, "Count", "INPUT", "NodeSocketInt", 10, 1, 64, "Points per fillet")
    sock(g, "Fill Holes", "INPUT", "NodeSocketBool", False, desc="Fill every hole the union encloses")
    sock(g, "Curve", "OUTPUT", "NodeSocketGeometry"); sock(g, "Region", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    def neighbour(off):
        idx = tb.n("GeometryNodeInputIndex").outputs[0]
        op = tb.n("GeometryNodeOffsetPointInCurve"); tb.inp(op, "Point Index", idx); tb.inp(op, "Offset", off)
        fa = tb.n("GeometryNodeFieldAtIndex", data_type="FLOAT_VECTOR", domain="POINT"); tb.inp(fa, "Index", op.outputs["Point Index"])
        tb.inp(fa, "Value", tb.n("GeometryNodeInputPosition").outputs[0])
        return fa.outputs[0]
    def ccw_fill(mesh):
        """The mesh's boundary loops, each turned counter-clockwise (by its signed area), filled at once by winding
        number (Non-Zero): overlapping loops unite; a hole's loop, turned counter-clockwise too, fills the hole."""
        en0 = tb.n("GeometryNodeInputMeshEdgeNeighbors")
        loops = tb.n("GeometryNodeMeshToCurve"); tb.inp(loops, "Mesh", mesh); tb.inp(loops, "Selection", tb.compare("EQUAL", en0.outputs["Face Count"], 1, "INT"))
        P = tb.n("GeometryNodeInputPosition").outputs[0]; x0, y0, _ = tb.separate(P); x1, y1, _ = tb.separate(neighbour(1))
        cross = tb.math("SUBTRACT", tb.math("MULTIPLY", x0, y1), tb.math("MULTIPLY", x1, y0))   # shoelace term
        cid = tb.n("GeometryNodeCurveOfPoint"); tb.inp(cid, "Point Index", tb.n("GeometryNodeInputIndex").outputs[0])
        acc = tb.n("GeometryNodeAccumulateField", data_type="FLOAT", domain="POINT"); tb.inp(acc, "Value", cross); tb.inp(acc, "Group ID", cid.outputs["Curve Index"])
        area2 = tb.store(loops.outputs[0], "mrs_area2", acc.outputs["Total"], "FLOAT", "POINT")
        rev = tb.n("GeometryNodeReverseCurve"); tb.inp(rev, "Curve", area2)
        tb.inp(rev, "Selection", tb.compare("LESS_THAN", tb.named("mrs_area2"), 0.0))              # read on splines: the loop's area
        fill = tb.n("GeometryNodeFillCurve"); tb.inp(fill, "Curve", rev.outputs[0])
        fill.inputs["Mode"].default_value = "Triangles"; fill.inputs["Fill Rule"].default_value = "Non-Zero"
        return fill.outputs[0]
    tb.frame_("Union: island outlines turned counter-clockwise, one Non-Zero fill; holes filled when asked")
    union = ccw_fill(I["Mesh"])
    region = tb.switch(I["Fill Holes"], union, ccw_fill(union), "GEOMETRY")
    tb.frame_("Outline: boundary edges -> curve loops, straight points dropped")
    en = tb.n("GeometryNodeInputMeshEdgeNeighbors")
    m2c = tb.n("GeometryNodeMeshToCurve"); tb.inp(m2c, "Mesh", region); tb.inp(m2c, "Selection", tb.compare("EQUAL", en.outputs["Face Count"], 1, "INT"))
    curve = m2c.outputs[0]
    P = tb.n("GeometryNodeInputPosition").outputs[0]
    d1 = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", P, neighbour(-1))); d2 = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", neighbour(1), P))
    x1, y1, _ = tb.separate(d1); x2, y2, _ = tb.separate(d2)
    turn = tb.math("SUBTRACT", tb.math("MULTIPLY", x1, y2), tb.math("MULTIPLY", y1, x2))
    straight = tb.boolean("AND", tb.compare("LESS_THAN", tb.math("ABSOLUTE", turn), STRAIGHT), tb.compare("GREATER_THAN", tb.vmath("DOT_PRODUCT", d1, d2), 0.0))
    dl = tb.n("GeometryNodeDeleteGeometry", domain="POINT"); tb.inp(dl, "Geometry", curve); tb.inp(dl, "Selection", straight)
    curve = dl.outputs[0]
    tb.frame_("Reflex corners: a probe on the bisector outside the region -> fillet radius")
    P = tb.n("GeometryNodeInputPosition").outputs[0]
    d1 = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", P, neighbour(-1))); d2 = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", neighbour(1), P))
    bis = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", d2, d1))
    probe = tb.vmath("ADD", tb.vmath("ADD", P, tb.vmath("SCALE", bis, scale=PROBE)), (0.0, 0.0, 5.0))
    rc = tb.n("GeometryNodeRaycast"); tb.inp(rc, "Target Geometry", region); tb.inp(rc, "Source Position", probe)
    tb.inp(rc, "Ray Direction", (0.0, 0.0, -1.0)); tb.inp(rc, "Ray Length", 10.0)
    reflex = tb.boolean("NOT", rc.outputs["Is Hit"])
    fl = tb.n("GeometryNodeFilletCurve"); tb.inp(fl, "Curve", curve); tb.inp(fl, "Radius", tb.switch(reflex, 0.0, I["Radius"]))
    tb.inp(fl, "Limit Radius", True); tb.inp(fl, "Count", I["Count"])
    fl.inputs["Mode"].default_value = "Poly"
    tb.link(fl.outputs[0], go.inputs["Curve"]); tb.link(region, go.inputs["Region"])
    return g


# ------------------------------------------------------------------ the junction
def build_area_junction():
    """MRS_AreaJunction: the CRM-style junction object (inputs named as in CRM's 02. CRM Junctions panel)."""
    build_region_outline(); tongue_materials()
    asphalt = _ensure_mat("Asphalt", (0.12, 0.12, 0.13)); paving = _ensure_mat("Paving", (0.46, 0.45, 0.43)); concrete = _ensure_mat("Concrete", (0.5, 0.5, 0.48))
    g = new_tree(MRS + "AreaJunction"); tb = T(g)
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    p = panel(g, "Junctions")
    sock(g, "Roads", "INPUT", "NodeSocketCollection", None, desc="Collection holding the roads and extensions whose tongues meet here", parent=p)
    sock(g, "Show", "INPUT", "NodeSocketBool", True, desc="Build the junction mesh (off: the tongues show)", parent=p)
    sock(g, "Range", "INPUT", "NodeSocketBool", True, desc="Take tongues within Distance of the origin (off: inside this object's own mesh)", parent=p)
    sock(g, "Distance", "INPUT", "NodeSocketFloat", 40.0, 0.0, 100000.0, "Range radius (m)", parent=p, subtype="DISTANCE")
    sock(g, "Export Ready", "INPUT", "NodeSocketBool", False, desc="No viewport guides (the range circle): only the surfaces, with UVs", parent=p)
    sock(g, "Inner Radius", "INPUT", "NodeSocketFloat", 2.0, 0.0, 100.0, "Fillet of the road surface's reflex corners (kerb line, m)", parent=p, subtype="DISTANCE")
    sock(g, "Outer Radius", "INPUT", "NodeSocketFloat", 0.0, 0.0, 100.0, "Fillet of the roadside's outer reflex corners (back of the sidewalk, m)", parent=p, subtype="DISTANCE")
    sock(g, "Resolution", "INPUT", "NodeSocketInt", 10, 1, 64, "Points per fillet", parent=p)
    pr = panel(g, "Road", closed=True)
    sock(g, "Road Material", "INPUT", "NodeSocketMaterial", None, parent=pr)
    sock(g, "Height Offset", "INPUT", "NodeSocketFloat", SEAT, -1.0, 1.0, "Surface above the tongues' level (m): 2 mm under, so the roads' ends lie over it", parent=pr, subtype="DISTANCE")
    ps = panel(g, "RoadSide", closed=True)
    sock(g, "RoadSide", "INPUT", "NodeSocketBool", True, desc="Build the roadside (yellow footprints)", parent=ps)
    sock(g, "Roadside Material", "INPUT", "NodeSocketMaterial", None, parent=ps)
    sock(g, "Curb Material", "INPUT", "NodeSocketMaterial", None, parent=ps)
    sock(g, "Curb Height", "INPUT", "NodeSocketFloat", 0.15, 0.0, 2.0, "", parent=ps, subtype="DISTANCE")
    sock(g, "UV Scale", "INPUT", "NodeSocketFloat", 1.0, 0.001, 100.0, "UV units per metre", parent=ps)
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    g.interface.items_tree["Road Material"].default_value = asphalt
    g.interface.items_tree["Roadside Material"].default_value = paving
    g.interface.items_tree["Curb Material"].default_value = concrete

    tb.frame_("Footprints: the Roads collection's tongue faces, in range")
    ci = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(ci, "Collection", I["Roads"])
    tb.inp(ci, "Separate Children", True); tb.inp(ci, "Reset Children", False)
    ri = tb.n("GeometryNodeRealizeInstances"); tb.inp(ri, "Geometry", ci.outputs[0]); tb.inp(ri, "Realize All", False); tb.inp(ri, "Depth", 1)
    sc = tb.n("GeometryNodeSeparateComponents"); tb.inp(sc, "Geometry", ri.outputs[0])
    is_t = tb.compare("GREATER_THAN", tb.named("mrs_tongue"), 0.5)
    lat_attr = tb.n("GeometryNodeInputNamedAttribute", data_type="FLOAT"); tb.inp(lat_attr, "Name", "lat")
    kind_v = tb.named("kind"); in_cw = None
    for k in CARRIAGEWAY_KINDS:
        c_ = tb.compare("LESS_THAN", tb.math("ABSOLUTE", tb.math("SUBTRACT", kind_v, float(k))), 0.5)
        in_cw = c_ if in_cw is None else tb.boolean("OR", in_cw, c_)
    nz_s = tb.separate(tb.n("GeometryNodeInputNormal").outputs[0])[2]
    is_surf = tb.boolean("AND", tb.boolean("AND", lat_attr.outputs["Exists"], tb.boolean("NOT", is_t)), tb.boolean("AND", in_cw, tb.compare("GREATER_THAN", nz_s, 0.5)))
    ss = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(ss, "Geometry", sc.outputs["Mesh"]); tb.inp(ss, "Selection", is_surf)
    ps_ = tb.separate(tb.n("GeometryNodeInputPosition").outputs[0])
    surf_flat = tb.n("GeometryNodeSetPosition"); tb.inp(surf_flat, "Geometry", ss.outputs["Selection"]); tb.inp(surf_flat, "Position", tb.combine(ps_[0], ps_[1], 0.0))
    st = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(st, "Geometry", sc.outputs["Mesh"]); tb.inp(st, "Selection", is_t)
    tongues = st.outputs["Selection"]
    # in range: a footprint island takes part as a whole when any of its vertices is in (Range: within Distance of the
    # origin; otherwise inside this object's own mesh bounds)
    pos = tb.n("GeometryNodeInputPosition").outputs[0]; px, py, pz = tb.separate(pos)
    near = tb.compare("LESS_EQUAL", tb.vmath("LENGTH", tb.combine(px, py, 0.0)), I["Distance"])
    bb = tb.n("GeometryNodeBoundBox"); tb.inp(bb, "Geometry", I["Geometry"])
    mn = tb.separate(bb.outputs["Min"]); mx = tb.separate(bb.outputs["Max"])
    inside = tb.boolean("AND", tb.boolean("AND", tb.compare("GREATER_EQUAL", px, mn[0]), tb.compare("LESS_EQUAL", px, mx[0])),
                        tb.boolean("AND", tb.boolean("AND", tb.compare("GREATER_EQUAL", py, mn[1]), tb.compare("LESS_EQUAL", py, mx[1])),
                                   tb.boolean("AND", tb.compare("GREATER_EQUAL", pz, mn[2]), tb.compare("LESS_EQUAL", pz, mx[2]))))
    hit = tb.switch(I["Range"], inside, near, "BOOLEAN")
    # ... or the footprint lies under the area's centre (a small junction inside one big extension)
    tongues = tb.store(tongues, "mrs_island", tb.n("GeometryNodeInputMeshIsland").outputs["Island Index"], "FLOAT", "FACE")
    cx = tb.switch(I["Range"], tb.math("MULTIPLY", tb.math("ADD", mn[0], mx[0]), 0.5), 0.0)
    cy = tb.switch(I["Range"], tb.math("MULTIPLY", tb.math("ADD", mn[1], mx[1]), 0.5), 0.0)
    rc = tb.n("GeometryNodeRaycast", data_type="FLOAT"); tb.inp(rc, "Target Geometry", tongues); tb.inp(rc, "Attribute", tb.named("mrs_island"))
    tb.inp(rc, "Source Position", tb.combine(cx, cy, 10000.0)); tb.inp(rc, "Ray Direction", (0.0, 0.0, -1.0)); tb.inp(rc, "Ray Length", 20000.0)
    under = tb.boolean("AND", rc.outputs["Is Hit"], tb.compare("LESS_THAN", tb.math("ABSOLUTE", tb.math("SUBTRACT", rc.outputs["Attribute"], tb.named("mrs_island"))), 0.5))
    hit = tb.boolean("OR", hit, under)
    isl = tb.n("GeometryNodeInputMeshIsland")
    acc = tb.n("GeometryNodeAccumulateField", data_type="FLOAT", domain="POINT"); tb.inp(acc, "Value", tb.switch(hit, 0.0, 1.0)); tb.inp(acc, "Group ID", isl.outputs["Island Index"])
    keep = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(keep, "Geometry", tongues); tb.inp(keep, "Selection", tb.compare("GREATER_THAN", acc.outputs["Total"], 0.5))
    fp = keep.outputs["Selection"]
    fp = tb.store(fp, "mrs_level", tb.math("ADD", pz, tb.named("mrs_drop")), "FLOAT", "POINT")
    flat = tb.n("GeometryNodeSetPosition"); tb.inp(flat, "Geometry", fp); tb.inp(flat, "Position", tb.combine(px, py, 0.0))
    fp_flat = flat.outputs[0]
    def of_kind(k):
        sel = tb.compare("LESS_THAN", tb.math("ABSOLUTE", tb.math("SUBTRACT", tb.named("mrs_tongue"), float(k))), 0.5)
        sg = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(sg, "Geometry", fp_flat); tb.inp(sg, "Selection", sel)
        return sg.outputs["Selection"]

    tb.frame_("Outlines: road (Inner Radius) and road + roadside (Outer Radius)")
    # the road never has a hole of its own: a gap the road footprints enclose (tongues that do not quite meet) is road;
    # raised areas inside a junction come only from island footprints
    road_ol = tb.group(MRS + "RegionOutline", Mesh=of_kind(TONGUE_ROAD), Radius=I["Inner Radius"], Count=I["Resolution"], **{"Fill Holes": True})
    all_ol = tb.group(MRS + "RegionOutline", Mesh=fp_flat, Radius=I["Outer Radius"], Count=I["Resolution"], **{"Fill Holes": True})   # a solid area
    isl_ol = tb.group(MRS + "RegionOutline", Mesh=of_kind(TONGUE_ISLAND), Radius=0.0, Count=I["Resolution"])
    def ccw(curve):
        """Every loop turned counter-clockwise (by its signed area): a Non-Zero fill then unites them."""
        def nb(off):
            idx = tb.n("GeometryNodeInputIndex").outputs[0]
            op = tb.n("GeometryNodeOffsetPointInCurve"); tb.inp(op, "Point Index", idx); tb.inp(op, "Offset", off)
            fa = tb.n("GeometryNodeFieldAtIndex", data_type="FLOAT_VECTOR", domain="POINT"); tb.inp(fa, "Index", op.outputs["Point Index"])
            tb.inp(fa, "Value", tb.n("GeometryNodeInputPosition").outputs[0]); return fa.outputs[0]
        x0, y0, _ = tb.separate(tb.n("GeometryNodeInputPosition").outputs[0]); x1, y1, _ = tb.separate(nb(1))
        cid = tb.n("GeometryNodeCurveOfPoint"); tb.inp(cid, "Point Index", tb.n("GeometryNodeInputIndex").outputs[0])
        acc = tb.n("GeometryNodeAccumulateField", data_type="FLOAT", domain="POINT")
        tb.inp(acc, "Value", tb.math("SUBTRACT", tb.math("MULTIPLY", x0, y1), tb.math("MULTIPLY", x1, y0))); tb.inp(acc, "Group ID", cid.outputs["Curve Index"])
        a2 = tb.store(curve, "mrs_area2", acc.outputs["Total"], "FLOAT", "POINT")
        rv = tb.n("GeometryNodeReverseCurve"); tb.inp(rv, "Curve", a2); tb.inp(rv, "Selection", tb.compare("LESS_THAN", tb.named("mrs_area2"), 0.0))
        return rv.outputs[0]
    def fill(curve, rule):
        f = tb.n("GeometryNodeFillCurve"); tb.inp(f, "Curve", curve)
        f.inputs["Fill Rule"].default_value = rule; f.inputs["Mode"].default_value = "Triangles"      # planar faces at any level
        # a boundary shared by two loops (a road end lying on the outer outline) stays in the triangulation as an edge
        # with no face on either side: delete such loose edges (the viewport draws them as lines, an exporter as line
        # primitives)
        en = tb.n("GeometryNodeInputMeshEdgeNeighbors")
        dl = tb.n("GeometryNodeDeleteGeometry", domain="EDGE", mode="EDGE_FACE"); tb.inp(dl, "Geometry", f.outputs[0])
        tb.inp(dl, "Selection", tb.compare("EQUAL", en.outputs["Face Count"], 0, "INT"))
        up = tb.n("GeometryNodeFlipFaces"); tb.inp(up, "Mesh", dl.outputs[0])                   # the winding decides the normal: face up
        tb.inp(up, "Selection", tb.compare("LESS_THAN", tb.separate(tb.n("GeometryNodeInputNormal").outputs[0])[2], 0.0))
        return up.outputs[0]
    # even-odd: the road with its islands as holes
    road = fill(tb.join(road_ol.outputs["Curve"], isl_ol.outputs["Curve"]), "Even-Odd")
    # the roadside: ONE constrained triangulation of every loop (area, road, islands, the roads' own carriageways), so
    # each triangle lies wholly inside or outside each region; a triangle is roadside when its centre is inside the
    # area and in neither the road nor a carriageway, or inside an island. It never overlaps the road by construction
    # (an outline re-derived from the road fill differed from the road's own by slivers that read as road AND roadside).
    surf_ol = tb.group(MRS + "RegionOutline", Mesh=surf_flat.outputs[0], Radius=0.0, Count=I["Resolution"])
    loops = [all_ol.outputs["Curve"], road_ol.outputs["Curve"], isl_ol.outputs["Curve"], surf_ol.outputs["Curve"]]
    arr = fill(tb.join(*[ccw(c) for c in loops]), "Non-Zero")                         # the union, with every loop's edges
    def inside(target):
        pc = tb.separate(tb.n("GeometryNodeInputPosition").outputs[0])                              # the face's centre (face domain)
        rc = tb.n("GeometryNodeRaycast"); tb.inp(rc, "Target Geometry", target); tb.inp(rc, "Source Position", tb.combine(pc[0], pc[1], 50.0))
        tb.inp(rc, "Ray Direction", (0.0, 0.0, -1.0)); tb.inp(rc, "Ray Length", 100.0)
        return rc.outputs["Is Hit"]
    in_area = inside(fill(all_ol.outputs["Curve"], "Non-Zero")); in_road = inside(fill(road_ol.outputs["Curve"], "Non-Zero"))
    in_isl = inside(fill(isl_ol.outputs["Curve"], "Non-Zero")); in_cw = inside(surf_ol.outputs["Region"])
    keep = tb.boolean("OR", tb.boolean("AND", in_area, tb.boolean("NOT", tb.boolean("OR", in_road, in_cw))), in_isl)
    out_a = tb.n("GeometryNodeDeleteGeometry", domain="FACE"); tb.inp(out_a, "Geometry", arr); tb.inp(out_a, "Selection", tb.boolean("NOT", keep))
    side = out_a.outputs[0]

    tb.frame_("Heights: each vertex at the nearest footprint's surface level")
    def at_level(geo, lift):
        sn = tb.n("GeometryNodeSampleNearestSurface", data_type="FLOAT"); tb.inp(sn, "Mesh", fp_flat); tb.inp(sn, "Value", tb.named("mrs_level"))
        p_ = tb.n("GeometryNodeInputPosition").outputs[0]; x_, y_, _ = tb.separate(p_); tb.inp(sn, "Sample Position", tb.combine(x_, y_, 0.0))
        sp_ = tb.n("GeometryNodeSetPosition"); tb.inp(sp_, "Geometry", geo); tb.inp(sp_, "Position", tb.combine(x_, y_, tb.math("ADD", sn.outputs[0], lift)))
        return sp_.outputs[0]
    road = at_level(road, I["Height Offset"])
    side = at_level(side, I["Height Offset"])
    exs = tb.n("GeometryNodeExtrudeMesh", mode="FACES"); tb.inp(exs, "Mesh", side); tb.inp(exs, "Offset", tb.combine(0.0, 0.0, I["Curb Height"])); tb.inp(exs, "Individual", False)
    nz = tb.separate(tb.n("GeometryNodeInputNormal").outputs[0])[2]
    side_m = tb.n("GeometryNodeSetMaterial"); tb.inp(side_m, "Geometry", exs.outputs["Mesh"]); tb.inp(side_m, "Material", I["Curb Material"])
    tb.inp(side_m, "Selection", tb.compare("LESS_THAN", tb.math("ABSOLUTE", nz), 0.5))
    side_t = tb.n("GeometryNodeSetMaterial"); tb.inp(side_t, "Geometry", side_m.outputs[0]); tb.inp(side_t, "Material", I["Roadside Material"])
    tb.inp(side_t, "Selection", tb.compare("GREATER_EQUAL", tb.math("ABSOLUTE", nz), 0.5))
    side = tb.switch(I["RoadSide"], tb.empty(), side_t.outputs[0], "GEOMETRY")
    road_m = tb.n("GeometryNodeSetMaterial"); tb.inp(road_m, "Geometry", road); tb.inp(road_m, "Material", I["Road Material"])
    road = tb.store(road_m.outputs[0], "kind", 0.0, "FLOAT", "FACE")
    side = tb.store(side, "kind", 2.0, "FLOAT", "FACE")
    surf = tb.join(road, side)
    surf = tb.store(surf, "ground_surface", 1.0, "FLOAT", "FACE")
    pw = tb.n("GeometryNodeInputPosition").outputs[0]; ux, uy, _ = tb.separate(pw)
    surf = tb.store(surf, "UVMap", tb.combine(tb.math("MULTIPLY", ux, I["UV Scale"]), tb.math("MULTIPLY", uy, I["UV Scale"]), 0.0), "FLOAT2", "CORNER")
    surf = tb.switch(I["Show"], tb.empty(), surf, "GEOMETRY")

    tb.frame_("Viewport guide: the range circle")
    circ = tb.n("GeometryNodeCurvePrimitiveCircle", mode="RADIUS"); tb.inp(circ, "Resolution", 64); tb.inp(circ, "Radius", I["Distance"])
    guide_on = tb.boolean("AND", tb.boolean("AND", I["Range"], tb.n("GeometryNodeIsViewport").outputs[0]), tb.boolean("NOT", I["Export Ready"]))
    guide = tb.switch(guide_on, tb.empty(), circ.outputs[0], "GEOMETRY")
    tb.link(tb.join(surf, guide), go.inputs["Geometry"])
    return g


# ------------------------------------------------------------------ extensions
def drop_of(kind):
    return TONGUE_DROP * {TONGUE_ROAD: 1.0, TONGUE_SIDE: 1.5, TONGUE_ISLAND: 0.5}[kind]      # red over yellow, green over red


def _footprint(tb, geo, kind):
    """Tag faces as a footprint: mrs_tongue = kind, the guide material, lowered by drop_of(kind) (stored in mrs_drop)."""
    geo = tb.store(geo, "mrs_tongue", float(kind), "FLOAT", "FACE")
    geo = tb.store(geo, "mrs_drop", drop_of(kind), "FLOAT", "POINT")
    mat = bpy.data.materials[MRS + {TONGUE_ROAD: "TongueRoad", TONGUE_SIDE: "TongueSide", TONGUE_ISLAND: "TongueIsland"}[kind]]
    sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", geo); tb.inp(sm, "Material", mat)
    mv = tb.n("GeometryNodeSetPosition"); tb.inp(mv, "Geometry", sm.outputs[0]); tb.inp(mv, "Offset", (0.0, 0.0, -drop_of(kind)))
    return mv.outputs[0]


def build_extension_mesh():
    """MRS_ExtensionMesh (CRM "19. CRM Extension Mesh"): the object's faces are road (red); a band Roadside Size wide
    round their outline is roadside (yellow), mitred at corners."""
    tongue_materials()
    g = new_tree(MRS + "ExtensionMesh"); tb = T(g)
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    sock(g, "Roadside Size", "INPUT", "NodeSocketFloat", 2.0, 0.0, 50.0, "Width of the roadside band round the area (m)", subtype="DISTANCE")
    sock(g, "Island", "INPUT", "NodeSocketBool", False, desc="The area is an island: cut out of the road and raised (a roundabout's centre); no band")
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    island = _footprint(tb, I["Geometry"], TONGUE_ISLAND)
    red = _footprint(tb, I["Geometry"], TONGUE_ROAD)
    en = tb.n("GeometryNodeInputMeshEdgeNeighbors")
    m2c = tb.n("GeometryNodeMeshToCurve"); tb.inp(m2c, "Mesh", I["Geometry"]); tb.inp(m2c, "Selection", tb.compare("EQUAL", en.outputs["Face Count"], 1, "INT"))
    # mitre: a corner turning by theta gets its profile scaled by 1 / cos(theta / 2)
    def neighbour(off):
        idx = tb.n("GeometryNodeInputIndex").outputs[0]
        op = tb.n("GeometryNodeOffsetPointInCurve"); tb.inp(op, "Point Index", idx); tb.inp(op, "Offset", off)
        fa = tb.n("GeometryNodeFieldAtIndex", data_type="FLOAT_VECTOR", domain="POINT"); tb.inp(fa, "Index", op.outputs["Point Index"])
        tb.inp(fa, "Value", tb.n("GeometryNodeInputPosition").outputs[0]); return fa.outputs[0]
    P = tb.n("GeometryNodeInputPosition").outputs[0]
    d1 = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", P, neighbour(-1))); d2 = tb.vmath("NORMALIZE", tb.vmath("SUBTRACT", neighbour(1), P))
    half_cos = tb.math("SQRT", tb.math("MAXIMUM", tb.math("MULTIPLY", tb.math("ADD", 1.0, tb.vmath("DOT_PRODUCT", d1, d2)), 0.5), 0.0))
    rad = tb.n("GeometryNodeSetCurveRadius"); tb.inp(rad, "Curve", m2c.outputs[0]); tb.inp(rad, "Radius", tb.math("DIVIDE", 1.0, tb.math("MAXIMUM", half_cos, 0.25)))
    prof = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(prof, "Start", tb.combine(tb.math("MULTIPLY", I["Roadside Size"], -1.0), 0.0, 0.0))
    tb.inp(prof, "End", tb.combine(I["Roadside Size"], 0.0, 0.0))
    c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", rad.outputs[0]); tb.inp(c2m, "Profile Curve", prof.outputs[0])
    yellow = _footprint(tb, c2m.outputs[0], TONGUE_SIDE)
    tb.link(tb.switch(I["Island"], tb.join(red, yellow), island, "GEOMETRY"), go.inputs["Geometry"])
    return g


def build_extension_curve():
    """MRS_ExtensionCurve (CRM "10. CRM Extension"): the curve swept to Road Size (red) inside Road Size + 2 x Roadside
    Size (yellow)."""
    tongue_materials()
    g = new_tree(MRS + "ExtensionCurve"); tb = T(g)
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    sock(g, "Resolution", "INPUT", "NodeSocketInt", 2, 1, 64, "Curve resolution (points per Bezier segment)")
    sock(g, "Road Size", "INPUT", "NodeSocketFloat", 5.0, 0.0, 100.0, "", subtype="DISTANCE")
    sock(g, "Roadside Size", "INPUT", "NodeSocketFloat", 2.0, 0.0, 50.0, "", subtype="DISTANCE")
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    res = tb.n("GeometryNodeSetSplineResolution"); tb.inp(res, "Geometry", I["Geometry"]); tb.inp(res, "Resolution", I["Resolution"])
    def strip(width):
        hw = tb.math("MULTIPLY", width, 0.5)
        prof = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(prof, "Start", tb.combine(tb.math("MULTIPLY", hw, -1.0), 0.0, 0.0)); tb.inp(prof, "End", tb.combine(hw, 0.0, 0.0))
        c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", res.outputs[0]); tb.inp(c2m, "Profile Curve", prof.outputs[0])
        return c2m.outputs[0]
    red = _footprint(tb, strip(I["Road Size"]), TONGUE_ROAD)
    yellow = _footprint(tb, strip(tb.math("ADD", I["Road Size"], tb.math("MULTIPLY", I["Roadside Size"], 2.0))), TONGUE_SIDE)
    tb.link(tb.join(red, yellow), go.inputs["Geometry"])
    return g


def build_all():
    from . import limits
    tongue_materials()
    groups = build_region_outline(), build_area_junction(), build_extension_mesh(), build_extension_curve()
    for g in groups: limits.apply_to_group(g)    # the tested ranges (limits.json) as the sockets' min / max
    return groups


def add_area_junction(name, location, roads_collection, collection=None, **inputs):
    """A junction object (a 2 m cube: Range off makes its mesh the area) with MRS_AreaJunction."""
    from .nodes import mod_input_set
    if MRS + "AreaJunction" not in bpy.data.node_groups: build_all()
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); (collection or bpy.context.scene.collection).objects.link(o); o.location = location
    mod = o.modifiers.new("MRS_AreaJunction", "NODES"); mod.node_group = bpy.data.node_groups[MRS + "AreaJunction"]
    mod_input_set(mod, "Roads", roads_collection)
    for k, v in inputs.items(): mod_input_set(mod, k, v)
    return o


def add_extension(name, kind, collection, location=(0.0, 0.0, 0.0), size=(10.0, 10.0), points=None, **inputs):
    """An extension object: kind "square" / "round" (mesh) or "curve" (`points` [(x, y, z)])."""
    from .nodes import mod_input_set
    import bmesh, math
    if MRS + "ExtensionMesh" not in bpy.data.node_groups: build_all()
    if kind == "curve":
        cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); sp.points.add(len(points) - 1)
        for p_, c in zip(sp.points, points): p_.co = (c[0], c[1], c[2], 1.0)
        o = bpy.data.objects.new(name, cu); grp = MRS + "ExtensionCurve"
    else:
        me = bpy.data.meshes.new(name); bm = bmesh.new()
        if kind == "round":
            bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=size[0] * 0.5)
        else:
            vs = [bm.verts.new((sx * size[0] * 0.5, sy * size[1] * 0.5, 0.0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]; bm.faces.new(vs)
        bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); grp = MRS + "ExtensionMesh"
    collection.objects.link(o); o.location = location
    mod = o.modifiers.new(grp, "NODES"); mod.node_group = bpy.data.node_groups[grp]
    for k, v in inputs.items(): mod_input_set(mod, k, v)
    return o
