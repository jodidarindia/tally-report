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
FINANCIAL_YEAR = os.getenv('FINANCIAL_YEAR', '2025-26')
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL_MINUTES', '20'))
EXPORT_DIR = os.getenv('TALLY_EXPORT_DIR', os.path.join(os.path.dirname(__file__), 'export_cache'))
ENABLE_WS = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
WS_PORT = int(os.getenv('WEBSOCKET_PORT', '8765'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))  # 15 sec per request (lightweight!)
SLEEP_BETWEEN_REQUESTS = float(os.getenv('SLEEP_BETWEEN_REQUESTS', '2'))  # 2 sec gap

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

    def __init__(self, url=TALLY_URL, company='', timeout=15):
        self.url = url
        self.company = company
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'text/xml',
            'Cache-Control': 'no-cache'
        })

    def _sanitize(self, xml_text):
        xml_text = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', xml_text)
        xml_text = re.sub(r'&#[0-9]+;?', ' ', xml_text)
        xml_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml_text)
        return xml_text

    def _post(self, xml_payload: str) -> Optional[dict]:
        try:
            resp = self.session.post(self.url, data=xml_payload, timeout=self.timeout)
            if resp.status_code == 200:
                clean = self._sanitize(resp.text)
                return xmltodict.parse(clean)
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
        """Quick ping to check Tally is responding."""
        xml = f"""<ENVELOPE>
            <HEADER><VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Data</TYPE><ID>List of Companies</ID></HEADER>
            <BODY><DESC><STATICVARIABLES>
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            </STATICVARIABLES></DESC></BODY></ENVELOPE>"""
        data = self._post(xml)
        if data:
            # Try to extract company name
            companies = self._find_deep(data, 'COMPANY')
            if companies:
                if isinstance(companies, list):
                    names = [c.get('NAME', c.get('@NAME', str(c))) for c in companies if isinstance(c, dict)]
                    if names:
                        self.company = self.company or str(names[0])
                        logger.info(f"  Tally company: {self.company}")
                elif isinstance(companies, dict):
                    name = companies.get('NAME', companies.get('@NAME', ''))
                    if name:
                        self.company = self.company or str(name)
                elif isinstance(companies, str):
                    self.company = self.company or companies
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

    def _num(self, val):
        if val is None:
            return 0.0
        s = str(val).replace(',', '').strip()
        if not s:
            return 0.0
        try:
            return abs(float(s.split()[0]))
        except:
            return 0.0

    def _qty_unit(self, val):
        if val is None or str(val).strip() == '':
            return 0.0, 'Pcs'
        parts = str(val).strip().split()
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

    # ---- STOCK ITEMS (lightweight: just master data) ----

    def fetch_stock_items(self) -> List[Dict]:
        """Fetch stock items with closing balance. ~1-2 seconds."""
        logger.info("  Requesting stock items collection...")
        xml = f"""<ENVELOPE>
            <HEADER><VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Collection</TYPE>
            <ID>Stock Item</ID></HEADER>
            <BODY><DESC>
            <STATICVARIABLES>
            {self._company_tag()}
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            </STATICVARIABLES>
            <TDL><TDLMESSAGE>
            <COLLECTION NAME="Stock Item" ISMODIFY="No">
            <TYPE>Stock Item</TYPE>
            <NATIVEMETHOD>Name</NATIVEMETHOD>
            <NATIVEMETHOD>Parent</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingValue</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingRate</NATIVEMETHOD>
            <NATIVEMETHOD>BaseUnits</NATIVEMETHOD>
            </COLLECTION>
            </TDLMESSAGE></TDL>
            </DESC></BODY></ENVELOPE>"""

        data = self._post(xml)
        if not data:
            return []

        items = []
        stock_list = self._find_deep(data, 'STOCKITEM')
        if not stock_list:
            stock_list = self._find_deep(data, 'COLLECTION')
        if not stock_list:
            return []
        if not isinstance(stock_list, list):
            stock_list = [stock_list]

        for si in stock_list:
            if not isinstance(si, dict):
                continue
            name = str(si.get('NAME', si.get('@NAME', '')) or '').strip()
            if not name:
                continue
            parent = str(si.get('PARENT', 'General') or 'General').strip()
            cb = si.get('CLOSINGBALANCE', 0)
            qty, unit = self._qty_unit(cb)
            cr = si.get('CLOSINGRATE', 0)
            rate = self._num(str(cr).split('/')[0]) if cr else 0
            cv = self._num(si.get('CLOSINGVALUE', 0))
            if rate == 0 and qty > 0 and cv > 0:
                rate = round(cv / qty, 2)
            items.append({
                'item_id': name, 'item_name': name,
                'quantity': qty, 'unit': unit, 'price': rate,
                'category': parent, 'stock_group': parent,
                'reorder_level': 10.0
            })

        logger.info(f"  Got {len(items)} stock items")
        return items

    # ---- LEDGERS / CUSTOMERS (lightweight: just balances) ----

    def fetch_customers(self) -> List[Dict]:
        """Fetch Sundry Debtors ledgers with closing balance. ~1-2 seconds."""
        logger.info("  Requesting customer ledgers...")
        xml = f"""<ENVELOPE>
            <HEADER><VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Collection</TYPE>
            <ID>Flowra Debtors</ID></HEADER>
            <BODY><DESC>
            <STATICVARIABLES>
            {self._company_tag()}
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            </STATICVARIABLES>
            <TDL><TDLMESSAGE>
            <COLLECTION NAME="Flowra Debtors" ISMODIFY="No">
            <TYPE>Ledger</TYPE>
            <NATIVEMETHOD>Name</NATIVEMETHOD>
            <NATIVEMETHOD>Parent</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
            <NATIVEMETHOD>LedgerPhone</NATIVEMETHOD>
            <NATIVEMETHOD>LedgerContact</NATIVEMETHOD>
            <NATIVEMETHOD>LedStateName</NATIVEMETHOD>
            <FILTER>FlowraDebtorFilter</FILTER>
            </COLLECTION>
            <SYSTEM TYPE="Formulae" NAME="FlowraDebtorFilter">
            $Parent = "Sundry Debtors" OR $Parent = "Sundry Creditors"
            </SYSTEM>
            </TDLMESSAGE></TDL>
            </DESC></BODY></ENVELOPE>"""

        data = self._post(xml)
        if not data:
            return []

        customers = []
        ledgers = self._find_deep(data, 'LEDGER')
        if not ledgers:
            return []
        if not isinstance(ledgers, list):
            ledgers = [ledgers]

        for l in ledgers:
            if not isinstance(l, dict):
                continue
            name = str(l.get('NAME', l.get('@NAME', '')) or '').strip()
            if not name:
                continue
            customers.append({
                'customer_name': name,
                'ledger_group': str(l.get('PARENT', 'Sundry Debtors') or 'Sundry Debtors').strip(),
                'outstanding_amount': self._num(l.get('CLOSINGBALANCE', 0)),
                'phone': str(l.get('LEDGERPHONE', '') or '').strip(),
                'contact_person': str(l.get('LEDGERCONTACT', '') or '').strip(),
                'state': str(l.get('LEDSTATENAME', '') or '').strip(),
                'total_purchases': 0.0,
                'transaction_count': 0
            })

        logger.info(f"  Got {len(customers)} customer ledgers")
        return customers

    # ---- SALES VOUCHERS (monthly batches: ~2-5 sec each) ----

    def fetch_sales_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch sales vouchers for one month. ~2-5 seconds."""
        fd = from_date.strftime("%d-%b-%Y")
        td = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting sales: {fd} to {td}")

        xml = f"""<ENVELOPE>
            <HEADER><VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Collection</TYPE>
            <ID>Flowra Sales Vouchers</ID></HEADER>
            <BODY><DESC>
            <STATICVARIABLES>
            {self._company_tag()}
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            <SVFROMDATE TYPE="Date">{fd}</SVFROMDATE>
            <SVTODATE TYPE="Date">{td}</SVTODATE>
            </STATICVARIABLES>
            <TDL><TDLMESSAGE>
            <COLLECTION NAME="Flowra Sales Vouchers" ISMODIFY="No">
            <TYPE>Voucher</TYPE>
            <NATIVEMETHOD>VoucherNumber</NATIVEMETHOD>
            <NATIVEMETHOD>Date</NATIVEMETHOD>
            <NATIVEMETHOD>PartyLedgerName</NATIVEMETHOD>
            <NATIVEMETHOD>Amount</NATIVEMETHOD>
            <NATIVEMETHOD>Reference</NATIVEMETHOD>
            <NATIVEMETHOD>VoucherTypeName</NATIVEMETHOD>
            <NATIVEMETHOD>Narration</NATIVEMETHOD>
            <NATIVEMETHOD>AllLedgerEntries</NATIVEMETHOD>
            <NATIVEMETHOD>AllInventoryEntries</NATIVEMETHOD>
            <NATIVEMETHOD>BasicShipDispatchThrough</NATIVEMETHOD>
            <NATIVEMETHOD>BasicFinalDestination</NATIVEMETHOD>
            <FILTER>FlowraSalesFilter</FILTER>
            </COLLECTION>
            <SYSTEM TYPE="Formulae" NAME="FlowraSalesFilter">
            $VoucherTypeName = "Sales" OR $VoucherTypeName = "Credit Note"
            </SYSTEM>
            </TDLMESSAGE></TDL>
            </DESC></BODY></ENVELOPE>"""

        data = self._post(xml)
        if not data:
            return []
        return self._parse_vouchers(data, 'sales')

    def fetch_receipts_month(self, from_date: date, to_date: date) -> List[Dict]:
        """Fetch receipt/payment vouchers for one month. ~2-5 seconds."""
        fd = from_date.strftime("%d-%b-%Y")
        td = to_date.strftime("%d-%b-%Y")
        logger.info(f"  Requesting receipts: {fd} to {td}")

        xml = f"""<ENVELOPE>
            <HEADER><VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Collection</TYPE>
            <ID>Flowra Receipt Vouchers</ID></HEADER>
            <BODY><DESC>
            <STATICVARIABLES>
            {self._company_tag()}
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            <SVFROMDATE TYPE="Date">{fd}</SVFROMDATE>
            <SVTODATE TYPE="Date">{td}</SVTODATE>
            </STATICVARIABLES>
            <TDL><TDLMESSAGE>
            <COLLECTION NAME="Flowra Receipt Vouchers" ISMODIFY="No">
            <TYPE>Voucher</TYPE>
            <NATIVEMETHOD>VoucherNumber</NATIVEMETHOD>
            <NATIVEMETHOD>Date</NATIVEMETHOD>
            <NATIVEMETHOD>PartyLedgerName</NATIVEMETHOD>
            <NATIVEMETHOD>Amount</NATIVEMETHOD>
            <NATIVEMETHOD>VoucherTypeName</NATIVEMETHOD>
            <NATIVEMETHOD>Narration</NATIVEMETHOD>
            <NATIVEMETHOD>AllLedgerEntries</NATIVEMETHOD>
            <FILTER>FlowraReceiptFilter</FILTER>
            </COLLECTION>
            <SYSTEM TYPE="Formulae" NAME="FlowraReceiptFilter">
            $VoucherTypeName = "Receipt" OR $VoucherTypeName = "Payment" OR $VoucherTypeName = "Contra" OR $VoucherTypeName = "Journal"
            </SYSTEM>
            </TDLMESSAGE></TDL>
            </DESC></BODY></ENVELOPE>"""

        data = self._post(xml)
        if not data:
            return []
        return self._parse_vouchers(data, 'receipt')

    def _parse_vouchers(self, data: dict, vtype: str) -> List[Dict]:
        """Parse voucher XML response into clean dicts."""
        vouchers_raw = self._find_deep(data, 'VOUCHER')
        if not vouchers_raw:
            return []
        if not isinstance(vouchers_raw, list):
            vouchers_raw = [vouchers_raw]

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
        self.tally = TallyCollectionClient(
            url=TALLY_URL,
            company=COMPANY_NAME,
            timeout=REQUEST_TIMEOUT
        )

        os.makedirs(self.export_dir, exist_ok=True)

        logger.info("=" * 60)
        logger.info("  FLOWRA TALLY SYNC AGENT v6")
        logger.info("  Lightweight Collection Requests (No Freeze)")
        logger.info("=" * 60)
        logger.info(f"  Tally URL     : {TALLY_URL}")
        logger.info(f"  Cloud Backend : {self.backend_url}")
        logger.info(f"  Financial Year: {self.financial_year}")
        logger.info(f"  Sync Interval : every {self.sync_interval} min")
        logger.info(f"  Timeout/req   : {REQUEST_TIMEOUT} sec")
        logger.info(f"  Cache Dir     : {self.export_dir}")
        logger.info("=" * 60)

    def report_progress(self, event_type, **kwargs):
        progress = {
            'type': event_type,
            'timestamp': datetime.now().isoformat(),
            'financial_year': self.financial_year,
            'company_name': self.tally.company or '',
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
                'agent_version': '6.0.0-collection',
                'company_name': self.tally.company or '',
                'financial_year': self.financial_year
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
        """Save fetched data to local JSON file for caching."""
        filepath = os.path.join(self.export_dir, f"{data_type}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Cached {len(data)} {data_type} to {filepath}")

    def run_sync_cycle(self):
        if self.sync_running:
            logger.info("Sync already running, skipping...")
            return

        try:
            self.sync_running = True
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"Starting sync cycle at {datetime.now().strftime('%H:%M:%S')}")
            logger.info("=" * 60)

            # Test connection
            if not self.tally.test_connection():
                logger.error("Cannot connect to Tally! Is TallyPrime running?")
                self.report_progress('sync_error', error='Tally not responding')
                return

            self.report_progress('sync_started', mode='collection-v6')
            results = {'inventory': 0, 'sales': 0, 'receipts': 0, 'customers': 0}

            # --- Phase 1: Stock Items (~1-2 sec) ---
            logger.info("--- Phase 1: Stock Items ---")
            self.report_progress('phase_start', phase='inventory')
            items = self.tally.fetch_stock_items()
            if items:
                self.save_cache('inventory', items)
                self.sync_to_backend('inventory', items)
                results['inventory'] = len(items)
            self.report_progress('phase_complete', phase='inventory', count=len(items))
            time.sleep(SLEEP_BETWEEN_REQUESTS)

            # --- Phase 2: Sales Vouchers (monthly, ~2-5 sec each) ---
            logger.info("--- Phase 2: Sales Vouchers ---")
            self.report_progress('phase_start', phase='sales')
            all_sales = []
            for m_start, m_end in months_in_fy(self.financial_year):
                month_sales = self.tally.fetch_sales_month(m_start, m_end)
                all_sales.extend(month_sales)
                time.sleep(SLEEP_BETWEEN_REQUESTS)
            if all_sales:
                self.save_cache('sales', all_sales)
                self.sync_to_backend('sales', all_sales)
                results['sales'] = len(all_sales)
            self.report_progress('phase_complete', phase='sales', count=len(all_sales))

            # --- Phase 3: Receipt/Payment Vouchers (monthly, ~2-5 sec each) ---
            logger.info("--- Phase 3: Receipts/Payments ---")
            self.report_progress('phase_start', phase='receipts')
            all_receipts = []
            for m_start, m_end in months_in_fy(self.financial_year):
                month_receipts = self.tally.fetch_receipts_month(m_start, m_end)
                all_receipts.extend(month_receipts)
                time.sleep(SLEEP_BETWEEN_REQUESTS)
            if all_receipts:
                self.save_cache('receipts', all_receipts)
                self.sync_to_backend('receipts', all_receipts)
                results['receipts'] = len(all_receipts)
            self.report_progress('phase_complete', phase='receipts', count=len(all_receipts))

            # --- Phase 4: Customer Ledgers (~1-2 sec) ---
            logger.info("--- Phase 4: Customer Ledgers ---")
            self.report_progress('phase_start', phase='customers')
            customers = self.tally.fetch_customers()
            if customers:
                # Enrich with sales totals
                cust_sales = {}
                for v in all_sales:
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
                results['customers'] = len(customers)
            self.report_progress('phase_complete', phase='customers', count=len(customers))

            # Summary
            logger.info("")
            logger.info(f"[DONE] Sync completed at {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"  Inventory: {results['inventory']} items")
            logger.info(f"  Sales:     {results['sales']} vouchers")
            logger.info(f"  Receipts:  {results['receipts']} vouchers")
            logger.info(f"  Customers: {results['customers']} ledgers")
            logger.info("=" * 60)

            state = load_sync_state()
            state['last_sync_time'] = datetime.now().isoformat()
            state['last_results'] = results
            state['company'] = self.tally.company
            save_sync_state(state)

            self.report_progress('sync_complete', **results)

        except Exception as e:
            logger.error(f"Sync cycle error: {e}")
            self.report_progress('sync_error', error=str(e))
        finally:
            self.sync_running = False

    def start(self):
        if ENABLE_WS:
            self.ws_server = WebSocketServer(port=WS_PORT)
            self.ws_server.start()

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
