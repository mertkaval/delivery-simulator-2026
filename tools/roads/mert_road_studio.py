"""Mert Road Studio: a curve-driven road and street generator for Blender 5.2 (Geometry Nodes +
procedural shader groups + Python junctions, UI and export), built for the Godot delivery simulator.

    exec(open("tools/roads/mert_road_studio.py").read())       # in a live Blender (MCP) or the text editor
    mrs.build_groups(); mrs.register()                          # node groups, materials, the N-panel
    mrs.demo_scene()                                            # the validation scene (collection MRS_Demo)
    mrs.export_glb(path)                                        # evaluated meshes + separate collision

Geometry Nodes group "MRS_Road" (on a curve object): the road is a set of strips swept along the
resampled curve with Curve to Mesh, each strip a Curve Line profile whose width comes from the
inputs (lanes x lane width, shoulders, median, curbs, sidewalks). Markings are their own thin
strips at lateral offsets; dashes are cut with the along-the-road length attribute. UVs are
stored as (lateral metres, along metres), so texture scale is stable on every road. Roadside
props are Curve-to-Points instances from collections, kept out of the junction approaches by the
Prop Clear inputs that the junction manager sets.

Junctions (Python, explicit): roads whose ends meet at a junction point are trimmed (Trim Start /
End inputs), the junction surface is the polygon through the trimmed road corners, with sidewalk
corner pieces, crosswalk stripes and stop lines as meshes. Supported: 2-4 roads meeting at one
point with angles >= 50 degrees and matching heights; others are reported, not faked.
"""
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix, geometry

MRS = "MRS_"
PRESETS = {
    "residential": dict(lanes=2, lane_width=3.2, shoulder=0.0, median=0.0, sidewalk_l=True, sidewalk_r=True, sidewalk_w=2.0, sidewalk_h=0.15,
                        curb_w=0.25, centre=2, edge_lines=False, dash=3.0, gap=6.0, marking_w=0.12, prop_spacing=28.0, prop_offset=0.5),
    "urban": dict(lanes=4, lane_width=3.5, shoulder=0.3, median=1.2, sidewalk_l=True, sidewalk_r=True, sidewalk_w=3.0, sidewalk_h=0.15,
                  curb_w=0.3, centre=3, edge_lines=True, dash=3.0, gap=4.5, marking_w=0.12, prop_spacing=24.0, prop_offset=0.6),
    "service": dict(lanes=1, lane_width=4.5, shoulder=0.6, median=0.0, sidewalk_l=False, sidewalk_r=False, sidewalk_w=1.5, sidewalk_h=0.12,
                    curb_w=0.2, centre=0, edge_lines=True, dash=2.0, gap=4.0, marking_w=0.1, prop_spacing=40.0, prop_offset=0.8),
}
MATERIAL_PRESETS = {"dry": dict(wetness=0.0), "wet": dict(wetness=0.85)}


# ============================================================================== node helpers
class T:
    """Node-tree builder: new nodes in a left-to-right flow, optional frames, typed sockets by identifier."""
    def __init__(self, tree):
        self.t = tree; self.x = 0; self.y = 0; self.frame = None

    def frame_(self, label):
        f = self.t.nodes.new("NodeFrame"); f.label = label; self.frame = f; self.y -= 500; self.x = 0; return f

    def n(self, idname, label=None, **props):
        node = self.t.nodes.new(idname)
        node.location = (self.x, self.y); self.x += 200
        if self.x > 4200: self.x = 0; self.y -= 320
        if self.frame: node.parent = self.frame
        if label: node.label = label
        for k, v in props.items(): setattr(node, k, v)
        return node

    def link(self, a, b):
        self.t.links.new(a, b)

    def inp(self, node, key, value):
        """Set or link an input by identifier (or name)."""
        sock = node.inputs.get(key)
        if sock is None:
            sock = next((s for s in node.inputs if s.identifier == key), None)
        if sock is None: raise KeyError("%s has no input %s: %s" % (node.name, key, [s.identifier for s in node.inputs]))
        if isinstance(value, bpy.types.NodeSocket): self.link(value, sock)
        else: sock.default_value = value
        return sock

    def math(self, op, a, b=0.0, c=None):
        node = self.n("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b) if c is None else (a, b, c)): self.inp(node, node.inputs[i].identifier, v)
        return node.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        node = self.n("ShaderNodeVectorMath", operation=op)
        self.inp(node, node.inputs[0].identifier, a)
        if b is not None: self.inp(node, node.inputs[1].identifier, b)
        if scale is not None: self.inp(node, "Scale", scale)
        return node.outputs[0]

    def combine(self, x=0.0, y=0.0, z=0.0):
        node = self.n("ShaderNodeCombineXYZ")
        self.inp(node, "X", x); self.inp(node, "Y", y); self.inp(node, "Z", z)
        return node.outputs[0]

    def compare(self, op, a, b, data_type="FLOAT"):
        node = self.n("FunctionNodeCompare", operation=op, data_type=data_type)
        self.inp(node, node.inputs[0].identifier, a); self.inp(node, node.inputs[1].identifier, b)
        return node.outputs[0]

    def boolean(self, op, a, b):
        node = self.n("FunctionNodeBooleanMath", operation=op)
        self.inp(node, node.inputs[0].identifier, a); self.inp(node, node.inputs[1].identifier, b)
        return node.outputs[0]

    def switch(self, cond, false_v, true_v, kind="FLOAT"):
        node = self.n("GeometryNodeSwitch", input_type=kind)
        self.inp(node, "Switch", cond); self.inp(node, "False", false_v); self.inp(node, "True", true_v)
        return node.outputs[0]


def new_tree(name, kind="GeometryNodeTree"):
    if name in bpy.data.node_groups: bpy.data.node_groups.remove(bpy.data.node_groups[name])
    return bpy.data.node_groups.new(name, kind)


def sock(tree, name, in_out, stype, default=None, minv=None, maxv=None, desc=""):
    s = tree.interface.new_socket(name, in_out=in_out, socket_type=stype, description=desc)
    if default is not None: s.default_value = default
    if minv is not None and hasattr(s, "min_value"): s.min_value = minv
    if maxv is not None and hasattr(s, "max_value"): s.max_value = maxv
    return s


# ============================================================================== materials
def _mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; m.node_tree.nodes.clear(); return m


def build_materials():
    """MRS_Asphalt, MRS_Paint, MRS_Concrete on top of three editable shader groups. Every control is a
    group input; Wetness darkens the colour and lowers roughness together (puddles in the low noise)."""
    # ---- shared coordinate: object space in metres (roads of any length keep the same texel scale)
    def coord(tb, scale_sock):
        tc = tb.n("ShaderNodeTexCoord")
        return tb.vmath("SCALE", tc.outputs["Object"], scale=scale_sock)

    # ---- MRS_AsphaltShader group
    g = new_tree(MRS + "AsphaltShader", "ShaderNodeTree")
    for nm, st, d in (("Asphalt Scale", "NodeSocketFloat", 1.0), ("Asphalt Roughness", "NodeSocketFloat", 0.86), ("Color Variation", "NodeSocketFloat", 0.25),
                      ("Patch Amount", "NodeSocketFloat", 0.15), ("Wetness", "NodeSocketFloat", 0.0), ("Base Color", "NodeSocketColor", (0.075, 0.075, 0.08, 1)),
                      ("Bump Strength", "NodeSocketFloat", 0.25)):
        sock(g, nm, "INPUT", st, d)
    sock(g, "BSDF", "OUTPUT", "NodeSocketShader")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    v = coord(tb, gi.outputs["Asphalt Scale"])
    broad = tb.n("ShaderNodeTexNoise", "broad tone"); tb.inp(broad, "Vector", v); tb.inp(broad, "Scale", 0.08); tb.inp(broad, "Detail", 2.0)
    agg = tb.n("ShaderNodeTexVoronoi", "aggregate", feature="F1"); tb.inp(agg, "Vector", v); tb.inp(agg, "Scale", 140.0)
    fine = tb.n("ShaderNodeTexNoise", "fine grain"); tb.inp(fine, "Vector", v); tb.inp(fine, "Scale", 40.0); tb.inp(fine, "Detail", 6.0); tb.inp(fine, "Roughness", 0.7)
    tone = tb.math("ADD", 1.0, tb.math("MULTIPLY", tb.math("SUBTRACT", broad.outputs["Fac"], 0.5), tb.math("MULTIPLY", gi.outputs["Color Variation"], 2.0)))
    # repair patches: large voronoi cells gated by noise, darker and smoother asphalt
    pv = tb.n("ShaderNodeTexVoronoi", "patch cells", feature="F1"); tb.inp(pv, "Vector", v); tb.inp(pv, "Scale", 0.35)
    pgate = tb.n("ShaderNodeTexNoise", "patch gate"); tb.inp(pgate, "Vector", v); tb.inp(pgate, "Scale", 0.2); tb.inp(pgate, "Detail", 1.0)
    pr = tb.n("ShaderNodeValToRGB", "patch mask"); pr.color_ramp.elements[0].position = 0.45; pr.color_ramp.elements[1].position = 0.5
    tb.link(pv.outputs["Distance"], pr.inputs[0])
    patch_on = tb.math("GREATER_THAN", pgate.outputs["Fac"], tb.math("SUBTRACT", 1.0, tb.math("MULTIPLY", gi.outputs["Patch Amount"], 0.9)))
    psep = tb.n("ShaderNodeSeparateColor"); tb.link(pr.outputs[0], psep.inputs[0])
    patch = tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, psep.outputs[0]), patch_on)
    col = tb.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); tb.inp(col, "Factor", 1.0)
    tb.link(gi.outputs["Base Color"], col.inputs[6]); tb.link(tb.combine(tone, tone, tone), col.inputs[7])
    grain = tb.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); tb.inp(grain, "Factor", 0.5)
    tb.link(col.outputs[2], grain.inputs[6]); tb.link(tb.combine(tb.math("ADD", 0.7, tb.math("MULTIPLY", agg.outputs["Distance"], 0.6)), tb.math("ADD", 0.7, tb.math("MULTIPLY", agg.outputs["Distance"], 0.6)), tb.math("ADD", 0.7, tb.math("MULTIPLY", agg.outputs["Distance"], 0.6))), grain.inputs[7])
    patched = tb.n("ShaderNodeMix", data_type="RGBA"); tb.link(patch, patched.inputs[0]); tb.link(grain.outputs[2], patched.inputs[6]); patched.inputs[7].default_value = (0.045, 0.045, 0.05, 1)
    # wetness: puddles where the broad noise is low; darker everywhere, glossy in the puddles
    puddle = tb.n("ShaderNodeValToRGB", "puddle mask"); puddle.color_ramp.elements[0].position = 0.35; puddle.color_ramp.elements[1].position = 0.5
    puddle.color_ramp.elements[0].color = (1, 1, 1, 1); puddle.color_ramp.elements[1].color = (0, 0, 0, 1)
    tb.link(broad.outputs["Fac"], puddle.inputs[0])
    pud = tb.n("ShaderNodeSeparateColor"); tb.link(puddle.outputs[0], pud.inputs[0])
    wet_mask = tb.math("MULTIPLY", gi.outputs["Wetness"], tb.math("ADD", 0.45, tb.math("MULTIPLY", pud.outputs[0], 0.55)))
    darken = tb.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); tb.link(wet_mask, darken.inputs[0]); tb.link(patched.outputs[2], darken.inputs[6]); darken.inputs[7].default_value = (0.35, 0.35, 0.38, 1)
    rough = tb.math("ADD", gi.outputs["Asphalt Roughness"], tb.math("MULTIPLY", tb.math("SUBTRACT", fine.outputs["Fac"], 0.5), 0.12))
    rough = tb.math("SUBTRACT", rough, tb.math("MULTIPLY", patch, 0.15))
    rough = tb.math("SUBTRACT", rough, tb.math("MULTIPLY", wet_mask, 0.75))
    bump = tb.n("ShaderNodeBump"); tb.inp(bump, "Strength", gi.outputs["Bump Strength"]); tb.inp(bump, "Distance", 0.01)
    tb.link(tb.math("ADD", tb.math("MULTIPLY", agg.outputs["Distance"], 0.7), tb.math("MULTIPLY", fine.outputs["Fac"], 0.3)), bump.inputs["Height"])
    bsdf = tb.n("ShaderNodeBsdfPrincipled"); tb.link(darken.outputs[2], bsdf.inputs["Base Color"]); tb.link(rough, bsdf.inputs["Roughness"]); tb.link(bump.outputs[0], bsdf.inputs["Normal"])
    tb.link(bsdf.outputs[0], go.inputs[0])

    # ---- MRS_PaintShader group: paint over asphalt with wear
    g = new_tree(MRS + "PaintShader", "ShaderNodeTree")
    for nm, st, d in (("Paint Color", "NodeSocketColor", (0.85, 0.85, 0.8, 1)), ("Paint Wear", "NodeSocketFloat", 0.35), ("Asphalt Scale", "NodeSocketFloat", 1.0),
                      ("Wetness", "NodeSocketFloat", 0.0), ("Bump Strength", "NodeSocketFloat", 0.15)):
        sock(g, nm, "INPUT", st, d)
    sock(g, "BSDF", "OUTPUT", "NodeSocketShader")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    v = coord(tb, gi.outputs["Asphalt Scale"])
    wearn = tb.n("ShaderNodeTexNoise", "wear"); tb.inp(wearn, "Vector", v); tb.inp(wearn, "Scale", 3.0); tb.inp(wearn, "Detail", 6.0); tb.inp(wearn, "Roughness", 0.7)
    agg = tb.n("ShaderNodeTexVoronoi", "aggregate", feature="F1"); tb.inp(agg, "Vector", v); tb.inp(agg, "Scale", 140.0)
    wr = tb.n("ShaderNodeValToRGB", "wear mask"); tb.link(wearn.outputs["Fac"], wr.inputs[0])
    wr.color_ramp.elements[0].position = 0.35; wr.color_ramp.elements[1].position = 0.75
    wsep = tb.n("ShaderNodeSeparateColor"); tb.link(wr.outputs[0], wsep.inputs[0])
    wear = tb.math("MULTIPLY", wsep.outputs[0], tb.math("MULTIPLY", gi.outputs["Paint Wear"], 1.3))
    wear = tb.math("ADD", wear, tb.math("MULTIPLY", tb.math("SUBTRACT", 1.0, agg.outputs["Distance"]), tb.math("MULTIPLY", gi.outputs["Paint Wear"], 0.25)))
    wear = tb.math("MINIMUM", wear, 1.0)
    col = tb.n("ShaderNodeMix", data_type="RGBA"); tb.link(wear, col.inputs[0]); tb.link(gi.outputs["Paint Color"], col.inputs[6]); col.inputs[7].default_value = (0.08, 0.08, 0.085, 1)
    wet = tb.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); tb.link(tb.math("MULTIPLY", gi.outputs["Wetness"], 0.7), wet.inputs[0]); tb.link(col.outputs[2], wet.inputs[6]); wet.inputs[7].default_value = (0.5, 0.5, 0.52, 1)
    rough = tb.math("SUBTRACT", tb.math("ADD", 0.55, tb.math("MULTIPLY", wear, 0.35)), tb.math("MULTIPLY", gi.outputs["Wetness"], 0.5))
    bump = tb.n("ShaderNodeBump"); tb.inp(bump, "Strength", gi.outputs["Bump Strength"]); tb.inp(bump, "Distance", 0.004)
    tb.link(tb.math("SUBTRACT", 1.0, wear), bump.inputs["Height"])
    bsdf = tb.n("ShaderNodeBsdfPrincipled"); tb.link(wet.outputs[2], bsdf.inputs["Base Color"]); tb.link(rough, bsdf.inputs["Roughness"]); tb.link(bump.outputs[0], bsdf.inputs["Normal"])
    tb.link(bsdf.outputs[0], go.inputs[0])

    # ---- MRS_ConcreteShader group: curbs and sidewalks
    g = new_tree(MRS + "ConcreteShader", "ShaderNodeTree")
    for nm, st, d in (("Concrete Variation", "NodeSocketFloat", 0.2), ("Asphalt Scale", "NodeSocketFloat", 1.0), ("Wetness", "NodeSocketFloat", 0.0),
                      ("Base Color", "NodeSocketColor", (0.52, 0.51, 0.49, 1)), ("Slab Size", "NodeSocketFloat", 1.5), ("Bump Strength", "NodeSocketFloat", 0.3)):
        sock(g, nm, "INPUT", st, d)
    sock(g, "BSDF", "OUTPUT", "NodeSocketShader")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    v = coord(tb, gi.outputs["Asphalt Scale"])
    broad = tb.n("ShaderNodeTexNoise", "broad"); tb.inp(broad, "Vector", v); tb.inp(broad, "Scale", 0.3); tb.inp(broad, "Detail", 3.0)
    fine = tb.n("ShaderNodeTexNoise", "pores"); tb.inp(fine, "Vector", v); tb.inp(fine, "Scale", 60.0); tb.inp(fine, "Detail", 5.0); tb.inp(fine, "Roughness", 0.7)
    sep = tb.n("ShaderNodeSeparateXYZ"); tb.link(v, sep.inputs[0])
    # slab joints every Slab Size metres (along x and y of object space)
    jx = tb.math("ABSOLUTE", tb.math("SUBTRACT", tb.math("FRACT", tb.math("DIVIDE", sep.outputs[0], gi.outputs["Slab Size"])), 0.5))
    jy = tb.math("ABSOLUTE", tb.math("SUBTRACT", tb.math("FRACT", tb.math("DIVIDE", sep.outputs[1], gi.outputs["Slab Size"])), 0.5))
    joint = tb.math("LESS_THAN", tb.math("MINIMUM", tb.math("SUBTRACT", 0.5, jx), tb.math("SUBTRACT", 0.5, jy)), 0.006)
    tone = tb.math("ADD", 1.0, tb.math("MULTIPLY", tb.math("SUBTRACT", broad.outputs["Fac"], 0.5), tb.math("MULTIPLY", gi.outputs["Concrete Variation"], 2.0)))
    tone = tb.math("SUBTRACT", tone, tb.math("MULTIPLY", joint, 0.35))
    col = tb.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); tb.inp(col, "Factor", 1.0); tb.link(gi.outputs["Base Color"], col.inputs[6]); tb.link(tb.combine(tone, tone, tone), col.inputs[7])
    wet = tb.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY"); tb.link(tb.math("MULTIPLY", gi.outputs["Wetness"], 0.8), wet.inputs[0]); tb.link(col.outputs[2], wet.inputs[6]); wet.inputs[7].default_value = (0.45, 0.45, 0.47, 1)
    rough = tb.math("SUBTRACT", tb.math("ADD", 0.85, tb.math("MULTIPLY", tb.math("SUBTRACT", fine.outputs["Fac"], 0.5), 0.1)), tb.math("MULTIPLY", gi.outputs["Wetness"], 0.6))
    bump = tb.n("ShaderNodeBump"); tb.inp(bump, "Strength", gi.outputs["Bump Strength"]); tb.inp(bump, "Distance", 0.01)
    tb.link(tb.math("SUBTRACT", fine.outputs["Fac"], tb.math("MULTIPLY", joint, 0.8)), bump.inputs["Height"])
    bsdf = tb.n("ShaderNodeBsdfPrincipled"); tb.link(wet.outputs[2], bsdf.inputs["Base Color"]); tb.link(rough, bsdf.inputs["Roughness"]); tb.link(bump.outputs[0], bsdf.inputs["Normal"])
    tb.link(bsdf.outputs[0], go.inputs[0])

    mats = {}
    for name, grp in (("Asphalt", "AsphaltShader"), ("Paint", "PaintShader"), ("Concrete", "ConcreteShader")):
        m = _mat(MRS + name); nt = m.node_tree
        gnode = nt.nodes.new("ShaderNodeGroup"); gnode.node_tree = bpy.data.node_groups[MRS + grp]; gnode.name = "MRS"; gnode.label = MRS + grp
        out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
        nt.links.new(gnode.outputs[0], out.inputs["Surface"])
        mats[name] = m
    return mats


def apply_material_preset(name):
    """dry / wet on the three road materials (the Wetness input of their shader groups)."""
    w = MATERIAL_PRESETS[name]["wetness"]
    for m in (MRS + "Asphalt", MRS + "Paint", MRS + "Concrete"):
        node = bpy.data.materials[m].node_tree.nodes.get("MRS")
        if node: node.inputs["Wetness"].default_value = w


# ============================================================================== the road group
INPUTS = [  # (name, socket type, default, min, max, description)
    ("Lanes", "NodeSocketInt", 2, 1, 8, "Number of traffic lanes"),
    ("Lane Width", "NodeSocketFloat", 3.2, 2.0, 6.0, "Width of one lane (m)"),
    ("Shoulder", "NodeSocketFloat", 0.0, 0.0, 3.0, "Paved shoulder each side (m)"),
    ("Median", "NodeSocketFloat", 0.0, 0.0, 6.0, "Raised median width (0 = none)"),
    ("Sidewalk Left", "NodeSocketBool", True, None, None, ""), ("Sidewalk Right", "NodeSocketBool", True, None, None, ""),
    ("Sidewalk Width Left", "NodeSocketFloat", 2.0, 0.5, 8.0, ""), ("Sidewalk Width Right", "NodeSocketFloat", 2.0, 0.5, 8.0, ""),
    ("Sidewalk Height", "NodeSocketFloat", 0.15, 0.05, 0.3, "Curb / sidewalk height (m)"),
    ("Curb Width", "NodeSocketFloat", 0.25, 0.1, 0.6, "Curb stone width (m)"),
    ("Resolution", "NodeSocketFloat", 1.0, 0.2, 10.0, "Curve sampling step (m)"),
    ("Centre Line", "NodeSocketInt", 2, 0, 3, "0 none, 1 solid, 2 dashed, 3 double solid"),
    ("Lane Lines", "NodeSocketBool", True, None, None, "Dashed lines between lanes"),
    ("Edge Lines", "NodeSocketBool", False, None, None, "Solid edge lines"),
    ("Marking Width", "NodeSocketFloat", 0.12, 0.05, 0.4, ""), ("Dash Length", "NodeSocketFloat", 3.0, 0.3, 12.0, ""), ("Dash Gap", "NodeSocketFloat", 6.0, 0.3, 20.0, ""),
    ("Marking Material", "NodeSocketMaterial", None, None, None, ""), ("Asphalt Material", "NodeSocketMaterial", None, None, None, ""),
    ("Concrete Material", "NodeSocketMaterial", None, None, None, ""),
    ("Trim Start", "NodeSocketFloat", 0.0, 0.0, 200.0, "Length cut off at the start (set by junctions)"),
    ("Trim End", "NodeSocketFloat", 0.0, 0.0, 200.0, "Length cut off at the end (set by junctions)"),
    ("Props", "NodeSocketCollection", None, None, None, "Collection of roadside props (one is picked per point)"),
    ("Prop Spacing", "NodeSocketFloat", 28.0, 2.0, 200.0, ""), ("Prop Offset", "NodeSocketFloat", 0.5, 0.0, 10.0, "Lateral offset behind the curb (m)"),
    ("Prop Side", "NodeSocketInt", 2, 0, 2, "0 left, 1 right, 2 both (alternating)"), ("Prop Seed", "NodeSocketInt", 0, 0, 10000, ""),
    ("Prop Clear", "NodeSocketFloat", 6.0, 0.0, 60.0, "No props this far from a trimmed end (junctions, crosswalks)"),
    ("Manholes", "NodeSocketCollection", None, None, None, ""), ("Manhole Spacing", "NodeSocketFloat", 45.0, 5.0, 300.0, ""),
    ("Realize Instances", "NodeSocketBool", False, None, None, "For export: props become real geometry"),
    ("Collision Only", "NodeSocketBool", False, None, None, "For export: only the drivable / walkable surfaces"),
]


def build_road_group():
    g = new_tree(MRS + "Road")
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    for nm, st, d, lo, hi, desc in INPUTS: sock(g, nm, "INPUT", st, d, lo, hi, desc)
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    tb = T(g)
    gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput")
    I = lambda k: gi.outputs[k]

    # ---------------------------------------------------------------- Road_Profile (widths)
    tb.frame_("Road_Profile: widths from the inputs")
    half_carr = tb.math("ADD", tb.math("MULTIPLY", tb.math("MULTIPLY", I("Lanes"), I("Lane Width")), 0.5), tb.math("ADD", I("Shoulder"), tb.math("MULTIPLY", I("Median"), 0.5)))
    curb_out = tb.math("ADD", half_carr, I("Curb Width"))
    sw_l_out = tb.math("ADD", curb_out, I("Sidewalk Width Left")); sw_r_out = tb.math("ADD", curb_out, I("Sidewalk Width Right"))
    H = I("Sidewalk Height")

    # ---------------------------------------------------------------- the rail: resampled, trimmed, with "along"
    tb.frame_("Road_Rail: trim, resample, along-length attribute, side vector")
    clen = tb.n("GeometryNodeCurveLength"); tb.inp(clen, "Curve", I("Geometry"))
    trim = tb.n("GeometryNodeTrimCurve", mode="LENGTH"); tb.inp(trim, "Curve", I("Geometry"))
    tb.inp(trim, "Start_001", I("Trim Start")); tb.inp(trim, "End_001", tb.math("SUBTRACT", clen.outputs[0], I("Trim End")))
    res = tb.n("GeometryNodeResampleCurve"); tb.inp(res, "Curve", trim.outputs[0])
    try: res.inputs["Mode"].default_value = "Length"
    except Exception: res.mode = "LENGTH"
    tb.inp(res, "Length", I("Resolution"))
    normal_mode = tb.n("GeometryNodeSetCurveNormal"); tb.inp(normal_mode, "Curve", res.outputs[0])
    for attempt in ("Z Up", "Z_UP", "ZUp"):
        try:
            if "Mode" in normal_mode.inputs: normal_mode.inputs["Mode"].default_value = attempt
            elif hasattr(normal_mode, "mode"): normal_mode.mode = attempt
            break
        except Exception:
            continue
    sp = tb.n("GeometryNodeSplineParameter")
    along = tb.n("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT"); tb.inp(along, "Geometry", normal_mode.outputs[0]); tb.inp(along, "Name", "along"); tb.inp(along, "Value", sp.outputs["Length"])
    rail = along.outputs[0]

    # ---------------------------------------------------------------- strips: a Curve Line profile (x = lateral, z = up) swept along the rail
    tb.frame_("Road_Surface + Sidewalks_Curbs: one Curve to Mesh per strip")
    def strip(x0, z0, x1, z1, material, label, flip=False):
        line = tb.n("GeometryNodeCurvePrimitiveLine", label)
        tb.inp(line, "Start", tb.combine(x0, 0.0, z0)); tb.inp(line, "End", tb.combine(x1, 0.0, z1))
        pos = tb.n("GeometryNodeInputPosition")
        sx = tb.n("ShaderNodeSeparateXYZ"); tb.link(pos.outputs[0], sx.inputs[0])
        lat = tb.n("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT"); tb.inp(lat, "Geometry", line.outputs[0]); tb.inp(lat, "Name", "lat"); tb.inp(lat, "Value", sx.outputs[0])
        c2m = tb.n("GeometryNodeCurveToMesh"); tb.inp(c2m, "Curve", rail); tb.inp(c2m, "Profile Curve", lat.outputs[0])
        geo = c2m.outputs[0]
        if flip:
            ff = tb.n("GeometryNodeFlipFaces"); tb.inp(ff, "Mesh", geo); geo = ff.outputs[0]
        sm = tb.n("GeometryNodeSetMaterial"); tb.inp(sm, "Geometry", geo); tb.inp(sm, "Material", material)
        return sm.outputs[0]
    neg = lambda s: tb.math("MULTIPLY", s, -1.0)
    parts = {}
    parts["asphalt"] = strip(neg(half_carr), 0.0, half_carr, 0.0, I("Asphalt Material"), "asphalt")
    # curbs: vertical face + top, both sides (profile goes outwards)
    curb_top = H
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        x_in = tb.math("MULTIPLY", half_carr, sgn); x_out = tb.math("MULTIPLY", curb_out, sgn)
        face = strip(x_in, 0.0, x_in, curb_top, I("Concrete Material"), "curb face " + side, flip=(sgn > 0))
        top = strip(x_in, curb_top, x_out, curb_top, I("Concrete Material"), "curb top " + side, flip=(sgn > 0))
        parts["curb" + side] = (face, top)
    # sidewalks: top slab + outer edge face, switched by the Sidewalk Left / Right booleans
    for side, sgn, on, outer in (("L", -1.0, I("Sidewalk Left"), sw_l_out), ("R", 1.0, I("Sidewalk Right"), sw_r_out)):
        x0 = tb.math("MULTIPLY", curb_out, sgn); x1 = tb.math("MULTIPLY", outer, sgn)
        top = strip(x0, H, x1, H, I("Concrete Material"), "sidewalk " + side, flip=(sgn > 0))
        edge = strip(x1, H, x1, 0.0, I("Concrete Material"), "sidewalk edge " + side, flip=(sgn > 0))
        j = tb.n("GeometryNodeJoinGeometry"); tb.link(top, j.inputs[0]); tb.link(edge, j.inputs[0])
        parts["sidewalk" + side] = tb.switch(on, tb.n("GeometryNodeJoinGeometry").outputs[0], j.outputs[0], "GEOMETRY")
    # median: raised strip in the middle when Median > 0
    med_half = tb.math("MULTIPLY", I("Median"), 0.5)
    med = tb.n("GeometryNodeJoinGeometry")
    for a, b, c, d, fl in ((neg(med_half), 0.0, neg(med_half), H, False), (neg(med_half), H, med_half, H, False), (med_half, H, med_half, 0.0, False)):
        tb.link(strip(a, b, c, d, I("Concrete Material"), "median", flip=fl), med.inputs[0])
    parts["median"] = tb.switch(tb.compare("GREATER_THAN", I("Median"), 0.05), tb.n("GeometryNodeJoinGeometry").outputs[0], med.outputs[0], "GEOMETRY")

    # ---------------------------------------------------------------- markings
    tb.frame_("Road_Markings: thin strips at lateral offsets, dashes cut by 'along'")
    mw2 = tb.math("MULTIPLY", I("Marking Width"), 0.5)
    zpaint = 0.004
    def marking(xc, dashed, label):
        geo = strip(tb.math("SUBTRACT", xc, mw2), zpaint, tb.math("ADD", xc, mw2), zpaint, I("Marking Material"), label)
        if dashed is None: return geo
        along_attr = tb.n("GeometryNodeInputNamedAttribute", data_type="FLOAT"); tb.inp(along_attr, "Name", "along")
        period = tb.math("ADD", I("Dash Length"), I("Dash Gap"))
        phase = tb.math("MODULO", along_attr.outputs[0], period)
        gap_sel = tb.compare("GREATER_THAN", phase, I("Dash Length"))
        delete = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(delete, "Geometry", geo); tb.inp(delete, "Selection", tb.boolean("AND", gap_sel, dashed))
        return delete.outputs[0]
    marks = tb.n("GeometryNodeJoinGeometry")
    centre = I("Centre Line")
    is_dashed = tb.compare("EQUAL", centre, 2, "INT")
    c_single = marking(tb.math("MULTIPLY", med_half, 0.0), is_dashed, "centre line")
    c_double_l = marking(tb.math("SUBTRACT", neg(med_half), tb.math("MULTIPLY", I("Marking Width"), 1.0)), tb.boolean("AND", False, False), "double centre L")
    c_double_r = marking(tb.math("ADD", med_half, tb.math("MULTIPLY", I("Marking Width"), 1.0)), tb.boolean("AND", False, False), "double centre R")
    dbl = tb.n("GeometryNodeJoinGeometry"); tb.link(c_double_l, dbl.inputs[0]); tb.link(c_double_r, dbl.inputs[0])
    has_median = tb.compare("GREATER_THAN", I("Median"), 0.05)
    single_or_double = tb.switch(tb.compare("EQUAL", centre, 3, "INT"), c_single, dbl.outputs[0], "GEOMETRY")
    centre_geo = tb.switch(tb.boolean("OR", tb.compare("EQUAL", centre, 0, "INT"), has_median), single_or_double, tb.n("GeometryNodeJoinGeometry").outputs[0], "GEOMETRY")
    tb.link(centre_geo, marks.inputs[0])
    # lane lines: for lane k = 1..3 each side of the centre at med_half + k * lane width (only when k < lanes/2)
    lanes_per_side = tb.math("DIVIDE", I("Lanes"), 2.0)
    for k in (1, 2, 3):
        for sgn in (-1.0, 1.0):
            x = tb.math("MULTIPLY", tb.math("ADD", med_half, tb.math("MULTIPLY", I("Lane Width"), float(k))), sgn)
            geo = marking(x, tb.boolean("AND", True, True), "lane line %d" % k)
            on = tb.boolean("AND", I("Lane Lines"), tb.compare("LESS_THAN", float(k), lanes_per_side))
            tb.link(tb.switch(on, tb.n("GeometryNodeJoinGeometry").outputs[0], geo, "GEOMETRY"), marks.inputs[0])
    for sgn in (-1.0, 1.0):
        x = tb.math("MULTIPLY", tb.math("SUBTRACT", half_carr, tb.math("ADD", I("Marking Width"), 0.1)), sgn)
        geo = marking(x, None, "edge line")
        tb.link(tb.switch(I("Edge Lines"), tb.n("GeometryNodeJoinGeometry").outputs[0], geo, "GEOMETRY"), marks.inputs[0])

    # ---------------------------------------------------------------- roadside props and manholes
    tb.frame_("Roadside_Instances: Curve to Points, side vector, collection pick, align to tangent")
    def points_along(spacing, clear):
        # a shorter rail for props: trimmed further by Prop Clear at both ends
        clen2 = tb.n("GeometryNodeCurveLength"); tb.inp(clen2, "Curve", rail)
        t2 = tb.n("GeometryNodeTrimCurve", mode="LENGTH"); tb.inp(t2, "Curve", rail)
        tb.inp(t2, "Start_001", clear); tb.inp(t2, "End_001", tb.math("SUBTRACT", clen2.outputs[0], clear))
        c2p = tb.n("GeometryNodeCurveToPoints", mode="LENGTH"); tb.inp(c2p, "Curve", t2.outputs[0]); tb.inp(c2p, "Length", spacing)
        side = tb.vmath("NORMALIZE", tb.vmath("CROSS_PRODUCT", c2p.outputs["Tangent"], (0.0, 0.0, 1.0)))
        return c2p, side
    c2p, side = points_along(I("Prop Spacing"), I("Prop Clear"))
    idx = tb.n("GeometryNodeInputIndex")
    alt = tb.math("MODULO", idx.outputs[0], 2.0)                       # 0,1,0,1: alternate sides
    sgn_sel = tb.switch(tb.compare("EQUAL", I("Prop Side"), 2, "INT"), tb.switch(tb.compare("EQUAL", I("Prop Side"), 0, "INT"), 1.0, -1.0), tb.math("SUBTRACT", tb.math("MULTIPLY", alt, 2.0), 1.0))
    off_l = tb.math("ADD", sw_l_out, I("Prop Offset")); off_r = tb.math("ADD", sw_r_out, I("Prop Offset"))
    # props stand on the sidewalk when there is one, else on the verge beyond the curb
    # with a sidewalk: Prop Offset behind the curb on the slab; without: on the verge, 0.6 m further out
    dist_l = tb.switch(I("Sidewalk Left"), tb.math("ADD", curb_out, tb.math("ADD", I("Prop Offset"), 0.6)), tb.math("ADD", curb_out, I("Prop Offset")), "FLOAT")
    dist_r = tb.switch(I("Sidewalk Right"), tb.math("ADD", curb_out, tb.math("ADD", I("Prop Offset"), 0.6)), tb.math("ADD", curb_out, I("Prop Offset")), "FLOAT")
    dist = tb.switch(tb.compare("LESS_THAN", sgn_sel, 0.0), dist_r, dist_l, "FLOAT")
    up_l = tb.switch(I("Sidewalk Left"), 0.0, H, "FLOAT"); up_r = tb.switch(I("Sidewalk Right"), 0.0, H, "FLOAT")
    up = tb.switch(tb.compare("LESS_THAN", sgn_sel, 0.0), up_r, up_l, "FLOAT")
    offset = tb.vmath("ADD", tb.vmath("SCALE", side, scale=tb.math("MULTIPLY", dist, sgn_sel)), tb.combine(0.0, 0.0, up))
    moved = tb.n("GeometryNodeSetPosition"); tb.inp(moved, "Geometry", c2p.outputs["Points"]); tb.inp(moved, "Offset", offset)
    coll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(coll, "Collection", I("Props")); tb.inp(coll, "Separate Children", True); tb.inp(coll, "Reset Children", True)
    rnd = tb.n("FunctionNodeRandomValue", data_type="INT"); tb.inp(rnd, "Min", 0); tb.inp(rnd, "Max", 100); tb.inp(rnd, "Seed", I("Prop Seed"))
    align = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(align, "Vector", c2p.outputs["Tangent"])
    # face the road: rotate so the prop's +Y (its front) looks across the road = -side * sgn
    facing = tb.vmath("SCALE", side, scale=tb.math("MULTIPLY", sgn_sel, -1.0))
    align2 = tb.n("FunctionNodeAlignRotationToVector", axis="Y", pivot_axis="Z"); tb.inp(align2, "Vector", facing)
    iop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(iop, "Points", moved.outputs[0]); tb.inp(iop, "Instance", coll.outputs[0])
    tb.inp(iop, "Pick Instance", True); tb.inp(iop, "Instance Index", rnd.outputs[2] if len(rnd.outputs) > 2 else rnd.outputs[0]); tb.inp(iop, "Rotation", align2.outputs[0])
    props_geo = iop.outputs[0]
    # manholes: on the carriageway, random lateral position within the right lane, flat on the asphalt
    c2m_pts, side_m = points_along(I("Manhole Spacing"), tb.math("ADD", I("Prop Clear"), 4.0))
    rndf = tb.n("FunctionNodeRandomValue", data_type="FLOAT"); tb.inp(rndf, "Min", 0.3); tb.inp(rndf, "Max", 0.8); tb.inp(rndf, "Seed", tb.math("ADD", I("Prop Seed"), 7))
    moff = tb.vmath("SCALE", side_m, scale=tb.math("MULTIPLY", rndf.outputs[1] if len(rndf.outputs) > 1 else rndf.outputs[0], tb.math("MULTIPLY", I("Lane Width"), 1.0)))
    mp = tb.n("GeometryNodeSetPosition"); tb.inp(mp, "Geometry", c2m_pts.outputs["Points"]); tb.inp(mp, "Offset", tb.vmath("ADD", moff, (0.0, 0.0, 0.003)))
    mcoll = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(mcoll, "Collection", I("Manholes")); tb.inp(mcoll, "Separate Children", True); tb.inp(mcoll, "Reset Children", True)
    miop = tb.n("GeometryNodeInstanceOnPoints"); tb.inp(miop, "Points", mp.outputs[0]); tb.inp(miop, "Instance", mcoll.outputs[0]); tb.inp(miop, "Pick Instance", True)
    tb.inp(miop, "Instance Index", rnd.outputs[2] if len(rnd.outputs) > 2 else rnd.outputs[0])
    inst = tb.n("GeometryNodeJoinGeometry"); tb.link(props_geo, inst.inputs[0]); tb.link(miop.outputs[0], inst.inputs[0])
    realized = tb.n("GeometryNodeRealizeInstances"); tb.inp(realized, "Geometry", inst.outputs[0])
    instances_out = tb.switch(I("Realize Instances"), inst.outputs[0], realized.outputs[0], "GEOMETRY")

    # ---------------------------------------------------------------- assembly, UVs, collision switch
    tb.frame_("Road_Materials + UVMap (lateral, along) + output")
    surf = tb.n("GeometryNodeJoinGeometry")
    for key in ("asphalt", "median"): tb.link(parts[key], surf.inputs[0])
    for key in ("curbL", "curbR"):
        for geo in parts[key]: tb.link(geo, surf.inputs[0])
    for key in ("sidewalkL", "sidewalkR"): tb.link(parts[key], surf.inputs[0])
    full = tb.n("GeometryNodeJoinGeometry"); tb.link(surf.outputs[0], full.inputs[0]); tb.link(marks.outputs[0], full.inputs[0])
    mesh = tb.switch(I("Collision Only"), full.outputs[0], surf.outputs[0], "GEOMETRY")
    lat_a = tb.n("GeometryNodeInputNamedAttribute", data_type="FLOAT"); tb.inp(lat_a, "Name", "lat")
    alo_a = tb.n("GeometryNodeInputNamedAttribute", data_type="FLOAT"); tb.inp(alo_a, "Name", "along")
    uv = tb.n("GeometryNodeStoreNamedAttribute", data_type="FLOAT2", domain="CORNER"); tb.inp(uv, "Geometry", mesh); tb.inp(uv, "Name", "UVMap")
    tb.inp(uv, "Value", tb.combine(lat_a.outputs[0], alo_a.outputs[0], 0.0))
    smooth = tb.n("GeometryNodeSetShadeSmooth"); tb.inp(smooth, "Geometry", uv.outputs[0]); tb.inp(smooth, "Shade Smooth", False)
    out = tb.n("GeometryNodeJoinGeometry"); tb.link(smooth.outputs[0], out.inputs[0])
    tb.link(tb.switch(I("Collision Only"), instances_out, tb.n("GeometryNodeJoinGeometry").outputs[0], "GEOMETRY"), out.inputs[0])
    tb.link(out.outputs[0], go.inputs[0])
    return g


# ============================================================================== placeholder props
def _box(bm, x0, y0, z0, x1, y1, z1):
    v = [bm.verts.new((x, y, z)) for x, y, z in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)): bm.faces.new([v[i] for i in f])


def _cyl(bm, x, y, z0, z1, r0, r1, n=10):
    a = [bm.verts.new((x + r0 * math.cos(2 * math.pi * k / n), y + r0 * math.sin(2 * math.pi * k / n), z0)) for k in range(n)]
    b = [bm.verts.new((x + r1 * math.cos(2 * math.pi * k / n), y + r1 * math.sin(2 * math.pi * k / n), z1)) for k in range(n)]
    for k in range(n): bm.faces.new([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]])
    bm.faces.new(b)


def placeholder_props(collection_name=MRS + "Props"):
    """Original placeholder props (streetlight, bollard, barrier, tree, sign, bench) in a collection the
    road group instances from; replace them with real assets by swapping the collection's objects."""
    col = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    for o in list(col.objects): bpy.data.objects.remove(o)
    metal = bpy.data.materials.get(MRS + "PropMetal") or bpy.data.materials.new(MRS + "PropMetal"); metal.diffuse_color = (0.2, 0.21, 0.22, 1)
    green = bpy.data.materials.get(MRS + "PropGreen") or bpy.data.materials.new(MRS + "PropGreen"); green.diffuse_color = (0.2, 0.4, 0.15, 1)
    wood = bpy.data.materials.get(MRS + "PropWood") or bpy.data.materials.new(MRS + "PropWood"); wood.diffuse_color = (0.45, 0.3, 0.18, 1)
    def make(name, builder, mat):
        bm = bmesh.new(); builder(bm); me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat)
        o = bpy.data.objects.new(name, me); col.objects.link(o); o.hide_render = True; o.hide_viewport = True; return o
    def streetlight(bm):
        _cyl(bm, 0, 0, 0, 0.5, 0.18, 0.15); _cyl(bm, 0, 0, 0.5, 8.0, 0.1, 0.06); _box(bm, -0.05, 0.0, 7.9, 0.05, 2.2, 8.0); _box(bm, -0.22, 1.8, 7.8, 0.22, 2.6, 8.05)
    def bollard(bm): _cyl(bm, 0, 0, 0, 0.9, 0.09, 0.09); _cyl(bm, 0, 0, 0.9, 1.0, 0.1, 0.06)
    def barrier(bm): _box(bm, -1.0, -0.12, 0.0, 1.0, 0.12, 0.45); _box(bm, -1.05, -0.08, 0.45, 1.05, 0.08, 0.8)
    def tree(bm):
        _cyl(bm, 0, 0, 0, 3.0, 0.16, 0.12, 8)
        for z, r in ((3.0, 2.2), (4.6, 1.7), (6.0, 1.0)): _cyl(bm, 0, 0, z, z + 1.8, r, r * 0.35, 9)
    def sign(bm): _cyl(bm, 0, 0, 0, 2.6, 0.04, 0.04, 6); _box(bm, -0.3, -0.02, 2.0, 0.3, 0.02, 2.6)
    def bench(bm): _box(bm, -0.9, -0.25, 0.42, 0.9, 0.25, 0.47); _box(bm, -0.9, -0.3, 0.47, 0.9, -0.22, 0.9); _box(bm, -0.8, -0.28, 0.0, -0.72, 0.25, 0.42); _box(bm, 0.72, -0.28, 0.0, 0.8, 0.25, 0.42)
    for nm, fn, m in (("MRS_Streetlight", streetlight, metal), ("MRS_Bollard", bollard, metal), ("MRS_Barrier", barrier, metal), ("MRS_Tree", tree, green), ("MRS_Sign", sign, metal), ("MRS_Bench", bench, wood)):
        make(nm, fn, m)
    mcol = bpy.data.collections.get(MRS + "Manholes") or bpy.data.collections.new(MRS + "Manholes")
    if mcol.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(mcol)
    for o in list(mcol.objects): bpy.data.objects.remove(o)
    bm = bmesh.new(); _cyl(bm, 0, 0, 0.0, 0.015, 0.33, 0.33, 16); me = bpy.data.meshes.new("MRS_Manhole"); bm.to_mesh(me); bm.free(); me.materials.append(metal)
    o = bpy.data.objects.new("MRS_Manhole", me); mcol.objects.link(o); o.hide_render = True; o.hide_viewport = True
    return col, mcol


# ============================================================================== roads
def _curve_object(name, points, collection, cyclic=False):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.resolution_u = 12
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = Vector(p); bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, cu); collection.objects.link(o)
    return o


def make_road(name, points, collection, preset="residential", **overrides):
    """A road object: a Bezier curve through `points` with the MRS_Road modifier and a preset."""
    o = _curve_object(name, points, collection)
    add_road_modifier(o, preset, **overrides)
    return o


def add_road_modifier(o, preset="residential", **overrides):
    mod = o.modifiers.get("MRS_Road") or o.modifiers.new("MRS_Road", "NODES")
    mod.node_group = bpy.data.node_groups[MRS + "Road"]
    set_road(o, preset, **overrides)
    o["mrs_preset"] = preset
    return mod


def _item(mod, name):
    return next(i for i in mod.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT" and i.name == name)


def _set_input(mod, name, value):
    """Modifier input by socket name. Blender 5.x: mod.properties.inputs.<identifier>.value;
    older: the id-property mod[identifier]."""
    ident = _item(mod, name).identifier
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        entry = getattr(props.inputs, ident, None)
        if entry is None:
            try: entry = props.inputs[ident]
            except Exception: entry = None
        if entry is not None:
            entry.value = value; return
    mod[ident] = value


def set_road(o, preset=None, **overrides):
    mod = o.modifiers["MRS_Road"]
    vals = dict(PRESETS[preset]) if preset else {}
    vals.update(overrides)
    keymap = {"lanes": "Lanes", "lane_width": "Lane Width", "shoulder": "Shoulder", "median": "Median", "sidewalk_l": "Sidewalk Left", "sidewalk_r": "Sidewalk Right",
              "sidewalk_w": ("Sidewalk Width Left", "Sidewalk Width Right"), "sidewalk_h": "Sidewalk Height", "curb_w": "Curb Width", "centre": "Centre Line",
              "edge_lines": "Edge Lines", "dash": "Dash Length", "gap": "Dash Gap", "marking_w": "Marking Width", "prop_spacing": "Prop Spacing", "prop_offset": "Prop Offset"}
    for k, v in vals.items():
        names = keymap.get(k, k)
        for nm in (names if isinstance(names, tuple) else (names,)): _set_input(mod, nm, v)
    _set_input(mod, "Asphalt Material", bpy.data.materials[MRS + "Asphalt"]); _set_input(mod, "Marking Material", bpy.data.materials[MRS + "Paint"])
    _set_input(mod, "Concrete Material", bpy.data.materials[MRS + "Concrete"])
    if bpy.data.collections.get(MRS + "Props"): _set_input(mod, "Props", bpy.data.collections[MRS + "Props"])
    if bpy.data.collections.get(MRS + "Manholes"): _set_input(mod, "Manholes", bpy.data.collections[MRS + "Manholes"])
    o.update_tag()


def road_input(o, name):
    mod = o.modifiers["MRS_Road"]
    item = _item(mod, name)
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        entry = getattr(props.inputs, item.identifier, None)
        if entry is not None: return entry.value
    v = mod.get(item.identifier)
    return v if v is not None else item.default_value


def road_widths(o):
    lanes, lw, sh, med = road_input(o, "Lanes"), road_input(o, "Lane Width"), road_input(o, "Shoulder"), road_input(o, "Median")
    half = lanes * lw / 2 + sh + med / 2
    curb = road_input(o, "Curb Width")
    swl = road_input(o, "Sidewalk Width Left") if road_input(o, "Sidewalk Left") else 0.0
    swr = road_input(o, "Sidewalk Width Right") if road_input(o, "Sidewalk Right") else 0.0
    return dict(half=half, curb=curb, swl=swl, swr=swr, h=road_input(o, "Sidewalk Height"))


def road_ends(o):
    """World-space end points and outward tangents of the road's curve: [(point, tangent_away, is_start)]."""
    sp = o.data.splines[0]
    M = o.matrix_world
    pts = [M @ bp.co for bp in sp.bezier_points] if sp.type == "BEZIER" else [M @ Vector(p.co[:3]) for p in sp.points]
    if sp.type == "BEZIER":
        h0 = M @ sp.bezier_points[0].handle_right; h1 = M @ sp.bezier_points[-1].handle_left
        t0 = (h0 - pts[0]); t1 = (h1 - pts[-1])
        if t0.length < 1e-6: t0 = pts[1] - pts[0]
        if t1.length < 1e-6: t1 = pts[-2] - pts[-1]
    else:
        t0 = pts[1] - pts[0]; t1 = pts[-2] - pts[-1]
    return [(pts[0], t0.normalized(), True), (pts[-1], t1.normalized(), False)]


# ============================================================================== junctions
def _line_x(p, d, q, e):
    den = d.x * e.y - d.y * e.x
    if abs(den) < 1e-9: return None
    t = ((q.x - p.x) * e.y - (q.y - p.y) * e.x) / den
    return p + d * t


def build_junction(name, at, roads, collection, crosswalks=True, stop_lines=True, snap=0.6):
    """Connect the road ends that lie within `snap` of `at`. Trims the roads, builds the junction
    surface, sidewalk corners, crosswalks and stop lines. Returns the junction object or raises
    ValueError for unsupported layouts (not 2-4 roads, angles under 50 degrees, height mismatch)."""
    at = Vector(at)
    approaches = []
    for r in roads:
        for p, t, is_start in road_ends(r):
            if (p - at).length <= snap:
                w = road_widths(r)
                approaches.append(dict(road=r, p=p, d=Vector((t.x, t.y, 0)).normalized(), start=is_start, **w))
    if not 2 <= len(approaches) <= 4:
        raise ValueError("%s: %d road ends at the junction point; 2-4 are supported" % (name, len(approaches)))
    zs = [a["p"].z for a in approaches]
    if max(zs) - min(zs) > 0.05: raise ValueError("%s: road ends differ in height by %.2f m (max 0.05)" % (name, max(zs) - min(zs)))
    approaches.sort(key=lambda a: math.atan2(a["d"].y, a["d"].x))
    n = len(approaches)
    for i in range(n):
        a, b = approaches[i], approaches[(i + 1) % n]
        ang = math.degrees(math.acos(max(-1.0, min(1.0, a["d"].dot(b["d"])))))
        if ang < 50.0: raise ValueError("%s: roads %s and %s meet at %.0f degrees (min 50)" % (name, a["road"].name, b["road"].name, ang))
    up = Vector((0, 0, 1))
    # corners between consecutive approaches: the asphalt edges intersect at C; curbs/sidewalks follow outwards
    corners = []
    for i in range(n):
        a, b = approaches[i], approaches[(i + 1) % n]
        la = a["d"].cross(up).normalized(); lb = b["d"].cross(up).normalized()      # right-hand side vectors of each outgoing direction
        # a's left edge (looking out) is at -la ... counter-clockwise order: a's left edge meets b's right edge
        swa, swb = a["swl"], b["swr"]
        def corner(offa, offb):
            c = _line_x(at - la * offa, a["d"], at + lb * offb, b["d"])
            # a straight-through pair (parallel edges): the corner is the edge point at the junction centre
            return c if c is not None else at - la * max(offa, offb)
        C = corner(a["half"], b["half"])
        Ck = corner(a["half"] + a["curb"], b["half"] + b["curb"])
        Cs = corner(a["half"] + a["curb"] + swa, b["half"] + b["curb"] + swb)
        corners.append(dict(C=C, Ck=Ck, Cs=Cs, a=a, b=b, la=la, lb=lb))
    # trim each approach to just past the furthest corner it touches
    for i, a in enumerate(approaches):
        cs = [corners[i - 1]["Cs"], corners[i]["Cs"]]
        trim = max((c - at).dot(a["d"]) for c in cs) + 0.4
        a["trim"] = max(trim, a["half"] + 1.0)
        _set_input(a["road"].modifiers["MRS_Road"], "Trim Start" if a["start"] else "Trim End", a["trim"])
        _set_input(a["road"].modifiers["MRS_Road"], "Prop Clear", a["trim"] + 7.0)
        a["road"].update_tag()
    # the junction surface polygon: for each approach its two trimmed asphalt corners, plus the corner C between approaches
    poly = []
    for i, a in enumerate(approaches):
        r = a["d"].cross(up).normalized()
        end = at + a["d"] * a["trim"]
        poly.append(end + r * a["half"])      # right corner (looking out)
        poly.append(end - r * a["half"])      # left corner
        poly.append(corners[i]["C"])
    bm = bmesh.new()
    z = at.z
    asphalt_verts = [bm.verts.new((p.x, p.y, z)) for p in poly]
    f = bm.faces.new(asphalt_verts); f.material_index = 0
    # sidewalk corners: between a's left edge and b's right edge, from the curb line C out to Cs
    sw_faces = []
    for i, c in enumerate(corners):
        a, b = c["a"], c["b"]
        if (a["swl"] <= 0 and b["swr"] <= 0): continue
        ea = at + a["d"] * a["trim"]; eb = at + b["d"] * b["trim"]
        A = ea - c["la"] * a["half"]; Ak = ea - c["la"] * (a["half"] + a["curb"]); As = ea - c["la"] * (a["half"] + a["curb"] + a["swl"])
        B = eb + c["lb"] * b["half"]; Bk = eb + c["lb"] * (b["half"] + b["curb"]); Bs = eb + c["lb"] * (b["half"] + b["curb"] + b["swr"])
        h = max(a["h"], b["h"])
        # curb top ring (A -> C -> B outward by curb width) and the sidewalk slab beyond it, both raised
        def quad(p0, p1, p2, p3, zz, mat):
            vs = [bm.verts.new((p.x, p.y, zz)) for p in (p0, p1, p2, p3)]
            ff = bm.faces.new(vs); ff.material_index = mat; return ff
        def wall(p0, p1, z0, z1, mat):
            vs = [bm.verts.new((p0.x, p0.y, z0)), bm.verts.new((p1.x, p1.y, z0)), bm.verts.new((p1.x, p1.y, z1)), bm.verts.new((p0.x, p0.y, z1))]
            ff = bm.faces.new(vs); ff.material_index = mat; return ff
        quad(A, c["C"], c["Ck"], Ak, h, 2); quad(c["C"], B, Bk, c["Ck"], h, 2)
        wall(A, c["C"], z, z + h, 2); wall(c["C"], B, z, z + h, 2)
        if a["swl"] > 0 or b["swr"] > 0:
            quad(Ak, c["Ck"], c["Cs"], As, h, 2); quad(c["Ck"], Bk, Bs, c["Cs"], h, 2)
    # crosswalks and stop lines on every approach (on the road strip, just outside the junction polygon)
    for a in approaches:
        r = a["d"].cross(up).normalized()
        end = at + a["d"] * a["trim"]
        if crosswalks:
            for k in range(int(2 * a["half"] / 1.0)):
                x0 = -a["half"] + 0.25 + k * 1.0; x1 = x0 + 0.5
                if x1 > a["half"] - 0.2: break
                p0 = end + a["d"] * 0.6 + r * x0; p1 = end + a["d"] * 0.6 + r * x1; p2 = end + a["d"] * 3.1 + r * x1; p3 = end + a["d"] * 3.1 + r * x0
                vs = [bm.verts.new((p.x, p.y, z + 0.004)) for p in (p0, p1, p2, p3)]
                ff = bm.faces.new(vs); ff.material_index = 1
        if stop_lines:
            # right-hand traffic: cars arrive on their right, which is -r when looking out from the junction
            p0 = end + a["d"] * 3.7 - r * a["half"]; p1 = end + a["d"] * 3.7 - r * 0.15; p2 = end + a["d"] * 4.1 - r * 0.15; p3 = end + a["d"] * 4.1 - r * a["half"]
            vs = [bm.verts.new((p.x, p.y, z + 0.004)) for p in (p0, p1, p2, p3)]
            ff = bm.faces.new(vs); ff.material_index = 1
    bm.normal_update()
    for ff in bm.faces:
        if ff.normal.z < 0: ff.normal_flip()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in (MRS + "Asphalt", MRS + "Paint", MRS + "Concrete"): me.materials.append(bpy.data.materials[m])
    # planar UVs in metres (object space is world space here: the object sits at the origin)
    uvl = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        v = me.vertices[loop.vertex_index].co; uvl.data[loop.index].uv = (v.x, v.y)
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, me); collection.objects.link(o)
    o["mrs_junction"] = {"at": list(at), "roads": [a["road"].name for a in approaches]}
    return o


# ============================================================================== demo scene
def demo_scene():
    """The validation scene in collection MRS_Demo: straight, S-curve, tight bend, T-junction,
    4-way, two widths, sidewalks on and off, dry and wet."""
    sc = bpy.context.scene
    col = bpy.data.collections.get(MRS + "Demo")
    if col:
        for o in list(col.objects): bpy.data.objects.remove(o)
    else:
        col = bpy.data.collections.new(MRS + "Demo"); sc.collection.children.link(col)
    roads = {}
    # a 4-way at (0,0) of an urban avenue (E-W) and a residential street (N-S); a T at (90, 0) with a service road going north
    roads["AvenueW"] = make_road("MRS_AvenueW", [(-120, 0, 0), (-60, 0, 0), (0, 0, 0)], col, "urban")
    roads["AvenueE"] = make_road("MRS_AvenueE", [(0, 0, 0), (45, 0, 0), (90, 0, 0)], col, "urban")
    roads["AvenueE2"] = make_road("MRS_AvenueE2", [(90, 0, 0), (130, 0, 0), (170, 0, 0)], col, "urban")
    roads["StreetN"] = make_road("MRS_StreetN", [(0, 0, 0), (0, 40, 0), (0, 80, 0)], col, "residential")
    roads["StreetS"] = make_road("MRS_StreetS", [(0, 0, 0), (0, -40, 0), (0, -80, 0)], col, "residential")
    roads["ServiceN"] = make_road("MRS_ServiceN", [(90, 0, 0), (90, 35, 0), (90, 70, 0)], col, "service")
    # an S-curve and a tight bend, residential with sidewalks only on one side
    roads["SCurve"] = make_road("MRS_SCurve", [(-120, 60, 0), (-80, 80, 0), (-40, 60, 0), (0, 80, 0)], col, "residential", sidewalk_r=False)
    roads["TightBend"] = make_road("MRS_TightBend", [(130, 60, 0), (160, 62, 0), (172, 80, 0), (160, 100, 0)], col, "residential", sidewalk_l=False, sidewalk_r=False)
    j4 = build_junction("MRS_Junction_4way", (0, 0, 0), [roads["AvenueW"], roads["AvenueE"], roads["StreetN"], roads["StreetS"]], col)
    jt = build_junction("MRS_Junction_T", (90, 0, 0), [roads["AvenueE"], roads["AvenueE2"], roads["ServiceN"]], col)
    return roads, [j4, jt]


# ============================================================================== export
def evaluated_mesh_object(o, name, collection, realize=True, collision=False):
    """A static mesh copy of a road (or junction) as Godot will see it."""
    if o.type == "CURVE":
        mod = o.modifiers["MRS_Road"]
        _set_input(mod, "Realize Instances", realize); _set_input(mod, "Collision Only", collision)
        o.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    if o.type == "CURVE":
        _set_input(mod, "Realize Instances", False); _set_input(mod, "Collision Only", False); o.update_tag()
    out = bpy.data.objects.new(name, me); out.matrix_world = o.matrix_world.copy(); collection.objects.link(out)
    return out


def export_glb(path, collection_name=MRS + "Demo", collision=True):
    """GLB of the evaluated roads and junctions (instances realized, materials kept, UVs in metres),
    plus <path>_collision.glb with only the drivable and walkable surfaces."""
    src = bpy.data.collections[collection_name]
    tmp = bpy.data.collections.get(MRS + "ExportTmp") or bpy.data.collections.new(MRS + "ExportTmp")
    if tmp.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(tmp)
    for o in list(tmp.objects): bpy.data.objects.remove(o)
    objs = [evaluated_mesh_object(o, o.name + "_export", tmp) for o in src.objects if o.type in ("CURVE", "MESH")]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_materials="EXPORT", export_normals=True, export_texcoords=True)
    stats = {"objects": len(objs), "tris": sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons), "bytes": os.path.getsize(path)}
    if collision:
        for o in list(tmp.objects): bpy.data.objects.remove(o)
        cobjs = [evaluated_mesh_object(o, o.name + "_col", tmp, realize=False, collision=True) for o in src.objects if o.type == "CURVE"]
        cobjs += [evaluated_mesh_object(o, o.name + "_col", tmp) for o in src.objects if o.type == "MESH"]
        for o in cobjs:                       # keep only the asphalt and concrete surfaces (slots 0 and 2)
            me = o.data
            bm = bmesh.new(); bm.from_mesh(me)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if me.materials and me.materials[f.material_index].name.endswith("Paint")], context="FACES")
            bm.to_mesh(me); bm.free()
        bpy.ops.object.select_all(action="DESELECT")
        for o in cobjs: o.select_set(True)
        bpy.context.view_layer.objects.active = cobjs[0]
        cpath = os.path.splitext(path)[0] + "_collision.glb"
        bpy.ops.export_scene.gltf(filepath=cpath, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_materials="NONE", export_normals=False, export_texcoords=False)
        stats["collision_tris"] = sum(len(p.vertices) - 2 for o in cobjs for p in o.data.polygons); stats["collision_bytes"] = os.path.getsize(cpath)
    for o in list(tmp.objects): bpy.data.objects.remove(o)
    return stats


# ============================================================================== UI
class MRS_OT_add_road(bpy.types.Operator):
    bl_idname = "mrs.add_road"; bl_label = "Add Road"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.EnumProperty(items=[(k, k.title(), "") for k in PRESETS], default="residential")

    def execute(self, ctx):
        col = bpy.data.collections.get(MRS + "Roads") or bpy.data.collections.new(MRS + "Roads")
        if col.name not in ctx.scene.collection.children: ctx.scene.collection.children.link(col)
        o = ctx.active_object
        if o and o.type == "CURVE" and "MRS_Road" not in o.modifiers:
            add_road_modifier(o, self.preset)
        else:
            c = ctx.scene.cursor.location
            o = make_road("MRS_Road", [(c.x, c.y, c.z), (c.x + 30, c.y, c.z), (c.x + 60, c.y, c.z)], col, self.preset)
        ctx.view_layer.objects.active = o
        return {"FINISHED"}


class MRS_OT_apply_preset(bpy.types.Operator):
    bl_idname = "mrs.apply_preset"; bl_label = "Apply Road Preset"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.EnumProperty(items=[(k, k.title(), "") for k in PRESETS], default="residential")

    def execute(self, ctx):
        n = 0
        for o in ctx.selected_objects:
            if "MRS_Road" in o.modifiers: set_road(o, self.preset); o["mrs_preset"] = self.preset; n += 1
        self.report({"INFO"}, "%d roads set to %s" % (n, self.preset)); return {"FINISHED"}


class MRS_OT_material_preset(bpy.types.Operator):
    bl_idname = "mrs.material_preset"; bl_label = "Dry / Wet"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.EnumProperty(items=[(k, k.title(), "") for k in MATERIAL_PRESETS], default="dry")

    def execute(self, ctx):
        apply_material_preset(self.preset); return {"FINISHED"}


class MRS_OT_add_junction(bpy.types.Operator):
    bl_idname = "mrs.add_junction"; bl_label = "Connect Roads at Cursor"; bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        roads = [o for o in ctx.selected_objects if "MRS_Road" in o.modifiers]
        col = bpy.data.collections.get(MRS + "Roads") or ctx.scene.collection
        try:
            j = build_junction("MRS_Junction_%d" % len([o for o in bpy.data.objects if o.name.startswith("MRS_Junction")]), ctx.scene.cursor.location, roads, col)
        except ValueError as e:
            self.report({"ERROR"}, str(e)); return {"CANCELLED"}
        self.report({"INFO"}, "junction %s: %d roads" % (j.name, len(j["mrs_junction"]["roads"]))); return {"FINISHED"}


class MRS_OT_export(bpy.types.Operator):
    bl_idname = "mrs.export"; bl_label = "Export GLB (+ collision)"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="//mrs_roads.glb")
    collection: bpy.props.StringProperty(default=MRS + "Demo")

    def invoke(self, ctx, event):
        ctx.window_manager.fileselect_add(self); return {"RUNNING_MODAL"}

    def execute(self, ctx):
        st = export_glb(bpy.path.abspath(self.filepath), self.collection)
        self.report({"INFO"}, "exported %d objects, %d tris" % (st["objects"], st["tris"])); return {"FINISHED"}


class MRS_PT_panel(bpy.types.Panel):
    bl_label = "Mert Road Studio"; bl_space_type = "VIEW_3D"; bl_region_type = "UI"; bl_category = "Road Studio"

    def draw(self, ctx):
        L = self.layout
        row = L.row(align=True)
        for k in PRESETS: row.operator("mrs.add_road", text=k.title()).preset = k
        L.label(text="Selected roads:")
        row = L.row(align=True)
        for k in PRESETS: row.operator("mrs.apply_preset", text=k.title()).preset = k
        L.operator("mrs.add_junction")
        L.label(text="Materials:")
        row = L.row(align=True)
        for k in MATERIAL_PRESETS: row.operator("mrs.material_preset", text=k.title()).preset = k
        L.operator("mrs.export")
        o = ctx.active_object
        if o and "MRS_Road" in o.modifiers:
            L.label(text="%s: %s" % (o.name, o.get("mrs_preset", "custom")))
            L.label(text="Edit inputs in the modifier panel", icon="MODIFIER")


CLASSES = (MRS_OT_add_road, MRS_OT_apply_preset, MRS_OT_material_preset, MRS_OT_add_junction, MRS_OT_export, MRS_PT_panel)


def register():
    for c in CLASSES:
        try: bpy.utils.unregister_class(c)
        except Exception: pass
        bpy.utils.register_class(c)


def build_groups():
    build_materials()
    placeholder_props()
    build_road_group()


class _API: pass
mrs = _API()
for _n in ("build_groups", "build_materials", "build_road_group", "placeholder_props", "make_road", "add_road_modifier", "set_road", "build_junction",
           "demo_scene", "export_glb", "register", "apply_material_preset", "road_widths", "road_ends", "PRESETS"):
    setattr(mrs, _n, globals()[_n])
