"""thumbs_img.py - makes background pictures for thumbnails from the ideas in thumb-request.txt (one idea per line). Nothing is uploaded."""
import os
import thumb_ai

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
STYLE = (" Photographic, warm natural light, vivid natural colours, shallow depth of field, emotional and uplifting. "
         "The main subject sits on the RIGHT half of the frame; the LEFT third is soft and uncluttered. "
         "NO text, letters, logos or flags.")


def main():
    key = os.environ["FAL_KEY"].strip()
    out = os.path.join(ROOT, "previews", "thumb_imgs")
    os.makedirs(out, exist_ok=True)
    ideas = [l.strip() for l in open(os.path.join(ROOT, "thumb-request.txt"), encoding="utf-8") if l.strip()]
    for i, idea in enumerate(ideas, 1):
        try:
            if thumb_ai._fal(idea + STYLE, os.path.join(out, f"img{i}.jpg"), key):
                print(f"[thumb] picture {i} done")
        except Exception as e:
            print(f"[thumb] picture {i} failed: {e}")


if __name__ == "__main__":
    main()
