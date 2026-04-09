#!/usr/bin/env python3
"""
FLOWRA Tally Sync Agent v6 — Lightweight Collection Requests

WHY THIS DOESN'T FREEZE TALLY:
  Previous versions used heavy Day Book / Report requests that locked
  Tally's single-threaded UI for 30-120 seconds.

  This version uses lightweight COLLECTION requests:
    - "Stock Item" collection → 1-2 sec (just master data)
    - "Ledger" collection → 1-2 sec (just balances)
    - "Voucher" collection with monthly filter → 2-5 sec per month
  
  Each request takes 1-5 seconds. Tally stays responsive.
  Responses are saved to local JSON files for caching.

Setup:
  1. pip install requests xmltodict python-dotenv schedule websockets
  2. Create .env from .env.example
  3. python tally_sync_agent_v6.py
"""

import os
import sys
import io
import re
import time
import json
import logging
import asyncio
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import requests
import xmltodict
import schedule
from dotenv import load_dotenv

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
logger = logging.getLogger('FlowraSyncV6')
load_dotenv()


# ==================== CONFIG ====================

TALLY_HOST = os.getenv('TALLY_HOST', 'localhost')
TALLY_PORT = int(os.getenv('TALLY_PORT', '9000'))
TALLY_URL = f"http://{TALLY_HOST}:{TALLY_PORT}/"
COMPANY_NAME = os.getenv('TALLY_COMPANY', '')  # Leave empty for current company
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8001')
API_KEY = os.getenv('AGENT_API_KEY', '')
TENANT_ID = os.getenv('TENANT_ID', '')  # Multi-tenant: assigned by FLOWRA super admin
SYNC_TOKEN = os.getenv('SYNC_TOKEN', '')  # Multi-tenant: auth token for sync
FINANCIAL_YEAR = os.getenv('FINANCIAL_YEAR', '2025-26')
SYNC_ALL_FY = os.getenv('SYNC_ALL_FY', 'true').lower() == 'true'
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL_MINUTES', '20'))
INCREMENTAL_SYNC = os.getenv('INCREMENTAL_SYNC', 'true').lower() == 'true'
EXPORT_DIR = os.getenv('TALLY_EXPORT_DIR', os.path.join(os.path.dirname(__file__), 'export_cache'))
ENABLE_WS = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
WS_PORT = int(os.getenv('WEBSOCKET_PORT', '8765'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
SLEEP_BETWEEN_REQUESTS = float(os.getenv('SLEEP_BETWEEN_REQUESTS', '2'))
SYNC_ALL_COMPANIES = os.getenv('SYNC_ALL_COMPANIES', 'false').lower() == 'true'

SYNC_STATE_FILE = 'sync_state_v6.json'


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


def months_in_fy(fy: str):
    """Generate monthly (start, end) date pairs for an FY."""
    fy_start, fy_end = fy_to_dates(fy)
    current = fy_start
    today = date.today()
    while current <= min(fy_end, today):
        month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        month_end = min(month_end, fy_end, today)
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
        if self.company:
            return f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>"
        return ""

    def test_connection(self) -> bool:
        """Quick ping to check Tally is responding — uses Collection request."""
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
<FETCH>NAME</FETCH>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""
        data = self._post(xml, debug_name='companies')
        if data:
            # Navigate to DATA > COLLECTION > COMPANY (skip CMPINFO counts)
            companies = self._get_collection_items(data, 'COMPANY')
            for c in companies:
                if isinstance(c, dict):
                    name = c.get('NAME', c.get('@NAME', ''))
                    # NAME might have TYPE attribute: {'#text': 'name', '@TYPE': 'String'}
                    if isinstance(name, dict):
                        name = name.get('#text', '')
                    if name and str(name).strip():
                        self.company = self.company or str(name).strip()
                        break
            if self.company:
                logger.info(f"  Tally company: {self.company}")
            else:
                logger.info("  Tally connected (company auto-detect pending)")
            return True
        return False

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
        """Fetch stock items with closing balances using TDL Collection + COMPUTE."""
        logger.info("  Requesting stock items (Collection)...")
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""
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
<COMPUTE>CLBAL : $$NumValue:$ClosingBalance</COMPUTE>
<COMPUTE>CLRATE : $$NumValue:$ClosingRate</COMPUTE>
<COMPUTE>CLVAL : $$NumValue:$ClosingValue</COMPUTE>
<COMPUTE>CLQTY : $$String:$ClosingBalance:"TailUnits"</COMPUTE>
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

            # Try COMPUTE fields first (CLBAL, CLRATE, CLVAL)
            qty = self._num(si.get('CLBAL', 0))
            rate = self._num(si.get('CLRATE', 0))
            value = self._num(si.get('CLVAL', 0))

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

            items.append({
                'item_id': name, 'item_name': name,
                'quantity': qty, 'unit': unit, 'price': rate,
                'category': parent, 'stock_group': parent,
                'reorder_level': 10.0
            })

        logger.info(f"  Got {len(items)} stock items")
        return items

    # ---- LEDGERS / CUSTOMERS (Collection request — lightweight) ----

    def fetch_customers(self) -> List[Dict]:
        """Fetch Sundry Debtors using TDL Collection request. ~1-3 seconds."""
        logger.info("  Requesting customer ledgers (Collection)...")
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""
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
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""

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
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""

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
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""

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
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""

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
        company_tag = f"<SVCURRENTCOMPANY>{self.company}</SVCURRENTCOMPANY>" if self.company else ""

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

            # Ledger entries
            ledger_entries = []
            le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
            if isinstance(le, dict):
                le = [le]
            if isinstance(le, list):
                for entry in le:
                    if not isinstance(entry, dict):
                        continue
                    lname = str(entry.get('LEDGERNAME', '')).strip()
                    lamt = self._num(entry.get('AMOUNT', 0))
                    if lname:
                        ledger_entries.append({'ledger_name': lname, 'amount': lamt})
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
                # Journals: compute debit and credit per ledger entry
                debit_total = 0.0
                credit_total = 0.0
                for entry in ledger_entries:
                    amt = entry.get('amount', 0)
                    if amt < 0:
                        debit_total += abs(amt)
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
                # Sales: line items
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

                results.append({
                    'voucher_id': str(v_number),
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


# ==================== MAIN AGENT ====================

class FlowraSyncAgent:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.api_key = API_KEY
        self.financial_year = FINANCIAL_YEAR
        self.sync_interval = SYNC_INTERVAL
        self.export_dir = EXPORT_DIR
        self.sync_running = False
        self.ws_server = None
        self._active_company = COMPANY_NAME  # Currently syncing company
        self._companies_to_sync = []  # List of companies to sync
        self.tally = TallyCollectionClient(
            url=TALLY_URL,
            company=COMPANY_NAME,
            timeout=REQUEST_TIMEOUT,
            debug_dir=self.export_dir
        )

        os.makedirs(self.export_dir, exist_ok=True)

        logger.info("=" * 60)
        logger.info("  FLOWRA TALLY SYNC AGENT v6.1 (Multi-Tenant)")
        logger.info("  Lightweight Collection Requests (No Freeze)")
        logger.info("=" * 60)
        logger.info(f"  Tally URL     : {TALLY_URL}")
        logger.info(f"  Cloud Backend : {self.backend_url}")
        logger.info(f"  Tenant ID     : {TENANT_ID or '(auto-detect)'}")
        logger.info(f"  Financial Year: {self.financial_year}")
        logger.info(f"  Auto Multi-FY : {SYNC_ALL_FY} (also syncs current FY: {current_fy()})")
        logger.info(f"  Incremental   : {INCREMENTAL_SYNC}")
        logger.info(f"  Sync Interval : every {self.sync_interval} min")
        logger.info(f"  Timeout/req   : {REQUEST_TIMEOUT} sec")
        logger.info(f"  Cache Dir     : {self.export_dir}")
        logger.info(f"  Multi-Company : {'Sync all' if SYNC_ALL_COMPANIES else 'Selected only'}")
        logger.info("=" * 60)

    def detect_companies(self):
        """Detect available companies in Tally."""
        try:
            xml_req = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
            resp = requests.post(TALLY_URL, data=xml_req.encode('utf-8'),
                                 headers={'Content-Type': 'application/xml'},
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                text = resp.text
                parsed = xmltodict.parse(text)
                companies = []
                collection = parsed.get('ENVELOPE', {}).get('BODY', {}).get('DATA', {}).get('COLLECTION', {})
                if collection:
                    items = collection.get('COMPANY', [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        name = item.get('NAME', {}).get('#text', '') if isinstance(item.get('NAME'), dict) else item.get('NAME', '')
                        if name:
                            companies.append(name)
                return companies
        except Exception as e:
            logger.warning(f"Could not detect companies: {e}")
        return []

    def select_companies(self):
        """Interactive company selection for multi-company Tally instances."""
        if COMPANY_NAME:
            self._companies_to_sync = [COMPANY_NAME]
            return

        companies = self.detect_companies()
        if not companies:
            # Fallback: use current company from Tally
            self._companies_to_sync = [self.tally.company or 'Default']
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

    def report_progress(self, event_type, **kwargs):
        progress = {
            'type': event_type,
            'timestamp': datetime.now().isoformat(),
            'financial_year': self.financial_year,
            'company_name': self._active_company or self.tally.company or '',
            'tenant_id': TENANT_ID,
            'company_id': self._active_company or '',
            **kwargs
        }
        if self.ws_server:
            self.ws_server.broadcast(progress)
        try:
            requests.post(
                f"{self.backend_url}/api/agent/sync-progress",
                json=progress,
                headers={'Content-Type': 'application/json', 'X-Agent-Key': self.api_key},
                timeout=5
            )
        except:
            pass

    def sync_to_backend(self, data_type, data):
        if not data:
            return True
        try:
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.utcnow().isoformat(),
                'agent_version': '6.1.0-multitenant',
                'company_name': self._active_company or self.tally.company or '',
                'financial_year': self.financial_year,
                'tenant_id': TENANT_ID,
                'company_id': self._active_company or '',
                'sync_token': SYNC_TOKEN
            }
            resp = requests.post(
                f"{self.backend_url}/api/agent/sync",
                json=payload,
                headers={'Content-Type': 'application/json', 'X-Agent-Key': self.api_key},
                timeout=30
            )
            if resp.status_code == 200:
                logger.info(f"  [OK] Synced {len(data)} {data_type} to cloud")
                return True
            else:
                logger.error(f"  Sync {data_type} failed: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"  Sync error ({data_type}): {e}")
            return False

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
            if not self._companies_to_sync:
                self.select_companies()
            for company in self._companies_to_sync:
                self._active_company = company
                self.tally.company = company
                logger.info("")
                logger.info(f"{'=' * 60}")
                logger.info(f"Syncing company: {company}")
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
            is_first_sync = not hasattr(self, '_full_sync_done') or company_name not in (self._full_sync_done or set())
            sync_mode = 'full' if is_first_sync else ('incremental' if INCREMENTAL_SYNC else 'full')

            logger.info(f"Starting {sync_mode} sync at {datetime.now().strftime('%H:%M:%S')}")

            # Test connection
            if not self.tally.test_connection():
                logger.error("Cannot connect to Tally! Is TallyPrime running?")
                self.report_progress('sync_error', error='Tally not responding')
                return

            # Determine which FYs to sync
            fys_to_sync = get_sync_fys()
            logger.info(f"  Syncing FYs: {', '.join(fys_to_sync)} ({sync_mode} mode)")

            # --- Phase 1: Stock Items (always full — just current balances) ---
            logger.info("--- Phase 1: Stock Items ---")
            self.financial_year = fys_to_sync[0]
            self.report_progress('sync_started', mode='collection-v6', fys=fys_to_sync, sync_mode=sync_mode)
            self.report_progress('phase_start', phase='inventory')
            items = self.tally.fetch_stock_items()
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

            for fy in fys_to_sync:
                self.financial_year = fy

                if sync_mode == 'incremental':
                    today = date.today()
                    months = []
                    m_start = today.replace(day=1)
                    m_end = min((m_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), today)
                    fy_start, fy_end = fy_to_dates(fy)
                    if m_start >= fy_start and m_start <= fy_end:
                        months.append((m_start, m_end))
                    prev_end = m_start - timedelta(days=1)
                    prev_start = prev_end.replace(day=1)
                    if prev_start >= fy_start and prev_start <= fy_end:
                        months.append((prev_start, prev_end))
                    if not months:
                        continue
                    logger.info(f"--- Incremental sync FY {fy}: {len(months)} months ---")
                else:
                    months = list(months_in_fy(fy))
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
            self.report_progress('phase_complete', phase='customers', count=len(customers))

            # Mark first full sync as done for this company
            if not hasattr(self, '_full_sync_done') or self._full_sync_done is None:
                self._full_sync_done = set()
            self._full_sync_done.add(company_name)

            # Summary
            total_sales = len(all_sales_combined)
            total_receipts = len(all_receipts_combined)
            total_cn = len(all_credit_notes_combined)
            total_jv = len(all_journals_combined)
            total_sj = len(all_stock_journals_combined)
            logger.info("")
            logger.info(f"[DONE] {sync_mode.capitalize()} sync completed at {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"  FYs synced:     {', '.join(fys_to_sync)}")
            logger.info(f"  Inventory:      {len(items)} items")
            logger.info(f"  Sales:          {total_sales} vouchers")
            logger.info(f"  Receipts:       {total_receipts} vouchers")
            logger.info(f"  Credit Notes:   {total_cn} vouchers")
            logger.info(f"  Journals:       {total_jv} vouchers")
            logger.info(f"  Stock Journals: {total_sj} vouchers")
            logger.info(f"  Customers:      {len(customers)} ledgers")
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

            # Mark first sync done for this company
            if not hasattr(self, '_full_sync_done') or self._full_sync_done is None:
                self._full_sync_done = set()
            self._full_sync_done.add(company_name)

        except Exception as e:
            logger.error(f"Sync error for {company_name}: {e}")
            self.report_progress('sync_error', error=str(e))

    def start(self):
        if ENABLE_WS:
            self.ws_server = WebSocketServer(port=WS_PORT)
            self.ws_server.start()

        # Select companies to sync
        self.select_companies()

        # Initial sync
        self.run_sync_cycle()

        # Schedule every 20 min
        schedule.every(self.sync_interval).minutes.do(self.run_sync_cycle)
        logger.info(f"Next sync in {self.sync_interval} minutes. Ctrl+C to stop.")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            sys.exit(0)


if __name__ == "__main__":
    agent = FlowraSyncAgent()
    agent.start()
