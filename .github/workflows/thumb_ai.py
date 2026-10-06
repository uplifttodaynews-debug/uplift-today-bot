"""thumb_ai.py - an attractive, story-specific thumbnail picture made with AI (fal.ai flux/dev, about 3 cents)."""
import os
import requests
import script_writer


def make_image(story, out_path):
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        return None
    try:
        p = script_writer._call(
            "Write ONE English prompt for an AI image generator to make the BACKGROUND PICTURE of a YouTube thumbnail "
            "about this news story. Photographic, warm natural light, vivid but natural colours, shallow depth of field, "
            "emotional and uplifting. The main subject sits on the RIGHT half of the frame; the LEFT third is soft and "
            "uncluttered (a headline will be placed there). Show ordinary, generic people or things that symbolise the "
            "story. NO text, letters, logos, flags, no real or famous people, no newsroom. Max 70 words.\n"
            f"Story headline: {story.get('headline', '')}\nStory: {story['narration'][:900]}\n"
            'Return ONLY JSON: {"prompt": "..."}', 0.6).get("prompt", "")
        if len(p) < 20:
            return None
        print(f"[thumb] image prompt: {p}")
        r = requests.post("https://fal.run/fal-ai/flux/dev",
                          headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
                          json={"prompt": p, "image_size": {"width": 1280, "height": 720}, "num_images": 1,
                                "output_format": "jpeg", "enable_safety_checker": True}, timeout=300)
        if r.status_code != 200:
            print(f"[thumb] fal error {r.status_code}: {r.text[:200]}")
            return None
        data = requests.get(r.json()["images"][0]["url"], timeout=120).content
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path
    except Exception as e:
        print(f"[thumb] AI picture failed: {e}")
        return None
