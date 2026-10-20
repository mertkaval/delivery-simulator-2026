"""Prepare the downloaded Sketchfab characters as retargetable humanoids for the game.

blender --background --factory-startup --python tools/prepare_characters.py -- [id ...]

ids: casual_male_tshirt business_man_eric sophia casual_female casual_male_2 cyclist_woman
     (no ids = all).  Add "noqa" to skip the QA renders.

Walking characters -> assets/sketchup/people/<id>.glb
  * one armature object at the scene root (unit transform, rest applied), skinned meshes as
    its children, metres, feet on z=0, Hips over the origin, facing Blender +Y (Godot -Z);
  * skeleton uses Godot SkeletonProfileHumanoid names (Root -> Hips -> ...); helper bones
    (twist, face) are kept with their source names, unweighted "_end"/tip bones removed;
  * <= 15k triangles, textures <= 1024 px, no animation except Sophia's "Idle";
  * the two unrigged scans get a fitted humanoid skeleton + automatic weights.
Cyclist -> assets/sketchup/people/cyclist_woman.glb: static prop, <= 25k triangles, bicycle
  pointing +Y, wheels on the ground, origin under the bicycle centre; wheels split under
  WheelFront / WheelRear empties (spin about local X) when they are separate loose parts.
assets/sketchup/people/humanoids.json lists the humanoids; QA renders go to people/qa/.
"""
import bpy, bmesh, sys, os, math, json, re
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sketchup_assets")
OUT = os.path.join(ROOT, "assets", "sketchup", "people")
QA = os.path.join(OUT, "qa")
JSON_PATH = os.path.join(OUT, "humanoids.json")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_QA = "noqa" not in ARGS
ONLY = [a for a in ARGS if a != "noqa"]
MAX_TRIS = 15000
TEX_MAX = 1024

CHARACTERS = [
    # id, source, kind, rig
    ("casual_male_tshirt", "casual_male_3d_character__t-pose.glb", "mixamo"),
    ("business_man_eric", "eric_rigged_001_-_rigged_3d_business_man.glb", "renderpeople"),
    ("sophia", "sophia_animated_003_-_animated_3d_woman.glb", "renderpeople"),
    ("casual_female", "female_character_with_casual_clothing.glb", "unrigged"),
    ("casual_male_2", "male_character_in_caual_clothing.glb", "unrigged"),
]

HUMANOID = ["Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftEye", "RightEye",
            "Jaw"]
FINGERS = [("Thumb", ["Metacarpal", "Proximal", "Distal"]), ("Index", ["Proximal", "Intermediate", "Distal"]),
           ("Middle", ["Proximal", "Intermediate", "Distal"]), ("Ring", ["Proximal", "Intermediate", "Distal"]),
           ("Little", ["Proximal", "Intermediate", "Distal"])]
for _s in ("Left", "Right"):
    HUMANOID += [_s + n for n in ("Shoulder", "UpperArm", "LowerArm", "Hand")]
    HUMANOID += [_s + f + p for f, ps in FINGERS for p in ps]
    HUMANOID += [_s + n for n in ("UpperLeg", "LowerLeg", "Foot", "Toes")]
HUMANOID_SET = set(HUMANOID)


# ----------------------------------------------------------------------------- helpers
def log(*a):
    print("[prep]", *a, flush=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load(name):
    reset()
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, name))
    for o in list(bpy.data.objects):
        if o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o)


def tris(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == 'MESH')


def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def verts_np(objs):
    chunks = []
    for o in objs:
        if o.type != 'MESH' or not o.data.vertices:
            continue
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(o.matrix_world)
        chunks.append(co @ m[:3, :3].T + m[:3, 3])
    return np.concatenate(chunks)


def flatten(keep):
    """Bake every object's world transform into its data, unparent, delete everything else."""
    for o in keep:
        mw = o.matrix_world.copy()
        o.parent = None
        if o.type == 'MESH':
            o.data.transform(mw)
        elif o.type == 'ARMATURE':
            o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o)


def apply_global(objs, M):
    for o in objs:
        o.data.transform(M)


def action_fcurves(a):
    if hasattr(a, "fcurves") and len(a.fcurves):
        return list(a.fcurves)
    out = []
    for layer in getattr(a, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def scale_location_curves(scale):
    for a in bpy.data.actions:
        for f in action_fcurves(a):
            if f.data_path.endswith(".location") or f.data_path == "location":
                for k in f.keyframe_points:
                    k.co[1] *= scale
                    k.handle_left[1] *= scale
                    k.handle_right[1] *= scale


def clean_mesh(o, merge=1e-5):
    """Weld split seams (glTF import splits at UV/normal seams), drop custom normals, smooth."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    bm.to_mesh(o.data)
    bm.free()
    select_only([o])
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except RuntimeError:
        pass
    o.data.shade_smooth()


def decimate(o, target, symmetric=True):
    cur = tris([o])
    if cur <= target:
        return
    select_only([o])
    m = o.modifiers.new("Decimate", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = max(0.001, target / cur)
    m.use_collapse_triangulate = True
    if symmetric:
        m.use_symmetry = True
        m.symmetry_axis = 'X'
    bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)
    bpy.ops.object.modifier_apply(modifier=m.name)


def downsize_images(objs, maxpx=TEX_MAX):
    seen = set()
    for o in objs:
        if o.type != 'MESH':
            continue
        for mat in o.data.materials:
            if not mat or not mat.node_tree:
                continue
            for n in mat.node_tree.nodes:
                im = getattr(n, "image", None)
                if n.type == 'TEX_IMAGE' and im and im.name not in seen:
                    seen.add(im.name)
                    w, h = im.size
                    if max(w, h) > maxpx:
                        f = maxpx / max(w, h)
                        im.scale(max(1, int(w * f)), max(1, int(h * f)))
                        log("  image", im.name, (w, h), "->", tuple(im.size))


def merge_trivial_materials(objs):
    """Merge materials whose node trees use the same images and identical settings."""
    def sig(mat):
        if not mat or not mat.node_tree:
            return None
        imgs = []
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                for l in n.outputs[0].links:
                    imgs.append((l.to_node.type, l.to_socket.identifier, n.image.name))
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        vals = []
        if bsdf:
            for key in ("Base Color", "Metallic", "Roughness", "Alpha"):
                s = bsdf.inputs.get(key)
                if s is not None and not s.is_linked:
                    v = s.default_value
                    vals.append(tuple(round(x, 3) for x in v) if hasattr(v, "__len__") else round(v, 3))
        return (tuple(sorted(imgs)), tuple(vals), getattr(mat, "blend_method", None))
    first = {}
    merged = []
    for o in objs:
        if o.type != 'MESH':
            continue
        for slot in o.material_slots:
            s = sig(slot.material)
            if s is None or not s[0]:
                continue
            if s in first and first[s] is not slot.material:
                merged.append((slot.material.name, first[s].name))
                slot.material = first[s]
            else:
                first.setdefault(s, slot.material)
    for a, b in merged:
        log("  merged material", a, "->", b)
    for o in objs:   # collapse duplicate slots inside one object
        if o.type == 'MESH' and len(o.material_slots) > 1:
            select_only([o])
            try:
                bpy.ops.object.material_slot_remove_unused()
            except RuntimeError:
                pass
    return merged


def join(parts, name):
    if len(parts) > 1:
        select_only(parts, parts[0])
        bpy.ops.object.join()
    parts[0].name = name
    parts[0].data.name = name
    return parts[0]


def weighted_groups(meshes, eps=1e-4):
    used = set()
    for o in meshes:
        names = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            for g in v.groups:
                if g.weight > eps:
                    used.add(names[g.group])
    return used


def limit_and_normalize(mesh):
    select_only([mesh])
    bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_DEFORM', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)


def fix_unweighted(mesh, arm):
    """Give vertices without any deform weight the weights of the nearest weighted vertex."""
    deform = {b.name for b in arm.data.bones if b.use_deform}
    idx2name = {g.index: g.name for g in mesh.vertex_groups}
    weighted, unweighted = [], []
    for v in mesh.data.vertices:
        tot = sum(g.weight for g in v.groups if idx2name[g.group] in deform)
        (weighted if tot > 1e-4 else unweighted).append(v.index)
    if not unweighted:
        return 0
    log("  vertices without deform weights after auto weights: %d / %d" % (len(unweighted), len(mesh.data.vertices)))
    if len(weighted) < 0.5 * len(mesh.data.vertices):
        # bone heat largely failed: weight every vertex from its distance to the bone segments
        distance_weights(mesh, arm)
        return len(mesh.data.vertices)
    kd = KDTree(len(weighted))
    for i in weighted:
        kd.insert(mesh.data.vertices[i].co, i)
    kd.balance()
    groups = {g.name: g for g in mesh.vertex_groups}
    for i in unweighted:
        _, j, _ = kd.find(mesh.data.vertices[i].co)
        for g in mesh.data.vertices[j].groups:
            n = idx2name[g.group]
            if n in deform and g.weight > 1e-4:
                groups[n].add([i], g.weight, 'REPLACE')
    return len(unweighted)


def distance_weights(mesh, arm):
    """Envelope-style fallback: blend the two nearest deform bone segments (1/d^4)."""
    bones = [b for b in arm.data.bones if b.use_deform]
    co = np.array([v.co[:] for v in mesh.data.vertices])
    D = np.empty((len(co), len(bones)))
    for j, b in enumerate(bones):
        a = np.array(b.head_local[:]); ab = np.array(b.tail_local[:]) - a
        t = np.clip(((co - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        D[:, j] = np.linalg.norm(co - (a + t[:, None] * ab), axis=1)
    for g in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(g)
    groups = {b.name: mesh.vertex_groups.new(name=b.name) for b in bones}
    order = np.argsort(D, axis=1)[:, :2]
    for i in range(len(co)):
        j0, j1 = order[i]
        w0, w1 = 1 / max(D[i, j0], 1e-4) ** 4, 1 / max(D[i, j1], 1e-4) ** 4
        if D[i, j1] > 1.6 * D[i, j0]:
            w1 = 0.0
        tot = w0 + w1
        groups[bones[j0].name].add([i], w0 / tot, 'REPLACE')
        if w1 > 0:
            groups[bones[j1].name].add([i], w1 / tot, 'REPLACE')


# ----------------------------------------------------------------------------- bone maps
MIXAMO = {"_rootJoint": "Root", "Hips": "Hips", "Spine": "Spine", "Spine1": "Chest", "Spine2": "UpperChest",
          "Neck": "Neck", "Head": "Head", "LeftEye": "LeftEye", "RightEye": "RightEye"}
RP = {"root": "Root", "hip": "Hips", "spine_01": "Spine", "spine_02": "Chest", "spine_03": "UpperChest",
      "neck": "Neck", "head": "Head", "jaw": "Jaw", "eye_l": "LeftEye", "eye_r": "RightEye"}
for side, s in (("Left", "l"), ("Right", "r")):
    MIXAMO.update({side + "Shoulder": side + "Shoulder", side + "Arm": side + "UpperArm",
                   side + "ForeArm": side + "LowerArm", side + "Hand": side + "Hand",
                   side + "UpLeg": side + "UpperLeg", side + "Leg": side + "LowerLeg",
                   side + "Foot": side + "Foot", side + "ToeBase": side + "Toes"})
    RP.update({"shoulder_" + s: side + "Shoulder", "upperarm_" + s: side + "UpperArm",
               "lowerarm_" + s: side + "LowerArm", "hand_" + s: side + "Hand",
               "upperleg_" + s: side + "UpperLeg", "lowerleg_" + s: side + "LowerLeg",
               "foot_" + s: side + "Foot", "ball_" + s: side + "Toes"})
    for (f, parts), mx, rp in zip(FINGERS, ("Thumb", "Index", "Middle", "Ring", "Pinky"),
                                  ("thumb", "index", "middle", "ring", "pinky")):
        for i, p in enumerate(parts):
            MIXAMO["%sHand%s%d" % (side, mx, i + 1)] = side + f + p
            RP["%s_%02d_%s" % (rp, i + 1, s)] = side + f + p

RP_PREFIX = re.compile(r"^rp_[a-z]+_[a-z]+_\d+_[a-z]+_")


def map_name(name, kind):
    """-> (new_name, is_end_bone)"""
    if kind == "mixamo":
        base = re.sub(r"_\d+$", "", name)
        end = base.lower().endswith("_end") or bool(re.match(r"(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)4$", base))
        return MIXAMO.get(base, name), end
    stripped = RP_PREFIX.sub("", name)
    base = re.sub(r"_\d+$", "", stripped)
    end = "_end" in base or base.startswith("end_")
    if name == "_rootJoint":
        return name, True       # Sketchfab wrapper above root_01
    return RP.get(base, stripped), end


def remap_skeleton(arm, meshes, kind):
    used = weighted_groups(meshes)
    # delete unweighted leaf end bones (and the Sketchfab wrapper joint for Renderpeople)
    select_only([arm])
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    removed = []
    changed = True
    while changed:
        changed = False
        for b in list(eb):
            new, end = map_name(b.name, kind)
            if end and b.name not in used and (not b.children or b.name == "_rootJoint"):
                for c in b.children:
                    c.parent = b.parent
                removed.append(b.name)
                eb.remove(b)
                changed = True
    bpy.ops.object.mode_set(mode='OBJECT')
    # rename (RNA rename also renames vertex groups and animation paths)
    renames = {}
    for b in list(arm.data.bones):
        new, _ = map_name(b.name, kind)
        if new != b.name:
            renames[b.name] = new
    for old, new in renames.items():
        arm.data.bones[old].name = new
    for o in meshes:  # safety: make sure the vertex groups followed
        for g in o.vertex_groups:
            if g.name in renames:
                g.name = renames[g.name]
    log("  removed bones:", len(removed), "renamed:", len(renames))
    return removed, renames


def check_hierarchy(arm):
    b = arm.data.bones
    assert "Hips" in b, "no Hips"
    hp = b["Hips"].parent
    assert hp is None or hp.name == "Root", "Hips parent %s" % hp
    roots = [x.name for x in b if x.parent is None]
    assert roots in (["Root"], ["Hips"]), "roots %s" % roots
    missing = [n for n in HUMANOID if n not in b and n != "Root"]
    return missing


def place_root(arm):
    select_only([arm])
    bpy.ops.object.mode_set(mode='EDIT')
    r = arm.data.edit_bones.get("Root")
    if r:
        r.head = (0, 0, 0)
        r.tail = (0, 0, 0.1)
        r.roll = 0
    bpy.ops.object.mode_set(mode='OBJECT')


def arm_angle(arm):
    """Degrees the left upper arm points below horizontal in the rest pose."""
    b = arm.data.bones["LeftUpperArm"]
    d = (b.tail_local - b.head_local)
    lo = arm.data.bones.get("LeftLowerArm")
    if lo:
        d = lo.head_local - b.head_local
    return math.degrees(math.atan2(-d.z, math.hypot(d.x, d.y)))


# ----------------------------------------------------------------------------- landmarks
def measure(V):
    """Body landmarks of a T/A-posed character facing +Y (left = -X), feet on z=0."""
    H = float(V[:, 2].max())
    m = {"H": H}

    def band(z, dz, cond=None):
        S = V[np.abs(V[:, 2] - z) < dz]
        return S if cond is None else S[cond(S)]

    def mid(S, i):
        return 0.5 * (S[:, i].min() + S[:, i].max())

    left = lambda S: S[:, 0] < -0.005
    thigh = band(0.40 * H, 0.01 * H, left)
    knee = band(0.276 * H, 0.008 * H, left)
    shin = band(0.07 * H, 0.006 * H, left)
    m["thigh"] = (mid(thigh, 0), mid(thigh, 1))
    m["knee"] = (mid(knee, 0), mid(knee, 1))
    m["shin"] = (mid(shin, 0), mid(shin, 1))
    foot = V[(V[:, 2] < 0.04 * H) & (V[:, 0] < -0.005)]
    m["toe_tip"] = float(foot[:, 1].max())
    m["heel"] = float(foot[:, 1].min())
    m["foot_x"] = mid(foot, 0)
    for key, z in (("hips", 0.515), ("spine", 0.603), ("chest", 0.666), ("upperchest", 0.705),
                   ("neck", 0.828), ("head", 0.885), ("headtop", 0.95)):
        S = band(z * H, 0.006 * H, lambda S: np.abs(S[:, 0]) < 0.07 * H)
        m[key] = mid(S, 1)
    # left arm: bins along -X
    A = V[(V[:, 0] < -0.06 * H) & (V[:, 2] > 0.55 * H)]
    x_tip = float(A[:, 0].min())
    step = 0.008 * H
    bins = []
    x = -0.06 * H
    while x - step > x_tip:
        S = A[(A[:, 0] <= x) & (A[:, 0] > x - step)]
        if len(S) >= 3:
            bins.append(dict(x=x - step / 2, zmid=mid(S, 2), ymid=mid(S, 1), zext=float(np.ptp(S[:, 2])),
                             zmin=float(S[:, 2].min()),
                             yext=float(np.ptp(S[:, 1]))))
        x -= step
    # arm thickness from the outer half of the arm; armpit = first (from outside) much thicker bin
    outer = [b for b in bins if b["x"] < 0.5 * (x_tip - 0.15 * H)]
    thick = float(np.median([b["zext"] for b in outer]))
    # armpit = first bin (from the hand inwards) whose geometry reaches far below the arm: the
    # torso side. A loose sleeve is thick but never hangs 0.15 H below the arm centre line.
    arm_z = float(np.median([b["zmid"] for b in outer]))
    armpit = None
    for b in reversed(bins):      # from the hand towards the torso
        if b["x"] > x_tip + 0.2 * H and b["zmin"] < arm_z - 0.15 * H:
            armpit = b["x"]
            break
    if armpit is None:
        armpit = -0.13 * H
    # wrist = narrowest width a hand-length in from the tip
    cand = [b for b in bins if x_tip + 0.065 * H <= b["x"] <= x_tip + 0.14 * H]
    wrist_x = min(cand, key=lambda b: b["yext"])["x"] if cand else x_tip + 0.10 * H
    fit = [b for b in bins if armpit - 0.03 * H > b["x"] > wrist_x]
    xs = np.array([b["x"] for b in fit])
    kz = np.polyfit(xs, [b["zmid"] for b in fit], 1)
    ky = np.polyfit(xs, [b["ymid"] for b in fit], 1)
    line = lambda xx: Vector((xx, float(np.polyval(ky, xx)), float(np.polyval(kz, xx))))
    m.update(x_tip=x_tip, armpit=armpit, wrist_x=wrist_x, arm_thick=thick)
    m["arm_line"] = line
    m["shoulder_pt"] = line(armpit + 0.02 * H)
    m["wrist_pt"] = line(wrist_x)
    m["tip_pt"] = line(x_tip)
    m["hand_len"] = (m["tip_pt"] - m["wrist_pt"]).length
    return m


def template_skeleton():
    """Casual male (Mixamo) skeleton, renamed + facing +Y, with landmarks of its mesh."""
    load(CHARACTERS[0][1])
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    flatten([arm] + meshes)
    apply_global([arm] + meshes, Matrix.Rotation(math.pi, 4, 'Z'))
    remap_skeleton(arm, meshes, "mixamo")
    bones = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in arm.data.bones}
    m = measure(verts_np(meshes))
    return bones, m


# ----------------------------------------------------------------------------- fitted rig
PARENT = {"Hips": "Root", "Spine": "Hips", "Chest": "Spine", "UpperChest": "Chest", "Neck": "UpperChest",
          "Head": "Neck", "LeftEye": "Head", "RightEye": "Head"}
for _s in ("Left", "Right"):
    PARENT.update({_s + "Shoulder": "UpperChest", _s + "UpperArm": _s + "Shoulder",
                   _s + "LowerArm": _s + "UpperArm", _s + "Hand": _s + "LowerArm",
                   _s + "UpperLeg": "Hips", _s + "LowerLeg": _s + "UpperLeg", _s + "Foot": _s + "LowerLeg",
                   _s + "Toes": _s + "Foot"})
    for f, ps in FINGERS:
        prev = _s + "Hand"
        for p in ps:
            PARENT[_s + f + p] = prev
            prev = _s + f + p


def fitted_heads(m, tb, tm):
    """Joint positions for a target with landmarks m from template bones tb / landmarks tm."""
    H = m["H"]
    k = H / tm["H"]
    P = {}
    P["Root"] = Vector((0, 0, 0))
    for name, key, zr in (("Hips", "hips", 0.515), ("Spine", "spine", 0.603), ("Chest", "chest", 0.666),
                          ("UpperChest", "upperchest", 0.705), ("Neck", "neck", 0.828), ("Head", "head", 0.885)):
        P[name] = Vector((0, m[key], zr * H))
    sh = m["shoulder_pt"]
    wr = m["wrist_pt"]
    el = sh.lerp(wr, 0.537)
    hip_x = 0.8 * m["thigh"][0]
    L = {}
    L["UpperLeg"] = Vector((hip_x, m["hips"], 0.5085 * H))
    L["LowerLeg"] = Vector((m["knee"][0], m["knee"][1], 0.276 * H))
    L["Foot"] = Vector((m["shin"][0], m["shin"][1], 0.045 * H))
    flen = m["toe_tip"] - m["heel"]
    L["Toes"] = Vector((m["foot_x"], m["heel"] + 0.74 * flen, 0.02 * H))
    L["UpperArm"] = sh
    L["Shoulder"] = Vector((0.44 * sh.x, sh.y, sh.z - 0.0127 * H))
    L["LowerArm"] = el
    L["Hand"] = wr
    # fingers: template hand frame -> target hand frame
    t_w = tb["LeftHand"][0]
    t_dir = (tb["LeftHand"][0] - tb["LeftLowerArm"][0]).normalized()
    dirv = (wr - el).normalized()
    q = t_dir.rotation_difference(dirv)
    s = m["hand_len"] / tm["hand_len"]
    for f, ps in FINGERS:
        for p in ps:
            n = "Left" + f + p
            L[f + p] = wr + q @ ((tb[n][0] - t_w) * s)
    for n, v in L.items():
        P["Left" + n] = v
        P["Right" + n] = Vector((-v.x, v.y, v.z))
    for side in ("Left", "Right"):
        t = tb[side + "Eye"][0] - tb["Head"][0]
        P[side + "Eye"] = P["Head"] + Vector((t.x * k, t.y * k, t.z * k))
    return P


def build_rig(m, tb, tm, name="Armature"):
    P = fitted_heads(m, tb, tm)
    H = m["H"]
    child = {"Hips": "Spine", "Spine": "Chest", "Chest": "UpperChest", "UpperChest": "Neck", "Neck": "Head"}
    for s in ("Left", "Right"):
        child.update({s + "Shoulder": s + "UpperArm", s + "UpperArm": s + "LowerArm", s + "LowerArm": s + "Hand",
                      s + "Hand": s + "MiddleProximal", s + "UpperLeg": s + "LowerLeg",
                      s + "LowerLeg": s + "Foot", s + "Foot": s + "Toes"})
        for f, ps in FINGERS:
            for a, b in zip(ps, ps[1:]):
                child[s + f + a] = s + f + b
    tails = {}
    for n in P:
        if n in child:
            tails[n] = P[child[n]]
        elif n == "Root":
            tails[n] = Vector((0, 0, 0.1))
        elif n == "Head":
            tails[n] = Vector((0, P[n].y, H))
        elif n.endswith("Eye"):
            tails[n] = P[n] + Vector((0, 0.03, 0))
        elif n.endswith("Toes"):
            tails[n] = Vector((P[n].x, m["toe_tip"], P[n].z))
        else:  # distal finger bones: continue the parent direction
            par = P[PARENT[n]]
            tails[n] = P[n] + (P[n] - par) * 0.8
    ad = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, ad)
    bpy.context.scene.collection.objects.link(arm)
    select_only([arm])
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    order = ["Root"] + [n for n in HUMANOID if n in P and n != "Root"]
    for n in order:
        b = eb.new(n)
        b.head = P[n]
        b.tail = tails[n]
    for n in order:
        b = eb[n]
        if n in PARENT:
            b.parent = eb[PARENT[n]]
            b.use_connect = False
        d = (b.tail - b.head).normalized()
        b.align_roll(Vector((0, 0, 1)) if abs(d.y) > 0.7 else Vector((0, 1, 0)))
        b.use_deform = not (n == "Root" or n.endswith("Eye"))
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm


# ----------------------------------------------------------------------------- export
def export_glb(path, objs, animations=False):
    select_only(objs)
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
              export_animations=animations, export_skins=True, export_def_bones=False, export_morph=False,
              export_image_format='JPEG', export_jpeg_quality=90,   # no material uses alpha
              export_materials='EXPORT', export_extras=True)
    if animations:
        kw.update(export_animation_mode='ACTIONS', export_force_sampling=True, export_optimize_animation_size=True)
    bpy.ops.export_scene.gltf(**kw)
    log("  wrote", path, "%.2f MB" % (os.path.getsize(path) / 1e6))


# ----------------------------------------------------------------------------- characters
CASUAL_MALE_BUDGET = {  # material -> triangles (teeth and eyelash cards are dropped)
    "AvatarHead": 3000, "haircut": 5000, "outfit_top": 2300, "outfit_bottom": 1600, "AvatarBody": 1300,
    "outfit_shoes": 900, "AvatarLeftEyeball": 250, "AvatarRightEyeball": 250}
DROP_MATERIALS = ("AvatarTeethLower", "AvatarTeethUpper", "AvatarEyelashes")


def process_rigged(cid, src, kind):
    load(src)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    meshes = [o for o in bpy.data.objects if o.type == 'MESH'
              and any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers)]
    flatten([arm] + meshes)
    for o in meshes:
        if o.data.shape_keys:
            o.shape_key_clear()
    # metres: Renderpeople files are in centimetres
    H0 = float(verts_np(meshes)[:, 2].max())
    scale = 0.01 if H0 > 10 else 1.0
    M = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(scale, 4)
    apply_global([arm] + meshes, M)
    if scale != 1.0:
        scale_location_curves(scale)
    removed, renames = remap_skeleton(arm, meshes, kind)
    hips = arm.data.bones["Hips"].head_local
    V = verts_np(meshes)
    T = Matrix.Translation((-hips.x, -hips.y, -float(V[:, 2].min())))
    apply_global([arm] + meshes, T)
    place_root(arm)
    # geometry
    if kind == "mixamo":
        for o in list(meshes):
            mn = o.data.materials[0].name if o.data.materials else ""
            if mn in DROP_MATERIALS:
                meshes.remove(o)
                bpy.data.objects.remove(o)
    for o in meshes:
        clean_mesh(o)
    total = tris(meshes)
    for o in meshes:
        if kind == "mixamo":
            mn = o.data.materials[0].name
            decimate(o, CASUAL_MALE_BUDGET.get(mn, 500))
        else:
            decimate(o, int(tris([o]) * min(1.0, 14500 / total)))
    merge_trivial_materials(meshes)
    downsize_images(meshes)
    body = join(meshes, "Body")
    if tris([body]) > MAX_TRIS:
        decimate(body, 14500)
    limit_and_normalize(body)
    arm.name = arm.data.name = "Armature"
    body.parent = arm
    body.matrix_parent_inverse = Matrix.Identity(4)
    for md in body.modifiers:
        if md.type == 'ARMATURE':
            md.object = arm
    # animation
    clips = []
    acts = list(bpy.data.actions)
    if cid == "sophia" and acts:
        a = acts[0]
        a.name = "Idle"
        bad, good = [], 0
        for f in action_fcurves(a):
            bn = re.match(r'pose\.bones\["([^"]+)"\]', f.data_path)
            if bn and bn.group(1) not in arm.data.bones:
                bad.append(f)
            else:
                good += 1
        removed_bones = set(removed)
        unexpected = [f.data_path for f in bad
                      if re.match(r'pose\.bones\["([^"]+)"\]', f.data_path).group(1) not in removed_bones]
        for layer in getattr(a, "layers", []):     # drop curves of the deleted end bones
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for f in list(cb.fcurves):
                        if f in bad:
                            cb.fcurves.remove(f)
        log("  Idle fcurves: %d kept, %d dropped (deleted bones), unresolved renamed: %s"
            % (good, len(bad), unexpected[:4]))
        arm.animation_data.action = a
        clips = ["Idle"]
    else:
        if arm.animation_data:
            arm.animation_data.action = None
        for a in acts:
            bpy.data.actions.remove(a)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    return finish(cid, arm, body, clips, len(renames))


def finish(cid, arm, body, clips, nren, rigged_by="source"):
    # Godot's humanoid retargeting (SkeletonProfileHumanoid, rest fixer) expects characters to
    # face +Z in Godot = Blender -Y, the glTF convention the animation library also follows.
    # Turn the finished character round; the game turns the model back to face -Z at runtime.
    apply_global([arm, body], Matrix.Rotation(math.pi, 4, 'Z'))
    missing = check_hierarchy(arm)
    V = verts_np([body])
    ang = arm_angle(arm)
    info = {
        "id": cid, "path": "res://assets/sketchup/people/%s.glb" % cid,
        "height": round(float(V[:, 2].max()), 3), "tris": tris([body]),
        "rest_pose": "T" if ang < 25 else "A", "rest_arm_angle_deg": round(ang, 1),
        "bones_mapped": sum(1 for b in arm.data.bones if b.name in HUMANOID_SET),
        "bones_total": len(arm.data.bones), "missing_humanoid_bones": missing,
        "clips": clips, "rig": rigged_by, "facing": "-Y blender / +Z godot (humanoid retarget convention)",
    }
    log("  info", info)
    log("  bbox min", V.min(axis=0).round(3), "max", V.max(axis=0).round(3))
    export_glb(os.path.join(OUT, cid + ".glb"), [arm, body], animations=bool(clips))
    return info


def unpinch_legs(mesh, H):
    """Wide trousers touch at the knees; welded/shared vertices there tie the legs together.
    Detach everything below the crotch on the +X side, then re-weld all but the midline."""
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    zc = 0.42 * H
    pinch = [v for v in bm.verts if v.co.z < zc and abs(v.co.x) < 0.01
             and {f.calc_center_median().x > 0 for f in v.link_faces} == {True, False}]
    if pinch:
        side = [f for f in bm.faces if f.calc_center_median().x > 0 and f.calc_center_median().z < zc]
        bmesh.ops.split(bm, geom=side, use_only_faces=False)
        reweld = [v for v in bm.verts if not (v.co.z < zc - 0.01 * H and abs(v.co.x) < 0.012)]
        bmesh.ops.remove_doubles(bm, verts=reweld, dist=1e-6)
        bm.to_mesh(mesh.data)
    bm.free()
    return len(pinch)


def enforce_leg_sides(mesh, H):
    """Below the crotch a vertex on the right half (+X) must not follow the left leg and vice
    versa (bone heat bleeds across wide trousers whose legs touch at the knees)."""
    legs = ("UpperLeg", "LowerLeg", "Foot", "Toes")
    idx = {g.name: g.index for g in mesh.vertex_groups}
    left = {idx["Left" + n] for n in legs if "Left" + n in idx}
    right = {idx["Right" + n] for n in legs if "Right" + n in idx}
    groups = {g.index: g for g in mesh.vertex_groups}
    changed = 0
    for v in mesh.data.vertices:
        if v.co.z > 0.44 * H or abs(v.co.x) < 0.004:
            continue
        wrong = left if v.co.x > 0 else right
        drop = [g.group for g in v.groups if g.group in wrong and g.weight > 0]
        if drop:
            for gi in drop:
                groups[gi].remove([v.index])
            changed += 1
    return changed


def count_unweighted(mesh, arm):
    deform = {b.name for b in arm.data.bones if b.use_deform}
    idx2name = {g.index: g.name for g in mesh.vertex_groups}
    return sum(1 for v in mesh.data.vertices
               if sum(g.weight for g in v.groups if idx2name[g.group] in deform) <= 1e-4)


def auto_weights(body, arm):
    """ARMATURE_AUTO with the usual bone-heat rescue steps; returns the method that worked."""
    def unbind():
        body.parent = None
        for md in list(body.modifiers):
            body.modifiers.remove(md)
        for g in list(body.vertex_groups):
            body.vertex_groups.remove(g)

    def heat(scale=1.0):
        unbind()
        if scale != 1.0:
            body.data.transform(Matrix.Scale(scale, 4))
            arm.data.transform(Matrix.Scale(scale, 4))
        select_only([body, arm], arm)
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        if scale != 1.0:
            body.data.transform(Matrix.Scale(1 / scale, 4))
            arm.data.transform(Matrix.Scale(1 / scale, 4))
        return count_unweighted(body, arm)

    n = len(body.data.vertices)
    bad = heat()
    log("  bone heat: %d / %d vertices unweighted" % (bad, n))
    if bad <= 0.02 * n:
        return "ARMATURE_AUTO"
    # repair: weld near-duplicates, consistent outward normals, drop loose verts/edges
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-4)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(body.data)
    bm.free()
    bad = heat()
    log("  bone heat after mesh repair: %d / %d unweighted" % (bad, len(body.data.vertices)))
    if bad <= 0.02 * len(body.data.vertices):
        return "ARMATURE_AUTO after weld/normals repair"
    bad = heat(10.0)
    log("  bone heat at x10 scale: %d / %d unweighted" % (bad, len(body.data.vertices)))
    if bad <= 0.02 * len(body.data.vertices):
        return "ARMATURE_AUTO (solved at x10 scale)"
    log("  bone heat failed; using distance (envelope-style) weights")
    distance_weights(body, arm)
    return "distance weights (bone heat failed)"


def process_unrigged(cid, src, template):
    tb, tm = template
    load(src)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    flatten(meshes)
    apply_global(meshes, Matrix.Rotation(math.pi, 4, 'Z'))
    body = join(meshes, "Body")
    clean_mesh(body, merge=1e-5)
    V = verts_np([body])
    cx = 0.5 * (V[:, 0].min() + V[:, 0].max())
    apply_global([body], Matrix.Translation((-cx, 0, -float(V[:, 2].min()))))
    V = verts_np([body])
    m = measure(V)
    apply_global([body], Matrix.Translation((0, -m["hips"], 0)))
    V = verts_np([body])
    m = measure(V)
    log("  legs unpinched at %d midline vertices" % unpinch_legs(body, m["H"]))
    log("  landmarks: H %.3f armpit %.3f wrist %.3f tip %.3f hand %.3f shoulder %s" % (
        m["H"], m["armpit"], m["wrist_x"], m["x_tip"], m["hand_len"], tuple(round(c, 3) for c in m["shoulder_pt"])))
    arm = build_rig(m, tb, tm)
    if tris([body]) > MAX_TRIS:
        decimate(body, 14500)
    method = auto_weights(body, arm)
    nside = enforce_leg_sides(body, m["H"])
    log("  removed cross-leg weights on %d vertices" % nside)
    nfix = fix_unweighted(body, arm)
    log("  auto weights done; vertices without weights fixed from neighbours:", nfix, "/", len(body.data.vertices))
    limit_and_normalize(body)
    merge_trivial_materials([body])
    downsize_images([body])
    return finish(cid, arm, body, [], 0, rigged_by="auto (fitted humanoid, %s, %d verts patched)" % (method, nfix))


# ----------------------------------------------------------------------------- cyclist
def loose_parts(bm):
    bm.verts.ensure_lookup_table()
    seen = np.zeros(len(bm.verts), bool)
    parts = []
    for v in bm.verts:
        if seen[v.index]:
            continue
        stack = [v]
        seen[v.index] = True
        ids = []
        while stack:
            x = stack.pop()
            ids.append(x.index)
            for e in x.link_edges:
                w = e.other_vert(x)
                if not seen[w.index]:
                    seen[w.index] = True
                    stack.append(w)
        parts.append(ids)
    return parts


def bake_lowpoly(hi, target, name, size):
    """Decimated, freshly unwrapped copy of `hi` with base colour + normal maps baked from it."""
    lo = hi.copy()
    lo.data = hi.data.copy()
    bpy.context.scene.collection.objects.link(lo)
    decimate(lo, target, symmetric=False)
    while lo.data.uv_layers:
        lo.data.uv_layers.remove(lo.data.uv_layers[0])
    lo.data.uv_layers.new(name="UVMap")
    select_only([lo])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    col = bpy.data.images.new(name + "_basecolor", size, size, alpha=False)
    nrm = bpy.data.images.new(name + "_normal", size, size, alpha=False)
    nrm.colorspace_settings.name = 'Non-Color'
    mat = bpy.data.materials.new(name + "_baked")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Roughness"].default_value = 0.75
    bsdf.inputs["Metallic"].default_value = 0.0
    tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = col
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    lo.data.materials.clear()
    lo.data.materials.append(mat)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 4
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = 0.015
    bk.max_ray_distance = 0.05
    bk.margin = 4
    select_only([hi, lo], lo)
    for img, btype, kw in ((col, 'DIFFUSE', dict(pass_filter={'COLOR'})),
                           (nrm, 'NORMAL', dict(normal_space='TANGENT'))):
        nt.nodes.active = tc if img is col else tn
        bpy.ops.object.bake(type=btype, use_selected_to_active=True, cage_extrusion=0.015,
                            max_ray_distance=0.05, margin=4, **kw)
        img.pack()
        log("  baked", img.name, btype)
    nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.nodes.active = tc
    hi_name = hi.name
    bpy.data.objects.remove(hi)
    lo.name = lo.data.name = hi_name
    return lo


def process_cyclist(cid="cyclist_woman", src="woman_riding_a_gray_bicycle.glb"):
    load(src)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    flatten(meshes)
    apply_global(meshes, Matrix.Rotation(math.pi, 4, 'Z'))
    body = join(meshes, "Cyclist")
    clean_mesh(body, merge=2e-5)
    V = verts_np([body])
    apply_global([body], Matrix.Translation((0, 0, -float(V[:, 2].min()))))
    V = verts_np([body])
    log("  cyclist tris", tris([body]), "bbox", V.min(axis=0).round(3), V.max(axis=0).round(3))
    # wheel hubs from the ground contacts and the tyre extremes
    ymid = 0.5 * (V[:, 1].min() + V[:, 1].max())
    low = V[V[:, 2] < 0.01]
    hubs = {}
    for name, sel, edge in (("WheelFront", low[:, 1] > ymid, V[:, 1].max()),
                            ("WheelRear", low[:, 1] < ymid, V[:, 1].min())):
        c = low[sel]
        yc = float(np.median(c[:, 1]))
        xc = float(np.median(c[:, 0]))
        r = abs(edge - yc)
        hubs[name] = (Vector((xc, yc, r)), r)
        log("  %s hub (%.3f, %.3f, %.3f) r=%.3f" % (name, xc, yc, r, r))
    # loose parts inside each wheel disc
    bm = bmesh.new()
    bm.from_mesh(body.data)
    parts = loose_parts(bm)
    co = np.array([v.co[:] for v in bm.verts])
    assign = {"WheelFront": [], "WheelRear": []}
    for ids in parts:
        P = co[ids]
        for name, (hub, r) in hubs.items():
            d = np.hypot(P[:, 1] - hub.y, P[:, 2] - hub.z)
            if d.max() <= r * 1.06 and np.abs(P[:, 0] - hub.x).max() < 0.09 and (d.max() > 0.8 * r or d.max() < 0.25 * r):
                assign[name].append(ids)
                break
    ok = True
    for name, (hub, r) in hubs.items():
        if not assign[name]:
            ok = False
            continue
        P = co[np.concatenate(assign[name])]
        span_y, span_z = np.ptp(P[:, 1]), np.ptp(P[:, 2])
        log("  %s: %d loose parts, %d verts, span y %.3f z %.3f (2r=%.3f)" % (
            name, len(assign[name]), len(P), span_y, span_z, 2 * r))
        if span_y < 1.8 * r or span_z < 1.8 * r or not (0.25 < r < 0.45):
            ok = False
    split = {}
    if ok:
        for name in ("WheelFront", "WheelRear"):
            ids = set(int(i) for part in assign[name] for i in part)
            bm.verts.ensure_lookup_table()
            for f in bm.faces:
                f.select = all(v.index in ids for v in f.verts)
            bm.to_mesh(body.data)
            select_only([body])
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')
            new = [o for o in bpy.context.selected_objects if o is not body][0]
            new.name = new.data.name = name + "Mesh"
            split[name] = new
            bm.free()
            bm = bmesh.new()
            bm.from_mesh(body.data)
    bm.free()
    log("  wheels split:", ok)
    # 25k budget. The source atlas is thousands of tiny UV islands, so a 20x decimation smears
    # it; instead decimate a copy, unwrap it fresh and bake colour + normals from the original.
    budgets = {"WheelFront": 2800, "WheelRear": 2800}
    lows = {}
    for name, hi in [("Cyclist", body)] + list(split.items()):
        lows[name] = bake_lowpoly(hi, budgets.get(name, 25000 - 300 - sum(budgets.values()) if split else 24500),
                                  name, 512 if name in budgets else TEX_MAX)
    body = lows["Cyclist"]
    split = {n: lows[n] for n in split}
    allm = [body] + list(split.values())
    # origin under the bicycle centre
    if split:
        hf, hr = hubs["WheelFront"][0], hubs["WheelRear"][0]
        cen = Vector(((hf.x + hr.x) / 2, (hf.y + hr.y) / 2, 0))
    else:
        V = verts_np([body])
        cen = Vector((0.5 * (V[:, 0].min() + V[:, 0].max()), 0.5 * (V[:, 1].min() + V[:, 1].max()), 0))
    apply_global(allm, Matrix.Translation(-cen))
    rootobj = bpy.data.objects.new("CyclistWoman", None)
    bpy.context.scene.collection.objects.link(rootobj)
    body.parent = rootobj
    out = [rootobj, body]
    for name, o in split.items():
        hub = hubs[name][0] - cen
        e = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(e)
        e.empty_display_type = 'PLAIN_AXES'
        e.location = hub
        e.parent = rootobj
        o.data.transform(Matrix.Translation(-hub))
        o.parent = e
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.location = (0, 0, 0)
        out += [e, o]
    V = verts_np(allm)
    info = {"id": cid, "path": "res://assets/sketchup/people/%s.glb" % cid,
            "tris": tris(allm), "height": round(float(V[:, 2].max()), 3),
            "length": round(float(np.ptp(V[:, 1])), 3), "wheels_split": bool(split),
            "wheel_radius": round(float(hubs["WheelFront"][1]), 3)}
    log("  info", info, "bbox", V.min(axis=0).round(3), V.max(axis=0).round(3))
    export_glb(os.path.join(OUT, cid + ".glb"), out)
    return info


# ----------------------------------------------------------------------------- QA renders
def render_setup(res=700):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_shadows = False
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.color = (0.32, 0.34, 0.38)
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    for mat in bpy.data.materials:   # workbench shows the active image node: make it the base colour
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
                    mat.node_tree.nodes.active = n
    # ground plane for contact check
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
    return cam


def shoot(cam, path, direction, target, ortho):
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ortho
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * 10
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = 100
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def pose_world(arm, bone, axis, deg):
    pb = arm.pose.bones.get(bone)
    if not pb:
        return
    B = (arm.matrix_world @ pb.bone.matrix_local).to_3x3().normalized()
    R = Matrix.Rotation(math.radians(deg), 3, axis)
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = (B.inverted() @ R @ B).to_quaternion()


def reimport(path):
    reset()
    bpy.ops.import_scene.gltf(filepath=path)
    for o in list(bpy.data.objects):   # the importer's bone-shape helper, not part of the file
        if o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o)


def qa_character(cid):
    reimport(os.path.join(OUT, cid + ".glb"))
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    V = verts_np(meshes)
    H = float(V[:, 2].max())
    log("  QA reimport: armature scale", tuple(round(s, 4) for s in arm.matrix_world.to_scale()),
        "bones", len(arm.data.bones), "H %.3f minz %.4f" % (H, V[:, 2].min()))
    cam = render_setup()
    tgt = (0, 0, H / 2)
    span = max(H, float(np.ptp(V[:, 0]))) * 1.08
    act = arm.animation_data.action if arm.animation_data else None
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()
    shoot(cam, os.path.join(QA, cid + "_front.png"), (0, 1, 0), tgt, span)
    shoot(cam, os.path.join(QA, cid + "_side.png"), (1, 0, 0), tgt, span)
    hb = arm.data.bones.get("Head")
    if hb:
        hz = (arm.matrix_world @ hb.head_local).z + 0.08
        shoot(cam, os.path.join(QA, cid + "_head.png"), (0.5, 1, 0.1), (0, 0, hz), 0.42)
    pose_world(arm, "Spine", 'Z', 20)
    pose_world(arm, "LeftUpperLeg", 'X', 40)
    pose_world(arm, "LeftUpperArm", 'Y', -60)
    bpy.context.view_layer.update()
    shoot(cam, os.path.join(QA, cid + "_posed_hips.png"), (0.45, 1, -0.05), (0, 0, 0.5 * H), 0.75)
    shoot(cam, os.path.join(QA, cid + "_posed_shoulder.png"), (-0.2, 1, 0.2), (-0.25, 0, 0.78 * H), 0.6)
    pose_world(arm, "LeftUpperLeg", 'X', 40)
    pose_world(arm, "LeftUpperArm", 'Y', -60)
    bpy.context.view_layer.update()
    shoot(cam, os.path.join(QA, cid + "_posed_front.png"), (0, 1, 0), tgt, span)
    shoot(cam, os.path.join(QA, cid + "_posed_side.png"), (1, 0, 0), tgt, span)
    shoot(cam, os.path.join(QA, cid + "_posed_34.png"), (0.7, 0.7, 0.25), tgt, span)
    if act:
        for pb in arm.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0)
        arm.animation_data.action = act
        try:
            arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass
        f0, f1 = act.frame_range
        for i, fr in enumerate((f0, f0 + (f1 - f0) * 0.37, f0 + (f1 - f0) * 0.74)):
            bpy.context.scene.frame_set(int(fr))
            shoot(cam, os.path.join(QA, "%s_idle_%d.png" % (cid, i)), (0.6, 1, 0.1), tgt, H * 1.08)
        log("  QA clip", act.name, "frames", tuple(act.frame_range))


def qa_cyclist(cid="cyclist_woman"):
    reimport(os.path.join(OUT, cid + ".glb"))
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    V = verts_np(meshes)
    for o in bpy.data.objects:
        if o.type == 'EMPTY':
            log("  QA node", o.name, tuple(round(c, 3) for c in o.matrix_world.translation),
                "parent", o.parent.name if o.parent else None)
    cam = render_setup()
    H = float(V[:, 2].max())
    span = max(H, float(np.ptp(V[:, 1]))) * 1.08
    tgt = (0, 0, H / 2)
    shoot(cam, os.path.join(QA, cid + "_side.png"), (1, 0, 0), tgt, span)
    shoot(cam, os.path.join(QA, cid + "_front.png"), (0, 1, 0), tgt, span)
    shoot(cam, os.path.join(QA, cid + "_34.png"), (0.7, 0.7, 0.3), tgt, span)
    fw = bpy.data.objects.get("WheelFront")
    if fw:   # spin both wheels 30 deg about local X: must stay in place
        for n in ("WheelFront", "WheelRear"):
            bpy.data.objects[n].rotation_euler.x += math.radians(30)
        bpy.context.view_layer.update()
        shoot(cam, os.path.join(QA, cid + "_wheels_spun.png"), (1, 0, 0), tgt, span)


# ----------------------------------------------------------------------------- main
def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(QA, exist_ok=True)
    try:
        with open(JSON_PATH) as fh:
            entries = {e["id"]: e for e in json.load(fh)}
    except (OSError, ValueError):
        entries = {}
    template = None
    for cid, src, kind in CHARACTERS:
        if ONLY and cid not in ONLY:
            continue
        log("=====", cid)
        if kind == "unrigged":
            if template is None:
                template = template_skeleton()
            info = process_unrigged(cid, src, template)
        else:
            info = process_rigged(cid, src, kind)
        entries[cid] = info
        with open(JSON_PATH, "w") as fh:
            json.dump([entries[c] for c, _, _ in CHARACTERS if c in entries], fh, indent=2)
        if DO_QA:
            qa_character(cid)
    if not ONLY or "cyclist_woman" in ONLY:
        log("===== cyclist_woman")
        process_cyclist()
        if DO_QA:
            qa_cyclist()


main()
