"""
script_writer.py - Step 2: Gemini picks the best positive stories and writes
a short Hindi bulletin in ORIGINAL words, using only facts we gave it.
"""
import json
import os
import requests
import config


def _prompt(items):
    lines = []
    for i, it in enumerate(items):
        lines.append(f"[{i}] ({it['source']}) {it['title']} - {it['summary']}")
    leads = "\n".join(lines)
    return f"""You are the editor of "{config.CHANNEL_NAME}", a daily {config.LANGUAGE_NAME} bulletin of
ONLY positive, uplifting news, read by a warm, professional female news anchor.

Below are candidate story leads (number, source, headline, summary).

RULES:
1. Choose the {config.NUM_STORIES} best stories. Prefer science, health, environment recovery,
   kindness, education, sports achievements, community heroes. REJECT anything about war, crime,
   politics, disasters, tragedy, or anything with a negative feel.
2. Use ONLY facts that appear in the lead text. Do NOT invent names, numbers, places or quotes.
   If a detail is not in the lead, leave it out. If unsure, leave the story out.
3. Write in natural, spoken {config.LANGUAGE_NAME} (Devanagari script), in your OWN words. Never
   copy sentences from the lead. Each story: 2-3 short sentences (about 35-45 words) that are easy
   to listen to.
4. Return fewer than {config.NUM_STORIES} stories if there are not enough good ones.
5. "thought" = one short, original, uplifting line in {config.LANGUAGE_NAME}. Do NOT attribute it to
   any real person.
6. "title" = a YouTube title in {config.LANGUAGE_NAME}, under 70 characters, hopeful, no clickbait lies.
7. "headline" for each story = a very short on-screen headline (max 8 words).

Return ONLY JSON with this exact shape:
{{"title": "...", "intro": "...", "stories": [{{"lead_index": 0, "headline": "...", "narration": "..."}}],
  "thought": "...", "outro": "..."}}

"intro" = a 1-2 sentence greeting that says the channel name "Uplift Today" and welcomes viewers to
today's good news. "outro" = a 1-2 sentence warm goodbye asking viewers to subscribe.

LEADS:
{leads}
"""


def write(items):
    key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent"
    )
    body = {
        "contents": [{"parts": [{"text": _prompt(items)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        },
    }
    r = requests.post(url, params={"key": key}, json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:500]}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(text)

    stories = [s for s in data.get("stories", []) if s.get("narration")]
    for s in stories:
        idx = s.get("lead_index")
        s["source"] = items[idx] if isinstance(idx, int) and 0 <= idx < len(items) else None
    data["stories"] = stories
    return data
