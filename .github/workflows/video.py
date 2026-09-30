"""
video.py - Step 4: build the video. Each segment = a colourful still slide with
the headline + its narration audio. Then all segments are joined with ffmpeg.
(First version: still slides, no paid avatar. Stock footage and music come later.)
"""
import math
import os
import re
import subprocess
from PIL import Image, ImageDraw, ImageFont
import config

W, H = config.VIDEO_SIZE


def _font(size, latin=False):
    paths = config.LATIN_FONT_CANDIDATES if latin else config.FONT_CANDIDATES
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
            except Exception:
                return ImageFont.truetype(path, size)
    raise RuntimeError("No usable font found")


def _gradient():
    img = Image.new("RGB", (W, H))
    px = img.load()
    a, b = config.GRADIENT_TOP, config.GRADIENT_BOTTOM
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img


def _sun(d, cx, cy, r):
    col = (255, 244, 200)
    for i in range(12):
        ang = math.radians(i * 30)
        d.line(
            [(cx + math.cos(ang) * r * 1.25, cy + math.sin(ang) * r * 1.25),
             (cx + math.cos(ang) * r * 1.7, cy + math.sin(ang) * r * 1.7)],
            fill=col, width=max(3, int(r * 0.12)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def _wrap(d, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if d.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


_BG_CACHE = {}


def _photo_background(path):
    """Crop a photo to fill the frame and darken it so the text stays easy to read."""
    if path in _BG_CACHE:
        return _BG_CACHE[path].copy()
    src = Image.open(path).convert("RGB")
    scale = max(W / src.width, H / src.height)
    src = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1), Image.LANCZOS)
    left, top = (src.width - W) // 2, (src.height - H) // 2
    img = src.crop((left, top, left + W, top + H))
    shade = Image.new("RGBA", (W, H), (45, 10, 35, 120))        # warm dark tint over everything
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    _BG_CACHE[path] = img
    return img.copy()


def make_slide(text, out_png, is_title=False, caption=None, headline_en=None, background=None):
    img = _photo_background(background) if background else _gradient()
    d = ImageDraw.Draw(img)
    _sun(d, 110, 100, 40)
    small = _font(34, latin=True)
    d.text((190, 80), "UPLIFT TODAY  |  " + config.CHANNEL_HANDLE, font=small, fill=(255, 255, 255))
    size = 76 if is_title else 64
    font = _font(size)
    lines = _wrap(d, text, font, W - 160)[:5]
    line_h = int(size * 1.45)
    top = 40 if caption else 40
    y = (H - line_h * len(lines)) // 2 + (top - 60 if caption else 0)
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(255, 255, 255),
               stroke_width=3 if background else 0, stroke_fill=(45, 10, 35))
        y += line_h
    if headline_en:
        # English version of the headline: ONE line, shrunk to fit if needed
        size_en = 46
        efont = _font(size_en, latin=True)
        while d.textlength(headline_en, font=efont) > W - 160 and size_en > 26:
            size_en -= 2
            efont = _font(size_en, latin=True)
        w = d.textlength(headline_en, font=efont)
        d.text(((W - w) / 2, y + 4), headline_en, font=efont, fill=(255, 236, 190),
               stroke_width=2 if background else 0, stroke_fill=(45, 10, 35))
    if caption:
        cfont = _font(38, latin=True)
        clines = _wrap(d, caption, cfont, W - 200)[:3]
        box_h = int(38 * 1.45) * len(clines) + 30
        box = Image.new("RGBA", (W, box_h), (40, 10, 30, 150))
        img.paste(box, (0, H - box_h - 30), box)
        d = ImageDraw.Draw(img)
        cy = H - box_h - 30 + 15
        for ln in clines:
            w = d.textlength(ln, font=cfont)
            d.text(((W - w) / 2, cy), ln, font=cfont, fill=(255, 255, 255))
            cy += int(38 * 1.45)
    img.save(out_png)


def _duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path])
    return float(out.strip())


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


def intro_path():
    """Full path of the news-style opening, or None if it is switched off / missing."""
    if not getattr(config, "INTRO_CLIP", ""):
        return None
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.INTRO_CLIP)
    return p if os.path.exists(p) else None


def intro_length():
    p = intro_path()
    return _duration(p) if p else 0.0


def _talking_clip(seg, clip):
    """Re-encode the talking-presenter video to our format, exactly as long as the voice."""
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-i", seg["clip"], "-i", seg["audio"],
        "-map", "0:v", "-map", "1:a",
        "-vf", f"scale=-2:{H},crop={W}:{H},tpad=stop_mode=clone:stop_duration=3,fps=25,format=yuv420p",
        "-c:v", "libx264", "-r", "25", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-shortest", clip])


def build(segments, out_mp4, workdir):
    """segments = list of dicts: {"headline", "audio", "title_slide", "english"(optional), "clip"(optional)}"""
    clips = []
    opening = intro_path()
    if opening:
        clips.append(opening)
    for i, seg in enumerate(segments):
        clip = os.path.join(workdir, f"clip_{i}.mp4")
        if seg.get("clip"):
            _talking_clip(seg, clip)
            clips.append(clip)
            continue
        total = _duration(seg["audio"])
        sents = _sentences(seg.get("english")) if config.ENGLISH_CAPTIONS else []
        if not sents:
            sents = [None]
        weights = [max(len(s), 1) if s else 1 for s in sents]
        wsum = float(sum(weights))
        lines = []
        for k, sent in enumerate(sents):
            png = os.path.join(workdir, f"slide_{i}_{k}.png")
            bgs = [b for b in (seg.get("backgrounds") or []) if b]
            bg = bgs[min(int(k * len(bgs) / len(sents)), len(bgs) - 1)] if bgs else None
            make_slide(seg["headline"], png, is_title=seg.get("title_slide", False), caption=sent,
                       headline_en=seg.get("headline_en"), background=bg)
            lines.append(f"file '{os.path.abspath(png)}'")
            lines.append(f"duration {total * weights[k] / wsum:.3f}")
        lines.append(lines[-2])  # the concat demuxer needs the last image repeated
        imglist = os.path.join(workdir, f"imgs_{i}.txt")
        with open(imglist, "w") as f:
            f.write("\n".join(lines) + "\n")
        subprocess.check_call([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", imglist, "-i", seg["audio"],
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-shortest", clip])
        clips.append(clip)
    listfile = os.path.join(workdir, "list.txt")
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", listfile, "-c", "copy", out_mp4])
    return _duration(out_mp4)


def make_thumbnail(title, out_png):
    """Bold thumbnail: big sun, huge outlined title, readable on a phone."""
    img = _gradient()
    d = ImageDraw.Draw(img)
    _sun(d, W // 2, 160, 85)
    # dark band behind the title so it stays readable
    band = Image.new("RGBA", (W, 400), (60, 10, 40, 110))
    img.paste(band, (0, 320), band)
    d = ImageDraw.Draw(img)
    font = _font(104)
    lines = _wrap(d, title, font, W - 100)[:3]
    if len(lines) > 2:
        font = _font(84)
        lines = _wrap(d, title, font, W - 100)[:3]
    line_h = int(font.size * 1.3)
    y = 340 + (360 - line_h * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(255, 255, 255),
               stroke_width=7, stroke_fill=(70, 10, 50))
        y += line_h
    tag = _font(40, latin=True)
    label = "UPLIFT TODAY  |  " + config.CHANNEL_HANDLE
    w = d.textlength(label, font=tag)
    d.text(((W - w) / 2, 660), label, font=tag, fill=(255, 244, 200))
    img.save(out_png)
