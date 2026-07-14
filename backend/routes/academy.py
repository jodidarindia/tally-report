"""
FLOWRA Academy — per-user lesson progress tracking.

Tracks watch progress per (user_id, lesson_n). A lesson is considered
COMPLETED when watched ≥60% (client sends `progress_pct` on `timeupdate`).

Endpoints (all under /api prefix):
  POST /api/academy/progress   — upsert progress for the current user
      body: { lesson: int, progress_pct: float (0..100) }
  GET  /api/academy/progress   — list all completed lessons for current user
      resp: { lessons: [{n, completed, progress_pct, completed_at}] }
"""
from fastapi import APIRouter, Request
from datetime import datetime, timezone
import logging

from db import db
from models import APIResponse
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION = "academy_progress"
COMPLETION_THRESHOLD_PCT = 60.0


@router.post("/academy/progress")
async def upsert_progress(request: Request):
    """Client sends { lesson, progress_pct } every ~5 seconds while the
    audio/video plays. We keep only the MAX watched % (so scrubbing
    backwards doesn't un-complete a lesson)."""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Unauthorized")

        body = await request.json()
        lesson_n = int(body.get("lesson", 0))
        pct = float(body.get("progress_pct", 0))
        if lesson_n < 1 or lesson_n > 30:
            return APIResponse(success=False, error="Invalid lesson number")
        pct = max(0.0, min(100.0, pct))

        user_id = str(user.get("id") or user.get("_id") or user.get("username"))
        now = datetime.now(timezone.utc).isoformat()
        key = {"user_id": user_id, "lesson": lesson_n}

        existing = await db[COLLECTION].find_one(key, {"_id": 0})
        best_pct = max(pct, (existing or {}).get("progress_pct", 0))
        completed = best_pct >= COMPLETION_THRESHOLD_PCT
        # Preserve the FIRST completion timestamp so the green tick has a
        # stable "completed_at" for future analytics.
        completed_at = (existing or {}).get("completed_at")
        if completed and not completed_at:
            completed_at = now

        doc = {
            **key,
            "progress_pct": round(best_pct, 1),
            "completed": completed,
            "completed_at": completed_at,
            "last_seen_at": now,
        }
        await db[COLLECTION].update_one(key, {"$set": doc}, upsert=True)
        return APIResponse(success=True, data={
            "lesson": lesson_n,
            "progress_pct": doc["progress_pct"],
            "completed": completed,
            "completed_at": completed_at,
        })
    except Exception as e:
        logger.error(f"upsert academy progress failed: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/academy/progress")
async def list_progress(request: Request):
    """Return { lessons: [{n, completed, progress_pct, completed_at}] }."""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Unauthorized")
        user_id = str(user.get("id") or user.get("_id") or user.get("username"))
        rows = await db[COLLECTION].find({"user_id": user_id}, {"_id": 0}).to_list(100)
        out = [
            {
                "n": r["lesson"],
                "completed": bool(r.get("completed")),
                "progress_pct": r.get("progress_pct", 0),
                "completed_at": r.get("completed_at"),
            }
            for r in rows
        ]
        # Total completed for the badge on the Academy hero
        completed_count = sum(1 for r in out if r["completed"])
        return APIResponse(success=True, data={
            "lessons": out,
            "completed_count": completed_count,
            "threshold_pct": COMPLETION_THRESHOLD_PCT,
        })
    except Exception as e:
        logger.error(f"list academy progress failed: {e}")
        return APIResponse(success=False, error=str(e))
