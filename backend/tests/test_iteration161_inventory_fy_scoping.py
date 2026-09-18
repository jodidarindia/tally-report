"""iter-161: Inventory FY-scoping regression tests.

Previous iter-158 dedupe summed quantities across FYs, which double-counted
Busy's per-FY snapshots. This iteration switches to "pick the row for the
selected FY" (or the latest FY when none specified) — no summing.
"""
from routes.inventory import _dedupe_inventory_by_name


def _row(name, fy, qty, cost=10.0, extra=None):
    r = {
        "item_name": name,
        "fy": fy,
        "quantity": qty,
        "cost_price": cost,
        "closing_value": qty * cost,
        "last_updated": f"{fy}-04-01",
    }
    if extra:
        r.update(extra)
    return r


def test_dedupe_picks_latest_fy_when_no_hint():
    rows = [
        _row("Widget A", "2025-26", 5.0),
        _row("Widget A", "2026-27", 10.0),
    ]
    out = _dedupe_inventory_by_name(rows)
    assert len(out) == 1
    # Latest FY row wins — quantity is NOT summed.
    assert out[0]["quantity"] == 10.0
    assert out[0]["fy"] == "2026-27"
    assert out[0]["_dedupe_group_size"] == 2


def test_dedupe_filters_by_fy_hint():
    rows = [
        _row("Widget A", "2025-26", 5.0),
        _row("Widget A", "2026-27", 10.0),
        _row("Widget B", "2026-27", 7.0),
    ]
    out = _dedupe_inventory_by_name(rows, fy_hint="2025-26")
    names = {r["item_name"]: r["quantity"] for r in out}
    # Only rows tagged 2025-26 are kept — B is dropped.
    assert names == {"Widget A": 5.0}


def test_dedupe_keeps_untagged_rows_regardless_of_fy():
    """Tally masters and legacy Busy rows have no ``fy`` field —
    they must always be kept because they carry the only snapshot."""
    rows = [
        {"item_name": "Legacy Item", "quantity": 3.0, "cost_price": 20.0},  # no fy
        _row("Widget A", "2026-27", 10.0),
    ]
    out = _dedupe_inventory_by_name(rows, fy_hint="2025-26")
    names = {r["item_name"]: r.get("quantity", 0) for r in out}
    assert names == {"Legacy Item": 3.0}
    # And without fy_hint, both come through.
    out2 = _dedupe_inventory_by_name(rows)
    names2 = {r["item_name"]: r.get("quantity", 0) for r in out2}
    assert names2 == {"Legacy Item": 3.0, "Widget A": 10.0}


def test_dedupe_no_double_counting_for_bsa_shape():
    """Reproduce BSA symptom: 3 FYs of the same 2 items → previously
    summed to 6 rows @ inflated qty. Now: 2 rows, correct FY qty."""
    rows = []
    for fy, qty in [("2024-25", 3.0), ("2025-26", 5.0), ("2026-27", 8.0)]:
        rows.append(_row("Item X", fy, qty, cost=100.0))
        rows.append(_row("Item Y", fy, qty * 2, cost=50.0))
    # Current FY selected
    out = _dedupe_inventory_by_name(rows, fy_hint="2026-27")
    assert len(out) == 2
    by = {r["item_name"]: r["quantity"] for r in out}
    assert by == {"Item X": 8.0, "Item Y": 16.0}
    total_value = sum(r["quantity"] * r["cost_price"] for r in out)
    # 8*100 + 16*50 = 800 + 800 = 1600
    assert total_value == 1600.0


def test_dedupe_case_insensitive_grouping():
    rows = [
        _row("WIDGET A", "2026-27", 4.0),
        _row("widget a", "2026-27", 6.0),   # same key, treated identical
    ]
    out = _dedupe_inventory_by_name(rows)
    assert len(out) == 1
    # No summing anymore — one row wins as-is.
    assert out[0]["quantity"] in (4.0, 6.0)


def test_dedupe_empty_returns_empty():
    assert _dedupe_inventory_by_name([]) == []
    assert _dedupe_inventory_by_name([], fy_hint="2026-27") == []


def test_dedupe_tally_row_no_op():
    """Tally rows have unique item_id per SKU — dedupe is a no-op."""
    rows = [
        {"item_name": f"Item {i}", "item_id": f"tally-{i}", "quantity": float(i), "cost_price": 10.0}
        for i in range(1, 6)
    ]
    out = _dedupe_inventory_by_name(rows)
    assert len(out) == 5
