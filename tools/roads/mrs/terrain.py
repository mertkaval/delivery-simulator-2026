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


def conform_terrain(source, roads_collection, sink=0.03, reach=3.0, subdivide=2, cut=False):
    """Pull a terrain to the roads without a dependency cycle: the roads raycast onto `source`
    (kept, hidden), and a second object sharing its mesh carries the MRS_TerrainConform modifier."""
    name = source.name + "_Conformed"
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, source.data)
        for c in source.users_collection: c.objects.link(o)
    o.data = source.data; o.matrix_world = source.matrix_world.copy()
    mod = o.modifiers.get("MRS_TerrainConform") or o.modifiers.new("MRS_TerrainConform", "NODES")
    mod.node_group = bpy.data.node_groups[MRS + "TerrainConform"]
    from .nodes import mod_input_set
    mod_input_set(mod, "Roads", roads_collection); mod_input_set(mod, "Sink", sink); mod_input_set(mod, "Reach", reach)
    mod_input_set(mod, "Subdivide", subdivide); mod_input_set(mod, "Cut", cut)
    source.hide_viewport = True; source.hide_render = True; source.display_type = "WIRE"
    o["mrs_terrain_source"] = source.name
    return o


def build_terrain_conform_group():
    """MRS_TerrainConform (modifier on the terrain): vertices under a road collection's surfaces are
    pulled to just below the road / embankment; optionally subdivided near the roads first."""
    g = new_tree(MRS + "TerrainConform")
    sock(g, "Geometry", "INPUT", "NodeSocketGeometry")
    add_inputs(g, [("Terrain", [
        ("Roads", "NodeSocketCollection", None, None, None, "Collection of MRS roads (and junctions)"),
        ("Sink", "NodeSocketFloat", 0.03, 0.0, 1.0, "Terrain stays this far below the road surface (m)"),
        ("Reach", "NodeSocketFloat", 2.0, 0.0, 30.0, "Blend distance beyond the road geometry (m)"),
        ("Subdivide", "NodeSocketInt", 1, 0, 3, "Subdivision levels for terrain faces near roads"),
        ("Cut", "NodeSocketBool", False, None, None, "Delete terrain faces under the road surface instead of sinking them"),
    ])])
    sock(g, "Geometry", "OUTPUT", "NodeSocketGeometry")
    tb = T(g); gi = tb.n("NodeGroupInput"); go = tb.n("NodeGroupOutput"); I = lambda k: gi.outputs[k]
    ci = tb.n("GeometryNodeCollectionInfo", transform_space="RELATIVE"); tb.inp(ci, "Collection", I("Roads"))
    real = tb.n("GeometryNodeRealizeInstances"); tb.inp(real, "Geometry", ci.outputs[0])
    # only surfaces (kind attribute present): drop instances' props by keeping faces with kind <= 4
    kind = tb.named("kind")
    keep = tb.boolean("OR", tb.compare("EQUAL", kind, 0.0), tb.boolean("OR", tb.compare("EQUAL", kind, 2.0), tb.boolean("OR", tb.compare("EQUAL", kind, 3.0), tb.compare("EQUAL", kind, 4.0))))
    sep = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(sep, "Geometry", real.outputs[0]); tb.inp(sep, "Selection", keep)
    roads = sep.outputs[0]
    # subdivide near the roads
    pos = tb.n("GeometryNodeInputPosition").outputs[0]
    prox = tb.n("GeometryNodeProximity", target_element="FACES"); tb.inp(prox, "Target", roads); tb.inp(prox, "Source Position", pos)
    near = tb.compare("LESS_THAN", prox.outputs["Distance"], tb.math("ADD", I("Reach"), 6.0))
    sub = tb.n("GeometryNodeSubdivideMesh"); tb.inp(sub, "Mesh", I("Geometry")); tb.inp(sub, "Level", I("Subdivide"))
    # subdivide only the near faces: separate, subdivide, join back
    sepn = tb.n("GeometryNodeSeparateGeometry", domain="FACE"); tb.inp(sepn, "Geometry", I("Geometry")); tb.inp(sepn, "Selection", near)
    sub2 = tb.n("GeometryNodeSubdivideMesh"); tb.inp(sub2, "Mesh", sepn.outputs[0]); tb.inp(sub2, "Level", I("Subdivide"))
    merged = tb.n("GeometryNodeMergeByDistance"); tb.inp(merged, "Geometry", tb.join(sub2.outputs[0], sepn.outputs[1])); tb.inp(merged, "Distance", 0.01)
    terrain = merged.outputs[0]
    # raycast up from below each vertex onto the road surfaces
    pos2 = tb.n("GeometryNodeInputPosition").outputs[0]
    rc = tb.n("GeometryNodeRaycast", data_type="FLOAT"); tb.inp(rc, "Target Geometry", roads)
    tb.inp(rc, "Source Position", tb.vmath("ADD", pos2, (0.0, 0.0, -300.0))); tb.inp(rc, "Ray Direction", (0.0, 0.0, 1.0)); tb.inp(rc, "Ray Length", 900.0)
    hz = tb.separate(rc.outputs["Hit Position"])[2]
    px, py, pz = tb.separate(pos2)
    under = tb.boolean("AND", rc.outputs["Is Hit"], tb.compare("LESS_THAN", tb.math("SUBTRACT", hz, pz), 12.0))   # ignore surfaces far above (elevated decks)
    newz = tb.switch(under, pz, tb.math("MINIMUM", pz, tb.math("SUBTRACT", hz, I("Sink"))), "FLOAT")     # only ever lower the terrain (bridges stay above it)
    # near the edge (within Reach, not under): blend towards the nearest road point height
    prox2 = tb.n("GeometryNodeProximity", target_element="FACES"); tb.inp(prox2, "Target", roads); tb.inp(prox2, "Source Position", pos2)
    d = prox2.outputs["Distance"]; nz = tb.separate(prox2.outputs["Position"])[2]
    f = tb.map_range(d, 0.0, I("Reach"), 1.0, 0.0)
    near2 = tb.boolean("AND", tb.boolean("NOT", under), tb.compare("LESS_THAN", d, I("Reach")))
    blend = tb.math("ADD", pz, tb.math("MULTIPLY", tb.math("SUBTRACT", tb.math("SUBTRACT", nz, I("Sink")), pz), f))
    newz = tb.switch(near2, newz, tb.math("MINIMUM", pz, blend), "FLOAT")
    sp = tb.n("GeometryNodeSetPosition"); tb.inp(sp, "Geometry", terrain); tb.inp(sp, "Position", tb.combine(px, py, newz))
    # cut: delete faces whose corners are all under the road
    delsel = tb.n("GeometryNodeDeleteGeometry", domain="FACE", mode="ALL"); tb.inp(delsel, "Geometry", sp.outputs[0]); tb.inp(delsel, "Selection", under)
    out = tb.switch(I("Cut"), sp.outputs[0], delsel.outputs[0], "GEOMETRY")
    tb.link(out, go.inputs[0])
    return g
