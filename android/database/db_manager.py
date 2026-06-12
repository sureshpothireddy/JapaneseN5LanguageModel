"""
database/db_manager.py — All database access for LinguaBridge.

A single DBManager instance is created in main.py and passed down.
UI/core code never touches SQLAlchemy sessions directly.
"""

import datetime as dt
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import config
from database.models import (Base, User, LessonProgress, VocabSRS, Mistake,
                             BadgeUnlock, DailyStat, Setting)


class DBManager:
    def __init__(self, db_path=None):
        path = db_path or config.DB_PATH
        self.engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True,
                                    expire_on_commit=False)
        self._ensure_user()
        self._ensure_settings()

    # ------------------------------------------------------------ internals
    def _ensure_user(self):
        with self.Session() as s:
            if not s.scalar(select(User).limit(1)):
                s.add(User(name=config.DEFAULT_SETTINGS["username"],
                           hearts=config.MAX_HEARTS))
                s.commit()

    def _ensure_settings(self):
        with self.Session() as s:
            existing = {r.key for r in s.scalars(select(Setting)).all()}
            for k, v in config.DEFAULT_SETTINGS.items():
                if k not in existing:
                    s.add(Setting(key=k, value=v))
            s.commit()

    # ------------------------------------------------------------ user
    def get_user(self) -> User:
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            self._regen_hearts(s, user)
            s.commit()
            return user

    def _regen_hearts(self, s, user: User):
        """Lazily refill hearts: +1 every HEART_REFILL_MINUTES."""
        if user.hearts >= config.MAX_HEARTS:
            user.hearts_updated_at = dt.datetime.utcnow()
            return
        elapsed = (dt.datetime.utcnow() - (user.hearts_updated_at or
                                           dt.datetime.utcnow()))
        gained = int(elapsed.total_seconds() // (config.HEART_REFILL_MINUTES * 60))
        if gained > 0:
            user.hearts = min(config.MAX_HEARTS, user.hearts + gained)
            user.hearts_updated_at = dt.datetime.utcnow()

    def lose_heart(self) -> int:
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            if user.hearts > 0:
                if user.hearts == config.MAX_HEARTS:
                    user.hearts_updated_at = dt.datetime.utcnow()
                user.hearts -= 1
            s.commit()
            return user.hearts

    def add_hearts(self, n: int) -> int:
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            user.hearts = min(config.MAX_HEARTS, user.hearts + n)
            s.commit()
            return user.hearts

    def add_xp(self, xp: int, exercises: int = 0, correct: int = 0):
        """Add XP, log the daily stat row and update the streak."""
        today = dt.date.today()
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            user.total_xp += xp
            # streak logic: active today extends/keeps streak
            if user.last_active_date != today:
                if user.last_active_date == today - dt.timedelta(days=1):
                    user.streak += 1
                else:
                    user.streak = 1
                user.last_active_date = today
                user.best_streak = max(user.best_streak, user.streak)
            stat = s.scalar(select(DailyStat).where(DailyStat.day == today))
            if not stat:
                stat = DailyStat(day=today, xp=0, exercises_done=0, correct=0)
                s.add(stat)
            stat.xp += xp
            stat.exercises_done += exercises
            stat.correct += correct
            s.commit()

    def bump_counter(self, field: str, n: int = 1):
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            setattr(user, field, (getattr(user, field) or 0) + n)
            s.commit()

    def set_username(self, name: str):
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            user.name = name.strip() or "Learner"
            s.commit()
        self.set_setting("username", name)

    def league_for_xp(self, xp: int) -> str:
        name = config.LEAGUES[0][0]
        for league, threshold in config.LEAGUES:
            if xp >= threshold:
                name = league
        return name

    # ------------------------------------------------------------ lessons
    def get_lesson_progress(self, lesson_id: str) -> LessonProgress | None:
        with self.Session() as s:
            return s.scalar(select(LessonProgress)
                            .where(LessonProgress.lesson_id == lesson_id))

    def all_lesson_progress(self) -> dict:
        with self.Session() as s:
            return {p.lesson_id: p
                    for p in s.scalars(select(LessonProgress)).all()}

    def record_lesson_result(self, lesson_id: str, score_pct: float):
        with self.Session() as s:
            p = s.scalar(select(LessonProgress)
                         .where(LessonProgress.lesson_id == lesson_id))
            if not p:
                p = LessonProgress(lesson_id=lesson_id, completed=False,
                                   best_score_pct=0.0, times_completed=0)
                s.add(p)
            p.completed = True
            p.times_completed = (p.times_completed or 0) + 1
            p.best_score_pct = max(p.best_score_pct or 0, score_pct)
            p.last_completed_at = dt.datetime.utcnow()
            s.commit()

    # ------------------------------------------------------------ SRS vocab
    def seed_vocab(self, lesson_id: str, vocab: list[dict]):
        """Insert vocabulary cards for a lesson if not already present."""
        with self.Session() as s:
            for v in vocab:
                key = f"{lesson_id}:{v['ja']}"
                if not s.scalar(select(VocabSRS)
                                .where(VocabSRS.vocab_key == key)):
                    s.add(VocabSRS(
                        vocab_key=key, lesson_id=lesson_id, ja=v["ja"],
                        reading=v.get("reading", ""), romaji=v.get("romaji", ""),
                        en=v["en"], example_ja=v.get("example_ja", ""),
                        example_en=v.get("example_en", ""),
                        due_date=dt.date.today()))
            s.commit()

    def due_vocab(self, limit: int = None) -> list[VocabSRS]:
        limit = limit or config.SRS_REVIEW_LIMIT
        with self.Session() as s:
            rows = s.scalars(
                select(VocabSRS)
                .where(VocabSRS.due_date <= dt.date.today())
                .order_by(VocabSRS.due_date)
                .limit(limit)).all()
            return rows

    def due_vocab_count(self) -> int:
        return len(self.due_vocab(limit=999))

    def update_vocab_srs(self, vocab_key: str, ease: float,
                         interval_days: float, repetitions: int,
                         due_date: dt.date, lapsed: bool):
        with self.Session() as s:
            row = s.scalar(select(VocabSRS)
                           .where(VocabSRS.vocab_key == vocab_key))
            if row:
                row.ease = ease
                row.interval_days = interval_days
                row.repetitions = repetitions
                row.due_date = due_date
                row.last_reviewed = dt.datetime.utcnow()
                if lapsed:
                    row.lapses += 1
                s.commit()

    def vocab_mastery(self) -> tuple[int, int]:
        """(mastered, total) — mastered = interval >= 7 days."""
        with self.Session() as s:
            rows = s.scalars(select(VocabSRS)).all()
            mastered = sum(1 for r in rows if r.interval_days >= 7)
            return mastered, len(rows)

    # ------------------------------------------------------------ mistakes
    def add_mistake(self, lesson_id: str, exercise: dict, user_answer: str):
        with self.Session() as s:
            s.add(Mistake(lesson_id=lesson_id,
                          exercise_json=json.dumps(exercise, ensure_ascii=False),
                          user_answer=user_answer))
            s.commit()

    def pending_mistakes(self, limit: int = 15) -> list[Mistake]:
        with self.Session() as s:
            return s.scalars(select(Mistake)
                             .where(Mistake.resolved == False)  # noqa: E712
                             .order_by(Mistake.created_at)
                             .limit(limit)).all()

    def resolve_mistake(self, mistake_id: int):
        with self.Session() as s:
            m = s.get(Mistake, mistake_id)
            if m:
                m.resolved = True
                s.commit()

    # ------------------------------------------------------------ badges
    def unlocked_badges(self) -> set[str]:
        with self.Session() as s:
            return {b.badge_id for b in s.scalars(select(BadgeUnlock)).all()}

    def unlock_badge(self, badge_id: str) -> bool:
        """Returns True if it was newly unlocked."""
        with self.Session() as s:
            if s.scalar(select(BadgeUnlock)
                        .where(BadgeUnlock.badge_id == badge_id)):
                return False
            s.add(BadgeUnlock(badge_id=badge_id))
            s.commit()
            return True

    # ------------------------------------------------------------ stats
    def xp_today(self) -> int:
        with self.Session() as s:
            stat = s.scalar(select(DailyStat)
                            .where(DailyStat.day == dt.date.today()))
            return stat.xp if stat else 0

    def last_n_days_xp(self, n: int = 7) -> list[tuple[dt.date, int]]:
        start = dt.date.today() - dt.timedelta(days=n - 1)
        with self.Session() as s:
            rows = {r.day: r.xp for r in s.scalars(
                select(DailyStat).where(DailyStat.day >= start)).all()}
        return [(start + dt.timedelta(days=i),
                 rows.get(start + dt.timedelta(days=i), 0)) for i in range(n)]

    def accuracy_by_lesson(self) -> dict[str, float]:
        with self.Session() as s:
            return {p.lesson_id: p.best_score_pct
                    for p in s.scalars(select(LessonProgress)).all()}

    # ------------------------------------------------------------ settings
    def get_setting(self, key: str, default: str = "") -> str:
        with self.Session() as s:
            row = s.scalar(select(Setting).where(Setting.key == key))
            return row.value if row else default

    def set_setting(self, key: str, value: str):
        with self.Session() as s:
            row = s.scalar(select(Setting).where(Setting.key == key))
            if not row:
                row = Setting(key=key)
                s.add(row)
            row.value = str(value)
            s.commit()

    # ------------------------------------------------------------ export / import
    def export_progress(self, path=None) -> str:
        """Dump user progress to a JSON file. Returns the file path."""
        path = path or (config.EXPORTS_DIR /
                        f"linguabridge_export_{dt.date.today()}.json")
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            data = {
                "version": config.APP_VERSION,
                "exported": dt.datetime.utcnow().isoformat(),
                "user": {"name": user.name, "total_xp": user.total_xp,
                         "streak": user.streak, "best_streak": user.best_streak,
                         "last_active_date": str(user.last_active_date or ""),
                         "speaking_passes": user.speaking_passes,
                         "srs_reviews_done": user.srs_reviews_done},
                "lessons": [{"lesson_id": p.lesson_id, "completed": p.completed,
                             "best_score_pct": p.best_score_pct,
                             "times_completed": p.times_completed}
                            for p in s.scalars(select(LessonProgress)).all()],
                "vocab": [{"vocab_key": v.vocab_key, "ease": v.ease,
                           "interval_days": v.interval_days,
                           "repetitions": v.repetitions,
                           "due_date": str(v.due_date), "lapses": v.lapses}
                          for v in s.scalars(select(VocabSRS)).all()],
                "badges": sorted(self.unlocked_badges()),
                "daily_stats": [{"day": str(d.day), "xp": d.xp,
                                 "exercises_done": d.exercises_done,
                                 "correct": d.correct}
                                for d in s.scalars(select(DailyStat)).all()],
                "settings": {r.key: r.value
                             for r in s.scalars(select(Setting)).all()},
            }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(path)

    def import_progress(self, path: str) -> bool:
        """Merge a previously exported JSON file back into the database."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        with self.Session() as s:
            user = s.scalar(select(User).limit(1))
            u = data.get("user", {})
            user.name = u.get("name", user.name)
            user.total_xp = max(user.total_xp, int(u.get("total_xp", 0)))
            user.streak = max(user.streak, int(u.get("streak", 0)))
            user.best_streak = max(user.best_streak, int(u.get("best_streak", 0)))
            user.speaking_passes = max(user.speaking_passes,
                                       int(u.get("speaking_passes", 0)))
            user.srs_reviews_done = max(user.srs_reviews_done,
                                        int(u.get("srs_reviews_done", 0)))
            if u.get("last_active_date"):
                try:
                    user.last_active_date = dt.date.fromisoformat(
                        u["last_active_date"])
                except ValueError:
                    pass
            for lp in data.get("lessons", []):
                row = s.scalar(select(LessonProgress).where(
                    LessonProgress.lesson_id == lp["lesson_id"]))
                if not row:
                    row = LessonProgress(lesson_id=lp["lesson_id"],
                                         completed=False, best_score_pct=0.0,
                                         times_completed=0)
                    s.add(row)
                row.completed = row.completed or lp.get("completed", False)
                row.best_score_pct = max(row.best_score_pct or 0,
                                         lp.get("best_score_pct", 0))
                row.times_completed = max(row.times_completed or 0,
                                          lp.get("times_completed", 0))
            for v in data.get("vocab", []):
                row = s.scalar(select(VocabSRS).where(
                    VocabSRS.vocab_key == v["vocab_key"]))
                if row:
                    row.ease = v.get("ease", row.ease)
                    row.interval_days = v.get("interval_days", row.interval_days)
                    row.repetitions = v.get("repetitions", row.repetitions)
                    row.lapses = v.get("lapses", row.lapses)
                    try:
                        row.due_date = dt.date.fromisoformat(v["due_date"])
                    except (KeyError, ValueError):
                        pass
            for day in data.get("daily_stats", []):
                try:
                    d = dt.date.fromisoformat(day["day"])
                except (KeyError, ValueError):
                    continue
                row = s.scalar(select(DailyStat).where(DailyStat.day == d))
                if not row:
                    s.add(DailyStat(day=d, xp=day.get("xp", 0),
                                    exercises_done=day.get("exercises_done", 0),
                                    correct=day.get("correct", 0)))
            for key, val in data.get("settings", {}).items():
                self_row = s.scalar(select(Setting).where(Setting.key == key))
                if self_row:
                    self_row.value = val
                else:
                    s.add(Setting(key=key, value=val))
            s.commit()
        for b in data.get("badges", []):
            self.unlock_badge(b)
        return True
