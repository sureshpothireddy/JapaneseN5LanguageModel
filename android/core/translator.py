"""
core/translator.py — Translation hints.

Primary: deep-translator (Google backend, online).
Fallback: an offline mini phrase table built from all loaded lesson vocab,
so hint buttons still work without internet.
"""

try:
    from deep_translator import GoogleTranslator
    _DT_OK = True
except Exception:
    _DT_OK = False


class Translator:
    def __init__(self):
        self._offline: dict[str, str] = {}     # normalized source -> target

    def register_offline_pairs(self, pairs: list[tuple[str, str]]):
        """Feed (ja, en) vocab pairs from lessons for offline lookups."""
        for ja, en in pairs:
            self._offline[ja.strip()] = en.strip()
            self._offline[en.strip().lower()] = ja.strip()

    def translate(self, text: str, source: str, target: str) -> str | None:
        """source/target: 'en' or 'ja'. Returns None when unavailable."""
        text = (text or "").strip()
        if not text:
            return None
        # offline table first (instant, free, deterministic for lesson vocab)
        hit = self._offline.get(text) or self._offline.get(text.lower())
        if hit:
            return hit
        if _DT_OK:
            try:
                return GoogleTranslator(source=source,
                                        target=target).translate(text)
            except Exception:
                return None
        return None
