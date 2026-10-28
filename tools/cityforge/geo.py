"""CityForge mesh builder: plain-Python polygons with materials, UVs and colours.

Kept free of bpy so the geometry is fast to build in bulk and easy to test; `to_object` turns a
Mesh into a Blender object. Coordinates are Blender's (metres, +Z up, +Y = north / a model's front).
Faces are wound counter-clockwise seen from outside.
"""
import math


class Mesh:
    def __init__(self):
        self.v = []          # [x, y, z]
        self.f = []          # (vertex indices, material, uvs or None, colour or None, uv z-base)
        self.uv2 = {}        # face index -> second UV set (roads: marking data)
        self.smooth = set()  # face indices shaded smooth (tree crowns)

    def poly(self, pts, mat, uv=None, col=None, zb=0.0, uv2=None, smooth=False):
        base = len(self.v)
        if smooth: self.smooth.add(len(self.f))
        self.v.extend([float(p[0]), float(p[1]), float(p[2])] for p in pts)
        if uv2 is not None: self.uv2[len(self.f)] = uv2
        self.f.append((list(range(base, base + len(pts))), mat, uv, col, zb))

    def box(self, x0, y0, z0, x1, y1, z1, mat, col=None, top=True, bottom=False, zb=None):
        """Axis-aligned box; zb sets the facade UV base height (defaults to the box bottom)."""
        if x0 > x1: x0, x1 = x1, x0
        if y0 > y1: y0, y1 = y1, y0
        if z0 > z1: z0, z1 = z1, z0
        b = z0 if zb is None else zb
        if top: self.poly([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat, col=col, zb=b)
        if bottom: self.poly([(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], mat, col=col, zb=b)
        self.poly([(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], mat, col=col, zb=b)
        self.poly([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], mat, col=col, zb=b)
        self.poly([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], mat, col=col, zb=b)
        self.poly([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], mat, col=col, zb=b)

    def obox(self, cx, cy, z0, sx, sy, z1, yaw, mat, col=None, top=True, zb=None):
        """Box of size sx * sy centred on (cx, cy), turned by yaw about +Z."""
        sub = Mesh()
        sub.box(-sx / 2, -sy / 2, z0, sx / 2, sy / 2, z1, mat, col, top=top, zb=zb)
        self.append(sub, yaw, (cx, cy, 0.0))

    def cylinder(self, cx, cy, z0, z1, r0, r1, mat, sides=8, col=None, cap=True):
        ring0 = [(cx + r0 * math.cos(2 * math.pi * k / sides), cy + r0 * math.sin(2 * math.pi * k / sides), z0) for k in range(sides)]
        ring1 = [(cx + r1 * math.cos(2 * math.pi * k / sides), cy + r1 * math.sin(2 * math.pi * k / sides), z1) for k in range(sides)]
        for k in range(sides):
            n = (k + 1) % sides
            self.poly([ring0[k], ring0[n], ring1[n], ring1[k]], mat, col=col)
        if cap: self.poly(ring1, mat, col=col)

    def append(self, other, yaw=0.0, offset=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
        c, s = math.cos(yaw), math.sin(yaw)
        base = len(self.v)
        self.smooth.update(fi + len(self.f) for fi in other.smooth)
        for fi, uv2 in other.uv2.items():
            self.uv2[fi + len(self.f)] = uv2
        for x, y, z in other.v:
            x, y, z = x * scale[0], y * scale[1], z * scale[2]
            self.v.append([x * c - y * s + offset[0], x * s + y * c + offset[1], z + offset[2]])
        for idx, mat, uv, col, zb in other.f:
            self.f.append(([i + base for i in idx], mat, uv, col, zb + offset[2]))

    def tris(self):
        return sum(len(f[0]) - 2 for f in self.f)


def face_uvs(pts, normal, zb):
    """Metres-based UVs: walls get (along the wall, height above zb), flat faces get (x, y)."""
    nx, ny, nz = normal
    if abs(nz) > 0.7:
        return [(p[0], p[1]) for p in pts]
    L = math.hypot(nx, ny) or 1.0
    tx, ty = -ny / L, nx / L
    return [(p[0] * tx + p[1] * ty, p[2] - zb) for p in pts]


def newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % len(pts)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / L, ny / L, nz / L


def to_object(mesh, name, materials, smooth=False, weld=False, uvs=True):
    """Blender object from a Mesh. materials: name -> bpy material (created on demand by the caller)."""
    import bpy
    verts = mesh.v
    faces = [f[0] for f in mesh.f]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    mat_names = []
    for f in mesh.f:
        if f[1] not in mat_names: mat_names.append(f[1])
    for mn in mat_names: me.materials.append(materials[mn])
    me.polygons.foreach_set("material_index", [mat_names.index(f[1]) for f in mesh.f])
    uvl = me.uv_layers.new(name="UVMap")
    uv_flat = []
    has_col = any(f[3] is not None for f in mesh.f)
    col_flat = []
    for idx, mat, uv, col, zb in mesh.f:
        pts = [verts[i] for i in idx]
        uvs = uv if uv is not None else face_uvs(pts, newell(pts), zb)
        for u in uvs: uv_flat.extend(u)
        if has_col:
            c = col if col is not None else (1.0, 1.0, 1.0, 1.0)
            per_corner = isinstance(c[0], (tuple, list))     # a colour per corner, or one for the face
            for k in range(len(idx)):
                ck = c[k] if per_corner else c
                col_flat.extend(ck if len(ck) == 4 else (ck[0], ck[1], ck[2], 1.0))
    uvl.data.foreach_set("uv", uv_flat)
    if mesh.uv2:
        uv2l = me.uv_layers.new(name="UV2")
        flat2 = []
        for fi, f in enumerate(mesh.f):
            flat2.extend(c for u in mesh.uv2.get(fi, [(0.0, 0.0)] * len(f[0])) for c in u)
        uv2l.data.foreach_set("uv", flat2)
        me.uv_layers.active_index = 0
    if has_col:
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")     # exact values: some colours are data
        ca.data.foreach_set("color", col_flat)
    if not uvs:                      # parts whose shaders work in world space export no UVs
        me.uv_layers.remove(me.uv_layers[0])
        while len(me.uv_layers): me.uv_layers.remove(me.uv_layers[0])
    if weld:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        me.shade_smooth()
    elif mesh.smooth:
        me.polygons.foreach_set("use_smooth", [fi in mesh.smooth for fi in range(len(mesh.f))])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    return ob
