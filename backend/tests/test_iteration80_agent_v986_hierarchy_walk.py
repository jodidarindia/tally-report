"""
Iteration 80 — Tally Sync Agent v9.8.6-hierarchy-walk (Phase 2 of BS/PL parity).

User-reported: "for inventory the root group or the group in primary is
not found in inventory menu. Example tvs sundaram fasteners is missing.
Similarly many parent groups are missing in company krishna sales corporation"

Root cause: Tally has multi-level stock-group nesting (Primary → Sub →
Sub-sub → leaf items). The agent only stored the IMMEDIATE parent as
`stock_group`, dropping the Primary-level grouping that the user organises
inventory by ("TVS Sundaram Fasteners" with sub-groups like "10mm & 12mm
1.25 Thread"). Same problem on the ledger side — Sundry Creditors / Fixed
Assets sub-groups got mis-classified in the BS endpoint.

Fix shipped in v9.8.6:
1. New `fetch_stock_group_parent_map()` — fetches `<STOCKGROUP>` collection
   to build {sg_name → parent_sg_name} hierarchy.
2. `fetch_stock_items()` walks the hierarchy via `_resolve_root_group()`
   and stamps `root_stock_group` on every item.
3. `fetch_all_ledgers_via_groups()` and `_fetch_ledgers_fallback()` already
   computed `root_group` — now they STORE it on every ledger doc.
4. Backend `InventoryItem` model accepts `root_stock_group`.
5. `/api/inventory/items` accepts `root_stock_group` filter and returns
   `root_stock_groups` list for the dropdown.
6. CA Corner BS endpoint: when classifier doesn't recognise
   `parent_group`, falls back to `root_group` (exact match, no heuristics).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import importlib.util
import pytest

AGENT_PATH = Path("/app/desktop-agent/tally_sync_agent_v9.py")
PUBLIC = Path("/app/frontend/public/flowra-desktop-agent.py")
INV_ROUTE = Path("/app/backend/routes/inventory.py")
CA_ROUTE = Path("/app/backend/routes/ca_corner.py")
MODELS = Path("/app/backend/models.py")


@pytest.fixture(scope="module")
def agent_module():
    spec = importlib.util.spec_from_file_location("tally_agent_v986", AGENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tally_agent_v986"] = mod
    spec.loader.exec_module(mod)
    return mod


def _build_client(agent_module):
    Cls = getattr(agent_module, "TallyCollectionClient")
    agent = Cls.__new__(Cls)
    agent.tally_url = "http://stub"
    agent.session = MagicMock()
    agent.current_company = "TEST CO"
    agent.company = "TEST CO"
    return agent


def test_agent_version_v986():
    contents = AGENT_PATH.read_text(encoding="utf-8")
    assert "v9.8.6-hierarchy-walk" in contents
    assert "9.8.6-hierarchy-walk" in contents


def test_public_agent_v986_present():
    contents = PUBLIC.read_text(encoding="utf-8")
    assert "9.8.6-hierarchy-walk" in contents


def test_fetch_stock_group_parent_map_method_exists(agent_module):
    """Phase 2 ships fetch_stock_group_parent_map() to walk Tally's
    multi-level stock-group hierarchy."""
    Cls = getattr(agent_module, "TallyCollectionClient")
    assert hasattr(Cls, "fetch_stock_group_parent_map")


def test_resolve_root_group_walks_chain(agent_module):
    """The walker chases parent links until it hits a root (no parent or
    parent == self). Depth-limited at 12 to prevent infinite loops on
    malformed data."""
    agent = _build_client(agent_module)
    parent_map = {
        "10mm & 12mm 1.25 thread": "tvs automotive fastener",
        "tvs automotive fastener": "tvs sundaram fasteners",
        "tvs sundaram fasteners": "primary",
    }
    root = agent._resolve_root_group("10mm & 12mm 1.25 Thread", parent_map)
    assert root == "tvs sundaram fasteners"


def test_resolve_root_group_terminates_on_self_loop(agent_module):
    """If a group's parent == itself (Tally's "Primary" sometimes does
    this), walker must terminate — don't recurse forever. v9.8.6 also
    short-circuits when we reach a group whose parent is 'primary'."""
    agent = _build_client(agent_module)
    parent_map = {"primary": "primary"}
    root = agent._resolve_root_group("Primary", parent_map)
    assert root == "primary"


def test_resolve_root_group_unknown_returns_self(agent_module):
    """If a sub-group isn't in the map, return its lower-cased name
    (best-effort fallback so the UI still has SOMETHING to filter by)."""
    agent = _build_client(agent_module)
    root = agent._resolve_root_group("Stray Group", {})
    assert root == "stray group"


def test_inventory_item_model_accepts_root_stock_group():
    """Pydantic InventoryItem must allow root_stock_group field through."""
    sys.path.insert(0, "/app/backend")
    from models import InventoryItem
    obj = InventoryItem(
        item_id="x", item_name="x", quantity=1.0, unit="NOS",
        root_stock_group="tvs sundaram fasteners",
    )
    assert obj.root_stock_group == "tvs sundaram fasteners"


def test_inventory_endpoint_accepts_root_filter():
    """/api/inventory/items accepts root_stock_group query param."""
    contents = INV_ROUTE.read_text(encoding="utf-8")
    assert "root_stock_group: Optional[str] = None" in contents
    assert 'extra["root_stock_group"]' in contents
    # Returns list of root groups for the dropdown
    assert '"root_stock_groups"' in contents


def test_ca_corner_bs_uses_root_group_fallback():
    """When classifier returns 'unknown' for the immediate parent_group,
    BS endpoint must consult root_group field on the ledger (set by
    v9.8.6 agent)."""
    contents = CA_ROUTE.read_text(encoding="utf-8")
    assert "l.get('root_group')" in contents


def test_ledger_payload_carries_root_group():
    """fetch_all_ledgers_via_groups stores root_group on every result
    (v9.8.6) so the backend has it on import."""
    contents = AGENT_PATH.read_text(encoding="utf-8")
    # The new payload key
    assert "'root_group': root_group," in contents


def test_inventory_payload_carries_root_stock_group():
    """fetch_stock_items walks stock_group hierarchy and stamps
    root_stock_group on every item."""
    contents = AGENT_PATH.read_text(encoding="utf-8")
    assert "'root_stock_group'" in contents
    # And uses the new fetch helper
    assert "fetch_stock_group_parent_map" in contents


def test_fetch_stock_items_attaches_root_when_hierarchy_provided(agent_module):
    """End-to-end (parser-only): when fetch_stock_group_parent_map returns
    a hierarchy, every item gets root_stock_group filled correctly."""
    agent = _build_client(agent_module)
    # Stub the stock-group hierarchy fetch
    agent.fetch_stock_group_parent_map = MagicMock(return_value={
        "10mm & 12mm 1.25 thread": "tvs automotive fastener",
        "tvs automotive fastener": "tvs sundaram fasteners",
        "tvs sundaram fasteners": "primary",
        "general": "primary",
    })
    # Stub _post for fetch_stock_items
    agent._post = MagicMock(return_value={
        "ENVELOPE": {"BODY": {"DATA": {"COLLECTION": {"STOCKITEM": [
            {
                "@NAME": "TVS 10x1.25x110 A(50)",
                "NAME": "TVS 10x1.25x110 A(50)",
                "PARENT": "10mm & 12mm 1.25 Thread",
                "BASEUNITS": "NOS",
                "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
                "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
            },
            {
                "@NAME": "Misc Item",
                "NAME": "Misc Item",
                "PARENT": "General",
                "BASEUNITS": "NOS",
                "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
                "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
            },
        ]}}}}
    })
    items = agent.fetch_stock_items()
    by_name = {it["item_name"]: it for it in items}
    assert by_name["TVS 10x1.25x110 A(50)"]["root_stock_group"] == "tvs sundaram fasteners"
    # Item directly under "General" — General's parent is "primary", so the
    # user-visible root IS "general" itself (not "primary").
    assert by_name["Misc Item"]["root_stock_group"] == "general"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
