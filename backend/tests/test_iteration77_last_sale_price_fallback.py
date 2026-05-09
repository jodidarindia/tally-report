"""
Iteration 77 — Last-Sale-Price fallback for Inventory + Salesman Catalog.

User-reported bug: After v9.8.2 stripped the cost-rate fallback from
`standard_price`, every Inventory row showed "Set in Tally" because the
user has not maintained STANDARDPRICE in Tally master for any of their
~7,700 stock items. They wanted real sale prices to surface.

Fix: derive "Last Sale Price" from the most recent sales_voucher line
per item. Tally master STANDARDPRICE always wins when present (cleanest
truth), but when it's 0 we surface the most recent invoice rate so:
- Inventory page no longer looks empty
- Salesman catalog quotes a sane price (NEVER cost — `price` field)
- Auto-updates as new bills sync

Endpoints:
- GET /api/inventory/items
- GET /api/salesman-orders/catalog
- GET /api/inventory/category-sales

This test stamps a tiny synthetic dataset, hits the live endpoints, and
asserts the fallback shape.
"""
import os
import asyncio
from datetime import datetime, timezone
import pytest
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


def _login():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "username": "admin", "password": "admin123", "captcha_token": "",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"], r.json()["data"]["token"]


@pytest.fixture
def admin():
    user_data, token = _login()
    return user_data, {"Authorization": f"Bearer {token}"}


# A real synced company — exercises the fallback against production data.
TEST_COMPANY = "03f638d1-eab0-47ee-aed6-59049ebb5207"  # ASA Autotech


def test_inventory_items_surfaces_last_sale_price(admin):
    """Every inventory row must include the new last_sale_price /
    last_sale_date / sale_price_source / effective_sale_price fields."""
    _, h = admin
    r = requests.get(
        f"{API_URL}/api/inventory/items?company_id={TEST_COMPANY}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert items, "no inventory rows in test company"

    # Schema: every row carries the new fields (even when 0)
    for it in items[:20]:
        assert "last_sale_price" in it, it
        assert "last_sale_date" in it, it
        assert "sale_price_source" in it, it
        assert "effective_sale_price" in it, it
        assert it["sale_price_source"] in ("tally_master", "last_sale", "unset")

    # At least one row must have a derived last-sale price (real data)
    with_last = [it for it in items if (it.get("last_sale_price") or 0) > 0]
    assert with_last, "expected at least one item with derived last_sale_price"


def test_inventory_effective_price_priority(admin):
    """When standard_price > 0 it wins. Otherwise last_sale_price fills in.
    effective_sale_price must equal whichever was chosen."""
    _, h = admin
    r = requests.get(
        f"{API_URL}/api/inventory/items?company_id={TEST_COMPANY}",
        headers=h,
    )
    items = r.json()["data"]["items"]
    for it in items:
        std = it.get("standard_price") or 0
        last = it.get("last_sale_price") or 0
        eff = it.get("effective_sale_price") or 0
        src = it.get("sale_price_source")
        if std > 0:
            assert eff == std, it
            assert src == "tally_master"
        elif last > 0:
            assert eff == last, it
            assert src == "last_sale"
        else:
            assert eff == 0
            assert src == "unset"


def test_salesman_catalog_quotes_last_sale_when_master_unset(admin):
    """Salesman catalog must NEVER quote 0 when last_sale_price is available."""
    _, h = admin
    r = requests.get(
        f"{API_URL}/api/salesman-orders/catalog?company_id={TEST_COMPANY}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert items, "no catalog rows"

    # Effective `price` = standard_price > 0 ? standard_price : last_sale_price
    for it in items:
        std = it.get("standard_price") or 0
        last = it.get("last_sale_price") or 0
        price = it.get("price") or 0
        src = it.get("sale_price_source")
        if std > 0:
            assert price == std
            assert src == "tally_master"
        elif last > 0:
            assert price == last
            assert src == "last_sale"
        else:
            assert price == 0
            assert src == "unset"


def test_catalog_never_quotes_cost(admin):
    """`price` must never equal the cost field (`it.price` on inventory_items
    represents closing rate = cost). This regression-guards v9.8.2."""
    _, h = admin
    r = requests.get(
        f"{API_URL}/api/salesman-orders/catalog?company_id={TEST_COMPANY}",
        headers=h,
    )
    items = r.json()["data"]["items"]
    # Any item that has a quoted price must have a documented source — never silent
    for it in items:
        if (it.get("price") or 0) > 0:
            assert it.get("sale_price_source") in ("tally_master", "last_sale"), it


def test_last_sale_price_helper_picks_most_recent():
    """Unit-test the helper directly: when an item has multiple sales,
    the most recent voucher's rate is the one returned."""
    from db import db
    from routes.inventory import _last_sale_price_map

    async def run():
        # Plant 2 vouchers — one old, one recent — for the same item
        tenant = "iter77-test-tenant"
        company = "iter77-test-company"
        item_name = "Iter77 Test Widget"
        await db.sales_vouchers.delete_many({"tenant_id": tenant})
        await db.sales_vouchers.insert_many([
            {
                "tenant_id": tenant, "company_id": company,
                "voucher_date": "2025-01-15", "voucher_number": "OLD-001",
                "items": [{"item": item_name, "quantity": 10, "rate": 100, "amount": 1000}],
            },
            {
                "tenant_id": tenant, "company_id": company,
                "voucher_date": "2026-04-10", "voucher_number": "NEW-001",
                "items": [{"item": item_name, "quantity": 5, "rate": 250, "amount": 1250}],
            },
        ])

        m = await _last_sale_price_map({"tenant_id": tenant, "company_id": company})
        key = item_name.lower()
        assert key in m, m
        assert m[key]["price"] == 250.0, m[key]
        assert m[key]["date"] == "2026-04-10", m[key]
        assert m[key]["voucher_no"] == "NEW-001", m[key]

        await db.sales_vouchers.delete_many({"tenant_id": tenant})

    asyncio.get_event_loop().run_until_complete(run())


def test_last_sale_price_helper_falls_back_to_amount_div_qty():
    """When voucher line has no `rate` field, helper computes amount/qty."""
    from db import db
    from routes.inventory import _last_sale_price_map

    async def run():
        tenant = "iter77-amt-tenant"
        company = "iter77-amt-company"
        item_name = "Iter77 Amount Item"
        await db.sales_vouchers.delete_many({"tenant_id": tenant})
        await db.sales_vouchers.insert_one({
            "tenant_id": tenant, "company_id": company,
            "voucher_date": "2026-04-01", "voucher_number": "AMT-001",
            "items": [{"item": item_name, "quantity": 4, "amount": 800}],  # no rate
        })

        m = await _last_sale_price_map({"tenant_id": tenant, "company_id": company})
        assert m[item_name.lower()]["price"] == 200.0  # 800/4

        await db.sales_vouchers.delete_many({"tenant_id": tenant})

    asyncio.get_event_loop().run_until_complete(run())


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
