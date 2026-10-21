"""Objective listen-check for generated sounds: levels, clipping, harshness, clicks, loop seams.

usage: python inspect_sfx.py <wav dir> [spectrogram png]

Per file: duration, peak (dBFS), short-term loudness (loudest 300 ms RMS, dBFS), high-band share
(energy above 8 kHz), DC offset, edge clicks for one-shots, and for loops:
  seam   - sample jump across the loop point relative to the clip's typical step (95th pct),
  hp     - high-passed (>4 kHz) energy in 10 ms around the seam relative to the clip's median,
  level  - RMS of the last vs first 100 ms (dB): a level step at the seam is audible as a bump,
  smpl   - a RIFF smpl loop chunk is present (Godot's importer then loops it by itself).
Exits non-zero when any file is flagged.
"""
import os
import struct
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import LOOPS  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

# Short-term loudness window (dBFS) every sound must fall in: loud enough to hear, never hot.
LOUD_MIN, LOUD_MAX = -34.0, -12.0
# High-band share limit (% energy above 8 kHz); hiss textures are allowed more.
HF_LIMIT = 12.0
HF_TEXTURES = {"air_brake_hiss": 20.0, "grill_sizzle": 20.0}


def load(path):
    with wave.open(path) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        return data, w.getframerate()


def has_smpl(path):
    raw = open(path, "rb").read()
    i = 12
    while i + 8 <= len(raw):
        cid, size = raw[i:i + 4], struct.unpack("<I", raw[i + 4:i + 8])[0]
        if cid == b"smpl":
            loops = struct.unpack("<I", raw[i + 8 + 28:i + 8 + 32])[0]
            return loops > 0
        i += 8 + size + (size & 1)
    return False


def short_loudness(x, sr, win=0.3):
    w = int(win * sr)
    if len(x) <= w:
        return float(np.sqrt(np.mean(x ** 2)))
    c = np.concatenate([[0.0], np.cumsum(x ** 2)])
    return float(np.sqrt(np.max(c[w:] - c[:-w]) / w))


def db(v):
    return 20 * np.log10(max(v, 1e-9))


def highpass(x, sr, fc):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return np.fft.irfft(spec * (f > fc), len(x))


def seam_metrics(x, sr):
    """Loop-seam continuity. A click is a step bigger than anything inside the clip, so the
    seam is compared with the clip's own extremes (99.9th percentile step, 99th percentile
    10 ms high-band energy), which also works for sparse click trains (ticks, ratchets)."""
    d = np.abs(np.diff(x))
    jump = abs(x[-1] - x[0]) / (float(np.percentile(d, 99.9)) or 1e-9)
    # Treat the clip as periodic, roll the seam to the middle and measure HF energy there.
    rolled = np.roll(x, len(x) // 2)
    hp = highpass(rolled, sr, 4000) ** 2
    w = int(0.01 * sr)
    frames = hp[: len(hp) // w * w].reshape(-1, w).mean(axis=1)
    mid = (len(x) // 2) // w
    seam_e = frames[max(0, mid - 1):mid + 2].max()
    ref = float(np.percentile(frames, 99)) or 1e-12
    hp_ratio = seam_e / ref
    # Level continuity over 250 ms either side (beds; click trains average out).
    n = int(0.25 * sr)
    lvl = db(np.sqrt(np.mean(x[-n:] ** 2))) - db(np.sqrt(np.mean(x[:n] ** 2)))
    return jump, hp_ratio, lvl


def spectrogram(x, bins=96, cols=220):
    hop = max(1, (len(x) - 2048) // cols)
    frames = [np.abs(np.fft.rfft(x[i:i + 2048] * np.hanning(2048)))[:1024] for i in range(0, max(1, len(x) - 2048), hop)][:cols]
    if not frames:
        return np.zeros((bins, cols))
    s = np.array(frames).T
    edges = np.geomspace(2, 1023, bins + 1).astype(int)
    rows = np.array([s[a:max(b, a + 1)].mean(axis=0) for a, b in zip(edges[:-1], edges[1:])])
    d = 20 * np.log10(rows + 1e-6)
    return np.clip((d + 60) / 60, 0, 1)[::-1]


def main(folder, out_png=None):
    names = sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".wav"))
    problems = 0
    tiles = []
    print(f"{'sound':22s} {'dur':>6s} {'peak':>6s} {'loud':>6s} {'hf%':>5s}  loop checks / flags")
    for n in names:
        path = os.path.join(folder, n + ".wav")
        x, sr = load(path)
        peak = float(np.max(np.abs(x)))
        loud = db(short_loudness(x, sr))
        spec = np.abs(np.fft.rfft(x)) ** 2
        f = np.fft.rfftfreq(len(x), 1 / sr)
        hf = float(spec[f > 8000].sum() / max(spec.sum(), 1e-12)) * 100
        dc = abs(float(np.mean(x)))
        flags = []
        if peak < 0.05: flags.append("SILENT")
        if np.mean(np.abs(x) > 0.995) > 0.0005: flags.append("CLIPPING")
        if peak > 0.95: flags.append("HOT")
        if not LOUD_MIN <= loud <= LOUD_MAX: flags.append(f"LEVEL({loud:.0f})")
        if hf > HF_TEXTURES.get(n, HF_LIMIT): flags.append("HARSH")
        if dc > 0.01: flags.append("DC")
        extra = ""
        if n in LOOPS:
            jump, hp_ratio, lvl = seam_metrics(x, sr)
            smpl = has_smpl(path)
            extra = f"seam {jump:4.2f} hp {hp_ratio:4.1f} lvl {lvl:+5.1f}dB smpl {'y' if smpl else 'n'}"
            if jump > 1.0: flags.append("LOOP-CLICK")
            if hp_ratio > 1.5: flags.append("LOOP-HF-BURST")
            if abs(lvl) > 4.0: flags.append("LOOP-LEVEL-STEP")
            if not smpl: flags.append("NO-LOOP-CHUNK")
        else:
            edge = max(abs(x[0]), abs(x[-1]))
            extra = f"edges {edge:.3f}"
            if edge > 0.02: flags.append("EDGE-CLICK")
        problems += bool(flags)
        print(f"{n:22s} {len(x) / sr:5.2f}s {db(peak):5.1f} {loud:6.1f} {hf:5.1f}  {extra} {' '.join(flags)}")
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
    print("files:", len(names), "problems:", problems)
    return problems


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None) else 0)
