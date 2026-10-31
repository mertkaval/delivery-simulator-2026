"""procmat x Mert Road Studio integration test (headless; never the user's open Blender; base.blend is never saved).

    blender --background tmp/roads/city/base.blend --python tools/materials/tests/road_integration.py -- <out_dir>
            [--res 1280x720] [--samples 48] [--glass PM_GlassFrosted] [--cobbled SB_TSide]

1. procmat.build_all() builds every PM_* material (asphalt, cobblestone, glass) in the road tool's library file.
2. The road tool's own sample code (tools/roads/mrs/samples.py street_block(): avenue, residential streets, junctions,
   sidewalks, placement v4 with a furnished bus stop) builds the street scene. The road tool is imported read-only
   (no .pyc written under tools/roads) and is not modified.
3. procmat.road_adapter assigns PM_Asphalt to every road's Asphalt Material and PM_Cobblestone to its Paving Material
   (menus Asphalt Condition / Sidewalk Surface -> Default), then the cobbled variant: PM_Cobblestone as the Asphalt
   Material of one road. Junction meshes are plain mesh objects with MRS_* slots (no modifier input): their asphalt /
   paving slots are replaced with replace_slot_materials (per object). The placed bus shelters (mrs_kind "shelter")
   get the glass material on their MRS_FurnitureGlass slot (per object: the furniture library mesh is unchanged).
4. Checks on the EVALUATED meshes (what renders): every road's evaluated mesh carries PM_Asphalt and (with sidewalks)
   PM_Cobblestone; the cobbled road carries PM_Cobblestone on its carriageway and no PM_Asphalt; junction and shelter
   evaluated objects carry the PM materials; every PM material passes the contract check.
5. EEVEE renders (scene world from the road tool's day setup): eye level and 45 degrees at the bus stop, eye level and
   45 degrees on the cobbled road, a close-up of the shelter glass -> tools/materials/renders/road_*.png; image stats
   (a flat / black render fails).
Every check prints "ROAD_INTEGRATION OK <check>: <data>" or "ROAD_INTEGRATION FAIL <check>: <data>"; the last line is
"ROAD_INTEGRATION OK" or "ROAD_INTEGRATION FAIL"; <out_dir>/road_integration.json holds the measurements.
"""
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
MAT_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(MAT_DIR))
RENDERS = os.path.join(MAT_DIR, "renders")

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass


class Tester:
    def __init__(self):
        self.results = []

    def check(self, name, ok, data=None):
        ok = bool(ok)
        self.results.append({"check": name, "ok": ok, "data": data})
        print("ROAD_INTEGRATION %s %s: %s" % ("OK" if ok else "FAIL", name, json.dumps(data, default=str)[:1500]))
        return ok

    @property
    def ok(self):
        return all(r["ok"] for r in self.results)


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0]) if argv and not argv[0].startswith("--") else os.path.join(ROOT, "tmp", "materials_road")
    opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
    w, h = (int(v) for v in opt("--res", "1280x720").split("x"))
    return out, (w, h), int(opt("--samples", "48")), opt("--glass", "PM_GlassFrosted"), opt("--cobbled", "SB_TSide")


def _eval_slot_materials(obj, dg):
    """{material: face count} of an evaluated mesh object, with object-linked slots resolved (what renders)."""
    ev = obj.evaluated_get(dg)
    slot_mats = [s.material.name if s.material else None for s in ev.material_slots]
    me = ev.to_mesh()
    try:
        idx = [0] * len(me.polygons); me.polygons.foreach_get("material_index", idx)
        mats = slot_mats or [m.name if m else None for m in me.materials]
        out = {}
        for i in idx:
            if 0 <= i < len(mats) and mats[i]: out[mats[i]] = out.get(mats[i], 0) + 1
        return out
    finally:
        ev.to_mesh_clear()


def _cam(sc, col, name, eye, target, lens):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); col.objects.link(cam)
    cam.data.lens = lens; cam.data.clip_start = 0.05; cam.data.clip_end = 3000.0
    from procmat import rig
    rig.look_at(cam, eye, target); sc.camera = cam
    return cam


def main():
    out, res, samples, glass_name, cobbled_name = _args()
    os.makedirs(out, exist_ok=True); os.makedirs(RENDERS, exist_ok=True)
    T = Tester(); t0 = time.time(); rec = {"renders": {}}
    T.check("road tool library opened (base.blend, MRS_Road group present)",
            bpy.data.filepath.replace("\\", "/").endswith("tmp/roads/city/base.blend") and "MRS_Road" in bpy.data.node_groups,
            {"file": bpy.data.filepath})

    # ---- the road tool's own sample code builds the street block (read-only import)
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
    from mrs import samples, structures
    t = time.time()
    sc = samples.street_block()
    col = bpy.data.collections["MRS_StreetBlock_Roads"]
    print("[road_integration] street_block built in %.0fs" % (time.time() - t))

    # ---- the library materials (after the street block: its material preset only touches MRS_* materials)
    sys.path.insert(0, MAT_DIR)
    import procmat
    from procmat import core, imaging, rig, road_adapter as RA
    built = procmat.build_all()
    mats = {m.name: m for ms in built.values() for m in ms}
    probs = {n: core.check_contract(m) for n, m in mats.items()}
    T.check("procmat.build_all: every PM material built and passes the contract", len(mats) >= 10 and not any(probs.values()),
            {"built": {k: [m.name for m in v] for k, v in built.items()}, "problems": {k: v for k, v in probs.items() if v}})
    asphalt = mats["PM_Asphalt"]; cobble = mats["PM_Cobblestone"]; glass = mats[glass_name]

    road_objs = RA.roads(col)
    T.check("street block has roads with the MRS_Road modifier", len(road_objs) >= 4, [o.name for o in road_objs])
    vl = sc.view_layers[0]; vl.update(); dg = vl.depsgraph
    before = {o.name: RA.evaluated_materials(o, dg) for o in road_objs}

    # ---- assign through the adapter
    reps = RA.assign_roads(col, {"Asphalt Material": asphalt, "Paving Material": cobble})
    cobbled = bpy.data.objects[cobbled_name]
    rep_c = RA.assign(cobbled, "Asphalt Material", cobble)
    rec["assign"] = reps + [rep_c]
    # junctions: mesh objects with MRS_* slots (no modifier input) -> slot replacement per object
    junctions = [o for o in col.all_objects if o.type == "MESH" and any(s.material and s.material.name.startswith("MRS_Asphalt") for s in o.material_slots)]
    jrep = {}
    for j in junctions:
        r = RA.replace_slot_materials(j, "MRS_Asphalt", asphalt, per_object=True)
        r += RA.replace_slot_materials(j, "MRS_Paving", cobble, per_object=True)
        jrep[j.name] = r
    rec["junction_slots"] = jrep
    # bus shelters placed by the road tool's placement (shared library mesh -> per-object slot)
    shelters = [o for o in col.all_objects if o.type == "MESH" and (o.get("mrs_kind") == "shelter" or "BusShelter" in str(o.get("mrs_placed", "")))]
    srep = {o.name: RA.replace_slot_materials(o, "FurnitureGlass", glass, per_object=True) + RA.replace_slot_materials(o, "PropGlass", glass, per_object=True) for o in shelters}
    rec["shelter_slots"] = srep
    T.check("assign_roads + assign: every road set (menus -> Default), cobbled variant on %s" % cobbled_name,
            len(reps) == 2 * len(road_objs) and all(r["menu"] is None or r["menu"][2] == "Default" for r in reps + [rep_c]),
            {"reports": len(reps), "roads": len(road_objs), "cobbled": rep_c})

    # ---- evaluated meshes
    vl.update(); dg = vl.depsgraph
    after = {o.name: RA.evaluated_materials(o, dg) for o in road_objs}
    rec["evaluated_roads"] = {"before": before, "after": after}
    bad = []
    for o in road_objs:
        ev = after[o.name]
        has_sw = bool(RA.get_input(RA.road_modifier(o), "Sidewalk Left") or RA.get_input(RA.road_modifier(o), "Sidewalk Right")) \
            if "Sidewalk Left" in [i.name for i in RA.road_modifier(o).node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT"] else True
        if o is cobbled:
            if not (ev.get("PM_Cobblestone", 0) > 0 and ev.get("PM_Asphalt", 0) == 0): bad.append((o.name, "cobbled", ev))
        else:
            if ev.get("PM_Asphalt", 0) <= 0: bad.append((o.name, "no PM_Asphalt", ev))
            if has_sw and ev.get("PM_Cobblestone", 0) <= 0: bad.append((o.name, "no PM_Cobblestone sidewalk", ev))
        if any(k.startswith("MRS_Asphalt") or k.startswith("MRS_Paving") for k in ev): bad.append((o.name, "MRS asphalt / paving left", ev))
    T.check("evaluated road meshes carry PM_Asphalt (carriageway) and PM_Cobblestone (sidewalks); cobbled road has no PM_Asphalt",
            not bad, {"bad": bad, "after": after})
    jev = {j.name: _eval_slot_materials(j, dg) for j in junctions}
    rec["evaluated_junctions"] = jev
    T.check("evaluated junction meshes carry PM_Asphalt and no MRS asphalt",
            junctions and all(v.get("PM_Asphalt", 0) > 0 and not any(k.startswith("MRS_Asphalt") for k in v) for v in jev.values()), jev)
    sev = {s.name: _eval_slot_materials(s, dg) for s in shelters}
    rec["evaluated_shelters"] = sev
    T.check("placed bus shelter(s) render %s on the glass slot (library mesh unchanged)" % glass.name,
            shelters and all(v.get(glass.name, 0) > 0 and "MRS_FurnitureGlass" not in v for v in sev.values())
            and all(any(m and m.name == "MRS_FurnitureGlass" for m in o.data.materials) for o in shelters),
            {"shelters": sev, "slots": srep, "library_mesh_slots": sorted({m.name for o in shelters for m in o.data.materials if m})})
    used = set()
    for d in list(after.values()) + list(jev.values()) + list(sev.values()): used |= set(d)
    T.check("PM materials really used by the evaluated scene", {"PM_Asphalt", "PM_Cobblestone", glass.name} <= used, sorted(k for k in used if k.startswith("PM_")))

    # ---- renders (EEVEE, the road tool's day lighting; bundled HDRI when the scene has no world)
    if sc.world is None: rig.world(sc, "city", 1.0, 0.0)
    rig.set_engine(sc, "EEVEE", samples)
    sc.render.resolution_x, sc.render.resolution_y = res
    shelter = shelters[0] if shelters else None
    shots = []
    if shelter is not None:
        road = bpy.data.objects[shelter.get("mrs_road", "SB_South")] if shelter.get("mrs_road") in bpy.data.objects else bpy.data.objects["SB_South"]
        sp = shelter.matrix_world.translation.copy()
        # nearest station on the road to the shelter
        L = structures.road_length(road); best = min((((structures.road_sample(road, a)[0] - sp).xy.length, a) for a in [i * 1.0 for i in range(int(L) + 1)]))
        a_sh = best[1]; p, tg, rr = structures.road_sample(road, a_sh)
        side = 1.0 if (sp - p).dot(rr) > 0 else -1.0
        back = -1.0 if a_sh > 25.0 else 1.0
        pe, _, _ = structures.road_sample(road, a_sh + back * 22.0)
        shots.append(("road_eye_busstop", pe + rr * side * 1.8 + Vector((0, 0, 1.7)), sp + Vector((0, 0, 1.0)) - rr * side * 1.5, 28.0))
        mid = (p + sp) / 2.0
        shots.append(("road_45_busstop", mid - tg * back * 14.0 - rr * side * 9.0 + Vector((0, 0, 16.0)), mid, 30.0))
        shots.append(("road_glass_closeup", sp - rr * side * 4.2 + tg * back * 1.5 + Vector((0, 0, 1.5)), sp + Vector((0, 0, 1.2)), 35.0))
    Lc = structures.road_length(cobbled)
    pc, tc, rc = structures.road_sample(cobbled, Lc * 0.35)
    pt, _, _ = structures.road_sample(cobbled, Lc * 0.75)
    shots.append(("road_eye_cobbled", pc + rc * 1.6 + Vector((0, 0, 1.7)), pt + Vector((0, 0, 0.3)), 28.0))
    pm, _, _ = structures.road_sample(cobbled, Lc * 0.55)
    shots.append(("road_45_cobbled", pm - tc * 16.0 + rc * 12.0 + Vector((0, 0, 18.0)), pm, 30.0))
    p0, t0_, r0 = structures.road_sample(bpy.data.objects["SB_AvenueW"], 60.0)
    p1, _, _ = structures.road_sample(bpy.data.objects["SB_AvenueW"], 110.0)
    shots.append(("road_eye_avenue", p0 + r0 * 2.0 + Vector((0, 0, 1.7)), p1 + Vector((0, 0, 0.5)), 28.0))
    for name, eye, target, lens in shots:
        _cam(sc, col, "PMI_Camera", eye, target, lens)
        path = os.path.join(RENDERS, name + ".png")
        t = time.time(); rig.render(path, scene=sc)
        s = imaging.stats(path)
        rec["renders"][name] = dict(s, path=path, seconds=round(time.time() - t, 1), eye=tuple(round(v, 2) for v in eye), target=tuple(round(v, 2) for v in target))
        T.check("render %s (not flat / black)" % name, s["std"] > 0.02 and s["mean"] > 0.03, rec["renders"][name])
    rec["results"] = T.results; rec["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(out, "road_integration.json"), "w", encoding="utf-8") as f: json.dump(rec, f, indent=1, default=str)
    return T.ok


if __name__ == "__main__":
    try:
        good = main()
    except Exception:
        traceback.print_exc(); good = False
    print("ROAD_INTEGRATION OK" if good else "ROAD_INTEGRATION FAIL")
    sys.stdout.flush()
    sys.exit(0 if good else 1)
