"""Iteration 152 — Busy Agent v1.5.7 invoice fields + line math + fy tags.

Locks the fixes for the user's second pass of complaints:
  • Sales-voucher item lines were storing `amount = rate` (from Busy
    D6 which turned out to be a duplicate of the rate column, not the
    net line amount). Sold-price analytics collapsed. v1.5.7 computes
    `amount = qty * rate` and derives per-line discount from
    `max(mrp − rate, 0) * qty`.
  • `discount` field was pulling D5 which is not a plain discount value
    — v1.5.7 emits a properly derived rupee discount instead.
  • Every voucher now carries a top-level `fy` field so CA-Corner's
    cash-flow / balance-sheet FY selector isn't identical between FY.
  • Voucher `reference_number` now reads Tran1.`RefNo`/`RefNoAlpha`
    (external counterparty ref), falling back to `voucher_number` when
    Busy didn't record a separate reference.
  • Customer outstanding balance now emits `outstanding_amount` and a
    real Master1.D1 `opening_balance` (was hard-coded to 0.0).
  • Creditors receive closing_balance + outstanding_amount + fy.
  • Backend sync handlers for receipts / payment / journals / stock /
    purchase / debit / credit / sundry_journal / sundry_creditors now
    persist `fy` + `voucher_number` + `reference_number` from the
    incoming payload.
  • Backend Pydantic models (`SalesVoucher`, `InventoryItem`) accept
    optional `fy` — Tally-safe (existing Tally payload has no `fy`, it
    just stays None on those rows).
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, "/app/desktop-agent/build-kit-busy")
sys.path.insert(0, "/app/backend")


# ─── 1) Sales-voucher item line math ───
def test_voucher_item_line_amount_is_qty_times_rate():
    """The extractor MUST compute amount = qty * rate. Previously it
    read D6 which is a duplicate of the rate column → collapsed the
    'avg sale price' analytic to 1/qty of its real value."""
    from flowra_busy_agent import BusyDataExtractor

    class _FakeReader:
        def __init__(self, rows): self._rows = rows
        def iter_rows(self, tbl):
            for r in self._rows.get(tbl, []):
                yield r
        def close(self): pass
        def count_rows(self, tbl): return len(self._rows.get(tbl, []))

    tran2 = [{
        "VchType": "9", "VchCode": "V1", "RecType": "2",
        "MasterCode1": "IT-1", "MasterCode2": "WH-1",
        "D1": "5",       # qty
        "D2": "2008.47", # rate
        "D3": "2008.47",
        "D4": "3060",    # MRP
        "D5": "11849.99", # noisy Busy slot — must NOT surface as discount
        "D6": "2008.47", # NOT net amount (Busy 21 empirical)
        "D9": "30", "D10": "918",
        "ShortNar": "",
    }]
    tran1 = [{
        "VchType": "9", "VchCode": "V1",
        "MasterCode1": "PARTY-1", "Date": "07/13/26",
        "VchNo": "NAV/628/26-27",
        "RefNoAlpha": "CUST-PO-42",
        "VchAmtBaseCur": "10960",
    }]
    fake = _FakeReader({"Tran1": tran1, "Tran2": tran2})

    ex = BusyDataExtractor.__new__(BusyDataExtractor)
    ex.data_folder = "/tmp"
    ex._fy_dbs = {"2025-26": "/tmp/fake.bds"}
    ex._reader_pool = {}
    ex._code_map = {}
    ex._group_map = {}
    ex._parent_map = {}
    ex._load_code_map = lambda fy: None
    ex._resolve_name = lambda code: f"NAME-{code}"
    ex._parse_date = lambda raw: "2026-07-13"
    ex._get_reader = lambda _p: fake

    vouchers = list(ex._extract_vouchers_by_type("2025-26", 9))
    assert len(vouchers) == 1
    v = vouchers[0]
    assert len(v["items"]) == 1
    it = v["items"][0]
    # KEY assertions:
    assert it["quantity"] == 5.0
    assert it["rate"] == 2008.47
    assert it["amount"] == round(5.0 * 2008.47, 2), (
        f"line amount must be qty*rate, got {it['amount']!r}"
    )
    # discount = qty * max(MRP - rate, 0)
    assert it["discount"] == round(5.0 * (3060 - 2008.47), 2), (
        f"discount must be qty*(mrp-rate), got {it['discount']!r}"
    )
    # NO trace of the spurious D5 value
    assert it["discount"] != 11849.99
    # FY on the voucher itself
    assert v["fy"] == "2025-26"
    # reference_number reads RefNoAlpha (customer PO), NOT the invoice number.
    assert v["reference_number"] == "CUST-PO-42"
    assert v["voucher_number"] == "NAV/628/26-27"


# ─── 2) voucher_number fallback when RefNo empty ───
def test_reference_number_falls_back_to_voucher_number():
    from flowra_busy_agent import BusyDataExtractor

    class _FakeReader:
        def __init__(self, rows): self._rows = rows
        def iter_rows(self, tbl):
            for r in self._rows.get(tbl, []):
                yield r
        def close(self): pass
        def count_rows(self, tbl): return len(self._rows.get(tbl, []))

    tran1 = [{
        "VchType": "9", "VchCode": "V2",
        "MasterCode1": "P", "Date": "07/13/26",
        "VchNo": "NAV/629/26-27",
        # No RefNo / RefNoAlpha
        "VchAmtBaseCur": "1000",
    }]
    fake = _FakeReader({"Tran1": tran1, "Tran2": []})

    ex = BusyDataExtractor.__new__(BusyDataExtractor)
    ex.data_folder = "/tmp"
    ex._fy_dbs = {"2025-26": "/tmp/x.bds"}
    ex._reader_pool = {}
    ex._code_map = {}
    ex._group_map = {}
    ex._parent_map = {}
    ex._load_code_map = lambda fy: None
    ex._resolve_name = lambda code: "n"
    ex._parse_date = lambda raw: "2026-07-13"
    ex._get_reader = lambda _p: fake

    vouchers = list(ex._extract_vouchers_by_type("2025-26", 9))
    assert vouchers[0]["reference_number"] == "NAV/629/26-27", (
        "reference_number should fall back to VchNo when RefNo is empty"
    )


# ─── 3) Customer emits outstanding_amount + real opening_balance ───
def test_extract_customer_outstanding_and_opening():
    """v1.5.7 — Sundry Debtors emit outstanding_amount = closing_balance
    (so CRM Outstanding tab renders) AND opening_balance from Master1.D1
    (was hard-coded 0.0)."""
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    # The updated block must set `opening` from D1 and emit outstanding_amount.
    assert 'opening = float(row.get("D1") or 0)' in src, (
        "customer extractor must read opening from Master1.D1"
    )
    assert '"outstanding_amount": closing,' in src, (
        "customer extractor must emit outstanding_amount"
    )
    assert '"fy": fy,' in src, "extractor must emit fy on customers"


# ─── 4) Creditors extractor emits closing balance + fy ───
def test_extract_creditors_now_emits_balances():
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    # Search inside `extract_creditors` block.
    m = re.search(
        r"def extract_creditors\(self, fy: str\).*?def extract_inventory_items",
        src, re.S,
    )
    assert m, "extract_creditors not found"
    body = m.group(0)
    for needle in ('"closing_balance": closing,',
                   '"outstanding_amount": closing,',
                   '"fy": fy,'):
        assert needle in body, f"creditors block missing {needle!r}"


# ─── 5) Backend voucher handlers persist fy + reference_number ───
def test_backend_voucher_handlers_persist_fy():
    """Guard: every voucher handler in sync.py that we just patched
    persists an `fy` field. Regression check locks in the ingest
    changes across receipts / payment / sundry-journal / credit-note /
    journal / stock / purchase / debit."""
    src = Path("/app/backend/routes/sync.py").read_text()
    # Look for the specific literal we added.
    # Each patched handler carries: "fy": xx.get('fy') or financial_year or '',
    assert src.count("or financial_year or ''") >= 8, (
        "expected ≥ 8 handlers persisting fy from payload / request; "
        f"found {src.count('or financial_year or ''')}"
    )


def test_sales_and_inventory_models_accept_fy():
    from models import SalesVoucher, InventoryItem
    # SalesVoucher accepts optional fy.
    sv = SalesVoucher(voucher_id="V", voucher_date="2026-07-13",
                      party_name="X", total_amount=100.0, fy="2025-26")
    assert sv.fy == "2025-26"
    # And works without fy (Tally payload path).
    sv2 = SalesVoucher(voucher_id="V2", voucher_date="d",
                       party_name="Y", total_amount=1.0)
    assert sv2.fy is None
    # InventoryItem accepts optional fy.
    ii = InventoryItem(item_id="I", item_name="N", quantity=1, unit="P", fy="2026-27")
    assert ii.fy == "2026-27"


# ─── 6) Version bumped ───
def test_version_bumped_to_157():
    import importlib
    import flowra_busy_agent
    importlib.reload(flowra_busy_agent)
    assert flowra_busy_agent.VERSION == "1.5.7"
    assert flowra_busy_agent.AGENT_TAG.startswith("busy-1.5.7")


def test_gui_version_matches_157():
    gui_src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py").read_text()
    m = re.search(r'^APP_VERSION\s*=\s*"v([\d.]+)"', gui_src, re.M)
    assert m and m.group(1) == "1.5.7"
