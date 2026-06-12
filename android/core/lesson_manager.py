"""
core/lesson_manager.py — Orchestrates lessons, sessions and reviews.

Sits between the UI and (loader, db, srs):
  * loads + caches all lessons, seeds SRS vocab into the database
  * recommends the next lesson (adaptive: weakest/unfinished first)
  * builds exercise sessions (lesson, mistake-review, SRS-review)
  * records results: XP, hearts, SRS scheduling, mistakes, badges
"""

import datetime as dt
import json
import random

import config
from core import srs
from lessons.loader import load_all_lessons, Lesson


class Session:
    """One run of exercises (a lesson or a review)."""

    def __init__(self, kind: str, title: str, exercises: list[dict],
                 lesson_id: str = ""):
        self.kind = kind                  # "lesson" | "mistakes" | "srs"
        self.title = title
        self.lesson_id = lesson_id
        self.exercises = exercises
        self.index = 0
        self.correct = 0
        self.wrong = 0
        self.xp_earned = 0

    @property
    def total(self) -> int:
        return len(self.exercises)

    @property
    def current(self) -> dict | None:
        return (self.exercises[self.index]
                if self.index < self.total else None)

    def advance(self):
        self.index += 1

    @property
    def finished(self) -> bool:
        return self.index >= self.total

    @property
    def score_pct(self) -> float:
        done = self.correct + self.wrong
        return round(100 * self.correct / done, 1) if done else 0.0


class LessonManager:
    def __init__(self, db):
        self.db = db
        self.lessons: list[Lesson] = load_all_lessons()
        # Vocabulary enters the SRS deck only once its lesson is completed —
        # a brand-new learner shouldn't face hundreds of due cards on day 1.
        prog = self.db.all_lesson_progress()
        for lesson in self.lessons:
            p = prog.get(lesson.id)
            if p and p.completed:
                self.db.seed_vocab(lesson.id, lesson.vocab)

    # ------------------------------------------------------------ catalogue
    def get_lesson(self, lesson_id: str) -> Lesson | None:
        return next((l for l in self.lessons if l.id == lesson_id), None)

    def lessons_with_progress(self) -> list[tuple[Lesson, dict]]:
        """[(lesson, {'completed', 'best', 'unlocked'}), ...] in order.
        Adaptive gating: a lesson unlocks once the previous one is completed
        (difficulty 'easy' setting unlocks everything)."""
        prog = self.db.all_lesson_progress()
        easy = self.db.get_setting("difficulty", "normal") == "easy"
        out, prev_done = [], True
        for lesson in self.lessons:
            p = prog.get(lesson.id)
            done = bool(p and p.completed)
            out.append((lesson, {
                "completed": done,
                "best": (p.best_score_pct if p else 0.0),
                "unlocked": easy or prev_done,
            }))
            prev_done = done
        return out

    def recommended(self) -> Lesson | None:
        """Adaptive pick: first unlocked-unfinished lesson; if all complete,
        the one with the weakest best score (targeting weak areas)."""
        rows = self.lessons_with_progress()
        for lesson, info in rows:
            if info["unlocked"] and not info["completed"]:
                return lesson
        if rows:
            return min(rows, key=lambda r: r[1]["best"])[0]
        return None

    # ------------------------------------------------------------ sessions
    def build_lesson_session(self, lesson: Lesson) -> Session:
        exercises = list(lesson.exercises)
        diff = self.db.get_setting("difficulty", "normal")
        if diff == "easy":
            # gentler: drop one speaking exercise if present
            speak = [e for e in exercises if e["type"] == "speak_translate"]
            for e in speak[1:]:
                exercises.remove(e)
        elif diff == "hard":
            random.shuffle(exercises)
        return Session("lesson", lesson.title, exercises, lesson_id=lesson.id)

    def build_mistake_session(self) -> Session | None:
        rows = self.db.pending_mistakes()
        if not rows:
            return None
        exercises = []
        for m in rows:
            ex = json.loads(m.exercise_json)
            ex["_mistake_id"] = m.id
            ex["_lesson_id"] = m.lesson_id
            exercises.append(ex)
        return Session("mistakes", "Mistake Review", exercises)

    def build_srs_session(self) -> Session | None:
        cards = self.db.due_vocab()
        if not cards:
            return None
        exercises = []
        for card in cards:
            # alternate recognition / recall / listening for variety
            mode = random.choice(["ja_en", "en_ja", "listen"])
            if mode == "ja_en":
                ex = {"type": "translate", "direction": "ja_en",
                      "text": card.ja, "answers": [card.en] + _en_variants(card.en),
                      "hint": f"romaji: {card.romaji}" if card.romaji else ""}
            elif mode == "en_ja":
                answers = [card.ja]
                if card.reading and card.reading != card.ja:
                    answers.append(card.reading)
                ex = {"type": "translate", "direction": "en_ja",
                      "text": card.en, "answers": answers,
                      "hint": card.example_en}
            else:
                answers = [card.ja]
                if card.reading and card.reading != card.ja:
                    answers.append(card.reading)
                if card.romaji:
                    answers.append(card.romaji)
                ex = {"type": "listen_type", "audio_text": card.reading or card.ja,
                      "lang": "ja", "answers": answers, "hint": card.en}
            ex["_vocab_key"] = card.vocab_key
            exercises.append(ex)
        return Session("srs", "Daily Review", exercises)

    # ------------------------------------------------------------ recording
    def record_answer(self, session: Session, exercise: dict, correct: bool,
                      user_answer: str, similarity: float = None) -> dict:
        """Update all systems after one answered exercise.
        Returns {'xp': int, 'hearts': int} for the UI."""
        hard = exercise["type"] in ("speak_translate", "sentence_build",
                                    "listen_repeat")
        xp = 0
        if correct:
            session.correct += 1
            if session.kind == "lesson":
                xp = config.XP_PER_CORRECT_HARD if hard else config.XP_PER_CORRECT
            else:
                xp = config.XP_REVIEW_ITEM
            session.xp_earned += xp
            if exercise["type"] in ("speak_translate", "listen_repeat"):
                self.db.bump_counter("speaking_passes")
        else:
            session.wrong += 1
            if session.kind == "lesson":
                self.db.lose_heart()
                self.db.add_mistake(session.lesson_id, _clean(exercise),
                                    user_answer)

        # SRS updates for review cards
        if "_vocab_key" in exercise:
            q = srs.quality_from_answer(correct, similarity)
            card = next((c for c in self.db.due_vocab(limit=999)
                         if c.vocab_key == exercise["_vocab_key"]), None)
            if card:
                res = srs.review(q, card.ease, card.interval_days,
                                 card.repetitions)
                self.db.update_vocab_srs(card.vocab_key, res.ease,
                                         res.interval_days, res.repetitions,
                                         res.due_date, res.lapsed)
            self.db.bump_counter("srs_reviews_done")
        # mistake queue resolution
        if "_mistake_id" in exercise and correct:
            self.db.resolve_mistake(exercise["_mistake_id"])

        user = self.db.get_user()
        return {"xp": xp, "hearts": user.hearts}

    def finish_session(self, session: Session) -> dict:
        """Commit XP/streak, lesson progress, hearts bonus and badges.
        Returns a results dict for the results screen."""
        bonus = 0
        if session.kind == "lesson":
            bonus += config.XP_LESSON_BONUS
            if session.wrong == 0 and session.correct > 0:
                bonus += config.XP_PERFECT_BONUS
            self.db.record_lesson_result(session.lesson_id, session.score_pct)
            # the lesson's vocabulary now joins the spaced-repetition deck
            lesson = self.get_lesson(session.lesson_id)
            if lesson:
                self.db.seed_vocab(lesson.id, lesson.vocab)
        else:
            self.db.add_hearts(config.HEARTS_FROM_REVIEW)
        total_xp = session.xp_earned + bonus
        self.db.add_xp(total_xp, exercises=session.correct + session.wrong,
                       correct=session.correct)
        new_badges = self._check_badges(session)
        user = self.db.get_user()
        return {"xp": total_xp, "bonus": bonus, "score": session.score_pct,
                "correct": session.correct, "wrong": session.wrong,
                "streak": user.streak, "new_badges": new_badges,
                "perfect": session.wrong == 0 and session.correct > 0}

    # ------------------------------------------------------------ badges
    def _check_badges(self, session: Session) -> list[tuple]:
        user = self.db.get_user()
        completed = sum(1 for _, i in self.lessons_with_progress()
                        if i["completed"])
        candidates = {
            "first_steps": session.kind == "lesson",
            "streak_3": user.streak >= 3,
            "streak_7": user.streak >= 7,
            "xp_100": user.total_xp >= 100,
            "xp_500": user.total_xp >= 500,
            "perfect": session.kind == "lesson" and session.wrong == 0
                       and session.correct > 0,
            "reviewer": (user.srs_reviews_done or 0) >= 20,
            "five_lessons": completed >= 5,
            "speaker": (user.speaking_passes or 0) >= 10,
        }
        new = []
        for badge_id, earned in candidates.items():
            if earned and self.db.unlock_badge(badge_id):
                icon, name, desc = config.BADGES[badge_id]
                new.append((icon, name, desc))
        return new


# -------------------------------------------------------------- helpers
def _clean(exercise: dict) -> dict:
    return {k: v for k, v in exercise.items() if not k.startswith("_")}


def _en_variants(en: str) -> list[str]:
    """Split 'hello / good afternoon' style glosses into variants."""
    parts = [p.strip() for p in en.replace("/", "|").split("|") if p.strip()]
    extra = []
    for p in parts:
        if "(" in p:
            extra.append(p.split("(")[0].strip())
    return parts + extra
