"""Convert the downloaded Sketchfab GLBs in sketchup_assets/ into game-ready assets.

blender --background --factory-startup --python tools/prepare_sketchup_assets.py -- [only_id ...]

Vehicles -> assets/sketchup/vehicles/<id>.glb, following the project's vehicle contract:
  root empty <id> on the ground, centred, facing Blender +Y (Godot -Z), metres;
  wheel empties WheelFrontL/R, WheelRearL/R (+ WheelRear2L/R for extra axles) at the wheel
  centres, identity rotation, spinning about local X; front wheels under SteerFrontL/R;
  untextured body paint split into meshes named VehiclePaint so the game can recolour them;
  glTF extras on the root: wheelbase, wheel_radius, length, width, height.
People -> assets/sketchup/people/<id>.glb: one skinned character, facing +Y, real height,
  animation clips renamed to the game's names (Idle, Walk, Brisk, Wait, Talk, Sit, Cycle).
QA renders -> assets/sketchup/qa/<id>.png (front three-quarter view from the left-front).
"""
import bpy, sys, os, math
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sketchup_assets")
OUT_V = os.path.join(ROOT, "assets", "sketchup", "vehicles")
OUT_P = os.path.join(ROOT, "assets", "sketchup", "people")
QA = os.path.join(ROOT, "assets", "sketchup", "qa")
ONLY = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def tris(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == 'MESH')


def load(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, name))
    for o in list(bpy.data.objects):
        if o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o)


def bbox(objs):
    """World bounds from the actual vertices (bound_box goes stale after mesh edits)."""
    import numpy as np
    chunks = []
    for o in objs:
        if o is None or o.type != 'MESH' or not o.data.vertices:
            continue
        co = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(o.matrix_world)
        chunks.append(co @ m[:3, :3].T + m[:3, 3])
    allp = np.concatenate(chunks)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    return Vector(lo.tolist()), Vector(hi.tolist())


def bbox_corners(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def descendants(o):
    return [o] + list(o.children_recursive)


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
    """World-space static copy of the given meshes (armatures/skins applied), joined into one."""
    dg = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        n = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(n)
        parts.append(n)
    return join(parts, name)


def loose_parts(obj):
    select_only([obj])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    return list(bpy.context.selected_objects)


def decimate(obj, budget):
    if obj is None:
        return
    t = tris([obj])
    if t <= budget:
        return
    m = obj.modifiers.new("decimate", 'DECIMATE')
    m.ratio = budget / t
    m.use_collapse_triangulate = True
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier=m.name)


def clear_others(keep):
    keep = set(k for k in keep if k is not None)
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o)


def find_tires(body, ground, min_d=0.45, max_d=1.35):
    """Split wheels out of a body mesh: ground-touching, round loose parts plus whatever sits
    inside them (rims, hubs). Returns (body, [wheel objects])."""
    parts = loose_parts(body)
    tires, rest = [], []
    for p in parts:
        mn, mx = bbox([p])
        d = mx - mn
        round_side = abs(d.y - d.z) < 0.18 * max(d.y, d.z)
        if mn.z < ground + 0.12 and round_side and min_d < d.z < max_d and d.x < 0.75:
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


def normalise(objs, centre, forward, scale=1.0):
    """Bake transforms into mesh data and place the vehicle centred at the origin facing +Y on z=0."""
    objs = [o for o in objs if o is not None]
    ang = math.atan2(forward.y, forward.x) - math.pi / 2
    m = Matrix.Diagonal((scale, scale, scale, 1)) @ Matrix.Rotation(-ang, 4, 'Z') @ Matrix.Translation(-Vector((centre.x, centre.y, 0)))
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


def principal_heading(objs, hint):
    """Long axis of the vehicle's footprint (PCA of vertex x/y), signed to agree with `hint`."""
    import numpy as np
    pts = []
    for o in objs:
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
        pts.append(co[:, :2])
    p = np.concatenate(pts)
    p = p - p.mean(axis=0)
    w, v = np.linalg.eigh(np.cov(p.T))
    axis = Vector((float(v[0, 1]), float(v[1, 1]), 0)).normalized()
    return axis if axis.dot(hint) >= 0 else -axis


def split_paint(o, paint_materials):
    names = [m.name for m in o.data.materials if m]
    if not any(n in paint_materials for n in names):
        return []
    select_only([o])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    for i, m in enumerate(o.data.materials):
        if m and m.name in paint_materials:
            o.active_material_index = i
            bpy.ops.object.material_slot_select()
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    out = []
    for p in bpy.context.selected_objects:
        if p != o:
            p.name = "VehiclePaint"
            out.append(p)
    return out


def rig_vehicle(vid, body_objs, wheel_objs, paint_materials=(), budget=30000, wheel_budget=1200):
    """Turn normalised meshes into the contract hierarchy, export and render QA."""
    root = bpy.data.objects.new(vid, None)
    bpy.context.scene.collection.objects.link(root)
    for o in [b for b in body_objs if b is not None]:
        decimate(o, budget)
        for p in split_paint(o, paint_materials):
            p.parent = root
        o.parent = root
    info = []
    for w in wheel_objs:
        decimate(w, wheel_budget)
        mn, mx = bbox([w])
        info.append((w, (mn + mx) / 2, (mx.z - mn.z) / 2))
        print("  wheel", w.name, tuple(round(v, 2) for v in (mn + mx) / 2), "d", tuple(round(v, 2) for v in mx - mn))
    axles = []
    for w, c, r in sorted(info, key=lambda t: -t[1].y):
        for a in axles:
            if abs(a["y"] - c.y) < 0.35:
                a["w"].append((w, c, r))
                break
        else:
            axles.append({"y": c.y, "w": [(w, c, r)]})
    radius = sum(r for _, _, r in info) / max(1, len(info))
    for ai, a in enumerate(axles):
        label = "Front" if ai == 0 else ("Rear" if ai == 1 else "Rear%d" % ai)
        for w, c, r in a["w"]:
            side = "L" if c.x < 0 else "R"
            name = "Wheel%s%s" % (label, side)
            k = 2
            while bpy.data.objects.get(name):
                name = "Wheel%s%s%d" % (label, side, k)
                k += 1
            hub = bpy.data.objects.new(name, None)
            bpy.context.scene.collection.objects.link(hub)
            hub.empty_display_size = r
            if label == "Front":
                steer = bpy.data.objects.new("SteerFront" + name[len("WheelFront"):], None)
                bpy.context.scene.collection.objects.link(steer)
                steer.location = c
                steer.parent = root
                hub.parent = steer
            else:
                hub.location = c
                hub.parent = root
            w.data.transform(Matrix.Translation(-c))
            w.matrix_world = Matrix.Identity(4)
            w.parent = hub
            w.name = name + "Mesh"
    bpy.context.view_layer.update()
    mn, mx = bbox([o for o in bpy.data.objects if o.type == 'MESH'])
    front_y = axles[0]["y"] if axles else 1.3
    rear_y = axles[-1]["y"] if axles else -1.3
    if len(axles) > 2:
        rear_y = sum(a["y"] for a in axles[1:]) / (len(axles) - 1)   # effective bogie centre
    root["wheelbase"] = round(front_y - rear_y, 3)
    root["wheel_radius"] = round(radius, 3)
    root["length"] = round(mx.y - mn.y, 3)
    root["width"] = round(mx.x - mn.x, 3)
    root["height"] = round(mx.z - mn.z, 3)
    root["collision_lift"] = 0.0
    root["source"] = "sketchup_assets (Sketchfab)"
    path = os.path.join(OUT_V, vid + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_extras=True, export_yup=True,
                              export_apply=True, export_animations=False)
    print("EXPORTED", vid, "tris", tris(bpy.data.objects), "size", root["length"], root["width"], root["height"],
          "wheelbase", root["wheelbase"], "radius", root["wheel_radius"], "wheels", len(info), "axles", len(axles))
    render_qa(vid, mx.y - mn.y, mx.z - mn.z)


def render_qa(name, length, height):
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_WORKBENCH'
    except TypeError:
        pass
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.render.resolution_x, scene.render.resolution_y = 640, 400
    cam = bpy.data.objects.new("QACam", bpy.data.cameras.new("QACam"))
    scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = max(length, height, 2.0) * 1.3
    d = Vector((-1.0, 1.4, 0.75)).normalized() * 30  # from the left-front: front is +Y, left is -X
    cam.location = d + Vector((0, 0, height * 0.5))
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    scene.render.filepath = os.path.join(QA, name + ".png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)


def want(vid):
    return not ONLY or vid in ONLY


# ------------------------------------------------------------------ passenger car pack
PASSENGER = {"car_compact": "Compact Body", "car_coupe": "Coupe Body", "car_hatchback": "Hatchback Body",
             "car_minivan": "minivan body", "car_offroad": "Offroad Body", "car_pickup": "Pickup Body",
             "car_sedan": "Sedan Body", "car_sport": "Sport body", "car_suv": "SUV Body", "car_wagon": "Wagon Body"}


def passenger_pack():
    for vid, body_name in PASSENGER.items():
        if not want(vid):
            continue
        load("generic_passenger_car_pack.glb")
        body_root = bpy.data.objects[body_name]
        body_meshes = [o for o in descendants(body_root) if o.type == 'MESH']
        mn, mx = bbox(body_meshes)
        centre = (mn + mx) / 2
        # Each wheel belongs to the body whose centre is nearest.
        centres = {}
        for n in PASSENGER.values():
            bm, bx = bbox([o for o in descendants(bpy.data.objects[n]) if o.type == 'MESH'])
            centres[n] = (bm + bx) / 2
        wheels = []
        for o in bpy.data.objects:
            if o.name.startswith("Wheel_") and o.type == 'EMPTY':
                wm, wx = bbox([m for m in descendants(o) if m.type == 'MESH'])
                wc = (wm + wx) / 2
                flat = lambda v: Vector((v.x, v.y))
                if min(centres, key=lambda n: (flat(centres[n]) - flat(wc)).length) == body_name:
                    wheels.append(o)
        # The pack lays the cars out in a ring, each facing the ring's centre.
        forward = principal_heading(body_meshes, Vector((-centre.x, -centre.y, 0)))
        body = bake(body_meshes, "Body")
        wheel_meshes = [bake([m for m in descendants(w) if m.type == 'MESH'], "WheelMesh") for w in wheels]
        clear_others([body] + wheel_meshes)
        normalise([body] + wheel_meshes, centre, forward)
        rig_vehicle(vid, [body], wheel_meshes, budget=12000, wheel_budget=600)


# ------------------------------------------------------------------ civil service pack
CIVIL = ["ambulance", "citybus", "fire_truck", "garbage_truck", "police_sedan", "postvan", "rdservtruck", "school_bus", "taxi", "towtruck"]


def civil_pack():
    for name in CIVIL:
        vid = "civil_" + name
        if not want(vid):
            continue
        load("generic_civil_service_vehicles_pack.glb")
        meshes = [o for o in descendants(bpy.data.objects[name]) if o.type == 'MESH']
        mn, mx = bbox(meshes)
        centre = (mn + mx) / 2
        # Unlike the passenger pack, these face away from the ring's centre.
        forward = principal_heading(meshes, Vector((centre.x, centre.y, 0)))
        main = max(meshes, key=lambda o: len(o.data.polygons))
        body = bake([main], "Main")
        extras = bake([m for m in meshes if m != main], "Extras")
        clear_others([body, extras])
        normalise([body, extras], centre, forward)
        body, wheels = find_tires(body, 0.0)
        rig_vehicle(vid, [body, extras], wheels, budget=14000, wheel_budget=500)


# ------------------------------------------------------------------ single cars
def sport_car():
    vid = "sport_car"
    if not want(vid):
        return
    load("car_for_games_unity.glb")
    groups = [o for o in bpy.data.objects if o.type == 'EMPTY' and "_Wheel" in o.name and "_LOD0" not in o.name]
    wheel_sets = [[m for m in descendants(g) if m.type == 'MESH'] for g in groups]
    in_wheel = {m for s in wheel_sets for m in s}
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o not in in_wheel]
    first = lambda o: o.data.materials[0].name if o.data.materials and o.data.materials[0] else ""
    paint = [o for o in meshes if first(o) == "Paint"]
    rest = [o for o in meshes if o not in paint and "Glow" not in first(o)]
    body = bake(rest, "Body")
    paint_mesh = bake(paint, "VehiclePaint")
    wheels = [bake(s, "WheelMesh") for s in wheel_sets]
    clear_others([body, paint_mesh] + wheels)
    normalise([body, paint_mesh] + wheels, Vector((0, 0, 0)), Vector((0, 1, 0)))
    rig_vehicle(vid, [body, paint_mesh], wheels, budget=20000, wheel_budget=900)


def police_crown_vic():
    vid = "police_interceptor"
    if not want(vid):
        return
    load("police_car.glb")
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    wheel_objs = [o for o in meshes if ".Wheel." in o.name]
    body = bake([o for o in meshes if o not in wheel_objs], "Body")
    wheels = [bake([w], "WheelMesh") for w in wheel_objs]
    clear_others([body] + wheels)
    mn, mx = bbox([body] + wheels)
    # Front wheels ("Ft") sit at -Y in the source; a Crown Victoria is 5.39 m long.
    normalise([body] + wheels, (mn + mx) / 2, Vector((0, -1, 0)), 5.39 / (mx.y - mn.y))
    rig_vehicle(vid, [body], wheels, budget=26000, wheel_budget=900)


def camaro():
    """1.3M-triangle source: decimate per part first, then split the wheel objects (which span
    both sides of the car) into four wheels by quadrant."""
    vid = "muscle_car"
    if not want(vid):
        return
    load("chevrolet_camero_car.glb")
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    wheel_roots = [o for o in bpy.data.objects if o.name.split("_")[0] in ("Cylinder", "Cylinder.001", "Cylinder.002", "Cylinder.003", "Cylinder.004", "Cylinder.005", "Plane.016", "Plane.023")]
    wheel_src = {m for r in wheel_roots for m in descendants(r) if m.type == 'MESH'}
    import time
    t0 = time.time()
    log = lambda m: print("  camaro %.0fs %s" % (time.time() - t0, m), flush=True)
    total = tris(meshes)
    log("loaded %d tris, %d wheel parts" % (total, len(wheel_src)))
    body = bake([m for m in meshes if m not in wheel_src], "Body")
    wheel_all = bake(list(wheel_src), "Wheels")
    clear_others([body, wheel_all])
    log("baked")
    decimate(body, 70000)
    log("body decimated")
    decimate(wheel_all, 36000)
    log("wheels decimated")
    mn, mx = bbox([body, wheel_all])
    print("  camaro", total, "->", tris([body, wheel_all]))
    normalise([body, wheel_all], (mn + mx) / 2, Vector((1, 0, 0)), 4.78 / (mx.x - mn.x))
    # Split by face centre into four wheels; faces near the centreline (axles) join the body.
    import bmesh
    def keep_faces(obj, test, name):
        dup = obj.copy()
        dup.data = obj.data.copy()
        dup.name = name
        bpy.context.scene.collection.objects.link(dup)
        bm = bmesh.new()
        bm.from_mesh(dup.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not test(f.calc_center_median())], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(dup.data)
        bm.free()
        return dup if dup.data.polygons else None
    wheels = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            w = keep_faces(wheel_all, lambda c, sx=sx, sy=sy: c.x * sx > 0.3 and c.y * sy > 0, "WheelMesh")
            if w:
                wheels.append(w)
    axle = keep_faces(wheel_all, lambda c: abs(c.x) <= 0.3, "Axle")
    bpy.data.objects.remove(wheel_all)
    body = join([body, axle], "Body")
    log("split into %d wheels" % len(wheels))
    rig_vehicle(vid, [body], wheels, budget=70000, wheel_budget=9000)


# ------------------------------------------------------------------ people
PEOPLE = {
    "tracksuit_man": ("goat_simulator_mobile_npc_2_tracksuit.glb", 1.78,
                      {"Idle_01": "Idle", "Walk": "Walk", "Walk_01": "Brisk", "Idle_03": "Wait", "Talking_01": "Talk",
                       "ChairIdle": "Sit", "idlecar_01": "Cycle", "Cellphone": "Phone", "Run": "Run"}),
    "casual_man": ("npc.glb", 1.77, {"mixamo.com": "Idle"}),
    "casual_woman": ("npc_2.glb", 1.68, {"mixamo.com": "Idle"}),
    "security_guard": ("security_guard__rigged_3d_model.glb", 1.82, {"idle": "Idle"}),
}


def people():
    for pid, (src, height, clips) in PEOPLE.items():
        if not want(pid):
            continue
        load(src)
        arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        top = arm
        while top.parent:
            top = top.parent
        keep = {}
        for a in list(bpy.data.actions):
            short = a.name.split("|")[-1]
            if short in clips and clips[short] not in keep.values():
                keep[a] = clips[short]
            else:
                bpy.data.actions.remove(a)
        for a, n in keep.items():
            a.name = n
            a.use_fake_user = True
        if arm.animation_data is None:
            arm.animation_data_create()
        # Measure on the walk pose when there is one (it is upright; the rest pose is not).
        idle = next((a for a, n in keep.items() if n == "Walk"), None) or next((a for a, n in keep.items() if n == "Idle"), None)
        if idle:
            arm.animation_data.action = idle
            if hasattr(arm.animation_data, "action_slot") and idle.slots:
                arm.animation_data.action_slot = idle.slots[0]
        bpy.context.scene.frame_set(0)
        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in meshes:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            pts += [ev.matrix_world @ v.co for v in me.vertices]
            ev.to_mesh_clear()
        zmin = min(p.z for p in pts)
        zmax = max(p.z for p in pts)
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        s = height / (zmax - zmin)
        holder = bpy.data.objects.new(pid, None)
        bpy.context.scene.collection.objects.link(holder)
        top.parent = holder
        # Sketchfab characters face -Y in Blender; the game wants +Y (Godot -Z).
        holder.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation((-cx, -cy, -zmin))
        holder["height"] = height
        holder["clips"] = ",".join(sorted(set(keep.values())))
        bpy.context.view_layer.update()
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT_P, pid + ".glb"), export_format='GLB', export_extras=True,
                                  export_yup=True, export_animations=True, export_animation_mode='ACTIONS',
                                  export_force_sampling=True, export_optimize_animation_size=True)
        print("EXPORTED", pid, "scale", round(s, 4), "clips", sorted(keep.values()), "tris", tris(meshes))
        render_qa(pid, 2.0, height)


passenger_pack()
civil_pack()
sport_car()
police_crown_vic()
camaro()
people()
