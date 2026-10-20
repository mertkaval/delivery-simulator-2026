"""Parametric wheel / tyre / rim / brake assembly for the player sedan (G4 mechanical).

usage (headless):
  blender --background --factory-startup --python wheel_assembly.py            # build + export + renders + handoff
  blender --background --factory-startup --python wheel_assembly.py -- --verify # re-import the GLB in a fresh
                                                                                 # Blender and append the result to the handoff

Local frame per wheel (Blender): axle = local X, RIGHT wheel face at +X, origin at the hub centre, the wheel
spins about local X. glTF export (Y-up) keeps the X axis, so Godot also spins it about local X.

Hierarchy (LOD0, repeated with _LOD1 suffix under WheelR_LOD1 at +1 m Y):
  WheelR (empty)
    WheelPivot (empty, spinning)  -> Tyre, RimBarrel, RimFace, CentreCap, LugNuts, BrakeDisc
    HubStatic  (empty, fixed)     -> Caliper, DustShield

Tyre 225/50 R17: OD 0.66, section 0.225, rim 0.432 x ~0.19 (7.5J). Rim face ~0.02 m inside the tyre outer sidewall.
"""
import bpy, bmesh, math, os, sys, json, time
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(HERE, "production")
WIP = os.path.join(PROD, "wip")
RENDERS = os.path.join(PROD, "renders", "g4_wheel")
REPORTS = os.path.join(PROD, "reports")
GLB = os.path.join(WIP, "wheel_assembly.glb")
BLEND = os.path.join(WIP, "wheel_assembly.blend")
HANDOFF = os.path.join(REPORTS, "g4_wheel_handoff.json")
VERSION = "0.4"

# ----------------------------------------------------------------------------- parameters
P = dict(
    tyre_od=0.66,        # outer diameter (m)
    tyre_width=0.225,    # section width (m)
    rim_dia=0.432,       # bead seat diameter (m)
    rim_width=0.19,      # bead-to-bead (m)
    face_inset=0.02,     # rim face sits this far inside the tyre outer sidewall
    spoke_pairs=5,       # twin spokes -> 10 blades
    blade_w_rim=0.042,   # blade width at the rim (m)
    blade_w_hub=0.032,   # blade width at the hub (m)
    pair_gap=0.022,      # slot between the two blades of a pair (m)
    blade_dish=0.020,    # rim end sits this much further outboard than the hub end
    hub_plate_r=0.11,
    lug_count=5,
    lug_pcd=0.114,
    lug_af=0.021,        # nut across flats (m)
    disc_dia=0.30,
    disc_thick=0.028,
    caliper_height=0.17,
    caliper_depth=0.07,
    shield_r=0.140,
)

LOD = {
    0: dict(tyre_seg=48, detail=True, tread_cuts=48, rim_seg=48, hub_seg=40, spoke_steps=3, chamfer=True, pockets=True,
            lug_sides=6, cap_seg=24, disc_seg=32, vanes=20, cal_seg=6, bosses=True, shield_seg=26),
    1: dict(tyre_seg=32, detail=False, tread_cuts=0, rim_seg=24, hub_seg=20, spoke_steps=1, chamfer=False, pockets=False,
            lug_sides=5, cap_seg=10, disc_seg=20, vanes=0, cal_seg=3, bosses=False, shield_seg=16),
}

# ----------------------------------------------------------------------------- helpers

def material(name, base, metallic=0.0, rough=0.5, coat=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.1
    return m


def mats():
    return dict(
        Rubber=material("Rubber", (0.018, 0.018, 0.019), 0.0, 0.9),
        RubberCut=material("RubberCut", (0.004, 0.004, 0.004), 0.0, 1.0),
        Alloy=material("Alloy", (0.80, 0.80, 0.79), 1.0, 0.25, coat=0.3),
        RimWell=material("RimWell", (0.16, 0.16, 0.165), 1.0, 0.5),
        Chrome=material("Chrome", (0.95, 0.95, 0.95), 1.0, 0.08),
        SteelDisc=material("SteelDisc", (0.46, 0.45, 0.44), 1.0, 0.4),
        CaliperDark=material("CaliperDark", (0.11, 0.11, 0.115), 0.0, 0.55),
    )


def finish_bmesh(bm, sharp_deg):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.normal_update()
    for f in bm.faces:
        f.smooth = True
    thr = math.radians(sharp_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            a, b = e.link_faces
            e.smooth = a.normal.angle(b.normal, 0.0) < thr
        else:
            e.smooth = False


def new_object(name, bm, mat, parent, sharp_deg=32.0, extra_mats=()):
    """Finalise a bmesh into a smooth-shaded object with angle-based sharp edges."""
    finish_bmesh(bm, sharp_deg)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for m in extra_mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob


def revolve(bm, profile, seg, start=0.0, closed=True, mat_index=0):
    """Revolve a closed (x, r) profile about local X. Points with r ~ 0 become a single centre vertex (fans)."""
    rings = []
    for i in range(seg):
        a = start + 2 * math.pi * i / seg
        ring = []
        for (x, r) in profile:
            ring.append(None if r < 1e-6 else bm.verts.new((x, r * math.cos(a), r * math.sin(a))))
        rings.append(ring)
    centres = {j: bm.verts.new((x, 0.0, 0.0)) for j, (x, r) in enumerate(profile) if r < 1e-6}
    n = len(profile)
    span = n if closed else n - 1
    for i in range(seg):
        r0, r1 = rings[i], rings[(i + 1) % seg]
        for j in range(span):
            k = (j + 1) % n
            v = [r0[j], r1[j], r1[k], r0[k]]
            if v[0] is None and v[3] is None:
                continue
            if v[0] is None:
                v = [centres[j], r1[k], r0[k]]
            elif v[3] is None:
                v = [r0[j], r1[j], centres[k]]
            try:
                f = bm.faces.new(v)
                f.material_index = mat_index
            except ValueError:
                pass


def arc(cx, cr, rad, a0, a1, n):
    """Points on an arc in the (x, r) plane from angle a0 to a1 (degrees, 0 = +x, 90 = +r)."""
    return [(cx + rad * math.cos(math.radians(a0 + (a1 - a0) * k / (n - 1))),
             cr + rad * math.sin(math.radians(a0 + (a1 - a0) * k / (n - 1)))) for k in range(n)]


def box(bm, verts8):
    vs = [bm.verts.new(v) for v in verts8]
    for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([vs[i] for i in q])


def prism(bm, sections, cap=True):
    """Loft polygon rings (lists of Vector) into a prism, optionally capping both ends."""
    rings = [[bm.verts.new(v) for v in s] for s in sections]
    n = len(sections[0])
    for a, b in zip(rings, rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            bm.faces.new([a[j], a[k], b[k], b[j]])
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


def evaluated_into_bmesh(ob, bm):
    """Append the modifier-evaluated mesh of ob into bm, then remove ob."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    tmp = bmesh.new()
    tmp.from_mesh(me)
    tmp.verts.ensure_lookup_table()
    vmap = [bm.verts.new(v.co) for v in tmp.verts]
    for f in tmp.faces:
        try:
            bm.faces.new([vmap[v.index] for v in f.verts])
        except ValueError:
            pass
    tmp.free()
    ob.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)


# ----------------------------------------------------------------------------- components

def build_tyre(L, M, parent, sfx):
    R = P["tyre_od"] / 2
    Rb = P["rim_dia"] / 2 + 0.006           # bead on the flange
    W2 = P["tyre_width"] / 2
    xf = W2 - P["face_inset"]               # rim face plane
    sh = 0.035                              # shoulder radius
    th = W2 - sh                            # tread half-width (shoulder arc tangent to sidewall and tread)
    det = L["detail"]
    prof = [(xf + 0.002, Rb)]
    if det:
        prof += [(0.108, Rb + 0.026), (0.1045, Rb + 0.034)]                            # rim-protector rib
        prof += [(W2, Rb + 0.042), (W2, Rb + 0.048), (W2 - 0.0015, Rb + 0.050),         # lettering rib 1
                 (W2 - 0.0015, Rb + 0.055), (W2, Rb + 0.057), (W2, Rb + 0.063)]          # lettering rib 2
        prof += arc(th, R - sh, sh, 0, 90, 4)                                         # rounded shoulder
    else:
        prof += [(W2 - 0.004, Rb + 0.030), (W2, Rb + 0.055)] + arc(th, R - sh, sh, 0, 90, 3)
    # tread: 4 circumferential grooves (2 wide centre, 2 narrow outer)
    if det:
        for xc, hw, d, flat in [(0.047, 0.003, 0.0085, False), (0.017, 0.0045, 0.009, True),
                                (-0.017, 0.0045, 0.009, True), (-0.047, 0.003, 0.0085, False)]:
            if flat:
                prof += [(xc + hw, R), (xc + hw * 0.6, R - d), (xc - hw * 0.6, R - d), (xc - hw, R)]
            else:
                prof += [(xc + hw, R), (xc, R - d), (xc - hw, R)]
    else:
        prof += [(0.004, R), (0.0, R - 0.008), (-0.004, R)]
    prof += arc(-th, R - sh, sh, 90, 180, 3)
    prof += [(-W2 + 0.004, Rb + 0.030), (-(xf + 0.002), Rb)]
    prof += [(-(xf - 0.004), Rb - 0.014), ((xf - 0.004), Rb - 0.014)]               # hidden inner carcass
    bm = bmesh.new()
    seg = L["tyre_seg"]
    revolve(bm, prof, seg)
    # transverse block cuts on the two outer ribs: thin dark decal quads lying on each tread facet
    if L["tread_cuts"]:
        n = L["tread_cuts"]
        rf = R * math.cos(math.pi / seg) + 0.0004        # facet radius at the segment centre, lifted 0.4 mm
        for rib in ((0.050, th - 0.004), (-(th - 0.004), -0.050)):
            for k in range(n):
                a = 2 * math.pi * (k + 0.5) / seg if n == seg else 2 * math.pi * k / n
                c, s = math.cos(a), math.sin(a)
                rad = Vector((0, c, s))
                tan = Vector((0, -s, c)) * 0.0028
                x0, x1 = rib
                vs = [Vector((x0, 0, 0)) + rad * rf - tan, Vector((x1, 0, 0)) + rad * rf - tan,
                      Vector((x1, 0, 0)) + rad * rf + tan, Vector((x0, 0, 0)) + rad * rf + tan]
                f = bm.faces.new([bm.verts.new(v) for v in vs])
                f.material_index = 1
                if f.normal_update() is None and f.normal.dot(rad) < 0:
                    f.normal_flip()
    return new_object("Tyre" + sfx, bm, M["Rubber"], parent, sharp_deg=48, extra_mats=(M["RubberCut"],))


def build_rim(L, M, parent, sfx):
    Rb = P["rim_dia"] / 2
    W2 = P["tyre_width"] / 2
    xf = W2 - P["face_inset"]              # outer flange plane
    xb = xf - P["rim_width"]               # inner bead plane
    # barrel: bead seats, rolled outer lip (r 0.011), flange back, stepped dark well
    lip_c = (xf - 0.011, Rb + 0.004)
    if L["detail"]:
        prof = [(xb, Rb - 0.006), (xb + 0.006, Rb + 0.002), (xf - 0.022, Rb + 0.002)]
        prof += arc(lip_c[0], lip_c[1], 0.011, 160, -70, 6)
        prof += [(xf - 0.008, Rb - 0.014), (xf - 0.034, Rb - 0.014),        # cylinder behind the blades (0.03 deep)
                 (xf - 0.052, Rb - 0.044), (xb + 0.004, Rb - 0.044), (xb, Rb - 0.036)]
    else:
        prof = [(xb, Rb - 0.006), (xf - 0.016, Rb + 0.002), (xf, Rb + 0.012), (xf - 0.004, Rb - 0.012),
                (xf - 0.034, Rb - 0.014), (xf - 0.052, Rb - 0.044), (xb, Rb - 0.044)]
    bm = bmesh.new()
    revolve(bm, prof, L["rim_seg"])
    barrel = new_object("RimBarrel" + sfx, bm, M["RimWell"], parent)

    # face: hub plate (with lug pockets) + twin blades
    bm = bmesh.new()
    hub_r = P["hub_plate_r"]
    x_face = xf - 0.004 - P["blade_dish"]        # hub plate face / blade face at the hub
    x_back = x_face - 0.034
    plate = [(x_face, 0.0), (x_face, hub_r - 0.004), (x_face - 0.004, hub_r), (x_back, hub_r), (x_back, 0.0)]
    if L["pockets"]:
        pb = bmesh.new()
        revolve(pb, plate, L["hub_seg"])
        bmesh.ops.remove_doubles(pb, verts=pb.verts, dist=1e-6)
        pme = bpy.data.meshes.new("hubplate_tmp")
        pb.to_mesh(pme)
        pb.free()
        pob = bpy.data.objects.new("hubplate_tmp", pme)
        bpy.context.scene.collection.objects.link(pob)
        cb = bmesh.new()
        pr = P["lug_pcd"] / 2
        for k in range(P["lug_count"]):
            a = 2 * math.pi * k / P["lug_count"] + math.pi / 2 + math.pi / P["spoke_pairs"]
            cy, cz = pr * math.cos(a), pr * math.sin(a)
            mat = Matrix.Translation((x_face, cy, cz)) @ Matrix.Rotation(math.radians(90), 4, "Y")
            bmesh.ops.create_cone(cb, cap_ends=True, segments=16, radius1=0.0165, radius2=0.0165, depth=0.020, matrix=mat)
        cme = bpy.data.meshes.new("cutter_tmp")
        cb.to_mesh(cme)
        cb.free()
        cob = bpy.data.objects.new("cutter_tmp", cme)
        bpy.context.scene.collection.objects.link(cob)
        mod = pob.modifiers.new("pockets", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cob
        try:
            mod.solver = "EXACT"
        except TypeError:
            pass
        bpy.context.view_layer.update()
        evaluated_into_bmesh(pob, bm)
        bpy.data.objects.remove(cob, do_unlink=True)
        bpy.data.meshes.remove(cme)
        bpy.data.meshes.remove(pme)
    else:
        revolve(bm, plate, L["hub_seg"])
    pairs = P["spoke_pairs"]
    steps = L["spoke_steps"]
    r0, r1 = 0.075, Rb + 0.006
    depth = 0.030
    for p in range(pairs):
        base = 2 * math.pi * p / pairs + math.pi / 2     # first pair at 12 o'clock
        for s in (-1, 1):
            sections = []
            for t in [k / steps for k in range(steps + 1)]:
                r = r0 + (r1 - r0) * t
                w = 0.5 * (P["blade_w_hub"] + (P["blade_w_rim"] - P["blade_w_hub"]) * t)
                off = P["pair_gap"] / 2 + w                      # blade centre-line offset from the pair axis
                xface = x_face - 0.0015 + (P["blade_dish"] + 0.0015) * t ** 1.6   # concave dish: emerges from the plate, outboard at the rim
                ang = base + s * math.atan2(off, r)
                c, sn = math.cos(ang), math.sin(ang)
                radial = Vector((0, c, sn))
                tang = Vector((0, -sn, c))
                centre = radial * (off ** 2 + r ** 2) ** 0.5
                ring = []
                if L["chamfer"]:
                    ch = 0.0035
                    k45 = 1 - math.cos(math.radians(45))
                    pts = [(-w, xface - depth), (w, xface - depth),
                           (w, xface - ch), (w - ch * k45, xface - ch * k45), (w - ch, xface),
                           (-w + ch, xface), (-w + ch * k45, xface - ch * k45), (-w, xface - ch)]
                else:
                    pts = [(-w, xface - depth), (w, xface - depth), (w, xface), (-w, xface)]
                for (tt, xx) in pts:
                    ring.append(centre + tang * tt + Vector((xx, 0, 0)))
                sections.append(ring)
            prism(bm, sections)
    face = new_object("RimFace" + sfx, bm, M["Alloy"], parent)

    # centre cap
    bm = bmesh.new()
    cap = [(x_face + 0.005, 0.0), (x_face + 0.005, 0.026), (x_face + 0.002, 0.030), (x_face - 0.004, 0.030), (x_face - 0.004, 0.0)]
    revolve(bm, cap, L["cap_seg"])
    capob = new_object("CentreCap" + sfx, bm, M["Chrome"], parent)

    # lug nuts: hex across flats lug_af, sitting 1 mm below the plate face inside the pockets
    bm = bmesh.new()
    pr = P["lug_pcd"] / 2
    rr = P["lug_af"] / math.sqrt(3)
    n = L["lug_sides"]
    for k in range(P["lug_count"]):
        a = 2 * math.pi * k / P["lug_count"] + math.pi / 2 + math.pi / P["spoke_pairs"]
        cy, cz = pr * math.cos(a), pr * math.sin(a)
        xb0 = x_face - 0.012
        base_ring = [Vector((xb0, cy + rr * math.cos(2 * math.pi * i / n), cz + rr * math.sin(2 * math.pi * i / n))) for i in range(n)]
        top_ring = [v + Vector((0.009, 0, 0)) for v in base_ring]
        dome = [Vector((0, cy, cz)) + (v - Vector((0, cy, cz))) * 0.65 + Vector((xb0 + 0.011, 0, 0)) for v in base_ring]
        prism(bm, [base_ring, top_ring, dome])
    lugs = new_object("LugNuts" + sfx, bm, M["Chrome"], parent)
    return barrel, face, capob, lugs


def build_brake(L, M, pivot, static, sfx):
    Rd = P["disc_dia"] / 2
    t = P["disc_thick"]
    x1 = 0.020                 # disc front face (toward the rim face)
    x0 = x1 - t                # disc back face
    hat_x = 0.048
    bm = bmesh.new()
    if L["vanes"]:
        plate = 0.010
        prof = [(x1, Rd), (x1 - plate, Rd), (x1 - plate, 0.090), (hat_x - 0.005, 0.090), (hat_x - 0.005, 0.035),
                (hat_x, 0.035), (hat_x, 0.097), (x1, 0.097)]
        revolve(bm, prof, L["disc_seg"])
        revolve(bm, [(x0 + plate, Rd), (x0, Rd), (x0, 0.097), (x0 + plate, 0.097)], L["disc_seg"])
        for k in range(L["vanes"]):
            a = 2 * math.pi * k / L["vanes"]
            ra, rb = 0.100, Rd - 0.003
            hw = 0.003
            c, s = math.cos(a), math.sin(a)
            rad, tan = Vector((0, c, s)), Vector((0, -s, c))
            xa, xb = x0 + plate - 0.001, x1 - plate + 0.001
            b0 = [rad * ra - tan * hw, rad * rb - tan * hw, rad * rb + tan * hw, rad * ra + tan * hw]
            box(bm, [v + Vector((xa, 0, 0)) for v in b0] + [v + Vector((xb, 0, 0)) for v in b0])
    else:
        prof = [(x1, Rd), (x0, Rd), (x0, 0.090), (hat_x - 0.005, 0.090), (hat_x - 0.005, 0.035), (hat_x, 0.035), (hat_x, 0.097), (x1, 0.097)]
        revolve(bm, prof, L["disc_seg"])
    disc = new_object("BrakeDisc" + sfx, bm, M["SteelDisc"], pivot)

    # caliper: arc block wrapping the disc edge, centred at the car rear (-Y)
    bm = bmesh.new()
    h = P["caliper_height"]
    ri, ro = Rd - 0.050, Rd + 0.020
    half_ang = math.asin(min(0.99, (h / 2) / ro))
    dx = (P["caliper_depth"] - t) / 2
    xa, xb = x0 - dx, x1 + dx
    n = L["cal_seg"]
    centre_ang = math.pi  # -Y (car rear) in the (Y, Z) plane: angle measured from +Y toward +Z
    sections = []
    for k in range(n + 1):
        a = centre_ang - half_ang + 2 * half_ang * k / n
        c, s = math.cos(a), math.sin(a)
        rad = Vector((0, c, s))
        ring = [Vector((xa, 0, 0)) + rad * ri, Vector((xa, 0, 0)) + rad * ro, Vector((xa + 0.012, 0, 0)) + rad * (ro + 0.006),
                Vector((xb - 0.012, 0, 0)) + rad * (ro + 0.006), Vector((xb, 0, 0)) + rad * ro, Vector((xb, 0, 0)) + rad * ri]
        sections.append(ring)
    rings = [[bm.verts.new(v) for v in sct] for sct in sections]
    m = len(sections[0])
    for a_, b_ in zip(rings, rings[1:]):
        for j in range(m):
            kk = (j + 1) % m
            bm.faces.new([a_[j], a_[kk], b_[kk], b_[j]])
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    if L["bosses"]:
        for k in (-1, 1):
            a = centre_ang + k * half_ang * 0.55
            c, s = math.cos(a), math.sin(a)
            rad = Vector((0, c, s))
            centre = rad * (ro - 0.004) + Vector((xb - 0.008, 0, 0))
            mat = Matrix.Translation(centre) @ Matrix.Rotation(math.radians(90), 4, "Y")
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.013, radius2=0.011, depth=0.024, matrix=mat)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cal = new_object("Caliper" + sfx, bm, M["CaliperDark"], static)

    # dust shield: thin dished plate behind the disc (r 0.148) + hub stub
    bm = bmesh.new()
    xs = x0 - 0.005
    Rs = P["shield_r"]
    prof = [(xs, Rs), (xs - 0.012, 0.085), (xs - 0.095, 0.085), (xs - 0.095, 0.0), (xs - 0.0145, 0.0),
            (xs - 0.0145, 0.087), (xs - 0.0025, Rs)]
    revolve(bm, prof, L["shield_seg"])
    shield = new_object("DustShield" + sfx, bm, M["Rubber"], static)
    return disc, cal, shield


def build_wheel(lod, root_name, sfx, y_offset):
    L = LOD[lod]
    M = mats()
    root = bpy.data.objects.new(root_name, None)
    root.location = (0, y_offset, 0)
    bpy.context.scene.collection.objects.link(root)
    pivot = bpy.data.objects.new("WheelPivot" + sfx, None)
    pivot.parent = root
    bpy.context.scene.collection.objects.link(pivot)
    static = bpy.data.objects.new("HubStatic" + sfx, None)
    static.parent = root
    bpy.context.scene.collection.objects.link(static)
    for e in (root, pivot, static):
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.1
    build_tyre(L, M, pivot, sfx)
    build_rim(L, M, pivot, sfx)
    build_brake(L, M, pivot, static, sfx)
    return root


# ----------------------------------------------------------------------------- metrics

def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def world_bounds(obs):
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in obs:
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, p))
            mx = Vector(map(max, mx, p))
    return mn, mx


def manifold_report(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bad = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    bm.free()
    return boundary, bad, ngons


def metrics_for(root):
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    bpy.context.view_layer.update()
    per = {}
    for o in meshes:
        mn, mx = world_bounds([o])
        c = (mn + mx) / 2 - root.matrix_world.translation
        boundary, bad, ng = manifold_report(o)
        per[o.name] = dict(triangles=tri_count(o), material=[m.name for m in o.data.materials],
                           parent=o.parent.name, centre_yz_offset_mm=[round(c.y * 1000, 2), round(c.z * 1000, 2)],
                           x_range=[round(mn.x, 4), round(mx.x, 4)], radius_max=round(max(mx.y, mx.z), 4),
                           boundary_edges=boundary, edges_with_3plus_faces=bad, ngons=ng)
    mn, mx = world_bounds(meshes)
    off = root.matrix_world.translation
    return dict(objects=per, triangles_total=sum(v["triangles"] for v in per.values()),
                bounds_m=dict(min=[round(v, 4) for v in (mn - off)], max=[round(v, 4) for v in (mx - off)],
                              size=[round(v, 4) for v in (mx - mn)]))


# ----------------------------------------------------------------------------- renders

def studio_and_render(lod0, lod1):
    os.makedirs(RENDERS, exist_ok=True)
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.42, 0.43, 0.45, 1)
    bg.inputs[1].default_value = 0.7
    R = P["tyre_od"] / 2
    gm = material("GroundMat", (0.30, 0.30, 0.31), 0.0, 0.7)
    ground = bpy.data.meshes.new("ground")
    s = 6.0
    ground.from_pydata([(-s, -s, -R), (s, -s, -R), (s, s, -R), (-s, s, -R)], [], [(0, 1, 2, 3)])
    ground.materials.append(gm)
    g = bpy.data.objects.new("Ground", ground)
    scene.collection.objects.link(g)

    def light(name, loc, rot, energy, size):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)
        return lo

    light("Key", (1.6, -1.2, 1.4), (math.radians(50), 0, math.radians(55)), 350, (1.2, 1.2))
    light("Fill", (1.2, 1.8, 0.6), (math.radians(70), 0, math.radians(150)), 120, (1.6, 1.6))
    light("Rim", (-1.5, 0.5, 1.2), (math.radians(45), 0, math.radians(-110)), 150, (0.8, 0.8))

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 48
    scene.render.resolution_x = scene.render.resolution_y = 1000
    scene.render.image_settings.file_format = "PNG"
    vts = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in vts else "Standard"
    scene.view_settings.exposure = -0.2

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens = 50

    def aim(target, direction, dist, lens=50):
        d = Vector(direction).normalized()
        cam_data.lens = lens
        cam.location = Vector(target) + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()

    def shoot(name):
        scene.render.filepath = os.path.join(RENDERS, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("G4_RENDER", scene.render.filepath, flush=True)
        return scene.render.filepath

    def show(root, flag):
        root.hide_render = not flag
        for o in root.children_recursive:
            o.hide_render = not flag

    out = {}
    show(lod1, False)
    fit = (R * 1.15) / math.tan(math.radians(39.6 / 2))   # frame the 0.66 m wheel with a margin
    aim((0, 0, 0), (1, 0.02, 0.02), fit)
    out["face"] = shoot("wheel_face")
    aim((0, 0, 0), (1, 0.9, 0.45), fit * 1.05)
    out["three_quarter"] = shoot("wheel_34")
    aim((0, 0, 0), (-1, -0.5, 0.25), fit * 1.05)
    out["rear_brake"] = shoot("wheel_rear_brake")
    aim((0, 0, R), (0.55, 0.35, 1.0), 0.55, lens=60)
    out["tread_closeup"] = shoot("wheel_tread_closeup")
    aim((0.07, 0.0, 0.11), (1, 0.35, 0.25), 0.42, lens=60)
    out["spoke_closeup"] = shoot("wheel_spoke_closeup")
    show(lod1, True)
    show(lod0, False)
    aim((0, 1, 0), (1, 0.9, 0.45), fit * 1.05)
    out["lod1_three_quarter"] = shoot("wheel_lod1_34")
    show(lod0, True)
    return out


# ----------------------------------------------------------------------------- main

def build_all():
    scene = bpy.context.scene
    for o in list(scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    lod0 = build_wheel(0, "WheelR", "", 0.0)
    lod1 = build_wheel(1, "WheelR_LOD1", "_LOD1", 1.0)
    bpy.context.view_layer.update()
    m0, m1 = metrics_for(lod0), metrics_for(lod1)

    os.makedirs(WIP, exist_ok=True)
    os.makedirs(REPORTS, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    for o in scene.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", export_apply=True, export_yup=True,
                              use_selection=True, export_cameras=False, export_lights=False)
    renders = studio_and_render(lod0, lod1)

    def budget(m, limits):
        groups = dict(tyre=["Tyre"], rim=["RimBarrel", "RimFace", "CentreCap", "LugNuts"], brake=["BrakeDisc", "Caliper", "DustShield"])
        res = {}
        for gname, names in groups.items():
            tris = sum(v["triangles"] for k, v in m["objects"].items() if k.split("_LOD1")[0] in names)
            res[gname] = dict(triangles=tris, limit=limits.get(gname), ok=(limits.get(gname) is None or tris <= limits[gname]))
        res["total"] = dict(triangles=m["triangles_total"], limit=limits["total"], ok=m["triangles_total"] <= limits["total"])
        return res

    b0 = budget(m0, dict(tyre=3500, rim=3500, brake=1500, total=9000))
    b1 = budget(m1, dict(total=2500))
    revolved = ("Tyre", "RimBarrel", "CentreCap", "BrakeDisc", "DustShield")
    conc = max(abs(c) for k, v in m0["objects"].items() if k in revolved for c in v["centre_yz_offset_mm"])
    tyre = m0["objects"]["Tyre"]
    rim = m0["objects"]["RimBarrel"]
    handoff = dict(
        component_id="player_sedan.wheel_assembly.R",
        gate="G4",
        version=VERSION,
        generated=time.strftime("%Y-%m-%d %H:%M:%S"),
        source_script=os.path.relpath(os.path.abspath(__file__), os.path.dirname(HERE)).replace("\\", "/"),
        source_blend=os.path.relpath(BLEND, os.path.dirname(HERE)).replace("\\", "/"),
        export_path=os.path.relpath(GLB, os.path.dirname(HERE)).replace("\\", "/"),
        units="m",
        coordinate_system="Blender local: axle = +X, right-wheel face at +X, origin at hub centre, spin about local X. "
                          "Exported Y-up (export_yup=True): X axis preserved, so Godot spins about local X as well. "
                          "LOD1 root offset +1 m Blender Y (= -1 m Godot Z).",
        parameters=P,
        lod0=dict(bounds_m=m0["bounds_m"], triangles=m0["objects"], triangles_total=m0["triangles_total"], budgets=b0),
        lod1=dict(bounds_m=m1["bounds_m"], triangles=m1["objects"], triangles_total=m1["triangles_total"], budgets=b1),
        material_slots=sorted({m for v in m0["objects"].values() for m in v["material"]}),
        pivot=dict(WheelPivot="empty at the hub centre; children Tyre, RimBarrel, RimFace, CentreCap, LugNuts, BrakeDisc spin about local X",
                   HubStatic="sibling empty at the same origin; children Caliper (rear / -Y position) and DustShield stay fixed",
                   root="WheelR (LOD0) and WheelR_LOD1 (+1 m Y)"),
        reference_ids=["production/references/dimension_sheet.json (tyre_diameter, tyre_width, rim_diameter)",
                       "production/references/ref_left_side.webp (twin-spoke styling)",
                       "production/references/ref_front.webp (tyre shoulder / tread)"],
        renders={k: os.path.relpath(v, os.path.dirname(HERE)).replace("\\", "/") for k, v in renders.items()},
        known_defects=[
            "Transverse block cuts are 96 dark decal quads (RubberCut slot) lying 0.4 mm above the tread facets of the two outer ribs, "
            "not cut geometry; they are loose faces (384 boundary edges in Tyre by design). Circumferential grooves are real geometry.",
            "Lug pockets are made with an EXACT boolean on the hub plate (n-gons triangulated); the blades interpenetrate the plate "
            "and the rolled lip rather than being unioned, each blade is its own closed shell.",
            "Alloy/Chrome/SteelDisc look flat grey under the uniform grey studio world (no HDRI); re-check materials in Godot.",
            "DustShield is parented to HubStatic (fixed) rather than WheelPivot: radially symmetric, no visual difference.",
            "Lettering is two plain raised ribs on the outer (+X) sidewall only; the tyre is not mirror-symmetric in X.",
            "Tyre revolve is 48 segments (7.5 deg) to stay under 3,500 tris with the richer profile; silhouette chord error 0.7 mm.",
        ],
        QA_status="pending",
        tests_run=[
            dict(name="triangle_budgets", result=b0, passed=all(v["ok"] for v in b0.values()) and all(v["ok"] for v in b1.values())),
            dict(name="concentricity_bbox", detail="max |bbox centre Y/Z| over the revolved meshes Tyre, RimBarrel, CentreCap, BrakeDisc, DustShield (mm); "
                 "RimFace/LugNuts/Caliper are not rotationally symmetric so their bbox centre is legitimately off-axis",
                 value_mm=round(conc, 3), passed=conc < 0.5),
            dict(name="tyre_dimensions", detail=dict(od_m=round(tyre["radius_max"] * 2, 4), width_m=round(tyre["x_range"][1] - tyre["x_range"][0], 4),
                                                     rim_face_x=rim["x_range"][1], tyre_outer_x=tyre["x_range"][1],
                                                     face_inset_m=round(tyre["x_range"][1] - rim["x_range"][1], 4)),
                 passed=abs(tyre["radius_max"] * 2 - P["tyre_od"]) < 0.002 and abs(tyre["x_range"][1] - tyre["x_range"][0] - P["tyre_width"]) < 0.002),
            dict(name="manifold_ngons", detail={k: dict(boundary_edges=v["boundary_edges"], edges_with_3plus_faces=v["edges_with_3plus_faces"], ngons=v["ngons"])
                                                for k, v in m0["objects"].items()},
                 note="boundary edges are allowed only on Tyre (decal cut quads); every other mesh must be closed",
                 passed=all(v["edges_with_3plus_faces"] == 0 and v["ngons"] == 0 for v in m0["objects"].values())
                 and all(v["boundary_edges"] == 0 for k, v in m0["objects"].items() if k != "Tyre")),
            dict(name="glb_reimport", passed=None, detail="run with -- --verify"),
        ],
    )
    json.dump(handoff, open(HANDOFF, "w"), indent=1)
    print("G4_HANDOFF", HANDOFF)
    print("G4_TRIS LOD0", m0["triangles_total"], "LOD1", m1["triangles_total"])
    print("G4_PER", json.dumps({k: v["triangles"] for k, v in m0["objects"].items()}), json.dumps({k: v["triangles"] for k, v in m1["objects"].items()}))
    print("G4_BUDGETS", json.dumps(b0), json.dumps(b1))
    print("G4_CONC_mm", round(conc, 3))
    print("G4_TESTS", [(t["name"], t["passed"]) for t in handoff["tests_run"]])
    print("G4_MANIFOLD", json.dumps(handoff["tests_run"][3]["detail"]))


def verify():
    scene = bpy.context.scene
    for o in list(scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=GLB)
    bpy.context.view_layer.update()

    def tree(o, depth=0):
        lines = [("  " * depth) + f"{o.name} [{o.type}]" + (f" tris={tri_count(o)} mat={[m.name for m in o.data.materials]}" if o.type == "MESH" else
                                                              f" loc={[round(v, 3) for v in o.location]}")]
        for c in sorted(o.children, key=lambda c: c.name):
            lines += tree(c, depth + 1)
        return lines

    roots = [o for o in scene.objects if o.parent is None]
    lines = []
    for r in sorted(roots, key=lambda r: r.name):
        lines += tree(r)
    names = {o.name for o in scene.objects}
    expected = {"WheelR", "WheelPivot", "HubStatic", "Tyre", "RimBarrel", "RimFace", "CentreCap", "LugNuts", "BrakeDisc", "Caliper", "DustShield",
                "WheelR_LOD1", "WheelPivot_LOD1", "HubStatic_LOD1", "Tyre_LOD1", "RimBarrel_LOD1", "RimFace_LOD1", "CentreCap_LOD1",
                "LugNuts_LOD1", "BrakeDisc_LOD1", "Caliper_LOD1", "DustShield_LOD1"}
    missing = sorted(expected - names)
    cal = bpy.data.objects.get("Caliper")
    cal_ok = cal is not None and cal.parent is not None and cal.parent.name == "HubStatic"
    tyre = bpy.data.objects.get("Tyre")
    tyre_ok = tyre is not None and tyre.parent is not None and tyre.parent.name == "WheelPivot"
    lod1 = bpy.data.objects.get("WheelR_LOD1")
    mn, mx = world_bounds([o for o in scene.objects if o.type == "MESH" and o.name.endswith("_LOD1") is False])
    result = dict(name="glb_reimport",
                  passed=(not missing) and cal_ok and tyre_ok and lod1 is not None and abs(lod1.location.y - 1.0) < 1e-3,
                  detail=dict(missing=missing, caliper_parent=cal.parent.name if cal and cal.parent else None,
                              tyre_parent=tyre.parent.name if tyre and tyre.parent else None,
                              lod1_root_location_blender=[round(v, 3) for v in lod1.location] if lod1 else None,
                              lod0_bounds_after_reimport=dict(min=[round(v, 4) for v in mn], max=[round(v, 4) for v in mx]),
                              hierarchy=lines))
    print("\n".join(lines))
    h = json.load(open(HANDOFF))
    h["tests_run"] = [t for t in h["tests_run"] if t["name"] != "glb_reimport"] + [result]
    json.dump(h, open(HANDOFF, "w"), indent=1)
    print("G4_REIMPORT", "PASS" if result["passed"] else "FAIL", json.dumps({k: v for k, v in result["detail"].items() if k != "hierarchy"}))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--verify" in argv:
        verify()
    else:
        build_all()
