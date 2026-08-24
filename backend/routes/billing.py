"""Razorpay integration — trial-to-paid, renewal, mid-cycle plan change.

Environment variables:
- RAZORPAY_KEY_ID      (rzp_test_... or rzp_live_...)
- RAZORPAY_KEY_SECRET
- RAZORPAY_WEBHOOK_SECRET  (optional, for webhook signature verification)

Flow:
1. Frontend calls POST /api/billing/create-order with {intent, plan, cycle,
   months} — server computes amount (with proration credit for mid-cycle
   changes), creates a Razorpay order, returns {order_id, key_id, amount}.
2. Frontend opens Razorpay Checkout, gets {razorpay_payment_id,
   razorpay_order_id, razorpay_signature} on success.
3. Frontend POSTs those to /api/billing/verify — server verifies the
   signature, applies the plan change / renewal, records a payment,
   stamps `converted_at` for trial upgrades.
4. Webhook /api/billing/webhook confirms captures asynchronously.
"""
from __future__ import annotations

import os
import logging
import uuid
from datetime import datetime, timezone

import razorpay
from fastapi import APIRouter, Request
from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

_client: razorpay.Client | None = None


def _rzp() -> razorpay.Client:
    global _client
    if _client is None:
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            raise RuntimeError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not configured")
        _client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return _client


def _plan_prices():
    """Local import to avoid circular deps at module load."""
    from routes.seller_panel import PLAN_PRICING
    return PLAN_PRICING


def _compute_amount(plan: str, cycle: str, months: int,
                    admin: dict, intent: str) -> tuple[float, dict]:
    """Return (amount_rupees, breakdown) for the requested action.

    - intent="upgrade":  trial → paid   → full new plan price
    - intent="renew":    paid → paid    → full new plan price (fresh cycle)
    - intent="change":   paid → paid    → new plan price − unused-days credit
    """
    pricing = _plan_prices().get(plan) or _plan_prices().get("starter")
    unit = pricing.get("annual" if cycle == "annual" else "monthly", 0) or 0
    if cycle == "annual":
        new_total = round(unit * (months / 12.0), 2)
    else:
        new_total = round(unit * months, 2)

    credit = 0.0
    if intent == "change" and not admin.get("is_trial"):
        # Prorate unused days from the OLD subscription and use that as
        # a credit against the NEW total.
        try:
            from services.ist_utils import subscription_expires_at
            old_start = admin.get("subscription_start", "")
            old_months = int(admin.get("subscription_months", 12) or 12)
            old_cycle = admin.get("billing_cycle", "annual")
            old_plan = admin.get("plan", "starter")
            old_pricing = _plan_prices().get(old_plan) or _plan_prices().get("starter")
            old_unit = old_pricing.get("annual" if old_cycle == "annual" else "monthly", 0) or 0
            old_total = (round(old_unit * (old_months / 12.0), 2)
                         if old_cycle == "annual" else round(old_unit * old_months, 2))
            if old_start:
                start_dt = datetime.fromisoformat(old_start.replace("Z", "+00:00"))
                end_iso = subscription_expires_at(old_start, old_months)
                end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                total_days = (end_dt - start_dt).days or 1
                unused_days = max(0, (end_dt - datetime.now(timezone.utc)).days)
                credit = round(old_total * (unused_days / total_days), 2)
        except Exception as e:
            logger.warning(f"proration credit calc failed: {e}")
            credit = 0.0

    net = max(1.0, round(new_total - credit, 2))       # never zero — Razorpay minimum ₹1
    return net, {
        "new_total": new_total,
        "credit": credit,
        "net": net,
    }


@router.get("/billing/config")
async def billing_config(request: Request):
    """Return the public Razorpay key id + list of purchasable plans so
    the frontend can render the upgrade modal."""
    ctx = await get_tenant_context(request)
    if not ctx:
        return APIResponse(success=False, error="Authentication required")
    from routes.seller_panel import PLAN_PRICING
    plans = {k: v for k, v in PLAN_PRICING.items() if k != "trial"}
    return APIResponse(success=True, data={
        "key_id": RAZORPAY_KEY_ID,
        "plans": plans,
        "configured": bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET),
    })


@router.post("/billing/create-order")
async def create_order(request: Request):
    """Create a Razorpay order for the current tenant admin.

    Body: {intent: 'upgrade'|'renew'|'change', plan, cycle, months}
    Only tenant admins may call this. Employees are rejected."""
    ctx = await get_tenant_context(request)
    if not ctx or not ctx.get("tenant_id"):
        return APIResponse(success=False, error="Authentication required")
    if ctx.get("role") != "admin":
        return APIResponse(success=False, error="Only the tenant admin can change the plan")
    try:
        body = await request.json()
        intent = body.get("intent", "upgrade")
        plan = body.get("plan", "starter")
        cycle = body.get("cycle", "annual")
        months = int(body.get("months", 12) or 12)
        if plan not in _plan_prices() or plan == "trial":
            return APIResponse(success=False, error="Invalid plan")
        # A paid customer cannot buy the trial plan (guard duplicated at
        # /billing entrypoint so Razorpay self-serve honours the same rule
        # as SuperAdmin edit / renewal).
        if intent in ("renew", "change") and plan == "trial":
            return APIResponse(success=False, error="Trial plan is only available for brand-new customers.")
        if cycle not in ("monthly", "annual"):
            return APIResponse(success=False, error="Invalid billing cycle")
        admin = await db.users.find_one({"tenant_id": ctx["tenant_id"], "role": "admin"}, {"_id": 0, "password_hash": 0})
        if not admin:
            return APIResponse(success=False, error="Tenant admin not found")

        amount, breakdown = _compute_amount(plan, cycle, months, admin, intent)
        # Razorpay works in paise
        amount_paise = int(round(amount * 100))
        # Receipt must be ≤ 40 chars.
        receipt = f"flowra-{intent}-{admin['username'][:15]}-{int(datetime.now().timestamp())}"[:40]
        order = _rzp().order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "tenant_id": ctx["tenant_id"],
                "username": admin["username"],
                "intent": intent, "plan": plan, "cycle": cycle, "months": str(months),
            },
        })
        # Persist a pending record so the webhook / verify endpoint can
        # look up the intent later.
        await db.billing_orders.insert_one({
            "order_id": order["id"],
            "tenant_id": ctx["tenant_id"],
            "username": admin["username"],
            "intent": intent, "plan": plan, "cycle": cycle, "months": months,
            "amount": amount, "breakdown": breakdown,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return APIResponse(success=True, data={
            "order_id": order["id"],
            "key_id": RAZORPAY_KEY_ID,
            "amount": amount_paise,
            "amount_rupees": amount,
            "currency": "INR",
            "breakdown": breakdown,
            "prefill": {
                "name": admin.get("name", ""),
                "email": admin["username"],
                "contact": admin.get("mobile", ""),
            },
        })
    except Exception as e:
        logger.exception("create_order failed")
        return APIResponse(success=False, error=str(e))


@router.post("/billing/verify")
async def verify_payment(request: Request):
    """Verify a Razorpay Checkout success payload and apply the plan
    change. This is the SYNCHRONOUS confirmation path; webhook is the
    asynchronous fallback."""
    ctx = await get_tenant_context(request)
    if not ctx or not ctx.get("tenant_id"):
        return APIResponse(success=False, error="Authentication required")
    try:
        body = await request.json()
        payment_id = body.get("razorpay_payment_id", "")
        order_id = body.get("razorpay_order_id", "")
        signature = body.get("razorpay_signature", "")
        if not (payment_id and order_id and signature):
            return APIResponse(success=False, error="Missing razorpay payload")

        # Signature verification — raises SignatureVerificationError on mismatch.
        _rzp().utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })

        # Look up our order metadata (intent + plan + months).
        order_row = await db.billing_orders.find_one({"order_id": order_id})
        if not order_row:
            return APIResponse(success=False, error="Order not found on server")
        if order_row["tenant_id"] != ctx["tenant_id"]:
            return APIResponse(success=False, error="Order does not belong to this tenant")

        await _apply_billing_success(order_row, payment_id)
        return APIResponse(success=True, message="Payment verified — plan updated", data={
            "intent": order_row["intent"], "plan": order_row["plan"],
            "cycle": order_row["cycle"], "months": order_row["months"],
        })
    except razorpay.errors.SignatureVerificationError:
        return APIResponse(success=False, error="Signature verification failed")
    except Exception as e:
        logger.exception("verify_payment failed")
        return APIResponse(success=False, error=str(e))


async def _apply_billing_success(order_row: dict, payment_id: str) -> None:
    """Idempotent — safe to call from both /verify and /webhook."""
    if order_row.get("status") == "captured":
        return
    from services.email_service import send_welcome_admin_rich
    from routes.seller_panel import PLAN_PRICING
    from routes.prospects import SUBSCRIPTION_PLANS

    username = order_row["username"]
    intent = order_row["intent"]
    plan = order_row["plan"]
    cycle = order_row["cycle"]
    months = int(order_row["months"])
    plan_cfg = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["starter"])
    now = datetime.now(timezone.utc).isoformat()

    admin = await db.users.find_one({"username": username, "role": "admin"}, {"_id": 0})
    if not admin:
        logger.error(f"admin {username} not found during billing apply")
        return

    update = {
        "plan": plan, "billing_cycle": cycle, "subscription_months": months,
        "subscription_start": now,
        "max_companies": plan_cfg["max_companies"],
        "max_employees": plan_cfg["max_employees"],
        "features": list(plan_cfg["features"]),
    }
    if admin.get("is_trial") and intent == "upgrade":
        update.update({"is_trial": False, "converted_at": now})
    await db.users.update_one({"username": username, "role": "admin"}, {"$set": update})

    # Record the payment against the admin's account.
    from routes.seller_panel import create_service_reference
    try:
        service_ref = await create_service_reference(
            customer_username=username,
            event="upgrade" if intent == "upgrade" else ("renewal" if intent == "renew" else "plan_change"),
            plan=plan, cycle=cycle, months=months,
            created_by="razorpay-self-serve",
        )
    except Exception:
        service_ref = ""
    await db.payments.insert_one({
        "payment_id": str(uuid.uuid4()),
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": order_row["order_id"],
        "customer_username": username,
        "amount": float(order_row["amount"]),
        "payment_mode": "razorpay",
        "reference_no": payment_id,
        "notes": f"{intent} to {plan} ({cycle}, {months}m)",
        "period_description": f"{intent.title()} · {plan} · {cycle}",
        "service_reference": service_ref,
        "created_at": now,
        "source": "razorpay-self-serve",
    })
    await db.billing_orders.update_one(
        {"order_id": order_row["order_id"]},
        {"$set": {"status": "captured", "payment_id": payment_id,
                  "captured_at": now}},
    )

    # Fire a fresh welcome mail (best-effort — don't fail the request).
    try:
        pricing = PLAN_PRICING.get(plan, PLAN_PRICING["starter"])
        price = pricing["annual"] if cycle == "annual" else pricing["monthly"]
        await send_welcome_admin_rich(
            to_email=username, name=admin.get("name", ""), password="•••••• (unchanged)",
            plan=pricing["name"], plan_price_display=f"₹{price:,.0f} / {cycle}",
            billing_cycle=cycle,
            subscription_display=f"{months} month(s), starts today",
            company_name=admin.get("company_name", ""), mobile=admin.get("mobile", ""),
            gst=admin.get("gst", ""), address=admin.get("address", ""),
            city=admin.get("city", ""), industry=admin.get("industry", ""),
            sales_count=admin.get("sales_count", 0), dispatch_count=admin.get("dispatch_count", 0),
            is_trial=False, trial_end_display="",
        )
    except Exception as e:
        logger.warning(f"post-conversion welcome mail failed: {e}")


@router.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Razorpay webhook — asynchronous confirmation. Optional signature
    check when RAZORPAY_WEBHOOK_SECRET is set."""
    try:
        raw = await request.body()
        if RAZORPAY_WEBHOOK_SECRET:
            sig = request.headers.get("X-Razorpay-Signature", "")
            _rzp().utility.verify_webhook_signature(raw.decode(), sig, RAZORPAY_WEBHOOK_SECRET)
        import json
        payload = json.loads(raw)
        event = payload.get("event", "")
        if event in ("payment.captured", "order.paid"):
            pay = payload.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = pay.get("order_id", "")
            payment_id = pay.get("id", "")
            row = await db.billing_orders.find_one({"order_id": order_id})
            if row:
                await _apply_billing_success(row, payment_id)
        return APIResponse(success=True, message=f"processed {event}")
    except Exception as e:
        logger.exception("billing webhook failed")
        return APIResponse(success=False, error=str(e))


# ─── SuperAdmin: one-click Convert Trial → Paid ─────────────────────
@router.post("/super-admin/admins/{username}/convert-trial")
async def super_convert_trial(username: str, request: Request):
    """SuperAdmin: convert a trial admin to a paid plan WITHOUT going
    through Razorpay (used when the SuperAdmin has collected payment
    offline via bank transfer / cash / cheque). Flips is_trial,
    stamps converted_at, and records a payment row."""
    from services.auth_service import get_current_user as _guc
    from db import db as _mdb
    sa = await _guc(request, _mdb)
    if not sa or sa.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        plan = body.get("plan", "starter")
        cycle = body.get("billing_cycle", "annual")
        months = int(body.get("subscription_months", 12) or 12)
        amount = float(body.get("amount") or 0)
        payment_mode = body.get("payment_mode", "bank_transfer")
        reference = body.get("reference_no", "")
        if plan not in _plan_prices() or plan == "trial":
            return APIResponse(success=False, error="Pick a paid plan")

        admin = await db.users.find_one({"username": username, "role": "admin"}, {"_id": 0})
        if not admin:
            return APIResponse(success=False, error="Admin not found")
        if not admin.get("is_trial"):
            return APIResponse(success=False, error="This admin is not on a trial")

        # Reuse the same code path as Razorpay success so behaviour is
        # identical (fresh sub window, welcome mail, converted_at).
        fake_order = {
            "order_id": f"manual-{uuid.uuid4()}",
            "tenant_id": admin.get("tenant_id", ""),
            "username": username,
            "intent": "upgrade", "plan": plan, "cycle": cycle, "months": months,
            "amount": amount, "status": "manual",
        }
        # Persist so the webhook idempotence check still works.
        await db.billing_orders.insert_one({**fake_order, "created_at": datetime.now(timezone.utc).isoformat()})
        await _apply_billing_success(fake_order, payment_id=reference or "manual")
        # Overwrite the payment row's mode/reference to what the SuperAdmin recorded.
        await db.payments.update_one(
            {"razorpay_order_id": fake_order["order_id"]},
            {"$set": {"payment_mode": payment_mode, "reference_no": reference,
                      "source": f"superadmin-manual:{sa['username']}"}},
        )
        return APIResponse(success=True, message=f"'{username}' converted to {plan.title()}")
    except Exception as e:
        logger.exception("super_convert_trial failed")
        return APIResponse(success=False, error=str(e))
