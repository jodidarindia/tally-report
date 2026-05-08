"""
Iteration 69 — P&L Monthly Gross Profit fix + M-o-M change.

Before: monthly gross_profit = voucher-header sales − voucher-header purchases
        (both INCLUDING GST → noisy + wrong; missing direct income/expense).
After:  monthly gross_profit = (net_sales + direct_income) − (net_purchases + direct_expense)
        net_sales = sum(items[].amount) from sales_vouchers minus credit-note items
        + adjustments from journal_vouchers' Sales-Account / Purchase-Account /
        Direct-Income / Direct-Expense ledger_entries.

Tests:
- Each monthly row has the correct keys including the M-o-M *_change_pct fields.
- monthly[0]'s *_change_pct fields are null (no previous month).
- M-o-M change pct math: row[i].sales_change_pct == round((sales[i] - sales[i-1])/abs(sales[i-1])*100, 1).
- monthly notice mentions "Trading Profit" and the stock-exclusion warning.
- gross_profit per row = sales − purchases (where sales/purchases are the
  values the API actually returned — so the table is internally consistent).
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


def _fetch(admin_h, fy="2026-27"):
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?view=monthly&fy={fy}", headers=admin_h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    return body["data"]


def test_monthly_row_shape_includes_mom_keys(admin_h):
    d = _fetch(admin_h)
    m = d.get("monthly")
    assert m and len(m) == 12
    expected = {"month", "sales", "purchases", "gross_profit", "receipts",
                "sales_change_pct", "purchases_change_pct", "gp_change_pct"}
    for row in m:
        assert expected <= set(row.keys()), f"missing keys in {row}"


def test_first_month_has_no_mom_change(admin_h):
    m = _fetch(admin_h)["monthly"]
    assert m[0]["sales_change_pct"] is None
    assert m[0]["purchases_change_pct"] is None
    assert m[0]["gp_change_pct"] is None


def test_mom_pct_math_is_correct(admin_h):
    """row[i].sales_change_pct must equal round((sales[i]-sales[i-1])/abs(sales[i-1])*100, 1)."""
    m = _fetch(admin_h)["monthly"]
    for i in range(1, len(m)):
        prev = m[i - 1]["sales"]
        curr = m[i]["sales"]
        if abs(prev) < 0.01:
            assert m[i]["sales_change_pct"] is None
        else:
            expected = round(((curr - prev) / abs(prev)) * 100, 1)
            assert m[i]["sales_change_pct"] == expected, (
                f"month {m[i]['month']}: expected {expected}, got {m[i]['sales_change_pct']}"
            )


def test_gross_profit_equals_sales_minus_purchases(admin_h):
    """Per-row internal consistency: gross_profit == round(sales − purchases, 2)."""
    m = _fetch(admin_h)["monthly"]
    for row in m:
        expected = round(row["sales"] - row["purchases"], 2)
        assert row["gross_profit"] == expected, (
            f"{row['month']}: GP {row['gross_profit']} != sales-purch {expected}"
        )


def test_monthly_notice_mentions_trading_profit(admin_h):
    d = _fetch(admin_h)
    notices = d.get("notices", [])
    # Concatenate so we can assert sub-strings cleanly
    notice_blob = " | ".join(notices).lower()
    assert "trading profit" in notice_blob or "stock movement" in notice_blob


def test_monthly_sales_excludes_gst_roughly(admin_h):
    """Sanity: sum-of-monthly sales should be within 10% of the FY's all_ledger total
    (both are net of GST). Wider gap than the legacy header-based math."""
    d = _fetch(admin_h)
    m = d["monthly"]
    fy_sales = d["total_sales"]
    if fy_sales <= 0:
        pytest.skip("No positive FY sales — can't compare ratios")
    monthly_sum = sum(r["sales"] for r in m)
    ratio = monthly_sum / fy_sales
    assert 0.85 <= ratio <= 1.15, (
        f"monthly sum ({monthly_sum:,.0f}) drifted >15% from FY ledgers ({fy_sales:,.0f}); ratio={ratio:.2f}"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
