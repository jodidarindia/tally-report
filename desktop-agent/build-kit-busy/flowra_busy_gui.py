"""FLOWRA Busy Sync Agent — Windows GUI Launcher (v1.2)

Visual + behavioural clone of the Tally Sync Agent GUI (v9.8.29):
  • Navy header with FLOWRA logo, "Running/Stopped" pill, user email + Logout.
  • Four tabs: Status · Settings · Logs · About.
  • Status tab: 4 connectivity cards (Internet · Busy Data · FLOWRA Cloud ·
    Sync Service), live Sync Status panel with progress bar, Subscription
    card with Refresh + Request Renewal buttons.
  • Settings tab: Login → locks after success, Busy data folder + Detect
    Company, Starting FY chips, Advanced (sync interval, backend URL,
    Windows auto-start, shortcut placement).
  • Bottom bar: blue "▶ Start Sync Service", "■ Stop", "Hide to Tray",
    "Open Logs Folder".

The GUI spawns `flowra_busy_agent.py --headless` as a subprocess so the
main thread stays responsive. All settings live in
`%LOCALAPPDATA%\\Flowra\\agent_busy.env`.
"""
import os
import sys
import json
import queue
import socket
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from datetime import datetime
from pathlib import Path

APP_NAME = "FLOWRA Busy Sync Agent"
APP_VERSION = "v1.2"
AGENT_SCRIPT = "flowra_busy_agent.py"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Flowra"
APP_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = APP_DIR / "agent_busy.env"
LOG_DIR = APP_DIR / "logs_busy"
LOG_DIR.mkdir(exist_ok=True)

PROD_URL = "https://insights.flowralive.in"
DEFAULT_BACKEND_URL = PROD_URL
INTERNET_PROBE_URL = "https://www.google.com/generate_204"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "FlowraBusyAgent"

# Single-instance guard port (distinct from Tally's 38765).
SINGLE_INSTANCE_PORT = 38766
_single_instance_socket = None


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
        return True
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
    appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Flowra"


def _start_menu_shortcut_path() -> Path:
    return _start_menu_dir() / "FLOWRA Busy Sync Agent.lnk"


def _desktop_shortcut_path() -> Path:
    desk = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    return desk / "FLOWRA Busy Sync Agent.lnk"


def _create_lnk(target_lnk: Path, exe_path: str, icon_path: str = "") -> bool:
    if os.name != "nt":
        return False
    try:
        target_lnk.parent.mkdir(parents=True, exist_ok=True)
        clean_exe = exe_path.strip('"')
        ps = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s  = $ws.CreateShortcut("{target_lnk}"); '
            f'$s.TargetPath = "{clean_exe}"; '
            f'$s.WorkingDirectory = "{os.path.dirname(clean_exe)}"; '
            f'$s.Description = "FLOWRA Busy Sync Agent"; '
        )
        if icon_path and os.path.exists(icon_path):
            ps += f'$s.IconLocation = "{icon_path},0"; '
        ps += '$s.Save();'
        result = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        return result.returncode == 0 and target_lnk.exists()
    except Exception:
        return False


def install_start_menu_shortcut() -> bool:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    exe = sys.executable
    ok1 = _create_lnk(_start_menu_shortcut_path(), exe, exe)
    ok2 = _create_lnk(_desktop_shortcut_path(), exe, exe)
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
    return ok


# ── Tray icon ───────────────────────────────────────────────────────────
def build_tray_icon_image():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    for candidate in ("flowra_logo.png", "flowra.ico"):
        p = resource_path(candidate)
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA")
                img.thumbnail((64, 64), Image.LANCZOS)
                return img
            except Exception:
                continue
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
def check_busy_folder(folder: str) -> tuple[bool, str]:
    """A valid Busy data folder contains at least one *.bds file
    (either db.bds master or db{year}.bds FY files) or DATA.ZIP."""
    if not folder:
        return False, "no folder configured"
    if not os.path.isdir(folder):
        return False, "not a folder"
    try:
        for name in os.listdir(folder):
            low = name.lower()
            if low.endswith(".bds") or low == "data.zip":
                return True, os.path.basename(folder)
    except Exception as e:
        return False, str(e)
    return False, "no .bds files"


def check_internet() -> tuple[bool, str]:
    try:
        import requests
        r = requests.get(INTERNET_PROBE_URL, timeout=3)
        return (r.status_code in (200, 204), f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


def check_backend(url: str) -> tuple[bool, str]:
    if not url:
        return False, "no URL configured"
    try:
        import requests
        r = requests.get(url.rstrip("/") + "/api/public/plans", timeout=4)
        return (r.status_code < 500, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


def detect_busy_companies(root_folder: str) -> list[dict]:
    """Scan a Busy data folder tree for company subfolders.

    Two supported layouts:
      1. Root folder IS the company (contains db*.bds directly).
      2. Root folder holds multiple company subfolders, each with db*.bds.

    Returns [{"name": display, "folder": abspath}, ...]
    """
    if not root_folder or not os.path.isdir(root_folder):
        return []

    def _has_bds(p: str) -> bool:
        try:
            for f in os.listdir(p):
                fl = f.lower()
                if fl.endswith(".bds") or fl == "data.zip":
                    return True
        except Exception:
            pass
        return False

    results: list[dict] = []
    # Case 1: folder itself is a company
    if _has_bds(root_folder):
        results.append({
            "name": os.path.basename(root_folder.rstrip("/\\")) or "Busy Company",
            "folder": os.path.abspath(root_folder),
        })
    # Case 2: subfolders are companies (skip if we already found one at root)
    if not results:
        try:
            for entry in sorted(os.listdir(root_folder)):
                sub = os.path.join(root_folder, entry)
                if os.path.isdir(sub) and _has_bds(sub):
                    results.append({
                        "name": entry,
                        "folder": os.path.abspath(sub),
                    })
        except Exception:
            pass
    return results


def detect_busy_fys(company_folder: str) -> list[str]:
    """Scan a company folder for db{year}.bds files → return FY strings."""
    if not company_folder or not os.path.isdir(company_folder):
        return []
    fys: set[str] = set()
    try:
        for name in os.listdir(company_folder):
            fl = name.lower()
            if not (fl.startswith("db") and fl.endswith(".bds")):
                continue
            year_part = fl.replace("db", "").replace(".bds", "")
            if not year_part or not year_part.isdigit():
                continue
            try:
                # "12025" (prefix 1) or "2025"
                if year_part.startswith("1") and len(year_part) == 5:
                    year = int(year_part[1:])
                else:
                    year = int(year_part)
                if 1990 < year < 2100:
                    fys.add(f"{year}-{str(year + 1)[-2:]}")
            except ValueError:
                pass
    except Exception:
        pass
    return sorted(fys)


def fetch_subscription_info(backend_url: str, email: str, password: str) -> dict | None:
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


# ── Main GUI ─────────────────────────────────────────────────────────────
class FlowraBusyAgentGUI:
    def __init__(self, root: tk.Tk, start_minimized: bool = False):
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.config = load_config()
        if not self.config.get("backend_url"):
            self.config["backend_url"] = DEFAULT_BACKEND_URL
            save_config(self.config)
        self.tray = None
        self._log_path: Path | None = None
        self._sub_info: dict | None = None

        self._build_ui()
        self._poll_log_queue()
        self._start_tray()

        root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # If creds stored, restore logged-in UI and lock the login fields.
        if self.config.get("email") and self.config.get("password"):
            try:
                self._set_logged_in(True, self.config["email"])
            except Exception:
                pass
        else:
            try:
                self._set_logged_in(False)
            except Exception:
                pass

        if start_minimized:
            self.root.after(50, self.hide_to_tray)

        # Initial subscription pull (silent — no blocking network on UI thread)
        self.root.after(500, self._refresh_subscription_async)
        self._schedule_subscription_refresh()

    # ---- UI construction --------------------------------------------------
    def _build_ui(self):
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1100x820")
        self.root.minsize(960, 720)
        try:
            self.root.iconbitmap(resource_path("flowra.ico"))
        except Exception:
            pass

        # Header strip
        header = tk.Frame(self.root, bg="#0F172A", height=72)
        header.pack(fill="x")
        self._header_logo = load_header_logo()
        if self._header_logo is not None:
            tk.Label(header, image=self._header_logo,
                     bg="#0F172A").pack(side="left", padx=(20, 12), pady=14)
        tk.Label(header, text="FLOWRA",
                 font=("Segoe UI", 20, "bold"), fg="#FFFFFF",
                 bg="#0F172A").pack(side="left", pady=14)
        tk.Label(header, text=f"Busy Sync Agent  ·  {APP_VERSION}",
                 font=("Segoe UI", 10), fg="#94A3B8",
                 bg="#0F172A").pack(side="left", padx=10, pady=14)

        right = tk.Frame(header, bg="#0F172A")
        right.pack(side="right", padx=16, pady=14)
        self.header_logout_btn = tk.Button(
            right, text="🚪  Logout",
            command=self._logout,
            bg="#1E293B", fg="white", relief="flat",
            activebackground="#334155", activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            padx=14, pady=6, cursor="hand2", borderwidth=0,
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

        # Bottom action bar (packed BEFORE the notebook so Tk reserves height)
        bar = tk.Frame(self.root, bg="#F1F5F9", height=56)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
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

        # Notebook
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=10)
        self._build_status_tab(nb)
        self._build_settings_tab(nb)
        self._build_logs_tab(nb)
        self._build_about_tab(nb)

    def _build_status_tab(self, nb: ttk.Notebook):
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

        # 4 connectivity cards
        cards = tk.Frame(f, bg="#FFFFFF")
        cards.pack(fill="x", pady=(0, 16))
        self._indicators: dict[str, tuple[tk.Label, tk.StringVar]] = {}
        layout = [
            ("internet", "Internet",         "Checking…"),
            ("busy",     "Busy Data",        "Checking…"),
            ("backend",  "FLOWRA Cloud",     "Checking…"),
            ("service",  "Sync Service",     "Stopped"),
        ]
        for i, (key, label, default) in enumerate(layout):
            card = tk.Frame(cards, bg="#F8FAFC", relief="solid", bd=1, padx=14, pady=12)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=label, fg="#64748B",
                     bg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w")
            row = tk.Frame(card, bg="#F8FAFC")
            row.pack(anchor="w", pady=(4, 0))
            dot = tk.Label(row, text="●", fg="#94A3B8",
                           bg="#F8FAFC", font=("Segoe UI", 14, "bold"))
            dot.pack(side="left")
            v = tk.StringVar(value=default)
            tk.Label(row, textvariable=v, fg="#0F172A",
                     bg="#F8FAFC", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(6, 0))
            self._indicators[key] = (dot, v)
        self.service_var = self._indicators["service"][1]
        self.busy_var    = self._indicators["busy"][1]
        self.backend_var = self._indicators["backend"][1]

        # Sync Status card
        sync_card = tk.Frame(f, bg="#EFF6FF", relief="solid", bd=1, padx=16, pady=14)
        sync_card.pack(fill="x", pady=(0, 14))
        tk.Label(sync_card, text="Sync Status", fg="#1E3A8A",
                 bg="#EFF6FF", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        row_co = tk.Frame(sync_card, bg="#EFF6FF")
        row_co.pack(anchor="w", pady=(6, 2))
        tk.Label(row_co, text="Active company: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        self.active_company_var = tk.StringVar(value="—  (not syncing)")
        tk.Label(row_co, textvariable=self.active_company_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 10, "bold")).pack(side="left")

        row_ph = tk.Frame(sync_card, bg="#EFF6FF")
        row_ph.pack(anchor="w", pady=(2, 6))
        tk.Label(row_ph, text="Current phase: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        self.phase_var = tk.StringVar(value="Idle")
        tk.Label(row_ph, textvariable=self.phase_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 10)).pack(side="left")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(sync_card, mode="determinate",
                                            maximum=100, length=600,
                                            variable=self.progress_var)
        self.progress_bar.pack(fill="x", pady=(6, 2))
        self.progress_pct_var = tk.StringVar(value="0%  ·  waiting")
        tk.Label(sync_card, textvariable=self.progress_pct_var,
                 fg="#1E3A8A", bg="#EFF6FF",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self.lastsync_var = tk.StringVar(value="Never")
        last_row = tk.Frame(sync_card, bg="#EFF6FF")
        last_row.pack(anchor="w", pady=(8, 0))
        tk.Label(last_row, text="Last successful sync: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(last_row, textvariable=self.lastsync_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 10, "bold")).pack(side="left")

        intv_row = tk.Frame(sync_card, bg="#EFF6FF")
        intv_row.pack(anchor="w", pady=(4, 0))
        tk.Label(intv_row, text="Sync interval: ", fg="#475569",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")
        self.sync_interval_var = tk.StringVar(
            value=f"every {self.config.get('sync_interval_minutes', '20')} min (full)  "
                  f"·  every 5 min (sales)")
        tk.Label(intv_row, textvariable=self.sync_interval_var, fg="#0F172A",
                 bg="#EFF6FF", font=("Segoe UI", 9)).pack(side="left")

        # Subscription card
        sub_card = tk.Frame(f, bg="#FEFCE8", relief="solid", bd=1, padx=16, pady=14)
        sub_card.pack(fill="x", pady=(0, 12))
        head_row = tk.Frame(sub_card, bg="#FEFCE8")
        head_row.pack(fill="x")
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

        self.sub_banner_var = tk.StringVar(value="")
        self.sub_banner = tk.Label(
            sub_card, textvariable=self.sub_banner_var,
            fg="#7F1D1D", bg="#FEE2E2",
            font=("Segoe UI", 9, "bold"), padx=10, pady=6,
            anchor="w", justify="left", wraplength=860,
        )

        # Action row
        actions = tk.Frame(f)
        actions.pack(fill="x", pady=10)
        tk.Button(actions, text="🔄  Re-check Now", command=self._refresh_indicators_now,
                  bg="#10B981", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"),
                  padx=16, pady=8, cursor="hand2").pack(side="left")
        tk.Button(actions, text="🧪  Test Busy Folder", command=self.test_connection,
                  bg="#F1F5F9", fg="#0F172A", relief="flat",
                  font=("Segoe UI", 10),
                  padx=16, pady=8, cursor="hand2").pack(side="left", padx=8)

        tk.Label(f, justify="left", fg="#64748B", bg="#FFFFFF",
                 font=("Segoe UI", 9), wraplength=820,
                 text=("Green = connected · Red = offline / unreachable · "
                       "Grey = checking.\nThis window can be closed safely — "
                       "the sync service keeps running in the system tray.")).pack(anchor="w",
                                                                                    pady=(20, 0))

        self.root.after(300, self._refresh_indicators_now)
        self._schedule_indicator_refresh()

    def _schedule_subscription_refresh(self):
        self.root.after(5 * 60 * 1000, self._tick_subscription)

    def _tick_subscription(self):
        self._refresh_subscription_async()
        self._schedule_subscription_refresh()

    def _build_settings_tab(self, nb: ttk.Notebook):
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
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        outer.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(canvas_window, width=e.width))

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(-1 * int(event.delta / 120), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

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

        # ── Section 2: Busy Data Folder ─────────────────────────────────
        sec2 = ttk.LabelFrame(outer, text="  2. Busy Data Folder  ", padding=14)
        sec2.pack(fill="x", pady=(0, 12))
        ttk.Label(sec2, text="Data folder").grid(row=0, column=0, sticky="w",
                                                  padx=(0, 12), pady=6)
        self.folder_entry = ttk.Entry(sec2, width=52)
        self.folder_entry.insert(0, self.config.get("busy_folder", ""))
        self.folder_entry.grid(row=0, column=1, sticky="ew", pady=6)
        # When the user edits + tabs out, auto-detect immediately.
        self.folder_entry.bind("<FocusOut>", lambda _e: self._on_folder_changed())
        self.folder_entry.bind("<Return>",  lambda _e: self._on_folder_changed())
        tk.Button(sec2, text="📂  Browse…",
                  command=self._browse_folder,
                  bg="#2563EB", fg="white", relief="flat",
                  activebackground="#1D4ED8", activeforeground="white",
                  font=("Segoe UI", 10, "bold"),
                  padx=12, pady=6, cursor="hand2", borderwidth=0,
                  ).grid(row=0, column=2, padx=(8, 0), pady=6)

        # Company selector
        ttk.Label(sec2, text="Busy Company").grid(row=1, column=0, sticky="w",
                                                    padx=(0, 12), pady=(10, 6))
        self.company_var = tk.StringVar(value=self.config.get("company_name", ""))
        self.company_combo = ttk.Combobox(sec2, textvariable=self.company_var,
                                          width=44, state="readonly")
        self.company_combo.grid(row=1, column=1, sticky="w", pady=(10, 6))
        self.detect_company_btn = tk.Button(
            sec2, text="🔍  Detect Company",
            command=self._detect_companies,
            bg="#2563EB", fg="white", relief="flat",
            activebackground="#1D4ED8", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=12, pady=6, cursor="hand2", borderwidth=0,
            state="disabled",
        )
        self.detect_company_btn.grid(row=1, column=2, padx=(8, 0), pady=(10, 6))
        cached = self.config.get("available_companies") or []
        if cached:
            self.company_combo["values"] = [c.get("name", c) if isinstance(c, dict) else c
                                             for c in cached]
        self.company_combo.bind("<<ComboboxSelected>>",
                                 lambda _e: self._on_company_chosen())
        ttk.Label(sec2,
                  text=("Point FLOWRA at your Busy data folder (e.g. C:\\Busy21\\Data\\). "
                        "We only READ the .bds files — nothing is modified locally."),
                  foreground="#94A3B8", wraplength=720).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        sec2.columnconfigure(1, weight=1)

        # ── Section 3: Starting Financial Year (chips) ─────────────────
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
            action_row, text="🔄  Detect FYs from Busy",
            command=self._detect_fys,
            bg="#2563EB", fg="white", relief="flat",
            activebackground="#1D4ED8", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=14, pady=6, cursor="hand2", borderwidth=0,
            state="disabled",
        )
        self.detect_fy_btn.pack(side="left")
        tk.Label(action_row, textvariable=self.fy_status_var,
                 fg="#0F172A", font=("Segoe UI", 10)).pack(side="left", padx=14)

        # ── Section 4: Advanced ────────────────────────────────────────
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

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="💾  Save & Start Sync",
                   command=self.save_settings).pack(side="left")
        ttk.Button(bar, text="Reset to defaults",
                   command=self._reset_defaults).pack(side="left", padx=8)
        ttk.Label(
            bar, foreground="#475569",
            text=("Tip: fill all sections above, then click Save & Start. "
                  "The Start/Stop buttons at the bottom can also be used.")
        ).pack(side="left", padx=12)

    def _render_fy_chips(self, fy_list: list[str]):
        for child in self.fy_chip_frame.winfo_children():
            child.destroy()
        self._fy_buttons: dict[str, ttk.Button] = {}
        if not fy_list:
            ttk.Label(self.fy_chip_frame,
                      text=("No FYs detected yet — pick your Busy data folder "
                            "above then click ‘Detect FYs from Busy’."),
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
        if self.fy_var.get() in self._fy_buttons:
            self._select_fy(self.fy_var.get(), persist=False)

    def _select_fy(self, fy: str, persist: bool = True):
        self.fy_var.set(fy)
        if hasattr(self, "fy_status_var"):
            self.fy_status_var.set(f"Starting FY:  {fy}")
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
        folder = self._current_company_folder()
        if not folder:
            messagebox.showwarning(APP_NAME,
                "Please pick a Busy data folder + detect a company first.")
            return
        self.fy_status_var.set("Detecting…")
        self.root.update_idletasks()

        def worker():
            fys = detect_busy_fys(folder)
            self.root.after(0, lambda: self._apply_fys(fys))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_fys(self, fys: list[str]):
        if not fys:
            messagebox.showerror(
                APP_NAME,
                "No FY databases (db{year}.bds) were found in this folder. "
                "Check the folder path and try again.")
            self.fy_status_var.set("No FY selected yet.")
            return
        self.config["available_fys"] = fys
        save_config(self.config)
        self._render_fy_chips(fys)
        if not self.fy_var.get() or self.fy_var.get() not in fys:
            default = fys[max(0, len(fys) - 3)]
            self._select_fy(default)
        else:
            self._select_fy(self.fy_var.get())
        self._toast(f"Detected {len(fys)} financial year(s) in Busy data.")

    def _on_company_chosen(self):
        c = self.company_var.get().strip()
        if c:
            self.config["company_name"] = c
            # Persist the actual folder too
            folder = self._folder_for_company_name(c)
            if folder:
                self.config["company_folder"] = folder
            save_config(self.config)
            # Auto-fetch FYs whenever a company is picked
            self._detect_fys()

    def _folder_for_company_name(self, name: str) -> str:
        for c in (self.config.get("available_companies") or []):
            if isinstance(c, dict) and c.get("name") == name:
                return c.get("folder", "")
        # Fallback: root folder IS the company
        root = self.folder_entry.get().strip() if hasattr(self, "folder_entry") else ""
        return root

    def _current_company_folder(self) -> str:
        folder = self.config.get("company_folder") or ""
        if folder and os.path.isdir(folder):
            return folder
        cname = self.company_var.get().strip() if hasattr(self, "company_var") else ""
        return self._folder_for_company_name(cname)

    def _browse_folder(self):
        initial = self.folder_entry.get().strip() or os.path.expanduser("~")
        chosen = filedialog.askdirectory(title="Select Busy data folder",
                                          initialdir=initial)
        if chosen:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, chosen)
            self._on_folder_changed()

    def _on_folder_changed(self):
        """User picked/typed a folder — persist and auto-detect companies + FYs."""
        folder = self.folder_entry.get().strip()
        self.config["busy_folder"] = folder
        save_config(self.config)
        if folder:
            # Enable Detect buttons and auto-run detection.
            self.detect_company_btn.configure(state="normal")
            self._detect_companies()
        self._refresh_indicators_now()

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
            "Securely syncs Busy Accounting Software data with the FLOWRA\n"
            "analytics platform. Data never leaves your network without your\n"
            "consent — only the configured FLOWRA tenant receives it.\n\n"
            "Busy is a registered trademark of Busy Infotech Pvt. Ltd. FLOWRA\n"
            "is an independent product and is not affiliated with Busy Infotech."
        )
        tk.Label(f, text=about, justify="left", fg="#475569", bg="#FFFFFF",
                 font=("Segoe UI", 10), wraplength=720).pack(anchor="w")
        tk.Label(f, text=f"Config folder:  {APP_DIR}",
                 font=("Segoe UI", 9), fg="#94A3B8",
                 bg="#FFFFFF").pack(anchor="w", pady=(20, 0))

    # ---- Tray ------------------------------------------------------------
    def _start_tray(self):
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
            self.tray = pystray.Icon("flowra-busy", image, APP_NAME, menu)

            def _run_tray():
                try:
                    self.tray.run()
                except Exception as e:
                    self.log_queue.put(f"[tray] run() crashed: {e}")
            threading.Thread(target=_run_tray, daemon=True).start()
            self._tray_ok = True
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
        if not getattr(self, "_tray_ok", False) or self.tray is None:
            self.root.iconify()
            return
        self.root.withdraw()

    # ---- Indicators ------------------------------------------------------
    def _set_indicator(self, key: str, ok: bool | None, text: str):
        if key not in self._indicators:
            return
        dot, var = self._indicators[key]
        var.set(text)
        if ok is True:
            dot.config(fg="#10B981")
        elif ok is False:
            dot.config(fg="#EF4444")
        else:
            dot.config(fg="#94A3B8")

    def _refresh_indicators_now(self):
        running = bool(self.proc and self.proc.poll() is None)
        self._set_indicator("service", running if running else None,
                            "Running" if running else "Stopped")
        threading.Thread(target=self._probe_worker, daemon=True).start()

    def _probe_worker(self):
        ok, msg = check_internet()
        self.root.after(0, lambda: self._set_indicator(
            "internet", ok, "Online" if ok else f"Offline ({msg[:24]})"))

        folder = (self.folder_entry.get().strip() if hasattr(self, "folder_entry")
                   else self.config.get("busy_folder", ""))
        ok, msg = check_busy_folder(folder)
        self.root.after(0, lambda: self._set_indicator(
            "busy", ok, msg if ok else "Unreachable"))

        url = (self.entries["backend_url"].get().strip() if hasattr(self, "entries")
                else self.config.get("backend_url", DEFAULT_BACKEND_URL))
        ok, msg = check_backend(url or DEFAULT_BACKEND_URL)
        self.root.after(0, lambda: self._set_indicator(
            "backend", ok, "Reachable" if ok else "Unreachable"))

    def _schedule_indicator_refresh(self):
        self.root.after(15000, self._tick_indicators)

    def _tick_indicators(self):
        self._refresh_indicators_now()
        self._schedule_indicator_refresh()

    # ---- Login lock/unlock ----------------------------------------------
    def _set_logged_in(self, is_logged_in: bool, email: str = ""):
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
            # Lock login fields until sign-out (bug #6)
            for k in ("email", "password"):
                if k in self.entries:
                    self.entries[k].configure(state="disabled")
            self.login_btn.configure(text="🔓  Re-login", bg="#475569",
                                     state="disabled")
            # Enable Detect once the folder exists
            if self.folder_entry.get().strip():
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
            # Unlock login fields
            for k in ("email", "password"):
                if k in self.entries:
                    self.entries[k].configure(state="normal")
            self.login_btn.configure(text="🔐  Login to FLOWRA", bg="#2563EB",
                                     state="normal")
            self.detect_company_btn.configure(state="disabled")
            self.detect_fy_btn.configure(state="disabled")

    def _do_login(self):
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
        self.config.update({
            "email": email,
            "password": password,
            "backend_url": url,
        })
        save_config(self.config)
        self._sub_info = info
        self._set_logged_in(True, email)
        self._apply_subscription(info)
        # Show login-success banner (bug #6)
        messagebox.showinfo(APP_NAME, f"Login successful — welcome, {email}!\n\n"
                                        "Login fields are now locked. "
                                        "Sign out to switch accounts.")

    # ---- Subscription card ----------------------------------------------
    def _refresh_subscription_async(self):
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
            try:
                exp_text = str(exp_raw)[:10]
            except Exception:
                exp_text = str(exp_raw)
        else:
            exp_text = "Lifetime"

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
                           self._sub_info else "",
                          "message": "Sent from FLOWRA Busy Sync Agent."},
                    timeout=10,
                )
                d = r.json()
                msg = d.get("message") or d.get("error") or "Done."
                ok = bool(d.get("success"))
                self.root.after(0, lambda: (
                    messagebox.showinfo(APP_NAME, msg) if ok
                    else messagebox.showerror(APP_NAME, msg)))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda err=err: messagebox.showerror(
                    APP_NAME, f"Could not submit renewal request:\n{err}"))
        threading.Thread(target=worker, daemon=True).start()

    def _logout(self):
        try:
            self.header_logout_btn.configure(state="disabled")
        except Exception:
            pass
        try:
            if not messagebox.askyesno(
                APP_NAME,
                "Logout?\n\n• The sync service will stop immediately.\n"
                "• Your email / password will be cleared from this PC.\n"
                "• Any cached company / FY selection will be reset.\n\n"
                "After logout, another user can sign in with their FLOWRA "
                "credentials and start syncing their own Busy company."
            ):
                return
            if self.proc and self.proc.poll() is None:
                self.stop_agent()
            cleared = {
                "backend_url": DEFAULT_BACKEND_URL,
                "busy_folder": self.config.get("busy_folder", ""),
                "sync_interval_minutes": self.config.get(
                    "sync_interval_minutes", "20"),
            }
            save_config(cleared)
            self.config = cleared
            # Wipe agent state files
            for fname in ("flowra_busy_config.json", "sync_state_busy.json",
                           "agent_busy.env"):
                p = APP_DIR / fname
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            self._sub_info = None
            try:
                # Re-enable + clear inputs
                for k in ("email", "password"):
                    if k in self.entries:
                        self.entries[k].configure(state="normal")
                        self.entries[k].delete(0, "end")
                self.entries["backend_url"].delete(0, "end")
                self.entries["backend_url"].insert(0, DEFAULT_BACKEND_URL)
                self.entries["sync_interval_minutes"].delete(0, "end")
                self.entries["sync_interval_minutes"].insert(0, "20")
                self.company_var.set("")
                self.company_combo["values"] = []
                self.fy_var.set("")
                self.fy_status_var.set("No FY selected yet.")
                self._render_fy_chips([])
            except Exception:
                pass
            try:
                self._set_logged_in(False)
            except Exception:
                pass
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
            try:
                self.header_logout_btn.configure(state="normal")
            except Exception:
                pass

    # ---- Company detection ----------------------------------------------
    def _detect_companies(self):
        folder = self.folder_entry.get().strip() or self.config.get("busy_folder", "")
        if not folder:
            messagebox.showwarning(APP_NAME,
                "Please pick your Busy data folder first.")
            return
        self.company_combo["values"] = ["Detecting…"]
        self.company_var.set("Detecting…")
        self.root.update_idletasks()

        def worker():
            companies = detect_busy_companies(folder)
            self.root.after(0, lambda: self._apply_companies(companies))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_companies(self, companies: list[dict]):
        if not companies:
            self.company_combo["values"] = []
            self.company_var.set("")
            messagebox.showerror(
                APP_NAME,
                "No Busy companies detected in this folder.\n\n"
                "Point FLOWRA at your Busy data folder (contains .bds files) "
                "or its parent (with company subfolders).")
            return
        names = [c["name"] for c in companies]
        self.company_combo["values"] = names
        chosen = self.company_var.get()
        if chosen not in names:
            chosen = names[0]
        self.company_var.set(chosen)
        self.config["available_companies"] = companies
        self.config["company_name"] = chosen
        self.config["company_folder"] = next(
            (c["folder"] for c in companies if c["name"] == chosen), "")
        save_config(self.config)
        self._toast(f"Detected {len(companies)} company/companies. Selected: {chosen}")
        try:
            self.detect_fy_btn.configure(state="normal")
        except Exception:
            pass
        # Auto-fetch FYs
        self._detect_fys()

    def save_settings(self):
        cfg = {k: (e.get().strip() if e.cget("state") != "disabled" or k in ("email",)
                    else self.config.get(k, ""))
               for k, e in self.entries.items()}
        # Password entry gets special treatment: if locked, use stored value.
        if not cfg.get("password"):
            cfg["password"] = self.config.get("password", "")
        if not cfg.get("email"):
            cfg["email"] = self.config.get("email", "")
        if not cfg.get("backend_url"):
            cfg["backend_url"] = DEFAULT_BACKEND_URL

        cfg["busy_folder"] = self.folder_entry.get().strip() if hasattr(self, "folder_entry") \
                                else self.config.get("busy_folder", "")
        cfg["company_name"] = self.company_var.get().strip() if hasattr(self, "company_var") else ""
        cfg["company_folder"] = self._folder_for_company_name(cfg["company_name"])
        cfg["starting_fy"] = self.fy_var.get().strip() if hasattr(self, "fy_var") else ""
        cfg["available_companies"] = self.config.get("available_companies", [])
        cfg["available_fys"] = self.config.get("available_fys", [])
        for k in ("startup_prompted", "tray_hint_shown", "shortcut_installed"):
            if k in self.config:
                cfg[k] = self.config[k]
        save_config(cfg)
        self.config = cfg

        missing = []
        if not cfg.get("email"):
            missing.append("Login Email")
        if not cfg.get("password"):
            missing.append("Password")
        if not cfg.get("busy_folder"):
            missing.append("Busy data folder")
        if not cfg.get("company_name"):
            missing.append("Busy Company (click Detect)")
        if not cfg.get("starting_fy"):
            missing.append("Starting FY")
        if missing:
            messagebox.showwarning(
                APP_NAME,
                "Settings saved, but the sync service won't start until you fill:\n\n"
                + "\n".join(f"  •  {m}" for m in missing))
            return

        if self.proc and self.proc.poll() is None:
            self.stop_agent()
            self.root.after(700, self.start_agent)
            self._toast("Settings saved — sync service restarting.")
        else:
            self.root.after(200, self.start_agent)
            self._toast("Settings saved — starting sync service.")
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
                    "FlowraBusyAgent.exe.\n\n"
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
        folder = self.folder_entry.get().strip() if hasattr(self, "folder_entry") \
                    else self.config.get("busy_folder", "")
        ok, msg = check_busy_folder(folder)
        if ok:
            self.busy_var.set(f"✅ {msg}")
            messagebox.showinfo(APP_NAME,
                                 f"Busy data folder is valid:\n{folder}\n\n"
                                 f"Detected: {msg}")
        else:
            self.busy_var.set("❌ Unreachable")
            messagebox.showerror(APP_NAME,
                                 f"Not a valid Busy data folder:\n{folder}\n\n"
                                 f"Reason: {msg}\n\n"
                                 "Make sure the folder contains db.bds / db{year}.bds "
                                 "files (or DATA.ZIP).")

    # ---- Agent lifecycle -------------------------------------------------
    def start_agent(self):
        if self.proc and self.proc.poll() is None:
            return
        if not self.config.get("email") or not self.config.get("password"):
            messagebox.showwarning(APP_NAME,
                "Please login first in Settings.")
            return
        if not self.config.get("busy_folder") or not self.config.get("company_name"):
            messagebox.showwarning(APP_NAME,
                "Pick your Busy data folder and detect a company first.")
            return
        info = getattr(self, "_sub_info", None)
        if info and info.get("subscription_days_left") is not None \
                 and info["subscription_days_left"] < 0:
            messagebox.showerror(
                APP_NAME,
                "Your FLOWRA subscription has expired. The sync service is "
                "disabled.\n\nPlease use ‘Request Renewal’ on the Status tab.")
            return

        env = os.environ.copy()
        env.update({
            "BACKEND_URL":            self.config.get("backend_url", DEFAULT_BACKEND_URL),
            "FLOWRA_EMAIL":           self.config.get("email", ""),
            "FLOWRA_PASSWORD":        self.config.get("password", ""),
            "BUSY_DATA_FOLDER":       (self.config.get("company_folder")
                                        or self.config.get("busy_folder", "")),
            "BUSY_COMPANY":           self.config.get("company_name", ""),
            "BUSY_STARTING_FY":       self.config.get("starting_fy", ""),
            "SYNC_INTERVAL_MINUTES":  self.config.get("sync_interval_minutes", "20"),
            "FLOWRA_DATA_DIR":        str(APP_DIR),
            "PYTHONUNBUFFERED":       "1",
        })

        if hasattr(self, "progress_var"):
            self.progress_var.set(0)
            self.progress_pct_var.set("0%  ·  starting…")
            self.phase_var.set("Initialising")
            self.active_company_var.set(self.config.get("company_name", "(detecting…)"))

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-agent"]
        else:
            cmd = [sys.executable, resource_path(AGENT_SCRIPT), "--daemon"]

        log_path = LOG_DIR / f"busy_agent_{datetime.now():%Y%m%d}.log"
        try:
            creationflags = 0
            if os.name == "nt":
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

    def stop_agent(self):
        if not self.proc or self.proc.poll() is not None:
            self._set_running(False)
            return
        try:
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

    # Phase weights for the progress bar (Busy sync phases from the agent)
    _PHASE_WEIGHTS = [
        ("phase 1/13: syncing customers",        8),
        ("phase 2/13: syncing sundry_creditors", 5),
        ("phase 3/13: syncing inventory",       10),
        ("phase 4/13: syncing sales",           16),
        ("phase 5/13: syncing receipts",         8),
        ("phase 6/13: syncing credit_notes",     5),
        ("phase 7/13: syncing journal_vouchers", 4),
        ("phase 8/13: syncing purchase_vouchers", 12),
        ("phase 9/13: syncing debit_notes",      4),
        ("phase 10/13: syncing contra_vouchers", 4),
        ("phase 11/13: syncing stock_journals",  4),
        ("computing p&l",                        6),
        ("syncing all ledgers",                 14),
        ("full sync complete",                   0),
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

                if "logged in as" in low or "login successful" in low:
                    self.backend_var.set("Connected")
                if "detected master db" in low or "detected fy databases" in low:
                    self.busy_var.set("Reachable")
                # Active company
                for marker in ("starting full sync for", "quick sales sync",
                               "syncing company:"):
                    if marker in low:
                        try:
                            after = line.split(marker, 1)[1].strip()
                            if after:
                                self.active_company_var.set(after.split("|")[0].strip())
                        except Exception:
                            pass
                        break

                cumulative = 0
                for phase_marker, weight in self._PHASE_WEIGHTS:
                    if phase_marker in low:
                        target = cumulative + max(1, weight // 3)
                        if phase_marker == "full sync complete":
                            target = 100
                        self.progress_var.set(min(100, target))
                        pretty = phase_marker.replace("phase ", "Phase ").title()
                        self.progress_pct_var.set(
                            f"{int(self.progress_var.get())}%  ·  {pretty}")
                        self.phase_var.set(pretty)
                        break
                    cumulative += weight

                if "full sync complete" in low:
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
        sys.argv = [a for a in sys.argv if a != "--run-agent"] + ["--daemon"]
        script = resource_path(AGENT_SCRIPT)
        os.environ.setdefault(
            "FLOWRA_DATA_DIR",
            str(Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
                / "Flowra"),
        )
        globals_dict = {
            "__name__": "__main__",
            "__file__": script,
            "__builtins__": __builtins__,
        }
        with open(script, encoding="utf-8") as fh:
            exec(compile(fh.read(), script, "exec"), globals_dict)
        sys.exit(0)


def _handle_cli_flags() -> bool:
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
    global _single_instance_socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        _single_instance_socket = s
        return True
    except OSError:
        return False


def main():
    _maybe_run_agent_directly()
    if _handle_cli_flags():
        return

    if not _acquire_single_instance_lock():
        try:
            tmp = tk.Tk()
            tmp.withdraw()
            messagebox.showinfo(
                APP_NAME,
                f"{APP_NAME} is already running.\n\n"
                "Look for the blue FLOWRA icon in your Windows system "
                "tray (bottom-right corner, next to the clock).")
            tmp.destroy()
        except Exception:
            print(f"{APP_NAME} is already running. Exiting duplicate instance.")
        sys.exit(0)

    start_minimized = "--minimized" in sys.argv

    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
    except Exception:
        pass
    FlowraBusyAgentGUI(root, start_minimized=start_minimized)
    root.mainloop()


if __name__ == "__main__":
    main()
