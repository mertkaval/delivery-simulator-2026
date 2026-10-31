"""Road-tool compatibility check for PM_Cobblestone (nothing is saved).

blender --background tmp/roads/city/base.blend --python road_check.py -- LIBRARY.blend [N_ROADS]

Appends PM_Cobblestone from a library .blend saved by run.py (--save), assigns it to the "Paving Material" (and, on the
first road, also the "Asphalt Material") socket of the first N roads with procmat.road_adapter, and prints the
evaluated face counts per material. Prints ROAD OK / ROAD FAIL.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if LIB not in sys.path: sys.path.insert(0, LIB)

from procmat import core, road_adapter as RA  # noqa: E402


def main(argv):
    lib = os.path.abspath(argv[0]); n = int(argv[1]) if len(argv) > 1 else 3
    core.append_materials(lib, ["PM_Cobblestone"])
    mat = core.material("PM_Cobblestone")
    print("[road] contract", core.check_contract(mat) or "OK")
    roads = RA.roads()
    print("[road] roads in file:", len(roads))
    if not roads:
        # base.blend holds the road tool's node groups but no road: build one with the road tool's own make_road()
        # (as tools/materials/tests/test_core.py does; no .pyc under tools/roads, the file is never saved)
        import bpy
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.join(LIB, "..", "roads"))
        from mrs import roads as mrs_roads, nodes as mrs_nodes
        sc = bpy.data.scenes.new("PM_CobbleRoadTest"); mrs_nodes.set_scene(sc)
        col = bpy.data.collections.new("PMC_Roads"); sc.collection.children.link(col)
        mrs_roads.make_road("PMC_Road", [(-30.0, 0.0, 0.0), (0.0, 0.0, 0.0), (30.0, 0.0, 0.0)], col, "residential",
                            Conform=False, Embankment=False)
        roads = RA.roads(col)
        print("[road] built", [o.name for o in roads])
    ok = False
    for i, o in enumerate(roads[:n]):
        socks = RA.material_sockets(o)
        if "Paving Material" not in socks: continue
        rep = RA.assign(o, "Paving Material", mat)
        print("[road] assign", {k: (v.name if hasattr(v, "name") else v) for k, v in rep.items()})
        if i == 0 and "Asphalt Material" in socks:
            rep2 = RA.assign(o, "Asphalt Material", mat)
            print("[road] assign", {k: (v.name if hasattr(v, "name") else v) for k, v in rep2.items()})
        ev = RA.evaluated_materials(o)
        print("[road] evaluated", o.name, ev)
        ok |= ev.get("PM_Cobblestone", 0) > 0
    if ok and len(argv) > 2:
        import bpy
        from procmat import rig
        o = roads[0]; sc = o.users_scene[0]
        rig.set_engine(sc, "EEVEE", 32); rig.world(sc, "courtyard", 1.0)
        sc.render.resolution_x, sc.render.resolution_y = 1280, 720
        try: sc.view_settings.view_transform = "AgX"
        except TypeError: pass
        cam = bpy.data.objects.new("PMC_Cam", bpy.data.cameras.new("PMC_Cam")); sc.collection.objects.link(cam)
        cam.data.lens = 30.0; sc.camera = cam
        from mathutils import Vector
        rig.look_at(cam, Vector((-6.0, -4.5, 1.7)), Vector((4.0, 0.5, 0.0)))
        sun = bpy.data.objects.new("PMC_Sun", bpy.data.lights.new("PMC_Sun", "SUN")); sc.collection.objects.link(sun)
        sun.data.energy = 3.0; rig.look_at(sun, Vector((-5, -8, 10)), Vector((0, 0, 0)))
        print("[road] render", rig.render(os.path.abspath(argv[2]), scene=sc))
    return ok


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    good = False
    try: good = main(argv)
    except Exception:
        import traceback; traceback.print_exc()
    print("ROAD OK" if good else "ROAD FAIL")
    sys.exit(0 if good else 1)
