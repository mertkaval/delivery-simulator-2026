"""CRM_Reconstruction_groups.blend: the reconstruction's node groups with one working example of each, in a small file
that opens in a fresh Blender (no MRS library needed; the full scene with MRS roads is reconstruct.py's output).
    blender --background --factory-startup --python tools/roads/crm_reconstruction/build/light_blend.py
Scene "CRM_Groups": four tongue footprints + a square extension (bus bay) + a curve extension + an area junction;
a round extension with an island + a junction (roundabout); the CRM 2.1 and stop signs; bay lines with an Array."""
import bpy, bmesh, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RECON = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(RECON)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
from mrs import areajunction as AJ, customsign as CS, markinglines as ML
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
AJ.build_all(); CS.build_custom_sign(); ML.build_marking_lines()
sc = bpy.context.scene; sc.name = "CRM_Groups"
roads = bpy.data.collections.new("Roads"); sc.collection.children.link(roads)
juncs = bpy.data.collections.new("Junctions"); sc.collection.children.link(juncs)
signs = bpy.data.collections.new("Signs"); sc.collection.children.link(signs)
for name, rgb in (("MRS_Asphalt", (0.09, 0.09, 0.1)), ("MRS_Paving", (0.5, 0.49, 0.46)), ("MRS_Concrete", (0.6, 0.6, 0.58))):
    m = bpy.data.materials.get(name)
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m and m.use_nodes else None
    if b: b.inputs["Base Color"].default_value = rgb + (1.0,)
    if m: m.diffuse_color = rgb + (1.0,)


def tongue(name, start, d, length=10.0, road=8.0, side=2.0, z=1.0):
    """A footprint like MRS_Road's tongue (a mesh stand-in: this file has no MRS_Road)."""
    sx, sy = start; nx, ny = -d[1], d[0]
    me = bpy.data.meshes.new(name); bm = bmesh.new(); lay = bm.faces.layers.float.new("mrs_tongue")
    def quad(l0, l1, kind):
        vs = [bm.verts.new((sx + d[0] * a + nx * l, sy + d[1] * a + ny * l, z - AJ.drop_of(kind))) for a, l in ((0, l0), (length, l0), (length, l1), (0, l1))]
        f = bm.faces.new(vs); f[lay] = kind; f.material_index = 0 if kind == 1 else 1
    quad(-road / 2, road / 2, 1); quad(road / 2, road / 2 + side, 2); quad(-road / 2 - side, -road / 2, 2)
    bm.to_mesh(me); bm.free()
    a = me.attributes.new("mrs_drop", "FLOAT", "POINT")
    for p in me.polygons:
        k = int(round(me.attributes["mrs_tongue"].data[p.index].value))
        for vi in p.vertices: a.data[vi].value = AJ.drop_of(k)
    me.materials.append(bpy.data.materials["MRS_TongueRoad"]); me.materials.append(bpy.data.materials["MRS_TongueSide"])
    o = bpy.data.objects.new(name, me); roads.objects.link(o); return o

# crossing + bus bay + lane
for nm, s, d in (("T_E", (8, 0), (-1, 0)), ("T_W", (-8, 0), (1, 0)), ("T_N", (0, 8), (0, -1)), ("T_S", (0, -8), (0, 1))): tongue(nm, s, d)
AJ.add_extension("Bus Bay", "square", roads, (6.0, 5.5, 1.0), (6.0, 3.0), **{"Roadside Size": 2.0})
AJ.add_extension("Lane", "curve", roads, points=[(-3.0, -3.0, 1.0), (-14.0, -14.0, 1.0)], **{"Road Size": 4.0, "Roadside Size": 1.5})
AJ.add_area_junction("Junction", (0, 0, 1.0), roads, juncs)
# roundabout (its own Roads collection)
ra = bpy.data.collections.new("Roads Roundabout"); sc.collection.children.link(ra)
for nm, s, d in (("R_E", (66, 0), (-1, 0)), ("R_W", (34, 0), (1, 0)), ("R_N", (50, 16), (0, -1)), ("R_S", (50, -16), (0, 1))):
    o = tongue(nm, s, d); roads.objects.unlink(o); ra.objects.link(o)
AJ.add_extension("Ring", "round", ra, (50, 0, 1.0), (30.0, 30.0), **{"Roadside Size": 2.5})
AJ.add_extension("Island", "round", ra, (50, 0, 1.0), (12.0, 12.0), Island=True)
AJ.add_area_junction("Roundabout", (50, 0, 1.0), ra, juncs, Distance=25.0)
# signs and bay lines
CS.add_custom_sign("CRM 2.1 Sign", (-6, -20, 0.0), "CRM 2.1", signs)
CS.add_custom_sign("Stop Sign", (-4.5, -20, 0.0), "Stop", signs)
bay = ML.add_marking_lines("Bay Lines", [(20, -30, 0.0), (20, -25, 0.0)], signs, **{"Edge Marking": False, "Center Marking": True, "Center Line 1": "Solid", "Center Color": "White"})
arr = bay.modifiers.new("Array", "ARRAY"); arr.count = 10; arr.use_relative_offset = False; arr.use_constant_offset = True; arr.constant_offset_displace = (2.6, 0, 0)
out = os.path.join(RECON, "CRM_Reconstruction_groups.blend")
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("LIGHT_BLEND %s (%.1f MB)" % (out, os.path.getsize(out) / 1e6))
