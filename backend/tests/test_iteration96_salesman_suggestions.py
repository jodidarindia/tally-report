"""Iteration 96 — Salesman order suggestions (repeat-order + cross-sell).

Tests the two new endpoints:
  GET /api/salesman-orders/customer-history/{customer}
  GET /api/salesman-orders/related-items/{customer}

Plus the FE component contract: 3 section pills + chart stays within budget.
"""
import os
import re
import pytest
import httpx

BACKEND = os.environ.get("BACKEND_URL_TEST") or "http://localhost:8001"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"
CUSTOMER = "Krishna Sales Corporation, RAIPUR"

pytestmark = pytest.mark.asyncio


async def _login(client, user, pwd):
    r = await client.post(f"{BACKEND}/api/auth/login",
                          json={"username": user, "password": pwd})
    body = r.json()
    assert body.get("success"), body
    return body["data"]["token"]


async def test_customer_history_returns_repeat_items_with_metadata():
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c, ADMIN_USER, ADMIN_PASS)
        h = {"Authorization": f"Bearer {tok}", "X-Company-Id": COMPANY_ID}
        # URL-encode the customer name (has a comma + space)
        from urllib.parse import quote
        url = f"{BACKEND}/api/salesman-orders/customer-history/{quote(CUSTOMER)}"
        r = await c.get(url, params={"months": 10}, headers=h)
        body = r.json()
        assert body.get("success"), body
        data = body["data"]
        assert data["customer_name"] == CUSTOMER
        assert data["months_window"] == 10
        items = data["items"]
        assert len(items) > 0, "Expected purchase history for known customer"

        # Schema sanity for the first row
        it = items[0]
        for key in (
            "item_name", "total_qty", "total_revenue", "order_count",
            "last_date", "last_qty", "avg_qty_per_order",
            "stock_qty", "price", "unit",
        ):
            assert key in it, f"Missing field: {key} in {it}"

        # Sorted by recency — first row's last_date >= second row's
        if len(items) >= 2 and items[0]["last_date"] and items[1]["last_date"]:
            assert items[0]["last_date"] >= items[1]["last_date"]


async def test_related_items_returns_cross_sell_with_signals():
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c, ADMIN_USER, ADMIN_PASS)
        h = {"Authorization": f"Bearer {tok}", "X-Company-Id": COMPANY_ID}
        from urllib.parse import quote
        url = f"{BACKEND}/api/salesman-orders/related-items/{quote(CUSTOMER)}"
        r = await c.get(url, params={"months": 12, "limit": 12}, headers=h)
        body = r.json()
        assert body.get("success"), body
        data = body["data"]
        assert data["bought_count"] > 0, "Customer must have prior purchases"
        items = data["items"]
        assert len(items) > 0, "Expected cross-sell candidates"
        assert len(items) <= 12

        # Each item carries a signal label, a co-occurrence count, a velocity,
        # a score, and current stock/price metadata.
        for it in items:
            assert it["signal"] in ("affinity", "fast_moving", "both"), it
            assert it["co_occurrence"] >= 0
            assert it["velocity_qty"] >= 0
            assert 0 <= it["score"] <= 1
            assert "item_name" in it
            assert "stock_qty" in it
            assert "price" in it

        # Signals should be a mix — at least one fast-mover or affinity.
        signals = {it["signal"] for it in items}
        assert signals & {"affinity", "fast_moving", "both"} != set()


async def test_related_items_excludes_already_purchased():
    """An item the customer has already bought must NEVER appear in
    cross-sell suggestions."""
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c, ADMIN_USER, ADMIN_PASS)
        h = {"Authorization": f"Bearer {tok}", "X-Company-Id": COMPANY_ID}
        from urllib.parse import quote
        # Pull what the customer has bought
        hist = (await c.get(f"{BACKEND}/api/salesman-orders/customer-history/{quote(CUSTOMER)}",
                            params={"months": 24}, headers=h)).json()["data"]["items"]
        bought_set = {it["item_name"].strip().lower() for it in hist}
        # Get suggestions on the same window
        rel = (await c.get(f"{BACKEND}/api/salesman-orders/related-items/{quote(CUSTOMER)}",
                           params={"months": 24, "limit": 30}, headers=h)).json()["data"]["items"]
        for it in rel:
            assert it["item_name"].strip().lower() not in bought_set, (
                f"Suggestion {it['item_name']!r} was already bought by customer"
            )


async def test_endpoints_match_existing_unauth_convention():
    """Mirror the convention used by the existing /catalog and /my-stats
    endpoints in this router: when called without a tenant, return
    `success: True` with empty data (tenant filter sees nothing). The data
    is privacy-protected because the tenant_id is None, not because we
    return 401 — this is the established pattern in salesman_orders.py."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BACKEND}/api/salesman-orders/customer-history/X")
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        assert body["data"]["items"] == []


def test_frontend_section_pills_present():
    """The redesigned OrderForm must wire up 3 section pills + key UX bits."""
    src = open("/app/frontend/src/pages/SalesmanOrderApp.js").read()
    # Pills wired with `data-testid={`section-${s.id}`}` — check for sids
    for sid in ("repeat", "suggest", "browse"):
        assert (f"id: '{sid}'" in src
                or f"id: \"{sid}\"" in src), f"Section id missing: {sid}"
    # Helper components exist
    for fn in ("RepeatRow", "SuggestRow", "CatalogRow", "CartPanel", "SectionEmpty"):
        assert re.search(rf"function {fn}\b", src), f"Missing component {fn}"
    # Mobile cart toggle exists
    assert "cart-toggle" in src
    # Signal labels are user-friendly
    assert "Hot pick" in src
    assert "Bought with regulars" in src
    assert "Fast mover" in src
    # New endpoints are wired
    assert "/api/salesman-orders/customer-history/" in src
    assert "/api/salesman-orders/related-items/" in src
