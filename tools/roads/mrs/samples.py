"""Pre-made sample scenes (each in its own Blender scene): city block, mountain road, highway with an
overpass, roundabout village, cable-stayed bridge over a valley. `render_all()` makes the validation
renders for docs/roads/v2/."""
import bpy, math, os
from mathutils import Vector
from .nodes import depsgraph, set_scene, MRS
from . import roads, junction, structures, terrain, qa


def _scene(name):
    sc = bpy.data.scenes.get(name)
    if sc is None: sc = bpy.data.scenes.new(name)
    set_scene(sc)
    col = bpy.data.collections.get(name + "_Roads")
    if col is None:
        col = bpy.data.collections.new(name + "_Roads"); sc.collection.children.link(col)
    for o in list(col.all_objects): bpy.data.objects.remove(o)
    for ch in list(col.children): bpy.data.collections.remove(ch)
    return sc, col


def _ground(col, size=600.0, z=-0.12):      # well below the roads: a 2 cm gap z-fights in the viewport at distance
    me = bpy.data.meshes.new("MRS_Ground"); me.from_pydata([(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [], [(0, 1, 2, 3)])
    from .props import mat
    me.materials.append(mat(MRS + "Ground", (0.16, 0.24, 0.09), 0.95)); o = bpy.data.objects.new("MRS_GroundPlane", me); col.objects.link(o); return o


def city_block():
    """Flat city: avenue with bike lanes and parking, residential grid, T and 4-way junctions with
    traffic lights, a dead end, gantry, bus stop, signs."""
    sc, col = _scene("MRS_CityBlock")
    _ground(col)
    R = lambda n, pts, preset, **kw: roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, **kw)
    r = {}
    r["avW"] = R("CB_AvenueW", [(-160, 0, 0), (-120, 0, 0), (-80, 0, 0)], "urban"); r["avW2"] = R("CB_AvenueW2", [(-80, 0, 0), (-40, 0, 0), (0, 0, 0)], "urban"); r["avE"] = R("CB_AvenueE", [(0, 0, 0), (60, 0, 0), (120, 0, 0)], "urban")
    r["avE2"] = R("CB_AvenueE2", [(120, 0, 0), (170, 0, 0), (220, 0, 0)], "urban")
    r["n1"] = R("CB_North1", [(0, 0, 0), (0, 50, 0), (0, 100, 0)], "residential"); r["s1"] = R("CB_South1", [(0, 0, 0), (0, -50, 0), (0, -100, 0)], "residential")
    r["n2"] = R("CB_North2", [(120, 0, 0), (120, 50, 0), (120, 100, 0)], "residential")
    r["s2"] = R("CB_South2", [(120, 0, 0), (120, -50, 0), (120, -100, 0)], "service", Tree_Side="Right")
    r["x1"] = R("CB_Cross1", [(0, 100, 0), (60, 100, 0), (120, 100, 0)], "residential"); r["x2"] = R("CB_Cross2", [(0, -100, 0), (60, -100, 0), (120, -100, 0)], "residential")
    r["w1"] = R("CB_West1", [(-80, 0, 0), (-80, 50, 0), (-80, 100, 0)], "residential"); r["dead"] = R("CB_Dead", [(-80, 100, 0), (-110, 120, 0), (-140, 150, 0)], "residential")
    r["x3"] = R("CB_Cross3", [(-80, 100, 0), (-40, 100, 0), (0, 100, 0)], "residential")
    junction.build_junction("CB_J1", (0, 0, 0), [r["avW2"], r["avE"], r["n1"], r["s1"]], col, traffic_lights=True)
    junction.build_junction("CB_J2", (120, 0, 0), [r["avE"], r["avE2"], r["n2"], r["s2"]], col, traffic_lights=True)
    junction.build_junction("CB_J3", (0, 100, 0), [r["n1"], r["x1"], r["x3"]], col)
    junction.build_junction("CB_J4", (120, 100, 0), [r["n2"], r["x1"]], col, corner_radius=8.0)
    junction.build_junction("CB_J5", (0, -100, 0), [r["s1"], r["x2"]], col, corner_radius=8.0)
    junction.build_junction("CB_J6", (120, -100, 0), [r["s2"], r["x2"]], col, corner_radius=8.0, crosswalks=False)
    junction.build_junction("CB_J7", (-80, 0, 0), [r["avW"], r["avW2"], r["w1"]], col)
    junction.build_junction("CB_J8", (-80, 100, 0), [r["w1"], r["x3"], r["dead"]], col)
    junction.build_dead_end("CB_DeadEnd", r["dead"], "end", 9.0, col)
    structures.gantry_sign(r["avE"], 60.0, ("A12 NORTH", "CITY CENTRE"), col)
    structures.bus_stop(r["avW2"], 40.0, 1, col)
    structures.text_sign("MAIN STREET", (8, -12.5, 0), 0, col); structures.text_sign("30", (14, -12.5, 0), 0, col, "circle", (0.8, 0.05, 0.05), 0.7)
    return sc


def mountain_road(seed=3):
    """Hilly terrain, a winding rural road with embankments and cuts, a tunnel, a service branch."""
    sc, col = _scene("MRS_Mountain")
    ter = terrain.demo_terrain(name="MRS_MountainTerrain", size=500.0, step=4.0, height=26.0, seed=seed, collection=col)
    main = roads.make_road("MT_Main", [(-220, -120, 0), (-120, -60, 0), (-30, 10, 0), (60, 20, 0)], col, "rural", terrain=ter, Superelevation=7.0)
    main2 = roads.make_road("MT_Main2", [(60, 20, 0), (120, 90, 0), (200, 150, 0)], col, "rural", terrain=ter, Superelevation=7.0)
    br = roads.make_road("MT_Branch", [(60, 20, 0), (90, -40, 0), (140, -90, 0)], col, "service", terrain=ter, Tree_Side="Both")
    junction.build_junction("MT_J1", (60, 20, 0), [main, main2, br], col, crosswalks=False, stop_lines=False, terrain=ter, snap=1.0)
    terrain.conform_terrain(ter, col, subdivide=2)
    L = structures.road_length(main2)
    # a tunnel where a hill stands over the road (the straight grade between its portals runs under the ground)
    if structures.auto_tunnel(main2, ter, min_cover=6.0, collection=col) is None:
        structures.tunnel(main2, L * 0.45, L * 0.62, col)
    sc["mrs_terrain"] = ter.name
    return sc


def highway():
    """Dual carriageway with guardrails and superelevation on terrain, an overpass crossing it on
    pillars, slip-road style service road, gantry signs."""
    sc, col = _scene("MRS_Highway")
    ter = terrain.demo_terrain(name="MRS_HighwayTerrain", size=500.0, step=5.0, height=9.0, seed=11, collection=col)
    hw = roads.make_road("HW_Main", [(-240, -40, 0), (-120, -10, 0), (0, 0, 0), (120, 30, 0), (240, 20, 0)], col, "highway", terrain=ter, Light_Side="None")
    over = roads.make_road("HW_Overpass", [(20, -140, 0), (20, -60, 7.5), (20, 0, 8.5), (20, 60, 7.5), (20, 140, 0)], col, "bridge", terrain=ter, Pillar_Spacing=22.0, Lanes_Forward=1, Lanes_Backward=1)
    ramp_s = roads.make_road("HW_RampS", [(20, -140, 0), (20, -200, 0), (20, -260, 0)], col, "rural", terrain=ter, Tree_Side="None")
    ramp_n = roads.make_road("HW_RampN", [(20, 140, 0), (20, 200, 0), (20, 260, 0)], col, "rural", terrain=ter, Tree_Side="None")
    junction.build_junction("HW_JS", (20, -140, 0), [over, ramp_s], col, crosswalks=False, stop_lines=False, terrain=ter)
    junction.build_junction("HW_JN", (20, 140, 0), [over, ramp_n], col, crosswalks=False, stop_lines=False, terrain=ter)
    terrain.conform_terrain(ter, col, subdivide=2)
    structures.gantry_sign(hw, 120.0, ("E4 NORTH", "EXIT 7  AIRPORT"), col)
    structures.gantry_sign(hw, 330.0, ("E4 NORTH",), col)
    sc["mrs_terrain"] = ter.name
    return sc


def roundabout_village():
    """Village: roundabout with four arms, cobblestone-ready residential streets, a bus stop, signs."""
    sc, col = _scene("MRS_Village")
    _ground(col)
    R = lambda n, pts, preset, **kw: roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, **kw)
    e = R("VL_East", [(0, 0, 0), (60, 5, 0), (130, 0, 0)], "residential", Tree_Side="Alternate", Tree_Spacing=16.0, Sidewalk_Surface="Cobblestone")
    w = R("VL_West", [(0, 0, 0), (-60, -5, 0), (-130, 0, 0)], "urban", Parking_Left=0.0, Parking_Right=0.0, Bike_Left="None", Bike_Right="None", Median=0.0, Lanes_Forward=1, Lanes_Backward=1, Lane_Width=3.5)
    n = R("VL_North", [(0, 0, 0), (5, 60, 0), (0, 130, 0)], "residential", Sidewalk_Surface="Brick"); s = R("VL_South", [(0, 0, 0), (-5, -60, 0), (0, -130, 0)], "rural", Tree_Side="Both")
    junction.build_roundabout("VL_Roundabout", (0, 0, 0), [e, w, n, s], col, island_radius=10.0)
    structures.bus_stop(e, 60.0, 1, col); structures.bus_stop(e, 70.0, -1, col)
    structures.text_sign("MARKET SQUARE", (24, -8.5, 0), 0, col); structures.text_sign("50", (-30, 9.5, 0), math.pi, col, "circle", (0.8, 0.05, 0.05), 0.7)
    return sc


def bridge_valley():
    """A cable-stayed bridge over a valley between two mountain road sections."""
    sc, col = _scene("MRS_BridgeValley")
    ter = terrain.demo_terrain(name="MRS_ValleyTerrain", size=500.0, step=4.0, height=22.0, seed=7, collection=col)
    west = roads.make_road("BV_West", [(-230, -40, 0), (-150, -20, 0), (-90, 0, 0)], col, "rural", terrain=ter, Lock_End=True)
    bridge = roads.make_road("BV_Bridge", [(-90, 0, 0), (0, 0, 0), (90, 0, 0)], col, "bridge", terrain=ter, Pillar_Spacing=60.0)
    east = roads.make_road("BV_East", [(90, 0, 0), (150, 30, 0), (230, 60, 0)], col, "rural", terrain=ter)
    junction.build_junction("BV_J1", (-90, 0, 0), [west, bridge], col, crosswalks=False, stop_lines=False, terrain=ter)
    junction.build_junction("BV_J2", (90, 0, 0), [bridge, east], col, crosswalks=False, stop_lines=False, terrain=ter)
    terrain.conform_terrain(ter, col, subdivide=2)
    structures.cable_stays(bridge, col, pylon_spacing=90.0, pylon_height=30.0)
    sc["mrs_terrain"] = ter.name
    return sc


def street_block(wear="light_wear"):
    """The representative demonstration block (brief section 14): a straight avenue with a lane increase
    then a decrease, an S-curve, a T-junction (priority, parallel-line crossings) and a signalised
    four-way, painted / buffered / protected cycleways, planting strips, crossings with ramps, signs, a
    direction board, rule-placed lights / furniture / trees, a bus stop; `wear` = material preset."""
    from . import placement, materials
    sc, col = _scene("MRS_StreetBlock")
    _ground(col)
    R = lambda n, pts, preset, **kw: roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, **kw)
    r = {}
    r["avW"] = R("SB_AvenueW", [(-150, 0, 0), (-75, 0, 0), (0, 0, 0)], "urban", Median=1.8, Bike_Left="Protected", Bike_Right="Protected", Planting_Strip_Left=1.2, Planting_Strip_Right=1.2,
                 Sidewalk_Width_Left=4.0, Sidewalk_Width_Right=4.0, Transition=True, Lanes_Forward_End=3, Lanes_Backward_End=2, Transition_Start=45.0, Taper_Length=40.0)
    r["avE"] = R("SB_AvenueE", [(0, 0, 0), (60, 0, 0), (120, 0, 0)], "urban", Median=1.8, Bike_Left="Protected", Bike_Right="Protected", Planting_Strip_Left=1.2, Planting_Strip_Right=1.2,
                 Sidewalk_Width_Left=4.0, Sidewalk_Width_Right=4.0, Lanes_Forward=3, Transition=True, Lanes_Forward_End=2, Lanes_Backward_End=2, Transition_Start=35.0, Taper_Length=40.0)
    r["n"] = R("SB_North", [(0, 0, 0), (0, 45, 0), (0, 90, 0)], "residential", Bike_Right="Painted", Bike_Left="Painted", Sidewalk_Width_Left=3.0, Sidewalk_Width_Right=3.0)
    r["s"] = R("SB_South", [(0, 0, 0), (0, -45, 0), (0, -90, 0)], "residential", Sidewalk_Width_Left=3.2, Sidewalk_Width_Right=3.2, Planting_Strip_Left=1.0, Planting_Strip_Right=1.0)
    r["scurve"] = R("SB_SCurve", [(120, 0, 0), (160, 8, 0), (200, -8, 0), (240, 0, 0)], "residential", Bike_Right="Buffered", Sidewalk_Width_Left=3.0, Sidewalk_Width_Right=3.2, Planting_Strip_Right=1.0)
    r["t"] = R("SB_TSide", [(120, 0, 0), (120, -40, 0), (120, -80, 0)], "residential", Sidewalk_Width_Left=3.0, Sidewalk_Width_Right=3.0)
    names = {"SB_AvenueW": "HARBOUR AVE", "SB_AvenueE": "HARBOUR AVE", "SB_North": "MAPLE ST", "SB_South": "MAPLE ST", "SB_SCurve": "RIVER RD", "SB_TSide": "MILL LANE"}
    for o in r.values(): o["mrs_street_name"] = names[o.name]
    junction.build_junction("SB_J4", (0, 0, 0), [r["avW"], r["avE"], r["n"], r["s"]], col, control="signals", corner_radius=5.0, main_roads=["SB_AvenueW", "SB_AvenueE"])
    junction.build_junction("SB_JT", (120, 0, 0), [r["avE"], r["scurve"], r["t"]], col, control="priority", corner_radius=5.0, main_roads=["SB_AvenueE", "SB_SCurve"], crossing="parallel")
    try:
        from . import signage
        board = signage.make_direction_board("SB_Board", [("CITY CENTRE", "ahead"), ("HARBOUR", "right"), ("STATION", "left")], collection=col)
        p, t, rr = structures.road_sample(r["avW"], 30.0); w = roads.road_widths(r["avW"])
        board.location = p + rr * (w["half_r"] + w["curb"] + 1.0); board.rotation_euler = (0, 0, math.atan2(t.y, t.x) + math.pi / 2)
    except Exception as e:
        print("direction board skipped:", e)
    sc["mrs_block_version"] = 4
    block_v4_features(sc, col, r)
    materials.apply_material_preset(wear)
    return sc


SB_SPEEDS = {"SB_AvenueW": 50, "SB_AvenueE": 50, "SB_North": 30, "SB_South": 30, "SB_SCurve": 30, "SB_TSide": 30}
SB_BUS = [{"id": "S1", "road": "SB_South", "along": 52.0, "side": "r"},
          {"id": "S2", "road": "SB_North", "along": 50.0, "side": "l"}]          # serves the shop frontage (v5)
# v5 street frontage: a shop built from the city kit on Maple St (west side), service yard + dropped kerb north of it
SB_FRONTAGES = [{"id": "SB_Shop", "road": "SB_North", "side": "l", "along": 22.0, "bays": 4, "floors": 2, "depth": 12.0, "style": 1,
                 "name": "Halden Grocer", "number": 24, "street": "Maple St", "yard_side": "ahead", "yard_width": 9.0, "drive_width": 5.0}]


def _clear_of_footbridges(pts, width, margin=0.5):
    """True when a path polyline (world XY points, `width` m wide) keeps `margin` m from every footbridge
    approach path and does not pass under an approach (ramp / stairs footprint)."""
    import json as _json
    P = [Vector((p[0], p[1])) for p in pts]
    samples = []
    for a_, b_ in zip(P, P[1:]):
        n = max(1, int((b_ - a_).length / 0.5))
        samples += [a_.lerp(b_, i / n) for i in range(n + 1)]
    def seg_d(p, a_, b_):
        d = b_ - a_; L2 = d.length_squared
        f = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (p - a_).dot(d) / L2))
        return (a_ + d * f - p).length
    def inside(p, poly):
        c = False
        for i in range(len(poly)):
            a_, b_ = poly[i], poly[i - 1]
            if (a_.y > p.y) != (b_.y > p.y) and p.x < (b_.x - a_.x) * (p.y - a_.y) / (b_.y - a_.y + 1e-12) + a_.x: c = not c
        return c
    for o in bpy.data.objects:
        plan = o.get("mrs_footbridge_plan")
        if not plan: continue
        plan = _json.loads(plan)
        for e in plan.get("ped_edges", []):
            ap = [Vector((q[0], q[1])) for q in e.get("approach_path", [])]
            for a_, b_ in zip(ap, ap[1:]):
                if any(seg_d(p, a_, b_) < width / 2 + min(e.get("width", 2.5), 2.5) / 2 + margin for p in samples): return False
        # no low part of the bridge overhead or underfoot along the path (ray down onto the evaluated footbridge mesh)
        from mathutils.bvhtree import BVHTree
        dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        bvh = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [list(pg.vertices) for pg in me.polygons]); ev.to_mesh_clear()
        dd = (P[-1] - P[0]); nn = Vector((-dd.y, dd.x)).normalized() if dd.length > 1e-6 else Vector((1.0, 0.0))
        for p in samples:
            for off in (-width / 2, 0.0, width / 2):
                q = p + nn * off
                h = bvh.ray_cast(Vector((q.x, q.y, 30.0)), Vector((0, 0, -1)), 60.0)
                if h[0] is not None and h[0].z < 3.2: return False         # < ~2.5 m headroom under the structure (or on it)
    return True
SB_PARK = [(-140.0, -27.0), (-17.0, -27.0), (-17.0, -88.0), (-140.0, -88.0)]


def _pavilion(name, centre, size, yaw, col, door_side=-1):
    """Simple single-storey cafe pavilion (context for the entrance rule): rendered walls, glazed front,
    flat roof with an overhang, a door recess on the street side. Floor at sidewalk height."""
    import bmesh
    from .props import mat
    from .assets import _box
    bm = bmesh.new()
    w, d, h = size
    _box(bm, -w / 2, -d / 2, -0.3, w / 2, d / 2, 0.15, 2)                       # plinth
    _box(bm, -w / 2 + 0.1, -d / 2 + 0.1, 0.15, w / 2 - 0.1, d / 2 - 0.1, h, 0)  # walls
    _box(bm, -w / 2 - 0.6, -d / 2 - 0.6, h, w / 2 + 0.6, d / 2 + 0.6, h + 0.35, 2)  # roof slab
    fx = door_side * (w / 2 - 0.08)
    _box(bm, min(fx, fx + door_side * 0.06), -d / 2 + 0.6, 0.45, max(fx, fx + door_side * 0.06), d / 2 - 0.6, h - 0.4, 1)   # glazing band
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m_ in (mat(MRS + "PavilionRender", (0.78, 0.74, 0.66), 0.85), mat(MRS + "PavilionGlass", (0.12, 0.16, 0.18), 0.08, 0.2), mat(MRS + "PavilionTrim", (0.22, 0.22, 0.23), 0.6, 0.4)):
        me.materials.append(m_)
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.location = centre; o.rotation_euler = (0, 0, yaw)
    return o


def _lawn(o):
    """Lawn material for the demo ground: patchy greens, dry patches, fine bump (no flat green plane)."""
    from .props import mat
    m = mat(MRS + "Lawn", (0.16, 0.24, 0.09), 0.92)
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if not any(n.type == "TEX_NOISE" for n in nt.nodes):
        tc = nt.nodes.new("ShaderNodeTexCoord")
        n1 = nt.nodes.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 0.08; n1.inputs["Detail"].default_value = 4.0
        n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 3.0; n2.inputs["Detail"].default_value = 8.0
        for n_ in (n1, n2): nt.links.new(tc.outputs["Object"], n_.inputs["Vector"])
        rp = nt.nodes.new("ShaderNodeValToRGB")
        rp.color_ramp.elements[0].position = 0.35; rp.color_ramp.elements[0].color = (0.10, 0.17, 0.05, 1)
        rp.color_ramp.elements[1].position = 0.75; rp.color_ramp.elements[1].color = (0.24, 0.27, 0.11, 1)
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "FLOAT"; mix.inputs["Factor"].default_value = 0.35
        nt.links.new(n1.outputs["Fac"], mix.inputs[2]); nt.links.new(n2.outputs["Fac"], mix.inputs[3])
        nt.links.new(mix.outputs[0], rp.inputs["Fac"]); nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
        bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35; bp.inputs["Distance"].default_value = 0.02
        nt.links.new(n2.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs[0], b.inputs["Normal"])
    o.data.materials.clear(); o.data.materials.append(m)


def block_v4_features(sc, col, r, seed=7, footbridge_along=100.0, bus_stops=None):
    """v4 additions to the street block: footbridge on the avenue (anchor), furnished bus stop on the
    south street, a park in the south-west quadrant with paths to the bus stop / avenue / kiosk, a cafe
    pavilion with an entrance anchor, rule-based placement v4, park planting, entrance paths, route
    graphs (stored on the scene as JSON) and real street-light sources."""
    from . import placement, footbridge, routes
    import json as _json
    ground = next((o for o in col.objects if o.name.startswith(MRS + "GroundPlane")), None)
    if ground is not None: _lawn(ground)
    roads.set_road(r["s"], Sidewalk_Width_Right=4.6)
    roads.set_road(r["n"], Sidewalk_Width_Left=4.5)                     # the shop frontage side: room for the bus shelter and the shop door
    sc["mrs_frontages"] = __import__("json").dumps(SB_FRONTAGES)
    for o in r.values(): roads.set_road(o, Scatter_Density=0.0)       # planting strips belong to the landscape regions (placement v4)
    junction.rebuild_all()
    footbridge.ensure_group()
    fb_obj, plan = footbridge.make("SB_Footbridge", r["avW"], footbridge_along, col)
    print("FOOTBRIDGE", plan["status"], "; ".join(plan["messages"]))
    try:
        from . import lighting
        lighting.day_setup(sc)
    except Exception as e:
        print("lighting day setup skipped:", e)
    bcol = bpy.data.collections.get(col.name + "_Buildings") or bpy.data.collections.new(col.name + "_Buildings")
    if bcol.name not in [c.name for c in col.children]: col.children.link(bcol)
    for o in list(bcol.objects): bpy.data.objects.remove(o)
    _pavilion("SB_Cafe", Vector((16.5, 52.0, 0.0)), (8.0, 11.0, 3.6), 0.0, bcol, door_side=-1)
    ent = bpy.data.objects.get("MRS_Entrance_Cafe") or bpy.data.objects.new("MRS_Entrance_Cafe", None)
    if ent.name not in col.objects: col.objects.link(ent)
    ent.location = (11.8, 52.0, 0.15); ent["mrs_road"] = "SB_North"; ent["mrs_side"] = "r"; ent.empty_display_size = 1.0    # 0.7 m in front of the facade
    kiosk_src = bpy.data.objects.get(MRS + "Kiosk")
    if kiosk_src is not None:
        k = bpy.data.objects.new("SB_ParkKiosk", kiosk_src.data); bcol.objects.link(k); k.location = (-72.0, -66.0, -0.12)
    placement.RULES["landscape"] = {"SB_AvenueW:r": "park", "SB_South:r": "park"}
    sc["mrs_block_seed"] = seed
    return regenerate_block(sc, col, seed=seed, bus_stops=bus_stops)


def regenerate_block(sc, col, seed=None, bus_stops=None, rebuild_junctions=False):
    """Everything downstream of the roads, in dependency order: (junctions) -> footbridges (re-solved from
    their anchors) -> placement v4 -> entrance paths -> park -> route graphs -> scene JSON. Re-running it
    replaces the previous results (stable names, no multiplying)."""
    from . import placement, footbridge, routes
    import json as _json
    seed = sc.get("mrs_block_seed", 7) if seed is None else seed
    if rebuild_junctions: junction.rebuild_all()
    # street frontages (city-kit shops with entrance / service anchors), then the driveways they declare -> the
    # roads' dropped kerbs; everything below re-reads the anchors
    from . import frontage as _fr
    specs = _json.loads(sc.get("mrs_frontages", "[]"))
    _fr.clear(col, keep=[f["id"] for f in specs])
    fronts = [_fr.make_shop(f, col) for f in specs]
    print("FRONTAGE", [(f["id"], f["address"], round(f["along"], 1)) for f in fronts], "driveways", _fr.sync_driveways(col))
    footbridge.rebuild_all(col)
    r_ = {k: bpy.data.objects[n] for k, n in (("avW", "SB_AvenueW"), ("s", "SB_South"))}
    rep = placement.place_all(col, seed=seed, style="avenue", speed_limits=SB_SPEEDS, bus_stops=bus_stops if bus_stops is not None else SB_BUS)
    placement.entrance_paths(col, rep)
    # park paths start on the back edge of the sidewalks (computed from the road stations, not fixed points)
    bs = (rep.get("bus_stops") or [None])[0]
    ms = placement.RoadModel(r_["s"]); mw = placement.RoadModel(r_["avW"])
    a_bus = (bs["along"] + 4.0) if bs else ms.A0 + 40.0
    q_bus = ms.point(a_bus, "r", ms.sw["r"] - 0.05)[0]
    # the avenue path starts at the first station near 90 m whose first 9 m keep clear of the footbridge approaches
    # (v4 started it under the ramp foot, on top of the footbridge's own approach path: a 12 cm upstand between them)
    a_ave = 90.0
    for a_try in (90.0, 94.0, 86.0, 98.0, 82.0, 102.0, 78.0, 106.0, 74.0, 110.0, 70.0):
        q_try = mw.point(a_try, "r", mw.sw["r"] - 0.05)[0]
        if _clear_of_footbridges([(q_try.x, q_try.y), (q_try.x, q_try.y - 9.0)], 2.5): a_ave = a_try; break
    q_ave = mw.point(a_ave, "r", mw.sw["r"] - 0.05)[0]
    hub = Vector((-42.0, -64.0, 0.0))
    paths = [{"pts": [(q_bus.x, q_bus.y), (q_bus.x - 12.0, q_bus.y), (hub.x, hub.y)], "z_top": q_bus.z},                     # bus stop -> park hub
             {"pts": [(q_ave.x, q_ave.y), (q_ave.x, q_ave.y - 9.0), (-50.0, -45.0), (hub.x, hub.y)], "z_top": q_ave.z},          # avenue sidewalk -> hub
             {"pts": [(hub.x, hub.y), (-58.0, -66.0), (-70.4, -65.2)], "z_top": -0.09, "ramp": 0.01, "dest": "kiosk"}]           # hub -> kiosk
    park = placement.place_park(col, rep, "SB_Park", SB_PARK, paths=paths, seed=seed)
    print("PLACEMENT", rep["counts"], rep["by_kind"], "park", park)
    # landscape ground: mask (beds, tree bases, access wear, macro variation) + tiling grass / soil / worn textures
    from . import ground as _ground_mod
    for o in [o for o in col.objects if o.name.startswith(MRS + "GroundPlane")]: bpy.data.objects.remove(o)
    g_obj, g_rec = _ground_mod.build(col, rep, z=placement.RULES["ground_z"])
    print("GROUND", g_rec["bounds"], g_rec["mask"])
    rt = routes.build(col, rep)
    from . import movements as _mv
    mv = _mv.build(col, rt)                      # lane paths, curved junction movements, swept clearance; refines ped corners
    print("ROUTES", rt["stats"], "validation", len(rt["validation"]))
    print("MOVEMENTS", mv["stats"], "validation", len(mv["validation"]))
    for v in (rt["validation"] + mv["validation"])[:14]: print("   ", v)
    sc["mrs_movements"] = _json.dumps(mv, default=str)
    sc["mrs_placement_report"] = _json.dumps({k: v for k, v in rep.items() if not k.startswith("_") and k != "items"}, default=str)
    sc["mrs_placement_items"] = _json.dumps(rep["items"], default=str)
    sc["mrs_routes"] = _json.dumps(rt, default=str)
    return rep, rt


ALL = {"street_block": street_block, "city_block": city_block, "mountain_road": mountain_road, "highway": highway, "roundabout_village": roundabout_village, "bridge_valley": bridge_valley}


def build_all():
    return {k: f() for k, f in ALL.items()}


def render_all(out_dir):
    """Validation renders for every sample scene."""
    os.makedirs(out_dir, exist_ok=True)
    shots = {
        "MRS_CityBlock": [("over", (60, -60, 260), (40, 10, 0), 32), ("j1", (-30, -45, 20), (5, 5, 0), 35), ("street", (-6, -60, 1.8), (0, 0, 1), 28), ("gantry", (18, -14, 2.5), (62, 0, 4), 30)],
        "MRS_Mountain": [("over", (-40, -260, 220), (0, 20, 0), 35), ("bend", "road:MT_Main:0.35"), ("tunnel", "road:MT_Main2:0.3"), ("cut", "road:MT_Main2:0.8")],
        "MRS_Highway": [("over", (-80, -230, 150), (20, 0, 0), 35), ("under", (-50, -70, 2.5), (20, 0, 6), 32), ("drive", "road:HW_Main:0.2"), ("overpass", "road:HW_Overpass:0.4")],
        "MRS_Village": [("over", (-70, -120, 110), (0, 0, 0), 35), ("entry", "road:VL_South:0.85"), ("ring", (18, -26, 6), (0, 0, 1), 32), ("bus", "road:VL_East:0.35")],
        "MRS_BridgeValley": [("over", (-120, -200, 90), (0, 0, 5), 35), ("deck", "road:BV_Bridge:0.1"), ("below", (-30, -90, 2), (0, 0, 12), 30), ("east", "road:BV_East:0.3")],
        "MRS_StreetBlock": [("overhead", (45, -40, 190), (45, 0, 0), 30), ("driver", "road:SB_South:0.75"), ("cyclist", "road:SB_AvenueW:0.78"), ("pedestrian", (-14, -16.5, 1.65), (0, -11, 1.0), 32),
                            ("crossing", (7, -31, 3.2), (0, -23.5, 0.1), 40), ("curb", (-22, -21.5, 1.4), (-19.5, -17.6, 0.2), 45), ("tree", (-127, -26, 1.7), (-133.5, -17.6, 5.0), 40), ("material", (30, -1.0, 1.2), (36, 2.5, 0.0), 45),
                            ("taper", (-110, -40, 25), (-95, 0, 0), 35), ("tjunction", (95, -40, 22), (122, 0, 0), 35), ("scurve", "road:SB_SCurve:0.3")],
    }
    paths = []
    headless = getattr(bpy.context, "window", None) is None
    for scene_name, views in shots.items():
        sc = bpy.data.scenes.get(scene_name)
        if sc is None: continue
        if headless and sc != bpy.context.scene: continue       # background: only the --scene passed on the command line
        set_scene(sc)
        for v in views:
            name = v[0]; path = os.path.join(out_dir, "%s_%s.png" % (scene_name[4:].lower(), name))
            if isinstance(v[1], str):
                _, rn, t = v[1].split(":")
                qa.road_view(path, bpy.data.objects[rn], float(t), lateral=-1.6, height=1.7, ahead=45, lens=28, scene=sc)
            else:
                qa.render(path, v[1], v[2], v[3], scene=sc)
            paths.append(path)
    return paths
