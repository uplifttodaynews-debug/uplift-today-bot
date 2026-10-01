"""
main.py - runs the whole daily job from start to finish.
Collect news -> write Hindi script -> fact-check -> voice -> video -> upload.
"""
import datetime
import os
import sys
import tempfile

import config
import news
import script_writer
import music
import avatar
import stock
import tts
import video
import upload


SKIPPED = 3  # exit code meaning 'no video today' (GitHub then emails you)


def limit_per_source(stories):
    """Keep at most MAX_PER_SOURCE stories from any one website."""
    counts, kept = {}, []
    for s in stories:
        name = s["source"]["source"] if s.get("source") else "?"
        counts[name] = counts.get(name, 0) + 1
        if counts[name] <= config.MAX_PER_SOURCE:
            kept.append(s)
    return kept


def save_preview(mp4, thumb, description, work):
    """Preview mode: do NOT upload to YouTube. Save a smaller copy in the repo folder previews/."""
    import shutil
    import subprocess
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "previews")
    os.makedirs(out, exist_ok=True)
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", "scale=960:-2",
        "-c:v", "libx264", "-crf", "27", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
        os.path.join(out, "preview.mp4")])
    shutil.copy(thumb, os.path.join(out, "thumbnail.png"))
    with open(os.path.join(out, "description.txt"), "w", encoding="utf-8") as f:
        f.write(description)
    print("[main] PREVIEW saved in previews/ - nothing was uploaded to YouTube")


def main():
    if os.environ.get("ANCHOR_OFF") == "1":
        config.ANCHOR = False
    work = tempfile.mkdtemp(prefix="uplift_")  # temp folder, deleted with the runner
    today = datetime.date.today().strftime("%d %B %Y")

    items = news.collect()
    print(f"[main] {len(items)} candidate stories")
    if len(items) < config.MIN_STORIES:
        print("[main] Not enough good news today - skipping.")
        return SKIPPED

    data = script_writer.write(items)
    stories = limit_per_source(data["stories"])
    print(f"[main] AI wrote {len(stories)} stories; fact-checking them...")
    passed, failed = script_writer.verify(stories)
    if failed and len(passed) < config.NUM_STORIES:
        print(f"[main] {len(failed)} stories flagged - asking the writer to fix them...")
        fixed = script_writer.repair(failed)
        again_ok, _ = script_writer.verify(fixed)
        passed += again_ok
    stories = passed[: config.NUM_STORIES]
    if len(stories) < config.MIN_STORIES:
        print(f"[main] Only {len(stories)} stories passed the checks - skipping today.")
        return SKIPPED
    sources_used = sorted({s["source"]["source"] for s in stories if s.get("source")})
    print(f"[main] {len(stories)} stories passed. Sources: {', '.join(sources_used)}")

    # ---- voice for every piece ----
    segments = []

    # ---- English captions (translated from the FINAL Hindi text) ----
    texts = [data["intro"]] + [s["narration"] for s in stories] + [data["thought"], data["outro"]]
    heads = [s.get("headline", "") for s in stories]
    english, english_heads = [""] * len(texts), [""] * len(heads)
    if config.ENGLISH_CAPTIONS:
        try:
            tr = script_writer.translate(texts + heads)
            english, english_heads = tr[: len(texts)], tr[len(texts):]
            print("[main] English captions ready")
        except Exception as e:
            print(f"[main] English captions skipped: {e}")

    # ---- stock photos for the backgrounds (falls back to the sunrise gradient) ----
    credits = []
    day = datetime.date.today().toordinal()

    def photos(queries, tag):
        found = []
        if not config.STOCK_PHOTOS:
            return found
        for j, q in enumerate(queries[: config.PHOTOS_PER_STORY]):
            res = stock.fetch(q, os.path.join(work, f"{tag}_{j}.jpg"), seed=day + j)
            if res:
                found.append(res["path"])
                credits.append(res)
        return found

    def story_photos(headline, text, queries, tag):
        if not config.STOCK_PHOTOS:
            return []
        res = stock.best_photos(headline, text, queries, os.path.join(work, tag))
        credits.extend(res)
        return [r["path"] for r in res]

    def add(headline, text, name, title_slide=False, eng="", headline_en="", queries=None, tag=None, smart=False):
        mp3 = os.path.join(work, f"{name}.mp3")
        tts.speak(text, mp3)
        if name == "intro" and config.ANCHOR:  # noqa
            for _try in range(3):
                if video._duration(mp3) <= config.ANCHOR_MAX_SECONDS:
                    break
                try:                       # the greeting is read by Kavya: keep it short so her clip stays cheap
                    r = script_writer._call(
                        "Shorten this Hindi news greeting to ONE short sentence of at most 14 words that still says "
                        "the channel name Uplift Today (written as in the original). Keep the same language and script.\n"
                        "Text: " + text + '\nReturn ONLY JSON: {"text": "..."}', 0.2)
                    text = r.get("text", text) or text
                except Exception as e:
                    print(f"[main] could not shorten the greeting: {e}")
                    break
                tts.speak(text, mp3)
            print(f"[main] greeting is {video._duration(mp3):.1f} s long")
        seg = {"headline": headline, "audio": mp3, "title_slide": title_slide,
               "english": eng, "headline_en": headline_en if config.ENGLISH_CAPTIONS else "",
               "backgrounds": (story_photos(headline_en or headline, eng or text, queries or [], name) if smart
                               else photos(queries or [], name)), "tag": tag}
        if name == "intro" and config.ANCHOR and video._duration(mp3) <= config.ANCHOR_MAX_SECONDS:
            seg["clip"] = avatar.make_clip(mp3, os.path.join(work, "anchor_intro.mp4"))
        segments.append(seg)

    fq = config.FIXED_SLIDE_QUERIES
    add("आज की अच्छी खबरें", data["intro"], "intro", True, english[0], "Today's Uplifting News", [fq["intro"]], ("UPLIFT", "TODAY"))
    for i, s in enumerate(stories):
        add(s.get("headline", ""), s["narration"], f"story{i}", False, english[1 + i], english_heads[i],
            s.get("visual_queries") or [], ("STORY", f"{i + 1:02d}"), True)
    add("आज का विचार", data["thought"], "thought", True, english[-2], "Thought of the Day", [fq["thought"]], ("TODAY'S", "THOUGHT"))
    add("धन्यवाद! सब्सक्राइब करें", data["outro"], "outro", True, english[-1], "Thank you! Please subscribe", [fq["outro"]], ("THANK", "YOU"))
    print(f"[main] {len(credits)} stock photos used")

    mp4 = os.path.join(work, "bulletin.mp4")
    secs = video.build(segments, mp4, work)
    print(f"[main] video ready, {secs:.0f} seconds")
    try:
        mixed = os.path.join(work, "bulletin_music.mp4")
        if music.mix(mp4, mixed, secs, start=video.intro_length()):
            mp4 = mixed
    except Exception as e:
        print(f"[main] background music skipped: {e}")

    thumb = os.path.join(work, "thumb.png")
    video.make_thumbnail(data["title"], thumb)

    # ---- description with sources + disclosures ----
    src_lines, seen = [], set()
    for s in stories:
        src = s.get("source")
        if src and src["link"] not in seen:
            seen.add(src["link"])
            src_lines.append(f"- {src['source']}: {src['link']}")
    description = (
        f"{data['title']}\n\n"
        f"Uplift Today - हर सुबह सिर्फ़ अच्छी और प्रेरणादायक खबरें। ({today})\n\n"
        + "\n".join(f"• {s.get('headline','')}" for s in stories)
        + ("\n\nEnglish summary:\n" + "\n".join(f"• {h}" for h in english_heads if h)
           if any(english_heads) else "")
        + "\n\nSources / स्रोत (facts rewritten in our own words):\n"
        + "\n".join(src_lines)
        + ("\n\nStock photos (for illustration only - they do not show the actual events):\n"
           + "\n".join(f"- Photo by {c['photographer']} on {c.get('source', 'Pexels')}: {c['url']}" for c in credits)
           if credits else "")
        + "\n\nMusic: original tracks created for Uplift Today. Our presenter Kavya is an AI-generated character."
        + "\n\nThis video was made with AI: the script is AI-written from public news "
          "sources, and the voice is synthetic.\n"
          "इस वीडियो में AI द्वारा बनाई गई आवाज़ और स्क्रिप्ट का उपयोग हुआ है।\n\n"
          "#GoodNews #PositiveNews #UpliftToday #अच्छीखबर"
    )
    tags = ["good news", "positive news", "uplift today", "अच्छी खबर",
            "सकारात्मक खबर", "hindi news", "inspiring news"]

    if os.environ.get("PREVIEW_ONLY") == "1":
        save_preview(mp4, thumb, description, work)
        return 0
    try:
        upload.upload(mp4, data["title"], description, tags, thumb)
    except Exception as e:
        if "uploadLimitExceeded" in str(e):
            print("[main] YouTube's daily upload limit for this channel is reached. Not retrying - "
                  "it resets within 24 hours.")
            return SKIPPED
        raise
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[main] FAILED: {e}")
        raise
