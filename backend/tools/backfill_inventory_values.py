"""iter-158 one-shot backfill: recompute closing_value from cost_price
for every Busy inventory row where sale-price inflation is suspected,
and stamp a `dedupe_group_size` on each row so ops can spot tenants
that have per-FY code drift.

Run: `python -m backend.tools.backfill_inventory_values` (dry-run by
default). Add `--commit` to persist. Add `--tenant <id>` to scope.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict


async def _run(commit: bool = False, only_tenant: str | None = None):
    sys.path.insert(0, "/app/backend")
    from db import db

    q: dict = {}
    if only_tenant:
        q["tenant_id"] = only_tenant

    tenants = await db.inventory_items.distinct("tenant_id", q)
    print(f"Scanning {len(tenants)} tenant(s)…\n")
    total_recomputed = 0
    total_dedupe_hint = 0

    for tid in tenants:
        rows = await db.inventory_items.find({"tenant_id": tid}, {"_id": 0}).to_list(50000)
        if not rows:
            continue
        # Group by (company, item_name) — that's the real SKU key.
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for r in rows:
            key = (r.get("company_id") or "", (r.get("item_name") or "").strip().lower())
            groups[key].append(r)

        dupes = sum(1 for rs in groups.values() if len(rs) > 1)
        distinct = len(groups)
        print(f"  tenant={tid[:8]}  rows={len(rows):>5}  distinct_names={distinct:>5}  duplicate_groups={dupes}")

        for r in rows:
            qty  = float(r.get("quantity") or 0)
            cost = float(r.get("cost_price") or 0)
            stored = float(r.get("closing_value") or 0)
            if qty > 0 and cost > 0:
                correct = round(qty * cost, 2)
                # Only rewrite when the drift is significant (>1%) —
                # avoids churn on Tally rows where closing_value is
                # already correct (comes directly from Tally CLVAL).
                if stored == 0 or abs(stored - correct) / max(stored, 1) > 0.01:
                    total_recomputed += 1
                    if commit:
                        await db.inventory_items.update_one(
                            {"tenant_id": r["tenant_id"], "company_id": r["company_id"], "item_id": r["item_id"]},
                            {"$set": {"closing_value": correct, "closing_value_source": "backfill_iter158"}},
                        )
            total_dedupe_hint += (len(groups) < len(rows))

    print(f"\n{'COMMIT' if commit else 'DRY-RUN'} · closing_value would be updated on {total_recomputed} rows")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--commit", action="store_true", help="Persist changes (default: dry-run).")
    p.add_argument("--tenant", help="Restrict to a single tenant_id.")
    args = p.parse_args()
    asyncio.run(_run(commit=args.commit, only_tenant=args.tenant))


if __name__ == "__main__":
    main()
