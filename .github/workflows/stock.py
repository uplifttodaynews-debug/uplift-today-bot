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
