"""Movement-path check on a saved block (no rebuild):
    blender -b --factory-startup <block.blend> --python tools/roads/tests/movements_test.py [-- --render]"""
import bpy, sys, os, json, time, traceback
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.join(ROOT, "tmp", "roads", "v5", "movements"); os.makedirs(OUT, exist_ok=True)
try:
    import mrs
    from mrs import movements as MV, routes as RT, qa
    sc = bpy.data.scenes["MRS_StreetBlock"]; mrs.nodes.set_scene(sc)
    col = bpy.data.collections["MRS_StreetBlock_Roads"]
    rt = json.loads(sc["mrs_routes"])
    t0 = time.time(); mv = MV.build(col, rt); print("MOVEMENTS %.1fs" % (time.time() - t0), mv["stats"])
    for v in mv["validation"][:30]: print("  ", v)
    json.dump({"movements": mv, "routes": rt}, open(os.path.join(OUT, "movements.json"), "w"), indent=1)
    if "--render" in args:
        import bmesh
        from mrs.props import mat
        bm = bmesh.new()
        def ribbon(pts, w, mi, lift=0.35):
            P = [Vector(p) + Vector((0, 0, lift)) for p in pts]
            for a, b in zip(P, P[1:]):
                d = b - a; d.z = 0
                if d.length < 1e-4: continue
                s = Vector((-d.y, d.x, 0)).normalized() * w
                f = bm.faces.new([bm.verts.new(q) for q in (a - s, b - s, b + s, a + s)]); f.material_index = mi
        mats = [mat("MV_Car", (1.0, 0.85, 0.1)), mat("MV_Bike", (0.1, 0.45, 1.0)), mat("MV_Ped", (0.1, 0.9, 0.2)), mat("MV_Bad", (1.0, 0.0, 0.0))]
        for m_ in mats:
            b = next(n for n in m_.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); b.inputs["Emission Color"].default_value = m_.diffuse_color; b.inputs["Emission Strength"].default_value = 3.0
        for m_ in mv["movements"]: ribbon(m_["points"], 0.12, 0 if m_["clearance_ok"] else 3)
        for l in mv["lanes"]: ribbon(l["points"], 0.06, 0)
        for m_ in mv["bike_movements"]: ribbon(m_["points"], 0.1, 1 if m_["clearance_ok"] else 3)
        for e in rt["ped"]["edges"]: ribbon(e["points"], 0.1, 2 if e.get("walk_ok", True) else 3)
        me = bpy.data.meshes.new("MV"); bm.to_mesh(me); bm.free()
        for m_ in mats: me.materials.append(m_)
        o = bpy.data.objects.new("MV_Debug", me); col.objects.link(o); o["mrs_debug"] = 1
        qa.render(os.path.join(OUT, "movements_j4.png"), (0, -30, 75), (0, 0, 0), 32, scene=sc, samples=12, res=(1600, 1200))
        qa.render(os.path.join(OUT, "movements_jt.png"), (120, -30, 70), (120, -2, 0), 32, scene=sc, samples=12, res=(1600, 1200))
        bpy.data.objects.remove(o)
    print("MOVEMENTS_TEST OK")
except Exception:
    traceback.print_exc(); print("MOVEMENTS_TEST FAILED")
