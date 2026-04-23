"""Dispatch Terminal routes — Kanban board, porter management, card lifecycle, document uploads."""
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid
import os
import shutil

from db import db
from models import APIResponse
from utils import safe_num
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "dispatch")
os.makedirs(UPLOAD_DIR, exist_ok=True)

VALID_STATUSES = ["new", "queued", "processing", "packed", "dispatched", "info_shared", "hold"]
MANUAL_REASONS = ["sample", "return", "replacement", "internal_transfer", "other"]


def _q(ctx, company_id=None):
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    cid = company_id or (ctx.get("company_id") if ctx else None)
    if cid:
        q["company_id"] = cid
    return q


# ═══════════════════════════════════════════════════════
# DISPATCH CARDS
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/cards")
async def get_dispatch_cards(request: Request, status: Optional[str] = None, search: Optional[str] = None,
                              fy: Optional[str] = None, company_id: Optional[str] = None,
                              page: int = 1, limit: int = 200):
    """Get dispatch cards. Employees see all active, admins see all."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)

        if status:
            if status == "active":
                q["status"] = {"$nin": ["info_shared"]}
            else:
                q["status"] = status
        if search:
            q["$or"] = [
                {"invoice_number": {"$regex": search, "$options": "i"}},
                {"party_name": {"$regex": search, "$options": "i"}},
                {"card_id": {"$regex": search, "$options": "i"}},
                {"lr_number": {"$regex": search, "$options": "i"}},
            ]
        if fy:
            from utils import fy_to_date_range
            fy_start, fy_end = fy_to_date_range(fy)
            if fy_start:
                q["created_at"] = {"$gte": fy_start, "$lte": fy_end + "T23:59:59"}

        total = await db.dispatch_cards.count_documents(q)
        skip = (page - 1) * limit
        cards = await db.dispatch_cards.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        return APIResponse(success=True, data={"cards": cards, "total": total, "page": page})
    except Exception as e:
        logger.error(f"Get dispatch cards error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/dispatch/cards/{card_id}")
async def get_dispatch_card(card_id: str, request: Request):
    """Get single dispatch card detail."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)
        card = await db.dispatch_cards.find_one({**q, "card_id": card_id}, {"_id": 0})
        if not card:
            return APIResponse(success=False, error="Card not found")
        return APIResponse(success=True, data=card)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/cards")
async def create_manual_card(request: Request):
    """Create a manual dispatch card (samples, returns, etc.)."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()

        reason = body.get("reason", "other")
        if reason not in MANUAL_REASONS:
            return APIResponse(success=False, error=f"Invalid reason. Use: {MANUAL_REASONS}")

        card_id = f"MAN-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        # Get dispatch employees for round-robin
        tq = _q(ctx)
        dispatch_employees = await db.users.find({**tq, "role": "dispatch"}, {"_id": 0, "username": 1, "name": 1}).to_list(50)
        assigned_to = None
        if dispatch_employees:
            last_assigned = await db.dispatch_cards.find_one(tq, {"_id": 0, "assigned_to": 1}, sort=[("created_at", -1)])
            last_user = last_assigned.get("assigned_to") if last_assigned else None
            usernames = [e["username"] for e in dispatch_employees]
            if last_user and last_user in usernames:
                idx = (usernames.index(last_user) + 1) % len(usernames)
                assigned_to = usernames[idx]
            else:
                assigned_to = usernames[0]

        card = {
            "card_id": card_id,
            "card_type": "manual",
            "manual_reason": reason,
            "invoice_number": card_id,
            "party_name": body.get("party_name", ""),
            "items": body.get("items", []),
            "destination_city": body.get("destination_city", ""),
            "status": "queued" if assigned_to else "new",
            "assigned_to": assigned_to,
            "total_boxes": 0,
            "transport_name": "",
            "transport_charges": 0,
            "porter_name": "",
            "porter_charges": 0,
            "lr_number": "",
            "physical_check": False,
            "notes": body.get("notes", ""),
            "documents": {},
            "status_history": [{"status": "new", "at": now, "by": user.get("username", "")}],
            "created_at": now,
            "created_by": user.get("username", ""),
            **tq
        }
        if assigned_to:
            card["status_history"].append({"status": "queued", "at": now, "by": "system"})

        await db.dispatch_cards.insert_one(card)
        return APIResponse(success=True, data={"card_id": card_id}, message="Manual dispatch card created")
    except Exception as e:
        logger.error(f"Create manual card error: {e}")
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/cards/{card_id}/status")
async def update_card_status(card_id: str, request: Request):
    """Transition dispatch card to a new status."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        new_status = body.get("status", "").lower()

        if new_status not in VALID_STATUSES:
            return APIResponse(success=False, error=f"Invalid status. Use: {VALID_STATUSES}")

        q = _q(ctx)
        card = await db.dispatch_cards.find_one({**q, "card_id": card_id}, {"_id": 0})
        if not card:
            return APIResponse(success=False, error="Card not found")

        current = card.get("status", "new")

        # Validate physical check for packed transition
        if new_status == "packed" and not card.get("physical_check"):
            return APIResponse(success=False, error="Physical verification must be confirmed before marking as packed")

        now = datetime.now(timezone.utc).isoformat()
        update = {
            "status": new_status,
        }

        # Append to status history
        history_entry = {"status": new_status, "at": now, "by": user.get("username", "")}
        if body.get("hold_reason"):
            history_entry["reason"] = body["hold_reason"]

        await db.dispatch_cards.update_one(
            {**q, "card_id": card_id},
            {
                "$set": update,
                "$push": {"status_history": history_entry}
            }
        )

        return APIResponse(success=True, message=f"Card {card_id} moved to {new_status}")
    except Exception as e:
        logger.error(f"Update card status error: {e}")
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/cards/{card_id}")
async def update_card_fields(card_id: str, request: Request):
    """Update dispatch card fields (boxes, transport, porter, LR number, notes, etc.)."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)

        card = await db.dispatch_cards.find_one({**q, "card_id": card_id}, {"_id": 0})
        if not card:
            return APIResponse(success=False, error="Card not found")

        allowed_fields = [
            "total_boxes", "transport_name", "transport_charges",
            "porter_name", "porter_charges", "destination_city",
            "physical_check", "notes", "lr_number", "party_name", "items"
        ]
        updates = {}
        for f in allowed_fields:
            if f in body:
                updates[f] = body[f]

        if updates:
            updates["last_updated_at"] = datetime.now(timezone.utc).isoformat()
            updates["last_updated_by"] = user.get("username", "")
            await db.dispatch_cards.update_one({**q, "card_id": card_id}, {"$set": updates})

        return APIResponse(success=True, message="Card updated")
    except Exception as e:
        logger.error(f"Update card error: {e}")
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/cards/{card_id}/assign")
async def reassign_card(card_id: str, request: Request):
    """Admin: reassign card to a different dispatch employee."""
    try:
        user = await get_current_user(request, db)
        if not user or user.get("role") not in ("admin",):
            return APIResponse(success=False, error="Admin access required")
        ctx = await get_tenant_context(request)
        body = await request.json()
        assign_to = body.get("assign_to", "")

        q = _q(ctx)
        now = datetime.now(timezone.utc).isoformat()
        await db.dispatch_cards.update_one(
            {**q, "card_id": card_id},
            {
                "$set": {"assigned_to": assign_to, "last_updated_at": now},
                "$push": {"status_history": {"status": "reassigned", "at": now, "by": user.get("username", ""), "assigned_to": assign_to}}
            }
        )
        return APIResponse(success=True, message=f"Card reassigned to {assign_to}")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DOCUMENT UPLOADS
# ═══════════════════════════════════════════════════════

@router.post("/dispatch/cards/{card_id}/upload/{doc_type}")
async def upload_document(card_id: str, doc_type: str, request: Request, file: UploadFile = File(...)):
    """Upload a document (invoice_doc, sales_order, lr_receipt) for a dispatch card."""
    try:
        if doc_type not in ("invoice_doc", "sales_order", "lr_receipt"):
            return APIResponse(success=False, error="doc_type must be: invoice_doc, sales_order, lr_receipt")

        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        q = _q(ctx)

        card = await db.dispatch_cards.find_one({**q, "card_id": card_id}, {"_id": 0, "card_id": 1})
        if not card:
            return APIResponse(success=False, error="Card not found")

        # Save file
        ext = os.path.splitext(file.filename)[1] or ".jpg"
        filename = f"{card_id}_{doc_type}_{uuid.uuid4().hex[:6]}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)

        file_url = f"/api/dispatch/files/{filename}"

        await db.dispatch_cards.update_one(
            {**q, "card_id": card_id},
            {"$set": {f"documents.{doc_type}": {"filename": filename, "url": file_url, "uploaded_at": datetime.now(timezone.utc).isoformat(), "uploaded_by": user.get("username", "")}}}
        )

        return APIResponse(success=True, data={"url": file_url, "filename": filename}, message=f"{doc_type} uploaded")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/dispatch/files/{filename}")
async def serve_file(filename: str):
    """Serve uploaded dispatch documents."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return APIResponse(success=False, error="File not found")
    return FileResponse(filepath)


# ═══════════════════════════════════════════════════════
# PORTER MANAGEMENT
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/porters")
async def get_porters(request: Request):
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)
        porters = await db.dispatch_porters.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        return APIResponse(success=True, data={"porters": porters})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/porters")
async def create_porter(request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)

        porter = {
            "porter_id": f"PRT-{uuid.uuid4().hex[:6].upper()}",
            "name": body.get("name", "").strip(),
            "phone": body.get("phone", "").strip(),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **q
        }
        if not porter["name"]:
            return APIResponse(success=False, error="Porter name required")

        await db.dispatch_porters.insert_one(porter)
        return APIResponse(success=True, data={"porter_id": porter["porter_id"]}, message="Porter added")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/porters/{porter_id}")
async def update_porter(porter_id: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)
        updates = {}
        for f in ("name", "phone", "is_active"):
            if f in body:
                updates[f] = body[f]
        if updates:
            await db.dispatch_porters.update_one({**q, "porter_id": porter_id}, {"$set": updates})
        return APIResponse(success=True, message="Porter updated")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# PORTER SETTLEMENT
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/porter-settlement")
async def get_porter_settlement(request: Request, period: Optional[str] = "week"):
    """Get porter settlement summary — total charges, payments, balance."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)

        porters = await db.dispatch_porters.find(q, {"_id": 0}).to_list(200)
        payments = await db.dispatch_porter_payments.find(q, {"_id": 0}).to_list(1000)
        cards = await db.dispatch_cards.find({**q, "porter_name": {"$ne": ""}, "status": {"$in": ["dispatched", "info_shared"]}}, {"_id": 0, "porter_name": 1, "porter_charges": 1, "created_at": 1}).to_list(5000)

        porter_totals = {}
        for c in cards:
            name = c.get("porter_name", "")
            if name:
                porter_totals.setdefault(name, {"total_charges": 0, "dispatch_count": 0})
                porter_totals[name]["total_charges"] += safe_num(c.get("porter_charges"))
                porter_totals[name]["dispatch_count"] += 1

        porter_payments = {}
        for p in payments:
            name = p.get("porter_name", "")
            porter_payments.setdefault(name, 0)
            porter_payments[name] += safe_num(p.get("amount"))

        settlement = []
        for porter in porters:
            name = porter.get("name", "")
            charges = porter_totals.get(name, {}).get("total_charges", 0)
            paid = porter_payments.get(name, 0)
            settlement.append({
                "porter_id": porter.get("porter_id"),
                "name": name,
                "phone": porter.get("phone", ""),
                "total_charges": round(charges, 2),
                "total_paid": round(paid, 2),
                "balance_due": round(charges - paid, 2),
                "dispatch_count": porter_totals.get(name, {}).get("dispatch_count", 0),
            })

        return APIResponse(success=True, data={"settlement": settlement})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/porter-payment")
async def record_porter_payment(request: Request):
    """Record a payment to a porter."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)

        payment = {
            "payment_id": f"PP-{uuid.uuid4().hex[:6].upper()}",
            "porter_name": body.get("porter_name", ""),
            "amount": float(body.get("amount", 0)),
            "payment_ref": body.get("payment_ref", ""),
            "notes": body.get("notes", ""),
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "paid_by": user.get("username", ""),
            **q
        }
        await db.dispatch_porter_payments.insert_one(payment)
        return APIResponse(success=True, message="Payment recorded")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DISPATCH EMPLOYEES
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/employees")
async def get_dispatch_employees(request: Request):
    """Get list of dispatch role employees."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)
        employees = await db.users.find({**q, "role": "dispatch"}, {"_id": 0, "password_hash": 0}).to_list(50)
        return APIResponse(success=True, data={"employees": employees})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# CLOSE OF DAY & SUMMARY
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/summary")
async def get_dispatch_summary(request: Request, date: Optional[str] = None, company_id: Optional[str] = None):
    """Get dispatch summary for a day (default: today)."""
    try:
        from datetime import date as date_type
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)

        target_date = date or date_type.today().isoformat()
        day_start = f"{target_date}T00:00:00"
        day_end = f"{target_date}T23:59:59"

        # All cards with activity today
        all_cards = await db.dispatch_cards.find(q, {"_id": 0}).to_list(10000)

        today_dispatched = [c for c in all_cards if c.get("status") in ("dispatched", "info_shared") and any(
            h.get("status") in ("dispatched",) and h.get("at", "") >= day_start and h.get("at", "") <= day_end
            for h in c.get("status_history", [])
        )]
        pending = [c for c in all_cards if c.get("status") in ("new", "queued", "processing", "packed")]
        on_hold = [c for c in all_cards if c.get("status") == "hold"]

        total_value = sum(safe_num(c.get("total_amount", 0)) for c in today_dispatched)
        total_boxes = sum(safe_num(c.get("total_boxes", 0)) for c in today_dispatched)
        total_transport = sum(safe_num(c.get("transport_charges", 0)) for c in today_dispatched)
        total_porter = sum(safe_num(c.get("porter_charges", 0)) for c in today_dispatched)

        # Transport-wise breakdown
        transport_wise = {}
        for c in today_dispatched:
            t = c.get("transport_name", "Unknown")
            transport_wise.setdefault(t, {"count": 0, "charges": 0})
            transport_wise[t]["count"] += 1
            transport_wise[t]["charges"] += safe_num(c.get("transport_charges", 0))

        # Employee-wise
        employee_wise = {}
        for c in today_dispatched:
            e = c.get("assigned_to", "Unassigned")
            employee_wise.setdefault(e, {"count": 0})
            employee_wise[e]["count"] += 1

        return APIResponse(success=True, data={
            "date": target_date,
            "dispatched_count": len(today_dispatched),
            "pending_count": len(pending),
            "hold_count": len(on_hold),
            "total_value": round(total_value, 2),
            "total_boxes": int(total_boxes),
            "total_transport_charges": round(total_transport, 2),
            "total_porter_charges": round(total_porter, 2),
            "transport_breakdown": [{"name": k, **v} for k, v in transport_wise.items()],
            "employee_breakdown": [{"name": k, **v} for k, v in employee_wise.items()],
            "dispatched_cards": today_dispatched,
            "pending_cards": pending,
            "hold_cards": on_hold,
        })
    except Exception as e:
        logger.error(f"Dispatch summary error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# AUTO-CREATE CARDS FROM SYNCED INVOICES
# ═══════════════════════════════════════════════════════

@router.post("/dispatch/auto-create")
async def auto_create_from_invoices(request: Request):
    """Create dispatch cards for new sales invoices that don't have cards yet."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)

        # Get all existing card invoice numbers
        existing = await db.dispatch_cards.distinct("invoice_number", q)
        existing_set = set(existing)

        # Get sales vouchers not yet having cards
        sales = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
        new_sales = [s for s in sales if s.get("voucher_id") not in existing_set and s.get("reference_number") not in existing_set]

        if not new_sales:
            return APIResponse(success=True, data={"created": 0}, message="No new invoices to create cards for")

        # Get dispatch employees for round-robin
        dispatch_employees = await db.users.find({**q, "role": "dispatch"}, {"_id": 0, "username": 1}).to_list(50)
        usernames = [e["username"] for e in dispatch_employees]

        last_assigned = await db.dispatch_cards.find_one(q, {"_id": 0, "assigned_to": 1}, sort=[("created_at", -1)])
        last_idx = 0
        if last_assigned and last_assigned.get("assigned_to") in usernames:
            last_idx = usernames.index(last_assigned["assigned_to"])

        now = datetime.now(timezone.utc).isoformat()
        created = 0
        for i, sale in enumerate(new_sales):
            inv_num = sale.get("reference_number") or sale.get("voucher_id", "")
            assigned = None
            if usernames:
                assigned = usernames[(last_idx + i + 1) % len(usernames)]

            card = {
                "card_id": f"DSP-{uuid.uuid4().hex[:8].upper()}",
                "card_type": "invoice",
                "invoice_number": inv_num,
                "voucher_id": sale.get("voucher_id", ""),
                "party_name": sale.get("party_name", ""),
                "items": sale.get("items", []),
                "total_amount": safe_num(sale.get("total_amount")),
                "voucher_date": sale.get("voucher_date", ""),
                "salesman": sale.get("salesman", ""),
                "destination_city": "",
                "status": "queued" if assigned else "new",
                "assigned_to": assigned,
                "total_boxes": 0,
                "transport_name": "",
                "transport_charges": 0,
                "porter_name": "",
                "porter_charges": 0,
                "lr_number": "",
                "physical_check": False,
                "notes": "",
                "documents": {},
                "status_history": [
                    {"status": "new", "at": now, "by": "system"},
                    *([{"status": "queued", "at": now, "by": "system"}] if assigned else []),
                ],
                "created_at": now,
                "created_by": "system",
                **q
            }
            await db.dispatch_cards.insert_one(card)
            created += 1

        return APIResponse(success=True, data={"created": created}, message=f"{created} dispatch cards created")
    except Exception as e:
        logger.error(f"Auto-create error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DISPATCH HISTORY (Permanent searchable archive)
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/history")
async def get_dispatch_history(request: Request, search: Optional[str] = None, page: int = 1, limit: int = 50, company_id: Optional[str] = None):
    """Permanent searchable archive of all dispatch cards with documents."""
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        q["status"] = {"$in": ["dispatched", "info_shared"]}

        if search:
            q["$or"] = [
                {"invoice_number": {"$regex": search, "$options": "i"}},
                {"party_name": {"$regex": search, "$options": "i"}},
                {"card_id": {"$regex": search, "$options": "i"}},
                {"lr_number": {"$regex": search, "$options": "i"}},
                {"transport_name": {"$regex": search, "$options": "i"}},
            ]

        total = await db.dispatch_cards.count_documents(q)
        skip = (page - 1) * limit
        cards = await db.dispatch_cards.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        return APIResponse(success=True, data={"cards": cards, "total": total, "page": page, "total_pages": (total + limit - 1) // limit})
    except Exception as e:
        return APIResponse(success=False, error=str(e))
