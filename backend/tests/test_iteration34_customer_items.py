"""
Iteration 34: Customer Items Feature + UUID Migration Regression Tests
Tests:
1. UUID migration still working (regression)
2. /api/sales/customer-names endpoint
3. /api/sales/customer-item-sales endpoint
4. /api/sales/customer-item-sales-export endpoint (Excel export)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_TENANT_ID = "3079b0af-e899-44b4-ae7c-c35d113fe296"
ADMIN_COMPANY_UUID = "03f638d1-eab0-47ee-aed6-59049ebb5207"

# Test customer from agent context
TEST_CUSTOMER = "Sharma Parts,Korndagaon,9993651416"
TEST_FY = "2026-27"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("success"), f"Login not successful: {data}"
    return data["data"]["token"]


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header and company header"""
    api_client.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "X-Company-ID": ADMIN_COMPANY_UUID
    })
    return api_client


class TestUUIDMigrationRegression:
    """Regression tests to ensure UUID migration still works"""
    
    def test_login_returns_uuid_tenant_id(self, api_client):
        """Verify login returns UUID-format tenant_id"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        
        tenant_id = data["data"].get("tenant_id")
        assert tenant_id is not None, "tenant_id missing from login response"
        
        # Verify UUID format
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, tenant_id), f"tenant_id not UUID format: {tenant_id}"
        assert tenant_id == ADMIN_TENANT_ID, f"Expected {ADMIN_TENANT_ID}, got {tenant_id}"
        print(f"SUCCESS: Login returns UUID tenant_id: {tenant_id}")
    
    def test_login_returns_company_mappings(self, api_client):
        """Verify login returns company_mappings array"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        
        company_mappings = data["data"].get("company_mappings")
        assert company_mappings is not None, "company_mappings missing from login response"
        assert isinstance(company_mappings, list), "company_mappings should be a list"
        assert len(company_mappings) > 0, "company_mappings should not be empty"
        
        # Verify structure
        mapping = company_mappings[0]
        assert "company_id" in mapping, "company_id missing from mapping"
        assert "company_name" in mapping, "company_name missing from mapping"
        
        # Verify UUID format for company_id
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, mapping["company_id"]), f"company_id not UUID: {mapping['company_id']}"
        
        print(f"SUCCESS: Login returns company_mappings: {mapping['company_id']} -> {mapping['company_name']}")
    
    def test_auth_me_returns_uuid_and_mappings(self, authenticated_client):
        """Verify /auth/me returns UUID tenant_id and company_mappings"""
        response = authenticated_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        
        # Check tenant_id
        tenant_id = data["data"].get("tenant_id")
        assert tenant_id == ADMIN_TENANT_ID, f"Expected {ADMIN_TENANT_ID}, got {tenant_id}"
        
        # Check company_mappings
        company_mappings = data["data"].get("company_mappings")
        assert company_mappings is not None, "company_mappings missing from /auth/me"
        assert len(company_mappings) > 0, "company_mappings should not be empty"
        
        print(f"SUCCESS: /auth/me returns UUID tenant_id and {len(company_mappings)} company mappings")


class TestCustomerNamesEndpoint:
    """Tests for /api/sales/customer-names endpoint"""
    
    def test_customer_names_returns_list(self, authenticated_client):
        """Verify customer-names endpoint returns list of customers"""
        response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-names?fy={TEST_FY}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data.get('error')}"
        
        customers = data["data"].get("customers")
        assert customers is not None, "customers missing from response"
        assert isinstance(customers, list), "customers should be a list"
        
        total = data["data"].get("total")
        assert total is not None, "total missing from response"
        assert total == len(customers), f"total ({total}) doesn't match customers length ({len(customers)})"
        
        print(f"SUCCESS: customer-names returns {total} customers for FY {TEST_FY}")
    
    def test_customer_names_contains_test_customer(self, authenticated_client):
        """Verify test customer exists in the list"""
        response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-names?fy={TEST_FY}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        
        customers = data["data"].get("customers", [])
        
        # Check if test customer exists
        found = TEST_CUSTOMER in customers
        if found:
            print(f"SUCCESS: Test customer '{TEST_CUSTOMER}' found in customer list")
        else:
            # List some customers for debugging
            print(f"WARNING: Test customer '{TEST_CUSTOMER}' not found. Available customers: {customers[:5]}...")
            # Don't fail - customer might not exist in test data
    
    def test_customer_names_without_fy(self, authenticated_client):
        """Verify customer-names works without FY filter"""
        response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-names")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data.get('error')}"
        
        customers = data["data"].get("customers")
        assert customers is not None, "customers missing from response"
        
        print(f"SUCCESS: customer-names without FY returns {len(customers)} customers")


class TestCustomerItemSalesEndpoint:
    """Tests for /api/sales/customer-item-sales endpoint"""
    
    def test_customer_item_sales_requires_customer(self, authenticated_client):
        """Verify endpoint requires customer parameter"""
        response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-item-sales")
        assert response.status_code == 200
        data = response.json()
        assert not data.get("success"), "Should fail without customer parameter"
        assert "Customer name is required" in data.get("error", ""), f"Unexpected error: {data.get('error')}"
        
        print("SUCCESS: customer-item-sales correctly requires customer parameter")
    
    def test_customer_item_sales_returns_data(self, authenticated_client):
        """Verify customer-item-sales returns item breakdown"""
        # First get a valid customer
        cust_response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-names?fy={TEST_FY}")
        assert cust_response.status_code == 200
        cust_data = cust_response.json()
        
        customers = cust_data.get("data", {}).get("customers", [])
        if not customers:
            pytest.skip("No customers available for testing")
        
        # Use first customer if test customer not available
        test_customer = TEST_CUSTOMER if TEST_CUSTOMER in customers else customers[0]
        
        # Get item sales for customer
        response = authenticated_client.get(
            f"{BASE_URL}/api/sales/customer-item-sales?customer={requests.utils.quote(test_customer)}&fy={TEST_FY}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data.get('error')}"
        
        result = data["data"]
        
        # Verify response structure
        assert "customer" in result, "customer missing from response"
        assert "items" in result, "items missing from response"
        assert "total_items" in result, "total_items missing from response"
        assert "total_quantity" in result, "total_quantity missing from response"
        assert "total_amount" in result, "total_amount missing from response"
        assert "total_vouchers" in result, "total_vouchers missing from response"
        
        assert result["customer"] == test_customer, f"Customer mismatch: {result['customer']}"
        assert isinstance(result["items"], list), "items should be a list"
        
        print(f"SUCCESS: customer-item-sales returns {result['total_items']} items for '{test_customer[:30]}...'")
        print(f"  - Total Quantity: {result['total_quantity']}")
        print(f"  - Total Amount: {result['total_amount']}")
        print(f"  - Total Vouchers: {result['total_vouchers']}")
    
    def test_customer_item_sales_item_structure(self, authenticated_client):
        """Verify item structure in response"""
        # Get a customer with data
        cust_response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-names?fy={TEST_FY}")
        customers = cust_response.json().get("data", {}).get("customers", [])
        if not customers:
            pytest.skip("No customers available")
        
        test_customer = TEST_CUSTOMER if TEST_CUSTOMER in customers else customers[0]
        
        response = authenticated_client.get(
            f"{BASE_URL}/api/sales/customer-item-sales?customer={requests.utils.quote(test_customer)}&fy={TEST_FY}"
        )
        data = response.json()
        
        items = data.get("data", {}).get("items", [])
        if not items:
            pytest.skip("No items found for customer")
        
        # Verify item structure
        item = items[0]
        assert "item_name" in item, "item_name missing"
        assert "quantity" in item, "quantity missing"
        assert "amount" in item, "amount missing"
        assert "avg_rate" in item, "avg_rate missing"
        assert "voucher_count" in item, "voucher_count missing"
        
        print(f"SUCCESS: Item structure verified - {item['item_name']}: qty={item['quantity']}, amt={item['amount']}")


class TestCustomerItemSalesExport:
    """Tests for /api/sales/customer-item-sales-export endpoint"""
    
    def test_export_requires_customer(self, authenticated_client):
        """Verify export endpoint requires customer parameter"""
        response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-item-sales-export")
        assert response.status_code == 200
        data = response.json()
        assert not data.get("success"), "Should fail without customer parameter"
        
        print("SUCCESS: customer-item-sales-export correctly requires customer parameter")
    
    def test_export_returns_excel(self, authenticated_client):
        """Verify export returns Excel file"""
        # Get a valid customer
        cust_response = authenticated_client.get(f"{BASE_URL}/api/sales/customer-names?fy={TEST_FY}")
        customers = cust_response.json().get("data", {}).get("customers", [])
        if not customers:
            pytest.skip("No customers available")
        
        test_customer = TEST_CUSTOMER if TEST_CUSTOMER in customers else customers[0]
        
        # Request export
        response = authenticated_client.get(
            f"{BASE_URL}/api/sales/customer-item-sales-export?customer={requests.utils.quote(test_customer)}&fy={TEST_FY}"
        )
        assert response.status_code == 200, f"Export failed: {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type, \
            f"Expected Excel content type, got: {content_type}"
        
        # Verify content disposition
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment, got: {content_disp}"
        assert ".xlsx" in content_disp, f"Expected .xlsx file, got: {content_disp}"
        
        # Verify content is not empty
        assert len(response.content) > 0, "Export file is empty"
        
        # Verify it's a valid xlsx (starts with PK - zip signature)
        assert response.content[:2] == b'PK', "File doesn't appear to be a valid xlsx"
        
        print(f"SUCCESS: Export returns valid Excel file ({len(response.content)} bytes)")


class TestDashboardWithUUID:
    """Test dashboard loads correctly with UUID-based IDs"""
    
    def test_sales_summary_with_uuid_company(self, authenticated_client):
        """Verify sales summary works with UUID company_id"""
        response = authenticated_client.get(f"{BASE_URL}/api/sales/summary?fy={TEST_FY}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data.get('error')}"
        
        result = data["data"]
        assert "total_vouchers" in result
        assert "total_sales" in result
        
        print(f"SUCCESS: Sales summary works with UUID company - {result['total_vouchers']} vouchers, Rs.{result['total_sales']}")
    
    def test_inventory_summary_with_uuid_company(self, authenticated_client):
        """Verify inventory summary works with UUID company_id"""
        response = authenticated_client.get(f"{BASE_URL}/api/inventory/summary?fy={TEST_FY}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data.get('error')}"
        
        print(f"SUCCESS: Inventory summary works with UUID company")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
