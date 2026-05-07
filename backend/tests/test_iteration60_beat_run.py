"""Regression tests for Beat Run Today feature.

Validates:
  - GET /api/salesman-orders/beat-run/today auto-builds from beat plan
  - POST /api/salesman-orders/beat-run/check-in toggles visited
  - POST /api/salesman-orders/beat-run/add-unplanned adds NEW-tagged visit
  - Past dates are locked=True (no edits allowed via UI; server uses today)
  - Admin sees history for any salesman; salesman sees only own
"""
import os
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


def _login(username, password):
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": username, "password": password, "captcha_token": "",
    })
    r.raise_for_status()
    return r.json()["data"]["token"]


def test_beat_run_today_auto_builds_from_plan():
    token = _login("ravi@test.com", "ravi1234")
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/salesman-orders/beat-run/today", headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["salesman"]
    assert d["run_date"]
    assert d["day_of_week"] in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
    assert "planned" in d and "unplanned" in d
    assert d["locked"] is False  # today is never locked


def test_check_in_and_unplanned_persist():
    token = _login("ravi@test.com", "ravi1234")
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Check in
    r1 = requests.post(f"{API_URL}/api/salesman-orders/beat-run/check-in", headers=h,
        json={"customer_name": "Krishna Sales Corporation RAIPUR", "visited": True, "notes": "test note"})
    assert r1.status_code == 200 and r1.json()["success"]
    # Add unplanned
    r2 = requests.post(f"{API_URL}/api/salesman-orders/beat-run/add-unplanned", headers=h,
        json={"customer_name": "PYTEST_New_Customer", "details": "regression test"})
    assert r2.status_code == 200 and r2.json()["success"]
    visit = r2.json()["data"]["visit"]
    assert visit["is_new"] is True
    # Verify both persisted
    r3 = requests.get(f"{API_URL}/api/salesman-orders/beat-run/today", headers=h)
    d = r3.json()["data"]
    assert any(p["customer_name"] == "Krishna Sales Corporation RAIPUR" and p["visited_at"] for p in d["planned"])
    assert any(u["customer_name"] == "PYTEST_New_Customer" and u["is_new"] for u in d["unplanned"])


def test_past_date_is_locked():
    token = _login("ravi@test.com", "ravi1234")
    h = {"Authorization": f"Bearer {token}"}
    # Yesterday-ish (use the seeded 2026-05-06 record from setup)
    r = requests.get(f"{API_URL}/api/salesman-orders/beat-run/today?run_date=2025-01-01", headers=h)
    d = r.json()["data"]
    assert d["locked"] is True


def test_admin_sees_any_salesman_history():
    a = _login("admin", "admin123")
    h = {"Authorization": f"Bearer {a}"}
    r = requests.get(f"{API_URL}/api/salesman-orders/beat-run/history?salesman=Ravi%20Kumar", headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["count"] >= 1
    assert all(run["salesman"] == "Ravi Kumar" for run in d["runs"])


def test_salesman_history_scoped_to_own():
    token = _login("ravi@test.com", "ravi1234")
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/salesman-orders/beat-run/history", headers=h)
    d = r.json()["data"]
    # Salesman can only see their own — even without filter param
    assert all(run["salesman"] == "Ravi Kumar" for run in d["runs"])
