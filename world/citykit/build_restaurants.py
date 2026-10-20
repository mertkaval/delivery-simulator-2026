"""Restaurant interior kit: shell, front-of-house, kitchen and signature equipment for the
sixteen Turkish restaurants (RestaurantCatalog in Godot).

Local frame (Godot): +Z faces the customer / the street, y up, metres. Shell pieces are
4 m bay modules so one kit fits 3- and 4-bay storefronts. Wall paint, accent panels and
upholstery are near-white and tinted per restaurant via MultiMesh instance colours.

Built on build_houses.py (XMesh, helpers, AO bake, glTF export). Run headless:
  blender --background --factory-startup --python build_restaurants.py
Output: world/citykit/restaurants/<name>.glb (+ _far: same mesh minus small dressing).
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\GodotProjects\delivery-simulator-2026\world\citykit"
SRC = os.path.join(HERE, "build_houses.py")
H = {"__name__": "houses_lib", "__file__": SRC, "BUILD": False}
exec(compile(open(SRC).read(), SRC, "exec"), H)
H["OUT"] = os.path.join(HERE, "restaurants")
H["PALETTE"].update({
    "Terrazzo": ("ddd3c3", 0.25), "SubwayTile": ("f2f0ea", 0.15), "Cini": ("3a5fa8", 0.2), "WoodFloor": ("8e6040", 0.45),
    "Plaster": ("f1eee8", 0.85), "WallPaint": ("f4f2ee", 0.8), "AccentPaint": ("f2f0ea", 0.5), "Upholstery": ("efece6", 0.7),
    "Steel": ("c4c8ca", 0.28), "SteelDark": ("5d6366", 0.4), "CounterStone": ("e9e5dc", 0.18), "Oak": ("a77a4f", 0.5),
    "ClearGlass": ("cfe3e8", 0.05), "Chalkboard": ("1d2321", 0.85), "Copper": ("b06a3b", 0.3), "Brass": ("b8913f", 0.3),
    "MeatRoast": ("7a3a1c", 0.6), "MeatRaw": ("a24438", 0.6), "Bread": ("d6a35f", 0.8), "Pastry": ("c78838", 0.5),
    "Pistachio": ("6d8f3a", 0.7), "Potato": ("c79a5a", 0.8), "Lettuce": ("5f9a35", 0.7), "Tomato": ("c0392b", 0.4),
    "Lemon": ("e8c547", 0.5), "FishSilver": ("98a3a8", 0.25), "Ice": ("e2ecef", 0.15), "Cream": ("efe6d2", 0.6),
    "Soup": ("b8622c", 0.3), "Charcoal": ("1a1a1a", 0.95), "Ember": ("ff7a2a", 0.6), "PaperBag": ("b8976a", 0.85),
    "BottleGreen": ("2f5e3c", 0.1), "Rubber": ("1c1f21", 0.8), "Ceramic": ("f5f3ee", 0.2), "TeaGlass": ("b5462a", 0.1),
})

XMesh, near, prism, blob, loft = H["XMesh"], H["near"], H["prism"], H["blob"], H["loft"]

BAY = 4.0
CEIL = 3.1


# ------------------------------------------------------------------------------ helpers

def cyl(m, x, z, y0, y1, r, mat, n=12, top=True, r1=None):
    """Vertical cylinder (optionally tapered to r1) with a top cap."""
    r1 = r if r1 is None else r1
    rings = [(x, y0, z, r, r), (x, y1, z, r1, r1)]
    if top:
        loft(m, rings, mat, n=n)
    else:
        pts0 = [(x + r * math.cos(math.tau * j / n), y0, z + r * math.sin(math.tau * j / n)) for j in range(n)]
        pts1 = [(x + r1 * math.cos(math.tau * j / n), y1, z + r1 * math.sin(math.tau * j / n)) for j in range(n)]
        for j in range(n):
            k = (j + 1) % n
            a = math.tau * (j + 0.5) / n
            m.face([pts0[j], pts0[k], pts1[k], pts1[j]], mat, (math.cos(a), 0, math.sin(a)))


def hcyl(m, x0, x1, y, z, r, mat, n=10):
    """Horizontal cylinder along x with end caps."""
    pts = [[(x, y + r * math.cos(math.tau * j / n), z + r * math.sin(math.tau * j / n)) for j in range(n)] for x in (x0, x1)]
    for j in range(n):
        k = (j + 1) % n
        a = math.tau * (j + 0.5) / n
        m.face([pts[0][j], pts[0][k], pts[1][k], pts[1][j]], mat, (0, math.cos(a), math.sin(a)))
    m.face(pts[0], mat, (-1, 0, 0))
    m.face(pts[1], mat, (1, 0, 0))


def disc(m, x, y, z, r, mat, n=12, up=1):
    m.face([(x + r * math.cos(math.tau * j / n), y, z + r * math.sin(math.tau * j / n)) for j in range(n)], mat, (0, up, 0))


def bowl(m, x, y, z, r, h, mat, fill=None, n=10):
    """Open bowl / pot: tapered side, optional food surface just below the rim."""
    cyl(m, x, z, y, y + h, r * 0.75, mat, n=n, top=False, r1=r)
    disc(m, x, y + 0.002, z, r * 0.75, mat, n=n, up=-1)
    if fill:
        disc(m, x, y + h * 0.82, z, r * 0.94, fill, n=n)


def chair(m, x, z, yaw=0.0, seat="Oak"):
    """Bistro chair facing +z after `yaw`."""
    m.push(x, 0, z, yaw)
    for sx in (-0.19, 0.19):
        for sz in (-0.19, 0.19):
            m.box((sx, 0.23, sz), (0.035, 0.46, 0.035), "SteelDark", skip=("-y",))
    m.box((0, 0.47, 0), (0.44, 0.04, 0.44), seat)
    if near():
        for sx in (-0.19, 0.19):
            m.box((sx, 0.72, -0.2), (0.035, 0.5, 0.035), "SteelDark", skip=("-y",))
        m.box((0, 0.86, -0.2), (0.42, 0.16, 0.03), seat)
    else:
        m.box((0, 0.72, -0.2), (0.42, 0.5, 0.03), seat)
    m.pop()


def table_top(m, x, z, w, d, h=0.75, top="Oak", round_top=False):
    if round_top:
        cyl(m, x, z, h - 0.035, h, w / 2, top, n=16)
        cyl(m, x, z, 0.0, h - 0.035, 0.035, "SteelDark", n=6, top=False)
        disc(m, x, 0.01, z, 0.24, "SteelDark", n=8)
    else:
        m.box((x, h - 0.0175, z), (w, 0.035, d), top)
        for sx in (-1, 1):
            for sz in (-1, 1):
                m.box((x + sx * (w / 2 - 0.05), (h - 0.035) / 2, z + sz * (d / 2 - 0.05)), (0.045, h - 0.035, 0.045), "SteelDark", skip=("-y",))


def tea_glass(m, x, y, z):
    cyl(m, x, z, y, y + 0.075, 0.022, "TeaGlass", n=6, r1=0.026)
    disc(m, x, y - 0.002, z, 0.04, "Ceramic", n=6)


def place_setting(m, x, z):
    if near():
        disc(m, x, 0.752, z, 0.12, "Ceramic", n=10)


# ------------------------------------------------------------------------------ shell

def rs_floor(m, mat="Terrazzo"):
    """Dining floor for one 4 m bay, z 0 .. -10, top at y 0.06 with a skirting lip."""
    m.box((0, 0.03, -5.0), (BAY, 0.06, 10.0), mat, skip=("-y",))


def rs_floor_kitchen(m):
    m.box((0, 0.03, -13.0), (BAY, 0.06, 6.0), "SubwayTile", skip=("-y",))
    if near():
        m.box((0, 0.065, -13.0), (0.35, 0.01, 0.35), "SteelDark")  # floor drain


def rs_ceiling(m):
    """Ceiling for one bay: plaster soffit at 3.1 m with two recessed light panels and a
    lower bulkhead over the kitchen line."""
    m.face([(-2, CEIL, 0), (2, CEIL, 0), (2, CEIL, -16), (-2, CEIL, -16)], "Plaster", (0, -1, 0))
    for z in (-2.5, -6.5):
        m.box((0, CEIL - 0.012, z), (0.6, 0.02, 0.6), "LampGlow", skip=("+y",))
    m.box((0, CEIL - 0.012, -13.0), (1.2, 0.02, 0.3), "LampGlow", skip=("+y",))


def wall_strip(m, length, wainscot, z0=0.0):
    """Interior wall run along -z from z0 (inner face towards +x): wainscot to 1.1 m, paint
    above, picture rail, skirting."""
    z1 = z0 - length
    m.face([(0, 0.06, z0), (0, 0.06, z1), (0, 1.1, z1), (0, 1.1, z0)], wainscot, (1, 0, 0))
    m.face([(0, 1.1, z0), (0, 1.1, z1), (0, CEIL, z1), (0, CEIL, z0)], "WallPaint", (1, 0, 0))
    m.box((0.02, 1.12, (z0 + z1) / 2), (0.04, 0.05, length), "Oak", skip=("-x",))
    m.box((0.012, 0.11, (z0 + z1) / 2), (0.024, 0.1, length), "Oak", skip=("-x",))


def rs_wall(m, wainscot="Cini"):
    """Side wall for one 4 m stretch of the dining room (inner face +x)."""
    wall_strip(m, BAY, wainscot, z0=0.0)


def rs_wall_kitchen(m):
    """Kitchen side wall: subway tile full height, 6 m deep (z -10 .. -16)."""
    m.face([(0, 0.06, -10), (0, 0.06, -16), (0, CEIL, -16), (0, CEIL, -10)], "SubwayTile", (1, 0, 0))


def rs_back(m):
    """Kitchen back wall for one bay (inner face +z at z = -15.9)."""
    m.face([(-2, 0.06, -15.9), (2, 0.06, -15.9), (2, CEIL, -15.9), (-2, CEIL, -15.9)], "SubwayTile", (0, 0, 1))


def partition(m, openings):
    """Kitchen partition for one bay at z = -10: dining face (+z) painted over a çini
    wainscot, kitchen face subway tile; `openings` are (x0, x1, y0, y1)."""
    for z, face, mat in ((-9.9, 1, "WallPaint"), (-10.1, -1, "SubwayTile")):
        xs = sorted({-2.0, 2.0} | {o[0] for o in openings} | {o[1] for o in openings})
        ys = sorted({0.06, CEIL, 1.1} | {o[2] for o in openings} | {o[3] for o in openings})
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                if any(o[0] < cx < o[1] and o[2] < cy < o[3] for o in openings):
                    continue
                part = mat if (face < 0 or cy > 1.1) else "Cini"
                m.face([(xs[i], ys[j], z), (xs[i + 1], ys[j], z), (xs[i + 1], ys[j + 1], z), (xs[i], ys[j + 1], z)], part, (0, 0, face))
    for x0, x1, y0, y1 in openings:  # reveals
        m.face([(x0, y0, -9.9), (x0, y0, -10.1), (x0, y1, -10.1), (x0, y1, -9.9)], "Oak", (1, 0, 0))
        m.face([(x1, y0, -9.9), (x1, y0, -10.1), (x1, y1, -10.1), (x1, y1, -9.9)], "Oak", (-1, 0, 0))
        m.face([(x0, y1, -9.9), (x1, y1, -9.9), (x1, y1, -10.1), (x0, y1, -10.1)], "Oak", (0, -1, 0))
        if y0 > 0.1:
            m.box(((x0 + x1) / 2, y0 - 0.02, -10.0), (x1 - x0 + 0.1, 0.04, 0.45), "Steel")


def rs_pass(m):
    """Partition with a 2.4 m pass-through window and heat lamps over the steel shelf."""
    partition(m, [(-1.2, 1.2, 1.05, 2.05)])
    if near():
        for x in (-0.6, 0.6):
            m.box((x, 1.96, -10.0), (0.5, 0.06, 0.12), "SteelDark")
            m.box((x, 1.925, -10.0), (0.44, 0.012, 0.08), "LampGlow")
        m.box((0, 2.12, -9.86), (2.6, 0.12, 0.04), "AccentPaint")  # order rail


def rs_door(m):
    """Partition with the staff doorway: double-acting door with porthole, closed."""
    partition(m, [(-0.5, 0.5, 0.06, 2.15)])
    m.box((0, 1.1, -10.0), (0.98, 2.06, 0.05), "SteelDark")
    if near():
        cyl(m, 0, -9.97, 1.45, 1.451, 0.15, "ClearGlass", n=12)
        m.box((0, 2.3, -9.88), (0.5, 0.14, 0.03), "Chalkboard")  # STAFF ONLY plate


def rs_plain(m):
    partition(m, [])


# ------------------------------------------------------------------------------ front of house

def counter(m, length=2.0):
    """Service counter module: slatted accent front, stone top with an overhang to the
    customer side (+z), kick plate, under-counter shelf on the staff side."""
    m.box((0, 0.05, 0), (length, 0.1, 0.62), "Rubber", skip=("-y",))
    m.box((0, 0.55, 0.0), (length, 0.9, 0.62), "AccentPaint", skip=("-y",))
    m.box((0, 1.02, 0.04), (length + 0.04, 0.04, 0.74), "CounterStone")
    if near():
        n = int(length / 0.12)
        for i in range(n):
            m.box((-length / 2 + 0.06 + i * 0.12, 0.56, 0.315), (0.07, 0.86, 0.02), "Oak", skip=("-z",))
        m.box((0, 0.5, -0.33), (length - 0.1, 0.03, 0.05), "Steel")


def rs_counter(m):
    counter(m, 2.0)


def rs_register(m):
    """POS terminal, receipt printer, card reader and tip jar on the counter top (y 1.04)."""
    y = 1.04
    m.box((0, y + 0.03, 0.0), (0.4, 0.06, 0.32), "Rubber")  # cash drawer
    m.box((0, y + 0.08, -0.02), (0.08, 0.1, 0.06), "SteelDark")
    prism(m, (0, y + 0.13, 0.0), (0, y + 0.38, -0.08), 0.36, 0.03, "Rubber")
    m.box((0, y + 0.255, -0.035), (0.33, 0.21, 0.002), "Chalkboard")
    if near():
        m.box((0.32, y + 0.05, 0.05), (0.14, 0.1, 0.16), "Ceramic")  # receipt printer
        m.box((-0.28, y + 0.04, 0.16), (0.08, 0.08, 0.14), "Rubber")  # card reader
        cyl(m, -0.42, 0.18, y, y + 0.14, 0.05, "ClearGlass", n=8, top=False)


def rs_pickup_shelf(m):
    """Courier pickup shelf: steel heated rack, three tiers, kraft bags waiting."""
    for x in (-0.45, 0.45):
        m.box((x, 0.85, 0), (0.04, 1.7, 0.04), "Steel", skip=("-y",))
    for y in (0.45, 0.95, 1.45):
        m.box((0, y, 0), (0.96, 0.03, 0.42), "Steel")
    m.box((0, 1.74, 0), (1.0, 0.08, 0.46), "AccentPaint")  # header panel (label in Godot)
    if near():
        m.box((0, 1.69, 0), (0.86, 0.015, 0.36), "LampGlow")
        for k, (x, y) in enumerate(((-0.25, 0.465), (0.2, 0.465), (-0.15, 0.965), (0.25, 0.965), (0.0, 1.465))):
            h = 0.3 + 0.05 * (k % 2)
            m.box((x, y + h / 2, 0), (0.24, h, 0.16), "PaperBag")
            m.box((x, y + h + 0.01, 0), (0.24, 0.02, 0.17), "PaperBag")


def rs_menu_board(m):
    """Back-lit menu board (2.4 x 0.9 m) with a brass frame; menu text is Label3D in Godot."""
    m.box((0, 0, 0), (2.4, 0.9, 0.05), "Chalkboard")
    for y in (-0.45, 0.45):
        m.box((0, y, 0.0), (2.46, 0.04, 0.07), "Brass")
    for x in (-1.22, 1.22):
        m.box((x, 0, 0.0), (0.04, 0.94, 0.07), "Brass")
    if near():
        for k in range(3):  # food photo tiles along the bottom
            m.box((-0.8 + k * 0.8, -0.3, 0.027), (0.5, 0.18, 0.004), ("MeatRoast", "Bread", "Lettuce")[k])


def rs_table2(m):
    """Round bistro table for two with chairs either side (along x)."""
    table_top(m, 0, 0, 0.7, 0.7, round_top=True)
    chair(m, -0.62, 0, math.pi / 2)
    chair(m, 0.62, 0, -math.pi / 2)
    if near():
        place_setting(m, -0.18, 0)
        tea_glass(m, 0.15, 0.752, 0.1)


def rs_table4(m):
    table_top(m, 0, 0, 1.2, 0.8)
    for sx in (-0.3, 0.3):
        chair(m, sx, 0.62, math.pi)
        chair(m, sx, -0.62, 0.0)
    if near():
        for sx in (-0.3, 0.3):
            for sz in (-0.2, 0.2):
                place_setting(m, sx, sz)
        cyl(m, 0, 0, 0.752, 0.86, 0.035, "ClearGlass", n=6)  # water carafe


def rs_booth(m):
    """Booth: two upholstered benches facing a table, 1.9 m long along z, back to the wall (-x)."""
    for z, face in ((0.8, -1), (-0.8, 1)):
        m.box((0, 0.22, z), (1.1, 0.44, 0.5), "Oak", skip=("-y",))
        m.box((0, 0.5, z), (1.1, 0.12, 0.5), "Upholstery")
        m.box((0, 0.85, z + face * -0.22), (1.1, 0.7, 0.14), "Upholstery")
    table_top(m, 0.05, 0, 1.0, 0.7)
    if near():
        place_setting(m, 0.05, 0.2)
        place_setting(m, 0.05, -0.2)


def rs_bar_ledge(m):
    """4 m window ledge with five stools, facing the glass (+z)."""
    m.box((0, 1.05, 0), (3.8, 0.04, 0.4), "Oak")
    for x in (-1.85, 1.85):
        m.box((x, 0.52, -0.05), (0.04, 1.02, 0.3), "SteelDark", skip=("-y",))
    for i in range(5):
        x = -1.6 + i * 0.8
        cyl(m, x, -0.5, 0.0, 0.72, 0.025, "SteelDark", n=6, top=False)
        cyl(m, x, -0.5, 0.72, 0.77, 0.18, "Upholstery", n=10)
        if near():
            cyl(m, x, -0.5, 0.28, 0.3, 0.15, "SteelDark", n=8)  # footrest ring
            disc(m, x, 0.005, -0.5, 0.2, "SteelDark", n=8)


def rs_condiments(m):
    """Self-service station: cabinet with napkin dispensers, sauce pumps, cutlery and bin."""
    m.box((0, 0.45, 0), (1.0, 0.9, 0.5), "AccentPaint", skip=("-y",))
    m.box((0, 0.92, 0), (1.04, 0.04, 0.54), "CounterStone")
    if near():
        for k, mat in enumerate(("Tomato", "Lemon", "Cream")):
            x = -0.3 + k * 0.2
            cyl(m, x, -0.08, 0.94, 1.1, 0.06, "Steel", n=8)
            cyl(m, x, -0.08, 1.1, 1.18, 0.012, mat, n=6)
        m.box((0.3, 1.02, -0.05), (0.16, 0.16, 0.16), "SteelDark")
        m.box((0, 0.6, 0.252), (0.25, 0.08, 0.005), "Rubber")  # bin slot


def rs_drink_fridge(m):
    """Glass-door drinks fridge: ayran cups, şalgam, colas and water bottles on four shelves."""
    m.box((0, 1.0, 0), (0.7, 2.0, 0.6), "SteelDark", skip=("-y", "+z"))
    m.face([(-0.35, 0, 0.3), (0.35, 0, 0.3), (0.35, 0.18, 0.3), (-0.35, 0.18, 0.3)], "Rubber", (0, 0, 1))
    m.face([(-0.35, 1.85, 0.3), (0.35, 1.85, 0.3), (0.35, 2.0, 0.3), (-0.35, 2.0, 0.3)], "AccentPaint", (0, 0, 1))
    m.face([(-0.31, 0.2, 0.28), (0.31, 0.2, 0.28), (0.31, 1.83, 0.28), (-0.31, 1.83, 0.28)], "ClearGlass", (0, 0, 1))
    m.box((-0.33, 1.0, 0.29), (0.04, 1.65, 0.02), "Steel")
    m.box((0.33, 1.0, 0.29), (0.04, 1.65, 0.02), "Steel")
    m.face([(-0.3, 0.2, -0.26), (0.3, 0.2, -0.26), (0.3, 1.83, -0.26), (-0.3, 1.83, -0.26)], "LampGlow", (0, 0, 1))
    if near():
        for row, y in enumerate((0.25, 0.65, 1.05, 1.45)):
            m.box((0, y - 0.01, 0), (0.62, 0.02, 0.5), "Steel")
            mat = ("Cream", "MeatRaw", "Tomato", "ClearGlass")[row]
            for k in range(5):
                cyl(m, -0.24 + k * 0.12, 0.12, y, y + (0.12 if row == 0 else 0.25), 0.035, mat, n=6)


def rs_ayran_machine(m):
    """Ayran dispenser: two clear churning tanks with white ayran, chrome taps, drip tray."""
    m.box((0, 0.1, 0), (0.6, 0.2, 0.42), "Steel")
    for x in (-0.15, 0.15):
        cyl(m, x, -0.02, 0.2, 0.62, 0.13, "ClearGlass", n=12, top=False)
        cyl(m, x, -0.02, 0.2, 0.52, 0.12, "Cream", n=12)
        cyl(m, x, -0.02, 0.62, 0.67, 0.135, "Steel", n=12)
        if near():
            m.box((x, 0.27, 0.16), (0.03, 0.08, 0.06), "Steel")
    m.box((0, 0.21, 0.17), (0.5, 0.015, 0.1), "SteelDark")


def rs_tea_station(m):
    """Çay ocağı: two-tier samovar kettle on a burner, tray of tulip glasses, sugar bowl."""
    m.box((0, 0.02, 0), (0.6, 0.04, 0.4), "Steel")
    cyl(m, -0.12, 0, 0.04, 0.3, 0.13, "Copper", n=12, r1=0.1)
    cyl(m, -0.12, 0, 0.3, 0.46, 0.08, "Copper", n=12, r1=0.065)
    blob(m, -0.12, 0.48, 0, 0.03, 0.03, 0.03, "Brass", seg=6, rings=3)
    if near():
        prism(m, (-0.02, 0.2, 0.0), (0.06, 0.26, 0.0), 0.03, 0.03, "Copper")  # spout
        for i in range(6):
            tea_glass(m, 0.12 + (i % 3) * 0.07, 0.04, -0.07 + (i // 3) * 0.12)
        bowl(m, 0.25, 0.04, 0.12, 0.05, 0.05, "Ceramic", fill="Ceramic")


def rs_pendant(m):
    """Pendant: cord from the ceiling and a brass dome shade with a glowing diffuser."""
    cyl(m, 0, 0, 2.3, CEIL, 0.006, "Rubber", n=4, top=False)
    cyl(m, 0, 0, 2.15, 2.3, 0.2, "Brass", n=12, top=True, r1=0.06)
    disc(m, 0, 2.152, 0, 0.19, "LampGlow", n=12, up=-1)


def rs_plant(m):
    cyl(m, 0, 0, 0.0, 0.45, 0.22, "Ceramic", n=10, r1=0.26)
    disc(m, 0, 0.42, 0, 0.24, "Soil", n=10)
    cyl(m, 0, 0, 0.42, 1.1, 0.025, "Bark", n=5, top=False)
    blob(m, 0, 1.35, 0, 0.42, 0.45, 0.42, "Foliage", seg=8, rings=5, seed=1.3)
    if near():
        blob(m, 0.18, 1.1, 0.1, 0.25, 0.22, 0.25, "Foliage", seg=7, rings=4, seed=2.1)


# ------------------------------------------------------------------------------ kitchen

def kitchen_base(m, w, top="Steel"):
    """Steel base cabinet / table: 0.9 m high, 0.7 m deep, against the back wall (front +z)."""
    m.box((0, 0.45, 0), (w, 0.86, 0.7), "Steel", skip=("-y",))
    m.box((0, 0.91, 0), (w + 0.02, 0.04, 0.72), top)
    if near():
        m.box((0, 0.06, 0.36), (w - 0.05, 0.1, 0.02), "SteelDark", skip=("-z",))


def rs_range(m):
    """Four-burner range with oven, stock pot and pan on the burners."""
    kitchen_base(m, 1.0, top="SteelDark")
    for x in (-0.25, 0.25):
        for z in (-0.15, 0.15):
            cyl(m, x, z, 0.93, 0.95, 0.11, "Charcoal", n=8)
    m.box((0, 0.5, 0.355), (0.8, 0.45, 0.012), "SteelDark")  # oven door
    if near():
        m.box((0, 0.76, 0.37), (0.6, 0.03, 0.04), "Steel")  # handle
        bowl(m, -0.25, 0.95, -0.15, 0.17, 0.28, "Steel", fill="Soup")
        cyl(m, 0.25, 0.15, 0.95, 1.0, 0.13, "SteelDark", n=10)
        prism(m, (0.38, 0.99, 0.15), (0.6, 1.0, 0.18), 0.03, 0.02, "SteelDark")


def rs_grill(m):
    """Mangal: open charcoal grill 1.2 m long with glowing coals, grate and köfte skewers."""
    kitchen_base(m, 1.2, top="SteelDark")
    m.box((0, 1.0, 0), (1.15, 0.14, 0.6), "SteelDark", skip=("+y",))
    m.face([(-0.55, 0.98, 0.27), (0.55, 0.98, 0.27), (0.55, 0.98, -0.27), (-0.55, 0.98, -0.27)], "Ember", (0, 1, 0))
    if near():
        for k in range(10):
            m.box((-0.5 + k * 0.111, 1.07, 0), (0.008, 0.008, 0.56), "Steel")
        for k in range(6):
            x = -0.45 + k * 0.18
            m.box((x, 1.09, 0.0), (0.012, 0.012, 0.8), "Steel")
            for z in (-0.12, 0.0, 0.12):
                blob(m, x, 1.1, z, 0.03, 0.025, 0.05, "MeatRoast", seg=6, rings=3, seed=k + z)


def rs_fryer(m):
    """Twin-basket fryer with oil wells and hanging baskets."""
    kitchen_base(m, 0.8, top="SteelDark")
    for x in (-0.19, 0.19):
        m.box((x, 0.94, -0.02), (0.32, 0.02, 0.48), "Pastry")
        if near():
            m.box((x, 1.06, 0.1), (0.26, 0.16, 0.24), "SteelDark", skip=("+y",))
            m.box((x, 1.14, 0.3), (0.02, 0.02, 0.2), "Rubber")
    m.box((0, 1.25, -0.33), (0.78, 0.6, 0.04), "Steel")  # splash back


def rs_prep(m):
    """1.6 m prep table: cutting boards, bowls of chopped salad, onions, parsley."""
    kitchen_base(m, 1.6)
    if near():
        m.box((-0.35, 0.945, 0.05), (0.5, 0.03, 0.35), "Oak")
        prism(m, (-0.2, 0.97, 0.12), (-0.02, 0.97, 0.14), 0.04, 0.008, "Steel")  # knife
        for k, fill in enumerate(("Tomato", "Lettuce", "Cream", "Lemon")):
            bowl(m, 0.15 + k * 0.17, 0.93, -0.12, 0.08, 0.07, "Steel", fill=fill)
        m.box((0, 0.3, 0), (1.5, 0.02, 0.6), "Steel")  # undershelf
        for k in range(3):
            m.box((-0.5 + k * 0.45, 0.42, 0.0), (0.35, 0.22, 0.4), "Ceramic")


def rs_sink(m):
    kitchen_base(m, 1.2)
    for x in (-0.28, 0.28):
        m.box((x, 0.85, 0), (0.48, 0.12, 0.45), "SteelDark", skip=("+y",))
    if near():
        cyl(m, 0, -0.3, 0.93, 1.3, 0.015, "Steel", n=6, top=False)
        prism(m, (0, 1.3, -0.3), (0, 1.25, -0.08), 0.03, 0.03, "Steel")
        m.box((0.6, 1.15, -0.25), (0.3, 0.4, 0.15), "Steel")  # dish rack
        for k in range(5):
            cyl(m, 0.48 + k * 0.06, -0.25, 1.0, 1.22, 0.1, "Ceramic", n=8, top=False)


def rs_fridge(m):
    """Reach-in two-door steel fridge."""
    m.box((0, 1.05, 0), (1.2, 2.1, 0.75), "Steel", skip=("-y",))
    if near():
        m.box((0, 1.05, 0.377), (0.01, 1.8, 0.005), "SteelDark")
        for x in (-0.08, 0.08):
            m.box((x, 1.3, 0.4), (0.025, 0.5, 0.04), "SteelDark")
        m.box((0, 2.0, 0.378), (0.4, 0.1, 0.005), "Chalkboard")


def rs_hood(m):
    """3 m canopy extraction hood over the cooking line (hung at 2.1 m, front +z)."""
    prism(m, (-1.5, 2.25, 0.0), (1.5, 2.25, 0.0), 1.05, 0.3, "Steel", up=(0, 1, -0.6))
    m.box((0, 2.75, -0.15), (3.0, 0.7, 0.75), "Steel", skip=("+y",))
    if near():
        for k in range(5):
            m.box((-1.2 + k * 0.6, 2.08, 0.15), (0.5, 0.01, 0.4), "SteelDark")
        m.box((0, 2.08, 0.38), (2.8, 0.015, 0.05), "LampGlow")


def rs_shelf(m):
    """Wall shelving above the line: two steel shelves with pots, jars and spice tins."""
    for y in (1.6, 2.1):
        m.box((0, y, 0), (1.6, 0.03, 0.35), "Steel")
    if near():
        for k in range(4):
            cyl(m, -0.6 + k * 0.4, 0.0, 1.615, 1.615 + 0.18 + 0.05 * (k % 2), 0.13, "Steel" if k % 2 else "Copper", n=10)
        for k in range(8):
            cyl(m, -0.7 + k * 0.2, 0.05, 2.115, 2.27, 0.05, ("Tomato", "Lemon", "Pistachio", "Pastry")[k % 4], n=6)


# ------------------------------------------------------------------------------ signature equipment

def rs_doner(m):
    """Döner grill: vertical gas burner panel, the meat cone on its spit (Godot spins
    rs_doner_cone), drip tray and a carving board."""
    m.box((0, 0.45, -0.2), (0.7, 0.9, 0.5), "Steel", skip=("-y",))
    m.box((0, 1.4, -0.42), (0.62, 1.0, 0.12), "SteelDark")
    m.face([(-0.26, 1.0, -0.355), (0.26, 1.0, -0.355), (0.26, 1.8, -0.355), (-0.26, 1.8, -0.355)], "Ember", (0, 0, 1))
    m.box((0, 0.92, -0.1), (0.5, 0.04, 0.4), "Steel")  # drip tray
    cyl(m, 0, -0.08, 1.9, 2.2, 0.012, "Steel", n=6, top=False)
    m.box((0, 2.2, -0.25), (0.06, 0.06, 0.4), "Steel")
    if near():
        m.box((0.45, 0.93, 0.1), (0.35, 0.03, 0.25), "Oak")
        prism(m, (0.35, 0.96, 0.25), (0.6, 0.96, 0.3), 0.03, 0.006, "Steel")  # long döner knife


def rs_doner_cone(m):
    """Meat cone (spins in Godot about its own y axis): stacked slices, browned outside."""
    rings = []
    for k in range(7):
        y = 0.94 + k * 0.15
        r = 0.13 + 0.07 * math.sin(k / 6 * math.pi * 0.85) + k * 0.012
        rings.append((0, y, 0, r, r))
    loft(m, rings, "MeatRoast", n=12)
    cyl(m, 0, 0, 0.92, 1.95, 0.01, "Steel", n=4, top=True)


def rs_kokorec(m):
    """Kokoreç: horizontal charcoal grill with the long spiral roll (rs_kokorec_roll spins)."""
    m.box((0, 0.45, 0), (1.5, 0.9, 0.5), "Steel", skip=("-y",))
    m.box((0, 0.98, 0), (1.45, 0.16, 0.42), "SteelDark", skip=("+y",))
    m.face([(-0.68, 0.95, 0.18), (0.68, 0.95, 0.18), (0.68, 0.95, -0.18), (-0.68, 0.95, -0.18)], "Ember", (0, 1, 0))
    for x in (-0.74, 0.74):
        m.box((x, 1.2, 0), (0.04, 0.45, 0.06), "Steel")
    if near():
        m.box((0.55, 0.93, 0.33), (0.3, 0.03, 0.2), "Oak")
        for k in range(3):
            cyl(m, -0.5 + k * 0.12, 0.33, 0.93, 1.0, 0.04, "Bread", n=8)


def rs_kokorec_roll(m):
    """Spiral-wrapped kokoreç roll along x, centred on its spin axis at the local origin."""
    hcyl(m, -0.62, 0.62, 0, 0, 0.11, "MeatRoast", n=10)
    if near():
        for k in range(9):
            x = -0.55 + k * 0.137
            hcyl(m, x - 0.03, x + 0.03, 0, 0, 0.118, "Pastry", n=10)
    hcyl(m, -0.76, 0.76, 0, 0, 0.012, "Steel", n=4)


def rs_pide_oven(m):
    """Wood-fired pide oven: tiled dome with a çini front, arched mouth with glowing embers,
    flue, and a long wooden peel resting against it."""
    m.box((0, 0.45, -0.6), (2.0, 0.9, 1.6), "BrickRed", skip=("-y",))
    rings = []
    for k in range(6):
        a = k / 5 * math.pi / 2
        rings.append((0, 0.9 + 0.75 * math.sin(a), -0.6, 0.95 * math.cos(a) + 0.02, 0.75 * math.cos(a) + 0.02))
    loft(m, rings, "Cini", n=14)
    m.box((0, 1.25, 0.18), (1.2, 0.7, 0.08), "Cini")
    m.face([(-0.32, 0.95, 0.225), (0.32, 0.95, 0.225), (0.32, 1.3, 0.225), (-0.32, 1.3, 0.225)], "Ember", (0, 0, 1))
    m.box((0, 0.92, 0.32), (0.8, 0.04, 0.3), "Limestone")
    cyl(m, 0, -0.9, 1.55, 3.1, 0.14, "SteelDark", n=8, top=False)
    if near():
        prism(m, (0.8, 0.05, 0.4), (0.95, 2.3, 0.3), 0.06, 0.02, "Oak")
        m.box((0.8, 0.25, 0.42), (0.32, 0.01, 0.4), "Oak", skip=())


def rs_fish_display(m):
    """Fish counter: angled stainless ice bed with whole sea bream, sea bass and hamsi on
    crushed ice, lemons, and a glass sneeze guard."""
    m.box((0, 0.45, 0), (1.8, 0.9, 0.8), "Steel", skip=("-y",))
    prism(m, (-0.9, 0.98, 0.0), (0.9, 0.98, 0.0), 0.8, 0.16, "Ice", up=(0, 1, -0.25))
    m.face([(-0.88, 1.2, -0.32), (0.88, 1.2, -0.32), (0.88, 1.45, -0.38), (-0.88, 1.45, -0.38)], "ClearGlass", (0, 0.2, 1))
    if near():
        for row in range(3):
            for k in range(6):
                x = -0.72 + k * 0.29 + (0.1 if row % 2 else 0)
                z = 0.25 - row * 0.22
                y = 1.06 + row * 0.055
                blob(m, x, y, z, 0.12 - row * 0.02, 0.03, 0.045, "FishSilver", seg=8, rings=3, seed=k + row)
                prism(m, (x + 0.12, y, z), (x + 0.18, y, z), 0.07, 0.01, "FishSilver")
        for k in range(4):
            blob(m, -0.8 + k * 0.5, 1.1, 0.33, 0.035, 0.03, 0.03, "Lemon", seg=6, rings=3)


def rs_dessert_vitrine(m):
    """Curved glass dessert vitrine: trays of baklava (diamond cut, pistachio), kadayıf
    and şöbiyet on two shelves, lit from above."""
    m.box((0, 0.45, 0), (1.8, 0.9, 0.75), "AccentPaint", skip=("-y",))
    m.box((0, 0.92, 0), (1.82, 0.04, 0.77), "CounterStone")
    m.face([(-0.88, 0.94, 0.36), (0.88, 0.94, 0.36), (0.88, 1.35, 0.2), (-0.88, 1.35, 0.2)], "ClearGlass", (0, 0.4, 1))
    m.face([(-0.88, 1.35, 0.2), (0.88, 1.35, 0.2), (0.88, 1.4, -0.3), (-0.88, 1.4, -0.3)], "ClearGlass", (0, 1, 0.1))
    m.box((0, 1.4, -0.33), (1.8, 0.06, 0.08), "Steel")
    for side in (-1, 1):
        m.face([(side * 0.89, 0.94, 0.36), (side * 0.89, 0.94, -0.33), (side * 0.89, 1.4, -0.33), (side * 0.89, 1.35, 0.2)], "ClearGlass", (side, 0, 0))
    if near():
        m.box((0, 1.38, -0.05), (1.7, 0.01, 0.1), "LampGlow")
        for k in range(4):
            x = -0.64 + k * 0.43
            m.box((x, 0.96, 0.0), (0.38, 0.03, 0.5), "Steel")
            fill = ("Pastry", "Pistachio", "Pastry", "Cream")[k]
            m.box((x, 0.995, 0.0), (0.36, 0.04, 0.48), fill)
            if k in (0, 2):
                for j in range(4):
                    m.box((x, 1.017, -0.18 + j * 0.12), (0.34, 0.004, 0.006), "MeatRoast")  # diamond cut lines
            if k == 1:
                for j in range(6):
                    blob(m, x - 0.12 + (j % 3) * 0.12, 1.025, -0.1 + (j // 3) * 0.2, 0.05, 0.02, 0.05, "Pastry", seg=6, rings=3)


def rs_soup_station(m):
    """Steam table with three soup cauldrons (mercimek, ezogelin, işkembe), ladles, bread."""
    m.box((0, 0.45, 0), (1.8, 0.9, 0.7), "Steel", skip=("-y",))
    m.box((0, 0.92, 0), (1.82, 0.04, 0.72), "SteelDark")
    for k, fill in enumerate(("Soup", "Pastry", "Cream")):
        x = -0.55 + k * 0.55
        bowl(m, x, 0.94, 0.0, 0.24, 0.32, "Copper" if k == 1 else "Steel", fill=fill, n=14)
        if near():
            prism(m, (x + 0.08, 1.1, 0.0), (x + 0.22, 1.5, -0.05), 0.02, 0.02, "Steel")
    if near():
        m.box((0.75, 1.0, 0.25), (0.25, 0.12, 0.18), "Oak")
        for j in range(4):
            m.box((0.75, 1.07 + j * 0.02, 0.25), (0.22, 0.018, 0.14), "Bread")


def rs_bain_marie(m):
    """Esnaf lokantası steam table: eight trays of home-style dishes under a glass guard."""
    m.box((0, 0.45, 0), (2.0, 0.9, 0.75), "Steel", skip=("-y",))
    m.box((0, 0.92, 0), (2.02, 0.04, 0.77), "SteelDark")
    fills = ("Soup", "Pastry", "Lettuce", "Tomato", "Cream", "MeatRoast", "Potato", "Pistachio")
    for k in range(8):
        x = -0.72 + (k % 4) * 0.48
        z = -0.17 + (k // 4) * 0.34
        m.box((x, 0.96, z), (0.44, 0.06, 0.3), "Steel", skip=("+y",))
        m.face([(x - 0.2, 0.975, z - 0.13), (x + 0.2, 0.975, z - 0.13), (x + 0.2, 0.975, z + 0.13), (x - 0.2, 0.975, z + 0.13)], fills[k], (0, 1, 0))
    m.face([(-0.98, 1.2, 0.38), (0.98, 1.2, 0.38), (0.98, 1.45, 0.2), (-0.98, 1.45, 0.2)], "ClearGlass", (0, 0.5, 1))


def rs_cigkofte_station(m):
    """Çiğ köfte counter: wide kneading tray with a mound of spiced bulgur, lettuce crate,
    lavash stack, lemons and pomegranate-molasses bottles."""
    m.box((0, 0.45, 0), (1.8, 0.9, 0.7), "AccentPaint", skip=("-y",))
    m.box((0, 0.92, 0), (1.82, 0.04, 0.72), "CounterStone")
    cyl(m, -0.3, 0.0, 0.94, 0.99, 0.38, "Copper", n=16, top=False)
    disc(m, -0.3, 0.945, 0.0, 0.38, "Copper", n=16)
    blob(m, -0.3, 1.02, 0.0, 0.26, 0.1, 0.22, "MeatRaw", seg=10, rings=4, seed=0.4)
    if near():
        m.box((0.45, 1.02, 0.0), (0.45, 0.16, 0.35), "Oak", skip=("+y",))
        for k in range(6):
            blob(m, 0.3 + (k % 3) * 0.14, 1.08, -0.08 + (k // 3) * 0.16, 0.07, 0.05, 0.08, "Lettuce", seg=6, rings=3, seed=k)
        for j in range(5):
            cyl(m, 0.75, 0.2, 0.94 + j * 0.008, 0.948 + j * 0.008, 0.14, "Bread", n=10)
        for k in range(2):
            cyl(m, 0.8, -0.2 + k * 0.1, 0.94, 1.15, 0.03, "MeatRoast", n=6)


def rs_crepe_griddle(m):
    """Pancake house: two round crêpe griddles, batter jug, spreader and a stack of pancakes."""
    m.box((0, 0.45, 0), (1.6, 0.9, 0.7), "Steel", skip=("-y",))
    for x in (-0.4, 0.4):
        cyl(m, x, 0.0, 0.9, 0.98, 0.22, "SteelDark", n=14)
        cyl(m, x, 0.0, 0.98, 0.99, 0.2, "Charcoal", n=14)
    if near():
        cyl(m, 0.4, 0.0, 0.99, 0.995, 0.17, "Pastry", n=14)
        cyl(m, 0.0, 0.25, 0.9, 1.1, 0.06, "Ceramic", n=8, r1=0.05)
        for j in range(6):
            cyl(m, -0.65, 0.25, 0.9 + j * 0.012, 0.91 + j * 0.012, 0.11, "Pastry", n=10)
        prism(m, (-0.1, 0.92, -0.25), (0.2, 0.92, -0.25), 0.04, 0.01, "Oak")


def rs_kumpir_bar(m):
    """Kumpir: glass-front potato warming oven with baked potatoes, and a toppings bar of
    twelve colourful bins (corn, olives, pickles, sausage, salad, cheese)."""
    m.box((0, 0.45, 0), (1.9, 0.9, 0.75), "Steel", skip=("-y",))
    m.box((-0.55, 1.2, -0.05), (0.75, 0.55, 0.6), "Steel", skip=("+z",))
    m.face([(-0.9, 0.95, 0.25), (-0.2, 0.95, 0.25), (-0.2, 1.45, 0.25), (-0.9, 1.45, 0.25)], "ClearGlass", (0, 0, 1))
    m.face([(-0.88, 1.43, 0.2), (-0.22, 1.43, 0.2), (-0.22, 1.43, -0.3), (-0.88, 1.43, -0.3)], "LampGlow", (0, -1, 0))
    for k in range(6):
        blob(m, -0.78 + (k % 3) * 0.22, 1.02 + (k // 3) * 0.24, 0.0, 0.09, 0.06, 0.07, "Potato", seg=7, rings=4, seed=k)
        if k < 3:
            m.box((-0.55, 1.0 + (k // 3) * 0.24, 0), (0.7, 0.01, 0.5), "Steel")
    fills = ("Lemon", "Charcoal", "Pistachio", "Tomato", "MeatRoast", "Lettuce", "Cream", "Pastry", "Tomato", "Lemon", "Lettuce", "Cream")
    for k in range(12):
        x = 0.05 + (k % 4) * 0.21
        z = -0.25 + (k // 4) * 0.2
        m.box((x, 0.95, z), (0.19, 0.06, 0.18), "Steel", skip=("+y",))
        m.face([(x - 0.085, 0.97, z - 0.08), (x + 0.085, 0.97, z - 0.08), (x + 0.085, 0.97, z + 0.08), (x - 0.085, 0.97, z + 0.08)], fills[k], (0, 1, 0))


def rs_dairy_display(m):
    """Muhallebici: chilled display of sütlaç bowls, kazandibi and tavuk göğsü trays."""
    m.box((0, 0.45, 0), (1.8, 0.9, 0.75), "AccentPaint", skip=("-y",))
    m.box((0, 1.15, -0.05), (1.8, 0.5, 0.65), "Steel", skip=("+z", "-y"))
    m.face([(-0.88, 0.92, 0.28), (0.88, 0.92, 0.28), (0.88, 1.4, 0.28), (-0.88, 1.4, 0.28)], "ClearGlass", (0, 0, 1))
    m.face([(-0.86, 1.38, 0.25), (0.86, 1.38, 0.25), (0.86, 1.38, -0.35), (-0.86, 1.38, -0.35)], "LampGlow", (0, -1, 0))
    for row in range(2):
        for k in range(7):
            x = -0.72 + k * 0.24
            z = 0.05 - row * 0.25
            bowl(m, x, 0.92, z, 0.07, 0.06, "Ceramic", fill="Cream", n=8)
            if near():
                disc(m, x, 0.972, z, 0.05, "Pastry", n=6)
    if near():
        m.box((0, 1.16, -0.05), (1.6, 0.02, 0.5), "Steel")
        for k in range(3):
            m.box((-0.55 + k * 0.55, 1.2, -0.05), (0.45, 0.05, 0.35), ("Pastry", "Cream", "Cream")[k])


def rs_simit_rack(m):
    """Pastry shop: tall wooden rack of simit rings and a display of poğaça and börek."""
    m.box((0, 0.9, -0.15), (0.9, 1.8, 0.06), "Oak")
    for x in (-0.42, 0.42):
        m.box((x, 0.9, 0), (0.05, 1.8, 0.35), "Oak", skip=("-y",))
    for row in range(5):
        y = 0.4 + row * 0.3
        m.box((0, y, 0), (0.84, 0.02, 0.3), "Oak")
        for k in range(4):
            x = -0.3 + k * 0.2
            for side in (-1, 1):
                m.box((x + side * 0.055, y + 0.035, 0.0), (0.03, 0.04, 0.14), "Bread")
                m.box((x, y + 0.032, side * 0.055), (0.14, 0.034, 0.03), "Bread")  # lower than the cross pieces: no shared top plane


def rs_bar(m):
    """Meyhane bar: back bar with rakı and wine bottles on shelves, mirror, meze fridge below."""
    m.box((0, 0.45, 0), (2.4, 0.9, 0.5), "Oak", skip=("-y",))
    m.box((0, 0.92, 0.0), (2.44, 0.04, 0.54), "CounterStone")
    m.face([(-1.15, 1.2, -0.24), (1.15, 1.2, -0.24), (1.15, 2.7, -0.24), (-1.15, 2.7, -0.24)], "ClearGlass", (0, 0, 1))
    for y in (1.3, 1.75, 2.2):
        m.box((0, y, -0.12), (2.3, 0.03, 0.22), "Oak")
        if near():
            for k in range(14):
                x = -1.05 + k * 0.16
                mat = "BottleGreen" if (k + int(y * 10)) % 3 else "ClearGlass"
                cyl(m, x, -0.12, y + 0.015, y + 0.28, 0.035, mat, n=6)
                cyl(m, x, -0.12, y + 0.28, y + 0.36, 0.012, mat, n=4)
    if near():
        for k in range(3):
            m.face([(-1.0 + k * 0.7, 0.15, 0.255), (-0.4 + k * 0.7, 0.15, 0.255), (-0.4 + k * 0.7, 0.8, 0.255), (-1.0 + k * 0.7, 0.8, 0.255)], "ClearGlass", (0, 0, 1))


def rs_barrel(m):
    """Oak barrel used as a standing table (tavern)."""
    rings = [(0, 0.0, 0, 0.3, 0.3), (0, 0.25, 0, 0.36, 0.36), (0, 0.5, 0, 0.38, 0.38), (0, 0.75, 0, 0.36, 0.36), (0, 1.0, 0, 0.3, 0.3)]
    loft(m, rings, "Oak", n=14)
    if near():
        for y in (0.15, 0.85):
            cyl(m, 0, 0, y, y + 0.05, 0.33 if y < 0.5 else 0.33, "SteelDark", n=14, top=False)
        cyl(m, 0, 0, 1.0, 1.04, 0.45, "Oak", n=14)


# ------------------------------------------------------------------------------ exterior

def rs_blade_sign(m):
    """Projecting blade sign on a wrought bracket (text is Label3D): 0.8 x 0.8 m panel."""
    m.box((0, 0, 0.1), (0.05, 0.05, 0.2), "RailBlack")
    prism(m, (0, 0.0, 0.2), (0, 0.0, 1.1), 0.04, 0.04, "RailBlack")
    prism(m, (0, -0.1, 0.2), (0, 0.0, 0.7), 0.025, 0.025, "RailBlack", up=(0, 0.4, 1))
    m.box((0, -0.5, 0.7), (0.06, 0.8, 0.8), "AccentPaint")
    for y in (-0.1, -0.9):
        m.box((0, y, 0.7), (0.08, 0.04, 0.84), "Brass")


def rs_sidewalk_set(m):
    """Sidewalk seating: small table, two chairs and a parasol."""
    table_top(m, 0, 0, 0.65, 0.65, round_top=True)
    chair(m, -0.55, 0, math.pi / 2, seat="AccentPaint")
    chair(m, 0.55, 0, -math.pi / 2, seat="AccentPaint")
    cyl(m, 0, 0, 0.75, 2.3, 0.02, "Oak", n=6, top=False)
    cone = [(0, 2.05, 0, 1.15, 1.15), (0, 2.38, 0, 0.05, 0.05)]
    loft(m, cone, "AccentPaint", n=8)
    m.face([(1.15 * math.cos(math.tau * j / 8), 2.05, 1.15 * math.sin(math.tau * j / 8)) for j in range(8)], "AccentPaint", (0, -1, 0))


def rs_aframe(m):
    """A-frame sidewalk menu board (chalkboard faces both ways)."""
    for z, nz in ((0.18, 1), (-0.18, -1)):
        prism(m, (0, 0.0, z), (0, 1.0, 0.0), 0.6, 0.03, "Oak", up=(0, 0, nz))
    if near():
        for z, nz in ((0.105, 1), (-0.105, -1)):
            m.face([(-0.25, 0.2, z * 1.55), (0.25, 0.2, z * 1.55), (0.25, 0.85, z * 0.25), (-0.25, 0.85, z * 0.25)], "Chalkboard", (0, 0.2, nz))


def rs_planter(m):
    m.box((0, 0.3, 0), (1.2, 0.6, 0.45), "AccentPaint", skip=("-y",))
    m.box((0, 0.58, 0), (1.1, 0.04, 0.38), "Soil")
    for k in range(4):
        blob(m, -0.4 + k * 0.27, 0.72, 0, 0.2, 0.2, 0.18, "Foliage", seg=6, rings=4, seed=k * 1.7)


PIECES = {
    "rs_floor": rs_floor, "rs_floor_wood": lambda m: rs_floor(m, "WoodFloor"), "rs_floor_kitchen": rs_floor_kitchen,
    "rs_ceiling": rs_ceiling, "rs_wall": rs_wall, "rs_wall_wood": lambda m: rs_wall(m, "Oak"), "rs_wall_kitchen": rs_wall_kitchen,
    "rs_back": rs_back, "rs_pass": rs_pass, "rs_door": rs_door, "rs_plain": rs_plain,
    "rs_counter": rs_counter, "rs_register": rs_register, "rs_pickup_shelf": rs_pickup_shelf, "rs_menu_board": rs_menu_board,
    "rs_table2": rs_table2, "rs_table4": rs_table4, "rs_booth": rs_booth, "rs_bar_ledge": rs_bar_ledge,
    "rs_condiments": rs_condiments, "rs_drink_fridge": rs_drink_fridge, "rs_ayran_machine": rs_ayran_machine,
    "rs_tea_station": rs_tea_station, "rs_pendant": rs_pendant, "rs_plant": rs_plant,
    "rs_range": rs_range, "rs_grill": rs_grill, "rs_fryer": rs_fryer, "rs_prep": rs_prep, "rs_sink": rs_sink,
    "rs_fridge": rs_fridge, "rs_hood": rs_hood, "rs_shelf": rs_shelf,
    "rs_doner": rs_doner, "rs_doner_cone": rs_doner_cone, "rs_kokorec": rs_kokorec, "rs_kokorec_roll": rs_kokorec_roll,
    "rs_pide_oven": rs_pide_oven, "rs_fish_display": rs_fish_display, "rs_dessert_vitrine": rs_dessert_vitrine,
    "rs_soup_station": rs_soup_station, "rs_bain_marie": rs_bain_marie, "rs_cigkofte_station": rs_cigkofte_station,
    "rs_crepe_griddle": rs_crepe_griddle, "rs_kumpir_bar": rs_kumpir_bar, "rs_dairy_display": rs_dairy_display,
    "rs_simit_rack": rs_simit_rack, "rs_bar": rs_bar, "rs_barrel": rs_barrel,
    "rs_blade_sign": rs_blade_sign, "rs_sidewalk_set": rs_sidewalk_set, "rs_aframe": rs_aframe, "rs_planter": rs_planter,
}
H["ALL"].clear()
H["ALL"].update(PIECES)
H["HOUSES"].clear()
H["HOUSES"].update({k: PIECES[k] for k in ("rs_counter", "rs_doner", "rs_pide_oven", "rs_fish_display", "rs_dessert_vitrine", "rs_kumpir_bar", "rs_bar", "rs_table4")})

if globals().get("PREVIEW"):
    print(H["preview"](globals().get("NAMES"), spacing=globals().get("SPACING", 3.0)))
elif globals().get("BUILD", True):
    H["build"](globals().get("NAMES"), globals().get("BAKE", True))
