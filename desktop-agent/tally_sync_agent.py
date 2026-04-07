#!/usr/bin/env python3
"""
Tally Desktop Sync Agent v2
Rewritten to match actual TallyPrime XML response formats.

Setup:
1. Install Python 3.8+
2. pip install requests xmltodict python-dotenv schedule
3. Create .env with BACKEND_URL=http://localhost:8001 (or your cloud URL)
4. Run: python tally_sync_agent.py
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

# Fix Windows console encoding BEFORE any output
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


class TallySyncAgent:
    """Syncs data from local TallyPrime to cloud backend."""

    # --- XML Request Templates (matched to actual Tally Prime responses) ---

    # Stock Summary report - returns DSPACCNAME/DSPSTKINFO display pairs
    STOCK_SUMMARY_XML = """<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Stock Summary</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY>
</ENVELOPE>"""

    # Sales Vouchers - returns structured VOUCHER elements inside TALLYMESSAGE
    SALES_VOUCHERS_XML = """<ENVELOPE>
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

    # Ledger list - returns display-format DSP entries
    LEDGER_XML = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>All Ledgers</ID>
</HEADER>
<BODY><DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</DESC></BODY>
</ENVELOPE>"""

    def __init__(self):
        self.tally_host = os.getenv('TALLY_HOST', 'localhost')
        self.tally_port = int(os.getenv('TALLY_PORT', '9000'))
        self.tally_url = f"http://{self.tally_host}:{self.tally_port}"
        self.backend_url = os.getenv('BACKEND_URL', 'http://localhost:8001')
        self.api_key = os.getenv('AGENT_API_KEY', '')
        self.sync_interval = int(os.getenv('SYNC_INTERVAL_MINUTES', '10'))
        self.debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        self.last_sync_time = None
        self.sync_running = False
        self.company_name = None

        logger.info(f"Tally Sync Agent v2 initialized")
        logger.info(f"  Tally: {self.tally_url}")
        logger.info(f"  Backend: {self.backend_url}")
        logger.info(f"  Sync every {self.sync_interval} min | Debug: {self.debug_mode}")

    # ------------------------------------------------------------------
    # Tally HTTP helpers
    # ------------------------------------------------------------------

    def _send_tally_request(self, xml_body: str, timeout: int = 120) -> Optional[str]:
        """Send XML request to Tally and return raw response text."""
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
            raw = resp.content.decode('utf-8', errors='replace')
            # Strip BOM
            raw = raw.lstrip('\ufeff')
            return raw
        except requests.exceptions.ReadTimeout:
            logger.error(f"Tally request timed out after {timeout}s")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Tally - is it running?")
            return None
        except Exception as e:
            logger.error(f"Tally request error: {e}")
            return None

    def _sanitize_xml(self, xml: str) -> str:
        """Remove problematic characters from Tally XML."""
        xml = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', xml)
        xml = re.sub(r'&#[0-9]+;?', ' ', xml)
        xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml)
        return xml

    def _dump_debug(self, name: str, content: str):
        """Save raw XML to file when debug mode is on."""
        if not self.debug_mode:
            return
        os.makedirs('debug_xml', exist_ok=True)
        path = os.path.join('debug_xml', f'{name}.xml')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"  [DEBUG] Saved {path} ({len(content)} chars)")

    # ------------------------------------------------------------------
    # Numeric parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_number(val) -> float:
        """Safely parse a numeric value from Tally (handles commas, spaces, None)."""
        if val is None:
            return 0.0
        s = str(val).replace(',', '').strip()
        if not s:
            return 0.0
        # Remove trailing unit like " Nos" or " Pcs"
        parts = s.split()
        try:
            return abs(float(parts[0]))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_qty_unit(val):
        """Parse '30 Nos' -> (30.0, 'Nos'), or empty -> (0, 'Pcs')."""
        if val is None or str(val).strip() == '':
            return 0.0, 'Pcs'
        s = str(val).strip()
        parts = s.split()
        try:
            qty = abs(float(parts[0].replace(',', '')))
        except (ValueError, TypeError):
            qty = 0.0
        unit = parts[1] if len(parts) > 1 else 'Pcs'
        return qty, unit

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_tally_connection(self) -> bool:
        """Quick ping to Tally."""
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
            logger.error(f"Tally returned HTTP {resp.status_code}")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to TallyPrime. Is it running on port %s?", self.tally_port)
            return False
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False

    # ------------------------------------------------------------------
    # INVENTORY: Parse Stock Summary display format
    # ------------------------------------------------------------------

    def fetch_inventory_from_tally(self) -> List[Dict[str, Any]]:
        """
        Fetch inventory using Stock Summary report.
        Tally returns display-format XML with DSPACCNAME/DSPSTKINFO pairs.
        """
        logger.info("Fetching Stock Summary from Tally...")
        raw = self._send_tally_request(self.STOCK_SUMMARY_XML, timeout=120)
        if not raw:
            return []

        self._dump_debug('stock_summary', raw)
        logger.info(f"Stock Summary response: {len(raw)} chars")

        raw = self._sanitize_xml(raw)
        items = []

        try:
            # Stock Summary is a single ENVELOPE with paired DSPACCNAME + DSPSTKINFO
            data = xmltodict.parse(raw)
            envelope = data.get('ENVELOPE', {})

            if not isinstance(envelope, dict):
                logger.error("Unexpected ENVELOPE format")
                return []

            names_raw = envelope.get('DSPACCNAME', [])
            infos_raw = envelope.get('DSPSTKINFO', [])

            # Ensure lists
            if isinstance(names_raw, dict):
                names_raw = [names_raw]
            if isinstance(infos_raw, dict):
                infos_raw = [infos_raw]

            if not names_raw:
                logger.warning("No DSPACCNAME found in Stock Summary")
                logger.info(f"Keys found: {list(envelope.keys())}")
                return []

            logger.info(f"Found {len(names_raw)} stock items in summary")

            for i, name_el in enumerate(names_raw):
                if not isinstance(name_el, dict):
                    continue
                item_name = name_el.get('DSPDISPNAME', '')
                if not item_name or not str(item_name).strip():
                    continue
                item_name = str(item_name).strip()

                # Get corresponding stock info
                stk_info = {}
                if i < len(infos_raw) and isinstance(infos_raw[i], dict):
                    stk_cl = infos_raw[i].get('DSPSTKCL', {})
                    if isinstance(stk_cl, dict):
                        stk_info = stk_cl

                qty, unit = self._parse_qty_unit(stk_info.get('DSPCLQTY'))
                rate = self._parse_number(stk_info.get('DSPCLRATE'))
                amount = self._parse_number(stk_info.get('DSPCLAMTA'))

                # If rate is 0 but we have amount and qty, calculate rate
                if rate == 0 and qty > 0 and amount > 0:
                    rate = round(amount / qty, 2)

                items.append({
                    'item_id': item_name,
                    'item_name': item_name,
                    'quantity': qty,
                    'unit': unit,
                    'price': rate,
                    'category': 'General',
                    'reorder_level': 10.0
                })

            logger.info(f"Parsed {len(items)} inventory items from Stock Summary")

        except Exception as e:
            logger.error(f"Error parsing Stock Summary: {e}")

        return items

    # ------------------------------------------------------------------
    # SALES: Parse structured VOUCHER elements
    # ------------------------------------------------------------------

    def fetch_sales_from_tally(self) -> List[Dict[str, Any]]:
        """
        Fetch sales vouchers from TallyPrime.
        Response: ENVELOPE > BODY > DATA > TALLYMESSAGE > VOUCHER (structured).
        """
        logger.info("Fetching Sales Vouchers from Tally...")
        raw = self._send_tally_request(self.SALES_VOUCHERS_XML, timeout=180)
        if not raw:
            return []

        self._dump_debug('sales_vouchers', raw)
        logger.info(f"Sales response: {len(raw)} chars")

        raw = self._sanitize_xml(raw)
        vouchers = []

        try:
            data = xmltodict.parse(raw)
            envelope = data.get('ENVELOPE', {})

            # Extract company name from response
            body = envelope.get('BODY', {})
            if isinstance(body, dict):
                desc = body.get('DESC', {})
                if isinstance(desc, dict):
                    sv = desc.get('STATICVARIABLES', {})
                    if isinstance(sv, dict):
                        cn = sv.get('SVCURRENTCOMPANY')
                        if cn:
                            self.company_name = str(cn)
                            logger.info(f"Company: {self.company_name}")

            # Navigate to TALLYMESSAGE
            data_section = body.get('DATA', {}) if isinstance(body, dict) else {}
            tally_msgs = data_section.get('TALLYMESSAGE', []) if isinstance(data_section, dict) else []

            if isinstance(tally_msgs, dict):
                tally_msgs = [tally_msgs]

            for msg in tally_msgs:
                if not isinstance(msg, dict):
                    continue
                # Skip COMPANY info messages
                if 'COMPANY' in msg:
                    continue

                voucher_raw = msg.get('VOUCHER')
                if not voucher_raw:
                    continue

                # Could be a single voucher dict or a list
                v_list = voucher_raw if isinstance(voucher_raw, list) else [voucher_raw]

                for v in v_list:
                    parsed = self._parse_single_voucher(v)
                    if parsed:
                        vouchers.append(parsed)

            logger.info(f"Parsed {len(vouchers)} sales vouchers")

        except Exception as e:
            logger.error(f"Error parsing sales vouchers: {e}")

        return vouchers

    def _parse_single_voucher(self, v: dict) -> Optional[Dict[str, Any]]:
        """Parse one VOUCHER element from the structured XML."""
        if not isinstance(v, dict):
            return None

        # Voucher number - try multiple field names
        v_number = (v.get('VOUCHERNUMBER') or v.get('NUMBER') or
                    v.get('@REMOTEID', '')[:20] or f"V-{id(v)}")

        # Date - Tally uses YYYYMMDD format
        raw_date = v.get('DATE', '')
        if raw_date and len(str(raw_date)) == 8 and str(raw_date).isdigit():
            d = str(raw_date)
            formatted_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        else:
            formatted_date = str(raw_date)

        # Party/Customer name
        party = (v.get('PARTYLEDGERNAME') or v.get('BASICBUYERNAME') or
                 v.get('PARTYNAME') or 'Unknown')

        # Amount - try various fields
        amount = 0.0
        for amt_field in ['AMOUNT', 'PARTYLEDGERAMOUNT', 'BASICBUYERAMOUNT']:
            val = v.get(amt_field)
            if val is not None:
                amount = self._parse_number(val)
                if amount > 0:
                    break

        # If still 0, try to sum up ledger entries
        if amount == 0:
            ledger_entries = v.get('ALLLEDGERENTRIES.LIST', v.get('LEDGERENTRIES.LIST', []))
            if isinstance(ledger_entries, dict):
                ledger_entries = [ledger_entries]
            if isinstance(ledger_entries, list):
                for le in ledger_entries:
                    if isinstance(le, dict):
                        le_amt = self._parse_number(le.get('AMOUNT', 0))
                        if le_amt > amount:
                            amount = le_amt

        # Line items from inventory entries
        line_items = []
        inv_entries = v.get('ALLINVENTORYENTRIES.LIST', v.get('INVENTORYENTRIES.LIST', []))
        if isinstance(inv_entries, dict):
            inv_entries = [inv_entries]
        if isinstance(inv_entries, list):
            for entry in inv_entries:
                if not isinstance(entry, dict):
                    continue
                item_name = entry.get('STOCKITEMNAME', entry.get('ITEMNAME', ''))
                if not item_name or str(item_name).strip() == '':
                    continue

                actual_qty = entry.get('ACTUALQTY', entry.get('BILLEDQTY', 0))
                rate = entry.get('RATE', entry.get('AMOUNT', 0))

                qty_val = self._parse_number(actual_qty)
                # Rate might be "100/Nos" format
                rate_str = str(rate) if rate else '0'
                rate_val = self._parse_number(rate_str.split('/')[0])

                entry_amount = self._parse_number(entry.get('AMOUNT', 0))

                line_items.append({
                    'item': str(item_name).strip(),
                    'quantity': qty_val,
                    'rate': rate_val,
                    'amount': entry_amount
                })

        # Reference number
        ref = v.get('REFERENCE', v.get('NARRATION', ''))

        return {
            'voucher_id': str(v_number),
            'voucher_date': formatted_date,
            'party_name': str(party),
            'total_amount': amount,
            'items': line_items,
            'reference_number': str(ref) if ref else ''
        }

    # ------------------------------------------------------------------
    # CUSTOMERS: Extract from Sales + Ledger data
    # ------------------------------------------------------------------

    def extract_customers_from_sales(self, vouchers: List[Dict]) -> List[Dict[str, Any]]:
        """Build unique customer list from sales voucher party names."""
        seen = {}
        for v in vouchers:
            name = v.get('party_name', '').strip()
            if not name or name == 'Unknown':
                continue
            key = name.lower()
            if key not in seen:
                seen[key] = {
                    'customer_name': name,
                    'outstanding_amount': 0.0,
                    'total_purchases': 0.0,
                    'transaction_count': 0
                }
            seen[key]['total_purchases'] += v.get('total_amount', 0)
            seen[key]['transaction_count'] += 1

        customers = list(seen.values())
        logger.info(f"Extracted {len(customers)} unique customers from sales data")
        return customers

    # ------------------------------------------------------------------
    # SYNC to backend
    # ------------------------------------------------------------------

    def sync_to_backend(self, data_type: str, data: List[Dict]) -> bool:
        """Push data to cloud backend."""
        if not data:
            logger.info(f"No {data_type} data to sync, skipping")
            return True

        try:
            endpoint = f"{self.backend_url}/api/agent/sync"
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.utcnow().isoformat(),
                'agent_version': '2.0.0',
                'company_name': self.company_name or ''
            }
            headers = {
                'Content-Type': 'application/json',
                'X-Agent-Key': self.api_key
            }

            resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)

            if resp.status_code == 200:
                logger.info(f"[OK] Synced {len(data)} {data_type} items to backend")
                return True
            else:
                logger.error(f"Sync failed for {data_type}: HTTP {resp.status_code}")
                logger.error(f"Response: {resp.text[:500]}")
                return False

        except Exception as e:
            logger.error(f"Error syncing {data_type}: {e}")
            return False

    # ------------------------------------------------------------------
    # Full sync cycle
    # ------------------------------------------------------------------

    def run_sync_cycle(self):
        """Execute one complete sync cycle."""
        if self.sync_running:
            logger.warning("Sync already in progress, skipping")
            return

        try:
            self.sync_running = True
            logger.info("=" * 50)
            logger.info("Starting sync cycle...")

            if not self.test_tally_connection():
                return

            # 1. Inventory (Stock Summary)
            logger.info("--- Inventory ---")
            inventory = self.fetch_inventory_from_tally()
            if inventory:
                self.sync_to_backend('inventory', inventory)
            else:
                logger.warning("No inventory data fetched")

            # 2. Sales Vouchers
            logger.info("--- Sales ---")
            sales = self.fetch_sales_from_tally()
            if sales:
                self.sync_to_backend('sales', sales)

                # 3. Customers (extracted from sales)
                logger.info("--- Customers ---")
                customers = self.extract_customers_from_sales(sales)
                if customers:
                    self.sync_to_backend('customers', customers)
            else:
                logger.warning("No sales data fetched")

            self.last_sync_time = datetime.now()
            logger.info(f"[OK] Sync cycle completed at {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"Sync cycle error: {e}")
        finally:
            self.sync_running = False

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(self):
        """Start the sync agent with scheduled syncs."""
        logger.info("")
        logger.info("=" * 50)
        logger.info("  TALLY DESKTOP SYNC AGENT v2")
        logger.info("=" * 50)
        logger.info("")

        # Initial sync
        logger.info("Running initial sync...")
        self.run_sync_cycle()

        # Schedule periodic syncs
        schedule.every(self.sync_interval).minutes.do(self.run_sync_cycle)

        logger.info(f"Scheduled: syncing every {self.sync_interval} minutes")
        logger.info("Press Ctrl+C to stop.")
        logger.info("")

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
