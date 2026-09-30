"""
news.py - Step 1: collect candidate positive stories from RSS feeds.
We only keep the headline and a short summary as a LEAD. We never copy articles.
"""
import re
import feedparser
import config


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def collect():
    items = []
    for url in config.RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[news] could not read {url}: {e}")
            continue
        source = feed.feed.get("title", url)
        for entry in feed.entries[: config.MAX_ITEMS_PER_FEED]:
            title = _clean(entry.get("title"))
            summary = _clean(entry.get("summary"))[:600]
            blob = f"{title} {summary}".lower()
            if any(re.search(rf"\b{re.escape(w)}\b", blob) for w in config.BLOCK_WORDS):
                continue  # quick safety filter
            if not title:
                continue
            items.append({
                "title": title,
                "summary": summary,
                "source": source,
                "link": entry.get("link", ""),
            })
        print(f"[news] {source}: kept so far {len(items)}")
    return items
