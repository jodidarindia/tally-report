#!/usr/bin/env python3
"""
FLOWRA Tally Sync Agent v9 — Deletion Reconciliation, Cash Flow, P&L, FY Discovery, Encrypted Config

v9 Changes (Apr 2026):
  - DELETION RECONCILIATION: After syncing each data type, sends manifest of all IDs
    to backend. Backend deletes any orphan records not in the manifest.
    Fixes ghost data when invoices/items/customers are deleted in Tally.
  - Scoped by tenant_id + company_id + financial_year for full data isolation
  - New reconcile_with_backend() method for Option B reconciliation
  - All other v8 features retained

v8 Changes (Apr 2026):
  - FY discovery: detects all available FYs from Tally, asks user to select starting FY
  - Contra vouchers: fetches bank-to-bank, cash-to-bank transfers
  - Bank/Cash ledger balances: opening/closing for all bank + cash accounts
  - P&L data: all Income and Expense group ledgers with balances
  - Encrypted local config: tenant_id, company_id, auth token encrypted with Fernet
  - Memory optimized: chunked processing, generators, explicit gc.collect()

v7 Changes (Apr 2026):
  - Fetches purchase_vouchers for true cost price analysis
  - Fetches debit_notes for return tracking
  - Fetches sundry_creditors for supplier analysis
  - Customer opening_balance from Tally ledger (for FY-based payment behavior)
  - Login-based auth (no manual tenant/sync token config)

Setup:
  1. pip install requests xmltodict python-dotenv schedule websockets cryptography
  2. Create .env from .env.example
  3. python tally_sync_agent_v9.py
"""

import os
import sys
import io
import re
import gc
import time
import json
import logging
import asyncio
import hashlib
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional
import requests
import xmltodict
import schedule
from dotenv import load_dotenv

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tally_sync_agent.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('FlowraSyncV9')
load_dotenv()


# ==================== CONFIG ====================

TALLY_HOST = os.getenv('TALLY_HOST', 'localhost')
TALLY_PORT = int(os.getenv('TALLY_PORT', '9000'))
TALLY_URL = f"http://{TALLY_HOST}:{TALLY_PORT}/"
COMPANY_NAME = os.getenv('TALLY_COMPANY', '')  # Leave empty for current company
BACKEND_URL = os.getenv('BACKEND_URL', '')  # Will be set during login if not provided
FINANCIAL_YEAR = os.getenv('FINANCIAL_YEAR', '2025-26')
SYNC_ALL_FY = os.getenv('SYNC_ALL_FY', 'true').lower() == 'true'
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL_MINUTES', '20'))
SALES_SYNC_INTERVAL = int(os.getenv('SALES_SYNC_INTERVAL_MINUTES', '5'))
INCREMENTAL_SYNC = os.getenv('INCREMENTAL_SYNC', 'true').lower() == 'true'
EXPORT_DIR = os.getenv('TALLY_EXPORT_DIR', os.path.join(os.path.dirname(__file__), 'export_cache'))
ENABLE_WS = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
WS_PORT = int(os.getenv('WEBSOCKET_PORT', '8765'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
SLEEP_BETWEEN_REQUESTS = float(os.getenv('SLEEP_BETWEEN_REQUESTS', '2'))
SYNC_ALL_COMPANIES = os.getenv('SYNC_ALL_COMPANIES', 'false').lower() == 'true'

SYNC_STATE_FILE = 'sync_state_v9.json'
AUTH_CONFIG_FILE = 'flowra_auth.enc'  # Encrypted auth config
ENCRYPTION_KEY_FILE = '.flowra_key'  # Machine-specific encryption key


def _get_encryption_key() -> bytes:
    """Get or generate machine-specific Fernet key."""
    if not HAS_CRYPTO:
        return b''
    key_path = Path(ENCRYPTION_KEY_FILE)
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    # Hide the key file on Windows
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(key_path), 0x02)
        except Exception:
            pass
    return key


def load_auth_config():
    """Load and decrypt saved auth session from local file."""
    if not os.path.exists(AUTH_CONFIG_FILE):
        return None
    try:
        raw = Path(AUTH_CONFIG_FILE).read_bytes()
        if HAS_CRYPTO:
            key = _get_encryption_key()
            f = Fernet(key)
            decrypted = f.decrypt(raw)
            config = json.loads(decrypted)
        else:
            config = json.loads(raw)
        # Check expiry
        saved_at = config.get('saved_at', '')
        if saved_at:
            saved_time = datetime.fromisoformat(saved_at)
            if (datetime.now() - saved_time).total_seconds() > 23 * 3600:
                logger.info("Saved auth session expired, re-login needed")
                return None
        return config
    except Exception as e:
        logger.warning(f"Could not load auth config: {e}")
    return None


def save_auth_config(config: dict):
    """Encrypt and save auth session to local file."""
    config['saved_at'] = datetime.now().isoformat()
    data = json.dumps(config, indent=2).encode()
    if HAS_CRYPTO:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(data)
        Path(AUTH_CONFIG_FILE).write_bytes(encrypted)
    else:
        Path(AUTH_CONFIG_FILE).write_bytes(data)
    logger.info(f"Auth session saved (encrypted={HAS_CRYPTO})")


def clear_auth_config():
    """Remove saved auth session and key."""
    for f in (AUTH_CONFIG_FILE, ENCRYPTION_KEY_FILE):
        if os.path.exists(f):
            os.remove(f)
    logger.info("Auth session and encryption key cleared")


def load_sync_state():
    if os.path.exists(SYNC_STATE_FILE):
        with open(SYNC_STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_sync_state(state):
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)


def fy_to_dates(fy: str):
    """Convert '2025-26' to (date(2025,4,1), date(2026,3,31))"""
    parts = fy.split('-')
    start_year = int(parts[0])
    end_short = int(parts[1])
    end_year = start_year // 100 * 100 + end_short if end_short < 100 else end_short
    return date(start_year, 4, 1), date(end_year, 3, 31)


def months_in_fy(fy: str, cap_date: date = None):
    """Generate monthly (start, end) date pairs for an FY.
    cap_date: if provided, stop at this date instead of today (for latest FY)."""
    fy_start, fy_end = fy_to_dates(fy)
    end_limit = cap_date if cap_date else date.today()
    end_limit = min(fy_end, end_limit)
    current = fy_start
    while current <= end_limit:
        month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        month_end = min(month_end, fy_end, end_limit)
        yield current, month_end
        current = (month_end + timedelta(days=1))


def current_fy() -> str:
    """Get the current financial year string (e.g. '2026-27' if today is April 2026)."""
    today = date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    end_short = (start_year + 1) % 100
    return f"{start_year}-{end_short:02d}"


def get_sync_fys() -> list:
    """Return list of FYs to sync: configured FY + current FY (if different)."""
    fys = [FINANCIAL_YEAR]
    cur = current_fy()
    if SYNC_ALL_FY and cur != FINANCIAL_YEAR and cur not in fys:
        fys.append(cur)
    return fys


# ==================== WEBSOCKET SERVER ====================

class WebSocketServer:
    def __init__(self, port=8765):
        self.port = port
        self.clients = set()
        self.loop = None
        self.thread = None

    def start(self):
        if not HAS_WEBSOCKETS:
            logger.warning("websockets not installed — pip install websockets")
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._serve())

    async def _serve(self):
        async with websockets.serve(self._handler, "0.0.0.0", self.port):
            logger.info(f"WebSocket server on ws://localhost:{self.port}")
            await asyncio.Future()

    async def _handler(self, websocket, path=None):
        self.clients.add(websocket)
        try:
            async for msg in websocket:
                pass
        except:
            pass
        finally:
            self.clients.discard(websocket)

    def broadcast(self, data: dict):
        if not self.loop or not self.clients:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self.loop)

    async def _broadcast(self, data: dict):
        msg = json.dumps(data, default=str)
        dead = set()
        for c in self.clients:
            try:
                await c.send(msg)
            except:
                dead.add(c)
        self.clients -= dead


# ==================== TALLY XML REQUESTS ====================

class TallyCollectionClient:
    """Makes lightweight Collection requests to Tally's HTTP server.
    Each request takes 1-5 seconds (vs 30-120 sec for report requests)."""

    def __init__(self, url=TALLY_URL, company='', timeout=15, debug_dir=None):
        self.url = url
        self.company = company
        self.timeout = timeout
        self.debug_dir = debug_dir
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'text/xml',
            'Cache-Control': 'no-cache'
        })

    def _sanitize(self, xml_text):
        """Clean XML to handle Tally's encoding quirks."""
        # Remove control characters
        xml_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', xml_text)
        # Remove ALL numeric character references (Tally generates invalid ones like &#1;)
        xml_text = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', xml_text)
        xml_text = re.sub(r'&#[0-9]+;?', ' ', xml_text)
        # Fix unescaped & (addresses, party names like "A & B Traders")
        xml_text = re.sub(r'&(?!(?:amp|lt|gt|apos|quot);)', '&amp;', xml_text)
        return xml_text

    def _aggressive_sanitize(self, xml_text):
        """Nuclear cleanup for stubborn Tally XML responses."""
        xml_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', xml_text)
        xml_text = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', xml_text)
        xml_text = re.sub(r'&#[0-9]+;?', ' ', xml_text)
        xml_text = re.sub(r'&(?!(?:amp|lt|gt|apos|quot);)', '&amp;', xml_text)
        # Strip CDATA wrappers if malformed
        xml_text = re.sub(r'<!\[CDATA\[.*?\]\]>', '', xml_text, flags=re.DOTALL)
        # Remove any stray < or > inside attribute values by finding broken tags
        # Replace non-XML chars in attribute values
        xml_text = re.sub(r'[\x80-\xff]', '', xml_text)
        return xml_text

    def _post(self, xml_payload: str, debug_name: str = '') -> Optional[dict]:
        try:
            resp = self.session.post(self.url, data=xml_payload, timeout=self.timeout)
            if resp.status_code == 200:
                raw = resp.text
                # Save raw response BEFORE sanitization for debugging
                if debug_name and self.debug_dir:
                    debug_path = os.path.join(self.debug_dir, f"{debug_name}_raw.xml")
                    with open(debug_path, 'w', encoding='utf-8') as f:
                        f.write(raw[:100000])
                    logger.info(f"  [DEBUG] Saved raw XML -> {debug_path}")

                # Check for Tally error responses first
                if '<LINEERROR>' in raw:
                    err = re.search(r'<LINEERROR>(.*?)</LINEERROR>', raw)
                    if err:
                        logger.error(f"  Tally error: {err.group(1)}")
                    return None

                # Try parsing with standard sanitization
                clean = self._sanitize(raw)
                try:
                    return xmltodict.parse(clean)
                except Exception as parse_err:
                    logger.warning(f"  XML parse error (attempt 1): {parse_err}")
                    # Fallback: aggressive sanitization
                    aggressive = self._aggressive_sanitize(raw)
                    try:
                        return xmltodict.parse(aggressive)
                    except Exception as e2:
                        logger.error(f"  XML parse failed after aggressive cleanup: {e2}")
                        return None
            else:
                logger.error(f"Tally HTTP {resp.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"Tally request timed out ({self.timeout}s)")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Tally — is it running?")
            return None
        except Exception as e:
            logger.error(f"Tally request error: {e}")
            return None

    def _company_tag(self):
        """Return SVCurrentCompany XML tag. Skip if company is unknown/Default — Tally will use the active company."""
        c = (self.company or '').strip()
        if c and c.lower() not in ('default', '##default', '_active_') and 'default' not in c.lower():
            return f"<SVCURRENTCOMPANY>{c}</SVCURRENTCOMPANY>"
        return ""

    def _ping_tally(self) -> bool:
        """Lightweight connection check — does NOT overwrite self.company.
        Just verifies Tally is responding with a minimal request."""
        try:
            company_tag = self._company_tag()
            xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>FlowraPing</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{company_tag}</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraPing" ISINITIALIZE="Yes"><TYPE>Company</TYPE><FETCH>NAME</FETCH></COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
            resp = requests.post(TALLY_URL, data=xml.encode('utf-8'),
                                 headers={'Content-Type': 'application/xml'},
                                 timeout=REQUEST_TIMEOUT)
            return resp.status_code == 200
        except Exception:
            return False

    def test_connection(self) -> bool:
        """Quick ping to check Tally is responding + detect active company name."""
        # Method 1: Collection request for company list
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>FlowraCompanyList</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraCompanyList" ISINITIALIZE="Yes">
<TYPE>Company</TYPE>
<FETCH>NAME, BASICCOMPANYFORMALNAME</FETCH>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
        data = self._post(xml, debug_name='companies')
        if not data:
            return False

        # Try to extract company name from collection response
        companies = self._get_collection_items(data, 'COMPANY')
        for c in companies:
            if isinstance(c, dict):
                # Try formal name first, then NAME
                for key in ('BASICCOMPANYFORMALNAME', 'NAME', '@NAME'):
                    name = c.get(key, '')
                    if isinstance(name, dict):
                        name = name.get('#text', '')
                    name = str(name).strip() if name else ''
                    if name and name.lower() not in ('default', '##default', ''):
                        self.company = name
                        break
                if self.company and self.company.lower() not in ('default', '##default'):
                    break

        # Method 2: If collection didn't yield a name, try TDL report for $$CurrentCompany
        if not self.company or self.company.lower() in ('default', '##default'):
            self.company = ''  # Reset
            try:
                xml2 = """<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE>
<ID>FlowraCurrentCompany</ID></HEADER>
<BODY><DESC><TDL><TDLMESSAGE>
<REPORT NAME="FlowraCurrentCompany"><FORMS>FCCForm</FORMS></REPORT>
<FORM NAME="FCCForm"><PARTS>FCCPart</PARTS></FORM>
<PART NAME="FCCPart"><LINES>FCCLine</LINES></PART>
<LINE NAME="FCCLine"><FIELDS>FCCField</FIELDS></LINE>
<FIELD NAME="FCCField"><SET>$$CurrentCompany</SET></FIELD>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""
                data2 = self._post(xml2)
                if data2:
                    # Extract text from the response — the company name is the field value
                    text = self._extract_text_deep(data2)
                    if text and text.lower() not in ('default', '##default', ''):
                        self.company = text
            except Exception as e:
                logger.debug(f"  CurrentCompany TDL failed: {e}")

        # Method 3: Try "List of Companies" report
        if not self.company or self.company.lower() in ('default', '##default'):
            self.company = ''
            try:
                xml3 = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
                data3 = self._post(xml3)
                if data3:
                    collection = data3.get('ENVELOPE', {}).get('BODY', {}).get('DATA', {}).get('COLLECTION', {})
                    if collection:
                        items = collection.get('COMPANY', [])
                        if isinstance(items, dict):
                            items = [items]
                        for item in items:
                            name = item.get('NAME', {}).get('#text', '') if isinstance(item.get('NAME'), dict) else item.get('NAME', '')
                            name = str(name).strip() if name else ''
                            if name and name.lower() not in ('default', '##default'):
                                self.company = name
                                break
            except Exception as e:
                logger.debug(f"  List of Companies failed: {e}")

        if self.company and self.company.strip().lower() not in ('default', '##default') and 'default' not in self.company.strip().lower():
            logger.info(f"  Tally company: {self.company}")
        else:
            self.company = ''
            logger.info("  Tally connected (company name will be detected from data)")
        return True

    def _extract_text_deep(self, d):
        """Recursively extract meaningful text from a nested dict/xml response."""
        if isinstance(d, str):
            d = d.strip()
            return d if d and d.lower() not in ('default', '##default', 'no', 'yes', '') else None
        if isinstance(d, dict):
            # Check #text first
            if '#text' in d:
                val = str(d['#text']).strip()
                if val and len(val) > 2 and val.lower() not in ('default', '##default'):
                    return val
            # Check FCCFIELD or any FIELD
            for key in ('FCCFIELD', 'FIELD', 'FCFFIELD'):
                if key in d:
                    return self._extract_text_deep(d[key])
            # Recurse into BODY, DATA, REPORT, FORM, PART, LINE
            for key in ('BODY', 'DATA', 'REPORT', 'FORM', 'PART', 'LINE', 'FIELD', 'COLLECTION', 'ENVELOPE'):
                if key in d:
                    result = self._extract_text_deep(d[key])
                    if result:
                        return result
        if isinstance(d, list):
            for item in d:
                result = self._extract_text_deep(item)
                if result:
                    return result
        return None

    def _find_deep(self, d, key):
        if isinstance(d, dict):
            if key in d:
                return d[key]
            for v in d.values():
                r = self._find_deep(v, key)
                if r is not None:
                    return r
        elif isinstance(d, list):
            for item in d:
                r = self._find_deep(item, key)
                if r is not None:
                    return r
        return None

    def _get_collection_items(self, data, tag_name):
        """Extract items from Collection response, navigating directly to
        BODY > DATA > COLLECTION > tag_name (skips CMPINFO counts)."""
        try:
            envelope = data.get('ENVELOPE', data)
            body = envelope.get('BODY', {}) if isinstance(envelope, dict) else {}
            coll_data = body.get('DATA', {}) if isinstance(body, dict) else {}
            collection = coll_data.get('COLLECTION', {}) if isinstance(coll_data, dict) else {}
            if not isinstance(collection, dict):
                return []
            items = collection.get(tag_name)
            if items is None:
                # Try with @NAME attribute pattern
                for k, v in collection.items():
                    if k.upper() == tag_name.upper():
                        items = v
                        break
            if items is None:
                logger.warning(f"  [DEBUG] COLLECTION keys: {list(collection.keys())}")
                return []
            if isinstance(items, dict):
                return [items]
            if isinstance(items, list):
                return items
            return []
        except Exception as e:
            logger.warning(f"  [DEBUG] _get_collection_items error: {e}")
            return []

    def _num(self, val):
        if val is None:
            return 0.0
        # Handle xmltodict dict format: {'#text': '14', '@TYPE': 'Number'}
        if isinstance(val, dict):
            val = val.get('#text', val.get('$', '0'))
        s = str(val).replace(',', '').strip()
        if not s or s in ('None', 'null'):
            return 0.0
        try:
            return abs(float(s.split()[0]))
        except:
            return 0.0

    def _signed_num(self, val):
        """Like _num but preserves sign — used for ledger entries where Tally encodes
        debit as negative and credit as positive in AMOUNT (or vice versa).
        """
        if val is None:
            return 0.0
        if isinstance(val, dict):
            val = val.get('#text', val.get('$', '0'))
        s = str(val).replace(',', '').strip()
        if not s or s in ('None', 'null'):
            return 0.0
        try:
            return float(s.split()[0])
        except:
            return 0.0

    def _safe_float(self, val):
        """Alias used by ledger-fetch helpers — preserves sign."""
        return self._signed_num(val)

    def _qty_unit(self, val):
        if val is None:
            return 0.0, 'Pcs'
        # Handle dict format
        if isinstance(val, dict):
            val = val.get('#text', val.get('$', ''))
        s = str(val).strip()
        if not s or s in ('None', 'null', '0'):
            return 0.0, 'Pcs'
        parts = s.split()
        try:
            qty = abs(float(parts[0].replace(',', '')))
        except:
            qty = 0.0
        unit = parts[1] if len(parts) > 1 else 'Pcs'
        return qty, unit

    def _format_date(self, raw):
        if raw and len(str(raw)) == 8 and str(raw).isdigit():
            d = str(raw)
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return str(raw) if raw else ''

    # ---- STOCK ITEMS (Collection with COMPUTE for closing balances) ----

    def fetch_stock_items(self) -> List[Dict]:
        """Fetch stock items with opening/closing balances using TDL Collection + COMPUTE."""
        logger.info("  Requesting stock items (Collection)...")
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>FlowraStockItems</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraStockItems" ISINITIALIZE="Yes">
<TYPE>Stock Item</TYPE>
<FETCH>NAME</FETCH>
<FETCH>PARENT</FETCH>
<FETCH>BASEUNITS</FETCH>
<FETCH>OPENINGBALANCE</FETCH>
<FETCH>PARTNUMBER</FETCH>
<FETCH>PARTNO</FETCH>
<FETCH>MAILINGNAME</FETCH>
<FETCH>STANDARDPRICE</FETCH>
<FETCH>STDPRICE</FETCH>
<COMPUTE>CLBAL : $$NumValue:$ClosingBalance</COMPUTE>
<COMPUTE>CLRATE : $$NumValue:$ClosingRate</COMPUTE>
<COMPUTE>CLVAL : $$NumValue:$ClosingValue</COMPUTE>
<COMPUTE>CLQTY : $$String:$ClosingBalance:"TailUnits"</COMPUTE>
<COMPUTE>OPBAL : $$NumValue:$OpeningBalance</COMPUTE>
<COMPUTE>OPRATE : $$NumValue:$OpeningRate</COMPUTE>
<COMPUTE>OPVAL : $$NumValue:$OpeningValue</COMPUTE>
<COMPUTE>OPQTY : $$String:$OpeningBalance:"TailUnits"</COMPUTE>
<COMPUTE>STDPRC : $$NumValue:$StandardPrice</COMPUTE>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name='stock_items')
        items = []
        stock_list = []
        if data:
            stock_list = self._get_collection_items(data, 'STOCKITEM')

        # Fallback: Export Data with Stock Summary
        if not stock_list:
            logger.info("  Collection returned 0 stock items, trying Stock Summary fallback...")
            xml2 = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Stock Summary</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""
            data2 = self._post(xml2, debug_name='stock_items_fb')
            if data2:
                raw = self._find_deep(data2, 'STOCKITEM')
                if raw:
                    stock_list = raw if isinstance(raw, list) else [raw]

        if not stock_list:
            logger.warning("  No stock items found from any method")
            return []

        for si in stock_list:
            if not isinstance(si, dict):
                continue
            name = si.get('NAME', si.get('@NAME', ''))
            if isinstance(name, dict):
                name = name.get('#text', '')
            name = str(name or '').strip()
            if not name:
                continue
            parent = si.get('PARENT', 'General')
            if isinstance(parent, dict):
                parent = parent.get('#text', 'General')
            parent = str(parent or 'General').strip()

            # Part Number — Tally uses $PartNo, also check PARTNUMBER and MAILINGNAME
            part_no = ''
            for pn_field in ('PARTNO', 'PARTNUMBER', 'PartNo'):
                raw = si.get(pn_field, '')
                if raw and raw != 'None':
                    if isinstance(raw, dict):
                        raw = raw.get('#text', '')
                    part_no = str(raw or '').strip()
                    if part_no and part_no.lower() not in ('none', '0', 'null'):
                        break
                    part_no = ''
            # Fallback: MAILINGNAME (can store part number as alias)
            if not part_no:
                mailing = si.get('MAILINGNAME', si.get('MAILINGNAME.LIST', ''))
                if mailing:
                    if isinstance(mailing, dict):
                        mailing = mailing.get('MAILINGNAME', mailing.get('#text', ''))
                    if isinstance(mailing, list):
                        mailing = mailing[0] if mailing else ''
                    if isinstance(mailing, dict):
                        mailing = mailing.get('#text', '')
                    mailing = str(mailing or '').strip()
                    if mailing and mailing.lower() not in ('none', name.lower()):
                        part_no = mailing

            # Try COMPUTE fields first (CLBAL, CLRATE, CLVAL)
            qty = self._num(si.get('CLBAL', 0))
            rate = self._num(si.get('CLRATE', 0))
            value = self._num(si.get('CLVAL', 0))

            # Opening balance from COMPUTE fields
            opening_qty = self._num(si.get('OPBAL', 0))
            opening_rate = self._num(si.get('OPRATE', 0))
            opening_value = self._num(si.get('OPVAL', 0))

            # Fallback to standard fields (for Export Data response)
            if qty == 0 and rate == 0:
                cb = si.get('CLOSINGBALANCE', 0)
                if cb:
                    qty_parsed, unit_parsed = self._qty_unit(cb)
                    qty = qty_parsed
                cr = si.get('CLOSINGRATE', 0)
                if cr:
                    rate = self._num(str(cr).split('/')[0])
                cv = si.get('CLOSINGVALUE', 0)
                if cv:
                    value = self._num(cv)

            if opening_qty == 0:
                ob = si.get('OPENINGBALANCE', 0)
                if ob:
                    opening_qty, _ = self._qty_unit(ob) if isinstance(ob, str) else (self._num(ob), 'Pcs')

            # Parse opening from OPQTY string
            opqty_str = si.get('OPQTY', '')
            if isinstance(opqty_str, str) and opqty_str.strip() and opening_qty == 0:
                parts = opqty_str.strip().split()
                if parts:
                    opening_qty = self._num(parts[0])

            # Determine unit from CLQTY string or BASEUNITS
            unit = 'Pcs'
            clqty = si.get('CLQTY', '')
            if isinstance(clqty, str) and clqty:
                # CLQTY format: "10.00 Nos" or "25.00 Lt."
                parts = clqty.strip().split()
                if len(parts) >= 2:
                    unit = parts[-1]
                    if qty == 0:
                        qty = self._num(parts[0])
            bu = si.get('BASEUNITS', '')
            if isinstance(bu, dict):
                bu = bu.get('#text', '')
            if bu and unit == 'Pcs':
                bu_str = str(bu).strip()
                if bu_str and bu_str not in ('None', '0'):
                    unit = bu_str

            if rate == 0 and qty > 0 and value > 0:
                rate = round(value / qty, 2)

            # Standard sale price (Tally STDPRICE master) — independent of stock
            # so even zero-qty items get a price for salesman quoting.
            std_price = self._num(si.get('STDPRC', 0))
            if std_price == 0:
                std_price = self._num(si.get('STANDARDPRICE', si.get('STDPRICE', 0)))
            if std_price == 0 and rate > 0:
                std_price = rate  # fallback to last closing rate

            items.append({
                'item_id': name, 'item_name': name,
                'part_number': part_no,
                'quantity': qty, 'unit': unit, 'price': rate,
                'standard_price': std_price,
                'category': parent, 'stock_group': parent,
                'reorder_level': 10.0,
                'opening_quantity': opening_qty,
                'opening_rate': opening_rate,
                'opening_value': opening_value,
                'closing_value': value,
            })

        logger.info(f"  Got {len(items)} stock items")
        return items

    # ---- LEDGERS / CUSTOMERS (Collection request — lightweight) ----

    def fetch_customers(self) -> List[Dict]:
        """Fetch Sundry Debtors using TDL Collection request. ~1-3 seconds."""
        logger.info("  Requesting customer ledgers (Collection)...")
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>FlowraDebtors</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraDebtors" ISINITIALIZE="Yes">
<TYPE>Ledger</TYPE>
<CHILDOF>Sundry Debtors</CHILDOF>
<BELONGSTO>Yes</BELONGSTO>
<FETCH>NAME</FETCH>
<FETCH>PARENT</FETCH>
<FETCH>LEDGERPHONE</FETCH>
<FETCH>LEDGERCONTACT</FETCH>
<FETCH>LEDSTATENAME</FETCH>
<COMPUTE>CLBAL : $$NumValue:$ClosingBalance</COMPUTE>
<COMPUTE>OPBAL : $$NumValue:$OpeningBalance</COMPUTE>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name='customers')
        if not data:
            return []

        customers = []
        # Navigate directly to DATA > COLLECTION > LEDGER (skip CMPINFO)
        ledgers = self._get_collection_items(data, 'LEDGER')
        if not ledgers:
            logger.warning("  Collection returned 0 customer ledgers")
            return []

        for l in ledgers:
            if not isinstance(l, dict):
                continue
            name = l.get('NAME', l.get('@NAME', ''))
            if isinstance(name, dict):
                name = name.get('#text', '')
            name = str(name or '').strip()
            if not name:
                continue
            parent = l.get('PARENT', 'Sundry Debtors')
            if isinstance(parent, dict):
                parent = parent.get('#text', 'Sundry Debtors')
            parent_str = str(parent or 'Sundry Debtors').strip()
            # Skip Branch / Divisions — these don't have receipts
            if 'branch' in parent_str.lower() or 'division' in parent_str.lower():
                continue
            customers.append({
                'customer_name': name,
                'ledger_group': parent_str,
                'outstanding_amount': self._num(l.get('CLBAL', l.get('CLOSINGBALANCE', 0))),
                'opening_balance': self._num(l.get('OPBAL', l.get('OPENINGBALANCE', 0))),
                'phone': str(l.get('LEDGERPHONE', '') or '').strip(),
                'contact_person': str(l.get('LEDGERCONTACT', '') or '').strip(),
                'state': str(l.get('LEDSTATENAME', '') or '').strip(),
                'total_purchases': 0.0,
                'transaction_count': 0
            })

        logger.info(f"  Got {len(customers)} customer ledgers")
        return customers

    # ---- SALES VOUCHERS (Export Data with enhanced sanitization) ----

    def fetch_sales_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch sales vouchers for one month using Export Data + Voucher Register."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting sales: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name=f'sales_{from_date.strftime("%Y%m")}')
        if not data:
            return []
        return self._parse_vouchers(data, 'sales')

    def fetch_receipts_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch receipt/payment vouchers for one month using Export Data."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting receipts: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        all_receipts = []
        for vtype_name in ("Receipt", "Payment"):
            xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>{vtype_name}</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

            slug = vtype_name.lower()
            data = self._post(xml, debug_name=f'{slug}s_{from_date.strftime("%Y%m")}')
            if data:
                all_receipts.extend(self._parse_vouchers(data, 'receipt'))
            time.sleep(SLEEP_BETWEEN_REQUESTS)

        return all_receipts

    # ---- CREDIT NOTES (monthly batches) ----

    def fetch_credit_notes_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch Credit Note vouchers for one month."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting credit notes: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Credit Note</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name=f'credit_notes_{from_date.strftime("%Y%m")}')
        if not data:
            return []
        return self._parse_vouchers(data, 'sales')  # Same structure as sales

    # ---- JOURNAL VOUCHERS (Sundry Debtors only, monthly) ----

    def fetch_journals_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch Journal vouchers involving Sundry Debtors for one month."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting journals: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name=f'journals_{from_date.strftime("%Y%m")}')
        if not data:
            return []
        raw = self._parse_vouchers(data, 'journal')
        # Filter: only journals involving Sundry Debtors
        return [j for j in raw if j.get('party_name', '')]

    # ---- STOCK JOURNALS (monthly) ----

    def fetch_stock_journals_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch Stock Journal vouchers for one month (inventory adjustments)."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting stock journals: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Stock Journal</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name=f'stock_journals_{from_date.strftime("%Y%m")}')
        if not data:
            return []
        return self._parse_vouchers(data, 'sales')  # Parse items like sales

    # ---- PURCHASE VOUCHERS (monthly) ----

    def fetch_purchases_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch Purchase vouchers for one month."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting purchase vouchers: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name=f'purchases_{from_date.strftime("%Y%m")}')
        if not data:
            return []
        return self._parse_vouchers(data, 'purchase')

    # ---- DEBIT NOTES (monthly) ----

    def fetch_debit_notes_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch Debit Note vouchers for one month."""
        fd_disp = from_date.strftime("%d-%b-%Y")
        td_disp = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting debit notes: {fd_disp} to {td_disp}")
        company_tag = self._company_tag()

        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Debit Note</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name=f'debit_notes_{from_date.strftime("%Y%m")}')
        if not data:
            return []
        return self._parse_vouchers(data, 'purchase')  # Same structure as purchases

    # ---- SUNDRY CREDITORS (Collection) ----

    def fetch_creditors_from_all_ledgers(self) -> List[Dict]:
        """Fallback: derive Sundry Creditors from the working `_fetch_ledgers_fallback`
        query. The Collection-based query patterns Tally rejects in this build, but the
        Function-based fallback (which gave us 212 ledgers) works. We just walk the
        parent chain and pick anything whose root is "sundry creditors".
        """
        try:
            # Reuse the already-working fallback. skip_excludes=True means
            # "do NOT apply exclude-list" → so Sundry Creditors ARE included.
            all_leds = self._fetch_ledgers_fallback(skip_excludes=True)
            if not all_leds:
                logger.warning("  Creditor fallback: ledger fetch returned empty")
                return []
            parent_map = self.fetch_group_parent_map()
            creditors = []
            for lg in all_leds:
                parent = (lg.get('parent_group') or '').strip()
                p_lower = parent.lower().strip()
                root = self._resolve_root_group(parent, parent_map) if parent else ''
                # Match if: root resolves to 'sundry creditors', OR parent string
                # contains 'creditor' / 'supplier' / 'vendor' (defensive).
                if (root != 'sundry creditors' and p_lower != 'sundry creditors'
                        and 'creditor' not in p_lower
                        and 'supplier' not in p_lower
                        and 'vendor' not in p_lower):
                    continue
                creditors.append({
                    'creditor_name': lg.get('ledger_name', ''),
                    'ledger_group': parent or 'Sundry Creditors',
                    'outstanding_amount': lg.get('closing_balance', 0),
                    'opening_balance': lg.get('opening_balance', 0),
                    'phone': lg.get('phone', ''),
                    'contact_person': lg.get('contact_person', ''),
                    'state': lg.get('state', ''),
                })
            logger.info(f"  Fallback fetched {len(creditors)} sundry creditors via group walker")
            return creditors
        except Exception as e:
            logger.warning(f"  Creditors fallback failed: {e}")
            return []

    def fetch_sundry_creditors(self) -> List[Dict]:
        """Fetch Sundry Creditors (vendors/suppliers) using TDL Collection."""
        logger.info("  Requesting Sundry Creditors (Collection)...")
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>FlowraSundryCreditors</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraSundryCreditors" ISINITIALIZE="Yes">
<TYPE>Ledger</TYPE>
<FILTER>IsSundryCreditor</FILTER>
<FETCH>NAME, PARENT, CLOSINGBALANCE, OPENINGBALANCE</FETCH>
<FETCH>LEDGERPHONE, LEDGERFAX, LEDGERCONTACT, LEDGERMOBILE, STATENAME</FETCH>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="IsSundryCreditor">
$Parent = "Sundry Creditors" OR $$GroupIdx:$PARENT = $$GroupIdx:"Sundry Creditors"
</SYSTEM>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""

        data = self._post(xml, debug_name='sundry_creditors')
        if not data:
            return []

        ledgers = self._find_deep(data, 'LEDGER')
        if not ledgers:
            ledgers = self._find_deep(data, 'COLLECTION')
            if isinstance(ledgers, dict):
                ledgers = ledgers.get('LEDGER', [])
        if isinstance(ledgers, dict):
            ledgers = [ledgers]
        if not isinstance(ledgers, list):
            return []

        creditors = []
        for lg in ledgers:
            if not isinstance(lg, dict):
                continue
            name = str(lg.get('NAME', lg.get('@NAME', ''))).strip()
            if not name:
                continue
            creditors.append({
                'creditor_name': name,
                'ledger_group': str(lg.get('PARENT', 'Sundry Creditors')).strip(),
                'outstanding_amount': self._num(lg.get('CLOSINGBALANCE', 0)),
                'opening_balance': self._num(lg.get('OPENINGBALANCE', 0)),
                'phone': str(lg.get('LEDGERPHONE', lg.get('LEDGERMOBILE', '')) or '').strip(),
                'contact_person': str(lg.get('LEDGERCONTACT', '') or '').strip(),
                'state': str(lg.get('STATENAME', '') or '').strip(),
            })

        logger.info(f"  Got {len(creditors)} sundry creditors")
        return creditors

    def _parse_vouchers(self, data: dict, vtype: str) -> List[Dict]:
        """Parse voucher XML response into clean dicts.
        
        Tally Export Data wraps each voucher in a separate TALLYMESSAGE:
          <TALLYMESSAGE><VOUCHER>...</VOUCHER></TALLYMESSAGE>
          <TALLYMESSAGE><VOUCHER>...</VOUCHER></TALLYMESSAGE>
        So we must collect VOUCHERs from ALL TALLYMESSAGE elements.
        """
        vouchers_raw = []

        # Strategy 1: Find TALLYMESSAGE and collect all VOUCHERs
        tally_msgs = self._find_deep(data, 'TALLYMESSAGE')
        if tally_msgs:
            if isinstance(tally_msgs, list):
                for msg in tally_msgs:
                    if isinstance(msg, dict) and 'VOUCHER' in msg:
                        v = msg['VOUCHER']
                        if isinstance(v, list):
                            vouchers_raw.extend(v)
                        elif isinstance(v, dict):
                            vouchers_raw.append(v)
            elif isinstance(tally_msgs, dict) and 'VOUCHER' in tally_msgs:
                v = tally_msgs['VOUCHER']
                if isinstance(v, list):
                    vouchers_raw = v
                elif isinstance(v, dict):
                    vouchers_raw = [v]

        # Strategy 2: Fallback — direct VOUCHER search (Collection responses)
        if not vouchers_raw:
            direct = self._find_deep(data, 'VOUCHER')
            if direct:
                if isinstance(direct, list):
                    vouchers_raw = direct
                elif isinstance(direct, dict):
                    vouchers_raw = [direct]

        if not vouchers_raw:
            logger.warning(f"  [DEBUG] {vtype}: no vouchers found in response")
            return []

        results = []
        for v in vouchers_raw:
            if not isinstance(v, dict):
                continue
            v_number = v.get('VOUCHERNUMBER') or v.get('@VCHKEY') or f"V-{len(results)}"
            raw_date = v.get('DATE', '')
            formatted_date = self._format_date(raw_date)
            party = str(v.get('PARTYLEDGERNAME', '') or 'Unknown').strip()

            # Amount
            amount = 0.0
            for field in ['AMOUNT', 'PARTYLEDGERAMOUNT']:
                val = v.get(field)
                if val is not None:
                    amount = self._num(val)
                    if amount > 0:
                        break

            # Ledger entries — capture per-line debit/credit direction so the
            # backend can compute correct outstanding/JV math without heuristics.
            ledger_entries = []
            le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
            if isinstance(le, dict):
                le = [le]
            if isinstance(le, list):
                for entry in le:
                    if not isinstance(entry, dict):
                        continue
                    lname = str(entry.get('LEDGERNAME', '')).strip()
                    raw_amt = entry.get('AMOUNT', 0)
                    signed = self._signed_num(raw_amt)
                    lamt = abs(signed)
                    # Tally convention: ISDEEMEDPOSITIVE='Yes' → debit; 'No' → credit.
                    # Fallback: signed AMOUNT < 0 means debit (older Tally exports).
                    idp = entry.get('ISDEEMEDPOSITIVE', entry.get('@ISDEEMEDPOSITIVE', ''))
                    if isinstance(idp, dict):
                        idp = idp.get('#text', '')
                    idp_str = str(idp or '').strip().lower()
                    if idp_str in ('yes', 'true', '1'):
                        is_debit = True
                    elif idp_str in ('no', 'false', '0'):
                        is_debit = False
                    else:
                        is_debit = signed < 0
                    if lname:
                        ledger_entries.append({
                            'ledger_name': lname,
                            'amount': lamt,
                            'is_debit': is_debit,
                            'dr_or_cr': 'Dr' if is_debit else 'Cr',
                        })
                    if amount == 0 and lamt > 0:
                        amount = lamt
                    if not party or party == 'Unknown':
                        party = lname

            if vtype == 'receipt':
                # Bill allocations
                bill_refs = []
                for entry in (le if isinstance(le, list) else []):
                    if not isinstance(entry, dict):
                        continue
                    bills = entry.get('BILLALLOCATIONS.LIST', [])
                    if isinstance(bills, dict):
                        bills = [bills]
                    for bill in (bills if isinstance(bills, list) else []):
                        if isinstance(bill, dict):
                            bill_refs.append({
                                'bill_ref': str(bill.get('NAME', '')),
                                'bill_type': str(bill.get('BILLTYPE', '')),
                                'amount': self._num(bill.get('AMOUNT', 0))
                            })

                results.append({
                    'voucher_id': str(v_number),
                    'voucher_type': str(v.get('VOUCHERTYPENAME', 'Receipt') or 'Receipt').lower(),
                    'voucher_date': formatted_date,
                    'party_name': party,
                    'amount': amount,
                    'bill_allocations': bill_refs,
                    'narration': str(v.get('NARRATION', '') or '')
                })
            elif vtype == 'journal':
                # Journals: compute debit and credit per ledger entry using captured direction
                debit_total = 0.0
                credit_total = 0.0
                for entry in ledger_entries:
                    amt = entry.get('amount', 0)
                    if entry.get('is_debit'):
                        debit_total += amt
                    else:
                        credit_total += amt

                results.append({
                    'voucher_id': str(v_number),
                    'voucher_type': 'journal',
                    'voucher_date': formatted_date,
                    'party_name': party,
                    'debit_amount': debit_total,
                    'credit_amount': credit_total,
                    'narration': str(v.get('NARRATION', '') or ''),
                    'ledger_entries': ledger_entries
                })
            else:
                # Sales / Purchase: line items
                line_items = []
                inv = v.get('ALLINVENTORYENTRIES.LIST', v.get('INVENTORYENTRIES.LIST', []))
                if isinstance(inv, dict):
                    inv = [inv]
                for entry in (inv if isinstance(inv, list) else []):
                    if not isinstance(entry, dict):
                        continue
                    iname = str(entry.get('STOCKITEMNAME', entry.get('ITEMNAME', '')) or '').strip()
                    if not iname:
                        continue
                    aq = entry.get('ACTUALQTY', entry.get('BILLEDQTY', 0))
                    rt = entry.get('RATE', 0)
                    qty_val = self._num(aq)
                    rate_val = self._num(str(rt).split('/')[0]) if rt else 0
                    ea = self._num(entry.get('AMOUNT', 0))
                    line_items.append({
                        'item': iname, 'quantity': qty_val,
                        'rate': rate_val, 'amount': ea
                    })

                dispatch_through = str(v.get('BASICSHIPDISPATCHTHROUGH', '') or '').strip()
                destination = str(v.get('BASICFINALDESTINATION', '') or '').strip()
                ref = v.get('REFERENCE', v.get('NARRATION', ''))
                v_type_name = str(v.get('VOUCHERTYPENAME', '') or '').lower()

                results.append({
                    'voucher_id': str(v_number),
                    'voucher_type': v_type_name if v_type_name else vtype,
                    'voucher_date': formatted_date,
                    'party_name': party,
                    'total_amount': amount,
                    'items': line_items,
                    'reference_number': str(ref) if ref else '',
                    'ledger_entries': ledger_entries,
                    'dispatch_through': dispatch_through,
                    'destination': destination
                })

        return results

    # ---- FY DISCOVERY from Tally ----

    def discover_financial_years(self) -> List[str]:
        """Query Tally for all available financial years (accounting periods)."""
        xml = """<ENVELOPE>
        <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>ListOfCompanies</ID></HEADER>
        <BODY><DESC>
            <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES>
            <TDL><TDLMESSAGE>
                <COLLECTION NAME="ListOfCompanies" ISMODIFY="No">
                    <TYPE>Company</TYPE>
                    <FETCH>NAME, STARTINGFROM, BOOKSFROM, ENDDATE</FETCH>
                </COLLECTION>
            </TDLMESSAGE></TDL>
        </DESC></BODY></ENVELOPE>"""
        try:
            data = self._post(xml)
            if not data:
                return self._fallback_fy_discovery()

            companies = self._find_deep(data, 'COMPANY')
            if not companies:
                return self._fallback_fy_discovery()

            if isinstance(companies, str):
                # Single company returned as string name — can't extract dates from name alone
                # Try the collection items approach instead
                companies = self._get_collection_items(data, 'COMPANY')
                if not companies:
                    return self._fallback_fy_discovery()

            if isinstance(companies, dict):
                companies = [companies]

            fys = set()
            for c in companies:
                if isinstance(c, str):
                    # Skip string entries — they're just company names without date fields
                    continue
                start = c.get('BOOKSFROM') or c.get('STARTINGFROM', '')
                if isinstance(start, dict):
                    start = start.get('#text', '')
                start = str(start or '').strip()
                if not start:
                    continue
                try:
                    # Tally dates are YYYYMMDD format
                    s = datetime.strptime(start[:8], '%Y%m%d')
                    fy_start_year = s.year if s.month >= 4 else s.year - 1
                    today = date.today()
                    current_fy_start = today.year if today.month >= 4 else today.year - 1
                    for y in range(fy_start_year, current_fy_start + 1):
                        short = str(y + 1)[-2:]
                        fys.add(f"{y}-{short}")
                except Exception:
                    pass

            if fys:
                return sorted(fys)
        except Exception as e:
            logger.warning(f"FY discovery error: {e}")
        return self._fallback_fy_discovery()

    def _fallback_fy_discovery(self) -> List[str]:
        """Fallback: generate last 5 FYs."""
        today = date.today()
        current_start = today.year if today.month >= 4 else today.year - 1
        fys = []
        for i in range(5):
            y = current_start - i
            fys.append(f"{y}-{str(y+1)[-2:]}")
        return sorted(fys)

    def fetch_last_voucher_date(self) -> Optional[date]:
        """Query Tally for the date of the most recent voucher entry in the active company.
        Returns a date object or None if detection fails."""
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE>
<ID>FlowraLastVoucherDate</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{company_tag}</STATICVARIABLES>
<TDL><TDLMESSAGE>
<REPORT NAME="FlowraLastVoucherDate"><FORMS>LVDForm</FORMS></REPORT>
<FORM NAME="LVDForm"><PARTS>LVDPart</PARTS></FORM>
<PART NAME="LVDPart"><LINES>LVDLine</LINES></PART>
<LINE NAME="LVDLine"><FIELDS>LVDField</FIELDS></LINE>
<FIELD NAME="LVDField"><SET>$$LastVoucherDate</SET></FIELD>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
        try:
            data = self._post(xml)
            if data:
                text = self._extract_text_deep(data)
                if text:
                    text = str(text).strip()
                    # Tally returns dates as YYYYMMDD or DD-Mon-YYYY
                    for fmt in ('%Y%m%d', '%d-%m-%Y', '%d-%b-%Y'):
                        try:
                            return datetime.strptime(text[:10], fmt).date()
                        except ValueError:
                            continue
        except Exception as e:
            logger.debug(f"  Last voucher date detection failed: {e}")
        return None

    # ---- CONTRA VOUCHERS (bank-to-bank, cash-to-bank) ----

    def fetch_contra_vouchers_month(self, month_start: date, month_end: date) -> List[Dict]:
        """Fetch Contra vouchers for a given month."""
        fd_disp = month_start.strftime("%d-%b-%Y")
        td_disp = month_end.strftime("%d-%b-%Y")
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Voucher Register</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{fd_disp}</SVFROMDATE>
<SVTODATE>{td_disp}</SVTODATE>
<VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""
        data = self._post(xml, debug_name=f'contra_{month_start.strftime("%Y%m")}')
        if not data:
            return []
        return self._parse_vouchers(data, 'contra')

    # ---- BANK & CASH LEDGER BALANCES ----

    def fetch_group_parent_map(self) -> Dict[str, str]:
        """Fetch all groups and their parent → returns {group_name: parent_group_name}.
        Used to walk sub-group chain when classifying ledgers (e.g., "Salaries" →
        "Indirect Expenses"). Without this, deeply-nested ledgers default to 'other'.
        """
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>FlowraGroupsHier</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{company_tag}</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraGroupsHier" ISINITIALIZE="Yes">
<TYPE>Group</TYPE>
<FETCH>NAME, PARENT</FETCH>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
        result = {}
        try:
            data = self._post(xml, debug_name='groups_hier')
            if not data:
                return result
            groups = self._get_collection_items(data, 'GROUP')
            if not groups:
                found = self._find_deep(data, 'GROUP')
                if isinstance(found, list):
                    groups = found
                elif isinstance(found, dict):
                    groups = [found]
                else:
                    return result
            for g in groups:
                if not isinstance(g, dict):
                    continue
                name = g.get('@NAME', '') or g.get('NAME', '')
                if isinstance(name, dict):
                    name = name.get('#text', '')
                parent = g.get('PARENT', '')
                if isinstance(parent, dict):
                    parent = parent.get('#text', '')
                name = str(name or '').strip()
                parent = str(parent or '').strip()
                if name:
                    result[name.lower()] = parent.lower()
            logger.info(f"  Fetched {len(result)} group hierarchies")
        except Exception as e:
            logger.warning(f"  Group hierarchy fetch failed: {e}")
        return result

    def _resolve_root_group(self, group_name: str, parent_map: Dict[str, str], depth: int = 0) -> str:
        """Walk up the parent chain to find the root group. Returns root name in lowercase."""
        if depth > 12 or not group_name:
            return group_name.lower() if group_name else ''
        gn = group_name.lower().strip()
        parent = parent_map.get(gn, '')
        if not parent or parent == gn:
            return gn
        return self._resolve_root_group(parent, parent_map, depth + 1)

    def fetch_balance_sheet(self, fy_start: date, fy_end: date) -> Dict:
        """Fetch Balance Sheet snapshot scoped to a specific FY using SVFROMDATE/SVTODATE.
        Returns Tally's actual closing balances at FY-end (not the running cumulative).

        Output structure:
        {
          'fy': '2025-26',
          'fy_start': '2025-04-01', 'fy_end': '2026-03-31',
          'groups': {
            'sundry_debtors':  {'total': 2900222, 'ledgers': [{'name':..., 'amount':...}]},
            'sundry_creditors':{'total': -345312, ...},
            'bank':            {...},
            ...
          },
          'totals': {
            'assets':         9919512,
            'liabilities':    9919512,
            'difference':     0,  # sanity check
          }
        }
        """
        fd = fy_start.strftime("%d-%b-%Y")
        td = fy_end.strftime("%d-%b-%Y")
        company_tag = self._company_tag()
        # Query LEDGER collection with FY date range so CLOSINGBALANCE = balance at FY-end
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>FlowraBSLedgers</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<SVFROMDATE>{fd}</SVFROMDATE>
<SVTODATE>{td}</SVTODATE>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraBSLedgers" ISINITIALIZE="Yes">
<TYPE>Ledger</TYPE>
<FETCH>NAME, PARENT, CLOSINGBALANCE, OPENINGBALANCE</FETCH>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
        out = {
            'fy': self.fy_label(fy_start),
            'fy_start': fy_start.isoformat(),
            'fy_end': fy_end.isoformat(),
            'groups': {},
            'totals': {'assets': 0, 'liabilities': 0, 'difference': 0},
            'raw_ledger_count': 0,
        }
        try:
            data = self._post(xml, debug_name=f'balance_sheet_{out["fy"]}')
            if not data:
                logger.warning(f"  Balance Sheet fetch returned no data for {out['fy']}")
                return out
            ledgers_raw = self._get_collection_items(data, 'LEDGER')
            if not ledgers_raw:
                found = self._find_deep(data, 'LEDGER')
                if isinstance(found, list):
                    ledgers_raw = found
                elif isinstance(found, dict):
                    ledgers_raw = [found]
            if not ledgers_raw:
                logger.warning(f"  Balance Sheet: no LEDGER records found")
                return out

            parent_map = self.fetch_group_parent_map()
            cat_map = self._get_group_category_map()

            # Asset categories vs liability categories (per Tally classification)
            ASSET_CATS = {'bank', 'cash', 'bank_od', 'current_assets', 'fixed_assets',
                          'investments', 'stock_in_hand', 'sundry_debtors',
                          'misc_expense', 'loans_advances_asset', 'deposits_asset'}
            LIAB_CATS = {'capital', 'reserves', 'secured_loans', 'unsecured_loans',
                         'current_liabilities', 'provisions', 'duties_taxes',
                         'sundry_creditors', 'non_current_liabilities', 'profit_loss_ac',
                         'branch_division', 'suspense'}

            grouped = {}
            for led in ledgers_raw:
                if not isinstance(led, dict):
                    continue
                name = str(led.get('@NAME', '') or led.get('NAME', '') or '').strip()
                if isinstance(name, dict):
                    name = name.get('#text', '')
                name = str(name).strip()
                if not name:
                    continue
                parent = str(led.get('PARENT', '') or '').strip()
                if isinstance(parent, dict):
                    parent = parent.get('#text', '')
                parent = str(parent).strip()
                root = self._resolve_root_group(parent, parent_map) if parent else ''
                category = cat_map.get(root, 'other')
                if category == 'other':
                    category = cat_map.get(parent.lower().strip(), 'other')
                if category == 'other':
                    continue  # Skip unclassified

                closing = self._signed_num(led.get('CLOSINGBALANCE', 0))  # signed
                opening = self._signed_num(led.get('OPENINGBALANCE', 0))
                # Tally sign convention: DR balances are positive, CR are negative.
                # For asset accounts → positive value = asset (good)
                # For liability accounts → typically CR balance (negative in Tally signed)
                #   we flip sign so liability total reads as positive
                display_amount = closing
                if category in LIAB_CATS:
                    display_amount = -closing
                # Skip ledgers with zero closing balance to keep the report tidy
                if abs(display_amount) < 0.01 and abs(opening) < 0.01:
                    continue

                key = category
                if key not in grouped:
                    grouped[key] = {
                        'category': category,
                        'side': 'asset' if category in ASSET_CATS else 'liability',
                        'total': 0.0,
                        'ledgers': [],
                    }
                grouped[key]['total'] += display_amount
                grouped[key]['ledgers'].append({
                    'name': name,
                    'parent_group': parent,
                    'amount': round(display_amount, 2),
                    'opening': round(opening if category in ASSET_CATS else -opening, 2),
                })

            for k in grouped:
                grouped[k]['total'] = round(grouped[k]['total'], 2)
                grouped[k]['ledgers'].sort(key=lambda x: -abs(x['amount']))

            out['groups'] = grouped
            out['raw_ledger_count'] = len(ledgers_raw)
            assets = sum(g['total'] for g in grouped.values() if g['side'] == 'asset')
            liabs = sum(g['total'] for g in grouped.values() if g['side'] == 'liability')
            out['totals'] = {
                'assets': round(assets, 2),
                'liabilities': round(liabs, 2),
                'difference': round(assets - liabs, 2),  # Should ideally be ~0 (P&L ac fills the gap)
            }
            logger.info(f"  [BS {out['fy']}] {len(grouped)} group categories, Assets=Rs.{assets:,.0f} / Liabilities=Rs.{liabs:,.0f} / Diff=Rs.{(assets-liabs):,.0f}")
        except Exception as e:
            logger.warning(f"  Balance Sheet fetch failed: {e}")
        return out

    def fy_label(self, fy_start: date) -> str:
        """2025-04-01 → '2025-26'."""
        return f"{fy_start.year}-{str(fy_start.year + 1)[-2:]}"

    def fetch_all_ledgers(self) -> List[Dict]:
        """Fetch ALL ledgers from Tally* using Export Data approach (most compatible).
        Excludes Sundry Debtors/Creditors on our side after fetching."""
        company_tag = self._company_tag()
        # Use Export Data with List of Ledgers — works reliably across all Tally versions
        xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>List of Accounts</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_tag}
<ACCOUNTTYPE>All Ledgers</ACCOUNTTYPE>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

        # Use shared category map (28 reserved Tally root groups)
        GROUP_CATEGORY = self._get_group_category_map()

        # Groups to EXCLUDE (synced separately)
        EXCLUDE_GROUPS = {'sundry debtors', 'sundry creditors'}

        try:
            data = self._post(xml, debug_name='all_ledgers')
            if not data:
                logger.warning("  No response for all ledgers query — trying fallback...")
                return self._fetch_ledgers_fallback()

            # Parse: Export Data returns TALLYMESSAGE > LEDGER[]
            ledgers_raw = []
            # Try TALLYMESSAGE path (Export Data format)
            envelope = data.get('ENVELOPE', data)
            if isinstance(envelope, dict):
                tally_msg = envelope.get('TALLYMESSAGE') or envelope.get('BODY', {}).get('TALLYMESSAGE', {})
                if isinstance(tally_msg, dict):
                    items = tally_msg.get('LEDGER', [])
                    if isinstance(items, dict):
                        items = [items]
                    if isinstance(items, list):
                        ledgers_raw = items

            # Fallback: try collection items path
            if not ledgers_raw:
                ledgers_raw = self._get_collection_items(data, 'LEDGER')

            # Fallback: try _find_deep
            if not ledgers_raw:
                found = self._find_deep(data, 'LEDGER')
                if isinstance(found, list):
                    ledgers_raw = found
                elif isinstance(found, dict):
                    ledgers_raw = [found]

            if not ledgers_raw:
                logger.warning("  No ledger data in Export Data response — trying fallback...")
                return self._fetch_ledgers_fallback()

            # Fetch group hierarchy so we can walk parent chain for sub-grouped ledgers
            parent_map = self.fetch_group_parent_map()

            results = []
            for led in ledgers_raw:
                if not isinstance(led, dict):
                    continue
                # Name: try @NAME (attribute), then NAME (child), then LEDGERNAME
                name = led.get('@NAME', '') or led.get('NAME', '') or led.get('LEDGERNAME', '')
                if isinstance(name, dict):
                    name = name.get('#text', '')
                name = str(name or '').strip()
                if not name:
                    continue

                # Parent group
                parent = led.get('PARENT', '') or led.get('@PARENT', '')
                if isinstance(parent, dict):
                    parent = parent.get('#text', '')
                parent = str(parent or '').strip()

                # Walk parent chain to root group (handles sub-groups like Salaries → Indirect Expenses)
                root_group = self._resolve_root_group(parent, parent_map) if parent else ''

                # Skip Sundry Debtors/Creditors (synced separately) — check both immediate and root
                if parent.lower().strip() in EXCLUDE_GROUPS or root_group in EXCLUDE_GROUPS:
                    continue

                # Balances
                opening = self._safe_float(led.get('OPENINGBALANCE', 0))
                closing = self._safe_float(led.get('CLOSINGBALANCE', 0))

                # Classify by ROOT group first (most reliable), fall back to immediate parent
                category = GROUP_CATEGORY.get(root_group, 'other')
                if category == 'other':
                    category = GROUP_CATEGORY.get(parent.lower().strip(), 'other')
                if category == 'other':
                    for group_key, cat_val in GROUP_CATEGORY.items():
                        if group_key in (root_group + ' ' + parent.lower()):
                            category = cat_val
                            break

                results.append({
                    'ledger_name': name,
                    'parent_group': parent,
                    'category': category,
                    'opening_balance': round(opening, 2),
                    'closing_balance': round(closing, 2),
                })

            # Log summary by category
            cat_counts = {}
            for r in results:
                cat_counts[r['category']] = cat_counts.get(r['category'], 0) + 1
            logger.info(f"  Fetched {len(results)} ledgers: {dict(cat_counts)}")
            return results

        except Exception as e:
            logger.warning(f"Error fetching all ledgers: {e}")
            return []


    def _fetch_ledgers_fallback(self, skip_excludes: bool = True) -> List[Dict]:
        """Fallback: fetch ledgers using simple TDL Collection with NO filter.
        Set skip_excludes=False to include Sundry Debtors / Creditors (used for the
        creditors fallback derivation).
        """
        company_tag = self._company_tag()
        xml = f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>FlowraLedgersFB</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{company_tag}</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraLedgersFB" ISINITIALIZE="Yes">
<TYPE>Ledger</TYPE>
<FETCH>NAME, PARENT, OPENINGBALANCE, CLOSINGBALANCE, LEDGERPHONE, LEDGERMOBILE, LEDGERCONTACT, STATENAME</FETCH>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
        EXCLUDE_GROUPS = {'sundry debtors', 'sundry creditors'} if skip_excludes else set()
        GROUP_CATEGORY = self._get_group_category_map()
        try:
            data = self._post(xml, debug_name='all_ledgers_fb')
            if not data:
                return []
            ledgers_raw = self._get_collection_items(data, 'LEDGER')
            if not ledgers_raw:
                found = self._find_deep(data, 'LEDGER')
                if isinstance(found, list):
                    ledgers_raw = found
                elif isinstance(found, dict):
                    ledgers_raw = [found]
                else:
                    return []
            # Fetch group hierarchy for sub-group walking
            parent_map = self.fetch_group_parent_map()
            results = []
            for led in ledgers_raw:
                if not isinstance(led, dict):
                    continue
                name = led.get('@NAME', '') or led.get('NAME', '')
                if isinstance(name, dict):
                    name = name.get('#text', '')
                name = str(name or '').strip()
                if not name:
                    continue
                parent = led.get('PARENT', '')
                if isinstance(parent, dict):
                    parent = parent.get('#text', '')
                parent = str(parent or '').strip()
                root_group = self._resolve_root_group(parent, parent_map) if parent else ''
                if parent.lower().strip() in EXCLUDE_GROUPS or root_group in EXCLUDE_GROUPS:
                    continue
                opening = self._safe_float(led.get('OPENINGBALANCE', 0))
                closing = self._safe_float(led.get('CLOSINGBALANCE', 0))
                category = GROUP_CATEGORY.get(root_group, 'other')
                if category == 'other':
                    category = GROUP_CATEGORY.get(parent.lower().strip(), 'other')
                if category == 'other':
                    for gk, cv in GROUP_CATEGORY.items():
                        if gk in (root_group + ' ' + parent.lower()):
                            category = cv
                            break
                results.append({
                    'ledger_name': name, 'parent_group': parent,
                    'category': category,
                    'opening_balance': round(opening, 2), 'closing_balance': round(closing, 2),
                    'phone': str(led.get('LEDGERPHONE', led.get('LEDGERMOBILE', '')) or '').strip(),
                    'contact_person': str(led.get('LEDGERCONTACT', '') or '').strip(),
                    'state': str(led.get('STATENAME', '') or '').strip(),
                })
            logger.info(f"  Fallback fetched {len(results)} ledgers")
            return results
        except Exception as e:
            logger.warning(f"  Fallback ledger fetch also failed: {e}")
            return []

    def _get_group_category_map(self):
        # Tally has 28 reserved root groups. We map each to a backend category.
        # The walker (`_resolve_root_group`) hits these as terminal nodes — sub-groups
        # like "Salaries" → "Indirect Expenses" → root match here.
        return {
            # Bank & Cash (Tally reserved root names)
            'bank accounts': 'bank',
            'bank od a/c': 'bank_od', 'bank od accounts': 'bank_od', 'bank o/d a/c': 'bank_od',
            'bank occ a/c': 'bank_od', 'bank cc accounts': 'bank_od', 'bank o.d. a/c': 'bank_od',
            'cash-in-hand': 'cash', 'cash in hand': 'cash',
            # Income
            'sales accounts': 'direct_income',
            'direct income': 'direct_income', 'direct incomes': 'direct_income',
            'indirect income': 'indirect_income', 'indirect incomes': 'indirect_income',
            # Expense
            'purchase accounts': 'direct_expense',
            'direct expenses': 'direct_expense', 'direct expense': 'direct_expense',
            'indirect expenses': 'indirect_expense', 'indirect expense': 'indirect_expense',
            'manufacturing expenses': 'direct_expense',
            # Capital & Reserves
            'capital account': 'capital', "partner's capital account": 'capital',
            'reserves & surplus': 'reserves', 'reserves and surplus': 'reserves',
            # Loans
            'secured loans': 'secured_loans', 'unsecured loans': 'unsecured_loans',
            'loans (liability)': 'unsecured_loans',
            # Liabilities
            'current liabilities': 'current_liabilities', 'provisions': 'provisions',
            'duties & taxes': 'duties_taxes', 'duties and taxes': 'duties_taxes',
            'non-current liabilities': 'non_current_liabilities',
            # Assets
            'current assets': 'current_assets', 'deposits (asset)': 'current_assets',
            'loans & advances (asset)': 'current_assets', 'loans and advances (asset)': 'current_assets',
            'stock-in-hand': 'stock_in_hand', 'fixed assets': 'fixed_assets',
            'investments': 'investments',
            # Special
            'profit & loss a/c': 'profit_loss_ac', 'profit and loss a/c': 'profit_loss_ac',
            'misc. expenses (asset)': 'misc_expense', 'misc expenses (asset)': 'misc_expense',
            'suspense a/c': 'suspense', 'suspense account': 'suspense',
            'branch / divisions': 'branch_division', 'branch/divisions': 'branch_division',
            # Sundry — handled separately but kept here for root-walker safety
            'sundry creditors': 'sundry_creditors',
            # Common user-defined sub-groups under Indirect Expenses that show
            # up in real Tally setups. The walker tries these by exact match if
            # the standard root resolution returns 'other'.
            'salary accounts': 'indirect_expense', 'salaries': 'indirect_expense',
            'wages': 'indirect_expense', 'staff welfare': 'indirect_expense',
            'local thela gaadi': 'indirect_expense', 'thela / local bhada': 'indirect_expense',
            'fuel & gas': 'indirect_expense', 'rent expense': 'indirect_expense',
            'travelling expenses': 'indirect_expense', 'commission paid': 'indirect_expense',
            'advertisement': 'indirect_expense',
        }


    def compute_pl_summary(self, ledgers: List[Dict], opening_stock: float = 0, closing_stock: float = 0,
                           total_sales_fy: float = 0, total_purchases_fy: float = 0) -> Dict:
        """Compute Gross Profit and Net Profit from ledger CLOSINGBALANCE data.
        Tally Trading Account formula:
          Sales A/c + Direct Income + Closing Stock
            = Opening Stock + Purchase A/c + Direct Expense + Gross Profit
        Net Profit = Gross Profit + Indirect Income - Indirect Expense

        Sign convention: Tally CLOSINGBALANCE for income ledgers is CR-natural
        (positive), expenses DR-natural (negative). To match Tally's display:
          income_total  = -sum(closing_balance) for income ledgers
          expense_total = +sum(closing_balance) for expense ledgers
        (because Tally signs CR balances as negative XML AMOUNT)
        Fallback to abs() if signs look inconsistent (some Tally builds export
        absolute values).
        """
        def _signed_total(cat: str, side: str) -> float:
            """side='income' (CR-natural) or 'expense' (DR-natural)."""
            entries = [l['closing_balance'] for l in ledgers if l['category'] == cat]
            if not entries:
                return 0.0
            # Try signed-sum first (Tally's normal export)
            signed = sum(entries)
            # If all entries are >= 0 (some Tally builds export absolute), use abs sum
            if side == 'income':
                # CR-natural: signed should be ≤ 0 (CR = -ve in Tally signed)
                # If sum > 0 → likely abs export; flip sign
                return -signed if signed < 0 else signed if all(e >= 0 for e in entries) else -signed
            else:
                # DR-natural: signed should be ≥ 0
                return signed if signed > 0 else -signed if all(e <= 0 for e in entries) else signed

        direct_income = _signed_total('direct_income', 'income')
        indirect_income = _signed_total('indirect_income', 'income')
        direct_expense = _signed_total('direct_expense', 'expense')
        indirect_expense = _signed_total('indirect_expense', 'expense')

        # Tally Trading Account: Sales A/c is mapped to direct_income category in
        # our agent. Voucher-header totals (total_sales_fy) include GST output and
        # are NOT used here — they would over-count the Sales A/c by the tax amount.
        sales_for_gp = direct_income
        purchases_for_gp = direct_expense

        # Gross Profit per Tally formula
        gross_profit = (closing_stock + sales_for_gp) - (opening_stock + purchases_for_gp)
        # Note: direct_income = sales_for_gp here, so we don't double count

        # Net Profit = Gross Profit + Indirect Income - Indirect Expense
        net_profit = gross_profit + indirect_income - indirect_expense

        total_income = direct_income + indirect_income
        total_expense = direct_expense + indirect_expense

        # Also check P&L A/c ledger balance (running cumulative)
        pl_ac_ledger = [l for l in ledgers if l['category'] == 'profit_loss_ac']
        pl_ac_closing = pl_ac_ledger[0]['closing_balance'] if pl_ac_ledger else 0
        pl_ac_opening = pl_ac_ledger[0]['opening_balance'] if pl_ac_ledger else 0

        return {
            'gross_profit': round(gross_profit, 2),
            'is_gross_loss': gross_profit < 0,
            'net_profit': round(net_profit, 2),
            'is_net_loss': net_profit < 0,
            'total_income': round(total_income, 2),
            'total_expense': round(total_expense, 2),
            'direct_income': round(direct_income, 2),
            'indirect_income': round(indirect_income, 2),
            'direct_expense': round(direct_expense, 2),
            'indirect_expense': round(indirect_expense, 2),
            'opening_stock': round(opening_stock, 2),
            'closing_stock': round(closing_stock, 2),
            'sales_value': round(sales_for_gp, 2),
            'purchases_value': round(purchases_for_gp, 2),
            'pl_ac_opening': round(pl_ac_opening, 2),
            'pl_ac_closing': round(pl_ac_closing, 2),
        }


# ==================== AUTH & SESSION MANAGEMENT ====================

def login_to_flowra(backend_url: str, email: str = None, password: str = None) -> dict:
    """Authenticate with FLOWRA backend. Returns auth config dict or raises error."""
    if not email:
        print("\n" + "=" * 50)
        print("  FLOWRA Desktop Agent - Login")
        print("=" * 50)
        email = input("  Email: ").strip()
        password = input("  Password: ").strip()

    if not email or not password:
        raise ValueError("Email and password are required")

    try:
        resp = requests.post(
            f"{backend_url}/api/auth/login",
            json={"username": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                auth_data = data["data"]
                if auth_data.get("role") not in ("admin",):
                    raise ValueError("Only admin accounts can use the desktop sync agent")

                # Check subscription status
                sub_days_left = auth_data.get("subscription_days_left", 999)
                sub_expires = auth_data.get("subscription_expires")
                plan = auth_data.get("plan", "unknown")
                max_companies = auth_data.get("max_companies", 10)

                if sub_days_left is not None and sub_days_left < 0:
                    raise ValueError(
                        "Your FLOWRA subscription has expired. Sync is disabled.\n"
                        "  Please renew your subscription at flowra.in or contact support@flowra.in"
                    )

                config = {
                    "backend_url": backend_url,
                    "email": email,
                    "token": auth_data["token"],
                    "tenant_id": auth_data.get("tenant_id", ""),
                    "companies": auth_data.get("companies", []),
                    "company_mappings": auth_data.get("company_mappings", []),
                    "name": auth_data.get("name", ""),
                    "features": auth_data.get("features", []),
                    "plan": plan,
                    "max_companies": max_companies,
                    "subscription_expires": sub_expires,
                    "subscription_days_left": sub_days_left,
                }
                # Get sync token for this tenant
                try:
                    token_resp = requests.get(
                        f"{backend_url}/api/auth/sync-token",
                        headers={"Authorization": f"Bearer {auth_data['token']}"},
                        timeout=10
                    )
                    if token_resp.status_code == 200:
                        token_data = token_resp.json()
                        if token_data.get("success"):
                            config["sync_token"] = token_data["data"].get("sync_token", "")
                except Exception as e:
                    logger.warning(f"Could not get sync token: {e}")
                    config["sync_token"] = ""

                save_auth_config(config)
                print(f"\n  Logged in as: {auth_data.get('name') or email}")
                print(f"  Tenant ID:    {config['tenant_id']}")
                print(f"  Plan:         {plan.upper()}")
                print(f"  Max Companies:{max_companies}")
                if sub_expires:
                    print(f"  Expires:      {sub_expires[:10]}")
                    if sub_days_left is not None and sub_days_left <= 30:
                        print(f"  WARNING: Subscription expires in {sub_days_left} days! Renew at flowra.in")
                if config['companies']:
                    co_names = [m.get('company_name', '') for m in config.get('company_mappings', [])]
                    print(f"  Companies:    {', '.join(co_names) if co_names else ', '.join(config['companies'])}")
                print()
                return config
            else:
                raise ValueError(data.get("error", "Login failed"))
        else:
            raise ValueError(f"Server returned HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        raise ValueError(f"Cannot connect to FLOWRA at {backend_url}. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise ValueError("Connection timed out")


def get_or_refresh_auth(backend_url: str = None) -> dict:
    """Load saved auth or prompt for login. Returns auth config."""
    config = load_auth_config()
    if config:
        # Validate the token is still working
        try:
            url = config.get('backend_url', backend_url)
            resp = requests.get(
                f"{url}/api/auth/me",
                headers={"Authorization": f"Bearer {config['token']}"},
                timeout=10
            )
            if resp.status_code == 200 and resp.json().get("success"):
                # Update companies list and subscription info from server
                me_data = resp.json().get("data", {})
                config["companies"] = me_data.get("companies", config.get("companies", []))
                config["company_mappings"] = me_data.get("company_mappings", config.get("company_mappings", []))
                config["plan"] = me_data.get("plan", config.get("plan", ""))
                config["max_companies"] = me_data.get("max_companies", config.get("max_companies", 10))
                config["subscription_expires"] = me_data.get("subscription_expires")
                config["subscription_days_left"] = me_data.get("subscription_days_left", 999)

                # Check subscription expiry
                days_left = config.get("subscription_days_left", 999)
                if days_left is not None and days_left < 0:
                    logger.error("Subscription expired! Sync disabled.")
                    print("\n  ERROR: Your FLOWRA subscription has expired.")
                    print("  Sync is disabled. Please renew at flowra.in or contact support@flowra.in")
                    raise ValueError("Subscription expired")

                if days_left is not None and days_left <= 30:
                    logger.warning(f"Subscription expires in {days_left} days!")
                    print(f"\n  WARNING: Subscription expires in {days_left} days. Renew at flowra.in")

                save_auth_config(config)
                logger.info(f"Auth session valid for {config.get('email', 'unknown')} | Plan: {config.get('plan', '?')} | Expires in {days_left}d")
                return config
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Auth validation failed: {e}")

        # Token expired or invalid — try re-login with saved email
        logger.info("Session expired, re-authenticating...")
        print("\n  Session expired. Please re-enter your password.")
        email = config.get('email', '')
        if email:
            print(f"  Email: {email}")
            password = input("  Password: ").strip()
            url = config.get('backend_url', backend_url)
            return login_to_flowra(url, email, password)

    # No saved config — fresh login
    url = backend_url or BACKEND_URL
    if not url:
        print("\n" + "=" * 50)
        print("  FLOWRA Desktop Agent - Setup")
        print("=" * 50)
        url = input("  FLOWRA Server URL (e.g. https://yourapp.flowra.in): ").strip().rstrip('/')
        if not url:
            raise ValueError("Server URL is required")

    return login_to_flowra(url)


# ==================== INCREMENTAL SYNC HELPERS ====================

def compute_data_hash(data: list) -> str:
    """Compute a quick hash of the data for change detection."""
    import hashlib
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(content.encode()).hexdigest()


def should_skip_sync(state: dict, company: str, data_type: str, data: list) -> bool:
    """Check if data has changed since last sync using hash comparison."""
    company_state = state.get('companies', {}).get(company, {})
    last_hash = company_state.get('hashes', {}).get(data_type, '')
    current_hash = compute_data_hash(data)
    return last_hash == current_hash and last_hash != ''


def update_sync_hash(state: dict, company: str, data_type: str, data: list) -> dict:
    """Update the stored hash after successful sync."""
    if 'companies' not in state:
        state['companies'] = {}
    if company not in state['companies']:
        state['companies'][company] = {'hashes': {}, 'last_sync': {}}
    state['companies'][company]['hashes'][data_type] = compute_data_hash(data)
    state['companies'][company]['last_sync'][data_type] = datetime.now().isoformat()
    return state


# ==================== MAIN AGENT ====================

class FlowraSyncAgent:
    def __init__(self):
        self.financial_year = FINANCIAL_YEAR
        self.sync_interval = SYNC_INTERVAL
        self.export_dir = EXPORT_DIR
        self.sync_running = False
        self.ws_server = None
        self._active_company = COMPANY_NAME
        self._companies_to_sync = []
        self.tally = TallyCollectionClient(
            url=TALLY_URL,
            company=COMPANY_NAME,
            timeout=REQUEST_TIMEOUT,
            debug_dir=self.export_dir
        )

        os.makedirs(self.export_dir, exist_ok=True)

        logger.info("=" * 60)
        logger.info("  FLOWRA TALLY SYNC AGENT v9 (Reconciliation + Command Queue)")
        logger.info("  Lightweight Collection Requests + Incremental Sync")
        logger.info("=" * 60)

        # --- LOGIN-BASED AUTH ---
        # Authenticate with FLOWRA backend to get tenant_id + sync_token
        self.auth_config = get_or_refresh_auth(BACKEND_URL or None)
        self.backend_url = self.auth_config['backend_url']
        self.tenant_id = self.auth_config['tenant_id']
        self.sync_token = self.auth_config.get('sync_token', '')
        self.auth_token = self.auth_config['token']
        self.server_companies = self.auth_config.get('companies', [])
        self.company_mappings = {}  # company_name -> company_uuid
        self.company_names = {}     # company_uuid -> company_name
        for m in self.auth_config.get('company_mappings', []):
            self.company_mappings[m.get('company_name', '')] = m.get('company_id', '')
            self.company_names[m.get('company_id', '')] = m.get('company_name', '')
        self.plan = self.auth_config.get('plan', 'enterprise')
        self.max_companies = self.auth_config.get('max_companies', 10)
        self.sub_days_left = self.auth_config.get('subscription_days_left', 999)
        self.sub_expires = self.auth_config.get('subscription_expires')

        logger.info(f"  Tally URL     : {TALLY_URL}")
        logger.info(f"  Cloud Backend : {self.backend_url}")
        logger.info(f"  Logged in as  : {self.auth_config.get('email', 'unknown')}")
        logger.info(f"  Tenant ID     : {self.tenant_id}")
        logger.info(f"  Plan          : {self.plan.upper()} (max {self.max_companies} companies)")
        if self.sub_expires:
            logger.info(f"  Subscription  : Expires {self.sub_expires[:10]} ({self.sub_days_left} days left)")
        server_co_names = [self.company_names.get(c, c) for c in self.server_companies]
        logger.info(f"  Server Cos    : {', '.join(server_co_names) if server_co_names else '(none yet)'}")
        logger.info(f"  Financial Year: {self.financial_year}")
        logger.info(f"  Auto Multi-FY : {SYNC_ALL_FY} (also syncs current FY: {current_fy()})")
        logger.info(f"  Incremental   : {INCREMENTAL_SYNC}")
        logger.info(f"  Sync Interval : every {self.sync_interval} min")
        logger.info(f"  Cache Dir     : {self.export_dir}")
        logger.info("=" * 60)

    def detect_companies(self):
        """Detect available companies in Tally using Collection request (most reliable)."""
        try:
            # Method 1: Collection-based request (same as test_connection)
            xml_req = """<ENVELOPE>
<HEADER><VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>FlowraCompanyList</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraCompanyList" ISINITIALIZE="Yes">
<TYPE>Company</TYPE>
<FETCH>NAME</FETCH>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
            resp = requests.post(TALLY_URL, data=xml_req.encode('utf-8'),
                                 headers={'Content-Type': 'application/xml'},
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                parsed = xmltodict.parse(resp.text)
                companies = []
                items = self.tally._get_collection_items(parsed, 'COMPANY')
                for item in items:
                    if isinstance(item, dict):
                        name = item.get('NAME', item.get('@NAME', ''))
                        if isinstance(name, dict):
                            name = name.get('#text', '')
                        name = str(name).strip() if name else ''
                        if name and name.lower() not in ('default', '##default'):
                            companies.append(name)
                if companies:
                    return companies
        except Exception as e:
            logger.warning(f"Collection-based company detect failed: {e}")

        try:
            # Method 2: Export Data format (fallback)
            xml_req = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
            resp = requests.post(TALLY_URL, data=xml_req.encode('utf-8'),
                                 headers={'Content-Type': 'application/xml'},
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                parsed = xmltodict.parse(resp.text)
                companies = []
                collection = parsed.get('ENVELOPE', {}).get('BODY', {}).get('DATA', {}).get('COLLECTION', {})
                if collection:
                    items = collection.get('COMPANY', [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        name = item.get('NAME', {}).get('#text', '') if isinstance(item.get('NAME'), dict) else item.get('NAME', '')
                        name = str(name).strip() if name else ''
                        if name and name.lower() not in ('default', '##default'):
                            companies.append(name)
                if companies:
                    return companies
        except Exception as e:
            logger.warning(f"Export-based company detect failed: {e}")

        try:
            # Method 3: Get currently active company via CompanyInfo
            xml_req = """<ENVELOPE>
<HEADER><VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>FlowraActiveCompany</ID></HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="FlowraActiveCompany" ISINITIALIZE="Yes">
<TYPE>Company</TYPE>
<FETCH>NAME, BASICCOMPANYFORMALNAME</FETCH>
<FILTER>ActiveCompanyFilter</FILTER>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="ActiveCompanyFilter">$$IsCurrentCompany</SYSTEM>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
            resp = requests.post(TALLY_URL, data=xml_req.encode('utf-8'),
                                 headers={'Content-Type': 'application/xml'},
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                parsed = xmltodict.parse(resp.text)
                items = self.tally._get_collection_items(parsed, 'COMPANY')
                for item in items:
                    if isinstance(item, dict):
                        name = item.get('NAME', item.get('@NAME', ''))
                        if isinstance(name, dict):
                            name = name.get('#text', '')
                        name = str(name).strip() if name else ''
                        if name and name.lower() not in ('default', '##default'):
                            return [name]
        except Exception as e:
            logger.warning(f"Active company detect failed: {e}")

        return []

    def select_companies(self):
        """Interactive company selection for multi-company Tally instances."""
        if COMPANY_NAME:
            self._companies_to_sync = [COMPANY_NAME]
            return

        companies = self.detect_companies()
        if not companies:
            # Fallback: use current company from Tally (if valid)
            current = self.tally.company
            if current and current.lower() not in ('default', '##default', ''):
                self._companies_to_sync = [current]
            else:
                # Tally is connected but company name unknown — proceed with placeholder
                # SVCurrentCompany will be empty so Tally uses the active company
                logger.info("  Company name not detected — using Tally's active company")
                self._companies_to_sync = ['_active_']
            return

        if len(companies) == 1:
            self._companies_to_sync = companies
            logger.info(f"Single company detected: {companies[0]}")
            return

        if SYNC_ALL_COMPANIES:
            self._companies_to_sync = companies
            logger.info(f"Syncing ALL {len(companies)} companies: {', '.join(companies)}")
            return

        # Interactive selection
        print("\n" + "=" * 50)
        print("  Multiple Tally companies detected:")
        print("=" * 50)
        for i, c in enumerate(companies, 1):
            print(f"  {i}. {c}")
        print(f"  A. Sync ALL companies")
        print("=" * 50)

        while True:
            choice = input("  Select company number (or A for all): ").strip()
            if choice.upper() == 'A':
                self._companies_to_sync = companies
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(companies):
                    self._companies_to_sync = [companies[idx]]
                    break
            except ValueError:
                pass
            print("  Invalid choice, try again.")

        logger.info(f"Selected companies: {', '.join(self._companies_to_sync)}")

        # Enforce plan company limit
        if len(self._companies_to_sync) > self.max_companies:
            logger.warning(f"Plan limit: {self.plan.upper()} allows max {self.max_companies} companies. Truncating selection.")
            print(f"\n  Your {self.plan.upper()} plan supports max {self.max_companies} company(ies).")
            print(f"  Only the first {self.max_companies} will be synced. Upgrade at flowra.in for more.")
            self._companies_to_sync = self._companies_to_sync[:self.max_companies]

    def _resolve_company_id(self, company_name):
        """Resolve a company name to its UUID if we have the mapping, otherwise return name for backend to resolve."""
        if not company_name or company_name in ('_active_', 'Default', '##Default'):
            return ''
        return self.company_mappings.get(company_name, company_name)

    def discover_and_select_fys(self):
        """Discover available FYs from Tally and ask user to select starting FY per company."""
        logger.info("Discovering available financial years from Tally*...")
        available_fys = self.tally.discover_financial_years()

        if not available_fys:
            logger.warning("Could not discover FYs from Tally. Using configured FY.")
            return

        cur = current_fy()
        state = load_sync_state()

        if not hasattr(self, '_company_fys'):
            self._company_fys = {}

        companies = self._companies_to_sync or ['_active_']

        for company in companies:
            display = company if company != '_active_' else 'Active Company'

            # Per-company state key
            company_fy_key = f"selected_start_fy__{company.replace(' ', '_')}"
            saved_start_fy = state.get(company_fy_key)

            if saved_start_fy and saved_start_fy in available_fys:
                idx = available_fys.index(saved_start_fy)
                company_fys = available_fys[idx:]
                if cur not in company_fys:
                    company_fys.append(cur)
                self._company_fys[company] = company_fys
                logger.info(f"  [{display}] Resuming from saved FY: {saved_start_fy} to {company_fys[-1]} ({len(company_fys)} FYs)")
                continue

            # First-time for this company: ask user
            print(f"\n{'=' * 56}")
            print(f"  FY Selection for: {display}")
            print(f"{'=' * 56}")
            print(f"  Available Financial Years in Tally*:")
            print(f"{'=' * 56}")
            for i, fy in enumerate(available_fys, 1):
                marker = " (current)" if fy == cur else ""
                print(f"  {i}. FY {fy}{marker}")
            print("=" * 56)
            print(f"  Select STARTING FY to sync from for {display}")
            print(f"  (data will sync from this FY up to current FY)")
            print()

            while True:
                choice = input(f"  Enter number [1-{len(available_fys)}]: ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(available_fys):
                        start_fy = available_fys[idx]
                        company_fys = available_fys[idx:]
                        if cur not in company_fys:
                            company_fys.append(cur)
                        self._company_fys[company] = company_fys
                        # Save per-company selection
                        state[company_fy_key] = start_fy
                        save_sync_state(state)
                        logger.info(f"  [{display}] Will sync FYs: {start_fy} to {company_fys[-1]} ({len(company_fys)} FYs)")
                        break
                except ValueError:
                    pass
                print("  Invalid choice, try again.")

        # Also set global _sync_fys as union of all company FYs (for backward compat)
        all_fys = set()
        for fys in self._company_fys.values():
            all_fys.update(fys)
        self._sync_fys = sorted(all_fys) if all_fys else None

    def report_progress(self, event_type, **kwargs):
        company = self._active_company or self.tally.company or ''
        if company in ('_active_', 'Default', '##Default'):
            company = ''
        company_id = self._resolve_company_id(company)
        progress = {
            'type': event_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'financial_year': self.financial_year,
            'company_name': company,
            'tenant_id': self.tenant_id,
            'company_id': company_id,
            **kwargs
        }
        if self.ws_server:
            self.ws_server.broadcast(progress)
        try:
            requests.post(
                f"{self.backend_url}/api/agent/sync-progress",
                json=progress,
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.auth_token}'},
                timeout=5
            )
        except:
            pass

    def sync_to_backend(self, data_type, data):
        if not data:
            return True

        # Incremental optimization: skip if data hash unchanged
        state = load_sync_state()
        company = self._active_company or ''
        if INCREMENTAL_SYNC and should_skip_sync(state, company, data_type, data):
            logger.info(f"  [SKIP] {data_type}: data unchanged since last sync (hash match)")
            return True

        try:
            company = self._active_company or self.tally.company or ''
            if company in ('_active_', 'Default', '##Default'):
                company = ''
            company_id = self._resolve_company_id(company)
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.now(timezone.utc).isoformat(),
                'agent_version': '9.6.0-stdprice',
                'company_name': company,
                'financial_year': self.financial_year,
                'tenant_id': self.tenant_id,
                'company_id': company_id,
                'sync_token': self.sync_token
            }
            resp = requests.post(
                f"{self.backend_url}/api/agent/sync",
                json=payload,
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.auth_token}'},
                timeout=30
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get('success'):
                    logger.info(f"  [OK] Synced {len(data)} {data_type} to cloud")
                    # Update hash after successful sync
                    state = update_sync_hash(state, company, data_type, data)
                    save_sync_state(state)
                    return True
                else:
                    logger.error(f"  Sync {data_type} failed: {result.get('error', 'unknown')}")
                    return False
            else:
                logger.error(f"  Sync {data_type} failed: HTTP {resp.status_code}")
                # If 401/403, try to re-authenticate
                if resp.status_code in (401, 403):
                    logger.warning("Auth token expired during sync, refreshing...")
                    try:
                        self.auth_config = get_or_refresh_auth(self.backend_url)
                        self.auth_token = self.auth_config['token']
                        self.sync_token = self.auth_config.get('sync_token', '')
                    except Exception:
                        pass
                return False
        except Exception as e:
            logger.error(f"  Sync error ({data_type}): {e}")
            return False

    def reconcile_with_backend(self, data_type, manifest_ids, id_key='voucher_id'):
        """Send manifest of all IDs to backend for orphan deletion (Option B reconciliation).
        Backend deletes any records for this data_type+tenant+company that are NOT in the manifest."""
        try:
            company = self._active_company or self.tally.company or ''
            if company in ('_active_', 'Default', '##Default'):
                company = ''
            company_id = self._resolve_company_id(company)

            payload = {
                'data_type': data_type,
                'manifest_ids': manifest_ids,
                'tenant_id': self.tenant_id,
                'company_id': company_id,
                'company_name': company,
                'financial_year': self.financial_year,
                'sync_token': self.sync_token,
                'agent_version': '9.6.0-stdprice',
            }
            resp = requests.post(
                f"{self.backend_url}/api/agent/reconcile",
                json=payload,
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.auth_token}'},
                timeout=30
            )
            if resp.status_code == 200:
                result = resp.json()
                msg = result.get('message', '')
                if 'orphan' in msg.lower() and '0 orphan' not in msg.lower():
                    logger.info(f"  [RECONCILE] {data_type}: {msg}")
                else:
                    logger.info(f"  [RECONCILE] {data_type}: clean — no orphans")
                return True
            else:
                logger.warning(f"  [RECONCILE] {data_type}: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"  Reconcile error ({data_type}): {e}")
            return False

    def poll_and_execute_commands(self):
        """Poll backend for pending commands (resync, delete) and execute them."""
        try:
            resp = requests.get(
                f"{self.backend_url}/api/agent/commands",
                params={"tenant_id": self.tenant_id, "sync_token": self.sync_token},
                headers={'Authorization': f'Bearer {self.auth_token}'},
                timeout=10
            )
            if resp.status_code != 200:
                return

            data = resp.json()
            commands = data.get('data', {}).get('commands', [])
            if not commands:
                return

            for cmd in commands:
                action = cmd.get('action', '')
                cmd_company_id = cmd.get('company_id', '')
                cmd_company_name = cmd.get('company_name', '')
                display = cmd_company_name or cmd_company_id

                if action == 'delete':
                    logger.info(f"[CMD] DELETE company: {display}")
                    # Remove from local sync list
                    if cmd_company_name and cmd_company_name in self._companies_to_sync:
                        self._companies_to_sync.remove(cmd_company_name)
                        logger.info(f"  Removed '{cmd_company_name}' from sync list")
                    # Also check by matching company_id in mappings
                    for cname, cid in list(self.company_mappings.items()):
                        if cid == cmd_company_id and cname in self._companies_to_sync:
                            self._companies_to_sync.remove(cname)
                            logger.info(f"  Removed '{cname}' (id={cid}) from sync list")
                    # Clear per-company FY selection
                    state = load_sync_state()
                    fy_key = f"selected_start_fy__{cmd_company_name.replace(' ', '_')}"
                    if fy_key in state:
                        del state[fy_key]
                    # Clear local cache
                    safe_name = (cmd_company_name or '').replace(' ', '_').replace('/', '_')
                    cache_dir = os.path.join(self.export_dir, safe_name) if safe_name else None
                    if cache_dir and os.path.isdir(cache_dir):
                        import shutil
                        shutil.rmtree(cache_dir, ignore_errors=True)
                        logger.info(f"  Deleted local cache: {cache_dir}")
                    # Clear hash state for this company
                    if 'companies' in state and cmd_company_name in state['companies']:
                        del state['companies'][cmd_company_name]
                    save_sync_state(state)
                    if hasattr(self, '_company_fys') and cmd_company_name in self._company_fys:
                        del self._company_fys[cmd_company_name]
                    logger.info(f"  Company '{display}' fully removed from agent")

                elif action == 'resync':
                    logger.info(f"[CMD] RESYNC company: {display}")
                    # Clear local hash cache so next full sync sends everything fresh
                    state = load_sync_state()
                    if 'companies' in state and cmd_company_name in state['companies']:
                        state['companies'][cmd_company_name]['hashes'] = {}
                        state['companies'][cmd_company_name]['full_sync_done'] = False
                        save_sync_state(state)
                    # Clear per-company FY selection — agent will ask user again
                    fy_key = f"selected_start_fy__{cmd_company_name.replace(' ', '_')}"
                    if fy_key in state:
                        del state[fy_key]
                        save_sync_state(state)
                    if hasattr(self, '_company_fys') and cmd_company_name in self._company_fys:
                        del self._company_fys[cmd_company_name]
                    # Clear local cache files
                    safe_name = (cmd_company_name or '').replace(' ', '_').replace('/', '_')
                    cache_dir = os.path.join(self.export_dir, safe_name) if safe_name else None
                    if cache_dir and os.path.isdir(cache_dir):
                        import shutil
                        shutil.rmtree(cache_dir, ignore_errors=True)
                        logger.info(f"  Cleared local cache: {cache_dir}")
                    logger.info(f"  Resync queued — agent will ask for FY selection on next cycle for '{display}'")

                # Acknowledge command
                try:
                    requests.post(
                        f"{self.backend_url}/api/agent/commands/ack",
                        json={
                            "tenant_id": self.tenant_id,
                            "company_id": cmd_company_id,
                            "action": action,
                        },
                        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.auth_token}'},
                        timeout=10
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Command poll error: {e}")

    def run_sales_quick_sync(self):
        """Quick sync: only sales vouchers for all companies (runs every 5 min)."""
        if self.sync_running:
            return
        self.sync_running = True
        try:
            # Poll commands first
            self.poll_and_execute_commands()

            if not self._companies_to_sync:
                return

            # Refresh auth
            try:
                self.auth_config = get_or_refresh_auth(self.backend_url)
                self.auth_token = self.auth_config.get('token', '')
                self.sync_token = self.auth_config.get('sync_token', '')
            except Exception:
                return

            for company in self._companies_to_sync:
                self._active_company = company
                self.tally.company = company if company != '_active_' else ''

                if not self.tally._ping_tally():
                    logger.warning(f"[QUICK] Tally not responding for company '{company}' — skipping. Is Tally running with this company open?")
                    continue

                # Per-company FYs
                if hasattr(self, '_company_fys') and company in self._company_fys:
                    fys = self._company_fys[company]
                elif hasattr(self, '_sync_fys') and self._sync_fys:
                    fys = self._sync_fys
                else:
                    fys = get_sync_fys()

                logger.info(f"[QUICK] Sales sync: {company}")

                # Detect last voucher date for this company
                lvd = self.tally.fetch_last_voucher_date() or date.today()

                all_quick_sales = []
                for fy in fys:
                    self.financial_year = fy
                    fy_start, fy_end = fy_to_dates(fy)
                    fy_sales = []
                    for m_start, m_end in months_in_fy(fy, cap_date=lvd):
                        fy_sales.extend(self.tally.fetch_sales_month(m_start, m_end))
                        time.sleep(SLEEP_BETWEEN_REQUESTS)
                    if fy_sales:
                        self.sync_to_backend('sales', fy_sales)
                    all_quick_sales.extend(fy_sales)
                    logger.info(f"  [QUICK] FY {fy}: {len(fy_sales)} sales vouchers synced")

                # Reconcile AFTER all FYs
                self.reconcile_with_backend('sales', [v.get('voucher_id', '') for v in all_quick_sales if v.get('voucher_id')])

        except Exception as e:
            logger.debug(f"Quick sales sync error: {e}")
        finally:
            self.sync_running = False

    def save_cache(self, data_type, data):
        """Save fetched data to local JSON file for caching.
        Uses company-specific subfolder for data isolation."""
        company_dir = self.export_dir
        if self._active_company:
            company_dir = os.path.join(self.export_dir, self._active_company.replace(' ', '_').replace('/', '_'))
        os.makedirs(company_dir, exist_ok=True)
        filepath = os.path.join(company_dir, f"{data_type}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Cached {len(data)} {data_type} to {filepath}")

    def run_sync_cycle(self):
        if self.sync_running:
            logger.info("Sync already running, skipping...")
            return
        try:
            self.sync_running = True

            # ── Poll and execute any pending commands (resync/delete) ──
            self.poll_and_execute_commands()

            # Refresh auth token before each cycle
            try:
                self.auth_config = get_or_refresh_auth(self.backend_url)
                self.auth_token = self.auth_config['token']
                self.tenant_id = self.auth_config['tenant_id']
                self.sync_token = self.auth_config.get('sync_token', '')
                # Refresh company mappings
                for m in self.auth_config.get('company_mappings', []):
                    self.company_mappings[m.get('company_name', '')] = m.get('company_id', '')
                    self.company_names[m.get('company_id', '')] = m.get('company_name', '')
            except Exception as auth_err:
                logger.error(f"Auth refresh failed: {auth_err}. Skipping this sync cycle.")
                return

            if not self._companies_to_sync:
                self.select_companies()
            if not self._companies_to_sync:
                logger.error("No companies to sync. Skipping this cycle.")
                self.report_progress('sync_error', error='No companies detected in Tally')
                return
            for company in self._companies_to_sync:
                self._active_company = company
                self.tally.company = company if company != '_active_' else ''
                display = company if company != '_active_' else 'Active Company (auto-detect)'
                logger.info("")
                logger.info(f"{'=' * 60}")
                logger.info(f"Syncing company: {display}")
                logger.info(f"{'=' * 60}")
                self._sync_single_company(company)
        except Exception as e:
            logger.error(f"Sync cycle error: {e}")
            self.report_progress('sync_error', error=str(e))
        finally:
            self.sync_running = False

    def _sync_single_company(self, company_name):
        """Run sync for a single company."""
        try:
            # If company_name is placeholder, use empty string for display but still sync
            is_placeholder = company_name == '_active_'
            display_name = company_name if not is_placeholder else 'Active Company (auto-detect)'

            # CRITICAL: Set the company on the TallyConnector BEFORE any requests.
            # This ensures _company_tag() injects <SVCURRENTCOMPANY> in all XML requests.
            if not is_placeholder:
                self.tally.company = company_name
                # Set per-company debug directory for raw XML exports
                safe_name = company_name.replace(' ', '_').replace('/', '_')
                self.tally.debug_dir = os.path.join(self.export_dir, safe_name)
                os.makedirs(self.tally.debug_dir, exist_ok=True)

            # Always do full sync — Tally has no change-detection API, so edits to old
            # invoices/items/vouchers would be missed by partial fetches.
            # Hash comparison on upload side still prevents unnecessary DB writes.
            sync_mode = 'full'

            logger.info(f"Starting {sync_mode} sync at {datetime.now().strftime('%H:%M:%S')}")

            # Test connection — use a lightweight ping that does NOT overwrite self.tally.company
            if not self.tally._ping_tally():
                logger.error("Cannot connect to Tally! Is TallyPrime running?")
                self.report_progress('sync_error', error='Tally not responding')
                return

            # Determine which FYs to sync — per-company if available
            if hasattr(self, '_company_fys') and company_name in self._company_fys:
                fys_to_sync = self._company_fys[company_name]
            elif hasattr(self, '_sync_fys') and self._sync_fys:
                fys_to_sync = self._sync_fys
            else:
                fys_to_sync = get_sync_fys()

            # If no per-company FY set (e.g. after resync), re-ask for this company
            if hasattr(self, '_company_fys') and company_name not in self._company_fys:
                available_fys = self.tally.discover_financial_years()
                if available_fys:
                    cur = current_fy()
                    print(f"\n{'=' * 56}")
                    print(f"  FY Selection for: {company_name}")
                    print(f"{'=' * 56}")
                    for i, fy in enumerate(available_fys, 1):
                        marker = " (current)" if fy == cur else ""
                        print(f"  {i}. FY {fy}{marker}")
                    print("=" * 56)
                    while True:
                        choice = input(f"  Enter starting FY [1-{len(available_fys)}]: ").strip()
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(available_fys):
                                start_fy = available_fys[idx]
                                fys_to_sync = available_fys[idx:]
                                if cur not in fys_to_sync:
                                    fys_to_sync.append(cur)
                                self._company_fys[company_name] = fys_to_sync
                                state = load_sync_state()
                                fy_key = f"selected_start_fy__{company_name.replace(' ', '_')}"
                                state[fy_key] = start_fy
                                save_sync_state(state)
                                logger.info(f"  [{company_name}] Will sync FYs: {start_fy} to {fys_to_sync[-1]}")
                                break
                        except ValueError:
                            pass
                        print("  Invalid choice, try again.")

            logger.info(f"  Syncing FYs: {', '.join(fys_to_sync)} ({sync_mode} mode)")

            # If company name is still unknown, try to resolve from Tally now
            if is_placeholder:
                if not self.tally.test_connection():
                    logger.error("Cannot connect to Tally!")
                    return
                if self.tally.company and self.tally.company.lower() not in ('default', '##default', '', '_active_'):
                    resolved = self.tally.company
                    logger.info(f"  Resolved company name: {resolved}")
                    self._active_company = resolved
                    company_name = resolved
            else:
                logger.info(f"  Tally company: {company_name}")

            # Detect last voucher entry date — cap syncing at this date for latest FY
            last_voucher_date = self.tally.fetch_last_voucher_date()
            if last_voucher_date:
                logger.info(f"  Last voucher date in Tally*: {last_voucher_date.strftime('%d-%b-%Y')}")
            else:
                last_voucher_date = date.today()
                logger.info(f"  Last voucher date: using today ({last_voucher_date.strftime('%d-%b-%Y')})")

            # Report sync started for this company
            self.report_progress('sync_started', company_name=company_name)

            # --- Phase 1: Stock Items (always full — just current balances) ---
            logger.info("--- Phase 1: Stock Items ---")
            self.financial_year = fys_to_sync[0]
            self.report_progress('sync_started', mode='collection-v6', fys=fys_to_sync, sync_mode=sync_mode)
            self.report_progress('phase_start', phase='inventory')
            items = self.tally.fetch_stock_items()
            self._last_inventory = items  # Store for P&L gross profit calculation
            if items:
                self.save_cache('inventory', items)
                self.sync_to_backend('inventory', items)
            self.report_progress('phase_complete', phase='inventory', count=len(items))
            time.sleep(SLEEP_BETWEEN_REQUESTS)

            # --- Phase 2-5: Sales, Receipts, Credit Notes, Journals (per FY) ---
            all_sales_combined = []
            all_receipts_combined = []
            all_credit_notes_combined = []
            all_journals_combined = []
            all_stock_journals_combined = []
            all_purchases_combined = []
            all_debit_notes_combined = []

            for fy in fys_to_sync:
                self.financial_year = fy
                fy_start, fy_end = fy_to_dates(fy)

                months = list(months_in_fy(fy, cap_date=last_voucher_date))
                logger.info(f"--- Full sync FY {fy}: {len(months)} months ---")

                # Phase 2: Sales
                logger.info(f"  Phase 2: Sales Vouchers (FY {fy})")
                self.report_progress('phase_start', phase='sales')
                fy_sales = []
                for m_start, m_end in months:
                    fy_sales.extend(self.tally.fetch_sales_month(m_start, m_end))
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_sales:
                    self.save_cache(f'sales_{fy}', fy_sales)
                    self.sync_to_backend('sales', fy_sales)
                    all_sales_combined.extend(fy_sales)
                logger.info(f"  FY {fy}: {len(fy_sales)} sales vouchers")
                self.report_progress('phase_complete', phase='sales', count=len(fy_sales))

                # Phase 3: Receipts
                logger.info(f"  Phase 3: Receipts/Payments (FY {fy})")
                self.report_progress('phase_start', phase='receipts')
                fy_receipts = []
                for m_start, m_end in months:
                    fy_receipts.extend(self.tally.fetch_receipts_month(m_start, m_end))
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_receipts:
                    self.save_cache(f'receipts_{fy}', fy_receipts)
                    self.sync_to_backend('receipts', fy_receipts)
                    all_receipts_combined.extend(fy_receipts)
                logger.info(f"  FY {fy}: {len(fy_receipts)} receipt vouchers")
                self.report_progress('phase_complete', phase='receipts', count=len(fy_receipts))

                # Phase 4: Credit Notes
                logger.info(f"  Phase 4: Credit Notes (FY {fy})")
                self.report_progress('phase_start', phase='credit_notes')
                fy_cn = []
                for m_start, m_end in months:
                    fy_cn.extend(self.tally.fetch_credit_notes_month(m_start, m_end))
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_cn:
                    self.save_cache(f'credit_notes_{fy}', fy_cn)
                    self.sync_to_backend('credit_notes', fy_cn)
                    all_credit_notes_combined.extend(fy_cn)
                logger.info(f"  FY {fy}: {len(fy_cn)} credit notes")
                self.report_progress('phase_complete', phase='credit_notes', count=len(fy_cn))

                # Phase 5a: Journal Vouchers (Sundry Debtors)
                logger.info(f"  Phase 5a: Journal Vouchers (FY {fy})")
                self.report_progress('phase_start', phase='journals')
                fy_jv = []
                for m_start, m_end in months:
                    fy_jv.extend(self.tally.fetch_journals_month(m_start, m_end))
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_jv:
                    self.save_cache(f'journals_{fy}', fy_jv)
                    self.sync_to_backend('journal_vouchers', fy_jv)
                    all_journals_combined.extend(fy_jv)
                logger.info(f"  FY {fy}: {len(fy_jv)} journal vouchers")
                self.report_progress('phase_complete', phase='journals', count=len(fy_jv))

                # Phase 5b: Stock Journals
                logger.info(f"  Phase 5b: Stock Journals (FY {fy})")
                self.report_progress('phase_start', phase='stock_journals')
                fy_sj = []
                for m_start, m_end in months:
                    fy_sj.extend(self.tally.fetch_stock_journals_month(m_start, m_end))
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_sj:
                    self.save_cache(f'stock_journals_{fy}', fy_sj)
                    self.sync_to_backend('stock_journals', fy_sj)
                    all_stock_journals_combined.extend(fy_sj)
                logger.info(f"  FY {fy}: {len(fy_sj)} stock journals")
                self.report_progress('phase_complete', phase='stock_journals', count=len(fy_sj))

                # Phase 6: Purchase Vouchers
                logger.info(f"  Phase 6: Purchase Vouchers (FY {fy})")
                self.report_progress('phase_start', phase='purchases')
                fy_purchases = []
                for m_start, m_end in months:
                    pvs = self.tally.fetch_purchases_month(m_start, m_end)
                    fy_purchases.extend(pvs)
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_purchases:
                    self.save_cache(f'purchase_vouchers_{fy}', fy_purchases)
                    self.sync_to_backend('purchase_vouchers', fy_purchases)
                    all_purchases_combined.extend(fy_purchases)
                logger.info(f"  FY {fy}: {len(fy_purchases)} purchase vouchers")
                self.report_progress('phase_complete', phase='purchases', count=len(fy_purchases))

                # Phase 7: Debit Notes
                logger.info(f"  Phase 7: Debit Notes (FY {fy})")
                self.report_progress('phase_start', phase='debit_notes')
                fy_dn = []
                for m_start, m_end in months:
                    dns = self.tally.fetch_debit_notes_month(m_start, m_end)
                    fy_dn.extend(dns)
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_dn:
                    self.save_cache(f'debit_notes_{fy}', fy_dn)
                    self.sync_to_backend('debit_notes', fy_dn)
                    all_debit_notes_combined.extend(fy_dn)
                logger.info(f"  FY {fy}: {len(fy_dn)} debit notes")
                self.report_progress('phase_complete', phase='debit_notes', count=len(fy_dn))

            # ── RECONCILE after ALL FYs (uses combined IDs so cross-FY data is preserved) ──
            logger.info("--- Reconciling all voucher types across FYs ---")
            self.reconcile_with_backend('sales', [v.get('voucher_id', '') for v in all_sales_combined if v.get('voucher_id')])
            self.reconcile_with_backend('receipts', [v.get('voucher_id', '') for v in all_receipts_combined if v.get('voucher_id')])
            self.reconcile_with_backend('credit_notes', [v.get('voucher_id', '') for v in all_credit_notes_combined if v.get('voucher_id')])
            self.reconcile_with_backend('journal_vouchers', [v.get('voucher_id', '') for v in all_journals_combined if v.get('voucher_id')])
            self.reconcile_with_backend('stock_journals', [v.get('voucher_id', '') for v in all_stock_journals_combined if v.get('voucher_id')])
            self.reconcile_with_backend('purchase_vouchers', [v.get('voucher_id', '') for v in all_purchases_combined if v.get('voucher_id')])
            self.reconcile_with_backend('debit_notes', [v.get('voucher_id', '') for v in all_debit_notes_combined if v.get('voucher_id')])

            # --- Phase 6: Customer Ledgers (always full — just current balances) ---
            self.financial_year = fys_to_sync[0]
            logger.info("--- Phase 4: Customer Ledgers ---")
            self.report_progress('phase_start', phase='customers')
            customers = self.tally.fetch_customers()
            if customers:
                cust_sales = {}
                for v in all_sales_combined:
                    p = v.get('party_name', '')
                    if p:
                        k = p.lower()
                        if k not in cust_sales:
                            cust_sales[k] = {'total': 0, 'count': 0}
                        cust_sales[k]['total'] += v.get('total_amount', 0)
                        cust_sales[k]['count'] += 1
                for c in customers:
                    k = c['customer_name'].lower()
                    if k in cust_sales:
                        c['total_purchases'] = cust_sales[k]['total']
                        c['transaction_count'] = cust_sales[k]['count']
                self.save_cache('customers', customers)
                self.sync_to_backend('customers', customers)
            # Reconcile: remove customers deleted from Tally*
            cust_names = [c.get('customer_name', '') for c in customers if c.get('customer_name')]
            self.reconcile_with_backend('customers', cust_names, id_key='customer_name')
            self.report_progress('phase_complete', phase='customers', count=len(customers))

            # --- Phase 8: Sundry Creditors (current balances) ---
            logger.info("--- Phase 8: Sundry Creditors ---")
            self.report_progress('phase_start', phase='sundry_creditors')
            creditors = self.tally.fetch_sundry_creditors()
            if not creditors:
                logger.info("  Primary creditor fetch returned empty — running group-walker fallback")
                creditors = self.tally.fetch_creditors_from_all_ledgers()
            if creditors:
                self.save_cache('sundry_creditors', creditors)
                self.sync_to_backend('sundry_creditors', creditors)
            # Reconcile sundry creditors
            cred_names = [c.get('creditor_name', '') for c in creditors if c.get('creditor_name')]
            self.reconcile_with_backend('sundry_creditors', cred_names, id_key='creditor_name')
            logger.info(f"  Got {len(creditors)} sundry creditors")
            self.report_progress('phase_complete', phase='sundry_creditors', count=len(creditors))

            # --- Phase 9: Contra Vouchers (bank-to-bank, cash-to-bank) per FY ---
            logger.info("--- Phase 9: Contra Vouchers ---")
            self.report_progress('phase_start', phase='contra_vouchers')
            all_contra_combined = []
            for fy in fys_to_sync:
                self.financial_year = fy
                fy_start, fy_end = fy_to_dates(fy)
                fy_contra = []
                for m_start, m_end in months_in_fy(fy, cap_date=last_voucher_date):
                    fy_contra.extend(self.tally.fetch_contra_vouchers_month(m_start, m_end))
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                if fy_contra:
                    self.save_cache(f'contra_vouchers_{fy}', fy_contra)
                    self.sync_to_backend('contra_vouchers', fy_contra)
                    all_contra_combined.extend(fy_contra)
                logger.info(f"  FY {fy}: {len(fy_contra)} contra vouchers")
            self.reconcile_with_backend('contra_vouchers', [v.get('voucher_id', '') for v in all_contra_combined if v.get('voucher_id')])
            self.report_progress('phase_complete', phase='contra_vouchers', count=len(all_contra_combined))

            # --- Phase 10: All Ledgers (Balance Sheet + P&L) ---
            logger.info("--- Phase 10: All Ledgers (Balance Sheet + P&L) ---")
            self.report_progress('phase_start', phase='ledgers')
            all_ledgers = self.tally.fetch_all_ledgers()
            bank_cash = []

            # Note: Balance Sheet snapshots are now computed on the backend from
            # the synced `all_ledgers` collection (avoids extra Tally roundtrips
            # which timeout on large company files). The backend uses today's FY
            # closing_balance for current-FY view and opening_balance (= prev-FY
            # closing) for prev-FY view.
            if all_ledgers:
                self.save_cache('all_ledgers', all_ledgers)
                self.sync_to_backend('all_ledgers', all_ledgers)

                # Extract bank/cash subset for backward compatibility
                bank_cash = [l for l in all_ledgers if l['category'] in ('bank', 'bank_od', 'cash')]
                if bank_cash:
                    self.sync_to_backend('bank_cash_ledgers', bank_cash)
                logger.info(f"  Bank/Cash: {len(bank_cash)} ledgers")

                # Compute P&L summary
                # Get stock values for gross profit calculation
                opening_stock = sum(i.get('opening_value', 0) or 0 for i in (self._last_inventory or []))
                closing_stock = sum(i.get('closing_value', 0) or 0 for i in (self._last_inventory or []))
                # Get sales and purchase totals from synced vouchers
                total_sales_fy = sum(abs(float(v.get('total_amount', 0) or 0)) for v in all_sales_combined)
                total_purchases_fy = sum(abs(float(v.get('total_amount', 0) or 0)) for v in all_purchases_combined)

                pl_summary = self.tally.compute_pl_summary(
                    all_ledgers,
                    opening_stock=opening_stock,
                    closing_stock=closing_stock,
                    total_sales_fy=total_sales_fy,
                    total_purchases_fy=total_purchases_fy
                )

                # Build P&L data in the format backend expects
                income_ledgers = [{'ledger_name': l['ledger_name'], 'parent_group': l['parent_group'],
                                   'amount': round(abs(l['closing_balance']), 2), 'is_debit': l['closing_balance'] > 0}
                                  for l in all_ledgers if l['category'] in ('direct_income', 'indirect_income')]
                expense_ledgers = [{'ledger_name': l['ledger_name'], 'parent_group': l['parent_group'],
                                    'amount': round(abs(l['closing_balance']), 2), 'is_debit': l['closing_balance'] > 0}
                                   for l in all_ledgers if l['category'] in ('direct_expense', 'indirect_expense')]

                pl_data = {
                    'income': income_ledgers,
                    'expense': expense_ledgers,
                    'total_income': pl_summary['total_income'],
                    'total_expense': pl_summary['total_expense'],
                    'net_profit_loss': pl_summary['net_profit'],
                    'gross_profit': pl_summary['gross_profit'],
                    'is_gross_loss': pl_summary['is_gross_loss'],
                    'is_net_loss': pl_summary['is_net_loss'],
                    'opening_stock': pl_summary['opening_stock'],
                    'closing_stock': pl_summary['closing_stock'],
                    'pl_ac_opening': pl_summary['pl_ac_opening'],
                    'pl_ac_closing': pl_summary['pl_ac_closing'],
                }
                self.save_cache('profit_loss', pl_data)
                self.sync_to_backend('profit_loss', [pl_data])

                gp_label = "Gross Loss" if pl_summary['is_gross_loss'] else "Gross Profit"
                np_label = "Net Loss" if pl_summary['is_net_loss'] else "Net Profit"
                logger.info(f"  {gp_label}: {abs(pl_summary['gross_profit']):,.2f}")
                logger.info(f"  {np_label}: {abs(pl_summary['net_profit']):,.2f}")
                logger.info(f"  P&L: {len(income_ledgers)} income, {len(expense_ledgers)} expense ledgers")
            else:
                logger.warning("  No ledgers fetched from Tally*")

            # Reconcile bank/cash ledgers
            bc_names = [l.get('ledger_name', '') for l in bank_cash if l.get('ledger_name')]
            self.reconcile_with_backend('bank_cash_ledgers', bc_names, id_key='ledger_name')
            self.report_progress('phase_complete', phase='ledgers', count=len(all_ledgers))

            # Free memory
            gc.collect()

            # Mark first full sync as done for this company (persisted to disk)
            if sync_mode == 'full':
                state = load_sync_state()
                if 'companies' not in state:
                    state['companies'] = {}
                if company_name not in state['companies']:
                    state['companies'][company_name] = {'hashes': {}, 'last_sync': {}}
                state['companies'][company_name]['full_sync_done'] = True
                state['companies'][company_name]['full_sync_at'] = datetime.now().isoformat()
                save_sync_state(state)

            # Summary
            total_sales = len(all_sales_combined)
            total_receipts = len(all_receipts_combined)
            total_cn = len(all_credit_notes_combined)
            total_jv = len(all_journals_combined)
            total_sj = len(all_stock_journals_combined)
            total_purchases = len(all_purchases_combined)
            total_dn = len(all_debit_notes_combined)
            total_contra = len(all_contra_combined)
            income_count = sum(1 for l in (all_ledgers or []) if l.get('category') in ('direct_income', 'indirect_income'))
            expense_count = sum(1 for l in (all_ledgers or []) if l.get('category') in ('direct_expense', 'indirect_expense'))
            logger.info("")
            logger.info(f"[DONE] {sync_mode.capitalize()} sync completed at {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"  FYs synced:     {', '.join(fys_to_sync)}")
            logger.info(f"  Inventory:      {len(items)} items")
            logger.info(f"  Sales:          {total_sales} vouchers")
            logger.info(f"  Purchases:      {total_purchases} vouchers")
            logger.info(f"  Debit Notes:    {total_dn} vouchers")
            logger.info(f"  Receipts:       {total_receipts} vouchers")
            logger.info(f"  Credit Notes:   {total_cn} vouchers")
            logger.info(f"  Journals:       {total_jv} vouchers")
            logger.info(f"  Stock Journals: {total_sj} vouchers")
            logger.info(f"  Contra:         {total_contra} vouchers")
            logger.info(f"  Bank/Cash:      {len(bank_cash)} ledgers")
            logger.info(f"  P&L:            {income_count} income + {expense_count} expense")
            logger.info(f"  Customers:      {len(customers)} ledgers")
            logger.info(f"  Creditors:      {len(creditors)} ledgers")
            logger.info("=" * 60)

            state = load_sync_state()
            state['last_sync_time'] = datetime.now().isoformat()
            state['last_results'] = {
                'inventory': len(items), 'sales': total_sales,
                'receipts': total_receipts, 'credit_notes': total_cn,
                'journals': total_jv, 'stock_journals': total_sj,
                'customers': len(customers)
            }
            state['company'] = self.tally.company
            state['fys_synced'] = fys_to_sync
            state['sync_mode'] = sync_mode
            save_sync_state(state)

            self.report_progress('sync_complete',
                                 inventory=len(items), sales=total_sales,
                                 receipts=total_receipts, credit_notes=total_cn,
                                 journals=total_jv, stock_journals=total_sj,
                                 customers=len(customers),
                                 fys_synced=fys_to_sync, sync_mode=sync_mode)

        except Exception as e:
            logger.error(f"Sync error for {company_name}: {e}")
            self.report_progress('sync_error', error=str(e))

    def start(self):
        if ENABLE_WS:
            self.ws_server = WebSocketServer(port=WS_PORT)
            self.ws_server.start()

        # Select companies to sync
        self.select_companies()

        # Discover FYs and ask user to select starting FY
        self._sync_fys = None  # Will be set by discover_and_select_fys
        self.discover_and_select_fys()

        # Initial sync
        self.run_sync_cycle()

        # Schedule: full sync every N min, sales quick sync every 5 min
        schedule.every(self.sync_interval).minutes.do(self.run_sync_cycle)
        schedule.every(SALES_SYNC_INTERVAL).minutes.do(self.run_sales_quick_sync)
        logger.info(f"Full sync every {self.sync_interval} min | Sales quick sync every {SALES_SYNC_INTERVAL} min")
        logger.info("Type Ctrl+C to exit. Run with --logout to clear saved credentials.")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            sys.exit(0)


if __name__ == "__main__":
    # Handle --logout flag
    if '--logout' in sys.argv:
        clear_auth_config()
        print("Saved credentials cleared. Run again to log in.")
        sys.exit(0)

    agent = FlowraSyncAgent()
    agent.start()
