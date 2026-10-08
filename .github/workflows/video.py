"""
video.py - Step 4: build the video. Each segment = a colourful still slide with
the headline + its narration audio. Then all segments are joined with ffmpeg.
(First version: still slides, no paid avatar. Stock footage and music come later.)
"""
import math
import os
import re
import subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont
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
    col = (255, 150, 30)
    for i in range(12):
        ang = math.radians(i * 30)
        d.line(
            [(cx + math.cos(ang) * r * 1.25, cy + math.sin(ang) * r * 1.25),
             (cx + math.cos(ang) * r * 1.7, cy + math.sin(ang) * r * 1.7)],
            fill=col, width=max(3, int(r * 0.12)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def _draw_mixed(d, xy, text, size, **kw):
    """Draw Hindi text, but words written in English letters (e.g. AI) with the Latin font so they never show as boxes."""
    x, y = xy
    hi, la = _font(size), _font(size, latin=True)
    sp = d.textlength(" ", font=hi)
    for w in text.split(" "):
        f = la if w.isascii() and any(c.isalpha() for c in w) else hi
        d.text((x, y), w, font=f, **kw)
        x += d.textlength(w, font=f) + sp


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
        "-vf", f"scale=-2:{H},crop={W}:{H},"
               f"crop=iw/{config.ANCHOR_ZOOM}:ih/{config.ANCHOR_ZOOM}:(iw-iw/{config.ANCHOR_ZOOM})/2:0,scale={W}:{H},tpad=stop_mode=clone:stop_duration=3,fps=25,format=yuv420p",
        "-c:v", "libx264", "-r", "25", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-shortest", clip])


# ------------------------------------------------------------------ TV-news set layout
# Studio backdrop, a framed picture window (like the report window on a news channel), a white
# lower-third bar with a blue label tab and the channel logo, an English caption strip, a date box
# and a scrolling news ticker. Colours: blue / white / black (no red or yellow).
FRAME = (180, 62, 920, 372)            # x, y, width, height of the picture window
TAB_Y, TAB_H = 438, 28
BAR_X0, BAR_X1, BAR_Y, BAR_H = 50, 1230, 466, 96
CAP_Y, CAP_H = 572, 76
TICK_Y, TICK_H = 662, 58
BLUE = (18, 76, 172)
NAVY = (8, 22, 64)
WHITE = (255, 255, 255)
SUN = (255, 196, 40)                      # the golden of the sun in the intro
INK = (14, 14, 20)
GREY = (70, 82, 112)
ZOOM_RATE, ZOOM_MAX = 0.00035, 1.18     # very slow, smooth push-in
PH_W, PH_H = int(FRAME[2] * 1.25), int(FRAME[3] * 1.25)
TICK_SPEED = 90                          # pixels per second
_STUDIO = {}


def _studio():
    if "img" in _STUDIO:
        return _STUDIO["img"].copy()
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio", "studio.jpg")
    if os.path.exists(p):
        src = Image.open(p).convert("RGB")
        scale = max(W / src.width, H / src.height)
        src = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1), Image.LANCZOS)
        left, top = (src.width - W) // 2, (src.height - H) // 2
        img = src.crop((left, top, left + W, top + H))
        img = img.filter(ImageFilter.GaussianBlur(2.2))
        shade = Image.new("RGBA", (W, H), (4, 10, 36, 105))
        img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    else:
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = y / (H - 1)
            d.line([(0, y), (W, y)], fill=(int(8 + 20 * t), int(18 + 30 * t), int(60 + 50 * t)))
    _STUDIO["img"] = img
    return img.copy()


def _fallback_art():
    """Sunrise picture used when no suitable stock photo was found."""
    img = Image.new("RGB", (PH_W, PH_H))
    d = ImageDraw.Draw(img)
    a, b = config.GRADIENT_TOP, config.GRADIENT_BOTTOM
    for y in range(PH_H):
        t = y / (PH_H - 1)
        d.line([(0, y), (PH_W, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    _sun(d, PH_W // 2, PH_H // 2, 95)
    return img


def _headline_card(text):
    """Plain blue news graphic with the story headline - used when no photo or clip clearly fits a story."""
    img = Image.new("RGB", (PH_W, PH_H))
    d = ImageDraw.Draw(img)
    for y in range(PH_H):
        t = y / (PH_H - 1)
        d.line([(0, y), (PH_W, y)], fill=tuple(int(BLUE[i] + (NAVY[i] - BLUE[i]) * t) for i in range(3)))
    font = _font(64, latin=True)
    lines = _wrap(d, text or "Uplift Today", font, int(PH_W * 0.8))[:3]
    lh = int(64 * 1.25)
    y = (PH_H - lh * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((PH_W - w) / 2, y), ln, font=font, fill=WHITE)
        y += lh
    d.rectangle([PH_W // 2 - 90, y + 10, PH_W // 2 + 90, y + 14], fill=WHITE)
    return img


def fit_photo(path, out_png, card_text=None):
    src = Image.open(path).convert("RGB") if path else (_headline_card(card_text) if card_text else _fallback_art())
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


def _spaced(d, x, y, text, font, fill, gap=2):
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + gap
    return x


def make_fixed_layers(headline, headline_en, tag, date_text, top_png, lower_png):
    """top_png: picture border, date box, ticker label (always on). lower_png: tab + white bar (slides in)."""
    fx, fy, fw, fh = FRAME
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    d.rectangle([fx - 4, fy - 4, fx + fw + 3, fy + fh + 3], outline=WHITE + (255,), width=4)
    # date box, top right (black with white text)
    df = _font(26, latin=True)
    dw = d.textlength(date_text, font=df)
    d.rectangle([W - 40 - dw - 36, 14, W - 14, 52], fill=(0, 0, 0, 235))
    d.text((W - 14 - dw - 18, 18), date_text, font=df, fill=WHITE + (255,))
    # ticker label at the left of the ticker strip
    d.rectangle([0, TICK_Y, 172, TICK_Y + TICK_H], fill=BLUE + (255,))
    lf = _font(28, latin=True)
    lt = "LATEST"
    d.text(((172 - d.textlength(lt, font=lf)) / 2, TICK_Y + 13), lt, font=lf, fill=WHITE + (255,))
    top.save(top_png)

    low = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(low)
    small, big = tag if tag else ("", "")
    tab_text = (small + " " + big).strip() or "GOOD NEWS"
    tf = _font(20, latin=True)
    tw = sum(d.textlength(c, font=tf) + 2 for c in tab_text)
    d.rectangle([BAR_X0, TAB_Y, BAR_X0 + tw + 40, TAB_Y + TAB_H], fill=BLUE + (255,))
    _spaced(d, BAR_X0 + 20, TAB_Y + 3, tab_text, tf, WHITE + (255,))
    d.rectangle([BAR_X0, BAR_Y, BAR_X1, BAR_Y + BAR_H], fill=WHITE + (255,))
    d.rectangle([BAR_X0, BAR_Y, BAR_X0 + 8, BAR_Y + BAR_H], fill=BLUE + (255,))
    # channel logo block at the right end of the bar
    lx0 = BAR_X1 - 270
    d.rectangle([lx0, BAR_Y, BAR_X1, BAR_Y + BAR_H], fill=NAVY + (255,))
    _sun(d, lx0 + 52, BAR_Y + BAR_H // 2, 18)
    d.text((lx0 + 92, BAR_Y + 16), "UPLIFT", font=_font(30, latin=True), fill=WHITE + (255,))
    d.text((lx0 + 92, BAR_Y + 50), "TODAY", font=_font(30, latin=True), fill=(170, 205, 255, 255))
    maxw = lx0 - BAR_X0 - 44
    hf = _fit_size(d, headline, maxw, 46, 30)
    lines = [headline] if d.textlength(headline, font=hf) <= maxw else _wrap(d, headline, hf, maxw)[:2]
    y = BAR_Y + 6
    for ln in lines:
        d.text((BAR_X0 + 26, y), ln, font=hf, fill=INK + (255,))
        y += int(hf.size * 1.28)
    if headline_en and len(lines) == 1:
        ef = _fit_size(d, headline_en, maxw, 26, 18, latin=True)
        d.text((BAR_X0 + 26, BAR_Y + BAR_H - 10 - int(ef.size * 1.25)), headline_en, font=ef, fill=GREY + (255,))
    low.save(lower_png)


def make_ticker(items, out_png):
    """One long strip of text for the scrolling ticker (the same text twice, so it can wrap around)."""
    f = _font(28, latin=True)
    one = "   \u2022   ".join(["UPLIFT TODAY - GOOD NEWS"] + [i for i in items if i]) + "   \u2022   "
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    L = int(probe.textlength(one, font=f)) + 4
    img = Image.new("RGBA", (L * 2 + W, TICK_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((0, 11), one, font=f, fill=SUN + (255,))
    d.text((L, 11), one, font=f, fill=SUN + (255,))
    d.text((2 * L, 11), one, font=f, fill=SUN + (255,))
    img.save(out_png)
    return L


def make_base(caption, out_png):
    """Studio backdrop + picture shadow + caption strip + ticker strip (the caption changes every sentence)."""
    img = _studio()
    fx, fy, fw, fh = FRAME
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([fx + 8, fy + 8, fx + fw + 12, fy + fh + 12], fill=(0, 0, 0, 120))
    d.rectangle([0, TICK_Y, W, TICK_Y + TICK_H], fill=NAVY + (250,))
    if caption:
        cf = _font(32, latin=True)
        clines = _wrap(d, caption, cf, W - 260)[:2]
        d.rectangle([BAR_X0, CAP_Y, BAR_X1, CAP_Y + CAP_H], fill=(5, 12, 40, 225))
        lh = int(32 * 1.3)
        cy = CAP_Y + (CAP_H - lh * len(clines)) // 2 - 2
        for ln in clines:
            w = d.textlength(ln, font=cf)
            d.text(((W - w) / 2, cy), ln, font=cf, fill=WHITE + (255,))
            cy += lh
    img.save(out_png)


def _render_piece(base, photo_png, top, lower, ticker, ticker_len, dur, offset, first, gt, out):
    """One sentence of a story. The picture is zoomed frame by frame with exact sub-pixel maths (no shaking)."""
    fx, fy, fw, fh = FRAME
    n = max(int(round(dur * 25)), 1)
    slide = ("overlay=x='-w*pow(1-min(t/0.5,1),2)':y=0" if first else "overlay=0:0")
    is_video = str(photo_png).lower().endswith(".mp4")
    pic = (f"[4:v]scale={fw}:{fh}:force_original_aspect_ratio=increase,crop={fw}:{fh},fps=25,setsar=1,"
           "format=yuv420p[vid];[0:v][vid]") if is_video else "[0:v][4:v]"
    filt = (
        f"{pic}overlay={fx}:{fy}[a];"
        f"[a][3:v]overlay=x='-mod({TICK_SPEED}*(t+{gt:.3f}),{ticker_len})':y={TICK_Y}[b];"
        f"[b][1:v]overlay=0:0[c];[c][2:v]{slide}[v]"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in (base, top, lower, ticker):
        cmd += ["-loop", "1", "-framerate", "25", "-t", f"{dur:.3f}", "-i", p]
    if is_video:
        cl = _duration(photo_png) or 5.0
        start = (offset / 25.0) % max(cl - 0.5, 1.0)
        cmd += ["-stream_loop", "-1", "-ss", f"{start:.3f}", "-i", photo_png]
    else:
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{fw}x{fh}", "-framerate", "25", "-i", "pipe:0"]
    cmd += ["-filter_complex", filt, "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "25", "-frames:v", str(n), out]
    if is_video:
        subprocess.check_call(cmd)
        return
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    src = Image.open(photo_png).convert("RGB")
    try:
        for f in range(n):
            z = min(1.0 + ZOOM_RATE * (offset + f), ZOOM_MAX)
            ww, hh = PH_W / z, PH_H / z
            im = src.transform((fw, fh), Image.AFFINE,
                               (ww / fw, 0, (PH_W - ww) / 2, 0, hh / fh, (PH_H - hh) / 2),
                               resample=Image.BICUBIC)
            proc.stdin.write(im.tobytes())
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg failed while drawing a story clip")


def _dissolve(a, b, out, fade=0.35, kind="fade", whoosh=False):
    """Presenter clip `a` dissolves into news clip `b`; length and sound stay exactly a + b.
    kind = any ffmpeg xfade style; whoosh adds a soft swoosh sound at the join."""
    da = _duration(a)
    if whoosh:
        ms = max(int((da - fade - 0.05) * 1000), 0)
        audio = (f"anoisesrc=d=0.6:c=pink:a=0.5,highpass=f=700,lowpass=f=7000,afade=t=in:d=0.25,"
                 f"afade=t=out:st=0.25:d=0.35,volume=0.6,adelay={ms}|{ms},aformat=sample_rates=44100:channel_layouts=stereo[w];"
                 "[0:a][1:a]concat=n=2:v=0:a=1,aformat=sample_rates=44100:channel_layouts=stereo[ac];"
                 "[ac][w]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        audio = "[0:a][1:a]concat=n=2:v=0:a=1[a]"
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-i", a, "-i", b, "-filter_complex",
        f"[1:v]tpad=start_duration={fade}:start_mode=clone[b];"
        f"[0:v][b]xfade=transition={kind}:duration={fade}:offset={da - fade:.3f},format=yuv420p[v];"
        + audio,
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "25",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", out])


def build(segments, out_mp4, workdir):
    """segments = list of dicts: {"headline", "audio", "english", "headline_en", "tag", "backgrounds", "clip"(optional)}"""
    import datetime
    _d = config.today_india()
    date_text = f"{_d.day} {_d.strftime('%B').upper()} {_d.year}"      # Indian style: 7 OCTOBER 2026
    ticker_png = os.path.join(workdir, "ticker.png")
    ticker_len = make_ticker([sg.get("headline_en") for sg in segments if (sg.get("tag") or ("",))[0] == "STORY"], ticker_png)
    clips = []
    pending = None
    gt = 0.0
    fancy = (config.today_india().isoformat() in getattr(config, "TRANSITION_DAYS", set())
             or os.environ.get("FORCE_TRANSITIONS") == "1")
    styles = ["circleopen", "slideleft", "radial", "diagtl", "zoomin", "smoothleft"]
    prev_news, n_tr = False, 0
    opening = intro_path()
    if opening:
        clips.append(opening)
        gt += _duration(opening)
    for i, seg in enumerate(segments):
        clip = os.path.join(workdir, f"clip_{i}.mp4")
        total = _duration(seg["audio"])
        if seg.get("clip"):
            _talking_clip(seg, clip)
            clips.append(clip)
            pending = clip
            gt += total
            continue
        sents = _sentences(seg.get("english")) if config.ENGLISH_CAPTIONS else []
        if not sents:
            sents = [None]
        weights = [max(len(s), 1) if s else 1 for s in sents]
        wsum = float(sum(weights))
        bgs = [b for b in (seg.get("backgrounds") or []) if b]
        top_png = os.path.join(workdir, f"top_{i}.png")
        lower_png = os.path.join(workdir, f"lower_{i}.png")
        make_fixed_layers(seg["headline"], seg.get("headline_en"), seg.get("tag"), date_text, top_png, lower_png)
        fits, last_key, offset, pieces = {}, None, 0, []
        for k, sent in enumerate(sents):
            dur = total * weights[k] / wsum
            bg = bgs[min(int(k * len(bgs) / len(sents)), len(bgs) - 1)] if bgs else None
            key = bg or "fallback"
            if key not in fits and bg and str(bg).lower().endswith(".mp4"):
                fits[key] = bg
            if key not in fits:
                is_story = (seg.get("tag") or ("",))[0] == "STORY"
                fits[key] = fit_photo(bg, os.path.join(workdir, f"photo_{i}_{len(fits)}.png"),
                                      card_text=(seg.get("headline_en") or seg.get("headline")) if (is_story and not bg) else None)
            if key != last_key:
                offset, last_key = 0, key
            base = os.path.join(workdir, f"base_{i}_{k}.png")
            make_base(sent, base)
            piece = os.path.join(workdir, f"piece_{i}_{k}.mp4")
            _render_piece(base, fits[key], top_png, lower_png, ticker_png, ticker_len, dur, offset, k == 0, gt, piece)
            offset += int(round(dur * 25))
            gt += dur
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
        if pending:                                   # soft dissolve from the presenter into the news set
            try:
                merged = os.path.join(workdir, f"merged_{i}.mp4")
                _dissolve(pending, clip, merged)
                clips.pop()
                clips.pop()
                clips.append(merged)
            except Exception as e:
                print(f"[video] dissolve skipped: {e}")
            pending = None
        elif fancy and prev_news and len(clips) >= 2:     # short dynamic transition between news pieces
            try:
                merged = os.path.join(workdir, f"trans_{i}.mp4")
                _dissolve(clips[-2], clips[-1], merged, fade=0.8, kind=styles[n_tr % len(styles)], whoosh=True)
                clips.pop()
                clips.pop()
                clips.append(merged)
                n_tr += 1
            except Exception as e:
                print(f"[video] transition skipped: {e}")
        prev_news = (seg.get("tag") or ("",))[0] != "UPLIFT"
    listfile = os.path.join(workdir, "list.txt")
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", listfile, "-c", "copy", out_mp4])
    return _duration(out_mp4)


def make_thumbnail(title, out_png, photo_path=None, subtitle="आज की पॉज़िटिव ख़बरें"):
    """Thumbnail: a strong story photo full-bleed, dark-blue fade on the left for the big headline,
    gold channel badge and a sun mark. Without a photo it falls back to the blue-sky / golden-sun design."""
    import math
    img = None
    if photo_path and os.path.exists(photo_path):
        try:
            src = Image.open(photo_path).convert("RGB")
            sc = max(W / src.width, H / src.height)
            src = src.resize((int(src.width * sc) + 1, int(src.height * sc) + 1), Image.LANCZOS)
            l, t = (src.width - W) // 2, (src.height - H) // 2
            img = src.crop((l, t, l + W, t + H))
            # a little more punch: slightly brighter and richer colour
            from PIL import ImageEnhance
            img = ImageEnhance.Color(ImageEnhance.Contrast(img).enhance(1.08)).enhance(1.15)
            fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fd = ImageDraw.Draw(fade)
            for x in range(W):                                   # navy fade from the left edge to ~65% of the width
                a_ = int(235 * max(0.0, 1 - x / (W * 0.68)) ** 1.15)
                fd.line([(x, 0), (x, H)], fill=(8, 24, 80, a_))
            img = Image.alpha_composite(img.convert("RGBA"), fade).convert("RGB")
        except Exception as e:
            print(f"[video] thumbnail photo skipped: {e}")
            img = None
    if img is None:
        img = Image.new("RGB", (W, H))
        px = ImageDraw.Draw(img)
        for y in range(H):
            t = y / (H - 1)
            top, mid, low = (22, 104, 214), (70, 170, 248), (255, 214, 140)
            c = tuple(int(top[i] + (mid[i] - top[i]) * min(t / 0.55, 1)) for i in range(3))
            k = max(0.0, (t - 0.5) / 0.4) ** 1.3
            c = tuple(int(c[i] + (low[i] - c[i]) * min(k, 1)) for i in range(3))
            px.line([(0, y), (W, y)], fill=c)
        d0 = ImageDraw.Draw(img)
        d0.ellipse([900 - 130, 640 - 130, 900 + 130, 640 + 130], fill=(255, 205, 60))
        hills = [(x, int(650 - 80 * (abs(2 * x / W - 1) ** 1.6) + 10 * math.sin(x / 90))) for x in range(0, W + 1, 8)]
        d0.polygon(hills + [(W, H), (0, H)], fill=(255, 140, 20))
        water = [(x, int(680 + 8 * math.sin(x / 130 + 2))) for x in range(0, W + 1, 8)]
        d0.polygon(water + [(W, H), (0, H)], fill=(10, 60, 170))
    d = ImageDraw.Draw(img)
    # gold channel badge with a small sun
    badge = _font(40, latin=True)
    label = "UPLIFT TODAY"
    bw = int(d.textlength(label, font=badge)) + 120
    d.rounded_rectangle([40, 36, 40 + bw, 108], radius=16, fill=(255, 205, 40))
    _sun(d, 40 + 44, 72, 17)
    d.text((40 + 86, 46), label, font=badge, fill=(20, 40, 110))
    # headline, left aligned, as large as fits in up to 4 lines
    text_w = 720
    _lat = title.isascii()
    font = _font(104, latin=_lat)
    lines = _wrap(d, title, font, text_w)
    for size in (96, 88, 80, 72):
        if len(lines) <= 3:
            break
        font = _font(size, latin=_lat)
        lines = _wrap(d, title, font, text_w)
    lines = lines[:4]
    line_h = int(font.size * 1.26)
    y = 150
    for ln in lines:
        _draw_mixed(d, (44, y), ln, font.size, fill=(255, 255, 255), stroke_width=7, stroke_fill=(8, 28, 100))
        y += line_h
    d.rounded_rectangle([44, y + 8, 44 + 260, y + 16], radius=4, fill=(255, 205, 40))
    d.text((44, y + 30), subtitle, font=_font(46, latin=subtitle.isascii()), fill=(255, 226, 120), stroke_width=4, stroke_fill=(8, 28, 100))
    img.save(out_png)
