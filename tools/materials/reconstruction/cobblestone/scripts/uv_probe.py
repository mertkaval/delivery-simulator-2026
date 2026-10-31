"""Bake internal texture outputs of PM_Cobblestone in object mode (3D twin) and UV mode (4D twin) to compare
their distributions.   blender -b --factory-startup --python probe.py -- OUT_DIR"""
import os, sys
import bpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")))
import procmat
from procmat import bake as B, core

procmat.discover(verbose=False); procmat.build("cobblestone")
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1]); os.makedirs(OUT, exist_ok=True)
m = core.material("PM_Cobblestone"); t = bpy.data.node_groups["PM_Cobblestone"]
go = next(n for n in t.nodes if n.bl_idname == "NodeGroupOutput")
h_in = go.inputs["Height"]; orig = h_in.links[0].from_socket
PROBES = [("dist_noise", "Color", 1.0), ("dirt_noise", "Fac", 1.0), ("dmoss_noise", "Fac", 1.0),
          ("rock_noise", "Fac", 1.0), ("rmmask_noise", "Fac", 1.0), ("rmoss_noise", "Fac", 1.0),
          ("cell_vor_smooth", "Distance", 1.0), ("cell_vor_f1", "Distance", 1.0), ("rock_vor", "Distance", 1.0)]
for nid, out, gain in PROBES:
    for mode, suf in (("obj", "_3d"), ("uv", "_4d")):
        src = t.nodes[nid + suf].outputs[out]
        t.links.new(src, h_in)
        B.bake(m, OUT, tile=4.0, res=512, samples=1, maps=["height"], use_uv=(mode == "uv"), plane_size=4.0,
               prefix="%s_%s_%s" % (mode, nid, out), verbose=False)
t.links.new(orig, h_in)
print("PROBE DONE")
