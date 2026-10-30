"""MRS_MarkingLines (CRM 2.1's Marking Lines, reconstructed): painted areas follow the patterns exactly.
    blender --background --factory-startup --python tools/roads/tests/marking_lines_test.py
A 30 m straight curve: two solid 0.1 m edge lines = 6 m2; + a solid centre line = 9; centre dashed 3/3 = 7.5; centre
double (dashed + solid) = 10.5; + two dashed lane lines each side = 16.5; lane lines evenly between centre and edges.
Prints MARKING_LINES OK."""
import bpy, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
from mrs import markinglines as ML
from mrs.nodes import mod_input_set

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
ML.build_marking_lines()
o = ML.add_marking_lines("ML", [(0, 0, 0), (0, 30, 0)], bpy.context.scene.collection)
mod = o.modifiers[0]


def area():
    o.update_tag(); ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    a = sum(p.area for p in me.polygons); xs = sorted({round(p.center.x, 2) for p in me.polygons}); ev.to_mesh_clear(); return a, xs

for step, want, text in ((lambda: None, 6.0, "two solid edge lines"), (lambda: mod_input_set(mod, "Center Marking", True), 9.0, "+ a solid centre line"),
                         (lambda: mod_input_set(mod, "Center Line 1", "Dashed"), 7.5, "centre dashed 3 / 3"),
                         (lambda: mod_input_set(mod, "Center Line 2", "Solid"), 10.5, "centre double line (dashed + solid)"),
                         (lambda: (mod_input_set(mod, "Lane Marking", True), mod_input_set(mod, "Lane Duplicate", 2)), 16.5, "+ two dashed lane lines each side")):
    step(); a, xs = area()
    check(abs(a - want) < 0.05, "%s: %.2f m2 (want %.1f)" % (text, a, want))
check(all(any(abs(x - t) < 0.06 for x in xs) for t in (-2.67, -1.33, 1.33, 2.67)), "lane lines at +-1/3 and +-2/3 of the half width (%s)" % xs)
print("MARKING_LINES %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
sys.exit(1 if fails else 0)
