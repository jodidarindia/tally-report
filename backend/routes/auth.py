from fastapi import APIRouter, Response, Request
from datetime import datetime, timezone
import logging

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

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/auth/login")
async def login(request: LoginRequest, raw_request: Request, response: Response):
    try:
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
        if user.get("role") == "employee":
            admin = await db.users.find_one(
                {"tenant_id": user.get("tenant_id"), "role": "admin"},
                {"_id": 0, "active": 1}
            )
            if admin and not admin.get("active", True):
                return APIResponse(success=False, error="Your organization's account has been deactivated.")

        tenant_id = user.get("tenant_id")
        token = create_access_token(user["username"], user["username"], user["role"], tenant_id)
        response.set_cookie(
            key="access_token", value=token,
            httponly=True, secure=False, samesite="lax",
            max_age=86400, path="/"
        )

        # Get companies for this tenant
        companies = []
        if tenant_id and user["role"] in ("admin", "employee"):
            admin_user = user if user["role"] == "admin" else await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"}, {"_id": 0}
            )
            companies = admin_user.get("companies", []) if admin_user else []

        await log_audit("login", user["username"], tenant_id=tenant_id or "", ip_address=get_client_ip(raw_request))

        return APIResponse(
            success=True,
            message="Login successful",
            data={
                "username": user["username"],
                "name": user.get("name", ""),
                "role": user["role"],
                "token": token,
                "tenant_id": tenant_id,
                "features": user.get("features", ALL_FEATURES if user["role"] == "admin" else []),
                "companies": companies
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

        if tenant_id and user["role"] in ("admin", "employee"):
            admin_user = user if user["role"] == "admin" else await db.users.find_one(
                {"tenant_id": tenant_id, "role": "admin"}, {"_id": 0}
            )
            if admin_user:
                companies = admin_user.get("companies", [])
                if user["role"] == "employee":
                    features = admin_user.get("features", [])

        return APIResponse(success=True, data={
            "username": user["username"],
            "name": user.get("name", ""),
            "role": user["role"],
            "tenant_id": tenant_id,
            "features": features,
            "companies": companies
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return APIResponse(success=True, message="Logged out successfully")


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
        existing = await db.users.find_one({"username": req.username})
        if existing:
            return APIResponse(success=False, error="Username already exists")

        tenant_id = user.get("tenant_id")
        new_user = {
            "username": req.username,
            "password_hash": hash_password(req.password),
            "name": req.name,
            "role": req.role if req.role in ("employee",) else "employee",
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(new_user)
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

        target = await db.users.find_one({"username": username})
        if not target:
            return APIResponse(success=False, error="User not found")

        # Admin can only delete their own employees
        if user["role"] == "admin" and target.get("tenant_id") != user.get("tenant_id"):
            return APIResponse(success=False, error="Cannot delete users outside your organization")
        if target.get("role") in ("super_admin", "admin") and user["role"] != "super_admin":
            return APIResponse(success=False, error="Only super admin can delete admins")

        result = await db.users.delete_one({"username": username})
        if result.deleted_count == 0:
            return APIResponse(success=False, error="User not found")
        return APIResponse(success=True, message=f"User '{username}' deleted")
    except Exception as e:
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
