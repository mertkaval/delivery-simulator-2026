"""Terrain helpers: a demo terrain (noise-displaced grid) and the MRS_TerrainConform group that pulls a
terrain mesh to the roads (CRM 'Pull Terrain' / 'Mountain Road')."""
import bpy, math
from mathutils import noise, Vector
from .nodes import T, MRS, new_tree, sock, add_inputs


def demo_terrain(name=MRS + "Terrain", size=400.0, step=4.0, height=18.0, seed=3, collection=None):
    """A hilly ground mesh with a valley across the middle (object space == world space, at the origin)."""
    n = int(size / step) + 1
    verts, faces = [], []
    for j in range(n):
        for i in range(n):
            x = -size / 2 + i * step; y = -size / 2 + j * step
            p = Vector((x * 0.012 + seed, y * 0.012, 0.0))
            h = noise.noise(p) * 0.6 + noise.noise(p * 2.3) * 0.25 + noise.noise(p * 5.0) * 0.1
            h = h * height + 0.5 * height * math.sin(x * 0.006) * math.cos(y * 0.004)
            valley = math.exp(-((y - 40.0) / 45.0) ** 2) * 14.0          # a dip across the scene
            verts.append((x, y, h - valley + 6.0))
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i; faces.append((a, a + 1, a + n + 1, a + n))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    for p in me.polygons: p.use_smooth = True
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    o = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(o)
    m = bpy.data.materials.get(MRS + "Ground") or bpy.data.materials.new(MRS + "Ground")
    m.use_nodes = True
    b = next(nn for nn in m.node_tree.nodes if nn.type == "BSDF_PRINCIPLED"); b.inputs["Base Color"].default_value = (0.16, 0.24, 0.09, 1); b.inputs["Roughness"].default_value = 0.95
    m.diffuse_color = (0.16, 0.24, 0.09, 1)
    me.materials.append(m)
    return o


def conform_terrain(source, roads_collection, sink=0.2, reach=80.0, subdivide=2, cut=False, cut_slope=1.0, fill_slope=0.5, raise_=True, own_slopes=False):
    """Grade a terrain to the roads without a dependency cycle: the roads raycast onto `source` (kept, hidden), and a
    second object sharing its mesh carries the MRS_TerrainConform modifier (cut / fill batters, see the group). With
    the terrain graded, the roads' own embankment skirts and retaining walls are switched off (they would stand
    against the graded slopes); `own_slopes=True` keeps them."""
    name = source.name + "_Conformed"
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, source.data)
    # never inside the roads collection it reads (that is a dependency cycle): link to the scene root
    for c in list(o.users_collection): c.objects.unlink(o)
    scenes = [sc for sc in bpy.data.scenes if source.name in sc.objects] or [bpy.context.scene]
    for sc in scenes: sc.collection.objects.link(o)
    o.data = source.data; o.matrix_world = source.matrix_world.copy()
    mod = o.modifiers.get("MRS_TerrainConform") or o.modifiers.new("MRS_TerrainConform", "NODES")
    mod.node_group = bpy.data.node_groups[MRS + "TerrainConform"]
    from .nodes import mod_input_set
    mod_input_set(mod, "Roads", roads_collection); mod_input_set(mod, "Sink", sink); mod_input_set(mod, "Reach", reach)
    mod_input_set(mod, "Subdivide", subdivide); mod_input_set(mod, "Cut", cut)
    mod_input_set(mod, "Cut Slope", cut_slope); mod_input_set(mod, "Fill Slope", fill_slope); mod_input_set(mod, "Raise", raise_)
    source.hide_viewport = True; source.hide_render = True; source.display_type = "WIRE"
    o["mrs_terrain_source"] = source.name
    if not own_slopes:
        from .roads import all_roads
        for r in all_roads(roads_collection):
            m = r.modifiers["MRS_Road"]; mod_input_set(m, "Embankment", False); mod_input_set(m, "Retaining Wall", False)
            # an edge skirt deeper than the sink: the terrain's step under the road edge is never seen
            from .roads import road_input
            if (road_input(r, "Edge Depth") or 0.0) < sink + 0.3: mod_input_set(m, "Edge Depth", sink + 0.3)
            r.update_tag()
    return o


def build_terrain_conform_group():
    """MRS_TerrainConform (modifier on a terrain mesh): the terrain graded to a road collection's ground surfaces with
    the rule mrs.grading applies to heightfields. Under a surface the terrain lies `Sink` below it (raised onto a fill
    with Raise, lowered into a cut); beyond, it is clipped between the batters from the nearest surface: at most
    `Cut Slope` (rise / run) above it and `Fill Slope` below it, so it meets every road edge and returns to its own
    shape where the batters let it (within `Reach`). Elevated decks and the roads' instances (props, trees) carry no
    `ground_surface` mark and are ignored; terrain faces near the roads are subdivided first."""
    g = new_tree(MRS + "TerrainConform")
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    add_inputs(g, [("Terrain", [
        ("Roads", "NodeSocketCollection", None, None, None, "Collection of MRS roads (and junctions)"),
        ("Sink", "NodeSocketFloat", 0.2, 0.0, 1.0, "Terrain this far below the road surfaces over it (m): more than a terrain triangle can sag "
         "under a bending road between two vertices (the roads' edge skirts hide the step)"),
        ("Cut Slope", "NodeSocketFloat", 1.0, 0.05, 10.0, "Steepest cut beside a road (rise / run: 1 = 45 deg)"),
        ("Fill Slope", "NodeSocketFloat", 0.5, 0.05, 10.0, "Steepest fill beside a road (rise / run: 0.5 = 1 : 2)"),
        ("Raise", "NodeSocketBool", True, None, None, "Fill up to the roads too (off: the terrain is only ever lowered)"),
        ("Max Rise", "NodeSocketFloat", 30.0, 0.0, 200.0, "Surfaces more than this above the terrain are ignored (m)"),
        ("Reach", "NodeSocketFloat", 80.0, 0.0, 500.0, "No change beyond this distance from the roads (m)"),
        ("Edge Band", "NodeSocketFloat", 2.5, 0.0, 20.0, "Beside a road the terrain lies at its edge height (minus Sink) this far out, then the batters start: "
         "set it to at least the terrain's edge length, so no terrain triangle rises through a road edge (m)"),
        ("Subdivide", "NodeSocketInt", 1, 0, 3, "Subdivision levels for terrain faces near roads"),
        ("Subdivide Reach", "NodeSocketFloat", 8.0, 0.0, 60.0, "Faces this close to a road are subdivided (m)"),
        ("Cut", "NodeSocketBool", False, None, None, "Delete terrain faces under the road surface instead of sinking them"),
        ("Tunnel Clearance", "NodeSocketFloat", 9.0, 3.0, 40.0, "Over a road's tunnel span the terrain stays at least this far above the road (m): the hill "
         "never cuts through the tunnel lining; near a portal it covers the lining like a cut-and-cover entrance"),
    ])])
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = lambda k: gi.outputs[k]
    ci = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(ci, "Collection", I("Roads"))
    real = tb.n("GeometryNodeRealizeInstances"); tb.inp(real, "Geometry", ci.outputs[0])
    keep = tb.compare("GREATER_THAN", tb.named("ground_surface"), 0.5)
    sep = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(sep, "Geometry", real.outputs[0]); tb.inp(sep, "Selection", keep)
    roads = sep.outputs[0]
    # the batters are measured from the surfaces' tops: the nearest point on a vertical edge skirt or kerb face is at
    # the terrain vertex's own height and would let the terrain sink down the skirt
    nrm = tb.n("GeometryNodeInputNormal").outputs[0]
    tops = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(tops, "Geometry", roads)
    tb.inp(tops, "Selection", tb.compare("GREATER_THAN", tb.math("ABSOLUTE", tb.separate(nrm)[2]), 0.3))
    road_tops = tops.outputs[0]
    # subdivide the faces near the roads (separate, subdivide, join back)
    pos = tb.n("GeometryNodeInputPosition").outputs[0]
    prox = tb.n("GeometryNodeProximity", target_element="FACES"); tb.inp(prox, "Target", roads); tb.inp(prox, "Source Position", pos)
    near = tb.compare("LESS_THAN", prox.outputs["Distance"], I("Subdivide Reach"))
    sepn = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(sepn, "Geometry", I("Geometry")); tb.inp(sepn, "Selection", near)
    sub2 = tb.n("GeometryNodeSubdivideMesh"); tb.inp(sub2, "Mesh", sepn.outputs[0]); tb.inp(sub2, "Level", I("Subdivide"))
    merged = tb.n("GeometryNodeMergeByDistance"); tb.inp(merged, "Geometry", tb.join(sub2.outputs[0], sepn.outputs[1])); tb.inp(merged, "Distance", 0.01)
    terrain = merged.outputs[0]
    pos2 = tb.n("GeometryNodeInputPosition").outputs[0]
    px, py, pz = tb.separate(pos2)
    # under a surface: a ray up from below finds it
    rc = tb.n("GeometryNodeRaycast", data_type="FLOAT"); tb.inp(rc, "Target Geometry", roads)
    tb.inp(rc, "Source Position", tb.vmath("ADD", pos2, (0.0, 0.0, -300.0))); tb.inp(rc, "Ray Direction", (0.0, 0.0, 1.0)); tb.inp(rc, "Ray Length", 900.0)
    hz = tb.math("SUBTRACT", tb.separate(rc.outputs["Hit Position"])[2], I("Sink"))
    under = tb.boolean("AND", rc.outputs["Is Hit"], tb.compare("LESS_THAN", tb.math("SUBTRACT", hz, pz), I("Max Rise")))
    z_under = tb.switch(I("Raise"), tb.math("MINIMUM", pz, hz), hz, "FLOAT")
    # beside the roads: clipped between the batters from the nearest surface point (horizontal distance)
    prox2 = tb.n("GeometryNodeProximity", target_element="FACES"); tb.inp(prox2, "Target", road_tops); tb.inp(prox2, "Source Position", pos2)
    nx, ny, nz0 = tb.separate(prox2.outputs["Position"])
    nz = tb.math("SUBTRACT", nz0, I("Sink"))
    dh = tb.vmath("LENGTH", tb.combine(tb.math("SUBTRACT", px, nx), tb.math("SUBTRACT", py, ny), 0.0))
    run = tb.math("MAXIMUM", tb.math("SUBTRACT", dh, I("Edge Band")), 0.0)          # the batters start beyond the edge band
    hi = tb.math("ADD", nz, tb.math("MULTIPLY", I("Cut Slope"), run)); lo = tb.math("SUBTRACT", nz, tb.math("MULTIPLY", I("Fill Slope"), run))
    clipped = tb.math("MINIMUM", tb.math("MAXIMUM", pz, lo), hi)
    z_side = tb.switch(I("Raise"), tb.math("MINIMUM", pz, clipped), clipped, "FLOAT")
    beside = tb.boolean("AND", tb.compare("LESS_THAN", dh, I("Reach")), tb.compare("LESS_THAN", tb.math("SUBTRACT", nz, pz), I("Max Rise")))
    newz = tb.switch(under, tb.switch(beside, pz, z_side, "FLOAT"), z_under, "FLOAT")
    # over a tunnel: at least Tunnel Clearance above the road (the tunnel faces carry tunnel_surface)
    tsep = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(tsep, "Geometry", real.outputs[0])
    tb.inp(tsep, "Selection", tb.compare("GREATER_THAN", tb.named("tunnel_surface"), 0.5))
    trc = tb.n("GeometryNodeRaycast", data_type="FLOAT"); tb.inp(trc, "Target Geometry", tsep.outputs[0])
    tb.inp(trc, "Source Position", tb.combine(px, py, tb.math("ADD", pz, 400.0))); tb.inp(trc, "Ray Direction", (0.0, 0.0, -1.0)); tb.inp(trc, "Ray Length", 900.0)
    t_need = tb.math("ADD", tb.separate(trc.outputs["Hit Position"])[2], I("Tunnel Clearance"))
    newz = tb.switch(trc.outputs["Is Hit"], newz, tb.math("MAXIMUM", newz, t_need), "FLOAT")
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", terrain); tb.inp(sp, "Position", tb.combine(px, py, newz))
    # cut: delete faces whose corners are all under the road
    delsel = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(delsel, "Geometry", sp.outputs[0]); tb.inp(delsel, "Selection", under)
    out = tb.switch(I("Cut"), sp.outputs[0], delsel.outputs[0], "GEOMETRY")
    tb.link(out, go.inputs[0])
    return g
