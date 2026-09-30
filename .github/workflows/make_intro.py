"""
make_intro.py - creates the ORIGINAL "evening news" opening (run once by Claude, not by the daily bot).
  intro/intro.mp4  = about 9 seconds: sunrise animation + "UPLIFT TODAY" title + a driving news-style theme
                     (snare roll, timpani, brass-style stabs, rising fanfare, big final chord).
The theme is our own composition in the general style of TV news openings - it is not any real channel's tune.
Usage: python make_intro.py [output_folder]
"""
import math
import os
import shutil
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

import config
import video
from make_music import piano_note, reverb, hz

SR = 44100
BPM = 144
BEAT = 60.0 / BPM
EIGHTH = BEAT / 2
BAR = BEAT * 4
BARS = 2
TAIL = 1.7
TOTAL = BAR * BARS + TAIL
HIT = BAR * BARS            # time of the final chord


# ------------------------------------------------------------------ sounds
def _add(buf, t, sig):
    s = int(t * SR)
    if s >= len(buf):
        return
    e = min(s + len(sig), len(buf))
    buf[s:e] += sig[: e - s]


def brass(midi, length, vel=1.0):
    n = int((length + 0.12) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.zeros(n)
    for k in range(1, 9):
        sig += np.sin(2 * np.pi * f * k * t + 0.3 * k) / k ** 0.9
        sig += 0.5 * np.sin(2 * np.pi * f * 1.004 * k * t) / k ** 0.9      # slight chorus
    env = np.minimum(1, t / 0.012) * np.where(t < length, 1.0, np.exp(-(t - length) / 0.04))
    env *= 0.75 + 0.25 * np.exp(-t / 0.15)                                  # bite at the start
    return sig * env * vel * 0.16


def string_pad(midi, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.zeros(n)
    for d in (-0.15, 0.0, 0.15):
        ff = f * (1 + d / 100)
        for k in range(1, 6):
            sig += np.sin(2 * np.pi * ff * k * t) / k
    env = np.minimum(1, t / 1.6) * np.minimum(1, (length - t) / 0.6)
    return sig * env * 0.03


def kick(vel=1.0, length=0.45):
    n = int(length * SR)
    t = np.arange(n) / SR
    freq = 50 + 110 * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(ph) * np.exp(-t / 0.16) * vel * 0.9


def timpani(midi, vel=1.0, length=1.2):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.sin(2 * np.pi * (f * (1 + 0.25 * np.exp(-t / 0.05))) * t) * np.exp(-t / 0.45)
    sig += 0.4 * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t / 0.25)
    return sig * vel * 0.8


def snare(vel=1.0, length=0.22, seed=1):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(18) / 18, mode="same")      # take out the lows
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.04) * 0.5
    return (noise * np.exp(-t / 0.06) * 0.6 + tone) * vel * 0.55


def crash(length=2.2, seed=9):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(8) / 8, mode="same")
    return noise * np.exp(-t / 0.8) * 0.22


def bell(midi, length=2.0, vel=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t)) * np.exp(-t / 0.7) * 0.12 * vel


# ------------------------------------------------------------------ composition (key of D major)
D, A, Bm, G = 2, 9, 11, 7                     # pitch classes
CHORDS = [  # bar -> (bass midi, chord midi notes)
    (38, [62, 69, 74]),         # D
    (45, [64, 69, 73]),         # A
    (47, [62, 66, 71]),         # Bm
    (43, [62, 67, 71]),         # G
]
STAB = [0, 2, 3, 5, 6]          # eighth-note positions of the brass stabs in each bar (syncopated)
MELODY = [
    [(0, 74, 2), (2, 78, 1), (3, 81, 1), (4, 86, 4)],
    [(0, 85, 2), (2, 88, 1), (3, 85, 1), (4, 81, 2), (6, 83, 1), (7, 86, 1)],
]


def render_theme():
    total = int(TOTAL * SR)
    L = np.zeros(total)
    R = np.zeros(total)
    mono = np.zeros(total)
    for bar in range(BARS):
        tb = bar * BAR
        bass, chord = CHORDS[bar]
        swell = 0.85 + 0.15 * bar / (BARS - 1)           # the piece grows louder as it goes
        # driving bass pulse in eighths
        for i in range(16):
            _add(mono, tb + i * EIGHTH / 2, brass(bass + 12 * (i % 2), EIGHTH / 2 * 0.75, 0.75 * swell))
        # brass stabs
        for e in STAB:
            for m in chord:
                _add(mono, tb + e * EIGHTH, brass(m, EIGHTH * 0.85, swell))
        # melody in brass + piano
        for (e, m, ln) in MELODY[bar]:
            _add(mono, tb + e * EIGHTH, brass(m, ln * EIGHTH * 0.95, 1.25 * swell))
            _add(mono, tb + e * EIGHTH, piano_note(m - 12, 0.8) * 0.9)
        # strings
        for m in chord:
            _add(mono, tb, string_pad(m - 12, BAR + 0.5))
        # drums
        for b in range(4):
            _add(mono, tb + b * BEAT, kick(0.85 * swell))
        if bar == 0:   # snare roll building up
            for i in range(16):
                _add(mono, tb + i * BEAT / 4, snare(0.25 + 0.6 * i / 15, seed=i))
        else:
            for b in (1, 3):
                _add(mono, tb + b * BEAT, snare(swell, seed=bar * 10 + b))
            for i in range(4):                                  # 16th-note fill at the end of each bar
                _add(mono, tb + 3.5 * BEAT + i * BEAT / 8, snare(0.5 + 0.12 * i, seed=100 + bar * 4 + i))
        if bar == BARS - 1:                                     # timpani roll into the final hit
            for i in range(8):
                _add(mono, tb + 3 * BEAT + i * BEAT / 8, timpani(38, 0.5 + 0.07 * i, 0.4))
    # the big final chord
    for m in [38, 50, 57, 62, 66, 69, 74, 78, 81, 86]:
        _add(mono, HIT, brass(m, 1.3, 1.2))
    _add(mono, HIT, piano_note(74, 1.0) * 1.1)
    _add(mono, HIT, piano_note(62, 1.0) * 1.1)
    _add(mono, HIT, piano_note(50, 1.0) * 1.1)
    _add(mono, HIT, timpani(38, 1.2, 1.6))
    _add(mono, HIT, kick(1.0, 0.6))
    _add(mono, HIT, crash())
    for i, m in enumerate([86, 90, 93, 98]):                    # sparkle on top
        _add(mono, HIT + 0.05 + i * 0.12, bell(m, 2.0, 1.0))
    # stereo + hall
    rng = np.random.default_rng(5)
    L = reverb(mono, rng, seconds=1.4, mix=0.22)
    R = reverb(mono * 0.98, np.random.default_rng(6), seconds=1.4, mix=0.22)
    st = np.stack([L, R], axis=1)
    fade = int(0.9 * SR)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st /= np.max(np.abs(st)) + 1e-9
    return st * 0.8


def save_wav(stereo, path):
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ pictures
W, H = config.VIDEO_SIZE
FPS = 25


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def frame(t, base, title_font, small_font, hindi_font, tag_font):
    img = base.copy().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(H * 0.72)
    # expanding rings from the sun position
    cx, cy = W // 2, horizon - 30
    for k in range(4):
        rt = (t * 0.9 - k * 0.22)
        if rt > 0:
            r = int(rt * 1100)
            a = int(max(0, 110 * (1 - rt * 1.0)))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 230, 170, a), width=3)
    # sun rises from the horizon over the first 2 seconds
    rise = ease(t / 1.0)
    sun_y = horizon + 70 - rise * 65
    glow = int(200 + 60 * rise)
    for g in range(6, 0, -1):
        rr = 62 + g * 12
        d.ellipse([cx - rr, sun_y - rr, cx + rr, sun_y + rr], fill=(255, 210, 120, int(12 * rise)))
    video._sun(d, cx, sun_y, 60)
    # ground band (hides the lower part of the sun)
    d.rectangle([0, horizon + 60, W, H], fill=(58, 14, 42, 255))
    d.rectangle([0, horizon + 56, W, horizon + 62], fill=(255, 196, 120, 255))
    # title
    title = "UPLIFT TODAY"
    tw = d.textlength(title, font=title_font)
    p = ease((t - 0.8) / 0.6)
    if p > 0:
        ty = int(85 - (1 - p) * 40)
        panel = Image.new("RGBA", (W, 325), (55, 10, 40, int(120 * p)))
        img.paste(panel, (0, 60), panel)
        d = ImageDraw.Draw(img, "RGBA")
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.text(((W - tw) / 2 + 4, ty + 5), title, font=title_font, fill=(40, 6, 30, int(200 * p)))
        img = Image.alpha_composite(img, shadow)
        d = ImageDraw.Draw(img, "RGBA")
        d.text(((W - tw) / 2, ty), title, font=title_font, fill=(255, 255, 255, int(255 * p)),
               stroke_width=2, stroke_fill=(70, 10, 50, int(255 * p)))
        # gold bars sweep in from both sides
        bar_len = int(ease((t - 0.9) / 0.6) * (tw / 2 + 40))
        by = ty + int(title_font.size * 1.25)
        d.rectangle([W // 2 - bar_len, by, W // 2 + bar_len, by + 7], fill=(255, 200, 110, 255))
    # hindi + english tag
    p2 = ease((t - 1.8) / 0.6)
    if p2 > 0:
        htxt = "आज की अच्छी खबरें"
        hw = d.textlength(htxt, font=hindi_font)
        d.text(((W - hw) / 2, 256 + (1 - p2) * 20), htxt, font=hindi_font, fill=(255, 236, 190, int(255 * p2)))
        tag = "Good news. Every day."
        tgw = d.textlength(tag, font=tag_font)
        d.text(((W - tgw) / 2, 322 + (1 - p2) * 20), tag, font=tag_font, fill=(255, 255, 255, int(230 * p2)))
    # flash on the final hit
    if HIT - 0.05 <= t <= HIT + 0.45:
        a = int(170 * (1 - (t - HIT + 0.05) / 0.5))
        d.rectangle([0, 0, W, H], fill=(255, 250, 235, max(a, 0)))
    # fade in from black at the very start
    if t < 0.2:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * (1 - t / 0.2))))
    return img.convert("RGB")


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    work = os.path.join(outdir, "_work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "theme.wav")
    save_wav(render_theme(), wav)
    base = video._gradient()
    title_font = video._font(118, latin=True)
    small_font = video._font(34, latin=True)
    hindi_font = video._font(64)
    tag_font = video._font(44, latin=True)
    n = int(TOTAL * FPS)
    for i in range(n):
        frame(i / FPS, base, title_font, small_font, hindi_font, tag_font).save(os.path.join(work, f"f{i:04d}.png"))
    out = os.path.join(outdir, "intro.mp4")
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(work, "f%04d.png"),
        "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-af", "alimiter=limit=0.9:level=disabled", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-shortest", out])
    shutil.copy(wav, os.path.join(outdir, "theme_preview.wav"))
    shutil.rmtree(work)
    print("made", out, round(TOTAL, 2), "seconds")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "intro")
