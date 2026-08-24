"""Remarks / notes with tags and history for Prospects and Leads.

Any authenticated SuperAdmin or FLOWRA staff member can attach a
timestamped remark (optionally tagged) to a prospect or questionnaire
lead. All remarks are append-only — staff cannot edit or delete a peer's
remark, preserving the audit trail the user asked for
(msg 828, item #5: "keep a history and track of all remarks added by
staff and superadmin").

Collections:
- `remarks`: { remark_id, target_type ('prospect'|'lead'), target_id,
              text, tag, author_username, author_name, author_role,
              created_at }
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from db import db
from models import APIResponse
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


REMARK_TAGS = [
    "Follow-up", "Callback", "Objection",
    "Positive", "Negative", "Info-Only",
]


async def _require_staff(request: Request):
    user = await get_current_user(request, db)
    if not user:
        return None
    if user.get("role") not in ("super_admin", "flowra_staff"):
        return None
    return user


async def _resolve_target(target_type: str, target_id: str) -> bool:
    if target_type == "prospect":
        return bool(await db.prospects.find_one({"prospect_id": target_id}, {"_id": 1}))
    if target_type == "lead":
        # Questionnaire submissions don't have their own id field — we
        # index them by submitted_at (ISO timestamp) which is what the
        # SuperAdmin UI already uses as the row key.
        return bool(await db.questionnaires.find_one({"submitted_at": target_id}, {"_id": 1}))
    return False


@router.get("/super-admin/remarks/{target_type}/{target_id}")
async def list_remarks(target_type: str, target_id: str, request: Request):
    user = await _require_staff(request)
    if not user:
        return APIResponse(success=False, error="Forbidden")
    if target_type not in ("prospect", "lead"):
        return APIResponse(success=False, error="target_type must be 'prospect' or 'lead'")
    remarks = await db.remarks.find(
        {"target_type": target_type, "target_id": target_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    return APIResponse(success=True, data={
        "remarks": remarks,
        "tags": REMARK_TAGS,
        "count": len(remarks),
    })


@router.post("/super-admin/remarks/{target_type}/{target_id}")
async def add_remark(target_type: str, target_id: str, request: Request):
    user = await _require_staff(request)
    if not user:
        return APIResponse(success=False, error="Forbidden")
    if target_type not in ("prospect", "lead"):
        return APIResponse(success=False, error="target_type must be 'prospect' or 'lead'")
    if not await _resolve_target(target_type, target_id):
        return APIResponse(success=False, error=f"{target_type} not found")

    body = await request.json()
    text = (body.get("text") or "").strip()
    tag = (body.get("tag") or "").strip()
    if not text:
        return APIResponse(success=False, error="Remark text is required")
    if tag and tag not in REMARK_TAGS:
        return APIResponse(success=False, error=f"Unknown tag. Pick one of: {', '.join(REMARK_TAGS)}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "remark_id":       f"REM-{uuid.uuid4().hex[:8].upper()}",
        "target_type":     target_type,
        "target_id":       target_id,
        "text":            text[:2000],
        "tag":             tag or "",
        "author_username": user.get("username"),
        "author_name":     user.get("name") or user.get("username"),
        "author_role":     user.get("role"),
        "created_at":      now,
    }
    await db.remarks.insert_one(doc)
    return APIResponse(success=True, data={
        "remark_id": doc["remark_id"],
        "created_at": now,
    }, message="Remark added")
