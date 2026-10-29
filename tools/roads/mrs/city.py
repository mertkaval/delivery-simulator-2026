"""Mert Road Studio builds a whole city's streets: the CityForge plan of Port Halden (city.json + graded heights)
becomes MRS roads, junctions, back lanes with dropped-kerb driveways and rule-placed street assets, which replace
CityForge's own road ribbons and street furniture in the game.

    import mrs; from mrs import city
    net = city.build(plan_dir)                     # roads, lanes, junctions, anchors, placement (in the context scene)
    city.export(out_dir)                           # per-chunk GLBs, asset kit, instance records, graded heights

The network comes from mrs.citynet (graph cleanup); everything placed on it uses the same tools as the street
block (junction.build_junction, placement.place_all). Plan metres (x east, y north) map to Blender as
(x - 1024, y - 1024, h), the CityForge contract, so Godot puts the exported chunks at the origin like its own."""
import bpy, json, math, os, time
from mathutils import Vector
from .nodes import MRS, set_scene, mod_input_set
from . import roads, junction, placement, citynet, structures

COL = "PH_Roads"
HALF = 1024.0
STATE = {}                     # plan, net, heights, timings of the last build
CF_REPLACED = ("lamp", "traffic_light", "bus_stop", "hydrant", "bench", "stop_sign", "street_sign")   # CityForge props the MRS placement replaces
CF_KEPT = {"vending_machine": 0.7, "post_box": 0.5, "phone_box": 0.8, "ad_column": 0.8, "cesme": 1.0, "cafe_set": 1.6, "utility_pole": 0.5}


BASE_VERSION = 4          # bump when tools/roads/mrs changes the node groups or the asset library


def ensure_base(path, rebuild=False, log=print):
    """Open the MRS base library (node groups, materials, asset collections) saved at `path`, building and saving it
    first (~6 min) when it is missing, older than BASE_VERSION or `rebuild`. Returns the reloaded mrs package."""
    import importlib, mrs
    if os.path.exists(path) and not rebuild:
        bpy.ops.wm.open_mainfile(filepath=path)
        mrs = importlib.reload(mrs)
    if bpy.data.node_groups.get(MRS + "Road") is None or bpy.context.scene.get("mrs_city_base") != BASE_VERSION or rebuild:
        t = time.time(); mrs.build_all(); log("BASE built in %.0fs" % (time.time() - t))
        for g_ in bpy.data.node_groups: g_.use_fake_user = True
        for m_ in bpy.data.materials: m_.use_fake_user = True
        bpy.context.scene["mrs_city_base"] = BASE_VERSION
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True, copy=True)
    return mrs


def B(x, y, z=0.0):
    return Vector((x - HALF, y - HALF, z))


def _col(name, parent):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    if c.name not in [ch.name for ch in parent.children]: parent.children.link(c)
    return c


def clear():
    """Remove everything a previous city build made (stable names: rebuilding does not multiply)."""
    for nm in (COL + "_Placed", COL + "_Anchors", COL):
        c = bpy.data.collections.get(nm)
        if c is None: continue
        for o in list(c.all_objects):
            bpy.data.objects.remove(o)
        for ch in list(c.children_recursive): bpy.data.collections.remove(ch)
        bpy.data.collections.remove(c)
    for o in [o for o in bpy.data.objects if o.name.startswith((MRS + "Driveways_PH_",))]: bpy.data.objects.remove(o)
    for me in [m for m in bpy.data.meshes if m.users == 0]: bpy.data.meshes.remove(me)
    for cu in [c for c in bpy.data.curves if c.users == 0]: bpy.data.curves.remove(cu)


def load_plan(plan_dir):
    city = json.load(open(os.path.join(plan_dir, "city.json"), encoding="utf-8"))
    hp = os.path.join(plan_dir, "graded.npz")
    H = citynet.Heights.load(hp if os.path.exists(hp) else os.path.join(plan_dir, "heights.f32"), city["grid"], city["cell_m"])
    global HALF
    HALF = city["size_m"] / 2.0
    return city, H


def _terrain_probe(H, col, step=8.0):
    """Coarse mesh of the graded ground (pillar feet of the elevated bridge decks find the ground on it)."""
    import numpy as np
    n = int(H.n * H.cell / step)
    xs = [i * step for i in range(n + 1)]
    verts = [(x - HALF, y - HALF, H(x, y)) for y in xs for x in xs]
    faces = [(j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i) for j in range(n) for i in range(n)]
    me = bpy.data.meshes.new("PH_GroundProbe"); me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new("PH_GroundProbe", me); col.objects.link(o)
    o.hide_viewport = True; o.hide_render = True; o["mrs_terrain_source"] = True; o["mrs_debug"] = True
    return o


def _road_object(rd, col, probe=None):
    preset, vals = citynet.profile(rd["cls"], rd.get("bridge", False))
    pts = [tuple(B(x, y, z)) for x, y, z in rd["pts"]]
    o = roads.curve_object(rd["id"], pts, col, kind="POLY")
    roads.add_road_modifier(o, preset, terrain=probe if rd.get("bridge") else None, **{k.replace(" ", "_"): v for k, v in vals.items()})
    # the node group's own manhole covers (~430 triangles each, every 45 m) and gully gratings stay off in the city:
    # the rule placement puts drain grates and access covers on every street as kit instances
    mod = o.modifiers["MRS_Road"]
    for k in ("Manholes", "Drains"): mod_input_set(mod, k, None)
    o["mrs_street_name"] = rd.get("street", "") or rd["id"]
    o["ph_cls"] = rd["cls"]; o["ph_cf_roads"] = json.dumps(rd.get("cf_roads", [rd.get("cf_lane", "")]))
    o["ph_culture"] = rd.get("culture", "")
    return o


def _control(j, objs):
    c = j["control"]; n = len(j["approaches"])
    if n == 2: return "none"
    if c == "signal": return "signals"
    if c == "stop": return "stop"
    if c == "uncontrolled" and n == 3: return "priority"
    return "none"


def _main_roads(j, objs, net_by):
    ranks = [(citynet.RANK[net_by[rid]["cls"]], rid) for rid, _ in j["approaches"]]
    top = max(r for r, _ in ranks)
    main = [rid for r, rid in ranks if r == top]
    if len(main) == len(ranks) and len(ranks) == 3:
        # a T of equal roads: the two most collinear approaches carry the priority
        ds = {}
        for rid, end in j["approaches"]:
            o = objs[rid]; (p0, t0, s0), (p1, t1, s1) = roads.road_ends(o)
            ds[rid] = t0 if end == "start" else t1
        best = min(((a, b) for a in ds for b in ds if a < b), key=lambda ab: ds[ab[0]].dot(ds[ab[1]]))
        main = list(best)
    return main


def build(plan_dir, region=None, seed=7, place=True, log=print):
    """Build the city's MRS streets in the context scene. Returns the network dict (citynet) + stats."""
    t0 = time.time(); tm = {}
    city, H = load_plan(plan_dir)
    net = citynet.build(city, H, region)
    tm["network"] = round(time.time() - t0, 1)
    log("NETWORK", json.dumps(net["report"]["summary"]))
    sc = bpy.context.scene; set_scene(sc)
    for o in [o for o in sc.collection.objects if o.name in ("Cube", "Light", "Camera")]: bpy.data.objects.remove(o)
    clear()
    col = _col(COL, sc.collection)
    probe = _terrain_probe(H, col) if any(r.get("bridge") for r in net["roads"]) else None
    t = time.time()
    objs = {}
    for rd in net["roads"]: objs[rd["id"]] = _road_object(rd, col, probe)
    for ln in net["lanes"]: objs[ln["id"]] = _road_object(ln, col)
    tm["roads"] = round(time.time() - t, 1)
    # back lanes cross the street sidewalks on a dropped kerb with a concrete apron (MRS driveways)
    drives = {}
    for ln in net["lanes"]:
        for e in ln["ends"]:
            if e.get("street") and e["street"] in objs:
                rd = next(r for r in net["roads"] if r["id"] == e["street"])
                pr = citynet._project_poly(rd["pts"], e["along_pos"])
                drives.setdefault(e["street"], []).append((round(pr[1], 3), e["side"], float(ln["width"]) + 1.0))
    from . import frontage
    for rid, lst in drives.items(): frontage.apply_driveways(objs[rid], sorted(lst))
    tm["driveways"] = sum(len(v) for v in drives.values())
    # junctions
    t = time.time(); net_by = {r["id"]: r for r in net["roads"]}; fails = []; built = 0
    for j in net["junctions"]:
        if j["kind"] != "junction": continue
        rs = [objs[rid] for rid, _ in j["approaches"] if rid in objs]
        if len(rs) < 2: continue
        x, y = j["pos"]
        ctrl = _control(j, objs); n = len(rs)
        try:
            junction.build_junction(j["id"], B(x, y, j["z"]), rs, col, crosswalks=n >= 3, stop_lines=n >= 3, corner_radius=j["corner_radius"],
                                    control=ctrl, main_roads=_main_roads(j, objs, net_by) if n >= 3 else None,
                                    crossing="zebra" if ctrl == "signals" else "parallel", snap=1.0, edge_depth=citynet.EDGE_DEPTH,
                                    plane=j.get("plane"), z=j["z"])
            built += 1
        except Exception as e:
            fails.append((j["id"], str(e))); log("JUNCTION FAILED", j["id"], e)
    tm["junctions"] = round(time.time() - t, 1); tm["junctions_built"] = built; tm["junction_failures"] = fails
    log("JUNCTIONS", built, "built,", len(fails), "failed in", tm["junctions"], "s")
    STATE.update(city=city, H=H, net=net, objs=objs, plan_dir=plan_dir, region=region, timings=tm)
    if place:
        anchors(city, net, objs)
        place_assets(seed=seed, log=log)
    tm["total"] = round(time.time() - t0, 1)
    return net


def load_state(plan_dir, region=None):
    """STATE for a saved build (.blend from mrs_streets.py --blend): plan, heights and the (deterministic) network,
    so export() / write_plan() can rerun without rebuilding the streets."""
    city, H = load_plan(plan_dir)
    net = citynet.build(city, H, region)
    objs = {o.name: o for o in roads.all_roads(bpy.data.collections.get(COL))} if bpy.data.collections.get(COL) else {}
    STATE.update(city=city, H=H, net=net, objs=objs, plan_dir=plan_dir, region=region, timings=STATE.get("timings", {}))
    saved = bpy.context.scene.get("ph_placement")
    if saved:
        d = json.loads(saved)
        STATE["placement"] = {k: d[k] for k in ("counts", "by_kind", "skip_summary", "items") if k in d}
        STATE["bus_stops"] = d.get("bus_stops", []); STATE["anchors"] = d.get("anchors"); STATE["timings"] = d.get("timings") or {}
    return net


# ---------------------------------------------------------------------------------------------- anchors
def _door(hs):
    pos = hs["pos"]; yaw = hs["yaw"]
    if hs.get("door"):
        d0, e = hs["door"][0], hs["door"][1] + 0.4
    else:
        d0, e = 0.0, hs["size"][1] * 0.5 + 0.4
    return (pos[0] + d0 * math.cos(yaw) - e * math.sin(yaw), pos[1] + d0 * math.sin(yaw) + e * math.cos(yaw))


def anchors(city, net, objs):
    """Entrance anchors (house doors, shop / tower / public fronts: the sidewalk in front stays free), exclusion
    anchors at the CityForge props that stay (culture furniture), bus-stop list from CityForge's stops."""
    sc = bpy.context.scene
    ac = _col(COL + "_Anchors", bpy.data.collections[COL])
    idx = citynet.RoadIndex(net["roads"])
    region = STATE.get("region")
    inside = (lambda p: True) if region is None else (lambda p: region[0] - 30 <= p[0] <= region[2] + 30 and region[1] - 30 <= p[1] <= region[3] + 30)
    n_ent = 0
    def entrance(name, p, kind):
        nonlocal n_ent
        if not inside(p): return
        nr = citynet.nearest_road(net["roads"], p, 45.0, idx)
        if nr is None or nr[0]["id"] not in objs: return
        rd, along, side, dist = nr
        if dist > rd["width"] / 2.0 + citynet.WALK + 30.0: return
        e = bpy.data.objects.new("MRS_Entrance_" + name, None); ac.objects.link(e)
        e.location = B(p[0], p[1], 0.0); e["mrs_road"] = rd["id"]; e["mrs_side"] = side; e["mrs_on_sidewalk"] = True; e["ph_kind"] = kind
        e.empty_display_size = 0.6; n_ent += 1
    for hs in city["houses"]: entrance(hs["id"], _door(hs), "house")
    for kind in ("shops", "towers", "public", "warehouses"):
        for b in city.get(kind, []):
            p = b["pos"]
            nr = citynet.nearest_road(net["roads"], p, 80.0, idx)
            if nr is None: continue
            rd, along, side, dist = nr
            # the front: the point on the lot line straight towards the street
            pr = citynet._project_poly(rd["pts"], p); q = pr[3]
            v = citynet._unit((p[0] - q[0], p[1] - q[1])); off = rd["width"] / 2.0 + citynet.WALK + 0.3
            entrance(b["id"], (q[0] + v[0] * off, q[1] + v[1] * off), kind[:-1])
    n_ex = 0
    for kind, size in CF_KEPT.items():
        for k, pr in enumerate(city["props"].get(kind, [])):
            if not inside(pr): continue
            e = bpy.data.objects.new("MRS_Exclude_%s_%d" % (kind, k), None); ac.objects.link(e)
            e.location = B(pr[0], pr[1], pr[2]); e.empty_display_size = size; n_ex += 1
    stops = []
    for k, bs in enumerate(city["props"].get("bus_stop", [])):
        if not inside(bs): continue
        nr = citynet.nearest_road(net["roads"], (bs[0], bs[1]), 30.0, idx)
        if nr is None or nr[0]["id"] not in objs: continue
        rd, along, side, dist = nr
        stops.append({"id": "BS%03d" % k, "road": rd["id"], "along": None, "pos": B(bs[0], bs[1], 0.0), "side": side, "name": bs[4] if len(bs) > 4 else ""})
    STATE["bus_stops"] = stops
    STATE["anchors"] = {"entrances": n_ent, "exclusions": n_ex, "bus_stops": len(stops)}
    return STATE["anchors"]


def place_assets(seed=7, log=print):
    """MRS rule-based placement over every city street: signs by junction control, bus stops at CityForge's stop
    positions, streetlights by road class, hydrants / drains / cabinets, benches / bins / racks, street trees by
    street style. Real light sources are left to the game (thousands of lamps: the heads glow at night)."""
    t = time.time()
    col = bpy.data.collections[COL]
    objs = STATE["objs"]; net = STATE["net"]
    speeds = {}; styles = {}
    for rd in net["roads"] + net["lanes"]:
        speeds[rd["id"]] = citynet.SPEED.get(rd["cls"], 30); styles[rd["id"]] = citynet.STYLE.get(rd["cls"], "residential")
    # city density: the street block's avenue rules furnish every 36 m; residential streets get fewer benches,
    # bins and racks, and utility cabinets only where a signal controller needs one
    placement.RULES.update({"light_sources": False, "road_styles": styles, "landscape": {}, "default_landscape": "none",
                            "bench_spacing": 72.0, "bin_spacing": 110.0, "rack_spacing": 150.0, "cabinet_controls": ["signals"]})
    landscape = placement._landscape
    placement._landscape = lambda ctx, m: None          # grass / shrub scatter of the planting strips: not drawn by the game
    try:
        rep = placement.place_all(col, seed=seed, style="residential", speed_limits=speeds, bus_stops=STATE.get("bus_stops", []))
    finally:
        placement._landscape = landscape
    STATE["placement"] = rep
    STATE["timings"]["placement"] = round(time.time() - t, 1)
    # kept in the .blend so an export rerun from it (mrs_streets.py --from-blend) still has the report and footprints
    bpy.context.scene["ph_placement"] = json.dumps({"counts": rep["counts"], "by_kind": rep["by_kind"], "skip_summary": rep.get("skip_summary", {}),
                                                    "items": rep["items"], "bus_stops": [dict(b, pos=list(b["pos"])) for b in STATE.get("bus_stops", [])],
                                                    "anchors": STATE.get("anchors"), "timings": STATE["timings"]}, default=str)
    log("PLACEMENT", rep["counts"], json.dumps(rep["by_kind"]), "in", STATE["timings"]["placement"], "s")
    return rep


# ---------------------------------------------------------------------------------------------- export
CHUNK = 256.0
KIT_SIGNAL = "MRS_PH_Signal"
KIT_STREETNAME = "MRS_PH_StreetName"
KIT_PREFIX = "KIT__"         # kit node names: KIT__<library object>; the game strips it to match the instance records
BATCH = 40                   # roads evaluated per depsgraph pass (memory)


def _chunk_key(x, y):
    n = int((2 * HALF) // CHUNK)
    return (min(max(int((x + HALF) // CHUNK), 0), n - 1), min(max(int((y + HALF) // CHUNK), 0), n - 1))


def _tmp_col():
    sc = bpy.context.scene
    c = bpy.data.collections.get("PH_ExportTmp") or bpy.data.collections.new("PH_ExportTmp")
    if c.name not in [ch.name for ch in sc.collection.children]: sc.collection.children.link(c)
    return c


def _clear_tmp(tmp):
    objs = list(tmp.objects); data = [o.data for o in objs if isinstance(o.data, bpy.types.Mesh)]
    if objs: bpy.data.batch_remove(objs)
    TRASH.extend(data)


def _drop_faces(me, keep):
    """Keep only the polygons whose index is in `keep` (a set)."""
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    bm.to_mesh(me); bm.free()


TRASH = []                   # meshes removed together at the end of the export (bpy.data.batch_remove)


def _split(me, out, overlap=0.0):
    """World-space mesh -> its polygons grouped by the chunk under their centre (out[key] = [meshes]). With
    `overlap` a polygon also goes to every chunk within that distance (collision: the chunks' trimeshes overlap at
    their seams, so a ray exactly on a shared edge cannot slip between two separate shapes)."""
    if not len(me.polygons):
        TRASH.append(me); return
    import array
    cs = array.array("f", [0.0]) * (3 * len(me.polygons)); me.polygons.foreach_get("center", cs)
    keys = {}
    offs = [(0.0, 0.0)] + ([(overlap, 0.0), (-overlap, 0.0), (0.0, overlap), (0.0, -overlap)] if overlap > 0 else [])
    for i in range(len(me.polygons)):
        for ox, oy in offs:
            keys.setdefault(_chunk_key(cs[3 * i] + ox, cs[3 * i + 1] + oy), set()).add(i)
    if len(keys) == 1:
        out.setdefault(next(iter(keys)), []).append(me); return
    for k, idx in keys.items():
        c = me.copy(); _drop_faces(c, idx); out.setdefault(k, []).append(c)
    TRASH.append(me)


def merge_along(me, angle=0.35):
    """Fewer triangles without touching the cross-section: the edges between consecutive stations (both ends at
    the same `along`) are dissolved where the faces either side are coplanar within `angle` degrees and share a
    material, so a straight stretch of kerb / asphalt / sidewalk becomes one long face per lateral strip (the
    road shader's lateral masks keep their vertices; crossing ramps, driveway dips and grade changes stay)."""
    import bmesh
    if "along" not in me.attributes or not len(me.polygons): return 0
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    al = bm.verts.layers.float.get("along")
    if al is None:
        bm.free(); return 0
    lim = math.cos(math.radians(angle)); n0 = len(bm.faces)

    def along_nb(v, f):
        """The vertex next to v in face f along the strip (not on v's station)."""
        for e2 in v.link_edges:
            if f in e2.link_faces:
                o = e2.other_vert(v)
                if abs(o[al] - v[al]) > 1e-3: return o
        return None

    def straight(v, f1, f2):
        a_, b_ = along_nb(v, f1), along_nb(v, f2)
        if a_ is None or b_ is None: return False
        d1 = (v.co - a_.co); d2 = (b_.co - v.co)
        if d1.length < 1e-6 or d2.length < 1e-6: return False
        return d1.normalized().dot(d2.normalized()) > lim
    edges = []
    for e in bm.edges:
        if len(e.link_faces) != 2: continue
        a, b = e.verts
        if abs(a[al] - b[al]) > 1e-3: continue
        f1, f2 = e.link_faces
        if f1.material_index != f2.material_index or f1.normal.dot(f2.normal) < lim: continue
        # only where both long edges run straight through: a bend stays faceted (merged faces stay convex)
        if not (straight(a, f1, f2) and straight(b, f1, f2)): continue
        edges.append(e)
    if edges: bmesh.ops.dissolve_edges(bm, edges=edges, use_verts=True, use_face_split=False)
    n1 = len(bm.faces)
    bm.to_mesh(me); bm.free()
    return n0 - n1


def _smooth(me, angle=30.0):
    """Smooth shading with sharp edges over `angle`: vertices are shared across flat surfaces in the GLB."""
    try:
        me.shade_smooth(); me.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        pass


def merge_meshes(meshes, name):
    """One mesh from many (numpy, no operators): positions, faces, materials (unified by name), UVMap / UV2
    per corner and the Col point colours. Replaces bpy.ops.object.join, which re-evaluated the whole scene."""
    import numpy as np
    mats, mat_index = [], {}
    vs, loops, starts, mids, uv1, uv2, col = [], [], [], [], [], [], []
    vo = lo = 0
    for me in meshes:
        nv, nl, npo = len(me.vertices), len(me.loops), len(me.polygons)
        if not npo: continue
        co = np.empty(nv * 3, np.float32); me.vertices.foreach_get("co", co); vs.append(co)
        vi = np.empty(nl, np.int32); me.loops.foreach_get("vertex_index", vi); loops.append(vi + vo)
        ls = np.empty(npo, np.int32); me.polygons.foreach_get("loop_start", ls); starts.append(ls + lo)
        mi = np.empty(npo, np.int32); me.polygons.foreach_get("material_index", mi)
        remap = np.zeros(max(1, len(me.materials)), np.int32)
        for k, m in enumerate(me.materials):
            key = m.name if m is not None else ""
            if key not in mat_index: mat_index[key] = len(mats); mats.append(m)
            remap[k] = mat_index[key]
        mids.append(remap[np.clip(mi, 0, len(remap) - 1)])
        for lay, dst in (("UVMap", uv1), ("UV2", uv2)):
            u = np.zeros(nl * 2, np.float32)
            L = me.uv_layers.get(lay) or (me.uv_layers[0] if lay == "UVMap" and len(me.uv_layers) else None)
            if L is not None: L.data.foreach_get("uv", u)
            dst.append(u)
        c = np.ones(nv * 4, np.float32)
        ca = me.color_attributes.get("Col")
        if ca is not None and ca.domain == "POINT": ca.data.foreach_get("color", c)
        col.append(c)
        vo += nv; lo += nl
    out = bpy.data.meshes.new(name)
    if not vs: return out
    V = np.concatenate(vs); Lp = np.concatenate(loops); S = np.concatenate(starts)
    out.vertices.add(len(V) // 3); out.vertices.foreach_set("co", V)
    out.loops.add(len(Lp)); out.loops.foreach_set("vertex_index", Lp)
    out.polygons.add(len(S)); out.polygons.foreach_set("loop_start", S)
    out.update(calc_edges=True)
    out.polygons.foreach_set("material_index", np.concatenate(mids))
    for lay, src in (("UVMap", uv1), ("UV2", uv2)):
        out.uv_layers.new(name=lay).data.foreach_set("uv", np.concatenate(src))
    ca = out.color_attributes.new("Col", "BYTE_COLOR", "POINT"); ca.data.foreach_set("color", np.concatenate(col))
    out.color_attributes.active_color = ca
    try: out.color_attributes.render_color_index = out.color_attributes.find("Col")
    except Exception: pass
    for m in mats: out.materials.append(m)
    out.validate(); out.update()
    return out


def merge_positions(meshes, name):
    """Positions and faces only (collision)."""
    import numpy as np
    vs, loops, starts = [], [], []; vo = lo = 0
    for me in meshes:
        if not len(me.polygons): continue
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); vs.append(co)
        vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", vi); loops.append(vi + vo)
        ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_start", ls); starts.append(ls + lo)
        vo += len(me.vertices); lo += len(me.loops)
    out = bpy.data.meshes.new(name)
    if not vs: return out
    V = np.concatenate(vs); Lp = np.concatenate(loops); S = np.concatenate(starts)
    out.vertices.add(len(V) // 3); out.vertices.foreach_set("co", V)
    out.loops.add(len(Lp)); out.loops.foreach_set("vertex_index", Lp)
    out.polygons.add(len(S)); out.polygons.foreach_set("loop_start", S)
    out.update(calc_edges=True); out.validate()
    return out


def _engine_mesh(me):
    from . import export as ex
    for i, m in enumerate(me.materials):
        em = ex.engine_material(m)
        if em is not m: me.materials[i] = em


def _collision_mesh(me):
    if "kind" in me.attributes:
        kind = me.attributes["kind"].data
        _drop_faces(me, {i for i in range(len(me.polygons)) if round(kind[i].value) not in (1, 5)})
    me.materials.clear()
    return me


def _layer(name, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.collection.name == name: return lc
    for ch in lc.children:
        r = _layer(name, ch)
        if r: return r
    return None


def _road_meshes(rds, collision, log=print):
    """World-space evaluated meshes of the roads at Final quality: visual (instances realized, masks, engine
    materials) or collision (drivable / walkable surfaces only). Inputs are set for a whole batch and evaluated
    in ONE depsgraph pass (one pass per road re-evaluated the whole 20 000-object scene each time)."""
    from . import export as ex
    from .nodes import mod_input_get
    out = {}
    for b0 in range(0, len(rds), BATCH):
        batch = rds[b0:b0 + BATCH]; saved = []
        for o in batch:
            mod = o.modifiers["MRS_Road"]
            try: vq = mod_input_get(mod, "Viewport Quality")
            except Exception: vq = None
            saved.append((o, vq))
            mod_input_set(mod, "Realize Instances", not collision); mod_input_set(mod, "Collision Only", collision)
            if vq is not None: mod_input_set(mod, "Viewport Quality", "Final")
            o.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        for o in batch:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            me.transform(o.matrix_world)
            if collision: _collision_mesh(me)
            else:
                ex.road_masks(o, me); _engine_mesh(me)
            STATE.setdefault("merged_faces", [0])[0] += merge_along(me)
            out[o.name] = me
        for o, vq in saved:
            mod = o.modifiers["MRS_Road"]
            mod_input_set(mod, "Realize Instances", False); mod_input_set(mod, "Collision Only", False)
            if vq is not None: mod_input_set(mod, "Viewport Quality", vq)
            o.update_tag()
        log("  roads %s %d / %d" % ("collision" if collision else "visual", min(b0 + BATCH, len(rds)), len(rds)))
    return out


def _static_meshes(col, placed):
    """Junctions, dead ends and the unique meshes of the placement (pads, paths, mulch, lane text) as world-space
    (visual, collision-or-None) pairs; library instances, signals and street-name signs go to the records."""
    from . import export as ex
    out = []
    srcs = [o for o in col.objects if o.type == "MESH" and o.get("mrs_junction")]
    if placed:
        for o in placed.objects:
            if o.parent is not None or o.type != "MESH" or o.get("mrs_debug"): continue
            lib = o.get("mrs_placed", "")
            if lib and bpy.data.objects.get(lib) is not None: continue
            if o.get("mrs_kind") in ("sign_street_name", "tree", "landscape"): continue
            srcs.append(o)
    for o in srcs:
        v = o.data.copy(); v.transform(o.matrix_world)
        ex.road_masks(None, v); _engine_mesh(v)
        c = None
        if o.get("mrs_kind") != "mulch":
            c = o.data.copy(); c.transform(o.matrix_world); _collision_mesh(c)
        out.append((o, v, c))
    return out


def _join(objs, name):
    if len(objs) == 1:
        objs[0].name = name; objs[0].data.name = name; return objs[0]
    with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    o = objs[0]; o.name = name; o.data.name = name
    return o


def _proxy(m):
    """Texture-less stand-in carrying the engine material's name (the game maps it back to the real material,
    loaded once from mrs_materials.glb, so 64 chunk files do not each embed the tiles)."""
    if m is None: return None
    pn = "PHX_" + m.name
    p = bpy.data.materials.get(pn)
    if p is None:
        p = bpy.data.materials.new(pn); p.use_nodes = True
        b = next(n for n in p.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = tuple(m.diffuse_color)
    return p


def _gltf(sel, path, **kw):
    for o in bpy.context.view_layer.objects: o.select_set(o in sel)
    bpy.context.view_layer.objects.active = sel[0]
    sc = bpy.context.scene
    stash = {k: sc[k] for k in list(sc.keys()) if k.startswith("mrs_")}
    for k in stash: del sc[k]
    try:
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, use_active_scene=True, **kw)
    finally:
        for k, v in stash.items(): sc[k] = v


def _local_copy(src, tmp, name):
    """One mesh object at the origin holding `src` and its children (in src's local space), engine materials."""
    parts = []
    inv = src.matrix_world.inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in [src] + list(src.children_recursive):
        if ob.type not in ("MESH", "CURVE", "FONT"): continue
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg) if ob.type != "MESH" else ob.data.copy()
        me.transform(inv @ ob.matrix_world)
        _engine_mesh(me)
        c = bpy.data.objects.new(name + "_part%d" % len(parts), me); tmp.objects.link(c); parts.append(c)
    if not parts: return None
    return _join(parts, name)


def _is_text(ob):
    return ob.type == "FONT" or bool(ob.get("mrs_text"))


def export(out_dir, log=print):
    """Game export of the city streets into `out_dir`:
      mrs/chunks/c_<i>_<j>.glb   MrsRoads_<i>_<j> (visual, proxy materials) + MrsCol_<i>_<j> (collision surfaces)
      mrs/mrs_materials.glb      one quad per road material (the real baked tiles), names = the proxies' minus PHX_
      mrs/mrs_kit.glb            one mesh per placed library model (+ the signal and the blank street-name sign)
      mrs/mrs_city.json          instances, signals + phases, street-name labels, trees, items (footprints), report
      plan/city.json             the plan with CityForge's replaced street props and street trees removed, streets = mrs
      plan/graded.npz, heights.f32  the graded ground fitted just under the MRS surfaces
    Coordinates in the JSON are Blender world (x, y, z) = (plan x - 1024, plan y - 1024, h); Godot (x, z, -y)."""
    t0 = time.time(); stats = {}
    col = bpy.data.collections[COL]; placed = bpy.data.collections.get(COL + "_Placed")
    md = os.path.join(out_dir, "mrs"); cd = os.path.join(md, "chunks"); os.makedirs(cd, exist_ok=True)
    for f in os.listdir(cd):
        if f.endswith(".glb"): os.remove(os.path.join(cd, f))
    tmp = _tmp_col(); _clear_tmp(tmp)
    # the placed instances and anchors stay out of the depsgraph while the roads evaluate
    hidden = []
    for nm in (COL + "_Placed", COL + "_Anchors"):
        lc = _layer(nm)
        if lc is not None and not lc.exclude: lc.exclude = True; hidden.append(lc)
    try:
        rds = [o for o in col.objects if o.type == "CURVE" and "MRS_Road" in o.modifiers and not o.get("mrs_debug")]
        vis_r = _road_meshes(rds, False, log); col_r = _road_meshes(rds, True, log)
    finally:
        for lc in hidden: lc.exclude = False
    statics = _static_meshes(col, placed)
    stats["roads"] = len(rds); stats["statics"] = len(statics); stats["evaluate_s"] = round(time.time() - t0, 1)
    log("EXPORT evaluated", len(rds), "roads,", len(statics), "static meshes in", stats["evaluate_s"], "s")
    # the ground under the MRS surfaces (elevated decks excluded) before the meshes are split and joined away
    ground = [m for n, m in col_r.items() if dict(bpy.data.objects[n].get("mrs_inputs") or {}).get("Mode") != "Elevated"]
    ground += [c for o, v, c in statics if c is not None and o.get("mrs_junction")]
    stats["plan"] = write_plan(os.path.join(out_dir, "plan"), ground, log=log)
    used_mats = {}
    vis, colm = {}, {}
    for me in list(vis_r.values()) + [v for o, v, c in statics]:
        for m in me.materials:
            if m is not None: used_mats[m.name] = m
        for k, m in enumerate(me.materials): me.materials[k] = _proxy(m)
        _split(me, vis)
    for me in list(col_r.values()) + [c for o, v, c in statics if c is not None]: _split(me, colm, overlap=1.0)
    tris = 0; ctris = 0; files = []
    for k in sorted(set(vis) | set(colm)):
        if vis.get(k):
            me = merge_meshes(vis[k], "MrsRoads_%d_%d" % k); _smooth(me)
            o = bpy.data.objects.new(me.name, me); tmp.objects.link(o)
            tris += sum(len(p.vertices) - 2 for p in me.polygons)
            fp = os.path.join(cd, "c_%d_%d.glb" % k)
            _gltf([o], fp, export_materials="EXPORT", export_normals=True, export_texcoords=True, export_vertex_color="ACTIVE")
            files.append(fp)
        if colm.get(k):
            me = merge_positions(colm[k], "MrsCol_%d_%d" % k)
            o = bpy.data.objects.new(me.name, me); tmp.objects.link(o)
            ctris += sum(len(p.vertices) - 2 for p in me.polygons)
            fp = os.path.join(cd, "c_%d_%d_col.glb" % k)
            _gltf([o], fp, export_materials="NONE", export_normals=False, export_texcoords=False)
            files.append(fp)
        TRASH.extend((vis.get(k) or []) + (colm.get(k) or []))
        _clear_tmp(tmp)
    stats.update(chunks=len([f for f in files if not f.endswith("_col.glb")]), tris=tris, collision_tris=ctris, merged_faces=STATE.get("merged_faces", [0])[0],
                 chunk_mb=round(sum(os.path.getsize(f) for f in files) / 1e6, 1))
    log("EXPORT chunks", json.dumps({k: stats[k] for k in ("chunks", "tris", "collision_tris", "chunk_mb")}), "%.0fs" % (time.time() - t0))
    # ------------------------------------------------------------------ the road materials once
    quads = []
    for name, m in sorted(used_mats.items()):
        me = bpy.data.meshes.new("PHM_" + name); me.from_pydata([(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap")
        for lp in me.loops: uv.data[lp.index].uv = tuple(me.vertices[lp.vertex_index].co[:2])
        me.materials.append(m); q = bpy.data.objects.new(name, me); tmp.objects.link(q); quads.append(q)
    if quads:
        _gltf(quads, os.path.join(md, "mrs_materials.glb"), export_materials="EXPORT", export_texcoords=True, export_image_format="JPEG", export_jpeg_quality=92)
        stats["materials"] = len(quads); stats["materials_mb"] = round(os.path.getsize(os.path.join(md, "mrs_materials.glb")) / 1e6, 1)
    _clear_tmp(tmp)
    # ------------------------------------------------------------------ instances, signals, labels, trees, items
    rec = {"godot_axes": "Blender (x, y, z) -> Godot (x, z, -y); yaw_godot = yaw_blender", "instances": {}, "signals": [], "junctions": [], "labels": [],
           "street_name_signs": [], "trees": [], "items": [], "bus_stops": [], "lights": []}
    libs = set()
    if placed:
        for o in placed.objects:
            if o.parent is not None: continue
            kind = o.get("mrs_kind", ""); lib = o.get("mrs_placed", "")
            M = o.matrix_world
            loc = [round(c, 3) for c in M.translation]; yaw = round(M.to_euler().z, 4); scl = round(M.to_scale().x, 3)
            if kind == "tree" and o.get("mrs_species"):
                rec["trees"].append({"species": o["mrs_species"], "pos": loc, "yaw": yaw, "scale": scl, "road": o.get("mrs_road", "")}); continue
            if kind == "sign_street_name":
                rec["street_name_signs"].append(loc + [yaw])
                for ch in o.children_recursive:
                    if not _is_text(ch): continue
                    txt = ch.data.body if ch.type == "FONT" else ch.get("mrs_text", "")
                    m = ch.matrix_world
                    rec["labels"].append({"text": txt, "pos": [round(c, 3) for c in m.translation], "yaw": round(m.to_euler().z, 4),
                                          "size": round(m.to_scale().x * (ch.data.size if ch.type == "FONT" else 0.11), 3)})
                continue
            if lib and bpy.data.objects.get(lib) is not None:
                libs.add(lib)
                rec["instances"].setdefault(lib, []).append(loc + [yaw, scl])
                if kind == "light": rec["lights"].append(loc + [yaw])
    for o in col.objects:
        meta = o.get("mrs_junction")
        if not meta or o.type != "MESH": continue
        meta = meta.to_dict() if hasattr(meta, "to_dict") else dict(meta)
        sigs = meta.get("signals") or []
        if not sigs: continue
        rec["junctions"].append({"id": o.name, "phases": len(meta.get("signal_phases") or []), "at": [round(c, 2) for c in meta["at"]]})
        for s in sigs:
            so = bpy.data.objects.get(s["id"])
            if so is None: continue
            rec["signals"].append({"id": s["id"], "junction": o.name, "phase": s["phase"], "approach": s["approach"],
                                   "pos": [round(c, 3) for c in so.matrix_world.translation], "yaw": round(so.matrix_world.to_euler().z, 4)})
    for st in STATE.get("bus_stops", []):
        rec["bus_stops"].append({"id": st["id"], "road": st["road"], "side": st["side"], "name": st.get("name", "")})
    rep = STATE.get("placement") or {}
    rec["items"] = [{k: it.get(k) for k in ("name", "kind", "lib", "pos", "foot")} for it in rep.get("items", []) if not it.get("flush")]
    if not rec["items"] and placed: rec["items"] = _items_from_objects(placed)
    # kit: one mesh per library model used, plus the signal and the blank street-name sign
    kit = []
    for lib in sorted(libs):
        k_ = _local_copy(bpy.data.objects[lib], tmp, KIT_PREFIX + lib)      # (the library object holds the plain name)
        if k_ is not None: kit.append(k_)
    sig0 = next((bpy.data.objects.get(s["id"]) for s in rec["signals"] if bpy.data.objects.get(s["id"])), None)
    if sig0 is not None:
        k_ = _local_copy(sig0, tmp, KIT_SIGNAL)
        if k_ is not None: kit.append(k_)
    try:
        from . import signage
        sn = signage.make_sign("PH_StreetNameBlank", "street_name", text="XXXXXXXXXXXX|XXXXXXXXXXXX", double=True, collection=tmp)
        for ch in list(sn.children_recursive):
            if _is_text(ch): bpy.data.objects.remove(ch)
        k_ = _local_copy(sn, tmp, KIT_STREETNAME)
        if k_ is not None: kit.append(k_)
    except Exception as e:
        log("street-name kit sign skipped:", e)
    names = {x.name for x in tmp.objects}
    kit = [k_ for k_ in kit if k_.name in names]
    for k_ in kit: k_.location = (0, 0, 0)
    if kit:
        _gltf(kit, os.path.join(md, "mrs_kit.glb"), export_materials="EXPORT", export_normals=True, export_texcoords=True)
        stats["kit"] = len(kit); stats["kit_mb"] = round(os.path.getsize(os.path.join(md, "mrs_kit.glb")) / 1e6, 1)
        stats["kit_tris"] = {k_.name: sum(len(p.vertices) - 2 for p in k_.data.polygons) for k_ in kit}
    _clear_tmp(tmp)
    rec["roads"] = road_records(STATE["net"])
    rec["counts"] = {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in rec.items() if k != "godot_axes"}
    rec["instance_counts"] = {k: len(v) for k, v in rec["instances"].items()}
    STATE.pop("merged_faces", None)
    gone = [m for m in dict.fromkeys(TRASH) if m.users == 0]
    if gone: bpy.data.batch_remove(gone)
    TRASH.clear()
    rec["report"] = {"network": STATE["net"]["report"]["summary"], "placement": {k: v for k, v in rep.items() if k in ("counts", "by_kind", "skip_summary")},
                     "timings": STATE.get("timings"), "anchors": STATE.get("anchors"), "export": {k: v for k, v in stats.items() if k != "kit_tris"}}
    json.dump(rec, open(os.path.join(md, "mrs_city.json"), "w", encoding="utf-8"), separators=(",", ":"), default=str)
    stats["records"] = rec["counts"]
    stats["export_s"] = round(time.time() - t0, 1)
    return stats


def _items_from_objects(placed):
    """Item records (kind, lib, base position, footprint corners) of the placed instances, from the objects and the
    library footprints, as placement.item_rects makes them (front = local -Y turned by the yaw)."""
    out = []
    for o in placed.objects:
        if o.parent is not None: continue
        kind = o.get("mrs_kind", ""); lib = o.get("mrs_placed", ""); src = bpy.data.objects.get(lib) if lib else None
        if src is None or kind in ("tree", "drain", "access_cover", "pad", "mulch"): continue
        key = next((k for k, names in placement.LIB.items() if lib in names), kind.split("_")[0])
        w, d, acc = placement.footprint(key, src)
        yaw = o.matrix_world.to_euler().z
        f = Vector((math.cos(yaw + math.pi / 2), math.sin(yaw + math.pi / 2), 0.0))
        foot, _ = placement.item_rects(o.matrix_world.translation, f, w, d, acc)
        out.append({"name": o.name, "kind": kind, "lib": lib, "pos": [round(c, 3) for c in o.matrix_world.translation],
                    "foot": [[round(c.x, 3), round(c.y, 3)] for c in foot.corners()]})
    return out


def _street_tree(net, idx, p):
    nr = citynet.nearest_road(net["roads"] + net["lanes"], p, 40.0, idx)
    return nr is not None and nr[3] <= nr[0]["width"] / 2.0 + citynet.WALK + 0.4


def _seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
    f = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - dx * f, p[1] - a[1] - dy * f)


def intruded(city, net, kind, tol=0.5):
    """Buildings of `kind` (houses / shops) whose footprint reaches more than `tol` m into an MRS street's right of
    way (carriageway + kerb + sidewalk; a lane's surface). CityForge drew some lots and shop rows across the diagonal
    arterials and boulevards (its ribbons simply overlapped them)."""
    idx = citynet.RoadIndex(net["roads"] + net["lanes"]); out = []
    for b in city[kind]:
        x, y = b["pos"]; w, d = b["size"][0], b["size"][1]; c, s_ = math.cos(b["yaw"]), math.sin(b["yaw"])
        pts = [(x + u * w * c - v * d * s_, y + u * w * s_ + v * d * c) for u in (-0.5, 0.0, 0.5) for v in (-0.5, 0.0, 0.5)]
        for rd in idx.near((x, y)):
            lim = rd["width"] / 2.0 + (citynet.WALK if rd["cls"] != "lane" else 0.0)
            dmin = min(_seg_d(p, a, q) for p in pts for a, q in zip(rd["pts"], rd["pts"][1:]))
            if dmin < lim - tol:
                out.append({"id": b["id"], "lot": b.get("lot"), "address": b.get("address", ""), "road": rd["id"], "depth": round(lim - dmin, 2)}); break
    return out


SINK = 0.30                  # the fitted ground under a street surface (m below it; the edge skirt is 1.2 m)
NEAR_MARGIN = 0.15           # next to a street: under its extended plane by this much more (the height-map collider
                             # and the terrain mesh split each 4 m cell into triangles, not bilinearly)


def _building_mask(city, shape, cell, pad=-1.5):
    """Grid points inside a house or garage (at least -`pad` m in): the ground fit next to a street does not move the
    ground those stand on (their heights are fixed in the plan); a point near the wall may follow a sidewalk down."""
    import numpy as np
    m = np.zeros(shape, bool); n = shape[0]
    def rect(pos, w, d, yaw):
        c, s_ = abs(math.cos(yaw)), abs(math.sin(yaw))
        hx = (w * c + d * s_) / 2 + pad; hy = (w * s_ + d * c) / 2 + pad
        if hx <= 0 or hy <= 0: return
        i0 = max(0, int(math.ceil((pos[0] - hx) / cell))); i1 = min(n - 1, int(math.floor((pos[0] + hx) / cell)))
        j0 = max(0, int(math.ceil((pos[1] - hy) / cell))); j1 = min(n - 1, int(math.floor((pos[1] + hy) / cell)))
        if i1 >= i0 and j1 >= j0: m[j0:j1 + 1, i0:i1 + 1] = True
    # houses and garages only: shops, towers, warehouses and public buildings stand at their lot line on a 0.8 m
    # foundation (build_city.py), so the ground under their street edge may follow the sidewalk down
    for b in city.get("houses", []): rect(b["pos"], b["size"][0], b["size"][1], b["yaw"])
    for b in city.get("garages", []): rect(b["pos"], 6.4, 6.4, b["yaw"])
    return m


def road_records(net, step=10.0):
    """MRS street centre lines for the game (Blender world, a point every ~`step` m): id, class, width, street name,
    the CityForge roads it replaces, points [x, y, z]."""
    out = []
    for rd in net["roads"] + net["lanes"]:
        pts = rd["pts"]; keep = [pts[0]]; acc = 0.0
        for a, b in zip(pts, pts[1:]):
            acc += math.hypot(b[0] - a[0], b[1] - a[1])
            if acc >= step: keep.append(b); acc = 0.0
        if keep[-1] is not pts[-1]: keep.append(pts[-1])
        out.append({"id": rd["id"], "cls": rd["cls"], "width": rd["width"], "bridge": bool(rd.get("bridge")), "street": rd.get("street", ""), "cf": rd.get("cf_roads", [rd.get("cf_lane", "")]),
                    "pts": [[round(x - HALF, 2), round(y - HALF, 2), round(z, 2)] for x, y, z in keep]})
    return out


def plan_only(out_dir, log=print):
    """Only the plan step of export() (graded ground + city.json) from the current build (e.g. a saved .blend)."""
    col = bpy.data.collections[COL]; placed = bpy.data.collections.get(COL + "_Placed")
    rds = [o for o in col.objects if o.type == "CURVE" and "MRS_Road" in o.modifiers and not o.get("mrs_debug")]
    hidden = []
    for nm in (COL + "_Placed", COL + "_Anchors"):
        lc = _layer(nm)
        if lc is not None and not lc.exclude: lc.exclude = True; hidden.append(lc)
    try:
        col_r = _road_meshes(rds, True, log)
    finally:
        for lc in hidden: lc.exclude = False
    ground = [m for n, m in col_r.items() if dict(bpy.data.objects[n].get("mrs_inputs") or {}).get("Mode") != "Elevated"]
    ground += [c for o, v, c in _static_meshes(col, None) if c is not None and o.get("mrs_junction")]
    out = write_plan(os.path.join(out_dir, "plan"), ground, log=log)
    rp = os.path.join(out_dir, "mrs", "mrs_city.json")
    if os.path.exists(rp):                      # keep the records' street centre lines in step with the network
        rec = json.load(open(rp, encoding="utf-8")); rec["roads"] = road_records(STATE["net"])
        json.dump(rec, open(rp, "w", encoding="utf-8"), separators=(",", ":"), default=str)
    return out


def _plane_cap(np, pts):
    """Height at (0, 0) of the plane through one street's grid targets round a point [(di, dj, t)]: the street surface
    extended to the point; the lowest target when the points are too few or do not lie on a plane."""
    if len(pts) >= 3 and len({(a, b) for a, b, _ in pts}) >= 3:
        A = np.array([[1.0, a, b] for a, b, _ in pts]); z_ = np.array([t for _, _, t in pts])
        c_, res, rank, sv = np.linalg.lstsq(A, z_, rcond=None)
        if rank == 3 and np.max(np.abs(A @ c_ - z_)) <= 0.25: return float(c_[0])
    return float(min(t for _, _, t in pts))


def write_plan(plan_out, ground_meshes, log=print):
    """city.json for CityForge's build with its own street ribbons and street furniture taken out (the MRS export
    replaces them) and graded heights fitted under the MRS surfaces (0.15 m below their top, raised or lowered:
    a flat junction on a slope neither floats nor has the ground showing through). `ground_meshes`: world-space
    collision meshes of every MRS surface on the ground."""
    import numpy as np, shutil
    from mathutils.bvhtree import BVHTree
    os.makedirs(plan_out, exist_ok=True)
    city = json.loads(json.dumps(STATE["city"])); net = STATE["net"]; plan_dir = STATE["plan_dir"]
    city["streets"] = "mrs"
    idx = citynet.RoadIndex(net["roads"] + net["lanes"])
    trees = city["props"].get("tree", [])
    keep = [t for t in trees if not _street_tree(net, idx, (t[0], t[1]))]
    out = {"street_trees_removed": len(trees) - len(keep)}
    city["props"]["tree"] = keep
    city["mrs_replaced"] = {k: len(city["props"].get(k, [])) for k in CF_REPLACED}
    # the street layout wins: a house a street runs through goes, with its lot, fence and garage
    gone = intruded(city, net, "houses")
    lots = {g["lot"] for g in gone}; hids = {g["id"] for g in gone}
    city["houses"] = [h for h in city["houses"] if h["id"] not in hids]
    city["lots"] = [l for l in city["lots"] if l["id"] not in lots]
    city["fences"] = [f for f in city["fences"] if f.get("lot") not in lots]
    city["garages"] = [g for g in city["garages"] if g.get("lot") not in lots]
    shops = intruded(city, net, "shops"); sids = {g["id"] for g in shops}
    city["shops"] = [b for b in city["shops"] if b["id"] not in sids]
    # the road graph (routes, minimap, the HUD's street names) loses the CityForge roads the MRS network dropped:
    # duplicates between two junctions and near-parallel approaches (roads merged into a junction stay: they are
    # inside its surface)
    rep_ = net["report"]
    dropped = {d["dropped"] for d in rep_.get("duplicates", [])} | {d["dropped"] for d in rep_.get("angle_drops", [])}
    city["roads"] = [r for r in city["roads"] if r["id"] not in dropped]
    for nd in city["nodes"]: nd["edges"] = [e for e in nd["edges"] if e not in dropped]
    city["mrs_removed"] = {"houses": gone, "shops": shops, "roads": sorted(dropped)}
    out["roads_removed"] = len(dropped)
    out["houses_removed"] = len(gone); out["shops_removed"] = len(shops)
    G = np.load(os.path.join(plan_dir, "graded.npz"))
    gh = G["height"].astype(np.float64).copy(); cell = float(city["cell_m"]); n = gh.shape[0]
    import bisect
    verts, polys, starts = [], [], []
    for me in ground_meshes:
        # loop triangles (ear clipping): a fan over a long concave n-gon would cover the inside of a bend
        me.calc_loop_triangles()
        starts.append(len(polys))
        base = len(verts); verts += [tuple(v.co) for v in me.vertices]; polys += [tuple(base + i for i in t.vertices) for t in me.loop_triangles]
    changed = lowered = raised = 0
    if polys:
        bvh = BVHTree.FromPolygons(verts, polys)
        xs = [v[0] for v in verts]; ys = [v[1] for v in verts]
        i0 = max(0, int((min(xs) + HALF) / cell) - 1); i1 = min(n - 1, int((max(xs) + HALF) / cell) + 1)
        j0 = max(0, int((min(ys) + HALF) / cell) - 1); j1 = min(n - 1, int((max(ys) + HALF) / cell) + 1)
        down = Vector((0, 0, -1))
        T = np.full(gh.shape, np.inf); S = np.full(gh.shape, -1, np.int32)      # target, and which street surface
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                hit = bvh.ray_cast(Vector((i * cell - HALF, j * cell - HALF, 400.0)), down, 1000.0)
                if hit[0] is not None:
                    T[j, i] = hit[0].z - SINK; S[j, i] = bisect.bisect_right(starts, hit[2]) - 1
        # under a street: SINK below its surface (deeper than a kerb, so the bilinear ground between a sidewalk point
        # and a road point stays under both). Next to one (within a cell): no higher than the street surface's plane,
        # fitted to the street points round it and extended to this point, so the ground between grid points (the
        # terrain mesh and the height-map collider are both bilinear) cannot rise through a sidewalk's back edge, and
        # a steep street does not drag its neighbours down by the grade. Points inside a building keep their height.
        own = np.isfinite(T); new_gh = np.where(own, T, gh)
        keep = _building_mask(city, gh.shape, cell)
        js, is_ = np.nonzero(~own[j0:j1 + 1, i0:i1 + 1])
        for jj, ii in zip(js + j0, is_ + i0):
            if keep[jj, ii]: continue
            groups = {}
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    if 0 <= jj + dj < n and 0 <= ii + di < n and own[jj + dj, ii + di]:
                        groups.setdefault(int(S[jj + dj, ii + di]), []).append((di, dj, T[jj + dj, ii + di]))
            if not groups: continue
            # one plane per street surface round the point (never one plane through a road and a higher cross
            # street), the lowest of them caps it
            new_gh[jj, ii] = min(gh[jj, ii], min(_plane_cap(np, pts) for pts in groups.values()) - NEAR_MARGIN)
        diff = new_gh - gh
        changed = int(np.count_nonzero(np.abs(diff) > 0.01)); lowered = int(np.count_nonzero(diff < -0.01)); raised = int(np.count_nonzero(diff > 0.01))
        out["max_lowered"] = round(float(-diff.min()), 2); out["max_raised"] = round(float(diff.max()), 2)
        gh = new_gh
    out.update(ground_points=changed, lowered=lowered, raised=raised)
    np.savez_compressed(os.path.join(plan_out, "graded.npz"), height=gh, water=G["water"], water_level=G["water_level"])
    gh.astype(np.float32).tofile(os.path.join(plan_out, "heights.f32"))
    for f in os.listdir(plan_dir):
        if f not in ("city.json", "graded.npz", "heights.f32") and os.path.isfile(os.path.join(plan_dir, f)): shutil.copy2(os.path.join(plan_dir, f), os.path.join(plan_out, f))
    json.dump(city, open(os.path.join(plan_out, "city.json"), "w", encoding="utf-8"), separators=(",", ":"))
    log("PLAN", json.dumps(out))
    return out
