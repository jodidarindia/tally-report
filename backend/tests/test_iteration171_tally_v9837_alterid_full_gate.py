"""Regression tests for v9.8.37 — AlterID-gated full sync.

These tests exercise the surgical change made in
`/app/desktop-agent/build-kit/tally_sync_agent_v9.py`:

  1. The 20-min full-sync cycle (now 60-min default) must honour the
     $$LastAlterId counter the same way the 5-min quick-sync already does.
     If `full_sync_done=True` AND `alter_id_full::<company>` matches
     Tally's current $$LastAlterId → the ENTIRE full sync is skipped.
  2. A first-ever full sync (no `full_sync_done`) must still run.
  3. A user-triggered Resync (which clears `full_sync_done`) must still
     run — and must also drop the `alter_id_full::` baseline so the gate
     cannot short-circuit the forced re-sync.
  4. If AlterID detection fails (returns None) the gate must fall through
     to a normal full sync — safer than skipping.
  5. After a successful full sync (no failed phases), the AlterID baseline
     must be saved. If any phase failed, baseline must NOT be saved —
     otherwise the next cycle would silently skip a recovery attempt.

These tests do NOT boot the full agent — they statically assert the
patched source contains the required logic and that the control-flow
constants are in place. This is deliberately a smoke-level regression
suite: the production integration test is pulling the compiled .exe
onto a Tally workstation.
"""
import os
import re
import pytest

AGENT_PATH = "/app/desktop-agent/build-kit/tally_sync_agent_v9.py"


@pytest.fixture(scope="module")
def agent_src() -> str:
    assert os.path.isfile(AGENT_PATH), f"missing: {AGENT_PATH}"
    with open(AGENT_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def test_version_bumped_to_9_8_37(agent_src):
    """Banner, print header and heartbeat payloads advertise v9.8.37."""
    assert "FLOWRA TALLY SYNC AGENT v9.8.37-alterid-gated-full-sync" in agent_src
    # No live heartbeat payloads should still tag with the previous release
    # string. Historical references inside comments are fine.
    assert "9.8.36-restore-v931-fetch-behaviour" not in agent_src
    # At least 5 call-sites tag their payloads with the new version.
    assert agent_src.count("9.8.37-alterid-gated-full-sync") >= 5


def test_full_sync_interval_default_is_60_minutes(agent_src):
    """SYNC_INTERVAL default raised 20 → 60. User can still override via env."""
    m = re.search(
        r"SYNC_INTERVAL\s*=\s*int\(os\.getenv\(\s*['\"]SYNC_INTERVAL_MINUTES['\"]\s*,\s*['\"](\d+)['\"]\s*\)\s*\)",
        agent_src,
    )
    assert m, "SYNC_INTERVAL getenv line not found"
    assert m.group(1) == "60", f"expected default 60, got {m.group(1)}"


def test_quick_sync_still_runs_every_5_minutes(agent_src):
    """Quick-sync frequency must stay 5 min — it's the fine-grained safety net."""
    m = re.search(
        r"SALES_SYNC_INTERVAL\s*=\s*int\(os\.getenv\(\s*['\"]SALES_SYNC_INTERVAL_MINUTES['\"]\s*,\s*['\"](\d+)['\"]\s*\)\s*\)",
        agent_src,
    )
    assert m and m.group(1) == "5"


def test_alterid_gate_is_present_in_single_company_full_sync(agent_src):
    """The gate must live inside _sync_single_company AFTER the preflight."""
    # The gate marker comment must appear.
    assert "v9.8.37 — AlterID gate for FULL SYNC" in agent_src
    # And must be inside _sync_single_company, after _preflight_or_skip.
    func_start = agent_src.index("def _sync_single_company(self, company_name)")
    preflight_pos = agent_src.index("_preflight_or_skip(company_name)", func_start)
    gate_pos = agent_src.index("v9.8.37 — AlterID gate for FULL SYNC", preflight_pos)
    assert gate_pos > preflight_pos, "gate placed before preflight — ordering wrong"


def test_gate_requires_full_sync_done_and_matching_alter_id(agent_src):
    """The gate's `if` must require BOTH baseline present AND equality."""
    gate_block = agent_src[
        agent_src.index("v9.8.37 — AlterID gate for FULL SYNC") :
        agent_src.index("# ───────────────────────────────────────────────────────────────────\n\n            # If company_name is placeholder")
    ]
    # All four guard conditions must appear in the `if`.
    assert "_full_done" in gate_block
    assert "_cur_alter_id is not None" in gate_block
    assert "_prev_alter_id is not None" in gate_block
    assert "str(_prev_alter_id) == str(_cur_alter_id)" in gate_block
    # And a safety log at the skip path.
    assert "$$LastAlterId unchanged" in gate_block
    assert "skipping entire Tally fetch cycle" in gate_block


def test_gate_falls_through_on_detection_failure(agent_src):
    """If AlterID detection raises OR the gate itself breaks, we must proceed
    with a normal full sync — never silently skip."""
    gate_block = agent_src[
        agent_src.index("v9.8.37 — AlterID gate for FULL SYNC") :
        agent_src.index("# ───────────────────────────────────────────────────────────────────\n\n            # If company_name is placeholder")
    ]
    assert "except Exception as _gate_err" in gate_block
    assert "proceeding with full sync" in gate_block


def test_baseline_saved_only_when_no_failed_phases(agent_src):
    """At the end of a successful full sync, the AlterID baseline must be
    persisted so the next cycle can short-circuit — but ONLY if the
    just-completed cycle had zero failed phases."""
    # Locate the end-of-full-sync block.
    end_block = agent_src[
        agent_src.index("Mark first full sync as done for this company") :
        agent_src.index("# Summary\n            total_sales = len(all_sales_combined)")
    ]
    assert "v9.8.37" in end_block
    assert "if not getattr(self, '_failed_phases', None)" in end_block
    assert "fetch_last_alter_id()" in end_block
    assert 'state[f"alter_id_full::{company_name}"]' in end_block
    assert "AlterID baseline saved" in end_block


def test_resync_command_drops_baseline(agent_src):
    """A manual Resync must clear `alter_id_full::<company>` from state so
    the gate cannot short-circuit the forced re-fetch."""
    # The resync branch should both reset full_sync_done AND delete the
    # alter_id_full baseline key.
    resync_block = agent_src[
        agent_src.index("[CMD] RESYNC company") :
        agent_src.index("[CMD] RESYNC company") + 1500
    ]
    assert "full_sync_done" in resync_block
    assert "alter_id_full::" in resync_block
    assert "del state[_alter_key]" in resync_block


def test_quick_sync_alterid_short_circuit_still_intact(agent_src):
    """The pre-existing v9.8.23 quick-sync AlterID gate must remain
    unchanged — this release only extends the pattern to the full sync."""
    assert "[QUICK]" in agent_src
    assert "$$LastAlterId unchanged" in agent_src
    assert "Nothing modified since last cycle — skipping Tally fetch." in agent_src


def test_no_adaptive_retry_doom_loop_reintroduced(agent_src):
    """Guardrail: v9.8.35's adaptive window-splitter on heavy voucher-type
    requests caused a 90-min doom loop on Krishna Sales Corp. v9.8.36
    reverted it. v9.8.37 must NOT re-introduce it anywhere in the hot
    voucher fetch path."""
    # fetch_sales_month must still call _post exactly once per voucher-type
    # per month and simply `continue` on timeout — no recursion into
    # smaller windows.
    sales_fn = agent_src[
        agent_src.index("def fetch_sales_month") :
        agent_src.index("def fetch_receipts_month")
    ]
    # No recursive window splitting.
    assert "_export_voucher_window" not in sales_fn
    assert "fetch_sales_month(" not in sales_fn[sales_fn.index(":") :]  # no self-recursion
    # On empty response we must simply continue, not retry.
    assert "continue" in sales_fn
