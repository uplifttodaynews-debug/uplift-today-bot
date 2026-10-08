"""thumb_ai.py - an attractive, story-specific thumbnail picture made with AI (fal.ai flux/dev, about 3 cents)."""
import os
import requests
import script_writer


def make_image(story, out_path, hint=""):
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        return None
    try:
        p = script_writer._call(
            "Write ONE English prompt for an AI image generator to make the BACKGROUND PICTURE of a YouTube thumbnail "
            "about this news story. Photographic, warm natural light, vivid but natural colours, shallow depth of field, "
            "emotional and uplifting. The main subject sits on the RIGHT half of the frame; the LEFT third is soft and "
            "uncluttered (a headline will be placed there). Show ordinary, generic people or things that symbolise the "
            "story. People must look like they belong to the story's own country and culture (for an Indian story show Indian people and a local setting, never generic Western stock-photo people). NO text, letters, logos, flags, no real or famous people, no newsroom. Max 70 words.\n" + (f"Composition idea to follow: {hint}\n" if hint else "") + 
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


def _fal(prompt, out_path, key, size=(1280, 720)):
    r = requests.post("https://fal.run/fal-ai/flux/dev",
                      headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
                      json={"prompt": prompt, "image_size": {"width": size[0], "height": size[1]}, "num_images": 1,
                            "output_format": "jpeg", "enable_safety_checker": True}, timeout=300)
    if r.status_code != 200:
        print(f"[thumb] fal error {r.status_code}: {r.text[:200]}")
        return None
    with open(out_path, "wb") as f:
        f.write(requests.get(r.json()["images"][0]["url"], timeout=120).content)
    return out_path


def make_illustrations(story, out_prefix, n=3):
    """Fallback pictures for a story with no matching stock footage: n different AI illustrations."""
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        return []
    try:
        ps = script_writer._call(
            f"Write {n} DIFFERENT English prompts for an AI image generator, each a photographic, natural, uplifting "
            "wide scene (different subject and angle each) that illustrates THIS news story. Show the specific things the "
            "story text describes (for example painted murals on village walls, a street being swept, a booklet being written), "
            "set in the story's own country and culture (Indian stories: Indian people, clothing and local setting). "
            "Generic people or places only, NO text, letters, logos, flags, no famous people. NEVER show injuries, wounds, "
            "scars, blood, hospitals beds in distress or anything disturbing: show dignity, hope, support and recovery instead. Max 50 words each.\n"
            f"Story: {story.get('headline', '')}. {story['narration'][:2200]}\n"
            'Return ONLY JSON: {"prompts": ["...", "..."]}', 0.7).get("prompts", [])
    except Exception as e:
        print(f"[thumb] illustration prompts failed: {e}")
        return []
    out = []
    for i, p in enumerate(ps[:n]):
        try:
            path = _fal(p, f"{out_prefix}_ai{i}.jpg", key)
            if path:
                out.append(path)
        except Exception as e:
            print(f"[thumb] illustration failed: {e}")
    return out
