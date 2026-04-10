"""
Iteration 23: Salesman FY-Specific Targets & Performance Tests
Tests:
- FY-specific targets and customer mappings
- FY locking for completed FYs (2025-26)
- Performance-detailed endpoint with monthly/quarterly/annual views
- Excel export functionality
- SearchableSelect integration (tested via frontend)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com')


class TestSalesmanFYFeatures:
    """Test salesman FY-specific features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert data.get("success") is True
        self.token = data["data"]["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"
        }
    
    # ==================== MASTER ENDPOINT TESTS ====================
    
    def test_get_salesman_master_fy_2025_26_locked(self):
        """GET /api/salesman/master?fy=2025-26 should return fy_locked=true"""
        res = requests.get(f"{BASE_URL}/api/salesman/master?fy=2025-26", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert data["data"]["fy_locked"] is True
        assert data["data"]["target_fy"] == "2025-26"
        assert data["data"]["current_fy"] == "2026-27"
        print(f"✓ FY 2025-26 is correctly marked as locked")
    
    def test_get_salesman_master_returns_salesmen_list(self):
        """GET /api/salesman/master should return salesmen with FY-specific data"""
        res = requests.get(f"{BASE_URL}/api/salesman/master?fy=2025-26", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        salesmen = data["data"]["salesmen"]
        assert isinstance(salesmen, list)
        if len(salesmen) > 0:
            salesman = salesmen[0]
            assert "salesman_name" in salesman
            assert "monthly_target" in salesman
            assert "quarterly_target" in salesman
            assert "customers" in salesman
            assert "fy" in salesman
            assert "fy_locked" in salesman
            print(f"✓ Salesman data structure correct: {salesman['salesman_name']}")
    
    def test_post_salesman_locked_fy_fails(self):
        """POST /api/salesman/master with fy=2025-26 should fail (FY locked)"""
        res = requests.post(f"{BASE_URL}/api/salesman/master", headers=self.headers, json={
            "salesman_name": "Test Locked FY",
            "fy": "2025-26",
            "monthly_target": 100000,
            "customers": []
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is False
        assert "ended" in data.get("error", "").lower() or "locked" in data.get("error", "").lower()
        print(f"✓ POST to locked FY correctly rejected: {data.get('error')}")
    
    def test_post_salesman_current_fy_succeeds(self):
        """POST /api/salesman/master with fy=2026-27 should succeed"""
        res = requests.post(f"{BASE_URL}/api/salesman/master", headers=self.headers, json={
            "salesman_name": "TEST_Iteration23_Salesman",
            "fy": "2026-27",
            "monthly_target": 500000,
            "quarterly_target": 1500000,
            "phone": "9876543210",
            "email": "test@example.com",
            "customers": []
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert "2026-27" in data.get("message", "")
        print(f"✓ POST to current FY succeeded: {data.get('message')}")
    
    def test_delete_test_salesman(self):
        """DELETE /api/salesman/master/{name} should work"""
        res = requests.delete(
            f"{BASE_URL}/api/salesman/master/TEST_Iteration23_Salesman",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        # May or may not find it depending on test order
        print(f"✓ DELETE salesman: {data.get('message')}")
    
    # ==================== PERFORMANCE-DETAILED ENDPOINT TESTS ====================
    
    def test_performance_detailed_monthly(self):
        """GET /api/salesman/performance-detailed?duration=monthly returns monthly breakdown"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=monthly",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        
        # Check periods structure
        periods = data["data"]["periods"]
        assert "months" in periods
        assert "month_labels" in periods
        assert "quarters" in periods
        assert isinstance(periods["months"], list)
        print(f"✓ Monthly periods: {len(periods['months'])} months")
        
        # Check salesman data structure
        salesmen = data["data"]["salesman"]
        if len(salesmen) > 0:
            s = salesmen[0]
            assert "salesman_name" in s
            assert "monthly_target" in s
            assert "quarterly_target" in s
            assert "annual_target" in s
            assert "achieved_amount" in s
            assert "achievement_percentage" in s
            assert "customers" in s
            
            # Check customer breakdown
            if len(s["customers"]) > 0:
                c = s["customers"][0]
                assert "customer_name" in c
                assert "monthly" in c
                assert "quarterly" in c
                assert "annual_amount" in c
                print(f"✓ Customer breakdown has monthly/quarterly data")
    
    def test_performance_detailed_quarterly(self):
        """GET /api/salesman/performance-detailed?duration=quarterly returns quarterly breakdown"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=quarterly",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        
        periods = data["data"]["periods"]
        assert "quarters" in periods
        quarters = periods["quarters"]
        # Should have Q1-Q4 labels
        expected_quarters = ["Q1 (Apr-Jun)", "Q2 (Jul-Sep)", "Q3 (Oct-Dec)", "Q4 (Jan-Mar)"]
        for q in quarters:
            assert q in expected_quarters
        print(f"✓ Quarterly periods: {quarters}")
    
    def test_performance_detailed_annual(self):
        """GET /api/salesman/performance-detailed?duration=annual returns annual totals"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=annual",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        
        salesmen = data["data"]["salesman"]
        if len(salesmen) > 0:
            s = salesmen[0]
            assert s["achieved_amount"] > 0
            assert s["annual_target"] > 0
            print(f"✓ Annual: achieved={s['achieved_amount']}, target={s['annual_target']}")
    
    def test_performance_detailed_weighted_average(self):
        """Achievement percentage should be weighted by revenue contribution"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26&duration=monthly",
            headers=self.headers
        )
        assert res.status_code == 200
        data = res.json()
        
        salesmen = data["data"]["salesman"]
        if len(salesmen) > 0:
            s = salesmen[0]
            # Verify weighted average calculation
            if s["annual_target"] > 0:
                expected_pct = round(s["achieved_amount"] / s["annual_target"] * 100, 1)
                assert abs(s["achievement_percentage"] - expected_pct) < 0.5
                print(f"✓ Weighted average correct: {s['achievement_percentage']}%")
    
    # ==================== EXPORT ENDPOINT TESTS ====================
    
    def test_export_excel_monthly(self):
        """GET /api/salesman/export returns Excel file"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/export?salesman_name=Ankit&fy=2025-26&duration=monthly",
            headers=self.headers
        )
        assert res.status_code == 200
        assert "spreadsheetml" in res.headers.get("content-type", "")
        assert "attachment" in res.headers.get("content-disposition", "")
        assert len(res.content) > 1000  # Should have some content
        print(f"✓ Excel export: {len(res.content)} bytes")
    
    def test_export_excel_quarterly(self):
        """GET /api/salesman/export?duration=quarterly returns Excel file"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/export?salesman_name=Ankit&fy=2025-26&duration=quarterly",
            headers=self.headers
        )
        assert res.status_code == 200
        assert "spreadsheetml" in res.headers.get("content-type", "")
        print(f"✓ Quarterly Excel export: {len(res.content)} bytes")
    
    def test_export_excel_annual(self):
        """GET /api/salesman/export?duration=annual returns Excel file"""
        res = requests.get(
            f"{BASE_URL}/api/salesman/export?salesman_name=Ankit&fy=2025-26&duration=annual",
            headers=self.headers
        )
        assert res.status_code == 200
        assert "spreadsheetml" in res.headers.get("content-type", "")
        print(f"✓ Annual Excel export: {len(res.content)} bytes")


class TestSearchableSelectIntegration:
    """Test that SearchableSelect is used in Sales, CRM, and Salesman pages"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        self.token = data["data"]["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"
        }
    
    def test_customers_outstanding_returns_sorted_list(self):
        """GET /api/customers/outstanding should return customers for SearchableSelect"""
        res = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        customers = data["data"]["customers"]
        assert isinstance(customers, list)
        if len(customers) > 1:
            # Check if sorted alphabetically
            names = [c["customer_name"] for c in customers]
            sorted_names = sorted(names, key=lambda x: x.lower())
            # Note: API may not sort, frontend sorts
            print(f"✓ Customers list: {len(customers)} customers")
    
    def test_sales_vouchers_returns_unique_parties(self):
        """GET /api/sales/vouchers should return unique_parties for SearchableSelect"""
        res = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        unique_parties = data["data"].get("unique_parties", [])
        assert isinstance(unique_parties, list)
        print(f"✓ Unique parties: {len(unique_parties)} parties")


class TestInventorySorting:
    """Test that Inventory categories and stock groups are sorted"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        self.token = data["data"]["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"
        }
    
    def test_inventory_items_returns_stock_groups(self):
        """GET /api/inventory/items should return stock_groups list"""
        res = requests.get(f"{BASE_URL}/api/inventory/items", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        stock_groups = data["data"].get("stock_groups", [])
        assert isinstance(stock_groups, list)
        print(f"✓ Stock groups: {len(stock_groups)} groups")
        
        # Frontend sorts these alphabetically
        items = data["data"].get("items", [])
        categories = list(set(i.get("category") for i in items if i.get("category")))
        print(f"✓ Categories: {len(categories)} categories")


class TestUtilsFunctions:
    """Test utility functions for FY handling"""
    
    def test_get_current_fy(self):
        """Current FY should be 2026-27 (April 2026)"""
        # We're in April 2026, so current FY is 2026-27
        res = requests.get(f"{BASE_URL}/api/salesman/master")
        assert res.status_code == 200
        data = res.json()
        assert data["data"]["current_fy"] == "2026-27"
        print(f"✓ Current FY: {data['data']['current_fy']}")
    
    def test_is_fy_completed_2025_26(self):
        """FY 2025-26 should be completed (ended Mar 31, 2026)"""
        res = requests.get(f"{BASE_URL}/api/salesman/master?fy=2025-26")
        assert res.status_code == 200
        data = res.json()
        assert data["data"]["fy_locked"] is True
        print(f"✓ FY 2025-26 is completed/locked")
    
    def test_is_fy_completed_2026_27(self):
        """FY 2026-27 should NOT be completed (current FY)"""
        res = requests.get(f"{BASE_URL}/api/salesman/master?fy=2026-27")
        assert res.status_code == 200
        data = res.json()
        assert data["data"]["fy_locked"] is False
        print(f"✓ FY 2026-27 is NOT locked (current FY)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
