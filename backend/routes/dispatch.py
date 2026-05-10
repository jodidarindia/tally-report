"""Dispatch Terminal routes — Kanban board, porter/transport management, card lifecycle, document uploads."""
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid
import os

from db import db
from models import APIResponse
from utils import safe_num, build_fuzzy_regex
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "dispatch")
os.makedirs(UPLOAD_DIR, exist_ok=True)

VALID_STATUSES = ["new", "queued", "processing", "packed", "dispatched", "info_shared", "hold", "cancelled"]
MANUAL_REASONS = ["sample", "return", "replacement", "internal_transfer", "other"]
CANCELLABLE_STATUSES = ["new", "queued", "processing", "packed"]
CANCEL_REASONS = ["customer_request", "payment_issue", "stock_unavailable", "duplicate", "invoice_modified", "other"]


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
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        if status:
            if status == "active":
                # Active board excludes shipped (info_shared) and old cancelled
                # cards. Cards cancelled TODAY (IST) remain visible with a
                # strikethrough; they auto-hide after end-of-day.
                from datetime import timedelta
                ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
                today_ist_start_utc = (ist_now.replace(hour=0, minute=0, second=0, microsecond=0)
                                       - timedelta(hours=5, minutes=30)).isoformat()
                q["$or"] = [
                    {"status": {"$nin": ["info_shared", "cancelled"]}},
                    {"status": "cancelled", "cancelled_at": {"$gte": today_ist_start_utc}},
                ]
            else:
                q["status"] = status
        if search:
            fuzzy = build_fuzzy_regex(search)
            if fuzzy:
                # Combine with any existing $or (active filter); use $and wrapper
                search_or = [
                    {"invoice_number": {"$regex": fuzzy, "$options": "i"}},
                    {"party_name": {"$regex": fuzzy, "$options": "i"}},
                    {"card_id": {"$regex": fuzzy, "$options": "i"}},
                    {"lr_number": {"$regex": fuzzy, "$options": "i"}},
                ]
                if "$or" in q:
                    existing_or = q.pop("$or")
                    q["$and"] = [{"$or": existing_or}, {"$or": search_or}]
                else:
                    q["$or"] = search_or
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
    try:
        ctx = await get_tenant_context(request)
        card = await db.dispatch_cards.find_one({**_q(ctx), "card_id": card_id}, {"_id": 0})
        if not card:
            return APIResponse(success=False, error="Card not found")
        return APIResponse(success=True, data=card)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/cards")
async def create_manual_card(request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        reason = body.get("reason", "other")
        if reason not in MANUAL_REASONS:
            return APIResponse(success=False, error=f"Invalid reason. Use: {MANUAL_REASONS}")

        tq = _q(ctx)
        assigned = await _round_robin_assign(tq)
        card_id = f"MAN-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        card = {
            "card_id": card_id, "card_type": "manual", "manual_reason": reason,
            "invoice_number": card_id, "party_name": body.get("party_name", ""),
            "items": body.get("items", []), "destination_city": body.get("destination_city", ""),
            "status": "queued" if assigned else "new", "assigned_to": assigned,
            "total_boxes": 0, "transport_name": "", "transport_charges": 0,
            "porter_name": "", "porter_charges": 0, "lr_number": "",
            "physical_check": False, "notes": body.get("notes", ""),
            "documents": {},
            "status_history": [{"status": "new", "at": now, "by": user.get("username", "")},
                               *([ {"status": "queued", "at": now, "by": "system"} ] if assigned else [])],
            "created_at": now, "created_by": user.get("username", ""), **tq
        }
        await db.dispatch_cards.insert_one(card)
        return APIResponse(success=True, data={"card_id": card_id}, message="Manual dispatch card created")
    except Exception as e:
        logger.error(f"Create manual card error: {e}")
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/cards/{card_id}/status")
async def update_card_status(card_id: str, request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        new_status = body.get("status", "").lower()
        if new_status not in VALID_STATUSES:
            return APIResponse(success=False, error="Invalid status")
        if new_status == "cancelled":
            return APIResponse(success=False, error="Use POST /dispatch/cards/{card_id}/cancel to cancel a card")
        q = _q(ctx)
        card = await db.dispatch_cards.find_one({**q, "card_id": card_id}, {"_id": 0})
        if not card:
            return APIResponse(success=False, error="Card not found")
        if card.get("status") == "cancelled":
            return APIResponse(success=False, error="Cancelled cards cannot be reopened")
        if new_status == "packed" and not card.get("physical_check"):
            return APIResponse(success=False, error="Physical verification must be confirmed before marking as packed")
        now = datetime.now(timezone.utc).isoformat()
        entry = {"status": new_status, "at": now, "by": user.get("username", "")}
        if body.get("hold_reason"):
            entry["reason"] = body["hold_reason"]
        await db.dispatch_cards.update_one({**q, "card_id": card_id},
            {"$set": {"status": new_status}, "$push": {"status_history": entry}})
        return APIResponse(success=True, message=f"Card {card_id} moved to {new_status}")
    except Exception as e:
        logger.error(f"Update card status error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/cards/{card_id}/cancel")
async def cancel_card(card_id: str, request: Request):
    """Cancel a dispatch card. Allowed only when current status is one of
    {new, queued, processing, packed} — once the truck has left (dispatched
    / info_shared) cancellation is blocked. Terminal: a cancelled card
    cannot be reopened. All authenticated dispatch / admin users may cancel.
    Body: { "reason": <CANCEL_REASONS>, "notes": "<free text>" }
    """
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")
        ctx = await get_tenant_context(request)
        body = await request.json()
        reason = (body.get("reason") or "other").lower().strip()
        if reason not in CANCEL_REASONS:
            return APIResponse(success=False, error=f"Invalid reason. Use one of: {CANCEL_REASONS}")
        notes = (body.get("notes") or "").strip()

        q = _q(ctx)
        card = await db.dispatch_cards.find_one({**q, "card_id": card_id}, {"_id": 0})
        if not card:
            return APIResponse(success=False, error="Card not found")
        cur = card.get("status", "")
        if cur == "cancelled":
            return APIResponse(success=False, error="Card is already cancelled")
        if cur not in CANCELLABLE_STATUSES:
            return APIResponse(
                success=False,
                error=f"Cannot cancel a card in '{cur}' status. Cancellation is allowed only up to 'packed' lane.",
            )

        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "status": "cancelled", "at": now, "by": user.get("username", ""),
            "reason": reason, "notes": notes, "from_status": cur,
        }
        await db.dispatch_cards.update_one(
            {**q, "card_id": card_id},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": now,
                    "cancelled_by": user.get("username", ""),
                    "cancel_reason": reason,
                    "cancel_notes": notes,
                    "cancelled_from_status": cur,
                },
                "$push": {"status_history": entry},
            },
        )
        return APIResponse(success=True, message=f"Card {card_id} cancelled", data={"card_id": card_id, "reason": reason})
    except Exception as e:
        logger.error(f"Cancel card error: {e}")
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/cards/{card_id}")
async def update_card_fields(card_id: str, request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)
        allowed = ["total_boxes", "transport_name", "transport_charges", "porter_name",
                    "porter_charges", "destination_city", "physical_check", "notes",
                    "lr_number", "party_name", "items"]
        updates = {f: body[f] for f in allowed if f in body}
        if updates:
            updates["last_updated_at"] = datetime.now(timezone.utc).isoformat()
            updates["last_updated_by"] = user.get("username", "")
            await db.dispatch_cards.update_one({**q, "card_id": card_id}, {"$set": updates})
        return APIResponse(success=True, message="Card updated")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/cards/{card_id}/assign")
async def reassign_card(card_id: str, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user.get("role") not in ("admin",):
            return APIResponse(success=False, error="Admin access required")
        ctx = await get_tenant_context(request)
        body = await request.json()
        now = datetime.now(timezone.utc).isoformat()
        await db.dispatch_cards.update_one({**_q(ctx), "card_id": card_id},
            {"$set": {"assigned_to": body.get("assign_to", ""), "last_updated_at": now},
             "$push": {"status_history": {"status": "reassigned", "at": now, "by": user.get("username", ""), "assigned_to": body.get("assign_to", "")}}})
        return APIResponse(success=True, message="Card reassigned")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DOCUMENT UPLOADS
# ═══════════════════════════════════════════════════════

@router.post("/dispatch/cards/{card_id}/upload/{doc_type}")
async def upload_document(card_id: str, doc_type: str, request: Request, file: UploadFile = File(...)):
    try:
        if doc_type not in ("invoice_doc", "sales_order", "lr_receipt"):
            return APIResponse(success=False, error="doc_type must be: invoice_doc, sales_order, lr_receipt")
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        card = await db.dispatch_cards.find_one({**_q(ctx), "card_id": card_id}, {"_id": 0, "card_id": 1})
        if not card:
            return APIResponse(success=False, error="Card not found")
        ext = os.path.splitext(file.filename)[1] or ".jpg"
        filename = f"{card_id}_{doc_type}_{uuid.uuid4().hex[:6]}{ext}"
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
            f.write(await file.read())
        file_url = f"/api/dispatch/files/{filename}"
        await db.dispatch_cards.update_one({**_q(ctx), "card_id": card_id},
            {"$set": {f"documents.{doc_type}": {"filename": filename, "url": file_url,
                      "uploaded_at": datetime.now(timezone.utc).isoformat(), "uploaded_by": user.get("username", "")}}})
        return APIResponse(success=True, data={"url": file_url, "filename": filename})
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/dispatch/files/{filename}")
async def serve_file(filename: str):
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
        porters = await db.dispatch_porters.find(_q(ctx), {"_id": 0}).sort("name", 1).to_list(200)
        return APIResponse(success=True, data={"porters": porters})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/porters")
async def create_porter(request: Request):
    try:
        await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return APIResponse(success=False, error="Porter name required")
        porter = {"porter_id": f"PRT-{uuid.uuid4().hex[:6].upper()}", "name": name,
                  "phone": (body.get("phone") or "").strip(), "is_active": True,
                  "created_at": datetime.now(timezone.utc).isoformat(), **_q(ctx)}
        await db.dispatch_porters.insert_one(porter)
        return APIResponse(success=True, data={"porter_id": porter["porter_id"], "name": name}, message="Porter added")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/porters/{porter_id}")
async def update_porter(porter_id: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        body = await request.json()
        updates = {f: body[f] for f in ("name", "phone", "is_active") if f in body}
        if updates:
            await db.dispatch_porters.update_one({**_q(ctx), "porter_id": porter_id}, {"$set": updates})
        return APIResponse(success=True, message="Porter updated")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# TRANSPORT MANAGEMENT
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/transporters")
async def get_transporters(request: Request):
    try:
        ctx = await get_tenant_context(request)
        items = await db.dispatch_transporters.find(_q(ctx), {"_id": 0}).sort("name", 1).to_list(200)
        return APIResponse(success=True, data={"transporters": items})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/transporters")
async def create_transporter(request: Request):
    try:
        await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return APIResponse(success=False, error="Transporter name required")
        t = {"transporter_id": f"TRN-{uuid.uuid4().hex[:6].upper()}", "name": name,
             "phone": (body.get("phone") or "").strip(), "is_active": True,
             "created_at": datetime.now(timezone.utc).isoformat(), **_q(ctx)}
        await db.dispatch_transporters.insert_one(t)
        return APIResponse(success=True, data={"transporter_id": t["transporter_id"], "name": name}, message="Transporter added")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# PORTER SETTLEMENT
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/porter-settlement")
async def get_porter_settlement(request: Request):
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)
        porters = await db.dispatch_porters.find(q, {"_id": 0}).to_list(200)
        payments = await db.dispatch_porter_payments.find(q, {"_id": 0}).to_list(1000)
        cards = await db.dispatch_cards.find({**q, "porter_name": {"$ne": ""}, "status": {"$in": ["dispatched", "info_shared"]}},
            {"_id": 0, "porter_name": 1, "porter_charges": 1}).to_list(5000)
        pt, pp = {}, {}
        for c in cards:
            n = c.get("porter_name", "")
            if n:
                pt.setdefault(n, {"total": 0, "cnt": 0})
                pt[n]["total"] += safe_num(c.get("porter_charges"))
                pt[n]["cnt"] += 1
        for p in payments:
            n = p.get("porter_name", "")
            pp[n] = pp.get(n, 0) + safe_num(p.get("amount"))
        settlement = []
        for porter in porters:
            n = porter.get("name", "")
            ch = pt.get(n, {}).get("total", 0)
            pd = pp.get(n, 0)
            settlement.append({"porter_id": porter.get("porter_id"), "name": n, "phone": porter.get("phone", ""),
                "total_charges": round(ch, 2), "total_paid": round(pd, 2), "balance_due": round(ch - pd, 2),
                "dispatch_count": pt.get(n, {}).get("cnt", 0)})
        return APIResponse(success=True, data={"settlement": settlement})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/porter-payment")
async def record_porter_payment(request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        payment = {"payment_id": f"PP-{uuid.uuid4().hex[:6].upper()}", "porter_name": body.get("porter_name", ""),
            "amount": float(body.get("amount", 0)), "payment_ref": body.get("payment_ref", ""),
            "notes": body.get("notes", ""), "paid_at": datetime.now(timezone.utc).isoformat(),
            "paid_by": user.get("username", ""), **_q(ctx)}
        await db.dispatch_porter_payments.insert_one(payment)
        return APIResponse(success=True, message="Payment recorded")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DISPATCH EMPLOYEES
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/employees")
async def get_dispatch_employees(request: Request):
    """List dispatch employees for this tenant. Users are tenant-wide (no
    company_id), so we filter ONLY by tenant_id, not the full _q() filter."""
    try:
        ctx = await get_tenant_context(request)
        q = {"role": "dispatch"}
        if ctx and ctx.get("tenant_id"):
            q["tenant_id"] = ctx["tenant_id"]
        employees = await db.users.find(q, {"_id": 0, "password_hash": 0}).to_list(50)
        return APIResponse(success=True, data={"employees": employees})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# SETTINGS — dispatch start date
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/settings")
async def get_dispatch_settings(request: Request):
    try:
        ctx = await get_tenant_context(request)
        doc = await db.dispatch_settings.find_one(_q(ctx), {"_id": 0})
        return APIResponse(success=True, data=doc or {})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/settings")
async def save_dispatch_settings(request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user.get("role") != "admin":
            return APIResponse(success=False, error="Admin access required")
        ctx = await get_tenant_context(request)
        body = await request.json()
        q = _q(ctx)
        await db.dispatch_settings.update_one(q, {"$set": {**q,
            "start_date": body.get("start_date", ""),
            "auto_create_enabled": body.get("auto_create_enabled", True),
            "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return APIResponse(success=True, message="Settings saved")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# CLOSE OF DAY & SUMMARY
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/summary")
async def get_dispatch_summary(request: Request, date: Optional[str] = None, company_id: Optional[str] = None):
    try:
        from datetime import date as date_type
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        target_date = date or date_type.today().isoformat()
        day_start, day_end = f"{target_date}T00:00:00", f"{target_date}T23:59:59"
        all_cards = await db.dispatch_cards.find(q, {"_id": 0}).to_list(10000)
        today_dispatched = [c for c in all_cards if c.get("status") in ("dispatched", "info_shared") and any(
            h.get("status") == "dispatched" and day_start <= h.get("at", "") <= day_end
            for h in c.get("status_history", []))]
        pending = [c for c in all_cards if c.get("status") in ("new", "queued", "processing", "packed")]
        on_hold = [c for c in all_cards if c.get("status") == "hold"]
        tw, ew = {}, {}
        for c in today_dispatched:
            t = c.get("transport_name") or "Unknown"
            tw.setdefault(t, {"count": 0, "charges": 0})
            tw[t]["count"] += 1; tw[t]["charges"] += safe_num(c.get("transport_charges"))
            e = c.get("assigned_to") or "Unassigned"
            ew.setdefault(e, {"count": 0}); ew[e]["count"] += 1
        return APIResponse(success=True, data={
            "date": target_date, "dispatched_count": len(today_dispatched), "pending_count": len(pending),
            "hold_count": len(on_hold), "total_value": round(sum(safe_num(c.get("total_amount", 0)) for c in today_dispatched), 2),
            "total_boxes": int(sum(safe_num(c.get("total_boxes", 0)) for c in today_dispatched)),
            "total_transport_charges": round(sum(safe_num(c.get("transport_charges", 0)) for c in today_dispatched), 2),
            "total_porter_charges": round(sum(safe_num(c.get("porter_charges", 0)) for c in today_dispatched), 2),
            "transport_breakdown": [{"name": k, **v} for k, v in tw.items()],
            "employee_breakdown": [{"name": k, **v} for k, v in ew.items()],
            "dispatched_cards": today_dispatched, "pending_cards": pending, "hold_cards": on_hold})
    except Exception as e:
        logger.error(f"Dispatch summary error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# AUTO-CREATE CARDS FROM INVOICES (date-based)
# ═══════════════════════════════════════════════════════

async def _detect_invoice_changes(tenant_id: str, company_id: str) -> dict:
    """Option B — flag-only detection of Tally invoice changes for existing
    dispatch cards. Runs after every sales sync.

    Logic:
      For every card NOT in {dispatched, info_shared, cancelled}:
        - Look up the live sales_voucher by voucher_id (or invoice_number).
        - If the voucher is missing → flag invoice_missing_flag = True.
        - Else compare items count, total_amount, party_name against the
          card's snapshot. If any field differs → flag invoice_changed_flag
          with `detected_changes` describing what moved.
      For cards in {dispatched, info_shared}:
        - Same comparison but flagged as `post_dispatch_invoice_changed`
          (red banner — truck has left, but Tally was modified after).
      Cards in {cancelled} are ignored (terminal).

    NEVER mutates `items`, `total_amount`, `party_name` or other dispatch
    fields — operator decides whether to reconcile.

    Returns: { "flagged_changed": int, "flagged_missing": int,
               "post_dispatch_changed": int, "cleared": int }
    """
    if not tenant_id:
        return {"flagged_changed": 0, "flagged_missing": 0,
                "post_dispatch_changed": 0, "cleared": 0}
    q = {"tenant_id": tenant_id, "company_id": company_id}

    cards = await db.dispatch_cards.find(
        {**q, "card_type": "invoice", "status": {"$ne": "cancelled"}},
        {
            "_id": 0, "card_id": 1, "voucher_id": 1, "invoice_number": 1,
            "items": 1, "total_amount": 1, "party_name": 1, "status": 1,
            "invoice_changed_flag": 1, "invoice_missing_flag": 1,
            "post_dispatch_invoice_changed": 1,
        },
    ).to_list(50000)
    if not cards:
        return {"flagged_changed": 0, "flagged_missing": 0,
                "post_dispatch_changed": 0, "cleared": 0}

    voucher_ids = [c.get("voucher_id") for c in cards if c.get("voucher_id")]
    invoice_nums = [c.get("invoice_number") for c in cards
                    if c.get("invoice_number") and not c.get("voucher_id")]

    voucher_map: dict = {}
    if voucher_ids:
        async for v in db.sales_vouchers.find(
            {**q, "voucher_id": {"$in": voucher_ids}},
            {"_id": 0, "voucher_id": 1, "items": 1, "total_amount": 1, "party_name": 1, "voucher_date": 1},
        ):
            voucher_map[v.get("voucher_id", "")] = v
    if invoice_nums:
        async for v in db.sales_vouchers.find(
            {**q, "reference_number": {"$in": invoice_nums}},
            {"_id": 0, "reference_number": 1, "items": 1, "total_amount": 1, "party_name": 1, "voucher_date": 1},
        ):
            voucher_map[v.get("reference_number", "")] = v

    now = datetime.now(timezone.utc).isoformat()
    flagged_changed = flagged_missing = post_disp_changed = cleared = 0
    SHIPPED = {"dispatched", "info_shared"}

    for c in cards:
        key = c.get("voucher_id") or c.get("invoice_number") or ""
        if not key:
            continue
        live = voucher_map.get(key)
        card_id = c.get("card_id", "")
        cur_status = c.get("status", "")

        if not live:
            # Missing in Tally → flag (only if not already flagged)
            if not c.get("invoice_missing_flag"):
                await db.dispatch_cards.update_one(
                    {**q, "card_id": card_id},
                    {"$set": {
                        "invoice_missing_flag": True,
                        "invoice_change_detected_at": now,
                    }},
                )
                flagged_missing += 1
            continue

        # Snapshot vs live diff
        snap_items = c.get("items") or []
        live_items = live.get("items") or []
        diffs = []
        if len(snap_items) != len(live_items):
            diffs.append({"field": "items_count", "old": len(snap_items), "new": len(live_items)})
        else:
            # Compare per-line item names + qty
            def _key(it):
                return (
                    (it.get("item") or it.get("item_name") or "").strip().lower(),
                    safe_num(it.get("quantity")),
                )
            if sorted(_key(i) for i in snap_items) != sorted(_key(i) for i in live_items):
                diffs.append({"field": "items_changed", "old": len(snap_items), "new": len(live_items)})

        snap_amt = round(safe_num(c.get("total_amount")), 2)
        live_amt = round(safe_num(live.get("total_amount")), 2)
        if abs(snap_amt - live_amt) > 0.5:
            diffs.append({"field": "total_amount", "old": snap_amt, "new": live_amt})

        snap_party = (c.get("party_name") or "").strip()
        live_party = (live.get("party_name") or "").strip()
        if snap_party.lower() != live_party.lower():
            diffs.append({"field": "party_name", "old": snap_party, "new": live_party})

        if diffs:
            update = {"detected_changes": diffs, "invoice_change_detected_at": now}
            if cur_status in SHIPPED:
                update["post_dispatch_invoice_changed"] = True
                post_disp_changed += 1
            else:
                update["invoice_changed_flag"] = True
                flagged_changed += 1
            # Always clear missing flag if we found the voucher
            unset = {}
            if c.get("invoice_missing_flag"):
                unset["invoice_missing_flag"] = ""
            ops = {"$set": update}
            if unset:
                ops["$unset"] = unset
            await db.dispatch_cards.update_one({**q, "card_id": card_id}, ops)
        else:
            # No diff — clear any stale flags from a prior detection
            unset = {}
            if c.get("invoice_changed_flag"):
                unset["invoice_changed_flag"] = ""
                unset["detected_changes"] = ""
            if c.get("invoice_missing_flag"):
                unset["invoice_missing_flag"] = ""
            if c.get("post_dispatch_invoice_changed"):
                unset["post_dispatch_invoice_changed"] = ""
            if unset:
                await db.dispatch_cards.update_one(
                    {**q, "card_id": card_id}, {"$unset": unset},
                )
                cleared += 1

    return {"flagged_changed": flagged_changed, "flagged_missing": flagged_missing,
            "post_dispatch_changed": post_disp_changed, "cleared": cleared}


async def _auto_create_cards_helper(tenant_id: str, company_id: str, from_date: str) -> int:
    """Internal helper — creates dispatch cards from sales vouchers. Used by both
    the manual /dispatch/auto-create endpoint and the sync hook in sync.py."""
    if not from_date or not tenant_id:
        return 0
    q = {"tenant_id": tenant_id, "company_id": company_id}

    existing = set(await db.dispatch_cards.distinct("invoice_number", q))
    sales_q = {**q, "voucher_date": {"$gte": from_date}}
    sales = await db.sales_vouchers.find(sales_q, {"_id": 0}).to_list(50000)
    new_sales = [
        s for s in sales
        if s.get("voucher_id") not in existing
        and (s.get("reference_number") or "") not in existing
    ]
    if not new_sales:
        return 0

    dispatch_employees = await db.users.find(
        {"tenant_id": q.get("tenant_id", ""), "role": "dispatch"}, {"_id": 0, "username": 1}
    ).to_list(50)
    usernames = [e["username"] for e in dispatch_employees]
    last_assigned = await db.dispatch_cards.find_one(
        q, {"_id": 0, "assigned_to": 1}, sort=[("created_at", -1)]
    )
    last_idx = 0
    if last_assigned and last_assigned.get("assigned_to") in usernames:
        last_idx = usernames.index(last_assigned["assigned_to"])

    now = datetime.now(timezone.utc).isoformat()
    created = 0
    for i, sale in enumerate(new_sales):
        inv_num = sale.get("reference_number") or sale.get("voucher_id", "")
        assigned = usernames[(last_idx + i + 1) % len(usernames)] if usernames else None
        card = {
            "card_id": f"DSP-{uuid.uuid4().hex[:8].upper()}", "card_type": "invoice",
            "invoice_number": inv_num, "voucher_id": sale.get("voucher_id", ""),
            "party_name": sale.get("party_name", ""), "items": sale.get("items", []),
            "total_amount": safe_num(sale.get("total_amount")), "voucher_date": sale.get("voucher_date", ""),
            "salesman": sale.get("salesman", ""), "destination_city": "",
            "status": "queued" if assigned else "new", "assigned_to": assigned,
            "total_boxes": 0, "transport_name": "", "transport_charges": 0,
            "porter_name": "", "porter_charges": 0, "lr_number": "",
            "physical_check": False, "notes": "", "documents": {},
            "status_history": [{"status": "new", "at": now, "by": "system"},
                               *([{"status": "queued", "at": now, "by": "system"}] if assigned else [])],
            "created_at": now, "created_by": "system", **q}
        await db.dispatch_cards.insert_one(card)
        created += 1
    return created


@router.post("/dispatch/auto-create")
async def auto_create_from_invoices(request: Request):
    """Create dispatch cards for sales invoices from a given date. Only sales invoices, no sales orders."""
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        from_date = body.get("from_date", "")
        q = _q(ctx)

        if not from_date:
            # Check settings for saved start date
            settings = await db.dispatch_settings.find_one(q, {"_id": 0})
            from_date = settings.get("start_date", "") if settings else ""
        if not from_date:
            return APIResponse(success=False, error="Please select a start date for dispatch card creation")

        # Save setting
        await db.dispatch_settings.update_one(q, {"$set": {**q, "start_date": from_date,
            "auto_create_enabled": True, "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)

        created = await _auto_create_cards_helper(ctx.get("tenant_id", ""), ctx.get("company_id", ""), from_date)
        if created == 0:
            return APIResponse(success=True, data={"created": 0}, message="No new invoices to create cards for")
        return APIResponse(success=True, data={"created": created, "from_date": from_date},
                           message=f"{created} dispatch cards created from {from_date}")
    except Exception as e:
        logger.error(f"Auto-create error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DISPATCH HISTORY
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/history")
async def get_dispatch_history(request: Request, search: Optional[str] = None, page: int = 1,
                                limit: int = 50, company_id: Optional[str] = None,
                                include: Optional[str] = None):
    """Dispatch history.
    `include`:
      - "completed" (default) → dispatched + info_shared
      - "cancelled"           → cancelled cards only
      - "all"                 → completed + cancelled
    """
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        inc = (include or "completed").lower()
        if inc == "cancelled":
            q["status"] = "cancelled"
        elif inc == "all":
            q["status"] = {"$in": ["dispatched", "info_shared", "cancelled"]}
        else:
            q["status"] = {"$in": ["dispatched", "info_shared"]}
        if search:
            fuzzy = build_fuzzy_regex(search)
            if fuzzy:
                q["$or"] = [{"invoice_number": {"$regex": fuzzy, "$options": "i"}},
                            {"party_name": {"$regex": fuzzy, "$options": "i"}},
                            {"card_id": {"$regex": fuzzy, "$options": "i"}},
                            {"lr_number": {"$regex": fuzzy, "$options": "i"}},
                            {"transport_name": {"$regex": fuzzy, "$options": "i"}}]
        total = await db.dispatch_cards.count_documents(q)
        skip = (page - 1) * limit
        cards = await db.dispatch_cards.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        return APIResponse(success=True, data={"cards": cards, "total": total, "page": page,
                                                "total_pages": (total + limit - 1) // limit})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# TRANSPORTER SETTLEMENT
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/transporter-settlement")
async def get_transporter_settlement(request: Request):
    try:
        ctx = await get_tenant_context(request)
        q = _q(ctx)
        transporters = await db.dispatch_transporters.find(q, {"_id": 0}).to_list(200)
        payments = await db.dispatch_transporter_payments.find(q, {"_id": 0}).to_list(1000)
        cards = await db.dispatch_cards.find({**q, "transport_name": {"$ne": ""}, "status": {"$in": ["dispatched", "info_shared"]}},
            {"_id": 0, "transport_name": 1, "transport_charges": 1}).to_list(5000)
        tt, tp = {}, {}
        for c in cards:
            n = c.get("transport_name", "")
            if n:
                tt.setdefault(n, {"total": 0, "cnt": 0})
                tt[n]["total"] += safe_num(c.get("transport_charges"))
                tt[n]["cnt"] += 1
        for p in payments:
            n = p.get("transporter_name", "")
            tp[n] = tp.get(n, 0) + safe_num(p.get("amount"))
        settlement = []
        for t in transporters:
            n = t.get("name", "")
            ch = tt.get(n, {}).get("total", 0)
            pd = tp.get(n, 0)
            settlement.append({"transporter_id": t.get("transporter_id"), "name": n, "phone": t.get("phone", ""),
                "total_charges": round(ch, 2), "total_paid": round(pd, 2), "balance_due": round(ch - pd, 2),
                "dispatch_count": tt.get(n, {}).get("cnt", 0)})
        return APIResponse(success=True, data={"settlement": settlement})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/dispatch/transporter-payment")
async def record_transporter_payment(request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
        body = await request.json()
        payment = {"payment_id": f"TP-{uuid.uuid4().hex[:6].upper()}", "transporter_name": body.get("transporter_name", ""),
            "amount": float(body.get("amount", 0)), "payment_ref": body.get("payment_ref", ""),
            "paid_at": datetime.now(timezone.utc).isoformat(), "paid_by": user.get("username", ""), **_q(ctx)}
        await db.dispatch_transporter_payments.insert_one(payment)
        return APIResponse(success=True, message="Payment recorded")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# DELETE PORTER / TRANSPORTER
# ═══════════════════════════════════════════════════════

@router.delete("/dispatch/porters/{porter_id}")
async def delete_porter(porter_id: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        await db.dispatch_porters.delete_one({**_q(ctx), "porter_id": porter_id})
        return APIResponse(success=True, message="Porter deleted")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.delete("/dispatch/transporters/{transporter_id}")
async def delete_transporter(transporter_id: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        await db.dispatch_transporters.delete_one({**_q(ctx), "transporter_id": transporter_id})
        return APIResponse(success=True, message="Transporter deleted")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.patch("/dispatch/transporters/{transporter_id}")
async def update_transporter(transporter_id: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        body = await request.json()
        updates = {f: body[f] for f in ("name", "phone", "is_active") if f in body}
        if updates:
            await db.dispatch_transporters.update_one({**_q(ctx), "transporter_id": transporter_id}, {"$set": updates})
        return APIResponse(success=True, message="Transporter updated")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# CLOSE OF DAY PDF
# ═══════════════════════════════════════════════════════

@router.get("/dispatch/close-of-day-pdf")
async def close_of_day_pdf(request: Request, date: Optional[str] = None, company_id: Optional[str] = None):
    """Generate Close-of-Day PDF for a given date."""
    from fastapi.responses import StreamingResponse
    import io
    try:
        from datetime import date as date_type
        ctx = await get_tenant_context(request)
        q = _q(ctx, company_id)
        target_date = date or date_type.today().isoformat()
        day_start, day_end = f"{target_date}T00:00:00", f"{target_date}T23:59:59"
        all_cards = await db.dispatch_cards.find(q, {"_id": 0}).to_list(10000)
        dispatched = [c for c in all_cards if c.get("status") in ("dispatched", "info_shared") and any(
            h.get("status") == "dispatched" and day_start <= h.get("at", "") <= day_end
            for h in c.get("status_history", []))]
        pending = [c for c in all_cards if c.get("status") in ("new", "queued", "processing", "packed")]
        on_hold = [c for c in all_cards if c.get("status") == "hold"]

        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=14, spaceAfter=6)
        sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
        h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=11, spaceAfter=4, spaceBefore=10)
        cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10)

        elements = []
        elements.append(Paragraph("FLOWRA — Dispatch Close of Day", title_style))
        elements.append(Paragraph(f"Date: {target_date}", sub_style))
        elements.append(Spacer(1, 8))

        # Summary
        elements.append(Paragraph(f"Dispatched: {len(dispatched)}  |  Pending: {len(pending)}  |  On Hold: {len(on_hold)}", styles['Normal']))
        total_boxes = sum(safe_num(c.get('total_boxes', 0)) for c in dispatched)
        total_transport = sum(safe_num(c.get('transport_charges', 0)) for c in dispatched)
        total_porter = sum(safe_num(c.get('porter_charges', 0)) for c in dispatched)
        elements.append(Paragraph(f"Total Boxes: {int(total_boxes)}  |  Transport: Rs.{total_transport:,.0f}  |  Porter: Rs.{total_porter:,.0f}", styles['Normal']))
        elements.append(Spacer(1, 6))

        if dispatched:
            elements.append(Paragraph("Dispatched Invoices", h2))
            data = [['#', 'Invoice', 'Party', 'Boxes', 'Transport', 'Porter', 'LR No.', 'Employee']]
            for i, c in enumerate(dispatched, 1):
                data.append([str(i), Paragraph(str(c.get('invoice_number', '')), cell),
                    Paragraph(str(c.get('party_name', ''))[:30], cell), str(c.get('total_boxes', 0)),
                    c.get('transport_name', '-'), c.get('porter_name', '-'),
                    c.get('lr_number', '-'), (c.get('assigned_to', '-') or '-').split('@')[0]])
            t = Table(data, colWidths=[15, 55, 85, 30, 65, 55, 55, 50])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(t)

        if pending:
            elements.append(Paragraph(f"Pending ({len(pending)})", h2))
            data = [['Invoice', 'Party', 'Status', 'Assigned To']]
            for c in pending[:30]:
                data.append([c.get('invoice_number', ''), c.get('party_name', '')[:35],
                    c.get('status', '').upper(), (c.get('assigned_to', '-') or '-').split('@')[0]])
            t = Table(data, colWidths=[80, 150, 60, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ]))
            elements.append(t)

        doc.build(elements)
        buf.seek(0)
        filename = f"dispatch_cod_{target_date}.pdf"
        return StreamingResponse(buf, media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        logger.error(f"COD PDF error: {e}")
        return APIResponse(success=False, error=str(e))



async def _round_robin_assign(tq):
    employees = await db.users.find({"tenant_id": tq.get("tenant_id", ""), "role": "dispatch"}, {"_id": 0, "username": 1}).to_list(50)
    if not employees:
        return None
    usernames = [e["username"] for e in employees]
    last = await db.dispatch_cards.find_one(tq, {"_id": 0, "assigned_to": 1}, sort=[("created_at", -1)])
    last_user = last.get("assigned_to") if last else None
    if last_user and last_user in usernames:
        return usernames[(usernames.index(last_user) + 1) % len(usernames)]
    return usernames[0]
