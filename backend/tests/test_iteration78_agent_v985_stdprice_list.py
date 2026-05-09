"""
Iteration 78 — Tally Sync Agent v9.8.5-stdprice-list.

User-reported bug: "Standard sales price exists in tally for every stock.
Then why are you showing last sale price."

Verified live: 0 of 7,712 items had standard_price > 0 even though the
user has set "Standard Selling Rate" on every stock item master.

Root cause: the agent's STANDARDPRICELIST walker was reading the wrong
key. Tally exports repeated `<STANDARDPRICELIST.LIST>` elements DIRECTLY
under each `<STOCKITEM>` — xmltodict surfaces them at
`si['STANDARDPRICELIST.LIST']`, NOT nested inside a `STANDARDPRICELIST`
parent. The previous code did `si.get('STANDARDPRICELIST', ...)` and
never entered the loop.

Fix: read `STANDARDPRICELIST.LIST` directly (and `STANDARDPRICEDETAILS.LIST`
for Tally Prime 3+), pick the entry whose APPLICABLEFROM <= today (most
recent first), and read RATE / STDPRICE / STANDARDPRICE in that order.

These tests simulate xmltodict's actual output and run the agent's parser
in isolation. We don't need a live Tally instance.
"""
import os
import sys
import importlib.util
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
import pytest


AGENT_PATH = Path("/app/desktop-agent/tally_sync_agent_v9.py")


@pytest.fixture(scope="module")
def agent_module():
    """Import the desktop agent module without running its main()."""
    spec = importlib.util.spec_from_file_location("tally_agent_v9", AGENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tally_agent_v9"] = mod
    # Stub heavy desktop deps (tkinter, requests) so import works in container
    spec.loader.exec_module(mod)
    return mod


def _build_agent_minimal(agent_module):
    """Build a TallyCollectionClient instance with the Tally HTTP layer
    mocked. Only need the parser methods."""
    Cls = getattr(agent_module, "TallyCollectionClient")
    agent = Cls.__new__(Cls)
    agent.tally_url = "http://stub"
    agent.session = MagicMock()
    agent.current_company = "TEST CO"
    agent.company = "TEST CO"
    return agent


def _stub_post_returning_stockitems(agent, stockitems):
    """Stub `_post` to return our synthetic items. The agent calls
    `self._get_collection_items(data, 'STOCKITEM')` to extract."""
    agent._post = MagicMock(return_value={
        "ENVELOPE": {"BODY": {"DATA": {"COLLECTION": {"STOCKITEM": stockitems}}}}
    })


def test_stdprice_list_direct_key(agent_module):
    """xmltodict surfaces <STANDARDPRICELIST.LIST> at si['STANDARDPRICELIST.LIST'] —
    NOT inside a STANDARDPRICELIST parent. The parser must read the direct key."""
    agent = _build_agent_minimal(agent_module)
    stockitems = [{
        "@NAME": "Test Widget A",
        "NAME": "Test Widget A",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        "PARTNO": "TWA-001",
        "STANDARDPRICELIST.LIST": [
            {"APPLICABLEFROM": "20240401", "RATE": "100", "RATEPERUNIT": "NOS"},
            {"APPLICABLEFROM": "20250401", "RATE": "150", "RATEPERUNIT": "NOS"},
        ],
        "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
        "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    assert len(items) == 1, items
    # Most-recent applicable rate is 150 (20250401 < today)
    assert items[0]["standard_price"] == 150.0, items[0]
    assert items[0]["standard_price_source"] == "tally_master"


def test_stdprice_list_single_entry_dict(agent_module):
    """When there's only one entry, xmltodict returns a dict (not a list)."""
    agent = _build_agent_minimal(agent_module)
    stockitems = [{
        "@NAME": "Test Widget B",
        "NAME": "Test Widget B",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        "STANDARDPRICELIST.LIST": {  # single entry → dict, not list
            "APPLICABLEFROM": "20240101",
            "RATE": "75",
            "RATEPERUNIT": "NOS",
        },
        "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
        "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    assert items[0]["standard_price"] == 75.0


def test_stdprice_skips_future_dated(agent_module):
    """A future-dated APPLICABLEFROM (e.g. 21260101) should NOT be chosen
    over a past-dated one — Tally semantically only applies dates that
    have already arrived."""
    agent = _build_agent_minimal(agent_module)
    today = datetime.now().strftime("%Y%m%d")
    stockitems = [{
        "@NAME": "Test Widget C",
        "NAME": "Test Widget C",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        "STANDARDPRICELIST.LIST": [
            {"APPLICABLEFROM": "20240101", "RATE": "100"},
            {"APPLICABLEFROM": "21260101", "RATE": "999"},  # future
        ],
        "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
        "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    # Future entry skipped; 100 chosen as the most-recent applicable rate
    assert items[0]["standard_price"] == 100.0, items[0]


def test_stdprice_picks_most_recent_applicable(agent_module):
    """Three entries — 2023, 2024, 2025-04 — picks 2025 (highest applicable)."""
    agent = _build_agent_minimal(agent_module)
    stockitems = [{
        "@NAME": "Test Widget D",
        "NAME": "Test Widget D",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        "STANDARDPRICELIST.LIST": [
            {"APPLICABLEFROM": "20230101", "RATE": "50"},
            {"APPLICABLEFROM": "20240101", "RATE": "75"},
            {"APPLICABLEFROM": "20250401", "RATE": "120"},
        ],
        "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
        "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    assert items[0]["standard_price"] == 120.0


def test_stdprice_details_list_tally_prime_3(agent_module):
    """Tally Prime 3+ exports `<STANDARDPRICEDETAILS.LIST>` instead.
    Parser must pick that up too."""
    agent = _build_agent_minimal(agent_module)
    stockitems = [{
        "@NAME": "Test Widget E",
        "NAME": "Test Widget E",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        "STANDARDPRICEDETAILS.LIST": {
            "APPLICABLEFROM": "20240101",
            "RATE": "200",
            "RATEPERUNIT": "NOS",
        },
        "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
        "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    assert items[0]["standard_price"] == 200.0


def test_stdprice_no_master_returns_zero(agent_module):
    """When no STDPRICE master is set, std_price MUST be 0 (not closing rate).
    This is the v9.8.2 invariant — we do NOT silently quote cost."""
    agent = _build_agent_minimal(agent_module)
    stockitems = [{
        "@NAME": "Test Widget F",
        "NAME": "Test Widget F",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        # NO STANDARDPRICELIST.LIST and NO direct STANDARDPRICE
        "OPBAL": "10", "OPRATE": "50", "OPVAL": "500", "OPQTY": "10 NOS",
        "CLBAL": "5", "CLRATE": "60", "CLVAL": "300", "CLQTY": "5 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    assert items[0]["standard_price"] == 0.0, items[0]
    assert items[0]["standard_price_source"] == "unset"
    # Cost (closing rate) is preserved on `price` field separately — not leaked
    assert items[0]["price"] == 60.0


def test_stdprice_priority_compute_wins_over_list(agent_module):
    """When TDL COMPUTE returns a non-zero STDPRC, it should win — that's the
    fastest path. The .LIST walker is the fallback."""
    agent = _build_agent_minimal(agent_module)
    stockitems = [{
        "@NAME": "Test Widget G",
        "NAME": "Test Widget G",
        "PARENT": "Widgets",
        "BASEUNITS": "NOS",
        "STDPRC": "999",  # COMPUTE result
        "STANDARDPRICELIST.LIST": [
            {"APPLICABLEFROM": "20240101", "RATE": "100"},
        ],
        "OPBAL": "0", "OPRATE": "0", "OPVAL": "0", "OPQTY": "0 NOS",
        "CLBAL": "0", "CLRATE": "0", "CLVAL": "0", "CLQTY": "0 NOS",
    }]
    _stub_post_returning_stockitems(agent, stockitems)
    items = agent.fetch_stock_items()
    assert items[0]["standard_price"] == 999.0


def test_public_agent_stamped_v985():
    public = Path("/app/frontend/public/flowra-desktop-agent.py")
    if not public.exists():
        pytest.skip("public agent not present")
    contents = public.read_text(encoding="utf-8")
    assert "9.8.5-stdprice-list" in contents or "9.8.6-hierarchy-walk" in contents or "9.8.7-aliases-perf" in contents
    # Direct-key reads must be present
    assert "STANDARDPRICELIST.LIST" in contents
    assert "STANDARDPRICEDETAILS.LIST" in contents
    # Old broken nested-parent fallback must be gone
    assert "si.get('STANDARDPRICELIST', si.get('STDPRICELIST', None))" not in contents


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
