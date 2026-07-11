"""Iteration 117 · Busy Agent v1.3 — pyodbc bundled in the .exe.

Regression for a customer-reported crash on 2026-07-11:

    ModuleNotFoundError: No module named 'pyodbc'

pyodbc is imported LAZILY inside `_get_connection()`, so PyInstaller's
static import scanner missed it in the v1.2 build. Customer's .exe ran
fine through login → data-folder detection → FY detection, then died the
moment Phase 1 (Customers) tried to open the .bds file.

Fix: declare pyodbc in BOTH:
  - build-kit-busy/requirements.txt  (installs into venv → PyInstaller sees it)
  - build-kit-busy/agent.spec        (hiddenimports — belt & braces)

Plus a friendlier error message when pyodbc OR the Access ODBC driver is
missing at runtime, so future customers get an actionable hint instead of
a Python traceback.
"""
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parents[2] / "desktop-agent" / "build-kit-busy"


def test_requirements_txt_lists_pyodbc():
    reqs = (BUILD_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "pyodbc" in reqs, (
        "requirements.txt must declare pyodbc — otherwise build.bat's venv "
        "doesn't have it and PyInstaller can't bundle it"
    )
    # Version pin is a soft requirement; check the line is real (not a comment).
    for line in reqs.splitlines():
        line = line.strip()
        if line.startswith("pyodbc"):
            assert ">=" in line or "==" in line, (
                f"pyodbc requirement line must pin a version: {line!r}"
            )
            return
    raise AssertionError("pyodbc line missing from requirements.txt")


def test_agent_spec_declares_pyodbc_in_hiddenimports():
    spec = (BUILD_DIR / "agent.spec").read_text(encoding="utf-8")
    assert "'pyodbc'" in spec, (
        "agent.spec must list 'pyodbc' in hiddenimports — pyodbc is imported "
        "lazily inside _get_connection() and PyInstaller's static scanner "
        "misses it without this hint"
    )


def test_agent_get_connection_wraps_pyodbc_import_with_friendly_error():
    """v1.3 — swallow the ImportError and raise a RuntimeError explaining how
    to rebuild + friendly hint about the ODBC driver."""
    src = (BUILD_DIR / "flowra_busy_agent.py").read_text(encoding="utf-8")
    # Find the _get_connection function body
    start = src.index("def _get_connection")
    body = src[start:start + 2000]
    assert "try:\n" in body and "import pyodbc" in body
    assert "except ImportError" in body
    assert "RuntimeError" in body
    assert "build.bat" in body, (
        "Friendly error should tell the customer to rebuild via build.bat"
    )
    assert "InterfaceError" in body, (
        "Should also catch pyodbc.InterfaceError (missing ODBC driver on PC) "
        "and point the customer at the download page"
    )
    assert "Microsoft Access Database Engine" in body


def test_version_bumped_to_v13_everywhere():
    agent_src = (BUILD_DIR / "flowra_busy_agent.py").read_text(encoding="utf-8")
    gui_src   = (BUILD_DIR / "flowra_busy_gui.py").read_text(encoding="utf-8")
    version_info = (BUILD_DIR / "version_info.txt").read_text(encoding="utf-8")

    assert 'VERSION = "1.3"' in agent_src
    assert 'AGENT_TAG = "busy-1.3-pyodbc-bundled"' in agent_src
    assert 'APP_VERSION = "v1.3"' in gui_src
    assert "(1, 3, 0, 0)" in version_info
    assert "u'1.3.0.0'" in version_info
    # Ensure no v1.2 leftovers
    for src, name in ((agent_src, "flowra_busy_agent.py"),
                       (gui_src, "flowra_busy_gui.py")):
        assert 'VERSION = "1.2"' not in src, (
            f"stale v1.2 constant still present in {name}"
        )
