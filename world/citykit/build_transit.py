"""Public transport kit: 12 m low-floor city bus (body, wheel, door leaf as separate pieces
so Godot can turn wheels and open doors), bus shelter and bus-stop pole.

Local frame (Godot): bus faces -Z (forward), +X is the kerb side (right-hand traffic),
origin on the ground at the bus centre. Livery stripes and skirt use AccentPaint so each
line tints its own colour. Shelter: back to -Z, open to the kerb at +Z.

Run headless:  blender --background --factory-startup --python build_transit.py
Output: world/citykit/transit/<name>.glb (+ _far)
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:\GodotProjects\delivery-simulator-2026\world\citykit"
SRC = os.path.join(HERE, "build_restaurants.py")
R = {"__name__": "restaurants_lib", "__file__": SRC, "BUILD": False}
exec(compile(open(SRC).read(), SRC, "exec"), R)
H = R["H"]
H["OUT"] = os.path.join(HERE, "transit")
H["PALETTE"].update({"BusGlass": ("2c3c44", 0.06), "BusBody": ("eef0ee", 0.35), "Tyre": ("1b1d1f", 0.85),
                     "HeadLight": ("f4f1e6", 0.1), "TailLight": ("b0221c", 0.2), "LedPanel": ("101214", 0.4)})
near, prism, cyl, hcyl, disc = H["near"], H["prism"], R["cyl"], R["hcyl"], R["disc"]

L, W, HT = 12.0, 2.55, 3.05   # length, width, roof height
FRONT, BACK = -L / 2, L / 2   # forward is -z
FRONT_DOOR = (-4.6, -3.4)     # z ranges of the door openings on the kerb side
MID_DOOR = (-0.2, 1.0)


def side(m, sx):
    """One side of the body (sx = +1 kerb side with door openings)."""
    x = sx * W / 2
    n = (sx, 0, 0)
    doors = (FRONT_DOOR, MID_DOOR) if sx > 0 else ()
    # Vertical bands: skirt 0.3-1.0 (accent), window band 1.05-2.5 (glass with pillars), cant rail.
    zs = sorted({FRONT + 0.4, BACK - 0.3} | {d for pair in doors for d in pair})
    for i in range(len(zs) - 1):
        z0, z1 = zs[i], zs[i + 1]
        if any(a <= (z0 + z1) / 2 <= b for a, b in doors):
            m.face([(x, 2.55, z0), (x, 2.55, z1), (x, 2.75, z1), (x, 2.75, z0)], "BusBody", n)  # door header
            continue
        m.face([(x, 0.32, z0), (x, 0.32, z1), (x, 0.88, z1), (x, 0.88, z0)], "AccentPaint", n)
        m.face([(x, 0.88, z0), (x, 0.88, z1), (x, 1.22, z1), (x, 1.22, z0)], "BusBody", n)
        m.face([(x, 1.22, z0), (x, 1.22, z1), (x, 2.5, z1), (x, 2.5, z0)], "BusGlass", n)
        m.face([(x, 2.5, z0), (x, 2.5, z1), (x, 2.75, z1), (x, 2.75, z0)], "BusBody", n)
        if near():
            k = int((z1 - z0) / 1.45)
            for j in range(1, k + 1):
                zp = z0 + (z1 - z0) * j / (k + 1)
                m.box((x + sx * 0.012, 1.86, zp), (0.02, 1.28, 0.12), "BusBody")
            m.box((x + sx * 0.015, 1.05, (z0 + z1) / 2), (0.025, 0.06, z1 - z0), "AccentPaint")
    # Upper body to the roof and the rear quarter above the engine.
    m.face([(x, 2.75, FRONT + 0.4), (x, 2.75, BACK - 0.3), (x, HT - 0.1, BACK - 0.3), (x, HT - 0.1, FRONT + 0.4)], "BusBody", n)
    m.face([(x, 0.32, BACK - 0.3), (x, 0.32, BACK), (x, HT - 0.1, BACK), (x, HT - 0.1, BACK - 0.3)], "BusBody", n)
    # Wheel arches: dark recesses at both axles.
    for az in (-3.35, 2.35):
        m.box((x - sx * 0.05, 0.62, az), (0.1, 0.6, 1.15), "Rubber", skip=(("+x",) if sx > 0 else ("-x",)))


def bus_body(m):
    """Low-floor 12 m bus body: sides with a continuous window band, raked windscreen with an
    LED destination panel, rear engine bay, roof air-conditioning pods, lights and mirrors."""
    side(m, 1)
    side(m, -1)
    hw = W / 2
    # Floor pan and roof.
    m.face([(-hw, 0.32, FRONT + 0.4), (hw, 0.32, FRONT + 0.4), (hw, 0.32, BACK), (-hw, 0.32, BACK)], "Rubber", (0, -1, 0))
    m.face([(-hw, 0.36, FRONT + 0.4), (hw, 0.36, FRONT + 0.4), (hw, 0.36, BACK), (-hw, 0.36, BACK)], "Rubber", (0, 1, 0))
    m.face([(-hw + 0.02, 0.36, FRONT + 0.45), (-hw + 0.02, 0.36, BACK - 0.05), (-hw + 0.02, 2.75, BACK - 0.05), (-hw + 0.02, 2.75, FRONT + 0.45)], "BusGlass", (1, 0, 0))
    m.face([(-hw, HT - 0.1, FRONT + 0.4), (hw, HT - 0.1, FRONT + 0.4), (hw, HT - 0.1, BACK), (-hw, HT - 0.1, BACK)], "BusBody", (0, 1, 0))
    # Front: bumper, skirt, raked windscreen, destination panel, front cap.
    m.box((0, 0.5, FRONT + 0.2), (W, 0.36, 0.4), "AccentPaint")
    prism(m, (0, 0.68, FRONT + 0.38), (0, 0.98, FRONT + 0.32), W, 0.08, "BusBody", up=(0, 0, -1))
    m.face([(-hw, 0.95, FRONT + 0.3), (hw, 0.95, FRONT + 0.3), (hw, 2.45, FRONT + 0.4), (-hw, 2.45, FRONT + 0.4)], "BusGlass", (0, 0.05, -1))
    m.face([(-hw, 2.45, FRONT + 0.4), (hw, 2.45, FRONT + 0.4), (hw, HT - 0.1, FRONT + 0.4), (-hw, HT - 0.1, FRONT + 0.4)], "BusBody", (0, 0, -1))
    m.face([(-hw + 0.25, 2.5, FRONT + 0.39), (hw - 0.25, 2.5, FRONT + 0.39), (hw - 0.25, 2.88, FRONT + 0.39), (-hw + 0.25, 2.88, FRONT + 0.39)], "LedPanel", (0, 0, -1))
    m.face([(-hw, 0.32, FRONT + 0.3), (hw, 0.32, FRONT + 0.3), (hw, 0.95, FRONT + 0.3), (-hw, 0.95, FRONT + 0.3)], "BusBody", (0, 0, -1))
    for sx in (-1, 1):
        m.box((sx * 0.95, 0.72, FRONT + 0.285), (0.32, 0.12, 0.03), "HeadLight")
        if near():
            prism(m, (sx * hw, 2.3, FRONT + 0.6), (sx * (hw + 0.35), 2.25, FRONT + 0.2), 0.04, 0.04, "RailBlack")
            m.box((sx * (hw + 0.36), 1.95, FRONT + 0.2), (0.06, 0.4, 0.2), "RailBlack")  # mirror
    # Rear: engine grille, tail lights, rear window.
    m.face([(-hw, 0.32, BACK), (hw, 0.32, BACK), (hw, 1.25, BACK), (-hw, 1.25, BACK)], "AccentPaint", (0, 0, 1))
    m.face([(-hw, 1.25, BACK), (hw, 1.25, BACK), (hw, 1.6, BACK), (-hw, 1.6, BACK)], "BusBody", (0, 0, 1))
    m.face([(-hw, 1.6, BACK), (hw, 1.6, BACK), (hw, 2.45, BACK), (-hw, 2.45, BACK)], "BusGlass", (0, 0, 1))
    m.face([(-hw, 2.45, BACK), (hw, 2.45, BACK), (hw, HT - 0.1, BACK), (-hw, HT - 0.1, BACK)], "BusBody", (0, 0, 1))
    for sx in (-1, 1):
        m.box((sx * 1.1, 1.1, BACK + 0.015), (0.18, 0.5, 0.03), "TailLight")
    if near():
        for k in range(6):
            m.box((0, 0.5 + k * 0.11, BACK + 0.012), (1.6, 0.03, 0.02), "RailBlack")
        m.face([(-0.5, 2.0, BACK + 0.01), (0.5, 2.0, BACK + 0.01), (0.5, 2.3, BACK + 0.01), (-0.5, 2.3, BACK + 0.01)], "LedPanel", (0, 0, 1))
    # Roof pods: air conditioning and the CNG tank fairing.
    m.box((0, HT + 0.08, -1.6), (1.9, 0.36, 2.6), "BusBody", skip=("-y",))
    m.box((0, HT + 0.05, 3.2), (1.7, 0.3, 2.2), "BusBody", skip=("-y",))
    if near():
        for k in range(3):
            m.box((0, HT + 0.27, -2.4 + k * 0.8), (1.5, 0.02, 0.5), "RailBlack")
    # Interior suggestion behind the glass: seat backs and stanchions (dark, low-detail).
    if near():
        for k in range(8):
            z = -2.6 + k * 1.0
            if MID_DOOR[0] - 0.4 < z < MID_DOOR[1] + 0.2:
                continue
            for sx in (-1, 1):
                m.box((sx * 0.75, 1.15, z), (0.85, 0.55, 0.1), "AccentPaint")
        for z in (-3.0, 0.4, 2.8):
            cyl(m, 0.4, z, 0.32, 2.95, 0.02, "Steel", n=6, top=False)


def bus_wheel(m):
    """Wheel and tyre about the local origin, axle along x (Godot spins it about x)."""
    hcyl(m, -0.15, 0.15, 0.0, 0.0, 0.5, "Tyre", n=16)
    if near():
        hcyl(m, 0.151, 0.16, 0.0, 0.0, 0.3, "Steel", n=12)
        hcyl(m, 0.16, 0.2, 0.0, 0.0, 0.1, "SteelDark", n=8)


def bus_door(m):
    """One glazed door leaf, 0.6 x 2.2 m, hinge edge at x = 0, leaf along +z (plug door)."""
    m.box((0, 1.42, 0.3), (0.05, 2.2, 0.6), "BusGlass")
    m.box((0.02, 1.42, 0.02), (0.06, 2.2, 0.06), "RailBlack")
    m.box((0.02, 1.42, 0.58), (0.06, 2.2, 0.06), "RailBlack")
    m.box((0.02, 0.36, 0.3), (0.06, 0.08, 0.6), "RailBlack")
    m.box((0.02, 2.48, 0.3), (0.06, 0.08, 0.6), "RailBlack")


def bus_shelter(m):
    """Bus shelter, 3.6 m long: steel frame, glass back and end panels, cantilevered roof with
    a light strip, perch bench, illuminated advertising panel and a route map."""
    for x in (-1.75, 1.75):
        m.box((x, 1.25, -0.6), (0.08, 2.5, 0.08), "SteelDark", skip=("-y",))
    m.box((0, 2.55, -0.05), (3.8, 0.1, 1.5), "SteelDark")
    m.box((0, 2.49, -0.05), (3.4, 0.02, 1.2), "LampGlow", skip=("+y",))
    m.face([(-1.7, 0.15, -0.62), (1.7, 0.15, -0.62), (1.7, 2.45, -0.62), (-1.7, 2.45, -0.62)], "ClearGlass", (0, 0, 1))
    m.box((0, 0.12, -0.6), (3.5, 0.05, 0.06), "SteelDark")
    m.box((0, 2.45, -0.6), (3.5, 0.05, 0.06), "SteelDark")
    # End panel with the illuminated advert (both faces lit) and a glass end on the other side.
    m.box((-1.75, 1.3, -0.05), (0.12, 2.0, 1.1), "SteelDark")
    for sx in (-1, 1):
        m.face([(-1.75 + sx * 0.062, 0.45, -0.5), (-1.75 + sx * 0.062, 0.45, 0.4), (-1.75 + sx * 0.062, 2.15, 0.4), (-1.75 + sx * 0.062, 2.15, -0.5)], "LampGlow", (sx, 0, 0))
    m.face([(1.75, 0.15, -0.55), (1.75, 0.15, 0.2), (1.75, 2.45, 0.2), (1.75, 2.45, -0.55)], "ClearGlass", (1, 0, 0))
    # Perch bench with oak slats.
    for x in (-1.2, 1.2):
        m.box((x, 0.25, -0.38), (0.05, 0.5, 0.05), "SteelDark", skip=("-y",))
    for k in range(3):
        m.box((0, 0.5, -0.5 + k * 0.12), (2.6, 0.04, 0.1), "Oak")
    if near():
        m.face([(0.4, 1.2, -0.57), (1.5, 1.2, -0.57), (1.5, 1.9, -0.57), (0.4, 1.9, -0.57)], "TrimPaint", (0, 0, 1))  # route map
        for k in range(5):
            m.box((0.95, 1.3 + k * 0.12, -0.565), (0.9, 0.012, 0.005), "AccentPaint")


def bus_stop_pole(m):
    """Bus-stop flag: pole, double-sided route flag (accent tinted), timetable case, bin."""
    cyl(m, 0, 0, 0.0, 2.9, 0.04, "SteelDark", n=8)
    m.box((0, 2.55, 0.0), (0.06, 0.6, 0.6), "AccentPaint")
    disc(m, 0.031, 2.65, 0.0, 0.17, "TrimPaint", n=14, up=1)  # placeholder disc, faced below
    m.box((0, 2.65, 0.0), (0.07, 0.3, 0.3), "TrimPaint")
    m.box((0, 1.5, 0.12), (0.05, 0.6, 0.4), "SteelDark")
    if near():
        m.box((0.03, 1.5, 0.12), (0.01, 0.52, 0.34), "TrimPaint")
        cyl(m, 0.0, -0.35, 0.3, 0.95, 0.17, "SteelDark", n=10, top=False)
        cyl(m, 0.0, -0.35, 0.0, 0.3, 0.03, "SteelDark", n=6, top=False)


PIECES = {"bus_body": bus_body, "bus_wheel": bus_wheel, "bus_door": bus_door,
          "bus_shelter": bus_shelter, "bus_stop_pole": bus_stop_pole}
H["ALL"].clear()
H["ALL"].update(PIECES)
H["HOUSES"].clear()
H["HOUSES"].update(PIECES)

if globals().get("PREVIEW"):
    print(H["preview"](globals().get("NAMES"), spacing=globals().get("SPACING", 14.0)))
elif globals().get("BUILD", True):
    H["build"](globals().get("NAMES"), globals().get("BAKE", True))
