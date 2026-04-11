from fastapi import APIRouter, Request
from typing import Optional
import logging

from db import db
from models import APIResponse
from utils import safe_num, compute_overdue_digest, filter_vouchers_by_fy
from services.tenant_context import get_tenant_context
from routes.branch_ledgers import get_branch_parties

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_query(ctx, company_id=None, extra=None):
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    cid = company_id or (ctx.get("company_id") if ctx else None)
    if cid:
        q["company_id"] = cid
    if extra:
        q.update(extra)
    return q


@router.get("/dashboard/overdue-digest")
async def get_overdue_digest(request: Request, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        tid = ctx.get("tenant_id") if ctx else None
        cid = company_id or (ctx.get("company_id") if ctx else None)

        # Get branch parties if exclusion header is set
        bp = []
        if request.headers.get("X-Exclude-Branches", "").lower() == "true":
            bp = await get_branch_parties(tid or "", cid or "")

        # When branch exclusion is active, always compute fresh (don't use cached)
        if bp:
            digest = await compute_overdue_digest(db, tid, cid, branch_parties=bp)
        else:
            q = {"_type": "latest"}
            if tid:
                q["tenant_id"] = tid
            if cid:
                q["company_id"] = cid
            digest = await db.overdue_digest.find_one(q, {"_id": 0})
            if not digest:
                digest = await compute_overdue_digest(db, tid, cid)

        return APIResponse(success=True, data=digest)
    except Exception as e:
        logger.error(f"Error getting overdue digest: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/dashboard/top-customers")
async def get_top_customers(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        vouchers = filter_vouchers_by_fy(vouchers, fy) if fy else vouchers

        # Apply branch exclusion
        if request.headers.get("X-Exclude-Branches", "").lower() == "true":
            bp = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
            if bp:
                vouchers = [v for v in vouchers if v.get("party_name") not in bp]

        customer_sales = {}
        for v in vouchers:
            party = v.get("party_name", "Unknown")
            customer_sales[party] = customer_sales.get(party, 0) + safe_num(v.get("total_amount"))

        top = sorted(
            [{"name": k, "total": round(v, 2)} for k, v in customer_sales.items()],
            key=lambda x: x["total"],
            reverse=True
        )[:10]

        return APIResponse(success=True, data={"customers": top})
    except Exception as e:
        logger.error(f"Error getting top customers: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/dashboard/reminders")
async def get_reminders(request: Request, company_id: Optional[str] = None):
    try:
        from datetime import datetime, timezone, timedelta
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id, {"status": "pending"})
        next_week = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()

        followups = await db.customer_followups.find(
            {**q, "followup_date": {"$lte": next_week}},
            {"_id": 0}
        ).sort("followup_date", 1).to_list(50)

        return APIResponse(success=True, data={"reminders": followups, "count": len(followups)})
    except Exception as e:
        logger.error(f"Error getting reminders: {e}")
        return APIResponse(success=False, error=str(e))
