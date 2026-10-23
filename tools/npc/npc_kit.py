"""NPC character kit for Blender 5.2 + MPFB 2 (Delivery Simulator 2026).

Builds townspeople the same way as the v3 courier: an MPFB human (macros + detail targets,
skin, eyes, brows, lashes, hair), the MPFB "game_engine" rig (53 bones, same names as the courier,
so every courier animation can be retargeted onto every NPC), garments grown from the body
surface (clean hems, no interpenetration), fabric textures painted per garment on a pattern UV
layout, an under-clothing body mask, 4-influence skin weights, and a GLB export.

Usage inside Blender:  ns = {}; exec(open(KIT).read(), ns); kit = ns["Kit"]("NPC01_...")
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

MPFB_USER = r"C:\Users\mert3\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\.user\blender_org\mpfb\data"
MPFB_SYS = r"C:\Users\mert3\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\blender_org\mpfb\data"
ROOT = r"C:\GodotProjects\delivery-simulator-2026\source_assets\npc"


def srgb(c):
    return tuple(((v / 255) / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4) for v in c) + (1.0,)


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


class Kit:
    def __init__(self, name):
        self.name = name
        self.dir = os.path.join(ROOT, name)
        self.tex = os.path.join(self.dir, "textures")
        os.makedirs(self.tex, exist_ok=True)
        os.makedirs(os.path.join(self.dir, "renders"), exist_ok=True)
        scn = bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
        scn.unit_settings.system = "METRIC"
        bpy.context.window.scene = scn
        self.scn = scn
        self.col = {}
        for c in ("Body", "Clothes", "Rig", "Stage"):
            full = "%s_%s" % (name, c)
            col = bpy.data.collections.get(full) or bpy.data.collections.new(full)
            if col.name not in scn.collection.children:
                scn.collection.children.link(col)
            self.col[c] = col
        self.body = None
        self.rig = None
        self.garments = []

    # ------------------------------------------------------------------ human
    def activate(self, which):
        lc = next(l for l in bpy.context.view_layer.layer_collection.children if l.collection == self.col[which])
        bpy.context.view_layer.active_layer_collection = lc

    def human(self, macros, targets=None, skin=None, eyes="brown", brows="eyebrow012", lashes="eyelashes01",
              hair=None, skin_tint=None, height_m=None):
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService
        from bl_ext.blender_org.mpfb.services.targetservice import TargetService
        from bl_ext.blender_org.mpfb.entities.objectproperties import HumanObjectProperties
        for old in [o for o in list(self.scn.objects) if not o.name.startswith(self.name + "_") or o.name.endswith(("_Body", "_Rig", "_Eyes", "_Eyebrows", "_Eyelashes", "_Hair"))]:
            if old.users_collection and any(c in self.col.values() for c in old.users_collection) and old.type in ("MESH", "ARMATURE") and "Floor" not in old.name:
                bpy.data.objects.remove(old, do_unlink=True)
        self.activate("Body")
        bpy.ops.mpfb.create_human()
        b = bpy.context.active_object
        b.name = self.name + "_Body"
        self.body = b
        for k, v in macros.items():
            HumanObjectProperties.set_value(k, v, entity_reference=b)
        TargetService.reapply_macro_details(b)
        if height_m:
            self.fit_height(height_m)
        for rel, w in (targets or {}).items():
            TargetService.load_target(b, os.path.join(MPFB_SYS, "targets", rel + ".target.gz"), weight=w)
        bpy.context.view_layer.update()
        if skin:
            HumanService.set_character_skin(os.path.join(MPFB_USER, "skins", skin, skin + ".mhmat"), b, skin_type="GAMEENGINE")
            if skin_tint:
                self.tint_body_texture(skin_tint)
        self.activate("Rig")
        rig = HumanService.add_builtin_rig(b, "game_engine", import_weights=True) or b.parent
        rig.name = self.name + "_Rig"
        for c in list(rig.users_collection):
            if c != self.col["Rig"]:
                c.objects.unlink(rig)
        if rig.name not in self.col["Rig"].objects:
            self.col["Rig"].objects.link(rig)
        self.rig = rig
        self.activate("Body")
        parts = {}
        eye_obj = HumanService.add_mhclo_asset(os.path.join(MPFB_USER, "eyes/high-poly/high-poly.mhclo"), b, asset_type="Eyes",
                                               subdiv_levels=0, material_type="MAKESKIN")
        parts["Eyes"] = eye_obj
        for kind, rel in (("Eyebrows", "eyebrows/%s/%s.mhclo" % (brows, brows)), ("Eyelashes", "eyelashes/%s/%s.mhclo" % (lashes, lashes))):
            parts[kind] = HumanService.add_mhclo_asset(os.path.join(MPFB_USER, rel), b, asset_type=kind, subdiv_levels=0, material_type="MAKESKIN")
        if hair:
            parts["Hair"] = HumanService.add_mhclo_asset(os.path.join(MPFB_USER, "hair/%s/%s.mhclo" % (hair, hair)), b,
                                                         asset_type="Hair", subdiv_levels=0, material_type="MAKESKIN")
        for k, o in parts.items():
            o.name = "%s_%s" % (self.name, k)
        self.parts = parts
        self.set_eye_color(eyes)
        return b

    def body_height(self):
        co = self.body_rest()
        return float(co[:, 2].max() - co[:, 2].min())

    def body_rest(self, world=True):
        b = self.body
        saved = [(m, m.show_viewport) for m in b.modifiers]
        for m, _ in saved:
            m.show_viewport = False
        bpy.context.view_layer.update()
        ev = b.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        co = np.array([tuple((b.matrix_world @ v.co) if world else v.co) for v in me.vertices], np.float32)
        ev.to_mesh_clear()
        for m, s in saved:
            m.show_viewport = s
        return co

    def fit_height(self, target_m, tol=0.004):
        from bl_ext.blender_org.mpfb.services.targetservice import TargetService
        from bl_ext.blender_org.mpfb.entities.objectproperties import HumanObjectProperties
        lo, hi = 0.0, 1.0
        for _ in range(14):
            mid = (lo + hi) / 2
            HumanObjectProperties.set_value("height", mid, entity_reference=self.body)
            TargetService.reapply_macro_details(self.body)
            h = self.body_height()
            if abs(h - target_m) < tol:
                break
            if h < target_m:
                lo = mid
            else:
                hi = mid
        return round(h, 3), round(mid, 3)

    # ------------------------------------------------------------------ materials / images
    def save_image(self, name, rgba, colorspace="sRGB"):
        h, w = rgba.shape[:2]
        img = bpy.data.images.get(name)
        if img is None or tuple(img.size) != (w, h):
            if img:
                bpy.data.images.remove(img)
            img = bpy.data.images.new(name, w, h, alpha=True)
        if img.colorspace_settings.name != colorspace:
            img.colorspace_settings.name = colorspace
        img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
        img.filepath_raw = os.path.join(self.tex, name + ".png")
        img.file_format = "PNG"
        img.save()
        return img

    def read_image(self, img):
        w, h = img.size
        a = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(a)
        return a.reshape(h, w, 4)

    @staticmethod
    def skin_tex(mat):
        """the body's colour texture node (MPFB's diffuse; not the kit's normal/roughness nodes)"""
        return next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and not n.name.startswith("NPC_"))

    @staticmethod
    def set_skin(mat, img):
        """point MPFB's diffuse and alpha texture nodes at img"""
        for n in mat.node_tree.nodes:
            if n.type == "TEX_IMAGE" and not n.name.startswith("NPC_"):
                n.image = img

    def tint_body_texture(self, mul, gamma=1.0):
        mat = self.body.material_slots[0].material
        src = self.read_image(self.skin_tex(mat).image)
        out = src.copy()
        out[..., :3] = np.clip(np.clip(src[..., :3], 0, 1) ** gamma * np.array(mul, np.float32), 0, 1)
        self.set_skin(mat, self.save_image(self.name + "_skin", out))

    # iris colour ramps (dark, light) applied over the MPFB eye texture's luminance
    IRIS = {"brown": ((24, 13, 7), (96, 58, 30)), "darkbrown": ((14, 8, 5), (62, 38, 22)),
            "hazel": ((40, 30, 12), (128, 102, 52)), "amber": ((50, 28, 8), (150, 98, 40)),
            "green": ((22, 36, 22), (92, 120, 74)), "blue": ((20, 34, 58), (96, 130, 170)),
            "grey": ((40, 46, 52), (130, 140, 148))}

    def set_eye_color(self, color):
        """MPFB's eye textures are over-saturated (brown reads red): recolour the iris from its
        luminance, darken the limbal ring and take the pink out of the sclera."""
        eye = self.parts["Eyes"]
        m = eye.material_slots[0].material
        path = os.path.join(MPFB_USER, "eyes", "materials", "brown_eye.png")
        src = self.read_image(bpy.data.images.load(path, check_existing=True))
        h, w = src.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        out = src.copy()
        rgb = src[..., :3]
        lum = rgb @ np.array([0.3, 0.55, 0.15], np.float32)
        grey = lum[..., None] * np.array([1.0, 0.99, 0.97], np.float32)
        out[..., :3] = rgb + (grey - rgb) * 0.65              # sclera: no pink cast
        dark, light = (np.array(c, np.float32) / 255 for c in self.IRIS.get(color, self.IRIS["brown"]))
        for cx, cy in ((0.708, 0.701), (0.290, 0.289)):        # iris centres (Blender pixel order: bottom-up)
            r = np.hypot(xx / w - cx, yy / h - cy) / 0.117
            iris = r < 1.06
            if not iris.any():
                continue
            t = np.clip(lum[iris] / max(float(np.percentile(lum[iris], 97)), 1e-3), 0, 1) ** 0.8
            col = dark + (light - dark) * t[:, None]
            col *= np.clip(1.0 - 0.55 * smooth(0.82, 1.0, r[iris]), 0, 1)[:, None]   # limbal ring
            col = np.where((r[iris] < 0.30)[:, None], rgb[iris] * 0.25, col)      # pupil stays black
            edge = smooth(1.06, 0.98, r[iris])[:, None]
            out[..., :3][iris] = out[..., :3][iris] * (1 - edge) + col * edge
        img = self.save_image("%s_eyes_%s" % (self.name, color), out)
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE":
                n.image = img
        p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        p.inputs["Roughness"].default_value = 0.12
        p.inputs["Specular IOR Level"].default_value = 0.2

    def color_hair(self, dark, light, gamma=1.4, rough=0.6, part="Hair", alpha_gamma=1.0):
        o = self.parts[part]
        m = o.material_slots[0].material
        tex = next(n for n in m.node_tree.nodes if n.type == "TEX_IMAGE")
        src = self.read_image(tex.image)
        lum = src[..., :3] @ np.array([0.3, 0.55, 0.15], np.float32)
        a = src[..., 3] > 0.5
        lo, hi = np.percentile(lum[a], [5, 95]) if a.any() else (0, 1)
        t = np.clip((lum - lo) / max(hi - lo, 1e-3), 0, 1).astype(np.float32)
        d = np.array(dark, np.float32) / 255
        l = np.array(light, np.float32) / 255
        rgb = d + (l - d) * (t ** gamma)[..., None]
        alpha = np.clip(src[..., 3:4], 0, 1) ** alpha_gamma          # < 1 thickens strands (brows)
        img = self.save_image("%s_%s" % (self.name, part.lower()), np.concatenate([rgb, alpha], -1))
        tex.image = img
        p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        p.inputs["Roughness"].default_value = rough
        p.inputs["Specular IOR Level"].default_value = 0.2

    @staticmethod
    def plain(name, rgb, rough=0.6, metal=0.0, sheen=0.0, coat=0.0):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        p.inputs["Base Color"].default_value = srgb(rgb)
        p.inputs["Roughness"].default_value = rough
        p.inputs["Metallic"].default_value = metal
        p.inputs["Sheen Weight"].default_value = sheen
        p.inputs["Coat Weight"].default_value = coat
        return m

    # ------------------------------------------------------------------ garments
    def bone_pt(self, name, t):
        b = self.rig.data.bones[name]
        h = self.rig.matrix_world @ b.head_local
        tl = self.rig.matrix_world @ b.tail_local
        return h + (tl - h) * t, (tl - h).normalized()

    def body_bmesh(self):
        b = self.body
        arm = [m for m in b.modifiers if m.type in ("ARMATURE", "MASK")]
        for m in arm:
            m.show_viewport = False
        deps = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(b.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
        for m in arm:
            m.show_viewport = True
        bm = bmesh.new()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        bm.transform(b.matrix_world)
        names = {vg.index: vg.name for vg in b.vertex_groups}
        # MPFB's helper geometry (proxy tights/skirt/hair/teeth...) is masked away on the body
        hidden = set()
        dl = bm.verts.layers.deform.active
        hg = [i for i, n in names.items() if n == "HelperGeometry" or n.startswith("helper") or n == "JointCubes"]
        for v in bm.verts:
            if any(v[dl].get(i, 0) > 0.5 for i in hg):
                hidden.add(v)
        bmesh.ops.delete(bm, geom=list(hidden), context="VERTS")
        return bm, names

    def dominant(self, bm, names, face, bones):
        dl = bm.verts.layers.deform.active
        acc = {}
        for v in face.verts:
            for gi, w in v[dl].items():
                n = names.get(gi, "")
                if n in bones:
                    acc[n] = acc.get(n, 0.0) + w
        return max(acc, key=acc.get) if acc else ""

    @staticmethod
    def iso_cut(bm, fn):
        """Cut along the zero line of a smooth field fn(co) and delete the fn > 0 side: edges are split
        exactly at the crossing, so curved necklines and hems come out clean."""
        val = {v: fn(v.co) for v in bm.verts}
        new = set()
        for e in list(bm.edges):
            a, b = e.verts
            va, vb = val[a], val[b]
            if (va > 0) != (vb > 0) and abs(va - vb) > 1e-12:
                t = va / (va - vb)
                pos = a.co.lerp(b.co, t)
                _, nv = bmesh.utils.edge_split(e, a, t)
                nv.co = pos
                val[nv] = 0.0
                new.add(nv)
        for f in list(bm.faces):
            cut = [v for v in f.verts if v in new]
            if len(cut) == 2 and not any(e for e in cut[0].link_edges if e.other_vert(cut[0]) == cut[1]):
                bmesh.ops.connect_verts(bm, verts=cut)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if any(val[v] > 1e-9 for v in f.verts)
                                   and all(val[v] >= -1e-9 for v in f.verts)], context="FACES")

    def trim(self, ob, fn):
        """iso_cut on a finished garment (e.g. a cardigan's front opening after hang())."""
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        self.iso_cut(bm, fn)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()

    def shell(self, name, keep_face, cuts=(), offset=0.004, open_front=None, trims=()):
        """Garment from the body surface. keep_face(center, bone) picks faces; cuts are (point, normal,
        bone_set|None) planes that trim the +normal side; trims are smooth fields cut by iso_cut;
        offset pushes the shell along the normals."""
        bm, names = self.body_bmesh()
        bones = set(self.rig.data.bones.keys())
        drop = [f for f in bm.faces if not keep_face(f.calc_center_median(), self.dominant(bm, names, f, bones))]
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008)
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * offset
        for p, n, cut_bones in cuts:
            if callable(cut_bones):
                region = [f for f in bm.faces if cut_bones(f.calc_center_median())]
            elif cut_bones:
                region = [f for f in bm.faces if self.dominant(bm, names, f, bones) in cut_bones]
            else:
                region = list(bm.faces)
            geom = list({e for f in region for e in f.edges}) + list({v for f in region for v in f.verts}) + region
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=p, plane_no=n, clear_outer=True)
        for fn in trims:
            self.iso_cut(bm, fn)
        if open_front:
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if open_front(f.calc_center_median())], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        me = bpy.data.meshes.new(self.name + "_" + name)
        bm.to_mesh(me)
        bm.free()
        old = bpy.data.objects.get(self.name + "_" + name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(self.name + "_" + name, me)
        self.col["Clothes"].objects.link(ob)
        for poly in me.polygons:
            poly.use_smooth = True
        self.garments.append(ob)
        return ob

    def shoe(self, name, heel_z, slope, offset=0.003, voxel=0.004, smooth_iter=6, foot_top=0.11, pull=0.55):
        """Shoe last per foot: convex hull of the foot, voxel-remeshed, pulled `pull` of the way onto
        the foot surface and smoothed (rounded toe box, no toe shapes), cut open above the plane
        z = heel_z + slope * (distance forward of the ankle)."""
        body, _ = self.body_bmesh()                          # no MPFB helper geometry
        co = np.array([tuple(v.co) for v in body.verts], np.float32)
        foot = BVHTree.FromBMesh(body)
        body.free()
        bm = bmesh.new()
        for s, sx in (("l", 1), ("r", -1)):
            a = self.rig.matrix_world @ self.rig.data.bones["foot_" + s].head_local
            pts = co[(co[:, 2] < foot_top) & (co[:, 0] * sx > 0)]
            one = bmesh.new()
            vs = [one.verts.new(tuple(p)) for p in pts]
            res = bmesh.ops.convex_hull(one, input=vs)
            junk = {e for e in res["geom_interior"] + res["geom_unused"] if isinstance(e, bmesh.types.BMVert)}
            bmesh.ops.delete(one, geom=list(junk), context="VERTS")
            me = bpy.data.meshes.new("_hull")
            one.to_mesh(me)
            one.free()
            tmp = bpy.data.objects.new("_hull", me)
            self.col["Clothes"].objects.link(tmp)
            rm = tmp.modifiers.new("rm", "REMESH")
            rm.mode = "VOXEL"
            rm.voxel_size = voxel
            with bpy.context.temp_override(object=tmp, active_object=tmp):
                bpy.ops.object.modifier_apply(modifier=rm.name)
            one = bmesh.new()
            one.from_mesh(tmp.data)
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.meshes.remove(me)
            floor = float(pts[:, 2].min())
            for v in one.verts:
                loc = foot.find_nearest(v.co)[0]
                if loc is not None:
                    v.co = v.co.lerp(loc, pull)
            for _ in range(smooth_iter):
                bmesh.ops.smooth_vert(one, verts=one.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
            one.normal_update()
            for v in one.verts:
                v.co += v.normal * offset
                v.co.z = max(v.co.z, floor - 0.004)             # flat sole
            n = Vector((0, slope, 1)).normalized()
            bmesh.ops.bisect_plane(one, geom=one.verts[:] + one.edges[:] + one.faces[:], plane_co=(0, a.y, heel_z),
                                   plane_no=n, clear_outer=True)
            tm = bpy.data.meshes.new("_part")
            one.to_mesh(tm)
            one.free()
            bm.from_mesh(tm)
            bpy.data.meshes.remove(tm)
        me = bpy.data.meshes.new(self.name + "_" + name)
        bm.to_mesh(me)
        bm.free()
        old = bpy.data.objects.get(self.name + "_" + name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(self.name + "_" + name, me)
        self.col["Clothes"].objects.link(ob)
        for poly in me.polygons:
            poly.use_smooth = True
        self.garments.append(ob)
        return ob

    def inflate(self, ob, fn):
        """Move vertices by fn(co, normal) -> Vector offset (world space, rest pose)."""
        me = ob.data
        me.calc_normals_split() if hasattr(me, "calc_normals_split") else None
        for v in me.vertices:
            v.co = v.co + fn(v.co.copy(), v.normal.copy())
        me.update()

    def hang(self, ob, z_from, z_band, axis_y=0.0, bins=72, fade=0.04, x_max=0.21):
        """Make a loose garment fall straight down from its widest part: below z_from every vertex is
        pushed out to the envelope (per angle around the body axis) measured in z_band=(lo, hi)."""
        me = ob.data
        co = np.array([tuple(v.co) for v in me.vertices], np.float32)
        ang = np.arctan2(co[:, 0], co[:, 1] - axis_y)
        rad = np.hypot(co[:, 0], co[:, 1] - axis_y)
        b = ((ang + np.pi) / (2 * np.pi) * bins).astype(int) % bins
        env = np.zeros(bins, np.float32)
        torso = np.abs(co[:, 0]) < x_max                     # sleeves / arms never take part
        band = (co[:, 2] > z_band[0]) & (co[:, 2] < z_band[1]) & torso
        for i in range(bins):
            m = band & (b == i)
            env[i] = rad[m].max() if m.any() else 0
        env = np.maximum(env, (np.roll(env, 1) + env + np.roll(env, -1)) / 3)
        w = smooth(z_from, z_from - fade, co[:, 2]) * torso
        newr = np.maximum(rad, rad + (env[b] - rad) * w)
        scale = np.where(rad > 1e-5, newr / np.maximum(rad, 1e-5), 1)
        co[:, 0] *= scale
        co[:, 1] = axis_y + (co[:, 1] - axis_y) * scale
        for i, v in enumerate(me.vertices):
            v.co = Vector(co[i])
        me.update()

    def drape_front(self, ob, z_top, z_bottom, x_max=0.17, slope=0.30, strip=0.012, fade=0.06, relax=8):
        """Fabric bridges the chest instead of following the bust: in each vertical strip of the
        front, going down from z_top, the surface may recede at most `slope` (m per m of drop)
        behind the most forward point above it; the effect fades out towards z_bottom. A relax
        pass then rounds off peaks and strip ridges (open edges stay put)."""
        me = ob.data
        co = np.array([tuple(v.co) for v in me.vertices], np.float32)
        front = (co[:, 1] < -0.02) & (np.abs(co[:, 0]) < x_max) & (co[:, 2] < z_top) & (co[:, 2] > z_bottom)
        xb = np.floor(co[:, 0] / strip).astype(int)
        newy = co[:, 1].copy()
        for b in np.unique(xb[front]):
            idx = np.where(front & (xb == b))[0]
            idx = idx[np.argsort(-co[idx, 2])]
            run, run_z = 1.0, z_top
            for i in idx:
                run = min(run + slope * (run_z - co[i, 2]), co[i, 1])
                run_z = co[i, 2]
                w = float(smooth(z_bottom, z_bottom + fade, co[i, 2]) * smooth(z_top, z_top - 0.03, co[i, 2]))
                newy[i] = co[i, 1] + (run - co[i, 1]) * w
        for i, v in enumerate(me.vertices):
            v.co.y = float(newy[i])
        me.update()
        if relax:
            bm = bmesh.new()
            bm.from_mesh(me)
            vs = [v for v in bm.verts if not v.is_boundary and v.co.y < -0.02 and abs(v.co.x) < x_max
                  and z_bottom < v.co.z < z_top]
            for _ in range(relax):
                bmesh.ops.smooth_vert(bm, verts=vs, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
            bm.to_mesh(me)
            bm.free()
            me.update()

    def bridge_crotch(self, ob, crotch_z, half=0.075, below=0.05, above=0.10, iters=30):
        """Trousers span the fork instead of following the body into it: in each horizontal row of
        the front around the crotch, the middle may not sit behind the straight line between the
        fabric at x = -half and +half; then a relax pass smooths the panel."""
        me = ob.data
        co = np.array([tuple(v.co) for v in me.vertices], np.float32)
        band = (co[:, 1] < -0.01) & (co[:, 2] > crotch_z - below) & (co[:, 2] < crotch_z + above)
        rows = np.floor(co[:, 2] / 0.01).astype(int)
        for r in np.unique(rows[band]):
            m = band & (rows == r)
            sides = [m & (np.abs(co[:, 0] - sx * half) < 0.012) for sx in (-1, 1)]
            if not (sides[0].any() and sides[1].any()):
                continue
            edge = min(co[sides[0], 1].min(), co[sides[1], 1].min())
            mid = m & (np.abs(co[:, 0]) < half)
            w = smooth(crotch_z - below, crotch_z - below + 0.03, co[mid, 2]) * smooth(crotch_z + above, crotch_z + above - 0.04, co[mid, 2])
            co[mid, 1] = co[mid, 1] + np.minimum(edge - co[mid, 1], 0) * w
        for i, v in enumerate(me.vertices):
            v.co.y = float(co[i, 1])
        bm = bmesh.new()
        bm.from_mesh(me)
        vs = [v for v in bm.verts if not v.is_boundary and v.co.y < -0.01 and abs(v.co.x) < half + 0.02
              and crotch_z - below < v.co.z < crotch_z + above]
        for _ in range(iters):
            bmesh.ops.smooth_vert(bm, verts=vs, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.to_mesh(me)
        bm.free()
        me.update()

    def pattern_uv(self, ob, label_fn, margin=0.01):
        me = ob.data
        uv = me.uv_layers.get("PatternUV") or me.uv_layers.new(name="PatternUV")
        me.uv_layers.active = uv
        bm = bmesh.new()
        bm.from_mesh(me)
        lab = {f.index: label_fn(f.calc_center_median()) for f in bm.faces}
        for e in bm.edges:
            fs = e.link_faces
            e.seam = len(fs) == 2 and lab[fs[0].index] != lab[fs[1].index]
        bm.to_mesh(me)
        bm.free()
        area = next(a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D")
        region = next(r for r in area.regions if r.type == "WINDOW")
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        with bpy.context.temp_override(area=area, region=region, active_object=ob, object=ob, selected_objects=[ob]):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.select_all(action="SELECT")
            bpy.ops.uv.unwrap(method="ANGLE_BASED", fill_holes=True, correct_aspect=True, margin=margin)
            try:
                bpy.ops.uv.align_rotation(method="GEOMETRY", axis="Z")
            except Exception:
                pass
            bpy.ops.uv.pack_islands(rotate=False, margin=margin)
            bpy.ops.object.mode_set(mode="OBJECT")
        for u in [u.name for u in me.uv_layers if u.name != "PatternUV"]:
            me.uv_layers.remove(me.uv_layers[u])

    def surface_maps(self, ob, size, uv_name="PatternUV", vco=None, vert_mask=None):
        """Per-texel world position P, normal N and coverage M of ob's UV layout. vco overrides the
        vertex positions (the MPFB body's shape lives in shape keys); vert_mask limits the work to
        triangles touching the masked vertices."""
        me = ob.data
        me.calc_loop_triangles()
        uvl = me.uv_layers[uv_name].data
        mw = ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        P = np.zeros((size, size, 3), np.float32)
        N = np.zeros((size, size, 3), np.float32)
        M = np.zeros((size, size), bool)
        if vco is None:
            vco = np.array([tuple(mw @ v.co) for v in me.vertices], np.float32)
        vno = np.array([tuple((nm @ v.normal).normalized()) for v in me.vertices], np.float32)
        for t in me.loop_triangles:
            if vert_mask is not None and not vert_mask[list(t.vertices)].any():
                continue
            uv = np.array([tuple(uvl[l].uv) for l in t.loops], np.float32) * size
            x0, y0 = np.floor(uv.min(0)).astype(int)
            x1, y1 = np.ceil(uv.max(0)).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = uv
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
            w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
            w2 = 1 - w0 - w1
            ins = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
            if not ins.any():
                continue
            vi = list(t.vertices)
            p = w0[..., None] * vco[vi[0]] + w1[..., None] * vco[vi[1]] + w2[..., None] * vco[vi[2]]
            n = w0[..., None] * vno[vi[0]] + w1[..., None] * vno[vi[1]] + w2[..., None] * vno[vi[2]]
            sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
            P[sl][ins] = p[ins]
            N[sl][ins] = n[ins]
            M[sl][ins] = True
        N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-6)
        return P, N, M

    # ------------------------------------------------------------------ face / skin detail
    def face_marks(self):
        """Face landmarks in rest pose. Nose tip = most forward point of the midline profile; nose
        base, mouth and chin sit at fixed offsets below it on MPFB heads (-15, -28, -79 mm); eye
        centres come from the fitted eye mesh."""
        co = self.body_rest()
        head = self.rig.matrix_world @ self.rig.data.bones["head"].head_local
        mid = co[(np.abs(co[:, 0]) < 0.006) & (co[:, 1] < head.y) & (co[:, 2] > head.z - 0.06) & (co[:, 2] < head.z + 0.06)]
        tip = mid[np.argmin(mid[:, 1])]
        eyes = self.parts["Eyes"]
        ev = eyes.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        ec = np.array([tuple(eyes.matrix_world @ v.co) for v in me.vertices], np.float32)
        ev.to_mesh_clear()
        eye = [ec[ec[:, 0] * s > 0].mean(0) for s in (1, -1)]
        return dict(head=head, tip=float(tip[2]), tip_y=float(tip[1]), sn=float(tip[2]) - 0.015,
                    mouth=float(tip[2]) - 0.028, menton=float(tip[2]) - 0.079, eye_l=eye[0], eye_r=eye[1])

    def bake_ao(self, size=2048, samples=32, distance=0.06):
        """Cycles ambient-occlusion bake of the body (eyes and hair occlude; clothes and brows don't)
        into its own UV layout. Returns the AO as a float array (1 = open, 0 = occluded)."""
        scn = self.scn
        prev = (scn.render.engine, scn.world.light_settings.distance if scn.world else None)
        try:
            scn.render.engine = "CYCLES"
        except TypeError:
            return None
        scn.cycles.samples = samples
        if scn.world is None:
            scn.world = bpy.data.worlds.get("NPC_World") or bpy.data.worlds.new("NPC_World")
        scn.world.light_settings.distance = distance
        keep = {self.body, self.parts.get("Eyes"), self.parts.get("Hair")}
        hidden = {o: o.hide_render for o in scn.objects}
        for o in scn.objects:
            o.hide_render = o not in keep
        img = bpy.data.images.get(self.name + "_ao")
        if img is None or tuple(img.size) != (size, size):
            if img:
                bpy.data.images.remove(img)
            img = bpy.data.images.new(self.name + "_ao", size, size, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        mat = self.body.material_slots[0].material
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        mat.node_tree.nodes.active = node
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        self.body.select_set(True)
        bpy.context.view_layer.objects.active = self.body
        try:
            bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
            ao = self.read_image(img)[..., 0].copy()
        finally:
            mat.node_tree.nodes.remove(node)
            for o, h in hidden.items():
                o.hide_render = h
            scn.render.engine = prev[0]
            if prev[1] is not None:
                scn.world.light_settings.distance = prev[1]
        return ao

    def skin_detail(self, F, age=0.3, ao_strength=0.6, lips_mul=(0.9, 0.82, 0.82), lips_desat=0.3, beard_zone=None, seed=31):
        """Face realism for the game skin: baked AO multiplied into the colour, muted lips, and a
        normal + roughness map pair (pore grain everywhere; nasolabial folds, forehead lines,
        under-eye creases and lip lines scaled by `age`; shinier T-zone and lips, matte beard)."""
        mat = self.body.material_slots[0].material
        tex = self.skin_tex(mat)
        src = self.read_image(tex.image)
        size = src.shape[0]
        ao = self.bake_ao(size)
        co = self.body_rest()
        P, N, M = self.surface_maps(self.body, size, uv_name=self.body.data.uv_layers[0].name, vco=co)
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        ax = np.abs(x)
        hy, tip, sn, mo = F["head"].y, F["tip"], F["sn"], F["mouth"]
        eye_z = float((F["eye_l"][2] + F["eye_r"][2]) / 2)
        eye_x = float(abs(F["eye_l"][0]))
        face = M & (y < hy - 0.035) & (z > F["menton"] - 0.01) & (z < tip + 0.12)
        out = src.copy()
        if ao is not None:
            aof = np.clip(ao, 0, 1) ** 1.2
            k_ = np.where(face, ao_strength, ao_strength * 0.75)
            out[..., :3] *= (1 - k_ + k_ * aof)[..., None]
        lip = face & (((ax / 0.025) ** 2 + ((z - mo) / np.where(z > mo, 0.0085, 0.0095)) ** 2) < 1.0)
        lw = self.blur(lip.astype(np.float32), 2)
        lum = out[..., :3] @ np.array([0.3, 0.55, 0.15], np.float32)
        lipc = out[..., :3] * (1 - lips_desat) + lum[..., None] * lips_desat
        lipc = lipc * np.array(lips_mul, np.float32)
        out[..., :3] = out[..., :3] * (1 - lw[..., None]) + lipc * lw[..., None]
        if ao is not None:                                     # the parting between the lips stays dark
            gap = self.blur((lip & (ao < 0.6)).astype(np.float32), 1)
            out[..., :3] *= (1 - 0.5 * gap)[..., None]
        self.set_skin(mat, self.save_image(self.name + "_skin", out))
        # height: pores + creases (metres)
        rng = np.random.default_rng(seed)
        grain = rng.standard_normal((size, size)).astype(np.float32)   # finest grain the texel size allows
        h = 0.00003 * grain * M
        h += np.where(face, 0.00005 * grain, 0)                # pores read on the face
        def groove(d, depth, width):
            return -depth * np.exp(-(d / width) ** 2)
        for s in (1, -1):
            xs = x * s
            # nasolabial fold: nose wing to beside the mouth corner
            d = np.abs((xs - 0.019) * (mo - 0.014 - sn) - (z - sn) * (0.034 - 0.019)) / np.hypot(mo - 0.014 - sn, 0.034 - 0.019)
            seg = smooth(sn + 0.008, sn, z) * smooth(mo - 0.022, mo - 0.008, z) * smooth(0.01, 0.016, xs)
            h += np.where(face, groove(d, 0.0009 * (0.4 + age), 0.003) * seg, 0)
            # under-eye crease and crow's feet
            r = np.hypot((xs - eye_x) / 1.25, z - eye_z)
            fade = smooth(eye_x - 0.024, eye_x - 0.012, xs) * smooth(eye_z + 0.002, eye_z - 0.006, z)
            h += np.where(face, groove(np.abs(r - 0.019), 0.0004 * age, 0.0018) * fade, 0)
            for i in range(3):
                ang = -0.35 + i * 0.35
                cx, cz = eye_x + 0.028, eye_z
                dd = np.abs(np.sin(ang) * (xs - cx) - np.cos(ang) * (z - cz))
                near = smooth(cx - 0.002, cx + 0.004, xs) * smooth(cx + 0.018, cx + 0.010, xs) * smooth(0.013, 0.007, np.abs(z - cz))
                h += np.where(face, groove(dd, 0.00028 * age, 0.001) * near, 0)
        for i in range(3):                                     # forehead lines
            fz = eye_z + 0.042 + i * 0.009
            h += np.where(face & (ax < 0.05), groove(np.abs(z - fz - 0.004 * (ax / 0.05) ** 2), 0.0003 * age, 0.0012) * smooth(0.05, 0.03, ax), 0)
        h += np.where(lip, -0.00014 * np.abs(np.sin(2 * np.pi * x / 0.0022)), 0)   # lip lines
        both = face[:, 1:] & face[:, :-1]
        texel = float(np.median(np.linalg.norm(P[:, 1:][both] - P[:, :-1][both], axis=-1))) if both.any() else 0.0008
        gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * texel)
        gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * texel)
        edge = ~(M & np.roll(M, 1, 1) & np.roll(M, -1, 1) & np.roll(M, 1, 0) & np.roll(M, -1, 0))
        gx[edge] = 0                                           # no ridges along UV island borders
        gy[edge] = 0
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        one = np.ones((size, size, 1), np.float32)
        nimg = self.save_image(self.name + "_skin_normal", np.concatenate([self.dilate(nrm * 0.5 + 0.5, M, 4), one], -1), "Non-Color")
        # roughness: T-zone and lips shinier, beard matte
        rough = np.full((size, size), 0.58, np.float32) + 0.03 * grain
        tzone = face & (((ax < 0.022) & (z > sn) & (z < eye_z + 0.07)) | ((z > eye_z + 0.025) & (ax < 0.05)))
        rough = np.where(tzone, rough - 0.12, rough)
        rough = np.where(lip, 0.5, rough)
        if beard_zone is not None:
            rough = np.where(M & beard_zone(P), 0.72, rough)
        rough = self.blur(rough, 2)
        rimg = self.save_image(self.name + "_skin_roughness", np.concatenate([np.repeat(np.clip(rough, 0, 1)[..., None], 3, -1), one], -1), "Non-Color")
        nt = mat.node_tree
        p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        for n in [n for n in nt.nodes if n.name in ("NPC_SkinNormal", "NPC_SkinNormalMap", "NPC_SkinRough", "NPC_SkinRoughSep")]:
            nt.nodes.remove(n)
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.name = "NPC_SkinNormal"; tn.image = nimg
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.name = "NPC_SkinNormalMap"
        nm.uv_map = self.body.data.uv_layers[0].name
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
        tr = nt.nodes.new("ShaderNodeTexImage"); tr.name = "NPC_SkinRough"; tr.image = rimg
        sep = nt.nodes.new("ShaderNodeSeparateColor"); sep.name = "NPC_SkinRoughSep"
        nt.links.new(tr.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[1], p.inputs["Roughness"])
        try:
            p.inputs["Subsurface Weight"].default_value = 0.12
            p.inputs["Subsurface Radius"].default_value = (0.9, 0.4, 0.25)
            p.inputs["Subsurface Scale"].default_value = 0.004
        except KeyError:
            pass
        return ao is not None

    def paint_skin(self, density_fn, hair_rgb, region, seed=7, grain=1):
        """Paint body hair (beard, stubble, arm hair) into the skin texture: density_fn(P) gives 0..1
        coverage per texel from its rest-pose world position; region(co) -> bool picks the
        vertices worth rasterising. Stubble grain comes from per-texel noise."""
        mat = self.body.material_slots[0].material
        src = self.read_image(self.skin_tex(mat).image)
        size = src.shape[0]
        co = self.body_rest()
        P, N, M = self.surface_maps(self.body, size, uv_name=self.body.data.uv_layers[0].name, vco=co,
                                    vert_mask=region(co))
        rng = np.random.default_rng(seed)
        grains = self.blur(rng.random((size, size)).astype(np.float32), grain)
        grains = np.clip((grains - grains.mean()) / (grains.std() * 3) + 0.5, 0, 1)
        a = np.zeros((size, size), np.float32)
        a[M] = np.clip(density_fn(P[M]), 0, 1)
        a = self.blur(a, 2)                                   # soft edge across UV texels
        cover = np.clip(a * (0.80 + 0.35 * grains), 0, 0.94)[..., None]   # dense, fine grain; skin shows faintly
        out = src.copy()
        hair = np.array(hair_rgb, np.float32) / 255
        # skin under hair is shadowed and loses its warmth before the hairs go on top
        lum = src[..., :3] @ np.array([0.3, 0.55, 0.15], np.float32)
        shade = a[..., None] * 0.6
        under = src[..., :3] * (1 - shade) + (lum[..., None] * 0.7) * shade
        out[..., :3] = under * (1 - cover) + hair * cover
        self.set_skin(mat, self.save_image(self.name + "_skin", out))
        return int((a > 0.05).sum())

    def add_asset(self, rel, asset_type="Clothes"):
        """Fit an MPFB clothing asset (mhclo under the user data dir) to the body and its rig."""
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService
        old = bpy.data.objects.get("%s_%s" % (self.name, os.path.basename(rel).split(".")[0]))
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        self.activate("Clothes")
        o = HumanService.add_mhclo_asset(os.path.join(MPFB_USER, rel), self.body, asset_type=asset_type,
                                         subdiv_levels=0, material_type="MAKESKIN")
        o.name = "%s_%s" % (self.name, os.path.basename(rel).split(".")[0])
        for c in list(o.users_collection):
            if c != self.col["Clothes"]:
                c.objects.unlink(o)
        if o.name not in self.col["Clothes"].objects:
            self.col["Clothes"].objects.link(o)
        return o

    def recolor(self, ob, fn, tag):
        """Rewrite ob's colour texture with fn(rgb, alpha) -> rgb (all float arrays)."""
        m = ob.material_slots[0].material
        tex = next(n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and "normal" not in n.image.name.lower())
        src = self.read_image(tex.image)
        out = src.copy()
        out[..., :3] = np.clip(fn(src[..., :3], src[..., 3]), 0, 1)
        img = self.save_image("%s_%s" % (self.name, tag), out)
        tex.image = img
        return m

    @staticmethod
    def blur(a, r=1, axis=None):
        out = a.astype(np.float32)
        for _ in range(r):
            if axis in (None, 1):
                out = (np.roll(out, 1, 1) + out + np.roll(out, -1, 1)) / 3
            if axis in (None, 0):
                out = (np.roll(out, 1, 0) + out + np.roll(out, -1, 0)) / 3
        return out

    def dilate(self, a, mask, n=12):
        a = a.copy()
        m = mask.copy()
        for _ in range(n):
            acc = np.zeros_like(a)
            cnt = np.zeros(m.shape, np.float32)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                sm = np.roll(np.roll(m, dy, 0), dx, 1)
                acc += np.roll(np.roll(a, dy, 0), dx, 1) * sm[..., None]
                cnt += sm
            g = (~m) & (cnt > 0)
            a[g] = acc[g] / cnt[g][..., None]
            m |= g
        return a

    def paint_fabric(self, ob, base_rgb, height_fn=None, color_fn=None, size=2048, rough=0.85, heather=0.05,
                     weave="knit", sheen=0.4, seed=1, nstrength=1.0):
        """Painted fabric: heathered colour, weave grain, optional height features (seams, ribs,
        creases) and colour features (e.g. buttons painted). Returns the material."""
        P, N, M = self.surface_maps(ob, size)
        rng = np.random.default_rng(seed)
        texel = float(np.median(np.linalg.norm(P[:, 1:][M[:, 1:] & M[:, :-1]] - P[:, :-1][M[:, 1:] & M[:, :-1]], axis=-1)))
        n = self.blur(rng.standard_normal((size, size)).astype(np.float32), 1)
        slub = self.blur(rng.standard_normal((size, size)).astype(np.float32), 6, axis=1)
        mott = (np.sin(P[..., 0] * 41 + P[..., 2] * 23) * np.sin(P[..., 1] * 37 - P[..., 2] * 29)).astype(np.float32)
        shade = 1 + heather * n + 0.03 * slub + 0.02 * mott
        base = np.array(base_rgb, np.float32) / 255.0
        rgb = np.clip(base[None, None, :] * shade[..., None], 0, 1)
        h = 0.00006 * n
        if weave == "knit":
            # knitted columns of V-stitches: ribs around the body, rows up it
            around = np.arctan2(P[..., 0], -P[..., 1]) * 0.16
            h += 0.00010 * np.abs(np.sin(2 * np.pi * around / 0.0034)) * (0.6 + 0.4 * np.sin(2 * np.pi * P[..., 2] / 0.0030)) + 0.00005 * slub
        elif weave == "twill":
            h += 0.00007 * np.sin(2 * np.pi * (P[..., 0] + P[..., 2]) / 0.0018)
        elif weave == "denim":
            h += 0.0001 * np.sin(2 * np.pi * (P[..., 0] - P[..., 2]) / 0.0016)
        if height_fn is not None:
            h += height_fn(P, N, M).astype(np.float32)
        r = np.full((size, size), rough, np.float32) + 0.04 * n
        if color_fn is not None:
            rgb, r = color_fn(P, N, M, rgb, r)
        gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * texel)
        gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * texel)
        edge = ~(M & np.roll(M, 1, 1) & np.roll(M, -1, 1) & np.roll(M, 1, 0) & np.roll(M, -1, 0))
        gx[edge] = 0
        gy[edge] = 0
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        one = np.ones((size, size, 1), np.float32)
        key = ob.name
        bimg = self.save_image(key + "_basecolor", np.concatenate([self.dilate(rgb, M), one], -1))
        nimg = self.save_image(key + "_normal", np.concatenate([self.dilate(nrm * 0.5 + 0.5, M), one], -1), "Non-Color")
        rimg = self.save_image(key + "_roughness", np.concatenate([self.dilate(np.repeat(np.clip(r, 0, 1)[..., None], 3, -1), M), one], -1), "Non-Color")
        m = bpy.data.materials.get("M_" + key) or bpy.data.materials.new("M_" + key)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        p = nt.nodes.new("ShaderNodeBsdfPrincipled")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "PatternUV"

        def tx(img):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img
            nt.links.new(uv.outputs[0], t.inputs[0])
            return t
        tb, tr, tn = tx(bimg), tx(rimg), tx(nimg)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.uv_map = "PatternUV"
        nm.inputs["Strength"].default_value = nstrength
        nt.links.new(tb.outputs["Color"], p.inputs["Base Color"])
        nt.links.new(tr.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[1], p.inputs["Roughness"])
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
        p.inputs["Sheen Weight"].default_value = sheen
        p.inputs["Sheen Roughness"].default_value = 0.6
        p.inputs["Sheen Tint"].default_value = srgb(tuple(min(255, v * 1.6) for v in base_rgb))   # white sheen washes dark dyes pink
        nt.links.new(p.outputs[0], out.inputs[0])
        ob.data.materials.clear()
        ob.data.materials.append(m)
        return m

    def rig_garment(self, ob, thickness=0.0, solid_offset=-1.0):
        b = self.body
        bones = set(self.rig.data.bones.keys())
        for vg in b.vertex_groups:
            if vg.name in bones and vg.name not in ob.vertex_groups:
                ob.vertex_groups.new(name=vg.name)
        dt = ob.modifiers.new("wt", "DATA_TRANSFER")
        dt.object = b
        dt.use_vert_data = True
        dt.data_types_verts = {"VGROUP_WEIGHTS"}
        dt.vert_mapping = "POLYINTERP_NEAREST"
        dt.layers_vgroup_select_src = "ALL"
        dt.layers_vgroup_select_dst = "NAME"
        arm = [m for m in b.modifiers if m.type == "ARMATURE"]
        for m in arm:
            m.show_viewport = False
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier=dt.name)
        for m in arm:
            m.show_viewport = True
        self.limit4(ob)
        if thickness > 0:
            so = ob.modifiers.new("Thickness", "SOLIDIFY")
            so.thickness = thickness
            so.offset = solid_offset
            so.use_even_offset = False
            so.use_quality_normals = True
        am = ob.modifiers.new("Armature", "ARMATURE")
        am.object = self.rig
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_move_to_index(modifier="Armature", index=0)
        ob.parent = self.rig
        return ob

    def limit4(self, o):
        bones = set(self.rig.data.bones.keys())
        vg = {g.index: g.name for g in o.vertex_groups}
        good = []
        for v in o.data.vertices:
            gs = sorted([(g.weight, g.group) for g in v.groups if vg.get(g.group) in bones and g.weight > 0], reverse=True)
            keep = gs[:4]
            s = sum(w for w, _ in keep)
            ks = {gi for _, gi in keep}
            for w, gi in gs:
                if gi in ks and s > 0:
                    o.vertex_groups[gi].add([v.index], w / s, "REPLACE")
                else:
                    o.vertex_groups[gi].remove([v.index])
            if s >= 0.5:
                good.append(v)
        bad = [v for v in o.data.vertices if sum(g.weight for g in v.groups if vg.get(g.group) in bones) < 0.5]
        if bad and good:
            kd = KDTree(len(good))
            for i, v in enumerate(good):
                kd.insert(v.co, i)
            kd.balance()
            for v in bad:
                src = good[kd.find(v.co)[1]]
                for g in src.groups:
                    if vg.get(g.group) in bones:
                        o.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")

    def hide_under(self, garments, margin=0.025, open_fn=None):
        """Body vertices covered by the given garments (and not near their open edges) are masked."""
        b = self.body
        co = self.body_rest()
        trees = []
        for g in garments:
            bm = bmesh.new()
            bm.from_mesh(g.data)
            bm.transform(g.matrix_world)
            pts = [v.co.copy() for v in bm.verts if v.is_boundary and (open_fn is None or open_fn(g, v.co))]
            kd = KDTree(max(len(pts), 1))
            for i, p in enumerate(pts):
                kd.insert(p, i)
            kd.balance()
            trees.append((BVHTree.FromBMesh(bm), kd, len(pts)))
            bm.free()
        cov = []
        for i, p in enumerate(co):
            p = Vector(p)
            for bvh, kd, n in trees:
                loc, nrm, idx, d = bvh.find_nearest(p, 0.03)
                if loc is not None and (n == 0 or kd.find(loc)[2] > margin):
                    cov.append(i)
                    break
        vg = b.vertex_groups.get("npc_covered") or b.vertex_groups.new(name="npc_covered")
        vg.remove(list(range(len(co))))
        vg.add(cov, 1.0, "REPLACE")
        mk = b.modifiers.get("Hidden under clothes") or b.modifiers.new("Hidden under clothes", "MASK")
        mk.vertex_group = "npc_covered"
        mk.invert_vertex_group = True
        return len(cov)

    # ------------------------------------------------------------------ studio / pose / output
    def stage(self):
        st = self.col["Stage"]
        for n, e, loc, size in (("Key", 380, (1.6, -2.4, 2.2), 2.5), ("Fill", 180, (-2.2, -1.8, 1.6), 3.0),
                                ("Top", 120, (0, 0.6, 3.6), 2.0), ("Back", 160, (0.6, 2.6, 2.2), 2.0)):
            full = "%s_Light%s" % (self.name, n)      # never the same name as a garment ("_Top")
            l = bpy.data.lights.get(full) or bpy.data.lights.new(full, "AREA")
            l.energy = e
            l.size = size
            o = bpy.data.objects.get(full) or bpy.data.objects.new(full, l)
            if o.name not in st.objects:
                st.objects.link(o)
            o.location = loc
            o.rotation_euler = (Vector((0, 0, 1.2)) - o.location).to_track_quat("-Z", "Y").to_euler()
        w = bpy.data.worlds.get("NPC_World") or bpy.data.worlds.new("NPC_World")
        w.use_nodes = True
        bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
        bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
        bg.inputs["Strength"].default_value = 0.25
        self.scn.world = w
        self.scn.view_settings.view_transform = "AgX"
        self.scn.view_settings.exposure = -0.45          # dark dyes (charcoal, burgundy) read true
        try:
            self.scn.view_settings.look = "AgX - Punchy"
        except TypeError:
            pass
        try:
            self.scn.render.engine = "BLENDER_EEVEE_NEXT"
        except TypeError:
            self.scn.render.engine = "BLENDER_EEVEE"
        fl = bpy.data.meshes.get("NPC_Floor")
        if fl is None:
            bm = bmesh.new()
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=3.0)
            fl = bpy.data.meshes.new("NPC_Floor")
            bm.to_mesh(fl)
            bm.free()
            fl.materials.append(self.plain("M_NPC_Floor", (200, 202, 205), 0.8))
        fo = bpy.data.objects.get(self.name + "_Floor") or bpy.data.objects.new(self.name + "_Floor", fl)
        if fo.name not in st.objects:
            st.objects.link(fo)
        cam = bpy.data.objects.get(self.name + "_Cam") or bpy.data.objects.new(self.name + "_Cam", bpy.data.cameras.new(self.name + "_Cam"))
        if cam.name not in st.objects:
            st.objects.link(cam)
        cam.data.lens = 50
        self.scn.camera = cam
        return cam

    def aim(self, bone, d):
        pb = self.rig.pose.bones[bone]
        bpy.context.view_layer.update()
        m = pb.matrix.copy()
        cur = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
        q = cur.rotation_difference(Vector(d).normalized())
        h = m.translation.copy()
        pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ m
        bpy.context.view_layer.update()

    def pose(self, kind="t"):
        for pb in self.rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        for s, sx in (("l", 1), ("r", -1)):
            if kind == "t":
                for b in ("upperarm_", "lowerarm_"):
                    self.aim(b + s, (sx, 0, 0.02))
                self.aim("hand_" + s, (sx, -0.02, 0))
            elif kind == "down":
                self.aim("upperarm_" + s, (sx * 0.16, 0.02, -0.99))
                self.aim("lowerarm_" + s, (sx * 0.08, -0.25, -0.97))

    def render(self, tag, views=("front", "three_quarter", "back", "side")):
        cam = self.stage()
        out = []
        locs = {"front": (0, -4.0, 0.95), "three_quarter": (2.7, -2.9, 1.05), "back": (0, 4.0, 0.95), "side": (4.0, 0, 0.95),
                "face": (0.35, -0.85, 1.6)}
        for o in self.col["Stage"].objects:
            o.hide_render = False
        for v in views:
            cam.location = locs[v]
            aim = Vector((0, 0, 0.88 if v != "face" else 1.55))
            if v == "face":
                aim.z = self.body_rest()[:, 2].max() - 0.12
                cam.location = (0.35, -0.85, aim.z + 0.02)
                cam.data.lens = 85
            else:
                cam.data.lens = 50
            cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
            self.scn.render.resolution_x, self.scn.render.resolution_y = (900, 1200) if v != "face" else (900, 900)
            self.scn.render.filepath = os.path.join(self.dir, "renders", "%s_%s_%s.png" % (self.name, tag, v))
            bpy.ops.render.render(write_still=True)
            out.append(self.scn.render.filepath)
        return out

    def save(self):
        path = os.path.join(self.dir, self.name + "_master.blend")
        bpy.data.libraries.write(path, {self.scn}, path_remap="ABSOLUTE", fake_user=True, compress=True)
        return path
