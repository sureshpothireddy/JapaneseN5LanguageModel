"""
lessons/loader.py — Loads and validates lesson JSON files.

A lesson file lives in lessons/data/*.json and must contain:
    id, title, icon, level, difficulty, description,
    vocab[]      (ja, en required; reading/romaji/example_* optional)
    exercises[]  (each with a known "type" + that type's required keys)
Optional: grammar_note {title, body}, culture_note (str), order (int).

Validation is strict and runs at startup so content typos fail loudly
with the file name and the reason — never silently mid-lesson.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import config

EXERCISE_REQUIRED_KEYS = {
    "translate":       {"direction", "text", "answers"},
    "listen_type":     {"audio_text", "lang", "answers"},
    "speak_translate": {"text", "target", "accept"},
    "listen_repeat":   {"audio_text", "lang"},
    "multiple_choice": {"question", "options", "answer"},
    "matching":        {"pairs"},
    "fill_blank":      {"sentence", "options", "answer"},
    "sentence_build":  {"translation", "tokens", "answer"},
}


@dataclass
class Lesson:
    id: str
    title: str
    icon: str
    level: str
    difficulty: int
    description: str
    vocab: list = field(default_factory=list)
    exercises: list = field(default_factory=list)
    grammar_note: dict = field(default_factory=dict)
    culture_note: str = ""
    order: int = 99
    # ---- teaching content (the "teacher" half of each lesson) ----
    study_guide: list = field(default_factory=list)   # [{heading, body}, ...]
    examples: list = field(default_factory=list)       # [{ja, romaji, en, note}]
    objectives: list = field(default_factory=list)     # ["learn X", ...]


class LessonValidationError(Exception):
    pass


def _validate(data: dict, fname: str) -> None:
    for key in ("id", "title", "level", "difficulty", "description",
                "vocab", "exercises"):
        if key not in data:
            raise LessonValidationError(f"{fname}: missing top-level '{key}'")
    if not isinstance(data["exercises"], list) or not data["exercises"]:
        raise LessonValidationError(f"{fname}: 'exercises' must be a "
                                    f"non-empty list")
    for i, v in enumerate(data["vocab"]):
        for key in ("ja", "en"):
            if key not in v:
                raise LessonValidationError(
                    f"{fname}: vocab[{i}] missing '{key}'")
    for i, ex in enumerate(data["exercises"]):
        etype = ex.get("type")
        if etype not in EXERCISE_REQUIRED_KEYS:
            raise LessonValidationError(
                f"{fname}: exercises[{i}] unknown type '{etype}'")
        missing = EXERCISE_REQUIRED_KEYS[etype] - set(ex)
        if missing:
            raise LessonValidationError(
                f"{fname}: exercises[{i}] ({etype}) missing {sorted(missing)}")
        if etype == "multiple_choice" and ex["answer"] not in ex["options"]:
            raise LessonValidationError(
                f"{fname}: exercises[{i}] answer not in options")
        if etype == "fill_blank" and ex["answer"] not in ex["options"]:
            raise LessonValidationError(
                f"{fname}: exercises[{i}] blank answer not in options")


def load_all_lessons(data_dir: Path | None = None) -> list[Lesson]:
    """Load every lesson JSON, validated and sorted by (order, difficulty)."""
    data_dir = data_dir or config.LESSONS_DIR
    lessons = []
    for path in sorted(Path(data_dir).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise LessonValidationError(f"{path.name}: invalid JSON "
                                            f"({e})") from e
        _validate(data, path.name)
        lessons.append(Lesson(
            id=data["id"], title=data["title"], icon=data.get("icon", "📖"),
            level=data["level"], difficulty=int(data["difficulty"]),
            description=data["description"], vocab=data["vocab"],
            exercises=data["exercises"],
            grammar_note=data.get("grammar_note", {}),
            culture_note=data.get("culture_note", ""),
            order=int(data.get("order", 99)),
            study_guide=data.get("study_guide", []),
            examples=data.get("examples", []),
            objectives=data.get("objectives", [])))
    lessons.sort(key=lambda l: (l.order, l.difficulty, l.title))
    return lessons
