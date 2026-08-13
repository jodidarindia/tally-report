"""Iteration 132 — Busy Agent v1.4.2 connection-diagnostic tests.

Guards for the new one-click 'Test Busy Connection' button:
  1. `probe_busy_drivers` helper exists at module scope.
  2. On non-Windows it returns a well-formed stub without crashing.
  3. Result schema matches what the modal expects.
  4. GUI wires the 🧪 Test Busy Connection button + _test_busy_connection
     handler + _show_busy_test_results modal renderer.
  5. Modal offers a clickable install link for the Access driver
     (Microsoft's official 54920 page).
  6. Version markers bumped to v1.4.2.
"""
import sys
from pathlib import Path

GUI = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py")
AGENT = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py")


def test_probe_helper_exists():
    src = GUI.read_text()
    assert "def probe_busy_drivers(" in src, (
        "probe_busy_drivers() helper must be defined at module scope"
    )
    assert "def _pick_test_bds_file(" in src


def test_probe_returns_stub_on_linux():
    """On this Linux CI box the probe must NOT crash — it should return
    a schema-shaped dict with all three sections populated (as errors)."""
    import pytest
    pytest.importorskip("tkinter",
                         reason="Skips on headless CI without libtk.",
                         exc_type=ImportError)
    sys.path.insert(0, str(GUI.parent))
    import importlib
    if "flowra_busy_gui" in sys.modules:
        del sys.modules["flowra_busy_gui"]
    mod = importlib.import_module("flowra_busy_gui")
    r = mod.probe_busy_drivers(bds_path="/tmp/nonexistent.bds",
                                busy_user="u", busy_pwd="p",
                                oledb_company="ACME")
    assert isinstance(r, dict)
    for key in ("os_supported", "oledb", "odbc", "connection_test"):
        assert key in r, f"result missing top-level key: {key}"
    for section in ("oledb", "odbc"):
        assert "available" in r[section]
        assert "error" in r[section]
    assert r["os_supported"] is False
    assert r["oledb"]["available"] is False
    assert r["odbc"]["available"] is False


def test_probe_schema_via_ast():
    """Static guarantee that probe_busy_drivers returns the shape the modal
    expects — runs even on boxes without tkinter."""
    import ast
    src = GUI.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "probe_busy_drivers":
            body_src = ast.unparse(node)
            # Top-level keys expected by _show_busy_test_results
            for key in ("os_supported", "oledb", "odbc",
                        "connection_test", "bds_path"):
                assert (f'"{key}"' in body_src
                        or f"'{key}'" in body_src), (
                    f"probe_busy_drivers must populate '{key}' in its result "
                    "dict — the modal reads this."
                )
            # Section keys
            for section_key in ("available", "provider", "driver", "error",
                                 "success", "method", "password_used"):
                assert (f'"{section_key}"' in body_src
                        or f"'{section_key}'" in body_src), (
                    f"result section missing key: {section_key}"
                )
            return
    raise AssertionError("probe_busy_drivers() function not found")


def test_gui_has_test_button_and_handler():
    src = GUI.read_text()
    # Button widget in Settings → Section 2
    assert "self.test_conn_btn" in src, "Test button widget missing"
    assert "🧪  Test Busy Connection" in src, "Button label missing"
    # Handler + modal
    assert "def _test_busy_connection(self)" in src
    assert "def _show_busy_test_results(self" in src


def test_modal_links_to_microsoft_access_download():
    src = GUI.read_text()
    assert "download/details.aspx?id=54920" in src, (
        "Modal must offer a clickable install link for the Microsoft "
        "Access Database Engine driver (support page id=54920)."
    )
    assert "webbrowser.open" in src, (
        "Install link button must actually open the URL via the "
        "standard-library webbrowser module."
    )


def test_version_markers_v142():
    assert 'APP_VERSION = "v1.5.3"' in GUI.read_text()
    agent_src = AGENT.read_text()
    assert 'VERSION = "1.5.3"' in agent_src
    assert 'AGENT_TAG = "busy-1.5.3-vchtype-mapping-fix"' in agent_src


if __name__ == "__main__":
    for fn in [
        test_probe_helper_exists,
        test_probe_returns_stub_on_linux,
        test_probe_schema_via_ast,
        test_gui_has_test_button_and_handler,
        test_modal_links_to_microsoft_access_download,
        test_version_markers_v142,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll v1.4.2 connection-diagnostic tests passed.")
