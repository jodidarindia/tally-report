from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from typing import Optional
import json
import logging
import re

from db import db
from models import InventoryItem, SalesVoucher, APIResponse
from utils import safe_num, compute_overdue_digest, ws_manager
from services.auth_service import verify_sync_token, get_current_user
from services.tenant_context import get_tenant_context, tenant_filter

logger = logging.getLogger(__name__)
router = APIRouter()


def _clean_tally_val(val):
    """Extract plain text from Tally XML dict strings like {'@TYPE': 'String', '#text': 'value'}."""
    if isinstance(val, dict):
        return val.get('#text', str(val))
    if isinstance(val, str) and "'#text'" in val:
        m = re.search(r"'#text':\s*'([^']*)'", val)
        return m.group(1) if m else val
    return val




@router.post("/agent/sync")
async def receive_agent_sync(request: dict):
    """Receive synced data from desktop agent.
    Requires tenant_id and sync_token for authentication + data isolation."""
    try:
        data_type = request.get('data_type')
        data = request.get('data', [])
        sync_time = request.get('sync_time')
        req_tenant_id = request.get('tenant_id', '')
        req_company_id = request.get('company_id', '')
        sync_token = request.get('sync_token', '')

        # Verify sync token if provided
        if req_tenant_id and sync_token:
            if not verify_sync_token(req_tenant_id, sync_token):
                return APIResponse(success=False, error="Invalid sync token")
        elif req_tenant_id:
            # Legacy: allow sync without token but log warning
            logger.warning(f"Sync without token for tenant {req_tenant_id}")

        # Fallback: if no tenant_id, use default (for backward compat)
        if not req_tenant_id:
            # Try to find the default admin tenant
            admin = await db.users.find_one({"role": "admin"}, {"_id": 0, "tenant_id": 1})
            req_tenant_id = admin.get("tenant_id", "tenant_admin") if admin else "tenant_admin"
            logger.info(f"No tenant_id in sync request, using default: {req_tenant_id}")

        # Add company to admin's company list if new — enforce max_companies limit
        if req_company_id and req_tenant_id:
            admin_user = await db.users.find_one({"tenant_id": req_tenant_id, "role": "admin"}, {"_id": 0, "companies": 1, "max_companies": 1, "plan": 1})
            if admin_user:
                current_companies = admin_user.get("companies", [])
                max_companies = admin_user.get("max_companies", 10)
                if req_company_id not in current_companies:
                    if len(current_companies) >= max_companies:
                        plan_name = (admin_user.get("plan") or "current").capitalize()
                        return APIResponse(success=False, error=f"Company limit reached ({max_companies}). Your {plan_name} plan allows syncing {max_companies} companies. Please upgrade to add more.")
                    await db.users.update_one(
                        {"tenant_id": req_tenant_id, "role": "admin"},
                        {"$addToSet": {"companies": req_company_id}}
                    )

        logger.info(f"Received {data_type} sync: {len(data)} items [tenant={req_tenant_id}, company={req_company_id}]")

        await ws_manager.broadcast({
            'event': 'data_synced',
            'data': {
                'data_type': data_type,
                'count': len(data),
                'sync_time': sync_time,
                'tenant_id': req_tenant_id,
                'company_id': req_company_id
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        # Build the tenant+company filter for deletions and upserts
        t_filter = {"tenant_id": req_tenant_id}
        if req_company_id:
            t_filter["company_id"] = req_company_id

        if data_type == 'inventory':
            await db.inventory_items.delete_many(t_filter)
            if data:
                docs = []
                for item in data:
                    inventory_obj = InventoryItem(**item)
                    doc = inventory_obj.model_dump()
                    doc['last_updated'] = doc['last_updated'].isoformat()
                    doc['tenant_id'] = req_tenant_id
                    doc['company_id'] = req_company_id
                    docs.append(doc)
                if docs:
                    await db.inventory_items.insert_many(docs)
            logger.info(f"Synced {len(data)} inventory items")

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
                    doc['tenant_id'] = req_tenant_id
                    doc['company_id'] = req_company_id
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": doc},
                            upsert=True
                        )
                    )
                if operations:
                    await db.sales_vouchers.bulk_write(operations)
            logger.info(f"Synced {len(data)} sales vouchers")

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
                            {"customer_name": customer_name, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "customer_name": customer_name,
                                "ledger_group": _clean_tally_val(cust.get('ledger_group', 'Sundry Debtors')),
                                "outstanding_amount": cust.get('outstanding_amount', 0),
                                "opening_balance": cust.get('opening_balance', 0),
                                "total_purchases": cust.get('total_purchases', 0),
                                "transaction_count": cust.get('transaction_count', 0),
                                "phone": _clean_tally_val(cust.get('phone', '')),
                                "contact_person": _clean_tally_val(cust.get('contact_person', '')),
                                "state": _clean_tally_val(cust.get('state', '')),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.customers.bulk_write(operations)
            logger.info(f"Synced {len(data)} customers")

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
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": receipt.get('voucher_type', 'receipt'),
                                "voucher_date": receipt.get('voucher_date', ''),
                                "party_name": receipt.get('party_name', ''),
                                "amount": receipt.get('amount', 0),
                                "bill_allocations": receipt.get('bill_allocations', []),
                                "narration": receipt.get('narration', ''),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.receipt_vouchers.bulk_write(operations)
            logger.info(f"Synced {len(data)} receipt/payment vouchers")

        elif data_type == 'credit_notes':
            if data:
                from pymongo import UpdateOne
                operations = []
                for cn in data:
                    v_id = cn.get('voucher_id', '')
                    if not v_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": "credit_note",
                                "voucher_date": cn.get('voucher_date', ''),
                                "party_name": cn.get('party_name', ''),
                                "total_amount": cn.get('total_amount', 0),
                                "items": cn.get('items', []),
                                "narration": cn.get('narration', ''),
                                "reference_number": cn.get('reference_number', ''),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.credit_notes.bulk_write(operations)
            logger.info(f"Synced {len(data)} credit notes")

        elif data_type == 'journal_vouchers':
            if data:
                from pymongo import UpdateOne
                operations = []
                for jv in data:
                    v_id = jv.get('voucher_id', '')
                    if not v_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": "journal",
                                "voucher_date": jv.get('voucher_date', ''),
                                "party_name": jv.get('party_name', ''),
                                "debit_amount": jv.get('debit_amount', 0),
                                "credit_amount": jv.get('credit_amount', 0),
                                "narration": jv.get('narration', ''),
                                "ledger_entries": jv.get('ledger_entries', []),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.journal_vouchers.bulk_write(operations)
            logger.info(f"Synced {len(data)} journal vouchers")

        elif data_type == 'stock_journals':
            if data:
                from pymongo import UpdateOne
                operations = []
                for sj in data:
                    v_id = sj.get('voucher_id', '')
                    if not v_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": "stock_journal",
                                "voucher_date": sj.get('voucher_date', ''),
                                "items": sj.get('items', []),
                                "narration": sj.get('narration', ''),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.stock_journals.bulk_write(operations)
            logger.info(f"Synced {len(data)} stock journals")

        elif data_type == 'purchase_vouchers':
            if data:
                from pymongo import UpdateOne
                operations = []
                for pv in data:
                    v_id = pv.get('voucher_id', '')
                    if not v_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": pv.get('voucher_type', 'purchase'),
                                "voucher_date": pv.get('voucher_date', ''),
                                "party_name": pv.get('party_name', ''),
                                "total_amount": pv.get('total_amount', 0),
                                "items": pv.get('items', []),
                                "reference_number": pv.get('reference_number', ''),
                                "ledger_entries": pv.get('ledger_entries', []),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.purchase_vouchers.bulk_write(operations)
            logger.info(f"Synced {len(data)} purchase vouchers")

        elif data_type == 'debit_notes':
            if data:
                from pymongo import UpdateOne
                operations = []
                for dn in data:
                    v_id = dn.get('voucher_id', '')
                    if not v_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"voucher_id": v_id, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "voucher_id": v_id,
                                "voucher_type": dn.get('voucher_type', 'debit_note'),
                                "voucher_date": dn.get('voucher_date', ''),
                                "party_name": dn.get('party_name', ''),
                                "total_amount": dn.get('total_amount', 0),
                                "items": dn.get('items', []),
                                "reference_number": dn.get('reference_number', ''),
                                "ledger_entries": dn.get('ledger_entries', []),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.debit_notes.bulk_write(operations)
            logger.info(f"Synced {len(data)} debit notes")

        elif data_type == 'sundry_creditors':
            if data:
                from pymongo import UpdateOne
                operations = []
                for cr in data:
                    cname = cr.get('creditor_name', '')
                    if not cname:
                        continue
                    operations.append(
                        UpdateOne(
                            {"creditor_name": cname, "tenant_id": req_tenant_id, "company_id": req_company_id},
                            {"$set": {
                                "creditor_name": cname,
                                "ledger_group": _clean_tally_val(cr.get('ledger_group', 'Sundry Creditors')),
                                "outstanding_amount": cr.get('outstanding_amount', 0),
                                "opening_balance": cr.get('opening_balance', 0),
                                "phone": _clean_tally_val(cr.get('phone', '')),
                                "contact_person": _clean_tally_val(cr.get('contact_person', '')),
                                "state": _clean_tally_val(cr.get('state', '')),
                                "last_synced": sync_time,
                                "tenant_id": req_tenant_id,
                                "company_id": req_company_id
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.sundry_creditors.bulk_write(operations)
            logger.info(f"Synced {len(data)} sundry creditors")

        # Update last sync time
        company_name = request.get('company_name', '') or req_company_id
        financial_year = request.get('financial_year', '')
        sync_time_val = sync_time or datetime.now(timezone.utc).isoformat()
        await db.sync_status.update_one(
            {'type': 'agent_sync', 'tenant_id': req_tenant_id, 'company_id': req_company_id},
            {'$set': {
                'last_sync': sync_time_val,
                'data_type': data_type,
                'count': len(data),
                'agent_version': request.get('agent_version', ''),
                'company_name': company_name,
                'financial_year': financial_year,
                'tenant_id': req_tenant_id,
                'company_id': req_company_id
            }},
            upsert=True
        )

        # Store sync history entry
        await db.sync_history.insert_one({
            'timestamp': sync_time_val,
            'data_type': data_type,
            'count': len(data),
            'financial_year': financial_year,
            'company_name': company_name,
            'agent_version': request.get('agent_version', ''),
            'sync_mode': request.get('sync_mode', 'full'),
            'tenant_id': req_tenant_id,
            'company_id': req_company_id
        })

        # Recompute overdue digest after sync of relevant data types
        if data_type in ('sales', 'receipts', 'customers', 'credit_notes', 'journal_vouchers'):
            try:
                digest = await compute_overdue_digest(db, req_tenant_id, req_company_id)
                logger.info(f"Overdue digest recomputed: {digest['total_overdue_invoices']} overdue invoices")
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
    """Receive real-time sync progress from desktop agent."""
    try:
        event_type = request.get('type', 'unknown')
        req_tenant_id = request.get('tenant_id', '')
        req_company_id = request.get('company_id', '')
        logger.info(f"Sync progress: {event_type}")

        await db.sync_status.update_one(
            {'type': 'sync_progress', 'tenant_id': req_tenant_id},
            {'$set': {
                'event': event_type,
                'details': request,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'tenant_id': req_tenant_id,
                'company_id': req_company_id
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
                    t_id = msg.get('tenant_id', '')
                    c_id = msg.get('company_id', '')
                    q = {'type': 'agent_sync'}
                    if t_id:
                        q['tenant_id'] = t_id
                    if c_id:
                        q['company_id'] = c_id
                    sync_status = await db.sync_status.find_one(q, {'_id': 0})
                    progress = await db.sync_status.find_one(
                        {'type': 'sync_progress', **({} if not t_id else {'tenant_id': t_id})},
                        {'_id': 0}
                    )
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
async def get_sync_status(request: Request, company_id: Optional[str] = None):
    """Get last sync status from desktop agent."""
    try:
        ctx = await get_tenant_context(request)
        q = {'type': 'agent_sync'}
        if ctx and ctx.get("tenant_id"):
            q['tenant_id'] = ctx["tenant_id"]
        if company_id:
            q['company_id'] = company_id
        elif ctx and ctx.get("company_id"):
            q['company_id'] = ctx["company_id"]

        sync_status = await db.sync_status.find_one(q, {'_id': 0})

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


@router.get("/sync/companies-status")
async def get_all_companies_sync_status(request: Request):
    """Get sync status for ALL companies of the current admin — powers the CompanySelector overlay."""
    try:
        ctx = await get_tenant_context(request)
        tenant_id = ctx.get("tenant_id", "") if ctx else ""
        if not tenant_id:
            return APIResponse(success=True, data=[])

        # Get the admin's companies list
        user = await db.users.find_one({"tenant_id": tenant_id, "role": "admin"}, {"_id": 0, "companies": 1})
        companies = user.get("companies", []) if user else []

        result = []
        for company in companies:
            sync_status = await db.sync_status.find_one(
                {"type": "agent_sync", "tenant_id": tenant_id, "company_id": company},
                {"_id": 0}
            )
            inv_count = await db.inventory_items.count_documents({"tenant_id": tenant_id, "company_id": company})
            sales_count = await db.sales_vouchers.count_documents({"tenant_id": tenant_id, "company_id": company})
            result.append({
                "company_name": company,
                "last_sync": sync_status.get("last_sync") if sync_status else None,
                "agent_version": sync_status.get("agent_version", "") if sync_status else "",
                "inventory_count": inv_count,
                "sales_count": sales_count,
            })

        return APIResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error getting companies sync status: {e}")
        return APIResponse(success=False, error=str(e))




@router.get("/sync/connection-status")
async def get_connection_status(request: Request):
    """Get comprehensive connection status for the Setup page — last sync, agent version, companies, data counts."""
    try:
        ctx = await get_tenant_context(request)
        tenant_id = ctx.get("tenant_id", "") if ctx else ""
        company_id = ctx.get("company_id", "") if ctx else ""

        if not tenant_id:
            return APIResponse(success=True, data=None)

        # Get last sync info
        q = {"type": "agent_sync", "tenant_id": tenant_id}
        if company_id:
            q["company_id"] = company_id
        sync_status = await db.sync_status.find_one(q, {"_id": 0}, sort=[("last_sync", -1)])

        # Get user's companies
        user = await db.users.find_one({"tenant_id": tenant_id, "role": "admin"}, {"_id": 0, "companies": 1})
        companies = user.get("companies", []) if user else []

        # Get data counts
        base_q = {"tenant_id": tenant_id}
        if company_id:
            base_q["company_id"] = company_id
        inv_count = await db.inventory_items.count_documents(base_q)
        sales_count = await db.sales_vouchers.count_documents(base_q)
        cust_count = await db.customers.count_documents(base_q)

        return APIResponse(success=True, data={
            "last_sync": sync_status.get("last_sync") if sync_status else None,
            "agent_version": sync_status.get("agent_version", "") if sync_status else "",
            "companies": companies,
            "sync_counts": {
                "inventory_items": inv_count,
                "sales_vouchers": sales_count,
                "customers": cust_count
            }
        })
    except Exception as e:
        logger.error(f"Error getting connection status: {e}")
        return APIResponse(success=False, error=str(e))




@router.get("/sync/history")
async def get_sync_history(request: Request, limit: int = 100, company_id: Optional[str] = None):
    """Get sync history timeline."""
    try:
        ctx = await get_tenant_context(request)
        q = {}
        if ctx and ctx.get("tenant_id"):
            q["tenant_id"] = ctx["tenant_id"]
        if company_id:
            q["company_id"] = company_id
        elif ctx and ctx.get("company_id"):
            q["company_id"] = ctx["company_id"]

        history = await db.sync_history.find(q, {"_id": 0}).sort("timestamp", -1).to_list(limit)

        cycles = []
        current_cycle = None
        for entry in history:
            ts = entry.get('timestamp', '')
            if not current_cycle or _time_diff_minutes(current_cycle['timestamp'], ts) > 5:
                if current_cycle:
                    cycles.append(current_cycle)
                current_cycle = {
                    'timestamp': ts,
                    'company_name': entry.get('company_name', ''),
                    'financial_year': entry.get('financial_year', ''),
                    'sync_mode': entry.get('sync_mode', 'full'),
                    'agent_version': entry.get('agent_version', ''),
                    'data_types': {}
                }
            dtype = entry.get('data_type', 'unknown')
            current_cycle['data_types'][dtype] = entry.get('count', 0)

        if current_cycle:
            cycles.append(current_cycle)

        return APIResponse(success=True, data={"cycles": cycles, "total": len(cycles)})
    except Exception as e:
        logger.error(f"Error fetching sync history: {e}")
        return APIResponse(success=False, error=str(e))


def _time_diff_minutes(ts1: str, ts2: str) -> float:
    try:
        from dateutil.parser import parse as parse_dt
        d1 = parse_dt(ts1)
        d2 = parse_dt(ts2)
        return abs((d1 - d2).total_seconds()) / 60
    except Exception:
        return 999
