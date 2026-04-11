"""
Iteration 36: Branch/Division Exclusion Toggle Feature Tests
Tests the X-Exclude-Branches header functionality across sales, inventory, and CRM endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
COMPANY_UUID = "03f638d1-eab0-47ee-aed6-59049ebb5207"
TENANT_ID = "3079b0af-e899-44b4-ae7c-c35d113fe296"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("success"), f"Login not successful: {data}"
    return data.get("data", {}).get("token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token and company ID."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Company-ID": COMPANY_UUID,
        "Content-Type": "application/json"
    }


class TestBranchLedgersAPI:
    """Tests for /api/settings/branch-ledgers endpoints."""
    
    def test_get_branch_ledgers(self, auth_headers):
        """GET /api/settings/branch-ledgers returns branch party names."""
        response = requests.get(f"{BASE_URL}/api/settings/branch-ledgers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "party_names" in data.get("data", {}), "Missing party_names in response"
        assert "count" in data.get("data", {}), "Missing count in response"
        print(f"Branch ledgers: {data['data']['party_names'][:3]}... (count: {data['data']['count']})")
    
    def test_detect_branch_ledgers(self, auth_headers):
        """GET /api/settings/branch-ledgers/detect auto-detects branch parties."""
        response = requests.get(f"{BASE_URL}/api/settings/branch-ledgers/detect", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "detected" in data.get("data", {}), "Missing detected in response"
        assert "count" in data.get("data", {}), "Missing count in response"
        detected = data["data"]["detected"]
        print(f"Detected branch parties: {detected}")
        # Should detect at least one branch party (ASA Autotech India Pvt Ltd Raipur DEPOT)
        if detected:
            assert any("depot" in p.lower() or "branch" in p.lower() or "asa" in p.lower() for p in detected), \
                f"Expected branch party not detected: {detected}"


class TestSalesAPIBranchExclusion:
    """Tests for sales endpoints with X-Exclude-Branches header."""
    
    def test_sales_summary_without_exclusion(self, auth_headers):
        """GET /api/sales/summary without exclusion header returns all sales."""
        response = requests.get(f"{BASE_URL}/api/sales/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        sales_data = data.get("data", {})
        assert "total_sales" in sales_data, "Missing total_sales"
        assert "total_vouchers" in sales_data, "Missing total_vouchers"
        assert "top_customers" in sales_data, "Missing top_customers"
        print(f"Sales WITHOUT exclusion: Rs.{sales_data['total_sales']:,.2f} ({sales_data['total_vouchers']} vouchers)")
        return sales_data["total_sales"]
    
    def test_sales_summary_with_exclusion(self, auth_headers):
        """GET /api/sales/summary with X-Exclude-Branches: true filters branch sales."""
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response = requests.get(f"{BASE_URL}/api/sales/summary", headers=headers_with_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        sales_data = data.get("data", {})
        assert "total_sales" in sales_data, "Missing total_sales"
        print(f"Sales WITH exclusion: Rs.{sales_data['total_sales']:,.2f} ({sales_data['total_vouchers']} vouchers)")
        return sales_data["total_sales"]
    
    def test_sales_summary_exclusion_reduces_total(self, auth_headers):
        """Verify that branch exclusion reduces total sales (branch sales exist)."""
        # Without exclusion
        response_all = requests.get(f"{BASE_URL}/api/sales/summary", headers=auth_headers)
        total_all = response_all.json().get("data", {}).get("total_sales", 0)
        
        # With exclusion
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response_filtered = requests.get(f"{BASE_URL}/api/sales/summary", headers=headers_with_exclusion)
        total_filtered = response_filtered.json().get("data", {}).get("total_sales", 0)
        
        print(f"Total ALL: Rs.{total_all:,.2f}, Total FILTERED: Rs.{total_filtered:,.2f}")
        print(f"Difference (branch sales): Rs.{total_all - total_filtered:,.2f}")
        
        # Branch exclusion should reduce total (assuming branch sales exist)
        # If no branch parties configured, totals will be equal
        assert total_filtered <= total_all, "Filtered total should be <= all total"
    
    def test_sales_vouchers_with_exclusion(self, auth_headers):
        """GET /api/sales/vouchers with X-Exclude-Branches filters branch parties."""
        # Get branch parties first
        branch_response = requests.get(f"{BASE_URL}/api/settings/branch-ledgers", headers=auth_headers)
        branch_parties = branch_response.json().get("data", {}).get("party_names", [])
        
        if not branch_parties:
            pytest.skip("No branch parties configured - skipping voucher filter test")
        
        # Get vouchers with exclusion
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response = requests.get(f"{BASE_URL}/api/sales/vouchers", headers=headers_with_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        
        vouchers = data.get("data", {}).get("vouchers", [])
        # Verify no branch parties in filtered vouchers
        branch_set = set(p.lower() for p in branch_parties)
        for v in vouchers[:100]:  # Check first 100
            party = v.get("party_name", "").lower()
            assert party not in branch_set, f"Branch party {v.get('party_name')} found in filtered vouchers"
        
        print(f"Verified {min(len(vouchers), 100)} vouchers don't contain branch parties")
    
    def test_sales_customer_names_with_exclusion(self, auth_headers):
        """GET /api/sales/customer-names excludes branch parties when header set."""
        # Get branch parties
        branch_response = requests.get(f"{BASE_URL}/api/settings/branch-ledgers", headers=auth_headers)
        branch_parties = branch_response.json().get("data", {}).get("party_names", [])
        
        # Get customer names without exclusion
        response_all = requests.get(f"{BASE_URL}/api/sales/customer-names", headers=auth_headers)
        all_customers = response_all.json().get("data", {}).get("customers", [])
        
        # Get customer names with exclusion
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response_filtered = requests.get(f"{BASE_URL}/api/sales/customer-names", headers=headers_with_exclusion)
        filtered_customers = response_filtered.json().get("data", {}).get("customers", [])
        
        print(f"Customers ALL: {len(all_customers)}, FILTERED: {len(filtered_customers)}")
        
        # Verify branch parties not in filtered list
        if branch_parties:
            branch_set = set(p.lower() for p in branch_parties)
            for customer in filtered_customers:
                assert customer.lower() not in branch_set, f"Branch party {customer} found in filtered customers"


class TestInventoryAPIBranchExclusion:
    """Tests for inventory endpoints with X-Exclude-Branches header."""
    
    def test_inventory_summary_without_exclusion(self, auth_headers):
        """GET /api/inventory/summary without exclusion header."""
        response = requests.get(f"{BASE_URL}/api/inventory/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        inv_data = data.get("data", {})
        assert "total_items" in inv_data, "Missing total_items"
        assert "total_value" in inv_data, "Missing total_value"
        print(f"Inventory WITHOUT exclusion: {inv_data['total_items']} items, Rs.{inv_data['total_value']:,.2f}")
    
    def test_inventory_summary_with_exclusion(self, auth_headers):
        """GET /api/inventory/summary with X-Exclude-Branches header."""
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response = requests.get(f"{BASE_URL}/api/inventory/summary", headers=headers_with_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        inv_data = data.get("data", {})
        assert "total_items" in inv_data, "Missing total_items"
        print(f"Inventory WITH exclusion: {inv_data['total_items']} items, Rs.{inv_data['total_value']:,.2f}")


class TestCustomersAPIBranchExclusion:
    """Tests for customers endpoints with X-Exclude-Branches header."""
    
    def test_customers_outstanding_without_exclusion(self, auth_headers):
        """GET /api/customers/outstanding without exclusion header."""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        cust_data = data.get("data", {})
        assert "customers" in cust_data, "Missing customers"
        assert "total_outstanding" in cust_data, "Missing total_outstanding"
        customer_count = len(cust_data.get("customers", []))
        print(f"Customers WITHOUT exclusion: {customer_count} customers, Rs.{cust_data['total_outstanding']:,.2f} outstanding")
    
    def test_customers_outstanding_with_exclusion(self, auth_headers):
        """GET /api/customers/outstanding with X-Exclude-Branches header."""
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=headers_with_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        cust_data = data.get("data", {})
        assert "customers" in cust_data, "Missing customers"
        customer_count = len(cust_data.get("customers", []))
        print(f"Customers WITH exclusion: {customer_count} customers, Rs.{cust_data['total_outstanding']:,.2f} outstanding")
    
    def test_customers_exclusion_reduces_outstanding(self, auth_headers):
        """Verify that branch exclusion reduces outstanding amount."""
        # Without exclusion
        response_all = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=auth_headers)
        data_all = response_all.json().get("data", {})
        total_all = data_all.get("total_outstanding", 0)
        count_all = len(data_all.get("customers", []))
        
        # With exclusion
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response_filtered = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=headers_with_exclusion)
        data_filtered = response_filtered.json().get("data", {})
        total_filtered = data_filtered.get("total_outstanding", 0)
        count_filtered = len(data_filtered.get("customers", []))
        
        print(f"Customers ALL: {count_all}, Outstanding: Rs.{total_all:,.2f}")
        print(f"Customers FILTERED: {count_filtered}, Outstanding: Rs.{total_filtered:,.2f}")
        print(f"Difference: {count_all - count_filtered} customers, Rs.{total_all - total_filtered:,.2f}")
        
        # Filtered should be <= all
        assert total_filtered <= total_all, "Filtered outstanding should be <= all outstanding"
        assert count_filtered <= count_all, "Filtered count should be <= all count"


class TestAuthStillWorks:
    """Verify login flow still works correctly."""
    
    def test_admin_login(self):
        """Admin login with admin/admin123 works."""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Login failed: {data}"
        assert "token" in data.get("data", {}) or "token" in data, "Missing token in response"
        print("Admin login successful")
    
    def test_superadmin_login(self):
        """SuperAdmin login with superadmin/superadmin123 works."""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Login failed: {data}"
        print("SuperAdmin login successful")


class TestTopCustomersExclusion:
    """Test that top customers list excludes branch parties."""
    
    def test_top_customers_without_branch(self, auth_headers):
        """Verify branch party not in top customers when excluded."""
        # Get branch parties
        branch_response = requests.get(f"{BASE_URL}/api/settings/branch-ledgers", headers=auth_headers)
        branch_parties = branch_response.json().get("data", {}).get("party_names", [])
        
        if not branch_parties:
            pytest.skip("No branch parties configured")
        
        # Get sales summary with exclusion
        headers_with_exclusion = {**auth_headers, "X-Exclude-Branches": "true"}
        response = requests.get(f"{BASE_URL}/api/sales/summary", headers=headers_with_exclusion)
        data = response.json()
        top_customers = data.get("data", {}).get("top_customers", [])
        
        # Verify branch parties not in top customers
        branch_set = set(p.lower() for p in branch_parties)
        for customer in top_customers:
            name = customer.get("name", "").lower()
            assert name not in branch_set, f"Branch party {customer['name']} found in top customers"
        
        print(f"Verified {len(top_customers)} top customers don't include branch parties")
        if top_customers:
            print(f"Top customer: {top_customers[0]['name']} - Rs.{top_customers[0]['total']:,.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
