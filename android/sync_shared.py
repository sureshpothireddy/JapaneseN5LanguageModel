"""
sync_shared.py — Copy the shared (non-Tkinter) modules from the desktop
project into android/ so buildozer can package a self-contained app.

Run from the project root OR from android/:
    python android/sync_shared.py

Copied:  config.py, core/, database/, utils/, lessons/ (loader + data +
kana.json + curriculum), assets/sounds.  The desktop ui/ folder is NOT
copied — the Android UI lives in android/main.py (Kivy).
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../android
ROOT = HERE.parent                              # project root

SHARED_DIRS = ["core", "database", "utils", "lessons"]
SHARED_FILES = ["config.py"]
ASSET_DIRS = [("assets/sounds", "assets/sounds")]


def main():
    for d in SHARED_DIRS:
        src, dst = ROOT / d, HERE / d
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst,
                        ignore=shutil.ignore_patterns("__pycache__",
                                                      "*.pyc"))
        print(f"  ✓ {d}/")
    for f in SHARED_FILES:
        shutil.copy2(ROOT / f, HERE / f)
        print(f"  ✓ {f}")
    for src_rel, dst_rel in ASSET_DIRS:
        src, dst = ROOT / src_rel, HERE / dst_rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  ✓ {src_rel}")
    print("Shared code synced into android/.")


if __name__ == "__main__":
    sys.exit(main())
