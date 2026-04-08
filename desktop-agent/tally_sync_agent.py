#!/usr/bin/env python3
"""
FLOWRA Tally Sync Agent v5
Lightweight XML exports + Receipt/Payment sync + long timeouts.

Key changes from v4:
- Uses standard Tally report exports (lighter on ODBC than TDL collections)
- HTTP Session with keep-alive (avoids reconnection overhead per request)
- Timeouts increased to 120s (Tally on large databases needs this)
- Added Receipt/Payment voucher sync for accurate outstanding calculation
- Retry logic per request (2 retries with backoff)

Setup:
1. pip install requests xmltodict python-dotenv schedule websockets
2. Create .env with your settings (see QUICK_START.txt)
3. Run: python tally_sync_agent.py
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
import requests
import xmltodict
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
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
logger = logging.getLogger('TallySyncAgent')

load_dotenv()


# ==================== HELPERS ====================

def get_fy_dates(fy_str: str):
    """Convert '2025-26' to ('20250401', '20260331')."""
    parts = fy_str.split('-')
    start_year = int(parts[0])
    end_short = int(parts[1]) if len(parts) > 1 else (start_year + 1) % 100
    end_year = start_year // 100 * 100 + end_short if end_short < 100 else end_short
    return f"{start_year}0401", f"{end_year}0331"


def get_monthly_ranges(fy_from: str, fy_to: str):
    """Break FY into monthly (from_date, to_date, label) tuples in YYYYMMDD."""
    start = date(int(fy_from[:4]), int(fy_from[4:6]), int(fy_from[6:8]))
    end = date(int(fy_to[:4]), int(fy_to[4:6]), int(fy_to[6:8]))
    month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    ranges = []
    current = start
    while current <= end:
        if current.month == 12:
            month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)
        if month_end > end:
            month_end = end
        label = f"{month_names[current.month - 1]} {current.year}"
        ranges.append((current.strftime('%Y%m%d'), month_end.strftime('%Y%m%d'), label))
        current = (month_end + timedelta(days=1))

    return ranges


SYNC_STATE_FILE = 'sync_state.json'


def load_sync_state():
    if os.path.exists(SYNC_STATE_FILE):
        with open(SYNC_STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_sync_state(state):
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


# ==================== WEBSOCKET SERVER ====================

class WebSocketServer:
    def __init__(self, port=8765):
        self.port = port
        self.clients = set()
        self.loop = None
        self.thread = None

    def start(self):
        if not HAS_WEBSOCKETS:
            logger.warning("websockets not installed. pip install websockets")
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
        msg = json.dumps(data)
        dead = set()
        for c in self.clients:
            try:
                await c.send(msg)
            except:
                dead.add(c)
        self.clients -= dead


# ==================== XML REQUEST TEMPLATES ====================
# These use standard Tally report exports (much lighter than TDL collections)

def xml_stock_summary(fy_from, fy_to):
    """Stock Summary report — standard Tally report, very lightweight."""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Stock Summary</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{fy_from}</SVFROMDATE>
<SVTODATE>{fy_to}</SVTODATE>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY>
</ENVELOPE>"""


def xml_stock_items_simple(fy_from, fy_to):
    """Minimal TDL collection — only Name, Parent, ClosingBalance, ClosingValue."""
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>MyStockItems</ID>
</HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{fy_from}</SVFROMDATE>
<SVTODATE>{fy_to}</SVTODATE>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="MyStockItems" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
<TYPE>Stock Item</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>Parent</NATIVEMETHOD>
<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
<NATIVEMETHOD>ClosingValue</NATIVEMETHOD>
<NATIVEMETHOD>ClosingRate</NATIVEMETHOD>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY>
</ENVELOPE>"""


def xml_daybook(from_date, to_date):
    """Day Book report for a date range — standard report, lists all vouchers."""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Day Book</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY>
</ENVELOPE>"""


def xml_bills_receivable(fy_from, fy_to):
    """Bills Receivable (Outstandings) — standard Tally report."""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Bills Receivable</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{fy_from}</SVFROMDATE>
<SVTODATE>{fy_to}</SVTODATE>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY>
</ENVELOPE>"""


def xml_ledger_list():
    """Minimal ledger list — Sundry Debtors/Creditors only."""
    return """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>CustLedgers</ID>
</HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="CustLedgers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
<TYPE>Ledger</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>Parent</NATIVEMETHOD>
<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
<NATIVEMETHOD>LedgerPhone</NATIVEMETHOD>
<NATIVEMETHOD>LedgerContact</NATIVEMETHOD>
<NATIVEMETHOD>LedStateName</NATIVEMETHOD>
<FILTER>CustFilter</FILTER>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="CustFilter">
$Parent = "Sundry Debtors" OR $Parent = "Sundry Creditors"
</SYSTEM>
</TDLMESSAGE></TDL>
</DESC></BODY>
</ENVELOPE>"""


# ==================== MAIN AGENT ====================

class TallySyncAgent:

    def __init__(self):
        self.tally_host = os.getenv('TALLY_HOST', 'localhost')
        self.tally_port = int(os.getenv('TALLY_PORT', '9000'))
        self.tally_url = f"http://{self.tally_host}:{self.tally_port}"
        self.backend_url = os.getenv('BACKEND_URL', 'http://localhost:8001')
        self.api_key = os.getenv('AGENT_API_KEY', '')
        self.sync_interval = int(os.getenv('SYNC_INTERVAL_MINUTES', '10'))
        self.debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        self.financial_year = os.getenv('FINANCIAL_YEAR', '2025-26')
        self.fy_from, self.fy_to = get_fy_dates(self.financial_year)
        self.batch_sleep = int(os.getenv('BATCH_SLEEP_SECONDS', '3'))
        self.enable_ws = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
        self.ws_port = int(os.getenv('WEBSOCKET_PORT', '8765'))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '120'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '2'))
        self.last_sync_time = None
        self.sync_running = False
        self.company_name = None
        self.ws_server = None

        # HTTP session with keep-alive (avoids reconnecting per request)
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'text/xml'})
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=1, pool_maxsize=1, max_retries=0
        )
        self.session.mount('http://', adapter)

        logger.info("=" * 55)
        logger.info("  FLOWRA TALLY SYNC AGENT v5")
        logger.info("  (Lightweight Exports + Receipt/Payment Sync)")
        logger.info("=" * 55)
        logger.info(f"  Tally Server  : {self.tally_url}")
        logger.info(f"  Cloud Backend : {self.backend_url}")
        logger.info(f"  Financial Year: {self.financial_year} ({self.fy_from} - {self.fy_to})")
        logger.info(f"  Timeout       : {self.request_timeout}s per request")
        logger.info(f"  Batch Sleep   : {self.batch_sleep}s between requests")
        logger.info(f"  Retries       : {self.max_retries} per request")
        logger.info(f"  Sync Interval : every {self.sync_interval} min")
        logger.info(f"  WebSocket     : {'enabled' if self.enable_ws else 'disabled'}")
        logger.info(f"  Debug Mode    : {self.debug_mode}")
        logger.info("=" * 55)

    # ---- Progress ----

    def report_progress(self, event_type, **kwargs):
        progress = {
            'type': event_type,
            'timestamp': datetime.now().isoformat(),
            'financial_year': self.financial_year,
            'company_name': self.company_name or '',
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

    # ---- Core HTTP ----

    def _send(self, xml_body, timeout=None):
        """Send XML to Tally with retry logic and keep-alive session."""
        if timeout is None:
            timeout = self.request_timeout

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    self.tally_url,
                    data=xml_body.encode('utf-8'),
                    timeout=timeout
                )
                if resp.status_code != 200:
                    logger.error(f"  Tally HTTP {resp.status_code} (attempt {attempt})")
                    if attempt < self.max_retries:
                        time.sleep(2)
                        continue
                    return None
                raw = resp.content.decode('utf-8', errors='replace').lstrip('\ufeff')
                return raw
            except requests.exceptions.ReadTimeout:
                logger.warning(f"  Tally timeout ({timeout}s) attempt {attempt}/{self.max_retries}")
                if attempt < self.max_retries:
                    logger.info(f"  Retrying in {self.batch_sleep}s...")
                    time.sleep(self.batch_sleep)
                    continue
                logger.error(f"  All {self.max_retries} attempts timed out")
                return None
            except requests.exceptions.ConnectionError:
                logger.error(f"  Cannot connect to Tally (attempt {attempt})")
                if attempt < self.max_retries:
                    time.sleep(2)
                    continue
                return None
            except Exception as e:
                logger.error(f"  Request error: {e}")
                return None
        return None

    def _sanitize(self, xml):
        xml = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', xml)
        xml = re.sub(r'&#[0-9]+;?', ' ', xml)
        xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml)
        return xml

    def _dump(self, name, content):
        if not self.debug_mode:
            return
        os.makedirs('debug_xml', exist_ok=True)
        path = os.path.join('debug_xml', f'{name}.xml')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"  [DEBUG] Saved {path}")

    @staticmethod
    def _num(val):
        if val is None:
            return 0.0
        s = str(val).replace(',', '').strip()
        if not s:
            return 0.0
        try:
            return abs(float(s.split()[0]))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _qty_unit(val):
        if val is None or str(val).strip() == '':
            return 0.0, 'Pcs'
        parts = str(val).strip().split()
        try:
            qty = abs(float(parts[0].replace(',', '')))
        except:
            qty = 0.0
        unit = parts[1] if len(parts) > 1 else 'Pcs'
        return qty, unit

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

    # ---- Connection Test ----

    def test_connection(self):
        try:
            resp = self.session.post(
                self.tally_url,
                data='<ENVELOPE></ENVELOPE>'.encode('utf-8'),
                timeout=10
            )
            if resp.status_code == 200:
                logger.info("[OK] Connected to TallyPrime")
                return True
            return False
        except:
            logger.error("Cannot connect to TallyPrime")
            return False

    # ==================== INVENTORY ====================

    def fetch_inventory(self):
        """Try simple TDL collection first, fallback to Stock Summary report."""
        logger.info("Fetching stock items (simple TDL)...")
        self.report_progress('phase_start', phase='inventory')

        raw = self._send(xml_stock_items_simple(self.fy_from, self.fy_to))
        if raw:
            items = self._parse_stock_items(raw)
            if items:
                logger.info(f"  Parsed {len(items)} stock items via TDL")
                return items

        logger.info("  TDL returned 0 items, trying Stock Summary report...")
        raw = self._send(xml_stock_summary(self.fy_from, self.fy_to))
        if raw:
            items = self._parse_stock_summary(raw)
            if items:
                logger.info(f"  Parsed {len(items)} items via Stock Summary")
                return items

        logger.warning("  No inventory data fetched")
        return []

    def _parse_stock_items(self, raw):
        self._dump('stock_items', raw)
        raw = self._sanitize(raw)
        items = []
        try:
            if raw.count('<ENVELOPE') > 1:
                raw = f"<ROOT>{raw}</ROOT>"
                data = xmltodict.parse(raw)
                envelopes = data.get('ROOT', {}).get('ENVELOPE', [])
                if isinstance(envelopes, dict):
                    envelopes = [envelopes]
            else:
                data = xmltodict.parse(raw)
                envelopes = [data.get('ENVELOPE', {})]

            for envelope in envelopes:
                if not isinstance(envelope, dict):
                    continue
                stock_items = self._find_deep(envelope, 'STOCKITEM')
                if not stock_items:
                    stock_items = self._find_deep(envelope, 'COLLECTION')
                if not stock_items:
                    continue
                if not isinstance(stock_items, list):
                    stock_items = [stock_items]

                for si in stock_items:
                    if not isinstance(si, dict):
                        continue
                    name = si.get('NAME', si.get('@NAME', '')).strip() if si.get('NAME', si.get('@NAME', '')) else ''
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
        except Exception as e:
            logger.error(f"  Error parsing stock items: {e}")
        return items

    def _parse_stock_summary(self, raw):
        self._dump('stock_summary', raw)
        raw = self._sanitize(raw)
        items = []
        try:
            data = xmltodict.parse(raw)
            envelope = data.get('ENVELOPE', {})
            names_raw = envelope.get('DSPACCNAME', [])
            infos_raw = envelope.get('DSPSTKINFO', [])
            if isinstance(names_raw, dict):
                names_raw = [names_raw]
            if isinstance(infos_raw, dict):
                infos_raw = [infos_raw]

            for i, name_el in enumerate(names_raw):
                if not isinstance(name_el, dict):
                    continue
                item_name = str(name_el.get('DSPDISPNAME', '')).strip()
                if not item_name:
                    continue
                stk_info = {}
                if i < len(infos_raw) and isinstance(infos_raw[i], dict):
                    stk_cl = infos_raw[i].get('DSPSTKCL', {})
                    if isinstance(stk_cl, dict):
                        stk_info = stk_cl
                qty, unit = self._qty_unit(stk_info.get('DSPCLQTY'))
                rate = self._num(stk_info.get('DSPCLRATE'))
                amount = self._num(stk_info.get('DSPCLAMTA'))
                if rate == 0 and qty > 0 and amount > 0:
                    rate = round(amount / qty, 2)
                items.append({
                    'item_id': item_name, 'item_name': item_name,
                    'quantity': qty, 'unit': unit, 'price': rate,
                    'category': 'General', 'stock_group': 'General',
                    'reorder_level': 10.0
                })
        except Exception as e:
            logger.error(f"  Error parsing stock summary: {e}")
        return items

    # ==================== SALES + RECEIPTS (MONTHLY BATCHES) ====================

    def fetch_vouchers_batched(self, incremental_from=None):
        """Fetch ALL vouchers (Sales + Receipts + Payments) using Day Book report
        in monthly batches. Returns (sales_vouchers, receipt_vouchers)."""
        monthly_ranges = get_monthly_ranges(self.fy_from, self.fy_to)

        if incremental_from:
            monthly_ranges = [(f, t, l) for f, t, l in monthly_ranges if t >= incremental_from]
            if monthly_ranges:
                f, t, l = monthly_ranges[0]
                if f < incremental_from:
                    monthly_ranges[0] = (incremental_from, t, l)

        total_months = len(monthly_ranges)
        if total_months == 0:
            return [], []

        logger.info(f"Fetching vouchers (Day Book) in {total_months} monthly batches...")
        self.report_progress('sales_batch_start', total_batches=total_months)

        all_sales = []
        all_receipts = []
        failed_months = []

        for idx, (from_date, to_date, label) in enumerate(monthly_ranges):
            batch_num = idx + 1
            logger.info(f"  Batch {batch_num}/{total_months}: {label} ({from_date} - {to_date})")

            self.report_progress(
                'sales_batch_progress',
                batch=batch_num, total_batches=total_months,
                month=label, from_date=from_date, to_date=to_date,
                vouchers_so_far=len(all_sales)
            )

            raw = self._send(xml_daybook(from_date, to_date))
            if not raw:
                logger.warning(f"  Batch {batch_num} failed — skipping {label}")
                failed_months.append(label)
                if batch_num < total_months:
                    time.sleep(self.batch_sleep)
                continue

            self._dump(f'daybook_{from_date}_{to_date}', raw)
            raw = self._sanitize(raw)
            sales, receipts = self._parse_daybook(raw)
            logger.info(f"  Batch {batch_num}: {len(sales)} sales, {len(receipts)} receipts/payments")
            all_sales.extend(sales)
            all_receipts.extend(receipts)

            if batch_num < total_months:
                logger.info(f"  Sleeping {self.batch_sleep}s...")
                time.sleep(self.batch_sleep)

        if failed_months:
            logger.warning(f"Failed months: {', '.join(failed_months)}")

        logger.info(f"TOTAL: {len(all_sales)} sales, {len(all_receipts)} receipts/payments across {total_months} batches")
        self.report_progress(
            'sales_batch_complete',
            total_vouchers=len(all_sales),
            total_receipts=len(all_receipts),
            total_batches=total_months,
            failed_batches=len(failed_months)
        )

        return all_sales, all_receipts

    def _parse_daybook(self, raw):
        """Parse Day Book XML — separates Sales vs Receipt/Payment vouchers."""
        sales = []
        receipts = []
        try:
            data = xmltodict.parse(raw)
            envelope = data.get('ENVELOPE', {})
            body = envelope.get('BODY', {})
            if isinstance(body, dict):
                desc = body.get('DESC', {})
                if isinstance(desc, dict):
                    sv = desc.get('STATICVARIABLES', {})
                    if isinstance(sv, dict) and sv.get('SVCURRENTCOMPANY'):
                        self.company_name = str(sv['SVCURRENTCOMPANY'])

            data_section = body.get('DATA', {}) if isinstance(body, dict) else {}
            tally_msgs = data_section.get('TALLYMESSAGE', []) if isinstance(data_section, dict) else []
            if isinstance(tally_msgs, dict):
                tally_msgs = [tally_msgs]

            for msg in tally_msgs:
                if not isinstance(msg, dict) or 'COMPANY' in msg:
                    continue
                voucher_raw = msg.get('VOUCHER')
                if not voucher_raw:
                    continue
                v_list = voucher_raw if isinstance(voucher_raw, list) else [voucher_raw]
                for v in v_list:
                    if not isinstance(v, dict):
                        continue
                    vtype = str(v.get('VOUCHERTYPENAME', v.get('@VCHTYPE', ''))).strip().lower()

                    if vtype in ('sales', 'sales return', 'credit note'):
                        parsed = self._parse_sale(v)
                        if parsed:
                            sales.append(parsed)
                    elif vtype in ('receipt', 'payment', 'contra', 'journal'):
                        parsed = self._parse_receipt(v, vtype)
                        if parsed:
                            receipts.append(parsed)
        except Exception as e:
            logger.error(f"  Error parsing Day Book: {e}")
        return sales, receipts

    def _parse_sale(self, v):
        v_number = v.get('VOUCHERNUMBER') or v.get('NUMBER') or v.get('@REMOTEID', '')[:20] or f"V-{id(v)}"
        raw_date = v.get('DATE', '')
        formatted_date = self._format_date(raw_date)
        party = v.get('PARTYLEDGERNAME') or v.get('BASICBUYERNAME') or v.get('PARTYNAME') or 'Unknown'

        amount = 0.0
        for f in ['AMOUNT', 'PARTYLEDGERAMOUNT', 'BASICBUYERAMOUNT']:
            val = v.get(f)
            if val is not None:
                amount = self._num(val)
                if amount > 0:
                    break

        if amount == 0:
            le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
            if isinstance(le, dict):
                le = [le]
            if isinstance(le, list):
                for entry in le:
                    if isinstance(entry, dict):
                        a = self._num(entry.get('AMOUNT', 0))
                        if a > amount:
                            amount = a

        line_items = []
        inv = v.get('ALLINVENTORYENTRIES.LIST', v.get('INVENTORYENTRIES.LIST', []))
        if isinstance(inv, dict):
            inv = [inv]
        if isinstance(inv, list):
            for entry in inv:
                if not isinstance(entry, dict):
                    continue
                iname = entry.get('STOCKITEMNAME', entry.get('ITEMNAME', ''))
                if not iname or not str(iname).strip():
                    continue
                aq = entry.get('ACTUALQTY', entry.get('BILLEDQTY', 0))
                rt = entry.get('RATE', entry.get('AMOUNT', 0))
                qty_val = self._num(aq)
                rate_val = self._num(str(rt).split('/')[0]) if rt else 0
                ea = self._num(entry.get('AMOUNT', 0))
                line_items.append({
                    'item': str(iname).strip(),
                    'quantity': qty_val,
                    'rate': rate_val,
                    'amount': ea
                })

        ref = v.get('REFERENCE', v.get('NARRATION', ''))

        # Extract ledger entries for discount/GST breakdown
        ledger_entries = []
        le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
        if isinstance(le, dict):
            le = [le]
        if isinstance(le, list):
            for entry in le:
                if isinstance(entry, dict):
                    lname = str(entry.get('LEDGERNAME', '')).strip()
                    lamt = entry.get('AMOUNT', 0)
                    if lname:
                        ledger_entries.append({
                            'ledger_name': lname,
                            'amount': self._num(lamt) if lamt else 0
                        })

        # Dispatch details from Tally voucher fields
        dispatch_through = str(v.get('BASICSHIPDISPATCHTHROUGH', v.get('DISPATCHTHROUGH', '')) or '').strip()
        destination = str(v.get('BASICFINALDESTINATION', v.get('DESTINATION', '')) or '').strip()
        carrier = str(v.get('BASICSHIPDELIVERYNOTE', '') or '').strip()
        bill_of_lading = str(v.get('BASICSHIPPEDBY', '') or '').strip()
        delivery_note = str(v.get('BASICORDERREF', v.get('DELIVERYNOTE', '')) or '').strip()

        return {
            'voucher_id': str(v_number),
            'voucher_date': formatted_date,
            'party_name': str(party),
            'total_amount': amount,
            'items': line_items,
            'reference_number': str(ref) if ref else '',
            'ledger_entries': ledger_entries,
            'dispatch_through': dispatch_through,
            'destination': destination,
            'carrier_name': carrier,
            'bill_of_lading': bill_of_lading,
            'delivery_note': delivery_note
        }

    def _parse_receipt(self, v, vtype):
        """Parse a receipt/payment/contra/journal voucher."""
        v_number = v.get('VOUCHERNUMBER') or v.get('NUMBER') or f"R-{id(v)}"
        raw_date = v.get('DATE', '')
        formatted_date = self._format_date(raw_date)
        party = v.get('PARTYLEDGERNAME') or v.get('PARTYNAME') or ''

        amount = 0.0
        for f in ['AMOUNT', 'PARTYLEDGERAMOUNT']:
            val = v.get(f)
            if val is not None:
                amount = self._num(val)
                if amount > 0:
                    break

        # For receipts, try ledger entries
        if amount == 0:
            le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
            if isinstance(le, dict):
                le = [le]
            if isinstance(le, list):
                for entry in le:
                    if isinstance(entry, dict):
                        a = self._num(entry.get('AMOUNT', 0))
                        if a > amount:
                            amount = a
                        # Also capture party from ledger entries
                        if not party:
                            party = str(entry.get('LEDGERNAME', '')).strip()

        # Bill allocations (which invoices this receipt applies to)
        bill_refs = []
        le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
        if isinstance(le, dict):
            le = [le]
        if isinstance(le, list):
            for entry in le:
                if not isinstance(entry, dict):
                    continue
                bills = entry.get('BILLALLOCATIONS.LIST', [])
                if isinstance(bills, dict):
                    bills = [bills]
                if isinstance(bills, list):
                    for bill in bills:
                        if isinstance(bill, dict):
                            bill_refs.append({
                                'bill_ref': str(bill.get('NAME', '')),
                                'bill_type': str(bill.get('BILLTYPE', '')),
                                'bill_amount': self._num(bill.get('AMOUNT', 0))
                            })

        narration = v.get('NARRATION', '')

        return {
            'voucher_id': str(v_number),
            'voucher_type': vtype,
            'voucher_date': formatted_date,
            'party_name': str(party) if party else 'Unknown',
            'amount': amount,
            'bill_allocations': bill_refs,
            'narration': str(narration) if narration else ''
        }

    @staticmethod
    def _format_date(raw_date):
        if raw_date and len(str(raw_date)) == 8 and str(raw_date).isdigit():
            d = str(raw_date)
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return str(raw_date)

    # ==================== CUSTOMERS ====================

    def fetch_customers(self):
        logger.info("Fetching customer ledgers...")
        self.report_progress('phase_start', phase='customers')

        raw = self._send(xml_ledger_list())
        if not raw:
            return []
        self._dump('customer_ledgers', raw)
        raw = self._sanitize(raw)
        customers = []

        try:
            if raw.count('<ENVELOPE') > 1:
                raw = f"<ROOT>{raw}</ROOT>"
                data = xmltodict.parse(raw)
                envelopes = data.get('ROOT', {}).get('ENVELOPE', [])
                if isinstance(envelopes, dict):
                    envelopes = [envelopes]
            else:
                data = xmltodict.parse(raw)
                envelopes = [data.get('ENVELOPE', {})]

            for envelope in envelopes:
                if not isinstance(envelope, dict):
                    continue
                ledgers = self._find_deep(envelope, 'LEDGER')
                if not ledgers:
                    continue
                if not isinstance(ledgers, list):
                    ledgers = [ledgers]
                for l in ledgers:
                    if not isinstance(l, dict):
                        continue
                    name = str(l.get('NAME', l.get('@NAME', '')) or '').strip()
                    if not name:
                        continue
                    parent = str(l.get('PARENT', 'Sundry Debtors') or 'Sundry Debtors').strip()
                    bal = self._num(l.get('CLOSINGBALANCE', 0))
                    phone = str(l.get('LEDGERPHONE', '') or '').strip()
                    contact = str(l.get('LEDGERCONTACT', '') or '').strip()
                    state = str(l.get('LEDSTATENAME', '') or '').strip()
                    customers.append({
                        'customer_name': name,
                        'ledger_group': parent,
                        'outstanding_amount': bal,
                        'phone': phone,
                        'contact_person': contact,
                        'state': state,
                        'total_purchases': 0.0,
                        'transaction_count': 0
                    })

            logger.info(f"  Parsed {len(customers)} customer ledgers")
        except Exception as e:
            logger.error(f"  Error parsing customer ledgers: {e}")

        return customers

    def extract_customers_from_sales(self, sales_vouchers):
        seen = {}
        for v in sales_vouchers:
            name = v.get('party_name', '').strip()
            if not name or name == 'Unknown':
                continue
            key = name.lower()
            if key not in seen:
                seen[key] = {
                    'customer_name': name,
                    'ledger_group': 'Sundry Debtors',
                    'outstanding_amount': 0.0,
                    'total_purchases': 0.0,
                    'transaction_count': 0
                }
            seen[key]['total_purchases'] += v.get('total_amount', 0)
            seen[key]['transaction_count'] += 1
        return list(seen.values())

    # ==================== SYNC TO BACKEND ====================

    def sync_to_backend(self, data_type, data):
        if not data:
            logger.info(f"  No {data_type} data to sync, skipping")
            return True
        try:
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.utcnow().isoformat(),
                'agent_version': '5.0.0',
                'company_name': self.company_name or '',
                'financial_year': self.financial_year
            }
            resp = requests.post(
                f"{self.backend_url}/api/agent/sync",
                json=payload,
                headers={'Content-Type': 'application/json', 'X-Agent-Key': self.api_key},
                timeout=30
            )
            if resp.status_code == 200:
                logger.info(f"  [OK] Synced {len(data)} {data_type} to backend")
                return True
            else:
                logger.error(f"  Sync {data_type} failed: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"  Sync error ({data_type}): {e}")
            return False

    # ==================== MAIN SYNC CYCLE ====================

    def run_sync_cycle(self):
        if self.sync_running:
            logger.info("Sync already running, skipping...")
            return
        try:
            self.sync_running = True
            state = load_sync_state()
            is_first_sync = not state.get('full_sync_done')
            last_sales_date = state.get('last_sales_date')

            logger.info("")
            logger.info("=" * 55)
            if is_first_sync:
                logger.info("FIRST RUN — Full batch sync...")
            else:
                logger.info(f"Incremental sync (since {last_sales_date})...")
            logger.info("=" * 55)

            self.report_progress('sync_started', is_first_sync=is_first_sync, last_sales_date=last_sales_date)

            if not self.test_connection():
                self.report_progress('sync_error', error='Cannot connect to TallyPrime')
                return

            # --- Inventory ---
            logger.info("--- Phase 1: Inventory ---")
            inventory = self.fetch_inventory()
            if inventory:
                self.sync_to_backend('inventory', inventory)
                self.report_progress('phase_complete', phase='inventory', count=len(inventory))
            else:
                self.report_progress('phase_warning', phase='inventory', message='No data')

            time.sleep(self.batch_sleep)

            # --- Vouchers (Sales + Receipts) in monthly batches ---
            logger.info("--- Phase 2: Vouchers (Day Book — Sales + Receipts) ---")
            self.report_progress('phase_start', phase='sales')

            incremental_from = None
            if not is_first_sync and last_sales_date:
                incremental_from = last_sales_date.replace('-', '')

            sales, receipts = self.fetch_vouchers_batched(incremental_from=incremental_from)

            if sales:
                self.sync_to_backend('sales', sales)
                self.report_progress('phase_complete', phase='sales', count=len(sales))
                latest_date = max(v.get('voucher_date', '') for v in sales)
                state['last_sales_date'] = latest_date

            if receipts:
                self.sync_to_backend('receipts', receipts)
                self.report_progress('phase_complete', phase='receipts', count=len(receipts))
                logger.info(f"  Synced {len(receipts)} receipt/payment vouchers")

            time.sleep(self.batch_sleep)

            # --- Customers ---
            logger.info("--- Phase 3: Customers ---")
            self.report_progress('phase_start', phase='customers')
            customers = self.fetch_customers()
            if sales:
                sales_customers = self.extract_customers_from_sales(sales)
                cust_map = {c['customer_name'].lower(): c for c in customers}
                for sc in sales_customers:
                    key = sc['customer_name'].lower()
                    if key in cust_map:
                        cust_map[key]['total_purchases'] = sc['total_purchases']
                        cust_map[key]['transaction_count'] = sc['transaction_count']
                    else:
                        customers.append(sc)
            if customers:
                self.sync_to_backend('customers', customers)
                self.report_progress('phase_complete', phase='customers', count=len(customers))

            # Save state
            state['full_sync_done'] = True
            state['last_sync_time'] = datetime.now().isoformat()
            save_sync_state(state)

            self.last_sync_time = datetime.now()
            logger.info("")
            logger.info(f"[OK] Sync completed at {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  Inventory: {len(inventory)} items")
            logger.info(f"  Sales:     {len(sales)} vouchers")
            logger.info(f"  Receipts:  {len(receipts)} vouchers")
            logger.info(f"  Customers: {len(customers)} ledgers")
            logger.info("=" * 55)

            self.report_progress(
                'sync_complete',
                inventory_count=len(inventory),
                sales_count=len(sales),
                receipt_count=len(receipts),
                customer_count=len(customers)
            )

        except Exception as e:
            logger.error(f"Sync cycle error: {e}")
            self.report_progress('sync_error', error=str(e))
        finally:
            self.sync_running = False

    def start(self):
        if self.enable_ws:
            self.ws_server = WebSocketServer(port=self.ws_port)
            self.ws_server.start()

        state = load_sync_state()
        if state.get('full_sync_done'):
            logger.info(f"Previous sync found. Last: {state.get('last_sync_time', 'unknown')}")
        else:
            logger.info("First run — full batch sync")

        logger.info("")
        self.run_sync_cycle()
        schedule.every(self.sync_interval).minutes.do(self.run_sync_cycle)
        logger.info(f"Scheduled: every {self.sync_interval} min. Ctrl+C to stop.")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            sys.exit(0)


if __name__ == "__main__":
    agent = TallySyncAgent()
    agent.start()
