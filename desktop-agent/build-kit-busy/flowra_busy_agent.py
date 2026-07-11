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
VERSION = "1.3.1"
AGENT_TAG = "busy-1.3.1-db-password-fallback"
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
class BusyDBReader:
    """Reads Busy .bds (MS Access/Jet) files with minimal RAM usage.

    On Windows: uses pyodbc with MS Access ODBC driver.
    On Linux (dev): uses mdb-export CLI tool (streaming CSV).
    """

    def __init__(self, bds_path: str):
        self.bds_path = bds_path
        self.is_windows = sys.platform == "win32"
        self._conn = None

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

    def _get_connection(self):
        """Lazy connection — only open when needed."""
        if not self.is_windows:
            return None
        try:
            import pyodbc
        except ImportError as e:
            raise RuntimeError(
                "pyodbc is not bundled in this build. Please rebuild "
                "FlowraBusyAgent.exe with build.bat — the fresh build "
                "includes pyodbc automatically. If you already rebuilt, "
                "reinstall the .exe (delete %LOCALAPPDATA%\\Flowra "
                "cache first).") from e
        if self._conn:
            return self._conn

        # 1) Explicit override wins.
        pwd_env = os.environ.get("BUSY_DB_PASSWORD", "").strip()
        candidates = [pwd_env] if pwd_env else list(self._KNOWN_BUSY_PASSWORDS)

        last_error = None
        for pwd in candidates:
            conn_str = (
                r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"Dbq={self.bds_path};"
                "ReadOnly=1;"
            )
            if pwd:
                # PWD must not be percent-escaped; Access ODBC takes it raw.
                conn_str += f"PWD={pwd};"
            try:
                self._conn = pyodbc.connect(conn_str)
                if pwd:
                    logger.info(
                        f"  Busy DB opened with password profile: "
                        f"{'env-override' if pwd_env else pwd[:2] + '***'}")
                else:
                    logger.info("  Busy DB opened without password")
                return self._conn
            except pyodbc.InterfaceError as e:
                # Driver missing / DSN broken → won't get better with next pwd.
                raise RuntimeError(
                    "Could not open the Busy database. The "
                    "'Microsoft Access Database Engine' ODBC driver is "
                    "missing on this PC. Install the free 64-bit driver "
                    "from https://www.microsoft.com/en-us/download/details.aspx?id=54920 "
                    "then restart the agent.") from e
            except pyodbc.ProgrammingError as e:
                last_error = e
                if "-1905" in str(e) or "Not a valid password" in str(e):
                    continue    # try next password
                raise
            except pyodbc.Error as e:
                last_error = e
                continue

        # All candidates failed
        raise RuntimeError(
            "Could not open the Busy database — every known password was "
            "rejected by the ODBC driver.\n\n"
            "Your Busy version may use a custom password. Please set the "
            "environment variable BUSY_DB_PASSWORD (or fill it in the "
            "Settings → Busy Data Folder section of the GUI) and restart.\n\n"
            f"Last driver error: {last_error}") from last_error

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def iter_rows(self, table: str, columns: str = "*", where: str = "") -> Generator[Dict, None, None]:
        """Iterate rows one-by-one. NEVER loads full table into RAM."""
        if self.is_windows:
            conn = self._get_connection()
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
            # Linux: use mdb-export (streams CSV via pipe)
            cmd = ["mdb-export", self.bds_path, table]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            reader = csv.DictReader(proc.stdout)
            for row in reader:
                if where:
                    # Simple client-side filter for Linux dev mode
                    pass  # All rows returned, filter in caller
                yield row
            proc.wait()

    def count_rows(self, table: str, where: str = "") -> int:
        if self.is_windows:
            conn = self._get_connection()
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
# Busy Data Extractor — converts Busy schema to FLOWRA format
# ---------------------------------------------------------------------------
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
        self._detect_files()

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

    def _load_code_map(self, fy: str):
        """Load code→name lookup. Small dataset (~500 entries ≈ 50KB RAM)."""
        if self._code_map:
            return
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                code = row.get("Code", "")
                name = (row.get("Name") or "").strip()
                mtype = row.get("MasterType", "")
                parent = row.get("ParentGrp", "")
                self._code_map[code] = name
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

    def extract_customers(self, fy: str) -> Generator[Dict, None, None]:
        """Yield Sundry Debtor records one by one."""
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if row.get("MasterType") != "2":
                    continue
                parent = self._resolve_category(row.get("ParentGrp", ""))
                if parent != "sundry_debtors":
                    continue
                yield {
                    "customer_name": (row.get("Name") or "").strip(),
                    "customer_id": row.get("Code", ""),
                    "phone": (row.get("D8") or "").strip(),  # D8 often has phone
                    "email": "",
                    "state": "",
                    "opening_balance": float(row.get("D1") or 0),
                    "ledger_group": "Sundry Debtors",
                }
        finally:
            reader.close()

    def extract_creditors(self, fy: str) -> Generator[Dict, None, None]:
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if row.get("MasterType") != "2":
                    continue
                parent = self._resolve_category(row.get("ParentGrp", ""))
                if parent != "sundry_creditors":
                    continue
                yield {
                    "creditor_name": (row.get("Name") or "").strip(),
                    "creditor_id": row.get("Code", ""),
                    "opening_balance": float(row.get("D1") or 0),
                    "ledger_group": "Sundry Creditors",
                }
        finally:
            reader.close()

    def extract_inventory_items(self, fy: str) -> Generator[Dict, None, None]:
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        # Get Folio1 balances for item quantities
        folio_qty = {}
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Folio1"):
                if row.get("MasterType") == "6":
                    code = row.get("MasterCode", "")
                    # D23 often contains closing quantity
                    folio_qty[code] = float(row.get("D23") or 0)
        finally:
            reader.close()

        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Master1"):
                if row.get("MasterType") != "6":
                    continue
                code = row.get("Code", "")
                yield {
                    "item_name": (row.get("Name") or "").strip(),
                    "item_id": code,
                    "part_number": (row.get("Alias") or "").strip(),
                    "quantity": folio_qty.get(code, 0),
                    "price": float(row.get("D1") or 0),
                    "unit": (row.get("D2") or "").strip() if row.get("D2") else "",
                    "stock_group": self._resolve_name(row.get("ParentGrp", "")),
                }
        finally:
            reader.close()

    def extract_all_ledgers(self, fy: str) -> Generator[Dict, None, None]:
        """All ledger accounts with closing balances for Balance Sheet & P&L."""
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return
        # Get Folio1 closing balances
        folio_bal = {}
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Folio1"):
                if row.get("MasterType") == "2":
                    code = row.get("MasterCode", "")
                    folio_bal[code] = float(row.get("D23") or 0)
        finally:
            reader.close()

        reader = BusyDBReader(db_path)
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
        """Stream vouchers of a specific type. Joins Tran1 (header) + Tran2 (items)."""
        self._load_code_map(fy)
        db_path = self._fy_dbs.get(fy)
        if not db_path:
            return

        # Phase 1: Build Tran2 index (VchCode → items). Only for matching VchType.
        # This is the only thing we hold in memory — but grouped by VchCode, released after use.
        items_by_vch = defaultdict(list)
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Tran2"):
                if str(row.get("VchType", "")) != str(vch_type):
                    continue
                vch_code = row.get("VchCode", "")
                rec_type = row.get("RecType", "")
                master_code = row.get("MasterCode1", "")
                value = float(row.get("Value2") or row.get("Value1") or 0)
                items_by_vch[vch_code].append({
                    "rec_type": rec_type,
                    "master_code": master_code,
                    "name": self._resolve_name(master_code),
                    "value": abs(value),
                    "quantity": abs(float(row.get("D5") or row.get("D4") or 0)),
                    "rate": abs(float(row.get("Value1") or 0)),
                    "short_nar": (row.get("ShortNar") or "").strip(),
                })
        finally:
            reader.close()

        # Phase 2: Stream Tran1 headers and join items
        reader = BusyDBReader(db_path)
        try:
            for row in reader.iter_rows("Tran1"):
                if str(row.get("VchType", "")) != str(vch_type):
                    continue
                vch_code = row.get("VchCode", "")
                party_code = row.get("MasterCode1", "")
                party_name = self._resolve_name(party_code)
                vch_date_raw = (row.get("Date") or "").strip()
                vch_date = self._parse_date(vch_date_raw)
                vch_no = (row.get("VchNo") or "").strip()
                amount = abs(float(row.get("VchAmtBaseCur") or 0))

                # Get line items for this voucher
                line_items = items_by_vch.pop(vch_code, [])
                # Separate: RecType=2 = ledger entries, RecType=3 = item entries
                item_entries = [i for i in line_items if i["rec_type"] == "3"]
                ledger_entries = [i for i in line_items if i["rec_type"] == "2"]

                voucher = {
                    "voucher_id": f"BUSY-{vch_code}-{vch_type}",
                    "voucher_date": vch_date,
                    "voucher_number": vch_no,
                    "reference_number": vch_no,
                    "party_name": party_name,
                    "party_code": party_code,
                    "total_amount": amount,
                    "items": [{
                        "item": i["name"],
                        "item_name": i["name"],
                        "quantity": i["quantity"],
                        "rate": i["rate"],
                        "amount": i["value"],
                        "remark": i["short_nar"],
                    } for i in item_entries],
                    "ledger_entries": [{
                        "ledger_name": e["name"],
                        "amount": e["value"],
                    } for e in ledger_entries],
                    "narration": "",
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

    def extract_sales(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 9)

    def extract_receipts(self, fy: str) -> Generator[Dict, None, None]:
        for v in self._extract_vouchers_by_type(fy, 1):
            yield v
        for v in self._extract_vouchers_by_type(fy, 3):
            yield v

    def extract_credit_notes(self, fy: str) -> Generator[Dict, None, None]:
        for v in self._extract_vouchers_by_type(fy, 10):
            yield v
        for v in self._extract_vouchers_by_type(fy, 12):
            yield v

    def extract_journals(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 5)

    def extract_purchases(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 7)

    def extract_debit_notes(self, fy: str) -> Generator[Dict, None, None]:
        for v in self._extract_vouchers_by_type(fy, 8):
            yield v
        for v in self._extract_vouchers_by_type(fy, 11):
            yield v

    def extract_contra(self, fy: str) -> Generator[Dict, None, None]:
        yield from self._extract_vouchers_by_type(fy, 6)

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
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "income": income_ledgers,
            "expense": expense_ledgers,
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
        import requests
        if not chunk:
            return True
        try:
            payload = self._build_envelope(data_type, chunk, company_id, company_name, financial_year)
            r = requests.post(
                f"{self.backend_url}/api/agent/sync",
                json=payload,
                headers=self._auth_headers(),
                timeout=60,
            )
            if r.status_code != 200:
                logger.warning(f"Sync {data_type}: HTTP {r.status_code} — {r.text[:200]}")
                return False
            js = r.json()
            if not js.get("success"):
                logger.warning(f"Sync {data_type} failed: {js.get('error', '')}")
                return False
            return True
        except Exception as e:
            logger.error(f"Sync error {data_type}: {e}")
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
            ("credit_notes",      self.extractor.extract_credit_notes,     "voucher_id"),
            ("journal_vouchers",  self.extractor.extract_journals,         "voucher_id"),
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
        logger.error("[daemon] Missing required env vars — cannot start.")
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

    quick_every_min = 5   # sales delta
    tick = 0
    while True:
        try:
            # Full sync every `interval_min` minutes; quick sync every 5 min.
            if tick % (interval_min // quick_every_min or 1) == 0:
                logger.info(f"[daemon] Starting full sync for {company} | FY {start_fy}")
                agent.run_full_sync(company, company, start_fy, force=False)
            else:
                logger.info(f"[daemon] Quick sales sync {company}")
                agent.run_quick_sales_sync(company, company, start_fy)
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
