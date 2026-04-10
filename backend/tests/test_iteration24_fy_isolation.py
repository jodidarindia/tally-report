"""
Iteration 24 Tests: FY Customer Mapping Isolation, Item-wise Sales Tab, Security Audit
Tests:
1. Item-wise Sales tab - items_sold field in performance-detailed endpoint
2. FY Mapping Isolation - changing FY 2026-27 mapping must NOT affect FY 2025-26
3. Security audit - tenant_id/company_id isolation on Insights and Salesman endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "admin123"}
TEST_ADMIN_CREDS = {"username": "test_admin", "password": "test123"}
COMPANY_NAME = "ASA AUTOTECH INDIA PRIVATE LIMITED"


@pytest.fixture(scope="module")
def admin_session():
    """Login as admin and get session with company selected."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    resp = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    assert data.get("success"), f"Admin login not successful: {data}"
    
    token = data.get("data", {}).get("token") or data.get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    
    # Get companies and select ASA AUTOTECH
    companies_resp = session.get(f"{BASE_URL}/api/companies")
    if companies_resp.status_code == 200:
        companies = companies_resp.json().get("data", {}).get("companies", [])
        for c in companies:
            if COMPANY_NAME in c.get("company_name", ""):
                session.post(f"{BASE_URL}/api/companies/select", json={"company_id": c.get("company_id")})
                break
    
    return session


@pytest.fixture(scope="module")
def test_admin_session():
    """Login as test_admin (different tenant) and get session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    resp = session.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN_CREDS)
    assert resp.status_code == 200, f"Test admin login failed: {resp.text}"
    data = resp.json()
    assert data.get("success"), f"Test admin login not successful: {data}"
    
    token = data.get("data", {}).get("token") or data.get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session


class TestItemWiseSalesTab:
    """Test Item-wise Sales tab functionality - items_sold in performance-detailed endpoint."""
    
    def test_performance_detailed_returns_items_sold(self, admin_session):
        """GET /api/salesman/performance-detailed should return items_sold array for each salesman."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success"), f"API not successful: {data}"
        
        salesmen = data.get("data", {}).get("salesman", [])
        assert len(salesmen) > 0, "No salesmen returned"
        
        # Find Ankit
        ankit = next((s for s in salesmen if s.get("salesman_name") == "Ankit"), None)
        assert ankit is not None, "Ankit salesman not found"
        
        # Check items_sold field exists
        items_sold = ankit.get("items_sold", [])
        assert isinstance(items_sold, list), "items_sold should be a list"
        print(f"Ankit has {len(items_sold)} items sold")
    
    def test_ankit_has_approximately_32_items(self, admin_session):
        """Ankit should have ~32 items with data for FY 2025-26."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26")
        assert resp.status_code == 200
        
        data = resp.json()
        salesmen = data.get("data", {}).get("salesman", [])
        ankit = next((s for s in salesmen if s.get("salesman_name") == "Ankit"), None)
        assert ankit is not None
        
        items_sold = ankit.get("items_sold", [])
        # Should have approximately 32 items (allow some variance)
        assert len(items_sold) >= 25, f"Expected ~32 items, got {len(items_sold)}"
        assert len(items_sold) <= 40, f"Expected ~32 items, got {len(items_sold)}"
        print(f"Ankit has {len(items_sold)} items (expected ~32)")
    
    def test_items_sold_has_required_fields(self, admin_session):
        """Each item in items_sold should have item_name, total_quantity, total_revenue, transaction_count."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26")
        assert resp.status_code == 200
        
        data = resp.json()
        salesmen = data.get("data", {}).get("salesman", [])
        ankit = next((s for s in salesmen if s.get("salesman_name") == "Ankit"), None)
        assert ankit is not None
        
        items_sold = ankit.get("items_sold", [])
        assert len(items_sold) > 0, "No items sold"
        
        # Check first item has required fields
        first_item = items_sold[0]
        assert "item_name" in first_item, "item_name field missing"
        assert "total_quantity" in first_item, "total_quantity field missing"
        assert "total_revenue" in first_item, "total_revenue field missing"
        assert "transaction_count" in first_item, "transaction_count field missing"
        
        print(f"First item: {first_item.get('item_name')} - Qty: {first_item.get('total_quantity')}, Revenue: {first_item.get('total_revenue')}")


class TestFYMappingIsolation:
    """Test FY customer mapping isolation - changing FY 2026-27 must NOT affect FY 2025-26."""
    
    def test_fy_2025_26_is_locked(self, admin_session):
        """FY 2025-26 should be locked (ended Mar 31, 2026)."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/master?fy=2025-26")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        assert data.get("data", {}).get("fy_locked") == True, "FY 2025-26 should be locked"
        print("FY 2025-26 is correctly locked")
    
    def test_fy_2026_27_is_not_locked(self, admin_session):
        """FY 2026-27 should NOT be locked (current FY)."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/master?fy=2026-27")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        assert data.get("data", {}).get("fy_locked") == False, "FY 2026-27 should NOT be locked"
        print("FY 2026-27 is correctly not locked")
    
    def test_post_to_locked_fy_fails(self, admin_session):
        """POST /api/salesman/master with fy=2025-26 should fail (FY locked)."""
        payload = {
            "salesman_name": "Ankit",
            "customers": [],
            "monthly_target": 1000000,
            "fy": "2025-26"
        }
        resp = admin_session.post(f"{BASE_URL}/api/salesman/master", json=payload)
        assert resp.status_code == 200  # API returns 200 with error in body
        
        data = resp.json()
        assert data.get("success") == False, "Should fail for locked FY"
        assert "ended" in data.get("error", "").lower() or "locked" in data.get("error", "").lower(), \
            f"Error should mention FY ended/locked: {data.get('error')}"
        print(f"Correctly rejected: {data.get('error')}")
    
    def test_get_ankit_fy_2025_26_has_customers(self, admin_session):
        """GET /api/salesman/master?fy=2025-26 should return Ankit with non-empty customers."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/master?fy=2025-26")
        assert resp.status_code == 200
        
        data = resp.json()
        salesmen = data.get("data", {}).get("salesmen", [])
        ankit = next((s for s in salesmen if s.get("salesman_name") == "Ankit"), None)
        assert ankit is not None, "Ankit not found in FY 2025-26"
        
        customers = ankit.get("customers", [])
        assert len(customers) > 0, f"Ankit should have customers in FY 2025-26, got: {customers}"
        print(f"Ankit FY 2025-26 customers: {customers}")
        
        # Store for later comparison
        return customers
    
    def test_fy_isolation_save_empty_customers_2026_27_preserves_2025_26(self, admin_session):
        """
        Critical FY Isolation Test:
        1. Get Ankit's customers for FY 2025-26 (should have 'Dinesh Automobiles' or similar)
        2. Save Ankit with empty customers for FY 2026-27
        3. Verify FY 2025-26 still has the original customers
        """
        # Step 1: Get FY 2025-26 customers
        resp_2025 = admin_session.get(f"{BASE_URL}/api/salesman/master?fy=2025-26")
        assert resp_2025.status_code == 200
        data_2025 = resp_2025.json()
        salesmen_2025 = data_2025.get("data", {}).get("salesmen", [])
        ankit_2025 = next((s for s in salesmen_2025 if s.get("salesman_name") == "Ankit"), None)
        assert ankit_2025 is not None
        
        original_customers_2025 = ankit_2025.get("customers", [])
        print(f"Original FY 2025-26 customers: {original_customers_2025}")
        
        # Step 2: Save Ankit with empty customers for FY 2026-27
        payload = {
            "salesman_name": "Ankit",
            "customers": [],  # Empty customers for 2026-27
            "monthly_target": 1000000,
            "quarterly_target": 3000000,
            "fy": "2026-27"
        }
        resp_save = admin_session.post(f"{BASE_URL}/api/salesman/master", json=payload)
        assert resp_save.status_code == 200
        save_data = resp_save.json()
        assert save_data.get("success"), f"Save failed: {save_data}"
        print(f"Saved Ankit for FY 2026-27 with empty customers")
        
        # Step 3: Verify FY 2025-26 still has original customers
        resp_verify = admin_session.get(f"{BASE_URL}/api/salesman/master?fy=2025-26")
        assert resp_verify.status_code == 200
        verify_data = resp_verify.json()
        salesmen_verify = verify_data.get("data", {}).get("salesmen", [])
        ankit_verify = next((s for s in salesmen_verify if s.get("salesman_name") == "Ankit"), None)
        assert ankit_verify is not None
        
        verified_customers_2025 = ankit_verify.get("customers", [])
        print(f"Verified FY 2025-26 customers after save: {verified_customers_2025}")
        
        # CRITICAL ASSERTION: FY 2025-26 customers should NOT be affected
        assert len(verified_customers_2025) == len(original_customers_2025), \
            f"FY 2025-26 customers changed! Original: {original_customers_2025}, After: {verified_customers_2025}"
        
        # Step 4: Verify FY 2026-27 has empty customers
        resp_2026 = admin_session.get(f"{BASE_URL}/api/salesman/master?fy=2026-27")
        assert resp_2026.status_code == 200
        data_2026 = resp_2026.json()
        salesmen_2026 = data_2026.get("data", {}).get("salesmen", [])
        ankit_2026 = next((s for s in salesmen_2026 if s.get("salesman_name") == "Ankit"), None)
        assert ankit_2026 is not None
        
        customers_2026 = ankit_2026.get("customers", [])
        print(f"FY 2026-27 customers: {customers_2026}")
        assert len(customers_2026) == 0, f"FY 2026-27 should have empty customers, got: {customers_2026}"
        
        print("FY ISOLATION TEST PASSED: FY 2025-26 customers preserved after FY 2026-27 update")


class TestSecurityTenantIsolation:
    """Security audit - verify tenant_id/company_id isolation on Insights and Salesman endpoints."""
    
    def test_insights_customer_lifecycle_tenant_isolation(self, test_admin_session):
        """GET /api/insights/customer-lifecycle with test_admin token should return zero customers."""
        resp = test_admin_session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        active = data.get("data", {}).get("active", [])
        inactive = data.get("data", {}).get("inactive", [])
        lost = data.get("data", {}).get("lost", [])
        
        total = len(active) + len(inactive) + len(lost)
        assert total == 0, f"test_admin should see 0 customers, got {total}"
        print(f"Security OK: test_admin sees 0 customers in customer-lifecycle")
    
    def test_insights_concentration_risk_tenant_isolation(self, test_admin_session):
        """GET /api/insights/concentration-risk with test_admin token should return zero data."""
        resp = test_admin_session.get(f"{BASE_URL}/api/insights/concentration-risk")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        customers = data.get("data", {}).get("customers", [])
        risk_level = data.get("data", {}).get("risk_level", "")
        
        assert len(customers) == 0 or risk_level == "no_data", \
            f"test_admin should see 0 customers or no_data, got {len(customers)} customers, risk: {risk_level}"
        print(f"Security OK: test_admin sees 0 customers in concentration-risk (risk_level: {risk_level})")
    
    def test_salesman_performance_detailed_tenant_isolation(self, test_admin_session):
        """GET /api/salesman/performance-detailed with test_admin token should return zero salesmen."""
        resp = test_admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        salesmen = data.get("data", {}).get("salesman", [])
        assert len(salesmen) == 0, f"test_admin should see 0 salesmen, got {len(salesmen)}"
        print(f"Security OK: test_admin sees 0 salesmen in performance-detailed")
    
    def test_salesman_master_tenant_isolation(self, test_admin_session):
        """GET /api/salesman/master with test_admin token should return zero salesmen."""
        resp = test_admin_session.get(f"{BASE_URL}/api/salesman/master")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        salesmen = data.get("data", {}).get("salesmen", [])
        assert len(salesmen) == 0, f"test_admin should see 0 salesmen, got {len(salesmen)}"
        print(f"Security OK: test_admin sees 0 salesmen in master")
    
    def test_admin_has_data_in_insights(self, admin_session):
        """Verify admin with ASA AUTOTECH company has data in insights endpoints."""
        # Customer lifecycle
        resp1 = admin_session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        assert resp1.status_code == 200
        data1 = resp1.json()
        total_customers = len(data1.get("data", {}).get("active", [])) + \
                         len(data1.get("data", {}).get("inactive", [])) + \
                         len(data1.get("data", {}).get("lost", []))
        assert total_customers > 0, "Admin should see customers"
        print(f"Admin sees {total_customers} customers in customer-lifecycle")
        
        # Concentration risk
        resp2 = admin_session.get(f"{BASE_URL}/api/insights/concentration-risk")
        assert resp2.status_code == 200
        data2 = resp2.json()
        customers = data2.get("data", {}).get("customers", [])
        assert len(customers) > 0, "Admin should see customers in concentration-risk"
        print(f"Admin sees {len(customers)} customers in concentration-risk")
    
    def test_admin_has_data_in_salesman(self, admin_session):
        """Verify admin with ASA AUTOTECH company has data in salesman endpoints."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26")
        assert resp.status_code == 200
        
        data = resp.json()
        salesmen = data.get("data", {}).get("salesman", [])
        assert len(salesmen) > 0, "Admin should see salesmen"
        print(f"Admin sees {len(salesmen)} salesmen in performance-detailed")


class TestDurationToggle:
    """Test duration toggle on Performance tab (Monthly/Quarterly/Annual)."""
    
    def test_monthly_duration(self, admin_session):
        """GET /api/salesman/performance-detailed?duration=monthly returns monthly breakdown."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=monthly")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        periods = data.get("data", {}).get("periods", {})
        months = periods.get("months", [])
        assert len(months) > 0, "Should have months in periods"
        print(f"Monthly periods: {months}")
    
    def test_quarterly_duration(self, admin_session):
        """GET /api/salesman/performance-detailed?duration=quarterly returns quarterly breakdown."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=quarterly")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        periods = data.get("data", {}).get("periods", {})
        quarters = periods.get("quarters", [])
        assert len(quarters) > 0, "Should have quarters in periods"
        print(f"Quarterly periods: {quarters}")
    
    def test_annual_duration(self, admin_session):
        """GET /api/salesman/performance-detailed?duration=annual returns annual totals."""
        resp = admin_session.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=annual")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("success")
        
        salesmen = data.get("data", {}).get("salesman", [])
        assert len(salesmen) > 0
        
        # Check annual data exists
        ankit = next((s for s in salesmen if s.get("salesman_name") == "Ankit"), None)
        assert ankit is not None
        assert ankit.get("achieved_amount", 0) > 0, "Should have annual achieved amount"
        print(f"Annual achieved: {ankit.get('achieved_amount')}")


class TestExcelExport:
    """Test Excel export functionality."""
    
    def test_export_excel_returns_valid_file(self, admin_session):
        """GET /api/salesman/export returns valid xlsx file."""
        resp = admin_session.get(
            f"{BASE_URL}/api/salesman/export?salesman_name=Ankit&fy=2025-26&duration=monthly"
        )
        assert resp.status_code == 200
        
        # Check content type
        content_type = resp.headers.get("content-type", "")
        assert "spreadsheet" in content_type or "octet-stream" in content_type, \
            f"Expected spreadsheet content type, got: {content_type}"
        
        # Check content disposition
        content_disp = resp.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment, got: {content_disp}"
        assert ".xlsx" in content_disp, f"Expected .xlsx file, got: {content_disp}"
        
        # Check file size
        assert len(resp.content) > 1000, f"Excel file too small: {len(resp.content)} bytes"
        print(f"Excel export successful: {len(resp.content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
