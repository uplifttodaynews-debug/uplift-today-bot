"""
main.py - runs the whole daily job from start to finish.
Collect news -> write Hindi script -> voice -> video -> upload.
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


def main():
    work = tempfile.mkdtemp(prefix="uplift_")  # temp folder, deleted with the runner
    today = datetime.date.today().strftime("%d %B %Y")

    items = news.collect()
    print(f"[main] {len(items)} candidate stories")
    if len(items) < config.MIN_STORIES:
        print("[main] Not enough good news today - skipping.")
        return 0

    data = script_writer.write(items)
    stories = data["stories"]
    if len(stories) < config.MIN_STORIES:
        print(f"[main] Only {len(stories)} good stories - skipping today.")
        return 0

    # ---- voice for every piece ----
    segments = []

    def add(headline, text, name, title_slide=False):
        mp3 = os.path.join(work, f"{name}.mp3")
        tts.speak(text, mp3)
        segments.append({"headline": headline, "audio": mp3, "title_slide": title_slide})

    add("आज की अच्छी खबरें", data["intro"], "intro", True)
    for i, s in enumerate(stories[: config.NUM_STORIES]):
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
