"""Super Admin routes — manage admin tenants, features, and subscriptions."""
from fastapi import APIRouter, Request
from datetime import datetime, timezone
import logging
import re

from db import db
from models import APIResponse
from services.auth_service import (
    hash_password, verify_password, get_current_user,
    generate_sync_token, ALL_FEATURES
)
from services.audit_service import log_audit, get_client_ip
from services.ist_utils import (
    now_ist_iso, subscription_expires_at, is_subscription_active,
    days_until_expiry
)
from services.email_service import (
    send_subscription_started, send_subscription_renewed
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _require_super_admin(request: Request):
    """Allows super_admin OR flowra_staff. Endpoints that mutate tenant
    admins (POST/PUT/DELETE on /super-admin/admins/*) further restrict to
    super_admin via inline checks. Read-only endpoints accept both."""
    user = await get_current_user(request, db)
    if not user:
        return None
    if user.get("role") in ("super_admin", "flowra_staff"):
        return user
    return None


async def _require_strict_super_admin(request: Request):
    """Only super_admin — used for tenant-admin mutations and other
    super-only operations."""
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return None
    return user


# ── FLOWRA Staff feature catalogue ──────────────────────────────────────
# Each key is one tab/feature in the Command Center. Granted via checkbox
# when SuperAdmin creates a staff account. `staff_mgmt` is reserved for
# super_admin only — staff cannot grant themselves staff-management
# privileges.
STAFF_FEATURES = [
    "overview", "subscriptions", "payments", "invoices",
    "prospects", "health", "admins", "renewals",
    "referrals", "questionnaires", "backups", "activity",
]

# Feature names where flowra_staff get VIEW-ONLY access. The route
# decorator checks the request method too — GET passes, mutating verbs
# (POST/PUT/PATCH/DELETE) are blocked for staff.
STAFF_VIEW_ONLY_FEATURES = {"admins"}


async def _require_command_center(request: Request, feature: str = "", *, mutating: bool = False):
    """Gate a Command Center endpoint:
    - super_admin → always allowed
    - flowra_staff → must have `feature` in their `staff_features` list
        AND if the feature is view-only, mutating calls are rejected
    Returns (user_dict, None) on success, or (None, APIResponse) on failure.
    """
    user = await get_current_user(request, db)
    if not user:
        return None, APIResponse(success=False, error="Authentication required")
    role = user.get("role")
    if role == "super_admin":
        return user, None
    if role == "flowra_staff":
        feats = user.get("staff_features") or []
        if feature and feature not in feats:
            return None, APIResponse(
                success=False,
                error=f"Forbidden: '{feature}' is not enabled for your account",
            )
        if mutating and feature in STAFF_VIEW_ONLY_FEATURES:
            return None, APIResponse(
                success=False,
                error=f"Forbidden: '{feature}' is view-only for staff accounts",
            )
        return user, None
    return None, APIResponse(success=False, error="Forbidden: control-panel role required")


# ── Staff CRUD ─────────────────────────────────────────────────────────
@router.get("/super-admin/staff")
async def list_staff(request: Request):
    user, denied = await _require_command_center(request, "")
    if denied: return denied
    # Staff can VIEW staff list (so they know who else has access) but
    # cannot mutate it unless they're super_admin or have `staff_mgmt`.
    rows = await db.users.find(
        {"role": "flowra_staff"},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).to_list(500)
    return APIResponse(success=True, data={
        "staff": rows,
        "available_features": STAFF_FEATURES,
        "view_only_features": list(STAFF_VIEW_ONLY_FEATURES),
        "viewer_role": user.get("role"),
    })


@router.post("/super-admin/staff")
async def create_staff(request: Request):
    user = await _require_strict_super_admin(request)
    if not user:
        return APIResponse(success=False, error="Forbidden: super-admin only")
    body = await request.json()
    username = (body.get("username") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    features = body.get("features") or []
    if not username or "@" not in username:
        return APIResponse(success=False, error="Email is required and must be valid")
    if not password or len(password) < 6:
        return APIResponse(success=False, error="Password must be at least 6 characters")
    if not name:
        return APIResponse(success=False, error="Name is required")
    if not isinstance(features, list):
        return APIResponse(success=False, error="`features` must be an array")
    invalid = [f for f in features if f not in STAFF_FEATURES]
    if invalid:
        return APIResponse(success=False, error=f"Unknown feature(s): {invalid}")

    if await db.users.find_one({"username": username}):
        return APIResponse(success=False, error="A user with this email already exists")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": f"staff-{username}",
        "username": username,
        "email": username,
        "name": name,
        "password_hash": hash_password(password),
        "role": "flowra_staff",
        "tenant_id": None,
        "company_id": None,
        "staff_features": features,
        "active": True,
        "must_change_password": True,
        "created_at": now,
        "created_by": user.get("username", ""),
    }
    await db.users.insert_one(doc)
    await log_audit(db, "flowra_staff_created", user, {
        "staff_username": username, "features": features,
    }, request)
    return APIResponse(success=True, data={"username": username}, message="Staff account created")


@router.put("/super-admin/staff/{username}/features")
async def update_staff_features(username: str, request: Request):
    user = await _require_strict_super_admin(request)
    if not user:
        return APIResponse(success=False, error="Forbidden: super-admin only")
    body = await request.json()
    features = body.get("features") or []
    invalid = [f for f in features if f not in STAFF_FEATURES]
    if invalid:
        return APIResponse(success=False, error=f"Unknown feature(s): {invalid}")
    res = await db.users.update_one(
        {"username": username.lower(), "role": "flowra_staff"},
        {"$set": {"staff_features": features, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        return APIResponse(success=False, error="Staff not found")
    await log_audit(db, "flowra_staff_features_updated", user,
                    {"staff_username": username, "features": features}, request)
    return APIResponse(success=True, message="Features updated")


@router.put("/super-admin/staff/{username}/toggle-active")
async def toggle_staff_active(username: str, request: Request):
    user = await _require_strict_super_admin(request)
    if not user:
        return APIResponse(success=False, error="Forbidden: super-admin only")
    target = await db.users.find_one({"username": username.lower(), "role": "flowra_staff"}, {"_id": 0, "active": 1})
    if not target:
        return APIResponse(success=False, error="Staff not found")
    new_active = not target.get("active", True)
    await db.users.update_one(
        {"username": username.lower(), "role": "flowra_staff"},
        {"$set": {"active": new_active, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await log_audit(db, "flowra_staff_toggle_active", user,
                    {"staff_username": username, "active": new_active}, request)
    return APIResponse(success=True, data={"active": new_active})


@router.post("/super-admin/staff/{username}/reset-password")
async def reset_staff_password(username: str, request: Request):
    user = await _require_strict_super_admin(request)
    if not user:
        return APIResponse(success=False, error="Forbidden: super-admin only")
    body = await request.json()
    new_pw = body.get("password") or ""
    if len(new_pw) < 6:
        return APIResponse(success=False, error="Password must be at least 6 characters")
    res = await db.users.update_one(
        {"username": username.lower(), "role": "flowra_staff"},
        {"$set": {
            "password_hash": hash_password(new_pw),
            "must_change_password": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if res.matched_count == 0:
        return APIResponse(success=False, error="Staff not found")
    await log_audit(db, "flowra_staff_password_reset", user, {"staff_username": username}, request)
    return APIResponse(success=True, message="Password reset")


@router.delete("/super-admin/staff/{username}")
async def delete_staff(username: str, request: Request):
    user = await _require_strict_super_admin(request)
    if not user:
        return APIResponse(success=False, error="Forbidden: super-admin only")
    res = await db.users.delete_one({"username": username.lower(), "role": "flowra_staff"})
    if res.deleted_count == 0:
        return APIResponse(success=False, error="Staff not found")
    await log_audit(db, "flowra_staff_deleted", user, {"staff_username": username}, request)
    return APIResponse(success=True, message="Staff deleted")


@router.get("/super-admin/admins")
async def list_admins(request: Request):
    """List all admin tenants."""
    user, denied = await _require_command_center(request, "admins")
    if denied: return denied
    try:
        admins = await db.users.find(
            {"role": "admin"},
            {"_id": 0, "password_hash": 0}
        ).to_list(500)

        # Enrich with employee count and data stats
        from services.id_mapping_service import resolve_company_names
        from routes.seller_panel import PLAN_PRICING
        result = []
        for admin in admins:
            tid = admin.get("tenant_id", "")
            # Count all non-admin staff regardless of role (employee/dispatch/salesman).
            emp_count = await db.users.count_documents({
                "tenant_id": tid,
                "role": {"$in": ["employee", "dispatch", "salesman"]},
            })
            sync_status = await db.sync_status.find_one(
                {"tenant_id": tid, "type": "agent_sync"}, {"_id": 0}
            )
            # Resolve company UUIDs to names
            company_uuids = admin.get("companies", [])
            name_map = await resolve_company_names(tid, company_uuids)
            companies_display = [name_map.get(c, c) for c in company_uuids]

            # Compute total_billed and total_paid so the SuperAdmin UI can
            # derive a Paid / Partially Paid / Pending / Unpaid label per
            # customer without additional round-trips.
            plan_id = admin.get("plan", "starter")
            cycle = admin.get("billing_cycle", "annual")
            months = int(admin.get("subscription_months", 12) or 12)
            is_trial = bool(admin.get("is_trial"))
            pricing = PLAN_PRICING.get(plan_id, PLAN_PRICING.get("starter", {"monthly": 0, "annual": 0}))
            unit = pricing.get("annual" if cycle == "annual" else "monthly", 0) or 0
            total_billed = 0.0 if is_trial else (
                round(unit * (months / 12.0), 2) if cycle == "annual" else round(unit * months, 2)
            )
            pay_rows = await db.payments.find(
                {"customer_username": admin["username"]}, {"_id": 0, "amount": 1}
            ).to_list(1000)
            total_paid = round(sum(float(p.get("amount", 0) or 0) for p in pay_rows), 2)

            result.append({
                "username": admin["username"],
                "name": admin.get("name", ""),
                "tenant_id": tid,
                "features": admin.get("features", []),
                "companies": companies_display,
                "active": admin.get("active", True),
                "employee_count": emp_count,
                "plan": plan_id,
                "max_companies": admin.get("max_companies", 1),
                "max_employees": admin.get("max_employees", 10),
                "billing_cycle": cycle,
                "subscription_months": months,
                "subscription_start": admin.get("subscription_start", admin.get("created_at", "")),
                "created_at": admin.get("created_at", ""),
                "last_sync": sync_status.get("last_sync") if sync_status else None,
                # Rich profile echoed so SuperAdmin table can show it
                "company_name": admin.get("company_name", ""),
                "mobile": admin.get("mobile", ""),
                "gst": admin.get("gst", ""),
                "city": admin.get("city", ""),
                "industry": admin.get("industry", ""),
                # Trial + payment status
                "is_trial": is_trial,
                "trial_end": admin.get("trial_end", ""),
                "converted_at": admin.get("converted_at") or "",
                "total_billed": total_billed,
                "total_paid": total_paid,
                "balance_due": round(max(0.0, total_billed - total_paid), 2),
            })

        return APIResponse(success=True, data={
            "admins": result,
            "all_features": ALL_FEATURES,
            "total": len(result)
        })
    except Exception as e:
        logger.error(f"Error listing admins: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/super-admin/admins")
async def create_admin(request: Request):
    """Create a new admin tenant. Now accepts the rich customer form
    (email, name, mobile/WhatsApp, address, city, company_name, gst,
    sales_count, dispatch_count, industry) and, when plan=='trial',
    stamps the 14-day trial window."""
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        name = body.get("name", "")
        plan_id = body.get("plan", "starter")
        billing_cycle = body.get("billing_cycle", "annual")
        features = body.get("features", [])
        subscription_months = int(body.get("subscription_months", 12) or 12)

        # Rich customer profile (all optional except the *starred* ones on
        # the SuperAdmin form which the frontend now enforces).
        mobile         = (body.get("mobile") or "").strip()
        address        = (body.get("address") or "").strip()
        city           = (body.get("city") or "").strip()
        company_name   = (body.get("company_name") or "").strip()
        gst            = (body.get("gst") or "").strip()
        industry       = (body.get("industry") or "").strip()
        try:
            sales_count    = int(body.get("sales_count") or 0)
            dispatch_count = int(body.get("dispatch_count") or 0)
        except (TypeError, ValueError):
            sales_count = dispatch_count = 0

        if not username or not password:
            return APIResponse(success=False, error="Email and password are required")
        if len(password) < 4:
            return APIResponse(success=False, error="Password must be at least 4 characters")

        # Validate email format for new admins
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, username):
            return APIResponse(success=False, error="Username must be a valid email address")

        existing = await db.users.find_one({"username": username})
        if existing:
            return APIResponse(success=False, error="This email is already registered as a user. Please use a different email address.")

        # Also check prospects collection for cross-collection uniqueness
        import hashlib
        email_hash = hashlib.sha256(username.lower().encode()).hexdigest()
        existing_prospect = await db.prospects.find_one({"email_hash": email_hash})
        if existing_prospect:
            return APIResponse(success=False, error="This email already has a pending enquiry. Use the 'Convert Prospect' flow from the Enquiries tab, or use a different email.")

        # Get plan config
        from routes.prospects import SUBSCRIPTION_PLANS
        plan_config = SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS["starter"])

        # Use plan features if no custom features provided
        valid_features = [f for f in features if f in ALL_FEATURES] if features else list(plan_config["features"])

        # Generate a UUID tenant_id
        import uuid
        tenant_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Trial handling — when plan is "trial" we stamp the trial window
        # onto the user doc. The trial_service + login guard use these to
        # (a) send reminder emails at day 5/8/12/14 and (b) block login
        # after day 14 until the account converts.
        from services.trial_service import compute_trial_window, TRIAL_DAYS
        is_trial = (plan_id == "trial")
        trial_start = trial_end = ""
        if is_trial:
            trial_start, trial_end = compute_trial_window()
            # Trial subscription = 14 days regardless of what UI sent.
            subscription_months = 0

        user_doc = {
            "username": username,
            "password_hash": hash_password(password),
            "name": name,
            "role": "admin",
            "tenant_id": tenant_id,
            "features": valid_features,
            "companies": [],
            "active": True,
            "plan": plan_id,
            "billing_cycle": billing_cycle,
            "max_companies": plan_config["max_companies"],
            "max_employees": plan_config["max_employees"],
            "subscription_months": subscription_months,
            "subscription_start": now,
            "created_at": now,
            # Rich profile
            "mobile": mobile,
            "address": address,
            "city": city,
            "company_name": company_name,
            "gst": gst,
            "industry": industry,
            "sales_count": sales_count,
            "dispatch_count": dispatch_count,
            # Trial fields (safe defaults for paid customers so UI code
            # doesn't have to key-check).
            "is_trial": is_trial,
            "trial_start": trial_start,
            "trial_end": trial_end,
            "trial_reminders_sent": [],
            "converted_at": None,
        }
        await db.users.insert_one(user_doc)

        sync_token = generate_sync_token(tenant_id)

        await log_audit("admin_created", sa["username"], target=username,
                        details=f"Tenant: {tenant_id}, Plan: {plan_id}, Trial: {is_trial}, Features: {len(valid_features)}, Subscription: {subscription_months}mo",
                        ip_address=get_client_ip(request))

        # Rich welcome mail — includes ALL captured fields + plan details.
        # We DO NOT silently swallow failures anymore; the response bubbles
        # up an `email_sent` flag so SuperAdmin UI can flag it.
        email_sent = False
        email_error = ""
        try:
            from services.email_service import send_welcome_admin_rich
            from services.ist_utils import subscription_expires_at
            from datetime import datetime as dt

            if is_trial:
                # Trial: subscription_display = "14-day free trial"
                trial_end_dt = dt.fromisoformat(trial_end.replace("Z", "+00:00"))
                trial_end_display = trial_end_dt.strftime("%d %b %Y")
                plan_price_display = "Free"
                subscription_display = f"14-day trial (ends {trial_end_display})"
            else:
                expires = subscription_expires_at(now, subscription_months)
                exp_date = dt.fromisoformat(expires.replace("Z", "+00:00")).strftime("%d %b %Y")
                # Format plan price
                price = plan_config.get(f"{billing_cycle}_price", 0)
                plan_price_display = f"₹{price:,.0f} / {billing_cycle}"
                subscription_display = f"{subscription_months} month(s), valid until {exp_date}"
                trial_end_display = ""

            email_sent = await send_welcome_admin_rich(
                to_email=username, name=name or username, password=password,
                plan=plan_config.get("name", plan_id.title()),
                plan_price_display=plan_price_display,
                billing_cycle=billing_cycle,
                subscription_display=subscription_display,
                company_name=company_name, mobile=mobile, gst=gst,
                address=address, city=city, industry=industry,
                sales_count=sales_count, dispatch_count=dispatch_count,
                is_trial=is_trial, trial_end_display=trial_end_display,
            )
        except Exception as email_err:
            email_error = str(email_err)
            logger.error(f"Failed to send welcome email: {email_err}")

        return APIResponse(success=True, message=f"Admin '{username}' created", data={
            "username": username,
            "tenant_id": tenant_id,
            "sync_token": sync_token,
            "features": valid_features,
            "is_trial": is_trial,
            "trial_end": trial_end,
            "email_sent": bool(email_sent),
            "email_error": email_error,
        })
    except Exception as e:
        logger.error(f"Error creating admin: {e}")
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/admins/{username}/features")
async def update_admin_features(username: str, request: Request):
    """Toggle features for an admin tenant."""
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        features = body.get("features", [])
        valid_features = [f for f in features if f in ALL_FEATURES]

        result = await db.users.update_one(
            {"username": username, "role": "admin"},
            {"$set": {"features": valid_features}}
        )
        if result.matched_count == 0:
            return APIResponse(success=False, error="Admin not found")

        await log_audit("features_updated", sa["username"], target=username, details=f"Features: {', '.join(valid_features)}", ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Features updated for '{username}'", data={
            "features": valid_features
        })
    except Exception as e:
        logger.error(f"Error updating features: {e}")
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/admins/{username}/edit")
async def edit_admin_full(username: str, request: Request):
    """Edit an admin's plan, cycle, subscription months, features and
    contact fields in one call. Returns a `billing_delta` block so the
    UI can prompt the SuperAdmin to record the incremental payment
    (or refund) that comes from the change.

    billing_delta.direction ∈ {'charge', 'refund', 'none'}
    billing_delta.amount    = price paid at NEW settings − price paid at OLD settings
                              (only the not-yet-consumed portion of the OLD
                              subscription is refunded, prorated by days used).
    """
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        target = await db.users.find_one({"username": username, "role": "admin"}, {"_id": 0, "password_hash": 0})
        if not target:
            return APIResponse(success=False, error="Admin not found")

        # Compose the update — accept partial payloads so front-end can
        # patch a single field or the whole record.
        from routes.prospects import SUBSCRIPTION_PLANS
        from routes.seller_panel import PLAN_PRICING
        from services.ist_utils import subscription_expires_at
        from datetime import datetime as dt

        old_plan = target.get("plan", "starter")
        old_cycle = target.get("billing_cycle", "annual")
        old_months = int(target.get("subscription_months", 12) or 12)
        old_start = target.get("subscription_start", "") or dt.now(timezone.utc).isoformat()

        new_plan = body.get("plan", old_plan)
        new_cycle = body.get("billing_cycle", old_cycle)
        new_months = int(body.get("subscription_months", old_months) or old_months)
        new_name = body.get("name", target.get("name", ""))
        features = body.get("features")
        max_companies = body.get("max_companies")
        max_employees = body.get("max_employees")

        plan_config = SUBSCRIPTION_PLANS.get(new_plan, SUBSCRIPTION_PLANS["starter"])
        update = {
            "name": new_name,
            "plan": new_plan,
            "billing_cycle": new_cycle,
            "subscription_months": new_months,
            "max_companies": max_companies if max_companies is not None else plan_config["max_companies"],
            "max_employees": max_employees if max_employees is not None else plan_config["max_employees"],
        }
        if isinstance(features, list):
            update["features"] = [f for f in features if f in ALL_FEATURES]

        # If plan or cycle changed, reset the subscription window so the
        # new billing runs cleanly from today.
        plan_changed = (new_plan != old_plan) or (new_cycle != old_cycle) or (new_months != old_months)
        if plan_changed:
            update["subscription_start"] = dt.now(timezone.utc).isoformat()

        await db.users.update_one({"username": username, "role": "admin"}, {"$set": update})

        # ---- Billing delta calculation (proration) ----------------------
        billing_delta = {"direction": "none", "amount": 0.0,
                         "old_total": 0.0, "new_total": 0.0,
                         "refund_credit": 0.0, "narrative": ""}
        if plan_changed and old_plan != "trial" and new_plan != "trial":
            old_price = PLAN_PRICING.get(old_plan, PLAN_PRICING["starter"])
            new_price = PLAN_PRICING.get(new_plan, PLAN_PRICING["starter"])
            old_unit = old_price["annual"] if old_cycle == "annual" else old_price["monthly"]
            new_unit = new_price["annual"] if new_cycle == "annual" else new_price["monthly"]

            def _total(unit, months, cycle):
                if cycle == "annual":
                    return round(unit * (months / 12.0), 2)
                return round(unit * months, 2)

            old_total = _total(old_unit, old_months, old_cycle)
            new_total = _total(new_unit, new_months, new_cycle)

            # How much of the OLD subscription is refunded? Proportional
            # to unused days (never below 0, never above old_total).
            try:
                old_expires = subscription_expires_at(old_start, old_months)
                exp_dt = dt.fromisoformat(old_expires.replace("Z", "+00:00"))
                total_days = (exp_dt - dt.fromisoformat(old_start.replace("Z", "+00:00"))).days or 1
                unused_days = max(0, (exp_dt - dt.now(timezone.utc)).days)
                refund_credit = round(old_total * (unused_days / total_days), 2)
            except Exception:
                refund_credit = 0.0

            delta = round(new_total - refund_credit, 2)
            if abs(delta) < 1:
                direction = "none"
            elif delta > 0:
                direction = "charge"
            else:
                direction = "refund"
                delta = abs(delta)
            billing_delta = {
                "direction": direction, "amount": delta,
                "old_total": old_total, "new_total": new_total,
                "refund_credit": refund_credit,
                "narrative": (
                    f"Plan changed from {old_plan.title()} ({old_cycle}, {old_months}m) "
                    f"to {new_plan.title()} ({new_cycle}, {new_months}m). "
                    + (f"Charge Rs. {delta:.2f}" if direction == "charge"
                       else f"Refund Rs. {delta:.2f} (unused prorated credit)" if direction == "refund"
                       else "No net billing change.")
                ),
            }

        await log_audit(
            "admin_edited", sa["username"], target=username,
            details=(f"plan={new_plan}, cycle={new_cycle}, months={new_months}, "
                     f"billing_delta={billing_delta['direction']}:{billing_delta['amount']}"),
            ip_address=get_client_ip(request),
        )
        return APIResponse(success=True, message=f"Admin '{username}' updated", data={
            "username": username,
            "plan": new_plan, "billing_cycle": new_cycle,
            "subscription_months": new_months,
            "features": update.get("features", target.get("features", [])),
            "billing_delta": billing_delta,
        })
    except Exception as e:
        logger.error(f"Error editing admin: {e}")
        return APIResponse(success=False, error=str(e))




@router.put("/super-admin/admins/{username}/toggle-active")
async def toggle_admin_active(username: str, request: Request):
    """Activate or deactivate an admin tenant."""
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admin = await db.users.find_one({"username": username, "role": "admin"})
        if not admin:
            return APIResponse(success=False, error="Admin not found")

        new_status = not admin.get("active", True)
        await db.users.update_one(
            {"username": username},
            {"$set": {"active": new_status}}
        )
        await log_audit("admin_toggled", sa["username"], target=username, details=f"{'Activated' if new_status else 'Deactivated'}", ip_address=get_client_ip(request))
        return APIResponse(success=True, message=f"Admin '{username}' {'activated' if new_status else 'deactivated'}", data={
            "active": new_status
        })
    except Exception as e:
        logger.error(f"Error toggling admin: {e}")
        return APIResponse(success=False, error=str(e))


@router.delete("/super-admin/admins/{username}")
async def delete_admin(username: str, request: Request):
    """Delete an admin tenant — archives all data for audit, then removes active records."""
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admin = await db.users.find_one({"username": username, "role": "admin"}, {"_id": 0})
        if not admin:
            return APIResponse(success=False, error="Admin not found")

        tenant_id = admin.get("tenant_id")
        now = now_ist_iso()

        # 1. Archive admin user record
        admin_archive = {
            **{k: v for k, v in admin.items() if k != "password_hash"},
            "deleted_at": now,
            "deleted_by": sa["username"],
            "deletion_reason": "admin_deleted_by_superadmin",
            "original_tenant_id": tenant_id,
            "original_role": "admin",
        }
        await db.deleted_users.insert_one(admin_archive)

        # 2. Archive all staff of this admin (employee, dispatch, salesman roles)
        # Legacy code only archived role=employee — left dispatch/salesman users
        # orphaned in the DB. Fixed to cover every non-admin role.
        staff = await db.users.find(
            {"tenant_id": tenant_id, "role": {"$in": ["employee", "dispatch", "salesman"]}},
            {"_id": 0, "password_hash": 0}
        ).to_list(500)
        for emp in staff:
            emp_archive = {
                **emp,
                "deleted_at": now,
                "deleted_by": sa["username"],
                "deletion_reason": "parent_admin_deleted",
                "original_tenant_id": tenant_id,
                "original_role": emp.get("role", "employee"),
            }
            await db.deleted_users.insert_one(emp_archive)
        await db.users.delete_many({
            "tenant_id": tenant_id,
            "role": {"$in": ["employee", "dispatch", "salesman"]},
        })

        # 3. Archive all tenant data into archived_tenant_data collection
        data_collections = [
            "inventory_items", "sales_vouchers", "receipt_vouchers",
            "credit_notes", "journal_vouchers", "customers",
            "sync_status", "sync_history", "stock_journals",
            "customer_followups", "customer_targets",
            "overdue_digest", "ai_query_history"
        ]

        total_archived = 0
        for coll_name in data_collections:
            docs = await db[coll_name].find(
                {"tenant_id": tenant_id}, {"_id": 0}
            ).to_list(50000)
            if docs:
                # Store as a batch archive record
                await db.archived_tenant_data.insert_one({
                    "tenant_id": tenant_id,
                    "admin_username": username,
                    "collection": coll_name,
                    "record_count": len(docs),
                    "archived_at": now,
                    "archived_by": sa["username"],
                    "data_sample_count": min(len(docs), 5),
                    "data_summary": f"{len(docs)} records from {coll_name}",
                })
                total_archived += len(docs)
                # Delete from active collection
                await db[coll_name].delete_many({"tenant_id": tenant_id})

        # 4. Clean up renewal_requests and prospects for this tenant
        await db.renewal_requests.delete_many({"tenant_id": tenant_id})

        # 5. Delete the admin user
        await db.users.delete_one({"username": username})

        await log_audit(
            "admin_deleted", sa["username"],
            target=username,
            details=f"Tenant: {tenant_id}, Staff: {len(staff)}, Data records archived: {total_archived}",
            ip_address=get_client_ip(request)
        )

        return APIResponse(
            success=True,
            message=f"Admin '{username}' deleted. {len(staff)} staff and {total_archived} data records archived for audit."
        )
    except Exception as e:
        logger.error(f"Error deleting admin: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/deleted-users")
async def get_deleted_users(request: Request):
    """View archived/deleted users for audit purposes."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        deleted = await db.deleted_users.find(
            {}, {"_id": 0}
        ).sort("deleted_at", -1).to_list(500)

        archived_tenants = await db.archived_tenant_data.find(
            {}, {"_id": 0}
        ).sort("archived_at", -1).to_list(500)

        return APIResponse(success=True, data={
            "deleted_users": deleted,
            "archived_tenants": archived_tenants,
            "total_deleted_users": len(deleted),
            "total_archived_tenants": len(archived_tenants)
        })
    except Exception as e:
        logger.error(f"Error fetching deleted users: {e}")
        return APIResponse(success=False, error=str(e))



@router.post("/super-admin/admins/{username}/reset-password")
async def reset_admin_password(username: str, request: Request):
    """Super admin resets an admin's password."""
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        new_password = body.get("new_password", "")
        if len(new_password) < 4:
            return APIResponse(success=False, error="Password must be at least 4 characters")

        admin = await db.users.find_one({"username": username, "role": "admin"})
        if not admin:
            return APIResponse(success=False, error="Admin not found")

        await db.users.update_one(
            {"username": username},
            {"$set": {"password_hash": hash_password(new_password)}}
        )
        await log_audit("password_reset", sa["username"], target=username, details="Admin password reset by super admin", ip_address=get_client_ip(request))
        return APIResponse(success=True, message=f"Password reset for '{username}'")
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/admins/{username}/sync-token")
async def get_admin_sync_token(username: str, request: Request):
    """Get the desktop agent sync token for an admin."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admin = await db.users.find_one({"username": username, "role": "admin"})
        if not admin:
            return APIResponse(success=False, error="Admin not found")
        token = generate_sync_token(admin.get("tenant_id", ""))
        return APIResponse(success=True, data={"sync_token": token, "tenant_id": admin.get("tenant_id")})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/admins/{username}/subscription")
async def update_admin_subscription(username: str, request: Request):
    """Update admin subscription details and name."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admin = await db.users.find_one({"username": username, "role": "admin"})
        if not admin:
            return APIResponse(success=False, error="Admin not found")

        body = await request.json()
        update_fields = {}
        if "name" in body:
            update_fields["name"] = body["name"]
        if "subscription_months" in body:
            update_fields["subscription_months"] = int(body["subscription_months"])
        if "subscription_start" in body:
            update_fields["subscription_start"] = body["subscription_start"]
        if "plan" in body:
            from routes.prospects import SUBSCRIPTION_PLANS
            plan_id = body["plan"]
            if plan_id in SUBSCRIPTION_PLANS:
                plan_config = SUBSCRIPTION_PLANS[plan_id]
                update_fields["plan"] = plan_id
                update_fields["features"] = list(plan_config["features"])
                update_fields["max_companies"] = plan_config["max_companies"]
                update_fields["max_employees"] = plan_config["max_employees"]
        if "billing_cycle" in body:
            update_fields["billing_cycle"] = body["billing_cycle"]

        if update_fields:
            await db.users.update_one({"username": username}, {"$set": update_fields})

        return APIResponse(success=True, message=f"Admin '{username}' updated")
    except Exception as e:
        return APIResponse(success=False, error=str(e))



@router.get("/super-admin/stats")
async def get_super_admin_stats(request: Request):
    """Get platform-wide stats for super admin dashboard."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        total_admins = await db.users.count_documents({"role": "admin"})
        active_admins = await db.users.count_documents({"role": "admin", "active": True})
        # All non-admin staff across the platform (employee + dispatch + salesman).
        total_employees = await db.users.count_documents({
            "role": {"$in": ["employee", "dispatch", "salesman"]}
        })

        return APIResponse(success=True, data={
            "total_admins": total_admins,
            "active_admins": active_admins,
            "inactive_admins": total_admins - active_admins,
            "total_employees": total_employees,
            "all_features": ALL_FEATURES
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))



@router.get("/super-admin/renewals")
async def get_renewals(request: Request):
    """Get renewal requests and near-expiry admins."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        # Get all renewal requests
        renewal_requests = await db.renewal_requests.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)

        # Get near-expiry admins (within 30 days or already expired)
        admins = await db.users.find(
            {"role": "admin", "subscription_start": {"$exists": True, "$ne": ""}},
            {"_id": 0, "password_hash": 0}
        ).to_list(500)

        from services.id_mapping_service import resolve_company_names
        near_expiry = []
        expired = []
        for admin in admins:
            sub_start = admin.get("subscription_start", "")
            sub_months = admin.get("subscription_months", 12)
            if not sub_start:
                continue
            days_left = days_until_expiry(sub_start, sub_months)
            expires_at = subscription_expires_at(sub_start, sub_months)
            tid = admin.get("tenant_id", "")
            company_uuids = admin.get("companies", [])
            name_map = await resolve_company_names(tid, company_uuids)
            companies_display = [name_map.get(c, c) for c in company_uuids]
            entry = {
                "username": admin["username"],
                "name": admin.get("name", ""),
                "tenant_id": tid,
                "plan": admin.get("plan", ""),
                "billing_cycle": admin.get("billing_cycle", ""),
                "subscription_start": sub_start,
                "subscription_expires": expires_at,
                "days_left": days_left,
                "active": admin.get("active", True),
                "companies": companies_display,
            }
            if days_left < 0:
                expired.append(entry)
            elif days_left <= 30:
                near_expiry.append(entry)

        # Sort by urgency
        near_expiry.sort(key=lambda x: x["days_left"])
        expired.sort(key=lambda x: x["days_left"])

        stats = {
            "pending_renewals": sum(1 for r in renewal_requests if r.get("status") == "pending"),
            "near_expiry_count": len(near_expiry),
            "expired_count": len(expired),
            "total_requests": len(renewal_requests)
        }

        return APIResponse(success=True, data={
            "renewal_requests": renewal_requests,
            "near_expiry": near_expiry,
            "expired": expired,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error fetching renewals: {e}")
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/renewals/{username}/process")
async def process_renewal(username: str, request: Request):
    """SuperAdmin processes a renewal request (approve/reject)."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        action = body.get("action", "")  # approve, reject
        new_months = body.get("subscription_months", 12)
        new_plan = body.get("plan", "")
        notes = body.get("notes", "")

        if action not in ("approve", "reject"):
            return APIResponse(success=False, error="Action must be 'approve' or 'reject'")

        now = now_ist_iso()

        # Update the renewal request status
        await db.renewal_requests.update_many(
            {"username": username, "status": "pending"},
            {"$set": {"status": action + "d", "processed_at": now, "admin_notes": notes, "updated_at": now}}
        )

        if action == "approve":
            # Reset subscription start to now + extend
            update_fields = {
                "subscription_start": now,
                "subscription_months": new_months,
                "active": True
            }
            if new_plan:
                from routes.prospects import SUBSCRIPTION_PLANS
                if new_plan in SUBSCRIPTION_PLANS:
                    plan_config = SUBSCRIPTION_PLANS[new_plan]
                    update_fields["plan"] = new_plan
                    update_fields["features"] = list(plan_config["features"])
                    update_fields["max_companies"] = plan_config["max_companies"]
                    update_fields["max_employees"] = plan_config["max_employees"]

            await db.users.update_one(
                {"username": username, "role": "admin"},
                {"$set": update_fields}
            )

            # Send renewal email
            try:
                expires = subscription_expires_at(now, new_months)
                from datetime import datetime as dt
                exp_date = dt.fromisoformat(expires.replace("Z", "+00:00")).strftime("%d %b %Y")
                admin_doc = await db.users.find_one({"username": username}, {"_id": 0, "name": 1, "plan": 1})
                plan = new_plan or (admin_doc.get("plan") if admin_doc else "starter")
                admin_name = (admin_doc.get("name") if admin_doc else "") or username
                await send_subscription_renewed(username, admin_name, plan, new_months, exp_date)
            except Exception as email_err:
                logger.error(f"Failed to send renewal email: {email_err}")

        await log_audit(
            f"renewal_{action}d", sa["username"],
            target=username,
            details=f"Months: {new_months}, Plan: {new_plan or 'same'}",
            ip_address=get_client_ip(request)
        )

        return APIResponse(success=True, message=f"Renewal {action}d for '{username}'")
    except Exception as e:
        logger.error(f"Error processing renewal: {e}")
        return APIResponse(success=False, error=str(e))



# ─────────────────────────  Company-Mapping Dedup  ─────────────────────────

@router.post("/super-admin/dedup-companies")
async def dedup_companies(request: Request):
    """Collapse duplicate company_mappings rows (caused by the legacy non-deterministic
    Fernet lookup bug). Re-points all docs/users.companies to the canonical UUID and
    deletes the obsolete mapping rows. Idempotent."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        from services.id_mapping_service import deduplicate_company_mappings
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        target_tenant = (body or {}).get("tenant_id")

        # Default: dedup every tenant in one shot
        tenant_ids = (
            [target_tenant] if target_tenant
            else await db.users.distinct("tenant_id", {"tenant_id": {"$nin": [None, ""]}})
        )

        results = []
        total_removed, total_repointed, total_users = 0, 0, 0
        for t_id in tenant_ids:
            if not t_id:
                continue
            r = await deduplicate_company_mappings(t_id)
            results.append({"tenant_id": t_id, **{k: v for k, v in r.items() if k != "canonical"}})
            total_removed += r.get("removed", 0)
            total_repointed += r.get("repointed", 0)
            total_users += r.get("users_updated", 0)

        await log_audit(
            "super_admin.dedup_companies",
            sa["username"],
            details=f"tenants={len(results)}, removed={total_removed}, repointed={total_repointed}",
            ip_address=get_client_ip(request),
        )
        return APIResponse(success=True, data={
            "tenants_processed": len(results),
            "duplicates_removed": total_removed,
            "docs_repointed": total_repointed,
            "users_updated": total_users,
            "results": results,
        }, message=f"Dedup complete — removed {total_removed} duplicate company mappings")
    except Exception as e:
        logger.error(f"dedup_companies error: {e}", exc_info=True)
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/trial-reminder-preview/{username}/{day}")
async def preview_trial_reminder(username: str, day: int, request: Request):
    """Return the exact HTML + subject that would be sent for one of
    the four trial reminder days (5, 8, 12, 14). Lets the SuperAdmin
    eyeball the copy from inside FLOWRA without hitting Resend."""
    sa = await _require_strict_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    if day not in (5, 8, 12, 14):
        return APIResponse(success=False, error="Day must be one of 5, 8, 12, 14")
    try:
        # Sample data: use the target admin if they're a trial, otherwise
        # synthesise a preview payload so we can still render.
        admin = await db.users.find_one({"username": username, "role": "admin"}, {"_id": 0, "password_hash": 0})
        name = (admin or {}).get("name", "there")
        # Compute days_left / trial_end_display defensively.
        from services.trial_service import parse_iso, trial_days_remaining
        end_dt = parse_iso((admin or {}).get("trial_end", ""))
        if end_dt:
            trial_end_disp = end_dt.strftime("%d %b %Y")
            days_left = trial_days_remaining(admin) or (14 - day)
        else:
            from datetime import timedelta
            trial_end_disp = (datetime.now(timezone.utc) + timedelta(days=14 - day)).strftime("%d %b %Y")
            days_left = 14 - day

        from services.email_service import (
            send_trial_reminder_day5, send_trial_reminder_day8,
            send_trial_reminder_day12, send_trial_reminder_day14,
        )
        if day == 5:
            rendered = await send_trial_reminder_day5(username, name, days_left, trial_end_disp, preview_only=True)
        elif day == 8:
            rendered = await send_trial_reminder_day8(username, name, days_left, trial_end_disp, preview_only=True)
        elif day == 12:
            rendered = await send_trial_reminder_day12(username, name, days_left, trial_end_disp, preview_only=True)
        else:  # day == 14
            rendered = await send_trial_reminder_day14(username, name, trial_end_disp, preview_only=True)
        return APIResponse(success=True, data={
            "day": day,
            "subject": rendered["subject"],
            "html": rendered["html"],
            "sample_name": name,
            "sample_days_left": days_left if day != 14 else 0,
            "sample_trial_end": trial_end_disp,
            "recipient_preview": username,
        })
    except Exception as e:
        logger.error(f"trial reminder preview failed: {e}")
        return APIResponse(success=False, error=str(e))

