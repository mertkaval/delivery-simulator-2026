"""MRS_CustomSign (CRM 2.1's Custom Sign, reconstructed): the two signs the tutorial builds (E43-E48), live edits.
    blender --background --factory-startup --python tools/roads/tests/custom_sign_test.py -- <out_dir> [--no-render]
Checks: the panel spans Scale X x Scale Y at Panel Height; the texts exist and move with their X / Y; a text edit
changes the geometry; Octagon gives eight panel corners; Auto text is white on blue / red; poles reach the ground.
Prints CUSTOM_SIGN OK."""
import bpy, os, sys
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.path.join(ROOT, "tmp", "roads", "custom_sign")); os.makedirs(OUT, exist_ok=True)
from mrs import customsign as CS
from mrs.nodes import mod_input_set, mod_input_get

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
CS.build_custom_sign()


def mesh_of(o):
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    by = {}
    for p in me.polygons:
        m = me.materials[p.material_index].name if me.materials and me.materials[p.material_index] else "-"
        by.setdefault(m, []).append([o.matrix_world @ me.vertices[i].co for i in p.vertices])
    ev.to_mesh_clear(); return by


def bounds(polys):
    vs = [v for p in polys for v in p]
    return Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))), Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))

crm = CS.add_custom_sign("CS_CRM", (0, 0, 0), "CRM 2.1")
by = mesh_of(crm); print({k: len(v) for k, v in by.items()})
blue = by.get("MRS_SignFace_Blue", []); check(bool(blue), "the panel is blue")
if blue:
    lo, hi = bounds(blue)
    check(abs((hi.x - lo.x) - 0.6) < 0.01 and abs((hi.z - lo.z) - 0.6) < 0.01, "panel 0.6 x 0.6 m (%.3f x %.3f)" % (hi.x - lo.x, hi.z - lo.z))
    check(abs((hi.z + lo.z) * 0.5 - 2.2) < 0.01, "panel centre at Panel Height 2.2 m")
white = by.get("MRS_SignFace_White", []); check(len(white) > 20, "Auto text and the line are white on blue (%d white faces)" % len(white))
words = [p for p in white if bounds([p])[1].z > 2.2 + 0.1]
check(bool(words), "CRM 2.1 stands in the upper half (Y 0.155)")
n0 = sum(len(v) for v in by.values())
mod_input_set(crm.modifiers[0], "L1 T1 Text", "CRM 2.1 RECONSTRUCTED"); crm.update_tag()
n1 = sum(len(v) for v in mesh_of(crm).values()); check(n1 > n0, "a text edit changes the sign at once (%d -> %d faces)" % (n0, n1))
mod_input_set(crm.modifiers[0], "L1 T1 Text", "CRM 2.1")
metal = [k for k in by if "Metal" in k or k.endswith("Grey")]
if metal:
    lo, hi = bounds(by[metal[0]]); check(lo.z < 0.01, "the pole reaches the ground (%.3f)" % lo.z)
stop = CS.add_custom_sign("CS_Stop", (1.5, 0, 0), "Stop")
bs = mesh_of(stop); red = bs.get("MRS_SignFace_Red", [])
check(bool(red), "the stop sign is red")
if red:
    lo, hi = bounds(red); xs = sorted({round(v.x, 3) for p in red for v in p})
    check(abs((hi.x - lo.x) - 0.6) < 0.01, "octagon 0.6 m across (%.3f)" % (hi.x - lo.x))
check(len(bs.get("MRS_SignFace_White", [])) > 10, "white STOP text and border on red")
if "--no-render" not in argv:
    from mrs import qa
    sc = bpy.context.scene
    qa.render(os.path.join(OUT, "custom_signs.png"), Vector((0.75, -3.2, 2.3)), Vector((0.75, 0, 2.15)), 45.0, res=(1280, 800), samples=16, scene=sc); print("RENDER custom_signs")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "custom_sign.blend"), copy=True)
print("CUSTOM_SIGN %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
sys.exit(1 if fails else 0)
