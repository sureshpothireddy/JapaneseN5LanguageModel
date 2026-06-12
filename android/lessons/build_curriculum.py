"""
build_curriculum.py — Generate lesson JSON files from n5_curriculum.py.

Run once (or whenever you edit the curriculum):
    python lessons/build_curriculum.py

For each curriculum entry it emits lessons/data/NN_<id>.json containing the
teaching content plus a balanced exercise set that always covers all eight
exercise types, built deterministically from the lesson's vocab + sentences.
The output is validated by the same loader the app uses, so a bad entry
fails loudly here instead of at runtime.
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lessons.n5_curriculum import CURRICULUM
from lessons.loader import _validate, EXERCISE_REQUIRED_KEYS

DATA_DIR = Path(__file__).resolve().parent / "data"
LEVEL = "N5"


def _vocab_dicts(vocab):
    out = []
    for ja, reading, romaji, en in vocab:
        out.append({"ja": ja, "reading": reading, "romaji": romaji, "en": en,
                    "example_ja": "", "example_en": ""})
    return out


def _tokenize(sentence_ja):
    """Split a spaced Japanese study sentence into build-tokens, attaching
    a trailing 。 as its own token."""
    raw = sentence_ja.replace("。", " 。").split()
    return [t for t in raw if t]


def _distractor_words(vocab, exclude):
    pool = [v[0] for v in vocab if v[0] not in exclude]
    return random.sample(pool, min(2, len(pool))) if pool else []


def build_exercises(entry):
    """Construct a balanced, valid exercise list covering all 8 types."""
    vocab = entry["vocab"]                     # list of (ja, reading, romaji, en)
    sents = entry.get("sentences", [])
    rng = random.Random(entry["id"])           # deterministic per lesson
    ex = []

    # 1. multiple_choice: meaning of a word (with audio)
    v = vocab[0]
    others = [w[3] for w in vocab[1:] if w[3] != v[3]]
    opts = rng.sample(others, min(3, len(others))) + [v[3]]
    rng.shuffle(opts)
    ex.append({"type": "multiple_choice",
               "question": f"What does {v[1]} mean?",
               "options": opts, "answer": v[3],
               "tts": v[1], "tts_lang": "ja"})

    # 2. multiple_choice: which kana is the word (reading recognition)
    v = vocab[1] if len(vocab) > 1 else vocab[0]
    others = [w[1] for w in vocab if w[1] != v[1]]
    opts = rng.sample(others, min(3, len(others))) + [v[1]]
    rng.shuffle(opts)
    ex.append({"type": "multiple_choice",
               "question": f"Which word means \u201c{v[3]}\u201d?",
               "options": opts, "answer": v[1], "options_lang": "ja"})

    # 3. matching: 5 word pairs
    pair_src = vocab[:5] if len(vocab) >= 5 else vocab
    ex.append({"type": "matching", "title": "Match the words",
               "pairs": [[w[1], w[3]] for w in pair_src]})

    # 4. translate en->ja (first vocab word)
    v = vocab[0]
    answers = [v[1]]
    if v[2]:
        answers.append(v[2])
    ex.append({"type": "translate", "direction": "en_ja", "text": v[3],
               "answers": answers, "hint": f"romaji: {v[2]}"})

    # 5. translate ja->en (a sentence if available, else a word)
    if sents:
        s = sents[0]
        ex.append({"type": "translate", "direction": "ja_en", "text": s[0],
                   "answers": [s[2].lower()], "hint": s[1]})
    else:
        v = vocab[2] if len(vocab) > 2 else vocab[-1]
        ex.append({"type": "translate", "direction": "ja_en", "text": v[1],
                   "answers": [v[3].lower()], "hint": v[2]})

    # 6. listen_type: a word
    v = vocab[3] if len(vocab) > 3 else vocab[-1]
    answers = [v[1]]
    if v[2]:
        answers.append(v[2])
    ex.append({"type": "listen_type", "audio_text": v[1], "lang": "ja",
               "answers": answers, "hint": v[3]})

    # 7. listen_type: a sentence (if available)
    if sents:
        s = sents[-1]
        ans = [s[0].replace(" ", ""), s[1]]
        ex.append({"type": "listen_type", "audio_text": s[0].replace(" ", ""),
                   "lang": "ja", "answers": ans, "hint": s[2]})

    # 8. fill_blank: blank out the last content word of a sentence
    if sents:
        s = sents[0]
        toks = [t for t in _tokenize(s[0]) if t != "\u3002"]
        target = toks[-1] if toks else vocab[0][1]
        blanked = s[0].replace(target, "___", 1)
        wrong = _distractor_words(vocab, {target})
        options = ([target] + wrong)[:4]
        if len(options) < 2:
            options = [target, vocab[-1][1]]
        rng.shuffle(options)
        ex.append({"type": "fill_blank", "sentence": blanked,
                   "options": options, "answer": target,
                   "translation": s[2]})

    # 9. sentence_build: build a study sentence
    if sents:
        s = sents[0] if len(sents) == 1 else sents[1]
        tokens = _tokenize(s[0])
        ex.append({"type": "sentence_build", "translation": s[2],
                   "tokens": tokens, "answer": s[0].replace(" ", ""),
                   "distractors": _distractor_words(vocab,
                                                    set(tokens))})

    # 10. listen_repeat: shadow a sentence or key word
    if sents:
        s = sents[0]
        ex.append({"type": "listen_repeat",
                   "audio_text": s[0].replace(" ", ""), "lang": "ja",
                   "romaji": s[1], "meaning": s[2]})
    else:
        v = vocab[0]
        ex.append({"type": "listen_repeat", "audio_text": v[1], "lang": "ja",
                   "romaji": v[2], "meaning": v[3]})

    # 11. speak_translate: say a sentence/word in Japanese
    if sents:
        s = sents[-1]
        ex.append({"type": "speak_translate", "text": s[2],
                   "target": s[0].replace(" ", ""),
                   "accept": [s[0].replace(" ", "")], "romaji": s[1]})
    else:
        v = vocab[0]
        ex.append({"type": "speak_translate", "text": v[3], "target": v[1],
                   "accept": [v[1]], "romaji": v[2]})

    # 12. fill_blank: grammar particle / second sentence if available
    if len(sents) > 1:
        s = sents[-1]
        toks = [t for t in _tokenize(s[0]) if t != "\u3002"]
        # blank a middle token for variety
        target = toks[len(toks) // 2] if len(toks) > 2 else toks[-1]
        blanked = s[0].replace(target, "___", 1)
        wrong = _distractor_words(vocab, {target})
        options = ([target] + wrong)[:4]
        if len(options) < 2:
            options = [target, vocab[0][1]]
        rng.shuffle(options)
        ex.append({"type": "fill_blank", "sentence": blanked,
                   "options": options, "answer": target,
                   "translation": s[2]})

    # 13. translate en->ja: another vocab word for breadth
    v = vocab[-1]
    answers = [v[1]]
    if v[2]:
        answers.append(v[2])
    ex.append({"type": "translate", "direction": "en_ja", "text": v[3],
               "answers": answers, "hint": f"romaji: {v[2]}"})

    return ex


def build_lesson(entry):
    lesson = {
        "id": entry["id"],
        "order": entry["order"],
        "title": entry["title"],
        "icon": entry["icon"],
        "level": LEVEL,
        "difficulty": entry["difficulty"],
        "description": entry["description"],
        "objectives": entry.get("objectives", []),
        "study_guide": [{"heading": s["heading"], "body": s["body"]}
                        for s in entry.get("study_guide", [])],
        "examples": [{"ja": ja, "romaji": romaji, "en": en}
                     for ja, romaji, en in entry.get("examples", [])],
        "grammar_note": entry.get("grammar_note", {}),
        "culture_note": entry.get("culture_note", ""),
        "vocab": _vocab_dicts(entry["vocab"]),
        "exercises": build_exercises(entry),
    }
    return lesson


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for entry in CURRICULUM:
        lesson = build_lesson(entry)
        _validate(lesson, f"{entry['id']}.json")     # fail loudly on bad data
        # confirm all 8 types present
        types = {e["type"] for e in lesson["exercises"]}
        missing = set(EXERCISE_REQUIRED_KEYS) - types
        if missing:
            raise SystemExit(f"{entry['id']}: missing exercise types {missing}")
        fname = DATA_DIR / f"{entry['order']:02d}_{entry['id']}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(lesson, f, ensure_ascii=False, indent=1)
        written += 1
        print(f"  ✓ {fname.name}  ({len(lesson['exercises'])} exercises)")
    print(f"Generated {written} lesson files.")


if __name__ == "__main__":
    main()
