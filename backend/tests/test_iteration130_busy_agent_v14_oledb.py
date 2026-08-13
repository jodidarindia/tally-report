"""Iteration 130 — Busy Agent v1.4 OLE DB primary + ODBC fallback.

The actual OLE DB path requires Windows + a licensed Busy install with the
BSSData provider, so the CI-runnable checks here are structural:

  1. VERSION bumped to 1.4.0
  2. `_OLEDBConnectionAdapter` + `_OLEDBCursor` classes present + shaped
     like pyodbc (cursor().execute().fetchone() surface)
  3. `_try_oledb()` method exists on BusyDBReader and returns None on
     non-Windows (Linux dev boxes / preview env) — no crash
  4. `_get_connection()` new order: OLE DB attempted first, falls back
     to ODBC when None returned
  5. Env-var mapping — GUI writes BUSY_USER / BUSY_LOGIN_PASSWORD /
     BUSY_COMPANY into the agent process environment
  6. requirements.txt lists pywin32
  7. PyInstaller spec's hiddenimports include win32com.client
"""
import re
import sys
from pathlib import Path

AGENT = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py")
GUI = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py")
REQ = Path("/app/desktop-agent/build-kit-busy/requirements.txt")
SPEC = Path("/app/desktop-agent/build-kit-busy/agent.spec")


def test_version_bumped():
    src = AGENT.read_text()
    assert 'VERSION = "1.5.3"' in src, "VERSION must be bumped to 1.5.3"


def test_oledb_adapter_classes_present():
    src = AGENT.read_text()
    assert "class _OLEDBConnectionAdapter" in src
    assert "class _OLEDBCursor" in src
    # Verify the pyodbc-shaped surface exists on the cursor
    for method in ("def execute", "def fetchone", "def close"):
        assert method in src, f"_OLEDBCursor missing {method}"


def test_try_oledb_method_present_and_returns_none_on_non_windows():
    src = AGENT.read_text()
    assert "def _try_oledb(self)" in src
    # On non-Windows, the very first branch must return None
    m = re.search(
        r"def _try_oledb\(self\):.*?if not self\.is_windows:\s*\n\s*return None",
        src, re.DOTALL,
    )
    assert m, "Non-Windows path must short-circuit to None"


def test_get_connection_prefers_oledb_before_odbc():
    src = AGENT.read_text()
    m = re.search(
        r"def _get_connection\(self\):(.*?)^    def ",
        src, re.DOTALL | re.MULTILINE,
    )
    assert m, "_get_connection() body not found"
    body = m.group(1)
    oledb_idx = body.find("_try_oledb(")
    odbc_idx = body.find("import pyodbc")
    assert 0 <= oledb_idx < odbc_idx, (
        "_try_oledb() call must precede the pyodbc fallback"
    )
    # Must record which method connected
    assert '_connection_method = "OLE DB"' in body
    assert '_connection_method = "ODBC"' in body


def test_gui_captures_busy_login_credentials():
    src = GUI.read_text()
    # v1.4.1 — busy_company text field was REMOVED to fix the dict duplicate-
    # key crash. The OLE DB provider's Company= param now reuses the auto-
    # detected `company_name`.
    for key in ("busy_user", "busy_login_password"):
        assert key in src, f"GUI config missing {key}"
    # Env vars exported to the agent subprocess
    for env_var in ("BUSY_USER", "BUSY_LOGIN_PASSWORD", "BUSY_OLEDB_COMPANY"):
        assert env_var in src, f"GUI env-var export missing {env_var}"


def test_requirements_includes_pywin32():
    src = REQ.read_text()
    assert "pywin32" in src, "requirements.txt must list pywin32 for OLE DB path"
    # Must be Windows-gated so Linux dev builds don't try to install it
    assert 'sys_platform == "win32"' in src


def test_pyinstaller_spec_bundles_win32com():
    src = SPEC.read_text()
    for mod in ("win32com", "win32com.client", "pywintypes", "pythoncom"):
        assert mod in src, f"agent.spec hiddenimports missing {mod!r}"


def test_get_connection_windows_only_bail_still_works():
    """On the Linux dev machine (this test), the whole function must
    return None (no Windows → no ODBC/OLEDB attempt), not raise."""
    sys.path.insert(0, str(AGENT.parent))
    # Import must not crash even without pywin32 available
    import importlib
    mod = importlib.import_module("flowra_busy_agent")
    reader = mod.BusyDBReader("/tmp/nonexistent.bds")
    # is_windows is False on our container → should return None
    assert reader.is_windows is False
    assert reader._get_connection() is None


if __name__ == "__main__":
    for fn in [
        test_version_bumped,
        test_oledb_adapter_classes_present,
        test_try_oledb_method_present_and_returns_none_on_non_windows,
        test_get_connection_prefers_oledb_before_odbc,
        test_gui_captures_busy_login_credentials,
        test_requirements_includes_pywin32,
        test_pyinstaller_spec_bundles_win32com,
        test_get_connection_windows_only_bail_still_works,
    ]:
        try:
            fn()
            print(f"  ✅ {fn.__name__}")
        except Exception as e:
            print(f"  ❌ {fn.__name__}: {e}")
