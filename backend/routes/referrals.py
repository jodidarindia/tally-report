"""
Referral & Commission routes.
- Users (admin/employee) get unique referral codes
- Prospects can use referral codes during signup
- 3% commission on subscription amount when referred prospect subscribes
- Ledger tracking for earnings and redemptions
"""
from fastapi import APIRouter, Request
from datetime import datetime, timezone
import logging
import uuid
import random
import string

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.audit_service import log_audit, get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()

COMMISSION_RATE = 0.03  # 3% flat


def _generate_referral_code():
    """Generate a unique 8-char referral code."""
    chars = string.ascii_uppercase + string.digits
    return "REF-" + "".join(random.choices(chars, k=6))


# ─── User endpoints ────────────────────────────────────

@router.get("/referrals/my-code")
async def get_my_referral_code(request: Request):
    """Get or generate the current user's referral code."""
    user = await get_current_user(request, db)
    if not user:
        return APIResponse(success=False, error="Authentication required")
    username = user["username"]
    tenant_id = user.get("tenant_id", "")

    existing = await db.referral_codes.find_one(
        {"username": username}, {"_id": 0}
    )
    if existing:
        return APIResponse(success=True, data={
            "referral_code": existing["referral_code"],
            "created_at": existing["created_at"],
        })

    # Generate new unique code
    for _ in range(10):
        code = _generate_referral_code()
        dup = await db.referral_codes.find_one({"referral_code": code})
        if not dup:
            break
    else:
        return APIResponse(success=False, error="Could not generate unique code. Try again.")

    now = datetime.now(timezone.utc).isoformat()
    await db.referral_codes.insert_one({
        "referral_code": code,
        "username": username,
        "tenant_id": tenant_id,
        "role": user.get("role", ""),
        "name": user.get("name", ""),
        "created_at": now,
    })

    await log_audit("referral_code_generated", username, tenant_id=tenant_id,
                     details=f"Code: {code}", ip_address=get_client_ip(request))

    return APIResponse(success=True, data={
        "referral_code": code,
        "created_at": now,
    })


@router.get("/referrals/my-dashboard")
async def get_my_referral_dashboard(request: Request):
    """Get referral stats, referral list, and earnings ledger for current user."""
    user = await get_current_user(request, db)
    if not user:
        return APIResponse(success=False, error="Authentication required")
    username = user["username"]

    # Get referral code
    code_doc = await db.referral_codes.find_one({"username": username}, {"_id": 0})
    referral_code = code_doc["referral_code"] if code_doc else None

    # Get referrals made by this user
    referrals = []
    cursor = db.referrals.find({"referrer_username": username}, {"_id": 0}).sort("created_at", -1)
    async for ref in cursor:
        referrals.append({
            "referred_company": ref.get("referred_company", ""),
            "referred_email": ref.get("referred_email", ""),
            "prospect_id": ref.get("prospect_id", ""),
            "signup_date": ref.get("created_at", ""),
            "status": ref.get("status", "pending"),  # pending, subscribed, expired
            "subscription_amount": ref.get("subscription_amount", 0),
            "commission_amount": ref.get("commission_amount", 0),
        })

    # Get ledger entries
    ledger = []
    cursor = db.referral_ledger.find({"username": username}, {"_id": 0}).sort("created_at", -1)
    async for entry in cursor:
        ledger.append({
            "entry_id": entry.get("entry_id", ""),
            "type": entry.get("type", ""),  # credit / debit
            "amount": entry.get("amount", 0),
            "description": entry.get("description", ""),
            "balance_after": entry.get("balance_after", 0),
            "created_at": entry.get("created_at", ""),
            "reference": entry.get("reference", ""),
        })

    # Calculate totals
    total_referrals = len(referrals)
    total_earned = sum(r["commission_amount"] for r in referrals if r["status"] == "subscribed")
    total_pending = sum(r["commission_amount"] for r in referrals if r["status"] == "pending" and r["commission_amount"] > 0)
    total_redeemed = sum(e["amount"] for e in ledger if e["type"] == "debit")

    # Current balance from last ledger entry or calculate
    current_balance = total_earned - total_redeemed

    return APIResponse(success=True, data={
        "referral_code": referral_code,
        "stats": {
            "total_referrals": total_referrals,
            "total_earned": round(total_earned, 2),
            "total_pending": round(total_pending, 2),
            "total_redeemed": round(total_redeemed, 2),
            "current_balance": round(current_balance, 2),
        },
        "referrals": referrals,
        "ledger": ledger,
    })


# ─── Public endpoint (validate referral code) ──────────

@router.get("/public/validate-referral")
async def validate_referral_code(code: str = ""):
    """Validate a referral code (used on signup form)."""
    code = code.strip().upper()
    if not code:
        return APIResponse(success=False, error="No referral code provided")

    doc = await db.referral_codes.find_one({"referral_code": code}, {"_id": 0})
    if not doc:
        return APIResponse(success=False, error="Invalid referral code")

    return APIResponse(success=True, data={
        "referral_code": doc["referral_code"],
        "referrer_name": doc.get("name", "A FLOWRA user"),
    })


# ─── Super Admin endpoints ─────────────────────────────

@router.get("/referrals/admin/overview")
async def admin_referral_overview(request: Request):
    """Super Admin: overview of all referral program data."""
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")

    # All referral codes
    total_codes = await db.referral_codes.count_documents({})

    # All referrals
    all_referrals = []
    cursor = db.referrals.find({}, {"_id": 0}).sort("created_at", -1)
    async for ref in cursor:
        all_referrals.append(ref)

    total_referrals = len(all_referrals)
    subscribed = [r for r in all_referrals if r.get("status") == "subscribed"]
    total_commission = sum(r.get("commission_amount", 0) for r in subscribed)

    # Per-referrer summary
    referrer_map = {}
    for ref in all_referrals:
        uname = ref.get("referrer_username", "")
        if uname not in referrer_map:
            referrer_map[uname] = {
                "username": uname,
                "name": ref.get("referrer_name", ""),
                "role": ref.get("referrer_role", ""),
                "tenant_id": ref.get("referrer_tenant_id", ""),
                "total_referrals": 0,
                "subscribed": 0,
                "total_earned": 0,
                "total_redeemed": 0,
            }
        referrer_map[uname]["total_referrals"] += 1
        if ref.get("status") == "subscribed":
            referrer_map[uname]["subscribed"] += 1
            referrer_map[uname]["total_earned"] += ref.get("commission_amount", 0)

    # Get redemption totals per user
    async for entry in db.referral_ledger.find({"type": "debit"}, {"_id": 0}):
        uname = entry.get("username", "")
        if uname in referrer_map:
            referrer_map[uname]["total_redeemed"] += entry.get("amount", 0)

    referrers = sorted(referrer_map.values(), key=lambda x: x["total_earned"], reverse=True)

    # Total redeemed
    total_redeemed = sum(r["total_redeemed"] for r in referrers)

    return APIResponse(success=True, data={
        "stats": {
            "total_referral_codes": total_codes,
            "total_referrals": total_referrals,
            "total_subscribed": len(subscribed),
            "total_commission": round(total_commission, 2),
            "total_redeemed": round(total_redeemed, 2),
            "total_pending_payout": round(total_commission - total_redeemed, 2),
        },
        "referrers": referrers,
        "recent_referrals": all_referrals[:20],
    })


@router.get("/referrals/admin/user-ledger")
async def admin_user_ledger(request: Request, username: str = ""):
    """Super Admin: get detailed ledger for a specific referrer."""
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")

    if not username:
        return APIResponse(success=False, error="Username required")

    ledger = []
    cursor = db.referral_ledger.find({"username": username}, {"_id": 0}).sort("created_at", -1)
    async for entry in cursor:
        ledger.append(entry)

    referrals = []
    cursor = db.referrals.find({"referrer_username": username}, {"_id": 0}).sort("created_at", -1)
    async for ref in cursor:
        referrals.append(ref)

    return APIResponse(success=True, data={
        "username": username,
        "ledger": ledger,
        "referrals": referrals,
    })


@router.post("/referrals/admin/redeem")
async def admin_process_redemption(request: Request):
    """Super Admin: process a payout/redemption for a referrer."""
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")

    body = await request.json()
    target_username = (body.get("username") or "").strip()
    amount = float(body.get("amount", 0))
    notes = (body.get("notes") or "").strip()

    if not target_username or amount <= 0:
        return APIResponse(success=False, error="Username and positive amount required")

    # Calculate current balance
    referrals_cursor = db.referrals.find(
        {"referrer_username": target_username, "status": "subscribed"}, {"_id": 0}
    )
    total_earned = 0
    async for r in referrals_cursor:
        total_earned += r.get("commission_amount", 0)

    total_redeemed = 0
    async for e in db.referral_ledger.find({"username": target_username, "type": "debit"}, {"_id": 0}):
        total_redeemed += e.get("amount", 0)

    current_balance = total_earned - total_redeemed

    if amount > current_balance:
        return APIResponse(success=False, error=f"Insufficient balance. Available: Rs.{current_balance:.2f}")

    now = datetime.now(timezone.utc).isoformat()
    entry_id = f"LED-{uuid.uuid4().hex[:8].upper()}"
    new_balance = round(current_balance - amount, 2)

    await db.referral_ledger.insert_one({
        "entry_id": entry_id,
        "username": target_username,
        "type": "debit",
        "amount": round(amount, 2),
        "description": f"Payout processed{f' — {notes}' if notes else ''}",
        "balance_after": new_balance,
        "created_at": now,
        "reference": f"Processed by {user['username']}",
        "processed_by": user["username"],
    })

    await log_audit("referral_payout", user["username"], target=target_username,
                     details=f"Amount: Rs.{amount}, Balance after: Rs.{new_balance}",
                     ip_address=get_client_ip(request))

    return APIResponse(success=True, message=f"Rs.{amount:.2f} payout processed for {target_username}", data={
        "entry_id": entry_id,
        "new_balance": new_balance,
    })


@router.post("/referrals/admin/credit-commission")
async def admin_credit_commission(request: Request):
    """Super Admin: manually credit commission when a referred prospect subscribes."""
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return APIResponse(success=False, error="Super admin access required")

    body = await request.json()
    referral_prospect_id = (body.get("prospect_id") or "").strip()
    subscription_amount = float(body.get("subscription_amount", 0))

    if not referral_prospect_id or subscription_amount <= 0:
        return APIResponse(success=False, error="Prospect ID and subscription amount required")

    # Find the referral record
    referral = await db.referrals.find_one({"prospect_id": referral_prospect_id}, {"_id": 0})
    if not referral:
        return APIResponse(success=False, error="No referral found for this prospect")

    if referral.get("status") == "subscribed":
        return APIResponse(success=False, error="Commission already credited for this referral")

    commission = round(subscription_amount * COMMISSION_RATE, 2)
    referrer_username = referral["referrer_username"]

    now = datetime.now(timezone.utc).isoformat()

    # Update referral status
    await db.referrals.update_one(
        {"prospect_id": referral_prospect_id},
        {"$set": {
            "status": "subscribed",
            "subscription_amount": subscription_amount,
            "commission_amount": commission,
            "subscribed_at": now,
        }}
    )

    # Calculate new balance
    total_earned = commission
    async for r in db.referrals.find({"referrer_username": referrer_username, "status": "subscribed"}, {"_id": 0}):
        if r.get("prospect_id") != referral_prospect_id:
            total_earned += r.get("commission_amount", 0)

    total_redeemed = 0
    async for e in db.referral_ledger.find({"username": referrer_username, "type": "debit"}, {"_id": 0}):
        total_redeemed += e.get("amount", 0)

    new_balance = round(total_earned - total_redeemed, 2)

    # Add ledger credit entry
    entry_id = f"LED-{uuid.uuid4().hex[:8].upper()}"
    await db.referral_ledger.insert_one({
        "entry_id": entry_id,
        "username": referrer_username,
        "type": "credit",
        "amount": commission,
        "description": f"Commission for {referral.get('referred_company', 'prospect')} subscription (Rs.{subscription_amount:,.0f} x 3%)",
        "balance_after": new_balance,
        "created_at": now,
        "reference": referral_prospect_id,
        "processed_by": user["username"],
    })

    await log_audit("referral_commission_credited", user["username"],
                     target=referrer_username,
                     details=f"Prospect: {referral_prospect_id}, Sub: Rs.{subscription_amount}, Commission: Rs.{commission}",
                     ip_address=get_client_ip(request))

    return APIResponse(success=True, message=f"Rs.{commission:.2f} commission credited to {referrer_username}", data={
        "commission": commission,
        "new_balance": new_balance,
    })
