"""Iteration 89 — Two CA Corner / Dashboard fixes:

1. Cash Flow tab read from `bank_cash_ledgers` collection which the v9.x
   sync agent does NOT populate, so all bank/cash figures showed ZERO
   even when `all_ledgers` had real Cash-in-Hand / Bank Accounts /
   Bank OD A/c data. Fix: read from `all_ledgers` directly, discriminate
   by `parent_group`.

2. Dashboard "Overdue" digest grossly under-reported because:
   (a) Tally exports payment-style vouchers under types like
       `bank payment`, `cash payment`, `cheque return voucher`. The old
       filter only excluded `voucher_type == "payment"` exactly.
   (b) The voucher-only reconstruction missed prior-FY opening balances.

   Fix: rebuild `customer_summary` using `customers.outstanding_amount`
   (Tally-truth) minus a FIFO-derived "recent unpaid cap".

Note: All sub-tests share one event loop because motor binds to the
first loop it sees on a per-process basis.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import db  # noqa: E402
from utils import compute_overdue_digest  # noqa: E402


def _date_str(days_ago: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_overdue_digest_three_scenarios():
    async def _run():
        # ── Scenario 1: payment-style vouchers must NOT reduce overdue ──
        t1 = f"itest-{uuid.uuid4().hex[:6]}"
        try:
            await db.customers.insert_one({
                "tenant_id": t1, "company_id": "",
                "customer_name": "Test Party Co", "outstanding_amount": 100000,
            })
            await db.sales_vouchers.insert_one({
                "tenant_id": t1, "company_id": "",
                "party_name": "Test Party Co", "total_amount": 100000,
                "voucher_id": "SV-1", "voucher_date": _date_str(90),
                "voucher_type": "Sales", "items": [],
            })
            # The CRITICAL bug: bank-payment counted as receipt
            await db.receipt_vouchers.insert_one({
                "tenant_id": t1, "company_id": "",
                "party_name": "Test Party Co", "amount": 50000,
                "voucher_id": "P-1", "voucher_date": _date_str(30),
                "voucher_type": "bank payment",
            })
            # Cheque return must also be excluded
            await db.receipt_vouchers.insert_one({
                "tenant_id": t1, "company_id": "",
                "party_name": "Test Party Co", "amount": 25000,
                "voucher_id": "CR-1", "voucher_date": _date_str(20),
                "voucher_type": "cheque return voucher",
            })

            digest = await compute_overdue_digest(db, t1, "")
            cs = digest.get("customer_summary", [])
            assert len(cs) == 1, f"Scenario 1: expected 1 overdue, got {len(cs)}"
            assert cs[0]["total_overdue"] == 100000.0, (
                f"REGRESSION: bank payment / cheque return reduced overdue. "
                f"Got ₹{cs[0]['total_overdue']} (expected ₹1L)"
            )
            assert digest["total_customers_overdue"] == 1
        finally:
            await db.customers.delete_many({"tenant_id": t1})
            await db.sales_vouchers.delete_many({"tenant_id": t1})
            await db.receipt_vouchers.delete_many({"tenant_id": t1})

        # ── Scenario 2: opening-balance-only customer must show overdue ──
        t2 = f"itest-{uuid.uuid4().hex[:6]}"
        try:
            await db.customers.insert_one({
                "tenant_id": t2, "company_id": "",
                "customer_name": "Old Party",
                "outstanding_amount": 200000, "opening_balance": 200000,
            })
            digest = await compute_overdue_digest(db, t2, "")
            cs = digest.get("customer_summary", [])
            assert len(cs) == 1, "Scenario 2: opening-balance-only customer dropped"
            assert cs[0]["total_overdue"] == 200000.0
            assert cs[0]["oldest_days"] >= 365  # proxy for prior-FY
        finally:
            await db.customers.delete_many({"tenant_id": t2})

        # ── Scenario 3: recent-only customer must NOT be overdue ──
        t3 = f"itest-{uuid.uuid4().hex[:6]}"
        try:
            await db.customers.insert_one({
                "tenant_id": t3, "company_id": "",
                "customer_name": "Recent Party", "outstanding_amount": 50000,
            })
            await db.sales_vouchers.insert_one({
                "tenant_id": t3, "company_id": "",
                "party_name": "Recent Party", "total_amount": 50000,
                "voucher_id": "SV-R", "voucher_date": _date_str(20),
                "voucher_type": "Sales", "items": [],
            })

            digest = await compute_overdue_digest(db, t3, "")
            cs = digest.get("customer_summary", [])
            assert len(cs) == 0, f"Scenario 3: recent-only customer wrongly overdue: {cs}"
        finally:
            await db.customers.delete_many({"tenant_id": t3})
            await db.sales_vouchers.delete_many({"tenant_id": t3})

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
