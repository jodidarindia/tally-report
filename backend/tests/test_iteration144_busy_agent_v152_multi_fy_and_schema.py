"""Iteration 144 — Busy Agent v1.5.2 · Multi-FY + Schema Corrections.

User bug report (Aug 13 2026):
    "only one FY fetched, it must fetch all fy from the selected till current"
    "sales invoice table not fetched properly, not data out seen"
    "inventory all fields not fetched, cost and sales price missing,
     inventory analytics table completely messed up"
    "in sales frequency tab it is showing rounded up ledger instead of
     stock items"
    "ca corner, insider results, almost all features are not giving
     output due to missing data"

RCA (four stacked bugs, all fixed in v1.5.2):

1. Multi-FY sync — daemon loop synced ONLY the single `start_fy` on
   every tick. Users starting from 2024-25 never saw 2025-26 or 2026-27.

2. Sales invoice items — Tran2 RecType flag semantics were flipped in
   v1.5.1. Real licensed Busy 21:
       RecType=2 → stock item lines (was incorrectly treated as ledgers)
       RecType=1 → ledger postings (was missed entirely)
       RecType=3 → rounding/adjustment ledgers (was treated as items)
   Consequence: every sale showed "Rounded Off (+)" or empty items list,
   ledger entries were SKU codes.

3. Inventory field mapping — `Master1.Name` is the SKU code (e.g.
   "10039927AA") and `Master1.Alias` is the human name (e.g. "SARTHI
   Engine Oil 1 LTR"). The v1.5.1 extractor put Name into `item_name`,
   making Sales Frequency and Inventory tabs unreadable. Also `D1` was
   used as price (always 1.0 for every item) — real prices had to be
   derived from voucher line rates.

4. Sales Frequency showed ledger names — downstream consequence of
   bug 2 above.

Fixes shipped:
  • `_fys_from_start(available, start_fy)` helper + daemon loop iterates
    all FYs ≥ start_fy on every tick.
  • `_extract_vouchers_by_type` RecType mapping corrected + line items
    now expose qty, rate, MRP, discount, GST%, GST amount, warehouse,
    item_code. Voucher payload also carries `busy_doc_link` (Google
    Drive URL Busy stores per invoice) and `busy_doc_name`.
  • `extract_inventory_items` reads Alias (human name) and Name (SKU),
    HSN, computed sale_price/cost_price from voucher line rates in the
    same FY, and quantity from Folio1 D11..D50 (max non-value slot).
  • `_load_code_map` now prefers Alias for MasterType=6 (items), so
    every downstream `_resolve_name(item_code)` returns the human name.

Regression tests below run against the actual COMP0002 (NAVDURGA AUTO)
licensed Busy 21 DB the user provided.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app/desktop-agent/build-kit-busy")

REAL_DB_ROOT = Path("/tmp/comp0002/unpacked/COMP0002")
REAL_DB_AVAILABLE = (REAL_DB_ROOT / "db12025.bds").exists()


@pytest.fixture(scope="module")
def real_extractor():
    """Shared BusyDataExtractor for all real-DB tests. Building the
    price map costs ~60s per FY (streams Tran2), so we build once and
    reuse the caches across the whole test module."""
    if not REAL_DB_AVAILABLE:
        pytest.skip("Real Busy 21 sample DB not present")
    from flowra_busy_agent import BusyDataExtractor
    ext = BusyDataExtractor(str(REAL_DB_ROOT))
    # Warm the caches
    list(ext.extract_inventory_items("2025-26"))
    return ext


# ---------------------------------------------------------------------------
# 1. Multi-FY resolver — independent unit test (no DB needed)
# ---------------------------------------------------------------------------

def test_fys_from_start_returns_all_fys_from_selected():
    from flowra_busy_agent import _fys_from_start
    avail = ["2025-26", "2026-27"]
    assert _fys_from_start(avail, "2024-25") == ["2025-26", "2026-27"]
    assert _fys_from_start(avail, "2025-26") == ["2025-26", "2026-27"]
    assert _fys_from_start(avail, "2026-27") == ["2026-27"]


def test_fys_from_start_stable_ordering():
    """Result must always be chronologically ordered, regardless of
    the order `available` came in."""
    from flowra_busy_agent import _fys_from_start
    assert _fys_from_start(["2026-27", "2025-26"], "2024-25") == \
        ["2025-26", "2026-27"]


def test_fys_from_start_empty_available():
    from flowra_busy_agent import _fys_from_start
    assert _fys_from_start([], "2025-26") == []


def test_fys_from_start_malformed_start_fy_returns_all():
    """A garbled start_fy must not silently drop the whole queue."""
    from flowra_busy_agent import _fys_from_start
    # start_fy of "" resolves to _fy_key = -1; every real FY is > -1
    # → every FY passes the filter.
    assert _fys_from_start(["2025-26", "2026-27"], "") == \
        ["2025-26", "2026-27"]


def test_daemon_calls_multi_fy_helper():
    """Source-scan fence: the daemon body must invoke `_fys_from_start`
    to guarantee multi-FY sync on every tick."""
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    daemon_start = src.find("def run_daemon")
    daemon_body = src[daemon_start: daemon_start + 6000]
    assert "_fys_from_start" in daemon_body, \
        "daemon loop must call _fys_from_start"
    assert "for fy in fys_to_sync" in daemon_body, \
        "daemon must iterate the queued FYs (not just start_fy)"


# ---------------------------------------------------------------------------
# 2. Voucher RecType classification — corrected in v1.5.2
# ---------------------------------------------------------------------------

def test_voucher_rectype_mapping_is_corrected():
    """v1.5.1 had item_entries = RecType==3 and ledger_entries = RecType==2.
    Real Busy 21 has RecType=2 → items, RecType=1 → ledgers. Confirm the
    source now reflects this."""
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    fn_start = src.find("def _extract_vouchers_by_type")
    fn_body = src[fn_start: fn_start + 6000]
    assert 'item_entries = [i for i in line_items if i["rec_type"] == "2"]' in fn_body
    assert 'ledger_entries = [i for i in line_items if i["rec_type"] == "1"]' in fn_body


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_sales_vouchers_have_non_empty_items_list(real_extractor):
    ext = real_extractor
    sales = list(ext.extract_sales("2025-26"))
    assert len(sales) > 1000, f"Expected 1000+ sales in FY25-26 sample, got {len(sales)}"
    non_empty = [s for s in sales if s.get("items")]
    # Every real sales voucher has line items; empty implies broken JOIN.
    coverage = len(non_empty) / len(sales)
    assert coverage > 0.95, (
        f"Only {coverage:.0%} of sales have items — RecType JOIN broken. "
        f"Expected >95%.")


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_sales_voucher_items_carry_real_item_names_not_ledgers(real_extractor):
    """User bug: 'sales frequency tab is showing rounded up ledger
    instead of stock items'. Regression fence: item_name in the items
    array must NOT contain accounting ledger words like 'Rounded Off',
    'Sales', 'IGST', 'CGST', 'SGST' — those belong to ledger_entries."""
    ext = real_extractor
    forbidden = {"rounded off", "rounded off (+)", "rounded off (-)",
                 "sales", "igst output", "cgst output", "sgst output",
                 "cash", "bank"}
    checked = 0
    for v in ext.extract_sales("2025-26"):
        for it in v.get("items", []):
            checked += 1
            name_lc = (it["item_name"] or "").lower().strip()
            assert name_lc not in forbidden, (
                f"Ledger '{it['item_name']}' leaking into items[] on "
                f"voucher {v['voucher_number']}")
        if checked > 500:      # spot-check enough to catch a regression
            break
    assert checked > 100, "Should have inspected >100 item rows"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_sales_voucher_ledger_entries_are_accounting_ledgers(real_extractor):
    """Complement of the above: ledger_entries[] MUST include names
    like 'Sales', 'IGST Output', 'Rounded Off', and the party — the
    accounting side of the double entry."""
    ext = real_extractor
    sales = list(ext.extract_sales("2025-26"))
    v = next(s for s in sales if len(s["ledger_entries"]) >= 3)
    names = [e["ledger_name"].lower() for e in v["ledger_entries"]]
    # At least one must contain "sales" (the credit ledger)
    assert any("sales" in n for n in names), (
        f"No 'Sales' ledger in ledger_entries for voucher {v['voucher_number']}: {names}")


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_sales_voucher_carries_busy_doc_link(real_extractor):
    """v1.5.2 exposes Busy's per-voucher Google Drive PDF URL so the
    FLOWRA UI can offer a 'View invoice PDF' button."""
    ext = real_extractor
    for v in ext.extract_sales("2025-26"):
        if v.get("busy_doc_link"):
            assert v["busy_doc_link"].startswith("https://drive.google.com/")
            return
    pytest.fail("Not a single sale exposed a busy_doc_link")


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_voucher_id_is_fy_scoped(real_extractor):
    """v1.5.2 — voucher_id must embed the FY tag so multi-FY syncs
    don't overwrite each other's records in Mongo. Regression fence
    for the iter-145 backend audit finding."""
    ext = real_extractor
    first = next(iter(ext.extract_sales("2025-26")))
    assert first["voucher_id"].startswith("BUSY-2025-26-"), \
        f"voucher_id must be FY-scoped, got: {first['voucher_id']!r}"


# ---------------------------------------------------------------------------
# 3. Inventory extractor — Alias, HSN, sale/cost, quantity
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_inventory_extractor_returns_human_names_and_prices(real_extractor):
    ext = real_extractor
    items = list(ext.extract_inventory_items("2025-26"))
    assert len(items) > 10000, "Expected ~10,630 items in the sample DB"

    # Every item must have an item_name; SKU codes and human names both
    # populated. Item 1288 (SARTHI Engine Oil 1 LTR) is the flagship
    # smoke-test row — the exact schema mismatch we found in v1.5.1.
    sarthi = next((i for i in items if i["item_id"] == "1288"), None)
    assert sarthi is not None, "Item code 1288 missing"
    assert sarthi["item_name"] == "SARTHI Engine Oil 1 LTR"
    assert sarthi["sku_code"] == "10039927AA"
    assert sarthi["hsn_code"] == "271019"
    assert sarthi["closing_qty"] > 0
    assert sarthi["sale_price"] > 0, \
        "sale_price should be back-derived from a sale voucher rate"
    assert sarthi["cost_price"] > 0, \
        "cost_price should be back-derived from a purchase voucher rate"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_inventory_price_and_qty_coverage_reasonable(real_extractor):
    """At least a healthy chunk of items must have prices and quantities.
    Real COMP0002 numbers: ~25% priced, ~25% with quantity."""
    ext = real_extractor
    items = list(ext.extract_inventory_items("2025-26"))
    priced = sum(1 for i in items if i["sale_price"] > 0)
    stocked = sum(1 for i in items if i["closing_qty"] > 0)
    # Regression fence: previously priced ≈ 100% at price=1.0 (bogus D1)
    # and stocked ≈ 3%. Now priced comes from real rates and stocked
    # reflects Folio1 balances properly.
    assert priced > 1000, f"Expected 1000+ priced items, got {priced}"
    assert stocked > 1000, f"Expected 1000+ stocked items, got {stocked}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_code_map_returns_alias_for_items(real_extractor):
    """The code map is what `_resolve_name(item_code)` returns to voucher
    items. Must return the human Alias for MasterType=6 items."""
    ext = real_extractor
    ext._load_code_map("2025-26")
    # Item 1288 = SARTHI Engine Oil 1 LTR (alias). Not the SKU code.
    assert ext._code_map.get("1288") == "SARTHI Engine Oil 1 LTR"


# ---------------------------------------------------------------------------
# 4. Sales frequency (downstream) — real item names dominate the top-N
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_top_sold_items_are_real_products_not_ledgers(real_extractor):
    """Emulates the Sales Frequency tab's aggregation. Top-10 items by
    invoice-count must be REAL product names, not accounting ledgers."""
    from collections import Counter
    ext = real_extractor
    freq = Counter()
    for v in ext.extract_sales("2025-26"):
        for it in v.get("items", []):
            freq[it["item_name"]] += 1
    top10 = freq.most_common(10)
    assert top10, "Sales frequency empty — item extraction still broken"
    forbidden = {"rounded off", "sales", "igst output"}
    for name, _ in top10:
        assert name.lower().strip() not in forbidden, (
            f"Ledger '{name}' in top-10 sales frequency — extractor broken")
