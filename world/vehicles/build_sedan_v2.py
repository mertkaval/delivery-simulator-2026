"""Sedan v2 — G3 body-surface milestone build.

Builds the creased subdivision body shell from sedan_body.py, then (all on the applied mesh,
plane cuts + extrusions + insets, no booleans):
  * trims the side glass with the raked A-pillar line and the forward-leaning C-pillar line, and
    the windscreen / rear screen with their plan-view side lines (bmesh bisect_plane);
  * separates Glass (side glass 12 mm, screens 5 mm inboard along the shell normal, with a 15 mm
    black ceramic band at the screen edges) and the BPillar band (14 mm inboard, black);
  * extrudes the daylight-opening rim inward 12 mm as a black window-surround step wall;
  * cuts the G4 apertures (headlamps, grille, lower intake, tail lamps, fuel flap, mirror pads)
    with an 8-10 mm inset floor (BlackTrim) at the dimension-sheet positions;
  * lines the wheel arches, adds proportion-check wheels, exports production/wip/sedan_v2_body.glb
    and writes a build report next to it.

Run headless:  blender --background --factory-startup --python build_sedan_v2.py
"""
import bpy, bmesh, math, os, sys, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import sedan_body as SB
importlib.reload(SB)

OUT_DIR = os.path.join(SB.HERE, "production", "wip")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "sedan_v2_body.glb")
GLASS_INSET_SIDE = 0.012
GLASS_INSET_SCREEN = 0.005
PILLAR_INSET = 0.014
CERAMIC_BAND = 0.015


def mat(name, rgb, rough=0.5, metal=0.0, alpha=1.0, clearcoat=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = alpha
    for key in ("Coat Weight", "Clearcoat"):
        if clearcoat and key in b.inputs:
            b.inputs[key].default_value = clearcoat
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    return m


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


scene = bpy.context.scene
for o in list(scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)

PAINT = mat("VehiclePaint", lin("c9ccd0"), 0.3, 0.85, clearcoat=1.0)
GLASS = mat("Glass", lin("22323a"), 0.05, 0.0, alpha=0.3)
TRIM = mat("BlackTrim", lin("131517"), 0.6)
LINER = mat("ArchLiner", lin("0e0f10"), 0.95)
RUBBER = mat("Rubber", lin("1a1c1e"), 0.9)
ALLOY = mat("Alloy", lin("c5c8cc"), 0.3, 0.9)
# zone placeholders (indices 3..5 are build-time only)
Z_PILLAR = mat("zone_pillar", (0, 0, 0))
Z_WS = mat("zone_windscreen", (0, 0, 0))
Z_RS = mat("zone_rearscreen", (0, 0, 0))

report = {"version": "g3", "stations": {}, "checks": {}}

body = SB.build_body("Body", [PAINT, GLASS, TRIM, Z_PILLAR, Z_WS, Z_RS], subdiv=2)
SB.apply_modifiers(body)


def key(co):
    return (round(co.x, 5), round(co.y, 5), round(co.z, 5))


# ------------------------------------------------------------------ 1. trim the glass zones
bm = bmesh.new()
bm.from_mesh(body.data)
bm.faces.ensure_lookup_table()


def bisect(bm, faces, co, no, dist=0.004):
    geom = list(faces) + list({e for f in faces for e in f.edges}) + list({v for f in faces for v in f.verts})
    bmesh.ops.bisect_plane(bm, geom=geom, dist=dist, plane_co=co, plane_no=no)


for co, no, zone_idx in SB.dlo_planes():
    faces = [f for f in bm.faces if f.material_index == zone_idx]
    bisect(bm, faces, co, no)
    for f in bm.faces:
        if f.material_index == zone_idx and (f.calc_center_median() - co).dot(no) < 0:
            f.material_index = 0
for f in bm.faces:
    if f.material_index in (4, 5):
        f.material_index = 1
bm.normal_update()
NORMALS = {key(v.co): v.normal.copy() for v in bm.verts}      # closed-shell normals, used for every inset
bm.to_mesh(body.data)
bm.free()

# ------------------------------------------------------------------ 2. separate glass, pillar, skirt
glass = SB.separate_material(body, 1, "Glass")
pillar = SB.separate_material(body, 3, "BPillar") if any(p.material_index == 3 for p in body.data.polygons) else None
trim = SB.separate_material(body, 2, "BumperSkirt") if any(p.material_index == 2 for p in body.data.polygons) else None
for o, mats in ((glass, [GLASS, TRIM]), (pillar, [TRIM]), (trim, [TRIM, TRIM])):   # skirt slot 1 = intake aperture floor
    if o is not None:
        o.data.materials.clear()
        for m in mats:
            o.data.materials.append(m)
        for p in o.data.polygons:
            p.material_index = 0
body.data.materials.clear()
body.data.materials.append(PAINT)
body.data.materials.append(TRIM)
for p in body.data.polygons:
    p.material_index = 0


def boundary_keys(o):
    b = bmesh.new()
    b.from_mesh(o.data)
    ks = {key(v.co) for e in b.edges if e.is_boundary for v in e.verts}
    b.free()
    return ks


def offset_along_normals(o, dist):
    b = bmesh.new()
    b.from_mesh(o.data)
    b.normal_update()
    for v in b.verts:
        n = NORMALS.get(key(v.co), v.normal)
        v.co -= n * dist
    b.to_mesh(o.data)
    b.free()


dlo_keys = boundary_keys(glass) | (boundary_keys(pillar) if pillar is not None else set())
RIM_DEPTH = {}            # boundary vertex key -> inset depth, filled by the glass/pillar stage below

# ------------------------------------------------------------------ 3. window-surround step wall
body_vert_count = len(body.data.vertices)
body_face_count = len(body.data.polygons)
bm = bmesh.new()
bm.from_mesh(body.data)
rim = [e for e in bm.edges if e.is_boundary and all(key(v.co) in dlo_keys for v in e.verts)]
res = bmesh.ops.extrude_edge_only(bm, edges=rim)
new_faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
rim_verts = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
bm.to_mesh(body.data)
bm.free()


def glass_classes(o):
    """Per boundary-vertex key: True when the vertex belongs to a screen (flat) glass component."""
    b = bmesh.new()
    b.from_mesh(o.data)
    b.normal_update()
    seen, out = set(), {}
    for f in b.faces:
        if f.index in seen:
            continue
        comp, stack = [], [f]
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        screen = sum(abs(g.normal.z) for g in comp) / len(comp) > 0.72
        for g in comp:
            for v in g.verts:
                out[key(v.co)] = screen
    b.free()
    return out


for k, screen in glass_classes(glass).items():
    RIM_DEPTH[k] = GLASS_INSET_SCREEN if screen else GLASS_INSET_SIDE
if pillar is not None:
    for k in boundary_keys(pillar):
        RIM_DEPTH.setdefault(k, PILLAR_INSET)
bm = bmesh.new()
bm.from_mesh(body.data)
bm.verts.ensure_lookup_table()
for v in bm.verts:
    if v.index >= body_vert_count:          # the freshly extruded rim copies
        n = NORMALS.get(key(v.co))
        if n is not None:
            v.co -= n * RIM_DEPTH.get(key(v.co), GLASS_INSET_SIDE)
new_faces = [f for f in bm.faces if f.index >= body_face_count]
for f in new_faces:
    f.material_index = 1
    f.smooth = True
    for e in f.edges:
        e.smooth = False
report["checks"]["dlo_rim_edges"] = len(rim)
bm.to_mesh(body.data)
bm.free()

# ------------------------------------------------------------------ 4. apertures (plane cuts + inset floor)


def cut_aperture(bm, ap, sx):
    xlo, xhi = ap["x"]
    ylo, yhi = ap["y"]
    zlo, zhi = ap["z"]
    pad = 0.06

    centred = xlo == 0.0

    def inside(c, m=0.0):
        cx = abs(c.x) if centred else sx * c.x
        return (xlo - m) < cx < (xhi + m) and (ylo - m) < c.y < (yhi + m) and (zlo - m) < c.z < (zhi + m)

    planes = []
    for bound in (xlo, xhi):
        if 0.0 < bound < 5.0:
            if centred:
                planes.append((Vector((bound, 0, 0)), Vector((1, 0, 0))))
                planes.append((Vector((-bound, 0, 0)), Vector((1, 0, 0))))
            else:
                planes.append((Vector((sx * bound, 0, 0)), Vector((1, 0, 0))))
    for bound in (ylo, yhi):
        if abs(bound) < 5.0:
            planes.append((Vector((0, bound, 0)), Vector((0, 1, 0))))
    for bound in (zlo, zhi):
        planes.append((Vector((0, 0, bound)), Vector((0, 0, 1))))
    for co, no in planes:
        faces = [f for f in bm.faces if inside(f.calc_center_median(), pad)]
        if faces:
            bisect(bm, faces, co, no, dist=0.0015)
    region = [f for f in bm.faces if inside(f.calc_center_median())]
    if not region:
        return 0
    # Sink the floor along the smooth shell vertex normals (not the inset's per-face average, which
    # wobbles at the nose-cap pole): inset with depth 0, then translate the region's vertices.
    bm.normal_update()
    from mathutils import kdtree
    pre = [(v.co.copy(), v.normal.copy()) for v in {v for f in region for v in f.verts}]
    kd = kdtree.KDTree(len(pre))
    for i, (co, _) in enumerate(pre):
        kd.insert(co, i)
    kd.balance()
    res = bmesh.ops.inset_region(bm, faces=region, thickness=0.0008, depth=0.0, use_even_offset=True, use_boundary=True)
    walls = res["faces"]
    for v in {v for f in region for v in f.verts}:        # inset re-creates the region's vertices
        _, i, _ = kd.find(v.co)
        v.co -= pre[i][1] * ap["depth"]
    for f in region + walls:
        f.material_index = 1
        f.smooth = True
    for f in walls:
        for e in f.edges:
            e.smooth = False
    return len(region)


report["apertures"] = {}
for target in (body, trim):
    if target is None:
        continue
    bm = bmesh.new()
    bm.from_mesh(target.data)
    for ap in SB.APERTURES:
        if (ap.get("target", "body") == "skirt") != (target is trim):
            continue
        sides = (1, -1) if ap.get("mirror") else (ap.get("side", 1),)
        for sx in sides:
            n = cut_aperture(bm, ap, sx)
            report["apertures"][f"{ap['name']}_{'L' if sx < 0 else 'R'}" if len(sides) > 1 or "side" in ap else ap["name"]] = n
    bm.to_mesh(target.data)
    bm.free()
    for p in target.data.polygons:
        p.use_smooth = True

# ------------------------------------------------------------------ 5. glass: ceramic band + inset
bm = bmesh.new()
bm.from_mesh(glass.data)
bm.normal_update()
seen = set()
components = []
for f in bm.faces:
    if f.index in seen:
        continue
    comp, stack = [], [f]
    seen.add(f.index)
    while stack:
        g = stack.pop()
        comp.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen:
                    seen.add(h.index)
                    stack.append(h)
    components.append(comp)
glass_offsets = {}
report["glass_components"] = []
for comp in components:
    nz = sum(abs(f.normal.z) for f in comp) / len(comp)
    screen = nz > 0.72          # side glass has ~31 deg tumblehome (|nz| ~0.5); screens are flatter than 44 deg
    if screen:
        # Black ceramic band: the boundary face row (subdivided faces are 15-35 mm here), plus any
        # face whose centre lies within CERAMIC_BAND of the boundary edge.
        comp_set = set(comp)
        bedges = [e for f in comp for e in f.edges if e.is_boundary]
        # group consecutive boundary edges into straight runs (direction within 4 deg)
        runs, used = [], set()
        adj = {}
        for e in bedges:
            for v in e.verts:
                adj.setdefault(v, []).append(e)
        for e0 in bedges:
            if e0 in used:
                continue
            run = [e0]
            used.add(e0)
            for end in (0, 1):
                e, v = e0, e0.verts[end]
                while True:
                    nxt = [x for x in adj.get(v, []) if x not in used]
                    if not nxt:
                        break
                    d0 = (e.verts[1].co - e.verts[0].co).normalized()
                    d1 = (nxt[0].verts[1].co - nxt[0].verts[0].co).normalized()
                    if abs(d0.dot(d1)) < math.cos(math.radians(4)):
                        break
                    e = nxt[0]
                    used.add(e)
                    run.append(e)
                    v = e.other_vert(v)
            runs.append(run)
        cuts = []
        for run in runs:
            pts = [v.co for e in run for v in e.verts]
            a, b = min(pts, key=lambda p: (p.y, p.z, p.x)), max(pts, key=lambda p: (p.y, p.z, p.x))
            d = (b - a)
            if d.length < 0.02:
                continue
            d.normalize()
            n_surf = sum((f.normal for e in run for f in e.link_faces if f in comp_set), Vector()).normalized()
            inward = n_surf.cross(d).normalized()
            mid = (a + b) / 2
            inner = sum((f.calc_center_median() for e in run for f in e.link_faces if f in comp_set), Vector()) / max(1, sum(1 for e in run for f in e.link_faces if f in comp_set))
            if (inner - mid).dot(inward) < 0:
                inward = -inward
            cuts.append((mid + inward * CERAMIC_BAND, inward, a, b, d))
        for co, no, a, b, d in cuts:
            near = [f for f in bm.faces if f in comp_set or f.material_index in (0, 1)]
            near = [f for f in comp_set if abs((f.calc_center_median() - co).dot(no)) < 0.05
                    and -0.03 < (f.calc_center_median() - a).dot(d) < (b - a).length + 0.03]
            if near:
                res = bmesh.ops.bisect_plane(bm, geom=list(near) + list({e for f in near for e in f.edges}) + list({v for f in near for v in f.verts}),
                                             dist=0.0005, plane_co=co, plane_no=no)
                comp_set |= {g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMFace)}
                comp_set |= {g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)}
        comp = [f for f in comp_set if f.is_valid]
        bedges = [e for f in comp for e in f.edges if e.is_boundary]
        for f in comp:
            c = f.calc_center_median()
            for e in bedges:
                a, b = e.verts[0].co, e.verts[1].co
                ab = b - a
                t = max(0.0, min(1.0, (c - a).dot(ab) / max(ab.length_squared, 1e-12)))
                if (c - (a + ab * t)).length < CERAMIC_BAND + 0.0005:
                    f.material_index = 1
                    break
    for f in comp:
        for v in f.verts:
            glass_offsets[v] = GLASS_INSET_SCREEN if screen else GLASS_INSET_SIDE
    cy = sum(f.calc_center_median().y for f in comp) / len(comp)
    report["glass_components"].append({"faces": len(comp), "screen": screen, "centre_y": round(cy, 3)})
for f in bm.faces:
    f.smooth = True
    for v in f.verts:
        glass_offsets.setdefault(v, GLASS_INSET_SCREEN)
bm.normal_update()
for v in bm.verts:
    n = NORMALS.get(key(v.co), v.normal)
    v.co -= n * glass_offsets[v]
bm.to_mesh(glass.data)
bm.free()
if pillar is not None:
    offset_along_normals(pillar, PILLAR_INSET)
    for p in pillar.data.polygons:
        p.use_smooth = True

# ------------------------------------------------------------------ 6. arches, normals, wheels
SB.cut_wheel_arches(body, liner_material=LINER)
bpy.context.view_layer.objects.active = body
wn = body.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
wn.keep_sharp = True
bpy.ops.object.modifier_apply(modifier="Weighted normals")

# Proportion-check wheels (G2): tyre profile + rim barrel; the detailed assembly is G4 work.
for y in (SB.AXLE_F, SB.AXLE_R):
    for sx in (-1, 1):
        bm = bmesh.new()
        tw = SB.DIM["tyre_width"]
        prof = [(-tw / 2, 0.245), (-tw / 2 + 0.012, 0.3), (-tw / 2 + 0.035, SB.WHEEL_R - 0.005), (-tw / 2 + 0.06, SB.WHEEL_R),
                (tw / 2 - 0.06, SB.WHEEL_R), (tw / 2 - 0.035, SB.WHEEL_R - 0.005), (tw / 2 - 0.012, 0.3), (tw / 2, 0.245)]
        n = 40
        rings = [[bm.verts.new((x, r * math.cos(i / n * math.tau), r * math.sin(i / n * math.tau))) for i in range(n)] for (x, r) in prof]
        for a in range(len(rings) - 1):
            for i in range(n):
                bm.faces.new((rings[a][i], rings[a][(i + 1) % n], rings[a + 1][(i + 1) % n], rings[a + 1][i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new("Tyre")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(RUBBER)
        for p in me.polygons:
            p.use_smooth = True
        tyre = bpy.data.objects.new("Tyre", me)
        tyre.location = (sx * SB.TRACK_X, y, SB.WHEEL_R)
        scene.collection.objects.link(tyre)
        rb = bmesh.new()
        bmesh.ops.create_cone(rb, cap_ends=True, segments=36, radius1=0.245, radius2=0.245, depth=tw - 0.03)
        bmesh.ops.rotate(rb, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "Y"), verts=rb.verts)
        rme = bpy.data.meshes.new("Rim")
        rb.to_mesh(rme)
        rb.free()
        rme.materials.append(ALLOY)
        rim = bpy.data.objects.new("Rim", rme)
        rim.location = (sx * SB.TRACK_X, y, SB.WHEEL_R)
        scene.collection.objects.link(rim)

for o in scene.objects:
    if o.type == "MESH":
        o.data.validate()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "sedan_v2_body.blend"))

# ------------------------------------------------------------------ 7. build report (cage-side measurements)
report["stations"] = {"Y_NOSE": SB.Y_NOSE, "Y_FRONT_cage": SB.Y_FRONT, "Y_REAR_cage": SB.Y_REAR, "Y_COWL": SB.Y_COWL,
                      "Y_WS_TOP": SB.Y_WS_TOP, "Y_ROOF_END": SB.Y_ROOF_END, "Y_TRUNK": SB.Y_TRUNK, "Y_A_PILLAR": SB.Y_A_PILLAR,
                      "Y_B_PILLAR": SB.Y_B_PILLAR, "Y_C_PILLAR": SB.Y_C_PILLAR, "door_gaps": SB.GAPS,
                      "hood_front_gap": SB.Y_FRONT - SB.HOOD_FRONT, "hood_rear_gap": SB.Y_COWL - 0.02,
                      "trunk_gaps": [SB.Y_TRUNK + 0.01, SB.Y_REAR + 0.36]}
report["shoulder_z_cage"] = {str(y): round(SB.section(y)[SB.SHOULDER][1], 4) for y in (2.0, 1.0, 0.0, -1.15, -2.0)}
report["body_vertices"] = len(body.data.vertices)
report["objects"] = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in scene.objects if o.type == "MESH"}
tris = sum(report["objects"].values())
report["triangles_total"] = tris
json.dump(report, open(os.path.join(OUT_DIR, "sedan_v2_body_build_report.json"), "w"), indent=1)
print("SEDAN_V2_BODY", json.dumps({"triangles": tris, "objects": len(scene.objects), "dims": {k: SB.DIM[k] for k in ("length", "width", "height", "wheelbase")}}), "->", OUT)
