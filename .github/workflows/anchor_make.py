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


def edit(image_path, prompt, seed):
    import base64
    b64 = base64.b64encode(open(image_path, "rb").read()).decode()
    r = requests.post(
        "https://fal.run/fal-ai/flux-pro/kontext",
        headers={"Authorization": f"Key {KEY}", "Content-Type": "application/json"},
        json={"prompt": prompt, "image_url": "data:image/jpeg;base64," + b64, "seed": seed,
              "output_format": "jpeg"},
        timeout=300,
    )
    if r.status_code != 200:
        print("fal error", r.status_code, r.text[:400])
        r.raise_for_status()
    return requests.get(r.json()["images"][0]["url"], timeout=120).content


def fair3():
    src = os.path.join(OUT, "candidates", "kavya_3.jpg")
    os.makedirs(os.path.join(OUT, "fair"), exist_ok=True)
    for i, seed in enumerate([5, 77], start=1):
        data = edit(src, "Make this woman's skin tone fairer and lighter, a light wheatish-fair complexion, "
                         "keep exactly the same face, smile, hairstyle, blazer and background", seed)
        path = os.path.join(OUT, "fair", f"fair_edit_{i}.jpg")
        open(path, "wb").write(data)
        print("saved", path, flush=True)
    for i, seed in enumerate([3333, 3334], start=1):
        data = generate(BASE.replace("a young Indian woman", "a young fair-skinned Indian woman with a light wheatish-fair complexion"), seed)
        path = os.path.join(OUT, "fair", f"fair_new_{i}.jpg")
        open(path, "wb").write(data)
        print("saved", path, flush=True)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "fair3":
    fair3()
elif __name__ == "__main__":
    for i, seed in enumerate([11, 222, 3333, 44444], start=1):
        data = generate(BASE, seed)
        path = os.path.join(OUT, "candidates", f"kavya_{i}.jpg")
        with open(path, "wb") as f:
            f.write(data)
        print("saved", path, len(data), "bytes", flush=True)
