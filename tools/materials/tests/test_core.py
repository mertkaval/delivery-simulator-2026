"""procmat core tests (headless; one Blender at a time).

    python tools/materials/tests/test_core.py [--out DIR] [--no-road]
        launcher (system Python): stage "core" in a factory-startup Blender, then - when tmp/roads/city/base.blend
        exists - stage "road" in a second Blender run that opens it. Full logs: <out>/stage_<name>.log
    blender --background --factory-startup --python tools/materials/tests/test_core.py -- --stage core [--out DIR]
    blender --background tmp/roads/city/base.blend --python tools/materials/tests/test_core.py -- --stage road [--out DIR]

core : registry; contract of PM_CoreDemo (one group node "MRS", label, BSDF -> Surface, Use UV / Tile Size,
       BSDF / Albedo outputs, 4D textures); displacement wiring; per-material defaults; graphdump; EEVEE renders in
       object mode on the icosphere and the 7 m x 20 m road strip (+ a side-by-side); UV-mode bake of a 4 m tile with
       the seam metric (ratio ~ 1) against an object-mode control (a visible seam); the seamless() fallback for a
       3D-only texture (Gabor) against its raw control; object mode in metres (a 1 m plane equals the centre of a
       4 m plane at the same texel density) against a UV-mode control.
road : the road tool's own make_road() builds a residential road in base.blend; road_adapter assigns PM_CoreDemo
       to Asphalt Material (Asphalt Condition -> Default) and the evaluated road mesh carries it (control: a "Worn"
       condition hides the socket); Paving Material (Sidewalk Surface -> Default); set_road() resets, reapply()
       restores; assign_roads(); the bus shelter's glass slots; an eye-level render. base.blend is never saved.
Every check prints "CORE_TEST OK <check>: <measurements>" or "CORE_TEST FAIL <check>: ..."; the last line is
"CORE_TEST OK" or "CORE_TEST FAIL".
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAT_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(MAT_DIR))
OUT_DEFAULT = os.path.join(ROOT, "tmp", "materials_core")
BASE = os.path.join(ROOT, "tmp", "roads", "city", "base.blend")
BLENDER = os.environ.get("PM_BLENDER", r"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe")

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


class Tester:
    def __init__(self):
        self.fails = []; self.n = 0

    def check(self, name, ok, detail=None):
        self.n += 1
        d = "" if detail is None else ": " + (detail if isinstance(detail, str) else json.dumps(detail, default=str))
        print(("CORE_TEST OK %s%s" if ok else "CORE_TEST FAIL %s%s") % (name, d[:900]))
        if not ok: self.fails.append(name)
        return bool(ok)

    def done(self, stage):
        if self.fails: print("CORE_TEST FAIL stage %s: %d of %d checks failed: %s" % (stage, len(self.fails), self.n, self.fails))
        else: print("CORE_TEST OK stage %s: %d checks" % (stage, self.n))
        return not self.fails


# ============================================================================================ stage core
def stage_core(out):
    import bpy
    import numpy as np
    sys.path.insert(0, MAT_DIR)
    import procmat
    from procmat import bake as B, core, graphdump, imaging, rig
    T = Tester(); t0 = time.time()
    st = procmat.discover(verbose=False)
    T.check("registry: material modules discovered, demo registered", st.get("demo") == "ok" and "coredemo" in procmat.MATERIALS
            and "coredemo" not in procmat.library_keys(), st)
    mats = procmat.build("coredemo")
    demo = bpy.data.materials.get("PM_CoreDemo"); seam = bpy.data.materials.get("PM_CoreSeamless")
    T.check("build coredemo returns PM_CoreDemo + PM_CoreSeamless", demo in mats and seam in mats, [m.name for m in mats])

    # ---- contract
    T.check("contract PM_CoreDemo (check_contract)", core.check_contract(demo) == [], core.check_contract(demo))
    T.check("contract PM_CoreSeamless (check_contract)", core.check_contract(seam) == [], core.check_contract(seam))
    nt = demo.node_tree
    groups = [n for n in nt.nodes if n.bl_idname == "ShaderNodeGroup"]
    outn = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    T.check("one group node named MRS, label = group name, BSDF -> Surface",
            len(groups) == 1 and groups[0].name == "MRS" and groups[0].label == "PM_CoreDemo" and groups[0].node_tree.name == "PM_CoreDemo"
            and outn.inputs["Surface"].links[0].from_socket.name == "BSDF" and not outn.inputs["Displacement"].is_linked,
            {"nodes": [(n.name, n.bl_idname) for n in nt.nodes], "label": groups[0].label if groups else None})
    g = bpy.data.node_groups["PM_CoreDemo"]
    ins, outs = core.input_names(g), core.output_names(g)
    T.check("interface: Use UV / Tile Size / Scale in, BSDF / Albedo / Height out",
            {"Use UV", "Tile Size", "Scale", "Cell Size"} <= set(ins) and outs[:3] == ["BSDF", "Albedo", "Height"], {"in": ins, "out": outs})
    tex = [n for n in g.nodes if n.bl_idname in ("ShaderNodeTexNoise", "ShaderNodeTexVoronoi")]
    dims = sorted({getattr(n, "noise_dimensions", getattr(n, "voronoi_dimensions", "?")) for n in tex})
    T.check("every Noise / Voronoi in the group is 4D", tex and dims == ["4D"], {"textures": len(tex), "dims": dims})
    real = [n for n in g.nodes if n.bl_idname != "NodeFrame"]
    rect = [(n.location_absolute[0], n.location_absolute[1], n.width, core._height(n)) for n in real]
    overl = sum(1 for i in range(len(rect)) for j in range(i + 1, len(rect))
                if rect[i][0] < rect[j][0] + rect[j][2] and rect[j][0] < rect[i][0] + rect[i][2]
                and rect[i][1] - rect[i][3] < rect[j][1] and rect[j][1] - rect[j][3] < rect[i][1])
    T.check("graph laid out: frames (Coordinates + 4 material frames), no overlapping nodes",
            sum(1 for n in g.nodes if n.bl_idname == "NodeFrame") >= 5 and overl == 0,
            {"nodes": len(real), "overlaps": overl, "frames": [n.label for n in g.nodes if n.bl_idname == "NodeFrame"]})
    disp = core.contract_material("CoreDemoDisp", g, displacement=True)
    od = next(n for n in disp.node_tree.nodes if n.type == "OUTPUT_MATERIAL")
    T.check("displacement=True: Height -> Displacement node -> Output Displacement, method BOTH",
            od.inputs["Displacement"].is_linked and od.inputs["Displacement"].links[0].from_node.bl_idname == "ShaderNodeDisplacement"
            and disp.displacement_method == "BOTH" and demo.displacement_method == "BUMP", disp.displacement_method)
    big = core.contract_material("CoreDemoBig", g, Cell_Size=1.2, **{"Stone Color": (0.5, 0.2, 0.1)})
    nb = core.group_node(big)
    T.check("per-material defaults (Cell_Size=1.2, Stone Color)", abs(nb.inputs["Cell Size"].default_value - 1.2) < 1e-6
            and abs(nb.inputs["Stone Color"].default_value[0] - 0.5) < 1e-6 and big.use_fake_user and big.get("procmat") == "PM_CoreDemo",
            {"cell": nb.inputs["Cell Size"].default_value, "viewport": tuple(round(c, 3) for c in big.diffuse_color)})

    # ---- graph dump
    md_path = graphdump.write(demo, os.path.join(out, "PM_CoreDemo_NODES.md"))
    md = open(md_path, encoding="utf-8").read()
    T.check("graphdump: interface, inventory, connections", "## Group PM_CoreDemo" in md and "| Use UV |" in md and "ShaderNodeTexVoronoi" in md
            and "### Connections" in md and "noise_dimensions=4D" in md and "ramp[LINEAR]" in md, {"path": md_path, "chars": len(md)})

    # ---- renders (object mode)
    rdir = os.path.join(out, "renders")
    paths = rig.preview(demo, rdir, views=("sphere", "road"), engine="EEVEE", res=640, samples=32, hdri="city")
    for v, p in paths.items():
        s = imaging.stats(p)
        T.check("EEVEE render %s (object mode)" % v, os.path.exists(p) and s["std"] > 0.02 and 0.01 < s["mean"] < 0.95, dict(s, path=p))
    sbs = rig.side_by_side(paths["sphere"], paths["road"], os.path.join(rdir, "PM_CoreDemo_sphere_road.png"),
                           labels=("icosphere r = 1 m, object mode", "road strip 7 x 20 m, eye level 1.7 m"))
    T.check("side_by_side with labels (Pillow via the system Python)", os.path.exists(sbs), sbs)
    ps = rig.preview(seam, rdir, views=("plane",), engine="EEVEE", res=480, samples=16)
    T.check("EEVEE render of the seamless demo (plane, top view)", imaging.stats(ps["plane"])["std"] > 0.02, imaging.stats(ps["plane"]))

    # ---- bake: UV mode tiles, seam metric, control
    bdir = os.path.join(out, "bake")
    pb = B.bake(demo, bdir, tile=4.0, res=1024, samples=16)
    for key in ("albedo", "normal", "roughness"):
        mm = B.seam_metric(pb[key])
        T.check("seamless UV bake 4 m tile: %s seams look like any pixel step" % key, B.is_seamless(mm), mm)
    T.check("tile preview 2 x 2", os.path.exists(B.tile_preview(pb["albedo"], 2)), pb["albedo"])
    pc = B.bake(demo, bdir, tile=4.0, res=1024, samples=16, maps=["albedo"], use_uv=False, prefix="CONTROL_PM_CoreDemo_objectmode")
    mc = B.seam_metric(pc["albedo"])
    T.check("control: the same bake in object mode shows a seam (metric discriminates)", mc["outlier_x"] > 2 and mc["outlier_y"] > 2 and mc["ratio"] > 2, mc)
    B.tile_preview(pc["albedo"], 2)
    # periodicity, directly: the material's UVs shifted by (0.5, 0.25) bake the tile rolled by (256, 128) px
    pdir = os.path.join(out, "periodicity")
    pr = B.periodicity(demo, pdir, tile=4.0, res=512, samples=16, maps=("albedo", "normal"))
    T.check("periodic (4D torus): UVs + (0.5, 0.25) bake = the tile rolled by (256, 128) px", B.is_periodic(pr),
            {k: {kk: vv for kk, vv in v.items() if kk != "files"} for k, v in pr.items()})
    pS = B.bake(seam, bdir, tile=4.0, res=1024, samples=16, maps=["albedo"])
    B.tile_preview(pS["albedo"], 2)
    pp = B.periodicity(seam, pdir, tile=4.0, res=512, samples=16)
    T.check("seamless() fallback (3D Gabor) + periodic() / wrap() slab grid repeat in UV mode", B.is_periodic(pp),
            dict({k: {kk: vv for kk, vv in v.items() if kk != "files"} for k, v in pp.items()}, seam=B.seam_metric(pS["albedo"])))
    core.set_inputs(seam, Seamless=0.0)
    pq = B.periodicity(seam, pdir, tile=4.0, res=512, samples=16, prefix="CONTROL_PM_CoreSeamless_raw")
    pR = B.bake(seam, bdir, tile=4.0, res=1024, samples=16, maps=["albedo"], prefix="CONTROL_PM_CoreSeamless_raw")
    core.set_inputs(seam, Seamless=1.0)
    B.tile_preview(pR["albedo"], 2)
    T.check("control: the raw 3D Gabor does not repeat (the periodicity test discriminates)", not B.is_periodic(pq),
            {k: {kk: vv for kk, vv in v.items() if kk != "files"} for k, v in pq.items()})
    # exact3d: 3D cells in object mode (tutorial look), 4D in UV mode, mixed by Use UV
    from procmat import demo as D
    dual = D.build_dual()
    gd = bpy.data.node_groups["PM_CoreDual"]
    vor = [n for n in gd.nodes if n.bl_idname == "ShaderNodeTexVoronoi"]
    mixes = [n for n in gd.nodes if n.bl_idname == "ShaderNodeMix" and n.label == "object 3D | UV 4D"]
    T.check("exact3d: a 3D and a 4D Voronoi per call, outputs mixed by Use UV", sorted(n.voronoi_dimensions for n in vor) == ["3D", "3D", "4D", "4D"] and len(mixes) >= 3
            and core.check_contract(dual) == [], {"voronoi": [n.voronoi_dimensions for n in vor], "mixes": len(mixes)})
    pD = B.periodicity(dual, pdir, tile=4.0, res=512, samples=16)
    T.check("exact3d material still repeats in UV mode", B.is_periodic(pD), {k: {kk: vv for kk, vv in v.items() if kk != "files"} for k, v in pD.items()})
    rd = rig.preview(dual, rdir, views=("sphere",), engine="EEVEE", res=640, samples=32, hdri="city")
    cmp_ = rig.side_by_side(paths["sphere"], rd["sphere"], os.path.join(rdir, "CoreDemo_4Dslice_vs_exact3d.png"),
                            labels=("voronoi4: 2D slice of 4D cells", "voronoi4(exact3d=True): 3D cells"))
    T.check("comparison render 4D slice vs exact3d", os.path.exists(cmp_), cmp_)

    # ---- metres: object mode, a 1 m and a 4 m plane at the same texel density (128 px / m)
    mdir = os.path.join(out, "metres")
    p1 = B.bake(demo, mdir, tile=4.0, res=128, samples=16, maps=["albedo"], use_uv=False, plane_size=1.0, prefix="PM_CoreDemo_obj_1m")
    p4 = B.bake(demo, mdir, tile=4.0, res=512, samples=16, maps=["albedo"], use_uv=False, plane_size=4.0, prefix="PM_CoreDemo_obj_4m")
    a1 = imaging.load(p1["albedo"])[..., :3]; a4 = imaging.load(p4["albedo"])[..., :3]; crop = a4[192:320, 192:320]
    corr = float(np.corrcoef(a1.ravel(), crop.ravel())[0, 1]); mad = float(np.abs(a1 - crop).mean())
    g1 = float(np.abs(np.diff(a1, axis=1)).mean()); g4 = float(np.abs(np.diff(a4, axis=1)).mean())
    T.check("object mode is metres: 1 m plane == centre metre of the 4 m plane (same texel size)", corr > 0.9 and mad < 0.03 and 0.75 < g1 / max(g4, 1e-9) < 1.33,
            {"corr": round(corr, 4), "mad": round(mad, 4), "grad_1m": round(g1, 4), "grad_4m": round(g4, 4)})
    u1 = B.bake(demo, mdir, tile=4.0, res=128, samples=16, maps=["albedo"], use_uv=True, plane_size=1.0, prefix="CONTROL_PM_CoreDemo_uv_1m")
    u4 = B.bake(demo, mdir, tile=4.0, res=512, samples=16, maps=["albedo"], use_uv=True, plane_size=4.0, prefix="CONTROL_PM_CoreDemo_uv_4m")
    b1 = imaging.load(u1["albedo"])[..., :3]; b4 = imaging.load(u4["albedo"])[..., :3]
    corr_u = float(np.corrcoef(b1.ravel(), b4[192:320, 192:320].ravel())[0, 1])
    T.check("control: UV mode (UVs 0..1 per object) is not metres", corr_u < 0.5, {"corr": round(corr_u, 4)})

    # ---- keep a .blend of the test materials for inspection (tmp only)
    keep = os.path.join(out, "core_test.blend")
    bpy.ops.wm.save_as_mainfile(filepath=keep, check_existing=False, copy=True, compress=True)
    print("core test blend:", keep, "%.1fs" % (time.time() - t0))
    return T.done("core")


# ============================================================================================ stage road
EXPECTED_SOCKETS = ("Asphalt Material", "Marking Material", "Yellow Marking Material", "Concrete Material", "Paving Material",
                    "Tactile Material", "Cycleway Material", "Bus Lane Material", "Structure Material", "Embankment Material")


def stage_road(out):
    import bpy
    T = Tester(); t0 = time.time()
    T.check("base library opened", bpy.data.filepath.replace("\\", "/").endswith("tmp/roads/city/base.blend") and "MRS_Road" in bpy.data.node_groups,
            {"file": bpy.data.filepath, "scenes": [s.name for s in bpy.data.scenes][:8]})
    # the road tool's own code builds the road (tests only; the library never imports it). No .pyc is written
    # under tools/roads (read-only for this library).
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
    from mrs import roads, nodes as mrs_nodes
    sys.path.insert(0, MAT_DIR)
    import procmat
    from procmat import core, imaging, rig, road_adapter as RA
    procmat.build("coredemo")
    demo = bpy.data.materials["PM_CoreDemo"]; seam = bpy.data.materials["PM_CoreSeamless"]
    sc = bpy.data.scenes.new("PM_CoreRoadTest"); mrs_nodes.set_scene(sc)
    col = bpy.data.collections.new("PMT_Roads"); sc.collection.children.link(col)
    R = lambda n, pts, preset, **kw: roads.make_road(n, pts, col, preset, Conform=False, Embankment=False, **kw)   # as samples.py
    road = R("PMT_Road", [(-30.0, 0.0, 0.0), (0.0, 0.0, 0.0), (30.0, 0.0, 0.0)], "residential")
    socks = RA.material_sockets(road)
    T.check("road material sockets (MRS_Road)", set(EXPECTED_SOCKETS) <= set(socks), socks)
    mod = RA.road_modifier(road)
    before = {k: getattr(RA.get_input(mod, k), "name", RA.get_input(mod, k)) for k in ("Asphalt Material", "Paving Material", "Asphalt Condition", "Sidewalk Surface")}
    ev0 = RA.evaluated_materials(road)
    T.check("road evaluates with the road tool's own materials", ev0.get(before["Asphalt Material"] or "", 0) > 0 or any(k.startswith("MRS_Asphalt") for k in ev0),
            {"inputs": before, "evaluated": ev0})
    # control: a non-Default condition overrides the socket
    RA.set_input(mod, "Asphalt Condition", "Worn"); RA.set_input(mod, "Asphalt Material", demo); road.update_tag()
    evc = RA.evaluated_materials(road)
    T.check("control: Asphalt Condition = Worn hides the Asphalt Material socket", "PM_CoreDemo" not in evc and evc.get("MRS_AsphaltWorn", 0) > 0, evc)
    rep = RA.assign(road, "Asphalt Material", demo)
    ev1 = RA.evaluated_materials(road)
    T.check("assign(Asphalt Material): menu -> Default and the evaluated road mesh carries PM_CoreDemo",
            ev1.get("PM_CoreDemo", 0) > 0 and rep["menu"] is not None and rep["menu"][2] == "Default" and RA.get_input(mod, "Asphalt Condition") == "Default",
            {"report": rep, "evaluated": ev1})
    RA.set_input(mod, "Sidewalk Surface", "Hexagon"); road.update_tag()
    rep2 = RA.assign(road, "Paving Material", seam)
    ev2 = RA.evaluated_materials(road)
    T.check("assign(Paving Material): Sidewalk Surface -> Default and the sidewalks carry PM_CoreSeamless",
            ev2.get("PM_CoreSeamless", 0) > 0 and rep2["menu"] == ("Sidewalk Surface", "Hexagon", "Default") and ev2.get("PM_CoreDemo", 0) > 0,
            {"report": rep2, "evaluated": ev2})
    T.check("assignments recorded on the object", dict(road.get(RA.RECORD, {})) == {"Asphalt Material": "PM_CoreDemo", "Paving Material": "PM_CoreSeamless"},
            dict(road.get(RA.RECORD, {})))
    roads.set_road(road)                       # the road tool re-applies its remembered inputs and MRS_* materials
    ev3 = RA.evaluated_materials(road)
    T.check("the road tool's set_road() puts its own materials back", "PM_CoreDemo" not in ev3, ev3)
    RA.reapply(col)
    ev4 = RA.evaluated_materials(road)
    T.check("reapply() restores the recorded PM materials", ev4.get("PM_CoreDemo", 0) > 0 and ev4.get("PM_CoreSeamless", 0) > 0, ev4)
    road2 = R("PMT_Road2", [(-30.0, 40.0, 0.0), (0.0, 40.0, 0.0), (30.0, 40.0, 0.0)], "residential")
    reps = RA.assign_roads(col, {"Asphalt Material": "PM_CoreDemo", "Concrete Material": "PM_DoesNotExist"})
    ev5 = RA.evaluated_materials(road2)
    T.check("assign_roads(collection, mapping): both roads, missing materials skipped", len(reps) == 2 and ev5.get("PM_CoreDemo", 0) > 0,
            {"reports": len(reps), "road2": ev5})
    # bus shelter glass slots
    gl = RA.shelter_glass_slots()
    sh = bpy.data.objects.get("MRS_F_BusShelter")
    if sh is not None:
        slots = [(i, s.material.name if s.material else None) for i, s in enumerate(sh.material_slots)]
        r = RA.replace_slot_materials(sh, "FurnitureGlass", seam, per_object=True)
        T.check("bus shelter glass: MRS_F_BusShelter slot 1 MRS_FurnitureGlass replaceable", r == [(1, "MRS_FurnitureGlass")] and sh.material_slots[1].material == seam,
                {"slots": slots, "replaced": r, "all_shelter_glass": gl})
    else:
        print("CORE_TEST NOTE shelter objects not in this file; glass slots seen:", gl)
    # evidence render (the test scene only)
    rig.set_engine(sc, "EEVEE", 32); rig.world(sc, "city", 1.0, 0.0)
    cam = bpy.data.objects.new("PMT_Camera", bpy.data.cameras.new("PMT_Camera")); col.objects.link(cam); cam.data.lens = 30.0
    rig.look_at(cam, (-33.0, -2.2, 1.7), (0.0, 1.0, 0.0)); sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    rp = rig.render(os.path.join(out, "road", "PMT_Road_PM_CoreDemo.png"), scene=sc)
    s = imaging.stats(rp)
    T.check("eye-level render of the road with PM_CoreDemo / PM_CoreSeamless", s["std"] > 0.02, dict(s, path=rp))
    print("road stage %.1fs" % (time.time() - t0))
    return T.done("road")


# ============================================================================================ entry points
def _blender_main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stage = argv[argv.index("--stage") + 1] if "--stage" in argv else "core"
    out = os.path.abspath(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_DEFAULT
    os.makedirs(out, exist_ok=True)
    try: sys.stdout.reconfigure(line_buffering=True)
    except Exception: pass
    import traceback
    try:
        ok = stage_core(out) if stage == "core" else stage_road(out)
    except Exception:
        traceback.print_exc(); print("CORE_TEST FAIL stage %s: exception" % stage); ok = False
    print("CORE_TEST OK" if ok else "CORE_TEST FAIL")
    sys.stdout.flush()
    sys.exit(0 if ok else 1)


def _launch():
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--out", default=OUT_DEFAULT); p.add_argument("--no-road", action="store_true")
    a = p.parse_args()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    stages = [("core", [BLENDER, "--background", "--factory-startup", "--python", os.path.abspath(__file__), "--", "--stage", "core", "--out", out])]
    if os.path.exists(BASE) and not a.no_road:
        stages.append(("road", [BLENDER, "--background", BASE, "--python", os.path.abspath(__file__), "--", "--stage", "road", "--out", out]))
    else:
        print("CORE_TEST NOTE road stage skipped (%s)" % ("--no-road" if a.no_road else "no " + BASE))
    results = {}
    for name, cmd in stages:                      # strictly one Blender at a time
        t = time.time(); log = os.path.join(out, "stage_%s.log" % name)
        with open(log, "w", encoding="utf-8", errors="replace") as f:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            for line in proc.stdout:
                f.write(line)
                if line.startswith("CORE_TEST") or "Traceback" in line or "Error" in line[:80]: print(line.rstrip())
            proc.wait()
        results[name] = proc.returncode == 0
        print("stage %s: %s in %.0fs (log %s)" % (name, "passed" if results[name] else "FAILED (exit %s)" % proc.returncode, time.time() - t, log))
    ok = all(results.values())
    print("CORE_TEST OK" if ok else "CORE_TEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if IN_BLENDER: _blender_main()
    else: sys.exit(_launch())
