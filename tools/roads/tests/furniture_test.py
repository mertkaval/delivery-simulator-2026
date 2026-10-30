"""Headless validation of the sidewalk furniture library (mrs/furniture.py).

    blender --background --factory-startup --python tools/roads/tests/furniture_test.py [-- --rebake] [--no-render]

Builds MRS_Props etc. (assets.build_assets) and MRS_Furniture (baking the atlas when missing / outdated or
with --rebake), then checks: names, custom-property contract, footprint vs mesh bounds (10 %), origin at
the ground centre, flush heights, outward normals (signed volume per shell, open only at z = 0), material
slots (atlas + optional glass), UVs inside each face's atlas cell, LOD1 budget, atlas textures, and the
exported GLB (named nodes, extras, textures). Writes to tmp/roads/v4/furniture/: furniture.glb,
layout.json (scenes shared with tests/capture_mrs_furniture.gd), per-object renders + catalogue.png (contact
sheet via tools/roads/sheet.py with the system Python), overview / close-up renders, atlas_labelled.png.
"""
import json, math, os, shutil, struct, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
import bpy, bmesh
from mathutils import Vector
import mrs.assets as A
from mrs import furniture as F, qa
from mrs.nodes import MRS

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.join(ROOT, "tmp", "roads", "v4", "furniture"); os.makedirs(OUT, exist_ok=True)
TILES = os.path.join(ROOT, "tmp", "roads", "materials", "tiles")
fails, notes = [], []


def log(*a): print("[furniture_test]", *a, flush=True)


# ------------------------------------------------------------------------------------------- build
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
t0 = time.time(); A.build_assets(); log("build_assets %.1f s" % (time.time() - t0))
t0 = time.time(); col = F.build_furniture(bake=True if "--rebake" in ARGS else "auto"); log("build_furniture %.1f s" % (time.time() - t0))
objs = {o.name: o for o in col.objects}

# ------------------------------------------------------------------------------------------- checks
REQUIRED = ["MRS_F_Bench", "MRS_F_BenchBackless", "MRS_F_BinWaste", "MRS_F_BinRecycling", "MRS_F_BikeRackHoop", "MRS_F_BikeRackRow",
            "MRS_F_BusShelter", "MRS_F_BusShelter_LOD1", "MRS_F_BusStopPole", "MRS_F_InfoBoard", "MRS_F_Bollard", "MRS_F_BollardRemovable",
            "MRS_F_PedBarrier", "MRS_F_Planter", "MRS_F_TreePitGrate", "MRS_F_TreePitOpen", "MRS_F_TreeGuard", "MRS_F_UtilityCabinet", "MRS_F_Hydrant",
            "MRS_F_DrainGrate", "MRS_F_AccessCover"]
missing = [n for n in REQUIRED if n not in objs]
if missing: fails.append("missing objects: %s" % missing)
extra = [n for n in objs if n not in REQUIRED]
if extra: fails.append("unexpected objects: %s" % extra)
if col.name not in bpy.context.scene.collection.children: fails.append("MRS_Furniture not linked under the scene")
if not col.hide_render: fails.append("MRS_Furniture not hidden from render")


def tris(me): return sum(len(p.vertices) - 2 for p in me.polygons)


def shells(me):
    """Signed volume (about the origin, which lies on the ground plane) of every edge-connected shell."""
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    seen, vols = set(), []
    for f0 in bm.faces:
        if f0.index in seen: continue
        stack, vol = [f0], 0.0; seen.add(f0.index)
        while stack:
            f = stack.pop(); vs = [v.co for v in f.verts]
            for i in range(1, len(vs) - 1): vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen: seen.add(g.index); stack.append(g)
        vols.append(vol)
    open_edges = [e for e in bm.edges if len(e.link_faces) == 1 and any(abs(v.co.z) > 1e-5 for v in e.verts)]
    nonman = [e for e in bm.edges if len(e.link_faces) > 2]
    bm.free()
    return vols, len(open_edges), len(nonman)


rows = []
atlas = bpy.data.materials.get(F.ATLAS); glass = bpy.data.materials.get(F.GLASS)
for name in REQUIRED:
    o = objs.get(name)
    if o is None: continue
    me = o.data; P = []
    for k in ("mrs_kind", "mrs_footprint", "mrs_access", "mrs_zone", "mrs_walkable", "mrs_height"):
        if k not in o.keys(): P.append("missing prop " + k)
    if P: fails.append("%s: %s" % (name, ", ".join(P))); continue
    try:
        fp = json.loads(o["mrs_footprint"]); acc = json.loads(o["mrs_access"])
    except (TypeError, ValueError) as e:
        fails.append("%s: bad JSON props (%s)" % (name, e)); continue
    if o["mrs_kind"] not in F.KINDS: P.append("kind %s" % o["mrs_kind"])
    if o["mrs_zone"] not in F.ZONES: P.append("zone %s" % o["mrs_zone"])
    if not isinstance(o["mrs_walkable"], bool): P.append("mrs_walkable is %s, not bool" % type(o["mrs_walkable"]).__name__)
    if not (isinstance(fp, list) and len(fp) == 2 and all(isinstance(v, (int, float)) and v > 0 for v in fp)): P.append("footprint %s" % fp)
    if sorted(acc) != ["back", "front", "left", "right"] or any(not isinstance(v, (int, float)) or v < 0 for v in acc.values()): P.append("access %s" % acc)
    if o.get("mrs_facing") not in F.FACINGS: P.append("facing %s" % o.get("mrs_facing"))
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    bx, by, bz = max(xs) - min(xs), max(ys) - min(ys), max(zs)
    for got, want, ax in ((bx, fp[0], "w"), (by, fp[1], "d")):
        if abs(want - got) > 0.10 * got: P.append("footprint %s %.3f vs mesh %.3f" % (ax, want, got))
    if abs(max(xs) + min(xs)) > 0.01 or abs(max(ys) + min(ys)) > 0.01: P.append("origin not at the XY centre (%.3f, %.3f)" % ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2))
    if abs(min(zs)) > 1e-4: P.append("min z %.4f" % min(zs))
    if abs(o["mrs_height"] - bz) > 0.01: P.append("mrs_height %.3f vs %.3f" % (o["mrs_height"], bz))
    if name in F.FLUSH:
        if bz > 0.01: P.append("flush item max z %.4f > 0.01" % bz)
        if o["mrs_walkable"] and not (0.003 <= bz <= 0.0065): P.append("walkable top %.4f outside 0.003-0.006" % bz)
    vols, open_e, nonman = shells(me)
    if nonman: P.append("%d non-manifold edges" % nonman)
    neg = [v for v in vols if v <= 1e-9]
    if neg: P.append("%d of %d shells have inward / zero volume" % (len(neg), len(vols)))
    if open_e: P.append("%d open edges above the ground" % open_e)
    if any(p.area < 1e-9 for p in me.polygons): P.append("zero-area faces")
    mats = [m.name if m else None for m in me.materials]
    if not (1 <= len(mats) <= 2) or mats[0] != F.ATLAS or (len(mats) == 2 and mats[1] != F.GLASS): P.append("materials %s" % mats)
    if any(p.material_index >= len(mats) for p in me.polygons): P.append("material index out of range")
    if not me.uv_layers: P.append("no UVs")
    else:
        uvl = me.uv_layers[0].data; cell = me.attributes["mrs_cell"].data; bad = 0
        for p in me.polygons:
            cid = cell[p.index].value; cname = F.CELLS[cid][0] if cid < len(F.CELLS) else "white"
            u0, v0, u1, v1 = F.cell_uv_rect(cname); e = 0.5 / F.AW
            for li in p.loop_indices:
                u, v = uvl[li].uv
                if not (u0 - e <= u <= u1 + e and v0 - e <= v <= v1 + e): bad += 1
        if bad: P.append("%d UVs outside their atlas cell" % bad)
    if not o.hide_viewport or not o.hide_render: P.append("not hidden")
    st = F.REPORT.get(name, {})
    if st.get("warnings"): notes += st["warnings"]
    if P: fails.append("%s: %s" % (name, "; ".join(P)))
    rows.append((name, tris(me), "+".join(m.replace("MRS_Furniture", "") or "" for m in mats), fp, round(bz, 3), o["mrs_zone"], o["mrs_kind"], acc,
                 st.get("min_ppm"), st.get("islands")))
lod0, lod1 = objs.get("MRS_F_BusShelter"), objs.get("MRS_F_BusShelter_LOD1")
if lod0 and lod1:
    r = tris(lod1.data) / tris(lod0.data)
    if r > 0.35: fails.append("shelter LOD1 has %.0f %% of LOD0 tris" % (100 * r))
    if lod0.get("mrs_lod1") != lod1.name or lod1.get("mrs_lod_of") != lod0.name: fails.append("LOD links missing")
# material uses image textures only
img_nodes = [n for n in atlas.node_tree.nodes if n.type == "TEX_IMAGE"] if atlas else []
if len(img_nodes) != 3 or any(n.image is None or tuple(n.image.size) != (F.AW, F.AH) for n in img_nodes): fails.append("atlas material image nodes: %s" % [(n.image.name, tuple(n.image.size)) for n in img_nodes if n.image])
proc = [n.type for n in atlas.node_tree.nodes if n.type.startswith("TEX_") and n.type != "TEX_IMAGE"] if atlas else []
if proc: fails.append("procedural nodes left in the atlas material: %s" % proc)
for p in F._paths(F.TEX_DIR).values():
    if not os.path.exists(p): fails.append("texture missing: " + p)

# ------------------------------------------------------------------------------------------- GLB export
glb = os.path.join(OUT, "furniture.glb")
st = F.export_library_glb(glb)
with open(glb, "rb") as f: data = f.read()
clen = struct.unpack_from("<I", data, 12)[0]; gj = json.loads(data[20:20 + clen])
nodes = {n.get("name"): n for n in gj.get("nodes", [])}
miss = [n for n in REQUIRED if n not in nodes]
if miss: fails.append("GLB nodes missing: %s" % miss)
noextra = [n for n in REQUIRED if n in nodes and "mrs_kind" not in nodes[n].get("extras", {})]
if noextra: fails.append("GLB nodes without extras: %s" % noextra)
notorigin = [n for n in REQUIRED if n in nodes and any(abs(v) > 1e-6 for v in nodes[n].get("translation", [0, 0, 0]))]
if notorigin: fails.append("GLB nodes not at the origin: %s" % notorigin)
gm = {m["name"]: m for m in gj.get("materials", [])}
pbr = gm.get(F.ATLAS, {}).get("pbrMetallicRoughness", {})
if set(gm) != {F.ATLAS, F.GLASS}: fails.append("GLB materials %s" % sorted(gm))
if "baseColorTexture" not in pbr or "metallicRoughnessTexture" not in pbr or "normalTexture" not in gm.get(F.ATLAS, {}): fails.append("GLB atlas textures missing: %s" % gm.get(F.ATLAS))
if gm.get(F.GLASS, {}).get("alphaMode") != "BLEND": fails.append("GLB glass alphaMode %s" % gm.get(F.GLASS, {}).get("alphaMode"))
log("GLB %s: %d nodes, %d materials, %d images, %d tris, %.1f MB" % (glb, len(nodes), len(gm), len(gj.get("images", [])), st["tris"], st["bytes"] / 1e6))

# ------------------------------------------------------------------------------------------- table
print("\n%-24s %6s %-12s %-14s %6s %-10s %-12s %-34s %6s" % ("name", "tris", "materials", "footprint", "height", "zone", "kind", "access f/b/l/r", "px/m"))
for name, t, mats, fp, h, zone, kind, acc, ppm, isl in rows:
    print("%-24s %6d %-12s %-14s %6.3f %-10s %-12s %-34s %6s" % (name, t, mats or "Atlas", "%.2f x %.2f" % tuple(fp), h, zone, kind,
          "%.2f / %.2f / %.2f / %.2f" % (acc["front"], acc["back"], acc["left"], acc["right"]), ppm))
print("%-24s %6d" % ("total (LOD0)", sum(r[1] for r in rows if not r[0].endswith("_LOD1"))))
for n in notes: log("note:", n)

# ------------------------------------------------------------------------------------------- renders
sysPy = shutil.which("python") or shutil.which("python3")


def sys_python(args):
    if not sysPy: log("no system python: skipped", args[:1]); return
    r = subprocess.run([sysPy] + args, capture_output=True, text=True)
    if r.returncode: fails.append("system python failed: %s" % r.stderr[-400:])
    else: log(r.stdout.strip())


if "--no-render" not in ARGS:
    scene = bpy.context.scene
    stage = bpy.data.collections.new("FurnitureStage"); scene.collection.children.link(stage)
    # paving ground (the road tiles baked by materials_test), metres / 4 m tile
    gm_ = bpy.data.materials.new("FurnTestPaving"); nt = F._nt(gm_); b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    pav = {k: os.path.join(TILES, "MRS_Paving_%s.png" % k) for k in ("albedo", "roughness", "normal")}
    if all(os.path.exists(p) for p in pav.values()):
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.25, 0.25, 0.25)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        for k, cs in (("albedo", "sRGB"), ("roughness", "Non-Color"), ("normal", "Non-Color")):
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(pav[k], check_existing=True); t.image.colorspace_settings.name = cs
            nt.links.new(mp.outputs[0], t.inputs["Vector"])
            if k == "albedo": nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
            elif k == "roughness": nt.links.new(t.outputs["Color"], b.inputs["Roughness"])
            else:
                nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(t.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    else:
        b.inputs["Base Color"].default_value = (0.4, 0.4, 0.38, 1)
    gme = bpy.data.meshes.new("FurnTestGround"); S = 80.0
    gme.from_pydata([(-S, -S, 0), (S, -S, 0), (S, S, 0), (-S, S, 0)], [], [(0, 1, 2, 3)]); gme.materials.append(gm_)
    ground = bpy.data.objects.new("FurnTestGround", gme); stage.objects.link(ground)
    cam, sun = qa.ensure_camera_and_sun(scene)
    sun.data.energy = 3.2; sun.rotation_euler = (math.radians(50), 0, math.radians(150))          # from the front (+Y), right, above
    scene.view_settings.view_transform = "AgX"
    insts = []

    def place(name, pos, rot=0.0):
        src = objs[name]; d = bpy.data.objects.new(name + ".stage", src.data); stage.objects.link(d)
        d.location = pos; d.rotation_euler = (0, 0, rot); insts.append(d); return d

    def clear():
        for d in insts: bpy.data.objects.remove(d)
        insts.clear()

    def frame(lo, hi, direction, lens=35.0, pad=1.1, aspect=16 / 9.0):
        lo, hi = Vector(lo), Vector(hi); c = (lo + hi) / 2; d = Vector(direction).normalized()
        right = d.cross(Vector((0, 0, 1))).normalized(); up = right.cross(d).normalized()
        corners = [Vector((x, y, z)) - c for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        hr = max(abs(p.dot(right)) for p in corners); vr = max(abs(p.dot(up)) for p in corners); dp = max(abs(p.dot(d)) for p in corners)
        hf = 2 * math.atan(18.0 / lens); vf = 2 * math.atan(math.tan(hf / 2) / aspect)
        dist = max(hr / math.tan(hf / 2), vr / math.tan(vf / 2)) * pad + dp
        return tuple(c + d * dist), tuple(c)

    def vfov(lens, aspect): return math.degrees(2 * math.atan(math.tan(math.atan(18.0 / lens)) / aspect))

    def bounds(ds):
        bpy.context.view_layer.update()
        pts = [d.matrix_world @ v.co for d in ds for v in d.data.vertices]
        return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]

    layout = {"ground": {k: os.path.abspath(p) for k, p in pav.items()}, "tile_m": 4.0, "scenes": {},
              "sun_dir": None, "note": "Blender coordinates (x, y, z) -> Godot (x, z, -y); rot_z -> rotation.y"}
    dsun = sun.rotation_euler.to_matrix() @ Vector((0, 0, -1)); layout["sun_dir"] = [dsun.x, dsun.y, dsun.z]   # light travel direction

    def shoot(key, eye, tgt, lens, res, samples=32):
        path = os.path.join(OUT, "%s.png" % key); qa.render(path, eye, tgt, lens, res=res, samples=samples, scene=scene)
        layout["scenes"][key] = {"items": [{"name": d.name[:-6], "pos": list(d.location), "rot_z": d.rotation_euler.z} for d in insts],
                                 "camera": {"eye": list(eye), "target": list(tgt), "lens": lens, "vfov_deg": vfov(lens, res[0] / res[1])}, "res": list(res)}
        log("rendered", path); return path

    # per-object catalogue renders (contact sheet)
    cat_dir = os.path.join(OUT, "catalogue"); os.makedirs(cat_dir, exist_ok=True)
    paths = []
    for name in REQUIRED:
        clear(); d = place(name, (0, 0, 0)); lo, hi = bounds([d])
        flush = name in F.FLUSH
        direction = (0.35, 0.75, 1.0) if flush else ((0.55, 1.0, 0.35) if name != "MRS_F_PedBarrier" else (0.45, 1.0, 0.45))
        if flush: hi[2] = max(hi[2], 0.3)
        eye, tgt = frame(lo, hi, direction, 40.0, 1.12, 4 / 3)
        path = os.path.join(cat_dir, "%s_%dtris.png" % (name, tris(objs[name].data)))
        qa.render(path, eye, tgt, 40.0, res=(512, 384), samples=16, scene=scene); paths.append(path)
    clear()
    sys_python([os.path.join(ROOT, "tools", "roads", "sheet.py"), os.path.join(OUT, "catalogue.png"), "5"] + paths)

    # overview grid (also captured in Godot). Cameras look from +Y at the fronts, so screen-right is -X:
    # positions are given as screen x (s) and placed at x = -s.
    def group(key, items, direction, lens, res=(1600, 900), pad=1.06, min_top=0.0):
        for nm, s_, y_ in items: place(nm, (-s_, y_, 0.0))
        lo, hi = bounds(insts); hi[2] = max(hi[2], min_top)
        eye, tgt = frame(lo, hi, direction, lens, pad, res[0] / res[1]); shoot(key, eye, tgt, lens, res); clear()

    items, s_, y_, row_d = [], 0.0, 0.0, 0.0
    for name in REQUIRED:
        w, dd = json.loads(objs[name]["mrs_footprint"])
        if s_ + w > 13.0: s_ = 0.0; y_ -= row_d + 1.6; row_d = 0.0
        items.append((name, s_ + w / 2, y_ - dd / 2)); s_ += w + 1.0; row_d = max(row_d, dd)
    group("overview", items, (0.0, 1.0, 0.85), 35.0, (1920, 1080), 1.02)
    group("closeup_bench_bin_rack", [("MRS_F_BikeRackRow", -2.75, -0.25), ("MRS_F_Bollard", -1.0, 1.25), ("MRS_F_Bench", 0.0, 0.0),
                                     ("MRS_F_BollardRemovable", 1.15, 1.25), ("MRS_F_BinWaste", 1.5, 0.05), ("MRS_F_BinRecycling", 2.65, 0.05)], (0.12, 1.0, 0.38), 35.0, pad=1.0)
    group("closeup_shelter_pole_board", [("MRS_F_InfoBoard", -3.0, 0.3), ("MRS_F_BusShelter", 0.0, 0.0), ("MRS_F_BusStopPole", 2.85, 1.1),
                                         ("MRS_F_Hydrant", 3.75, 1.35)], (0.15, 1.0, 0.28), 35.0, pad=1.0)
    group("closeup_detail", [("MRS_F_InfoBoard", -1.55, 0.0), ("MRS_F_Bench", 0.0, 0.0), ("MRS_F_BinWaste", 1.45, 0.05)], (0.2, 1.0, 0.3), 35.0, pad=0.98)
    group("closeup_flush", [("MRS_F_AccessCover", -1.45, 0.4), ("MRS_F_TreePitGrate", 0.0, 0.0), ("MRS_F_TreePitOpen", 2.2, 0.0), ("MRS_F_DrainGrate", 3.95, 0.9),
                            ("MRS_F_Bollard", -1.5, -1.1)], (0.0, 0.75, 1.0), 35.0, min_top=0.4)
    with open(os.path.join(OUT, "layout.json"), "w", encoding="utf-8") as f: json.dump(layout, f, indent=1)
    # labelled atlas (system python, PIL)
    script = os.path.join(OUT, "_label_atlas.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write("import json, sys\nfrom PIL import Image, ImageDraw\nlay = json.load(open(sys.argv[1]))\nim = Image.open(sys.argv[2]).convert('RGB'); d = ImageDraw.Draw(im)\n"
                "for n, c in lay['cells'].items():\n    x, y, w, h = c['px']; d.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 0, 255))\n"
                "    t = n + ('' if c['metres'] is None else ' %gx%g m' % tuple(c['metres']))\n    d.rectangle([x + 2, y + 2, x + 8 + 6 * len(t), y + 14], fill=(0, 0, 0)); d.text((x + 5, y + 3), t, fill=(255, 255, 0))\n"
                "im.save(sys.argv[3]); print('labelled atlas', sys.argv[3])\n")
    sys_python([script, os.path.join(F.TEX_DIR, "atlas_layout.json"), F._paths(F.TEX_DIR)["albedo"], os.path.join(OUT, "atlas_labelled.png")])

print("\nRESULT:", "FAIL" if fails else "PASS")
for f_ in fails: print("  FAIL", f_)
if fails: sys.exit(1)
