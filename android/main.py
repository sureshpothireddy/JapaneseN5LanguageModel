"""
LinguaBridge for Android — Kivy edition.

Reuses the exact same core engine as the desktop app (lessons, SM-2 SRS,
fuzzy scorer, SQLite database, gamification) with a touch-first Kivy UI.

Differences from desktop, by design:
  * Speaking exercises use a type-what-you'd-say fallback (Android STT
    needs per-device permissions; typing keeps every lesson completable).
  * TTS: gTTS (cached mp3 via SoundLoader) when online, falling back to
    the phone's native voice through plyer.tts offline.

Entry point must be named main.py for python-for-android/buildozer.
"""

import os
import sys
import threading
from pathlib import Path

# --------------------------------------------------------------- paths
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.audio import SoundLoader
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as hexc

import config

# Redirect all user data to the app's private writable directory ----------
def _redirect_user_data(app_dir: str):
    base = Path(app_dir)
    config.USER_DATA_DIR = base / "user_data"
    config.DB_PATH = config.USER_DATA_DIR / "linguabridge.db"
    config.TTS_CACHE_DIR = config.USER_DATA_DIR / "tts_cache"
    config.RECORDINGS_DIR = config.USER_DATA_DIR / "audio_recordings"
    config.EXPORTS_DIR = config.USER_DATA_DIR / "exports"
    for d in (config.USER_DATA_DIR, config.TTS_CACHE_DIR,
              config.RECORDINGS_DIR, config.EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------- fonts
def register_fonts():
    """Bundle Noto Sans JP; fall back to Android system CJK fonts."""
    candidates = [
        HERE / "assets" / "fonts" / "NotoSansJP-Regular.otf",
        Path("/system/fonts/NotoSansCJK-Regular.ttc"),
        Path("/system/fonts/NotoSansJP-Regular.otf"),
    ]
    for p in candidates:
        if p.exists():
            try:
                LabelBase.register(name="JP", fn_regular=str(p))
                return
            except Exception:
                continue
    LabelBase.register(name="JP",
                       fn_regular=LabelBase._fonts["Roboto"][0])  # last resort


# --------------------------------------------------------------- theme
C = {k: hexc(v) for k, v in config.COLORS.items()}
BG = hexc("#F6F4EF")
CARD = hexc("#FFFFFF")
TXT = hexc("#222222")
MUT = hexc("#8A8A8E")


def vlabel(text, size=16, bold=False, color=TXT, halign="left", **kw):
    lbl = Label(text=text, font_name="JP", font_size=sp(size), bold=bold,
                color=color, halign=halign, valign="middle",
                size_hint_y=None, markup=True, **kw)
    lbl.bind(width=lambda l, w: setattr(l, "text_size", (w, None)))
    lbl.bind(texture_size=lambda l, ts: setattr(l, "height",
                                                ts[1] + dp(4)))
    return lbl


class CardBox(BoxLayout):
    """White rounded card."""

    def __init__(self, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding", dp(14))
        kw.setdefault("spacing", dp(6))
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self.bind(minimum_height=self.setter("height"))
        from kivy.graphics import Color, RoundedRectangle
        with self.canvas.before:
            Color(*CARD)
            self._rect = RoundedRectangle(radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


class PillButton(Button):
    def __init__(self, bg=None, fg=(1, 1, 1, 1), **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(52))
        kw.setdefault("font_name", "JP")
        kw.setdefault("font_size", sp(16))
        kw.setdefault("bold", True)
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = fg
        self._bg = bg or C["primary"]
        from kivy.graphics import Color, RoundedRectangle
        with self.canvas.before:
            self._col = Color(*self._bg)
            self._rect = RoundedRectangle(radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync, state=self._press)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _press(self, *a):
        r, g, b, _ = self._bg
        f = 0.85 if self.state == "down" else 1.0
        self._col.rgba = (r * f, g * f, b * f, 1)

    def set_bg(self, rgba):
        self._bg = rgba
        self._col.rgba = rgba


class OptionButton(PillButton):
    """White bordered option for quizzes."""

    def __init__(self, **kw):
        super().__init__(bg=CARD, fg=TXT, **kw)
        from kivy.graphics import Color, Line
        with self.canvas.after:
            self._line_col = Color(*hexc("#E0DDD5"))
            self._line = Line(width=dp(1.2))
        self.bind(pos=self._sync_line, size=self._sync_line)

    def _sync_line(self, *a):
        self._line.rounded_rectangle = (self.x, self.y, self.width,
                                        self.height, dp(14))

    def mark(self, kind):
        if kind == "selected":
            self._line_col.rgba = C["primary"]
        elif kind == "correct":
            self.set_bg(hexc("#D7FFB8"))
            self.color = C["success"]
            self._line_col.rgba = C["success"]
        elif kind == "wrong":
            self.set_bg(hexc("#FFDFE0"))
            self.color = C["error"]
            self._line_col.rgba = C["error"]
        else:
            self._line_col.rgba = hexc("#E0DDD5")


class JPTextInput(TextInput):
    def __init__(self, **kw):
        kw.setdefault("font_name", "JP")
        kw.setdefault("font_size", sp(18))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(52))
        kw.setdefault("multiline", False)
        kw.setdefault("padding", [dp(12), dp(14)])
        super().__init__(**kw)


def scroll_body():
    sv = ScrollView(do_scroll_x=False, bar_width=dp(3))
    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10),
                    size_hint_y=None)
    box.bind(minimum_height=box.setter("height"))
    sv.add_widget(box)
    return sv, box


# --------------------------------------------------------------- mobile TTS
class MobileTTS:
    """gTTS+SoundLoader online (cached), plyer native TTS offline."""

    def __init__(self, db=None):
        self.db = db
        self._current = None

    def speak(self, text, lang="ja", slow=False, on_done=None):
        threading.Thread(target=self._work, args=(text, lang, slow),
                         daemon=True).start()

    def _work(self, text, lang, slow):
        from utils.helpers import tts_cache_path
        path = tts_cache_path(text, lang, slow)
        if not path.exists():
            try:
                from gtts import gTTS
                gTTS(text=text, lang=lang, slow=slow).save(str(path))
            except Exception:
                path = None
        if path and path.exists():
            self._play(str(path))
        else:
            try:
                from plyer import tts as native_tts
                native_tts.speak(text)
            except Exception:
                pass

    @mainthread
    def _play(self, path):
        try:
            if self._current:
                self._current.stop()
            snd = SoundLoader.load(path)
            if snd:
                self._current = snd
                snd.play()
        except Exception:
            pass


def play_effect(name):
    p = HERE / "assets" / "sounds" / f"{name}.wav"
    if p.exists():
        try:
            snd = SoundLoader.load(str(p))
            if snd:
                snd.play()
        except Exception:
            pass


# =================================================================
# Exercise widgets — same contract as desktop: check() -> GradeResult
# =================================================================
from core import scorer
from utils import japanese_utils as ju

PUNCT_TOKENS = {"、", "。", "！", "？"}


class ExBase(BoxLayout):
    def __init__(self, exercise, app, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("spacing", dp(10))
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self.bind(minimum_height=self.setter("height"))
        self.exercise = exercise
        self.app = app
        self.on_ready = lambda ok: None

    def ready(self, ok=True):
        self.on_ready(ok)

    def show_romaji(self):
        return self.app.db.get_setting("show_romaji", "1") == "1"

    def instruction(self, text):
        self.add_widget(vlabel(text, 13, bold=True, color=MUT))

    def prompt(self, text, japanese=False):
        self.add_widget(vlabel(text, 24, bold=True))
        if japanese and self.show_romaji() and ju.contains_japanese(text):
            self.add_widget(vlabel(ju.to_romaji(text), 12, color=MUT))

    def audio_row(self, text, lang):
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        b1 = PillButton(text="🔊 Play", size_hint_x=None, width=dp(120),
                        height=dp(48))
        b1.bind(on_release=lambda *a: self.app.tts.speak(text, lang))
        b2 = PillButton(text="🐢 Slow", size_hint_x=None, width=dp(110),
                        height=dp(48), bg=C["matcha"])
        b2.bind(on_release=lambda *a: self.app.tts.speak(text, lang,
                                                         slow=True))
        row.add_widget(b1)
        row.add_widget(b2)
        row.add_widget(Widget())
        self.add_widget(row)

    def text_entry(self, hint):
        self.entry = JPTextInput(hint_text=hint)
        self.entry.bind(text=lambda i, t: self.ready(bool(t.strip())))
        self.add_widget(self.entry)
        return self.entry

    def hint_row(self, hint):
        if hint:
            self.add_widget(vlabel(f"💡 {hint}", 12, color=MUT))

    def user_answer_text(self):
        return getattr(self, "entry", None) and self.entry.text or ""


class TranslateEx(ExBase):
    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        en_ja = exercise["direction"] == "en_ja"
        self.lang = "ja" if en_ja else "en"
        self.instruction("Translate into " + ("Japanese" if en_ja
                                              else "English"))
        self.prompt(exercise["text"], japanese=not en_ja)
        if not en_ja:
            self.audio_row(exercise["text"], "ja")
        self.text_entry("Type in Japanese (kana or romaji)…" if en_ja
                        else "Type in English…")
        self.hint_row(exercise.get("hint", ""))

    def check(self):
        answers = list(self.exercise["answers"])
        if self.lang == "ja":
            answers += [ju.to_romaji(a) for a in self.exercise["answers"]]
        return scorer.grade_text(self.entry.text, answers, self.lang)


class ListenTypeEx(ExBase):
    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        self.instruction("Listen, then type what you hear")
        self.add_widget(vlabel("👂", 40))
        self.audio_row(exercise["audio_text"], exercise.get("lang", "ja"))
        self.text_entry("Type what you heard…")
        self.hint_row(exercise.get("hint", ""))
        Clock.schedule_once(lambda dt: self.app.tts.speak(
            exercise["audio_text"], exercise.get("lang", "ja")), 0.4)

    def check(self):
        return scorer.grade_text(self.entry.text, self.exercise["answers"],
                                 self.exercise.get("lang", "ja"))


class MCQEx(ExBase):
    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        self.instruction("Choose the correct answer")
        self.prompt(exercise["question"],
                    japanese=ju.contains_japanese(exercise["question"]))
        if exercise.get("tts"):
            self.audio_row(exercise["tts"], exercise.get("tts_lang", "ja"))
        self.selected = ""
        self.btns = []
        for opt in exercise["options"]:
            b = OptionButton(text=opt)
            b.bind(on_release=lambda btn, o=opt: self._pick(btn, o))
            self.btns.append(b)
            self.add_widget(b)

    def _pick(self, btn, opt):
        self.selected = opt
        for b in self.btns:
            b.mark("selected" if b is btn else "none")
        if ju.contains_japanese(opt):
            self.app.tts.speak(opt, "ja")
        self.ready(True)

    def check(self):
        return scorer.grade_exact_choice(self.selected,
                                         self.exercise["answer"])

    def user_answer_text(self):
        return self.selected


class MatchingEx(ExBase):
    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        import random
        self.instruction(exercise.get("title", "Match the pairs"))
        self.pairs = {a: b for a, b in exercise["pairs"]}
        self.remaining = len(self.pairs)
        self.wrong = 0
        self.left_sel = None
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        lefts = list(self.pairs.keys())
        rights = list(self.pairs.values())
        random.shuffle(lefts)
        random.shuffle(rights)
        self.lbtn, self.rbtn = {}, {}
        for i in range(len(lefts)):
            lb = OptionButton(text=lefts[i], height=dp(50))
            lb.bind(on_release=lambda b, t=lefts[i]: self._left(b, t))
            rb = OptionButton(text=rights[i], height=dp(50))
            rb.bind(on_release=lambda b, t=rights[i]: self._right(b, t))
            self.lbtn[lefts[i]] = lb
            self.rbtn[rights[i]] = rb
            grid.add_widget(lb)
            grid.add_widget(rb)
        self.add_widget(grid)

    def _left(self, btn, text):
        if btn.disabled:
            return
        self.left_sel = text
        for t, b in self.lbtn.items():
            if not b.disabled:
                b.mark("selected" if t == text else "none")
        if ju.contains_japanese(text):
            self.app.tts.speak(text, "ja")

    def _right(self, btn, text):
        if btn.disabled or not self.left_sel:
            return
        if self.pairs.get(self.left_sel) == text:
            for b in (self.lbtn[self.left_sel], btn):
                b.mark("correct")
                b.disabled = True
            self.left_sel = None
            self.remaining -= 1
            if self.remaining == 0:
                self.ready(True)
        else:
            self.wrong += 1
            btn.mark("wrong")
            Clock.schedule_once(lambda dt: btn.mark("none"), 0.5)

    def check(self):
        ok = self.wrong <= 1
        fb = "" if ok else (f"All matched, but {self.wrong} wrong taps — "
                            "let's review these words.")
        return scorer.GradeResult(ok, 100.0 if ok else 60.0, "", fb)

    def user_answer_text(self):
        return f"{self.wrong} wrong taps"


class FillBlankEx(ExBase):
    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        self.instruction("Fill in the blank")
        self.selected = ""
        self.sentence_lbl = vlabel(exercise["sentence"], 24, bold=True)
        self.add_widget(self.sentence_lbl)
        if exercise.get("translation"):
            self.add_widget(vlabel(exercise["translation"], 12, color=MUT))
        self.btns = []
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for opt in exercise["options"]:
            b = OptionButton(text=opt, height=dp(50))
            b.bind(on_release=lambda btn, o=opt: self._pick(btn, o))
            self.btns.append(b)
            grid.add_widget(b)
        self.add_widget(grid)

    def _pick(self, btn, opt):
        self.selected = opt
        self.sentence_lbl.text = self.exercise["sentence"].replace("___",
                                                                   opt, 1)
        for b in self.btns:
            b.mark("selected" if b is btn else "none")
        self.ready(True)

    def check(self):
        return scorer.grade_exact_choice(self.selected,
                                         self.exercise["answer"])

    def user_answer_text(self):
        return self.selected


class SentenceBuildEx(ExBase):
    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        import random
        self.instruction("Build the sentence in Japanese")
        self.prompt(exercise["translation"])
        self.chosen = []
        self.answer_lbl = vlabel("﹏" * 12, 22, bold=True,
                                 color=C["primary"])
        self.add_widget(self.answer_lbl)
        undo = PillButton(text="⌫ Undo", height=dp(40), bg=C["accent"],
                          size_hint_x=None, width=dp(110))
        undo.bind(on_release=lambda *a: self._undo())
        self.add_widget(undo)
        tokens = [t for t in (list(exercise["tokens"])
                              + list(exercise.get("distractors", [])))
                  if t not in PUNCT_TOKENS]
        random.shuffle(tokens)
        grid = GridLayout(cols=3, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        self.tiles = []
        for tok in tokens:
            b = OptionButton(text=tok, height=dp(48))
            b.bind(on_release=lambda btn, t=tok: self._take(btn, t))
            self.tiles.append(b)
            grid.add_widget(b)
        self.add_widget(grid)

    def _take(self, btn, tok):
        if btn.disabled:
            return
        btn.disabled = True
        self.chosen.append((tok, btn))
        if ju.contains_japanese(tok):
            self.app.tts.speak(tok, "ja")
        self._refresh()

    def _undo(self):
        if self.chosen:
            tok, btn = self.chosen.pop()
            btn.disabled = False
            self._refresh()

    def _refresh(self):
        s = "".join(t for t, _ in self.chosen)
        self.answer_lbl.text = s if s else "﹏" * 12
        self.ready(bool(self.chosen))

    def check(self):
        built = "".join(t for t, _ in self.chosen)
        return scorer.grade_text(built, [self.exercise["answer"]], "ja",
                                 threshold=92)

    def user_answer_text(self):
        return "".join(t for t, _ in self.chosen)


class SpeakFallbackEx(ExBase):
    """speak_translate / listen_repeat on mobile: produce the sentence by
    typing (kana or romaji). Audio support included for shadowing."""

    def __init__(self, exercise, app, **kw):
        super().__init__(exercise, app, **kw)
        if exercise["type"] == "speak_translate":
            self.target = exercise["target"]
            self.accept = list(exercise["accept"])
            self.instruction("Say it out loud, then type it in Japanese")
            self.prompt(exercise["text"])
            if exercise.get("romaji") and self.show_romaji():
                self.add_widget(vlabel(f"({exercise['romaji']})", 12,
                                       color=MUT))
            listen = PillButton(text="🔊 Hear the answer", height=dp(44),
                                bg=C["matcha"])
            listen.bind(on_release=lambda *a: self.app.tts.speak(
                self.target, "ja"))
            self.add_widget(listen)
        else:                                   # listen_repeat
            self.target = exercise["audio_text"]
            self.accept = [self.target]
            self.instruction("Listen, repeat OUT LOUD, then type it")
            if exercise.get("meaning"):
                self.add_widget(vlabel(f"“{exercise['meaning']}”", 13,
                                       color=MUT))
            self.prompt(self.target, japanese=True)
            self.audio_row(self.target, exercise.get("lang", "ja"))
            Clock.schedule_once(lambda dt: self.app.tts.speak(
                self.target, exercise.get("lang", "ja")), 0.4)
        self.accept += [ju.to_romaji(a) for a in self.accept]
        self.text_entry("Type the Japanese here…")

    def check(self):
        return scorer.grade_text(self.entry.text, self.accept, "ja")


EX_WIDGETS = {
    "translate": TranslateEx,
    "listen_type": ListenTypeEx,
    "multiple_choice": MCQEx,
    "matching": MatchingEx,
    "fill_blank": FillBlankEx,
    "sentence_build": SentenceBuildEx,
    "speak_translate": SpeakFallbackEx,
    "listen_repeat": SpeakFallbackEx,
}


# =================================================================
# Screens
# =================================================================
class TopBar(BoxLayout):
    def __init__(self, app, title="", back_to=None, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(54))
        kw.setdefault("padding", [dp(8), dp(4)])
        super().__init__(**kw)
        if back_to:
            b = PillButton(text="←", size_hint_x=None, width=dp(54),
                           height=dp(44), bg=hexc("#E8E5DD"), fg=TXT)
            b.bind(on_release=lambda *a: app.goto(back_to))
            self.add_widget(b)
        t = vlabel(title, 18, bold=True)
        t.size_hint_y = 1
        self.add_widget(t)


class HomeScreen(Screen):
    def on_pre_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        root = BoxLayout(orientation="vertical")
        sv, box = scroll_body()

        user = app.db.get_user()
        name = app.db.get_setting("username", "Learner")
        box.add_widget(vlabel(f"こんにちは, {name}!", 24, bold=True))
        stats = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(12))
        for icon, val, col in (("🔥", user.streak, C["streak"]),
                               ("⚡", user.total_xp, C["xp"]),
                               ("❤", user.hearts, C["heart"])):
            lab = Label(text=f"{icon} {val}", font_name="JP",
                        font_size=sp(16), bold=True, color=col)
            stats.add_widget(lab)
        box.add_widget(stats)

        # daily goal
        try:
            goal = int(app.db.get_setting("daily_goal_xp", "50"))
        except ValueError:
            goal = 50
        xp_today = app.db.xp_today()
        card = CardBox()
        card.add_widget(vlabel(f"Daily goal — {xp_today}/{goal} XP",
                               14, bold=True))
        pb = ProgressBar(max=goal, value=min(xp_today, goal),
                         size_hint_y=None, height=dp(16))
        card.add_widget(pb)
        box.add_widget(card)

        # reviews
        due = app.db.due_vocab_count()
        mistakes = len(app.db.pending_mistakes())
        rv = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        b1 = PillButton(text=f"🧠 Review ({due})", bg=C["matcha"],
                        disabled=not due)
        b1.bind(on_release=lambda *a: app.start_srs())
        b2 = PillButton(text=f"📝 Mistakes ({mistakes})", bg=C["accent"],
                        disabled=not mistakes)
        b2.bind(on_release=lambda *a: app.start_mistakes())
        rv.add_widget(b1)
        rv.add_widget(b2)
        box.add_widget(rv)

        # kana entry
        kana_btn = PillButton(text="🈁  Kana Trainer — start here!",
                              bg=C["accent"])
        kana_btn.bind(on_release=lambda *a: app.goto("kana"))
        box.add_widget(kana_btn)

        done = sum(1 for _, i in app.lessons.lessons_with_progress()
                   if i["completed"])
        box.add_widget(vlabel(
            f"Your N5 path 🗾  ({done}/{len(app.lessons.lessons)} lessons)",
            18, bold=True))

        for lesson, info in app.lessons.lessons_with_progress():
            box.add_widget(self._lesson_card(app, lesson, info))

        sb = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6),
                       padding=[dp(8), dp(4)])
        for label, target in (("🏠", "home"), ("🈁", "kana"),
                              ("👤", "profile"), ("⚙", "settings")):
            b = PillButton(text=label, bg=hexc("#E8E5DD"), fg=TXT,
                           height=dp(48))
            b.bind(on_release=lambda btn, t=target: app.goto(t))
            sb.add_widget(b)
        root.add_widget(sv)
        root.add_widget(sb)
        self.add_widget(root)

    def _lesson_card(self, app, lesson, info):
        card = CardBox()
        head = f"{lesson.icon if info['unlocked'] else '🔒'}  " \
               f"{lesson.title}  ·  {lesson.level}"
        card.add_widget(vlabel(head, 16, bold=True,
                               color=TXT if info["unlocked"] else MUT))
        sub = lesson.description
        if info["completed"]:
            sub = f"✅ Best {info['best']:.0f}%  ·  {sub}"
        card.add_widget(vlabel(sub, 12, color=MUT))
        if info["unlocked"]:
            b = PillButton(text="PRACTICE" if info["completed"] else "STUDY",
                           height=dp(44),
                           bg=C["matcha"] if info["completed"]
                           else C["primary"])
            b.bind(on_release=lambda btn, l=lesson: app.open_study(l))
            card.add_widget(b)
        else:
            card.add_widget(vlabel("Complete the previous lesson to unlock",
                                   11, color=MUT))
        return card


class StudyScreen(Screen):
    lesson = None

    def on_pre_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        lesson = self.lesson
        root = BoxLayout(orientation="vertical")
        root.add_widget(TopBar(app, f"{lesson.icon} {lesson.title}",
                               back_to="home"))
        sv, box = scroll_body()

        box.add_widget(vlabel(lesson.description, 13, color=MUT))
        if lesson.objectives:
            card = CardBox()
            card.add_widget(vlabel("🎯 You'll learn to", 14, bold=True))
            for o in lesson.objectives:
                card.add_widget(vlabel(f"• {o}", 13))
            box.add_widget(card)

        if lesson.study_guide:
            box.add_widget(vlabel("📖 Study guide", 17, bold=True))
            for sec in lesson.study_guide:
                card = CardBox()
                card.add_widget(vlabel(sec.get("heading", ""), 15,
                                       bold=True))
                card.add_widget(vlabel(sec.get("body", ""), 13))
                box.add_widget(card)

        if lesson.examples:
            box.add_widget(vlabel("💬 Examples — tap to listen", 17,
                                  bold=True))
            for ex in lesson.examples:
                card = CardBox()
                b = PillButton(text=f"🔊  {ex.get('ja', '')}",
                               height=dp(46), bg=C["primary"])
                b.bind(on_release=lambda btn, t=ex.get("ja", ""):
                       app.tts.speak(t, "ja"))
                card.add_widget(b)
                sub = ex.get("en", "")
                if ex.get("romaji"):
                    sub = f"{ex['romaji']}  ·  {sub}"
                card.add_widget(vlabel(sub, 12, color=MUT))
                box.add_widget(card)

        gn = lesson.grammar_note
        if gn:
            card = CardBox()
            card.add_widget(vlabel(f"🔧 {gn.get('title', '')}", 15,
                                   bold=True))
            card.add_widget(vlabel(gn.get("body", ""), 13))
            box.add_widget(card)

        box.add_widget(vlabel("🗂 Vocabulary", 17, bold=True))
        vcard = CardBox()
        for v in lesson.vocab:
            reading = v.get("reading", v["ja"])
            head = v["ja"]
            if v.get("reading") and v["reading"] != v["ja"]:
                head = f"{v['ja']} （{v['reading']}）"
            b = PillButton(text=f"🔊  {head}", height=dp(44),
                           bg=hexc("#EFEDE6"), fg=TXT)
            b.bind(on_release=lambda btn, t=reading: app.tts.speak(t, "ja"))
            vcard.add_widget(b)
            sub = v["en"]
            if v.get("romaji"):
                sub = f"{v['romaji']}  ·  {sub}"
            vcard.add_widget(vlabel(sub, 12, color=MUT))
        box.add_widget(vcard)

        if lesson.culture_note:
            card = CardBox()
            card.add_widget(vlabel("🏮 Culture note", 15, bold=True))
            card.add_widget(vlabel(lesson.culture_note, 13))
            box.add_widget(card)

        start = PillButton(text="START PRACTICE ▶", bg=C["success"])
        start.bind(on_release=lambda *a: app.start_lesson(lesson))
        box.add_widget(start)
        root.add_widget(sv)
        self.add_widget(root)


class LessonScreen(Screen):
    session = None

    def on_pre_enter(self):
        self.app = App.get_running_app()
        self.checked = False
        self._build()

    def _build(self):
        self.clear_widgets()
        self.root_box = BoxLayout(orientation="vertical")
        top = BoxLayout(size_hint_y=None, height=dp(54),
                        padding=[dp(8), dp(6)], spacing=dp(8))
        quit_btn = PillButton(text="✕", size_hint_x=None, width=dp(50),
                              height=dp(42), bg=hexc("#E8E5DD"), fg=TXT)
        quit_btn.bind(on_release=lambda *a: self.app.goto("home"))
        self.pb = ProgressBar(max=1, value=0)
        self.hearts_lbl = Label(text="", font_name="JP", font_size=sp(15),
                                color=C["heart"], size_hint_x=None,
                                width=dp(110))
        top.add_widget(quit_btn)
        top.add_widget(self.pb)
        top.add_widget(self.hearts_lbl)
        self.root_box.add_widget(top)

        self.sv, self.body = scroll_body()
        self.root_box.add_widget(self.sv)

        self.feedback = vlabel("", 14, bold=True)
        self.feedback.padding = [dp(14), dp(6)]
        self.root_box.add_widget(self.feedback)

        self.action = PillButton(text="CHECK", bg=C["success"],
                                 disabled=True)
        self._handler = self._on_action
        self.action.bind(on_release=lambda *a: self._handler())
        wrap = BoxLayout(size_hint_y=None, height=dp(68),
                         padding=[dp(14), dp(8)])
        wrap.add_widget(self.action)
        self.root_box.add_widget(wrap)
        self.add_widget(self.root_box)
        self._show_exercise()

    def _hearts(self):
        if self.session.kind != "lesson":
            self.hearts_lbl.text = "📚 review"
            return
        h = self.app.db.get_user().hearts
        self.hearts_lbl.text = "❤" * h + "♡" * (config.MAX_HEARTS - h)

    def _show_exercise(self):
        self.body.clear_widgets()
        self.feedback.text = ""
        self.checked = False
        self._hearts()
        ex = self.session.current
        if ex is None:
            self._results()
            return
        self.pb.value = self.session.index / max(1, self.session.total)
        self.widget = EX_WIDGETS[ex["type"]](ex, self.app)
        self.widget.on_ready = lambda ok: setattr(self.action, "disabled",
                                                  not ok)
        self.action.disabled = True
        self.action.text = "CHECK"
        self.action.set_bg(C["success"])
        self.body.add_widget(self.widget)

    def _on_action(self):
        if not self.checked:
            self._check()
        else:
            self.session.advance()
            self._show_exercise()

    def _check(self):
        ex = self.session.current
        result = self.widget.check()
        self.checked = True
        self.app.lessons.record_answer(self.session, ex, result.correct,
                                       self.widget.user_answer_text(),
                                       result.similarity)
        self._hearts()
        from utils.helpers import random_encouragement
        head = random_encouragement(result.correct)
        detail = result.feedback
        if not result.correct and result.best_answer:
            detail = detail or f"Answer: {result.best_answer}"
            if ju.contains_japanese(result.best_answer):
                ro = ju.to_romaji(result.best_answer)
                if ro and ro != result.best_answer:
                    detail += f" ({ro})"
                self.app.tts.speak(result.best_answer, "ja")
        self.feedback.text = ("[color=58A700]✅ " if result.correct
                              else "[color=EA2B2B]✖ ") + head + \
            (("\n" + detail) if detail else "") + "[/color]"
        play_effect("correct" if result.correct else "wrong")
        if (self.session.kind == "lesson"
                and self.app.db.get_user().hearts <= 0):
            self.action.text = "OUT OF HEARTS — RESULTS"
            self.action.set_bg(C["heart"])
            self._handler = self._results
            return
        self.action.text = "CONTINUE"
        self.action.set_bg(C["primary"])

    def _results(self):
        self.body.clear_widgets()
        self.feedback.text = ""
        res = self.app.lessons.finish_session(self.session)
        play_effect("level_up")
        title = ("Perfect! 完璧！" if res["perfect"] else
                 "Lesson complete! お疲れさま！"
                 if self.session.kind == "lesson"
                 else "Review complete! よくできました！")
        self.body.add_widget(vlabel("🎉 " + title, 24, bold=True,
                                    halign="center"))
        card = CardBox()
        card.add_widget(vlabel(f"⚡ +{res['xp']} XP    "
                               f"🎯 {res['score']:.0f}%    "
                               f"🔥 {res['streak']} days", 16, bold=True,
                               halign="center"))
        self.body.add_widget(card)
        for icon, name, desc in res["new_badges"]:
            self.body.add_widget(vlabel(f"{icon} New badge: {name} — {desc}",
                                        13, color=C["gold"]))
        if self.session.kind == "lesson" and res["wrong"]:
            self.body.add_widget(vlabel(
                f"{res['wrong']} tricky one(s) added to Mistake Review.",
                12, color=MUT))
        self.action.text = "CONTINUE"
        self.action.set_bg(C["primary"])
        self.action.disabled = False
        self._handler = lambda: self.app.goto("home")


class KanaScreen(Screen):
    script = "hiragana"

    def on_pre_enter(self):
        self._chart()

    def _chart(self):
        self.clear_widgets()
        app = App.get_running_app()
        from core import kana as kana_core
        data = kana_core.load_kana()
        root = BoxLayout(orientation="vertical")
        root.add_widget(TopBar(app, "🈁 Kana Trainer", back_to="home"))
        sv, box = scroll_body()

        switch = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for s in ("hiragana", "katakana"):
            b = PillButton(text=s, bg=C["primary"] if s == self.script
                           else hexc("#E8E5DD"),
                           fg=(1, 1, 1, 1) if s == self.script else TXT)
            b.bind(on_release=lambda btn, sc=s: self._switch(sc))
            switch.add_widget(b)
        box.add_widget(switch)

        quiz = PillButton(text=f"▶ Quiz me on {self.script}",
                          bg=C["success"])
        quiz.bind(on_release=lambda *a: self._start_quiz())
        box.add_widget(quiz)

        for group in data[self.script]:
            box.add_widget(vlabel(group["group"], 13, bold=True,
                                  color=C["primary"]))
            grid = GridLayout(cols=5, spacing=dp(6), size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            for ch in group["chars"]:
                b = OptionButton(text=f"{ch['kana']}\n{ch['romaji']}",
                                 height=dp(64))
                b.halign = "center"
                b.bind(on_release=lambda btn, k=ch["kana"]:
                       app.tts.speak(k, "ja"))
                grid.add_widget(b)
            box.add_widget(grid)
        root.add_widget(sv)
        self.add_widget(root)

    def _switch(self, script):
        self.script = script
        self._chart()

    def _start_quiz(self):
        from core import kana as kana_core
        self.quiz = kana_core.make_quiz(self.script, n=12)
        self.qi = 0
        self.qok = 0
        self._quiz_step()

    def _quiz_step(self):
        self.clear_widgets()
        app = App.get_running_app()
        if self.qi >= len(self.quiz):
            self._quiz_done()
            return
        item = self.quiz[self.qi]
        root = BoxLayout(orientation="vertical")
        root.add_widget(TopBar(app, f"Quiz {self.qi + 1}/{len(self.quiz)}",
                               back_to="kana"))
        sv, box = scroll_body()
        big = PillButton(text=item["prompt"], height=dp(120),
                         bg=CARD, fg=TXT)
        big.font_size = sp(54)
        big.bind(on_release=lambda *a: app.tts.speak(item["kana"], "ja"))
        box.add_widget(big)
        box.add_widget(vlabel("(tap to hear)", 11, color=MUT,
                              halign="center"))
        self.fb = vlabel("", 15, bold=True, halign="center")
        box.add_widget(self.fb)
        self.obtns = []
        for opt in item["options"]:
            b = OptionButton(text=opt, height=dp(54))
            b.bind(on_release=lambda btn, o=opt: self._answer(btn, o, item))
            self.obtns.append(b)
            box.add_widget(b)
        root.add_widget(sv)
        self.add_widget(root)

    def _answer(self, btn, choice, item):
        app = App.get_running_app()
        correct = choice == item["answer"]
        if correct:
            self.qok += 1
        for b in self.obtns:
            b.disabled = True
            if b.text == item["answer"]:
                b.mark("correct")
            elif b.text == choice:
                b.mark("wrong")
        self.fb.text = (f"✅ {item['kana']} = {item['answer']}" if correct
                        else f"✖ {item['kana']} is “{item['answer']}”")
        self.fb.color = C["success"] if correct else C["error"]
        app.tts.speak(item["kana"], "ja")
        self.qi += 1
        Clock.schedule_once(lambda dt: self._quiz_step(), 1.0)

    def _quiz_done(self):
        self.clear_widgets()
        app = App.get_running_app()
        pct = round(100 * self.qok / len(self.quiz))
        root = BoxLayout(orientation="vertical")
        root.add_widget(TopBar(app, "Quiz results", back_to="kana"))
        sv, box = scroll_body()
        box.add_widget(vlabel("🎉", 50, halign="center"))
        box.add_widget(vlabel(f"{self.qok}/{len(self.quiz)} ({pct}%)", 26,
                              bold=True, halign="center",
                              color=C["success"]))
        if self.qok:
            app.db.add_xp(self.qok, exercises=len(self.quiz),
                          correct=self.qok)
        again = PillButton(text="Try again", bg=C["primary"])
        again.bind(on_release=lambda *a: self._start_quiz())
        box.add_widget(again)
        back = PillButton(text="Back to chart", bg=hexc("#E8E5DD"), fg=TXT)
        back.bind(on_release=lambda *a: self._chart())
        box.add_widget(back)
        root.add_widget(sv)
        self.add_widget(root)


class ProfileScreen(Screen):
    def on_pre_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        user = app.db.get_user()
        root = BoxLayout(orientation="vertical")
        root.add_widget(TopBar(app, "👤 Profile", back_to="home"))
        sv, box = scroll_body()
        league = app.db.league_for_xp(user.total_xp)
        mastered, total = app.db.vocab_mastery()
        card = CardBox()
        card.add_widget(vlabel(app.db.get_setting("username", "Learner"),
                               20, bold=True))
        card.add_widget(vlabel(f"🏆 {league} League", 14,
                               color=C["gold"]))
        card.add_widget(vlabel(
            f"⚡ {user.total_xp} XP   🔥 {user.streak}d   "
            f"🏅 best {user.best_streak}d   📚 {mastered}/{total} words",
            13))
        box.add_widget(card)

        box.add_widget(vlabel("Badges 🏮", 17, bold=True))
        unlocked = app.db.unlocked_badges()
        bc = CardBox()
        for bid, (icon, name, desc) in config.BADGES.items():
            got = bid in unlocked
            bc.add_widget(vlabel(
                f"{icon if got else '🔒'} {name} — {desc}", 13,
                color=C["gold"] if got else MUT))
        box.add_widget(bc)

        week = app.db.last_n_days_xp(7)
        wc = CardBox()
        wc.add_widget(vlabel("This week 📈", 15, bold=True))
        for d, xp in week:
            bar = "█" * min(20, xp // 5) if xp else "·"
            wc.add_widget(vlabel(f"{d.strftime('%a')}  {bar}  {xp}", 12))
        box.add_widget(wc)
        root.add_widget(sv)
        self.add_widget(root)


class SettingsScreen(Screen):
    def on_pre_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        root = BoxLayout(orientation="vertical")
        root.add_widget(TopBar(app, "⚙ Settings", back_to="home"))
        sv, box = scroll_body()

        card = CardBox()
        card.add_widget(vlabel("Display name", 14, bold=True))
        name = JPTextInput(text=app.db.get_setting("username", "Learner"))
        name.bind(on_text_validate=lambda i: app.db.set_username(i.text))
        card.add_widget(name)
        save = PillButton(text="Save name", height=dp(42), bg=C["primary"])
        save.bind(on_release=lambda *a: app.db.set_username(name.text))
        card.add_widget(save)
        box.add_widget(card)

        card = CardBox()
        card.add_widget(vlabel("Show romaji under Japanese", 14, bold=True))
        cur = app.db.get_setting("show_romaji", "1") == "1"
        toggle = PillButton(text="ON ✓" if cur else "OFF",
                            bg=C["success"] if cur else hexc("#B8B8B8"))

        def flip(*a):
            now = app.db.get_setting("show_romaji", "1") == "1"
            app.db.set_setting("show_romaji", "0" if now else "1")
            toggle.text = "OFF" if now else "ON ✓"
            toggle.set_bg(hexc("#B8B8B8") if now else C["success"])
        toggle.bind(on_release=flip)
        card.add_widget(toggle)
        box.add_widget(card)

        card = CardBox()
        card.add_widget(vlabel("Daily goal (XP)", 14, bold=True))
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for g in ("30", "50", "100", "150"):
            b = PillButton(text=g, bg=C["primary"]
                           if app.db.get_setting("daily_goal_xp",
                                                 "50") == g
                           else hexc("#E8E5DD"),
                           fg=(1, 1, 1, 1)
                           if app.db.get_setting("daily_goal_xp",
                                                 "50") == g else TXT)

            def set_goal(btn, val=g):
                app.db.set_setting("daily_goal_xp", val)
                self.on_pre_enter()
            b.bind(on_release=set_goal)
            row.add_widget(b)
        card.add_widget(row)
        box.add_widget(card)

        card = CardBox()
        card.add_widget(vlabel("Difficulty", 14, bold=True))
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for d in ("easy", "normal", "hard"):
            sel = app.db.get_setting("difficulty", "normal") == d
            b = PillButton(text=d, bg=C["primary"] if sel
                           else hexc("#E8E5DD"),
                           fg=(1, 1, 1, 1) if sel else TXT)

            def set_diff(btn, val=d):
                app.db.set_setting("difficulty", val)
                self.on_pre_enter()
            b.bind(on_release=set_diff)
            row.add_widget(b)
        card.add_widget(row)
        box.add_widget(card)

        box.add_widget(vlabel(
            f"⛩ {config.APP_NAME} {config.APP_VERSION} — Android edition\n"
            "がんばって！", 12, color=MUT))
        root.add_widget(sv)
        self.add_widget(root)


# =================================================================
# App
# =================================================================
class LinguaBridgeApp(App):
    title = "LinguaBridge"

    def build(self):
        Window.clearcolor = BG
        _redirect_user_data(self.user_data_dir)
        register_fonts()

        from database.db_manager import DBManager
        from core.lesson_manager import LessonManager
        self.db = DBManager(db_path=config.DB_PATH)
        self.lessons = LessonManager(self.db)
        self.tts = MobileTTS(self.db)

        self.sm = ScreenManager(transition=SlideTransition(
            duration=0.18))
        self.sm.add_widget(HomeScreen(name="home"))
        self.sm.add_widget(KanaScreen(name="kana"))
        self.sm.add_widget(StudyScreen(name="study"))
        self.sm.add_widget(LessonScreen(name="lesson"))
        self.sm.add_widget(ProfileScreen(name="profile"))
        self.sm.add_widget(SettingsScreen(name="settings"))
        return self.sm

    # ---------------------------------------------------------- nav
    def goto(self, name):
        self.sm.current = name

    def open_study(self, lesson):
        scr = self.sm.get_screen("study")
        scr.lesson = lesson
        self.goto("study")

    def start_lesson(self, lesson):
        if self.db.get_user().hearts <= 0:
            return
        scr = self.sm.get_screen("lesson")
        scr.session = self.lessons.build_lesson_session(lesson)
        self.goto("lesson")

    def start_srs(self):
        s = self.lessons.build_srs_session()
        if s:
            scr = self.sm.get_screen("lesson")
            scr.session = s
            self.goto("lesson")

    def start_mistakes(self):
        s = self.lessons.build_mistake_session()
        if s:
            scr = self.sm.get_screen("lesson")
            scr.session = s
            self.goto("lesson")


if __name__ == "__main__":
    LinguaBridgeApp().run()
