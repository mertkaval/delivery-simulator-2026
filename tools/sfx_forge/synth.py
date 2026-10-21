"""SFX Forge: free, offline procedural sound-effect synthesis for the game (numpy only).

Techniques: modal synthesis (bells, cutlery, register), shaped noise with FFT-domain filters
(tyres, wind, water, hiss, ambience), firing-pulse engines (diesel bus), formant voices
(pigeons, crows, gulls, dog) and seamless crossfaded loops. Output: 16-bit PCM WAV.

Every preset is deterministic for a given seed, so regenerating gives identical files.
"""
import io
import math
import struct
import wave

import numpy as np

SR = 44100


# --------------------------------------------------------------------------- primitives

def rng(seed):
    return np.random.default_rng(seed)


def t_axis(duration):
    return np.arange(int(duration * SR)) / SR


def white(n, r):
    return r.standard_normal(n)


def fft_filter(x, response):
    """Zero-phase filtering: multiply the spectrum by response(freqs) (magnitude)."""
    n = len(x)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(spec * response(freqs), n)


def coloured(n, r, slope_db_oct):
    """Noise with a spectral slope (-3 dB/oct pink, -6 brown, 0 white)."""
    return fft_filter(white(n, r), lambda f: np.where(f > 10, (np.maximum(f, 10) / 1000.0) ** (slope_db_oct / 6.02), 0.0))


def band(x, lo, hi, order=2.0):
    def resp(f):
        hp = 1.0 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order)) if lo > 0 else 1.0
        lp = 1.0 / np.sqrt(1 + (f / hi) ** (2 * order)) if hi else 1.0
        return hp * lp
    return fft_filter(x, resp)


def resonance(x, centre, q, gain=1.0):
    """Add a resonant peak (formant) at centre Hz."""
    return fft_filter(x, lambda f: 1.0 + gain / (1 + ((f - centre) / (centre / q)) ** 2))


def env_adsr(n, a, d, s, r, sustain_level=0.7):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    s_len = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, max(a, 1)), np.linspace(1, sustain_level, max(d, 1)),
                        np.full(s_len, sustain_level), np.linspace(sustain_level, 0, max(r, 1))])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def exp_decay(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


def modal(duration, modes, strike_noise=0.0, seed=0):
    """Sum of decaying sinusoids. modes: [(freq Hz, amplitude, decay seconds)]."""
    t = t_axis(duration)
    r = rng(seed)
    out = np.zeros_like(t)
    for f, a, tau in modes:
        out += a * np.sin(2 * np.pi * f * t + r.uniform(0, 2 * np.pi)) * np.exp(-t / tau)
    if strike_noise:
        n = int(0.004 * SR)
        out[:n] += strike_noise * band(white(n, r), 2000, 9000) * np.linspace(1, 0, n)
    return out


def place(buf, sound, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sound))
    if i < len(buf):
        buf[i:j] += sound[: j - i]
    return buf


def loopify(x, fade=0.5):
    """Crossfade the tail into the head so the clip loops without a click (equal-power, so
    noise beds keep their level through the seam)."""
    n = int(fade * SR)
    head, tail = x[:n].copy(), x[-n:]
    w = np.sin(np.linspace(0, np.pi / 2, n))
    x = x[:-n].copy()
    x[:n] = head * w + tail * np.cos(np.linspace(0, np.pi / 2, n))
    return x


def normalise(x, peak=0.89):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def soft_clip(x, drive=1.5):
    return np.tanh(x * drive) / np.tanh(drive)


def to_wav_bytes(x, stereo=None, loop=False):
    """16-bit PCM WAV. Loops get a RIFF 'smpl' chunk (forward loop over the whole clip), which
    Godot's WAV importer reads with loop mode 'Detect From WAV'."""
    x = np.clip(x, -1, 1)
    frames = len(x)
    data = np.round(x * 32767).astype(np.int16)
    channels = 1
    if stereo is not None:
        right = np.round(np.clip(stereo, -1, 1) * 32767).astype(np.int16)
        data = np.column_stack([data, right]).ravel()
        channels = 2
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    out = bytearray(buf.getvalue())
    if loop:
        smpl = struct.pack("<9I", 0, 0, int(1e9 / SR), 60, 0, 0, 0, 1, 0)
        smpl += struct.pack("<6I", 0, 0, 0, frames, 0, 0)
        out += b"smpl" + struct.pack("<I", len(smpl)) + smpl
        out[4:8] = struct.pack("<I", len(out) - 8)
    return bytes(out)


# --------------------------------------------------------------------------- mix helpers

def fade(x, a=0.002, r=0.015):
    """Short fade in/out so one-shots never start or stop with a click."""
    x = x.copy()
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    x[:na] *= np.linspace(0, 1, na)
    x[-nr:] *= np.linspace(1, 0, nr) ** 2
    return x


def soften(x, fc=7000.0):
    """Gentle first-order high cut: tames harsh top end without dulling the attack."""
    return fft_filter(x, lambda f: 1.0 / np.sqrt(1 + (f / fc) ** 2))


def dc_block(x, fc=25.0):
    return fft_filter(x, lambda f: 1.0 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** 4))


def loudest_rms(x, win=0.3):
    """RMS of the loudest `win`-second window: a short-term loudness that treats a 0.1 s click
    and a 10 s loop alike."""
    w = int(win * SR)
    if len(x) <= w:
        return float(np.sqrt(np.mean(x ** 2)))
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    return float(np.sqrt(np.max(c[w:] - c[:-w]) / w))


def level(x, rms_db=-20.0, peak=0.89, right=None):
    """Loudness-normalise to a short-term RMS target (dBFS), never above `peak`.
    With `right`, both stereo channels share one gain."""
    both = x if right is None else np.concatenate([x, right])
    r = loudest_rms(x) if right is None else max(loudest_rms(x), loudest_rms(right))
    g = 10 ** (rms_db / 20) / max(r, 1e-9)
    m = float(np.max(np.abs(both))) * g
    if m > peak:
        g *= peak / m
    return x * g if right is None else (x * g, right * g)


def cplace(buf, sound, at):
    """Place `sound` at time `at`, wrapping round the end: periodic (seamless) loops."""
    n = len(buf)
    i = int(at * SR) % n
    k = min(len(sound), n)
    first = min(k, n - i)
    buf[i:i + first] += sound[:first]
    if k > first:
        buf[: k - first] += sound[first:k]
    return buf


def log_bell(f, fc, octaves):
    """Gaussian band-pass gain in log frequency (centre fc, width in octaves)."""
    return np.exp(-0.5 * (np.log2(np.maximum(f, 1.0) / fc) / octaves) ** 2)


def tv_filter(x, resp, frame=1024):
    """Time-varying spectral filter: resp(t_seconds, freqs) -> gain. Hann frames at 50 % overlap."""
    hop = frame // 2
    win = np.hanning(frame + 1)[:-1]
    pad = np.concatenate([np.zeros(hop), x, np.zeros(frame)])
    out = np.zeros(len(pad))
    freqs = np.fft.rfftfreq(frame, 1 / SR)
    for i in range(0, len(pad) - frame, hop):
        seg = np.fft.rfft(pad[i:i + frame] * win)
        out[i:i + frame] += np.fft.irfft(seg * resp((i - hop + frame / 2) / SR, freqs), frame)
    return out[hop:hop + len(x)]


def crackle(n, r, rate, lo=1500, hi=7000, decay=0.0012):
    """Sparse random micro-impulses (paper, grass, nylon, rain drops)."""
    imp = np.zeros(n)
    k = r.poisson(rate * n / SR)
    imp[r.integers(0, n, k)] += r.standard_normal(k) * r.uniform(0.15, 1.0, k) ** 2
    m = max(8, int(decay * 6 * SR))
    ker = white(m, r) * np.exp(-np.arange(m) / (decay * SR))
    return band(np.convolve(imp, ker)[:n], lo, hi)


def reverb(x, t60=0.5, mix=0.2, seed=99, lp=5000, circular=False):
    """Diffuse room: convolution with decaying filtered noise. Circular keeps loops seamless."""
    r = rng(seed)
    m = int(t60 * SR)
    ir = white(m, r) * np.exp(-6.9 * np.arange(m) / m)
    ir = band(ir, 120, lp)
    ir[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    ir /= np.sqrt(np.sum(ir ** 2))
    if circular:
        n = len(x)
        wet = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir, n), n)
        dry = x
    else:
        n = len(x) + m
        wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
        dry = np.pad(x, (0, m))
    return dry * (1 - mix) + wet * mix * 0.7


def env_shape(n, attack, release, curve=2.0):
    """Smooth attack/release envelope (raised-sine edges) over n samples."""
    e = np.ones(n)
    a, r = max(1, int(attack * SR)), max(1, int(release * SR))
    e[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** curve
    e[-r:] *= np.cos(np.linspace(0, np.pi / 2, r)) ** curve
    return e


def struck(duration, f, partials, attack=0.0012, seed=0):
    """Mallet/strike voice: partials [(ratio, amp, decay s)] with a soft attack (no click)."""
    t = t_axis(duration)
    r = rng(seed)
    out = np.zeros_like(t)
    for ratio, a, tau in partials:
        out += a * np.sin(2 * np.pi * f * ratio * t + r.uniform(0, 0.4)) * np.exp(-t / tau)
    a = int(attack * SR)
    out[:a] *= np.linspace(0, 1, a)
    return out


MARIMBA = [(1.0, 1.0, 0.45), (3.93, 0.22, 0.09), (9.2, 0.05, 0.03), (1.0018, 0.35, 0.5)]
BELL = [(1.0, 1.0, 1.0), (2.0, 0.3, 0.55), (3.0, 0.12, 0.35), (4.17, 0.05, 0.2), (1.0025, 0.5, 1.1)]


def marimba(f, dur=0.9, decay=1.0, seed=0):
    return struck(dur, f, [(r_, a, d * decay) for r_, a, d in MARIMBA], 0.0015, seed)


def bell(f, dur=1.6, decay=1.0, seed=0):
    return struck(dur, f, [(r_, a, d * decay) for r_, a, d in BELL], 0.0012, seed)


def harmonic_source(f0, max_hz=4000.0, tilt=1.0):
    """Band-limited sawtooth-like source following an f0 curve (array, Hz)."""
    phase = 2 * np.pi * np.cumsum(f0) / SR
    out = np.zeros(len(f0))
    for k in range(1, int(max_hz / max(np.min(f0), 30)) + 1):
        out += np.sin(k * phase) / k ** tilt * (k * np.max(f0) < max_hz * 1.2)
    return out


def chirp_tone(f_start, f_end, dur, decay=None, harmonics=((1, 1.0),)):
    """Sine (plus harmonics) gliding exponentially from f_start to f_end."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = f_start * (f_end / f_start) ** (tt / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = sum(a * np.sin(k * ph) for k, a in harmonics)
    return s * (np.exp(-tt / decay) if decay else 1.0)


# --------------------------------------------------------------------------- presets

def bike_bell(seed=1):
    # Ding-ding: dome bell partials (inharmonic), two strikes by the thumb lever.
    def ring(s):
        f0 = 2480 * (1 + rng(s).uniform(-0.01, 0.01))
        return modal(1.4, [(f0, 1.0, 0.55), (f0 * 2.76, 0.45, 0.22), (f0 * 5.4, 0.18, 0.09), (f0 * 8.93, 0.08, 0.05), (f0 * 1.003, 0.6, 0.6)], 0.5, s)
    out = np.zeros(int(1.8 * SR))
    place(out, ring(seed), 0.0)
    place(out, ring(seed + 1) * 0.8, 0.16)
    return normalise(out, 0.8)


def bike_freewheel(seed=2, rate=22.0):
    # Ratcheting pawl clicks of a coasting hub, looped (pitch the player for speed).
    dur = 2.0
    out = np.zeros(int(dur * SR))
    r = rng(seed)
    click = modal(0.03, [(4200, 1, 0.004), (6900, 0.6, 0.003), (2600, 0.4, 0.006)], 0.2, seed)
    t = 0.0
    while t < dur - 0.05:
        place(out, click * r.uniform(0.7, 1.0), t)
        t += 1.0 / rate * r.uniform(0.96, 1.04)
    return normalise(loopify(out, 0.05), 0.5)


def tyre_roll(seed=3):
    # Rubber on asphalt: brown-ish noise, low band, gentle surface-texture flutter.
    dur = 4.0
    r = rng(seed)
    n = int(dur * SR)
    x = band(coloured(n, r, -4.5), 60, 1400)
    flutter = 1 + 0.25 * band(white(n, r), 0, 12)
    x *= flutter / np.max(np.abs(flutter))
    x += 0.15 * band(white(n, r), 2500, 6000) * band(white(n, r), 0, 30)  # grit
    return normalise(loopify(x, 0.4), 0.6)


def wrap_loop(buf, n):
    """Fold anything past n samples back onto the start: a seamless periodic loop."""
    out = buf[:n].copy()
    tail = buf[n:]
    out[: len(tail)] += tail[:n]
    return out


def chain_pedal(seed=4):
    # Chain over sprockets while pedalling: periodic soft rattles at cadence.
    dur = 2.0
    n = int(dur * SR)
    out = np.zeros(n + int(0.05 * SR))
    r = rng(seed)
    tick = band(white(int(0.02 * SR), r), 1500, 5000) * exp_decay(int(0.02 * SR), 0.004)
    for i in range(int(dur * 18)):
        place(out, tick * r.uniform(0.3, 0.8), i / 18 + r.uniform(0, 0.01))
    return normalise(wrap_loop(out, n), 0.35)


def brake_squeal(seed=5):
    t = t_axis(1.3)
    r = rng(seed)
    f = 1850 + 40 * np.sin(2 * np.pi * 6 * t)
    squeal = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    e = env_adsr(len(t), 0.08, 0.2, 0.9, 0.35, 0.55)
    scrub = band(white(len(t), r), 300, 3000) * 0.4
    return normalise((squeal * 0.35 + scrub) * e, 0.7)


def footstep(seed=6, surface="concrete"):
    r = rng(seed)
    n = int(0.25 * SR)
    heel = band(white(n, r), 80, 900) * exp_decay(n, 0.025)
    toe = band(white(n, r), 1200, 6000) * exp_decay(n, 0.012) * (0.6 if surface == "concrete" else 0.25)
    out = np.zeros(n)
    place(out, heel, 0.0)
    place(out, toe, 0.045)
    if surface == "gravel":
        for _ in range(14):
            place(out, band(white(400, r), 2000, 8000) * exp_decay(400, 0.002) * r.uniform(0.1, 0.4), r.uniform(0.0, 0.12))
    return normalise(out, 0.6)



def door_close(seed=8):
    r = rng(seed)
    n = int(0.6 * SR)
    thud = band(white(n, r), 40, 400) * exp_decay(n, 0.06)
    latch = modal(0.1, [(1500, 1, 0.012), (2900, 0.5, 0.01)], 0.5, seed)
    out = thud.copy()
    place(out, latch * 0.6, 0.02)
    return normalise(out, 0.8)


def bus_engine_idle(seed=9):
    # Six-cylinder diesel at idle: firing pulses at 3x crank rate with combustion knock.
    dur = 4.0
    t = t_axis(dur)
    r = rng(seed)
    crank = 11.5  # Hz (690 rpm)
    firing = 3 * crank
    phase = (t * firing) % 1.0
    pulses = np.exp(-phase * 9) * (1 + 0.15 * np.sin(2 * np.pi * crank * t))
    body = band(pulses * coloured(len(t), r, -3) + 0.6 * pulses, 25, 900)
    knock = band(white(len(t), r), 1200, 4000) * np.exp(-phase * 40) * 0.25
    hum = 0.3 * np.sin(2 * np.pi * firing * 2 * t) + 0.2 * np.sin(2 * np.pi * firing * t)
    x = body + knock + hum * 0.4
    return normalise(loopify(soft_clip(normalise(x), 1.3), 0.3), 0.7)


def air_brake_hiss(seed=10):
    r = rng(seed)
    n = int(1.4 * SR)
    hiss = band(white(n, r), 2500, 11000) * env_adsr(n, 0.01, 0.15, 0.7, 0.9, 0.5)
    pop = band(white(n, r), 60, 500) * exp_decay(n, 0.04) * 0.5
    return normalise(hiss + pop, 0.75)


def bus_door(seed=11):
    out = np.zeros(int(2.2 * SR))
    place(out, air_brake_hiss(seed) * 0.6, 0.0)
    r = rng(seed)
    n = int(0.9 * SR)
    slide = band(white(n, r), 150, 1200) * env_adsr(n, 0.1, 0.3, 0.6, 0.3, 0.6) * 0.6
    place(out, slide, 0.3)
    place(out, door_close(seed) * 0.7, 1.15)
    return normalise(out, 0.8)


def chime(notes, step=0.32, decay=0.9, seed=12):
    out = np.zeros(int((len(notes) * step + 1.6) * SR))
    for i, f in enumerate(notes):
        tone = modal(1.4, [(f, 1, decay), (f * 2, 0.3, decay * 0.5), (f * 3.01, 0.12, decay * 0.3)], 0.05, seed + i)
        place(out, tone, i * step)
    return normalise(out, 0.7)


def bus_stop_chime(seed=13):
    return chime([659.3, 523.3], 0.42, 1.1, seed)


def car_pass(seed=14):
    # Doppler fly-by: engine tone + tyre noise sweeping through the listener.
    dur = 3.5
    t = t_axis(dur)
    r = rng(seed)
    v, d0, c = 13.0, 4.0, 343.0
    x_pos = (t - dur / 2) * v
    dist = np.sqrt(x_pos ** 2 + d0 ** 2)
    radial = x_pos / dist * v
    shift = c / (c + radial)
    f_engine = 95 * shift
    engine = band(np.sin(2 * np.pi * np.cumsum(f_engine) / SR) * 0.5 + 0.5 * np.sin(4 * np.pi * np.cumsum(f_engine) / SR), 40, 800)
    tyres = band(coloured(len(t), r, -3), 200, 4000)
    gain = 1 / (dist / d0) ** 1.4
    return normalise((engine * 0.6 + tyres) * gain, 0.75)


def car_horn(seed=15):
    t = t_axis(0.6)
    tone = sum(np.sign(np.sin(2 * np.pi * f * t)) * a for f, a in ((420, 0.5), (500, 0.5)))
    return normalise(band(tone, 200, 3000) * env_adsr(len(t), 0.01, 0.05, 0.9, 0.08, 0.9), 0.6)


def bird_chirp(seed=16):
    r = rng(seed)
    out = np.zeros(int(1.2 * SR))
    at = 0.0
    for _ in range(r.integers(2, 5)):
        n = int(r.uniform(0.05, 0.12) * SR)
        tt = np.arange(n) / SR
        f = r.uniform(2800, 4200) + r.uniform(-1500, 1500) * tt / tt[-1] + 300 * np.sin(2 * np.pi * r.uniform(20, 45) * tt)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2
        place(out, s, at)
        at += n / SR + r.uniform(0.03, 0.12)
    return normalise(out, 0.5)


def pigeon_coo(seed=17):
    # "Hoo-hrroo": low formant voice with a throaty tremolo.
    t = t_axis(1.2)
    r = rng(seed)
    f = 300 + 60 * np.sin(2 * np.pi * 0.8 * t) - 50 * t
    voice = np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 + 0.6 * np.sin(2 * np.pi * 28 * t))
    voice = resonance(voice + 0.2 * white(len(t), r), 600, 4, 2)
    e = np.zeros(len(t))
    for a, b in ((0.0, 0.35), (0.45, 1.1)):
        i, j = int(a * SR), int(b * SR)
        e[i:j] = np.sin(np.linspace(0, np.pi, j - i)) ** 1.5
    return normalise(band(voice * e, 150, 1500), 0.5)


def wing_flap(seed=18):
    r = rng(seed)
    out = np.zeros(int(0.9 * SR))
    for i in range(10):
        n = int(0.04 * SR)
        place(out, band(white(n, r), 300, 3000) * np.hanning(n) * (1 - i / 12), i * 0.075)
    return normalise(out, 0.6)


def crow_caw(seed=19):
    out = np.zeros(int(1.6 * SR))
    r = rng(seed)
    for k in range(3):
        n = int(0.32 * SR)
        tt = np.arange(n) / SR
        f = 520 - 120 * tt / tt[-1]
        saw = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
        v = resonance(saw + 0.4 * white(n, r), 1300, 3, 3)
        v = resonance(v, 2400, 4, 1.5)
        place(out, band(v, 300, 5000) * np.sin(np.pi * tt / tt[-1]) ** 0.7, k * 0.42)
    return normalise(soft_clip(normalise(out), 2.0), 0.55)


def seagull_call(seed=20):
    t = t_axis(1.0)
    f = 1500 + 900 * np.sin(np.pi * t / t[-1]) ** 2 - 600 * t
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(6 * np.pi * np.cumsum(f) / SR)
    return normalise(v * env_adsr(len(t), 0.05, 0.2, 0.7, 0.4, 0.6), 0.45)


def dog_bark(seed=21):
    out = np.zeros(int(1.1 * SR))
    r = rng(seed)
    for k in range(2):
        n = int(0.16 * SR)
        tt = np.arange(n) / SR
        f = 420 + 250 * np.exp(-tt * 25)
        pulse = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
        v = resonance(pulse + 0.5 * white(n, r), 900, 3, 4)
        v = resonance(v, 1800, 4, 2)
        place(out, band(v, 200, 4000) * np.exp(-tt * 14) * (1 - np.exp(-tt * 300)), k * 0.38)
    return normalise(soft_clip(normalise(out), 2.5), 0.7)


def fountain_water(seed=22):
    dur = 6.0
    r = rng(seed)
    n = int(dur * SR)
    splash = band(coloured(n, r, -1.5), 300, 9000) * (0.7 + 0.3 * band(white(n, r), 0, 4))
    out = splash * 0.5
    for _ in range(int(dur * 40)):
        m = int(0.03 * SR)
        f = r.uniform(600, 2200)
        tt = np.arange(m) / SR
        drop = np.sin(2 * np.pi * (f + 3000 * tt) * tt) * np.exp(-tt * 120)
        place(out, drop * r.uniform(0.05, 0.25), r.uniform(0, dur - 0.05))
    return normalise(loopify(out, 0.5), 0.6)


def city_ambience(seed=23):
    # Distant traffic rumble with slow swells, the odd passing car, far horn and birds.
    dur = 20.0
    r = rng(seed)
    n = int(dur * SR)
    rumble = band(coloured(n, r, -5), 30, 600) * (0.7 + 0.3 * band(white(n, r), 0, 0.15) / 0.05)
    out = normalise(rumble) * 0.6
    for at in (2.5, 9.0, 14.5):
        place(out, band(car_pass(seed + int(at * 10)), 60, 2500) * 0.25, at)
    place(out, band(car_horn(seed), 300, 1500) * 0.06, 6.2)
    for at in (1.2, 5.5, 11.7, 17.3):
        place(out, bird_chirp(seed + int(at * 7)) * 0.08, at)
    left = loopify(out, 1.5)
    right = loopify(np.roll(out, int(0.013 * SR)) * 0.95 + 0.05 * band(coloured(n, r, -5), 30, 500), 1.5)
    return normalise(left, 0.6), normalise(right, 0.6)


def park_ambience(seed=24):
    dur = 16.0
    r = rng(seed)
    n = int(dur * SR)
    leaves = band(coloured(n, r, -2), 800, 7000) * (0.3 + 0.7 * np.abs(band(white(n, r), 0, 0.4)) * 6)
    out = normalise(leaves) * 0.15 + normalise(band(coloured(n, r, -5), 30, 300)) * 0.12
    for i in range(14):
        place(out, bird_chirp(seed + i * 3) * r.uniform(0.15, 0.4), r.uniform(0, dur - 1.3))
    return normalise(loopify(out, 1.0), 0.55)



def grill_sizzle(seed=26):
    dur = 5.0
    r = rng(seed)
    n = int(dur * SR)
    out = band(white(n, r), 2500, 12000) * 0.25
    for _ in range(int(dur * 120)):
        m = int(0.004 * SR)
        place(out, band(white(m, r), 1500, 9000) * np.hanning(m) * r.uniform(0.2, 1.0), r.uniform(0, dur - 0.01))
    return normalise(loopify(out, 0.3), 0.5)


def cash_register(seed=27):
    out = np.zeros(int(1.4 * SR))
    place(out, modal(1.0, [(1975, 1, 0.5), (1975 * 2.03, 0.3, 0.2)], 0.3, seed), 0.0)
    r = rng(seed)
    n = int(0.35 * SR)
    drawer = band(white(n, r), 200, 2500) * env_adsr(n, 0.01, 0.1, 0.5, 0.2, 0.5) * 0.5
    place(out, drawer, 0.25)
    place(out, door_close(seed) * 0.4, 0.55)
    return normalise(out, 0.7)


def ui_notification(seed=28):
    return chime([880.0, 1318.5], 0.11, 0.35, seed)


def ui_accept(seed=29):
    return chime([659.3, 880.0, 1174.7], 0.08, 0.3, seed)


def ui_reject(seed=30):
    return chime([587.3, 440.0], 0.12, 0.25, seed)


def delivery_complete(seed=31):
    return chime([523.3, 659.3, 784.0, 1046.5], 0.09, 0.5, seed)


def wind(seed=32):
    dur = 10.0
    r = rng(seed)
    n = int(dur * SR)
    gust = 0.4 + 0.6 * np.abs(band(white(n, r), 0, 0.3)) * 8
    x = band(coloured(n, r, -4), 80, 1500) * np.minimum(gust, 1.5)
    x = resonance(x, 420 + 0 * x[:1], 8, 1.0)
    return normalise(loopify(x, 1.0), 0.5)



# --------------------------------------------------------------------------- phone & shop UI
# Loudness targets (short-term RMS, dBFS): soft taps/clicks -27..-25, UI cues -23..-21,
# rewards -19..-17, world one-shots -24..-18, loops -28..-20. CityAudio's play_ui() default
# (-4 dB) and the bus trims sit on top of these.

def phone_raise(seed=40):
    # Phone sliding out of a pocket: fabric swish rising in pitch, a little rustle, then the
    # soft tick of the phone settling in the hand.
    r = rng(seed)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    noise = coloured(n, r, -2)
    swish = tv_filter(noise, lambda tc, f: log_bell(f, 450 * (2600 / 450) ** min(max(tc, 0) / 0.3, 1), 0.9))
    e = np.where(t < 0.28, (t / 0.28) ** 1.6, np.exp(-(t - 0.28) / 0.05))
    rustle = crackle(n, r, 220, 1500, 6000) * e * 0.35
    tick = np.zeros(n)
    place(tick, struck(0.05, 2300, [(1, 1, 0.006), (1.8, 0.4, 0.004)], 0.0005, seed) * 0.18, 0.31)
    return level(fade(soften(swish * e + rustle + tick, 6000)), -25)


def phone_lower(seed=41):
    # Back into the pocket: falling swish and a soft fabric thump at the end.
    r = rng(seed)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    noise = coloured(n, r, -2)
    swish = tv_filter(noise, lambda tc, f: log_bell(f, 2400 * (550 / 2400) ** min(max(tc, 0) / 0.3, 1), 0.9))
    e = np.where(t < 0.06, t / 0.06, np.exp(-(t - 0.06) / 0.12))
    rustle = crackle(n, r, 160, 1200, 5000) * e * 0.3
    thump = np.zeros(n)
    m = int(0.12 * SR)
    place(thump, band(white(m, r), 60, 320) * exp_decay(m, 0.025) * 0.45, 0.3)
    return level(fade(soften(swish * e + rustle + thump, 5500)), -25)


def phone_tap(seed=42):
    # Soft glassy UI tap: a tiny pitched blip with a muted fingertip transient.
    r = rng(seed)
    blip = chirp_tone(1250, 950, 0.09, 0.016, ((1, 1.0), (2, 0.12)))
    n = len(blip)
    tip = band(white(n, r), 1800, 6000) * exp_decay(n, 0.0018) * 0.25
    return level(fade(soften(blip + tip, 7000), 0.0008, 0.02), -27)


def phone_unlock(seed=43):
    # Click, an upward glassy swish and two mellow notes (G5 -> D6).
    r = rng(seed)
    out = np.zeros(int(0.9 * SR))
    place(out, struck(0.04, 1900, [(1, 1, 0.005), (2.2, 0.4, 0.003)], 0.0005, seed) * 0.35, 0.0)
    m = int(0.22 * SR)
    sw = tv_filter(coloured(m, r, -1), lambda tc, f: log_bell(f, 900 * (4200 / 900) ** min(max(tc, 0) / 0.2, 1), 0.7))
    place(out, sw * env_shape(m, 0.12, 0.08) * 0.35, 0.02)
    place(out, bell(784.0, 0.7, 0.35, seed) * 0.55, 0.12)
    place(out, bell(1174.7, 0.7, 0.4, seed + 1) * 0.5, 0.22)
    return level(fade(soften(out, 6500)), -22)


def app_open(seed=44):
    # Whoosh up into a quick bright arpeggio (C6 E6 G6).
    r = rng(seed)
    out = np.zeros(int(1.0 * SR))
    m = int(0.28 * SR)
    sw = tv_filter(coloured(m, r, -2), lambda tc, f: log_bell(f, 350 * (3200 / 350) ** min(max(tc, 0) / 0.25, 1), 0.8))
    place(out, sw * env_shape(m, 0.2, 0.08) * 0.6, 0.0)
    for i, f in enumerate((1046.5, 1318.5, 1568.0)):
        place(out, marimba(f, 0.7, 0.8, seed + i) * (0.55 - i * 0.08), 0.17 + i * 0.05)
    return level(fade(soften(out, 6000)), -22)


def app_locked(seed=45):
    # Soft "bzz-bzz" denial: two short muted low buzzes, no harsh edges.
    out = np.zeros(int(0.42 * SR))
    for at in (0.0, 0.17):
        n = int(0.11 * SR)
        f0 = np.full(n, 196.0) * np.linspace(1.0, 0.97, n)
        buzz = band(harmonic_source(f0, 2000), 120, 1100)
        place(out, buzz * env_shape(n, 0.006, 0.03), at)
    return level(fade(out), -25)


def notify_order(seed=46):
    # New order: warm marimba G5 B5 D6 with a soft bell bloom on top (distinct from ui_notification).
    out = np.zeros(int(1.5 * SR))
    for i, (at, f) in enumerate(((0.0, 784.0), (0.1, 987.8), (0.2, 1174.7))):
        place(out, marimba(f, 1.2, 1.0 + i * 0.4, seed + i) * 0.6, at)
    place(out, bell(1568.0, 1.2, 0.6, seed + 5) * 0.12, 0.2)
    return level(fade(soften(reverb(out, 0.5, 0.15, seed), 6500)), -19)


def kiosk_click(seed=47):
    # Computer key press and release (plastic click with a small desk thump).
    r = rng(seed)
    out = np.zeros(int(0.16 * SR))

    def click(amp, f):
        m = int(0.03 * SR)
        body = struck(0.03, f, [(1, 1, 0.003), (1.62, 0.4, 0.002), (0.44, 0.5, 0.005)], 0.0003, seed)
        tr = band(white(m, r), 1500, 8000) * exp_decay(m, 0.0012) * 0.5
        thud = band(white(m, r), 80, 400) * exp_decay(m, 0.006) * 0.4
        return (body + tr + thud) * amp

    place(out, click(1.0, 3200), 0.0)
    place(out, click(0.45, 3500), 0.075)
    return level(fade(soften(out, 7500), 0.0005, 0.02), -26)


def cart_add(seed=48):
    # Light upward "pop" with a small sparkle.
    out = np.zeros(int(0.3 * SR))
    pop = chirp_tone(380, 980, 0.12, 0.045, ((1, 1.0), (2, 0.15)))
    place(out, pop, 0.0)
    place(out, struck(0.2, 1760, [(1, 1, 0.07), (2, 0.2, 0.03)], 0.001, seed) * 0.25, 0.04)
    return level(fade(soften(out, 7000), 0.001), -22)


def cart_remove(seed=49):
    # Downward pop, a touch quieter than cart_add.
    r = rng(seed)
    out = np.zeros(int(0.3 * SR))
    place(out, chirp_tone(900, 330, 0.14, 0.05, ((1, 1.0), (2, 0.1))), 0.0)
    m = int(0.08 * SR)
    place(out, band(white(m, r), 80, 400) * exp_decay(m, 0.015) * 0.3, 0.05)
    return level(fade(soften(out, 6500), 0.001), -24)


def purchase_complete(seed=50):
    # Receipt printer (three stepper bursts), paper tear, then a gentle till bell.
    r = rng(seed)
    out = np.zeros(int(1.9 * SR))
    for i, at in enumerate((0.0, 0.14, 0.28)):
        n = int(0.1 * SR)
        tt = np.arange(n) / SR
        rate = 880 + 40 * i
        pulse = np.exp(-((tt * rate) % 1.0) * 6)
        motor = band(pulse - pulse.mean(), 500, 3500) + band(white(n, r), 1000, 4000) * 0.25
        place(out, motor * env_shape(n, 0.008, 0.02) * 0.4, at)
    m = int(0.14 * SR)
    tear = crackle(m, r, 2500, 900, 6000, 0.0008) + band(white(m, r), 1500, 5000) * 0.3
    place(out, tear * env_shape(m, 0.01, 0.05) * 0.8, 0.46)
    place(out, bell(1975.0, 1.3, 0.55, seed) * 0.5, 0.66)
    place(out, bell(1975.0 * 1.5, 1.0, 0.4, seed + 1) * 0.15, 0.68)
    return level(fade(soften(out, 6500)), -20)


def item_pickup(seed=51):
    # Paper bag rustle as an item is lifted.
    r = rng(seed)
    n = int(0.45 * SR)
    e = env_shape(n, 0.06, 0.25, 1.5)
    rustle = crackle(n, r, 1800, 1000, 6000, 0.001) * e
    whoosh = band(coloured(n, r, -2), 300, 1500) * e * 0.25
    return level(fade(soften(rustle + whoosh, 6000)), -24)


def package_drop(seed=52):
    # Paper/cardboard parcel landing on pavement: soft thump, box resonance, crinkle, tiny bounce.
    r = rng(seed)
    out = np.zeros(int(0.6 * SR))
    n = int(0.3 * SR)
    t = np.arange(n) / SR

    def thump(amp):
        low = band(white(n, r), 50, 300) * exp_decay(n, 0.045) + np.sin(2 * np.pi * 85 * t) * exp_decay(n, 0.06) * 0.6
        box = resonance(band(white(n, r), 200, 1500), 420, 3, 2) * exp_decay(n, 0.018) * 0.35
        a = int(0.002 * SR)
        s = low + box
        s[:a] *= np.linspace(0, 1, a)
        return s * amp

    place(out, thump(1.0), 0.0)
    place(out, thump(0.22), 0.13)
    m = int(0.18 * SR)
    place(out, crackle(m, r, 900, 1200, 5000) * env_shape(m, 0.005, 0.12) * 0.25, 0.02)
    return level(fade(soften(out, 5000)), -20)


def package_place(seed=53):
    # Bag set into a compartment: muffled thud and nylon rustle.
    r = rng(seed)
    out = np.zeros(int(0.55 * SR))
    m = int(0.25 * SR)
    thud = band(white(m, r), 90, 500) * exp_decay(m, 0.05)
    thud[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    place(out, thud * 0.8, 0.05)
    n = int(0.4 * SR)
    nylon = (band(coloured(n, r, -1), 700, 3500) * 0.5 + crackle(n, r, 500, 900, 4500)) * env_shape(n, 0.05, 0.25)
    place(out, nylon * 0.45, 0.0)
    return level(fade(soften(out, 5500)), -23)


def bag_zip(seed=54):
    # Backpack zip: teeth clicks speeding up then easing off, friction hiss, tab clack.
    r = rng(seed)
    dur = 0.62
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    rate = 55 + 110 * np.sin(np.pi * np.clip(t / 0.5, 0, 1))
    pos = np.nonzero(np.diff(np.floor(np.cumsum(rate) / SR)) > 0)[0]
    tooth = resonance(band(white(64, r), 2000, 7000), 3400, 4, 2) * np.hanning(64)
    for p in pos:
        if p / SR < 0.5:
            place(out, tooth * r.uniform(0.5, 1.0) * (0.6 + 0.4 * np.sin(np.pi * p / SR / 0.5)), p / SR)
    hiss = band(white(n, r), 1500, 6000) * np.where(t < 0.5, np.sin(np.pi * t / 0.5), 0) * 0.08
    place(out, struck(0.06, 1800, [(1, 1, 0.01), (1.85, 0.5, 0.006)], 0.0005, seed) * 0.35, 0.52)
    return level(fade(soften(out + hiss, 6500)), -23)


def door_knock(seed=55):
    # Three knuckle knocks on a wooden front door.
    r = rng(seed)
    out = np.zeros(int(0.9 * SR))
    for i, (at, amp) in enumerate(((0.0, 1.0), (0.21, 0.88), (0.41, 0.95))):
        k = r.uniform(0.97, 1.03)
        n = int(0.2 * SR)
        wood = struck(0.2, 190 * k, [(1, 1, 0.05), (2.16, 0.7, 0.04), (4.1, 0.45, 0.025), (7.1, 0.25, 0.015), (12.1, 0.08, 0.008)], 0.0006, seed + i)
        knuckle = band(white(n, r), 800, 4000) * exp_decay(n, 0.003) * 0.35
        low = band(white(n, r), 60, 220) * exp_decay(n, 0.03) * 0.4
        place(out, (wood + knuckle + low) * amp, at)
    return level(fade(soften(reverb(out, 0.35, 0.12, seed), 6000)), -18)


def doorbell(seed=56):
    # Two-tone "ding-dong" (E5 then C5) chime.
    out = np.zeros(int(2.6 * SR))
    place(out, bell(659.3, 2.0, 1.2, seed) * 0.8, 0.0)
    place(out, bell(523.3, 2.0, 1.4, seed + 1) * 0.8, 0.55)
    return level(fade(soften(reverb(out, 0.6, 0.15, seed), 6000), 0.002, 0.3), -19)


def door_open(seed=7):
    # Residential door: handle and latch click, weather-strip rub, airy swing, faint hinge creak.
    r = rng(seed)
    out = np.zeros(int(1.2 * SR))
    place(out, struck(0.08, 1500, [(1, 1, 0.012), (2.06, 0.5, 0.008), (3.3, 0.2, 0.005)], 0.0005, seed) * 0.5, 0.0)
    place(out, struck(0.06, 2100, [(1, 1, 0.008), (1.7, 0.4, 0.005)], 0.0005, seed + 1) * 0.35, 0.09)
    n = int(0.8 * SR)
    tt = np.arange(n) / SR
    swing = band(coloured(n, r, -3), 120, 900) * env_shape(n, 0.25, 0.4) * 0.35
    rub = band(white(n, r), 500, 2500) * env_shape(n, 0.05, 0.3) * np.exp(-tt / 0.25) * 0.15
    f = 105 + 60 * tt / tt[-1]
    pulses = np.exp(-((np.cumsum(f) / SR) % 1.0) * 14)
    creak = sum(resonance(pulses - pulses.mean(), fc, 8, 3) for fc in (720, 1450)) / 2
    creak = band(creak, 300, 3000) * env_shape(n, 0.15, 0.3) * 0.12
    place(out, swing + rub + creak, 0.12)
    return level(fade(soften(reverb(out, 0.3, 0.1, seed), 5500)), -21)


def photo_shutter(seed=57):
    # Phone camera shutter: "ka-chik".
    r = rng(seed)
    out = np.zeros(int(0.3 * SR))

    def blade(amp, f):
        m = int(0.05 * SR)
        s = band(white(m, r), 1200, 7000) * exp_decay(m, 0.004)
        s += struck(0.05, f, [(1, 0.6, 0.01), (1.6, 0.3, 0.006)], 0.0003, seed)
        s += band(white(m, r), 150, 600) * exp_decay(m, 0.01) * 0.4
        return s * amp

    place(out, blade(1.0, 2600), 0.0)
    m = int(0.07 * SR)
    place(out, band(white(m, r), 800, 3000) * np.hanning(m) * 0.06, 0.012)
    place(out, blade(0.8, 2900), 0.085)
    return level(fade(soften(out, 7500), 0.0005, 0.02), -21)


def delivery_success(seed=58):
    # Short positive jingle: G5 -> C6, then a C-major bloom with a warm low pad.
    out = np.zeros(int(1.6 * SR))
    place(out, marimba(784.0, 0.6, 0.6, seed) * 0.5, 0.0)
    place(out, marimba(1046.5, 0.6, 0.6, seed + 1) * 0.5, 0.11)
    for i, f in enumerate((784.0, 1046.5, 1318.5)):
        place(out, bell(f, 1.3, 0.6, seed + 2 + i) * 0.3, 0.22 + i * 0.012)
    n = int(1.2 * SR)
    tt = np.arange(n) / SR
    pad = (np.sin(2 * np.pi * 261.6 * tt) + 0.3 * np.sin(2 * np.pi * 392 * tt)) * env_shape(n, 0.15, 0.7) * 0.12
    place(out, pad, 0.2)
    return level(fade(soften(reverb(out, 0.6, 0.15, seed), 6500), 0.001, 0.2), -19)


def customer_thanks(seed=59):
    # Friendly hummed "mm-HM!": nasal formant voice, second syllable higher and falling.
    r = rng(seed)
    out = np.zeros(int(0.8 * SR))
    for at, dur, f_a, f_b, amp in ((0.0, 0.2, 188, 200, 0.7), (0.27, 0.34, 238, 182, 1.0)):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f0 = (f_a * (f_b / f_a) ** (tt / dur)) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * tt))
        src = harmonic_source(f0, 3500, 1.3)
        v = resonance(src, 260, 4, 6)
        v = resonance(v, 1000, 5, 1.2)
        v = resonance(v, 2300, 6, 0.5)
        v = band(v, 90, 2600)
        e = env_shape(n, 0.03, 0.08)
        if amp == 1.0:
            breath = band(white(n, r), 500, 2500) * np.exp(-tt / 0.025) * 0.06
            v = v + breath / max(np.max(np.abs(breath)), 1e-9) * np.max(np.abs(v)) * 0.12
        place(out, v * e * amp, at)
    return level(fade(soften(out, 4500)), -21)


def coins(seed=60):
    # A few coins dropping into a palm: small inharmonic clinks, softened top.
    r = rng(seed)
    out = np.zeros(int(1.0 * SR))
    m = int(0.1 * SR)
    place(out, band(white(m, r), 100, 500) * exp_decay(m, 0.03) * 0.25, 0.0)
    for i, at in enumerate((0.0, 0.07, 0.13, 0.21, 0.26, 0.37)):
        f = r.uniform(1900, 3200)
        clink = struck(0.45, f, [(1, 1, 0.12), (1.47, 0.6, 0.09), (2.09, 0.35, 0.06), (2.56, 0.2, 0.045), (3.3, 0.08, 0.03)], 0.0004, seed + i)
        place(out, clink * (1.0 - i * 0.12) * r.uniform(0.7, 1.0), at)
    return level(fade(soften(out, 6500), 0.0005, 0.1), -21)


def step_complete(seed=61):
    # Tutorial task ticked: quick "tick-ding" pluck up a fifth.
    out = np.zeros(int(0.7 * SR))
    place(out, marimba(1046.5, 0.6, 0.5, seed) * 0.6, 0.0)
    place(out, marimba(1568.0, 0.6, 0.6, seed + 1) * 0.5, 0.07)
    return level(fade(soften(out, 6500), 0.001, 0.1), -21)


def brass(f, dur, seed=0):
    """Soft synth brass: additive tone that brightens as it swells, gentle vibrato."""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    swell = 1 - np.exp(-tt / 0.05)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * tt) * np.clip((tt - 0.15) / 0.2, 0, 1)
    ph = 2 * np.pi * np.cumsum(np.full(n, f) * vib) / SR
    out = np.zeros(n)
    for k in range(1, int(4500 / f) + 1):
        out += np.sin(k * ph) / k * np.exp(-k * (0.5 - 0.25 * swell))
    return out * env_shape(n, 0.025, min(0.25, dur * 0.4))


def mission_complete(seed=62):
    # Short fanfare: G4 C5 E5 pick-up into a held C-major chord, soft timpani and a bell glint.
    r = rng(seed)
    out = np.zeros(int(2.8 * SR))
    for at, f in ((0.0, 392.0), (0.15, 523.3), (0.30, 659.3)):
        place(out, brass(f, 0.16, seed) * 0.55, at)
    for f in (261.6, 523.3, 659.3, 784.0, 1046.5):
        place(out, brass(f, 1.5, seed) * (0.32 if f > 300 else 0.25), 0.45)
    n = int(0.8 * SR)
    tt = np.arange(n) / SR
    timp = np.sin(2 * np.pi * np.cumsum(98 - 6 * tt / tt[-1]) / SR) * np.exp(-tt / 0.35) + band(white(n, r), 60, 400) * np.exp(-tt / 0.03) * 0.5
    timp[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    place(out, timp * 0.5, 0.45)
    place(out, bell(2093.0, 1.5, 0.6, seed) * 0.08, 0.47)
    return level(fade(soften(reverb(out, 1.1, 0.2, seed), 6000), 0.001, 0.4), -17)


# --------------------------------------------------------------------------- traffic
# Engine loops are built from integer numbers of firing periods and FFT (circular) filters, so
# they are exactly periodic: the loop seam is sample-continuous with no crossfade.

def car_engine(seed=63):
    # Four-cylinder petrol at ~900 rpm (30 Hz firing); CityAudio pitches it with speed.
    r = rng(seed)
    n = 1470 * 90  # 3.0 s, 90 firing periods
    t = np.arange(n) / SR
    firing = SR / 1470
    tp = t * firing + 0.5  # seam falls mid-period, between firings
    k, phase = np.floor(tp).astype(int), tp % 1.0
    pulses = np.exp(-phase * 7) * np.where(k % 2 == 0, 1.0, 0.93)
    exhaust = band(pulses - pulses.mean(), 28, 700)
    rumble = band(coloured(n, r, -4), 30, 450) * (0.6 + 0.4 * pulses)
    intake = band(white(n, r), 300, 2000) * pulses * 0.12
    hum = 0.25 * np.sin(2 * np.pi * 60 * t) + 0.12 * np.sin(2 * np.pi * 120 * t) + 0.08 * np.sin(2 * np.pi * 90 * t)
    x = normalise(exhaust) + normalise(rumble) * 0.45 + normalise(intake) * 0.15 + hum * 0.6
    x = soft_clip(normalise(x), 1.4)
    return level(soften(x, 2500), -20)


def truck_engine(seed=64):
    # Heavy six-cylinder diesel (24.5 Hz firing) with combustion knock: trucks, vans and coaches.
    r = rng(seed)
    n = 1800 * 96  # ~3.9 s, 96 firing periods (16 full cycles of six)
    t = np.arange(n) / SR
    firing = SR / 1800
    tp = t * firing + 0.5  # seam falls mid-period, between firings
    k, phase = np.floor(tp).astype(int), tp % 1.0
    cyl = np.array([1.0, 0.9, 0.96, 0.88, 0.97, 0.92])[k % 6]
    pulses = np.exp(-phase * 8) * cyl
    body = band(pulses * (1 + 0.5 * band(coloured(n, r, -3), 20, 900)) - pulses.mean(), 22, 800)
    knock = band(white(n, r), 1200, 3500) * np.exp(-phase * 35) * cyl
    hum = 0.3 * np.sin(2 * np.pi * firing * t) + 0.2 * np.sin(2 * np.pi * firing * 2 * t) + 0.15 * np.sin(2 * np.pi * firing / 3 * t)
    x = normalise(body) + normalise(knock) * 0.12 + hum * 0.5
    x = soft_clip(normalise(x), 1.6)
    return level(soften(x, 2800), -19)


def horn_honk(seed=65):
    # Car horn double tap "beep-beep": two horn tones (415 + 520 Hz) through a body resonance.
    out = np.zeros(int(0.55 * SR))
    for at, dur in ((0.0, 0.12), (0.2, 0.2)):
        n = int(dur * SR)
        tone = sum(harmonic_source(np.full(n, f) * np.linspace(0.985, 1.0, n) ** 0.2, 4000) * a for f, a in ((415.0, 0.6), (520.0, 0.5)))
        tone = resonance(band(tone, 250, 3200), 1000, 2, 1.5)
        place(out, tone * env_shape(n, 0.008, 0.025), at)
    return level(fade(soften(out, 3500)), -18)


def truck_brake_squeal(seed=66):
    # Heavy-vehicle drum brakes squealing as it pulls up (moderate, wavering, not piercing).
    r = rng(seed)
    t = t_axis(1.4)
    f = 980 + 25 * np.sin(2 * np.pi * 5.5 * t) - 60 * t
    ph = 2 * np.pi * np.cumsum(f) / SR
    squeal = (np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)) * (1 + 0.3 * np.sin(2 * np.pi * 7 * t))
    e = env_shape(len(t), 0.18, 0.35) * (1 - 0.4 * t / t[-1])
    scrub = band(white(len(t), r), 200, 1500) * 0.35
    return level(fade(soften((squeal * 0.5 + scrub) * e, 4000)), -24)


def tyre_wet(seed=67):
    # Tyres on a wet road: spray hiss with a gentle swash, low road rumble (loop).
    r = rng(seed)
    n = 4 * SR
    hiss = resonance(band(coloured(n, r, -1.5), 400, 8000), 2200, 1.5, 1.5)
    mod = band(white(n, r), 0, 6)
    mod = 0.75 + 0.25 * mod / np.max(np.abs(mod))
    low = band(coloured(n, r, -4), 60, 300)
    x = normalise(hiss) * mod + normalise(low) * 0.25
    return level(soften(x, 6000), -22)


def signal_tick(f, seed):
    """Woody click of a pedestrian push-button signal."""
    r = rng(seed)
    m = int(0.05 * SR)
    s = struck(0.05, f, [(1, 1, 0.008), (2.0, 0.5, 0.005), (3.3, 0.25, 0.003)], 0.0004, seed)
    s += band(white(m, r), 1500, 5000) * exp_decay(m, 0.001) * 0.25
    return s


def ped_signal_walk(seed=68):
    # WALK: rapid tick, 10 per second (loop, 1 s).
    out = np.zeros(SR)
    for i in range(10):
        cplace(out, signal_tick(880, seed + i % 2), i / 10 + 0.03)
    return level(soften(out, 6000), -21)


def ped_signal_wait(seed=69):
    # WAIT / DON'T WALK: slow locator tick, one per second (loop, 2 s).
    out = np.zeros(2 * SR)
    for i in range(2):
        cplace(out, signal_tick(660, seed) * 0.8, i + 0.3)
    return level(soften(out, 5000), -26)


# --------------------------------------------------------------------------- shops & restaurants

def shop_door_chime(seed=70):
    # Brass shop bell on a spring, jingling as the door opens.
    r = rng(seed)
    out = np.zeros(int(1.6 * SR))
    for i, (at, amp) in enumerate(((0.0, 1.0), (0.09, 0.7), (0.2, 0.5), (0.33, 0.35), (0.5, 0.2))):
        f = 1650 * r.uniform(0.99, 1.01)
        place(out, struck(1.1, f, [(1, 1, 0.5), (2.32, 0.4, 0.25), (3.6, 0.15, 0.15), (1.004, 0.5, 0.5)], 0.0008, seed + i) * amp, at)
    return level(fade(soften(reverb(out, 0.4, 0.12, seed), 6500), 0.001, 0.25), -20)


def cutlery_clink(seed=71):
    # Fork tapping a plate twice.
    r = rng(seed)
    out = np.zeros(int(0.45 * SR))
    for i, (at, amp) in enumerate(((0.0, 1.0), (0.11, 0.6))):
        f = r.uniform(2600, 3500)
        s = struck(0.3, f, [(1, 1, 0.06), (2.3, 0.35, 0.03), (3.1, 0.15, 0.02)], 0.0004, seed + i)
        s += struck(0.3, 1500, [(1, 0.3, 0.04), (1.6, 0.2, 0.03)], 0.0004, seed + i)
        place(out, s * amp, at)
    return level(fade(soften(out, 6500), 0.0005, 0.05), -24)


def plate_clink(seed=72):
    # Ceramic plate set down on a table.
    r = rng(seed)
    out = np.zeros(int(0.5 * SR))
    m = int(0.1 * SR)
    place(out, band(white(m, r), 150, 600) * exp_decay(m, 0.02) * 0.6, 0.0)
    modes = [(1, 1, 0.08), (1.64, 0.6, 0.06), (2.43, 0.35, 0.04), (3.47, 0.12, 0.025)]
    place(out, struck(0.4, 1180, modes, 0.0005, seed) * 0.6, 0.0)
    place(out, struck(0.4, 1240, modes, 0.0005, seed + 1) * 0.25, 0.03)
    return level(fade(soften(out, 6000), 0.0005, 0.05), -23)


def pan_clank(seed=73):
    # Kitchen pan knocked on a hob.
    r = rng(seed)
    out = np.zeros(int(0.7 * SR))
    modes = [(1, 1, 0.25), (2.69, 0.6, 0.15), (4.88, 0.35, 0.1), (7.86, 0.15, 0.06)]
    place(out, struck(0.6, 420, modes, 0.0005, seed), 0.0)
    place(out, struck(0.6, 430, modes, 0.0005, seed + 1) * 0.45, 0.08)
    m = int(0.05 * SR)
    place(out, band(white(m, r), 1000, 5000) * exp_decay(m, 0.003) * 0.3, 0.0)
    return level(fade(soften(reverb(out, 0.4, 0.15, seed), 5500), 0.0005, 0.1), -24)


def babble_voice(n, r, f0):
    """One indistinct talker: glottal source shaped by random vowel formants per syllable."""
    vowels = ((730, 1090, 2440), (530, 1840, 2480), (300, 2200, 2900), (570, 840, 2410), (440, 1020, 2240))
    out = np.zeros(n)
    t = r.uniform(0, n / SR)
    end = t + n / SR
    while t < end:
        if r.random() < 0.18:
            t += r.uniform(0.3, 1.4)
            continue
        d = r.uniform(0.12, 0.28)
        m = int(d * SR)
        tilt = np.linspace(1, -1, m) * r.uniform(-0.08, 0.08)
        f = f0 * r.uniform(0.92, 1.1) * (1 + tilt)
        src = harmonic_source(f, 3200, 1.2)
        fm = vowels[r.integers(len(vowels))]
        syl = fft_filter(src, lambda fr: sum(a / (1 + ((fr - fc) / (fc / 6)) ** 2) for fc, a in zip(fm, (1.0, 0.6, 0.25))))
        cplace(out, syl * np.hanning(m) * r.uniform(0.4, 1.0), t)
        t += d + r.uniform(0.02, 0.1)
    return out


def restaurant_ambience(seed=25):
    # Busy dining room (loop): a dozen indistinct talkers in a reverberant room, cutlery and
    # plates now and then, a low room tone. Circular synthesis: the loop seam is continuous.
    r = rng(seed)
    n = 14 * SR
    talk = np.zeros(n)
    for i in range(12):
        f0 = r.choice([r.uniform(100, 135), r.uniform(185, 235)])
        v = babble_voice(n, r, f0)
        talk += v / max(np.max(np.abs(v)), 1e-9) * r.uniform(0.35, 1.0)
    talk = band(talk, 120, 3000)
    out = normalise(talk) * 0.8
    for _ in range(int(14 * 1.4)):
        s = cutlery_clink(int(r.integers(1e6))) if r.random() < 0.7 else plate_clink(int(r.integers(1e6)))
        cplace(out, s / max(np.max(np.abs(s)), 1e-9) * r.uniform(0.04, 0.14), r.uniform(0, 14))
    out += normalise(band(coloured(n, r, -4), 40, 400)) * 0.12
    out = reverb(out, 0.7, 0.35, seed, 4500, circular=True)
    return level(soften(out, 5500), -22)


# --------------------------------------------------------------------------- nature & weather

def songbird_trill(seed=74):
    # Wren-like rapid trill ending in three slower notes.
    r = rng(seed)
    out = np.zeros(int(1.5 * SR))
    at = 0.0
    while at < 0.7:
        place(out, chirp_tone(r.uniform(4000, 4400), r.uniform(3000, 3300), 0.035) * np.sin(np.linspace(0, np.pi, int(0.035 * SR))) ** 2, at)
        at += 1 / 18
    for i in range(3):
        place(out, chirp_tone(r.uniform(2700, 3000), r.uniform(3400, 3700), 0.08) * np.sin(np.linspace(0, np.pi, int(0.08 * SR))) ** 2 * 0.8, 0.8 + i * 0.16)
    return level(fade(soften(out, 6000)), -24)


def blackbird_song(seed=75):
    # Mellow fluting phrase (dawn and dusk).
    r = rng(seed)
    out = np.zeros(int(2.2 * SR))
    at = 0.0
    for i in range(5):
        d = r.uniform(0.09, 0.22)
        m = int(d * SR)
        tt = np.arange(m) / SR
        fc = r.uniform(1800, 2800)
        f = fc + r.uniform(-400, 400) * tt / d + 40 * np.sin(2 * np.pi * 25 * tt)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.1 * np.sin(4 * np.pi * np.cumsum(f) / SR)
        place(out, s * np.sin(np.pi * tt / d) ** 1.5 * r.uniform(0.6, 1.0), at)
        at += d + r.uniform(0.04, 0.09)
    for i in range(4):
        place(out, chirp_tone(3500, 3900, 0.03) * np.hanning(int(0.03 * SR)) * 0.3, at + 0.05 + i * 0.05)
    return level(fade(soften(reverb(out, 0.6, 0.15, seed), 5500)), -24)


def owl_hoot(seed=76):
    # Tawny owl at night: "hoo ... hu-hoooo".
    r = rng(seed)
    out = np.zeros(int(2.6 * SR))
    for at, dur, fa, fb, amp in ((0.0, 0.45, 430, 405, 0.8), (1.0, 0.12, 420, 415, 0.5), (1.2, 0.9, 445, 395, 1.0)):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f = fa + (fb - fa) * tt / dur + 6 * np.sin(2 * np.pi * 7 * tt) * (dur > 0.5)
        ph = 2 * np.pi * np.cumsum(f) / SR
        v = np.sin(ph) + 0.12 * np.sin(2 * ph) + band(white(n, r), 300, 1500) * 0.05
        place(out, v * env_shape(n, min(0.06, dur * 0.3), min(0.2, dur * 0.5)) * amp, at)
    return level(fade(soften(reverb(out, 0.8, 0.25, seed), 4000)), -24)


def crickets(seed=77):
    # Summer-night crickets in the grass (loop, 6 s, periodic).
    r = rng(seed)
    n = 6 * SR
    out = np.zeros(n)
    for c in range(5):
        fc = r.uniform(3200, 3900)
        amp = r.uniform(0.25, 1.0)
        pulses = int(r.integers(3, 5))
        period = 6.0 / int(r.integers(10, 18))
        m = int(0.016 * SR)
        tt = np.arange(m) / SR
        pulse = np.sin(2 * np.pi * fc * tt) * np.sin(np.pi * tt / tt[-1]) ** 2
        start = r.uniform(0, 6)
        for k in range(int(round(6.0 / period))):
            for p in range(pulses):
                cplace(out, pulse * amp * r.uniform(0.8, 1.0), start + k * period + p * 0.033)
    out += band(white(n, r), 2000, 5000) * 0.01
    return level(soften(out, 4500), -29)


def night_city_hum(seed=78):
    # Distant city at night: low rumble, far traffic wash, a faint mains hum (stereo loop).
    r = rng(seed)
    n = 20 * SR
    t = np.arange(n) / SR

    def side(rr):
        rumble = band(coloured(n, rr, -5), 25, 400)
        swell = band(white(n, rr), 0, 0.12)
        swell = 0.7 + 0.3 * swell / np.max(np.abs(swell))
        wash = band(coloured(n, rr, -3), 200, 1500)
        return normalise(rumble) * swell + normalise(wash) * 0.12 * swell

    common = side(r)
    left = common * 0.7 + side(rng(seed + 1)) * 0.3
    right = common * 0.7 + side(rng(seed + 2)) * 0.3
    for at, gl, gr in ((6.0, 0.12, 0.07), (15.0, 0.07, 0.12)):
        p = band(car_pass(seed + int(at)), 60, 1200)
        cplace(left, p * gl, at)
        cplace(right, p * gr, at + 0.01)
    hum = 0.015 * (np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 100 * t))
    left, right = soften(left + hum, 3000), soften(right + hum, 3000)
    return level(left, -26, right=right)


def wind_soft(seed=79):
    # Gentle breeze with slow swells and faint leaf rustle (stereo loop).
    r = rng(seed)
    n = 12 * SR

    def side(rr, swell):
        air = resonance(band(coloured(n, rr, -3), 100, 2500), 600, 6, 0.5)
        leaves = band(crackle(n, rr, 600, 1500, 5000), 1500, 5000)
        return normalise(air) * swell + normalise(leaves) * 0.15 * swell ** 2

    s = band(white(n, r), 0, 0.12)
    swell = 0.45 + 0.55 * (s - s.min()) / (s.max() - s.min())
    left = side(rng(seed + 1), swell)
    right = side(rng(seed + 2), np.roll(swell, int(0.4 * SR)))
    return level(soften(left, 5000), -26, right=soften(right, 5000))


def rain_layer(n, r, drops_per_s, roar):
    wash = soften(band(coloured(n, r, -1.5), 300, 9000), 6000)
    out = normalise(wash) * 0.5
    drops = crackle(n, r, drops_per_s, 1000, 6000, 0.0008)
    out += normalise(drops) * 0.35
    patter = band(crackle(n, r, drops_per_s * 0.3, 200, 1200, 0.003), 200, 1200)
    out += normalise(patter) * 0.3
    for _ in range(int(n / SR * 2.5)):
        f = r.uniform(1200, 2600)
        plip = chirp_tone(f, f * 1.6, 0.03, 0.012)
        cplace(out, plip * r.uniform(0.04, 0.12), r.uniform(0, n / SR))
    if roar:
        out += normalise(band(coloured(n, r, -4), 80, 600)) * 0.4 * roar
    return out


def rain(seed=33):
    # Steady rain on pavement and leaves: soft wash, fine drops, low patter, the odd drip
    # (stereo loop, circular synthesis: no seam).
    n = 10 * SR
    common = rain_layer(n, rng(seed), 350, 0.0)
    left = common * 0.6 + rain_layer(n, rng(seed + 1), 350, 0.0) * 0.4
    right = common * 0.6 + rain_layer(n, rng(seed + 2), 350, 0.0) * 0.4
    return level(left, -22, right=right)


def rain_heavy(seed=80):
    # Downpour layer: dense drops, low roar and gutter splash (stereo loop).
    n = 8 * SR
    r = rng(seed)
    gutter = band(coloured(n, r, -1), 400, 3000)
    g = band(white(n, r), 0, 12)
    gutter = gutter * (0.6 + 0.4 * g / np.max(np.abs(g)))
    common = rain_layer(n, rng(seed + 3), 1200, 1.0) + normalise(gutter) * 0.15
    left = common * 0.6 + rain_layer(n, rng(seed + 1), 1200, 1.0) * 0.4
    right = common * 0.6 + rain_layer(n, rng(seed + 2), 1200, 1.0) * 0.4
    return level(left, -20, right=right)


# --------------------------------------------------------------------------- footsteps by surface

def footstep_grass(seed=81):
    # Soft heel thud and a crisp swish of grass blades.
    r = rng(seed)
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    thud = band(white(n, r), 50, 260) * exp_decay(n, 0.03) * 0.5
    swish = crackle(n, r, 1500, 1200, 6000, 0.0008) * np.where(t < 0.01, t / 0.01, np.exp(-(t - 0.01) / 0.07)) * 0.6
    brush = band(white(n, r), 500, 3000) * exp_decay(n, 0.05) * 0.25
    out = thud + swish + brush
    place(out, crackle(n, r, 800, 1500, 5000) * exp_decay(n, 0.04) * 0.25, 0.05)
    return level(fade(soften(out, 6000), 0.001, 0.04), -22)


def footstep_wood(seed=82):
    # Hollow wooden floor: heel thump with board resonances, then the toe.
    r = rng(seed)
    out = np.zeros(int(0.35 * SR))
    modes = [(1, 1, 0.05), (2.18, 0.6, 0.04), (4.7, 0.4, 0.03), (8.6, 0.2, 0.015)]
    m = int(0.2 * SR)
    heel = struck(0.2, 110, modes, 0.001, seed) + band(white(m, r), 800, 4000) * exp_decay(m, 0.003) * 0.4
    toe = struck(0.2, 150, modes, 0.001, seed + 1) * 0.45 + band(white(m, r), 1000, 5000) * exp_decay(m, 0.002) * 0.2
    place(out, heel, 0.0)
    place(out, toe, 0.06)
    return level(fade(soften(reverb(out, 0.3, 0.15, seed), 6000), 0.0008, 0.05), -21)


def footstep_interior(seed=83):
    # Hard tiled floor indoors: crisp heel click, soft body, a short room reflection.
    r = rng(seed)
    out = np.zeros(int(0.35 * SR))
    m = int(0.15 * SR)
    heel = band(white(m, r), 1500, 6000) * exp_decay(m, 0.004) * 0.8 + band(white(m, r), 100, 500) * exp_decay(m, 0.015) * 0.5
    toe = band(white(m, r), 2000, 7000) * exp_decay(m, 0.003) * 0.4
    place(out, heel, 0.0)
    place(out, toe, 0.05)
    return level(fade(soften(reverb(out, 0.45, 0.18, seed), 6500), 0.0005, 0.05), -23)


def footstep_wet(seed=84):
    # Step on wet pavement: concrete heel plus a small splash and droplets.
    r = rng(seed)
    n = int(0.35 * SR)
    out = np.zeros(n)
    step = footstep(seed, "concrete")
    place(out, step / np.max(np.abs(step)) * 0.7, 0.0)
    splash = band(white(n, r), 700, 4500) * np.where(np.arange(n) < 40, np.arange(n) / 40, exp_decay(n, 0.05))
    place(out, splash * 0.35, 0.01)
    for _ in range(4):
        f = r.uniform(1500, 3000)
        place(out, chirp_tone(f, f * 1.5, 0.02, 0.008) * 0.1, r.uniform(0.03, 0.15))
    return level(fade(soften(out, 6000), 0.0008, 0.05), -21)


PRESETS = {
    "bike_bell": (bike_bell, "Thumb-lever dome bell, ding-ding"),
    "bike_freewheel": (bike_freewheel, "Coasting hub ratchet clicks (loop; pitch with speed)"),
    "bike_chain": (chain_pedal, "Chain over sprockets while pedalling (loop)"),
    "tyre_roll": (tyre_roll, "Tyres rolling on asphalt (loop; volume with speed)"),
    "brake_squeal": (brake_squeal, "Rim brake squeal and scrub"),
    "footstep_concrete": (lambda seed=6: footstep(seed, "concrete"), "Footstep on concrete"),
    "footstep_gravel": (lambda seed=6: footstep(seed, "gravel"), "Footstep on gravel"),
    "door_open": (door_open, "Latch click and hinge creak"),
    "door_close": (door_close, "Door thud and latch"),
    "bus_engine_idle": (bus_engine_idle, "Six-cylinder diesel bus idle (loop)"),
    "air_brake_hiss": (air_brake_hiss, "Bus air-brake release hiss"),
    "bus_door": (bus_door, "Pneumatic bus door open/close"),
    "bus_stop_chime": (bus_stop_chime, "Two-tone stop-request chime"),
    "car_pass": (car_pass, "Car driving past with Doppler shift"),
    "car_horn": (car_horn, "Short car horn"),
    "bird_chirp": (bird_chirp, "Songbird chirps"),
    "pigeon_coo": (pigeon_coo, "Pigeon coo"),
    "wing_flap": (wing_flap, "Bird take-off wing flaps"),
    "crow_caw": (crow_caw, "Crow caws"),
    "seagull_call": (seagull_call, "Seagull call"),
    "dog_bark": (dog_bark, "Dog barks twice"),
    "fountain_water": (fountain_water, "Park fountain splashing (loop)"),
    "city_ambience": (city_ambience, "Street ambience: traffic, passing cars, birds (stereo loop)"),
    "park_ambience": (park_ambience, "Park ambience: leaves and birdsong (loop)"),
    "restaurant_ambience": (restaurant_ambience, "Restaurant murmur and cutlery (loop)"),
    "grill_sizzle": (grill_sizzle, "Kitchen grill sizzle (loop)"),
    "cash_register": (cash_register, "Till bell and drawer"),
    "ui_notification": (ui_notification, "Phone: new order"),
    "ui_accept": (ui_accept, "Phone: accept"),
    "ui_reject": (ui_reject, "Phone: reject"),
    "delivery_complete": (delivery_complete, "Delivery completed jingle"),
    "wind": (wind, "Gusting wind (loop)"),
    "rain": (rain, "Rain on pavement and leaves: wash, drops, patter, drips (stereo loop)"),
    # Phone, shop and delivery gameplay (CityAudio.play_ui / one_shot_at).
    "phone_raise": (phone_raise, "Phone coming up out of a pocket"),
    "phone_lower": (phone_lower, "Phone going back into a pocket"),
    "phone_tap": (phone_tap, "Soft phone UI tap"),
    "phone_unlock": (phone_unlock, "Phone unlock click, swish and two notes"),
    "app_open": (app_open, "App open: whoosh into a bright arpeggio"),
    "app_locked": (app_locked, "Soft denied double buzz"),
    "notify_order": (notify_order, "New order: warm marimba chime"),
    "kiosk_click": (kiosk_click, "Computer key / mouse click"),
    "cart_add": (cart_add, "Add to cart: light upward pop"),
    "cart_remove": (cart_remove, "Remove from cart: downward pop"),
    "purchase_complete": (purchase_complete, "Receipt printer, paper tear and till bell"),
    "item_pickup": (item_pickup, "Paper bag rustle when lifting an item"),
    "package_drop": (package_drop, "Parcel landing on the ground: soft thump and crinkle"),
    "package_place": (package_place, "Bag set into a backpack compartment"),
    "bag_zip": (bag_zip, "Backpack zip"),
    "door_knock": (door_knock, "Three knocks on a wooden door"),
    "doorbell": (doorbell, "Ding-dong doorbell"),
    "photo_shutter": (photo_shutter, "Phone camera shutter"),
    "delivery_success": (delivery_success, "Short positive delivery jingle"),
    "customer_thanks": (customer_thanks, "Friendly hummed mm-hm"),
    "coins": (coins, "Coins dropping into a palm (tip / cash)"),
    "step_complete": (step_complete, "Tutorial task ticked"),
    "mission_complete": (mission_complete, "Short fanfare: training / mission complete"),
    # Traffic.
    "car_engine": (car_engine, "Petrol car engine (loop; pitch with speed)"),
    "truck_engine": (truck_engine, "Heavy diesel engine for trucks, vans and coaches (loop)"),
    "horn_honk": (horn_honk, "Car horn double tap"),
    "truck_brake_squeal": (truck_brake_squeal, "Heavy-vehicle brake squeal"),
    "tyre_wet": (tyre_wet, "Tyres on a wet road (loop)"),
    "ped_signal_walk": (ped_signal_walk, "Pedestrian signal WALK: rapid ticks (loop)"),
    "ped_signal_wait": (ped_signal_wait, "Pedestrian signal WAIT: slow locator tick (loop)"),
    # Shops and restaurants.
    "shop_door_chime": (shop_door_chime, "Brass shop-door bell"),
    "cutlery_clink": (cutlery_clink, "Fork tapping a plate"),
    "plate_clink": (plate_clink, "Ceramic plate set down"),
    "pan_clank": (pan_clank, "Kitchen pan knocked on a hob"),
    # Nature, night and weather.
    "songbird_trill": (songbird_trill, "Wren-like trill"),
    "blackbird_song": (blackbird_song, "Mellow blackbird phrase (dawn / dusk)"),
    "owl_hoot": (owl_hoot, "Tawny owl hoot (night)"),
    "crickets": (crickets, "Night crickets in the grass (loop)"),
    "night_city_hum": (night_city_hum, "Distant city at night (stereo loop)"),
    "wind_soft": (wind_soft, "Gentle breeze with leaf rustle (stereo loop)"),
    "rain_heavy": (rain_heavy, "Downpour layer (stereo loop)"),
    # Footsteps by surface.
    "footstep_grass": (footstep_grass, "Footstep on grass"),
    "footstep_wood": (footstep_wood, "Footstep on a wooden floor"),
    "footstep_interior": (footstep_interior, "Footstep on an indoor tiled floor"),
    "footstep_wet": (footstep_wet, "Footstep on wet pavement"),
}

# Seamless loops: written with a RIFF smpl loop chunk; CityAudio.LOOPS must match.
LOOPS = {"bike_freewheel", "bike_chain", "tyre_roll", "bus_engine_idle", "fountain_water", "city_ambience",
         "park_ambience", "restaurant_ambience", "grill_sizzle", "wind", "rain", "car_engine", "truck_engine",
         "tyre_wet", "ped_signal_walk", "ped_signal_wait", "crickets", "night_city_hum", "wind_soft", "rain_heavy"}


# Mix pass for the original (peak-normalised) presets: short-term loudness target (dBFS) and an
# optional gentle high cut, so the whole library sits at one consistent level. The bike loops
# (tyre_roll, bike_chain, bike_freewheel), city_ambience, door_close and wing_flap already sit right.
LEGACY_MIX = {
    "air_brake_hiss": (-20, 2800), "bike_bell": (-17, None), "bird_chirp": (-20, 7000), "brake_squeal": (-18, 6000),
    "bus_door": (-18, 6000), "bus_engine_idle": (-19, None), "bus_stop_chime": (-18, None), "car_horn": (-17, 3500),
    "car_pass": (-17, None), "cash_register": (-18, None), "crow_caw": (-18, None), "delivery_complete": (-18, None),
    "dog_bark": (-18, None), "footstep_concrete": (-22, 7000), "footstep_gravel": (-22, 7000), "fountain_water": (-20, 6000),
    "grill_sizzle": (-25, 3200), "park_ambience": (-19, None), "pigeon_coo": (-19, None), "seagull_call": (-18, None),
    "ui_accept": (-18, None), "ui_notification": (-19, None), "ui_reject": (-21, None), "wind": (-21, None),
    "door_close": (None, None), "wing_flap": (None, None),
}


def render(preset, seed=None):
    fn = PRESETS[preset][0]
    result = fn() if seed is None else fn(seed=seed)
    loop = preset in LOOPS
    left, right = result if isinstance(result, tuple) else (result, None)
    if preset in LEGACY_MIX:
        target, cut = LEGACY_MIX[preset]
        if cut:
            left = soften(left, cut)
            right = None if right is None else soften(right, cut)
        if not loop:
            left = fade(left, 0.001, 0.12)
            right = None if right is None else fade(right, 0.001, 0.12)
        if target is not None:
            if right is None:
                left = level(left, target)
            else:
                left, right = level(left, target, right=right)
    return to_wav_bytes(left, right, loop)
