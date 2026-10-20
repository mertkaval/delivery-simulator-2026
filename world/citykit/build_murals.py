"""Street-art murals honouring heroes of the Turkish War of Independence.

Each mural is a flat 2D composition rendered with an orthographic camera: painted sky
gradient with brush noise, sunburst rays, crescent and star, a bold two-tone silhouette
of the figure (outlined in cream), and the name in large lettering with a dedication.
Output: world/citykit/murals/mural_<n>.png (1024 x 640), applied in Godot on terrace
end walls facing the pocket parks (StreetSignage).

Run headless:  blender --background --factory-startup --python build_murals.py
"""
import bpy, math, os, random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "murals")
W, H = 16.0, 10.0

# name, dedication, figure kind, palette (sky top, sky bottom, rays, figure, accent)
MURALS = [
    ("KARA FATMA", "Fatma Seher Erden · 1888–1955", "rifle_scarf", ("7a1520", "e0703a", "f2b04a", "1d1a24", "f3e6c8")),
    ("TAYYAR RAHMİYE", "Hero of the Aegean front · 1919", "rider_scarf", ("1c3a5c", "d9893b", "f4c46a", "161a22", "f3e6c8")),
    ("NEZAHAT ONBAŞI", "The youngest corporal · 1907–1993", "rifle_cap", ("2d5a3d", "e2b453", "f6dc8a", "18201c", "f6efdc")),
    ("HALİME ÇAVUŞ", "Ammunition carrier · Kastamonu", "crate_scarf", ("4a2148", "e07a4a", "f3b562", "1b1622", "f3e6c8")),
    ("SÜTÇÜ İMAM", "The first shot at Maraş · 1919", "rifle_kalpak", ("8e1b1b", "f0a046", "f8d27a", "1e1815", "fbf2dc")),
    ("HASAN TAHSİN", "The first bullet at İzmir · 1919", "pistol_kalpak", ("173b57", "cf5a3c", "f1a85a", "141821", "f6ecd6")),
]


def rgb(h, a=1.0):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (a,)


def emission(name, colour):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgb(colour)
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def poly(name, pts, mat, z):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x, y, z) for x, y in pts], [], [list(range(len(pts)))])
    ob = bpy.data.objects.new(name, mesh)
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def disc(name, cx, cy, r, mat, z, n=48, sy=1.0):
    return poly(name, [(cx + r * math.cos(math.tau * i / n), cy + r * sy * math.sin(math.tau * i / n)) for i in range(n)], mat, z)


def quad(name, a, b, w, mat, z):
    """Thick line segment (limbs, rifles)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / ln * w / 2, dx / ln * w / 2
    return poly(name, [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)], mat, z)


def star(name, cx, cy, r, mat, z, rot=0.0):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.4
        a = rot + math.pi / 2 + math.tau * i / 10
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(name, pts, mat, z)


def figure(kind, x0, mat, z, grow=0.0):
    """Heroic figure silhouette, feet at y=-5, about 8 units tall; `grow` widens it for the outline."""
    g = grow
    parts = []
    # Long coat / dress, legs and boots.
    parts.append(poly("coat", [(x0 - 1.15 - g, -4.2 - g), (x0 + 1.15 + g, -4.2 - g), (x0 + 0.85 + g, 0.6 + g), (x0 - 0.85 - g, 0.6 + g)], mat, z))
    for s in (-1, 1):
        parts.append(quad("leg", (x0 + s * 0.4, -4.3), (x0 + s * 0.45, -5.0), 0.42 + 2 * g, mat, z))
    parts.append(poly("shoulders", [(x0 - 1.25 - g, 0.2 - g), (x0 + 1.25 + g, 0.2 - g), (x0 + 0.95 + g, 1.0 + g), (x0 - 0.95 - g, 1.0 + g)], mat, z))
    parts.append(quad("neck", (x0, 0.9), (x0, 1.35), 0.42 + 2 * g, mat, z))
    parts.append(disc("head", x0 + 0.05, 1.85, 0.55 + g, mat, z, sy=1.12))
    if kind.endswith("kalpak"):
        parts.append(poly("kalpak", [(x0 - 0.55 - g, 2.2 - g), (x0 + 0.6 + g, 2.2 - g), (x0 + 0.65 + g, 3.0 + g), (x0 - 0.5 - g, 3.0 + g)], mat, z))
    elif kind.endswith("cap"):
        parts.append(poly("cap", [(x0 - 0.6 - g, 2.15 - g), (x0 + 0.95 + g, 2.15 - g), (x0 + 0.55 + g, 2.6 + g), (x0 - 0.5 - g, 2.65 + g)], mat, z))
    else:  # headscarf flowing back in the wind
        parts.append(disc("scarf", x0 - 0.05, 1.95, 0.68 + g, mat, z, sy=1.08))
        parts.append(poly("scarf_tail", [(x0 - 0.4, 2.3 + g), (x0 - 1.9 - g, 1.5), (x0 - 2.1 - g, 1.05 - g), (x0 - 0.5, 1.3 - g)], mat, z))
    # Arms and the carried object.
    if kind.startswith("rifle") or kind.startswith("rider"):
        parts.append(quad("arm_r", (x0 + 1.0, 0.8), (x0 + 1.5, -0.6), 0.45 + 2 * g, mat, z))
        parts.append(quad("arm_l", (x0 - 1.0, 0.8), (x0 - 1.13, 2.4), 0.42 + 2 * g, mat, z))
        parts.append(quad("rifle", (x0 + 1.6, -1.2), (x0 - 0.3, 4.2), 0.2 + 2 * g, mat, z))
        parts.append(quad("bayonet", (x0 - 0.3, 4.2), (x0 - 0.5, 4.9), 0.08 + 2 * g, mat, z))
    elif kind.startswith("crate"):
        for s in (-1, 1):
            parts.append(quad("arm", (x0 + s * 1.0, 0.8), (x0 + s * 0.9, 3.2), 0.42 + 2 * g, mat, z))
        parts.append(poly("crate", [(x0 - 1.3 - g, 3.0 - g), (x0 + 1.3 + g, 3.0 - g), (x0 + 1.3 + g, 4.3 + g), (x0 - 1.3 - g, 4.3 + g)], mat, z))
    else:  # pistol raised
        parts.append(quad("arm_r", (x0 + 1.0, 0.8), (x0 + 2.4, 2.4), 0.42 + 2 * g, mat, z))
        parts.append(quad("pistol", (x0 + 2.3, 2.3), (x0 + 2.85, 2.95), 0.22 + 2 * g, mat, z))
        parts.append(quad("arm_l", (x0 - 1.0, 0.8), (x0 - 1.13, 2.4), 0.42 + 2 * g, mat, z))
    return parts


def background(top, bottom, seed):
    """Painted sky: vertical gradient with brush-stroke noise, emission only."""
    m = bpy.data.materials.new("sky")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.5
    noise.inputs["Detail"].default_value = 6.0
    noise.noise_dimensions = "4D"
    next(s for s in noise.inputs if s.name == "W").default_value = seed
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 6.0, 1.0)  # horizontal brush strokes
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.18
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = rgb(bottom)
    ramp.color_ramp.elements[1].color = rgb(top)
    nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs[0], noise.inputs["Vector"])
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(noise.outputs["Fac"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[2])
    nt.links.new(add.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    plane = poly("sky", [(-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)], m, 0.0)
    plane.data.uv_layers.new()
    return plane


def text(body, size, x, y, mat, z, align="CENTER"):
    curve = bpy.data.curves.new("txt", "FONT")
    curve.body = body
    curve.size = size
    curve.align_x = align
    curve.align_y = "CENTER"
    for f in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"):
        if os.path.exists(f):
            curve.font = bpy.data.fonts.load(f, check_existing=True)
            break
    ob = bpy.data.objects.new("txt", curve)
    ob.location = (x, y, z)
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def hills(y0, amp, freq, phase, mat, z):
    pts = [(-W / 2 - 0.1, -H / 2)]
    for k in range(65):
        x = -W / 2 + W * k / 64
        y = y0 + amp * math.sin(x * freq + phase) + amp * 0.35 * math.sin(x * freq * 2.7 + phase * 1.9)
        pts.append((x, y))
    pts.append((W / 2 + 0.1, -H / 2))
    return poly("hill", pts, mat, z)


def flag(pole_x, top_y, d, s, z):
    """Waving Turkish flag flying in direction d from a pole at pole_x (all in mural units)."""
    red = emission("flag", "c8102e")
    white = emission("flagwhite", "f7f2ea")
    length, height = 3.3 * s, 2.2 * s
    top, bottom = [], []
    for k in range(17):
        u = k / 16
        wave = 0.22 * s * math.sin(u * 7.0) * u
        top.append((pole_x + d * length * u, top_y + wave))
        bottom.append((pole_x + d * length * u, top_y - height + wave * 1.2 - 0.1 * s * u))
    poly("flag", top + list(reversed(bottom)), red, z)
    cx, cy = pole_x + d * length * 0.36, top_y - height * 0.5 + 0.22 * s * math.sin(0.36 * 7) * 0.36
    disc("cres", cx, cy, height * 0.25, white, z + 0.001)
    disc("cres_cut", cx + d * height * 0.0625, cy, height * 0.2, red, z + 0.002)
    star("fstar", cx + d * height * 0.29, cy, height * 0.12, white, z + 0.003, rot=(-math.pi / 2 if d > 0 else math.pi / 2))
    quad("pole", (pole_x, top_y + 0.15 * s), (pole_x, top_y - 6.0 * s), 0.09 * s, emission("pole", "3a2c22"), z - 0.001)


def ornament_band(y, mat, z, h=0.34):
    """Çini-style border: a row of diamonds with small tulip buds between them."""
    poly("band", [(-W / 2, y - h), (W / 2, y - h), (W / 2, y + h), (-W / 2, y + h)], mat[0], z)
    n = 26
    for k in range(n):
        x = -W / 2 + W * (k + 0.5) / n
        poly("dia", [(x - 0.2, y), (x, y + 0.22), (x + 0.2, y), (x, y - 0.22)], mat[1], z + 0.001)
        bx = x + W / n / 2
        poly("tulip", [(bx - 0.08, y - 0.12), (bx + 0.08, y - 0.12), (bx + 0.12, y + 0.06), (bx + 0.04, y + 0.02),
                       (bx, y + 0.16), (bx - 0.04, y + 0.02), (bx - 0.12, y + 0.06)], mat[2], z + 0.001)


def render_mural(i, spec):
    name, dedication, kind, (top, bottom, rays, fig, accent) = spec
    for ob in list(bpy.context.scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    random.seed(i * 31 + 7)
    background(top, bottom, i * 1.7)
    accent_mat = emission("accent", accent)
    fig_mat = emission("figure", fig)
    d = -1 if i % 2 == 0 else 1          # flag flies towards the outer edge
    fig_x = 4.4 * d
    # Layered hills: hazy far ridge to the dark near crest the figure stands on.
    hills(-0.6, 0.55, 0.45, i * 1.3, emission("hill_far", rays), 0.01)
    hills(-1.8, 0.45, 0.6, i * 2.1 + 1.0, emission("hill_mid", bottom), 0.02)
    near_mat = emission("hill_near", fig)
    hills(-3.2, 0.35, 0.35, i * 0.7 + 2.0, near_mat, 0.03)
    # Birds over the hills.
    bird_mat = emission("bird", fig)
    for k in range(5):
        bx, by = random.uniform(-6, 6), random.uniform(2.2, 3.8)
        quad("wing", (bx - 0.25, by + 0.08), (bx, by), 0.05, bird_mat, 0.02)
        quad("wing", (bx, by), (bx + 0.25, by + 0.1), 0.05, bird_mat, 0.02)
    # Figure on the crest with the flag: cream outline behind a dark silhouette.
    s = 0.55
    foot = (fig_x, -3.2 + 0.35 * math.sin(fig_x * 0.35 + i * 0.7 + 2.0) - 0.05)
    for grow, mat, z in ((0.1, accent_mat, 0.06), (0.0, fig_mat, 0.07)):
        for ob in figure(kind, 0.0, mat, z, grow=grow):
            ob.scale = (s * -d, s, 1.0)   # mirrored so the free arm holds the flag pole
            ob.location = (foot[0], foot[1] + 5.0 * s, 0.0)
    pole_x = foot[0] + d * 0.62 * s
    flag(pole_x, foot[1] + 11.6 * s, d, 1.0, 0.08)
    # Lettering panel on the opposite side, framed in the accent colour.
    tx = -3.0 * d
    poly("panel_edge", [(tx - 4.15, -1.95), (tx + 4.15, -1.95), (tx + 4.15, 1.85), (tx - 4.15, 1.85)], accent_mat, 0.09)
    poly("panel", [(tx - 4.0, -1.8), (tx + 4.0, -1.8), (tx + 4.0, 1.7), (tx - 4.0, 1.7)], fig_mat, 0.095)
    text(name, 1.05 if len(name) < 12 else 0.85, tx, 0.65, accent_mat, 0.1)
    text(dedication, 0.4, tx, -0.45, emission("ded", rays), 0.1)
    text("KUVA-YI MİLLİYE · 1919–1922", 0.3, tx, -1.2, accent_mat, 0.1)
    ornament_band(H / 2 - 0.34, (fig_mat, accent_mat, emission("tulip", "c8102e")), 0.12)
    ornament_band(-H / 2 + 0.34, (fig_mat, accent_mat, emission("tulip2", "c8102e")), 0.12)
    # Orthographic camera looking down -Z at the composition.
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = W
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = (0, 0, 10)
    bpy.context.scene.collection.objects.link(cam)
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 640
    scene.render.filepath = os.path.join(OUT, "mural_%d.png" % i)
    bpy.ops.render.render(write_still=True)
    print("MURAL", i, name, scene.render.filepath)


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except TypeError:
            scene.render.engine = "CYCLES"
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 8
    else:
        scene.eevee.taa_render_samples = 16
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("w") if scene.world is None else scene.world
    scene.world = world
    for i, spec in enumerate(MURALS):
        render_mural(i, spec)


main()
