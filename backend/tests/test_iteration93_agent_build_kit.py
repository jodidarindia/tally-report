"""Iteration 93 — Tally Agent Windows build-kit completeness.

Asserts that everything required to produce the Windows .exe is in place:
  - Build folder /app/desktop-agent/build-kit/ has all 8 expected files
  - Agent script and GUI launcher are valid Python
  - PyInstaller spec references real bundled files
  - Version metadata in agent matches version_info.txt
  - Build kit zip is publicly served from /app/frontend/public
  - Agent honors FLOWRA_EMAIL / FLOWRA_PASSWORD env vars (so the GUI's
    headless launch works without stdin prompts)
"""
import ast
import os
import re
import zipfile

KIT_DIR = "/app/desktop-agent/build-kit"
PUBLIC_ZIP = "/app/frontend/public/flowra-agent-buildkit.zip"
AGENT_SRC = "/app/desktop-agent/tally_sync_agent_v9.py"

REQUIRED_FILES = [
    "build.bat",
    "flowra_gui.py",
    "tally_sync_agent_v9.py",
    "agent.spec",
    "requirements.txt",
    "version_info.txt",
    "README.txt",
    ".gitignore",
]


def test_build_kit_has_all_files():
    for f in REQUIRED_FILES:
        path = os.path.join(KIT_DIR, f)
        assert os.path.exists(path), f"Missing build-kit file: {path}"
        assert os.path.getsize(path) > 0, f"Build-kit file is empty: {path}"


def test_python_sources_are_valid():
    for f in ("flowra_gui.py", "tally_sync_agent_v9.py", "agent.spec"):
        src = open(os.path.join(KIT_DIR, f)).read()
        ast.parse(src)  # raises SyntaxError on bad Python


def test_spec_references_real_files():
    spec = open(os.path.join(KIT_DIR, "agent.spec")).read()
    # Spec must declare the GUI as the entrypoint and bundle the agent
    assert "'flowra_gui.py'" in spec, "spec must use flowra_gui.py as entry"
    assert "'tally_sync_agent_v9.py'" in spec, "spec must bundle the agent script"
    # console=False → windowed app (no black console window)
    assert "console=False" in spec
    # Single-file output named FlowraTallyAgent
    assert "name='FlowraTallyAgent'" in spec


def test_build_bat_is_windows_friendly():
    bat = open(os.path.join(KIT_DIR, "build.bat")).read()
    # Must invoke pyinstaller with the spec
    assert "PyInstaller agent.spec" in bat
    # Must produce a versioned exe filename matching v9.8.9
    assert "FlowraTallyAgent_v9.8.9.exe" in bat
    # Must check for Python on PATH
    assert "python" in bat.lower()


def test_version_consistency():
    """version_info.txt and the GUI's APP_VERSION must agree on v9.8.9."""
    vi = open(os.path.join(KIT_DIR, "version_info.txt")).read()
    assert "9, 8, 9, 0" in vi
    assert "9.8.9.0" in vi
    gui = open(os.path.join(KIT_DIR, "flowra_gui.py")).read()
    assert 'APP_VERSION = "v9.8.9"' in gui
    agent = open(AGENT_SRC).read()
    assert "v9.8.9-daybook-lvd" in agent


def test_public_zip_served_and_complete():
    assert os.path.exists(PUBLIC_ZIP), "build-kit zip not published to /public"
    with zipfile.ZipFile(PUBLIC_ZIP) as z:
        names = z.namelist()
        for f in REQUIRED_FILES:
            assert f in names, f"zip is missing {f}"


def test_agent_supports_env_var_login():
    """The Windows GUI launches the agent headless with FLOWRA_EMAIL /
    FLOWRA_PASSWORD env vars. Verify the agent reads them instead of
    prompting via input()."""
    src = open(AGENT_SRC).read()
    # login_to_flowra() reads the env vars
    m = re.search(r"def login_to_flowra\(.*?return config", src, re.DOTALL)
    assert m, "login_to_flowra not found"
    block = m.group(0)
    assert "FLOWRA_EMAIL" in block, "login_to_flowra must read FLOWRA_EMAIL env"
    assert "FLOWRA_PASSWORD" in block, "login_to_flowra must read FLOWRA_PASSWORD env"


def test_kit_copy_matches_source():
    """The bundled agent inside the build kit must match the source of truth."""
    src = open(AGENT_SRC).read()
    kit = open(os.path.join(KIT_DIR, "tally_sync_agent_v9.py")).read()
    assert src == kit, (
        "build-kit/tally_sync_agent_v9.py is out of sync with the source. "
        "Run: cp /app/desktop-agent/tally_sync_agent_v9.py /app/desktop-agent/build-kit/"
    )


def test_gui_supports_system_tray():
    """Tray + Pillow icon helpers are present in the GUI."""
    src = open(os.path.join(KIT_DIR, "flowra_gui.py")).read()
    # Pillow-based tray icon generator
    assert "def build_tray_icon_image" in src
    # pystray + menu items
    assert "import pystray" in src
    assert "Show FLOWRA" in src
    assert "Quit FLOWRA" in src
    assert "Sync Now" in src
    # Closing the window hides to tray instead of exiting
    assert "def hide_to_tray" in src
    assert 'protocol("WM_DELETE_WINDOW", self.hide_to_tray)' in src


def test_gui_supports_windows_autostart():
    """Auto-start helpers + CLI flags are present."""
    src = open(os.path.join(KIT_DIR, "flowra_gui.py")).read()
    for sym in (
        "def register_startup",
        "def unregister_startup",
        "def is_startup_registered",
        "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        "FlowraTallyAgent",
    ):
        assert sym in src, f"missing autostart symbol: {sym!r}"
    # CLI flags exposed
    for flag in ("--register-startup", "--unregister-startup", "--minimized"):
        assert flag in src, f"missing CLI flag: {flag}"


def test_spec_bundles_tray_dependencies():
    """The .spec must declare hidden imports for pystray + Pillow + winreg
    so PyInstaller can find them in the frozen .exe."""
    spec = open(os.path.join(KIT_DIR, "agent.spec")).read()
    for hidden in (
        "'pystray'",
        "'PIL.Image'",
        "'PIL.ImageDraw'",
        "'winreg'",
    ):
        assert hidden in spec, f"spec missing hidden import: {hidden}"


def test_requirements_include_tray_libs():
    req = open(os.path.join(KIT_DIR, "requirements.txt")).read().lower()
    assert "pystray" in req
    assert "pillow" in req
