"""End-to-end test for v9.8.30 window-scoped reconcile.

Inserts 3 sales vouchers spanning 3 dates into `sales_vouchers`, then hits
`/api/agent/reconcile` with a narrow window that ONLY covers the middle
voucher. Verifies:

  • the middle voucher is deleted (it's inside the window and not in manifest)
  • the OUTSIDE-WINDOW vouchers survive (this is the whole point of v9.8.30)

Runs against the local FastAPI server on port 8001. Skips gracefully when
Mongo / API is unreachable.
"""
import os
import sys
import uuid
import asyncio

import pytest
import requests
from dotenv import load_dotenv

# Load /app/backend/.env so MONGO_URL / DB_NAME reach this test process.
load_dotenv("/app/backend/.env")

BACKEND = "http://localhost:8001"
TENANT  = str(uuid.uuid4())
COMPANY = str(uuid.uuid4())


def _mint_sync_token() -> str:
    """Mint a valid sync_token via the backend helper."""
    sys.path.insert(0, "/app/backend")
    try:
        from services.auth_service import generate_sync_token  # type: ignore
        return generate_sync_token(TENANT)
    except Exception:
        return ""


def _backend_up() -> bool:
    """Backend may be reloading (uvicorn watches /app/backend). Retry a few
    times before giving up so a test-file save doesn't skip our tests."""
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


async def _seed_and_run():
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name   = os.environ.get("DB_NAME")
    if not (mongo_url and db_name):
        pytest.skip("MONGO_URL / DB_NAME not set")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Seed 3 vouchers
    docs = [
        {"tenant_id": TENANT, "company_id": COMPANY, "voucher_id": "V-outside-before",
         "voucher_date": "2026-06-15", "amount": 100},
        {"tenant_id": TENANT, "company_id": COMPANY, "voucher_id": "V-inside-window",
         "voucher_date": "2026-07-05", "amount": 200},
        {"tenant_id": TENANT, "company_id": COMPANY, "voucher_id": "V-outside-after",
         "voucher_date": "2026-08-20", "amount": 300},
    ]
    await db.sales_vouchers.insert_many(docs)
    return db


@pytest.mark.asyncio
async def test_window_scoped_reconcile_keeps_out_of_window_records():
    if not _backend_up():
        pytest.skip("backend not running")
    db = await _seed_and_run()
    try:
        token = _mint_sync_token()
        assert token, "could not mint sync_token"
        # Manifest contains ONLY V-inside-window's id?  No — the whole
        # point is the *quick sync* returns an EMPTY manifest for the
        # window (voucher was deleted from Tally) → backend must delete
        # the middle one and LEAVE the two outside-window vouchers alone.
        payload = {
            "data_type": "sales",
            "manifest_ids": [],
            "tenant_id": TENANT,
            "company_id": COMPANY,
            "financial_year": "2026-27",
            "sync_token": token,
            "agent_version": "9.8.30-window-scoped-reconcile",
            "window_start": "2026-07-01",
            "window_end":   "2026-07-31",
        }
        r = requests.post(f"{BACKEND}/api/agent/reconcile",
                           json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True, d

        # Only the INSIDE-window voucher should be gone
        left = await db.sales_vouchers.find(
            {"tenant_id": TENANT, "company_id": COMPANY}
        ).to_list(length=100)
        left_ids = sorted(v["voucher_id"] for v in left)
        assert left_ids == ["V-outside-after", "V-outside-before"], (
            f"window-scoped reconcile deleted rows OUTSIDE the window! "
            f"survivors: {left_ids}"
        )
    finally:
        await db.sales_vouchers.delete_many({"tenant_id": TENANT})


@pytest.mark.asyncio
async def test_unscoped_reconcile_still_deletes_everything():
    """Backward-compat: full-sync callers omit window_* and must delete
    every mismatch, exactly like v9.8.29 did."""
    if not _backend_up():
        pytest.skip("backend not running")
    db = await _seed_and_run()
    try:
        token = _mint_sync_token()
        payload = {
            "data_type": "sales",
            "manifest_ids": [],  # nothing survives
            "tenant_id": TENANT,
            "company_id": COMPANY,
            "financial_year": "2026-27",
            "sync_token": token,
            "agent_version": "9.8.30-window-scoped-reconcile",
        }
        r = requests.post(f"{BACKEND}/api/agent/reconcile",
                           json=payload, timeout=15)
        assert r.status_code == 200, r.text
        left = await db.sales_vouchers.find(
            {"tenant_id": TENANT, "company_id": COMPANY}
        ).to_list(length=100)
        assert left == [], f"unscoped reconcile should nuke all, got {left}"
    finally:
        await db.sales_vouchers.delete_many({"tenant_id": TENANT})
