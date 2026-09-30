"""
script_writer.py - Step 2: Gemini picks the best positive stories and writes
a short Hindi bulletin in ORIGINAL words, using only facts we gave it.
Step 2b: a SECOND Gemini check compares every written story against its source
lead and throws away anything that adds facts that are not in the source.
"""
import json
import os
import requests
import config


def _call(prompt, temperature):
    key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": temperature,
        },
    }
    r = requests.post(url, params={"key": key}, json=body, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:500]}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def _write_prompt(items):
    lines = []
    for i, it in enumerate(items):
        lines.append(f"[{i}] ({it['source']}) {it['title']} - {it['summary']}")
    leads = "\n".join(lines)
    return f"""You are the editor of "{config.CHANNEL_NAME}", a daily {config.LANGUAGE_NAME} bulletin of
ONLY positive, uplifting news, read aloud by a warm, professional female news anchor.

Below are candidate story leads (number, source, headline, summary).

RULES:
1. Choose the {config.NUM_STORIES} best stories. Prefer science, health, environment recovery,
   kindness, education, sports achievements, community heroes. REJECT anything about war, crime,
   politics, disasters, tragedy, illness without a clear hopeful outcome, or anything with a
   negative or frightening feel.
2. Choose stories from DIFFERENT sources. Never more than {config.MAX_PER_SOURCE} stories from the same source.
3. Use ONLY facts that appear in the lead text. Do NOT invent or guess names, numbers, places,
   dates, causes or quotes. If a detail is not in the lead, leave it out. Do not add background
   from your own memory. If a lead has too little information for a full story, skip it.
4. Write in natural SPOKEN {config.LANGUAGE_NAME} (Devanagari script), in your OWN words. Never copy
   sentences from the lead. Use SHORT sentences (under 15 words each), simple everyday words,
   and a warm conversational tone, like talking to a friend. Avoid long lists of numbers and
   heavy formal words. Each story: 60-80 words, in 4-6 short sentences.
5. Return fewer than {config.NUM_STORIES} stories if there are not enough good ones.
6. "thought" = one short, original, uplifting line in {config.LANGUAGE_NAME}. Do NOT attribute it to
   any real person.
7. "title" = a YouTube title in {config.LANGUAGE_NAME}, under 70 characters, hopeful, truthful.
8. "headline" for each story = a very short on-screen headline (max 6 words).

Return ONLY JSON with this exact shape:
{{"title": "...", "intro": "...", "stories": [{{"lead_index": 0, "headline": "...", "narration": "..."}}],
  "thought": "...", "outro": "..."}}

"intro" = a 1-2 sentence greeting that says the channel name "Uplift Today" and welcomes viewers to
today's good news. "outro" = a 1-2 sentence warm goodbye asking viewers to subscribe.

LEADS:
{leads}
"""


def write(items):
    data = _call(_write_prompt(items), 0.7)
    stories = [s for s in data.get("stories", []) if s.get("narration")]
    for s in stories:
        idx = s.get("lead_index")
        s["source"] = items[idx] if isinstance(idx, int) and 0 <= idx < len(items) else None
    data["stories"] = stories
    return data


def verify(stories):
    """Second, independent check. Keeps only stories fully supported by their lead."""
    checks = []
    for n, s in enumerate(stories):
        src = s.get("source")
        if not src:
            continue
        checks.append(
            f"[{n}] SOURCE LEAD: {src['title']} - {src['summary']}\n"
            f"    NARRATION ({config.LANGUAGE_NAME}): {s['narration']}"
        )
    if not checks:
        return []
    prompt = (
        "You are a strict fact-checker. For each item, compare the NARRATION with the SOURCE LEAD. "
        "The narration is supported ONLY IF every name, number, place, date and claim in it appears "
        "in the lead (paraphrasing is fine). It is NOT supported if it adds any new fact, guesses a "
        "cause, exaggerates, or changes the meaning. It is also NOT acceptable if the story is "
        "sad, political or frightening rather than uplifting.\n"
        'Return ONLY JSON: {"results": [{"i": 0, "supported": true, "problem": ""}]}\n\n'
        + "\n\n".join(checks)
    )
    result = _call(prompt, 0.0)
    ok = set()
    for r in result.get("results", []):
        if r.get("supported") is True:
            ok.add(r.get("i"))
        else:
            print(f"[verify] dropped story {r.get('i')}: {r.get('problem', '')}")
    return [s for n, s in enumerate(stories) if n in ok]
