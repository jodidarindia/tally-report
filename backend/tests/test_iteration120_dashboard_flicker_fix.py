"""Iteration 120 — Dashboard top-panel flicker fix regression.

Root cause:
1) `StatCard` was defined INSIDE the `Dashboard` component body. Every parent
   render created a new component *type*, so React unmounted-and-remounted
   the four top stat cards on every state update (including 30-s auto-refresh
   fetches). This produced a visible flash where the panel briefly vanished.

2) `fetchData()` called `setLoading(true)` on EVERY refresh (initial + 30-s
   interval + manual button). Combined with `{!loading && <StatCards>}` guards
   in JSX, the entire top panel disappeared for the duration of every network
   round-trip during auto-refresh.

Fix in /app/frontend/src/pages/Dashboard.js:
  a. Hoisted `StatCard` above the Dashboard component so it has a stable
     identity across renders.
  b. Made `fetchData({ silent })` accept a silent flag; the 30-s auto-refresh
     interval and manual Refresh button now pass `{ silent: true }` so
     `loading` is not toggled and the JSX stays mounted.

This test is a static assertion against the source file so it runs in CI
without booting the frontend.
"""
from pathlib import Path
import re


DASH = Path("/app/frontend/src/pages/Dashboard.js")


def test_statcard_is_hoisted_outside_dashboard_component():
    src = DASH.read_text()
    # Locate positions of `const StatCard` and `const Dashboard`
    m_stat = re.search(r"^const StatCard\s*=", src, re.MULTILINE)
    m_dash = re.search(r"^const Dashboard\s*=", src, re.MULTILINE)
    assert m_stat, "StatCard component definition not found"
    assert m_dash, "Dashboard component definition not found"
    assert m_stat.start() < m_dash.start(), (
        "StatCard must be defined BEFORE (outside) the Dashboard component. "
        "Defining it inside causes unmount-remount on every render — this is "
        "the top-panel flicker regression from iteration 120."
    )


def test_fetchdata_supports_silent_mode():
    src = DASH.read_text()
    assert "silent = false" in src, (
        "fetchData must accept a { silent } flag to allow background auto-"
        "refresh without toggling `loading` (which vanishes the top panel)."
    )
    # setLoading(true) must be gated on !silent, not unconditional
    assert re.search(r"if\s*\(!silent\)\s*setLoading\(true\)", src), (
        "setLoading(true) must be gated behind `if (!silent)` so silent "
        "refreshes don't blank out the panel."
    )
    assert re.search(r"if\s*\(!silent\)\s*setLoading\(false\)", src), (
        "setLoading(false) must be similarly gated in the finally block."
    )


def test_autorefresh_and_manual_refresh_are_silent():
    src = DASH.read_text()
    # Auto-refresh 30-s interval should call fetchData with silent:true
    interval_block = re.search(
        r"setInterval\(\s*\(\)\s*=>\s*\{(.*?)\}\s*,\s*30000\)", src, re.DOTALL
    )
    assert interval_block, "30-s setInterval block not found"
    assert "silent: true" in interval_block.group(1), (
        "Auto-refresh interval must call fetchData({ silent: true })."
    )
    # Manual Refresh button also silent (keep old data visible mid-fetch)
    assert "fetchData({ silent: true })" in src, (
        "Manual Refresh button should also fetch silently."
    )


if __name__ == "__main__":
    test_statcard_is_hoisted_outside_dashboard_component()
    test_fetchdata_supports_silent_mode()
    test_autorefresh_and_manual_refresh_are_silent()
    print("PASS — Dashboard flicker fix locked in.")
