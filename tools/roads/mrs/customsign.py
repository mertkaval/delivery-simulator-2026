"""MRS_CustomSign: a fully parametric sign in Geometry Nodes, reconstructed from City Road Maker 2.1's "13. CRM Custom
Sign" (tools/roads/crm_reconstruction). Live text (String to Curves), so editing a text, colour, size or position updates the
sign at once; the font is the String to Curves node's inside the nested MRS_PanelText group (as in CRM, a font is not a
group input).

Panels (CRM's order): Panel (shape, scale, colour, rotation, bevel, outline), Back Post (shape, width, struts, poles),
Text Line 1..3 (three texts each: text, colour, size, X, Y), Images (three materials), Lines Shape (three bars).
The sign faces -Y (the MRS signage convention: traffic arrives from -Y), its panel centre at the origin + Panel Height.
Colours "Auto" pick white or black for contrast with the panel colour."""
import math
import bpy
from .nodes import MRS, T, new_tree, sock, panel

COLOURS = ["White", "Black", "Red", "Blue", "Green", "Yellow", "Orange", "Brown", "Grey"]
LIGHT = ("White", "Yellow", "Orange", "Grey")           # "Auto" text on these is black, otherwise white
SHAPES = ["Quad", "Octagon", "Circle", "Triangle", "Diamond"]
POSTS = ["Pipe", "U Channel", "Square"]
THICK = 0.02            # panel thickness (m)
FRONT = 0.002           # text / image / line layers stand this far in front of the panel face


def index_switch(tb, idx, values, kind):
    """An Index Switch over `values` (a group menu socket may drive only ONE Menu Switch: every further use goes
    through that switch's index)."""
    n = tb.n("GeometryNodeIndexSwitch", data_type=kind)
    while len(n.index_switch_items) < len(values): n.index_switch_items.new()
    tb.inp(n, "Index", idx)
    for i, v in enumerate(values): tb.inp(n, n.inputs[i + 1].identifier, v)
    return n.outputs[0]


def _mat(colour):
    from . import signage
    return signage.face_material(colour)


def build_panel_text():
    """MRS_PanelText (CRM "Panel Text", 9 users): Text, Size, X, Y, Material -> filled text curves at (X, Y)."""
    g = new_tree(MRS + "PanelText"); tb = T(g)
    for nm, st, d in (("Text", "NodeSocketString", ""), ("Size", "NodeSocketFloat", 0.1), ("X", "NodeSocketFloat", 0.0), ("Y", "NodeSocketFloat", 0.0)):
        sock(g, nm, "INPUT", st, d)
    sock(g, "Material", "INPUT", "NodeSocketMaterial"); sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs
    s2c = tb.n("GeometryNodeStringToCurves"); tb.inp(s2c, "String", I["Text"]); tb.inp(s2c, "Size", I["Size"])
    s2c.inputs["Align X"].default_value = "Center"; s2c.inputs["Align Y"].default_value = "Middle"
    res = tb.n("GeometryNodeSetSplineResolution"); tb.inp(res, "Geometry", s2c.outputs["Curve Instances"]); tb.inp(res, "Resolution", 6)
    fill = tb.n("GeometryNodeFillCurve"); tb.inp(fill, "Curve", res.outputs[0]); fill.inputs["Mode"].default_value = "N-gons"
    real = tb.n("GeometryNodeRealizeInstances"); tb.inp(real, "Geometry", fill.outputs[0])
    sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", real.outputs[0]); tb.inp(sm, "Material", I["Material"])
    # text curves lie in XY: stand them up on the sign face (X right, Z up, facing -Y)
    tr = tb.n("GeometryNodeTransform"); tb.inp(tr, "Geometry", sm.outputs[0]); tb.inp(tr, "Rotation", (math.pi / 2, 0.0, 0.0))
    tb.inp(tr, "Translation", tb.combine(I["X"], -(THICK * 0.5 + FRONT), I["Y"]))
    tb.link(tr.outputs[0], go.inputs[0])
    return g


def build_custom_sign():
    build_panel_text()
    g = new_tree(MRS + "CustomSign"); tb = T(g)
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    pp = panel(g, "Panel")
    sock(g, "Shape", "INPUT", "NodeSocketMenu", parent=pp)
    sock(g, "Scale X", "INPUT", "NodeSocketFloat", 0.6, 0.05, 20.0, "Panel width (m)", parent=pp, subtype="DISTANCE")
    sock(g, "Scale Y", "INPUT", "NodeSocketFloat", 0.6, 0.05, 20.0, "Panel height (m)", parent=pp, subtype="DISTANCE")
    sock(g, "Color", "INPUT", "NodeSocketMenu", parent=pp)
    sock(g, "Rotation", "INPUT", "NodeSocketFloat", 0.0, -6.3, 6.3, "Panel rotation in its plane", parent=pp, subtype="ANGLE")
    sock(g, "Bevel Radius", "INPUT", "NodeSocketFloat", 0.044, 0.0, 5.0, "Corner rounding (m)", parent=pp, subtype="DISTANCE")
    sock(g, "Bevel Res", "INPUT", "NodeSocketInt", 4, 1, 32, "Points per rounded corner", parent=pp)
    sock(g, "Outline", "INPUT", "NodeSocketBool", True, desc="A border band inside the panel edge", parent=pp)
    sock(g, "Position", "INPUT", "NodeSocketFloat", 0.0, 0.0, 2.0, "Border inset from the edge (m)", parent=pp)
    sock(g, "Width", "INPUT", "NodeSocketFloat", 0.03, 0.0, 2.0, "Border width (m)", parent=pp)
    sock(g, "Outline Color", "INPUT", "NodeSocketMenu", parent=pp)
    sock(g, "Panel Height", "INPUT", "NodeSocketFloat", 2.2, 0.0, 20.0, "Panel centre above the origin (m)", parent=pp, subtype="DISTANCE")
    pb = panel(g, "Back Post", closed=True)
    sock(g, "Post Shape", "INPUT", "NodeSocketMenu", parent=pb)
    sock(g, "Post Width", "INPUT", "NodeSocketFloat", 0.372, 0.0, 20.0, "Length of the horizontal struts behind the panel (m)", parent=pb, subtype="DISTANCE")
    sock(g, "H Struts Count", "INPUT", "NodeSocketInt", 2, 0, 8, "Horizontal struts behind the panel", parent=pb)
    sock(g, "Poles Count", "INPUT", "NodeSocketInt", 1, 0, 4, "Vertical poles to the ground", parent=pb)
    sock(g, "Pole Height", "INPUT", "NodeSocketFloat", 0.0, 0.0, 20.0, "Pole length above the panel's bottom edge (0: up to the panel centre)", parent=pb, subtype="DISTANCE")
    texts = []
    for ln in range(1, 4):
        pt = panel(g, "Text Line %d" % ln, closed=True)
        for k in range(1, 4):
            sfx = "" if k == 1 else " %d" % k
            nm = "L%d T%d" % (ln, k)
            sock(g, "%s Text" % nm, "INPUT", "NodeSocketString", "", parent=pt)
            sock(g, "%s Color" % nm, "INPUT", "NodeSocketMenu", parent=pt)
            sock(g, "%s Size" % nm, "INPUT", "NodeSocketFloat", 0.1, 0.0, 5.0, "", parent=pt)
            sock(g, "%s X" % nm, "INPUT", "NodeSocketFloat", 0.0, -20.0, 20.0, "", parent=pt, subtype="DISTANCE")
            sock(g, "%s Y" % nm, "INPUT", "NodeSocketFloat", 0.0, -20.0, 20.0, "", parent=pt, subtype="DISTANCE")
            texts.append(nm)
    pi = panel(g, "Images", closed=True)
    for k in range(1, 4):
        sock(g, "Image %d Material" % k, "INPUT", "NodeSocketMaterial", parent=pi)
        sock(g, "Image %d Size" % k, "INPUT", "NodeSocketFloat", 0.5, 0.0, 20.0, "", parent=pi)
        sock(g, "Image %d X" % k, "INPUT", "NodeSocketFloat", 0.0, -20.0, 20.0, "", parent=pi, subtype="DISTANCE")
        sock(g, "Image %d Y" % k, "INPUT", "NodeSocketFloat", 0.0, -20.0, 20.0, "", parent=pi, subtype="DISTANCE")
    pl = panel(g, "Lines Shape", closed=True)
    for k in range(1, 4):
        sock(g, "Line %d Color" % k, "INPUT", "NodeSocketMenu", parent=pl)
        sock(g, "Line %d Length" % k, "INPUT", "NodeSocketFloat", 0.0, 0.0, 20.0, "0: no line", parent=pl, subtype="DISTANCE")
        sock(g, "Line %d Width" % k, "INPUT", "NodeSocketFloat", 0.03, 0.0, 5.0, "", parent=pl, subtype="DISTANCE")
        sock(g, "Line %d Rotation" % k, "INPUT", "NodeSocketFloat", 0.0, -6.3, 6.3, "", parent=pl, subtype="ANGLE")
        sock(g, "Line %d X" % k, "INPUT", "NodeSocketFloat", 0.0, -20.0, 20.0, "", parent=pl, subtype="DISTANCE")
        sock(g, "Line %d Y" % k, "INPUT", "NodeSocketFloat", 0.0, -20.0, 20.0, "", parent=pl, subtype="DISTANCE")
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = gi.outputs

    def colour(menu, with_auto=False, auto=None):
        items = ([("Auto", auto)] if with_auto else []) + [(c, _mat(c)) for c in COLOURS]
        return tb.menu_switch(menu, items, "MATERIAL")
    tb.frame_("Panel: shape outline (scaled, bevelled), filled, given thickness; the border band")
    col_i = tb.menu_switch(I["Color"], [(c, i) for i, c in enumerate(COLOURS)], "INT")
    panel_mat = index_switch(tb, col_i, [_mat(c) for c in COLOURS], "MATERIAL")
    light = index_switch(tb, col_i, [c in LIGHT for c in COLOURS], "BOOLEAN")
    auto = tb.switch(light, _mat("White"), _mat("Black"), "MATERIAL")
    shape_i = tb.menu_switch(I["Shape"], [(nm, i) for i, nm in enumerate(SHAPES)], "INT")
    post_i = tb.menu_switch(I["Post Shape"], [(nm, i) for i, nm in enumerate(POSTS)], "INT")
    def outline_curve(inset):
        """The panel shape as a closed curve, `inset` m inside the edge (by scaling about the centre)."""
        sx = tb.math("MAXIMUM", tb.math("SUBTRACT", I["Scale X"], tb.math("MULTIPLY", inset, 2.0)), 0.001)
        sy = tb.math("MAXIMUM", tb.math("SUBTRACT", I["Scale Y"], tb.math("MULTIPLY", inset, 2.0)), 0.001)
        quad = tb.n("GeometryNodeCurvePrimitiveQuadrilateral", mode="RECTANGLE"); tb.inp(quad, "Width", 1.0); tb.inp(quad, "Height", 1.0)
        def ngon(n, rot, r):
            """A regular n-gon of circumradius r, chosen so the shape is 1 wide (Scale X is its width)."""
            c = tb.n("GeometryNodeCurvePrimitiveCircle", mode="RADIUS"); tb.inp(c, "Resolution", n); tb.inp(c, "Radius", r)
            t = tb.n("GeometryNodeTransform"); tb.inp(t, "Geometry", c.outputs[0]); tb.inp(t, "Rotation", (0.0, 0.0, rot)); return t.outputs[0]
        oct_ = ngon(8, math.pi / 8, 0.5 / math.cos(math.pi / 8))             # flat top and bottom (a stop sign), 1 across the flats
        circ = ngon(48, 0.0, 0.5)
        tri = ngon(3, -math.pi / 2, 0.5 / math.cos(math.pi / 6))             # point down (give way), 1 wide
        dia = ngon(4, 0.0, 0.5)
        shp = index_switch(tb, shape_i, [quad.outputs[0], oct_, circ, tri, dia], "GEOMETRY")         # SHAPES order
        sc_ = tb.n("GeometryNodeTransform"); tb.inp(sc_, "Geometry", shp); tb.inp(sc_, "Scale", tb.combine(sx, sy, 1.0)); tb.inp(sc_, "Rotation", tb.combine(0.0, 0.0, I["Rotation"]))
        fl = tb.n("GeometryNodeFilletCurve"); tb.inp(fl, "Curve", sc_.outputs[0]); fl.inputs["Mode"].default_value = "Poly"
        tb.inp(fl, "Radius", tb.math("MAXIMUM", tb.math("SUBTRACT", I["Bevel Radius"], inset), 0.0)); tb.inp(fl, "Count", I["Bevel Res"]); tb.inp(fl, "Limit Radius", True)
        return fl.outputs[0]
    def stand(geo, y):
        """XY-plane geometry onto the sign face plane (X right, Z up), at depth y, the panel centre Panel Height up."""
        t = tb.n("GeometryNodeTransform"); tb.inp(t, "Geometry", geo); tb.inp(t, "Rotation", (math.pi / 2, 0.0, 0.0)); tb.inp(t, "Translation", tb.combine(0.0, y, I["Panel Height"]))
        return t.outputs[0]
    edge = outline_curve(0.0)
    face = tb.n("GeometryNodeFillCurve"); tb.inp(face, "Curve", edge); face.inputs["Mode"].default_value = "Triangles"
    up = tb.n("GeometryNodeFlipFaces"); tb.inp(up, "Mesh", face.outputs[0])                    # Fill Curve's winding decides the normal
    tb.inp(up, "Selection", tb.compare("LESS_THAN", tb.separate(tb.n("GeometryNodeInputNormal").outputs[0])[2], 0.0))
    # Extrude Mesh's Offset has an implicit Normal field: a constant typed in is ignored, so link it
    slab = tb.n("GeometryNodeExtrudeMesh", mode="FACES"); tb.inp(slab, "Mesh", up.outputs[0]); tb.inp(slab, "Offset", tb.combine(0.0, 0.0, THICK))
    tb.inp(slab, "Individual", False)
    back = tb.n("GeometryNodeFlipFaces"); tb.inp(back, "Mesh", up.outputs[0])
    plate = tb.join(slab.outputs["Mesh"], back.outputs[0])
    pm = tb.n("GeometryNodeSetMaterial"); tb.inp(pm, "Geometry", plate); tb.inp(pm, "Material", panel_mat)
    # stand: the slab spans local z 0..THICK -> y from +THICK/2 (back) to -THICK/2 (front); rotation maps +z to -y
    panel_geo = stand(pm.outputs[0], THICK * 0.5)
    band = tb.n("GeometryNodeFillCurve"); tb.inp(band, "Curve", tb.join(outline_curve(I["Position"]), outline_curve(tb.math("ADD", I["Position"], I["Width"]))))
    band.inputs["Mode"].default_value = "Triangles"
    bm_ = tb.n("GeometryNodeSetMaterial"); tb.inp(bm_, "Geometry", band.outputs[0]); tb.inp(bm_, "Material", colour(I["Outline Color"], True, auto))
    border = tb.switch(tb.boolean("AND", I["Outline"], tb.compare("GREATER_THAN", I["Width"], 0.0)), tb.empty(), stand(bm_.outputs[0], -(THICK * 0.5 + FRONT * 0.5)), "GEOMETRY")

    tb.frame_("Text lines: nine Panel Text slots (empty text = nothing)")
    words = []
    for nm in texts:
        node = tb.group(MRS + "PanelText", Text=I["%s Text" % nm], Size=I["%s Size" % nm], X=I["%s X" % nm], Y=I["%s Y" % nm],
                        Material=colour(I["%s Color" % nm], True, auto))
        node.label = "Panel Text " + nm
        lift = tb.n("GeometryNodeTransform"); tb.inp(lift, "Geometry", node.outputs[0]); tb.inp(lift, "Translation", tb.combine(0.0, 0.0, I["Panel Height"]))
        words.append(lift.outputs[0])
    tb.frame_("Images (a square of the material, its UVs 0..1) and line bars")
    extras = []
    for k in range(1, 4):
        sz = I["Image %d Size" % k]
        grid = tb.n("GeometryNodeMeshGrid"); tb.inp(grid, "Size X", sz); tb.inp(grid, "Size Y", sz); tb.inp(grid, "Vertices X", 2); tb.inp(grid, "Vertices Y", 2)
        uv = tb.store(grid.outputs["Mesh"], "UVMap", grid.outputs["UV Map"], "FLOAT2", "CORNER")
        mv = tb.n("GeometryNodeTransform"); tb.inp(mv, "Geometry", uv); tb.inp(mv, "Translation", tb.combine(I["Image %d X" % k], I["Image %d Y" % k], 0.0))
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", mv.outputs[0]); tb.inp(sm, "Material", I["Image %d Material" % k])
        img = stand(sm.outputs[0], -(THICK * 0.5 + FRONT * 0.75))
        # no material, no image (as in CRM): Material Selection of an empty material matches only a face without one
        probe = tb.n("GeometryNodeMeshGrid"); ms = tb.n("GeometryNodeMaterialSelection"); tb.inp(ms, "Material", I["Image %d Material" % k])
        si = tb.n("GeometryNodeSampleIndex", data_type="BOOLEAN", domain="FACE"); tb.inp(si, "Geometry", probe.outputs[0]); tb.inp(si, "Value", ms.outputs[0]); tb.inp(si, "Index", 0)
        on = tb.boolean("AND", tb.compare("GREATER_THAN", sz, 0.0), tb.boolean("NOT", si.outputs[0]))
        extras.append(tb.switch(on, tb.empty(), img, "GEOMETRY"))
    for k in range(1, 4):
        Ln = I["Line %d Length" % k]
        grid = tb.n("GeometryNodeMeshGrid"); tb.inp(grid, "Size X", Ln); tb.inp(grid, "Size Y", I["Line %d Width" % k]); tb.inp(grid, "Vertices X", 2); tb.inp(grid, "Vertices Y", 2)
        mv = tb.n("GeometryNodeTransform"); tb.inp(mv, "Geometry", grid.outputs["Mesh"]); tb.inp(mv, "Rotation", tb.combine(0.0, 0.0, I["Line %d Rotation" % k]))
        tb.inp(mv, "Translation", tb.combine(I["Line %d X" % k], I["Line %d Y" % k], 0.0))
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", mv.outputs[0]); tb.inp(sm, "Material", colour(I["Line %d Color" % k], True, auto))
        extras.append(tb.switch(tb.compare("GREATER_THAN", Ln, 0.0), tb.empty(), stand(sm.outputs[0], -(THICK * 0.5 + FRONT)), "GEOMETRY"))

    tb.frame_("Back post: horizontal struts behind the panel, poles down to the ground")
    metal = bpy.data.materials.get(MRS + "PoleMetal") or _mat("Grey")
    def profile(width):
        """The post's cross-section: pipe (circle), U channel (open square), square tube."""
        circ = tb.n("GeometryNodeCurvePrimitiveCircle", mode="RADIUS"); tb.inp(circ, "Resolution", 12); tb.inp(circ, "Radius", width * 0.5)
        sq = tb.n("GeometryNodeCurvePrimitiveQuadrilateral", mode="RECTANGLE"); tb.inp(sq, "Width", width); tb.inp(sq, "Height", width)
        uq = tb.n("GeometryNodeCurvePrimitiveQuadrilateral", mode="RECTANGLE"); tb.inp(uq, "Width", width); tb.inp(uq, "Height", width * 0.6)
        cyc = tb.n("GeometryNodeSetSplineCyclic"); tb.inp(cyc, "Geometry", uq.outputs[0]); tb.inp(cyc, "Cyclic", False)      # open side: a U
        return index_switch(tb, post_i, [circ.outputs[0], cyc.outputs[0], sq.outputs[0]], "GEOMETRY")   # POSTS order
    half_h = tb.math("MULTIPLY", I["Scale Y"], 0.5)
    # struts: evenly spread over the panel height, Post Width long, just behind the panel
    n_s = I["H Struts Count"]
    st_pts = tb.n("GeometryNodeMeshLine", mode="END_POINTS"); tb.inp(st_pts, "Count", n_s)
    tb.inp(st_pts, "Start Location", tb.combine(0.0, 0.0, tb.math("ADD", I["Panel Height"], tb.math("MULTIPLY", half_h, -0.6))))
    tb.inp(st_pts, "Offset", tb.combine(0.0, 0.0, tb.math("ADD", I["Panel Height"], tb.math("MULTIPLY", half_h, 0.6))))
    strut_line = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(strut_line, "Start", tb.combine(tb.math("MULTIPLY", I["Post Width"], -0.5), 0.0, 0.0))
    tb.inp(strut_line, "End", tb.combine(tb.math("MULTIPLY", I["Post Width"], 0.5), 0.0, 0.0))
    strut = tb.n("GeometryNodeCurveToMesh"); tb.inp(strut, "Curve", strut_line.outputs[0]); tb.inp(strut, "Profile Curve", profile(0.04)); tb.inp(strut, "Fill Caps", True)
    io = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(io, "Points", st_pts.outputs[0]); tb.inp(io, "Instance", strut.outputs[0])
    struts = tb.n("GeometryNodeTranslateInstances"); tb.inp(struts, "Instances", io.outputs[0]); tb.inp(struts, "Translation", (0.0, THICK + 0.03, 0.0))
    struts = tb.switch(tb.compare("GREATER_THAN", n_s, 0, "INT"), tb.empty(), struts.outputs[0], "GEOMETRY")
    # poles: Poles Count of them across the panel width, from the ground to the panel top (or Pole Height above its bottom)
    n_p = I["Poles Count"]
    top_z = tb.switch(tb.compare("GREATER_THAN", I["Pole Height"], 0.0), tb.math("ADD", I["Panel Height"], half_h),
                      tb.math("ADD", tb.math("SUBTRACT", I["Panel Height"], half_h), I["Pole Height"]))
    spread = tb.math("MULTIPLY", I["Scale X"], 0.6)
    p_pts = tb.n("GeometryNodeMeshLine", mode="END_POINTS"); tb.inp(p_pts, "Count", n_p)
    one = tb.compare("EQUAL", n_p, 1, "INT")
    tb.inp(p_pts, "Start Location", tb.combine(tb.switch(one, tb.math("MULTIPLY", spread, -0.5), 0.0), THICK + 0.07, 0.0))
    tb.inp(p_pts, "Offset", tb.combine(tb.switch(one, tb.math("MULTIPLY", spread, 0.5), 0.0), THICK + 0.07, 0.0))
    pole_line = tb.n("GeometryNodeCurvePrimitiveLine"); tb.inp(pole_line, "Start", (0.0, 0.0, 0.0)); tb.inp(pole_line, "End", tb.combine(0.0, 0.0, top_z))
    pole = tb.n("GeometryNodeCurveToMesh"); tb.inp(pole, "Curve", pole_line.outputs[0]); tb.inp(pole, "Profile Curve", profile(0.07)); tb.inp(pole, "Fill Caps", True)
    pio = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(pio, "Points", p_pts.outputs[0]); tb.inp(pio, "Instance", pole.outputs[0])
    poles = tb.switch(tb.compare("GREATER_THAN", n_p, 0, "INT"), tb.empty(), pio.outputs[0], "GEOMETRY")
    post = tb.n("GeometryNodeRealizeInstances"); tb.inp(post, "Geometry", tb.join(struts, poles))
    postm = tb.n("GeometryNodeSetMaterial"); tb.inp(postm, "Geometry", post.outputs[0]); tb.inp(postm, "Material", metal)
    out = tb.join(panel_geo, border, *words, *extras, postm.outputs[0])
    tb.link(out, go.inputs["Geometry"])
    # menu defaults (the menu switches define the entries)
    for nm, d in (("Shape", "Quad"), ("Color", "Blue"), ("Outline Color", "Auto"), ("Post Shape", "Pipe")):
        try: g.interface.items_tree[nm].default_value = d
        except Exception: pass
    for nm in texts:
        try: g.interface.items_tree["%s Color" % nm].default_value = "Auto"
        except Exception: pass
    for k in range(1, 4):
        try: g.interface.items_tree["Line %d Color" % k].default_value = "Auto"
        except Exception: pass
    from . import limits
    limits.apply_to_group(g)                     # the tested ranges (limits.json) as the sockets' min / max
    return g


PRESETS = {   # CRM's demonstrated signs (tools/roads/crm_reconstruction: E43-E48), as modifier inputs
    "CRM 2.1": {"Shape": "Quad", "Color": "Blue", "Scale X": 0.6, "Scale Y": 0.6, "Bevel Radius": 0.044, "Bevel Res": 4, "Outline": True, "Position": 0.0, "Width": 0.03,
                "L1 T1 Text": "CRM 2.1", "L1 T1 Size": 0.097, "L1 T1 Y": 0.155, "L1 T2 Text": "Custom Sign", "L1 T2 Size": 0.1, "L1 T2 Y": -0.163,
                "Line 1 Length": 0.45, "Line 1 Width": 0.054, "Line 1 Color": "White", "Post Shape": "Pipe", "H Struts Count": 2, "Poles Count": 1},
    "Stop": {"Shape": "Octagon", "Color": "Red", "Scale X": 0.6, "Scale Y": 0.6, "Bevel Radius": 0.0, "Outline": True, "Position": 0.021, "Width": 0.026, "Outline Color": "White",
             "L1 T1 Text": "STOP", "L1 T1 Size": 0.2, "L1 T1 Color": "White", "Post Shape": "Pipe", "H Struts Count": 1, "Poles Count": 1},
}


def add_custom_sign(name, location=(0.0, 0.0, 0.0), preset="CRM 2.1", collection=None, yaw=0.0, **inputs):
    from .nodes import mod_input_set
    if MRS + "CustomSign" not in bpy.data.node_groups: build_custom_sign()
    me = bpy.data.meshes.new(name); o = bpy.data.objects.new(name, me); (collection or bpy.context.scene.collection).objects.link(o)
    o.location = location; o.rotation_euler = (0.0, 0.0, yaw)
    mod = o.modifiers.new("MRS_CustomSign", "NODES"); mod.node_group = bpy.data.node_groups[MRS + "CustomSign"]
    for k, v in dict(PRESETS.get(preset, {}), **inputs).items(): mod_input_set(mod, k, v)
    o["mrs_custom_sign"] = preset
    return o
