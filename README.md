# ⛩ LinguaBridge — English ↔ Japanese

A complete beginner-to-JLPT-N5 Japanese course in a desktop app — **study
guide, teacher, and exercises in one**, built with Python + CustomTkinter.

**How the course works (designed for a total beginner):**

1. **🈁 Kana Trainer (Step 0)** — learn to *read* hiragana & katakana with a
   tappable audio chart and recognition quizzes. This is where Japanese
   actually starts.
2. **📖 Study (the teacher)** — every one of the **25 N5 lessons** opens with
   a study guide: learning objectives, concept explanations, worked example
   sentences with tap-to-hear audio, a grammar breakdown, the full vocabulary
   list with audio + romaji, and a culture note.
3. **🏋️ Practice (the exercises)** — 13 exercises per lesson across 8 types:
   translate (both directions), listen & type, multiple choice, matching,
   fill-in-the-blank, sentence building, listen & repeat (shadowing), and
   speak & translate with pronunciation scoring.
4. **🧠 Review (it sticks)** — finished lessons feed their vocabulary into an
   Anki-style SM-2 spaced-repetition deck; mistakes go to a Mistake Review
   queue. Hearts, streaks, XP, leagues and badges keep you coming back.
5. **🧑‍🏫 AI Sensei (optional)** — add your own Anthropic API key in Settings
   to unlock a live conversation tutor for free chat, grammar Q&A and
   roleplay. Everything else works fully offline without it.

**The path to N3:** this build delivers the complete N5 level (the correct
starting point — N3 assumes N5+N4 mastery). The lesson format, level field,
and progression system already support N4/N3: drop new lesson JSON files into
`lessons/data/` (or extend `lessons/n5_curriculum.py` and regenerate) and the
app picks them up automatically.

---

## 🚀 Quick start (PyCharm)

1. **Extract** this folder anywhere and open it in PyCharm
   (`File → Open → select the LinguaBridge folder`).
2. **Create a virtual environment** when PyCharm prompts you
   (Python **3.11+** required), or manually:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS / Linux:
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run**:
   ```bash
   python main.py
   ```
   (or right-click `main.py` in PyCharm → *Run*)

That's it — the database, settings and lesson vocabulary are created
automatically on first launch in the `user_data/` folder.

## 🎤 Microphone (speaking exercises)

Speech recognition needs **PyAudio**:

| OS | Command |
|---|---|
| Windows | `pip install pyaudio` (wheels ship pre-built) |
| macOS | `brew install portaudio` then `pip install pyaudio` |
| Ubuntu/Debian | `sudo apt install portaudio19-dev python3-pyaudio` then `pip install pyaudio` |

**No microphone? No problem** — speaking exercises automatically offer a
typing fallback, so every lesson can always be completed.

## 🔊 Audio notes

* **TTS** uses Google TTS (natural Japanese voice) when online and caches
  every phrase in `user_data/tts_cache/` — phrases you've heard once keep
  working offline. With no internet at all, it falls back to your OS
  voices via `pyttsx3`.
* **Sound effects** are bundled WAV files in `assets/sounds/`.
* If you hear nothing, check your system output device; the app never
  crashes on audio failures, it just stays silent.

## 🈶 Japanese fonts

For the best rendering install a CJK font if you don't have one:
**Noto Sans JP** (free, Google Fonts), or rely on the system fonts the
app auto-detects (Yu Gothic / Meiryo on Windows, Hiragino on macOS).

## 🗂 Project structure

```
LinguaBridge/
├── main.py                 # entry point
├── config.py               # every tunable: colors, XP, SRS, paths
├── database/               # SQLAlchemy models + DBManager (SQLite)
├── core/                   # pure logic: SRS, scoring, TTS/STT, sessions
├── lessons/
│   ├── loader.py           # strict JSON schema validation
│   └── data/*.json         # lesson content — add your own here!
├── ui/                     # all CustomTkinter screens & widgets
├── utils/                  # Japanese text helpers, misc utilities
├── tests/                  # unit tests (pure logic, no GUI needed)
├── assets/sounds/          # UI sound effects
└── user_data/              # created at runtime: DB, TTS cache, exports
```

**Layering rule:** `ui → core → (database, lessons, utils)`. Nothing
outside `ui/` imports Tkinter — port the app to Android (Kivy/BeeWare)
by rewriting only `ui/` and `main.py`.

## ➕ Adding your own lessons

Drop a new JSON file into `lessons/data/` following the existing files'
shape (id, title, level, difficulty, description, `vocab[]`,
`exercises[]`). It is validated at startup — any typo is reported with
the file name and reason. Vocabulary is automatically added to the
spaced-repetition deck.

## 📚 The N5 curriculum (25 lessons)

Greetings · Numbers · Food & Drink · Travel · Family · Self-Introduction ·
This & That (これ/それ/あれ) · Days & Time · Daily Verbs (ます) · Places &
Locations (あります/います) · い-Adjectives · な-Adjectives · Shopping ·
Weather & Seasons · Hobbies & Likes · Past Tense (ました) · The て-Form &
Requests · Now Happening (ています) · Wants & Wishes (〜たい) · Body & Health ·
Asking Directions · At the Restaurant · Ability (できます) · Comparing Things ·
Making Plans (〜ましょう)

Together these cover the core N5 grammar points, ~250 vocabulary items, and
all four skills (reading, listening, speaking, writing-by-typing).

## ➕ Extending to N4 / N3

Lessons are data, not code. Two ways to add content:

1. **Hand-write** a JSON file in `lessons/data/` following any existing file
   (set `"level": "N4"` etc.). It's validated at startup.
2. **Use the generator**: add entries to `lessons/n5_curriculum.py` (or copy
   it to `n4_curriculum.py`), then run `python lessons/build_curriculum.py`.
   Each entry needs only vocab, study-guide text, examples and 2–3 model
   sentences — the script builds a balanced 13-exercise set automatically.

## 🧪 Running tests

```bash
python tests/test_srs.py
python tests/test_scorer.py
python tests/test_japanese_utils.py
# or, if you have pytest:
pytest tests/
```

## 🆘 Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: customtkinter` | `pip install -r requirements.txt` inside your venv |
| Speaking exercise says "No microphone detected" | Install PyAudio (table above) and allow mic access in OS privacy settings |
| Japanese shows as boxes □□□ | Install Noto Sans JP / any CJK font |
| No TTS voice offline | First listen online once (it's then cached), or install OS Japanese voices for pyttsx3 |
| Reset all progress | Delete the `user_data/` folder (export first from Profile!) |
| `pip install pyaudio` fails on Linux | `sudo apt install portaudio19-dev` first |

## 📱 Porting to Android (later)

The codebase was structured for this: `core/`, `database/`, `lessons/`
and `utils/` are pure Python with no Tkinter imports. To port, keep them
unchanged and re-implement `ui/` with Kivy or BeeWare/Toga, swapping
gTTS/playsound for Android's native `TextToSpeech` and
`SpeechRecognizer` via `plyer`/`pyjnius`.

---

七転び八起き — *Fall seven times, rise eight.* がんばって！ 🇯🇵
