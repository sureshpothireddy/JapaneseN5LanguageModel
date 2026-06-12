"""
utils/japanese_utils.py — Japanese text helpers.

Uses pykakasi (kanji→kana/romaji) and jaconv (kana/width normalization)
when installed; degrades gracefully (identity functions) when they are not,
so the app still runs anywhere.
"""

import re
import unicodedata

# ---------------------------------------------------------------- optional deps
try:
    import pykakasi
    _kks = pykakasi.kakasi()
except Exception:                                    # pragma: no cover
    _kks = None

try:
    import jaconv
except Exception:                                    # pragma: no cover
    jaconv = None

_PUNCT_RE = re.compile(r"[ \t\u3000。、．，,.!！?？・「」『』()（）\"'’‘\-—~〜:;]+")

_HIRAGANA = (0x3041, 0x3096)
_KATAKANA = (0x30A1, 0x30FA)
_KANJI = (0x4E00, 0x9FFF)


def _in_range(ch: str, rng: tuple) -> bool:
    return rng[0] <= ord(ch) <= rng[1]


def contains_japanese(text: str) -> bool:
    return any(_in_range(c, _HIRAGANA) or _in_range(c, _KATAKANA)
               or _in_range(c, _KANJI) for c in text)


def contains_kanji(text: str) -> bool:
    return any(_in_range(c, _KANJI) for c in text)


# ---------------------------------------------------------------- conversion
def to_hiragana(text: str) -> str:
    """Kanji/Katakana → Hiragana (best effort)."""
    if _kks:
        try:
            text = "".join(item["hira"] for item in _kks.convert(text))
        except Exception:
            pass
    elif jaconv:
        text = jaconv.kata2hira(text)
    else:
        # stdlib fallback: shift katakana block onto hiragana block
        text = "".join(chr(ord(c) - 0x60) if _in_range(c, _KATAKANA) else c
                       for c in text)
    return text


def to_romaji(text: str) -> str:
    """Japanese → romaji (best effort; returns input if no converter)."""
    if _kks:
        try:
            return " ".join(item["hepburn"] for item in _kks.convert(text)).strip()
        except Exception:
            pass
    return text


def furigana_pairs(text: str) -> list[tuple[str, str]]:
    """[(surface, reading), ...] — reading == '' when surface is already kana."""
    if not _kks:
        return [(text, "")]
    try:
        out = []
        for item in _kks.convert(text):
            surface, hira = item["orig"], item["hira"]
            out.append((surface, hira if surface != hira else ""))
        return out
    except Exception:
        return [(text, "")]


# ---------------------------------------------------------------- normalization
def normalize_japanese(text: str) -> str:
    """
    Canonical comparison form for grading Japanese answers:
    NFKC → full-width unification → all-hiragana → strip punctuation/spaces.
    Makes 'スシをたべます。' == 'すしを食べます' for matching purposes.
    """
    text = unicodedata.normalize("NFKC", text or "")
    if jaconv:
        text = jaconv.z2h(text, kana=False, ascii=True, digit=True)
        text = jaconv.h2z(text, kana=True, ascii=False, digit=False)
    text = to_hiragana(text)
    text = _PUNCT_RE.sub("", text)
    return text.strip().lower()


def normalize_english(text: str) -> str:
    """Lowercase, strip punctuation/extra spaces, drop leading articles."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(the|a|an) ", "", text)
    return text


def normalize_for_lang(text: str, lang: str) -> str:
    return normalize_japanese(text) if lang.startswith("ja") \
        else normalize_english(text)
