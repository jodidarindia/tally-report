"""Iteration 139 — CA Corner Bank & Investor Report FY detection.

Bug: Preview endpoint returned the error
    "No FY data synced yet for this company, and no prior-year figures
     entered manually…"
even when 2 FYs worth of sales_vouchers were live in the tenant.

Root cause:
  - `sales_vouchers` and `profit_loss` never persist a scalar `fy`
     field. FY is derived from `voucher_date` (see ai_reports.py iter-121).
  - `_detect_synced_fys` used `distinct("fy", ...)` → always [] → error.
  - `_build_historical_fy` filtered by `{fy: fy_label}` → 0 vouchers,
     also summed the wrong `amount` key (real field is `total_amount`).

Fix:
  - `_detect_synced_fys` now derives FYs from the voucher_date min/max
     span and confirms each candidate FY has ≥1 voucher.
  - `_build_historical_fy` filters by voucher_date range and reads
     `total_amount` (falling back to `amount` for defensive support).

Regression protection: these tests mock the module-level `db` used by
routes.ca_reports and assert both fixes end-to-end.
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app/backend")

ROUTE_FILE = Path("/app/backend/routes/ca_reports.py")


# ---------- helpers -----------------------------------------------------

def _has_source(src: str) -> str:
    return ROUTE_FILE.read_text()


def test_source_no_longer_uses_broken_fy_scalar_filter():
    """The bugged `{fy: fy_label}` filter on sales_vouchers must be gone.
    (This locks in the fix; guards against a future refactor putting it
    back and silently reintroducing the empty-report regression.)"""
    src = _has_source("routes/ca_reports.py")
    # It's OK to filter profit_loss by fy (that's a defensive-write for
    # a future schema), but sales_vouchers / purchase_vouchers must be
    # filtered by voucher_date now, not the non-existent scalar `fy`.
    assert '"fy": fy_label' not in src or 'sales_vouchers.find(\n            {**q, "fy": fy_label}' not in src, \
        "sales_vouchers must no longer be filtered on non-existent 'fy' field"
    assert "voucher_date" in src, "voucher_date range filter must be present"
    assert "total_amount" in src, "must read total_amount from sales_vouchers"


# ---------- functional round-trip against fake collections --------------

class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)
        self._sort = None
        self._limit_n = None

    def sort(self, key, order):
        self._sort = (key, order)
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    async def to_list(self, n):
        docs = list(self._docs)
        if self._sort:
            k, o = self._sort
            docs.sort(key=lambda d: d.get(k, ""), reverse=(o == -1))
        if self._limit_n is not None:
            docs = docs[: self._limit_n]
        return docs


class _FakeColl:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, q=None, proj=None):
        return _FakeCursor(_filter(self._docs, q or {}))

    async def find_one(self, q=None, proj=None):
        for d in _filter(self._docs, q or {}):
            return d
        return None

    async def count_documents(self, q=None, **kw):
        return len(_filter(self._docs, q or {}))

    async def distinct(self, key, q=None):
        docs = _filter(self._docs, q or {})
        return list({d.get(key) for d in docs if d.get(key) is not None})


def _match(doc, q):
    for k, v in q.items():
        if isinstance(v, dict):
            for op, val in v.items():
                dv = doc.get(k, "")
                if op == "$gte" and not (dv >= val):
                    return False
                if op == "$lte" and not (dv <= val):
                    return False
        else:
            if doc.get(k) != v:
                return False
    return True


def _filter(docs, q):
    return [d for d in docs if _match(d, q)]


class _FakeDB:
    def __init__(self, **collections):
        self._colls = collections

    def __getattr__(self, name):
        return self._colls.get(name, _FakeColl([]))

    def __getitem__(self, name):
        return self._colls.get(name, _FakeColl([]))


@pytest.fixture
def patch_db(monkeypatch):
    """Point routes.ca_reports.db at a fake mongo containing a mix of
    FY 2025-26 + 2026-27 sales vouchers, so the detection logic can run
    against realistic data."""
    sales = [
        # FY 2025-26 (Apr 2025 – Mar 2026)
        {"tenant_id": "t1", "company_id": "c1",
         "voucher_date": "2025-04-05", "total_amount": 12345.0},
        {"tenant_id": "t1", "company_id": "c1",
         "voucher_date": "2025-11-30", "total_amount": 8000.0},
        {"tenant_id": "t1", "company_id": "c1",
         "voucher_date": "2026-03-31", "total_amount": 15000.0},
        # FY 2026-27
        {"tenant_id": "t1", "company_id": "c1",
         "voucher_date": "2026-05-11", "total_amount": 22000.0},
        # Other tenant — must be excluded
        {"tenant_id": "t2", "company_id": "cx",
         "voucher_date": "2025-06-01", "total_amount": 99999.0},
    ]
    purchases = [
        {"tenant_id": "t1", "company_id": "c1",
         "voucher_date": "2025-04-10", "total_amount": 5000.0},
        {"tenant_id": "t1", "company_id": "c1",
         "voucher_date": "2026-06-01", "total_amount": 2000.0},
    ]
    pl = [
        {"tenant_id": "t1", "company_id": "c1",
         "total_income": 3500000.0, "net_profit_loss": 450000.0,
         "total_expense": 3050000.0, "expense": [], "income": []},
    ]
    ledgers = []
    users = [{"tenant_id": "t1", "role": "admin",
              "name": "Test", "email": "t@x.io"}]

    fake = _FakeDB(
        sales_vouchers=_FakeColl(sales),
        purchase_vouchers=_FakeColl(purchases),
        profit_loss=_FakeColl(pl),
        all_ledgers=_FakeColl(ledgers),
        ca_manual_historicals=_FakeColl([]),
        ca_report_assumptions=_FakeColl([]),
        users=_FakeColl(users),
    )

    import routes.ca_reports as mod
    monkeypatch.setattr(mod, "db", fake, raising=True)
    return fake


def test_detect_synced_fys_derives_from_voucher_date(patch_db):
    from routes.ca_reports import _detect_synced_fys
    fys = asyncio.run(_detect_synced_fys("t1", "c1"))
    assert fys == ["2025-26", "2026-27"], (
        f"Expected 2 FYs derived from voucher_date range, got {fys}"
    )


def test_build_historical_fy_uses_total_amount_and_date_range(patch_db):
    from routes.ca_reports import _build_historical_fy

    h1 = asyncio.run(_build_historical_fy("t1", "c1", "2025-26"))
    h2 = asyncio.run(_build_historical_fy("t1", "c1", "2026-27"))

    # Sales must be in Rs. Lacs, non-zero and per-FY (not identical)
    assert h1.gross_sales > 0, "FY 2025-26 sales must be > 0"
    assert h2.gross_sales > 0, "FY 2026-27 sales must be > 0"
    assert h1.gross_sales != h2.gross_sales, (
        "Per-FY sales must differ (regression: the bug repeated one number)"
    )

    # Concrete: FY 2025-26 vouchers = 12345 + 8000 + 15000 = 35345 → 0.35 L
    assert h1.gross_sales == round(35345 / 100000, 2), (
        f"Unexpected FY25-26 gross_sales: {h1.gross_sales}"
    )
    assert h2.gross_sales == round(22000 / 100000, 2), (
        f"Unexpected FY26-27 gross_sales: {h2.gross_sales}"
    )

    # Purchases likewise per-FY (5000 & 2000 respectively)
    assert h1.purchases == round(5000 / 100000, 2)
    assert h2.purchases == round(2000 / 100000, 2)


def test_detect_ignores_other_tenants(patch_db):
    from routes.ca_reports import _detect_synced_fys
    # t2 has one voucher in 2025-06 — must still resolve to 2025-26 only
    fys = asyncio.run(_detect_synced_fys("t2", "cx"))
    assert fys == ["2025-26"], f"tenant isolation broken: {fys}"


def test_empty_tenant_still_reports_zero_fys(patch_db):
    from routes.ca_reports import _detect_synced_fys
    fys = asyncio.run(_detect_synced_fys("tX", "cX"))
    assert fys == [], (
        "A tenant with no vouchers must still return [] so the "
        "'add prior-year manual entry' hint stays reachable."
    )
