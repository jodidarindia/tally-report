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


class _AggCursor:
    def __init__(self, rows): self._rows = rows
    def __aiter__(self):
        async def _gen():
            for r in self._rows:
                yield r
        return _gen()


def _run_pipeline(rows, pipeline):
    """Mimic Mongo's $match + $unwind + $group($sum) locally. Equality
    filters (tenant_id, company_id) are ignored — tests intentionally
    omit those keys from the fixture rows."""
    match = next((s["$match"] for s in pipeline if "$match" in s), {})
    def _ok(doc):
        for k, v in match.items():
            if isinstance(v, dict) and ("$gte" in v or "$lte" in v):
                val = doc.get(k, "")
                if "$gte" in v and val < v["$gte"]: return False
                if "$lte" in v and val > v["$lte"]: return False
            # Equality filters (tenant_id, company_id) — skip in stub.
        return True
    totals: dict = {}
    for doc in rows:
        if not _ok(doc): continue
        for line in (doc.get("items") or []):
            key = (line.get("item") or "").strip().lower()
            if not key: continue
            try:
                totals[key] = totals.get(key, 0.0) + float(line.get("quantity") or 0)
            except (TypeError, ValueError):
                pass
    return [{"_id": k, "qty": v} for k, v in totals.items()]


class _Coll:
    """Counts how many times `aggregate()` was called so tests can
    assert the cache is actually taking the second hit."""
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0
    def find(self, *a, **k):
        self.calls += 1
        return _AsyncCursor(self._rows)
    def aggregate(self, pipeline, **_kwargs):
        self.calls += 1
        return _AggCursor(_run_pipeline(self._rows, pipeline))


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


# ─── iter-176b — Server-side aggregation ──────────────────────────────
def test_aggregation_uses_mongo_pipeline_not_full_fetch(monkeypatch):
    """The movement maps must come from `.aggregate()` with a
    `$unwind` + `$group` pipeline — NOT a `.find() + .to_list(50000)`
    pull. If someone refactors to a Python loop again this test
    catches the regression."""
    import routes.inventory as inv
    from routes.inventory import _get_voucher_movement_maps

    captured = {"pipelines": []}

    class _AggCursor2:
        def __init__(self, rows): self._rows = rows
        def __aiter__(self):
            async def _gen():
                for r in self._rows:
                    yield r
            return _gen()

    class _Coll2:
        def find(self, *a, **k):
            raise AssertionError("`find()` must NOT be called — aggregation path required")
        def aggregate(self, pipeline, **_kwargs):
            captured["pipelines"].append(pipeline)
            return _AggCursor2([{"_id": "widget", "qty": 42.0}])

    class _StubDb:
        def __init__(self):
            self.sales_vouchers = _Coll2()
            self.purchase_vouchers = _Coll2()
    monkeypatch.setattr(inv, "db", _StubDb())
    inv._RECONCILE_CACHE.clear()

    in_qty, out_qty = _run(_get_voucher_movement_maps("t1", "c1", "2026-27"))
    assert in_qty == {"widget": 42.0} and out_qty == {"widget": 42.0}
    # Both collections hit, with pipelines that include $unwind + $group.
    assert len(captured["pipelines"]) == 2
    for pipe in captured["pipelines"]:
        kinds = [list(stage.keys())[0] for stage in pipe]
        assert "$match" in kinds
        assert "$unwind" in kinds
        assert "$group" in kinds


def test_aggregation_scopes_match_by_voucher_date_range(monkeypatch):
    """FY filter is pushed into Mongo as a `voucher_date` range match
    so it can ride the `tcid_vdate` compound index. We assert the
    pipeline's `$match` stage carries the right date bounds."""
    import routes.inventory as inv
    from routes.inventory import _get_voucher_movement_maps
    captured = {"match": None}

    class _AggCursor3:
        def __aiter__(self):
            async def _gen():
                if False: yield None  # empty async generator
            return _gen()

    class _Coll3:
        def find(self, *a, **k): raise AssertionError("find not expected")
        def aggregate(self, pipeline, **_kwargs):
            captured["match"] = next(s["$match"] for s in pipeline if "$match" in s)
            return _AggCursor3()

    class _StubDb:
        def __init__(self):
            self.sales_vouchers = _Coll3()
            self.purchase_vouchers = _Coll3()
    monkeypatch.setattr(inv, "db", _StubDb())
    inv._RECONCILE_CACHE.clear()

    _run(_get_voucher_movement_maps("tX", "cY", "2026-27"))
    m = captured["match"]
    assert m["tenant_id"] == "tX"
    assert m["company_id"] == "cY"
    assert m["voucher_date"] == {"$gte": "2026-04-01", "$lte": "2027-03-31"}


def test_startup_creates_tcid_fy_index():
    """Guard against someone removing the `tcid_fy` compound index
    the audit introduced. It covers `fy`-literal filters that the
    aggregation path doesn't use directly but many analytics
    routes still do."""
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "name='tcid_fy'" in src
    assert "('tenant_id', 1), ('company_id', 1), ('fy', 1)" in src
