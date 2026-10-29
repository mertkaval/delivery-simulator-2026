"""Import the landscape-kit trees into the MRS library and render close-ups (Blender side of the
Blender/Godot tree comparison).  blender -b --factory-startup --python tools/roads/tests/game_trees_test.py"""
import bpy, sys, os, time, math, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
OUT = os.path.join(ROOT, "tmp", "roads", "v4", "trees"); os.makedirs(OUT, exist_ok=True)
try:
    from mrs import game_trees as gt, qa
    t0 = time.time(); gt.build_game_trees(); print("IMPORT %.1fs" % (time.time() - t0))
    for k, (n, m) in sorted(gt.tri_counts().items()): print("  %-34s tris %6d mats %d" % (k, n, m))
    for o in bpy.data.collections[gt.TREE_COL].objects:
        if not o.get("mrs_lod"): print("  %-26s h %.1f crown %.1f reach %.1f base %.1f trunk %.2f" % (o.name, o["mrs_tree_height"], o["mrs_crown_radius"], o["mrs_crown_reach"], o["mrs_crown_base"], o["mrs_trunk_radius"]))
    for o in bpy.data.collections[gt.PLANT_COL].objects: print("  plant %-24s h %.2f size %s" % (o.name, o["mrs_height"], [round(x, 2) for x in o["mrs_size"]]))
    sc = bpy.context.scene
    stage = bpy.data.collections.new("TreeStage"); sc.collection.children.link(stage)
    me = bpy.data.meshes.new("g"); me.from_pydata([(-200, -200, 0), (200, -200, 0), (200, 200, 0), (-200, 200, 0)], [], [(0, 1, 2, 3)])
    gm = bpy.data.materials.new("grass"); gm.use_nodes = True; next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.13, 0.2, 0.07, 1); me.materials.append(gm)
    stage.objects.link(bpy.data.objects.new("g", me))
    x = 0.0
    for sid in ("plane_tree", "linden_a", "linden_b", "maple_a", "cherry", "walnut_spring", "grove_a"):
        src = bpy.data.objects["MRS_GTree_" + sid]; c = bpy.data.objects.new("T_" + sid, src.data); stage.objects.link(c); c.location = (x, 0, 0); c.hide_render = False
        l1 = bpy.data.objects.get("MRS_GTree_" + sid + "_LOD1")
        if l1: c2 = bpy.data.objects.new("T1_" + sid, l1.data); stage.objects.link(c2); c2.location = (x, 22, 0)
        x += 13.0
    qa.render(os.path.join(OUT, "blender_row.png"), (39, -48, 6), (39, 0, 6), 35, scene=sc, samples=32)
    qa.render(os.path.join(OUT, "blender_lod1_row.png"), (39, -26, 6), (39, 22, 6), 35, scene=sc, samples=32)
    qa.render(os.path.join(OUT, "blender_close_linden.png"), (13 + 6, -9, 1.7), (13, 0, 4.5), 32, scene=sc, samples=48)
    qa.render(os.path.join(OUT, "blender_close_base.png"), (2.2, -2.6, 1.2), (0, 0, 0.6), 35, scene=sc, samples=32)
    print("TREES OK")
except Exception:
    traceback.print_exc(); print("TREES FAILED")
