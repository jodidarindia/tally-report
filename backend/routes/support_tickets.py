"""In-app support ticket system with outbound webhooks.

- Tenant users open POST /api/support/tickets to create a ticket.
- SuperAdmin sees the inbox via GET /api/super-admin/support/tickets
- Two-way threading via /tickets/{id}/messages.
- Outbound webhook fires on ticket.created / ticket.replied so the
  SuperAdmin can pipe events into Slack/Discord/Teams.

Zendesk / Freshdesk 2-way sync is *scoped* for a follow-up iteration
— placeholder stubs left in place to make v2 easy.
"""
from __future__ import annotations

import os
import uuid
import json
import logging
import hmac
import hashlib
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request

from db import db
from models import APIResponse
from services.tenant_context import get_tenant_context
from services.auth_service import get_current_user as _guc
from db import db as _mongo_db


async def get_current_user(request: Request):
    return await _guc(request, _mongo_db)

logger = logging.getLogger(__name__)
router = APIRouter()

TICKET_STATES = {"open", "pending", "resolved", "closed"}
TICKET_PRIORITIES = {"low", "normal", "high", "urgent"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _fire_webhook(event: str, ticket: dict, extra: dict | None = None) -> None:
    """Fire outbound webhooks matching this event. Non-blocking-ish —
    3 s timeout each so a slow webhook can't stall the request."""
    hooks = await db.support_webhooks.find({"active": True, "events": event}).to_list(20)
    if not hooks:
        return
    payload = {"event": event, "ticket": ticket, "extra": extra or {},
               "sent_at": _now_iso()}
    body = json.dumps(payload, default=str).encode()
    async with httpx.AsyncClient(timeout=3.0) as client:
        for h in hooks:
            headers = {"Content-Type": "application/json",
                       "User-Agent": "FLOWRA-Webhook/1.0"}
            secret = h.get("secret") or ""
            if secret:
                sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                headers["X-FLOWRA-Signature"] = f"sha256={sig}"
            try:
                r = await client.post(h["url"], content=body, headers=headers)
                await db.support_webhook_deliveries.insert_one({
                    "delivery_id": str(uuid.uuid4()),
                    "webhook_id": h.get("webhook_id"),
                    "event": event,
                    "ticket_id": ticket.get("ticket_id"),
                    "status_code": r.status_code,
                    "sent_at": _now_iso(),
                })
            except Exception as e:
                logger.warning(f"webhook {h.get('url')} failed: {e}")


@router.post("/support/tickets")
async def create_ticket(request: Request):
    """Any authenticated tenant user can raise a ticket."""
    ctx = await get_tenant_context(request)
    if not ctx or not ctx.get("tenant_id"):
        return APIResponse(success=False, error="Authentication required")
    body = await request.json()
    subject = (body.get("subject") or "").strip()
    message = (body.get("message") or "").strip()
    priority = body.get("priority", "normal")
    if priority not in TICKET_PRIORITIES:
        priority = "normal"
    if not subject or not message:
        return APIResponse(success=False, error="Subject and message are required")

    ticket = {
        "ticket_id": str(uuid.uuid4()),
        "tenant_id": ctx["tenant_id"],
        "created_by": ctx.get("username", ""),
        "creator_name": ctx.get("name", ""),
        "creator_role": ctx.get("role", ""),
        "subject": subject[:200],
        "status": "open",
        "priority": priority,
        "messages": [{
            "message_id": str(uuid.uuid4()),
            "author_role": ctx.get("role", ""),
            "author_username": ctx.get("username", ""),
            "author_name": ctx.get("name", ""),
            "body": message,
            "created_at": _now_iso(),
        }],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "assignee_username": "",
    }
    await db.support_tickets.insert_one(ticket)
    ticket.pop("_id", None)
    await _fire_webhook("ticket.created", ticket)
    return APIResponse(success=True, data=ticket)


@router.get("/support/tickets")
async def list_my_tickets(request: Request):
    """List tickets for the current tenant."""
    ctx = await get_tenant_context(request)
    if not ctx or not ctx.get("tenant_id"):
        return APIResponse(success=False, error="Authentication required")
    tickets = await db.support_tickets.find(
        {"tenant_id": ctx["tenant_id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(200)
    return APIResponse(success=True, data={"tickets": tickets, "count": len(tickets)})


@router.post("/support/tickets/{ticket_id}/messages")
async def reply_ticket(ticket_id: str, request: Request):
    """Reply to a ticket. Tenant users can reply to their tickets;
    SuperAdmin can reply to any."""
    user = await get_current_user(request)
    if not user:
        return APIResponse(success=False, error="Authentication required")
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return APIResponse(success=False, error="Message body required")
    ticket = await db.support_tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
    if not ticket:
        return APIResponse(success=False, error="Ticket not found")

    is_super = user.get("role") == "super_admin"
    if not is_super and ticket["tenant_id"] != user.get("tenant_id"):
        return APIResponse(success=False, error="Not allowed to reply to this ticket")

    new_msg = {
        "message_id": str(uuid.uuid4()),
        "author_role": user.get("role", ""),
        "author_username": user.get("username", ""),
        "author_name": user.get("name", ""),
        "body": message,
        "created_at": _now_iso(),
    }
    # Auto-flip status: tenant reply → open, super_admin reply → pending
    new_status = "pending" if is_super else "open"
    await db.support_tickets.update_one(
        {"ticket_id": ticket_id},
        {"$push": {"messages": new_msg},
         "$set": {"updated_at": _now_iso(), "status": new_status}},
    )
    ticket = await db.support_tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
    await _fire_webhook("ticket.replied", ticket, {"message": new_msg})
    return APIResponse(success=True, data=ticket)


@router.put("/support/tickets/{ticket_id}/status")
async def set_ticket_status(ticket_id: str, request: Request):
    user = await get_current_user(request)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")
    body = await request.json()
    status = body.get("status", "")
    if status not in TICKET_STATES:
        return APIResponse(success=False, error=f"Status must be one of {TICKET_STATES}")
    r = await db.support_tickets.update_one(
        {"ticket_id": ticket_id},
        {"$set": {"status": status, "updated_at": _now_iso()}},
    )
    if r.matched_count == 0:
        return APIResponse(success=False, error="Ticket not found")
    ticket = await db.support_tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
    await _fire_webhook(f"ticket.{status}", ticket)
    return APIResponse(success=True, data=ticket)


# ─── SuperAdmin views ────────────────────────────────────────────────

@router.get("/super-admin/support/tickets")
async def super_list_tickets(request: Request):
    user = await get_current_user(request)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")
    tickets = await db.support_tickets.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    open_count = sum(1 for t in tickets if t.get("status") == "open")
    pending_count = sum(1 for t in tickets if t.get("status") == "pending")
    resolved_count = sum(1 for t in tickets if t.get("status") in ("resolved", "closed"))
    return APIResponse(success=True, data={
        "tickets": tickets,
        "counts": {"total": len(tickets), "open": open_count,
                   "pending": pending_count, "resolved": resolved_count},
    })


# ─── Webhook config CRUD (SuperAdmin only) ───────────────────────────

@router.get("/super-admin/support/webhooks")
async def list_webhooks(request: Request):
    user = await get_current_user(request)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")
    rows = await db.support_webhooks.find({}, {"_id": 0}).to_list(50)
    return APIResponse(success=True, data={"webhooks": rows})


@router.post("/super-admin/support/webhooks")
async def upsert_webhook(request: Request):
    user = await get_current_user(request)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")
    body = await request.json()
    wid = body.get("webhook_id") or str(uuid.uuid4())
    doc = {
        "webhook_id": wid,
        "name": (body.get("name") or "").strip()[:80],
        "url": (body.get("url") or "").strip(),
        "events": body.get("events") or ["ticket.created", "ticket.replied"],
        "active": bool(body.get("active", True)),
        "secret": body.get("secret") or "",
        "updated_at": _now_iso(),
    }
    if not doc["url"].startswith("http"):
        return APIResponse(success=False, error="URL must start with http(s)")
    await db.support_webhooks.update_one({"webhook_id": wid}, {"$set": doc}, upsert=True)
    return APIResponse(success=True, data=doc)


@router.delete("/super-admin/support/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, request: Request):
    user = await get_current_user(request)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")
    r = await db.support_webhooks.delete_one({"webhook_id": webhook_id})
    return APIResponse(success=True, data={"deleted": r.deleted_count})


import re

# ─── Inbound (Resend Inbound → auto-create tickets) ────────────────

_TICKET_ID_RE = re.compile(r"\[FLOWRA-([0-9a-f-]{8,})\]", re.IGNORECASE)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _parse_email_addr(raw: str) -> str:
    """Pull the bare address out of "Name <addr@x.y>" or just addr@x.y."""
    if not raw:
        return ""
    m = re.search(r"<([^>]+)>", raw)
    email = (m.group(1) if m else raw).strip().lower()
    return email


@router.post("/support/inbound-email")
async def inbound_email(request: Request):
    """Resend Inbound webhook — parses the email, matches the sender to
    an admin (or falls back to a shared 'inbound' tenant), and either
    creates a new ticket OR appends to an existing thread when the
    subject contains a `[FLOWRA-<id>]` marker.

    Payload shape (Resend Inbound):
      { "type": "email.received", "data": {
          "from": "Customer <c@x.com>", "subject": "...",
          "text": "...", "html": "...", ... } }
    """
    try:
        raw = await request.body()
        # Always log raw to inbound_log for ops visibility.
        await db.support_inbound_log.insert_one({
            "received_at": _now_iso(),
            "raw_body_sample": raw[:4000].decode(errors="ignore"),
        })
        payload = json.loads(raw or b"{}")
        # Resend nests useful fields under `data`. We also accept a flat
        # dict for other providers (e.g. Mailgun forward test).
        data = payload.get("data", payload)
        sender = _parse_email_addr(data.get("from") or "")
        subject = (data.get("subject") or "").strip()[:200] or "(no subject)"
        text = (data.get("text") or "").strip() or _strip_html(data.get("html", ""))[:8000]

        if not sender:
            return APIResponse(success=False, error="No sender email in payload")

        # ─── Match sender → tenant admin ────────────────────────────
        admin = await db.users.find_one(
            {"username": sender, "role": "admin"},
            {"_id": 0, "tenant_id": 1, "name": 1, "username": 1},
        )
        creator_role = "admin" if admin else "guest"
        creator_name = (admin or {}).get("name", "") or sender
        tenant_id = (admin or {}).get("tenant_id", "guest-inbound")

        # ─── Reply thread detection ────────────────────────────────
        m = _TICKET_ID_RE.search(subject)
        if m:
            ticket_id_prefix = m.group(1)
            existing = await db.support_tickets.find_one(
                {"ticket_id": {"$regex": f"^{re.escape(ticket_id_prefix)}"}},
                {"_id": 0},
            )
            if existing:
                new_msg = {
                    "message_id": str(uuid.uuid4()),
                    "author_role": creator_role,
                    "author_username": sender,
                    "author_name": creator_name,
                    "body": text,
                    "source": "inbound-email",
                    "created_at": _now_iso(),
                }
                await db.support_tickets.update_one(
                    {"ticket_id": existing["ticket_id"]},
                    {"$push": {"messages": new_msg},
                     "$set": {"updated_at": _now_iso(), "status": "open"}},
                )
                updated = await db.support_tickets.find_one(
                    {"ticket_id": existing["ticket_id"]}, {"_id": 0}
                )
                await _fire_webhook("ticket.replied", updated, {"message": new_msg, "via": "email"})
                return APIResponse(success=True, data={"action": "appended",
                                                       "ticket_id": existing["ticket_id"]})

        # ─── Otherwise create a new ticket ─────────────────────────
        ticket = {
            "ticket_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "created_by": sender,
            "creator_name": creator_name,
            "creator_role": creator_role,
            "subject": subject,
            "status": "open",
            "priority": "normal",
            "source": "inbound-email",
            "messages": [{
                "message_id": str(uuid.uuid4()),
                "author_role": creator_role,
                "author_username": sender,
                "author_name": creator_name,
                "body": text,
                "source": "inbound-email",
                "created_at": _now_iso(),
            }],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "assignee_username": "",
        }
        await db.support_tickets.insert_one(ticket)
        ticket.pop("_id", None)
        await _fire_webhook("ticket.created", ticket, {"via": "email"})
        return APIResponse(success=True, data={"action": "created",
                                               "ticket_id": ticket["ticket_id"]})
    except Exception as e:
        logger.exception("inbound_email failed")
        return APIResponse(success=False, error=str(e))
