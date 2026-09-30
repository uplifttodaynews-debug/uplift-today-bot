"""
stock.py - fetches free stock photos from Pexels to use as video backgrounds.
Pexels licence: free for commercial use, credit not required but requested - so we
put a credit line in every video description. If anything goes wrong (no key, no
result, network problem) we simply return None and the video uses the sunrise gradient.
"""
import os
import random
import requests
from PIL import Image

import config

API = "https://api.pexels.com/v1/search"


def fetch(query, out_path, seed=0):
    """Download one landscape photo for `query`. Returns {"path","photographer","url"} or None."""
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
        }
    except Exception as e:
        print(f"[stock] skipped '{query}': {e}")
        return None
