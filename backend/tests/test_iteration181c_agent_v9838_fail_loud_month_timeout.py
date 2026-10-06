"""
iter-181c / agent v9.8.38 — fail-loud month-timeout tracking.

Static regression tests for the "Krishna Sales Corp" silent-drop bug:
when a per-month Tally Export timed out, prior agents returned 0 vouchers
AND persisted the AlterID baseline → next cycle short-circuited and the
missed months were never retried → dashboard showed 440 / 2000.

v9.8.38 adds:
  * `_tracked_month_fetch` wrapper that records per-month timeouts in
    `failed_months`.
  * Report-to-backend via `/agent/sync-progress` event `months_failed`.
  * Skip AlterID / LVD state persistence if `failed_months` is non-empty.
  * Backend-side: `receive_sync_progress` now promotes `months_failed`
    to dedicated fields on `sync_status`.
  * Default `EXPORT_TIMEOUT` raised 30 → 120 s.
"""
import os
import pytest


AGENT = open(
    os.path.join(os.path.dirname(__file__), "..", "..", "desktop-agent",
                 "build-kit", "tally_sync_agent_v9.py")
).read()
SYNC = open(os.path.join(os.path.dirname(__file__), "..", "routes", "sync.py")).read()


def test_version_bumped_to_9_8_38():
    assert "9.8.38-fail-loud-month-timeout" in AGENT
    assert "9.8.37-alterid-gated-full-sync" not in AGENT, \
        "stale v9.8.37 version strings must be removed"


def test_export_timeout_default_bumped_to_120():
    """Default was 0 (meaning 30s via REQUEST_TIMEOUT) → 120 to cover
    heavy monthly ledgers like Krishna's."""
    assert "EXPORT_TIMEOUT = int(os.getenv('EXPORT_TIMEOUT', '120'))" in AGENT


def test_tallyconnector_declares_timeout_tracker_flags():
    """`_in_month_fetch` + `_month_fetch_timed_out` must exist on
    TallyConnector so monthly fetchers can toggle them."""
    # Find __init__ body of TallyConnector.
    init_idx = AGENT.find("def __init__(self, url=TALLY_URL")
    assert init_idx > 0
    init_body = AGENT[init_idx:init_idx + 2500]
    assert "_in_month_fetch" in init_body
    assert "_month_fetch_timed_out" in init_body


def test_do_post_sets_month_fetch_timed_out_on_timeout():
    """Inside `_do_post`'s Timeout branch, when `_in_month_fetch` is
    True, the agent MUST set `_month_fetch_timed_out = True` so
    callers detect the drop. This is the whole point of Fix A."""
    # The exception block must include both flags.
    idx = AGENT.find("except requests.exceptions.Timeout:")
    assert idx > 0
    block = AGENT[idx:idx + 500]
    assert "self._in_month_fetch" in block
    assert "self._month_fetch_timed_out = True" in block


def test_quick_sync_tracks_failed_months_and_skips_state_save():
    """`run_sales_quick_sync` must initialise `failed_months`, add
    on timeout, report to backend, AND skip the AlterID/LVD state
    persistence when any month failed (the critical regression fix)."""
    start = AGENT.find("def run_sales_quick_sync")
    end = AGENT.find("def save_cache", start)
    assert start > 0 and end > start
    body = AGENT[start:end]
    assert "failed_months: set = set()" in body
    assert "if self.tally._month_fetch_timed_out:" in body
    assert "months_failed" in body, "must POST a 'months_failed' sync-progress event"
    # The state save must be guarded behind a `continue` (skip) when
    # failures exist.
    assert "skip the save_sync_state block below" in body or \
           "continue  # NB: skip" in body


def test_full_sync_uses_tracked_month_fetch_helper():
    """All seven voucher phases in `_sync_single_company` must call
    `_tracked_month_fetch` so timeouts don't silently vanish."""
    start = AGENT.find("def _sync_single_company")
    end = AGENT.find("def _preflight_or_skip", start)
    body = AGENT[start:end]
    # Every direct-call pattern should be gone — must use the wrapper.
    for raw_call in (
        "self.tally.fetch_sales_month(m_start, m_end)",
        "self.tally.fetch_receipts_month(m_start, m_end)",
        "self.tally.fetch_credit_notes_month(m_start, m_end)",
        "self.tally.fetch_journals_month(m_start, m_end)",
        "self.tally.fetch_stock_journals_month(m_start, m_end)",
        "self.tally.fetch_purchases_month(m_start, m_end)",
        "self.tally.fetch_debit_notes_month(m_start, m_end)",
    ):
        assert f"fy_sales.extend({raw_call})" not in body, \
            f"full-sync still has unwrapped {raw_call}"
    assert body.count("_tracked_month_fetch") >= 7, \
        "all seven phases must be routed via _tracked_month_fetch"


def test_full_sync_skips_full_sync_done_when_months_failed():
    """`full_sync_done = True` and AlterID baseline must NOT be
    persisted when `failed_months` is non-empty."""
    start = AGENT.find("def _sync_single_company")
    body = AGENT[start:start + 60000]
    assert "if sync_mode == 'full' and not failed_months:" in body
    # The old unconditional `if sync_mode == 'full':` has been removed.
    assert "if sync_mode == 'full' and failed_months:" in body, \
        "must have an explicit branch that WARNS when months failed"


def test_backend_promotes_months_failed_to_sync_status():
    """`receive_sync_progress` must surface the agent's `months_failed`
    event to dedicated top-level fields on `sync_status.agent_sync`."""
    body = SYNC[SYNC.find("async def receive_sync_progress"):SYNC.find("# v9.8.24 — agent posts a structured cycle summary")]
    assert '"months_failed_count"' in body or 'months_failed_count' in body
    assert 'months_failed' in body
    assert '"months_failed_hint"' in body or 'months_failed_hint' in body
    # Must also clear the badge on sync_complete.
    assert 'elif event_type == "sync_complete":' in body


def test_release_notes_exist():
    rn_path = os.path.join(os.path.dirname(__file__), "..", "..", "desktop-agent",
                           "build-kit", "RELEASE_NOTES_v9.8.38.md")
    assert os.path.isfile(rn_path), "RELEASE_NOTES_v9.8.38.md must ship with the agent"
    content = open(rn_path).read()
    assert "EXPORT_TIMEOUT=180" in content, "must document the workaround"
    assert "Fix A" in content and "Fix B" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
