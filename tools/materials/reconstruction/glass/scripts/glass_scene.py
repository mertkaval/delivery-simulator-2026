"""Glass validation scenes (headless Blender; never the user's open Blender, nothing applied to the game).

    blender --background --factory-startup --python tools/materials/reconstruction/glass/scripts/glass_scene.py --
            --modes check,video,panel,road,bake,dump [--out DIR] [--samples 256] [--res 2560x1440]
            [--hdri courtyard] [--rotation 0] [--strength 0.5] [--denoise 1] [--materials PM_GlassCircles,...]
            [--set PM_GlassCircles:Glass_Roughness=0.3] [--tag name] [--hdri-test]

modes
  check  build procmat "glass", contract check, node / link counts                       -> <out>/check.json
  video  the tutorial scene (spec a/b "scene"): six 0.8 m planes (2 m plane, S 0.4, R X 90, scale applied -> object
         coordinates x, z in [-0.4, 0.4] m, y = 0, exactly as in the video) in a 3 x 2 grid (pitch 0.874 / 0.856 m,
         measured on the 33:23 camera frame), red Suzannes (#F40D00) behind the left / right columns, camera 50 mm at
         4.435 m (from the frame), Cycles, Filmic + Very High Contrast, film transparent, a bundled HDRI at 0.5 (D6)
         -> <out>/video_full<tag>.png (RGBA) and one crop per pane video_<material><tag>.png (on the viewport grey)
  panel  real-world check: a 1.2 m x 2 m glass panel at eye level (camera 1.7 m, 3 m away) in front of a textured
         wall, a red Suzanne and a blue pole                                              -> <out>/panel_<material>.png
  road   real-world check: rig.preview "road" view (7 m x 20 m strip, eye level 1.7 m), Cycles -> <out>/<material>_road.png
  bake   UV-mode tiles (core bake, 4 m / 1024 px and 1 m / 1024 px), seam metric, periodicity -> <out>/bake.json
  dump   graphdump of every glass material (interface, nodes, connections)               -> <out>/NODES_raw.md
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
MAT_DIR = os.path.join(ROOT, "tools", "materials")
if MAT_DIR not in sys.path: sys.path.insert(0, MAT_DIR)
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass

import bmesh  # noqa: E402
import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import procmat  # noqa: E402
from procmat import bake as BK, core, graphdump, imaging, rig  # noqa: E402

GLASS = ("PM_GlassCircles", "PM_GlassVoronoi", "PM_GlassCells", "PM_GlassWavy", "PM_GlassBlobby", "PM_GlassFrosted")
# video layout (spec a: Plane.002 Circles / Plane Voronoi / Plane.001 Cells on top; spec b: Wavy / Blobby / Frosted below;
# columns from the 33:23 frame, C): material -> (column -1 / 0 / 1, row 1 top / 0 bottom)
LAYOUT = {"PM_GlassCircles": (-1, 1), "PM_GlassVoronoi": (0, 1), "PM_GlassCells": (1, 1),
          "PM_GlassWavy": (-1, 0), "PM_GlassBlobby": (0, 0), "PM_GlassFrosted": (1, 0)}
PANE = 0.8                      # A: 2 m plane scaled 0.4
PITCH_X, PITCH_Z = 0.874, 0.856  # C: measured on the 33:23 camera frame (pane 228 px, pitch 249 / 244 px)
CAM_DIST = 4.435                # C: frame width 3.193 m at the panes with a 50 mm lens / 36 mm sensor
GRID_Z = 1.0                    # grid centre height (no ground in the video scene; the HDRI is at infinity)
RED = (0.9047, 0.0040, 0.0, 1.0)  # A: #F40D00 (Perceptual HSV 0.009 / 1 / 0.956) as scene-linear
VIEWPORT_GREY = (43, 43, 43)    # the viewport's transparent-film backdrop behind the panes (dark checker ~#2B2B2B)


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="glass_scene.py")
    p.add_argument("--modes", default="check")
    p.add_argument("--out", default=os.path.join(ROOT, "tools", "materials", "reconstruction", "glass", "renders"))
    p.add_argument("--samples", type=int, default=256)
    p.add_argument("--res", default="2560x1440")
    p.add_argument("--hdri", default="courtyard"); p.add_argument("--rotation", type=float, default=0.0)
    p.add_argument("--strength", type=float, default=0.5)
    p.add_argument("--denoise", type=int, default=1)
    p.add_argument("--materials", default=",".join(GLASS))
    p.add_argument("--set", action="append", default=[], help="MATERIAL:Input_Name=value (temporary input override)")
    p.add_argument("--tag", default="")
    p.add_argument("--hdri-test", action="store_true", help="video mode: render the full view for several HDRIs / rotations")
    p.add_argument("--hdri-list", default="courtyard:0,courtyard:90,courtyard:180,courtyard:270,city:0,city:90,city:180,city:270",
                   help="hdri:rotation pairs for --hdri-test")
    p.add_argument("--monkey", default="0.45,1.2,0.85,0.47,-0.58",
                   help="Suzanne scale, distance behind the panes (m), |x| (m), z of the top / bottom row monkeys relative to the "
                        "grid centre (m); C, fitted to the 25:26 and 33:23 frames (positions are class D in the video)")
    p.add_argument("--bake-out", default=os.path.join(ROOT, "tmp", "materials_bake", "glass"))
    return p.parse_args(argv)


def _rgba_png(sc):
    st = sc.render.image_settings; st.file_format = "PNG"; st.color_mode = "RGBA"; st.color_depth = "8"


def _view(sc, view="Filmic", look="Very High Contrast"):
    """The video's colour management (A): Filmic, Very High Contrast, exposure 0, gamma 1."""
    try: sc.view_settings.view_transform = view
    except TypeError as e: print("[glass] view transform %s: %s" % (view, e))
    try: sc.view_settings.look = look
    except TypeError as e: print("[glass] look %s: %s" % (look, e))
    sc.view_settings.exposure = 0.0; sc.view_settings.gamma = 1.0
    return sc.view_settings.view_transform, sc.view_settings.look


def _overrides(a):
    out = {}
    for s in a.set:
        m, kv = s.split(":", 1); k, v = kv.split("=", 1)
        out.setdefault(m, {})[k] = float(v) if "," not in v else tuple(float(x) for x in v.split(","))
    return out


def _apply_overrides(ov):
    saved = []
    for m, vals in ov.items():
        node = core.group_node(m)
        for k, v in vals.items():
            k2 = core._key(node.inputs, k)
            if k2 not in node.inputs: print("[glass] %s has no input %s" % (m, k)); continue
            d = node.inputs[k2].default_value
            saved.append((node, k2, tuple(d) if hasattr(d, "__len__") else d))
        miss = core.set_inputs(node, **vals)
        if miss: print("[glass] unknown inputs", m, miss)
    return saved


def _restore(saved):
    for node, k, v in saved: node.inputs[k].default_value = v


# ======================================================================================== objects
def _mesh(sc, col, name, bm, location=(0, 0, 0)):
    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data; bpy.data.objects.remove(old)
        if me is not None and me.users == 0: bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.location = location; col.objects.link(ob)
    return ob


def video_pane(sc, col, name, location):
    """The video's pane: a 2 m plane, S 0.4, R X 90, Ctrl+A rotation & scale -> vertices (+-0.4, 0, +-0.4), normal -Y,
    object scale 1, UVs 0..1 (u along x, v along z). Its object coordinates are the video's."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    h = PANE / 2.0
    vs = [bm.verts.new(p) for p in ((-h, 0.0, -h), (h, 0.0, -h), (h, 0.0, h), (-h, 0.0, h))]
    f = bm.faces.new(vs)
    for lp, uv in zip(f.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))): lp[uvl].uv = uv
    bm.normal_update()
    if f.normal.y > 0: f.normal_flip()
    return _mesh(sc, col, name, bm, location)


def red_material():
    m = bpy.data.materials.get("PMV_Red") or bpy.data.materials.new("PMV_Red")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = RED
    return m


def suzanne(sc, col, name, location, scale):
    bm = bmesh.new(); bmesh.ops.create_monkey(bm)
    for v in bm.verts: v.co *= scale
    for f in bm.faces: f.smooth = True
    ob = _mesh(sc, col, name, bm, location)
    ob.data.materials.append(red_material())
    return ob


def _camera(sc, col, name, location, rot_deg, lens):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); col.objects.link(cam)
    cam.data.lens = lens; cam.data.sensor_width = 36.0; cam.data.sensor_fit = "AUTO"
    cam.data.clip_start = 0.1; cam.data.clip_end = 1000.0; cam.data.type = "PERSP"
    cam.location = location; cam.rotation_euler = tuple(math.radians(r) for r in rot_deg)
    sc.camera = cam
    return cam


def _new_scene(name, a, res, samples, hdri, strength, rotation):
    sc = rig.scene(name, "CYCLES", samples, res, True, "Filmic", hdri, strength, rotation)
    sc.cycles.use_denoising = bool(a.denoise)
    sc.render.film_transparent = True
    try: sc.cycles.film_transparent_glass = False          # glass shows the HDRI behind it, as in the video
    except AttributeError: pass
    sc.render.filter_size = 1.5                            # A: Blackman-Harris 1.5 px (Cycles default)
    vt = _view(sc)
    _rgba_png(sc)
    col = bpy.data.collections.get(name + "_Objects") or bpy.data.collections.new(name + "_Objects")
    if col.name not in sc.collection.children: sc.collection.children.link(col)
    return sc, col, vt


def _project_box(sc, cam, ob):
    """Pixel box (x0, y0, x1, y1), top-left origin, of an object's bounding box in the render."""
    sc.view_layers[0].update()
    rx, ry = sc.render.resolution_x, sc.render.resolution_y
    M = ob.matrix_world
    pts = [world_to_camera_view(sc, cam, M @ Vector(c)) for c in ob.bound_box]
    xs = [p.x * rx for p in pts]; ys = [(1.0 - p.y) * ry for p in pts]
    return [int(round(min(xs))), int(round(min(ys))), int(round(max(xs))), int(round(max(ys)))]


# ======================================================================================== modes
def mode_check(a, mats, out):
    rep = {}
    for m in mats:
        g = core.group_node(m).node_tree
        nodes = [n for n in g.nodes if n.bl_idname not in ("NodeFrame",)]
        rep[m.name] = {"contract": core.check_contract(m) or "OK", "group": g.name, "nodes": len(nodes),
                       "frames": len([n for n in g.nodes if n.bl_idname == "NodeFrame"]), "links": len(g.links),
                       "inputs": core.input_names(g), "outputs": core.output_names(g),
                       "video_group": m.get("pm_video_group"), "settings": {k: getattr(m, k, None) for k in
                                                                            ("surface_render_method", "use_raytrace_refraction", "displacement_method")}}
        print("[check] %-18s %s nodes %d links %d" % (m.name, rep[m.name]["contract"], len(nodes), len(g.links)))
    with open(os.path.join(out, "check.json"), "w", encoding="utf-8") as f: json.dump(rep, f, indent=1, default=str)
    return all(v["contract"] == "OK" for v in rep.values())


def build_video_scene(a, mats, res, samples, hdri, strength, rotation):
    sc, col, vt = _new_scene("PMV_Video", a, res, samples, hdri, strength, rotation)
    ms, md, mx, mzt, mzb = (float(x) for x in a.monkey.split(","))
    panes = {}
    for m in mats:
        cx, row = LAYOUT[m.name]
        loc = (cx * PITCH_X, 0.0, GRID_Z + (PITCH_Z / 2.0 if row else -PITCH_Z / 2.0))
        ob = video_pane(sc, col, "PMV_" + m.name[3:], loc); ob.data.materials.append(m)
        panes[m.name] = ob
    for row in (0, 1):
        for cx in (-1, 1):
            suzanne(sc, col, "PMV_Suzanne_%d_%d" % (row, cx), (cx * mx, md, GRID_Z + (mzt if row else mzb)), ms)
    cam = _camera(sc, col, "PMV_Camera", (0.0, -CAM_DIST, GRID_Z), (90.0, 0.0, 0.0), 50.0)
    return sc, col, cam, panes, vt


def _flatten(src, dst, bg=VIEWPORT_GREY, box=None):
    """RGBA render -> RGB on the viewport grey (optionally a crop box). numpy only (inside Blender)."""
    import numpy as np
    A = imaging.load(src)
    if box is not None:
        x0, y0, x1, y1 = box; A = A[max(0, y0):y1, max(0, x0):x1]
    rgb = A[..., :3]; al = A[..., 3:4] if A.shape[2] > 3 else np.ones_like(A[..., :1])
    out = rgb * al + (np.array(bg, dtype=np.float32) / 255.0) * (1.0 - al)   # PNG stores straight alpha
    return imaging.save(out, dst)


def mode_video(a, mats, out):
    rx, ry = (int(x) for x in a.res.lower().split("x"))
    runs = [(a.hdri, a.rotation)]
    if a.hdri_test:
        runs = [(x.split(":")[0], float(x.split(":")[1])) for x in a.hdri_list.split(",") if x.strip()]
    res = {}
    for hdri, rot in runs:
        sc, col, cam, panes, vt = build_video_scene(a, mats, (rx, ry), a.samples, hdri, a.strength, rot)
        tag = a.tag + ("_%s%d" % (hdri, int(rot)) if a.hdri_test else "")
        t = time.time()
        full = rig.render(os.path.join(out, "video_full%s.png" % tag), scene=sc)
        dt = time.time() - t
        boxes = {m: _project_box(sc, cam, ob) for m, ob in panes.items()}
        _flatten(full, os.path.join(out, "video_full%s_grey.png" % tag))
        if not a.hdri_test:
            for m, box in boxes.items():
                _flatten(full, os.path.join(out, "video_%s%s.png" % (m[3:], tag)), box=box)
        res[tag or "default"] = {"file": full, "seconds": round(dt, 1), "hdri": hdri, "rotation": rot, "strength": a.strength,
                                 "view": vt, "samples": a.samples, "res": [rx, ry], "pane_boxes": boxes,
                                 "gpu": bool(sc.get("pm_gpu")), "denoise": bool(a.denoise)}
        print("[video] %s %.1fs %s" % (os.path.basename(full), dt, json.dumps(boxes)))
    with open(os.path.join(out, "video%s.json" % a.tag), "w", encoding="utf-8") as f: json.dump(res, f, indent=1)
    return True


def _wall_material():
    """A textured wall for the panel check: coloured bricks with a white poster band and black text-like bars."""
    m = bpy.data.materials.get("PMV_Wall") or bpy.data.materials.new("PMV_Wall")
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 4.0
    br.inputs["Color1"].default_value = (0.55, 0.12, 0.05, 1); br.inputs["Color2"].default_value = (0.75, 0.55, 0.25, 1)
    br.inputs["Mortar"].default_value = (0.7, 0.7, 0.68, 1); br.inputs["Mortar Size"].default_value = 0.03
    ck = nt.nodes.new("ShaderNodeTexChecker"); ck.inputs["Scale"].default_value = 12.0
    ck.inputs["Color1"].default_value = (0.9, 0.9, 0.9, 1); ck.inputs["Color2"].default_value = (0.02, 0.02, 0.02, 1)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mask = nt.nodes.new("ShaderNodeMath"); mask.operation = "COMPARE"; mask.inputs[1].default_value = 1.6; mask.inputs[2].default_value = 0.35
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"]); nt.links.new(tc.outputs["Object"], ck.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], mask.inputs[0])
    nt.links.new(mask.outputs[0], mix.inputs["Factor"]); nt.links.new(br.outputs["Color"], mix.inputs["A"])
    nt.links.new(ck.outputs["Color"], mix.inputs["B"]); nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return m


def mode_panel(a, mats, out):
    sc, col, vt = _new_scene("PMV_Panel", a, (1280, 960), a.samples, "city", 1.0, 0.0)
    sc.render.film_transparent = False
    _rgba_png(sc); sc.render.image_settings.color_mode = "RGB"
    _view(sc, "AgX", "None")
    # ground, wall, props
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6.0)
    g = _mesh(sc, col, "PMV_Ground", bm, (0, 0, 0))
    gm = bpy.data.materials.get("PMV_Ground") or bpy.data.materials.new("PMV_Ground"); gm.use_nodes = True
    next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.18, 0.18, 0.18, 1)
    g.data.materials.append(gm)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=2.0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.radians(90), 3, "X"))
    for v in bm.verts: v.co.z += 2.0
    w = _mesh(sc, col, "PMV_Wall", bm, (0.0, 1.2, 0.0)); w.scale = (1.6, 1.0, 1.0); w.data.materials.append(_wall_material())
    suzanne(sc, col, "PMV_PanelSuzanne", (-0.25, 0.55, 1.55), 0.22)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.05, radius2=0.05, depth=2.4)
    pole = _mesh(sc, col, "PMV_Pole", bm, (0.35, 0.6, 1.2))
    pm = bpy.data.materials.get("PMV_Blue") or bpy.data.materials.new("PMV_Blue"); pm.use_nodes = True
    next(n for n in pm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.02, 0.12, 0.6, 1)
    pole.data.materials.append(pm)
    pane = rig.pane(sc, width=1.2, height=2.0, location=(0.0, 0.0, 0.25), name="PMV_GlassPanel")
    for o in list(pane.users_collection): o.objects.unlink(pane)
    col.objects.link(pane)
    cam = _camera(sc, col, "PMV_PanelCam", (0.0, -3.0, 1.7), (90.0 - math.degrees(math.atan2(1.7 - 1.25, 3.0)), 0.0, 0.0), 35.0)
    res = {}
    pane.data.materials.clear(); pane.hide_render = True
    p = rig.render(os.path.join(out, "panel_none.png"), scene=sc); res["none"] = p
    pane.hide_render = False
    for m in mats:
        pane.data.materials.clear(); pane.data.materials.append(m)
        t = time.time(); p = rig.render(os.path.join(out, "panel_%s.png" % m.name[3:]), scene=sc)
        res[m.name] = {"file": p, "seconds": round(time.time() - t, 1)}
        print("[panel]", os.path.basename(p), res[m.name]["seconds"])
    with open(os.path.join(out, "panel.json"), "w", encoding="utf-8") as f: json.dump(res, f, indent=1)
    return True


def mode_road(a, mats, out):
    res = {}
    for m in mats:
        t = time.time()
        r = rig.preview(m, out, views=("road",), engine="CYCLES", res=960, samples=min(a.samples, 128), hdri="city", strength=1.0)
        res[m.name] = {"file": r["road"], "seconds": round(time.time() - t, 1)}
        print("[road]", os.path.basename(r["road"]), res[m.name]["seconds"])
    with open(os.path.join(out, "road.json"), "w", encoding="utf-8") as f: json.dump(res, f, indent=1)
    return True


def mode_bake(a, mats, out):
    import numpy as np
    bout = os.path.abspath(a.bake_out); os.makedirs(bout, exist_ok=True)
    res = {}
    good = True
    for m in mats:
        res[m.name] = {}
        for tile in (4.0, 1.0):
            d = os.path.join(bout, "tile%gm" % tile)
            t = time.time()
            paths = BK.bake(m, d, tile=tile, res=1024, samples=16)
            entry = {"seconds": round(time.time() - t, 1), "files": {k: os.path.relpath(v, ROOT).replace("\\", "/") for k, v in paths.items()}}
            for k, p in paths.items():
                arr = imaging.load(p)[..., :3]
                st = {"mean": round(float(arr.mean()), 4), "std": round(float(arr.std()), 5)}
                if st["std"] > 1e-4:
                    sm = BK.seam_metric(p); st["seam"] = sm; st["seamless"] = bool(BK.is_seamless(sm))
                else:
                    st["seam"] = "constant map (no variation): seamless trivially"; st["seamless"] = True
                entry[k] = st
                if k in ("normal", "roughness"): BK.tile_preview(p, 2)
            res[m.name]["tile%gm" % tile] = entry
            print("[bake] %s tile %g m %.1fs %s" % (m.name, tile, entry["seconds"],
                                                   {k: (v.get("seam", {}).get("ratio") if isinstance(v.get("seam"), dict) else "const")
                                                    for k, v in entry.items() if isinstance(v, dict) and "mean" in v}))
        maps = ("normal",) if m.name != "PM_GlassFrosted" else ("roughness",)
        pr = BK.periodicity(m, os.path.join(bout, "periodicity"), tile=4.0, res=512, samples=16, maps=maps)
        ok = BK.is_periodic(pr)
        res[m.name]["periodicity"] = {k: {kk: vv for kk, vv in v.items() if kk != "files"} for k, v in pr.items()}
        res[m.name]["periodic"] = bool(ok); good &= bool(ok)
        print("[bake] periodicity %s %s %s" % (m.name, "OK" if ok else "FAIL", json.dumps(res[m.name]["periodicity"])))
    with open(os.path.join(out, "bake.json"), "w", encoding="utf-8") as f: json.dump(res, f, indent=1)
    return good


def mode_dump(a, mats, out):
    parts = []
    for m in mats:
        parts.append(graphdump.dump(m))
    p = os.path.join(out, "NODES_raw.md")
    with open(p, "w", encoding="utf-8") as f: f.write("\n\n".join(parts))
    print("[dump]", p)
    return True


def main():
    a = _args()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    print("[glass] modules", json.dumps(procmat.discover(["glass"])))
    t = time.time()
    built = procmat.build("glass")
    print("[glass] built %d materials in %.1fs" % (len(built), time.time() - t))
    want = [x.strip() for x in a.materials.split(",") if x.strip()]
    mats = [bpy.data.materials[n] for n in want]
    saved = _apply_overrides(_overrides(a))
    ok = True
    try:
        for mode in [x.strip() for x in a.modes.split(",") if x.strip()]:
            t = time.time()
            r = {"check": mode_check, "video": mode_video, "panel": mode_panel, "road": mode_road, "bake": mode_bake,
                 "dump": mode_dump}[mode](a, mats, out)
            print("[glass] mode %s %s %.1fs" % (mode, "OK" if r else "FAIL", time.time() - t))
            ok &= bool(r)
    finally:
        _restore(saved)
    return ok


if __name__ == "__main__":
    import traceback
    try:
        good = main()
    except Exception:
        traceback.print_exc(); good = False
    print("GLASS RUN OK" if good else "GLASS RUN FAIL")
    sys.stdout.flush()
    sys.exit(0 if good else 1)
