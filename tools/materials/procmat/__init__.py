"""procmat - procedural material library for Blender 5.2 (headless-safe), separate from the road tool (decision D1).

    import sys; sys.path.insert(0, r"C:/GodotProjects/delivery-simulator-2026/tools/materials")
    import procmat
    procmat.discover()                  # import procmat.asphalt / cobblestone / glass (+ any other material module)
    mats = procmat.build("asphalt")     # -> [bpy.types.Material, ...]
    procmat.build_all()                 # every library material -> {key: [materials]}

Modules: core (builder, contract groups / materials, coordinates), rig (preview scene, renders), bake (seamless
tiles, seam metric), graphdump (Markdown node documentation), road_adapter (Mert Road Studio material inputs,
shelter glass), imaging (PNG helpers). API: procmat/API.md. CLI: tools/materials/run.py.

A material module defines KEY and build() (returning its materials) and registers itself at import time:
    import sys; from . import register; register(sys.modules[__name__])
"""
import importlib
import os
import sys
import traceback

from . import core  # noqa: F401  (core needs bpy: the package runs inside Blender)

MATERIALS = {}                                  # key -> module with build() returning materials
KNOWN_MODULES = ("asphalt", "cobblestone", "glass")
CORE_MODULES = {"core", "rig", "bake", "graphdump", "road_adapter", "imaging"}


def register(module, key=None):
    """Add a material module (or its dotted name) to MATERIALS under `key` (default: module.KEY or its file name)."""
    if isinstance(module, str): module = sys.modules[module]
    key = key or getattr(module, "KEY", None) or module.__name__.rsplit(".", 1)[-1]
    MATERIALS[key] = module
    return module


def discover(names=None, verbose=True):
    """Import material modules: `names`, or the known ones plus every other .py module in this package.
    A module that does not exist is skipped with a message; one that fails to import is reported with its
    traceback. Returns {name: "ok" | "missing" | "error: ..."}."""
    if names is None:
        here = os.path.dirname(os.path.abspath(__file__))
        extra = sorted(f[:-3] for f in os.listdir(here) if f.endswith(".py") and not f.startswith("_") and f[:-3] not in CORE_MODULES)
        names = list(KNOWN_MODULES) + [n for n in extra if n not in KNOWN_MODULES]
    status = {}
    for n in names:
        full = __name__ + "." + n
        try:
            mod = importlib.import_module(full)
            if not any(m is mod for m in MATERIALS.values()) and hasattr(mod, "build"): register(mod)
            status[n] = "ok"
        except ModuleNotFoundError as e:
            if e.name == full:
                status[n] = "missing"
                if verbose: print("[procmat] %s not present, skipped" % full)
            else:
                status[n] = "error: %s" % e
                print("[procmat] %s failed to import:\n%s" % (full, traceback.format_exc()))
        except Exception as e:
            status[n] = "error: %s" % e
            print("[procmat] %s failed to import:\n%s" % (full, traceback.format_exc()))
    return status


def _as_list(r):
    if r is None: return []
    if isinstance(r, dict): return list(r.values())
    if isinstance(r, (list, tuple)): return list(r)
    return [r]


def build(key):
    """Build one registered material module. Returns its materials (a list)."""
    if key not in MATERIALS: discover()
    if key not in MATERIALS: raise KeyError("no material module %r (have %s)" % (key, sorted(MATERIALS)))
    return _as_list(MATERIALS[key].build())


def library_keys():
    """Registered keys that belong to the library (modules with LIBRARY = False, e.g. the core demo, are left out)."""
    return [k for k, m in sorted(MATERIALS.items()) if getattr(m, "LIBRARY", True)]


def build_all(include_demo=False):
    """Build every registered library module. Returns {key: [materials]}."""
    if not MATERIALS: discover()
    keys = sorted(MATERIALS) if include_demo else library_keys()
    return {k: build(k) for k in keys}


def reload():
    """Re-import the core modules and the registered material modules (development in a live session)."""
    for n in ("core", "imaging", "rig", "bake", "graphdump", "road_adapter"):
        full = __name__ + "." + n
        if full in sys.modules: importlib.reload(sys.modules[full])
    for k, m in list(MATERIALS.items()):
        MATERIALS[k] = importlib.reload(m)
