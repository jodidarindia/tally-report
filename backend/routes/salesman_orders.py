"""Salesman Order System — order placement, admin approval, dispatch integration."""
from fastapi import APIRouter, Request
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid

from db import db
from models import APIResponse
from utils import safe_num, fy_to_date_range, get_current_fy
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()

ORDER_STATUSES = ["pending", "approved", "rejected", "billed", "hold"]


def _q(ctx, company_id=None):
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    cid = company_id or (ctx.get("company_id") if ctx else None)
    if cid:
        q["company_id"] = cid
    return q


# ═══════════════════════════════════════════════════════
# SALESMAN: MAPPED CUSTOMERS
# ═══════════════════════════════════════════════════════

@router.get("/salesman-orders/my-customers")
async def get_my_customers(request: Request, company_id: Optional[str] = None):
    """Get customers mapped to the logged-in salesman."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        fy = get_current_fy()

        master = await db.salesman_master.find_one(
            {**q, "salesman_name": user.get("name", "")}, {"_id": 0})
        if not master:
            master = await db.salesman_master.find_one(
                {**q, "salesman_name": {"$regex": f"^{user.get('name', '')}$", "$options": "i"}}, {"_id": 0})

        if not master:
            return APIResponse(success=True, data={"customers": [], "message": "No salesman mapping found"})

        fy_customers = master.get("fy_customers", {}).get(fy, master.get("customers", []))
        customer_details = []
        for name in fy_customers:
            cust = await db.customers.find_one({**q, "customer_name": name}, {"_id": 0, "customer_name": 1, "phone": 1, "state": 1, "opening_balance": 1})
            customer_details.append({
                "customer_name": name,
                "phone": cust.get("phone", "") if cust else "",
                "state": cust.get("state", "") if cust else "",
            })

        return APIResponse(success=True, data={"customers": customer_details, "salesman_name": master.get("salesman_name")})
    except Exception as e:
        logger.error(f"Get my customers error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# PRODUCT CATALOG (from inventory)
# ═══════════════════════════════════════════════════════

@router.get("/salesman-orders/catalog")
async def get_catalog(request: Request, search: Optional[str] = None, company_id: Optional[str] = None):
    """Get product catalog with real-time stock & Tally price."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        inv_q = {**q}
        if search:
            inv_q["item_name"] = {"$regex": search, "$options": "i"}
        items = await db.inventory_items.find(inv_q, {"_id": 0}).sort("item_name", 1).to_list(500)
        catalog = [{
            "item_name": it.get("item_name", ""),
            "item_id": it.get("item_id", ""),
            "part_number": it.get("part_number", ""),
            "stock_qty": safe_num(it.get("quantity", 0)),
            "price": safe_num(it.get("price", 0)),
            "unit": it.get("unit", ""),
            "stock_group": it.get("stock_group", ""),
        } for it in items]
        return APIResponse(success=True, data={"items": catalog, "total": len(catalog)})
    except Exception as e:
        logger.error(f"Catalog error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# ORDER CRUD
# ═══════════════════════════════════════════════════════

@router.post("/salesman-orders/orders")
async def create_order(request: Request):
    """Salesman creates a new order for a customer."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)

        customer_name = (body.get("customer_name") or "").strip()
        items = body.get("items", [])
        if not customer_name:
            return APIResponse(success=False, error="Customer name required")
        if not items or len(items) == 0:
            return APIResponse(success=False, error="At least one item required")

        order_items = []
        total = 0
        for it in items:
            qty = safe_num(it.get("quantity", 0))
            price = safe_num(it.get("price", 0))
            amt = round(qty * price, 2)
            total += amt
            order_items.append({
                "item_name": it.get("item_name", ""),
                "quantity": qty,
                "price": price,
                "amount": amt,
                "unit": it.get("unit", ""),
                "remark": (it.get("remark") or "").strip(),
            })

        now = datetime.now(timezone.utc).isoformat()
        order = {
            "order_id": f"SO-{uuid.uuid4().hex[:8].upper()}",
            "salesman": user.get("name", user.get("username", "")),
            "salesman_username": user.get("username", ""),
            "customer_name": customer_name,
            "items": order_items,
            "total_amount": round(total, 2),
            "status": "pending",
            "notes": (body.get("notes") or "").strip(),
            "admin_notes": "",
            "invoice_number": "",
            "created_at": now,
            "updated_at": now,
            "status_history": [{"status": "pending", "at": now, "by": user.get("username", "")}],
            **q
        }
        await db.salesman_orders.insert_one(order)
        return APIResponse(success=True, data={"order_id": order["order_id"]}, message="Order submitted for approval")
    except Exception as e:
        logger.error(f"Create order error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/salesman-orders/orders")
async def get_orders(request: Request, status: Optional[str] = None, search: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None,
                     salesman: Optional[str] = None, company_id: Optional[str] = None,
                     page: int = 1, limit: int = 100):
    """Get orders. Salesman sees own, admin sees all."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)

        if user.get("role") == "salesman":
            q["salesman_username"] = user.get("username", "")

        if status:
            q["status"] = status
        if salesman:
            q["salesman"] = {"$regex": salesman, "$options": "i"}
        if search:
            q["$or"] = [
                {"order_id": {"$regex": search, "$options": "i"}},
                {"customer_name": {"$regex": search, "$options": "i"}},
                {"invoice_number": {"$regex": search, "$options": "i"}},
            ]
        if date_from:
            q.setdefault("created_at", {})["$gte"] = f"{date_from}T00:00:00"
        if date_to:
            q.setdefault("created_at", {})["$lte"] = f"{date_to}T23:59:59"

        total = await db.salesman_orders.count_documents(q)
        skip = (page - 1) * limit
        orders = await db.salesman_orders.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        return APIResponse(success=True, data={"orders": orders, "total": total, "page": page})
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/salesman-orders/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        order = await db.salesman_orders.find_one({**_q(ctx), "order_id": order_id}, {"_id": 0})
        if not order:
            return APIResponse(success=False, error="Order not found")
        return APIResponse(success=True, data=order)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.patch("/salesman-orders/orders/{order_id}")
async def update_order(order_id: str, request: Request):
    """Salesman edits order — only if status is 'pending'."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)

        order = await db.salesman_orders.find_one({**q, "order_id": order_id}, {"_id": 0})
        if not order:
            return APIResponse(success=False, error="Order not found")
        if order.get("status") != "pending":
            return APIResponse(success=False, error="Cannot edit order after approval. Only pending orders can be modified.")

        updates = {}
        if "items" in body:
            items = body["items"]
            total = 0
            order_items = []
            for it in items:
                qty = safe_num(it.get("quantity", 0))
                price = safe_num(it.get("price", 0))
                amt = round(qty * price, 2)
                total += amt
                order_items.append({
                    "item_name": it.get("item_name", ""),
                    "quantity": qty, "price": price, "amount": amt,
                    "unit": it.get("unit", ""), "remark": (it.get("remark") or "").strip(),
                })
            updates["items"] = order_items
            updates["total_amount"] = round(total, 2)
        if "notes" in body:
            updates["notes"] = body["notes"]
        if "customer_name" in body:
            updates["customer_name"] = body["customer_name"]

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.salesman_orders.update_one({**q, "order_id": order_id}, {"$set": updates})

        return APIResponse(success=True, message="Order updated")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# ADMIN: APPROVE / REJECT / HOLD / BILL
# ═══════════════════════════════════════════════════════

@router.patch("/salesman-orders/orders/{order_id}/status")
async def update_order_status(order_id: str, request: Request):
    """Admin changes order status: approve, reject, hold, billed."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        new_status = (body.get("status") or "").lower()

        if new_status not in ORDER_STATUSES:
            return APIResponse(success=False, error=f"Invalid status")

        q = _q(ctx)
        order = await db.salesman_orders.find_one({**q, "order_id": order_id}, {"_id": 0})
        if not order:
            return APIResponse(success=False, error="Order not found")

        now = datetime.now(timezone.utc).isoformat()
        update_fields = {"status": new_status, "updated_at": now}

        if new_status == "rejected":
            reject_reason = (body.get("reject_reason") or "").strip()
            if not reject_reason:
                return APIResponse(success=False, error="Rejection reason is required")

        if new_status == "billed":
            invoice_number = (body.get("invoice_number") or "").strip()
            if not invoice_number:
                return APIResponse(success=False, error="Invoice number required for billing")
            update_fields["invoice_number"] = invoice_number

        if body.get("admin_notes"):
            update_fields["admin_notes"] = body["admin_notes"]

        entry = {"status": new_status, "at": now, "by": user.get("username", "")}
        if body.get("reject_reason"):
            entry["reason"] = body["reject_reason"]

        await db.salesman_orders.update_one({**q, "order_id": order_id},
            {"$set": update_fields, "$push": {"status_history": entry}})

        return APIResponse(success=True, message=f"Order {order_id} marked as {new_status}")
    except Exception as e:
        logger.error(f"Update order status error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# ADMIN: ORDER STATS
# ═══════════════════════════════════════════════════════

@router.get("/salesman-orders/stats")
async def get_order_stats(request: Request, company_id: Optional[str] = None):
    """Get order counts by status for admin dashboard."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        pipeline = [
            {"$match": q},
            {"$group": {"_id": "$status", "count": {"$sum": 1}, "total": {"$sum": "$total_amount"}}}
        ]
        results = await db.salesman_orders.aggregate(pipeline).to_list(20)
        stats = {r["_id"]: {"count": r["count"], "total": round(r["total"], 2)} for r in results}
        return APIResponse(success=True, data={"stats": stats})
    except Exception as e:
        return APIResponse(success=False, error=str(e))



# ═══════════════════════════════════════════════════════
# PENDING BILLING — Approved orders not yet billed + item verification
# ═══════════════════════════════════════════════════════

@router.get("/salesman-orders/pending-billing")
async def get_pending_billing(request: Request, company_id: Optional[str] = None):
    """Get approved orders pending billing, grouped by customer with item details.
    Also for billed orders, compare order items vs actual Tally invoice items."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)

        # Approved orders (pending billing)
        approved = await db.salesman_orders.find(
            {**q, "status": "approved"}, {"_id": 0}
        ).sort("created_at", 1).to_list(500)

        # Billed orders — for verification
        billed = await db.salesman_orders.find(
            {**q, "status": "billed", "invoice_number": {"$ne": ""}}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)

        # Group approved by customer
        pending_by_customer = {}
        for o in approved:
            cust = o.get("customer_name", "Unknown")
            pending_by_customer.setdefault(cust, {"orders": [], "total_items": [], "total_amount": 0})
            pending_by_customer[cust]["orders"].append({
                "order_id": o.get("order_id"),
                "salesman": o.get("salesman", ""),
                "created_at": o.get("created_at", ""),
                "total_amount": o.get("total_amount", 0),
                "items": o.get("items", []),
            })
            pending_by_customer[cust]["total_amount"] += safe_num(o.get("total_amount", 0))
            for it in o.get("items", []):
                pending_by_customer[cust]["total_items"].append({
                    "item_name": it.get("item_name", ""),
                    "quantity": safe_num(it.get("quantity", 0)),
                    "price": safe_num(it.get("price", 0)),
                    "remark": it.get("remark", ""),
                    "order_id": o.get("order_id"),
                })

        pending_list = []
        for cust, data in sorted(pending_by_customer.items()):
            # Aggregate items by name
            item_agg = {}
            for it in data["total_items"]:
                name = it["item_name"]
                item_agg.setdefault(name, {"item_name": name, "total_qty": 0, "price": it["price"], "orders": []})
                item_agg[name]["total_qty"] += it["quantity"]
                item_agg[name]["orders"].append(it["order_id"])
            pending_list.append({
                "customer_name": cust,
                "order_count": len(data["orders"]),
                "total_amount": round(data["total_amount"], 2),
                "items": list(item_agg.values()),
                "orders": data["orders"],
            })

        # Billed verification — compare order items vs Tally invoice
        verified = []
        for o in billed[:50]:
            inv_num = o.get("invoice_number", "")
            if not inv_num:
                continue
            # Find matching Tally invoice
            tally_inv = await db.sales_vouchers.find_one(
                {**q, "$or": [{"voucher_id": inv_num}, {"reference_number": inv_num}]},
                {"_id": 0, "items": 1, "party_name": 1, "total_amount": 1, "voucher_id": 1}
            )
            order_items = {it.get("item_name", ""): safe_num(it.get("quantity", 0)) for it in o.get("items", [])}
            invoice_items = {}
            if tally_inv:
                for it in tally_inv.get("items", []):
                    name = it.get("item") or it.get("item_name") or ""
                    invoice_items[name] = safe_num(it.get("quantity", 0))

            # Compare
            all_items = set(list(order_items.keys()) + list(invoice_items.keys()))
            discrepancies = []
            for name in all_items:
                oq = order_items.get(name, 0)
                iq = invoice_items.get(name, 0)
                if abs(oq - iq) > 0.01:
                    discrepancies.append({"item_name": name, "ordered": oq, "billed": iq, "diff": round(iq - oq, 2)})

            verified.append({
                "order_id": o.get("order_id"),
                "invoice_number": inv_num,
                "customer_name": o.get("customer_name", ""),
                "tally_matched": tally_inv is not None,
                "match_status": "matched" if not discrepancies and tally_inv else ("discrepancy" if discrepancies else "not_synced"),
                "discrepancies": discrepancies,
            })

        return APIResponse(success=True, data={
            "pending": pending_list,
            "pending_count": len(approved),
            "verified": verified,
        })
    except Exception as e:
        logger.error(f"Pending billing error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# BEAT MANAGEMENT
# ═══════════════════════════════════════════════════════

@router.get("/salesman-orders/beats")
async def get_beats(request: Request, salesman: Optional[str] = None, company_id: Optional[str] = None):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        if user.get("role") == "salesman":
            q["salesman"] = user.get("name", "")
        elif salesman:
            q["salesman"] = salesman
        beats = await db.salesman_beats.find(q, {"_id": 0}).to_list(500)
        return APIResponse(success=True, data={"beats": beats})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/salesman-orders/beats")
async def save_beats(request: Request):
    """Admin saves beat plan for a salesman."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)
        salesman = body.get("salesman", "")
        beats = body.get("beats", [])

        await db.salesman_beats.delete_many({**q, "salesman": salesman})
        now = datetime.now(timezone.utc).isoformat()
        for b in beats:
            await db.salesman_beats.insert_one({
                "beat_id": f"BT-{uuid.uuid4().hex[:6].upper()}",
                "salesman": salesman,
                "customer_name": b.get("customer_name", ""),
                "day_of_week": b.get("day_of_week", ""),
                "frequency": b.get("frequency", "weekly"),
                "created_at": now,
                **q
            })

        return APIResponse(success=True, message=f"{len(beats)} beats saved")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/salesman-orders/beats/{beat_id}/visit")
async def mark_visited(beat_id: str, request: Request):
    """Salesman marks a beat customer as visited."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        now = datetime.now(timezone.utc).isoformat()
        await db.salesman_beats.update_one(
            {**_q(ctx), "beat_id": beat_id},
            {"$push": {"visits": {"at": now, "by": user.get("username", "")}}}
        )
        return APIResponse(success=True, message="Visit recorded")
    except Exception as e:
        return APIResponse(success=False, error=str(e))
