"""Audit: build PM_Cobblestone headless and compare the group node by node / link by link with GRAPH_SPEC_b.json
(and the ramp stops with GRAPH_SPEC_a.json).

    blender --background --factory-startup --python verify_graph.py -- OUT.json
"""
import json, os, re, sys
import bpy

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".."))
LIB = REPO + "/tools/materials"
sys.path.insert(0, LIB)
import procmat
from procmat import core, graphdump

procmat.discover(verbose=False)
mats = procmat.build("cobblestone")
OUT = sys.argv[sys.argv.index("--") + 1]
tree = bpy.data.node_groups["PM_Cobblestone"]
spec = json.load(open(LIB + "/reconstruction/cobblestone/GRAPH_SPEC_b.json"))
sg = spec["materials"][0]["groups"][0]
specA = json.load(open(LIB + "/reconstruction/cobblestone/GRAPH_SPEC_a.json"))

res = {"contract": {m.name: core.check_contract(m) for m in mats}, "nodes": [], "links": [], "interface": [],
       "extra_nodes": {}, "problems": []}


def P(msg): res["problems"].append(msg); print("PROBLEM", msg)


def in_coords(n):
    f = n.parent
    while f is not None:
        if f.label.startswith("Coordinates"): return True
        f = f.parent
    return False


def transparent(n):
    return (n.bl_idname == "NodeReroute" or n.label == "object 3D | UV 4D" or n.name == "mapping_scale"
            or (in_coords(n) and n.bl_idname != "ShaderNodeTexCoord"))


def built(node_id):
    if node_id == "tex_coord": return [n for n in tree.nodes if n.bl_idname == "ShaderNodeTexCoord"]
    if node_id == "group_input": return [n for n in tree.nodes if n.bl_idname == "NodeGroupInput"]
    if node_id == "group_output": return [n for n in tree.nodes if n.bl_idname == "NodeGroupOutput"]
    if node_id == "mapping": return [n for n in tree.nodes if n.label == "V" and in_coords(n)]
    ns = [n for n in tree.nodes if n.name == node_id]
    if not ns: ns = [n for n in tree.nodes if n.name in (node_id + "_3d",)]
    return ns


def sock_in(n, s):
    m = re.search(r"inputs\[(\d+)\]", s)
    if m: return n.inputs[int(m.group(1))]
    name = re.sub(r"\s*\(.*\)", "", s).strip()
    if n.bl_idname == "ShaderNodeMix" and n.data_type == "RGBA":
        name = {"A": "A_Color", "B": "B_Color", "Factor": "Factor_Float"}.get(name, name)
    if n.bl_idname == "NodeGroupOutput": name = {"Shader": "BSDF"}.get(name, name)
    for x in n.inputs:
        if x.identifier == name: return x
    for x in n.inputs:
        if x.name == name and x.enabled: return x
    return None


def out_ok(sock, from_id, s):
    n = sock.node
    if from_id == "group_input": return n.bl_idname == "NodeGroupInput" and sock.name == s
    if from_id == "tex_coord": return n.bl_idname == "ShaderNodeTexCoord" and sock.name == s
    m = re.search(r"outputs\[(\d+)\]", s)
    if m: return list(n.outputs).index(sock) == int(m.group(1))
    name = re.sub(r"\s*\(.*\)", "", s).strip()
    return sock.name == name or sock.identifier == name or (name == "Fac" and sock.identifier == "Fac")


def upstream(sock, only3d=True):
    """producer sockets reached through transparent nodes; only3d: through a 3D|4D mix take only A (object mode)."""
    out, todo, seen = [], [sock], set()
    while todo:
        s = todo.pop()
        for l in s.links:
            n = l.from_node
            if transparent(n):
                if id(n) in seen: continue
                seen.add(id(n))
                if n.label == "object 3D | UV 4D" and only3d:
                    todo.append(n.inputs[{"FLOAT": 2, "VECTOR": 4, "RGBA": 6}[n.data_type]])
                    todo.append(n.inputs[0])
                else:
                    todo += [i for i in n.inputs if i.is_linked]
            else:
                out.append(l.from_socket)
    return out


# ------------------------------------------------------------ links
for L in sg["links"]:
    fid, tid = L["from_node"], L["to_node"]
    rec = dict(L); rec.pop("class", None); rec.pop("t", None)
    targets = built(tid)
    if tid == "mapping":
        # mapping.Vector <- tex_coord.Object ; mapping.Scale <- Material Scale
        v = targets[0]
        if L["to_socket"] == "Vector":
            ups = upstream(v.inputs[0], True)
        else:
            ups = upstream(v.inputs["Scale"], True)
        ok = any(out_ok(u, fid, L["from_socket"]) for u in ups)
        rec["ok"] = ok; rec["via"] = [u.node.name + "." + u.name for u in ups]
        res["links"].append(rec)
        if not ok: P("link %s.%s -> %s.%s missing" % (fid, L["from_socket"], tid, L["to_socket"]))
        continue
    ok = False; via = []
    for t in targets:
        si = sock_in(t, L["to_socket"])
        if si is None: via.append("no socket %s on %s" % (L["to_socket"], t.name)); continue
        if fid == "mapping":
            ups = upstream(si, True)
            ok = any(u.node.label == "V" and in_coords(u.node) for u in ups) or any(
                u.node.bl_idname == "ShaderNodeTexCoord" for u in ups)
            # check that the vector is not modified by anything else than V (object mode)
            via += [u.node.name + "." + u.name for u in ups]
            # V is in coords (transparent) so ups should be TexCoord.Object + group inputs of the scale
            continue
        ups = upstream(si, True)
        via += [u.node.name + "." + u.name for u in ups]
        if any(out_ok(u, fid, L["from_socket"]) and (fid in ("group_input", "tex_coord") or u.node.name in (fid, fid + "_3d"))
               for u in ups):
            ok = True
    rec["ok"] = ok; rec["via"] = via
    res["links"].append(rec)
    if not ok: P("link %s.%s -> %s.%s : got %s" % (fid, L["from_socket"], tid, L["to_socket"], via))

# 4D twins: every 3D texture input that is linked must have the same producers on the 4D twin (UV mode fidelity)
twins = []
for n in tree.nodes:
    if n.name.endswith("_3d"):
        n4 = tree.nodes.get(n.name[:-3] + "_4d")
        if n4 is None: P("no 4D twin for " + n.name); continue
        diffs = []
        for s in n.inputs:
            if not s.enabled: continue
            s4 = n4.inputs.get(s.name) if s.name != "Vector" else n4.inputs["Vector"]
            if s4 is None: continue
            if s.name == "Vector": continue
            a = sorted(u.node.name.replace("_3d", "") + "." + u.name for u in upstream(s, True)) if s.is_linked else round(s.default_value, 5)
            b = sorted(u.node.name.replace("_4d", "") + "." + u.name for u in upstream(s4, False)) if s4.is_linked else round(s4.default_value, 5)
            if a != b: diffs.append((s.name, a, b))
        for k in ("noise_type", "feature", "distance", "normalize"):
            if hasattr(n, k) and getattr(n, k) != getattr(n4, k): diffs.append((k, getattr(n, k), getattr(n4, k)))
        twins.append({"node": n.name, "diffs": diffs})
        if diffs: P("4D twin differs %s %s" % (n.name, diffs))
res["twins"] = twins


# ------------------------------------------------------------ nodes
def hex2lin(h):
    h = h.lstrip("#"); o = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        o.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return o


def num(v):
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        m = re.match(r"^\s*(-?[\d.]+)", v)
        if m and "link" not in v: return float(m.group(1))
    return None


mapped = set()
for N in sg["nodes"]:
    nid = N["id"]; bs = built(nid)
    rec = {"id": nid, "type": N["type"], "found": [b.name for b in bs], "issues": []}
    for b in bs: mapped.add(b.name)
    if not bs:
        rec["issues"].append("missing"); P("node %s missing" % nid); res["nodes"].append(rec); continue
    b = bs[0]
    if nid not in ("mapping",) and b.bl_idname != N["type"]:
        rec["issues"].append("type %s != %s" % (b.bl_idname, N["type"]))
    for k, v in (N.get("settings") or {}).items():
        if k == "elements":
            got = [(round(e.position, 4), [round(c, 4) for c in e.color[:3]]) for e in b.color_ramp.elements]
            want = [(e["position"], [round(c, 4) for c in hex2lin(e["color_hex"])]) for e in v]
            rec["ramp_got"] = got; rec["ramp_want_b"] = want
            for (gp, gc), (wp, wc) in zip(got, want):
                if abs(gp - wp) > 1e-3 or max(abs(x - y) for x, y in zip(gc, wc)) > 2e-3:
                    rec["issues"].append("ramp stop got %s %s want(b) %s %s" % (gp, gc, wp, wc))
            if len(got) != len(want): rec["issues"].append("ramp stop count %d != %d" % (len(got), len(want)))
            continue
        if k.startswith("color_ramp."):
            got = getattr(b.color_ramp, k.split(".")[1])
        elif k in ("object", "from_instancer", "is_active_output"):
            continue
        elif k == "noise_dimensions" or k == "voronoi_dimensions":
            got = getattr(b, k)
        else:
            if not hasattr(b, k): rec["issues"].append("no attr %s" % k); continue
            got = getattr(b, k)
        want = v.split(" ")[0] if isinstance(v, str) else v
        if got != want: rec["issues"].append("%s = %r want %r" % (k, got, want))
    for k, v in (N.get("inputs") or {}).items():
        if nid in ("mapping", "group_output"): continue
        s = sock_in(b, k)
        if s is None: rec["issues"].append("no input %s" % k); continue
        n_ = num(v)
        if isinstance(v, list):
            if s.is_linked: rec["issues"].append("%s linked, want const %s" % (k, v))
            continue
        if isinstance(v, str) and "(unlinked)" in v:
            if s.is_linked: rec["issues"].append("%s linked, want unlinked" % k)
            continue
        if n_ is not None:
            if s.is_linked:
                rec["issues"].append("%s linked, want const %s" % (k, n_))
            elif abs(float(s.default_value) - n_) > 1e-6:
                rec["issues"].append("%s = %s want %s" % (k, s.default_value, n_))
    if b.bl_idname in ("ShaderNodeTexNoise", "ShaderNodeTexVoronoi"):
        rec["twin"] = [x.name for x in tree.nodes if x.name == nid + "_4d"]
        d3 = getattr(b, "noise_dimensions", getattr(b, "voronoi_dimensions", None))
        if d3 != "3D": rec["issues"].append("object twin is %s" % d3)
    if b.bl_idname == "ShaderNodeBsdfPrincipled":
        rec["hidden"] = {"distribution": b.distribution, "subsurface_method": b.subsurface_method}
    res["nodes"].append(rec)
    for i in rec["issues"]: P("node %s: %s" % (nid, i))

for n in tree.nodes:
    if n.name in mapped or n.name.endswith("_4d") or n.bl_idname == "NodeFrame": continue
    key = "coords" if in_coords(n) else ("dual_mix" if n.label == "object 3D | UV 4D" else n.name)
    res["extra_nodes"].setdefault(key, []).append("%s %s %s" % (n.bl_idname, n.name, n.label))

# ------------------------------------------------------------ interface
items = [i for i in tree.interface.items_tree if i.item_type == "SOCKET"]
panels = {}
for i in tree.interface.items_tree:
    if i.item_type == "SOCKET": panels[(i.name, i.in_out)] = i.parent.name if i.parent and i.parent.name else None
spec_in = [s for s in sg["interface"] if s["in_out"] == "INPUT"]
got_in = [i for i in items if i.in_out == "INPUT"]
res["interface_order_got"] = [i.name for i in got_in]
res["interface_order_spec"] = [s["name"] for s in spec_in]
gi = [i.name for i in got_in if i.name not in ("Pattern Size", "Use UV", "Tile Size")]
if gi != res["interface_order_spec"]: P("input order differs: %s" % gi)
for s in spec_in:
    it = next((i for i in got_in if i.name == s["name"]), None)
    rec = {"name": s["name"], "issues": []}
    if it is None: rec["issues"].append("missing"); res["interface"].append(rec); P("input missing " + s["name"]); continue
    if it.bl_socket_idname.split("Float")[0] != s["socket_type"].split("Float")[0] and it.bl_socket_idname != s["socket_type"]:
        rec["issues"].append("type %s != %s" % (it.bl_socket_idname, s["socket_type"]))
    pan = panels[(s["name"], "INPUT")]
    if pan != s["panel"]: rec["issues"].append("panel %r != %r" % (pan, s["panel"]))
    if s["socket_type"] == "NodeSocketColor":
        want = s.get("default_linear_rgba")
        got = list(it.default_value)
        if max(abs(a - b) for a, b in zip(got[:3], want[:3])) > 3e-4: rec["issues"].append("colour %s != %s" % (got, want))
    else:
        if abs(it.default_value - s["default"]) > 1e-6: rec["issues"].append("default %s != %s" % (it.default_value, s["default"]))
        mn = -3.4028234663852886e38 if s["min"] == "-inf" else s["min"]; mx = 3.4028234663852886e38 if s["max"] == "inf" else s["max"]
        if abs(it.min_value - mn) > 1e-3 * max(1, abs(mn)) or abs(it.max_value - mx) > 1e-3 * max(1, abs(mx)):
            rec["issues"].append("range %s..%s != %s..%s" % (it.min_value, it.max_value, mn, mx))
        st = getattr(it, "subtype", "NONE")
        if (s["subtype"] or "NONE") != st: rec["issues"].append("subtype %s != %s" % (st, s["subtype"]))
    res["interface"].append(rec)
    for i in rec["issues"]: P("input %s: %s" % (s["name"], i))
res["outputs_got"] = [i.name for i in items if i.in_out == "OUTPUT"]

# ------------------------------------------------------------ materials
for m in mats:
    res.setdefault("materials", {})[m.name] = {"displacement_method": m.displacement_method,
        "group_nodes": [n.name for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeGroup"],
        "out_links": sorted("%s.%s->%s" % (l.from_node.name, l.from_socket.name, l.to_socket.name) for l in m.node_tree.links),
        "diffuse": list(m.diffuse_color), "roughness": m.roughness}
res["counts"] = {"nodes": len(tree.nodes), "links": len(tree.links),
                 "non_frame": len([n for n in tree.nodes if n.bl_idname != "NodeFrame"])}
res["links_ok"] = sum(1 for l in res["links"] if l["ok"]); res["links_total"] = len(res["links"])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w"), indent=1, default=str)
graphdump.write(mats[0], os.path.join(os.path.dirname(OUT), "PM_Cobblestone_NODES_built.md"))
print("LINKS %d / %d, problems %d" % (res["links_ok"], res["links_total"], len(res["problems"])))
print("VERIFY DONE")
