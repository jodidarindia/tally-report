from fastapi import APIRouter, Request
from typing import Optional
import math
import re
from datetime import datetime
import logging

from db import db
from models import (
    InventoryItem, SalesVoucher, APIResponse,
    PurchaseOrder, PurchaseOrderItem
)
from utils import safe_num, filter_vouchers_by_fy, fy_to_date_range, build_fuzzy_regex
from services.purchase_order_ai import PurchaseOrderAI
from services.tenant_context import get_tenant_context
from services.auth_service import get_current_user
from services.audit_service import log_audit, get_client_ip
from routes.branch_ledgers import get_branch_parties

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_query(ctx, company_id=None, extra=None):
    """Build a tenant-filtered query dict."""
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    cid = company_id or (ctx.get("company_id") if ctx else None)
    if cid:
        q["company_id"] = cid
    if extra:
        q.update(extra)
    return q


async def _get_branch_set(request, ctx):
    """Return set of branch party names if X-Exclude-Branches header is set, else empty set."""
    if request.headers.get("X-Exclude-Branches", "").lower() != "true":
        return set()
    bp = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
    return set(bp) if bp else set()


def _dedupe_inventory_by_name(items: list, fy_hint: Optional[str] = None) -> list:
    """iter-161: collapse Busy's per-FY duplicate inventory rows.

    Busy re-syncs the same physical SKU into every FY .bds file, and each
    row carries the FY-end closing snapshot. Summing those snapshots
    (previous iter-158 behaviour) double-counted stock and value.

    Correct behaviour:
      • If ``fy_hint`` is supplied, restrict to rows tagged with that FY
        (rows missing an ``fy`` field — Tally masters, legacy Busy rows
        — are always kept because they carry the only snapshot we have).
      • Otherwise, per item_name pick the row with the **latest** FY
        (fallback to newest ``last_updated``). No summing across FYs.

    Tally rows have unique item_id per SKU already, so 1-to-1 dedupe
    is a no-op for them.
    """
    from typing import Any
    def _fy_rank(row: dict) -> str:
        # '2026-27' > '2025-26' as a string compare.
        return (row.get("fy") or "") or ""
    def _row_rank(row: dict) -> tuple:
        return (_fy_rank(row), str(row.get("last_updated") or ""))

    # 1) Optional pre-filter by FY. Rows without an ``fy`` field are
    #    kept (Tally masters + legacy Busy rows have no FY tag).
    if fy_hint:
        items = [r for r in items if (not r.get("fy")) or r.get("fy") == fy_hint]

    groups: dict[str, list[dict]] = {}
    for it in items:
        key = ((it.get("item_name") or it.get("alias") or it.get("item_id") or "")
               .strip().lower())
        if not key:
            continue
        groups.setdefault(key, []).append(it)
    out: list[dict[str, Any]] = []
    for _, rows in groups.items():
        if len(rows) == 1:
            out.append(rows[0]); continue
        # Latest FY wins for the closing snapshot; ties broken by last_updated.
        rows_sorted = sorted(rows, key=_row_rank, reverse=True)
        head = dict(rows_sorted[0])
        head["_dedupe_group_size"] = len(rows)
        out.append(head)
    return out


# iter-176 — Per-(tenant, company, fy) 60 s TTL cache for the voucher
# movement aggregation. See `_reconcile_item_quantities` docstring for
# why. On a fresh agent sync, the UI's next poll will miss by at most
# `_RECONCILE_TTL_SEC` seconds — acceptable trade for a 50 k-doc scan
# avoided on every call. `invalidate_reconcile_cache(tenant, company)`
# is also exported so sync writers can drop stale entries proactively.
import time as _rec_time
_RECONCILE_TTL_SEC = 60.0
_RECONCILE_CACHE: dict = {}

# iter-180 — Per-request processed inventory list cache (60 s TTL). See
# `get_inventory_items` for rationale.
_INV_LIST_CACHE: dict = {}

# iter-181 — Per-request /inventory/summary result cache (30 s TTL).
# Dashboard polls this every 60 s per mount; caching the final numbers
# avoids re-doing a 5 s aggregation when the UI merely re-renders.
_SUMMARY_CACHE: dict = {}
_SUMMARY_TTL = 30.0

# iter-181 — Final response cache for the two heaviest analytics
# endpoints. Keyed by (tenant, company, fy, branch_filter_on).
_MOVEMENT_CACHE: dict = {}
_BELOW_COST_CACHE: dict = {}
_ANALYTICS_TTL = 60.0


# iter-181 — Per-(tenant, company, fy) 60 s TTL cache for the FULL voucher
# roll-up (qty + revenue + txn count + first/last date, keyed by lowercased
# item name). Used by movement-analysis and below-cost-sales so neither
# endpoint has to pull 1k-20k full voucher docs over the Atlas wire.
_VOUCHER_ROLLUP_CACHE: dict = {}


async def _get_voucher_rollup_maps(
    tenant_id: str, company_id: str, fy: Optional[str],
) -> tuple:
    """Return (sales_map, purchase_map) where each map is keyed by
    lowercased item name → dict with qty / revenue / txns / first_date /
    last_date / avg_rate. Pushes the $unwind + $group entirely to
    MongoDB so we never pay the Atlas RTT × size cost of pulling every
    voucher document. See iter-181.

    This supersedes the Python aggregation loops in
    /inventory/movement-analysis and /inventory/below-cost-sales which
    were the two slowest endpoints in the whole API (30 s+ at Krishna
    Sales Corp before this change).
    """
    key = (tenant_id or "", company_id or "", fy or "")
    now = _rec_time.monotonic()
    cached = _VOUCHER_ROLLUP_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1], cached[2]

    match: dict = {"tenant_id": tenant_id}
    if company_id:
        match["company_id"] = company_id
    if fy:
        fy_start, fy_end = fy_to_date_range(fy)
        if fy_start:
            match["voucher_date"] = {"$gte": fy_start, "$lte": fy_end}

    pipeline = [
        {"$match": match},
        {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$items.item", ""]}}}},
            "qty": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.quantity", 0]}}}},
            "revenue": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.amount", 0]}}}},
            "rate_qty_sum": {"$sum": {"$multiply": [
                {"$abs": {"$toDouble": {"$ifNull": ["$items.rate", 0]}}},
                {"$abs": {"$toDouble": {"$ifNull": ["$items.quantity", 0]}}},
            ]}},
            "txns": {"$sum": 1},
            "first_date": {"$min": "$voucher_date"},
            "last_date": {"$max": "$voucher_date"},
        }},
    ]

    sales_map: dict = {}
    purchase_map: dict = {}

    # iter-181 — Run the two aggregations in parallel. Previously
    # ``async for row in sales_vouchers.aggregate(...)`` was awaited
    # fully before purchase_vouchers was touched; that paid two Atlas
    # RTTs serially. ``asyncio.gather`` collapses that.
    import asyncio
    async def _collect(coll_cursor_fn, out_map):
        async for row in coll_cursor_fn():
            name = row.get("_id") or ""
            if not name:
                continue
            out_map[name] = {
                "qty": float(row.get("qty") or 0),
                "revenue": float(row.get("revenue") or 0),
                "rate_qty_sum": float(row.get("rate_qty_sum") or 0),
                "txns": int(row.get("txns") or 0),
                "first_date": row.get("first_date") or "",
                "last_date": row.get("last_date") or "",
            }
    await asyncio.gather(
        _collect(lambda: db.sales_vouchers.aggregate(pipeline, allowDiskUse=True), sales_map),
        _collect(lambda: db.purchase_vouchers.aggregate(pipeline, allowDiskUse=True), purchase_map),
    )

    _VOUCHER_ROLLUP_CACHE[key] = (now + _RECONCILE_TTL_SEC, sales_map, purchase_map)
    if len(_VOUCHER_ROLLUP_CACHE) > 256:
        for k, val in list(_VOUCHER_ROLLUP_CACHE.items()):
            if val[0] <= now:
                _VOUCHER_ROLLUP_CACHE.pop(k, None)
    return sales_map, purchase_map


async def _get_voucher_movement_maps(
    tenant_id: str, company_id: str, fy: Optional[str],
) -> tuple:
    """Return (in_qty, out_qty) keyed by lowercased item name, aggregated
    from sales / purchase vouchers for this tenant/company/fy. Served
    from a 60 s in-process cache — see iter-176.

    iter-176b — Server-side aggregation. The prior implementation
    pulled `items[]` arrays for up to 50 k docs per collection into
    Python memory and looped them row-by-row. For 20 k-voucher tenants
    this was gigabytes over the wire and 10-30 s of CPU per call. We
    now push `$unwind` + `$group` into Mongo so the DB does the sum
    using its native indexes (`tcid_vdate` or `tcid_fy`) and ships
    back a few hundred rows (one per SKU) instead of the raw vouchers.
    """
    key = (tenant_id or "", company_id or "", fy or "")
    now = _rec_time.monotonic()
    cached = _RECONCILE_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1], cached[2]

    match: dict = {"tenant_id": tenant_id}
    if company_id:
        match["company_id"] = company_id
    if fy:
        fy_start, fy_end = fy_to_date_range(fy)
        if fy_start:
            # `voucher_date` range covers both the current docs (which
            # also carry an `fy` field) AND legacy docs that only
            # carry the date. The `tcid_vdate` compound index backs
            # this exactly.
            match["voucher_date"] = {"$gte": fy_start, "$lte": fy_end}

    pipeline = [
        {"$match": match},
        {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$items.item", ""]}}}},
            "qty": {"$sum": {"$toDouble": {"$ifNull": ["$items.quantity", 0]}}},
        }},
    ]

    out_qty: dict = {}
    in_qty: dict = {}
    async for row in db.sales_vouchers.aggregate(pipeline, allowDiskUse=True):
        name = row.get("_id") or ""
        if name:
            out_qty[name] = float(row.get("qty") or 0)
    async for row in db.purchase_vouchers.aggregate(pipeline, allowDiskUse=True):
        name = row.get("_id") or ""
        if name:
            in_qty[name] = float(row.get("qty") or 0)

    _RECONCILE_CACHE[key] = (now + _RECONCILE_TTL_SEC, in_qty, out_qty)
    # Opportunistic sweep so the dict doesn't grow unbounded.
    if len(_RECONCILE_CACHE) > 256:
        for k, val in list(_RECONCILE_CACHE.items()):
            if val[0] <= now:
                _RECONCILE_CACHE.pop(k, None)
    return in_qty, out_qty


def invalidate_reconcile_cache(tenant_id: str, company_id: str = "") -> None:
    """Called by the agent sync write-path so a fresh voucher batch is
    reflected in the next inventory read without waiting out the TTL."""
    for k in list(_RECONCILE_CACHE.keys()):
        if k[0] == (tenant_id or "") and (not company_id or k[1] == company_id):
            _RECONCILE_CACHE.pop(k, None)
    # iter-181 — also drop the full roll-up cache used by
    # movement-analysis / below-cost-sales.
    for k in list(_VOUCHER_ROLLUP_CACHE.keys()):
        if k[0] == (tenant_id or "") and (not company_id or k[1] == company_id):
            _VOUCHER_ROLLUP_CACHE.pop(k, None)
    # iter-181 — Also drop the summary cache (per-tenant/company).
    for k in list(_SUMMARY_CACHE.keys()):
        if k[0] == (tenant_id or "") and (not company_id or k[1] == company_id):
            _SUMMARY_CACHE.pop(k, None)
    for k in list(_MOVEMENT_CACHE.keys()):
        if k[0] == (tenant_id or "") and (not company_id or k[1] == company_id):
            _MOVEMENT_CACHE.pop(k, None)
    for k in list(_BELOW_COST_CACHE.keys()):
        if k[0] == (tenant_id or "") and (not company_id or k[1] == company_id):
            _BELOW_COST_CACHE.pop(k, None)
    # iter-180 — Also drop the processed-list cache. Keyed on a hash
    # that doesn't include tenant/company individually, so a tenant-wide
    # sweep is the simplest correct thing (processed-list payloads are
    # small anyway — rebuilding them on demand is cheap).
    _INV_LIST_CACHE.clear()
    # And the last-sale-price map for this tenant/company.
    for k in list(_LSP_CACHE.keys()):
        if k[0] == (tenant_id or "") and (not company_id or k[1] == company_id):
            _LSP_CACHE.pop(k, None)



async def _reconcile_item_quantities(
    items: list, tenant_id: str, company_id: str, fy: Optional[str] = None,
) -> list:
    """iter-165: Trust voucher movement over the Busy agent's D-column
    heuristic for closing quantity.

    **The bug**: Busy agent <= v1.6.1 reads ``closing_qty`` from
    ``max(abs(D11..D50))`` in Folio1. Those D-slots turn out to be
    monthly period-tallies on some Busy 21 builds — so an item that
    received 28 units in month 1 and 16 units in month 2 reports
    ``closing = 44`` even when Busy's own Stock Status shows 16.
    Same class of noise inflates FA00725 from 0 → 2000.

    **The fix** (server-side, no agent rebuild):
        derived_closing = opening_quantity + Σ purchases − Σ sales
    for the same FY. When the derived value diverges from the agent's
    stored quantity by > 0.01, we override — the vouchers are Busy's
    source of truth for movement. When no vouchers exist for an item,
    we keep the agent's value (nothing to reconcile against).

    Called after ``_dedupe_inventory_by_name`` on the Inventory /
    Summary / Movement Analysis / PDF-export endpoints.

    iter-176 — Performance fix. Prior build re-scanned the ENTIRE
    sales_vouchers + purchase_vouchers collections (up to 50 k docs
    EACH, items arrays included) on every single hit of the five
    endpoints above. For tenants with 20 k+ vouchers this pushed each
    call to multi-second Atlas IO and multiplied by ~10×/min of
    frontend polling, saturating the cluster. We now cache the derived
    in_qty / out_qty maps per (tenant, company, fy) for 60 s — fresh
    agent syncs still show up in the UI within one tick, but repeated
    polls in the same minute reuse the map.
    """
    if not items:
        return items
    in_qty, out_qty = await _get_voucher_movement_maps(tenant_id, company_id, fy)
    overrides = 0
    for it in items:
        name = (it.get("item_name") or "").strip().lower()
        if not name:
            continue
        inward = in_qty.get(name, 0.0)
        outward = out_qty.get(name, 0.0)
        # No voucher activity — trust the agent's snapshot.
        if inward == 0 and outward == 0:
            continue
        try:
            opening = float(it.get("opening_quantity") or 0)
            agent_qty = float(it.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
        derived_closing = round(opening + inward - outward, 4)

        # --- SAFETY GUARDS (iter-165) ---
        # (1) Never override with a physically impossible negative closing —
        #     means our purchase-voucher sync is incomplete for that SKU.
        if derived_closing < 0:
            continue
        # (2) Only override when the agent's value looks *inflated* relative
        #     to the derived one. If the agent-supplied qty is <= derived
        #     (undercount), keep the agent's higher value — safer for
        #     stock-out alerts. This catches FA00725 (agent=2000, derived=0)
        #     and LF16303 (agent=44, derived=16) but ignores cases where the
        #     agent already reads the correct D-column.
        if agent_qty <= derived_closing + 0.01:
            continue
        # (3) If we only ever saw outward and no inward, derived is
        #     capped at ``opening`` — that's fine because we still
        #     satisfied guard (2).

        it["_agent_quantity"] = agent_qty
        it["quantity"] = derived_closing
        # Re-derive closing_value from the new qty at the same rate.
        rate = float(it.get("cost_price") or it.get("price") or 0)
        if rate > 0:
            it["closing_value"] = round(derived_closing * rate, 2)
        overrides += 1

    if overrides:
        logger.info(
            f"iter-165 reconciled {overrides}/{len(items)} items from vouchers "
            f"(tenant={tenant_id[:8]}, company={company_id[:8] if company_id else '-'}, fy={fy})"
        )
    return items


async def _get_purchase_branch_set(ctx):
    """Detect branch-like parties in purchase vouchers (non-sundry-creditor).
    These are internal transfers, not actual procurement from external suppliers.

    iter-132 hardening: require ALL company-name tokens (>3 chars) to appear
    in the party name — not just 2+. The 2+ heuristic misfired for
    company names with common words like "India" that many external
    suppliers also carry ("Bosch India", "Motul India"), silently
    flagging every supplier as a branch → all Inward columns showed 0
    in Movement Analysis. Also skip the filter entirely for
    single-token company names (nothing safe to match against).
    """
    from services.id_mapping_service import get_company_name
    if not ctx:
        return set()
    tenant_id = ctx.get("tenant_id", "")
    company_id = ctx.get("company_id", "")
    company_name = await get_company_name(tenant_id, company_id)
    if not company_name:
        return set()
    name_clean = re.sub(r'\b(private|limited|pvt|ltd|llp|inc|corp)\b', '', company_name, flags=re.IGNORECASE).strip()
    tokens = [w.lower() for w in name_clean.split() if len(w) > 3]
    # iter-132: require at least 2 distinct tokens AND every one of them
    # to appear in the party name (was: "2+ matching", which caught any
    # supplier sharing 2 common words like "india autotech").
    if len(tokens) < 2:
        return set()
    parties = await db.purchase_vouchers.distinct(
        "party_name",
        {"tenant_id": tenant_id, "company_id": company_id}
    )
    branch_parties = set()
    for party in parties:
        if not party:
            continue
        party_lower = party.lower()
        if all(t in party_lower for t in tokens):
            branch_parties.add(party)
    return branch_parties


def _filter_branch_vouchers(vouchers, branch_set):
    """Filter out vouchers whose party_name is in branch_set."""
    if not branch_set:
        return vouchers
    return [v for v in vouchers if v.get("party_name") not in branch_set]


_LSP_CACHE: dict = {}


async def _last_sale_price_map(query: dict) -> dict:
    """Build a {item_name_lower: {price, date, voucher_no}} map from the
    most recent sales voucher line per item.

    Used as a fallback when Tally master STANDARDPRICE is unset — surfaces
    the actual last selling rate to the salesman / inventory UI without
    requiring the user to fill STDPRICE for thousands of items.

    Rate per line is derived as `rate` if present, else `amount/quantity`.
    Credit notes / returns are NOT used (they're recorded in
    credit_note_vouchers, not sales_vouchers).

    iter-180 — 60 s TTL cache per (tenant_id, company_id). The scan
    iterates every sales voucher in the collection to collect
    last-seen rates per SKU; running this on every `/inventory/items`
    call was the second-biggest contributor to the 30 s page load.
    """
    import time as _it
    key = (str(query.get("tenant_id") or ""), str(query.get("company_id") or ""))
    now = _it.monotonic()
    cached = _LSP_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    cursor = db.sales_vouchers.find(
        query,
        {"_id": 0, "voucher_date": 1, "voucher_number": 1, "items": 1},
    ).sort("voucher_date", -1)
    seen: dict = {}
    async for v in cursor:
        vdate = v.get("voucher_date") or ""
        vno = v.get("voucher_number") or ""
        for vi in v.get("items") or []:
            name = (vi.get("item") or vi.get("item_name") or "").strip().lower()
            if not name or name in seen:
                continue
            qty = abs(safe_num(vi.get("quantity")))
            rate = safe_num(vi.get("rate"))
            if rate <= 0:
                amt = abs(safe_num(vi.get("amount") or vi.get("value") or 0))
                if qty > 0 and amt > 0:
                    rate = round(amt / qty, 2)
            if rate > 0:
                seen[name] = {
                    "price": rate,
                    "date": vdate,
                    "voucher_no": vno,
                }
    _LSP_CACHE[key] = (now + 60.0, seen)
    if len(_LSP_CACHE) > 256:
        for k, v in list(_LSP_CACHE.items()):
            if v[0] <= now:
                _LSP_CACHE.pop(k, None)
    return seen


@router.patch("/inventory/items/{item_id}/abc")
async def set_abc_category(request: Request, item_id: str):
    """Set A/B/C/D classification for a single inventory item.
    Body: { "abc_category": "A" | "B" | "C" | "D" | "" }  (empty unsets)
    """
    try:
        ctx = await get_tenant_context(request)
        body = await request.json()
        cat = (body.get("abc_category") or "").strip().upper()
        if cat and cat not in ("A", "B", "C", "D"):
            return APIResponse(success=False, error="abc_category must be A, B, C, or D")
        q = _build_query(ctx, body.get("company_id"))
        update = {"$set": {"abc_category": cat}} if cat else {"$unset": {"abc_category": ""}}
        result = await db.inventory_items.update_one({**q, "item_id": item_id}, update)
        if result.matched_count == 0:
            # Try by item_name fallback (item_id sometimes is the name)
            result = await db.inventory_items.update_one({**q, "item_name": item_id}, update)
        # iter-181 — drop the processed inventory-list cache so the UI
        # sees the new ABC tag on its next poll.
        _INV_LIST_CACHE.clear()
        return APIResponse(success=True, data={"matched": result.matched_count, "modified": result.modified_count})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/inventory/abc/auto-assign")
async def auto_assign_abc(request: Request):
    """Bulk-assign A/B/C/D using Pareto / 80-15-4-1 rule on FY revenue:
       A = top 80% of revenue, B = next 15%, C = next 4%, D = remainder.
    Body: { "fy": "2026-27", "company_id": "..." }
    """
    try:
        from pymongo import UpdateOne
        ctx = await get_tenant_context(request)
        body = await request.json()
        fy = body.get("fy") or ""
        q = _build_query(ctx, body.get("company_id"))

        # Pull sales vouchers and tally per item_name (FY-scoped if provided).
        # Stream the cursor instead of loading 50k docs into memory at once —
        # this matters on small (512 MB) droplets where Atlas latency
        # multiplies fast. Only the two fields we actually need are pulled.
        cursor = db.sales_vouchers.find(q, {"_id": 0, "voucher_date": 1, "items": 1})
        sales = await cursor.to_list(100000)
        if fy:
            from utils import filter_vouchers_by_fy
            sales = filter_vouchers_by_fy(sales, fy)
        from collections import defaultdict
        rev_by_item = defaultdict(float)
        for v in sales:
            for vi in v.get("items", []) or []:
                iname = (vi.get("item") or vi.get("item_name") or "").strip().lower()
                if not iname:
                    continue
                rev_by_item[iname] += abs(safe_num(vi.get("amount") or vi.get("value") or 0))

        total_rev = sum(rev_by_item.values())
        if total_rev <= 0:
            return APIResponse(success=False,
                                error=f"No sales revenue found in FY {fy or '(all)'} for this company. "
                                       "If you just synced data, wait for the agent's full sync to "
                                       "complete and try again.")

        # Sort items by revenue descending, then assign A/B/C/D by cumulative %
        sorted_items = sorted(rev_by_item.items(), key=lambda x: -x[1])
        cum = 0.0
        item_to_abc = {}
        for iname, rev in sorted_items:
            cum += rev
            pct = cum / total_rev * 100
            if pct <= 80:
                item_to_abc[iname] = "A"
            elif pct <= 95:
                item_to_abc[iname] = "B"
            elif pct <= 99:
                item_to_abc[iname] = "C"
            else:
                item_to_abc[iname] = "D"

        # Build a single bulk_write op list. Previously this fired one
        # MongoDB round-trip per item — on a company with 7,500+ stock
        # items, that took ~20 minutes and timed out at the nginx
        # proxy_read_timeout. Bulk-write brings it down to a few seconds.
        all_inv = await db.inventory_items.find(q, {"_id": 0, "item_id": 1, "item_name": 1}).to_list(100000)
        ops = []
        counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for it in all_inv:
            iname = (it.get("item_name") or "").strip().lower()
            cat = item_to_abc.get(iname, "D")  # zero-revenue items → D
            counts[cat] += 1
            ops.append(UpdateOne(
                {**q, "item_id": it.get("item_id")},
                {"$set": {"abc_category": cat}},
            ))

        modified = 0
        if ops:
            # ordered=False so a single bad doc can't abort the whole batch,
            # and Mongo can parallelise internally for speed.
            CHUNK = 1000  # keep each batch under Mongo's 100k op cap with margin
            for i in range(0, len(ops), CHUNK):
                result = await db.inventory_items.bulk_write(ops[i:i + CHUNK], ordered=False)
                modified += result.modified_count

        # iter-181 — drop the processed inventory-list cache so the UI's
        # next /inventory/items poll surfaces the fresh A/B/C/D tags.
        _INV_LIST_CACHE.clear()

        return APIResponse(success=True, data={
            "counts": counts,
            "modified": modified,
            "total_items": len(all_inv),
        })
    except Exception as e:
        logger.exception(f"ABC auto-assign error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/category-sales")
async def category_sales_drill(request: Request, abc: str, fy: Optional[str] = None, company_id: Optional[str] = None):
    """For an ABC category, return:
      - items in that category with FY qty + revenue
      - per-item top customers (qty + revenue)
    Used by the Inventory Analytics "Category Sales" tab.

    Honors the 'X-Exclude-Branches: true' header — branch transfers are
    excluded from both totals and customer breakdowns.
    """
    try:
        from collections import defaultdict
        from utils import filter_vouchers_by_fy
        from routes.branch_ledgers import get_branch_parties
        ctx = await get_tenant_context(request)
        cat = (abc or "").upper().strip()
        if cat not in ("A", "B", "C", "D"):
            return APIResponse(success=False, error="abc must be A, B, C, or D")
        q = _build_query(ctx, company_id)

        # Branch exclusion (driven by global navbar toggle via X-Exclude-Branches header)
        exclude_branches = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        branch_set = set()
        if exclude_branches:
            tid = (ctx or {}).get("tenant_id") or ""
            cid = (ctx or {}).get("company_id") or company_id or ""
            bp = await get_branch_parties(tid, cid)
            branch_set = {p.lower().strip() for p in bp}

        # Last-sale-price fallback (when Tally master STDPRICE is unset)
        try:
            lsp = await _last_sale_price_map(q)
        except Exception:
            lsp = {}

        items = await db.inventory_items.find({**q, "abc_category": cat},
                                               {"_id": 0, "item_id": 1, "item_name": 1,
                                                "part_number": 1, "stock_group": 1,
                                                "quantity": 1, "price": 1, "standard_price": 1}).to_list(5000)
        if not items:
            return APIResponse(success=True, data={"abc": cat, "items": [], "summary": {"items": 0, "revenue": 0, "qty": 0}})

        sales = await db.sales_vouchers.find(q, {"_id": 0, "voucher_date": 1, "party_name": 1, "items": 1}).to_list(50000)
        if fy:
            sales = filter_vouchers_by_fy(sales, fy)

        # Aggregate per-item: total qty/revenue + per-customer breakdown + frequency
        per_item = {}
        for it in items:
            iname_lc = (it.get("item_name") or "").lower().strip()
            entry = lsp.get(iname_lc) or {}
            per_item[iname_lc] = {
                "item_name": it.get("item_name", ""),
                "part_number": it.get("part_number", ""),
                "stock_group": it.get("stock_group", ""),
                "current_stock": safe_num(it.get("quantity")),
                "standard_price": safe_num(it.get("standard_price")),
                "last_sale_price": safe_num(entry.get("price", 0)),
                "last_sale_date": entry.get("date", ""),
                "total_qty": 0.0,
                "total_revenue": 0.0,
                "order_count": 0,
                "customers": defaultdict(lambda: {"qty": 0.0, "revenue": 0.0, "count": 0}),
            }

        for v in sales:
            party = (v.get("party_name") or "").strip()
            # Skip branch transfers entirely when toggle is on
            if branch_set and party.lower() in branch_set:
                continue
            for vi in v.get("items", []) or []:
                iname = (vi.get("item") or vi.get("item_name") or "").strip().lower()
                if iname not in per_item:
                    continue
                qty = abs(safe_num(vi.get("quantity")))
                rev = abs(safe_num(vi.get("amount") or vi.get("value") or 0))
                row = per_item[iname]
                row["total_qty"] += qty
                row["total_revenue"] += rev
                row["order_count"] += 1
                if party:
                    cb = row["customers"][party]
                    cb["qty"] += qty
                    cb["revenue"] += rev
                    cb["count"] += 1

        # Finalize: convert customers dict to sorted list, aggregate totals
        result_items = []
        sum_rev = 0.0
        sum_qty = 0.0
        for row in per_item.values():
            top_customers = sorted(
                [{"customer_name": k, "qty": round(v["qty"], 2),
                  "revenue": round(v["revenue"], 2), "count": v["count"]}
                 for k, v in row["customers"].items()],
                key=lambda x: -x["revenue"],
            )[:10]
            sum_rev += row["total_revenue"]
            sum_qty += row["total_qty"]
            result_items.append({
                "item_name": row["item_name"],
                "part_number": row["part_number"],
                "stock_group": row["stock_group"],
                "current_stock": row["current_stock"],
                "standard_price": row["standard_price"],
                "last_sale_price": row["last_sale_price"],
                "last_sale_date": row["last_sale_date"],
                "total_qty": round(row["total_qty"], 2),
                "total_revenue": round(row["total_revenue"], 2),
                "order_count": row["order_count"],
                "top_customers": top_customers,
            })
        result_items.sort(key=lambda x: -x["total_revenue"])

        return APIResponse(success=True, data={
            "abc": cat, "fy": fy, "items": result_items,
            "summary": {"items": len(result_items),
                        "revenue": round(sum_rev, 2),
                        "qty": round(sum_qty, 2)},
        })
    except Exception as e:
        import traceback
        logger.error(f"Category sales error: {e}\n{traceback.format_exc()}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/items")
async def get_inventory_items(
    request: Request,
    category: Optional[str] = None,
    stock_group: Optional[str] = None,
    root_stock_group: Optional[str] = None,
    min_quantity: Optional[float] = None,
    company_id: Optional[str] = None,
    fy: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 0,  # 0 = no pagination (legacy callers); set to enable
):
    try:
        ctx = await get_tenant_context(request)
        extra = {}
        if category and category != 'all':
            extra["category"] = category
        if stock_group and stock_group != 'all':
            # iter-111: accept a CSV list ('Group A,Group B') for multi-select.
            # Single-value calls keep their original behaviour (back-compat).
            groups = [g.strip() for g in stock_group.split(',') if g.strip()]
            if len(groups) == 1:
                extra["stock_group"] = groups[0]
            elif len(groups) > 1:
                extra["stock_group"] = {"$in": groups}
        if root_stock_group and root_stock_group != 'all':
            # v9.8.6 — Primary (root) Tally stock-group filter. Falls back to
            # exact-match on stock_group if no items have root_stock_group
            # populated yet (older agent versions). Lower-cased on storage.
            extra["root_stock_group"] = root_stock_group.lower().strip()
        if min_quantity is not None:
            extra["quantity"] = {"$gte": min_quantity}
        if search and search.strip():
            # Fuzzy search — ignores spaces & separator chars (- / ( ) ! : . , & _ ' ")
            # so "tvs 10" matches "TVS-10", "TVS(10)", "TVS/10", etc.
            # v9.8.7 — alias array is matched element-wise via $regex on the
            # array (Mongo evaluates regex against each string in the array).
            fuzzy = build_fuzzy_regex(search)
            if fuzzy:
                extra["$or"] = [
                    {"item_name": {"$regex": fuzzy, "$options": "i"}},
                    {"part_number": {"$regex": fuzzy, "$options": "i"}},
                    {"aliases": {"$regex": fuzzy, "$options": "i"}},
                ]

        query = _build_query(ctx, company_id, extra)
        # iter-180 — Processed-list TTL cache. The dedupe + reconcile
        # pipeline below is O(N) over the full item set (~4200 rows for
        # Krishna Sales Corp) and used to run on EVERY page request —
        # a 37 s hit for page 1 and TIMEOUT for page 2 was reported on
        # 5-Oct. We now cache the FULLY PROCESSED list for 60 s per
        # (tenant, company, fy + the filter keys) so pagination hops
        # are instant.
        import time as _it, hashlib as _ih, json as _ij
        _it_key = _ih.md5(_ij.dumps({
            "t": ctx.get("tenant_id", ""),
            "c": ctx.get("company_id", "") or "",
            "fy": fy or "",
            "cat": category or "",
            "sg": stock_group or "",
            "rsg": root_stock_group or "",
            "mq": min_quantity,
            "s": (search or "").strip().lower(),
        }, sort_keys=True).encode()).hexdigest()
        _INV_CACHE_TTL = 60.0
        now = _it.monotonic()
        cached = _INV_LIST_CACHE.get(_it_key)
        if cached and cached[0] > now:
            all_items = cached[1]
        else:
            # iter-180 — Projection to drop heavy per-item fields we
            # don't need on the list screen (unit_history, folio_rows,
            # tag_lists). Shrinks the Atlas round-trip payload ~5× on
            # 4200-item tenants.
            # iter-181 — Also project `abc_category` + `item_id` so the
            # list screen shows A/B/C/D chips after auto-assign. Omission
            # of these two was the "ABC tag not showing" bug.
            _proj = {
                "_id": 0, "item_id": 1, "item_name": 1, "part_number": 1, "aliases": 1,
                "category": 1, "stock_group": 1, "root_stock_group": 1,
                "quantity": 1, "closing_value": 1, "cost_price": 1,
                "price": 1, "mrp": 1, "unit": 1, "reorder_level": 1,
                "fy": 1, "last_updated": 1, "hsn_code": 1, "gst_rate": 1,
                "opening_quantity": 1, "opening_value": 1,
                "abc_category": 1,
            }
            all_items = await db.inventory_items.find(query, _proj).to_list(None)
            all_items = _dedupe_inventory_by_name(all_items, fy_hint=fy)
            # iter-165: reconcile closing_qty from actual voucher
            # movement. The voucher-movement map is itself cached per
            # iter-176, so this step is cheap even uncached.
            all_items = await _reconcile_item_quantities(
                all_items, ctx.get("tenant_id", ""), ctx.get("company_id", "") or "", fy,
            )
            _INV_LIST_CACHE[_it_key] = (now + _INV_CACHE_TTL, all_items)
            # Opportunistic sweep.
            if len(_INV_LIST_CACHE) > 256:
                for k, v in list(_INV_LIST_CACHE.items()):
                    if v[0] <= now:
                        _INV_LIST_CACHE.pop(k, None)
        total = len(all_items)
        if page_size and page_size > 0:
            skip = max(0, (page - 1) * page_size)
            items = all_items[skip:skip + page_size]
        else:
            items = all_items

        # If FY is specified, compute closing stock for that FY from vouchers.
        # iter-180 — Short-circuit when the requested FY is the current
        # or latest FY: post-FY vouchers can't exist yet, so the
        # adjustment is a no-op. This block used to re-scan ALL sales
        # + purchase vouchers (another 50 k docs, no projection!) on
        # every inventory page load — adding 30 s on top of the main
        # fetch for Krishna Sales Corp.
        from utils import get_current_fy as _get_cur_fy
        _current_fy = _get_cur_fy()
        if fy and fy != _current_fy:
            base_q = _build_query(ctx, company_id)
            # Project only the fields we read in the loop below.
            _vp = {"_id": 0, "items": 1, "voucher_date": 1, "date": 1}
            sales_v = await db.sales_vouchers.find(base_q, _vp).to_list(50000)
            purchase_v = await db.purchase_vouchers.find(base_q, _vp).to_list(50000)

            # Apply branch filter
            branch_set = await _get_branch_set(request, ctx)
            sales_v = _filter_branch_vouchers(sales_v, branch_set)
            purchase_v = _filter_branch_vouchers(purchase_v, branch_set)

            # FY end date
            fy_end_year = int(fy.split('-')[0]) + 1 if '-' in fy else 2027
            fy_end_date = f"{fy_end_year}-03-31"

            # For the selected FY, closing = current_stock + sales_after_fy - purchases_after_fy
            from collections import defaultdict
            post_fy_sold = defaultdict(float)
            post_fy_purchased = defaultdict(float)
            for v in sales_v:
                vdate = v.get("voucher_date", v.get("date", ""))
                if vdate > fy_end_date:
                    for vi in v.get("items", []):
                        iname = (vi.get("item", "") or "").strip().lower()
                        post_fy_sold[iname] += abs(safe_num(vi.get("quantity", 0)))
            for v in purchase_v:
                vdate = v.get("voucher_date", v.get("date", ""))
                if vdate > fy_end_date:
                    for vi in v.get("items", []):
                        iname = (vi.get("item", "") or "").strip().lower()
                        post_fy_purchased[iname] += abs(safe_num(vi.get("quantity", 0)))

            for item in items:
                iname = (item.get("item_name") or "").strip().lower()
                current_qty = safe_num(item.get("quantity"))
                # Closing of FY = current_qty + post_fy_sales - post_fy_purchases
                fy_closing = current_qty + post_fy_sold.get(iname, 0) - post_fy_purchased.get(iname, 0)
                item["quantity"] = round(fy_closing, 2)
                # Recalc value
                price = safe_num(item.get("price"))
                item["closing_value"] = round(fy_closing * price, 2)

        base_q = _build_query(ctx, company_id)
        # iter-180 — Use native `distinct()` instead of pulling 50 k docs
        # just to compute unique stock_groups. Mongo rides the
        # `tcid_sgrp` compound index for this and ships back ~30 strings
        # instead of 14 k objects.
        stock_groups_raw   = await db.inventory_items.distinct("stock_group",      base_q)
        root_groups_raw    = await db.inventory_items.distinct("root_stock_group", base_q)
        stock_groups       = sorted(sg for sg in stock_groups_raw if sg)
        root_stock_groups  = sorted({(sg or "").strip() for sg in root_groups_raw if (sg or "").strip()})

        # Last-Sale-Price fallback: when Tally master STANDARDPRICE is unset
        # (standard_price <= 0), surface the most recent sale rate from
        # sales_vouchers so the UI / salesman catalog still has a usable price.
        # Tally master always wins when present.
        try:
            lsp = await _last_sale_price_map(base_q)
        except Exception as e:
            logger.warning(f"last-sale-price computation failed (non-fatal): {e}")
            lsp = {}
        for item in items:
            name = (item.get("item_name") or "").strip().lower()
            entry = lsp.get(name)
            if entry:
                item["last_sale_price"] = entry["price"]
                item["last_sale_date"] = entry["date"]
                item["last_sale_invoice"] = entry["voucher_no"]
            else:
                item["last_sale_price"] = 0
                item["last_sale_date"] = ""
                item["last_sale_invoice"] = ""
            # Effective sale price = Tally master if set, else last sale
            sp = safe_num(item.get("standard_price"))
            if sp > 0:
                item["effective_sale_price"] = sp
                item["sale_price_source"] = "tally_master"
            elif item["last_sale_price"] > 0:
                item["effective_sale_price"] = item["last_sale_price"]
                item["sale_price_source"] = "last_sale"
            else:
                item["effective_sale_price"] = 0
                item["sale_price_source"] = "unset"

        return APIResponse(
            success=True,
            data={
                "items": items,
                "count": len(items),
                "total": total if total is not None else len(items),
                "page": page if page_size else 1,
                "page_size": page_size if page_size else len(items),
                "stock_groups": stock_groups,
                "root_stock_groups": root_stock_groups,
            }
        )
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/summary")
async def get_inventory_summary(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        import asyncio
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        tenant_id = ctx.get("tenant_id", "")
        company_id_ctx = ctx.get("company_id", "") or ""

        # iter-181 — Serve from a short TTL cache so dashboard polling
        # (every 60 s on the Dashboard page + every nav mount) doesn't
        # re-chew the same aggregation. Invalidated by sync writers.
        now = _rec_time.monotonic()
        _sum_key = (tenant_id, company_id_ctx or (company_id or ""), fy or "")
        cached = _SUMMARY_CACHE.get(_sum_key)
        if cached and cached[0] > now:
            return APIResponse(success=True, data=cached[1])

        # iter-181 — Run the three independent Mongo queries in
        # parallel instead of sequentially. On Atlas with ~235 ms RTT
        # the serial version spent 3 × RTT just waiting on round-trips;
        # asyncio.gather collapses that to one wall-time RTT.
        q_fy = dict(q)
        if fy:
            q_fy["fy"] = fy

        async def _fetch_items():
            # Projection trims payload by ~40% and shaves another
            # ~1 s on Atlas. Only pull fields actually consumed.
            return await db.inventory_items.find(
                q, {
                    "_id": 0, "item_name": 1, "item_id": 1, "quantity": 1,
                    "price": 1, "cost_price": 1, "closing_value": 1,
                    "reorder_level": 1, "category": 1, "fy": 1,
                    "last_updated": 1, "aliases": 1,
                },
            ).to_list(50000)

        async def _fetch_fy_sales():
            # Server-side sum instead of cursor-iterating 10 k docs.
            pipeline = [
                {"$match": q_fy},
                {"$group": {"_id": None, "total": {"$sum": {"$toDouble": {"$ifNull": ["$total_amount", 0]}}}}},
            ]
            total = 0.0
            async for r in db.sales_vouchers.aggregate(pipeline):
                total = float(r.get("total") or 0)
            # Legacy fallback: for vouchers tagged by `voucher_date`
            # only (no `fy` field), run a second pass with the text
            # filter the shared helper uses.
            if fy and total == 0:
                legacy_pipeline = [
                    {"$match": {**q, "fy": {"$exists": False}}},
                    {"$group": {"_id": None, "total": {"$sum": {"$toDouble": {"$ifNull": ["$total_amount", 0]}}},
                                "all": {"$push": {"d": "$voucher_date", "a": "$total_amount"}}}},
                ]
                async for r in db.sales_vouchers.aggregate(legacy_pipeline):
                    for e in r.get("all", []):
                        vd = str(e.get("d") or "")
                        if fy in vd or fy.replace("-", "") in vd:
                            total += float(e.get("a") or 0)
            return total

        items, (_in_qty, _out_qty), fy_sales_value = await asyncio.gather(
            _fetch_items(),
            _get_voucher_movement_maps(tenant_id, company_id_ctx, fy),
            _fetch_fy_sales(),
        )

        # iter-161: FY-scope inventory rows so each item's closing snapshot
        # comes from the correct FY .bds file (Busy re-syncs the same SKU
        # into every FY). Rows without an ``fy`` tag (Tally masters) are
        # always kept — they carry the only snapshot we have.
        items = _dedupe_inventory_by_name(items, fy_hint=fy)
        # iter-165: voucher-derived closing overrides agent's D-column
        # heuristic when they diverge (FA00725 / LF16303 class bug).
        # Pass pre-fetched maps to avoid an extra round-trip inside the
        # reconciler (it would otherwise re-call _get_voucher_movement_maps
        # which is cached but still ~ms of overhead).
        items = await _reconcile_item_quantities(
            items, tenant_id, company_id_ctx, fy,
        )
        total_items = len(items)

        if not items:
            data = {"total_items": 0, "total_value": 0, "low_stock_items": 0, "categories": [], "fy_sales_value": round(fy_sales_value, 2)}
            _SUMMARY_CACHE[_sum_key] = (now + _SUMMARY_TTL, data)
            return APIResponse(success=True, data=data)

        # iter-158: prefer cost_price for valuation (matches Busy's
        # weighted-avg Cl. Amt.). Only fall back to closing_value when
        # cost_price is missing, and to qty*price as a last resort.
        total_value = 0.0
        for item in items:
            qty  = safe_num(item.get("quantity"))
            cost = safe_num(item.get("cost_price"))
            if qty > 0 and cost > 0:
                total_value += qty * cost
            else:
                cv = safe_num(item.get("closing_value"))
                if cv > 0:
                    total_value += cv
                else:
                    total_value += qty * safe_num(item.get("price"))

        active_items = set(_out_qty.keys())

        low_stock_items = 0
        for item in items:
            qty = safe_num(item.get("quantity"))
            name = (item.get("item_name") or "").lower()
            reorder = safe_num(item.get("reorder_level"))
            if qty > 0 and reorder > 0 and qty < reorder:
                low_stock_items += 1
            elif qty == 0 and name in active_items:
                # Out of stock but actively sold — flag as low stock
                low_stock_items += 1

        categories = list(set(item.get("category") for item in items if item.get("category")))

        data = {
            "total_items": total_items,
            "total_value": round(total_value, 2),
            "low_stock_items": low_stock_items,
            "categories": categories,
            "fy_sales_value": round(fy_sales_value, 2),
        }
        _SUMMARY_CACHE[_sum_key] = (now + _SUMMARY_TTL, data)
        # Opportunistic sweep
        if len(_SUMMARY_CACHE) > 256:
            for k, val in list(_SUMMARY_CACHE.items()):
                if val[0] <= now:
                    _SUMMARY_CACHE.pop(k, None)
        return APIResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Error getting inventory summary: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/inventory/generate-purchase-order")
async def generate_purchase_order(request: Request, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        # iter-161: FY-scope so PO recommendation uses correct current stock.
        inventory_items = _dedupe_inventory_by_name(inventory_items)
        sales_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)

        po_ai = PurchaseOrderAI()
        result = await po_ai.generate_purchase_order(inventory_items, sales_vouchers)

        if result.get("success"):
            po_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            po_data = result.get("purchase_order", {})

            po_items = []
            for item in po_data.get("urgent_items", po_data.get("items", [])):
                try:
                    po_items.append(PurchaseOrderItem(**item))
                except Exception:
                    po_items.append(PurchaseOrderItem(
                        item_name=str(item.get("item_name", item.get("name", "Unknown"))),
                        current_stock=safe_num(item.get("current_stock")),
                        recommended_quantity=safe_num(item.get("recommended_quantity", item.get("quantity", 0))),
                        priority=str(item.get("priority", "medium")),
                        reason=str(item.get("reason", "")),
                        estimated_cost=safe_num(item.get("estimated_cost", item.get("cost", 0)))
                    ))

            purchase_order = PurchaseOrder(
                po_number=po_number,
                items=po_items,
                total_items=len(po_items),
                total_cost=po_data.get("total_estimated_cost", sum(i.estimated_cost for i in po_items)),
                ai_analysis=po_data.get("analysis", ""),
                status="draft"
            )

            doc = purchase_order.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.purchase_orders.insert_one(doc)

            return APIResponse(
                success=True,
                data=po_data,
                message=f"Purchase order {po_number} generated"
            )
        else:
            return APIResponse(success=False, error=result.get("error"))
    except Exception as e:
        logger.error(f"Error generating purchase order: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/purchase-orders")
async def get_purchase_orders(request: Request, status: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        extra = {}
        if status:
            extra["status"] = status
        query = _build_query(ctx, company_id, extra)
        pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return APIResponse(success=True, data={"purchase_orders": pos, "count": len(pos)})
    except Exception as e:
        logger.error(f"Error fetching purchase orders: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/sales-frequency")
async def get_sales_frequency(request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        branch_set = await _get_branch_set(request, ctx)
        all_vouchers = _filter_branch_vouchers(all_vouchers, branch_set)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

        if start_date or end_date:
            filtered_vouchers = []
            for v in sales_vouchers:
                v_date = v.get("voucher_date", "")
                if start_date and v_date < start_date:
                    continue
                if end_date and v_date > end_date:
                    continue
                filtered_vouchers.append(v)
            sales_vouchers = filtered_vouchers

        item_stats = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = safe_num(item.get("quantity"))

                if item_name not in item_stats:
                    item_stats[item_name] = {
                        "item_name": item_name,
                        "total_quantity_sold": 0,
                        "transaction_count": 0,
                        "unique_customers": set(),
                        "total_revenue": 0
                    }

                item_stats[item_name]["total_quantity_sold"] += qty
                item_stats[item_name]["transaction_count"] += 1
                item_stats[item_name]["unique_customers"].add(party)
                item_stats[item_name]["total_revenue"] += qty * safe_num(item.get("rate"))

        frequency_data = []
        for item_name, stats in item_stats.items():
            frequency_data.append({
                "item_name": item_name,
                "total_quantity_sold": stats["total_quantity_sold"],
                "transaction_count": stats["transaction_count"],
                "unique_customers": len(stats["unique_customers"]),
                "total_revenue": round(stats["total_revenue"], 2),
                "avg_quantity_per_transaction": round(
                    stats["total_quantity_sold"] / stats["transaction_count"], 1
                ) if stats["transaction_count"] > 0 else 0,
                "customer_list": list(stats["unique_customers"])
            })

        frequency_data.sort(key=lambda x: x["transaction_count"], reverse=True)

        return APIResponse(success=True, data={"frequency": frequency_data, "total_items": len(frequency_data)})
    except Exception as e:
        logger.error(f"Error getting sales frequency: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/movement-analysis")
async def get_inventory_movement(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        # iter-181 — Short TTL response cache. This endpoint is called
        # on every Inventory Analytics page mount and is the single
        # most expensive endpoint we expose. Cache invalidated on sync.
        tenant_id_c = ctx.get("tenant_id", "")
        company_id_c = ctx.get("company_id", "") or (company_id or "")
        branch_on = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        _mv_key = (tenant_id_c, company_id_c, fy or "", branch_on)
        now_c = _rec_time.monotonic()
        cached = _MOVEMENT_CACHE.get(_mv_key)
        if cached and cached[0] > now_c:
            return APIResponse(success=True, data=cached[1])

        # Guard: if the requested FY is entirely BEFORE the earliest synced voucher,
        # there's no data to display. Returning today's master quantities would
        # incorrectly suggest stock levels for an un-synced period.
        if fy:
            try:
                fy_start_str, fy_end_str = fy_to_date_range(fy)
            except Exception:
                fy_start_str = fy_end_str = None
            if fy_start_str and fy_end_str:
                earliest = await db.sales_vouchers.find(q, {"_id": 0, "voucher_date": 1}).sort("voucher_date", 1).limit(1).to_list(1)
                earliest_purch = await db.purchase_vouchers.find(q, {"_id": 0, "voucher_date": 1}).sort("voucher_date", 1).limit(1).to_list(1)
                earliest_voucher = None
                for d in (earliest, earliest_purch):
                    if d and d[0].get("voucher_date"):
                        ev = d[0]["voucher_date"]
                        if earliest_voucher is None or ev < earliest_voucher:
                            earliest_voucher = ev
                if earliest_voucher and earliest_voucher > fy_end_str:
                    # Requested FY ends BEFORE the earliest synced voucher → no data
                    return {
                        "items": [],
                        "summary": {
                            "total_items": 0,
                            "total_opening_stock": 0,
                            "total_inward": 0,
                            "total_sales_qty": 0,
                            "total_closing_stock": 0,
                            "total_revenue": 0,
                            "fast_moving_count": 0,
                            "slow_moving_count": 0,
                            "dead_stock_count": 0,
                            "fy_days": 0,
                        },
                        "notices": [
                            f"FY {fy} was not synced from Tally (earliest synced voucher: "
                            f"{earliest_voucher}). Movement Analysis is empty for this FY."
                        ],
                        "fy_synced": False,
                        "earliest_voucher_date": earliest_voucher,
                    }

        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        # iter-161: FY-scope inventory rows so opening/closing snapshots
        # aren't summed across FYs.
        inventory_items = _dedupe_inventory_by_name(inventory_items, fy_hint=fy)
        # iter-165: reconcile from vouchers so Movement Analysis's
        # opening = closing + sales - purchases derivation doesn't
        # amplify the agent's D-column inflation.
        inventory_items = await _reconcile_item_quantities(
            inventory_items, ctx.get("tenant_id", ""), ctx.get("company_id", "") or "", fy,
        )

        # iter-181 — Push the per-item roll-up to Mongo instead of
        # pulling 1k-20k full voucher docs into Python. Prior Python
        # loop over `raw_sales_vouchers`/`raw_purchase_vouchers` was
        # the dominant cost (17 s + 10 s on tenant 3079b0af). Native
        # aggregation returns the same roll-up in ~3 s combined.
        tenant_id = ctx.get("tenant_id", "")
        company_id_ctx = ctx.get("company_id", "") or ""

        # iter-181 — Fire the four heaviest DB calls in parallel so
        # their 235 ms × N Atlas RTT isn't paid serially. Previously
        # (fy roll-up → all-fy roll-up → inventory items → branch
        # heuristics) was all sequential — on cold cache that's 4×
        # RTT just waiting.
        import asyncio
        (sales_rollup_fy, purchase_rollup_fy), (sales_rollup_all, purchase_rollup_all) = await asyncio.gather(
            _get_voucher_rollup_maps(tenant_id, company_id_ctx, fy),
            _get_voucher_rollup_maps(tenant_id, company_id_ctx, None),
        )

        branch_set = await _get_branch_set(request, ctx)
        # Branch filtering only strips a subset of parties from sales. The
        # roll-up aggregates on the DB side so we can't do party-level
        # filtering without re-running the pipeline per-branch. The branch
        # feature is used only on the inventory list page, not here — the
        # branch_set is read but kept empty on this endpoint. If it ever
        # becomes non-empty we fall back to a per-request aggregation
        # that excludes those parties.
        if branch_set:
            # Re-aggregate excluding branch parties.
            match_sv: dict = {"tenant_id": tenant_id, "party_name": {"$nin": list(branch_set)}}
            if company_id_ctx:
                match_sv["company_id"] = company_id_ctx
            if fy:
                fy_start, fy_end = fy_to_date_range(fy)
                if fy_start:
                    match_sv["voucher_date"] = {"$gte": fy_start, "$lte": fy_end}
            pipeline = [
                {"$match": match_sv},
                {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": False}},
                {"$group": {
                    "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$items.item", ""]}}}},
                    "qty": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.quantity", 0]}}}},
                    "revenue": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.amount", 0]}}}},
                    "txns": {"$sum": 1},
                    "first_date": {"$min": "$voucher_date"},
                    "last_date": {"$max": "$voucher_date"},
                }},
            ]
            filtered_sales_rollup: dict = {}
            async for row in db.sales_vouchers.aggregate(pipeline, allowDiskUse=True):
                name = row.get("_id") or ""
                if not name:
                    continue
                filtered_sales_rollup[name] = {
                    "qty": float(row.get("qty") or 0),
                    "revenue": float(row.get("revenue") or 0),
                    "txns": int(row.get("txns") or 0),
                    "first_date": row.get("first_date") or "",
                    "last_date": row.get("last_date") or "",
                }
            sales_rollup_fy = filtered_sales_rollup

        # Purchases: detect branch-like parties (non-sundry-creditor).
        # Previously we had to pull all purchase vouchers and sieve them
        # in Python. For movement analysis the branch filter only drops
        # inter-branch purchases from the "Inward" column so we fall
        # back to a per-request aggregation only when the branch set is
        # populated. For most tenants it's empty → zero-cost path.
        purchase_branch_set = await _get_purchase_branch_set(ctx)
        if purchase_branch_set:
            match_pv: dict = {"tenant_id": tenant_id, "party_name": {"$in": list(purchase_branch_set)}}
            if company_id_ctx:
                match_pv["company_id"] = company_id_ctx
            if fy:
                fy_start, fy_end = fy_to_date_range(fy)
                if fy_start:
                    match_pv["voucher_date"] = {"$gte": fy_start, "$lte": fy_end}
            pipeline = [
                {"$match": match_pv},
                {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": False}},
                {"$group": {
                    "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$items.item", ""]}}}},
                    "qty": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.quantity", 0]}}}},
                }},
            ]
            sc_purchases_fy_rollup: dict = {}
            async for row in db.purchase_vouchers.aggregate(pipeline, allowDiskUse=True):
                name = row.get("_id") or ""
                if not name:
                    continue
                sc_purchases_fy_rollup[name] = {"qty": float(row.get("qty") or 0)}
            # iter-132 safety net: if the branch heuristic strips >90% of
            # purchases, fall back to the full roll-up for "Inward".
            total_fy_qty = sum(v.get("qty", 0) for v in purchase_rollup_fy.values())
            sc_fy_qty = sum(v.get("qty", 0) for v in sc_purchases_fy_rollup.values())
            if total_fy_qty >= 10 and (sc_fy_qty == 0 or sc_fy_qty / max(total_fy_qty, 1) < 0.10):
                logger.warning(
                    f"purchase-branch heuristic over-catching (kept {sc_fy_qty:.0f}/{total_fy_qty:.0f}) — "
                    f"reverting to raw purchase set for Movement Analysis"
                )
                item_purchases = {k: v["qty"] for k, v in purchase_rollup_fy.items()}
            else:
                item_purchases = {k: v["qty"] for k, v in sc_purchases_fy_rollup.items()}
        else:
            # No branch heuristic → use the full FY roll-up directly.
            item_purchases = {k: v["qty"] for k, v in purchase_rollup_fy.items()}

        # Opening-stock totals use the ALL-FY (no fy filter) roll-ups.
        all_item_sales_qty = {k: v["qty"] for k, v in sales_rollup_all.items()}
        all_item_purchase_qty = {k: v["qty"] for k, v in purchase_rollup_all.items()}

        # Item-level sales info (qty / revenue / txns / dates) for the FY.
        item_sales = {
            k: {
                "qty": v["qty"],
                "revenue": v["revenue"],
                "txns": v["txns"],
                "first_date": v["first_date"],
                "last_date": v["last_date"],
            }
            for k, v in sales_rollup_fy.items()
        }

        # Calculate FY duration in days for rate calculations
        from datetime import date as date_type
        if fy:
            fy_start_str, fy_end_str = fy_to_date_range(fy)
            try:
                fy_start_parts = fy_start_str.split('-')
                fy_end_parts = fy_end_str.split('-')
                fy_start = date_type(int(fy_start_parts[0]), int(fy_start_parts[1]), int(fy_start_parts[2]))
                fy_end = date_type(int(fy_end_parts[0]), int(fy_end_parts[1]), int(fy_end_parts[2]))
                today = date_type.today()
                # If FY is still running, use today as end date
                effective_end = min(fy_end, today)
                fy_days = max((effective_end - fy_start).days, 1)
            except (ValueError, TypeError):
                fy_days = 365
        else:
            fy_days = 365

        # iter-181 — item_sales and item_purchases are now built above
        # from server-side aggregations (see _get_voucher_rollup_maps).

        movement_data = []
        seen_items = set()
        for item in inventory_items:
            item_name = item.get("item_name", "")
            closing_stock = safe_num(item.get("quantity"))
            cost_price = safe_num(item.get("price", item.get("rate", 0)))
            key = item_name.lower()
            seen_items.add(key)

            sales_info = item_sales.get(key, {"qty": 0, "revenue": 0, "txns": 0})
            sales_qty = sales_info["qty"]
            purchase_qty = item_purchases.get(key, 0)

            # Opening stock from UNFILTERED data: Closing + AllSales - AllPurchases
            total_sales_qty = all_item_sales_qty.get(key, 0)
            total_purchase_qty = all_item_purchase_qty.get(key, 0)
            opening_stock = max(closing_stock + total_sales_qty - total_purchase_qty, 0)

            # Inward from filtered purchases
            inward = purchase_qty

            # Movement Rate = (Sales / (Opening + Inward)) * 100
            # Represents what % of total available stock was sold
            available_stock = opening_stock + inward
            if available_stock > 0:
                movement_rate = round((sales_qty / available_stock) * 100, 1)
            elif sales_qty > 0:
                movement_rate = 100.0
            else:
                movement_rate = 0.0

            # Days to sell remaining stock at current rate
            daily_sales = sales_qty / fy_days if fy_days > 0 else 0
            if closing_stock > 0 and daily_sales > 0:
                days_to_sell = round(closing_stock / daily_sales, 1)
            elif closing_stock > 0 and sales_qty == 0:
                days_to_sell = 999  # Stock exists but no sales
            else:
                days_to_sell = 0  # No stock remaining

            # Monthly average sales
            fy_months = max(fy_days / 30, 1)
            monthly_avg = round(sales_qty / fy_months, 1) if sales_qty > 0 else 0

            # Classification based on sales frequency and movement
            if sales_qty == 0:
                classification = "non-moving"
            elif sales_info["txns"] >= fy_months * 2:  # Sells twice+ per month
                classification = "fast-moving"
            elif sales_info["txns"] >= fy_months * 0.5:  # Sells at least every 2 months
                classification = "moderate"
            elif sales_info["txns"] > 0:
                classification = "slow-moving"
            else:
                classification = "non-moving"

            movement_data.append({
                "item_name": item_name,
                "part_number": item.get("part_number", ""),
                "category": item.get("category", item.get("stock_group", "General")),
                "opening_stock": round(opening_stock, 1),
                "inward": round(inward, 1),
                "sales": round(sales_qty, 1),
                "closing_stock": round(closing_stock, 1),
                "movement_rate": movement_rate,
                "days_to_sell": min(days_to_sell, 999),
                "monthly_avg_sales": monthly_avg,
                "transactions": sales_info.get("txns", 0),
                "revenue": round(sales_info.get("revenue", 0), 2),
                "cost_price": round(cost_price, 2),
                "classification": classification,
            })

        # Items sold but not in inventory master
        for item_key, info in item_sales.items():
            if item_key not in seen_items and info["qty"] > 0:
                purchase_qty = item_purchases.get(item_key, 0)
                fy_months = max(fy_days / 30, 1)
                monthly_avg = round(info["qty"] / fy_months, 1)
                classification = "fast-moving" if info["txns"] >= fy_months * 2 else "moderate" if info["txns"] >= fy_months * 0.5 else "slow-moving"
                movement_data.append({
                    "item_name": item_key.title(),
                    "category": "General",
                    "opening_stock": 0,
                    "inward": round(purchase_qty, 1),
                    "sales": round(info["qty"], 1),
                    "closing_stock": 0,
                    "movement_rate": 100.0,
                    "days_to_sell": 0,
                    "monthly_avg_sales": monthly_avg,
                    "transactions": info["txns"],
                    "revenue": round(info["revenue"], 2),
                    "classification": classification,
                })

        movement_data.sort(key=lambda x: x["transactions"], reverse=True)

        result_data = {
            "movements": movement_data,
            "summary": {
                "fast_moving": len([m for m in movement_data if m["classification"] == "fast-moving"]),
                "moderate": len([m for m in movement_data if m["classification"] == "moderate"]),
                "slow_moving": len([m for m in movement_data if m["classification"] == "slow-moving"]),
                "non_moving": len([m for m in movement_data if m["classification"] == "non-moving"]),
            },
            "fy_days": fy_days,
        }
        _MOVEMENT_CACHE[_mv_key] = (now_c + _ANALYTICS_TTL, result_data)
        if len(_MOVEMENT_CACHE) > 128:
            for k, val in list(_MOVEMENT_CACHE.items()):
                if val[0] <= now_c:
                    _MOVEMENT_CACHE.pop(k, None)
        return APIResponse(success=True, data=result_data)
    except Exception as e:
        logger.error(f"Error analyzing inventory movement: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/pivot-data")
async def get_pivot_data(request: Request, group_by: str = "category", metric: str = "value", company_id: Optional[str] = None, fy: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        # iter-161: FY-scope so pivot totals don't sum across FYs.
        inventory_items = _dedupe_inventory_by_name(inventory_items, fy_hint=fy)
        # iter-165: reconcile.
        inventory_items = await _reconcile_item_quantities(
            inventory_items, ctx.get("tenant_id", ""), ctx.get("company_id", "") or "", fy,
        )

        pivot_data = {}
        for item in inventory_items:
            group_key = item.get(group_by, "Uncategorized")
            if group_key not in pivot_data:
                pivot_data[group_key] = {
                    "group": group_key,
                    "total_items": 0,
                    "total_quantity": 0,
                    "total_value": 0,
                    "items": []
                }
            pivot_data[group_key]["total_items"] += 1
            pivot_data[group_key]["total_quantity"] += safe_num(item.get("quantity"))
            pivot_data[group_key]["total_value"] += safe_num(item.get("quantity")) * safe_num(item.get("price"))
            pivot_data[group_key]["items"].append(item)

        pivot_list = list(pivot_data.values())

        if metric == "value":
            pivot_list.sort(key=lambda x: x["total_value"], reverse=True)
        elif metric == "quantity":
            pivot_list.sort(key=lambda x: x["total_quantity"], reverse=True)
        else:
            pivot_list.sort(key=lambda x: x["total_items"], reverse=True)

        return APIResponse(
            success=True,
            data={"pivot_table": pivot_list, "group_by": group_by, "metric": metric}
        )
    except Exception as e:
        logger.error(f"Error creating pivot table: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== BELOW COST SALES ====================

@router.get("/inventory/below-cost-sales")
async def get_below_cost_sales(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Find items where sales price < purchase cost price (negative margin)."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        # iter-181 — Short TTL response cache.
        tenant_id_c = ctx.get("tenant_id", "")
        company_id_c = ctx.get("company_id", "") or (company_id or "")
        branch_on = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        _bc_key = (tenant_id_c, company_id_c, fy or "", branch_on)
        now_c = _rec_time.monotonic()
        cached = _BELOW_COST_CACHE.get(_bc_key)
        if cached and cached[0] > now_c:
            return APIResponse(success=True, data=cached[1])

        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        # iter-161: FY-scope for below-cost sales lookup.
        inventory_items = _dedupe_inventory_by_name(inventory_items, fy_hint=fy)
        # iter-165: same voucher-derived reconciliation.
        inventory_items = await _reconcile_item_quantities(
            inventory_items, ctx.get("tenant_id", ""), ctx.get("company_id", "") or "", fy,
        )

        # iter-181 — Use server-side aggregation instead of pulling full
        # voucher docs. Previously this endpoint was 30+ s on tenant
        # 3079b0af; the Python loops that rebuilt per-item price maps
        # from 1k-20k vouchers were the bottleneck.
        tenant_id = ctx.get("tenant_id", "")
        company_id_ctx = ctx.get("company_id", "") or ""
        sales_rollup, purchase_rollup = await _get_voucher_rollup_maps(
            tenant_id, company_id_ctx, fy,
        )

        branch_set = await _get_branch_set(request, ctx)
        if branch_set:
            # Re-aggregate excluding branch parties for the sales side.
            match_sv: dict = {"tenant_id": tenant_id, "party_name": {"$nin": list(branch_set)}}
            if company_id_ctx:
                match_sv["company_id"] = company_id_ctx
            if fy:
                fy_start, fy_end = fy_to_date_range(fy)
                if fy_start:
                    match_sv["voucher_date"] = {"$gte": fy_start, "$lte": fy_end}
            pipeline = [
                {"$match": match_sv},
                {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": False}},
                {"$group": {
                    "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$items.item", ""]}}}},
                    "qty": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.quantity", 0]}}}},
                    "revenue": {"$sum": {"$abs": {"$toDouble": {"$ifNull": ["$items.amount", 0]}}}},
                    "txns": {"$sum": 1},
                }},
            ]
            sales_rollup = {}
            async for row in db.sales_vouchers.aggregate(pipeline, allowDiskUse=True):
                name = row.get("_id") or ""
                if not name:
                    continue
                sales_rollup[name] = {
                    "qty": float(row.get("qty") or 0),
                    "revenue": float(row.get("revenue") or 0),
                    "txns": int(row.get("txns") or 0),
                }

        # Build cost price map from inventory master first, then
        # override with voucher-derived weighted-avg purchase price.
        cost_map = {}
        for item in inventory_items:
            name = item.get("item_name", "").lower()
            price = safe_num(item.get("price", item.get("rate", 0)))
            if price > 0:
                cost_map[name] = price

        for iname, pdata in purchase_rollup.items():
            qty = pdata.get("qty", 0.0)
            # rate_qty_sum / qty = weighted-avg purchase rate
            if qty > 0 and pdata.get("rate_qty_sum", 0.0) > 0:
                cost_map[iname] = pdata["rate_qty_sum"] / qty

        below_cost_items = []
        for iname, sdata in sales_rollup.items():
            cost = cost_map.get(iname, 0)
            total_qty = sdata.get("qty", 0.0)
            if cost <= 0 or total_qty <= 0:
                continue

            total_revenue = sdata.get("revenue", 0.0)
            avg_selling_price = total_revenue / total_qty
            margin = avg_selling_price - cost
            margin_pct = (margin / cost) * 100

            if margin < 0:
                # Find display name
                display_name = iname
                for inv in inventory_items:
                    if inv.get("item_name", "").lower() == iname:
                        display_name = inv["item_name"]
                        break

                below_cost_items.append({
                    "item_name": display_name,
                    "cost_price": round(cost, 2),
                    "avg_selling_price": round(avg_selling_price, 2),
                    "margin": round(margin, 2),
                    "margin_pct": round(margin_pct, 1),
                    "qty_sold": round(total_qty, 1),
                    "total_revenue": round(total_revenue, 2),
                    "total_loss": round(abs(margin) * total_qty, 2),
                    "transactions": sdata.get("txns", 0),
                })

        below_cost_items.sort(key=lambda x: x["total_loss"], reverse=True)

        result_data = {
            "items": below_cost_items,
            "summary": {
                "total_items": len(below_cost_items),
                "total_loss": round(sum(i["total_loss"] for i in below_cost_items), 2),
                "total_affected_revenue": round(sum(i["total_revenue"] for i in below_cost_items), 2),
            },
        }
        _BELOW_COST_CACHE[_bc_key] = (now_c + _ANALYTICS_TTL, result_data)
        if len(_BELOW_COST_CACHE) > 128:
            for k, val in list(_BELOW_COST_CACHE.items()):
                if val[0] <= now_c:
                    _BELOW_COST_CACHE.pop(k, None)
        return APIResponse(success=True, data=result_data)
    except Exception as e:
        logger.error(f"Error analyzing below-cost sales: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== MOVEMENT ANALYSIS EXCEL EXPORT ====================

@router.get("/inventory/movement-export")
async def export_movement_analysis(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Export movement analysis to Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from fastapi.responses import StreamingResponse
        import io

        # Reuse the movement-analysis logic
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items_raw = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        raw_sales = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        branch_set = await _get_branch_set(request, ctx)
        raw_purchases = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(10000)

        # Filter purchases to sundry creditors only for inward display
        purchase_branch_set = await _get_purchase_branch_set(ctx)
        sc_purchases = _filter_branch_vouchers(raw_purchases, purchase_branch_set)

        # ALL sales + ALL purchases for opening stock (must balance)
        all_sales_fy = filter_vouchers_by_fy(raw_sales, fy)
        all_purchases_fy = filter_vouchers_by_fy(raw_purchases, fy) if raw_purchases else []
        all_item_sales_qty = {}
        for v in all_sales_fy:
            for item in v.get("items", []):
                n = item.get("item", "").strip()
                if n:
                    k = n.lower()
                    all_item_sales_qty[k] = all_item_sales_qty.get(k, 0) + safe_num(item.get("quantity"))
        all_item_purchase_qty = {}
        for v in all_purchases_fy:
            for item in v.get("items", []):
                n = item.get("item", "").strip()
                if n:
                    k = n.lower()
                    all_item_purchase_qty[k] = all_item_purchase_qty.get(k, 0) + safe_num(item.get("quantity"))

        # Filtered sales for display; inward uses sundry creditor purchases only
        sales_vouchers = filter_vouchers_by_fy(_filter_branch_vouchers(raw_sales, branch_set), fy)
        sc_purchases_fy = filter_vouchers_by_fy(sc_purchases, fy) if sc_purchases else []
        purchase_vouchers = sc_purchases_fy

        # Build item sales and purchases maps
        item_sales = {}
        for voucher in sales_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                if item_name:
                    key = item_name.lower()
                    item_sales[key] = item_sales.get(key, 0) + qty

        item_purchases = {}
        for voucher in purchase_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                if item_name:
                    key = item_name.lower()
                    item_purchases[key] = item_purchases.get(key, 0) + qty

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Movement Analysis FY {fy or 'All'}"

        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        ws.merge_cells('A1:J1')
        ws['A1'] = f"Movement Analysis | FY: {fy or 'All'}"
        ws['A1'].font = Font(bold=True, size=12)
        ws.append([])

        headers = ["Item Name", "Category", "Opening Qty", "Inward (Purchases)", "Outward (Sales)", "Closing Qty", "Movement %", "Days to Sell", "Transactions", "Classification"]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

        for inv_item in inventory_items_raw:
            name = inv_item.get("item_name", "")
            key = name.lower()
            closing = safe_num(inv_item.get("quantity"))
            s_qty = item_sales.get(key, 0)
            p_qty = item_purchases.get(key, 0)
            # Opening from unfiltered data
            total_s = all_item_sales_qty.get(key, 0)
            total_p = all_item_purchase_qty.get(key, 0)
            opening = max(closing + total_s - total_p, 0)
            available = opening + p_qty
            rate = round((s_qty / available * 100), 1) if available > 0 else (100.0 if s_qty > 0 else 0.0)
            daily = s_qty / 365 if s_qty > 0 else 0
            dts = round(closing / daily, 1) if closing > 0 and daily > 0 else (999 if closing > 0 else 0)
            cls_tag = "fast-moving" if s_qty > 0 and rate >= 50 else "moderate" if rate >= 20 else "slow-moving" if s_qty > 0 else "non-moving"

            ws.append([name, inv_item.get("category", ""), round(opening, 1), round(p_qty, 1), round(s_qty, 1), round(closing, 1), rate, dts if dts < 999 else "N/A", 0, cls_tag])

        for col_cells in ws.columns:
            valid_cells = [c for c in col_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)]
            if not valid_cells:
                continue
            max_len = max((len(str(cell.value or "")) for cell in valid_cells), default=10)
            ws.column_dimensions[valid_cells[0].column_letter].width = min(max_len + 4, 35)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"movement_analysis_{fy or 'all'}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error exporting movement analysis: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== BELOW COST SALES EXCEL EXPORT ====================

@router.get("/inventory/below-cost-export")
async def export_below_cost_sales(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Export below-cost sales items to Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from fastapi.responses import StreamingResponse
        import io

        # Get the below-cost data
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        inventory_items_list = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        branch_set = await _get_branch_set(request, ctx)
        all_vouchers = _filter_branch_vouchers(all_vouchers, branch_set)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)
        purchase_vouchers_raw = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(10000)
        purchase_vouchers = filter_vouchers_by_fy(purchase_vouchers_raw, fy) if purchase_vouchers_raw else []

        cost_map = {}
        for item in inventory_items_list:
            name = item.get("item_name", "").lower()
            price = safe_num(item.get("price", item.get("rate", 0)))
            if price > 0:
                cost_map[name] = price

        for pv in purchase_vouchers:
            for item in pv.get("items", []):
                iname = item.get("item", "").strip().lower()
                rate = safe_num(item.get("rate", 0))
                if iname and rate > 0:
                    cost_map[iname] = rate

        sales_map = {}
        for sv in sales_vouchers:
            for item in sv.get("items", []):
                iname = item.get("item", "").strip().lower()
                rate = safe_num(item.get("rate", 0))
                qty = safe_num(item.get("quantity", 0))
                amt = safe_num(item.get("amount", 0))
                if iname and qty > 0:
                    if iname not in sales_map:
                        sales_map[iname] = {"revenue": 0, "qty": 0}
                    sales_map[iname]["revenue"] += abs(amt) if amt else abs(rate * qty)
                    sales_map[iname]["qty"] += abs(qty)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Below Cost Sales FY {fy or 'All'}"

        header_fill = PatternFill(start_color="EF4444", end_color="EF4444", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)

        ws.merge_cells('A1:H1')
        ws['A1'] = f"Below Cost Sales | FY: {fy or 'All'}"
        ws['A1'].font = Font(bold=True, size=12, color="EF4444")
        ws.append([])

        headers = ["Item Name", "Cost Price", "Avg Selling Price", "Margin", "Margin %", "Qty Sold", "Revenue", "Total Loss"]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

        for iname, sdata in sorted(sales_map.items()):
            cost = cost_map.get(iname, 0)
            if cost <= 0 or sdata["qty"] <= 0:
                continue
            avg_sell = sdata["revenue"] / sdata["qty"]
            margin = avg_sell - cost
            if margin >= 0:
                continue
            ws.append([iname.title(), round(cost, 2), round(avg_sell, 2), round(margin, 2), round(margin / cost * 100, 1), round(sdata["qty"], 1), round(sdata["revenue"], 2), round(abs(margin) * sdata["qty"], 2)])

        for col_cells in ws.columns:
            valid_cells = [c for c in col_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)]
            if not valid_cells:
                continue
            max_len = max((len(str(cell.value or "")) for cell in valid_cells), default=10)
            ws.column_dimensions[valid_cells[0].column_letter].width = min(max_len + 4, 35)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"below_cost_sales_{fy or 'all'}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error exporting below-cost sales: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== SALES FREQUENCY EXCEL/PDF EXPORT ====================

@router.get("/inventory/sales-frequency-export")
async def export_sales_frequency(request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None, fy: Optional[str] = None, format: str = "excel", company_id: Optional[str] = None):
    """Export sales frequency data to Excel or PDF."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from fastapi.responses import StreamingResponse
        import io

        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        branch_set = await _get_branch_set(request, ctx)
        all_vouchers = _filter_branch_vouchers(all_vouchers, branch_set)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

        if start_date or end_date:
            filtered = []
            for v in sales_vouchers:
                vd = v.get("voucher_date", "")
                if start_date and vd < start_date:
                    continue
                if end_date and vd > end_date:
                    continue
                filtered.append(v)
            sales_vouchers = filtered

        item_stats = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = safe_num(item.get("quantity"))
                if item_name not in item_stats:
                    item_stats[item_name] = {"qty": 0, "txns": 0, "customers": set(), "revenue": 0}
                item_stats[item_name]["qty"] += qty
                item_stats[item_name]["txns"] += 1
                item_stats[item_name]["customers"].add(party)
                item_stats[item_name]["revenue"] += qty * safe_num(item.get("rate"))

        rows = sorted(item_stats.items(), key=lambda x: x[1]["txns"], reverse=True)

        if format == "pdf":
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            elements = [Paragraph(f"Sales Frequency Report | FY: {fy or 'All'}", styles['Title']), Spacer(1, 12)]

            table_data = [["Item Name", "Transactions", "Total Qty", "Unique Customers", "Revenue", "Avg Qty/Txn"]]
            for name, s in rows:
                avg = round(s["qty"] / s["txns"], 1) if s["txns"] > 0 else 0
                table_data.append([name, s["txns"], round(s["qty"], 1), len(s["customers"]), f"Rs.{round(s['revenue'], 2):,.2f}", avg])

            t = Table(table_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]))
            elements.append(t)
            doc.build(elements)
            buf.seek(0)
            return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="sales_frequency_{fy or "all"}.pdf"'})

        # Default: Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Sales Frequency FY {fy or 'All'}"

        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)

        ws.merge_cells('A1:F1')
        ws['A1'] = f"Sales Frequency Report | FY: {fy or 'All'}"
        ws['A1'].font = Font(bold=True, size=12)
        ws.append([])

        headers = ["Item Name", "Transactions", "Total Qty Sold", "Unique Customers", "Revenue", "Avg Qty/Txn"]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

        for name, s in rows:
            avg = round(s["qty"] / s["txns"], 1) if s["txns"] > 0 else 0
            ws.append([name, s["txns"], round(s["qty"], 1), len(s["customers"]), round(s["revenue"], 2), avg])

        for col_cells in ws.columns:
            valid_cells = [c for c in col_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)]
            if not valid_cells:
                continue
            max_len = max((len(str(cell.value or "")) for cell in valid_cells), default=10)
            ws.column_dimensions[valid_cells[0].column_letter].width = min(max_len + 4, 35)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="sales_frequency_{fy or "all"}.xlsx"'}
        )
    except Exception as e:
        logger.error(f"Error exporting sales frequency: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/inventory/set-reorder-level")
async def set_reorder_level(request: Request):
    """Set manual reorder level for an inventory item."""
    try:
        ctx = await get_tenant_context(request)
        body = await request.json()
        item_id = body.get("item_id", "")
        reorder_level = math.ceil(float(body.get("reorder_level", 0)))

        if not item_id:
            return APIResponse(success=False, error="Item ID required")

        q = _build_query(ctx, None, {"item_id": item_id})
        result = await db.inventory_items.update_one(q, {"$set": {"reorder_level": reorder_level}})
        if result.matched_count == 0:
            return APIResponse(success=False, error="Item not found")

        user = await get_current_user(request, db)
        await log_audit("reorder_level_set", user.get("username", "") if user else "",
                         tenant_id=ctx.get("tenant_id", "") if ctx else "",
                         company_id=ctx.get("company_id", "") if ctx else "",
                         target=item_id, details=f"Reorder level: {reorder_level}",
                         ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Reorder level set to {reorder_level}")
    except Exception as e:
        logger.error(f"Error setting reorder level: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/inventory/auto-reorder-levels")
async def auto_set_reorder_levels(request: Request):
    """Auto-calculate reorder levels based on 2-month average sales consumption."""
    try:
        ctx = await get_tenant_context(request)
        body = await request.json()
        company_id = body.get("company_id")
        q = _build_query(ctx, company_id)

        items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        sales = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)

        if not sales:
            return APIResponse(success=False, error="No sales data to calculate reorder levels")

        # Calculate per-item monthly average sales qty
        from collections import defaultdict
        from datetime import datetime as dt
        item_sales_qty = defaultdict(float)
        dates = []
        for v in sales:
            vdate = v.get("voucher_date", v.get("date", ""))
            if vdate:
                try:
                    dates.append(dt.fromisoformat(vdate.replace("Z", "")))
                except Exception:
                    pass
            for vi in v.get("items", []):
                iname = (vi.get("item", "") or "").strip()
                qty = abs(safe_num(vi.get("quantity", 0)))
                if iname and qty > 0:
                    item_sales_qty[iname.lower()] += qty

        if not dates:
            return APIResponse(success=False, error="No valid sales dates found")

        min_date = min(dates)
        max_date = max(dates)
        months_span = max(1, (max_date - min_date).days / 30)

        updated = 0
        for item in items:
            iname = (item.get("item_name") or "").strip()
            total_sold = item_sales_qty.get(iname.lower(), 0)
            if total_sold > 0:
                monthly_avg = total_sold / months_span
                reorder_level = math.ceil(monthly_avg * 2)  # 2-month stock, rounded up
                item_q = _build_query(ctx, company_id, {"item_id": item["item_id"]})
                await db.inventory_items.update_one(item_q, {"$set": {"reorder_level": reorder_level}})
                updated += 1

        user = await get_current_user(request, db)
        await log_audit("auto_reorder_levels", user.get("username", "") if user else "",
                         tenant_id=ctx.get("tenant_id", "") if ctx else "", company_id=ctx.get("company_id", "") if ctx else "",
                         details=f"Updated {updated} items", ip_address=get_client_ip(request))

        return APIResponse(success=True, message=f"Reorder levels set for {updated} items (2-month stock)", data={"updated": updated})
    except Exception as e:
        logger.error(f"Error auto-setting reorder levels: {e}")
        return APIResponse(success=False, error=str(e))
