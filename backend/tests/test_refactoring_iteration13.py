"""
Iteration 13: Refactoring Validation Tests
Tests all endpoints after server.py was split into 9 route modules.
Validates that all APIs return the same responses as before refactoring.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthEndpoints:
    """Auth route module tests - /api/auth/*"""
    
    def test_login_success(self):
        """POST /api/auth/login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "token" in data["data"]
        assert data["data"]["username"] == "admin"
        assert data["data"]["role"] == "admin"
        print(f"✓ Login successful, token received")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "error" in data
        print(f"✓ Invalid login correctly rejected")


class TestTallyEndpoints:
    """Tally route module tests - /api/tally/*"""
    
    def test_tally_status(self):
        """GET /api/tally/status returns connection status"""
        response = requests.get(f"{BASE_URL}/api/tally/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Should have is_connected field
        assert "is_connected" in data["data"]
        print(f"✓ Tally status: connected={data['data'].get('is_connected')}")


class TestSyncEndpoints:
    """Sync route module tests - /api/sync/*"""
    
    def test_sync_status(self):
        """GET /api/sync/status returns last sync info"""
        response = requests.get(f"{BASE_URL}/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        print(f"✓ Sync status retrieved")


class TestInventoryEndpoints:
    """Inventory route module tests - /api/inventory/*"""
    
    def test_inventory_summary(self):
        """GET /api/inventory/summary?fy=2024-2025 returns summary stats"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Validate required fields
        assert "total_items" in data["data"]
        assert "total_value" in data["data"]
        assert "low_stock_items" in data["data"]
        print(f"✓ Inventory summary: {data['data']['total_items']} items, value={data['data']['total_value']}")
    
    def test_inventory_items(self):
        """GET /api/inventory/items returns item list"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "items" in data["data"]
        print(f"✓ Inventory items: {data['data'].get('count', len(data['data']['items']))} items")
    
    def test_inventory_movement_analysis(self):
        """GET /api/inventory/movement-analysis?fy=2024-2025 returns movement data"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "movements" in data["data"]
        assert "summary" in data["data"]
        print(f"✓ Movement analysis: {len(data['data']['movements'])} items analyzed")


class TestSalesEndpoints:
    """Sales route module tests - /api/sales/*"""
    
    def test_sales_summary(self):
        """GET /api/sales/summary?fy=2024-2025 returns sales summary"""
        response = requests.get(f"{BASE_URL}/api/sales/summary", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Validate required fields
        assert "total_vouchers" in data["data"]
        assert "total_sales" in data["data"]
        assert "top_customers" in data["data"]
        assert "recent_vouchers" in data["data"]
        print(f"✓ Sales summary: {data['data']['total_vouchers']} vouchers, total={data['data']['total_sales']}")
    
    def test_sales_vouchers(self):
        """GET /api/sales/vouchers?fy=2024-2025 returns voucher list with metadata"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "vouchers" in data["data"]
        assert "unique_parties" in data["data"]
        assert "unique_months" in data["data"]
        print(f"✓ Sales vouchers: {data['data'].get('count', len(data['data']['vouchers']))} vouchers")


class TestCustomerEndpoints:
    """Customer/CRM route module tests - /api/customers/*"""
    
    def test_customer_outstanding(self):
        """GET /api/customers/outstanding?fy=2024-2025 returns outstanding data"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Validate required fields
        assert "customers" in data["data"]
        assert "groups" in data["data"]
        assert "states" in data["data"]
        print(f"✓ Customer outstanding: {len(data['data']['customers'])} customers")
    
    def test_customer_payment_behavior(self):
        """GET /api/customers/payment-behavior?fy=2024-2025 returns payment analysis"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "customers" in data["data"]
        print(f"✓ Payment behavior: {len(data['data']['customers'])} customers analyzed")
    
    def test_customer_targets(self):
        """GET /api/customers/targets?fy=2024-2025 returns target data"""
        response = requests.get(f"{BASE_URL}/api/customers/targets", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "targets" in data["data"]
        print(f"✓ Customer targets: {len(data['data']['targets'])} targets")
    
    def test_customer_followups(self):
        """GET /api/customers/followups returns followup list"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "followups" in data["data"]
        print(f"✓ Followups: {data['data'].get('count', len(data['data']['followups']))} followups")


class TestSalesmanEndpoints:
    """Salesman route module tests - /api/salesman/*"""
    
    def test_salesman_performance_detailed(self):
        """GET /api/salesman/performance-detailed?fy=2024-2025 returns detailed performance"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "salesman" in data["data"]
        print(f"✓ Salesman performance: {len(data['data']['salesman'])} salesmen")
    
    def test_salesman_performance(self):
        """GET /api/salesman/performance?fy=2024-2025 returns basic performance"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "salesman" in data["data"]
        print(f"✓ Salesman basic performance retrieved")
    
    def test_salesman_master(self):
        """GET /api/salesman/master returns salesman master list"""
        response = requests.get(f"{BASE_URL}/api/salesman/master")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "salesmen" in data["data"]
        print(f"✓ Salesman master: {len(data['data']['salesmen'])} salesmen")


class TestDashboardEndpoints:
    """Dashboard route module tests - /api/dashboard/*"""
    
    def test_dashboard_overdue_digest(self):
        """GET /api/dashboard/overdue-digest returns overdue summary"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Validate required fields
        assert "threshold_days" in data["data"]
        assert data["data"]["threshold_days"] == 55
        print(f"✓ Overdue digest: threshold={data['data']['threshold_days']} days")
    
    def test_dashboard_reminders(self):
        """GET /api/dashboard/reminders returns reminder data"""
        response = requests.get(f"{BASE_URL}/api/dashboard/reminders")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Validate structure
        assert "overdue" in data["data"]
        assert "today" in data["data"]
        assert "upcoming" in data["data"]
        print(f"✓ Dashboard reminders: {data['data'].get('total_pending', 0)} pending")


class TestAIReportsEndpoints:
    """AI Reports route module tests - /api/reports/*"""
    
    def test_reports_history(self):
        """GET /api/reports/history returns query history"""
        response = requests.get(f"{BASE_URL}/api/reports/history")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "queries" in data["data"]
        print(f"✓ Reports history: {data['data'].get('count', len(data['data']['queries']))} queries")


class TestAdditionalEndpoints:
    """Additional endpoint tests for completeness"""
    
    def test_inventory_sales_frequency(self):
        """GET /api/inventory/sales-frequency returns frequency data"""
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "frequency" in data["data"]
        print(f"✓ Sales frequency: {data['data'].get('total_items', 0)} items")
    
    def test_inventory_purchase_orders(self):
        """GET /api/inventory/purchase-orders returns PO list"""
        response = requests.get(f"{BASE_URL}/api/inventory/purchase-orders")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "purchase_orders" in data["data"]
        print(f"✓ Purchase orders: {data['data'].get('count', 0)} orders")
    
    def test_inventory_pivot_data(self):
        """GET /api/inventory/pivot-data returns pivot table"""
        response = requests.get(f"{BASE_URL}/api/inventory/pivot-data")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "pivot_table" in data["data"]
        print(f"✓ Pivot data retrieved")
    
    def test_sales_analytics(self):
        """GET /api/sales/analytics returns analytics data"""
        response = requests.get(f"{BASE_URL}/api/sales/analytics", params={"fy": "2024-2025"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        print(f"✓ Sales analytics retrieved")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
