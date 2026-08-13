"""Iteration 148 — Busy Agent v1.5.4 display-name resolution + retry logic.

Scenarios locked in:
  1. `register_company_by_folder()` creates a NEW mapping keyed on both
     the folder id hash and the display-name hash.
  2. Re-calling with the SAME folder id but a NEW display name updates
     the name in-place (no orphan UUID, same UUID returned).
  3. Legacy migration — a v1.5.3 mapping whose `company_name_hash`
     equals the folder id gets adopted (same UUID, new display name,
     new folder_id_hash stamped).
  4. `/api/agent/sync` returns success:false when tenant_id + folder id +
     display name are missing (existing hard-enforce guards intact).
  5. `/api/agent/sync` accepts `company_id="COMP<n>"` + `company_name=<display>`
     and stores rows under the RESOLVED UUID (not under the folder id).
  6. `BusyDataExtractor.get_company_display_name()` returns the folder-id
     fallback when no master DB / candidate table matches (Linux dev env
     without a real .bds file). The method must not raise.
  7. Agent version bump: `VERSION == '1.5.4'`.
  8. `_post_chunk()` source-asserts on the presence of a 3-tier retry
     backoff so a future refactor that removes it fails loudly.
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from pathlib import Path

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
    # Motor caches the loop it was created with — reuse a single loop
    # across all tests in this module so re-connecting between calls
    # doesn't hit the "Event loop is closed" error.
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ─── 1) register_company_by_folder: fresh create ───
def test_register_by_folder_fresh_create():
    from services.id_mapping_service import register_company_by_folder
    from db import db

    tenant = f"test-{uuid.uuid4()}"
    folder = "COMP9101"
    display = "TEST FRESH COMPANY PVT LTD"

    async def _t():
        uid = await register_company_by_folder(tenant, folder, display)
        assert uid, "expected a non-empty UUID"
        # Confirm mapping is keyed on both folder_id_hash + company_name_hash
        row = await db.company_mappings.find_one({"company_uuid": uid, "tenant_id": tenant})
        assert row is not None
        assert row.get("folder_id_hash")
        assert row.get("company_name_hash")
        await db.company_mappings.delete_many({"tenant_id": tenant})
        return uid
    assert _run(_t())


# ─── 2) Same folder, new display name → in-place rename, same UUID ───
def test_register_by_folder_rename_in_place():
    from services.id_mapping_service import register_company_by_folder, get_company_name
    from db import db

    tenant = f"test-{uuid.uuid4()}"
    folder = "COMP9102"

    async def _t():
        uid1 = await register_company_by_folder(tenant, folder, "OLD NAME")
        uid2 = await register_company_by_folder(tenant, folder, "NEW SHINY NAME")
        assert uid1 == uid2, "same folder id must return the same UUID"
        name = await get_company_name(tenant, uid1)
        assert name == "NEW SHINY NAME"
        # Only ONE row exists for the tenant.
        n = await db.company_mappings.count_documents({"tenant_id": tenant})
        assert n == 1
        await db.company_mappings.delete_many({"tenant_id": tenant})
    _run(_t())


# ─── 3) Legacy migration: v1.5.3 mapping under folder-id-as-name ───
def test_register_by_folder_legacy_migration():
    from services.id_mapping_service import (
        register_company_mapping, register_company_by_folder, get_company_name,
    )
    from db import db

    tenant = f"test-{uuid.uuid4()}"
    folder = "COMP9103"
    display = "REAL COMPANY NAME LTD"

    async def _t():
        # Simulate the v1.5.3 buggy behaviour: agent sent folder-id as
        # both company_id AND company_name → mapping keyed on hash(folder).
        legacy_uid = await register_company_mapping(tenant, folder)
        # Now v1.5.4 comes in with the correct display name.
        migrated_uid = await register_company_by_folder(tenant, folder, display)
        # Must ADOPT the legacy UUID (no orphan data).
        assert legacy_uid == migrated_uid, (
            "legacy folder-name mapping must be adopted, not duplicated"
        )
        # Display name is now the real name.
        assert (await get_company_name(tenant, legacy_uid)) == display
        # Only one row survives.
        n = await db.company_mappings.count_documents({"tenant_id": tenant})
        assert n == 1
        await db.company_mappings.delete_many({"tenant_id": tenant})
    _run(_t())


# ─── 4) /api/agent/sync still hard-enforces sync_token ───
def test_sync_rejects_missing_sync_token():
    r = requests.post(
        f"{BASE_URL}/api/agent/sync",
        json={"data_type": "inventory", "data": [], "tenant_id": ADMIN_TENANT,
              "company_id": "COMP9104", "company_name": "TEST NAME"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json().get("success") is False


# ─── 5) End-to-end sync uses folder-keyed mapping ───
def test_sync_end_to_end_folder_keyed():
    from services.auth_service import generate_sync_token
    from db import db

    token = generate_sync_token(ADMIN_TENANT)
    folder = f"COMPZZZ{str(uuid.uuid4())[:4].upper()}"
    display = f"E2E TEST COMPANY {str(uuid.uuid4())[:6].upper()}"

    payload = {
        "data_type": "inventory",
        "data": [{
            "item_id": "ZZZ-ITEM-1",
            "item_name": "ZZZ SMOKE ITEM",
            "quantity": 1, "price": 100, "stock_group": "TEST",
            "part_number": "ZZZ-1", "unit": "PC",
        }],
        "sync_time": "2026-02-16T00:00:00+05:30",
        "financial_year": "2025-26",
        "tenant_id": ADMIN_TENANT,
        "company_id": folder,
        "company_name": display,
        "sync_token": token,
    }
    r = requests.post(f"{BASE_URL}/api/agent/sync", json=payload, timeout=60)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success"), f"sync failed: {body}"

    async def _verify():
        # Look up the mapping — must be keyed under folder_id_hash and
        # carry `display` as its decrypted name.
        from services.id_mapping_service import (
            _stable_name_hash, register_company_by_folder,
        )
        from services.encryption_service import decrypt_field
        folder_hash = _stable_name_hash(f"__folder__:{folder}")
        row = await db.company_mappings.find_one(
            {"tenant_id": ADMIN_TENANT, "folder_id_hash": folder_hash})
        assert row is not None, "folder-keyed mapping missing"
        name = decrypt_field(row["company_name_encrypted"]).strip()
        assert name == display, f"display name mismatch: {name!r} != {display!r}"
        # Inventory row lives under the resolved UUID.
        inv = await db.inventory_items.count_documents({
            "tenant_id": ADMIN_TENANT,
            "company_id": row["company_uuid"],
            "item_name": "ZZZ SMOKE ITEM",
        })
        assert inv == 1
        # Cleanup — DELETE the ephemeral rows we created.
        await db.inventory_items.delete_many({"item_name": "ZZZ SMOKE ITEM"})
        await db.company_mappings.delete_many(
            {"tenant_id": ADMIN_TENANT, "folder_id_hash": folder_hash})
        # Also drop from the admin user's companies list.
        await db.users.update_one(
            {"tenant_id": ADMIN_TENANT, "role": "admin"},
            {"$pull": {"companies": row["company_uuid"]}},
        )
    _run(_verify())


# ─── 6) Extractor display-name resolver: no crash, folder fallback ───
def test_extractor_display_name_fallback_on_no_db(tmp_path):
    from flowra_busy_agent import BusyDataExtractor
    # Empty folder — no .bds files.
    ex = BusyDataExtractor(str(tmp_path))
    name = ex.get_company_display_name("COMP9999")
    assert name == "COMP9999", "must fall back to folder id when no DB is present"

    # Absolutely no folder id and no DB → sentinel fallback.
    name2 = ex.get_company_display_name("")
    assert name2, "must not return empty string"


# ─── 7) Version bump locked ───
def test_version_bumped_to_154():
    import importlib
    import flowra_busy_agent
    importlib.reload(flowra_busy_agent)
    assert flowra_busy_agent.VERSION == "1.5.4"
    assert flowra_busy_agent.AGENT_TAG.startswith("busy-1.5.4")


# ─── 8) Retry backoff present in _post_chunk source ───
def test_post_chunk_has_retry_backoff():
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    # The retry list literal is the anchor. Guard against silent removal.
    assert "backoffs = [5, 30, 60]" in src, (
        "3-tier retry backoff must be present in _post_chunk"
    )
    assert "[SYNC-LOST]" in src, "loud dead-letter log line missing"
