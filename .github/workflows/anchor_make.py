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


OUTFITS = [
    ("mustard_blazer", "a soft mustard-yellow blazer over a white top"),
    ("teal_kurta", "a simple teal-green kurta with a fine subtle embroidered neckline"),
    ("maroon_blazer", "a deep maroon blazer over a cream shirt"),
    ("peach_kurta", "a simple pastel peach kurta with a delicate neckline"),
    ("grey_blazer", "a light grey blazer over a royal blue shirt"),
    ("ivory_blazer", "an ivory blazer over a sky-blue top"),
]


def outfits():
    base = os.path.join(OUT, "fair", "fair_edit_2.jpg")
    os.makedirs(os.path.join(OUT, "outfits"), exist_ok=True)
    import shutil
    shutil.copy(base, os.path.join(OUT, "outfits", "0_navy_blazer.jpg"))
    for i, (name, desc) in enumerate(OUTFITS, start=1):
        data = edit(base, f"Change only her clothing: she now wears {desc}. Keep exactly the same face, "
                          "skin tone, smile, ponytail, pose, camera angle and the same background.", 100 + i)
        path = os.path.join(OUT, "outfits", f"{i}_{name}.jpg")
        open(path, "wb").write(data)
        print("saved", path, flush=True)


def lipsync_test():
    """Hindi line -> Google voice -> talking Kavya (VEED Fabric, 480p). Saves anchor/test/."""
    import base64
    import time
    import tts
    os.makedirs(os.path.join(OUT, "test"), exist_ok=True)
    audio = os.path.join(OUT, "test", "line.mp3")
    tts.speak("नमस्ते! आपका स्वागत है अपलिफ्ट टुडे में। आज की सबसे अच्छी और उम्मीद भरी खबरें, सीधे आपके लिए।", audio)
    img = os.path.join(OUT, "outfits", "0_navy_blazer.jpg")
    body = {
        "image_url": "data:image/jpeg;base64," + base64.b64encode(open(img, "rb").read()).decode(),
        "audio_url": "data:audio/mpeg;base64," + base64.b64encode(open(audio, "rb").read()).decode(),
        "resolution": "480p",
    }
    h = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}
    r = requests.post("https://queue.fal.run/veed/fabric-1.0", headers=h, json=body, timeout=300)
    print("submit", r.status_code, r.text[:300])
    if r.status_code >= 300:
        raise RuntimeError(f"submit failed {r.status_code}: {r.text[:600]}")
    sub = r.json()
    for _ in range(120):
        st = requests.get(sub["status_url"], headers=h, timeout=60).json()
        print("status", st.get("status"), flush=True)
        if st.get("status") == "COMPLETED":
            break
        time.sleep(5)
    res = requests.get(sub["response_url"], headers=h, timeout=60)
    print("result", res.status_code, res.text[:300])
    if res.status_code >= 300:
        raise RuntimeError(f"result failed {res.status_code}: {res.text[:1500]}")
    url = res.json()["video"]["url"]
    with open(os.path.join(OUT, "test", "kavya_test.mp4"), "wb") as f:
        f.write(requests.get(url, timeout=300).content)
    print("saved test video")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "test":
    import traceback
    try:
        lipsync_test()
    except Exception:
        os.makedirs(os.path.join(OUT, "test"), exist_ok=True)
        open(os.path.join(OUT, "test", "error.txt"), "w").write(traceback.format_exc())
        print("test failed, see anchor/test/error.txt")
elif __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "outfits":
    outfits()
elif __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "fair3":
    fair3()
elif __name__ == "__main__":
    for i, seed in enumerate([11, 222, 3333, 44444], start=1):
        data = generate(BASE, seed)
        path = os.path.join(OUT, "candidates", f"kavya_{i}.jpg")
        with open(path, "wb") as f:
            f.write(data)
        print("saved", path, len(data), "bytes", flush=True)
