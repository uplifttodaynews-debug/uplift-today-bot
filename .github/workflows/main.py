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


def pick_stories(passed):
    """Best stories by impact; at most one animal story; the strongest one goes first."""
    def imp(s):
        try:
            return float(s.get("impact", 5))
        except Exception:
            return 5.0
    ranked = sorted(passed, key=imp, reverse=True)
    chosen, animals = [], 0
    for s in ranked:
        if str(s.get("topic", "")).lower() == "animals":
            if animals >= 1:
                continue
            animals += 1
        chosen.append(s)
        if len(chosen) >= config.NUM_STORIES:
            break
    if len(chosen) < config.MIN_STORIES:          # not enough without the cap: fill up in impact order
        chosen = ranked[: config.NUM_STORIES]
    print("[main] stories by impact:", [(str(s.get("topic")), s.get("impact")) for s in chosen])
    return chosen


def record_used(stories):
    """Remember the stories of this video so they are never repeated."""
    import json
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "approval", "used.json")
    try:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
        for s in stories:
            link = (s.get("source") or {}).get("link")
            if link:
                data.append({"link": link, "date": config.today_india().isoformat()})
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except Exception as e:
        print(f"[main] could not record the used stories: {e}")


def load_approved():
    """The owner's approved stories (approval/chosen.json) are used only for the video dated `date`."""
    import json
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "approval", "chosen.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("date") == config.today_india().isoformat() and d.get("leads"):
            return d["leads"]
    except Exception:
        pass
    return None


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
    today = config.today_india().strftime("%d %B %Y")

    approved = load_approved()
    if approved:
        items = [news.enrich(l) for l in approved]
        config.NUM_STORIES, config.EXTRA_CANDIDATES = len(items), 0
        config.APPROVED_MODE = True
        print(f"[main] using the {len(items)} stories YOU approved, in your order")
    else:
        items = news.collect()
    print(f"[main] {len(items)} candidate stories")
    if len(items) < (2 if approved else config.MIN_STORIES):
        print("[main] Not enough good news today - skipping.")
        return SKIPPED

    data = script_writer.write(items)
    stories = data["stories"] if approved else limit_per_source(data["stories"])
    print(f"[main] AI wrote {len(stories)} stories; fact-checking them...")
    passed, failed = script_writer.verify(stories)
    if failed and len(passed) < config.NUM_STORIES:
        print(f"[main] {len(failed)} stories flagged - asking the writer to fix them...")
        fixed = script_writer.repair(failed)
        again_ok, _ = script_writer.verify(fixed)
        passed += again_ok
    if approved:                                   # keep the owner's order
        order = {it.get("link"): n for n, it in enumerate(items)}
        stories = sorted(passed, key=lambda s: order.get((s.get("source") or {}).get("link"), 99))
        seen_links, uniq = set(), []
        for s in stories:                          # one story per approved lead
            k = (s.get("source") or {}).get("link")
            if k not in seen_links:
                seen_links.add(k)
                uniq.append(s)
        stories = uniq
        print("[main] approved order:", [s.get("headline") for s in stories])
    else:
        stories = pick_stories(passed)
    if len(stories) < (2 if approved else config.MIN_STORIES):
        print(f"[main] Only {len(stories)} stories passed the checks - skipping today.")
        return SKIPPED
    for k_ in ("title", "intro", "thought", "outro"):
        data[k_] = script_writer.polish_hindi(data.get(k_))
    for s_ in stories:
        s_["headline"] = script_writer.polish_hindi(s_.get("headline"))
        s_["narration"] = script_writer.polish_hindi(s_.get("narration"))
    data["title"] = script_writer.make_title(stories, data.get("title", ""))
    print(f"[main] title (about the lead story): {data['title']}")
    special = config.SPECIAL_DAYS.get((config.today_india().month, config.today_india().day))
    if special:
        print("[main] special day greeting is used")
        data["intro"] = special
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
    ai_used = []
    day = config.today_india().toordinal()

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
        res = stock.best_photos(headline, text, queries, os.path.join(work, tag), want=config.PICS_PER_STORY)
        credits.extend(res)
        return [r["path"] for r in res]

    def story_media(headline, text, queries, tag, want_video):
        if want_video:
            vids = stock.best_photos(headline, text, queries, os.path.join(work, tag + "_v"), want=3, kind="video")
            if vids:
                credits.extend(vids)
                paths = [v["path"] for v in vids]
                if len(paths) < 4:                         # clips plus photos keep the picture changing
                    pics = stock.best_photos(headline, text, queries, os.path.join(work, tag), want=min(2, 4 - len(paths)))
                    credits.extend(pics)
                    paths += [p["path"] for p in pics]
                print(f"[main] {tag}: {len(vids)} video clip(s)")
                return paths
            print(f"[main] {tag}: no good video clip, using photos")
        return story_photos(headline, text, queries, tag)

    def story_media_ai(headline, text, queries, tag, want_video, idx=None):
        force = idx is not None and str(idx) in os.environ.get("FORCE_AI_VISUALS", "").split(",")
        paths = [] if force else story_media(headline, text, queries, tag, want_video)
        if (len(paths) < 2 or force) and idx is not None:           # nothing suitable in the stock libraries: AI illustrations
            import thumb_ai
            extra = thumb_ai.make_illustrations(stories[idx], os.path.join(work, tag), n=4 if force else 3)
            if extra:
                print(f"[main] {tag}: {len(extra)} AI illustration(s) added (no good stock footage)")
                ai_used.extend(extra)
                paths = paths + extra
        return paths

    def add(headline, text, name, title_slide=False, eng="", headline_en="", queries=None, tag=None, smart=False, want_video=False, idx=None):
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
               "backgrounds": (story_media_ai(headline_en or headline, eng or text, queries or [], name, want_video, idx) if smart
                               else photos(queries or [], name)), "tag": tag}
        if name == "intro" and config.ANCHOR and video._duration(mp3) <= config.ANCHOR_MAX_SECONDS:
            seg["clip"] = avatar.make_clip(mp3, os.path.join(work, "anchor_intro.mp4"))
        segments.append(seg)

    fq = config.FIXED_SLIDE_QUERIES
    add("आज की पॉज़िटिव ख़बरें", data["intro"], "intro", True, english[0], "Today's Uplifting News", [fq["intro"]], ("UPLIFT", "TODAY"))
    for i, s in enumerate(stories):
        add(s.get("headline", ""), s["narration"], f"story{i}", False, english[1 + i], english_heads[i],
            s.get("visual_queries") or [], ("STORY", f"{i + 1:02d}"), True, idx=i,
            want_video=bool(config.STOCK_VIDEOS and (i * config.VIDEO_SHARE) % 1 < config.VIDEO_SHARE - 1e-9))
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
    thumb_src = None
    for sg_ in segments:                                   # the first story's photo (or a frame of its video) is the thumbnail picture
        if (sg_.get("tag") or ("",))[0] != "STORY":
            continue
        for b_ in sg_.get("backgrounds") or []:
            if str(b_).lower().endswith(".mp4"):
                try:
                    import subprocess
                    fr = os.path.join(work, "thumb_frame.jpg")
                    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5", "-i", b_, "-frames:v", "1", "-q:v", "2", fr])
                    thumb_src = fr
                except Exception as e:
                    print(f"[main] could not take a frame from the clip: {e}")
            else:
                thumb_src = b_
            if thumb_src:
                break
        if thumb_src:
            break
    ai_thumb = False
    if config.today_india().isoformat() in getattr(config, "AI_THUMBNAIL_DAYS", set()) or os.environ.get("FORCE_AI_THUMB") == "1":
        import thumb_ai
        pic = thumb_ai.make_image(stories[0], os.path.join(work, "thumb_ai.jpg"))
        if pic:
            thumb_src, ai_thumb = pic, True
    video.make_thumbnail(data["title"], thumb, thumb_src)
    if os.environ.get("THUMB_OPTIONS") == "1":
        import thumb_ai
        try:
            r = script_writer._call(
                "For the lead story below write 4 DIFFERENT short Hindi (Devanagari) thumbnail headlines, 18-34 characters each, "
                "hopeful and punchy, no numbers; keep the word AI in English letters. Also write 4 matching, clearly different image ideas "
                "(English, one sentence each, a different scene/subject each).\n"
                f"Lead story: {stories[0].get('headline','')}. {stories[0]['narration'][:900]}\n"
                'Return ONLY JSON: {"options": [{"headline": "...", "idea": "..."}]}', 0.8).get("options", [])
        except Exception as e:
            print(f"[thumb] options failed: {e}")
            r = []
        odir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "previews", "thumb_options")
        os.makedirs(odir, exist_ok=True)
        for k, o in enumerate(r[:4], 1):
            pic = thumb_ai.make_image(stories[0], os.path.join(work, f"opt{k}.jpg"), hint=o.get("idea", ""))
            if pic:
                video.make_thumbnail(script_writer.polish_hindi(o.get("headline", data["title"])), os.path.join(odir, f"option{k}.png"), pic)
                print(f"[thumb] option {k}: {o.get('headline')}")

    # ---- description with sources + disclosures ----
    src_lines, seen = [], set()
    for s in stories:
        src = s.get("source")
        if src and src["link"] not in seen:
            seen.add(src["link"])
            src_lines.append(f"- {src['source']}: {src['link']}")
    description = (
        f"{data['title']}\n\n"
        f"Uplift Today - हर सुबह सिर्फ़ अच्छी और प्रेरणादायक ख़बरें। ({today})\n\n"
        + "\n".join(f"• {s.get('headline','')}" for s in stories)
        + ("\n\nEnglish summary:\n" + "\n".join(f"• {h}" for h in english_heads if h)
           if any(english_heads) else "")
        + "\n\nSources / स्रोत (facts rewritten in our own words):\n"
        + "\n".join(src_lines)
        + ("\n\nStock photos (for illustration only - they do not show the actual events):\n"
           + "\n".join(f"- Photo by {c['photographer']} on {c.get('source', 'Pexels')}: {c['url']}" for c in credits)
           if credits else "")
        + ("\n\nSome pictures in this video are AI-generated illustrations (not photos of the actual events)." if ai_used else "")
        + ("\n\nThumbnail picture: AI-generated illustration (not a photo of the actual event)." if ai_thumb else "")
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
        hold = os.environ.get("HOLD_OUT")
        if hold:                                   # full-quality copy kept for a later "upload" command
            import json
            import shutil
            os.makedirs(hold, exist_ok=True)
            shutil.copy(mp4, os.path.join(hold, "bulletin.mp4"))
            shutil.copy(thumb, os.path.join(hold, "thumbnail.png"))
            with open(os.path.join(hold, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"title": data["title"], "description": description, "tags": tags,
                           "date": config.today_india().isoformat(),
                           "links": [(s.get("source") or {}).get("link") for s in stories]}, f, ensure_ascii=False)
            print("[main] HOLD: the finished video is kept for review - NOT uploaded to YouTube")
        return 0
    try:
        upload.upload(mp4, data["title"], description, tags, thumb)
    except Exception as e:
        if "uploadLimitExceeded" in str(e):
            print("[main] YouTube's daily upload limit for this channel is reached. Not retrying - "
                  "it resets within 24 hours.")
            return SKIPPED
        raise
    record_used(stories)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[main] FAILED: {e}")
        raise
