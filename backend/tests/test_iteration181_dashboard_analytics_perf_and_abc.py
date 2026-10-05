"""
iter-181 — Dashboard / Analytics performance regression & ABC-tag visibility.

Covers three user-reported issues:
  1. Dashboard load > 35 s (inventory/summary was 5 s cold, no response cache).
  2. Analytics load > 47 s (movement-analysis 32 s + below-cost-sales 30 s).
  3. "Inventory ABC performed, tag not showing" (projection + cache invalidation).

The fixes:
  * Server-side $unwind + $group aggregation in `_get_voucher_rollup_maps`
    replaces per-request Python loops over 1k-20k full voucher docs.
  * Per-tenant TTL response caches on /inventory/summary,
    /inventory/movement-analysis, /inventory/below-cost-sales.
  * `/inventory/items` projection now includes `abc_category` + `item_id`
    so the UI sees the A/B/C/D chip after auto-assign.
  * `_INV_LIST_CACHE.clear()` invoked by `/inventory/abc/auto-assign`
    and `/inventory/items/{id}/abc` so cached pages reflect new tags.
  * Sync writers invalidate the three new caches via
    `invalidate_reconcile_cache(tenant, company)`.
"""
import os
import pytest


def test_projection_includes_abc_category_and_item_id():
    """The /inventory/items projection must surface the two fields the
    UI relies on to render the A/B/C/D chip. Omitting them was the
    "tag not showing" bug (iter-181)."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    # Find the projection block for the inventory list route.
    start = src.find("_proj = {")
    assert start > 0, "could not locate _proj block"
    end = src.find("}", start)
    block = src[start:end]
    assert '"item_id": 1' in block, "item_id must be projected (abc update targets by item_id)"
    assert '"abc_category": 1' in block, "abc_category must be projected"


def test_abc_endpoints_clear_processed_list_cache():
    """Both ABC write-endpoints must invalidate `_INV_LIST_CACHE` so the
    next /inventory/items read reflects the newly-assigned category."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    # Single-item PATCH.
    single_block = src[src.find('async def set_abc_category'):src.find('async def auto_assign_abc')]
    assert "_INV_LIST_CACHE.clear()" in single_block, \
        "set_abc_category must clear _INV_LIST_CACHE after write"
    # Bulk auto-assign.
    auto_block = src[src.find('async def auto_assign_abc'):src.find('async def auto_assign_abc') + 4000]
    assert "_INV_LIST_CACHE.clear()" in auto_block, \
        "auto_assign_abc must clear _INV_LIST_CACHE after bulk write"


def test_summary_endpoint_uses_response_cache():
    """/inventory/summary must have a TTL cache so dashboard polls
    don't re-run the aggregation on every mount."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    sum_block = src[src.find("async def get_inventory_summary"):src.find("async def get_inventory_summary") + 4000]
    assert "_SUMMARY_CACHE" in sum_block, "summary endpoint must use _SUMMARY_CACHE"


def test_movement_and_below_cost_have_response_cache():
    """The two heaviest analytics endpoints must cache their final
    payload so repeat visits are instant."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    mv_block = src[src.find("async def get_inventory_movement"):src.find("async def get_inventory_movement") + 1500]
    bc_block = src[src.find("async def get_below_cost_sales"):src.find("async def get_below_cost_sales") + 1500]
    assert "_MOVEMENT_CACHE" in mv_block, "movement-analysis must use _MOVEMENT_CACHE"
    assert "_BELOW_COST_CACHE" in bc_block, "below-cost-sales must use _BELOW_COST_CACHE"


def test_rollup_helper_uses_server_side_aggregation():
    """`_get_voucher_rollup_maps` must push $unwind+$group to Mongo
    instead of streaming full voucher docs into Python memory."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    helper = src[src.find("async def _get_voucher_rollup_maps"):src.find("async def _get_voucher_rollup_maps") + 4000]
    assert "$unwind" in helper, "rollup helper must $unwind on the DB side"
    assert "$group" in helper, "rollup helper must $group on the DB side"
    assert "aggregate(" in helper, "rollup helper must call collection.aggregate(...)"


def test_sync_invalidator_clears_all_three_new_caches():
    """`invalidate_reconcile_cache` must sweep _SUMMARY_CACHE,
    _MOVEMENT_CACHE and _BELOW_COST_CACHE for the touched tenant so
    stale FY-sales / movement / margin numbers never leak after a sync."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    body = src[src.find("def invalidate_reconcile_cache"):src.find("def invalidate_reconcile_cache") + 2500]
    assert "_SUMMARY_CACHE" in body
    assert "_MOVEMENT_CACHE" in body
    assert "_BELOW_COST_CACHE" in body
    assert "_VOUCHER_ROLLUP_CACHE" in body


def test_movement_endpoint_no_longer_loads_full_voucher_docs():
    """Confirm the slow `db.sales_vouchers.find(..).to_list(10000)` +
    equivalent purchase_vouchers call were removed from
    /inventory/movement-analysis. Those two round-trips were the
    dominant cost (~27 s on tenant 3079b0af)."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    # Isolate movement endpoint.
    start = src.find("async def get_inventory_movement")
    end = src.find("async def get_pivot_data")
    assert start > 0 and end > start
    body = src[start:end]
    assert "db.sales_vouchers.find(q, {\"_id\": 0}).to_list(10000)" not in body, \
        "movement-analysis must not re-fetch full sales voucher docs"
    assert "db.purchase_vouchers.find(q, {\"_id\": 0}).to_list(10000)" not in body, \
        "movement-analysis must not re-fetch full purchase voucher docs"


def test_below_cost_endpoint_no_longer_loads_full_voucher_docs():
    """Same check for /inventory/below-cost-sales — rebuilding the
    per-item price map in Python from 10 k full vouchers was a 30 s
    endpoint. We now rely on the aggregated rollup maps."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "routes", "inventory.py")).read()
    start = src.find("async def get_below_cost_sales")
    end = src.find("# ==================== MOVEMENT ANALYSIS EXCEL EXPORT ====================", start)
    assert start > 0 and end > start
    body = src[start:end]
    # The old all_vouchers / purchase_vouchers_raw fetches are gone.
    assert "all_vouchers = await db.sales_vouchers.find" not in body
    assert "purchase_vouchers_raw = await db.purchase_vouchers.find" not in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
