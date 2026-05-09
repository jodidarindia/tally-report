"""
Iteration 82 — Batch B + remaining issues from user report.

Items shipped:
  1. SPIP zero-stock false positive fix — `inventory_items.find(...).to_list(5000)`
     was capping at 5,000 items; KSC has 7,510. Items past index 5,000 never
     entered `inv_map` so cross-lookup against sales returned stock_qty=0.
     Now uses `.to_list(None)` (unbounded). Also `sales_vouchers.to_list`
     bumped 20K → 50K to handle larger tenants.

  2. Sales Forecast revamp:
     a. YoY now groups by Indian-FY label (2024-25, 2025-26, 2026-27) instead
        of calendar year, fixing the "only FY 26-27 visible" report.
     b. Forecast horizon now extends to end-of-selected-FY (instead of
        next-3-calendar-months, which was visible OUTSIDE the selected FY's
        range and looked broken).
     c. Forecast = same-month-previous-FY × growth_trend (capped 0.5–2.0).
        Falls back to 0.6 × MA-3 + 0.4 × MA-6 when prev-FY data missing.
        Tags each forecast row with `based_on_prev_fy_month` and
        `growth_trend_pct` so the UI can show provenance.
     d. Frontend bridges actual → forecast line to render continuously
        (Recharts won't draw a line from undefined → defined). Adds method
        caption ("Forecast = same-month previous FY × growth trend ▼ 33%").

  3. Tally Sync Agent v9.8.7-aliases-perf:
     a. Aliases — fetches Tally `LANGUAGENAME.LIST` per stock item and
        stores as an `aliases` array. Customer SKUs / brand short-names
        / part-number variants are now searchable.
     b. TDL FETCH list extended with LANGUAGENAME and ALIAS.
     c. `InventoryItem` model accepts `aliases: Optional[List[str]]`.
     d. `/api/inventory/items` and `/api/salesman-orders/catalog` search
        now matches `aliases` array element-wise (Mongo regex on array).

  4. Mobile responsiveness perf:
     a. `/api/inventory/items` accepts `page`, `page_size`, `search` — when
        page_size > 0 returns paged result + count; else legacy full-list.
     b. `/api/customers/outstanding` accepts same params; full totals stay
        full-tenant accurate, the customers array is paged.
     c. Inventory page: render-cap of 200 rows + "Load 200 more" button.
        Reset cap on filter/search/sort change. Aliases shown as chips.
     d. CustomerCRM Outstanding tab: same 200-row render-cap with debounced
        search input (name/phone/group). Same "Load more" pattern.
"""
import os
from pathlib import Path
import pytest
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

INV_ROUTE = Path("/app/backend/routes/inventory.py")
CRM_ROUTE = Path("/app/backend/routes/customers.py")
SP_ROUTE = Path("/app/backend/routes/salesman_orders.py")
INSIGHTS = Path("/app/backend/routes/insights.py")
AGENT = Path("/app/desktop-agent/tally_sync_agent_v9.py")
PUBLIC = Path("/app/frontend/public/flowra-desktop-agent.py")
INV_PAGE = Path("/app/frontend/src/pages/Inventory.js")
CRM_PAGE = Path("/app/frontend/src/pages/CustomerCRM.js")
INSIDER_PAGE = Path("/app/frontend/src/pages/InsiderResult.js")
MODELS = Path("/app/backend/models.py")


def _login():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": "admin", "password": "admin123", "captcha_token": "",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


@pytest.fixture
def token():
    return _login()


# ─── Issue #1: SPIP zero-stock false positive ─────────────────────────────
def test_spip_loads_all_inventory_no_5k_cap():
    """Items past index 5,000 must reach inv_map so cross-lookup works."""
    code = INSIGHTS.read_text(encoding="utf-8")
    # Old `to_list(5000)` cap is gone for inventory in spip
    assert ".to_list(5000)" not in code
    # Inventory now unbounded
    assert 'inventory = await db.inventory_items.find(q, {"_id": 0}).to_list(None)' in code


def test_spip_total_items_matches_summary(token):
    """Live regression: total_items must equal sum(summary.values())."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/insights/spip-analysis", headers=h)
    data = r.json()["data"]
    summary = data.get("summary") or {}
    assert data["total_items"] == sum(summary.values())


# ─── Issue #2: Sales Forecast (YoY + projection + prev-FY basis) ──────────
def test_forecast_yoy_uses_fy_labels(token):
    """YoY response now keys by Indian-FY label (2024-25), not calendar year."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/insights/sales-forecast", headers=h)
    data = r.json()["data"]
    yoy = data.get("yoy") or []
    if yoy:
        for entry in yoy:
            year = entry.get("year", "")
            # Format must be NNNN-NN (e.g. "2025-26") — NOT plain "2025"
            assert "-" in year and len(year) == 7, f"bad year format: {year!r}"


def test_forecast_includes_prev_fy_provenance(token):
    """Each forecast row must indicate which prev-FY month it was based on
    (or null if it had to fall back to MA)."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/insights/sales-forecast?fy=2026-27", headers=h)
    data = r.json()["data"]
    forecasts = data.get("forecasts") or []
    if forecasts:
        for f in forecasts:
            assert "based_on_prev_fy_month" in f
            assert "growth_trend_pct" in f
            assert "confidence" in f


def test_forecast_horizon_within_selected_fy(token):
    """When fy=2026-27 is selected, forecasts must extend to FY end (Mar 2027)
    — not 3 months from today (which could be inside or outside the FY)."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/insights/sales-forecast?fy=2026-27", headers=h)
    data = r.json()["data"]
    forecasts = data.get("forecasts") or []
    for f in forecasts:
        m = f["month"]  # YYYY-MM
        # Must be within FY 26-27 (Apr 2026 → Mar 2027)
        assert m >= "2026-04" and m <= "2027-03", f"forecast month {m} outside FY 26-27"


def test_forecast_chart_bridge_present():
    """Frontend bridges actual → forecast so the line renders continuously
    (Recharts skips undefined → defined transitions otherwise)."""
    code = INSIDER_PAGE.read_text(encoding="utf-8")
    assert "Bridge actual" in code
    assert "connectNulls" in code


def test_forecast_method_caption_rendered():
    """Forecast tab now shows what the projection is based on."""
    code = INSIDER_PAGE.read_text(encoding="utf-8")
    assert 'data-testid="forecast-method-note"' in code
    assert "same-month previous FY" in code


# ─── Issue #5: Alias sync (agent v9.8.7) ──────────────────────────────────
def test_agent_v987_alias_extraction():
    contents = AGENT.read_text(encoding="utf-8")
    assert "v9.8.7-aliases-perf" in contents
    assert "9.8.7-aliases-perf" in contents
    # LANGUAGENAME extraction
    assert "LANGUAGENAME" in contents
    # 'aliases' field on each item dict
    assert "'aliases': clean_aliases," in contents
    # TDL FETCH list extended
    assert "<FETCH>LANGUAGENAME</FETCH>" in contents


def test_public_agent_v987_present():
    contents = PUBLIC.read_text(encoding="utf-8")
    assert "9.8.7-aliases-perf" in contents


def test_inventory_item_model_accepts_aliases():
    import sys
    sys.path.insert(0, "/app/backend")
    from models import InventoryItem
    obj = InventoryItem(
        item_id="x", item_name="x", quantity=1.0, unit="NOS",
        aliases=["TVS Bolt", "TVS-10mm-Bolt", "B-10-1.25"],
    )
    assert obj.aliases == ["TVS Bolt", "TVS-10mm-Bolt", "B-10-1.25"]


def test_inventory_search_matches_aliases():
    """Backend regex search now hits aliases array."""
    code = INV_ROUTE.read_text(encoding="utf-8")
    assert '{"aliases": {"$regex": esc, "$options": "i"}},' in code


def test_salesman_catalog_search_matches_aliases():
    code = SP_ROUTE.read_text(encoding="utf-8")
    assert '{"aliases": {"$regex": s, "$options": "i"}},' in code


# ─── Issue #6: Mobile pagination ──────────────────────────────────────────
def test_inventory_endpoint_supports_pagination(token):
    """page_size=10 must return at most 10 items + total + page metadata."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/inventory/items?page=1&page_size=10", headers=h)
    data = r.json()["data"]
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert len(data["items"]) <= 10


def test_customers_endpoint_supports_pagination(token):
    """page_size=20 returns paged customers + tenant-wide totals."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/customers/outstanding?page=1&page_size=20", headers=h)
    data = r.json()["data"]
    assert "total" in data
    assert "page" in data
    # total_outstanding is the FULL-tenant figure (not page-only)
    assert "total_outstanding" in data
    assert len(data["customers"]) <= 20


def test_inventory_search_param(token):
    """search='steelgrip' must match KSC's Steelgrip items by name. Skipped
    if the admin tenant has no Steelgrip items (default admin is a separate
    tenant from KSC)."""
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/api/inventory/items?search=steelgrip", headers=h)
    data = r.json()["data"]
    items = data["items"]
    if not items:
        pytest.skip("no Steelgrip items in default admin tenant")
    for it in items:
        full = (it.get("item_name", "") + " " + " ".join(it.get("aliases") or []) + " " + (it.get("part_number") or "")).lower()
        assert "steelgrip" in full, it


def test_inventory_page_render_cap():
    """Frontend caps initial render at 200 rows + Load More button."""
    code = INV_PAGE.read_text(encoding="utf-8")
    assert "renderLimit" in code
    assert "data-testid=\"load-more-inventory\"" in code
    assert "filteredItems.slice(0, renderLimit)" in code


def test_crm_page_render_cap_and_search():
    """CRM Outstanding tab caps render + has search box."""
    code = CRM_PAGE.read_text(encoding="utf-8")
    assert "outstandingLimit" in code
    assert "data-testid=\"load-more-customers\"" in code
    assert "data-testid=\"customer-search\"" in code


def test_inventory_page_renders_aliases():
    """Aliases array shown as chips below item_name."""
    code = INV_PAGE.read_text(encoding="utf-8")
    assert "Array.isArray(item.aliases)" in code
    assert 'data-testid="alias-chips"' in code


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
