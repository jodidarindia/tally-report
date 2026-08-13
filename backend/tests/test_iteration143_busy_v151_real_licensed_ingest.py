"""Iter-143 — Backend ingest validation using the REAL v1.5.1 licensed Busy
enriched payload (COMP0002 / NAVDURGA AUTO — 12 Sundry Debtors).

Payload is generated live from /tmp/comp0002/unpacked/COMP0002 via
`flowra_busy_agent.BusyDataExtractor.extract_customers('2025-26')` — the
same code path that will run inside the Windows agent EXE (v1.5.1).

Coverage:
  1. All 12 customers land in Mongo with every v1.5.1 enrichment field intact.
  2. Legacy v1.4.x payload still upserts (backwards compat).
  3. GET /api/customers/outstanding surfaces the enriched fields to CRM.
  4. Tenant isolation — customers synced by tenant A are not visible to
     tenant B.

All API calls hit the PUBLIC REACT_APP_BACKEND_URL (not localhost).
"""
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

# ------------------------------------------------------------
# Env / URL
# ------------------------------------------------------------
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BACKEND = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BACKEND, "REACT_APP_BACKEND_URL not set in /app/frontend/.env"

REAL_DB_ROOT = "/tmp/comp0002/unpacked/COMP0002"

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())
COMPANY_A = str(uuid.uuid4())
COMPANY_B = str(uuid.uuid4())


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
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
    return AsyncIOMotorClient(mongo_url)[db_name]


@pytest.fixture(scope="module")
def real_customers():
    """Extract the 12 real Sundry Debtors from the licensed Busy DB via
    flowra_busy_agent (pure-Python access_parser path)."""
    if not os.path.isdir(REAL_DB_ROOT):
        pytest.skip(f"Real Busy DB not present at {REAL_DB_ROOT}")
    sys.path.insert(0, "/app/desktop-agent/build-kit-busy")
    try:
        from flowra_busy_agent import BusyDataExtractor  # type: ignore
    except Exception as e:
        pytest.skip(f"flowra_busy_agent import failed: {e}")
    ext = BusyDataExtractor(REAL_DB_ROOT)
    customers = list(ext.extract_customers("2025-26"))
    assert len(customers) == 12, (
        f"Expected 12 Sundry Debtors from licensed COMP0002; got {len(customers)}"
    )
    # Prefix names so we can find & clean them up without touching real data.
    for c in customers:
        c["customer_name"] = f"TEST_R143_{c['customer_name']}"
    return customers


def _sync_payload(tenant, company, cust_list):
    return {
        "data_type": "customers",
        "data": cust_list,
        "tenant_id": tenant,
        "company_id": company,
        "company_name": "TEST_R143_COMPANY",
        "sync_time": "2026-01-15T10:00:00Z",
        "sync_token": _mint_sync_token(tenant),
        "agent_version": "1.5.1-iter143-licensed-real",
    }


def _post_sync(payload):
    return requests.post(f"{BACKEND}/api/agent/sync", json=payload, timeout=45)


# ============================================================
# Sanity — backend reachable via public URL
# ============================================================
def test_public_backend_reachable():
    import time as _t
    last = None
    for _ in range(3):
        try:
            r = requests.get(f"{BACKEND}/api/health", timeout=30)
            if r.status_code == 200:
                return
            last = r.text
        except Exception as e:
            last = str(e)
        _t.sleep(2)
    pytest.fail(f"backend /api/health unreachable: {last}")


# ============================================================
# Test 1 — Real 12-customer v1.5.1 payload persists ALL enriched fields
# ============================================================
@pytest.mark.asyncio
async def test_real_v151_payload_persists_all_12_customers(real_customers):
    db = await _db()
    payload = _sync_payload(TENANT_A, COMPANY_A, real_customers)
    try:
        r = _post_sync(payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body

        docs = [d async for d in db.customers.find(
            {"tenant_id": TENANT_A, "company_id": COMPANY_A},
            {"_id": 0},
        )]
        assert len(docs) == 12, (
            f"Expected all 12 real customers persisted; got {len(docs)}"
        )

        # Every doc must have the enriched keys (empty allowed, missing NOT).
        required_keys = [
            "customer_id", "customer_name", "group_id", "group_name",
            "mobile_number", "phone", "whatsapp_number",
            "gst_number", "pan_number",
            "address", "pin_code", "station",
            "opening_balance", "closing_balance", "balance",
            "contact_person", "ledger_group",
        ]
        for d in docs:
            missing = [k for k in required_keys if k not in d]
            assert not missing, (
                f"customer {d.get('customer_name')!r} missing keys: {missing}"
            )

        # Spot-check the well-known SHITLA row from the real DB
        shitla = next(
            (d for d in docs if "SHITLA" in d.get("customer_name", "")),
            None,
        )
        assert shitla is not None, "SHITLA AUTO SPARES RAIPUR row missing"
        assert shitla["customer_id"] == "6003"
        assert shitla["mobile_number"] == "9300029026"
        assert shitla["phone"] == "9300029026"
        assert shitla["whatsapp_number"] == "919820074085"
        assert shitla["gst_number"] == "22ACOFS7545J1ZN"
        assert shitla["pan_number"] == "ACOFS7545J"
        assert shitla["pin_code"] == "492001"
        assert shitla["station"] == "BHATAGAON"
        assert shitla["contact_person"] == "SUDHIR"
        assert shitla["group_name"] == "Sundry Debtors"
        assert shitla["ledger_group"] == "Sundry Debtors"
        # Closing balance must have been captured (D22 preferred)
        assert float(shitla["closing_balance"]) == 134633.0
        assert float(shitla["balance"]) == 134633.0

        # Every real customer_id should be a non-empty string
        for d in docs:
            assert d["customer_id"], f"empty customer_id on {d['customer_name']}"
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})


# ============================================================
# Test 2 — Legacy v1.4.x payload still upserts (backwards compat)
# ============================================================
@pytest.mark.asyncio
async def test_legacy_v14_payload_backwards_compat():
    db = await _db()
    legacy = {
        "customer_name": "TEST_R143_LEGACY_V14",
        "phone": "9111111111",
        "opening_balance": 500.0,
        "ledger_group": "Sundry Debtors",
    }
    try:
        r = _post_sync(_sync_payload(TENANT_A, COMPANY_A, [legacy]))
        assert r.status_code == 200, r.text
        assert r.json().get("success") is True, r.text

        doc = await db.customers.find_one(
            {"tenant_id": TENANT_A, "customer_name": legacy["customer_name"]},
            {"_id": 0},
        )
        assert doc is not None, "legacy customer not persisted"
        assert doc["phone"] == "9111111111"
        assert doc["mobile_number"] == "9111111111"  # mirror
        assert doc["opening_balance"] == 500.0
        # New fields default to '' / 0 — no KeyError
        for k in ("group_id", "group_name", "whatsapp_number",
                  "gst_number", "pan_number", "pin_code", "station"):
            assert doc.get(k, "") == "", f"{k} should default to '' on legacy"
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})


# ============================================================
# Test 3 — /api/customers/outstanding surfaces enriched fields (CRM)
# ============================================================
@pytest.mark.asyncio
async def test_customers_outstanding_surfaces_v151_enrichment(real_customers):
    db = await _db()
    try:
        r = _post_sync(_sync_payload(TENANT_A, COMPANY_A, real_customers))
        assert r.status_code == 200 and r.json().get("success") is True, r.text

        # Seed minimal admin user for tenant A (subscription must be active)
        await db.users.update_one(
            {"tenant_id": TENANT_A, "role": "admin"},
            {"$set": {
                "tenant_id": TENANT_A, "role": "admin",
                "username": f"{TENANT_A}@test.local",
                "companies": [COMPANY_A],
                "subscription_start": "2026-01-01T00:00:00Z",
                "subscription_months": 24,
            }},
            upsert=True,
        )

        token = _forge_jwt(TENANT_A)
        rr = requests.get(
            f"{BACKEND}/api/customers/outstanding?company_id={COMPANY_A}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Company-ID": COMPANY_A,
            },
            timeout=30,
        )
        assert rr.status_code == 200, rr.text
        rows = (rr.json().get("data") or {}).get("customers") or []
        assert len(rows) >= 12, f"expected ≥12 rows, got {len(rows)}"

        shitla = next(
            (c for c in rows if "SHITLA" in c.get("customer_name", "")), None
        )
        assert shitla is not None, "SHITLA row not returned by /customers/outstanding"

        # The v1.5.1 enrichment must be surfaced to CRM
        must_have = {
            "customer_id": "6003",
            "mobile_number": "9300029026",
            "whatsapp_number": "919820074085",
            "gst_number": "22ACOFS7545J1ZN",
            "pan_number": "ACOFS7545J",
            "pin_code": "492001",
            "station": "BHATAGAON",
            "group_name": "Sundry Debtors",
            "contact_person": "SUDHIR",
        }
        for k, v in must_have.items():
            assert shitla.get(k) == v, (
                f"CRM read /customers/outstanding dropping/altering {k}: "
                f"expected {v!r}, got {shitla.get(k)!r}"
            )
        # Balance must be exposed
        assert float(shitla.get("closing_balance", 0)) == 134633.0
        # Additional keys required by CRM columns must at least exist
        for k in ("group_id", "address", "price_category", "email"):
            assert k in shitla, f"CRM read missing key {k}"
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})
        await db.users.delete_many({"tenant_id": TENANT_A,
                                    "username": f"{TENANT_A}@test.local"})


# ============================================================
# Test 4 — Tenant isolation on the real payload
# ============================================================
@pytest.mark.asyncio
async def test_tenant_isolation_with_real_payload(real_customers):
    db = await _db()
    # Take first 3 for A, next 3 for B
    a_slice = real_customers[:3]
    b_slice = [{**c, "customer_name": c["customer_name"] + "_B"}
               for c in real_customers[3:6]]
    try:
        r1 = _post_sync(_sync_payload(TENANT_A, COMPANY_A, a_slice))
        r2 = _post_sync(_sync_payload(TENANT_B, COMPANY_B, b_slice))
        assert r1.status_code == 200 and r1.json().get("success") is True, r1.text
        assert r2.status_code == 200 and r2.json().get("success") is True, r2.text

        a_names = {d["customer_name"] async for d in
                   db.customers.find({"tenant_id": TENANT_A})}
        b_names = {d["customer_name"] async for d in
                   db.customers.find({"tenant_id": TENANT_B})}

        for c in a_slice:
            assert c["customer_name"] in a_names
            assert c["customer_name"] not in b_names, "isolation broken A→B"
        for c in b_slice:
            assert c["customer_name"] in b_names
            assert c["customer_name"] not in a_names, "isolation broken B→A"
    finally:
        await db.customers.delete_many({"tenant_id": TENANT_A})
        await db.customers.delete_many({"tenant_id": TENANT_B})
