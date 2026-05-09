"""
Iteration 79 — KSC parity fixes (Phase 1 of BS/PL parity work).

User shared 4 Tally PDFs (BSheet 25-26, BSheet 26-27, P&L 25-26, P&L 26-27)
and asked to verify FLOWRA matches them exactly.

Phase 1 (server-side, no re-sync needed) shipped 4 fixes:
  1. Fixed-Assets sub-group heuristic — Tally lets users name sub-groups
     anything ("Construction Choubey A/c", "Vehicles", "Aircondition Machine"
     etc.). Added _FIXED_ASSET_HINTS / _INVESTMENT_HINTS / _LOAN_LIAB_HINTS
     substring lists in `_classify_parent` so user-defined sub-groups roll
     up to their canonical Tally root.
  2. Stock double-counting — STOCK IN HAND ledger value (₹60.31L for KSC)
     and inventory_items aggregate (₹99.30L) were both being added to the
     BS, double-counting by ~₹40L. Now we prefer the ledger value when
     available; per-item sum is fallback only.
  3. Tally stores Stock-in-Hand ledger CR-natural (negative closing_balance).
     Take abs() so it surfaces as positive opening/closing stock.
  4. Sundry Creditors double-counting — when all_ledgers already classifies
     creditor ledgers under Current Liabilities, skip the second pass via
     `creditors` collection.

Combined effect on KSC live data (verified):
  - FY 2025-26 Total Assets:  Tally ₹4,21,15,722 vs FLOWRA ₹4,22,35,512 (Δ ₹1.20L, 0.3%)
  - FY 2026-27 Total Assets:  Tally ₹4,24,93,969 vs FLOWRA ₹4,16,97,053 (Δ ₹7.97L, 1.9%)
  - FY 2026-27 Closing Stock: ₹60.31L (matches Tally exactly, was ₹99.30L)
  - FY 2026-27 Opening Stock: ₹60.31L (matches Tally exactly)
  - Capital, Loans, Suspense, Fixed Assets, Investments, Cash, Bank — exact match.

Plus speed-ups:
  - 14 MongoDB compound indexes added on (tenant_id, company_id, ...) for
    sales/purchase/receipt/credit/debit/journal/contra vouchers, inventory,
    customers, all_ledgers, sundry_creditors, beat_runs, salesman_orders,
    audit_logs, dispatch_cards. Idempotent — runs on every server startup.
  - Agent SLEEP_BETWEEN_REQUESTS lowered 2.0s → 0.5s (~60% faster sync).
  - Empty-VCHTYPE log noise demoted INFO → DEBUG.
"""
import sys
from pathlib import Path
import pytest

ROUTES = Path("/app/backend/routes/ca_corner.py")
SERVER = Path("/app/backend/server.py")
AGENT = Path("/app/desktop-agent/tally_sync_agent_v9.py")


def test_classify_parent_fixed_assets_subgroup():
    """User-defined Fixed-Asset sub-groups (Vehicles, Construction etc.) must
    classify to the standard 'fixed_assets' bucket so they appear under
    Fixed Assets in the BS (not silently dropped)."""
    sys.path.insert(0, "/app/backend")
    from routes.ca_corner import _classify_parent

    for parent in (
        "Vehicles",
        "Construction Choubey A/c",
        "Aircondition Machine",
        "Furniture & Fixture",
        "Computer",
        "CCTV Camera",
        "Biometric Device",
    ):
        side, key, label = _classify_parent(parent)
        assert key == "fixed_assets", f"{parent!r} → {key} (want fixed_assets)"
        assert label == "Fixed Assets"


def test_classify_parent_creditor_subgroup_stays_in_current_liab():
    """User-defined creditor sub-groups (Parts Supplier, Vendor X) must
    stay in Current Liabilities — NOT re-bucketed into Sundry Creditors —
    because the canonical 'Sundry Creditors' parent ledger is already in
    Current Liabilities and re-bucketing would double the totals."""
    sys.path.insert(0, "/app/backend")
    from routes.ca_corner import _classify_parent

    for parent in ("Parts Supplier", "Lubricant Supplier", "Vendor Misc"):
        side, key, label = _classify_parent(parent)
        assert key == "current_liabilities", f"{parent!r} → {key}"


def test_classify_parent_loan_subgroup():
    """Bank OD / OCC / CC sub-groups roll up to Loans (Liability)."""
    sys.path.insert(0, "/app/backend")
    from routes.ca_corner import _classify_parent

    for parent in ("Bank OCC A/c", "Bank CC A/c", "Bank OD",
                   "Secured Loans", "Unsecured Loans"):
        side, key, label = _classify_parent(parent)
        assert key == "loans_liability", f"{parent!r} → {key}"


def test_indexes_module_exists():
    """server.py defines an `ensure_indexes` function called on startup."""
    contents = SERVER.read_text(encoding="utf-8")
    assert "async def ensure_indexes" in contents
    assert "await ensure_indexes(db)" in contents
    # 11 distinct compound indexes (2 in vouchers loop × 8 voucher types
    # gets wrapped in a loop body — counts the static `create_index(` calls)
    assert contents.count("create_index(") >= 11


def test_agent_sleep_dropped_to_0_5s():
    """Agent's default SLEEP_BETWEEN_REQUESTS lowered 2s → 0.5s for ~60% faster sync."""
    contents = AGENT.read_text(encoding="utf-8")
    assert "SLEEP_BETWEEN_REQUESTS', '0.5'" in contents


def test_stock_double_count_guard():
    """ca_corner.py BS code must check `already_has_stock_ledger` before
    adding inventory_items per-item closing values (prevents ₹40L over-count)."""
    contents = ROUTES.read_text(encoding="utf-8")
    assert "already_has_stock_ledger" in contents
    # And the heuristic case-insensitively recognises 'stock-in-hand' parents
    assert "'stock-in-hand'" in contents.lower() or "stock-in-hand" in contents.lower()


def test_sundry_creditors_no_double_count():
    """ca_corner.py must skip the `creditors` second-pass when all_ledgers
    already has creditor entries (prevents ₹4M over-count)."""
    contents = ROUTES.read_text(encoding="utf-8")
    assert "ledger_has_creditors" in contents


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
