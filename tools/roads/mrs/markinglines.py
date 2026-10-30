"""MRS_MarkingLines: paint lines along any curve, no road (City Road Maker 2.1's "03. CRM Marking Lines", reconstructed in
tools/roads/crm_reconstruction). Parking bays, a car park's aisles, lines over an extension: draw a curve, pick the
lines; an Array modifier after it repeats a bay line (as the tutorial does at 28:39).

Lines: Edge (both sides at +-Road Size / 2), Center (at X), Lane (Duplicate lines evenly between the centre and each
edge). Each has Line 1 / Line 2 patterns (Line 2 drawn beside Line 1: a double line), Width and colour. Patterns:
None, Solid, Dashed (Dash / Gap), Dotted."""
import bpy
from .nodes import MRS, T, new_tree, sock, panel

PATTERNS = ["None", "Solid", "Dashed", "Dotted"]
DOUBLE_GAP = 0.12        # space between Line 1 and Line 2 of a double line (m)
LIFT = 0.006             # paint above the curve


def _paint(colour):
    m = bpy.data.materials.get(MRS + ("Paint" if colour == "White" else "PaintYellow"))
    if m is None:
        m = bpy.data.materials.new(MRS + ("Paint" if colour == "White" else "PaintYellow"))
        m.diffuse_color = (0.85, 0.85, 0.8, 1) if colour == "White" else (0.82, 0.58, 0.08, 1)
    return m


def build_paint_line():
    """MRS_PaintLine: one line Offset m beside a curve (right +), Width wide, Pattern 0 None / 1 Solid / 2 Dashed
    (Dash / Gap) / 3 Dotted. The line is swept along the curve resampled every 0.1 m and the faces in the gaps are
    deleted (deleting curve points would only reconnect the curve across a gap)."""
    from .customsign import index_switch
    g = new_tree(MRS + "PaintLine"); tb = T(g)
    sock(g, "Curve", "INPUT", "NodeSocketGeometry")
    for nm, d in (("Offset", 0.0), ("Width", 0.1), ("Dash", 3.0), ("Gap", 3.0)): sock(g, nm, "INPUT", "NodeSocketFloat", d)
    sock(g, "Pattern", "INPUT", "NodeSocketInt", 1, 0, 3); sock(g, "Material", "INPUT", "NodeSocketMaterial")
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    offset, width = I["Offset"], I["Width"]
    hw = tb.math("MULTIPLY", width, 0.5)
    prof = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(prof, "Start", tb.combine(tb.math("SUBTRACT", offset, hw), 0.0, 0.0)); tb.inp(prof, "End", tb.combine(tb.math("ADD", offset, hw), 0.0, 0.0))
    rs = tb.n("GeometryNodeResampleCurve"); tb.inp(rs, "Curve", I["Curve"])
    rs.inputs["Mode"].default_value = "Length"; tb.inp(rs, "Length", 0.1)
    on_par = tb.store(rs.outputs[0], "mrs_par", tb.n("GeometryNodeSplineParameter").outputs["Length"])
    c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", on_par); tb.inp(c2m, "Profile Curve", prof.outputs[0])
    par = tb.named("mrs_par")                                                 # read on faces: the face's mid-length
    dashed_on = tb.compare("LESS_THAN", tb.math("FLOORED_MODULO", par, tb.math("ADD", I["Dash"], I["Gap"])), I["Dash"])
    dotted_on = tb.compare("LESS_THAN", tb.math("FLOORED_MODULO", par, tb.math("MULTIPLY", width, 4.0)), tb.math("MULTIPLY", width, 1.5))
    keep = index_switch(tb, I["Pattern"], [False, True, dashed_on, dotted_on], "BOOLEAN")
    dl = tb.n("GeometryNodeDeleteGeometry", domain="FACE"); tb.inp(dl, "Geometry", c2m.outputs[0]); tb.inp(dl, "Selection", tb.boolean("NOT", keep))
    mv = tb.n("GeometryNodeSetPosition"); tb.inp(mv, "Geometry", dl.outputs[0]); tb.inp(mv, "Offset", tb.combine(0.0, 0.0, LIFT))
    sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", mv.outputs[0]); tb.inp(sm, "Material", I["Material"])
    tb.link(tb.switch(tb.compare("EQUAL", I["Pattern"], 0, "INT"), sm.outputs[0], tb.empty(), "GEOMETRY"), go.inputs[0])
    return g


def build_marking_lines():
    build_paint_line()
    g = new_tree(MRS + "MarkingLines"); tb = T(g)
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    sock(g, "Resolution", "INPUT", "NodeSocketInt", 12, 1, 64, "Curve resolution (points per Bezier segment)")
    sock(g, "Road Size", "INPUT", "NodeSocketFloat", 8.0, 0.0, 100.0, "Width between the edge lines (m)", subtype="DISTANCE")
    sock(g, "Dash", "INPUT", "NodeSocketFloat", 3.0, 0.05, 50.0, "Dashed: paint length (m)", subtype="DISTANCE")
    sock(g, "Gap", "INPUT", "NodeSocketFloat", 3.0, 0.05, 50.0, "Dashed: gap length (m)", subtype="DISTANCE")
    groups = {}
    for nm, d1, d2, extra in (("Edge", "Solid", "None", ()), ("Center", "Solid", "None", ("X",)), ("Lane", "Dashed", "None", ("X", "Duplicate"))):
        p = panel(g, nm + " Marking", closed=(nm != "Edge"))
        sock(g, nm + " Marking", "INPUT", "NodeSocketBool", nm == "Edge", parent=p)
        if "Duplicate" in extra: sock(g, nm + " Duplicate", "INPUT", "NodeSocketInt", 1, 1, 8, "Lane lines on each side of the centre", parent=p)
        sock(g, nm + " Line 1", "INPUT", "NodeSocketMenu", parent=p); sock(g, nm + " Line 2", "INPUT", "NodeSocketMenu", parent=p)
        sock(g, nm + " Width", "INPUT", "NodeSocketFloat", 0.1, 0.01, 2.0, "", parent=p, subtype="DISTANCE")
        if "X" in extra: sock(g, nm + " X", "INPUT", "NodeSocketFloat", 0.0, -50.0, 50.0, "Offset from the curve (m)", parent=p, subtype="DISTANCE")
        sock(g, nm + " Color", "INPUT", "NodeSocketMenu", parent=p)
        groups[nm] = (d1, d2)
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    res = tb.n("GeometryNodeSetSplineResolution"); tb.inp(res, "Geometry", I["Geometry"]); tb.inp(res, "Resolution", I["Resolution"])
    nm_ = tb.n("GeometryNodeSetCurveNormal"); tb.inp(nm_, "Curve", res.outputs[0])
    for attempt in ("Z Up", "Z_UP"):
        try: nm_.inputs["Mode"].default_value = attempt; break
        except Exception: continue
    rail = nm_.outputs[0]

    def line(offset, width, pattern_i, mat):
        """One painted line `offset` m beside the curve (right +), `width` wide, in a pattern: an MRS_PaintLine node."""
        return tb.group(MRS + "PaintLine", Curve=rail, Offset=offset, Width=width, Pattern=pattern_i, Dash=I["Dash"], Gap=I["Gap"], Material=mat).outputs[0]

    out = []
    for nm, (d1, d2) in groups.items():
        p1 = tb.menu_switch(I[nm + " Line 1"], [(pn, i) for i, pn in enumerate(PATTERNS)], "INT")
        p2 = tb.menu_switch(I[nm + " Line 2"], [(pn, i) for i, pn in enumerate(PATTERNS)], "INT")
        mat = tb.menu_switch(I[nm + " Color"], [("White", _paint("White")), ("Yellow", _paint("Yellow"))], "MATERIAL")
        w = I[nm + " Width"]
        second = tb.math("ADD", w, DOUBLE_GAP)                               # Line 2 beside Line 1 (toward the curve's right)
        if nm == "Edge":
            half = tb.math("MULTIPLY", I["Road Size"], 0.5)
            offs = [tb.math("MULTIPLY", half, -1.0), half]
            geo = []
            for k, o in enumerate(offs):
                inward = 1.0 if k == 0 else -1.0
                geo.append(line(o, w, p1, mat)); geo.append(line(tb.math("ADD", o, tb.math("MULTIPLY", second, inward)), w, p2, mat))
            grp = tb.join(*geo)
        elif nm == "Center":
            x = I["Center X"]
            grp = tb.join(line(tb.math("SUBTRACT", x, tb.math("MULTIPLY", second, 0.5)), w, p1, mat), line(tb.math("ADD", x, tb.math("MULTIPLY", second, 0.5)), w, p2, mat))
        else:
            # Duplicate lane lines each side: evenly between the centre (X) and the edges
            geo = []
            half = tb.math("MULTIPLY", I["Road Size"], 0.5)
            n_ = I["Lane Duplicate"]
            # line k of n on each side at X +- k * half / (n + 1); lane lines follow the curve, so each is its own sweep
            # (an instance would not bend): up to 8 each side, switched on by Duplicate
            for i_ in range(8):
                kk = float(i_ + 1)
                for sgn in (1.0, -1.0):
                    o_ = tb.math("ADD", I["Lane X"], tb.math("MULTIPLY", sgn, tb.math("DIVIDE", tb.math("MULTIPLY", kk, half), tb.math("ADD", n_, 1.0))))
                    on = tb.compare("LESS_EQUAL", kk, n_)
                    geo.append(tb.switch(on, tb.empty(), tb.join(line(o_, w, p1, mat), line(tb.math("ADD", o_, second), w, p2, mat)), "GEOMETRY"))
            grp = tb.join(*geo)
        out.append(tb.switch(I[nm + " Marking"], tb.empty(), grp, "GEOMETRY"))
        for k_, d in ((nm + " Line 1", d1), (nm + " Line 2", d2), (nm + " Color", "Yellow" if nm == "Center" else "White")):
            try: g.interface.items_tree[k_].default_value = d
            except Exception: pass
    sm = tb.n("GeometryNodeSetShadeSmooth"); tb.inp(sm, "Geometry", tb.join(*out)); tb.inp(sm, "Shade Smooth", False)
    tb.link(sm.outputs[0], go.inputs["Geometry"])
    from . import limits
    limits.apply_to_group(g)                     # the tested ranges (limits.json) as the sockets' min / max
    return g


def add_marking_lines(name, points, collection, **inputs):
    from .nodes import mod_input_set
    if MRS + "MarkingLines" not in bpy.data.node_groups: build_marking_lines()
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); sp.points.add(len(points) - 1)
    for p_, c in zip(sp.points, points): p_.co = (c[0], c[1], c[2], 1.0)
    o = bpy.data.objects.new(name, cu); collection.objects.link(o)
    mod = o.modifiers.new("MRS_MarkingLines", "NODES"); mod.node_group = bpy.data.node_groups[MRS + "MarkingLines"]
    for k, v in inputs.items(): mod_input_set(mod, k, v)
    return o
