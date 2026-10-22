"""The player courier, its animation set, and two extra realistic NPCs, prepared in Blender.

blender --background --factory-startup --python tools/prepare_player.py -- <stage> [options]

stages:
  player    Ch42 (Mixamo) -> assets/player/courier.glb: one skinned mesh (hidden body under the
            clothes removed), textures <= 2048 with metal/rough PBR, skeleton renamed to the
            Godot SkeletonProfileHumanoid names, rest matched to the UAL library rest
            (tools/match_ual_rest.py method), and the player's clips baked on its own rig:
            library motion (assets/animations/ual) transferred by world-space rotation deltas,
            the supplied Mixamo "Jog Forward" (root motion removed), and authored clips (side
            steps, step turns, walking backwards, idle variants, hard landing, bicycle seated /
            pedalling fitted to assets/bicycles/gray_bicycle.glb). Clip ground speeds measured
            from the planted feet -> assets/player/clips_blender.json (tools/setup_player.gd
            measures again in Godot and writes assets/player/clips.json).
  avaturn   Avaturn talking avatar -> assets/player/customer_avaturn.glb (realistic door
            customer: face blend shapes and its own talking clip kept, rest matched to UAL).
  clothed   unrigged clothed figure -> assets/sketchup/people/clothed_man.glb (fitted humanoid
            skeleton, automatic weights with armpit / crotch fixes, <= 25k tris, 1024 textures).
  qa        QA renders of the courier (rest views, clip frames) -> assets/player/qa/.
  fit       rider fit on the gray bicycle (Bike_Seated / Bike_Pedal at 0/90/180/270 deg) ->
            world/vehicles/production/renders/gray_bicycle/rider_fit_*.png
  bag       development stage of the backpack work (tools/courier_bag.py): builds the courier and
            its clips, the worn fit, the body-fitted straps and the bag / carry clips, renders the
            bag QA to assets/player/qa/bag_*.png; exports nothing. Options: --no-qa, --no-worn,
            --clips=Bag_TakeOff,Bag_PutOn (QA sheets of those clips only).
            The `player` stage does all of this too and bakes the clips / straps into courier.glb.

Conventions (same as the townspeople, see tools/prepare_characters.py / match_ual_rest.py):
characters face Blender -Y = Godot +Z (the humanoid retarget convention), metres, feet on z 0,
skeleton "Armature" with profile bone names, Root bone at the origin.
"""
import bpy, bmesh, sys, os, math, json, re, shutil
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source_assets", "incoming_2026_10_22")
OUT = os.path.join(ROOT, "assets", "player")
QA = os.path.join(OUT, "qa")
UAL = os.path.join(ROOT, "assets", "animations", "ual", "ual_standard.glb")
UAL_NPC = os.path.join(ROOT, "assets", "animations", "ual", "ual_npc.glb")
BIKE = os.path.join(ROOT, "assets", "bicycles", "gray_bicycle.glb")
FIT_DIR = os.path.join(ROOT, "world", "vehicles", "production", "renders", "gray_bicycle")
PEOPLE = os.path.join(ROOT, "assets", "sketchup", "people")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FPS = 30
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ----------------------------------------------------------------------------- humanoid profile
FINGERS = [("Thumb", ["Metacarpal", "Proximal", "Distal"]), ("Index", ["Proximal", "Intermediate", "Distal"]),
           ("Middle", ["Proximal", "Intermediate", "Distal"]), ("Ring", ["Proximal", "Intermediate", "Distal"]),
           ("Little", ["Proximal", "Intermediate", "Distal"])]
HUMANOID = ["Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftEye", "RightEye", "Jaw"]
for _s in ("Left", "Right"):
    HUMANOID += [_s + n for n in ("Shoulder", "UpperArm", "LowerArm", "Hand")]
    HUMANOID += [_s + f + p for f, ps in FINGERS for p in ps]
    HUMANOID += [_s + n for n in ("UpperLeg", "LowerLeg", "Foot", "Toes")]
HUMANOID_SET = set(HUMANOID)

# Mixamo / Avaturn names (after stripping "mixamorig:" and Sketchfab "_N" suffixes) -> profile.
MIXAMO = {"Hips": "Hips", "Spine": "Spine", "Spine1": "Chest", "Spine2": "UpperChest", "Neck": "Neck",
          "Head": "Head", "LeftEye": "LeftEye", "RightEye": "RightEye"}
for _side in ("Left", "Right"):
    MIXAMO.update({_side + "Shoulder": _side + "Shoulder", _side + "Arm": _side + "UpperArm",
                   _side + "ForeArm": _side + "LowerArm", _side + "Hand": _side + "Hand",
                   _side + "UpLeg": _side + "UpperLeg", _side + "Leg": _side + "LowerLeg",
                   _side + "Foot": _side + "Foot", _side + "ToeBase": _side + "Toes"})
    for (_f, _parts), _mx in zip(FINGERS, ("Thumb", "Index", "Middle", "Ring", "Pinky")):
        for _i, _p in enumerate(_parts):
            MIXAMO["%sHand%s%d" % (_side, _mx, _i + 1)] = _side + _f + _p

# Profile bone -> UAL (Rigify DEF-) bone.
UAL_NAMES = {"Root": "root", "Hips": "DEF-hips", "Spine": "DEF-spine.001", "Chest": "DEF-spine.002",
             "UpperChest": "DEF-spine.003", "Neck": "DEF-neck", "Head": "DEF-head"}
for _side, _s in (("Left", "L"), ("Right", "R")):
    UAL_NAMES.update({_side + "Shoulder": "DEF-shoulder." + _s, _side + "UpperArm": "DEF-upper_arm." + _s,
                      _side + "LowerArm": "DEF-forearm." + _s, _side + "Hand": "DEF-hand." + _s,
                      _side + "UpperLeg": "DEF-thigh." + _s, _side + "LowerLeg": "DEF-shin." + _s,
                      _side + "Foot": "DEF-foot." + _s, _side + "Toes": "DEF-toe." + _s})
    for _f, _u in (("Thumb", "thumb"), ("Index", "f_index"), ("Middle", "f_middle"), ("Ring", "f_ring"), ("Little", "f_pinky")):
        for _k, _p in enumerate(dict(FINGERS)[_f]):
            UAL_NAMES[_side + _f + _p] = "DEF-%s.0%d.%s" % (_u, _k + 1, _s)

# Segments whose direction is matched to the library rest (joint -> next joint).
SEGMENTS = [("Hips", "Spine"), ("Spine", "Chest"), ("Chest", "UpperChest"), ("UpperChest", "Neck"), ("Neck", "Head")]
for _side in ("Left", "Right"):
    SEGMENTS += [(_side + "UpperLeg", _side + "LowerLeg"), (_side + "LowerLeg", _side + "Foot"), (_side + "Foot", _side + "Toes"),
                 (_side + "Shoulder", _side + "UpperArm"), (_side + "UpperArm", _side + "LowerArm"),
                 (_side + "LowerArm", _side + "Hand"), (_side + "Hand", _side + "MiddleProximal")]
    for _f, _parts in FINGERS:
        for _a, _b in zip(_parts, _parts[1:]):
            SEGMENTS.append((_side + _f + _a, _side + _f + _b))


def log(*a):
    print("[player]", *a, flush=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def tris(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == 'MESH')


def import_any(path):
    before = set(bpy.data.objects)
    if path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.name.startswith("Icosphere"):
            new.remove(o)
            bpy.data.objects.remove(o)
    return new


def flatten(keep):
    """Bake every kept object's world transform into its data, unparent, delete the rest."""
    for o in keep:
        mw = o.matrix_world.copy()
        o.parent = None
        if o.type in ('MESH', 'ARMATURE'):
            o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o)


def mesh_np(o, world=True):
    co = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    if world:
        m = np.array(o.matrix_world)
        co = co @ m[:3, :3].T + m[:3, 3]
    return co


def evaluated_np(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(e.matrix_world)
        out.append(co @ m[:3, :3].T + m[:3, 3])
        e.to_mesh_clear()
    return out


def strip_name(name):
    name = name.split(":")[-1]
    return re.sub(r"_\d+$", "", name)


def rename_bones(arm, meshes, mapping):
    """Rename bones (and vertex groups) through mapping(stripped name) -> profile name or None."""
    renames = {}
    for b in arm.data.bones:
        base = strip_name(b.name)
        new = mapping.get(base)
        if new and new != b.name:
            renames[b.name] = new
    for old, new in renames.items():
        arm.data.bones[old].name = new
    for o in meshes:
        for g in o.vertex_groups:
            if g.name in renames:
                g.name = renames[g.name]
    return renames


def remove_bones(arm, meshes, names):
    """Delete bones; their weights go to the nearest kept ancestor, their children to their parent."""
    names = [n for n in names if n in arm.data.bones]
    if not names:
        return
    target = {}
    for n in names:
        p = arm.data.bones[n].parent
        while p is not None and p.name in names:
            p = p.parent
        target[n] = p.name if p else None
    for o in meshes:
        for n, t in target.items():
            src = o.vertex_groups.get(n)
            if src is None:
                continue
            if t is not None:
                dst = o.vertex_groups.get(t) or o.vertex_groups.new(name=t)
                for v in o.data.vertices:
                    for g in v.groups:
                        if g.group == src.index and g.weight > 0:
                            dst.add([v.index], g.weight, 'ADD')
            o.vertex_groups.remove(src)
    select_only([arm])
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for n in names:
        b = eb.get(n)
        if b is None:
            continue
        for c in list(b.children):
            c.use_connect = False
            c.parent = b.parent
        eb.remove(b)
    bpy.ops.object.mode_set(mode='OBJECT')


def add_root(arm):
    select_only([arm])
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    r = eb.get("Root") or eb.new("Root")
    r.head = (0, 0, 0)
    r.tail = (0, 0, 0.1)
    r.roll = 0
    r.use_deform = False
    hips = eb["Hips"]
    hips.use_connect = False
    hips.parent = r
    bpy.ops.object.mode_set(mode='OBJECT')


def limit_and_normalize(mesh):
    select_only([mesh])
    bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_DEFORM', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)


def decimate(o, ratio):
    if ratio >= 0.999:
        return
    select_only([o])
    m = o.modifiers.new("Decimate", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = ratio
    m.use_collapse_triangulate = True
    m.use_symmetry = True
    m.symmetry_axis = 'X'
    bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)
    bpy.ops.object.modifier_apply(modifier=m.name)


def action_fcurves(a):
    if hasattr(a, "fcurves") and len(a.fcurves):
        return list(a.fcurves)
    out = []
    for layer in getattr(a, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def set_action(obj, act):
    if not obj.animation_data:
        obj.animation_data_create()
    obj.animation_data.action = act
    if act is not None and getattr(act, "slots", None) and len(act.slots):
        try:
            obj.animation_data.action_slot = act.slots[0]
        except Exception:
            pass


# ----------------------------------------------------------------------------- library rest & motion capture
def capture(arm, act, names, frames=None):
    """World matrices (4x4, armature at its world transform) of the named pose bones per frame."""
    sc = bpy.context.scene
    set_action(arm, act)
    f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
    out = []
    for f in (frames if frames is not None else range(f0, f1 + 1)):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        fr = {}
        for n in names:
            if n in arm.pose.bones:
                M = arm.matrix_world @ arm.pose.bones[n].matrix
                fr[n] = Matrix.Translation(M.to_translation()) @ M.to_3x3().normalized().to_4x4()
        out.append(fr)
    return out


def rest_world(arm, names):
    return {n: (arm.matrix_world @ arm.data.bones[n].matrix_local).copy() for n in names if n in arm.data.bones}


UAL_CLIPS = ["Idle_Loop", "Walk_Loop", "Jog_Fwd_Loop", "Sprint_Loop", "Jump_Start", "Jump_Loop", "Jump_Land",
             "Interact", "PickUp_Table", "Idle_Talking_Loop", "Driving_Loop", "Sitting_Idle_Loop"]
UAL_NPC_CLIPS = ["Idle_Look_Loop"]


def load_library():
    """UAL rest (segment directions, hips height, rests) and the source clips as profile-named
    world matrices: {'rest': {...}, 'dirs': {...}, 'fps': 24, 'clips': {name: [frame dicts]}}"""
    lib = {"clips": {}}
    for path, wanted in ((UAL, UAL_CLIPS), (UAL_NPC, UAL_NPC_CLIPS)):
        reset()
        import_any(path)
        arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        sc = bpy.context.scene
        lib["fps"] = sc.render.fps / sc.render.fps_base
        inv = {v: k for k, v in UAL_NAMES.items()}
        names = [n for n in inv if n in arm.pose.bones]
        if "rest" not in lib:
            rw = rest_world(arm, names)
            lib["rest"] = {inv[n]: m for n, m in rw.items()}
            dirs = {}
            for a, b in SEGMENTS:
                if UAL_NAMES.get(a) in arm.data.bones and UAL_NAMES.get(b) in arm.data.bones:
                    ha = arm.matrix_world @ arm.data.bones[UAL_NAMES[a]].head_local
                    hb = arm.matrix_world @ arm.data.bones[UAL_NAMES[b]].head_local
                    dirs[a] = (hb - ha).normalized()
            lib["dirs"] = dirs
        acts = {a.name: a for a in bpy.data.actions}
        for clip in wanted:
            if clip not in acts:
                log("  library clip missing", clip)
                continue
            frames = capture(arm, acts[clip], names)
            lib["clips"][clip] = [{inv[n]: m for n, m in fr.items()} for fr in frames]
        log("library", os.path.basename(path), "clips", [c for c in wanted if c in lib["clips"]])
    return lib


# ----------------------------------------------------------------------------- rest matching
def match_rest(arm, meshes, dirs):
    """Pose every segment to point like the library's, bake into the meshes, apply as rest."""
    set_action(arm, None)
    select_only([arm])
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    pose = arm.pose.bones
    worst = 0.0
    for a, b in SEGMENTS:
        if a not in pose or b not in pose or a not in dirs:
            continue
        pb = pose[a]
        head = pb.head.copy()
        v = (pose[b].head - head).normalized()
        t = dirs[a]
        R = v.rotation_difference(t).to_matrix().to_4x4()
        worst = max(worst, v.angle(t))
        pb.matrix = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ pb.matrix
        bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in meshes:
        mod = next(m for m in o.modifiers if m.type == 'ARMATURE')
        select_only([o])
        if o.data.shape_keys:
            apply_armature_with_shape_keys(o, mod)
        else:
            bpy.ops.object.modifier_apply(modifier=mod.name)
    select_only([arm])
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in meshes:
        m = o.modifiers.new("Armature", 'ARMATURE')
        m.object = arm
    return math.degrees(worst)


def apply_armature_with_shape_keys(o, mod):
    """modifier_apply refuses meshes with shape keys: bake the armature deformation into the
    basis and move every key by the same per-vertex deformation (keys stay relative deltas)."""
    dg = bpy.context.evaluated_depsgraph_get()
    keys = o.data.shape_keys.key_blocks
    vals = [k.value for k in keys]
    for k in keys:
        k.value = 0.0
    o.show_only_shape_key = False
    bpy.context.view_layer.update()
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.to_mesh()
    deformed = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", deformed)
    e.to_mesh_clear()
    basis = np.empty(len(o.data.vertices) * 3)
    keys[0].data.foreach_get("co", basis)
    delta = deformed - basis
    # A per-vertex translation keeps key deltas un-rotated; small for rest corrections (<10 deg)
    # on the face, which moves rigidly with the head anyway.
    for k in keys:
        co = np.empty(len(o.data.vertices) * 3)
        k.data.foreach_get("co", co)
        k.data.foreach_set("co", co + delta)
    o.data.vertices.foreach_set("co", basis + delta)
    for k, v in zip(keys, vals):
        k.value = v
    o.modifiers.remove(mod)


# ----------------------------------------------------------------------------- mini FK rig for clip baking
class Rig:
    """Armature-space FK on rest matrices; a pose is {bone: basis 4x4} (like matrix_basis)."""

    def __init__(self, arm):
        bones = arm.data.bones
        self.arm = arm
        depth = {}

        def d(b):
            if b.name not in depth:
                depth[b.name] = 0 if b.parent is None else d(b.parent) + 1
            return depth[b.name]
        self.order = sorted([b.name for b in bones], key=lambda n: d(bones[n]))
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        self.rest_rot = {n: m.to_quaternion() for n, m in self.rest.items()}
        self.rel = {}
        for n in self.order:
            p = self.parent[n]
            self.rel[n] = (self.rest[p].inverted() @ self.rest[n]) if p else self.rest[n].copy()
        self.children = {n: [c for c in self.order if self.parent[c] == n] for n in self.order}

    def identity(self):
        return {n: Matrix.Identity(4) for n in self.order}

    def fk(self, basis):
        W = {}
        for n in self.order:
            p = self.parent[n]
            W[n] = (W[p] @ self.rel[n] @ basis[n]) if p else (self.rel[n] @ basis[n])
        return W

    def set_world_rot(self, basis, W, n, q):
        """Give bone n the world rotation q (Quaternion), head kept; returns updated W."""
        p = self.parent[n]
        base = (W[p] @ self.rel[n]) if p else self.rel[n]
        loc = basis[n].to_translation()
        target = Matrix.Translation((base @ basis[n]).to_translation()) @ q.to_matrix().to_4x4()
        b = base.inverted() @ target
        b.translation = loc if p else b.translation   # child bones never translate
        basis[n] = b
        return self.fk(basis)

    def set_world(self, basis, W, n, M):
        """World matrix (rotation + head position) for a translating bone (Hips)."""
        p = self.parent[n]
        base = (W[p] @ self.rel[n]) if p else self.rel[n]
        basis[n] = base.inverted() @ M
        return self.fk(basis)

    def head(self, W, n):
        return W[n].to_translation()

    def rot(self, W, n):
        return W[n].to_quaternion()


def rot_about(axis, angle):
    return Quaternion(Vector(axis).normalized(), angle)


def aim_quat(q, cur_dir, new_dir):
    return cur_dir.rotation_difference(new_dir) @ q


def sstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def transfer_pose(rig, frame, src_rest, hip_scale, hip_offset=Vector(), leg_scale=None):
    """Library motion -> this rig: each bone gets the source bone's world rotation delta from
    its rest, applied to its own rest (the rests point the same way after match_rest); the hips
    position is scaled by the hips-height ratio (Godot's normalize_position_tracks does the same)."""
    basis = rig.identity()
    W = rig.fk(basis)
    for n in rig.order:
        if n == "Root" or n not in frame or n not in src_rest:
            continue
        D = frame[n].to_quaternion() @ src_rest[n].to_quaternion().inverted()
        q = D @ rig.rest_rot[n]
        if n == "Hips":
            if leg_scale is not None and "LeftUpperLeg" in frame and "RightUpperLeg" in frame:
                # place the hip joints (legs' roots), scaled by the leg-length ratio, so feet land
                # where the library's feet do; the Hips head follows from its own rest offset.
                mid = (frame["LeftUpperLeg"].to_translation() + frame["RightUpperLeg"].to_translation()) / 2 * leg_scale
                r = rig.rest
                off = r["Hips"].to_translation() - (r["LeftUpperLeg"].to_translation() + r["RightUpperLeg"].to_translation()) / 2
                pos = mid + D @ off + hip_offset
            else:
                pos = frame[n].to_translation() * hip_scale + hip_offset
            W = rig.set_world(basis, W, n, Matrix.Translation(pos) @ q.to_matrix().to_4x4())
        else:
            W = rig.set_world_rot(basis, W, n, q)
    return basis, W


def copy_world_pose(rig, frame, offset=Vector()):
    """Same skeleton (renamed): reproduce the recorded world matrices exactly."""
    basis = rig.identity()
    W = rig.fk(basis)
    for n in rig.order:
        if n == "Root" or n not in frame:
            continue
        q = frame[n].to_quaternion()
        if n == "Hips":
            W = rig.set_world(basis, W, n, Matrix.Translation(frame[n].to_translation() + offset) @ q.to_matrix().to_4x4())
        else:
            W = rig.set_world_rot(basis, W, n, q)
    return basis, W


def sample_frames(frames, t_src):
    """Interpolated frame dict at fractional source frame index t_src (clamped)."""
    n = len(frames)
    t_src = min(max(t_src, 0.0), n - 1.0)
    i = int(math.floor(t_src))
    j = min(i + 1, n - 1)
    a = t_src - i
    if a < 1e-6:
        return frames[i]
    out = {}
    for k, m0 in frames[i].items():
        m1 = frames[j][k]
        q = m0.to_quaternion().slerp(m1.to_quaternion(), a)
        p = m0.to_translation().lerp(m1.to_translation(), a)
        out[k] = Matrix.Translation(p) @ q.to_matrix().to_4x4()
    return out


# ----------------------------------------------------------------------------- courier mesh
def hide_covered_body(body, cloth, max_gap=0.07, hem=0.045):
    """Delete body faces hidden under the clothes (and inside the shoes): a vertex is covered when
    the ray along its normal hits a garment within max_gap; faces closer than `hem` to a garment
    opening (sleeve, neck, waist, leg hems, shoe collar) are kept so nothing opens up."""
    bm = bmesh.new()
    for o in cloth:
        bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    border = [v.co.copy() for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
    bm.free()
    kd = KDTree(len(border))
    for i, c in enumerate(border):
        kd.insert(c, i)
    kd.balance()
    me = body.data
    covered = np.zeros(len(me.vertices), bool)
    for v in me.vertices:
        n = v.normal
        hit = bvh.ray_cast(v.co + n * 0.0005, n, max_gap)
        if hit[0] is None:
            continue
        _, _, dist = kd.find(v.co)
        covered[v.index] = dist > hem
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    dead = [f for f in bm.faces if all(covered[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(me)
    bm.free()
    return len(dead)


def image_by_file(token):
    for im in bpy.data.images:
        if token in (im.filepath or "") or token in im.name:
            return im
    return None


def tex_node(nt, image, x, y, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = image
    n.location = (x, y)
    if non_color:
        image.colorspace_settings.name = 'Non-Color'
    return n


def pixels(im):
    a = np.empty(im.size[0] * im.size[1] * 4, np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(im.size[1], im.size[0], 4)


def new_image(name, arr, non_color=False, alpha=False):
    h, w = arr.shape[:2]
    im = bpy.data.images.new(name, w, h, alpha=alpha)
    if non_color:
        im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(arr.astype(np.float32).ravel())
    im.file_format = 'PNG' if alpha else 'JPEG'
    im.pack()
    return im


def scaled_copy(im, size, name, non_color=False, alpha=False):
    c = im.copy()
    if c.size[0] > size:
        c.scale(size, size)
    arr = pixels(c)
    bpy.data.images.remove(c)
    if not alpha:
        arr[..., 3] = 1.0
    return new_image(name, arr, non_color, alpha)


def courier_materials(meshes):
    """Mixamo's material: base 4096, normal, specular and glossiness maps, metallic 0.5 (wrong).
    -> base colour / normal at 2048 and a glTF metal-rough map (G = 1 - glossiness, B = 0)."""
    base = image_by_file("1001_Diffuse")
    nrm = image_by_file("1001_Normal")
    gloss = image_by_file("1001_Glossiness")
    hair = image_by_file("1002_Diffuse")
    log("  source images", [(i.name, tuple(i.size)) for i in (base, nrm, gloss, hair) if i])
    b2 = scaled_copy(base, 2048, "Courier_basecolor")
    n2 = scaled_copy(nrm, 2048, "Courier_normal", non_color=True)
    g = gloss.copy()
    g.scale(2048, 2048)
    ga = pixels(g)[..., 0]
    bpy.data.images.remove(g)
    rough = np.clip(1.0 - ga, 0.18, 1.0)
    mr = np.stack([np.ones_like(rough), rough, np.zeros_like(rough), np.ones_like(rough)], -1)
    m2 = new_image("Courier_metal_rough", mr, non_color=True)
    log("  roughness range %.2f..%.2f mean %.2f" % (rough.min(), rough.max(), rough.mean()))
    h2 = scaled_copy(hair, 2048, "Courier_hair", alpha=True)

    body = bpy.data.materials.new("Courier_Body")
    body.use_nodes = True
    nt = body.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tb = tex_node(nt, b2, -700, 300)
    tn = tex_node(nt, n2, -700, -300, True)
    tm = tex_node(nt, m2, -700, 0, True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tb.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.nodes.active = tb

    hm = bpy.data.materials.new("Courier_Hair")
    hm.use_nodes = True
    nt = hm.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    th = tex_node(nt, h2, -700, 200)
    rnd = nt.nodes.new("ShaderNodeMath")
    rnd.operation = 'ROUND'          # glTF exporter: alpha through ROUND = alphaMode MASK, cutoff 0.5
    nt.links.new(th.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(th.outputs["Alpha"], rnd.inputs[0])
    nt.links.new(rnd.outputs[0], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Metallic"].default_value = 0.0
    try:
        hm.surface_render_method = 'DITHERED'
    except Exception:
        pass
    hm.use_backface_culling = False
    nt.nodes.active = th
    for o in meshes:
        for slot in o.material_slots:
            if slot.material and "Hair" in slot.material.name:
                slot.material = hm
            else:
                slot.material = body
    return body, hm


def foot_contacts(arm, mesh):
    """Heel / ball / toe-tip sole points of each foot in the Foot bone's rest frame (feet flat)."""
    co = mesh_np(mesh)
    idx = {g.index: g.name for g in mesh.vertex_groups}
    out = {}
    for side in ("Left", "Right"):
        wsum = np.zeros(len(co))
        for v in mesh.data.vertices:
            wsum[v.index] = sum(g.weight for g in v.groups if idx[g.group] in (side + "Foot", side + "Toes"))
        S = co[(wsum > 0.5) & (co[:, 2] < 0.035)]
        foot = arm.data.bones[side + "Foot"]
        toes = arm.data.bones[side + "Toes"]
        sole = float(np.percentile(S[:, 2], 5))
        x = float(np.median(S[:, 0]))
        heel_y = float(S[:, 1].max())      # faces -Y: heel is the largest y
        tip_y = float(S[:, 1].min())
        pts = {"heel": Vector((x, heel_y - 0.025, sole)), "ball": Vector((toes.head_local.x, toes.head_local.y, sole)),
               "tip": Vector((x, tip_y + 0.012, sole))}
        inv = foot.matrix_local.inverted()
        out[side] = {k: inv @ p for k, p in pts.items()}
        out[side]["tip"] = toes.matrix_local.inverted() @ pts["tip"]     # the toes bend at push-off
        out[side]["_world"] = {k: tuple(round(c, 4) for c in p) for k, p in pts.items()}
    return out


def build_courier(lib):
    # --- the supplied Mixamo jog, recorded as world matrices of the same (renamed) skeleton
    reset()
    import_any(os.path.join(SRC, "Jog Forward.fbx"))
    jarm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    sc = bpy.context.scene
    jog_fps = sc.render.fps / sc.render.fps_base
    rename_bones(jarm, [], MIXAMO)
    jact = next(a for a in bpy.data.actions)
    names = [b.name for b in jarm.data.bones if b.name in HUMANOID_SET]
    jog_rest = rest_world(jarm, names)
    jog = capture(jarm, jact, names)
    log("jog: %d frames at %.0f fps, action %s range %s" % (len(jog), jog_fps, jact.name, tuple(jact.frame_range)))

    # --- the character
    reset()
    import_any(os.path.join(SRC, "Ch42_nonPBR.fbx"))
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    set_action(arm, None)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    flatten([arm] + meshes)
    rename_bones(arm, meshes, MIXAMO)
    # same skeleton as the jog file?
    worst = 0.0
    for n in names:
        if n in arm.data.bones:
            a = arm.data.bones[n].matrix_local
            worst = max(worst, (a.to_translation() - jog_rest[n].to_translation()).length,
                        a.to_quaternion().rotation_difference(jog_rest[n].to_quaternion().normalized()).angle)
    log("courier vs jog rest: worst difference %.5f (m / rad)" % worst)
    ends = [b.name for b in arm.data.bones if b.name not in HUMANOID_SET]
    log("removing non-profile bones", ends)
    remove_bones(arm, meshes, ends)
    add_root(arm)
    body = next(o for o in meshes if "Body" in o.name)
    cloth = [o for o in meshes if any(k in o.name for k in ("Shirt", "Shorts", "Sneakers"))]
    t0 = tris(meshes)
    log("source tris", {o.name: tris([o]) for o in meshes})
    nd = hide_covered_body(body, cloth)
    log("hidden body faces removed:", nd, "-> body tris", tris([body]))
    for o in meshes:
        for k, v in {"Shorts": 0.6, "Sneakers": 0.6, "Shirt": 0.8, "Hair": 0.85}.items():
            if k in o.name:
                decimate(o, v)
    courier_materials(meshes)
    select_only(meshes, body)
    bpy.ops.object.join()
    mesh = body
    mesh.name = mesh.data.name = "CourierMesh"
    select_only([mesh])
    bpy.ops.object.material_slot_remove_unused()
    for md in mesh.modifiers:
        if md.type == 'ARMATURE':
            md.object = arm
    limit_and_normalize(mesh)
    log("tris %d -> %d" % (t0, tris([mesh])))
    arm.name = arm.data.name = "Armature"
    corr = match_rest(arm, [mesh], lib["dirs"])
    zmin = float(mesh_np(mesh)[:, 2].min())
    arm.location.z -= zmin
    mesh.location.z -= zmin
    select_only([arm, mesh], arm)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    mesh.parent = arm
    mesh.matrix_parent_inverse = Matrix.Identity(4)
    log("rest matched: largest correction %.1f deg, ground shift %.4f" % (corr, zmin))
    return arm, mesh, {"jog": jog, "jog_fps": jog_fps, "jog_offset": Vector((0, 0, -zmin))}


def export_rigged(objs, path, animations, morph=False):
    select_only(objs, objs[0])
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
              export_animations=animations, export_skins=True, export_def_bones=False, export_morph=morph,
              export_image_format='JPEG', export_jpeg_quality=92, export_materials='EXPORT', export_extras=True)
    if animations:
        kw.update(export_animation_mode='ACTIONS', export_force_sampling=True, export_frame_step=1,
                  export_optimize_animation_size=False)
    bpy.ops.export_scene.gltf(**kw)
    log("wrote", path, "%.2f MB" % (os.path.getsize(path) / 1e6))


# ----------------------------------------------------------------------------- clip baking
def write_action(arm, rig, name, poses):
    """poses: list of basis dicts, frame 0..N (a loop repeats frame 0 as frame N)."""
    act = bpy.data.actions.new(name)
    set_action(arm, act)
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    n = len(poses)
    for b in rig.order:
        if b == "Root":
            continue
        quats = []
        prev = None
        for P in poses:
            q = P[b].to_quaternion()
            if prev is not None and prev.dot(q) < 0:
                q = -q
            quats.append(q)
            prev = q
        chans = [("rotation_quaternion", 4, [[q[i] for q in quats] for i in range(4)])]
        if b == "Hips":
            locs = [P[b].to_translation() for P in poses]
            chans.append(("location", 3, [[l[i] for l in locs] for i in range(3)]))
        for prop, count, vals in chans:
            path = 'pose.bones["%s"].%s' % (b, prop)
            for i in range(count):
                fc = act.fcurve_ensure_for_datablock(arm, path, index=i, group_name=b)
                fc.keyframe_points.add(n)
                co = np.empty(2 * n)
                co[0::2] = np.arange(n)
                co[1::2] = vals[i]
                fc.keyframe_points.foreach_set("co", co)
                for k in fc.keyframe_points:
                    k.interpolation = 'LINEAR'
                fc.update()
    act.use_fake_user = True
    return act


def world_series(rig, poses):
    return [rig.fk(P) for P in poses]


def contact_series(Ws, contacts):
    """Per frame, per foot: heel / ball / tip world points."""
    out = []
    for W in Ws:
        fr = {}
        for side in ("Left", "Right"):
            M = W[side + "Foot"]
            fr[side] = {k: M @ contacts[side][k] for k in ("heel", "ball")}
            fr[side]["tip"] = W[side + "Toes"] @ contacts[side]["tip"]
        out.append(fr)
    return out


def measure_clip(Ws, contacts, axis=Vector((0, 1, 0)), loop=True, ground=0.02):
    """Ground speed (m/s at speed_scale 1) from the planted feet of an in-place clip: for every
    stance (heel or ball within 2 cm of the ground for >= 2 frames) the point carrying the weight
    in mid-stance is followed while it stays down; its motion along `axis` (backwards relative to
    the body) is fitted with a line. speed = stance-length-weighted mean of the slopes;
    slide = largest deviation of that point from the fitted line (m)."""
    C = contact_series(Ws, contacts)
    n = len(C) - (1 if loop else 0)
    zmin = min(min(fr[s][k].z for k in ("heel", "ball")) for fr in C for s in fr)
    tipmin = min(fr[s]["tip"].z for fr in C for s in fr)
    slopes, weights, slide, side = [], [], 0.0, 0.0
    for s in ("Left", "Right"):
        down = [min(C[i][s]["heel"].z, C[i][s]["ball"].z) < ground for i in range(n)]
        if all(down) or not any(down):
            continue
        start = next(i for i in range(n) if not down[i])   # begin scanning in a swing
        i = 0
        while i < n:
            k = (start + i) % n
            if not down[k]:
                i += 1
                continue
            run = []
            while i < n and down[(start + i) % n]:
                run.append((start + i) % n)
                i += 1
            if len(run) < 2:
                continue
            mid = run[len(run) // 2]
            key = min(("heel", "ball"), key=lambda kk: C[mid][s][kk].z)
            pts = [(j, C[f][s][key]) for j, f in enumerate(run) if C[f][s][key].z < ground + 0.005]
            if len(pts) < 2:
                continue
            tt = np.array([j / FPS for j, _ in pts])
            yy = np.array([p.dot(axis) for _, p in pts])
            A = np.vstack([tt, np.ones_like(tt)]).T
            (m, c), *_ = np.linalg.lstsq(A, yy, rcond=None)
            slopes.append(m)
            weights.append(len(pts))
            slide = max(slide, float(np.abs(yy - (m * tt + c)).max()))
            lat = [(p - axis * p.dot(axis)) for _, p in pts]
            side = max(side, max((q - lat[0]).length for q in lat))
    if not slopes:
        return {"ground_z": round(zmin, 4), "speed": 0.0, "stances": 0}
    return {"ground_z": round(zmin, 4), "toe_tip_min_z": round(tipmin, 4),
            "speed": round(float(np.average(slopes, weights=weights)), 3),
            "speed_per_stance": [round(float(x), 3) for x in slopes], "slide_m": round(slide, 3),
            "side_slip_m": round(side, 3), "stances": len(slopes)}


def hips_world_shift(rig, poses, delta):
    """Translate the whole body by a world vector (via the Hips basis, rest frame aware)."""
    Rinv = rig.rest["Hips"].to_3x3().inverted()
    local = Rinv @ delta
    out = []
    for P in poses:
        Q = dict(P)
        M = P["Hips"].copy()
        M.translation = M.translation + local
        Q["Hips"] = M
        out.append(Q)
    return out


def resample(src_frames, src_fps, loop):
    """Source frame list -> list of frames at FPS (as fractional source indices)."""
    P = len(src_frames) - 1
    secs = P / src_fps
    N = max(1, int(round(secs * FPS)))
    return [k * P / N for k in range(N + 1)], N


class Limbs:
    """Two-bone IK with a hinge: the upper bone is twisted so the joint flexes about its natural
    axis (knee: bends backwards, elbow: forwards), no knee / elbow twisting."""

    def __init__(self, rig):
        self.rig = rig
        self.len = {}
        self.hinge = {}
        R = rig.rest
        for side, sx in (("Left", 1), ("Right", -1)):
            for a, b, c, flex in ((side + "UpperLeg", side + "LowerLeg", side + "Foot", Vector((0, 1, 0))),
                                  (side + "UpperArm", side + "LowerArm", side + "Hand", Vector((0, -1, 0)))):
                pa, pb, pc = R[a].to_translation(), R[b].to_translation(), R[c].to_translation()
                self.len[a] = ((pb - pa).length, (pc - pb).length)
                u0 = (pb - pa).normalized()
                hw = u0.cross(flex).normalized()
                self.hinge[a] = rig.rest_rot[a].inverted() @ hw

    def solve(self, basis, W, a, b, c, target, pole, end_rot=None, stretch=0.9995):
        rig = self.rig
        q_end = end_rot if end_rot is not None else rig.rot(W, c)
        l1, l2 = self.len[a]
        pa = W[a].to_translation()
        d = target - pa
        dist = max(min(d.length, (l1 + l2) * stretch), abs(l1 - l2) + 1e-4)
        dn = d.normalized()
        p = pole - dn * pole.dot(dn)
        p = p.normalized() if p.length > 1e-6 else Vector((0, -1, 0))
        aa = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        h = math.sqrt(max(l1 * l1 - aa * aa, 0.0))
        mid = pa + dn * aa + p * h
        end = pa + dn * dist
        u = (mid - pa).normalized()
        qa = rig.rot(W, a)
        cur = (W[b].to_translation() - pa).normalized()
        qa = cur.rotation_difference(u) @ qa
        n_des = p.cross(dn).normalized()
        hw = qa @ self.hinge[a]
        hw_p = hw - u * hw.dot(u)
        n_p = n_des - u * n_des.dot(u)
        if hw_p.length > 1e-6 and n_p.length > 1e-6:
            ang = hw_p.normalized().angle(n_p.normalized())
            if hw_p.cross(n_p).dot(u) < 0:
                ang = -ang
            qa = Quaternion(u, ang) @ qa
        W = rig.set_world_rot(basis, W, a, qa)
        qb = qa @ (rig.rest_rot[a].inverted() @ rig.rest_rot[b])
        W = rig.set_world_rot(basis, W, b, qb)
        pbn = W[b].to_translation()
        cur = (W[c].to_translation() - pbn).normalized()
        qb = cur.rotation_difference((end - pbn).normalized()) @ qb
        W = rig.set_world_rot(basis, W, b, qb)
        W = rig.set_world_rot(basis, W, c, q_end)
        return W

    def leg(self, basis, W, side, ankle, pole, foot_rot=None, stretch=0.9995):
        return self.solve(basis, W, side + "UpperLeg", side + "LowerLeg", side + "Foot", ankle, pole, foot_rot, stretch)

    def arm(self, basis, W, side, wrist, pole, hand_rot=None):
        return self.solve(basis, W, side + "UpperArm", side + "LowerArm", side + "Hand", wrist, pole, hand_rot)


def rotate_bone_world(rig, basis, W, n, q_delta):
    return rig.set_world_rot(basis, W, n, q_delta @ rig.rot(W, n))


# ----------------------------------------------------------------------------- the player's clips
LEFT, FWD, UP = Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))   # character frame (Blender)


class Clips:
    def __init__(self, arm, mesh, lib, src):
        self.arm, self.mesh, self.lib, self.src = arm, mesh, lib, src
        self.rig = Rig(arm)
        self.limbs = Limbs(self.rig)
        self.contacts = foot_contacts(arm, mesh)
        self.hip_scale = self.rig.rest["Hips"].to_translation().z / lib["rest"]["Hips"].to_translation().z
        lr = lib["rest"]
        self.leg_scale = ((self.rig.rest["LeftUpperLeg"].to_translation().z + self.rig.rest["RightUpperLeg"].to_translation().z)
                          / (lr["LeftUpperLeg"].to_translation().z + lr["RightUpperLeg"].to_translation().z))
        log("leg scale %.4f" % self.leg_scale)
        self.out = []          # (action name, poses, meta)
        log("hip scale %.4f, contacts %s" % (self.hip_scale, {s: c["_world"] for s, c in self.contacts.items()}))

    # -- sources
    def ual(self, clip, reverse=False):
        frames = self.lib["clips"][clip]
        idx, N = resample(frames, self.lib["fps"], True)
        if reverse:
            idx = idx[::-1]
        return [transfer_pose(self.rig, sample_frames(frames, t), self.lib["rest"], self.hip_scale,
                              leg_scale=self.leg_scale)[0] for t in idx]

    def ground_shift(self, poses, ref=None):
        Ws = world_series(self.rig, ref if ref is not None else poses)
        C = contact_series(Ws, self.contacts)
        zmin = min(min(p.z for p in fr[s].values()) for fr in C for s in fr)
        return hips_world_shift(self.rig, poses, Vector((0, 0, -zmin))), zmin

    def add(self, name, poses, loop, kind, **meta):
        if loop:
            poses = poses[:-1] + [dict(poses[0])]      # exact seam
        Ws = world_series(self.rig, poses)
        m = {"loop": loop, "frames": len(poses) - 1, "length": round((len(poses) - 1) / FPS, 4), "kind": kind}
        axis = meta.pop("axis", Vector((0, 1, 0)))
        ground = meta.pop("ground", 0.02)
        if kind in ("locomotion", "standing"):
            m.update(measure_clip(Ws, self.contacts, axis, loop, ground))
            m["axis"] = [round(c, 3) for c in axis]
        m.update(meta)
        game = name[:-5] if name.endswith("_Loop") else name
        self.out.append((name, poses, m))
        log("CLIP %-18s %s" % (game, json.dumps({k: v for k, v in m.items() if k != "root_yaw_samples_30fps"})))
        return poses

    # -- helpers on one pose
    def W(self, P):
        return self.rig.fk(P)

    def clean_feet(self, poses, floor_from_flat=True):
        """Library feet on this body: shoes are longer and thicker than the library mannequin's
        feet, so at push-off the ball / toes dipped below the flat-stance level. Put the flat
        stance on the ground, then lift any heel / ball under the ground with leg IK (the knee
        bends a little more) and bend the toes up so the toe tip never goes below the ground."""
        rig = self.rig
        Ws = world_series(rig, poses)
        C = contact_series(Ws, self.contacts)
        flats = [min(fr[s]["heel"].z, fr[s]["ball"].z) for fr in C for s in fr
                 if abs(fr[s]["heel"].z - fr[s]["ball"].z) < 0.006]
        floor = float(np.percentile(flats, 5)) if (flats and floor_from_flat) else             min(min(fr[s][k].z for k in ("heel", "ball")) for fr in C for s in fr)
        poses = hips_world_shift(rig, poses, Vector((0, 0, -floor)))
        out, fixed = [], 0
        for P in poses:
            P = {n: m.copy() for n, m in P.items()}
            W = rig.fk(P)
            for side in ("Left", "Right"):
                M = W[side + "Foot"]
                low = min((M @ self.contacts[side][k]).z for k in ("heel", "ball"))
                if low < 0.0:
                    hp, kn, an = (W[side + n].to_translation() for n in ("UpperLeg", "LowerLeg", "Foot"))
                    pole = kn - (hp + an) / 2
                    W = self.limbs.leg(P, W, side, an + UP * (-low), pole, rig.rot(W, side + "Foot"))
                    fixed += 1
                B = W[side + "Toes"].to_translation()
                T = W[side + "Toes"] @ self.contacts[side]["tip"]
                if T.z < 0.0 and B.z >= 0.0:
                    L = (T - B).length
                    e0 = math.asin(max(-1.0, min(1.0, (T.z - B.z) / L)))
                    e1 = math.asin(max(-1.0, min(1.0, -B.z / L)))
                    ax = (T - B).cross(UP)
                    if ax.length > 1e-6:
                        W = rotate_bone_world(rig, P, W, side + "Toes", Quaternion(ax.normalized(), e1 - e0))
            out.append(P)
        return out, floor, fixed

    def straighten(self, poses, target, min_flex=7.0, loop=True):
        """The library mannequin stands and walks with 20-35 deg bent knees. Raise the hips by up to
        `target` (never so far that a leg would bend less than min_flex deg) and re-solve both legs
        to their original feet, so the courier stands tall and walks with natural knee flexion."""
        rig = self.rig
        Ws = world_series(rig, poses)
        ratio = math.cos(math.radians(min_flex) / 2)
        allow = []
        for W in Ws:
            r = target
            for s in ("Left", "Right"):
                L = sum(self.limbs.len[s + "UpperLeg"]) * ratio
                H, A = W[s + "UpperLeg"].to_translation(), W[s + "Foot"].to_translation()
                d = H - A
                # |d + r UP| = L  ->  r^2 + 2 r d.z + |d|^2 - L^2 = 0
                b, c = d.z, d.length_squared - L * L
                disc = b * b - c
                rmax = (-b + math.sqrt(disc)) if disc >= 0 else 0.0
                r = min(r, max(rmax, 0.0))
            allow.append(r)
        n = len(allow)
        sm = []
        for i in range(n):
            win = [allow[(i + k) % n] if loop else allow[min(max(i + k, 0), n - 1)] for k in range(-2, 3)]
            sm.append(min(sum(w * a for w, a in zip((1, 2, 3, 2, 1), win)) / 9.0, allow[i]))
        out = []
        for P, W, r in zip(poses, Ws, sm):
            P = {k: m.copy() for k, m in P.items()}
            feet = {s: (W[s + "Foot"].to_translation(), W[s + "Foot"].to_quaternion(),
                        W[s + "LowerLeg"].to_translation() - (W[s + "UpperLeg"].to_translation() + W[s + "Foot"].to_translation()) / 2)
                    for s in ("Left", "Right")}
            W2 = rig.set_world(P, rig.fk(P), "Hips", Matrix.Translation(W["Hips"].to_translation() + UP * r)
                               @ W["Hips"].to_quaternion().to_matrix().to_4x4())
            for s in ("Left", "Right"):
                a, q, pole = feet[s]
                W2 = self.limbs.leg(P, W2, s, a, pole, q)
            out.append(P)
        return out, (min(sm), max(sm))

    def lock_feet(self, poses, axis=Vector((0, 1, 0)), blend=2, ground=0.02):
        """Foot locking for an in-place loop: during each stance the weight-bearing point (heel or
        ball, whichever is lower) is moved onto a straight line at the clip's ground speed
        (anchored at mid-stance, constant sideways position) with leg IK, blended over `blend`
        frames at touch-down / lift-off. With the root moving at that speed nothing slides."""
        rig = self.rig
        m = measure_clip(world_series(rig, poses), self.contacts, axis, True, ground)
        v = m.get("speed", 0.0)
        if not v:
            return poses, 0.0
        n = len(poses) - 1
        Ws = world_series(rig, poses)
        C = contact_series(Ws, self.contacts)
        corr = {s: [None] * n for s in ("Left", "Right")}
        for s in ("Left", "Right"):
            down = [min(C[i][s]["heel"].z, C[i][s]["ball"].z) < ground for i in range(n)]
            if all(down) or not any(down):
                continue
            start = next(i for i in range(n) if not down[i])
            i = 0
            while i < n:
                if not down[(start + i) % n]:
                    i += 1
                    continue
                run = []
                while i < n and down[(start + i) % n]:
                    run.append((start + i) % n)
                    i += 1
                mid = run[len(run) // 2]
                jm = len(run) // 2
                for j, f in enumerate(run):
                    key = min(("heel", "ball"), key=lambda kk: C[f][s][kk].z)
                    anc = C[mid][s][key]
                    ideal = anc + axis * (v * (j - jm) / FPS)
                    cur = C[f][s][key]
                    d = ideal - cur
                    d.z = 0.0
                    w = min(1.0, (j + 1) / (blend + 1), (len(run) - j) / (blend + 1))
                    corr[s][f] = d * w
        out = []
        for i, P in enumerate(poses[:-1]):
            P = {k: mm.copy() for k, mm in P.items()}
            W = rig.fk(P)
            for s in ("Left", "Right"):
                d = corr[s][i]
                if d is None or d.length < 1e-4:
                    continue
                hp, kn, an = (W[s + nn].to_translation() for nn in ("UpperLeg", "LowerLeg", "Foot"))
                W = self.limbs.leg(P, W, s, an + d, kn - (hp + an) / 2, rig.rot(W, s + "Foot"))
            out.append(P)
        out.append(dict(out[0]))
        return out, v

    # ------------------------------------------------------------------ clips
    def library_clips(self):
        R = {}
        idle, z = self.ground_shift(self.ual("Idle_Loop"))
        idle, rr = self.straighten(idle, 0.03, 4.0)
        log("  idle hips raised %.3f..%.3f" % rr)
        R["Idle"] = self.add("Idle_Loop", idle, True, "standing")
        for src, name in (("Idle_Talking_Loop", "Idle_Talk_Loop"), ("Idle_Look_Loop", "Idle_Look_Loop")):
            p, _ = self.ground_shift(self.ual(src))
            p, _ = self.straighten(p, 0.03, 4.0)
            self.add(name, p, True, "standing")
        walk, _, _ = self.clean_feet(self.ual("Walk_Loop"))
        walk, rr = self.straighten(walk, 0.045, 5.0)
        log("  walk hips raised %.3f..%.3f" % rr)
        walk, _ = self.lock_feet(walk)
        R["Walk"] = self.add("Walk_Loop", walk, True, "locomotion")
        back = list(reversed(walk))
        self.add("Walk_Back_Loop", back, True, "locomotion", axis=Vector((0, -1, 0)),
                 note="time-reversed Walk: toe-first steps; the body moves backwards")
        run, _, _ = self.clean_feet(self.ual("Jog_Fwd_Loop"), False)
        run, _ = self.lock_feet(run, ground=0.035)
        self.add("Run_Loop", run, True, "locomotion", ground=0.035, note="library Jog_Fwd: a fast run")
        spr, _, _ = self.clean_feet(self.ual("Sprint_Loop"), False)
        spr, _ = self.lock_feet(spr, ground=0.035)
        self.add("Sprint_Loop", spr, True, "locomotion", ground=0.035)
        js, zj = self.ground_shift(self.ual("Jump_Start"))
        self.add("Jump_Start", js, False, "jump")
        jl = hips_world_shift(self.rig, self.ual("Jump_Loop"), Vector((0, 0, -zj)))
        self.add("Jump_Loop", jl, True, "jump", note="air pose loop; same hips offset as Jump_Start")
        land, zl = self.ground_shift(self.ual("Jump_Land"))
        R["Jump_Land"] = land
        self.add("Jump_Land", land, False, "jump")
        for src, name in (("Interact", "Interact"), ("PickUp_Table", "PickUp")):
            p, _ = self.ground_shift(self.ual(src))
            p, _ = self.straighten(p, 0.03, 4.0, loop=False)
            self.add(name, p, False, "action")
        return R

    def mixamo_jog(self):
        jog = self.src["jog"]
        P = len(jog) - 1                     # the last frame repeats the first one stride later
        worst = max(jog[0][n].to_quaternion().rotation_difference(jog[P][n].to_quaternion()).angle
                    for n in jog[0] if n != "Hips")
        h0, h1 = jog[0]["Hips"].to_translation(), jog[P]["Hips"].to_translation()
        delta = Vector((h1.x - h0.x, h1.y - h0.y, 0))
        native_T = P / self.src["jog_fps"]
        log("mixamo jog: period %d frames (%.3f s), loop pose error %.2f deg, hips travel %s (%.3f m/s native)"
            % (P, native_T, math.degrees(worst), tuple(round(c, 3) for c in delta), delta.length / native_T))
        N = int(round(native_T * FPS))
        mean = Vector()
        for i in range(P):
            h = jog[i]["Hips"].to_translation() - delta * (i / P)
            mean += Vector((h.x, h.y, 0)) / P
        rest_h = self.rig.rest["Hips"].to_translation()
        centre = Vector((rest_h.x, rest_h.y, 0)) - mean
        poses = []
        for k in range(N + 1):
            t = k * P / N
            fr = sample_frames(jog, t)
            off = self.src["jog_offset"] + centre - delta * (t / P)
            poses.append(copy_world_pose(self.rig, fr, off)[0])
        poses, z, _ = self.clean_feet(poses, False)
        self.add("Jog_Mixamo_Loop", poses, True, "locomotion", root_motion_removed_m=round(delta.length, 3),
                 cycle_time_scale=round((N / FPS) / native_T, 4))
        return poses

    def strafe(self, R, sgn):
        """Side steps (sgn +1 = to the character's left, -1 = right): the leading foot steps out,
        the trailing foot closes; planted feet move at exactly the ground speed."""
        name = "Strafe_L_Loop" if sgn > 0 else "Strafe_R_Loop"
        T, d, w, lift = 0.62, 0.44, 0.105, 0.07
        N = int(round(T * FPS))
        base = R["Idle"][0]
        W0 = self.W(base)
        lead = "Left" if sgn > 0 else "Right"
        ank = {s: W0[s + "Foot"].to_translation() for s in ("Left", "Right")}
        fq = {s: W0[s + "Foot"].to_quaternion() for s in ("Left", "Right")}
        az = sum(a.z for a in ank.values()) / 2

        def g(ph, a, b):
            return d * sstep((ph - a) / (b - a))
        phs = [k / N for k in range(N)]
        c_mean = sum((g(ph, 0.0, 0.40) + g(ph, 0.50, 0.90)) / 2 - d * ph for ph in phs) / N
        poses = []
        for k in range(N + 1):
            ph = (k % N) / N
            P = {n: m.copy() for n, m in base.items()}
            W = self.W(P)
            bob = -0.022 - 0.010 * math.cos(4 * math.pi * (ph - 0.45))
            roll = math.radians(2.0) * math.sin(2 * math.pi * ph) * sgn
            hq = Quaternion(FWD, roll) @ self.rig.rot(W, "Hips")
            hp = W["Hips"].to_translation() + UP * bob
            W = self.rig.set_world(P, W, "Hips", Matrix.Translation(hp) @ hq.to_matrix().to_4x4())
            for n, k2 in (("Spine", -0.6), ("Chest", -0.4)):
                W = rotate_bone_world(self.rig, P, W, n, Quaternion(FWD, roll * k2))
            for side in ("Left", "Right"):
                is_lead = side == lead
                a0, a1 = (0.0, 0.40) if is_lead else (0.50, 0.90)
                x = (w if is_lead else -w) + g(ph, a0, a1) - d * ph - c_mean
                u = (ph - a0) / (a1 - a0)
                z = az + (lift * math.sin(math.pi * u) if 0 < u < 1 else 0.0)
                tgt = Vector((sgn * x, ank[side].y, z))
                fqq = Quaternion(UP, math.radians(5 if side == "Left" else -5)) @ fq[side]
                if 0 < u < 1:
                    fqq = Quaternion(LEFT, -math.radians(6) * math.sin(math.pi * u)) @ fqq
                W = self.limbs.leg(P, W, side, tgt, FWD + LEFT * (0.25 if side == "Left" else -0.25), fqq)
            sway = math.radians(4) * math.sin(2 * math.pi * ph)
            for side in ("Left", "Right"):
                W = rotate_bone_world(self.rig, P, W, side + "UpperArm", Quaternion(FWD, sway))
            poses.append(P)
        return self.add(name, poses, True, "locomotion", axis=Vector((-sgn, 0, 0)),
                        note="side steps; the body moves to the character's %s" % ("left" if sgn > 0 else "right"))

    def turn(self, R, sgn):
        """In-place 90 degree step turn (sgn +1 = left). The clip keeps the body facing the root:
        the gameplay root must yaw by sgn*90 deg over the clip following root_yaw (smoothstep of
        t / 0.85 s); the planted feet counter-rotate in the clip so they stay fixed on the ground."""
        name = "Turn_L_90" if sgn > 0 else "Turn_R_90"
        T, Tyaw = 1.0, 0.85
        N = int(round(T * FPS))
        idle = R["Idle"]
        total = math.radians(90) * sgn
        inner, outer = ("Left", "Right") if sgn > 0 else ("Right", "Left")
        W0 = self.W(idle[0])
        ank = {s: W0[s + "Foot"].to_translation() for s in ("Left", "Right")}
        fq = {s: W0[s + "Foot"].to_quaternion() for s in ("Left", "Right")}
        windows = {inner: (0.08, 0.45), outer: (0.42, 0.84)}
        poses, yaw_curve = [], []
        for k in range(N + 1):
            t = k / FPS
            th = total * sstep(t / Tyaw)
            yaw_curve.append(round(math.degrees(th), 2))
            P = {n: m.copy() for n, m in idle[k % (len(idle) - 1)].items()}
            W = self.W(P)
            dip = -0.018 * math.sin(math.pi * min(t / Tyaw, 1.0))
            W = self.rig.set_world(P, W, "Hips", Matrix.Translation(W["Hips"].to_translation() + UP * dip)
                                   @ self.rig.rot(W, "Hips").to_matrix().to_4x4())
            to_root = Quaternion(UP, -th)
            for side in ("Left", "Right"):
                a0, a1 = windows[side]
                u = (t / T - a0) / (a1 - a0)
                ang = total * sstep(u)
                lift = 0.055 * math.sin(math.pi * u) if 0 < u < 1 else 0.0
                world = Quaternion(UP, ang) @ ank[side] + UP * lift
                fworld = Quaternion(UP, ang) @ fq[side]
                pole = to_root @ (Quaternion(UP, ang) @ FWD) + LEFT * (0.2 if side == "Left" else -0.2)
                W = self.limbs.leg(P, W, side, to_root @ world, pole, to_root @ fworld)
            look = 0.30 * sgn * math.sin(math.pi * min(t / 0.7, 1.0))
            for n, share in (("Neck", 0.4), ("Head", 0.6)):
                W = rotate_bone_world(self.rig, P, W, n, Quaternion(UP, look * share))
            poses.append(P)
        return self.add(name, poses, False, "turn", root_yaw_deg=round(math.degrees(total)),
                        root_yaw_curve="smoothstep(t / %.2f s)" % Tyaw, root_yaw_samples_30fps=yaw_curve)

    def idle_shift(self, R):
        """Weight shift to the left leg and back; the right knee relaxes and its heel lifts."""
        idle = R["Idle"]
        L = len(idle) - 1
        N = 3 * L
        Ttot = N / FPS
        poses = []
        for k in range(N + 1):
            t = k / FPS
            P = {n: m.copy() for n, m in idle[k % L].items()}
            W = self.W(P)
            feet = {s: (W[s + "Foot"].to_translation(), W[s + "Foot"].to_quaternion()) for s in ("Left", "Right")}
            ball = W["RightFoot"] @ self.contacts["Right"]["ball"]
            sh = sstep((t - 1.0) / 1.3) * (1 - sstep((t - (Ttot - 2.5)) / 1.3))
            sh *= 1.0 + 0.06 * math.sin(2 * math.pi * t / 2.5)
            hp = W["Hips"].to_translation() + LEFT * 0.042 * sh + UP * (-0.006 * sh)
            hq = Quaternion(Vector((0, 1, 0)), -math.radians(4.5) * sh) @ self.rig.rot(W, "Hips")
            W = self.rig.set_world(P, W, "Hips", Matrix.Translation(hp) @ hq.to_matrix().to_4x4())
            for n, a in (("Spine", 2.5), ("Chest", 1.5), ("UpperChest", 0.5)):
                W = rotate_bone_world(self.rig, P, W, n, Quaternion(Vector((0, 1, 0)), math.radians(a) * sh))
            for side in ("Left", "Right"):
                ank, q = feet[side]
                if side == "Right":
                    rq = Quaternion(LEFT, math.radians(7) * sh)
                    ank = ball + rq @ (ank - ball)
                    q = rq @ q
                W = self.limbs.leg(P, W, side, ank, FWD + LEFT * (0.2 if side == "Left" else -0.2), q)
            poses.append(P)
        return self.add("Idle_Shift_Loop", poses, True, "standing", note="weight shift idle variant")

    def land_hard(self, R):
        land = R["Jump_Land"]
        Ws = world_series(self.rig, land)
        hz = [W["Hips"].to_translation().z for W in Ws]
        imp = int(np.argmin(hz[: len(hz) // 2 + 1]))
        poses = []
        for k, base in enumerate(land):
            t = (k - imp) / FPS
            bump = sstep((t + 0.06) / 0.12) * (1 - sstep((t - 0.12) / 0.5))
            P = {n: m.copy() for n, m in base.items()}
            W = self.W(P)
            feet = {s: (W[s + "Foot"].to_translation(), W[s + "Foot"].to_quaternion()) for s in ("Left", "Right")}
            hp = W["Hips"].to_translation() + UP * (-0.17 * bump) + FWD * (-0.03 * bump)
            W = self.rig.set_world(P, W, "Hips", Matrix.Translation(hp) @ self.rig.rot(W, "Hips").to_matrix().to_4x4())
            for n, a in (("Spine", 12), ("Chest", 9), ("UpperChest", 4), ("Neck", -9), ("Head", -6)):
                W = rotate_bone_world(self.rig, P, W, n, Quaternion(LEFT, math.radians(a) * bump))
            for side, sx in (("Left", 1), ("Right", -1)):
                W = rotate_bone_world(self.rig, P, W, side + "UpperArm", Quaternion(FWD, -sx * math.radians(14) * bump))
            for side in ("Left", "Right"):
                a, q = feet[side]
                W = self.limbs.leg(P, W, side, a, FWD + LEFT * (0.3 if side == "Left" else -0.3), q)
            poses.append(P)
        return self.add("Land_Hard", poses, False, "jump", note="Jump_Land with a deep knee bend")


    # ------------------------------------------------------------------ bicycle
    def load_bike(self):
        """Gray bicycle in the courier's space: turned to face -Y (the courier GLB faces Godot +Z;
        tools/setup_player.gd turns the model round, so courier root = bicycle root in Godot)."""
        new = import_any(BIKE)
        roots = [o for o in new if o.parent is None]
        for r in roots:
            r.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ r.matrix_world
        bpy.context.view_layer.update()
        ob = {o.name.split(".")[0]: o for o in new}
        bike = {"objects": new, "ob": ob}
        for n in ("Seat", "GripL", "GripR", "Crank", "PedalL", "PedalR"):
            bike[n] = ob[n].matrix_world.to_translation().copy()
        bike["crank_rest"] = ob["Crank"].matrix_world.copy()
        bike["pedal_rest"] = {n: ob[n].matrix_world.copy() for n in ("PedalL", "PedalR")}
        bike["crank_len"] = (Vector((0, bike["PedalR"].y, bike["PedalR"].z)) - Vector((0, bike["Crank"].y, bike["Crank"].z))).length
        # grip axes (outward), measured on the bars by tools/build_gray_bicycle.py (Godot bike space)
        gl, gr = Vector((-0.675, 0.104, 0.731)), Vector((0.693, 0.090, 0.716))
        bike["grip_axis"] = {"Left": Vector((-gl.x, gl.z, gl.y)).normalized(), "Right": Vector((-gr.x, gr.z, gr.y)).normalized()}
        log("bike markers (courier space):", {k: tuple(round(c, 4) for c in bike[k]) for k in ("Seat", "GripL", "GripR", "Crank", "PedalL", "PedalR")},
            "crank %.4f" % bike["crank_len"])
        self.bike = bike
        return bike

    def pedal(self, side, alpha):
        b = self.bike
        rest = b["PedalR" if side == "Right" else "PedalL"]
        off = rest - b["Crank"]
        return b["Crank"] + Quaternion(LEFT, alpha) @ off

    def pose_bike_crank(self, alpha):
        b = self.bike
        cr = b["ob"]["Crank"]
        C = b["Crank"]
        cr.matrix_world = Matrix.Translation(C) @ Quaternion(LEFT, alpha).to_matrix().to_4x4() @ Matrix.Translation(-C) @ b["crank_rest"]
        bpy.context.view_layer.update()
        for n in ("PedalL", "PedalR"):
            p = b["ob"][n]
            p.matrix_world = Matrix.Translation(p.matrix_world.to_translation()) @ b["pedal_rest"][n].to_3x3().to_4x4()
        bpy.context.view_layer.update()

    def hand_frame(self, side):
        """Rest hand direction (wrist -> middle knuckle), palm normal, in world."""
        R = self.rig.rest
        h = (R[side + "MiddleProximal"].to_translation() - R[side + "Hand"].to_translation())
        L = h.length
        h.normalize()
        t = R[side + "ThumbProximal"].to_translation() - R[side + "Hand"].to_translation()
        t = (t - h * t.dot(h)).normalized()
        palm = h.cross(t) * (1.0 if side == "Left" else -1.0)
        return h, palm.normalized(), L

    def grip_target(self, side):
        b = self.bike
        G = b["GripL" if side == "Left" else "GripR"]
        g = b["grip_axis"][side]
        h0, p0, L = self.hand_frame(side)
        d = FWD - g * FWD.dot(g)
        d = (d.normalized() - UP * 0.55).normalized()
        d = (d - g * d.dot(g)).normalized()
        n = g.cross(d).normalized()
        if n.z > 0:
            n = -n
        F0 = Matrix((h0, p0, h0.cross(p0))).transposed()
        F1 = Matrix((d, n, d.cross(n))).transposed()
        q = (F1 @ F0.inverted()).to_quaternion() @ self.rig.rest_rot[side + "Hand"]
        wrist = G - d * (0.80 * L) - n * 0.034
        return wrist, q, p0

    def grip_hand(self, P, W, side):
        wrist, q, p0 = self.grip_target(side)
        pole = LEFT * (0.55 if side == "Left" else -0.55) + Vector((0, 0.65, 0)) - UP * 0.45
        W = self.limbs.arm(P, W, side, wrist, pole, q)
        # fingers wrap the grip, thumb under it
        for f, angs in (("Index", (62, 80, 50)), ("Middle", (66, 84, 52)), ("Ring", (70, 86, 52)), ("Little", (74, 86, 50)),
                        ("Thumb", (18, 28, 30))):
            parts = dict(FINGERS)[f]
            for part, a in zip(parts, angs):
                n_ = side + f + part
                if n_ not in self.rig.rest:
                    continue
                i = parts.index(part)
                nxt = side + f + parts[i + 1] if i + 1 < len(parts) else None
                R = self.rig.rest
                fd = ((R[nxt].to_translation() if nxt else R[n_] @ Vector((0, 0.03, 0))) - R[n_].to_translation()).normalized()
                ax = fd.cross(p0).normalized()
                P[n_] = Quaternion(self.rig.rest_rot[n_].inverted() @ ax, math.radians(a)).to_matrix().to_4x4()
        return self.rig.fk(P)

    def bike_pose(self, alpha, hips_pos, lean, breath=0.0, rock=0.0, pitch_feet=0.0):
        base = self.idle0
        P = {n: m.copy() for n, m in base.items()}
        for n in P:          # fingers and arms from scratch
            if any(k in n for k in ("Thumb", "Index", "Middle", "Ring", "Little")):
                P[n] = Matrix.Identity(4)
        W = self.W(P)
        hq = Quaternion(LEFT, math.radians(14)) @ Quaternion(FWD, rock) @ self.rig.rest_rot["Hips"]
        W = self.rig.set_world(P, W, "Hips", Matrix.Translation(hips_pos) @ hq.to_matrix().to_4x4())
        rest_lean = lean - 14
        for n, share in (("Spine", 0.38), ("Chest", 0.34), ("UpperChest", 0.28)):
            a = rest_lean * share + (breath if n == "Chest" else 0.0)
            W = rotate_bone_world(self.rig, P, W, n, Quaternion(LEFT, math.radians(a)))
        for n, share in (("Neck", -0.42), ("Head", -0.40)):
            W = rotate_bone_world(self.rig, P, W, n, Quaternion(LEFT, math.radians(lean * share)))
        for side, sx in (("Left", 1), ("Right", -1)):
            W = rotate_bone_world(self.rig, P, W, side + "Shoulder", Quaternion(UP, -sx * math.radians(7)))
        for side in ("Left", "Right"):
            W = self.grip_hand(P, W, side)
        for side in ("Left", "Right"):
            q = Quaternion(LEFT, pitch_feet) @ self.rig.rest_rot[side + "Foot"]
            top = self.pedal(side, alpha) + UP * 0.012
            ank = top - q @ self.contacts[side]["ball"]
            W = self.limbs.leg(P, W, side, ank, FWD + LEFT * (0.10 if side == "Left" else -0.10), q, stretch=0.999)
        return P, W

    def seat_contact(self, P):
        """Lowest point of the buttocks (rest-pose region around the sit bones) over the saddle."""
        if not hasattr(self, "pelvis_mask"):
            rest = mesh_np(self.mesh, world=False)
            hz = self.rig.rest["Hips"].to_translation().z
            self.pelvis_mask = (rest[:, 2] > hz - 0.16) & (rest[:, 2] < hz + 0.02) & (np.abs(rest[:, 0]) < 0.13) & (rest[:, 1] > -0.01)
        apply_pose(self.arm, P)
        co = evaluated_np([self.mesh])[0]
        S = self.bike["Seat"]
        sel = self.pelvis_mask & (np.abs(co[:, 0] - S.x) < 0.075) & (co[:, 1] > S.y - 0.11) & (co[:, 1] < S.y + 0.09)
        return float(co[sel, 2].min()) if sel.any() else None

    def reach(self, W, side):
        """Shoulder -> wrist target distance over the arm length (1 = straight arm)."""
        l1, l2 = self.limbs.len[side + "UpperArm"]
        return (self.grip_target(side)[0] - W[side + "UpperArm"].to_translation()).length / (l1 + l2)

    def bike_clips(self, R):
        self.load_bike()
        self.idle0 = R["Idle"][0]
        S = self.bike["Seat"]
        hips = S + UP * 0.16 + FWD * 0.02
        lean = 26.0
        for it in range(4):
            lo, hi = 10.0, 80.0         # trunk lean: elbows slightly bent (wrist at 0.975 of the arm)
            for _ in range(14):
                lean = (lo + hi) / 2
                P, W = self.bike_pose(0.0, hips, lean)
                r = max(self.reach(W, s) for s in ("Left", "Right"))
                if r > 0.975:
                    lo = lean
                else:
                    hi = lean
            P, W = self.bike_pose(0.0, hips, lean)
            zc = self.seat_contact(P)
            dz = (S.z - 0.006) - zc
            hips = hips + UP * dz
            sh = (W["LeftUpperArm"].to_translation() + W["RightUpperArm"].to_translation()) / 2
            trunk = math.degrees(math.atan2(-(sh - hips).y, (sh - hips).z))
            self.trunk = trunk
            log("  bike fit it %d: seat gap %.4f -> hips %s, lean param %.1f (trunk %.1f deg from vertical), reach %.3f"
                % (it, dz, tuple(round(c, 3) for c in hips), lean, trunk, r))
        self.bike_hips, self.bike_lean = hips, lean
        knees = []
        N = 30
        poses = []
        for k in range(N + 1):
            a = 2 * math.pi * k / N
            P, W = self.bike_pose(a, hips, lean, breath=0.0, rock=math.radians(1.2) * math.sin(a))
            poses.append(P)
            for side in ("Left", "Right"):
                hp, kn, an = (W[side + n].to_translation() for n in ("UpperLeg", "LowerLeg", "Foot"))
                q = self.rig.rest_rot[side + "Foot"]
                want = self.pedal(side, a) + UP * 0.012 - q @ self.contacts[side]["ball"]
                knees.append((round(math.degrees(a)), side, round(180 - math.degrees((hp - kn).angle(an - kn)), 1),
                              round((want - hp).length / sum(self.limbs.len[side + "UpperLeg"]), 3)))
        rmax = max(k[3] for k in knees)
        L = sum(self.limbs.len["LeftUpperLeg"])
        log("  leg reach: max hip-ankle target / leg = %.3f -> saddle change for 30 deg knee flexion at the bottom: %+.3f m"
            % (rmax, (math.cos(math.radians(15)) - rmax) * L))
        flex = [k[2] for k in knees]
        log("  knee flexion over the stroke: min %.1f max %.1f deg" % (min(flex), max(flex)))
        self.knees = knees
        self.add("Bike_Pedal_Loop", poses, True, "bike", crank_deg_per_s=360.0 / (N / FPS),
                 note="one forward crank revolution; frame k <-> crank angle 360*k/%d deg from rest (right crank forward)" % N,
                 knee_flexion_min_deg=min(flex), knee_flexion_max_deg=max(flex))
        seated = []
        M = 60
        for k in range(M + 1):
            br = 1.2 * math.sin(2 * math.pi * k / M)
            P, W = self.bike_pose(0.0, hips, lean, breath=br)
            seated.append(P)
        Wd = self.W(seated[0])
        self.add("Bike_Seated_Loop", seated, True, "bike", note="crank at rest (right pedal forward), breathing",
                 hips_bike_space_godot=[round(c, 4) for c in to_godot_bike(Wd["Hips"].to_translation())])
        return poses, seated


def apply_pose(arm, P):
    for pb in arm.pose.bones:
        if pb.name in P:
            pb.matrix_basis = P[pb.name]
    bpy.context.view_layer.update()


def to_godot_bike(v):
    """Courier Blender space (faces -Y) -> gray bicycle Godot space (faces -Z)."""
    return Vector((-v.x, v.z, v.y))


# ----------------------------------------------------------------------------- QA renders
def render_setup(res=900, engine='WORKBENCH'):
    sc = bpy.context.scene
    if engine == 'WORKBENCH':
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.light = 'STUDIO'
        sc.display.shading.color_type = 'TEXTURE'
        sc.display.shading.show_shadows = False
    else:
        try:
            sc.render.engine = 'BLENDER_EEVEE'
        except TypeError:
            sc.render.engine = 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    w = bpy.data.worlds.get("QAWorld") or bpy.data.worlds.new("QAWorld")
    sc.world = w
    w.color = (0.32, 0.34, 0.38)
    w.use_nodes = True
    bg = next((n for n in w.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg:
        bg.inputs[0].default_value = (0.42, 0.44, 0.48, 1)
        bg.inputs[1].default_value = 0.9
    cam = bpy.data.objects.get("QACam")
    if cam is None:
        cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
        sc.collection.objects.link(cam)
    sc.camera = cam
    for mat in bpy.data.materials:
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
                    mat.node_tree.nodes.active = n
    if engine != 'WORKBENCH' and not bpy.data.objects.get("QASun"):
        sun = bpy.data.objects.new("QASun", bpy.data.lights.new("QASun", 'SUN'))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
        sc.collection.objects.link(sun)
    return cam


def shoot(cam, path, direction, target, ortho, persp_dist=None):
    d = Vector(direction).normalized()
    if persp_dist:
        cam.data.type = 'PERSP'
        cam.data.lens = 50
        cam.location = Vector(target) + d * persp_dist
    else:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
        cam.location = Vector(target) + d * 12
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = 100
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def ground_plane(size=6):
    g = bpy.data.objects.get("QAGround")
    if g:
        return g
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "QAGround"
    m = bpy.data.materials.new("QAGroundMat")
    m.diffuse_color = (0.55, 0.55, 0.52, 1)
    g.data.materials.append(m)
    return g


def qa_rest(tag, arm, mesh):
    os.makedirs(QA, exist_ok=True)
    cam = render_setup()
    ground_plane()
    H = float(mesh_np(mesh)[:, 2].max())
    tgt = (0, 0, H / 2)
    for name, d in (("front", (0, -1, 0.05)), ("side", (1, 0, 0.05)), ("back", (0, 1, 0.05)), ("34", (0.7, -0.7, 0.25))):
        shoot(cam, os.path.join(QA, "%s_rest_%s.png" % (tag, name)), d, tgt, H * 1.1)
    shoot(cam, os.path.join(QA, "%s_rest_face.png" % tag), (0.3, -1, 0.08), (0, -0.02, H - 0.13), 0.42)


def compose(paths, out, cols=None):
    ims = [bpy.data.images.load(p) for p in paths]
    w, h = ims[0].size
    cols = cols or len(ims)
    rows = (len(ims) + cols - 1) // cols
    canvas = np.ones((rows * h, cols * w, 4), np.float32)
    for i, im in enumerate(ims):
        a = pixels(im)
        r, c = i // cols, i % cols
        canvas[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = a
    res = bpy.data.images.new("strip", cols * w, rows * h, alpha=False)
    res.pixels.foreach_set(canvas.ravel())
    res.filepath_raw = out
    res.file_format = 'PNG'
    res.save()
    for im in ims:
        bpy.data.images.remove(im)
    bpy.data.images.remove(res)
    for p in paths:
        os.remove(p)


def render_strip(arm, poses, path, count=6, view=(1, 0, 0.06), ortho=2.2, target=(0, 0, 0.95), res=420):
    sc = bpy.context.scene
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    cam = bpy.data.objects["QACam"]
    n = len(poses) - 1 if len(poses) > 1 else 1
    idx = sorted(set(int(round(i * n / count)) for i in range(count)))
    tmp = []
    for i in idx:
        apply_pose(arm, poses[min(i, len(poses) - 1)])
        p = path[:-4] + "_%02d.png" % i
        shoot(cam, p, view, target, ortho)
        tmp.append(p)
    compose(tmp, path, cols=4)


def checker_ground():
    g = ground_plane(8)
    m = g.data.materials[0]
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    ch = nt.nodes.new("ShaderNodeTexChecker")
    ch.inputs["Scale"].default_value = 16.0
    ch.inputs["Color1"].default_value = (0.62, 0.62, 0.6, 1)
    ch.inputs["Color2"].default_value = (0.42, 0.42, 0.4, 1)
    nt.links.new(ch.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = ch
    return g


def bag_parts(C, R):
    """Worn backpack fit, skinned shoulder straps and the bag / carry clips (tools/courier_bag.py)."""
    import courier_bag
    courier_bag.bind(globals())
    BW = courier_bag.BagWork(C, R)
    BW.run()
    return BW


def bag_args():
    only = None
    for a in ARGS:
        if a.startswith("--clips="):
            only = set(a.split("=", 1)[1].split(","))
    return only


def bag_stage():
    lib = load_library()
    arm, mesh, src = build_courier(lib)
    C = Clips(arm, mesh, lib, src)
    R = C.library_clips()
    C.mixamo_jog()
    C.strafe(R, +1)
    C.turn(R, +1)
    C.land_hard(R)
    C.bike_clips(R)
    BW = bag_parts(C, R)
    if "--no-qa" not in ARGS:
        BW.qa(C.bike, worn="--no-worn" not in ARGS, only=bag_args())
    log("bag stage done; clips:", list(BW.clips))


def player_stage():
    lib = load_library()
    arm, mesh, src = build_courier(lib)
    C = Clips(arm, mesh, lib, src)
    R = C.library_clips()
    C.mixamo_jog()
    C.strafe(R, +1)
    C.strafe(R, -1)
    C.turn(R, +1)
    C.turn(R, -1)
    C.idle_shift(R)
    C.land_hard(R)
    pedal, seated = C.bike_clips(R)
    BW = bag_parts(C, R)
    bike_objs = C.bike["objects"]
    for o in bike_objs:
        o.hide_render = True
    qa_rest("courier", arm, mesh)
    for o in bike_objs:
        o.hide_render = False
    # --- QA: rider fit on the bicycle
    os.makedirs(FIT_DIR, exist_ok=True)
    os.makedirs(QA, exist_ok=True)
    cam = render_setup(900)
    checker_ground()
    N = len(pedal) - 1
    for deg in (0, 90, 180, 270):
        k = int(round(deg / 360 * N))
        C.pose_bike_crank(math.radians(deg))
        apply_pose(arm, pedal[k])
        for vname, d, tgt, sc_ in (("side", (-1, 0, 0.04), (0, 0.0, 0.75), 2.3), ("front", (0, -1, 0.06), (0, 0, 0.8), 1.9),
                                   ("34", (-0.75, -0.62, 0.3), (0, 0, 0.8), 2.3)):
            shoot(cam, os.path.join(FIT_DIR, "rider_fit_%03d_%s.png" % (deg, vname)), d, tgt, sc_)
    C.pose_bike_crank(0.0)
    apply_pose(arm, seated[0])
    shoot(cam, os.path.join(FIT_DIR, "rider_fit_seated_side_left.png"), (1, 0, 0.04), (0, 0, 0.75), 2.3)
    shoot(cam, os.path.join(FIT_DIR, "rider_fit_seated_closeup_hands.png"), (-0.5, -0.8, 0.5), C.bike["GripR"], 0.55)
    shoot(cam, os.path.join(FIT_DIR, "rider_fit_seated_closeup_feet.png"), (-1, -0.15, 0.1), C.bike["Crank"] + UP * 0.05, 0.8)
    shoot(cam, os.path.join(FIT_DIR, "rider_fit_seated_closeup_seat.png"), (-1, 0.2, 0.15), C.bike["Seat"], 0.6)
    if "--no-qa" not in ARGS:
        BW.qa(C.bike, worn="--no-worn" not in ARGS, only=bag_args())
    for o in BW.strap_objs.values():
        o.hide_render = True
    for o in C.bike["objects"]:
        if o.name in bpy.data.objects:
            bpy.data.objects.remove(o)
    # --- QA: clip strips (side view, checker ground for foot sliding)
    for name, poses, meta in C.out:
        if meta["kind"] == "bike" or name in BW.clips or "--no-qa" in ARGS:
            continue
        view = (1, 0, 0.06) if "Strafe" not in name else (0, -1, 0.06)
        render_strip(arm, poses, os.path.join(QA, "clip_%s.png" % name), count=8, view=view)
    # --- actions and export
    for name, poses, meta in C.out:
        write_action(arm, C.rig, name, poses)
    set_action(arm, bpy.data.actions.get("Idle_Loop"))
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    BW.export_plain_worn()
    straps = list(BW.strap_objs.values())
    for o in list(bpy.data.objects):
        if o not in [arm, mesh] + straps:
            bpy.data.objects.remove(o)
    set_action(arm, None)
    path = os.path.join(OUT, "courier.glb")
    export_rigged([arm, mesh] + straps, path, True)
    V = mesh_np(mesh)
    clips = {}
    for name, poses, meta in C.out:
        game = name[:-5] if name.endswith("_Loop") else name
        clips[game] = meta
    info = {"model": "res://assets/player/courier.glb", "source": "source_assets/incoming_2026_10_22/Ch42_nonPBR.fbx (Mixamo)",
            "height_m": round(float(V[:, 2].max()), 3), "triangles": tris([mesh]), "bones": len(arm.data.bones),
            "textures": {im.name: list(im.size) for im in bpy.data.images if im.name.startswith("Courier_")},
            "facing": "-Y blender / +Z godot (courier.tscn turns the model to face -Z)",
            "bike": {"seat": [round(c, 4) for c in to_godot_bike(C.bike["Seat"])], "lean_param": round(C.bike_lean, 1), "trunk_lean_deg": round(C.trunk, 1),
                     "hips": [round(c, 4) for c in to_godot_bike(C.bike_hips)],
                     "crank_length": round(C.bike["crank_len"], 4), "knees": C.knees},
            "fps": FPS, "clips": clips, "backpack": BW.bag_meta}
    with open(os.path.join(OUT, "clips_blender.json"), "w") as f:
        json.dump(info, f, indent=1)
    log("info written; clips:", list(clips))


# ----------------------------------------------------------------------------- Avaturn door customer
AVATURN_SRC = "model-_anim-_talking_visio_win.glb"
AVATURN_HEIGHT = 1.82


def flatten_keys(keep):
    """flatten() that also moves shape keys (Mesh.transform leaves them by default)."""
    for o in keep:
        mw = o.matrix_world.copy()
        o.parent = None
        if o.type == 'MESH':
            o.data.transform(mw, shape_keys=True)
        elif o.type == 'ARMATURE':
            o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o)


def bake_into_slot(arm, rig, act, poses):
    """Replace the armature channels of a slotted action (keeping its shape-key slots)."""
    set_action(arm, act)
    slot = arm.animation_data.action_slot
    for layer in act.layers:
        for strip in layer.strips:
            cb = strip.channelbag(slot)
            if cb:
                for fc in list(cb.fcurves):
                    cb.fcurves.remove(fc)
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    n = len(poses)
    for b in rig.order:
        if b == "Root":
            continue
        quats, prev = [], None
        for P in poses:
            q = P[b].to_quaternion()
            if prev is not None and prev.dot(q) < 0:
                q = -q
            quats.append(q)
            prev = q
        chans = [("rotation_quaternion", 4, [[q[i] for q in quats] for i in range(4)])]
        if b == "Hips":
            locs = [P[b].to_translation() for P in poses]
            chans.append(("location", 3, [[l[i] for l in locs] for i in range(3)]))
        for prop, count, vals in chans:
            path = 'pose.bones["%s"].%s' % (b, prop)
            for i in range(count):
                fc = act.fcurve_ensure_for_datablock(arm, path, index=i, group_name=b)
                fc.keyframe_points.add(n)
                co = np.empty(2 * n)
                co[0::2] = np.arange(n) + int(round(act.frame_range[0]))
                co[1::2] = vals[i]
                fc.keyframe_points.foreach_set("co", co)
                for k in fc.keyframe_points:
                    k.interpolation = 'LINEAR'
                fc.update()


def avaturn_stage():
    lib = load_library()
    reset()
    import_any(os.path.join(SRC, AVATURN_SRC))
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    mapping = dict(MIXAMO)
    mapping[strip_name(next(b.name for b in arm.data.bones if b.parent is None))] = "Root"
    rename_bones(arm, meshes, mapping)
    act = next(a for a in bpy.data.actions)
    names = [b.name for b in arm.data.bones if b.name in HUMANOID_SET]
    f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
    talk = capture(arm, act, names, range(f0, f1 + 1))
    log("avaturn: %d bones, %d meshes, clip %s frames %d..%d at %.0f fps" % (len(arm.data.bones), len(meshes), act.name, f0, f1, fps))
    set_action(arm, None)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(f0)
    flatten_keys([arm] + meshes)
    set_action(arm, None)
    V = np.concatenate([mesh_np(o) for o in meshes])
    k = AVATURN_HEIGHT / float(V[:, 2].max() - V[:, 2].min())
    S = Matrix.Scale(k, 4)
    for o in meshes:
        o.data.transform(S, shape_keys=True)
    arm.data.transform(S)
    ends = [b.name for b in arm.data.bones if b.name not in HUMANOID_SET]
    remove_bones(arm, meshes, ends)
    add_root(arm)
    # one static body mesh, the face / eyes / teeth keep their blend shapes as separate meshes
    plain = [o for o in meshes if not o.data.shape_keys]
    keyed = [o for o in meshes if o.data.shape_keys]
    t0 = tris(meshes)
    for o in plain:
        if tris([o]) > 6500:
            decimate(o, 0.55)
    if len(plain) > 1:
        select_only(plain, plain[0])
        bpy.ops.object.join()
    body = plain[0]
    body.name = body.data.name = "CustomerBody"
    for o in keyed:
        o.name = o.data.name = "Customer_" + ("Head" if len(o.data.shape_keys.key_blocks) > 60 else o.name)
    meshes = [body] + keyed
    for o in meshes:
        for md in o.modifiers:
            if md.type == 'ARMATURE':
                md.object = arm
        limit_and_normalize(o)
    for im in bpy.data.images:
        if max(im.size) > 1024:
            im.scale(1024, 1024)
    log("avaturn tris %d -> %d, scale %.4f" % (t0, tris(meshes), k))
    arm.name = arm.data.name = "Armature"
    corr = match_rest(arm, meshes, lib["dirs"])
    zmin = float(np.concatenate([mesh_np(o) for o in meshes])[:, 2].min())
    for o in meshes:
        o.data.transform(Matrix.Translation((0, 0, -zmin)), shape_keys=True)
    arm.data.transform(Matrix.Translation((0, 0, -zmin)))
    for o in meshes:
        o.parent = arm
        o.matrix_parent_inverse = Matrix.Identity(4)
    log("rest matched: largest correction %.1f deg, ground %.4f" % (corr, zmin))
    rig = Rig(arm)
    off = Vector((0, 0, -zmin))
    poses = []
    for fr in talk:
        sc_fr = {n: Matrix.Translation(m.to_translation() * k) @ m.to_quaternion().to_matrix().to_4x4() for n, m in fr.items()}
        poses.append(copy_world_pose(rig, sc_fr, off)[0])
    # The source clip talks to someone off to the side (body turned ~30-70 deg): turn the whole
    # clip by its mean yaw so the customer faces the courier at the door (one constant rotation,
    # so the feet do not slide).
    yaws = []
    for P in poses:
        W = rig.fk(P)
        f = (W["Hips"].to_quaternion() @ rig.rest_rot["Hips"].inverted()) @ Vector((0, -1, 0))
        yaws.append(math.atan2(f.x, -f.y))
    mean = math.atan2(sum(math.sin(y) for y in yaws), sum(math.cos(y) for y in yaws))
    log("talk clip yaw: mean %.1f, range %.1f..%.1f deg" % (math.degrees(mean), math.degrees(min(yaws)), math.degrees(max(yaws))))
    R = Matrix.Rotation(-mean, 4, 'Z')
    for P in poses:
        W = rig.fk(P)
        rig.set_world(P, W, "Hips", R @ W["Hips"])
    act.name = "Talk"
    bake_into_slot(arm, rig, act, poses)
    act.use_fake_user = True
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    path = os.path.join(OUT, "customer_avaturn.glb")
    export_rigged([arm] + meshes, path, True, morph=True)
    V = np.concatenate([mesh_np(o) for o in meshes])
    info = {"model": "res://assets/player/customer_avaturn.glb", "source": "source_assets/incoming_2026_10_22/" + AVATURN_SRC,
            "height_m": round(float(V[:, 2].max()), 3), "triangles": tris(meshes), "bones": len(arm.data.bones),
            "blend_shape_meshes": {o.name: len(o.data.shape_keys.key_blocks) - 1 for o in keyed},
            "clip": "Talk", "clip_seconds": round((f1 - f0) / fps, 3), "fps": fps,
            "textures_max": max(max(im.size) for im in bpy.data.images if im.users)}
    with open(os.path.join(OUT, "customer_avaturn.json"), "w") as f:
        json.dump(info, f, indent=1)
    log("avaturn info", info)
    # QA
    os.makedirs(QA, exist_ok=True)
    cam = render_setup(700)
    ground_plane()
    H = float(V[:, 2].max())
    set_action(arm, None)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for name, d in (("front", (0, -1, 0.05)), ("side", (1, 0, 0.05)), ("34", (0.7, -0.7, 0.25))):
        shoot(cam, os.path.join(QA, "customer_rest_%s.png" % name), d, (0, 0, H / 2), H * 1.1)
    set_action(arm, act)
    for f in (f0 + 40, f0 + 160):
        sc.frame_set(f)
        shoot(cam, os.path.join(QA, "customer_talk_%d.png" % f), (0.3, -1, 0.05), (0, 0, H / 2), H * 1.1)
        shoot(cam, os.path.join(QA, "customer_talk_face_%d.png" % f), (0.3, -1, 0.05), (0, -0.05, H - 0.12), 0.4)


# ----------------------------------------------------------------------------- clothed pedestrian
CLOTHED_SRC = "character_with_clothes.glb"
CLOTHED_ID = "clothed_man"
CLOTHED_HEIGHT = 1.72        # source scale (A-pose legs); ~1.80 m after the library rest straightens the legs
CLOTHED_TRIS = 24000


def characters_module():
    """tools/prepare_characters.py helpers (fitted humanoid rig, bone-heat rescue, leg fixes)."""
    path = os.path.join(ROOT, "tools", "prepare_characters.py")
    src = open(path, encoding="utf-8").read()
    src = src[:src.rindex("\nmain()")]
    ns = {"__name__": "prepare_characters", "__file__": path}
    exec(compile(src, path, "exec"), ns)
    return ns


def fix_arm_torso_weights(mesh, arm):
    """Bone heat bleeds between the arms and the torso at the armpits on loose shirts: below the
    armpit, torso-side vertices lose any arm weight (-> UpperChest / Chest), and arm vertices well
    outside the shoulder lose any spine weight (-> UpperArm)."""
    idx = {g.name: g for g in mesh.vertex_groups}
    name_of = {g.index: g.name for g in mesh.vertex_groups}
    changed = 0
    for side, sx in (("Left", -1.0), ("Right", 1.0)):     # faces +Y here: left is -X
        ua = arm.data.bones[side + "UpperArm"].head_local
        arm_groups = {side + n for n in ("UpperArm", "LowerArm", "Hand")} | {side + f + p for f, ps in FINGERS for p in ps}
        torso_groups = {"Hips", "Spine", "Chest", "UpperChest"}
        for v in mesh.data.vertices:
            x = v.co.x * sx
            if x <= 0:
                continue
            inner = x < abs(ua.x) - 0.03 and v.co.z < ua.z - 0.05
            outer = x > abs(ua.x) + 0.05
            drop = arm_groups if inner else (torso_groups if outer else set())
            if not drop:
                continue
            moved = 0.0
            for g in list(v.groups):
                n = name_of[g.group]
                if n in drop and g.weight > 0:
                    moved += g.weight
                    idx[n].remove([v.index])
            if moved > 0:
                target = ("UpperChest" if v.co.z > ua.z - 0.12 else "Chest") if inner else side + "UpperArm"
                (idx.get(target) or mesh.vertex_groups.new(name=target)).add([v.index], moved, 'ADD')
                changed += 1
    return changed


def sleeve_weights(mesh, arm):
    """Shirt sleeves follow the arm inside them: sleeve / shoulder-cap vertices take the weights of
    the nearest arm-skin vertex (blended in over 6 cm from the shoulder joint outwards), so the
    sleeve no longer stays with the chest and opens a gap when the arm swings."""
    me = mesh.data
    mats = [m.name if m else "" for m in me.materials]
    vmat = np.full(len(me.vertices), -1)
    for poly in me.polygons:
        for vi in poly.vertices:
            vmat[vi] = poly.material_index
    skin_ids = {i for i, n in enumerate(mats) if "Skin" in n}
    shirt_ids = {i for i, n in enumerate(mats) if "Shirt" in n}
    name_of = {g.index: g.name for g in mesh.vertex_groups}
    groups = {g.name: g for g in mesh.vertex_groups}
    changed = 0
    for side, sx in (("Left", -1.0), ("Right", 1.0)):
        ua = arm.data.bones[side + "UpperArm"].head_local
        x0 = abs(ua.x) - 0.04
        src = [v for v in me.vertices if vmat[v.index] in skin_ids and v.co.x * sx > abs(ua.x) - 0.01 and v.co.z < ua.z + 0.08]
        if not src:
            continue
        kd = KDTree(len(src))
        for i, v in enumerate(src):
            kd.insert(v.co, i)
        kd.balance()
        for v in me.vertices:
            if vmat[v.index] not in shirt_ids or v.co.x * sx < x0:
                continue
            w = sstep((v.co.x * sx - x0) / 0.06)
            _, j, _ = kd.find(v.co)
            donor = {name_of[g.group]: g.weight for g in src[j].groups if g.weight > 1e-4}
            own = {name_of[g.group]: g.weight for g in v.groups if g.weight > 1e-4}
            mix = {n: own.get(n, 0.0) * (1 - w) + donor.get(n, 0.0) * w for n in set(own) | set(donor)}
            for n in own:
                groups[n].remove([v.index])
            for n, val in mix.items():
                if val > 1e-4:
                    (groups.get(n) or mesh.vertex_groups.new(name=n)).add([v.index], val, 'REPLACE')
            changed += 1
    return changed


def clothed_stage():
    lib = load_library()
    pc = characters_module()
    tb, tm = pc["template_skeleton"]()
    reset()
    import_any(os.path.join(SRC, CLOTHED_SRC))
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    flatten(meshes)
    # the second skin object is a coincident duplicate of the arms / hands?
    skins = [o for o in meshes if "Skin" in o.name]
    if len(skins) == 2:
        big, small = sorted(skins, key=lambda o: len(o.data.vertices), reverse=True)
        kd = KDTree(len(big.data.vertices))
        for v in big.data.vertices:
            kd.insert(v.co, v.index)
        kd.balance()
        d = np.array([kd.find(small.data.vertices[i].co)[2] for i in range(0, len(small.data.vertices), 7)])
        log("duplicate skin check: median distance %.4f (units)" % float(np.median(d)))
        if float(np.median(d)) < 0.05:          # cm units: < 0.5 mm -> coincident copy
            meshes.remove(small)
            bpy.data.objects.remove(small)
    V = np.concatenate([mesh_np(o) for o in meshes])
    k = CLOTHED_HEIGHT / float(np.ptp(V[:, 2]))
    pc["apply_global"](meshes, Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(k, 4))
    body = pc["join"](meshes, "Body")
    pc["clean_mesh"](body, merge=1e-5)
    V = mesh_np(body)
    cx = 0.5 * (V[:, 0].min() + V[:, 0].max())
    pc["apply_global"]([body], Matrix.Translation((-cx, 0, -float(V[:, 2].min()))))
    m = pc["measure"](mesh_np(body))
    pc["apply_global"]([body], Matrix.Translation((0, -m["hips"], 0)))
    m = pc["measure"](mesh_np(body))
    log("clothed: scale %.4f, landmarks H %.3f armpit %.3f wrist %.3f hand %.3f" % (k, m["H"], m["armpit"], m["wrist_x"], m["hand_len"]))
    log("  legs unpinched at %d midline vertices" % pc["unpinch_legs"](body, m["H"]))
    arm = pc["build_rig"](m, tb, tm)
    t0 = tris([body])
    pc["decimate"](body, CLOTHED_TRIS)
    log("  tris %d -> %d" % (t0, tris([body])))
    method = pc["auto_weights"](body, arm)
    log("  weights:", method)
    log("  cross-leg weights removed on %d vertices" % pc["enforce_leg_sides"](body, m["H"]))
    log("  arm / torso weights fixed on %d vertices" % fix_arm_torso_weights(body, arm))
    log("  sleeve weights from the arms on %d vertices" % sleeve_weights(body, arm))
    log("  unweighted patched: %d" % pc["fix_unweighted"](body, arm))
    pc["limit_and_normalize"](body)
    pc["merge_trivial_materials"]([body])
    pc["downsize_images"]([body], 1024)
    # face -Y (Godot +Z, the retarget convention), then the library rest
    pc["apply_global"]([arm, body], Matrix.Rotation(math.pi, 4, 'Z'))
    arm.name = arm.data.name = "Armature"
    body.parent = arm
    body.matrix_parent_inverse = Matrix.Identity(4)
    for md in body.modifiers:
        if md.type == 'ARMATURE':
            md.object = arm
    corr = match_rest(arm, [body], lib["dirs"])
    zmin = float(mesh_np(body)[:, 2].min())
    pc["apply_global"]([arm, body], Matrix.Translation((0, 0, -zmin)))
    log("  rest matched (largest correction %.1f deg), ground %.4f" % (corr, zmin))
    path = os.path.join(PEOPLE, CLOTHED_ID + ".glb")
    export_rigged([arm, body], path, False)
    V = mesh_np(body)
    info = {"id": CLOTHED_ID, "path": "res://assets/sketchup/people/%s.glb" % CLOTHED_ID,
            "height": round(float(V[:, 2].max()), 3), "tris": tris([body]), "rest_pose": "T (library rest)",
            "bones_total": len(arm.data.bones), "clips": [], "facing": "-Y blender / +Z godot (humanoid retarget convention)",
            "rig": "auto (fitted humanoid, %s, armpit/crotch fixes)" % method,
            "source": "source_assets/incoming_2026_10_22/" + CLOTHED_SRC}
    jp = os.path.join(PEOPLE, "humanoids.json")
    try:
        entries = json.load(open(jp))
    except (OSError, ValueError):
        entries = []
    entries = [e for e in entries if e.get("id") != CLOTHED_ID] + [info]
    with open(jp, "w") as f:
        json.dump(entries, f, indent=2)
    log("clothed info", info)
    # QA: rest views and library clips transferred onto the new rig (weights at shoulders / hips)
    os.makedirs(QA, exist_ok=True)
    C = Clips(arm, body, lib, None)
    cam = render_setup(420)
    ground_plane()
    for name, d in (("front", (0, -1, 0.05)), ("side", (1, 0, 0.05)), ("34", (0.7, -0.7, 0.25))):
        shoot(cam, os.path.join(QA, "%s_rest_%s.png" % (CLOTHED_ID, name)), d, (0, 0, 0.9), 2.0)
    for clip, view in (("Walk_Loop", (1, 0, 0.06)), ("Walk_Loop", (0.6, -0.8, 0.1)), ("Interact", (0.6, -0.8, 0.1)),
                       ("Sitting_Idle_Loop", (0.8, -0.6, 0.15)), ("Jump_Start", (0.6, -0.8, 0.1))):
        poses = C.ual(clip)
        render_strip(arm, poses, os.path.join(QA, "%s_%s_%d.png" % (CLOTHED_ID, clip, int(view[0] * 10))), count=4, view=view)


# ----------------------------------------------------------------------------- main
def main():
    stage = ARGS[0] if ARGS else "player"
    os.makedirs(OUT, exist_ok=True)
    if stage == "player":
        player_stage()
    if stage == "bag":
        bag_stage()
    if stage == "avaturn":
        avaturn_stage()
    if stage == "clothed":
        clothed_stage()
    if stage == "mesh_test":
        lib = load_library()
        arm, mesh, src = build_courier(lib)
        os.makedirs(os.path.join(ROOT, "tmp", "player_test"), exist_ok=True)
        export_rigged([arm, mesh], os.path.join(ROOT, "tmp", "player_test", "courier_noanim.glb"), False)
        qa_rest("test", arm, mesh)


main()
