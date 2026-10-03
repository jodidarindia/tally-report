"""iter-176 — Inventory reconciliation TTL cache.

Context: `_reconcile_item_quantities` was being called by five hot
inventory endpoints (Summary / Inventory list / Movement Analysis /
PDF export / Purchase-order draft). Each call did two full-collection
scans (`sales_vouchers` + `purchase_vouchers`, up to 50 k docs with
`items[]` arrays). For 20 k-voucher tenants that is multi-second Mongo
I/O × ~10 polls/min from the dashboard → Atlas saturation.

The fix pins the aggregation into a per-(tenant, company, fy) 60 s
TTL cache so repeated inventory polls reuse the maps instead of
re-scanning. Fresh agent writes invalidate the cache so UI never sees
stale numbers.
"""
import asyncio
import time
from types import SimpleNamespace


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _AsyncCursor:
    def __init__(self, rows): self._rows = rows
    async def to_list(self, _): return list(self._rows)


class _Coll:
    """Counts how many times `find()` was called so tests can assert
    the cache is actually taking the second hit."""
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0
    def find(self, *a, **k):
        self.calls += 1
        return _AsyncCursor(self._rows)


def _stub(monkeypatch, sales, purchases):
    import routes.inventory as inv
    s_coll = _Coll(sales)
    p_coll = _Coll(purchases)
    class _StubDb:
        def __init__(self):
            self.sales_vouchers = s_coll
            self.purchase_vouchers = p_coll
    monkeypatch.setattr(inv, "db", _StubDb())
    inv._RECONCILE_CACHE.clear()
    return s_coll, p_coll


def test_cache_hits_skip_db_on_second_call(monkeypatch):
    """First call must scan Mongo; second call for the same key must
    return from cache without touching the DB at all."""
    from routes.inventory import _get_voucher_movement_maps
    sales = [{"items": [{"item": "ABC", "quantity": 10}]}]
    purchases = [{"items": [{"item": "ABC", "quantity": 15}]}]
    s_coll, p_coll = _stub(monkeypatch, sales, purchases)

    in1, out1 = _run(_get_voucher_movement_maps("t1", "c1", None))
    assert s_coll.calls == 1 and p_coll.calls == 1
    assert in1 == {"abc": 15.0} and out1 == {"abc": 10.0}

    # Second call → must be served from cache; find() must not fire again.
    in2, out2 = _run(_get_voucher_movement_maps("t1", "c1", None))
    assert s_coll.calls == 1 and p_coll.calls == 1
    assert in2 == in1 and out2 == out1


def test_cache_scopes_by_tenant_company_fy(monkeypatch):
    """A different tenant / company / fy triplet must NOT be served
    from another triplet's cached entry — the key tuple is the whole
    primary key."""
    from routes.inventory import _get_voucher_movement_maps
    s_coll, p_coll = _stub(monkeypatch, [], [])

    _run(_get_voucher_movement_maps("t1", "c1", "2026-27"))
    _run(_get_voucher_movement_maps("t1", "c1", "2026-27"))   # cached
    _run(_get_voucher_movement_maps("t1", "c1", "2025-26"))   # new fy
    _run(_get_voucher_movement_maps("t2", "c1", "2026-27"))   # new tenant
    _run(_get_voucher_movement_maps("t1", "c2", "2026-27"))   # new company
    # 1 cache + 3 misses on sales_vouchers = 4 find() calls, same on
    # purchase_vouchers.
    assert s_coll.calls == 4
    assert p_coll.calls == 4


def test_invalidate_drops_entry_for_tenant(monkeypatch):
    """A fresh voucher batch (bulk_write in sync.py) calls
    `invalidate_reconcile_cache(tenant_id, company_id)`. The very
    next inventory read must re-fetch from Mongo so the user never
    sees stale totals."""
    from routes.inventory import _get_voucher_movement_maps, invalidate_reconcile_cache
    s_coll, p_coll = _stub(monkeypatch, [], [])

    _run(_get_voucher_movement_maps("t1", "c1", None))
    assert s_coll.calls == 1
    _run(_get_voucher_movement_maps("t1", "c1", None))  # cached
    assert s_coll.calls == 1

    invalidate_reconcile_cache("t1", "c1")
    _run(_get_voucher_movement_maps("t1", "c1", None))  # cache busted
    assert s_coll.calls == 2


def test_invalidate_tenant_wide_matches_all_companies(monkeypatch):
    """When `invalidate_reconcile_cache` is called without a company
    (older callers), every entry under that tenant must drop so no
    stale company-scoped slice survives."""
    from routes.inventory import _get_voucher_movement_maps, invalidate_reconcile_cache
    s_coll, p_coll = _stub(monkeypatch, [], [])

    _run(_get_voucher_movement_maps("t1", "cA", None))
    _run(_get_voucher_movement_maps("t1", "cB", None))
    assert s_coll.calls == 2
    invalidate_reconcile_cache("t1")  # no company → tenant-wide
    _run(_get_voucher_movement_maps("t1", "cA", None))
    _run(_get_voucher_movement_maps("t1", "cB", None))
    assert s_coll.calls == 4


def test_ttl_expiry_forces_refresh(monkeypatch):
    """After the TTL elapses the cache must silently refresh so
    long-lived processes don't serve indefinitely-old maps if a sync
    wrote directly to Mongo without going through our bulk_write
    hook (e.g. a one-off CSV import)."""
    import routes.inventory as inv
    from routes.inventory import _get_voucher_movement_maps
    s_coll, p_coll = _stub(monkeypatch, [], [])

    # Shrink TTL to effectively zero for this test.
    orig_ttl = inv._RECONCILE_TTL_SEC
    inv._RECONCILE_TTL_SEC = 0.01
    try:
        _run(_get_voucher_movement_maps("t1", "c1", None))
        assert s_coll.calls == 1
        time.sleep(0.05)
        _run(_get_voucher_movement_maps("t1", "c1", None))
        assert s_coll.calls == 2
    finally:
        inv._RECONCILE_TTL_SEC = orig_ttl


def test_sync_endpoint_imports_invalidator():
    """Guard: the sync.py write-path must still import
    `invalidate_reconcile_cache` from inventory. Protects against
    accidental refactors that would silently reintroduce stale cache."""
    src = open("/app/backend/routes/sync.py", encoding="utf-8").read()
    # Called once after each of the two bulk_writes (sales + purchases).
    assert src.count("invalidate_reconcile_cache(req_tenant_id") >= 2
