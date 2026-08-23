"""
Prospect & Public routes — signup, demo, enquiry management.
No auth required for signup/demo. SuperAdmin auth for enquiry management.
"""
from fastapi import APIRouter, Request, Response
from datetime import datetime, timezone
from typing import Optional
import logging
import re
import uuid

from db import db
from models import APIResponse
from services.auth_service import (
    hash_password, get_current_user, generate_sync_token, ALL_FEATURES
)
from services.encryption_service import encrypt_pii, decrypt_pii, PROSPECT_PII_FIELDS
from services.audit_service import log_audit, get_client_ip
from services.recaptcha import verify_recaptcha
from services.email_service import (
    send_lead_signup_notification,
    send_lead_demo_requested_notification,
    send_lead_requirements_notification,
)
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

SUBSCRIPTION_PLANS = {
    "starter": {
        "name": "Starter",
        "monthly_price": 999,
        "annual_price": 9990,
        "features": ["dashboard", "sales", "inventory", "sync_history", "setup"],
        "max_companies": 1,
        "max_employees": 2,
        "description": "Perfect for small businesses getting started with Tally analytics"
    },
    "professional": {
        "name": "Professional",
        "monthly_price": 2499,
        "annual_price": 24990,
        "features": ["dashboard", "sales", "crm", "inventory", "analytics", "salesman", "sync_history", "setup"],
        "max_companies": 1,
        "max_employees": 5,
        "description": "For growing businesses that need CRM, analytics and salesman ordering"
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price": 3799,
        "annual_price": 37990,
        "features": ALL_FEATURES,
        "max_companies": 1,
        "max_employees": 10,
        "description": "Full suite with AI reports, insider analytics and every FLOWRA capability"
    },
    "trial": {
        # 14-day free trial with FULL enterprise access. Enforced by the
        # trial_service (trial_end + is_trial fields on the user). After
        # day 14, login is blocked (soft lockout — user lands on a
        # "trial expired, convert now" screen).
        "name": "Free Trial (14 days)",
        "monthly_price": 0,
        "annual_price": 0,
        "features": ALL_FEATURES,
        "max_companies": 1,
        "max_employees": 10,
        "trial_days": 14,
        "description": "14-day free trial with full Enterprise access. Convert before day 14 to keep your data."
    }
}


# ==================== PUBLIC ENDPOINTS (No Auth) ====================

@router.get("/public/plans")
async def get_subscription_plans():
    """Public endpoint: returns subscription plans in INR."""
    return APIResponse(success=True, data={"plans": SUBSCRIPTION_PLANS})


@router.post("/public/signup")
async def prospect_signup(request: Request):
    """New customer signup — stores prospect for SuperAdmin review."""
    try:
        body = await request.json()

        # Verify reCAPTCHA
        captcha_token = (body.get("captcha_token") or "").strip()
        if not await verify_recaptcha(captcha_token):
            return APIResponse(success=False, error="CAPTCHA verification failed. Please try again.")

        company_name = (body.get("company_name") or "").strip()
        contact_person = (body.get("contact_person") or "").strip()
        email = (body.get("email") or "").strip().lower()
        phone = (body.get("phone") or "").strip()
        gst_number = (body.get("gst_number") or "").strip()
        address = (body.get("address") or "").strip()
        selected_plan = (body.get("selected_plan") or "").strip()
        message = (body.get("message") or "").strip()
        referral_code = (body.get("referral_code") or "").strip().upper()

        if not company_name or not email or not contact_person or not phone:
            return APIResponse(success=False, error="Company name, contact person, email, and phone are required")

        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, email):
            return APIResponse(success=False, error="Please enter a valid email address")

        existing = await db.users.find_one({"username": email})
        if existing:
            return APIResponse(success=False, error="This email is already registered as a user. Please login instead or use a different email address.")

        existing_prospect = await db.prospects.find_one({"email_hash": _hash_email(email)})
        if existing_prospect:
            return APIResponse(success=False, error="This email already has a pending enquiry. Our team will contact you soon. Please use a different email if this is a new request.")

        # Check if this email was previously deleted (audit awareness)
        was_deleted = await db.deleted_users.find_one({"username": email}, {"_id": 0, "deleted_at": 1, "original_tenant_id": 1})

        now = datetime.now(timezone.utc).isoformat()
        prospect_id = f"PRO-{uuid.uuid4().hex[:8].upper()}"

        prospect_data = {
            "prospect_id": prospect_id,
            "company_name": company_name,
            "contact_person": contact_person,
            "email": email,
            "phone": phone,
            "gst_number": gst_number,
            "address": address,
            "selected_plan": selected_plan,
            "message": message,
            "referral_code": referral_code,
            "status": "new",
            "demo_requested": False,
            "returning_user": bool(was_deleted),
            "previous_tenant_id": was_deleted.get("original_tenant_id", "") if was_deleted else "",
            "demo_completed": False,
            "requirements": [],
            "notes": "",
            "created_at": now,
            "updated_at": now,
            "ip_address": get_client_ip(request),
        }

        encrypted = encrypt_pii(prospect_data, PROSPECT_PII_FIELDS)
        encrypted["email_hash"] = _hash_email(email)

        await db.prospects.insert_one(encrypted)
        logger.info(f"New prospect signup: {prospect_id}")

        # Fire-and-forget admin lead notification email (Insights branded,
        # TO=support@flowralive.in, CC=jodidarindiaoffice@gmail.com).
        try:
            # ``prospect_data`` still has plaintext PII (encryption happened on
            # a separate dict above), so it is safe to forward to the email.
            asyncio.create_task(send_lead_signup_notification(prospect_data))
        except Exception as mail_err:
            logger.error(f"Lead notification email scheduling failed: {mail_err}")

        # Link referral if code provided
        if referral_code:
            referrer = await db.referral_codes.find_one({"referral_code": referral_code}, {"_id": 0})
            if referrer:
                await db.referrals.insert_one({
                    "referrer_username": referrer["username"],
                    "referrer_name": referrer.get("name", ""),
                    "referrer_role": referrer.get("role", ""),
                    "referrer_tenant_id": referrer.get("tenant_id", ""),
                    "referral_code": referral_code,
                    "prospect_id": prospect_id,
                    "referred_company": company_name,
                    "referred_email": email,
                    "status": "pending",
                    "subscription_amount": 0,
                    "commission_amount": 0,
                    "created_at": now,
                })
                logger.info(f"Referral linked: {referral_code} -> {prospect_id}")

        return APIResponse(success=True, message="Thank you! Your enquiry has been submitted. Our team will contact you shortly.", data={
            "prospect_id": prospect_id,
            "email": email
        })
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return APIResponse(success=False, error="Something went wrong. Please try again.")


@router.post("/public/demo-request")
async def request_demo(request: Request):
    """Prospect requests demo access."""
    try:
        body = await request.json()
        email = (body.get("email") or "").strip().lower()
        prospect_id = (body.get("prospect_id") or "").strip()

        if not email and not prospect_id:
            return APIResponse(success=False, error="Email or prospect ID required")

        query = {"prospect_id": prospect_id} if prospect_id else {"email_hash": _hash_email(email)}
        prospect = await db.prospects.find_one(query)
        if not prospect:
            return APIResponse(success=False, error="Enquiry not found. Please sign up first.")

        await db.prospects.update_one(
            {"_id": prospect["_id"]},
            {"$set": {"demo_requested": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

        # Notify admins (Insights-branded).
        try:
            decrypted_prospect = decrypt_pii(dict(prospect), PROSPECT_PII_FIELDS)
            decrypted_prospect.pop("_id", None)
            asyncio.create_task(send_lead_demo_requested_notification(decrypted_prospect))
        except Exception as mail_err:
            logger.error(f"Demo-request notification email failed: {mail_err}")

        demo_token = f"demo_{uuid.uuid4().hex[:16]}"
        await db.demo_sessions.insert_one({
            "prospect_id": prospect.get("prospect_id"),
            "demo_token": demo_token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + __import__('datetime').timedelta(hours=24)).isoformat(),
            "active": True
        })

        return APIResponse(success=True, message="Demo access granted! Explore FLOWRA features with sample data.", data={
            "demo_token": demo_token
        })
    except Exception as e:
        logger.error(f"Demo request error: {e}")
        return APIResponse(success=False, error="Something went wrong.")


@router.get("/public/demo-data")
async def get_demo_data(request: Request, demo_token: Optional[str] = None):
    """Returns demo/sample data for prospects. NO real customer data."""
    try:
        if demo_token:
            session = await db.demo_sessions.find_one({"demo_token": demo_token, "active": True}, {"_id": 0})
            if not session:
                return APIResponse(success=False, error="Demo session expired or invalid")

        demo = _get_demo_dataset()
        return APIResponse(success=True, data=demo)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/public/submit-requirements")
async def submit_requirements(request: Request):
    """Prospect submits feature requirements after demo."""
    try:
        body = await request.json()
        prospect_id = (body.get("prospect_id") or "").strip()
        email = (body.get("email") or "").strip().lower()
        requirements = body.get("requirements", [])
        notes = (body.get("notes") or "").strip()

        query = {"prospect_id": prospect_id} if prospect_id else {"email_hash": _hash_email(email)}
        prospect = await db.prospects.find_one(query)
        if not prospect:
            return APIResponse(success=False, error="Enquiry not found")

        await db.prospects.update_one(
            {"_id": prospect["_id"]},
            {"$set": {
                "requirements": requirements,
                "requirement_notes": notes,
                "demo_completed": True,
                "status": "requirements_submitted",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

        # Notify admins (Insights-branded).
        try:
            decrypted_prospect = decrypt_pii(dict(prospect), PROSPECT_PII_FIELDS)
            decrypted_prospect.pop("_id", None)
            asyncio.create_task(send_lead_requirements_notification(decrypted_prospect, requirements, notes))
        except Exception as mail_err:
            logger.error(f"Requirements notification email failed: {mail_err}")

        return APIResponse(success=True, message="Requirements submitted! Our team will prepare a customized proposal for you.")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ==================== SUPER ADMIN ENDPOINTS ====================

@router.get("/super-admin/prospects")
async def list_prospects(request: Request):
    """SuperAdmin: list all prospect enquiries."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        prospects_raw = await db.prospects.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        prospects = [decrypt_pii(p, PROSPECT_PII_FIELDS) for p in prospects_raw]

        stats = {
            "total": len(prospects),
            "new": sum(1 for p in prospects if p.get("status") == "new"),
            "contacted": sum(1 for p in prospects if p.get("status") == "contacted"),
            "demo_given": sum(1 for p in prospects if p.get("demo_completed")),
            "converted": sum(1 for p in prospects if p.get("status") == "converted"),
        }

        return APIResponse(success=True, data={"prospects": prospects, "stats": stats})
    except Exception as e:
        logger.error(f"Error listing prospects: {e}")
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/prospects/{prospect_id}/status")
async def update_prospect_status(prospect_id: str, request: Request):
    """SuperAdmin: update prospect status."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        new_status = body.get("status", "")
        notes = body.get("notes", "")

        valid_statuses = ["new", "contacted", "demo_given", "negotiating", "converted", "lost"]
        if new_status not in valid_statuses:
            return APIResponse(success=False, error=f"Invalid status. Use: {', '.join(valid_statuses)}")

        update = {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if notes:
            update["notes"] = notes

        result = await db.prospects.update_one({"prospect_id": prospect_id}, {"$set": update})
        if result.matched_count == 0:
            return APIResponse(success=False, error="Prospect not found")

        await log_audit("prospect_status_updated", sa["username"], target=prospect_id, details=f"Status: {new_status}", ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Prospect status updated to '{new_status}'")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/super-admin/prospects/{prospect_id}/convert")
async def convert_prospect_to_admin(prospect_id: str, request: Request):
    """SuperAdmin: convert a prospect to an actual admin account with plan-based limits."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        password = body.get("password", "")
        plan_id = body.get("plan", "starter")
        billing_cycle = body.get("billing_cycle", "annual")
        subscription_months = body.get("subscription_months", 12)

        if not password or len(password) < 6:
            return APIResponse(success=False, error="Password must be at least 6 characters")

        if plan_id not in SUBSCRIPTION_PLANS:
            return APIResponse(success=False, error=f"Invalid plan. Use: {', '.join(SUBSCRIPTION_PLANS.keys())}")

        plan = SUBSCRIPTION_PLANS[plan_id]

        prospect = await db.prospects.find_one({"prospect_id": prospect_id})
        if not prospect:
            return APIResponse(success=False, error="Prospect not found")

        decrypted = decrypt_pii(prospect, PROSPECT_PII_FIELDS)
        email = decrypted.get("email", "")
        name = decrypted.get("company_name", "")

        if not email:
            return APIResponse(success=False, error="Prospect email not found")

        existing = await db.users.find_one({"username": email})
        if existing:
            return APIResponse(success=False, error="This email is already registered as an active user. Cannot convert — use a different email or delete the existing user first.")

        tenant_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one({
            "username": email,
            "password_hash": hash_password(password),
            "name": name,
            "role": "admin",
            "tenant_id": tenant_id,
            "features": list(plan["features"]),
            "companies": [],
            "active": True,
            "plan": plan_id,
            "billing_cycle": billing_cycle,
            "max_companies": plan["max_companies"],
            "max_employees": plan["max_employees"],
            "subscription_months": subscription_months,
            "subscription_start": now,
            "converted_from_prospect": prospect_id,
            "created_at": now
        })

        await db.prospects.update_one(
            {"prospect_id": prospect_id},
            {"$set": {"status": "converted", "converted_at": now, "converted_username": email, "updated_at": now}}
        )

        sync_token = generate_sync_token(tenant_id)

        await log_audit("prospect_converted", sa["username"], target=email, details=f"Prospect {prospect_id} -> Admin, Plan: {plan_id}, Tenant: {tenant_id}", ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Prospect converted to admin! Login: {email}", data={
            "username": email,
            "tenant_id": tenant_id,
            "sync_token": sync_token,
            "plan": plan_id,
            "features": list(plan["features"]),
            "max_companies": plan["max_companies"],
            "max_employees": plan["max_employees"]
        })
    except Exception as e:
        logger.error(f"Error converting prospect: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== HELPERS ====================

async def _require_super_admin(request: Request):
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return None
    return user


def _hash_email(email: str) -> str:
    import hashlib
    return hashlib.sha256(email.lower().encode()).hexdigest()


def _get_demo_dataset():
    """Returns hardcoded demo data. NO connection to real app data."""
    return {
        "company_name": "Demo Trading Co.",
        "fy": "2025-26",
        "dashboard": {
            "total_sales": 5230000,
            "inventory_items": 156,
            "low_stock_items": 23,
            "overdue_payments": 890000,
            "top_customers": [
                {"name": "ABC Motors Pvt Ltd", "amount": 1250000},
                {"name": "Shree Krishna Traders", "amount": 980000},
                {"name": "Mahalaxmi Enterprises", "amount": 750000},
                {"name": "National Auto Parts", "amount": 620000},
                {"name": "Raj Engineering Works", "amount": 510000},
            ],
            "monthly_sales": [
                {"month": "Apr", "amount": 420000},
                {"month": "May", "amount": 380000},
                {"month": "Jun", "amount": 510000},
                {"month": "Jul", "amount": 470000},
                {"month": "Aug", "amount": 590000},
                {"month": "Sep", "amount": 630000},
                {"month": "Oct", "amount": 550000},
                {"month": "Nov", "amount": 680000},
                {"month": "Dec", "amount": 540000},
            ]
        },
        "inventory_sample": [
            {"item": "Ball Bearing 6205", "qty": 450, "value": 135000, "status": "In Stock"},
            {"item": "Oil Seal TC 30x50x7", "qty": 12, "value": 3600, "status": "Low Stock"},
            {"item": "Clutch Plate 200mm", "qty": 0, "value": 0, "status": "Out of Stock"},
            {"item": "Brake Pad Set Front", "qty": 85, "value": 170000, "status": "In Stock"},
            {"item": "Timing Belt Kit", "qty": 35, "value": 87500, "status": "In Stock"},
        ],
        "crm_sample": [
            {"customer": "ABC Motors", "outstanding": 350000, "last_payment": "2025-12-15", "aging": "30-60 days"},
            {"customer": "Shree Krishna", "outstanding": 180000, "last_payment": "2026-01-22", "aging": "0-30 days"},
            {"customer": "Mahalaxmi Ent.", "outstanding": 95000, "last_payment": "2025-11-10", "aging": "60-90 days"},
        ]
    }
