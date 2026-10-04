"""
config.py - ALL the settings live here. To change the voice, language, video
privacy or news sources later, you only edit this one file.
"""

# ---- Channel ----
CHANNEL_NAME = "Uplift Today Hindi"
CHANNEL_HANDLE = "@UpliftTodayHindi"
LANGUAGE_NAME = "Hindi"          # used in the AI instructions
LANGUAGE_CODE = "hi-IN"          # used by the voice service

# ---- Publishing ----
# Keep "private" until you have checked several videos and the YouTube audit
# is sorted out. Change to "public" later (one word).
PRIVACY = "private"

# ---- Voice (Google Chirp 3 HD). Try: Aoede, Kore, Leda, Zephyr (female) ----
VOICE_NAME = "hi-IN-Chirp3-HD-Aoede"

# ---- AI writer (Gemini). If Google retires this name, change it here. ----
GEMINI_MODEL = "gemini-3.8-flash"

# ---- Bulletin size ----
NUM_STORIES = 3                  # 3 in-depth stories of ~150 words, read slowly ~ 4 minutes
SPEAKING_RATE = 0.95             # slower, clearer voice (1.0 = normal)
PICS_PER_STORY = 4               # longer stories need a few more pictures
MIN_STORIES = 2                  # fewer good stories than this = skip the day
MAX_PER_SOURCE = 2               # no more than 2 stories from the same website
EXTRA_CANDIDATES = 3             # AI writes a few extra stories, the fact-check keeps the good ones

# ---- Positive news sources (RSS). Used only as LEADS for facts. ----
RSS_FEEDS = [
    "https://www.goodnewsnetwork.org/feed/",
    "https://www.positive.news/feed/",
    "https://reasonstobecheerful.world/feed/",
    "https://www.optimistdaily.com/feed/",
    "https://www.thebetterindia.com/feed/",
    "https://www.goodgoodgood.co/articles/rss.xml",
]
MAX_ITEMS_PER_FEED = 8

# ---- Words that make us reject a story before the AI even sees it ----
BLOCK_WORDS = [
    "war", "killed", "murder", "shooting", "attack", "terror", "bomb",
    "dead", "death", "died", "crash", "rape", "abuse", "trump", "election",
    "hostage", "suicide", "lawsuit",
]

# ---- Look of the video ----
VIDEO_SIZE = (1280, 720)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]
GRADIENT_TOP = (255, 150, 60)
GRADIENT_BOTTOM = (190, 55, 100)

# ---- English captions under the Hindi headline ----
ENGLISH_CAPTIONS = True          # False = no English captions
LATIN_FONT_CANDIDATES = [        # fonts that have English letters
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

# ---- Background music (original tracks in the music/ folder) ----
BACKGROUND_MUSIC = True
MUSIC_FOLDER = "music"
MUSIC_VOLUME = 0.40              # how loud the music is before it ducks under the voice
MUSIC_INTRO_BOOST = 1.3          # piano is a little louder during the greeting
MUSIC_INTRO_SECONDS = 12         # how long (after the opening) the louder part lasts

# ---- Stock photos (Pexels). Needs the PEXELS_API_KEY secret; without it the sunrise gradient is used ----
STOCK_PHOTOS = True
STOCK_VIDEOS = True              # use short stock video clips for some stories
VIDEO_SHARE = 0.5                # about this share of the stories get video clips (the rest photos)
PHOTOS_PER_STORY = 2             # the picture changes once in the middle of each story
FIXED_SLIDE_QUERIES = {          # for the opening, thought and closing slides
    "intro": "sunrise sky",
    "thought": "calm lake morning",
    "outro": "sunlight through trees",
}

# ---- News-style opening (about 5 seconds, made once by make_intro.py) ----
INTRO_CLIP = "intro/intro.mp4"   # set to "" to switch the opening off

# ---- Talking AI presenter (Kavya) via fal.ai. Needs the FAL_KEY secret. ----
ANCHOR = True
ANCHOR_MODEL = "fal-ai/kling-video/ai-avatar/v2/pro"   # the clip you chose (about $0.115 per second)
ANCHOR_ZOOM = 1.35               # slight zoom on the presenter, anchored at the top, so her hands stay out of frame
ANCHOR_MAX_SECONDS = 14          # safety cap so the daily cost stays small; longer greetings use the normal slide


# ---- India date and special-day greetings ----
import datetime as _dt
from zoneinfo import ZoneInfo as _Zone


def today_india():
    """Today's date in India (the daily build runs at 23:30 UTC, which is already tomorrow in India)."""
    return _dt.datetime.now(_Zone("Asia/Kolkata")).date()


# (month, day): what Kavya says first on that day (Hindi). Fixed-date national days only.
SPECIAL_DAYS = {
    (1, 1): "नया साल मुबारक हो! अपलिफ्ट टुडे में आपका स्वागत है। आइए सुनें आज की पॉज़िटिव ख़बरें।",
    (1, 26): "गणतंत्र दिवस की हार्दिक शुभकामनाएं! अपलिफ्ट टुडे में आपका स्वागत है। आइए सुनें आज की पॉज़िटिव ख़बरें।",
    (8, 15): "स्वतंत्रता दिवस की हार्दिक शुभकामनाएं! अपलिफ्ट टुडे में आपका स्वागत है। आइए सुनें आज की पॉज़िटिव ख़बरें।",
    (10, 2): "गांधी जयंती की हार्दिक शुभकामनाएं! अपलिफ्ट टुडे में आपका स्वागत है। आइए सुनें आज की पॉज़िटिव ख़बरें।",
}
