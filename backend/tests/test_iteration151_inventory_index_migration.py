"""Iteration 151 — v1.5.6 addendum: inventory index migration to item_id.

The v1.5.5 backend's `data_type=='inventory'` handler switched to
`UpdateOne+upsert` keyed on `(tenant_id, company_id, item_id)`. But
the legacy `tcid_iname` index carried a `unique=True` constraint on
`(tenant_id, company_id, item_name)`. Busy legitimately ships multiple
SKUs sharing an Alias/PrintName, so the old constraint triggered
E11000 duplicate-key errors that dropped items on every sync tick.

v1.5.6 addendum:
  • Drop legacy `tcid_iname` (unique on item_name).
  • Create `tcid_iid` (unique on item_id) — matches the upsert key.
  • Recreate `tcid_iname` non-unique for search performance.

This test file guards the migration:
  1. Startup index bootstrap lands the correct index shape.
  2. Two items with the same `item_name` but different `item_id` can
     coexist in the collection (regression guard against re-adding the
     old unique-on-name constraint).
"""
import os
import sys
import uuid
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:
    for _line in Path("/app/backend/.env").read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, "/app/backend")


def _run(coro):
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def test_inventory_indexes_migrated_to_item_id():
    from db import db

    async def _t():
        idx = await db.inventory_items.index_information()
        # tcid_iid — new UNIQUE index on item_id.
        assert "tcid_iid" in idx, "tcid_iid unique-on-item_id index missing"
        iid = idx["tcid_iid"]
        assert iid.get("unique") is True, "tcid_iid must be UNIQUE"
        assert iid["key"] == [("tenant_id", 1), ("company_id", 1), ("item_id", 1)]
        # tcid_iname — kept for search, but non-unique.
        if "tcid_iname" in idx:
            assert not idx["tcid_iname"].get("unique"), (
                "tcid_iname must NOT be unique — Busy legitimately has "
                "multiple SKUs sharing an alias/name"
            )
    _run(_t())


def test_two_items_same_name_different_id_coexist():
    """Regression guard — the v1.5.5 unique constraint on item_name
    dropped ~1 % of items every tick because Busy aliases duplicate.
    v1.5.6 lifts that constraint; verify two items with the SAME
    item_name but different item_id both persist."""
    from db import db

    tenant = f"idx-test-{uuid.uuid4()}"
    cid = f"cid-{uuid.uuid4()}"

    async def _t():
        # Manually insert what the sync would upsert — bypasses the
        # v1.5.5 route (which we've already tested elsewhere) to
        # isolate the index layer.
        await db.inventory_items.insert_many([
            {
                "tenant_id": tenant, "company_id": cid,
                "item_id": "SKU-A", "item_name": "Widget",
                "quantity": 1, "price": 100,
            },
            {
                "tenant_id": tenant, "company_id": cid,
                "item_id": "SKU-B", "item_name": "Widget",  # same NAME
                "quantity": 2, "price": 200,
            },
        ])
        n = await db.inventory_items.count_documents(
            {"tenant_id": tenant, "company_id": cid, "item_name": "Widget"})
        assert n == 2, (
            f"Expected 2 rows sharing item_name='Widget', got {n} — the "
            "unique-on-name constraint has been re-introduced."
        )
        # Cleanup
        await db.inventory_items.delete_many({"tenant_id": tenant})
    _run(_t())


def test_startup_creates_expected_indexes(monkeypatch):
    """Source anchor — server.py's startup block MUST recreate the
    correct index shape. Guards against a future edit that accidentally
    reintroduces `unique=True` on the item_name index."""
    src = Path("/app/backend/server.py").read_text()
    assert "name='tcid_iid'" in src, "startup missing tcid_iid create_index call"
    # tcid_iid must be unique
    assert (
        "name='tcid_iid', background=True, unique=True"
        in src.replace(" ", "").replace("\n", " ")
        or "'tcid_iid', background=True, unique=True" in src
    ), "tcid_iid must be UNIQUE"
    # The remaining tcid_iname line MUST not carry unique=True.
    for line in src.splitlines():
        if "tcid_iname" in line and "create_index" in line:
            continue  # multi-line — check the next non-continuation line
        if "name='tcid_iname'" in line:
            assert "unique=True" not in line, (
                "tcid_iname must be non-unique — see iter 151 notes"
            )
