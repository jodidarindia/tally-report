#!/usr/bin/env python3
"""
Tally Desktop Sync Agent v3
Fetches stock items with groups, customers with groups, and FY-based sales.

Setup:
1. pip install requests xmltodict python-dotenv schedule
2. Create .env:
   BACKEND_URL=http://localhost:8001
   FINANCIAL_YEAR=2025-26
   TALLY_HOST=localhost
   TALLY_PORT=9000
   SYNC_INTERVAL_MINUTES=10
   DEBUG_MODE=true
3. Run: python tally_sync_agent.py
"""

import os
import sys
import io
import re
import time
import json
import logging
import requests
import xmltodict
from datetime import datetime
from typing import Dict, List, Any, Optional
import schedule
from dotenv import load_dotenv

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


def get_fy_dates(fy_str: str):
    """Convert '2025-26' to ('20250401', '20260331')."""
    parts = fy_str.split('-')
    start_year = int(parts[0])
    end_year_short = int(parts[1]) if len(parts) > 1 else (start_year + 1) % 100
    end_year = start_year // 100 * 100 + end_year_short if end_year_short < 100 else end_year_short
    return f"{start_year}0401", f"{end_year}0331"


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
        self.last_sync_time = None
        self.sync_running = False
        self.company_name = None

        logger.info("Tally Sync Agent v3 initialized")
        logger.info(f"  Tally: {self.tally_url}")
        logger.info(f"  Backend: {self.backend_url}")
        logger.info(f"  FY: {self.financial_year} ({self.fy_from} - {self.fy_to})")
        logger.info(f"  Sync every {self.sync_interval} min | Debug: {self.debug_mode}")

    # ---- XML request builders ----

    def _stock_items_xml(self):
        """TDL request to fetch ALL stock items as objects with group info."""
        return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>StockItemsList</ID>
</HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{self.fy_from}</SVFROMDATE>
<SVTODATE>{self.fy_to}</SVTODATE>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="StockItemsList" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
<TYPE>Stock Item</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>Parent</NATIVEMETHOD>
<NATIVEMETHOD>BaseUnits</NATIVEMETHOD>
<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
<NATIVEMETHOD>ClosingRate</NATIVEMETHOD>
<NATIVEMETHOD>ClosingValue</NATIVEMETHOD>
<NATIVEMETHOD>OpeningBalance</NATIVEMETHOD>
<NATIVEMETHOD>OpeningValue</NATIVEMETHOD>
<NATIVEMETHOD>Category</NATIVEMETHOD>
</COLLECTION>
</TDLMESSAGE></TDL>
</DESC></BODY>
</ENVELOPE>"""

    def _stock_summary_xml(self):
        """Fallback: Stock Summary report (display format)."""
        return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Stock Summary</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{self.fy_from}</SVFROMDATE>
<SVTODATE>{self.fy_to}</SVTODATE>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY>
</ENVELOPE>"""

    def _sales_vouchers_xml(self):
        """Structured VOUCHER export for given FY."""
        return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>Sales Vouchers</ID>
</HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<EXPLODEFLAG>Yes</EXPLODEFLAG>
<SVFROMDATE>{self.fy_from}</SVFROMDATE>
<SVTODATE>{self.fy_to}</SVTODATE>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="SalesCollection" ISMODIFY="No">
<TYPE>Voucher</TYPE>
<FETCH>VoucherNumber, Date, PartyLedgerName, Amount, VoucherTypeName</FETCH>
<FILTER>VoucherTypeFilter</FILTER>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="VoucherTypeFilter">
$$IsSales:$VoucherTypeName
</SYSTEM>
</TDLMESSAGE></TDL>
</DESC></BODY>
</ENVELOPE>"""

    def _ledger_list_xml(self):
        """Fetch all ledgers as objects with parent group."""
        return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>CustomerLedgers</ID>
</HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{self.fy_from}</SVFROMDATE>
<SVTODATE>{self.fy_to}</SVTODATE>
</STATICVARIABLES>
<TDL><TDLMESSAGE>
<COLLECTION NAME="CustomerLedgers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
<TYPE>Ledger</TYPE>
<NATIVEMETHOD>Name</NATIVEMETHOD>
<NATIVEMETHOD>Parent</NATIVEMETHOD>
<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
<NATIVEMETHOD>Address</NATIVEMETHOD>
<NATIVEMETHOD>LedStateName</NATIVEMETHOD>
<NATIVEMETHOD>LedgerPhone</NATIVEMETHOD>
<NATIVEMETHOD>LedgerContact</NATIVEMETHOD>
<FILTER>CustomerGroupFilter</FILTER>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="CustomerGroupFilter">
$$IsSundryDebtor:$Parent OR $$IsSundryCreditor:$Parent OR $Parent = "Sundry Debtors" OR $Parent = "Sundry Creditors"
</SYSTEM>
</TDLMESSAGE></TDL>
</DESC></BODY>
</ENVELOPE>"""

    # ---- HTTP + XML helpers ----

    def _send(self, xml_body, timeout=120):
        try:
            resp = requests.post(
                self.tally_url,
                data=xml_body.encode('utf-8'),
                headers={'Content-Type': 'text/xml'},
                timeout=timeout
            )
            if resp.status_code != 200:
                logger.error(f"Tally HTTP {resp.status_code}")
                return None
            raw = resp.content.decode('utf-8', errors='replace').lstrip('\ufeff')
            return raw
        except requests.exceptions.ReadTimeout:
            logger.error(f"Tally timed out ({timeout}s)")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Tally")
            return None
        except Exception as e:
            logger.error(f"Request error: {e}")
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
        except (ValueError, TypeError):
            qty = 0.0
        unit = parts[1] if len(parts) > 1 else 'Pcs'
        return qty, unit

    def _find_deep(self, d, key):
        """Recursively find a key in nested dict/list."""
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

    # ---- Connection test ----

    def test_connection(self):
        try:
            resp = requests.post(
                self.tally_url,
                data='<ENVELOPE></ENVELOPE>'.encode('utf-8'),
                headers={'Content-Type': 'text/xml'},
                timeout=5
            )
            if resp.status_code == 200:
                logger.info("[OK] Connected to TallyPrime")
                return True
            return False
        except:
            logger.error("Cannot connect to TallyPrime")
            return False

    # ---- INVENTORY ----

    def fetch_inventory(self):
        """Try TDL object export first, fallback to Stock Summary display format."""
        items = self._fetch_inventory_tdl()
        if items:
            return items
        logger.info("TDL stock export returned 0 items, trying Stock Summary...")
        return self._fetch_inventory_summary()

    def _fetch_inventory_tdl(self):
        """Fetch stock items as TDL collection objects."""
        logger.info("Fetching stock items via TDL collection...")
        raw = self._send(self._stock_items_xml(), timeout=120)
        if not raw:
            return []
        self._dump('stock_items_tdl', raw)
        raw = self._sanitize(raw)
        logger.info(f"Stock items TDL response: {len(raw)} chars")

        items = []
        try:
            # Handle multi-envelope response (wrap in root)
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

                # Try: BODY > DATA > TALLYMESSAGE > STOCKITEM
                stock_items = None
                body = envelope.get('BODY', {})
                if isinstance(body, dict):
                    ds = body.get('DATA', {})
                    if isinstance(ds, dict):
                        tm = ds.get('TALLYMESSAGE', {})
                        if isinstance(tm, dict):
                            stock_items = tm.get('STOCKITEM')
                        elif isinstance(tm, list):
                            for msg in tm:
                                if isinstance(msg, dict) and 'STOCKITEM' in msg:
                                    si = msg['STOCKITEM']
                                    if stock_items is None:
                                        stock_items = si if isinstance(si, list) else [si]
                                    else:
                                        if isinstance(si, list):
                                            stock_items.extend(si)
                                        else:
                                            stock_items.append(si)

                # Fallback: deep search
                if not stock_items:
                    stock_items = self._find_deep(envelope, 'STOCKITEM')

                # Also try COLLECTION format
                if not stock_items:
                    stock_items = self._find_deep(envelope, 'COLLECTION')

                if not stock_items:
                    continue

                if not isinstance(stock_items, list):
                    stock_items = [stock_items]

                for si in stock_items:
                    if not isinstance(si, dict):
                        continue
                    name = si.get('NAME', si.get('@NAME', si.get('STOCKITEMNAME', '')))
                    if not name or not str(name).strip():
                        continue
                    name = str(name).strip()
                    parent = str(si.get('PARENT', si.get('STOCKGROUP', 'General')) or 'General').strip()
                    category = str(si.get('CATEGORY', parent) or parent).strip()

                    cb = si.get('CLOSINGBALANCE', si.get('BASEUNITS', 0))
                    qty, unit = self._qty_unit(cb)
                    cr = si.get('CLOSINGRATE', si.get('RATE', 0))
                    rate_str = str(cr) if cr else '0'
                    rate = self._num(rate_str.split('/')[0])
                    cv = self._num(si.get('CLOSINGVALUE', 0))
                    if rate == 0 and qty > 0 and cv > 0:
                        rate = round(cv / qty, 2)

                    items.append({
                        'item_id': name,
                        'item_name': name,
                        'quantity': qty,
                        'unit': unit,
                        'price': rate,
                        'category': category,
                        'stock_group': parent,
                        'reorder_level': 10.0
                    })

            logger.info(f"TDL: Parsed {len(items)} stock items")
        except Exception as e:
            logger.error(f"Error parsing TDL stock items: {e}")

        return items

    def _fetch_inventory_summary(self):
        """Fallback: parse Stock Summary display format."""
        logger.info("Fetching Stock Summary report...")
        raw = self._send(self._stock_summary_xml(), timeout=120)
        if not raw:
            return []
        self._dump('stock_summary', raw)
        raw = self._sanitize(raw)
        items = []

        try:
            data = xmltodict.parse(raw)
            envelope = data.get('ENVELOPE', {})
            if not isinstance(envelope, dict):
                return []

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
                    'item_id': item_name,
                    'item_name': item_name,
                    'quantity': qty,
                    'unit': unit,
                    'price': rate,
                    'category': 'General',
                    'stock_group': 'General',
                    'reorder_level': 10.0
                })

            logger.info(f"Summary: Parsed {len(items)} items")
        except Exception as e:
            logger.error(f"Error parsing Stock Summary: {e}")

        return items

    # ---- SALES ----

    def fetch_sales(self):
        logger.info("Fetching Sales Vouchers...")
        raw = self._send(self._sales_vouchers_xml(), timeout=180)
        if not raw:
            return []
        self._dump('sales_vouchers', raw)
        raw = self._sanitize(raw)
        logger.info(f"Sales response: {len(raw)} chars")
        vouchers = []

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
                        logger.info(f"Company: {self.company_name}")

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
                    parsed = self._parse_voucher(v)
                    if parsed:
                        vouchers.append(parsed)

            logger.info(f"Parsed {len(vouchers)} sales vouchers")
        except Exception as e:
            logger.error(f"Error parsing sales: {e}")

        return vouchers

    def _parse_voucher(self, v):
        if not isinstance(v, dict):
            return None

        v_number = v.get('VOUCHERNUMBER') or v.get('NUMBER') or v.get('@REMOTEID', '')[:20] or f"V-{id(v)}"
        raw_date = v.get('DATE', '')
        if raw_date and len(str(raw_date)) == 8 and str(raw_date).isdigit():
            d = str(raw_date)
            formatted_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        else:
            formatted_date = str(raw_date)

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
                rate_str = str(rt) if rt else '0'
                rate_val = self._num(rate_str.split('/')[0])
                ea = self._num(entry.get('AMOUNT', 0))
                line_items.append({
                    'item': str(iname).strip(),
                    'quantity': qty_val,
                    'rate': rate_val,
                    'amount': ea
                })

        ref = v.get('REFERENCE', v.get('NARRATION', ''))

        return {
            'voucher_id': str(v_number),
            'voucher_date': formatted_date,
            'party_name': str(party),
            'total_amount': amount,
            'items': line_items,
            'reference_number': str(ref) if ref else ''
        }

    # ---- CUSTOMERS ----

    def fetch_customers(self):
        """Fetch customer ledgers with groups via TDL, fallback to extracting from sales."""
        customers = self._fetch_ledgers_tdl()
        if customers:
            return customers
        logger.info("TDL ledger fetch returned 0, extracting customers from sales...")
        return []

    def _fetch_ledgers_tdl(self):
        logger.info("Fetching customer ledgers via TDL...")
        raw = self._send(self._ledger_list_xml(), timeout=120)
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

            logger.info(f"TDL: Parsed {len(customers)} customer ledgers")
        except Exception as e:
            logger.error(f"Error parsing customer ledgers: {e}")

        return customers

    def extract_customers_from_sales(self, vouchers):
        seen = {}
        for v in vouchers:
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

    # ---- SYNC ----

    def sync_to_backend(self, data_type, data):
        if not data:
            logger.info(f"No {data_type} data to sync, skipping")
            return True
        try:
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.utcnow().isoformat(),
                'agent_version': '3.0.0',
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
                logger.info(f"[OK] Synced {len(data)} {data_type} to backend")
                return True
            else:
                logger.error(f"Sync {data_type} failed: HTTP {resp.status_code} - {resp.text[:300]}")
                return False
        except Exception as e:
            logger.error(f"Sync error ({data_type}): {e}")
            return False

    def run_sync_cycle(self):
        if self.sync_running:
            return
        try:
            self.sync_running = True
            logger.info("=" * 50)
            logger.info(f"Starting sync cycle (FY: {self.financial_year})...")

            if not self.test_connection():
                return

            # Inventory
            logger.info("--- Inventory ---")
            inventory = self.fetch_inventory()
            if inventory:
                self.sync_to_backend('inventory', inventory)
            else:
                logger.warning("No inventory data fetched")

            # Sales
            logger.info("--- Sales ---")
            sales = self.fetch_sales()
            if sales:
                self.sync_to_backend('sales', sales)
            else:
                logger.warning("No sales data fetched")

            # Customers (TDL + sales extract merge)
            logger.info("--- Customers ---")
            customers = self.fetch_customers()
            if sales:
                sales_customers = self.extract_customers_from_sales(sales)
                # Merge: add sales data to TDL customers, add missing ones
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

            self.last_sync_time = datetime.now()
            logger.info(f"[OK] Sync completed at {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 50)
        except Exception as e:
            logger.error(f"Sync cycle error: {e}")
        finally:
            self.sync_running = False

    def start(self):
        logger.info("")
        logger.info("=" * 50)
        logger.info("  TALLY DESKTOP SYNC AGENT v3")
        logger.info(f"  Financial Year: {self.financial_year}")
        logger.info("=" * 50)

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
