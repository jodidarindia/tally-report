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
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from pathlib import Path

APP_NAME = "FLOWRA Tally Sync Agent"
APP_VERSION = "v9.8.9"
AGENT_SCRIPT = "tally_sync_agent_v9.py"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Flowra"
APP_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = APP_DIR / "agent.env"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Windows Registry key that auto-launches programs at user login.
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
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


# ── Tray icon (pystray + Pillow) ────────────────────────────────────────
def build_tray_icon_image():
    """Build a 64×64 in-memory PNG: blue rounded square with white "F"."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Brand blue
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(37, 99, 235, 255))
    # Big "F"
    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font = ImageFont.load_default()
    d.text((20, 7), "F", fill=(255, 255, 255, 255), font=font)
    return img


# ── Main GUI ─────────────────────────────────────────────────────────────
class FlowraAgentGUI:
    def __init__(self, root: tk.Tk, start_minimized: bool = False):
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.config = load_config()
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

        # Auto-launch sync service if credentials are saved
        if self.config.get("backend_url") and self.config.get("email") \
                and self.config.get("password"):
            self.root.after(800, self.start_agent)

        if start_minimized:
            self.root.after(50, self.hide_to_tray)

    # ---- UI construction --------------------------------------------------
    def _build_ui(self):
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("900x620")
        self.root.minsize(720, 520)
        try:
            self.root.iconbitmap(resource_path("flowra.ico"))
        except Exception:
            pass

        # Header strip
        header = tk.Frame(self.root, bg="#0F172A", height=64)
        header.pack(fill="x")
        tk.Label(header, text="FLOWRA",
                 font=("Segoe UI", 18, "bold"), fg="#FFFFFF",
                 bg="#0F172A").pack(side="left", padx=20, pady=14)
        tk.Label(header, text=f"Tally Sync Agent  ·  {APP_VERSION}",
                 font=("Segoe UI", 10), fg="#94A3B8",
                 bg="#0F172A").pack(side="left", pady=14)
        self.status_var = tk.StringVar(value="● Stopped")
        tk.Label(header, textvariable=self.status_var,
                 font=("Segoe UI", 10, "bold"), fg="#F87171",
                 bg="#0F172A").pack(side="right", padx=20, pady=14)

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=10)
        self._build_status_tab(nb)
        self._build_settings_tab(nb)
        self._build_logs_tab(nb)
        self._build_about_tab(nb)

        bar = tk.Frame(self.root, bg="#F1F5F9", height=52)
        bar.pack(fill="x", side="bottom")
        self.btn_start = tk.Button(bar, text="▶  Start Sync Service",
                                   command=self.start_agent,
                                   bg="#2563EB", fg="white", relief="flat",
                                   font=("Segoe UI", 10, "bold"),
                                   padx=16, pady=8, cursor="hand2")
        self.btn_start.pack(side="left", padx=12, pady=8)
        self.btn_stop = tk.Button(bar, text="■  Stop",
                                  command=self.stop_agent, state="disabled",
                                  bg="#E2E8F0", fg="#0F172A", relief="flat",
                                  font=("Segoe UI", 10, "bold"),
                                  padx=16, pady=8, cursor="hand2")
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

    def _build_status_tab(self, nb: ttk.Notebook):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Status  ")

        cards = tk.Frame(f, bg="#FFFFFF")
        cards.pack(fill="x", pady=(0, 16))
        for i, (label, var_attr, default) in enumerate([
            ("Tally Connection",  "tally_var",   "Not checked"),
            ("FLOWRA Backend",    "backend_var", "Not checked"),
            ("Last Sync",         "lastsync_var", "Never"),
            ("Service",           "service_var", "Stopped"),
        ]):
            card = tk.Frame(cards, bg="#F8FAFC", relief="solid", bd=1, padx=14, pady=12)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=label, fg="#64748B",
                     bg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w")
            v = tk.StringVar(value=default)
            setattr(self, var_attr, v)
            tk.Label(card, textvariable=v, fg="#0F172A",
                     bg="#F8FAFC", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(f)
        actions.pack(fill="x", pady=10)
        tk.Button(actions, text="🔄  Sync Now", command=self.sync_now,
                  bg="#10B981", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"),
                  padx=16, pady=8, cursor="hand2").pack(side="left")
        tk.Button(actions, text="🧪  Test Connection", command=self.test_connection,
                  bg="#F1F5F9", fg="#0F172A", relief="flat",
                  font=("Segoe UI", 10),
                  padx=16, pady=8, cursor="hand2").pack(side="left", padx=8)

        tk.Label(f, justify="left", fg="#64748B", bg="#FFFFFF",
                 font=("Segoe UI", 9), wraplength=820,
                 text=("This window can be closed safely — the sync service "
                       "keeps running in the system tray (look for the FLOWRA "
                       "icon near your clock). Right-click the tray icon for "
                       "quick actions.")).pack(anchor="w", pady=(20, 0))

    def _build_settings_tab(self, nb: ttk.Notebook):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Settings  ")

        rows = [
            ("FLOWRA Server URL",       "backend_url",            "https://yourcompany.flowra.in", False),
            ("Login Email",             "email",                  "you@company.com",                False),
            ("Password",                "password",               "",                                True),
            ("Tally Host",              "tally_host",             "localhost",                       False),
            ("Tally Port",              "tally_port",             "9000",                            False),
            ("Sync Interval (minutes)", "sync_interval_minutes",  "20",                              False),
        ]
        self.entries: dict[str, tk.Entry] = {}
        for i, (label, key, placeholder, is_secret) in enumerate(rows):
            tk.Label(f, text=label, fg="#334155", bg="#FFFFFF",
                     font=("Segoe UI", 10)).grid(row=i, column=0, sticky="w",
                                                  pady=8, padx=(0, 12))
            e = tk.Entry(f, font=("Segoe UI", 10), width=46,
                         show="•" if is_secret else "")
            e.insert(0, str(self.config.get(key, placeholder if not is_secret else "")))
            e.grid(row=i, column=1, sticky="w", pady=8)
            self.entries[key] = e

        # Auto-start checkbox
        self.startup_var = tk.BooleanVar(value=is_startup_registered())
        tk.Checkbutton(
            f, text="Start FLOWRA automatically when Windows starts",
            variable=self.startup_var, command=self._toggle_startup,
            font=("Segoe UI", 10), bg="#FFFFFF", fg="#0F172A",
            activebackground="#FFFFFF", anchor="w",
        ).grid(row=len(rows), column=1, sticky="w", pady=(14, 0))

        tk.Button(f, text="💾  Save Settings", command=self.save_settings,
                  bg="#2563EB", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"),
                  padx=20, pady=8, cursor="hand2").grid(
            row=len(rows) + 1, column=1, sticky="w", pady=(16, 0))

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
        try:
            import pystray
            from pystray import MenuItem as Item, Menu
        except ImportError:
            return  # pystray unavailable → app still works, just no tray

        image = build_tray_icon_image()
        if image is None:
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
        self.tray = pystray.Icon("flowra", image, APP_NAME, menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

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
        self.root.withdraw()
        # First-time hint so users know the app didn't actually quit
        if not self.config.get("tray_hint_shown"):
            self.config["tray_hint_shown"] = True
            save_config(self.config)
            if self.tray:
                try:
                    self.tray.notify(
                        "Sync continues in the background. "
                        "Right-click the tray icon for quick actions.",
                        "FLOWRA is still running",
                    )
                except Exception:
                    pass

    # ---- Actions ---------------------------------------------------------
    def save_settings(self):
        cfg = {k: e.get().strip() for k, e in self.entries.items()}
        if not cfg.get("password"):
            cfg["password"] = self.config.get("password", "")
        # Preserve flags
        for k in ("startup_prompted", "tray_hint_shown"):
            if k in self.config:
                cfg[k] = self.config[k]
        save_config(cfg)
        self.config = cfg
        # Restart the sync service so it picks up the new env vars
        if self.proc and self.proc.poll() is None:
            self.stop_agent()
            self.root.after(500, self.start_agent)
        self._toast("Settings saved.")

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

        env = os.environ.copy()
        env.update({
            "BACKEND_URL":            self.config.get("backend_url", ""),
            "FLOWRA_EMAIL":           self.config.get("email", ""),
            "FLOWRA_PASSWORD":        self.config.get("password", ""),
            "TALLY_HOST":             self.config.get("tally_host", "localhost"),
            "TALLY_PORT":             self.config.get("tally_port", "9000"),
            "SYNC_INTERVAL_MINUTES":  self.config.get("sync_interval_minutes", "20"),
            "PYTHONUNBUFFERED":       "1",
        })

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

    def stop_agent(self):
        if not self.proc or self.proc.poll() is not None:
            self._set_running(False)
            return
        try:
            if os.name == "nt":
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
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

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line == "__AGENT_EXITED__":
                    self._set_running(False)
                    self._append_log("[gui] agent process exited")
                    continue
                self._append_log(line)
                low = line.lower()
                if "last voucher date" in low or "sync complete" in low:
                    self.lastsync_var.set(datetime.now().strftime("%d %b %H:%M"))
                if "tally responded" in low or "ping ok" in low:
                    self.tally_var.set("✅ Connected")
                if "login successful" in low or "authenticated" in low:
                    self.backend_var.set("✅ Connected")
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
        sys.argv = [a for a in sys.argv if a != "--run-agent"]
        script = resource_path(AGENT_SCRIPT)
        with open(script, encoding="utf-8") as fh:
            exec(compile(fh.read(), script, "exec"), {"__name__": "__main__"})
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


def main():
    _maybe_run_agent_directly()
    if _handle_cli_flags():
        return

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
