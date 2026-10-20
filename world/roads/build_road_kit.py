"""Deterministic Blender workshop for the neighbourhood street kit.

Run headless:  blender --background --python world/roads/build_road_kit.py
or execute inside a live Blender session (MCP execute_blender_code).

Builds modular, game-ready road pieces in a dedicated "RoadKit" scene, saves the
editable source to world/roads/source/road_kit.blend and exports one GLB per piece
to world/roads/. Blender +Y becomes Godot -Z, i.e. the direction of travel for the
right-hand (+X) lane. Pieces are centred on the origin; deck tops are at z=0.

Cross-sections (metres from the centreline):
  avenue (12 m): yellow 0.07-0.17 | car lane -3.70 | white 3.70-3.85 | bike lane -5.55 | gutter -6.00 | curb -6.20
  street (10 m): yellow 0.07-0.17 | car lane -3.10 | white 3.10-3.25 | bike lane -4.70 | gutter -5.00 | curb -5.20
"""
import bmesh
import bpy
import math
import os

ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\GodotProjects\delivery-simulator-2026\world\roads"
SEGMENT = 12.0  # module length along travel
PAINT_Z = 0.006  # thermoplastic paint height above the deck
SYMBOL_Z = 0.008  # symbols sit above the green lane fill

PROFILES = {
    "avenue": {"asphalt": 5.55, "gutter": 6.0, "curb": 6.2, "line": (3.70, 3.85)},
    "street": {"asphalt": 4.70, "gutter": 5.0, "curb": 5.2, "line": (3.10, 3.25)},
}

MATERIALS = {
    # name: (base colour, roughness). Godot replaces these with runtime shaders by name.
    "Asphalt": ((0.075, 0.078, 0.082), 0.92),
    "GutterConcrete": ((0.52, 0.51, 0.48), 0.85),
    "CurbConcrete": ((0.66, 0.65, 0.61), 0.8),
    "PaintWhite": ((0.86, 0.86, 0.82), 0.55),
    "PaintYellow": ((0.86, 0.66, 0.16), 0.55),
    "BikeLaneGreen": ((0.16, 0.42, 0.24), 0.7),
}


def material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    colour, rough = MATERIALS[name]
    bsdf.inputs["Base Color"].default_value = (*colour, 1)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


class Builder:
    """Accumulates faces per material, then emits one object."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _slot(self, mat_name):
        if mat_name not in self.mats:
            self.mats.append(mat_name)
        return self.mats.index(mat_name)

    def face(self, points, mat_name):
        verts = [self.bm.verts.new(p) for p in points]
        f = self.bm.faces.new(verts)
        f.material_index = self._slot(mat_name)
        return f

    def quad(self, x0, x1, y0, y1, z, mat_name):
        """Upward-facing rectangle."""
        return self.face([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], mat_name)

    def profile(self, points, y0, y1, mat_name):
        """Extrude an (x, z) polyline along Y; points ordered so normals face up/outward."""
        for (xa, za), (xb, zb) in zip(points, points[1:]):
            self.face([(xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za)], mat_name)

    def stroke(self, a, b, width, z, mat_name):
        """Flat bar between two (x, y) points."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy / length * width / 2, dx / length * width / 2
        return self.face([(a[0] - nx, a[1] - ny, z), (b[0] - nx, b[1] - ny, z),
                          (b[0] + nx, b[1] + ny, z), (a[0] + nx, a[1] + ny, z)], mat_name)

    def emit(self, name, collection):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        for f in self.bm.faces:
            f.smooth = False
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mat_name in self.mats:
            mesh.materials.append(material(mat_name))
        # Planar top-down UVs in metres keep the source textured sensibly in Blender.
        uv = mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            co = mesh.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = (co.x / 4.0, co.y / 4.0)
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        return obj


def deck(kind, collection):
    p = PROFILES[kind]
    b = Builder()
    y0, y1 = -SEGMENT / 2, SEGMENT / 2
    a, g, c = p["asphalt"], p["gutter"], p["curb"]
    b.quad(-a, a, y0, y1, 0.0, "Asphalt")
    for s in (-1, 1):
        # Gutter pan falls 12 mm toward the curb so the drainage line reads at grazing angles.
        gutter = [(s * a, 0.0), (s * g, -0.012)]
        curb = [(s * g, -0.012), (s * (g + 0.012), 0.062), (s * (g + 0.022), 0.078),
                (s * (g + 0.045), 0.085), (s * (c - 0.04), 0.085), (s * c, 0.02)]
        if s < 0:
            gutter.reverse()
            curb.reverse()
        b.profile(gutter, y0, y1, "GutterConcrete")
        b.profile(curb, y0, y1, "CurbConcrete")
        # Skirt hides the deck edge where it meets lower ground or a junction pad.
        b.profile([(s * c, 0.02), (s * c, -0.12)] if s > 0 else [(s * c, -0.12), (s * c, 0.02)], y0, y1, "CurbConcrete")
    return b.emit(f"{kind}_deck", collection)


def junction_pad(collection):
    b = Builder()
    b.quad(-0.5, 0.5, -0.5, 0.5, 0.0, "Asphalt")
    return b.emit("junction_pad", collection)


def marks_half(kind, collection):
    """Right-hand half of the lane markings: one centre yellow, edge line, green bike lane."""
    p = PROFILES[kind]
    b = Builder()
    y0, y1 = -SEGMENT / 2, SEGMENT / 2
    b.quad(0.07, 0.17, y0, y1, PAINT_Z, "PaintYellow")
    b.quad(p["line"][0], p["line"][1], y0, y1, PAINT_Z, "PaintWhite")
    b.quad(p["line"][1], p["asphalt"], y0, y1, PAINT_Z - 0.001, "BikeLaneGreen")
    return b.emit(f"{kind}_marks_half", collection)


def ring(b, cx, cy, r_out, r_in, stretch, z, mat_name, segments=28):
    for i in range(segments):
        a0, a1 = math.tau * i / segments, math.tau * (i + 1) / segments
        pts = [(cx + r_in * math.cos(a0), cy + r_in * math.sin(a0) * stretch),
               (cx + r_out * math.cos(a0), cy + r_out * math.sin(a0) * stretch),
               (cx + r_out * math.cos(a1), cy + r_out * math.sin(a1) * stretch),
               (cx + r_in * math.cos(a1), cy + r_in * math.sin(a1) * stretch)]
        b.face([(x, y, z) for x, y in pts], mat_name)


def bike_symbol(collection):
    """Upright bicycle pictogram plus arrow, stretched 2.2x along travel for driver perspective."""
    b = Builder()
    k = 2.2  # longitudinal stretch
    z = SYMBOL_Z
    base = -1.5  # shift so the whole symbol is centred on the origin

    def p(s, t):  # side-view (s across, t up) -> road (x, y)
        return (s, base + t * k)

    for hub in (-0.31, 0.31):
        ring(b, hub, base + 0.21 * k, 0.21, 0.165, k, z, "PaintWhite")
    w = 0.045
    rear, front, bb = p(-0.31, 0.21), p(0.31, 0.21), p(-0.03, 0.22)
    seat, head_low, head_top = p(-0.11, 0.47), p(0.21, 0.40), p(0.235, 0.5)
    for a, c in [(rear, bb), (bb, seat), (seat, rear), (bb, head_low), (seat, head_top),
                 (head_top, front), (seat, p(-0.115, 0.52)), (p(-0.19, 0.52), p(-0.04, 0.52)), (head_top, p(0.30, 0.56))]:
        b.stroke(a, c, w, z, "PaintWhite")
    # Arrow ahead of the bicycle.
    shaft_w, head_w = 0.13, 0.46
    y_shaft0, y_shaft1, y_tip = base + 1.65, base + 2.45, base + 3.0
    b.quad(-shaft_w / 2, shaft_w / 2, y_shaft0, y_shaft1, z, "PaintWhite")
    b.face([(-head_w / 2, y_shaft1, z), (head_w / 2, y_shaft1, z), (0, y_tip, z)], "PaintWhite")
    return b.emit("bike_symbol", collection)


def unit_paint(name, mat_name, z, collection):
    """1 x 1 m paint tile, scaled in Godot (stop bars, crosswalk bars, conflict dashes)."""
    b = Builder()
    b.quad(-0.5, 0.5, -0.5, 0.5, z, mat_name)
    return b.emit(name, collection)


def build():
    # Work in a collection of the active scene: selecting objects in an inactive
    # scene's view layer crashes Blender 5.2 during depsgraph evaluation.
    scene = bpy.context.scene
    col = bpy.data.collections.get("RoadKit")
    if col is None:
        col = bpy.data.collections.new("RoadKit")
        scene.collection.children.link(col)
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(mesh)
    pieces = [deck("avenue", col), deck("street", col), junction_pad(col),
              marks_half("avenue", col), marks_half("street", col), bike_symbol(col),
              unit_paint("paint_white_tile", "PaintWhite", PAINT_Z, col),
              unit_paint("bike_conflict_tile", "BikeLaneGreen", PAINT_Z - 0.001, col)]
    # Lay pieces out side by side so the source file is easy to inspect.
    for i, obj in enumerate(pieces):
        obj.location.x = i * 16.0
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
        report.append(f"{obj.name}: {tris} tris, materials={[m.name for m in obj.data.materials]}")
    source = os.path.join(ROOT, "source")
    os.makedirs(source, exist_ok=True)
    open(os.path.join(source, ".gdignore"), "w").close()
    with open(os.path.join(source, "manifest.txt"), "w") as fh:
        fh.write("\n".join(report) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(source, "road_kit.blend"), copy=True)
    print("\n".join(report))
    return scene


build()
