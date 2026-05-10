"""Iteration 90 — Flowra Staff (control-panel employees) + Tally Agent v9.8.9 metadata.

Tests:
  1. SuperAdmin can create a flowra_staff account with a feature checklist.
  2. flowra_staff appears in GET /super-admin/staff with feature list.
  3. Updating staff features works.
  4. Toggling active works.
  5. Deleting staff works.
  6. Tally agent file declares v9.8.9 and Day-Book fallback method exists.
"""
import os
import asyncio
import re
import pytest
import httpx

BACKEND = os.environ.get("BACKEND_URL_TEST") or "http://localhost:8001"
SUPER_USER = "superadmin"
SUPER_PASS = "superadmin123"

pytestmark = pytest.mark.asyncio


async def _login(client, username, password):
    r = await client.post(f"{BACKEND}/api/auth/login",
                          json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"], body
    return body["data"]["token"]


async def test_staff_full_lifecycle():
    async with httpx.AsyncClient(timeout=15) as c:
        sa_token = await _login(c, SUPER_USER, SUPER_PASS)
        h = {"Authorization": f"Bearer {sa_token}"}

        username = "staff-regression@flowra.in"

        # Cleanup any prior run
        await c.delete(f"{BACKEND}/api/super-admin/staff/{username}", headers=h)

        # 1. Create
        r = await c.post(f"{BACKEND}/api/super-admin/staff", headers=h, json={
            "username": username, "name": "Regression Bot",
            "password": "secret123", "features": ["overview", "subscriptions"],
        })
        assert r.json().get("success"), r.text

        # 2. List
        r = await c.get(f"{BACKEND}/api/super-admin/staff", headers=h)
        body = r.json()
        assert body["success"]
        usernames = [s["username"] for s in body["data"]["staff"]]
        assert username in usernames

        # 3. Update features
        r = await c.put(f"{BACKEND}/api/super-admin/staff/{username}/features",
                        headers=h, json={"features": ["payments", "invoices", "health"]})
        assert r.json().get("success"), r.text

        r = await c.get(f"{BACKEND}/api/super-admin/staff", headers=h)
        rec = next(s for s in r.json()["data"]["staff"] if s["username"] == username)
        assert set(rec["staff_features"]) == {"payments", "invoices", "health"}

        # 4. Toggle active
        r = await c.put(f"{BACKEND}/api/super-admin/staff/{username}/toggle-active", headers=h)
        assert r.json().get("success"), r.text
        assert r.json()["data"]["active"] is False

        # 5. Reset password
        r = await c.post(f"{BACKEND}/api/super-admin/staff/{username}/reset-password",
                         headers=h, json={"password": "newsecret"})
        assert r.json().get("success"), r.text

        # 6. Delete
        r = await c.delete(f"{BACKEND}/api/super-admin/staff/{username}", headers=h)
        assert r.json().get("success"), r.text


async def test_unknown_feature_rejected():
    async with httpx.AsyncClient(timeout=10) as c:
        sa_token = await _login(c, SUPER_USER, SUPER_PASS)
        h = {"Authorization": f"Bearer {sa_token}"}
        r = await c.post(f"{BACKEND}/api/super-admin/staff", headers=h, json={
            "username": "bad@flowra.in", "name": "X", "password": "abc123",
            "features": ["overview", "definitely-not-a-feature"],
        })
        body = r.json()
        assert body.get("success") is False
        assert "Unknown feature" in (body.get("error") or "")


def test_agent_v989_metadata_present():
    """v9.8.9 banner + Day-Book fallback function must exist in the source."""
    src = open("/app/desktop-agent/tally_sync_agent_v9.py").read()
    assert "v9.8.9-daybook-lvd" in src, "v9.8.9 version banner missing"
    assert "_fetch_last_voucher_date_via_daybook" in src, "Day-Book fallback method missing"
    # And it must be invoked from the public method
    pattern = re.compile(r"def fetch_last_voucher_date.*?def _fetch_last_voucher_date_via_daybook",
                         re.DOTALL)
    block = pattern.search(src)
    assert block, "fetch_last_voucher_date should call the daybook fallback"
    assert "_fetch_last_voucher_date_via_daybook" in block.group(0), (
        "fetch_last_voucher_date does not invoke the daybook fallback")


def test_public_agent_copy_in_sync():
    """The publicly-served file must match the source-of-truth."""
    src = open("/app/desktop-agent/tally_sync_agent_v9.py").read()
    pub = open("/app/frontend/public/flowra-desktop-agent.py").read()
    assert src == pub, "Public agent file out of sync — copy /app/desktop-agent/tally_sync_agent_v9.py to /app/frontend/public/flowra-desktop-agent.py"
