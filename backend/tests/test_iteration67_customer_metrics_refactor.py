"""
Unit tests for services.customer_metrics — verifies the extracted helpers preserve
the legacy in-route behaviour exactly. No DB needed; pure pythonic.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from services.customer_metrics import (
    fy_start_iso, base_fy_start_iso, split_by_fy, is_payment_voucher,
    split_receipts_and_payments, filter_branch_parties,
    compute_opening_balance_map, aggregate_party_credits,
    apply_fifo_aging, aging_status,
)


def test_fy_start_iso():
    assert fy_start_iso("2024-25") == "2024-04-01"
    assert fy_start_iso("2025-26") == "2025-04-01"
    assert fy_start_iso(None) is None
    assert fy_start_iso("garbage") is None
    assert fy_start_iso("") is None


def test_base_fy_start_iso():
    # Apr/May/.../Dec → same year start
    assert base_fy_start_iso(date(2026, 5, 1)) == "2026-04-01"
    assert base_fy_start_iso(date(2026, 12, 31)) == "2026-04-01"
    # Jan/Feb/Mar → previous year start
    assert base_fy_start_iso(date(2026, 1, 15)) == "2025-04-01"
    assert base_fy_start_iso(date(2026, 3, 31)) == "2025-04-01"
    assert base_fy_start_iso(date(2026, 4, 1)) == "2026-04-01"


def test_split_by_fy_and_no_fy():
    rows = [
        {"voucher_date": "2024-03-31", "amt": 100},
        {"voucher_date": "2024-04-01", "amt": 200},
        {"voucher_date": "2024-04-02", "amt": 300},
        {"voucher_date": "", "amt": 400},  # treated as < anything
    ]
    pre, curr = split_by_fy(rows, "2024-04-01")
    assert [r["amt"] for r in pre] == [100, 400]
    assert [r["amt"] for r in curr] == [200, 300]
    # No fy_start_str → all current
    pre, curr = split_by_fy(rows, None)
    assert pre == [] and curr == rows


def test_split_receipts_and_payments():
    rows = [
        {"voucher_type": "Receipt", "amount": 10},
        {"voucher_type": "PAYMENT", "amount": 20},
        {"voucher_type": "  payment  ", "amount": 30},
        {"voucher_type": None, "amount": 40},  # treated as receipt
        {"voucher_type": "", "amount": 50},
    ]
    receipts, payments = split_receipts_and_payments(rows)
    assert [r["amount"] for r in receipts] == [10, 40, 50]
    assert [p["amount"] for p in payments] == [20, 30]


def test_is_payment_voucher():
    assert is_payment_voucher({"voucher_type": "Payment"}) is True
    assert is_payment_voucher({"voucher_type": "PAYMENT"}) is True
    assert is_payment_voucher({"voucher_type": "  payment "}) is True
    assert is_payment_voucher({"voucher_type": "Receipt"}) is False
    assert is_payment_voucher({}) is False


def test_filter_branch_parties():
    rows = [
        {"party_name": "A"},
        {"party_name": "B"},
        {"party_name": "  c  "},  # whitespace + case
        {"party_name": None},
    ]
    branch = {"a", "c"}
    out = filter_branch_parties(rows, branch)
    assert [r["party_name"] for r in out] == ["B", None]
    # Empty set short-circuits
    assert filter_branch_parties(rows, set()) == rows


def test_aging_status_thresholds():
    assert aging_status(0, 99) == ("normal", "Normal")
    assert aging_status(-100, 99) == ("normal", "Normal")  # advance
    assert aging_status(100, 91) == ("critical", "Critical")
    assert aging_status(100, 90) == ("overdue", "Overdue")  # boundary: >60 not >=
    assert aging_status(100, 61) == ("overdue", "Overdue")
    assert aging_status(100, 60) == ("at_risk", "At Risk")
    assert aging_status(100, 31) == ("at_risk", "At Risk")
    assert aging_status(100, 30) == ("normal", "Normal")
    assert aging_status(100, 0) == ("normal", "Normal")


def test_apply_fifo_aging_with_invoices():
    # Outstanding 1500 with two invoices: 1000@100d + 800@40d
    vouchers = [
        {"amount": 1000, "days_old": 100},
        {"amount": 800, "days_old": 40},
    ]
    aging, oldest = apply_fifo_aging(1500, vouchers, date(2026, 5, 8), "2025-04-01")
    # Oldest 1000 first → 90+ bucket; remaining 500 → 30-60 bucket (40 days)
    assert aging["aging_90_plus"] == 1000
    assert aging["aging_30_60"] == 500
    assert aging["aging_60_90"] == 0
    assert aging["aging_0_30"] == 0
    assert oldest == 0  # only set in fallback path


def test_apply_fifo_aging_zero_or_negative():
    aging, oldest = apply_fifo_aging(0, [{"amount": 100, "days_old": 50}], date.today(), None)
    assert aging == {"aging_0_30": 0.0, "aging_30_60": 0.0, "aging_60_90": 0.0, "aging_90_plus": 0.0}
    assert oldest == 0
    aging, _ = apply_fifo_aging(-50, [], date.today(), None)
    assert aging["aging_0_30"] == 0.0


def test_apply_fifo_aging_fallback_to_fy_start():
    # No invoices, OS > 0 → uses fy_start as anchor
    today = date(2026, 5, 8)
    aging, oldest = apply_fifo_aging(1000, [], today, "2025-04-01")
    # ~399 days from FY start → 90+ bucket
    assert aging["aging_90_plus"] == 1000
    assert oldest > 90


def test_apply_fifo_aging_remainder_drops_to_0_30():
    # Outstanding > sum of invoices → leftover goes to 0-30 bucket
    vouchers = [{"amount": 100, "days_old": 100}]
    aging, _ = apply_fifo_aging(500, vouchers, date(2026, 5, 8), "2025-04-01")
    assert aging["aging_90_plus"] == 100
    assert aging["aging_0_30"] == 400


def test_aggregate_party_credits_signed_cn():
    # Receipt + plain CN
    receipts = [{"party_name": "ALPHA TRADERS", "amount": 1000}]
    cns = [
        {"party_name": "ALPHA TRADERS", "total_amount": 200, "ledger_entries": []},
        # CN reversal where party row is is_debit → DR's the party
        {
            "party_name": "ALPHA TRADERS",
            "total_amount": 50,
            "ledger_entries": [{"ledger_name": "alpha traders", "is_debit": True}],
        },
    ]
    jvs = []  # no JV
    rec, cn_total, jv_net, jv_dr = aggregate_party_credits(receipts, cns, jvs)
    assert rec == {"alpha traders": 1000}
    # 200 (CR) - 50 (reversal) = 150 net CR
    assert cn_total == {"alpha traders": 150}
    assert jv_dr == {"alpha traders": 50}
    assert jv_net == {}


def test_compute_opening_balance_same_fy_no_replay():
    synced = [{"customer_name": "FOO", "opening_balance": 10000}]
    ob = compute_opening_balance_map(
        synced, [], [], [], [], [],
        fy_start_str="2025-04-01", base_fy_start_str="2025-04-01",
    )
    assert ob == {"FOO": 10000}


def test_compute_opening_balance_backward_replay():
    """Asking for an earlier FY → undo activity in [req, base)."""
    synced = [{"customer_name": "FOO", "opening_balance": 10000}]
    sales = [{"party_name": "FOO", "voucher_date": "2024-06-01", "total_amount": 5000}]
    receipts = [{"party_name": "FOO", "voucher_date": "2024-07-01", "amount": 2000}]
    ob = compute_opening_balance_map(
        synced, sales, receipts, [], [], [],
        fy_start_str="2024-04-01", base_fy_start_str="2025-04-01",
    )
    # OB at 2024-04-01 = 10000 (base OB) - 5000 sales + 2000 receipt = 7000
    assert ob == {"FOO": 7000}


def test_compute_opening_balance_forward_replay():
    """Asking for a later FY → forward-add activity in [base, req)."""
    synced = [{"customer_name": "FOO", "opening_balance": 10000}]
    sales = [{"party_name": "FOO", "voucher_date": "2025-06-01", "total_amount": 5000}]
    receipts = [{"party_name": "FOO", "voucher_date": "2025-07-01", "amount": 2000}]
    ob = compute_opening_balance_map(
        synced, sales, receipts, [], [], [],
        fy_start_str="2026-04-01", base_fy_start_str="2025-04-01",
    )
    # OB at 2026-04-01 = 10000 + 5000 - 2000 = 13000
    assert ob == {"FOO": 13000}


def test_compute_opening_balance_skips_unknown_party():
    """Vouchers for non-synced parties don't pollute OB."""
    synced = [{"customer_name": "FOO", "opening_balance": 10000}]
    sales = [{"party_name": "STRANGER", "voucher_date": "2024-06-01", "total_amount": 9999}]
    ob = compute_opening_balance_map(
        synced, sales, [], [], [], [],
        fy_start_str="2024-04-01", base_fy_start_str="2025-04-01",
    )
    assert ob == {"FOO": 10000}


def test_compute_opening_balance_no_fy_returns_empty():
    synced = [{"customer_name": "FOO", "opening_balance": 10000}]
    assert compute_opening_balance_map(synced, [], [], [], [], [], None, "2025-04-01") == {}


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
