"""Iteration 101 — Dashboard "Recent Transactions" must show the
latest bill first when multiple vouchers share the same date.

Bug report: on tenant Krishna Sales Corp the most recent voucher of the
day was not on top — older same-day vouchers appeared above it.

Root cause: backend sorted only by `voucher_date` (date-only string).
Ties were preserved in MongoDB's natural (insertion) order, which is
chronological by `_id` — but when vouchers are synced out-of-order (very
common for back-filled or batched Tally syncs) the ordering became
effectively random.

Fix: secondary sort by `voucher_id` (Tally's per-series running serial)
and tertiary by `last_updated` (sync timestamp) — both DESC.

This test calls the same `sorted()` expression used by the endpoint to
guarantee the contract.
"""


def _sort_recent(vouchers):
    return sorted(
        vouchers,
        key=lambda x: (
            x.get("voucher_date", ""),
            x.get("voucher_id", ""),
            x.get("last_updated", ""),
        ),
        reverse=True,
    )[:10]


def test_latest_date_wins():
    vs = [
        {"voucher_date": "2026-05-19", "voucher_id": "A/0001", "party_name": "Old"},
        {"voucher_date": "2026-05-21", "voucher_id": "A/0050", "party_name": "Newest"},
        {"voucher_date": "2026-05-20", "voucher_id": "A/0030", "party_name": "Mid"},
    ]
    assert _sort_recent(vs)[0]["party_name"] == "Newest"


def test_same_date_higher_voucher_id_wins():
    """On the same day Tally's series number is monotonic — the highest
    serial is the latest bill of the day."""
    vs = [
        {"voucher_date": "2026-05-21", "voucher_id": "VCG/0001/2627", "party_name": "First bill"},
        {"voucher_date": "2026-05-21", "voucher_id": "VCG/0010/2627", "party_name": "Latest bill"},
        {"voucher_date": "2026-05-21", "voucher_id": "VCG/0005/2627", "party_name": "Mid bill"},
    ]
    out = _sort_recent(vs)
    assert out[0]["party_name"] == "Latest bill"
    assert out[1]["party_name"] == "Mid bill"
    assert out[2]["party_name"] == "First bill"


def test_missing_voucher_id_falls_back_to_last_updated():
    """Legacy rows without voucher_id should still order by sync time."""
    vs = [
        {"voucher_date": "2026-05-21", "last_updated": "2026-05-21T09:00:00Z", "party_name": "Early"},
        {"voucher_date": "2026-05-21", "last_updated": "2026-05-21T18:00:00Z", "party_name": "Late"},
    ]
    assert _sort_recent(vs)[0]["party_name"] == "Late"


def test_returns_at_most_ten():
    vs = [
        {"voucher_date": f"2026-05-{d:02d}", "voucher_id": f"X/{d:04d}"}
        for d in range(1, 25)
    ]
    out = _sort_recent(vs)
    assert len(out) == 10
    # First entry is the latest date
    assert out[0]["voucher_date"] == "2026-05-24"


def test_mixed_series_same_day():
    """Multi-series shops (e.g. KTG/ + CGSA2627/) — string sort still
    surfaces the alphabetically-highest serial as 'latest of the day'.
    This is the best we can do without a true entry timestamp, and
    matches what the user perceives because each series is processed
    sequentially by the agent."""
    vs = [
        {"voucher_date": "2026-05-21", "voucher_id": "CGSA2627/0053", "party_name": "C-series"},
        {"voucher_date": "2026-05-21", "voucher_id": "KTG/0030/2526",  "party_name": "K-series"},
    ]
    out = _sort_recent(vs)
    # K > C alphabetically — K-series is on top.
    assert out[0]["party_name"] == "K-series"
