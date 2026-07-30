"""Iter-141 — Backend ingest tests for Busy Agent v1.5.0 customer enrichment.

Validates that POST /api/agent/sync (data_type='customers'):
  1. Persists ALL enriched v1.5.0 fields into the customers collection.
  2. Remains backwards-compatible with a v1.4.x-shaped payload.
  3. Is tenant-isolated — a customer synced by tenant A must not leak into
     tenant B.
  4. Read-side check: whichever endpoint the CRM tab consumes
     (/customers/outstanding) returns the enriched fields when present
     in the DB.

Agent-side unit tests (test_iteration140_busy_agent_v15_enrichment.py) are
already green — this file exercises the RUNTIME backend behaviour only.
"""
import os
import sys
import uuid
import asyncio

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BACKEND = "http://localhost:8001"

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())
COMPANY_A = str(uuid.uuid4())
COMPANY_B = str(uuid.uuid4())

# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------
def _backend_up() -> bool:
    import time as _t
    for _ in range(6):
        try:
            r = requests.get(f"{BACKEND}/api/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        _t.sleep(1.5)
    return False


def _mint_sync_token(tenant_id: str) -> str:
    sys.path.insert(0, "/app/backend")
    from services.auth_service import generate_sync_token  # type: ignore
    return generate_sync_token(tenant_id)


def _forge_jwt(tenant_id: str) -> str:
    sys.path.insert(0, "/app/backend")
    from services.auth_service import create_access_token  # type: ignore
    return create_access_token(
        user_id=f"{tenant_id}@test.local",
        username=f"{tenant_id}@test.local",
        role="admin",
        tenant_id=tenant_id,
    )


async def _db():
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not (mongo_url and db_name):
        pytest.skip("MONGO_URL / DB_NAME not set")
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


# ------------------------------------------------------------
# payload fixtures
# ------------------------------------------------------------
def _enriched_customer(name="TEST_ENRICHED_CUST_A"):
    """Full v1.5.0 shape emitted by flowra_busy_agent v1.5+."""
    return {
        "customer_id": "BUSY-CUST-001",
        "customer_name": name,
        "ledger_group": "Sundry Debtors",
        "group_id": "GRP-01",
        "group_name": "Wholesale Debtors",
        "mobile_number": "9876543210",
        "whatsapp_number": "9876543210",
        "email_id": "enriched@test.local",
        "contact_person": "Ravi Kumar",
        "address": "1st Floor, Test Complex",
        "address_line_1": "1st Floor",
        "address_line_2": "Test Complex",
        "address_line_3": "Main Bazar",
        "address_line_4": "Near Signal",
        "city": "Indore",
        "station": "INDR",
        "pin_code": "452001",
        "state": "Madhya Pradesh",
        "country": "India",
        "gst_number": "23ABCDE1234F1Z5",
        "pan_number": "ABCDE1234F",
        "salesman_id": "SM-01",
        "salesman_name": "Amit Sales",
        "salesman_mobile_number": "9000000001",
        "salesman_whatsapp_number": "9000000001",
        "price_category": "2",
        "opening_balance": 12345.67,
        "closing_balance": 22333.44,
        "balance": 22333.44,
        "outstanding_amount": 22333.44,
    }


def _legacy_customer(name="TEST_LEGACY_CUST_A"):
    """v1.4.x shape — only the old subset."""
    return {
        "customer_name": name,
        "phone": "9111111111",
        "opening_balance": 500.0,
        "ledger_group": "Sundry Debtors",
        "state": "Maharashtra",
    }


def _sync_payload(tenant, company, cust_list):
    return {
        "data_type": "customers",
        "data": cust_list,
        "tenant_id": tenant,
        "company_id": company,
        "company_name": "TEST_COMPANY",
        "sync_time": "2026-01-15T10:00:00Z",
        "sync_token": _mint_sync_token(tenant),
        "agent_version": "1.5.0-iter141-test",
    }


# ============================================================
# Test 1 — enriched payload persists all fields
# ============================================================
@pytest.mark.asyncio
async def test_enriched_v15_payload_persists_all_fields():
    if not _backend_up():
        pytest.skip("backend not running")
    db = await _db()
    cust = _enriched_customer("TEST_ENRICHED_CUST_A")
    try:
        r = requests.post(f"{BACKEND}/api/agent/sync",
                          json=_sync_payload(TENANT_A, COMPANY_A, [cust]),
                          timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body

        doc = await db.customers.find_one(
            {"tenant_id": TENANT_A, "company_id": COMPANY_A,
             "customer_name": cust["customer_name"]},
            {"_id": 0},
        )
        assert doc is not None, "enriched customer was not persisted"

        # Every enriched field must round-trip
        assert doc["customer_id"] == "BUSY-CUST-001"
        assert doc["group_id"] == "GRP-01"
        assert doc["group_name"] == "Wholesale Debtors"
        assert doc["mobile_number"] == "9876543210"
        assert doc["phone"] == "9876543210"   # mirrored
        assert doc["whatsapp_number"] == "9876543210"
        assert doc["email"] == "enriched@test.local"
        assert doc["contact_person"] == "Ravi Kumar"
        assert doc["address"] == "1st Floor, Test Complex"
        assert doc["address_line_1"] == "1st Floor"
        assert doc["address_line_2"] == "Test Complex"
        assert doc["address_line_3"] == "Main Bazar"
        assert doc["address_line_4"] == "Near Signal"
        assert doc["city"] == "Indore"
        assert doc["station"] == "INDR"
        assert doc["pin_code"] == "452001"
        assert doc["state"] == "Madhya Pradesh"
        assert doc["country"] == "India"
        assert doc["gst_number"] == "23ABCDE1234F1Z5"
        assert doc["pan_number"] == "ABCDE1234F"
        assert doc["salesman_id"] == "SM-01"
        assert doc["salesman_name"] == "Amit Sales"
        assert doc["salesman_mobile_number"] == "9000000001"
        assert doc["salesman_whatsapp_number"] == "9000000001"
        assert doc["price_category"] == "2"
        assert doc["closing_balance"] == 22333.44
        assert doc["balance"] == 22333.44
        assert doc["opening_balance"] == 12345.67
        assert doc["ledger_group"] == "Sundry Debtors"
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})


# ============================================================
# Test 2 — v1.4.x legacy payload still upserts
# ============================================================
@pytest.mark.asyncio
async def test_legacy_v14_payload_still_persists_no_keyerror():
    if not _backend_up():
        pytest.skip("backend not running")
    db = await _db()
    cust = _legacy_customer("TEST_LEGACY_CUST_A")
    try:
        r = requests.post(f"{BACKEND}/api/agent/sync",
                          json=_sync_payload(TENANT_A, COMPANY_A, [cust]),
                          timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body

        doc = await db.customers.find_one(
            {"tenant_id": TENANT_A, "company_id": COMPANY_A,
             "customer_name": cust["customer_name"]},
            {"_id": 0},
        )
        assert doc is not None, "legacy customer was not persisted"
        # Old subset preserved
        assert doc["phone"] == "9111111111"
        assert doc["mobile_number"] == "9111111111"   # mirrored from phone
        assert doc["opening_balance"] == 500.0
        assert doc["ledger_group"] == "Sundry Debtors"
        assert doc["state"] == "Maharashtra"
        # New fields default to empty / 0 — no KeyError
        for empty_field in ("group_id", "group_name", "whatsapp_number",
                            "email", "gst_number", "pan_number",
                            "address_line_1", "address_line_2",
                            "address_line_3", "address_line_4", "city",
                            "station", "pin_code", "country",
                            "salesman_id", "salesman_name",
                            "salesman_mobile_number",
                            "salesman_whatsapp_number"):
            assert doc.get(empty_field, "") == "", (
                f"{empty_field} should default to '' for legacy payload, "
                f"got {doc.get(empty_field)!r}"
            )
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})


# ============================================================
# Test 3 — tenant isolation
# ============================================================
@pytest.mark.asyncio
async def test_customers_are_tenant_isolated():
    if not _backend_up():
        pytest.skip("backend not running")
    db = await _db()
    cust_a = _enriched_customer("TEST_ISOLATION_CUST_A")
    cust_b = _enriched_customer("TEST_ISOLATION_CUST_B")
    try:
        # sync under tenant A
        r1 = requests.post(f"{BACKEND}/api/agent/sync",
                           json=_sync_payload(TENANT_A, COMPANY_A, [cust_a]),
                           timeout=15)
        assert r1.status_code == 200 and r1.json().get("success") is True, r1.text
        # sync under tenant B
        r2 = requests.post(f"{BACKEND}/api/agent/sync",
                           json=_sync_payload(TENANT_B, COMPANY_B, [cust_b]),
                           timeout=15)
        assert r2.status_code == 200 and r2.json().get("success") is True, r2.text

        # Tenant A must NOT see B's row
        a_names = {d["customer_name"] async for d in
                   db.customers.find({"tenant_id": TENANT_A})}
        b_names = {d["customer_name"] async for d in
                   db.customers.find({"tenant_id": TENANT_B})}
        assert cust_a["customer_name"] in a_names
        assert cust_b["customer_name"] not in a_names, (
            "TENANT ISOLATION BROKEN: tenant A sees tenant B's customer"
        )
        assert cust_b["customer_name"] in b_names
        assert cust_a["customer_name"] not in b_names, (
            "TENANT ISOLATION BROKEN: tenant B sees tenant A's customer"
        )
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})
        await db.customers.delete_many({"tenant_id": TENANT_B})


# ============================================================
# Test 4 — cross-tenant sync_token rejection
# ============================================================
def test_sync_token_from_tenant_A_cannot_write_for_tenant_B():
    if not _backend_up():
        pytest.skip("backend not running")
    cust = _enriched_customer("TEST_XT_TOKEN_LEAK")
    bad_payload = {
        "data_type": "customers",
        "data": [cust],
        "tenant_id": TENANT_B,
        "company_id": COMPANY_B,
        "company_name": "TEST_COMPANY",
        "sync_time": "2026-01-15T10:00:00Z",
        # Note: token minted for tenant A but posted with tenant_id=B
        "sync_token": _mint_sync_token(TENANT_A),
        "agent_version": "1.5.0-iter141-test",
    }
    r = requests.post(f"{BACKEND}/api/agent/sync",
                      json=bad_payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is False, (
        "Cross-tenant sync token should be rejected"
    )
    assert "token" in (body.get("error") or "").lower()


# ============================================================
# Test 5 — CRM read side (whichever endpoint feeds the CRM tab)
# The tab reads /api/customers/outstanding. Verify enriched fields
# are surfaced when present in DB.
# ============================================================
@pytest.mark.asyncio
async def test_customers_outstanding_surfaces_enriched_fields():
    if not _backend_up():
        pytest.skip("backend not running")
    db = await _db()
    cust = _enriched_customer("TEST_READSIDE_ENRICHED")
    try:
        # First persist via sync endpoint
        r = requests.post(f"{BACKEND}/api/agent/sync",
                          json=_sync_payload(TENANT_A, COMPANY_A, [cust]),
                          timeout=15)
        assert r.status_code == 200 and r.json().get("success") is True, r.text

        # Also seed a user record so the endpoint's admin lookup does not
        # throw. /customers/outstanding does not strictly require it, but
        # some downstream services do. We create a minimal admin.
        await db.users.update_one(
            {"tenant_id": TENANT_A, "role": "admin"},
            {"$set": {"tenant_id": TENANT_A, "role": "admin",
                      "username": f"{TENANT_A}@test.local",
                      "companies": [COMPANY_A],
                      "subscription_start": "2026-01-01T00:00:00Z",
                      "subscription_months": 24}},
            upsert=True,
        )

        token = _forge_jwt(TENANT_A)
        rr = requests.get(
            f"{BACKEND}/api/customers/outstanding?company_id={COMPANY_A}",
            headers={"Authorization": f"Bearer {token}",
                     "X-Company-ID": COMPANY_A},
            timeout=15,
        )
        assert rr.status_code == 200, rr.text
        data = rr.json().get("data") or {}
        rows = data.get("customers") or []
        target = next((c for c in rows
                       if c.get("customer_name") == cust["customer_name"]),
                      None)
        assert target is not None, (
            f"Enriched customer not returned by /customers/outstanding. "
            f"rows returned: {[c.get('customer_name') for c in rows][:10]}"
        )
        # Existing fields the CRM already relied on
        assert target.get("phone") == "9876543210"
        assert target.get("state") == "Madhya Pradesh"

        # v1.5.0 enrichment: assert enriched fields are actually surfaced.
        # If these fail, the sync stored the fields correctly but the CRM
        # read endpoint does NOT expose them → the CRM UI cannot show the
        # new columns (mobile/whatsapp/gst/salesman etc.).
        missing = [k for k in (
            "mobile_number", "whatsapp_number", "email", "gst_number",
            "pan_number", "address", "city", "station", "pin_code",
            "salesman_id", "salesman_name", "price_category",
            "group_id", "group_name",
        ) if k not in target]
        assert not missing, (
            f"/customers/outstanding is DROPPING enriched fields: {missing}. "
            f"Sync persists them but the read endpoint projects them out."
        )
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})
        await db.users.delete_many({"tenant_id": TENANT_A,
                                    "username": f"{TENANT_A}@test.local"})
