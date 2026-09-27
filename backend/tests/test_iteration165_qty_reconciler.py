"""iter-165: Server-side voucher-derived quantity reconciliation.

Busy agent <= v1.6.1 reads ``closing_qty`` from ``max(abs(D11..D50))``
in Folio1. Those D-slots are monthly period-tallies on Busy 21 builds
so items get inflated (LF16303 44 vs Busy 16, FA00725 2000 vs Busy 0).

Server-side fix: derived_closing = opening + Σ purchases − Σ sales.
Override the agent's value only when:
  1. derived_closing >= 0 (physically possible)
  2. agent_qty > derived_closing + tolerance (agent is inflated)
  3. Voucher activity exists (inward or outward != 0)

Skip in every other case so incomplete voucher sync doesn't damage
correct agent values (busydemo purchase set is sparse; iter-165 v1 was
producing negatives and we backed off).
"""
import asyncio
from types import SimpleNamespace


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _patch_db(monkeypatch, sales, purchases):
    """Stub ``db.sales_vouchers`` and ``db.purchase_vouchers``."""
    import routes.inventory as inv

    class _AsyncCursor:
        def __init__(self, rows): self._rows = rows
        async def to_list(self, _): return list(self._rows)

    class _Coll:
        def __init__(self, rows): self._rows = rows
        def find(self, *a, **k): return _AsyncCursor(self._rows)

    class _StubDb:
        def __init__(self):
            self.sales_vouchers    = _Coll(sales)
            self.purchase_vouchers = _Coll(purchases)

    monkeypatch.setattr(inv, "db", _StubDb())


def test_inflated_closing_gets_reconciled_to_voucher_movement(monkeypatch):
    """LF16303 shape: agent stored 44, real Busy closing 16, opening 0,
    16 units received in purchases. Reconciler overrides 44 → 16."""
    from routes.inventory import _reconcile_item_quantities
    items = [{
        "item_name": "FLG LF16303 LUBE FILTER- FARMTRAC TR",
        "opening_quantity": 0.0, "quantity": 44.0,
        "cost_price": 100.0, "closing_value": 4400.0,
    }]
    sales = []
    purchases = [{"items": [{"item": "flg lf16303 lube filter- farmtrac tr", "quantity": 16}]}]
    _patch_db(monkeypatch, sales, purchases)
    out = _run(_reconcile_item_quantities(items, "t", "c", None))
    assert out[0]["quantity"] == 16.0
    assert out[0]["_agent_quantity"] == 44.0
    assert out[0]["closing_value"] == 1600.0  # 16 × 100


def test_zero_activity_zero_stock_keeps_agent(monkeypatch):
    """FA00725 shape: agent stored 2000, no vouchers, opening 0. Since
    the agent shows 2000 and there's *no* voucher movement, guard (3)
    prevents override. This item won't be fixed by reconcile alone —
    still needs the agent v1.6.2 D-column fix. But we don't damage it
    either."""
    from routes.inventory import _reconcile_item_quantities
    items = [{
        "item_name": "FA00725 DEF Liquid",
        "opening_quantity": 0.0, "quantity": 2000.0,
        "cost_price": 50.0, "closing_value": 100000.0,
    }]
    _patch_db(monkeypatch, [], [])
    out = _run(_reconcile_item_quantities(items, "t", "c", None))
    # No voucher activity — kept as-is (guard 3).
    assert out[0]["quantity"] == 2000.0
    assert "_agent_quantity" not in out[0]


def test_negative_derived_closing_is_ignored(monkeypatch):
    """When purchase sync is incomplete, opening + inward − outward can
    go negative. Never persist that — keep the agent's value."""
    from routes.inventory import _reconcile_item_quantities
    items = [{
        "item_name": "SARTHI Engine Oil 1 LTR",
        "opening_quantity": 0.0, "quantity": 40.0,
        "cost_price": 100.0,
    }]
    sales = [{"items": [{"item": "sarthi engine oil 1 ltr", "quantity": 80}]}]
    purchases = []  # missing sync
    _patch_db(monkeypatch, sales, purchases)
    out = _run(_reconcile_item_quantities(items, "t", "c", None))
    # derived = 0 + 0 − 80 = −80 → guard (1) skip.
    assert out[0]["quantity"] == 40.0
    assert "_agent_quantity" not in out[0]


def test_agent_undercount_is_not_overwritten(monkeypatch):
    """If the agent stored *less* than derived (edge case: agent under-
    reports), the reconciler must not lower it — safer for stock-out
    alerts. Guard (2)."""
    from routes.inventory import _reconcile_item_quantities
    items = [{
        "item_name": "6212 BALL BEARING",
        "opening_quantity": 10.0, "quantity": 5.0,   # agent < derived
        "cost_price": 200.0,
    }]
    sales = []
    purchases = [{"items": [{"item": "6212 ball bearing", "quantity": 8}]}]
    _patch_db(monkeypatch, sales, purchases)
    out = _run(_reconcile_item_quantities(items, "t", "c", None))
    # derived = 10 + 8 − 0 = 18, agent = 5 < 18 → keep agent.
    assert out[0]["quantity"] == 5.0
    assert "_agent_quantity" not in out[0]


def test_closing_value_re_derived_at_cost(monkeypatch):
    from routes.inventory import _reconcile_item_quantities
    items = [{
        "item_name": "Widget",
        "opening_quantity": 0.0, "quantity": 100.0,
        "cost_price": 25.0, "closing_value": 2500.0,
    }]
    _patch_db(monkeypatch, [], [{"items": [{"item": "widget", "quantity": 20}]}])
    out = _run(_reconcile_item_quantities(items, "t", "c", None))
    assert out[0]["quantity"] == 20.0
    assert out[0]["closing_value"] == 500.0  # 20 × 25


def test_fy_scoped_reconciliation(monkeypatch):
    """Vouchers outside the requested FY must not contribute to the
    derived closing."""
    from routes.inventory import _reconcile_item_quantities
    items = [{
        "item_name": "Widget",
        "opening_quantity": 0.0, "quantity": 50.0,
        "cost_price": 10.0, "fy": "2026-27",
    }]
    _patch_db(
        monkeypatch,
        [{"fy": "2025-26", "voucher_date": "2025-04-01", "items": [{"item": "widget", "quantity": 100}]}],  # FY 25-26
        [{"fy": "2026-27", "voucher_date": "2026-06-01", "items": [{"item": "widget", "quantity": 15}]}],   # FY 26-27
    )
    out = _run(_reconcile_item_quantities(items, "t", "c", "2026-27"))
    # Only 15 inward counts (FY 26-27); FY 25-26 sale ignored.
    # derived = 0 + 15 − 0 = 15. agent = 50 > 15 → override to 15.
    assert out[0]["quantity"] == 15.0


def test_empty_items_short_circuits(monkeypatch):
    from routes.inventory import _reconcile_item_quantities
    _patch_db(monkeypatch, [], [])
    out = _run(_reconcile_item_quantities([], "t", "c", None))
    assert out == []
