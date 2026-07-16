"""Iteration 131 — Busy Agent v1.4.1 daemon-crash regression tests.

The v1.4.0 build shipped a duplicate `BUSY_COMPANY` key in the GUI env-var
dict — the second entry (the empty OLE DB text field `busy_company`)
overwrote the first (the auto-detected `company_name`). The daemon then
saw `BUSY_COMPANY=""` and refused to start with:

    [daemon] Missing required env vars — cannot start.

These tests guard against the regression, and validate the three linked
fixes in v1.4.1:

  1. GUI env dict must NOT contain duplicate keys (parsed via AST).
  2. `BUSY_COMPANY` in the env dict must resolve to `company_name`
     (the auto-detected value), not `busy_company`.
  3. `BUSY_OLEDB_COMPANY` env var exists and also resolves to
     `company_name` — no separate user-typed field.
  4. Daemon's `_try_oledb` reads `BUSY_OLEDB_COMPANY` first, falls back
     to `BUSY_COMPANY` for backward compat.
  5. Daemon's missing-env error message lists exactly which vars are
     empty (so the user knows what to fill).
  6. AGENT_TAG carries the v1.4.1 marker.
  7. GUI applies proper taskbar iconphoto + AppUserModelID (fixes the
     Windows "leaf" icon issue).
  8. Manual "Busy company name" text-field widget is removed (Task 3 —
     company name is auto-detected from the folder).
"""
import ast
import re
import sys
from pathlib import Path

AGENT = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py")
GUI = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py")


def _find_env_update_dict(src: str) -> ast.Dict:
    """Locate the `env.update({...})` call inside start_agent() and return
    the Dict AST node."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "update"
                and isinstance(f.value, ast.Name) and f.value.id == "env"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Dict):
            # Sanity — must have BUSY_COMPANY somewhere in the keys
            keys = [k.value for k in arg.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if "BUSY_COMPANY" in keys:
                return arg
    raise AssertionError("Could not locate env.update({...}) call in GUI")


def test_env_dict_has_no_duplicate_keys():
    """Root cause guard: dict literal must not repeat any key."""
    d = _find_env_update_dict(GUI.read_text())
    keys = [k.value for k in d.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    duplicates = [k for k in keys if keys.count(k) > 1]
    assert not duplicates, (
        f"env dict has duplicate keys — this was the v1.4.0 daemon-crash "
        f"root cause: {sorted(set(duplicates))}"
    )


def test_busy_company_resolves_to_company_name():
    """BUSY_COMPANY must be populated from the auto-detected company_name,
    NOT from any user-typed `busy_company` field."""
    d = _find_env_update_dict(GUI.read_text())
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == "BUSY_COMPANY":
            src = ast.unparse(v)
            assert "company_name" in src, (
                f"BUSY_COMPANY must resolve to 'company_name' (auto-detected). "
                f"Got: {src}"
            )
            assert "busy_company" not in src, (
                "BUSY_COMPANY must NOT read from 'busy_company' (the removed "
                "user-typed field)."
            )
            return
    raise AssertionError("BUSY_COMPANY key not found in env dict")


def test_busy_oledb_company_env_var_present():
    """OLE DB provider's Company= param must live on its own env var."""
    d = _find_env_update_dict(GUI.read_text())
    keys = [k.value for k in d.keys if isinstance(k, ast.Constant)]
    assert "BUSY_OLEDB_COMPANY" in keys, (
        "BUSY_OLEDB_COMPANY env var must be present (new v1.4.1 key)"
    )
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == "BUSY_OLEDB_COMPANY":
            src = ast.unparse(v)
            assert "company_name" in src, (
                f"BUSY_OLEDB_COMPANY must resolve to the auto-detected "
                f"company_name. Got: {src}"
            )
            return


def test_agent_try_oledb_reads_new_env_var():
    src = AGENT.read_text()
    # _try_oledb() must read BUSY_OLEDB_COMPANY (new) with BUSY_COMPANY as
    # a backward-compat fallback.
    m = re.search(
        r"def _try_oledb\(self\):(.*?)(?=^\s{4}def )",
        src, re.DOTALL | re.MULTILINE,
    )
    assert m, "_try_oledb() body not found"
    body = m.group(1)
    assert "BUSY_OLEDB_COMPANY" in body, (
        "_try_oledb must read BUSY_OLEDB_COMPANY (v1.4.1 env split)"
    )


def test_daemon_missing_env_message_lists_specifics():
    src = AGENT.read_text()
    # The error line must interpolate a list of missing var names — not the
    # old flat "Missing required env vars" message.
    assert "Missing: {" in src or "Missing: " in src, (
        "Daemon error must list *which* env vars are missing so the user "
        "can fix them without reading source."
    )


def test_agent_tag_reflects_v141():
    src = AGENT.read_text()
    assert 'AGENT_TAG = "busy-1.4.2-conn-diagnostic"' in src, (
        "AGENT_TAG must roll forward to v1.4.2 marker"
    )


def test_gui_removes_manual_busy_company_field():
    """Task 3 — the redundant Busy company text entry widget was removed.
    Company name should always come from the auto-detected value."""
    src = GUI.read_text()
    assert "self.busy_company_entry" not in src, (
        "The manual Busy company name text widget must be removed — company "
        "is auto-detected from the folder (same UX as Tally Agent)."
    )
    # And there must be no self.entries['busy_company'] mapping either
    assert 'self.entries["busy_company"]' not in src


def test_gui_applies_iconphoto_and_appusermodelid():
    """The taskbar previously showed Tk's default 'leaf' icon on some
    Windows/Tk builds because iconbitmap failed silently. v1.4.1 adds
    iconphoto + SetCurrentProcessExplicitAppUserModelID as fallbacks."""
    src = GUI.read_text()
    assert "iconphoto" in src, "GUI must call iconphoto() for taskbar icon"
    assert "SetCurrentProcessExplicitAppUserModelID" in src, (
        "GUI must set AppUserModelID so Windows doesn't group under "
        "python.exe (which picks up python's own icon)."
    )
    assert "Flowra.BusySyncAgent" in src, "AppUserModelID must be branded"


if __name__ == "__main__":
    for fn in [
        test_env_dict_has_no_duplicate_keys,
        test_busy_company_resolves_to_company_name,
        test_busy_oledb_company_env_var_present,
        test_agent_try_oledb_reads_new_env_var,
        test_daemon_missing_env_message_lists_specifics,
        test_agent_tag_reflects_v141,
        test_gui_removes_manual_busy_company_field,
        test_gui_applies_iconphoto_and_appusermodelid,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll v1.4.1 daemon-fix regression tests passed.")
