"""Creditors (Sundry Creditors + custom liability groups) — derived from `all_ledgers`.

Background: Some Tally tenants don't actually use the reserved "Sundry Creditors"
group. They organise vendors/distributors/dealer-deposits under custom primary
or secondary groups (e.g. `Dealer Deposit`, `Unsecured Loans`, `MP Distributor`
when those are vendor groups). The desktop agent walker only matches the
reserved name, so creditors come back as 0 for these tenants.

This module derives a per-tenant creditor list LIVE from `all_ledgers` against
a configurable list of group names — no agent re-sync needed. The list of
"creditor groups" is editable per tenant via /api/creditors/config.

Defaults: Sundry Creditors, Dealer Deposit, Unsecured Loans, Non Current Liability.
"""
from fastapi import APIRouter, Request
from typing import List, Optional
import logging

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()

# Sensible defaults — covers the reserved Tally group plus the most common
# custom liability buckets observed across tenants.
DEFAULT_CREDITOR_GROUPS = [
    "Sundry Creditors",
    "Dealer Deposit",
    "Unsecured Loans",
    "Non Current Liability",
]


def _build_q(ctx, extra: Optional[dict] = None) -> dict:
    q = {}
    if ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    if ctx.get("company_id"):
        q["company_id"] = ctx["company_id"]
    if extra:
        q.update(extra)
    return q


async def _get_creditor_groups(tenant_id: str) -> List[str]:
    """Per-tenant configurable list. Falls back to defaults."""
    cfg = await db.tenant_settings.find_one(
        {"tenant_id": tenant_id, "key": "creditor_groups"}, {"_id": 0}
    )
    groups = cfg.get("value") if cfg else None
    if not groups or not isinstance(groups, list):
        return list(DEFAULT_CREDITOR_GROUPS)
    return groups


# ───────────────────────────────────────────────────────────────────
@router.get("/creditors")
async def list_creditors(request: Request):
    """Live-derived creditors from `all_ledgers` for this tenant/company.

    Sign convention (owner-cash perspective):
      Tally stores liability CR balance as positive (= you owe).
      We flip the sign so positive = you owe (intuitive on the reports).
      Wait — keep the user's expectation: outstanding_amount > 0 = "we owe".
      That matches Tally's positive sign already, so we keep raw value.
    """
    user = await get_current_user(request, db)
    if not user:
        return APIResponse(success=False, error="Authentication required")
    ctx = await get_tenant_context(request)
    q = _build_q(ctx)

    creditor_groups = await _get_creditor_groups(ctx.get("tenant_id", ""))

    rows = await db.all_ledgers.find(
        {**q, "parent_group": {"$in": creditor_groups}},
        {"_id": 0, "ledger_name": 1, "name": 1, "parent_group": 1, "closing_balance": 1, "opening_balance": 1,
         "phone": 1, "contact_person": 1, "state": 1},
    ).to_list(5000)

    # Cross-check: anything already in `customers` (debtor) should not appear here
    cust_names = set()
    async for c in db.customers.find(q, {"_id": 0, "customer_name": 1}):
        n = (c.get("customer_name") or "").strip().lower()
        if n:
            cust_names.add(n)

    creditors = []
    for r in rows:
        name = (r.get("ledger_name") or r.get("name") or "").strip()
        if not name or name.lower() in cust_names:
            continue
        creditors.append({
            "creditor_name": name,
            "ledger_group": r.get("parent_group", ""),
            "outstanding_amount": float(r.get("closing_balance", 0) or 0),
            "opening_balance": float(r.get("opening_balance", 0) or 0),
            "phone": (r.get("phone") or "").strip(),
            "contact_person": (r.get("contact_person") or "").strip(),
            "state": (r.get("state") or "").strip(),
        })

    creditors.sort(key=lambda c: abs(c["outstanding_amount"]), reverse=True)

    return APIResponse(success=True, data={
        "creditors": creditors,
        "count": len(creditors),
        "creditor_groups": creditor_groups,
        "total_outstanding": round(sum(c["outstanding_amount"] for c in creditors), 2),
    })


@router.get("/creditors/config")
async def get_creditor_config(request: Request):
    """Return current creditor-group list + every parent_group seen in
    all_ledgers (for the admin UI to pick from)."""
    user = await get_current_user(request, db)
    if not user or user.get("role") not in ("admin", "super_admin"):
        return APIResponse(success=False, error="Admin access required")
    ctx = await get_tenant_context(request)
    q = _build_q(ctx)
    creditor_groups = await _get_creditor_groups(ctx.get("tenant_id", ""))
    available = await db.all_ledgers.distinct("parent_group", q)
    available = sorted([g for g in available if g], key=str.lower)
    return APIResponse(success=True, data={
        "creditor_groups": creditor_groups,
        "available_groups": available,
        "defaults": list(DEFAULT_CREDITOR_GROUPS),
    })


@router.post("/creditors/config")
async def set_creditor_config(request: Request):
    """Save the per-tenant creditor-group list."""
    user = await get_current_user(request, db)
    if not user or user.get("role") not in ("admin", "super_admin"):
        return APIResponse(success=False, error="Admin access required")
    body = await request.json()
    groups = body.get("creditor_groups") or []
    if not isinstance(groups, list):
        return APIResponse(success=False, error="creditor_groups must be a list")
    groups = [str(g).strip() for g in groups if str(g).strip()]
    ctx = await get_tenant_context(request)
    tenant_id = ctx.get("tenant_id", "")
    await db.tenant_settings.update_one(
        {"tenant_id": tenant_id, "key": "creditor_groups"},
        {"$set": {"value": groups, "tenant_id": tenant_id, "key": "creditor_groups"}},
        upsert=True,
    )
    return APIResponse(success=True, message=f"Saved {len(groups)} creditor groups",
                       data={"creditor_groups": groups})
