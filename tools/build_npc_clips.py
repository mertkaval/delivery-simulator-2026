"""Extra townspeople clips authored on the Quaternius Universal Animation Library rig.

blender --background --factory-startup --python tools/build_npc_clips.py

The CC0 library (assets/animations/ual/ual_standard.glb) has walking, idles and sitting but no
carrying, phone or eating motion. Each new clip starts from a library clip (so legs, hips and
breathing stay the library's) and re-poses the arms / head per frame with an analytic two-bone
IK solved on the library rig (shoulder -> elbow -> wrist, elbow pole, palm direction):

  Idle_Carry, Walk_Carry     waiter: both forearms level in front, palms up under a tray
  Idle_Phone                 standing, right hand holding a phone at chest height, head down
  Sitting_Phone              seated, both hands on the phone in the lap, head down
  Sitting_Eat                seated at a table: left hand rests by the plate, right hand works
                             at the plate, lifts food to the mouth, chews, returns
  Idle_Look                  standing, head slowly turning to look along shop windows

Targets are offsets from the posed upper-chest joint in the character's frame (forward / left /
up), so they ride on the library clip's breathing and walking sway. Output (rig + mannequin
skin only, original clips removed): assets/animations/ual/ual_npc.glb. tools/setup_retarget.gd
gives it the same humanoid BoneMap as the library, and LivingAssets merges the clips.
"""
import bpy
import math
import os
from mathutils import Vector, Matrix, Quaternion

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "animations", "ual", "ual_standard.glb")
OUT = os.path.join(ROOT, "assets", "animations", "ual", "ual_npc.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
scene = bpy.context.scene
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
pose = arm.pose
bones = arm.data.bones
# Library character frame (Blender): faces -Y, left is +X, up +Z.
FWD, LEFT, UP = Vector((0, -1, 0)), Vector((1, 0, 0)), Vector((0, 0, 1))
originals = list(bpy.data.actions)
base_actions = {a.name: a for a in originals}


def P(name):
    return pose.bones[name]


def head_of(name):
    return (arm.matrix_world @ P(name).matrix).to_translation()


def update():
    bpy.context.view_layer.update()


def frame_vec(off):
    """(left, forward, up) -> armature-space vector."""
    return LEFT * off[0] + FWD * off[1] + UP * off[2]


def aim(name, direction, roll_ref=None):
    """Rotate pose bone `name` about its head so its Y axis points along `direction`."""
    pb = P(name)
    m = pb.matrix.copy()
    head = m.to_translation()
    rot = m.to_3x3()
    y = rot.col[1].normalized()
    q = y.rotation_difference(direction.normalized())
    new = (q.to_matrix() @ rot)
    pb.matrix = Matrix.Translation(head) @ new.to_4x4()
    update()


def twist(name, angle):
    pb = P(name)
    m = pb.matrix.copy()
    head = m.to_translation()
    rot = m.to_3x3()
    axis = rot.col[1].normalized()
    pb.matrix = Matrix.Translation(head) @ (Quaternion(axis, angle).to_matrix() @ rot).to_4x4()
    update()


def rotate_about(name, axis, angle):
    pb = P(name)
    m = pb.matrix.copy()
    head = m.to_translation()
    pb.matrix = Matrix.Translation(head) @ (Quaternion(axis, angle).to_matrix() @ m.to_3x3()).to_4x4()
    update()


# Palm normals in each hand bone's local frame, from the rest pose: the thumb lies on the palm
# side's leading edge, so palm = +-(hand axis x thumb direction).
PALM = {}
for s, sign in (("L", 1.0), ("R", -1.0)):
    hb = bones["DEF-hand." + s]
    h = (hb.tail_local - hb.head_local).normalized()
    t = (bones["DEF-thumb.01." + s].head_local - hb.head_local)
    t = (t - h * t.dot(h)).normalized()
    palm_world = h.cross(t) * sign
    PALM[s] = hb.matrix_local.to_3x3().inverted() @ palm_world
LEN = {s: ((bones["DEF-upper_arm." + s].tail_local - bones["DEF-upper_arm." + s].head_local).length,
           (bones["DEF-forearm." + s].tail_local - bones["DEF-forearm." + s].head_local).length) for s in "LR"}


def palm_dir(s):
    return (P("DEF-hand." + s).matrix.to_3x3() @ PALM[s]).normalized()


def arm_ik(s, wrist, pole, palm=None):
    """Two-bone IK: put the wrist (hand head) at `wrist`, elbow toward `pole`, palm toward `palm`."""
    up_n, fo_n, ha_n = "DEF-upper_arm." + s, "DEF-forearm." + s, "DEF-hand." + s
    l1, l2 = LEN[s]
    sh = P(up_n).matrix.to_translation()
    d = wrist - sh
    dist = min(d.length, (l1 + l2) * 0.985)
    d = d.normalized()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    p = pole - d * pole.dot(d)
    p = p.normalized() if p.length > 1e-6 else Vector((0, 0, -1))
    elbow = sh + d * a + p * h
    aim(up_n, elbow - sh)
    aim(fo_n, (sh + d * dist) - P(fo_n).matrix.to_translation())
    # Straight wrist: the hand continues the forearm.
    aim(ha_n, P(fo_n).matrix.to_3x3().col[1])
    if palm is not None:
        axis = P(fo_n).matrix.to_3x3().col[1].normalized()
        cur = palm_dir(s)
        want = palm - axis * palm.dot(axis)
        cur = cur - axis * cur.dot(axis)
        if want.length > 1e-4 and cur.length > 1e-4:
            ang = cur.normalized().angle(want.normalized())
            if cur.cross(want).dot(axis) < 0:
                ang = -ang
            twist(fo_n, ang)


def head_turn(yaw=0.0, pitch=0.0):
    """Turn neck + head: yaw about up (positive = to the character's left), pitch down positive."""
    for name, share in (("DEF-neck", 0.4), ("DEF-head", 0.6)):
        if yaw:
            rotate_about(name, UP, yaw * share)
        if pitch:
            rotate_about(name, LEFT, pitch * share)


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def chest():
    return P("DEF-spine.003").matrix.to_translation()


# --------------------------------------------------------------------------- pose programs

def carry(t, n):
    c = chest()
    for s, side in (("L", 1.0), ("R", -1.0)):
        w = c + frame_vec((side * 0.155, 0.30, -0.13))
        arm_ik(s, w, frame_vec((side * 0.35, -0.7, -1.0)), palm=UP)


def phone_standing(t, n):
    c = chest()
    bob = math.sin(t / n * math.tau) * 0.006
    arm_ik("R", c + frame_vec((-0.07, 0.28, -0.07 + bob)), frame_vec((-0.6, -0.4, -1.0)),
           palm=(UP + FWD * -0.9 + LEFT * 0.25).normalized())
    head_turn(yaw=-0.06, pitch=0.42)


def phone_sitting(t, n):
    c = chest()
    bob = math.sin(t / n * math.tau) * 0.005
    for s, side in (("L", 1.0), ("R", -1.0)):
        arm_ik(s, c + frame_vec((side * 0.06, 0.30, -0.19 + bob)), frame_vec((side * 0.7, -0.3, -1.0)),
               palm=(UP + FWD * -0.6 - LEFT * side * 0.5).normalized())
    head_turn(pitch=0.5)


def eat(t, n):
    """Right hand: plate (with a small cutting motion) -> mouth -> chew -> plate."""
    c = chest()
    x = t / n
    lift = smooth((x - 0.36) / 0.14) * (1 - smooth((x - 0.62) / 0.16))
    cut = math.sin(x * math.tau * 6) * 0.018 * (1 - lift)
    plate = c + frame_vec((-0.12, 0.42 + cut, -0.26))
    mouth = P("DEF-head").matrix.to_translation() + frame_vec((-0.05, 0.16, -0.075))
    w = plate.lerp(mouth, lift)
    palm = (-UP).lerp((LEFT * 0.8 - FWD * 0.6).normalized(), lift).normalized()
    arm_ik("R", w, frame_vec((-0.8, -0.2, -1.0)), palm=palm)
    arm_ik("L", c + frame_vec((0.17, 0.38, -0.27)), frame_vec((0.8, -0.2, -1.0)), palm=-UP)
    head_turn(pitch=0.32 * (1 - lift) + 0.05)


def look(t, n):
    x = t / n
    head_turn(yaw=0.5 * math.sin(x * math.tau) + 0.08 * math.sin(x * math.tau * 3), pitch=0.08 + 0.06 * math.sin(x * math.tau * 2))


CLIPS = [
    # name (Godot strips _Loop and loops it), base library action, length in seconds, program
    ("Idle_Carry_Loop", "Idle_Loop", 2.5, carry),
    ("Walk_Carry_Loop", "Walk_Loop", None, carry),
    ("Idle_Phone_Loop", "Idle_Loop", 5.0, phone_standing),
    ("Sitting_Phone_Loop", "Sitting_Idle_Loop", 5.0, phone_sitting),
    ("Sitting_Eat_Loop", "Sitting_Idle_Loop", 5.0, eat),
    ("Idle_Look_Loop", "Idle_Loop", 7.5, look),
]

fps = scene.render.fps / scene.render.fps_base
if not arm.animation_data:
    arm.animation_data_create()
new_actions = []
for name, base_name, seconds, program in CLIPS:
    base = base_actions[base_name]
    b0, b1 = base.frame_range
    blen = b1 - b0
    frames = int(round(seconds * fps)) if seconds else int(round(blen))
    samples = []
    for f in range(frames):
        arm.animation_data.action = base
        if base.slots:
            arm.animation_data.action_slot = base.slots[0]
        scene.frame_set(int(b0 + (f % blen)))
        update()
        program(f, frames)
        samples.append({pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.scale.copy()) for pb in pose.bones})
    act = bpy.data.actions.new(name)
    arm.animation_data.action = act
    for f in range(frames + 1):
        data = samples[f % frames]
        for pb in pose.bones:
            loc, rot, scl = data[pb.name]
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scl
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.keyframe_insert("scale", frame=f)
    act.use_fake_user = True
    new_actions.append(act)
    print("CLIP", name, "frames", frames, "base", base_name)

for a in originals:
    bpy.data.actions.remove(a)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name != "Mannequin":
        bpy.data.objects.remove(o)
# The glTF importer leaves one NLA track per library clip; export only the new actions.
for t in list(arm.animation_data.nla_tracks):
    arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = new_actions[0]
print("ACTIONS", [(a.name, len(a.layers[0].strips[0].channelbags[0].fcurves) if a.layers else -1) for a in bpy.data.actions])
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_yup=True, export_animations=True,
                          export_animation_mode='ACTIONS', export_force_sampling=True, export_frame_step=1,
                          export_optimize_animation_size=False, export_materials='EXPORT', export_cameras=False,
                          export_lights=False)
print("EXPORTED", OUT, os.path.getsize(OUT))
