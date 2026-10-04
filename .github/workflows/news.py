"""
news.py - Step 1: collect candidate positive stories from RSS feeds.
We only keep the headline and a short summary as a LEAD. We never copy articles.
Stories from the different sites are mixed in turn, so no single site dominates.
"""
import re
import feedparser
import config


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _norm(link):
    return (link or "").split("?")[0].rstrip("/").lower()


def used_links():
    """Links of stories already used in earlier videos (approval/used.json) - we never repeat a story."""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "approval", "used.json")
    try:
        with open(p, encoding="utf-8") as f:
            return {_norm(x.get("link")) for x in json.load(f)}
    except Exception:
        return set()


def collect():
    per_feed = []
    for url in config.RSS_FEEDS:
        kept = []
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[news] could not read {url}: {e}")
            continue
        source = feed.feed.get("title", url)
        for entry in feed.entries[: config.MAX_ITEMS_PER_FEED]:
            title = _clean(entry.get("title"))
            summary = _clean(entry.get("summary"))
            try:
                body = _clean(entry.content[0].value) if entry.get("content") else ""
            except Exception:
                body = ""
            summary = (body if len(body) > len(summary) else summary)[:1800]
            blob = f"{title} {summary}".lower()
            if any(re.search(rf"\b{re.escape(w)}\b", blob) for w in config.BLOCK_WORDS):
                continue  # quick safety filter
            if not title:
                continue
            kept.append({
                "title": title,
                "summary": summary,
                "source": source,
                "link": entry.get("link", ""),
            })
        print(f"[news] {source}: kept {len(kept)}")
        per_feed.append(kept)

    used = used_links()
    before = sum(len(k) for k in per_feed)
    per_feed = [[it for it in k if _norm(it["link"]) not in used] for k in per_feed]
    print(f"[news] {before - sum(len(k) for k in per_feed)} stories skipped: already used in an earlier video")

    # Mix the feeds in turn: one from each site, then the next from each...
    items = []
    for i in range(config.MAX_ITEMS_PER_FEED):
        for kept in per_feed:
            if i < len(kept):
                items.append(kept[i])
    return items
