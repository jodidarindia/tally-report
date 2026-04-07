#!/usr/bin/env python3
"""
Tally Desktop Sync Agent

This agent runs on the Windows machine where TallyPrime is installed.
It syncs data from local Tally to the cloud backend every 10 minutes.

Setup:
1. Install Python 3.11+
2. Install dependencies: pip install requests xmltodict python-dotenv schedule
3. Configure .env file with your cloud backend URL
4. Run: python tally_sync_agent.py
5. Optional: Install as Windows Service for auto-start
"""

import os
import sys
import time
import logging
import requests
import xmltodict
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import schedule
from dotenv import load_dotenv

import re

# Configure logging - use utf-8 for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tally_sync_agent.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('TallySyncAgent')

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()

class TallySyncAgent:
    """
    Desktop agent that syncs TallyPrime data to cloud backend
    """
    
    def __init__(self):
        # Tally connection settings
        self.tally_host = os.getenv('TALLY_HOST', 'localhost')
        self.tally_port = int(os.getenv('TALLY_PORT', '9000'))
        self.tally_url = f"http://{self.tally_host}:{self.tally_port}"
        
        # Cloud backend settings
        self.backend_url = os.getenv('BACKEND_URL', 'http://localhost:8001')
        self.api_key = os.getenv('AGENT_API_KEY', '')  # For authenticating agent
        
        # Sync settings
        self.sync_interval = int(os.getenv('SYNC_INTERVAL_MINUTES', '10'))
        self.last_sync_time = None
        self.sync_running = False
        
        logger.info(f"Tally Sync Agent initialized")
        logger.info(f"Tally: {self.tally_url}")
        logger.info(f"Backend: {self.backend_url}")
        logger.info(f"Sync Interval: {self.sync_interval} minutes")
    
    def _find_key_deep(self, d, target_key):
        """Recursively search for a key in nested dict"""
        if isinstance(d, dict):
            if target_key in d:
                return d[target_key]
            for v in d.values():
                result = self._find_key_deep(v, target_key)
                if result is not None:
                    return result
        elif isinstance(d, list):
            for item in d:
                result = self._find_key_deep(item, target_key)
                if result is not None:
                    return result
        return None

    def test_tally_connection(self) -> bool:
        """Test connection to local TallyPrime"""
        try:
            test_xml = """<ENVELOPE>
                <HEADER>
                    <VERSION>1</VERSION>
                    <TALLYREQUEST>Export</TALLYREQUEST>
                    <TYPE>Data</TYPE>
                    <ID>$$NumStockItems</ID>
                </HEADER>
                <BODY>
                    <DESC></DESC>
                </BODY>
            </ENVELOPE>"""
            
            response = requests.post(
                self.tally_url,
                data=test_xml.encode('utf-8'),
                headers={'Content-Type': 'text/xml'},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("[OK] Connected to TallyPrime successfully")
                return True
            else:
                logger.error(f"[ERROR] TallyPrime connection failed: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("[ERROR] Cannot connect to TallyPrime. Ensure Tally is running and port 9000 is accessible.")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Error testing Tally connection: {e}")
            return False
    
    def fetch_inventory_from_tally(self) -> List[Dict[str, Any]]:
        """Fetch inventory data from TallyPrime using XML API"""
        try:
            xml_request = """<ENVELOPE>
                <HEADER>
                    <VERSION>1</VERSION>
                    <TALLYREQUEST>Export</TALLYREQUEST>
                    <TYPE>Data</TYPE>
                    <ID>All Stock Items</ID>
                </HEADER>
                <BODY>
                    <DESC>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                        </STATICVARIABLES>
                        <TDL>
                            <TDLMESSAGE>
                                <COLLECTION NAME="StockCollection" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                                    <TYPE>Stock Item</TYPE>
                                    <FETCH>Name, ClosingBalance, BaseUnits, Category, ClosingRate</FETCH>
                                </COLLECTION>
                                
                                <OBJECT NAME="StockExport" TYPE="Report" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                                    <FETCH>Name, ClosingBalance, BaseUnits, Parent, ClosingRate</FETCH>
                                    <USE>StockCollection</USE>
                                </OBJECT>
                            </TDLMESSAGE>
                        </TDL>
                    </DESC>
                </BODY>
            </ENVELOPE>"""
            
            response = requests.post(
                self.tally_url,
                data=xml_request.encode('utf-8'),
                headers={'Content-Type': 'text/xml'},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch inventory: HTTP {response.status_code}")
                return []
            
            # Parse XML response - sanitize Tally's messy XML first
            raw_xml = response.content.decode('utf-8', errors='replace')
            logger.info(f"Inventory XML response length: {len(raw_xml)} chars")
            
            # Remove BOM if present
            raw_xml = raw_xml.lstrip('\ufeff')
            
            # Remove invalid XML character references
            raw_xml = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', raw_xml)
            raw_xml = re.sub(r'&#[0-9]+;?', ' ', raw_xml)
            
            # Remove control characters
            raw_xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_xml)
            
            # Handle multiple XML documents - keep only the first complete one
            # Find the first <?xml...?> or <ENVELOPE> tag
            envelope_start = raw_xml.find('<ENVELOPE')
            if envelope_start == -1:
                logger.error("No ENVELOPE tag found in Tally response")
                logger.info(f"First 500 chars of response: {raw_xml[:500]}")
                return []
            
            envelope_end = raw_xml.find('</ENVELOPE>')
            if envelope_end == -1:
                logger.error("No closing ENVELOPE tag found")
                return []
            
            clean_xml = raw_xml[envelope_start:envelope_end + len('</ENVELOPE>')]
            
            data = xmltodict.parse(clean_xml)
            items = []
            
            # Log the top-level structure for debugging
            envelope = data.get('ENVELOPE', data)
            logger.info(f"Inventory XML top-level keys: {list(envelope.keys()) if isinstance(envelope, dict) else type(envelope)}")
            
            body = envelope.get('BODY', {})
            if isinstance(body, dict):
                logger.info(f"BODY keys: {list(body.keys())}")
            
            # TallyPrime XML structure varies - search for stock items at multiple paths
            stock_items = None
            
            # Path 1: BODY > DATA > COLLECTION > STOCKITEM
            if isinstance(body, dict):
                data_section = body.get('DATA', {})
                if isinstance(data_section, dict):
                    collection = data_section.get('COLLECTION', {})
                    if isinstance(collection, dict):
                        stock_items = collection.get('STOCKITEM', [])
            
            # Path 2: BODY > STOCKITEM
            if not stock_items and isinstance(body, dict):
                stock_items = body.get('STOCKITEM', [])
            
            # Path 3: BODY > DATA > TALLYMESSAGE > STOCKITEM  
            if not stock_items and isinstance(body, dict):
                data_section = body.get('DATA', {})
                if isinstance(data_section, dict):
                    tally_msg = data_section.get('TALLYMESSAGE', {})
                    if isinstance(tally_msg, dict):
                        stock_items = tally_msg.get('STOCKITEM', [])
            
            # Path 4: Deep search - find STOCKITEM anywhere in the structure
            if not stock_items:
                stock_items = self._find_key_deep(envelope, 'STOCKITEM')
            
            if not stock_items:
                logger.error(f"Could not find STOCKITEM in Tally response")
                logger.info(f"Full structure: {str(data)[:1000]}")
                return []
            
            if not isinstance(stock_items, list):
                stock_items = [stock_items] if stock_items else []
            
            for item in stock_items:
                if not item or not isinstance(item, dict):
                    continue
                
                # Handle different field name formats (uppercase, mixed case, with @)
                name = item.get('NAME', item.get('@NAME', item.get('STOCKITEMNAME', item.get('#text', 'Unknown'))))
                closing_bal = item.get('CLOSINGBALANCE', item.get('CLOSINGBAL', item.get('BASEUNITS', 0)))
                closing_rate = item.get('CLOSINGRATE', item.get('RATE', item.get('CLOSINGVALUE', 0)))
                parent = item.get('PARENT', item.get('STOCKGROUP', item.get('GROUP', 'General')))
                unit = item.get('BASEUNITS', item.get('UNITS', item.get('UNIT', 'Pcs')))
                
                # Parse numeric values safely
                try:
                    qty = float(str(closing_bal).replace(',', '').strip() or 0)
                except (ValueError, TypeError):
                    qty = 0
                try:
                    price = float(str(closing_rate).replace(',', '').strip() or 0)
                except (ValueError, TypeError):
                    price = 0
                    
                item_data = {
                    'item_id': str(name),
                    'item_name': str(name),
                    'quantity': abs(qty),
                    'unit': str(unit) if unit else 'Pcs',
                    'price': abs(price),
                    'category': str(parent) if parent else 'General',
                    'reorder_level': 10.0
                }
                items.append(item_data)
            
            logger.info(f"Fetched {len(items)} inventory items from Tally")
            return items
            
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
            return []
    
    def fetch_sales_from_tally(self) -> List[Dict[str, Any]]:
        """Fetch sales vouchers from TallyPrime"""
        try:
            xml_request = """<ENVELOPE>
                <HEADER>
                    <VERSION>1</VERSION>
                    <TALLYREQUEST>Export</TALLYREQUEST>
                    <TYPE>Data</TYPE>
                    <ID>Sales Vouchers</ID>
                </HEADER>
                <BODY>
                    <DESC>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                            <EXPLODEFLAG>Yes</EXPLODEFLAG>
                        </STATICVARIABLES>
                        <TDL>
                            <TDLMESSAGE>
                                <COLLECTION NAME="SalesCollection" ISMODIFY="No">
                                    <TYPE>Voucher</TYPE>
                                    <FETCH>VoucherNumber, Date, PartyLedgerName, Amount, VoucherTypeName</FETCH>
                                    <FILTER>VoucherTypeFilter</FILTER>
                                </COLLECTION>
                                
                                <SYSTEM TYPE="Formulae" NAME="VoucherTypeFilter">
                                    $$IsSales:$VoucherTypeName
                                </SYSTEM>
                            </TDLMESSAGE>
                        </TDL>
                    </DESC>
                </BODY>
            </ENVELOPE>"""
            
            response = requests.post(
                self.tally_url,
                data=xml_request.encode('utf-8'),
                headers={'Content-Type': 'text/xml'},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch sales: HTTP {response.status_code}")
                return []
            
            # Parse XML response - sanitize Tally's messy XML first
            raw_xml = response.content.decode('utf-8', errors='replace')
            logger.info(f"Sales XML response length: {len(raw_xml)} chars")
            
            # Remove BOM if present
            raw_xml = raw_xml.lstrip('\ufeff')
            
            # Remove invalid XML character references
            raw_xml = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', raw_xml)
            raw_xml = re.sub(r'&#[0-9]+;?', ' ', raw_xml)
            
            # Remove control characters
            raw_xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_xml)
            
            # Extract just the ENVELOPE portion
            envelope_start = raw_xml.find('<ENVELOPE')
            if envelope_start == -1:
                logger.error("No ENVELOPE tag found in sales response")
                logger.info(f"First 500 chars of response: {raw_xml[:500]}")
                return []
            
            envelope_end = raw_xml.find('</ENVELOPE>')
            if envelope_end == -1:
                logger.error("No closing ENVELOPE tag in sales response")
                return []
            
            clean_xml = raw_xml[envelope_start:envelope_end + len('</ENVELOPE>')]
            
            data = xmltodict.parse(clean_xml)
            vouchers = []
            
            envelope = data.get('ENVELOPE', data)
            logger.info(f"Sales XML top-level keys: {list(envelope.keys()) if isinstance(envelope, dict) else type(envelope)}")
            
            body = envelope.get('BODY', {})
            if isinstance(body, dict):
                logger.info(f"Sales BODY keys: {list(body.keys())}")
            
            # Search for vouchers at multiple paths
            voucher_items = None
            
            # Path 1: BODY > DATA > COLLECTION > VOUCHER
            if isinstance(body, dict):
                data_section = body.get('DATA', {})
                if isinstance(data_section, dict):
                    collection = data_section.get('COLLECTION', {})
                    if isinstance(collection, dict):
                        voucher_items = collection.get('VOUCHER', [])
            
            # Path 2: BODY > VOUCHER
            if not voucher_items and isinstance(body, dict):
                voucher_items = body.get('VOUCHER', [])
            
            # Path 3: BODY > DATA > TALLYMESSAGE > VOUCHER
            if not voucher_items and isinstance(body, dict):
                data_section = body.get('DATA', {})
                if isinstance(data_section, dict):
                    tally_msg = data_section.get('TALLYMESSAGE', {})
                    if isinstance(tally_msg, dict):
                        voucher_items = tally_msg.get('VOUCHER', [])
            
            # Path 4: Deep search
            if not voucher_items:
                voucher_items = self._find_key_deep(envelope, 'VOUCHER')
            
            if not voucher_items:
                logger.error("Could not find VOUCHER in Tally response")
                logger.info(f"Full structure: {str(data)[:1000]}")
                return []
            
            if not isinstance(voucher_items, list):
                voucher_items = [voucher_items] if voucher_items else []
            
            for voucher in voucher_items:
                if not voucher or not isinstance(voucher, dict):
                    continue
                
                # Handle different field name formats
                v_number = voucher.get('VOUCHERNUMBER', voucher.get('NUMBER', voucher.get('@VCHKEY', '')))
                v_date = voucher.get('DATE', voucher.get('VOUCHERDATE', voucher.get('@DATE', '')))
                party = voucher.get('PARTYLEDGERNAME', voucher.get('PARTYNAME', voucher.get('PARTY', 'Unknown')))
                amount = voucher.get('AMOUNT', voucher.get('PARTYLEDGERAMOUNT', voucher.get('CLOSINGBALANCE', 0)))
                ref = voucher.get('REFERENCE', voucher.get('VOUCHERNUMBER', voucher.get('NARRATION', '')))
                
                # Parse date - Tally uses YYYYMMDD format sometimes
                if v_date and len(str(v_date)) == 8 and str(v_date).isdigit():
                    v_date = f"{v_date[:4]}-{v_date[4:6]}-{v_date[6:8]}"
                
                # Parse amount safely
                try:
                    amt = abs(float(str(amount).replace(',', '').strip() or 0))
                except (ValueError, TypeError):
                    amt = 0
                
                # Extract line items if available
                line_items = []
                inv_entries = voucher.get('ALLINVENTORYENTRIES.LIST', voucher.get('INVENTORYENTRIES.LIST', []))
                if inv_entries:
                    if not isinstance(inv_entries, list):
                        inv_entries = [inv_entries]
                    for entry in inv_entries:
                        if isinstance(entry, dict):
                            item_name = entry.get('STOCKITEMNAME', entry.get('ITEMNAME', ''))
                            qty = entry.get('ACTUALQTY', entry.get('BILLEDQTY', 0))
                            rate = entry.get('RATE', entry.get('AMOUNT', 0))
                            try:
                                qty_val = abs(float(str(qty).split()[0].replace(',', '') if qty else 0))
                            except (ValueError, TypeError):
                                qty_val = 0
                            try:
                                rate_val = abs(float(str(rate).split('/')[0].replace(',', '').strip() if rate else 0))
                            except (ValueError, TypeError):
                                rate_val = 0
                            if item_name:
                                line_items.append({
                                    'item': str(item_name),
                                    'quantity': qty_val,
                                    'rate': rate_val
                                })
                
                voucher_data = {
                    'voucher_id': str(v_number) if v_number else f"V{len(vouchers)+1}",
                    'voucher_date': str(v_date),
                    'party_name': str(party),
                    'total_amount': amt,
                    'items': line_items,
                    'reference_number': str(ref) if ref else ''
                }
                vouchers.append(voucher_data)
            
            logger.info(f"Fetched {len(vouchers)} sales vouchers from Tally")
            return vouchers
            
        except Exception as e:
            logger.error(f"Error fetching sales: {e}")
            return []
    
    def sync_to_backend(self, data_type: str, data: List[Dict]) -> bool:
        """Push data to cloud backend"""
        try:
            endpoint = f"{self.backend_url}/api/agent/sync"
            
            payload = {
                'data_type': data_type,
                'data': data,
                'sync_time': datetime.utcnow().isoformat(),
                'agent_version': '1.0.0'
            }
            
            headers = {
                'Content-Type': 'application/json',
                'X-Agent-Key': self.api_key
            }
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"[OK] Synced {len(data)} {data_type} items to backend")
                return True
            else:
                logger.error(f"[ERROR] Failed to sync {data_type}: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error syncing {data_type} to backend: {e}")
            return False
    
    def run_sync_cycle(self):
        """Execute one complete sync cycle"""
        if self.sync_running:
            logger.warning("Sync already in progress, skipping...")
            return
        
        try:
            self.sync_running = True
            logger.info("="*60)
            logger.info("Starting sync cycle...")
            
            # Test Tally connection
            if not self.test_tally_connection():
                logger.error("Cannot connect to Tally. Please ensure Tally is running.")
                return
            
            # Fetch and sync inventory
            logger.info("Fetching inventory data...")
            inventory_data = self.fetch_inventory_from_tally()
            if inventory_data:
                self.sync_to_backend('inventory', inventory_data)
            
            # Fetch and sync sales
            logger.info("Fetching sales data...")
            sales_data = self.fetch_sales_from_tally()
            if sales_data:
                self.sync_to_backend('sales', sales_data)
            
            self.last_sync_time = datetime.now()
            logger.info(f"[OK] Sync cycle completed at {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Error during sync cycle: {e}")
        finally:
            self.sync_running = False
    
    def start(self):
        """Start the sync agent with scheduled syncs"""
        logger.info("")
        logger.info("========================================================")
        logger.info("       TALLY DESKTOP SYNC AGENT STARTED                ")
        logger.info("========================================================")
        logger.info("")
        
        # Initial sync
        logger.info("Running initial sync...")
        self.run_sync_cycle()
        
        # Schedule periodic syncs
        schedule.every(self.sync_interval).minutes.do(self.run_sync_cycle)
        
        logger.info(f"Agent running. Syncing every {self.sync_interval} minutes...")
        logger.info("Press Ctrl+C to stop.")
        logger.info("")
        
        # Keep running
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("")
            logger.info("Shutting down Tally Sync Agent...")
            logger.info("Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    agent = TallySyncAgent()
    agent.start()
