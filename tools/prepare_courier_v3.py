"""Animation set for the v3 MPFB courier (the new main male character), built in headless Blender.

"C:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background --factory-startup \
    --python tools/prepare_courier_v3.py -- [stage] [options]

stages:
  all      (default) work + final.
  work     retarget / author every clip on a working copy of the character, cache the result
           (source_assets/character_mpfb/anim_cache/courier_v3_work.pkl).
  final    from the cache: actions on the untouched export rig (MPFB names, A-pose rest and bind),
           courier_v3_animated.blend, export/courier_v3_animated.glb, the clips JSON, a copy of the
           master .blend with the actions, and the QA contact sheets.
options:
  --clips=A,B      QA sheets for these clips only (game names).
  --no-qa          skip the contact sheets.
  --qa-only        final stage: contact sheets only (no files written besides the PNGs).

How it works
  * The library motion (assets/animations/ual, CC0) and the Mixamo "Jog Forward" are transferred
    with tools/prepare_player.py's retargeter (world-space rotation deltas from rests that point
    the same way; hip height scaled by the leg-length ratio). The working copy of the character
    has its bones renamed to the SkeletonProfileHumanoid names and its rest posed to the library
    rest (segment directions; the feet keep their own flat orientation). prepare_player.py's
    Clips / Limbs (two-bone IK) and tools/courier_bag.py's BagWork author the rest of the clips.
  * match_rest only rotates bones, so every bone's world matrix is the same on the working copy
    and on the original rig. The final stage writes each frame's world matrices back as local
    rotations of the untouched export rig (A-pose rest, MPFB game_engine names), so the GLB has
    exactly the validated courier_v3 skeleton and skin.
  * Conventions: Blender courier space faces -Y (Godot +Z after glTF export, the humanoid
    retarget convention), +X = the courier's left, metres, feet on z 0. Bag / package / phone
    tracks are given in the "Courier root" frame of assets/player/clips.json (Godot, root facing
    -Z with the model turned PI): p_g = (-x, z, y).
"""
import bpy, bmesh, sys, os, math, json, re, time, pickle
import numpy as np
from mathutils import Vector, Matrix, Quaternion

_HERE = os.path.dirname(os.path.abspath(__file__))
_PP = os.path.join(_HERE, "prepare_player.py")
_SRC = open(_PP, encoding="utf-8").read()
_SRC = _SRC[:_SRC.rindex("\nmain()")]
exec(compile(_SRC, _PP, "exec"), globals())      # Rig, Limbs, Clips, load_library, match_rest helpers ...


def log(*a):
    print("[courier_v3]", *a, flush=True)


CHAR = os.path.join(ROOT, "source_assets", "character_mpfb")
EXPORT_COPY = os.path.join(CHAR, "courier_character_v3_export_copy.blend")
MASTER = os.path.join(CHAR, "courier_character_v3_master.blend")
OUT_DIR = os.path.join(CHAR, "export")
OUT_GLB = os.path.join(OUT_DIR, "courier_v3_animated.glb")
OUT_JSON = os.path.join(OUT_DIR, "courier_v3_animated_clips.json")
OUT_BLEND = os.path.join(CHAR, "courier_v3_animated.blend")
OUT_MASTER = os.path.join(CHAR, "courier_character_v3_master_animated.blend")
QA = os.path.join(CHAR, "renders", "anims")
OUT = OUT_DIR
CACHE = os.path.join(CHAR, "anim_cache", "courier_v3_work.pkl")
JOG_FBX = os.path.join(ROOT, "source_assets", "incoming_2026_10_22", "Jog Forward.fbx")
WALK_BLEND = os.path.join(CHAR, "anims_wip", "walk_natural.blend")   # procedural gait (main session's walk_gen.py)
RUN_BLEND = os.path.join(CHAR, "anims_wip", "run_natural.blend")     # procedural Jog / Run / Sprint (same generator)
UAL_CLIPS = ["Idle_Loop", "Jog_Fwd_Loop", "Sprint_Loop", "Jump_Start", "Jump_Loop", "Jump_Land",
             "Interact", "PickUp_Table", "Idle_Talking_Loop", "Driving_Loop", "Sitting_Idle_Loop"]
UAL_NPC_CLIPS = ["Idle_Look_Loop", "Idle_Phone_Loop"]

# --------------------------------------------------------------------------- MPFB game_engine names
MPFB = {"Root": "Root", "Hips": "pelvis", "Spine": "spine_01", "Chest": "spine_02", "UpperChest": "spine_03",
        "Neck": "neck_01", "Head": "head"}
for _side, _s in (("Left", "l"), ("Right", "r")):
    MPFB.update({_side + "Shoulder": "clavicle_" + _s, _side + "UpperArm": "upperarm_" + _s, _side + "LowerArm": "lowerarm_" + _s,
                 _side + "Hand": "hand_" + _s, _side + "UpperLeg": "thigh_" + _s, _side + "LowerLeg": "calf_" + _s,
                 _side + "Foot": "foot_" + _s, _side + "Toes": "ball_" + _s})
    for _f, _m in (("Thumb", "thumb"), ("Index", "index"), ("Middle", "middle"), ("Ring", "ring"), ("Little", "pinky")):
        for _k, _p in enumerate(dict(FINGERS)[_f]):
            MPFB[_side + _f + _p] = "%s_%02d_%s" % (_m, _k + 1, _s)
TO_PROFILE = {v: k for k, v in MPFB.items()}
KEEP_ORIENT = ("LeftFoot", "LeftToes", "RightFoot", "RightToes")   # rest feet stay flat

# game name of an internal clip name
RENAME = {"Jog_Mixamo_Loop": "Jog_Loop", "Jog_Mixamo_Bag_Loop": "Jog_Bag_Loop"}


def game_name(n):
    n = RENAME.get(n, n)
    return n[:-5] if n.endswith("_Loop") else n


def action_name(n):
    return RENAME.get(n, n)


# --------------------------------------------------------------------------- rest matching
def pose_to_dirs(arm, dirs, names=None):
    """Pose the armature (rest -> library segment directions, world space aware), feet keep their
    rest world orientation. Returns world matrices (normalized) of the pose bones."""
    set_action(arm, None)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    Mw = arm.matrix_world.copy()
    R3 = Mw.to_3x3().normalized()
    Ri = R3.inverted()
    pose = arm.pose.bones
    keep = {n: (Mw @ pose[n].matrix).to_quaternion() for n in KEEP_ORIENT if n in pose}
    worst = 0.0
    for a, b in SEGMENTS:
        if a in KEEP_ORIENT or a not in pose or b not in pose or a not in dirs:
            continue
        pb = pose[a]
        ha, hb = Mw @ pb.head, Mw @ pose[b].head
        v = (hb - ha).normalized()
        t = dirs[a]
        worst = max(worst, v.angle(t))
        Rw = v.rotation_difference(t).to_matrix()
        Ra = (Ri @ Rw @ R3).to_4x4()
        head = pb.head.copy()
        pb.matrix = Matrix.Translation(head) @ Ra @ Matrix.Translation(-head) @ pb.matrix
        bpy.context.view_layer.update()
    for n in KEEP_ORIENT:
        if n not in pose:
            continue
        pb = pose[n]
        qa = (Ri.to_quaternion() @ keep[n])
        M = pb.matrix.copy()
        sc = M.to_scale()
        pb.matrix = Matrix.Translation(M.to_translation()) @ qa.to_matrix().to_4x4() @ Matrix.Diagonal((sc.x, sc.y, sc.z, 1))
        bpy.context.view_layer.update()
    out = {}
    for pb in pose:
        if names is None or pb.name in names:
            M = Mw @ pb.matrix
            out[pb.name] = Matrix.Translation(M.to_translation()) @ M.to_3x3().normalized().to_4x4()
    return out, math.degrees(worst)


def match_rest_v3(arm, meshes, dirs):
    """prepare_player.match_rest with flat feet kept: pose to the library directions, bake the
    deformation into the meshes and apply the pose as the new rest."""
    _, worst = pose_to_dirs(arm, dirs)
    for o in meshes:
        mod = next(m for m in o.modifiers if m.type == 'ARMATURE')
        select_only([o])
        bpy.ops.object.modifier_apply(modifier=mod.name)
    select_only([arm])
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in meshes:
        m = o.modifiers.new("Armature", 'ARMATURE')
        m.object = arm
    return worst


# --------------------------------------------------------------------------- sources
def load_jog(dirs):
    """Mixamo Jog Forward: world matrices per frame (profile names) and its reference pose (the
    jog skeleton posed to the library rest directions, same as the courier's working rest)."""
    reset()
    import_any(JOG_FBX)
    jarm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    rename_bones(jarm, [], MIXAMO)
    jact = next(a for a in bpy.data.actions)
    names = [b.name for b in jarm.data.bones if b.name in HUMANOID_SET]
    frames = capture(jarm, jact, names)
    ref, worst = pose_to_dirs(jarm, dirs, names)
    log("jog: %d frames at %.0f fps, reference pose correction %.1f deg" % (len(frames), fps, worst))
    return {"frames": frames, "fps": fps, "ref": ref}


def load_gaits(path, actions):
    """Procedural gaits from the main session's generator (rig 'WalkRig', 30 fps, frames 0..N with
    N == 0, in place, MPFB bone names): {action: world matrices per frame, profile names}."""
    bpy.ops.wm.open_mainfile(filepath=path)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name == "WalkRig")
    if arm.name not in bpy.context.view_layer.objects:          # the file keeps it outside the scene
        bpy.context.scene.collection.objects.link(arm)
    if arm.animation_data:
        for t in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(t)
    names = [b.name for b in arm.data.bones]
    out = {}
    for a in actions:
        act = bpy.data.actions.get(a)
        if act is None:
            log("gait %s missing in %s" % (a, os.path.basename(path)))
            continue
        frames = capture(arm, act, names)
        out[a] = [{TO_PROFILE[n]: m for n, m in fr.items() if n in TO_PROFILE} for fr in frames]
        log("gait %s: %d frames (%s) from %s" % (a, len(frames), tuple(act.frame_range), os.path.basename(path)))
    set_action(arm, None)
    return out


DL = os.path.join(ROOT, "source_assets", "downloads")
UAL3_GLB = os.path.join(DL, "ual_v3_standard", "extracted", "Universal Animation Library[Standard]", "Unreal-Godot", "UAL1_Standard.glb")
UAL2_GLB = os.path.join(DL, "ual2_standard", "extracted", "Universal Animation Library 2[Standard]", "Unreal-Godot", "UAL2_Standard.glb")
EXT_LIBS = [
    (UAL3_GLB, "UAL v3.0 Standard", ["Idle_Loop", "Jump_Start", "Driving_Loop", "Sitting_Enter", "Sitting_Idle_Loop", "Sitting_Exit",
                                     "Sitting_Talking_Loop", "Crouch_Idle_Loop", "Crouch_Fwd_Loop", "Push_Loop", "Roll"]),
    (UAL2_GLB, "UAL2 Standard", ["Idle_TalkingPhone_Loop", "Consume", "Yes", "Idle_No_Loop", "Idle_FoldArms_Loop", "ClimbUp_1m",
                                 "Chest_Open", "OverhandThrow", "LayToIdle", "Hit_Knockback", "Slide_Start", "Slide_Loop", "Slide_Exit"]),
]
EXT_RM = [(UAL3_GLB.replace("UAL1_Standard.glb", "UAL1_Standard_RM.glb"), ["Roll"]),
          (UAL2_GLB.replace("UAL2_Standard.glb", "UAL2_Standard_RM.glb"), ["ClimbUp_1m"])]
UE2PROF = {v: k for k, v in MPFB.items()}
UE2PROF.update({"Head": "Head", "root": "Root"})


def load_ext(dirs):
    """Quaternius UAL v3 / UAL2 (UE-style bone names, CC0): world matrices of the wanted clips
    (profile names) and each file's reference pose (its skeleton posed to the library rest
    directions, like the courier's working rest). Clips are captured before the bones are renamed
    (a bone rename only updates the active action)."""
    out = {"clips": {}, "src": {}}
    for path, label, wanted in EXT_LIBS:
        if not os.path.exists(path):
            log("library missing:", path)
            continue
        reset()
        import_any(path)
        arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        sc = bpy.context.scene
        fps = sc.render.fps / sc.render.fps_base
        names = [b.name for b in arm.data.bones if b.name in UE2PROF]
        acts = {a.name: a for a in bpy.data.actions}
        got = {}
        for c in wanted:
            if c not in acts:
                log("  %s: clip %s missing" % (label, c))
                continue
            got[c] = [{UE2PROF[n]: m for n, m in fr.items()} for fr in capture(arm, acts[c], names)]
        set_action(arm, None)
        for b in list(arm.data.bones):
            if b.name in UE2PROF:
                b.name = UE2PROF[b.name]
        ref, worst = pose_to_dirs(arm, dirs, set(UE2PROF.values()))
        for c, fr in got.items():
            key = c if c not in out["clips"] else label + ":" + c
            out["clips"][key] = fr
            out["src"][key] = (ref, fps, label)
        log("library %s: %d clips at %.0f fps, reference pose correction %.1f deg" % (label, len(got), fps, worst))
    out["root"] = {}
    for path, wanted in EXT_RM:
        if not os.path.exists(path):
            continue
        reset()
        import_any(path)
        arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        acts = {a.name: a for a in bpy.data.actions}
        sc = bpy.context.scene
        for c in wanted:
            if c not in acts:
                continue
            fr = capture(arm, acts[c], ["root"])
            fps = sc.render.fps / sc.render.fps_base
            out["root"][c] = ([f["root"].to_translation() for f in fr], fps)
            log("root motion %s: end offset %s" % (c, tuple(round(v, 3) for v in out["root"][c][0][-1] - out["root"][c][0][0])))
    return out


def repair_unweighted(meshes, arm):
    """Vertices without deform weight (they would stay at rest and spike during animation) take
    the weights of the nearest weighted vertex of the same mesh. In memory only."""
    from mathutils.kdtree import KDTree
    deform = {b.name for b in arm.data.bones if b.use_deform}
    fixed = {}
    for o in meshes:
        gi = {g.index: g.name for g in o.vertex_groups}
        bad, good = [], []
        for v in o.data.vertices:
            s = sum(g.weight for g in v.groups if gi.get(g.group) in deform)
            (bad if s < 0.5 else good).append(v)
        if not bad or not good:
            continue
        kd = KDTree(len(good))
        for i, v in enumerate(good):
            kd.insert(v.co, i)
        kd.balance()
        for v in bad:
            _, j, _ = kd.find(v.co)
            src = good[j]
            for g in list(v.groups):
                o.vertex_groups[g.group].remove([v.index])
            for g in src.groups:
                o.vertex_groups[g.group].add([v.index], g.weight, 'REPLACE')
        fixed[o.name] = len(bad)
    if fixed:
        log("unweighted vertices repaired (nearest weighted neighbour):", fixed)
    return fixed


def load_character(lib):
    """Working copy of the export rig: profile bone names, one joined mesh, library rest."""
    bpy.ops.wm.open_mainfile(filepath=EXPORT_COPY)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    arm = find_rig("Courier")
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("EXP_")]
    for o in list(bpy.data.objects):
        if o is not arm and o not in meshes:
            bpy.data.objects.remove(o)
    set_action(arm, None)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    orig_rest = {TO_PROFILE[b.name]: (arm.matrix_world @ b.matrix_local).copy() for b in arm.data.bones}
    repair_unweighted(meshes, arm)
    flatten([arm] + meshes)
    for b in list(arm.data.bones):
        if b.name in TO_PROFILE:
            b.name = TO_PROFILE[b.name]
    for o in meshes:                         # in case the rename did not reach a vertex group
        for g in o.vertex_groups:
            if g.name in TO_PROFILE:
                g.name = TO_PROFILE[g.name]
    body = next(o for o in meshes if o.name == "EXP_Body")
    select_only(meshes, body)
    bpy.ops.object.join()
    mesh = body
    mesh.name = mesh.data.name = "WorkMesh"
    for md in mesh.modifiers:
        if md.type == 'ARMATURE':
            md.object = arm
    missing = [n for n in HUMANOID if n in arm.data.bones and arm.data.bones[n].use_deform and n != "Root" and n not in mesh.vertex_groups]
    log("working mesh: %d verts, %d tris, groups missing for bones: %s" % (len(mesh.data.vertices), tris([mesh]), missing))
    arm.name = arm.data.name = "Armature"
    corr = match_rest_v3(arm, [mesh], lib["dirs"])
    zmin = float(mesh_np(mesh)[:, 2].min())
    arm.location.z -= zmin
    mesh.location.z -= zmin
    select_only([arm, mesh], arm)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    mesh.parent = arm
    mesh.matrix_parent_inverse = Matrix.Identity(4)
    log("rest matched: largest segment correction %.1f deg, ground shift %.4f" % (corr, zmin))
    V = mesh_np(mesh)
    return arm, mesh, {"orig_rest": orig_rest, "height": float(V[:, 2].max()), "zshift": zmin}


# --------------------------------------------------------------------------- clips on the courier rig
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


class KeyT:
    """Keyed scalar / Vector track, or a callable of t."""

    def __init__(self, v):
        self.fn = v if callable(v) else None
        if self.fn is None:
            import courier_bag
            self.k = courier_bag.Keys(v)

    def at(self, t):
        return self.fn(t) if self.fn else self.k.at(t)


class V3Clips(Clips):
    SOURCES = {}

    def add(self, name, poses, loop, kind, **meta):
        meta.setdefault("source", self.SOURCES.get(name, "authored (tools/prepare_courier_v3.py)"))
        if name.startswith(("Walk", "Carry_Walk")):
            meta["ground"] = 0.012      # the natural walk's swing passes 1.6 cm over the ground
        devs = [self.pelvis_dev(self.W(P)) for P in poses[::max(1, len(poses) // 12)]]
        meta["pelvis_pitch_dev_deg"] = round(sum(devs) / len(devs), 1)
        meta["pelvis_pitch_dev_range_deg"] = [round(min(devs), 1), round(max(devs), 1)]
        pm = [self.posture(self.W(P)) for P in poses[::max(1, len(poses) // 12)]]
        meta["shoulders_over_hips_cm"] = round(100 * sum(x[0] for x in pm) / len(pm), 1)
        meta["head_ahead_cm"] = round(100 * sum(x[1] for x in pm) / len(pm), 1)
        meta["head_pitch_deg"] = round(sum(x[2] for x in pm) / len(pm), 1)
        meta["thoracic_flex_deg"] = round(sum(x[3] for x in pm) / len(pm), 1)
        return Clips.add(self, name, poses, loop, kind, **meta)

    def low_contact(self, P):
        W = self.W(P)
        z = []
        for s in ("Left", "Right"):
            M = W[s + "Foot"]
            z.append(min((M @ self.contacts[s][k]).z for k in ("heel", "ball")))
            z.append((W[s + "Toes"] @ self.contacts[s]["tip"]).z)
        return min(z)

    def set_hips_z(self, P, z):
        W = self.W(P)
        h = W["Hips"].to_translation()
        return hips_world_shift(self.rig, [P], Vector((0, 0, z - h.z)))[0]

    def blend_to(self, seq, target, n):
        """Ease the last n frames of a one-shot clip into a target pose (joint blend, feet
        re-solved to the blended foot transforms), so it ends exactly in that pose."""
        out = list(seq[:-n])
        WT = self.W(target)
        for i, P in enumerate(seq[-n:]):
            u = ease((i + 1) / n)
            WP = self.W(P)
            Q = {}
            for b in P:
                qa, qb = P[b].to_quaternion(), target[b].to_quaternion()
                if qa.dot(qb) < 0:
                    qb = -qb
                Q[b] = Matrix.Translation(P[b].to_translation().lerp(target[b].to_translation(), u)) @ qa.slerp(qb, u).to_matrix().to_4x4()
            W = self.W(Q)
            for s in ("Left", "Right"):
                a = WP[s + "Foot"].to_translation().lerp(WT[s + "Foot"].to_translation(), u)
                q = WP[s + "Foot"].to_quaternion().slerp(WT[s + "Foot"].to_quaternion(), u)
                hp, kn = W[s + "UpperLeg"].to_translation(), W[s + "LowerLeg"].to_translation()
                W = self.limbs.leg(Q, W, s, a, kn - (hp + a) / 2, q)
            out.append(Q)
        return out

    def lift_feet(self, P, clearance):
        """Leg IK: raise each foot whose lowest point is under `clearance` (knee bends, foot keeps
        its orientation), then bend the toes up where the toe tip would still be under the ground."""
        W = self.W(P)
        for s in ("Left", "Right"):
            M = W[s + "Foot"]
            low = min([(M @ self.contacts[s][k]).z for k in ("heel", "ball")] + [(W[s + "Toes"] @ self.contacts[s]["tip"]).z if clearance > 0 else 1.0])
            if low < clearance:
                hp, kn, an = (W[s + n].to_translation() for n in ("UpperLeg", "LowerLeg", "Foot"))
                pole = kn - (hp + an) / 2
                if pole.length < 1e-4:
                    pole = FWD
                W = self.limbs.leg(P, W, s, an + UP * (clearance - low), pole.normalized() + FWD * 0.3, self.rig.rot(W, s + "Foot"))
        return self.fix_toes([P])[0][0]

    def jumps_in_place(self, js, jl, land):
        """Jump clips without vertical travel (the game's CharacterBody moves the body):
        Jump_Start = an anticipation from the idle into the library crouch, then the library
        extension with the pelvis capped at standing + 3 cm and the feet kept on / above the ground
        until toe-off, then tucked to 4 cm clearance; Jump_Loop = the same pelvis height with the legs
        tucked; Jump_Land = held at that height while the clearance eases to 0 at touch-down, then the
        library landing compression (feet clamped to the ground)."""
        hz = lambda P: self.W(P)["Hips"].to_translation().z
        js = [self.set_hips_z(P, hz(P) - self.low_contact(js[0])) for P in js]
        land = [self.set_hips_z(P, hz(P) - self.low_contact(land[-1])) for P in land]
        idle = self.restance_idle0
        H = self.W(idle)["Hips"].to_translation().z + 0.03
        CL = 0.04
        to = next(k for k, P in enumerate(js) if k > 2 and self.low_contact(P) > 0.03)
        td = next(k for k, P in enumerate(land) if self.low_contact(P) < 0.015)
        # anticipation: idle -> library crouch (joint blend, feet re-solved to the blended feet)
        A, B = idle, js[0]
        WA, WB = self.W(A), self.W(B)
        pre = []
        NP = 8
        for k in range(NP):
            u = ease(k / NP)
            P = {}
            for n in A:
                qa, qb = A[n].to_quaternion(), B[n].to_quaternion()
                if qa.dot(qb) < 0:
                    qb = -qb
                P[n] = Matrix.Translation(A[n].to_translation().lerp(B[n].to_translation(), u)) @ qa.slerp(qb, u).to_matrix().to_4x4()
            W = self.W(P)
            for s in ("Left", "Right"):
                a = WA[s + "Foot"].to_translation().lerp(WB[s + "Foot"].to_translation(), u)
                q = WA[s + "Foot"].to_quaternion().slerp(WB[s + "Foot"].to_quaternion(), u)
                hp, kn = W[s + "UpperLeg"].to_translation(), W[s + "LowerLeg"].to_translation()
                W = self.limbs.leg(P, W, s, a, kn - (hp + a) / 2, q)
            pre.append(P)
        out_s = list(pre)
        for k, P in enumerate(js):
            P = self.set_hips_z(P, min(hz(P), H))
            c = 0.0 if k < to else CL * ease((k - to + 1) / 4.0)
            out_s.append(self.lift_feet(P, c))
        H = hz(out_s[-1])                       # air height = where Jump_Start ends (exact seam)
        zl = [hz(P) for P in jl[:-1]]
        mz = sum(zl) / len(zl)
        out_l = [self.lift_feet(self.set_hips_z(P, H + max(0.0, (hz(P) - mz) * 0.25)), CL) for P in jl]
        out_l[-1] = dict(out_l[0])
        out_d = []
        k0 = max(0, td - 4)
        for k, P in enumerate(land):
            if k >= td:
                c = CL * (1 - ease((k - td) / 3.0))      # the loop's tuck eases out into the touch-down
                out_d.append(self.lift_feet(self.set_hips_z(P, min(hz(P), H)), c))
            else:
                u = ease((k - k0 + 1) / (td - k0 + 1)) if k >= k0 else 0.0
                out_d.append(self.lift_feet(self.set_hips_z(P, H + (min(hz(P), H) - H) * u), CL * (1 - u)))
        out_d = self.blend_to(out_d, idle, 12)
        to += NP
        for name, seq in (("Jump_Start", out_s), ("Jump_Loop", out_l), ("Jump_Land", out_d)):
            lows = [self.low_contact(P) for P in seq]
            log("  %s in place: lowest foot point %.3f, first frame %.3f, last frame %.3f; pelvis %.3f..%.3f"
                % (name, min(lows), lows[0], lows[-1], min(hz(P) for P in seq), max(hz(P) for P in seq)))
        air = H
        log("  jumps: take-off frame %d, touch-down frame %d, air pelvis height %.3f" % (to, td, air))
        return out_s, out_l, out_d, {"takeoff": to, "touchdown": td, "air": air}

    PHONE_CURL =((10, 82, 34), (8, 86, 34), (8, 88, 32), (10, 86, 30), (22, 12, 8))

    def phone_hand(self, poses, side="Right"):
        """The library phone idle closes the phone hand into a fist: open it into a phone grip
        (palm under the phone, fingers round its far edge, thumb over the screen)."""
        out = []
        for P in poses:
            P = {k: m.copy() for k, m in P.items()}
            for f, angs in zip(("Index", "Middle", "Ring", "Little", "Thumb"), self.PHONE_CURL):
                self.set_finger(P, side, f, angs)
            out.append(P)
        return out

    def relax_fingers(self, poses):
        """Light relaxed curl (same as the idle's hanging hands) where the clip leaves fingers straight."""
        out = []
        for P in poses:
            P = {k: m.copy() for k, m in P.items()}
            for side in ("Left", "Right"):
                if all(P[side + "Index" + p].to_quaternion().angle < 0.02 for p in ("Proximal", "Intermediate", "Distal")):
                    for f, angs in zip(("Index", "Middle", "Ring", "Little", "Thumb"),
                                       ((14, 22, 12), (16, 24, 14), (18, 26, 14), (20, 28, 14), (10, 8, 4))):
                        self.set_finger(P, side, f, angs)
            out.append(P)
        return out

    def fix_toes(self, poses):
        """Bend the toes up where the toe tip would dip below the ground (ball above it)."""
        rig, n = self.rig, 0
        out = []
        for P in poses:
            P = {k: m.copy() for k, m in P.items()}
            W = rig.fk(P)
            for side in ("Left", "Right"):
                B = W[side + "Toes"].to_translation()
                Tp = W[side + "Toes"] @ self.contacts[side]["tip"]
                if Tp.z < 0.0 and B.z >= -0.002:
                    L = (Tp - B).length
                    e0 = math.asin(max(-1.0, min(1.0, (Tp.z - B.z) / L)))
                    e1 = math.asin(max(-1.0, min(1.0, (0.001 - B.z) / L)))
                    ax = (Tp - B).cross(UP)
                    if ax.length > 1e-6:
                        W = rotate_bone_world(rig, P, W, side + "Toes", Quaternion(ax.normalized(), e1 - e0))
                        n += 1
            out.append(P)
        return out, n

    def library_clips(self):
        R = {}
        S = self.SOURCES
        idle, z = self.ground_shift(self.ual("Idle_Loop"))
        idle, rr = self.straighten(idle, 0.03, 4.0)
        log("  idle hips raised %.3f..%.3f" % rr)
        S["Idle_Loop"] = "UAL Idle_Loop breathing / sway (CC0), re-stanced: feet under the hips, arms relaxed"
        R["Idle"] = self.add("Idle_Loop", self.restance(idle), True, "standing",
                             note="relaxed standing idle: feet under the hips, arms hanging beside the thighs, the library idle's breathing and sway")
        self.restance_idle0 = R["Idle"][0]
        for src, name, pack, arms in (("Idle_Talking_Loop", "Idle_Talk_Loop", "UAL", ("keep", "keep")),
                                      ("Idle_Look_Loop", "Idle_Look_Loop", "UAL NPC", ("relaxed", "relaxed")),
                                      ("Idle_Phone_Loop", "Phone_Use_Loop", "UAL NPC", ("keep", "keep"))):
            p, _ = self.ground_shift(self.ual(src))
            p, _ = self.straighten(p, 0.03, 4.0)
            p = self.restance(p, arms=arms)
            if name == "Phone_Use_Loop":
                p = self.phone_hand(p)
            S[name] = "%s %s (Quaternius Universal Animation Library, CC0), re-stanced to the courier's idle stance" % (pack, src)
            R[name] = self.add(name, p, True, "standing")
        wf = self.src["walk"]
        walk, nt = self.fix_toes([copy_world_pose(self.rig, fr)[0] for fr in wf])
        log("  natural walk: toes lifted on %d foot-frames" % nt)
        walk = self.relax_fingers(walk)
        wf = [{n: m for n, m in self.rig.fk(P).items()} for P in walk]
        S["Walk_Loop"] = "procedural natural gait (anims_wip/walk_natural.blend, walk_gen.py: heel strike / roll / toe-off, analytic leg IK, pelvis bob / sway / rotation / list, spine counter-rotation, arm swing)"
        R["Walk"] = self.add("Walk_Loop", walk, True, "locomotion",
                             note="natural walk, 112 steps/min: heel strike, roll, toe-off; pelvis bob, sway and rotation, spine counter-rotation, level head, arms swinging opposite the legs")
        # walking backwards ~ the forward gait reversed in time (ball-first landing, heel lowers,
        # toes rise last), slowed to 1.33 s per cycle (backward walking is slower)
        rev = list(reversed(wf))
        N = 40
        back, _ = self.fix_toes([copy_world_pose(self.rig, sample_frames(rev, k * (len(rev) - 1) / N))[0] for k in range(N + 1)])
        S["Walk_Back_Loop"] = "the natural walk reversed in time and slowed to 0.8x (backward gait is close to a time-reversed forward gait)"
        self.add("Walk_Back_Loop", back, True, "locomotion", axis=Vector((0, -1, 0)),
                 note="walking backwards: the natural walk reversed in time and slowed (ball-first landing, heel lowers, toes lift last); the body moves backwards")
        runs = self.src.get("runs") or {}
        if runs:
            for a, note in (("Jog_Loop", "natural jog"), ("Run_Loop", "natural run"), ("Sprint_Loop", "natural sprint")):
                if a not in runs:
                    continue
                p, nt = self.fix_toes([copy_world_pose(self.rig, fr)[0] for fr in runs[a]])
                S[a] = "procedural gait (anims_wip/run_natural.blend, same generator as the walk)"
                self.add(a, p, True, "locomotion", ground=0.035, note=note)
        else:
            run, _, _ = self.clean_feet(self.ual("Jog_Fwd_Loop"), False)
            run, _ = self.lock_feet(run, ground=0.035)
            S["Run_Loop"] = "UAL Jog_Fwd_Loop (CC0), feet locked with IK"
            self.add("Run_Loop", run, True, "locomotion", ground=0.035, note="library Jog_Fwd: a fast run")
            spr, _, _ = self.clean_feet(self.ual("Sprint_Loop"), False)
            spr, _ = self.lock_feet(spr, ground=0.035)
            S["Sprint_Loop"] = "UAL Sprint_Loop (CC0), feet locked with IK"
            self.add("Sprint_Loop", spr, True, "locomotion", ground=0.035)
        js, zj = self.ground_shift(self.unbias(self.ual("Jump_Start"), "v1"))
        jl = hips_world_shift(self.rig, self.unbias(self.ual("Jump_Loop"), "v1"), Vector((0, 0, -zj)))
        land, zl = self.ground_shift(self.unbias(self.ual("Jump_Land"), "v1"))
        js, jl, land, info = self.jumps_in_place(js, jl, land)
        S["Jump_Start"] = "UAL Jump_Start (CC0), vertical travel removed after take-off"
        R["Jump_Start"] = self.add("Jump_Start", js, False, "jump", takeoff_frame=info["takeoff"],
                                   note="anticipation crouch, extension and toe-off (frame %d); after take-off the pelvis stays at air height (%.2f m) and the legs tuck: the CharacterBody provides the vertical motion" % (info["takeoff"], info["air"]))
        S["Jump_Loop"] = "UAL Jump_Loop (CC0), pelvis held at the air height"
        self.add("Jump_Loop", jl, True, "jump", note="in-air loop, legs tucked, pelvis at the same height as the end of Jump_Start / start of Jump_Land")
        R["Jump_Land"] = land
        S["Jump_Land"] = "UAL Jump_Land (CC0), vertical travel removed before touch-down"
        self.add("Jump_Land", land, False, "jump", touchdown_frame=info["touchdown"],
                 note="in the air at the Jump_Loop pelvis height, touch-down at frame %d, landing compression, recover to standing" % info["touchdown"])
        for src, name, arms in (("Interact", "Interact", ("keep", "relaxed")), ("PickUp_Table", "PickUp_Table", ("keep", "keep"))):
            p, _ = self.ground_shift(self.ual(src))
            p, _ = self.straighten(p, 0.03, 4.0, loop=False)
            p = self.restance(p, loop=False, arms=arms, sway=1.0)
            S[name] = "UAL %s (CC0), re-stanced to the courier's idle stance" % src
            R[name] = self.add(name, p, False, "action")
        return R

    def mixamo_jog(self):
        """Mixamo Jog Forward retargeted (rotation deltas from its reference pose), root motion
        removed, feet cleaned and locked."""
        J = self.src["jog"]
        jog, fps, ref = J["frames"], J["fps"], J["ref"]
        P = len(jog) - 1
        h0, h1 = jog[0]["Hips"].to_translation(), jog[P]["Hips"].to_translation()
        delta = Vector((h1.x - h0.x, h1.y - h0.y, 0))
        log("mixamo jog: travel %s over %d frames (%.3f m/s native)" % (tuple(round(c, 3) for c in delta), P, delta.length / (P / fps)))
        flip = delta.y > 0          # the courier faces -Y: a jog travelling +Y faces the other way
        Rz = Matrix.Rotation(math.pi, 4, 'Z') if flip else Matrix.Identity(4)
        mean = Vector()
        for i in range(P):
            h = jog[i]["Hips"].to_translation() - delta * (i / P)
            mean += Vector((h.x, h.y, 0)) / P
        clean = []
        for i, fr in enumerate(jog):
            off = -(delta * (i / P)) - mean
            clean.append({n: Rz @ (Matrix.Translation(off) @ m) for n, m in fr.items()})
        refr = {n: Rz @ m for n, m in ref.items()}
        r = self.rig.rest
        lr = refr
        leg_scale = ((r["LeftUpperLeg"].to_translation().z + r["RightUpperLeg"].to_translation().z)
                     / (lr["LeftUpperLeg"].to_translation().z + lr["RightUpperLeg"].to_translation().z))
        hip_scale = r["Hips"].to_translation().z / lr["Hips"].to_translation().z
        N = int(round(P / fps * FPS))
        poses = []
        for k in range(N + 1):
            fr = sample_frames(clean, k * P / N)
            poses.append(transfer_pose(self.rig, fr, refr, hip_scale, leg_scale=leg_scale)[0])
        poses, z, _ = self.clean_feet(poses, False)
        poses, _ = self.lock_feet(poses, ground=0.035)
        self.SOURCES["Jog_Mixamo_Loop"] = "Mixamo Jog Forward (source_assets/incoming_2026_10_22/Jog Forward.fbx), retargeted, root motion removed"
        self.add("Jog_Mixamo_Loop", poses, True, "locomotion", ground=0.035, root_motion_removed_m=round(delta.length, 3),
                 cycle_time_scale=round((N / FPS) / (P / fps), 4), leg_scale=round(leg_scale, 4))
        return poses

    # ------------------------------------------------------------------ stance
    PELVIS_TARGET = 3.0      # neutral standing: pelvis pitch = rest + 3 deg

    def pelvis_pitch(self, M):
        d = M.to_3x3() @ Vector((0, 1, 0))
        return math.degrees(math.atan2(-d.y, d.z))

    def pelvis_dev(self, W):
        """Pelvis forward (anterior) tilt relative to the character's original (MPFB) rest, degrees."""
        ref = self.orig_rest["Hips"] if getattr(self, "orig_rest", None) else self.rig.rest["Hips"]
        return self.pelvis_pitch(W["Hips"]) - self.pelvis_pitch(ref)

    def neutral_pelvis(self, P, dev=None, keep_feet=False):
        """Undo an anterior pelvic tilt (sway-back): the pelvis rotates about its head back to
        rest + PELVIS_TARGET (or by `dev` degrees), the lumbar takes the compensation so the chest
        keeps its world orientation (Spine 60 %, Chest 40 %); optionally the feet are re-pinned."""
        rig = self.rig
        W = self.W(P)
        d = (self.pelvis_dev(W) - self.PELVIS_TARGET) if dev is None else dev
        if abs(d) < 0.2:
            return 0.0
        feet = {s: (W[s + "Foot"].to_translation(), W[s + "Foot"].to_quaternion(), W[s + "LowerLeg"].to_translation()) for s in ("Left", "Right")}
        uc = W["UpperChest"].to_quaternion()
        ax = Quaternion(UP, self.yaw_of(W, "Hips")) @ LEFT
        W = rotate_bone_world(rig, P, W, "Hips", Quaternion(ax, math.radians(-d)))
        W = rotate_bone_world(rig, P, W, "Spine", Quaternion(ax, math.radians(d * 0.6)))
        W = rotate_bone_world(rig, P, W, "Chest", Quaternion(ax, math.radians(d * 0.4)))
        res = W["UpperChest"].to_quaternion().rotation_difference(uc)
        if res.angle > 1e-4:
            W = rotate_bone_world(rig, P, W, "UpperChest", res)
        if keep_feet:
            for s in ("Left", "Right"):
                a, q, kn = feet[s]
                hp = W[s + "UpperLeg"].to_translation()
                W = self.limbs.leg(P, W, s, a, kn - (hp + a) / 2, q)
        return d

    # ------------------------------------------------------------------ upright posture (no hunch)
    SH_TARGET, HEAD_TARGET = 0.010, 0.035      # shoulders 1 cm ahead of the hips, head 3.5 cm ahead of the shoulders

    def body_frame(self, W):
        yaw = self.yaw_of(W, "Hips")
        return Quaternion(UP, yaw) @ FWD, Quaternion(UP, yaw) @ LEFT

    def posture(self, W):
        """(shoulders ahead of the hips, head-bone head ahead of the shoulders) in metres along the
        body's forward direction, head pitch vs rest (deg, + = face tipped down), thoracic flexion
        vs rest (deg)."""
        f, _ = self.body_frame(W)
        sh = (W["LeftUpperArm"].to_translation() + W["RightUpperArm"].to_translation()) / 2
        hp = (W["LeftUpperLeg"].to_translation() + W["RightUpperLeg"].to_translation()) / 2
        hd = W["Head"].to_translation()
        d = W["Head"].to_3x3() @ Vector((0, 1, 0))
        r = self.orig_rest["Head"].to_3x3() @ Vector((0, 1, 0)) if getattr(self, "orig_rest", None) else self.rig.rest["Head"].to_3x3() @ Vector((0, 1, 0))
        pitch = lambda v: math.degrees(math.atan2(v.dot(f), v.z))
        t = W["UpperChest"].to_3x3() @ Vector((0, 1, 0))
        tr = (self.orig_rest if getattr(self, "orig_rest", None) else self.rig.rest)["UpperChest"].to_3x3() @ Vector((0, 1, 0))
        return (sh - hp).dot(f), (hd - sh).dot(f), pitch(d) - pitch(r), pitch(t) - pitch(tr)

    CHAIN = ("Spine", "Chest", "UpperChest", "Neck", "Head")

    def bone_pitch(self, W, n, M=None):
        f, _ = self.body_frame(W)
        d = (M if M is not None else W[n]).to_3x3() @ Vector((0, 1, 0))
        return math.degrees(math.atan2(d.dot(f), d.z))

    def walk_template(self):
        """The upright chain of the approved natural walk (cycle means): spine / neck / head pitch
        in the body frame and the clavicles' local rotation."""
        if not hasattr(self, "_wt"):
            fr = self.src["walk"][:-1]
            pit = {b: sum(self.bone_pitch(W, b) for W in fr) / len(fr) for b in self.CHAIN}
            cl = {}
            for s_ in ("Left", "Right"):
                n = s_ + "Shoulder"
                qs = []
                for W in fr:
                    p = self.rig.parent[n]
                    q = ((W[p] @ self.rig.rel[n]).inverted() @ W[n]).to_quaternion()
                    if qs and qs[0].dot(q) < 0:
                        q = -q
                    qs.append(q)
                m = Quaternion((sum(q.w for q in qs), sum(q.x for q in qs), sum(q.y for q in qs), sum(q.z for q in qs))).normalized()
                cl[n] = m
            self._wt = (pit, cl)
            log("  posture template (walk means): " + ", ".join("%s %.1f" % (k, v) for k, v in pit.items()))
        return self._wt

    def neutral_spine(self, poses, weights=None):
        """Clip-level upright posture (no hunch, no arch): the clavicles take the approved walk's
        rotation, each spine / neck / head bone's mean pitch is set to the walk's (the clip's own
        motion around its mean is kept: breathing, nods, sway). weights: per-frame blend."""
        rig = self.rig
        n = len(poses)
        w = weights or [1.0] * n
        P = [{k: m.copy() for k, m in Q.items()} for Q in poses]
        pit, cl = self.walk_template()
        for Q, wi in zip(P, w):
            for nm, q in cl.items():
                q0 = Q[nm].to_quaternion()
                if q0.dot(q) < 0:
                    q = -q
                Q[nm] = q0.slerp(q, wi).to_matrix().to_4x4()

        def rot_all(bone, deg_list):
            for Q, dg in zip(P, deg_list):
                if abs(dg) < 1e-3:
                    continue
                W = rig.fk(Q)
                _, ax = self.body_frame(W)
                rotate_bone_world(rig, Q, W, bone, Quaternion(ax, math.radians(dg)))

        for bone in self.CHAIN:
            cur = [self.bone_pitch(rig.fk(Q), bone) for Q in P]
            dm = pit[bone] - sum(cur) / n
            rot_all(bone, [dm * wi for wi in w])
        # standing: without the walking lean (shoulders ~2 cm ahead of the hips), head level
        rot_all("Spine", [-self.STAND_BACK * wi for wi in w])
        rot_all("Head", [self.STAND_BACK * wi for wi in w])
        return P

    STAND_BACK = 3.0

    def bias_of(self, key):
        """A library's anterior pelvic-tilt bias: its standing idle's pelvis pitch above neutral."""
        self._bias = getattr(self, "_bias", {})
        if key not in self._bias:
            if key == "v1":
                P = self.ual("Idle_Loop")[0]
            else:
                E = self.src["ext"]
                ref = next((c for c in ("Idle_Loop", "Idle_FoldArms_Loop") if c in E["clips"] and E["src"][c][2] == key), None)
                P = self.ext(ref)[0] if ref else None
            self._bias[key] = (self.pelvis_dev(self.W(P)) - self.PELVIS_TARGET) if P else 0.0
            log("  pelvis bias of %s: %+.1f deg (removed from its clips)" % (key, self._bias[key]))
        return self._bias[key]

    def unbias(self, poses, key):
        d = self.bias_of(key)
        out = []
        for P in poses:
            P = {k: m.copy() for k, m in P.items()}
            self.neutral_pelvis(P, dev=d, keep_feet=True)
            out.append(P)
        return out

    def yaw_of(self, W, n):
        D = W[n].to_quaternion() @ self.rig.rest_rot[n].inverted()
        f = D @ FWD
        return math.atan2(f.x, -f.y)

    def hand_rot(self, side, d, n):
        h0, p0, L = self.hand_frame(side)
        d = Vector(d).normalized()
        n = Vector(n)
        n = (n - d * n.dot(d)).normalized()
        F0 = Matrix((h0, p0, h0.cross(p0))).transposed()
        F1 = Matrix((d, n, d.cross(n))).transposed()
        return (F1 @ F0.inverted()).to_quaternion() @ self.rig.rest_rot[side + "Hand"]

    def restance(self, poses, loop=True, arms=("relaxed", "relaxed"), width=0.115, stagger=0.035, toe_out=7.0, sway=0.6, drop=0.012, pelvis_fix=True):
        """Library standing clip -> the courier's stance: feet under the hips (side by side, left 3.5
        cm ahead, toes out 7 deg), the clip's mean hip yaw and chest yaw turned back to the front,
        its hip sway kept at `sway`, legs re-solved; arms 'keep' (library motion) or 'relaxed'
        (hanging beside the thighs, carried by the chest so breathing / sway still move them)."""
        rig = self.rig
        n = len(poses) - 1 if loop else len(poses)

        def cmean(a):
            return math.atan2(sum(math.sin(x) for x in a), sum(math.cos(x) for x in a))
        Ws = [self.W(P) for P in poses]
        mh = cmean([self.yaw_of(W, "Hips") for W in Ws[:n]])
        mean = sum((W["Hips"].to_translation() for W in Ws[:n]), Vector()) / n
        rest = rig.rest
        hz0 = rest["Hips"].to_translation().z - drop
        feet = {}
        for side, sx in (("Left", 1), ("Right", -1)):
            a = rest[side + "Foot"].to_translation()
            q = Quaternion(UP, math.radians(sx * toe_out)) @ rig.rest_rot[side + "Foot"]
            feet[side] = (Vector((sx * width, a.y + (-stagger / 2 if side == "Left" else stagger / 2), a.z)), q)
        hy0 = rest["Hips"].to_translation().y - 0.005
        stage = []
        for P in poses:
            P = {b: m.copy() for b, m in P.items()}
            W = self.W(P)
            h = W["Hips"].to_translation()
            d = (h - mean) * sway
            pos = Vector((d.x, hy0 + d.y, hz0 + (h.z - mean.z)))
            q = Quaternion(UP, -mh) @ W["Hips"].to_quaternion()
            rig.set_world(P, W, "Hips", Matrix.Translation(pos) @ q.to_matrix().to_4x4())
            if pelvis_fix:
                self.neutral_pelvis(P)
            stage.append(P)
        if pelvis_fix:
            stage = self.neutral_spine(stage)
            if loop:
                stage[-1] = dict(stage[0])
        Ws = [self.W(P) for P in stage]
        mc = cmean([self.yaw_of(W, "UpperChest") for W in Ws[:n]])
        out = []
        local = {}
        for k, P in enumerate(stage):
            W = self.W(P)
            for nb, share in (("Spine", 0.4), ("Chest", 0.3), ("UpperChest", 0.3)):
                W = rotate_bone_world(rig, P, W, nb, Quaternion(UP, -mc * share))
            for side, sx in (("Left", 1), ("Right", -1)):
                a, q = feet[side]
                W = self.limbs.leg(P, W, side, a, FWD + LEFT * (0.15 * sx), q)
            for side, sx, mode in (("Left", 1, arms[0]), ("Right", -1, arms[1])):
                if mode != "relaxed":
                    continue
                P[side + "Shoulder"] = self.walk_template()[1][side + "Shoulder"].to_matrix().to_4x4() if pelvis_fix else Matrix.Identity(4)
                W = self.W(P)
                UC = W["UpperChest"]
                if side not in local:
                    S = W[side + "UpperArm"].to_translation()
                    l1, l2 = self.limbs.len[side + "UpperArm"]
                    wrist = S + Vector((sx * 0.045, -0.035, -(l1 + l2) * 0.955))
                    qh = self.hand_rot(side, Vector((sx * 0.06, -0.12, -1.0)), Vector((-sx, 0.12, 0.0)))
                    local[side] = UC.inverted() @ (Matrix.Translation(wrist) @ qh.to_matrix().to_4x4())
                M = UC @ local[side]
                sw = 0.008 * math.sin(2 * math.pi * k / max(n, 1)) if loop else 0.0
                W = self.limbs.arm(P, W, side, M.to_translation() + FWD * sw, Vector((sx * 0.3, 1.0, -0.1)), M.to_quaternion())
                for f, angs in zip(("Index", "Middle", "Ring", "Little", "Thumb"),
                                   ((14, 22, 12), (16, 24, 14), (18, 26, 14), (20, 28, 14), (10, 8, 4))):
                    self.set_finger(P, side, f, angs)
            out.append(P)
        if loop:
            out[-1] = dict(out[0])
        log("  restance: hips yaw %.1f, chest yaw %.1f deg removed" % (math.degrees(mh), math.degrees(mc)))
        return out

    # ------------------------------------------------------------------ helpers
    def transition(self, name, A, B, T, kind="action", feet_from=None, **meta):
        """Joint-space blend A -> B (local rotations slerped, ease in/out), feet re-solved to the
        blended foot transforms (the poses share their stance)."""
        N = int(round(T * FPS))
        WA, WB = self.W(A), self.W(B)
        out = []
        for k in range(N + 1):
            u = ease(k / N)
            P = {}
            for n in A:
                qa, qb = A[n].to_quaternion(), B[n].to_quaternion()
                if qa.dot(qb) < 0:
                    qb = -qb
                P[n] = Matrix.Translation(A[n].to_translation().lerp(B[n].to_translation(), u)) @ qa.slerp(qb, u).to_matrix().to_4x4()
            W = self.W(P)
            for s in ("Left", "Right"):
                a = WA[s + "Foot"].to_translation().lerp(WB[s + "Foot"].to_translation(), u)
                q = WA[s + "Foot"].to_quaternion().slerp(WB[s + "Foot"].to_quaternion(), u)
                hp, kn = W[s + "UpperLeg"].to_translation(), W[s + "LowerLeg"].to_translation()
                W = self.limbs.leg(P, W, s, a, kn - (hp + a) / 2, q)
            out.append(P)
        return self.add(name, out, False, kind, **meta)

    def set_finger(self, P, side, f, angs, spread=0.0):
        R = self.rig.rest
        _, p0, _ = self.hand_frame(side)
        parts = dict(FINGERS)[f]
        for i, (part, a) in enumerate(zip(parts, angs)):
            n_ = side + f + part
            if n_ not in R:
                continue
            nxt = side + f + parts[i + 1] if i + 1 < len(parts) else None
            fd = ((R[nxt].to_translation() if nxt else R[n_] @ Vector((0, 0.03, 0))) - R[n_].to_translation()).normalized()
            ax = fd.cross(p0).normalized()
            q = Quaternion(self.rig.rest_rot[n_].inverted() @ ax, math.radians(a))
            if i == 0 and spread:
                q = Quaternion(self.rig.rest_rot[n_].inverted() @ p0, math.radians(spread)) @ q
            P[n_] = q.to_matrix().to_4x4()

    # ------------------------------------------------------------------ UAL v3 / UAL2 clips
    def ext(self, clip):
        E = self.src["ext"]
        frames = E["clips"][clip]
        ref, fps, _ = E["src"][clip]
        r = self.rig.rest
        leg_scale = ((r["LeftUpperLeg"].to_translation().z + r["RightUpperLeg"].to_translation().z)
                     / (ref["LeftUpperLeg"].to_translation().z + ref["RightUpperLeg"].to_translation().z))
        hip_scale = r["Hips"].to_translation().z / ref["Hips"].to_translation().z
        idx, N = resample(frames, fps, True)
        return [transfer_pose(self.rig, sample_frames(frames, t), ref, hip_scale, leg_scale=leg_scale)[0] for t in idx]

    def floor_at(self, poses, mode):
        if mode == "min":
            return self.ground_shift(poses)[0]
        z = self.low_contact(poses[0] if mode == "first" else poses[-1])
        return hips_world_shift(self.rig, poses, Vector((0, 0, -z)))

    def seat_height(self, P):
        """Lowest point of the buttocks / thighs under the pelvis in a sitting pose (the chair seat)."""
        W = self.W(P)
        h = W["Hips"].to_translation()
        apply_pose(self.arm, P)
        co = evaluated_np([self.mesh])[0]
        sel = (np.abs(co[:, 0] - h.x) < 0.2) & (co[:, 1] > h.y - 0.15) & (co[:, 1] < h.y + 0.2) & (co[:, 2] < h.z)
        return float(co[sel, 2].min()) if sel.any() else None

    def fastest_hand_frame(self, poses):
        best, bf, side = 0.0, 0, "Right"
        prev = None
        for k, P in enumerate(poses):
            W = self.W(P)
            cur = {s: W[s + "Hand"].to_translation() for s in ("Left", "Right")}
            if prev:
                for s in cur:
                    v = (cur[s] - prev[s]).length * FPS
                    if v > best:
                        best, bf, side = v, k, s
            prev = cur
        return bf, side, best

    def ext_clips(self, R):
        E = self.src.get("ext") or {}
        if not E.get("clips"):
            return
        S = self.SOURCES
        self.phone_side = getattr(self, "phone_side", {})
        have = E["clips"]

        def lab(c, extra=""):
            return "Quaternius %s %s (CC0)%s" % (E["src"][c][2], c, extra)

        def put(src, name, loop, kind, floor="min", restance=None, **meta):
            if src not in have:
                return None
            p = self.ext(src)
            if not restance:
                p = self.unbias(p, E["src"][src][2])     # the library's constant anterior pelvic tilt
            p = self.floor_at(p, floor)
            if name in ("Sit_Idle_Loop", "Sit_Talk_Loop"):
                p = self.neutral_spine(p)
                p[-1] = dict(p[0])
            elif name in ("Sit_Enter", "Sit_Exit"):
                n_ = len(p) - 1
                p = self.neutral_spine(p, [ease(k / n_) if name == "Sit_Enter" else 1 - ease(k / n_) for k in range(n_ + 1)])
            if restance:
                p = self.restance(p, loop=loop, arms=restance, sway=0.6 if loop else 1.0)
            S[name] = lab(src, ", re-stanced to the courier's idle stance" if restance else "")
            return self.add(name, p, loop, kind, **meta)

        # library v3 vs v1: same idle / jump content? (they replace nothing if they match)
        for c, old in (("Idle_Loop", "Idle_Loop"), ("Jump_Start", "Jump_Start")):
            if c in have:
                a, b = self.ual(old), self.ext(c)
                n = min(len(a), len(b))
                d = max(a[k][bn].to_quaternion().rotation_difference(b[k][bn].to_quaternion()).angle
                        for k in range(n) for bn in a[k] if bn in b[k] and bn != "Root")
                log("  UAL v3 %s vs v1: %d / %d frames, largest local rotation difference %.2f deg" % (c, len(b), len(a), math.degrees(d)))
        # standing gestures (feet planted, re-stanced)
        put("Idle_TalkingPhone_Loop", "Phone_Call_Loop", True, "standing", restance=("keep", "keep"),
            note="phone call: phone at the ear, talking, small weight shifts (phone_track gives the phone in the hand)")
        put("Consume", "Consume_Item", False, "action", restance=("keep", "keep"), note="uses / shows an item held out in the left hand (library 'Consume'; not hand-to-mouth: see Eat_Drink)")
        put("Yes", "Nod_Yes", False, "action", restance=("relaxed", "relaxed"), note="nods yes")
        put("Idle_No_Loop", "Shake_No_Loop", True, "standing", restance=("relaxed", "relaxed"), note="shakes the head no")
        put("Idle_FoldArms_Loop", "Idle_FoldArms_Loop", True, "standing", restance=("keep", "keep"), note="waiting with folded arms")
        # crouch
        put("Crouch_Idle_Loop", "Crouch_Idle_Loop", True, "standing", note="crouched idle")
        if "Crouch_Fwd_Loop" in have:
            cw, _, _ = self.clean_feet(self.unbias(self.ext("Crouch_Fwd_Loop"), E["src"]["Crouch_Fwd_Loop"][2]), False)
            cw, _ = self.lock_feet(cw, ground=0.012)
            S["Crouch_Walk_Loop"] = lab("Crouch_Fwd_Loop", ", feet locked with IK")
            self.add("Crouch_Walk_Loop", cw, True, "locomotion", ground=0.012, note="crouched walk forward")
        if "Push_Loop" in have:
            pw, _, _ = self.clean_feet(self.unbias(self.ext("Push_Loop"), E["src"]["Push_Loop"][2]), False)
            pw, _ = self.lock_feet(pw, ground=0.03)
            S["Push_Loop"] = lab("Push_Loop", ", feet locked with IK")
            self.add("Push_Loop", pw, True, "locomotion", ground=0.03,
                     note="pushing forward with both hands at chest height (door, cart); walk the root at the measured speed, 0 = pushing in place")
        # sitting (chair): the seat height is the lowest point under the pelvis in Sit_Idle
        sit = put("Sitting_Idle_Loop", "Sit_Idle_Loop", True, "sit", note="sitting on a chair, relaxed")
        meta_sit = {}
        if sit:
            sh = self.seat_height(sit[0])
            Wd = self.W(sit[0])
            meta_sit = {"seat_height_m": round(sh, 3) if sh else None,
                        "hips_courier_root": [round(c, 3) for c in to_godot_bike(Wd["Hips"].to_translation())]}
            for n_, _, m in self.out:
                if n_ == "Sit_Idle_Loop":
                    m.update(meta_sit)
            log("  sitting: seat height %.3f m (chair seat for the clips)" % (sh or -1))
        put("Sitting_Enter", "Sit_Enter", False, "sit", floor="min", note="standing in front of a chair -> sitting (chair seat height: see Sit_Idle seat_height_m)", **meta_sit)
        put("Sitting_Exit", "Sit_Exit", False, "sit", floor="min", note="sitting -> standing up", **meta_sit)
        put("Sitting_Talking_Loop", "Sit_Talk_Loop", True, "sit", note="sitting and talking", **meta_sit)
        # car (driver's seat: hands on the wheel)
        car = put("Driving_Loop", "Car_Drive_Loop", True, "car",
                  note="driver's seat, both hands on the steering wheel with small steering corrections; feet set to z 0 (put the root on the car floor)")
        if car:
            Wc = self.W(car[0])
            mid = (Wc["LeftHand"].to_translation() + Wc["RightHand"].to_translation()) / 2
            for n_, _, m in self.out:
                if n_ == "Car_Drive_Loop":
                    m["hands_mid_courier_root"] = [round(c, 3) for c in to_godot_bike(mid)]
                    m["hips_courier_root"] = [round(c, 3) for c in to_godot_bike(Wc["Hips"].to_translation())]
        # one-shot actions
        put("Chest_Open", "Open_Box", False, "action", floor="first", note="kneels / bends and lifts a lid open with both hands (a package box or a locker)")
        if "OverhandThrow" in have:
            p = self.floor_at(self.unbias(self.ext("OverhandThrow"), E["src"]["OverhandThrow"][2]), "first")
            rf, side, v = self.fastest_hand_frame(p)
            S["Throw"] = lab("OverhandThrow")
            self.add("Throw", p, False, "action", release_frame=rf, release_hand=side.lower(),
                     note="overhand throw (newspaper / package onto a porch); release at frame %d (%s hand, %.1f m/s)" % (rf, side.lower(), v),
                     events=[{"frame": rf, "do": "release", "hand": side.lower()}])
        put("ClimbUp_1m", "ClimbUp_1m", False, "action", floor="first",
            note="climb up onto a 1 m ledge (feet on z 0 at frame 0)")
        put("Roll", "Roll", False, "action", floor="first", note="forward roll (hard-landing recovery), in place")
        put("LayToIdle", "Get_Up", False, "action", floor="last", note="get up from lying on the ground to standing (after a bike crash)")
        put("Hit_Knockback", "Hit_Knockback", False, "action", floor="first", note="knocked back by a hit (bike crash / collision)")
        put("Slide_Start", "Slide_Start", False, "action", floor="first", note="run into a slide")
        put("Slide_Loop", "Slide_Loop", True, "action", floor="min", note="sliding on the ground")
        put("Slide_Exit", "Slide_Exit", False, "action", floor="last", note="slide back up to running")
        for n_, poses, m in self.out:
            src = {"ClimbUp_1m": "ClimbUp_1m", "Roll": "Roll"}.get(n_)
            if src and src in E.get("root", {}):
                pts, fps = E["root"][src]
                P0 = len(pts) - 1
                N = len(poses) - 1
                samples = []
                for k in range(N + 1):
                    t = k * P0 / N
                    i = min(int(t), P0 - 1)
                    a = t - i
                    v = pts[i].lerp(pts[i + 1], a) - pts[0]
                    samples.append([round(c, 4) for c in to_godot_bike(v)])
                m["root_motion"] = "root_curve"
                m["root_motion_samples_30fps"] = samples
                m["end_offset_courier_root"] = samples[-1]
                m["note"] = m.get("note", "") + "; the clip is in place: move the root along root_motion_samples_30fps (Courier-root frame) from the library's root-motion version"
        if "Phone_Call_Loop" in [n for n, _, _ in self.out]:
            i = [n for n, _, _ in self.out].index("Phone_Call_Loop")
            name_, poses, meta = self.out[i]
            W = self.W(poses[0])
            hd = W["Head"].to_translation()
            side = min(("Left", "Right"), key=lambda s: (W[s + "Hand"].to_translation() - hd).length)
            self.phone_side["Phone_Call_Loop"] = side
            self.out[i] = (name_, self.phone_at_ear(poses, side), meta)

    def phone_at_ear(self, poses, side):
        """Phone call: the phone hand is IK'd so the phone lies on the ear and cheek (screen to the
        face, top behind the ear, bottom toward the mouth); phone grip on the fingers."""
        sx = 1 if side == "Left" else -1
        F = phone_frame(self, side)
        H0 = self.rig.rest["Head"].to_translation()
        ear = Vector((sx * 0.082, 0.012, 0.045))
        z = -sx * LEFT
        y = (UP * 0.78 - FWD * 0.62).normalized()
        y = (y - z * y.dot(z)).normalized()
        Rp = Matrix((y.cross(z), y, z)).transposed()
        out = []
        for P in poses:
            P = {k: m.copy() for k, m in P.items()}
            W = self.W(P)
            qh = W["Head"].to_quaternion() @ self.rig.rest_rot["Head"].inverted()
            c = W["Head"].to_translation() + qh @ (ear + LEFT * (sx * 0.014) + FWD * 0.025 - UP * 0.045)
            Mp = Matrix.Translation(c) @ (qh.to_matrix() @ Rp).to_4x4()
            Mh = Mp @ F.inverted()
            pole = (LEFT * (0.8 * sx) - UP * 0.7 - FWD * 0.15).normalized()
            W = self.limbs.arm(P, W, side, Mh.to_translation(), pole, Mh.to_quaternion())
            for f, angs in zip(("Index", "Middle", "Ring", "Little", "Thumb"), self.PHONE_CURL):
                self.set_finger(P, side, f, angs)
            out.append(P)
        return out

    # ------------------------------------------------------------------ bicycle
    def bike_clips(self, R):
        """prepare_player's fit (hips on the saddle, elbows slightly bent) and the crank-synced
        Bike_Pedal loop; the other bike clips come from keyed_bike()."""
        self.load_bike()
        self.idle0 = R["Idle"][0]
        S = self.bike["Seat"]
        hips = S + UP * 0.16 + FWD * 0.02
        lean = 26.0
        for it in range(4):
            lo, hi = 10.0, 80.0
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
            log("  bike fit it %d: seat gap %.4f -> hips %s, lean param %.1f (trunk %.1f deg), reach %.3f"
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
        flex = [k[2] for k in knees]
        log("  knee flexion over the stroke: min %.1f max %.1f deg, max reach %.3f" % (min(flex), max(flex), max(k[3] for k in knees)))
        self.knees = knees
        self.add("Bike_Pedal_Loop", poses, True, "bike", crank_deg_per_s=360.0 / (N / FPS),
                 note="seated pedalling, one forward crank revolution per clip second; frame k <-> crank angle 360*k/%d deg from rest (right crank forward, Crank rotation.x = -angle)" % N,
                 knee_flexion_min_deg=min(flex), knee_flexion_max_deg=max(flex))
        return poses

    BIKE_SEATED_PELVIS = 20.0      # seated pelvis pitch vs the MPFB rest (deg); the code's nominal 14 maps to it

    def hp_shift(self):
        if not hasattr(self, "_hps"):
            self._hps = self.BIKE_SEATED_PELVIS - 14.0 - self.pelvis_dev(self.rig.fk(self.rig.identity()))
            log("  bike pelvis: nominal hip pitch +%.1f deg -> %.0f deg vs the MPFB rest" % (self._hps, self.BIKE_SEATED_PELVIS))
        return self._hps

    def bike_pose(self, alpha, hips_pos, lean, breath=0.0, rock=0.0, pitch_feet=0.0):
        """prepare_player.Clips.bike_pose with the pelvis pitch measured against the MPFB rest
        (the library-matched rest pelvis already points ~34 deg forward)."""
        hp = 14.0 + self.hp_shift()
        P = {n: m.copy() for n, m in self.idle0.items()}
        for n in P:
            if any(k in n for k in ("Thumb", "Index", "Middle", "Ring", "Little")):
                P[n] = Matrix.Identity(4)
        W = self.W(P)
        hq = Quaternion(LEFT, math.radians(hp)) @ Quaternion(FWD, rock) @ self.rig.rest_rot["Hips"]
        W = self.rig.set_world(P, W, "Hips", Matrix.Translation(hips_pos) @ hq.to_matrix().to_4x4())
        rest_lean = lean - hp
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

    def pedal_ball(self, side, alpha):
        return self.pedal(side, alpha) + UP * 0.012

    def foot_q(self, side, pitch=0.0, yaw=0.0):
        return Quaternion(UP, math.radians(yaw)) @ Quaternion(LEFT, math.radians(pitch)) @ self.rig.rest_rot[side + "Foot"]

    def keyed_bike(self, name, T, keys, loop=False, kind="bike", fingers_fn=None, crank=None, hands=True, **meta):
        """Bicycle-space body from keyed tracks (lists of (t, value[, 'stop']) or callables of t):
        hips (Vector), hpitch / hroll / hyaw (deg), lean (trunk, deg), twist, head_yaw, head_pitch,
        breath, ballL / ballR (Vector: ball of the foot), fpL / fpR (foot pitch, + = toes down),
        fyL / fyR (foot yaw, + = toes to the left), poleL / poleR (knee direction)."""
        K = {k: KeyT(v) for k, v in keys.items()}
        N = int(round(T * FPS))
        poses, track = [], []
        for k in range(N + 1):
            t = k / FPS
            g = (lambda key, d: K[key].at(t) if key in K else d)
            P = {n: m.copy() for n, m in self.idle0.items()}
            for n in P:
                if any(f in n for f in ("Thumb", "Index", "Middle", "Ring", "Little")):
                    P[n] = Matrix.Identity(4)
            W = self.W(P)
            hp = g("hpitch", 14.0) + self.hp_shift()
            hq = (Quaternion(UP, math.radians(g("hyaw", 0.0))) @ Quaternion(LEFT, math.radians(hp))
                  @ Quaternion(FWD, math.radians(g("hroll", 0.0))) @ self.rig.rest_rot["Hips"])
            W = self.rig.set_world(P, W, "Hips", Matrix.Translation(Vector(g("hips", self.bike_hips))) @ hq.to_matrix().to_4x4())
            lean = g("lean", self.bike_lean)
            tw = g("twist", 0.0)
            rest_lean = lean - hp
            for n, share in (("Spine", 0.38), ("Chest", 0.34), ("UpperChest", 0.28)):
                a = rest_lean * share + (g("breath", 0.0) if n == "Chest" else 0.0)
                W = rotate_bone_world(self.rig, P, W, n, Quaternion(UP, math.radians(tw * share)) @ Quaternion(LEFT, math.radians(a)))
            hy, hpch = g("head_yaw", 0.0), g("head_pitch", 0.0)
            for n, share, ys in (("Neck", -0.42, 0.4), ("Head", -0.40, 0.6)):
                W = rotate_bone_world(self.rig, P, W, n, Quaternion(UP, math.radians(hy * ys)) @ Quaternion(LEFT, math.radians(lean * share + hpch * ys)))
            for side, sx in (("Left", 1), ("Right", -1)):
                W = rotate_bone_world(self.rig, P, W, side + "Shoulder", Quaternion(UP, -sx * math.radians(7)))
            if hands:
                for side in ("Left", "Right"):
                    W = self.grip_hand(P, W, side)
            if fingers_fn:
                fingers_fn(self, P, t)
                W = self.W(P)
            for side, s in (("Left", "L"), ("Right", "R")):
                q = self.foot_q(side, g("fp" + s, 0.0), g("fy" + s, 0.0))
                ball = Vector(g("ball" + s, self.pedal_ball(side, 0.0)))
                ank = ball - q @ self.contacts[side]["ball"]
                pole = Vector(g("pole" + s, FWD + LEFT * (0.10 if side == "Left" else -0.10)))
                W = self.limbs.leg(P, W, side, ank, pole, q, stretch=0.999)
            poses.append(P)
            track.append(None if crank is None else crank(t))
        rec = self.add(name, poses, loop, kind, **meta)
        self.crank_tracks[name] = track
        return poses

    def reach_leg(self, W, side, ank):
        return (ank - W[side + "UpperLeg"].to_translation()).length / sum(self.limbs.len[side + "UpperLeg"])

    def bike_extras(self):
        self.crank_tracks = getattr(self, "crank_tracks", {})
        self.crank_tracks["Bike_Pedal_Loop"] = [2 * math.pi * k / 30 for k in range(31)]
        H, lean = self.bike_hips, self.bike_lean
        B = self.bike
        # ---- seated, left foot down on its toes (stopped); right foot on the forward pedal
        hfd = H + LEFT * 0.035 + UP * -0.004
        best = None
        for pitch in range(20, 62, 2):
            for dx in (0.20, 0.19, 0.18, 0.17, 0.16):
                ball = Vector((hfd.x + dx, hfd.y - 0.13, 0.006))
                P, W = self.bike_pose(0.0, hfd, lean)
                q = self.foot_q("Left", pitch, 8.0)
                ank = ball - q @ self.contacts["Left"]["ball"]
                r = self.reach_leg(W, "Left", ank)
                if r < 0.985 and (best is None or (r > best[0] and r < 0.985)):
                    best = (r, pitch, dx, ball)
            if best and best[0] > 0.95:
                break
        r, fpitch, dx, ball_fd = best
        log("  foot-down: toe pitch %d deg, foot %.2f m left of the hips, leg reach %.3f" % (fpitch, dx, r))
        self.fd = {"hips": hfd, "fp": fpitch, "ball": ball_fd, "hroll": -4.0, "lean": lean - 3.0}
        L = 2.0
        cyc = lambda a, b=0.0: (lambda t: a * math.sin(2 * math.pi * t / L + b))
        self.keyed_bike("Bike_Seated_Loop", L, {
            "hips": [(0, hfd)], "hroll": [(0, -4.0)], "lean": (lambda t: lean - 3.0 + 0.5 * math.sin(2 * math.pi * t / L)),
            "breath": cyc(1.3), "head_yaw": cyc(4.0, 1.0), "head_pitch": [(0, -3.0)],
            "ballL": [(0, ball_fd)], "fpL": [(0, float(fpitch))], "fyL": [(0, 8.0)], "poleL": [(0, FWD + LEFT * 0.45)],
            "ballR": [(0, self.pedal_ball("Right", 0.0))]}, loop=True, crank=lambda t: 0.0,
            note="stopped on the saddle: left foot down on its toes beside the bike, right foot on the forward pedal (crank at rest), breathing",
            hips_bike_space_godot=[round(c, 4) for c in to_godot_bike(hfd)])
        # ---- coasting, level pedals
        self.keyed_bike("Bike_Coast_Loop", L, {
            "lean": (lambda t: lean + 0.4 * math.sin(2 * math.pi * t / L)), "breath": cyc(1.0),
            "head_yaw": cyc(7.0, 0.5), "head_pitch": cyc(1.5, 1.3), "hroll": cyc(0.8),
            "ballL": [(0, self.pedal_ball("Left", 0.0))], "ballR": [(0, self.pedal_ball("Right", 0.0))]},
            loop=True, crank=lambda t: 0.0,
            note="freewheeling: seated, pedals level (crank at rest, right forward), relaxed look around; crank does not turn")
        # ---- out of the saddle
        self.stand_pedal()
        # ---- braking (one shot, ends holding the levers)
        def brake_fingers(C, P, t):
            u1 = ease((t - 0.04) / 0.16)
            u2 = ease((t - 0.20) / 0.18)
            for side in ("Left", "Right"):
                for f, g0 in (("Index", (62, 80, 50)), ("Middle", (66, 84, 52))):
                    ext = [a + (b - a) * u1 for a, b in zip(g0, (14, 22, 14))]
                    pull = [a + (b - a) * u2 for a, b in zip(ext, (38, 58, 40))]
                    C.set_finger(P, side, f, pull)
        self.keyed_bike("Bike_Brake", 1.0, {
            "hips": [(0, H), (0.25, H + FWD * -0.012), (0.55, H + FWD * 0.008), (1.0, H + FWD * -0.004)],
            "lean": [(0, lean), (0.3, lean - 2.0), (0.55, lean + 3.0), (1.0, lean + 1.0)],
            "head_pitch": [(0, 0.0), (0.5, 4.0), (1.0, 1.0)],
            "ballL": [(0, self.pedal_ball("Left", 0.0))], "ballR": [(0, self.pedal_ball("Right", 0.0))]},
            fingers_fn=brake_fingers, crank=lambda t: 0.0,
            note="seated, pedals level: index and middle fingers reach forward to the brake levers (in front of the grips) and pull; the body braces against the deceleration; ends holding the levers",
            events=[{"frame": 6, "do": "sfx", "name": "brake"}])
        # ---- shoulder check
        self.keyed_bike("Bike_Look_Back", 1.8, {
            "twist": [(0, 0.0), (0.5, 22.0), (1.1, 22.0, "stop"), (1.8, 0.0)],
            "hyaw": [(0, 0.0), (0.5, 4.0), (1.1, 4.0), (1.8, 0.0)],
            "head_yaw": [(0, 0.0), (0.5, 72.0), (1.1, 72.0, "stop"), (1.8, 0.0)],
            "head_pitch": [(0, 0.0), (0.5, -6.0), (1.1, -6.0), (1.8, 0.0)],
            "lean": [(0, lean), (0.5, lean - 4.0), (1.1, lean - 4.0), (1.8, lean)],
            "ballL": [(0, self.pedal_ball("Left", 0.0))], "ballR": [(0, self.pedal_ball("Right", 0.0))]},
            crank=lambda t: 0.0,
            note="coasting shoulder check over the left shoulder (torso twist + head turn), hands stay on the grips")
        # ---- bell (right thumb)
        def bell_thumb(C, P, t):
            u = max(ease((t - 0.12) / 0.10) * (1 - ease((t - 0.30) / 0.10)), ease((t - 0.42) / 0.10) * (1 - ease((t - 0.60) / 0.12)))
            g0 = (18, 28, 30)
            C.set_finger(P, "Right", "Thumb", [a + (b - a) * u for a, b in zip(g0, (-6, -14, 8))], spread=-18 * u)
        self.keyed_bike("Bike_Bell", 0.9, {
            "head_pitch": [(0, 0.0), (0.3, 3.0), (0.9, 0.0)],
            "ballL": [(0, self.pedal_ball("Left", 0.0))], "ballR": [(0, self.pedal_ball("Right", 0.0))]},
            fingers_fn=bell_thumb, crank=lambda t: 0.0,
            note="right thumb flicks the bell lever twice (bell assumed just inboard of the right grip; the gray bicycle has no bell model yet)",
            events=[{"frame": 7, "do": "sfx", "name": "bell"}, {"frame": 15, "do": "sfx", "name": "bell"}])
        self.mount()

    def stand_pedal(self):
        """Out of the saddle: hips forward over the bottom bracket and up, trunk further forward,
        the body sways over the down-stroke pedal; one crank revolution per clip second."""
        B = self.bike
        N = 30
        Cr = B["Crank"]
        lean0 = self.bike_lean + 16.0
        base_h = Vector((0.0, Cr.y + 0.01, 0.0))
        # hip height: the longest hip -> ankle reach over the stroke is 0.965 of the leg
        best_z = None
        for z in np.arange(1.30, 0.85, -0.005):
            worst = 0.0
            for k in range(0, N, 3):
                a = 2 * math.pi * k / N
                h = base_h + UP * float(z)
                P, W = self.bike_pose(a, h, lean0)
                for s in ("Left", "Right"):
                    q = self.rig.rest_rot[s + "Foot"]
                    ank = self.pedal_ball(s, a) - q @ self.contacts[s]["ball"]
                    worst = max(worst, self.reach_leg(W, s, ank))
            if worst <= 0.985:
                best_z = float(z)
                break
        H = base_h + UP * best_z
        log("  stand pedal: hips %s" % (tuple(round(c, 3) for c in H),))

        def hips(t):
            a = 2 * math.pi * t
            return H + UP * (-0.02 * math.cos(2 * a)) + LEFT * (-0.03 * math.sin(a))

        self.keyed_bike("Bike_Stand_Pedal_Loop", 1.0, {
            "hips": hips, "hpitch": [(0, 30.0)], "lean": (lambda t: lean0 + 1.5 * math.cos(4 * math.pi * t)),
            "hroll": (lambda t: 6.0 * math.sin(2 * math.pi * t)), "twist": (lambda t: -4.0 * math.sin(2 * math.pi * t)),
            "head_pitch": [(0, -6.0)],
            "ballL": (lambda t: self.pedal_ball("Left", 2 * math.pi * t)), "ballR": (lambda t: self.pedal_ball("Right", 2 * math.pi * t)),
            "fpL": (lambda t: 8.0 * math.sin(2 * math.pi * t + math.pi)), "fpR": (lambda t: 8.0 * math.sin(2 * math.pi * t)),
            "poleL": [(0, FWD + LEFT * 0.12)], "poleR": [(0, FWD - LEFT * 0.12)]},
            loop=True, crank=lambda t: 2 * math.pi * t, crank_deg_per_s=360.0,
            note="out of the saddle (climb / sprint), one forward crank revolution per clip second like Bike_Pedal; the body sways over the down-stroke pedal",
            hips_bike_space_godot=[round(c, 4) for c in to_godot_bike(H)])

    def mount(self):
        """Mount from the left side: hands on the grips, weight onto the left foot, the right leg
        swings up and back over the saddle, down onto the right pedal, sit; ends in Bike_Seated."""
        fd = self.fd
        S = self.bike["Seat"]
        W0 = self.W(self.idle0)
        hz = W0["Hips"].to_translation().z
        HS = Vector((0.33, 0.04, hz - 0.035))           # standing beside the bike, a little behind the grips
        bl0 = Vector((0.43, 0.04, 0.0))
        br0 = Vector((0.21, -0.02, 0.0))
        pr = self.pedal_ball("Right", 0.0)
        lean = self.bike_lean
        keys = {
            "hips": [(0.0, HS), (0.40, HS + LEFT * 0.06 + UP * 0.005), (0.80, HS + LEFT * 0.07 + Vector((0, 0.04, 0.02))),
                     (1.10, Vector((0.33, 0.12, hz - 0.02))), (1.40, Vector((0.22, 0.20, hz - 0.03))),
                     (1.75, fd["hips"] + Vector((0.06, -0.02, 0.03))), (2.05, fd["hips"], "stop"), (2.4, fd["hips"])],
            "hyaw": [(0.0, -14.0), (0.40, -14.0), (0.80, -10.0), (1.40, -6.0), (2.05, 0.0)],
            "hpitch": [(0.0, 10.0), (0.40, 16.0), (0.80, 28.0), (1.10, 32.0), (1.40, 24.0), (2.05, 14.0)],
            "hroll": [(0.0, 0.0), (0.40, -4.0), (0.80, -9.0), (1.10, -7.0), (1.75, -4.0), (2.4, fd["hroll"])],
            "lean": [(0.0, 30.0), (0.40, 34.0), (0.80, 42.0), (1.10, 46.0), (1.40, 38.0), (1.75, 30.0), (2.05, fd["lean"]), (2.4, fd["lean"])],
            "twist": [(0.0, -16.0), (0.40, -16.0), (0.80, -10.0), (1.40, -4.0), (2.05, 0.0)],
            "head_yaw": [(0.0, -8.0), (0.8, 0.0), (2.4, 0.0)], "head_pitch": [(0.0, 6.0), (0.8, 4.0), (2.05, -3.0)],
            "ballL": [(0.0, bl0), (1.55, bl0, "stop"), (1.80, (bl0 + fd["ball"]) / 2 + UP * 0.05), (2.0, fd["ball"], "stop"), (2.4, fd["ball"])],
            "fpL": [(0.0, 0.0), (0.80, 0.0), (1.35, 8.0), (1.55, 22.0), (2.0, float(fd["fp"])), (2.4, float(fd["fp"]))],
            "fyL": [(0.0, 0.0), (1.55, 0.0), (2.0, 8.0)],
            "poleL": [(0.0, FWD + LEFT * 0.2), (1.5, FWD + LEFT * 0.35), (2.0, FWD + LEFT * 0.45)],
            "ballR": [(0.0, br0), (0.30, br0, "stop"), (0.62, Vector((0.25, 0.38, 0.32))), (0.92, Vector((0.17, 0.64, 0.80))),
                      (1.18, Vector((-0.05, 0.66, 0.90))), (1.45, Vector((-0.25, 0.48, 0.60))), (1.75, Vector((-0.22, 0.10, 0.36))),
                      (2.0, pr, "stop"), (2.4, pr)],
            "fpR": [(0.0, 0.0), (0.30, 12.0), (0.62, 45.0), (0.92, 35.0), (1.45, 20.0), (1.75, 10.0), (2.0, 0.0)],
            "fyR": [(0.0, -6.0), (0.30, -6.0), (1.0, 0.0)],
            "poleR": [(0.0, FWD - LEFT * 0.1), (0.30, FWD - LEFT * 0.1), (0.62, -UP + FWD * 0.3), (0.92, -UP * 0.6 + FWD * 0.2 + LEFT * 0.4),
                      (1.18, -UP * 0.6 + FWD * 0.4), (1.45, FWD - UP * 0.4 - LEFT * 0.3), (1.75, FWD), (2.0, FWD - LEFT * 0.1)],
        }
        self.keyed_bike("Bike_Mount", 2.4, keys, crank=lambda t: 0.0,
                        note="from standing at the left of the bike with both hands on the grips: weight onto the left foot, the right leg swings up and back over the saddle and down onto the forward right pedal, sit, the left foot steps to its toe-down spot; ends in the Bike_Seated pose",
                        events=[{"frame": 60, "do": "sfx", "name": "bike_mount"}])
        # Dismount: the same motion backwards (stand up on the left foot, leg back over the saddle)
        T = 2.2
        rev = {}
        for k, v in keys.items():
            items = []
            for kk in v:
                t = kk[0] / 2.4 * T
                items.append((T - t, kk[1]) + tuple(kk[2:]))
            rev[k] = sorted(items, key=lambda x: x[0])
        self.keyed_bike("Bike_Dismount", T, rev, crank=lambda t: 0.0,
                        note="from the Bike_Seated pose: stand on the left foot, the right leg swings back over the saddle and steps down at the left of the bike; ends standing beside the bike with both hands on the grips (the game hands over to Idle with a blend)",
                        events=[{"frame": 6, "do": "sfx", "name": "bike_dismount"}],
                        end_offset_bike_space_godot=[round(c, 4) for c in to_godot_bike(Vector((HS.x, HS.y, 0)))])


# --------------------------------------------------------------------------- bag / delivery / standing actions
def bag_module(C):
    import courier_bag
    courier_bag.bind(globals())
    courier_bag.CURLS.update({
        "fist": ((84, 96, 62), (86, 98, 64), (88, 98, 62), (88, 96, 60), (34, 30, 34)),
        "point": ((2, 4, 2), (70, 92, 56), (76, 94, 56), (80, 94, 56), (28, 26, 20)),
        "open": ((2, 3, 2), (2, 3, 2), (3, 4, 2), (4, 5, 3), (6, 4, 2)),
    })
    return courier_bag


def make_bag_class(cb):
    BagWork, Keys, T, rx, rz = cb.BagWork, cb.Keys, cb.T, cb.rx, cb.rz
    hermite, quat_track = cb.hermite, cb.quat_track
    PKG = cb.PKG

    class V3Bag(BagWork):
        VARIANTS = ["Walk_Loop", "Walk_Back_Loop", "Jog_Mixamo_Loop", "Jog_Loop", "Run_Loop", "Sprint_Loop", "Strafe_L_Loop", "Strafe_R_Loop",
                    "Turn_L_90", "Turn_R_90", "Jump_Start", "Jump_Loop", "Jump_Land", "Land_Hard", "Interact", "PickUp_Table"]

        def grip_world(self, side, M, G, d, n, kind):
            if kind not in ("knuckle", "tip"):
                return BagWork.grip_world(self, side, M, G, d, n, kind)
            R3 = M.to_3x3().normalized()
            Gw = M @ Vector(G)
            dw = (R3 @ Vector(d)).normalized()
            nw = R3 @ Vector(n)
            nw = (nw - dw * nw.dot(dw)).normalized()
            _, _, L = self.C.hand_frame(side)
            if kind == "knuckle":
                wrist = Gw - dw * (1.0 * L) - nw * 0.012
            else:
                wrist = Gw - dw * self.tip_len(side) * 0.97 - nw * 0.008
            return wrist, self.hand_rot(side, dw, nw)

        def bag_variant(self, name):
            new = BagWork.bag_variant(self, name)
            if new:
                src = next((m.get("source") for n, _, m in self.C.out if n == name), "authored")
                for n, _, m in self.C.out:
                    if n == new:
                        m["source"] = "%s; arms eased around the worn backpack" % src
            return new

        def perform(self, name, n_frames, base, spec, loop=False, kind="bag", **meta):
            # the base poses already carry the upright clavicles (walk template): keep them
            spec.setdefault("neutral_shoulders", False)
            return BagWork.perform(self, name, n_frames, base, spec, loop, kind, **meta)

        def tip_len(self, side):
            arm = self.arm
            b = arm.data.bones[side + "IndexDistal"]
            tip = b.tail_local
            h = arm.data.bones[side + "Hand"].head_local
            return (tip - h).length

        FIT_CLIPS = [c for c in BagWork.FIT_CLIPS if not c.startswith("Bike")] + ["Jog_Loop"]   # bike: checked, not fitted
        # BagWork.fit_worn with a wider tilt search (the upright back needs more than -6 deg)
        import inspect, textwrap
        _src = textwrap.dedent(inspect.getsource(BagWork.fit_worn)).replace("np.arange(-6.0, 12.01, 0.5)", "np.arange(-20.0, 16.01, 0.5)")
        _ns = {}
        exec(_src, cb.__dict__, _ns)
        fit_worn = _ns["fit_worn"]

        def build_clips(self):
            BagWork.build_clips(self)
            self.pickup_floor()
            self.pickup_shelf()
            self.knock()
            self.doorbell()
            self.wave()
            self.look_back()
            self.eat_drink()

        # ---------------------------------------------------------------- delivery
        SQUAT = {"hips": (0, 0.15, -0.56), "pitch": 30.0, "flex": 34.0, "heel": 18.0}
        PKG_GROUND_Y = -0.33

        def chest_at(self, N, base, spec, times):
            """UpperChest world matrices at the given times from a body-only draft of a clip."""
            body = {k: v for k, v in spec.items() if k in ("hips", "pitch", "flex", "twist", "side", "yaw", "roll", "heel_Left", "heel_Right")}
            n0 = len(self.C.out)
            rec = self.perform("_draft", N, base, body, kind="action")
            del self.C.out[n0:]
            self.clips.pop("_draft", None)
            return [rec["frames"][int(round(t * FPS))]["W"]["UpperChest"].copy() for t in times]

        def grabbed(self, UC, M):
            return ("uc", UC.inverted() @ M)

        def pregrip(self, side, up=0.12, out=0.05):
            G, d, n, kind = self.carry_grip(side)
            sx = 1 if side == "Left" else -1
            return ((G[0] + sx * out, G[1], G[2] + up), d, n, kind)

        def pickup_floor(self):
            pk = self.pkg_carry(None)
            ground = T((0.0, self.PKG_GROUND_Y, 0.0))
            Q = self.SQUAT
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.62, Q["hips"], "stop"), (0.80, Q["hips"], "stop"), (1.40, (0, 0, 0), "stop"), (1.6, (0, 0, 0))]),
                "pitch": Keys([(0.0, 0.0), (0.62, Q["pitch"], "stop"), (0.80, Q["pitch"] - 2, "stop"), (1.40, 0.0, "stop"), (1.6, 0.0)]),
                "flex": Keys([(0.0, 0.0), (0.62, Q["flex"], "stop"), (0.80, Q["flex"] - 2, "stop"), (1.40, -2.0, "stop"), (1.6, -2.0)]),
                "heel_Left": Keys([(0.0, 0.0), (0.62, Q["heel"]), (0.80, Q["heel"] - 3), (1.40, 0.0)]),
                "heel_Right": Keys([(0.0, 0.0), (0.62, Q["heel"]), (0.80, Q["heel"] - 3), (1.40, 0.0)]),
                "hand_Left": [(0.0, ("idle",)), (0.42, ("pkg", self.pregrip("Left"), "box", self.POLE_L)),
                              (0.62, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"), (1.6, ("pkg", self.carry_grip("Left"), "box", self.POLE_L))],
                "hand_Right": [(0.0, ("idle",)), (0.42, ("pkg", self.pregrip("Right"), "box", self.POLE_R)),
                               (0.62, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"), (1.6, ("pkg", self.carry_grip("Right"), "box", self.POLE_R))],
                "look": [(0.0, (0, -2.0, 1.5), 0.2), (0.3, "pkg", 0.55), (0.9, "pkg", 0.55), (1.4, (0, -2.0, 1.45), 0.25), (1.6, (0, -2.0, 1.45), 0.25)],
                "events": [{"frame": 20, "do": "package", "to": "track"}],
            }
            U1, = self.chest_at(48, self.idle_base(), spec, (0.80,))
            spec["pkg"] = [(0.0, ("world", ground)), (0.66, ("world", ground), "stop"), (0.80, self.grabbed(U1, T((0, 0.0, 0.03)) @ ground)),
                           (1.40, pk, "stop"), (1.6, pk)]
            return self.perform("PickUp", 48, self.idle_base(), spec, kind="action",
                                note="squat (knees bent, back ~50 deg), both hands take the package from the ground 0.33 m in front (grab at frame 20), stand up holding it in front (ends in the Carry_Idle pose). package_track frame 0 = where the package must lie",
                                package_grab_frame=20)

        def place_down(self):
            pk = self.pkg_carry(None)
            ground = T((0.0, self.PKG_GROUND_Y, 0.0))
            Q = self.SQUAT
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.62, Q["hips"], "stop"), (0.74, Q["hips"]), (1.3, (0, 0, 0), "stop")]),
                "pitch": Keys([(0.0, 0.0), (0.62, Q["pitch"], "stop"), (0.74, Q["pitch"] - 2), (1.3, 0.0, "stop")]),
                "flex": Keys([(0.0, -2.0), (0.62, Q["flex"], "stop"), (0.74, Q["flex"] - 2), (1.3, 0.0, "stop")]),
                "heel_Left": Keys([(0.0, 0.0), (0.62, Q["heel"]), (0.80, Q["heel"] - 3), (1.3, 0.0)]),
                "heel_Right": Keys([(0.0, 0.0), (0.62, Q["heel"]), (0.80, Q["heel"] - 3), (1.3, 0.0)]),
                "hand_Left": [(0.0, ("pkg", self.carry_grip("Left"), "box", self.POLE_L)), (0.64, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"),
                              (0.82, ("pkg", self.pregrip("Left"), "box", self.POLE_L)), (1.3, ("idle",), "stop")],
                "hand_Right": [(0.0, ("pkg", self.carry_grip("Right"), "box", self.POLE_R)), (0.64, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"),
                               (0.82, ("pkg", self.pregrip("Right"), "box", self.POLE_R)), (1.3, ("idle",), "stop")],
                "look": [(0.0, (0, -2.0, 1.45), 0.25), (0.3, "pkg", 0.55), (0.8, "pkg", 0.55), (1.3, (0, -2.0, 1.55), 0.1)],
                "events": [{"frame": 0, "do": "package", "to": "track"}, {"frame": 19, "do": "package", "to": "released"}],
            }
            U, = self.chest_at(39, self.idle_base(), spec, (0.62,))
            spec["pkg"] = [(0.0, pk), (0.52, self.grabbed(U, T((0, 0.0, 0.03)) @ ground)), (0.62, ("world", ground), "stop"), (1.3, ("world", ground))]
            return self.perform("PlaceDown", 39, self.idle_base(), spec, kind="action",
                                note="squat (knees bent, back ~50 deg) and set the package on the ground 0.33 m in front (leave at door), release at frame 19, stand up",
                                package_release_frame=19)

        def handover(self):
            """Offer the package to the customer: weight shifts forward onto the balls of the feet,
            slight lean, the head dips toward the recipient's hands (nod) at the release, then the
            body settles back with a small overshoot."""
            pk = self.pkg_carry(None)
            spec = {
                "pkg": [(0.0, pk), (0.50, T((0, -0.52, 1.10)), "stop"), (0.66, T((0, -0.54, 1.10)), "stop"), (0.95, T((0, -0.78, 1.16)))],
                "hips": Keys([(0.0, (0, 0, 0)), (0.50, (0, -0.055, -0.012), "stop"), (0.70, (0, -0.05, -0.010)), (1.05, (0, 0.012, -0.002)),
                              (1.30, (0, -0.004, 0.0)), (1.5, (0, 0, 0), "stop")]),
                "flex": Keys([(0.0, -2.0), (0.50, 11.0, "stop"), (0.70, 10.0), (1.05, -1.5), (1.30, 0.5), (1.5, 0.0, "stop")]),
                "heel_Left": Keys([(0.0, 0.0), (0.50, 4.0), (0.80, 3.0), (1.1, 0.0)]),
                "heel_Right": Keys([(0.0, 0.0), (0.50, 4.0), (0.80, 3.0), (1.1, 0.0)]),
                "hand_Left": [(0.0, ("pkg", self.carry_grip("Left"), "box", self.POLE_L)), (0.66, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"),
                              (0.90, ("ref", ((0.24, -0.36, 1.06), (-0.1, -0.6, -0.8), (-0.9, 0, 0.2), "flat"), "flat")), (1.5, ("idle",), "stop")],
                "hand_Right": [(0.0, ("pkg", self.carry_grip("Right"), "box", self.POLE_R)), (0.66, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"),
                               (0.90, ("ref", ((-0.24, -0.36, 1.06), (0.1, -0.6, -0.8), (0.9, 0, 0.2), "flat"), "flat")), (1.5, ("idle",), "stop")],
                "look": [(0.0, (0, -2.0, 1.45), 0.25), (0.30, "pkg", 0.5), (0.55, (0, -0.9, 1.62), 0.8), (0.66, (0, -0.75, 1.20), 0.85),
                         (0.85, (0, -0.95, 1.62), 0.8), (1.2, (0, -1.6, 1.62), 0.4), (1.5, (0, -2.0, 1.6), 0.15)],
                "events": [{"frame": 0, "do": "package", "to": "track"}, {"frame": 20, "do": "package", "to": "released"}],
            }
            return self.perform("Handover", 45, self.idle_base(), spec, kind="action",
                                note="offer the package forward with both hands, weight shifting onto the balls of the feet and a slight lean; the customer takes it at frame 20 with a small nod toward their hands, hands come back and the body settles",
                                package_release_frame=20)

        def eat_drink(self):
            """Right hand brings a held bottle / snack to the mouth (wrap grip, thumb toward the
            face), the head tips back a little while drinking, then the hand lowers."""
            mouth = (-0.012, -0.225, 1.615)
            sip = ("ref", (mouth, (0.75, -0.25, 0.62), (0.45, 0.75, 0.3), "wrap"), "grip", (-0.9, 0.2, -0.5))
            near = ("ref", ((-0.10, -0.24, 1.36), (0.6, -0.5, 0.6), (0.4, 0.8, 0.2), "wrap"), "grip", (-0.9, 0.2, -0.5))
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.6, (0, 0.006, -0.002)), (1.6, (0, 0.006, -0.002)), (2.4, (0, 0, 0))]),
                "flex": Keys([(0.0, 0.0), (0.6, -3.0), (1.6, -3.0), (2.4, 0.0)]),
                "hand_Right": [(0.0, ("idle",)), (0.40, near), (0.62, sip, "stop"), (1.55, sip, "stop"), (1.80, near), (2.4, ("idle",), "stop")],
                "hand_Left": [(0.0, ("idle",))],
                "look": [(0.0, (0, -2.0, 1.55), 0.2), (0.4, (-0.1, -0.5, 1.2), 0.5), (0.7, (0, -1.5, 2.0), 0.5), (1.5, (0, -1.5, 2.05), 0.5),
                         (1.9, (0, -2.0, 1.5), 0.3), (2.4, (0, -2.0, 1.55), 0.2)],
                "events": [{"frame": 19, "do": "sfx", "name": "drink"}],
            }
            return self.perform("Eat_Drink", 72, self.idle_base(), spec, kind="action",
                                note="drinks / eats from the right hand: the item (attach to hand_r) reaches the mouth at frame 19, held to frame 46 with the head tipped back, then lowered")

        def pickup_shelf(self):
            pk = self.pkg_carry(None)
            shelf = T((0.0, -0.50, 0.90))
            spec = {
                "pkg": [(0.0, ("world", shelf)), (0.50, ("world", shelf), "stop"), (0.80, T((0.0, -0.44, 0.94))), (1.10, pk, "stop"), (1.3, pk)],
                "hips": Keys([(0.0, (0, 0, 0)), (0.45, (0, 0.06, -0.035), "stop"), (0.6, (0, 0.06, -0.035)), (1.1, (0, 0, 0), "stop"), (1.3, (0, 0, 0))]),
                "pitch": Keys([(0.0, 0.0), (0.45, 12.0, "stop"), (0.6, 12.0), (1.1, 0.0)]),
                "flex": Keys([(0.0, 0.0), (0.45, 24.0, "stop"), (0.6, 23.0), (1.1, -2.0, "stop"), (1.3, -2.0)]),
                "hand_Left": [(0.0, ("idle",)), (0.45, ("pkg", self.carry_grip("Left"), "box", self.POLE_L), "stop"),
                              (1.3, ("pkg", self.carry_grip("Left"), "box", self.POLE_L))],
                "hand_Right": [(0.0, ("idle",)), (0.45, ("pkg", self.carry_grip("Right"), "box", self.POLE_R), "stop"),
                               (1.3, ("pkg", self.carry_grip("Right"), "box", self.POLE_R))],
                "look": [(0.0, (0, -2.0, 1.5), 0.2), (0.25, "pkg", 0.75), (0.8, "pkg", 0.6), (1.3, (0, -2.0, 1.45), 0.25)],
                "events": [{"frame": 14, "do": "package", "to": "track"}],
            }
            return self.perform("PickUp_Shelf", 39, self.idle_base(), spec, kind="action",
                                note="lean in, both hands take a package standing on a shelf / counter at 0.90 m, 0.50 m in front (grab at frame 14), pull it in to the carry pose (ends in the Carry_Idle pose)",
                                package_grab_frame=14)

        def knock(self):
            door_y = -0.50
            # fist: knuckles forward, thumb up, palm to the courier's left
            d, n = (0.12, -0.96, 0.25), (1.0, 0.05, 0.1)
            P0 = (-0.10, door_y + 0.004, 1.42)
            back = (-0.10, door_y + 0.075, 1.40)
            kf = lambda p: ("world", (p, d, n, "knuckle"), "fist", (-0.75, 0.3, -0.6))
            keys = [(0.0, ("idle",)), (0.40, kf(back)), (0.55, kf(P0), "stop"), (0.66, kf(back)), (0.77, kf(P0), "stop"),
                    (0.88, kf(back)), (0.99, kf(P0), "stop"), (1.12, kf(back)), (1.6, ("idle",), "stop")]
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.5, (0, -0.012, -0.004)), (1.1, (0, -0.012, -0.004)), (1.6, (0, 0, 0))]),
                "flex": Keys([(0.0, 0.0), (0.5, 4.0), (1.1, 4.0), (1.6, 0.0)]),
                "twist": Keys([(0.0, 0.0), (0.5, 6.0), (1.1, 6.0), (1.6, 0.0)]),
                "hand_Right": keys,
                "hand_Left": [(0.0, ("idle",))],
                "look": [(0.0, (0, -2.0, 1.55), 0.2), (0.4, (-0.1, door_y, 1.55), 0.6), (1.2, (-0.1, door_y, 1.6), 0.5), (1.6, (0, -2.0, 1.55), 0.2)],
                "events": [{"frame": 16, "do": "sfx", "name": "knock"}, {"frame": 23, "do": "sfx", "name": "knock"},
                           {"frame": 30, "do": "sfx", "name": "knock"}],
            }
            return self.perform("Knock_Door", 48, self.idle_base(), spec, kind="action",
                                note="three knocks with the right fist on a door 0.50 m in front of the courier (knuckles touch at frames 16, 23, 30)",
                                door_distance_m=round(-door_y, 3), contact_frames=[16, 23, 30])

        def doorbell(self):
            bell = (-0.30, -0.47, 1.24)
            d, n = (-0.12, -0.98, 0.10), (0.15, 0.0, -1.0)
            pf = lambda p: ("world", (p, d, n, "tip"), "point", (-0.8, 0.35, -0.5))
            out = (bell[0], bell[1] + 0.06, bell[2])
            press = (bell[0], bell[1] - 0.006, bell[2])
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.5, (-0.01, -0.01, -0.003)), (0.9, (-0.01, -0.01, -0.003)), (1.3, (0, 0, 0))]),
                "twist": Keys([(0.0, 0.0), (0.45, -8.0), (0.85, -8.0), (1.3, 0.0)]),
                "hand_Right": [(0.0, ("idle",)), (0.36, pf(out)), (0.48, pf(press), "stop"), (0.66, pf(press), "stop"), (0.80, pf(out)), (1.3, ("idle",), "stop")],
                "hand_Left": [(0.0, ("idle",))],
                "look": [(0.0, (0, -2.0, 1.55), 0.2), (0.3, bell, 0.7), (0.8, bell, 0.6), (1.3, (0, -2.0, 1.55), 0.2)],
                "events": [{"frame": 15, "do": "sfx", "name": "doorbell"}],
            }
            return self.perform("Press_Doorbell", 39, self.idle_base(), spec, kind="action",
                                note="the right index finger presses a doorbell button beside the door (0.30 m to the right, 0.47 m ahead, 1.24 m high), pressed frames 14-20",
                                button_courier_root=[round(-bell[0], 3), round(bell[2], 3), round(bell[1], 3)])

        def wave(self):
            c = Vector((-0.48, -0.22, 1.70))
            keys = [(0.0, ("idle",))]
            for i, t in enumerate((0.42, 0.62, 0.82, 1.02, 1.22, 1.42)):
                s = 1 if i % 2 == 0 else -1
                p = c + Vector((0.08 * s, 0.0, -0.012))
                dd = (0.38 * s - 0.1, -0.15, 1.0)
                keys.append((t, ("ref", (tuple(p), dd, (0.05, -1.0, 0.05), "flat"), "open", (-1.0, 0.15, -0.6))))
            keys.append((2.0, ("idle",), "stop"))
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.5, (0.012, 0, -0.003)), (1.5, (0.012, 0, -0.003)), (2.0, (0, 0, 0))]),
                "side": Keys([(0.0, 0.0), (0.5, 3.0), (1.5, 3.0), (2.0, 0.0)]),
                "hand_Right": keys,
                "hand_Left": [(0.0, ("idle",))],
                "look": [(0.0, (0, -3.0, 1.6), 0.3), (2.0, (0, -3.0, 1.6), 0.3)],
                "events": [],
            }
            return self.perform("Wave", 60, self.idle_base(), spec, kind="action",
                                note="friendly wave with the right hand raised beside the head (three side-to-side swings), arm comes back down")

        def look_back(self):
            spec = {
                "hips": Keys([(0.0, (0, 0, 0)), (0.6, (0.01, 0.0, -0.003)), (1.5, (0.01, 0.0, -0.003)), (2.2, (0, 0, 0))]),
                "yaw": Keys([(0.0, 0.0), (0.6, 10.0), (1.5, 10.0, "stop"), (2.2, 0.0)]),
                "twist": Keys([(0.0, 0.0), (0.6, 26.0), (1.5, 26.0, "stop"), (2.2, 0.0)]),
                "hand_Left": [(0.0, ("idle",))], "hand_Right": [(0.0, ("idle",))],
                "look": [(0.0, (0, -3.0, 1.6), 0.0), (0.6, (2.2, 2.4, 1.55), 1.0), (1.5, (2.2, 2.4, 1.55), 1.0), (2.2, (0, -3.0, 1.6), 0.0)],
                "events": [],
            }
            return self.perform("Look_Back", 66, self.idle_base(), spec, kind="action",
                                note="shoulder check over the left shoulder while standing (feet planted), back to the front")

    return V3Bag


# --------------------------------------------------------------------------- work stage
def phone_frame(C, side="Right"):
    """Phone transform in the hand bone's frame (see phone_track)."""
    h0, p0, L = C.hand_frame(side)
    R = C.rig.rest_rot[side + "Hand"]
    hl, pl = R.inverted() @ h0, R.inverted() @ p0
    yl = pl.cross(hl).normalized()
    F = Matrix((hl, yl, pl)).transposed().to_4x4()
    F.translation = hl * (L + 0.045 - 0.0375) + pl * 0.017
    return F


def phone_track(C, poses, side="Right"):
    """Phone in a one-hand grip: its back on the palm and the proximal phalanges, its long edge
    under the middle finger joints (the fingers bend round it), the screen facing out of the palm
    (towards the eyes when the palm faces up / in); long axis along the knuckle line."""
    h0, p0, L = C.hand_frame(side)
    R = C.rig.rest_rot[side + "Hand"]
    hl, pl = R.inverted() @ h0, R.inverted() @ p0
    yl = pl.cross(hl).normalized()
    # phone frame (asset: x = width, y = length, z = screen normal) in hand-local axes
    F = Matrix((hl, yl, pl)).transposed().to_4x4()
    F.translation = hl * (L + 0.045 - 0.0375) + pl * 0.017
    out = []
    for P in poses:
        W = C.rig.fk(P)
        M = W[side + "Hand"]
        out.append(Matrix.Translation(M.to_translation()) @ M.to_quaternion().to_matrix().to_4x4() @ F)
    return out


def work_stage():
    t0 = time.time()
    lib = load_library()
    jog = load_jog(lib["dirs"])
    walk = load_gaits(WALK_BLEND, ["Walk_Loop"])["Walk_Loop"]
    runs = load_gaits(RUN_BLEND, ["Jog_Loop", "Run_Loop", "Sprint_Loop"]) if os.path.exists(RUN_BLEND) else {}
    ext = load_ext(lib["dirs"])
    arm, mesh, info = load_character(lib)
    C = V3Clips(arm, mesh, lib, {"jog": jog, "walk": walk, "runs": runs, "ext": ext})
    C.orig_rest = info["orig_rest"]           # the MPFB A-pose rest (pelvis pitch reference)
    C.crank_tracks = {}
    R = C.library_clips()
    if not C.src.get("runs"):
        C.mixamo_jog()
    C.strafe(R, +1)
    C.strafe(R, -1)
    C.turn(R, +1)
    C.turn(R, -1)
    C.idle_shift(R)
    C.land_hard(R)
    C.bike_clips(R)
    C.bike_extras()
    C.ext_clips(R)
    # phone raise / lower around the library phone loop
    phone = R["Phone_Use_Loop"]
    C.transition("Phone_Raise", R["Idle"][0], phone[0], 0.7, note="Idle -> Phone_Use: the phone comes up to reading height (phone visible from frame 6)",
                 events=[{"frame": 6, "do": "phone", "visible": True}])
    C.transition("Phone_Lower", phone[0], R["Idle"][0], 0.7, note="Phone_Use -> Idle: the phone goes back to the pocket (hidden from frame 16)",
                 events=[{"frame": 16, "do": "phone", "visible": False}])
    cb = bag_module(C)
    V3Bag = make_bag_class(cb)
    BW = V3Bag(C, R)
    BW.run()
    log("work: %d clips in %.0f s" % (len(C.out), time.time() - t0))
    # ---- collect
    rig = C.rig
    names = list(rig.order)
    clips = []
    for name, poses, meta in C.out:
        Ws = [rig.fk(P) for P in poses]
        Wa = np.array([[[list(r) for r in W[n]] for n in names] for W in Ws], np.float64)
        props = {}
        if name in BW.clips:
            rec = BW.clips[name]
            fr = rec["frames"]
            if fr[0]["bag"] is not None:
                props["bag"] = [[list(r) for r in f["bag"]] for f in fr]
                props["flap"] = list(rec["flap"])
            if fr[0]["pkg"] is not None:
                props["pkg"] = [[list(r) for r in f["pkg"]] for f in fr]
            props["events"] = rec["events"]
        if name in C.crank_tracks:
            props["crank"] = C.crank_tracks[name]
        if name.startswith("Phone"):
            side = getattr(C, "phone_side", {}).get(name, "Right")
            props["phone"] = [[list(r) for r in M] for M in phone_track(C, poses, side)]
        worn = [[list(r) for r in BW.worn(W)] for W in Ws]
        props["worn"] = worn
        clips.append({"name": name, "meta": meta, "W": Wa, "props": props})
    strap = {}
    for side, ob in BW.strap_objs.items():
        me = ob.data
        co = np.array([v.co[:] for v in me.vertices])
        faces = [list(p.vertices) for p in me.polygons]
        gname = {g.index: g.name for g in ob.vertex_groups}
        wts = [[(gname[g.group], g.weight) for g in v.groups] for v in me.vertices]
        strap[side] = {"co": co, "faces": faces, "weights": wts, "name": ob.name}
    data = {
        "bones": names, "clips": clips, "straps": strap,
        "rest_work": {n: [list(r) for r in rig.rest[n]] for n in names},
        "contacts": {s: {k: list(v) for k, v in c.items() if k != "_world"} for s, c in C.contacts.items()},
        "bag_O": [list(r) for r in BW.O], "bag_O_plain": [list(r) for r in BW.O_plain], "bag_meta": BW.bag_meta,
        "bike": {"seat": list(C.bike["Seat"]), "crank": list(C.bike["Crank"]), "hips": list(C.bike_hips), "lean": C.bike_lean,
                 "trunk": C.trunk, "crank_len": C.bike["crank_len"], "knees": C.knees, "fd": {k: (list(v) if isinstance(v, Vector) else v) for k, v in C.fd.items()}},
        "info": {"height": info["height"], "zshift": info["zshift"]},
    }
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump(data, f, protocol=4)
    log("work cache written:", CACHE, "%.1f MB" % (os.path.getsize(CACHE) / 1e6))
    return data


# --------------------------------------------------------------------------- final stage
def M4(a):
    return Matrix([list(r) for r in a])


def find_rig(rig_name):
    """The rig by name, else the file's only armature (a rebuilt file may carry 'Courier.001')."""
    arm = bpy.data.objects.get(rig_name)
    if arm is None:
        arms = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name.split(".")[0] == rig_name] or                [o for o in bpy.data.objects if o.type == 'ARMATURE']
        arm = arms[0]
        log("rig '%s' not found, using '%s' (renamed to '%s')" % (rig_name, arm.name, rig_name))
        arm.name = rig_name
    return arm


def open_rig(path, rig_name):
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    arm = find_rig(rig_name)
    set_action(arm, None)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return arm


def clip_bases(arm, rigo, Wa, bone_names):
    """World matrices (profile names, per frame) -> local bases of the MPFB rig."""
    Ainv = arm.matrix_world.inverted()
    idx = {n: i for i, n in enumerate(bone_names)}
    out, resid = [], 0.0
    for f in range(Wa.shape[0]):
        Wo, B = {}, {}
        for bn in rigo.order:
            prof = TO_PROFILE.get(bn)
            p = rigo.parent[bn]
            base = (Wo[p] @ rigo.rel[bn]) if p else rigo.rel[bn]
            if prof is None or prof == "Root" or prof not in idx:
                b = Matrix.Identity(4)
            else:
                tgt = Ainv @ M4(Wa[f, idx[prof]])
                b = base.inverted() @ tgt
                if prof != "Hips":
                    resid = max(resid, b.translation.length)
                    b.translation = Vector((0, 0, 0))
            B[bn] = b
            Wo[bn] = base @ b
        out.append(B)
    return out, resid


def write_bases(arm, rigo, name, bases):
    act = bpy.data.actions.get(name)
    if act:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    set_action(arm, act)
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    n = len(bases)
    for b in rigo.order:
        if b == "Root":
            continue
        quats, prev = [], None
        for B in bases:
            q = B[b].to_quaternion()
            if prev is not None and prev.dot(q) < 0:
                q = -q
            quats.append(q)
            prev = q
        chans = [("rotation_quaternion", 4, [[q[i] for q in quats] for i in range(4)])]
        if b == "pelvis":
            locs = [B[b].to_translation() for B in bases]
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


def build_straps(data, arm, prefix=""):
    """Strap meshes from the working rest (library rest) to the original rest: each vertex follows
    its bones rigidly (M_b = rest_orig[b] @ rest_work[b]^-1, skinned blend)."""
    rest_w = {n: M4(m) for n, m in data["rest_work"].items()}
    rest_o = {TO_PROFILE[b.name]: arm.matrix_world @ b.matrix_local for b in arm.data.bones}
    Mb = {n: rest_o[n] @ rest_w[n].inverted() for n in rest_w if n in rest_o}
    objs = []
    for side, s in data["straps"].items():
        co = s["co"]
        new = []
        for v, ws in zip(co, s["weights"]):
            acc = Vector()
            tot = 0.0
            for g, w in ws:
                if g in Mb:
                    acc += (Mb[g] @ Vector(v)) * w
                    tot += w
            new.append(acc / tot if tot > 0 else Vector(v))
        me = bpy.data.meshes.new(prefix + s["name"])
        me.from_pydata([tuple(p) for p in new], [], s["faces"])
        for p in me.polygons:
            p.use_smooth = True
        mat = bpy.data.materials.get("Courier_Strap") or bpy.data.materials.new("Courier_Strap")
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
        bsdf.inputs["Roughness"].default_value = 0.78
        mat.diffuse_color = (0.03, 0.03, 0.034, 1)
        me.materials.append(mat)
        ob = bpy.data.objects.new(prefix + s["name"], me)
        ob["hidden_by_default"] = True             # glTF node extras: shown only with the worn backpack
        ob["show_with"] = "worn_backpack"
        coll = arm.users_collection[0]
        coll.objects.link(ob)
        groups = {}
        for vi, ws in enumerate(s["weights"]):
            for g, w in ws:
                mg = MPFB.get(g, g)
                if mg not in groups:
                    groups[mg] = ob.vertex_groups.new(name=mg)
                groups[mg].add([vi], w, 'REPLACE')
        ob.parent = arm
        ob.matrix_parent_inverse = arm.matrix_world.inverted()
        md = ob.modifiers.new("Armature", 'ARMATURE')
        md.object = arm
        objs.append(ob)
    return objs


def godot_dir(v):
    return [round(-v[0], 3), round(v[2], 3), round(v[1], 3)]


def contact_points(Wa, bone_names, contacts):
    idx = {n: i for i, n in enumerate(bone_names)}
    out = []
    for f in range(Wa.shape[0]):
        fr = {}
        for s in ("Left", "Right"):
            M = M4(Wa[f, idx[s + "Foot"]])
            Mt = M4(Wa[f, idx[s + "Toes"]])
            fr[s] = {"heel": M @ Vector(contacts[s]["heel"]), "ball": M @ Vector(contacts[s]["ball"]), "tip": Mt @ Vector(contacts[s]["tip"])}
        out.append(fr)
    return out


def footsteps(C, loop, ground=0.025):
    n = len(C) - (1 if loop else 0)
    ev = []
    for s in ("Left", "Right"):
        down = [min(C[i][s]["heel"].z, C[i][s]["ball"].z) < ground for i in range(n)]
        for i in range(n):
            if down[i] and not down[i - 1 if (loop or i > 0) else i]:
                ev.append({"frame": i, "do": "footstep", "foot": s.lower()})
    return sorted(ev, key=lambda e: e["frame"])


def clip_json(data):
    """The clips JSON (assets/player/clips.json style) from the cache."""
    import courier_bag as cb
    out = {}
    for c in data["clips"]:
        name, meta, props = c["name"], dict(c["meta"]), c["props"]
        g = game_name(name)
        m = {"length": meta["length"], "frames": meta["frames"], "fps": FPS, "loop": meta["loop"], "kind": meta["kind"],
             "source": meta.get("source"), "action": action_name(name)}
        if meta.get("note"):
            m["note"] = meta["note"]
        if meta["kind"] == "locomotion":
            ax = Vector(meta.get("axis", (0, 1, 0)))
            m["speed"] = meta.get("speed", 0.0)
            m["speed_cm_s"] = round(meta.get("speed", 0.0) * 100, 1)
            m["move_direction"] = godot_dir(-ax) if meta.get("speed") else [0, 0, 0]
            m["foot_slide_m"] = meta.get("slide_m")
            m["side_slip_m"] = meta.get("side_slip_m")
            m["stances"] = meta.get("stances")
        m["root_motion"] = meta.get("root_motion", "in_place")
        if "root_yaw_deg" in meta:
            m["root_motion"] = "root_yaw_curve"
        for k in ("root_yaw_deg", "root_yaw_curve", "root_yaw_samples_30fps", "crank_deg_per_s", "hips_bike_space_godot",
                  "knee_flexion_min_deg", "knee_flexion_max_deg", "package_release_frame", "package_grab_frame", "bag_variant_of",
                  "contact_frames", "door_distance_m", "seat_height_m", "hips_courier_root", "hands_mid_courier_root", "end_offset_courier_root", "root_motion_samples_30fps", "release_frame", "release_hand", "takeoff_frame", "touchdown_frame", "pelvis_pitch_dev_deg", "pelvis_pitch_dev_range_deg", "shoulders_over_hips_cm", "head_ahead_cm", "head_pitch_deg", "thoracic_flex_deg", "button_courier_root", "end_offset_bike_space_godot", "root_motion_removed_m", "cycle_time_scale"):
            if k in meta:
                m[k] = meta[k]
        ev = list(meta.get("events", [])) + list(props.get("events", []))
        if meta["kind"] in ("locomotion",):
            Cp = contact_points(c["W"], data["bones"], data["contacts"])
            ev += footsteps(Cp, meta["loop"], 0.035 if g.startswith(("Run", "Sprint", "Jog")) else 0.025)
        if ev:
            m["events"] = sorted(ev, key=lambda e: e["frame"])
        if "bag" in props:
            m["bag_track"] = [cb.to_godot(M4(x)) for x in props["bag"]]
            m["flap_deg"] = [round(x, 1) for x in props["flap"]]
            m["bag_model"] = "res://assets/delivery/delivery_bag_open.glb"
        if "pkg" in props:
            m["package_track"] = [cb.to_godot(M4(x)) for x in props["pkg"]]
            m["package_box"] = [round(cb.PKG.x, 3), round(cb.PKG.z, 3), round(cb.PKG.y, 3)]
        if "phone" in props:
            m["phone_track"] = [cb.to_godot(M4(x)) for x in props["phone"]]
            m["phone_box"] = [0.075, 0.009, 0.155]
        if "crank" in props and meta["kind"] == "bike":
            m["crank_rad"] = [round(float(a), 4) for a in props["crank"]]
        if g == "Bag_Hold":
            m["bag_socket"] = "track"
        out[g] = m
    return out


def final_stage(data, qa=True, qa_only=False, only=None):
    import courier_bag as cb
    cb.bind(globals())
    arm = open_rig(EXPORT_COPY, "Courier")
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("EXP_")]
    for o in list(bpy.data.objects):
        if o is not arm and o not in meshes:
            bpy.data.objects.remove(o)
    repair_unweighted(meshes, arm)
    rigo = Rig(arm)
    worst = 0.0
    t0 = time.time()
    for c in data["clips"]:
        bases, resid = clip_bases(arm, rigo, c["W"], data["bones"])
        worst = max(worst, resid)
        write_bases(arm, rigo, action_name(c["name"]), bases)
    log("actions written (%d) in %.0f s; child-bone translation residual %.5f m" % (len(data["clips"]), time.time() - t0, worst))
    straps = build_straps(data, arm)
    set_action(arm, None)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    clips = clip_json(data)
    if not qa_only:
        os.makedirs(OUT_DIR, exist_ok=True)
        # same settings as prepare_player.export_rigged, but the textures stay PNG like courier_v3.glb
        select_only([arm] + meshes + straps, arm)
        bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
                                  export_animations=True, export_skins=True, export_def_bones=False, export_morph=False,
                                  export_image_format='AUTO', export_materials='EXPORT', export_extras=True,
                                  export_animation_mode='ACTIONS', export_force_sampling=True, export_frame_step=1,
                                  export_optimize_animation_size=False)
        log("wrote", OUT_GLB, "%.2f MB" % (os.path.getsize(OUT_GLB) / 1e6))
        V = np.concatenate([mesh_np(o) for o in meshes])
        info = {
            "model": "source_assets/character_mpfb/export/courier_v3_animated.glb",
            "source_blend": "source_assets/character_mpfb/courier_v3_animated.blend",
            "pipeline": "tools/prepare_courier_v3.py",
            "facing": "Blender -Y / Godot +Z inside the GLB (humanoid retarget convention); every track below is in the Courier-root frame of assets/player/clips.json (root faces -Z, model turned PI)",
            "height_m": round(float(V[:, 2].max()), 3), "triangles": tris(meshes), "bones": len(arm.data.bones),
            "skeleton": "MPFB game_engine (53 bones), A-pose rest; bone_map_profile_to_mpfb below for a SkeletonProfileHumanoid BoneMap",
            "bone_map_profile_to_mpfb": {k: v for k, v in MPFB.items()},
            "fps": FPS, "loop_convention": "actions named *_Loop import into Godot as looping clips (suffix removed)",
            "strap_meshes": ["BackpackStrapL", "BackpackStrapR"],
            "bike": {"seat": [round(c, 4) for c in to_godot_bike(Vector(data["bike"]["seat"]))],
                     "hips": [round(c, 4) for c in to_godot_bike(Vector(data["bike"]["hips"]))],
                     "trunk_lean_deg": round(data["bike"]["trunk"], 1), "crank_length": round(data["bike"]["crank_len"], 4),
                     "knees": data["bike"]["knees"], "crank_contract": "Bike_Pedal / Bike_Stand_Pedal: one clip second = one crank revolution, crank rotation.x = -angle; crank_rad per frame for the other bike clips"},
            "backpack": dict(data["bag_meta"], bone="spine_03 (UpperChest)",
                             attach_upperchest_blender=[[round(x, 5) for x in r] for r in data["bag_O"]],
                             attach_upperchest_plain_blender=[[round(x, 5) for x in r] for r in data["bag_O_plain"]]),
            "licences": {
                "UAL": "Quaternius Universal Animation Library (assets/animations/ual): CC0 1.0 public domain, commercial use allowed",
                "Mixamo": "Mixamo Jog Forward (Adobe): free to use in commercial games per the Mixamo / Adobe terms; the raw FBX is not redistributed",
                "authored": "clips authored procedurally in tools/prepare_courier_v3.py / courier_bag.py / prepare_player.py (project-owned)"},
            "clips": clips,
        }
        with open(OUT_JSON, "w") as f:
            json.dump(info, f, indent=1)
        log("json written", OUT_JSON)
        # NLA: one muted track per action so the clips are browsable in the NLA editor
        add_nla(arm)
        bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
        log("saved", OUT_BLEND)
    if qa:
        set_action(arm, None)
        qa_sheets(data, arm, meshes, straps, clips, only)
    if not qa_only:
        master_copy(data)


def add_nla(arm):
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    for act in sorted([a for a in bpy.data.actions if a.use_fake_user], key=lambda a: a.name):
        tr = ad.nla_tracks.new()
        tr.name = act.name
        st = tr.strips.new(act.name, 0, act)
        tr.mute = True
    set_action(arm, bpy.data.actions.get("Idle_Loop"))


def master_copy(data):
    """The editable master with the same actions on its rig (identical rest) -> new file."""
    arm = open_rig(MASTER, "V3_Courier_Rig")
    repair_unweighted([o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers)], arm)
    rigo = Rig(arm)
    for c in data["clips"]:
        bases, _ = clip_bases(arm, rigo, c["W"], data["bones"])
        write_bases(arm, rigo, action_name(c["name"]), bases)
    build_straps(data, arm, prefix="V3_")
    add_nla(arm)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_MASTER, compress=True)
    log("saved", OUT_MASTER)


# --------------------------------------------------------------------------- QA contact sheets
def import_props():
    import courier_bag as cb
    props = {}
    for key, path in (("closed", os.path.join(ROOT, "assets", "delivery", "delivery_bag.glb")),
                      ("open", os.path.join(ROOT, "assets", "delivery", "delivery_bag_open.glb"))):
        new = import_any(path)
        roots = [o for o in new if o.parent is None]
        e = bpy.data.objects.new("QA_" + key, None)
        bpy.context.scene.collection.objects.link(e)
        for r in roots:
            r.parent = e
        by = {o.name.split(".")[0]: o for o in new}
        for o in new:
            if o.type == 'MESH':
                for m in o.data.materials:
                    if m and m.node_tree:
                        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                        if b:
                            c = b.inputs["Base Color"].default_value
                            m.diffuse_color = (c[0], c[1], c[2], 1)
        if by.get("FlapStraps"):
            by["FlapStraps"].hide_render = True
        props[key] = {"root": e, "objs": new, "by": by}
    # bike, turned to face -Y like the courier
    new = import_any(BIKE)
    for r in [o for o in new if o.parent is None]:
        r.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ r.matrix_world
    bpy.context.view_layer.update()
    ob = {o.name.split(".")[0]: o for o in new}
    props["bike"] = {"objs": new, "ob": ob, "crank_rest": ob["Crank"].matrix_world.copy(), "C": ob["Crank"].matrix_world.to_translation(),
                     "pedal_rest": {n: ob[n].matrix_world.copy() for n in ("PedalL", "PedalR")}}
    for o in new:
        if o.type == 'MESH':
            for m in o.data.materials:
                if m and m.node_tree:
                    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                    if b:
                        c = b.inputs["Base Color"].default_value
                        m.diffuse_color = (c[0], c[1], c[2], 1)
    for nm, dims, col in (("QA_pkg", (cb.PKG.x, cb.PKG.y, cb.PKG.z), (0.62, 0.45, 0.26, 1)), ("QA_phone", (0.075, 0.155, 0.009), (0.05, 0.05, 0.06, 1)),
                          ("QA_door", (1.0, 0.05, 2.1), (0.55, 0.35, 0.22, 1)), ("QA_wall", (0.5, 0.05, 2.1), (0.75, 0.73, 0.68, 1)),
                          ("QA_bell", (0.05, 0.02, 0.07), (0.85, 0.85, 0.85, 1))):
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        o = bpy.context.active_object
        o.name = nm
        if nm in ("QA_pkg", "QA_door", "QA_wall"):
            o.data.transform(Matrix.Translation((0, 0, 0.5)))
        o.data.transform(Matrix.Diagonal((dims[0], dims[1], dims[2], 1)))
        if nm == "QA_door":
            o.location = (0.0, -0.525, 0.0)
        elif nm == "QA_wall":
            o.location = (-0.30, -0.515, 0.0)
        elif nm == "QA_bell":
            o.location = (-0.30, -0.48, 1.24)
        o.hide_render = True
        m = bpy.data.materials.new(nm + "_mat")
        m.diffuse_color = col
        o.data.materials.append(m)
        props[nm] = o
    return props


def image_checker_ground(size=30.0, squares=120):
    """Ground with an image checker (Workbench TEXTURE mode shows image textures only):
    25 cm squares, so planted feet can be followed across the frames."""
    g = ground_plane(size)
    px = 1440
    a = (np.indices((px, px)) // (px // squares)).sum(0) % 2
    rgb = np.where(a[..., None] == 0, np.array([0.60, 0.60, 0.58]), np.array([0.40, 0.40, 0.38]))
    arr = np.concatenate([rgb, np.ones((px, px, 1))], -1).astype(np.float32)
    im = bpy.data.images.new("QAChecker", px, px)
    im.pixels.foreach_set(arr.ravel())
    m = g.data.materials[0]
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = im
    tx.interpolation = 'Closest'
    nt.links.new(tx.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = tx
    return g


def pose_crank(props, alpha):
    b = props["bike"]
    cr = b["ob"]["Crank"]
    C = b["C"]
    cr.matrix_world = Matrix.Translation(C) @ Quaternion(LEFT, alpha).to_matrix().to_4x4() @ Matrix.Translation(-C) @ b["crank_rest"]
    bpy.context.view_layer.update()
    for n in ("PedalL", "PedalR"):
        p = b["ob"][n]
        p.matrix_world = Matrix.Translation(p.matrix_world.to_translation()) @ b["pedal_rest"][n].to_3x3().to_4x4()
    bpy.context.view_layer.update()


def show(objs, vis):
    for o in objs:
        if o.type == 'MESH':
            o.hide_render = not vis


def place_bag(props, key, M, flap=None):
    b = props[key]
    b["root"].matrix_world = M
    show(b["objs"], True)
    if b["by"].get("FlapStraps"):
        b["by"]["FlapStraps"].hide_render = True
    for s in ("StrapL", "StrapR"):
        if b["by"].get(s):
            b["by"][s].hide_render = key == "closed"
    if flap is not None and b["by"].get("Flap"):
        fl = b["by"]["Flap"]
        fl.rotation_mode = 'XYZ'
        fl.rotation_euler = (math.radians(flap), 0, 0)


def clip_state(g, events, k):
    st = {"bag": "none", "pkg": True, "phone": False}
    if g.startswith("Bag_") or g.endswith("_Bag") or "_Bag" in g:
        st["bag"] = "back"
    if g in ("Bag_Hold", "Bag_PackItem", "Bag_TakeItem", "Bag_PutOn", "Bag_PutOn_Holding"):
        st["bag"] = "track"
    if g in ("Phone_Use", "Phone_Call"):
        st["phone"] = True
    for e in events:
        if e["frame"] <= k:
            if e["do"] == "bag_socket":
                st["bag"] = e["to"]
            elif e["do"] == "phone":
                st["phone"] = e["visible"]
    return st


CLOSEUPS = [  # (clip, frame or fraction, view direction, target, ortho size)
    ("Phone_Use", 0, (-0.35, -1, 0.45), (-0.05, -0.30, 1.25), 0.55),
    ("Phone_Use", 0, (1, -0.3, 0.2), (-0.05, -0.30, 1.25), 0.55),
    ("Phone_Use", 0, (0.1, 0.35, 1.0), (-0.05, -0.30, 1.25), 0.5),
    ("Knock_Door", 16, (1, 0.25, 0.15), (-0.1, -0.42, 1.38), 0.6),
    ("Knock_Door", 16, (-0.6, 0.6, 0.6), (-0.1, -0.42, 1.38), 0.6),
    ("Press_Doorbell", 17, (1, 0.2, 0.15), (-0.28, -0.40, 1.22), 0.5),
    ("Press_Doorbell", 17, (-0.9, 0.6, 0.4), (-0.28, -0.40, 1.22), 0.5),
    ("Bike_Brake", 29, (-0.5, -1, 0.6), (-0.25, -0.32, 1.0), 0.45),
    ("Bike_Bell", 7, (-0.5, -1, 0.6), (-0.25, -0.32, 1.0), 0.45),
    ("Bike_Pedal", 0, (-0.3, -1, 0.5), (0.0, -0.32, 1.0), 0.8),
    ("Bike_Seated", 0, (1, -0.4, 0.15), (0.15, 0.1, 0.35), 1.0),
    ("Carry_Idle", 0, (-0.7, -0.8, 0.5), (0.0, -0.3, 1.0), 0.75),
    ("PickUp", 20, (1, -0.5, 0.3), (0.0, -0.3, 0.3), 0.9),
    ("Wave", 0.4, (-0.3, -1, 0.2), (-0.3, -0.1, 1.5), 0.9),
    ("Idle", 0, (-0.3, -1, 0.1), (0.0, 0.0, 0.95), 2.1),
    ("Idle", 0, (0.0, 1, 0.12), (0.0, 0.05, 1.32), 0.75),
    ("Idle", 8, (1, 0, 0.04), (0.0, 0.0, 0.93), 2.05),
    ("Idle", 8, (0.0, 1, 0.04), (0.0, 0.0, 0.93), 2.05),
    ("Walk", 8, (1, 0, 0.04), (0.0, 0.0, 0.93), 2.05),
    ("Walk", 8, (0.0, 1, 0.04), (0.0, 0.0, 0.93), 2.05),
    ("Run", 5, (1, 0, 0.04), (0.0, 0.0, 0.93), 2.05),
    ("Run", 5, (0.0, 1, 0.04), (0.0, 0.0, 0.93), 2.05),
    ("Phone_Call", 0, (-0.6, -1, 0.2), (0.0, -0.05, 1.55), 0.55),
    ("Phone_Call", 0, (-1, -0.1, 0.1), (0.0, -0.05, 1.55), 0.55),
    ("Eat_Drink", 30, (-0.6, -1, 0.2), (0.0, -0.05, 1.55), 0.55),
    ("Eat_Drink", 30, (-1, -0.1, 0.1), (0.0, -0.05, 1.55), 0.55),
    ("Walk", 0.25, (0.0, 1, 0.12), (0.0, 0.05, 1.32), 0.75),
    ("Run", 0.25, (0.0, 1, 0.12), (0.0, 0.05, 1.30), 0.8),
    ("Walk", 0.25, (0.7, 0.7, 0.15), (0.0, 0.05, 1.32), 0.75),
]


def qa_sheets(data, arm, meshes, straps, clips, only=None):
    os.makedirs(QA, exist_ok=True)
    props = import_props()
    cam = render_setup(300)
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = 300
    sc.display.shading.color_type = 'TEXTURE'
    image_checker_ground()
    base_loc = arm.location.copy()
    base_rot = arm.rotation_euler.copy()
    by_game = {game_name(c["name"]): c for c in data["clips"]}

    def stage(c, k):
        """Pose clip c at frame k with its props; returns the root offset (locomotion)."""
        name, meta, P = c["name"], c["meta"], c["props"]
        g = game_name(name)
        cj = clips[g]
        set_action(arm, bpy.data.actions[action_name(name)])
        sc.frame_set(k)
        bike = meta["kind"] == "bike"
        speed = cj.get("speed", 0.0) or 0.0
        mdir = Vector(meta.get("axis", (0, 1, 0))) * -1.0
        yaw_s = meta.get("root_yaw_samples_30fps")
        off = mdir * speed * (k / FPS) if meta["kind"] == "locomotion" else Vector()
        yaw = math.radians(yaw_s[min(k, len(yaw_s) - 1)]) if yaw_s else 0.0
        Rw = Matrix.Translation(off) @ Matrix.Rotation(yaw, 4, 'Z')
        arm.location = base_loc + off
        arm.rotation_euler = (base_rot[0], base_rot[1], base_rot[2] + yaw)
        st = clip_state(g, cj.get("events", []), k)
        show(props["closed"]["objs"], False)
        show(props["open"]["objs"], False)
        if st["bag"] == "back":
            place_bag(props, "closed", Rw @ M4(P["worn"][k]), 0.0)
        elif st["bag"] == "track" and "bag" in P:
            place_bag(props, "open", Rw @ M4(P["bag"][k]), P["flap"][k])
        for s in straps:
            s.hide_render = st["bag"] != "back"
        pk = props["QA_pkg"]
        pk.hide_render = "pkg" not in P
        if "pkg" in P:
            pk.matrix_world = Rw @ M4(P["pkg"][k])
        ph = props["QA_phone"]
        ph.hide_render = not ("phone" in P and st["phone"])
        if "phone" in P:
            ph.matrix_world = Rw @ M4(P["phone"][k])
        props["QA_door"].hide_render = g != "Knock_Door"
        props["QA_wall"].hide_render = props["QA_bell"].hide_render = g != "Press_Doorbell"
        show(props["bike"]["objs"], bike)
        if bike:
            cr = P.get("crank")
            pose_crank(props, cr[min(k, len(cr) - 1)] if cr else 0.0)
        bpy.context.view_layer.update()
        return off

    for c in data["clips"]:
        meta = c["meta"]
        g = game_name(c["name"])
        if only and g not in only:
            continue
        n = meta["frames"]
        cnt = 6
        if meta["loop"]:
            idx = sorted(set(int(round(i * n / cnt)) for i in range(cnt)))
        else:
            idx = sorted(set(int(round(i * n / (cnt - 1))) for i in range(cnt)))
        bike = meta["kind"] == "bike"
        squat = g.startswith(("PickUp", "PlaceDown", "Land_Hard", "Sit", "Crouch", "Car", "Open_Box", "Roll", "Get_Up", "Slide", "Hit_"))
        big = g.startswith(("ClimbUp", "Roll", "Slide", "Hit_", "Get_Up", "Throw"))
        views = [("side", (1, 0, 0.08)), ("34", (-0.72, -0.66, 0.28))]
        if bike:
            views = [("side", (1, 0, 0.06)), ("34", (-0.75, -0.62, 0.3))]
        tiles = []
        for vname, d in views:
            for k in idx:
                off = stage(c, k)
                tgt = Vector((0, 0.05, 0.80)) if bike else Vector((0, -0.05, 0.72 if squat else 0.92))
                p = os.path.join(QA, "_tmp_%s_%s_%03d.png" % (g, vname, k))
                shoot(cam, p, d, tgt + off, 2.5 if bike else (3.2 if big else 2.2))
                tiles.append(p)
        compose(tiles, os.path.join(QA, "%s.png" % g), cols=len(idx))
        log("QA sheet", g)
    # close-ups of the contacts (hands on objects, feet on the ground / pedals)
    sc.render.resolution_x = sc.render.resolution_y = 420
    groups = {}
    for clip, fr, d, tgt, o in CLOSEUPS:
        if clip not in by_game or (only and clip not in only):
            continue
        c = by_game[clip]
        n = c["meta"]["frames"]
        k = int(round(fr * n)) if isinstance(fr, float) else min(fr, n)
        off = stage(c, k)
        p = os.path.join(QA, "_tmp_close_%s_%d_%d.png" % (clip, k, len(groups.get(clip, []))))
        shoot(cam, p, d, Vector(tgt) + off, o)
        groups.setdefault(clip, []).append(p)
    for clip, tiles in groups.items():
        compose(tiles, os.path.join(QA, "close_%s.png" % clip), cols=len(tiles))
    arm.location = base_loc
    arm.rotation_euler = base_rot
    set_action(arm, None)


WIP = os.path.join(CHAR, "anims_wip", "courier_v3_anims_wip.blend")


def wip_stage(data):
    """Self-contained WIP file for viewing in the GUI: only the collection ANIM_Courier (rig
    'Courier', EXP_* meshes, backpack straps, the gray bicycle under the empty 'ANIM_Bike' with a
    crank action per bike clip), every clip as an action (fake user) on its own muted NLA track."""
    arm = open_rig(EXPORT_COPY, "Courier")
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("EXP_")]
    for o in list(bpy.data.objects):
        if o is not arm and o not in meshes:
            bpy.data.objects.remove(o)
    repair_unweighted(meshes, arm)
    rigo = Rig(arm)
    for c in data["clips"]:
        bases, _ = clip_bases(arm, rigo, c["W"], data["bones"])
        write_bases(arm, rigo, action_name(c["name"]), bases)
    straps = build_straps(data, arm)
    sc = bpy.context.scene
    coll = bpy.data.collections.new("ANIM_Courier")
    sc.collection.children.link(coll)
    # the bicycle (faces -Y like the courier; bike root = courier root)
    new = import_any(BIKE)
    bike_root = bpy.data.objects.new("ANIM_Bike", None)
    sc.collection.objects.link(bike_root)
    for r in [o for o in new if o.parent is None]:
        r.parent = bike_root
    bike_root.rotation_euler = (0, 0, math.pi)
    bpy.context.view_layer.update()
    crank = next(o for o in new if o.name.split(".")[0] == "Crank")
    crank.rotation_mode = 'QUATERNION'
    q0 = crank.rotation_quaternion.copy()
    l0 = crank.location.copy()
    rest_w = crank.matrix_world.copy()
    Cw = rest_w.to_translation()
    for c in data["clips"]:
        cr = c["props"].get("crank")
        if not cr:
            continue
        act = bpy.data.actions.new(action_name(c["name"]) + "__Crank")
        if not crank.animation_data:
            crank.animation_data_create()
        crank.animation_data.action = act
        if getattr(act, "slots", None) and len(act.slots):
            crank.animation_data.action_slot = act.slots[0]
        for k, a in enumerate(cr):
            crank.matrix_world = Matrix.Translation(Cw) @ Quaternion(LEFT, a).to_matrix().to_4x4() @ Matrix.Translation(-Cw) @ rest_w
            crank.keyframe_insert("rotation_quaternion", frame=k)
            crank.keyframe_insert("location", frame=k)
        act.use_fake_user = True
    if crank.animation_data:
        crank.animation_data.action = None
    crank.rotation_quaternion = q0
    crank.location = l0
    for o in [arm] + meshes + straps + [bike_root] + new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        coll.objects.link(o)
    for o in list(bpy.data.objects):
        if o.name not in coll.objects:
            bpy.data.objects.remove(o)
    for ch in list(sc.collection.children):
        if ch is not coll:
            sc.collection.children.unlink(ch)
    for cl in list(bpy.data.collections):
        if cl is not coll and cl.users == 0:
            bpy.data.collections.remove(cl)
    add_nla(arm)
    sc.frame_start, sc.frame_end = 0, 75
    os.makedirs(os.path.dirname(WIP), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=WIP, compress=True)
    log("WIP saved", WIP, "clips:", ",".join(game_name(c["name"]) for c in data["clips"]))


# --------------------------------------------------------------------------- main
def main():
    stage = next((a for a in ARGS if not a.startswith("--")), "all")
    only = None
    for a in ARGS:
        if a.startswith("--clips="):
            only = set(a.split("=", 1)[1].split(","))
    qa = "--no-qa" not in ARGS
    if stage in ("all", "work"):
        data = work_stage()
    if stage == "wip":
        with open(CACHE, "rb") as f:
            data = pickle.load(f)
        wip_stage(data)
    if stage in ("all", "final"):
        if stage == "final":
            with open(CACHE, "rb") as f:
                data = pickle.load(f)
        final_stage(data, qa=qa, qa_only="--qa-only" in ARGS, only=only)
    log("done")


main()
