"""
Tally Company Binding — iter-168.

Problem
-------
A single Tally instance (port 9000) can have MULTIPLE companies loaded
concurrently. Any XML request that omits `<SVCURRENTCOMPANY>` returns
merged data from ALL loaded companies. Even with SVCURRENTCOMPANY, an
operator on the shop-floor computer could accidentally re-bind the
agent to a DIFFERENT Tally company (e.g. a sister-concern's books)
and pour those vouchers into the wrong FLOWRA tenant.

Solution
--------
"Trust-on-first-use" (TOFU) binding — per useradmin, exactly one Tally
company (identified by Tally's internal $Guid). The agent captures the
GUID + display name on first sync and calls `/api/agent/tally-binding/bind`.
Once stored, every subsequent sync MUST carry the identical GUID — a
mismatch is HARD-BLOCKED at the sync endpoint (returns 409 CONFLICT).

The useradmin can UNBIND from the FLOWRA Settings → Integrations page.
Unbinding clears the binding but leaves the synced data intact so the
admin can re-bind (perhaps to the correct company) without data loss.

Endpoints
---------
POST /api/agent/tally-binding/bind         — agent-side (sync_token auth)
GET  /api/settings/tally-binding           — useradmin (JWT auth)
DELETE /api/settings/tally-binding         — useradmin (JWT auth)

Storage
-------
Collection `tally_bindings` — one document per (tenant_id, company_id):
  {
    tenant_id, company_id,
    tally_company_name, tally_company_guid,
    bound_at, bound_by (username), last_seen_at,
  }
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException

from db import db
from models import APIResponse
from services.auth_service import verify_sync_token, get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────
def _norm_guid(v: str) -> str:
    """Tally GUIDs come back like `f2e8c4a1-1234-...-#####` or with braces.
    Normalise to a case-insensitive lookup key: strip whitespace, remove
    surrounding `{}`, lowercase."""
    if not v:
        return ""
    s = str(v).strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    return s.lower()


async def get_binding(tenant_id: str, company_id: str) -> dict | None:
    """Fetch the binding doc for a (tenant, company). Returns None if unbound."""
    if not tenant_id or not company_id:
        return None
    return await db.tally_bindings.find_one(
        {"tenant_id": tenant_id, "company_id": company_id},
        {"_id": 0},
    )


async def touch_last_seen(tenant_id: str, company_id: str) -> None:
    """Update `last_seen_at` on every successful sync so the settings
    page can show 'Last synced X mins ago'."""
    try:
        await db.tally_bindings.update_one(
            {"tenant_id": tenant_id, "company_id": company_id},
            {"$set": {"last_seen_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.debug(f"touch_last_seen failed silently: {e}")


async def validate_sync_binding(
    tenant_id: str,
    company_id: str,
    payload_guid: str,
    payload_name: str,
) -> tuple[bool, str]:
    """Called from sync.py for every /agent/sync request.

    Return (ok, error_msg).
      - No binding + payload has GUID  → auto-bind (TOFU) and accept.
      - No binding + no payload GUID   → legacy agent, accept (soft-warn).
      - Binding exists + GUID matches  → accept, update last_seen_at.
      - Binding exists + GUID mismatch → REJECT (409-like).
      - Binding exists + payload GUID missing → REJECT (agent must upgrade).
    """
    binding = await get_binding(tenant_id, company_id)
    incoming = _norm_guid(payload_guid)

    if not binding:
        # First-ever sync for this (tenant, company). Auto-bind if the
        # agent supplied a GUID; otherwise let the legacy agent through
        # so no existing customer is broken by the upgrade.
        if incoming:
            await db.tally_bindings.insert_one({
                "tenant_id": tenant_id,
                "company_id": company_id,
                "tally_company_name": (payload_name or "").strip(),
                "tally_company_guid": incoming,
                "bound_at": datetime.now(timezone.utc).isoformat(),
                "bound_by": "agent-tofu",
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(
                f"TOFU bind: tenant={tenant_id} company={company_id} "
                f"guid={incoming} name='{payload_name}'"
            )
        return True, ""

    # Binding exists — must match GUID.
    bound_guid = _norm_guid(binding.get("tally_company_guid", ""))
    if not incoming:
        return False, (
            "Your Tally Agent is not sending the company GUID. Please "
            "update to Tally Agent v9.8.32 or newer so multi-company "
            "safety can validate the sync."
        )
    if incoming != bound_guid:
        return False, (
            f"Tally company GUID mismatch. This FLOWRA tenant is bound "
            f"to '{binding.get('tally_company_name')}' (guid ending "
            f"…{bound_guid[-6:]}). The current sync payload reports "
            f"'{(payload_name or '').strip()}' (guid ending "
            f"…{incoming[-6:]}). Refusing to write to avoid corrupting "
            f"cross-company data. If you moved to a new company, "
            f"unbind first from FLOWRA → Settings → Integrations."
        )

    await touch_last_seen(tenant_id, company_id)
    return True, ""


# ─── Agent-side bind (called from Tally Agent GUI on Save) ────────────
@router.post("/agent/tally-binding/bind")
async def agent_bind(request: Request):
    """The Tally Agent sends `{tenant_id, sync_token, company_id,
    company_name, company_guid}` right after the useradmin picks a
    company in the agent's Settings tab and hits Save.

    Idempotent: if already bound to the same GUID, returns success.
    If already bound to a DIFFERENT GUID, refuses. Useradmin must
    unbind from the FLOWRA UI first.
    """
    try:
        body = await request.json()
    except Exception:
        return APIResponse(success=False, error="Invalid JSON body")

    tenant_id = (body.get("tenant_id") or "").strip()
    sync_token = (body.get("sync_token") or "").strip()
    company_id = (body.get("company_id") or "").strip()
    name = (body.get("company_name") or "").strip()
    guid = _norm_guid(body.get("company_guid") or "")

    if not tenant_id or not sync_token:
        return APIResponse(success=False, error="tenant_id and sync_token required")
    if not verify_sync_token(tenant_id, sync_token):
        return APIResponse(success=False, error="Invalid sync token")
    if not company_id or not name or not guid:
        return APIResponse(
            success=False,
            error="company_id, company_name and company_guid are all required",
        )

    existing = await get_binding(tenant_id, company_id)
    now = datetime.now(timezone.utc).isoformat()

    if existing:
        if _norm_guid(existing.get("tally_company_guid")) == guid:
            # Same company — refresh name (rename in Tally propagates).
            await db.tally_bindings.update_one(
                {"tenant_id": tenant_id, "company_id": company_id},
                {"$set": {"tally_company_name": name, "last_seen_at": now}},
            )
            return APIResponse(success=True, data={"status": "already-bound", "name": name})
        return APIResponse(
            success=False,
            error=(
                "This FLOWRA workspace is already bound to a different "
                f"Tally company ('{existing.get('tally_company_name')}'). "
                "Unbind it from FLOWRA → Settings → Integrations, then "
                "try again."
            ),
        )

    await db.tally_bindings.insert_one({
        "tenant_id": tenant_id,
        "company_id": company_id,
        "tally_company_name": name,
        "tally_company_guid": guid,
        "bound_at": now,
        "bound_by": "agent",
        "last_seen_at": now,
    })
    logger.info(
        f"Agent bind: tenant={tenant_id} company={company_id} "
        f"guid={guid} name='{name}'"
    )
    return APIResponse(success=True, data={"status": "bound", "name": name})


# ─── Settings UI (useradmin, JWT auth) ────────────────────────────────
async def _require_useradmin(request: Request):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Auth required")
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only the tenant useradmin can manage the Tally binding.",
        )
    ctx = await get_tenant_context(request)
    if not ctx.get("tenant_id") or not ctx.get("company_id"):
        raise HTTPException(
            status_code=400,
            detail="Tenant + company context required. Pick a company first.",
        )
    return {"user": user, "ctx": ctx}


@router.get("/settings/tally-binding")
async def get_settings_binding(request: Request):
    """Return the current Tally binding for the logged-in useradmin's
    active company. Frontend shows this on the Integrations tab."""
    guard = await _require_useradmin(request)
    ctx = guard["ctx"]
    binding = await get_binding(ctx["tenant_id"], ctx["company_id"])
    if not binding:
        return APIResponse(success=True, data={"bound": False})
    return APIResponse(success=True, data={
        "bound": True,
        "tally_company_name": binding.get("tally_company_name"),
        "tally_company_guid": binding.get("tally_company_guid"),
        "bound_at": binding.get("bound_at"),
        "bound_by": binding.get("bound_by"),
        "last_seen_at": binding.get("last_seen_at"),
    })


@router.delete("/settings/tally-binding")
async def delete_settings_binding(request: Request):
    """Useradmin explicitly unbinds. Synced data is retained so the
    admin can re-bind (usually to the correct company) without loss.
    Next sync will re-run TOFU capture."""
    guard = await _require_useradmin(request)
    ctx = guard["ctx"]
    user = guard["user"]
    result = await db.tally_bindings.delete_one(
        {"tenant_id": ctx["tenant_id"], "company_id": ctx["company_id"]}
    )
    logger.info(
        f"Unbind: tenant={ctx['tenant_id']} company={ctx['company_id']} "
        f"by={user.get('username')} removed={result.deleted_count}"
    )
    return APIResponse(success=True, data={
        "unbound": result.deleted_count > 0,
    })
