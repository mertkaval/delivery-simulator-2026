"""Uniform decals for the NPCs (RGBA PNGs for garments.Decal), rendered with PIL outside Blender:
    python tools/npc/decals.py      ->  source_assets/npc/_decals/*.png
Text panels (POLICE, PARAMEDIC, SECURITY ...), round shoulder patches, a gold badge, the star of
life, company logos. Transparent backgrounds; letters are anti-aliased."""
import os, math
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "source_assets", "npc", "_decals")
FONTS = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/bahnschrift.ttf"]


def font(size, path=None):
    for f in ([path] if path else []) + FONTS:
        if f and os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def text_panel(name, text, w, h, fg, bg=None, size=None, outline=None, bold_font=None):
    im = Image.new("RGBA", (w, h), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = size or int(h * 0.7)
    f = font(size, bold_font)
    while d.textlength(text, font=f) > w * 0.94 and size > 8:
        size -= 2
        f = font(size, bold_font)
    tw = d.textlength(text, font=f)
    box = d.textbbox((0, 0), text, font=f)
    th = box[3] - box[1]
    d.text(((w - tw) / 2, (h - th) / 2 - box[1]), text, font=f, fill=fg, stroke_width=2 if outline else 0, stroke_fill=outline)
    im.save(os.path.join(OUT, name + ".png"))


def round_patch(name, ring_text, centre_text, ring, fill, ink, size=512):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, size - 4, size - 4), fill=ring)
    d.ellipse((size * 0.17, size * 0.17, size * 0.83, size * 0.83), fill=fill)
    f = font(int(size * 0.2))
    tw = d.textlength(centre_text, font=f)
    d.text(((size - tw) / 2, size * 0.39), centre_text, font=f, fill=ink)
    fr = font(int(size * 0.085))
    # ring text along the top arc
    n = len(ring_text)
    for i, ch in enumerate(ring_text):
        a = math.pi * (1.15 - 1.3 * i / max(n - 1, 1))
        x = size / 2 + math.cos(a) * size * 0.415
        y = size / 2 - math.sin(a) * size * 0.415
        ci = Image.new("RGBA", (int(size * 0.1), int(size * 0.1)), (0, 0, 0, 0))
        ImageDraw.Draw(ci).text((int(size * 0.02), 0), ch, font=fr, fill=fill)
        ci = ci.rotate(math.degrees(a) - 90, resample=Image.BICUBIC, expand=True)
        im.alpha_composite(ci, (int(x - ci.width / 2), int(y - ci.height / 2)))
    im.save(os.path.join(OUT, name + ".png"))


def badge(name, size=256):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(size * 0.5, size * 0.04), (size * 0.92, size * 0.2), (size * 0.84, size * 0.66), (size * 0.5, size * 0.96),
           (size * 0.16, size * 0.66), (size * 0.08, size * 0.2)]
    d.polygon(pts, fill=(212, 170, 70, 255), outline=(150, 110, 40, 255))
    d.ellipse((size * 0.3, size * 0.3, size * 0.7, size * 0.7), fill=(235, 200, 110, 255), outline=(150, 110, 40, 255), width=4)
    im.save(os.path.join(OUT, name + ".png"))


def star_of_life(name, size=512):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    for k in range(3):
        a = math.radians(90 + 60 * k)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy, dx
        w, l = size * 0.13, size * 0.45
        pts = [(c + dx * l + px * w, c - dy * l - py * w), (c + dx * l - px * w, c - dy * l + py * w),
               (c - dx * l - px * w, c + dy * l + py * w), (c - dx * l + px * w, c + dy * l - py * w)]
        d.polygon(pts, fill=(30, 90, 200, 255), outline=(255, 255, 255, 255))
    d.line((c, c - size * 0.3, c, c + size * 0.3), fill=(255, 255, 255, 255), width=int(size * 0.04))
    im.save(os.path.join(OUT, name + ".png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    text_panel("police_back", "POLICE", 1024, 256, (240, 240, 240, 255))
    text_panel("police_chest", "POLICE", 512, 128, (220, 220, 220, 255))
    round_patch("police_patch", "VANCOUVER POLICE", "VPD", (24, 30, 60, 255), (210, 180, 90, 255), (24, 30, 60, 255))
    badge("police_badge")
    text_panel("paramedic_back", "PARAMEDIC", 1024, 256, (240, 240, 240, 255))
    star_of_life("star_of_life")
    text_panel("security_back", "SECURITY", 1024, 256, (235, 235, 235, 255))
    round_patch("security_patch", "CITY SECURITY", "SEC", (40, 44, 52, 255), (230, 230, 230, 255), (40, 44, 52, 255))
    text_panel("transit_chest", "TRANSIT", 512, 128, (230, 230, 235, 255), bg=(26, 50, 110, 255))
    text_panel("courier_logo", "CourierNow", 768, 192, (255, 255, 255, 255))
    text_panel("express_logo", "CITY EXPRESS", 768, 192, (250, 205, 40, 255))
    text_panel("pizza_logo", "PIZZA", 512, 160, (245, 230, 210, 255))
    text_panel("cafe_logo", "CAFE", 512, 160, (240, 232, 214, 255))
    text_panel("bakery_logo", "BAKERY", 512, 160, (240, 232, 214, 255))
    text_panel("market_logo", "FRESH MARKET", 768, 192, (245, 245, 240, 255))
    text_panel("crew_back", "CITY WORKS", 1024, 256, (40, 40, 40, 255))
    text_panel("staff_tag", "STAFF", 256, 96, (30, 30, 30, 255), bg=(240, 240, 240, 255))
    print("decals in", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
