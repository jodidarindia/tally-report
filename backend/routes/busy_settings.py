"""iter-170 — Busy tenant settings: triple-name field mapping.

Problem
-------
Busy exposes THREE name-like fields per stock item:
  - ItemName    (the primary name entered when the item was created)
  - AliasName   (short code / local nickname)
  - PrintName   (the string shown on invoices)
Different Busy tenants treat them differently. One shop stores the
part number in Alias; another stores it in PrintName; the primary
name may be a cryptic SKU or a human-readable description.

Instead of hard-coding one convention, we store a per-tenant mapping
and recompute `inventory_items.name` / `part_number` on every sync
based on the admin's chosen Busy field.

Storage
-------
Collection `tenant_settings`, key `{tenant_id}`, field `busy_name_mapping`:

  {
    "flowra_name":        "ItemName" | "AliasName" | "PrintName",
    "flowra_part_number": "ItemName" | "AliasName" | "PrintName" | null,
  }

Default (if unset): {flowra_name: ItemName, flowra_part_number: AliasName}.

Endpoints
---------
GET  /api/settings/busy-name-mapping     — useradmin reads current mapping.
PUT  /api/settings/busy-name-mapping     — useradmin updates it. Also marks
                                            the tenant for a one-time back-fill
                                            on the next sync tick.

The sync-side resolver `apply_busy_name_mapping()` is imported by
routes/sync.py's inventory branch — it rewrites `name` / `part_number`
on each inbound item according to the admin's choice.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException

from db import db
from models import APIResponse
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_SOURCES = ("ItemName", "AliasName", "PrintName")
DEFAULT_MAPPING = {
    "flowra_name": "ItemName",
    "flowra_part_number": "AliasName",
}


async def get_mapping(tenant_id: str) -> dict:
    """Return the merged mapping (defaults + overrides). Never None."""
    if not tenant_id:
        return dict(DEFAULT_MAPPING)
    doc = await db.tenant_settings.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "busy_name_mapping": 1},
    )
    user = (doc or {}).get("busy_name_mapping") or {}
    out = dict(DEFAULT_MAPPING)
    for k in ("flowra_name", "flowra_part_number"):
        v = user.get(k)
        if v in ALLOWED_SOURCES:
            out[k] = v
        elif v in (None, "", "none", "None") and k == "flowra_part_number":
            out[k] = None
    return out


def _busy_field_value(item: dict, key: str | None) -> str:
    """Resolve a Busy field from a stock-item payload. The agent must
    send `item_name` + `item_alias` + `item_print_name`. Fallback to the
    classic `item_name` so legacy sync payloads still work."""
    if not key:
        return ""
    mapping = {
        "ItemName":  item.get("item_name"),
        "AliasName": item.get("item_alias") or item.get("alias") or item.get("alias_name"),
        "PrintName": item.get("item_print_name") or item.get("print_name"),
    }
    v = mapping.get(key)
    if v is None:
        return ""
    return str(v).strip()


def apply_busy_name_mapping(items: list, mapping: dict) -> list:
    """Rewrite each item's `item_name` + `part_number` based on the
    admin's mapping. Called by routes/sync.py when `source=busy` AND
    the inventory batch arrives. Non-destructive — if the mapped field
    is empty on a given row, we fall back to the original ItemName so
    we never emit a nameless item."""
    if not items:
        return items
    name_src = mapping.get("flowra_name") or "ItemName"
    pn_src = mapping.get("flowra_part_number")
    out = []
    for it in items:
        if not isinstance(it, dict):
            out.append(it)
            continue
        new = dict(it)
        new_name = _busy_field_value(it, name_src) or (it.get("item_name") or "")
        new["item_name"] = new_name
        if pn_src:
            pn = _busy_field_value(it, pn_src)
            if pn:
                new["part_number"] = pn
        out.append(new)
    return out


# ─── Endpoints ───────────────────────────────────────────────────────
async def _require_useradmin(request: Request):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Auth required")
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    tenant_id = user.get("tenant_id") or user.get("owner_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    return {"user": user, "tenant_id": tenant_id}


@router.get("/settings/busy-name-mapping")
async def get_busy_name_mapping(request: Request):
    guard = await _require_useradmin(request)
    mapping = await get_mapping(guard["tenant_id"])
    return APIResponse(success=True, data={
        "mapping": mapping,
        "allowed_sources": list(ALLOWED_SOURCES),
    })


@router.put("/settings/busy-name-mapping")
async def put_busy_name_mapping(request: Request):
    guard = await _require_useradmin(request)
    try:
        body = await request.json()
    except Exception:
        return APIResponse(success=False, error="Invalid JSON body")
    mapping_in = (body or {}).get("mapping") or {}
    name_src = mapping_in.get("flowra_name")
    pn_src = mapping_in.get("flowra_part_number")
    if name_src not in ALLOWED_SOURCES:
        return APIResponse(
            success=False,
            error=f"flowra_name must be one of {ALLOWED_SOURCES}",
        )
    if pn_src not in (None, "", "none") and pn_src not in ALLOWED_SOURCES:
        return APIResponse(
            success=False,
            error=f"flowra_part_number must be one of {ALLOWED_SOURCES} or null",
        )
    normalised = {
        "flowra_name": name_src,
        "flowra_part_number": pn_src if pn_src in ALLOWED_SOURCES else None,
    }
    now = datetime.now(timezone.utc).isoformat()
    await db.tenant_settings.update_one(
        {"tenant_id": guard["tenant_id"]},
        {"$set": {
            "busy_name_mapping": normalised,
            "busy_name_mapping_updated_at": now,
            "busy_name_mapping_updated_by": guard["user"].get("username"),
            # Flag the tenant for a one-time back-fill on next sync so
            # existing items get rewritten with the new field choice.
            "busy_name_mapping_dirty": True,
        }},
        upsert=True,
    )
    logger.info(
        f"Busy name mapping updated: tenant={guard['tenant_id']} "
        f"name<-{name_src} part_number<-{pn_src}"
    )
    return APIResponse(success=True, data={"mapping": normalised})
