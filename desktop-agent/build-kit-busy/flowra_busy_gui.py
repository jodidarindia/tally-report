"""FLOWRA Busy Sync Agent — modern GUI (v1.1)

Ports the visual language of the Tally v9.8.29 GUI to the Busy agent:
- Navy header with the FLOWRA logo and title
- Logged-in-user pill (name · tenant · plan)
- Amber CTA buttons for high-signal actions
- Tabbed body (Dashboard · Sync · Logs · Settings)
- Status bar footer with connectivity dots

This file wraps the existing FlowraBusySyncAgent class (business logic
untouched). Running `python flowra_busy_gui.py` launches the app; without
this file, `python flowra_busy_agent.py` still works and drops to the
legacy Tk shell — so we have a safety net.
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from datetime import datetime, timezone, timedelta

# Import all the business logic from the sibling agent module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flowra_busy_agent import (  # noqa: E402
    APP_NAME, VERSION, AGENT_TAG, DEFAULT_BACKEND_URL, IST,
    FlowraBusySyncAgent, now_ist_display,
)

# ── Brand palette (must match Tally GUI) ─────────────────────────────────
NAVY  = "#0F1B4C"
BLUE  = "#2563EB"
AMBER = "#F59E0B"
PAPER = "#FFFFFF"
SOFT  = "#F0F4FF"
GREY  = "#64748B"
DARK  = "#0F172A"
INK   = "#1E293B"
MUTED = "#94A3B8"
OK    = "#10B981"
BAD   = "#DC2626"

FONT_HEAD = ("Segoe UI", 16, "bold")
FONT_SUB  = ("Segoe UI", 10)
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)
FONT_PILL = ("Segoe UI", 9, "bold")


def _resource(name: str) -> str:
    """Locate a bundled asset (works both in dev and inside a PyInstaller
    single-file exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def _load_logo(size: int = 40):
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return None
    for candidate in ("flowra_logo.png", "flowra.ico"):
        p = _resource(candidate)
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGBA")
                im.thumbnail((size, size), Image.LANCZOS)
                return ImageTk.PhotoImage(im)
            except Exception:
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────
class BusyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.agent = FlowraBusySyncAgent(status_callback=self._on_status)
        self._log_q: "queue.Queue[str]" = queue.Queue()
        self._logo_ref = None  # keep image alive

        # Window chrome
        root.title(f"{APP_NAME} {VERSION}")
        root.geometry("1120x680")
        root.minsize(940, 580)
        try:
            root.iconbitmap(_resource("flowra.ico"))
        except Exception:
            pass
        root.configure(bg=PAPER)

        # ttk theming
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Nav.TNotebook", background=PAPER, borderwidth=0)
        style.configure("Nav.TNotebook.Tab",
                        padding=(18, 8),
                        font=("Segoe UI", 10, "bold"),
                        background=SOFT,
                        foreground=INK)
        style.map("Nav.TNotebook.Tab",
                  background=[("selected", PAPER)],
                  foreground=[("selected", BLUE)])
        style.configure("TFrame", background=PAPER)
        style.configure("Card.TFrame", background=SOFT)
        style.configure("TLabel", background=PAPER, foreground=INK,
                        font=FONT_BODY)
        style.configure("Muted.TLabel", background=PAPER, foreground=MUTED,
                        font=("Segoe UI", 9))
        style.configure("CardHead.TLabel", background=SOFT, foreground=NAVY,
                        font=("Segoe UI", 10, "bold"))
        style.configure("Cta.TButton", padding=(16, 8),
                        font=("Segoe UI", 10, "bold"))

        self._build_header()
        self._build_body()
        self._build_footer()
        self._pump_log_queue()

        # Boot sequence — auto-restore session if we have a saved token
        self.root.after(200, self._restore_session_if_any)

    # ── HEADER ───────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=NAVY, height=64)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)

        # Logo
        self._logo_ref = _load_logo(size=40)
        if self._logo_ref:
            tk.Label(hdr, image=self._logo_ref, bg=NAVY).pack(
                side="left", padx=(16, 10), pady=12)

        # Title + subtitle
        title_wrap = tk.Frame(hdr, bg=NAVY)
        title_wrap.pack(side="left", pady=10)
        tk.Label(title_wrap, text="FLOWRA", fg=PAPER, bg=NAVY,
                 font=("Segoe UI", 16, "bold")).pack(side="top", anchor="w")
        tk.Label(title_wrap, text=f"Busy Sync Agent  ·  v{VERSION}",
                 fg="#C7D2FE", bg=NAVY,
                 font=("Segoe UI", 9)).pack(side="top", anchor="w")

        # Amber accent under header
        tk.Frame(self.root, bg=AMBER, height=3).pack(side="top", fill="x")

        # User pill on the right of header
        self._user_frame = tk.Frame(hdr, bg=NAVY)
        self._user_frame.pack(side="right", padx=16, pady=12)
        self.user_pill = tk.Label(
            self._user_frame, text="  Not signed in  ",
            bg="#1E3A8A", fg=PAPER,
            font=FONT_PILL, padx=10, pady=4,
        )
        self.user_pill.pack(side="right")

    def _update_user_pill(self):
        api = getattr(self.agent, "api", None)
        if api and getattr(api, "token", None):
            name = api.name or self.agent.config.get("username", "—")
            plan = (api.plan or "free").upper()
            text = f"  {name}  ·  {plan}  "
            self.user_pill.configure(text=text, bg="#065F46")  # green
        else:
            self.user_pill.configure(text="  Not signed in  ", bg="#1E3A8A")

    # ── BODY ─────────────────────────────────────────────────────────────
    def _build_body(self):
        nb = ttk.Notebook(self.root, style="Nav.TNotebook")
        nb.pack(side="top", fill="both", expand=True, padx=12, pady=(10, 6))
        self.nb = nb

        self.tab_dash = ttk.Frame(nb, padding=16)
        self.tab_sync = ttk.Frame(nb, padding=16)
        self.tab_logs = ttk.Frame(nb, padding=16)
        self.tab_sets = ttk.Frame(nb, padding=16)
        nb.add(self.tab_dash, text="  Dashboard  ")
        nb.add(self.tab_sync, text="  Sync  ")
        nb.add(self.tab_logs, text="  Logs  ")
        nb.add(self.tab_sets, text="  Settings  ")

        self._build_dashboard(self.tab_dash)
        self._build_sync_tab(self.tab_sync)
        self._build_logs_tab(self.tab_logs)
        self._build_settings_tab(self.tab_sets)

    # ── DASHBOARD ────────────────────────────────────────────────────────
    def _build_dashboard(self, parent):
        # Row of 3 metric cards
        row = tk.Frame(parent, bg=PAPER)
        row.pack(side="top", fill="x")
        self.card_user = self._metric_card(row, "Signed in as", "—")
        self.card_folder = self._metric_card(row, "Busy data folder", "—")
        self.card_last = self._metric_card(row, "Last full sync", "Never")
        for c in (self.card_user, self.card_folder, self.card_last):
            c["frame"].pack(side="left", fill="x", expand=True, padx=(0, 12))

        # Company table
        wrap = tk.LabelFrame(parent, text="  Companies detected  ",
                             font=("Segoe UI", 10, "bold"),
                             fg=NAVY, bg=PAPER, padx=8, pady=8, bd=1,
                             relief="solid")
        wrap.pack(side="top", fill="both", expand=True, pady=(14, 0))

        cols = ("company", "financial_year", "last_full_sync")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=8)
        self.tree.heading("company", text="Company")
        self.tree.heading("financial_year", text="Financial Year")
        self.tree.heading("last_full_sync", text="Last Full Sync")
        self.tree.column("company", width=340, anchor="w")
        self.tree.column("financial_year", width=140, anchor="center")
        self.tree.column("last_full_sync", width=200, anchor="center")
        self.tree.pack(side="top", fill="both", expand=True)

        # CTA row
        cta = tk.Frame(parent, bg=PAPER)
        cta.pack(side="top", fill="x", pady=(12, 0))
        self._amber_button(cta, "Refresh companies",
                           self._on_refresh_companies).pack(side="left")
        self._ghost_button(cta, "Open logs folder",
                           self._on_open_logs_folder).pack(side="left", padx=(8, 0))

    def _metric_card(self, parent, label, value):
        f = tk.Frame(parent, bg=SOFT, padx=14, pady=12,
                     highlightthickness=1, highlightbackground="#DBEAFE")
        tk.Label(f, text=label.upper(), fg=BLUE, bg=SOFT,
                 font=("Segoe UI", 8, "bold")).pack(side="top", anchor="w")
        val = tk.Label(f, text=value, fg=NAVY, bg=SOFT,
                       font=("Segoe UI", 13, "bold"))
        val.pack(side="top", anchor="w", pady=(4, 0))
        return {"frame": f, "value": val}

    def _amber_button(self, parent, text, cmd):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=AMBER, fg=NAVY, activebackground="#F97316",
                      activeforeground=NAVY,
                      bd=0, padx=16, pady=8, cursor="hand2",
                      font=("Segoe UI", 10, "bold"))
        return b

    def _ghost_button(self, parent, text, cmd):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=SOFT, fg=NAVY, activebackground="#DBEAFE",
                      activeforeground=NAVY,
                      bd=0, padx=14, pady=8, cursor="hand2",
                      font=("Segoe UI", 10))
        return b

    # ── SYNC TAB ─────────────────────────────────────────────────────────
    def _build_sync_tab(self, parent):
        wrap = tk.Frame(parent, bg=PAPER)
        wrap.pack(side="top", fill="both", expand=True)

        tk.Label(wrap, text="Pick a company + FY, then run sync",
                 bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 11, "bold")).pack(side="top", anchor="w")
        tk.Label(wrap, text="Full sync scans every ledger, voucher and item. "
                            "Quick sync only pulls new sales since the last cycle.",
                 bg=PAPER, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="top", anchor="w",
                                            pady=(0, 12))

        form = tk.Frame(wrap, bg=PAPER)
        form.pack(side="top", fill="x")

        tk.Label(form, text="Company", bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0,
                                                    sticky="w", padx=(0, 6))
        self.company_var = tk.StringVar()
        self.company_combo = ttk.Combobox(form, textvariable=self.company_var,
                                          width=44, state="readonly")
        self.company_combo.grid(row=0, column=1, sticky="ew",
                                padx=(0, 20), pady=4)

        tk.Label(form, text="FY", bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=2,
                                                    sticky="w", padx=(0, 6))
        self.fy_var = tk.StringVar()
        self.fy_combo = ttk.Combobox(form, textvariable=self.fy_var,
                                     width=14, state="readonly")
        self.fy_combo.grid(row=0, column=3, sticky="w", pady=4)

        form.columnconfigure(1, weight=1)

        # CTA row
        cta = tk.Frame(wrap, bg=PAPER)
        cta.pack(side="top", fill="x", pady=(18, 0))
        self._amber_button(cta, "▶  Run Full Sync",
                           self._on_run_full).pack(side="left")
        self._ghost_button(cta, "Quick Sales Sync",
                           self._on_run_quick).pack(side="left", padx=(10, 0))
        self._ghost_button(cta, "Force Full Sync (bypass 7-day skip)",
                           self._on_run_full_force).pack(side="left",
                                                         padx=(10, 0))

        # Progress
        prog_wrap = tk.LabelFrame(wrap, text="  Progress  ",
                                  font=("Segoe UI", 10, "bold"),
                                  fg=NAVY, bg=PAPER, padx=10, pady=10,
                                  bd=1, relief="solid")
        prog_wrap.pack(side="top", fill="both", expand=True, pady=(18, 0))
        self.progress_var = tk.StringVar(value="Idle")
        tk.Label(prog_wrap, textvariable=self.progress_var,
                 bg=PAPER, fg=INK, font=FONT_MONO,
                 justify="left", anchor="w",
                 wraplength=1000).pack(side="top", fill="both", expand=True)

    # ── LOGS TAB ────────────────────────────────────────────────────────
    def _build_logs_tab(self, parent):
        top = tk.Frame(parent, bg=PAPER)
        top.pack(side="top", fill="x")
        tk.Label(top, text="Live log tail  (also mirrored to flowra_busy_agent.log)",
                 bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 10, "bold")).pack(side="left", anchor="w")
        self._ghost_button(top, "Clear",
                           self._on_clear_logs).pack(side="right")

        self.log_widget = scrolledtext.ScrolledText(
            parent, bg="#0F172A", fg="#CBD5E1",
            insertbackground=PAPER, font=FONT_MONO,
            wrap="none", padx=8, pady=8,
        )
        self.log_widget.pack(side="top", fill="both", expand=True,
                             pady=(8, 0))

        self._install_log_handler()

    def _install_log_handler(self):
        """Wire a logging.Handler that pipes into the on-screen text widget."""
        import logging
        q = self._log_q

        class QueueHandler(logging.Handler):
            def emit(self, record):
                try:
                    q.put_nowait(self.format(record))
                except Exception:
                    pass

        h = QueueHandler()
        h.setLevel(logging.INFO)
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s",
                                         datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(h)

    def _pump_log_queue(self):
        # Drain up to 200 records per tick so UI stays responsive under load
        drained = 0
        while drained < 200:
            try:
                line = self._log_q.get_nowait()
            except queue.Empty:
                break
            self.log_widget.insert("end", line + "\n")
            self.log_widget.see("end")
            drained += 1
        self.root.after(150, self._pump_log_queue)

    # ── SETTINGS TAB ────────────────────────────────────────────────────
    def _build_settings_tab(self, parent):
        wrap = tk.Frame(parent, bg=PAPER)
        wrap.pack(side="top", fill="both", expand=True)

        grid = tk.Frame(wrap, bg=PAPER)
        grid.pack(side="top", fill="x")

        # Backend URL
        tk.Label(grid, text="FLOWRA Backend URL", bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0,
                                                    sticky="w", pady=4)
        self.url_var = tk.StringVar(
            value=self.agent.config.get("backend_url", DEFAULT_BACKEND_URL))
        tk.Entry(grid, textvariable=self.url_var, width=54,
                 font=FONT_BODY).grid(row=0, column=1, sticky="ew", pady=4)

        # Busy data folder
        tk.Label(grid, text="Busy data folder", bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 9, "bold")).grid(row=1, column=0,
                                                    sticky="w", pady=4)
        self.folder_var = tk.StringVar(
            value=self.agent.config.get("busy_folder", ""))
        fwrap = tk.Frame(grid, bg=PAPER)
        fwrap.grid(row=1, column=1, sticky="ew", pady=4)
        tk.Entry(fwrap, textvariable=self.folder_var, width=46,
                 font=FONT_BODY).pack(side="left", fill="x", expand=True)
        self._ghost_button(fwrap, "Browse…",
                           self._on_browse_folder).pack(side="left",
                                                        padx=(6, 0))

        # Login block
        tk.Label(grid, text="Email", bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 9, "bold")).grid(row=2, column=0,
                                                    sticky="w", pady=(18, 4))
        self.email_var = tk.StringVar(
            value=self.agent.config.get("username", ""))
        tk.Entry(grid, textvariable=self.email_var, width=44,
                 font=FONT_BODY).grid(row=2, column=1, sticky="ew",
                                      pady=(18, 4))

        tk.Label(grid, text="Password", bg=PAPER, fg=NAVY,
                 font=("Segoe UI", 9, "bold")).grid(row=3, column=0,
                                                    sticky="w", pady=4)
        self.pwd_var = tk.StringVar()
        tk.Entry(grid, textvariable=self.pwd_var, width=44, show="•",
                 font=FONT_BODY).grid(row=3, column=1, sticky="ew", pady=4)

        grid.columnconfigure(1, weight=1)

        # CTA row
        cta = tk.Frame(wrap, bg=PAPER)
        cta.pack(side="top", fill="x", pady=(18, 0))
        self._amber_button(cta, "Save & Connect",
                           self._on_save_and_connect).pack(side="left")
        self._ghost_button(cta, "Sign out",
                           self._on_signout).pack(side="left", padx=(10, 0))

        # Info block
        info = tk.Frame(wrap, bg=SOFT, padx=12, pady=10)
        info.pack(side="top", fill="x", pady=(18, 0))
        tk.Label(info,
                 text=f"Agent tag: {AGENT_TAG}  ·  IST timezone  ·  "
                      f"7-day full-sync skip window active",
                 bg=SOFT, fg=NAVY, font=("Segoe UI", 9)).pack(side="left")

    # ── FOOTER ───────────────────────────────────────────────────────────
    def _build_footer(self):
        bar = tk.Frame(self.root, bg=SOFT, height=28)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)
        self.status_lbl = tk.Label(bar, text="Ready.",
                                   bg=SOFT, fg=INK,
                                   font=("Segoe UI", 9), anchor="w")
        self.status_lbl.pack(side="left", padx=12)
        self.time_lbl = tk.Label(bar, text=now_ist_display(),
                                 bg=SOFT, fg=MUTED, font=("Segoe UI", 9))
        self.time_lbl.pack(side="right", padx=12)
        self._tick_clock()

    def _tick_clock(self):
        self.time_lbl.configure(text=now_ist_display())
        self.root.after(1000, self._tick_clock)

    # ── STATE / EVENTS ───────────────────────────────────────────────────
    def _on_status(self, msg: str):
        # Called from background threads — schedule on UI thread
        self.root.after(0, lambda: self.status_lbl.configure(
            text=(msg or "")[:180]))
        self.root.after(0, lambda: self.progress_var.set(
            (self.progress_var.get() + "\n" + msg) if self.progress_var.get()
            != "Idle" else msg))

    def _restore_session_if_any(self):
        # v1.1 — the current agent doesn't auto-restore an old JWT; we simply
        # refresh the UI. Users click "Save & Connect" to sign in.
        self._update_user_pill()
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        api = getattr(self.agent, "api", None)
        name = (api.name if api else "") or self.agent.config.get("username", "—")
        self.card_user["value"].configure(text=name or "—")
        self.card_folder["value"].configure(
            text=self.agent.config.get("busy_folder", "—") or "—")

        # Companies + FY selectors from the agent's authoritative helpers
        try:
            companies = self.agent.get_companies() if hasattr(self.agent, "get_companies") else []
        except Exception:
            companies = []
        # Store the id lookup for _sync_worker.
        self._company_id_map = {c.get("company_name") or c.get("company_id"): c.get("company_id")
                                for c in companies}
        self.company_combo["values"] = list(self._company_id_map.keys())
        if self._company_id_map:
            first = next(iter(self._company_id_map.keys()))
            if not self.company_var.get():
                self.company_var.set(first)

        try:
            fys = self.agent.get_fys() if hasattr(self.agent, "get_fys") else []
        except Exception:
            fys = []
        self.fy_combo["values"] = fys
        if fys and not self.fy_var.get():
            self.fy_var.set(fys[-1])

        # Populate tree
        for r in self.tree.get_children():
            self.tree.delete(r)
        state = getattr(self.agent, "state", {}) or {}
        for cid, cstate in state.items():
            last = cstate.get("last_full_sync") or "—"
            if last and len(last) > 19:
                last = last[:19].replace("T", " ")
            self.tree.insert("", "end", values=(
                cstate.get("company_name") or cid,
                cstate.get("last_fy") or "—",
                last,
            ))

        # Last full-sync metric
        latest = None
        for c in state.values():
            ts = c.get("last_full_sync")
            if ts and (not latest or ts > latest):
                latest = ts
        if latest:
            self.card_last["value"].configure(text=latest[:19].replace("T", " "))
        else:
            self.card_last["value"].configure(text="Never")

    def _on_refresh_companies(self):
        threading.Thread(target=self._refresh_companies_worker,
                         daemon=True).start()

    def _refresh_companies_worker(self):
        self._on_status("Refreshing companies & FY list…")
        # Re-init the extractor if we have a folder configured; that
        # triggers FY database discovery on disk.
        try:
            folder = self.agent.config.get("busy_folder", "")
            if folder and hasattr(self.agent, "set_busy_folder"):
                self.agent.set_busy_folder(folder)
        except Exception as e:
            self._on_status(f"Folder scan failed: {e}")
        self.root.after(0, self._refresh_dashboard)
        self._on_status("Refresh complete.")

    def _on_open_logs_folder(self):
        path = os.path.abspath(".")
        try:
            os.startfile(path)  # Windows
        except Exception:
            try:
                import subprocess
                subprocess.Popen(["xdg-open", path])
            except Exception:
                messagebox.showinfo("Logs", f"Logs are in:\n{path}")

    def _on_browse_folder(self):
        folder = filedialog.askdirectory(title="Pick your Busy data folder")
        if folder:
            self.folder_var.set(folder)

    def _on_save_and_connect(self):
        cfg = self.agent.config
        cfg["backend_url"] = self.url_var.get().strip() or DEFAULT_BACKEND_URL
        cfg["busy_folder"] = self.folder_var.get().strip()
        cfg["username"] = self.email_var.get().strip()
        self.agent.save_config()

        threading.Thread(target=self._connect_worker,
                         daemon=True).start()

    def _connect_worker(self):
        email = self.email_var.get().strip()
        pwd = self.pwd_var.get()
        if not email or not pwd:
            self._on_status("Enter email and password to sign in")
            return
        try:
            ok = self.agent.login(email, pwd)
        except Exception as e:
            self._on_status(f"Login failed: {e}")
            return
        if not ok:
            self._on_status("Login rejected by server")
            return
        # Clear password from memory immediately after use
        self.root.after(0, lambda: self.pwd_var.set(""))
        try:
            if hasattr(self.agent, "detect_databases"):
                self.agent.detect_databases()
        except Exception:
            pass
        self.root.after(0, self._update_user_pill)
        self.root.after(0, self._refresh_dashboard)

    def _on_signout(self):
        try:
            self.agent.logout()
        except Exception:
            pass
        self.root.after(0, self._update_user_pill)
        self.root.after(0, self._refresh_dashboard)
        self._on_status("Signed out")

    def _sync_worker(self, force: bool, quick: bool):
        cname = self.company_var.get()
        fy = self.fy_var.get()
        if not cname or not fy:
            self._on_status("Pick a company and FY first")
            return
        # Resolve company_id from detected list
        cid = None
        for c in getattr(self.agent, "detected_companies", []) or []:
            if c.get("name") == cname:
                cid = c.get("id") or c.get("name")
                break
        if not cid:
            self._on_status(f"Company id not resolved for {cname!r}")
            return
        try:
            if quick:
                self.agent.run_quick_sales_sync(cid, cname, fy)
            else:
                self.agent.run_full_sync(cid, cname, fy, force=force)
        except TypeError:
            # Older signature without force= kwarg
            if quick:
                self.agent.run_quick_sales_sync(cid, cname, fy)
            else:
                self.agent.run_full_sync(cid, cname, fy)
        except Exception as e:
            self._on_status(f"Sync failed: {e}")
        self.root.after(0, self._refresh_dashboard)

    def _on_run_full(self):
        self.progress_var.set("Idle")
        threading.Thread(target=lambda: self._sync_worker(False, False),
                         daemon=True).start()

    def _on_run_full_force(self):
        self.progress_var.set("Idle")
        threading.Thread(target=lambda: self._sync_worker(True, False),
                         daemon=True).start()

    def _on_run_quick(self):
        self.progress_var.set("Idle")
        threading.Thread(target=lambda: self._sync_worker(False, True),
                         daemon=True).start()

    def _on_clear_logs(self):
        self.log_widget.delete("1.0", "end")


def main():
    root = tk.Tk()
    _ = BusyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
