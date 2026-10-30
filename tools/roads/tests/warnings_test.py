"""Combination warnings (phase B6): the modifiers warn, and validate reports `warning`, exactly when two inputs that pass
alone fail together; a scene with the same objects inside the rules shows no warning.
    blender --background tmp/roads/city/base.blend --python tools/roads/tests/warnings_test.py
Cases: a road bent tighter than bend_ratio x its inner half width (and the same road on a wide bend: none); a lane
taper running past the road's end (and one that ends on it); a custom sign whose text reaches beyond its panel (and the
same text on a panel large enough); marking lines with Center X beyond Road Size / 2 (and inside it); a value inside a
forbidden gap of limits.json when one exists. Prints WARNINGS_TEST OK."""
import bpy, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "roads"))
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
from mrs import roads, nodes, validate, limits, customsign as CS, markinglines as ML
from mrs.nodes import mod_input_set

fails = []
def check(ok, text):
    print(("PASS: " if ok else "FAIL: ") + text)
    if not ok: fails.append(text)

sc = bpy.data.scenes.new("WarnTest"); nodes.set_scene(sc)
try: bpy.context.window.scene = sc
except Exception: pass
col = bpy.data.collections.new("WT_Roads"); sc.collection.children.link(col)


def warnings_of(o):
    bpy.context.evaluated_depsgraph_get(); o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [w.message for m in o.modifiers if m.type == "NODES" for w in getattr(m, "node_warnings", ()) if w.message.startswith("MRS:")]


def arc(R, n=40):
    pts = [(-30.0, -R, 0.0)]
    for k in range(n + 1):
        a = -math.pi / 2 + (2.0 * math.pi / 3.0) * k / n; pts.append((R * math.cos(a), R * math.sin(a), 0.0))
    return pts

ratio = limits.rule("MRS_Road", "bend_ratio")
check(ratio is not None and ratio > 1.0, "limits.json carries the tested bend rule (bend_ratio %s)" % ratio)
# 1. bend: a 1+1 road with 2 m sidewalks has H = 5.45 m; R = 4 m folds, R = 30 m is fine
tight = roads.make_road("WT_Tight", arc(4.0), col, "residential", Conform=False, Embankment=False)
wide = roads.make_road("WT_Wide", arc(30.0), col, "residential", Conform=False, Embankment=False)
wt, ww = warnings_of(tight), warnings_of(wide)
check(any("bend" in w for w in wt), "a 4 m bend of a 5.45 m half-width road warns (%s)" % wt)
check(not ww, "the same road on a 30 m bend shows no warning (%s)" % ww)
# 2. taper past the end
tp = roads.make_road("WT_Taper", [(0, 100, 0), (60, 100, 0), (120, 100, 0)], col, "residential", Conform=False, Embankment=False,
                     Transition=True, Lanes_Forward_End=2, Transition_Start=40.0, Taper_Length=30.0)
check(not warnings_of(tp), "a taper ending on the road shows no warning (%s)" % warnings_of(tp))
mod_input_set(tp.modifiers["MRS_Road"], "Taper Length", 150.0); tp.update_tag()
check(any("taper" in w for w in warnings_of(tp)), "a taper running past the road's end warns (%s)" % warnings_of(tp))
# 3. sign content off the panel
sign = CS.add_custom_sign("WT_Sign", location=(0.0, 200.0, 0.0), preset="CRM 2.1", collection=col)
check(not warnings_of(sign), "the CRM 2.1 preset shows no warning (%s)" % warnings_of(sign))
msign = sign.modifiers[0]
mod_input_set(msign, "L1 T1 Size", 0.6); sign.update_tag()
check(any("panel" in w for w in warnings_of(sign)), "a text larger than the panel warns (%s)" % warnings_of(sign))
mod_input_set(msign, "Scale X", 3.0); mod_input_set(msign, "Scale Y", 3.0); sign.update_tag()
check(not warnings_of(sign), "the same text on a 3 m panel shows no warning (%s)" % warnings_of(sign))
# 4. marking lines off the road
ml = ML.add_marking_lines("WT_Lines", [(0.0, 300.0, 0.0), (60.0, 300.0, 0.0)], col)
mml = ml.modifiers[0]
mod_input_set(mml, "Center Marking", True); mod_input_set(mml, "Center X", 2.0); ml.update_tag()
check(not warnings_of(ml), "a centre line 2 m off a Road Size 8 curve shows no warning (%s)" % warnings_of(ml))
mod_input_set(mml, "Center X", 6.0); ml.update_tag()
check(any("outside the road" in w for w in warnings_of(ml)), "a centre line 6 m off a Road Size 8 curve warns (%s)" % warnings_of(ml))
# 5. forbidden gaps (when the sweeps found one): the value in the gap warns
gaps = [(g, k, r["gaps"][0]) for g, m in limits.load().items() if g != "_rules" for k, r in m.items() if r.get("gaps")]
if gaps:
    g, k, (a, b) = gaps[0]
    o = {"MRS_Road": wide}.get(g)
    if o is not None:
        mod_input_set(o.modifiers["MRS_Road"], k, (a + b) * 0.5); o.update_tag()
        check(any(k in w for w in warnings_of(o)), "%s = %.3g inside the gap (%.3g, %.3g) warns (%s)" % (k, (a + b) * 0.5, a, b, warnings_of(o)))
        mod_input_set(o.modifiers["MRS_Road"], k, roads.road_input(wide, k) if False else b + (b - a)); o.update_tag()
else:
    print("INFO: limits.json has no forbidden gaps (nothing to test)")
# validate reports every warning (the tight bend, the taper, the sign, the lines)
mod_input_set(msign, "Scale X", 0.6); mod_input_set(msign, "Scale Y", 0.6); sign.update_tag()
rep = validate.validate(col, None, overlaps=False)
ws = [p for p in rep["problems"] if p["check"] == "warning"]
names = {p["object"] for p in ws}
check({"WT_Tight", "WT_Taper", "WT_Sign", "WT_Lines"} <= names, "validate reports the warnings of every object (%s)" % sorted(names))
check("WT_Wide" not in names, "and none for the road inside the rules")
print("WARNINGS_TEST " + ("OK" if not fails else "FAIL: %d" % len(fails)))
