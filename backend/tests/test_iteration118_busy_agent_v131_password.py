"""Iteration 118 · Busy Agent v1.3.1 — DB password fallback + env override.

Customer log (2026-07-11 07:50:55) after the v1.3 rebuild:

    pyodbc.ProgrammingError: (42000) [Microsoft][ODBC Microsoft Access Driver]
    Not a valid password. (-1905)

Busy encrypts every .bds with a proprietary password. The v1.3 build
attempted a passwordless connection so the Access ODBC driver rejected
it with error -1905.

v1.3.1 fix: try a fallback chain of the standard Busy passwords
(Busy 21 → 18 → older → blank), and honour a BUSY_DB_PASSWORD env var
override coming from the new GUI Settings field. Only ProgrammingError
with the -1905 code is retried — other pyodbc errors bubble up.
"""
import os
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parents[2] / "desktop-agent" / "build-kit-busy"
sys.path.insert(0, str(BUILD_DIR))


def test_known_passwords_list_declared():
    import flowra_busy_agent as a
    passwords = a.BusyDBReader._KNOWN_BUSY_PASSWORDS
    assert isinstance(passwords, tuple), "must be immutable"
    assert "bs21DBFile" in passwords, "Busy 21 default missing"
    assert "" in passwords, "empty-password fallback missing (some builds)"
    assert len(passwords) >= 3, "need at least 3 fallback candidates"


def test_env_override_wins_over_defaults(monkeypatch):
    import flowra_busy_agent as a

    captured = []

    class FakePyodbc:
        class ProgrammingError(Exception):
            pass

        class InterfaceError(Exception):
            pass

        class Error(Exception):
            pass

        @staticmethod
        def connect(conn_str):
            captured.append(conn_str)
            # Return an object with a .cursor()/close() interface
            class _C:
                def cursor(self): pass
                def close(self):  pass
            return _C()

    monkeypatch.setitem(sys.modules, "pyodbc", FakePyodbc)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setenv("BUSY_DB_PASSWORD", "MY-CUSTOM-PWD")

    r = a.BusyDBReader("/tmp/fake.bds")
    r._get_connection()
    # First conn_str must contain the env override, NOT the Busy defaults
    assert "PWD=MY-CUSTOM-PWD;" in captured[0], captured[0]
    assert "bs21DBFile" not in captured[0]


def test_fallback_chain_tries_each_password(monkeypatch):
    import flowra_busy_agent as a

    tried = []

    class FakePyodbc:
        class ProgrammingError(Exception):
            pass

        class InterfaceError(Exception):
            pass

        class Error(Exception):
            pass

        @staticmethod
        def connect(conn_str):
            tried.append(conn_str)
            # Simulate driver rejecting first 2 passwords, accepting 3rd.
            if len(tried) < 3:
                raise FakePyodbc.ProgrammingError(
                    "('42000', '[42000] [Microsoft][ODBC Microsoft Access "
                    "Driver] Not a valid password. (-1905) (SQLDriverConnect)')")
            class _C:
                def cursor(self): pass
                def close(self):  pass
            return _C()

    monkeypatch.setitem(sys.modules, "pyodbc", FakePyodbc)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.delenv("BUSY_DB_PASSWORD", raising=False)

    r = a.BusyDBReader("/tmp/fake.bds")
    r._get_connection()
    assert len(tried) == 3, f"should have tried 3 passwords, tried {len(tried)}"
    # First two attempts used the first two known passwords
    pwds_in_order = a.BusyDBReader._KNOWN_BUSY_PASSWORDS
    assert f"PWD={pwds_in_order[0]};" in tried[0]
    assert f"PWD={pwds_in_order[1]};" in tried[1]


def test_all_passwords_fail_raises_friendly_runtime_error(monkeypatch):
    import flowra_busy_agent as a

    class FakePyodbc:
        class ProgrammingError(Exception):
            pass

        class InterfaceError(Exception):
            pass

        class Error(Exception):
            pass

        @staticmethod
        def connect(conn_str):
            raise FakePyodbc.ProgrammingError("Not a valid password. (-1905)")

    monkeypatch.setitem(sys.modules, "pyodbc", FakePyodbc)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.delenv("BUSY_DB_PASSWORD", raising=False)

    r = a.BusyDBReader("/tmp/fake.bds")
    try:
        r._get_connection()
        assert False, "should have raised RuntimeError"
    except RuntimeError as e:
        msg = str(e)
        assert "BUSY_DB_PASSWORD" in msg, (
            "friendly error must mention the env var / Settings field"
        )
        assert "custom password" in msg.lower()


def test_gui_passes_busy_db_password_env_var():
    gui_src = (BUILD_DIR / "flowra_busy_gui.py").read_text(encoding="utf-8")
    assert '"BUSY_DB_PASSWORD"' in gui_src, (
        "GUI daemon spawn must propagate BUSY_DB_PASSWORD env var"
    )
    assert '"busy_db_password"' in gui_src, (
        "config key must be stored as busy_db_password"
    )


def test_gui_settings_tab_has_password_field():
    gui_src = (BUILD_DIR / "flowra_busy_gui.py").read_text(encoding="utf-8")
    assert 'Busy DB password' in gui_src, (
        "Settings tab must have a labelled 'Busy DB password' field"
    )
    assert 'busy_pwd_entry' in gui_src


def test_version_bumped_to_v131():
    agent_src = (BUILD_DIR / "flowra_busy_agent.py").read_text(encoding="utf-8")
    gui_src   = (BUILD_DIR / "flowra_busy_gui.py").read_text(encoding="utf-8")
    version_info = (BUILD_DIR / "version_info.txt").read_text(encoding="utf-8")
    assert 'VERSION = "1.3.1"' in agent_src
    assert 'APP_VERSION = "v1.3.1"' in gui_src
    assert "(1, 3, 1, 0)" in version_info
