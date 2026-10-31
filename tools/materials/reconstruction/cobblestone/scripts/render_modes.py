"""Eye-level 7 m x 20 m strip: object mode (live), UV mode (live, Tile 4 m), baked 4 m tile (what a game shows).
    blender -b --factory-startup --python render_modes.py -- OUT_DIR BAKE_DIR"""
import os, sys, math
import bpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
import procmat
from procmat import bake as B, core, rig
procmat.discover(verbose=False); procmat.build("cobblestone")
a = sys.argv[sys.argv.index("--") + 1:]; OUT = os.path.abspath(a[0]); BK = os.path.abspath(a[1])
m = core.material("PM_Cobblestone"); n = core.group_node(m)
sc = rig.scene("PM_Rig", "CYCLES", 64, (1280, 720), True, "AgX", "courtyard", 1.0, 0.0)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); rig.collection(sc).objects.link(sun)
sun.data.energy = 4.0; sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
strip = rig.road_strip(sc, uv_scale=0.25)
rig.camera(sc, "eye", strip)
paths = {"albedo": BK + "/PM_Cobblestone_albedo.png", "normal": BK + "/PM_Cobblestone_normal.png",
         "roughness": BK + "/PM_Cobblestone_roughness.png"}
baked = B.baked_material("PMV_CobbleBaked", paths)
for tag, mat, uv in (("object", m, 0.0), ("uv", m, 1.0), ("baked", baked, None)):
    rig.assign(strip, mat)
    if uv is not None:
        n.inputs["Use UV"].default_value = uv; n.inputs["Tile Size"].default_value = 4.0
    rig.render(os.path.join(OUT, "eye_%s.png" % tag), (1280, 720), scene=sc)
    # close look 1.7 m above, looking down 60 deg at 1 m distance
cam = sc.camera; rig.look_at(cam, (0.0, 1.0, 1.7), (0.0, 2.6, 0.0)); cam.data.lens = 35
for tag, mat, uv in (("object", m, 0.0), ("uv", m, 1.0)):
    rig.assign(strip, mat); n.inputs["Use UV"].default_value = uv
    rig.render(os.path.join(OUT, "near_%s.png" % tag), (1280, 720), scene=sc)
n.inputs["Use UV"].default_value = 0.0
print("RENDER DONE")
