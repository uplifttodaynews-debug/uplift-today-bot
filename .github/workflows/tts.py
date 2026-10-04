"""
tts.py - Step 3: turn text into Hindi speech with Google Text-to-Speech.
Each piece (intro, each story, outro) is a separate short audio file.
"""
import base64
import os
import requests
import config


def speak(text, out_path):
    key = os.environ["GOOGLE_TTS_API_KEY"]
    body = {
        "input": {"text": text},
        "voice": {"languageCode": config.LANGUAGE_CODE, "name": config.VOICE_NAME},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": getattr(config, "SPEAKING_RATE", 1.0)},
    }
    r = requests.post(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        params={"key": key},
        json=body,
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"TTS error {r.status_code}: {r.text[:500]}")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(r.json()["audioContent"]))
    return out_path
