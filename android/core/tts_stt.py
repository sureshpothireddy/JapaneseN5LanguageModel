"""
core/tts_stt.py — Speech engines.

TTS  : gTTS (natural Japanese prosody, online) cached to user_data/tts_cache
       so repeated phrases play instantly and work offline afterwards.
       Falls back to pyttsx3 (offline OS voices) when there's no network.
STT  : SpeechRecognition + Google recognizer (ja-JP / en-US).
       `STTEngine.available` is False when PyAudio/mic is missing — the UI
       then offers a type-instead fallback so the app never breaks.

All playback happens on daemon threads; UI stays responsive.
"""

import threading

import config
from utils.helpers import tts_cache_path, play_sound_async

# ---------------------------------------------------------------- optional deps
try:
    from gtts import gTTS
    _GTTS_OK = True
except Exception:
    _GTTS_OK = False

try:
    import pyttsx3
    _PYTTSX3_OK = True
except Exception:
    _PYTTSX3_OK = False

try:
    import speech_recognition as sr
    _SR_OK = True
except Exception:
    _SR_OK = False


class TTSEngine:
    """Speak text in Japanese or English, with speed control and caching."""

    def __init__(self, db=None):
        self.db = db
        self._lock = threading.Lock()

    # -------------------------------------------------- public API
    def speak(self, text: str, lang: str = "ja", slow: bool = False,
              on_done=None) -> None:
        """Asynchronously synthesize + play `text`. Never raises."""
        threading.Thread(target=self._speak_blocking,
                         args=(text, lang, slow, on_done),
                         daemon=True).start()

    def speed(self) -> float:
        try:
            return float(self.db.get_setting("voice_speed", "1.0")) if self.db \
                else 1.0
        except ValueError:
            return 1.0

    # -------------------------------------------------- internals
    def _speak_blocking(self, text, lang, slow, on_done):
        try:
            slow = slow or self.speed() < 0.85
            path = tts_cache_path(text, lang, slow)
            if not path.exists() and _GTTS_OK:
                try:
                    gTTS(text=text, lang=lang, slow=slow).save(str(path))
                except Exception:
                    pass  # offline → fall through to pyttsx3
            if path.exists():
                self._play_file(path)
            elif _PYTTSX3_OK:
                self._pyttsx3_say(text, lang, slow)
        finally:
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

    def _play_file(self, path):
        # playsound3 blocks until done — that's fine, we're on a worker thread
        try:
            from playsound3 import playsound
            playsound(str(path))
        except Exception:
            play_sound_async(path)

    def _pyttsx3_say(self, text, lang, slow):
        with self._lock:                       # pyttsx3 isn't thread-safe
            try:
                engine = pyttsx3.init()
                # try to select a voice matching the language
                for v in engine.getProperty("voices"):
                    meta = f"{v.id} {getattr(v, 'name', '')}".lower()
                    if (lang.startswith("ja") and ("ja" in meta or "haruka"
                                                   in meta or "japan" in meta)) \
                       or (lang.startswith("en") and "en" in meta):
                        engine.setProperty("voice", v.id)
                        break
                rate = engine.getProperty("rate")
                engine.setProperty("rate", int(rate * (0.7 if slow else
                                                       self.speed())))
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception:
                pass


class STTEngine:
    """Capture microphone speech and transcribe via Google recognizer."""

    def __init__(self):
        self.recognizer = sr.Recognizer() if _SR_OK else None
        self._mic_ok = None

    @property
    def available(self) -> bool:
        if not _SR_OK:
            return False
        if self._mic_ok is None:
            try:
                with sr.Microphone():
                    pass
                self._mic_ok = True
            except Exception:
                self._mic_ok = False
        return self._mic_ok

    def listen_async(self, lang: str, callback) -> None:
        """
        Record one phrase and call `callback(transcript:str|None, error:str)`
        from the worker thread. The UI must marshal back with .after().
        lang: "ja-JP" or "en-US".
        """
        threading.Thread(target=self._listen_blocking,
                         args=(lang, callback), daemon=True).start()

    def _listen_blocking(self, lang, callback):
        if not self.available:
            callback(None, "Microphone not available")
            return
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self.recognizer.listen(
                    source, timeout=config.STT_TIMEOUT,
                    phrase_time_limit=config.STT_PHRASE_LIMIT)
            text = self.recognizer.recognize_google(audio, language=lang)
            callback(text, "")
        except sr.WaitTimeoutError:
            callback(None, "No speech detected — try again!")
        except sr.UnknownValueError:
            callback(None, "Couldn't understand that — speak a little "
                           "slower and clearer.")
        except sr.RequestError:
            callback(None, "Speech recognition needs an internet connection.")
        except Exception as e:                       # pragma: no cover
            callback(None, f"Recording error: {e}")
