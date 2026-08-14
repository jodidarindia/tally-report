"""Iteration 150 — Busy Agent v1.5.6 data-parity fixes.

Locks in the four critical fixes that turned the live COMP0002 Busy
sync from "182 items, ₹0 net-profit" into full data parity with the
underlying Busy 21 database:

  1. Backend inventory ingest — chunked UpdateOne+upsert (was
     delete_many-per-chunk, which wiped every prior chunk).
  2. Backend profit_loss ingest — key includes `fy` so both FYs coexist.
  3. Backend all_ledgers ingest — key includes `fy` so opening/closing
     balances don't collide between FYs.
  4. Agent `compute_profit_loss` — emits `net_profit_loss` (was
     `net_profit`, which the backend never read → stored as 0).
  5. Agent `extract_inventory_items` — emits `opening_quantity`,
     `opening_rate`, `opening_value`, `closing_value` with a
     sale_price/cost_price fallback ladder for items without txns.
  6. Version + name bump: 1.5.6 across agent + gui.
"""
import os
import sys
import uuid
import asyncio
from pathlib import Path

import pytest
import requests

try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:
    for _line in Path("/app/backend/.env").read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, "/app/desktop-agent/build-kit-busy")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    fe_env = Path("/app/frontend/.env").read_text()
    for line in fe_env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_TENANT = "3079b0af-e899-44b4-ae7c-c35d113fe296"


def _run(coro):
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _post_sync(payload):
    return requests.post(f"{BASE_URL}/api/agent/sync", json=payload, timeout=60)


@pytest.fixture(scope="module")
def sync_token():
    from services.auth_service import generate_sync_token
    return generate_sync_token(ADMIN_TENANT)


# ─── 1) Inventory: chunked upsert keeps every chunk's items ───
def test_inventory_chunked_upsert_no_data_loss(sync_token):
    """The v1.5.5 backend wiped every prior chunk. v1.5.6 upserts, so
    posting the same items across 3 chunks must leave 3 chunks in DB."""
    from db import db
    cid = f"COMP{uuid.uuid4().hex[:6].upper()}"
    display = f"E2E INV {uuid.uuid4().hex[:6].upper()}"

    def _mk(prefix, n):
        return [{
            "item_id": f"{prefix}-{i}",
            "item_name": f"Item {prefix}-{i}",
            "quantity": 10 + i, "price": 100 + i,
            "stock_group": "TEST",
            "part_number": f"PN-{prefix}-{i}",
            "unit": "PC",
        } for i in range(n)]

    resolved_uuid = None
    for prefix in ("A", "B", "C"):
        payload = {
            "data_type": "inventory",
            "data": _mk(prefix, 3),
            "sync_time": "2026-02-16T00:00:00+05:30",
            "financial_year": "2025-26",
            "tenant_id": ADMIN_TENANT,
            "company_id": cid,
            "company_name": display,
            "sync_token": sync_token,
        }
        r = _post_sync(payload)
        assert r.status_code == 200 and r.json().get("success"), r.text

    async def _verify():
        from services.id_mapping_service import _stable_name_hash
        folder_hash = _stable_name_hash(f"__folder__:{cid}")
        m = await db.company_mappings.find_one(
            {"tenant_id": ADMIN_TENANT, "folder_id_hash": folder_hash})
        assert m is not None
        nonlocal_uuid = m["company_uuid"]
        n = await db.inventory_items.count_documents({
            "tenant_id": ADMIN_TENANT,
            "company_id": nonlocal_uuid,
        })
        # 3 chunks × 3 items = 9. The pre-1.5.6 delete-per-chunk bug
        # would leave only the LAST chunk (3 items).
        assert n == 9, (
            f"Expected 9 items (3 chunks × 3 items), got {n} — the "
            "delete_many-per-chunk regression is back."
        )
        # Cleanup
        await db.inventory_items.delete_many({"tenant_id": ADMIN_TENANT, "company_id": nonlocal_uuid})
        await db.company_mappings.delete_many({"tenant_id": ADMIN_TENANT, "folder_id_hash": folder_hash})
        await db.users.update_one(
            {"tenant_id": ADMIN_TENANT, "role": "admin"},
            {"$pull": {"companies": nonlocal_uuid}},
        )
    _run(_verify())


# ─── 2) Inventory upsert preserves user-managed abc_category ───
def test_inventory_upsert_preserves_abc_category(sync_token):
    from db import db
    cid = f"COMP{uuid.uuid4().hex[:6].upper()}"
    display = f"ABC PRESERVE {uuid.uuid4().hex[:6].upper()}"

    # First sync
    r = _post_sync({
        "data_type": "inventory",
        "data": [{
            "item_id": "ABC-1", "item_name": "ABC-1",
            "quantity": 1, "price": 100, "stock_group": "T",
            "part_number": "P", "unit": "PC",
        }],
        "sync_time": "2026-02-16T00:00:00+05:30",
        "financial_year": "2025-26",
        "tenant_id": ADMIN_TENANT, "company_id": cid,
        "company_name": display, "sync_token": sync_token,
    })
    assert r.status_code == 200 and r.json().get("success")

    async def _tag_and_resync():
        from services.id_mapping_service import _stable_name_hash
        fh = _stable_name_hash(f"__folder__:{cid}")
        m = await db.company_mappings.find_one(
            {"tenant_id": ADMIN_TENANT, "folder_id_hash": fh})
        uid = m["company_uuid"]
        # User sets abc_category via /api/inventory/{id}/abc
        await db.inventory_items.update_one(
            {"tenant_id": ADMIN_TENANT, "company_id": uid, "item_id": "ABC-1"},
            {"$set": {"abc_category": "A"}}
        )
        # Re-sync same item (fresh agent tick)
        rr = _post_sync({
            "data_type": "inventory",
            "data": [{
                "item_id": "ABC-1", "item_name": "ABC-1",
                "quantity": 2, "price": 999, "stock_group": "T",
                "part_number": "P", "unit": "PC",
            }],
            "sync_time": "2026-02-16T01:00:00+05:30",
            "financial_year": "2025-26",
            "tenant_id": ADMIN_TENANT, "company_id": cid,
            "company_name": display, "sync_token": sync_token,
        })
        assert rr.status_code == 200 and rr.json().get("success")
        # abc_category must survive.
        doc = await db.inventory_items.find_one(
            {"tenant_id": ADMIN_TENANT, "company_id": uid, "item_id": "ABC-1"})
        assert doc["abc_category"] == "A", "user-managed abc_category was overwritten"
        assert doc["quantity"] == 2, "sync updates were not applied"
        # Cleanup
        await db.inventory_items.delete_many({"tenant_id": ADMIN_TENANT, "company_id": uid})
        await db.company_mappings.delete_many({"tenant_id": ADMIN_TENANT, "folder_id_hash": fh})
        await db.users.update_one(
            {"tenant_id": ADMIN_TENANT, "role": "admin"},
            {"$pull": {"companies": uid}},
        )
    _run(_tag_and_resync())


# ─── 3) P&L key includes FY — both FYs coexist ───
def test_profit_loss_fy_scoped(sync_token):
    from db import db
    cid = f"COMP{uuid.uuid4().hex[:6].upper()}"
    display = f"PL FY {uuid.uuid4().hex[:6].upper()}"

    for fy, income, expense in (("2025-26", 100_000, 40_000),
                                ("2026-27", 200_000, 90_000)):
        r = _post_sync({
            "data_type": "profit_loss",
            "data": [{
                "total_income": income, "total_expense": expense,
                "net_profit_loss": income - expense,
                "income": [], "expense": [],
            }],
            "sync_time": "2026-02-16T00:00:00+05:30",
            "financial_year": fy,
            "tenant_id": ADMIN_TENANT, "company_id": cid,
            "company_name": display, "sync_token": sync_token,
        })
        assert r.status_code == 200 and r.json().get("success")

    async def _verify():
        from services.id_mapping_service import _stable_name_hash
        fh = _stable_name_hash(f"__folder__:{cid}")
        m = await db.company_mappings.find_one(
            {"tenant_id": ADMIN_TENANT, "folder_id_hash": fh})
        uid = m["company_uuid"]
        # Both FYs live in DB.
        pl1 = await db.profit_loss.find_one({
            "tenant_id": ADMIN_TENANT, "company_id": uid, "fy": "2025-26"})
        pl2 = await db.profit_loss.find_one({
            "tenant_id": ADMIN_TENANT, "company_id": uid, "fy": "2026-27"})
        assert pl1 and pl1["net_profit_loss"] == 60_000
        assert pl2 and pl2["net_profit_loss"] == 110_000
        assert pl1["_id"] != pl2["_id"], "same _id → they overwrote"
        # Cleanup
        await db.profit_loss.delete_many({"tenant_id": ADMIN_TENANT, "company_id": uid})
        await db.company_mappings.delete_many({"tenant_id": ADMIN_TENANT, "folder_id_hash": fh})
        await db.users.update_one(
            {"tenant_id": ADMIN_TENANT, "role": "admin"},
            {"$pull": {"companies": uid}},
        )
    _run(_verify())


# ─── 4) all_ledgers key includes FY — no cross-FY overwrites ───
def test_all_ledgers_fy_scoped(sync_token):
    from db import db
    cid = f"COMP{uuid.uuid4().hex[:6].upper()}"
    display = f"LDG FY {uuid.uuid4().hex[:6].upper()}"

    for fy, close in (("2025-26", 50_000), ("2026-27", 120_000)):
        r = _post_sync({
            "data_type": "all_ledgers",
            "data": [{
                "ledger_name": "Cash A/C",
                "ledger_id": "LDG-CASH",
                "closing_balance": close,
                "opening_balance": 0,
                "parent_group": "Cash-in-Hand",
                "category": "cash",
            }],
            "sync_time": "2026-02-16T00:00:00+05:30",
            "financial_year": fy,
            "tenant_id": ADMIN_TENANT, "company_id": cid,
            "company_name": display, "sync_token": sync_token,
        })
        assert r.status_code == 200 and r.json().get("success")

    async def _verify():
        from services.id_mapping_service import _stable_name_hash
        fh = _stable_name_hash(f"__folder__:{cid}")
        m = await db.company_mappings.find_one(
            {"tenant_id": ADMIN_TENANT, "folder_id_hash": fh})
        uid = m["company_uuid"]
        rows = await db.all_ledgers.find({
            "tenant_id": ADMIN_TENANT, "company_id": uid,
            "ledger_name": "Cash A/C",
        }).to_list(10)
        by_fy = {r.get("fy"): r for r in rows}
        assert "2025-26" in by_fy and by_fy["2025-26"]["closing_balance"] == 50_000
        assert "2026-27" in by_fy and by_fy["2026-27"]["closing_balance"] == 120_000
        # Cleanup
        await db.all_ledgers.delete_many({"tenant_id": ADMIN_TENANT, "company_id": uid})
        await db.company_mappings.delete_many({"tenant_id": ADMIN_TENANT, "folder_id_hash": fh})
        await db.users.update_one(
            {"tenant_id": ADMIN_TENANT, "role": "admin"},
            {"$pull": {"companies": uid}},
        )
    _run(_verify())


# ─── 5) compute_profit_loss emits net_profit_loss ───
def test_compute_profit_loss_emits_net_profit_loss(tmp_path):
    from flowra_busy_agent import BusyDataExtractor
    ex = BusyDataExtractor(str(tmp_path))
    # Stub extract_all_ledgers so we get a deterministic P&L
    def _fake_ledgers(fy):
        yield {"ledger_name": "Sales", "parent_group": "Sale",
               "closing_balance": 100_000, "category": "sale"}
        yield {"ledger_name": "Purchase", "parent_group": "Purchase",
               "closing_balance": -40_000, "category": "purchase"}
        yield {"ledger_name": "Rent", "parent_group": "Expenses (Indirect/Admn.)",
               "closing_balance": -5_000, "category": "indirect_expense"}
    ex.extract_all_ledgers = _fake_ledgers
    pl = ex.compute_profit_loss("2025-26")
    assert pl["total_income"] == 100_000
    assert pl["total_expense"] == 45_000  # abs values
    assert pl["net_profit_loss"] == 55_000, (
        "net_profit_loss must equal total_income - total_expense"
    )
    assert pl["net_profit"] == pl["net_profit_loss"], (
        "net_profit legacy field must mirror net_profit_loss"
    )
    assert pl["fy"] == "2025-26"


# ─── 6) Inventory extractor opening-balance ladder ───
def test_extract_inventory_opening_and_price_fallbacks():
    """The extractor must:
      (a) surface `opening_quantity/opening_rate/opening_value/closing_value`
      (b) fall back sale_price/cost_price to Master1 built-in columns
          when the price-map has no rate for the item.
    """
    from flowra_busy_agent import BusyDataExtractor

    class _FakeReader:
        def __init__(self, rows):
            self._rows = rows
        def iter_rows(self, tbl):
            for r in self._rows.get(tbl, []):
                yield r
        def count_rows(self, tbl):
            return len(self._rows.get(tbl, []))
        def close(self):
            pass

    master_rows = [{
        "MasterType": "6", "Code": "IT-1", "Name": "SKU-1",
        "Alias": "Widget", "PrintName": "Widget", "HSNCode": "9999",
        "ParentGrp": "GRP-1",
        # No SPrice/PPrice — force fallback to D3/D2.
        "D2": "42.5",   # cost
        "D3": "60.0",   # sale
    }]
    folio_rows = [{
        "MasterType": "6", "MasterCode": "IT-1",
        "D1": "5", "D2": "40", "D3": "200",   # opening qty/rate/value
    }]

    ex = BusyDataExtractor.__new__(BusyDataExtractor)
    ex.data_folder = "/tmp"
    ex._fy_dbs = {"2025-26": "/tmp/fake.bds"}
    ex._master_db = None
    ex._reader_pool = {}
    ex._code_map = {}
    ex._group_map = {}
    ex._parent_map = {}
    fake = _FakeReader({"Master1": master_rows, "Folio1": folio_rows,
                        "Tran2": []})
    ex._get_reader = lambda _p: fake  # bypass real DB open
    ex._load_code_map = lambda fy: None
    ex._resolve_name = lambda code: "TEST GROUP"

    items = list(ex.extract_inventory_items("2025-26"))
    assert len(items) == 1
    it = items[0]
    # Opening slots from Folio1
    assert it["opening_quantity"] == 5
    assert it["opening_rate"] == 40
    assert it["opening_value"] == 200
    # Price ladder — Master1.D3 → sale, Master1.D2 → cost
    assert it["sale_price"] == 60.0
    assert it["cost_price"] == 42.5
    # closing_value derived from qty × sale (or cost if sale=0)
    assert it["closing_value"] >= 0


# ─── 7) Version bump locked ───
def test_version_bumped_to_156():
    import importlib
    import flowra_busy_agent
    importlib.reload(flowra_busy_agent)
    # v1.5.6 floor — every future release must stay ≥ 1.5.6.
    assert tuple(int(p) for p in flowra_busy_agent.VERSION.split(".")) >= (1, 5, 6)


def test_gui_and_agent_versions_stay_in_sync_156():
    import re
    import flowra_busy_agent
    gui_src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py").read_text()
    m = re.search(r'^APP_VERSION\s*=\s*"v([\d.]+)"', gui_src, re.M)
    assert m
    assert m.group(1) == flowra_busy_agent.VERSION


# ─── 8) Removed Busy-login / DB-password fields from GUI ───
def test_gui_removes_busy_password_widgets():
    """v1.5.6 — access_parser bypasses ODBC/OLE DB entirely, so the
    Busy Username / Login Password / DB Password entry widgets serve
    no purpose. Assert they were removed from the settings tab layout."""
    gui_src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py").read_text()
    for banned in (
        "Busy login username",
        "Busy login password",
        "Busy DB password (fallback)",
        "self.busy_user_entry = ttk.Entry",
        "self.busy_login_pwd_entry = ttk.Entry",
        "self.busy_pwd_entry = ttk.Entry",
    ):
        assert banned not in gui_src, (
            f"GUI still ships the removed widget/label: {banned!r}"
        )


# ─── 9) Stop-Sync button — bottom bar auto-sizes ───
def test_gui_bottom_bar_no_frozen_height():
    """The old bar had `height=56` + `pack_propagate(False)` which
    clipped the ~68 px tall "Stop" button when the window maximised.
    v1.5.6 removes both so the frame grows to fit its children."""
    gui_src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py").read_text()
    assert "bg=\"#F1F5F9\", height=56" not in gui_src
    assert "bar.pack_propagate(False)" not in gui_src
