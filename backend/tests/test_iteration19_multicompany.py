"""
Iteration 19: Multi-Company Data Switching Tests
Tests the multi-tenant company data isolation feature.
Admin user has 2 companies: 'ASA AUTOTECH INDIA PRIVATE LIMITED' and 'Demo Trading Co'
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Company names
COMPANY_ASA = "ASA AUTOTECH INDIA PRIVATE LIMITED"
COMPANY_DEMO = "Demo Trading Co"

# Expected data counts (approximate)
ASA_INVENTORY_COUNT = 202
ASA_SALES_COUNT = 1255
DEMO_INVENTORY_COUNT = 3
DEMO_SALES_COUNT = 2
DEMO_CUSTOMER_COUNT = 2


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("success"), f"Login not successful: {data}"
    return data["data"]["token"]


@pytest.fixture(scope="module")
def admin_companies(auth_token):
    """Get companies list from login response"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    data = response.json()
    return data["data"].get("companies", [])


class TestAdminLogin:
    """Test admin login returns correct companies"""
    
    def test_admin_login_success(self):
        """Admin login should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "token" in data.get("data", {})
    
    def test_admin_has_two_companies(self):
        """Admin should have exactly 2 companies"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        data = response.json()
        companies = data["data"].get("companies", [])
        assert len(companies) == 2, f"Expected 2 companies, got {len(companies)}: {companies}"
    
    def test_admin_companies_include_asa(self):
        """Admin should have ASA AUTOTECH company"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        data = response.json()
        companies = data["data"].get("companies", [])
        assert COMPANY_ASA in companies, f"ASA AUTOTECH not in companies: {companies}"
    
    def test_admin_companies_include_demo(self):
        """Admin should have Demo Trading Co company"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        data = response.json()
        companies = data["data"].get("companies", [])
        assert COMPANY_DEMO in companies, f"Demo Trading Co not in companies: {companies}"


class TestInventoryIsolation:
    """Test inventory data is isolated by company"""
    
    def test_asa_inventory_count(self, auth_token):
        """ASA AUTOTECH should have ~202 inventory items"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/items",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        count = data["data"].get("count", 0)
        assert count >= 200, f"Expected ~202 items for ASA, got {count}"
    
    def test_demo_inventory_count(self, auth_token):
        """Demo Trading Co should have exactly 3 inventory items"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/items",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        count = data["data"].get("count", 0)
        assert count == DEMO_INVENTORY_COUNT, f"Expected {DEMO_INVENTORY_COUNT} items for Demo, got {count}"
    
    def test_inventory_summary_asa(self, auth_token):
        """ASA inventory summary should show correct totals"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/summary?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_items = data["data"].get("total_items", 0)
        assert total_items >= 200, f"Expected ~202 total items for ASA, got {total_items}"
    
    def test_inventory_summary_demo(self, auth_token):
        """Demo inventory summary should show small totals"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/summary?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_items = data["data"].get("total_items", 0)
        assert total_items == DEMO_INVENTORY_COUNT, f"Expected {DEMO_INVENTORY_COUNT} total items for Demo, got {total_items}"


class TestSalesIsolation:
    """Test sales data is isolated by company"""
    
    def test_asa_sales_count(self, auth_token):
        """ASA AUTOTECH should have ~1255 sales vouchers"""
        response = requests.get(
            f"{BASE_URL}/api/sales/vouchers?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        count = data["data"].get("count", 0)
        assert count >= 1200, f"Expected ~1255 vouchers for ASA, got {count}"
    
    def test_demo_sales_count(self, auth_token):
        """Demo Trading Co should have exactly 2 sales vouchers"""
        response = requests.get(
            f"{BASE_URL}/api/sales/vouchers?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        count = data["data"].get("count", 0)
        assert count == DEMO_SALES_COUNT, f"Expected {DEMO_SALES_COUNT} vouchers for Demo, got {count}"
    
    def test_sales_summary_asa(self, auth_token):
        """ASA sales summary should show high totals"""
        response = requests.get(
            f"{BASE_URL}/api/sales/summary?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_vouchers = data["data"].get("total_vouchers", 0)
        assert total_vouchers >= 1200, f"Expected ~1255 total vouchers for ASA, got {total_vouchers}"
    
    def test_sales_summary_demo(self, auth_token):
        """Demo sales summary should show small totals"""
        response = requests.get(
            f"{BASE_URL}/api/sales/summary?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_vouchers = data["data"].get("total_vouchers", 0)
        assert total_vouchers == DEMO_SALES_COUNT, f"Expected {DEMO_SALES_COUNT} total vouchers for Demo, got {total_vouchers}"


class TestCustomerIsolation:
    """Test customer data is isolated by company"""
    
    def test_asa_customers(self, auth_token):
        """ASA AUTOTECH should have many customers"""
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"].get("customers", [])
        assert len(customers) >= 30, f"Expected many customers for ASA, got {len(customers)}"
    
    def test_demo_customers(self, auth_token):
        """Demo Trading Co should have exactly 2 customers"""
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"].get("customers", [])
        assert len(customers) == DEMO_CUSTOMER_COUNT, f"Expected {DEMO_CUSTOMER_COUNT} customers for Demo, got {len(customers)}"


class TestDashboardIsolation:
    """Test dashboard data is isolated by company"""
    
    def test_dashboard_reminders_asa(self, auth_token):
        """Dashboard reminders should work for ASA"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/reminders",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
    
    def test_dashboard_reminders_demo(self, auth_token):
        """Dashboard reminders should work for Demo"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/reminders",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


class TestSyncStatusIsolation:
    """Test sync status is isolated by company"""
    
    def test_sync_connection_status_asa(self, auth_token):
        """Sync connection status should work for ASA"""
        response = requests.get(
            f"{BASE_URL}/api/sync/connection-status",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
    
    def test_sync_connection_status_demo(self, auth_token):
        """Sync connection status should work for Demo"""
        response = requests.get(
            f"{BASE_URL}/api/sync/connection-status",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


class TestCompanySwitching:
    """Test that switching companies returns different data"""
    
    def test_inventory_differs_between_companies(self, auth_token):
        """Inventory count should differ between companies"""
        # Get ASA inventory
        resp_asa = requests.get(
            f"{BASE_URL}/api/inventory/items",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        count_asa = resp_asa.json()["data"].get("count", 0)
        
        # Get Demo inventory
        resp_demo = requests.get(
            f"{BASE_URL}/api/inventory/items",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        count_demo = resp_demo.json()["data"].get("count", 0)
        
        assert count_asa != count_demo, f"Inventory counts should differ: ASA={count_asa}, Demo={count_demo}"
        assert count_asa > count_demo, f"ASA should have more items than Demo"
    
    def test_sales_differs_between_companies(self, auth_token):
        """Sales count should differ between companies"""
        # Get ASA sales
        resp_asa = requests.get(
            f"{BASE_URL}/api/sales/vouchers?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_ASA
            }
        )
        count_asa = resp_asa.json()["data"].get("count", 0)
        
        # Get Demo sales
        resp_demo = requests.get(
            f"{BASE_URL}/api/sales/vouchers?fy=2025-26",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Company-ID": COMPANY_DEMO
            }
        )
        count_demo = resp_demo.json()["data"].get("count", 0)
        
        assert count_asa != count_demo, f"Sales counts should differ: ASA={count_asa}, Demo={count_demo}"
        assert count_asa > count_demo, f"ASA should have more sales than Demo"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
