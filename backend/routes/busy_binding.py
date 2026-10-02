"""iter-170 — Busy Agent company binding + Trust-On-First-Use (TOFU).

Problem
-------
A single useradmin email in Flowra should be bound to EXACTLY ONE Busy
company (BDEPName). The Busy agent, pointed at a different folder by
mistake, would otherwise silently drop foreign vouchers / customers /
inventory into the wrong tenant. Field-reported on NAVDURGA — when the
same useradmin tried a second company's folder, the agent happily
started syncing before the backend could reject it.

Solution
--------
TOFU binding keyed on **Busy BDEPName** (the display name Busy shows to
the admin — e.g. "NAVDURGA AUTO SPARES JABALPUR"). Captured by the
agent via `_resolve_company_display_name()` on first sync, stored on
`busy_bindings`. Any later sync whose BDEPName doesn't match is
HARD-BLOCKED at the server AND the agent (on startup, via the new
`/busy-binding/check` endpoint) refuses to enter the sync loop and
pops a GUI dialog telling the admin which company is already locked.

Useradmin can unbind from the Flowra UI (Settings → Integrations →
Busy Company Lock). Existing synced data is kept; next sync re-binds.

Endpoints
---------
POST /api/agent/busy-binding/check     — agent-side (sync_token auth)
POST /api/agent/busy-binding/bind      — agent-side (sync_token auth)
GET  /api/settings/busy-binding        — useradmin (JWT)
DELETE /api/settings/busy-binding      — useradmin (JWT)

Storage
-------
Collection `busy_bindings` — one document per tenant_id (NOT per
company_id — because the user's constraint is "one email = one Busy
company" regardless of how many internal company_ids the tenant has):

  {
    tenant_id,
    busy_company_name,     # case-preserved display
    busy_company_name_norm, # lowercase, whitespace-collapsed for compare
    bound_at, bound_by, last_seen_at,
  }
"""
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException

from db import db
from models import APIResponse
from services.auth_service import verify_sync_token, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _norm_name(v: str) -> str:
    """Normalise a Busy BDEPName for case-insensitive comparison.
    Busy admins sometimes change capitalisation / spacing between
    sessions, which must NOT be treated as a new company."""
    if not v:
        return ""
    s = str(v).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


async def get_binding(tenant_id: str) -> dict | None:
    if not tenant_id:
        return None
    return await db.busy_bindings.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0},
    )


async def touch_last_seen(tenant_id: str) -> None:
    try:
        await db.busy_bindings.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"last_seen_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.debug(f"busy touch_last_seen: {e}")


async def validate_busy_sync(
    tenant_id: str,
    payload_name: str,
) -> tuple[bool, str]:
    """Called by /api/agent/sync when source=busy. Behaviour:
      - no binding + payload has a name  → TOFU bind, accept.
      - no binding + no name             → accept (legacy agents).
      - binding + name matches           → accept, bump last_seen_at.
      - binding + name differs           → REJECT with clear error.
    """
    binding = await get_binding(tenant_id)
    incoming_norm = _norm_name(payload_name)

    if not binding:
        if incoming_norm:
            await db.busy_bindings.insert_one({
                "tenant_id": tenant_id,
                "busy_company_name": (payload_name or "").strip(),
                "busy_company_name_norm": incoming_norm,
                "bound_at": datetime.now(timezone.utc).isoformat(),
                "bound_by": "agent-tofu",
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(
                f"Busy TOFU bind: tenant={tenant_id} name='{payload_name}'"
            )
        return True, ""

    bound_norm = _norm_name(binding.get("busy_company_name_norm")
                            or binding.get("busy_company_name"))
    if not incoming_norm:
        # Agent didn't send a name — accept and warn (older build).
        logger.warning(
            f"Busy sync without company_name on bound tenant {tenant_id}. "
            f"Expected '{binding.get('busy_company_name')}'."
        )
        await touch_last_seen(tenant_id)
        return True, ""

    if incoming_norm != bound_norm:
        return False, (
            f"This FLOWRA tenant is already locked to Busy company "
            f"'{binding.get('busy_company_name')}'. The agent is trying "
            f"to sync '{(payload_name or '').strip()}'. Refusing to "
            f"write to avoid cross-company corruption. Unbind the current "
            f"company from FLOWRA → Settings → Integrations → Busy "
            f"Company Lock before pointing the agent at a different Busy "
            f"folder."
        )
    await touch_last_seen(tenant_id)
    return True, ""


# ─── Agent-side ───────────────────────────────────────────────────────
@router.post("/agent/busy-binding/check")
async def agent_check(request: Request):
    """Agent calls this on EVERY startup, right after it reads the
    Busy BDEPName. Returns `{bound, matches, existing_name}` so the
    agent can abort BEFORE touching Busy if the admin pointed it at
    a different company. Non-mutating — just a read.
    """
    try:
        body = await request.json()
    except Exception:
        return APIResponse(success=False, error="Invalid JSON body")

    tenant_id = (body.get("tenant_id") or "").strip()
    sync_token = (body.get("sync_token") or "").strip()
    incoming_name = (body.get("busy_company_name") or "").strip()

    if not tenant_id or not sync_token:
        return APIResponse(success=False, error="tenant_id and sync_token required")
    if not verify_sync_token(tenant_id, sync_token):
        return APIResponse(success=False, error="Invalid sync token")

    binding = await get_binding(tenant_id)
    if not binding:
        return APIResponse(success=True, data={
            "bound": False, "matches": None, "existing_name": None,
        })
    bound_norm = _norm_name(binding.get("busy_company_name_norm")
                            or binding.get("busy_company_name"))
    incoming_norm = _norm_name(incoming_name)
    matches = (incoming_norm == bound_norm) if incoming_norm else None
    return APIResponse(success=True, data={
        "bound": True,
        "matches": matches,
        "existing_name": binding.get("busy_company_name"),
    })


@router.post("/agent/busy-binding/bind")
async def agent_bind(request: Request):
    """Explicit bind endpoint — used by the agent's config save path
    (and the GUI 'Lock this company' button). Idempotent for the same
    name, refuses a different name."""
    try:
        body = await request.json()
    except Exception:
        return APIResponse(success=False, error="Invalid JSON body")

    tenant_id = (body.get("tenant_id") or "").strip()
    sync_token = (body.get("sync_token") or "").strip()
    name = (body.get("busy_company_name") or "").strip()

    if not tenant_id or not sync_token:
        return APIResponse(success=False, error="tenant_id and sync_token required")
    if not verify_sync_token(tenant_id, sync_token):
        return APIResponse(success=False, error="Invalid sync token")
    if not name:
        return APIResponse(success=False, error="busy_company_name required")

    now = datetime.now(timezone.utc).isoformat()
    norm = _norm_name(name)
    existing = await get_binding(tenant_id)
    if existing:
        if _norm_name(existing.get("busy_company_name_norm")
                      or existing.get("busy_company_name")) == norm:
            await db.busy_bindings.update_one(
                {"tenant_id": tenant_id},
                {"$set": {"busy_company_name": name, "last_seen_at": now}},
            )
            return APIResponse(success=True, data={"status": "already-bound", "name": name})
        return APIResponse(
            success=False,
            error=(
                "This FLOWRA tenant is already locked to Busy company "
                f"'{existing.get('busy_company_name')}'. Unbind it from "
                "FLOWRA → Settings → Integrations → Busy Company Lock "
                "before binding a different company."
            ),
        )
    await db.busy_bindings.insert_one({
        "tenant_id": tenant_id,
        "busy_company_name": name,
        "busy_company_name_norm": norm,
        "bound_at": now,
        "bound_by": "agent",
        "last_seen_at": now,
    })
    logger.info(f"Busy bind: tenant={tenant_id} name='{name}'")
    return APIResponse(success=True, data={"status": "bound", "name": name})


# ─── Settings UI (useradmin) ──────────────────────────────────────────
async def _require_useradmin(request: Request):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Auth required")
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only the tenant useradmin can manage the Busy binding.",
        )
    tenant_id = user.get("tenant_id") or user.get("owner_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    return {"user": user, "tenant_id": tenant_id}


@router.get("/settings/busy-binding")
async def get_settings_binding(request: Request):
    guard = await _require_useradmin(request)
    binding = await get_binding(guard["tenant_id"])
    if not binding:
        return APIResponse(success=True, data={"bound": False})
    return APIResponse(success=True, data={
        "bound": True,
        "busy_company_name": binding.get("busy_company_name"),
        "bound_at": binding.get("bound_at"),
        "bound_by": binding.get("bound_by"),
        "last_seen_at": binding.get("last_seen_at"),
    })


@router.delete("/settings/busy-binding")
async def delete_settings_binding(request: Request):
    guard = await _require_useradmin(request)
    user = guard["user"]
    result = await db.busy_bindings.delete_one({"tenant_id": guard["tenant_id"]})
    logger.info(
        f"Busy unbind: tenant={guard['tenant_id']} by={user.get('username')} "
        f"removed={result.deleted_count}"
    )
    return APIResponse(success=True, data={"unbound": result.deleted_count > 0})
