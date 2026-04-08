from fastapi import APIRouter
from typing import Optional
from datetime import datetime, timezone
import logging

from db import db
from models import APIResponse
from utils import safe_num, compute_overdue_digest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard/reminders")
async def get_dashboard_reminders():
    try:
        followups = await db.customer_followups.find(
            {"status": "pending"},
            {"_id": 0}
        ).sort("followup_date", 1).to_list(50)

        overdue = []
        today_list = []
        upcoming = []
        now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for f in followups:
            f_date = f.get("followup_date", "")[:10]
            if f_date < now_date:
                f["reminder_type"] = "overdue"
                overdue.append(f)
            elif f_date == now_date:
                f["reminder_type"] = "today"
                today_list.append(f)
            else:
                f["reminder_type"] = "upcoming"
                upcoming.append(f)

        return APIResponse(
            success=True,
            data={
                "overdue": overdue,
                "today": today_list,
                "upcoming": upcoming[:5],
                "total_pending": len(followups),
                "overdue_count": len(overdue),
                "today_count": len(today_list)
            }
        )
    except Exception as e:
        logger.error(f"Error fetching reminders: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/dashboard/overdue-digest")
async def get_overdue_digest(recompute: Optional[str] = None):
    try:
        if recompute == "true":
            digest = await compute_overdue_digest(db)
            return APIResponse(success=True, data=digest)

        cached = await db.overdue_digest.find_one({"_type": "latest"}, {"_id": 0, "_type": 0})
        if cached:
            return APIResponse(success=True, data=cached)

        digest = await compute_overdue_digest(db)
        return APIResponse(success=True, data=digest)

    except Exception as e:
        logger.error(f"Error fetching overdue digest: {e}")
        return APIResponse(success=False, error=str(e))
