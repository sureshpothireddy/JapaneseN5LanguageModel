# 📱 LinguaBridge for Android — Build Guide

The `android/` folder contains a complete Kivy edition of LinguaBridge:
same 25-lesson N5 course, study guides, kana trainer, SRS reviews,
mistakes queue, hearts/XP/streaks/badges, and Japanese TTS — with a
touch-first mobile UI and a bundled Noto Sans JP font.

An APK is a compiled Android binary: it must be **built** with the
Android SDK. You don't need to install anything for that — GitHub will
build it for you, free.

---

## ✅ Option A — One-click cloud build (recommended)

1. Create a free account at https://github.com (if you don't have one)
   and create a **new repository** (private is fine).
2. Upload this whole project folder to the repository
   (GitHub → *Add file* → *Upload files*, or use git).
   ⚠️ Make sure the hidden `.github/workflows/build-apk.yml` file is
   included — it's the build recipe.
3. Open the repo's **Actions** tab → select **Build Android APK** →
   **Run workflow**.
4. Wait ~25–40 minutes (first build downloads the Android SDK; later
   builds are faster).
5. When the run shows ✅, open it and download **LinguaBridge-APK**
   from the *Artifacts* section. Unzip it → `linguabridge-…-debug.apk`.
6. Copy the APK to your phone and tap it to install. Android will ask
   you to allow "install from unknown sources" — that's normal for any
   app not from the Play Store.

## 🐧 Option B — Build locally (Linux or Windows-WSL)

Buildozer only runs on Linux. On Windows, install WSL Ubuntu first
(`wsl --install` in PowerShell), then inside Ubuntu:

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses-dev \
    cmake libffi-dev libssl-dev
pip3 install --user buildozer cython==0.29.36

cd LinguaBridge
python3 android/sync_shared.py     # copy engine into android/
cd android
buildozer android debug            # first run: big SDK/NDK download
# APK appears in android/bin/
```

Install on your phone:
```bash
buildozer android deploy run       # phone connected with USB debugging
# or just copy android/bin/*.apk to the phone manually
```

## 📋 What's in the Android edition

| Feature | Status |
|---|---|
| 25 N5 lessons with study guides, examples, grammar & culture notes | ✅ identical content to desktop |
| Kana trainer (chart + quiz, both scripts) | ✅ |
| All 8 exercise types | ✅ (speaking exercises use a *say-it-aloud-then-type-it* flow — see below) |
| Japanese TTS with offline caching | ✅ gTTS online → cached; phone's native voice offline (plyer) |
| SM-2 spaced repetition + mistake review | ✅ same engine, same database schema |
| Hearts, XP, streaks, leagues, badges, daily goal | ✅ |
| Romaji toggle, difficulty, daily goal settings | ✅ |
| Bundled Japanese font (Noto Sans JP) | ✅ no tofu boxes |
| Microphone pronunciation scoring | ➖ not in v1: Android speech-to-text needs per-device permission plumbing; speaking exercises instead prompt you to say the sentence aloud and then type it (kana **or romaji** accepted), so every lesson is fully completable. The desktop app retains full mic scoring. |
| AI Sensei chat | ➖ desktop-only for now (easy to add later — the `core/sensei.py` engine is already packaged) |

## 🆘 Build troubleshooting

| Problem | Fix |
|---|---|
| Actions tab shows no workflow | The `.github/` folder wasn't uploaded — it's hidden; upload it explicitly |
| Build fails on a dependency | Re-run the workflow once (network hiccups happen); the recipe uses only pure-Python deps known to work with python-for-android |
| APK installs but crashes on open | Connect the phone via USB and run `adb logcat | grep -i python` to see the error; 99% of cases are a missing file — re-run `python3 android/sync_shared.py` and rebuild |
| Japanese shows as boxes | Shouldn't happen (font is bundled), but if so the font failed to copy — confirm `android/assets/fonts/NotoSansJP-Regular.otf` exists before building |
| No sound | First playback of each phrase needs internet (gTTS); afterwards it's cached. Offline, the phone's native Japanese voice is used if installed (Settings → Accessibility → Text-to-speech) |

## ⚠️ Honest status

The Android **engine** (lessons, SRS, scoring, database, session flow) is
the same code as the desktop app and passes the same automated tests.
The Kivy **UI** compiles cleanly and follows standard Kivy patterns, but
it has not been run on a physical device by the author of this codebase —
your first build is its first device test. If anything misbehaves, the
fix is almost always small; check `adb logcat` and the table above.
