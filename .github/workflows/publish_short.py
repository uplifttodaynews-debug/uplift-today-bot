"""publish_short.py - uploads the prepared Short (previews/short) to YouTube as PRIVATE."""
import os
import upload

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "previews", "short")


def main():
    with open(os.path.join(D, "description.txt"), encoding="utf-8") as f:
        lines = f.read().split("\n")
    title = lines[0].strip()
    desc = "\n".join(lines[2:]).strip()
    upload.upload(os.path.join(D, "short.mp4"), title, desc,
                  ["shorts", "good news", "positive news", "uplift today", "अच्छी खबर", "hindi news"], None)
    print("[publish] Short uploaded (private)")


if __name__ == "__main__":
    main()
