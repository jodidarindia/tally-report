"""Tenant context helpers for multi-tenant data isolation."""
from fastapi import Request
from db import db
from services.auth_service import get_current_user


async def get_tenant_context(request: Request) -> dict:
    """Extract tenant context from the authenticated user.
    Returns dict with tenant_id, company_id, role, features, user.
    Returns None if not authenticated."""
    user = await get_current_user(request, db)
    if not user:
        return None

    role = user.get("role", "employee")
    tenant_id = user.get("tenant_id")
    features = user.get("features", [])

    # Get company_id from header or query param
    company_id = request.headers.get("X-Company-ID", "")
    if not company_id:
        company_id = request.query_params.get("company_id", "")

    # Super admin has no tenant context (can't see data)
    if role == "super_admin":
        return {
            "user": user,
            "role": role,
            "tenant_id": None,
            "company_id": None,
            "features": []
        }

    return {
        "user": user,
        "role": role,
        "tenant_id": tenant_id,
        "company_id": company_id or None,
        "features": features
    }


def tenant_filter(tenant_id: str, company_id: str = None) -> dict:
    """Build a MongoDB filter dict for tenant isolation."""
    f = {"tenant_id": tenant_id}
    if company_id:
        f["company_id"] = company_id
    return f
