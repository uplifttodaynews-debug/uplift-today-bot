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


def _plan(lead, text, max_words):
    return script_writer._call(
        f"Write a YouTube SHORT (vertical, about 45 seconds) in simple spoken {config.LANGUAGE_NAME} (Devanagari) about this "
        f"positive news story. At most {max_words} words in total. Start with ONE strong hook sentence that makes people stop "
        "scrolling (a surprising fact from the story), then 3-4 short sentences with the key facts, then end with exactly: "
        "पूरी ख़बर हमारे चैनल पर देखें। Use only facts from the text; keep the word AI in English letters. "
        "Also write a title (Devanagari, under 60 characters) and 5 DIFFERENT English image prompts (photographic, warm natural light, "
        "vertical composition, generic people or places that illustrate the story, NO text, letters, logos, flags, famous people; max 40 words each).\n"
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


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(HERE, "..", "..", "approval", "chosen.json"), encoding="utf-8") as f:
        lead = json.load(f)["leads"][0]
    full = news.enrich(lead) or lead.get("summary", "")
    plan = _plan(lead, full, 105)
    script = script_writer.polish_hindi(plan["script"])
    mp3 = os.path.join(WORK, "short.mp3")
    for _ in range(3):
        tts.speak(script, mp3)
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

    # captions timed by length of text
    ch = _chunks(script)
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
    desc = (f"{title}\n\nपूरी ख़बर हमारे चैनल Uplift Today पर देखें। (Source: {lead.get('source','')}: {lead.get('link','')})\n\n"
            "Pictures are AI-generated illustrations. The voice is synthetic and the script is AI-written from public news sources.\n\n"
            "#Shorts #GoodNews #PositiveNews #UpliftToday #अच्छीखबर")
    with open(os.path.join(OUT, "description.txt"), "w", encoding="utf-8") as f:
        f.write(title + " #Shorts\n\n" + desc)
    print(f"[short] ready: {dur:.0f} s - nothing uploaded")


if __name__ == "__main__":
    main()
