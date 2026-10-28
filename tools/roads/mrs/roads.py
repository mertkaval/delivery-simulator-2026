"""Road objects: curves with the MRS_Road modifier, presets, input access."""
import bpy
from mathutils import Vector
from .nodes import MRS, mod_input_set, mod_input_get

PRESETS = {
    "residential": {"Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 3.2, "Shoulder": 0.0, "Median": 0.0, "Sidewalk Left": True, "Sidewalk Right": True,
                    "Sidewalk Width Left": 2.0, "Sidewalk Width Right": 2.0, "Curb Height": 0.15, "Curb Width": 0.25, "Centre Line": "Dashed", "Edge Lines": False,
                    "Dash Length": 3.0, "Dash Gap": 6.0, "Marking Width": 0.12, "Prop Spacing": 28.0, "Prop Offset": 0.5, "Light Spacing": 30.0, "Light Side": "Alternate", "Prop Side": "None",
                    "Tree Side": "None", "Parking Left": 0.0, "Parking Right": 0.0, "Bike Left": "None", "Bike Right": "None", "Crown": 2.0, "Mode": "Ground",
                    "Barrier Left": "None", "Barrier Right": "None"},
    "urban": {"Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.5, "Shoulder": 0.0, "Median": 1.6, "Sidewalk Left": True, "Sidewalk Right": True,
              "Sidewalk Width Left": 3.5, "Sidewalk Width Right": 3.5, "Curb Height": 0.15, "Curb Width": 0.3, "Centre Line": "None", "Edge Lines": True,
              "Dash Length": 3.0, "Dash Gap": 4.5, "Marking Width": 0.12, "Prop Spacing": 24.0, "Prop Offset": 0.6, "Light Spacing": 28.0, "Light Side": "Both",
              "Tree Side": "Both", "Tree Spacing": 14.0, "Tree Offset": -2.0, "Parking Left": 2.2, "Parking Right": 2.2, "Bike Left": "Buffered", "Bike Right": "Buffered", "Bike Width": 1.8, "Crown": 2.0, "Mode": "Ground",
              "Barrier Left": "None", "Barrier Right": "None"},
    "highway": {"Lanes Forward": 2, "Lanes Backward": 2, "Lane Width": 3.7, "Shoulder": 2.5, "Median": 3.0, "Sidewalk Left": False, "Sidewalk Right": False,
                "Curb Height": 0.0, "Curb Width": 0.1, "Centre Line": "None", "Edge Lines": True, "Dash Length": 6.0, "Dash Gap": 12.0, "Marking Width": 0.15,
                "Prop Spacing": 60.0, "Prop Side": "None", "Light Spacing": 45.0, "Light Side": "Alternate", "Tree Side": "None", "Parking Left": 0.0, "Parking Right": 0.0,
                "Bike Left": "None", "Bike Right": "None", "Crown": 2.5, "Superelevation": 7.0, "Mode": "Ground", "Barrier Left": "Guardrail", "Barrier Right": "Guardrail",
                "Embankment Width": 9.0, "Lane Arrows": False},
    "rural": {"Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 3.5, "Shoulder": 1.0, "Median": 0.0, "Sidewalk Left": False, "Sidewalk Right": False,
              "Curb Height": 0.0, "Curb Width": 0.1, "Centre Line": "Dashed", "Edge Lines": True, "Dash Length": 3.0, "Dash Gap": 9.0, "Marking Width": 0.12,
              "Prop Spacing": 50.0, "Prop Side": "Alternate", "Light Side": "None", "Tree Side": "Alternate", "Tree Spacing": 18.0, "Tree Offset": 3.0, "Parking Left": 0.0, "Parking Right": 0.0,
              "Bike Left": "None", "Bike Right": "None", "Crown": 2.5, "Superelevation": 6.0, "Mode": "Ground", "Barrier Left": "None", "Barrier Right": "None",
              "Embankment Width": 5.0, "Lane Arrows": False},
    "service": {"Lanes Forward": 1, "Lanes Backward": 0, "Lane Width": 4.5, "Shoulder": 0.6, "Median": 0.0, "Sidewalk Left": False, "Sidewalk Right": False,
                "Curb Height": 0.12, "Curb Width": 0.2, "Centre Line": "None", "Edge Lines": True, "Dash Length": 2.0, "Dash Gap": 4.0, "Marking Width": 0.1,
                "Prop Spacing": 40.0, "Prop Offset": 0.8, "Light Side": "None", "Tree Side": "None", "Parking Left": 0.0, "Parking Right": 0.0, "Bike Left": "None", "Bike Right": "None",
                "Crown": 1.5, "Mode": "Ground", "Barrier Left": "None", "Barrier Right": "None", "Lane Arrows": False},
    "bridge": {"Lanes Forward": 1, "Lanes Backward": 1, "Lane Width": 3.5, "Shoulder": 0.5, "Median": 0.0, "Sidewalk Left": True, "Sidewalk Right": True,
               "Sidewalk Width Left": 1.8, "Sidewalk Width Right": 1.8, "Curb Height": 0.15, "Curb Width": 0.25, "Centre Line": "Solid", "Edge Lines": True,
               "Prop Side": "None", "Light Side": "Alternate", "Light Spacing": 24.0, "Tree Side": "None", "Parking Left": 0.0, "Parking Right": 0.0, "Bike Left": "None", "Bike Right": "None",
               "Crown": 1.5, "Mode": "Elevated", "Barrier Left": "Parapet", "Barrier Right": "Parapet", "Conform": False, "Embankment": False, "Lane Arrows": False},
}
COLLECTION_INPUTS = {"Props": "Props", "Streetlights": "Streetlights", "Trees": "Trees", "Manholes": "Manholes", "Drains": "Drains", "Markings Collection": "Markings",
                     "Pillars": "Pillars", "Barriers": "Barriers", "Scatter": "Scatter"}
MATERIAL_INPUTS = {"Asphalt Material": ("Asphalt",), "Marking Material": ("Paint",), "Concrete Material": ("Concrete",), "Paving Material": ("Paving", "Concrete"),
                   "Tactile Material": ("Tactile", "Paint"), "Cycleway Material": ("Cycleway", "BikeLane"), "Bus Lane Material": ("BusLane", "Cycleway", "BikeLane"),
                   "Structure Material": ("Structure",), "Embankment Material": ("Embankment",)}


def curve_object(name, points, collection, cyclic=False, kind="BEZIER"):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.resolution_u = 12
    if kind == "BEZIER":
        sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(points) - 1)
        for bp, p in zip(sp.bezier_points, points):
            bp.co = Vector(p); bp.handle_left_type = bp.handle_right_type = "AUTO"
    else:
        sp = cu.splines.new("POLY"); sp.points.add(len(points) - 1)
        for pp, p in zip(sp.points, points): pp.co = (*p, 1.0)
    sp.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, cu); collection.objects.link(o)
    return o


def make_road(name, points, collection, preset="residential", terrain=None, **overrides):
    """A road object: a Bezier curve through `points` with the MRS_Road modifier, a preset and
    optional overrides (socket names, spaces replaced by underscores allowed)."""
    o = curve_object(name, points, collection)
    add_road_modifier(o, preset, terrain=terrain, **overrides)
    return o


def add_road_modifier(o, preset="residential", terrain=None, **overrides):
    mod = o.modifiers.get("MRS_Road") or o.modifiers.new("MRS_Road", "NODES")
    mod.node_group = bpy.data.node_groups[MRS + "Road"]
    set_road(o, preset, terrain=terrain, **overrides)
    o["mrs_preset"] = preset
    return mod


def set_road(o, preset=None, terrain=None, **overrides):
    """Apply a preset and/or overrides; the applied values are remembered on the object
    (o["mrs_inputs"]) so `refresh_all()` can re-apply them after the node group is rebuilt."""
    mod = o.modifiers["MRS_Road"]
    vals = dict(PRESETS[preset]) if preset else {}
    vals.update({k.replace("_", " "): v for k, v in overrides.items()})
    stored = dict(o.get("mrs_inputs", {})) if preset is None else {}
    stored.update(vals); o["mrs_inputs"] = stored
    for k, v in vals.items(): mod_input_set(mod, k, v)
    for k, c in COLLECTION_INPUTS.items():
        if bpy.data.collections.get(MRS + c): mod_input_set(mod, k, bpy.data.collections[MRS + c])
    for k, names in MATERIAL_INPUTS.items():
        m = next((bpy.data.materials[MRS + n] for n in names if bpy.data.materials.get(MRS + n)), None)
        if m is not None: mod_input_set(mod, k, m)
    if terrain is not None:
        if isinstance(terrain, bpy.types.Collection): mod_input_set(mod, "Terrain Collection", terrain); o["mrs_terrain_col"] = terrain.name
        else: mod_input_set(mod, "Terrain", terrain); o["mrs_terrain"] = terrain.name
    o.update_tag()


def refresh_all(rebuild_junctions=True):
    """After `build_road_group()`: re-point every road at the group, re-apply its remembered inputs
    and rebuild the junctions (they set trims / height locks through the inputs)."""
    g = bpy.data.node_groups[MRS + "Road"]
    for o in all_roads():
        mod = o.modifiers["MRS_Road"]
        mod.node_group = None; mod.node_group = g
        # a rebuilt group issues new socket identifiers, so every value starts from the interface default
        for item in g.interface.items_tree:
            if getattr(item, "in_out", "") != "INPUT" or item.socket_type in ("NodeSocketGeometry", "NodeSocketObject", "NodeSocketCollection", "NodeSocketMaterial"): continue
            d = getattr(item, "default_value", None)
            if d is None or d == "": continue
            try: mod_input_set(mod, item.name, d)
            except Exception as e: print("default", item.name, e)
        inputs = dict(o.get("mrs_inputs", {}))
        if not inputs and o.get("mrs_preset"): inputs = dict(PRESETS[o["mrs_preset"]])
        ter = bpy.data.objects.get(o.get("mrs_terrain", "")) or bpy.data.collections.get(o.get("mrs_terrain_col", ""))
        set_road(o, None, terrain=ter, **{k.replace(" ", "_"): v for k, v in inputs.items()})
    if rebuild_junctions:
        from . import junction
        junction.rebuild_all()


def road_input(o, name):
    return mod_input_get(o.modifiers["MRS_Road"], name)


BIKE_KINDS = ("None", "Painted", "Buffered", "Protected", "Two-Way")


def bike_layout(o, side):
    """(buffer, width, protected, on) of the cycleway on a side ('l'/'r'), mirroring the node group."""
    kind = road_input(o, "Bike Right" if side == "r" else "Bike Left") or "None"
    idx = BIKE_KINDS.index(kind) if kind in BIKE_KINDS else 0
    on = idx > 0
    width = (road_input(o, "Bike Width") * (2.0 if idx == 4 else 1.0)) if on else 0.0
    buf = road_input(o, "Bike Buffer") if idx > 1 else 0.0
    return buf, width, idx > 2, on


def road_widths(o, at_end=None):
    """Half widths of the asphalt on each side, curb, sidewalks, curb height, cycleway layout (for the
    junction builder). `at_end` True uses the lane counts after a transition (end of the road)."""
    lw = road_input(o, "Lane Width"); med = road_input(o, "Median") * 0.5; sh = road_input(o, "Shoulder")
    rht = (road_input(o, "Driving Side") or "Right") == "Right"
    lf, lb = road_input(o, "Lanes Forward"), road_input(o, "Lanes Backward")
    if at_end and road_input(o, "Transition"): lf, lb = road_input(o, "Lanes Forward End"), road_input(o, "Lanes Backward End")
    lanes_r, lanes_l = (lb, lf) if rht else (lf, lb)
    out = dict(lw=lw, median=med * 2, curb=road_input(o, "Curb Width"), h=road_input(o, "Curb Height"), lanes_f=lf, lanes_b=lb, rht=rht)
    for s, lanes, pk in (("r", lanes_r, road_input(o, "Parking Right")), ("l", lanes_l, road_input(o, "Parking Left"))):
        buf, bw, prot, on = bike_layout(o, s)
        carr = med + lanes * lw; shd = carr + sh
        buf0 = shd if prot else shd + pk
        bike0 = buf0 + buf; bike1 = bike0 + bw
        park0 = bike1 if prot else shd; park1 = park0 + pk
        half = park1 if prot else bike1
        out["carr_" + s] = carr; out["bike0_" + s] = bike0; out["bike1_" + s] = bike1; out["bike_on_" + s] = on; out["bike_prot_" + s] = prot
        out["half_" + s] = half; out["lanes_" + s] = lanes
    out["half"] = max(out["half_l"], out["half_r"])
    out["swl"] = road_input(o, "Sidewalk Width Left") if road_input(o, "Sidewalk Left") else 0.0
    out["swr"] = road_input(o, "Sidewalk Width Right") if road_input(o, "Sidewalk Right") else 0.0
    return out


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


def all_roads(collection=None):
    objs = collection.all_objects if collection else bpy.data.objects
    return [o for o in objs if o.type == "CURVE" and "MRS_Road" in o.modifiers]
