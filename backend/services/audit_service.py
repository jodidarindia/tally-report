"""Audit logging service — records all admin actions for compliance."""
from datetime import datetime, timezone
import logging
from db import db

logger = logging.getLogger(__name__)


async def log_audit(
    action: str,
    actor_username: str,
    tenant_id: str = "",
    company_id: str = "",
    target: str = "",
    details: str = "",
    ip_address: str = "",
):
    """Insert an audit log entry."""
    try:
        doc = {
            "action": action,
            "actor": actor_username,
            "tenant_id": tenant_id,
            "company_id": company_id,
            "target": target,
            "details": details,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.audit_logs.insert_one(doc)
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


def get_client_ip(request) -> str:
    """Extract client IP from request headers (handles proxies)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
