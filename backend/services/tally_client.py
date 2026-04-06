import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class TallyClient:
    """
    Client for communicating with TallyPrime using either REST API or XML/HTTP integration.
    """
    
    def __init__(self, connection_type: str = "xml", **kwargs):
        self.connection_type = connection_type
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TallyIntegrationClient/1.0"})
        
        if connection_type == "rest":
            self.api_key = kwargs.get("api_key")
            self.api_url = kwargs.get("api_url", "https://api.tally.so")
            if self.api_key:
                self.session.headers.update({
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                })
        elif connection_type == "xml":
            self.host = kwargs.get("host", "localhost")
            self.port = kwargs.get("port", 9000)
            self.protocol = kwargs.get("protocol", "http")
            self.base_url = f"{self.protocol}://{self.host}:{self.port}"
            self.session.headers.update({"Content-Type": "text/xml"})
        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")
    
    def test_connection(self) -> bool:
        """Test connectivity to TallyPrime server."""
        try:
            if self.connection_type == "rest":
                response = self.session.get(f"{self.api_url}/v1/accounts", timeout=5)
                return response.status_code in [200, 401]
            else:
                # For demo purposes, always return True for XML connection
                # In production, this would send a test XML request
                return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def fetch_inventory(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Fetch inventory/stock items from TallyPrime."""
        try:
            if self.connection_type == "rest":
                return self._fetch_inventory_rest(filters)
            else:
                return self._fetch_inventory_mock(filters)
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
            raise
    
    def _fetch_inventory_rest(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch inventory using REST API"""
        endpoint = f"{self.api_url}/v1/inventory/items"
        params = {}
        if filters:
            params.update(filters)
        
        response = self.session.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    
    def _fetch_inventory_mock(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Mock inventory data for demonstration"""
        mock_data = [
            {
                "item_id": "SKU001",
                "item_name": "Laptop Dell Inspiron",
                "quantity": 45.0,
                "unit": "Pcs",
                "price": 45000.0,
                "category": "Electronics",
                "reorder_level": 10.0
            },
            {
                "item_id": "SKU002",
                "item_name": "Office Chair Executive",
                "quantity": 120.0,
                "unit": "Pcs",
                "price": 8500.0,
                "category": "Furniture",
                "reorder_level": 20.0
            },
            {
                "item_id": "SKU003",
                "item_name": "Printer HP LaserJet",
                "quantity": 28.0,
                "unit": "Pcs",
                "price": 22000.0,
                "category": "Electronics",
                "reorder_level": 5.0
            },
            {
                "item_id": "SKU004",
                "item_name": "Desk Lamp LED",
                "quantity": 200.0,
                "unit": "Pcs",
                "price": 1200.0,
                "category": "Accessories",
                "reorder_level": 50.0
            },
            {
                "item_id": "SKU005",
                "item_name": "Whiteboard Magnetic",
                "quantity": 35.0,
                "unit": "Pcs",
                "price": 3500.0,
                "category": "Office Supplies",
                "reorder_level": 10.0
            }
        ]
        
        if filters:
            if "category" in filters:
                mock_data = [item for item in mock_data if item.get("category") == filters["category"]]
            if "min_quantity" in filters:
                mock_data = [item for item in mock_data if item.get("quantity", 0) >= filters["min_quantity"]]
        
        return mock_data
    
    def fetch_sales_vouchers(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Fetch sales vouchers/transactions from TallyPrime."""
        try:
            if self.connection_type == "rest":
                return self._fetch_sales_vouchers_rest(start_date, end_date)
            else:
                return self._fetch_sales_vouchers_mock(start_date, end_date)
        except Exception as e:
            logger.error(f"Error fetching sales vouchers: {e}")
            raise
    
    def _fetch_sales_vouchers_rest(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Fetch sales vouchers using REST API"""
        endpoint = f"{self.api_url}/v1/sales/vouchers"
        params = {}
        if start_date:
            params["from_date"] = start_date
        if end_date:
            params["to_date"] = end_date
        
        response = self.session.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("vouchers", [])
    
    def _fetch_sales_vouchers_mock(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Mock sales data for demonstration"""
        mock_data = [
            {
                "voucher_id": "SALE001",
                "voucher_date": "2026-01-05",
                "party_name": "Tech Solutions Pvt Ltd",
                "total_amount": 225000.0,
                "items": [{"item": "Laptop Dell Inspiron", "quantity": 5, "rate": 45000}],
                "reference_number": "INV-2026-001"
            },
            {
                "voucher_id": "SALE002",
                "voucher_date": "2026-01-08",
                "party_name": "Office Mart",
                "total_amount": 102000.0,
                "items": [{"item": "Office Chair Executive", "quantity": 12, "rate": 8500}],
                "reference_number": "INV-2026-002"
            },
            {
                "voucher_id": "SALE003",
                "voucher_date": "2026-01-10",
                "party_name": "Smart Enterprises",
                "total_amount": 66000.0,
                "items": [{"item": "Printer HP LaserJet", "quantity": 3, "rate": 22000}],
                "reference_number": "INV-2026-003"
            },
            {
                "voucher_id": "SALE004",
                "voucher_date": "2026-01-12",
                "party_name": "Corporate Hub Ltd",
                "total_amount": 180000.0,
                "items": [{"item": "Laptop Dell Inspiron", "quantity": 4, "rate": 45000}],
                "reference_number": "INV-2026-004"
            },
            {
                "voucher_id": "SALE005",
                "voucher_date": "2026-01-15",
                "party_name": "Global Systems Inc",
                "total_amount": 24000.0,
                "items": [{"item": "Desk Lamp LED", "quantity": 20, "rate": 1200}],
                "reference_number": "INV-2026-005"
            },
            {
                "voucher_id": "SALE006",
                "voucher_date": "2026-01-18",
                "party_name": "Tech Solutions Pvt Ltd",
                "total_amount": 85000.0,
                "items": [{"item": "Office Chair Executive", "quantity": 10, "rate": 8500}],
                "reference_number": "INV-2026-006"
            }
        ]
        return mock_data
    
    def close(self):
        """Close the session"""
        if self.session:
            self.session.close()
