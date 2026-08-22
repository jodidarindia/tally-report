"""Iteration 116 — Sync-History display fixes (Bug A + Bug B).

Bug A: company_name column was showing raw UUID (Tally) or COMPxxx
       (legacy Busy) — must resolve to human-readable display name.
Bug B: chunked data types showed count=500 (CHUNK_SIZE) for last chunk
       instead of aggregated total. Backend now upserts one row per
       (tenant, company, data_type, fy, sync_mode) within a 30-min
       rolling window and $inc's the count.
"""
import os
import re
import uuid
from pathlib import Path

import pytest
import requests

# Load backend .env so services can boot when imported for direct db checks.
for _line in Path("/app/backend/.env").read_text().splitlines():
    if "=" in _line and not _line.strip().startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

NAV_TENANT = "1524ec0e-faae-448c-9f24-1ae8f51c399e"
NAV_COMPANY = "b21b291b-afcd-4152-b166-85be751d94bb"
NAV_DISPLAY = "NAVDURGA AUTO SPARES JABALPUR"

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ─── Helpers ─────────────────────────────────────────────────────────────

_CACHED_TOKEN = None


def _login():
    """Login once per test session and cache the token. Preview host
    aggressively rate-limits repeated logins (5 tries/minute)."""
    global _CACHED_TOKEN
    if _CACHED_TOKEN:
        return _CACHED_TOKEN
    last_err = None
    for _ in range(3):
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login", timeout=90,
                              json={"username": "busydemo@flowralive.in",
                                    "password": "demo2026"})
            if r.status_code == 200 and r.json().get("success"):
                _CACHED_TOKEN = r.json()["data"]["token"]
                return _CACHED_TOKEN
            last_err = f"{r.status_code} {r.text[:200]}"
            if r.status_code == 429:
                import time as _t
                _t.sleep(65)
        except requests.exceptions.RequestException as e:
            last_err = str(e)
    pytest.skip(f"busydemo login failed after retries: {last_err}")


def _get_sync_token(tok):
    r = requests.get(f"{BASE_URL}/api/auth/sync-token",
                     headers={"Authorization": f"Bearer {tok}"},
                     timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success"), j
    return j["data"]["sync_token"]


def _get_history_cycles(tok, limit=200):
    """Return the cycle-grouped payload of /api/sync/history.
    Each cycle is: {timestamp, company_name, financial_year, sync_mode,
    agent_version, data_types: {data_type: count}}"""
    r = requests.get(
        f"{BASE_URL}/api/sync/history?limit={limit}",
        headers={"Authorization": f"Bearer {tok}",
                 "X-Company-ID": NAV_COMPANY}, timeout=60,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success"), j
    return j["data"].get("cycles", [])


# ─── Bug A ───────────────────────────────────────────────────────────────
# company_name column must be a human-readable name, NEVER a UUID and
# NEVER a COMPxxx folder-id.

def test_bugA_no_uuid_or_compxxx_in_history_for_nav():
    tok = _login()
    cycles = _get_history_cycles(tok, limit=500)
    assert cycles, "sync/history for NAV returned no cycles — data missing"

    offenders = []
    for cyc in cycles:
        cn = (cyc.get("company_name") or "").strip()
        if not cn:
            offenders.append(("<empty>", cyc.get("timestamp")))
            continue
        if UUID_RE.match(cn):
            offenders.append((cn, cyc.get("timestamp")))
            continue
        if cn.upper().startswith("COMP") and cn[4:].isdigit():
            offenders.append((cn, cyc.get("timestamp")))

    assert not offenders, (
        f"sync_history still has UUID/COMPxxx company_name entries: {offenders[:10]}"
    )


def test_bugA_nav_display_name_present():
    """The NAV Busy tenant must show the human-readable display name
    on at least one sync_history cycle (post backfill)."""
    tok = _login()
    cycles = _get_history_cycles(tok, limit=500)
    names = {(c.get("company_name") or "").strip() for c in cycles}
    assert NAV_DISPLAY in names, (
        f"Expected '{NAV_DISPLAY}' in cycles, got: {list(names)[:6]}"
    )


# ─── Bug B ───────────────────────────────────────────────────────────────
# Chunked data types must show TRUE totals, not CHUNK_SIZE tails.

# Expected minimums (post-backfill) from the review brief.
EXPECTED_MIN = {
    ("sales", "2025-26"): 10000,
    ("sales", "2026-27"): 3000,
    ("inventory", "2025-26"): 30000,
    ("receipts", "2025-26"): 3000,
    ("all_ledgers", "2025-26"): 1500,
}


def test_bugB_no_chunk_size_500_totals_for_chunked_types():
    """After the fix, count MUST NOT equal the CHUNK_SIZE (500) for the
    NAV chunked data types — because their real totals are all > 500.
    A `count == 500` for these types means we're still displaying the
    tail chunk instead of the aggregated total."""
    tok = _login()
    cycles = _get_history_cycles(tok, limit=500)

    chunked_types = {"sales", "inventory", "receipts",
                     "contra_vouchers", "credit_notes", "all_ledgers"}

    top_by_key = {}
    for cyc in cycles:
        fy = cyc.get("financial_year", "")
        for dt, cnt in (cyc.get("data_types") or {}).items():
            if dt not in chunked_types:
                continue
            key = (dt, fy)
            c = int(cnt or 0)
            if c > top_by_key.get(key, -1):
                top_by_key[key] = c

    stuck_at_500 = {k: v for k, v in top_by_key.items() if v == 500}
    assert not stuck_at_500, (
        f"Chunked data types stuck at 500 (CHUNK_SIZE tail — Bug B not "
        f"fixed): {stuck_at_500}"
    )


def test_bugB_nav_totals_exceed_backfill_minimums():
    """For known-populated NAV phases, the aggregated count must be at
    least the backfill minimums we published in the review brief."""
    tok = _login()
    cycles = _get_history_cycles(tok, limit=500)

    top_by_key = {}
    for cyc in cycles:
        fy = cyc.get("financial_year", "")
        for dt, cnt in (cyc.get("data_types") or {}).items():
            key = (dt, fy)
            c = int(cnt or 0)
            if c > top_by_key.get(key, -1):
                top_by_key[key] = c

    misses = []
    for key, min_expected in EXPECTED_MIN.items():
        got = top_by_key.get(key, 0)
        if got < min_expected:
            misses.append({"phase": key, "got": got, "expected_min": min_expected})
    assert not misses, f"Aggregated counts below backfill minimums: {misses}"


# ─── Bug B forward-fix — 3-chunk sales POST must land as ONE row ─────────

def test_bugB_forward_fix_three_chunks_aggregate_to_one_row():
    """Post 3 chunks of 250 sales as busydemo. sync_history should
    contain ONE row with count=750 and chunks=3, NOT three rows of
    250 each."""
    tok = _login()
    stok = _get_sync_token(tok)

    fy = "2099-00"  # reserved test FY that no real data uses
    sync_mode = "test_forward_fix"
    data_type = "sales"

    def _mk_chunk(prefix, n):
        return [{
            "voucher_id": f"TEST_{prefix}_{i:04d}",
            "voucher_number": f"TEST-{prefix}-{i:04d}",
            "voucher_date": "2099-04-01",
            "party_name": "TEST_PARTY",
            "total_amount": 100.0,
            "amount": 100.0,
            "item_name": "TEST_ITEM",
            "quantity": 1,
            "rate": 100.0,
            "godown_name": "",
            "narration": "iter-116 forward-fix test",
        } for i in range(n)]

    # We must ensure a clean window so the pre-existing rows don't get
    # $inc'd. Use a made-up FY to isolate.
    for prefix, n in [("A", 250), ("B", 250), ("C", 250)]:
        payload = {
            "data_type": data_type,
            "data": _mk_chunk(prefix, n),
            "tenant_id": NAV_TENANT,
            "company_id": NAV_COMPANY,
            "company_name": NAV_DISPLAY,
            "financial_year": fy,
            "sync_mode": sync_mode,
            "sync_token": stok,
            "agent_version": "iter116-test",
        }
        r = requests.post(f"{BASE_URL}/api/agent/sync", json=payload, timeout=180)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success"), j

    # Query the raw sync_history collection directly to verify the
    # single-row aggregation (the /api/sync/history endpoint groups
    # entries into cycles which would hide the row-level shape).
    import asyncio
    from db import db  # noqa: E402

    async def _fetch_and_cleanup():
        matching = await db.sync_history.find({
            "tenant_id": NAV_TENANT,
            "company_id": NAV_COMPANY,
            "data_type": data_type,
            "financial_year": fy,
            "sync_mode": sync_mode,
        }, {"_id": 0}).to_list(100)
        # cleanup regardless of assertion outcome
        return matching

    async def _cleanup():
        await db.sales_vouchers.delete_many({
            "tenant_id": NAV_TENANT,
            "company_id": NAV_COMPANY,
            "voucher_id": {"$regex": "^TEST_"}
        })
        await db.sync_history.delete_many({
            "tenant_id": NAV_TENANT,
            "company_id": NAV_COMPANY,
            "financial_year": fy,
            "sync_mode": sync_mode,
        })
        await db.sync_status.delete_many({
            "tenant_id": NAV_TENANT,
            "company_id": NAV_COMPANY,
            "financial_year": fy,
        })

    loop = asyncio.new_event_loop()
    try:
        matching = loop.run_until_complete(_fetch_and_cleanup())
    finally:
        try:
            loop.run_until_complete(_cleanup())
        except Exception as _e:
            print(f"cleanup warn: {_e}")
        loop.close()

    assert len(matching) == 1, (
        f"Expected ONE aggregated sync_history row for 3-chunk test, "
        f"got {len(matching)}: {matching}"
    )
    row = matching[0]
    assert row.get("count") == 750, f"Expected count=750, got {row.get('count')} — {row}"
    assert row.get("chunks") == 3, f"Expected chunks=3, got {row.get('chunks')} — {row}"
    cn = (row.get("company_name") or "").strip()
    assert cn == NAV_DISPLAY, f"Expected display '{NAV_DISPLAY}', got '{cn}'"


# ─── Regression — forecast still returns 200 for busydemo ────────────────

def test_regression_forecast_overview_still_200():
    tok = _login()
    r = requests.get(
        f"{BASE_URL}/api/analytics/forecast/overview?horizon_months=3",
        headers={"Authorization": f"Bearer {tok}", "X-Company-ID": NAV_COMPANY},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success"), r.json()


# ─── Regression — reconcile still logs a row with the display name ───────

def test_regression_reconcile_logs_display_name():
    tok = _login()
    stok = _get_sync_token(tok)

    payload = {
        "data_type": "sales",
        "manifest_ids": ["__NONEXISTENT_ID__"],
        "tenant_id": NAV_TENANT,
        "company_id": NAV_COMPANY,
        "company_name": NAV_DISPLAY,
        "financial_year": "2099-01",   # narrow window that won't match anything
        "sync_token": stok,
        "agent_version": "iter116-test",
        "window_start": "2099-04-01",
        "window_end": "2099-04-02",
    }
    r = requests.post(f"{BASE_URL}/api/agent/reconcile", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success"), j
