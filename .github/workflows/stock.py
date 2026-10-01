"""
stock.py - fetches free stock photos to use as video backgrounds.
Sources, in order: Pexels (PEXELS_API_KEY), then Pixabay (PIXABAY_API_KEY) as the backup.
Both licences allow commercial use and do not require credit, but we put a credit line in every
video description anyway. If anything goes wrong (no key, no result, network problem) we simply
return None and the video uses the sunrise gradient.
"""
import os
import random
import requests
from PIL import Image

import config

API = "https://api.pexels.com/v1/search"


def fetch(query, out_path, seed=0):
    """Download one landscape photo for `query`. Returns {"path","photographer","url","source"} or None."""
    return _pexels(query, out_path, seed) or _pixabay(query, out_path, seed)


def _pixabay(query, out_path, seed=0):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key or not query:
        return None
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={"key": key, "q": query[:100], "image_type": "photo", "orientation": "horizontal",
                    "safesearch": "true", "per_page": 20, "min_width": 1280},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[stock] Pixabay error {r.status_code} for '{query}'")
            return None
        hits = r.json().get("hits", [])
        if not hits:
            print(f"[stock] Pixabay: no photo found for '{query}'")
            return None
        hit = random.Random(seed).choice(hits[:10])
        data = requests.get(hit["largeImageURL"], timeout=60)
        data.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(data.content)
        Image.open(out_path).verify()
        return {"path": out_path, "photographer": hit.get("user", "Unknown"),
                "url": hit.get("pageURL", "https://pixabay.com"), "source": "Pixabay"}
    except Exception as e:
        print(f"[stock] Pixabay skipped '{query}': {e}")
        return None


def _pexels(query, out_path, seed=0):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or not query:
        return None
    try:
        r = requests.get(
            API,
            headers={"Authorization": key},
            params={"query": query, "orientation": "landscape", "size": "large", "per_page": 15},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[stock] Pexels error {r.status_code} for '{query}'")
            return None
        photos = r.json().get("photos", [])
        if not photos:
            print(f"[stock] no photo found for '{query}'")
            return None
        photo = random.Random(seed).choice(photos[:10])
        img_url = photo["src"].get("large2x") or photo["src"]["large"]
        data = requests.get(img_url, timeout=60)
        data.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(data.content)
        Image.open(out_path).verify()  # make sure it is a real image
        return {
            "path": out_path,
            "photographer": photo.get("photographer", "Unknown"),
            "url": photo.get("url", "https://www.pexels.com"),
            "source": "Pexels",
        }
    except Exception as e:
        print(f"[stock] skipped '{query}': {e}")
        return None


# ---------------------------------------------------------------- smart picking
def _cands_pexels(query, n=8):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or not query:
        return []
    try:
        r = requests.get(API, headers={"Authorization": key},
                         params={"query": query, "orientation": "landscape", "size": "large", "per_page": n}, timeout=30)
        if r.status_code != 200:
            return []
        return [{"thumb": p["src"].get("medium") or p["src"]["large"], "full": p["src"].get("large2x") or p["src"]["large"],
                 "photographer": p.get("photographer", "Unknown"), "url": p.get("url", "https://www.pexels.com"),
                 "source": "Pexels"} for p in r.json().get("photos", [])]
    except Exception as e:
        print(f"[stock] Pexels candidates skipped '{query}': {e}")
        return []


def _cands_pixabay(query, n=8):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key or not query:
        return []
    try:
        r = requests.get("https://pixabay.com/api/",
                         params={"key": key, "q": query[:100], "image_type": "photo", "orientation": "horizontal",
                                 "safesearch": "true", "per_page": max(n, 3), "min_width": 1280}, timeout=30)
        if r.status_code != 200:
            return []
        return [{"thumb": h.get("webformatURL") or h["largeImageURL"], "full": h["largeImageURL"],
                 "photographer": h.get("user", "Unknown"), "url": h.get("pageURL", "https://pixabay.com"),
                 "source": "Pixabay"} for h in r.json().get("hits", [])[:n]]
    except Exception as e:
        print(f"[stock] Pixabay candidates skipped '{query}': {e}")
        return []


def _cands_videos(query, n=8):
    """Short stock video clips (Pexels if a key exists, plus Pixabay). `full` is a ~720p file."""
    out = []
    pk = os.environ.get("PEXELS_API_KEY", "").strip()
    if pk and query:
        try:
            r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": pk},
                             params={"query": query, "orientation": "landscape", "size": "medium", "per_page": n}, timeout=30)
            if r.status_code == 200:
                for v in r.json().get("videos", []):
                    if (v.get("duration") or 0) < 4:
                        continue
                    files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 960]
                    files.sort(key=lambda f: abs((f.get("width") or 0) - 1280))
                    if files:
                        out.append({"thumb": v.get("image"), "full": files[0]["link"], "photographer": (v.get("user") or {}).get("name", "Unknown"),
                                    "url": v.get("url", "https://www.pexels.com"), "source": "Pexels"})
        except Exception as e:
            print(f"[stock] Pexels videos skipped '{query}': {e}")
    xk = os.environ.get("PIXABAY_API_KEY", "").strip()
    if xk and query:
        try:
            r = requests.get("https://pixabay.com/api/videos/", params={"key": xk, "q": query[:100], "safesearch": "true", "per_page": max(n, 3)}, timeout=30)
            if r.status_code == 200:
                for h in r.json().get("hits", []):
                    vids = h.get("videos") or {}
                    pick = next((vids[k] for k in ("medium", "small") if vids.get(k, {}).get("url") and (vids[k].get("width") or 0) >= 900), None)
                    if not pick or (h.get("duration") or 0) < 4 or (pick.get("size") or 0) > 45_000_000:
                        continue
                    thumb = pick.get("thumbnail") or (f"https://i.vimeocdn.com/video/{h['picture_id']}_640x360.jpg" if h.get("picture_id") else None)
                    if thumb:
                        out.append({"thumb": thumb, "full": pick["url"], "photographer": h.get("user", "Unknown"),
                                    "url": h.get("pageURL", "https://pixabay.com"), "source": "Pixabay"})
            else:
                print(f"[stock] Pixabay videos error {r.status_code} for '{query}'")
        except Exception as e:
            print(f"[stock] Pixabay videos skipped '{query}': {e}")
    return out


def _best_photos_once(headline, narration, queries, out_prefix, want, loose, kind="photo"):
    """Look at many candidate photos and let Gemini choose the ones that really suit the story.
    Returns a list of {"path","photographer","url","source"} (possibly empty -> sunrise picture is used)."""
    import base64
    import script_writer
    cands, seen = [], set()
    for q in queries:
        for c in (_cands_videos(q) if kind == "video" else _cands_pexels(q) + _cands_pixabay(q)):
            if c["full"] not in seen:
                seen.add(c["full"])
                cands.append(c)
    cands = cands[:16 if kind == "video" else 20]
    if not cands:
        return []
    parts = [{"text": (
        "You are a strict picture editor for a positive-news TV bulletin. STORY HEADLINE: " + (headline or "") +
        "\nSTORY: " + (narration or "") + "\n\nBelow are numbered candidate " + ("video clips (one preview frame of each)" if kind == "video" else "photos") +
        ". Score EVERY candidate from 0 to 10 for how well it shows THIS story's actual subject "
        "(the specific place, activity, people or object the story is about). 9-10 = clearly the subject of the story; "
        "7-8 = same subject type/setting, a viewer would accept it; 4-6 = only generally related scenery; 0-3 = unrelated, "
        "misleading, dirty/ugly, shows close-up faces, brands, logos, text, flags, or looks unprofessional. "
        + ("Generic scenery of the right kind of place or nature is acceptable here (score it up to 7). " if loose else
           "Do not give 7 or more to something that merely looks nice. ") +
        'Return ONLY JSON: {"scores": [{"i": 0, "score": 8}, {"i": 1, "score": 2}]}')}]
    usable = []
    for c in cands:
        try:
            img = requests.get(c["thumb"], timeout=30)
            img.raise_for_status()
            parts.append({"text": f"Photo {len(usable)}:"})
            parts.append({"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(img.content).decode()}})
            usable.append(c)
        except Exception:
            continue
    if not usable:
        return []
    need = 7 if loose else 8
    try:
        sc = script_writer._call(parts, 0.0).get("scores", [])
        ranked = sorted([(float(x.get("score", 0)), int(x["i"])) for x in sc if isinstance(x, dict) and "i" in x], reverse=True)
        picks = [i for (v, i) in ranked if v >= need][:want]
        print(f"[stock] '{(headline or '')[:30]}': best scores {[v for (v, i) in ranked[:3]]} (need {need})")
    except Exception as e:
        print(f"[stock] picture check failed, using nothing from this search: {e}")
        picks = []
    out = []
    for n_, idx in enumerate([i for i in picks if isinstance(i, int) and 0 <= i < len(usable)][:want]):
        c = usable[idx]
        path = f"{out_prefix}_{n_}.mp4" if kind == "video" else f"{out_prefix}_{n_}.jpg"
        try:
            data = requests.get(c["full"], timeout=180)
            data.raise_for_status()
            with open(path, "wb") as f:
                f.write(data.content)
            if kind == "video":
                if os.path.getsize(path) < 50_000:
                    raise ValueError("video file too small")
            else:
                Image.open(path).verify()
            out.append({"path": path, "photographer": c["photographer"], "url": c["url"], "source": c["source"]})
        except Exception as e:
            print(f"[stock] download skipped: {e}")
    print(f"[stock] '{(headline or '')[:30]}': {len(usable)} candidates, {len(out)} matched")
    return out


def best_photos(headline, narration, queries, out_prefix, want=2, kind="photo"):
    """First the specific searches; if nothing fits, broader searches and a more generous check."""
    out = _best_photos_once(headline, narration, queries, out_prefix, want, False, kind)
    if out:
        return out
    try:
        import script_writer
        r = script_writer._call(
            "Story headline: " + (headline or "") + "\nStory: " + (narration or "") +
            "\nGive 4 SHORT, broad stock-photo search phrases (2-3 words, English) for generic scenery that "
            "would suit this story, e.g. 'coastal park', 'city skyline', 'green park trees', 'sea sunset'. "
            'No people, no names. Return ONLY JSON: {"queries": ["...", "..."]}', 0.3)
        broad = [q for q in r.get("queries", []) if isinstance(q, str)][:4]
    except Exception as e:
        print(f"[stock] broad queries failed: {e}")
        broad = []
    if not broad:
        return []
    print(f"[stock] second try with broader searches: {broad}")
    return _best_photos_once(headline, narration, broad, out_prefix, want, True, kind)
