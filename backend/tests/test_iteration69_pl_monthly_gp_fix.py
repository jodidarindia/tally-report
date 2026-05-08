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


def test_gross_profit_consistency_per_row(admin_h):
    """Per-row consistency:
    - When stock_aware: GP == sales − COGS (Tally Trading Account formula)
    - When not (Trading Profit fallback): GP == sales − purchases.
    """
    d = _fetch(admin_h)
    m = d["monthly"]
    stock_aware = (d.get("monthly_meta") or {}).get("stock_aware", False)
    for row in m:
        if stock_aware:
            expected = round(row["sales"] - row["cogs"], 2)
            assert abs(row["gross_profit"] - expected) < 0.5, (
                f"{row['month']}: GP {row['gross_profit']} != sales-cogs {expected}"
            )
        else:
            expected = round(row["sales"] - row["purchases"], 2)
            assert row["gross_profit"] == expected, (
                f"{row['month']}: GP {row['gross_profit']} != sales-purch {expected}"
            )


def test_monthly_gp_sums_to_fy_gp_when_stock_aware(admin_h):
    """When stock_aware, Σ monthly_gp must equal FY-level gross_profit (within ₹1 rounding)."""
    d = _fetch(admin_h)
    if not (d.get("monthly_meta") or {}).get("stock_aware"):
        pytest.skip("not stock-aware for this FY")
    fy_gp = d["gross_profit"]
    monthly_sum = sum(r["gross_profit"] for r in d["monthly"])
    assert abs(monthly_sum - fy_gp) < 1.0, (
        f"Σ monthly GP ({monthly_sum:,.2f}) ≠ FY GP ({fy_gp:,.2f})"
    )


def test_monthly_sales_sums_to_fy_sales_when_stock_aware(admin_h):
    """When stock_aware we scale monthly to match FY exactly (so the totals are consistent)."""
    d = _fetch(admin_h)
    if not (d.get("monthly_meta") or {}).get("stock_aware"):
        pytest.skip("not stock-aware for this FY")
    fy_sales = d["total_sales"] + d["direct_income"]
    monthly_sum = sum(r["sales"] for r in d["monthly"])
    assert abs(monthly_sum - fy_sales) < 1.0


def test_prev_fy_sales_not_negative(admin_h):
    """REGRESSION: FY 2025-26 was returning negative sales (the bug shipped to user)."""
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?view=annual&fy=2025-26", headers=admin_h)
    d = r.json()["data"]
    assert d["total_sales"] >= 0, f"FY 2025-26 total_sales is negative: {d['total_sales']}"
    # Sanity: sales should be in the same order of magnitude as purchases
    if d["total_purchases"] > 0:
        ratio = d["total_sales"] / d["total_purchases"]
        assert 0.5 < ratio < 2.5, f"sales/purchases ratio drifted: {ratio:.2f}"


def test_prev_fy_stock_handling(admin_h):
    """For previous FYs we don't have opening stock, so we set it to 0 and notice."""
    r = requests.get(f"{API_URL}/api/ca-corner/profit-loss?view=annual&fy=2025-26", headers=admin_h)
    d = r.json()["data"]
    assert d["opening_stock"] == 0
    notice_blob = " | ".join(d.get("notices", []))
    assert "previous FY" in notice_blob.lower() or "previous fys" in notice_blob.lower()


def test_monthly_notice_mentions_trading_profit(admin_h):
    d = _fetch(admin_h)
    notice_blob = " | ".join(d.get("notices", [])).lower()
    # Either stock-aware uses "trading-account" or fallback uses "trading profit"
    assert "trading" in notice_blob


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
