"""Iteration 133 — v1.4.2 daemon-side driver pre-flight banner.

The user's log kept crashing at Phase 1 with a Python stack trace because
NEITHER the BSSData OLE DB provider nor the Microsoft Access ODBC driver
was installed on the target Windows PC. In v1.4.2 the daemon now probes
both drivers immediately after login and, if neither is present, refuses
to enter the sync loop while logging a big install-instructions banner.

Tests:
  1. `_check_busy_drivers_or_banner()` helper exists.
  2. Banner includes both install options (Access driver URL + Data
     Connectivity path).
  3. run_daemon() calls the helper AFTER login and returns 2 on failure.
  4. On non-Windows dev boxes the helper short-circuits to True (so the
     Linux mdb-export dev path still works).
"""
import sys
from pathlib import Path

AGENT = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py")


def test_helper_exists():
    src = AGENT.read_text()
    assert "def _check_busy_drivers_or_banner" in src, (
        "Pre-flight helper missing from agent module"
    )


def test_banner_lists_both_install_options():
    src = AGENT.read_text()
    # Access driver install URL
    assert "download/details.aspx?id=54920" in src, (
        "Banner must point users at Microsoft's Access Driver download page"
    )
    # BSSData / Data Connectivity option
    assert "Data Connectivity" in src, (
        "Banner must mention Busy's Data Connectivity add-on"
    )
    # Reference to the Test button so users know they can re-check
    assert "Test Busy Connection" in src, (
        "Banner should nudge users to the Test button for re-checking"
    )


def test_run_daemon_calls_preflight_and_bails_with_code_2():
    src = AGENT.read_text()
    # The helper must be called from run_daemon
    assert "_check_busy_drivers_or_banner(folder)" in src, (
        "run_daemon must call the pre-flight helper"
    )
    # Return code 2 signals "drivers missing" (0 = ok, 1 = env vars missing)
    assert "return 2" in src, (
        "run_daemon must return 2 when drivers are missing so callers can "
        "distinguish from other failure modes"
    )


def test_non_windows_short_circuits_to_true():
    src = AGENT.read_text()
    # Inspecting the function body: on non-Windows we return True to keep
    # the Linux mdb-export dev path working.
    idx = src.find("def _check_busy_drivers_or_banner")
    body = src[idx:idx + 3000]
    assert 'sys.platform != "win32"' in body
    # The return True must appear before any Windows-only probing
    ret_idx = body.find("return True")
    probe_idx = body.find("BSSData.6.0")
    assert 0 < ret_idx < probe_idx, (
        "Non-Windows short-circuit must precede the Windows COM probes"
    )


if __name__ == "__main__":
    for fn in [
        test_helper_exists,
        test_banner_lists_both_install_options,
        test_run_daemon_calls_preflight_and_bails_with_code_2,
        test_non_windows_short_circuits_to_true,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll v1.4.2 pre-flight tests passed.")
