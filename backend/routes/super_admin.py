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
        from services.id_mapping_service import resolve_company_names
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
            result.append({
                "username": admin["username"],
                "name": admin.get("name", ""),
                "tenant_id": tid,
                "features": admin.get("features", []),
                "companies": companies_display,
                "active": admin.get("active", True),
                "employee_count": emp_count,
                "plan": admin.get("plan", "enterprise"),
                "max_companies": admin.get("max_companies", 10),
                "max_employees": admin.get("max_employees", 20),
                "billing_cycle": admin.get("billing_cycle", "annual"),
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
        plan_id = body.get("plan", "starter")
        billing_cycle = body.get("billing_cycle", "annual")
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
        await db.users.insert_one({
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
            "created_at": now
        })

        sync_token = generate_sync_token(tenant_id)

        await log_audit("admin_created", sa["username"], target=username, details=f"Tenant: {tenant_id}, Plan: {plan_id}, Features: {len(valid_features)}, Subscription: {subscription_months}mo", ip_address=get_client_ip(request))

        # Send subscription started email
        try:
            expires = subscription_expires_at(now, subscription_months)
            from datetime import datetime as dt
            exp_date = dt.fromisoformat(expires.replace("Z", "+00:00")).strftime("%d %b %Y")
            await send_subscription_started(username, name or username, plan_id, subscription_months, exp_date)
        except Exception as email_err:
            logger.error(f"Failed to send welcome email: {email_err}")

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
    """Delete an admin tenant — archives all data for audit, then removes active records."""
    sa = await _require_super_admin(request)
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
