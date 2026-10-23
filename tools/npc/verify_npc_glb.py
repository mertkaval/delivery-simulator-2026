"""Re-import an NPC GLB into an empty scene, report what the game will receive and render it with the
arms down (proves skinning, textures and alpha survived the export).

usage: blender --background --factory-startup --python tools/npc/verify_npc_glb.py -- <in.glb> <out.png>
"""
import bpy, sys
from mathutils import Vector, Matrix

glb, out_png = sys.argv[sys.argv.index("--") + 1:][:2]
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=glb)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
print("ROOT", arm.name, "bones", len(arm.data.bones), "extras", {k: arm[k] for k in arm.keys() if not k.startswith("_")})
tris = 0
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    t = sum(len(p.vertices) - 2 for p in o.data.polygons)
    tris += t
    maxinf = max((len([g for g in v.groups if g.weight > 0]) for v in o.data.vertices), default=0)
    unweighted = sum(1 for v in o.data.vertices if sum(g.weight for g in v.groups) < 0.5)
    mats = []
    for s in o.material_slots:
        m = s.material
        imgs = sorted({n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
        mats.append((m.name, getattr(m, "surface_render_method", ""), imgs))
    print("MESH", o.name, "tris", t, "max_influences", maxinf, "unweighted", unweighted, "uv", len(o.data.uv_layers), mats)
print("TOTAL_TRIS", tris)

# arms down, then a quick studio render
bpy.context.view_layer.objects.active = arm
arm.data.pose_position = "POSE"


def aim(bone, d):
    pb = arm.pose.bones[bone]
    bpy.context.view_layer.update()
    m = pb.matrix.copy()
    cur = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
    q = cur.rotation_difference(Vector(d).normalized())
    h = m.translation.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ m
    bpy.context.view_layer.update()


for s, sx in (("l", 1), ("r", -1)):
    if "upperarm_" + s in arm.pose.bones:
        aim("upperarm_" + s, (sx * 0.16, 0.02, -0.99))
        aim("lowerarm_" + s, (sx * 0.08, -0.25, -0.97))
scn = bpy.context.scene
for n, e, loc in (("Key", 380, (1.6, -2.4, 2.2)), ("Fill", 180, (-2.2, -1.8, 1.6)), ("Back", 160, (0.6, 2.6, 2.2))):
    ld = bpy.data.lights.new(n, "AREA")
    ld.energy, ld.size = e, 2.5
    lo = bpy.data.objects.new(n, ld)
    scn.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 1.2)) - lo.location).to_track_quat("-Z", "Y").to_euler()
w = bpy.data.worlds.new("W")
scn.world = w
w.color = (0.12, 0.12, 0.12)
cams = []
for i, loc in enumerate(((0, -3.6, 1.0), (2.5, -2.6, 1.1))):
    cam = bpy.data.objects.new("Cam%d" % i, bpy.data.cameras.new("Cam%d" % i))
    scn.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector((0, 0, 0.88)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cams.append(cam)
scn.view_settings.view_transform = "AgX"
scn.view_settings.exposure = -0.45
scn.render.resolution_x, scn.render.resolution_y = 600, 900
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scn.render.engine = eng
        break
    except TypeError:
        pass
for i, cam in enumerate(cams):
    scn.camera = cam
    scn.render.filepath = out_png.replace(".png", "_%d.png" % i)
    bpy.ops.render.render(write_still=True)
print("VERIFY_DONE")
