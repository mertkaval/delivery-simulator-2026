"""Re-pose each converted humanoid so its rest pose matches the animation library's rest pose.

blender --background --factory-startup --python tools/match_ual_rest.py -- [ids]

Godot's humanoid retargeting transfers each bone's motion relative to its rest. When a
character's rest differs from the library rig's (different spine curvature, A-pose vs T-pose
arms, hip tilt), that difference is added on top of every clip: people stood hunched with bent
knees and jutting heads. Here every body segment (joint to next joint) of the character is
rotated to point exactly like the library's, from the hips outward, the pose is baked into the
mesh and applied as the new rest. Retargeted clips then reproduce the library's posture.

Input/output: assets/sketchup/people/<id>.glb (backups in tmp/people_before_rest/).
Characters face Blender -Y (Godot +Z), like the library.
"""
import bpy, sys, os, shutil
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "assets", "sketchup", "people")
UAL = os.path.join(ROOT, "assets", "animations", "ual", "ual_standard.glb")
BACKUP = os.path.join(ROOT, "tmp", "people_before_rest")
IDS = ["casual_male_tshirt", "business_man_eric", "sophia", "casual_female", "casual_male_2"]
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if ARGS:
    IDS = [a for a in ARGS if a in IDS]

# Humanoid profile bone -> library (Rigify DEF-) bone.
UAL_NAMES = {"Hips": "DEF-hips", "Spine": "DEF-spine.001", "Chest": "DEF-spine.002", "UpperChest": "DEF-spine.003",
             "Neck": "DEF-neck", "Head": "DEF-head"}
for side, s in (("Left", "L"), ("Right", "R")):
    UAL_NAMES.update({side + "Shoulder": "DEF-shoulder." + s, side + "UpperArm": "DEF-upper_arm." + s,
                      side + "LowerArm": "DEF-forearm." + s, side + "Hand": "DEF-hand." + s,
                      side + "UpperLeg": "DEF-thigh." + s, side + "LowerLeg": "DEF-shin." + s,
                      side + "Foot": "DEF-foot." + s, side + "Toes": "DEF-toe." + s,
                      side + "MiddleProximal": "DEF-f_middle.01." + s})
# Segment from a bone's head to the head of the next joint (None = the bone's own tail).
# (Only joint-to-joint segments: bone tails of imported rigs point in arbitrary directions.)
SEGMENTS = [("Hips", "Spine"), ("Spine", "Chest"), ("Chest", "UpperChest"), ("UpperChest", "Neck"), ("Neck", "Head")]
for side in ("Left", "Right"):
    SEGMENTS += [(side + "UpperLeg", side + "LowerLeg"), (side + "LowerLeg", side + "Foot"), (side + "Foot", side + "Toes"),
                 (side + "Shoulder", side + "UpperArm"), (side + "UpperArm", side + "LowerArm"),
                 (side + "LowerArm", side + "Hand"), (side + "Hand", side + "MiddleProximal")]


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    return next(o for o in bpy.data.objects if o.type == 'ARMATURE')


def library_directions():
    arm = load(UAL)
    out = {}
    for a, b in SEGMENTS:
        bone = arm.data.bones[UAL_NAMES[a]]
        head = arm.matrix_world @ bone.head_local
        end = arm.matrix_world @ (arm.data.bones[UAL_NAMES[b]].head_local if b else bone.tail_local)
        out[a] = (end - head).normalized()
    return out


PROFILE = set(UAL_NAMES) | {"Root", "LeftEye", "RightEye", "Jaw"} | {
    s + f + p for s in ("Left", "Right") for f in ("Thumb", "Index", "Middle", "Ring", "Little")
    for p in ("Metacarpal", "Proximal", "Intermediate", "Distal")}


def dissolve_chain_helpers(arm, meshes):
    """Remove unmapped bones that sit between two profile bones (e.g. Mixamo Neck1/Neck2 between
    Neck and Head). The retargeter never drives them, so they kept their rest while the mapped
    bones around them moved, which tipped heads forward. Their weights go to their parent."""
    removed = []
    bones = arm.data.bones
    for b in list(bones):
        if b.name in PROFILE:
            continue
        if not any(c.name in PROFILE for c in b.children_recursive):
            continue
        parent = b.parent
        while parent is not None and parent.name not in PROFILE:
            parent = parent.parent
        if parent is None:
            continue
        removed.append((b.name, parent.name))
    for o in meshes:
        for name, parent in removed:
            src = o.vertex_groups.get(name)
            if src is None:
                continue
            dst = o.vertex_groups.get(parent) or o.vertex_groups.new(name=parent)
            for v in o.data.vertices:
                for g in v.groups:
                    if g.group == src.index and g.weight > 0:
                        dst.add([v.index], g.weight, 'ADD')
            o.vertex_groups.remove(src)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for name, parent in removed:
        b = eb.get(name)
        if b is None:
            continue
        for c in list(b.children):
            c.use_connect = False
            c.parent = eb[parent]
        eb.remove(b)
    bpy.ops.object.mode_set(mode='OBJECT')
    return [n for n, _ in removed]


def match(cid, target):
    path = os.path.join(PEOPLE, cid + ".glb")
    arm = load(path)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    gone = dissolve_chain_helpers(arm, meshes)
    print("  dissolved helper bones", gone, flush=True)
    # The library rest is the reference; this character's own clip (if any) would no longer fit.
    if arm.animation_data:
        arm.animation_data.action = None
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    pose = arm.pose.bones
    worst = 0.0
    for a, b in SEGMENTS:
        if a not in pose or (b and b not in pose):
            continue
        pb = pose[a]
        head = pb.head.copy()
        end = pose[b].head.copy() if b else pb.tail.copy()
        v = (end - head).normalized()
        t = target[a]
        R = v.rotation_difference(t).to_matrix().to_4x4()
        worst = max(worst, v.angle(t))
        pb.matrix = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ pb.matrix
        bpy.context.view_layer.update()
    # Bake the pose into the meshes, then make it the rest pose.
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in meshes:
        mod = next(m for m in o.modifiers if m.type == 'ARMATURE')
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in meshes:
        m = o.modifiers.new("Armature", 'ARMATURE')
        m.object = arm
    # Feet back on the ground (the hips re-pose can lift or lower the body slightly).
    zmin = min((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
    arm.location.z -= zmin
    bpy.ops.object.select_all(action='DESELECT')
    for o in [arm] + meshes:
        o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_animations=False, export_skins=True, export_def_bones=False,
                              export_image_format='AUTO', export_extras=True)
    print("MATCHED", cid, "largest segment correction %.1f deg" % (worst * 57.2958), "ground shift %.3f" % zmin, flush=True)


os.makedirs(BACKUP, exist_ok=True)
target = library_directions()
for cid in IDS:
    src = os.path.join(PEOPLE, cid + ".glb")
    if not os.path.exists(os.path.join(BACKUP, cid + ".glb")):
        shutil.copy2(src, os.path.join(BACKUP, cid + ".glb"))
    match(cid, target)
