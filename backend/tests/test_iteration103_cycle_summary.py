"""Iteration 103 — POST /api/agent/cycle-summary stores cycle summaries,
and GET /api/sync/history surfaces had_errors + failed_phases per cycle.

This is what powers the "SYNC INCOMPLETE" badge on the web Sync History page.
"""
import os
import sys
import uuid
import time
import datetime as dt

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "http://127.0.0.1:8001"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "Flowra-Insights-Dev")
_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]

T = f"itest103-tenant-{uuid.uuid4().hex[:8]}"
COMPANY = f"itest103-co-{uuid.uuid4().hex[:6]}"


def _sync_token(tenant_id: str) -> str:
    from services.auth_service import generate_sync_token
    return generate_sync_token(tenant_id)


def _jwt(tenant_id: str) -> str:
    from services.auth_service import create_access_token
    return create_access_token(
        user_id=f"{tenant_id}@test.local",
        username=f"{tenant_id}@test.local",
        role="admin",
        tenant_id=tenant_id,
    )


@pytest.fixture(autouse=True)
def around_each():
    _db.sync_status.delete_many({"tenant_id": T})
    _db.sync_cycle_summaries.delete_many({"tenant_id": T})
    _db.sync_history.delete_many({"tenant_id": T})
    _db.users.delete_many({"tenant_id": T})
    _db.users.insert_one({
        "username": f"{T}@test.local", "tenant_id": T, "role": "admin",
        "active": True, "password_hash": "x", "subscription_start": "",
        "subscription_months": 999,
    })
    yield
    _db.sync_status.delete_many({"tenant_id": T})
    _db.sync_cycle_summaries.delete_many({"tenant_id": T})
    _db.sync_history.delete_many({"tenant_id": T})
    _db.users.delete_many({"tenant_id": T})


def test_cycle_summary_endpoint_persists_payload():
    token = _sync_token(T)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "tenant_id": T,
        "sync_token": token,
        "company_id": COMPANY,
        "company_name": "Krishna Sales Corp",
        "financial_year": "2025-26",
        "sync_mode": "full",
        "agent_version": "9.8.24-alter-id",
        "started_at": now,
        "ended_at": now,
        "had_errors": True,
        "failed_phases": [
            {"phase": "sales", "reason": "HTTPSConnectionPool read timeout", "count": 1},
            {"phase": "receipts", "reason": "Read timed out", "count": 2},
        ],
        "totals": {"sales": 0, "receipts": 0, "inventory": 11777},
    }
    r = requests.post(f"{BASE}/api/agent/cycle-summary", json=payload, timeout=15)
    assert r.status_code == 200
    assert r.json()["success"] is True
    rec = _db.sync_cycle_summaries.find_one({"tenant_id": T, "company_id": COMPANY})
    assert rec is not None
    assert rec["had_errors"] is True
    assert len(rec["failed_phases"]) == 2
    assert rec["agent_version"] == "9.8.24-alter-id"


def test_cycle_summary_rejects_bad_sync_token():
    payload = {
        "tenant_id": T, "sync_token": "WRONG", "company_id": COMPANY,
        "had_errors": False, "failed_phases": [], "totals": {},
    }
    r = requests.post(f"{BASE}/api/agent/cycle-summary", json=payload, timeout=5)
    body = r.json()
    assert body["success"] is False
    assert "sync_token" in (body.get("error") or "").lower()


def test_cycle_summary_requires_tenant():
    payload = {"sync_token": "x", "had_errors": False}
    body = requests.post(f"{BASE}/api/agent/cycle-summary", json=payload, timeout=5).json()
    assert body["success"] is False


def test_sync_history_attaches_had_errors_and_failed_phases():
    # 1) Seed one sync_history row that the cycle-grouping logic will pick up.
    base_ts = dt.datetime.now(dt.timezone.utc)
    history_ts = base_ts.isoformat()
    _db.sync_history.insert_one({
        "tenant_id": T,
        "company_id": COMPANY,
        "company_name": "Krishna Sales Corp",
        "financial_year": "2025-26",
        "sync_mode": "full",
        "agent_version": "9.8.24-alter-id",
        "data_type": "inventory",
        "count": 11777,
        "timestamp": history_ts,
    })
    # 2) Post a matching cycle-summary (window includes history_ts).
    started = (base_ts - dt.timedelta(seconds=30)).isoformat()
    ended = (base_ts + dt.timedelta(seconds=30)).isoformat()
    token = _sync_token(T)
    requests.post(f"{BASE}/api/agent/cycle-summary", json={
        "tenant_id": T, "sync_token": token, "company_id": COMPANY,
        "company_name": "Krishna Sales Corp", "financial_year": "2025-26",
        "sync_mode": "full", "agent_version": "9.8.24-alter-id",
        "started_at": started, "ended_at": ended,
        "had_errors": True,
        "failed_phases": [{"phase": "sales", "reason": "Read timed out", "count": 1}],
        "totals": {"inventory": 11777},
    }, timeout=5)
    # 3) Hit /api/sync/history with a tenant JWT.
    jwt = _jwt(T)
    r = requests.get(
        f"{BASE}/api/sync/history?company_id={COMPANY}",
        headers={"Authorization": f"Bearer {jwt}", "X-Company-ID": COMPANY},
        timeout=5,
    )
    assert r.status_code == 200
    cycles = r.json()["data"]["cycles"]
    assert len(cycles) >= 1
    cyc = cycles[0]
    assert cyc["had_errors"] is True
    assert any(p["phase"] == "sales" for p in cyc["failed_phases"])
