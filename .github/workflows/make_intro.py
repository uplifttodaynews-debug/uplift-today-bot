"""
make_intro.py - creates the ORIGINAL cinematic news opening (run once by Claude, not by the daily bot).
  intro/intro.mp4 = about 6 seconds: dark cinematic build -> big synchronised hit -> "UPLIFT TODAY".
Style: serious, authoritative, urgent - D minor, deep pulsing sub bass, sustained synth/string textures,
sharp percussion, rising tension, crescendo, synchronised hits. Everything (motif, rhythm, sounds) is our
own composition and sound design; it is in the general style of TV news openings, not any real channel's tune.
Usage: python make_intro.py [output_folder]
"""
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
BPM = 160
BEAT = 60.0 / BPM
BAR = BEAT * 4
BUILD_BARS = 3
HIT = BAR * BUILD_BARS          # the final big hit, 4.5 s
TAIL = 1.5
TOTAL = HIT + TAIL


# ------------------------------------------------------------------ sound building blocks
def _add(buf, t, sig):
    s = int(t * SR)
    if s >= len(buf) or s < 0:
        return
    e = min(s + len(sig), len(buf))
    buf[s:e] += sig[: e - s]


def sub_bass(midi, length, vel=1.0):
    n = int((length + 0.15) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t)
    sig = np.tanh(1.6 * sig) * 0.7                                    # warm saturation
    env = np.minimum(1, t / 0.006) * np.where(t < length, 1.0, np.exp(-(t - length) / 0.05))
    env *= 0.6 + 0.4 * np.exp(-t / 0.18)
    return sig * env * vel * 0.9


def pluck(midi, length=0.11, vel=1.0, bright=1.0):
    n = int((length + 0.1) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.zeros(n)
    for k in range(1, 11):
        sig += np.sin(2 * np.pi * f * k * t + 0.4 * k) / k * np.exp(-t * (18 + 10 * k) / bright)
    env = np.minimum(1, t / 0.002)
    return sig * env * vel * 0.30


def pad(midi, length, vel=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.zeros(n)
    for d in (-0.2, 0.0, 0.2):
        ff = f * (1 + d / 100)
        for k in range(1, 7):
            sig += np.sin(2 * np.pi * ff * k * t + k) / k ** 1.1
    env = np.minimum(1, t / 1.2) * np.minimum(1, (length - t) / 0.4)
    return sig * env * vel * 0.03


def lead(midi, length, vel=1.0):
    """Sustained synth/cello-like lead with a little vibrato."""
    n = int((length + 0.2) * SR)
    t = np.arange(n) / SR
    f = hz(midi) * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.3))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.zeros(n)
    for k in range(1, 9):
        sig += np.sin(k * ph) / k ** 0.85
    env = np.minimum(1, t / 0.025) * np.where(t < length, 1.0, np.exp(-(t - length) / 0.1))
    return sig * env * vel * 0.16


def kick(vel=1.0, length=0.5):
    n = int(length * SR)
    t = np.arange(n) / SR
    freq = 46 + 120 * np.exp(-t / 0.025)
    ph = 2 * np.pi * np.cumsum(freq) / SR
    return np.tanh(1.4 * np.sin(ph)) * np.exp(-t / 0.18) * vel


def timpani(midi, vel=1.0, length=1.4):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    sig = np.sin(2 * np.pi * (f * (1 + 0.3 * np.exp(-t / 0.05))) * t) * np.exp(-t / 0.5)
    sig += 0.4 * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t / 0.3)
    return sig * vel * 0.85


def snare(vel=1.0, length=0.25, seed=1):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(14) / 14, mode="same")
    tone = np.sin(2 * np.pi * 200 * t) * np.exp(-t / 0.04) * 0.5
    return (noise * np.exp(-t / 0.07) * 0.65 + tone) * vel * 0.6


def crash(length=2.6, seed=9, vel=1.0):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(6) / 6, mode="same")
    return noise * np.exp(-t / 0.9) * 0.26 * vel


def riser(length, seed=3):
    """Filtered-noise swell plus a rising sine sweep: the classic 'tension' rise."""
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    x = t / length
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(10) / 10, mode="same")
    sweep = np.sin(2 * np.pi * np.cumsum(180 + 2400 * x ** 2) / SR)
    return (noise * 0.22 + sweep * 0.18) * (x ** 2.2)


def brass_stab(midis, length=0.9, vel=1.0):
    n = int((length + 0.15) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in midis:
        f = hz(m)
        for k in range(1, 9):
            out += np.sin(2 * np.pi * f * k * t + 0.3 * k) / k ** 0.9 * 0.06
    env = np.minimum(1, t / 0.012) * np.where(t < length, 1.0, np.exp(-(t - length) / 0.08))
    env *= 0.7 + 0.3 * np.exp(-t / 0.2)
    return out * env * vel


def big_hit(mono, t, size=1.0, chord=(38, 45, 50, 53, 57, 62)):
    """Synchronised hit: kick + timpani + sub boom + brass/orchestra stab + cymbal."""
    _add(mono, t, kick(1.0 * size))
    _add(mono, t, timpani(38, 1.0 * size))
    _add(mono, t, sub_bass(26, 0.9 * size + 0.2, 1.1 * size))
    _add(mono, t, brass_stab(list(chord), 0.8 * size + 0.2, 1.0 * size))
    _add(mono, t, crash(1.4 + 1.2 * size, vel=0.6 * size))


# ------------------------------------------------------------------ composition (D minor / Dorian)
BASS = [26, 34, 33]                    # D1 D1 Bb1 G1 A1
TRIADS = [                                      # sustained textures (midi)
    [50, 57, 62, 65],                           # Dm
    [46, 53, 58, 62],                           # Bb
    [45, 52, 57, 61],                           # A (tension)
]
PLUCK_NOTES = [                                 # 16th-note ostinato pattern per bar (root, 5th, octave, 5th)
    [50, 57, 62, 57], [46, 53, 58, 53], [45, 52, 57, 52],
]
MOTIF_A = [(0, 74, 1.5), (1.5, 77, 0.5), (2, 81, 1.0), (3, 79, 1.0)]     # D F A G  (asks a question)
MOTIF_B = [(0, 74, 1.5), (1.5, 77, 0.5), (2, 82, 1.0), (3, 81, 1.0)]     # D F Bb A (rises higher)


def render_theme():
    total = int(TOTAL * SR)
    mono = np.zeros(total)
    for bar in range(BUILD_BARS):
        tb = bar * BAR
        grow = 0.55 + 0.45 * bar / (BUILD_BARS - 1)
        # deep pulsing bass: quarters in bar 0, then driving eighths
        steps = 4 if bar == 0 else 8
        for i in range(steps):
            _add(mono, tb + i * BAR / steps, sub_bass(BASS[bar], BAR / steps * 0.85, (0.75 + 0.25 * (i % 2 == 0)) * grow))
        # sustained textures
        for m in TRIADS[bar]:
            _add(mono, tb, pad(m, BAR + 0.6, 0.6 + 0.6 * grow))
            _add(mono, tb, pad(m + 12, BAR + 0.6, 0.35 * grow))
        # 16th-note synth ticks (from bar 1); faster brightness later
        if bar >= 1:
            notes = PLUCK_NOTES[bar]
            for i in range(16):
                acc = 1.0 if i % 4 == 0 else 0.6
                m = notes[i % 4] + (12 if bar >= 2 and i % 8 >= 4 else 0)
                _add(mono, tb + i * BAR / 16, pluck(m, 0.1, acc * grow, bright=1.0 + 0.3 * bar))
        # percussion
        if bar == 0:
            _add(mono, tb, kick(0.7))
            _add(mono, tb + 2 * BEAT, kick(0.55))
        elif bar == 1:
            for b in range(4):
                _add(mono, tb + b * BEAT, kick(0.9))
            for b in (1, 3):
                _add(mono, tb + b * BEAT, snare(0.85, seed=bar * 7 + b))
        else:  # bar 4: snare roll accelerating, kicks dropping out for tension
            _add(mono, tb, kick(0.8))
            n_hits = 0
            tt = 0.0
            step = BEAT / 2
            while tt < BAR - 0.02:
                _add(mono, tb + tt, snare(0.3 + 0.7 * tt / BAR, seed=200 + n_hits))
                n_hits += 1
                tt += step * (1 - 0.8 * tt / BAR)                # shorter and shorter gaps
    # lead motif: bars 2 and 3 (piano doubles it for clarity), rising run in bar 4
    for (b, m, ln) in MOTIF_A:
        _add(mono, 1 * BAR + b * BEAT, lead(m, ln * BEAT * 0.95, 1.0))
        _add(mono, 1 * BAR + b * BEAT, piano_note(m - 12, 0.85) * 0.55)
    run = [81, 83, 85, 86, 88, 89, 91, 93]                      # rising harmonic-minor run into the hit
    for i, m in enumerate(run):
        _add(mono, 2 * BAR + i * BAR / 8, lead(m, BAR / 8 * 0.9, 0.9 + 0.05 * i))
    # tension riser across the last two bars
    _add(mono, 1 * BAR, riser(2 * BAR)[: int(2 * BAR * SR)] * 0.9)
    # synchronised hits: bar 2 (motif enters), bar 4 (final build), and the big finish
    big_hit(mono, 1 * BAR, 0.75, chord=(38, 45, 50, 53))
    big_hit(mono, HIT, 1.25, chord=(26, 38, 45, 50, 53, 57, 62, 65, 69))
    _add(mono, HIT, piano_note(62, 1.0) * 1.1)
    _add(mono, HIT, piano_note(74, 1.0) * 0.9)
    # hall reverb, slightly different each side = wide stereo
    L = reverb(mono, np.random.default_rng(5), seconds=2.0, mix=0.24)
    R = reverb(mono * 0.98, np.random.default_rng(6), seconds=2.0, mix=0.24)
    st = np.stack([L, R], axis=1)
    fade = int(1.2 * SR)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st[: int(0.15 * SR)] *= np.linspace(0, 1, int(0.15 * SR))[:, None]
    st /= np.max(np.abs(st)) + 1e-9
    return st * 0.8


def save_wav(stereo, path):
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ pictures (synchronised to the music)
W, H = config.VIDEO_SIZE
FPS = 25


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _dark_gradient(warm):
    """Night-blue top to a warm glow at the bottom; `warm` (0..1) grows as the sun nears."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    top = (10, 10, 28)
    bot = (int(40 + 150 * warm), int(14 + 70 * warm), int(48 + 10 * warm))
    for y in range(H):
        t = (y / (H - 1)) ** 1.6
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(0, W, 1):
            px[x, y] = c
    return img


_GRAD = {}


def gradient_for(warm):
    key = round(warm * 20)
    if key not in _GRAD:
        _GRAD[key] = _dark_gradient(key / 20)
    return _GRAD[key]


def frame(t, fonts):
    title_font, tag_font, hindi_font, small_font = fonts
    warm = ease(t / HIT) * 0.9
    img = gradient_for(warm).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(H * 0.74)
    cx = W // 2
    # pulse rings on every beat (they get stronger as the music builds)
    for k in range(int(t / (2 * BEAT)) + 1):
        bt = k * 2 * BEAT
        age = t - bt
        if 0 <= age < 1.3 and bt < HIT + 0.01:
            r = int(40 + age * 620)
            a = int(max(0, (60 + 40 * bt / HIT) * (1 - age / 1.3) ** 1.5))
            d.ellipse([cx - r, horizon - r, cx + r, horizon + r], outline=(255, 214, 150, a), width=2)
    # horizontal light line that widens, then the sun slowly rises behind the horizon
    rise = ease(t / (HIT + 0.6))
    sun_y = horizon + 95 - rise * 122
    for g in range(7, 0, -1):
        rr = 60 + g * 16
        d.ellipse([cx - rr, sun_y - rr, cx + rr, sun_y + rr], fill=(255, 190, 110, int(10 + 12 * rise)))
    video._sun(d, cx, sun_y, 60)
    d.rectangle([0, horizon, W, H], fill=(20, 8, 30, 255))
    wline = int(W * ease(t / 1.0))
    d.rectangle([cx - wline // 2, horizon - 1, cx + wline // 2, horizon + 3], fill=(255, 205, 130, 255))
    # the question-motif moment (bar 3): small gold caption fades in
    if t >= 1 * BAR:
        p = ease((t - 1 * BAR) / 0.4) * (1 - ease((t - HIT + 0.4) / 0.3))
        txt = "T O D A Y ' S   G O O D   N E W S"
        w = d.textlength(txt, font=small_font)
        d.text(((W - w) / 2, 250), txt, font=small_font, fill=(255, 214, 150, int(255 * p)))
        bar_w = int(300 * ease((t - 1 * BAR) / 0.5))
        d.rectangle([cx - bar_w, 300, cx + bar_w, 303], fill=(255, 205, 130, int(255 * p)))
    # the final hit: white flash, title slams in
    if t >= HIT - 0.03:
        a = ease((t - HIT + 0.03) / 0.35)
        settle = 1 - ease((t - HIT) / 0.5)
        scale_off = int(26 * settle)
        title = "UPLIFT TODAY"
        tw = d.textlength(title, font=title_font)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rectangle([0, 80 - scale_off, W, 425 + scale_off], fill=(30, 8, 38, int(150 * a)))
        ld.text(((W - tw) / 2 + 5, 105 + 6), title, font=title_font, fill=(0, 0, 0, int(200 * a)))
        ld.text(((W - tw) / 2, 105), title, font=title_font, fill=(255, 255, 255, int(255 * a)),
                stroke_width=2, stroke_fill=(90, 20, 50, int(255 * a)))
        bl = int((tw / 2 + 50) * ease((t - HIT - 0.1) / 0.5))
        ld.rectangle([cx - bl, 252, cx + bl, 259], fill=(255, 200, 110, int(255 * a)))
        img = Image.alpha_composite(img, layer)
        d = ImageDraw.Draw(img, "RGBA")
        p2 = ease((t - HIT - 0.25) / 0.4)
        if p2 > 0:
            h = "आज की अच्छी खबरें"
            hw = d.textlength(h, font=hindi_font)
            d.text(((W - hw) / 2, 290 + (1 - p2) * 16), h, font=hindi_font, fill=(255, 236, 190, int(255 * p2)))
            tg = "Good news. Every day."
            tgw = d.textlength(tg, font=tag_font)
            d.text(((W - tgw) / 2, 364 + (1 - p2) * 16), tg, font=tag_font, fill=(255, 255, 255, int(235 * p2)))
    # fade in from black
    if t < 0.25:
        d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * (1 - t / 0.25))))
    return img.convert("RGB")


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    work = os.path.join(outdir, "_work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "theme.wav")
    save_wav(render_theme(), wav)
    fonts = (video._font(118, latin=True), video._font(44, latin=True), video._font(64), video._font(30, latin=True))
    n = int(TOTAL * FPS)
    for i in range(n):
        frame(i / FPS, fonts).save(os.path.join(work, f"f{i:04d}.png"))
    out = os.path.join(outdir, "intro.mp4")
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(work, "f%04d.png"),
        "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-af", "alimiter=limit=0.9:level=disabled",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", out])
    shutil.copy(wav, os.path.join(outdir, "theme_preview.wav"))
    shutil.rmtree(work)
    print("made", out, round(TOTAL, 2), "seconds")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "intro")
