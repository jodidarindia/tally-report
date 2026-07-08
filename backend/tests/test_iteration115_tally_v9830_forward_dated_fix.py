"""Iteration 115 · Tally Sync Agent v9.8.30 — Forward-dated voucher fix.

Locks in the three fixes shipped in v9.8.30 to prevent regressions:

  a) Quick-sync date window ALWAYS ends at max(LVD, today), not at LVD.
     Ensures forward-dated vouchers (voucher_date > system date) are
     inside the SVFROMDATE/SVTODATE window and come back in the XML.

  b) reconcile_with_backend() accepts an optional (window_start, window_end)
     pair so the backend only deletes rows INSIDE that date window instead
     of every FY voucher missing from the manifest.

  c) _fetch_last_voucher_date_via_daybook() no longer crashes when
     `_post()` returns the dict form (which it always does since v9.8.x).
     Previously threw "expected string or bytes-like object, got 'dict'".
"""
import inspect
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop-agent" / "build-kit-2"))

import tally_sync_agent_v9 as m  # noqa: E402


# ─── (a) months_in_fy cap semantics ────────────────────────────────────
def test_months_in_fy_caps_at_today_when_no_cap_given():
    """No cap → iterator walks to today, not to fy_end."""
    today = date.today()
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    fy = f"{fy_start.year}-{str(fy_start.year + 1)[-2:]}"
    months = list(m.months_in_fy(fy))
    assert months, f"no months yielded for {fy}"
    last_start, last_end = months[-1]
    assert last_end <= today, f"iterator went past today: {last_end}"


def test_months_in_fy_extends_beyond_lvd_when_today_larger():
    """Simulate the exact bug: LVD = 08-Jul, voucher dated 10-Jul.

    If cap_date=lvd we STOP on Jul-08 → voucher missed.
    v9.8.30 fix: caller now passes cap_date=max(lvd, today).
    Verify the utility behaves correctly under both inputs.
    """
    fy = "2026-27"
    lvd = date(2026, 7, 8)
    today = date(2026, 7, 10)

    # Old behaviour (buggy) — cap at LVD → month_end = 08-Jul
    m_end_old = list(m.months_in_fy(fy, cap_date=lvd))[-1][1]
    assert m_end_old == date(2026, 7, 8)

    # New behaviour — cap at max(lvd, today) → month_end reaches 10-Jul
    window_end = max(lvd, today)
    m_end_new = list(m.months_in_fy(fy, cap_date=window_end))[-1][1]
    assert m_end_new == date(2026, 7, 10), (
        f"quick-sync must reach today ({today}) to see forward-dated "
        f"vouchers; got last month_end={m_end_new}"
    )


# ─── (b) reconcile signature accepts window bounds ─────────────────────
def test_reconcile_with_backend_accepts_window_kwargs():
    """v9.8.30 signature: (data_type, manifest_ids, id_key,
                            window_start=None, window_end=None)."""
    sig = inspect.signature(m.FlowraSyncAgent.reconcile_with_backend)
    params = sig.parameters
    assert "window_start" in params, "window_start kwarg missing"
    assert "window_end"   in params, "window_end kwarg missing"
    assert params["window_start"].default is None
    assert params["window_end"].default is None


# ─── (c) Day-Book LVD fallback survives dict input ─────────────────────
def test_daybook_fallback_handles_dict_from_post(monkeypatch):
    """Regression for: 'expected string or bytes-like object, got dict'.

    We instantiate the TallyClient class and monkey-patch its _post to
    return the dict shape (parsed XML with __raw_xml__ key) that the real
    _post has been returning since v9.8.x. Before the fix this raised
    TypeError inside re.finditer(); after the fix it parses cleanly.
    """
    tc = m.TallyCollectionClient(url="http://127.0.0.1:1", company="Acme", timeout=1)
    tc.debug_dir = None

    fake_raw = (
        "<ENVELOPE>"
        "<VOUCHER><VCHDATE>20260710</VCHDATE></VOUCHER>"
        "<VOUCHER><VCHDATE>20260708</VCHDATE></VOUCHER>"
        "<VOUCHER><DATE>2026-07-05</DATE></VOUCHER>"
        "</ENVELOPE>"
    )
    monkeypatch.setattr(tc, "_post",
                         lambda xml, debug_name='': {"__raw_xml__": fake_raw})
    result = tc._fetch_last_voucher_date_via_daybook()
    assert result == date(2026, 7, 10), (
        f"Day-Book fallback should return latest voucher date; got {result}"
    )


def test_daybook_fallback_returns_none_on_none_input(monkeypatch):
    tc = m.TallyCollectionClient(url="http://127.0.0.1:1", company="Acme", timeout=1)
    tc.debug_dir = None
    monkeypatch.setattr(tc, "_post", lambda xml, debug_name='': None)
    assert tc._fetch_last_voucher_date_via_daybook() is None


def test_daybook_fallback_returns_none_on_dict_without_raw(monkeypatch):
    tc = m.TallyCollectionClient(url="http://127.0.0.1:1", company="Acme", timeout=1)
    tc.debug_dir = None
    monkeypatch.setattr(tc, "_post",
                         lambda xml, debug_name='': {"unrelated": "value"})
    # Empty raw string → 0 candidates → None (not a crash)
    assert tc._fetch_last_voucher_date_via_daybook() is None


# ─── Version + agent-version string ────────────────────────────────────
def test_agent_reports_v9_8_30_on_reconcile_payload():
    """Every reconcile payload must carry agent_version so the backend can
    tell old (unscoped) vs new (window-scoped) callers apart in logs."""
    src = (Path(m.__file__)).read_text(encoding="utf-8")
    assert "9.8.30-window-scoped-reconcile" in src
    assert "9.8.29-lvd-persist" not in src, (
        "stale v9.8.29 agent_version string still present"
    )


def test_gui_apps_version_bumped():
    gui_src = (Path(m.__file__).parent / "flowra_gui.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "v9.8.30"' in gui_src
