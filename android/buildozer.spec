[app]
title = LinguaBridge
package.name = linguabridge
package.domain = org.linguabridge
version = 1.0.0

source.dir = .
source.include_exts = py,json,wav,otf,ttf,png,md
source.exclude_dirs = bin,.buildozer,__pycache__,tests
source.exclude_patterns = sync_shared.py

# Pure-Python / recipe-supported dependencies only — no compiler surprises.
# (rapidfuzz/pykakasi are intentionally omitted; the app's scorer and
# romaji helpers degrade gracefully to stdlib fallbacks without them.)
requirements = python3,kivy,sqlalchemy,gtts,requests,urllib3,charset-normalizer,idna,certifi,click,plyer,jaconv

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True

# Keep the bundled Japanese font and lesson data
android.add_assets =

[buildozer]
log_level = 2
warn_on_root = 0
