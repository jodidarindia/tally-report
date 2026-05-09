"""
Iteration 70 — Two fixes for ASA-Autotech-style "first-FY-synced" tenants:

A. P&L FY 25-26 should show **opening stock** reconstructed from item-level
   quantity replay (master Tally only persists current-FY snapshots).

B. Inventory Movement Analysis must NOT show data for FYs that were never
   synced (FY end < earliest voucher) — previously it leaked today's master
   quantities into 24-25 and earlier.
"""
import os
import requests
import pytest

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": "admin", "password": "admin123", "captcha_token": "",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login()}"}


# ── Fix A: P&L opening-stock reconstruction for prev FYs ──

def test_prev_fy_pl_opening_stock_reconstructed(admin_h):
    """FY 25-26 (the first synced FY for a typical tenant) must now show a
    non-zero opening_stock because we reconstruct it from item-level quantity
    replay. Previous behaviour was opening_stock=0 (the bug)."""
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?view=annual&fy=2025-26",
                     headers=admin_h)
    d = r.json()["data"]
    # Must not be the impossible-negative number we shipped before either
    assert d["total_sales"] >= 0
    # Stock fields shape
    for k in ("opening_stock", "closing_stock", "gross_profit"):
        assert k in d
    # If this tenant has any inventory + voucher activity, opening_stock
    # reconstruction should produce a value > 0 (matching the user's
    # complaint about ASA Autotech)
    # Otherwise, flag stays at 0 (acceptable for tenants with no inventory).
    if d.get("closing_stock", 0) > 0 and d.get("total_sales", 0) > 0:
        assert d["opening_stock"] > 0, (
            f"Opening stock not reconstructed for prev FY despite sales+stock present: "
            f"{d}"
        )


def test_prev_fy_pl_notice_explains_reconstruction(admin_h):
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?view=annual&fy=2025-26",
                     headers=admin_h)
    notices = " | ".join(r.json()["data"].get("notices", [])).lower()
    # Either reconstructed OR (rare) tenant-with-no-stock fallback
    assert ("reconstructed" in notices or "approximated" in notices or
            "previous fy" in notices)


def test_unsynced_fy_pl_returns_zero_stock_with_notice(admin_h):
    """An FY entirely before the earliest voucher must have stock=0 + notice."""
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?view=annual&fy=2024-25",
                     headers=admin_h)
    d = r.json()["data"]
    notices = " | ".join(d.get("notices", []))
    # Stock should be zero (no leak) AND there should be a "not synced" notice
    assert d["opening_stock"] == 0
    assert d["closing_stock"] == 0
    assert "not synced" in notices.lower() or "previous fy" in notices.lower()


# ── Fix B: Movement Analysis gates unsynced FYs ──

def test_unsynced_fy_movement_analysis_is_empty(admin_h):
    """FY 24-25 (entirely before earliest synced voucher) must return empty
    items + summary + clear `not synced` notice. Previously it leaked today's
    master quantities into the response."""
    r = requests.get(f"{API_URL}/api/inventory/movement-analysis?fy=2024-25",
                     headers=admin_h)
    d = r.json()
    # New explicit fields
    assert d.get("fy_synced") is False, d
    assert d.get("earliest_voucher_date"), d
    # Empty body
    assert d["items"] == [] or len(d["items"]) == 0
    s = d.get("summary", {})
    assert s.get("total_opening_stock", 0) == 0
    assert s.get("total_closing_stock", 0) == 0
    assert s.get("total_revenue", 0) == 0
    # Notice
    notices = " ".join(d.get("notices", []))
    assert "not synced" in notices.lower()
    assert "2024-25" in notices


def test_synced_fy_movement_analysis_still_works(admin_h):
    """Sanity: an FY with synced data must NOT trigger the empty response."""
    r = requests.get(f"{API_URL}/api/inventory/movement-analysis?fy=2025-26",
                     headers=admin_h)
    d = r.json()
    # Either it has items, or summary is reported normally (no `fy_synced=False`).
    fy_synced = d.get("fy_synced", True)
    assert fy_synced is not False, "FY 2025-26 was incorrectly marked unsynced"


def test_synced_fy_movement_analysis_returns_summary_keys(admin_h):
    """Standard response shape preserved for synced FYs."""
    r = requests.get(f"{API_URL}/api/inventory/movement-analysis?fy=2025-26",
                     headers=admin_h)
    d = r.json()
    s = d.get("summary", {})
    if d.get("fy_synced") is False or not s:
        pytest.skip("tenant has no inventory data synced for FY 25-26")
    for k in ("total_items", "total_opening_stock", "total_closing_stock",
              "total_sales_qty"):
        assert k in s, f"missing summary key {k}"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
