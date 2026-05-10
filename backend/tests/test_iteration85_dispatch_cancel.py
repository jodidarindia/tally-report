"""Iteration 85 — Dispatch card cancel + invoice change detection (Option B).

Verifies (single-loop pattern to avoid motor "Event loop is closed" issues):
  - Constants (CANCELLABLE_STATUSES / CANCEL_REASONS) match spec.
  - _detect_invoice_changes flags items / total_amount / party_name diffs
    without mutating the snapshot.
  - Missing invoices flagged separately.
  - Post-dispatch changes use a distinct flag.
  - Cancelled cards are skipped.
  - Stale flags clear when invoice is restored.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import db  # noqa: E402
from routes.dispatch import (  # noqa: E402
    _detect_invoice_changes, CANCELLABLE_STATUSES, CANCEL_REASONS,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Constants sanity (no DB) ─────────────────────────────────────────────
def test_cancellable_statuses_match_spec():
    assert CANCELLABLE_STATUSES == ["new", "queued", "processing", "packed"]


def test_cancel_reasons_present():
    for r in ["customer_request", "payment_issue", "stock_unavailable",
              "duplicate", "invoice_modified", "other"]:
        assert r in CANCEL_REASONS


# ── DB integration — all in one async block to share motor's event loop ──
def test_detect_invoice_changes_full_suite():
    tenant = f"itest-{uuid.uuid4().hex[:6]}"
    company = f"co-{uuid.uuid4().hex[:6]}"

    async def _run():
        # Seed helper
        async def seed_card(cid, status, items=None, total=10000, party="ACME",
                            cancelled_at=None, cancelled_from_status=None,
                            extra=None):
            doc = {
                "card_id": cid, "card_type": "invoice",
                "invoice_number": f"INV-{cid}", "voucher_id": f"V-{cid}",
                "party_name": party,
                "items": items or [{"item": "Widget", "quantity": 5}],
                "total_amount": total, "voucher_date": "2026-02-09",
                "status": status, "assigned_to": None,
                "total_boxes": 0, "physical_check": status == "packed",
                "status_history": [{"status": "new", "at": _now(), "by": "system"}],
                "created_at": _now(), "created_by": "system",
                "tenant_id": tenant, "company_id": company,
            }
            if cancelled_at:
                doc["cancelled_at"] = cancelled_at
                doc["cancelled_from_status"] = cancelled_from_status or "queued"
                doc["cancel_reason"] = "duplicate"
                doc["status"] = "cancelled"
            if extra:
                doc.update(extra)
            await db.dispatch_cards.insert_one(doc)

        async def seed_voucher(cid, items, total, party="ACME"):
            await db.sales_vouchers.insert_one({
                "voucher_id": f"V-{cid}",
                "reference_number": f"INV-{cid}",
                "party_name": party, "items": items, "total_amount": total,
                "voucher_date": "2026-02-09",
                "tenant_id": tenant, "company_id": company,
            })

        try:
            # ── Test 1: no change → zero flags ──
            cid1 = uuid.uuid4().hex[:8]
            items = [{"item": "Widget", "quantity": 5}]
            await seed_card(cid1, "queued", items=items, total=10000)
            await seed_voucher(cid1, items=items, total=10000)
            r1 = await _detect_invoice_changes(tenant, company)
            assert r1["flagged_changed"] == 0, f"unchanged card flagged: {r1}"
            assert r1["flagged_missing"] == 0
            assert r1["post_dispatch_changed"] == 0

            # ── Test 2: items added → flag + snapshot preserved ──
            cid2 = uuid.uuid4().hex[:8]
            await seed_card(cid2, "processing", items=items, total=10000)
            await seed_voucher(cid2, items=[{"item": "Widget", "quantity": 5},
                                            {"item": "Bolt", "quantity": 10}],
                               total=12000)
            r2 = await _detect_invoice_changes(tenant, company)
            assert r2["flagged_changed"] >= 1, f"added-items not flagged: {r2}"
            card = await db.dispatch_cards.find_one({"card_id": cid2}, {"_id": 0})
            assert card["invoice_changed_flag"] is True
            # Snapshot must NOT be mutated (Option B)
            assert len(card["items"]) == 1, "snapshot was mutated!"
            assert card["total_amount"] == 10000, "snapshot total was mutated!"
            diffs = {d["field"] for d in card.get("detected_changes", [])}
            assert "items_count" in diffs or "items_changed" in diffs
            assert "total_amount" in diffs

            # ── Test 3: invoice deleted → missing flag ──
            cid3 = uuid.uuid4().hex[:8]
            await seed_card(cid3, "queued", total=5000)
            # No voucher seeded → simulates Tally deletion
            r3 = await _detect_invoice_changes(tenant, company)
            assert r3["flagged_missing"] >= 1, f"missing not flagged: {r3}"
            card = await db.dispatch_cards.find_one({"card_id": cid3}, {"_id": 0})
            assert card.get("invoice_missing_flag") is True

            # ── Test 4: post-dispatch change → separate flag ──
            cid4 = uuid.uuid4().hex[:8]
            await seed_card(cid4, "dispatched", items=items, total=10000)
            await seed_voucher(cid4, items=items, total=11500)  # changed amt
            r4 = await _detect_invoice_changes(tenant, company)
            assert r4["post_dispatch_changed"] >= 1, f"post-dispatch not flagged: {r4}"
            card = await db.dispatch_cards.find_one({"card_id": cid4}, {"_id": 0})
            assert card.get("post_dispatch_invoice_changed") is True
            # `invoice_changed_flag` must NOT be set on shipped cards
            assert not card.get("invoice_changed_flag")

            # ── Test 5: cancelled cards are skipped ──
            cid5 = uuid.uuid4().hex[:8]
            await seed_card(cid5, "queued", items=[{"item": "X", "quantity": 1}],
                            total=100, cancelled_at=_now(),
                            cancelled_from_status="queued")
            # Voucher very different — but card is cancelled, must be ignored
            await seed_voucher(cid5, items=[{"item": "Y", "quantity": 99}], total=99999)
            await _detect_invoice_changes(tenant, company)
            card = await db.dispatch_cards.find_one({"card_id": cid5}, {"_id": 0})
            assert not card.get("invoice_changed_flag")
            assert not card.get("invoice_missing_flag")
            assert not card.get("post_dispatch_invoice_changed")

            # ── Test 6: stale flag clears when invoice is restored to original ──
            cid6 = uuid.uuid4().hex[:8]
            await seed_card(cid6, "queued", items=items, total=10000,
                            extra={
                                "invoice_changed_flag": True,
                                "detected_changes": [{"field": "items_count", "old": 1, "new": 2}],
                            })
            await seed_voucher(cid6, items=items, total=10000)
            r6 = await _detect_invoice_changes(tenant, company)
            assert r6["cleared"] >= 1, f"stale flag did not clear: {r6}"
            card = await db.dispatch_cards.find_one({"card_id": cid6}, {"_id": 0})
            assert not card.get("invoice_changed_flag")

        finally:
            # Always clean up this test's data
            await db.dispatch_cards.delete_many({"tenant_id": tenant})
            await db.sales_vouchers.delete_many({"tenant_id": tenant})

    asyncio.get_event_loop().run_until_complete(_run())
