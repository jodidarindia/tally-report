"""
customer_metrics.py — Pure-math helpers for customer outstanding & payment-behavior.

These were extracted out of routes/customers.py to remove a ~600-line duplicate setup
between get_customer_outstanding() and get_payment_behavior(). Behaviour preserving:
every helper here is a verbatim move of logic that was previously inline, with the only
change being parameterisation. Keep this module pure (no DB, no FastAPI) so it can be
unit-tested in isolation.
"""
from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from utils import safe_num, safe_str, get_jv_party_amount


# ── FY helpers ──────────────────────────────────────────────────────────────

def fy_start_iso(fy: Optional[str]) -> Optional[str]:
    """'2024-25' → '2024-04-01'. Returns None on bad input."""
    if not fy:
        return None
    try:
        start_year = int(fy.split("-")[0])
        return f"{start_year}-04-01"
    except (ValueError, IndexError):
        return None


def base_fy_start_iso(today: Optional[date_type] = None) -> str:
    """The FY start anchor where Tally's master OpeningBalance currently lives —
    today's calendar FY (Tally auto-rolls every 1-Apr)."""
    today = today or date_type.today()
    fy_year = today.year if today.month >= 4 else today.year - 1
    return f"{fy_year}-04-01"


def split_by_fy(vouchers: list, fy_start_str: Optional[str], date_field: str = "voucher_date"):
    """Split (pre_fy, current_fy) by date < fy_start_str. If no fy_start_str, all current."""
    if not fy_start_str:
        return [], list(vouchers)
    pre, curr = [], []
    for v in vouchers:
        if v.get(date_field, "") < fy_start_str:
            pre.append(v)
        else:
            curr.append(v)
    return pre, curr


def is_payment_voucher(v: dict) -> bool:
    """receipt_vouchers collection holds both receipts and payment vouchers; this
    distinguishes them by voucher_type."""
    return (v.get("voucher_type") or "").strip().lower() == "payment"


def split_receipts_and_payments(receipt_voucher_rows: list):
    """One pass over the merged collection → (receipts, payments)."""
    receipts, payments = [], []
    for v in receipt_voucher_rows:
        (payments if is_payment_voucher(v) else receipts).append(v)
    return receipts, payments


def filter_branch_parties(vouchers: list, branch_parties_lower: set) -> list:
    """Drop vouchers whose party_name is in the branch-party set (case-insensitive)."""
    if not branch_parties_lower:
        return vouchers
    return [
        v for v in vouchers
        if (v.get("party_name") or "").lower().strip() not in branch_parties_lower
    ]


# ── Opening balance ─────────────────────────────────────────────────────────

def build_synced_lookup(synced_customers: list):
    """(canonical_set, lower_to_canonical, lower_to_master_ob) for synced customers."""
    canonical = set()
    lower_to_canonical = {}
    lower_to_master_ob = {}
    for sc in synced_customers:
        name = sc.get("customer_name")
        if not name:
            continue
        canonical.add(name)
        key = name.lower().strip()
        lower_to_canonical[key] = name
        lower_to_master_ob[key] = safe_num(sc.get("opening_balance", 0))
    return canonical, lower_to_canonical, lower_to_master_ob


def compute_opening_balance_map(
    synced_customers: list,
    all_sales: list,
    all_receipts: list,
    all_payments: list,
    all_credit_notes: list,
    all_journals: list,
    fy_start_str: Optional[str],
    base_fy_start_str: str,
) -> dict:
    """Anchor Tally's master OpeningBalance against today's FY and adjust for the
    requested FY by replaying activity in the gap window. Returns {customer_name: OB}.

    - Same FY as base → return master OB unchanged.
    - Earlier FY than base → undo activity from req_fy_start to base_fy_start.
    - Later FY than base → forward-add activity from base_fy_start to req_fy_start.
    """
    opening_balance: dict = {}
    if not fy_start_str:
        return opening_balance

    _, lower_to_canonical, lower_to_master_ob = build_synced_lookup(synced_customers)
    for canonical_lower, canonical in lower_to_canonical.items():
        opening_balance[canonical] = lower_to_master_ob.get(canonical_lower, 0)

    if fy_start_str == base_fy_start_str:
        return opening_balance

    def resolve(p):
        return lower_to_canonical.get((p or "").lower().strip())

    if fy_start_str < base_fy_start_str:
        # Backward: undo activity in [fy_start_str, base_fy_start_str)
        lo, hi = fy_start_str, base_fy_start_str
        sign = -1  # subtract sales / add receipts (undo)
    else:
        # Forward: replay activity in [base_fy_start_str, fy_start_str)
        lo, hi = base_fy_start_str, fy_start_str
        sign = +1

    def _in_window(v):
        d = v.get("voucher_date", "")
        return lo <= d < hi

    for v in all_sales:
        if not _in_window(v):
            continue
        p = resolve(v.get("party_name"))
        if p is not None:
            opening_balance[p] += sign * safe_num(v.get("total_amount"))
    for r in all_receipts:
        if not _in_window(r):
            continue
        p = resolve(r.get("party_name"))
        if p is not None:
            opening_balance[p] += -sign * safe_num(r.get("amount"))
    for pmt in all_payments:
        if not _in_window(pmt):
            continue
        p = resolve(pmt.get("party_name"))
        if p is not None:
            # Payment vouchers DR the customer (e.g., cheque-bounce refund) →
            # forward = add DR; backward = subtract DR
            opening_balance[p] += sign * safe_num(pmt.get("amount"))
    for cn in all_credit_notes:
        if not _in_window(cn):
            continue
        p = resolve(cn.get("party_name"))
        if p is not None:
            opening_balance[p] += -sign * safe_num(cn.get("total_amount"))
    for jv in all_journals:
        if not _in_window(jv):
            continue
        p = resolve(jv.get("party_name"))
        if p is not None:
            debit, credit = get_jv_party_amount(jv)
            opening_balance[p] += sign * (debit - credit)

    return opening_balance


# ── Aging / status ──────────────────────────────────────────────────────────

def apply_fifo_aging(
    outstanding_amount: float,
    voucher_list: list,
    today: date_type,
    fy_start_str: Optional[str],
):
    """Return aging buckets dict for the given outstanding amount, allocating older
    invoices first. If no invoices exist but outstanding > 0, falls back to FY-start
    age. Mirrors the legacy in-route logic byte-for-byte (incl. the > vs >= boundaries)."""
    aging = {"aging_0_30": 0.0, "aging_30_60": 0.0, "aging_60_90": 0.0, "aging_90_plus": 0.0}
    oldest_days = 0
    if outstanding_amount <= 0:
        return aging, oldest_days

    if voucher_list:
        voucher_list = sorted(voucher_list, key=lambda x: x["days_old"], reverse=True)
        remaining = outstanding_amount
        for v in voucher_list:
            if remaining <= 0:
                break
            alloc = min(v["amount"], remaining)
            days = v["days_old"]
            if days > 90:
                aging["aging_90_plus"] += alloc
            elif days > 60:
                aging["aging_60_90"] += alloc
            elif days > 30:
                aging["aging_30_60"] += alloc
            else:
                aging["aging_0_30"] += alloc
            remaining -= alloc
        if remaining > 0:
            aging["aging_0_30"] += remaining
        return aging, oldest_days

    # No invoices: use FY-start as the reference for ageing
    try:
        if not fy_start_str:
            raise ValueError("no fy_start_str")
        fy_start_date = date_type(*[int(x) for x in fy_start_str.split("-")])
        days_from_fy_start = (today - fy_start_date).days
        oldest_days = days_from_fy_start
        if days_from_fy_start > 90:
            aging["aging_90_plus"] = outstanding_amount
        elif days_from_fy_start > 60:
            aging["aging_60_90"] = outstanding_amount
        elif days_from_fy_start > 30:
            aging["aging_30_60"] = outstanding_amount
        else:
            aging["aging_0_30"] = outstanding_amount
    except Exception:
        aging["aging_0_30"] = outstanding_amount
    return aging, oldest_days


def aging_status(outstanding_amount: float, oldest_invoice_days: int):
    """Map (outstanding, oldest_days) → (status, status_label) — same thresholds as legacy."""
    if outstanding_amount <= 0:
        return "normal", "Normal"
    if oldest_invoice_days > 90:
        return "critical", "Critical"
    if oldest_invoice_days > 60:
        return "overdue", "Overdue"
    if oldest_invoice_days > 30:
        return "at_risk", "At Risk"
    return "normal", "Normal"


# ── FY-aware credit aggregation (used by both endpoints) ────────────────────

def aggregate_party_credits(fy_receipts: list, fy_credit_notes: list, fy_journals: list):
    """Return per-party (lower-case key) breakdown of credits in the current FY.

    customer_receipts:    receipts (CR party) → reduces OS
    customer_cn_total:    CN totals (signed by per-line direction when available)
    customer_jv_net:      JV net = credit - debit (positive reduces OS)
    customer_jv_debit:    DR-only sum (JV DR + CN reversals) — for the Adjustment column
    """
    customer_receipts: dict = {}
    customer_cn_total: dict = {}
    customer_jv_net: dict = {}
    customer_jv_debit: dict = {}

    for r in fy_receipts:
        p = safe_str(r.get("party_name")).strip().lower()
        if p:
            customer_receipts[p] = customer_receipts.get(p, 0) + safe_num(r.get("amount"))

    for cn in fy_credit_notes:
        p = safe_str(cn.get("party_name")).strip().lower()
        if not p:
            continue
        # Honor per-ledger-entry direction when available (post-agent-v9.1 sync).
        # If a CN's party-row is is_debit=True it's a reversal that DR's the customer.
        entries = cn.get("ledger_entries") or []
        party_entry = next(
            (e for e in entries if (e.get("ledger_name") or "").lower().strip() == p),
            None,
        )
        amt = safe_num(cn.get("total_amount"))
        if party_entry and party_entry.get("is_debit"):
            customer_cn_total[p] = customer_cn_total.get(p, 0) - amt
            customer_jv_debit[p] = customer_jv_debit.get(p, 0) + amt
        else:
            customer_cn_total[p] = customer_cn_total.get(p, 0) + amt

    for jv in fy_journals:
        p = safe_str(jv.get("party_name")).strip().lower()
        if not p:
            continue
        debit, credit = get_jv_party_amount(jv)
        customer_jv_net[p] = customer_jv_net.get(p, 0) + (credit - debit)
        if debit > 0:
            customer_jv_debit[p] = customer_jv_debit.get(p, 0) + debit

    return customer_receipts, customer_cn_total, customer_jv_net, customer_jv_debit
