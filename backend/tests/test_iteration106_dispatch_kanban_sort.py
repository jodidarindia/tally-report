"""Iteration 106 — Dispatch Terminal kanban sort must be consistent across
ALL lanes (New, Queued, Processing, Packed, Dispatched, Hold).

Prior behaviour:
  • New lane was sorted client-side by digit-stripped invoice_number DESC,
    which mis-ranked multi-series shops (e.g. CGSA2627/0013 outranked
    KTG/0030/2526 even when the latter was newer).
  • All other lanes were sorted by created_at DESC at the backend.
  • Result: when a card moved from New → Queued, its position relative
    to siblings flipped, confusing dispatch operators.

Fix:
  • Backend now returns dispatch_cards sorted by
    (voucher_date DESC, voucher_id DESC, created_at DESC) for EVERY lane.
  • Frontend drops its special-case New-lane sort and renders the cards
    in the exact order it receives them from the API.

These tests hit the live endpoint with seeded data and assert the order.
"""
import os
import sys
import uuid
import datetime as dt

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "http://127.0.0.1:8001"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "Flowra-Insights-Dev")
_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]

T = f"itest106-tenant-{uuid.uuid4().hex[:8]}"
CO = f"itest106-co-{uuid.uuid4().hex[:6]}"


def _jwt(tenant_id: str) -> str:
    from services.auth_service import create_access_token
    return create_access_token(
        user_id=f"{tenant_id}@test.local",
        username=f"{tenant_id}@test.local",
        role="admin",
        tenant_id=tenant_id,
    )


def _seed_card(card_id, voucher_id, voucher_date, status="new",
               created_at=None, invoice_number=None):
    return {
        "tenant_id": T,
        "company_id": CO,
        "card_id": card_id,
        "invoice_number": invoice_number or voucher_id,
        "voucher_id": voucher_id,
        "voucher_date": voucher_date,
        "status": status,
        "party_name": "Test Party",
        "total_amount": 1000.0,
        "created_at": created_at or dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@pytest.fixture(autouse=True)
def around_each():
    _db.dispatch_cards.delete_many({"tenant_id": T})
    _db.users.delete_many({"tenant_id": T})
    _db.users.insert_one({
        "username": f"{T}@test.local", "tenant_id": T, "role": "admin",
        "active": True, "password_hash": "x", "subscription_start": "",
        "subscription_months": 999,
        "companies": [CO],
    })
    yield
    _db.dispatch_cards.delete_many({"tenant_id": T})
    _db.users.delete_many({"tenant_id": T})


def _get_cards(status="active"):
    token = _jwt(T)
    r = requests.get(
        f"{BASE}/api/dispatch/cards?company_id={CO}&status={status}",
        headers={"Authorization": f"Bearer {token}", "X-Company-ID": CO},
        timeout=10,
    )
    assert r.status_code == 200
    return r.json()["data"]["cards"]


def test_latest_voucher_date_floats_to_top():
    _db.dispatch_cards.insert_many([
        _seed_card("c1", "AAA/0001", "2026-04-10", status="new"),
        _seed_card("c2", "AAA/0002", "2026-05-21", status="new"),   # newest
        _seed_card("c3", "AAA/0003", "2026-05-15", status="new"),
    ])
    cards = _get_cards()
    assert [c["card_id"] for c in cards] == ["c2", "c3", "c1"]


def test_same_date_higher_voucher_id_wins():
    """Two cards on the same date — Tally's running serial breaks the tie.
    The HIGHEST series number is the latest bill of the day."""
    _db.dispatch_cards.insert_many([
        _seed_card("c-low",  "VCG/0001/2627", "2026-05-21", status="new"),
        _seed_card("c-mid",  "VCG/0005/2627", "2026-05-21", status="new"),
        _seed_card("c-high", "VCG/0010/2627", "2026-05-21", status="new"),
    ])
    cards = _get_cards()
    assert [c["card_id"] for c in cards] == ["c-high", "c-mid", "c-low"]


def test_sort_consistent_across_lanes():
    """Card moved from New → Queued must keep the same relative position
    against its same-day siblings. v9.8.27 fixes the previous inconsistency
    where the New lane used a different (invoice_number) sort key."""
    _db.dispatch_cards.insert_many([
        _seed_card("new-old",  "X/0001", "2026-05-10", status="new"),
        _seed_card("new-new",  "X/0010", "2026-05-21", status="new"),
        _seed_card("queue-old","X/0002", "2026-05-10", status="queued"),
        _seed_card("queue-new","X/0011", "2026-05-21", status="queued"),
    ])
    cards = _get_cards()
    # Both newest-date cards (queue-new + new-new) come before the older ones.
    # Within the same date, voucher_id DESC orders them.
    ids = [c["card_id"] for c in cards]
    assert ids.index("queue-new") < ids.index("queue-old")
    assert ids.index("new-new")   < ids.index("new-old")
    # And the 2026-05-21 cards are above the 2026-05-10 ones.
    assert ids.index("new-new")   < ids.index("queue-old")
    assert ids.index("queue-new") < ids.index("new-old")


def test_multi_series_same_day_consistent():
    """Krishna Sales scenario: two parallel series KTG and CGSA both
    issued today. The OLD frontend sort would have ranked CGSA above KTG
    because digit-stripping gave '2627...' > '0030...' regardless of
    actual recency. The new sort orders by voucher_id DESC alphabetically,
    which is consistent for the same date even across series."""
    _db.dispatch_cards.insert_many([
        _seed_card("k-30",  "KTG/0030/2526",   "2026-05-21", status="new"),
        _seed_card("c-13",  "CGSA2627/0013",   "2026-05-21", status="new"),
    ])
    cards = _get_cards()
    # K > C alphabetically. Both are 2026-05-21, so voucher_id DESC wins.
    # Importantly, both shops see the same predictable order regardless
    # of which lane the cards are in.
    assert cards[0]["card_id"] == "k-30"
    assert cards[1]["card_id"] == "c-13"


def test_legacy_card_with_no_voucher_id_falls_to_bottom():
    _db.dispatch_cards.insert_many([
        _seed_card("good", "A/0001", "2026-05-21", status="new"),
        # Legacy card missing voucher_id — should sink below "good"
        {**_seed_card("legacy", "", "2026-05-21", status="new"), "voucher_id": ""},
    ])
    cards = _get_cards()
    assert cards[0]["card_id"] == "good"
    assert cards[1]["card_id"] == "legacy"
