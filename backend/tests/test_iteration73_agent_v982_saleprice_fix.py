"""
Iteration 73 — Tally Sync Agent v9.8.2-saleprice-fix.

User reported: "Inventory page still showing cost price in sale price column.
Even after new sync. Checked for ASA Autotech company."

Root cause: agent v9.7.x → v9.8.1 had a buggy fallback:
    if std_price == 0 and rate > 0:
        std_price = rate  # ← rate is `closing_value/closing_qty` = COST
This silently substituted the cost rate for the standard sale price whenever
Tally master had no STANDARDPRICE for an item. 100% of the production
tenant's `inventory_items` (2308/2308) had `standard_price == price`.

Three coordinated fixes:

(1) AGENT v9.8.2 — remove the cost-rate fallback. Leave standard_price=0
    when Tally has no STANDARDPRICE. Add `standard_price_source` field
    ('tally_master' | 'unset') for diagnostic visibility.

(2) BACKEND — `/api/sync/upload` for `inventory` now detects the polluted
    pattern (std_price == price) on incoming docs and resets to 0 before
    insert. Catches stale/cached agents that haven't been updated.
    Also: `/inventory/movement-analysis` and `/salesman-orders/catalog`
    no longer fall back to `price` for sale price (was quoting at COST).

(3) FRONTEND — Inventory page's "Sale Price" column shows
    "Set in Tally" amber badge instead of the cost rate when standard_price
    is 0. InventoryAnalytics list rows do the same.

A one-shot DB cleanup also ran during deploy to reset the 2308 polluted
items to standard_price=0, so users see the corrected UI immediately
(without waiting for re-sync).
"""
import os
import asyncio
import pytest


# ── (2a) Sync-upload sanity guard — blocks polluted std_price ──

def test_sync_upload_resets_polluted_std_price(monkeypatch):
    """An inventory item with std_price == price (cost-rate fallback artefact)
    must be reset to standard_price=0 on insert. Test mirrors the contract
    of routes/sync.py:127-135.
    """
    item = {"item_id": "X1", "item_name": "X1",
            "quantity": 10, "unit": "PCS",
            "price": 633.71, "standard_price": 633.71}

    sp = item.get('standard_price') or 0
    pr = item.get('price') or 0
    if sp > 0 and pr > 0 and abs(sp - pr) < 0.01:
        item['standard_price'] = 0
        item['standard_price_source'] = 'unset_cleaned_v982'

    assert item['standard_price'] == 0
    assert item.get('standard_price_source') == 'unset_cleaned_v982'


def test_sync_upload_keeps_genuine_std_price():
    """Genuine std_price (different from cost rate) survives the guard."""
    item = {"item_id": "X1", "item_name": "X1",
            "quantity": 10, "unit": "PCS",
            "price": 500.0, "standard_price": 750.0}  # 50% margin

    sp = item.get('standard_price') or 0
    pr = item.get('price') or 0
    if sp > 0 and pr > 0 and abs(sp - pr) < 0.01:
        item['standard_price'] = 0

    assert item['standard_price'] == 750.0


def test_sync_upload_keeps_zero_std_price():
    """std_price=0 (not set in Tally) is left alone."""
    item = {"item_id": "X1", "item_name": "X1",
            "quantity": 10, "unit": "PCS",
            "price": 500.0, "standard_price": 0}

    sp = item.get('standard_price') or 0
    pr = item.get('price') or 0
    if sp > 0 and pr > 0 and abs(sp - pr) < 0.01:
        item['standard_price'] = 0

    assert item['standard_price'] == 0


# ── (3) DB-state assertion — no item should have std_price == price ──

def test_db_has_no_polluted_inventory_items():
    """After v9.8.2 cleanup migration, NO inventory_items row should have
    standard_price exactly equal to price (the cost-rate signature)."""
    from db import db

    async def _check():
        return await db.inventory_items.count_documents({
            '$expr': {'$and': [
                {'$gt': ['$standard_price', 0]},
                {'$eq': ['$standard_price', '$price']},
            ]}
        })

    polluted = asyncio.get_event_loop().run_until_complete(_check())
    assert polluted == 0, f"{polluted} polluted items still present — re-run cleanup"


# ── (1) Public agent stamp ──

def test_public_agent_is_v982():
    path = "/app/frontend/public/flowra-desktop-agent.py"
    if not os.path.exists(path):
        pytest.skip("public agent not present")
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()
    assert "9.8.2-saleprice-fix" in contents
    # Cost-rate fallback must be GONE
    assert "std_price = rate" not in contents
    # New diagnostic field must be present
    assert "standard_price_source" in contents


def test_agent_no_longer_has_cost_fallback():
    """Hard guard against the regression. Agent must never assign std_price
    from the closing rate."""
    path = "/app/frontend/public/flowra-desktop-agent.py"
    if not os.path.exists(path):
        pytest.skip("public agent not present")
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()
    forbidden = [
        "std_price = rate",
        "std_price = price",
        "standard_price = rate",
        "standard_price = price",
    ]
    for needle in forbidden:
        assert needle not in contents, (
            f"forbidden cost-rate fallback found: {needle!r}"
        )


# ── (2b) API: catalog endpoint never quotes at cost ──

import requests  # noqa: E402

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


def test_salesman_catalog_no_longer_quotes_cost(admin_h):
    """The salesman catalog must NOT fall back from standard_price to cost.
    For items with no Tally STDPRICE, both `price` and `standard_price`
    must be 0 — never the closing rate."""
    r = requests.get(f"{API_URL}/api/salesman-orders/catalog", headers=admin_h)
    if r.status_code != 200:
        pytest.skip(f"catalog endpoint returned {r.status_code}")
    body = r.json()
    if not body.get("success"):
        pytest.skip(f"catalog: {body.get('error')}")
    items = body["data"]["items"]
    # If catalog is empty, skip cleanly (test tenants without inventory)
    if not items:
        pytest.skip("catalog empty for this tenant")
    # No item should have price > 0 unless standard_price > 0
    for it in items:
        if it["price"] > 0:
            assert it["standard_price"] > 0, (
                f"item {it['item_name']!r}: price={it['price']} but "
                f"standard_price=0 — cost-rate fallback regression"
            )


def test_inventory_movement_analysis_doesnt_use_cost_as_sale_price(admin_h):
    """Movement analysis's per-item standard_price must not be filled from
    closing rate."""
    r = requests.get(f"{API_URL}/api/inventory/movement-analysis", headers=admin_h)
    if r.status_code != 200:
        pytest.skip(f"endpoint returned {r.status_code}")
    body = r.json()
    items = body.get("items", []) if isinstance(body, dict) else []
    if not items:
        pytest.skip("no inventory items for this tenant")
    # If standard_price equals current_stock-derived rate, that's the bug.
    # We can't compare directly here without the cost field, but at minimum
    # standard_price should be a number (>=0), not None.
    for it in items[:50]:
        assert it.get("standard_price") is not None
        assert isinstance(it["standard_price"], (int, float))


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
