"""Street technology kit: traffic-signal poles, mast arms, signal heads, pedestrian signals,
push buttons and LED sign frames for the delivery city.

Run headless:
  blender --background --factory-startup --python world/streets/build_street_tech.py
or inside a live Blender session (MCP execute_blender_code).

Builds every piece in a dedicated "StreetTech" collection (never clears anything else), saves
the editable source to world/streets/source/street_tech.blend and exports one GLB per piece to
world/streets/. Units are metres, Blender Z up. glTF turns Blender -Y into Godot +Z, so:
  * signal heads, pedestrian heads, buttons, lenses and wall LED boards FACE Blender -Y
    (Godot +Z); their origin is the mounting point (top of a hanging head, back of a wall piece),
  * mast arms run along +X from the pole axis,
  * poles stand on the origin.
Materials are named for the Godot side (TrafficSignals / LedBoards replace the lens, symbol
and screen materials at runtime by name): SignalSteel, SignalBlack, SignalYellow, Lens,
PedHand, PedWalk, LedFrame, LedScreen, LedBracket.
"""
import bmesh
import bpy
import math
import os
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\GodotProjects\delivery-simulator-2026\world\streets"

MATERIALS = {
    # name: (base colour (linear), metallic, roughness)
    "SignalSteel": ((0.42, 0.43, 0.42), 0.8, 0.38),   # hot-dip galvanised
    "SignalBlack": ((0.018, 0.019, 0.021), 0.1, 0.55),  # powder-coated aluminium housings
    "SignalYellow": ((0.86, 0.58, 0.02), 0.0, 0.42),   # retroreflective backplate border
    "Lens": ((0.08, 0.08, 0.08), 0.0, 0.12),
    "PedHand": ((0.9, 0.35, 0.05), 0.0, 0.3),
    "PedWalk": ((0.9, 0.9, 0.85), 0.0, 0.3),
    "LedFrame": ((0.03, 0.032, 0.036), 0.65, 0.32),    # black anodised extrusion
    "LedScreen": ((0.01, 0.01, 0.012), 0.0, 0.18),
    "LedBracket": ((0.30, 0.31, 0.31), 0.85, 0.4),
}


def material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    colour, metal, rough = MATERIALS[name]
    bsdf.inputs["Base Color"].default_value = (*colour, 1)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    return mat


class Builder:
    """Accumulates geometry per material in one bmesh, then emits one object."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []
        self.uv_faces = {}  # face -> [(u, v)] explicit UVs (screens)

    def slot(self, mat_name):
        if mat_name not in self.mats:
            self.mats.append(mat_name)
        return self.mats.index(mat_name)

    def _take(self, geom_verts, mat_name, smooth):
        faces = set()
        for v in geom_verts:
            for f in v.link_faces:
                faces.add(f)
        for f in faces:
            f.material_index = self.slot(mat_name)
            f.smooth = smooth
        return faces

    def box(self, lo, hi, mat_name, bevel=0.0):
        lo, hi = Vector(lo), Vector(hi)
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        verts = res["verts"]
        size = hi - lo
        centre = (hi + lo) * 0.5
        bmesh.ops.transform(self.bm, matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*size, 1.0)), verts=verts)
        if bevel > 0.0:
            edges = list({e for v in verts for e in v.link_edges})
            res2 = bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, segments=2, affect="EDGES", profile=0.5)
            verts = list({v for f in res2["faces"] for v in f.verts} | set(v for v in verts if v.is_valid))
        return self._take([v for v in verts if v.is_valid], mat_name, bevel > 0.0)

    def cylinder(self, a, b, r0, r1, mat_name, segments=16, caps=True, smooth=True):
        """Tapered cylinder from point a (radius r0) to point b (radius r1)."""
        a, b = Vector(a), Vector(b)
        axis = b - a
        length = axis.length
        res = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=segments,
                                    radius1=r0, radius2=r1, depth=length)
        rot = Vector((0, 0, 1)).rotation_difference(axis.normalized()).to_matrix().to_4x4()
        bmesh.ops.transform(self.bm, matrix=Matrix.Translation((a + b) * 0.5) @ rot, verts=res["verts"])
        faces = self._take(res["verts"], mat_name, smooth)
        if caps:
            for f in faces:
                # Flat cap faces stay flat-shaded.
                if abs(f.normal.normalized().dot(axis.normalized())) > 0.95:
                    f.smooth = False
        return faces

    def dome(self, centre, radius, sag, normal, mat_name, segments=20, rings=4):
        """Spherical cap (lens) of `radius` bulging `sag` along `normal`, with a flat back."""
        centre, normal = Vector(centre), Vector(normal).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(normal).to_matrix()
        # Sphere radius through the rim and the apex.
        R = (radius * radius + sag * sag) / (2 * sag)
        rings_v = []
        for k in range(rings + 1):
            t = k / rings
            rr = radius * (1 - t)
            z = math.sqrt(max(R * R - rr * rr, 0.0)) - (R - sag)
            ring = []
            for i in range(segments if k < rings else 1):
                a = math.tau * i / segments
                p = Vector((rr * math.cos(a), rr * math.sin(a), z))
                ring.append(self.bm.verts.new(centre + rot @ p))
            rings_v.append(ring)
        faces = []
        for k in range(rings):
            ra, rb = rings_v[k], rings_v[k + 1]
            for i in range(segments):
                if len(rb) == 1:
                    faces.append(self.bm.faces.new((ra[i], ra[(i + 1) % segments], rb[0])))
                else:
                    faces.append(self.bm.faces.new((ra[i], ra[(i + 1) % segments], rb[(i + 1) % segments], rb[i])))
        back = self.bm.faces.new(list(reversed(rings_v[0])))
        for f in faces:
            f.material_index = self.slot(mat_name)
            f.smooth = True
        back.material_index = self.slot(mat_name)
        return faces

    def visor(self, centre, r_in, r_out, depth, mat_name, start_deg=-35.0, end_deg=215.0, segments=18):
        """Cut-away tunnel visor round a lens facing -Y: an open-bottom shell projecting forward."""
        cx, cy, cz = centre
        outer_front, outer_back, inner_front, inner_back = [], [], [], []
        for i in range(segments + 1):
            a = math.radians(start_deg + (end_deg - start_deg) * i / segments)
            ca, sa = math.cos(a), math.sin(a)
            # The visor tips down a little at the front, like the real hoods.
            droop = 0.012
            outer_back.append(self.bm.verts.new((cx + r_out * ca, cy, cz + r_out * sa)))
            outer_front.append(self.bm.verts.new((cx + r_out * ca, cy - depth, cz + r_out * sa - droop)))
            inner_back.append(self.bm.verts.new((cx + r_in * ca, cy, cz + r_in * sa)))
            inner_front.append(self.bm.verts.new((cx + r_in * ca, cy - depth, cz + r_in * sa - droop)))
        faces = []
        for i in range(segments):
            faces.append(self.bm.faces.new((outer_back[i], outer_back[i + 1], outer_front[i + 1], outer_front[i])))
            faces.append(self.bm.faces.new((inner_back[i + 1], inner_back[i], inner_front[i], inner_front[i + 1])))
            faces.append(self.bm.faces.new((outer_front[i], outer_front[i + 1], inner_front[i + 1], inner_front[i])))
        for end in (0, segments):
            q = (outer_back[end], outer_front[end], inner_front[end], inner_back[end])
            faces.append(self.bm.faces.new(q if end == 0 else tuple(reversed(q))))
        for f in faces:
            f.material_index = self.slot(mat_name)
            f.smooth = True
        return faces

    def quad_uv(self, corners, uvs, mat_name):
        """One quad with explicit UVs (v = 1 at the top in Blender; glTF flips it)."""
        verts = [self.bm.verts.new(c) for c in corners]
        f = self.bm.faces.new(verts)
        f.material_index = self.slot(mat_name)
        f.smooth = False
        self.uv_faces[f] = uvs
        return f

    def polygon(self, points2d, y, mat_name, scale=1.0, offset=(0.0, 0.0)):
        """Flat filled polygon in the XZ plane at depth y, facing -Y (triangulated)."""
        verts = [self.bm.verts.new((offset[0] + x * scale, y, offset[1] + z * scale)) for x, z in points2d]
        f = self.bm.faces.new(verts)
        if f.normal.y > 0:
            f.normal_flip()
        res = bmesh.ops.triangulate(self.bm, faces=[f])
        for t in res["faces"]:
            t.material_index = self.slot(mat_name)
            t.smooth = False
        return res["faces"]

    def stroke(self, a, b, width, y, mat_name):
        """Flat bar in the XZ plane between (x, z) points a and b, facing -Y."""
        ax, az = a
        bx, bz = b
        dx, dz = bx - ax, bz - az
        length = math.hypot(dx, dz)
        nx, nz = -dz / length * width / 2, dx / length * width / 2
        pts = [(ax - nx, az - nz), (bx - nx, bz - nz), (bx + nx, bz + nz), (ax + nx, az + nz)]
        return self.polygon(pts, y, mat_name)

    def disc(self, centre_xz, radius, y, mat_name, segments=16):
        cx, cz = centre_xz
        pts = [(cx + radius * math.cos(math.tau * i / segments), cz + radius * math.sin(math.tau * i / segments)) for i in range(segments)]
        return self.polygon(pts, y, mat_name)

    def emit(self, name, collection):
        bmesh.ops.remove_doubles(self.bm, verts=[v for v in self.bm.verts], dist=1e-6)
        mesh = bpy.data.meshes.new(name)
        uv_lookup = {}
        uv_layer = self.bm.loops.layers.uv.new("UVMap")
        for f in self.bm.faces:
            if f in self.uv_faces:
                for loop, uv in zip(f.loops, self.uv_faces[f]):
                    loop[uv_layer].uv = uv
            else:
                # Box projection in metres for everything else.
                n = f.normal
                for loop in f.loops:
                    co = loop.vert.co
                    if abs(n.z) > abs(n.x) and abs(n.z) > abs(n.y):
                        loop[uv_layer].uv = (co.x, co.y)
                    elif abs(n.x) > abs(n.y):
                        loop[uv_layer].uv = (co.y, co.z)
                    else:
                        loop[uv_layer].uv = (co.x, co.z)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mat_name in self.mats:
            mesh.materials.append(material(mat_name))
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        return obj


# ----------------------------------------------------------------------------- poles

def pole_base(b, collar_r, collar_h):
    b.box((-0.24, -0.24, 0.0), (0.24, 0.24, 0.035), "SignalSteel", bevel=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cylinder((sx * 0.18, sy * 0.18, 0.035), (sx * 0.18, sy * 0.18, 0.075), 0.022, 0.022, "SignalSteel", segments=6, smooth=False)
    b.cylinder((0, 0, 0.035), (0, 0, collar_h), collar_r, collar_r * 0.82, "SignalSteel", segments=8, smooth=False)


def mast(length, collection):
    """Mast-arm signal pole: 6.4 m tapered pole with an arm along +X at 5.75 m."""
    b = Builder()
    pole_base(b, 0.2, 0.42)
    b.cylinder((0, 0, 0.42), (0, 0, 6.4), 0.128, 0.092, "SignalSteel", segments=18)
    b.dome((0, 0, 6.4), 0.094, 0.05, (0, 0, 1), "SignalSteel", segments=18, rings=3)
    # Hand-hole cover low on the street side.
    b.box((-0.05, -0.135, 0.75), (0.05, -0.115, 0.95), "SignalSteel", bevel=0.005)
    # Arm: clamp collar, flange plates, tapered tube rising slightly, end cap.
    zc = 5.75
    b.cylinder((0, 0, zc - 0.22), (0, 0, zc + 0.22), 0.118, 0.118, "SignalSteel", segments=18)
    b.box((0.10, -0.16, zc - 0.17), (0.14, 0.16, zc + 0.17), "SignalSteel", bevel=0.006)
    rise = 0.012 * length
    b.cylinder((0.14, 0, zc), (length, 0, zc + rise), 0.088, 0.052, "SignalSteel", segments=14)
    b.dome((length, 0, zc + rise), 0.052, 0.025, (1, 0, rise / length), "SignalSteel", segments=14, rings=2)
    # Diagonal gusset strut for longer arms.
    if length > 5.5:
        b.cylinder((0.1, 0, zc - 0.95), (1.5, 0, zc + 0.02 * 1.5 - 0.02), 0.03, 0.026, "SignalSteel", segments=8)
    return b.emit("signal_mast_%d" % round(length), collection)


def post(collection):
    """Plain 3.6 m post for pedestrian signals and side-mounted heads."""
    b = Builder()
    pole_base(b, 0.14, 0.32)
    b.cylinder((0, 0, 0.32), (0, 0, 3.6), 0.072, 0.062, "SignalSteel", segments=14)
    b.dome((0, 0, 3.6), 0.064, 0.035, (0, 0, 1), "SignalSteel", segments=14, rings=3)
    return b.emit("signal_post", collection)


# ----------------------------------------------------------------------------- heads

SECTION = 0.40     # 300 mm lens sections
LENS_R = 0.138
DEPTH = 0.24


def signal_head(collection):
    """Three-section vehicle signal (red/amber/green, 300 mm), hanging from its origin.
    Lens centres (Godot local, metres): (0, -0.28 - 0.40 k, +0.122) for k = 0 red, 1 amber, 2 green."""
    b = Builder()
    top = -0.08
    # Hanger: pipe and a top bracket.
    b.cylinder((0, 0, 0.0), (0, 0, top + 0.01), 0.028, 0.028, "SignalBlack", segments=10)
    b.box((-0.07, -0.06, top - 0.005), (0.07, 0.06, top + 0.03), "SignalBlack", bevel=0.008)
    for k in range(3):
        zc = top - SECTION * (k + 0.5)
        b.box((-SECTION / 2 + 0.005, -DEPTH / 2, zc - SECTION / 2 + 0.004), (SECTION / 2 - 0.005, DEPTH / 2, zc + SECTION / 2 - 0.004), "SignalBlack", bevel=0.018)
        # Lens bezel ring and the visor.
        b.cylinder((0, -DEPTH / 2 - 0.012, zc), (0, -DEPTH / 2 + 0.002, zc), LENS_R + 0.02, LENS_R + 0.02, "SignalBlack", segments=20, caps=False)
        b.visor((0, -DEPTH / 2 - 0.005, zc), LENS_R + 0.012, LENS_R + 0.022, 0.24, "SignalBlack")
    # Backplate with a retroreflective yellow border, 2.5 cm behind the housing.
    w, h = 0.78, SECTION * 3 + 0.28
    zt, zb = top + 0.14, top - SECTION * 3 - 0.14
    yb = DEPTH / 2 + 0.01
    b.box((-w / 2, yb, zb), (w / 2, yb + 0.012, zt), "SignalBlack")
    border = 0.05
    for lo, hi in [((-w / 2, zt - border), (w / 2, zt)), ((-w / 2, zb), (w / 2, zb + border)),
                   ((-w / 2, zb + border), (-w / 2 + border, zt - border)), ((w / 2 - border, zb + border), (w / 2, zt - border))]:
        b.box((lo[0], yb - 0.003, lo[1]), (hi[0], yb + 0.001, hi[1]), "SignalYellow")
    # Struts joining the backplate to the housing.
    for sx in (-1, 1):
        for zz in (zt - 0.25, zb + 0.25):
            b.box((sx * 0.14 - 0.015, DEPTH / 2 - 0.01, zz - 0.015), (sx * 0.14 + 0.015, yb, zz + 0.015), "SignalBlack")
    return b.emit("signal_head", collection)


def lens(collection):
    """One 300 mm lens facing -Y, centred on the origin (Godot: instanced per lamp)."""
    b = Builder()
    b.dome((0, 0, 0), LENS_R, 0.028, (0, -1, 0), "Lens", segments=24, rings=4)
    return b.emit("signal_lens", collection)


PED = 0.34


def ped_head(collection):
    """Two-section pedestrian signal (hand above, walking figure below) on a pole clamp.
    Origin: back of the clamp on the pole surface. Symbol centres (Godot local):
    hand (0, -0.21, +0.247), walk (0, -0.55, +0.247)."""
    b = Builder()
    back, front = -0.045, -0.245
    b.box((-0.06, back, -0.74), (0.06, 0.0, -0.65), "SignalBlack", bevel=0.006)   # lower clamp
    b.box((-0.06, back, -0.10), (0.06, 0.0, -0.01), "SignalBlack", bevel=0.006)   # upper clamp
    for k in range(2):
        zc = -0.04 - PED * (k + 0.5)
        b.box((-PED / 2, front, zc - PED / 2 + 0.004), (PED / 2, back, zc + PED / 2 - 0.004), "SignalBlack", bevel=0.014)
        # Hood: top plate and side cheeks.
        b.box((-PED / 2, front - 0.12, zc + PED / 2 - 0.018), (PED / 2, front + 0.005, zc + PED / 2 - 0.004), "SignalBlack")
        for sx in (-1, 1):
            x0, x1 = sorted((sx * (PED / 2 - 0.012), sx * PED / 2))
            b.box((x0, front - 0.12, zc - PED / 2 + 0.05), (x1, front + 0.005, zc + PED / 2 - 0.004), "SignalBlack")
    return b.emit("ped_head", collection)


def ped_symbols(collection):
    """Upraised hand and walking figure as flat shapes facing -Y, ~0.24 m tall, centred."""
    hand = Builder()
    y = 0.0
    hand.polygon([(-0.075, -0.115), (0.06, -0.115), (0.075, -0.07), (0.075, 0.03), (-0.075, 0.03), (-0.085, -0.07)], y, "PedHand")
    for i, (x, top) in enumerate([(-0.058, 0.085), (-0.02, 0.11), (0.018, 0.105), (0.055, 0.075)]):
        hand.stroke((x, 0.0), (x, top), 0.03, y - 0.0004 * (i + 1), "PedHand")
        hand.disc((x, top), 0.015, y - 0.0004 * (i + 1), "PedHand", segments=10)
    hand.stroke((-0.07, -0.04), (-0.115, 0.02), 0.032, y - 0.002, "PedHand")
    hand.disc((-0.115, 0.02), 0.016, y - 0.002, "PedHand", segments=10)
    a = hand.emit("ped_hand", collection)
    walk = Builder()
    walk.disc((0.01, 0.095), 0.024, y, "PedWalk", segments=14)
    w = 0.026
    neck, hip = (0.0, 0.06), (-0.012, -0.025)
    for i, (p, q) in enumerate([(neck, hip), (neck, (-0.045, 0.01)), ((-0.045, 0.01), (-0.06, -0.035)),
                                (neck, (0.04, 0.02)), ((0.04, 0.02), (0.065, -0.01)),
                                (hip, (-0.045, -0.07)), ((-0.045, -0.07), (-0.07, -0.115)),
                                (hip, (0.025, -0.07)), ((0.025, -0.07), (0.04, -0.118)), ((0.04, -0.118), (0.062, -0.118))]):
        walk.stroke(p, q, w, y - 0.0004 * (i + 1), "PedWalk")
        walk.disc(q, w / 2, y - 0.0004 * (i + 1), "PedWalk", segments=8)
    c = walk.emit("ped_walk", collection)
    return [a, c]


def ped_button(collection):
    """Push-button box with an arrow plate; origin at the back (pole side), faces -Y."""
    b = Builder()
    b.box((-0.055, -0.07, -0.09), (0.055, 0.0, 0.09), "SignalYellow", bevel=0.01)
    b.box((-0.05, -0.074, -0.03), (0.05, -0.069, 0.08), "SignalBlack")
    b.cylinder((0, -0.07, -0.055), (0, -0.088, -0.055), 0.026, 0.024, "SignalSteel", segments=14)
    b.polygon([(-0.03, 0.025), (0.015, 0.025), (0.015, 0.045), (0.04, 0.02), (0.015, -0.005), (0.015, 0.015), (-0.03, 0.015)], -0.0745, "PedWalk")
    return b.emit("ped_button", collection)


# ----------------------------------------------------------------------------- LED signs

def led_wall(collection, name="led_board_wall", screen_w=2.40, screen_h=0.46):
    """Wall-mounted LED marquee: anodised frame, glass-fronted LED screen, stand-off brackets.
    Origin on the wall (back centre); faces -Y. Screen UV 0..1 left to right, v=1 at the top."""
    b = Builder()
    rim = 0.045
    W, H = screen_w + 2 * rim, screen_h + 2 * rim
    back, front = -0.06, -0.15
    b.box((-W / 2, front + 0.012, -H / 2), (W / 2, back, H / 2), "LedFrame", bevel=0.01)
    # Raised bezel lips round the screen.
    for lo, hi in [((-W / 2, H / 2 - rim), (W / 2, H / 2)), ((-W / 2, -H / 2), (W / 2, -H / 2 + rim)),
                   ((-W / 2, -H / 2 + rim), (-W / 2 + rim, H / 2 - rim)), ((W / 2 - rim, -H / 2 + rim), (W / 2, H / 2 - rim))]:
        b.box((lo[0], front, lo[1]), (hi[0], front + 0.014, hi[1]), "LedFrame", bevel=0.004)
    sx, sz = screen_w / 2, screen_h / 2
    ys = front + 0.006
    b.quad_uv([(-sx, ys, -sz), (sx, ys, -sz), (sx, ys, sz), (-sx, ys, sz)], [(0, 0), (1, 0), (1, 1), (0, 1)], "LedScreen")
    # Stand-off brackets and a cable conduit up the wall.
    for x in (-W / 2 + 0.3, W / 2 - 0.3):
        b.box((x - 0.03, back, -0.12), (x + 0.03, 0.0, 0.12), "LedBracket", bevel=0.004)
        b.box((x - 0.07, -0.008, -0.16), (x + 0.07, 0.0, 0.16), "LedBracket")
    b.cylinder((W / 2 - 0.12, -0.03, H / 2 - 0.02), (W / 2 - 0.12, -0.03, H / 2 + 0.45), 0.014, 0.014, "LedBracket", segments=8)
    # Ventilation slots along the bottom edge.
    for i in range(9):
        x = -W / 2 + 0.2 + i * (W - 0.4) / 8
        b.box((x - 0.05, front + 0.03, -H / 2 - 0.003), (x + 0.05, back - 0.01, -H / 2 + 0.002), "LedScreen")
    return b.emit(name, collection)


def led_blade(collection, screen_l=1.30, screen_h=0.40):
    """Double-sided projecting LED sign on a wall bracket. The board runs out from the wall along
    -Y; its screens face +X and -X, each reading left to right for its viewer.
    Origin on the wall at the bracket; screen centre at (0, -0.95, -0.36) Blender."""
    b = Builder()
    rim = 0.04
    L, H, T = screen_l + 2 * rim, screen_h + 2 * rim, 0.13
    y0, y1 = -0.22, -0.22 - L
    zc = -0.36
    b.box((-T / 2, y1, zc - H / 2), (T / 2, y0, zc + H / 2), "LedFrame", bevel=0.01)
    # Wall plate and two bracket arms (top one longer, scrolled end).
    b.box((-0.07, -0.012, zc - 0.32), (0.07, 0.0, zc + 0.30), "LedBracket", bevel=0.004)
    for z, reach in ((zc + H / 2 + 0.06, y1 - 0.06), (zc - 0.05, y0)):
        b.box((-0.018, reach, z - 0.018), (0.018, -0.01, z + 0.018), "LedBracket", bevel=0.004)
    b.cylinder((0, y1 - 0.06, zc + H / 2 + 0.06), (0, y1 - 0.06, zc + H / 2 + 0.005), 0.012, 0.012, "LedBracket", segments=8)
    b.cylinder((0, y0 - 0.2, zc + H / 2 + 0.06), (0, y0 - 0.2, zc + H / 2 + 0.005), 0.012, 0.012, "LedBracket", segments=8)
    ya, yb = y0 - rim, y1 + rim
    za, zb = zc - screen_h / 2, zc + screen_h / 2
    x = T / 2 + 0.002
    # +X face: its viewer's right is +Y (toward the wall), so u grows with y.
    b.quad_uv([(x, yb, za), (x, ya, za), (x, ya, zb), (x, yb, zb)], [(0, 0), (1, 0), (1, 1), (0, 1)], "LedScreen")
    # -X face: its viewer's right is -Y (away from the wall).
    b.quad_uv([(-x, ya, za), (-x, yb, za), (-x, yb, zb), (-x, ya, zb)], [(0, 0), (1, 0), (1, 1), (0, 1)], "LedScreen")
    return b.emit("led_board_blade", collection)


def build():
    scene = bpy.context.scene
    col = bpy.data.collections.get("StreetTech")
    if col is None:
        col = bpy.data.collections.new("StreetTech")
        scene.collection.children.link(col)
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(mesh)
    pieces = [mast(4.6, col), mast(6.6, col), mast(8.6, col), post(col), signal_head(col), lens(col),
              ped_head(col), *ped_symbols(col), ped_button(col), led_wall(col), led_blade(col),
              led_wall(col, "led_board_long", 3.40, 0.46)]
    for i, obj in enumerate(pieces):
        obj.location.x = i * 4.0
    os.makedirs(ROOT, exist_ok=True)
    report = []
    for obj in pieces:
        loc = obj.location.copy()
        obj.location = (0, 0, 0)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = os.path.join(ROOT, obj.name + ".glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB",
                                  export_yup=True, export_apply=True, export_normals=True,
                                  export_texcoords=True, export_materials="EXPORT")
        obj.location = loc
        tris = sum(len(poly.vertices) - 2 for poly in obj.data.polygons)
        dims = obj.dimensions
        report.append(f"{obj.name}: {tris} tris, {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f} m, materials={[m.name for m in obj.data.materials]}")
    source = os.path.join(ROOT, "source")
    os.makedirs(source, exist_ok=True)
    open(os.path.join(source, ".gdignore"), "w").close()
    with open(os.path.join(source, "manifest.txt"), "w") as fh:
        fh.write("\n".join(report) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(source, "street_tech.blend"), copy=True)
    print("\n".join(report))


build()
