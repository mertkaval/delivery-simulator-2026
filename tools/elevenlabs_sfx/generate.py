"""Generate the game's sound effects with ElevenLabs text-to-sound-effects.

Reads sounds.json (name, folder, prompt, duration, loop, influence, priority, slice) and writes
44.1 kHz WAVs to assets/audio/elevenlabs/<folder>/. Sounds that already exist are skipped, so a
run can be repeated or resumed. `slice: true` sounds are generated as a sequence of separate hits
(footsteps, landings, clicks) and cut into numbered one-shots: <name>_01.wav, <name>_02.wav, ...

The API key comes from .env.local (ELEVENLABS_API_KEY, written by `elevenlabs onboard`); it is
never read or printed here. Credits are checked before every request and the run stops when the
next sound would take the account below --reserve.

usage: python generate.py [--priority N] [--only name,name] [--reserve 800] [--dry-run]
       python generate.py --normalize      (level-match every generated file to -6 dB peak)
"""
import argparse
import io
import json
import os
import sys
import time
import wave

import numpy as np
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(PROJECT, "assets", "audio", "elevenlabs")
RATE = 44100
MODEL = "eleven_text_to_sound_v2"
# Price used to decide whether a sound still fits the budget (credits per second). Measured
# ~10/s on eleven_text_to_sound_v2 (Oct 2026); 12 leaves a margin.
EST_PER_SECOND = 12


def read_wav(data):
    with wave.open(io.BytesIO(data)) as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return pcm.reshape(-1, ch), rate


def write_wav(path, samples, rate):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(samples.shape[1])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def slice_hits(samples, rate, min_gap=0.08, pad=0.02):
    """Split a recording of separate hits on the silences between them."""
    mono = np.abs(samples).max(axis=1)
    hop = int(rate * 0.005)
    env = np.array([mono[i:i + hop].max() for i in range(0, len(mono), hop)])
    floor = max(env.max() * 0.06, 10 ** (-50 / 20))
    loud = env > floor
    hits, start, quiet = [], None, 0
    for i, on in enumerate(loud):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * hop >= min_gap * rate:
                hits.append((start, i - quiet + 1))
                start, quiet = None, 0
    if start is not None:
        hits.append((start, len(env)))
    out = []
    for a, b in hits:
        if (b - a) * hop < 0.04 * rate:
            continue
        s = max(0, a * hop - int(pad * rate))
        e = min(len(samples), b * hop + int(pad * 4 * rate))
        clip = samples[s:e].copy()
        fade = min(len(clip) // 4, int(0.015 * rate))
        if fade > 0:
            clip[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
        out.append(clip)
    return out


def with_retry(call, tries=6):
    """Run an API call, backing off on 429 rate limits."""
    for attempt in range(tries):
        try:
            return call()
        except Exception as e:
            if getattr(e, "status_code", None) != 429 or attempt == tries - 1:
                raise
            wait = 10 * (attempt + 1)
            print(f"     rate limited, waiting {wait} s")
            time.sleep(wait)


def normalize_all(peak_db=-6.0, max_gain_db=30.0):
    """Bring every generated sound (not the _source recordings) to the same peak level.
    One gain per file, so seamless loops stay seamless."""
    target = 10 ** (peak_db / 20)
    for root, dirs, files in os.walk(OUT):
        dirs[:] = [d for d in dirs if d != "_source"]
        for f in files:
            if not f.endswith(".wav"):
                continue
            path = os.path.join(root, f)
            with open(path, "rb") as fh:
                samples, rate = read_wav(fh.read())
            peak = float(np.abs(samples).max())
            if peak <= 0:
                continue
            gain = min(target / peak, 10 ** (max_gain_db / 20))
            write_wav(path, samples * gain, rate)
            print(f"{os.path.relpath(path, OUT):45s} {20 * np.log10(peak):6.1f} -> {20 * np.log10(peak * gain):6.1f} dB")


def credits(client):
    s = with_retry(lambda: client.user.subscription.get())
    return s.character_limit - s.character_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--priority", type=int, default=1, help="generate sounds with priority <= N")
    ap.add_argument("--only", default="", help="comma-separated sound names")
    ap.add_argument("--reserve", type=int, default=800, help="credits to leave unspent")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--normalize", action="store_true", help="only level-match the existing files")
    args = ap.parse_args()
    if args.normalize:
        normalize_all()
        return

    sounds = json.load(open(os.path.join(HERE, "sounds.json"), encoding="utf-8"))["sounds"]
    only = {n for n in args.only.split(",") if n}
    todo = []
    for s in sounds:
        if only and s["name"] not in only:
            continue
        if not only and s.get("priority", 1) > args.priority:
            continue
        first = os.path.join(OUT, s["folder"], s["name"] + ("_01.wav" if s.get("slice") else ".wav"))
        if not os.path.exists(first):
            todo.append(s)
    est = sum(s["duration"] for s in todo) * EST_PER_SECOND
    print(f"{len(todo)} sounds to make, {sum(s['duration'] for s in todo):.1f} s of audio, "
          f"worst case ~{est:.0f} credits")
    if args.dry_run or not todo:
        return

    load_dotenv(os.path.join(PROJECT, ".env.local"))
    from elevenlabs import ElevenLabs
    client = ElevenLabs()
    start = credits(client)
    print(f"credits left: {start}")
    # The account balance updates late, so spending is tracked here at the worst-case price.
    log, spent = [], 0
    for s in todo:
        cost = s["duration"] * EST_PER_SECOND
        if start - spent - cost < args.reserve:
            print(f"stopping: ~{start - spent:.0f} credits left (estimate), keeping {args.reserve} in reserve")
            break
        try:
            data = with_retry(lambda: b"".join(client.text_to_sound_effects.convert(
                text=s["prompt"], model_id=MODEL, duration_seconds=s["duration"],
                prompt_influence=s.get("influence", 0.5), loop=bool(s.get("loop", False)),
                output_format="wav_44100")))
        except Exception as e:  # keep going; a single failure should not stop the batch
            print(f"FAIL {s['name']}: {str(e)[:160]}")
            continue
        spent += cost
        time.sleep(2.0)
        samples, rate = read_wav(data)
        folder = os.path.join(OUT, s["folder"])
        if s.get("slice"):
            hits = slice_hits(samples, rate)
            write_wav(os.path.join(folder, "_source", s["name"] + ".wav"), samples, rate)
            for i, clip in enumerate(hits, 1):
                write_wav(os.path.join(folder, f"{s['name']}_{i:02d}.wav"), clip, rate)
            made = f"{len(hits)} slices"
        else:
            write_wav(os.path.join(folder, s["name"] + ".wav"), samples, rate)
            made = f"{len(samples) / rate:.1f} s"
        log.append({"name": s["name"], "seconds": s["duration"]})
        print(f"ok   {s['folder']}/{s['name']}  ({made}, ~{start - spent:.0f} credits left by estimate)")
    end = credits(client)
    print(f"done: used {start - end} credits this run, {end} left")
    with open(os.path.join(OUT, "generation_log.json"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"run": log, "used": start - end, "left": end}) + "\n")


if __name__ == "__main__":
    sys.exit(main())
