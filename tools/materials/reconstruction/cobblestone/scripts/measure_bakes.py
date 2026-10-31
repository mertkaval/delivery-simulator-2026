"""Object-mode / UV-mode bakes for the audit: albedo + stone mask (Height normalised) on 1 m and 4 m planes.

    blender --background --factory-startup --python measure_bakes.py -- OUT_DIR [key=value ...group inputs]
"""
import json, os, sys
import bpy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
import procmat
from procmat import bake as B, core

procmat.discover(verbose=False)
procmat.build("cobblestone")
args = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(args[0]); os.makedirs(OUT, exist_ok=True)
over = {}
for a in args[1:]:
    k, v = a.split("="); over[k.replace("_", " ")] = float(v)
m = core.material("PM_Cobblestone"); n = core.group_node(m)
if over: core.set_inputs(n, **over)
ds = n.inputs["Displacement Strength"].default_value
grey = 0.31854677   # #999999 linear
n.inputs["Displacement Strength"].default_value = 1.0 / grey          # Height = mask 0..1
spp = 4
B.bake(m, OUT, tile=1.0, res=256, samples=spp, maps=["albedo", "height"], use_uv=False, plane_size=1.0, prefix="obj1m")
B.bake(m, OUT, tile=4.0, res=1024, samples=spp, maps=["albedo", "height", "normal"], use_uv=False, plane_size=4.0, prefix="obj4m")
B.bake(m, OUT, tile=4.0, res=1024, samples=spp, maps=["albedo", "height", "normal"], use_uv=True, prefix="uv4m")
n.inputs["Displacement Strength"].default_value = ds
print("MEASURE DONE")
