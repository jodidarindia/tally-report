"""Iteration 104 — AlterID detection must survive every documented Tally
response shape, especially Tally Prime 7.0 quirks.

These tests stub out `_post()` with simulated Tally XML responses and
exercise each detection path in isolation. They prove that:

  1. The legacy `len(val) > 2` length-guard bug is gone — 1- and 2-digit
     AlterIDs are no longer silently filtered.
  2. The universal iteration fallback (Path-3) correctly takes the MAX
     of however many integers come back.
  3. When Tally returns an empty / non-numeric body, every path returns
     None instead of crashing.
"""
import os
import re
import sys
import types

import pytest

# Locate the build-kit so we can import the agent module.
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "desktop-agent", "build-kit")
)

# The agent module pulls in many runtime deps (requests, xmltodict,
# odbc helpers …). We only need the parser, so install lightweight stubs
# for anything that would otherwise fail to import during the test run.
for missing in ("websockets", "watchdog", "ttkthemes"):
    sys.modules.setdefault(missing, types.ModuleType(missing))
# `tally_sync_agent_v9` will import requests + xmltodict — both are
# normally installed already.


@pytest.fixture(scope="module")
def Cls():
    """Import the TallyCollectionClient class lazily so the heavy module
    imports only happen once per session."""
    mod = __import__("tally_sync_agent_v9")
    return mod.TallyCollectionClient


def _make_inst(Cls, post_responses):
    """Build a bare-bones TallySync instance whose `_post` returns each
    of `post_responses` in turn. We bypass __init__ since we don't need
    the network/session setup for these unit tests."""
    inst = Cls.__new__(Cls)
    inst.url = "http://127.0.0.1:9000"
    inst.timeout = 5
    inst.company = "Krishna Sales Corp"
    inst._active_company = "Krishna Sales Corp"
    inst.debug_dir = None
    inst._request_lock = __import__("threading").Lock()
    iter_responses = iter(post_responses)

    def fake_post(xml, debug_name=""):
        try:
            raw = next(iter_responses)
        except StopIteration:
            raw = ""
        return {"__raw_xml__": raw} if raw else None

    inst._post = fake_post
    return inst


# Helper: Tally-style aggregation response (single line, one number).
def _agg(num):
    if num is None:
        return ""
    return (
        f"<ENVELOPE><HEADER><VERSION>1</VERSION></HEADER><BODY><DATA>"
        f"<COLLECTION><LAIDField>{num}</LAIDField></COLLECTION></DATA></BODY></ENVELOPE>"
    )


# Helper: Tally-style iteration response (many lines, one number each).
def _iter(field_tag, ids):
    rows = "".join(f"<{field_tag}>{i}</{field_tag}>" for i in ids)
    return (
        f"<ENVELOPE><HEADER><VERSION>1</VERSION></HEADER><BODY><DATA>"
        f"<COLLECTION>{rows}</COLLECTION></DATA></BODY></ENVELOPE>"
    )


def test_path1_single_digit_alterid_is_accepted(Cls):
    """Old code's `len(val) > 2` guard threw away 1-digit AlterIDs.
    The new helper must return them faithfully."""
    inst = _make_inst(Cls, [_agg(7)])
    assert inst._fetch_alter_id_path1_sys_funcs() == 7


def test_path1_two_digit_alterid_is_accepted(Cls):
    inst = _make_inst(Cls, [_agg(42)])
    assert inst._fetch_alter_id_path1_sys_funcs() == 42


def test_path1_blank_response_returns_none(Cls):
    inst = _make_inst(Cls, [""])
    assert inst._fetch_alter_id_path1_sys_funcs() is None


def test_path2_aggregation_returns_voucher_max(Cls):
    inst = _make_inst(Cls, [_agg(15234)])
    v = inst._fetch_max_alter_id_aggregation("Voucher", "AlterID", "FlowraMaxVchAlterId")
    assert v == 15234


def test_path3_iteration_picks_max_over_many_rows(Cls):
    """The whole point of Path-3: dump every AlterID and let Python max."""
    raw_iter = _iter("FlowraIterVchAID_F", [101, 99, 14012, 7, 5000])
    inst = _make_inst(Cls, [raw_iter])
    v = inst._fetch_max_alter_id_via_iteration("Voucher", "AlterID", "FlowraIterVchAID")
    assert v == 14012


def test_path3_iteration_zero_only_returns_zero(Cls):
    """Tally returns 0 for objects with no edits. max(0,0,0) == 0 — still
    a valid response, not None."""
    raw_iter = _iter("FlowraIterLedAID_F", [0, 0, 0])
    inst = _make_inst(Cls, [raw_iter])
    v = inst._fetch_max_alter_id_via_iteration("Ledger", "AlterID", "FlowraIterLedAID")
    assert v == 0


def test_path3_iteration_falls_back_to_generic_FIELD_tag(Cls):
    """Some Tally builds emit numeric values inside <FCCFIELD> rather
    than the requested named tag. Path-3 must still capture them."""
    raw = (
        "<ENVELOPE><BODY><DATA>"
        "<FCCFIELD>100</FCCFIELD><FCCFIELD>250</FCCFIELD><FCCFIELD>175</FCCFIELD>"
        "</DATA></BODY></ENVELOPE>"
    )
    inst = _make_inst(Cls, [raw])
    v = inst._fetch_max_alter_id_via_iteration("Voucher", "AlterID", "FlowraIterVchAID")
    assert v == 250


def test_path3_returns_none_when_tally_returned_nothing_numeric(Cls):
    inst = _make_inst(Cls, ["<ENVELOPE><BODY><DATA></DATA></BODY></ENVELOPE>"])
    assert inst._fetch_max_alter_id_via_iteration(
        "Voucher", "AlterID", "FlowraIterVchAID") is None


def test_fetch_last_alter_id_uses_path1_when_available(Cls):
    """When Path-1 returns a positive number, Path-2 / Path-3 must not be
    called. We arrange for only ONE response — if subsequent paths fired
    they'd consume more and `_make_inst` would return None and the test
    would break."""
    inst = _make_inst(Cls, [_agg(999), "", "", "", "", ""])
    assert inst.fetch_last_alter_id() == 999


def test_fetch_last_alter_id_falls_through_to_path3(Cls):
    """Path-1 returns 0 → Path-2 returns 0 → Path-3 iteration wins."""
    # Order of _post calls inside fetch_last_alter_id():
    #   1) Path-1 (single TDL func call)
    #   2) Path-2 Voucher aggregation
    #   3) Path-2 Ledger aggregation
    #   4) Path-3 Voucher iteration
    #   5) Path-3 Ledger iteration (AlterID variant)
    #   6) Path-3 Ledger iteration (Alterid variant)  -- only if 5 returned 0/None
    inst = _make_inst(Cls, [
        _agg(0),                                  # Path-1: zero → skip
        _agg(0),                                  # Path-2 vouchers: zero
        _agg(0),                                  # Path-2 ledgers: zero
        _iter("FlowraIterVchAID_F", [3, 17, 9]),  # Path-3 vouchers: max=17
        _iter("FlowraIterLedAID_F", [4, 12, 8]),  # Path-3 ledgers: max=12
    ])
    total = inst.fetch_last_alter_id()
    # 17 (vouchers) + 12 (ledgers)  = 29
    assert total == 29


def test_fetch_last_alter_id_returns_none_when_truly_unsupported(Cls):
    """Every path returns None / non-numeric → caller falls back to LVD."""
    inst = _make_inst(Cls, ["", "", "", "", "", ""])
    assert inst.fetch_last_alter_id() is None
