"""
Iteration 81 — Insider Result Batch A bug fixes.

User report (4 issues, fixed in this batch):
  1. SPIP "out of stock" rows showed zero stock even when the item had
     inventory — caused by case/whitespace mismatch between sales-voucher
     `item_name` and inventory_items `item_name`. Now both sides keyed on
     `name.strip().lower()` so cross-lookup works.
  2. SPIP categories empty in dropdown (overstocked / balanced / dead_stock
     showed nothing) — backend was returning only `analysis[:200]` (top
     200 by priority). User couldn't see lower-priority items. Now returns
     ALL items; frontend pages 50 at a time.
  3. Sales forecast tab missing prev-FY comparison — backend already
     returned `month_comparison` (Apr-25 ₹65.5L vs Apr-26 ₹89.9L etc.) but
     frontend never rendered it. Added a "Month-over-Month FY Comparison"
     bar chart + a YoY-delta table.
  4. Customer lifecycle limited to 100 rows — frontend hard-coded
     `.slice(0, 100)`. Added a real `Pager` component (50/page, First/Prev/
     Next/Last) and reset-on-filter-change logic so the user can reach
     all 1,800+ KSC customers.
"""
import os
from pathlib import Path
import pytest
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

INSIGHTS = Path("/app/backend/routes/insights.py")
INSIDER_PAGE = Path("/app/frontend/src/pages/InsiderResult.js")


def _login():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": "admin", "password": "admin123", "captcha_token": "",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


@pytest.fixture(scope="module")
def token():
    return _login()


# ─── Backend: Bug #2 — SPIP returns all items ────────────────────────────
def test_spip_returns_all_items_not_truncated(token):
    """Bug #2: backend used to slice [:200], hiding overstocked/balanced
    rows from the dropdown filter. Must now return every item."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/insights/spip-analysis", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    summary = data.get("summary") or {}
    items = data.get("items") or []
    # Items returned must equal total_items in the summary
    total = sum(summary.values())
    assert len(items) == data.get("total_items", 0)
    assert len(items) == total, f"items={len(items)} but summary sums to {total}"


def test_spip_source_no_longer_slices():
    """The dangerous `analysis[:200]` slice is gone."""
    code = INSIGHTS.read_text(encoding="utf-8")
    assert '"items": analysis[:200]' not in code
    assert '"items": analysis,' in code


# ─── Backend: Bug #1 — Case/whitespace-normalised item-name matching ─────
def test_spip_name_matching_case_insensitive():
    """Bug #1: keys built on `name.strip().lower()` so 'TVS Item ' (sales)
    matches 'tvs item' (inventory). Without this, items showed
    out_of_stock with stock_qty=0 even though stock existed."""
    code = INSIGHTS.read_text(encoding="utf-8")
    # The new item_sales loop uses .strip().lower() before keying
    assert "key = name.strip().lower()" in code
    # And inventory is keyed the same way
    assert 'key = name.strip().lower()\n                inv_map[key] = {' in code
    # display_name fallback present so UI shows the original casing
    assert '"display_name"' in code


# ─── Frontend: Bug #4 — Customer lifecycle pagination ────────────────────
def test_lifecycle_pagination_present():
    """Old code: filtered.slice(0, 100). New: filtered.slice((page-1)*50, page*50)."""
    code = INSIDER_PAGE.read_text(encoding="utf-8")
    # Old slice gone in both lifecycle and SPIP tables
    assert "filtered.slice(0, 100)" not in code
    # New pager component exists and is wired up
    assert "const Pager = " in code
    assert "lifecyclePage" in code
    assert "spipPage" in code
    assert "PAGE_SIZE = 50" in code
    # Pager is rendered for both tables
    assert 'testIdPrefix="lifecycle-pager"' in code
    assert 'testIdPrefix="spip-pager"' in code


def test_lifecycle_page_resets_on_filter_change():
    """When user switches filter (all → active) the table should jump to
    page 1 — otherwise they'd be stranded on a non-existent page."""
    code = INSIDER_PAGE.read_text(encoding="utf-8")
    assert "setLifecyclePage(1); }, [lifecycleFilter, search, activeTab" in code
    assert "setSpipPage(1); }, [spipFilter, search, activeTab" in code


# ─── Frontend: Bug #3 — Cross-FY forecast comparison ─────────────────────
def test_month_comparison_chart_rendered():
    """The Forecast tab now renders the month_comparison data the backend
    has been returning all along."""
    code = INSIDER_PAGE.read_text(encoding="utf-8")
    assert 'data-testid="month-comparison-chart"' in code
    assert 'data-testid="month-comparison-table"' in code
    # Pivots backend [{month_num, month_name, data: [{fy, revenue}]}]
    assert "monthComparison.forEach(row => (row.data || [])" in code
    # Renders %-delta vs previous FY in the table
    assert "_delta" in code
    assert "Month-over-Month FY Comparison" in code


def test_forecast_endpoint_returns_month_comparison(token):
    """Sanity: backend month_comparison shape unchanged — array of
    {month_num, month_name, data: [{fy, revenue, count}]}. Frontend pivots
    to chart-friendly shape."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/insights/sales-forecast", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    mc = data.get("month_comparison") or []
    assert isinstance(mc, list)
    if mc:  # tenant has data
        first = mc[0]
        assert "month_num" in first
        assert "month_name" in first
        assert "data" in first
        assert isinstance(first["data"], list)
        for d in first["data"]:
            assert "fy" in d
            assert "revenue" in d
            assert "count" in d


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
