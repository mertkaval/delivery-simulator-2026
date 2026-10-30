"""N-panel 'Road Studio' (View3D > sidebar): roads, presets, terrain, junctions, structures, materials,
export. Every button maps to a function in the package so the API and the UI stay the same."""
import bpy, os, json
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


class MRS_OT_junction_settings(bpy.types.Operator):
    """Settings of the active junction (its build parameters); tweak them in the Adjust Last Operation panel and the
    junction rebuilds from its roads each time"""
    bl_idname = "mrs.junction_settings"; bl_label = "Junction Settings"; bl_options = {"REGISTER", "UNDO"}
    control: bpy.props.EnumProperty(items=[(k, k.title(), "") for k in junction.CONTROLS], name="Control")
    crossing: bpy.props.EnumProperty(items=[("zebra", "Zebra", ""), ("parallel", "Parallel lines", "")], name="Crossing")
    crosswalks: bpy.props.BoolProperty(name="Crossings", default=True)
    stop_lines: bpy.props.BoolProperty(name="End markings", default=True, description="Stop line / STOP / give way by control")
    bike_crossings: bpy.props.BoolProperty(name="Cycle crossings", default=True)
    refuge: bpy.props.BoolProperty(name="Median refuges", default=True)
    box: bpy.props.BoolProperty(name="Yellow box", default=False)
    corner_radius: bpy.props.FloatProperty(name="Corner radius", default=6.0, min=1.0, max=40.0, unit="LENGTH")
    crossing_width: bpy.props.FloatProperty(name="Crossing width", default=2.5, min=1.0, max=8.0, unit="LENGTH")
    stop_setback: bpy.props.FloatProperty(name="Crossing setback", default=0.6, min=0.0, max=10.0, unit="LENGTH")
    KEYS = ("control", "crossing", "crosswalks", "stop_lines", "bike_crossings", "refuge", "box", "corner_radius", "crossing_width", "stop_setback")

    @classmethod
    def poll(cls, ctx):
        o = ctx.active_object
        return o is not None and o.get("mrs_junction") is not None and dict(o["mrs_junction"]).get("type", "junction") == "junction"

    def invoke(self, ctx, event):
        m = ctx.active_object["mrs_junction"]; m = m.to_dict() if hasattr(m, "to_dict") else dict(m)
        p = dict(m.get("params") or {}); p.setdefault("control", m.get("control", "none"))
        for k in self.KEYS:
            if p.get(k) is not None:
                try: setattr(self, k, p[k])
                except Exception: pass
        return self.execute(ctx)

    def execute(self, ctx):
        o = junction.configure(ctx.active_object, **{k: getattr(self, k) for k in self.KEYS})
        if o is not None: o.select_set(True); ctx.view_layer.objects.active = o
        return {"FINISHED"}


class MRS_OT_place(bpy.types.Operator):
    """Place the street assets (lights, signals' cabinets, signs by control and speed, bus stops, benches, bins,
    hydrants, drains, trees) on every road of the collection by the placement rules"""
    bl_idname = "mrs.place"; bl_label = "Place Street Assets"; bl_options = {"REGISTER", "UNDO"}
    seed: bpy.props.IntProperty(name="Seed", default=0)

    def execute(self, ctx):
        from . import placement
        rep = placement.place_all(_roads_collection(ctx), seed=self.seed); ctx.scene["mrs_place_seed"] = self.seed
        self.report({"INFO"}, "%d placed, %d skipped" % (len(rep["placed"]), len(rep["skipped"]))); return {"FINISHED"}


class MRS_OT_auto_place(bpy.types.Operator):
    """Toggle re-placing the street assets after every automatic junction rebuild"""
    bl_idname = "mrs.auto_place"; bl_label = "Auto-place Street Assets"

    def execute(self, ctx):
        ctx.scene["mrs_auto_place"] = not ctx.scene.get("mrs_auto_place", False); return {"FINISHED"}


class MRS_OT_validate(bpy.types.Operator):
    """Check every road, junction and sign against the rules the tool derives them from (paint clear zones, arrows,
    end markings, cycle crossings, signal heads, speed signs); selects the objects with problems"""
    bl_idname = "mrs.validate"; bl_label = "Validate"

    def execute(self, ctx):
        from . import validate
        col = _roads_collection(ctx)
        rep = validate.validate(col, bpy.data.collections.get(col.name + "_Placed"))
        ctx.scene["mrs_validation"] = json.dumps({"counts": rep["counts"], "problems": rep["problems"][:40]})
        bad = {p["object"] for p in rep["problems"]}
        for o in ctx.selected_objects: o.select_set(False)
        for n in bad:
            if n in bpy.data.objects and bpy.data.objects[n].name in ctx.view_layer.objects: bpy.data.objects[n].select_set(True)
        self.report({"INFO"} if not bad else {"WARNING"}, "%d problems on %d objects" % (len(rep["problems"]), len(bad))); return {"FINISHED"}


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
    """A parametric sign (MRS_CustomSign) at the 3D cursor: panel, post, texts, images and lines stay editable in the
    Modifier panel"""
    bl_idname = "mrs.custom_sign"; bl_label = "Custom Sign at Cursor"; bl_options = {"REGISTER", "UNDO"}
    preset: bpy.props.EnumProperty(items=[("CRM 2.1", "Blue Info", "Blue panel, two lines of text and a bar"), ("Stop", "Stop", "Red octagon")], default="CRM 2.1")
    text: bpy.props.StringProperty(default="MAIN STREET", description="First text line (empty: the preset's own text)")

    def execute(self, ctx):
        from . import customsign
        c = ctx.scene.cursor.location
        extra = {"L1 T1 Text": self.text} if self.text else {}
        o = customsign.add_custom_sign("Custom Sign", (c.x, c.y, c.z), self.preset, _roads_collection(ctx), **extra)
        ctx.view_layer.objects.active = o
        return {"FINISHED"}


def _collection_named(ctx, name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name); ctx.scene.collection.children.link(c)
    return c


class MRS_OT_set_tongues(bpy.types.Operator):
    """Leave the first / last metres of every selected road as a tongue: a footprint an area junction builds over"""
    bl_idname = "mrs.set_tongues"; bl_label = "Set Tongues"; bl_options = {"REGISTER", "UNDO"}
    start: bpy.props.FloatProperty(name="Start", default=10.0, min=0.0, max=200.0, unit="LENGTH")
    end: bpy.props.FloatProperty(name="End", default=10.0, min=0.0, max=200.0, unit="LENGTH")

    def execute(self, ctx):
        n = 0
        for o in _selected_roads(ctx):
            mod = o.modifiers["MRS_Road"]; mod_input_set(mod, "Tongue Start", self.start); mod_input_set(mod, "Tongue End", self.end); o.update_tag(); n += 1
        self.report({"INFO"}, "tongues on %d roads" % n)
        return {"FINISHED"}


class MRS_OT_add_area_junction(bpy.types.Operator):
    """An area junction at the 3D cursor: every tongue and extension of the Roads collection within Range becomes one
    junction mesh (the selected roads and extensions are moved into Roads)"""
    bl_idname = "mrs.add_area_junction"; bl_label = "Area Junction at Cursor"; bl_options = {"REGISTER", "UNDO"}
    distance: bpy.props.FloatProperty(name="Range", default=40.0, min=1.0, max=1000.0, unit="LENGTH")

    def execute(self, ctx):
        from . import areajunction
        rc = _collection_named(ctx, "Roads"); jc = _collection_named(ctx, "Junctions")
        for o in ctx.selected_objects:
            if any(m.type == "NODES" and m.node_group and m.node_group.name in ("MRS_Road", "MRS_ExtensionMesh", "MRS_ExtensionCurve") for m in o.modifiers):
                for c in list(o.users_collection): c.objects.unlink(o)
                rc.objects.link(o)
        o = areajunction.add_area_junction("Area Junction", tuple(ctx.scene.cursor.location), rc, jc, Distance=self.distance)
        ctx.view_layer.objects.active = o
        return {"FINISHED"}


class MRS_OT_add_extension(bpy.types.Operator):
    """An extension (a free-form road area: bus bay, car park, cul-de-sac, roundabout) at the 3D cursor"""
    bl_idname = "mrs.add_extension"; bl_label = "Add Extension"; bl_options = {"REGISTER", "UNDO"}
    kind: bpy.props.EnumProperty(items=[("square", "Square", ""), ("round", "Round", ""), ("curve", "Curve", ""), ("island", "Island", "")])
    size: bpy.props.FloatProperty(name="Size", default=10.0, min=1.0, max=200.0, unit="LENGTH")

    def execute(self, ctx):
        from . import areajunction
        rc = _collection_named(ctx, "Roads"); c = ctx.scene.cursor.location
        if self.kind == "curve":
            o = areajunction.add_extension("Extension", "curve", rc, points=[(c.x - self.size / 2, c.y, c.z), (c.x + self.size / 2, c.y, c.z)])
        else:
            o = areajunction.add_extension("Extension", "round" if self.kind in ("round", "island") else "square", rc, tuple(c), (self.size, self.size),
                                           **({"Island": True} if self.kind == "island" else {}))
        ctx.view_layer.objects.active = o
        return {"FINISHED"}


class MRS_OT_add_marking_lines(bpy.types.Operator):
    """Painted lines along a new curve at the 3D cursor (add an Array modifier for parking bays)"""
    bl_idname = "mrs.add_marking_lines"; bl_label = "Marking Lines at Cursor"; bl_options = {"REGISTER", "UNDO"}
    length: bpy.props.FloatProperty(name="Length", default=10.0, min=0.5, max=500.0, unit="LENGTH")

    def execute(self, ctx):
        from . import markinglines
        c = ctx.scene.cursor.location
        o = markinglines.add_marking_lines("Marking Lines", [(c.x, c.y, c.z), (c.x, c.y + self.length, c.z)], _roads_collection(ctx))
        ctx.view_layer.objects.active = o
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
        box.operator("mrs.junction_settings", icon="PREFERENCES")
        box = L.box(); box.label(text="Area junctions (tongues)", icon="SNAP_FACE")
        box.operator("mrs.set_tongues"); box.operator("mrs.add_area_junction")
        row = box.row(align=True)
        for k, t in (("square", "Square"), ("round", "Round"), ("curve", "Curve"), ("island", "Island")): row.operator("mrs.add_extension", text=t).kind = k
        box.operator("mrs.add_marking_lines")
        box = L.box(); box.label(text="Street assets + checks", icon="CHECKMARK")
        row = box.row(align=True); row.operator("mrs.place")
        row.operator("mrs.auto_place", text="Auto: " + ("on" if ctx.scene.get("mrs_auto_place") else "off"), depress=bool(ctx.scene.get("mrs_auto_place")))
        box.operator("mrs.validate")
        if ctx.scene.get("mrs_validation"):
            v = json.loads(ctx.scene["mrs_validation"])
            box.label(text="ok" if not v["problems"] else ", ".join("%s %d" % kv for kv in v["counts"].items()), icon="INFO" if not v["problems"] else "ERROR")
            for p in v["problems"][:6]: box.label(text="%s: %s" % (p["object"], p["message"])[:70])
        box = L.box(); box.label(text="Structures", icon="MOD_BUILD")
        row = box.row(align=True)
        for k, t in (("gantry", "Gantry"), ("bus", "Bus Stop"), ("stays", "Stays"), ("tunnel", "Tunnel")): row.operator("mrs.structure", text=t).kind = k
        box.operator_menu_enum("mrs.custom_sign", "preset", text="Custom Sign at Cursor")
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
           MRS_OT_add_dead_end, MRS_OT_rebuild_junctions, MRS_OT_auto_update, MRS_OT_junction_settings, MRS_OT_place, MRS_OT_auto_place, MRS_OT_validate, MRS_OT_structure, MRS_OT_custom_sign, MRS_OT_set_tongues, MRS_OT_add_area_junction, MRS_OT_add_extension,
           MRS_OT_add_marking_lines, MRS_OT_material_preset, MRS_OT_export,
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
