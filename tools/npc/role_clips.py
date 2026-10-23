"""Role clips for the townspeople, authored on the MPFB game_engine rig of the v3 courier (every NPC
shares that rig, so Godot retargets one library onto all of them through the humanoid profile).

  blender --background source_assets/character_mpfb/courier_v3_animated.blend --python tools/npc/role_clips.py -- <out.glb>

Standing clips take their legs, hips and breathing from the courier's Idle_Loop and place the arms
with an analytic two-bone IK on hand targets (rig space: metres, -Y forward), the hands gripping:
  Sweep_Loop          a push broom swept side to side, bent forward, eyes on the ground
  Counter_Work_Loop   working at a counter (barista, cook, baker, cashier): right hand stirring /
                      kneading, left hand steadying, head down
  Duty_Stand_Loop     police / security: thumbs in the belt, weight shifting, scanning the street
  Photo_Take_Loop     tourist: phone held up in front of the face in both hands
Walking variants copy Walk_Loop and replace the arms:
  Walk_Leash_Loop     left hand forward-down holding a dog leash, right arm swinging
  Walk_Push_Loop      both hands on a stroller / cart handle
"""
import bpy, math, sys
from mathutils import Vector, Matrix, Quaternion

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else r"C:\GodotProjects\delivery-simulator-2026\assets\people\npc_role_clips.glb"
rig = bpy.data.objects["Courier"]
scn = bpy.context.scene
bpy.context.view_layer.objects.active = rig
FPS = 30
ARM = {"l": ("upperarm_l", "lowerarm_l", "hand_l"), "r": ("upperarm_r", "lowerarm_r", "hand_r")}
FINGERS = ["thumb", "index", "middle", "ring", "pinky"]


def fcurves(action):
    """Blender 5 layered actions: the F-curves of the first slot's channel bag."""
    if hasattr(action, "fcurves") and action.fcurves is not None and len(action.fcurves):
        return action.fcurves
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                return bag.fcurves
    return []


def eval_action(action, frame):
    rig.animation_data.action = action
    if hasattr(rig.animation_data, "action_slot") and action.slots:
        rig.animation_data.action_slot = action.slots[0]
    scn.frame_set(int(frame))
    bpy.context.view_layer.update()


def wpos(bone, tail=False):
    pb = rig.pose.bones[bone]
    return rig.matrix_world @ (pb.tail if tail else pb.head)


def aim(bone, d):
    """Turn a pose bone (minimal rotation) so its +Y points along world direction d."""
    pb = rig.pose.bones[bone]
    bpy.context.view_layer.update()
    m = pb.matrix.copy()
    cur = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
    q = cur.rotation_difference(Vector(d).normalized())
    h = m.translation.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ m
    bpy.context.view_layer.update()


def reach(side, target, pole, hand_dir):
    """Analytic two-bone IK: shoulder -> elbow -> wrist onto `target`, elbow towards `pole`."""
    up, lo, hand = ARM[side]
    S = wpos(up)
    a = (wpos(up, True) - S).length
    b = (wpos(lo, True) - wpos(lo)).length
    T = Vector(target)
    d = min((T - S).length, a + b - 0.002)
    axis = (T - S).normalized()
    along = (a * a - b * b + d * d) / (2 * d)
    h = math.sqrt(max(a * a - along * along, 0.0))
    p = Vector(pole) - axis * Vector(pole).dot(axis)
    p = p.normalized() if p.length > 1e-6 else Vector((0, 0, -1))
    E = S + axis * along + p * h
    aim(up, E - S)
    aim(lo, (S + axis * d) - wpos(lo))
    aim(hand, hand_dir)


def grip(side, amount=1.0):
    """Curl the fingers round a handle (rest-relative X rotation of every finger joint)."""
    for f in FINGERS:
        for j in (1, 2, 3):
            n = "%s_%02d_%s" % (f, j, side)
            if n not in rig.pose.bones:
                continue
            pb = rig.pose.bones[n]
            ang = (0.55 if f == "thumb" else (0.9 if j == 1 else 1.05)) * amount
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = Quaternion(Vector((1, 0, 0)), ang if f != "thumb" else ang * 0.6)
    bpy.context.view_layer.update()


def bend(bone, pitch=0.0, yaw=0.0, roll=0.0):
    """Extra rotation of a spine / neck / head bone about world axes, at its head. pitch < 0 bends
    forward / looks down (the courier faces -Y), yaw > 0 turns to the courier's left."""
    pb = rig.pose.bones[bone]
    bpy.context.view_layer.update()
    m = pb.matrix.copy()
    r = (Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(-pitch, 4, "X") @ Matrix.Rotation(roll, 4, "Y"))
    h = m.translation.copy()
    pb.matrix = Matrix.Translation(h) @ r @ Matrix.Translation(-h) @ m
    bpy.context.view_layer.update()


def snapshot():
    return {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}


def bake(name, frames):
    """frames: [(frame, {bone: matrix_basis})] posed with no action assigned (an assigned action
    would be re-evaluated over the pose being built); keyed here in one pass."""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    for f, mats in frames:
        for pb in rig.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.matrix_basis = mats[pb.name]
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if pb.name in ("Root", "pelvis"):
                pb.keyframe_insert("location", frame=f)
    rig.animation_data.action = None
    return act


def source_poses(action, frames, step=1):
    """matrix_basis of every bone of `action` at frames 0..frames (looping over its length)."""
    n = int(action.frame_range[1])
    out = []
    for f in range(0, frames + 1, step):
        eval_action(action, f % n if f != frames or frames != n else n)
        out.append((f, snapshot()))
    rig.animation_data.action = None
    return out


def posed(name, base, pose_fn, frames):
    out = []
    for f, mats in base:
        for pb in rig.pose.bones:
            pb.matrix_basis = mats[pb.name]
        bpy.context.view_layer.update()
        pose_fn(f / FPS, f / frames)
        out.append((f, snapshot()))
    return bake(name, out)


def standing_clip(name, frames, pose_fn):
    """Idle_Loop legs / hips / breathing, then pose_fn(t, phase) for the upper body each frame."""
    return posed(name, source_poses(bpy.data.actions["Idle_Loop"], frames, 2), pose_fn, frames)


def walking_clip(name, arms_fn):
    """Walk_Loop with the arms (and a little spine) replaced by arms_fn(t, phase)."""
    walk = bpy.data.actions["Walk_Loop"]
    n = int(walk.frame_range[1])
    return posed(name, source_poses(walk, n, 1), arms_fn, n)


def body_point(x, fwd, z):
    """A point in front of the hips: x to the courier's left (+X), fwd metres forward (-Y), z above the floor."""
    hips = wpos("pelvis")
    return Vector((hips.x + x, hips.y - fwd, z))


# --- clips -------------------------------------------------------------------------------------
def sweep(t, ph):
    w = math.sin(2 * math.pi * ph * 2)                 # two strokes per loop
    bend("spine_01", pitch=-0.18)
    bend("spine_02", pitch=-0.08, yaw=0.18 * w)
    bend("head", pitch=-0.35)
    # handle: low (right) hand near the hip, high (left) hand up the stick; the broom head sweeps
    # across the ground about 0.9 m in front
    hz = wpos("pelvis").z
    low = body_point(-0.16 + 0.1 * w, 0.38, hz + 0.04)
    high = body_point(-0.06 + 0.06 * w, 0.3, hz + 0.27)
    reach("r", low, (-0.8, 0.4, -0.6), (0.05 * w, -0.7, -0.7))
    reach("l", high, (0.6, 0.6, -0.8), (-0.3, -0.6, -0.7))
    grip("r")
    grip("l")


def counter(t, ph):
    a = 2 * math.pi * ph * 3                           # three stirring circles per loop
    bend("spine_01", pitch=-0.12)
    bend("spine_02", pitch=-0.06)
    bend("head", pitch=-0.42, yaw=0.08 * math.sin(2 * math.pi * ph))
    hz = wpos("pelvis").z
    stir = body_point(-0.13 + 0.05 * math.cos(a), 0.42 + 0.04 * math.sin(a), hz + 0.05)
    hold = body_point(0.17, 0.4, hz + 0.04 + 0.01 * math.sin(2 * math.pi * ph))
    reach("r", stir, (0.6, 0.3, -1.0), (0.0, -0.8, -0.6))
    reach("l", hold, (-0.6, 0.3, -1.0), (-0.2, -0.8, -0.5))
    grip("r", 0.8)
    grip("l", 0.5)


def duty(t, ph):
    s = math.sin(2 * math.pi * ph)
    bend("spine_03", pitch=0.04)
    bend("head", yaw=0.32 * math.sin(2 * math.pi * ph + 0.6), pitch=0.03)
    for side, sx in (("r", -1), ("l", 1)):
        at = body_point(sx * 0.13, 0.13, wpos("pelvis").z + 0.06)
        reach(side, at, (sx * 1.0, 0.2, -0.3), (sx * 0.2, -0.3, -1.0))
        grip(side, 0.55)


def photo(t, ph):
    hold = 0.4 + 0.03 * math.sin(2 * math.pi * ph)
    sh = wpos("upperarm_l")
    bend("head", pitch=-0.05)
    for side, sx in (("r", -1), ("l", 1)):
        at = Vector((sx * 0.07, wpos("pelvis").y - hold, sh.z + 0.1))
        reach(side, at, (sx * 0.9, 0.3, -1.0), (sx * -0.35, -0.75, 0.55))
        grip(side, 0.45)


def leash(t, ph):
    bob = 0.02 * math.sin(2 * math.pi * ph * 2)
    reach("l", body_point(0.2, 0.34, 0.86 + bob), (0.7, 0.3, -1.0), (0.1, -0.6, -0.8))
    grip("l")


def push(t, ph):
    bend("spine_01", pitch=-0.06)
    bob = 0.01 * math.sin(2 * math.pi * ph * 2)
    for side, sx in (("r", -1), ("l", 1)):
        reach(side, body_point(sx * 0.21, 0.46, 0.98 + bob), (sx * 0.7, 0.3, -1.0), (0.0, -0.95, -0.3))
        grip(side)


made = [standing_clip("Sweep_Loop", 60, sweep), standing_clip("Counter_Work_Loop", 90, counter),
        standing_clip("Duty_Stand_Loop", 120, duty), standing_clip("Photo_Take_Loop", 90, photo),
        walking_clip("Walk_Leash_Loop", leash), walking_clip("Walk_Push_Loop", push)]
print("ROLE CLIPS", [a.name for a in made])

if "qa" in sys.argv:
    # two frames of each clip on the courier body, 3/4 front, Workbench (fast, readable silhouettes)
    import os
    qa_dir = os.path.join(os.path.dirname(OUT), "qa")
    os.makedirs(qa_dir, exist_ok=True)
    cam = bpy.data.objects.new("QA_Cam", bpy.data.cameras.new("QA_Cam"))
    scn.collection.objects.link(cam)
    scn.camera = cam
    cam.location = (1.9, -2.6, 1.35)
    cam.rotation_euler = (Vector((0, 0, 0.95)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scn.render.engine = "BLENDER_WORKBENCH"
    scn.display.shading.light = "STUDIO"
    scn.display.shading.color_type = "TEXTURE"
    scn.render.resolution_x, scn.render.resolution_y = 600, 800
    for a in made:
        n = int(a.frame_range[1])
        for k_, f in enumerate((int(n * 0.25), int(n * 0.6))):
            eval_action(a, f)
            scn.render.filepath = os.path.join(qa_dir, "%s_%d.png" % (a.name, k_))
            bpy.ops.render.render(write_still=True)
    print("QA in", qa_dir)

# Export the rig with just these actions (meshes stay out; the game only needs the tracks).
keep = {a.name for a in made}
for a in list(bpy.data.actions):
    if a.name not in keep:
        bpy.data.actions.remove(a)
rig.animation_data.action = None
for o in bpy.context.view_layer.objects:
    o.select_set(o == rig)
bpy.context.view_layer.objects.active = rig
for pb in rig.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_skins=True, export_yup=True, export_def_bones=False)
print("EXPORTED", OUT)
