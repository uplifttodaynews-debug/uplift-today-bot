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


# ------------------------------------------------------------------ news-report layout
# The picture sits in a framed window (like a report on a news channel) instead of running behind the text.
# A bright lower-third bar carries the headline, and the picture drifts in very slowly ("Ken Burns").
FRAME = (140, 30, 1000, 420)           # x, y, width, height of the picture window
BAR_Y, BAR_H = 462, 120
CAP_Y = 596
NAVY_TOP, NAVY_BOT = (10, 14, 46), (50, 16, 70)
CRIMSON = (216, 30, 91)
GOLD = (255, 194, 77)
PH_W, PH_H = int(FRAME[2] * 1.2), int(FRAME[3] * 1.2)    # a little larger than the window so it can zoom


def _backdrop():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * t) for i in range(3)))
    return img


def _fallback_art():
    """Sunrise picture used when no stock photo was found."""
    img = Image.new("RGB", (PH_W, PH_H))
    d = ImageDraw.Draw(img)
    a, b = config.GRADIENT_TOP, config.GRADIENT_BOTTOM
    for y in range(PH_H):
        t = y / (PH_H - 1)
        d.line([(0, y), (PH_W, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    _sun(d, PH_W // 2, PH_H // 2, 95)
    return img


def fit_photo(path, out_png):
    src = Image.open(path).convert("RGB") if path else _fallback_art()
    scale = max(PH_W / src.width, PH_H / src.height)
    src = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1), Image.LANCZOS)
    left, top = (src.width - PH_W) // 2, (src.height - PH_H) // 2
    src.crop((left, top, left + PH_W, top + PH_H)).save(out_png)
    return out_png


def _fit_size(d, text, max_w, start, stop, latin=False):
    size = start
    font = _font(size, latin=latin)
    while d.textlength(text, font=font) > max_w and size > stop:
        size -= 2
        font = _font(size, latin=latin)
    return font


def make_fixed_layers(headline, headline_en, tag, top_png, lower_png):
    """top_png: picture border + channel bug (always on).  lower_png: the lower-third bar (slides in)."""
    fx, fy, fw, fh = FRAME
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    d.rectangle([fx - 5, fy - 5, fx + fw + 4, fy + fh + 4], outline=(255, 255, 255, 255), width=5)
    d.rectangle([fx - 5, fy + fh + 4, fx + fw + 4, fy + fh + 10], fill=GOLD + (255,))
    pill = Image.new("RGBA", (330, 54), (10, 14, 46, 215))
    top.paste(pill, (fx + 16, fy + 16), pill)
    d = ImageDraw.Draw(top)
    _sun(d, fx + 16 + 30, fy + 16 + 27, 14)
    d.text((fx + 16 + 62, fy + 16 + 9), "UPLIFT TODAY", font=_font(30, latin=True), fill=(255, 255, 255, 255))
    top.save(top_png)

    low = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(low)
    tag_w = 220
    d.rectangle([fx, BAR_Y, fx + tag_w, BAR_Y + BAR_H], fill=GOLD + (255,))
    small, big = tag if tag else ("", "")
    if small:
        sf = _font(24, latin=True)
        sw = d.textlength(small, font=sf)
        d.text((fx + (tag_w - sw) / 2, BAR_Y + 14), small, font=sf, fill=(10, 14, 46, 255))
    if big:
        bf = _fit_size(d, big, tag_w - 24, 58, 24, latin=True)
        bw = d.textlength(big, font=bf)
        d.text((fx + (tag_w - bw) / 2, BAR_Y + 44), big, font=bf, fill=(10, 14, 46, 255))
    bx0, bx1 = fx + tag_w, fx + fw
    d.rectangle([bx0, BAR_Y, bx1, BAR_Y + BAR_H], fill=CRIMSON + (255,))
    d.rectangle([bx0, BAR_Y, bx1, BAR_Y + 4], fill=(255, 255, 255, 255))
    maxw = bx1 - bx0 - 40
    hf = _fit_size(d, headline, maxw, 54, 36)
    lines = [headline] if d.textlength(headline, font=hf) <= maxw else _wrap(d, headline, hf, maxw)[:2]
    y = BAR_Y + 14
    for ln in lines:
        d.text((bx0 + 20, y), ln, font=hf, fill=(255, 255, 255, 255))
        y += int(hf.size * 1.3)
    if headline_en:
        ef = _fit_size(d, headline_en, maxw, 30, 20, latin=True)
        d.text((bx0 + 20, BAR_Y + BAR_H - 14 - ef.size * 1.2), headline_en, font=ef, fill=(255, 226, 150, 255))
    low.save(lower_png)


def make_base(caption, out_png):
    """Backdrop + caption strip (changes with every sentence)."""
    img = _backdrop()
    fx, fy, fw, fh = FRAME
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([fx + 10, fy + 10, fx + fw + 14, fy + fh + 14], fill=(0, 0, 0, 120))     # soft shadow
    if caption:
        cf = _font(34, latin=True)
        clines = _wrap(d, caption, cf, W - 240)[:2]
        box_h = int(34 * 1.4) * len(clines) + 22
        y0 = CAP_Y + (H - CAP_Y - box_h) // 2 - 6
        d.rectangle([0, y0 - 6, W, y0 + box_h], fill=(6, 8, 30, 235))
        cy = y0 + 8
        for ln in clines:
            w = d.textlength(ln, font=cf)
            d.text(((W - w) / 2, cy), ln, font=cf, fill=(255, 255, 255, 255))
            cy += int(34 * 1.4)
    img.save(out_png)


def _render_piece(base, photo, top, lower, dur, offset, first, out):
    """One sentence: slow zoom on the picture, bar slides in on the first sentence of a story."""
    fx, fy, fw, fh = FRAME
    zoom = f"min(1.0+0.00045*(on+{offset}),1.2)"
    slide = ("overlay=x='-w*pow(1-min(t/0.5,1),2)':y=0" if first else "overlay=0:0")
    filt = (
        f"[1:v]zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={fw}x{fh}:fps=25[p];"
        f"[0:v][p]overlay={fx}:{fy}[a];[a][2:v]overlay=0:0[b];[b][3:v]{slide}[v]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in (base, photo, top, lower):
        cmd += ["-loop", "1", "-framerate", "25", "-t", f"{dur:.3f}", "-i", p]
    cmd += ["-filter_complex", filt, "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "25", "-t", f"{dur:.3f}", out]
    subprocess.check_call(cmd)


def build(segments, out_mp4, workdir):
    """segments = list of dicts: {"headline", "audio", "english", "headline_en", "tag", "backgrounds", "clip"(optional)}"""
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
        bgs = [b for b in (seg.get("backgrounds") or []) if b]
        top_png = os.path.join(workdir, f"top_{i}.png")
        lower_png = os.path.join(workdir, f"lower_{i}.png")
        make_fixed_layers(seg["headline"], seg.get("headline_en"), seg.get("tag"), top_png, lower_png)
        fits, last_key, offset, pieces = {}, None, 0, []
        for k, sent in enumerate(sents):
            dur = total * weights[k] / wsum
            bg = bgs[min(int(k * len(bgs) / len(sents)), len(bgs) - 1)] if bgs else None
            key = bg or "fallback"
            if key not in fits:
                fits[key] = fit_photo(bg, os.path.join(workdir, f"photo_{i}_{len(fits)}.png"))
            if key != last_key:
                offset, last_key = 0, key
            base = os.path.join(workdir, f"base_{i}_{k}.png")
            make_base(sent, base)
            piece = os.path.join(workdir, f"piece_{i}_{k}.mp4")
            _render_piece(base, fits[key], top_png, lower_png, dur, offset, k == 0, piece)
            offset += int(round(dur * 25))
            pieces.append(piece)
        plist = os.path.join(workdir, f"pieces_{i}.txt")
        with open(plist, "w") as f:
            for p in pieces:
                f.write(f"file '{os.path.abspath(p)}'\n")
        subprocess.check_call([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", plist, "-i", seg["audio"],
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
            "-ac", "2", "-shortest", clip])
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
