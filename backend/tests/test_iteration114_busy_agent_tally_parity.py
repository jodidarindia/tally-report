"""Iteration 114 · Busy Agent v1.2 — Tally-parity GUI contract.

Locks in the visual + behavioural cloning of the Tally Sync Agent GUI
into the Busy Sync Agent GUI so a future refactor can't silently drift.
Every assertion below maps to a specific user-reported bug from the
Feb-2026 review of the v1.1 Busy Agent.
"""
import sys
import tempfile
import pathlib
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parents[2] / "desktop-agent" / "build-kit-busy"
sys.path.insert(0, str(BUILD_DIR))


# ── Static contract on build-kit contents ──────────────────────────────
def test_build_kit_ships_build_bat_agent_spec_and_versioninfo():
    """Bug #7 — no batch file existed. Build kit must ship one now."""
    for name in ("build.bat", "agent.spec", "version_info.txt",
                 "requirements.txt", "README.txt", "flowra_logo.png",
                 "flowra.ico"):
        assert (BUILD_DIR / name).exists(), f"build kit missing {name}"


def test_build_bat_produces_flowra_busy_agent_exe():
    txt = (BUILD_DIR / "build.bat").read_text(encoding="utf-8")
    assert "FlowraBusyAgent.exe" in txt
    assert "FlowraBusyAgent_" in txt  # versioned copy


def test_agent_spec_targets_gui_and_bundles_agent_module():
    spec = (BUILD_DIR / "agent.spec").read_text(encoding="utf-8")
    assert "'flowra_busy_gui.py'" in spec
    assert "'flowra_busy_agent.py', '.'" in spec
    assert "name='FlowraBusyAgent'" in spec


# ── Version + branding parity ──────────────────────────────────────────
def test_gui_version_is_v12():
    import flowra_busy_gui as g
    assert g.APP_VERSION == "v1.2"
    assert g.APP_NAME == "FLOWRA Busy Sync Agent"


def test_agent_version_is_v12():
    import flowra_busy_agent as a
    assert a.VERSION == "1.2"
    assert a.AGENT_TAG == "busy-1.2-tally-parity"


# ── Backend URL matches Tally agent's default ─────────────────────────
def test_backend_url_defaults_to_insights_flowralive_in():
    import flowra_busy_gui as g
    assert g.DEFAULT_BACKEND_URL == "https://insights.flowralive.in"


# ── Detection helpers (Bug #4, #5 — data folder → auto-detect) ────────
def test_check_busy_folder_recognises_bds_files(tmp_path):
    import flowra_busy_gui as g
    (tmp_path / "db.bds").write_bytes(b"")
    ok, msg = g.check_busy_folder(str(tmp_path))
    assert ok is True
    assert msg  # basename returned


def test_detect_busy_companies_finds_root_company(tmp_path):
    import flowra_busy_gui as g
    (tmp_path / "db.bds").write_bytes(b"")
    comps = g.detect_busy_companies(str(tmp_path))
    assert len(comps) == 1
    assert comps[0]["folder"] == str(tmp_path.resolve())


def test_detect_busy_companies_finds_subfolder_companies(tmp_path):
    import flowra_busy_gui as g
    for name in ("ACME", "BETA"):
        sub = tmp_path / name
        sub.mkdir()
        (sub / "db.bds").write_bytes(b"")
    comps = g.detect_busy_companies(str(tmp_path))
    names = sorted(c["name"] for c in comps)
    assert names == ["ACME", "BETA"]


def test_detect_busy_fys_scans_dbYEAR_bds(tmp_path):
    import flowra_busy_gui as g
    for y in (2023, 2024, 2025):
        (tmp_path / f"db{y}.bds").write_bytes(b"")
    fys = g.detect_busy_fys(str(tmp_path))
    assert fys == ["2023-24", "2024-25", "2025-26"]


# ── Daemon entry point exists for the GUI subprocess ──────────────────
def test_agent_run_daemon_is_defined():
    import flowra_busy_agent as a
    assert hasattr(a, "run_daemon") and callable(a.run_daemon)


# ── Windows registry hooks named for Busy (not tally) ─────────────────
def test_startup_registry_key_is_flowra_busy():
    import flowra_busy_gui as g
    assert g.RUN_VALUE == "FlowraBusyAgent"


# ── Single-instance guard uses distinct port from Tally ───────────────
def test_single_instance_port_differs_from_tally():
    import flowra_busy_gui as g
    assert g.SINGLE_INSTANCE_PORT == 38766  # Tally uses 38765


# ── Subscription helpers reachable ────────────────────────────────────
def test_fetch_subscription_info_signature():
    import inspect
    import flowra_busy_gui as g
    sig = inspect.signature(g.fetch_subscription_info)
    assert list(sig.parameters) == ["backend_url", "email", "password"]
