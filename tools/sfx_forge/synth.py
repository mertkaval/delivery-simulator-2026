"""SFX Forge: free, offline procedural sound-effect synthesis for the game (numpy only).

Techniques: modal synthesis (bells, cutlery, register), shaped noise with FFT-domain filters
(tyres, wind, water, hiss, ambience), firing-pulse engines (diesel bus), formant voices
(pigeons, crows, gulls, dog) and seamless crossfaded loops. Output: 16-bit PCM WAV.

Every preset is deterministic for a given seed, so regenerating gives identical files.
"""
import io
import math
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
    """Crossfade the tail into the head so the clip loops without a click."""
    n = int(fade * SR)
    head, tail = x[:n].copy(), x[-n:]
    w = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * w + tail * (1 - w)
    return x


def normalise(x, peak=0.89):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def soft_clip(x, drive=1.5):
    return np.tanh(x * drive) / np.tanh(drive)


def to_wav_bytes(x, stereo=None):
    x = np.clip(x, -1, 1)
    data = (x * 32767).astype(np.int16)
    channels = 1
    if stereo is not None:
        right = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
        data = np.column_stack([data, right]).ravel()
        channels = 2
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return buf.getvalue()


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


def door_open(seed=7):
    r = rng(seed)
    out = np.zeros(int(1.2 * SR))
    latch = modal(0.08, [(1700, 1, 0.01), (3100, 0.6, 0.008)], 0.6, seed)
    place(out, latch, 0.0)
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    creak_f = 380 + 160 * t / t[-1]
    creak = np.sign(np.sin(2 * np.pi * np.cumsum(creak_f) / SR)) * band(white(n, r), 200, 2500) * 0.3
    place(out, band(creak, 250, 2200) * env_adsr(n, 0.1, 0.2, 0.6, 0.3, 0.6), 0.1)
    return normalise(out, 0.7)


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
    out = np.zeros(int((len(notes) * step + 1.2) * SR))
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


def restaurant_ambience(seed=25):
    # Indistinct murmur (formant-shaped noise), cutlery clinks, the odd laugh-like swell.
    dur = 14.0
    r = rng(seed)
    n = int(dur * SR)
    base = coloured(n, r, -3)
    murmur = sum(resonance(band(base, 150, 3500), fc, 6, 1.5) for fc in (500, 1100, 2300)) / 3
    murmur *= 0.7 + 0.3 * np.abs(band(white(n, r), 0, 2.5)) * 5
    out = normalise(murmur) * 0.5
    for _ in range(int(dur * 2.2)):
        f = r.uniform(3200, 5200)
        clink = modal(0.25, [(f, 1, 0.05), (f * 2.4, 0.4, 0.03)], 0.2, int(r.integers(1e6)))
        place(out, clink * r.uniform(0.05, 0.18), r.uniform(0, dur - 0.3))
    return normalise(loopify(out, 0.8), 0.55)


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


def rain(seed=33):
    dur = 8.0
    r = rng(seed)
    n = int(dur * SR)
    out = band(coloured(n, r, -1), 400, 12000) * 0.4
    for _ in range(int(dur * 300)):
        m = int(0.003 * SR)
        place(out, band(white(m, r), 2000, 10000) * np.hanning(m) * r.uniform(0.05, 0.5), r.uniform(0, dur - 0.01))
    return normalise(loopify(out, 0.6), 0.5)


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
    "rain": (rain, "Rain on pavement (loop)"),
}


def render(preset, seed=None):
    fn = PRESETS[preset][0]
    result = fn() if seed is None else fn(seed=seed)
    if isinstance(result, tuple):
        return to_wav_bytes(result[0], result[1])
    return to_wav_bytes(result)
