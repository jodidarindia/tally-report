"""iter-162: Busy Agent group-hierarchy walk.

BSA-style Busy books nest their debtors/creditors under user-created
sub-groups whose ParentGrp points to the built-in root (116/117/…).
Older ``_resolve_category`` returned "other" for the sub-group code
and dropped every customer under it. This test locks in the walking
behaviour introduced in v1.6.0.

The full agent module can't import in a Linux pytest env (Windows /
pyodbc deps), so we replicate the resolver logic here — it's a tiny,
pure function that mirrors the one shipped in
``desktop-agent/build-kit-busy/flowra_busy_agent.py``.
"""
import pathlib
import re


ACCOUNT_GROUP_MAP = {
    116: "sundry_debtors", 117: "sundry_creditors",
    111: "cash", 112: "bank",
    122: "purchase", 123: "sale",
}


def _resolve_category(parent_grp_code, group_map, parent_map):
    """Mirror of the agent's v1.6.0 walker."""
    code = str(parent_grp_code or "").strip()
    seen = set()
    while code and code not in seen:
        seen.add(code)
        cat = group_map.get(code)
        if cat and cat != "other":
            return cat
        try:
            built_in = ACCOUNT_GROUP_MAP.get(int(code))
            if built_in:
                return built_in
        except (ValueError, TypeError):
            pass
        code = str(parent_map.get(code, "") or "").strip()
    return "other"


def test_agent_source_file_has_walker():
    """Guardrail: ensure the shipped agent source still contains the walk."""
    src = pathlib.Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    # Function signature + walking loop hallmarks.
    assert "def _resolve_category" in src
    assert "while code and code not in seen" in src
    assert "self._parent_map.get(code" in src
    # Version bumped to 1.6.1 for stock-group name-resolution fix.
    assert re.search(r'VERSION\s*=\s*"1\.6\.[01]"', src), "agent VERSION must be 1.6.0+"


def test_direct_root_code_resolves():
    assert _resolve_category("116", {"116": "sundry_debtors"}, {}) == "sundry_debtors"


def test_nested_subgroup_walks_up_to_root():
    """BSA reality: customers reference sub-group 5001, whose ParentGrp is 116."""
    group_map = {"116": "sundry_debtors", "5001": "other", "5002": "other"}
    parent_map = {"5001": "116", "5002": "5001"}
    assert _resolve_category("5001", group_map, parent_map) == "sundry_debtors"
    assert _resolve_category("5002", group_map, parent_map) == "sundry_debtors"


def test_creditor_hierarchy_walks_too():
    group_map = {"117": "sundry_creditors", "6001": "other"}
    parent_map = {"6001": "117"}
    assert _resolve_category("6001", group_map, parent_map) == "sundry_creditors"


def test_falls_back_to_account_group_map_when_group_not_cached():
    # _group_map has no direct hit, but 116 is in the built-in ACCOUNT_GROUP_MAP.
    assert _resolve_category("5001", {}, {"5001": "116"}) == "sundry_debtors"


def test_cycles_dont_infinite_loop():
    group_map = {"5001": "other", "5002": "other"}
    parent_map = {"5001": "5002", "5002": "5001"}
    assert _resolve_category("5001", group_map, parent_map) == "other"


def test_empty_or_missing_code_returns_other():
    assert _resolve_category("", {}, {}) == "other"
    assert _resolve_category(None, {}, {}) == "other"
    assert _resolve_category("9999", {}, {}) == "other"
