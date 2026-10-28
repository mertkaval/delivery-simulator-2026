"""Mert Road Studio v2 - procedural roads for Blender 5.2.

    import sys; sys.path.insert(0, r"C:/GodotProjects/delivery-simulator-2026/tools/roads")
    import mrs; mrs.reload(); mrs.build_all(); mrs.register()
    mrs.samples.city_block()            # or mountain_road(), highway(), roundabout_village(), bridge_valley()
"""
import importlib, sys
import bpy

from . import nodes, materials, props, road, terrain

MODULES = ("nodes", "materials", "props", "road", "terrain", "roads", "qa", "junction", "structures", "assets", "ui", "export", "samples")


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


def build_all():
    materials.build_materials()
    materials.extra_materials()
    props.build_prop_collections()
    road.build_road_group()
    terrain.build_terrain_conform_group()
    roads.refresh_all()
    for m in ("junction", "structures", "assets"):
        mod = globals().get(m)
        if mod and hasattr(mod, "build_groups"): mod.build_groups()


def register():
    mod = globals().get("ui")
    if mod: mod.register()


from .nodes import MRS, mod_input_set, mod_input_get  # noqa: E402
for _m in ("roads", "qa", "junction", "structures", "assets", "ui", "export", "samples"):
    try: globals()[_m] = importlib.import_module(__name__ + "." + _m)
    except ModuleNotFoundError: pass
