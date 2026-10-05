"""
iter-181b — Re-navigation response caches on hot endpoints.

User complaint: "Inventory page and all other pages, once loaded, take
the same loading time for the same company if clicked again. Why?"

Root cause: the earlier iter-181 caches memoised intermediate work
(processed-list, roll-up maps) but every re-mount still paid for:
  - two `distinct()` round-trips on /inventory/items
  - a 100 KB JSON transfer of 200+ items
  - full-collection scan + Python filter on /sales/vouchers
  - full-collection scan on /sales/analytics
  - full-collection scan on /sales/customer-names
So the user saw the same latency on every re-navigation.

Fix: final-response TTL caches keyed on (tenant, company, FY, filters)
on each of those endpoints, cleared by sync writers.
"""
import os


SRC_INV = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
SRC_SALES = open(os.path.join(os.path.dirname(__file__), "..", "routes", "sales.py")).read()
SRC_SYNC = open(os.path.join(os.path.dirname(__file__), "..", "routes", "sync.py")).read()


def test_inventory_items_has_response_cache():
    """`/inventory/items` must have a final-response cache so repeat
    navigations hit the cached payload (not just the processed list)."""
    assert "_INV_RESP_CACHE" in SRC_INV, "inventory.py must declare _INV_RESP_CACHE"
    body = SRC_INV[SRC_INV.find("async def get_inventory_items"):SRC_INV.find("async def get_inventory_summary")]
    assert "_INV_RESP_CACHE.get(" in body, "/inventory/items must read from _INV_RESP_CACHE"
    assert "_INV_RESP_CACHE[_resp_key]" in body, "/inventory/items must write to _INV_RESP_CACHE"


def test_sales_summary_and_vouchers_and_analytics_have_caches():
    """The three Sales endpoints that re-mount on every nav must each
    hold a final-response cache so re-visits are instant."""
    assert "_SALES_SUMMARY_CACHE" in SRC_SALES
    assert "_SALES_VOUCHERS_CACHE" in SRC_SALES
    assert "_SALES_ANALYTICS_CACHE" in SRC_SALES
    sum_body = SRC_SALES[SRC_SALES.find("async def get_sales_summary"):SRC_SALES.find("async def get_sales_analytics")]
    an_body = SRC_SALES[SRC_SALES.find("async def get_sales_analytics"):SRC_SALES.find("async def get_customer_names")]
    cn_body = SRC_SALES[SRC_SALES.find("async def get_customer_names"):SRC_SALES.find("async def get_customer_item_sales")]
    assert "_SALES_SUMMARY_CACHE.get" in sum_body
    assert "_SALES_ANALYTICS_CACHE.get" in an_body
    assert "_SALES_ANALYTICS_CACHE" in cn_body, "customer-names should reuse the analytics cache"


def test_sales_vouchers_honours_limit_and_fy_in_db_match():
    """Prior to iter-181b `/sales/vouchers` ignored `limit=` entirely
    and pulled the whole collection just to Python-filter by FY. Both
    must now happen in the DB match."""
    body = SRC_SALES[SRC_SALES.find("async def get_sales_vouchers"):SRC_SALES.find("async def get_voucher_detail")]
    # FY range pushed to Mongo via voucher_date $gte/$lte.
    assert "fy_to_date_range" in body
    assert '"voucher_date": {"$gte"' in body or '"$gte": fy_start' in body
    # limit honoured server-side.
    assert ".limit(limit)" in body
    assert "limit: int = 0" in body, "limit query parameter must be exposed"


def test_sync_invalidates_sales_caches():
    """Sync writers must clear the three sales caches so stale totals
    never leak after a fresh voucher batch lands."""
    assert "_SALES_SUMMARY_CACHE.clear()" in SRC_SYNC
    assert "_SALES_VOUCHERS_CACHE.clear()" in SRC_SYNC
    assert "_SALES_ANALYTICS_CACHE.clear()" in SRC_SYNC


def test_sync_invalidates_inv_response_cache():
    """Likewise the inventory-items response cache must be dropped on
    sync (handled via `_INV_RESP_CACHE.clear()` in invalidate_reconcile_cache)."""
    inv_invalidator = SRC_INV[SRC_INV.find("def invalidate_reconcile_cache"):SRC_INV.find("def invalidate_reconcile_cache") + 3000]
    assert "_INV_RESP_CACHE.clear()" in inv_invalidator or "_INV_RESP_CACHE" in inv_invalidator


def test_abc_write_endpoints_clear_response_cache_too():
    """ABC writes must drop _INV_RESP_CACHE in addition to the
    processed-list cache — the cached JSON payload would otherwise
    still have the old (or empty) `abc_category` on each item."""
    single = SRC_INV[SRC_INV.find("async def set_abc_category"):SRC_INV.find("async def auto_assign_abc")]
    bulk = SRC_INV[SRC_INV.find("async def auto_assign_abc"):SRC_INV.find("async def auto_assign_abc") + 4000]
    assert "_INV_RESP_CACHE.clear()" in single, "set_abc_category must clear response cache"
    assert "_INV_RESP_CACHE.clear()" in bulk, "auto_assign_abc must clear response cache"


def test_customer_names_uses_native_distinct_not_full_scan():
    """`/sales/customer-names` previously fetched every voucher just
    to collect `party_name`. Must now use Mongo's `distinct()`."""
    body = SRC_SALES[SRC_SALES.find("async def get_customer_names"):SRC_SALES.find("async def get_customer_item_sales")]
    assert "distinct(\"party_name\"" in body
    assert "find(q, {\"_id\": 0, \"party_name\"" not in body, \
        "customer-names must not pull full voucher list"


def test_sales_analytics_uses_server_side_aggregation():
    """`/sales/analytics` must group daily totals via `$group` on the
    DB side, not Python loops over every voucher."""
    body = SRC_SALES[SRC_SALES.find("async def get_sales_analytics"):SRC_SALES.find("async def get_customer_names")]
    assert "$group" in body
    assert "aggregate(" in body


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
