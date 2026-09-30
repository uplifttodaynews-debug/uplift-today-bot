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
import tts
import video
import upload


def limit_per_source(stories):
    """Keep at most MAX_PER_SOURCE stories from any one website."""
    counts, kept = {}, []
    for s in stories:
        name = s["source"]["source"] if s.get("source") else "?"
        counts[name] = counts.get(name, 0) + 1
        if counts[name] <= config.MAX_PER_SOURCE:
            kept.append(s)
    return kept


def main():
    work = tempfile.mkdtemp(prefix="uplift_")  # temp folder, deleted with the runner
    today = datetime.date.today().strftime("%d %B %Y")

    items = news.collect()
    print(f"[main] {len(items)} candidate stories")
    if len(items) < config.MIN_STORIES:
        print("[main] Not enough good news today - skipping.")
        return 0

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
        return 0
    sources_used = sorted({s["source"]["source"] for s in stories if s.get("source")})
    print(f"[main] {len(stories)} stories passed. Sources: {', '.join(sources_used)}")

    # ---- voice for every piece ----
    segments = []

    def add(headline, text, name, title_slide=False):
        mp3 = os.path.join(work, f"{name}.mp3")
        tts.speak(text, mp3)
        segments.append({"headline": headline, "audio": mp3, "title_slide": title_slide})

    add("आज की अच्छी खबरें", data["intro"], "intro", True)
    for i, s in enumerate(stories):
        add(s.get("headline", ""), s["narration"], f"story{i}")
    add("आज का विचार", data["thought"], "thought", True)
    add("धन्यवाद! सब्सक्राइब करें", data["outro"], "outro", True)

    mp4 = os.path.join(work, "bulletin.mp4")
    secs = video.build(segments, mp4, work)
    print(f"[main] video ready, {secs:.0f} seconds")

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
        + "\n\nSources / स्रोत (facts rewritten in our own words):\n"
        + "\n".join(src_lines)
        + "\n\nThis video was made with AI: the script is AI-written from public news "
          "sources, and the voice is synthetic.\n"
          "इस वीडियो में AI द्वारा बनाई गई आवाज़ और स्क्रिप्ट का उपयोग हुआ है।\n\n"
          "#GoodNews #PositiveNews #UpliftToday #अच्छीखबर"
    )
    tags = ["good news", "positive news", "uplift today", "अच्छी खबर",
            "सकारात्मक खबर", "hindi news", "inspiring news"]

    upload.upload(mp4, data["title"], description, tags, thumb)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[main] FAILED: {e}")
        raise
