"""procmat.road_adapter: put procmat materials on Mert Road Studio objects without importing the road tool (D1).

Roads are curve objects with a Geometry Nodes modifier "MRS_Road" (node group MRS_Road). Its material inputs:
    Asphalt Material, Marking Material, Yellow Marking Material, Concrete Material, Paving Material,
    Tactile Material, Cycleway Material, Bus Lane Material, Structure Material, Embankment Material
Two menus override a socket with a built-in road-tool material unless they are "Default":
    Asphalt Condition (Default / New / Worn / Wet / Patched) -> MRS_Asphalt<Condition> instead of Asphalt Material
    Sidewalk Surface  (Default / Tiles / Hexagon / Cobblestone / Brick / Gravel) -> MRS_Paving<Surface> instead of Paving Material
so assign() sets the menu to "Default" whenever it assigns Asphalt Material / Paving Material.

The road tool's own set_road() / refresh_all() re-apply its MRS_* materials to every material input; assign()
records its choices on the object (custom property "pm_materials") so reapply() can restore them afterwards.

Bus shelter glass (tools/roads/mrs/furniture.py): objects MRS_F_BusShelter and MRS_F_BusShelter_LOD1 carry two
slots, 0 = MRS_FurnitureAtlas, 1 = MRS_FurnitureGlass (the glass panels). Older placeholder shelters use
MRS_PropGlass (assets.py MRS_BusShelter / MRS_BusStopShelter slot 1; structures.bus_stop: the whole mesh).
"""
import bpy

ROAD_MODIFIER = "MRS_Road"
ROAD_GROUP = "MRS_Road"
MATERIAL_SOCKETS = ("Asphalt Material", "Marking Material", "Yellow Marking Material", "Concrete Material", "Paving Material",
                    "Tactile Material", "Cycleway Material", "Bus Lane Material", "Structure Material", "Embankment Material")
MENU_FOR_SOCKET = {"Asphalt Material": ("Asphalt Condition", "Default"), "Paving Material": ("Sidewalk Surface", "Default")}
DEFAULT_MAPPING = {"Asphalt Material": "PM_Asphalt", "Paving Material": "PM_Cobblestone"}
SHELTER_GLASS = {"MRS_F_BusShelter": "MRS_FurnitureGlass", "MRS_F_BusShelter_LOD1": "MRS_FurnitureGlass"}
GLASS_MATERIALS = ("MRS_FurnitureGlass", "MRS_PropGlass")
RECORD = "pm_materials"


# ------------------------------------------------------------------------------------------ modifier inputs
def road_modifier(obj):
    """The road's Geometry Nodes modifier (named MRS_Road, or any NODES modifier using the MRS_Road group)."""
    mod = obj.modifiers.get(ROAD_MODIFIER)
    if mod is not None and mod.type == "NODES" and mod.node_group is not None: return mod
    for m in obj.modifiers:
        if m.type == "NODES" and m.node_group is not None and m.node_group.name.startswith(ROAD_GROUP): return m
    return None


def is_road(obj):
    return obj is not None and road_modifier(obj) is not None


def _item(mod, name):
    for i in mod.node_group.interface.items_tree:
        if getattr(i, "item_type", "SOCKET") == "SOCKET" and i.in_out == "INPUT" and i.name == name: return i
    return None


def _entry(mod, ident):
    props = getattr(mod, "properties", None)
    if props is None or not hasattr(props, "inputs"): return None
    e = getattr(props.inputs, ident, None)
    if e is None:
        try: e = props.inputs[ident]
        except (KeyError, TypeError, IndexError): e = None
    return e


def get_input(mod, name):
    """A modifier input value by its interface name (Blender 5.x: mod.properties.inputs.<identifier>.value)."""
    it = _item(mod, name)
    if it is None: raise KeyError("%s has no input %r" % (mod.node_group.name, name))
    e = _entry(mod, it.identifier)
    if e is not None: return e.value
    v = mod.get(it.identifier)
    return v if v is not None else getattr(it, "default_value", None)


def set_input(mod, name, value):
    """Set a modifier input by its interface name (menus take their item name, e.g. "Default")."""
    it = _item(mod, name)
    if it is None: raise KeyError("%s has no input %r" % (mod.node_group.name, name))
    e = _entry(mod, it.identifier)
    if e is not None:
        e.value = value; return "properties"
    mod[it.identifier] = value
    return "idprop"


# ------------------------------------------------------------------------------------------ roads
def material_sockets(road_obj):
    """Names of the road modifier's material inputs, in interface order."""
    mod = road_modifier(road_obj)
    if mod is None: return []
    return [i.name for i in mod.node_group.interface.items_tree
            if getattr(i, "item_type", "SOCKET") == "SOCKET" and i.in_out == "INPUT" and i.socket_type == "NodeSocketMaterial"]


def _material(m):
    if m is None or isinstance(m, bpy.types.Material): return m
    mat = bpy.data.materials.get(m) or bpy.data.materials.get("PM_" + m)
    if mat is None: raise KeyError("no material %r" % m)
    return mat


def assign(road_obj, socket_name, material, default_menu=True, record=True):
    """Set the road's material input `socket_name` (e.g. "Asphalt Material") to `material` (a Material or name).
    For Asphalt Material / Paving Material the menu that would override it (Asphalt Condition / Sidewalk Surface)
    is set to "Default" (also in the object's remembered road inputs "mrs_inputs" when present), so the socket's
    material is the one the road uses. Returns a report dict."""
    mod = road_modifier(road_obj)
    if mod is None: raise ValueError("%s is not a Mert Road Studio road (no %s modifier)" % (road_obj.name, ROAD_MODIFIER))
    if socket_name not in material_sockets(road_obj):
        raise KeyError("%s: %r is not a material input (have %s)" % (road_obj.name, socket_name, material_sockets(road_obj)))
    mat = _material(material)
    prev = get_input(mod, socket_name)
    how = set_input(mod, socket_name, mat)
    rep = {"object": road_obj.name, "socket": socket_name, "material": mat.name if mat else None,
           "previous": getattr(prev, "name", prev), "set_via": how, "menu": None}
    if default_menu and socket_name in MENU_FOR_SOCKET:
        menu, val = MENU_FOR_SOCKET[socket_name]
        if _item(mod, menu) is not None:
            old = get_input(mod, menu)
            set_input(mod, menu, val)
            rep["menu"] = (menu, old, val)
            stored = road_obj.get("mrs_inputs")
            if stored is not None and menu in stored:
                d = dict(stored); d[menu] = val; road_obj["mrs_inputs"] = d
    if record:
        rec = dict(road_obj.get(RECORD, {})); rec[socket_name] = mat.name if mat else ""
        road_obj[RECORD] = rec
    road_obj.update_tag()
    return rep


def roads(collection=None):
    objs = collection.all_objects if collection is not None else bpy.data.objects
    return [o for o in objs if o.type == "CURVE" and is_road(o)]


def assign_roads(collection=None, mapping=None):
    """assign() on every road in `collection` (default: all roads): mapping = {socket: material or name}; pairs
    whose material does not exist are skipped. Returns the reports."""
    mapping = dict(DEFAULT_MAPPING if mapping is None else mapping)
    reps = []
    for sock, m in mapping.items():
        try: mat = _material(m)
        except KeyError:
            print("[procmat.road_adapter] %s: material %r not found, skipped" % (sock, m)); continue
        for o in roads(collection):
            if sock in material_sockets(o): reps.append(assign(o, sock, mat))
    return reps


def reapply(collection=None):
    """Re-assign the materials recorded by assign() (after the road tool's set_road / refresh_all reset them)."""
    reps = []
    for o in roads(collection):
        for sock, name in dict(o.get(RECORD, {})).items():
            mat = bpy.data.materials.get(name)
            if mat is not None and sock in material_sockets(o): reps.append(assign(o, sock, mat))
    return reps


def evaluated_materials(obj, depsgraph=None):
    """{material name: face count} of the evaluated mesh (what the road really renders with)."""
    if depsgraph is None:
        sc = obj.users_scene[0] if obj.users_scene else bpy.context.scene
        vl = sc.view_layers[0]; vl.update(); depsgraph = vl.depsgraph
    ev = obj.evaluated_get(depsgraph); me = ev.to_mesh()
    try:
        mats = [m.name if m else None for m in me.materials]
        counts = {}
        idx = [0] * len(me.polygons); me.polygons.foreach_get("material_index", idx)
        for i in idx:
            if 0 <= i < len(mats) and mats[i]: counts[mats[i]] = counts.get(mats[i], 0) + 1
        return counts
    finally:
        ev.to_mesh_clear()


# ------------------------------------------------------------------------------------------ furniture slots
def replace_slot_materials(obj, name_contains, material, per_object=False):
    """Put `material` in every slot of `obj` whose material name contains `name_contains` (e.g. "FurnitureGlass").
    per_object=False changes the mesh's slot (every object using that mesh); True links the slot to the object.
    Returns [(slot index, previous material name)]."""
    mat = _material(material); out = []
    for i, slot in enumerate(obj.material_slots):
        cur = slot.material
        if cur is None or name_contains not in cur.name: continue
        if per_object: slot.link = "OBJECT"
        slot.material = mat
        out.append((i, cur.name))
    return out


def shelter_glass_slots():
    """{object name: [(slot index, material name)]} of the bus shelters' glass slots present in this file."""
    out = {}
    for o in bpy.data.objects:
        if o.type != "MESH": continue
        hits = [(i, s.material.name) for i, s in enumerate(o.material_slots) if s.material and s.material.name in GLASS_MATERIALS]
        if hits and ("Shelter" in o.name or o.name in SHELTER_GLASS): out[o.name] = hits
    return out


def assign_shelter_glass(material, objects=None, per_object=False):
    """Replace the bus shelters' glass (MRS_FurnitureGlass / MRS_PropGlass slots) with `material`."""
    objs = objects if objects is not None else [bpy.data.objects[n] for n in shelter_glass_slots()]
    out = {}
    for o in objs:
        for g in GLASS_MATERIALS:
            r = replace_slot_materials(o, g, material, per_object)
            if r: out.setdefault(o.name, []).extend(r)
    return out
