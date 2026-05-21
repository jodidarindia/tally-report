"""Iteration 105 — v9.8.26 AlterID fixes for Tally Prime 7.0.

Built directly from the real customer (ASA Autotech) daybook XML, which
showed THREE root causes of the v9.8.25 "all 3 paths failed" symptom:

  1. Tally Prime 7.0 lowercases every response tag — the regex was
     case-sensitive so `<flowrayitervchaid_f>` was never matched.
  2. Voucher collections come back EMPTY without SVFROMDATE/SVTODATE —
     covered by sniffing the generated XML payload for those variables.
  3. Path-4 (NEW) scrapes `<alterid>NUMBER</alterid>` directly from any
     cached voucher / daybook export — proven against the real XML
     where the customer's voucher carried `<alterid> 12877</alterid>`.
"""
import os
import re
import sys
import tempfile
import threading
import types

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "desktop-agent", "build-kit")
)
for missing in ("websockets", "watchdog", "ttkthemes"):
    sys.modules.setdefault(missing, types.ModuleType(missing))


@pytest.fixture(scope="module")
def Cls():
    mod = __import__("tally_sync_agent_v9")
    return mod.TallyCollectionClient


# Real fragment taken verbatim from /var/log uploaded customer XML
# (ASA AUTOTECH INDIA PRIVATE LIMITED daybook export, 21 May 2026).
REAL_CUSTOMER_XML_FRAGMENT = """
<envelope><body><importdata><requestdata>
  <tallymessage>
    <voucher remoteid="0ab0a616-eff8-4cff-8f6e-82790aed7f4d-00001926">
      <date>20260521</date>
      <vouchertypename>Payment</vouchertypename>
      <vouchernumber>VPAY2627/067</vouchernumber>
      <alterid> 12877</alterid>
      <masterid> 6438</masterid>
      <voucherkey>198264280317960</voucherkey>
    </voucher>
  </tallymessage>
  <tallymessage>
    <voucher>
      <vouchernumber>VPAY2627/068</vouchernumber>
      <alterid>12880</alterid>
      <date>20260521</date>
    </voucher>
  </tallymessage>
  <tallymessage>
    <voucher>
      <vouchernumber>VPAY2627/069</vouchernumber>
      <alterid>12879</alterid>
    </voucher>
  </tallymessage>
</requestdata></importdata></body></envelope>
"""


def _make_inst(Cls, post_responses=None, debug_dir=None):
    """Build a TallyCollectionClient instance whose `_post` returns each
    of `post_responses` in turn (or empty) and whose `debug_dir` is the
    given path."""
    inst = Cls.__new__(Cls)
    inst.url = "http://127.0.0.1:9000"
    inst.timeout = 5
    inst.company = "ASA Autotech India Private Limited"
    inst._active_company = inst.company
    inst.debug_dir = debug_dir
    inst._request_lock = threading.Lock()
    iter_responses = iter(post_responses or [])

    def fake_post(xml, debug_name=""):
        try:
            raw = next(iter_responses)
        except StopIteration:
            raw = ""
        # Capture the XML payload so date-variable presence can be asserted.
        fake_post.last_payload = xml
        return {"__raw_xml__": raw} if raw else None
    fake_post.last_payload = ""
    inst._post = fake_post
    return inst


def test_path3_uses_case_insensitive_regex_for_prime_7_lowercase_tags(Cls):
    """Tally Prime 7.0 lowercases tags. v9.8.25 would have missed every
    integer in this response because of case sensitivity."""
    lower_resp = (
        "<envelope><body>"
        "<flowraitervchaid_f>10</flowraitervchaid_f>"
        "<flowraitervchaid_f>15234</flowraitervchaid_f>"
        "<flowraitervchaid_f>9</flowraitervchaid_f>"
        "</body></envelope>"
    )
    inst = _make_inst(Cls, [lower_resp])
    v = inst._fetch_max_alter_id_via_iteration(
        "Voucher", "AlterID", "FlowraIterVchAID"
    )
    assert v == 15234


def test_path3_query_includes_date_variables_for_prime_7(Cls):
    """Tally Prime 7.0 needs SVFROMDATE/SVTODATE on Voucher collections —
    otherwise Tally returns an empty <COLLECTION/>. Assert they're sent."""
    inst = _make_inst(Cls, [""])
    inst._fetch_max_alter_id_via_iteration("Voucher", "AlterID", "FlowraIterVchAID")
    payload = inst._post.last_payload
    assert "SVFROMDATE" in payload
    assert "SVTODATE" in payload


def test_path4_scrapes_alterid_from_real_customer_xml(Cls, tmp_path):
    """Drop the ACTUAL daybook XML the customer sent into a debug-cache
    folder and verify Path-4 finds the cumulative AlterID."""
    cache = tmp_path / "debug_cache"
    cache.mkdir()
    (cache / "daybook_lvd_raw.xml").write_text(
        REAL_CUSTOMER_XML_FRAGMENT, encoding="utf-8"
    )
    inst = _make_inst(Cls, [], debug_dir=str(cache))
    v = inst._fetch_max_alter_id_from_cached_exports()
    # 3 vouchers with AlterIDs: 12877, 12880, 12879 → max = 12880
    assert v == 12880


def test_path4_handles_leading_whitespace_in_real_response(Cls, tmp_path):
    """Tally pads numeric fields with spaces: `<alterid> 12877</alterid>`.
    The Path-4 regex must strip these or the value is lost."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "vchr.xml").write_text(
        "<envelope><alterid>   42</alterid><alterid>   7</alterid></envelope>",
        encoding="utf-8",
    )
    inst = _make_inst(Cls, [], debug_dir=str(cache))
    assert inst._fetch_max_alter_id_from_cached_exports() == 42


def test_path4_returns_none_when_cache_dir_missing(Cls):
    inst = _make_inst(Cls, [], debug_dir="/nonexistent/path/xyz")
    assert inst._fetch_max_alter_id_from_cached_exports() is None


def test_path4_returns_none_when_cache_has_no_alterid_tags(Cls, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "junk.xml").write_text(
        "<envelope><name>Krishna Sales</name><amount>1234.56</amount></envelope>",
        encoding="utf-8",
    )
    inst = _make_inst(Cls, [], debug_dir=str(cache))
    assert inst._fetch_max_alter_id_from_cached_exports() is None


def test_path4_scans_only_last_8_files_by_mtime(Cls, tmp_path):
    """Path-4 caps the scan at 8 most-recent files so a stale 50-file
    cache doesn't blow the budget. The newest file's max must win even
    if older files have larger AlterIDs."""
    cache = tmp_path / "cache"
    cache.mkdir()
    import time as _t
    # Create 12 files. Files 0-3 (oldest) have huge AlterIDs.
    # Files 4-11 (newest) have smaller ones. Path-4 must scan only 4-11.
    for i in range(12):
        fp = cache / f"vchr_{i:02d}.xml"
        # First 4 files are "old" with huge values, rest are "new" with smaller.
        if i < 4:
            val = 999999
        else:
            val = 100 + i
        fp.write_text(f"<envelope><alterid>{val}</alterid></envelope>", encoding="utf-8")
        # Bump mtime so file index determines age. Newer files = bigger index.
        os.utime(fp, (1_000_000_000 + i, 1_000_000_000 + i))
    inst = _make_inst(Cls, [], debug_dir=str(cache))
    v = inst._fetch_max_alter_id_from_cached_exports()
    # Newest 8 files are indices 4..11 with values 104..111 → max = 111
    assert v == 111


def test_fetch_last_alter_id_path4_triggers_when_paths_1_2_3_all_fail(Cls, tmp_path):
    """Full integration: all 3 dedicated AlterID queries come back empty,
    but Path-4 finds 12880 in the customer's cached daybook export."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "daybook.xml").write_text(REAL_CUSTOMER_XML_FRAGMENT, encoding="utf-8")
    # Order of fake _post responses inside fetch_last_alter_id():
    #   1) Path-1 sys-funcs                  → ""  (empty)
    #   2) Path-2 vouchers aggregation        → ""
    #   3) Path-2 ledgers aggregation         → ""
    #   4) Path-3 vouchers iteration          → ""
    #   5) Path-3 ledgers iteration AlterID   → ""
    #   6) Path-3 ledgers iteration Alterid   → ""
    inst = _make_inst(Cls, ["", "", "", "", "", ""], debug_dir=str(cache))
    v = inst.fetch_last_alter_id()
    assert v == 12880
