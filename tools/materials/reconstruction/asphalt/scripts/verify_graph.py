"""Check the built groups against the reverse-engineered spec: every one of the spec's 38 links (reroutes collapsed)
must exist in PM_AsphaltTutorial and PM_Asphalt, seen through layout-only nodes (reroutes), the 3D / 4D twins'
"object 3D | UV 4D" mixes and the Coordinates frame (Object -> V); every spec node must exist (by its id).

    blender --background --factory-startup --python verify_graph.py -- SPEC.json OUT.json

Socket names map 3.2 -> 5.2: MixRGB Fac / Color1 / Color2 / Color -> Mix Factor / A / B / Result; a ColorRamp that
became a control is a Map Range (Value -> Result) or a Mix (Factor -> Result)."""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if LIB not in sys.path: sys.path.insert(0, LIB)
import procmat  # noqa: E402
from procmat import core  # noqa: E402

IN_MAP = {"ShaderNodeMix": {"Fac": "Factor_Float", "Color1": "A_Color", "Color2": "B_Color"},
          "ShaderNodeMapRange": {"Fac": "Value"}, "ShaderNodeValToRGB": {"Fac": "Fac"}}
OUT_MAP = {"ShaderNodeMix": {"Color": "Result_Color"}, "ShaderNodeMapRange": {"Color": "Result"}}


def nodes_for(tree, node_id):
    if node_id == "texcoord":
        return [n for n in tree.nodes if n.bl_idname == "ShaderNodeTexCoord"]
    return [n for n in tree.nodes if n.name == node_id or n.name in (node_id + "_3d", node_id + "_4d")]


def transparent(n):
    if n.bl_idname == "NodeReroute": return True
    if n.label == "object 3D | UV 4D": return True
    f = n.parent
    while f is not None:
        if f.label.startswith("Coordinates"): return True
        f = f.parent
    return n.name == "pattern_scale"


def in_socket(n, name):
    key = IN_MAP.get(n.bl_idname, {}).get(name, name)
    for s in n.inputs:
        if s.identifier == key or (s.name == key and getattr(s, "enabled", True)): return s
    return None


def out_matches(sock, name):
    n = sock.node; key = OUT_MAP.get(n.bl_idname, {}).get(name, name)
    return sock.identifier == key or sock.name == key or (name == "Fac" and sock.identifier == "Fac")


def upstream(sock):
    """Producer sockets reached from an input socket through transparent nodes."""
    out, todo, seen = [], [sock], set()
    while todo:
        s = todo.pop()
        for l in s.links:
            n = l.from_node
            if (n.name, l.from_socket.identifier) in seen: continue
            seen.add((n.name, l.from_socket.identifier))
            if transparent(n) and n.bl_idname != "ShaderNodeTexCoord":
                todo += [i for i in n.inputs if i.is_linked]
            else:
                out.append(l.from_socket)
    return out


def check_tree(tree, links, node_ids):
    res = []
    for L in links:
        src, dst = L["from_node"], L["to_node"]
        if dst == "output":
            go = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput")
            ups = upstream(go.inputs["BSDF"])
            ok = any(u.node.name == "principled" and u.name == "BSDF" for u in ups)
            res.append(dict(L, ok=ok, via="principled.BSDF -> group output BSDF -> material output Surface (contract)")); continue
        dn = nodes_for(tree, dst)
        found = []
        for n in dn:
            s = in_socket(n, L["to_socket"])
            if s is None or not s.is_linked: continue
            for u in upstream(s):
                if u.node in nodes_for(tree, src) and out_matches(u, L["from_socket"]):
                    found.append("%s.%s -> %s.%s" % (u.node.name, u.identifier, n.name, s.identifier))
        res.append(dict(L, ok=bool(found) and len(found) >= len(dn) - 0, via="; ".join(found)))
    missing_nodes = [i for i in node_ids if not nodes_for(tree, i) and i not in ("output",) and not i.startswith("frame_")]
    return res, missing_nodes


def main(argv):
    spec_path, out_path = argv[0], argv[1]
    spec = json.load(open(spec_path, encoding="utf-8"))
    top = spec["materials"][0]["top_level"]
    links = top["links_collapsed_without_reroutes"]
    node_ids = [n["id"] for n in top["nodes"]]
    procmat.discover(verbose=False); procmat.build("asphalt")
    report = {}
    for gname in ("PM_AsphaltTutorial", "PM_Asphalt"):
        tree = bpy.data.node_groups[gname]
        res, miss = check_tree(tree, links, node_ids)
        report[gname] = {"links_ok": sum(r["ok"] for r in res), "links_total": len(res), "missing_nodes": miss, "links": res}
        print("[verify] %s: %d / %d spec links found, missing nodes %s" % (gname, report[gname]["links_ok"], len(res), miss))
        for r in res:
            if not r["ok"]: print("   MISSING", r["from_node"], r["from_socket"], "->", r["to_node"], r["to_socket"])
    with open(out_path, "w") as f: json.dump(report, f, indent=1)
    ok = all(v["links_ok"] == v["links_total"] and not v["missing_nodes"] for v in report.values())
    print("VERIFY %s" % ("OK" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    good = main(sys.argv[sys.argv.index("--") + 1:])
    sys.stdout.flush(); sys.exit(0 if good else 1)
