from fastapi import APIRouter
from datetime import datetime, timezone
import logging

from db import db
from models import TallyConnection, TallyConnectionCreate, APIResponse
from services.tally_client import TallyClient

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
async def get_tally_status():
    try:
        sync_status = await db.sync_status.find_one({'type': 'agent_sync'}, {'_id': 0})
        if sync_status and sync_status.get('last_sync'):
            last_sync = sync_status['last_sync']
            company = sync_status.get('company_name', '')
            return APIResponse(
                success=True,
                data={
                    "is_connected": True,
                    "message": f"Connected - {company}" if company else "Connected",
                    "last_sync": last_sync,
                    "company_name": company,
                    "agent_version": sync_status.get('agent_version', '')
                }
            )
        return APIResponse(
            success=True,
            data={"is_connected": False, "message": "No sync data yet. Run the desktop agent."}
        )
    except Exception as e:
        logger.error(f"Error checking Tally status: {e}")
        return APIResponse(success=False, error=str(e))
