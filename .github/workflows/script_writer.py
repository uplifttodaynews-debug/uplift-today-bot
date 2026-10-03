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
    """`prompt` is a text string, or a list of parts (text and/or inline images) for picture checks."""
    key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}] if isinstance(prompt, str) else prompt}],
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
1. Choose the {config.NUM_STORIES + config.EXTRA_CANDIDATES} best stories. We want REAL, IMPACTFUL, MORALE-BOOSTING news:
   a concrete good outcome for real people or the planet (lives improved or saved, a problem actually
   solved, measurable results, a breakthrough, courage, kindness, a community or individual who made a
   difference, a young person or ordinary person who overcame odds). Prefer stories ABOUT PEOPLE: health,
   education, science and inventions, community heroes, environment recovery that helps people, sports
   achievements. Give each story an "impact" score from 1 to 10 (10 = changes many lives or deeply
   inspiring; 5 = nice but small) and a "topic": one of people, health, science, environment, education,
   sports, animals, other. Animal or wildlife stories are allowed only when they are truly significant,
   and at most ONE per bulletin. REJECT fluff and cute-only items, celebrity news, product launches or
   marketing, corporate PR donations, listicles, opinion pieces, and anything about war, crime, politics,
   disasters, tragedy, illness without a clear hopeful outcome, or anything with a negative or
   frightening feel. Put the most inspiring, highest-impact story first.
2. Choose stories from DIFFERENT sources. Never more than {config.MAX_PER_SOURCE} stories from the same source.
3. Use ONLY facts that appear in the lead text. Do NOT invent or guess names, numbers, places,
   dates, causes or quotes. If a detail is not in the lead, leave it out. Do not add background
   from your own memory. If a lead has too little information for a full story, skip it.
4. Write in natural SPOKEN {config.LANGUAGE_NAME} (Devanagari script), in your OWN words. Never copy
   sentences from the lead. Use SHORT sentences (under 15 words each) and a warm conversational
   tone, like talking to a friend.
   LANGUAGE LEVEL: use simple, everyday Hindi that an ordinary person speaks at home. Do NOT use
   heavy, formal or Sanskritized words (no "shuddh" bookish Hindi). Where an English word is what
   people really say (doctor, hospital, school, computer, scientist, research, team, electric,
   solar, energy, rupees, million), write that English word in Devanagari, like "doctor",
   "scientist", "hospital" - this is normal spoken Hindi/Hinglish. Avoid long lists of numbers.
   Each story: 60-80 words, in 4-6 short sentences.
5. Return fewer than {config.NUM_STORIES + config.EXTRA_CANDIDATES} stories if there are not enough good ones.
6. "thought" = one short, original, uplifting line in {config.LANGUAGE_NAME}. Do NOT attribute it to
   any real person.
7. "title" = a YouTube title in {config.LANGUAGE_NAME}, under 70 characters, hopeful, truthful. Do NOT put any number
   of stories in the title (no "8 news", no "5 stories"); name the most inspiring story or the feeling instead.
8. "headline" for each story = a very short on-screen headline (max 6 words).
9. "visual_queries" for each story = exactly 4 short English search phrases (1-4 words each) for FREE
   STOCK PHOTOS AND VIDEOS that would literally show the SUBJECT and SETTING of THIS story:
   (a) the main living or physical subject on its own, one or two words ("monkey", "deer", "wetland birds",
   "solar panels", "school children");
   (b) the subject in its setting ("monkey sanctuary forest", "wildlife overpass highway");
   (c) if the story names a city, region or country, the place itself ("Athens Greece", "Athens coast",
   "Jharkhand India river"), otherwise another specific view of the subject;
   (d) one more concrete view (aerial, close-up, wide shot).
   Use concrete things that appear in a photo, never abstract words or verbs like "cleaning", "initiative"
   or "success". NEVER ask for famous people, brands, logos, flags, or anything that would pretend to show
   the actual event.
10. SPELLING AND WORDS: always write the Hindi word for news with the dot under the first letter:
   ख़बर / ख़बरें (never खबर). Never use the word "सकारात्मक"; say the English word "positive" in
   Devanagari ("पॉज़िटिव") instead, e.g. "पॉज़िटिव ख़बरें".

Return ONLY JSON with this exact shape:
{{"title": "...", "intro": "...", "stories": [{{"lead_index": 0, "topic": "people", "impact": 8, "headline": "...", "visual_queries": ["...", "...", "...", "..."], "narration": "..."}}],
  "thought": "...", "outro": "..."}}

"intro" = ONE short sentence (at most 14 words, it must be spoken in under 10 seconds) that says the channel name "Uplift Today" and welcomes viewers to
today's positive news (say "पॉज़िटिव ख़बरें"). "outro" = a 1-2 sentence warm goodbye asking viewers to subscribe.

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
    """Second, independent check. Returns (passed, failed). failed items carry 'problem'."""
    checks = []
    for n, s_ in enumerate(stories):
        src = s_.get("source")
        if not src:
            continue
        checks.append(
            f"[{n}] SOURCE LEAD: {src['title']} - {src['summary']}\n"
            f"    NARRATION ({config.LANGUAGE_NAME}): {s_['narration']}"
        )
    if not checks:
        return [], []
    prompt = (
        "You are a fact-checker for a positive-news bulletin. For each item, compare the NARRATION "
        "with the SOURCE LEAD.\n"
        "The narration is SUPPORTED if every claim in it is stated in the lead (paraphrasing is fine). "
        "You MAY accept plain, undisputed geography that only names the country or continent of a place "
        "the lead names (for example Athens -> Greece) - that is not a problem.\n"
        "It is NOT supported if it adds a claim, a number, a name, a date, a cause, a result, a benefit "
        "or an opinion that is not in the lead, exaggerates, or changes the meaning. It is also NOT "
        "acceptable if the story is sad, political or frightening rather than uplifting.\n"
        'Return ONLY JSON: {"results": [{"i": 0, "supported": true, "problem": ""}]}\n\n'
        + "\n\n".join(checks)
    )
    result = _call(prompt, 0.0)
    verdict = {r.get("i"): r for r in result.get("results", [])}
    passed, failed = [], []
    for n, s_ in enumerate(stories):
        r = verdict.get(n)
        if r and r.get("supported") is True:
            passed.append(s_)
        else:
            problem = (r or {}).get("problem", "not checked")
            print(f"[verify] story {n} flagged: {problem}")
            s_["problem"] = problem
            failed.append(s_)
    return passed, failed


def repair(failed):
    """Ask the writer to rewrite flagged stories using ONLY the facts in each lead."""
    parts = []
    for n, s_ in enumerate(failed):
        src = s_["source"]
        parts.append(
            f"[{n}] SOURCE LEAD: {src['title']} - {src['summary']}\n"
            f"    OLD NARRATION: {s_['narration']}\n"
            f"    PROBLEM FOUND: {s_.get('problem', '')}"
        )
    prompt = (
        f"Rewrite each {config.LANGUAGE_NAME} news narration so it uses ONLY facts stated in its SOURCE "
        "LEAD. Remove the problem described. Do not add benefits, results, opinions, places, numbers "
        "or background that the lead does not state. Keep it warm, positive, in simple everyday spoken "
        f"{config.LANGUAGE_NAME} (Devanagari) with short sentences, 45-70 words. If the lead has too little "
        "information, write a shorter narration rather than adding anything.\n"
        'Return ONLY JSON: {"results": [{"i": 0, "narration": "..."}]}\n\n' + "\n\n".join(parts)
    )
    result = _call(prompt, 0.2)
    fixed = []
    for r in result.get("results", []):
        i = r.get("i")
        if isinstance(i, int) and 0 <= i < len(failed) and r.get("narration"):
            item = dict(failed[i])
            item["narration"] = r["narration"]
            item.pop("problem", None)
            fixed.append(item)
    return fixed


def translate(texts):
    """Translate finished Hindi lines into plain English captions (faithful, nothing added)."""
    numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts))
    prompt = (
        f"Translate each {config.LANGUAGE_NAME} line into natural, simple English for on-screen captions. "
        "Translate faithfully: do NOT add, remove or explain anything, and keep every name and number. "
        "Keep sentence breaks, using normal punctuation.\n"
        'Return ONLY JSON: {"results": [{"i": 0, "english": "..."}]}\n\n' + numbered
    )
    result = _call(prompt, 0.0)
    out = [""] * len(texts)
    for r in result.get("results", []):
        i = r.get("i")
        if isinstance(i, int) and 0 <= i < len(texts):
            out[i] = (r.get("english") or "").strip()
    return out


def polish_hindi(text):
    """Fixed spelling/wording preferences for spoken Hindi (so the voice says them the way we want)."""
    if not isinstance(text, str):
        return text
    return text.replace("खबर", "ख़बर").replace("सकारात्मक", "पॉज़िटिव")
