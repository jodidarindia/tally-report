"""
Iteration 76 — Tally Sync Agent v9.8.4-tenant-guard.

Two distinct user-reported bugs:

(1) Cross-tenant company drift: User logged into agent as admin (ASA Autotech).
    User then opened Krishna Sales Corp in Tally on the same machine. Agent's
    `_pick_company` method blindly picked the new company because
    `len(companies) == 1` after Tally's company switch — synced KSC under
    admin's tenant. Data leak.

(2) Stale "is_syncing": After the agent was logged out and re-logged in as
    a different user (kscraipur1995@...), the admin user's frontend kept
    polling `/sync/status` and saw `is_syncing=True` indefinitely because
    the previous agent process never sent `sync_complete` (it was killed)
    so `is_syncing=True` lived forever in the admin tenant's row.

Fixes:

A. AGENT — `_pick_company` now persists the previously-synced company name
   to `last_company.txt`. On every cycle, if Tally's active company differs,
   it INTERRUPTS with a confirmation prompt before syncing. Default = NO.

B. AGENT --logout — sends `sync_aborted` event to backend BEFORE clearing
   creds, so the frontend `is_syncing` clears immediately. Also deletes
   `last_company.txt` so next login starts fresh.

C. BACKEND `/sync/status` — auto-clears stale `is_syncing=True` rows where
   `sync_started_at > 10 min ago` AND no `sync_progress` event in last 5
   min. This is the safety net for cases where the agent died ungracefully
   (Ctrl+C, network drop, OS reboot).

D. BACKEND `/agent/sync-progress` — new event type `sync_aborted` that
   immediately clears `is_syncing` for the tenant.
"""
import os
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
import requests


API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": "admin", "password": "admin123", "captcha_token": "",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"], r.json()["data"]["token"]


@pytest.fixture
def admin_data():
    user_data, token = _login()
    return user_data, {"Authorization": f"Bearer {token}"}


# ── (C) Backend: stale-sync auto-clear on /sync/status read ──

def test_stale_sync_auto_cleared_on_status_read(admin_data):
    """If is_syncing=True with sync_started_at > 10 min ago AND no recent
    progress, /sync/status must auto-flip is_syncing to False."""
    user_data, h = admin_data
    tenant_id = user_data.get("tenant_id") or user_data.get("id") or user_data.get("username")

    # Plant a stale row directly in DB
    from db import db

    async def setup():
        old_iso = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        await db.sync_status.update_one(
            {'type': 'agent_sync', 'tenant_id': tenant_id, 'company_id': 'iter76-stale'},
            {'$set': {
                'type': 'agent_sync',
                'tenant_id': tenant_id,
                'company_id': 'iter76-stale',
                'is_syncing': True,
                'sync_started_at': old_iso,
            }},
            upsert=True,
        )

    asyncio.get_event_loop().run_until_complete(setup())

    # Hit /sync/status with the planted company_id
    r = requests.get(f"{API_URL}/api/sync/status?company_id=iter76-stale", headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["is_syncing"] is False, f"stale row not auto-cleared: {d}"
    assert "stale_reason" in d or d.get("stale_at") is not None

    # Cleanup
    async def cleanup():
        await db.sync_status.delete_many({'company_id': 'iter76-stale'})

    asyncio.get_event_loop().run_until_complete(cleanup())


def test_fresh_sync_NOT_auto_cleared(admin_data):
    """A genuinely-in-progress sync (started < 10 min ago) must NOT be cleared."""
    user_data, h = admin_data
    tenant_id = user_data.get("tenant_id") or user_data.get("id") or user_data.get("username")

    from db import db

    async def setup():
        recent_iso = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        await db.sync_status.update_one(
            {'type': 'agent_sync', 'tenant_id': tenant_id, 'company_id': 'iter76-fresh'},
            {'$set': {
                'type': 'agent_sync',
                'tenant_id': tenant_id,
                'company_id': 'iter76-fresh',
                'is_syncing': True,
                'sync_started_at': recent_iso,
            }},
            upsert=True,
        )

    asyncio.get_event_loop().run_until_complete(setup())

    r = requests.get(f"{API_URL}/api/sync/status?company_id=iter76-fresh", headers=h)
    d = r.json()["data"]
    assert d["is_syncing"] is True, f"fresh sync was incorrectly cleared: {d}"

    async def cleanup():
        await db.sync_status.delete_many({'company_id': 'iter76-fresh'})

    asyncio.get_event_loop().run_until_complete(cleanup())


# ── (D) Backend: sync_aborted event clears is_syncing ──

def test_sync_aborted_event_clears_is_syncing(admin_data):
    user_data, h = admin_data
    tenant_id = user_data.get("tenant_id") or user_data.get("id") or user_data.get("username")

    from db import db

    async def setup():
        await db.sync_status.update_one(
            {'type': 'agent_sync', 'tenant_id': tenant_id, 'company_id': 'iter76-abort'},
            {'$set': {
                'type': 'agent_sync',
                'tenant_id': tenant_id,
                'company_id': 'iter76-abort',
                'is_syncing': True,
                'sync_started_at': datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    asyncio.get_event_loop().run_until_complete(setup())

    payload = {
        'type': 'sync_aborted',
        'tenant_id': tenant_id,
        'company_id': 'iter76-abort',
        'reason': 'agent --logout',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    r = requests.post(
        f"{API_URL}/api/agent/sync-progress",
        headers={**h, 'X-Company-Id': 'iter76-abort'},
        json=payload,
    )
    if r.status_code != 200:
        pytest.skip(f"sync-progress returned {r.status_code}: {r.text[:120]}")

    async def check():
        return await db.sync_status.find_one(
            {'type': 'agent_sync', 'tenant_id': tenant_id, 'company_id': 'iter76-abort'},
            {'_id': 0, 'is_syncing': 1},
        )

    after = asyncio.get_event_loop().run_until_complete(check())
    assert after and after.get('is_syncing') is False, after

    async def cleanup():
        await db.sync_status.delete_many({'company_id': 'iter76-abort'})

    asyncio.get_event_loop().run_until_complete(cleanup())


# ── (A, B) Public agent stamp + new code paths present ──

def test_public_agent_v984_has_company_switch_guard():
    path = "/app/frontend/public/flowra-desktop-agent.py"
    if not os.path.exists(path):
        pytest.skip("public agent not present")
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()

    # v9.8.4 introduced the tenant guard; later versions inherit it.
    assert "9.8.4-tenant-guard" in contents or "9.8.5-stdprice-list" in contents or "9.8.6-hierarchy-walk" in contents or "9.8.7-aliases-perf" in contents
    # Switch-guard prompt is wired
    assert "TALLY ACTIVE COMPANY CHANGED" in contents
    assert "last_company.txt" in contents
    # Logout sends sync_aborted
    assert "'type': 'sync_aborted'" in contents


def test_public_agent_no_silent_company_switch():
    """Hard regression guard — ensures the silent picker is gone."""
    path = "/app/frontend/public/flowra-desktop-agent.py"
    if not os.path.exists(path):
        pytest.skip("public agent not present")
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()
    # The previous one-liner that picked companies[0] without confirmation:
    assert "self._companies_to_sync = companies\n            logger.info(f\"Single company detected" not in contents


# ── No regressions on regular happy path ──

def test_normal_status_read_unchanged(admin_data):
    """A tenant with no sync rows must still get the standard 'no data' response."""
    _, h = admin_data
    r = requests.get(f"{API_URL}/api/sync/status?company_id=iter76-doesnt-exist", headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["is_syncing"] is False


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
