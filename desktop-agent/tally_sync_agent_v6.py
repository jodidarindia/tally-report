#!/usr/bin/env python3
"""
FLOWRA Tally Sync Agent v6 — File-Based (Zero Freeze)

Instead of making HTTP requests to Tally (which freezes the UI),
this agent reads JSON/XML files exported by Tally's TDL auto-export.

How it works:
  1. Tally loads flowra_export.tdl which exports data to C:\FlowraExport\
  2. This agent watches that folder for new/updated files
  3. Parses the exported XML and syncs to the FLOWRA cloud backend
  4. Reports progress via WebSocket to the frontend dashboard

Zero HTTP requests to Tally = Zero freezing.

Setup:
  1. Load flowra_export.tdl in TallyPrime (see TDL file header for instructions)
  2. In Tally: press 'F' on Gateway to run "FLOWRA Auto Export" (or schedule it)
  3. pip install requests xmltodict python-dotenv schedule watchdog websockets
  4. Create .env (see .env.example)
  5. python tally_sync_agent_v6.py
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
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import xmltodict
import schedule
from dotenv import load_dotenv

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

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

EXPORT_DIR = os.getenv('TALLY_EXPORT_DIR', r'C:\FlowraExport')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8001')
API_KEY = os.getenv('AGENT_API_KEY', '')
FINANCIAL_YEAR = os.getenv('FINANCIAL_YEAR', '2025-26')
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL_MINUTES', '5'))
ENABLE_WS = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
WS_PORT = int(os.getenv('WEBSOCKET_PORT', '8765'))
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

# File names that TDL exports (must match flowra_export.tdl Output paths)
EXPORT_FILES = {
    'inventory': 'stock_items.xml',
    'sales': 'sales_vouchers.xml',
    'receipts': 'receipt_vouchers.xml',
    'customers': 'customers.xml',
}

COMPLETION_MARKER = '_export_complete.txt'

SYNC_STATE_FILE = 'sync_state_v6.json'


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
        msg = json.dumps(data)
        dead = set()
        for c in self.clients:
            try:
                await c.send(msg)
            except:
                dead.add(c)
        self.clients -= dead


# ==================== XML PARSERS ====================

def _num(val):
    """Parse Tally numeric value to float."""
    if val is None:
        return 0.0
    s = str(val).replace(',', '').strip()
    if not s:
        return 0.0
    try:
        return abs(float(s.split()[0]))
    except (ValueError, TypeError):
        return 0.0


def _qty_unit(val):
    """Parse Tally quantity with unit (e.g. '100 Nos')."""
    if val is None or str(val).strip() == '':
        return 0.0, 'Pcs'
    parts = str(val).strip().split()
    try:
        qty = abs(float(parts[0].replace(',', '')))
    except:
        qty = 0.0
    unit = parts[1] if len(parts) > 1 else 'Pcs'
    return qty, unit


def _sanitize(xml):
    """Remove invalid XML characters."""
    xml = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', xml)
    xml = re.sub(r'&#[0-9]+;?', ' ', xml)
    xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml)
    return xml


def _format_date(raw_date):
    """Convert YYYYMMDD to YYYY-MM-DD."""
    if raw_date and len(str(raw_date)) == 8 and str(raw_date).isdigit():
        d = str(raw_date)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return str(raw_date)


def _find_deep(d, key):
    """Recursively find a key in nested dict/list."""
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            r = _find_deep(v, key)
            if r is not None:
                return r
    elif isinstance(d, list):
        for item in d:
            r = _find_deep(item, key)
            if r is not None:
                return r
    return None


def parse_stock_items_xml(filepath: str) -> List[Dict]:
    """Parse exported stock_items.xml from TDL."""
    logger.info(f"  Parsing {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read().lstrip('\ufeff')
    except Exception as e:
        logger.error(f"  Cannot read {filepath}: {e}")
        return []

    raw = _sanitize(raw)
    items = []
    try:
        # Handle multiple envelopes
        if raw.count('<ENVELOPE') > 1:
            raw = f"<ROOT>{raw}</ROOT>"
            data = xmltodict.parse(raw)
            envelopes = data.get('ROOT', {}).get('ENVELOPE', [])
            if isinstance(envelopes, dict):
                envelopes = [envelopes]
        else:
            data = xmltodict.parse(raw)
            envelopes = [data.get('ENVELOPE', data)]

        for envelope in envelopes:
            if not isinstance(envelope, dict):
                continue
            # Try multiple keys the TDL might use
            stock_items = _find_deep(envelope, 'STOCKITEM')
            if not stock_items:
                stock_items = _find_deep(envelope, 'COLLECTION')
            if not stock_items:
                # Try parsing as flat list of items
                stock_items = envelope.get('BODY', {}).get('DATA', {}).get('COLLECTION', [])
            if not stock_items:
                continue
            if not isinstance(stock_items, list):
                stock_items = [stock_items]

            for si in stock_items:
                if not isinstance(si, dict):
                    continue
                name = str(si.get('NAME', si.get('@NAME', '')) or '').strip()
                if not name:
                    continue
                parent = str(si.get('PARENT', 'General') or 'General').strip()
                cb = si.get('CLOSINGBALANCE', 0)
                qty, unit = _qty_unit(cb)
                cr = si.get('CLOSINGRATE', 0)
                rate = _num(str(cr).split('/')[0]) if cr else 0
                cv = _num(si.get('CLOSINGVALUE', 0))
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


def parse_sales_xml(filepath: str) -> List[Dict]:
    """Parse exported sales_vouchers.xml from TDL."""
    logger.info(f"  Parsing {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read().lstrip('\ufeff')
    except Exception as e:
        logger.error(f"  Cannot read {filepath}: {e}")
        return []

    raw = _sanitize(raw)
    sales = []
    try:
        data = xmltodict.parse(raw)
        # Navigate to voucher list
        vouchers = _find_deep(data, 'VOUCHER')
        if not vouchers:
            vouchers = _find_deep(data, 'TALLYMESSAGE')
            if isinstance(vouchers, list):
                v_list = []
                for msg in vouchers:
                    if isinstance(msg, dict) and 'VOUCHER' in msg:
                        v = msg['VOUCHER']
                        if isinstance(v, list):
                            v_list.extend(v)
                        else:
                            v_list.append(v)
                vouchers = v_list

        if not vouchers:
            return []
        if not isinstance(vouchers, list):
            vouchers = [vouchers]

        for v in vouchers:
            if not isinstance(v, dict):
                continue
            v_number = v.get('VOUCHERNUMBER') or v.get('NUMBER') or f"V-{id(v)}"
            raw_date = v.get('DATE', '')
            formatted_date = _format_date(raw_date)
            party = v.get('PARTYLEDGERNAME') or v.get('PARTYNAME') or 'Unknown'

            # Amount
            amount = 0.0
            for field in ['AMOUNT', 'PARTYLEDGERAMOUNT']:
                val = v.get(field)
                if val is not None:
                    amount = _num(val)
                    if amount > 0:
                        break

            if amount == 0:
                le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
                if isinstance(le, dict):
                    le = [le]
                if isinstance(le, list):
                    for entry in le:
                        if isinstance(entry, dict):
                            a = _num(entry.get('AMOUNT', 0))
                            if a > amount:
                                amount = a

            # Line items
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
                    qty_val = _num(aq)
                    rate_val = _num(str(rt).split('/')[0]) if rt else 0
                    ea = _num(entry.get('AMOUNT', 0))
                    line_items.append({
                        'item': str(iname).strip(),
                        'quantity': qty_val,
                        'rate': rate_val,
                        'amount': ea
                    })

            # Ledger entries (discount/GST)
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
                                'amount': _num(lamt) if lamt else 0
                            })

            # Dispatch details
            dispatch_through = str(v.get('BASICSHIPDISPATCHTHROUGH', v.get('DISPATCHTHROUGH', '')) or '').strip()
            destination = str(v.get('BASICFINALDESTINATION', v.get('DESTINATION', '')) or '').strip()
            carrier = str(v.get('BASICSHIPDELIVERYNOTE', '') or '').strip()
            bill_of_lading = str(v.get('BASICSHIPPEDBY', '') or '').strip()
            delivery_note = str(v.get('BASICORDERREF', v.get('DELIVERYNOTE', '')) or '').strip()

            ref = v.get('REFERENCE', v.get('NARRATION', ''))

            sales.append({
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
            })
    except Exception as e:
        logger.error(f"  Error parsing sales: {e}")
    return sales


def parse_receipts_xml(filepath: str) -> List[Dict]:
    """Parse exported receipt_vouchers.xml from TDL."""
    logger.info(f"  Parsing {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read().lstrip('\ufeff')
    except Exception as e:
        logger.error(f"  Cannot read {filepath}: {e}")
        return []

    raw = _sanitize(raw)
    receipts = []
    try:
        data = xmltodict.parse(raw)
        vouchers = _find_deep(data, 'VOUCHER')
        if not vouchers:
            vouchers = _find_deep(data, 'TALLYMESSAGE')
            if isinstance(vouchers, list):
                v_list = []
                for msg in vouchers:
                    if isinstance(msg, dict) and 'VOUCHER' in msg:
                        vv = msg['VOUCHER']
                        if isinstance(vv, list):
                            v_list.extend(vv)
                        else:
                            v_list.append(vv)
                vouchers = v_list

        if not vouchers:
            return []
        if not isinstance(vouchers, list):
            vouchers = [vouchers]

        for v in vouchers:
            if not isinstance(v, dict):
                continue
            v_number = v.get('VOUCHERNUMBER') or v.get('NUMBER') or f"R-{id(v)}"
            raw_date = v.get('DATE', '')
            formatted_date = _format_date(raw_date)
            vtype = str(v.get('VOUCHERTYPENAME', '') or '').lower()
            party = v.get('PARTYLEDGERNAME') or v.get('PARTYNAME') or ''

            amount = 0.0
            for field in ['AMOUNT', 'PARTYLEDGERAMOUNT']:
                val = v.get(field)
                if val is not None:
                    amount = _num(val)
                    if amount > 0:
                        break

            if amount == 0:
                le = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
                if isinstance(le, dict):
                    le = [le]
                if isinstance(le, list):
                    for entry in le:
                        if isinstance(entry, dict):
                            a = _num(entry.get('AMOUNT', 0))
                            if a > amount:
                                amount = a
                            if not party:
                                party = str(entry.get('LEDGERNAME', '')).strip()

            # Bill allocations
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
                                    'bill_amount': _num(bill.get('AMOUNT', 0))
                                })

            narration = v.get('NARRATION', '')
            receipts.append({
                'voucher_id': str(v_number),
                'voucher_type': vtype or 'receipt',
                'voucher_date': formatted_date,
                'party_name': str(party) if party else 'Unknown',
                'amount': amount,
                'bill_allocations': bill_refs,
                'narration': str(narration) if narration else ''
            })
    except Exception as e:
        logger.error(f"  Error parsing receipts: {e}")
    return receipts


def parse_customers_xml(filepath: str) -> List[Dict]:
    """Parse exported customers.xml from TDL."""
    logger.info(f"  Parsing {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read().lstrip('\ufeff')
    except Exception as e:
        logger.error(f"  Cannot read {filepath}: {e}")
        return []

    raw = _sanitize(raw)
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
            envelopes = [data.get('ENVELOPE', data)]

        for envelope in envelopes:
            if not isinstance(envelope, dict):
                continue
            ledgers = _find_deep(envelope, 'LEDGER')
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
                bal = _num(l.get('CLOSINGBALANCE', 0))
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
    except Exception as e:
        logger.error(f"  Error parsing customers: {e}")
    return customers


# ==================== FILE WATCHER ====================

class ExportWatcher(FileSystemEventHandler):
    """Watches C:\FlowraExport for new/modified files and triggers sync."""

    def __init__(self, agent):
        self.agent = agent

    def on_modified(self, event):
        if event.is_directory:
            return
        filename = os.path.basename(event.src_path)
        if filename == COMPLETION_MARKER:
            logger.info("Export completion marker detected — triggering sync")
            self.agent.run_sync_cycle()


# ==================== MAIN AGENT ====================

class FlowraSyncAgent:
    def __init__(self):
        self.export_dir = EXPORT_DIR
        self.backend_url = BACKEND_URL
        self.api_key = API_KEY
        self.financial_year = FINANCIAL_YEAR
        self.sync_interval = SYNC_INTERVAL
        self.company_name = None
        self.sync_running = False
        self.ws_server = None
        self.observer = None
        self.file_timestamps = {}

        logger.info("=" * 60)
        logger.info("  FLOWRA TALLY SYNC AGENT v6 — FILE-BASED (ZERO FREEZE)")
        logger.info("=" * 60)
        logger.info(f"  Export Dir    : {self.export_dir}")
        logger.info(f"  Cloud Backend : {self.backend_url}")
        logger.info(f"  Financial Year: {self.financial_year}")
        logger.info(f"  Sync Interval : every {self.sync_interval} min (+ file watch)")
        logger.info(f"  File Watch    : {'enabled' if HAS_WATCHDOG else 'disabled (pip install watchdog)'}")
        logger.info(f"  WebSocket     : {'enabled' if ENABLE_WS else 'disabled'}")
        logger.info("=" * 60)

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

    def sync_to_backend(self, data_type, data):
        if not data:
            logger.info(f"  No {data_type} data to sync, skipping")
            return True
        try:
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.utcnow().isoformat(),
                'agent_version': '6.0.0-filebased',
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

    def _has_new_data(self, filepath: str) -> bool:
        """Check if file has been modified since last read."""
        if not os.path.exists(filepath):
            return False
        mtime = os.path.getmtime(filepath)
        last_mtime = self.file_timestamps.get(filepath, 0)
        return mtime > last_mtime

    def _mark_read(self, filepath: str):
        """Mark file as read."""
        if os.path.exists(filepath):
            self.file_timestamps[filepath] = os.path.getmtime(filepath)

    def run_sync_cycle(self):
        """Read exported files and sync any new data to backend."""
        if self.sync_running:
            logger.info("Sync already running, skipping...")
            return

        try:
            self.sync_running = True
            export_dir = Path(self.export_dir)

            if not export_dir.exists():
                logger.warning(f"Export directory not found: {self.export_dir}")
                logger.info("Waiting for Tally to export data...")
                logger.info(f"  Make sure flowra_export.tdl is loaded in TallyPrime")
                logger.info(f"  Then press 'F' on Gateway to run FLOWRA Auto Export")
                return

            logger.info("")
            logger.info("=" * 60)
            logger.info("Reading exported Tally data files...")
            logger.info("=" * 60)
            self.report_progress('sync_started', mode='file-based')

            results = {
                'inventory': 0, 'sales': 0, 'receipts': 0, 'customers': 0
            }

            # --- Inventory ---
            inv_path = str(export_dir / EXPORT_FILES['inventory'])
            if self._has_new_data(inv_path):
                logger.info("--- Phase 1: Inventory ---")
                self.report_progress('phase_start', phase='inventory')
                items = parse_stock_items_xml(inv_path)
                if items:
                    self.sync_to_backend('inventory', items)
                    results['inventory'] = len(items)
                    self.report_progress('phase_complete', phase='inventory', count=len(items))
                self._mark_read(inv_path)
            else:
                logger.info("  Inventory: no new data")

            # --- Sales ---
            sales_path = str(export_dir / EXPORT_FILES['sales'])
            if self._has_new_data(sales_path):
                logger.info("--- Phase 2: Sales ---")
                self.report_progress('phase_start', phase='sales')
                sales = parse_sales_xml(sales_path)
                if sales:
                    self.sync_to_backend('sales', sales)
                    results['sales'] = len(sales)
                    self.report_progress('phase_complete', phase='sales', count=len(sales))
                self._mark_read(sales_path)
            else:
                logger.info("  Sales: no new data")

            # --- Receipts ---
            receipts_path = str(export_dir / EXPORT_FILES['receipts'])
            if self._has_new_data(receipts_path):
                logger.info("--- Phase 3: Receipts ---")
                self.report_progress('phase_start', phase='receipts')
                receipts = parse_receipts_xml(receipts_path)
                if receipts:
                    self.sync_to_backend('receipts', receipts)
                    results['receipts'] = len(receipts)
                    self.report_progress('phase_complete', phase='receipts', count=len(receipts))
                self._mark_read(receipts_path)
            else:
                logger.info("  Receipts: no new data")

            # --- Customers ---
            cust_path = str(export_dir / EXPORT_FILES['customers'])
            if self._has_new_data(cust_path):
                logger.info("--- Phase 4: Customers ---")
                self.report_progress('phase_start', phase='customers')
                customers = parse_customers_xml(cust_path)
                if customers:
                    # Enrich with sales data if available
                    if results['sales'] > 0:
                        sales = parse_sales_xml(sales_path)
                        seen = {}
                        for v in sales:
                            name = v.get('party_name', '').strip()
                            if not name or name == 'Unknown':
                                continue
                            key = name.lower()
                            if key not in seen:
                                seen[key] = {'total': 0.0, 'count': 0}
                            seen[key]['total'] += v.get('total_amount', 0)
                            seen[key]['count'] += 1
                        for c in customers:
                            key = c['customer_name'].lower()
                            if key in seen:
                                c['total_purchases'] = seen[key]['total']
                                c['transaction_count'] = seen[key]['count']

                    self.sync_to_backend('customers', customers)
                    results['customers'] = len(customers)
                    self.report_progress('phase_complete', phase='customers', count=len(customers))
                self._mark_read(cust_path)
            else:
                logger.info("  Customers: no new data")

            # Summary
            total = sum(results.values())
            if total > 0:
                state = load_sync_state()
                state['last_sync_time'] = datetime.now().isoformat()
                state['last_results'] = results
                save_sync_state(state)

                logger.info("")
                logger.info(f"[OK] Sync completed at {datetime.now().strftime('%H:%M:%S')}")
                logger.info(f"  Inventory: {results['inventory']} items")
                logger.info(f"  Sales:     {results['sales']} vouchers")
                logger.info(f"  Receipts:  {results['receipts']} vouchers")
                logger.info(f"  Customers: {results['customers']} ledgers")
                self.report_progress('sync_complete', **results)
            else:
                logger.info("  No new data to sync (files unchanged)")

            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Sync cycle error: {e}")
            self.report_progress('sync_error', error=str(e))
        finally:
            self.sync_running = False

    def start(self):
        # Start WebSocket
        if ENABLE_WS:
            self.ws_server = WebSocketServer(port=WS_PORT)
            self.ws_server.start()

        # Start file watcher
        if HAS_WATCHDOG and os.path.exists(self.export_dir):
            self.observer = Observer()
            handler = ExportWatcher(self)
            self.observer.schedule(handler, self.export_dir, recursive=False)
            self.observer.start()
            logger.info(f"File watcher started on {self.export_dir}")

        # Initial sync
        logger.info("")
        self.run_sync_cycle()

        # Schedule periodic checks
        schedule.every(self.sync_interval).minutes.do(self.run_sync_cycle)
        logger.info(f"Scheduled: every {self.sync_interval} min. Ctrl+C to stop.")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            if self.observer:
                self.observer.stop()
                self.observer.join()
            sys.exit(0)


if __name__ == "__main__":
    agent = FlowraSyncAgent()
    agent.start()
