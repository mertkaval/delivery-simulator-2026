"""Objective checks for generated sounds: levels, clipping, silence, loop seams, spectrograms.

usage: python inspect_sfx.py <wav dir> <spectrogram png>
"""
import os
import sys
import wave

import numpy as np

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

LOOPS = {"bike_freewheel", "bike_chain", "tyre_roll", "bus_engine_idle", "fountain_water", "city_ambience",
         "park_ambience", "restaurant_ambience", "grill_sizzle", "wind", "rain"}


def load(path):
    with wave.open(path) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        return data, w.getframerate()


def spectrogram(x, bins=96, cols=220):
    hop = max(1, (len(x) - 2048) // cols)
    frames = [np.abs(np.fft.rfft(x[i:i + 2048] * np.hanning(2048)))[:1024] for i in range(0, max(1, len(x) - 2048), hop)][:cols]
    if not frames:
        return np.zeros((bins, cols))
    s = np.array(frames).T
    # Log-frequency rows from 40 Hz to 16 kHz.
    edges = np.geomspace(2, 1023, bins + 1).astype(int)
    rows = np.array([s[a:max(b, a + 1)].mean(axis=0) for a, b in zip(edges[:-1], edges[1:])])
    db = 20 * np.log10(rows + 1e-6)
    return np.clip((db + 60) / 60, 0, 1)[::-1]


def main(folder, out_png):
    names = sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".wav"))
    problems = 0
    tiles = []
    for n in names:
        x, sr = load(os.path.join(folder, n + ".wav"))
        peak = float(np.max(np.abs(x)))
        rms = float(np.sqrt(np.mean(x ** 2)))
        clip = float(np.mean(np.abs(x) > 0.995))
        # Seam jump relative to the clip's own typical sample-to-sample change (95th pct).
        typical = float(np.percentile(np.abs(np.diff(x)), 95)) or 1e-6
        seam = float(abs(x[-1] - x[0])) / typical if n in LOOPS else 0.0
        flags = []
        if peak < 0.05: flags.append("SILENT")
        if clip > 0.001: flags.append("CLIPPING")
        if n in LOOPS and seam > 1.5: flags.append("LOOP-CLICK")
        problems += bool(flags)
        print(f"{n:22s} {len(x) / sr:5.2f}s peak {peak:.2f} rms {rms:.3f} seam {seam:.3f} {' '.join(flags)}")
        tiles.append((n, spectrogram(x)))
    if Image and out_png:
        cols = 4
        w, h = 230, 120
        sheet = Image.new("RGB", (cols * w, ((len(tiles) + cols - 1) // cols) * h), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for i, (n, s) in enumerate(tiles):
            img = Image.fromarray((np.stack([s ** 0.7, s ** 1.4, s ** 3], -1) * 255).astype(np.uint8)).resize((w - 10, h - 22))
            x0, y0 = (i % cols) * w, (i // cols) * h
            sheet.paste(img, (x0 + 5, y0 + 18))
            d.text((x0 + 5, y0 + 3), n, fill=(230, 230, 230))
        sheet.save(out_png)
    print("problems:", problems)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
