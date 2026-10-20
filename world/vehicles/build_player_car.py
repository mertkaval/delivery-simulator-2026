"""Player sedan: a clean, drivable game-ready car built to the reference photos (silver
mid-size sedan: slim LED headlights with a black horizontal grille, long raked rear screen,
5 twin-spoke alloys, red wrap-around tail lamps).

The supplied car_model.glb was a fused 404k-triangle scan with toy proportions and an
atlas texture, so this rebuilds the car from scratch:
  * body: lofted cross-sections through a subdivision surface (smooth, no lumps), wheel
    arches cut with booleans and lined, door seams, shoulder line, bumpers, sills
  * glass: separate transparent mesh (windscreen, side windows, rear screen), real interior
    behind it (dash, steering wheel, seats, console) so the cabin reads through the glass
  * lamps, grille, mirrors, handles, exhausts, plates
  * four wheels as separate meshes under empties: WheelFrontL/R under SteerFrontL/R (yaw),
    WheelRearL/R; a SteeringWheel empty turns with the steering input in Godot.
Frame: Blender Z up, car front = +Y (glTF export turns that into Godot -Z forward), origin on
the ground at the wheelbase centre. Dimensions in metres: 4.78 x 1.86 x 1.46, wheelbase 2.85.

Run headless:  blender --background --factory-startup --python build_player_car.py
Output: world/vehicles/player_sedan.glb
"""
import bpy, bmesh, math, os
from mathutils import Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_sedan.glb")
L, W, H = 4.78, 1.86, 1.46
WHEEL_Y = (1.44, -1.41)      # front, rear axle y
WHEEL_X = 0.79
WHEEL_R = 0.335
TYRE_W = 0.225
FLOOR_Z = 0.25

# ------------------------------------------------------------------------------ materials

def mat(name, rgb, rough=0.5, metal=0.0, alpha=1.0, emit=None, emit_strength=0.0, clearcoat=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = alpha
    if clearcoat:
        for key in ("Coat Weight", "Clearcoat"):
            if key in b.inputs:
                b.inputs[key].default_value = clearcoat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    return m


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


PAINT = mat("VehiclePaint", lin("c9ccd0"), 0.3, 0.85, clearcoat=1.0)
GLASS = mat("Glass", lin("22323a"), 0.05, 0.0, alpha=0.32)
TRIM = mat("BlackTrim", lin("131517"), 0.55)
GLOSS_BLACK = mat("GlossBlack", lin("0b0d10"), 0.15, 0.3)
CHROME = mat("Chrome", lin("e8eaec"), 0.12, 1.0)
RUBBER = mat("Rubber", lin("1a1c1e"), 0.9)
ALLOY = mat("Alloy", lin("c5c8cc"), 0.3, 0.9)
HEAD = mat("HeadLamp", lin("f2f4f6"), 0.1, 0.0, emit=lin("ffffff"), emit_strength=0.4)
TAIL = mat("TailLamp", lin("b4141c"), 0.15, 0.0, emit=lin("ff2a26"), emit_strength=0.6)
REFLECTOR = mat("Reflector", lin("5a5e63"), 0.2, 1.0)
INTERIOR = mat("Interior", lin("2a2b2e"), 0.8)
SEAT = mat("Seat", lin("3a3c42"), 0.85)
LINER = mat("ArchLiner", lin("0e0f10"), 0.95)
PLATE = mat("Plate", lin("f0efe8"), 0.5)

COL = None


def obj(name, bm, material, smooth=True, parent=None, location=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    o.location = location
    if parent:
        o.parent = parent
    COL.objects.link(o)
    return o


def empty(name, location, parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.1
    e.location = location
    if parent:
        e.parent = parent
    COL.objects.link(e)
    return e


def box(name, c, s, material, parent=None, rot=(0, 0, 0), bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=bevel, segments=2, affect="EDGES")
    o = obj(name, bm, material, smooth=bevel > 0, parent=parent, location=c)
    o.rotation_euler = rot
    return o


def cylinder(name, c, r, length, material, axis="x", n=24, parent=None, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r, radius2=r2 if r2 is not None else r, depth=length)
    if axis == "x":
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "Y"), verts=bm.verts)
    elif axis == "y":
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "X"), verts=bm.verts)
    return obj(name, bm, material, parent=parent, location=c)


# ------------------------------------------------------------------------------ body profile

def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def half_width(y):
    """Plan view half width of the lower body."""
    w = W / 2
    front = smoothstep(1.3, L / 2, y)          # taper into the nose
    rear = smoothstep(-1.2, -L / 2, y)         # taper into the tail
    return w - 0.24 * front ** 2.2 - 0.09 * rear ** 1.8


def belt_z(y):
    """Shoulder / belt line (top of the lower body)."""
    if y > 0.78:    # bonnet: from the windscreen base down to the nose
        t = (y - 0.78) / (L / 2 - 0.78)
        return 0.98 - 0.26 * t ** 1.15
    if y < -1.52:   # boot lid to the tail
        t = (-1.52 - y) / (L / 2 - 1.52)
        return 1.0 - 0.07 * t ** 1.4
    return 0.95 + 0.05 * smoothstep(0.78, -1.52, y)


def roof_z(y):
    """Top of the greenhouse / bonnet / boot."""
    if y > 0.78:
        return belt_z(y) + 0.02
    if y < -1.52:
        return belt_z(y) + 0.015
    # windscreen (0.78 .. 0.22), roof (0.22 .. -0.75), rear screen (-0.75 .. -1.52)
    if y > 0.22:
        t = (0.78 - y) / 0.56
        return 0.98 + 0.46 * math.sin(t * math.pi / 2) ** 1.1
    if y > -0.75:
        t = (0.22 - y) / 0.97
        return 1.44 + 0.02 * math.sin(t * math.pi)
    t = (y + 1.52) / 0.77      # 1 at the roof end .. 0 at the boot
    return 1.0 + 0.44 * math.sin(t * math.pi / 2) ** 0.9


def glass_half_width(y, z_frac):
    """Greenhouse half width at height fraction z_frac (0 belt, 1 roof)."""
    base = half_width(y) - 0.05
    top = min(0.70, base - 0.04)
    return base + (top - base) * z_frac ** 1.3


def has_greenhouse(y):
    return -1.52 <= y <= 0.78


SIDE_PTS = 8    # lower body points from the floor centre to the shoulder
GLASS_PTS = 7   # greenhouse points from the shoulder to the roof centre


def section(y):
    """Cross-section half profile (x >= 0) as (x, z) points, floor centre to roof centre."""
    w = half_width(y)
    zb = belt_z(y)
    zr = roof_z(y)
    pts = [(0.0, FLOOR_Z), (w * 0.86, FLOOR_Z), (w * 0.985, FLOOR_Z + 0.09), (w + 0.012, FLOOR_Z + 0.30),
           (w + 0.02, 0.62), (w + 0.01, zb - 0.16), (w * 0.985, zb - 0.05), (w * 0.955, zb)]
    if has_greenhouse(y):
        # soft shoulder then tumblehome glass up to a rounded roof
        for k in range(1, GLASS_PTS + 1):
            t = k / GLASS_PTS
            if k == GLASS_PTS:
                pts.append((0.0, zr))
            else:
                a = t * math.pi / 2
                # Superellipse: flat roof, rounded cant rail.
                x = glass_half_width(y, t) * math.cos(a) ** 0.4
                z = zb + (zr - zb) * (math.sin(a) ** 0.75)
                pts.append((x, z))
    else:
        # bonnet / boot: a flat crown with a rounded edge
        for k in range(1, GLASS_PTS + 1):
            t = k / GLASS_PTS
            a = t * math.pi / 2
            x = w * 0.955 * math.cos(a) ** 0.35
            z = zb + (zr - zb) * math.sin(a) ** 0.6
            pts.append((x if k < GLASS_PTS else 0.0, z))
    return pts


def stations():
    ys = []
    y = -L / 2
    while y < L / 2 - 1e-6:
        # Dense near the screens and bumpers where the profile bends.
        step = 0.10 if (0.5 < y < 1.0 or -1.7 < y < -0.6 or abs(y) > 1.9) else 0.16
        ys.append(y)
        y += step
    ys.append(L / 2)
    return ys


def build_body():
    bm = bmesh.new()
    ys = stations()
    rings = []
    for y in ys:
        prof = section(y)
        # mirror across x, drop duplicated centre points
        left = [(-x, y, z) for (x, z) in reversed(prof[1:-1])]
        right = [(x, y, z) for (x, z) in prof]
        ring = [bm.verts.new(p) for p in [(0, y, prof[0][1])] + [(x, y, z) for (x, z) in prof[1:]] + left]
        rings.append(ring)
    n = len(rings[0])
    glass_faces = []
    for i in range(len(rings) - 1):
        for j in range(n):
            k = (j + 1) % n
            f = bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
            y_mid = (ys[i] + ys[i + 1]) / 2
            # Points SIDE_PTS .. SIDE_PTS+GLASS_PTS-1 (and their mirrors) are the greenhouse.
            jj = j if j < n // 2 + 1 else n - j
            in_glass = SIDE_PTS <= jj < SIDE_PTS + GLASS_PTS - 1 and has_greenhouse(y_mid)
            if in_glass:
                glass_faces.append((i, j))
            f.material_index = 1 if in_glass else 0
    # End caps: nose and tail.
    for ring in (rings[0], rings[-1]):
        bm.faces.new(ring if ring is rings[-1] else list(reversed(ring)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Body")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(PAINT)
    me.materials.append(GLASS)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("Body", me)
    COL.objects.link(o)
    return o


def separate_glass(body):
    """Split greenhouse faces into their own object (Glass), leaving pillar bands painted.
    Pillars: A at the windscreen edges, B at y ~ -0.3, C along the rear screen edges."""
    me = body.data
    for p in me.polygons:
        if p.material_index != 1:
            continue
        c = p.center
        side = abs(p.normal.x) > 0.55            # side glass (vs screens)
        if side:
            # B pillar and the door-frame bands become paint; the rest stays glass.
            if -0.42 < c.y < -0.24 or c.y > 0.66 or c.y < -1.38:
                p.material_index = 0
        else:
            # Screens: a painted band at the outer edge reads as the A/C pillars.
            z_frac = (c.z - belt_z(c.y)) / max(0.05, roof_z(c.y) - belt_z(c.y))
            if abs(c.x) > glass_half_width(c.y, z_frac) * 0.84 and 0.1 < z_frac < 0.9 and abs(p.normal.y) < 0.75:
                p.material_index = 0
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    body.active_material_index = 1
    bpy.ops.object.material_slot_select()
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    glass = [o for o in bpy.context.selected_objects if o != body][0]
    glass.name = "Glass"
    glass.data.materials.clear()
    glass.data.materials.append(GLASS)
    body.data.materials.pop(index=1)
    return glass


def subdivide(o, levels=2):
    m = o.modifiers.new("Smooth surface", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=m.name)


def cut_arches(body):
    for y in WHEEL_Y:
        for sx in (-1, 1):
            cutter = cylinder("cutter", (sx * 0.78, y, WHEEL_R - 0.02), WHEEL_R + 0.085, 0.5, LINER, axis="x", n=40)
            m = body.modifiers.new("arch", "BOOLEAN")
            m.operation = "DIFFERENCE"
            m.object = cutter
            m.solver = "EXACT"
            bpy.context.view_layer.objects.active = body
            bpy.ops.object.modifier_apply(modifier=m.name)
            bpy.data.objects.remove(cutter, do_unlink=True)
            # Arch liner: a dark cup open towards the wheel (tube + inner wall only).
            bm = bmesh.new()
            rl = WHEEL_R + 0.08
            x_in, x_out = sx * 0.46, sx * 0.86
            ring_in = [bm.verts.new((x_in, y + rl * math.cos(i / 40 * math.tau), WHEEL_R - 0.02 + rl * math.sin(i / 40 * math.tau))) for i in range(40)]
            ring_out = [bm.verts.new((x_out, y + rl * math.cos(i / 40 * math.tau), WHEEL_R - 0.02 + rl * math.sin(i / 40 * math.tau))) for i in range(40)]
            for i in range(40):
                bm.faces.new((ring_in[i], ring_in[(i + 1) % 40], ring_out[(i + 1) % 40], ring_out[i]))
            bm.faces.new(ring_in)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            for f in bm.faces:
                f.normal_flip()  # faces point inwards: seen from inside the arch
            obj("ArchLiner", bm, LINER, smooth=True)


# ------------------------------------------------------------------------------ details

def side_strip(name, y, material, depth=0.004, thickness=0.012, z0=FLOOR_Z + 0.1, z1=None):
    """Thin dark seam following the side profile at station y (door shut lines)."""
    prof = section(y)
    z1 = z1 if z1 is not None else belt_z(y) - 0.01
    bm = bmesh.new()
    for sx in (-1, 1):
        pts = [(x, z) for (x, z) in prof[1:SIDE_PTS] if z0 <= z <= z1]
        pts = [(prof[1][0] * 0.98 + 0.02, z0)] + pts + [(prof[SIDE_PTS - 1][0], z1)]
        a = [bm.verts.new((sx * (x + depth), y - thickness / 2, z)) for (x, z) in pts]
        b = [bm.verts.new((sx * (x + depth), y + thickness / 2, z)) for (x, z) in pts]
        for i in range(len(pts) - 1):
            f = bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, bm, material, smooth=False)


def mirror(sx):
    base_y, z = 0.6, 1.0
    x = side_x(base_y, z, sx) - sx * 0.03
    arm = box("MirrorArm", (x + sx * 0.08, base_y, z), (0.16, 0.06, 0.035), PAINT)
    head = box("MirrorHead", (x + sx * 0.18, base_y - 0.02, z + 0.04), (0.12, 0.2, 0.13), PAINT, bevel=0.03)
    lens = box("MirrorLens", (x + sx * 0.18, base_y - 0.125, z + 0.04), (0.1, 0.005, 0.11), CHROME)
    return [arm, head, lens]


def handle(y, sx):
    x = side_x(y, 0.84, sx) + sx * 0.012
    return box("DoorHandle", (x, y, 0.84), (0.03, 0.2, 0.035), PAINT, bevel=0.01)


BODY = None


def hit(origin, direction):
    ok, loc, normal, _ = BODY.ray_cast(Vector(origin), Vector(direction))
    return loc if ok else None


def front_y(x, z):
    p = hit((x, 5.0, z), (0, -1, 0))
    return p.y if p else L / 2 - 0.1


def rear_y(x, z):
    p = hit((x, -5.0, z), (0, 1, 0))
    return p.y if p else -L / 2 + 0.1


def side_x(y, z, sx):
    p = hit((sx * 3.0, y, z), (-sx, 0, 0))
    return p.x if p else sx * half_width(y)


def top_z(x, y):
    p = hit((x, y, 5.0), (0, 0, -1))
    return p.z if p else roof_z(y)


def strip(name, samples, material, proud=0.004, depth=0.06, direction=1):
    """Surface-hugging band. samples are (x, z_centre, half_height); the band's top and bottom
    edges are each ray-cast onto the body so it follows the curved nose/tail in both plan and
    section, standing `proud` of the surface and extending `depth` into it."""
    bm = bmesh.new()
    prev = None
    for (x, z, h) in samples:
        ys = []
        for zz in (z - h, z + h):
            ys.append(front_y(x, zz) if direction > 0 else rear_y(x, zz))
        yb, yt = ys
        vs = [bm.verts.new((x, yb + direction * proud, z - h)), bm.verts.new((x, min(yb, yt) - direction * depth if direction > 0 else max(yb, yt) + depth, z - h)),
              bm.verts.new((x, (min(yb, yt) - direction * depth) if direction > 0 else (max(yb, yt) + depth), z + h)), bm.verts.new((x, yt + direction * proud, z + h))]
        if prev:
            for i in range(4):
                bm.faces.new((prev[i], prev[(i + 1) % 4], vs[(i + 1) % 4], vs[i]))
        prev = vs
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, bm, material, smooth=False)


def front_samples(xs, z_of, h, sign=1):
    """(x, z_centre, h) samples; z may follow the belt line, which depends on the surface y."""
    out = []
    for x in xs:
        z = z_of(0.0)
        for _ in range(2):
            y = front_y(x, z) if sign > 0 else rear_y(x, z)
            z = z_of(y)
        out.append((x, z, h))
    return out

def lamps():
    parts = []
    yf = L / 2
    for sx in (-1, 1):
        # Slim LED headlamp sweeping from the grille into the fender, hugging the nose.
        xs = [sx * v for v in (0.16, 0.3, 0.45, 0.6, 0.72, 0.82, 0.88)]
        parts.append(strip("HeadLamp", front_samples(xs, lambda y: belt_z(y) - 0.085, 0.045), HEAD, proud=0.003, depth=0.08))
        parts.append(strip("HeadLampTrim", front_samples(xs, lambda y: belt_z(y) - 0.138, 0.012), GLOSS_BLACK, proud=0.003, depth=0.04))
        for k in range(3):
            x = sx * (0.3 + k * 0.14)
            z = belt_z(front_y(x, 0.7)) - 0.085
            parts.append(cylinder("Projector", (x, front_y(x, z) - 0.02, z), 0.028, 0.03, GLOSS_BLACK, axis="y", n=14))
        # Fog light bezel set into the bumper corner.
        x = sx * 0.64
        parts.append(box("FogBezel", (x, front_y(x, 0.47) - 0.025, 0.47), (0.24, 0.06, 0.1), TRIM, bevel=0.015))
        parts.append(box("FogLamp", (x - sx * 0.04, front_y(x, 0.47) + 0.004, 0.46), (0.08, 0.012, 0.04), HEAD))
        # Tail lamps: red wrap-around band with a dark inner stripe, following the tail.
        xs_r = [sx * v for v in (0.2, 0.35, 0.5, 0.65, 0.78, 0.86)]
        parts.append(strip("TailLamp", front_samples(xs_r, lambda y: belt_z(y) - 0.11, 0.05, -1), TAIL, proud=0.003, depth=0.08, direction=-1))
        parts.append(strip("TailInner", front_samples(xs_r[:4], lambda y: belt_z(y) - 0.11, 0.012, -1), GLOSS_BLACK, proud=0.006, depth=0.02, direction=-1))
        x = sx * 0.62
        parts.append(box("RearReflector", (x, rear_y(x, 0.5) + 0.004, 0.5), (0.2, 0.012, 0.06), TAIL))
        x = sx * 0.45
        parts.append(cylinder("Exhaust", (x, rear_y(x, 0.3) + 0.02, 0.3), 0.04, 0.12, CHROME, axis="y", n=16))
    # Grille: gloss-black field with three chrome bars across the curved nose.
    xs = [v / 100.0 for v in range(-46, 47, 4)]
    parts.append(strip("GrilleField", front_samples(xs, lambda y: 0.63, 0.075), GLOSS_BLACK, proud=0.002, depth=0.05))
    for k in range(3):
        parts.append(strip("GrilleBar", front_samples(xs, lambda y, k=k: 0.58 + k * 0.05, 0.007), CHROME, proud=0.012, depth=0.01))
    parts.append(box("Badge", (0, front_y(0, 0.65) + 0.012, 0.65), (0.08, 0.012, 0.06), CHROME, bevel=0.01))
    # Lower intake, chrome lip, dark skirt and the plates.
    xs_w = [v / 100.0 for v in range(-56, 57, 4)]
    parts.append(strip("Intake", front_samples(xs_w, lambda y: 0.41, 0.08), GLOSS_BLACK, proud=0.002, depth=0.05))
    parts.append(strip("IntakeLip", front_samples(xs_w, lambda y: 0.325, 0.01), CHROME, proud=0.01, depth=0.01))
    xs_s = [v / 100.0 for v in range(-78, 79, 6)]
    parts.append(strip("FrontSkirt", front_samples(xs_s, lambda y: FLOOR_Z + 0.04, 0.045), TRIM, proud=0.006, depth=0.05))
    parts.append(strip("RearSkirt", front_samples(xs_s, lambda y: FLOOR_Z + 0.06, 0.07, -1), TRIM, proud=0.006, depth=0.05, direction=-1))
    parts.append(strip("RearDiffuser", front_samples([v / 100.0 for v in range(-50, 51, 5)], lambda y: FLOOR_Z + 0.02, 0.02, -1), GLOSS_BLACK, proud=0.012, depth=0.02, direction=-1))
    parts.append(box("FrontPlate", (0, front_y(0, 0.52) + 0.012, 0.52), (0.5, 0.008, 0.11), PLATE))
    parts.append(box("RearPlate", (0, rear_y(0, 0.72) - 0.012, 0.72), (0.5, 0.008, 0.11), PLATE))
    parts.append(box("RearBadge", (0, rear_y(0, 0.86) - 0.01, 0.86), (0.08, 0.008, 0.06), CHROME, bevel=0.01))
    # Dark sills under the doors.
    for sx in (-1, 1):
        parts.append(box("Sill", (side_x(0.0, FLOOR_Z + 0.06, sx) - sx * 0.02, 0.0, FLOOR_Z + 0.055), (0.06, 3.1, 0.11), TRIM, bevel=0.01))
    # Shark-fin antenna, wipers, cowl.
    parts.append(box("SharkFin", (0, -0.62, top_z(0, -0.62) + 0.025), (0.04, 0.16, 0.06), PAINT, bevel=0.012))
    for sx in (-0.45, 0.25):
        parts.append(box("Wiper", (sx, 0.76, top_z(sx, 0.76) + 0.015), (0.55, 0.02, 0.012), TRIM, rot=(0, 0, 0.35)))
    parts.append(box("Cowl", (0, 0.8, top_z(0, 0.8) + 0.002), (1.4, 0.08, 0.02), TRIM))
    return parts

def interior():
    parts = []
    parts.append(box("CabinFloor", (0, -0.3, 0.42), (1.5, 2.2, 0.04), INTERIOR))
    parts.append(box("Dashboard", (0, 0.55, 0.9), (1.5, 0.5, 0.26), INTERIOR, bevel=0.03))
    parts.append(box("DashTop", (0, 0.68, 1.03), (1.46, 0.3, 0.03), INTERIOR))
    parts.append(box("CentreScreen", (0, 0.33, 0.98), (0.3, 0.02, 0.16), GLOSS_BLACK))
    parts.append(box("Console", (0, -0.05, 0.6), (0.3, 1.0, 0.3), INTERIOR, bevel=0.02))
    parts.append(box("Cluster", (-0.38, 0.38, 1.0), (0.3, 0.04, 0.1), GLOSS_BLACK))
    for sx in (-1, 1):
        parts.append(box("Vent", (sx * 0.55, 0.32, 0.98), (0.2, 0.02, 0.06), GLOSS_BLACK))
        for y, name in ((-0.05, "FrontSeat"), (-0.95, "RearSeat")):
            parts.append(box(name + "Base", (sx * 0.38, y, 0.56), (0.5, 0.52, 0.16), SEAT, bevel=0.03))
            parts.append(box(name + "Back", (sx * 0.38, y - 0.22, 0.85), (0.5, 0.12, 0.6), SEAT, bevel=0.03, rot=(0.15, 0, 0)))
            parts.append(box(name + "Headrest", (sx * 0.38, y - 0.3, 1.22), (0.26, 0.1, 0.16), SEAT, bevel=0.03))
        parts.append(box("DoorCard", (sx * 0.86, -0.3, 0.72), (0.04, 2.0, 0.5), INTERIOR))
    parts.append(box("RearShelf", (0, -1.42, 1.0), (1.4, 0.5, 0.03), INTERIOR))
    # Steering wheel on its own pivot (left-hand drive), column raked 25 degrees.
    pivot = empty("SteeringWheel", (-0.38, 0.22, 0.93))
    pivot.rotation_euler = (math.radians(-65), 0, 0)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, segments=28, radius=0.185)
    rim_me = bpy.data.meshes.new("rim")
    # torus rim
    bm.free()
    bm = bmesh.new()
    torus_verts = []
    for i in range(28):
        a = i / 28 * math.tau
        ring = []
        for j in range(8):
            b = j / 8 * math.tau
            r = 0.185 + 0.018 * math.cos(b)
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0.018 * math.sin(b))))
        torus_verts.append(ring)
    for i in range(28):
        for j in range(8):
            bm.faces.new((torus_verts[i][j], torus_verts[i][(j + 1) % 8], torus_verts[(i + 1) % 28][(j + 1) % 8], torus_verts[(i + 1) % 28][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    rim = obj("WheelRim", bm, SEAT, parent=pivot)
    hub = cylinder("WheelHub", (0, 0, 0), 0.06, 0.05, INTERIOR, axis="z", n=16, parent=pivot)
    for ang in (0, 2.2, -2.2):
        sp = box("WheelSpoke", (0.09 * math.cos(ang), 0.09 * math.sin(ang), 0), (0.17, 0.035, 0.02), INTERIOR, parent=pivot, rot=(0, 0, ang))
        parts.append(sp)
    parts += [rim, hub]
    column = box("SteeringColumn", (-0.38, 0.33, 0.9), (0.08, 0.25, 0.08), INTERIOR, rot=(math.radians(25), 0, 0))
    parts.append(column)
    return parts


def wheel(name, pivot):
    """Tyre with a squarish shoulder and tread grooves, 5 twin-spoke alloy, hub cap."""
    parts = []
    # Tyre: loft of profile rings around the x axis.
    bm = bmesh.new()
    prof = [(-TYRE_W / 2, 0.245), (-TYRE_W / 2 + 0.01, 0.30), (-TYRE_W / 2 + 0.03, WHEEL_R - 0.004), (-TYRE_W / 2 + 0.05, WHEEL_R),
            (TYRE_W / 2 - 0.05, WHEEL_R), (TYRE_W / 2 - 0.03, WHEEL_R - 0.004), (TYRE_W / 2 - 0.01, 0.30), (TYRE_W / 2, 0.245)]
    n = 36
    rings = []
    for (x, r) in prof:
        rings.append([bm.verts.new((x, r * math.cos(i / n * math.tau), r * math.sin(i / n * math.tau))) for i in range(n)])
    for i in range(len(rings) - 1):
        for j in range(n):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % n], rings[i + 1][(j + 1) % n], rings[i + 1][j]))
    # Tread grooves: inset rings of faces.
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts.append(obj("Tyre_" + name, bm, RUBBER, parent=pivot))
    # Rim barrel and face.
    rim_r = 0.245
    # Open barrel (tube) so the spokes and the dark rim well read from outside.
    bm = bmesh.new()
    r0, r1 = rim_r - 0.02, rim_r
    ring_a = [bm.verts.new((-TYRE_W / 2 + 0.01, r1 * math.cos(i / 36 * math.tau), r1 * math.sin(i / 36 * math.tau))) for i in range(36)]
    ring_b = [bm.verts.new((TYRE_W / 2 - 0.01, r1 * math.cos(i / 36 * math.tau), r1 * math.sin(i / 36 * math.tau))) for i in range(36)]
    ring_c = [bm.verts.new((TYRE_W / 2 - 0.01, r0 * math.cos(i / 36 * math.tau), r0 * math.sin(i / 36 * math.tau))) for i in range(36)]
    ring_d = [bm.verts.new((-TYRE_W / 2 + 0.01, r0 * math.cos(i / 36 * math.tau), r0 * math.sin(i / 36 * math.tau))) for i in range(36)]
    for ra, rb in ((ring_a, ring_b), (ring_b, ring_c), (ring_c, ring_d), (ring_d, ring_a)):
        for i in range(36):
            bm.faces.new((ra[i], ra[(i + 1) % 36], rb[(i + 1) % 36], rb[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts.append(obj("Barrel_" + name, bm, ALLOY, parent=pivot))
    face = cylinder("RimFace_" + name, (TYRE_W / 2 - 0.07, 0, 0), rim_r - 0.015, 0.02, GLOSS_BLACK, axis="x", n=36, parent=pivot)
    parts.append(face)
    # Five twin spokes.
    for k in range(5):
        a = k / 5 * math.tau
        for off in (-0.028, 0.028):
            sp = box("Spoke_" + name, (TYRE_W / 2 - 0.035, 0.125 * math.cos(a) + off * -math.sin(a), 0.125 * math.sin(a) + off * math.cos(a)), (0.035, 0.028, 0.22), ALLOY, parent=pivot)
            sp.rotation_euler = (a + math.pi / 2, 0, 0)
            parts.append(sp)
    parts.append(cylinder("Hub_" + name, (TYRE_W / 2 - 0.03, 0, 0), 0.06, 0.03, ALLOY, axis="x", n=20, parent=pivot))
    parts.append(cylinder("Cap_" + name, (TYRE_W / 2 - 0.012, 0, 0), 0.03, 0.006, CHROME, axis="x", n=16, parent=pivot))
    parts.append(cylinder("Disc_" + name, (0, 0, 0), 0.16, 0.03, REFLECTOR, axis="x", n=24, parent=pivot))
    return parts


def build():
    global COL
    scene = bpy.context.scene
    for o in list(scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    COL = scene.collection
    body = build_body()
    glass = separate_glass(body)
    subdivide(body, 2)
    subdivide(glass, 2)
    # Glass sits 6 mm inside the paint surface so the pillar edges catch the light.
    for v in glass.data.vertices:
        v.co.x *= 0.995
    cut_arches(body)
    bpy.context.view_layer.objects.active = body
    body.modifiers.new("Smooth normals", "WEIGHTED_NORMAL")
    bpy.ops.object.modifier_apply(modifier="Smooth normals")
    global BODY
    BODY = body
    # Door shut lines and the bonnet / boot gaps.
    for y in (0.62, -0.32, -1.3):
        side_strip("DoorSeam", y, TRIM)
    for sx in (-1, 1):
        for p in mirror(sx):
            pass
        handle(0.2, sx)
        handle(-0.78, sx)
    lamps()
    interior()
    root_y = (WHEEL_Y[0] + WHEEL_Y[1]) / 2
    for (y, front) in ((WHEEL_Y[0], True), (WHEEL_Y[1], False)):
        for sx, side in ((-1, "L"), (1, "R")):
            name = ("Front" if front else "Rear") + side
            if front:
                steer = empty("Steer" + name, (sx * WHEEL_X, y, WHEEL_R))
                pivot = empty("Wheel" + name, (0, 0, 0), parent=steer)
            else:
                pivot = empty("Wheel" + name, (sx * WHEEL_X, y, WHEEL_R))
            wheel(name, pivot)
            if sx < 0:
                for child in pivot.children:
                    child.scale.x = -1   # mirror the rim face to the outside
    # Root: ground origin at the wheelbase centre, with gameplay metadata (glTF extras).
    root = empty("PlayerSedan", (0, 0, 0))
    root["wheelbase"] = WHEEL_Y[0] - WHEEL_Y[1]
    root["collision_lift"] = 0.08
    for o in list(scene.objects):
        if o is not root and o.parent is None:
            o.parent = root
            o.location.y -= root_y
    for o in scene.objects:
        if o.type == "MESH":
            o.data.validate()
            # CityAssets.tint() recolours meshes whose node name contains "VehiclePaint".
            if o.data.materials and o.data.materials[0] is PAINT and "VehiclePaint" not in o.name:
                o.name = o.name + "_VehiclePaint"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_extras=True, export_yup=True)
    tris = sum(len(p.vertices) - 2 for o in scene.objects if o.type == "MESH" for p in o.data.polygons)
    print("PLAYER_SEDAN triangles", tris, "objects", len(scene.objects), "->", OUT)


build()
