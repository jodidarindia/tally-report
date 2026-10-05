"""iter-180 — Inventory-list pagination + delete-company completeness.

Three issues reported after a fresh Krishna Sales Corp sync on 5-Oct:

  1. **Inventory page**: 200 SKUs/page but server was fetching ALL
     4200 items + reconciling + deduping + ANOTHER full voucher scan
     + ANOTHER full inventory fetch (for stock-group facets) on
     every page. Measured 36 s for page=1 and TIMEOUT at 120 s for
     page=2. Fix: TTL-cache the fully processed list + skip the
     post-FY adjustment when the FY is the current one + use
     `distinct()` for facets + TTL-cache the last-sale-price map.

  2. **Delete-company purge**: 11 collections (payment_vouchers,
     dispatch_*, salesman_*, agent_commands, etc.) were orphaned
     because the `_COMPANY_DATA_COLLECTIONS` list predated them.
     Fix: audited every collection carrying (tenant_id, company_id)
     and added the missing ones.

  3. **44 s pause between "cached sales locally" and "synced to cloud"
     ack** on the Tally agent log is the backend commit path (fixed
     via P1 iter-178 indexes — just awaiting production deploy).
"""
from pathlib import Path


INV  = Path("/app/backend/routes/inventory.py").read_text(encoding="utf-8")
SYNC = Path("/app/backend/routes/sync.py").read_text(encoding="utf-8")


# ─── 1 — Inventory list caches ─────────────────────────────────────────
def test_processed_list_cache_registered():
    """`_INV_LIST_CACHE` must exist at module scope and be read on
    every /inventory/items hit (so pages 2+ don't re-process)."""
    assert "_INV_LIST_CACHE: dict = {}" in INV
    assert "cached = _INV_LIST_CACHE.get(_it_key)" in INV
    assert "_INV_LIST_CACHE[_it_key] = (now + _INV_CACHE_TTL, all_items)" in INV


def test_last_sale_price_cache_registered():
    """`_LSP_CACHE` must TTL-cache the per-(tenant,company) last-sale
    scan. The scan iterates every sales voucher, so a cold path on a
    4 k-voucher tenant costs ~2 s even projected."""
    assert "_LSP_CACHE: dict = {}" in INV
    assert "_LSP_CACHE[key] = (now + 60.0, seen)" in INV
    # And both caches must be invalidated from the sync write-path.
    assert "_INV_LIST_CACHE.clear()" in INV
    assert "_LSP_CACHE.pop(k, None)" in INV


def test_post_fy_block_short_circuits_on_current_fy():
    """The `if fy:` block below the cache re-fetched 50 k vouchers to
    compute post-FY-end adjustments. For the current FY no vouchers
    can be post-FY-end, so the whole block is a no-op — must be
    short-circuited."""
    assert "if fy and fy != _current_fy:" in INV
    # And when we DO run it, we must project items/voucher_date only.
    assert '_vp = {"_id": 0, "items": 1, "voucher_date": 1, "date": 1}' in INV


def test_stock_groups_use_distinct_not_full_fetch():
    """Stock-group / root-group facets must use `distinct()` instead
    of pulling 50 k inventory docs just to compute two uniques."""
    assert 'db.inventory_items.distinct("stock_group",      base_q)' in INV
    assert 'db.inventory_items.distinct("root_stock_group", base_q)' in INV


def test_list_fetch_uses_projection():
    """The main `inventory_items.find()` below the cache must use a
    small projection — otherwise 4 k rows × full-fat docs blows the
    Atlas round-trip even once per 60 s TTL."""
    frag = INV.split("_INV_LIST_CACHE.get(_it_key)")[1][:1500]
    assert '"_id": 0' in frag and '"item_name": 1' in frag
    # Projection must list specific fields (not `{}` which = everything).
    assert "inventory_items.find(query, _proj)" in frag


# ─── 2 — Delete-company completeness ──────────────────────────────────
def test_delete_company_covers_all_tenant_scoped_collections():
    """Every collection that stores (tenant_id, company_id) scoped
    records must be in `_COMPANY_DATA_COLLECTIONS` so delete-company
    truly wipes the tenant. The 5-Oct bug was 11 collections missed:
    payment_vouchers, dispatch_*, salesman_*, agent_commands,
    sundry_journals, customer_target_removals, ca_report_generations."""
    for coll in (
        "payment_vouchers",
        "sundry_journals",
        "salesman_master",
        "salesman_orders",
        "salesman_beats",
        "beat_runs",
        "dispatch_cards",
        "dispatch_settings",
        "dispatch_porters",
        "dispatch_transporters",
        "dispatch_porter_payments",
        "dispatch_transporter_payments",
        "agent_commands",
        "customer_target_removals",
        "ca_report_generations",
    ):
        assert f'"{coll}"' in SYNC, f"delete-company purge missing {coll}"


def test_sync_status_still_in_company_all_only():
    """`sync_status` must only be dropped by the FULL delete (not by
    resync) — otherwise a resync would nuke the agent-binding
    bootstrap and force the user to log in again from the agent."""
    assert '_COMPANY_ALL_COLLECTIONS = _COMPANY_DATA_COLLECTIONS + ["sync_status", "company_mappings"]' in SYNC
