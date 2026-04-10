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

logger = logging.getLogger(__name__)
router = APIRouter()


async def _require_super_admin(request: Request):
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return None
    return user


@router.get("/super-admin/admins")
async def list_admins(request: Request):
    """List all admin tenants."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admins = await db.users.find(
            {"role": "admin"},
            {"_id": 0, "password_hash": 0}
        ).to_list(500)

        # Enrich with employee count and data stats
        result = []
        for admin in admins:
            tid = admin.get("tenant_id", "")
            emp_count = await db.users.count_documents({"tenant_id": tid, "role": "employee"})
            sync_status = await db.sync_status.find_one(
                {"tenant_id": tid, "type": "agent_sync"}, {"_id": 0}
            )
            result.append({
                "username": admin["username"],
                "name": admin.get("name", ""),
                "tenant_id": tid,
                "features": admin.get("features", []),
                "companies": admin.get("companies", []),
                "active": admin.get("active", True),
                "employee_count": emp_count,
                "subscription_months": admin.get("subscription_months", 12),
                "subscription_start": admin.get("subscription_start", admin.get("created_at", "")),
                "created_at": admin.get("created_at", ""),
                "last_sync": sync_status.get("last_sync") if sync_status else None
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
    """Create a new admin tenant."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        name = body.get("name", "")
        features = body.get("features", [])
        subscription_months = body.get("subscription_months", 12)

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
            return APIResponse(success=False, error="Username already exists")

        # Validate features
        valid_features = [f for f in features if f in ALL_FEATURES]

        # Generate a clean tenant_id from email
        clean_name = re.sub(r'[^a-z0-9]', '_', username.lower().split('@')[0])
        tenant_id = f"tenant_{clean_name}"
        # Ensure uniqueness
        existing_tenant = await db.users.find_one({"tenant_id": tenant_id})
        if existing_tenant:
            import uuid
            tenant_id = f"tenant_{clean_name}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        await db.users.insert_one({
            "username": username,
            "password_hash": hash_password(password),
            "name": name,
            "role": "admin",
            "tenant_id": tenant_id,
            "features": valid_features,
            "companies": [],
            "active": True,
            "subscription_months": subscription_months,
            "subscription_start": now,
            "created_at": now
        })

        sync_token = generate_sync_token(tenant_id)

        await log_audit("admin_created", sa["username"], target=username, details=f"Tenant: {tenant_id}, Features: {len(valid_features)}, Subscription: {subscription_months}mo", ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Admin '{username}' created", data={
            "username": username,
            "tenant_id": tenant_id,
            "sync_token": sync_token,
            "features": valid_features
        })
    except Exception as e:
        logger.error(f"Error creating admin: {e}")
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/admins/{username}/features")
async def update_admin_features(username: str, request: Request):
    """Toggle features for an admin tenant."""
    sa = await _require_super_admin(request)
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


@router.put("/super-admin/admins/{username}/toggle-active")
async def toggle_admin_active(username: str, request: Request):
    """Activate or deactivate an admin tenant."""
    sa = await _require_super_admin(request)
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
    """Delete an admin tenant and all their data."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admin = await db.users.find_one({"username": username, "role": "admin"})
        if not admin:
            return APIResponse(success=False, error="Admin not found")

        tenant_id = admin.get("tenant_id")

        # Delete all employees of this admin
        await db.users.delete_many({"tenant_id": tenant_id, "role": "employee"})

        # Delete all tenant data
        collections = [
            "inventory_items", "sales_vouchers", "receipt_vouchers",
            "credit_notes", "journal_vouchers", "customers",
            "sync_status", "sync_history", "stock_journals",
            "customer_followups", "customer_targets",
            "overdue_digest", "ai_query_history"
        ]
        for coll_name in collections:
            await db[coll_name].delete_many({"tenant_id": tenant_id})

        # Delete the admin user
        await db.users.delete_one({"username": username})

        await log_audit("admin_deleted", sa["username"], target=username, details=f"Tenant: {tenant_id}", ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Admin '{username}' and all data deleted")
    except Exception as e:
        logger.error(f"Error deleting admin: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/super-admin/admins/{username}/reset-password")
async def reset_admin_password(username: str, request: Request):
    """Super admin resets an admin's password."""
    sa = await _require_super_admin(request)
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
        total_employees = await db.users.count_documents({"role": "employee"})

        return APIResponse(success=True, data={
            "total_admins": total_admins,
            "active_admins": active_admins,
            "inactive_admins": total_admins - active_admins,
            "total_employees": total_employees,
            "all_features": ALL_FEATURES
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))
