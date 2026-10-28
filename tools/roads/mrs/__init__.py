"""Mert Road Studio v2 - procedural roads for Blender 5.2.

    import sys; sys.path.insert(0, r"C:/GodotProjects/delivery-simulator-2026/tools/roads")
    import mrs; mrs.reload(); mrs.build_all(); mrs.register()
    mrs.samples.city_block()            # or mountain_road(), highway(), roundabout_village(), bridge_valley()
"""
import importlib, sys
import bpy

from . import nodes, materials, props, road, terrain

MODULES = ("nodes", "materials", "props", "road", "terrain", "roads", "qa", "junction", "structures", "assets", "trees", "signage", "placement", "street_model", "ui", "export", "samples")


def reload():
    """Re-import every submodule (development in a live Blender)."""
    g = globals()
    for m in MODULES:
        full = __name__ + "." + m
        if full in sys.modules:
            g[m] = importlib.reload(sys.modules[full])
        else:
            try: g[m] = importlib.import_module(full)
            except ModuleNotFoundError: pass


def build_all(verbose=True):
    import time
    def step(name, fn):
        t = time.time(); r = fn()
        if verbose: print("  build %-14s %5.1fs" % (name, time.time() - t))
        return r
    step("materials", materials.build_materials); step("extra mats", materials.extra_materials)
    step("props", props.build_prop_collections)
    a = globals().get("assets")
    if a and hasattr(a, "build_assets"): step("assets", a.build_assets)      # the detailed library replaces the placeholders
    tr = globals().get("trees")
    if tr and hasattr(tr, "build_trees"): step("trees", tr.build_trees)      # after assets: refills MRS_Trees with the generated variants
    sg = globals().get("signage")
    if sg and hasattr(sg, "build_signage"): step("signage", sg.build_signage)
    step("road group", road.build_road_group)                                  # after the collections exist: pick indices follow sorted names
    step("terrain", terrain.build_terrain_conform_group)
    step("refresh", roads.refresh_all)


def register():
    mod = globals().get("ui")
    if mod: mod.register()


from .nodes import MRS, mod_input_set, mod_input_get  # noqa: E402
for _m in ("roads", "qa", "junction", "structures", "assets", "trees", "signage", "placement", "street_model", "ui", "export", "samples"):
    try: globals()[_m] = importlib.import_module(__name__ + "." + _m)
    except ModuleNotFoundError: pass
