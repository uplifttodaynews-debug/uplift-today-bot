"""
video.py - Step 4: build the video. Each segment = a colourful still slide with
the headline + its narration audio. Then all segments are joined with ffmpeg.
(First version: still slides, no paid avatar. Stock footage and music come later.)
"""
import math
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import config

W, H = config.VIDEO_SIZE


def _font(size):
    for path in config.FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
            except Exception:
                return ImageFont.truetype(path, size)
    raise RuntimeError("No Hindi-capable font found")


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


def make_slide(text, out_png, is_title=False):
    img = _gradient()
    d = ImageDraw.Draw(img)
    _sun(d, 110, 100, 40)
    small = _font(34)
    d.text((190, 80), "UPLIFT TODAY  |  " + config.CHANNEL_HANDLE, font=small, fill=(255, 255, 255))
    size = 76 if is_title else 64
    font = _font(size)
    lines = _wrap(d, text, font, W - 160)[:5]
    line_h = int(size * 1.45)
    y = (H - line_h * len(lines)) // 2 + 40
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(255, 255, 255))
        y += line_h
    img.save(out_png)


def _duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path])
    return float(out.strip())


def build(segments, out_mp4, workdir):
    """segments = list of dicts: {"headline": str, "audio": mp3 path, "title_slide": bool}"""
    clips = []
    for i, seg in enumerate(segments):
        png = os.path.join(workdir, f"slide_{i}.png")
        clip = os.path.join(workdir, f"clip_{i}.mp4")
        make_slide(seg["headline"], png, is_title=seg.get("title_slide", False))
        subprocess.check_call([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", png, "-i", seg["audio"],
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-r", "25", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
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
    img = _gradient()
    d = ImageDraw.Draw(img)
    _sun(d, W // 2, 190, 90)
    font = _font(84)
    lines = _wrap(d, title, font, W - 120)[:3]
    y = 360
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(255, 255, 255))
        y += 120
    img.save(out_png)
