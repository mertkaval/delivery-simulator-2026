"""Landscape ground for a street block: one light grid mesh + a block-wide mask texture + three tiling
surface textures, blended identically in Blender (node material) and Godot (world/roads/mrs_ground.gdshader).

Large-scale variation and regions live in the MASK (0.25 m texels over the block bounds, from placement data):
  R  soil / bed   - park tree bases (soil ring fading into grass), shrub beds (union of shrub discs with a
                    defined edge), planting-bed outlines
  G  wear         - trampled grass at pedestrian access: path ends, path junctions, entrances, the footbridge
                    foot paths, the bus stop; worn bands along park-path edges; faint desire lines
  B  macro        - broad lush / dry variation (low-frequency value noise, 25-60 m)
  A  1
Fine detail comes from the TILES (seamless 4 m, baked from the embankment shader group): grass, bed soil
(dark, mulchy), worn earth. The ground mesh is a coarse grid (cell 8 m) carrying UVMap = metres and
UV2 = mask coordinates; no dense geometry. `build(roads_col, rep, z)` -> ground object + record dict."""
import bpy, os, math, json
import numpy as np
from mathutils import Vector
from .nodes import MRS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TILES = os.path.join(ROOT, "tmp", "roads", "materials", "tiles")
VARIANTS = {"GroundGrass": {"Slope Override": 0.0, "Rockiness": 0.0},
            "GroundSoil": {"Slope Override": 1.0, "Rockiness": 0.0, "Dirt Color": (0.095, 0.066, 0.045, 1.0)},
            "GroundWorn": {"Slope Override": 0.62, "Rockiness": 0.05, "Dirt Color": (0.30, 0.25, 0.18, 1.0), "Grass Color": (0.20, 0.25, 0.10, 1.0)}}
TEXEL = 0.25


def bake_tiles(res=1024, samples=8, force=False):
    """Bake the three ground tiles (albedo / normal / roughness) next to the road tiles."""
    from . import materials as M
    need = force or any(not os.path.exists(os.path.join(TILES, "%s%s_albedo.png" % (MRS, n))) for n in VARIANTS)
    src = bpy.data.materials.get(MRS + "Embankment")
    if src is None: raise RuntimeError("MRS_Embankment missing: run mrs.build_all() first")
    for n, vals in VARIANTS.items():
        m = bpy.data.materials.get(MRS + n) or src.copy(); m.name = MRS + n
        node = m.node_tree.nodes.get("MRS")
        for k, v in vals.items():
            if k in node.inputs: node.inputs[k].default_value = v
    if need: M.bake_tiles(TILES, res=res, samples=samples, tile=4.0, materials=tuple(VARIANTS))
    return {n: {k: os.path.join(TILES, "%s%s_%s.png" % (MRS, n, k)) for k in ("albedo", "normal", "roughness")} for n in VARIANTS}


# ----------------------------------------------------------------------------- mask painting
class Mask:
    def __init__(self, x0, y0, x1, y1, texel=TEXEL):
        self.x0, self.y0, self.t = x0, y0, texel
        self.w = int(math.ceil((x1 - x0) / texel)); self.h = int(math.ceil((y1 - y0) / texel))
        self.x1 = x0 + self.w * texel; self.y1 = y0 + self.h * texel
        self.c = np.zeros((4, self.h, self.w), dtype=np.float32); self.c[3] = 1.0
        xs = x0 + (np.arange(self.w) + 0.5) * texel; ys = y0 + (np.arange(self.h) + 0.5) * texel
        self.X, self.Y = np.meshgrid(xs, ys)

    def _win(self, x, y, r):
        i0 = max(0, int((x - r - self.x0) / self.t)); i1 = min(self.w, int((x + r - self.x0) / self.t) + 2)
        j0 = max(0, int((y - r - self.y0) / self.t)); j1 = min(self.h, int((y + r - self.y0) / self.t) + 2)
        return slice(j0, j1), slice(i0, i1)

    def disc(self, ch, x, y, r_full, r_zero, amount=1.0):
        """max-blend a soft disc: `amount` inside r_full, smooth fall to 0 at r_zero."""
        sj, si = self._win(x, y, r_zero)
        if sj.start >= sj.stop or si.start >= si.stop: return
        d = np.hypot(self.X[sj, si] - x, self.Y[sj, si] - y)
        v = np.clip((r_zero - d) / max(r_zero - r_full, 1e-6), 0.0, 1.0); v = v * v * (3 - 2 * v) * amount
        self.c[ch][sj, si] = np.maximum(self.c[ch][sj, si], v)

    def polyline(self, ch, pts, r_full, r_zero, amount=1.0, inner=None):
        """soft band around a polyline; `inner` (m) leaves a hole of that half-width (path edges, not the path)."""
        for a, b in zip(pts, pts[1:]):
            ax, ay = a[0], a[1]; bx, by = b[0], b[1]
            sj, si = self._win((ax + bx) / 2, (ay + by) / 2, math.hypot(bx - ax, by - ay) / 2 + r_zero)
            if sj.start >= sj.stop or si.start >= si.stop: continue
            X = self.X[sj, si]; Y = self.Y[sj, si]
            dx, dy = bx - ax, by - ay; L2 = max(dx * dx + dy * dy, 1e-9)
            t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0.0, 1.0)
            d = np.hypot(X - (ax + t * dx), Y - (ay + t * dy))
            v = np.clip((r_zero - d) / max(r_zero - r_full, 1e-6), 0.0, 1.0); v = v * v * (3 - 2 * v) * amount
            if inner is not None: v = v * np.clip((d - inner) / 0.15, 0.0, 1.0)
            self.c[ch][sj, si] = np.maximum(self.c[ch][sj, si], v)

    def macro(self, ch, seed=5):
        """broad lush / dry variation: two octaves of smooth value noise (25 m and 60 m cells)."""
        rng = np.random.default_rng(seed); acc = np.zeros((self.h, self.w), dtype=np.float32)
        for cell, wgt in ((60.0, 0.6), (25.0, 0.4)):
            gw = int((self.x1 - self.x0) / cell) + 3; gh = int((self.y1 - self.y0) / cell) + 3
            G = rng.random((gh, gw)).astype(np.float32)
            fx = (self.X - self.x0) / cell; fy = (self.Y - self.y0) / cell
            ix = np.floor(fx).astype(int); iy = np.floor(fy).astype(int); tx = fx - ix; ty = fy - iy
            tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
            v = (G[iy, ix] * (1 - tx) * (1 - ty) + G[iy, ix + 1] * tx * (1 - ty) + G[iy + 1, ix] * (1 - tx) * ty + G[iy + 1, ix + 1] * tx * ty)
            acc += v * wgt
        self.c[ch] = acc

    def save(self, path):
        img = bpy.data.images.get(os.path.basename(path))
        if img is not None: bpy.data.images.remove(img)
        img = bpy.data.images.new(os.path.basename(path), self.w, self.h, alpha=True, float_buffer=False)
        px = np.clip(np.stack([self.c[0], self.c[1], self.c[2], self.c[3]], axis=-1), 0.0, 1.0).astype(np.float32)
        img.pixels.foreach_set(px.ravel())
        img.colorspace_settings.name = "Non-Color"
        img.filepath_raw = path; img.file_format = "PNG"; img.save()
        return img


def paint(roads_col, rep, bounds, out_png):
    """Mask from the placement report (trees, plants, park paths, access points)."""
    x0, y0, x1, y1 = bounds
    M = Mask(x0, y0, x1, y1)
    M.macro(2)
    placed = bpy.data.collections.get(roads_col.name + "_Placed")
    # park / landscape trees: soil ring at the trunk fading into grass (street trees stand in strips / pits)
    for it in rep.get("items", []):
        if it.get("kind") == "tree" and it.get("side") == "park":
            x, y = it["pos"][0], it["pos"][1]; r = 0.9 + 0.15 * (it.get("crown", 4.0) / 4.0)
            M.disc(0, x, y, r, r + 0.9, 1.0)
            M.disc(1, x, y, r + 0.5, r + 2.2, 0.35)                  # trampled ring where people stand in the shade
    # shrub beds (park planting + landscape regions): union of shrub discs with a defined edge
    if placed:
        for o in placed.objects:
            if o.get("mrs_kind") != "landscape" or o.type != "MESH" or "plant" not in o.data.attributes: continue
            plants = sorted(x.name for x in bpy.data.collections[MRS + "GamePlants"].objects)
            pl = o.data.attributes["plant"].data; sc = o.data.attributes["scale"].data
            for i, v in enumerate(o.data.vertices):
                pid = plants[int(round(pl[i].value))][len(MRS + "GPlant_"):]
                q = o.matrix_world @ v.co
                if pid.startswith("shrub"):
                    r = 0.75 * sc[i].value + (0.35 if pid == "shrub_b" else 0.15)
                    M.disc(0, q.x, q.y, r, r + 0.25, 0.92)
        # park paths: worn edges (not under the path), path ends and junctions = access wear
        for o in placed.objects:
            if not o.get("mrs_ped_path"): continue
            pts = json.loads(o["mrs_ped_path"]); hw = float(o.get("mrs_path_width", 2.5)) / 2
            M.polyline(1, pts, hw + 0.35, hw + 1.4, 0.55, inner=hw - 0.05)
            for p in (pts[0], pts[-1]): M.disc(1, p[0], p[1], 1.2, 3.5, 0.6)
    # entrances, bus stops, footbridge foot paths: localized wear on the grass next to the access
    for o in bpy.data.objects:
        if o.type == "EMPTY" and o.name.startswith("MRS_Entrance"): M.disc(1, o.location.x, o.location.y, 1.0, 3.0, 0.5)
    for bs in rep.get("bus_stops", []):
        M.disc(1, bs["point"][0], bs["point"][1], 2.0, 6.0, 0.3)
    for o in roads_col.all_objects:
        if o.get("mrs_footbridge_plan") and o.type == "MESH":
            plan = json.loads(o["mrs_footbridge_plan"])
            for e in plan.get("ped_edges", []):
                path = e.get("approach_path", [])
                if path: M.polyline(1, path, 1.6, 3.2, 0.45, inner=1.2); M.disc(1, path[0][0], path[0][1], 1.5, 4.0, 0.5)
    M.save(out_png)
    return M


def build(roads_col, rep, z=-0.12, margin=40.0, cell=8.0, name=None):
    """Ground mesh + mask + material for the block. Returns (object, record)."""
    from .props import mat
    pts = []
    for o in roads_col.all_objects:
        if o.type in ("CURVE", "MESH") and not o.name.startswith(MRS + "Ground"):
            for c in o.bound_box: pts.append(o.matrix_world @ Vector(c))
    xs = [p.x for p in pts]; ys = [p.y for p in pts]
    bounds = (math.floor(min(xs) - margin), math.floor(min(ys) - margin), math.ceil(max(xs) + margin), math.ceil(max(ys) + margin))
    name = name or MRS + "Ground_" + roads_col.name
    tiles = bake_tiles()
    os.makedirs(TILES, exist_ok=True)
    mask_png = os.path.join(TILES, "%s_mask.png" % name)
    M = paint(roads_col, rep, bounds, mask_png)
    x0, y0, x1, y1 = M.x0, M.y0, M.x1, M.y1
    nx = int(math.ceil((x1 - x0) / cell)); ny = int(math.ceil((y1 - y0) / cell))
    verts = [(x0 + i * (x1 - x0) / nx, y0 + j * (y1 - y0) / ny, z) for j in range(ny + 1) for i in range(nx + 1)]
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i) for j in range(ny) for i in range(nx)]
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap"); uv2 = me.uv_layers.new(name="UV2")
    for li, l in enumerate(me.loops):
        co = me.vertices[l.vertex_index].co
        uv.data[li].uv = (co.x, co.y); uv2.data[li].uv = ((co.x - x0) / (x1 - x0), (co.y - y0) / (y1 - y0))
    me.materials.append(ground_material(name, mask_png, tiles))
    o = bpy.data.objects.new(name, me); roads_col.objects.link(o)
    o["mrs_ground"] = 1
    rec = {"name": name, "bounds": [x0, y0, x1, y1], "z": z, "texel": TEXEL, "mask": os.path.basename(mask_png), "tile_size": 4.0,
           "tiles": {n: {k: os.path.basename(p) for k, p in maps.items()} for n, maps in tiles.items()}}
    o["mrs_ground_record"] = json.dumps(rec)
    return o, rec


def ground_material(name, mask_png, tiles):
    """Blender version of world/roads/mrs_ground.gdshader (same textures, same blend)."""
    m = bpy.data.materials.get(name + "_Mat") or bpy.data.materials.new(name + "_Mat")
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (1400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled"); b.location = (1100, 0)
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"; uv.location = (-900, 0)
    sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs["Scale"].default_value = 0.25; sc.location = (-700, 0)
    nt.links.new(uv.outputs[0], sc.inputs[0])
    uv2 = nt.nodes.new("ShaderNodeUVMap"); uv2.uv_map = "UV2"; uv2.location = (-900, -500)
    mk = nt.nodes.new("ShaderNodeTexImage"); mk.location = (-650, -500); mk.image = bpy.data.images.load(mask_png, check_existing=True)
    mk.image.colorspace_settings.name = "Non-Color"; mk.extension = "EXTEND"; nt.links.new(uv2.outputs[0], mk.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateColor"); sep.location = (-350, -500); nt.links.new(mk.outputs["Color"], sep.inputs[0])
    def tex(path, nc=False, y=0):
        t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-450, y); t.image = bpy.data.images.load(path, check_existing=True)
        if nc: t.image.colorspace_settings.name = "Non-Color"
        nt.links.new(sc.outputs[0], t.inputs[0]); return t
    g, so, wo = tiles["GroundGrass"], tiles["GroundSoil"], tiles["GroundWorn"]
    tg, ts, tw = tex(g["albedo"], y=600), tex(so["albedo"], y=300), tex(wo["albedo"], y=0)
    rg, rs, rw = tex(g["roughness"], True, -900), tex(so["roughness"], True, -1100), tex(wo["roughness"], True, -1300)
    ng, ns, nw = tex(g["normal"], True, -1500), tex(so["normal"], True, -1700), tex(wo["normal"], True, -1900)
    def mix(fac, a, bsock, y, rgb=True):
        n_ = nt.nodes.new("ShaderNodeMix"); n_.data_type = "RGBA"; n_.location = (100, y)
        nt.links.new(fac, n_.inputs["Factor"]); nt.links.new(a, n_.inputs[6]); nt.links.new(bsock, n_.inputs[7]); return n_.outputs[2]
    # wear = G (smoothstep 0.15..0.85), soil = R (smoothstep 0.35..0.65: defined bed edges)
    def smooth(sock, lo, hi, y):
        mr = nt.nodes.new("ShaderNodeMapRange"); mr.interpolation_type = "SMOOTHSTEP"; mr.location = (-150, y)
        mr.inputs["From Min"].default_value = lo; mr.inputs["From Max"].default_value = hi; nt.links.new(sock, mr.inputs["Value"]); return mr.outputs[0]
    wear = smooth(sep.outputs[1], 0.15, 0.85, -600); soil = smooth(sep.outputs[0], 0.35, 0.65, -700)
    col = mix(wear, tg.outputs["Color"], tw.outputs["Color"], 500); col = mix(soil, col, ts.outputs["Color"], 400)
    # macro: B -> brightness / yellowing of the grass (lush 1.08, dry 0.86 + warmer)
    hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.location = (500, 400)
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (300, -800); mr.inputs["To Min"].default_value = 0.86; mr.inputs["To Max"].default_value = 1.08
    nt.links.new(sep.outputs[2], mr.inputs["Value"]); nt.links.new(mr.outputs[0], hsv.inputs["Value"])
    mh = nt.nodes.new("ShaderNodeMapRange"); mh.location = (300, -950); mh.inputs["To Min"].default_value = 0.515; mh.inputs["To Max"].default_value = 0.49
    nt.links.new(sep.outputs[2], mh.inputs["Value"]); nt.links.new(mh.outputs[0], hsv.inputs["Hue"])
    nt.links.new(col, hsv.inputs["Color"]); nt.links.new(hsv.outputs[0], b.inputs["Base Color"])
    rough = mix(wear, rg.outputs["Color"], rw.outputs["Color"], -300); rough = mix(soil, rough, rs.outputs["Color"], -400)
    bw = nt.nodes.new("ShaderNodeRGBToBW"); bw.location = (500, -350); nt.links.new(rough, bw.inputs[0]); nt.links.new(bw.outputs[0], b.inputs["Roughness"])
    nrm = mix(wear, ng.outputs["Color"], nw.outputs["Color"], -1000); nrm = mix(soil, nrm, ns.outputs["Color"], -1100)
    nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.location = (800, -900); nmap.uv_map = "UVMap"; nt.links.new(nrm, nmap.inputs["Color"]); nt.links.new(nmap.outputs[0], b.inputs["Normal"])
    nt.links.new(b.outputs[0], out.inputs[0])
    m["mrs_ground_mat"] = 1
    return m
