"""Procedural building materials as reusable node groups, applied to one prototype house, baked
for Godot. Runs inside a (visible or headless) Blender: exec() this file, then call the stages.

Node groups (all inputs exposed; changing Seed never changes the physical scale):
  CF_Coord        wall-aligned metre coordinates from object space: walls use (along, up), roofs
                  and floors use (x, y); Scale (tiles per metre) and Seed (offset only)
  CF_GeoMasks     geometry masks (Cycles): Edge (convex edges, Bevel vs true normal), Cavity
                  (1 - AO), Up / Down facing, Height above the object's base
  CF_EdgeWear     chipped edges: Edge mask x noise breakup -> Mask (+ Height dent)
  CF_Scratches    thin directional lines (Voronoi edge distance on stretched, rotated coords),
                  gated by noise: Mask
  CF_Damage       irregular patches (Voronoi cells gated by noise), breakup at the rim: Mask, Height
  CF_Grime        dirt: cavities + sheltered undersides + rain streaks (down-stretched noise) +
                  a foundation band near the ground: Mask
  CF_Layer        one mask drives Color, Roughness, Metallic and Height together (A over B)
  CF_Base_*       base surfaces: Stucco, Concrete, Terracotta, PaintedMetal, Wood, Trim, Glass
Materials for the prototype's slots: CF_Stucco, CF_Concrete, CF_RoofTerracotta, CF_Trim, CF_Door,
CF_Metal (painted railings), CF_Shutter (painted wood), CF_Glass.
Techniques verified from the reference file (realisticProceduralMaterial_01.blend): Pointiness /
Bevel / AO as edge-and-cavity masks, Voronoi distance for scratches, stacked noise masks gating
mix shaders, ColorRamps thresholding masks, masks feeding colour and roughness and bump together.
The Jamie Dunbar tutorial's own node graphs were not retrievable (no transcript, files behind a
Gumroad form), so the layering here is this project's implementation of those confirmed ideas.
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector

GROUPS = {}


# ------------------------------------------------------------------------------------ helpers
class NG:
    """Builder for a node group with named inputs / outputs."""
    def __init__(self, name, inputs, outputs):
        if name in bpy.data.node_groups: bpy.data.node_groups.remove(bpy.data.node_groups[name])
        self.g = bpy.data.node_groups.new(name, "ShaderNodeTree")
        self.inp = self.g.nodes.new("NodeGroupInput"); self.inp.location = (-900, 0)
        self.out = self.g.nodes.new("NodeGroupOutput"); self.out.location = (1200, 0)
        for nm, kind, default in inputs:
            s = self.g.interface.new_socket(nm, in_out="INPUT", socket_type=kind)
            if default is not None: s.default_value = default
        for nm, kind in outputs:
            self.g.interface.new_socket(nm, in_out="OUTPUT", socket_type=kind)
        self.x = -600
        GROUPS[name] = self.g

    def node(self, kind, props=None, **inputs):
        n = self.g.nodes.new(kind)
        n.location = (self.x, 0); self.x += 170
        for k, v in (props or {}).items(): setattr(n, k, v)
        for k, v in inputs.items():
            nm = k.replace("_", " ")
            sock = n.inputs[nm] if nm in n.inputs else n.inputs[k]
            if isinstance(v, bpy.types.NodeSocket): self.g.links.new(v, sock)
            else: sock.default_value = v
        return n

    def i(self, name): return self.inp.outputs[name]

    def set(self, name, sock):
        if isinstance(sock, bpy.types.NodeSocket): self.g.links.new(sock, self.out.inputs[name])
        else: self.out.inputs[name].default_value = sock

    def math(self, op, a, b=0.0, c=None, clamp=False):
        n = self.node("ShaderNodeMath", {"operation": op, "use_clamp": bool(clamp)})
        for k, v in enumerate((a, b) if c is None else (a, b, c)):
            if isinstance(v, bpy.types.NodeSocket): self.g.links.new(v, n.inputs[k])
            else: n.inputs[k].default_value = v
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", {"operation": op})
        for k, v in enumerate([a] + ([b] if b is not None else [])):
            if isinstance(v, bpy.types.NodeSocket): self.g.links.new(v, n.inputs[k])
            else: n.inputs[k].default_value = v
        if scale is not None:
            if isinstance(scale, bpy.types.NodeSocket): self.g.links.new(scale, n.inputs["Scale"])
            else: n.inputs["Scale"].default_value = scale
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix", {"data_type": "RGBA", "blend_type": blend})
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, bpy.types.NodeSocket): self.g.links.new(v, sock)
            elif isinstance(v, (int, float)): sock.default_value = v if sock.type != "RGBA" else (v, v, v, 1)
            else: sock.default_value = v
        return n.outputs[2]

    def ramp(self, fac, a, b, interp="EASE"):
        """Scalar smoothstep a..b (b < a inverts)."""
        n = self.node("ShaderNodeValToRGB")
        cr = n.color_ramp; cr.interpolation = interp
        lo, hi = (a, b) if a <= b else (b, a)
        cr.elements[0].position = lo; cr.elements[1].position = hi
        cr.elements[0].color = (0, 0, 0, 1) if a <= b else (1, 1, 1, 1)
        cr.elements[1].color = (1, 1, 1, 1) if a <= b else (0, 0, 0, 1)
        self.g.links.new(fac, n.inputs[0])
        return self.node("ShaderNodeSeparateColor", Color=n.outputs[0]).outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.5, distortion=0.0):
        n = self.node("ShaderNodeTexNoise", {"noise_dimensions": "3D"}, Vector=vec, Scale=scale, Detail=detail, Roughness=rough, Distortion=distortion)
        return n.outputs["Fac"]

    def voronoi(self, vec, scale, feature="F1"):
        n = self.node("ShaderNodeTexVoronoi", {"voronoi_dimensions": "3D", "feature": feature}, Vector=vec, Scale=scale)
        return n.outputs["Distance"], (n.outputs["Color"] if "Color" in n.outputs else None)

    def group(self, name, **inputs):
        n = self.node("ShaderNodeGroup", {"node_tree": GROUPS[name]})
        for k, v in inputs.items():
            sock = n.inputs[k]
            if isinstance(v, bpy.types.NodeSocket): self.g.links.new(v, sock)
            else: sock.default_value = v
        return n


def seeded(ng, vec, seed):
    """Offset coordinates by the seed (never scaled): a different pattern at the same physical size."""
    off = ng.node("ShaderNodeCombineXYZ", X=ng.math("MULTIPLY", seed, 13.7), Y=ng.math("MULTIPLY", seed, 7.3), Z=ng.math("MULTIPLY", seed, 3.1))
    return ng.vmath("ADD", vec, off.outputs[0])


# ------------------------------------------------------------------------------- the groups
def make_groups():
    # CF_Coord: wall-aligned metre coordinates
    ng = NG("CF_Coord", [("Scale", "NodeSocketFloat", 1.0), ("Seed", "NodeSocketFloat", 0.0)], [("Vector", "NodeSocketVector"), ("Up", "NodeSocketFloat")])
    tc = ng.node("ShaderNodeTexCoord")
    geo = ng.node("ShaderNodeNewGeometry")
    n = ng.node("ShaderNodeSeparateXYZ", Vector=geo.outputs["Normal"])
    p = ng.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"])
    ax = ng.math("ABSOLUTE", n.outputs["X"]); ay = ng.math("ABSOLUTE", n.outputs["Y"]); az = ng.math("ABSOLUTE", n.outputs["Z"])
    x_wall = ng.math("GREATER_THAN", ax, ay)                       # faces along x use (y, z), else (x, z)
    along = ng.mix(x_wall, ng.node("ShaderNodeCombineColor", Red=p.outputs["X"]).outputs[0], ng.node("ShaderNodeCombineColor", Red=p.outputs["Y"]).outputs[0])
    along_v = ng.node("ShaderNodeSeparateColor", Color=along).outputs[0]
    flat = ng.math("GREATER_THAN", az, 0.75)                        # floors / roofs: (x, y)
    u = ng.mix(flat, ng.node("ShaderNodeCombineColor", Red=along_v).outputs[0], ng.node("ShaderNodeCombineColor", Red=p.outputs["X"]).outputs[0])
    v = ng.mix(flat, ng.node("ShaderNodeCombineColor", Red=p.outputs["Z"]).outputs[0], ng.node("ShaderNodeCombineColor", Red=p.outputs["Y"]).outputs[0])
    uu = ng.node("ShaderNodeSeparateColor", Color=u).outputs[0]; vv = ng.node("ShaderNodeSeparateColor", Color=v).outputs[0]
    vec = ng.node("ShaderNodeCombineXYZ", X=ng.math("MULTIPLY", uu, ng.i("Scale")), Y=ng.math("MULTIPLY", vv, ng.i("Scale")), Z=ng.math("MULTIPLY", p.outputs["Z"], 0.37))
    ng.set("Vector", seeded(ng, vec.outputs[0], ng.i("Seed")))
    ng.set("Up", n.outputs["Z"])

    # CF_GeoMasks (Cycles for Bevel / AO)
    ng = NG("CF_GeoMasks", [("Edge Radius", "NodeSocketFloat", 0.03), ("AO Distance", "NodeSocketFloat", 0.35)],
            [("Edge", "NodeSocketFloat"), ("Cavity", "NodeSocketFloat"), ("Up", "NodeSocketFloat"), ("Down", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    geo = ng.node("ShaderNodeNewGeometry")
    bev = ng.node("ShaderNodeBevel", {"samples": 8}, Radius=ng.i("Edge Radius"))
    d = ng.vmath("DOT_PRODUCT", bev.outputs["Normal"], geo.outputs["True Normal"])
    dot = ng.node("ShaderNodeSeparateXYZ", Vector=d)  # dot product lands in a vector socket's x
    edge = ng.ramp(ng.math("SUBTRACT", 1.0, ng.node("ShaderNodeVectorMath", {"operation": "DOT_PRODUCT"}, Vector=bev.outputs["Normal"], Vector_001=geo.outputs["True Normal"]).outputs["Value"]), 0.02, 0.3)
    ng.set("Edge", edge)
    ao = ng.node("ShaderNodeAmbientOcclusion", {"samples": 8, "inside": False, "only_local": True}, Distance=ng.i("AO Distance"))
    ng.set("Cavity", ng.ramp(ao.outputs["AO"], 0.95, 0.35))
    nz = ng.node("ShaderNodeSeparateXYZ", Vector=geo.outputs["Normal"]).outputs["Z"]
    ng.set("Up", ng.ramp(nz, 0.2, 0.9)); ng.set("Down", ng.ramp(nz, -0.2, -0.9))
    tc = ng.node("ShaderNodeTexCoord")
    ng.set("Height", ng.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"]).outputs["Z"])

    # CF_EdgeWear
    ng = NG("CF_EdgeWear", [("Vector", "NodeSocketVector", None), ("Edge", "NodeSocketFloat", 0.0), ("Amount", "NodeSocketFloat", 0.5), ("Scale", "NodeSocketFloat", 30.0), ("Seed", "NodeSocketFloat", 0.0)],
            [("Mask", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    vec = seeded(ng, ng.i("Vector"), ng.i("Seed"))
    brk = ng.noise(vec, ng.i("Scale"), 4.0, 0.6)
    cells, _ = ng.voronoi(vec, ng.math("MULTIPLY", ng.i("Scale"), 2.5))
    gate = ng.ramp(ng.math("ADD", ng.math("MULTIPLY", ng.i("Edge"), 0.8), ng.math("MULTIPLY", brk, 0.5)), ng.math("SUBTRACT", 1.1, ng.math("MULTIPLY", ng.i("Amount"), 0.7)) if False else 0.72, 0.95)
    amount_gate = ng.math("GREATER_THAN", ng.math("ADD", ng.math("MULTIPLY", ng.i("Edge"), 0.8), ng.math("MULTIPLY", brk, 0.5)), ng.math("SUBTRACT", 1.15, ng.math("MULTIPLY", ng.i("Amount"), 0.75)))
    soft = ng.math("MULTIPLY", gate, ng.math("ADD", 0.3, ng.math("MULTIPLY", amount_gate, 0.7)), clamp=True)
    chip = ng.math("MULTIPLY", soft, ng.math("ADD", 0.5, ng.math("MULTIPLY", ng.ramp(cells, 0.45, 0.2), 0.5)), clamp=True)
    ng.set("Mask", chip); ng.set("Height", ng.math("MULTIPLY", chip, -0.4))

    # CF_Scratches
    ng = NG("CF_Scratches", [("Vector", "NodeSocketVector", None), ("Amount", "NodeSocketFloat", 0.3), ("Scale", "NodeSocketFloat", 6.0), ("Direction", "NodeSocketFloat", 0.0), ("Length", "NodeSocketFloat", 6.0), ("Seed", "NodeSocketFloat", 0.0)],
            [("Mask", "NodeSocketFloat")])
    vec = seeded(ng, ng.i("Vector"), ng.i("Seed"))
    rot = ng.node("ShaderNodeVectorRotate", {"rotation_type": "Z_AXIS"}, Vector=vec, Angle=ng.i("Direction"))
    stretched = ng.vmath("MULTIPLY", rot.outputs[0], ng.node("ShaderNodeCombineXYZ", X=1.0, Y=ng.i("Length"), Z=1.0).outputs[0])
    ed, _ = ng.voronoi(stretched, ng.i("Scale"), "DISTANCE_TO_EDGE")
    line = ng.ramp(ed, 0.02, 0.004)
    gate = ng.noise(vec, 2.0, 3.0, 0.5)
    ng.set("Mask", ng.math("MULTIPLY", line, ng.ramp(gate, ng.math("SUBTRACT", 1.0, ng.i("Amount")) if False else 0.55, 0.75), clamp=True))
    # amount scales the gate threshold: re-wire with a math node so Amount is live
    g = ng.g
    thr = ng.math("SUBTRACT", 1.0, ng.math("MULTIPLY", ng.i("Amount"), 0.9))
    gated = ng.math("GREATER_THAN", gate, thr)
    soft = ng.math("MULTIPLY", ng.ramp(gate, 0.3, 0.9), gated)
    ng.set("Mask", ng.math("MULTIPLY", line, ng.math("ADD", 0.25, ng.math("MULTIPLY", soft, 0.75)), clamp=True))

    # CF_Damage
    ng = NG("CF_Damage", [("Vector", "NodeSocketVector", None), ("Amount", "NodeSocketFloat", 0.3), ("Scale", "NodeSocketFloat", 1.5), ("Seed", "NodeSocketFloat", 0.0)],
            [("Mask", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    vec = seeded(ng, ng.i("Vector"), ng.i("Seed"))
    cells, _ = ng.voronoi(vec, ng.i("Scale"))
    rim = ng.noise(vec, ng.math("MULTIPLY", ng.i("Scale"), 12.0), 5.0, 0.7)
    gate = ng.noise(vec, ng.math("MULTIPLY", ng.i("Scale"), 0.5), 2.0, 0.5)
    allow = ng.math("GREATER_THAN", gate, ng.math("SUBTRACT", 1.0, ng.math("MULTIPLY", ng.i("Amount"), 0.8)))
    patch = ng.ramp(ng.math("ADD", cells, ng.math("MULTIPLY", ng.math("SUBTRACT", rim, 0.5), 0.3)), 0.5, 0.3)
    mask = ng.math("MULTIPLY", patch, allow, clamp=True)
    ng.set("Mask", mask); ng.set("Height", ng.math("MULTIPLY", mask, -0.6))

    # CF_Grime
    ng = NG("CF_Grime", [("Vector", "NodeSocketVector", None), ("Cavity", "NodeSocketFloat", 0.0), ("Down", "NodeSocketFloat", 0.0), ("Height", "NodeSocketFloat", 1.0),
                         ("Amount", "NodeSocketFloat", 0.5), ("Scale", "NodeSocketFloat", 2.0), ("Streaks", "NodeSocketFloat", 0.4), ("Foundation", "NodeSocketFloat", 0.6), ("Seed", "NodeSocketFloat", 0.0)],
            [("Mask", "NodeSocketFloat")])
    vec = seeded(ng, ng.i("Vector"), ng.i("Seed"))
    blotch = ng.ramp(ng.noise(vec, ng.i("Scale"), 7.0, 0.7), 0.45, 0.7)
    streak_vec = ng.vmath("MULTIPLY", vec, ng.node("ShaderNodeCombineXYZ", X=1.0, Y=0.08, Z=1.0).outputs[0])
    streaks = ng.math("MULTIPLY", ng.ramp(ng.noise(streak_vec, ng.math("MULTIPLY", ng.i("Scale"), 4.0), 3.0, 0.5), 0.5, 0.75), ng.i("Streaks"))
    cav = ng.math("MULTIPLY", ng.i("Cavity"), 0.9)
    shelter = ng.math("MULTIPLY", ng.i("Down"), 0.5)
    base_band = ng.math("MULTIPLY", ng.ramp(ng.i("Height"), 0.9, 0.0), ng.math("MULTIPLY", ng.i("Foundation"), ng.math("ADD", 0.5, ng.math("MULTIPLY", blotch, 0.5))))
    total = ng.math("ADD", ng.math("ADD", ng.math("MULTIPLY", blotch, 0.6), streaks), ng.math("ADD", cav, ng.math("ADD", shelter, base_band)))
    speck = ng.noise(vec, ng.math("MULTIPLY", ng.i("Scale"), 30.0), 3.0, 0.7)
    ng.set("Mask", ng.math("MULTIPLY", ng.math("MULTIPLY", total, ng.i("Amount")), ng.math("ADD", 0.6, ng.math("MULTIPLY", speck, 0.6)), clamp=True))

    # CF_Layer: one mask drives everything
    ng = NG("CF_Layer", [("Mask", "NodeSocketFloat", 0.0), ("Color A", "NodeSocketColor", (0.5, 0.5, 0.5, 1)), ("Rough A", "NodeSocketFloat", 0.6), ("Metal A", "NodeSocketFloat", 0.0), ("Height A", "NodeSocketFloat", 0.5),
                         ("Color B", "NodeSocketColor", (0.5, 0.5, 0.5, 1)), ("Rough B", "NodeSocketFloat", 0.6), ("Metal B", "NodeSocketFloat", 0.0), ("Height B", "NodeSocketFloat", 0.5)],
            [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"), ("Metal", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    ng.set("Color", ng.mix(ng.i("Mask"), ng.i("Color A"), ng.i("Color B")))
    for nm in ("Rough", "Metal", "Height"):
        n = ng.node("ShaderNodeMix", {"data_type": "FLOAT"})
        ng.g.links.new(ng.i("Mask"), n.inputs[0]); ng.g.links.new(ng.i(nm + " A"), n.inputs[2]); ng.g.links.new(ng.i(nm + " B"), n.inputs[3])
        ng.set(nm, n.outputs[0])

    # base surfaces -------------------------------------------------------------------------
    ng = NG("CF_Base_Stucco", [("Vector", "NodeSocketVector", None), ("Color", "NodeSocketColor", (0.82, 0.78, 0.68, 1)), ("Variation", "NodeSocketFloat", 0.12), ("Pores", "NodeSocketFloat", 0.5), ("Roughness", "NodeSocketFloat", 0.85)],
            [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    vec = ng.i("Vector")
    broad = ng.noise(vec, 0.35, 2.0, 0.5)
    fine = ng.noise(vec, 28.0, 8.0, 0.65)
    trowel = ng.noise(ng.vmath("MULTIPLY", vec, (3.0, 1.0, 1.0)), 6.0, 2.0, 0.4)
    tone = ng.math("ADD", 1.0, ng.math("MULTIPLY", ng.math("SUBTRACT", broad, 0.5), ng.math("MULTIPLY", ng.i("Variation"), 2.0)))
    col = ng.mix(1.0, ng.i("Color"), ng.node("ShaderNodeCombineColor", Red=tone, Green=tone, Blue=tone).outputs[0], "MULTIPLY")
    pores, _ = ng.voronoi(vec, 120.0)
    pit = ng.math("MULTIPLY", ng.ramp(pores, 0.12, 0.05), ng.i("Pores"))
    col = ng.mix(ng.math("MULTIPLY", pit, 0.5), col, (0.4, 0.38, 0.35, 1))
    ng.set("Color", col)
    ng.set("Rough", ng.math("ADD", ng.i("Roughness"), ng.math("MULTIPLY", ng.math("SUBTRACT", fine, 0.5), 0.1)))
    ng.set("Height", ng.math("SUBTRACT", ng.math("ADD", ng.math("MULTIPLY", fine, 0.55), ng.math("MULTIPLY", trowel, 0.45)), ng.math("MULTIPLY", pit, 0.3)))

    ng = NG("CF_Base_Terracotta", [("Vector", "NodeSocketVector", None), ("Color", "NodeSocketColor", (0.55, 0.24, 0.13, 1)), ("Tile Width", "NodeSocketFloat", 0.22), ("Tile Length", "NodeSocketFloat", 0.4), ("Variation", "NodeSocketFloat", 0.12)],
            [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    vec = ng.i("Vector")
    sep = ng.node("ShaderNodeSeparateXYZ", Vector=vec)
    fu = ng.math("FRACT", ng.math("DIVIDE", sep.outputs["X"], ng.i("Tile Width")))
    ridge = ng.math("SINE", ng.math("MULTIPLY", fu, math.pi))
    row = ng.math("FLOOR", ng.math("DIVIDE", sep.outputs["Y"], ng.i("Tile Length")))
    fv = ng.math("FRACT", ng.math("DIVIDE", sep.outputs["Y"], ng.i("Tile Length")))
    lip = ng.ramp(fv, 0.0, 0.1)
    cell = ng.node("ShaderNodeCombineXYZ", X=ng.math("FLOOR", ng.math("DIVIDE", sep.outputs["X"], ng.i("Tile Width"))), Y=row, Z=0.0)
    r = ng.node("ShaderNodeTexWhiteNoise", {"noise_dimensions": "3D"}, Vector=cell.outputs[0]).outputs["Value"]
    tone = ng.math("ADD", 1.0, ng.math("MULTIPLY", ng.math("SUBTRACT", r, 0.5), ng.math("MULTIPLY", ng.i("Variation"), 2.0)))
    col = ng.mix(1.0, ng.i("Color"), ng.node("ShaderNodeCombineColor", Red=tone, Green=tone, Blue=tone).outputs[0], "MULTIPLY")
    col = ng.mix(ng.math("MULTIPLY", ng.math("SUBTRACT", 1.0, ridge), 0.5), col, (0.12, 0.09, 0.07, 1), "MULTIPLY")
    fine = ng.noise(vec, 20.0, 5.0, 0.55)
    lichen = ng.ramp(ng.noise(vec, 2.5, 4.0, 0.6), 0.62, 0.75)
    col = ng.mix(ng.math("MULTIPLY", lichen, 0.5), col, (0.45, 0.5, 0.3, 1))
    ng.set("Color", col); ng.set("Rough", ng.math("ADD", 0.72, ng.math("MULTIPLY", fine, 0.12))); ng.set("Height", ng.math("MULTIPLY", ridge, lip))

    ng = NG("CF_Base_PaintedMetal", [("Vector", "NodeSocketVector", None), ("Paint", "NodeSocketColor", (0.12, 0.2, 0.16, 1)), ("Metal", "NodeSocketColor", (0.5, 0.5, 0.52, 1)), ("Paint Rough", "NodeSocketFloat", 0.45)],
            [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"), ("Metal", "NodeSocketFloat"), ("Height", "NodeSocketFloat"),
             ("Sub Color", "NodeSocketColor"), ("Sub Rough", "NodeSocketFloat"), ("Sub Metal", "NodeSocketFloat")])
    vec = ng.i("Vector")
    orange_peel = ng.noise(vec, 60.0, 3.0, 0.6)
    ng.set("Color", ng.mix(ng.math("MULTIPLY", ng.noise(vec, 1.5, 2.0, 0.5), 0.15), ng.i("Paint"), (0.6, 0.6, 0.6, 1), "MULTIPLY"))
    ng.set("Rough", ng.math("ADD", ng.i("Paint Rough"), ng.math("MULTIPLY", ng.math("SUBTRACT", orange_peel, 0.5), 0.12)))
    ng.set("Metal", 0.0); ng.set("Height", ng.math("MULTIPLY", orange_peel, 0.3))
    rust = ng.ramp(ng.noise(vec, 8.0, 5.0, 0.6), 0.5, 0.7)
    ng.set("Sub Color", ng.mix(rust, ng.i("Metal"), (0.3, 0.12, 0.06, 1)))
    ng.set("Sub Rough", ng.math("ADD", 0.35, ng.math("MULTIPLY", rust, 0.45))); ng.set("Sub Metal", ng.math("SUBTRACT", 1.0, ng.math("MULTIPLY", rust, 0.8)))

    ng = NG("CF_Base_Wood", [("Vector", "NodeSocketVector", None), ("Dark", "NodeSocketColor", (0.2, 0.12, 0.07, 1)), ("Light", "NodeSocketColor", (0.45, 0.3, 0.17, 1)), ("Board", "NodeSocketFloat", 0.12), ("Vertical", "NodeSocketFloat", 1.0), ("Roughness", "NodeSocketFloat", 0.6)],
            [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"), ("Height", "NodeSocketFloat")])
    vec = ng.i("Vector")
    sep = ng.node("ShaderNodeSeparateXYZ", Vector=vec)
    a = ng.mix(ng.i("Vertical"), ng.node("ShaderNodeCombineColor", Red=sep.outputs["Y"]).outputs[0], ng.node("ShaderNodeCombineColor", Red=sep.outputs["X"]).outputs[0])
    along = ng.mix(ng.i("Vertical"), ng.node("ShaderNodeCombineColor", Red=sep.outputs["X"]).outputs[0], ng.node("ShaderNodeCombineColor", Red=sep.outputs["Y"]).outputs[0])
    av = ng.node("ShaderNodeSeparateColor", Color=a).outputs[0]; alv = ng.node("ShaderNodeSeparateColor", Color=along).outputs[0]
    cell = ng.math("FLOOR", ng.math("DIVIDE", av, ng.i("Board")))
    fa = ng.math("FRACT", ng.math("DIVIDE", av, ng.i("Board")))
    gap = ng.ramp(ng.math("MINIMUM", fa, ng.math("SUBTRACT", 1.0, fa)), 0.06, 0.0)
    gvec = ng.node("ShaderNodeCombineXYZ", X=ng.math("MULTIPLY", av, 7.0), Y=ng.math("MULTIPLY", alv, 0.35), Z=cell)
    grain = ng.noise(gvec.outputs[0], 6.0, 10.0, 0.75)
    rings = ng.ramp(ng.math("FRACT", ng.math("MULTIPLY", ng.math("ADD", grain, ng.math("MULTIPLY", av, 0.6)), 9.0)), 0.0, 1.0)
    r = ng.node("ShaderNodeTexWhiteNoise", {"noise_dimensions": "1D"}, W=cell).outputs["Value"]
    wood = ng.mix(ng.math("ADD", ng.math("MULTIPLY", rings, 0.6), ng.math("MULTIPLY", r, 0.4)), ng.i("Dark"), ng.i("Light"))
    ng.set("Color", ng.mix(gap, wood, (0.05, 0.035, 0.025, 1)))
    ng.set("Rough", ng.math("ADD", ng.i("Roughness"), ng.math("MULTIPLY", rings, 0.15)))
    ng.set("Height", ng.math("SUBTRACT", ng.math("ADD", 0.9, ng.math("MULTIPLY", ng.math("SUBTRACT", rings, 0.5), 0.12)), ng.math("MULTIPLY", gap, 0.9)))

    ng = NG("CF_Base_Glass", [("Tint", "NodeSocketColor", (0.18, 0.24, 0.28, 1)), ("Interior", "NodeSocketColor", (0.06, 0.05, 0.045, 1)), ("Smudge", "NodeSocketFloat", 0.3), ("Vector", "NodeSocketVector", None)],
            [("Color", "NodeSocketColor"), ("Rough", "NodeSocketFloat"), ("Metal", "NodeSocketFloat")])
    smudge = ng.ramp(ng.noise(ng.i("Vector"), 1.2, 3.0, 0.6), 0.5, 0.75)
    geo = ng.node("ShaderNodeNewGeometry")
    fres = ng.node("ShaderNodeFresnel", IOR=1.5)
    ng.set("Color", ng.mix(fres.outputs[0], ng.i("Interior"), ng.i("Tint")))
    ng.set("Rough", ng.math("ADD", 0.04, ng.math("MULTIPLY", smudge, ng.math("MULTIPLY", ng.i("Smudge"), 0.5))))
    ng.set("Metal", 0.3)


# ------------------------------------------------------------------------- the materials
def _mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


class M:
    """Material assembler on top of the groups."""
    def __init__(self, name):
        self.m = _mat(name); self.nt = self.m.node_tree; self.x = 0

    def node(self, kind, props=None, **inputs):
        n = self.nt.nodes.new(kind); n.location = (self.x, 0); self.x += 220
        for k, v in (props or {}).items(): setattr(n, k, v)
        for k, v in inputs.items():
            nm = k.replace("_", " ")
            sock = n.inputs[nm] if nm in n.inputs else n.inputs[k]
            if isinstance(v, bpy.types.NodeSocket): self.nt.links.new(v, sock)
            else: sock.default_value = v
        return n

    def group(self, name, **inputs):
        return self.node("ShaderNodeGroup", {"node_tree": GROUPS[name], "label": name}, **inputs)

    def layer(self, mask, a, b):
        """a, b: dicts with Color, Rough, Metal, Height sockets or values."""
        kw = {"Mask": mask}
        for side, src in (("A", a), ("B", b)):
            for k in ("Color", "Rough", "Metal", "Height"):
                kw["%s %s" % (k, side)] = src.get(k, 0.0 if k != "Color" else (0.5, 0.5, 0.5, 1))
        n = self.group("CF_Layer", **kw)
        return {"Color": n.outputs["Color"], "Rough": n.outputs["Rough"], "Metal": n.outputs["Metal"], "Height": n.outputs["Height"]}

    def finish(self, s, bump=0.4, bump_dist=0.015):
        bmp = self.node("ShaderNodeBump", Strength=bump, Distance=bump_dist, Height=s["Height"])
        bsdf = self.node("ShaderNodeBsdfPrincipled", Base_Color=s["Color"], Roughness=s["Rough"], Metallic=s["Metal"], Normal=bmp.outputs["Normal"])
        out = self.node("ShaderNodeOutputMaterial")
        self.nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
        self.m["cf_layers"] = {k: (v.node.name + ":" + v.name) for k, v in s.items()}
        return self.m


def build_materials(seed=0.0):
    make_groups()
    mats = {}
    # stucco walls: base + plaster damage (render coat shows) + grime with foundation band
    mm = M("CF_Stucco")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.03, AO_Distance=0.4)
    base = mm.group("CF_Base_Stucco", Vector=co.outputs["Vector"], Color=(0.84, 0.78, 0.64, 1), Variation=0.14, Pores=0.5)
    s = {"Color": base.outputs["Color"], "Rough": base.outputs["Rough"], "Metal": 0.0, "Height": base.outputs["Height"]}
    dmg = mm.group("CF_Damage", Vector=co.outputs["Vector"], Amount=0.25, Scale=1.2, Seed=seed)
    s = mm.layer(dmg.outputs["Mask"], s, {"Color": (0.55, 0.53, 0.48, 1), "Rough": 0.95, "Metal": 0.0, "Height": 0.1})
    ew = mm.group("CF_EdgeWear", Vector=co.outputs["Vector"], Edge=gm.outputs["Edge"], Amount=0.3, Scale=25.0, Seed=seed)
    s = mm.layer(ew.outputs["Mask"], s, {"Color": (0.6, 0.57, 0.52, 1), "Rough": 0.9, "Metal": 0.0, "Height": 0.2})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=gm.outputs["Height"], Amount=0.55, Scale=1.6, Streaks=0.45, Foundation=0.7, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.22, 0.2, 0.16, 1), "Rough": 0.98, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_Stucco"] = mm.finish(s, 0.35, 0.012)
    # concrete: balcony slabs, plinth, steps
    mm = M("CF_Concrete")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.04, AO_Distance=0.4)
    base = mm.group("CF_Base_Stucco", Vector=co.outputs["Vector"], Color=(0.6, 0.6, 0.58, 1), Variation=0.18, Pores=1.0, Roughness=0.9)
    s = {"Color": base.outputs["Color"], "Rough": base.outputs["Rough"], "Metal": 0.0, "Height": base.outputs["Height"]}
    ew = mm.group("CF_EdgeWear", Vector=co.outputs["Vector"], Edge=gm.outputs["Edge"], Amount=0.45, Scale=20.0, Seed=seed)
    s = mm.layer(ew.outputs["Mask"], s, {"Color": (0.72, 0.72, 0.7, 1), "Rough": 0.95, "Metal": 0.0, "Height": 0.3})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=gm.outputs["Height"], Amount=0.6, Scale=2.0, Streaks=0.5, Foundation=0.5, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.18, 0.17, 0.15, 1), "Rough": 1.0, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_Concrete"] = mm.finish(s, 0.3, 0.012)
    # terracotta roof: tiles follow each slope (CF_Coord picks the slope's projection); grime, moss in the valleys
    mm = M("CF_RoofTerracotta")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.05, AO_Distance=0.5)
    base = mm.group("CF_Base_Terracotta", Vector=co.outputs["Vector"], Color=(0.56, 0.25, 0.13, 1), Variation=0.14)
    s = {"Color": base.outputs["Color"], "Rough": base.outputs["Rough"], "Metal": 0.0, "Height": base.outputs["Height"]}
    dmg = mm.group("CF_Damage", Vector=co.outputs["Vector"], Amount=0.12, Scale=2.0, Seed=seed)
    s = mm.layer(dmg.outputs["Mask"], s, {"Color": (0.7, 0.45, 0.3, 1), "Rough": 0.9, "Metal": 0.0, "Height": 0.2})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=1.0, Amount=0.5, Scale=1.2, Streaks=0.6, Foundation=0.0, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.16, 0.14, 0.11, 1), "Rough": 1.0, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_RoofTerracotta"] = mm.finish(s, 0.9, 0.02)
    # trim: painted plaster mouldings, light grime in the cavities
    mm = M("CF_Trim")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.02, AO_Distance=0.25)
    base = mm.group("CF_Base_Stucco", Vector=co.outputs["Vector"], Color=(0.93, 0.92, 0.88, 1), Variation=0.06, Pores=0.15, Roughness=0.6)
    s = {"Color": base.outputs["Color"], "Rough": base.outputs["Rough"], "Metal": 0.0, "Height": base.outputs["Height"]}
    ew = mm.group("CF_EdgeWear", Vector=co.outputs["Vector"], Edge=gm.outputs["Edge"], Amount=0.2, Scale=30.0, Seed=seed)
    s = mm.layer(ew.outputs["Mask"], s, {"Color": (0.7, 0.68, 0.62, 1), "Rough": 0.9, "Metal": 0.0, "Height": 0.2})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=1.0, Amount=0.35, Scale=2.0, Streaks=0.5, Foundation=0.0, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.3, 0.28, 0.25, 1), "Rough": 0.95, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_Trim"] = mm.finish(s, 0.2, 0.01)
    # railings: dark green paint over steel, chips to metal at edges, directional scratches, grime under rails
    mm = M("CF_Metal")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.012, AO_Distance=0.15)
    base = mm.group("CF_Base_PaintedMetal", Vector=co.outputs["Vector"], Paint=(0.1, 0.16, 0.13, 1), Metal=(0.5, 0.5, 0.52, 1), Paint_Rough=0.42)
    paint = {"Color": base.outputs["Color"], "Rough": base.outputs["Rough"], "Metal": 0.0, "Height": base.outputs["Height"]}
    steel = {"Color": base.outputs["Sub Color"], "Rough": base.outputs["Sub Rough"], "Metal": base.outputs["Sub Metal"], "Height": 0.0}
    ew = mm.group("CF_EdgeWear", Vector=co.outputs["Vector"], Edge=gm.outputs["Edge"], Amount=0.55, Scale=40.0, Seed=seed)
    s = mm.layer(ew.outputs["Mask"], paint, steel)
    sc_ = mm.group("CF_Scratches", Vector=co.outputs["Vector"], Amount=0.35, Scale=12.0, Direction=0.3, Length=8.0, Seed=seed)
    s = mm.layer(sc_.outputs["Mask"], s, {"Color": (0.55, 0.55, 0.57, 1), "Rough": 0.35, "Metal": 0.9, "Height": -0.1})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=1.0, Amount=0.4, Scale=4.0, Streaks=0.3, Foundation=0.0, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.12, 0.11, 0.1, 1), "Rough": 0.9, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_Metal"] = mm.finish(s, 0.25, 0.004)
    # shutters: green paint over wood, wear shows the wood, grime in the louvres
    mm = M("CF_Shutter")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.015, AO_Distance=0.12)
    wood = mm.group("CF_Base_Wood", Vector=co.outputs["Vector"], Board=0.09, Vertical=1.0)
    paint = mm.group("CF_Base_PaintedMetal", Vector=co.outputs["Vector"], Paint=(0.16, 0.32, 0.25, 1), Paint_Rough=0.55)
    s = {"Color": paint.outputs["Color"], "Rough": paint.outputs["Rough"], "Metal": 0.0, "Height": wood.outputs["Height"]}
    ew = mm.group("CF_EdgeWear", Vector=co.outputs["Vector"], Edge=gm.outputs["Edge"], Amount=0.45, Scale=30.0, Seed=seed)
    s = mm.layer(ew.outputs["Mask"], s, {"Color": wood.outputs["Color"], "Rough": wood.outputs["Rough"], "Metal": 0.0, "Height": wood.outputs["Height"]})
    dmg = mm.group("CF_Damage", Vector=co.outputs["Vector"], Amount=0.2, Scale=4.0, Seed=seed)
    s = mm.layer(dmg.outputs["Mask"], s, {"Color": wood.outputs["Color"], "Rough": 0.8, "Metal": 0.0, "Height": wood.outputs["Height"]})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=1.0, Amount=0.4, Scale=3.0, Streaks=0.4, Foundation=0.0, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.1, 0.1, 0.08, 1), "Rough": 0.95, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_Shutter"] = mm.finish(s, 0.3, 0.006)
    # door: varnished oak, scratches at hand height, grime at the foot
    mm = M("CF_Door")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed); gm = mm.group("CF_GeoMasks", Edge_Radius=0.015, AO_Distance=0.15)
    wood = mm.group("CF_Base_Wood", Vector=co.outputs["Vector"], Dark=(0.25, 0.14, 0.07, 1), Light=(0.5, 0.32, 0.16, 1), Board=0.14, Vertical=1.0, Roughness=0.35)
    s = {"Color": wood.outputs["Color"], "Rough": wood.outputs["Rough"], "Metal": 0.0, "Height": wood.outputs["Height"]}
    sc_ = mm.group("CF_Scratches", Vector=co.outputs["Vector"], Amount=0.25, Scale=10.0, Direction=1.2, Length=5.0, Seed=seed)
    s = mm.layer(sc_.outputs["Mask"], s, {"Color": (0.6, 0.45, 0.28, 1), "Rough": 0.6, "Metal": 0.0, "Height": 0.3})
    gr = mm.group("CF_Grime", Vector=co.outputs["Vector"], Cavity=gm.outputs["Cavity"], Down=gm.outputs["Down"], Height=gm.outputs["Height"], Amount=0.35, Scale=3.0, Streaks=0.2, Foundation=0.8, Seed=seed)
    s = mm.layer(gr.outputs["Mask"], s, {"Color": (0.12, 0.09, 0.06, 1), "Rough": 0.85, "Metal": 0.0, "Height": s["Height"]})
    mats["CF_Door"] = mm.finish(s, 0.3, 0.006)
    # glass: dark interior backing, fresnel tint, smudges in the roughness
    mm = M("CF_Glass")
    co = mm.group("CF_Coord", Scale=1.0, Seed=seed)
    gl = mm.group("CF_Base_Glass", Vector=co.outputs["Vector"], Smudge=0.35)
    bsdf = mm.node("ShaderNodeBsdfPrincipled", Base_Color=gl.outputs["Color"], Roughness=gl.outputs["Rough"], Metallic=gl.outputs["Metal"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.8
    out = mm.node("ShaderNodeOutputMaterial"); mm.nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    mats["CF_Glass"] = mm.m
    return mats


def apply_materials(obj, mats):
    for slot in obj.material_slots:
        key = slot.material.name.split(".")[0] if slot.material else ""
        if key in mats: slot.material = mats[key]


# ----------------------------------------------------------------------------- bake + export
def unwrap(obj, margin=0.004):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True)
    obj.data.uv_layers.clear() if hasattr(obj.data.uv_layers, "clear") else None
    while obj.data.uv_layers: obj.data.uv_layers.remove(obj.data.uv_layers[0])
    obj.data.uv_layers.new(name="Bake")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_object(obj, out_dir, res=2048, samples=32):
    """Albedo (colour only), tangent normal, roughness, metallic, AO -> <out>/<obj>_albedo.png, _normal.png, _orm.png."""
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    prev_engine = sc.render.engine
    sc.render.engine = "CYCLES"
    try:                                           # GPU when there is one (OptiX / CUDA / HIP)
        cp = bpy.context.preferences.addons["cycles"].preferences
        for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                cp.compute_device_type = dev; cp.get_devices()
                if any(d.type == dev for d in cp.devices):
                    for d in cp.devices: d.use = d.type == dev
                    sc.cycles.device = "GPU"; break
            except TypeError:
                continue
    except Exception:
        pass
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.bake.margin = 8
    sc.render.bake.use_selected_to_active = False
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True)
    imgs = {}
    for key, srgb in (("albedo", True), ("normal", False), ("rough", False), ("metal", False), ("ao", False)):
        im = bpy.data.images.get("%s_%s" % (obj.name, key))
        if im is None or im.size[0] != res:
            if im: bpy.data.images.remove(im)
            im = bpy.data.images.new("%s_%s" % (obj.name, key), res, res, alpha=False, float_buffer=False)
        im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
        imgs[key] = im
    nodes = []
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        n = nt.nodes.new("ShaderNodeTexImage"); n.name = "CF_BakeTarget"; nodes.append((nt, n))
    def target(im):
        for nt, n in nodes:
            n.image = im; nt.nodes.active = n
    target(imgs["albedo"]); bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8)
    target(imgs["normal"]); bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=8)
    target(imgs["rough"]); bpy.ops.object.bake(type="ROUGHNESS", margin=8)
    # metallic: no bake pass; emit it through a temporary emission on each material
    swaps = []
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        bsdf = out.inputs["Surface"].links[0].from_node
        em = nt.nodes.new("ShaderNodeEmission")
        src = bsdf.inputs["Metallic"]
        if src.links: nt.links.new(src.links[0].from_socket, em.inputs["Color"])
        else: em.inputs["Color"].default_value = (src.default_value,) * 3 + (1,)
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        swaps.append((nt, out, bsdf, em))
    target(imgs["metal"]); bpy.ops.object.bake(type="EMIT", margin=8)
    for nt, out, bsdf, em in swaps:
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"]); nt.nodes.remove(em)
    target(imgs["ao"]); bpy.ops.object.bake(type="AO", margin=8)
    for nt, n in nodes: nt.nodes.remove(n)
    r = np.array(imgs["rough"].pixels[:], np.float32).reshape(res, res, 4)
    m = np.array(imgs["metal"].pixels[:], np.float32).reshape(res, res, 4)
    a = np.array(imgs["ao"].pixels[:], np.float32).reshape(res, res, 4)
    orm = np.ones((res, res, 4), np.float32)
    orm[..., 0] = np.clip(a[..., 0] * 0.5 + 0.5, 0, 1)      # local AO, softened: Godot adds SSAO
    orm[..., 1] = np.clip(r[..., 0], 0.03, 1); orm[..., 2] = np.clip(m[..., 0], 0, 1)
    im_orm = bpy.data.images.get(obj.name + "_orm") or bpy.data.images.new(obj.name + "_orm", res, res, alpha=False)
    if im_orm.size[0] != res:
        bpy.data.images.remove(im_orm); im_orm = bpy.data.images.new(obj.name + "_orm", res, res, alpha=False)
    im_orm.colorspace_settings.name = "Non-Color"
    im_orm.pixels.foreach_set(orm.ravel())
    paths = {}
    for key, im in (("albedo", imgs["albedo"]), ("normal", imgs["normal"]), ("orm", im_orm)):
        im.filepath_raw = os.path.join(out_dir, "%s_%s.png" % (obj.name, key)); im.file_format = "PNG"; im.save()
        paths[key] = im.filepath_raw
    sc.render.engine = prev_engine
    return paths


def baked_material(obj, paths, name):
    """One glTF-ready material: albedo, ORM (Separate Color -> occlusion / roughness / metallic), normal map."""
    m = _mat(name); nt = m.node_tree
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    def img(path, srgb):
        # a fresh datablock from disk: the bake images are packed in the .blend and the glTF exporter
        # would write their packed (previous) pixels instead of the file just saved
        for old in [i for i in bpy.data.images if os.path.abspath(bpy.path.abspath(i.filepath_raw or "")) == os.path.abspath(path)]:
            bpy.data.images.remove(old)
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(path, check_existing=False)
        n.image.colorspace_settings.name = "sRGB" if srgb else "Non-Color"; return n
    a = img(paths["albedo"], True); nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
    o = img(paths["orm"], False); sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(o.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"]); nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    gs = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if "Occlusion" not in [s.name for s in gs.interface.items_tree]: gs.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup"); gn.node_tree = gs; nt.links.new(sep.outputs[0], gn.inputs["Occlusion"])
    nm = img(paths["normal"], False); nmap = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(nm.outputs["Color"], nmap.inputs["Color"]); nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def export_baked(obj, paths, glb_path):
    """A copy of the object with the single baked material, exported as GLB (textures embedded)."""
    copy = obj.copy(); copy.data = obj.data.copy(); copy.name = obj.name + "_baked"
    bpy.context.scene.collection.objects.link(copy)
    copy.data.materials.clear(); copy.data.materials.append(baked_material(obj, paths, obj.name + "_baked"))
    for p in copy.data.polygons: p.material_index = 0
    copy.location = (0, 0, 0)
    bpy.ops.object.select_all(action="DESELECT"); copy.select_set(True); bpy.context.view_layer.objects.active = copy
    os.makedirs(os.path.dirname(glb_path), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_materials="EXPORT",
                              export_normals=True, export_texcoords=True, export_image_format="AUTO")
    return copy
