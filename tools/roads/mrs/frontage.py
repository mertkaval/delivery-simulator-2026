"""Street frontage (v5): a shop / delivery destination built from the game's existing city kit.

The building is assembled from the facade modules in world/citykit/modules (the same GLBs, module rules and
`Kit*` material names the downtown district uses, world/downtown/district.gd::build_building), so Godot
gives it the game's own materials (CityKit.material) and Blender gets matching triplanar materials made
from the same texture sets (world/citykit/textures).

A frontage is a spec (road, side, station, bays, floors, depth) and produces, every time it is rebuilt:
  * `<id>`             the building (one mesh, world-space vertices: the materials are world-triplanar)
  * `<id>_Plinth`      the base the facade modules stand on (sidewalk height down into the ground)
  * `<id>_Signs`       fascia lettering over the storefronts and an address plate beside the door
  * `<id>_Yard`        a concrete service yard beside the building (mrs_kind "drive": walked + driven)
  * `<id>_RollerDoor`  the loading door on the yard side
  * `MRS_Entrance_<id>`  entrance anchor (0.7 m in front of the door): keep-clear envelope to the kerb,
                         route-graph node, bike-parking magnet and the delivery destination record
  * `MRS_Driveway_<id>`  service-access anchor: the road gets a dropped kerb + concrete apron there
                         (road input "Driveways", written by `sync_driveways`)
Everything downstream (placement, ground, routes, movements) re-reads the anchors, so moving the spec's
station and regenerating moves the envelopes, the kerb drop, the bike rack and the bus stop rules with it.
"""
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix
from .nodes import MRS, mod_input_set

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
KIT_DIR = os.path.join(REPO, "world", "citykit", "modules")
TEX_DIR = os.path.join(REPO, "world", "citykit", "textures")
GROUND_WALL = 4.18 / 3.2           # district.gd: ground-floor walls are 4.18 m tall (the 3.2 m module scaled)

# world/citykit/city_kit.gd (TEXTURED: set, metres per repeat, metallic, normal scale[, tint]; FLAT: colour, roughness, metallic)
TEXTURED = {"KitBrickRed": ("brick_red", 1.8, 0.0, 1.0), "KitConcrete": ("concrete", 2.0, 0.0, 0.7), "KitLimestone": ("limestone", 2.4, 0.0, 0.8),
            "KitRoofGravel": ("roof_gravel", 2.0, 0.0, 1.0), "KitPartyBrick": ("brick_red", 1.8, 0.0, 1.0, "9a8a80"), "KitStucco": ("stucco", 2.0, 0.0, 0.6),
            "KitMetalPanel": ("metal_panel", 2.0, 0.55, 1.0), "KitTerrazzo": ("terrazzo", 2.0, 0.0, 0.4)}
FLAT = {"KitFrameDark": ("22282b", 0.38, 0.6), "KitFrameBronze": ("4b3a2a", 0.36, 0.7), "KitFrameLight": ("a7acaf", 0.3, 0.8), "KitRail": ("202528", 0.42, 0.6),
        "KitDoor": ("2a3134", 0.5, 0.3), "KitPaintGreen": ("274d3d", 0.55, 0.0), "KitPaintNavy": ("243650", 0.55, 0.0), "KitAwning": ("3e5c4a", 0.92, 0.0),
        "KitTrimPaint": ("ffffff", 0.45, 0.0), "KitBronze": ("6b4a2c", 0.36, 0.85), "KitSignGreen": ("1f5c3a", 0.4, 0.0), "KitPlaster": ("eeebe4", 0.85, 0.0),
        "KitDoorWood": ("7a4a2a", 0.4, 0.0), "KitWallPaint": ("ffffff", 0.8, 0.0)}

# Godot (x, y, z) -> Blender (x, -z, y): the glTF importer applies this to the module meshes
G2B = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
B2G = G2B.inverted()


def _srgb(h):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def _key(name):
    k = name.split(".")[0]
    return k[:-4] if len(k) > 4 and k[-4] == "_" and k[-3:].isdigit() else k


def kit_material(key):
    """Blender stand-in for CityKit.material(key): world-aligned box-projected PBR sets / flat finishes.
    The name is the Kit* key itself, so the Godot loader maps it to the game material by name."""
    m = bpy.data.materials.get(key)
    if m is not None and m.get("mrs_kit"): return m
    m = m or bpy.data.materials.new(key); m.use_nodes = True; m["mrs_kit"] = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs[0])
    if key == "KitGlass":
        # Godot uses the downtown window shader (interiors); here: dark reflective glass with a faint warm interior
        b.inputs["Base Color"].default_value = (0.035, 0.045, 0.05, 1); b.inputs["Roughness"].default_value = 0.05
        b.inputs["Emission Color"].default_value = (1.0, 0.82, 0.6, 1); b.inputs["Emission Strength"].default_value = 0.02
        m.diffuse_color = (0.05, 0.06, 0.07, 1)
    elif key in TEXTURED:
        spec = TEXTURED[key]
        geo = nt.nodes.new("ShaderNodeNewGeometry"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / spec[1],) * 3
        nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
        def tex(kind, cs):
            p = os.path.join(TEX_DIR, "%s_%s.png" % (spec[0], kind))
            img = bpy.data.images.get(os.path.basename(p)) or bpy.data.images.load(p, check_existing=True)
            img.colorspace_settings.name = cs
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.projection = "BOX"; t.projection_blend = 0.15
            nt.links.new(mp.outputs[0], t.inputs["Vector"]); return t
        ta = tex("albedo", "sRGB"); tr = tex("rough", "Non-Color"); tn = tex("normal", "Non-Color")
        if len(spec) > 4:
            mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0
            nt.links.new(ta.outputs["Color"], mix.inputs["A"]); mix.inputs["B"].default_value = (*_srgb(spec[4]), 1)
            nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
        else:
            nt.links.new(ta.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(tr.outputs["Color"], b.inputs["Roughness"])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = spec[3]
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
        b.inputs["Metallic"].default_value = spec[2]
        m.diffuse_color = (0.55, 0.5, 0.45, 1)
    else:
        col, rough, metal = FLAT.get(key, ("808080", 0.7, 0.0))
        c = _srgb(col); b.inputs["Base Color"].default_value = (*c, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*c, 1); m.roughness = rough; m.metallic = metal
    return m


def kit_mesh(name):
    """The module `name` as one Blender mesh 'KitMod_<name>' (imported once; materials remapped to kit_material)."""
    mn = "KitMod_" + name
    me = bpy.data.meshes.get(mn)
    if me is not None: return me
    path = os.path.join(KIT_DIR, name + ".glb")
    if not os.path.exists(path): raise FileNotFoundError(path)
    before_o = set(bpy.data.objects); before_m = set(bpy.data.meshes); before_mat = set(bpy.data.materials)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before_o]
    verts, faces, fmats, mats = [], [], [], []
    for o in new:
        if o.type != "MESH": continue
        M = o.matrix_world; base = len(verts)
        verts.extend((M @ v.co)[:] for v in o.data.vertices)
        for p in o.data.polygons:
            faces.append([base + i for i in p.vertices])
            src = o.data.materials[p.material_index] if o.data.materials else None
            km = kit_material(_key(src.name) if src else "KitConcrete")
            if km not in mats: mats.append(km)
            fmats.append(mats.index(km))
    me = bpy.data.meshes.new(mn); me.from_pydata(verts, [], faces); me.update()
    for m in mats: me.materials.append(m)
    for p, k in zip(me.polygons, fmats): p.material_index = k; p.use_smooth = False
    me.use_fake_user = True
    for o in new: bpy.data.objects.remove(o)
    for m_ in [x for x in bpy.data.meshes if x not in before_m and x is not me and x.users == 0]: bpy.data.meshes.remove(m_)
    for m_ in [x for x in bpy.data.materials if x not in before_mat and x.users == 0 and not x.get("mrs_kit")]: bpy.data.materials.remove(m_)
    return me


def pose(x=0.0, y=0.0, z=0.0, yaw=0.0, sx=1.0, sy=1.0, sz=1.0):
    """Godot-space Transform (district.gd `pose`): translation, rotation about +Y, scale."""
    return Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, "Y") @ Matrix.Diagonal((sx, sy, sz, 1.0))


def assemble(bays=4, floors=2, depth=12.0, style=1, entry_bay=None, yard_side=1):
    """Module placements [(module, Godot matrix)] for a free-standing shop, following district.gd:
    front: storefronts + entrance (ground), apartment bays above, awnings on the storefronts; back: party
    brick below, apartment bays above; sides: brick walls (the yard side gets the loading door separately);
    roof slab inset 15 cm, parapets on all four sides, corner posts. Facade at z = 0 facing +Z, depth -Z."""
    w = bays * 4.0; d = depth
    entry_bay = bays // 2 if entry_bay is None else entry_bay
    out = []
    for f in range(floors):
        y = 0.0 if f == 0 else 4.2 + (f - 1) * 3.2
        for face in (0, 1):
            fp = pose(0, y, 0 if face == 0 else -d, 0 if face == 0 else math.pi)
            for i in range(bays):
                x = -bays * 2.0 + 2 + i * 4
                if f == 0:
                    if face == 0: out.append((("entrance_%d" if i == entry_bay else "storefront_%d") % style, fp @ pose(x)))
                    else: out.append(("blank_wall", fp @ pose(x, 0, 0, 0, 1, GROUND_WALL, 1)))
                else:
                    out.append(("bay_apartment_%d" % style, fp @ pose(x)))
                if f == 0 and face == 0 and i != entry_bay: out.append(("awning", fp @ pose(x, 3.2, 0.04)))
        for side in (-1, 1):
            sp = pose(side * w * 0.5, y, -d * 0.5, side * math.pi / 2)
            out.append(("blank_wall", sp @ pose(0, 0, -0.1, 0, (d - 0.04) / 4, GROUND_WALL if f == 0 else 1, 1)))
    roof_y = 4.2 + (floors - 1) * 3.2
    out.append(("roof_slab", pose(0, roof_y, -0.15, 0, (w - 0.3) / 4, 1, (d - 0.3) / 4)))
    for face in (0, 1): out.append(("parapet", pose(0, roof_y, 0 if face == 0 else -d, 0 if face == 0 else math.pi, w / 4, 1, 1)))
    for side in (-1, 1): out.append(("parapet", pose(side * w * 0.5, roof_y, -d * 0.5, side * math.pi / 2, (d - 0.6) / 4, 1, 1)))
    for back in (False, True):
        for sx in (-1.0, 1.0):
            corner = pose(0, 0, -d if back else 0, math.pi if back else 0.0)
            px = sx * (w * 0.5 + 0.0025) * (-1.0 if back else 1.0)
            out.append(("plain_wall_%d" % style, corner @ pose(px, 0, 0.10, 0, 0.075 / 4, (roof_y + 0.025) / 3.2, 0.44 / 0.3)))
    entry_x = -bays * 2.0 + 2 + entry_bay * 4
    return out, {"width": w, "depth": d, "height": roof_y, "entry_x": entry_x}


def _box(bm, x0, y0, z0, x1, y1, z1, mat):
    vs = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        ff = bm.faces.new([vs[i] for i in f]); ff.material_index = mat


def _mesh_obj(name, me, col, sid=None):
    old = bpy.data.objects.get(name)
    if old is not None: bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    if sid: o["mrs_frontage"] = sid
    return o


def _text_mesh(text, size, mat, depth=0.02, align="CENTER"):
    """Extruded lettering as a mesh in the XZ plane (reads from -Y, Blender's facade direction), centred."""
    cu = bpy.data.curves.new("_t", "FONT"); cu.body = text; cu.size = size; cu.extrude = depth / 2; cu.align_x = align; cu.align_y = "CENTER"
    cu.fill_mode = "BOTH"; cu.resolution_u = 4
    tmp = bpy.data.objects.new("_t", cu); bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp); bpy.data.curves.remove(cu)
    me.transform(Matrix.Rotation(math.pi / 2, 4, "X"))          # text XY -> XZ, front face toward -Y
    me.materials.clear(); me.materials.append(mat)
    xs = [v.co.x for v in me.vertices]
    return me, (max(xs) - min(xs)) if xs else 0.0


def _join(dst_bm, me, M, mat_index):
    tmp = me.copy(); tmp.transform(M)
    bm2 = bmesh.new(); bm2.from_mesh(tmp)
    vmap = {v: dst_bm.verts.new(v.co) for v in bm2.verts}
    for f in bm2.faces:
        try:
            nf = dst_bm.faces.new([vmap[v] for v in f.verts]); nf.material_index = mat_index
        except ValueError: pass
    bm2.free(); bpy.data.meshes.remove(tmp)


# ============================================================================ the frontage
def make_shop(spec, roads_col):
    """Build (or rebuild) one shop frontage from `spec`:
    {id, road, side, along, bays, floors, depth, style, name, number, street, yard_width, drive_width, setback}.
    Returns a record {id, entrance, driveway, door, facing, address, ...}."""
    from .placement import RoadModel
    sid = spec["id"]; road = bpy.data.objects[spec["road"]]; s = spec.get("side", "r")
    m = RoadModel(road)
    bays = int(spec.get("bays", 4)); floors = int(spec.get("floors", 2)); depth = float(spec.get("depth", 12.0)); style = int(spec.get("style", 1))
    yard_w = float(spec.get("yard_width", 9.0)); drive_w = float(spec.get("drive_width", 5.0))
    col = bpy.data.collections.get(roads_col.name + "_Frontage") or bpy.data.collections.new(roads_col.name + "_Frontage")
    if col.name not in [c.name for c in roads_col.children]: roads_col.children.link(col)
    a = float(spec["along"])
    q_sw, t, n = m.point(a, s, m.sw[s] - 0.05)                        # on the sidewalk, back edge (n: away from the road)
    q_face, _, _ = m.point(a, s, m.sw[s] + float(spec.get("setback", 0.02)))
    z0 = q_sw.z
    n = Vector((n.x, n.y, 0)).normalized(); xb = n.cross(Vector((0, 0, 1))).normalized()
    W = Matrix((( xb.x, n.x, 0, q_face.x), (xb.y, n.y, 0, q_face.y), (0, 0, 1, z0), (0, 0, 0, 1)))
    yard_side = 1 if spec.get("yard_side", "ahead") == "ahead" else -1          # +x_local = road direction (n x up)
    if t.dot(xb) < 0: yard_side = -yard_side
    placements, info = assemble(bays, floors, depth, style, spec.get("entry_bay"), yard_side)
    w = info["width"]
    # --- building: every module baked into one world-space mesh (world-triplanar materials)
    bm = bmesh.new(); mats = []
    def mi(mat):
        if mat not in mats: mats.append(mat)
        return mats.index(mat)
    for name, Mg in placements:
        me = kit_mesh(name)
        Mb = W @ G2B @ Mg @ B2G
        tmp = me.copy(); tmp.transform(Mb)
        bm2 = bmesh.new(); bm2.from_mesh(tmp)
        vmap = {v: bm.verts.new(v.co) for v in bm2.verts}
        for f in bm2.faces:
            try:
                nf = bm.faces.new([vmap[v] for v in f.verts]); nf.material_index = mi(tmp.materials[f.material_index])
            except ValueError: pass
        bm2.free(); bpy.data.meshes.remove(tmp)
    # shop room behind the entrance bay (the kit entrance door stands open): terrazzo floor, plaster walls and
    # ceiling (normals inward), a counter and wall shelving. Local Blender frame: x along the facade, y into the building.
    ex0 = -bays * 2.0 + 2 + (bays // 2 if spec.get("entry_bay") is None else int(spec["entry_bay"])) * 4
    rx0, rx1, ry0, ry1, rz1 = ex0 - 1.95, ex0 + 1.95, 0.32, min(depth - 0.5, 6.0), 3.1
    floor_m, wall_m, wood_m, dark_m = mi(kit_material("KitTerrazzo")), mi(kit_material("KitPlaster")), mi(kit_material("KitDoorWood")), mi(kit_material("KitFrameDark"))
    def quad(ps, m_):
        f_ = bm.faces.new([bm.verts.new((W @ Vector(p))[:]) for p in reversed(ps)]); f_.material_index = m_     # listed outward-wound: reversed = inward
    quad([(rx0, ry0, 0.005), (rx0, ry1, 0.005), (rx1, ry1, 0.005), (rx1, ry0, 0.005)], floor_m)          # floor (up)
    quad([(rx0, ry0, rz1), (rx1, ry0, rz1), (rx1, ry1, rz1), (rx0, ry1, rz1)], wall_m)                 # ceiling (down)
    quad([(rx0, ry1, 0), (rx0, ry1, rz1), (rx1, ry1, rz1), (rx1, ry1, 0)], wall_m)                     # back wall (toward the door)
    quad([(rx0, ry0, 0), (rx0, ry0, rz1), (rx0, ry1, rz1), (rx0, ry1, 0)], wall_m)                     # side walls (inward)
    quad([(rx1, ry1, 0), (rx1, ry1, rz1), (rx1, ry0, rz1), (rx1, ry0, 0)], wall_m)
    for (x0, y0, z0_, x1, y1, z1, m_) in ((ex0 - 1.2, ry1 - 1.1, 0.0, ex0 + 0.6, ry1 - 0.5, 1.0, wood_m),          # counter
                                         (ex0 - 1.25, ry1 - 1.15, 1.0, ex0 + 0.65, ry1 - 0.45, 1.04, dark_m),  # counter top
                                         (rx0 + 0.02, ry0 + 1.2, 0.0, rx0 + 0.45, ry1 - 0.3, 2.1, dark_m),     # shelving left
                                         (rx1 - 0.45, ry0 + 1.2, 0.0, rx1 - 0.02, ry1 - 1.6, 2.1, dark_m)):    # shelving right
        bm2 = bmesh.new(); _box(bm2, x0, y0, z0_, x1, y1, z1, 0)
        vm = {v: bm.verts.new((W @ v.co)[:]) for v in bm2.verts}
        for f in bm2.faces:
            nf = bm.faces.new([vm[v] for v in f.verts]); nf.material_index = m_
        bm2.free()
    me = bpy.data.meshes.new(sid); bm.to_mesh(me); bm.free()
    for mt in mats: me.materials.append(mt)
    bld = _mesh_obj(sid, me, col, sid)
    bld["mrs_building"] = json.dumps({"id": sid, "kit_modules": sorted({p[0] for p in placements}), "width": w, "depth": depth, "height": info["height"] + 0.92,
                                      "floors": floors, "style": style, "footprint": [list(W @ Vector(c))[:2] for c in ((-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, depth, 0), (-w / 2, depth, 0))]})
    # --- plinth: from the module base (sidewalk height) down into the ground, 5 cm inside the walls
    bm = bmesh.new(); _box(bm, -w / 2 + 0.05, 0.05, -0.45, w / 2 - 0.05, depth - 0.05, 0.0, 0)
    me = bpy.data.meshes.new(sid + "_Plinth"); bm.to_mesh(me); bm.free(); me.transform(W); me.materials.append(kit_material("KitConcrete"))
    _mesh_obj(sid + "_Plinth", me, col, sid)
    # --- signs: fascia lettering (navy fascia band 3.15..4.06 m) and the address plate beside the door
    ex = info["entry_x"]
    white = kit_material("KitTrimPaint"); navy = kit_material("KitPaintNavy"); bronze = kit_material("KitBronze")
    bm = bmesh.new(); smats = [white, navy, bronze]
    tm, tw = _text_mesh(spec.get("name", "SHOP").upper(), 0.48, white, depth=0.03)
    sc = min(1.0, (w - 1.6) / max(tw, 1e-3))
    _join(bm, tm, Matrix.Translation((0.0, -0.035, 3.62)) @ Matrix.Diagonal((sc, 1, sc, 1)), 0); bpy.data.meshes.remove(tm)
    # address plate: enamel plate 0.36 x 0.26 on the pier right of the door, 1.9 m up; number in white
    px = ex + 1.78
    _box(bm, px - 0.18, -0.025, 1.77, px + 0.18, -0.005, 2.03, 1)
    tm, _ = _text_mesh(str(spec.get("number", "1")), 0.17, white, depth=0.008)
    _join(bm, tm, Matrix.Translation((px, -0.03, 1.9)), 0); bpy.data.meshes.remove(tm)
    tm, tw2 = _text_mesh(spec.get("street", "").upper(), 0.045, white, depth=0.004)
    _join(bm, tm, Matrix.Translation((px, -0.03, 1.8)) @ Matrix.Diagonal((min(1.0, 0.32 / max(tw2, 1e-3)), 1, 1, 1)), 0); bpy.data.meshes.remove(tm)
    me = bpy.data.meshes.new(sid + "_Signs"); bm.to_mesh(me); bm.free(); me.transform(W)
    for mt in smats: me.materials.append(mt)
    so = _mesh_obj(sid + "_Signs", me, col, sid)
    so["mrs_legend"] = json.dumps({"fascia": spec.get("name", ""), "number": str(spec.get("number", "")), "street": spec.get("street", "")})
    # --- service yard beside the building on the yard side (local x from the side wall outwards)
    face_x = yard_side * (w / 2 - 0.1)              # outer face of the side wall (district.gd side walls sit 0.1 m in)
    yx0 = yard_side * (w / 2 - 0.05); yx1 = yard_side * (w / 2 + yard_w)
    z_front = 0.01 - z0                            # 1 cm above the dropped kerb at the sidewalk back; floor level at the back
    def ytop(y): return z_front + (0.0 - z_front) * max(0.0, min(1.0, y / depth))
    bm = bmesh.new()
    xa, xb_ = min(yx0, yx1), max(yx0, yx1); ny = 6
    ys = [-float(spec.get("setback", 0.02)) - 0.01] + [depth * j / ny for j in range(1, ny + 1)]      # front edge meets the sidewalk back
    top = [[bm.verts.new((x, y_, ytop(max(y_, 0.0)))) for y_ in ys] for x in (xa, xb_)]
    bot = [[bm.verts.new((x, y_, -0.35)) for y_ in ys] for x in (xa, xb_)]
    for j in range(ny):
        bm.faces.new((top[0][j], top[1][j], top[1][j + 1], top[0][j + 1]))
        bm.faces.new((bot[0][j], bot[0][j + 1], bot[1][j + 1], bot[1][j]))
        bm.faces.new((top[0][j], top[0][j + 1], bot[0][j + 1], bot[0][j]))
        bm.faces.new((top[1][j + 1], top[1][j], bot[1][j], bot[1][j + 1]))
    bm.faces.new((top[0][0], bot[0][0], bot[1][0], top[1][0])); bm.faces.new((top[1][ny], bot[1][ny], bot[0][ny], top[0][ny]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # loading box (yellow frame) in front of the roller door, 3 mm proud of the sloping slab
    lx = yard_side * (w / 2 + 2.2)
    for (x0, y0, x1, y1) in ((lx - 1.6, 2.0, lx + 1.6, 2.12), (lx - 1.6, 8.88, lx + 1.6, 9.0), (lx - 1.6, 2.0, lx - 1.48, 9.0), (lx + 1.48, 2.0, lx + 1.6, 9.0)):
        f_ = bm.faces.new([bm.verts.new((x_, y_, ytop(y_) + 0.003)) for x_, y_ in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]); f_.material_index = 1
        if f_.normal.z < 0: f_.normal_flip()
    me = bpy.data.meshes.new(sid + "_Yard"); bm.to_mesh(me); bm.free(); me.transform(W)
    uv = me.uv_layers.new(name="UVMap")                 # metres in world XY, like the road meshes (baked tiles repeat every 4 m)
    for lp in me.loops: uv.data[lp.index].uv = (me.vertices[lp.vertex_index].co.x, me.vertices[lp.vertex_index].co.y)
    conc = bpy.data.materials.get(MRS + "Concrete") or kit_material("KitConcrete")
    from .props import mat as _pmat
    me.materials.append(conc); me.materials.append(_pmat(MRS + "MarkingYellow", (0.8, 0.6, 0.05), 0.55))
    yard = _mesh_obj(sid + "_Yard", me, col, sid)
    yard["mrs_kind"] = "drive"; yard["mrs_ped_path"] = False
    # --- roller door on the yard-side wall (3.2 m wide, 3.4 m high) with a steel box frame
    bm = bmesh.new(); fx = face_x; sg = yard_side
    def X(a_, b_): return min(fx + sg * a_, fx + sg * b_), max(fx + sg * a_, fx + sg * b_)
    dz0, dz1, dy0, dy1 = 0.0, 3.4, depth / 2 - 1.6, depth / 2 + 1.6
    x0_, x1_ = X(0.01, 0.07); _box(bm, x0_, dy0, dz0, x1_, dy1, dz1, 0)                       # shutter (metal panel texture)
    for (y0_, y1_) in ((dy0 - 0.12, dy0), (dy1, dy1 + 0.12)):
        x0_, x1_ = X(0.0, 0.12); _box(bm, x0_, y0_, 0.0, x1_, y1_, dz1 + 0.12, 1)             # guide rails
    x0_, x1_ = X(0.0, 0.36); _box(bm, x0_, dy0 - 0.12, dz1, x1_, dy1 + 0.12, dz1 + 0.45, 1)   # coil box
    x0_, x1_ = X(0.01, 0.03); _box(bm, x0_, dy1 + 0.5, 1.6, x1_, dy1 + 1.5, 2.1, 2)            # "DELIVERIES" panel
    me = bpy.data.meshes.new(sid + "_RollerDoor"); bm.to_mesh(me); bm.free()
    for mt in (kit_material("KitMetalPanel"), kit_material("KitFrameDark"), kit_material("KitSignGreen")): me.materials.append(mt)
    tm, tw3 = _text_mesh("DELIVERIES  " + str(spec.get("number", "")), 0.12, white, depth=0.004)
    me.materials.append(white)
    bmd = bmesh.new(); bmd.from_mesh(me)
    _join(bmd, tm, Matrix.Translation((fx + sg * 0.036, dy1 + 1.0, 1.85)) @ Matrix.Rotation(sg * math.pi / 2, 4, "Z") @ Matrix.Diagonal((min(1.0, 0.9 / max(tw3, 1e-3)), 1, 1, 1)), 3)
    bmd.to_mesh(me); bmd.free(); bpy.data.meshes.remove(tm)
    me.transform(W)
    _mesh_obj(sid + "_RollerDoor", me, col, sid)
    # --- shopfront lighting: warm downlights under the fascia over each storefront / the door (real light sources,
    # exported as light records; lighting.night_setup / MrsStreetLights switch them with the street lights)
    for i in range(bays):
        lx_ = -bays * 2.0 + 2 + i * 4
        nm = "%s_Downlight%d" % (sid, i)
        old = bpy.data.objects.get(nm)
        if old is not None: bpy.data.objects.remove(old)
        ld = bpy.data.lights.get(nm) or bpy.data.lights.new(nm, "SPOT")
        ld.energy = 45.0; ld.spot_size = math.radians(110.0); ld.spot_blend = 0.6; ld.shadow_soft_size = 0.15
        ld.use_custom_distance = True; ld.cutoff_distance = 8.0
        try: ld.use_temperature = True; ld.temperature = 3000
        except AttributeError: ld.color = (1.0, 0.78, 0.55)
        lo = bpy.data.objects.new(nm, ld); col.objects.link(lo)
        lo.matrix_world = W @ Matrix.Translation((lx_, -0.55, 3.05)) @ Matrix.Rotation(math.radians(18.0), 4, "X")   # aimed down, slightly out
        lo["mrs_light"] = 1; lo["mrs_light_class"] = "frontage"; lo["mrs_temperature"] = 3000; lo["mrs_godot_range"] = 8.0
        lo["mrs_godot_fade_begin"] = 45.0; lo["mrs_frontage"] = sid; lo.hide_render = True
    # --- anchors (placement / routes / movements read these)
    door = W @ Vector((ex, -0.12, 1.1))
    ent_pos = W @ Vector((ex, -0.7, 0.0)); ent_pos.z = z0
    facing = (W.to_3x3() @ Vector((0, -1, 0))).normalized()
    ent = bpy.data.objects.get("MRS_Entrance_" + sid) or bpy.data.objects.new("MRS_Entrance_" + sid, None)
    if ent.name not in col.objects: col.objects.link(ent)
    ent.location = ent_pos; ent.empty_display_size = 1.0; ent["mrs_frontage"] = sid
    ent["mrs_road"] = road.name; ent["mrs_side"] = s; ent["mrs_bike_parking"] = True; ent["mrs_on_sidewalk"] = True
    mouth = W @ Vector((yard_side * (w / 2 + yard_w / 2), 0.0, 0.0))
    drv = bpy.data.objects.get("MRS_Driveway_" + sid) or bpy.data.objects.new("MRS_Driveway_" + sid, None)
    if drv.name not in col.objects: col.objects.link(drv)
    drv.location = mouth; drv.empty_display_size = drive_w / 2; drv["mrs_frontage"] = sid
    drv["mrs_road"] = road.name; drv["mrs_side"] = s; drv["mrs_width"] = drive_w
    yard_c = W @ Vector((yard_side * (w / 2 + yard_w / 2), depth * 0.6, 0.0))
    yard_l = [round(c, 3) for c in yard_c]; drv["mrs_yard"] = yard_l
    rec = {"id": sid, "kind": "shop", "name": spec.get("name", ""), "address": "%s %s" % (spec.get("number", ""), spec.get("street", "")),
           "road": road.name, "side": s, "along": a, "door": [round(c, 3) for c in door], "facing": [round(c, 3) for c in facing],
           "entrance": [round(c, 3) for c in ent_pos], "service": {"driveway": [round(c, 3) for c in mouth], "yard": yard_l, "width": drive_w},
           "building": bld.name, "kit_modules": sorted({p[0] for p in placements})}
    ent["mrs_destination"] = json.dumps(rec)
    return rec


def clear(roads_col, keep=()):
    """Remove the objects of every frontage whose id is not in `keep` (stable rebuilds, no leftovers)."""
    col = bpy.data.collections.get(roads_col.name + "_Frontage")
    if col is None: return
    for o in list(col.objects):
        if o.get("mrs_frontage") and o["mrs_frontage"] not in keep: bpy.data.objects.remove(o)


def destinations():
    out = []
    for o in bpy.data.objects:
        if o.type == "EMPTY" and o.name.startswith("MRS_Entrance") and o.get("mrs_destination"):
            out.append(json.loads(o["mrs_destination"]))
    return out


# ============================================================================ driveways -> road input
def sync_driveways(roads_col):
    """Every MRS_Driveway_* anchor -> a point (station, +/-100 by side, 0) with `width` on its road's
    driveway mesh 'MRS_Driveways_<road>' (road input "Driveways"): the road drops the kerb there and paves a
    concrete apron across the sidewalk. Roads without driveways get no object. Returns {road: [(along, side, width)]}."""
    from .roads import all_roads
    from .placement import _project, RoadModel
    from . import structures
    roads = {r.name: r for r in all_roads(roads_col)}
    per = {n: [] for n in roads}
    for o in bpy.data.objects:
        if o.type != "EMPTY" or not o.name.startswith("MRS_Driveway"): continue
        r = roads.get(o.get("mrs_road", ""))
        if r is None: continue
        structures._CENTRE.pop(r.name, None)
        a = _project(RoadModel(r), o.location)
        per[r.name].append((round(a, 3), o.get("mrs_side", "r"), float(o.get("mrs_width", 5.0))))
    for name, lst in per.items(): apply_driveways(roads[name], lst)
    return {k: v for k, v in per.items() if v}


def apply_driveways(r, lst):
    """Set road r's driveway point cloud 'MRS_Driveways_<road>' from [(along, side 'l'/'r', width)] (empty: none)."""
    from . import structures
    lib = bpy.data.collections.get(MRS + "DrivewayPoints") or bpy.data.collections.new(MRS + "DrivewayPoints")
    mod = r.modifiers["MRS_Road"]; name = r.name
    on = MRS + "Driveways_" + name
    if not lst:
        mod_input_set(mod, "Driveways", None)
        if bpy.data.objects.get(on): bpy.data.objects.remove(bpy.data.objects[on])
        if r.get("mrs_driveways"): del r["mrs_driveways"]
        r.update_tag(); return
    me = bpy.data.meshes.get(on) or bpy.data.meshes.new(on)
    me.clear_geometry()
    me.from_pydata([(a, 100.0 if s == "r" else -100.0, 0.0) for a, s, w in lst], [], [])
    at = me.attributes.get("width") or me.attributes.new("width", "FLOAT", "POINT")
    at.data.foreach_set("value", [w for a, s, w in lst]); me.update()
    o = bpy.data.objects.get(on) or bpy.data.objects.new(on, me)
    if o.name not in lib.objects: lib.objects.link(o)
    o.hide_viewport = True; o.hide_render = True; o["mrs_debug"] = True
    mod_input_set(mod, "Driveways", o)
    r["mrs_driveways"] = json.dumps(lst)
    structures._CENTRE.pop(r.name, None)
    r.update_tag()
