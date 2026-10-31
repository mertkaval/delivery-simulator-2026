"""procmat.bake: bake any contract material (one "MRS" group node) to PNG tiles, like the road tool's bake_tiles().

    paths = bake("PM_Asphalt", out_dir, tile=4.0, res=1024, samples=16)   # {"albedo": .., "normal": .., "roughness": ..}
    seam_metric(paths["albedo"]) -> {"edge_mad", "interior_mad", "ratio", "ratio_x", "ratio_y", "size"}
    tile_preview(paths["albedo"], n=2, out=None) -> path of an n x n repeat

A tile x tile metre plane with UVs 0..1 carries the material with "Use UV" = 1 and "Tile Size" = tile, so every 4D
texture samples the seamless torus and the PNGs repeat. Albedo is the group's "Albedo" output through an emission
bake (exact, unlit), or the diffuse colour pass when the group has none; normal is tangent space; roughness is the
BSDF's; metallic / height / alpha are emission bakes of those outputs when the group has them. Cycles (GPU when
available) in its own scene "PM_Bake"; the material's inputs and displacement method are restored afterwards.
"""
import os

import bpy

from . import core, imaging, rig

BAKE_SCENE = "PM_Bake"
DEFAULT_MAPS = ("albedo", "normal", "roughness")      # + "metallic" when the group has a Metallic output

seam_metric = imaging.seam_metric
is_seamless = imaging.is_seamless


def tile_preview(png, n=2, out=None):
    """An n x n repeat of a baked tile (to look at the seams). Returns the output path."""
    return imaging.tile(png, n, out)


def _scene(samples, gpu, margin):
    sc = bpy.data.scenes.get(BAKE_SCENE) or bpy.data.scenes.new(BAKE_SCENE)
    on_gpu = rig.cycles_gpu(sc) if gpu else False
    if not gpu:
        sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    sc.cycles.samples = samples; sc.cycles.use_denoising = False
    bk = sc.render.bake; bk.margin = margin; bk.use_selected_to_active = False; bk.use_clear = True
    return sc, on_gpu


BAKE_UV = "PM_BakeUV"


def _plane(sc, size, uv_offset=(0.0, 0.0)):
    """The bake plane: "UVMap" (what the material reads: 0..1 + uv_offset, the active render UV map) and
    "PM_BakeUV" (0..1, the raster the bake writes through), so an offset never pushes texels off the image."""
    h = size / 2.0
    me = bpy.data.meshes.new("PM_BakePlane")
    me.from_pydata([(-h, -h, 0.0), (h, -h, 0.0), (h, h, 0.0), (-h, h, 0.0)], [], [(0, 1, 2, 3)])
    corners = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    uv = me.uv_layers.new(name="UVMap")
    for i, co in enumerate(corners): uv.data[i].uv = (co[0] + uv_offset[0], co[1] + uv_offset[1])
    raster = me.uv_layers.new(name=BAKE_UV)
    for i, co in enumerate(corners): raster.data[i].uv = co
    me.uv_layers.active = raster; uv.active_render = True
    me.update()
    ob = bpy.data.objects.new("PM_BakePlane", me); sc.collection.objects.link(ob)
    return ob


def _run_bake(sc, ob, **kw):
    """bpy.ops.object.bake on `ob` in scene `sc` (context override; falls back to the context scene)."""
    vl = sc.view_layers[0]
    for o in sc.objects: o.select_set(o == ob, view_layer=vl)
    vl.objects.active = ob
    try:
        with bpy.context.temp_override(scene=sc, view_layer=vl, active_object=ob, object=ob,
                                       selected_objects=[ob], selected_editable_objects=[ob]):
            bpy.ops.object.bake(**kw)
        return "override"
    except (RuntimeError, TypeError) as e:
        print("[procmat.bake] scene override failed (%s); baking in the context scene" % str(e).strip()[:200])
    cs = bpy.context.scene; cvl = bpy.context.view_layer
    linked = ob.name not in cs.collection.objects
    if linked: cs.collection.objects.link(ob)
    prev = (cs.render.engine, cs.cycles.samples, cs.cycles.device)
    sel = [o for o in cvl.objects if o.select_get()]; act = cvl.objects.active
    try:
        cs.render.engine = "CYCLES"; cs.cycles.samples = sc.cycles.samples; cs.cycles.device = sc.cycles.device
        for o in cvl.objects: o.select_set(False)
        ob.select_set(True); cvl.objects.active = ob
        bpy.ops.object.bake(**kw)
        return "context"
    finally:
        if linked: cs.collection.objects.unlink(ob)
        try: cs.render.engine = prev[0]
        except TypeError: pass
        cs.cycles.samples, cs.cycles.device = prev[1], prev[2]
        for o in sel: o.select_set(True)
        cvl.objects.active = act


def _output(node, key):
    """Group output for an emission bake: exact name, else a case-insensitive match."""
    if key in node.outputs: return node.outputs[key]
    for s in node.outputs:
        if s.name.lower() == key.lower(): return s
    return None


def bake(material, out_dir, tile=4.0, res=1024, samples=16, maps=None, margin=16, use_uv=True, plane_size=None,
         gpu=True, prefix=None, verbose=True, uv_offset=(0.0, 0.0)):
    """Bake `material` to <out_dir>/<prefix or material name>_<map>.png. Returns {map: path}.

    maps      : default albedo, normal, roughness (+ metallic when the group has a Metallic output); any other
                group output name (height, alpha, ...) bakes through emission
    use_uv    : True = UV mode (seamless). False keeps object mode (a control: object coordinates on the plane)
    plane_size: metres of the bake plane (default = tile); object-mode texel checks bake 1 m and 4 m planes
    uv_offset : added to the plane's UVs (0..1); a periodic material bakes the same tile, rolled (periodicity checks)"""
    mat = core.material(material); node = core.group_node(mat)
    if node is None: raise ValueError("%s has no %r group node" % (mat.name, core.GROUP_NODE))
    out_dir = os.path.abspath(out_dir); os.makedirs(out_dir, exist_ok=True)
    if maps is None: maps = list(DEFAULT_MAPS) + (["metallic"] if "Metallic" in node.outputs else [])
    sc, on_gpu = _scene(samples, gpu, margin)
    ob = _plane(sc, plane_size or tile, uv_offset); ob.data.materials.append(mat)
    nt = mat.node_tree
    saved = {k: node.inputs[k].default_value for k in ("Use UV", "Tile Size") if k in node.inputs}
    saved_method = getattr(mat, "displacement_method", None)
    out_node = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None) or \
        next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    surf = out_node.inputs["Surface"]
    surf_from = surf.links[0].from_socket if surf.is_linked else None
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.name = "PM_BakeTarget"; tex.location = (0.0, -500.0)
    nt.nodes.active = tex
    paths = {}; images = []; how = None
    try:
        if "Use UV" in node.inputs: node.inputs["Use UV"].default_value = 1.0 if use_uv else 0.0
        if "Tile Size" in node.inputs: node.inputs["Tile Size"].default_value = tile
        if saved_method is not None: mat.displacement_method = "BUMP"      # displacement reaches the normal map as bump
        for key in maps:
            extra = {}; emit = None; srgb = False
            if key == "albedo":
                srgb = True; emit = _output(node, "Albedo")
                btype = "EMIT" if emit is not None else "DIFFUSE"
                if emit is None: extra = {"pass_filter": {"COLOR"}}
            elif key == "normal":
                btype = "NORMAL"; extra = {"normal_space": "TANGENT"}
            elif key == "roughness":
                btype = "ROUGHNESS"
            else:
                emit = _output(node, key); btype = "EMIT"
                if emit is None:
                    print("[procmat.bake] %s: no %r output, skipped" % (mat.name, key)); continue
            img_name = "%s_%s" % (prefix or mat.name, key)
            old = bpy.data.images.get(img_name)
            if old is not None: bpy.data.images.remove(old)
            im = bpy.data.images.new(img_name, res, res, alpha=False, float_buffer=False); images.append(im)
            im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
            tex.image = im
            em = None
            if emit is not None:
                em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(emit, em.inputs["Color"])
                nt.links.new(em.outputs[0], surf)
            try:
                how = _run_bake(sc, ob, type=btype, margin=margin, use_clear=True, uv_layer=BAKE_UV, **extra)
            finally:
                if em is not None:
                    nt.nodes.remove(em)
                    if surf_from is not None: nt.links.new(surf_from, surf)
            p = os.path.join(out_dir, "%s_%s.png" % (prefix or mat.name, key))
            im.filepath_raw = p; im.file_format = "PNG"; im.save()
            paths[key] = p
    finally:
        for k, v in saved.items(): node.inputs[k].default_value = v
        if saved_method is not None: mat.displacement_method = saved_method
        nt.nodes.remove(tex)
        me = ob.data; bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
        for im in images: bpy.data.images.remove(im)
    if verbose:
        print("[procmat.bake] %s: %d px, tile %g m, %s, %s, %s" % (mat.name, res, tile, "UV mode" if use_uv else "object mode",
                                                                  "GPU" if on_gpu else "CPU", {k: os.path.basename(v) for k, v in paths.items()}))
    return paths


def baked_material(name, paths, repeat=1.0):
    """A plain image-textured material from bake() output (UV x repeat): what an engine would show."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-900, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-700, 0); mp.inputs["Scale"].default_value = (repeat, repeat, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    for i, key in enumerate(k for k in ("albedo", "normal", "roughness", "metallic") if k in paths):
        t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-450, -300 * i)
        t.image = bpy.data.images.load(paths[key], check_existing=True)
        t.image.colorspace_settings.name = "sRGB" if key == "albedo" else "Non-Color"
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
        if key == "albedo": nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        elif key == "roughness": nt.links.new(t.outputs["Color"], bsdf.inputs["Roughness"])
        elif key == "metallic": nt.links.new(t.outputs["Color"], bsdf.inputs["Metallic"])
        else:
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-150, -300 * i)
            nt.links.new(t.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return m


def periodicity(material, out_dir, tile=4.0, res=512, samples=16, offset=(0.5, 0.25), maps=("albedo",), gpu=True, prefix=None):
    """The direct repeat test: bake the tile, then again with the material's UVs shifted by `offset` (the bake raster
    stays 0..1). A material that repeats every Tile Size gives the first image rolled by offset x res pixels.
    Robust where seam_metric() is not (a joint grid snapped onto the seam). offset x res must be whole pixels.
    Returns {map: {"mad": rolled difference, "corr": rolled correlation, "mad_unrolled": difference without the roll}};
    is_periodic(result) applies the thresholds used by the tests (mad < 0.012, corr > 0.97)."""
    import numpy as np
    name = prefix or core.material(material).name
    a = bake(material, out_dir, tile, res, samples, list(maps), prefix=name + "_period0", gpu=gpu, verbose=False)
    b = bake(material, out_dir, tile, res, samples, list(maps), prefix=name + "_period1", gpu=gpu, verbose=False, uv_offset=offset)
    dx = int(round(offset[0] * res)); dy = int(round(offset[1] * res))
    out = {}
    for k in maps:
        A = imaging.load(a[k])[..., :3]; Bm = imaging.load(b[k])[..., :3]
        exp = np.roll(np.roll(A, -dx, axis=1), dy, axis=0)               # rows are top-down: +v moves up
        out[k] = {"mad": round(float(np.abs(Bm - exp).mean()), 5), "corr": round(float(np.corrcoef(Bm.ravel(), exp.ravel())[0, 1]), 5),
                  "mad_unrolled": round(float(np.abs(Bm - A).mean()), 5), "files": [a[k], b[k]]}
    return out


def is_periodic(result, mad=0.012, corr=0.97):
    """True when every map of a periodicity() result matches its rolled tile."""
    return all(v["mad"] < mad and v["corr"] > corr for v in result.values())

