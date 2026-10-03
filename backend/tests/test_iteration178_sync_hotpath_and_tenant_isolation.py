"""iter-178 — Tenant-isolation hardening, background-task auto-dispatch,
and compound upsert indexes.

Context:
  * NAVDURGA / Krishna Sales Corp log on 2026-10-03 showed 35+ read
    timeouts on `/api/agent/sync` because each sales/receipts batch
    held the HTTP response for >120 s. Root causes:
      1. `_auto_create_cards_helper` + `_detect_invoice_changes` + the
         overdue-digest recompute all ran inline on the sync hot path.
      2. The voucher upsert `bulk_write(UpdateOne, filter={voucher_id,
         tenant_id, company_id}, upsert=True)` had no matching
         compound index — every row did a full-collection scan.
  * At the same time, every tenant's dashboard flipped to
    "Sync in progress…" even though only Krishna Sales was actively
    syncing. A ghost `sync_status` doc from 2026-07-30 with
    `company_id=''` was leaking through the `/sync/status` fallback
    into every sibling company query, and the WebSocket `get_status`
    path accepted empty `tenant_id` → cross-tenant leak.

The tests below are static code-level checks (same style as prior
iter-176/177 regressions) so refactors can't silently reintroduce
the hot-path or isolation regressions.
"""
from pathlib import Path
import pytest


SYNC   = Path("/app/backend/routes/sync.py").read_text(encoding="utf-8")
SERVER = Path("/app/backend/server.py").read_text(encoding="utf-8")


# ─── A — Background-task hot-path (P1a) ───────────────────────────────
def test_auto_dispatch_is_fire_and_forget():
    """`_auto_create_cards_helper` + `_detect_invoice_changes` must run
    inside `asyncio.create_task(...)` so the agent's HTTP ack is NOT
    blocked by the dispatch scan."""
    # The create_task wrapper must appear right before the dispatch
    # helpers are referenced.
    assert "async def _bg_auto_dispatch" in SYNC
    assert "_asyncio.create_task(_bg_auto_dispatch())" in SYNC
    # Both helpers must only be imported inside the background closure
    # (so a sync import failure doesn't crash the ack path).
    assert SYNC.count("from routes.dispatch import _auto_create_cards_helper, _detect_invoice_changes") == 1


def test_overdue_digest_is_fire_and_forget():
    """Same treatment for the overdue-digest recompute (second-biggest
    inline offender on the sync hot path)."""
    assert "async def _bg_overdue_digest" in SYNC
    assert "_asyncio.create_task(_bg_overdue_digest())" in SYNC


# ─── B — Compound upsert indexes (P1b) ────────────────────────────────
def test_compound_upsert_index_registered():
    """Each voucher collection whose sync upserts filter on
    (tenant_id, company_id, voucher_id) must have `tcid_vid`. Without
    this each upsert does a full COLLSCAN under load — the direct
    cause of the 3-Oct 120 s read-timeout cascade."""
    assert "name='tcid_vid'" in SERVER
    assert "('tenant_id', 1), ('company_id', 1), ('voucher_id', 1)" in SERVER
    # Must cover every voucher collection in the sync hot-path.
    for coll in (
        "'sales_vouchers'", "'purchase_vouchers'", "'receipt_vouchers'",
        "'payment_vouchers'", "'credit_notes'", "'debit_notes'",
        "'journal_vouchers'", "'stock_journals'", "'contra_vouchers'",
    ):
        assert coll in SERVER, f"missing tcid_vid coverage for {coll}"


def test_customer_upsert_index_registered():
    """Customers upsert on (tenant_id, company_id, customer_name).
    Non-unique on purpose — legacy data has dup rows."""
    assert "name='tcid_cname'" in SERVER
    assert "('tenant_id', 1), ('company_id', 1), ('customer_name', 1)" in SERVER
    # Must NOT be unique (would break upserts on tenants with legacy dups).
    cname_block = SERVER.split("name='tcid_cname'")[0].rsplit("db.customers.create_index", 1)[-1]
    assert "unique=True" not in cname_block


# ─── C — Tenant-isolation hardening ───────────────────────────────────
def test_ws_get_status_refuses_empty_tenant():
    """The WebSocket `get_status` handler must refuse to answer when
    tenant_id is empty — otherwise `find_one({'type':'agent_sync'})`
    returns an unrelated tenant's doc (the "all tenants show
    sync-in-progress" bug)."""
    # The handler must branch on `not t_id` and short-circuit.
    assert "if not t_id:" in SYNC
    assert "'tenant_id required'" in SYNC
    # The query must ALWAYS include tenant_id when it runs.
    assert "q = {'type': 'agent_sync', 'tenant_id': t_id}" in SYNC


def test_sync_status_fallback_strips_is_syncing():
    """`/sync/status` fallback (returning the tenant's latest doc when
    the exact (tenant, company) pair has no record) must NOT propagate
    `is_syncing=True` across companies. Only the exact-match path
    can declare a live sync."""
    # Fallback branch sets is_syncing to False explicitly.
    frag = SYNC.split('_fallback_company_mismatch')[1][:400]
    assert 'sync_status["is_syncing"] = False' in frag
    assert 'sync_started_at' in frag  # also stripped


def test_stale_sync_has_absolute_cap():
    """A silent-crashed agent that posted ONE progress event then died
    was leaving `is_syncing=True` forever (the stale ghost doc). An
    absolute 60-min cap backstops the normal 10-min+5-min "both must
    be stale" rule."""
    assert "stale_absolute = age > _td(minutes=60)" in SYNC
    assert "if stale_both or stale_absolute:" in SYNC


# ─── D — Broadcast tenant-scope (regression) ──────────────────────────
def test_all_broadcasts_pass_tenant_id():
    """Every `ws_manager.broadcast(...)` in sync.py must pass
    tenant_id=... as the second arg. Unscoped broadcasts fan out to
    every connected client across tenants."""
    import re
    # Match broadcast calls that do NOT include `tenant_id=`.
    calls = re.findall(r"ws_manager\.broadcast\(\{.*?\}, (.*?)\)", SYNC, flags=re.DOTALL)
    for arg in calls:
        assert "tenant_id=" in arg, f"unscoped broadcast found: {arg[:120]}"
