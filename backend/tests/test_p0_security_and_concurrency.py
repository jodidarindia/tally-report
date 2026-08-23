"""
Regression tests for P0 fixes:
  1. Unauth cross-tenant leak in /api/insights/* (4 endpoints)
  2. Event-loop blocking during /api/analytics/forecast/overview compute
"""
import os
import time
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

INSIGHT_PATHS = [
    "/api/insights/customer-lifecycle",
    "/api/insights/sales-forecast",
    "/api/insights/spip-analysis",
    "/api/insights/concentration-risk",
]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123", "captcha_token": ""},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("token") or body.get("access_token") or (body.get("data") or {}).get("token") or (body.get("data") or {}).get("access_token")
    assert tok, f"No token in login response: {body}"
    return tok


# ---------- SECURITY: unauth must be rejected on insights endpoints ----------
@pytest.mark.parametrize("path", INSIGHT_PATHS)
def test_insights_unauth_rejected(path):
    r = requests.get(f"{BASE_URL}{path}", timeout=30)
    assert r.status_code == 200, f"expected 200 wrapped error, got {r.status_code}"
    body = r.json()
    assert body.get("success") is False, f"expected success=false, got {body}"
    assert body.get("error") == "Authentication required.", f"got error={body.get('error')}"
    # Ensure no leaked data payload
    data = body.get("data")
    assert data in (None, {}, []), f"data should be empty on unauth, got: {str(data)[:200]}"


# ---------- REGRESSION: authenticated insights still work ----------
@pytest.mark.parametrize("path", INSIGHT_PATHS)
def test_insights_authenticated_ok(admin_token, path):
    r = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=60,
    )
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("success") is True, f"{path} success!=true: {body.get('error')}"
    assert "data" in body


# ---------- SECURITY: forecast overview unauth must be 401 ----------
def test_forecast_overview_unauth_401():
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/overview", timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


# ---------- REGRESSION: forecast overview authenticated ----------
def test_forecast_overview_authenticated(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/analytics/forecast/overview?fresh=1",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=120,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("success") is True, f"error: {body.get('error')}"
    data = body.get("data") or {}
    assert "kpi" in data, f"missing kpi, keys={list(data.keys())}"
    assert "buy_list" in data, f"missing buy_list, keys={list(data.keys())}"


# ---------- REGRESSION: forecast season ----------
def test_forecast_season_authenticated(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/analytics/forecast/season?top=5",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=120,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("success") is True
    data = body.get("data") or {}
    for k in ("rows", "past_start", "festival_calendar"):
        assert k in data, f"missing {k}, keys={list(data.keys())}"
    # past_start should be an ISO date string
    ps = data["past_start"]
    assert isinstance(ps, str) and len(ps) >= 10, f"past_start not ISO string: {ps}"


# ---------- CONCURRENCY: event loop must not stall during compute ----------
def test_event_loop_not_blocked_by_forecast(admin_token):
    """
    Fire forecast overview (fresh=1, CPU-heavy) concurrently with 5 health calls.
    All health calls must return 200 quickly, proving the event loop isn't blocked.
    """
    import aiohttp

    async def run():
        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            headers = {"Authorization": f"Bearer {admin_token}"}

            async def health_call(i):
                t0 = time.time()
                async with sess.get(f"{BASE_URL}/api/health") as resp:
                    await resp.read()
                    return i, resp.status, time.time() - t0

            async def forecast_call():
                t0 = time.time()
                async with sess.get(
                    f"{BASE_URL}/api/analytics/forecast/overview?fresh=1",
                    headers=headers,
                ) as resp:
                    await resp.read()
                    return resp.status, time.time() - t0

            # Start forecast first, then immediately fire 5 health calls
            forecast_task = asyncio.create_task(forecast_call())
            # brief yield so forecast reaches server first
            await asyncio.sleep(0.05)
            health_results = await asyncio.gather(*[health_call(i) for i in range(5)])
            fc_status, fc_elapsed = await forecast_task
            return health_results, fc_status, fc_elapsed

    health_results, fc_status, fc_elapsed = asyncio.run(run())
    print(f"Forecast status={fc_status} elapsed={fc_elapsed:.2f}s")
    for i, status, elapsed in health_results:
        print(f"Health[{i}] status={status} elapsed={elapsed:.3f}s")

    # All health calls must be 200
    for i, status, elapsed in health_results:
        assert status == 200, f"health[{i}] returned {status}"
    # All health calls should complete within a reasonable window (event loop not blocked).
    # If run_in_executor works, health should return sub-second even mid-compute.
    max_elapsed = max(e for _, _, e in health_results)
    assert max_elapsed < 10.0, f"health call took {max_elapsed:.2f}s — event loop likely blocked"
    assert fc_status == 200, f"forecast returned {fc_status}"
