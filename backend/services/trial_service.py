"""14-day Free Trial lifecycle helpers.

Trial user schema additions (stored on the `users` doc):
- is_trial:     bool. Set on create when plan == "trial".
- trial_start:  ISO 8601 UTC string. Day 1 of the trial.
- trial_end:    ISO 8601 UTC string. First moment the account is locked.
- trial_reminders_sent: list[int]. Days (5, 8, 12, 14) that already got an
                        email so we never spam the same day twice.
- converted_at: ISO 8601 UTC. Set when a super-admin flips them to a paid plan.

Reminder cadence — each mail has a distinctly different subject and body:
- Day 5:  "How's it going? Here's what to explore next"     (curiosity / education)
- Day 8:  "You're past the halfway mark of your FLOWRA trial" (progress-nudge / social proof)
- Day 12: "48 hours left — lock in your discount"           (loss aversion / anchor)
- Day 14: "Final call — your FLOWRA trial ends tonight"     (urgency / clear CTA)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from db import db

logger = logging.getLogger(__name__)

REMINDER_DAYS = [5, 8, 12, 14]
TRIAL_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc)


def compute_trial_window(started_at: Optional[datetime] = None) -> tuple[str, str]:
    """Return (trial_start_iso, trial_end_iso). End = start + 14 days."""
    start = started_at or _now()
    end = start + timedelta(days=TRIAL_DAYS)
    return start.isoformat(), end.isoformat()


def parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def trial_days_remaining(user: dict) -> Optional[int]:
    """Return days remaining (>=0) or None if not a trial user.
    Returns 0 for the expiry day and negative-ish? — we clamp at 0."""
    if not user.get("is_trial"):
        return None
    end = parse_iso(user.get("trial_end", ""))
    if not end:
        return None
    delta = end - _now()
    return max(0, delta.days + (1 if delta.seconds > 0 else 0))


def is_trial_expired(user: dict) -> bool:
    """True iff this user is a trial and now >= trial_end. Non-trial
    users always return False."""
    if not user.get("is_trial"):
        return False
    if user.get("converted_at"):
        # They upgraded → treat as regular paid customer
        return False
    end = parse_iso(user.get("trial_end", ""))
    if not end:
        return False
    return _now() >= end


def _reminder_day_for(user: dict) -> Optional[int]:
    """Return the REMINDER_DAYS bucket the user hits TODAY (in UTC), or None."""
    start = parse_iso(user.get("trial_start", ""))
    if not start:
        return None
    now = _now()
    # Whole days elapsed since trial start
    elapsed = (now.date() - start.date()).days
    if elapsed in REMINDER_DAYS:
        return elapsed
    return None


async def get_users_due_for_reminder() -> list[tuple[dict, int]]:
    """Scan active trials and return [(user, day)] for those that hit
    a reminder milestone today AND haven't been mailed for that day."""
    cursor = db.users.find({
        "role": "admin",
        "is_trial": True,
        "active": True,
        "converted_at": {"$in": [None, ""]},
    }, {"_id": 0, "password_hash": 0})
    out = []
    async for u in cursor:
        day = _reminder_day_for(u)
        if day is None:
            continue
        sent = set(u.get("trial_reminders_sent", []) or [])
        if day in sent:
            continue
        out.append((u, day))
    return out


async def mark_reminder_sent(username: str, day: int) -> None:
    await db.users.update_one(
        {"username": username, "role": "admin"},
        {"$addToSet": {"trial_reminders_sent": day}},
    )


async def get_users_to_lock() -> list[dict]:
    """Trials whose end has passed AND still have active=True. Used by
    the nightly cron to flip active→False and send the final expiry mail
    (which we do inline with the day-14 reminder already)."""
    cursor = db.users.find({
        "role": "admin",
        "is_trial": True,
        "active": True,
        "converted_at": {"$in": [None, ""]},
    }, {"_id": 0, "password_hash": 0})
    out = []
    async for u in cursor:
        if is_trial_expired(u):
            out.append(u)
    return out
