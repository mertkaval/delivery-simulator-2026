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


def _ground(col, size=600.0, z=-0.02):
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
    terrain.conform_terrain(ter, col, subdivide=2, reach=3.0)
    L = structures.road_length(main2)
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
    terrain.conform_terrain(ter, col, subdivide=1, reach=4.0)
    structures.gantry_sign(hw, 120.0, ("E4 NORTH", "EXIT 7  AIRPORT"), col)
    structures.gantry_sign(hw, 330.0, ("E4 NORTH",), col)
    sc["mrs_terrain"] = ter.name
    return sc


def roundabout_village():
    """Village: roundabout with four arms, cobblestone-ready residential streets, a bus stop, signs."""
    sc, col = _scene("MRS_Village")
    _ground(col)
    R = lambda n, pts, preset, **kw: roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, **kw)
    e = R("VL_East", [(0, 0, 0), (60, 5, 0), (130, 0, 0)], "residential", Tree_Side="Alternate", Tree_Spacing=16.0)
    w = R("VL_West", [(0, 0, 0), (-60, -5, 0), (-130, 0, 0)], "urban", Parking_Left=0.0, Parking_Right=0.0, Bike_Lane_Left=0.0, Bike_Lane_Right=0.0, Median=0.0, Lanes_Forward=1, Lanes_Backward=1, Lane_Width=3.5)
    n = R("VL_North", [(0, 0, 0), (5, 60, 0), (0, 130, 0)], "residential"); s = R("VL_South", [(0, 0, 0), (-5, -60, 0), (0, -130, 0)], "rural", Tree_Side="Both")
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
    terrain.conform_terrain(ter, col, subdivide=1, reach=3.0)
    structures.cable_stays(bridge, col, pylon_spacing=90.0, pylon_height=30.0)
    sc["mrs_terrain"] = ter.name
    return sc


ALL = {"city_block": city_block, "mountain_road": mountain_road, "highway": highway, "roundabout_village": roundabout_village, "bridge_valley": bridge_valley}


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
        "MRS_BridgeValley": [("over", (-120, -200, 90), (0, 0, 5), 35), ("deck", "road:BV_Bridge:0.1"), ("below", (0, -80, -2), (0, 0, 8), 30), ("east", "road:BV_East:0.3")],
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
