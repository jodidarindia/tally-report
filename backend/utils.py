from datetime import datetime, timezone
from typing import List
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


def safe_num(val, default=0):
    """Return numeric value or default if None/non-numeric."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def safe_str(val, default=""):
    """Return string value or default if None."""
    return str(val) if val is not None else default


def fy_to_date_range(fy: str):
    """Convert '2025-26' to ('2025-04-01', '2026-03-31')"""
    if not fy or '-' not in fy:
        return None, None
    parts = fy.split('-')
    start_year = int(parts[0])
    end_year_short = int(parts[1])
    end_year = start_year // 100 * 100 + end_year_short if end_year_short < 100 else end_year_short
    return f"{start_year}-04-01", f"{end_year}-03-31"


def filter_vouchers_by_fy(vouchers, fy):
    """Filter vouchers by financial year date range"""
    if not fy:
        return vouchers
    fy_start, fy_end = fy_to_date_range(fy)
    if not fy_start:
        return vouchers
    return [v for v in vouchers if fy_start <= v.get('voucher_date', '') <= fy_end]


def get_previous_fy(fy: str):
    """Given '2025-26', returns '2024-25'"""
    if not fy or '-' not in fy:
        return None
    parts = fy.split('-')
    start_year = int(parts[0])
    end_short = int(parts[1])
    prev_start = start_year - 1
    prev_end = end_short - 1 if end_short > 0 else 99
    return f"{prev_start}-{str(prev_end).zfill(2)}"


OVERDUE_THRESHOLD_DAYS = 55


async def compute_overdue_digest(db_ref):
    """Compute overdue invoices (>55 days from invoice date) considering receipt payments.
    Stores result in overdue_digest collection for quick dashboard retrieval."""
    from datetime import date as date_type

    today = date_type.today()

    sales = await db_ref.sales_vouchers.find({}, {"_id": 0}).to_list(20000)
    receipts = await db_ref.receipt_vouchers.find({}, {"_id": 0}).to_list(20000)
    synced_customers = await db_ref.customers.find({}, {"_id": 0}).to_list(5000)
    synced_map = {safe_str(c.get("customer_name")).lower(): c for c in synced_customers if c.get("customer_name")}

    customer_receipt_total = {}
    receipt_bill_allocs = {}
    for r in receipts:
        party = safe_str(r.get("party_name")).strip()
        if not party:
            continue
        amt = safe_num(r.get("amount"))
        customer_receipt_total[party] = customer_receipt_total.get(party, 0) + amt

        for alloc in r.get("bill_allocations", []):
            bill_ref = safe_str(alloc.get("bill_ref", alloc.get("name", ""))).strip()
            alloc_amt = safe_num(alloc.get("amount"))
            key = party.lower()
            if key not in receipt_bill_allocs:
                receipt_bill_allocs[key] = {}
            receipt_bill_allocs[key][bill_ref] = receipt_bill_allocs[key].get(bill_ref, 0) + alloc_amt

    overdue_invoices = []
    customer_overdue = {}

    for v in sales:
        v_date_str = v.get("voucher_date", "")
        if not v_date_str:
            continue
        try:
            parts = v_date_str.split("-")
            if len(parts) != 3:
                continue
            v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, TypeError):
            continue

        days_old = (today - v_date).days
        if days_old <= OVERDUE_THRESHOLD_DAYS:
            continue

        party = v.get("party_name", "Unknown")
        invoice_amt = safe_num(v.get("total_amount"))
        voucher_id = v.get("voucher_id", "")
        ref_number = v.get("reference_number", voucher_id)

        paid_for_invoice = 0
        allocs = receipt_bill_allocs.get(party.lower(), {})
        if ref_number and ref_number in allocs:
            paid_for_invoice = allocs[ref_number]
        elif voucher_id and voucher_id in allocs:
            paid_for_invoice = allocs[voucher_id]

        remaining = invoice_amt - paid_for_invoice
        if remaining <= 0:
            continue

        overdue_invoices.append({
            "voucher_id": voucher_id,
            "reference_number": ref_number,
            "party_name": party,
            "voucher_date": v_date_str,
            "invoice_amount": round(invoice_amt, 2),
            "paid_amount": round(paid_for_invoice, 2),
            "overdue_amount": round(remaining, 2),
            "days_overdue": days_old,
        })

        if party not in customer_overdue:
            synced = synced_map.get(party.lower(), {})
            customer_overdue[party] = {
                "customer_name": party,
                "phone": synced.get("phone", ""),
                "total_overdue": 0,
                "invoice_count": 0,
                "oldest_days": 0,
            }
        customer_overdue[party]["total_overdue"] += remaining
        customer_overdue[party]["invoice_count"] += 1
        if days_old > customer_overdue[party]["oldest_days"]:
            customer_overdue[party]["oldest_days"] = days_old

    if not receipt_bill_allocs:
        customer_invoices_map = {}
        for inv in overdue_invoices:
            p = inv["party_name"]
            customer_invoices_map.setdefault(p, []).append(inv)

        for party, invoices in customer_invoices_map.items():
            total_receipts = customer_receipt_total.get(party, 0)
            if total_receipts <= 0:
                continue
            invoices.sort(key=lambda x: x["days_overdue"], reverse=True)
            remaining_receipts = total_receipts
            for inv in invoices:
                if remaining_receipts <= 0:
                    break
                payoff = min(inv["overdue_amount"], remaining_receipts)
                inv["paid_amount"] += payoff
                inv["overdue_amount"] -= payoff
                remaining_receipts -= payoff

        overdue_invoices = [inv for inv in overdue_invoices if inv["overdue_amount"] > 0.5]
        customer_overdue = {}
        for inv in overdue_invoices:
            party = inv["party_name"]
            if party not in customer_overdue:
                synced = synced_map.get(party.lower(), {})
                customer_overdue[party] = {
                    "customer_name": party,
                    "phone": synced.get("phone", ""),
                    "total_overdue": 0,
                    "invoice_count": 0,
                    "oldest_days": 0,
                }
            customer_overdue[party]["total_overdue"] += inv["overdue_amount"]
            customer_overdue[party]["invoice_count"] += 1
            if inv["days_overdue"] > customer_overdue[party]["oldest_days"]:
                customer_overdue[party]["oldest_days"] = inv["days_overdue"]

    for c in customer_overdue.values():
        c["total_overdue"] = round(c["total_overdue"], 2)

    overdue_invoices.sort(key=lambda x: x["days_overdue"], reverse=True)
    customer_summary = sorted(customer_overdue.values(), key=lambda x: x["total_overdue"], reverse=True)

    total_overdue = round(sum(inv["overdue_amount"] for inv in overdue_invoices), 2)

    digest = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "threshold_days": OVERDUE_THRESHOLD_DAYS,
        "total_overdue_amount": total_overdue,
        "total_overdue_invoices": len(overdue_invoices),
        "total_customers_overdue": len(customer_summary),
        "customer_summary": customer_summary[:20],
        "overdue_invoices": overdue_invoices[:50],
    }

    await db_ref.overdue_digest.update_one(
        {"_type": "latest"},
        {"$set": {**digest, "_type": "latest"}},
        upsert=True
    )

    return digest


class SyncWebSocketManager:
    """Manages WebSocket connections for real-time sync status updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.last_progress: dict = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected ({len(self.active_connections)} total)")
        # Send last known progress on connect
        if self.last_progress:
            try:
                await websocket.send_text(json.dumps(self.last_progress))
            except Exception:
                pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(self.active_connections)} total)")

    async def broadcast(self, message: dict):
        self.last_progress = message
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = SyncWebSocketManager()
