"""Garment library for NPCs built with npc_kit.Kit (Delivery Simulator 2026).

Every garment grows from the MPFB body surface (Kit.shell: clean plane / iso-line cuts, no
interpenetration), is draped (hang / drape_front / bridge_crotch / leg straightening), gets a pattern
UV layout and painted fabric maps (Kit.paint_fabric: weave, seams, ribs, pockets, buttons, decals),
and is rigged to the MPFB game_engine skeleton. An NPC is a list of garment specs:

    out = Outfit(kit)
    out.add("shirt", color=(240, 238, 232), sleeve="long", neck="collar", hem="tucked")
    out.add("trousers", color=(40, 42, 46), kind="slacks")
    out.add("shoes", kind="dress", color=(20, 20, 22))
    out.finish()                      # materials, rigging, body mask

Layering (offsets from the skin, metres): leggings 0.002 < tucked top 0.004 < trousers 0.007 <
untucked top 0.010 < belt 0.013 < jacket 0.015 < vest / apron 0.019. Text and patches are planar
decals (RGBA images rendered outside Blender by tools/npc/decals.py) placed on the front, back or a
sleeve in body space.
"""
import bpy, math, os
import numpy as np
from mathutils import Vector

_ns = {}
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else
                       r"C:\GodotProjects\delivery-simulator-2026\tools\npc", "npc_kit.py"), encoding="utf-8").read(), _ns)
Kit, smooth, srgb = _ns["Kit"], _ns["smooth"], _ns["srgb"]
DECALS = r"C:\GodotProjects\delivery-simulator-2026\source_assets\npc\_decals"

TORSO = {"pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "neck_01", "upperarm_l", "upperarm_r"}
ARMS = {"upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r"}
LEGS = {"pelvis", "spine_01", "thigh_l", "thigh_r", "calf_l", "calf_r"}
SLEEVES = {"none": None, "cap": ("upperarm", 0.22), "short": ("upperarm", 0.5), "elbow": ("upperarm", 0.95),
           "three_quarter": ("lowerarm", 0.55), "long": ("lowerarm", 0.97)}


def landmarks(k):
    r = k.rig
    def head(b): return r.matrix_world @ r.data.bones[b].head_local
    L = dict(hip=head("thigh_l").z, knee=head("calf_l").z, ankle=head("foot_l").z, waist=head("spine_01").z,
             chest=head("spine_03").z, neck=head("neck_01").z, neck_y=head("neck_01").y, shoulder=head("upperarm_l").z)
    L["crotch"] = L["hip"] - 0.075
    return L


def seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    t = np.clip(((px - ax) * dx + (pz - az) * dz) / max(dx * dx + dz * dz, 1e-9), 0, 1)
    return np.hypot(px - (ax + t * dx), pz - (az + t * dz))


def rgb01(c):
    return np.array(c, np.float32) / 255.0


class Decal:
    """A planar RGBA image (or a solid patch) placed on the body: side "front" / "back" projects on
    x-z, "arm_l" / "arm_r" on y-z (outer side of the sleeve). centre (x, z) / (y, z), size (w, h) m."""
    def __init__(self, side, centre, size, image=None, rgb=None, round_=False):
        self.side, self.centre, self.size, self.rgb, self.round_ = side, centre, size, rgb, round_
        self.img = None
        if image:
            path = image if os.path.isabs(image) else os.path.join(DECALS, image if os.path.splitext(image)[1] else image + ".png")
            im = bpy.data.images.load(path, check_existing=True)
            w, h = im.size
            a = np.empty(w * h * 4, np.float32)
            im.pixels.foreach_get(a)
            self.img = a.reshape(h, w, 4)

    def apply(self, P, rgb, rough, rough_value=None):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        if self.side == "front":
            sel, u, v = y < -0.01, x, z
        elif self.side == "back":
            sel, u, v = y > 0.01, -x, z
        elif self.side == "arm_l":
            sel, u, v = x > 0.12, -y, z
        else:
            sel, u, v = x < -0.12, y, z
        uu = (u - self.centre[0]) / self.size[0] + 0.5
        vv = (v - self.centre[1]) / self.size[1] + 0.5
        inside = sel & (uu >= 0) & (uu < 1) & (vv >= 0) & (vv < 1)
        if self.round_:
            inside &= ((uu - 0.5) ** 2 + (vv - 0.5) ** 2) < 0.25
        if not inside.any():
            return rgb, rough
        if self.img is None:
            rgb[inside] = rgb01(self.rgb)
            if rough_value is not None:
                rough[inside] = rough_value
            return rgb, rough
        h, w = self.img.shape[:2]
        px = np.clip((uu[inside] * (w - 1)).astype(int), 0, w - 1)
        py = np.clip((vv[inside] * (h - 1)).astype(int), 0, h - 1)
        s = self.img[py, px]
        a = s[:, 3:4]
        rgb[inside] = rgb[inside] * (1 - a) + s[:, :3] * a
        if rough_value is not None:
            rough[inside] = rough[inside] * (1 - a[:, 0]) + rough_value * a[:, 0]
        return rgb, rough


class Outfit:
    def __init__(self, k):
        self.k = k
        self.L = landmarks(k)
        self.items = []          # (kind, object, spec, extra)
        self.rise = self.L["waist"] - 0.035
        self.tucked_hem = None

    # ------------------------------------------------------------------ helpers
    def edge_curve(self, zs, ws):
        return lambda z: np.interp(z, zs, ws)

    def collar_z(self, depth=0.046, width=0.085, back=0.012):
        L = self.L
        def f(x, y):
            fr = np.clip((L["neck_y"] - y) / 0.07, 0, 1) ** 1.5
            return L["neck"] + back - depth * fr * np.clip(1 - (np.asarray(x) / width) ** 2, 0, 1)
        return f

    def vneck_z(self, depth, width):
        L = self.L
        def f(x, y):
            fr = np.clip((L["neck_y"] - y) / 0.07, 0, 1)
            return L["neck"] + 0.012 - depth * fr * np.clip(1 - np.abs(np.asarray(x)) / width, 0, 1)
        return f

    def sleeve_cuts(self, sleeve):
        cuts = []
        s = SLEEVES[sleeve]
        if s is None:
            return cuts
        for side in ("l", "r"):
            p, d = self.k.bone_pt("%s_%s" % (s[0], side), s[1])
            bones = {"upperarm_" + side} if s[0] == "upperarm" else {"lowerarm_" + side}
            cuts.append((p, d, bones))
        return cuts

    def sleeve_inflate(self, ob, sleeve, extra):
        """Loosen a sleeve: push it off the arm, more towards its opening."""
        if extra <= 0 or SLEEVES[sleeve] is None:
            return
        k = self.k
        bone = SLEEVES[sleeve][0]
        arms = {}
        for side in ("l", "r"):
            a, d = k.bone_pt("upperarm_" + side, 0.0)
            e, _ = k.bone_pt("lowerarm_" + side, 1.0)
            arms[side] = (a, e)
        def f(co, n):
            side = "l" if co.x > 0 else "r"
            a, e = arms[side]
            ax = e - a
            t = (co - a).dot(ax) / max(ax.length_squared, 1e-6)
            if t < 0.05 or abs(co.x) < 0.16:
                return Vector((0, 0, 0))
            foot = a + ax * t
            rad = co - foot
            if rad.length < 1e-4:
                return Vector((0, 0, 0))
            return rad.normalized() * extra * float(smooth(0.05, 0.35, t))
        k.inflate(ob, f)

    # ------------------------------------------------------------------ garments
    def add(self, garment, **spec):
        return getattr(self, "g_" + garment)(**spec)

    def g_top(self, name="Top", color=(200, 200, 200), sleeve="short", neck="crew", hem="untucked", fit=0.0,
              weave="knit", heather=0.06, rough=0.88, sheen=0.3, placket=None, pocket=False, epaulettes=False,
              stripes=None, zip=False, cuffs=False, hem_rib=False, decals=(), buttons_rgb=(235, 235, 230),
              collar_rgb=None, pattern=None, offset=None, drape=True, tag=None):
        """Tees, polos, shirts, sweaters, jerseys, chef coats, uniform shirts.
        neck: crew | scoop | vneck | collar (shirt / polo) | mock (zip jersey) | none
        hem: untucked (hangs over the waistband) | tucked (inside the trousers) | long (tunic)
        fit: extra looseness (m) of the body and sleeves; placket: None | "polo" | "shirt" | "double"."""
        k, L = self.k, self.L
        tucked = hem == "tucked"
        hem_z = (self.rise - 0.02) if tucked else (L["hip"] + 0.0 if hem == "untucked" else L["hip"] - 0.03)
        if tucked:
            self.tucked_hem = hem_z
        off = offset if offset is not None else (0.004 if tucked else 0.012)
        if neck == "crew":
            nz = self.collar_z()
        elif neck == "scoop":
            nz = self.collar_z(depth=0.075, width=0.09)
        elif neck == "vneck":
            nz = self.vneck_z(0.09, 0.07)
        elif neck in ("collar", "mock"):
            nz = self.collar_z(depth=0.02, width=0.07, back=0.022)
        else:
            nz = self.collar_z()
        def keep(c, bone):
            ok = bone in TORSO or (bone in ARMS and SLEEVES[sleeve] is not None and SLEEVES[sleeve][0] == "lowerarm")
            return ok and hem_z - 0.02 < c.z < L["neck"] + 0.05
        cuts = [(Vector((0, 0, hem_z)), Vector((0, 0, -1)), lambda c: abs(c.x) < 0.24)] + self.sleeve_cuts(sleeve)
        if sleeve == "none":
            for side, sx in (("l", 1), ("r", -1)):
                p, d = k.bone_pt("upperarm_" + side, 0.05)
                cuts.append((p + Vector((-sx * 0.02, 0, 0)), Vector((sx, 0, 0.25)).normalized(), {"upperarm_" + side, "clavicle_" + side}))
        ob = k.shell(name, keep, cuts, offset=off, trims=(lambda c: c.z - float(nz(c.x, c.y)),))
        if not tucked:
            k.hang(ob, z_from=L["chest"] - 0.02, z_band=(hem_z, L["chest"] - 0.02), axis_y=0.0, x_max=0.19, fade=0.08)
        if drape:
            k.drape_front(ob, z_top=L["neck"] - 0.06, z_bottom=(L["waist"] - 0.02 if not tucked else self.rise + 0.02), x_max=0.19,
                          slope=0.35 if k.body_gender < 0.5 else 0.45)
        self.sleeve_inflate(ob, sleeve, 0.006 + fit)
        if fit > 0:
            k.inflate(ob, lambda co, n: n * fit * 0.5 if abs(co.x) < 0.19 else Vector((0, 0, 0)))
        collar = None
        if neck in ("collar", "mock"):
            collar = self.collar_band(name + "Collar", collar_rgb or color, height=0.022 if neck == "collar" else 0.034,
                                      off=off + 0.004, open_front=(neck == "collar"), flare=0.012 if neck == "collar" else 0.004)
        spec = dict(kind="top", color=color, sleeve=sleeve, neck=neck, nz=nz, hem_z=hem_z, weave=weave, heather=heather,
                    rough=rough, sheen=sheen, placket=placket, pocket=pocket, epaulettes=epaulettes, stripes=stripes, zip=zip,
                    cuffs=cuffs, hem_rib=hem_rib, decals=decals, buttons_rgb=buttons_rgb, pattern=pattern)
        self.items.append(("top", ob, spec))
        if collar is not None:
            self.items.append(("collar", collar, dict(color=collar_rgb or color, weave=weave)))
        return ob

    def collar_band(self, name, color, height=0.032, off=0.012, open_front=True, flare=0.006):
        """A shirt / polo collar or a jersey's stand collar: a band round the neck base."""
        k, L = self.k, self.L
        nz = self.collar_z(depth=0.02, width=0.07, back=0.022)
        def keep(c, bone):
            return bone in {"neck_01", "spine_03", "clavicle_l", "clavicle_r"} and L["neck"] - 0.06 < c.z < L["neck"] + 0.07
        def band(c):
            base = float(nz(c.x, c.y))
            return max(base - 0.004 - c.z, c.z - (base + height))
        trims = [band]
        if open_front:
            trims.append(lambda c: 0.012 - abs(c.x) if c.y < L["neck_y"] - 0.03 else -1.0)
        ob = k.shell(name, keep, (), offset=off, trims=tuple(trims))
        # the band flares out a little at its top edge
        # a shirt collar folds down and out over the band: the top edge flares away from the neck
        k.inflate(ob, lambda co, n: n * flare * float(smooth(nz(co.x, co.y), nz(co.x, co.y) + height, co.z)))
        return ob

    def g_jacket(self, name="Jacket", color=(40, 40, 44), open=False, opening=(0.07, 0.05, 0.075), lapels=False,
                 zip=False, collar="none", length="hip", weave="twill", heather=0.05, rough=0.8, sheen=0.2, fit=0.004,
                 pockets="flap", buttons=0, panels=False, cuffs=False, hem_rib=False, decals=(), lining_rgb=None, padded=0.0):
        """Blazers, cardigans, bombers, zip jackets, motorcycle jackets (long sleeves)."""
        k, L = self.k, self.L
        hem = L["hip"] - 0.005 if length == "hip" else (L["hip"] + 0.04 if length == "waist" else L["hip"] - 0.07)
        def keep(c, bone):
            if bone not in TORSO | ARMS or c.z < hem - 0.02:
                return False
            return not (bone == "neck_01" and c.z > L["neck"] + 0.03)
        neck_n = Vector((0, -0.25, 1)).normalized()
        top = L["neck"] + (0.035 if collar in ("stand", "rib") else 0.012)
        cuts = [(Vector((0, 0, top)), neck_n, None), (Vector((0, 0, hem)), Vector((0, 0, -1)), lambda c: abs(c.x) < 0.25)]
        cuts += self.sleeve_cuts("long")
        ob = k.shell(name, keep, cuts, offset=0.015 + fit)
        k.hang(ob, z_from=L["chest"] - 0.02, z_band=(hem, L["chest"] - 0.02), axis_y=0.0, x_max=0.2, fade=0.07)
        k.drape_front(ob, z_top=L["neck"] - 0.06, z_bottom=L["waist"] - 0.03, x_max=0.2, slope=0.4)
        self.sleeve_inflate(ob, "long", 0.008 + fit)
        if padded > 0:
            # armour / padding: shoulders and elbows stand proud
            sh = [k.bone_pt("upperarm_" + s, 0.1)[0] for s in ("l", "r")]
            el = [k.bone_pt("lowerarm_" + s, 0.0)[0] for s in ("l", "r")]
            def pad(co, n):
                w = 0.0
                for p in sh + el:
                    w = max(w, float(smooth(0.07, 0.03, (co - p).length)))
                return n * padded * w
            k.inflate(ob, pad)
        edge_w = None
        if open:
            zs = [hem, L["chest"] - 0.02, L["neck"] + 0.02]
            edge_w = self.edge_curve(zs, list(opening))
            k.trim(ob, lambda c: float(edge_w(c.z)) * float(smooth(-0.01, -0.05, c.y)) - abs(c.x))
        spec = dict(kind="jacket", color=color, open=open, edge_w=edge_w, lapels=lapels, zip=zip, collar=collar, hem=hem,
                    weave=weave, heather=heather, rough=rough, sheen=sheen, pockets=pockets, buttons=buttons, panels=panels,
                    cuffs=cuffs, hem_rib=hem_rib, decals=decals)
        self.items.append(("jacket", ob, spec))
        if collar in ("stand", "rib"):
            band = self.collar_band(name + "Collar", color, height=0.04, off=0.02 + fit, open_front=False)
            self.items.append(("collar", band, dict(color=color, weave="knit" if collar == "rib" else weave)))
        return ob

    def g_vest(self, name="Vest", color=(255, 120, 10), kind="hivis", stripes=(200, 200, 200), decals=(), open=False):
        """Hi-vis safety vests (reflective bands) and waistcoats (kind="waistcoat")."""
        k, L = self.k, self.L
        hem = L["hip"] + (0.0 if kind == "hivis" else 0.03)
        def keep(c, bone):
            return bone in TORSO - {"upperarm_l", "upperarm_r"} and hem - 0.02 < c.z < L["neck"] + 0.04
        cuts = [(Vector((0, 0, hem)), Vector((0, 0, -1)), None)]
        armpit = L["shoulder"] - 0.075
        def armhole(c):
            # the vest's side edge: full width below the armpit, an oval armhole up to a shoulder strap
            lim = np.interp(c.z, [armpit - 0.02, armpit + 0.02, L["shoulder"] - 0.01, L["shoulder"] + 0.04], [0.4, 0.165, 0.15, 0.128])
            return abs(c.x) - float(lim)
        depth = 0.17 if kind == "waistcoat" else 0.1
        nz = self.vneck_z(depth, 0.085 if kind == "waistcoat" else 0.075)
        ob = k.shell(name, keep, cuts, offset=0.019 if kind == "hivis" else 0.013,
                     trims=(lambda c: c.z - float(nz(c.x, c.y)), armhole))
        k.drape_front(ob, z_top=L["neck"] - 0.06, z_bottom=L["waist"] - 0.03, x_max=0.2, slope=0.3)
        if kind == "hivis":
            k.hang(ob, z_from=L["chest"], z_band=(hem, L["chest"]), axis_y=0.0, x_max=0.21, fade=0.06)
        spec = dict(kind=kind, color=color, stripes=stripes, decals=decals, hem=hem, nz=nz)
        self.items.append(("vest", ob, spec))
        return ob

    def g_apron(self, name="Apron", color=(60, 90, 140), kind="bib", length="knee", strap_rgb=None, decals=(), pocket=True):
        """Bib aprons (chest to knee, neck strap) and waist aprons: a cloth panel built as a grid in
        front of the body (not grown from it): each row follows a gentle curve just in front of the
        most forward point of the body, the cloth hangs straight down (it may not recede more than a
        little below the bust / belly) and spans the gap between the legs."""
        import bmesh
        k, L = self.k, self.L
        top = L["chest"] + 0.12 if kind == "bib" else self.rise + 0.005
        bottom = {"knee": L["knee"] + 0.02, "thigh": L["crotch"] - 0.15, "shin": L["knee"] - 0.12}[length]
        body, _ = k.body_bmesh()
        co = np.array([tuple(v.co) for v in body.verts], np.float32)
        body.free()
        # the garments already on (coat, shirt, trousers) are part of what the apron hangs over
        for kind_, gob, _ in self.items:
            if kind_ in ("top", "jacket", "trousers", "collar", "belt"):
                mw = gob.matrix_world
                co = np.concatenate([co, np.array([tuple(mw @ v.co) for v in gob.data.vertices], np.float32)])
        front = co[(co[:, 1] < 0.02) & (np.abs(co[:, 0]) < 0.3)]
        nx, nz = 26, 34
        zs = np.linspace(bottom, top, nz)
        def half_width(z):
            if kind == "bib":
                return float(np.interp(z, [bottom, L["waist"] - 0.02, L["chest"], top], [0.21, 0.205, 0.12, 0.11]))
            return 0.215
        grid = np.zeros((nz, nx, 3), np.float32)
        for i, z in enumerate(zs):
            hw = half_width(z)
            xs = np.linspace(-hw, hw, nx)
            band = front[(np.abs(front[:, 2] - z) < 0.02) & (np.abs(front[:, 0]) < hw + 0.02)]   # only what the cloth covers
            curv = 2.4 if z > L["waist"] else 1.4
            # the flattest curve y = a + curv * x^2 that stays in front of every point of the row
            a_ = float((band[:, 1] - curv * band[:, 0] ** 2).min()) if len(band) else -0.12
            grid[i, :, 0] = xs
            grid[i, :, 1] = a_ + curv * xs ** 2 - 0.024
            grid[i, :, 2] = z
        # hang: going down a column the cloth may come forward freely but recede at most 6 cm per m
        for j in range(nx):
            for i in range(nz - 2, -1, -1):
                grid[i, j, 1] = min(grid[i, j, 1], grid[i + 1, j, 1] + 0.06 * (zs[i + 1] - zs[i]))
        bm = bmesh.new()
        vs = [[bm.verts.new(tuple(float(c) for c in grid[i, j])) for j in range(nx)] for i in range(nz)]
        uv = bm.loops.layers.uv.new("PatternUV")
        for i in range(nz - 1):
            for j in range(nx - 1):
                f = bm.faces.new((vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]))
                for l, (u, v) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                    l[uv].uv = (u / (nx - 1), v / (nz - 1))
        bm.normal_update()
        for f in bm.faces:
            if f.normal.y > 0:
                f.normal_flip()
        oname = k.name + "_" + name
        old = bpy.data.objects.get(oname)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        me = bpy.data.meshes.new(oname)
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = True
        ob = bpy.data.objects.new(oname, me)
        k.col["Clothes"].objects.link(ob)
        k.garments.append(ob)
        spec = dict(kind=kind, color=color, strap_rgb=strap_rgb or color, decals=decals, top=top, bottom=bottom, pocket=pocket)
        self.items.append(("apron", ob, spec))
        return ob

    def g_scarf(self, name="Scarf", color=(120, 22, 36), pattern=None):
        """A neckerchief: a band round the neck and a small knot with two short tails at the throat."""
        k, L = self.k, self.L
        band = self.collar_band(name + "Band", color, height=0.03, off=0.021, open_front=False, flare=0.003)
        self.items.append(("collar", band, dict(color=color, weave="twill")))
        knot_z = L["neck"] - 0.012
        def keep(c, bone):
            return c.y < L["neck_y"] - 0.02 and L["neck"] - 0.12 < c.z < L["neck"] + 0.02 and abs(c.x) < 0.08
        def tie(c):
            if c.z > knot_z - 0.015:
                w = 0.016 + 0.3 * max(0.0, c.z - (knot_z - 0.015))
                return max(abs(c.x) - min(w, 0.03), c.z - (knot_z + 0.012))
            # two tails, crossing and widening down to 7 cm below the knot
            t = (knot_z - 0.015 - c.z) / 0.07
            centre = 0.008 + 0.012 * t
            w = 0.012 + 0.008 * t
            return max(abs(abs(c.x) - centre) - w, (knot_z - 0.085) - c.z)
        ob = k.shell(name + "Tie", keep, (), offset=0.023, trims=(tie,))
        self.items.append(("collar", ob, dict(color=color, weave="twill")))
        return ob

    def g_trousers(self, name="Trousers", color=(45, 45, 48), kind="slacks", hem=None, width=0.068, taper=0.01,
                   rise=None, crease=None, pockets=None, weave=None, heather=0.06, rough=0.8, decals=(), stripes=None,
                   cargo=False, belt_loops=True):
        """slacks | chinos | jeans | cargo | work | leggings | joggers | shorts | running_shorts | bike_shorts."""
        k, L = self.k, self.L
        r = rise if rise is not None else self.rise
        self.rise = r
        tight = kind in ("leggings", "bike_shorts")
        if hem is None:
            hem = {"shorts": L["knee"] + 0.07, "running_shorts": L["crotch"] - 0.16, "bike_shorts": L["knee"] + 0.1}.get(kind, L["ankle"] + 0.012)
        long_leg = hem < L["knee"]
        def keep(c, bone):
            return bone in LEGS and hem - 0.03 < c.z < r + 0.02
        cuts = [(Vector((0, 0, r)), Vector((0, 0, 1)), None), (Vector((0, 0, hem)), Vector((0, 0, -1)), lambda c: c.z < L["crotch"])]
        off = 0.002 if tight else 0.007
        ob = k.shell(name, keep, cuts, offset=off)
        if not tight:
            knee_r = {}
            for s in ("l", "r"):
                knee_r[s] = (k.rig.matrix_world @ k.rig.data.bones["calf_" + s].head_local, k.rig.matrix_world @ k.rig.data.bones["foot_" + s].head_local,
                             k.rig.matrix_world @ k.rig.data.bones["thigh_" + s].head_local)
            def straighten(co, n):
                s = "l" if co.x > 0 else "r"
                kc, ac, hc = knee_r[s]
                if kind in ("shorts", "running_shorts"):
                    # wide straight legs from the crotch down
                    t = max(0.0, min(1.0, (hc.z - co.z) / max(hc.z - kc.z, 0.1)))
                    axis = hc.lerp(kc, t)
                    want = 0.085 + (0.012 if kind == "running_shorts" else 0.0)
                    w = smooth(L["crotch"] + 0.02, L["crotch"] - 0.04, co.z)
                else:
                    if co.z > kc.z + 0.06:
                        return Vector((0, 0, 0))
                    t = max(0.0, min(1.0, (kc.z - co.z) / max(kc.z - ac.z, 0.1)))
                    axis = kc.lerp(ac, t)
                    want = width - taper * t + (0.008 * float(smooth(0.85, 1.0, t)) if kind == "jeans" else 0.0)
                    w = smooth(kc.z + 0.06, kc.z - 0.04, co.z)
                rad = Vector((co.x - axis.x, co.y - axis.y, 0))
                if rad.length < 1e-4:
                    return Vector((0, 0, 0))
                return rad.normalized() * max(0.0, want - rad.length) * float(w)
            k.inflate(ob, straighten)
            if cargo:
                # side pockets stand off the thigh
                pk = [(k.bone_pt("thigh_" + s, 0.55)[0], 1 if s == "l" else -1) for s in ("l", "r")]
                def pocket(co, n):
                    for p, sx in pk:
                        d = Vector((0, co.y - p.y, co.z - p.z))
                        if co.x * sx > 0 and abs(co.x) > abs(p.x) + 0.03 and d.length < 0.08:
                            return Vector((sx, 0, 0)) * 0.012 * float(smooth(0.08, 0.05, d.length))
                    return Vector((0, 0, 0))
                k.inflate(ob, pocket)
        k.bridge_crotch(ob, L["crotch"])
        weave = weave or {"jeans": "denim", "leggings": "knit", "joggers": "knit", "bike_shorts": "knit", "running_shorts": "twill"}.get(kind, "twill")
        spec = dict(kind=kind, color=color, rise=r, hem=hem, crease=crease if crease is not None else kind == "slacks",
                    pockets=pockets or {"jeans": "jeans", "slacks": "slant", "chinos": "slant", "cargo": "cargo", "work": "cargo"}.get(kind, None),
                    weave=weave, heather=heather, rough=rough, decals=decals, stripes=stripes, belt_loops=belt_loops and not tight and kind != "running_shorts",
                    long_leg=long_leg)
        self.items.append(("trousers", ob, spec))
        return ob

    def g_belt(self, name="Belt", color=(26, 22, 20), width=0.035, buckle=(150, 150, 152), duty=False):
        k, L = self.k, self.L
        top = self.rise + 0.004
        def keep(c, bone):
            return bone in {"pelvis", "spine_01", "thigh_l", "thigh_r"} and top - width - 0.03 < c.z < top + 0.03
        ob = k.shell(name, keep, (), offset=0.013 + (0.004 if duty else 0.0),
                     trims=(lambda c: max(c.z - top, top - width * (1.5 if duty else 1.0) - c.z),))
        self.items.append(("belt", ob, dict(color=color, buckle=buckle, duty=duty, top=top, width=width * (1.5 if duty else 1.0))))
        if duty:
            self.duty_gear()
        return ob

    def duty_gear(self):
        """Pouches, radio and holster on a police / security duty belt (boxes on the pelvis)."""
        import bmesh
        k = self.k
        top = self.rise + 0.004
        parts = [(0.15, -0.02, 0.06, 0.05, 0.11, "holster"), (-0.15, 0.0, 0.05, 0.04, 0.08, "radio"),
                 (0.07, -0.13, 0.05, 0.035, 0.05, "pouch"), (-0.07, -0.13, 0.05, 0.035, 0.05, "pouch"),
                 (0.0, 0.14, 0.07, 0.035, 0.05, "cuffs")]
        body, _ = k.body_bmesh()                       # without MPFB helper geometry
        co = np.array([tuple(v.co) for v in body.verts], np.float32)
        body.free()
        bm = bmesh.new()
        for x, y, w, d, h, _ in parts:
            # sit on the belt's outer surface: the body's extent at that height and angle
            band = co[(np.abs(co[:, 2] - (top - 0.02)) < 0.02)]
            ang = math.atan2(x, -y)
            a = np.arctan2(band[:, 0], -band[:, 1])
            near = band[np.abs(np.angle(np.exp(1j * (a - ang)))) < 0.15]
            r = float(np.hypot(near[:, 0], near[:, 1]).max()) + 0.018 if len(near) else 0.17
            cx, cy = r * math.sin(ang), -r * math.cos(ang)
            res = bmesh.ops.create_cube(bm, size=1.0)
            vs = res["verts"]
            for v in vs:
                v.co.x *= w
                v.co.y *= d
                v.co.z *= h
            rot = Vector((math.sin(ang), -math.cos(ang), 0)).to_track_quat("-Y", "Z")
            for v in vs:
                v.co = rot @ v.co + Vector((cx, cy, top - 0.02 - h * 0.3))
        bevel_geom = bm.edges[:]
        bmesh.ops.bevel(bm, geom=bevel_geom, offset=0.006, segments=2, affect="EDGES")
        me = bpy.data.meshes.new(k.name + "_DutyGear")
        bm.to_mesh(me)
        bm.free()
        old = bpy.data.objects.get(k.name + "_DutyGear")
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob = bpy.data.objects.new(k.name + "_DutyGear", me)
        k.col["Clothes"].objects.link(ob)
        k.garments.append(ob)
        ob.data.materials.append(k.plain("M_%s_DutyGear" % k.name, (22, 22, 24), rough=0.45, coat=0.2))
        self.items.append(("gear", ob, {}))

    def g_shoes(self, kind="sneaker", color=(240, 240, 240), sole=(235, 235, 235), sock=None, sock_height=None):
        """sneaker / runner (MPFB shoes05 / 06 recoloured), dress (shoes04), brown_dress (shoes01),
        boot (shoes03), flat (shoe last, women's flats), cycling (shoe last, stiff, with cleat)."""
        k = self.k
        if kind in ("boot", "work_boot"):
            ob = k.shoe("Shoes", heel_z=0.13, slope=0.02, offset=0.006, pull=0.45)
            k.inflate(ob, lambda co, n: (n * 0.006 + Vector((0, 0, -0.004))) * float(smooth(0.03, 0.012, co.z)))   # lug sole
            self.items.append(("boots", ob, dict(kind=kind, color=color, sole=sole)))
            return ob
        if kind in ("flat", "pump", "cycling"):
            ob = k.shoe("Shoes", heel_z=0.046 if kind != "cycling" else 0.075, slope=0.17 if kind != "cycling" else 0.05,
                        offset=0.0025 if kind != "cycling" else 0.004)
            if kind == "pump":
                k.inflate(ob, lambda co, n: Vector((0, 0, 0.012)) * float(smooth(0.0, -0.08, co.y - k.bone_pt("foot_l" if co.x > 0 else "foot_r", 0)[0].y)) * float(co.z < 0.03))
            self.items.append(("shoes_last", ob, dict(kind=kind, color=color, sole=sole)))
            return ob
        asset = {"sneaker": "shoes05", "runner": "shoes06", "dress": "shoes04", "brown_dress": "shoes01", "brogue": "shoes03",
                 "trainer": "shoes02"}[kind]
        ob = k.add_asset("clothes/%s/%s.mhclo" % (asset, asset))
        if sock_height is not None:
            # the MPFB shoes carry a mid-calf tube sock: cut it to ankle / crew height and let the
            # body show above it (hide_under then masks only what the shoe still covers)
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            mw = ob.matrix_world
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if (mw @ f.calc_center_median()).z > sock_height], context="FACES")
            bm.to_mesh(ob.data)
            bm.free()
            for m in [m for m in k.body.modifiers if m.type == "MASK" and m.name.startswith("Delete.")]:
                k.body.modifiers.remove(m)
        self.items.append(("shoes_asset", ob, dict(kind=kind, color=color, sole=sole, sock=sock, asset=asset)))
        return ob

    # ------------------------------------------------------------------ materials
    def paint(self):
        k, L = self.k, self.L
        for kind, ob, spec in self.items:
            getattr(self, "paint_" + kind)(ob, spec)

    def _decals(self, decals, P, rgb, r):
        for d in decals:
            rgb, r = d.apply(P, rgb, r, rough_value=0.6)
        return rgb, r

    def paint_top(self, ob, s):
        k, L = self.k, self.L
        k.pattern_uv(ob, lambda c: ("sleeve_l" if c.x > 0 else "sleeve_r") if abs(c.x) > 0.2 else ("front" if c.y < 0 else "back"))
        nz, hem_z = s["nz"], s["hem_z"]
        sl = SLEEVES[s["sleeve"]]
        ends = [k.bone_pt("%s_%s" % (sl[0], side), sl[1]) for side in ("l", "r")] if sl else []
        def h_fn(P, N, M):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            h = np.zeros(P.shape[:2], np.float32)
            e = nz(x, y) - z
            if s["neck"] in ("crew", "scoop", "vneck"):
                band = (e >= 0) & (e < 0.016)
                h += np.where(band, 0.0002 * np.abs(np.sin(2 * np.pi * np.arctan2(x, y - L["neck_y"]) * 0.07 / 0.0026)), 0)
                h += np.where(np.abs(e - 0.016) < 0.0012, -0.0003, 0)
            if not s["hem_rib"]:
                for off in (0.016, 0.022):
                    h += np.where(np.abs(z - (hem_z + off)) < 0.0007, -0.00025, 0)
            else:
                h += np.where(z < hem_z + 0.045, 0.0002 * np.abs(np.sin(2 * np.pi * np.arctan2(x, -y) * 0.16 / 0.004)), 0)
            for (p, d) in ends:
                p = np.array(p, np.float32); d = np.array(d, np.float32)
                along = (P - p) @ d
                side = np.sign(x) == np.sign(p[0])
                if s["cuffs"]:
                    h += np.where(side & (along > -0.06) & (along < 0), 0.0002 * np.abs(np.sin(2 * np.pi * np.arctan2(P[..., 1] - p[1], P[..., 2] - p[2]) * 0.045 / 0.0035)), 0)
                for off in (-0.016, -0.022):
                    h += np.where(side & (np.abs(along - off) < 0.0007), -0.00025, 0)
            h += np.where((np.abs(np.abs(x) - 0.175) < 0.0012) & (z > L["shoulder"] - 0.02), -0.0003, 0)
            pl = s["placket"]
            if pl:
                length = 0.12 if pl == "polo" else (L["neck"] - hem_z)
                xc = 0.0 if pl != "double" else 0.055
                line = (y < -0.02) & (z > L["neck"] - length) & (np.abs(np.abs(x) - (xc + 0.013)) < 0.0012)
                h += np.where(line, -0.00035, 0)
                h += np.where((y < -0.02) & (z > L["neck"] - length) & (np.abs(x - xc) < 0.012), 0.00015, 0)
            if s["pocket"]:
                d = np.maximum(np.abs(x - 0.075) - 0.05, np.abs(z - (L["chest"] + 0.07)) - 0.06)
                h += np.where((y < -0.02) & (np.abs(d) < 0.0012), -0.0003, 0) + np.where((y < -0.02) & (d < 0), 0.00012, 0)
            if s["zip"]:
                h += np.where((y < -0.03) & (np.abs(x) < 0.006), 0.0004, 0)
            if s["epaulettes"]:
                strap = (np.abs(y - L["neck_y"]) < 0.025) & (np.abs(x) > 0.07) & (np.abs(x) < 0.17) & (z > L["shoulder"] - 0.01)
                h += np.where(strap, 0.0008, 0)
            return h
        def c_fn(P, N, M, rgb, r):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            if s["pattern"] == "check":
                c2 = rgb * 0.82
                chk = ((np.floor(x / 0.012) + np.floor(z / 0.012)) % 2) == 0
                rgb = np.where(chk[..., None], c2, rgb)
            elif s["pattern"] == "stripe":
                st = (np.floor((x + 1) / 0.006) % 3) == 0
                rgb = np.where(st[..., None], rgb * 0.8 + 0.12, rgb)
            pl = s["placket"]
            if pl:
                length = 0.12 if pl == "polo" else (L["neck"] - hem_z)
                n_btn = 3 if pl == "polo" else max(4, int(length / 0.09))
                cols = [0.0] if pl != "double" else [0.055, -0.055]
                for xc in cols:
                    for i in range(n_btn):
                        bz = L["neck"] - 0.02 - i * (length - 0.04) / max(n_btn - 1, 1)
                        m = (y < -0.02) & (np.hypot(x - xc, z - bz) < 0.0055)
                        rgb[m] = rgb01(s["buttons_rgb"])
                        r[m] = 0.3
            if s["stripes"]:
                col, zs_, w = s["stripes"]
                for zz in zs_:
                    m = np.abs(z - zz) < w / 2
                    rgb[m] = rgb01(col)
                    r[m] = 0.35
            if s["epaulettes"]:
                strap = (np.abs(y - L["neck_y"]) < 0.025) & (np.abs(x) > 0.07) & (np.abs(x) < 0.17) & (z > L["shoulder"] - 0.01)
                rgb[strap] *= 0.85
            if s["zip"]:
                m = (y < -0.03) & (np.abs(x) < 0.004)
                rgb[m] = np.array([0.12, 0.12, 0.13])
                r[m] = 0.3
            return self._decals(s["decals"], P, rgb, r)
        k.paint_fabric(ob, s["color"], height_fn=h_fn, color_fn=c_fn, weave=s["weave"], heather=s["heather"],
                       rough=s["rough"], sheen=s["sheen"], seed=hash(ob.name) % 1000)

    def paint_collar(self, ob, s):
        k = self.k
        k.pattern_uv(ob, lambda c: "f" if c.y < 0 else "b")
        def h_fn(P, N, M):
            return 0.00015 * np.abs(np.sin(2 * np.pi * P[..., 2] / 0.004)) * (s.get("weave") == "knit")
        k.paint_fabric(ob, s["color"], height_fn=h_fn, weave="twill", heather=0.04, rough=0.85, sheen=0.25, size=512, seed=3)

    def paint_jacket(self, ob, s):
        k, L = self.k, self.L
        def label(c):
            if abs(c.x) > 0.19 and c.z > L["chest"] - 0.12:
                return "sleeve_l" if c.x > 0 else "sleeve_r"
            return "front_l" if (c.y < 0.0 and c.x > 0) else ("front_r" if c.y < 0.0 else "back")
        k.pattern_uv(ob, label)
        edge_w, hem = s["edge_w"], s["hem"]
        def band(P):
            if edge_w is None:
                return np.full(P.shape[:2], -1.0)
            return np.where(P[..., 1] < -0.045, np.abs(P[..., 0]) - edge_w(P[..., 2]), -1.0)
        pockets = [(sx * 0.11, L["hip"] + 0.07) for sx in (1, -1)]
        def h_fn(P, N, M):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            h = np.zeros(P.shape[:2], np.float32)
            e = band(P)
            on = (e >= 0) & (e < 0.02)
            if s["lapels"]:
                lap = on | ((e >= 0) & (e < 0.055) & (z > L["chest"] - 0.04))
                h += np.where(lap, 0.0004, 0) + np.where(np.abs(e - 0.055) < 0.0015, -0.0005, 0) * (z > L["chest"] - 0.04)
            else:
                h += np.where(on, 0.00025, 0) + np.where(np.abs(e - 0.02) < 0.0013, -0.0003, 0)
            if s["hem_rib"]:
                h += np.where(z < hem + 0.05, 0.0002 * np.abs(np.sin(2 * np.pi * np.arctan2(x, -y) * 0.16 / 0.004)), 0)
            if s["zip"]:
                h += np.where((y < -0.03) & (np.abs(x) < 0.006), 0.0005, 0)
            if s["pockets"] == "flap":
                for px, pz in pockets:
                    d = np.maximum(np.abs(x - px) - 0.06, np.abs(z - pz) - 0.008)
                    h += np.where((y < -0.02) & (d < 0), 0.0004, 0) + np.where((y < -0.02) & (np.abs(d) < 0.0012), -0.0004, 0)
            elif s["pockets"] == "welt":
                for px, pz in pockets:
                    m = (y < -0.02) & (np.abs(x - px) < 0.07) & (np.abs(z - pz) < 0.004) & (np.abs(x) > 0.04)
                    h += np.where(m, -0.0005, 0)
            if s["panels"]:
                for zz in (L["chest"] + 0.02, L["waist"]):
                    h += np.where(np.abs(z - zz) < 0.0015, -0.0005, 0)
                h += np.where((np.abs(np.abs(x) - 0.2) < 0.0015), -0.0004, 0)
            h += np.where((np.abs(np.abs(x) - 0.18) < 0.0012) & (z > L["shoulder"] - 0.02), -0.0003, 0)
            return h
        def c_fn(P, N, M, rgb, r):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            e = band(P)
            if s["buttons"] and edge_w is not None:
                for i in range(s["buttons"]):
                    bz = L["waist"] + 0.02 - i * 0.075
                    d = np.hypot(e - 0.01, z - bz)
                    m = (x > 0) & (e >= 0) & (d < 0.009)
                    rgb[m] = np.array([0.06, 0.06, 0.06])
                    r[m] = 0.3
            if s["zip"]:
                m = (y < -0.03) & (np.abs(x) < 0.004)
                rgb[m] = np.array([0.1, 0.1, 0.11])
                r[m] = 0.3
            if s["panels"]:
                m = (y < -0.02) & ((np.abs(np.abs(x) - 0.2) < 0.03) | (z > L["chest"] + 0.02)) & (np.abs(x) > 0.03)
                rgb[m] *= 0.55
            return self._decals(s["decals"], P, rgb, r)
        k.paint_fabric(ob, s["color"], height_fn=h_fn, color_fn=c_fn, weave=s["weave"], heather=s["heather"], rough=s["rough"],
                       sheen=s["sheen"], seed=hash(ob.name) % 1000)

    def paint_vest(self, ob, s):
        k, L = self.k, self.L
        k.pattern_uv(ob, lambda c: "f_l" if (c.y < 0 and c.x > 0) else ("f_r" if c.y < 0 else "b"))
        def h_fn(P, N, M):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            h = np.where((y < -0.03) & (np.abs(x) < 0.006), 0.0004, 0.0).astype(np.float32)
            if s["kind"] == "hivis":
                h += 0.00012 * np.abs(np.sin(2 * np.pi * x / 0.0025)) * np.abs(np.sin(2 * np.pi * z / 0.0025))   # mesh fabric
            return h
        def c_fn(P, N, M, rgb, r):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            if s["kind"] == "hivis":
                col = rgb01(s["stripes"])
                lime = np.array([0.80, 0.95, 0.10])
                hb = [L["waist"] - 0.045, L["waist"] + 0.065]
                horiz = np.min([np.abs(z - zz) for zz in hb], axis=0)
                vert = np.where((z > hb[1]) & (y < L["neck_y"] + 0.02), np.abs(np.abs(x) - 0.085), 1.0)
                vert = np.where((z > hb[1]) & (y >= L["neck_y"] + 0.02), np.abs(np.abs(x) - 0.085), vert)
                d = np.minimum(horiz, vert)
                edge = (d >= 0.017) & (d < 0.024)
                band = d < 0.017
                rgb[edge] = lime
                rgb[band] = col
                r[band] = 0.22
            else:
                for i in range(4):
                    bz = L["waist"] + 0.06 - i * 0.045
                    m = (y < -0.02) & (np.hypot(x - 0.004, z - bz) < 0.006)
                    rgb[m] = np.array([0.08, 0.08, 0.08])
                    r[m] = 0.3
                rgb[(y > 0.0)] *= 1.12   # satin back
                r[(y > 0.0)] = 0.35
            return self._decals(s["decals"], P, rgb, r)
        hivis = s["kind"] == "hivis"
        m = k.paint_fabric(ob, s["color"], height_fn=h_fn, color_fn=c_fn, weave="twill", heather=0.03 if hivis else 0.05,
                           rough=0.7 if hivis else 0.75, sheen=0.2, seed=7)
        if hivis:
            p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            tb = next(n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image.name.endswith("_basecolor"))
            m.node_tree.links.new(tb.outputs["Color"], p.inputs["Emission Color"])
            p.inputs["Emission Strength"].default_value = 0.12          # fluorescent dye reads brighter than white

    def paint_apron(self, ob, s):
        k, L = self.k, self.L
        top, bottom = s["top"], s["bottom"]
        def h_fn(P, N, M):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            h = np.zeros(P.shape[:2], np.float32)
            edges = (np.abs(z - top) < 0.012) | (np.abs(z - bottom) < 0.014)
            h += np.where(edges, 0.0003, 0)
            if s["pocket"]:
                d = np.maximum(np.abs(x) - 0.12, np.abs(z - (L["crotch"] + 0.02)) - 0.06)
                h += np.where(np.abs(d) < 0.0012, -0.0004, 0) + np.where(d < 0, 0.0002, 0)
                h += np.where((d < 0) & (np.abs(x) < 0.0012), -0.0004, 0)
            return h
        def c_fn(P, N, M, rgb, r):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            # waist ties across the front
            m = np.abs(z - (L["waist"] - 0.01)) < 0.012
            rgb[m] = rgb01(s["strap_rgb"]) * 0.92
            return self._decals(s["decals"], P, rgb, r)
        k.paint_fabric(ob, s["color"], height_fn=h_fn, color_fn=c_fn, weave="twill", heather=0.08, rough=0.9, sheen=0.2, seed=9)
        if s["kind"] == "bib":
            self.apron_straps(ob, s)

    def apron_straps(self, apron, s):
        """Neck strap of a bib apron: a thin band from the bib's top corners round the back of the neck."""
        k, L = self.k, self.L
        nz = self.collar_z(depth=0.0, width=0.2, back=0.0)
        def keep(c, bone):
            return bone in {"neck_01", "spine_03", "clavicle_l", "clavicle_r"} and c.z > s["top"] - 0.02
        def strap(c):
            # two straps from x = +-0.1 at the bib top up to the neck sides, one band round the back
            if c.y < L["neck_y"] - 0.02:
                xs = np.interp(c.z, [s["top"], L["neck"]], [0.095, 0.06])
                return abs(abs(c.x) - float(xs)) - 0.011
            return abs(c.z - (L["neck"] - 0.005)) - 0.011
        ob = k.shell("ApronStrap", keep, (), offset=0.02, trims=(strap,))
        ob.data.materials.append(k.plain("M_%s_ApronStrap" % k.name, s["strap_rgb"], rough=0.9))
        self.items.append(("strap", ob, {}))

    def paint_strap(self, ob, s):
        pass

    def paint_gear(self, ob, s):
        pass

    def paint_trousers(self, ob, s):
        k, L = self.k, self.L
        k.pattern_uv(ob, lambda c: ("L" if c.x > 0 else "R") + ("front" if c.y < 0 else "back"))
        rise, hem = s["rise"], s["hem"]
        def stitches(P):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            front, back = y < -0.01, y > 0.01
            lines = []
            pk = s["pockets"]
            for sx in (1, -1):
                if pk in ("jeans", "slant"):
                    a = seg_dist(x * sx, z, (0.085, rise - 0.035), (0.11 if pk == "jeans" else 0.13, rise - 0.075 if pk == "jeans" else rise - 0.16))
                    b = seg_dist(x * sx, z, (0.11, rise - 0.075), (0.17, rise - 0.095)) if pk == "jeans" else np.ones_like(a)
                    lines.append(np.where(front, np.minimum(a, b), 1))
                if pk in ("jeans", "slant", "cargo"):
                    cx, top_, bot = 0.075, rise - 0.075, rise - (0.205 if pk == "jeans" else 0.12)
                    if pk == "jeans":
                        pts = [(cx - 0.065, top_), (cx + 0.065, top_), (cx + 0.06, bot + 0.02), (cx, bot), (cx - 0.06, bot + 0.02), (cx - 0.065, top_)]
                        d = np.min([seg_dist(x * sx, z, pts[i], pts[i + 1]) for i in range(5)], axis=0)
                    else:
                        d = np.abs(np.hypot((x * sx - cx) / 0.06, (z - (top_ + bot) / 2) / 0.003) - 1) * 0.003 + (np.abs(x * sx - cx) > 0.06)
                    lines.append(np.where(back, d, 1))
            lines.append(np.abs(z - (rise - 0.035)))
            if s["long_leg"]:
                lines.append(np.abs(z - (hem + 0.016)))
            fly = np.minimum(seg_dist(x, z, (0.032, rise - 0.035), (0.032, L["crotch"] + 0.06)), seg_dist(x, z, (0.032, L["crotch"] + 0.06), (0.004, L["crotch"] + 0.035)))
            if s["kind"] not in ("leggings", "bike_shorts", "joggers", "running_shorts"):
                lines.append(np.where(front, fly, 1))
            return lines
        thighs = [k.bone_pt("thigh_" + s_, 0.55)[0] for s_ in ("l", "r")]
        def h_fn(P, N, M):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            h = np.zeros(P.shape[:2], np.float32)
            for d in stitches(P):
                h += np.where(d < 0.0012, -0.0004, 0)
            if s["crease"]:
                for side, sx in (("l", 1), ("r", -1)):
                    kc = k.rig.matrix_world @ k.rig.data.bones["calf_" + side].head_local
                    cr = (np.abs(x - kc.x) < 0.0025) & (y < kc.y - 0.02) & (np.sign(x) == sx) & (z < rise - 0.06)
                    h += np.where(cr, 0.0006 * (1 - np.abs(x - kc.x) / 0.0025), 0)
            if s["belt_loops"]:
                wb = z > rise - 0.035
                ang = np.arctan2(x, -y)
                for a in (-2.7, -1.3, -0.45, 0.45, 1.3, 2.7, np.pi):
                    h += np.where(wb & (np.abs(np.angle(np.exp(1j * (ang - a)))) * 0.16 < 0.006), 0.0007, 0)
            if s["pockets"] == "cargo":
                for p, sx in zip(thighs, (1, -1)):
                    side = (x * sx > abs(p.x) + 0.02)
                    d = np.maximum(np.abs(y - p.y) - 0.07, np.abs(z - p.z) - 0.08)
                    h += np.where(side & (np.abs(d) < 0.0013), -0.0005, 0) + np.where(side & (d < 0), 0.0002, 0)
                    flap = side & (np.abs(y - p.y) < 0.07) & (np.abs(z - (p.z + 0.07)) < 0.012)
                    h += np.where(flap, 0.0004, 0)
            if s["kind"] in ("leggings", "joggers"):
                h += np.where(z > rise - 0.05, 0.0002 * np.abs(np.sin(2 * np.pi * z / 0.004)), 0)
            return h
        def c_fn(P, N, M, rgb, r):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            if s["kind"] == "jeans":
                front = y < -0.01
                thigh = front & (z > L["knee"] - 0.05) & (z < L["crotch"])
                wash = np.where(thigh, 0.18 * smooth(L["knee"] - 0.05, L["knee"] + 0.12, z) * smooth(L["crotch"], L["crotch"] - 0.08, z), 0)
                wash += np.where(front, 0.1 * np.exp(-((z - L["knee"]) / 0.05) ** 2), 0)
                rgb = np.clip(rgb * (1 + wash)[..., None], 0, 1)
                for d in stitches(P):
                    th = d < 0.0009
                    rgb[th] = rgb[th] * 0.35 + np.array([0.62, 0.48, 0.25]) * 0.65 if s["color"][2] > s["color"][0] else rgb[th] * 0.35 + np.array([0.3, 0.3, 0.29]) * 0.65
            if s["stripes"]:
                col, zs_, w = s["stripes"]
                for zz in zs_:
                    m = np.abs(z - zz) < w / 2
                    rgb[m] = rgb01(col)
                    r[m] = 0.3
            return self._decals(s["decals"], P, rgb, r)
        k.paint_fabric(ob, s["color"], height_fn=h_fn, color_fn=c_fn, weave=s["weave"], heather=s["heather"], rough=s["rough"],
                       sheen=0.15 if s["kind"] != "leggings" else 0.35, seed=hash(ob.name) % 1000)

    def paint_belt(self, ob, s):
        k = self.k
        k.pattern_uv(ob, lambda c: "f" if c.y < 0 else "b")
        top, w = s["top"], s["width"]
        def h_fn(P, N, M):
            z = P[..., 2]
            return np.where((np.abs(z - top + 0.003) < 0.001) | (np.abs(z - (top - w) - 0.003) < 0.001), -0.0003, 0.0).astype(np.float32)
        def c_fn(P, N, M, rgb, r):
            x, y, z = P[..., 0], P[..., 1], P[..., 2]
            m = (y < -0.05) & (np.abs(x) < 0.03)
            ring = m & ((np.abs(x) > 0.022) | (np.abs(z - (top - w / 2)) > w / 2 - 0.006))
            rgb[ring] = rgb01(s["buckle"])
            r[ring] = 0.25
            return rgb, r
        mat = k.paint_fabric(ob, s["color"], height_fn=h_fn, color_fn=c_fn, weave="none", heather=0.03, rough=0.45, sheen=0.0, size=512, seed=11)

    def paint_shoes_last(self, ob, s):
        k = self.k
        ob.data.materials.clear()
        rough = {"flat": 0.32, "pump": 0.25, "cycling": 0.4}[s["kind"]]
        ob.data.materials.append(k.plain("M_%s_Shoes" % k.name, s["color"], rough=rough, coat=0.25 if s["kind"] != "cycling" else 0.1))

    def paint_boots(self, ob, s):
        """Leather upper, darker rubber sole (faces under 2.4 cm), laces suggested by the material split."""
        k = self.k
        me = ob.data
        me.materials.clear()
        me.materials.append(k.plain("M_%s_BootLeather" % k.name, s["color"], rough=0.55, coat=0.1))
        me.materials.append(k.plain("M_%s_BootSole" % k.name, (28, 24, 22), rough=0.85))
        for poly in me.polygons:
            poly.material_index = 1 if poly.center.z < 0.024 else 0

    def paint_shoes_asset(self, ob, s):
        k = self.k
        target = rgb01(s["color"])
        sole = rgb01(s["sole"])
        sock = rgb01(s["sock"]) if s["sock"] else None
        asset = s["asset"]
        def fn(rgb, a):
            lum = rgb @ np.array([0.3, 0.55, 0.15], np.float32)
            h, w = rgb.shape[:2]
            yy, xx = np.mgrid[0:h, 0:w]
            u, v = xx / w, 1 - yy / h
            mx, mn = rgb.max(-1), rgb.min(-1)
            sat = (mx - mn) / np.maximum(mx, 1e-4)
            # keep the lightness detail of the source, take the hue / value of the target
            rel = np.clip(lum / max(float(np.median(lum[(sat > 0.15) | (lum < 0.5)])) if ((sat > 0.15) | (lum < 0.5)).any() else 0.4, 1e-3), 0.3, 1.8)
            out = np.clip(target[None, None, :] * rel[..., None], 0, 1)
            if asset in ("shoes05", "shoes06", "shoes02"):
                white = (lum > 0.62) & (sat < 0.18)
                out = np.where(white[..., None], np.clip(sole * (lum / 0.8)[..., None], 0, 1), out)
                if asset == "shoes06":
                    logo = (u > 0.42) & (u < 0.54) & (v > 0.76) & (v < 0.84)
                    out[logo] = np.median(out[~white], axis=0) if (~white).any() else out[logo]
            if sock is not None:
                sockm = (u > 0.76) & (v > 0.84)
                out[sockm] = sock * np.clip(lum[sockm] / 0.8, 0.5, 1.1)[:, None]
            return out
        k.recolor(ob, fn, "shoes_" + asset)


def stiffen(k, ob, bone, amount):
    """Blend a garment's skin weights towards one bone (an apron hangs from the waist instead of
    stretching between the thighs)."""
    if bone not in ob.vertex_groups:
        ob.vertex_groups.new(name=bone)
    gi = ob.vertex_groups[bone].index
    for v in ob.data.vertices:
        ws = {g.group: g.weight * (1 - amount) for g in v.groups}
        ws[gi] = ws.get(gi, 0.0) + amount
        for g, w in ws.items():
            ob.vertex_groups[g].add([v.index], w, "REPLACE")
    k.limit4(ob)


def finish(k, out):
    """Materials, rigging, body mask. Returns the number of masked body vertices."""
    out.paint()
    thick = {"top": 0.0015, "collar": 0.002, "jacket": 0.003, "vest": 0.0025, "apron": 0.002, "trousers": 0.002,
             "belt": 0.003, "strap": 0.0015, "shoes_last": 0.0025, "boots": 0.003}
    garments = []
    for kind, ob, spec in out.items:
        if kind == "shoes_asset":
            garments.append(ob)
            continue
        k.rig_garment(ob, thickness=thick.get(kind, 0.0))
        if kind == "apron":
            stiffen(k, ob, "pelvis" if spec["kind"] == "waist" else "spine_01", 0.6)
        # over other clothes (or loose in front): they never decide which skin is hidden
        if kind not in ("apron", "strap", "vest", "belt", "gear"):
            garments.append(ob)
    open_fn = None
    if out.tucked_hem is not None:
        top = next((ob for kind, ob, s in out.items if kind == "top"), None)
        open_fn = lambda go, co: not (go == top and co.z < out.tucked_hem + 0.03)
    return k.hide_under(garments, open_fn=open_fn)
