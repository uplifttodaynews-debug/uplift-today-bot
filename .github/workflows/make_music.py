"""
make_music.py - creates the ORIGINAL background piano tracks (run once by Claude, not by the daily bot).
Warm, hopeful solo piano with a soft string bed. Every track is built from 8-bar sections
(intro, theme, lift, theme again, ...) with changing chord progressions, left-hand patterns,
a melody that repeats and develops, and rising/falling dynamics - so it does not feel like a loop.
Because we make it ourselves, there is no licence to worry about and no YouTube Content ID claim.
Usage: python make_music.py [output_folder]
"""
import os
import subprocess
import sys
import wave

import numpy as np

SR = 44100
MAJOR = [0, 2, 4, 5, 7, 9, 11]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ---------------------------------------------------------------- piano voice
_CACHE = {}


def piano_note(midi, vel):
    """One synthetic piano note (inharmonic partials, two slightly detuned strings, hammer thump)."""
    key = (midi, int(vel * 4))
    if key in _CACHE:
        return _CACHE[key]
    f0 = hz(midi)
    dur = float(np.clip(6.0 - (midi - 36) * 0.07, 1.6, 5.5))
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(midi)
    out = np.zeros(n)
    B = 0.00035 * (1 + (midi - 60) / 40.0 if midi > 60 else 1.0)
    bright = 0.55 + 0.75 * vel                      # harder hit = brighter
    for k in range(1, 15):
        fk = f0 * k * np.sqrt(1 + B * k * k)
        if fk > 11000:
            break
        amp = (1.0 / k ** 1.15) * (bright ** (k - 1) if k > 1 else 1.0)
        tau = (dur * 0.45) / (1 + 0.55 * (k - 1))     # upper partials die faster
        for det in (-0.25, 0.25):                        # two strings -> gentle shimmer
            ph = rng.uniform(0, 2 * np.pi)
            out += 0.5 * amp * np.exp(-t / tau) * np.sin(2 * np.pi * (fk + det) * t + ph)
    attack = np.minimum(1.0, t / 0.004)
    out *= attack
    # hammer thump: short filtered noise burst
    thump_n = int(0.03 * SR)
    noise = rng.standard_normal(thump_n) * np.exp(-np.arange(thump_n) / (SR * 0.007))
    noise = np.convolve(noise, np.ones(24) / 24, mode="same")
    out[:thump_n] += noise * 0.05 * vel
    rel = int(0.35 * SR)                                # smooth end
    out[-rel:] *= np.linspace(1, 0, rel)
    out = out / (np.max(np.abs(out)) + 1e-9) * (0.35 + 0.65 * vel)
    _CACHE[key] = out
    return out


def pad_tone(freq, n, rng):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for detune in (-0.12, 0.0, 0.12):
        f = freq * (1 + detune / 100.0)
        ph = rng.uniform(0, 2 * np.pi)
        out += np.sin(2 * np.pi * f * t + ph) + 0.25 * np.sin(2 * np.pi * 2 * f * t + ph)
    return out / 3.0


def reverb(x, rng, seconds=2.4, mix=0.30):
    n = int(SR * seconds)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * 0.55))
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return (1 - mix) * x + mix * wet


# ---------------------------------------------------------------- composition
def scale_note(key, degree, octave):
    """degree 0.. (can exceed 6 or be negative) -> midi note in a major scale."""
    octv, d = divmod(degree, 7)
    return key + 12 * (octave + octv) + MAJOR[d]


def triad(root_degree):
    return [root_degree, root_degree + 2, root_degree + 4]


PROGRESSIONS = [
    [0, 4, 5, 3],   # I  V  vi IV
    [0, 5, 3, 4],   # I  vi IV V
    [3, 0, 4, 5],   # IV I  V  vi
    [0, 2, 3, 4],   # I  iii IV V
    [5, 3, 0, 4],   # vi IV I  V
]

# left-hand patterns, 8 eighth-notes per bar; numbers index [root, 5th, octave-root, 3rd(high)]
LEFT = [
    [0, 1, 3, 1, 0, 1, 3, 1],
    [0, None, 1, None, 3, None, 1, None],
    [0, 3, 1, 3, 2, 3, 1, 3],
    [0, None, None, None, 1, None, 3, None],
]

# melody rhythms: list of (start_in_eighths, length_in_eighths) inside one bar
RHYTHMS = [
    [(0, 3), (3, 1), (4, 2), (6, 2)],
    [(0, 2), (2, 2), (4, 4)],
    [(0, 1), (1, 1), (2, 2), (4, 2), (6, 2)],
    [(0, 4), (4, 2), (6, 2)],
    [(0, 2), (3, 1), (4, 1), (5, 1), (6, 2)],
    [(2, 2), (4, 2), (6, 2)],
]


def compose(key, bpm, seed, sections=12):
    """Returns (piano_events, pad_events). Event = (time_sec, midi, velocity, length_sec)."""
    rng = np.random.default_rng(seed)
    eighth = 60.0 / bpm / 2
    bar = eighth * 8
    piano, pads = [], []
    plan = ["intro", "theme", "theme", "lift", "theme", "bridge", "lift", "lift", "theme", "bridge", "lift", "outro"]
    plan = (plan * 2)[:sections]
    motif = None
    t0 = 0.0
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    for si, kind in enumerate(plan):
        if kind in ("theme", "lift") or si == 0:
            prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
        base_vel = {"intro": 0.35, "theme": 0.5, "bridge": 0.42, "lift": 0.68, "outro": 0.38}[kind]
        left = LEFT[int(rng.integers(len(LEFT)))] if kind != "lift" else LEFT[0 if rng.random() < 0.5 else 2]
        if motif is None or kind == "bridge":
            motif = [RHYTHMS[int(rng.integers(len(RHYTHMS)))] for _ in range(2)]
        melody_degree = 7 + int(rng.integers(0, 3))      # start around the octave above the key
        for b in range(8):
            chord_root = prog[b % 4]
            tb = t0 + b * bar
            # pad (soft strings): whole bar chord
            for d in triad(chord_root):
                pads.append((tb, scale_note(key, d, 3), 0.5, bar + 1.2))
            # left hand
            notes = [
                scale_note(key, chord_root, 2),
                scale_note(key, chord_root + 4, 2),
                scale_note(key, chord_root + 7, 2),
                scale_note(key, chord_root + 2, 3),
            ]
            if kind == "lift" or (kind == "theme" and si > 2):
                notes = [m for m in notes]
            for i, idx in enumerate(left):
                if idx is None:
                    continue
                vel = base_vel * (0.85 if i % 2 else 1.0) * (0.8 if kind in ("intro", "outro") else 1.0)
                piano.append((tb + i * eighth, notes[idx], min(vel, 0.9) * 0.8, 2.0))
            # melody (not in the first 4 bars of the intro, not in the last 4 of the outro)
            has_melody = not ((kind == "intro" and b < 4) or (kind == "outro" and b >= 4))
            if has_melody:
                rhythm = motif[b % 2]
                chord_tones = triad(chord_root)
                for j, (st, ln) in enumerate(rhythm):
                    strong = st in (0, 4)
                    if strong:   # land on a chord tone near where we are
                        cands = [d + 7 * o for d in chord_tones for o in (0, 1, 2)]
                        cands = [c for c in cands if 6 <= c <= 13]
                        melody_degree = min(cands, key=lambda c: abs(c - melody_degree) + rng.random() * 0.8)
                    else:
                        melody_degree += int(rng.choice([-1, 1, 1, -2, 2]))
                        melody_degree = int(np.clip(melody_degree, 6, 13))
                    # sometimes leave a gap so the tune breathes
                    if not strong and rng.random() < 0.15:
                        continue
                    if b == 7:                               # cadence: end the phrase calmly
                        if j == len(rhythm) - 1:
                            melody_degree = chord_tones[0] + 7 * (1 if chord_tones[0] < 6 else 0) + 7
                    vel = base_vel * (1.15 if kind == "lift" else 1.0) * (1.1 if strong else 0.92)
                    m = scale_note(key, melody_degree, 3)
                    piano.append((tb + st * eighth, m, min(vel, 0.95), ln * eighth + 1.2))
                    if kind == "lift" and strong and rng.random() < 0.6:   # octave doubling in the lift
                        piano.append((tb + st * eighth, m - 12, min(vel, 0.9) * 0.6, ln * eighth + 1.0))
        t0 += 8 * bar
    return piano, pads, t0


def render(name, key, bpm, seed, total_seconds=240):
    rng = np.random.default_rng(seed)
    piano, pads, length = compose(key, bpm, seed, sections=max(1, int(np.ceil(total_seconds / (8 * 60.0 / bpm * 4)))))
    total = int(total_seconds * SR)
    L = np.zeros(total)
    R = np.zeros(total)
    for (t, m, vel, ln) in piano:
        s = int(t * SR)
        if s >= total:
            continue
        w = piano_note(int(m), vel)
        keep = min(len(w), int((ln + 0.8) * SR))
        seg = w[:keep].copy()
        fade = min(int(0.4 * SR), keep)
        seg[-fade:] *= np.linspace(1, 0, fade)
        e = min(s + keep, total)
        pan = float(np.clip((m - 60) / 50.0, -0.6, 0.6))
        L[s:e] += seg[: e - s] * (0.5 - pan / 2) * 1.4
        R[s:e] += seg[: e - s] * (0.5 + pan / 2) * 1.4
    # soft strings underneath
    pad = np.zeros(total)
    for (t, m, vel, ln) in pads:
        s = int(t * SR)
        if s >= total:
            continue
        n = int(ln * SR)
        env = np.minimum(1.0, np.arange(n) / (1.4 * SR)) * np.minimum(1.0, (n - np.arange(n)) / (1.2 * SR))
        seg = pad_tone(hz(m), n, rng) * env
        e = min(s + n, total)
        pad[s:e] += seg[: e - s]
    pad *= 0.045
    L += pad
    R += pad
    rl = np.random.default_rng(seed + 1)
    rr = np.random.default_rng(seed + 2)
    L = reverb(L, rl)
    R = reverb(R, rr)
    st = np.stack([L, R], axis=1)
    fade = int(4 * SR)
    st[:fade] *= np.linspace(0, 1, fade)[:, None]
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st /= np.max(np.abs(st)) + 1e-9
    st *= 0.7
    return st


def save_mp3(stereo, path):
    pcm = (stereo * 32767).astype(np.int16)
    wav = path + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "128k", path])
    os.remove(wav)


# name, key (MIDI of the tonic, C2=36 .. we use pitch-class numbers in octave 0), tempo
TRACKS = [
    ("piano_sunrise", 0, 92),     # C major
    ("piano_hope", 7, 100),       # G major
    ("piano_bright", 2, 104),     # D major
    ("piano_glow", 5, 88),        # F major
]

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "music"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    os.makedirs(outdir, exist_ok=True)
    for i, (name, key, bpm) in enumerate(TRACKS):
        if only and only != name:
            continue
        save_mp3(render(name, key, bpm, seed=i * 11 + 3), os.path.join(outdir, name + ".mp3"))
        print("made", name, flush=True)
