#!/usr/bin/env python3
"""
FLOWRA Busy Sync Agent v1.0
Syncs data from Busy Accounting Software (.bds / MS Access) to FLOWRA cloud.

RAM Optimization Strategy:
- Row-by-row cursor iteration (never fetchall on large tables)
- Chunked uploads (500 vouchers at a time)
- Generator-based data extraction
- Explicit gc.collect() after each sync phase
- No in-memory caching of full datasets

Requirements (Windows):
- Python 3.9+
- pyodbc (with Microsoft Access Database Engine ODBC driver)
- requests
- cryptography (for local config encryption)

v1.0 Features:
- Login-based auth with FLOWRA backend
- Busy data folder detection (DATA.ZIP → .bds files)
- FY auto-discovery from db{year}.bds filenames
- All voucher types: Sales, Receipts, Credit Notes, Journals, Purchase, Debit Notes, Contra, Stock Journals
- Master data: Customers, Creditors, Inventory, All Ledgers, Account Groups
- P&L computation from ledger groups
- Deletion reconciliation (manifest-based)
- Command queue polling (resync/delete from web UI)
- Dual schedule: 5-min quick sales + 20-min full sync
- IST timezone for all timestamps
- Encrypted local config
- Light-themed GUI (tkinter)
- System tray support
"""

import os
import sys
import json
import time
import uuid
import hashlib
import logging
import zipfile
import csv
import io
import gc
import subprocess
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Generator
from collections import defaultdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.5.7"
AGENT_TAG = "busy-1.5.7-invoice-fields"
APP_NAME = "FLOWRA Busy Sync Agent"
IST = timezone(timedelta(hours=5, minutes=30))
CONFIG_FILE = "flowra_busy_config.json"
SYNC_STATE_FILE = "sync_state_busy.json"
CHUNK_SIZE = 500          # vouchers per API call — keeps RAM low
MAX_ROWS_PER_BATCH = 1000 # max rows to hold in memory at once
DEFAULT_BACKEND_URL = "https://insights.flowralive.in"
# Full-sync short-circuit window — restart within N days on the same
# company skips the full month-by-month scan. Mirrors the Tally v9.8.29
# AlterID skip logic; Busy doesn't have AlterID so we use a time gate.
FULL_SKIP_WINDOW_DAYS = 7

BUSY_VCHTYPE_MAP = {
    1: "cash_receipt", 2: "cash_payment", 3: "bank_receipt", 4: "bank_payment",
    5: "journal", 6: "contra", 7: "purchase", 8: "purchase_return",
    9: "sales", 10: "sales_return", 11: "debit_note", 12: "credit_note",
    13: "material_receipt", 14: "material_issue", 15: "stock_journal",
    16: "purchase_order", 17: "sales_order",
}

ACCOUNT_GROUP_MAP = {
    101: "capital", 102: "current_assets", 103: "current_liabilities",
    104: "fixed_assets", 105: "investments", 106: "loans_liability",
    107: "misc_expense", 108: "profit_loss_ac", 109: "revenue",
    110: "suspense", 111: "cash", 112: "bank", 113: "securities_deposits",
    114: "loans_advances_asset", 115: "stock_in_hand", 116: "sundry_debtors",
    117: "sundry_creditors", 118: "duties_taxes", 119: "provisions",
    120: "secured_loans", 121: "unsecured_loans", 122: "purchase",
    123: "sale", 124: "direct_expense", 125: "indirect_expense",
    126: "direct_income", 127: "indirect_income", 128: "bank_od",
    129: "reserves",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("flowra_busy")


# ---------------------------------------------------------------------------
# Config Persistence (simple JSON, no heavy crypto to save RAM)
# ---------------------------------------------------------------------------
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            return json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    Path(CONFIG_FILE).write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def load_sync_state() -> dict:
    if os.path.exists(SYNC_STATE_FILE):
        try:
            return json.loads(Path(SYNC_STATE_FILE).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_sync_state(state: dict):
    Path(SYNC_STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")


def now_ist() -> str:
    return datetime.now(IST).isoformat()


def now_ist_display() -> str:
    return datetime.now(IST).strftime("%d-%b-%Y %I:%M %p IST")


# ---------------------------------------------------------------------------
# Busy Database Reader — LOW RAM, cursor-based
# ---------------------------------------------------------------------------
class _OLEDBConnectionAdapter:
    """v1.4 — thin shim so an ADODB.Connection object satisfies the same
    `.cursor().execute(sql)` + `.fetchone()` contract as a pyodbc connection.

    ADO's native API is `Recordset.Open(sql, conn)` → row-by-row via
    `MoveNext()`. This adapter presents a pyodbc-shaped facade so
    downstream code (iter_rows / count_rows) needs zero branching."""

    def __init__(self, ado_conn):
        self._ado = ado_conn

    def cursor(self):
        return _OLEDBCursor(self._ado)

    def close(self):
        try:
            self._ado.Close()
        except Exception:
            pass


class _OLEDBCursor:
    def __init__(self, ado_conn):
        self._ado = ado_conn
        self._rs = None
        self.description = None

    def execute(self, sql: str):
        import win32com.client
        self._rs = win32com.client.Dispatch("ADODB.Recordset")
        # 0 = adOpenForwardOnly, 1 = adLockReadOnly, 1 = adCmdText
        self._rs.Open(sql, self._ado, 0, 1, 1)
        if self._rs.Fields.Count > 0:
            self.description = [
                (self._rs.Fields.Item(i).Name, None, None, None, None, None, None)
                for i in range(self._rs.Fields.Count)
            ]
        return self

    def fetchone(self):
        if not self._rs or self._rs.EOF:
            return None
        row = tuple(
            self._rs.Fields.Item(i).Value
            for i in range(self._rs.Fields.Count)
        )
        self._rs.MoveNext()
        return row

    def close(self):
        try:
            if self._rs:
                self._rs.Close()
        except Exception:
            pass


class BusyDBReader:
    """Reads Busy .bds (MS Access/Jet) files with minimal RAM usage.

    On Windows: uses pyodbc with MS Access ODBC driver.
    On Linux (dev): uses mdb-export CLI tool (streaming CSV).
    """

    def __init__(self, bds_path: str):
        self.bds_path = bds_path
        self.is_windows = sys.platform == "win32"
        self._conn = None
        self._connection_method = None   # "AccessParser" | "OLE DB" | "ODBC"
        # v1.5.1 — access_parser is a pure-Python JET4 reader that
        # bypasses the Access driver entirely. Confirmed to open licensed
        # Busy 21 .bds files WITHOUT any password (the file structure is
        # readable at the JET4 level; Busy's password enforcement lives
        # only in the ODBC/OLE DB layer). Populated on first successful
        # `_try_access_parser()` call and cached table-by-table thereafter.
        self._ap = None                     # AccessParser instance
        self._ap_row_cache: Dict[str, List[Dict]] = {}

    def _try_access_parser(self):
        """v1.5.1 — pure-Python JET4 read path. Runs on ANY OS, needs no
        driver install, and works around Windows-side password / registry
        temp-DSN errors ("Unable to open registry key Temporary (volatile)
        Ace DSN", "Not a valid password -1905"). If the library isn't
        bundled OR the file layout isn't parseable, returns None and the
        caller falls through to OLE DB → ODBC."""
        if self._ap is not None:
            return self._ap
        try:
            from access_parser import AccessParser  # pip: access-parser
        except ImportError:
            logger.info("  access_parser unavailable — rebuild the EXE "
                        "with the updated requirements.txt to enable "
                        "the pure-Python JET4 reader")
            return None
        try:
            self._ap = AccessParser(self.bds_path)
            self._connection_method = "AccessParser"
            logger.info(
                "  Busy DB opened via pure-Python access_parser — no "
                "driver / password needed")
            return self._ap
        except Exception as e:
            logger.info(f"  access_parser open failed: {e}")
            return None

    def _load_table_via_ap(self, table: str) -> List[Dict]:
        """Convert access_parser's columnar {col: [v0, v1, …]} shape into
        an ordered list of row dicts, cached per table so repeated
        iter_rows() calls stay O(1).

        v1.5.1 — every value is stringified (or left None) to match the
        mdb-export CSV shape the rest of the extractor was built for.
        Numeric downstream users still work because `float("116996.0")`
        and `int("6003")` succeed. This keeps the string comparisons in
        `_load_code_map` (`mtype == "1"`) etc. working regardless of the
        underlying driver."""
        if table in self._ap_row_cache:
            return self._ap_row_cache[table]
        col_data = self._ap.parse_table(table)
        if not col_data:
            self._ap_row_cache[table] = []
            return []
        cols = list(col_data.keys())
        row_count = max((len(col_data[c]) for c in cols), default=0)
        rows: List[Dict] = []
        for i in range(row_count):
            row = {}
            for c in cols:
                col = col_data[c]
                v = col[i] if i < len(col) else None
                if v is None:
                    row[c] = None
                elif isinstance(v, (bytes, bytearray)):
                    try:
                        row[c] = v.decode("utf-8", errors="replace")
                    except Exception:
                        row[c] = ""
                elif isinstance(v, float):
                    # Preserve numeric strings without trailing zeros
                    # that float("6003.0") would parse back to 6003.0 –
                    # good for both string compare and float() consumers.
                    if v.is_integer():
                        row[c] = str(int(v))
                    else:
                        row[c] = str(v)
                else:
                    row[c] = str(v)
            rows.append(row)
        self._ap_row_cache[table] = rows
        return rows

    # v1.3.1 — Busy encrypts every .bds file with a proprietary password.
    # Without PWD=... the Access ODBC driver returns error -1905
    # "Not a valid password". Try a fallback chain of the passwords that
    # ship with each Busy generation. If none work, ask the user to set
    # BUSY_DB_PASSWORD in the environment (or Settings tab).
    _KNOWN_BUSY_PASSWORDS = (
        "bs21DBFile",   # Busy 21
        "Bus1Wor$1D",   # Busy 18/19
        "busyww",       # older builds
        "busy",         # community-reported
        "",              # blank — some early builds
    )

    # v1.4 — Busy Solutions' official OLEDB provider (BSSData) is our
    # preferred connection path. It handles the internal file encryption
    # itself, so we ONLY need the user's normal Busy login (username +
    # password) — the same one they type when opening BusyWin.
    #
    # If the provider is not registered on the host (Busy Basic edition,
    # Demo build, or the Data-Connectivity add-on wasn't purchased) we
    # fall back to the v1.3 password-fallback ODBC path.
    _OLEDB_PROVIDERS = (
        "BSSData.6.0",
        "BSSData.5.0",
        "BSSData.4.0",
    )

    def _try_oledb(self):
        """Attempt COM/OLE DB connection via pywin32. Returns a live
        connection or None if unavailable. Windows-only."""
        if not self.is_windows:
            return None
        try:
            import win32com.client
        except ImportError:
            logger.info("  OLE DB unavailable — pywin32 not installed")
            return None

        busy_user = os.environ.get("BUSY_USER", "").strip()
        busy_pwd = os.environ.get("BUSY_LOGIN_PASSWORD", "").strip()
        # v1.4.1 — OLE DB provider's Company= param now lives on its own env
        # var so it can never collide with BUSY_COMPANY (which the daemon
        # uses as the sync identifier and validates on boot).
        company = (os.environ.get("BUSY_OLEDB_COMPANY", "").strip()
                   or os.environ.get("BUSY_COMPANY", "").strip())
        data_dir = os.path.dirname(self.bds_path)

        last_err = None
        for provider in self._OLEDB_PROVIDERS:
            try:
                conn = win32com.client.Dispatch("ADODB.Connection")
                conn_str = (
                    f"Provider={provider};"
                    f"Data Source={data_dir};"
                )
                if company:
                    conn_str += f"Company={company};"
                if busy_user:
                    conn_str += f"User Id={busy_user};"
                if busy_pwd:
                    conn_str += f"Password={busy_pwd};"
                conn.Open(conn_str)
                logger.info(
                    f"  Busy DB opened via OLE DB (provider={provider}, "
                    f"user={'set' if busy_user else 'default'})")
                return _OLEDBConnectionAdapter(conn)
            except Exception as e:
                last_err = e
                # com_error / pywintypes.com_error means provider not
                # registered → try the next version
                continue
        logger.info(f"  OLE DB providers all failed. Last: {last_err}")
        return None

    def _get_connection(self):
        """Lazy connection — access_parser first (v1.5.1 pure-Python
        JET4, no driver / no password), then OLE DB, then ODBC."""
        if self._conn or self._ap:
            return self._conn or self._ap

        # ── Try pure-Python access_parser first (v1.5.1) ─────────────
        # This is now the preferred strategy because it side-steps the
        # entire Windows driver + password + registry-DSN mess. It also
        # runs on Linux for dev/testing without mdbtools installed.
        ap = self._try_access_parser()
        if ap is not None:
            return ap

        if not self.is_windows:
            return None

        # ── Try OLE DB (v1.4) ────────────────────────────────────────
        oledb = self._try_oledb()
        if oledb is not None:
            self._conn = oledb
            self._connection_method = "OLE DB"
            return self._conn

        # ── Fall back to ODBC + password chain (v1.3.1) ──────────
        # v1.5.1 — added `Exclusive=1;` to bypass "Unable to open
        # registry key Temporary (volatile) Ace DSN" errors that hit
        # when the ODBC driver can't write its temp DSN under HKLM
        # (Windows Server / service accounts / restricted users).
        try:
            import pyodbc
        except ImportError as e:
            raise RuntimeError(
                "pyodbc is not bundled in this build. Please rebuild "
                "FlowraBusyAgent.exe with build.bat — the fresh build "
                "includes pyodbc automatically. If you already rebuilt, "
                "reinstall the .exe (delete %LOCALAPPDATA%\\Flowra "
                "cache first).") from e

        # 1) Explicit override wins.
        pwd_env = os.environ.get("BUSY_DB_PASSWORD", "").strip()
        candidates = [pwd_env] if pwd_env else list(self._KNOWN_BUSY_PASSWORDS)

        last_error = None
        for pwd in candidates:
            conn_str = (
                r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"Dbq={self.bds_path};"
                "ReadOnly=1;"
                "Exclusive=1;"          # v1.5.1 — avoids temp-DSN registry error
            )
            if pwd:
                conn_str += f"PWD={pwd};"
            try:
                self._conn = pyodbc.connect(conn_str)
                self._connection_method = "ODBC"
                if pwd:
                    logger.info(
                        f"  Busy DB opened via ODBC (password profile: "
                        f"{'env-override' if pwd_env else pwd[:2] + '***'})")
                else:
                    logger.info("  Busy DB opened via ODBC (no password)")
                return self._conn
            except pyodbc.InterfaceError as e:
                raise RuntimeError(
                    "Could not open the Busy database. The "
                    "'Microsoft Access Database Engine' ODBC driver is "
                    "missing on this PC. Install the free 64-bit driver "
                    "from https://www.microsoft.com/en-us/download/details.aspx?id=54920 "
                    "then restart the agent.") from e
            except pyodbc.ProgrammingError as e:
                last_error = e
                if "-1905" in str(e) or "Not a valid password" in str(e):
                    continue
                raise
            except pyodbc.Error as e:
                last_error = e
                continue

        raise RuntimeError(
            "Could not open the Busy database — both OLE DB and every "
            "known ODBC password were rejected.\n\n"
            "Best path forward:\n"
            "  • On a LICENSED Busy install: enable 'Busy Data "
            "Connectivity' from Setup → License, and set your Busy user "
            "credentials in Settings → Busy Data Folder.\n"
            "  • On Demo/older builds: paste a custom BUSY_DB_PASSWORD "
            "in Settings → Busy Data Folder.\n\n"
            f"Last driver error: {last_error}") from last_error

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        # access_parser has no explicit close — drop the reference so
        # the underlying file handle / mmap gets GC'd.
        self._ap = None
        self._ap_row_cache.clear()

    def iter_rows(self, table: str, columns: str = "*", where: str = "") -> Generator[Dict, None, None]:
        """Iterate rows one-by-one. NEVER loads full table into RAM
        (except the access_parser path which caches per table)."""
        # v1.5.1 — pure-Python JET4 path when access_parser succeeded.
        # No password, no driver, works on any OS.
        conn = self._get_connection()
        if self._ap is not None:
            for row in self._load_table_via_ap(table):
                yield row
            return

        if self.is_windows:
            sql = f"SELECT {columns} FROM [{table}]"
            if where:
                sql += f" WHERE {where}"
            cursor = conn.cursor()
            cursor.execute(sql)
            col_names = [desc[0] for desc in cursor.description]
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                yield dict(zip(col_names, row))
            cursor.close()
        else:
            # Linux dev-mode fallback: mdb-export CLI
            cmd = ["mdb-export", self.bds_path, table]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            reader = csv.DictReader(proc.stdout)
            for row in reader:
                if where:
                    pass  # Simple client-side filter for Linux dev mode
                yield row
            proc.wait()

    def count_rows(self, table: str, where: str = "") -> int:
        # v1.5.1 — access_parser path
        conn = self._get_connection()
        if self._ap is not None:
            return len(self._load_table_via_ap(table))
        if self.is_windows:
            sql = f"SELECT COUNT(*) FROM [{table}]"
            if where:
                sql += f" WHERE {where}"
            cursor = conn.cursor()
            cursor.execute(sql)
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        else:
            count = 0
            for _ in self.iter_rows(table):
                count += 1
            return count


# ---------------------------------------------------------------------------
# Busy Master1 column aliases (iter-140: enrichment inspired by BusyNotify's
# public API response shape — implementation is 100% our own via direct
# ODBC, no dependency or bridge to BusyNotify.)
#
# Busy's Master1 table stores extended party attributes in `Dn` (D1..D30ish)
# columns whose *meaning* varies by Busy build. Rather than hard-coding one
# mapping, we probe a candidate list in order and pick the first non-empty
# value. Newer builds also carry human-named columns (Add1, GSTIN, Email,
# PinCode, PhoneNo, MobileNo, PANNo, Station, PriceCat) — we prefer those.
#
# Each key maps to a list of possible source column names. On any given
# Busy install only a subset will actually exist; missing columns are
# silently ignored so we never crash on older schemas.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Busy real-schema mapping — validated iter-141 against a real licensed
# Busy 21 database (COMP0002 live sample, 12 Sundry Debtors, 10,287
# MasterAddressInfo rows).
#
# Corrections vs iter-140 assumptions:
#   • Party contact/address/GST/PAN/mobile/email live in `MasterAddressInfo`,
#     joined on `MasterCode = Master1.Code`. They are NOT on Master1.
#     (Master1's `D1..D26` are Double columns — never text — so the
#     v1.5.0 fallback aliases like "D8 for phone" could never work on
#     licensed Busy 21 and were leftover assumptions from Busy Demo.)
#   • Busy 21 has a dedicated `WhatsAppNo` column, already E.164-shaped
#     (starts with country code, e.g. "919820074085"). Prefer it over
#     re-normalizing `Mobile`.
#   • MasterType=6 in Busy 21 = **items/stock master** (10,630 in sample),
#     NOT salesman as in older builds. Salesman link is not directly on
#     Master1 in licensed Busy — voucher-level or MasterSupport-level
#     lookups are needed (deferred to a future iteration).
#   • Folio1's per-party closing balance for FY is `D22` (last-month
#     running balance), not `D23`. D11..D22 hold Apr..Mar monthly
#     end-balances.
# ---------------------------------------------------------------------------
BUSY_MASTERADDRESSINFO_FIELDS: Dict[str, List[str]] = {
    # Real Busy 21 columns first, legacy fallbacks after.
    "phone":       ["Mobile", "TelNo", "MobileNo", "Phone"],
    "email":       ["Email", "EmailId"],
    "gstin":       ["GSTNo", "GSTIN", "TIN"],
    "pan":         ["ITPAN", "PANNo", "PAN"],
    "address_1":   ["Address1", "Add1", "AddLine1"],
    "address_2":   ["Address2", "Add2", "AddLine2"],
    "address_3":   ["Address3", "Add3", "AddLine3"],
    "address_4":   ["Address4", "Add4", "AddLine4"],
    "city":        ["City", "Town"],
    "station":     ["Station", "StationName"],
    "pincode":     ["PINCode", "PinCode", "Pin"],
    "contact":     ["Contact", "ContactPerson"],
    "whatsapp":    ["WhatsAppNo", "WhatsApp"],
    "supplier_type": ["SupplierType", "PartyType"],
}
# Legacy alias kept for tests that still import it (iter-140 tests).
BUSY_MASTER1_FIELD_ALIASES: Dict[str, List[str]] = {
    **BUSY_MASTERADDRESSINFO_FIELDS,
    "price_cat":   ["PriceCat", "PriceCategory", "PC"],
    "opening_bal": ["OpBal", "OpeningBalance"],
    "salesman_code_link": ["Salesman", "SalesmanCode", "AssociatedSalesman"],
}


def _row_pick(row: Dict, candidates: List[str]) -> str:
    """Return the first non-empty value from `row` for any key in `candidates`.
    Empty string if nothing matches. Handles both str and numeric values."""
    for k in candidates:
        v = row.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in ("none", "null"):
            return s
    return ""


def _normalize_whatsapp(mobile: str, default_country_code: str = "91") -> str:
    """Convert a raw Indian mobile number into E.164 form (911XXXXXXXXXX).
    Rules mirror BusyNotify's public contract: strip non-digits, drop
    leading 0/+91, keep last 10, prefix `91`. Returns '' if not
    reconstructable — never raises. Users on non-India country codes can
    override via BUSY_WHATSAPP_COUNTRY_CODE env in a future release."""
    if not mobile:
        return ""
    digits = "".join(ch for ch in str(mobile) if ch.isdigit())
    if not digits:
        return ""
    # Trim leading 0 or country-code duplication
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    if len(digits) > 10 and digits.startswith(default_country_code):
        digits = digits[len(default_country_code):]
    if len(digits) < 10:
        return ""
    last10 = digits[-10:]
    return f"{default_country_code}{last10}"


# ---------------------------------------------------------------------------
# Busy Data Extractor — converts Busy schema to FLOWRA format
# ---------------------------------------------------------------------------
class _PooledReader:
    """v1.5.5 — thin no-op-close proxy over a shared BusyDBReader.

    The 25+ extractor helpers each carry a `finally: reader.close()` line
    from the pre-pool era. Rewiring all of them to skip close would be
    error-prone; instead we hand out this proxy so those close() calls
    become harmless (the pool owns the real lifecycle). Everything else
    (iter_rows, count_rows) delegates straight through — zero behaviour
    change for callers, ~25× fewer .bds file parses per sync tick.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner: "BusyDBReader"):
        self._inner = inner

    def iter_rows(self, *args, **kwargs):
        return self._inner.iter_rows(*args, **kwargs)

    def count_rows(self, *args, **kwargs):
        return self._inner.count_rows(*args, **kwargs)

    def close(self):
        # Pool owns the underlying BusyDBReader; ignore per-helper close.
        return None


class BusyDataExtractor:
    """Extracts and transforms Busy data to FLOWRA-compatible format.
    
    RAM strategy: builds code→name lookup once (small), then streams vouchers.
    """

    def __init__(self, data_folder: str):
        self.data_folder = data_folder
        self._master_db = None   # db.bds path
        self._fy_dbs = {}        # {fy_str: db{year}.bds path}
        self._code_map = {}      # code → name (lazy loaded, ~500 entries max ≈ 50KB)
        self._group_map = {}     # code → group category
        self._parent_map = {}    # code → parent group code
        # v1.5.5 — Reader pool. Each .bds file is opened once per sync
        # cycle instead of ~25 times. `close_readers()` at the end of
        # run_full_sync frees memory (access_parser holds the whole file
        # in RAM); helpers get a `_PooledReader` proxy so their existing
        # `finally: reader.close()` blocks stay safe.
        self._reader_pool: Dict[str, "BusyDBReader"] = {}
        self._detect_files()

    def _get_reader(self, db_path: str) -> "_PooledReader":
        """Return a pooled BusyDBReader proxy for `db_path`. Opens the
        underlying reader on first call, reuses it on subsequent calls
        within the same sync cycle."""
        inner = self._reader_pool.get(db_path)
        if inner is None:
            inner = BusyDBReader(db_path)
            self._reader_pool[db_path] = inner
        return _PooledReader(inner)

    def close_readers(self):
        """Tear down every cached reader — call at the end of a full
        sync tick to release access_parser's in-memory file caches."""
        for path, r in list(self._reader_pool.items()):
            try:
                r.close()
            except Exception as e:
                logger.info(f"  Reader close error for {path}: {e}")
        self._reader_pool.clear()

    def _detect_files(self):
        """Find .bds files in the data folder."""
        folder = self.data_folder
        # Check if DATA.ZIP needs extraction
        data_zip = os.path.join(folder, "DATA.ZIP")
        if os.path.exists(data_zip):
            extract_dir = os.path.join(folder, "_extracted")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(data_zip, "r") as z:
                z.extractall(extract_dir)
            folder = extract_dir

        for f in os.listdir(folder):
            fl = f.lower()
            fpath = os.path.join(folder, f)
            if fl == "db.bds":
                self._master_db = fpath
            elif fl.startswith("db") and fl.endswith(".bds") and fl != "db.bds":
                # db12025.bds → FY start year 2025 → "2025-26"
                try:
                    year_part = fl.replace("db", "").replace(".bds", "")
                    # Could be "12025" (prefix 1) or "2025"
                    if year_part.startswith("1"):
                        year = int(year_part[1:])
                    else:
                        year = int(year_part)
                    fy_str = f"{year}-{str(year + 1)[-2:]}"
                    self._fy_dbs[fy_str] = fpath
                except ValueError:
                    pass

        logger.info(f"Detected master DB: {self._master_db}")
        logger.info(f"Detected FY databases: {list(self._fy_dbs.keys())}")

    def get_available_fys(self) -> List[str]:
        return sorted(self._fy_dbs.keys())

    def get_company_display_name(self, folder_id: str = "") -> str:
        """v1.5.4 — Resolve the human-readable company name (e.g.
        `NAVDURGA AUTO SPARES JABALPUR`) from the Busy database itself
        instead of falling back to the folder id (`COMP0002`).

        Busy 21 stores the company header inside `db.bds` (the master
        DB, shared across all FYs of a company). Column names differ
        across Busy generations, so we probe a candidate list and
        return the first non-empty value. Falls back to `folder_id`
        if none of the candidates yield a name — the agent still
        works, just with the old ugly label.
        """
        # Prefer master DB (constant across FYs). Fall back to any FY
        # DB — company header is duplicated in every FY file too.
        candidate_dbs = []
        if self._master_db:
            candidate_dbs.append(self._master_db)
        for _fy, _path in sorted(self._fy_dbs.items(), reverse=True):
            if _path not in candidate_dbs:
                candidate_dbs.append(_path)

        # (table, [name_columns]) tuples — tried in order.
        table_probes = [
            ("Cmpny",     ["BDEPName", "Name", "CompanyName", "CmpnyName"]),
            ("Company1",  ["BDEPName", "Name", "CompanyName"]),
            ("Company",   ["BDEPName", "Name", "CompanyName"]),
            ("BusyDataInfo", ["Name", "CompanyName", "BDEPName"]),
            ("BDept",     ["BDEPName", "Name"]),
            ("CompanyInfo", ["Name", "CompanyName", "BDEPName"]),
        ]

        for db_path in candidate_dbs:
            reader = None
            try:
                reader = self._get_reader(db_path)
                for tbl, cols in table_probes:
                    try:
                        for row in reader.iter_rows(tbl):
                            for col in cols:
                                name = (row.get(col) or "").strip()
                                if name and name.lower() != "default":
                                    logger.info(
                                        f"  Resolved company display name: "
                                        f"'{name}' (via {tbl}.{col})"
                                    )
                                    return name
                    except Exception:
                        # Table missing on this Busy build — try next.
                        continue
            except Exception as e:
                logger.info(f"  Company name probe skipped for {db_path}: {e}")
            finally:
                if reader is not None:
                    try:
                        reader.close()
                    except Exception:
                        pass

        fallback = (folder_id or "").strip() or "Default Company"
        logger.info(
            f"  Company display name not found in DB — falling back to "
            f"'{fallback}'. Set BUSY_COMPANY_DISPLAY_NAME env var to "
            "override manually."
        )
        return fallback

    def _load_code_map(self, fy: str):
        """Load code→name lookup. Small dataset (~500 entries ≈ 50KB RAM).

        v1.5.2 — For MasterType=6 (items), Busy 21 stores the human-
        readable name in `Alias` while `Name` is the alphanumeric SKU
        code. We now prefer Alias for items so voucher-item names, sales
        frequency, and inventory analytics render intelligibly.
        Non-item masters (parties, ledgers, groups) still use `Name`.
        """
        if self._code_map:
            return
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                code = row.get("Code", "")
                mtype = str(row.get("MasterType") or "")
                name = (row.get("Name") or "").strip()
                alias = (row.get("Alias") or "").strip()
                parent = row.get("ParentGrp", "")

                # Items (MasterType=6) — prefer human-readable Alias.
                display = (alias if mtype == "6" and alias else name)
                self._code_map[code] = display
                self._parent_map[code] = parent
                if mtype == "1":
                    # Account group
                    try:
                        self._group_map[code] = ACCOUNT_GROUP_MAP.get(int(code), "other")
                    except (ValueError, TypeError):
                        self._group_map[code] = "other"
        finally:
            reader.close()
        logger.info(f"Code map loaded: {len(self._code_map)} entries")

    def _resolve_name(self, code) -> str:
        return self._code_map.get(str(code), f"Code:{code}")

    def _resolve_category(self, parent_grp_code) -> str:
        return self._group_map.get(str(parent_grp_code), "other")

    # ── Master Data Extractors ──────────────────────────

    def _load_salesman_map(self, fy: str) -> Dict[str, Dict[str, str]]:
        """Build code → {name, mobile, whatsapp} for MasterType=6 (Salesman).
        Iter-140: enables per-party salesman enrichment on `extract_customers`.
        Cached after first call. Safe on older Busy builds that may lack the
        salesman master — returns {} silently instead of raising."""
        if hasattr(self, "_salesman_map_cache") and self._salesman_map_cache is not None:
            return self._salesman_map_cache
        result: Dict[str, Dict[str, str]] = {}
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            self._salesman_map_cache = result
            return result
        try:
            reader = self._get_reader(db_path)
            try:
                for row in reader.iter_rows("Master1"):
                    if row.get("MasterType") != "6":
                        continue
                    code = str(row.get("Code") or "").strip()
                    if not code:
                        continue
                    mobile = _row_pick(row, BUSY_MASTER1_FIELD_ALIASES["phone"])
                    result[code] = {
                        "name": (row.get("Name") or "").strip(),
                        "mobile": mobile,
                        "whatsapp": _normalize_whatsapp(mobile),
                    }
            finally:
                reader.close()
        except Exception as e:
            logger.warning(f"Salesman map load skipped: {e}")
        self._salesman_map_cache = result
        return result

    def _load_folio_closing_bal(self, fy: str) -> Dict[str, float]:
        """Build code → closing_balance for MasterType=2 rows (parties).

        v1.5.1 — verified against a real licensed Busy 21 DB: monthly
        end-balances live in D11..D22 (Apr..Mar for Indian FY). The
        year-end closing balance for the FY is therefore `D22` (or the
        last non-zero of D11..D22 if the party had no March activity).
        Legacy Busy Demo builds used `D23`; we keep it as a fallback."""
        if hasattr(self, "_folio_bal_cache") and self._folio_bal_cache is not None:
            return self._folio_bal_cache
        result: Dict[str, float] = {}
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            self._folio_bal_cache = result
            return result
        try:
            reader = self._get_reader(db_path)
            try:
                for row in reader.iter_rows("Folio1"):
                    if str(row.get("MasterType") or "") != "2":
                        continue
                    code = str(row.get("MasterCode") or "").strip()
                    if not code:
                        continue
                    # Prefer D22 (Mar month-end). Fall back to last
                    # non-zero of D11..D22, then to legacy D23.
                    bal = 0.0
                    for key in ("D22", "D21", "D20", "D19", "D18",
                                "D17", "D16", "D15", "D14", "D13",
                                "D12", "D11", "D23"):
                        try:
                            v = float(row.get(key) or 0)
                        except (TypeError, ValueError):
                            v = 0.0
                        if v != 0:
                            bal = v
                            break
                    result[code] = bal
            finally:
                reader.close()
        except Exception as e:
            logger.warning(f"Folio closing-balance map skipped: {e}")
        self._folio_bal_cache = result
        return result

    def _load_address_info(self, fy: str) -> Dict[str, Dict]:
        """v1.5.1 — Load MasterAddressInfo, keyed by MasterCode. This is
        where licensed Busy 21 keeps party contact / address / GST / PAN
        / mobile / WhatsApp / station / PIN. Silently returns {} on
        older builds that don't ship the table."""
        if hasattr(self, "_addr_info_cache") and self._addr_info_cache is not None:
            return self._addr_info_cache
        result: Dict[str, Dict] = {}
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            self._addr_info_cache = result
            return result
        try:
            reader = self._get_reader(db_path)
            try:
                for row in reader.iter_rows("MasterAddressInfo"):
                    code = str(row.get("MasterCode") or "").strip()
                    if code:
                        result[code] = row
            finally:
                reader.close()
            logger.info(f"MasterAddressInfo loaded: {len(result)} rows")
        except Exception as e:
            logger.info(f"MasterAddressInfo unavailable ({e}) — "
                        "falling back to Master1-only fields")
        self._addr_info_cache = result
        return result

    def extract_customers(self, fy: str) -> Generator[Dict, None, None]:
        """Yield Sundry Debtor records with enriched contact, address,
        GST/PAN, price category and closing balance.

        v1.5.1 — rewritten against a real licensed Busy 21 database.
        Master1 holds only identity + `Dn` numerics; contact/address
        lives in `MasterAddressInfo` joined on MasterCode. Older Busy
        Demo builds that lack `MasterAddressInfo` degrade gracefully
        (address/contact fields emit as empty strings).
        """
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        closing_bal_map = self._load_folio_closing_bal(fy)
        addr_info_map = self._load_address_info(fy)
        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if str(row.get("MasterType") or "") != "2":
                    continue
                parent_code = str(row.get("ParentGrp") or "").strip()
                parent = self._resolve_category(parent_code)
                if parent != "sundry_debtors":
                    continue

                code = str(row.get("Code") or "").strip()
                customer_name = (row.get("Name") or "").strip()

                # Join with MasterAddressInfo (v1.5.1 — real Busy 21 path)
                addr = addr_info_map.get(code, {}) or {}

                addr_lines = [
                    _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS[k])
                    for k in ("address_1", "address_2", "address_3", "address_4")
                ]
                address_joined = ", ".join([a for a in addr_lines if a])

                # Contact — Mobile column may hold comma-separated numbers
                # ("7458879984,9820074085"). Split and keep the first.
                phone_raw = _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["phone"])
                phone = phone_raw.split(",")[0].strip() if phone_raw else ""
                # Prefer Busy 21's dedicated WhatsAppNo (already E.164).
                whatsapp_raw = _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["whatsapp"])
                whatsapp = whatsapp_raw or _normalize_whatsapp(phone)

                closing = closing_bal_map.get(code, 0.0)
                # v1.5.7 — Opening balance IS stored on Master1.D1 for
                # MasterType=2 (verified against extract_all_ledgers which
                # already reads it). The earlier "unreliable" comment was
                # overly cautious.
                try:
                    opening = float(row.get("D1") or 0)
                except (TypeError, ValueError):
                    opening = 0.0

                # Salesman: Busy 21's MasterType=6 = items, NOT salesman.
                # Party-level salesman link isn't in Master1/MasterAddressInfo
                # here; deferred to a future voucher-level enrichment.
                salesman_code = ""
                sales_info: Dict[str, str] = {}

                # Price category — sometimes carried on Master1 as `I5`
                # (per BSSData reference). Emit "" if unknown, matches
                # BusyNotify's `null` convention (transported as "").
                price_cat = str(row.get("I5") or row.get("PriceCat")
                                or "").strip() or "0"

                yield {
                    # Identity
                    "customer_id": code,
                    "customer_name": customer_name,

                    # Group hierarchy
                    "group_id": parent_code,
                    "group_name": self._resolve_name(parent_code) if parent_code else "",

                    # Contact (from MasterAddressInfo)
                    "mobile_number": phone,
                    "phone": phone,                       # legacy alias
                    "whatsapp_number": whatsapp,
                    "email_id": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["email"]),

                    # Address
                    "address_line_1": addr_lines[0],
                    "address_line_2": addr_lines[1],
                    "address_line_3": addr_lines[2],
                    "address_line_4": addr_lines[3],
                    "address": address_joined,
                    "city": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["city"]),
                    "station": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["station"]),
                    "pin_code": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["pincode"]),
                    "state": "",                          # resolved via StateCodeLong (future)
                    "country": "India",                   # default; StateCodeLong lookup future

                    # Tax IDs
                    "gst_number": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["gstin"]),
                    "pan_number": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["pan"]),

                    # Balances
                    "opening_balance": opening,
                    "closing_balance": closing,
                    "balance": closing,
                    # v1.5.7 — Sundry Debtors: closing_balance IS the
                    # outstanding receivable from that customer. The
                    # CRM Outstanding tab reads `outstanding_amount`
                    # explicitly, so emit it too instead of leaving it 0.
                    "outstanding_amount": closing,

                    # Salesman (party-level link — placeholder in v1.5.1)
                    "salesman_id": salesman_code or "",
                    "salesman_name": sales_info.get("name", ""),
                    "salesman_mobile_number": sales_info.get("mobile", ""),
                    "salesman_whatsapp_number": sales_info.get("whatsapp", ""),

                    # Price category
                    "price_category": price_cat,

                    # Contact person (v1.5.1 — new field, from MasterAddressInfo.Contact)
                    "contact_person": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["contact"]),
                    "supplier_type": _row_pick(addr, BUSY_MASTERADDRESSINFO_FIELDS["supplier_type"]),

                    # Legacy
                    "ledger_group": "Sundry Debtors",
                    # v1.5.7 — FY tag for CRM per-FY filters + CA-Corner
                    # opening/closing snapshots.
                    "fy": fy,
                }
        finally:
            reader.close()

    def extract_creditors(self, fy: str) -> Generator[Dict, None, None]:
        """v1.5.7 — emit closing_balance + outstanding_amount + fy so
        the CRM Creditors tab shows real balances instead of blanks."""
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        closing_bal_map = self._load_folio_closing_bal(fy)
        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if row.get("MasterType") != "2":
                    continue
                parent = self._resolve_category(row.get("ParentGrp", ""))
                if parent != "sundry_creditors":
                    continue
                code = row.get("Code", "")
                try:
                    opening = float(row.get("D1") or 0)
                except (TypeError, ValueError):
                    opening = 0.0
                closing = closing_bal_map.get(code, 0.0)
                yield {
                    "creditor_name": (row.get("Name") or "").strip(),
                    "creditor_id": code,
                    "opening_balance": opening,
                    "closing_balance": closing,
                    "outstanding_amount": closing,
                    "ledger_group": "Sundry Creditors",
                    "fy": fy,
                }
        finally:
            reader.close()

    def extract_inventory_items(self, fy: str) -> Generator[Dict, None, None]:
        """v1.5.2 — Rewritten against real licensed Busy 21 schema.

        Confirmed via COMP0002 (10,630 items):
          • `Master1.Name`  = alphanumeric SKU code (e.g. "10039927AA")
          • `Master1.Alias` = human-readable name (e.g. "SARTHI Engine Oil 1 LTR")
            ← this is what the FLOWRA UI must display.
          • `Master1.PrintName` = invoice-print name
          • `Master1.HSNCode` = HSN
          • `Master1.D1..D26` are numeric flags/factors — NOT prices, so
            we no longer default `price = D1` (which was always 1.0).
          • `Folio1` (for MasterType=6) holds monthly quantity slots
            across multiple dimensions; last non-zero within D11..D30 is
            the most recent qty snapshot.

        Cost & sale price are computed as a weighted-average from
        purchase/sales voucher line-items via `_load_item_price_map` —
        this is the same last-known-rate approach Busy uses internally.
        """
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return

        # Build item quantity and price maps once (streamed, cached).
        item_qty_map = self._load_item_qty_map(fy)
        item_price_map = self._load_item_price_map(fy)
        item_opening_map = self._load_item_opening_map(fy)  # v1.5.6

        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if str(row.get("MasterType") or "") != "6":
                    continue
                code = str(row.get("Code") or "").strip()
                # Alias holds the human-readable name in Busy 21; some
                # older builds put it in `Name`. Fall back defensively.
                alias = (row.get("Alias") or "").strip()
                sku_code = (row.get("Name") or "").strip()
                item_name = alias or sku_code
                price_row = item_price_map.get(code, {})
                opening = item_opening_map.get(code, {})
                closing_qty = item_qty_map.get(code, 0.0)
                # v1.5.6 — sale/cost price fallback ladder: transaction
                # rate → Master1 built-in rate columns (SPrice/PPrice
                # exist on newer Busy builds; on older builds we probe
                # D-columns that historically carried the sale rate).
                sale_price = price_row.get("sale_price", 0.0)
                if not sale_price:
                    for col in ("SPrice", "SalePrice", "SaleRate", "MRP", "PrintPrice", "D3", "D4"):
                        try:
                            v = float(row.get(col) or 0)
                        except (TypeError, ValueError):
                            continue
                        if 0 < v < 1_000_000:
                            sale_price = v
                            break
                cost_price = price_row.get("cost_price", 0.0)
                if not cost_price:
                    for col in ("PPrice", "PurchasePrice", "PurchaseRate", "CostRate", "D2"):
                        try:
                            v = float(row.get(col) or 0)
                        except (TypeError, ValueError):
                            continue
                        if 0 < v < 1_000_000:
                            cost_price = v
                            break

                # Opening rate/value — fall back to cost_price × opening_qty
                # when Folio1 didn't have an explicit rate row.
                op_qty  = opening.get("opening_quantity", 0.0)
                op_rate = opening.get("opening_rate", 0.0) or cost_price
                op_val  = opening.get("opening_value",
                                      round(op_qty * op_rate, 2))
                close_val = round(closing_qty * (sale_price or cost_price or op_rate), 2)

                yield {
                    # Legacy keys — kept for backwards-compat with v1.5.1
                    # and the analytics tables that key on them.
                    "item_name": item_name,
                    "item_id": code,
                    "part_number": (row.get("PrintName") or alias or sku_code).strip(),
                    "quantity": closing_qty,
                    "price": sale_price,
                    "unit": "",     # unit code resolves via CM master later
                    "stock_group": self._resolve_name(row.get("ParentGrp", "")),

                    # v1.5.2 — enriched fields
                    "sku_code": sku_code,
                    "alias": alias,
                    "hsn_code": (row.get("HSNCode") or "").strip(),
                    "sale_price": sale_price,
                    "cost_price": cost_price,
                    "last_sold_rate": price_row.get("last_sold_rate", 0.0),
                    "last_purchased_rate": price_row.get("last_purchased_rate", 0.0),
                    "closing_qty": closing_qty,
                    "stock_group_code": (row.get("ParentGrp") or "").strip(),
                    "created_at": (row.get("CreationTime") or "").strip(),
                    "modified_at": (row.get("ModificationTime") or "").strip(),

                    # v1.5.6 — opening balance snapshot for CA-Corner
                    # balance-sheet + Dashboard opening-stock widgets.
                    "opening_quantity": op_qty,
                    "opening_rate": op_rate,
                    "opening_value": op_val,
                    "closing_value": close_val,

                    # v1.5.7 — FY tag so CA-Corner opening-stock queries
                    # can filter per FY (Tally-safe: field is optional).
                    "fy": fy,
                }
        finally:
            reader.close()

    def _load_item_opening_map(self, fy: str) -> Dict[str, Dict[str, float]]:
        """v1.5.6 — Opening quantity/rate/value per item from Folio1.

        Busy 21 stores per-item opening balance snapshots in Folio1
        MasterType=6 rows using D-slot columns *before* the qty-snapshot
        range (D11..D50 are period-end snapshots — see
        `_load_item_qty_map`). Empirically D1/D2/D3 hold opening qty /
        rate / value for MasterType=6 in newer Busy releases. On older
        builds those slots may be zero — the fallback ladder in
        `extract_inventory_items` derives opening_rate from cost_price
        and opening_value from qty×rate so the UI never shows blanks.
        """
        if hasattr(self, "_item_opening_cache") and self._item_opening_cache is not None:
            return self._item_opening_cache
        result: Dict[str, Dict[str, float]] = {}
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            self._item_opening_cache = result
            return result
        try:
            reader = self._get_reader(db_path)
            try:
                for row in reader.iter_rows("Folio1"):
                    if str(row.get("MasterType") or "") != "6":
                        continue
                    code = str(row.get("MasterCode") or "").strip()
                    if not code:
                        continue
                    def _fnum(col):
                        try:
                            return float(row.get(col) or 0)
                        except (TypeError, ValueError):
                            return 0.0
                    op_qty  = _fnum("D1")
                    op_rate = _fnum("D2")
                    op_val  = _fnum("D3")
                    # Sanity: opening qty rarely exceeds 1e7; if D1 looks
                    # more like a value (₹ 10 lakh+), swap slots.
                    if abs(op_qty) > 1_000_000 and abs(op_val) < 100_000:
                        op_qty, op_val = op_val, op_qty
                    if op_val == 0 and op_qty and op_rate:
                        op_val = round(op_qty * op_rate, 2)
                    if op_qty or op_rate or op_val:
                        result[code] = {
                            "opening_quantity": op_qty,
                            "opening_rate": op_rate,
                            "opening_value": op_val,
                        }
            finally:
                reader.close()
        except Exception as e:
            logger.warning(f"Item opening map skipped: {e}")
        self._item_opening_cache = result
        return result

    def _load_item_qty_map(self, fy: str) -> Dict[str, float]:
        """v1.5.2 — Closing quantity per item, read from Folio1.

        Busy 21 stores item balances in Folio1 rows where MasterType=6.
        Quantity slots span D11..D50; the last non-zero column is the
        most recent snapshot. We take max abs across those columns as a
        robust heuristic — under-selects during mid-FY are better than
        picking a stale zeroed month."""
        if hasattr(self, "_item_qty_cache") and self._item_qty_cache is not None:
            return self._item_qty_cache
        result: Dict[str, float] = {}
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            self._item_qty_cache = result
            return result
        try:
            reader = self._get_reader(db_path)
            try:
                for row in reader.iter_rows("Folio1"):
                    if str(row.get("MasterType") or "") != "6":
                        continue
                    code = str(row.get("MasterCode") or "").strip()
                    if not code:
                        continue
                    # Only quantity-range D-columns (D11..D50). D1..D10
                    # and D51+ hold value-in-rupees or other metrics.
                    best = 0.0
                    for key in [f"D{n}" for n in range(11, 51)]:
                        try:
                            v = float(row.get(key) or 0)
                        except (TypeError, ValueError):
                            v = 0.0
                            continue
                        # Ignore obviously-value columns (values in ₹
                        # are typically 3+ digits and much larger than
                        # typical qty). If it looks like a price, skip.
                        if abs(v) > 100000:
                            continue
                        if abs(v) > abs(best):
                            best = v
                    result[code] = best
            finally:
                reader.close()
        except Exception as e:
            logger.warning(f"Item qty map skipped: {e}")
        self._item_qty_cache = result
        return result

    def _load_item_price_map(self, fy: str) -> Dict[str, Dict[str, float]]:
        """v1.5.2 — Derive per-item sale_price + cost_price from voucher
        line items in this FY. Uses the most recent sale/purchase rate
        so newly-adjusted prices show up in FLOWRA within the same tick.

        Streamed in one pass over Tran2 — no full-history retention."""
        if hasattr(self, "_item_price_cache") and self._item_price_cache is not None:
            return self._item_price_cache
        result: Dict[str, Dict[str, float]] = {}
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            self._item_price_cache = result
            return result
        try:
            reader = self._get_reader(db_path)
            try:
                # Reader over Tran2 rows carrying stock-item lines
                # (RecType=2) across sales (VchType=9) & purchases
                # (VchType=2). We keep the LAST non-zero rate per item
                # per direction — this is Busy's own "last rate" logic.
                for row in reader.iter_rows("Tran2"):
                    if str(row.get("RecType") or "") != "2":
                        continue
                    vch_type = str(row.get("VchType") or "")
                    item_code = str(row.get("MasterCode1") or "").strip()
                    if not item_code:
                        continue
                    try:
                        rate = abs(float(row.get("D2") or row.get("D3") or 0))
                    except (TypeError, ValueError):
                        rate = 0.0
                    if rate <= 0:
                        continue
                    slot = result.setdefault(item_code, {
                        "sale_price": 0.0, "cost_price": 0.0,
                        "last_sold_rate": 0.0, "last_purchased_rate": 0.0,
                    })
                    if vch_type == "9":           # sale
                        slot["last_sold_rate"] = rate
                        slot["sale_price"] = rate
                    elif vch_type == "2":         # purchase
                        slot["last_purchased_rate"] = rate
                        slot["cost_price"] = rate
            finally:
                reader.close()
        except Exception as e:
            logger.warning(f"Item price map skipped: {e}")
        self._item_price_cache = result
        return result

    def extract_all_ledgers(self, fy: str) -> Generator[Dict, None, None]:
        """All ledger accounts with closing balances for Balance Sheet & P&L."""
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        # Get Folio1 closing balances
        folio_bal = {}
        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Folio1"):
                if row.get("MasterType") == "2":
                    code = row.get("MasterCode", "")
                    folio_bal[code] = float(row.get("D23") or 0)
        finally:
            reader.close()

        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if row.get("MasterType") != "2":
                    continue
                code = row.get("Code", "")
                parent_code = row.get("ParentGrp", "")
                category = self._resolve_category(parent_code)
                if category in ("sundry_debtors", "sundry_creditors"):
                    continue  # Exclude debtors/creditors (they're in customers/creditors)
                yield {
                    "ledger_name": (row.get("Name") or "").strip(),
                    "ledger_id": code,
                    "parent_group": self._resolve_name(parent_code),
                    "category": category,
                    "closing_balance": folio_bal.get(code, 0),
                    "opening_balance": float(row.get("D1") or 0),
                }
        finally:
            reader.close()

    # ── Voucher Extractors (streaming, chunked) ─────────

    def _extract_vouchers_by_type(self, fy: str, vch_type: int) -> Generator[Dict, None, None]:
        """Stream vouchers of a specific type. Joins Tran1 (header) + Tran2 (items).

        v1.5.2 — SCHEMA CORRECTION verified against real licensed Busy 21 DB:
          • RecType=2 in Tran2 = STOCK ITEM lines (NOT ledger lines — the
            v1.5.1 mapping had this flipped). Item code lives in
            MasterCode1, warehouse/material-center in MasterCode2, sold
            quantity in D1 (with sign), rate in D2/D3, MRP in D4, discount
            in D5, net line amount in D6, GST rate% in D9, GST amount in
            D10, CGST/SGST in D11.
          • RecType=1 = journal ledger postings (party dr/cr, sales cr,
            GST payable cr, freight etc). MasterCode1 = ledger code,
            Value1 = amount (signed).
          • RecType=3 = rounding / auto-generated adjustments.
        """
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return

        items_by_vch = defaultdict(list)
        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Tran2"):
                if str(row.get("VchType", "")) != str(vch_type):
                    continue
                vch_code = row.get("VchCode", "")
                rec_type = str(row.get("RecType") or "")
                master_code = row.get("MasterCode1", "")
                if rec_type == "2":
                    # v1.5.7 — Busy 21 empirical mapping (COMP0002):
                    #   D1  = signed quantity
                    #   D2  = rate/unit  (identical to D3 in the wild)
                    #   D3  = rate/unit
                    #   D4  = MRP
                    #   D5  = internal amount slot (NOT plain discount — often
                    #         holds "MRP*qty - net + GST" or similar, so
                    #         storing it as `discount` gave nonsensical values)
                    #   D6  = rate/unit again (SAME as D2 in every observed
                    #         line — NOT net line amount as the v1.5.2
                    #         comment claimed).
                    #   D9  = tax code / GST% (raw)
                    #   D10 = GST amount (₹)
                    # → the *only* trustworthy line total is `qty × rate`.
                    quantity = abs(float(row.get("D1") or row.get("Value1") or 0))
                    rate     = abs(float(row.get("D2") or row.get("D3") or 0))
                    line_amount = round(quantity * rate, 2)
                    mrp = abs(float(row.get("D4") or 0))
                    # Per-line discount recovered from MRP minus rate. If
                    # MRP is 0 (item without a printed MRP) we can't infer
                    # discount, so emit 0 rather than a spurious value.
                    disc_per_unit = max(mrp - rate, 0.0) if mrp else 0.0
                    line_discount = round(disc_per_unit * quantity, 2)
                    amount = line_amount
                else:
                    amount = abs(float(row.get("Value1") or row.get("Value3") or 0))
                    quantity = 0.0
                    rate = 0.0
                    mrp = 0.0
                    line_discount = 0.0
                items_by_vch[vch_code].append({
                    "rec_type": rec_type,
                    "master_code": master_code,
                    "name": self._resolve_name(master_code),
                    "value": amount,
                    "quantity": quantity,
                    "rate": rate,
                    "mrp": mrp,
                    "discount": line_discount,
                    "gst_pct": abs(float(row.get("D9") or 0)),
                    "gst_amount": abs(float(row.get("D10") or 0)),
                    "warehouse_code": row.get("MasterCode2", ""),
                    "warehouse_name": self._resolve_name(row.get("MasterCode2", "")),
                    "short_nar": (row.get("ShortNar") or "").strip(),
                })
        finally:
            reader.close()

        reader = self._get_reader(db_path)
        try:
            for row in reader.iter_rows("Tran1"):
                if str(row.get("VchType", "")) != str(vch_type):
                    continue
                vch_code = row.get("VchCode", "")
                party_code = row.get("MasterCode1", "")
                party_name = self._resolve_name(party_code)
                vch_date_raw = (row.get("Date") or "").strip()
                vch_date = self._parse_date(vch_date_raw)
                # VchNo comes right-space-padded in the DB — strip aggressively.
                vch_no = (row.get("VchNo") or row.get("AutoVchNo") or "").strip()
                # v1.5.7 — Busy stores the *external* reference (customer
                # PO / counterparty invoice) in RefNo / RefNoAlpha. When
                # present, expose it separately from the printed invoice
                # number so app columns labelled "Reference" and
                # "Invoice #" stop showing the same value.
                ref_no = (row.get("RefNoAlpha") or row.get("RefNo") or "").strip()
                amount = abs(float(row.get("VchAmtBaseCur") or 0))
                # v1.5.2 — Busy 21 stores a Drive link to the invoice PDF
                # per voucher. Expose it so FLOWRA UI can open the source.
                doc_link = (row.get("BusyDocLink") or "").strip()
                doc_name = (row.get("BusyDocName") or "").strip()
                # v1.5.7 — narration column varies by build.
                narration = (row.get("Narration") or row.get("LongNar")
                             or row.get("Nar") or "").strip()

                line_items = items_by_vch.pop(vch_code, [])
                # v1.5.2 — CORRECTED mapping (was inverted in v1.5.1):
                # RecType=2 → stock items, RecType=1 → ledger postings.
                item_entries = [i for i in line_items if i["rec_type"] == "2"]
                ledger_entries = [i for i in line_items if i["rec_type"] == "1"]

                voucher = {
                    "voucher_id": f"BUSY-{fy}-{vch_code}-{vch_type}",   # v1.5.2 — FY-scoped so multi-FY syncs don't overwrite
                    "voucher_date": vch_date,
                    "voucher_number": vch_no,          # printed invoice number ("NAV/628/26-27")
                    "reference_number": ref_no or vch_no,  # external ref if present, else fall back to VchNo
                    "fy": fy,                          # v1.5.7 — required for CA-Corner FY-picker
                    "party_name": party_name,
                    "party_code": party_code,
                    "total_amount": amount,
                    "items": [{
                        "item": i["name"],
                        "item_name": i["name"],
                        "item_code": i["master_code"],
                        "quantity": i["quantity"],
                        "rate": i["rate"],
                        "amount": i["value"],
                        "mrp": i.get("mrp", 0),
                        "discount": i.get("discount", 0),
                        "gst_pct": i.get("gst_pct", 0),
                        "gst_amount": i.get("gst_amount", 0),
                        "warehouse": i.get("warehouse_name", ""),
                        "remark": i["short_nar"],
                    } for i in item_entries],
                    "ledger_entries": [{
                        "ledger_name": e["name"],
                        "ledger_code": e["master_code"],
                        "amount": e["value"],
                    } for e in ledger_entries],
                    "narration": narration,
                    "busy_doc_link": doc_link,      # v1.5.2 — Google Drive URL to invoice PDF
                    "busy_doc_name": doc_name,
                    "synced_at": now_ist(),
                }

                # Type-specific fields
                if vch_type == 9:  # Sales
                    voucher["salesman"] = ""
                elif vch_type in (1, 3):  # Receipts
                    voucher["amount"] = amount
                elif vch_type == 5:  # Journal
                    total_debit = sum(e["value"] for e in ledger_entries if e.get("rec_type") == "2")
                    voucher["debit_amount"] = total_debit
                    voucher["credit_amount"] = total_debit  # Balanced

                yield voucher
                del line_items  # Free immediately
        finally:
            reader.close()
        del items_by_vch
        gc.collect()

    def _parse_date(self, raw: str) -> str:
        """Parse Busy date formats to YYYY-MM-DD."""
        if not raw:
            return ""
        try:
            # Format: "04/01/25 00:00:00" or "04/01/2025 00:00:00"
            date_part = raw.split(" ")[0]
            parts = date_part.split("/")
            if len(parts) == 3:
                m, d, y = parts
                if len(y) == 2:
                    y = f"20{y}" if int(y) < 50 else f"19{y}"
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        except Exception:
            pass
        return raw

    # v1.5.3 — VchType mapping VERIFIED against real licensed Busy 21
    # (COMP0002 NAVDURGA AUTO). The 1.5.1 map used Busy Demo defaults
    # which don't match live installs. Live distribution proved:
    #   VchType=9  Sale (1774)   VchType=2  Purchase (467)
    #   VchType=14 Receipt (1446)  VchType=16 Payment (431)
    #   VchType=10 Credit Note (38)  VchType=12 Debit Note (1)
    #   VchType=4  Journal (3)  VchType=19 Contra (568)
    #   VchType=15 Stock Journal (29)
    #   VchType=17 Rate-Diff-on-Sale (5) — lump into credit_notes
    #   VchType=18 Discount-on-Sale (52)  — lump into credit_notes
    #   VchType=3  Sales adjustment (16)  — legacy "sundry_journals"

    def extract_sales(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 9)

    def extract_purchases(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 2)

    def extract_receipts(self, fy: str) -> Generator[Dict, None, None]:
        # Receipts (bank/cash IN from customer) — Busy 21 VchType=14.
        yield from self._extract_vouchers_by_type(fy, 14)

    def extract_payments(self, fy: str) -> Generator[Dict, None, None]:
        """v1.5.3 — Payments (bank/cash OUT to supplier or expense).
        Real Busy 21 VchType=16."""
        yield from self._extract_vouchers_by_type(fy, 16)

    def extract_credit_notes(self, fy: str) -> Generator[Dict, None, None]:
        # Credit-side adjustments reducing receivable: sale-return + rate
        # diff + on-sale discount all funnel into `credit_notes`.
        for vt in (10, 17, 18):
            for v in self._extract_vouchers_by_type(fy, vt):
                yield v

    def extract_debit_notes(self, fy: str) -> Generator[Dict, None, None]:
        # Debit-side adjustment (purchase return / supplier claim).
        yield from self._extract_vouchers_by_type(fy, 12)

    def extract_journals(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 4)

    def extract_contra(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 19)

    def extract_sundry_journals(self, fy: str) -> Generator[Dict, None, None]:
        """v1.5.3 — Busy 21 VchType=3 mixes sale-adjustment / rounding
        journals; keep them under a distinct label so they don't inflate
        the sales-return count."""
        yield from self._extract_vouchers_by_type(fy, 3)

    def extract_stock_journals(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 15)

    def compute_profit_loss(self, fy: str) -> Dict:
        """Compute P&L from ledger closing balances. Low RAM — single pass."""
        income_ledgers = []
        expense_ledgers = []
        total_income = 0
        total_expense = 0

        for ledger in self.extract_all_ledgers(fy):
            cat = ledger.get("category", "")
            bal = abs(ledger.get("closing_balance", 0))
            entry = {
                "ledger_name": ledger["ledger_name"],
                "parent_group": ledger["parent_group"],
                "amount": bal,
            }
            if cat in ("direct_income", "indirect_income", "sale"):
                income_ledgers.append(entry)
                total_income += bal
            elif cat in ("direct_expense", "indirect_expense", "purchase"):
                expense_ledgers.append(entry)
                total_expense += bal

        return {
            "gross_profit": round(total_income - sum(e["amount"] for e in expense_ledgers if e["parent_group"] in ("Expenses (Direct/Mfg.)", "Purchase")), 2),
            "net_profit": round(total_income - total_expense, 2),
            # v1.5.6 — Backend `/api/agent/sync` (data_type='profit_loss')
            # reads `net_profit_loss`. The pre-1.5.6 payload only carried
            # `net_profit`, so the P&L doc's `net_profit_loss` column
            # always ended up stored as 0. Emit BOTH to avoid a fresh
            # regression while the field name is finalised.
            "net_profit_loss": round(total_income - total_expense, 2),
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "income": income_ledgers,
            "expense": expense_ledgers,
            "fy": fy,
            "computed_at": now_ist(),
        }


# ---------------------------------------------------------------------------
# FLOWRA API Client — chunked upload
# ---------------------------------------------------------------------------
class FlowraAPIClient:
    """Handles auth and data sync to FLOWRA backend."""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")
        self.token = None
        self.tenant_id = None
        self.companies = []           # list of company_id strings
        self.company_mappings = []    # list of {company_name, company_id}
        self.features = []
        self.plan = "unknown"
        self.max_companies = 10
        self.sync_token = ""
        self.name = ""

    def login(self, username: str, password: str) -> bool:
        import requests
        try:
            r = requests.post(
                f"{self.backend_url}/api/auth/login",
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if r.status_code != 200:
                logger.error(f"Login HTTP {r.status_code}: {r.text[:200]}")
                return False
            data = r.json()
            if not data.get("success"):
                logger.error(f"Login failed: {data.get('error', 'Unknown')}")
                return False

            d = data["data"]
            if d.get("role") not in ("admin",):
                logger.error("Only admin accounts can use the Busy Sync Agent")
                return False

            self.token = d["token"]
            self.tenant_id = d.get("tenant_id", "")
            self.companies = d.get("companies", []) or []
            self.company_mappings = d.get("company_mappings", []) or []
            self.features = d.get("features", []) or []
            self.plan = d.get("plan", "unknown")
            self.max_companies = d.get("max_companies", 10)
            self.name = d.get("name", "")

            # Fetch sync token (HMAC) for subsequent sync calls
            try:
                tr = requests.get(
                    f"{self.backend_url}/api/auth/sync-token",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10,
                )
                if tr.status_code == 200 and tr.json().get("success"):
                    self.sync_token = tr.json()["data"].get("sync_token", "")
            except Exception as e:
                logger.warning(f"Could not fetch sync_token: {e}")

            logger.info(
                f"Logged in as {self.name or username} | tenant={self.tenant_id} | "
                f"plan={self.plan} | companies={len(self.companies)}"
            )
            return True
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _build_envelope(self, data_type: str, data: list, company_id: str,
                        company_name: str, financial_year: str) -> dict:
        return {
            "data_type": data_type,
            "data": data,
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "agent_version": AGENT_TAG,
            "company_name": company_name,
            "financial_year": financial_year,
            "tenant_id": self.tenant_id,
            "company_id": company_id,
            "sync_token": self.sync_token,
        }

    def _post_chunk(self, data_type: str, chunk: list, company_id: str,
                    company_name: str, financial_year: str) -> bool:
        """POST one chunk with 3-attempt retry + exponential backoff.

        v1.5.4 — Previously a single 502/503/timeout burned the entire
        phase. We now retry with 5s → 30s → 60s sleeps before giving up
        and logging a LOUD error so downstream operators can pinpoint
        the exact data_type + FY that lost data.

        Empty chunks still short-circuit as `True` (no-op).
        """
        import requests
        if not chunk:
            return True
        url = f"{self.backend_url}/api/agent/sync"
        payload = self._build_envelope(data_type, chunk, company_id, company_name, financial_year)
        backoffs = [5, 30, 60]
        for attempt in range(1, len(backoffs) + 2):
            try:
                r = requests.post(url, json=payload, headers=self._auth_headers(), timeout=60)
                if r.status_code == 200:
                    js = r.json()
                    if js.get("success"):
                        return True
                    logger.warning(
                        f"Sync {data_type} attempt {attempt} → app-error: "
                        f"{js.get('error', '')[:200]}"
                    )
                    # App-level errors (e.g. subscription expired,
                    # tenant_id missing) are NOT transient — no retry.
                    return False
                # 4xx / 5xx — treat as transient and retry.
                logger.warning(
                    f"Sync {data_type} attempt {attempt} → HTTP {r.status_code} "
                    f"({len(chunk)} records) · body[:180]: {r.text[:180]}"
                )
            except Exception as e:
                logger.warning(
                    f"Sync {data_type} attempt {attempt} → network error: {e}"
                )
            if attempt <= len(backoffs):
                sleep_s = backoffs[attempt - 1]
                logger.info(
                    f"  Retrying {data_type} in {sleep_s}s "
                    f"(attempt {attempt + 1}/{len(backoffs) + 1})…"
                )
                time.sleep(sleep_s)

        logger.error(
            f"[SYNC-LOST] {data_type}: {len(chunk)} records dropped after "
            f"{len(backoffs) + 1} attempts to {url} · company={company_name} "
            f"({company_id}) fy={financial_year}. Next full-sync tick will "
            "attempt them again."
        )
        return False

    def sync_generator(self, company_id: str, company_name: str, financial_year: str,
                       data_type: str, gen: Generator, id_key: str = "voucher_id") -> tuple:
        """Stream records from a generator, chunk-upload to backend.
        Returns (success, count, manifest_ids)."""
        buffer = []
        manifest = []
        count = 0
        success = True

        for record in gen:
            buffer.append(record)
            manifest.append(str(record.get(id_key, "")))
            count += 1
            if len(buffer) >= CHUNK_SIZE:
                if not self._post_chunk(data_type, buffer, company_id, company_name, financial_year):
                    success = False
                buffer.clear()
                gc.collect()

        if buffer:
            if not self._post_chunk(data_type, buffer, company_id, company_name, financial_year):
                success = False
            buffer.clear()

        gc.collect()
        return success, count, manifest

    def sync_data(self, company_id: str, company_name: str, financial_year: str,
                  data_type: str, records: list) -> bool:
        """One-shot sync (for small datasets like profit_loss)."""
        for i in range(0, len(records) or 1, CHUNK_SIZE):
            chunk = records[i:i + CHUNK_SIZE] if records else []
            if not self._post_chunk(data_type, chunk, company_id, company_name, financial_year):
                return False
        return True

    def reconcile(self, company_id: str, company_name: str, financial_year: str,
                  data_type: str, manifest_ids: list, id_key: str = "voucher_id") -> bool:
        import requests
        try:
            payload = {
                "data_type": data_type,
                "manifest_ids": manifest_ids,
                "tenant_id": self.tenant_id,
                "company_id": company_id,
                "company_name": company_name,
                "financial_year": financial_year,
                "sync_token": self.sync_token,
                "agent_version": AGENT_TAG,
                "id_key": id_key,
            }
            r = requests.post(
                f"{self.backend_url}/api/agent/reconcile",
                json=payload,
                headers=self._auth_headers(),
                timeout=30,
            )
            return r.status_code == 200 and r.json().get("success", False)
        except Exception as e:
            logger.error(f"Reconcile error {data_type}: {e}")
            return False

    def poll_commands(self) -> list:
        import requests
        try:
            r = requests.get(
                f"{self.backend_url}/api/agent/commands",
                params={"tenant_id": self.tenant_id, "sync_token": self.sync_token},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            if r.status_code == 200 and r.json().get("success"):
                return r.json()["data"].get("commands", []) or []
        except Exception as e:
            logger.debug(f"Command poll failed: {e}")
        return []

    def ack_command(self, company_id: str, action: str):
        import requests
        try:
            requests.post(
                f"{self.backend_url}/api/agent/commands/ack",
                json={
                    "tenant_id": self.tenant_id,
                    "company_id": company_id,
                    "action": action,
                },
                headers=self._auth_headers(),
                timeout=10,
            )
        except Exception as e:
            logger.debug(f"Ack failed: {e}")


# ---------------------------------------------------------------------------
# Main Sync Agent — orchestrates extraction + upload
# ---------------------------------------------------------------------------
class FlowraBusySyncAgent:
    """Main agent: login, detect Busy data, sync in phases."""

    def __init__(self, status_callback=None):
        self.config = load_config()
        self.state = load_sync_state()
        self.api = None
        self.extractor = None
        self.running = False
        self.status_callback = status_callback  # GUI callback

    def set_status(self, msg: str):
        logger.info(msg)
        if self.status_callback:
            self.status_callback(msg)

    # ── v1.1 helpers exposed to the new GUI ─────────────────────────────
    def save_config(self):
        """Persist self.config to disk. Called after edits from the UI."""
        save_config(self.config)

    def logout(self):
        """Clear the current session (token + api client)."""
        self.api = None

    def detect_databases(self):
        """Re-initialise the extractor against the currently configured
        Busy data folder. Safe to call multiple times."""
        folder = self.config.get("busy_folder", "")
        if folder:
            self.extractor = BusyDataExtractor(folder)

    @property
    def detected_companies(self):
        """Compatibility alias — GUI code iterates over this to resolve
        company_id from a friendly company_name."""
        return [
            {"id": c["company_id"], "name": c["company_name"]}
            for c in self.get_companies()
        ]

    def report_progress(self, event_type: str, company_id: str = "", company_name: str = "",
                        financial_year: str = "", **kwargs):
        """Mirror Tally v9's progress events — POST to /api/agent/sync-progress.
        Backend broadcasts via websocket so web UI shows live phase progress."""
        if not self.api:
            return
        import requests
        payload = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "financial_year": financial_year,
            "company_name": company_name,
            "tenant_id": self.api.tenant_id,
            "company_id": company_id,
            "agent_version": AGENT_TAG,
            **kwargs,
        }
        try:
            requests.post(
                f"{self.api.backend_url}/api/agent/sync-progress",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api.token}",
                },
                timeout=5,
            )
        except Exception:
            pass  # Non-blocking — progress is best-effort

    def login(self, *args) -> bool:
        """Sign in to FLOWRA.

        Two supported signatures for backward compatibility:
        - login(email, password)          — new GUI (uses saved backend_url)
        - login(backend_url, email, pwd)  — legacy shell / CLI callers
        """
        if len(args) == 2:
            email, password = args
            backend_url = self.config.get("backend_url", DEFAULT_BACKEND_URL)
        elif len(args) == 3:
            backend_url, email, password = args
        else:
            raise TypeError(
                "login() expects (email, password) or (backend_url, email, password)"
            )
        self.api = FlowraAPIClient(backend_url)
        if self.api.login(email, password):
            self.config["backend_url"] = backend_url
            self.config["username"] = email
            save_config(self.config)
            return True
        return False

    def set_busy_folder(self, folder: str):
        self.extractor = BusyDataExtractor(folder)
        self.config["busy_folder"] = folder
        save_config(self.config)

    def get_companies(self) -> list:
        """Return list of {company_id, company_name} from login mappings."""
        if not self.api:
            return []
        if self.api.company_mappings:
            return [
                {"company_id": m.get("company_id", ""),
                 "company_name": m.get("company_name", m.get("company_id", ""))}
                for m in self.api.company_mappings
            ]
        # Fallback: raw company ids only
        return [{"company_id": c, "company_name": c} for c in (self.api.companies or [])]

    def get_fys(self) -> list:
        return self.extractor.get_available_fys() if self.extractor else []

    def available_fys(self) -> list:
        """v1.5.2 alias used by the daemon multi-FY loop."""
        return self.get_fys()

    def run_full_sync(self, company_id: str, company_name: str, fy: str,
                      force: bool = False):
        """Full sync — all data types. RAM-optimized with generator streaming.

        v1.1 — mirrors the Tally v9.8.29 "sync-state banner + short-circuit"
        UX. Emits a single INFO line summarising the persisted state, then
        gates the full scan behind a 7-day recency window (unless force=True).
        """
        if not self.api or not self.extractor:
            self.set_status("Not configured. Login and set Busy folder first.")
            return

        # ── v1.1 — Sync state banner + full-sync short-circuit ────────────
        _cstate = (self.state.get(company_id) or {})
        _prev_full = _cstate.get("last_full_sync")
        _prev_fy = _cstate.get("last_fy")
        _prev_name = _cstate.get("company_name")
        _age_hint = "never"
        _age_days = None
        if _prev_full:
            try:
                _age = datetime.now(IST) - datetime.fromisoformat(_prev_full)
                _age_days = _age.total_seconds() / 86400
                _hours = _age.total_seconds() / 3600
                if _hours < 1:
                    _age_hint = f"{int(_age.total_seconds() // 60)} min ago"
                elif _hours < 48:
                    _age_hint = f"{_hours:.1f} h ago"
                else:
                    _age_hint = f"{int(_hours // 24)} d ago"
            except Exception:
                _age_hint = _prev_full[:19]
        logger.info(
            f"  Sync state ({company_name}): FY={_prev_fy or '—'}  "
            f"·  Last full sync = {_age_hint}"
        )
        if (not force) and _age_days is not None and _age_days < FULL_SKIP_WINDOW_DAYS \
                and _prev_fy == fy and _prev_name == company_name:
            logger.info(
                f"[FULL-SKIP] {company_name}/{fy}: last full sync was "
                f"{_age_hint} (< {FULL_SKIP_WINDOW_DAYS} d). Quick sync will "
                f"pick up new sales. Pass force=True to override."
            )
            self.report_progress("sync_complete",
                                 company_id=company_id, company_name=company_name,
                                 financial_year=fy, source="busy",
                                 mode="full_skip", elapsed_seconds=0)
            return

        self.running = True
        start = time.time()
        self.set_status(f"Starting full sync for {company_name} | FY {fy}...")
        self.report_progress("sync_started", company_id=company_id,
                             company_name=company_name, financial_year=fy,
                             source="busy")

        sync_phases = [
            ("customers",         self.extractor.extract_customers,        "customer_id"),
            ("sundry_creditors",  self.extractor.extract_creditors,        "creditor_id"),
            ("inventory",         self.extractor.extract_inventory_items,  "item_id"),
            ("sales",             self.extractor.extract_sales,            "voucher_id"),
            ("receipts",          self.extractor.extract_receipts,         "voucher_id"),
            ("payment_vouchers",  self.extractor.extract_payments,         "voucher_id"),   # v1.5.3
            ("credit_notes",      self.extractor.extract_credit_notes,     "voucher_id"),
            ("journal_vouchers",  self.extractor.extract_journals,         "voucher_id"),
            ("sundry_journals",   self.extractor.extract_sundry_journals,  "voucher_id"),   # v1.5.3
            ("purchase_vouchers", self.extractor.extract_purchases,        "voucher_id"),
            ("debit_notes",       self.extractor.extract_debit_notes,      "voucher_id"),
            ("contra_vouchers",   self.extractor.extract_contra,           "voucher_id"),
            ("stock_journals",    self.extractor.extract_stock_journals,   "voucher_id"),
        ]

        total_phases = len(sync_phases) + 2  # + profit_loss + all_ledgers
        sync_failed = False

        try:
            for i, (dtype, extractor_fn, id_key) in enumerate(sync_phases, 1):
                self.set_status(f"Phase {i}/{total_phases}: Syncing {dtype}...")
                self.report_progress("phase_start", phase=dtype,
                                     company_id=company_id, company_name=company_name,
                                     financial_year=fy,
                                     phase_index=i, total_phases=total_phases)
                ok, count, manifest = self.api.sync_generator(
                    company_id, company_name, fy, dtype, extractor_fn(fy), id_key
                )
                if ok and manifest:
                    self.api.reconcile(company_id, company_name, fy, dtype, manifest, id_key)
                self.set_status(f"  {dtype}: {count} records synced")
                self.report_progress("phase_complete", phase=dtype, count=count,
                                     company_id=company_id, company_name=company_name,
                                     financial_year=fy,
                                     phase_index=i, total_phases=total_phases)
                if not ok:
                    sync_failed = True
                gc.collect()

            # P&L
            self.set_status("Computing P&L...")
            self.report_progress("phase_start", phase="profit_loss",
                                 company_id=company_id, company_name=company_name,
                                 financial_year=fy,
                                 phase_index=len(sync_phases) + 1, total_phases=total_phases)
            pl = self.extractor.compute_profit_loss(fy)
            self.api.sync_data(company_id, company_name, fy, "profit_loss", [pl])
            self.report_progress("phase_complete", phase="profit_loss", count=1,
                                 company_id=company_id, company_name=company_name,
                                 financial_year=fy,
                                 phase_index=len(sync_phases) + 1, total_phases=total_phases)

            # All Ledgers
            self.set_status("Syncing all ledgers...")
            self.report_progress("phase_start", phase="all_ledgers",
                                 company_id=company_id, company_name=company_name,
                                 financial_year=fy,
                                 phase_index=total_phases, total_phases=total_phases)
            ok, count, _ = self.api.sync_generator(
                company_id, company_name, fy, "all_ledgers",
                self.extractor.extract_all_ledgers(fy), "ledger_id"
            )
            self.set_status(f"  all_ledgers: {count} records synced")
            self.report_progress("phase_complete", phase="all_ledgers", count=count,
                                 company_id=company_id, company_name=company_name,
                                 financial_year=fy,
                                 phase_index=total_phases, total_phases=total_phases)
            if not ok:
                sync_failed = True

            elapsed = round(time.time() - start, 1)
            self.set_status(f"Full sync complete in {elapsed}s at {now_ist_display()}")
            self.report_progress(
                "sync_error" if sync_failed else "sync_complete",
                company_id=company_id, company_name=company_name, financial_year=fy,
                elapsed_seconds=elapsed, source="busy",
            )

            # v1.1 — Persist state (includes ISO-format timestamp used by the
            # 7-day full-sync short-circuit).
            self.state.setdefault(company_id, {})["last_full_sync"] = datetime.now(IST).isoformat()
            self.state[company_id]["last_fy"] = fy
            self.state[company_id]["company_name"] = company_name
            self.state[company_id]["agent_version"] = AGENT_TAG
            save_sync_state(self.state)
            logger.info(
                f"  Sync state persisted: FY={fy}  ·  last_full_sync = now  "
                f"→ next restart within {FULL_SKIP_WINDOW_DAYS} d will short-circuit."
            )
        except Exception as e:
            logger.exception("Full sync failed")
            self.report_progress("sync_error", error=str(e),
                                 company_id=company_id, company_name=company_name,
                                 financial_year=fy, source="busy")
            raise
        finally:
            self.running = False
            # v1.5.5 — Free the pooled BusyDBReader instances so
            # access_parser can release the ~50-200 MB it keeps
            # in RAM for large .bds files. Next tick reopens fresh.
            try:
                self.extractor.close_readers()
            except Exception:
                pass
            gc.collect()

    def run_quick_sales_sync(self, company_id: str, company_name: str, fy: str):
        """Quick sync — sales only. For 5-min interval."""
        if not self.api or not self.extractor:
            return
        self.set_status("Quick sales sync...")
        self.report_progress("sync_started", company_id=company_id,
                             company_name=company_name, financial_year=fy,
                             source="busy", mode="quick")
        self.report_progress("phase_start", phase="sales",
                             company_id=company_id, company_name=company_name,
                             financial_year=fy, phase_index=1, total_phases=1)
        ok, count, manifest = self.api.sync_generator(
            company_id, company_name, fy, "sales",
            self.extractor.extract_sales(fy), "voucher_id"
        )
        if ok and manifest:
            self.api.reconcile(company_id, company_name, fy, "sales", manifest, "voucher_id")
        self.set_status(f"Quick sync: {count} sales at {now_ist_display()}")
        self.report_progress("phase_complete", phase="sales", count=count,
                             company_id=company_id, company_name=company_name,
                             financial_year=fy, phase_index=1, total_phases=1)
        self.report_progress("sync_complete" if ok else "sync_error",
                             company_id=company_id, company_name=company_name,
                             financial_year=fy, source="busy", mode="quick")
        self.state.setdefault(company_id, {})["last_quick_sync"] = now_ist()
        save_sync_state(self.state)
        # v1.5.5 — Release pooled readers between quick syncs too.
        try:
            self.extractor.close_readers()
        except Exception:
            pass
        gc.collect()

    def poll_commands(self, company_id: str, company_name: str, fy: str):
        """Check and execute remote commands."""
        if not self.api:
            return
        commands = self.api.poll_commands()
        for cmd in commands:
            action = cmd.get("action", "") or cmd.get("command_type", "")
            cmd_company = cmd.get("company_id", "") or company_id
            if action == "resync":
                self.set_status("Remote resync command received")
                self.run_full_sync(cmd_company, company_name, fy)
                self.api.ack_command(cmd_company, action)
            elif action == "delete":
                self.set_status("Remote delete command — marking acknowledged")
                self.api.ack_command(cmd_company, action)


# ---------------------------------------------------------------------------
# GUI Application (tkinter) — Light themed, minimal RAM
# ---------------------------------------------------------------------------
def run_gui():
    """Launch the GUI application."""
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        logger.error("tkinter not available. Run in headless mode or install tk.")
        return

    agent = FlowraBusySyncAgent()

    root = tk.Tk()
    root.title(f"{APP_NAME} v{VERSION}")
    root.geometry("680x520")
    root.configure(bg="#f8fafc")
    root.resizable(True, True)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame", background="#f8fafc")
    style.configure("TLabel", background="#f8fafc", font=("Segoe UI", 9))
    style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1e293b")
    style.configure("Status.TLabel", font=("Segoe UI", 8), foreground="#64748b")
    style.configure("TButton", font=("Segoe UI", 9), padding=6)
    style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))

    # ── Variables ──
    status_var = tk.StringVar(value="Not connected")
    sync_status_var = tk.StringVar(value="Idle")

    def update_status(msg):
        status_var.set(msg)
        root.update_idletasks()

    agent.status_callback = update_status

    # ── Header ──
    header = ttk.Frame(root, padding=15)
    header.pack(fill="x")
    ttk.Label(header, text="FLOWRA", style="Title.TLabel").pack(side="left")
    ttk.Label(header, text=f"Busy Sync Agent v{VERSION}", style="Status.TLabel").pack(side="left", padx=(10, 0))

    # ── Login Frame ──
    login_frame = ttk.LabelFrame(root, text="Login to FLOWRA", padding=10)
    login_frame.pack(fill="x", padx=15, pady=(0, 10))

    ttk.Label(login_frame, text="Server:").grid(row=0, column=0, sticky="w", pady=2)
    url_entry = ttk.Entry(login_frame, width=40)
    url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=5)
    url_entry.insert(0, agent.config.get("backend_url", DEFAULT_BACKEND_URL))

    ttk.Label(login_frame, text="Username:").grid(row=1, column=0, sticky="w", pady=2)
    user_entry = ttk.Entry(login_frame, width=30)
    user_entry.grid(row=1, column=1, sticky="ew", pady=2, padx=5)
    user_entry.insert(0, agent.config.get("username", ""))

    ttk.Label(login_frame, text="Password:").grid(row=2, column=0, sticky="w", pady=2)
    pass_entry = ttk.Entry(login_frame, show="*", width=30)
    pass_entry.grid(row=2, column=1, sticky="ew", pady=2, padx=5)

    def do_login():
        ok = agent.login(url_entry.get().strip(), user_entry.get().strip(), pass_entry.get())
        if ok:
            update_status(f"Logged in — {len(agent.get_companies())} companies")
            refresh_companies()
        else:
            messagebox.showerror("Login Failed", "Check credentials and server URL.")

    ttk.Button(login_frame, text="Login", command=do_login, style="Accent.TButton").grid(row=2, column=2, padx=5)
    login_frame.columnconfigure(1, weight=1)

    # ── Busy Folder ──
    folder_frame = ttk.LabelFrame(root, text="Busy Data Folder", padding=10)
    folder_frame.pack(fill="x", padx=15, pady=(0, 10))

    folder_var = tk.StringVar(value=agent.config.get("busy_folder", ""))
    ttk.Entry(folder_frame, textvariable=folder_var, width=50, state="readonly").pack(side="left", fill="x", expand=True)

    def browse_folder():
        path = filedialog.askdirectory(title="Select Busy Data Folder")
        if path:
            folder_var.set(path)
            agent.set_busy_folder(path)
            fys = agent.get_fys()
            fy_combo["values"] = fys
            if fys:
                fy_combo.current(len(fys) - 1)
            update_status(f"FYs found: {fys}")

    ttk.Button(folder_frame, text="Browse", command=browse_folder).pack(side="right", padx=(5, 0))

    # ── Companies & Sync ──
    sync_frame = ttk.LabelFrame(root, text="Companies & Sync", padding=10)
    sync_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    # FY selector row
    fy_row = ttk.Frame(sync_frame)
    fy_row.pack(fill="x", pady=(0, 8))
    ttk.Label(fy_row, text="Financial Year:").pack(side="left")
    fy_var = tk.StringVar()
    fy_combo = ttk.Combobox(fy_row, textvariable=fy_var, state="readonly", width=15)
    fy_combo.pack(side="left", padx=(5, 10))

    def refresh_fys():
        fys = agent.get_fys()
        fy_combo["values"] = fys
        if fys:
            fy_combo.current(len(fys) - 1)  # default: latest FY
        else:
            fy_var.set("")

    ttk.Button(fy_row, text="Reload FYs", command=refresh_fys).pack(side="left")

    tree = ttk.Treeview(sync_frame, columns=("name", "status", "last_sync"),
                        show="headings", height=5)
    tree.heading("name", text="Company")
    tree.heading("status", text="Status")
    tree.heading("last_sync", text="Last Sync (IST)")
    tree.column("name", width=220)
    tree.column("status", width=100)
    tree.column("last_sync", width=180)
    tree.pack(fill="both", expand=True)

    def refresh_companies():
        tree.delete(*tree.get_children())
        for c in agent.get_companies():
            cid = c.get("company_id", "")
            name = c.get("company_name", cid[:30]) or cid[:30]
            state = agent.state.get(cid, {})
            last = state.get("last_full_sync", "Never")
            if last and last != "Never":
                try:
                    last = datetime.fromisoformat(last).astimezone(IST).strftime("%d-%b %I:%M %p")
                except Exception:
                    pass
            tree.insert("", "end", iid=cid, values=(name, "Idle", last))

    btn_frame = ttk.Frame(sync_frame)
    btn_frame.pack(fill="x", pady=(5, 0))

    def _selected_company():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select Company", "Select a company row first")
            return None, None
        cid = sel[0]
        name = tree.item(cid, "values")[0] if tree.item(cid, "values") else cid
        return cid, name

    def _current_fy():
        fy = fy_var.get().strip()
        if not fy:
            messagebox.showerror("No FY", "No FY data available. Check your Busy folder.")
            return None
        return fy

    def do_sync():
        cid, cname = _selected_company()
        if not cid:
            return
        fy = _current_fy()
        if not fy:
            return
        tree.set(cid, "status", "Syncing...")

        def sync_thread():
            try:
                agent.run_full_sync(cid, cname, fy)
                tree.set(cid, "status", "Done")
                tree.set(cid, "last_sync", now_ist_display())
            except Exception as e:
                logger.exception("Full sync crashed")
                tree.set(cid, "status", "Error")
                update_status(f"Sync error: {e}")

        threading.Thread(target=sync_thread, daemon=True).start()

    def do_quick_sync():
        cid, cname = _selected_company()
        if not cid:
            return
        fy = _current_fy()
        if not fy:
            return
        threading.Thread(
            target=lambda: agent.run_quick_sales_sync(cid, cname, fy),
            daemon=True,
        ).start()

    ttk.Button(btn_frame, text="Full Sync", command=do_sync, style="Accent.TButton").pack(side="left", padx=(0, 5))
    ttk.Button(btn_frame, text="Quick Sales Sync", command=do_quick_sync).pack(side="left", padx=(0, 5))
    ttk.Button(btn_frame, text="Refresh", command=lambda: (refresh_companies(), refresh_fys())).pack(side="right")

    # ── Status Bar ──
    status_bar = ttk.Frame(root, padding=(15, 5))
    status_bar.pack(fill="x", side="bottom")
    ttk.Label(status_bar, textvariable=status_var, style="Status.TLabel").pack(side="left")
    ttk.Label(status_bar, textvariable=sync_status_var, style="Status.TLabel").pack(side="right")

    # Auto-load saved config
    if agent.config.get("busy_folder"):
        agent.set_busy_folder(agent.config["busy_folder"])
        refresh_fys()

    root.mainloop()


def _check_busy_drivers_or_banner(folder: str) -> bool:
    """v1.4.2 daemon-side pre-flight. Returns True if at least one of the
    two supported connection paths is usable. Otherwise logs a big, clear
    multi-line banner and returns False so run_daemon can bail cleanly
    (no stack trace, no 20-min retry cycle grinding the log)."""
    if sys.platform != "win32":
        # Non-Windows dev boxes → let the existing mdb-export path handle it.
        return True

    # Probe OLE DB (BSSData COM provider)
    oledb_ok = False
    oledb_err = ""
    try:
        import win32com.client
        for provider in ("BSSData.6.0", "BSSData.5.0", "BSSData.4.0"):
            try:
                conn = win32com.client.Dispatch("ADODB.Connection")
                conn_str = f"Provider={provider};Data Source={folder};"
                conn.Open(conn_str)
                oledb_ok = True
                try:
                    conn.Close()
                except Exception:
                    pass
                break
            except Exception as e:
                oledb_err = str(e)[:200]
                continue
    except ImportError:
        oledb_err = "pywin32 not bundled"

    # Probe ODBC (Microsoft Access Database Engine)
    odbc_ok = False
    odbc_err = ""
    try:
        import pyodbc
        drivers = pyodbc.drivers() or []
        odbc_ok = any("Access Driver" in d for d in drivers)
        if not odbc_ok:
            odbc_err = "Microsoft Access Database Engine driver is not installed"
    except ImportError:
        odbc_err = "pyodbc not bundled"

    if oledb_ok or odbc_ok:
        logger.info(
            f"[daemon] Driver check OK — "
            f"OLE DB {'available' if oledb_ok else 'unavailable'}, "
            f"ODBC {'available' if odbc_ok else 'unavailable'}."
        )
        return True

    # Both missing — big obvious banner.
    banner = [
        "",
        "==============================================================================",
        "  ⛔  BUSY SYNC AGENT — REQUIRED DRIVER NOT INSTALLED",
        "==============================================================================",
        "",
        "  FLOWRA cannot open your Busy .bds files because NEITHER of the two",
        "  supported drivers is installed on this PC:",
        "",
        f"    ✗  OLE DB (BSSData) provider     →  {oledb_err or 'not registered'}",
        f"    ✗  Microsoft Access ODBC driver  →  {odbc_err or 'not installed'}",
        "",
        "  Install ANY ONE of the following, then restart the FLOWRA agent:",
        "",
        "  Option A  (fastest, ~90 seconds, free)",
        "  ────────────────────────────────────────",
        "  1. Open this URL in a browser:",
        "     https://www.microsoft.com/en-us/download/details.aspx?id=54920",
        "  2. Download 'AccessDatabaseEngine_X64.exe'.",
        "  3. Run it. Accept defaults. Reboot not needed.",
        "  4. Right-click the FLOWRA tray icon → Quit, then relaunch it.",
        "",
        "  Option B  (preferred long-term — requires Busy paid add-on)",
        "  ────────────────────────────────────────────────────────────",
        "  1. In BusyWin: Administration → Configuration → Data Connectivity",
        "     → Enable. (Requires the Data Connectivity module on your licence.)",
        "  2. Restart Busy and the FLOWRA agent.",
        "",
        "  Tip: click the '🧪 Test Busy Connection' button in the FLOWRA Settings",
        "  tab (Section 2) any time to re-check driver status without starting",
        "  a full sync.",
        "",
        "==============================================================================",
        "",
    ]
    for line in banner:
        logger.error(line)
    return False



def _fy_key(fy: str) -> int:
    """Parse 'YYYY-YY' → sortable integer starting-year. Returns -1 on
    malformed inputs so they sort to the front (and get quietly skipped
    upstream)."""
    try:
        return int(fy.split("-")[0])
    except (ValueError, AttributeError, IndexError):
        return -1


def _fys_from_start(available: List[str], start_fy: str) -> List[str]:
    """v1.5.2 — Return every FY from `start_fy` onwards (inclusive), in
    chronological order. Used by the daemon to sync ALL live FYs on
    every tick instead of the single start_fy (which was the v1.5.1
    bug: users who set start_fy=2024-25 never saw 2025-26 or 2026-27
    data reach FLOWRA)."""
    if not available:
        return []
    start_k = _fy_key(start_fy)
    return sorted(
        (fy for fy in available if _fy_key(fy) >= start_k),
        key=_fy_key,
    )


def run_daemon() -> int:
    """Headless daemon mode. Reads env vars set by the GUI subprocess and
    runs the sync loop on the configured interval until killed.

    Required env vars:
      BACKEND_URL, FLOWRA_EMAIL, FLOWRA_PASSWORD,
      BUSY_DATA_FOLDER, BUSY_COMPANY, BUSY_STARTING_FY,
      SYNC_INTERVAL_MINUTES  (default: 20)
    """
    import time as _time

    backend  = os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL)
    email    = os.environ.get("FLOWRA_EMAIL", "")
    password = os.environ.get("FLOWRA_PASSWORD", "")
    folder   = os.environ.get("BUSY_DATA_FOLDER", "")
    company  = os.environ.get("BUSY_COMPANY", "")
    start_fy = os.environ.get("BUSY_STARTING_FY", "")
    try:
        interval_min = max(1, int(os.environ.get("SYNC_INTERVAL_MINUTES", "20")))
    except Exception:
        interval_min = 20

    logger.info(f"[daemon] boot. backend={backend} email={email} "
                f"folder={folder} company={company} start_fy={start_fy} "
                f"interval={interval_min}min")

    if not (email and password and folder and company and start_fy):
        _missing = [k for k, v in (
            ("FLOWRA_EMAIL", email),
            ("FLOWRA_PASSWORD", password),
            ("BUSY_DATA_FOLDER", folder),
            ("BUSY_COMPANY", company),
            ("BUSY_STARTING_FY", start_fy),
        ) if not v]
        logger.error(
            f"[daemon] Missing required env vars — cannot start. "
            f"Missing: {', '.join(_missing)}. Set them in the GUI Settings "
            "tab then click Save & Start Sync.")
        return 1

    agent = FlowraBusySyncAgent(status_callback=lambda m: logger.info(f"[daemon] {m}"))
    agent.config["backend_url"] = backend
    agent.config["busy_folder"] = folder
    agent.set_busy_folder(folder)

    if not agent.login(email, password):
        logger.error("[daemon] Login failed. Retrying every 5 minutes…")
        # Retry indefinitely — user may be offline temporarily.
        while True:
            _time.sleep(300)
            if agent.login(email, password):
                break

    logger.info(f"[daemon] logged in as {email}. Entering sync loop.")

    # v1.4.2 — Pre-flight driver check. Detects the "Both drivers missing"
    # scenario BEFORE trying to open a .bds file, so users see a clear
    # banner instead of a Python stack trace buried in the logs.
    _drv_ok = _check_busy_drivers_or_banner(folder)
    if not _drv_ok:
        logger.error("[daemon] Refusing to enter sync loop — install a "
                      "driver from the banner above, then restart the agent.")
        return 2

    # v1.5.4 — Resolve the human-readable company display name from the
    # Busy master DB. Falls back to the folder id (e.g. `COMP0002`) on
    # older Busy builds that don't ship a `Cmpny` / `Company1` table.
    # An explicit BUSY_COMPANY_DISPLAY_NAME env var (from GUI Settings)
    # trumps the auto-detection so users can override edge cases.
    override = os.environ.get("BUSY_COMPANY_DISPLAY_NAME", "").strip()
    try:
        if override:
            company_display = override
        elif agent.extractor is not None:
            company_display = agent.extractor.get_company_display_name(company)
        else:
            company_display = company
    except Exception as e:
        logger.warning(f"[daemon] Display-name resolution failed ({e}); "
                       f"using folder id '{company}' instead.")
        company_display = company
    logger.info(
        f"[daemon] Company identifier — folder='{company}' display='{company_display}'"
    )

    quick_every_min = 5   # sales delta
    tick = 0
    while True:
        try:
            # v1.5.2 — Sync ALL FYs from start_fy onwards (was previously
            # syncing only the single start_fy, so newer FYs never landed).
            available = agent.available_fys()
            fys_to_sync = _fys_from_start(available, start_fy)
            if not fys_to_sync:
                fys_to_sync = [start_fy]
            logger.info(f"[daemon] FYs queued this tick: {fys_to_sync}")

            # Full sync every `interval_min` minutes; quick sync every 5 min.
            for fy in fys_to_sync:
                if tick % (interval_min // quick_every_min or 1) == 0:
                    logger.info(f"[daemon] Starting full sync for {company_display} | FY {fy}")
                    agent.run_full_sync(company, company_display, fy, force=False)
                else:
                    logger.info(f"[daemon] Quick sales sync {company_display} | FY {fy}")
                    agent.run_quick_sales_sync(company, company_display, fy)
        except Exception as e:
            logger.exception(f"[daemon] sync tick failed: {e}")
        tick += 1
        _time.sleep(quick_every_min * 60)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n  {APP_NAME} v{VERSION}")
    print("  All times in IST (Asia/Kolkata)\n")

    if "--daemon" in sys.argv:
        # Headless scheduled loop driven by env vars (launched by the GUI
        # or by the frozen .exe with --run-agent).
        raise SystemExit(run_daemon())
    elif "--headless" in sys.argv:
        agent = FlowraBusySyncAgent()
        logger.info("Running in headless mode. Use --gui for graphical interface.")
    elif "--legacy-gui" in sys.argv:
        run_gui()
    else:
        # v1.2 — launch the new Tally-parity GUI (Status/Settings/Logs/About)
        try:
            from flowra_busy_gui import main as _gui_main
            _gui_main()
        except Exception as e:
            logger.warning(f"New GUI unavailable ({e}); falling back to legacy shell")
            run_gui()
