"""
core/srs.py — Anki-style spaced repetition (SM-2 variant).

Pure functions: take current card state + answer quality, return new state.
Quality scale (mapped from exercise results):
    0–2  fail  (card lapses, interval resets)
    3    hard / barely correct
    4    good
    5    easy / instant correct
"""

import datetime as dt
from dataclasses import dataclass

import config


@dataclass
class SRSResult:
    ease: float
    interval_days: float
    repetitions: int
    due_date: dt.date
    lapsed: bool


def review(quality: int, ease: float, interval_days: float,
           repetitions: int, today: dt.date | None = None) -> SRSResult:
    """Apply one review with SM-2 scheduling."""
    today = today or dt.date.today()
    quality = max(0, min(5, int(quality)))

    if quality < 3:                                   # ----- lapse
        new_ease = max(config.SRS_MIN_EASE, ease - 0.20)
        return SRSResult(ease=new_ease, interval_days=0, repetitions=0,
                         due_date=today + dt.timedelta(days=1), lapsed=True)

    # ----- success: update ease (SM-2 formula), then grow interval
    new_ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease = max(config.SRS_MIN_EASE, new_ease)

    reps = repetitions + 1
    if reps == 1:
        interval = config.SRS_FIRST_INTERVAL_DAYS
    elif reps == 2:
        interval = config.SRS_SECOND_INTERVAL_DAYS
    else:
        interval = interval_days * new_ease
    interval = min(config.SRS_MAX_INTERVAL_DAYS, max(1, round(interval, 1)))

    return SRSResult(ease=round(new_ease, 3), interval_days=interval,
                     repetitions=reps,
                     due_date=today + dt.timedelta(days=int(interval)),
                     lapsed=False)


def quality_from_answer(correct: bool, similarity: float | None = None,
                        hesitated: bool = False) -> int:
    """Map an exercise outcome to an SM-2 quality grade."""
    if not correct:
        return 1
    if similarity is not None and similarity < 90:
        return 3
    return 3 if hesitated else 4
