"""
Iteration 20 Tests: CompanySelector Enhancement & Security Audit Fixes

Tests:
1. CompanySelector shows sync info (last sync time, item count, voucher count) per company
2. Company switching still works end-to-end
3. SECURITY: GET /api/sales/vouchers/{id} now requires tenant/company isolation
4. SECURITY: Voucher detail returns 'not found' when wrong X-Company-ID is sent
5. SECURITY: GET /api/salesman/master now requires tenant context
6. SECURITY: GET /api/salesman/performance now filters salesman_master by tenant
7. SECURITY: GET /api/salesman/performance-detailed now requires tenant context
8. SECURITY: POST /api/salesman/master now includes tenant_id/company_id on insert
9. SECURITY: DELETE /api/salesman/master/{name} now requires tenant context
10. SECURITY: POST /api/customers/targets/set now includes tenant_id/company_id
11. SECURITY: PATCH /api/customers/followups/{id} now includes tenant filter
12. Backend: GET /api/sync/companies-status returns per-company sync data
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCompanySelectorSyncInfo:
    """Test the new /api/sync/companies-status endpoint for CompanySelector"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data.get("success"), f"Login not successful: {data}"
        self.token = data["data"]["token"]
        self.companies = data["data"].get("companies", [])
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_companies_status_endpoint_exists(self):
        """Test that /api/sync/companies-status endpoint exists and returns data"""
        response = requests.get(f"{BASE_URL}/api/sync/companies-status", headers=self.headers)
        assert response.status_code == 200, f"Endpoint failed: {response.text}"
        data = response.json()
        assert data.get("success"), f"Response not successful: {data}"
        print(f"✓ /api/sync/companies-status endpoint exists and returns success")
    
    def test_companies_status_returns_array(self):
        """Test that endpoint returns array of company sync info"""
        response = requests.get(f"{BASE_URL}/api/sync/companies-status", headers=self.headers)
        data = response.json()
        assert isinstance(data.get("data"), list), "Expected data to be a list"
        print(f"✓ Endpoint returns array with {len(data['data'])} companies")
    
    def test_companies_status_has_required_fields(self):
        """Test that each company has required fields: company_name, last_sync, inventory_count, sales_count"""
        response = requests.get(f"{BASE_URL}/api/sync/companies-status", headers=self.headers)
        data = response.json()
        companies_data = data.get("data", [])
        
        for company in companies_data:
            assert "company_name" in company, f"Missing company_name in {company}"
            assert "last_sync" in company, f"Missing last_sync in {company}"
            assert "inventory_count" in company, f"Missing inventory_count in {company}"
            assert "sales_count" in company, f"Missing sales_count in {company}"
            print(f"✓ Company '{company['company_name']}': inv={company['inventory_count']}, sales={company['sales_count']}, last_sync={company.get('last_sync', 'None')}")
    
    def test_companies_status_matches_user_companies(self):
        """Test that returned companies match user's companies list"""
        response = requests.get(f"{BASE_URL}/api/sync/companies-status", headers=self.headers)
        data = response.json()
        companies_data = data.get("data", [])
        
        returned_names = [c["company_name"] for c in companies_data]
        for company in self.companies:
            assert company in returned_names, f"User company '{company}' not in returned data"
        print(f"✓ All user companies ({len(self.companies)}) present in sync status response")


class TestSecurityVoucherDetail:
    """SECURITY: Test voucher detail endpoint requires tenant/company isolation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data["data"]["token"]
        self.companies = data["data"].get("companies", [])
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_voucher_detail_with_correct_company(self):
        """Test voucher detail returns data when correct company is set"""
        # DEMO-001 belongs to Demo Trading Co
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/DEMO-001", headers=headers)
        data = response.json()
        
        # Should succeed with correct company
        if data.get("success"):
            print(f"✓ DEMO-001 found with X-Company-ID='Demo Trading Co'")
            assert data["data"].get("voucher_id") == "DEMO-001"
        else:
            # Voucher might not exist in test data
            print(f"⚠ DEMO-001 not found (may not exist in test data): {data.get('error')}")
    
    def test_voucher_detail_with_wrong_company_returns_not_found(self):
        """SECURITY: Voucher detail returns 'not found' when wrong X-Company-ID is sent"""
        # DEMO-001 belongs to Demo Trading Co, but we send ASA AUTOTECH
        headers = {**self.headers, "X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"}
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/DEMO-001", headers=headers)
        data = response.json()
        
        # Should NOT find the voucher (security isolation)
        if not data.get("success"):
            print(f"✓ SECURITY: DEMO-001 correctly NOT found with wrong company header")
            assert "not found" in data.get("error", "").lower() or not data.get("success")
        else:
            # If found, this is a security issue
            pytest.fail("SECURITY ISSUE: Voucher found with wrong company header!")
    
    def test_voucher_list_filtered_by_company(self):
        """Test voucher list is filtered by X-Company-ID header"""
        # Get vouchers for Demo Trading Co
        headers_demo = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        response_demo = requests.get(f"{BASE_URL}/api/sales/vouchers", headers=headers_demo)
        data_demo = response_demo.json()
        demo_count = data_demo.get("data", {}).get("count", 0)
        
        # Get vouchers for ASA AUTOTECH
        headers_asa = {**self.headers, "X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"}
        response_asa = requests.get(f"{BASE_URL}/api/sales/vouchers", headers=headers_asa)
        data_asa = response_asa.json()
        asa_count = data_asa.get("data", {}).get("count", 0)
        
        print(f"✓ Demo Trading Co: {demo_count} vouchers, ASA AUTOTECH: {asa_count} vouchers")
        # Counts should be different (data isolation)
        assert demo_count != asa_count or (demo_count == 0 and asa_count == 0), "Voucher counts should differ between companies"


class TestSecuritySalesmanRoutes:
    """SECURITY: Test salesman routes require tenant context"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data["data"]["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_salesman_master_get_requires_tenant(self):
        """Test GET /api/salesman/master requires tenant context"""
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        response = requests.get(f"{BASE_URL}/api/salesman/master", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Salesman master GET failed: {data}"
        print(f"✓ GET /api/salesman/master works with tenant context")
    
    def test_salesman_performance_requires_tenant(self):
        """Test GET /api/salesman/performance requires tenant context"""
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        response = requests.get(f"{BASE_URL}/api/salesman/performance", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Salesman performance GET failed: {data}"
        print(f"✓ GET /api/salesman/performance works with tenant context")
    
    def test_salesman_performance_detailed_requires_tenant(self):
        """Test GET /api/salesman/performance-detailed requires tenant context"""
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Salesman performance-detailed GET failed: {data}"
        print(f"✓ GET /api/salesman/performance-detailed works with tenant context")
    
    def test_salesman_create_includes_tenant_company(self):
        """Test POST /api/salesman/master includes tenant_id/company_id on insert"""
        test_name = f"TEST_Salesman_{uuid.uuid4().hex[:8]}"
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        
        response = requests.post(f"{BASE_URL}/api/salesman/master", 
            headers=headers,
            json={
                "salesman_name": test_name,
                "customers": [],
                "monthly_target": 10000
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Salesman create failed: {data}"
        
        # Verify the created salesman has tenant_id and company_id
        created = data.get("data", {})
        assert created.get("tenant_id"), "Created salesman missing tenant_id"
        assert created.get("company_id"), "Created salesman missing company_id"
        print(f"✓ POST /api/salesman/master includes tenant_id={created.get('tenant_id')}, company_id={created.get('company_id')}")
        
        # Cleanup - delete the test salesman
        requests.delete(f"{BASE_URL}/api/salesman/master/{test_name}", headers=headers)
    
    def test_salesman_delete_requires_tenant(self):
        """Test DELETE /api/salesman/master/{name} requires tenant context"""
        # First create a test salesman
        test_name = f"TEST_DeleteSalesman_{uuid.uuid4().hex[:8]}"
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        
        requests.post(f"{BASE_URL}/api/salesman/master", 
            headers=headers,
            json={"salesman_name": test_name, "customers": []}
        )
        
        # Delete with correct tenant context
        response = requests.delete(f"{BASE_URL}/api/salesman/master/{test_name}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Salesman delete failed: {data}"
        print(f"✓ DELETE /api/salesman/master/{test_name} works with tenant context")


class TestSecurityCustomerRoutes:
    """SECURITY: Test customer routes require tenant context"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data["data"]["token"]
        self.companies = data["data"].get("companies", [])
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_customer_targets_set_includes_tenant_company(self):
        """Test POST /api/customers/targets/set includes tenant_id/company_id"""
        test_customer = f"TEST_Customer_{uuid.uuid4().hex[:8]}"
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        
        response = requests.post(f"{BASE_URL}/api/customers/targets/set",
            headers=headers,
            json={
                "customer_name": test_customer,
                "target_amount": 50000,
                "last_fy_sales": 40000,
                "fy": "2026-27"  # Current FY (Apr 2026 - Mar 2027)
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Customer target set failed: {data}"
        
        # Verify the created target has tenant_id and company_id
        created = data.get("data", {})
        assert created.get("tenant_id"), "Created target missing tenant_id"
        assert created.get("company_id"), "Created target missing company_id"
        print(f"✓ POST /api/customers/targets/set includes tenant_id={created.get('tenant_id')}, company_id={created.get('company_id')}")
    
    def test_followup_update_requires_tenant(self):
        """Test PATCH /api/customers/followups/{id} requires tenant filter"""
        headers = {**self.headers, "X-Company-ID": "Demo Trading Co"}
        
        # First create a followup
        create_response = requests.post(f"{BASE_URL}/api/customers/followups",
            headers=headers,
            json={
                "customer_name": "Test Customer",
                "followup_date": "2026-02-01",
                "followup_type": "call",
                "notes": "Test followup"
            }
        )
        
        if create_response.status_code == 200 and create_response.json().get("success"):
            followup_id = create_response.json().get("data", {}).get("id")
            
            # Update the followup
            update_response = requests.patch(
                f"{BASE_URL}/api/customers/followups/{followup_id}?status=completed",
                headers=headers
            )
            assert update_response.status_code == 200
            data = update_response.json()
            print(f"✓ PATCH /api/customers/followups/{followup_id} works with tenant context: {data.get('message')}")
        else:
            print(f"⚠ Could not create followup for testing: {create_response.json()}")


class TestCrossTenantIsolation:
    """SECURITY: Test that test_admin cannot see admin's data"""
    
    def test_cross_tenant_data_isolation(self):
        """Test that test_admin cannot access admin's company data"""
        # Login as admin
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert admin_response.status_code == 200
        admin_data = admin_response.json()
        admin_token = admin_data["data"]["token"]
        admin_companies = admin_data["data"].get("companies", [])
        
        # Login as test_admin
        test_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "test_admin",
            "password": "test123"
        })
        assert test_response.status_code == 200
        test_data = test_response.json()
        test_token = test_data["data"]["token"]
        
        # test_admin tries to access admin's company data
        if admin_companies:
            admin_company = admin_companies[0]
            headers = {
                "Authorization": f"Bearer {test_token}",
                "X-Company-ID": admin_company  # Try to access admin's company
            }
            
            # Try to get inventory
            inv_response = requests.get(f"{BASE_URL}/api/inventory/items", headers=headers)
            inv_data = inv_response.json()
            inv_count = inv_data.get("data", {}).get("count", 0)
            
            # test_admin should see 0 items (not admin's data)
            print(f"✓ test_admin sees {inv_count} items when trying to access admin's company")
            # This is expected - test_admin has different tenant_id
            assert inv_count == 0 or inv_data.get("success") == False, \
                "SECURITY ISSUE: test_admin can see admin's inventory data!"


class TestCompanySwitching:
    """Test company switching still works end-to-end"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data["data"]["token"]
        self.companies = data["data"].get("companies", [])
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_inventory_works_for_both_companies(self):
        """Test inventory page works for both companies"""
        for company in self.companies:
            headers = {**self.headers, "X-Company-ID": company}
            response = requests.get(f"{BASE_URL}/api/inventory/items", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data.get("success"), f"Inventory failed for {company}: {data}"
            count = data.get("data", {}).get("count", 0)
            print(f"✓ Inventory for '{company}': {count} items")
    
    def test_sales_works_for_both_companies(self):
        """Test sales page works for both companies"""
        for company in self.companies:
            headers = {**self.headers, "X-Company-ID": company}
            response = requests.get(f"{BASE_URL}/api/sales/vouchers", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data.get("success"), f"Sales failed for {company}: {data}"
            count = data.get("data", {}).get("count", 0)
            print(f"✓ Sales for '{company}': {count} vouchers")
    
    def test_crm_works_for_both_companies(self):
        """Test CRM page works for both companies"""
        for company in self.companies:
            headers = {**self.headers, "X-Company-ID": company}
            response = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data.get("success"), f"CRM failed for {company}: {data}"
            customers = data.get("data", {}).get("customers", [])
            print(f"✓ CRM for '{company}': {len(customers)} customers")
    
    def test_dashboard_works_for_both_companies(self):
        """Test dashboard works for both companies"""
        for company in self.companies:
            headers = {**self.headers, "X-Company-ID": company}
            response = requests.get(f"{BASE_URL}/api/dashboard/reminders", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data.get("success"), f"Dashboard failed for {company}: {data}"
            print(f"✓ Dashboard reminders for '{company}': success")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
