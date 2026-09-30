"""
avatar.py - makes the talking AI presenter (Kavya) for one piece of audio.
A still picture of Kavya (a different outfit each weekday) + the Hindi voice -> a talking video (fal.ai).
If anything goes wrong (no key, no credit, service down) it returns None and the bulletin simply uses
the normal slide instead - the daily video is never blocked.
"""
import datetime
import glob
import os
import time

import requests

import config

HERE = os.path.dirname(os.path.abspath(__file__))
OUTFITS = os.path.join(HERE, "..", "..", "anchor", "outfits")


def _headers():
    return {"Authorization": f"Key {os.environ['FAL_KEY'].strip()}", "Content-Type": "application/json"}


def _upload(path, content_type):
    r = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3",
                      headers=_headers(),
                      json={"content_type": content_type, "file_name": os.path.basename(path)}, timeout=60)
    r.raise_for_status()
    info = r.json()
    put = requests.put(info["upload_url"], data=open(path, "rb").read(),
                       headers={"Content-Type": content_type}, timeout=300)
    put.raise_for_status()
    return info["file_url"]


def todays_picture():
    pics = sorted(glob.glob(os.path.join(OUTFITS, "*.jpg")))
    if not pics:
        return None
    return pics[datetime.date.today().weekday() % len(pics)]


def make_clip(audio_path, out_path):
    """Returns out_path, or None if the talking clip could not be made."""
    if not config.ANCHOR or not os.environ.get("FAL_KEY", "").strip():
        return None
    try:
        pic = todays_picture()
        if not pic:
            return None
        body = {"image_url": _upload(pic, "image/jpeg"), "audio_url": _upload(audio_path, "audio/mpeg")}
        r = requests.post("https://queue.fal.run/" + config.ANCHOR_MODEL, headers=_headers(), json=body, timeout=120)
        r.raise_for_status()
        sub = r.json()
        for _ in range(180):                                   # wait up to 15 minutes
            st = requests.get(sub["status_url"], headers=_headers(), timeout=60).json()
            if st.get("status") == "COMPLETED":
                break
            if st.get("status") in ("FAILED", "ERROR"):
                raise RuntimeError(f"fal job failed: {str(st)[:300]}")
            time.sleep(5)
        res = requests.get(sub["response_url"], headers=_headers(), timeout=60)
        if res.status_code >= 300:
            raise RuntimeError(f"fal result {res.status_code}: {res.text[:300]}")
        data = requests.get(res.json()["video"]["url"], timeout=300)
        data.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(data.content)
        print(f"[avatar] talking clip ready ({os.path.basename(pic)})")
        return out_path
    except Exception as e:
        print(f"[avatar] skipped: {e}")
        return None
