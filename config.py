"""
config.py — Central configuration for LinguaBridge.

Every tunable lives here: paths, theme colors, gamification numbers,
SRS parameters, audio settings. No other module should hard-code these.
"""

from pathlib import Path

# ---------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"
LESSONS_DIR = BASE_DIR / "lessons" / "data"

USER_DATA_DIR = BASE_DIR / "user_data"
DB_PATH = USER_DATA_DIR / "linguabridge.db"
TTS_CACHE_DIR = USER_DATA_DIR / "tts_cache"
RECORDINGS_DIR = USER_DATA_DIR / "audio_recordings"
EXPORTS_DIR = USER_DATA_DIR / "exports"

for _d in (USER_DATA_DIR, TTS_CACHE_DIR, RECORDINGS_DIR, EXPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

APP_NAME = "LinguaBridge"
APP_TAGLINE = "English ↔ Japanese"
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------- window
WINDOW_SIZE = "1080x720"
MIN_WINDOW_SIZE = (900, 620)

# ---------------------------------------------------------------- theme
# Japanese-inspired palette: indigo (藍 ai), vermilion (朱 shu),
# matcha green, sakura pink — applied over CustomTkinter light/dark bases.
COLORS = {
    "primary": "#3E64AD",        # ai indigo
    "primary_hover": "#32528F",
    "accent": "#E4513F",         # shu vermilion
    "accent_hover": "#C44434",
    "success": "#58A700",        # Duolingo-style green
    "success_bg": "#D7FFB8",
    "error": "#EA2B2B",
    "error_bg": "#FFDFE0",
    "warning": "#FFC800",
    "gold": "#FFC800",
    "sakura": "#F6C6D0",
    "matcha": "#7BA05B",
    "card_light": "#FFFFFF",
    "card_dark": "#2B2B33",
    "bg_light": "#F6F4EF",
    "bg_dark": "#1E1E24",
    "text_muted": "#8A8A8E",
    "streak": "#FF9600",
    "xp": "#1CB0F6",
    "heart": "#FF4B4B",
    "locked": "#B8B8B8",
}

# Preferred fonts (first installed one wins). Japanese-capable fonts first.
JAPANESE_FONTS = ["Yu Gothic UI", "Meiryo UI", "Meiryo", "Noto Sans JP",
                  "Noto Sans CJK JP", "Hiragino Sans", "MS Gothic", "TakaoGothic"]
UI_FONTS = ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Arial"]

# ---------------------------------------------------------------- gamification
XP_PER_CORRECT = 10
XP_PER_CORRECT_HARD = 15          # speaking / sentence-building exercises
XP_LESSON_BONUS = 20
XP_PERFECT_BONUS = 15
XP_REVIEW_ITEM = 5
DAILY_GOAL_XP = 50

MAX_HEARTS = 5
HEART_REFILL_MINUTES = 30         # one heart regenerates every N minutes
HEARTS_FROM_REVIEW = 1            # completing a review session restores hearts

LEAGUES = [
    ("Bronze", 0), ("Silver", 150), ("Gold", 400), ("Sapphire", 800),
    ("Ruby", 1500), ("Emerald", 2500), ("Diamond", 4000),
]

BADGES = {
    "first_steps":   ("🌱", "First Steps", "Complete your first lesson"),
    "streak_3":      ("🔥", "On Fire", "Reach a 3-day streak"),
    "streak_7":      ("🏮", "Lantern Lit", "Reach a 7-day streak"),
    "xp_100":        ("⚡", "Spark", "Earn 100 total XP"),
    "xp_500":        ("🌊", "Great Wave", "Earn 500 total XP"),
    "perfect":       ("🎯", "Perfectionist", "Finish a lesson with no mistakes"),
    "reviewer":      ("🧠", "Memory Master", "Review 20 SRS cards"),
    "five_lessons":  ("🗻", "Climbing Fuji", "Complete 5 different lessons"),
    "speaker":       ("🎤", "Brave Voice", "Pass 10 speaking exercises"),
}

ENCOURAGEMENTS_CORRECT = [
    "Great job! すごい！", "Excellent! 完璧！", "You nailed it!",
    "Wonderful! その調子！", "Amazing work!", "Correct — keep it up!",
]
ENCOURAGEMENTS_WRONG = [
    "Almost there — you've got this!", "Good try! Let's look at the answer.",
    "Not quite, but every mistake teaches us. がんばって！",
    "So close! Take note and move on.", "Keep going — progress, not perfection!",
]

# ---------------------------------------------------------------- SRS (SM-2 style)
SRS_DEFAULT_EASE = 2.5
SRS_MIN_EASE = 1.3
SRS_FIRST_INTERVAL_DAYS = 1
SRS_SECOND_INTERVAL_DAYS = 3
SRS_MAX_INTERVAL_DAYS = 180
SRS_NEW_CARDS_PER_SESSION = 8
SRS_REVIEW_LIMIT = 20

# ---------------------------------------------------------------- scoring
TEXT_MATCH_THRESHOLD = 85         # % fuzzy similarity to count as correct
PRONUNCIATION_PASS = 70           # % similarity STT-vs-target to pass speaking
LISTEN_REPEAT_PASS = 65

# ---------------------------------------------------------------- audio
TTS_DEFAULT_SPEED = 1.0           # via settings: 0.7 (slow) – 1.3 (fast)
STT_TIMEOUT = 6                   # seconds waiting for speech to start
STT_PHRASE_LIMIT = 8              # max seconds of speech captured

# ---------------------------------------------------------------- defaults
DEFAULT_SETTINGS = {
    "theme": "light",             # light | dark | system
    "show_romaji": "1",           # romaji toggle for Japanese text
    "voice_speed": "1.0",
    "daily_goal_xp": str(DAILY_GOAL_XP),
    "notifications": "1",
    "difficulty": "normal",       # easy | normal | hard
    "username": "Learner",
    "anthropic_api_key": "",      # optional — enables the AI Sensei tutor
}
