"""Iteration 102 — tally/status must be tenant-scoped.

Tests the live /api/tally/status endpoint against the running backend
(no asyncio gymnastics — straight HTTP). The endpoint must NOT leak
agent_version from another tenant's sync_status row.
"""
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Talk to the backend through the in-cluster URL.
BASE = "http://127.0.0.1:8001"
T_A = f"itest102-tenantA-{uuid.uuid4().hex[:8]}"
T_B = f"itest102-tenantB-{uuid.uuid4().hex[:8]}"
COMPANY_A = "iter102-company-A"
COMPANY_B = "iter102-company-B"

# --- One-shot mongo seed using pymongo (synchronous, no asyncio) ------------
from pymongo import MongoClient  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "Flowra-Insights-Dev")
_client = MongoClient(MONGO_URL)
sync_status_col = _client[DB_NAME].sync_status
users_col = _client[DB_NAME].users


def _seed():
    sync_status_col.delete_many({"tenant_id": {"$in": [T_A, T_B]}})
    users_col.delete_many({"tenant_id": {"$in": [T_A, T_B]}})
    # Seed minimal admin user docs so get_current_user can resolve the JWT.
    users_col.insert_many([
        {"username": f"{T_A}@test.local", "tenant_id": T_A, "role": "admin",
         "active": True, "password_hash": "x", "subscription_start": "",
         "subscription_months": 999},
        {"username": f"{T_B}@test.local", "tenant_id": T_B, "role": "admin",
         "active": True, "password_hash": "x", "subscription_start": "",
         "subscription_months": 999},
    ])
    sync_status_col.insert_many([
        {
            "type": "agent_sync",
            "tenant_id": T_A,
            "company_id": COMPANY_A,
            "agent_version": "9.8.23-alter-id",
            "company_name": "Tenant A Shop",
            "last_sync": "2026-05-21T10:00:00+00:00",
        },
        {
            "type": "agent_sync",
            "tenant_id": T_B,
            "company_id": COMPANY_B,
            "agent_version": "9.8.7-aliases-perf",
            "company_name": "Tenant B Shop",
            "last_sync": "2026-05-11T14:00:00+00:00",
        },
    ])


def _cleanup():
    sync_status_col.delete_many({"tenant_id": {"$in": [T_A, T_B]}})
    users_col.delete_many({"tenant_id": {"$in": [T_A, T_B]}})


@pytest.fixture(autouse=True)
def around_each_test():
    _seed()
    yield
    _cleanup()


def _forge_jwt(tenant_id: str) -> str:
    """Issue a tenant-scoped JWT identical to the one /auth/login returns,
    using the same secret + algorithm the backend uses."""
    from services.auth_service import create_access_token
    return create_access_token(
        user_id=f"{tenant_id}@test.local",
        username=f"{tenant_id}@test.local",
        role="admin",
        tenant_id=tenant_id,
    )


def test_no_global_leak_unauthenticated():
    """Without a token we must NOT receive Tenant B's agent_version."""
    r = requests.get(f"{BASE}/api/tally/status", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data.get("is_connected") is False
    assert "agent_version" not in data


def test_tenant_A_sees_only_its_own_agent_version():
    token = _forge_jwt(T_A)
    r = requests.get(
        f"{BASE}/api/tally/status",
        headers={"Authorization": f"Bearer {token}", "X-Company-ID": COMPANY_A},
        timeout=5,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["is_connected"] is True
    assert data["agent_version"] == "9.8.23-alter-id"
    assert data["company_name"] == "Tenant A Shop"


def test_tenant_B_sees_only_its_own_agent_version():
    token = _forge_jwt(T_B)
    r = requests.get(
        f"{BASE}/api/tally/status",
        headers={"Authorization": f"Bearer {token}", "X-Company-ID": COMPANY_B},
        timeout=5,
    )
    data = r.json()["data"]
    assert data["agent_version"] == "9.8.7-aliases-perf"
    assert data["company_name"] == "Tenant B Shop"


def test_tenant_A_with_wrong_company_falls_back_to_latest_for_tenant():
    """Admin selects a company that doesn't have a sync row yet → endpoint
    falls back to the LATEST row under their tenant (never another tenant)."""
    token = _forge_jwt(T_A)
    r = requests.get(
        f"{BASE}/api/tally/status",
        headers={"Authorization": f"Bearer {token}", "X-Company-ID": "non-existent-company"},
        timeout=5,
    )
    data = r.json()["data"]
    assert data["is_connected"] is True
    assert data["agent_version"] == "9.8.23-alter-id"  # Tenant A's, not B's


def test_tenant_A_token_never_sees_tenant_B_data():
    """Even if Tenant A tries to spoof company_id=COMPANY_B, they cannot
    see Tenant B's row because the tenant_id filter is from the JWT."""
    token = _forge_jwt(T_A)
    r = requests.get(
        f"{BASE}/api/tally/status",
        headers={"Authorization": f"Bearer {token}", "X-Company-ID": COMPANY_B},
        timeout=5,
    )
    data = r.json()["data"]
    # Falls back to tenant A's latest — never returns tenant B's agent.
    assert data["agent_version"] != "9.8.7-aliases-perf"
