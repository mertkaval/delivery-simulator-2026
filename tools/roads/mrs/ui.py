"""N-panel 'Road Studio' (View3D > sidebar): roads, presets, terrain, junctions, structures, materials,
export. Every button maps to a function in the package so the API and the UI stay the same."""
import bpy, os
from .nodes import MRS, mod_input_set, mod_input_get
from . import roads, junction, structures, materials, terrain, export as export_mod


def _roads_collection(ctx):
    col = bpy.data.collections.get(MRS + "Roads") or bpy.data.collections.new(MRS + "Roads")
    if col.name not in ctx.scene.collection.children: ctx.scene.collection.children.link(col)
    return col


def _selected_roads(ctx):
    return [o for o in ctx.selected_objects if o.type == "CURVE" and "MRS_Road" in o.modifiers]


class MRS_OT_add_road(bpy.types.Operator):
    """Add a road at the 3D cursor (or turn the active curve into a road)"""
    bl_idname = "mrs.add_road"; bl_label = "Add Road"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.EnumProperty(items=[(k, k.title(), "") for k in roads.PRESETS], default="residential")

    def execute(self, ctx):
        col = _roads_collection(ctx)
        o = ctx.active_object
        ter = ctx.scene.get("mrs_terrain")
        ter = bpy.data.objects.get(ter) if ter else None
        if o and o.type == "CURVE" and "MRS_Road" not in o.modifiers:
            roads.add_road_modifier(o, self.preset, terrain=ter)
        else:
            c = ctx.scene.cursor.location
            o = roads.make_road("MRS_Road", [(c.x, c.y, c.z), (c.x + 30, c.y, c.z), (c.x + 60, c.y, c.z)], col, self.preset, terrain=ter)
        ctx.view_layer.objects.active = o
        return {"FINISHED"}


class MRS_OT_apply_preset(bpy.types.Operator):
    """Apply a road preset to the selected roads"""
    bl_idname = "mrs.apply_preset"; bl_label = "Apply Road Preset"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.EnumProperty(items=[(k, k.title(), "") for k in roads.PRESETS], default="residential")

    def execute(self, ctx):
        n = 0
        for o in _selected_roads(ctx): roads.set_road(o, self.preset); o["mrs_preset"] = self.preset; n += 1
        self.report({"INFO"}, "%d roads set to %s" % (n, self.preset)); return {"FINISHED"}


class MRS_OT_set_terrain(bpy.types.Operator):
    """Use the active mesh as the terrain for new and selected roads"""
    bl_idname = "mrs.set_terrain"; bl_label = "Use Active as Terrain"; bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        if not o or o.type != "MESH": self.report({"ERROR"}, "select a terrain mesh"); return {"CANCELLED"}
        ctx.scene["mrs_terrain"] = o.name
        for r in _selected_roads(ctx): roads.set_road(r, terrain=o)
        self.report({"INFO"}, "terrain: " + o.name); return {"FINISHED"}


class MRS_OT_conform_terrain(bpy.types.Operator):
    """Pull the terrain to the roads (a conformed copy carries the modifier; the source stays hidden)"""
    bl_idname = "mrs.conform_terrain"; bl_label = "Pull Terrain to Roads"; bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        nm = ctx.scene.get("mrs_terrain"); src = bpy.data.objects.get(nm) if nm else None
        if src is None: self.report({"ERROR"}, "set a terrain first"); return {"CANCELLED"}
        terrain.conform_terrain(src, _roads_collection(ctx))
        return {"FINISHED"}


class MRS_OT_demo_terrain(bpy.types.Operator):
    """Generate a hilly demo terrain"""
    bl_idname = "mrs.demo_terrain"; bl_label = "Demo Terrain"; bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        t = terrain.demo_terrain(collection=_roads_collection(ctx)); ctx.scene["mrs_terrain"] = t.name; return {"FINISHED"}


class MRS_OT_add_junction(bpy.types.Operator):
    """Connect the selected roads whose ends meet at the 3D cursor"""
    bl_idname = "mrs.add_junction"; bl_label = "Connect Roads at Cursor"; bl_options = {"REGISTER", "UNDO"}
    crosswalks: bpy.props.BoolProperty(default=True); stop_lines: bpy.props.BoolProperty(default=True)
    traffic_lights: bpy.props.BoolProperty(default=False); corner_radius: bpy.props.FloatProperty(default=6.0, min=1.0, max=30.0)

    def execute(self, ctx):
        rs = _selected_roads(ctx)
        nm = ctx.scene.get("mrs_terrain"); ter = bpy.data.objects.get(nm) if nm else None
        try:
            j = junction.build_junction("MRS_Junction_%d" % len(junction.all_junctions()), ctx.scene.cursor.location, rs, _roads_collection(ctx),
                                        self.crosswalks, self.stop_lines, self.corner_radius, self.traffic_lights, terrain=ter)
        except ValueError as e:
            self.report({"ERROR"}, str(e)); return {"CANCELLED"}
        self.report({"INFO"}, "junction %s: %d roads" % (j.name, len(j["mrs_junction"]["roads"]))); return {"FINISHED"}


class MRS_OT_add_roundabout(bpy.types.Operator):
    """Roundabout at the 3D cursor joining the selected roads"""
    bl_idname = "mrs.add_roundabout"; bl_label = "Roundabout at Cursor"; bl_options = {"REGISTER", "UNDO"}
    island_radius: bpy.props.FloatProperty(default=8.0, min=2.0, max=60.0); lanes: bpy.props.IntProperty(default=1, min=1, max=3)

    def execute(self, ctx):
        nm = ctx.scene.get("mrs_terrain"); ter = bpy.data.objects.get(nm) if nm else None
        try:
            junction.build_roundabout("MRS_Roundabout_%d" % len(junction.all_junctions()), ctx.scene.cursor.location, _selected_roads(ctx), _roads_collection(ctx),
                                      island_radius=self.island_radius, lanes=self.lanes, terrain=ter)
        except ValueError as e:
            self.report({"ERROR"}, str(e)); return {"CANCELLED"}
        return {"FINISHED"}


class MRS_OT_add_dead_end(bpy.types.Operator):
    """Turning circle at the end of the active road nearest the 3D cursor"""
    bl_idname = "mrs.add_dead_end"; bl_label = "Dead End at Cursor"; bl_options = {"REGISTER", "UNDO"}
    radius: bpy.props.FloatProperty(default=9.0, min=4.0, max=30.0)

    def execute(self, ctx):
        rs = _selected_roads(ctx)
        if not rs: self.report({"ERROR"}, "select a road"); return {"CANCELLED"}
        r = rs[0]; c = ctx.scene.cursor.location
        (p0, _, _), (p1, _, _) = roads.road_ends(r)
        end = "start" if (p0 - c).length < (p1 - c).length else "end"
        nm = ctx.scene.get("mrs_terrain"); ter = bpy.data.objects.get(nm) if nm else None
        junction.build_dead_end(r.name + "_deadend", r, end, self.radius, _roads_collection(ctx), ter)
        return {"FINISHED"}


class MRS_OT_rebuild_junctions(bpy.types.Operator):
    """Rebuild every junction from its roads' current curves"""
    bl_idname = "mrs.rebuild_junctions"; bl_label = "Rebuild Junctions"; bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        n = len(junction.rebuild_all()); self.report({"INFO"}, "%d junctions rebuilt" % n); return {"FINISHED"}


class MRS_OT_auto_update(bpy.types.Operator):
    """Toggle automatic junction rebuilds when a road curve is edited"""
    bl_idname = "mrs.auto_update"; bl_label = "Auto-update Junctions"

    def execute(self, ctx):
        on = not ctx.scene.get("mrs_auto", False); ctx.scene["mrs_auto"] = on; junction.enable_auto_update(on)
        self.report({"INFO"}, "auto-update " + ("on" if on else "off")); return {"FINISHED"}


class MRS_OT_structure(bpy.types.Operator):
    """Add a structure on the active road at the 3D cursor's distance along it"""
    bl_idname = "mrs.structure"; bl_label = "Add Structure"; bl_options = {"REGISTER", "UNDO"}
    kind: bpy.props.EnumProperty(items=[("gantry", "Gantry Sign", ""), ("bus", "Bus Stop", ""), ("stays", "Cable Stays", ""), ("tunnel", "Tunnel (40 m)", "")])
    text: bpy.props.StringProperty(default="EXIT 12")

    def execute(self, ctx):
        rs = _selected_roads(ctx)
        if not rs: self.report({"ERROR"}, "select a road"); return {"CANCELLED"}
        r = rs[0]; c = ctx.scene.cursor.location
        # distance along the road: nearest centre-line sample to the cursor
        L = structures.road_length(r); best = min((((structures.road_sample(r, a)[0] - c).length, a) for a in [L * k / 40 for k in range(41)]))[1]
        col = _roads_collection(ctx)
        if self.kind == "gantry": structures.gantry_sign(r, best, tuple(t.strip() for t in self.text.split("|")), col)
        elif self.kind == "bus": structures.bus_stop(r, best, 1, col)
        elif self.kind == "stays": structures.cable_stays(r, col)
        elif self.kind == "tunnel": structures.tunnel(r, max(0, best - 20), min(L, best + 20), col)
        return {"FINISHED"}


class MRS_OT_custom_sign(bpy.types.Operator):
    """A sign post with your text at the 3D cursor"""
    bl_idname = "mrs.custom_sign"; bl_label = "Custom Sign at Cursor"; bl_options = {"REGISTER", "UNDO"}
    text: bpy.props.StringProperty(default="MAIN STREET"); circle: bpy.props.BoolProperty(default=False)

    def execute(self, ctx):
        c = ctx.scene.cursor.location
        structures.text_sign(self.text, (c.x, c.y, c.z), 0.0, _roads_collection(ctx), "circle" if self.circle else "rect",
                             (0.8, 0.05, 0.05) if self.circle else (0.02, 0.22, 0.09))
        return {"FINISHED"}


class MRS_OT_material_preset(bpy.types.Operator):
    """Material preset for all road materials"""
    bl_idname = "mrs.material_preset"; bl_label = "Material Preset"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.StringProperty(default="dry")

    def execute(self, ctx):
        materials.apply_material_preset(self.preset); return {"FINISHED"}


class MRS_OT_export(bpy.types.Operator):
    """Export the roads collection as GLB (+ collision GLB), instances realized"""
    bl_idname = "mrs.export"; bl_label = "Export GLB (+ collision)"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="//mrs_roads.glb")

    def invoke(self, ctx, event):
        ctx.window_manager.fileselect_add(self); return {"RUNNING_MODAL"}

    def execute(self, ctx):
        st = export_mod.export_glb(bpy.path.abspath(self.filepath), _roads_collection(ctx).name)
        self.report({"INFO"}, "exported %d objects, %d tris" % (st["objects"], st["tris"])); return {"FINISHED"}


class MRS_OT_export_ready(bpy.types.Operator):
    """Convert the selected roads to plain meshes with instances realized (keeps the originals hidden)"""
    bl_idname = "mrs.export_ready"; bl_label = "Make Export-Ready Meshes"; bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        n = len(export_mod.export_ready(_selected_roads(ctx) or roads.all_roads(_roads_collection(ctx)), _roads_collection(ctx)))
        self.report({"INFO"}, "%d meshes" % n); return {"FINISHED"}


class MRS_PT_panel(bpy.types.Panel):
    bl_label = "Mert Road Studio"; bl_space_type = "VIEW_3D"; bl_region_type = "UI"; bl_category = "Road Studio"

    def draw(self, ctx):
        L = self.layout
        box = L.box(); box.label(text="Roads", icon="CURVE_BEZCURVE")
        row = box.row(align=True)
        for k in list(roads.PRESETS)[:3]: row.operator("mrs.add_road", text=k.title()).preset = k
        row = box.row(align=True)
        for k in list(roads.PRESETS)[3:]: row.operator("mrs.add_road", text=k.title()).preset = k
        box.label(text="Selected roads -> preset:")
        row = box.row(align=True)
        for k in list(roads.PRESETS)[:3]: row.operator("mrs.apply_preset", text=k.title()).preset = k
        row = box.row(align=True)
        for k in list(roads.PRESETS)[3:]: row.operator("mrs.apply_preset", text=k.title()).preset = k
        box = L.box(); box.label(text="Terrain", icon="RNDCURVE")
        box.label(text="terrain: " + str(ctx.scene.get("mrs_terrain", "-")))
        row = box.row(align=True); row.operator("mrs.set_terrain"); row.operator("mrs.demo_terrain")
        box.operator("mrs.conform_terrain")
        box = L.box(); box.label(text="Junctions", icon="MOD_BOOLEAN")
        box.operator("mrs.add_junction"); box.operator("mrs.add_roundabout"); box.operator("mrs.add_dead_end")
        row = box.row(align=True); row.operator("mrs.rebuild_junctions")
        row.operator("mrs.auto_update", text="Auto: " + ("on" if ctx.scene.get("mrs_auto") else "off"), depress=bool(ctx.scene.get("mrs_auto")))
        box = L.box(); box.label(text="Structures", icon="MOD_BUILD")
        row = box.row(align=True)
        for k, t in (("gantry", "Gantry"), ("bus", "Bus Stop"), ("stays", "Stays"), ("tunnel", "Tunnel")): row.operator("mrs.structure", text=t).kind = k
        box.operator("mrs.custom_sign")
        box = L.box(); box.label(text="Materials", icon="MATERIAL")
        names = list(materials.MATERIAL_PRESETS)
        for i in range(0, len(names), 3):
            row = box.row(align=True)
            for k in names[i:i + 3]: row.operator("mrs.material_preset", text=k.replace("_", " ").title()).preset = k
        box = L.box(); box.label(text="Export", icon="EXPORT")
        box.operator("mrs.export_ready"); box.operator("mrs.export")
        o = ctx.active_object
        if o and "MRS_Road" in o.modifiers:
            L.label(text="%s: %s" % (o.name, o.get("mrs_preset", "custom")), icon="MODIFIER")
            L.label(text="All road inputs: Modifier panel")


CLASSES = (MRS_OT_add_road, MRS_OT_apply_preset, MRS_OT_set_terrain, MRS_OT_conform_terrain, MRS_OT_demo_terrain, MRS_OT_add_junction, MRS_OT_add_roundabout,
           MRS_OT_add_dead_end, MRS_OT_rebuild_junctions, MRS_OT_auto_update, MRS_OT_structure, MRS_OT_custom_sign, MRS_OT_material_preset, MRS_OT_export,
           MRS_OT_export_ready, MRS_PT_panel)


def register():
    for c in CLASSES:
        try: bpy.utils.unregister_class(c)
        except Exception: pass
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try: bpy.utils.unregister_class(c)
        except Exception: pass
