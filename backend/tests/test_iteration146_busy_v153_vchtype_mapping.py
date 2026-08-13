"""Iteration 146 — Busy Agent v1.5.3 · VchType mapping corrected.

User bug: after v1.5.2 shipped, live sync showed
    journal_vouchers: 0, purchase_vouchers: 0, contra_vouchers: 0,
    debit_notes: 0
even though the customer confirmed that "data exist for journal, purchase,
contra". Traced against the real COMP0002 (NAVDURGA AUTO) licensed Busy 21
Tran1 VchType distribution:

    9  Sale             1,774
    2  Purchase           467   ← v1.5.1/1.5.2 was hitting VchType=7 (empty)
    14 Receipt         1,446   ← was hitting VchType=1,3 (empty / mis-mapped)
    16 Payment           431   ← MISSING entirely from the extractor
    19 Contra            568   ← was hitting VchType=6 (empty)
    10 Credit Note        38
    12 Debit Note          1   ← was hitting VchType=8,11 (empty)
    4  Journal             3   ← was hitting VchType=5 (empty)
    17 Rate-Diff-on-Sale   5   ← now folded into credit_notes
    18 Discount-on-Sale   52   ← now folded into credit_notes
    15 Stock Journal      29
    3  Sales adjustment   16   ← now emitted separately as sundry_journals

The v1.5.1/1.5.2 map was Busy Demo defaults; live licensed builds
renumber the VchType codes. v1.5.3 wires the correct numbers.

Also added:
  • `extract_payments` — brand-new voucher category (VchType=16) so
    bank-outflows land in their own collection.
  • `extract_sundry_journals` — sale-adjustment / rounding vouchers
    kept isolated so P&L doesn't double-count them.
  • Backend `data_type='payment_vouchers'` and `'sundry_journals'`
    handlers to persist the new payloads.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app/desktop-agent/build-kit-busy")
REAL_DB_ROOT = Path("/tmp/comp0002/unpacked/COMP0002")
REAL_DB_AVAILABLE = (REAL_DB_ROOT / "db12025.bds").exists()

AGENT_SRC = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()


# ---------------------------------------------------------------------------
# 1. Source-scan fences — VchType numbers hard-coded correctly
# ---------------------------------------------------------------------------

def test_purchase_vchtype_is_2():
    """v1.5.1/1.5.2 pointed extract_purchases at VchType=7 (empty in
    licensed Busy). Real code is 2."""
    idx = AGENT_SRC.find("def extract_purchases")
    body = AGENT_SRC[idx: idx + 400]
    assert "self._extract_vouchers_by_type(fy, 2)" in body, \
        "extract_purchases must point at VchType=2 (real Busy 21 purchase)"


def test_receipts_vchtype_is_14():
    idx = AGENT_SRC.find("def extract_receipts")
    body = AGENT_SRC[idx: idx + 400]
    assert "self._extract_vouchers_by_type(fy, 14)" in body


def test_journals_vchtype_is_4():
    idx = AGENT_SRC.find("def extract_journals")
    body = AGENT_SRC[idx: idx + 400]
    assert "self._extract_vouchers_by_type(fy, 4)" in body


def test_contra_vchtype_is_19():
    idx = AGENT_SRC.find("def extract_contra")
    body = AGENT_SRC[idx: idx + 400]
    assert "self._extract_vouchers_by_type(fy, 19)" in body


def test_debit_notes_vchtype_is_12():
    idx = AGENT_SRC.find("def extract_debit_notes")
    body = AGENT_SRC[idx: idx + 400]
    assert "self._extract_vouchers_by_type(fy, 12)" in body


def test_payments_extractor_exists_and_points_to_16():
    """v1.5.3 adds a dedicated Payment voucher extractor (VchType=16).
    Regression fence: it must exist AND land in the daemon's sync_phases."""
    assert "def extract_payments" in AGENT_SRC
    idx = AGENT_SRC.find("def extract_payments")
    body = AGENT_SRC[idx: idx + 400]
    assert "self._extract_vouchers_by_type(fy, 16)" in body
    # Wired into sync_phases so the daemon syncs it
    assert '"payment_vouchers"' in AGENT_SRC


def test_credit_notes_covers_all_credit_side_adjustments():
    """v1.5.3 folds VchType 10 + 17 (rate-diff) + 18 (discount) into
    credit_notes so downstream analytics see the full customer-balance
    reduction picture."""
    idx = AGENT_SRC.find("def extract_credit_notes")
    body = AGENT_SRC[idx: idx + 500]
    for vt in ("10", "17", "18"):
        assert vt in body, f"credit_notes must include VchType={vt}"


def test_sundry_journals_extractor_exists():
    assert "def extract_sundry_journals" in AGENT_SRC
    assert '"sundry_journals"' in AGENT_SRC


# ---------------------------------------------------------------------------
# 2. Backend router accepts the two new voucher categories
# ---------------------------------------------------------------------------

def test_backend_accepts_payment_vouchers():
    src = Path("/app/backend/routes/sync.py").read_text()
    assert "data_type == 'payment_vouchers'" in src
    assert "db.payment_vouchers" in src


def test_backend_accepts_sundry_journals():
    src = Path("/app/backend/routes/sync.py").read_text()
    assert "data_type == 'sundry_journals'" in src
    assert "db.sundry_journals" in src


# ---------------------------------------------------------------------------
# 3. Real-DB smoke — the numbers actually align with the user's data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_extractor():
    if not REAL_DB_AVAILABLE:
        pytest.skip("Real Busy 21 sample DB not present")
    from flowra_busy_agent import BusyDataExtractor
    return BusyDataExtractor(str(REAL_DB_ROOT))


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_purchases_now_non_zero(real_extractor):
    """User bug: 'purchase_vouchers: 0'. Real DB has 467."""
    n = sum(1 for _ in real_extractor.extract_purchases("2025-26"))
    assert n > 400, f"Expected 400+ purchases in FY25-26, got {n}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_receipts_now_reflect_all_customer_payments(real_extractor):
    """User bug: 'receipts: 16'. Real DB has ~1,446."""
    n = sum(1 for _ in real_extractor.extract_receipts("2025-26"))
    assert n > 1000, f"Expected 1000+ receipts in FY25-26, got {n}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_contra_now_non_zero(real_extractor):
    """User bug: 'contra_vouchers: 0'. Real DB has ~568."""
    n = sum(1 for _ in real_extractor.extract_contra("2025-26"))
    assert n > 400, f"Expected 400+ contra in FY25-26, got {n}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_journals_now_non_zero(real_extractor):
    """User bug: 'journal_vouchers: 0'. Real DB has 3 in this small sample."""
    n = sum(1 for _ in real_extractor.extract_journals("2025-26"))
    assert n >= 3, f"Expected 3+ journals, got {n}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_payments_extractor_yields_records(real_extractor):
    """v1.5.3 adds Payments (VchType=16). Real DB has ~431."""
    n = sum(1 for _ in real_extractor.extract_payments("2025-26"))
    assert n > 400, f"Expected 400+ payments in FY25-26, got {n}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_debit_notes_non_zero_when_present(real_extractor):
    n = sum(1 for _ in real_extractor.extract_debit_notes("2025-26"))
    # DB has 1 debit note. Test tolerates 0..few — the point is the
    # extractor didn't silently miss it because of the wrong VchType.
    assert n >= 1, f"Expected 1+ debit note, got {n}"


@pytest.mark.skipif(not REAL_DB_AVAILABLE,
                    reason="Real Busy 21 sample DB not present")
def test_real_db_credit_notes_include_rate_diff_and_discount(real_extractor):
    """v1.5.3 folds VchType 10 + 17 + 18 → credit_notes. Expected
    total = 38 + 5 + 52 = ~95."""
    n = sum(1 for _ in real_extractor.extract_credit_notes("2025-26"))
    assert n > 70, f"Expected 70+ credit adjustments, got {n}"
