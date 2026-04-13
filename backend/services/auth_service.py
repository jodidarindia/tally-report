import os
import bcrypt
import jwt
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from fastapi import Request
import logging

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"

ALL_FEATURES = [
    "dashboard", "sales", "crm", "inventory", "analytics",
    "salesman", "ai_reports", "insider", "ca_corner", "sync_history", "setup"
]


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "flowra_default_jwt_secret_key_2026_change_in_production")


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str, username: str, role: str, tenant_id: str = None) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])


def generate_sync_token(tenant_id: str) -> str:
    """Generate a HMAC-based token for desktop agent authentication."""
    secret = get_jwt_secret()
    msg = f"flowra_sync:{tenant_id}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_sync_token(tenant_id: str, token: str) -> bool:
    expected = generate_sync_token(tenant_id)
    return hmac.compare_digest(expected, token)


async def get_current_user(request: Request, db) -> dict:
    """Extract and validate user from JWT cookie or Authorization header."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user = await db.users.find_one({"username": payload["username"]}, {"_id": 0, "password_hash": 0})
        if not user:
            return None
        # For admin/employee, check if their tenant is active
        if user.get("role") in ("admin", "employee") and user.get("tenant_id"):
            if user["role"] == "employee":
                # Find the admin for this tenant
                admin = await db.users.find_one(
                    {"tenant_id": user["tenant_id"], "role": "admin"},
                    {"_id": 0, "active": 1, "features": 1}
                )
                if admin and not admin.get("active", True):
                    return None
                user["features"] = admin.get("features", []) if admin else []
            elif user["role"] == "admin" and not user.get("active", True):
                return None
        return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def seed_admin(db):
    """Seed super admin and default admin on startup."""
    # Seed super admin
    sa_username = os.environ.get("SUPER_ADMIN_USERNAME", "superadmin")
    sa_password = os.environ.get("SUPER_ADMIN_PASSWORD", "superadmin123")
    existing_sa = await db.users.find_one({"username": sa_username})
    if existing_sa is None:
        await db.users.insert_one({
            "username": sa_username,
            "password_hash": hash_password(sa_password),
            "name": "FLOWRA Super Admin",
            "role": "super_admin",
            "tenant_id": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Super admin '{sa_username}' seeded")
    elif existing_sa.get("role") != "super_admin":
        await db.users.update_one(
            {"username": sa_username},
            {"$set": {"role": "super_admin", "tenant_id": None}}
        )

    # Seed default admin tenant (migrate existing admin)
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing_admin = await db.users.find_one({"username": admin_username})

    if existing_admin is None:
        import uuid
        tenant_id = str(uuid.uuid4())
        await db.users.insert_one({
            "username": admin_username,
            "password_hash": hash_password(admin_password),
            "name": "Administrator",
            "role": "admin",
            "tenant_id": tenant_id,
            "features": list(ALL_FEATURES),
            "companies": [],
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin '{admin_username}' seeded with tenant '{tenant_id}'")
    else:
        tenant_id = existing_admin.get("tenant_id", "")
        # Migrate existing admin: add tenant_id and features if missing
        update_fields = {}
        if not tenant_id:
            import uuid
            tenant_id = str(uuid.uuid4())
            update_fields["tenant_id"] = tenant_id
        if not existing_admin.get("features"):
            update_fields["features"] = list(ALL_FEATURES)
        else:
            # Ensure features match ALL_FEATURES order and include any new features
            current = set(existing_admin.get("features", []))
            expected = set(ALL_FEATURES)
            if current != expected or existing_admin.get("features") != list(ALL_FEATURES):
                # Reorder to match ALL_FEATURES order, keeping only valid features + adding new ones
                update_fields["features"] = [f for f in ALL_FEATURES if f in current or f in expected]
        if "active" not in existing_admin:
            update_fields["active"] = True
        if "companies" not in existing_admin:
            update_fields["companies"] = []
        if existing_admin.get("role") != "admin":
            update_fields["role"] = "admin"
        if not verify_password(admin_password, existing_admin["password_hash"]):
            update_fields["password_hash"] = hash_password(admin_password)
        if update_fields:
            await db.users.update_one({"username": admin_username}, {"$set": update_fields})
            logger.info(f"Admin '{admin_username}' migrated with tenant fields")

    # Migrate any existing employee users to the admin's tenant
    if tenant_id:
        await db.users.update_many(
            {"role": "employee", "tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": tenant_id}}
        )

    # Migrate existing data to admin's tenant if no tenant_id yet
    collections = [
        "inventory_items", "sales_vouchers", "receipt_vouchers",
        "credit_notes", "journal_vouchers", "customers",
        "sync_status", "sync_history", "stock_journals",
        "customer_followups", "customer_targets",
        "overdue_digest", "ai_query_history"
    ]
    if tenant_id:
        for coll_name in collections:
            coll = db[coll_name]
            count = await coll.count_documents({"tenant_id": {"$exists": False}})
            if count > 0:
                await coll.update_many(
                    {"tenant_id": {"$exists": False}},
                    {"$set": {"tenant_id": tenant_id}}
                )
                logger.info(f"Migrated {count} docs in '{coll_name}' to tenant '{tenant_id}'")

    await db.users.create_index("username", unique=True)
    await db.users.create_index("tenant_id")
    await db.users.create_index("role")
    await db.prospects.create_index("prospect_id", unique=True)
    await db.prospects.create_index("email_hash", unique=True, sparse=True)
    await db.prospects.create_index("status")
    await db.demo_sessions.create_index("demo_token", unique=True)
    await db.demo_sessions.create_index("expires_at")
    await db.audit_logs.create_index([("timestamp", -1)])
    await db.audit_logs.create_index("actor")
    await db.sales_vouchers.create_index([("tenant_id", 1), ("company_id", 1)])
    await db.inventory_items.create_index([("tenant_id", 1), ("company_id", 1)])
    await db.customers.create_index([("tenant_id", 1), ("company_id", 1)])
