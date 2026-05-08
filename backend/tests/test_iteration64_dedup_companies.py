"""Regression tests for iteration 64: company-mapping dedup + WS tenant scoping.

Covers the duplicate-company bug that occurred because `Fernet.encrypt` is
non-deterministic. New flow uses HMAC-SHA256 hash for lookups.
"""
import os
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


def _login(u, p):
    r = requests.post(
        f"{API_URL}/api/auth/login",
        json={"username": u, "password": p, "captcha_token": ""},
    )
    r.raise_for_status()
    return r.json()["data"]["token"]


# ───────── Idempotent company mapping ─────────

def test_register_company_mapping_idempotent():
    """Same name registered N times → SAME UUID every time. Was creating a
    fresh UUID per call before the HMAC-hash fix."""
    import asyncio
    import sys
    sys.path.insert(0, "/app/backend")
    from services.id_mapping_service import register_company_mapping
    from db import db

    async def _run():
        tenant = "test-idempotent-tenant-iter64"
        name = "Krishna Sales Corporation (from 1-Apr-24)"
        uuids = set()
        for _ in range(5):
            uuids.add(await register_company_mapping(tenant, name))
        assert len(uuids) == 1, f"Expected 1 UUID, got {len(uuids)}: {uuids}"
        # Cleanup
        await db.company_mappings.delete_many({"tenant_id": tenant})

    asyncio.run(_run())


# ───────── /api/super-admin/dedup-companies ─────────

def test_dedup_endpoint_super_admin_only():
    admin_h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.post(f"{API_URL}/api/super-admin/dedup-companies",
                      headers={**admin_h, "Content-Type": "application/json"}, json={})
    body = r.json()
    assert body["success"] is False
    assert "Super admin" in (body.get("error") or "")


def test_dedup_endpoint_idempotent():
    """Run dedup twice — second run should report 0 removed (already clean)."""
    sa_h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}",
            "Content-Type": "application/json"}
    r1 = requests.post(f"{API_URL}/api/super-admin/dedup-companies",
                       headers=sa_h, json={}).json()
    assert r1["success"] is True
    r2 = requests.post(f"{API_URL}/api/super-admin/dedup-companies",
                       headers=sa_h, json={}).json()
    assert r2["success"] is True
    # On a clean DB the second call should produce 0 removals
    assert r2["data"]["duplicates_removed"] == 0


# ───────── User.companies array has no dupes ─────────

def test_user_companies_array_has_no_duplicates():
    """The dedup migration must leave users.companies arrays without duplicates."""
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    me = requests.get(f"{API_URL}/api/auth/me", headers=h).json()
    assert me["success"] is True
    companies = me["data"].get("companies", [])
    assert len(companies) == len(set(companies)), \
        f"Duplicates detected in user.companies: {companies}"


def test_company_mappings_endpoint_returns_unique_companies():
    """`/auth/me` returns company_mappings — must have ONE row per unique name."""
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    me = requests.get(f"{API_URL}/api/auth/me", headers=h).json()
    mappings = me["data"].get("company_mappings", [])
    names = [m["company_name"] for m in mappings]
    assert len(names) == len(set(names)), \
        f"Duplicate company names returned: {names}"
