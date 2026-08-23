from fastapi import APIRouter, Response, Request
from datetime import datetime, timezone
import logging
import re
import asyncio

from db import db
from models import (
    LoginRequest, ChangePasswordRequest, CreateUserRequest,
    ResetPasswordRequest, APIResponse
)
from services.auth_service import (
    hash_password, verify_password, create_access_token,
    get_current_user, generate_sync_token, ALL_FEATURES
)
from services.audit_service import log_audit, get_client_ip
from services.ist_utils import (
    now_ist_iso, subscription_expires_at, is_subscription_active,
    days_until_expiry
)
from services.email_service import (
    send_subscription_expiry_warning,
    send_employee_created_to_employee,
    send_employee_created_to_admin
)
from services.recaptcha import verify_recaptcha

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/auth/login")
async def login(request: LoginRequest, raw_request: Request, response: Response):
    try:
        # Verify reCAPTCHA
        if not await verify_recaptcha(request.captcha_token):
            return APIResponse(success=False, error="CAPTCHA verification failed. Please try again.")

        user = await db.users.find_one({"username": request.username}, {"_id": 0})
        if not user:
            await log_audit("login_failed", request.username, ip_address=get_client_ip(raw_request), details="Invalid username")
            return APIResponse(success=False, error="Invalid username or password")
        if not verify_password(request.password, user["password_hash"]):
            await log_audit("login_failed", request.username, tenant_id=user.get("tenant_id", ""), ip_address=get_client_ip(raw_request), details="Wrong password")
            return APIResponse(success=False, error="Invalid username or password")
        # Check if admin is active
        if user.get("role") == "admin" and not user.get("active", True):
            return APIResponse(success=False, error="Your account has been deactivated. Contact FLOWRA admin.")
        # NEW (iter-110): block deactivated employees / salesmen / dispatch.
        if user.get("role") in ("employee", "dispatch", "salesman") and not user.get("active", True):
            return APIResponse(success=False, error="Your account has been deactivated. Contact your admin.")
        if user.get("role") in ("employee", "dispatch", "salesman"):
            admin = await db.users.find_one(
                {"tenant_id": user.get("tenant_id"), "role": "admin"},
                {"_id": 0, "active": 1, "subscription_start": 1, "subscription_months": 1, "username": 1, "name": 1}
            )
            if admin and not admin.get("active", True):
                return APIResponse(success=False, error="Your organization's account has been deactivated.")

        # Check subscription expiry for admin/employee
        tenant_id = user.get("tenant_id")
        sub_start = user.get("subscription_start", "")
        sub_months = user.get("subscription_months", 12)
        # Detect trial upfront — trial users must not trigger the old
        # subscription-expired check (their sub_months is 0). The trial
        # guard below handles their expiry with a different message.
        trial_flag = bool(user.get("is_trial"))
        if user.get("role") in ("employee", "dispatch", "salesman") and tenant_id:
            admin_for_sub = await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"},
                {"_id": 0, "subscription_start": 1, "subscription_months": 1, "is_trial": 1}
            )
            if admin_for_sub:
                sub_start = admin_for_sub.get("subscription_start", "")
                sub_months = admin_for_sub.get("subscription_months", 12)
                trial_flag = bool(admin_for_sub.get("is_trial"))

        sub_expired = False
        sub_days_left = 999
        sub_expires_iso = None
        if sub_start and user.get("role") != "super_admin" and not trial_flag:
            sub_expired = not is_subscription_active(sub_start, sub_months)
            sub_days_left = days_until_expiry(sub_start, sub_months)
            sub_expires_iso = subscription_expires_at(sub_start, sub_months)

        if sub_expired and user.get("role") != "super_admin":
            # iter-110: friendlier message for employees vs admin.
            if user.get("role") == "admin":
                exp_disp = ""
                try:
                    if sub_expires_iso:
                        exp_disp = datetime.fromisoformat(sub_expires_iso.replace("Z", "+00:00")).strftime("%d %b %Y")
                except Exception:
                    exp_disp = ""
                msg = (
                    f"Your subscription has expired{f' on {exp_disp}' if exp_disp else ''}. "
                    f"Renew from Profile → Subscription, or write to support@flowralive.in. "
                    f"Your team's access will resume immediately on renewal."
                )
            else:
                # Employee / salesman / dispatch — point them at THEIR admin.
                admin_for_msg = await db.users.find_one(
                    {"tenant_id": tenant_id, "role": "admin"},
                    {"_id": 0, "username": 1, "name": 1, "company_name": 1}
                ) if tenant_id else None
                admin_label = ""
                if admin_for_msg:
                    admin_label = admin_for_msg.get("name") or admin_for_msg.get("username") or ""
                msg = (
                    "Your organization's FLOWRA subscription has expired. "
                    + (f"Please ask your admin ({admin_label}) to renew. " if admin_label
                       else "Please ask your admin to renew. ")
                    + "Access will resume automatically once renewed."
                )
            return APIResponse(success=False, error=msg)

        # 14-day trial expiry — hard(er) lockout at login. We return a
        # dedicated error code so the frontend can route them to the
        # "trial expired, convert now" screen without extra roundtrips.
        # Note: this fires for the admin AND every employee under a
        # trial tenant (their admin's is_trial flag governs).
        from services.trial_service import is_trial_expired
        trial_owner = user
        if user.get("role") in ("employee", "dispatch", "salesman") and tenant_id:
            trial_owner = await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"},
                {"_id": 0, "is_trial": 1, "trial_end": 1, "converted_at": 1}
            ) or user
        if trial_owner and is_trial_expired(trial_owner):
            trial_end_disp = ""
            try:
                te = trial_owner.get("trial_end", "")
                if te:
                    trial_end_disp = datetime.fromisoformat(te.replace("Z", "+00:00")).strftime("%d %b %Y")
            except Exception:
                pass
            if user.get("role") == "admin":
                trial_msg = (
                    f"Your 14-day FLOWRA free trial ended{f' on {trial_end_disp}' if trial_end_disp else ''}. "
                    f"Please convert to a paid plan to keep your access. "
                    f"Write to support@flowralive.in or WhatsApp us on +91 81204 70018 to convert."
                )
            else:
                trial_msg = (
                    "Your organisation's FLOWRA free trial has ended. "
                    "Please ask your admin to convert to a paid plan to restore access."
                )
            return APIResponse(success=False, error=trial_msg, data={"trial_expired": True})

        token = create_access_token(user["username"], user["username"], user["role"], tenant_id)
        response.set_cookie(
            key="access_token", value=token,
            httponly=True, secure=False, samesite="lax",
            max_age=86400, path="/"
        )

        # Get companies for this tenant (UUIDs + resolved names)
        companies = []
        company_mappings = []
        if tenant_id and user["role"] in ("admin", "employee", "dispatch", "salesman"):
            admin_user = user if user["role"] == "admin" else await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"}, {"_id": 0}
            )
            companies = admin_user.get("companies", []) if admin_user else []
            # Resolve UUID company IDs to display names
            from services.id_mapping_service import get_all_company_mappings
            company_mappings = await get_all_company_mappings(tenant_id)

        await log_audit("login", user["username"], tenant_id=tenant_id or "", ip_address=get_client_ip(raw_request))

        # Send expiry warning email (non-blocking, at most once per day)
        if user.get("role") == "admin" and sub_days_left <= 30 and sub_days_left > 0:
            try:
                last_warning = user.get("last_expiry_email_sent", "")
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if last_warning != today_str:
                    import asyncio
                    exp_date = datetime.fromisoformat(sub_expires_iso.replace("Z", "+00:00")).strftime("%d %b %Y") if sub_expires_iso else "soon"
                    asyncio.create_task(send_subscription_expiry_warning(
                        user["username"], user.get("name", user["username"]), sub_days_left, exp_date
                    ))
                    await db.users.update_one({"username": user["username"]}, {"$set": {"last_expiry_email_sent": today_str}})
            except Exception as email_err:
                logger.error(f"Expiry warning email error: {email_err}")

        return APIResponse(
            success=True,
            message="Login successful",
            data={
                "username": user["username"],
                "name": user.get("name", ""),
                "role": user["role"],
                "token": token,
                "tenant_id": tenant_id,
                "features": user.get("features", ALL_FEATURES if user["role"] == "admin" else (["dispatch"] if user["role"] == "dispatch" else (["salesman"] if user["role"] == "salesman" else []))),
                # FLOWRA staff control-panel feature list — only set for
                # role==flowra_staff. Frontend uses this to show/hide tabs.
                "staff_features": user.get("staff_features", []),
                "companies": companies,
                "company_mappings": company_mappings,
                "plan": user.get("plan", "enterprise"),
                "max_companies": user.get("max_companies", 10),
                "max_employees": user.get("max_employees", 20),
                "subscription_start": sub_start or None,
                "subscription_months": sub_months,
                "subscription_expires": sub_expires_iso,
                "subscription_days_left": sub_days_left,
                "is_trial": bool(user.get("is_trial")) if user["role"] == "admin"
                            else bool((await db.users.find_one({"tenant_id": tenant_id, "role": "admin"}, {"_id": 0, "is_trial": 1}) or {}).get("is_trial")) if tenant_id else False,
                "trial_end": (user.get("trial_end") if user["role"] == "admin" else "") or "",
                "onboarding_completed": user.get("onboarding_completed", False)
            }
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/auth/me")
async def get_me(request: Request):
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")

        tenant_id = user.get("tenant_id")
        companies = []
        features = user.get("features", [])

        if tenant_id and user["role"] in ("admin", "employee", "dispatch", "salesman"):
            admin_user = user if user["role"] == "admin" else await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"}, {"_id": 0}
            )
            if admin_user:
                companies = admin_user.get("companies", [])
                if user["role"] == "employee":
                    features = admin_user.get("features", [])
                elif user["role"] == "dispatch":
                    features = ["dispatch"]
                elif user["role"] == "salesman":
                    features = ["salesman"]

        # Subscription info
        sub_start = user.get("subscription_start", "")
        sub_months = user.get("subscription_months", 12)
        if user["role"] in ("employee", "dispatch", "salesman") and tenant_id:
            admin_for_sub = await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"},
                {"_id": 0, "subscription_start": 1, "subscription_months": 1}
            )
            if admin_for_sub:
                sub_start = admin_for_sub.get("subscription_start", "")
                sub_months = admin_for_sub.get("subscription_months", 12)

        sub_expires_iso = subscription_expires_at(sub_start, sub_months) if sub_start else None
        sub_days_left = days_until_expiry(sub_start, sub_months) if sub_start else 999

        # Resolve company UUID mappings
        from services.id_mapping_service import get_all_company_mappings
        company_mappings = await get_all_company_mappings(tenant_id) if tenant_id else []

        # Trial info — echoed to the frontend so the profile modal /
        # dashboard can render a "X days left" banner without an extra
        # roundtrip. Employees under a trial admin get the flag too.
        trial_owner = user
        if user["role"] in ("employee", "dispatch", "salesman") and tenant_id:
            trial_owner = await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"},
                {"_id": 0, "is_trial": 1, "trial_end": 1, "converted_at": 1}
            ) or user

        return APIResponse(success=True, data={
            "username": user["username"],
            "name": user.get("name", ""),
            "role": user["role"],
            "tenant_id": tenant_id,
            "features": features,
            "companies": companies,
            "company_mappings": company_mappings,
            "plan": user.get("plan", "enterprise"),
            "max_companies": user.get("max_companies", 1),
            "max_employees": user.get("max_employees", 10),
            "subscription_start": sub_start or None,
            "subscription_months": sub_months,
            "subscription_expires": sub_expires_iso,
            "subscription_days_left": sub_days_left,
            "is_trial": bool(trial_owner.get("is_trial")) if trial_owner else False,
            "trial_end": (trial_owner.get("trial_end") if trial_owner else "") or "",
            "converted_at": (trial_owner.get("converted_at") if trial_owner else "") or "",
            "onboarding_completed": user.get("onboarding_completed", False)
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return APIResponse(success=True, message="Logged out successfully")


@router.post("/auth/complete-onboarding")
async def complete_onboarding(request: Request):
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        await db.users.update_one(
            {"username": user["username"]},
            {"$set": {"onboarding_completed": True}}
        )
        return APIResponse(success=True, message="Onboarding completed")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        full_user = await db.users.find_one({"username": user["username"]})
        if not verify_password(req.current_password, full_user["password_hash"]):
            return APIResponse(success=False, error="Current password is incorrect")
        await db.users.update_one(
            {"username": user["username"]},
            {"$set": {"password_hash": hash_password(req.new_password)}}
        )
        await log_audit("password_change", user["username"], tenant_id=user.get("tenant_id", ""), ip_address=get_client_ip(request))
        return APIResponse(success=True, message="Password changed successfully")
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        # Super admin can reset any admin or own password
        # Admin can reset their own employees
        if user["role"] == "super_admin":
            target = await db.users.find_one({"username": req.username})
            if not target:
                return APIResponse(success=False, error="User not found")
        elif user["role"] == "admin":
            target = await db.users.find_one({"username": req.username})
            if not target:
                return APIResponse(success=False, error="User not found")
            if target.get("tenant_id") != user.get("tenant_id"):
                return APIResponse(success=False, error="Cannot reset password for users outside your organization")
            if target.get("role") == "super_admin":
                return APIResponse(success=False, error="Cannot reset super admin password")
        else:
            return APIResponse(success=False, error="Access denied")

        await db.users.update_one(
            {"username": req.username},
            {"$set": {"password_hash": hash_password(req.new_password)}}
        )
        return APIResponse(success=True, message=f"Password reset for {req.username}")
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/auth/users")
async def create_user(req: CreateUserRequest, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] not in ("admin", "super_admin"):
            return APIResponse(success=False, error="Admin access required")

        # Validate email format
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, req.username):
            return APIResponse(success=False, error="Username must be a valid email address")

        # Check uniqueness across users collection
        existing = await db.users.find_one({"username": req.username})
        if existing:
            return APIResponse(success=False, error="This email is already registered. Please use a different email address.")

        # Check uniqueness across prospects collection
        import hashlib
        email_hash = hashlib.sha256(req.username.lower().encode()).hexdigest()
        existing_prospect = await db.prospects.find_one({"email_hash": email_hash})
        if existing_prospect:
            return APIResponse(success=False, error="This email already has a pending enquiry. Please use a different email address.")

        tenant_id = user.get("tenant_id")

        # Enforce max_employees from plan
        if user["role"] == "admin":
            max_emp = user.get("max_employees", 20)
            current_employees = await db.users.count_documents({"tenant_id": tenant_id, "role": {"$in": ["employee", "dispatch", "salesman"]}})
            if current_employees >= max_emp:
                plan_name = user.get("plan", "current").capitalize()
                return APIResponse(success=False, error=f"Employee limit reached ({max_emp}). Upgrade your {plan_name} plan to add more employees.")

        new_user = {
            "username": req.username,
            "password_hash": hash_password(req.password),
            "name": req.name,
            "role": req.role if req.role in ("employee", "dispatch", "salesman") else "employee",
            "tenant_id": tenant_id,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(new_user)

        # Send emails: credentials to employee + confirmation to admin
        admin_company = user.get("name", user.get("username", "Your Organization"))
        asyncio.create_task(
            send_employee_created_to_employee(req.username, req.name or req.username, req.password, admin_company)
        )
        # Only send admin notification if admin username is a valid email
        admin_email = user.get("username", "")
        if re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', admin_email):
            asyncio.create_task(
                send_employee_created_to_admin(admin_email, user.get("name", admin_email), req.name or req.username, req.username, "employee")
            )

        return APIResponse(success=True, message=f"User '{req.username}' created", data={"username": req.username, "role": new_user["role"]})
    except Exception as e:
        logger.error(f"Create user error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/auth/users")
async def list_users(request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] not in ("admin", "super_admin"):
            return APIResponse(success=False, error="Admin access required")

        query = {}
        if user["role"] == "admin":
            query = {"tenant_id": user.get("tenant_id"), "role": {"$ne": "super_admin"}}
        elif user["role"] == "super_admin":
            query = {"tenant_id": user.get("tenant_id")} if user.get("tenant_id") else {"role": {"$ne": "super_admin"}}

        users = await db.users.find(query, {"_id": 0, "password_hash": 0}).to_list(100)
        return APIResponse(success=True, data={"users": users})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.delete("/auth/users/{username}")
async def delete_user(username: str, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] not in ("admin", "super_admin"):
            return APIResponse(success=False, error="Admin access required")
        if username == user["username"]:
            return APIResponse(success=False, error="Cannot delete yourself")

        target = await db.users.find_one({"username": username}, {"_id": 0})
        if not target:
            return APIResponse(success=False, error="User not found")

        # Admin can only delete their own employees
        if user["role"] == "admin" and target.get("tenant_id") != user.get("tenant_id"):
            return APIResponse(success=False, error="Cannot delete users outside your organization")
        if target.get("role") in ("super_admin", "admin") and user["role"] != "super_admin":
            return APIResponse(success=False, error="Only super admin can delete admins")

        now = now_ist_iso()

        # Archive the user record before deletion
        archive_record = {
            **{k: v for k, v in target.items() if k != "password_hash"},
            "deleted_at": now,
            "deleted_by": user["username"],
            "deletion_reason": "employee_removed_by_admin",
            "original_tenant_id": target.get("tenant_id", ""),
            "original_role": target.get("role", ""),
        }
        await db.deleted_users.insert_one(archive_record)

        # Remove the user
        result = await db.users.delete_one({"username": username})
        if result.deleted_count == 0:
            return APIResponse(success=False, error="User not found")

        await log_audit(
            "employee_deleted", user["username"],
            tenant_id=user.get("tenant_id", ""),
            target=username,
            details=f"Role: {target.get('role')}, Tenant: {target.get('tenant_id')}",
            ip_address=get_client_ip(request)
        )

        return APIResponse(success=True, message=f"User '{username}' removed. Record archived for audit.")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.put("/auth/users/{username}/toggle-active")
async def toggle_user_active(username: str, request: Request):
    """Admin toggles an employee/salesman/dispatch user's active flag.
    Deactivated users cannot log in; their email stays reserved so no
    new user with the same email can be created."""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] not in ("admin", "super_admin"):
            return APIResponse(success=False, error="Admin access required")
        if username.lower() == (user.get("username") or "").lower():
            return APIResponse(success=False, error="Cannot toggle your own account")

        target = await db.users.find_one({"username": username}, {"_id": 0})
        if not target:
            return APIResponse(success=False, error="User not found")

        # Tenant isolation — admin cannot touch users outside their tenant.
        if user["role"] == "admin" and target.get("tenant_id") != user.get("tenant_id"):
            return APIResponse(success=False, error="Cannot modify users outside your organization")
        # Don't let admins toggle other admins / super-admins.
        if target.get("role") in ("admin", "super_admin") and user["role"] != "super_admin":
            return APIResponse(success=False, error="Cannot toggle this account type")

        new_active = not target.get("active", True)
        await db.users.update_one(
            {"username": username},
            {"$set": {
                "active": new_active,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "active_changed_by": user["username"],
                "active_changed_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await log_audit(
            "employee_toggle_active", user["username"],
            tenant_id=user.get("tenant_id", ""),
            target=username,
            details=f"active={new_active}, role={target.get('role')}",
            ip_address=get_client_ip(request)
        )
        return APIResponse(
            success=True,
            message=f"User '{username}' {'activated' if new_active else 'deactivated'}",
            data={"username": username, "active": new_active}
        )
    except Exception as e:
        logger.error(f"toggle_user_active error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/auth/select-company")
async def select_company(request: Request):
    """Set the active company for this session."""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")

        body = await request.json()
        company_id = body.get("company_id", "")

        tenant_id = user.get("tenant_id")
        if not tenant_id:
            return APIResponse(success=False, error="No tenant context")

        # Verify company belongs to this tenant
        admin_user = user if user["role"] == "admin" else await db.users.find_one(
            {"tenant_id": tenant_id, "role": "admin"}, {"_id": 0}
        )
        companies = admin_user.get("companies", []) if admin_user else []

        if company_id and company_id not in companies:
            return APIResponse(success=False, error="Company not found in your account")

        return APIResponse(success=True, data={"company_id": company_id, "companies": companies})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/auth/sync-token")
async def get_sync_token(request: Request):
    """Get the sync authentication token for the desktop agent."""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            return APIResponse(success=False, error="No tenant context")
        token = generate_sync_token(tenant_id)
        return APIResponse(success=True, data={"sync_token": token, "tenant_id": tenant_id})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/auth/request-renewal")
async def request_renewal(request: Request):
    """Admin requests subscription renewal. Stored for SuperAdmin review."""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")

        body = await request.json()
        plan_interest = (body.get("plan_interest") or user.get("plan", "")).strip()
        message = (body.get("message") or "").strip()

        # Check if a pending renewal already exists
        existing = await db.renewal_requests.find_one({
            "username": user["username"],
            "status": "pending"
        }, {"_id": 0})
        if existing:
            return APIResponse(success=False, error="You already have a pending renewal request. Our team will contact you shortly.")

        now = now_ist_iso()
        await db.renewal_requests.insert_one({
            "username": user["username"],
            "tenant_id": user.get("tenant_id", ""),
            "name": user.get("name", ""),
            "current_plan": user.get("plan", ""),
            "plan_interest": plan_interest,
            "current_expires": subscription_expires_at(
                user.get("subscription_start", ""),
                user.get("subscription_months", 12)
            ),
            "message": message,
            "status": "pending",
            "created_at": now,
            "updated_at": now
        })

        await log_audit("renewal_requested", user["username"],
                        tenant_id=user.get("tenant_id", ""),
                        details=f"Plan interest: {plan_interest}",
                        ip_address=get_client_ip(request))

        return APIResponse(success=True, message="Renewal request submitted! Our team will contact you shortly.")
    except Exception as e:
        logger.error(f"Renewal request error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/sync/latest-fy")
async def get_latest_fy(request: Request):
    """Get the latest financial year that has synced data for this tenant."""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")

        tenant_id = user.get("tenant_id", "")
        if not tenant_id:
            return APIResponse(success=False, error="No tenant context")

        # 1. Find the most recent sales voucher to determine FY
        latest_sale = await db.sales_vouchers.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "fy": 1, "voucher_date": 1},
            sort=[("voucher_date", -1)]
        )
        if latest_sale and latest_sale.get("fy"):
            return APIResponse(success=True, data={"latest_fy": latest_sale["fy"]})

        # 2. Check inventory items for FY
        latest_inv = await db.inventory_items.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "fy": 1},
            sort=[("fy", -1)]
        )
        if latest_inv and latest_inv.get("fy"):
            return APIResponse(success=True, data={"latest_fy": latest_inv["fy"]})

        # 3. Fallback: check sync status for last synced FY
        sync_recs = await db.sync_status.find(
            {"tenant_id": tenant_id},
            {"_id": 0, "fy": 1}
        ).to_list(100)
        fys = [r["fy"] for r in sync_recs if r.get("fy")]
        if fys:
            fys.sort(reverse=True)
            return APIResponse(success=True, data={"latest_fy": fys[0]})

        # 4. No synced data at all — return null (frontend will use current FY)
        return APIResponse(success=True, data={"latest_fy": None})
    except Exception as e:
        return APIResponse(success=False, error=str(e))
