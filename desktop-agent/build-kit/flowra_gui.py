"""FLOWRA Tally Sync Agent — Windows GUI Launcher (v9.8.9)

A lightweight Tkinter shell + system-tray icon around `tally_sync_agent_v9.py`.

Behaviour:
  • Single-instance app pinned to the Windows system tray.
  • Closing the window minimises to tray; the sync continues in the background.
  • Right-click the tray icon for: Show, Sync Now, Open Logs, Quit.
  • First launch asks once whether to auto-start with Windows. Toggle later
    from Settings or via `FlowraTallyAgent.exe --register-startup` /
    `--unregister-startup` flags.
  • Sync service starts automatically when the GUI opens (set-and-forget).

Why a subprocess instead of importing the agent in-process?
  The agent script has interactive `input()` prompts and a long-running
  asyncio + scheduler loop. Wrapping it as a subprocess keeps the GUI
  responsive and isolates crashes.

RAM footprint: ~25 MB idle (GUI + tray), ~80 MB peak during a full sync.
"""

import os
import sys
import json
import queue
import signal
import socket
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from pathlib import Path

APP_NAME = "FLOWRA Tally Sync Agent"
APP_VERSION = "v9.8.21"
AGENT_SCRIPT = "tally_sync_agent_v9.py"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Flowra"
APP_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = APP_DIR / "agent.env"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

PROD_URL = "https://insights.flowralive.in"
DEFAULT_BACKEND_URL = PROD_URL  # Pre-filled in Settings → Advanced.
                                # Users override only if self-hosting.
# A non-existent host the connectivity check uses to verify HTTPS internet.
INTERNET_PROBE_URL = "https://www.google.com/generate_204"

# Windows Registry key that auto-launches programs at user login.
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# ── Single-instance guard ──────────────────────────────────────────────
# Binds a TCP socket to a fixed local-only port. A second copy of the .exe
# will find the port in use and bail out (preventing duplicate writes to
# MongoDB + duplicate Tally fetches that customers were hitting in v9.8.18).
# 38765 was chosen to be deliberately above the IANA registered range and
# well away from the WebSocket port (8765) the agent already uses.
SINGLE_INSTANCE_PORT = 38765
_single_instance_socket = None  # module-level so the GC never closes it
RUN_VALUE = "FlowraTallyAgent"


# ── PyInstaller resource resolver ────────────────────────────────────────
def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ── Config persistence ──────────────────────────────────────────────────
def load_config() -> dict:
    if ENV_FILE.exists():
        try:
            return json.loads(ENV_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    ENV_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ── Windows auto-start (HKCU\…\Run) ─────────────────────────────────────
def _exe_path() -> str:
    """Path Windows should launch — the frozen .exe, or the script in dev."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}" --minimized'


def register_startup() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY,
                            0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, _exe_path())
        return True
    except Exception:
        return False


def unregister_startup() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY,
                            0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, RUN_VALUE)
        return True
    except FileNotFoundError:
        return True  # already absent → success
    except Exception:
        return False


def is_startup_registered() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_VALUE)
        return True
    except Exception:
        return False


# ── Start Menu shortcut (per-user, no admin required) ──────────────────
def _start_menu_dir() -> Path:
    """%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Flowra"""
    appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Flowra"


def _start_menu_shortcut_path() -> Path:
    return _start_menu_dir() / "FLOWRA Tally Sync Agent.lnk"


def _desktop_shortcut_path() -> Path:
    desk = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    return desk / "FLOWRA Tally Sync Agent.lnk"


def _create_lnk(target_lnk: Path, exe_path: str, icon_path: str = "") -> bool:
    """Create a .lnk shortcut using PowerShell's WScript.Shell COM.
    No extra Python deps required — PowerShell ships with every Windows."""
    if os.name != "nt":
        return False
    try:
        target_lnk.parent.mkdir(parents=True, exist_ok=True)
        # Strip surrounding quotes if any
        clean_exe = exe_path.strip('"')
        ps = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s  = $ws.CreateShortcut("{target_lnk}"); '
            f'$s.TargetPath = "{clean_exe}"; '
            f'$s.WorkingDirectory = "{os.path.dirname(clean_exe)}"; '
            f'$s.Description = "FLOWRA Tally Sync Agent"; '
        )
        if icon_path and os.path.exists(icon_path):
            ps += f'$s.IconLocation = "{icon_path},0"; '
        ps += '$s.Save();'
        result = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if os.name == "nt" else 0,  # CREATE_NO_WINDOW
        )
        return result.returncode == 0 and target_lnk.exists()
    except Exception:
        return False


def install_start_menu_shortcut() -> bool:
    """Install both Start Menu and Desktop shortcuts (per-user)."""
    if os.name != "nt":
        return False
    if not getattr(sys, "frozen", False):
        # Only meaningful when running as the built .exe
        return False
    exe = sys.executable
    icon = exe  # Use the embedded icon from the .exe itself
    ok1 = _create_lnk(_start_menu_shortcut_path(), exe, icon)
    ok2 = _create_lnk(_desktop_shortcut_path(),  exe, icon)
    return ok1 or ok2


def is_start_menu_shortcut_installed() -> bool:
    return _start_menu_shortcut_path().exists()


def remove_start_menu_shortcut() -> bool:
    ok = True
    for p in (_start_menu_shortcut_path(), _desktop_shortcut_path()):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            ok = False
    try:
        if _start_menu_dir().exists() and not any(_start_menu_dir().iterdir()):
            _start_menu_dir().rmdir()
    except Exception:
        pass
    return ok


# ── Tray icon (pystray + Pillow) ────────────────────────────────────────
def build_tray_icon_image():
    """Load the bundled FLOWRA logo for the tray icon. Falls back to a
    drawn blue-square 'F' if the logo file or PIL is unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    # Try the real logo first.
    for candidate in ("flowra_logo.png", "flowra.ico"):
        p = resource_path(candidate)
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA")
                # System tray expects a square ~64x64; resize cleanly.
                img.thumbnail((64, 64), Image.LANCZOS)
                return img
            except Exception:
                continue

    # Fallback: hand-drawn placeholder.
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(37, 99, 235, 255))
    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font = ImageFont.load_default()
    d.text((20, 7), "F", fill=(255, 255, 255, 255), font=font)
    return img


def load_header_logo():
    """Return a Tkinter PhotoImage for the in-app header logo, or None."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return None
    for candidate in ("flowra_logo.png", "flowra.ico"):
        p = resource_path(candidate)
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGBA")
                im.thumbnail((40, 40), Image.LANCZOS)
                return ImageTk.PhotoImage(im)
            except Exception:
                continue
    return None


# ── Connectivity probes ─────────────────────────────────────────────────
def check_tally(host: str, port: str | int) -> tuple[bool, str]:
    """TCP-ping the Tally ODBC port. Returns (ok, message)."""
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=2):
            return True, f"{host}:{port}"
    except Exception as e:
        return False, str(e)


def check_internet() -> tuple[bool, str]:
    """Quick HTTPS probe — connection only, doesn't matter what response."""
    try:
        import requests
        r = requests.get(INTERNET_PROBE_URL, timeout=3)
        return (r.status_code in (200, 204), f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


def check_backend(url: str) -> tuple[bool, str]:
    """Probe the FLOWRA backend's public health endpoint."""
    if not url:
        return False, "no URL configured"
    try:
        import requests
        r = requests.get(url.rstrip("/") + "/api/public/plans", timeout=4)
        return (r.status_code < 500, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


def fetch_tally_companies(host: str, port: str | int) -> list[str]:
    """Ask Tally for the list of OPEN companies (its native XML protocol).
    Returns an empty list if Tally is unreachable or no companies are loaded.
    """
    import requests
    xml = (
        '<ENVELOPE><HEADER><VERSION>1</VERSION>'
        '<TALLYREQUEST>Export</TALLYREQUEST>'
        '<TYPE>Collection</TYPE><ID>FlowraCompanyList</ID></HEADER>'
        '<BODY><DESC><STATICVARIABLES>'
        '<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>'
        '</STATICVARIABLES><TDL><TDLMESSAGE>'
        '<COLLECTION NAME="FlowraCompanyList" ISINITIALIZE="Yes">'
        '<TYPE>Company</TYPE>'
        '<FETCH>NAME, BASICCOMPANYFORMALNAME</FETCH>'
        '</COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>'
    )
    try:
        r = requests.post(f"http://{host}:{port}",
                          data=xml.encode("utf-8"),
                          headers={"Content-Type": "application/xml"},
                          timeout=5)
        if r.status_code != 200:
            return []
        import re as _re
        # Tally returns "<COMPANY NAME='...'>" or "<NAME>...</NAME>" — extract both.
        names = set()
        for m in _re.finditer(r'NAME="([^"]+)"', r.text):
            names.add(m.group(1).strip())
        for m in _re.finditer(r"<NAME[^>]*>([^<]+)</NAME>", r.text):
            names.add(m.group(1).strip())
        # Filter out junk Tally adds (default, blank).
        return sorted(n for n in names if n and n.lower() != "default")
    except Exception:
        return []


def fetch_tally_fys(host: str, port: str | int) -> list[str]:
    """Ask Tally for company BOOKSFROM date → generate FY list up to current.
    Falls back to last 5 FYs if Tally is unreachable or returns no date.

    Returns FY strings like '2024-25', '2025-26', '2026-27'.
    """
    import requests
    from datetime import date as _date, datetime as _dt
    xml = (
        '<ENVELOPE><HEADER><VERSION>1</VERSION>'
        '<TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE>'
        '<ID>FlowraFYList</ID></HEADER><BODY><DESC>'
        '<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>'
        '</STATICVARIABLES><TDL><TDLMESSAGE>'
        '<COLLECTION NAME="FlowraFYList" ISMODIFY="No">'
        '<TYPE>Company</TYPE><FETCH>NAME, BOOKSFROM, STARTINGFROM</FETCH>'
        '</COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>'
    )
    today = _date.today()
    current_start = today.year if today.month >= 4 else today.year - 1
    fy_start_year = None
    try:
        r = requests.post(f"http://{host}:{port}",
                          data=xml.encode("utf-8"),
                          headers={"Content-Type": "application/xml"},
                          timeout=5)
        if r.status_code == 200:
            import re as _re
            for tag in ("BOOKSFROM", "STARTINGFROM"):
                for m in _re.finditer(fr"<{tag}[^>]*>(\d{{8}})</{tag}>", r.text):
                    dt = _dt.strptime(m.group(1), "%Y%m%d")
                    yr = dt.year if dt.month >= 4 else dt.year - 1
                    if fy_start_year is None or yr < fy_start_year:
                        fy_start_year = yr
                if fy_start_year is not None:
                    break
    except Exception:
        pass

    if fy_start_year is None:
        # Fallback: last 5 FYs.
        fy_start_year = current_start - 4

    fys = []
    for y in range(fy_start_year, current_start + 1):
        fys.append(f"{y}-{str(y + 1)[-2:]}")
    return fys


def fetch_subscription_info(backend_url: str, email: str, password: str) -> dict | None:
    """Login to FLOWRA and return subscription details for the dashboard.
    Returns dict with: plan, subscription_days_left, subscription_expires,
    max_companies, max_employees, name — or None on failure."""
    import requests
    try:
        r = requests.post(
            f"{backend_url.rstrip('/')}/api/auth/login",
            json={"username": email, "password": password, "captcha_token": ""},
            timeout=8,
        )
        d = r.json()
        if not d.get("success"):
            return None
        data = d.get("data", {}) or {}
        return {
            "name": data.get("name", ""),
            "plan": (data.get("plan") or "free").lower(),
            "subscription_days_left": data.get("subscription_days_left"),
            "subscription_expires": data.get("subscription_expires", ""),
            "max_companies": data.get("max_companies", 1),
            "max_employees": data.get("max_employees", 1),
            "tenant_id": data.get("tenant_id", ""),
        }
    except Exception:
        return None


def current_fy_string() -> str:
    from datetime import date as _date
    today = _date.today()
    y = today.year if today.month >= 4 else today.year - 1
    return f"{y}-{str(y + 1)[-2:]}"


# ── Auto-update plumbing ────────────────────────────────────────────────
def _parse_ver(v: str) -> tuple:
    """'9.8.20-foo' → (9, 8, 20). Permissive."""
    if not v:
        return (0,)
    parts = []
    for seg in str(v).lstrip("v").split("."):
        num = ""
        for ch in seg:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts) or (0,)


def fetch_latest_release(backend_url: str) -> dict | None:
    """GET /api/agent/latest-version. Returns dict or None on failure.
    Never raises — failures are silent so the user is never blocked."""
    try:
        import requests
        r = requests.get(
            f"{backend_url.rstrip('/')}/api/agent/latest-version",
            timeout=5,
        )
        if r.status_code != 200:
            return None
        d = r.json()
        if not d.get("success"):
            return None
        return d.get("data") or None
    except Exception:
        return None


def download_to_temp(url: str, dest_path: str,
                      progress_cb=None) -> tuple[bool, str]:
    """Stream-download the new .exe to a temp path. Returns (ok, message)."""
    try:
        import requests
        with requests.get(url, stream=True, timeout=180) as r:
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
            total = int(r.headers.get("Content-Length", "0") or 0)
            done = 0
            with open(dest_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_cb and total > 0:
                        try:
                            progress_cb(done, total)
                        except Exception:
                            pass
            # Sanity: the .exe is ~26 MB. Refuse anything below 5 MB.
            try:
                sz = os.path.getsize(dest_path)
            except Exception:
                sz = 0
            if sz < 5 * 1024 * 1024:
                try:
                    os.unlink(dest_path)
                except Exception:
                    pass
                return False, f"Downloaded file too small ({sz} bytes)"
            return True, f"Downloaded {sz // (1024*1024)} MB"
    except Exception as e:
        return False, str(e)


def write_updater_batch(new_exe: str, target_exe: str,
                          pid: int, log_path: str) -> str:
    """Generate a Windows .bat that:
       1) Waits for the current PID to exit (up to 60s).
       2) Backs up the existing .exe → .bak (kept for one cycle).
       3) Moves the new .exe over the old one.
       4) Launches the new .exe.
       5) Deletes itself.

       Returns the path to the generated .bat file.
       NOTE: We never touch Tally, MongoDB, or anything outside the agent's
       own install location. The .bak file lets the user roll back if the
       new build fails to start."""
    bat_path = str(Path(os.environ.get("TEMP", str(APP_DIR))) /
                    "flowra_agent_updater.bat")
    new_exe_q = new_exe.replace("/", "\\")
    target_q = target_exe.replace("/", "\\")
    bak = target_q + ".bak"
    bat = f"""@echo off
setlocal
echo [FLOWRA updater] waiting for PID {pid} to exit... >> "{log_path}"
set /a tries=0
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if errorlevel 1 goto exited
set /a tries+=1
if %tries% GEQ 60 goto force
timeout /t 1 /nobreak >nul
goto wait
:force
echo [FLOWRA updater] PID {pid} still alive after 60s — proceeding anyway >> "{log_path}"
:exited
if exist "{bak}" del /Q "{bak}" >nul 2>&1
if exist "{target_q}" move /Y "{target_q}" "{bak}" >> "{log_path}" 2>&1
move /Y "{new_exe_q}" "{target_q}" >> "{log_path}" 2>&1
echo [FLOWRA updater] new binary installed at {target_q} >> "{log_path}"
start "" "{target_q}"
del /Q "%~f0"
endlocal
"""
    with open(bat_path, "w", encoding="ascii") as fh:
        fh.write(bat)
    return bat_path


# ── Main GUI ─────────────────────────────────────────────────────────────
class FlowraAgentGUI:
    def __init__(self, root: tk.Tk, start_minimized: bool = False):
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.config = load_config()
        # Seed defaults so the user never has to type the FLOWRA URL.
        if not self.config.get("backend_url"):
            self.config["backend_url"] = DEFAULT_BACKEND_URL
            save_config(self.config)
        self.tray = None
        self._log_path: Path | None = None

        self._build_ui()
        self._poll_log_queue()
        self._start_tray()

        # Override close → hide to tray, NOT exit.
        root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # First-run autostart prompt — asked once.
        if not self.config.get("startup_prompted"):
            self.config["startup_prompted"] = True
            save_config(self.config)
            if messagebox.askyesno(
                APP_NAME,
                "Start FLOWRA Tally Sync Agent automatically when Windows starts?\n\n"
                "Recommended for set-and-forget syncing. You can change this later "
                "in Settings.",
            ):
                if register_startup():
                    self._toast("Auto-start enabled.")

        # First-run Start Menu + Desktop shortcut install.
        # Only attempt when running as the frozen .exe so dev runs don't
        # install shortcuts pointing at python.exe.
        if getattr(sys, "frozen", False) and not self.config.get("shortcut_installed"):
            try:
                ok = install_start_menu_shortcut()
                if ok:
                    self.config["shortcut_installed"] = True
                    save_config(self.config)
                    self.log_queue.put("[setup] Start Menu + Desktop shortcut installed.")
            except Exception as e:
                self.log_queue.put(f"[setup] shortcut install failed: {e}")

        # NOTE: We no longer auto-start the sync service on launch.
        # The user must explicitly click "▶ Start Sync Service" or
        # "💾 Save & Start Sync" so they can review settings first.

        # If creds were stored previously, treat the user as already
        # "logged in" so the UI reflects it and detect buttons unlock.
        if self.config.get("email") and self.config.get("password"):
            try:
                self._set_logged_in(True, self.config["email"])
                if self.config.get("company_name"):
                    self.detect_fy_btn.configure(state="normal")
            except Exception:
                pass
        else:
            try:
                self._set_logged_in(False)
            except Exception:
                pass

        if start_minimized:
            self.root.after(50, self.hide_to_tray)

        # Kick off the first auto-update check 3 s after launch so the UI
        # is fully painted, then poll every 24 h. The check itself is HTTP
        # GET — no DB writes, never touches Tally.
        self.root.after(3000, self._check_for_update_async)
        self._schedule_update_check()

    # ---- UI construction --------------------------------------------------
    def _build_ui(self):
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        # Bigger default + minimum size so the FY section + subscription
        # card are never hidden below the fold on common laptop screens.
        self.root.geometry("1100x820")
        self.root.minsize(960, 720)
        try:
            self.root.iconbitmap(resource_path("flowra.ico"))
        except Exception:
            pass

        # Header strip with real FLOWRA logo
        header = tk.Frame(self.root, bg="#0F172A", height=72)
        header.pack(fill="x")
        self._header_logo = load_header_logo()  # keep ref so Tk doesn't GC it
        if self._header_logo is not None:
            tk.Label(header, image=self._header_logo,
                     bg="#0F172A").pack(side="left", padx=(20, 12), pady=14)
        tk.Label(header, text="FLOWRA",
                 font=("Segoe UI", 20, "bold"), fg="#FFFFFF",
                 bg="#0F172A").pack(side="left", pady=14)
        tk.Label(header, text=f"Tally Sync Agent  ·  {APP_VERSION}",
                 font=("Segoe UI", 10), fg="#94A3B8",
                 bg="#0F172A").pack(side="left", padx=10, pady=14)

        # Right side of header: logged-in email + logout button.
        right = tk.Frame(header, bg="#0F172A")
        right.pack(side="right", padx=16, pady=14)
        self.header_logout_btn = tk.Button(
            right, text="🚪  Logout",
            command=self._logout,
            bg="#1E293B", fg="white", relief="flat",
            activebackground="#334155", activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            padx=14, pady=6, cursor="hand2",
            borderwidth=0,
        )
        self.header_logout_btn.pack(side="right", padx=(10, 0))
        self.header_user_var = tk.StringVar(
            value=self.config.get("email") or "(not logged in)")
        tk.Label(right, textvariable=self.header_user_var,
                 fg="#CBD5E1", bg="#0F172A",
                 font=("Segoe UI", 9)).pack(side="right")
        self.status_var = tk.StringVar(value="● Stopped")
        tk.Label(header, textvariable=self.status_var,
                 font=("Segoe UI", 10, "bold"), fg="#F87171",
                 bg="#0F172A").pack(side="right", padx=20, pady=14)

        # IMPORTANT — pack the bottom action bar BEFORE the notebook so Tk
        # reserves vertical space for it. If we packed it after a Notebook
        # with `expand=True`, Tk pushes the bar off-screen on smaller
        # displays (which is what hid the Start/Stop buttons earlier).
        bar = tk.Frame(self.root, bg="#F1F5F9", height=56)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)  # honour the 56-px height
        self.btn_start = tk.Button(bar, text="▶  Start Sync Service",
                                   command=self.start_agent,
                                   bg="#2563EB", fg="white", relief="flat",
                                   font=("Segoe UI", 11, "bold"),
                                   padx=18, pady=10, cursor="hand2")
        self.btn_start.pack(side="left", padx=12, pady=8)
        self.btn_stop = tk.Button(bar, text="■  Stop",
                                  command=self.stop_agent, state="disabled",
                                  bg="#E2E8F0", fg="#0F172A", relief="flat",
                                  font=("Segoe UI", 11, "bold"),
                                  padx=18, pady=10, cursor="hand2")
        self.btn_stop.pack(side="left", padx=4, pady=8)
        tk.Button(bar, text="📁 Open Logs Folder",
                  command=lambda: os.startfile(str(LOG_DIR))
                  if os.name == "nt" else None,
                  bg="#F1F5F9", fg="#475569", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2").pack(side="right", padx=12)
        tk.Button(bar, text="✕ Hide to Tray",
                  command=self.hide_to_tray,
                  bg="#F1F5F9", fg="#475569", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2").pack(side="right")

        # ── Update button (hidden until a newer release is detected) ──
        # Sits between Start/Stop and the right-side utility buttons.
        # Flashes amber → red while it's visible so it grabs attention.
        self._update_info: dict | None = None
        self.update_btn = tk.Button(
            bar, text="⬆  Update Available",
            command=self._do_update,
            bg="#F59E0B", fg="white", relief="flat",
            activebackground="#D97706", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=14, pady=8, cursor="hand2", borderwidth=0,
        )
        # Don't pack yet — _show_update_button() will do it when needed.
        self._update_flash_state = False

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=10)
        self._build_status_tab(nb)
        self._build_settings_tab(nb)
        self._build_logs_tab(nb)
        self._build_about_tab(nb)

    def _build_status_tab(self, nb: ttk.Notebook):
        # Wrap the Status tab in a scrollable canvas too, so the
        # Subscription card at the bottom is always reachable.
        scroll_holder = ttk.Frame(nb)
        nb.add(scroll_holder, text="  Status  ")
        canvas = tk.Canvas(scroll_holder, borderwidth=0, highlightthickness=0,
                           background="#FFFFFF")
        scroll = ttk.Scrollbar(scroll_holder, orient="vertical",
                                command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        f = ttk.Frame(canvas, padding=20)
        cwin = canvas.create_window((0, 0), window=f, anchor="nw")

        def _cfg(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(cwin, width=canvas.winfo_width())
        f.bind("<Configure>", _cfg)
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(cwin, width=e.width))

        # Live indicator cards
        cards = tk.Frame(f, bg="#FFFFFF")
        cards.pack(fill="x", pady=(0, 16))
        self._indicators: dict[str, tuple[tk.Label, tk.StringVar]] = {}
        layout = [
            ("internet",     "Internet",          "Checking…"),
            ("tally",        "Tally Connection",  "Checking…"),
            ("backend",      "FLOWRA Cloud",      "Checking…"),
            ("service",      "Sync Service",      "Stopped"),
        ]
        for i, (key, label, default) in enumerate(layout):
            card = tk.Frame(cards, bg="#F8FAFC", relief="solid", bd=1, padx=14, pady=12)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=label, fg="#64748B",
                     bg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w")
            row = tk.Frame(card, bg="#F8FAFC"); row.pack(anchor="w", pady=(4, 0))
            dot = tk.Label(row, text="●", fg="#94A3B8",
                           bg="#F8FAFC", font=("Segoe UI", 14, "bold"))
            dot.pack(side="left")
            v = tk.StringVar(value=default)
            tk.Label(row, textvariable=v, fg="#0F172A",
                     bg="#F8FAFC", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(6, 0))
            self._indicators[key] = (dot, v)

        # Convenience aliases for existing log-driven setters
        self.service_var = self._indicators["service"][1]
        self.tally_var = self._indicators["tally"][1]
        self.backend_var = self._indicators["backend"][1]

        # ── Active sync card ────────────────────────────────────────────
        sync_card = tk.Frame(f, bg="#EFF6FF", relief="solid", bd=1, padx=16, pady=14)
        sync_card.pack(fill="x", pady=(0, 14))
        tk.Label(sync_card, text="Sync Status", fg="#1E3A8A",
                 bg="#EFF6FF", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        # Row 1: active company name
        row_co = tk.Frame(sync_card, bg="#EFF6FF"); row_co.pack(anchor="w", pady=(6, 2))
        tk.Label(row_co, text="Active company: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        self.active_company_var = tk.StringVar(value="—  (not syncing)")
        tk.Label(row_co, textvariable=self.active_company_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 10, "bold")).pack(side="left")

        # Row 2: current phase
        row_ph = tk.Frame(sync_card, bg="#EFF6FF"); row_ph.pack(anchor="w", pady=(2, 6))
        tk.Label(row_ph, text="Current phase: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        self.phase_var = tk.StringVar(value="Idle")
        tk.Label(row_ph, textvariable=self.phase_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 10)).pack(side="left")

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(sync_card, mode="determinate",
                                            maximum=100, length=600,
                                            variable=self.progress_var)
        self.progress_bar.pack(fill="x", pady=(6, 2))
        self.progress_pct_var = tk.StringVar(value="0%  ·  waiting")
        tk.Label(sync_card, textvariable=self.progress_pct_var,
                 fg="#1E3A8A", bg="#EFF6FF",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")

        # Last sync line
        self.lastsync_var = tk.StringVar(value="Never")
        last_row = tk.Frame(sync_card, bg="#EFF6FF"); last_row.pack(anchor="w", pady=(8, 0))
        tk.Label(last_row, text="Last successful sync: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(last_row, textvariable=self.lastsync_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 10, "bold")).pack(side="left")

        # Sync interval row
        intv_row = tk.Frame(sync_card, bg="#EFF6FF"); intv_row.pack(anchor="w", pady=(4, 0))
        tk.Label(intv_row, text="Sync interval: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        self.sync_interval_var = tk.StringVar(
            value=f"every {self.config.get('sync_interval_minutes', '20')} min (full)  "
                  f"·  every 5 min (sales)")
        tk.Label(intv_row, textvariable=self.sync_interval_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")

        # ── Subscription card ───────────────────────────────────────────
        sub_card = tk.Frame(f, bg="#FEFCE8", relief="solid", bd=1, padx=16, pady=14)
        sub_card.pack(fill="x", pady=(0, 12))
        head_row = tk.Frame(sub_card, bg="#FEFCE8"); head_row.pack(fill="x")
        tk.Label(head_row, text="Subscription", fg="#854D0E",
                 bg="#FEFCE8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.renew_button = tk.Button(
            head_row, text="📨  Request Renewal",
            command=self._request_renewal,
            bg="#854D0E", fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=12, pady=4, cursor="hand2",
        )
        self.renew_button.pack(side="right")
        tk.Button(
            head_row, text="🔄 Refresh",
            command=self._refresh_subscription_async,
            bg="#FEFCE8", fg="#854D0E", relief="flat",
            activebackground="#FDE68A",
            font=("Segoe UI", 9, "bold"),
            padx=10, pady=4, cursor="hand2", borderwidth=0,
        ).pack(side="right", padx=(0, 8))

        sub_grid = tk.Frame(sub_card, bg="#FEFCE8")
        sub_grid.pack(fill="x", pady=(8, 0))

        def _sub_field(parent, col, label):
            cell = tk.Frame(parent, bg="#FEFCE8")
            cell.grid(row=0, column=col, padx=(0, 28), sticky="nw")
            tk.Label(cell, text=label, fg="#854D0E", bg="#FEFCE8",
                     font=("Segoe UI", 9)).pack(anchor="w")
            v = tk.StringVar(value="—")
            tk.Label(cell, textvariable=v, fg="#0F172A", bg="#FEFCE8",
                     font=("Segoe UI", 12, "bold"),
                     wraplength=200, justify="left").pack(anchor="w", pady=(2, 0))
            return v

        self.plan_var       = _sub_field(sub_grid, 0, "Plan")
        self.account_var    = _sub_field(sub_grid, 1, "Account")
        self.expires_var    = _sub_field(sub_grid, 2, "Expires on")
        self.days_left_var  = _sub_field(sub_grid, 3, "Days remaining")

        # Banner row (shown only when warning / expired)
        self.sub_banner_var = tk.StringVar(value="")
        self.sub_banner = tk.Label(
            sub_card, textvariable=self.sub_banner_var,
            fg="#7F1D1D", bg="#FEE2E2",
            font=("Segoe UI", 9, "bold"), padx=10, pady=6,
            anchor="w", justify="left", wraplength=860,
        )  # packed only when needed

        # (Logout button now lives in the header strip — top right.)

        # Action row
        actions = tk.Frame(f); actions.pack(fill="x", pady=10)
        tk.Button(actions, text="🔄  Re-check Now", command=self._refresh_indicators_now,
                  bg="#10B981", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"),
                  padx=16, pady=8, cursor="hand2").pack(side="left")
        tk.Button(actions, text="🧪  Test Tally Connection", command=self.test_connection,
                  bg="#F1F5F9", fg="#0F172A", relief="flat",
                  font=("Segoe UI", 10),
                  padx=16, pady=8, cursor="hand2").pack(side="left", padx=8)

        tk.Label(f, justify="left", fg="#64748B", bg="#FFFFFF",
                 font=("Segoe UI", 9), wraplength=820,
                 text=("Green = connected · Red = offline / unreachable · "
                       "Grey = checking.\nThis window can be closed safely — "
                       "the sync service keeps running in the system tray.")).pack(anchor="w",
                                                                                    pady=(20, 0))

        # Kick off the first probe and a 15-second background refresh.
        self.root.after(300, self._refresh_indicators_now)
        self._schedule_indicator_refresh()
        # Pull subscription info now and again every 5 minutes.
        self.root.after(500, self._refresh_subscription_async)
        self._schedule_subscription_refresh()

    def _schedule_subscription_refresh(self):
        self.root.after(5 * 60 * 1000, self._tick_subscription)

    def _tick_subscription(self):
        self._refresh_subscription_async()
        self._schedule_subscription_refresh()

    def _build_settings_tab(self, nb: ttk.Notebook):
        # Wrap the entire Settings tab in a scrollable canvas so every
        # section (incl. Section 3 — Starting FY) is always reachable,
        # even on shorter laptop screens or when the user resizes the
        # window narrow.
        scroll_holder = ttk.Frame(nb)
        nb.add(scroll_holder, text="  Settings  ")
        canvas = tk.Canvas(scroll_holder, borderwidth=0, highlightthickness=0,
                           background="#FFFFFF")
        scroll = ttk.Scrollbar(scroll_holder, orient="vertical",
                                command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        outer = ttk.Frame(canvas, padding=(20, 18))
        canvas_window = canvas.create_window((0, 0), window=outer, anchor="nw")

        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make inner frame at least as wide as the canvas
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        outer.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Mouse-wheel scrolling — Windows + Linux + macOS
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(-1 * int(event.delta / 120), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Force the native "vista" / "xpnative" theme on Windows so buttons
        # and entries look like standard Windows controls.
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass

        # ── Section 1: Login ────────────────────────────────────────────
        sec1 = ttk.LabelFrame(outer, text="  1. FLOWRA Login  ", padding=14)
        sec1.pack(fill="x", pady=(0, 12))
        self.entries: dict[str, ttk.Entry] = {}

        def add_entry(parent, row, label, key, default="", secret=False, width=46):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w",
                                                padx=(0, 12), pady=6)
            e = ttk.Entry(parent, width=width, show="•" if secret else "")
            stored = self.config.get(key)
            e.insert(0, stored if stored else ("" if secret else default))
            e.grid(row=row, column=1, sticky="w", pady=6)
            self.entries[key] = e

        add_entry(sec1, 0, "Login Email",  "email",    "you@company.com")
        add_entry(sec1, 1, "Password",     "password", "", secret=True)

        # Login action row — a BIG blue button + live status label.
        login_row = tk.Frame(sec1)
        login_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.login_btn = tk.Button(
            login_row, text="🔐  Login to FLOWRA",
            command=self._do_login,
            bg="#2563EB", fg="white", relief="flat",
            activebackground="#1D4ED8", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=18, pady=8, cursor="hand2", borderwidth=0,
        )
        self.login_btn.pack(side="left")
        self.login_status_var = tk.StringVar(value="Not logged in")
        self.login_status_label = tk.Label(
            login_row, textvariable=self.login_status_var,
            fg="#94A3B8", font=("Segoe UI", 10, "bold"))
        self.login_status_label.pack(side="left", padx=14)

        # ── Section 2: Tally Connection ────────────────────────────────
        sec2 = ttk.LabelFrame(outer, text="  2. Tally Connection  ", padding=14)
        sec2.pack(fill="x", pady=(0, 12))
        add_entry(sec2, 0, "Tally Host",  "tally_host", "localhost", width=20)
        add_entry(sec2, 1, "Tally Port",  "tally_port", "9000",       width=20)

        # Tally Company
        ttk.Label(sec2, text="Tally Company").grid(row=2, column=0, sticky="w",
                                                     padx=(0, 12), pady=(10, 6))
        self.company_var = tk.StringVar(value=self.config.get("company_name", ""))
        self.company_combo = ttk.Combobox(sec2, textvariable=self.company_var,
                                          width=44, state="readonly")
        self.company_combo.grid(row=2, column=1, sticky="w", pady=(10, 6))
        # BLUE prominent button (was ttk default — easy to miss).
        self.detect_company_btn = tk.Button(
            sec2, text="🔍  Detect Company from Tally",
            command=self._detect_companies,
            bg="#2563EB", fg="white", relief="flat",
            activebackground="#1D4ED8", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=12, pady=6, cursor="hand2", borderwidth=0,
            state="disabled",  # enabled after login
        )
        self.detect_company_btn.grid(row=2, column=2, padx=(8, 0), pady=(10, 6))
        cached = self.config.get("available_companies") or []
        if cached:
            self.company_combo["values"] = cached
        self.company_combo.bind("<<ComboboxSelected>>",
                                 lambda _e: self._on_company_chosen())
        ttk.Label(sec2,
                  text=("Only ONE company can be synced at a time. If Tally has "
                        "multiple companies open, pick which one this PC should "
                        "send to FLOWRA — others stay untouched."),
                  foreground="#94A3B8", wraplength=720).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # ── Section 3: Starting Financial Year (clickable chips) ───────
        sec3 = ttk.LabelFrame(outer, text="  3. Starting Financial Year  ",
                              padding=14)
        sec3.pack(fill="x", pady=(0, 12))
        ttk.Label(
            sec3,
            text=("Click an FY below to choose where to START syncing from. "
                  "All data from that FY up to the current FY will be uploaded."),
            wraplength=720, foreground="#475569",
        ).pack(anchor="w", pady=(0, 8))

        self.fy_chip_frame = ttk.Frame(sec3)
        self.fy_chip_frame.pack(anchor="w", pady=(2, 4))
        self.fy_var = tk.StringVar(value=self.config.get("starting_fy", ""))
        self.fy_status_var = tk.StringVar(
            value=(f"Starting FY:  {self.fy_var.get()}" if self.fy_var.get()
                   else "No FY selected yet."))
        cached_fys = self.config.get("available_fys") or []
        self._render_fy_chips(cached_fys or [])

        action_row = tk.Frame(sec3)
        action_row.pack(anchor="w", pady=(8, 0))
        self.detect_fy_btn = tk.Button(
            action_row, text="🔄  Detect FYs from Tally",
            command=self._detect_fys,
            bg="#2563EB", fg="white", relief="flat",
            activebackground="#1D4ED8", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=14, pady=6, cursor="hand2", borderwidth=0,
            state="disabled",  # enabled after a company is chosen
        )
        self.detect_fy_btn.pack(side="left")
        tk.Label(action_row, textvariable=self.fy_status_var,
                 fg="#0F172A", font=("Segoe UI", 10)).pack(side="left", padx=14)

        # ── Section 4: Advanced + integrations ──────────────────────────
        sec4 = ttk.LabelFrame(outer, text="  4. Advanced  ", padding=14)
        sec4.pack(fill="x", pady=(0, 12))
        add_entry(sec4, 0, "Sync Interval (minutes)", "sync_interval_minutes",
                  "20", width=12)
        ttk.Label(sec4, text="FLOWRA Server URL").grid(row=1, column=0,
                                                         sticky="w",
                                                         padx=(0, 12), pady=6)
        url_entry = ttk.Entry(sec4, width=56)
        url_entry.insert(0, self.config.get("backend_url", DEFAULT_BACKEND_URL))
        url_entry.grid(row=1, column=1, sticky="w", pady=6)
        self.entries["backend_url"] = url_entry
        ttk.Label(sec4,
                  text=("Pre-filled. Only change if you self-host FLOWRA."),
                  foreground="#94A3B8").grid(row=2, column=1,
                                              sticky="w", pady=(0, 4))

        # Auto-start + shortcut checkboxes
        self.startup_var = tk.BooleanVar(value=is_startup_registered())
        ttk.Checkbutton(sec4, text="Start FLOWRA automatically when Windows starts",
                        variable=self.startup_var, command=self._toggle_startup
                        ).grid(row=3, column=0, columnspan=3, sticky="w",
                               pady=(12, 0))
        self.shortcut_var = tk.BooleanVar(value=is_start_menu_shortcut_installed())
        ttk.Checkbutton(sec4, text="Place shortcut in Start Menu and on Desktop",
                        variable=self.shortcut_var, command=self._toggle_shortcut
                        ).grid(row=4, column=0, columnspan=3, sticky="w",
                               pady=(2, 0))

        # ── Save button bar ─────────────────────────────────────────────
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="💾  Save & Start Sync",
                   command=self.save_settings).pack(side="left")
        ttk.Button(bar, text="Reset to defaults",
                   command=self._reset_defaults).pack(side="left", padx=8)
        ttk.Label(
            bar, foreground="#475569",
            text=("Tip: fills in all sections above, then click Save & Start. "
                  "The Start/Stop buttons at the bottom can also be used.")
        ).pack(side="left", padx=12)

    def _render_fy_chips(self, fy_list: list[str]):
        """Render FY values as a row of selectable ttk.Button chips."""
        for child in self.fy_chip_frame.winfo_children():
            child.destroy()
        self._fy_buttons: dict[str, ttk.Button] = {}
        if not fy_list:
            ttk.Label(self.fy_chip_frame,
                      text=("No FYs detected yet — make sure Tally is open with "
                            "a company loaded, then click ‘Detect FYs from Tally’."),
                      foreground="#94A3B8").pack(anchor="w")
            return
        cur = current_fy_string()
        for fy in fy_list:
            label = f"FY {fy}" + ("  (current)" if fy == cur else "")
            btn = ttk.Button(
                self.fy_chip_frame, text=label, width=20,
                command=lambda v=fy: self._select_fy(v))
            btn.pack(side="left", padx=4, pady=4)
            self._fy_buttons[fy] = btn
        # Re-style the currently-selected one so the user can see it.
        if self.fy_var.get() in self._fy_buttons:
            self._select_fy(self.fy_var.get(), persist=False)

    def _select_fy(self, fy: str, persist: bool = True):
        self.fy_var.set(fy)
        if hasattr(self, "fy_status_var"):
            self.fy_status_var.set(f"Starting FY:  {fy}")
        # Re-style: selected = primary, others = normal.
        for v, b in getattr(self, "_fy_buttons", {}).items():
            try:
                b.state(["pressed"] if v == fy else ["!pressed"])
            except Exception:
                pass
        if persist:
            self.config["starting_fy"] = fy
            save_config(self.config)
            self._toast(f"Starting FY set to {fy}.")

    def _detect_fys(self):
        host = self.entries["tally_host"].get().strip() or "localhost"
        port = self.entries["tally_port"].get().strip() or "9000"
        self.fy_status_var.set("Detecting…")
        self.root.update_idletasks()

        def worker():
            fys = fetch_tally_fys(host, port)
            self.root.after(0, lambda: self._apply_fys(fys))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_fys(self, fys: list[str]):
        if not fys:
            messagebox.showerror(
                APP_NAME,
                "Could not detect FYs. Make sure Tally is open with a company "
                "loaded, then try again.")
            self.fy_status_var.set("No FY selected yet.")
            return
        self.config["available_fys"] = fys
        save_config(self.config)
        self._render_fy_chips(fys)
        if not self.fy_var.get() or self.fy_var.get() not in fys:
            # Default selection: 2 FYs back (gives a meaningful backfill)
            default = fys[max(0, len(fys) - 3)]
            self._select_fy(default)
        else:
            self._select_fy(self.fy_var.get())
        self._toast(f"Detected {len(fys)} financial years from Tally.")

    def _on_company_chosen(self):
        """When the user picks a company, persist it immediately."""
        c = self.company_var.get().strip()
        if c:
            self.config["company_name"] = c
            save_config(self.config)

    def _reset_defaults(self):
        if not messagebox.askyesno(APP_NAME, "Reset all settings to defaults?"):
            return
        keep = {"shortcut_installed", "startup_prompted", "tray_hint_shown"}
        new_cfg = {k: self.config[k] for k in keep if k in self.config}
        new_cfg["backend_url"] = DEFAULT_BACKEND_URL
        save_config(new_cfg)
        self.config = new_cfg
        messagebox.showinfo(APP_NAME, "Settings reset. Re-open the window to refresh.")

    def _build_logs_tab(self, nb: ttk.Notebook):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="  Logs  ")
        self.log_box = scrolledtext.ScrolledText(
            f, font=("Consolas", 9), bg="#0F172A", fg="#E2E8F0",
            insertbackground="white", relief="flat", padx=10, pady=8)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def _build_about_tab(self, nb: ttk.Notebook):
        f = ttk.Frame(nb, padding=24)
        nb.add(f, text="  About  ")
        tk.Label(f, text=APP_NAME, font=("Segoe UI", 16, "bold"),
                 fg="#0F172A", bg="#FFFFFF").pack(anchor="w")
        tk.Label(f, text=APP_VERSION, font=("Segoe UI", 11),
                 fg="#64748B", bg="#FFFFFF").pack(anchor="w", pady=(0, 14))
        about = (
            "Securely syncs Tally* ERP 9 / Tally Prime data with the FLOWRA\n"
            "analytics platform. Data never leaves your network without your\n"
            "consent — only the configured FLOWRA tenant receives it.\n\n"
            "Tally* is a registered trademark of Tally Solutions. FLOWRA is\n"
            "an independent product and is not affiliated with Tally Solutions."
        )
        tk.Label(f, text=about, justify="left", fg="#475569", bg="#FFFFFF",
                 font=("Segoe UI", 10), wraplength=720).pack(anchor="w")
        tk.Label(f, text=f"Config folder:  {APP_DIR}",
                 font=("Segoe UI", 9), fg="#94A3B8",
                 bg="#FFFFFF").pack(anchor="w", pady=(20, 0))

    # ---- Tray ------------------------------------------------------------
    def _start_tray(self):
        """Boot the system-tray icon. Logs any failure so the user can see
        WHY the tray didn't appear (in the Logs tab + agent.log file)."""
        self._tray_ok = False
        try:
            import pystray
            from pystray import MenuItem as Item, Menu
        except Exception as e:
            self.log_queue.put(f"[tray] pystray unavailable: {e}")
            return

        try:
            image = build_tray_icon_image()
        except Exception as e:
            self.log_queue.put(f"[tray] icon load failed: {e}")
            image = None

        if image is None:
            # Last-ditch fallback so the tray icon still appears.
            try:
                from PIL import Image
                image = Image.new("RGB", (64, 64), (37, 99, 235))
            except Exception as e:
                self.log_queue.put(f"[tray] PIL fallback failed: {e}")
                return

        menu = Menu(
            Item("Show FLOWRA", self._tray_show, default=True),
            Item("Sync Now", lambda: self.root.after(0, self.sync_now)),
            Menu.SEPARATOR,
            Item("Open Logs Folder",
                 lambda: os.startfile(str(LOG_DIR)) if os.name == "nt" else None),
            Item("Auto-start with Windows",
                 self._tray_toggle_startup,
                 checked=lambda _: is_startup_registered()),
            Menu.SEPARATOR,
            Item("Quit FLOWRA", self._tray_quit),
        )
        try:
            self.tray = pystray.Icon("flowra", image, APP_NAME, menu)
            # Boot the tray on a daemon thread so it survives even after the
            # main window is hidden.  `visible=True` is the default but we
            # set it explicitly because some Windows versions hide the icon
            # in the overflow chevron until the user pins it.
            def _run_tray():
                try:
                    self.tray.run()
                except Exception as e:
                    self.log_queue.put(f"[tray] run() crashed: {e}")
            threading.Thread(target=_run_tray, daemon=True).start()
            self._tray_ok = True
            self.log_queue.put("[tray] icon started — look near the clock; "
                                "may be hidden behind the ‘^’ overflow chevron.")
        except Exception as e:
            self.log_queue.put(f"[tray] failed to start icon: {e}")

    def _tray_show(self, icon=None, item=None):
        self.root.after(0, self.show_window)

    def _tray_quit(self, icon=None, item=None):
        self.root.after(0, self._real_quit)

    def _tray_toggle_startup(self, icon=None, item=None):
        if is_startup_registered():
            unregister_startup()
        else:
            register_startup()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_to_tray(self):
        # If the tray icon failed to start, never withdraw — the user would
        # have no way to bring the window back. Minimize to the taskbar
        # instead so it stays visible.
        if not getattr(self, "_tray_ok", False) or self.tray is None:
            self.root.iconify()
            messagebox.showinfo(
                APP_NAME,
                "System tray is not available on this Windows configuration.\n"
                "The app has been minimised to the taskbar instead — the sync "
                "service keeps running in the background.")
            return
        self.root.withdraw()
        # First-time hint so users know the app didn't actually quit
        if not self.config.get("tray_hint_shown"):
            self.config["tray_hint_shown"] = True
            save_config(self.config)
            try:
                self.tray.notify(
                    "Sync continues in the background. "
                    "If you don't see the FLOWRA icon, click the ‘^’ arrow "
                    "near the clock — Windows may have hidden it.",
                    "FLOWRA is still running",
                )
            except Exception:
                pass

    # ---- Actions ---------------------------------------------------------
    def _set_indicator(self, key: str, ok: bool | None, text: str):
        if key not in self._indicators:
            return
        dot, var = self._indicators[key]
        var.set(text)
        if ok is True:
            dot.config(fg="#10B981")           # green
        elif ok is False:
            dot.config(fg="#EF4444")           # red
        else:
            dot.config(fg="#94A3B8")           # grey (checking)

    def _refresh_indicators_now(self):
        # Service status is read from the live subprocess.
        running = bool(self.proc and self.proc.poll() is None)
        self._set_indicator("service", running if running else None,
                            "Running" if running else "Stopped")
        # The other three involve network/socket calls — run on a thread
        # so the UI doesn't freeze.
        threading.Thread(target=self._probe_worker, daemon=True).start()

    def _probe_worker(self):
        # 1) Internet
        ok, msg = check_internet()
        self.root.after(0, lambda: self._set_indicator(
            "internet", ok, "Online" if ok else f"Offline ({msg[:24]})"))
        # 2) Tally
        host = self.entries["tally_host"].get().strip() if hasattr(self, "entries") \
            else self.config.get("tally_host", "localhost")
        port = self.entries["tally_port"].get().strip() if hasattr(self, "entries") \
            else self.config.get("tally_port", "9000")
        ok, msg = check_tally(host or "localhost", port or "9000")
        self.root.after(0, lambda: self._set_indicator(
            "tally", ok, f"{host}:{port}" if ok else "Unreachable"))
        # 3) FLOWRA backend
        url = self.entries["backend_url"].get().strip() if hasattr(self, "entries") \
            else self.config.get("backend_url", DEFAULT_BACKEND_URL)
        ok, msg = check_backend(url or DEFAULT_BACKEND_URL)
        self.root.after(0, lambda: self._set_indicator(
            "backend", ok, "Reachable" if ok else "Unreachable"))

    def _schedule_indicator_refresh(self):
        self.root.after(15000, self._tick_indicators)

    def _tick_indicators(self):
        self._refresh_indicators_now()
        self._schedule_indicator_refresh()

    # ─── Login (Settings tab) ───────────────────────────────────────────
    def _set_logged_in(self, is_logged_in: bool, email: str = ""):
        """Toggle UI state based on login status."""
        if is_logged_in:
            self.login_status_var.set(f"✓ Logged in as {email}")
            try:
                self.login_status_label.configure(fg="#10B981")
            except Exception:
                pass
            try:
                self.header_user_var.set(email)
            except Exception:
                pass
            self.login_btn.configure(text="🔓  Re-login", bg="#475569")
            self.detect_company_btn.configure(state="normal")
        else:
            self.login_status_var.set("Not logged in")
            try:
                self.login_status_label.configure(fg="#94A3B8")
            except Exception:
                pass
            try:
                self.header_user_var.set("(not logged in)")
            except Exception:
                pass
            self.login_btn.configure(text="🔐  Login to FLOWRA", bg="#2563EB")
            self.detect_company_btn.configure(state="disabled")
            self.detect_fy_btn.configure(state="disabled")

    def _do_login(self):
        """Validate credentials against FLOWRA backend. Only after success
        does the user unlock Detect Company / Detect FY."""
        email = self.entries["email"].get().strip()
        password = self.entries["password"].get().strip()
        url = self.entries["backend_url"].get().strip() or DEFAULT_BACKEND_URL
        if not email or not password:
            messagebox.showwarning(APP_NAME,
                "Please enter both Login Email and Password.")
            return
        self.login_btn.configure(state="disabled", text="Logging in…")
        self.login_status_var.set("Logging in…")
        try:
            self.login_status_label.configure(fg="#94A3B8")
        except Exception:
            pass

        def worker():
            info = fetch_subscription_info(url, email, password)
            self.root.after(0, lambda: self._apply_login(info, email, password, url))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_login(self, info: dict | None, email: str, password: str, url: str):
        self.login_btn.configure(state="normal")
        if not info:
            messagebox.showerror(APP_NAME,
                "Login failed. Please check your email and password.")
            self._set_logged_in(False)
            return
        # Persist creds so subsequent restarts know who is logged in.
        self.config.update({
            "email": email,
            "password": password,
            "backend_url": url,
        })
        save_config(self.config)
        self._sub_info = info
        self._set_logged_in(True, email)
        self._apply_subscription(info)
        self._toast(f"Logged in as {email}.")

    # ─── Subscription handling ───────────────────────────────────────────
    def _refresh_subscription_async(self):
        """Fetch subscription info in a background thread and update the
        Subscription card. Called periodically and after login."""
        email = self.config.get("email", "")
        password = self.config.get("password", "")
        url = self.config.get("backend_url", DEFAULT_BACKEND_URL)
        if not email or not password:
            self.plan_var.set("(not logged in)")
            self.account_var.set("—")
            self.expires_var.set("—")
            self.days_left_var.set("—")
            return

        def worker():
            info = fetch_subscription_info(url, email, password)
            self.root.after(0, lambda: self._apply_subscription(info))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_subscription(self, info: dict | None):
        if not info:
            try:
                self.plan_var.set("(login failed)")
                self.account_var.set("—")
                self.expires_var.set("—")
                self.days_left_var.set("—")
            except Exception:
                pass
            return
        self._sub_info = info
        plan_text = (info.get("plan") or "").upper() or "—"
        name_text = info.get("name") or self.config.get("email", "—") or "—"

        exp_raw = info.get("subscription_expires")
        if exp_raw:
            # Accept either "YYYY-MM-DD..." or "DD-MM-YYYY"
            try:
                exp_text = str(exp_raw)[:10]
            except Exception:
                exp_text = str(exp_raw)
        else:
            exp_text = "Lifetime"   # subscription_expires=None typically means
                                    #  no expiry set (admin / lifetime / trial-extended)

        days = info.get("subscription_days_left")
        if days is None:
            days_text = "Unlimited" if exp_text == "Lifetime" else "—"
        else:
            try:
                d = int(days)
                days_text = f"{d:,} days"
            except Exception:
                days_text = str(days)

        try:
            self.plan_var.set(plan_text)
            self.account_var.set(name_text)
            self.expires_var.set(exp_text)
            self.days_left_var.set(days_text)
        except Exception:
            pass

        # ── Expiry banner + agent kill switch ──
        try:
            if days is not None and isinstance(days, (int, float)) and days < 0:
                self.sub_banner_var.set(
                    "⚠  Your FLOWRA subscription has EXPIRED — the sync service "
                    "has been stopped. Click 'Request Renewal' to continue.")
                self.sub_banner.pack(fill="x", pady=(10, 0))
                if self.proc and self.proc.poll() is None:
                    self._append_log("[sub] subscription expired — stopping sync.")
                    self.stop_agent()
                self.btn_start.configure(state="disabled",
                                          text="▶  Subscription expired")
            elif days is not None and isinstance(days, (int, float)) and days <= 10:
                self.sub_banner_var.set(
                    f"⚠  Your FLOWRA subscription expires in {int(days)} day"
                    f"{'s' if int(days) != 1 else ''}. Click 'Request Renewal' "
                    "to keep syncing without interruption.")
                self.sub_banner.pack(fill="x", pady=(10, 0))
                self.btn_start.configure(state="normal",
                                          text="▶  Start Sync Service")
            else:
                self.sub_banner_var.set("")
                self.sub_banner.pack_forget()
                self.btn_start.configure(state="normal",
                                          text="▶  Start Sync Service")
        except Exception:
            pass

    def _request_renewal(self):
        """POST /api/auth/request-renewal using stored credentials."""
        email = self.config.get("email", "")
        password = self.config.get("password", "")
        url = self.config.get("backend_url", DEFAULT_BACKEND_URL)
        if not email or not password:
            messagebox.showwarning(APP_NAME,
                "Please save your Login Email and Password in Settings first.")
            return
        if not messagebox.askyesno(
            APP_NAME,
            "Send a renewal request for your current plan to FLOWRA team?\n\n"
            "Our team will reach out shortly to extend your subscription."
        ):
            return

        def worker():
            import requests as _r
            try:
                login = _r.post(f"{url.rstrip('/')}/api/auth/login",
                                json={"username": email, "password": password,
                                       "captcha_token": ""}, timeout=8)
                token = (login.json().get("data") or {}).get("token", "")
                if not token:
                    self.root.after(0, lambda: messagebox.showerror(
                        APP_NAME, "Login failed — cannot send renewal request."))
                    return
                r = _r.post(
                    f"{url.rstrip('/')}/api/auth/request-renewal",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"plan_interest": self._sub_info.get("plan", "") if
                           getattr(self, "_sub_info", None) else "",
                          "message": "Sent from FLOWRA Tally Sync Agent."},
                    timeout=10,
                )
                d = r.json()
                msg = d.get("message") or d.get("error") or "Done."
                ok = bool(d.get("success"))
                self.root.after(0, lambda: (
                    messagebox.showinfo(APP_NAME, msg) if ok
                    else messagebox.showerror(APP_NAME, msg)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    APP_NAME, f"Could not submit renewal request:\n{e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _logout(self):
        """Stop the agent, clear saved login + cached agent state, so another
        user can log in from scratch."""
        # Disable the button immediately so a double-click can't open two
        # dialogs at once.
        try:
            self.header_logout_btn.configure(state="disabled")
        except Exception:
            pass
        try:
            if not messagebox.askyesno(
                APP_NAME,
                "Logout?\n\n• The sync service will stop immediately.\n"
                "• Your email / password will be cleared from this PC.\n"
                "• Any cached Tally company / FY selection will be reset.\n\n"
                "After logout, another user can sign in with their FLOWRA "
                "credentials and start syncing their own Tally company."
            ):
                return
            # Stop sync first.
            if self.proc and self.proc.poll() is None:
                self.stop_agent()
            # Clear GUI config keys.
            cleared = {
                "backend_url": DEFAULT_BACKEND_URL,
                "tally_host": self.config.get("tally_host", "localhost"),
                "tally_port": self.config.get("tally_port", "9000"),
                "sync_interval_minutes": self.config.get(
                    "sync_interval_minutes", "20"),
            }
            save_config(cleared)
            self.config = cleared
            # Clear agent's encrypted auth + sync state so the new user
            # gets a completely clean slate.
            for fname in ("flowra_auth.enc", ".flowra_key",
                           "sync_state_v9.json", "last_company.txt"):
                p = APP_DIR / fname
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            # Forget cached subscription so the card empties immediately.
            self._sub_info = None
            # Reset Settings + Status widgets immediately.
            try:
                for k, e in self.entries.items():
                    e.delete(0, "end")
                    if k == "backend_url":
                        e.insert(0, DEFAULT_BACKEND_URL)
                    elif k == "tally_host":
                        e.insert(0, "localhost")
                    elif k == "tally_port":
                        e.insert(0, "9000")
                    elif k == "sync_interval_minutes":
                        e.insert(0, "20")
                self.company_var.set("")
                self.company_combo["values"] = []
                self.fy_var.set("")
                self.fy_status_var.set("No FY selected yet.")
                self._render_fy_chips([])
            except Exception:
                pass
            # Reset the login-state UI flags — Login button, header email,
            # green check, detect buttons.
            try:
                self._set_logged_in(False)
            except Exception:
                pass
            # Reset Subscription card on Status tab.
            try:
                self.plan_var.set("(not logged in)")
                self.account_var.set("—")
                self.expires_var.set("—")
                self.days_left_var.set("—")
                self.sub_banner_var.set("")
                self.sub_banner.pack_forget()
                self.btn_start.configure(state="normal",
                                          text="▶  Start Sync Service")
            except Exception:
                pass
            self._append_log("[gui] logged out — local credentials cleared.")
            messagebox.showinfo(APP_NAME,
                "Logged out. Open the Settings tab and sign in with the new "
                "credentials to start syncing.")
        finally:
            # Always re-enable the Logout button afterwards.
            try:
                self.header_logout_btn.configure(state="normal")
            except Exception:
                pass

    def _detect_companies(self):
        host = self.entries["tally_host"].get().strip() or "localhost"
        port = self.entries["tally_port"].get().strip() or "9000"
        # Show a quick "working" hint
        self.company_combo["values"] = ["Detecting…"]
        self.company_var.set("Detecting…")
        self.root.update_idletasks()

        def worker():
            names = fetch_tally_companies(host, port)
            self.root.after(0, lambda: self._apply_companies(names))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_companies(self, names: list[str]):
        if not names:
            self.company_combo["values"] = []
            self.company_var.set("")
            messagebox.showerror(
                APP_NAME,
                "No companies detected. Make sure Tally is open and the "
                "company is loaded.\n\n"
                "If Tally has no companies open, this list will be empty.")
            return
        self.company_combo["values"] = names

        # If multiple companies are open in Tally, force the user to
        # explicitly pick one — we only ever sync ONE company at a time.
        chosen = self.company_var.get()
        if len(names) > 1:
            chosen = self._ask_company_pick(names, current=chosen)
            if not chosen:
                self._toast("Company selection cancelled.")
                return
        else:
            chosen = names[0]

        self.company_var.set(chosen)
        self.config["available_companies"] = names
        self.config["company_name"] = chosen
        save_config(self.config)
        self._toast(f"Company set: {chosen}")
        # Enable the Detect FY button now that a company is chosen.
        try:
            self.detect_fy_btn.configure(state="normal")
        except Exception:
            pass
        # Auto-fetch FYs too so the user only ever clicks once.
        self._detect_fys()

    def _ask_company_pick(self, names: list[str], current: str = "") -> str | None:
        """Modal dialog: radio-button list of Tally companies. Returns the
        chosen name, or None if the user cancelled."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Select Tally Company to Sync")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("520x420")
        dlg.configure(bg="#FFFFFF")

        tk.Label(dlg, text="Multiple companies detected in Tally",
                 font=("Segoe UI", 13, "bold"), bg="#FFFFFF",
                 fg="#0F172A").pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(dlg, text=("FLOWRA syncs ONE company at a time. Pick which "
                            "company this PC should send to your FLOWRA "
                            "account — the others stay untouched."),
                 wraplength=460, justify="left", fg="#475569", bg="#FFFFFF",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 12))

        var = tk.StringVar(value=current if current in names else names[0])
        scrolled = tk.Frame(dlg, bg="#FFFFFF")
        scrolled.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        canvas = tk.Canvas(scrolled, bg="#FFFFFF", highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(scrolled, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=sb.set)
        inner = tk.Frame(canvas, bg="#FFFFFF")
        canvas.create_window((0, 0), window=inner, anchor="nw")

        for n in names:
            tk.Radiobutton(inner, text=n, variable=var, value=n,
                           font=("Segoe UI", 10), bg="#FFFFFF",
                           anchor="w", padx=4, pady=6,
                           selectcolor="#EFF6FF").pack(fill="x", anchor="w")
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        result = {"value": None}

        def on_ok():
            result["value"] = var.get()
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btn_bar = tk.Frame(dlg, bg="#FFFFFF")
        btn_bar.pack(fill="x", padx=20, pady=(0, 18))
        tk.Button(btn_bar, text="Cancel", command=on_cancel,
                  bg="#F1F5F9", fg="#0F172A", relief="flat",
                  font=("Segoe UI", 10), padx=18, pady=8,
                  cursor="hand2", borderwidth=0).pack(side="right", padx=(8, 0))
        tk.Button(btn_bar, text="✓  Use this company",
                  command=on_ok,
                  bg="#2563EB", fg="white", relief="flat",
                  activebackground="#1D4ED8", activeforeground="white",
                  font=("Segoe UI", 10, "bold"),
                  padx=18, pady=8, cursor="hand2",
                  borderwidth=0).pack(side="right")

        dlg.wait_window()
        return result["value"]

    def save_settings(self):
        cfg = {k: e.get().strip() for k, e in self.entries.items()}
        if not cfg.get("password"):
            cfg["password"] = self.config.get("password", "")
        if not cfg.get("backend_url"):
            cfg["backend_url"] = DEFAULT_BACKEND_URL
        cfg["company_name"] = self.company_var.get().strip() if hasattr(self, "company_var") else ""
        cfg["starting_fy"] = self.fy_var.get().strip() if hasattr(self, "fy_var") else ""
        cfg["available_companies"] = self.config.get("available_companies", [])
        cfg["available_fys"]       = self.config.get("available_fys", [])
        for k in ("startup_prompted", "tray_hint_shown", "shortcut_installed"):
            if k in self.config:
                cfg[k] = self.config[k]
        save_config(cfg)
        self.config = cfg

        # Validate before launching the sync service.
        missing = []
        if not cfg.get("email"):        missing.append("Login Email")
        if not cfg.get("password"):     missing.append("Password")
        if not cfg.get("company_name"): missing.append("Tally Company (click Detect)")
        if not cfg.get("starting_fy"):  missing.append("Starting FY")
        if missing:
            messagebox.showwarning(
                APP_NAME,
                "Settings saved, but the sync service won't start until you fill:\n\n"
                + "\n".join(f"  •  {m}" for m in missing))
            return

        # Restart the sync service (or START it if it was idle).
        if self.proc and self.proc.poll() is None:
            self.stop_agent()
            self.root.after(700, self.start_agent)
            self._toast("Settings saved — sync service restarting.")
        else:
            self.root.after(200, self.start_agent)
            self._toast("Settings saved — starting sync service.")
        # Update the visible sync-interval label.
        try:
            self.sync_interval_var.set(
                f"every {cfg.get('sync_interval_minutes', '20')} min (full)  "
                f"·  every 5 min (sales)")
        except Exception:
            pass
        self._refresh_indicators_now()
        self._refresh_subscription_async()

    def _toggle_startup(self):
        if self.startup_var.get():
            ok = register_startup()
            if not ok:
                self.startup_var.set(False)
                messagebox.showerror(APP_NAME, "Could not register auto-start.")
            else:
                self._toast("Auto-start enabled.")
        else:
            unregister_startup()
            self._toast("Auto-start disabled.")

    def _toggle_shortcut(self):
        if self.shortcut_var.get():
            if not getattr(sys, "frozen", False):
                self.shortcut_var.set(False)
                messagebox.showinfo(
                    APP_NAME,
                    "Shortcuts can only be installed when running the built "
                    "FlowraTallyAgent_v9.8.10.exe.\n\n"
                    "Build it once with build.bat, then run the .exe — it "
                    "will install the shortcuts on first launch.")
                return
            ok = install_start_menu_shortcut()
            if not ok:
                self.shortcut_var.set(False)
                messagebox.showerror(
                    APP_NAME,
                    "Could not create Start Menu / Desktop shortcuts.\n"
                    "Check the Logs tab for details.")
            else:
                self.config["shortcut_installed"] = True
                save_config(self.config)
                self._toast("Start Menu + Desktop shortcuts installed.")
        else:
            remove_start_menu_shortcut()
            self.config["shortcut_installed"] = False
            save_config(self.config)
            self._toast("Shortcuts removed.")

    def test_connection(self):
        host = self.config.get("tally_host", "localhost")
        port = self.config.get("tally_port", "9000")
        import socket
        try:
            with socket.create_connection((host, int(port)), timeout=3):
                self.tally_var.set(f"✅ {host}:{port}")
                messagebox.showinfo(APP_NAME, f"Tally is reachable on {host}:{port}")
        except Exception as e:
            self.tally_var.set("❌ Unreachable")
            messagebox.showerror(APP_NAME,
                                 f"Could not reach Tally on {host}:{port}\n\n"
                                 f"{e}\n\nMake sure Tally is open and "
                                 "ODBC Server is enabled.")

    def start_agent(self):
        if self.proc and self.proc.poll() is None:
            return
        if not self.config.get("backend_url") or not self.config.get("email"):
            messagebox.showwarning(
                APP_NAME,
                "Please fill in Settings (URL + Email + Password) first.")
            return
        # Subscription gate — never start the agent if the account has expired.
        info = getattr(self, "_sub_info", None)
        if info and info.get("subscription_days_left") is not None \
                 and info["subscription_days_left"] < 0:
            messagebox.showerror(
                APP_NAME,
                "Your FLOWRA subscription has expired. The sync service is "
                "disabled.\n\nPlease use ‘Request Renewal’ on the Status tab "
                "to extend your plan.")
            return

        env = os.environ.copy()
        env.update({
            "BACKEND_URL":            self.config.get("backend_url", DEFAULT_BACKEND_URL),
            "FLOWRA_EMAIL":           self.config.get("email", ""),
            "FLOWRA_PASSWORD":        self.config.get("password", ""),
            "TALLY_HOST":             self.config.get("tally_host", "localhost"),
            "TALLY_PORT":             self.config.get("tally_port", "9000"),
            "SYNC_INTERVAL_MINUTES":  self.config.get("sync_interval_minutes", "20"),
            # The agent reads TALLY_COMPANY — when set, it skips the
            # interactive "Select company number" prompt.
            "TALLY_COMPANY":          self.config.get("company_name", ""),
            "SYNC_ALL_FY":            "true",
            # Pin every path the agent might need to a writable, predictable
            # location under %LOCALAPPDATA%\Flowra. Setting these means the
            # agent script never falls back to `__file__` (which is undefined
            # when the script is run via exec() inside a PyInstaller bundle).
            "TALLY_EXPORT_DIR":       str(APP_DIR / "export_cache"),
            "FLOWRA_DATA_DIR":        str(APP_DIR),
            "PYTHONUNBUFFERED":       "1",
        })
        # Ensure the export cache directory exists (the agent assumes it does).
        (APP_DIR / "export_cache").mkdir(parents=True, exist_ok=True)

        # Reset Status-tab progress widgets for a fresh visual.
        if hasattr(self, "progress_var"):
            self.progress_var.set(0)
            self.progress_pct_var.set("0%  ·  starting…")
            self.phase_var.set("Initialising")
            company = self.config.get("company_name", "")
            self.active_company_var.set(company if company else "(detecting…)")

        # Pre-write the agent's sync state file so it doesn't open an
        # interactive "Enter starting FY" prompt in the headless subprocess.
        try:
            self._write_sync_state_for_agent()
        except Exception as e:
            self._append_log(f"[gui] could not pre-write sync state: {e}")

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-agent"]
        else:
            cmd = [sys.executable, resource_path(AGENT_SCRIPT)]

        log_path = LOG_DIR / f"agent_{datetime.now():%Y%m%d}.log"
        try:
            creationflags = 0
            if os.name == "nt":
                # CREATE_NO_WINDOW + NEW_PROCESS_GROUP so we can send Ctrl+Break
                creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            self.proc = subprocess.Popen(
                cmd, env=env, cwd=str(APP_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, text=True,
                creationflags=creationflags,
                bufsize=1,
            )
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Failed to start agent:\n{e}")
            return

        self._log_path = log_path
        threading.Thread(target=self._reader_thread, daemon=True).start()
        self._set_running(True)
        self._append_log(f"[gui] agent started, pid={self.proc.pid}")

    def _write_sync_state_for_agent(self):
        """Persist company + starting-FY selection into sync_state_v9.json so
        the headless agent subprocess never opens an interactive prompt.

        The agent expects the key  `selected_start_fy__<company name with
        spaces underscored>` to short-circuit its FY question."""
        company = (self.config.get("company_name") or "").strip()
        start_fy = (self.config.get("starting_fy") or "").strip()
        if not company or not start_fy:
            return  # nothing to seed yet; agent will fall back

        state_path = APP_DIR / "sync_state_v9.json"
        try:
            existing = json.loads(state_path.read_text(encoding="utf-8")) \
                if state_path.exists() else {}
        except Exception:
            existing = {}
        key_active   = f"selected_start_fy___active_"
        key_named    = f"selected_start_fy__{company.replace(' ', '_')}"
        existing[key_active] = start_fy
        existing[key_named]  = start_fy
        # Save selected company too so the agent's `last_company.txt` guard
        # doesn't prompt about a company switch.
        try:
            (APP_DIR / "last_company.txt").write_text(company, encoding="utf-8")
        except Exception:
            pass
        state_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        self._append_log(f"[gui] seeded sync_state: company={company!r}, "
                         f"start_fy={start_fy}")

    def stop_agent(self):
        if not self.proc or self.proc.poll() is not None:
            self._set_running(False)
            return
        try:
            # CTRL_BREAK_EVENT requires the subprocess to have a console.
            # We launch with CREATE_NO_WINDOW for the bundled .exe so the
            # signal raises "handle is invalid". Use terminate() in that case.
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        except Exception as e:
            self._append_log(f"[gui] stop error: {e}")
        self._set_running(False)
        self._append_log("[gui] agent stopped")

    def sync_now(self):
        if not self.proc or self.proc.poll() is not None:
            self.start_agent()
            return
        messagebox.showinfo(
            APP_NAME,
            "Sync runs automatically on the configured interval.\n"
            "Use Stop → Start to force an immediate sync.")

    # ---- Helpers ---------------------------------------------------------
    def _set_running(self, running: bool):
        if running:
            self.status_var.set("● Running")
            self.service_var.set("Running")
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
        else:
            self.status_var.set("● Stopped")
            self.service_var.set("Stopped")
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

    def _toast(self, msg: str):
        if self.tray:
            try:
                self.tray.notify(msg, APP_NAME)
                return
            except Exception:
                pass
        messagebox.showinfo(APP_NAME, msg)

    def _reader_thread(self):
        if not self.proc or not self.proc.stdout:
            return
        try:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                for line in self.proc.stdout:
                    fh.write(line)
                    fh.flush()
                    self.log_queue.put(line.rstrip("\n"))
        except Exception as e:
            self.log_queue.put(f"[gui] reader stopped: {e}")
        finally:
            self.log_queue.put("__AGENT_EXITED__")

    # Mapping of human-friendly phase labels → progress weight in % units.
    # Order matters: each label is a substring search against the agent log
    # (lower-cased). Weights add up to 100.
    _PHASE_WEIGHTS = [
        ("phase 1: stock items",          8),
        ("phase 2: sales vouchers",      18),
        ("phase 3: receipts",             8),
        ("phase 4: credit notes",         5),
        ("phase 5a: journal vouchers",    4),
        ("phase 5b: stock journals",      4),
        ("phase 6: purchase vouchers",   12),
        ("phase 7: debit notes",          4),
        ("phase 4: customer ledgers",     8),
        ("phase 8: sundry creditors",     5),
        ("phase 9: contra vouchers",      4),
        ("phase 10: all ledgers",        14),
        ("[done]",                        6),
    ]

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line == "__AGENT_EXITED__":
                    self._set_running(False)
                    self.phase_var.set("Idle")
                    self.progress_var.set(0)
                    self.progress_pct_var.set("0%  ·  stopped")
                    self.active_company_var.set("—  (not syncing)")
                    self._append_log("[gui] agent process exited")
                    continue
                self._append_log(line)
                low = line.lower()
                # ── Connectivity hints ──
                if "tally responded" in low or "ping ok" in low:
                    self.tally_var.set("Connected")
                if "login successful" in low or "authenticated" in low:
                    self.backend_var.set("Connected")
                # ── Active company ──
                # Agent prints e.g. "Syncing company: ASA AUTOTECH ..."
                # or "Single company detected: ASA AUTOTECH ..."
                for marker in ("syncing company:", "single company detected:",
                               "selected companies:"):
                    if marker in low:
                        try:
                            name = line.split(":", 1)[1].strip()
                            # Trim long FY tag and quotes
                            if name and name not in ("_active_", "Default"):
                                self.active_company_var.set(name)
                        except Exception:
                            pass
                        break
                # ── Phase-driven progress ──
                cumulative = 0
                for phase_marker, weight in self._PHASE_WEIGHTS:
                    if phase_marker == low.strip() or phase_marker in low:
                        # When we see the START of a phase, set progress
                        # to the cumulative weight BEFORE this phase, plus a
                        # nudge so the user sees motion.
                        target = cumulative + max(1, weight // 3)
                        # Show full credit for the "[done]" marker.
                        if phase_marker == "[done]":
                            target = 100
                        self.progress_var.set(min(100, target))
                        self.progress_pct_var.set(
                            f"{int(self.progress_var.get())}%  ·  "
                            f"{phase_marker.title().replace('[Done]', 'Completed')}")
                        # Pretty phase label
                        phase_label = phase_marker.split(":", 1)
                        if len(phase_label) == 2:
                            self.phase_var.set(phase_label[1].strip().title())
                        elif phase_marker == "[done]":
                            self.phase_var.set("Completed")
                        else:
                            self.phase_var.set(phase_marker.title())
                        break
                    cumulative += weight
                # ── Last sync timestamp ──
                if "[done]" in low and "sync completed" in low:
                    self.lastsync_var.set(datetime.now().strftime("%d %b %Y, %H:%M"))
                    self.progress_var.set(100)
                    self.progress_pct_var.set("100%  ·  Sync complete")
                    self.phase_var.set("Idle")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_log_queue)

    def _append_log(self, line: str):
        self.log_box.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {line}\n")
        if int(self.log_box.index("end-1c").split(".")[0]) > 5000:
            self.log_box.delete("1.0", "1000.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ── Auto-update (24-hour cycle) ───────────────────────────────────
    def _schedule_update_check(self):
        # 24 hours.
        self.root.after(24 * 60 * 60 * 1000, self._tick_update_check)

    def _tick_update_check(self):
        self._check_for_update_async()
        self._schedule_update_check()

    def _check_for_update_async(self):
        """Fetch /api/agent/latest-version on a background thread, then
        compare to our APP_VERSION. Reveals the flashing button if newer."""
        url = self.config.get("backend_url", DEFAULT_BACKEND_URL)

        def worker():
            rel = fetch_latest_release(url)
            self.root.after(0, lambda: self._apply_update_check(rel))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_update_check(self, rel: dict | None):
        if not rel:
            return
        latest = rel.get("version") or ""
        if not latest:
            return
        if _parse_ver(APP_VERSION) >= _parse_ver(latest):
            # Already on the latest build → ensure the button is hidden
            self._hide_update_button()
            return
        # Newer build available — remember it and reveal the flashing button.
        backend_url = self.config.get("backend_url", DEFAULT_BACKEND_URL)
        download_url = rel.get("download_url", "/FlowraTallyAgent.exe")
        # Convert relative URL to absolute against backend.
        if download_url.startswith("/"):
            download_url = backend_url.rstrip("/") + download_url
        self._update_info = {
            "version": latest,
            "download_url": download_url,
            "release_notes": rel.get("release_notes", ""),
            "released_at": rel.get("released_at", ""),
        }
        try:
            self._append_log(
                f"[update] new version available: v{latest} "
                f"(current {APP_VERSION}).")
        except Exception:
            pass
        self._show_update_button()

    def _show_update_button(self):
        """Pack the update button + start the amber/red flash animation."""
        try:
            if not self.update_btn.winfo_ismapped():
                self.update_btn.pack(side="left", padx=12, pady=8,
                                      after=self.btn_stop)
                # Start flashing
                self.root.after(700, self._flash_update_button)
        except Exception:
            pass

    def _hide_update_button(self):
        try:
            if self.update_btn.winfo_ismapped():
                self.update_btn.pack_forget()
        except Exception:
            pass

    def _flash_update_button(self):
        """Toggle amber ↔ red bg every 700 ms while the button is visible.
        Stops automatically once the button is hidden (post-update)."""
        try:
            if not self.update_btn.winfo_ismapped():
                return
            self._update_flash_state = not self._update_flash_state
            self.update_btn.configure(
                bg="#DC2626" if self._update_flash_state else "#F59E0B"
            )
            self.root.after(700, self._flash_update_button)
        except Exception:
            pass

    def _do_update(self):
        """User clicked the flashing Update button. Confirms, downloads,
        and hands over to updater.bat.

        Safety guarantees:
          • Does NOT touch any data on the server (uses public GET endpoint).
          • Does NOT touch Tally — we only replace our own .exe.
          • Stops the sync subprocess gracefully before relaunching.
          • Keeps a .bak of the old .exe in case the new one fails.
        """
        if not getattr(self, "_update_info", None):
            return
        info = self._update_info
        new_ver = info["version"]
        # Only works when running as the frozen .exe — otherwise we'd be
        # replacing the dev script which makes no sense.
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                APP_NAME,
                f"A new version (v{new_ver}) is available, but you are "
                "running the Python source rather than the compiled .exe. "
                "Auto-update only works for the .exe build. Rebuild from "
                "source to pick up the latest changes.")
            return

        msg = (
            f"Update FLOWRA Tally Sync Agent\n\n"
            f"Current:  {APP_VERSION}\n"
            f"Latest:    v{new_ver}\n\n"
            f"Notes: {info.get('release_notes') or '(no release notes)'}\n\n"
            "The sync service will stop for a few seconds while the new "
            "build is installed. Your Tally data and FLOWRA cloud data "
            "are NOT touched. After the update, the agent will relaunch "
            "automatically.\n\n"
            "Proceed?"
        )
        if not messagebox.askyesno(APP_NAME, msg):
            return

        # Disable the button so it can't be clicked twice.
        try:
            self.update_btn.configure(state="disabled",
                                       text="⬇  Downloading…")
        except Exception:
            pass

        def worker():
            # Stop the running sync subprocess (this is the SAFE pause —
            # writes have already been flushed to MongoDB during phase-end
            # checkpoints, and an interrupted sync just resumes next tick).
            try:
                if self.proc and self.proc.poll() is None:
                    self.stop_agent()
            except Exception:
                pass

            temp_exe = str(Path(os.environ.get("TEMP", str(APP_DIR))) /
                            f"FlowraTallyAgent_new_{new_ver}.exe")
            ok, msg2 = download_to_temp(info["download_url"], temp_exe,
                                          progress_cb=self._update_progress_cb)
            if not ok:
                self.root.after(0, lambda: self._update_failed(msg2))
                return

            target_exe = sys.executable  # the .exe we're currently running
            log_path = str(LOG_DIR / "updater.log")
            try:
                bat = write_updater_batch(temp_exe, target_exe,
                                            os.getpid(), log_path)
            except Exception as e:
                self.root.after(0, lambda: self._update_failed(
                    f"Could not write updater: {e}"))
                return

            self.root.after(0, lambda: self._launch_updater_and_exit(bat))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress_cb(self, done: int, total: int):
        pct = int((done / total) * 100) if total > 0 else 0
        try:
            self.root.after(0, lambda: self.update_btn.configure(
                text=f"⬇  Downloading… {pct}%"))
        except Exception:
            pass

    def _update_failed(self, reason: str):
        try:
            self.update_btn.configure(
                state="normal", text="⬆  Update Available")
        except Exception:
            pass
        messagebox.showerror(
            APP_NAME,
            f"Update could not be downloaded:\n\n{reason}\n\n"
            "No data was changed. Please try again later or "
            "re-download the agent manually from the FLOWRA "
            "Setup page.")
        try:
            self._append_log(f"[update] failed: {reason}")
        except Exception:
            pass

    def _launch_updater_and_exit(self, bat_path: str):
        """Spawn the updater .bat detached and quit ourselves so Windows
        releases the file lock on the old .exe."""
        try:
            self._append_log(f"[update] launching updater: {bat_path}")
        except Exception:
            pass
        try:
            # CREATE_NO_WINDOW + DETACHED_PROCESS so the .bat doesn't
            # flash a console window and survives our exit.
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                close_fds=True,
            )
        except Exception as e:
            self._update_failed(f"Could not launch updater: {e}")
            return

        # Tear everything down. _real_quit handles the running subprocess
        # and the tray icon. os._exit forces release of file handles so
        # the .bat can move/replace the .exe.
        try:
            self._real_quit()
        except Exception:
            pass
        try:
            os._exit(0)
        except Exception:
            sys.exit(0)

    def _real_quit(self):
        if self.proc and self.proc.poll() is None:
            self.stop_agent()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.destroy()


# ── Frozen-mode reentry: when the .exe is invoked with `--run-agent`,
#    delegate to the agent script. ───────────────────────────────────────
def _maybe_run_agent_directly():
    if "--run-agent" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--run-agent"]
        script = resource_path(AGENT_SCRIPT)

        # Belt-and-braces: also set TALLY_EXPORT_DIR if the GUI did not, so
        # the agent's module-level `EXPORT_DIR = os.path.dirname(__file__)`
        # fallback is never reached.
        os.environ.setdefault(
            "TALLY_EXPORT_DIR",
            str(Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
                / "Flowra" / "export_cache"),
        )

        # exec() doesn't define __file__ by default — inject it so the
        # agent's `os.path.dirname(__file__)` calls resolve cleanly.
        globals_dict = {
            "__name__": "__main__",
            "__file__": script,
            "__builtins__": __builtins__,
        }
        with open(script, encoding="utf-8") as fh:
            exec(compile(fh.read(), script, "exec"), globals_dict)
        sys.exit(0)


def _handle_cli_flags() -> bool:
    """Returns True if the program should exit immediately after handling
    a CLI-only flag (no GUI shown)."""
    if "--register-startup" in sys.argv:
        ok = register_startup()
        print("Auto-start registered." if ok else "Failed to register auto-start.")
        return True
    if "--unregister-startup" in sys.argv:
        ok = unregister_startup()
        print("Auto-start removed." if ok else "Failed to remove auto-start.")
        return True
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return True
    return False


def _acquire_single_instance_lock() -> bool:
    """Bind a TCP socket to 127.0.0.1:SINGLE_INSTANCE_PORT.

    Returns True if this is the first instance (lock acquired), False if
    another agent is already running. The bound socket is kept alive for
    the lifetime of the process via the module-level reference."""
    global _single_instance_socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # DO NOT set SO_REUSEADDR — we want the bind to fail when a
        # second copy starts up. Linux honours SO_REUSEADDR more loosely
        # than Windows, but we ship for Windows anyway.
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        _single_instance_socket = s  # pin so the GC never closes it
        return True
    except OSError:
        # Port already in use ⇒ another FLOWRA agent is running.
        return False


def main():
    _maybe_run_agent_directly()
    if _handle_cli_flags():
        return

    # SINGLE-INSTANCE GUARD — must run BEFORE we create any window or
    # spawn the sync subprocess. Prevents duplicate MongoDB writes +
    # duplicate Tally fetches when a user accidentally double-clicks the
    # .exe or runs auto-start while a tray instance is already up.
    if not _acquire_single_instance_lock():
        # Show a friendly dialog and bail. We deliberately do not try to
        # raise the existing instance's window — that needs Win32 IPC and
        # adds complexity for marginal gain. The existing instance is
        # already in the system tray; the user can click it.
        try:
            tmp = tk.Tk()
            tmp.withdraw()
            messagebox.showinfo(
                APP_NAME,
                "FLOWRA Tally Sync Agent is already running.\n\n"
                "Look for the green FLOWRA icon in your Windows system "
                "tray (bottom-right corner, next to the clock). "
                "Right-click it to show the window, view logs, or quit.\n\n"
                "Only one copy of the agent can run at a time — multiple "
                "copies would cause duplicate data to be synced to FLOWRA.",
            )
            tmp.destroy()
        except Exception:
            # Headless / no display — just print and exit quietly.
            print(f"{APP_NAME} is already running. Exiting duplicate instance.")
        sys.exit(0)

    start_minimized = "--minimized" in sys.argv

    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
    except Exception:
        pass
    FlowraAgentGUI(root, start_minimized=start_minimized)
    root.mainloop()


if __name__ == "__main__":
    main()
