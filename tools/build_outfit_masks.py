"""Outfit masks for the converted townspeople, so crowds can be recoloured per person.

blender --background --factory-startup --python tools/build_outfit_masks.py

The four scanned characters (business_man_eric, sophia, casual_female, casual_male_2) carry one
texture atlas for skin, hair, face and clothes. For each one this writes
assets/sketchup/people/<id>_outfit_mask.png (same UV layout as the atlas):

  R = upper-body clothing (shirt, jacket, sleeves)   G = lower-body clothing (trousers, skirt)

A texel is clothing when (1) the faces that cover it lie, in the shared rest pose, between the
ankles and the neck and inside the wrists (faces, hair, hands and shoes keep their colours) and
(2) its colour is not skin-like (YCbCr skin test), so bare forearms, necklines and knees stay
skin. Godot's outfit shader (world/living_city/outfit.gdshader) shifts hue / saturation /
value only where the mask is set. casual_male_tshirt has separate outfit materials and needs
no mask.
"""
import bpy
import os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "assets", "sketchup", "people")
IDS = ["business_man_eric", "sophia", "casual_female", "casual_male_2"]
SIZE = 1024

# (bone sets kept for reference)
UPPER = {"Spine", "Chest", "UpperChest", "LeftShoulder", "RightShoulder", "LeftUpperArm", "RightUpperArm",
         "LeftLowerArm", "RightLowerArm"}
LOWER = {"Hips", "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg"}


# Face classes (rest pose heights): sure top, sure bottom, ambiguous band above / below the
# waist (shirt hems and waistbands overlap there), hands (skin colour reference).
TOP, BOTTOM, BAND_UP, BAND_DOWN, HAND = 1, 2, 3, 4, 5


def classify(obj, arm):
    """Per-polygon class from the shared rest pose (every character has the library T-pose after
    match_ual_rest.py, so unmapped helper bones in the scanned rigs do not matter): head above
    the neck joint, hands outside the wrists, shoes below the ankles are never clothing."""
    bones = arm.data.bones
    w = arm.matrix_world
    def head(n):
        return w @ bones[n].head_local
    neck = head("Neck").z
    waist = head("Spine").z
    hips = head("Hips").z
    ankle = max(head("LeftFoot").z, head("RightFoot").z) + 0.02
    wrist = min(abs(head("LeftHand").x), abs(head("RightHand").x)) - 0.01
    band_top, band_low = waist + 0.1, hips - 0.14
    mesh = obj.data
    mw = obj.matrix_world
    vclass = np.zeros(len(mesh.vertices), dtype=np.int8)
    for v in mesh.vertices:
        p = mw @ v.co
        if abs(p.x) > wrist + 0.03 and p.z < neck:
            vclass[v.index] = HAND
        elif p.z > neck or abs(p.x) > wrist or p.z < ankle:
            continue
        elif p.z > band_top:
            vclass[v.index] = TOP
        elif p.z < band_low:
            vclass[v.index] = BOTTOM
        else:
            vclass[v.index] = BAND_UP if p.z > waist else BAND_DOWN
    out = []
    for p in mesh.polygons:
        cls = [int(vclass[i]) for i in p.vertices]
        if all(c == cls[0] for c in cls):
            out.append(cls[0])
        elif all(c in (TOP, BOTTOM, BAND_UP, BAND_DOWN) for c in cls):
            out.append(BAND_UP if max(cls) == BAND_UP or TOP in cls else BAND_DOWN)
        else:
            out.append(0)   # a face across the wrist / neck / ankle border stays original
    return out


def rasterize(obj, pclass):
    mesh = obj.data
    uv = mesh.uv_layers.active.data
    mask = np.zeros((SIZE, SIZE), dtype=np.uint8)
    for p, c in zip(mesh.polygons, pclass):
        if c == 0:
            continue
        pts = np.array([uv[li].uv[:] for li in p.loop_indices]) * (SIZE - 1)
        for k in range(1, len(pts) - 1):
            tri = np.array([pts[0], pts[k], pts[k + 1]])
            x0, y0 = np.floor(tri.min(0)).astype(int) - 1
            x1, y1 = np.ceil(tri.max(0)).astype(int) + 1
            x0, y0 = max(x0, 0), max(y0, 0)
            x1, y1 = min(x1, SIZE - 1), min(y1, SIZE - 1)
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
            l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
            l3 = 1 - l1 - l2
            # Slightly generous edges so neighbouring faces leave no seam.
            inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
            sub = mask[y0:y1 + 1, x0:x1 + 1]
            sub[inside] = c
    return mask


def skin_like(rgb):
    r, g, b = rgb[..., 0] * 255, rgb[..., 1] * 255, rgb[..., 2] * 255
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    mx = np.maximum(np.maximum(r, g), b)
    sat = (mx - np.minimum(np.minimum(r, g), b)) / np.maximum(mx, 1)
    # Saturation floor: cream / white fabric is warm but far less saturated than skin.
    return (cr > 136) & (cr < 175) & (cb > 82) & (cb < 128) & (y > 45) & (r > g) & (g >= b * 0.85) & (sat > 0.17)


def dilate(a, n):
    out = a.copy()
    for _ in range(n):
        p = np.pad(out, 1)
        out = np.maximum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return out


def erode(a, n):
    return 255 - dilate(255 - a, n)


def blur(a):
    p = np.pad(a.astype(np.float32), 1, mode="edge")
    return (p[1:-1, 1:-1] * 4 + p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 8.0


for ident in IDS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PEOPLE, ident + ".glb"))
    obj = next(o for o in bpy.data.objects if o.type == 'MESH' and o.vertex_groups)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    pclass = classify(obj, arm)
    mask = rasterize(obj, pclass)
    img = bpy.data.images.load(os.path.join(PEOPLE, ident + "_Image_0.jpg"))
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3]
    if (w, h) != (SIZE, SIZE):
        ys = (np.arange(SIZE) * h / SIZE).astype(int)
        xs = (np.arange(SIZE) * w / SIZE).astype(int)
        px = px[ys][:, xs]
    generic = skin_like(px)
    # This character's own skin tone (median over the hands) keeps tan / beige cloth recolourable.
    hand = (mask == HAND) & generic
    skin = generic
    if hand.sum() > 200:
        ref = np.median(px[hand], axis=0)
        chroma = px / np.maximum(px.sum(-1, keepdims=True), 1e-4)
        ref_c = ref / max(ref.sum(), 1e-4)
        bright = px.sum(-1) / max(ref.sum(), 1e-4)
        skin = generic & (np.abs(chroma - ref_c).sum(-1) < 0.07) & (bright > 0.45) & (bright < 1.7)
    # Skin areas grow slightly so the clothing border never bleeds onto skin.
    skin = dilate(skin.astype(np.uint8) * 255, 1) > 0
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    sat = (mx - np.minimum(np.minimum(r, g), b)) / np.maximum(mx, 1e-4)
    # Long hair falling over the shoulders lies below the neck joint: keep brown/auburn texels
    # out of the top.
    hair = dilate(((r > g) & (g > b) & (sat > 0.3) & (mx < 0.62)).astype(np.uint8) * 255, 1) > 0
    cloth = (mask >= TOP) & (mask <= BAND_DOWN) & ~skin
    top = cloth & (mask == TOP) & ~hair
    bottom = cloth & (mask == BOTTOM)
    band = cloth & ((mask == BAND_UP) | (mask == BAND_DOWN))
    # Band texels (hems, waistbands) join whichever garment they look like; when top and bottom
    # are the same colour (suits, dresses) the waist height decides.
    tc = np.median(px[top], axis=0) if top.sum() > 100 else None
    bc = np.median(px[bottom], axis=0) if bottom.sum() > 100 else None
    if tc is not None and bc is not None and np.abs(tc - bc).sum() > 0.12:
        to_top = np.abs(px - tc).sum(-1) < np.abs(px - bc).sum(-1)
    else:
        to_top = mask == BAND_UP
    top = top | (band & to_top & ~hair)
    bottom = bottom | (band & ~to_top)
    out = np.zeros((SIZE, SIZE, 4), dtype=np.float32)
    for ch, m in enumerate((top, bottom)):
        m = m.astype(np.uint8) * 255
        # Remove isolated speckles (stray skin-test misses), then soften the border.
        m = dilate(erode(m, 1), 1)
        out[..., ch] = blur(m) / 255.0
    out[..., 3] = 1.0
    res = bpy.data.images.new(ident + "_outfit_mask", SIZE, SIZE, alpha=False)
    res.pixels[:] = out.ravel()
    res.filepath_raw = os.path.join(PEOPLE, ident + "_outfit_mask.png")
    res.file_format = 'PNG'
    res.save()
    cover = [float((out[..., c] > 0.5).mean()) for c in range(2)]
    print("MASK", ident, "faces", len(pclass), "top colour", None if tc is None else np.round(tc, 2),
          "bottom colour", None if bc is None else np.round(bc, 2), "coverage", [round(c, 3) for c in cover])
