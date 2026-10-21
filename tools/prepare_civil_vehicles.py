"""Split the civil service vehicle pack and the Ace 11 hatchback into game-ready GLBs.

"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" --background --factory-startup \
    --python tools/prepare_civil_vehicles.py -- [id ...]

ids: ambulance citybus fire_truck garbage_truck police_sedan postvan rdservtruck school_bus taxi
towtruck ace11 (none = all). Sources are the user's GLBs at the project root (left untouched):
  generic_civil_service_vehicles_pack.glb -> assets/vehicles/civil/<name>.glb
  ace_11_-_low_poly_model.glb             -> assets/vehicles/ace11/ace11.glb

Vehicle contract (same as tools/prepare_sketchup_assets.py / VehicleCatalog):
  root empty on the ground (z = 0), centred on the footprint, front at Blender +Y (Godot -Z),
  metres (sources are already real scale); wheel empties WheelFrontL/R, WheelRearL/R
  (WheelRear2L/R for a third axle) at the hub centres with identity rotation, so they spin about
  local X; front wheels under SteerFrontL/R (yaw); glTF extras on the root: wheelbase,
  wheel_radius, length, width, height, collision_lift.
  Civil liveries are kept (no VehiclePaint). The Ace 11 body panels are one VehiclePaint mesh
  (traffic recolours it) and it has a SteeringWheel empty whose local Blender -Y (Godot +Z) is
  the steering column, so the player's drive code can turn it.
Textures are downscaled: 2048 -> 1024, anything smaller -> at most 512.
QA renders (front three-quarter, Workbench, textured) -> world/vehicles/production/renders/civil/.
"""
import bpy, sys, os, math, json
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "generic_civil_service_vehicles_pack.glb")
ACE = os.path.join(ROOT, "ace_11_-_low_poly_model.glb")
OUT_CIVIL = os.path.join(ROOT, "assets", "vehicles", "civil")
OUT_ACE = os.path.join(ROOT, "assets", "vehicles", "ace11")
QA = os.path.join(ROOT, "world", "vehicles", "production", "renders", "civil")
REPORT = os.path.join(ROOT, "world", "vehicles", "production", "reports", "civil_vehicles.json")
CIVIL = ["ambulance", "citybus", "fire_truck", "garbage_truck", "police_sedan", "postvan", "rdservtruck",
         "school_bus", "taxi", "towtruck"]
ONLY = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
for d in (OUT_CIVIL, OUT_ACE, QA, os.path.dirname(REPORT)):
    os.makedirs(d, exist_ok=True)


# ------------------------------------------------------------------ helpers
def tris(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o is not None and o.type == 'MESH')


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)


def points(objs):
    chunks = []
    for o in objs:
        if o is None or o.type != 'MESH' or not o.data.vertices:
            continue
        co = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        chunks.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
    return np.concatenate(chunks)


def bbox(objs):
    p = points(objs)
    return Vector(p.min(axis=0).tolist()), Vector(p.max(axis=0).tolist())


def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def join(parts, name):
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    if len(parts) > 1:
        select_only(parts)
        bpy.ops.object.join()
    parts[0].name = name
    return parts[0]


def bake(objs, name):
    """World-space static copies of the given meshes, joined into one object."""
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        if o.matrix_world.determinant() < 0:
            me.flip_normals()
        n = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(n)
        parts.append(n)
    return join(parts, name)


def clear_others(keep):
    keep = set(k for k in keep if k is not None)
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o)


def loose_parts(obj):
    select_only([obj])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    return list(bpy.context.selected_objects)


def principal_heading(objs, hint):
    """Long axis of the footprint (PCA of x/y), signed to agree with `hint`."""
    p = points(objs)[:, :2]
    p = p - p.mean(axis=0)
    w, v = np.linalg.eigh(np.cov(p.T))
    axis = Vector((float(v[0, 1]), float(v[1, 1]), 0)).normalized()
    return axis if axis.dot(hint) >= 0 else -axis


def normalise(objs, centre, forward):
    """Bake transforms into the meshes; centre the footprint on the origin, front to +Y, ground z=0."""
    objs = [o for o in objs if o is not None]
    ang = math.atan2(forward.y, forward.x) - math.pi / 2
    m = Matrix.Rotation(-ang, 4, 'Z') @ Matrix.Translation(-Vector((centre.x, centre.y, 0)))
    for o in objs:
        if o.data.users > 1:
            o.data = o.data.copy()
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.data.transform(m)
    mn, mx = bbox(objs)
    shift = Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z))
    for o in objs:
        o.data.transform(shift)


def find_tires(body, min_d=0.45, max_d=1.4):
    """Split wheels out of a body mesh: ground-touching round loose parts, plus whatever sits
    inside them (rims, hubs, lug nuts). Returns (body, [wheel objects])."""
    parts = loose_parts(body)
    tires, rest = [], []
    for p in parts:
        mn, mx = bbox([p])
        d = mx - mn
        round_side = abs(d.y - d.z) < 0.18 * max(d.y, d.z)
        if mn.z < 0.12 and round_side and min_d < d.z < max_d and d.x < 0.75:
            tires.append(p)
        else:
            rest.append(p)
    wheels = []
    for t in sorted(tires, key=lambda p: -(bbox([p])[1].z - bbox([p])[0].z)):
        mn, mx = bbox([t])
        c = (mn + mx) / 2
        for w in wheels:
            if (w["c"] - c).length < 0.3:
                w["parts"].append(t)
                break
        else:
            wheels.append({"c": c, "r": (mx.z - mn.z) / 2, "parts": [t]})
    body_parts = []
    for p in rest:
        mn, mx = bbox([p])
        c = (mn + mx) / 2
        host = None
        for w in wheels:
            near = (Vector((c.y, c.z)) - Vector((w["c"].y, w["c"].z))).length < w["r"] * 0.6
            fits = (mx - mn).z < w["r"] * 2.05 and (mx - mn).y < w["r"] * 2.05 and abs(c.x - w["c"].x) < 0.35
            if near and fits:
                host = w
                break
        (host["parts"] if host else body_parts).append(p)
    return join(body_parts, "Body"), [join(w["parts"], "WheelMesh") for w in wheels]


def downscale_textures():
    """2048 maps -> 1024; smaller maps -> at most 512. Repacked so the exporter writes the new pixels."""
    used = set()
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        for m in o.data.materials:
            if m and m.node_tree:
                used |= {n.image for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}
    out = []
    for im in sorted(used, key=lambda i: i.name):
        if im.size[0] == 0:
            continue
        w, h = im.size
        big = max(w, h)
        target = 1024 if big >= 2048 else min(big, 512)
        if big > target:
            k = target / big
            im.scale(max(1, int(w * k)), max(1, int(h * k)))
            im.pack()
        out.append("%s %dx%d" % (im.name, im.size[0], im.size[1]))
    return out


def empty(name, parent=None, at=(0, 0, 0), size=0.3):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_size = size
    e.location = at
    e.parent = parent
    return e


def rig(vid, root_name, body_objs, wheel_objs):
    """Wheel/steer empties, root extras. Returns (root, info dict)."""
    root = empty(root_name, size=1.0)
    for o in body_objs:
        if o is not None:
            o.parent = root
    info = []
    for w in wheel_objs:
        mn, mx = bbox([w])
        info.append((w, (mn + mx) / 2, (mx.z - mn.z) / 2))
    axles = []
    for w, c, r in sorted(info, key=lambda t: -t[1].y):
        for a in axles:
            if abs(a["y"] - c.y) < 0.35:
                a["w"].append((w, c, r))
                break
        else:
            axles.append({"y": c.y, "w": [(w, c, r)]})
    radius = sum(r for _, _, r in info) / max(1, len(info))
    names = []
    for ai, a in enumerate(axles):
        label = "Front" if ai == 0 else ("Rear" if ai == 1 else "Rear%d" % ai)
        for w, c, r in sorted(a["w"], key=lambda t: abs(t[1].x)):
            side = "L" if c.x < 0 else "R"
            name = "Wheel%s%s" % (label, side)
            k = 2
            while bpy.data.objects.get(name):
                name = "Wheel%s%s_%d" % (label, side, k)
                k += 1
            if label == "Front" and not bpy.data.objects.get("SteerFront" + side):
                steer = empty("SteerFront" + side, root, c)
                hub = empty(name, steer, size=r)
            elif label == "Front":
                # A second front wheel on the same side (twin tyres) rides the same steer pivot.
                steer = bpy.data.objects["SteerFront" + side]
                hub = empty(name, steer, c - steer.location, size=r)
            else:
                hub = empty(name, root, c, size=r)
            w.data.transform(Matrix.Translation(-c))
            w.matrix_world = Matrix.Identity(4)
            w.parent = hub
            w.name = name + "Mesh"
            names.append(name)
    bpy.context.view_layer.update()
    mn, mx = bbox([o for o in bpy.data.objects if o.type == 'MESH'])
    front_y = axles[0]["y"] if axles else 1.3
    rear_y = axles[-1]["y"] if axles else -1.3
    if len(axles) > 2:
        rear_y = sum(a["y"] for a in axles[1:]) / (len(axles) - 1)   # effective rear bogie centre
    root["wheelbase"] = round(front_y - rear_y, 3)
    root["wheel_radius"] = round(radius, 3)
    root["length"] = round(mx.y - mn.y, 3)
    root["width"] = round(mx.x - mn.x, 3)
    root["height"] = round(mx.z - mn.z, 3)
    root["front_overhang"] = round(mx.y - front_y, 3)
    root["rear_overhang"] = round(rear_y - mn.y, 3) if len(axles) < 3 else round(axles[-1]["y"] - mn.y, 3)
    root["collision_lift"] = 0.0
    return root, {"wheels": names, "axles": len(axles), "wheelbase": root["wheelbase"], "wheel_radius": root["wheel_radius"],
                  "length": root["length"], "width": root["width"], "height": root["height"],
                  "front_overhang": root["front_overhang"], "rear_overhang": root["rear_overhang"]}


def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_extras=True, export_yup=True,
                              export_apply=True, export_animations=False, export_image_format='AUTO')


def render_qa(name, length, height, width):
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_WORKBENCH'
    except TypeError:
        pass
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = 800, 500
    scene.render.film_transparent = False
    # A ground plane so the wheels visibly sit on z = 0.
    bpy.ops.mesh.primitive_plane_add(size=max(length, width) * 3)
    ground = bpy.context.active_object
    ground.name = "QAGround"
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = max(length * 1.05, height * 1.6, 2.0) * 1.15
    d = Vector((-1.0, 1.35, 0.55)).normalized() * 40   # from the left-front: front is +Y, left is -X
    cam.location = d + Vector((0, 0, height * 0.45))
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    scene.render.filepath = os.path.join(QA, name + ".png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    bpy.data.objects.remove(ground)


def want(vid):
    return not ONLY or vid in ONLY


report = {}
if os.path.exists(REPORT):
    try:
        report = json.load(open(REPORT))
    except Exception:
        report = {}


# ------------------------------------------------------------------ civil service pack
def civil(name):
    load(PACK)
    vroot = bpy.data.objects[name]
    meshes = [o for o in vroot.children_recursive if o.type == 'MESH']
    src_tris = tris(meshes)
    mn, mx = bbox(meshes)
    centre = (mn + mx) / 2
    # Each vehicle's root yaw gives its heading: the model's front is local -Y at yaw 0
    # (checked against the QA renders); PCA gives the exact long axis.
    yaw = vroot.matrix_world.to_euler().z
    hint = Matrix.Rotation(yaw, 3, 'Z') @ Vector((0, -1, 0))
    forward = principal_heading(meshes, hint)
    main = max(meshes, key=lambda o: len(o.data.polygons))
    body = bake([main], "Main")
    extras = bake([m for m in meshes if m != main], "Details")
    clear_others([body, extras])
    normalise([body, extras], centre, forward)
    body, wheels = find_tires(body)
    vid = "civil_" + name
    root, info = rig(vid, vid, [body, extras], wheels)
    root["source"] = "generic_civil_service_vehicles_pack.glb (Sketchfab)"
    info["textures"] = downscale_textures()
    info["tris_source"] = src_tris
    info["tris"] = tris(bpy.data.objects)
    export(os.path.join(OUT_CIVIL, name + ".glb"))
    info["glb_bytes"] = os.path.getsize(os.path.join(OUT_CIVIL, name + ".glb"))
    render_qa(vid, info["length"], info["height"], info["width"])
    print("EXPORTED", vid, json.dumps(info))
    report[vid] = info


# ------------------------------------------------------------------ Ace 11
def ace11():
    load(ACE)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    src_tris = tris(meshes)
    group = lambda pred: [o for o in meshes if pred(o.name)]
    wheel_src = {tag: group(lambda n, t=tag: n.startswith("Ace11_WheelStock_" + t)) for tag in ("FL", "FR", "RL", "RR")}
    in_wheels = {o for s in wheel_src.values() for o in s}
    paint_src = [o for o in meshes if o not in in_wheels and o.data.materials and o.data.materials[0]
                 and o.data.materials[0].name == "Ace11_Bodymat"]
    sw_src = group(lambda n: n.startswith("Ace11_Steering_Wheel"))
    rest_src = [o for o in meshes if o not in in_wheels and o not in paint_src and o not in sw_src]
    # Underbody, suspension and bumper inners (UCB_BOTTOM_LT) are barely seen: halve them so the
    # car stays near the 15k-triangle budget without touching the visible shell.
    for o in rest_src:
        if o.data.materials and o.data.materials[0] and o.data.materials[0].name == "UCB_BOTTOM_LT":
            mod = o.modifiers.new("decimate", 'DECIMATE')
            mod.ratio = 0.5
            mod.use_collapse_triangulate = True
    mn, mx = bbox(meshes)
    centre = (mn + mx) / 2
    paint = bake(paint_src, "VehiclePaint")
    body = bake(rest_src, "Body")
    sw = bake(sw_src, "SteeringWheelMesh")
    wheels = {tag: bake(objs, "WheelMesh") for tag, objs in wheel_src.items()}
    clear_others([paint, body, sw] + list(wheels.values()))
    # Front of the Ace 11 is Blender +X in the source.
    normalise([paint, body, sw] + list(wheels.values()), centre, Vector((1, 0, 0)))
    root, info = rig("ace11", "ace11", [paint, body], list(wheels.values()))
    # Steering wheel: the empty's local Y is the column axis (wheel-plane normal, pointing forward
    # and down), so Godot's local +Z (Blender -Y) is the axis the drive code turns it about.
    p = points([sw])
    c = p.mean(axis=0)
    w, v = np.linalg.eigh(np.cov((p - c).T))
    n = Vector(v[:, 0].tolist()).normalized()
    if n.y < 0:
        n = -n
    centre_sw = Vector(((p.min(axis=0) + p.max(axis=0)) / 2).tolist())
    x = (Vector((1, 0, 0)) - n * n.x).normalized()
    z = x.cross(n).normalized()
    basis = Matrix((x, n, z)).transposed().to_4x4()
    pivot = empty("SteeringWheel", root, size=0.2)
    pivot.matrix_world = Matrix.Translation(centre_sw) @ basis
    bpy.context.view_layer.update()
    sw.data.transform(pivot.matrix_world.inverted())
    sw.matrix_world = Matrix.Identity(4)
    sw.parent = pivot
    sw.matrix_parent_inverse = Matrix.Identity(4)
    sw.matrix_basis = Matrix.Identity(4)
    info["steering_wheel"] = {"centre": [round(v, 3) for v in centre_sw], "column": [round(v, 3) for v in n],
                              "tilt_deg": round(math.degrees(math.asin(max(-1.0, min(1.0, -n.z)))), 1)}
    root["source"] = "ace_11_-_low_poly_model.glb (Sketchfab)"
    info["textures"] = downscale_textures()
    info["tris_source"] = src_tris
    info["tris"] = tris(bpy.data.objects)
    path = os.path.join(OUT_ACE, "ace11.glb")
    export(path)
    info["glb_bytes"] = os.path.getsize(path)
    render_qa("ace11", info["length"], info["height"], info["width"])
    print("EXPORTED ace11", json.dumps(info))
    report["ace11"] = info


for name in CIVIL:
    if want(name):
        civil(name)
if want("ace11"):
    ace11()
json.dump(report, open(REPORT, "w"), indent=1)
print("REPORT", REPORT)
