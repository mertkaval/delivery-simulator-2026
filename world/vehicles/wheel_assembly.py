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
VERSION = "0.6.1"

# ----------------------------------------------------------------------------- parameters
P = dict(
    tyre_od=0.66,        # outer diameter (m)
    tyre_width=0.225,    # section width (m)
    rim_dia=0.432,       # bead seat diameter (m)
    rim_width=0.19,      # bead-to-bead (m)
    face_inset=0.02,     # rim face sits this far inside the tyre outer sidewall
    spoke_pairs=5,       # twin spokes -> 10 blades
    spoke_w_rim=0.105,   # wedge spoke width at the rim (m)
    spoke_w_hub=0.060,   # wedge spoke width at the hub root (m)
    groove_w=0.006,      # centre groove splitting the wedge (twin-spoke read), width (m)
    groove_d=0.004,      # centre groove depth (m)
    root_flare=0.012,    # extra width blending the root into the dome (m)
    face_lift=0.0,       # v0.6.1: spoke tips flush with the rolled lip
    blade_dish=0.035,    # rim end sits this much further outboard than the hub end
    blade_depth=0.030,
    well_depth=0.040,    # dark well floor this far behind the blade face at the rim
    hub_plate_r=0.072,   # shallow dome, ~33 % of the rim diameter
    lug_count=5,
    lug_pcd=0.112,
    lug_af=0.019,        # nut across flats (m)
    pocket_r=0.0125,
    disc_dia=0.30,
    disc_thick=0.028,
    caliper_arc=0.17,    # body length along the disc arc (m)
    caliper_r=(0.085, 0.157),
    caliper_width=0.068, # straddling the disc (m)
    shield_r=0.140,
)

LOD = {
    0: dict(tyre_seg=48, detail=True, tread_cuts=48, rim_seg=40, hub_seg=40, spoke_steps=4, chamfer=True, pockets=True,
            pocket_seg=16, lug_sides=6, cap_seg=24, disc_seg=30, vanes=16, cal_seg=5, cal_detail=True, shield_seg=24),
    1: dict(tyre_seg=24, detail=False, tread_cuts=0, rim_seg=20, hub_seg=16, spoke_steps=1, chamfer=False, pockets=False,
            pocket_seg=8, lug_sides=4, cap_seg=10, disc_seg=16, vanes=0, cal_seg=2, cal_detail=False, shield_seg=14),
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
        SteelDisc=material("SteelDisc", (0.34, 0.33, 0.32), 1.0, 0.45),
        CaliperDark=material("CaliperDark", (0.11, 0.11, 0.115), 0.0, 0.55),
        BrakePad=material("BrakePad", (0.20, 0.17, 0.15), 0.0, 0.8),
        ShieldSteel=material("ShieldSteel", (0.09, 0.09, 0.095), 0.6, 0.6),
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


def revolve(bm, profile, seg, start=0.0, closed=True, mat_index=0, span_mat=None):
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
                f.material_index = span_mat.get(j, mat_index) if span_mat else mat_index
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
    span_mat = {}
    # outer (face-side) sidewall: bead, rim-protector rib, continuous curve with two 1.2 mm lettering ribs
    prof = [(xf + 0.002, Rb)]
    if det:
        prof += [(0.106, 0.240), (0.1035, 0.247)]                                     # rim-protector rib
        prof += [(0.1063, 0.255), (0.1065, 0.262), (0.1093, 0.270), (0.1095, 0.277)]                  # ribs on the curve
        prof += arc(th, R - sh, sh, 0, 90, 4)                                         # rounded shoulder
    else:
        prof += [(0.1063, 0.255), (0.1065, 0.262), (0.1093, 0.270), (0.1095, 0.277)]
        prof += arc(th, R - sh, sh, 0, 90, 3)
    # tread: 4 circumferential grooves (2 wide flat-bottom centre, 2 narrow V outer); groove bottoms on the RubberCut slot
    for xc, hw, d, flat in [(0.047, 0.003, 0.0085, det), (0.017, 0.0045, 0.009, det),
                            (-0.017, 0.0045, 0.009, det), (-0.047, 0.003, 0.0085, det)]:
        if flat:
            prof += [(xc + hw, R), (xc + hw * 0.6, R - d), (xc - hw * 0.6, R - d), (xc - hw, R)]
            span_mat[len(prof) - 3] = 1
        else:
            prof += [(xc + hw, R), (xc, R - d), (xc - hw, R)]
            span_mat[len(prof) - 3] = 1
            span_mat[len(prof) - 2] = 1
    prof += arc(-th, R - sh, sh, 90, 180, 3)
    prof += [(-W2 + 0.004, Rb + 0.030), (-(xf + 0.002), Rb)]
    prof += [(-(xf - 0.004), Rb - 0.014), ((xf - 0.004), Rb - 0.014)]               # hidden inner carcass
    bm = bmesh.new()
    seg = L["tyre_seg"]
    revolve(bm, prof, seg, span_mat=span_mat)
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
                f.normal_update()
                if f.normal.dot(rad) < 0:
                    f.normal_flip()
    return new_object("Tyre" + sfx, bm, M["Rubber"], parent, sharp_deg=48, extra_mats=(M["RubberCut"],))


def build_rim(L, M, parent, sfx):
    Rb = P["rim_dia"] / 2
    W2 = P["tyre_width"] / 2
    xf = W2 - P["face_inset"]              # outer flange plane
    xb = xf - P["rim_width"]               # inner bead plane
    wd = P["well_depth"]
    # barrel: bead seats, rolled outer lip (r 0.011), cylinder behind the blades, step down to the dark well floor,
    # back flange closed by a recessed cone (kept dark from behind)
    lip_c = (xf - 0.011, Rb + 0.004)
    if L["detail"]:
        prof = [(xb, Rb - 0.006), (xb + 0.006, Rb + 0.002), (xf - 0.022, Rb + 0.002)]
        prof += arc(lip_c[0], lip_c[1], 0.011, 160, -70, 6)
        prof += [(xf - 0.008, Rb - 0.014), (xf - 0.004 - wd, Rb - 0.014),
                 (xf - 0.004 - wd - 0.016, Rb - 0.046), (xb + 0.012, Rb - 0.046)]
    else:
        prof = [(xb, Rb - 0.006), (xf - 0.016, Rb + 0.002), (xf, Rb + 0.012), (xf - 0.004, Rb - 0.012),
                (xf - 0.004 - wd, Rb - 0.014), (xf - 0.004 - wd - 0.016, Rb - 0.046), (xb + 0.012, Rb - 0.046)]
    bm = bmesh.new()
    revolve(bm, prof, L["rim_seg"])
    barrel = new_object("RimBarrel" + sfx, bm, M["RimWell"], parent)

    # face: five broad wedge spokes with a centre groove, unioned into a step-free shallow dome (one surface)
    hub_r = P["hub_plate_r"]
    x_rim_face = xf - 0.004 + P["face_lift"]     # spoke face at the rim (lifted outboard so the lip rings around the tips)
    x_face = x_rim_face - P["blade_dish"]        # dome edge / spoke face at the hub
    x_dome = x_face + 0.006                      # dome centre
    x_back = x_face - 0.030
    dome = [(x_dome, 0.0), (x_dome - 0.0012, 0.030), (x_dome - 0.0035, 0.055), (x_face, hub_r - 0.003),
            (x_face - 0.003, hub_r), (x_back, hub_r), (x_back, 0.0)]
    pairs = P["spoke_pairs"]
    steps = L["spoke_steps"]
    r0, r1 = 0.050, Rb - 0.002
    depth = P["blade_depth"]
    sb = bmesh.new()
    for p in range(pairs):
        base = 2 * math.pi * p / pairs + math.pi / 2     # first spoke at 12 o'clock
        A = Vector((0, math.cos(base), math.sin(base)))
        T = Vector((0, -math.sin(base), math.cos(base)))
        sections = []
        for t in [k / steps for k in range(steps + 1)]:
            u = r0 + (r1 - r0) * t
            w = P["spoke_w_hub"] + (P["spoke_w_rim"] - P["spoke_w_hub"]) * t + P["root_flare"] * (1 - t) ** 5
            xface = x_face - 0.0005 + (P["blade_dish"] + 0.0005) * t ** 1.3
            if L["chamfer"]:
                ch, g, gd = 0.003, P["groove_w"] / 2, P["groove_d"]
                pts = [(-w / 2, xface - depth), (w / 2, xface - depth), (w / 2, xface - ch), (w / 2 - ch, xface),
                       (g, xface), (g, xface - gd), (-g, xface - gd), (-g, xface),
                       (-w / 2 + ch, xface), (-w / 2, xface - ch)]
            else:
                pts = [(-w / 2, xface - depth), (w / 2, xface - depth), (w / 2, xface), (-w / 2, xface)]
            if t >= 1.0:   # arc-cut tip concentric with the lip
                sections.append([A * math.sqrt(max(r1 * r1 - tt * tt, 0.0)) + T * tt + Vector((xx, 0, 0)) for (tt, xx) in pts])
            else:
                sections.append([A * u + T * tt + Vector((xx, 0, 0)) for (tt, xx) in pts])
        prism(sb, sections)
    bm = bmesh.new()
    union_ok = False
    if L["pockets"]:
        def temp_object(name, src_bm):
            bmesh.ops.remove_doubles(src_bm, verts=src_bm.verts, dist=1e-6)
            me = bpy.data.meshes.new(name)
            src_bm.to_mesh(me)
            src_bm.free()
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(ob)
            return ob
        pb = bmesh.new()
        revolve(pb, dome, L["hub_seg"])
        pob = temp_object("hubdome_tmp", pb)
        cb = bmesh.new()
        pr = P["lug_pcd"] / 2
        for k in range(P["lug_count"]):
            a = 2 * math.pi * k / P["lug_count"] + math.pi / 2 + math.pi / P["spoke_pairs"]
            cy, cz = pr * math.cos(a), pr * math.sin(a)
            mat = Matrix.Translation((x_dome, cy, cz)) @ Matrix.Rotation(math.radians(90), 4, "Y")
            bmesh.ops.create_cone(cb, cap_ends=True, segments=L["pocket_seg"], radius1=P["pocket_r"], radius2=P["pocket_r"],
                                  depth=0.016, matrix=mat)
            mat2 = Matrix.Translation((x_dome - 0.0035, cy, cz)) @ Matrix.Rotation(math.radians(90), 4, "Y")   # 3 mm chamfer at the mouth
            bmesh.ops.create_cone(cb, cap_ends=True, segments=L["pocket_seg"], radius1=P["pocket_r"], radius2=P["pocket_r"] + 0.0035,
                                  depth=0.007, matrix=mat2)
        cob = temp_object("cutter_tmp", cb)
        sob = temp_object("spokes_tmp", sb)
        for name, op, target in (("spokes", "UNION", sob), ("pockets", "DIFFERENCE", cob)):
            mod = pob.modifiers.new(name, "BOOLEAN")
            mod.operation = op
            mod.object = target
            try:
                mod.solver = "EXACT"
            except TypeError:
                pass
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        n_eval = len(pob.evaluated_get(dg).to_mesh().polygons)
        pob.evaluated_get(dg).to_mesh_clear()
        if n_eval > 0:
            evaluated_into_bmesh(pob, bm)
            union_ok = True
            for ob in (cob, sob):
                me = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                bpy.data.meshes.remove(me)
        else:   # boolean failed: fall back to overlapping shells
            pob.modifiers.clear()
            evaluated_into_bmesh(pob, bm)
            evaluated_into_bmesh(sob, bm)
            me = cob.data
            bpy.data.objects.remove(cob, do_unlink=True)
            bpy.data.meshes.remove(me)
    else:
        revolve(bm, dome, L["hub_seg"])
        bmesh.ops.remove_doubles(sb, verts=sb.verts, dist=1e-6)
        tmp = bpy.data.meshes.new("spokes_lod_tmp")
        sb.to_mesh(tmp)
        sb.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    face = new_object("RimFace" + sfx, bm, M["Alloy"], parent)
    face["face_union"] = union_ok
    # window fraction of the face annulus between dome edge and lip inner edge (reported, not enforced)
    r_lip = Rb - 0.014
    n_int = 200
    spoke_area = 0.0
    for k in range(n_int):
        t = (k + 0.5) / n_int
        u = r0 + (r1 - r0) * t
        if hub_r <= u <= r_lip:
            spoke_area += (P["spoke_w_hub"] + (P["spoke_w_rim"] - P["spoke_w_hub"]) * t) * (r1 - r0) / n_int
    annulus = math.pi * (r_lip ** 2 - hub_r ** 2)
    face["window_fraction"] = round(1.0 - pairs * spoke_area / annulus, 3)
    face["window_arc_at_rim_m"] = round((2 * math.pi * r_lip - pairs * P["spoke_w_rim"]) / pairs, 3)
    face["window_arc_at_r150_m"] = round((2 * math.pi * 0.15 - pairs * (P["spoke_w_hub"] + (P["spoke_w_rim"] - P["spoke_w_hub"]) * (0.15 - r0) / (r1 - r0))) / pairs, 3)

    # centre cap: r 0.028 with a 2 mm raised lip
    bm = bmesh.new()
    xc = x_dome
    cap = [(xc + 0.004, 0.0), (xc + 0.004, 0.022), (xc + 0.006, 0.024), (xc + 0.006, 0.028), (xc - 0.006, 0.028), (xc - 0.006, 0.0)]
    revolve(bm, cap, L["cap_seg"])
    capob = new_object("CentreCap" + sfx, bm, M["Chrome"], parent)

    # lug nuts: hex across flats lug_af, top 1 mm below the dome surface inside the pockets
    bm = bmesh.new()
    pr = P["lug_pcd"] / 2
    rr = P["lug_af"] / math.sqrt(3)
    n = L["lug_sides"]
    for k in range(P["lug_count"]):
        a = 2 * math.pi * k / P["lug_count"] + math.pi / 2 + math.pi / P["spoke_pairs"]
        cy, cz = pr * math.cos(a), pr * math.sin(a)
        xb0 = x_dome - 0.0161            # nut crown 1.5 mm below the local dome surface
        base_ring = [Vector((xb0, cy + rr * math.cos(2 * math.pi * i / n), cz + rr * math.sin(2 * math.pi * i / n))) for i in range(n)]
        top_ring = [v + Vector((0.008, 0, 0)) for v in base_ring]
        dome_ring = [Vector((0, cy, cz)) + (v - Vector((0, cy, cz))) * 0.65 + Vector((xb0 + 0.010, 0, 0)) for v in base_ring]
        prism(bm, [base_ring, top_ring, dome_ring])
    lugs = new_object("LugNuts" + sfx, bm, M["Chrome"], parent)
    return barrel, face, capob, lugs


def arc_prism(bm, section_fn, a0, a1, n, mat_index=0):
    """Sweep a section (function of angle -> list of Vector) from angle a0 to a1 in n steps, capped."""
    sections = [section_fn(a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    rings = [[bm.verts.new(v) for v in s] for s in sections]
    m = len(sections[0])
    faces = []
    for a_, b_ in zip(rings, rings[1:]):
        for j in range(m):
            kk = (j + 1) % m
            faces.append(bm.faces.new([a_[j], a_[kk], b_[kk], b_[j]]))
    faces.append(bm.faces.new(rings[0]))
    faces.append(bm.faces.new(list(reversed(rings[-1]))))
    for f in faces:
        f.material_index = mat_index
    return faces


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
        prof = [(x1, Rd), (x0, Rd), (x0, 0.090), (hat_x - 0.003, 0.090), (hat_x, 0.097), (x1, 0.097)]
        revolve(bm, prof, L["disc_seg"])
    disc = new_object("BrakeDisc" + sfx, bm, M["SteelDisc"], pivot)

    # caliper: fixed two-piece body straddling the disc at the car rear (-Y); angles measured from +Y toward +Z
    bm = bmesh.new()
    ri, ro = P["caliper_r"]
    r_mid = (ri + ro) / 2
    half_ang = (P["caliper_arc"] / 2) / r_mid
    xc = (x0 + x1) / 2
    hw = P["caliper_width"] / 2
    xa, xb = xc - hw, xc + hw                   # inboard / outboard outer faces
    gap = 0.0025                                # clearance to each disc face (pads live here)
    centre_ang = math.pi
    n = L["cal_seg"]

    def rad(a):
        return Vector((0, math.cos(a), math.sin(a)))

    def X(x):
        return Vector((x, 0, 0))

    def half_section(xi, xo):
        def fn(a):
            r_ = rad(a)
            rr = ro - 0.007                      # halves stop just under the bridge
            return [X(xi) + r_ * ri, X(xi) + r_ * (rr - 0.008), X(xi + 0.006) + r_ * rr,
                    X(xo - 0.006) + r_ * rr, X(xo) + r_ * (rr - 0.008), X(xo) + r_ * ri]
        return fn
    arc_prism(bm, half_section(xa, x0 - gap), centre_ang - half_ang, centre_ang + half_ang, n)       # inboard half
    arc_prism(bm, half_section(x1 + gap, xb), centre_ang - half_ang, centre_ang + half_ang, n)       # outboard half
    # bridges over the disc edge: two ends + centre, rounded top; the openings between them are the pad windows
    detail = L["cal_detail"]
    bw = 0.09 if detail else 2 * half_ang

    def bridge(a):
        r_ = rad(a)
        return [X(xa + 0.004) + r_ * (ro - 0.014), X(xa + 0.004) + r_ * (ro - 0.004), X(xa + 0.012) + r_ * ro,
                X(xb - 0.012) + r_ * ro, X(xb - 0.004) + r_ * (ro - 0.004), X(xb - 0.004) + r_ * (ro - 0.014)]
    for ac in ([-half_ang + bw / 2, 0.0, half_ang - bw / 2] if detail else [0.0]):
        arc_prism(bm, bridge, centre_ang + ac - bw / 2, centre_ang + ac + bw / 2, 2 if detail else n)
    if detail:
        # pads (backing plate + friction material) against each disc face, visible through the windows
        for (pi_, po_) in ((x0 - gap - 0.0005, x0 - 0.0005), (x1 + 0.0005, x1 + gap + 0.0005)):
            def pad(a, pi_=pi_, po_=po_):
                r_ = rad(a)
                return [X(pi_) + r_ * 0.100, X(pi_) + r_ * (Rd - 0.004), X(po_) + r_ * (Rd - 0.004), X(po_) + r_ * 0.100]
            arc_prism(bm, pad, centre_ang - half_ang + 0.06, centre_ang + half_ang - 0.06, 3, mat_index=1)
        # two bolt bosses on the outboard face
        for k in (-1, 1):
            a = centre_ang + k * half_ang * 0.5
            centre = rad(a) * (ri + 0.028) + Vector((xb - 0.006, 0, 0))
            mat = Matrix.Translation(centre) @ Matrix.Rotation(math.radians(90), 4, "Y")
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.012, radius2=0.010, depth=0.022, matrix=mat)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cal = new_object("Caliper" + sfx, bm, M["CaliperDark"], static, extra_mats=(M["BrakePad"],))

    # dust shield: thin dished plate behind the disc (r shield_r) + hub stub, own ShieldSteel slot
    bm = bmesh.new()
    xs = x0 - 0.006
    Rs = P["shield_r"]
    if L["detail"]:
        prof = [(xs, Rs), (xs - 0.012, 0.085), (xs - 0.095, 0.085), (xs - 0.095, 0.0), (xs - 0.0145, 0.0),
                (xs - 0.0145, 0.087), (xs - 0.0025, Rs)]
    else:
        prof = [(xs, Rs), (xs - 0.012, 0.085), (xs - 0.095, 0.085), (xs - 0.095, 0.0), (xs - 0.0025, Rs)]
    revolve(bm, prof, L["shield_seg"])
    shield = new_object("DustShield" + sfx, bm, M["ShieldSteel"], static)
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
        mn, mx = mn - root.matrix_world.translation, mx - root.matrix_world.translation
        c = (mn + mx) / 2
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
    bg.inputs[1].default_value = 0.5
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

    light("Key", (1.6, -1.2, 1.4), (math.radians(50), 0, math.radians(55)), 260, (1.2, 1.2))
    light("Fill", (1.2, 1.8, 0.6), (math.radians(70), 0, math.radians(150)), 80, (1.6, 1.6))
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
    scene.view_settings.exposure = -1.1

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
    aim((0.06, 0.0, 0.10), (1, 0.35, 0.25), 0.42, lens=60)
    out["spoke_closeup"] = shoot("wheel_spoke_closeup")
    aim((0.03, -0.13, 0.0), (1, -0.12, 0.08), 1.5, lens=135)      # through the 9 o'clock window from 1.5 m
    out["caliper_window"] = shoot("wheel_caliper_window")
    show(lod1, True)
    show(lod0, False)
    aim((0, 1, 0), (1, 0.9, 0.45), fit * 1.05)
    out["lod1_three_quarter"] = shoot("wheel_lod1_34")
    show(lod0, True)
    out["face_vs_ref"] = composite_face_vs_ref(out["face"])
    return out


def composite_face_vs_ref(face_png):
    """Side-by-side: our face render next to the front wheel of ref_left_side.webp scaled to the same pixel diameter."""
    import numpy as np
    ref_path = os.path.join(PROD, "references", "ref_left_side.webp")
    sheet = json.load(open(os.path.join(PROD, "references", "dimension_sheet.json")))["sources"]["left"]
    cx, dia = sheet["front_wheel_x"], sheet["wheel_dia_px"][0]
    cy = sheet["ground_y"] - dia / 2

    def load(path):
        img = bpy.data.images.load(path, check_existing=False)
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        return px.reshape(h, w, 4)[::-1]          # top row first

    face = load(face_png)
    ref = load(ref_path)
    H, W = face.shape[:2]
    our_dia = int(W / 1.15)                      # the face camera frames the 0.66 m wheel at 1/1.15 of the frame width
    # reference tyre diameter: outermost dark pixels on the wheel-centre row within +-0.75 sheet diameters of front_wheel_x
    win = int(dia * 0.75)
    seg = ref[int(cy), max(0, int(cx) - win):int(cx) + win, :3].mean(axis=1)
    dk = np.where(seg < 0.06)[0]                 # pixels come back linear: tyre ~0.01, grey paint ~0.2
    dia_sheet = dia
    if len(dk) > 2:
        dia = int(dk[-1] - dk[0])
        cx = max(0, int(cx) - win) + (dk[0] + dk[-1]) / 2
    crop_half = int(dia * 0.62)
    y0, y1 = int(max(0, cy - crop_half)), int(min(ref.shape[0], cy + crop_half))
    x0, x1 = int(max(0, cx - crop_half)), int(min(ref.shape[1], cx + crop_half))
    crop = ref[y0:y1, x0:x1]
    scale = our_dia / dia
    oh, ow = int(crop.shape[0] * scale), int(crop.shape[1] * scale)
    ys = np.clip((np.arange(oh) / scale).astype(int), 0, crop.shape[0] - 1)
    xs = np.clip((np.arange(ow) / scale).astype(int), 0, crop.shape[1] - 1)
    scaled = crop[ys][:, xs]
    out = np.zeros((H, W * 2, 4), dtype=np.float32)
    out[..., 3] = 1.0
    out[:, :W] = face
    oh, ow = min(oh, H), min(ow, W)
    oy, ox = (H - oh) // 2, W + (W - ow) // 2
    out[oy:oy + oh, ox:ox + ow] = scaled[:oh, :ow]
    img = bpy.data.images.new("face_vs_ref", W * 2, H, alpha=True)
    img.pixels.foreach_set(out[::-1].ravel())
    path = os.path.join(RENDERS, "wheel_face_vs_ref.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    chk = out[H // 2, W:, :3].mean(axis=1)
    ck = np.where(chk < 0.06)[0]
    print("G4_COMPOSITE_CHECK ref_tyre_px_in_composite", int(ck[-1] - ck[0]) if len(ck) > 2 else None, "target", our_dia, flush=True)
    print("G4_RENDER", path, "our_dia_px", our_dia, "ref_dia_px_measured", dia, "ref_dia_px_sheet", dia_sheet, flush=True)
    return path


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
        rim_face=dict(spokes_unioned_into_dome=bool(bpy.data.objects["RimFace"].get("face_union")),
                      window_fraction_of_face_annulus=bpy.data.objects["RimFace"].get("window_fraction"),
                      window_arc_at_lip_m=bpy.data.objects["RimFace"].get("window_arc_at_rim_m"),
                      window_arc_at_r0150_m=bpy.data.objects["RimFace"].get("window_arc_at_r150_m"),
                      note="spec asked 0.105/0.060 wedges AND ~35 % windows; with these widths the window share is what is reported here"),
        pivot=dict(WheelPivot="empty at the hub centre; children Tyre, RimBarrel, RimFace, CentreCap, LugNuts, BrakeDisc spin about local X",
                   HubStatic="sibling empty at the same origin; children Caliper (rear / -Y position) and DustShield stay fixed",
                   root="WheelR (LOD0) and WheelR_LOD1 (+1 m Y)"),
        reference_ids=["production/references/dimension_sheet.json (tyre_diameter, tyre_width, rim_diameter)",
                       "production/references/ref_left_side.webp (twin-spoke styling)",
                       "production/references/ref_front.webp (tyre shoulder / tread)"],
        renders={k: os.path.relpath(v, os.path.dirname(HERE)).replace("\\", "/") for k, v in renders.items()},
        known_defects=[
            "Spoke widths follow the spec (0.105 rim / 0.060 hub); the resulting open-window share of the face annulus is reported in rim_face "
            "and is larger than the ~35 % quoted, because 5 x 0.105 m only closes 35 % of the circumference at r ~0.15, not at the lip.",
            "Transverse block cuts are 96 dark decal quads (RubberCut) 0.4 mm proud of the outer-rib facets; z-fight to be checked in Godot.",
            "Hub dome r 0.072 (33 % of rim) as in v0.5 for pocket clearance on the 0.112 PCD.",
            "Caliper pads show only their top edge through the bridge windows; caliper/lip/spoke-tip shells interpenetrate (only dome+spokes+pockets are booleaned).",
            "Metals look flat under the grey studio world (no HDRI); re-check in Godot. DustShield parented to HubStatic (fixed).",
            "LOD1 tyre is a 24-gon; expect a visible LOD pop under ~15 m.",
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
