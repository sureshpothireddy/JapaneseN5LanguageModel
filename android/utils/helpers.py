"""
utils/helpers.py — Small shared utilities (no Tkinter imports except
the font probe, which is only called after the root window exists).
"""

import hashlib
import random
import threading

import config

# ---------------------------------------------------------------- audio
try:
    from playsound3 import playsound as _playsound
    _SOUND_OK = True
except Exception:                                    # pragma: no cover
    _SOUND_OK = False


def play_sound_async(path) -> None:
    """Fire-and-forget playback of a local audio file (never raises)."""
    if not _SOUND_OK:
        return
    p = str(path)

    def _run():
        try:
            _playsound(p)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def play_effect(name: str) -> None:
    """Play a named UI sound effect from assets/sounds (correct/wrong/level_up)."""
    path = config.SOUNDS_DIR / f"{name}.wav"
    if path.exists():
        play_sound_async(path)


# ---------------------------------------------------------------- misc
def tts_cache_path(text: str, lang: str, slow: bool):
    key = hashlib.md5(f"{lang}|{int(slow)}|{text}".encode("utf-8")).hexdigest()
    return config.TTS_CACHE_DIR / f"{key}.mp3"


def run_in_thread(fn, *args, **kwargs) -> threading.Thread:
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


def random_encouragement(correct: bool) -> str:
    pool = (config.ENCOURAGEMENTS_CORRECT if correct
            else config.ENCOURAGEMENTS_WRONG)
    return random.choice(pool)


# ---------------------------------------------------------------- fonts
_font_cache = {}


def pick_font(japanese: bool = False) -> str:
    """Pick the first installed font from the configured preference lists.
    Must be called after a Tk root exists."""
    key = "ja" if japanese else "ui"
    if key in _font_cache:
        return _font_cache[key]
    try:
        from tkinter import font as tkfont
        installed = set(tkfont.families())
        prefs = config.JAPANESE_FONTS if japanese else config.UI_FONTS
        for f in prefs:
            if f in installed:
                _font_cache[key] = f
                return f
    except Exception:
        pass
    _font_cache[key] = "TkDefaultFont"
    return _font_cache[key]
