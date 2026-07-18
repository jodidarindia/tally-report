"""
Google Drive OAuth + connection-management routes.

Endpoints:
  GET  /api/gdrive/connect         — start OAuth, returns auth URL
  GET  /api/gdrive/oauth/callback  — Google redirects here with `code`
  GET  /api/gdrive/status          — {connected, google_email, ...}
  POST /api/gdrive/disconnect      — revoke + delete connection

All state-mutating endpoints require role="admin" (useradmin only).
Every DB query filtered by (tenant_id, company_id) so tenants stay
completely isolated.
"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context
from services.gdrive_service import (
    build_authorization_url, exchange_code_for_credentials,
    get_email_from_creds, credentials_to_persist,
    revoke_credentials,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _require_useradmin(request: Request):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Auth required.")
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only the tenant useradmin can manage Drive integration.")
    ctx = await get_tenant_context(request)
    if not ctx.get("tenant_id") or not ctx.get("company_id"):
        raise HTTPException(
            status_code=400,
            detail="Tenant + company context required. Pick a company first.")
    return {"user": user, "ctx": ctx}


def _q(ctx):
    return {"tenant_id": ctx["tenant_id"], "company_id": ctx["company_id"]}


@router.get("/gdrive/connect")
async def start_connect(request: Request):
    """Return the Google consent URL for the frontend to redirect to."""
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    state = f"{ctx['tenant_id']}:{ctx['company_id']}"
    try:
        url = build_authorization_url(state)
    except RuntimeError as e:
        return APIResponse(success=False, error=str(e))
    return APIResponse(success=True, data={"authorization_url": url})


@router.get("/gdrive/oauth/callback")
async def oauth_callback(code: str = Query(...), state: str = Query(...),
                          error: str = Query(None)):
    """Google redirects back here after user consents. `state` carries
    <tenant_id>:<company_id> from the connect endpoint above.

    We DON'T re-auth the user here (Google handled the auth). We just
    write the encrypted refresh_token, keyed by the state we set."""
    frontend = os.environ.get(
        "FLOWRA_FRONTEND_URL",
        "https://tally-report-ai.preview.emergentagent.com")
    if error:
        return RedirectResponse(
            f"{frontend}/#gdrive-error=" + error, status_code=302)

    try:
        tenant_id, company_id = state.split(":", 1)
    except ValueError:
        return RedirectResponse(
            f"{frontend}/#gdrive-error=bad-state", status_code=302)

    # Basic safety: make sure this state matches a real tenant/company
    if not (tenant_id and company_id):
        return RedirectResponse(
            f"{frontend}/#gdrive-error=empty-state", status_code=302)

    try:
        creds = exchange_code_for_credentials(code)
    except Exception as e:
        logger.error(f"OAuth token exchange failed: {e}")
        return RedirectResponse(
            f"{frontend}/#gdrive-error=token-exchange", status_code=302)

    google_email = get_email_from_creds(creds)
    payload = credentials_to_persist(creds, google_email)
    await db.gdrive_tenant_connections.update_one(
        {"tenant_id": tenant_id, "company_id": company_id},
        {"$set": {
            "tenant_id": tenant_id, "company_id": company_id,
            **payload,
        }},
        upsert=True,
    )
    logger.info(f"gdrive connected: tenant={tenant_id} email={google_email}")
    return RedirectResponse(
        f"{frontend}/#gdrive-connected={google_email}",
        status_code=302)


@router.get("/gdrive/status")
async def get_status(request: Request):
    """Return whether a Drive is connected for the current
    (tenant, company). Also readable by non-admin roles — dispatch
    employees need to know whether they can upload."""
    ctx = await get_tenant_context(request)
    if not ctx.get("tenant_id") or not ctx.get("company_id"):
        return APIResponse(success=True, data={"connected": False})
    doc = await db.gdrive_tenant_connections.find_one(
        {"tenant_id": ctx["tenant_id"], "company_id": ctx["company_id"]},
        {"_id": 0, "refresh_token_encrypted": 0, "folder_cache": 0}) or {}
    return APIResponse(success=True, data={
        "connected": bool(doc.get("refresh_token_encrypted")
                            or doc.get("google_email")),
        "google_email": doc.get("google_email"),
        "status": doc.get("status"),
        "connected_at": doc.get("connected_at"),
        "last_used_at": doc.get("last_used_at"),
    })


@router.post("/gdrive/disconnect")
async def disconnect(request: Request):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    doc = await db.gdrive_tenant_connections.find_one(_q(ctx))
    if not doc:
        return APIResponse(success=True, data={"disconnected": False})
    try:
        revoke_credentials(doc)
    except Exception as e:
        logger.warning(f"revoke_credentials failed (continuing): {e}")
    await db.gdrive_tenant_connections.delete_one(_q(ctx))
    logger.info(
        f"gdrive disconnected: tenant={ctx['tenant_id']} "
        f"email={doc.get('google_email')}")
    return APIResponse(success=True, data={"disconnected": True})
