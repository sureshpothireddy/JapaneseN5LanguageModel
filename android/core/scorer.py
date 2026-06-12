"""
core/scorer.py — Grades every kind of answer in LinguaBridge.

* Text answers (translations, listen & type, fill-in-the-blank …) are
  graded with language-aware normalization + fuzzy similarity so small
  typos, kana/kanji variants, or punctuation never punish the learner.
* Speech answers compare the STT transcript to the target sentence on the
  hiragana level and return a pronunciation percentage plus per-word
  feedback for the visual mistake highlighting.
"""

from dataclasses import dataclass, field

import config
from utils import japanese_utils as ju

# rapidfuzz preferred; difflib fallback keeps the app dependency-tolerant
try:
    from rapidfuzz import fuzz

    def _similarity(a: str, b: str) -> float:
        return float(fuzz.ratio(a, b))
except Exception:                                    # pragma: no cover
    import difflib

    def _similarity(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio() * 100


@dataclass
class GradeResult:
    correct: bool
    similarity: float                 # 0–100 vs the best-matching answer
    best_answer: str                  # the canonical accepted answer
    feedback: str = ""
    word_marks: list = field(default_factory=list)   # [(word, ok_bool), ...]


# ---------------------------------------------------------------- text answers
def grade_text(user_answer: str, accepted: list[str], lang: str,
               threshold: int = None) -> GradeResult:
    """Grade a typed answer against any accepted variant."""
    threshold = threshold or config.TEXT_MATCH_THRESHOLD
    user_norm = ju.normalize_for_lang(user_answer, lang)
    best_sim, best_ans = 0.0, accepted[0] if accepted else ""
    for ans in accepted:
        sim = _similarity(user_norm, ju.normalize_for_lang(ans, lang))
        if sim > best_sim:
            best_sim, best_ans = sim, ans
    correct = best_sim >= threshold and bool(user_norm)
    if correct and best_sim < 100:
        fb = "Correct — watch the small details!" if best_sim < 95 else ""
    elif correct:
        fb = ""
    else:
        fb = f"The answer was: {best_ans}"
    return GradeResult(correct, round(best_sim, 1), best_ans, fb)


def grade_exact_choice(user_choice: str, answer: str) -> GradeResult:
    ok = (user_choice or "").strip() == (answer or "").strip()
    return GradeResult(ok, 100.0 if ok else 0.0, answer,
                       "" if ok else f"The answer was: {answer}")


# ---------------------------------------------------------------- speech
def grade_pronunciation(transcript: str, target: str, lang: str = "ja",
                        pass_pct: int = None) -> GradeResult:
    """
    Compare what the user *said* (STT transcript) to the target phrase.
    Marks each target word green/red for the visual feedback strip.
    """
    pass_pct = pass_pct or config.PRONUNCIATION_PASS
    if not transcript:
        return GradeResult(False, 0.0, target,
                           "We couldn't hear anything — try again closer "
                           "to the microphone.")

    t_norm = ju.normalize_for_lang(transcript, lang)
    g_norm = ju.normalize_for_lang(target, lang)
    overall = _similarity(t_norm, g_norm)

    # word-level marks: split target into comparable chunks
    if lang.startswith("ja"):
        chunks = _split_japanese(target)
    else:
        chunks = target.split()
    marks = []
    for chunk in chunks:
        c_norm = ju.normalize_for_lang(chunk, lang)
        ok = c_norm in t_norm or _similarity(c_norm, t_norm) >= 70 \
            or _best_substring_sim(c_norm, t_norm) >= 75
        marks.append((chunk, ok))

    correct = overall >= pass_pct
    if correct:
        fb = "Beautiful pronunciation!" if overall >= 90 else \
             "Good! A little more practice and it'll be perfect."
    else:
        fb = f"We heard: 「{transcript}」 — let's try that once more."
    return GradeResult(correct, round(overall, 1), target, fb, marks)


def _split_japanese(text: str) -> list[str]:
    """Word segmentation via fugashi when available, else char bigrams."""
    try:
        from fugashi import Tagger
        tagger = _split_japanese._tagger or Tagger()
        _split_japanese._tagger = tagger
        words = [w.surface for w in tagger(text) if w.surface.strip()]
        if words:
            return words
    except Exception:
        pass
    text = text.replace("。", "").replace("、", "")
    if len(text) <= 4:
        return [text]
    return [text[i:i + 2] for i in range(0, len(text), 2)]


_split_japanese._tagger = None


def _best_substring_sim(needle: str, haystack: str) -> float:
    """Best similarity of needle against any same-length window of haystack."""
    n = len(needle)
    if not n or not haystack:
        return 0.0
    if n >= len(haystack):
        return _similarity(needle, haystack)
    return max(_similarity(needle, haystack[i:i + n])
               for i in range(len(haystack) - n + 1))


# ---------------------------------------------------------------- sessions
def session_score(correct: int, total: int) -> float:
    return round(100.0 * correct / total, 1) if total else 0.0
