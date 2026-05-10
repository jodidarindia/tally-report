"""Iteration 88 — Auto-created dispatch cards must always start in `new` lane.

Bug: prior to this fix, when there were dispatch employees configured,
the auto-create helper round-robin-assigned each new card AND set its
status straight to `queued`, skipping the `new` review lane entirely.
The dispatch admin lost the chance to review fresh-from-Tally invoices
before they were queued for processing.

Fix: status is unconditionally set to `new`. Round-robin assignment is
preserved so the eventual queue-er sees who owns the card, but the lane
stays at `new` until a human moves it.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import db  # noqa: E402
from routes.dispatch import _auto_create_cards_helper  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_auto_create_always_starts_in_new_lane():
    tenant = f"itest-{uuid.uuid4().hex[:6]}"
    company = f"co-{uuid.uuid4().hex[:6]}"
    start = "2026-04-01"

    async def _run():
        # Seed dispatch_settings with auto-create enabled
        await db.dispatch_settings.insert_one({
            "tenant_id": tenant, "company_id": company,
            "auto_create_enabled": True, "start_date": start,
        })

        # Seed two dispatch users so round-robin assignment kicks in
        # (the bug only manifested when assignment was non-null)
        for un in ("d1@test.in", "d2@test.in"):
            await db.users.insert_one({
                "id": f"itest-{un}", "username": un, "email": un,
                "password_hash": "x", "role": "dispatch",
                "tenant_id": tenant, "company_id": company,
                "active": True,
            })

        # Seed 3 fresh sales vouchers (each becomes one card)
        for i in range(3):
            await db.sales_vouchers.insert_one({
                "voucher_id": f"V-{i}", "reference_number": f"INV-{i}",
                "voucher_type": "Sales",
                "party_name": f"Party {i}",
                "total_amount": 1000 * (i + 1),
                "voucher_date": "2026-05-01",
                "items": [{"item_name": "Widget", "quantity": 1, "rate": 1000}],
                "tenant_id": tenant, "company_id": company,
            })

        try:
            created = await _auto_create_cards_helper(tenant, company, start)
            assert created == 3, f"expected 3 cards, got {created}"

            cards = await db.dispatch_cards.find(
                {"tenant_id": tenant, "company_id": company},
                {"_id": 0, "status": 1, "assigned_to": 1, "status_history": 1, "invoice_number": 1},
            ).to_list(50)
            assert len(cards) == 3

            # Every card MUST be in `new` lane regardless of assignment
            for c in cards:
                assert c["status"] == "new", (
                    f"REGRESSION: card {c.get('invoice_number')} landed in "
                    f"{c['status']} (expected 'new')"
                )
                # Status history should have ONE entry, not two (the previous
                # buggy version pushed both `new` and `queued` entries)
                assert len(c.get("status_history", [])) == 1, (
                    f"unexpected extra status_history entries: {c['status_history']}"
                )
                assert c["status_history"][0]["status"] == "new"

            # Assignment is still round-robined — the workflow still tells the
            # eventual queue-er who owns the card. We just don't auto-skip
            # the review lane any more.
            assigned = [c.get("assigned_to") for c in cards]
            assert all(a in ("d1@test.in", "d2@test.in") for a in assigned), (
                f"round-robin assignment should still happen: {assigned}"
            )

        finally:
            await db.dispatch_cards.delete_many({"tenant_id": tenant})
            await db.dispatch_settings.delete_many({"tenant_id": tenant})
            await db.users.delete_many({"tenant_id": tenant})
            await db.sales_vouchers.delete_many({"tenant_id": tenant})

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
