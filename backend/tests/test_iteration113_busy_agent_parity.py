"""Iteration 113 · Busy Agent v1.1 GUI ↔ Agent parity.

Ensures the public API surface of `FlowraBusySyncAgent` matches what
`flowra_busy_gui.BusyGUI` actually calls. If a future refactor renames
a method, this test breaks at the seam instead of the user's laptop.
"""
import inspect
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "desktop-agent" / "build-kit-busy"
sys.path.insert(0, str(AGENT_DIR))

import flowra_busy_agent as fba  # noqa: E402


def test_agent_accepts_status_callback():
    called = []

    def cb(msg):
        called.append(msg)

    a = fba.FlowraBusySyncAgent(status_callback=cb)
    a.set_status("hello")
    assert called == ["hello"]


def test_agent_exposes_gui_api():
    agent = fba.FlowraBusySyncAgent()
    for m in (
        "save_config",
        "logout",
        "detect_databases",
        "login",
        "set_busy_folder",
        "get_companies",
        "get_fys",
        "run_full_sync",
        "run_quick_sales_sync",
    ):
        assert hasattr(agent, m), f"agent missing method used by GUI: {m}"

    # `detected_companies` is exposed as a compatibility alias
    assert hasattr(agent, "detected_companies")


def test_login_supports_two_and_three_arg_signatures():
    agent = fba.FlowraBusySyncAgent()
    sig = inspect.signature(agent.login)
    # signature uses *args now, verify it accepts variable arity
    assert any(p.kind == inspect.Parameter.VAR_POSITIONAL
               for p in sig.parameters.values())


def test_run_full_sync_accepts_force_kwarg():
    sig = inspect.signature(fba.FlowraBusySyncAgent.run_full_sync)
    assert "force" in sig.parameters


def test_full_skip_window_days_present():
    assert fba.FULL_SKIP_WINDOW_DAYS == 7


def test_version_is_v11_parity():
    assert fba.VERSION == "1.3"
    assert fba.AGENT_TAG == "busy-1.3-pyodbc-bundled"
