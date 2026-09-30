"""
make_music.py - creates the ORIGINAL background music tracks (run once by Claude, not by the daily bot).
Soft, warm, hopeful ambient: a slow chord pad + gentle bell notes + a little room echo.
Because we make it ourselves, there is no licence to worry about and no YouTube Content ID claim.
"""
import subprocess
import sys
import wave

import numpy as np

SR = 44100


def note(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


# Each track: name, chord length in seconds, list of chords (MIDI notes), bell pattern offset
TRACKS = [
    # C major feel: C - G - Am - F
    ("ambient_sunrise", 8.0, [[48, 55, 60, 64, 67], [43, 55, 59, 62, 67], [45, 57, 60, 64, 67], [41, 53, 60, 64, 69]]),
    # D major feel: D - A - Bm - G
    ("ambient_morning", 9.0, [[50, 57, 62, 66, 69], [45, 57, 61, 64, 69], [47, 59, 62, 66, 71], [43, 55, 62, 67, 71]]),
    # F major feel: F - C - Dm - Bb
    ("ambient_hope", 8.5, [[41, 53, 57, 60, 65], [48, 55, 60, 64, 67], [50, 57, 62, 65, 69], [46, 53, 58, 62, 65]]),
    # G major feel: G - D - Em - C
    ("ambient_glow", 9.5, [[43, 55, 59, 62, 67], [50, 57, 62, 66, 69], [52, 55, 59, 64, 67], [48, 55, 60, 64, 67]]),
]


def pad_tone(freq, n, rng):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for detune in (-0.12, 0.0, 0.12):  # slight detune = warm, chorus-like
        f = freq * (1 + detune / 100.0)
        ph = rng.uniform(0, 2 * np.pi)
        out += np.sin(2 * np.pi * f * t + ph)
        out += 0.25 * np.sin(2 * np.pi * 2 * f * t + ph)
        out += 0.08 * np.sin(2 * np.pi * 3 * f * t + ph)
    return out / 3.0


def bell(freq, n):
    t = np.arange(n) / SR
    env = np.exp(-t * 2.2) * (1 - np.exp(-t * 80))
    return env * (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * 2 * freq * t))


def reverb(x, rng, seconds=2.6, mix=0.28):
    n = int(SR * seconds)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * 0.6))
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return (1 - mix) * x + mix * wet


def render(name, chord_len, chords, total_seconds=240, seed=1):
    rng = np.random.default_rng(seed)
    total = int(total_seconds * SR)
    mix = np.zeros(total)
    clen = int(chord_len * SR)
    overlap = int(2.5 * SR)
    pos, k = 0, 0
    while pos < total:
        chord = chords[k % len(chords)]
        n = clen + overlap
        seg = sum(pad_tone(note(m), n, rng) for m in chord) / len(chord)
        env = np.ones(n)
        a = overlap
        env[:a] = np.linspace(0, 1, a) ** 1.5
        env[-overlap:] = np.linspace(1, 0, overlap) ** 1.5
        end = min(pos + n, total)
        mix[pos:end] += (seg * env)[: end - pos]
        # gentle bell notes from the chord, two per chord, spaced out
        for j, m in enumerate([chord[2] + 12, chord[3] + 12, chord[4] + 12][:2]):
            start = pos + int((1.5 + j * chord_len / 2.2) * SR)
            b = bell(note(m), int(3.5 * SR)) * 0.10
            e = min(start + len(b), total)
            if start < total:
                mix[start:e] += b[: e - start]
        pos += clen
        k += 1
    mix = reverb(mix, rng)
    fade = int(4 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= np.max(np.abs(mix)) + 1e-9
    mix *= 0.6
    return mix


def save_mp3(samples, path):
    pcm = (samples * 32767).astype(np.int16)
    wav = path + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "2",
                           "-b:a", "96k", path])
    import os
    os.remove(wav)


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "music"
    import os
    os.makedirs(outdir, exist_ok=True)
    for i, (name, clen, chords) in enumerate(TRACKS):
        x = render(name, clen, chords, seed=i + 7)
        save_mp3(x, os.path.join(outdir, name + ".mp3"))
        print("made", name)
