"""Mert Road Studio as a Blender add-on: the Road Studio sidebar panel in every session, plus opening / building the
MRS library. The tool itself lives in the repository (tools/roads/mrs); this add-on only points Blender at it.

Install: Edit > Preferences > Add-ons > Install from Disk, this folder zipped. Preferences: MRS tools path
(<repo>/tools/roads), Library file (<repo>/tmp/roads/city/base.blend). See docs/roads/USER_GUIDE.md."""
bl_info = {
    "name": "Mert Road Studio",
    "author": "Mert Road Studio",
    "version": (1, 0, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > Road Studio",
    "description": "Procedural roads, junctions, markings, signals, signs and street assets; validation; GLB export",
    "category": "Add Curve",
}
import os, sys
import bpy
from bpy.props import StringProperty

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_TOOLS = os.path.normpath(os.path.join(HERE, "..", ".."))                       # <repo>/tools/roads
REPO_LIBRARY = os.path.normpath(os.path.join(REPO_TOOLS, "..", "..", "tmp", "roads", "city", "base.blend"))


def _register_tools(self=None, context=None):
    """Register the Road Studio panel and operators from the tools path (called at enable and whenever the preference
    changes: an installed copy of the add-on lives outside the repository, so the default path rarely fits)."""
    try:
        _mrs().register()
    except Exception as e:
        print("Mert Road Studio: tools not found (%s); set the MRS tools path in the add-on preferences" % e)


class MRSADDON_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    tools_path: StringProperty(name="MRS tools path", subtype="DIR_PATH", default=REPO_TOOLS, description="The folder holding the mrs package (<repo>/tools/roads)",
                               update=_register_tools)
    library: StringProperty(name="Library file", subtype="FILE_PATH", default=REPO_LIBRARY, description="The MRS library .blend (node groups, materials, assets)")

    def draw(self, context):
        self.layout.prop(self, "tools_path"); self.layout.prop(self, "library")


def _prefs():
    try: return bpy.context.preferences.addons[__name__].preferences
    except Exception: return None


def _mrs():
    p = _prefs(); path = os.path.normpath(bpy.path.abspath(p.tools_path)) if p and p.tools_path else REPO_TOOLS
    if not os.path.isdir(os.path.join(path, "mrs")): raise ImportError("no mrs package in %s" % path)
    if path not in sys.path: sys.path.insert(0, path)
    import importlib, mrs
    if os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(mrs.__file__)))) != path: mrs = importlib.reload(mrs)
    return mrs


class MRSADDON_OT_open_library(bpy.types.Operator):
    """Open the MRS library as a new, unsaved project (Save As to keep it under your own name)"""
    bl_idname = "mrs_addon.open_library"; bl_label = "Open Library as New Project"

    def execute(self, context):
        p = _prefs(); lib = p.library if p else REPO_LIBRARY
        if not os.path.exists(lib):
            self.report({"ERROR"}, "No library at %s: use Build Library" % lib); return {"CANCELLED"}
        bpy.ops.wm.open_mainfile(filepath=lib, load_ui=False)
        self.report({"INFO"}, "MRS library opened: File > Save As to start your project")
        return {"FINISHED"}


class MRSADDON_OT_build_library(bpy.types.Operator):
    """Build (or rebuild) the MRS library file (about 12 minutes; Blender is busy meanwhile)"""
    bl_idname = "mrs_addon.build_library"; bl_label = "Build Library"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        _mrs(); from mrs import city
        p = _prefs(); lib = p.library if p else REPO_LIBRARY
        os.makedirs(os.path.dirname(lib), exist_ok=True)
        city.ensure_base(lib)
        self.report({"INFO"}, "MRS library built: %s" % lib)
        return {"FINISHED"}


class MRSADDON_PT_library(bpy.types.Panel):
    bl_label = "Library"; bl_space_type = "VIEW_3D"; bl_region_type = "UI"; bl_category = "Road Studio"; bl_order = 0

    def draw(self, context):
        L = self.layout
        if "MRS_Road" in bpy.data.node_groups:
            L.label(text="MRS library loaded", icon="CHECKMARK")
        else:
            L.label(text="No MRS library in this file", icon="ERROR")
        L.operator("mrs_addon.open_library", icon="FILE_FOLDER"); L.operator("mrs_addon.build_library", icon="NODETREE")


CLASSES = (MRSADDON_Preferences, MRSADDON_OT_open_library, MRSADDON_OT_build_library, MRSADDON_PT_library)


def register():
    for c in CLASSES: bpy.utils.register_class(c)
    _register_tools()                              # the Road Studio panel and operators (mrs/ui.py)


def unregister():
    try:
        from mrs import ui
        for c in reversed(ui.CLASSES):
            try: bpy.utils.unregister_class(c)
            except Exception: pass
    except Exception: pass
    for c in reversed(CLASSES): bpy.utils.unregister_class(c)
