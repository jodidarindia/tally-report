"""Audit log routes — view activity logs for Super Admin and Admin."""
from fastapi import APIRouter, Request
from typing import Optional
import logging

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/audit/logs")
async def get_audit_logs(
    request: Request,
    limit: int = 100,
    action: Optional[str] = None,
    actor: Optional[str] = None,
):
    """Get audit logs. Super admin sees all; admin sees own tenant only."""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = {}
        if user.get("role") == "super_admin":
            pass  # super admin sees all
        elif user.get("role") == "admin":
            q["tenant_id"] = user.get("tenant_id", "")
        else:
            q["tenant_id"] = user.get("tenant_id", "")

        if action:
            q["action"] = action
        if actor:
            q["actor"] = actor

        logs = await db.audit_logs.find(q, {"_id": 0}).sort("timestamp", -1).to_list(limit)
        return APIResponse(success=True, data={"logs": logs, "count": len(logs)})
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/audit/actions")
async def get_audit_action_types(request: Request):
    """Get distinct action types for filter dropdown."""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = {}
        if user.get("role") != "super_admin":
            q["tenant_id"] = user.get("tenant_id", "")

        actions = await db.audit_logs.distinct("action", q)
        return APIResponse(success=True, data={"actions": sorted(actions)})
    except Exception as e:
        return APIResponse(success=False, error=str(e))
