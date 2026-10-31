"""Sweep the UV-mode cell gain: UV-mode stone mask bakes (4 m, 1024 px) for several gains, at Individual Size values.
    blender -b --factory-startup --python sweep.py -- OUT_DIR"""
import os, sys
import bpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
import procmat
from procmat import bake as B, core
procmat.discover(verbose=False); procmat.build("cobblestone")
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1]); os.makedirs(OUT, exist_ok=True)
m = core.material("PM_Cobblestone"); n = core.group_node(m); t = bpy.data.node_groups["PM_Cobblestone"]
n.inputs["Displacement Strength"].default_value = 1.0 / 0.31854677
for ind in (0.4, 0.6, 0.8):
    n.inputs["Cobblestone Individual Size"].default_value = ind
    B.bake(m, OUT, 4.0, 1024, 1, ["height"], use_uv=False, plane_size=4.0, prefix="obj_i%.1f" % ind, verbose=False)
    for k in ((1.0, 0.8, 0.7, 0.6, 0.5) if ind == 0.6 else (0.7,)):
        t.nodes["uv_smooth_gain"].outputs[0].default_value = k
        B.bake(m, OUT, 4.0, 1024, 1, ["height"], use_uv=True, prefix="uv_i%.1f_k%.2f" % (ind, k), verbose=False)
print("SWEEP DONE")
