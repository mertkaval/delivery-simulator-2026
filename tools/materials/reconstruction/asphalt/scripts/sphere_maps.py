"""Equirectangular maps of a PM material's Albedo over the video's sphere (icosphere, subdivisions 6, radius 1 m,
object space), seen from a panoramic camera at the sphere centre, plus a position map that calibrates the mapping.
Used by view_match.py to find the video camera's view direction (object mode reproduces the video's exact 3D fields).

    blender --background --factory-startup --python sphere_maps.py -- OUT_DIR [--res 2048] [--material PM_Asphalt]

Writes OUT_DIR/albedo_pano.png and OUT_DIR/position_pano.png (16-bit PNG, view transform Raw: stored values are the
linear emission; position = Object x 0.5 + 0.5). Headless only; never the user's Blender."""
import argparse
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))          # tools/materials
if LIB not in sys.path: sys.path.insert(0, LIB)
import procmat  # noqa: E402
from procmat import core, rig  # noqa: E402


def emit_material(name, build_out):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
    nt.links.new(build_out(nt), em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("out"); p.add_argument("--res", type=int, default=2048); p.add_argument("--material", default="PM_Asphalt")
    p.add_argument("--samples", type=int, default=16)
    a = p.parse_args(argv)
    procmat.discover(verbose=False); procmat.build("asphalt")
    src = core.material(a.material); grp = core.group_node(src)
    sc = bpy.data.scenes.new("PM_Maps")
    rig.set_engine(sc, "CYCLES", a.samples, True, denoise=False)
    sc.render.resolution_x, sc.render.resolution_y = a.res, a.res // 2; sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Raw"; sc.view_settings.look = "None"
    st = sc.render.image_settings; st.file_format = "PNG"; st.color_mode = "RGB"; st.color_depth = "16"
    sc.cycles.max_bounces = 0
    w = bpy.data.worlds.new("black"); sc.world = w
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=6, radius=1.0)
    for f in bm.faces: f.smooth = True
    me = bpy.data.meshes.new("VideoSphere"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("VideoSphere", me); sc.collection.objects.link(ob)
    cd = bpy.data.cameras.new("Pano"); cd.type = "PANO"; cd.panorama_type = "EQUIRECTANGULAR"; cd.clip_start = 0.01
    cam = bpy.data.objects.new("Pano", cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0.0, 0.0, 0.0); cam.rotation_euler = (0.0, 0.0, 0.0)

    def albedo_out(nt):
        g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = grp.node_tree
        for s in grp.inputs:
            if hasattr(s, "default_value") and s.name in g.inputs: g.inputs[s.name].default_value = s.default_value
        return g.outputs["Albedo"]

    def position_out(nt):
        tc = nt.nodes.new("ShaderNodeTexCoord")
        vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
        nt.links.new(tc.outputs["Object"], vm.inputs[0]); vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        return vm.outputs[0]

    os.makedirs(a.out, exist_ok=True)
    for name, fn in (("albedo", albedo_out), ("position", position_out)):
        me.materials.clear(); me.materials.append(emit_material("PM_Map_" + name, fn))
        sc.render.filepath = os.path.join(os.path.abspath(a.out), "%s_pano.png" % name)
        bpy.ops.render.render(write_still=True, scene=sc.name)
        # Pillow reads 16-bit RGB PNGs as 8-bit: hand the values over as float32 .npy (rows top-down)
        import numpy as np
        img = bpy.data.images.load(sc.render.filepath, check_existing=False)
        img.colorspace_settings.name = "Non-Color"
        wd, ht = img.size; px = np.empty(wd * ht * img.channels, dtype=np.float32); img.pixels.foreach_get(px)
        np.save(os.path.join(os.path.abspath(a.out), "%s_pano.npy" % name), px.reshape(ht, wd, img.channels)[::-1, :, :3].copy())
        bpy.data.images.remove(img)
        print("[maps] wrote", sc.render.filepath)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
