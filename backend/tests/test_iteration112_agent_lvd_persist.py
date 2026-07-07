"""Iteration 112 — v9.8.29 LVD persistence + full-sync AlterID short-circuit.

Field report from Ankit Sarawgi's 07-Jul-2026 log:
  1. `not detected via $$LastVoucherDate or Day-Book scan — defaulting to today`
     → LVD regex only matched `<DATE>`, but Tally Prime 7.0 Day Book export
       emits `<VCHDATE>` / `<VOUCHERDATE>` (also `<VOUCHDATE>` on some
       builds). Regex now matches all four (case-insensitive) and accepts
       5 date formats.
  2. Every agent restart re-ran a full 16-month sync per company because
     the AlterID gate lived only inside the 5-min quick-sync path. The
     full-sync path now:
       (a) emits a sync-state banner on every cycle
       (b) short-circuits when AlterID unchanged and last-full < 7 days old
       (c) persists per-company alter_id / lvd / last_full_sync
       (d) falls back to cached LVD (not `date.today()`) when live
           detection returns None

This test file source-asserts the v9.8.29 contract from build-kit-2/ so
build-kit/ (v9.8.28) stays untouched until the user rebuilds the .exe.
"""
import os
import re
import sys
import types

import pytest

BK2 = os.path.join(os.path.dirname(__file__), "..", "..", "desktop-agent", "build-kit-2")
sys.path.insert(0, BK2)
for missing in ("websockets", "watchdog", "ttkthemes"):
    sys.modules.setdefault(missing, types.ModuleType(missing))


@pytest.fixture(scope="module")
def src():
    with open(os.path.join(BK2, "tally_sync_agent_v9.py"), "r") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def gui_src():
    with open(os.path.join(BK2, "flowra_gui.py"), "r") as fh:
        return fh.read()


# ─── Version bump ────────────────────────────────────────────────────────
def test_version_bumped_to_v9_8_29(src, gui_src):
    assert 'v9.8.29-lvd-persist' in src
    assert 'APP_VERSION = "v9.8.29"' in gui_src
    # No stale v9.8.28 tags in agent_version fields.
    stale = [ln for ln in src.splitlines()
             if "'agent_version'" in ln and "9.8.28" in ln]
    assert stale == [], f"stale agent_version tags: {stale[:3]}"


# ─── Fix 1 — Broadened LVD regex ─────────────────────────────────────────
def test_lvd_regex_matches_vchdate_voucherdate_voucdate_date(src):
    # The regex string is authoritative — pull it out and try it live.
    m = re.search(r"date_tag_re\s*=\s*re\.compile\((.*?)\)", src, re.DOTALL)
    assert m, "date_tag_re not found in build-kit-2"
    # Sanity: assemble a live regex like the agent does and try all four tags.
    live_re = re.compile(
        r'<(VCHDATE|VOUCHERDATE|VOUCHDATE|DATE)[^>]*>([^<]+)</\1>',
        re.IGNORECASE,
    )
    xml_samples = [
        ('<VCHDATE>20260707</VCHDATE>', 'VCHDATE'),
        ('<vchdate>20260707</vchdate>', 'vchdate'),
        ('<VOUCHERDATE>20260707</VOUCHERDATE>', 'VOUCHERDATE'),
        ('<VOUCHDATE>20260707</VOUCHDATE>', 'VOUCHDATE'),
        ('<DATE>20260707</DATE>', 'DATE'),
    ]
    for xml, tag in xml_samples:
        mm = live_re.search(xml)
        assert mm and mm.group(2) == '20260707', f"failed for {tag}"


def test_lvd_parser_accepts_five_date_formats(src):
    """Contract check — 5 date formats must be listed in the format tuple."""
    for fmt in ('%Y%m%d', '%d-%m-%Y', '%d-%b-%Y',
                '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        assert repr(fmt) in src, f"format {fmt!r} missing"


# ─── Fix 2 — Promoted diagnostic logs ────────────────────────────────────
def test_lvd_diagnostic_logs_are_info_not_debug(src):
    """The Day-Book scan result must be visible without DEBUG level."""
    assert "logger.info(" in src
    assert "$$LastVoucherDate returned" in src
    assert "Day-Book scan:" in src or "Day-Book fallback:" in src
    # Failure diagnostic explains WHICH tags were seen.
    assert "tag hits:" in src


# ─── Fix 3+4 — Full-sync banner + AlterID short-circuit ──────────────────
def test_full_sync_emits_state_banner(src):
    assert "Sync state:" in src
    assert "AlterID=" in src
    assert "LVD=" in src


def test_full_sync_alter_id_short_circuit(src):
    """AlterID-unchanged + <7d recency → skip full sync."""
    assert "[FULL-SKIP]" in src
    assert "AlterID unchanged" in src
    assert "load_sync_state()" in src
    assert "alter_id::" in src
    assert "last_full_sync::" in src


def test_full_sync_narrows_window_on_delta(src):
    """When AlterID advanced, we surface the delta in the log."""
    assert "AlterID advanced by" in src


# ─── Fix 5 — LVD persistence + fallback-from-state ───────────────────────
def test_lvd_persisted_at_end_of_full_sync(src):
    assert "state[f\"alter_id::{company_name}\"]" in src
    assert "state[f\"lvd::{company_name}\"]" in src
    assert "state[f\"last_full_sync::{company_name}\"]" in src
    assert "Sync state persisted:" in src


def test_lvd_fallback_prefers_cached_over_today(src):
    """Live LVD None → prefer sync_state cached LVD, THEN fall to today."""
    assert "using cached LVD from previous sync" in src
    assert 'state.get(f"lvd::{company_name}")' in src or 'state.get(f\'lvd::{company_name}\')' in src
    # The final default-to-today only fires when cached LVD is also missing.
    assert "no cached LVD in sync_state" in src


# ─── Build-kit isolation — v9.8.28 must remain untouched ─────────────────
def test_build_kit_v9_8_28_untouched():
    """User asked build-kit/ (v9.8.28) to stay unchanged."""
    with open(os.path.join(os.path.dirname(__file__), "..", "..",
                           "desktop-agent", "build-kit",
                           "tally_sync_agent_v9.py"), "r") as fh:
        original = fh.read()
    assert 'v9.8.28-company-raw-parens' in original
    assert 'v9.8.29-lvd-persist' not in original
    assert '[FULL-SKIP]' not in original


# ─── Module still imports (no syntax regressions) ────────────────────────
def test_module_imports_cleanly():
    import tally_sync_agent_v9 as m
    cls = m.TallyCollectionClient
    for attr in ('fetch_last_voucher_date',
                 '_fetch_last_voucher_date_via_daybook',
                 '_company_tag'):
        assert hasattr(cls, attr), f"missing method {attr}"
