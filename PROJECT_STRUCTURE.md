# LinguaBridge — Project Structure

Desktop-first (CustomTkinter), structured so `core/`, `database/`, `lessons/` and
`utils/` are 100% UI-agnostic — only `ui/` and `main.py` would be rewritten for a
future BeeWare/Kivy Android port.

```
LinguaBridge/
├── main.py                      # Entry point: init DB, load config, launch MainWindow
├── config.py                    # Paths, theme colors, audio/SRS/gamification constants
├── requirements.txt
│
├── assets/
│   ├── icons/                   # Streak flame, hearts, XP gem, badge art (PNG)
│   ├── images/                  # Flashcard images, mascot, backgrounds
│   ├── sounds/                  # correct.wav, wrong.wav, level_up.wav, confetti pop
│   └── fonts/                   # (optional) bundled Noto Sans JP
│
├── database/
│   ├── __init__.py
│   ├── models.py                # SQLAlchemy models: User, LessonProgress, VocabSRS,
│   │                            #   MistakeQueue, Badge, DailyStat, Settings
│   └── db_manager.py            # Engine/session setup, CRUD helpers, export/import JSON
│
├── core/                        # Pure logic — no Tkinter imports allowed here
│   ├── __init__.py
│   ├── lesson_manager.py        # Loads lessons, picks exercises, adaptive difficulty,
│   │                            #   recommends next lesson, builds mistake-review sessions
│   ├── srs.py                   # SM-2 style spaced repetition scheduler (Anki-like)
│   ├── translator.py            # deep-translator wrapper + offline phrase-table fallback
│   ├── tts_stt.py               # gTTS (online) / pyttsx3 (offline) TTS with caching;
│   │                            #   SpeechRecognition mic capture; slow/pitch playback (pydub)
│   └── scorer.py                # Answer grading: fuzzy text match (rapidfuzz),
│   │                            #   JA normalization (kana/romaji-aware), pronunciation %
│
├── ui/                          # All CustomTkinter code lives here
│   ├── __init__.py
│   ├── main_window.py           # Root CTk window, nav sidebar, screen router, theming
│   ├── home_screen.py           # Streak, XP, hearts, daily goal ring, recommended lesson
│   ├── lesson_screen.py         # Exercise flow controller: progress bar, hearts, results
│   ├── exercise_widgets.py      # One widget class per exercise type (translate, listen-
│   │                            #   type, speak, repeat, MCQ, matching, blanks, builder)
│   └── components.py            # Reusable: cards, pill buttons, confetti canvas, toasts,
│                                #   waveform view, charts panel, settings panel
│
├── lessons/
│   ├── __init__.py
│   ├── loader.py                # Validates + loads JSON lesson files into dataclasses
│   └── data/                    # One JSON per lesson (greetings.json, food.json, ...)
│
├── utils/
│   ├── __init__.py
│   ├── helpers.py               # Date/streak math, audio file mgmt, debounce, resources
│   └── japanese_utils.py        # pykakasi/jaconv/fugashi: furigana, romaji toggle,
│                                #   kana detection, answer normalization
│
├── tests/
│   ├── __init__.py
│   ├── test_srs.py
│   ├── test_scorer.py
│   └── test_japanese_utils.py
│
└── user_data/                   # Created at first run (gitignore this)
    ├── linguabridge.db          # SQLite database
    ├── tts_cache/               # Cached gTTS mp3s for offline replay
    ├── audio_recordings/        # User mic recordings for record-and-compare
    └── exports/                 # Progress export JSON files
```

## Design rules

1. **Dependency direction:** `ui` -> `core` -> (`database`, `lessons`, `utils`).
   Nothing below `ui` may import Tkinter. This is what makes the Android port a
   UI-swap rather than a rewrite.
2. **All tunables in `config.py`:** XP per exercise, hearts count, SRS intervals,
   pass thresholds, colors, font names. No magic numbers in modules.
3. **Lessons are data, not code:** new lessons = new JSON file. `loader.py`
   validates schema so a typo in JSON fails loudly at startup, not mid-lesson.
4. **TTS is cached:** every generated phrase mp3 is saved to `user_data/tts_cache/`
   keyed by hash(text+lang+speed), so repeated playback works offline and is instant.
5. **Threading:** network/audio work (gTTS, STT, translation) runs in worker
   threads; UI updates marshalled back via `widget.after()`.
