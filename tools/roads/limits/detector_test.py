"""The sweeps' detectors must find what they are meant to find: known-bad layouts are built and every one must be
reported (a check that never fails proves nothing).
    blender --background tmp/roads/city/base.blend --python tools/roads/limits/detector_test.py
Cases: two roads crossing with no junction (overlap), two roads on top of each other (overlap), a road bent tighter
than its own half width (fold), a 30 / 45 / 60 degree bend junction with wide sidewalks (reported or clean, printed with
the overlap area so the sweep's verdict can be cross-checked by eye). Prints DETECTORS OK."""
import bpy, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads")); sys.path.insert(0, HERE)
import checks as C
from mrs import roads, nodes, validate, junction

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

sc = bpy.data.scenes.new("Detectors"); nodes.set_scene(sc)
try: bpy.context.window.scene = sc
except Exception: pass
over = dict(Conform=False, Embankment=False, Props=None, Trees=None, Streetlights=None, Scatter=None)


def fresh(name):
    c = bpy.data.collections.new(name); sc.collection.children.link(c); return c


def overlaps(col):
    dg = bpy.context.evaluated_depsgraph_get(); validate._CACHE.clear(); out = []
    validate.check_overlaps(col, dg, out); return out

c1 = fresh("D_Cross")
roads.make_road("D_X1", [(-50, 0, 0), (50, 0, 0)], c1, "residential", **over); roads.make_road("D_X2", [(0, -50, 0), (0, 50, 0)], c1, "residential", **over)
o1 = overlaps(c1); check(bool(o1), "two roads crossing with no junction are reported (%s)" % (o1[0]["message"] if o1 else "nothing"))
c2 = fresh("D_Stack")
roads.make_road("D_S1", [(200, 0, 0), (300, 0, 0)], c2, "residential", **over); roads.make_road("D_S2", [(200, 1.0, 0), (300, 1.0, 0)], c2, "residential", **over)
o2 = overlaps(c2); check(bool(o2), "two roads on top of each other are reported (%s)" % (o2[0]["message"] if o2 else "nothing"))
c3 = fresh("D_Fold")
r = 4.0
pts = [(400 + r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0.0) for a in range(-90, 181, 15)]
fo = roads.make_road("D_F", pts, c3, "urban", **over)
dg = bpy.context.evaluated_depsgraph_get(); f = C.check_fold(C.mesh_data(fo, dg))
check(bool(f), "a road bent on a 4 m radius (tighter than its width) is reported as folding (%s)" % (f[0] if f else "nothing"))
# bend junctions at acute angles (the city's case): print the overlap verdicts
for ang in (30.0, 45.0, 60.0):
    c = fresh("D_Bend%d" % ang)
    a = math.radians(ang)
    ra = roads.make_road("D_B%dA" % ang, [(70.0, 600.0 + 0, 0), (0.0, 600.0, 0)], c, "urban", **over)
    rb = roads.make_road("D_B%dB" % ang, [(70 * math.cos(a), 600.0 + 70 * math.sin(a), 0), (0.0, 600.0, 0)], c, "urban", **over)
    try:
        junction.build_junction("D_BJ%d" % ang, (0.0, 600.0, 0.0), [ra, rb], c, corner_radius=6.0, snap=1.0, z=0.0)
        o = overlaps(c); print("  bend %2d deg: %s" % (ang, o[0]["message"] if o else "no overlap"))
    except Exception as e:
        print("  bend %2d deg: build failed %s" % (ang, e))
print("DETECTORS %s" % ("OK" if not fails else "FAILED %d" % len(fails)))
