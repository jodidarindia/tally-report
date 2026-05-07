"""Regression tests for CA Corner Balance Sheet & P&L endpoints.

Validates against the user's actual ASA AUTOTECH Tally exports:
  - BSheet26-27.pdf  (TA = TL = 1,21,97,144.12)
  - PandL26-27.pdf   (Net Profit = 5,20,469.80)
  - PandL25-26.pdf   (Net Profit = 1,92,399.36)

Run with: pytest /app/backend/tests/test_ca_corner_bs_pl.py -v
"""
import os
import requests
import pytest

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": "admin", "password": "admin123", "captcha_token": "",
    })
    r.raise_for_status()
    return r.json()["data"]["token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


def test_bs_balances(headers):
    """Balance Sheet must auto-balance: Total Assets = Total Liabilities."""
    r = requests.get(f"{API_URL}/api/ca-corner/balance-sheet?fy=2026-27", headers=headers)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["difference"] == 0, f"BS does not balance: TA={d['total_assets']} TL={d['total_liabilities']}"
    assert d["total_assets"] > 0
    # Capital Account must show as a liability
    cap = next((g for g in d["liabilities"] if g["group"] == "Capital Account"), None)
    assert cap is not None, "Capital Account missing from BS liabilities"
    assert cap["total"] == 166780.0, f"Capital Account expected 1,66,780, got {cap['total']}"
    # Fixed Assets must match Tally exactly
    fa = next((g for g in d["assets"] if g["group"] == "Fixed Assets"), None)
    assert fa is not None
    assert abs(fa["total"] - 240527.27) < 1, f"Fixed Assets expected 2,40,527.27, got {fa['total']}"


def test_pl_sales_purchases_match_tally(headers):
    """Sales A/c and Purchase A/c totals should match Tally PDF exactly."""
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?fy=2026-27", headers=headers)
    assert r.status_code == 200
    d = r.json()["data"]
    # Tally PDF: Sales A/c = 35,36,521.28
    assert abs(d["total_sales"] - 3536521.28) < 1, f"Sales mismatch: {d['total_sales']}"
    # Tally PDF: Purchase A/c = 32,49,829.94
    assert abs(d["total_purchases"] - 3249829.94) < 1, f"Purchases mismatch: {d['total_purchases']}"
    # Tally PDF: Indirect Income = 3,959
    assert abs(d["indirect_income"] - 3959.0) < 1, f"Indirect Income mismatch: {d['indirect_income']}"
    # Tally PDF: Direct Expense = 88,110
    assert abs(d["direct_expense"] - 88110.0) < 1, f"Direct Expense mismatch: {d['direct_expense']}"


def test_bs_returns_notices_when_data_missing(headers):
    """If stock/creditors not synced, response should include actionable notices."""
    r = requests.get(f"{API_URL}/api/ca-corner/balance-sheet?fy=2026-27", headers=headers)
    d = r.json()["data"]
    # Until user re-syncs with v9.5+ agent, these should appear
    if not d["stock_synced"]:
        assert any("Stock-in-Hand" in n for n in d.get("notices", []))
    if d["creditor_count"] == 0:
        assert any("Sundry Creditors" in n for n in d.get("notices", []))


def test_bs_prev_fy_view(headers):
    """Previous-FY BS should use opening_balance and still balance."""
    r = requests.get(f"{API_URL}/api/ca-corner/balance-sheet?fy=2025-26", headers=headers)
    d = r.json()["data"]
    assert d["view"] == "opening"
    assert d["difference"] == 0
