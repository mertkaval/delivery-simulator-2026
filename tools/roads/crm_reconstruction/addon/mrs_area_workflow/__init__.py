"""Mert Road Studio - Area Junction workflow (the City Road Maker 2.1 workflow, reconstructed).

3D View > Sidebar > MRS > Area Junctions. Install this folder as an add-on (Edit > Preferences > Add-ons > Install from
disk, the zipped folder) or run it from the repository; it imports the `mrs` package from the "MRS tools path"
preference (default: the repository's tools/roads next to this add-on).

Operators: build the node groups, add an area junction (Roads / Junctions collections made when missing, selected
roads moved into Roads), add an extension (square, round, curve, island), set tongues on the selected roads, add a
custom sign from a preset, save a sign's settings as a preset (presets/signs.json), add marking lines."""
bl_info = {
    "name": "MRS Area Junction Workflow",
    "author": "Mert Road Studio",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > MRS > Area Junctions",
    "description": "Tongue / area-junction road workflow, extensions, custom signs and marking lines (a City Road Maker 2.1 reconstruction)",
    "category": "Add Mesh",
}
import json, os, sys
import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty

HERE = os.path.dirname(os.path.abspath(__file__))
PRESET_FILE = os.path.join(HERE, "presets", "signs.json")


def _default_tools():
    return os.path.normpath(os.path.join(HERE, "..", "..", ".."))       # .../tools/roads


class MRSAW_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    tools_path: StringProperty(name="MRS tools path", subtype="DIR_PATH", default=_default_tools(),
                               description="Folder holding the mrs package (the repository's tools/roads)")

    def draw(self, context):
        self.layout.prop(self, "tools_path")


def _mrs():
    """The mrs package from the preference path (imported once)."""
    try: path = bpy.context.preferences.addons[__name__].preferences.tools_path
    except Exception: path = _default_tools()
    if path and path not in sys.path: sys.path.insert(0, path)
    import mrs
    return mrs


def _collection(name, context):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name); context.scene.collection.children.link(c)
    return c


def _move_to(obj, col):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    col.objects.link(obj)


def _sign_presets():
    from mrs import customsign
    out = dict(customsign.PRESETS)
    try:
        with open(PRESET_FILE) as f: out.update(json.load(f))
    except (OSError, ValueError):
        pass
    return out


def _preset_items(self, context):
    try:
        _mrs(); return [(k, k, "") for k in sorted(_sign_presets())]
    except Exception:
        return [("CRM 2.1", "CRM 2.1", ""), ("Stop", "Stop", "")]


class MRSAW_OT_build(bpy.types.Operator):
    bl_idname = "mrs_aw.build_groups"; bl_label = "Build Node Groups"
    bl_description = "Build MRS_AreaJunction, the extensions, MRS_CustomSign and MRS_MarkingLines (MRS_Road comes from the MRS library)"

    def execute(self, context):
        m = _mrs()
        from mrs import areajunction, customsign, markinglines
        areajunction.build_all(); customsign.build_custom_sign(); markinglines.build_marking_lines()
        if "MRS_Road" not in bpy.data.node_groups:
            self.report({"WARNING"}, "MRS_Road is not in this file: append it from the MRS library (tmp/roads/city/base.blend) or run mrs.build_all()")
        return {"FINISHED"}


class MRSAW_OT_add_junction(bpy.types.Operator):
    bl_idname = "mrs_aw.add_junction"; bl_label = "Add Area Junction"
    bl_description = "A junction at the 3D cursor; the selected roads go into the Roads collection it reads"
    bl_options = {"REGISTER", "UNDO"}
    distance: FloatProperty(name="Range", default=40.0, min=0.0, unit="LENGTH")

    def execute(self, context):
        _mrs(); from mrs import areajunction as AJ
        roads = _collection("Roads", context); juncs = _collection("Junctions", context)
        for o in context.selected_objects:
            if any(m.type == "NODES" and m.node_group and m.node_group.name in ("MRS_Road", "MRS_ExtensionMesh", "MRS_ExtensionCurve") for m in o.modifiers):
                _move_to(o, roads)
        o = AJ.add_area_junction("Area Junction", tuple(context.scene.cursor.location), roads, juncs, Distance=self.distance)
        for s in context.selected_objects: s.select_set(False)
        o.select_set(True); context.view_layer.objects.active = o
        return {"FINISHED"}


class MRSAW_OT_add_extension(bpy.types.Operator):
    bl_idname = "mrs_aw.add_extension"; bl_label = "Add Extension"
    bl_description = "An extension (a free-form road area) at the 3D cursor, in the Roads collection"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(name="Kind", items=[("square", "Square", "A rectangle of road with a roadside band (bus bay, car park)"),
                                           ("round", "Round", "A disc of road with a roadside band (turning circle, roundabout)"),
                                           ("curve", "Curve", "A curve swept to Road Size + Roadside Size"),
                                           ("island", "Island", "A disc cut out of the road and raised (a roundabout's centre)")])
    size: FloatProperty(name="Size", default=10.0, min=0.5, unit="LENGTH")

    def execute(self, context):
        _mrs(); from mrs import areajunction as AJ
        roads = _collection("Roads", context); c = context.scene.cursor.location
        if self.kind == "curve":
            o = AJ.add_extension("Extension Curve", "curve", roads, points=[(c.x - self.size * 0.5, c.y, c.z), (c.x + self.size * 0.5, c.y, c.z)])
        else:
            o = AJ.add_extension("Extension " + self.kind.title(), "round" if self.kind in ("round", "island") else "square", roads, tuple(c), (self.size, self.size),
                                 **({"Island": True} if self.kind == "island" else {}))
        for s in context.selected_objects: s.select_set(False)
        o.select_set(True); context.view_layer.objects.active = o
        return {"FINISHED"}


class MRSAW_OT_set_tongues(bpy.types.Operator):
    bl_idname = "mrs_aw.set_tongues"; bl_label = "Set Tongues"
    bl_description = "Tongue Start / Tongue End on every selected MRS road"
    bl_options = {"REGISTER", "UNDO"}
    start: FloatProperty(name="Start", default=10.0, min=0.0, unit="LENGTH")
    end: FloatProperty(name="End", default=10.0, min=0.0, unit="LENGTH")

    def execute(self, context):
        _mrs(); from mrs.nodes import mod_input_set
        n = 0
        for o in context.selected_objects:
            mod = o.modifiers.get("MRS_Road")
            if mod is None: continue
            mod_input_set(mod, "Tongue Start", self.start); mod_input_set(mod, "Tongue End", self.end); o.update_tag(); n += 1
        self.report({"INFO"}, "Tongues set on %d roads" % n)
        return {"FINISHED"}


class MRSAW_OT_add_sign(bpy.types.Operator):
    bl_idname = "mrs_aw.add_sign"; bl_label = "Add Custom Sign"
    bl_options = {"REGISTER", "UNDO"}
    preset: EnumProperty(name="Preset", items=_preset_items)

    def execute(self, context):
        _mrs(); from mrs import customsign
        o = customsign.add_custom_sign("Custom Sign", tuple(context.scene.cursor.location), preset="")
        from mrs.nodes import mod_input_set
        for k, v in _sign_presets().get(self.preset, {}).items(): mod_input_set(o.modifiers[0], k, v)
        o["mrs_custom_sign"] = self.preset
        for s in context.selected_objects: s.select_set(False)
        o.select_set(True); context.view_layer.objects.active = o
        return {"FINISHED"}


class MRSAW_OT_save_sign(bpy.types.Operator):
    bl_idname = "mrs_aw.save_sign_preset"; bl_label = "Save Sign Preset"
    bl_description = "Store the active custom sign's settings under a name in presets/signs.json"
    name: StringProperty(name="Name", default="My Sign")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        _mrs(); from mrs.nodes import mod_input_get
        o = context.active_object; mod = o.modifiers.get("MRS_CustomSign") if o else None
        if mod is None: self.report({"ERROR"}, "The active object has no MRS_CustomSign modifier"); return {"CANCELLED"}
        vals = {}
        for it in mod.node_group.interface.items_tree:
            if getattr(it, "in_out", "") != "INPUT" or it.socket_type in ("NodeSocketGeometry", "NodeSocketMaterial"): continue
            v = mod_input_get(mod, it.name)
            vals[it.name] = v if isinstance(v, (int, float, str, bool)) else (list(v) if v is not None else None)
        data = {}
        try:
            with open(PRESET_FILE) as f: data = json.load(f)
        except (OSError, ValueError): pass
        data[self.name] = vals
        os.makedirs(os.path.dirname(PRESET_FILE), exist_ok=True)
        with open(PRESET_FILE, "w") as f: json.dump(data, f, indent=1)
        self.report({"INFO"}, "Saved preset %r" % self.name)
        return {"FINISHED"}


class MRSAW_OT_add_lines(bpy.types.Operator):
    bl_idname = "mrs_aw.add_marking_lines"; bl_label = "Add Marking Lines"
    bl_options = {"REGISTER", "UNDO"}
    length: FloatProperty(name="Length", default=10.0, min=0.5, unit="LENGTH")

    def execute(self, context):
        _mrs(); from mrs import markinglines
        c = context.scene.cursor.location
        o = markinglines.add_marking_lines("Marking Lines", [(c.x, c.y, c.z), (c.x, c.y + self.length, c.z)], context.collection)
        for s in context.selected_objects: s.select_set(False)
        o.select_set(True); context.view_layer.objects.active = o
        return {"FINISHED"}


class MRSAW_PT_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"; bl_region_type = "UI"; bl_category = "MRS"; bl_label = "Area Junctions"

    def draw(self, context):
        lay = self.layout
        lay.operator("mrs_aw.build_groups", icon="NODETREE")
        box = lay.box(); box.label(text="Roads and junctions", icon="MOD_CURVE")
        box.operator("mrs_aw.set_tongues", icon="IPO_CONSTANT")
        box.operator("mrs_aw.add_junction", icon="SNAP_FACE")
        box = lay.box(); box.label(text="Extensions", icon="MOD_BUILD")
        grid = box.grid_flow(columns=2, align=True)
        for k, label in (("square", "Square"), ("round", "Round"), ("curve", "Curve"), ("island", "Island")):
            grid.operator("mrs_aw.add_extension", text=label).kind = k
        box = lay.box(); box.label(text="Signs and markings", icon="FONT_DATA")
        box.operator_menu_enum("mrs_aw.add_sign", "preset", text="Add Custom Sign")
        box.operator("mrs_aw.save_sign_preset", icon="FILE_TICK")
        box.operator("mrs_aw.add_marking_lines", icon="IPO_LINEAR")
        o = context.active_object
        if o is not None:
            for m in o.modifiers:
                if m.type == "NODES" and m.node_group and m.node_group.name.startswith("MRS_"):
                    lay.label(text="%s: edit in the Modifier properties" % m.node_group.name, icon="INFO")


CLASSES = (MRSAW_Preferences, MRSAW_OT_build, MRSAW_OT_add_junction, MRSAW_OT_add_extension, MRSAW_OT_set_tongues, MRSAW_OT_add_sign,
           MRSAW_OT_save_sign, MRSAW_OT_add_lines, MRSAW_PT_panel)


def register():
    for c in CLASSES: bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES): bpy.utils.unregister_class(c)
