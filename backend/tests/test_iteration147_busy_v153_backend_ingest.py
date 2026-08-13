"""Iteration 147 — Busy Agent v1.5.3 backend ingest round-trip.

Verifies against the LIVE preview backend (REACT_APP_BACKEND_URL) that:
  1. The two NEW voucher categories introduced in v1.5.3
     (data_type='payment_vouchers', data_type='sundry_journals') are
     accepted by POST /api/agent/sync and land in Mongo.
  2. Existing categories with v1.5.3 fixed VchType mapping still ingest
     cleanly (purchases, contra, journals, debit_notes, credit_notes).
  3. Tenant isolation holds — a foreign tenant_id cannot read our writes
     (indirect: our writes must carry the expected tenant_id).
  4. Existing v1.5.2 customer flow + /api/customers/outstanding still
     returns enriched fields (mobile_number, gst_number, closing_balance …).

Auth strategy:
  • /api/agent/sync uses HMAC sync_token from services.auth_service.
  • /api/customers/outstanding uses admin JWT cookie/bearer from
    /api/auth/login (admin / admin123 per /app/memory/test_credentials.md).
"""
import os
import sys
import uuid
import pytest
import requests
from pathlib import Path

# Load backend .env so JWT_SECRET, MONGO_URL, DB_NAME etc are available
try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:
    for _line in Path("/app/backend/.env").read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# Agent extractor path
sys.path.insert(0, "/app/desktop-agent/build-kit-busy")
# Backend path (for auth_service.generate_sync_token)
sys.path.insert(0, "/app/backend")

REAL_DB_ROOT = Path("/tmp/comp0002/unpacked/COMP0002")
REAL_DB_AVAILABLE = (REAL_DB_ROOT / "db12025.bds").exists()

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback read frontend .env — REACT_APP_BACKEND_URL isn't in the
    # pytest shell environment by default.
    fe_env = Path("/app/frontend/.env").read_text()
    for line in fe_env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_TENANT = "3079b0af-e899-44b4-ae7c-c35d113fe296"
ADMIN_COMPANY = "03f638d1-eab0-47ee-aed6-59049ebb5207"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

CHUNK = 50  # per problem statement: chunk large payloads to ~50 records


# ─────────────────────── Fixtures ───────────────────────
@pytest.fixture(scope="module")
def sync_token():
    from services.auth_service import generate_sync_token
    return generate_sync_token(ADMIN_TENANT)


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    tok = None
    # Try common token locations
    if isinstance(body, dict):
        tok = body.get("token") or body.get("access_token") or (body.get("data") or {}).get("token") or (body.get("data") or {}).get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def extractor():
    if not REAL_DB_AVAILABLE:
        pytest.skip("Real Busy 21 sample DB not present")
    from flowra_busy_agent import BusyDataExtractor
    return BusyDataExtractor(str(REAL_DB_ROOT))


def _post_sync(data_type: str, records: list, sync_token: str):
    payload = {
        "data_type": data_type,
        "data": records,
        "sync_time": "2026-08-13T00:00:00+05:30",
        "tenant_id": ADMIN_TENANT,
        "company_id": ADMIN_COMPANY,
        "sync_token": sync_token,
        "financial_year": "2025-26",
    }
    return requests.post(f"{BASE_URL}/api/agent/sync", json=payload, timeout=120)


async def _mongo_count(collection_name: str, extra_filter: dict = None):
    """Direct Mongo count for assertion — the read-side API for these
    collections doesn't necessarily exist, so we verify persistence via
    the same db handle the backend uses."""
    from db import db
    q = {"tenant_id": ADMIN_TENANT, "company_id": ADMIN_COMPANY}
    if extra_filter:
        q.update(extra_filter)
    return await getattr(db, collection_name).count_documents(q)


def _count(collection_name: str, extra_filter: dict = None):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _mongo_count(collection_name, extra_filter)
    )


# ─────────────────────── 1. Auth / handshake ───────────────────────
def test_backend_reachable():
    r = requests.get(f"{BASE_URL}/api/agent/latest-version", timeout=60)
    assert r.status_code == 200, f"backend not reachable: {r.status_code}"


def test_sync_rejects_missing_token():
    r = requests.post(
        f"{BASE_URL}/api/agent/sync",
        json={"data_type": "payment_vouchers", "data": [], "tenant_id": ADMIN_TENANT},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False
    assert "sync_token" in (body.get("error") or "").lower()


def test_sync_rejects_bad_token():
    r = requests.post(
        f"{BASE_URL}/api/agent/sync",
        json={
            "data_type": "payment_vouchers", "data": [],
            "tenant_id": ADMIN_TENANT, "sync_token": "bogus",
        },
        timeout=15,
    )
    body = r.json()
    assert body.get("success") is False
    assert "invalid" in (body.get("error") or "").lower()


# ─────────────────────── 2. NEW: payment_vouchers ───────────────────────
@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_payment_vouchers_ingest(extractor, sync_token):
    payments = list(extractor.extract_payments("2025-26"))
    assert len(payments) > 400, f"extractor yielded {len(payments)} payments — expected 400+"
    chunk = payments[:CHUNK]

    r = _post_sync("payment_vouchers", chunk, sync_token)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    assert body.get("success") is True, body

    # Persistence check: rows landed with expected shape
    count = _count("payment_vouchers")
    assert count >= len(chunk), f"expected >= {len(chunk)} payment_vouchers, got {count}"

    # Field shape spot-check on first ingested record
    from db import db
    import asyncio
    doc = asyncio.get_event_loop().run_until_complete(
        db.payment_vouchers.find_one(
            {"tenant_id": ADMIN_TENANT, "company_id": ADMIN_COMPANY,
             "voucher_id": chunk[0]["voucher_id"]}, {"_id": 0}
        )
    )
    assert doc is not None, "first payment voucher not persisted"
    assert doc["voucher_type"] == "payment"
    for k in ("voucher_id", "voucher_date", "party_name",
              "party_code", "total_amount", "ledger_entries", "tenant_id", "company_id"):
        assert k in doc, f"payment voucher doc missing key {k}"
    assert doc["tenant_id"] == ADMIN_TENANT
    assert doc["company_id"] == ADMIN_COMPANY


# ─────────────────────── 3. NEW: sundry_journals ───────────────────────
@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_sundry_journals_ingest(extractor, sync_token):
    sundry = list(extractor.extract_sundry_journals("2025-26"))
    assert len(sundry) >= 10, f"extractor yielded {len(sundry)} sundry — expected 10+"

    r = _post_sync("sundry_journals", sundry, sync_token)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    assert body.get("success") is True, body

    count = _count("sundry_journals")
    assert count >= len(sundry), f"expected >= {len(sundry)} sundry_journals, got {count}"

    from db import db
    import asyncio
    doc = asyncio.get_event_loop().run_until_complete(
        db.sundry_journals.find_one(
            {"tenant_id": ADMIN_TENANT, "company_id": ADMIN_COMPANY,
             "voucher_id": sundry[0]["voucher_id"]}, {"_id": 0}
        )
    )
    assert doc is not None
    assert doc["voucher_type"] == "sundry_journal"
    assert doc["tenant_id"] == ADMIN_TENANT


# ─────────────────────── 4. Regression on existing categories ───────────────────────
@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_purchase_vouchers_ingest(extractor, sync_token):
    rows = list(extractor.extract_purchases("2025-26"))[:CHUNK]
    assert rows, "no purchases from extractor"
    r = _post_sync("purchase_vouchers", rows, sync_token)
    assert r.status_code == 200 and r.json().get("success"), r.text[:400]
    assert _count("purchase_vouchers") >= len(rows)


@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_contra_vouchers_ingest(extractor, sync_token):
    rows = list(extractor.extract_contra("2025-26"))[:CHUNK]
    assert rows, "no contra from extractor"
    r = _post_sync("contra_vouchers", rows, sync_token)
    assert r.status_code == 200 and r.json().get("success"), r.text[:400]
    assert _count("contra_vouchers") >= len(rows)


@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_journal_vouchers_ingest(extractor, sync_token):
    rows = list(extractor.extract_journals("2025-26"))
    assert len(rows) >= 3
    r = _post_sync("journal_vouchers", rows, sync_token)
    assert r.status_code == 200 and r.json().get("success"), r.text[:400]
    assert _count("journal_vouchers") >= len(rows)


@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_debit_notes_ingest(extractor, sync_token):
    rows = list(extractor.extract_debit_notes("2025-26"))
    r = _post_sync("debit_notes", rows, sync_token)
    assert r.status_code == 200 and r.json().get("success"), r.text[:400]
    # Real DB has 1 debit note; ensure it lands
    assert _count("debit_notes") >= len(rows)


@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_credit_notes_ingest_folded(extractor, sync_token):
    rows = list(extractor.extract_credit_notes("2025-26"))[:CHUNK]
    assert len(rows) >= 10
    r = _post_sync("credit_notes", rows, sync_token)
    assert r.status_code == 200 and r.json().get("success"), r.text[:400]
    assert _count("credit_notes") >= len(rows)


# ─────────────────────── 5. Existing v1.5.2 customer + outstanding round-trip ───────────────────────
@pytest.mark.skipif(not REAL_DB_AVAILABLE, reason="Real Busy 21 sample DB not present")
def test_customers_ingest_still_works(extractor, sync_token):
    """v1.5.2 regression fence — enriched customer fields must ingest."""
    rows = list(extractor.extract_customers("2025-26"))[:CHUNK]
    if not rows:
        pytest.skip("no customers in extractor output")
    r = _post_sync("customers", rows, sync_token)
    assert r.status_code == 200 and r.json().get("success"), r.text[:400]

    from db import db
    import asyncio
    doc = asyncio.get_event_loop().run_until_complete(
        db.customers.find_one(
            {"tenant_id": ADMIN_TENANT, "company_id": ADMIN_COMPANY,
             "customer_name": rows[0].get("customer_name")}, {"_id": 0}
        )
    )
    assert doc is not None, f"customer {rows[0].get('customer_name')} not persisted"


def test_customers_outstanding_endpoint(admin_session):
    """Round-trip: /api/customers/outstanding returns 200 with the
    v1.5.2 enriched fields surfaced when present in Mongo. This tenant
    (ASA AUTOTECH) may or may not have the enriched fields — the
    assertion here is that the endpoint honours the projection."""
    r = admin_session.get(
        f"{BASE_URL}/api/customers/outstanding",
        params={"fy": "2025-26"},
        timeout=45,
    )
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    assert body.get("success") is True, body
    payload = body.get("data") or {}
    customers = payload.get("customers") or []
    assert isinstance(customers, list)
    # If there are any customers, spot-check that the enriched keys are
    # part of the response projection (may be empty strings).
    if customers:
        c0 = customers[0]
        for k in ("customer_name", "outstanding_amount"):
            assert k in c0, f"outstanding customer missing key {k}"
        # Enriched keys should be surfaced (empty string is fine on this
        # tenant if not synced yet — we only fail if the KEY is absent).
        enriched_keys = ("mobile_number", "whatsapp_number", "gst_number",
                         "pan_number", "closing_balance", "contact_person",
                         "address", "pin_code", "station")
        missing = [k for k in enriched_keys if k not in c0]
        # Tolerate <=3 missing (some may only exist when populated) —
        # assert at least the core few are present.
        core = {"mobile_number", "gst_number", "closing_balance"}
        missing_core = core - set(c0.keys())
        assert not missing_core, (
            f"/customers/outstanding missing core enriched keys {missing_core}. "
            f"All missing: {missing}. sample={list(c0.keys())[:20]}"
        )


# ─────────────────────── 6. Tenant isolation ───────────────────────
def test_tenant_isolation_foreign_token_rejected(sync_token):
    """A sync_token generated for ADMIN_TENANT must NOT authenticate a
    write claiming to be for another tenant."""
    foreign = str(uuid.uuid4())
    r = requests.post(
        f"{BASE_URL}/api/agent/sync",
        json={
            "data_type": "payment_vouchers",
            "data": [{"voucher_id": "SHOULD-NOT-LAND", "total_amount": 1}],
            "tenant_id": foreign,
            "company_id": ADMIN_COMPANY,
            "sync_token": sync_token,  # signed for ADMIN_TENANT, not foreign
        },
        timeout=15,
    )
    body = r.json()
    assert body.get("success") is False
    assert "invalid" in (body.get("error") or "").lower()
