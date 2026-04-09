from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from typing import Optional
import json
import logging

from db import db
from models import InventoryItem, SalesVoucher, APIResponse
from utils import safe_num, compute_overdue_digest, ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agent/sync")
async def receive_agent_sync(request: dict):
    """Receive synced data from desktop agent"""
    try:
        data_type = request.get('data_type')
        data = request.get('data', [])
        sync_time = request.get('sync_time')

        logger.info(f"Received {data_type} sync from agent: {len(data)} items")

        await ws_manager.broadcast({
            'event': 'data_synced',
            'data': {
                'data_type': data_type,
                'count': len(data),
                'sync_time': sync_time
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        if data_type == 'inventory':
            await db.inventory_items.delete_many({})
            if data:
                docs = []
                for item in data:
                    inventory_obj = InventoryItem(**item)
                    doc = inventory_obj.model_dump()
                    doc['last_updated'] = doc['last_updated'].isoformat()
                    docs.append(doc)
                if docs:
                    await db.inventory_items.insert_many(docs)
            logger.info(f"Synced {len(data)} inventory items to database")

        elif data_type == 'sales':
            if data:
                from pymongo import UpdateOne
                operations = []
                for voucher in data:
                    v_id = voucher.get('voucher_id', '')
                    if not v_id:
                        continue
                    sales_obj = SalesVoucher(**voucher)
                    doc = sales_obj.model_dump()
                    doc['last_updated'] = doc['last_updated'].isoformat()
                    doc.pop('id', None)
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id},
                            {"$set": doc},
                            upsert=True
                        )
                    )
                if operations:
                    await db.sales_vouchers.bulk_write(operations)
            logger.info(f"Synced {len(data)} sales vouchers to database")

        elif data_type == 'customers':
            if data:
                from pymongo import UpdateOne
                operations = []
                for cust in data:
                    customer_name = cust.get('customer_name', '')
                    if not customer_name:
                        continue
                    operations.append(
                        UpdateOne(
                            {"customer_name": customer_name},
                            {"$set": {
                                "customer_name": customer_name,
                                "ledger_group": cust.get('ledger_group', 'Sundry Debtors'),
                                "outstanding_amount": cust.get('outstanding_amount', 0),
                                "total_purchases": cust.get('total_purchases', 0),
                                "transaction_count": cust.get('transaction_count', 0),
                                "phone": cust.get('phone', ''),
                                "contact_person": cust.get('contact_person', ''),
                                "state": cust.get('state', ''),
                                "last_synced": sync_time
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.customers.bulk_write(operations)
            logger.info(f"Synced {len(data)} customers to database")

        elif data_type == 'receipts':
            if data:
                from pymongo import UpdateOne
                operations = []
                for receipt in data:
                    v_id = receipt.get('voucher_id', '')
                    if not v_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": receipt.get('voucher_type', 'receipt'),
                                "voucher_date": receipt.get('voucher_date', ''),
                                "party_name": receipt.get('party_name', ''),
                                "amount": receipt.get('amount', 0),
                                "bill_allocations": receipt.get('bill_allocations', []),
                                "narration": receipt.get('narration', ''),
                                "last_synced": sync_time
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.receipt_vouchers.bulk_write(operations)
            logger.info(f"Synced {len(data)} receipt/payment vouchers to database")

        # Update last sync time
        company_name = request.get('company_name', '')
        financial_year = request.get('financial_year', '')
        await db.sync_status.update_one(
            {'type': 'agent_sync'},
            {'$set': {
                'last_sync': sync_time,
                'data_type': data_type,
                'count': len(data),
                'agent_version': request.get('agent_version', ''),
                'company_name': company_name,
                'financial_year': financial_year
            }},
            upsert=True
        )

        # Recompute overdue digest after every sync (sales or receipts affect it)
        if data_type in ('sales', 'receipts', 'customers'):
            try:
                digest = await compute_overdue_digest(db)
                logger.info(f"Overdue digest recomputed after {data_type} sync: {digest['total_overdue_invoices']} overdue invoices")
                await ws_manager.broadcast({
                    'event': 'overdue_digest_updated',
                    'data': {
                        'total_overdue_invoices': digest['total_overdue_invoices'],
                        'total_overdue_amount': digest['total_overdue_amount'],
                    },
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            except Exception as digest_err:
                logger.error(f"Error recomputing overdue digest: {digest_err}")

        return APIResponse(
            success=True,
            message=f"Successfully synced {len(data)} {data_type} items"
        )

    except Exception as e:
        logger.error(f"Error receiving agent sync: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/agent/sync-progress")
async def receive_sync_progress(request: dict):
    """Receive real-time sync progress from desktop agent and broadcast to WebSocket clients."""
    try:
        event_type = request.get('type', 'unknown')
        logger.info(f"Sync progress: {event_type} - {json.dumps({k: v for k, v in request.items() if k != 'type'}, default=str)[:200]}")

        await db.sync_status.update_one(
            {'type': 'sync_progress'},
            {'$set': {
                'event': event_type,
                'details': request,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )

        await ws_manager.broadcast({
            'event': event_type,
            'data': request,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        return APIResponse(success=True, message="Progress received")
    except Exception as e:
        logger.error(f"Error receiving sync progress: {e}")
        return APIResponse(success=False, error=str(e))


@router.websocket("/ws/sync-status")
async def websocket_sync_status(websocket: WebSocket):
    """WebSocket endpoint for real-time sync status updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get('action') == 'get_status':
                    sync_status = await db.sync_status.find_one({'type': 'agent_sync'}, {'_id': 0})
                    progress = await db.sync_status.find_one({'type': 'sync_progress'}, {'_id': 0})
                    await websocket.send_json({
                        'event': 'status_response',
                        'data': {
                            'sync_status': sync_status,
                            'last_progress': progress
                        }
                    })
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@router.get("/sync/status")
async def get_sync_status():
    """Get last sync status from desktop agent"""
    try:
        sync_status = await db.sync_status.find_one({'type': 'agent_sync'}, {'_id': 0})

        if not sync_status:
            return APIResponse(
                success=True,
                data={
                    'last_sync': None,
                    'is_syncing': False,
                    'message': 'No sync data available'
                }
            )

        return APIResponse(success=True, data=sync_status)

    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return APIResponse(success=False, error=str(e))
