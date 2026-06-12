"""
core/kana.py — Hiragana & Katakana data + quiz generation.

The kana trainer is the true starting point for a beginner: before any
words make sense you must be able to *read* the syllabary. This module
loads lessons/kana.json and builds simple recognition quizzes
(kana -> romaji and romaji -> kana).
"""

import json
import random
from pathlib import Path

import config

_KANA_PATH = Path(config.BASE_DIR) / "lessons" / "kana.json"


def load_kana() -> dict:
    with open(_KANA_PATH, encoding="utf-8") as f:
        return json.load(f)


def all_chars(script: str) -> list[dict]:
    """Flat list of {kana, romaji} for 'hiragana' or 'katakana'."""
    data = load_kana()
    return [c for group in data[script] for c in group["chars"]]


def make_quiz(script: str, n: int = 10, direction: str = "kana_to_romaji",
              pool: list | None = None) -> list[dict]:
    """
    Build n multiple-choice questions.
    Each item: {prompt, answer, options[4], kana, romaji}
    """
    chars = pool or all_chars(script)
    chosen = random.sample(chars, min(n, len(chars)))
    quiz = []
    for c in chosen:
        if direction == "kana_to_romaji":
            prompt, answer = c["kana"], c["romaji"]
            distractor_field = "romaji"
        else:
            prompt, answer = c["romaji"], c["kana"]
            distractor_field = "kana"
        others = [d[distractor_field] for d in chars
                  if d[distractor_field] != answer]
        options = random.sample(others, 3) + [answer]
        random.shuffle(options)
        quiz.append({"prompt": prompt, "answer": answer, "options": options,
                     "kana": c["kana"], "romaji": c["romaji"]})
    return quiz
