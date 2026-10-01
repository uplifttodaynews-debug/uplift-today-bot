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


import math as _m

_CACHE2 = {}
SS = 2


def _sky():
    a = np.zeros((H, W, 3), dtype=np.float32)
    ys = np.linspace(0, 1, H)[:, None]
    top = np.array([22, 104, 214], dtype=np.float32)
    mid = np.array([70, 170, 248], dtype=np.float32)
    low = np.array([255, 215, 140], dtype=np.float32)
    k = np.clip(ys / 0.55, 0, 1)
    c1 = top + (mid - top) * k
    k2 = np.clip((ys - 0.5) / 0.35, 0, 1) ** 1.3
    c = c1 + (low - c1) * k2
    a[:] = c[:, None, :] if c.ndim == 2 else c
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "RGB")


def _glow_layer():
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / 1.5) ** 2 + (yy - 500) ** 2)
    al = np.clip(1 - d / 330, 0, 1) ** 1.6
    img = np.zeros((H, W, 4), dtype=np.uint8)
    img[..., 0] = 255
    img[..., 1] = 205
    img[..., 2] = 90
    img[..., 3] = (al * 230).astype("uint8")
    return Image.fromarray(img, "RGBA")


def _clouds():
    """Crisp, smooth cumulus (union of circles, drawn at 2x), white on top fading to warm gold underneath."""
    rng = np.random.default_rng(11)
    S = 2
    mask = Image.new("L", (W * S, H * S), 0)
    d = ImageDraw.Draw(mask)

    def puff(cx, base, width, height):
        n = int(width / 26)
        for i in range(n):
            u = (i + rng.uniform(0.2, 0.8)) / n
            hump = 1 - abs(2 * u - 1) ** 1.8
            r = rng.uniform(0.4, 0.6) * height * (0.4 + 0.7 * hump)
            x, y = cx - width / 2 + u * width, base - r * 0.55
            d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=255)
        d.rectangle([(cx - width / 2 - r) * S, base * S, (cx + width / 2 + r) * S, (base + 200) * S], fill=0)

    puff(70, 470, 380, 130)
    puff(215, 480, 220, 80)
    puff(W - 80, 470, 400, 140)
    puff(W - 250, 485, 200, 70)
    mask = mask.resize((W, H), Image.LANCZOS)
    ys = np.linspace(0, 1, H)[:, None, None]
    y0, y1 = 345, 450
    k = np.clip((ys - y0) / (y1 - y0), 0, 1)
    top, bot = np.array([255, 253, 248]), np.array([255, 190, 120])
    col = (top * (1 - k) + bot * k)
    col = np.repeat(col, W, axis=1).astype("uint8")
    lay = Image.fromarray(col, "RGB").convert("RGBA")
    lay.putalpha(mask)
    return lay


def _grad(h, c0, c1):
    a = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(c0)[None, None, :] * (1 - a) + np.array(c1)[None, None, :] * a
    arr = np.repeat(arr, W * SS, axis=1)
    return Image.fromarray(arr.astype("uint8"), "RGB")


def _waves(t):
    """Three layered hills drawn at 2x and shrunk (smooth edges); they gently drift."""
    w2, h2 = W * SS, H * SS
    out = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))

    def band(top_fn, c0, c1, line=None):
        pts = [(x, top_fn(x / SS) * SS) for x in range(0, w2 + 1, 8)]
        mask = Image.new("L", (w2, h2), 0)
        ImageDraw.Draw(mask).polygon(pts + [(w2, h2), (0, h2)], fill=255)
        g = _grad(h2, c0, c1)
        out.paste(g, (0, 0), mask)
        if line:
            ImageDraw.Draw(out).line(pts, fill=line, width=SS * 3)

    ph = t * 1.1
    # back: golden-orange hills, high at both sides, low in the middle
    band(lambda x: 575 - 150 * (abs(2 * x / W - 1) ** 1.6) + 7 * _m.sin(x / 95 + ph),
         (255, 196, 40), (255, 120, 15), line=(255, 240, 150, 255))
    # middle: orange to red stripe
    band(lambda x: 610 - 40 * (2 * x / W - 1) ** 2 + 9 * _m.sin(x / 120 + ph * 1.3 + 1.5),
         (255, 150, 25), (250, 70, 30), line=(255, 220, 120, 255))
    # front: deep blue water
    band(lambda x: 640 + 12 * _m.sin(x / 150 + ph * 0.9 + 3) + 10 * (2 * x / W - 1),
         (20, 130, 235), (8, 50, 160), line=(70, 210, 255, 255))
    return out.resize((W, H), Image.LANCZOS)


def _gold_text(layer, xy, text, font):
    """Gold gradient letters with a dark-gold 3D edge."""
    x, y = xy
    ld = ImageDraw.Draw(layer)
    for i in range(10, 0, -1):
        ld.text((x + i * 0.7, y + i), text, font=font, fill=(176, 96, 8, 255))
    mask = Image.new("L", layer.size, 0)
    ImageDraw.Draw(mask).text((x, y), text, font=font, fill=255)
    g = _grad(H, (255, 240, 110), (255, 150, 15)).resize(layer.size)
    layer.paste(g, (0, 0), mask)


def frame(t, fonts):
    title_font, tag_font, hindi_font, small_font = fonts
    if "sky" not in _CACHE2:
        _CACHE2["sky"] = _sky().convert("RGBA")
        _CACHE2["glow"] = _glow_layer()
        _CACHE2["clouds"] = _clouds()
    cx = W // 2
    img = _CACHE2["sky"].copy()
    glow = _CACHE2["glow"].copy()
    glow.putalpha(glow.getchannel("A").point(lambda v: int(v * (0.65 + 0.35 * ease(t / HIT)))))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, _CACHE2["clouds"])
    d = ImageDraw.Draw(img, "RGBA")
    # the sun rises from behind the hills; its rays grow
    rise = ease(t / (HIT + 0.4))
    sun_y = 640 - rise * 125
    r = 104
    ray = ease(t / (HIT - 0.5))
    for i in range(9):
        ang = _m.radians(180 + 20 + i * 17.5)
        r0, r1 = r * 1.2, r * (1.28 + 0.3 * ray)
        d.line([(cx + _m.cos(ang) * r0, sun_y + _m.sin(ang) * r0), (cx + _m.cos(ang) * r1, sun_y + _m.sin(ang) * r1)],
               fill=(255, 226, 90, 255), width=7)
    sun = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
    sg = _grad(2 * r, (255, 236, 90), (255, 150, 15)).resize((2 * r, 2 * r))
    m = Image.new("L", (2 * r * 4, 2 * r * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 2 * r * 4 - 1, 2 * r * 4 - 1], fill=255)
    m = m.resize((2 * r, 2 * r), Image.LANCZOS)
    img.paste(sg, (cx - r, int(sun_y - r)), m)
    # thin golden arc drawn across the top
    arc = ease((t - 0.2) / (HIT - 0.4))
    if arc > 0:
        R = 640
        a0 = 180 + (1 - arc) * 0.0
        sweep = 180 * arc
        bbox = [cx - R, 640 - R, cx + R, 640 + R]
        d.arc(bbox, 270 - sweep / 2, 270 + sweep / 2, fill=(255, 205, 60, 255), width=4)
    img = Image.alpha_composite(img, _waves(t))
    d = ImageDraw.Draw(img, "RGBA")
    # soft beat pulses of light from the sun
    for k in range(int(t / (2 * BEAT)) + 1):
        bt = k * 2 * BEAT
        age = t - bt
        if 0 <= age < 1.0 and bt < HIT + 0.01:
            rr = int(60 + age * 500)
            a = int(max(0, (30 + 20 * bt / HIT) * (1 - age / 1.0) ** 1.5))
            d.ellipse([cx - rr, sun_y - rr, cx + rr, sun_y + rr], outline=(255, 245, 200, a), width=3)
    # small caption before the title
    p = 1.0 * (1 - ease((t - HIT + 0.4) / 0.3))
    if p > 0.01:
        txt = "T O D A Y ' S   U P L I F T I N G   N E W S"
        w = d.textlength(txt, font=small_font)
        d.text(((W - w) / 2 + 2, 172), txt, font=small_font, fill=(10, 50, 130, int(150 * p)))
        d.text(((W - w) / 2, 170), txt, font=small_font, fill=(255, 255, 255, int(255 * p)))
        bw = int(300 * ease(max(t, 0.02) / 0.4 + 0.05))
        d.rounded_rectangle([cx - bw, 222, cx + bw, 227], radius=3, fill=(255, 205, 60, int(255 * p)))
    # the big hit: the title slams in
    if t >= HIT - 0.03:
        a = ease((t - HIT + 0.03) / 0.3)
        drop = int(30 * (1 - ease((t - HIT) / 0.45)))
        up, td = "UPLIFT", "TODAY"
        uw, gw = d.textlength(up + " ", font=title_font), d.textlength(td, font=title_font)
        x0 = (W - (uw + gw)) / 2
        y0 = 72 - drop
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i in range(10, 0, -1):
            ld.text((x0 + i * 0.7, y0 + i), up, font=title_font, fill=(120, 150, 205, 255))
        ld.text((x0, y0), up, font=title_font, fill=(255, 255, 255, 255))
        _gold_text(layer, (x0 + uw, y0), td, title_font)
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
        img = Image.alpha_composite(img, layer)
        d = ImageDraw.Draw(img, "RGBA")
        bl = int(((uw + gw) / 2) * ease((t - HIT - 0.1) / 0.5))
        yl = y0 + 170
        d.rounded_rectangle([cx - bl, yl, cx + bl, yl + 7], radius=4, fill=(255, 205, 40, int(255 * a)))
        p2 = ease((t - HIT - 0.25) / 0.4)
        if p2 > 0:
            h = "आज की अच्छी खबरें"
            hw = d.textlength(h, font=hindi_font)
            d.text(((W - hw) / 2 + 2, yl + 22 + (1 - p2) * 14 + 2), h, font=hindi_font, fill=(10, 50, 130, int(170 * p2)))
            d.text(((W - hw) / 2, yl + 22 + (1 - p2) * 14), h, font=hindi_font, fill=(255, 255, 255, int(255 * p2)))
    return img.convert("RGB")


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    work = os.path.join(outdir, "_work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "theme.wav")
    save_wav(render_theme(), wav)
    fonts = (video._font(122, latin=True), video._font(44, latin=True), video._font(54), video._font(30, latin=True))
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
