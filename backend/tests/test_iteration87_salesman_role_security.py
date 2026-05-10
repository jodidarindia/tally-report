"""Iteration 87 — CRITICAL security regression: salesman role MUST NOT
access admin-only `/api/salesman/*` endpoints.

Background: A duplicate `case 'salesman':` in PageRenderer.js leaked the
admin SalesmanPerformance UI to the salesman role. This test enforces
defense-in-depth on the API layer so that even if the frontend leaks a
route, salesmen cannot pull other salesmen's targets, customer maps, or
performance figures via direct API calls.
"""
import asyncio
import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import db  # noqa: E402
from services.auth_service import hash_password  # noqa: E402

BASE = "http://localhost:8001"


# Endpoints that MUST be admin-only
ADMIN_ONLY_GET = [
    "/api/salesman/master",
    "/api/salesman/performance",
    "/api/salesman/performance-detailed",
    "/api/salesman/customer-ownership",
]

# Endpoints the salesman role MUST be able to use
SALESMAN_ALLOWED_GET = [
    "/api/salesman-orders/my-customers",
    "/api/salesman-orders/catalog",
]


def test_salesman_role_blocked_from_admin_endpoints():
    tenant = f"sec-test-{uuid.uuid4().hex[:6]}"
    sm_user = f"itest_sm_{uuid.uuid4().hex[:6]}"
    ad_user = f"itest_ad_{uuid.uuid4().hex[:6]}"
    sm_pw = "Salesman@123"
    ad_pw = "Admin@123"

    async def _seed_and_test():
        # Seed both users with their respective roles
        await db.users.insert_one({
            "id": f"sec-{sm_user}",
            "username": sm_user, "email": sm_user,
            "password_hash": hash_password(sm_pw),
            "name": "ITest Salesman", "role": "salesman",
            "tenant_id": tenant, "company_id": "",
            "features": ["salesman"], "active": True,
            "must_change_password": False,
        })
        await db.users.insert_one({
            "id": f"sec-{ad_user}",
            "username": ad_user, "email": ad_user,
            "password_hash": hash_password(ad_pw),
            "name": "ITest Admin", "role": "admin",
            "tenant_id": tenant, "company_id": "",
            "features": ["salesman"], "active": True,
            "must_change_password": False,
        })

        try:
            # Use SEPARATE clients so the salesman's session-cookie isn't
            # overwritten by the admin's login (which would silently make all
            # subsequent salesman-Bearer calls authenticate as admin via the
            # cookie-first lookup in get_current_user — a test artifact, not
            # a production issue since the frontend never logs in twice).
            async with httpx.AsyncClient(base_url=BASE, timeout=15.0) as sm_cx, \
                       httpx.AsyncClient(base_url=BASE, timeout=15.0) as ad_cx:
                # Login both
                r1 = await sm_cx.post("/api/auth/login",
                                      json={"username": sm_user, "password": sm_pw})
                sm_token = r1.json()["data"]["token"]
                r2 = await ad_cx.post("/api/auth/login",
                                      json={"username": ad_user, "password": ad_pw})
                ad_token = r2.json()["data"]["token"]

                sm_hdr = {"Authorization": f"Bearer {sm_token}"}
                ad_hdr = {"Authorization": f"Bearer {ad_token}"}

                # ── Salesman role MUST be blocked on admin endpoints
                for ep in ADMIN_ONLY_GET:
                    resp = await sm_cx.get(ep, headers=sm_hdr)
                    payload = resp.json()
                    assert payload.get("success") is False, (
                        f"SECURITY LEAK: {ep} returned success=True for salesman role"
                    )
                    err = (payload.get("error") or "").lower()
                    assert "forbidden" in err or "admin" in err, (
                        f"{ep} blocked salesman but with wrong error: {err!r}"
                    )

                # ── Admin role MUST succeed on the same endpoints
                for ep in ADMIN_ONLY_GET:
                    resp = await ad_cx.get(ep, headers=ad_hdr)
                    payload = resp.json()
                    assert payload.get("success") is True, (
                        f"REGRESSION: admin blocked from {ep}: {payload.get('error')}"
                    )

                # ── Salesman MUST still be able to use their own ordering app
                for ep in SALESMAN_ALLOWED_GET:
                    resp = await sm_cx.get(ep, headers=sm_hdr)
                    payload = resp.json()
                    assert payload.get("success") is True, (
                        f"REGRESSION: salesman blocked from own endpoint {ep}: {payload.get('error')}"
                    )

                # ── Salesman MUST be blocked on POST/DELETE admin endpoints too
                resp = await sm_cx.post("/api/salesman/master", headers=sm_hdr,
                                        json={"salesman_name": "Hacker"})
                assert resp.json().get("success") is False
                resp = await sm_cx.delete("/api/salesman/master/Anything", headers=sm_hdr)
                assert resp.json().get("success") is False

        finally:
            await db.users.delete_many({"tenant_id": tenant})

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed_and_test())
    finally:
        loop.close()
