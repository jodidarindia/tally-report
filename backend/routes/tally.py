from fastapi import APIRouter, Request
from datetime import datetime, timezone
import logging

from db import db
from models import TallyConnection, TallyConnectionCreate, APIResponse
from services.tally_client import TallyClient
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()

tally_client_instance = None


@router.post("/tally/connect")
async def connect_tally(connection: TallyConnectionCreate):
    try:
        global tally_client_instance

        if connection.connection_type == "rest":
            tally_client_instance = TallyClient(
                connection_type="rest",
                api_key=connection.api_key
            )
        else:
            tally_client_instance = TallyClient(
                connection_type="xml",
                host=connection.host or "localhost",
                port=connection.port or 9000
            )

        is_connected = tally_client_instance.test_connection()

        if not is_connected:
            return APIResponse(
                success=False,
                error="Unable to connect to Tally. Please check your settings."
            )

        connection_obj = TallyConnection(**connection.model_dump())
        connection_obj.last_synced = datetime.utcnow()

        doc = connection_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc.get('last_synced'):
            doc['last_synced'] = doc['last_synced'].isoformat()

        await db.tally_connections.insert_one(doc)

        return APIResponse(
            success=True,
            message="Successfully connected to Tally",
            data={"connection_id": connection_obj.id}
        )
    except Exception as e:
        logger.error(f"Error connecting to Tally: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/tally/status")
async def get_tally_status(request: Request):
    """Return the agent connection status for the CURRENT tenant + company.

    Bug fix (2026-05-21): the previous implementation read
    ``db.sync_status.find_one({'type': 'agent_sync'})`` with no tenant
    filter, returning the first ``agent_sync`` row in the entire DB. That
    leaked another tenant's ``agent_version`` (e.g. ``9.8.7-aliases-perf``)
    onto every shop's Sync History header. Now we filter by tenant_id +
    company_id from the authenticated request, and fall back to the
    tenant-level row when no per-company doc exists. No tenant_id ⇒ no
    rows returned, never a global leak.
    """
    try:
        ctx = await get_tenant_context(request)
        tenant_id = ctx.get("tenant_id") if ctx else ""
        company_id = request.headers.get("X-Company-ID", "") or (ctx.get("company_id") if ctx else "")

        if not tenant_id:
            return APIResponse(
                success=True,
                data={"is_connected": False, "message": "No sync data yet. Run the desktop agent."}
            )

        # Prefer the exact tenant + company match. Fall back to tenant-only
        # (covers admins viewing before selecting a company).
        sync_status = None
        if company_id:
            sync_status = await db.sync_status.find_one(
                {"type": "agent_sync", "tenant_id": tenant_id, "company_id": company_id},
                {"_id": 0}
            )
        if not sync_status:
            # Latest sync any company under this tenant (sort by last_sync desc).
            cursor = db.sync_status.find(
                {"type": "agent_sync", "tenant_id": tenant_id},
                {"_id": 0}
            ).sort("last_sync", -1).limit(1)
            rows = await cursor.to_list(1)
            sync_status = rows[0] if rows else None

        if sync_status and sync_status.get("last_sync"):
            last_sync = sync_status["last_sync"]
            company = sync_status.get("company_name", "")
            return APIResponse(
                success=True,
                data={
                    "is_connected": True,
                    "message": f"Connected - {company}" if company else "Connected",
                    "last_sync": last_sync,
                    "company_name": company,
                    "agent_version": sync_status.get("agent_version", "")
                }
            )
        return APIResponse(
            success=True,
            data={"is_connected": False, "message": "No sync data yet. Run the desktop agent."}
        )
    except Exception as e:
        logger.error(f"Error checking Tally status: {e}")
        return APIResponse(success=False, error=str(e))
