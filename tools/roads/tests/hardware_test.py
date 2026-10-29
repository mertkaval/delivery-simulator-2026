"""Street-hardware polish validation: streetlights, barriers, signs / signals and the footbridge MRS_HW_* materials.

    blender --background --factory-startup --python tools/roads/tests/hardware_test.py -- [--baseline] [--no-render] [--rebake]
    blender --background --factory-startup --python tools/roads/tests/hardware_test.py -- --compose   (after the Godot capture)

--baseline  rebuilds the library from the base commit's assets.py / signage.py (`git show`, in a temporary copy of the
            package without hardware.py) and writes tmp/roads/v5/hardware/baseline.json (names, collections, children,
            dimensions, custom properties, materials, triangles) and before/*.png with the same scenes and cameras.
default     builds the current library (mrs.assets.build_assets(), mrs.signage.build_signage(),
            mrs.hardware.build_hardware_materials()), checks it against baseline.json (names / collections / origins /
            dimensions / contract properties unchanged, lens / lamp materials kept, game materials image-textured),
            exports hardware.glb through mrs.export.apply_engine_materials (+ layout.json for tests/capture_hardware.gd),
            renders after/*.png (catalogue per object, close-ups, footbridge material swatches, a night shot) and the
            before | after sheets, and writes tris.json (triangles per asset before / after).
--compose   only rebuilds the before | after | Godot comparison sheets (run after tests/capture_hardware.gd).
Prints HARDWARE OK / FAIL lines; exit code 1 on failures.
"""
import json, math, os, shutil, subprocess, sys, time, traceback

ROOT = "C:/GodotProjects/delivery-simulator-2026"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
BASELINE = "--baseline" in ARGS
OUT = os.path.join(ROOT, "tmp", "roads", "v5", "hardware")
BASE_COMMIT = "fe2bd6a"                 # last commit before the hardware polish (assets.py / signage.py as audited in v4)
TILES = os.path.join(ROOT, "tmp", "roads", "materials", "tiles")
os.makedirs(OUT, exist_ok=True)
SYSPY = shutil.which("python") or shutil.which("python3")
T0 = time.time()


def log(*a):
    print("[hardware %5.1fs]" % (time.time() - T0), *a, flush=True)


def sys_python(args):
    if not SYSPY: log("no system python: skipped", os.path.basename(args[0])); return False
    r = subprocess.run([SYSPY] + args, capture_output=True, text=True)
    if r.returncode: log("system python failed:", r.stderr[-600:]); return False
    if r.stdout.strip(): log(r.stdout.strip()[-300:])
    return True


# ------------------------------------------------------------------------------------------------ compose only
COMPOSE = os.path.join(OUT, "_compose.py")
with open(COMPOSE, "w", encoding="utf-8") as f:
    f.write('''import json, os, sys
from PIL import Image, ImageDraw
out, cols_spec, rows = sys.argv[1], sys.argv[2], sys.argv[3:]
cols = cols_spec.split(",")
W = 640
cells = []
for r in rows:
    row = []
    for c in cols:
        p = c.replace("{}", r)
        row.append(Image.open(p).convert("RGB") if os.path.exists(p) else None)
    cells.append(row)
H = max([int(im.height * W / im.width) for row in cells for im in row if im] or [360])
S = Image.new("RGB", (W * len(cols), H * len(rows)), (35, 35, 35)); d = ImageDraw.Draw(S)
for i, row in enumerate(cells):
    for j, im in enumerate(row):
        if im is not None:
            im = im.resize((W, int(im.height * W / im.width))); S.paste(im, (j * W, i * H))
        lab = os.path.basename(cols[j].replace("{}", rows[i]))
        d.rectangle([j * W + 4, i * H + 4, j * W + 12 + 6 * len(lab), i * H + 18], fill=(0, 0, 0)); d.text((j * W + 8, i * H + 6), lab, fill=(255, 230, 0))
S.save(out, quality=88)
print(out, S.size)
''')

CLOSEUPS = ["lights_row", "cu_highway_head", "cu_led_head", "cu_lantern", "cu_pole_base", "cu_bollard_wallpack", "signs_front", "cu_sign_text",
            "cu_sign_back", "cu_direction_board", "signals_row", "cu_signal_head", "cu_signal_ped", "barriers_row", "cu_guardrail", "cu_jersey_parapet",
            "cu_railing_fence", "hw_materials", "hw_materials_close", "night_lights"]


def compose_sheets():
    B, A, G = os.path.join(OUT, "before"), os.path.join(OUT, "after"), os.path.join(OUT, "godot")
    groups = {"compare_lights": CLOSEUPS[:6] + ["night_lights"], "compare_signs": CLOSEUPS[6:13], "compare_barriers": CLOSEUPS[13:17],
              "compare_footbridge_materials": CLOSEUPS[17:19]}
    for name, keys in groups.items():
        sys_python([COMPOSE, os.path.join(OUT, name + ".jpg"), ",".join([os.path.join(B, "{}.png"), os.path.join(A, "{}.png"), os.path.join(G, "godot_{}.png")])] + keys)


if "--compose" in ARGS:
    compose_sheets(); sys.exit(0)

# ------------------------------------------------------------------------------------------------ package (baseline = base commit)
if BASELINE:
    pkg = os.path.join(OUT, "_baseline_pkg"); dst = os.path.join(pkg, "mrs")
    if os.path.isdir(pkg): shutil.rmtree(pkg)
    shutil.copytree(os.path.join(ROOT, "tools", "roads", "mrs"), dst, ignore=shutil.ignore_patterns("__pycache__", "hardware.py"))
    for f_ in ("assets.py", "signage.py"):
        src = subprocess.run(["git", "-C", ROOT, "show", "%s:tools/roads/mrs/%s" % (BASE_COMMIT, f_)], capture_output=True, text=True, encoding="utf-8")
        if src.returncode: raise RuntimeError("git show failed: %s" % src.stderr)
        with open(os.path.join(dst, f_), "w", encoding="utf-8", newline="\n") as fh: fh.write(src.stdout)
    sys.path.insert(0, pkg)
else:
    sys.path.insert(0, ROOT + "/tools/roads")

import bpy, bmesh
from mathutils import Vector, Matrix
import mrs
from mrs import qa, assets as A, signage as S
from mrs.nodes import MRS
HW = None if BASELINE else __import__("mrs.hardware", fromlist=["hardware"])
fails, notes = [], []


def check(cond, msg):
    if not cond: fails.append(msg); log("FAIL", msg)
    return cond


# ------------------------------------------------------------------------------------------------ build
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
scene = bpy.context.scene
t = time.time()
mrs.materials.build_materials(); mrs.materials.extra_materials()
mrs.props.build_prop_collections()
if HW is not None and "--rebake" in ARGS: HW.build_hardware_materials(bake=True)
A.build_assets(); lib = S.build_signage()
hwm = HW.build_hardware_materials() if HW is not None else {}
log("library built in %.1f s (%s)" % (time.time() - t, "baseline %s" % BASE_COMMIT if BASELINE else "current"))


def tris_of(o):
    n = 0
    for ob in [o] + list(o.children_recursive):
        if ob.type == "MESH": n += sum(len(p.vertices) - 2 for p in ob.data.polygons)
        elif ob.type == "FONT":
            dg = bpy.context.evaluated_depsgraph_get(); me = ob.evaluated_get(dg).to_mesh()
            n += sum(len(p.vertices) - 2 for p in me.polygons); ob.evaluated_get(dg).to_mesh_clear()
    return n


def tree_bbox(o):
    """Bounds of the object and its children in the object's own frame (library objects sit at the origin)."""
    bpy.context.view_layer.update()
    def local(ob):                                          # parent chain from matrix_basis (hidden objects are not evaluated)
        m = Matrix.Identity(4)
        while ob is not None and ob is not o: m = ob.matrix_parent_inverse @ ob.matrix_basis if m is None else (ob.matrix_parent_inverse @ ob.matrix_basis) @ m; ob = ob.parent
        return m
    pts = []
    for ob in [o] + list(o.children_recursive):
        if ob.type in ("MESH", "FONT"): pts += [local(ob) @ Vector(c) for c in ob.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def pyval(v):
    if hasattr(v, "to_dict"): return {k: pyval(x) for k, x in v.to_dict().items()}
    if hasattr(v, "to_list"): return [pyval(x) for x in v.to_list()]
    if isinstance(v, dict): return {k: pyval(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [pyval(x) for x in v]
    if isinstance(v, (int, float, str, bool)) or v is None: return v
    return str(v)


def family(o):
    cols = [c.name for c in o.users_collection]
    if MRS + "Streetlights" in cols: return "lights"
    if MRS + "Barriers" in cols: return "barriers"
    if o.get("mrs_signal"): return "signals"
    if o.get("mrs_sign") is not None: return "boards" if o.name == MRS + "DirectionBoard" else "signs"
    return "other"


def library():
    objs = sorted(bpy.data.collections[MRS + "Streetlights"].objects, key=lambda o: o.name) + sorted(bpy.data.collections[MRS + "Barriers"].objects, key=lambda o: o.name)
    objs += sorted([o for o in bpy.data.collections[S.LIB].objects if o.parent is None], key=lambda o: o.name)
    return objs


def snapshot():
    out = {}
    for o in library():
        lo, hi = tree_bbox(o)
        me_lo = [min((v.co[i] for v in o.data.vertices), default=0.0) for i in range(3)]
        me_hi = [max((v.co[i] for v in o.data.vertices), default=0.0) for i in range(3)]
        out[o.name] = {"family": family(o), "collections": sorted(c.name for c in o.users_collection), "location": [round(c, 5) for c in o.location],
                       "children": sorted(c.name for c in o.children), "child_types": sorted(set(c.type for c in o.children)),
                       "bbox": [[round(c, 4) for c in lo], [round(c, 4) for c in hi]], "mesh_bbox": [[round(c, 4) for c in me_lo], [round(c, 4) for c in me_hi]],
                       "dims": [round(hi[i] - lo[i], 4) for i in range(3)], "props": {k: pyval(o[k]) for k in o.keys() if not k.startswith("_")},
                       "mesh_props": {k: pyval(o.data[k]) for k in o.data.keys() if not k.startswith("_")},
                       "materials": sorted({m.name for ob in [o] + list(o.children_recursive) if ob.type == "MESH" for m in ob.data.materials if m}),
                       "tris": tris_of(o), "objects": 1 + len(o.children_recursive)}
        for c in o.children:
            if c.type == "MESH":
                out[o.name].setdefault("child_props", {})[c.name] = {k: pyval(c[k]) for k in c.keys() if not k.startswith("_")}
    return out


snap = snapshot()
if BASELINE:
    with open(os.path.join(OUT, "baseline.json"), "w", encoding="utf-8") as f: json.dump(snap, f, indent=1)
    log("baseline.json: %d objects" % len(snap))
else:
    # -------------------------------------------------------------------------------------------- contract checks
    bp = os.path.join(OUT, "baseline.json")
    if not check(os.path.exists(bp), "baseline.json missing: run with -- --baseline first"):
        base = {}
    else:
        with open(bp, encoding="utf-8") as f: base = json.load(f)
    TOL = {"lights": (0.002, 0.002, 0.002), "barriers": (0.002, 0.002, 0.002), "signs": (0.01, 0.03, 0.01), "boards": (0.01, 0.03, 0.01), "signals": (0.01, 0.01, 0.01)}
    check(sorted(snap) == sorted(base), "library names changed: added %s, removed %s" % (sorted(set(snap) - set(base)), sorted(set(base) - set(snap))))
    for name, b in sorted(base.items()):
        a = snap.get(name)
        if a is None: continue
        fam = b["family"]; tol = TOL.get(fam, (0.002,) * 3)
        check(a["collections"] == b["collections"], "%s collections %s != %s" % (name, a["collections"], b["collections"]))
        check(a["location"] == b["location"], "%s origin moved %s -> %s" % (name, b["location"], a["location"]))
        for i in range(3):
            check(abs(a["dims"][i] - b["dims"][i]) <= tol[i], "%s dimension %s %.4f -> %.4f (tol %.3f)" % (name, "xyz"[i], b["dims"][i], a["dims"][i], tol[i]))
        check(abs(a["bbox"][0][2]) < 0.002, "%s min z %.4f (origin must stay at the base)" % (name, a["bbox"][0][2]))
        # contract properties
        for k in ("mrs_fixtures",):
            if k in b["props"]:
                check(a["props"].get(k) == b["props"][k], "%s %s changed" % (name, k)); check(a["mesh_props"].get(k) == b["mesh_props"].get(k), "%s mesh %s changed" % (name, k))
        if "mrs_signal" in b["props"]:
            sa, sb = a["props"].get("mrs_signal", {}), b["props"]["mrs_signal"]
            for k in ("style", "pole_height", "arm_length", "setback", "lens_size", "faces", "housing"):
                check(sa.get(k) == sb.get(k), "%s mrs_signal.%s %s -> %s" % (name, k, sb.get(k), sa.get(k)))
            ha = [{k: h.get(k) for k in ("kind", "lenses", "lens_materials", "object", "mount")} for h in sa.get("heads", [])]
            hb = [{k: h.get(k) for k in ("kind", "lenses", "lens_materials", "object", "mount")} for h in sb.get("heads", [])]
            check(ha == hb, "%s signal heads changed" % name)
            check(a["children"] == b["children"], "%s signal children %s -> %s" % (name, b["children"], a["children"]))
            for cn, cp in b.get("child_props", {}).items():
                check(a.get("child_props", {}).get(cn, {}).get("mrs_signal_head") == cp.get("mrs_signal_head"), "%s head %s mrs_signal_head changed" % (name, cn))
        if "mrs_sign" in b["props"]:
            ma, mb = a["props"].get("mrs_sign", {}), b["props"]["mrs_sign"]
            for k in ("kind", "text", "value", "size", "pole_height", "double", "faces"):
                if k in mb: check(ma.get(k) == mb.get(k), "%s mrs_sign.%s %s -> %s" % (name, k, mb.get(k), ma.get(k)))
            leg_b = mb.get("legends", []); leg_a = ma.get("legends", []) + ma.get("baked_legends", [])
            check(sorted(leg_a) == sorted(leg_b), "%s legends %s -> %s" % (name, leg_b, leg_a))
        # materials: lens / lamp materials stay; everything else is an image-textured game material
        for m in b["materials"]:
            if m.startswith(MRS + "Lens_") or m.startswith(MRS + "PropLamp"):
                check(m in a["materials"], "%s lost material %s" % (name, m))
    # every library mesh: UVs, material slots in range, game materials image-textured (export passes them through)
    from mrs import export as EX
    for o in library():
        for ob in [o] + list(o.children_recursive):
            if ob.type != "MESH": continue
            me = ob.data
            check(bool(me.uv_layers), "%s has no UVs" % ob.name)
            used = {v for p in me.polygons for v in p.vertices}
            check(len(used) == len(me.vertices), "%s: %d loose verts" % (ob.name, len(me.vertices) - len(used)))
            check(not any(p.area < 1e-9 for p in me.polygons), "%s: zero-area faces" % ob.name)
            if family(o) in ("lights", "barriers"): check(50 <= len(me.vertices) <= 3000, "%s: %d verts (assets_test range 50..3000)" % (ob.name, len(me.vertices)))
            check(all(p.material_index < len(me.materials) for p in me.polygons), "%s material index out of range" % ob.name)
            for m in me.materials:
                if m is None or m.name.startswith(MRS + "PropLamp"): continue          # the shared lamp emitter is flattened by name (contract)
                em = EX.engine_material(m)
                check(em is m, "%s: material %s is not passed through by export.engine_material (-> %s)" % (ob.name, m.name, em.name if em else None))
    for nm in ("MRS_HW_PaintedSteel", "MRS_HW_Galvanized", "MRS_HW_Stainless", "MRS_HW_Concrete", "MRS_HW_DeckAntiSlip", "MRS_HW_LEDDiffuser", "MRS_HW_Glass"):
        m = bpy.data.materials.get(nm)
        if check(m is not None, "material %s missing" % nm):
            check(EX.engine_material(m) is m, "%s not passed through by engine_material" % nm)
            if nm != "MRS_HW_Glass":
                imgs = [n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
                check(len(imgs) >= 3, "%s has %d image textures" % (nm, len(imgs)))
    # signal lens / housing conventions (read by the Godot loader and signage_test)
    for o in [o for o in library() if family(o) == "signals"]:
        for h in o.children:
            mats = [m.name for m in h.data.materials if m]
            check(MRS + "SignalHousing" in mats, "%s: MRS_SignalHousing missing (%s)" % (h.name, mats))
            for k in h["mrs_signal_head"]["lenses"]:
                m = bpy.data.materials.get(MRS + "Lens_" + k)
                check(m is not None and m.node_tree.nodes.get("State") is not None and (MRS + "Lens_" + k) in mats, "%s: lens %s / State node" % (h.name, k))
    # lighting fixture checks (same as lighting_test): emitters near anchors, aim clear of the own mesh, housing above
    from mrs import lighting as L
    from mathutils.bvhtree import BVHTree
    for o in [o for o in library() if family(o) == "lights"]:
        me = o.data; fx = L.fixtures_of(o)
        li = [i for i, m in enumerate(me.materials) if m and m.name.startswith(L.LAMP_MATERIAL_PREFIXES)]
        lf = [p for p in me.polygons if p.material_index in li]
        check(lf, "%s: no emitter faces" % o.name)
        for p in lf: check(min((p.center - Vector(f["pos"])).length for f in fx) < 0.35, "%s: stray emitter face at %s" % (o.name, tuple(round(x, 2) for x in p.center)))
        bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        lbvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in lf])
        for f in fx:
            pos = Vector(f["pos"]); near = lbvh.find_nearest(pos)[3]
            check(near < 0.10, "%s: anchor %s is %.3f m from the emitter" % (o.name, f["pos"], near))
            if o.name not in ("MRS_Light_Lantern", "MRS_Light_Bollard"):
                for tilt in (0.0, 10.0):
                    hit = bvh.ray_cast(pos, L._aim(f, tilt)); check(hit[0] is None, "%s: aim (tilt %g) hits its own mesh at %s" % (o.name, tilt, hit[0]))
                if Vector(f["dir"]).z < -0.9:
                    hit = bvh.ray_cast(pos, Vector((0, 0, 1))); check(hit[0] is not None and hit[3] < 0.3, "%s: no housing above the anchor" % o.name)
    # tris table
    rows = []
    for name in sorted(base):
        if name in snap: rows.append((base[name]["family"], name, base[name]["tris"], snap[name]["tris"], base[name]["objects"], snap[name]["objects"],
                                      len(base[name]["materials"]), len(snap[name]["materials"])))
    with open(os.path.join(OUT, "tris.json"), "w", encoding="utf-8") as f:
        json.dump([{"family": r[0], "name": r[1], "tris_before": r[2], "tris_after": r[3], "objects_before": r[4], "objects_after": r[5],
                    "materials_before": r[6], "materials_after": r[7]} for r in rows], f, indent=1)
    print("\n%-10s %-32s %8s %8s %6s %10s" % ("family", "asset", "before", "after", "x", "materials"))
    for r in rows: print("%-10s %-32s %8d %8d %6.2f %5d -> %d" % (r[0], r[1], r[2], r[3], r[3] / max(1, r[2]), r[6], r[7]))
    for fam in ("lights", "barriers", "signs", "signals", "boards"):
        b_ = sum(r[2] for r in rows if r[0] == fam); a_ = sum(r[3] for r in rows if r[0] == fam)
        print("%-10s %-32s %8d %8d %6.2f" % (fam, "(total)", b_, a_, a_ / max(1, b_)))
    if HW is not None: print("HW REPORT", json.dumps(HW.REPORT, indent=None)[:2000])

# ------------------------------------------------------------------------------------------------ stage: footbridge material swatches
stage = bpy.data.collections.new("HardwareStage"); scene.collection.children.link(stage)


def _mesh(name, bm, mats, uv_mode):
    """uv_mode: 'latalong' (footbridge slab: u = lateral x, v = along y), 'world' (stairs: u = x, v = y), 'zero' (Curve to Mesh tubes)."""
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = (co.x, co.y) if uv_mode in ("latalong", "world") else (0.0, 0.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    o = bpy.data.objects.new(name, me); return o


def swatch_objects():
    """A footbridge-like test piece with the footbridge's UV conventions: deck slab and girders u = lateral, v = along
    (metres), stairs u = x, v = y, railing tubes / posts / columns without UVs (Curve to Mesh)."""
    if HW is not None:
        mt = {k: bpy.data.materials[n] for k, n in (("deck", "MRS_HW_DeckAntiSlip"), ("steel", "MRS_HW_PaintedSteel"), ("rail", "MRS_HW_Stainless"),
                                                     ("galv", "MRS_HW_Galvanized"), ("concrete", "MRS_HW_Concrete"), ("led", "MRS_HW_LEDDiffuser"))}
    else:
        from mrs.props import mat as fmat
        mt = {"deck": bpy.data.materials.get(MRS + "Paving") or fmat(MRS + "FB_Deck", (0.42, 0.42, 0.40), 0.85),
              "steel": fmat(MRS + "FB_Steel", (0.20, 0.26, 0.30), 0.45, 0.6),
              "rail": bpy.data.materials.get(MRS + "PropSteel"), "galv": bpy.data.materials.get(MRS + "PropSteel"),
              "concrete": bpy.data.materials.get(MRS + "PropConcrete"), "led": fmat(MRS + "FB_LED", (1.0, 0.9, 0.75), 0.4)}
        b_ = next(n for n in mt["led"].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b_.inputs["Emission Color"].default_value = (1.0, 0.86, 0.66, 1); b_.inputs["Emission Strength"].default_value = 3.0
    objs = []
    L_, W_, Z = 9.0, 3.0, 2.2                                              # deck along +Y, top at Z
    bm = bmesh.new(); A._box(bm, -W_ / 2, 0, Z - 0.22, W_ / 2, L_, Z); objs.append(_mesh("HW_Swatch_Deck", bm, [mt["deck"]], "latalong"))
    bm = bmesh.new()                                                       # two painted I-girders under the deck
    for x in (-0.95, 0.95):
        A._box(bm, x - 0.16, 0, Z - 0.26, x + 0.16, L_, Z - 0.22); A._box(bm, x - 0.012, 0, Z - 0.84, x + 0.012, L_, Z - 0.26); A._box(bm, x - 0.16, 0, Z - 0.88, x + 0.16, L_, Z - 0.84)
    objs.append(_mesh("HW_Swatch_Girders", bm, [mt["steel"]], "latalong"))
    bm = bmesh.new()                                                       # galvanised posts + stainless handrail + infill bars (no UVs)
    for x in (-1.45, 1.45):
        for y in (0.4, 2.9, 5.4, 7.9): A._box(bm, x - 0.03, y - 0.03, Z, x + 0.03, y + 0.03, Z + 1.1)
    objs.append(_mesh("HW_Swatch_Posts", bm, [mt["galv"]], "zero"))
    bm = bmesh.new()
    for x in (-1.45, 1.45):
        A._tube(bm, [(x, 0.2, Z + 1.1), (x, L_ - 0.2, Z + 1.1)], 0.03, 12); A._tube(bm, [(x * 0.97, 0.2, Z + 0.9), (x * 0.97, L_ - 0.2, Z + 0.9)], 0.021, 10)
        for k in range(36): A._cyl(bm, x, 0.35 + k * 0.24, Z + 0.1, Z + 1.08, 0.008, 0.008, 6)
    objs.append(_mesh("HW_Swatch_Rails", bm, [mt["rail"]], "zero"))
    bm = bmesh.new()
    for x in (-1.42, 1.42): A._box(bm, x - 0.005, 0.2, Z + 0.07, x + 0.005, L_ - 0.2, Z + 0.09)
    objs.append(_mesh("HW_Swatch_LED", bm, [mt["led"]], "zero"))
    bm = bmesh.new()                                                       # concrete column + crosshead (no UVs) and a stair flight (u = x, v = y)
    A._cyl(bm, 0, 1.2, 0, Z - 0.88, 0.32, 0.32, 16); A._box(bm, -1.3, 0.8, Z - 1.3, 1.3, 1.6, Z - 0.88)
    objs.append(_mesh("HW_Swatch_Column", bm, [mt["concrete"]], "zero"))
    bm = bmesh.new()
    for k in range(7): A._box(bm, 2.3, -0.3 * k - 0.3, 0, 3.8, -0.3 * k, 0.163 * (7 - k))
    objs.append(_mesh("HW_Swatch_Stairs", bm, [mt["concrete"]], "world"))
    for o in objs: stage.objects.link(o); o.hide_render = True; o.hide_viewport = True; o["mrs_swatch"] = 1
    return objs


swatches = swatch_objects()

# ------------------------------------------------------------------------------------------------ GLB export (current build)
if not BASELINE:
    from mrs import export as EX
    tmpc = bpy.data.collections.new("HardwareExport"); scene.collection.children.link(tmpc)
    copies = []

    def copy_tree(o, parent=None):
        c = bpy.data.objects.new(o.name, o.data.copy() if o.type == "MESH" else o.data); tmpc.objects.link(c)
        for k in o.keys():
            if not k.startswith("_"): c[k] = o[k]
        if parent is not None: c.parent = parent; c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        c.matrix_basis = o.matrix_basis.copy(); copies.append(c)
        for ch in o.children: copy_tree(ch, c)
        return c
    for o in library() + swatches: copy_tree(o)
    n_lamp = sum(1 for c in copies if c.type == "MESH" for m in c.data.materials if m and m.name.startswith(MRS + "PropLamp"))
    n_eng = EX.apply_engine_materials(copies) - n_lamp
    check(n_eng == 0, "%d material slots were replaced by export.engine_material (expected 0: game materials are image-textured)" % n_eng)
    for c in copies: c.hide_viewport = False; c.hide_render = False
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects: o.select_set(o in copies)
    bpy.context.view_layer.objects.active = copies[0]
    glb = os.path.join(OUT, "hardware.glb")
    stash = {k: scene[k] for k in list(scene.keys()) if k.startswith("mrs_")}
    for k in stash: del scene[k]
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_extras=True,
                              export_materials="EXPORT", export_normals=True, export_texcoords=True, export_lights=False)
    for k, v in stash.items(): scene[k] = v
    log("exported", glb, "%.1f MB" % (os.path.getsize(glb) / 1e6))
    # inspect the GLB json: materials, textures, alpha, texture transforms
    import struct
    with open(glb, "rb") as f:
        f.read(12); ln, _ = struct.unpack("<II", f.read(8)); gj = json.loads(f.read(ln))
    gm = {m["name"]: m for m in gj.get("materials", [])}
    for nm, m in sorted(gm.items()):
        pbr = m.get("pbrMetallicRoughness", {})
        tex = "baseColorTexture" in pbr
        if nm.startswith(MRS + "Lens_") or nm.startswith(MRS + "PropLamp"): continue
        if nm == "MRS_HW_Glass":
            check(m.get("alphaMode") == "BLEND", "MRS_HW_Glass alphaMode %s (want BLEND)" % m.get("alphaMode")); continue
        if nm == "MRS_SignFace_Atlas":                                                  # printed sheeting: albedo only
            check(tex, "GLB material %s lacks its baseColor texture" % nm); continue
        check(tex and "metallicRoughnessTexture" in pbr and "normalTexture" in m, "GLB material %s lacks baseColor / metallicRoughness / normal textures" % nm)
        if nm.startswith("MRS_HW_") and tex and nm != "MRS_HW_Stainless":             # Stainless tiles at 1 m: identity transform, not written
            tt = pbr["baseColorTexture"].get("extensions", {}).get("KHR_texture_transform")
            check(tt is not None and "scale" in tt, "GLB material %s has no KHR_texture_transform (metre UVs)" % nm)
    notes.append("GLB materials: %s" % ", ".join(sorted(gm)))
    for c in list(copies):
        d = c.data; bpy.data.objects.remove(c)
        if isinstance(d, bpy.types.Mesh) and d.users == 0: bpy.data.meshes.remove(d)
    bpy.data.collections.remove(tmpc)

# ------------------------------------------------------------------------------------------------ renders
if "--no-render" not in ARGS:
    RD = os.path.join(OUT, "before" if BASELINE else "after"); os.makedirs(RD, exist_ok=True)
    gm_ = bpy.data.materials.new("HWTestPaving"); nt = gm_.node_tree or (setattr(gm_, "use_nodes", True) or gm_.node_tree)
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    pav = {k: os.path.join(TILES, "MRS_Paving_%s.png" % k) for k in ("albedo", "roughness", "normal")}
    if all(os.path.exists(p) for p in pav.values()):
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.25, 0.25, 0.25)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        for k, cs in (("albedo", "sRGB"), ("roughness", "Non-Color"), ("normal", "Non-Color")):
            t_ = nt.nodes.new("ShaderNodeTexImage"); t_.image = bpy.data.images.load(pav[k], check_existing=True); t_.image.colorspace_settings.name = cs
            nt.links.new(mp.outputs[0], t_.inputs["Vector"])
            if k == "albedo": nt.links.new(t_.outputs["Color"], b.inputs["Base Color"])
            elif k == "roughness": nt.links.new(t_.outputs["Color"], b.inputs["Roughness"])
            else:
                nm_ = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(t_.outputs["Color"], nm_.inputs["Color"]); nt.links.new(nm_.outputs[0], b.inputs["Normal"])
    else:
        b.inputs["Base Color"].default_value = (0.4, 0.4, 0.38, 1)
    gme = bpy.data.meshes.new("HWTestGround"); SZ = 120.0
    gme.from_pydata([(-SZ, -SZ, 0), (SZ, -SZ, 0), (SZ, SZ, 0), (-SZ, SZ, 0)], [], [(0, 1, 2, 3)]); gme.materials.append(gm_)
    ground = bpy.data.objects.new("HWTestGround", gme); stage.objects.link(ground)
    cam, sun = qa.ensure_camera_and_sun(scene)
    sun.data.energy = 3.2; sun.rotation_euler = (math.radians(50), 0, math.radians(150))
    scene.view_settings.view_transform = "AgX"
    try: scene.eevee.use_shadows = True
    except Exception: pass
    insts = []
    layout = {"ground": {k: os.path.abspath(p) for k, p in pav.items()}, "tile_m": 4.0, "scenes": {}, "sun_dir": None,
              "note": "Blender coordinates (x, y, z) -> Godot (x, z, -y); rot_z -> rotation.y"}
    dsun = sun.rotation_euler.to_matrix() @ Vector((0, 0, -1)); layout["sun_dir"] = [dsun.x, dsun.y, dsun.z]

    def place(name, pos, rot=0.0):
        src = bpy.data.objects[name]

        def rec(s, parent):
            d = bpy.data.objects.new(s.name + ".stage", s.data); stage.objects.link(d)
            if parent is None: d.location = pos; d.rotation_euler = (0, 0, rot); d["mrs_placed"] = s.name; d["lib"] = s.name
            else: d.parent = parent; d.matrix_parent_inverse = s.matrix_parent_inverse.copy(); d.matrix_basis = s.matrix_basis.copy()
            insts.append(d)
            for ch in s.children: rec(ch, d)
            return d
        return rec(src, None)

    def clear():
        for d in reversed(insts):
            for ch in [c for c in d.children if c.type == "LIGHT"]:
                ld = ch.data; bpy.data.objects.remove(ch)
                if ld.users == 0: bpy.data.lights.remove(ld)
            bpy.data.objects.remove(d)
        insts.clear()

    def bounds(ds):
        bpy.context.view_layer.update(); pts = []
        for d in ds:
            for ob in [d] + list(d.children_recursive):
                if ob.type in ("MESH", "FONT"): pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]

    def frame(lo, hi, direction, lens=35.0, pad=1.1, aspect=16 / 9.0):
        lo, hi = Vector(lo), Vector(hi); c = (lo + hi) / 2; d = Vector(direction).normalized()
        right = d.cross(Vector((0, 0, 1))).normalized(); up = right.cross(d).normalized()
        corners = [Vector((x, y, z)) - c for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        hr = max(abs(p.dot(right)) for p in corners); vr = max(abs(p.dot(up)) for p in corners); dp = max(abs(p.dot(d)) for p in corners)
        hf = 2 * math.atan(18.0 / lens); vf = 2 * math.atan(math.tan(hf / 2) / aspect)
        dist = max(hr / math.tan(hf / 2), vr / math.tan(vf / 2)) * pad + dp
        return tuple(c + d * dist), tuple(c)

    def vfov(lens, aspect): return math.degrees(2 * math.atan(math.tan(math.atan(18.0 / lens)) / aspect))

    def shoot(key, eye, tgt, lens, res=(1600, 900), samples=32, night=False):
        path = os.path.join(RD, "%s.png" % key); qa.render(path, eye, tgt, lens, res=res, samples=samples, scene=scene)
        layout["scenes"][key] = {"items": [{"name": d["lib"], "pos": list(d.location), "rot_z": d.rotation_euler.z} for d in insts if d.parent is None],
                                 "camera": {"eye": list(eye), "target": list(tgt), "lens": lens, "vfov_deg": vfov(lens, res[0] / res[1])}, "res": list(res), "night": night}
        log("rendered", path); return path

    def scene_(key, items, eye=None, tgt=None, lens=35.0, direction=None, pad=1.08, res=(1600, 900), samples=32):
        for it in items: place(*it)
        if eye is None:
            lo, hi = bounds(insts); eye, tgt = frame(lo, hi, direction, lens, pad, res[0] / res[1])
        p = shoot(key, eye, tgt, lens, res, samples); clear(); return p

    # ---- per-object catalogue
    cat = os.path.join(RD, "catalogue"); os.makedirs(cat, exist_ok=True)
    DIRS = {"lights": (1.0, -0.45, 0.22), "barriers": (-1.0, -0.6, 0.45), "signs": (0.3, 1.0, 0.12), "boards": (0.25, 1.0, 0.1), "signals": (0.45, -1.0, 0.15)}
    for o in library():
        fam = family(o); its = [(o.name, (0, 0, 0))]
        if fam == "barriers": its = [(o.name, (0, -2.0, 0)), (o.name, (0, 0, 0)), (o.name, (0, 2.0, 0))]
        for it in its: place(*it)
        lo, hi = bounds(insts); eye, tgt = frame(lo, hi, DIRS[fam], 40.0, 1.1, 4 / 3)
        qa.render(os.path.join(cat, "%s.png" % o.name), eye, tgt, 40.0, res=(512, 384), samples=16, scene=scene); clear()
    log("catalogue renders done")

    # ---- close-ups (fixed cameras, same in before / after / Godot)
    LX = {"MRS_Light_Highway": 0.0, "MRS_Light_Double": 5.5, "MRS_Light_LED": 11.0, "MRS_Light_Lantern": 15.0, "MRS_Light_Bollard": 17.5, "MRS_Light_WallPack": 19.5}
    lights_items = [(n, (x, 0, 0)) for n, x in LX.items()]
    scene_("lights_row", lights_items, (9.75 + 15.0, -21.0, 6.5), (9.75, 0.6, 4.8), 35.0)
    scene_("cu_highway_head", [("MRS_Light_Highway", (0, 0, 0))], (1.7, 0.6, 8.75), (0, 2.15, 9.85), 45.0)
    scene_("cu_led_head", [("MRS_Light_LED", (0, 0, 0))], (1.25, 0.05, 6.05), (0, 0.78, 6.97), 45.0)
    scene_("cu_lantern", [("MRS_Light_Lantern", (0, 0, 0))], (1.45, -1.2, 3.55), (0, 0, 3.72), 45.0)
    scene_("cu_pole_base", [("MRS_Light_Highway", (0, 0, 0)), ("MRS_Light_LED", (0.9, 0.55, 0))], (1.6, -1.55, 0.95), (0.4, 0.2, 0.32), 40.0)
    scene_("cu_bollard_wallpack", [("MRS_Light_Bollard", (0, 0, 0)), ("MRS_Light_WallPack", (0.9, -0.4, 0))], (3.4, 4.3, 2.5), (0.55, -0.25, 1.75), 32.0)
    sg = [o for o in library() if family(o) == "signs"]; byn = {o.name: o for o in sg}
    front = ["MRS_Sign_Stop", "MRS_Sign_Yield", "MRS_Sign_Speed50", "MRS_Sign_NoEntry", "MRS_Sign_PedestrianCrossing", "MRS_Sign_Roundabout", "MRS_Sign_Children",
             "MRS_Sign_Parking", "MRS_Sign_BicycleRoute"]
    scene_("signs_front", [(n, (-i * 1.05 + 4.2, 0, 0)) for i, n in enumerate(front)], (0.0, 10.5, 2.4), (0.0, 0.0, 2.15), 35.0)
    scene_("cu_sign_text", [("MRS_Sign_Stop", (0.9, 0, 0)), ("MRS_Sign_BusStop", (-0.25, 0, 0)), ("MRS_Sign_StreetNameDouble", (-1.55, 0, 0))],
           (-0.25, 3.4, 2.45), (-0.25, 0.0, 2.45), 40.0)
    scene_("cu_sign_back", [("MRS_Sign_Stop", (0.0, 0, 0)), ("MRS_Sign_DirectionBoard", (-2.2, 0, 0))], (0.9, -3.2, 2.0), (-0.9, 0.0, 2.3), 40.0)
    scene_("cu_direction_board", [("MRS_DirectionBoard", (0, 0, 0))], (-1.2, 7.5, 2.6), (0, 0, 3.2), 40.0)
    sigs = [o.name for o in library() if family(o) == "signals"]
    SX = {"MRS_Signal_Post": 0.0, "MRS_Signal_Pedestrian": 2.5, "MRS_Signal_Bicycle": 5.0, "MRS_Signal_Combined": 7.5, "MRS_Signal_MastArm": 10.5}
    scene_("signals_row", [(n, (SX.get(n, 0.0), 0, 0)) for n in sigs], (8.0, -15.5, 3.6), (8.0, 0.0, 3.2), 35.0)
    scene_("cu_signal_head", [("MRS_Signal_Post", (0, 0, 0))], (0.75, -1.9, 3.45), (0, -0.2, 3.35), 40.0)
    scene_("cu_signal_ped", [("MRS_Signal_Combined", (0, 0, 0))], (0.8, -2.3, 2.1), (0, -0.2, 2.15), 40.0)
    BX = {"MRS_Guardrail": 0.0, "MRS_Jersey": 2.0, "MRS_Parapet": 4.2, "MRS_Railing": 6.4, "MRS_Fence": 8.2, "MRS_Hedge": 10.0}
    bars = []
    for n, x in BX.items(): bars += [(n, (x, -2.0, 0)), (n, (x, 0.0, 0)), (n, (x, 2.0, 0))]
    scene_("barriers_row", bars, (-3.8, -8.5, 3.6), (5.0, 0.6, 0.45), 35.0)
    scene_("cu_guardrail", [("MRS_Guardrail", (0, -2.0, 0)), ("MRS_Guardrail", (0, 0, 0)), ("MRS_Guardrail", (0, 2.0, 0))], (-1.35, -1.7, 1.05), (0, 0.6, 0.55), 40.0)
    scene_("cu_jersey_parapet", [("MRS_Jersey", (0, -2.0, 0)), ("MRS_Jersey", (0, 0, 0)), ("MRS_Parapet", (1.4, -2.0, 0)), ("MRS_Parapet", (1.4, 0, 0))],
           (-1.9, -3.4, 1.55), (0.6, 0.0, 0.55), 40.0)
    scene_("cu_railing_fence", [("MRS_Railing", (0, -2.0, 0)), ("MRS_Railing", (0, 0, 0)), ("MRS_Fence", (1.3, -2.0, 0)), ("MRS_Fence", (1.3, 0, 0)),
                                ("MRS_Hedge", (2.7, -2.0, 0)), ("MRS_Hedge", (2.7, 0, 0))], (-1.6, -3.6, 1.6), (1.3, 0.0, 0.55), 40.0)
    # ---- footbridge material swatches (swatch objects are hidden library-like objects: place them by name)
    scene_("hw_materials", [(o.name, (0, 0, 0)) for o in swatches], (6.2, -4.5, 3.9), (0.0, 3.0, 1.6), 35.0)
    scene_("hw_materials_close", [(o.name, (0, 0, 0)) for o in swatches], (1.0, 1.3, 2.75), (-1.35, 3.8, 2.4), 40.0)
    # ---- night: the light row with real light sources (lighting.py presets) and lamp emission
    from mrs import lighting as L
    for it in lights_items: place(*it)
    lights_ = L.add_lights_for_collection(stage)
    L.night_setup(scene)
    key = "night_lights"; eye, tgt = (9.75 + 15.0, -21.0, 6.5), (9.75, 0.6, 4.8)
    shoot(key, eye, tgt, 35.0, samples=48, night=True)
    layout["scenes"][key]["lights"] = L.light_records(stage); layout["night"] = L.lights_model(stage).get("night", {})
    L.day_setup(scene); clear()
    with open(os.path.join(OUT, "layout.json" if not BASELINE else "layout_before.json"), "w", encoding="utf-8") as f: json.dump(layout, f, indent=1)
    # ---- sheets
    if BASELINE:
        sys_python([os.path.join(ROOT, "tools", "roads", "sheet.py"), os.path.join(OUT, "catalogue_before.png"), "6"] + [os.path.join(cat, o.name + ".png") for o in library()])
    else:
        pairs = []
        for o in library(): pairs += [os.path.join(OUT, "before", "catalogue", o.name + ".png"), os.path.join(cat, o.name + ".png")]
        pairs = [p for p in pairs if os.path.exists(p)]
        fams = {}
        for o in library(): fams.setdefault(family(o), []).append(o.name)
        for fam, names in fams.items():
            sys_python([COMPOSE, os.path.join(OUT, "catalogue_%s.jpg" % fam), ",".join([os.path.join(OUT, "before", "catalogue", "{}.png"), os.path.join(cat, "{}.png")])] + names)
        compose_sheets()

print("\nnotes:"); [print("  ", n) for n in notes]
print("RESULT:", ("BASELINE written" if BASELINE else ("HARDWARE FAIL (%d)" % len(fails) if fails else "HARDWARE OK")))
for f_ in fails: print("  FAIL", f_)
sys.exit(1 if fails else 0)
