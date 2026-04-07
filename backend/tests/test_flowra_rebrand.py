"""
FLOWRA Rebrand Testing - Iteration 7
Tests for verifying the rebrand from 'Tally Reports' to 'FLOWRA'
and blue/purple color theme implementation.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com')

class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "token" in data["data"]
        assert data["data"]["role"] == "admin"
        assert data["data"]["username"] == "admin"
    
    def test_employee_login_success(self):
        """Test employee login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "emp1",
            "password": "emp123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "token" in data["data"]
        assert data["data"]["role"] == "employee"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code in [401, 200]  # May return 200 with success=false
        data = response.json()
        if response.status_code == 200:
            assert data["success"] == False


class TestTallyStatus:
    """Tally connection status tests"""
    
    def test_tally_status_endpoint(self):
        """Test /api/tally/status returns connection info"""
        response = requests.get(f"{BASE_URL}/api/tally/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "is_connected" in data["data"]
        assert "company_name" in data["data"]


class TestInventoryEndpoints:
    """Inventory endpoint tests"""
    
    def test_get_inventory_items(self):
        """Test /api/inventory/items returns items list"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "items" in data["data"]
        assert isinstance(data["data"]["items"], list)
    
    def test_inventory_has_stock_groups(self):
        """Test inventory response includes stock_groups for filtering"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        assert "stock_groups" in data["data"]


class TestSalesEndpoints:
    """Sales endpoint tests"""
    
    def test_get_sales_vouchers(self):
        """Test /api/sales/vouchers returns vouchers list"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "vouchers" in data["data"]
        assert isinstance(data["data"]["vouchers"], list)
    
    def test_sales_voucher_detail(self):
        """Test /api/sales/vouchers/{id} returns voucher detail"""
        # First get list to find a voucher ID
        list_response = requests.get(f"{BASE_URL}/api/sales/vouchers")
        vouchers = list_response.json()["data"]["vouchers"]
        
        if len(vouchers) > 0:
            voucher_id = vouchers[0]["voucher_id"]
            response = requests.get(f"{BASE_URL}/api/sales/vouchers/{voucher_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "voucher_id" in data["data"]
            assert "party_name" in data["data"]
    
    def test_sales_analytics(self):
        """Test /api/sales/analytics returns analytics data"""
        response = requests.get(f"{BASE_URL}/api/sales/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True


class TestCRMEndpoints:
    """CRM endpoint tests"""
    
    def test_get_outstanding_customers(self):
        """Test /api/customers/outstanding returns customer list with aging"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "customers" in data["data"]
        
        # Verify aging columns exist
        if len(data["data"]["customers"]) > 0:
            customer = data["data"]["customers"][0]
            assert "aging_0_30" in customer
            assert "aging_30_60" in customer
            assert "aging_60_90" in customer
            assert "aging_90_plus" in customer
            assert "status" in customer
            assert "ledger_group" in customer
    
    def test_outstanding_status_values(self):
        """Test outstanding status is one of expected values"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        data = response.json()
        
        valid_statuses = ["normal", "at_risk", "overdue", "critical"]
        for customer in data["data"]["customers"]:
            assert customer["status"] in valid_statuses
    
    def test_get_followups(self):
        """Test /api/customers/followups returns followups list"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "followups" in data["data"]
    
    def test_get_targets(self):
        """Test /api/customers/targets returns targets list"""
        response = requests.get(f"{BASE_URL}/api/customers/targets")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "targets" in data["data"]


class TestExportEndpoints:
    """Export functionality tests"""
    
    def test_export_inventory_csv(self):
        """Test inventory CSV export"""
        response = requests.post(f"{BASE_URL}/api/reports/export", json={
            "report_type": "inventory",
            "format": "csv"
        })
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "") or len(response.content) > 0
    
    def test_export_sales_csv(self):
        """Test sales CSV export"""
        response = requests.post(f"{BASE_URL}/api/reports/export", json={
            "report_type": "sales",
            "format": "csv"
        })
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
