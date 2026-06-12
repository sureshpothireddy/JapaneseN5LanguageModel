"""
database/models.py — SQLAlchemy ORM models.

Tables
------
User            learner profile + aggregate stats (XP, streak, hearts, league)
LessonProgress  per-lesson completion state and best score
VocabSRS        spaced-repetition state for each vocabulary item (SM-2)
Mistake         queue of wrongly answered exercises for review
Badge           unlocked achievements
DailyStat       XP earned per calendar day (streak + charts)
Setting         simple key/value app settings
"""

import datetime as dt

from sqlalchemy import (Column, Integer, String, Float, Date, DateTime,
                        Boolean, Text, UniqueConstraint)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), default="Learner")
    total_xp = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    best_streak = Column(Integer, default=0)
    last_active_date = Column(Date, nullable=True)
    hearts = Column(Integer, default=5)
    hearts_updated_at = Column(DateTime, default=utcnow)
    speaking_passes = Column(Integer, default=0)
    srs_reviews_done = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("lesson_id", name="uq_lesson"),)

    id = Column(Integer, primary_key=True)
    lesson_id = Column(String(64), nullable=False)
    completed = Column(Boolean, default=False)
    best_score_pct = Column(Float, default=0.0)     # best accuracy %
    times_completed = Column(Integer, default=0)
    last_completed_at = Column(DateTime, nullable=True)


class VocabSRS(Base):
    __tablename__ = "vocab_srs"
    __table_args__ = (UniqueConstraint("vocab_key", name="uq_vocab"),)

    id = Column(Integer, primary_key=True)
    vocab_key = Column(String(128), nullable=False)  # "<lesson_id>:<ja>"
    lesson_id = Column(String(64), nullable=False)
    ja = Column(String(128), nullable=False)
    reading = Column(String(128), default="")
    romaji = Column(String(128), default="")
    en = Column(String(256), nullable=False)
    example_ja = Column(String(256), default="")
    example_en = Column(String(256), default="")
    # SM-2 state
    ease = Column(Float, default=2.5)
    interval_days = Column(Float, default=0.0)
    repetitions = Column(Integer, default=0)
    due_date = Column(Date, default=dt.date.today)
    lapses = Column(Integer, default=0)
    last_reviewed = Column(DateTime, nullable=True)


class Mistake(Base):
    __tablename__ = "mistakes"

    id = Column(Integer, primary_key=True)
    lesson_id = Column(String(64), nullable=False)
    exercise_json = Column(Text, nullable=False)     # serialized exercise dict
    user_answer = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    resolved = Column(Boolean, default=False)        # cleared after correct review


class BadgeUnlock(Base):
    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("badge_id", name="uq_badge"),)

    id = Column(Integer, primary_key=True)
    badge_id = Column(String(64), nullable=False)
    unlocked_at = Column(DateTime, default=utcnow)


class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("day", name="uq_day"),)

    id = Column(Integer, primary_key=True)
    day = Column(Date, nullable=False)
    xp = Column(Integer, default=0)
    exercises_done = Column(Integer, default=0)
    correct = Column(Integer, default=0)


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("key", name="uq_key"),)

    id = Column(Integer, primary_key=True)
    key = Column(String(64), nullable=False)
    value = Column(String(256), default="")
