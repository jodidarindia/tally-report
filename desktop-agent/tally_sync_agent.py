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
            # Remove invalid XML characters
            raw_xml = re.sub(r'&#x[0-9a-fA-F]+;?', '', raw_xml)
            raw_xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw_xml)
            # Handle multiple XML documents (Tally sometimes sends multiple root elements)
            if raw_xml.count('<?xml') > 1:
                raw_xml = raw_xml.split('<?xml')[1]
                raw_xml = '<?xml' + raw_xml
            data = xmltodict.parse(raw_xml)
            items = []
            
            # Extract stock items from response
            envelope = data.get('ENVELOPE', {})
            body = envelope.get('BODY', {})
            
            # TallyPrime XML structure varies, handle different formats
            stock_items = body.get('STOCKITEM', [])
            if not isinstance(stock_items, list):
                stock_items = [stock_items] if stock_items else []
            
            for item in stock_items:
                if not item:
                    continue
                    
                item_data = {
                    'item_id': item.get('NAME', 'Unknown'),
                    'item_name': item.get('NAME', 'Unknown'),
                    'quantity': float(item.get('CLOSINGBALANCE', 0) or 0),
                    'unit': item.get('BASEUNITS', 'Pcs'),
                    'price': float(item.get('CLOSINGRATE', 0) or 0),
                    'category': item.get('PARENT', 'General'),
                    'reorder_level': 10.0  # Can be fetched if configured in Tally
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
            raw_xml = re.sub(r'&#x[0-9a-fA-F]+;?', '', raw_xml)
            raw_xml = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw_xml)
            if raw_xml.count('<?xml') > 1:
                raw_xml = raw_xml.split('<?xml')[1]
                raw_xml = '<?xml' + raw_xml
            data = xmltodict.parse(raw_xml)
            vouchers = []
            
            envelope = data.get('ENVELOPE', {})
            body = envelope.get('BODY', {})
            
            voucher_items = body.get('VOUCHER', [])
            if not isinstance(voucher_items, list):
                voucher_items = [voucher_items] if voucher_items else []
            
            for voucher in voucher_items:
                if not voucher:
                    continue
                    
                voucher_data = {
                    'voucher_id': voucher.get('VOUCHERNUMBER', 'Unknown'),
                    'voucher_date': voucher.get('DATE', ''),
                    'party_name': voucher.get('PARTYLEDGERNAME', 'Unknown'),
                    'total_amount': abs(float(voucher.get('AMOUNT', 0) or 0)),
                    'items': [],
                    'reference_number': voucher.get('REFERENCE', '')
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
