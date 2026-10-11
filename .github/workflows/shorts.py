"""shorts.py - makes ONE vertical YouTube Short (about 50 s) from the lead approved story. Nothing is uploaded."""
import json
import os
import re
import subprocess
from PIL import Image, ImageDraw
import config
import news
import script_writer
import thumb_ai
import tts
import video
import music

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "previews", "short")
W, H = 1080, 1920
WORK = "/tmp/short_work"


UR = os.environ.get("SHORT_LANG") == "ur"


def _urdu(script):
    """Urdu (Nastaliq-script) version of the Hindi script, for the Urdu voice."""
    r = script_writer._call("Translate this spoken Hindi news script into natural, simple spoken Urdu written in Urdu (Perso-Arabic) script. "
                            "Keep every fact and number (write numbers as Urdu words), keep AI as 'اے آئی'. "
                            'Return ONLY JSON: {"urdu": "..."}\n\n' + script, 0.2)
    return (r.get("urdu") or "").strip()


def _speak(script, mp3):
    if not UR:
        return tts.speak(script, mp3)
    text = _urdu(script)
    print("[short] urdu script:", text)
    config.LANGUAGE_CODE = "ur-IN"
    for voice in ("ur-IN-Chirp3-HD-Aoede", "ur-IN-Wavenet-A", "ur-IN-Standard-A"):
        config.VOICE_NAME = voice
        try:
            print("[short] urdu voice:", voice)
            return tts.speak(text, mp3)
        except Exception as e:
            print(f"[short] voice {voice} failed: {e}")
    raise SystemExit("no Urdu voice available")


PK_RULE = ("The Short is for a PAKISTANI audience, so in EVERY image prompt show Pakistani people and homes: women wearing a dupatta or "
           "shawl loosely covering the head (NOT a hijab and NOT a niqab or any face covering), men in shalwar kameez, Pakistani home settings "
           "(dastarkhwan, roti, daal, biryani), always groups of at least three (families or same-gender friends), modest, never couples. ")


def _plan(lead, text, max_words):
    return script_writer._call((PK_RULE if os.environ.get("SHORT_LANG") == "ur" else "") +
        f"Write a YouTube SHORT (vertical, about 45 seconds) in simple spoken {config.LANGUAGE_NAME} (Devanagari) about this "
        f"positive news story. At most {max_words} words in total. Start with ONE strong hook sentence that makes people stop "
        "scrolling (a surprising fact from the story), then 3-4 short sentences with the key facts, then end with exactly: "
        "पूरी ख़बर हमारे चैनल पर देखें। Use only facts from the text; keep the word AI in English letters. The audience is conservative Indian families: NEVER mention romantic partners, couples, intimacy or physical closeness; speak only of family, friends or loved ones. "
        "Also write a title (Devanagari, under 60 characters) and 5 DIFFERENT English image prompts (photographic, warm natural light, "
        "vertical composition, generic people or places that illustrate the story (modest, family-friendly: families, friends, children; never couples or intimate scenes; Indian stories show Indian people), NO text, letters, logos, flags, famous people; max 40 words each).\n"
        f"Story headline: {lead.get('title', '')}\nStory text: {text[:3500]}\n"
        'Return ONLY JSON: {"title": "...", "script": "...", "prompts": ["..."]}', 0.5)


def _chunks(script, per=5):
    parts = [p.strip() for p in re.split(r"(?<=[।?!,])\s+", script) if p.strip()]
    out = []
    for p in parts:
        words = p.split()
        for i in range(0, len(words), per):
            out.append(" ".join(words[i:i + per]))
    return out


def _caption_png(text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = 84
    font = video._font(size)
    lines = video._wrap(d, text, font, W - 160)[:3]
    lh = int(size * 1.4)
    y = 1180
    box_h = lh * len(lines) + 40
    d.rounded_rectangle([50, y - 20, W - 50, y - 20 + box_h], radius=30, fill=(8, 24, 80, 190))
    for ln in lines:
        w = sum(d.textlength(x, font=font) for x in ln.split(" ")) + d.textlength(" ", font=font) * (len(ln.split(" ")) - 1)
        video._draw_mixed(d, ((W - w) / 2, y), ln, size, fill=(255, 255, 255), stroke_width=4, stroke_fill=(8, 28, 100))
        y += lh
    img.save(path)


def _frame_furniture(path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for yy in range(0, 260):                                  # soft dark band at the top for the badge
        d.line([(0, yy), (W, yy)], fill=(8, 24, 80, int(170 * (1 - yy / 260))))
    badge = video._font(46, latin=True)
    label = "UPLIFT TODAY"
    bw = int(d.textlength(label, font=badge)) + 120
    d.rounded_rectangle([50, 70, 50 + bw, 150], radius=18, fill=(255, 205, 40, 255))
    video._sun(d, 50 + 46, 110, 19)
    d.text((50 + 90, 80), label, font=badge, fill=(20, 40, 110, 255))
    img.save(path)


def _title_card(title, first_img, out_png):
    """Full-height cover with the WHOLE title in big letters: used as the Short's thumbnail and for the first second of the video."""
    from PIL import ImageEnhance
    src = Image.open(first_img).convert("RGB")
    sc = max(W / src.width, H / src.height)
    src = src.resize((int(src.width * sc) + 1, int(src.height * sc) + 1), Image.LANCZOS)
    l, t = (src.width - W) // 2, (src.height - H) // 2
    img = src.crop((l, t, l + W, t + H))
    img = ImageEnhance.Brightness(img).enhance(0.85).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H):
        a = int(215 * max(0.0, (y - H * 0.38) / (H * 0.62)) ** 1.1)
        sd.line([(0, y), (W, y)], fill=(8, 24, 80, a))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    size = 104
    font = video._font(size)
    lines = video._wrap(d, title, font, W - 120)
    while len(lines) > 5 and size > 60:
        size -= 8
        font = video._font(size)
        lines = video._wrap(d, title, font, W - 120)
    lh = int(size * 1.3)
    y = H - 260 - lh * len(lines)
    for ln in lines:
        w = sum(d.textlength(x, font=font) for x in ln.split(" ")) + d.textlength(" ", font=font) * (len(ln.split(" ")) - 1)
        video._draw_mixed(d, ((W - w) / 2, y), ln, size, fill=(255, 215, 40), stroke_width=7, stroke_fill=(5, 20, 70))
        y += lh
    badge = video._font(46, latin=True)
    label = "UPLIFT TODAY"
    bw = int(d.textlength(label, font=badge)) + 120
    d.rounded_rectangle([50, 70, 50 + bw, 150], radius=18, fill=(255, 205, 40, 255))
    video._sun(d, 50 + 46, 110, 19)
    d.text((50 + 90, 80), label, font=badge, fill=(20, 40, 110, 255))
    img.convert("RGB").save(out_png)


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(HERE, "..", "..", "approval", "chosen.json"), encoding="utf-8") as f:
        lead = json.load(f)["leads"][max(int(os.environ.get("SHORT_STORY", "1")) - 1, 0)]
    full = (news.enrich(lead) or lead).get("summary", "")
    plan = _plan(lead, full, 105)
    script = script_writer.polish_hindi(plan["script"])
    mp3 = os.path.join(WORK, "short.mp3")
    for _ in range(3):
        _speak(script, mp3)
        dur = video._duration(mp3)
        print(f"[short] voice {dur:.1f} s")
        if dur <= 57:
            break
        plan = _plan(lead, full, 80)
        script = script_writer.polish_hindi(plan["script"])
    print("[short] script:", script)

    imgs = []
    key = os.environ.get("FAL_KEY", "").strip()
    for i, p in enumerate(plan.get("prompts", [])[:5]):
        path = os.path.join(WORK, f"img{i}.jpg")
        try:
            if key and thumb_ai._fal(p, path, key, size=(720, 1280)):
                imgs.append(path)
        except Exception as e:
            print(f"[short] picture {i} failed: {e}")
    if len(imgs) < 2:
        raise SystemExit("not enough pictures for the Short")

    # background: slow zoom on each picture
    per = dur / len(imgs)
    clips = []
    for i, im in enumerate(imgs):
        c = os.path.join(WORK, f"clip{i}.mp4")
        frames = int(per * 30) + 2
        zoom = "min(zoom+0.0006,1.12)" if i % 2 == 0 else "if(eq(on,0),1.12,max(zoom-0.0006,1.0))"
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", im, "-vf",
                               f"scale=1188:2112,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps=30,format=yuv420p",
                               "-t", f"{per:.3f}", "-c:v", "libx264", "-preset", "veryfast", c])
        clips.append(c)
    lst = os.path.join(WORK, "list.txt")
    with open(lst, "w") as f:
        f.write("".join(f"file '{c}'\n" for c in clips))
    bg = os.path.join(WORK, "bg.mp4")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", bg])

    # captions timed by length of text (English subtitles under the Hindi voice when SHORT_SUBS=en)
    cap_text = script
    if os.environ.get("SHORT_SUBS") == "en":
        try:
            t_ = script_writer._call("Translate this spoken Hindi news script into simple, natural English subtitles. Keep it short and "
                                     "faithful, no additions. Return ONLY JSON: {\"english\": \"...\"}\n\n" + script, 0.2)
            cap_text = (t_.get("english") or script).strip()
            print("[short] english subtitles:", cap_text)
        except Exception as e:
            print(f"[short] translation failed, using Hindi captions: {e}")
    ch = _chunks(cap_text, per=6 if cap_text is not script else 5)
    total = sum(len(c) for c in ch) or 1
    t, items = 0.0, []
    for i, c in enumerate(ch):
        d_ = dur * len(c) / total
        p = os.path.join(WORK, f"cap{i}.png")
        _caption_png(c, p)
        items.append((p, t, t + d_))
        t += d_
    furn = os.path.join(WORK, "furniture.png")
    _frame_furniture(furn)
    inputs = ["-i", bg, "-i", mp3, "-i", furn] + sum([["-i", p] for p, _, _ in items], [])
    fc = "[0:v][2:v]overlay=0:0[v0];"
    for i, (_, a, b) in enumerate(items):
        fc += f"[v{i}][{i + 3}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[v{i + 1}];"
    fc = fc.rstrip(";")
    raw = os.path.join(WORK, "short_raw.mp4")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", fc, "-map", f"[v{len(items)}]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", raw])
    final = os.path.join(OUT, "short.mp4")
    try:
        if not music.mix(raw, final, dur):
            raise RuntimeError("no music")
    except Exception as e:
        print(f"[short] music skipped: {e}")
        subprocess.check_call(["cp", raw, final])
    title = (plan.get("title") or lead.get("title", "")).strip()
    if UR:
        try:
            title = script_writer._call("Write a short catchy English YouTube title (under 60 characters) for this story: "
                                        + lead.get("title", "") + '. Return ONLY JSON: {"title": "..."}', 0.4).get("title", title).strip() or title
        except Exception as e:
            print(f"[short] english title skipped: {e}")
    # the whole title as the thumbnail, and on screen for the first 1.2 s (YouTube often picks the opening frame)
    try:
        card = os.path.join(OUT, "thumbnail.png")
        _title_card(title, imgs[0], card)
        titled = os.path.join(WORK, "titled.mp4")
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", final, "-i", card, "-filter_complex",
                               "[0:v][1:v]overlay=0:0:enable='lt(t,1.2)'[v]", "-map", "[v]", "-map", "0:a", "-c:v", "libx264",
                               "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "copy", titled])
        subprocess.check_call(["cp", titled, final])
    except Exception as e:
        print(f"[short] title card skipped: {e}")
    desc = (f"{title}\n\nपूरी ख़बर हमारे चैनल Uplift Today पर देखें। (Source: {lead.get('source','')}: {lead.get('link','')})\n\n"
            "Pictures are AI-generated illustrations. The voice is synthetic and the script is AI-written from public news sources.\n\n"
            "#Shorts #GoodNews #PositiveNews #UpliftToday #अच्छीखबर")
    with open(os.path.join(OUT, "description.txt"), "w", encoding="utf-8") as f:
        f.write(title + " #Shorts\n\n" + desc)
    n_ = os.environ.get("SHORT_STORY", "1")
    subprocess.check_call(["cp", final, os.path.join(OUT, f"short_{n_}.mp4")])
    subprocess.check_call(["cp", os.path.join(OUT, "description.txt"), os.path.join(OUT, f"description_{n_}.txt")])
    print(f"[short] ready: {dur:.0f} s - nothing uploaded")


if __name__ == "__main__":
    main()
