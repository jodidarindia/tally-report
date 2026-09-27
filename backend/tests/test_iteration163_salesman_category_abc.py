"""iter-163: Salesman screens surface product_category + ABC per item.

- Item-Wise Sales tab (admin's Salesman menu) shows Category + ABC pill.
- New Order screens (Repeat / Suggestions / Browse) show the same chips.
- Backend enrichment: `/salesman-orders/catalog`, `_build_inventory_lookup`,
  `/salesman-orders/my-stats`, and `/salesman/performance-detailed`.
- Catalog is now FY-scope-safe (dedupe) so BSA-style per-FY snapshots
  don't render the same SKU twice with contradictory stock qty.
"""
import inspect
from routes.inventory import _dedupe_inventory_by_name


def test_dedupe_wired_into_salesman_orders_catalog():
    from routes.salesman_orders import get_catalog
    src = inspect.getsource(get_catalog)
    assert "_dedupe_inventory_by_name" in src, "catalog must dedupe"
    assert "to_list(20000)" in src, "catalog limit must be raised from 2000"


def test_dedupe_wired_into_build_inventory_lookup():
    from routes.salesman_orders import _build_inventory_lookup
    src = inspect.getsource(_build_inventory_lookup)
    assert "_dedupe_inventory_by_name" in src


def test_catalog_response_carries_abc_category_key():
    """The response dict in /catalog must include abc_category (else the
    UI chip is silently blank)."""
    from routes.salesman_orders import get_catalog
    src = inspect.getsource(get_catalog)
    assert '"abc_category"' in src


def test_inventory_lookup_carries_abc_category_key():
    from routes.salesman_orders import _build_inventory_lookup
    src = inspect.getsource(_build_inventory_lookup)
    assert '"abc_category"' in src


def test_my_stats_enriches_items_sold():
    from routes.salesman_orders import get_my_stats
    src = inspect.getsource(get_my_stats)
    assert "product_category" in src and "abc_category" in src


def test_performance_detailed_enriches_items_sold():
    from routes.salesman import get_salesman_performance_detailed
    src = inspect.getsource(get_salesman_performance_detailed)
    assert "product_category" in src and "abc_category" in src
    assert "_inv_lookup" in src


def test_dedupe_no_op_when_items_have_no_fy():
    """Tally-shape catalog rows must not be dropped by the dedupe path."""
    rows = [
        {"item_name": "SPARK PLUG NGK (PACK 4)", "quantity": 102, "abc_category": "C"},
        {"item_name": "HYDRAULIC OIL 68 20LT",   "quantity": 103, "abc_category": "A"},
    ]
    out = _dedupe_inventory_by_name(rows)
    assert len(out) == 2
