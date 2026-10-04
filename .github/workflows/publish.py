"""publish.py - uploads a video that was prepared earlier (hold_out/) to YouTube as PRIVATE, then remembers its stories."""
import json
import os
import upload

HERE = os.path.dirname(os.path.abspath(__file__))
HOLD = os.path.join(HERE, "..", "..", "hold_out")


def main():
    with open(os.path.join(HOLD, "meta.json"), encoding="utf-8") as f:
        m = json.load(f)
    upload.upload(os.path.join(HOLD, "bulletin.mp4"), m["title"], m["description"], m["tags"],
                  os.path.join(HOLD, "thumbnail.png"))
    p = os.path.join(HERE, "..", "..", "approval", "used.json")
    try:
        with open(p, encoding="utf-8") as f:
            used = json.load(f)
    except Exception:
        used = []
    for link in m.get("links", []):
        if link:
            used.append({"link": link, "date": m.get("date")})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(used, f, indent=1)
    print("[publish] uploaded (private) and stories remembered")


if __name__ == "__main__":
    main()
