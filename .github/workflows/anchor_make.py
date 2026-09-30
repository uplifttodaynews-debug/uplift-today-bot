"""
anchor_make.py - one-off helper (NOT part of the daily run): creates the AI news presenter "Kavya".
Stage 1 ("candidates"): makes 4 different face candidates so the owner can choose one.
Images are saved in the repo folder anchor/ so Claude and the owner can look at them.
Cost: about 4 images = roughly 10 cents.
"""
import os
import sys
import requests

KEY = os.environ.get("FAL_KEY", "").strip()
if not KEY:
    print("FAL_KEY secret is missing or empty")
    sys.exit(1)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "anchor")
os.makedirs(os.path.join(OUT, "candidates"), exist_ok=True)

BASE = (
    "Professional studio photograph of a young Indian woman television news presenter, about 25 years old, "
    "sleek high ponytail, warm confident friendly expression with a soft closed-mouth smile, "
    "wearing a tailored navy blazer over a white shirt, sitting at a modern news desk, "
    "bright warm studio with soft golden sunrise-coloured lights in the background, "
    "medium shot from the waist up, facing the camera directly, sharp focus, realistic skin, "
    "natural lighting, high quality broadcast look"
)


def generate(prompt, seed):
    r = requests.post(
        "https://fal.run/fal-ai/flux/dev",
        headers={"Authorization": f"Key {KEY}", "Content-Type": "application/json"},
        json={"prompt": prompt, "image_size": {"width": 1280, "height": 720}, "num_images": 1,
              "seed": seed, "output_format": "jpeg", "enable_safety_checker": True},
        timeout=300,
    )
    if r.status_code != 200:
        print("fal error", r.status_code, r.text[:400])
        r.raise_for_status()
    url = r.json()["images"][0]["url"]
    return requests.get(url, timeout=120).content


if __name__ == "__main__":
    for i, seed in enumerate([11, 222, 3333, 44444], start=1):
        data = generate(BASE, seed)
        path = os.path.join(OUT, "candidates", f"kavya_{i}.jpg")
        with open(path, "wb") as f:
            f.write(data)
        print("saved", path, len(data), "bytes", flush=True)
