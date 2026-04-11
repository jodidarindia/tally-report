"""Branch ledger detection and management for filtering inter-branch transfers."""
from fastapi import APIRouter, Request
import logging
import re

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context
from services.id_mapping_service import get_company_name

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_branch_parties(tenant_id: str, company_id: str) -> list:
    """Get the list of branch party names for a tenant+company. Returns empty list if none set."""
    doc = await db.branch_ledgers.find_one(
        {"tenant_id": tenant_id, "company_id": company_id},
        {"_id": 0, "party_names": 1}
    )
    return doc.get("party_names", []) if doc else []


async def detect_branch_parties(tenant_id: str, company_id: str) -> list:
    """Auto-detect branch/division parties by matching company name in party names."""
    company_name = await get_company_name(tenant_id, company_id)
    if not company_name:
        return []

    # Build matching tokens from company name (remove common suffixes)
    name_clean = re.sub(r'\b(private|limited|pvt|ltd|llp|inc|corp)\b', '', company_name, flags=re.IGNORECASE).strip()
    # Take significant words (>3 chars)
    tokens = [w.lower() for w in name_clean.split() if len(w) > 3]
    if not tokens:
        return []

    # Get all distinct party names from sales vouchers
    parties = await db.sales_vouchers.distinct(
        "party_name",
        {"tenant_id": tenant_id, "company_id": company_id}
    )

    branch_parties = []
    for party in parties:
        if not party:
            continue
        party_lower = party.lower()
        # Check if enough company name tokens match (at least 2 significant words)
        matching_tokens = sum(1 for t in tokens if t in party_lower)
        if matching_tokens >= 2:
            branch_parties.append(party)

    return branch_parties


@router.get("/settings/branch-ledgers")
async def get_branch_ledgers(request: Request):
    """Get branch ledger settings for the current company."""
    try:
        ctx = await get_tenant_context(request)
        tenant_id = ctx.get("tenant_id", "")
        company_id = ctx.get("company_id", "")

        parties = await get_branch_parties(tenant_id, company_id)
        return APIResponse(success=True, data={"party_names": parties, "count": len(parties)})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/settings/branch-ledgers")
async def set_branch_ledgers(request: Request):
    """Set branch ledger party names for the current company."""
    try:
        ctx = await get_tenant_context(request)
        tenant_id = ctx.get("tenant_id", "")
        company_id = ctx.get("company_id", "")

        body = await request.json()
        party_names = body.get("party_names", [])

        await db.branch_ledgers.update_one(
            {"tenant_id": tenant_id, "company_id": company_id},
            {"$set": {"tenant_id": tenant_id, "company_id": company_id, "party_names": party_names}},
            upsert=True
        )

        return APIResponse(success=True, message=f"{len(party_names)} branch ledger(s) saved")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/settings/branch-ledgers/detect")
async def detect_branch_ledgers(request: Request):
    """Auto-detect branch/division parties based on company name matching."""
    try:
        ctx = await get_tenant_context(request)
        tenant_id = ctx.get("tenant_id", "")
        company_id = ctx.get("company_id", "")

        detected = await detect_branch_parties(tenant_id, company_id)

        # Auto-save if detected and none already set
        existing = await get_branch_parties(tenant_id, company_id)
        if detected and not existing:
            await db.branch_ledgers.update_one(
                {"tenant_id": tenant_id, "company_id": company_id},
                {"$set": {"tenant_id": tenant_id, "company_id": company_id, "party_names": detected}},
                upsert=True
            )

        return APIResponse(success=True, data={"detected": detected, "count": len(detected), "auto_saved": not existing and len(detected) > 0})
    except Exception as e:
        return APIResponse(success=False, error=str(e))
