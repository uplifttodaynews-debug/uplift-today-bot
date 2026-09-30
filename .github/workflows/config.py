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
GEMINI_MODEL = "gemini-2.5-flash"

# ---- Bulletin size ----
NUM_STORIES = 4                  # 4 stories ~ 3 minutes
MIN_STORIES = 3                  # fewer good stories than this = skip the day

# ---- Positive news sources (RSS). Used only as LEADS for facts. ----
RSS_FEEDS = [
    "https://www.goodnewsnetwork.org/feed/",
    "https://www.positive.news/feed/",
    "https://reasonstobecheerful.world/feed/",
    "https://www.optimistdaily.com/feed/",
]
MAX_ITEMS_PER_FEED = 8

# ---- Words that make us reject a story before the AI even sees it ----
BLOCK_WORDS = [
    "war", "killed", "murder", "shooting", "attack", "terror", "bomb",
    "dead", "death", "died", "crash", "rape", "abuse", "trump", "election",
    "war", "hostage", "suicide", "lawsuit",
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
