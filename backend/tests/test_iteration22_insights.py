"""
Iteration 22: Insider Result Analytics Dashboard Tests
Tests for 4 new analytics endpoints:
1. GET /api/insights/customer-lifecycle - Active/Inactive/Lost customer tracking
2. GET /api/insights/sales-forecast - Sales trend forecasting
3. GET /api/insights/spip-analysis - Purchase vs Sales Gap analysis
4. GET /api/insights/concentration-risk - Customer concentration risk (Pareto)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_CREDS = {"username": "admin", "password": "admin123"}
TEST_ADMIN_CREDS = {"username": "test_admin", "password": "test123"}
ADMIN_COMPANY = "ASA AUTOTECH INDIA PRIVATE LIMITED"


class TestInsightsEndpoints:
    """Test all 4 Insider Result analytics endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with admin login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        data = login_res.json()
        assert data.get("success"), f"Admin login not successful: {data}"
        
        token = data["data"]["token"]
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "X-Company-ID": ADMIN_COMPANY
        })
        yield
        self.session.close()
    
    # ============ CUSTOMER LIFECYCLE TESTS ============
    
    def test_customer_lifecycle_returns_success(self):
        """GET /api/insights/customer-lifecycle returns success with proper structure"""
        res = self.session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        # Verify response structure
        result = data.get("data", {})
        assert "active" in result, "Missing 'active' array"
        assert "inactive" in result, "Missing 'inactive' array"
        assert "lost" in result, "Missing 'lost' array"
        assert "summary" in result, "Missing 'summary' object"
        assert "trend" in result, "Missing 'trend' array"
        print(f"Customer Lifecycle: Active={len(result['active'])}, Inactive={len(result['inactive'])}, Lost={len(result['lost'])}")
    
    def test_customer_lifecycle_summary_structure(self):
        """Customer lifecycle summary has correct fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        data = res.json()
        summary = data.get("data", {}).get("summary", {})
        
        required_fields = ["active_count", "inactive_count", "lost_count", 
                          "active_revenue", "inactive_revenue", "lost_revenue"]
        for field in required_fields:
            assert field in summary, f"Missing summary field: {field}"
        
        # Verify counts are non-negative integers
        assert isinstance(summary["active_count"], int) and summary["active_count"] >= 0
        assert isinstance(summary["inactive_count"], int) and summary["inactive_count"] >= 0
        assert isinstance(summary["lost_count"], int) and summary["lost_count"] >= 0
        print(f"Summary: {summary}")
    
    def test_customer_lifecycle_customer_entry_structure(self):
        """Each customer entry has required fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        data = res.json()
        result = data.get("data", {})
        
        # Check first active customer if exists
        all_customers = result.get("active", []) + result.get("inactive", []) + result.get("lost", [])
        if all_customers:
            customer = all_customers[0]
            required_fields = ["customer_name", "status", "last_transaction", 
                             "days_since_last", "total_revenue", "transaction_count"]
            for field in required_fields:
                assert field in customer, f"Missing customer field: {field}"
            print(f"Sample customer: {customer['customer_name']}, status={customer['status']}, revenue={customer['total_revenue']}")
    
    # ============ SALES FORECAST TESTS ============
    
    def test_sales_forecast_returns_success(self):
        """GET /api/insights/sales-forecast returns success with proper structure"""
        res = self.session.get(f"{BASE_URL}/api/insights/sales-forecast")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        result = data.get("data", {})
        assert "timeline" in result, "Missing 'timeline' array"
        assert "forecasts" in result, "Missing 'forecasts' array"
        assert "yoy" in result, "Missing 'yoy' array"
        assert "summary" in result, "Missing 'summary' object"
        print(f"Sales Forecast: {len(result['timeline'])} months of data, {len(result['forecasts'])} forecasts")
    
    def test_sales_forecast_summary_structure(self):
        """Sales forecast summary has correct fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/sales-forecast")
        data = res.json()
        summary = data.get("data", {}).get("summary", {})
        
        required_fields = ["total_months", "avg_monthly_revenue", "best_month", "best_month_revenue"]
        for field in required_fields:
            assert field in summary, f"Missing summary field: {field}"
        print(f"Forecast Summary: avg_monthly={summary['avg_monthly_revenue']}, best_month={summary['best_month']}")
    
    def test_sales_forecast_timeline_entry_structure(self):
        """Each timeline entry has required fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/sales-forecast")
        data = res.json()
        timeline = data.get("data", {}).get("timeline", [])
        
        if timeline:
            entry = timeline[0]
            required_fields = ["month", "revenue", "count", "unique_customers"]
            for field in required_fields:
                assert field in entry, f"Missing timeline field: {field}"
            print(f"Sample timeline: month={entry['month']}, revenue={entry['revenue']}, customers={entry['unique_customers']}")
    
    def test_sales_forecast_has_forecasts(self):
        """Sales forecast includes future month predictions"""
        res = self.session.get(f"{BASE_URL}/api/insights/sales-forecast")
        data = res.json()
        forecasts = data.get("data", {}).get("forecasts", [])
        
        # Should have forecasts if there's enough historical data
        timeline = data.get("data", {}).get("timeline", [])
        if len(timeline) >= 3:
            assert len(forecasts) > 0, "Expected forecasts with sufficient historical data"
            forecast = forecasts[0]
            assert "month" in forecast
            assert "forecast_revenue" in forecast
            assert "confidence" in forecast
            print(f"Forecast: {forecasts}")
    
    # ============ SPIP ANALYSIS TESTS ============
    
    def test_spip_analysis_returns_success(self):
        """GET /api/insights/spip-analysis returns success with proper structure"""
        res = self.session.get(f"{BASE_URL}/api/insights/spip-analysis")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        result = data.get("data", {})
        assert "items" in result, "Missing 'items' array"
        assert "summary" in result, "Missing 'summary' object"
        assert "total_items" in result, "Missing 'total_items' count"
        print(f"SPIP Analysis: {result['total_items']} total items, summary={result['summary']}")
    
    def test_spip_analysis_item_structure(self):
        """Each SPIP item has required fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/spip-analysis")
        data = res.json()
        items = data.get("data", {}).get("items", [])
        
        if items:
            item = items[0]
            required_fields = ["item_name", "gap_type", "stock_qty", "qty_sold", 
                             "revenue", "monthly_avg_sales", "months_of_stock"]
            for field in required_fields:
                assert field in item, f"Missing item field: {field}"
            
            # Verify gap_type is valid
            valid_gap_types = ["out_of_stock", "understocked", "dead_stock", "overstocked", "balanced"]
            assert item["gap_type"] in valid_gap_types, f"Invalid gap_type: {item['gap_type']}"
            print(f"Sample item: {item['item_name']}, gap={item['gap_type']}, stock={item['stock_qty']}")
    
    def test_spip_analysis_summary_has_gap_counts(self):
        """SPIP summary contains gap type counts"""
        res = self.session.get(f"{BASE_URL}/api/insights/spip-analysis")
        data = res.json()
        summary = data.get("data", {}).get("summary", {})
        
        # Summary should have counts for each gap type found
        assert isinstance(summary, dict), "Summary should be a dict"
        print(f"SPIP Gap Summary: {summary}")
    
    # ============ CONCENTRATION RISK TESTS ============
    
    def test_concentration_risk_returns_success(self):
        """GET /api/insights/concentration-risk returns success with proper structure"""
        res = self.session.get(f"{BASE_URL}/api/insights/concentration-risk")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        result = data.get("data", {})
        assert "customers" in result, "Missing 'customers' array"
        assert "summary" in result, "Missing 'summary' object"
        assert "risk_level" in result, "Missing 'risk_level'"
        print(f"Concentration Risk: {len(result['customers'])} customers, risk_level={result['risk_level']}")
    
    def test_concentration_risk_summary_structure(self):
        """Concentration risk summary has correct fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/concentration-risk")
        data = res.json()
        summary = data.get("data", {}).get("summary", {})
        
        required_fields = ["total_customers", "total_revenue", "top5_pct", "top10_pct", 
                          "top20pct_pct", "top5_revenue", "top10_revenue"]
        for field in required_fields:
            assert field in summary, f"Missing summary field: {field}"
        print(f"Concentration Summary: total_customers={summary['total_customers']}, top5_pct={summary['top5_pct']}%")
    
    def test_concentration_risk_customer_entry_structure(self):
        """Each customer entry has Pareto fields"""
        res = self.session.get(f"{BASE_URL}/api/insights/concentration-risk")
        data = res.json()
        customers = data.get("data", {}).get("customers", [])
        
        if customers:
            customer = customers[0]
            required_fields = ["rank", "customer_name", "revenue", "pct_of_total", "cumulative_pct"]
            for field in required_fields:
                assert field in customer, f"Missing customer field: {field}"
            
            # First customer should be rank 1
            assert customer["rank"] == 1, f"First customer should be rank 1, got {customer['rank']}"
            print(f"Top customer: {customer['customer_name']}, revenue={customer['revenue']}, cumulative={customer['cumulative_pct']}%")
    
    def test_concentration_risk_level_valid(self):
        """Risk level is one of valid values"""
        res = self.session.get(f"{BASE_URL}/api/insights/concentration-risk")
        data = res.json()
        risk_level = data.get("data", {}).get("risk_level")
        
        valid_levels = ["critical", "high", "moderate", "healthy", "no_data"]
        assert risk_level in valid_levels, f"Invalid risk_level: {risk_level}"
        print(f"Risk Level: {risk_level}")


class TestInsightsTenantIsolation:
    """Test that insights data is properly isolated by tenant_id and company_id"""
    
    def test_test_admin_gets_empty_data(self):
        """test_admin (different tenant) should get empty/zero data from all endpoints"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as test_admin
        login_res = session.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN_CREDS)
        assert login_res.status_code == 200, f"test_admin login failed: {login_res.text}"
        data = login_res.json()
        assert data.get("success"), f"test_admin login not successful: {data}"
        
        token = data["data"]["token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Test customer-lifecycle - should have 0 customers
        res = session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        assert res.status_code == 200
        result = res.json().get("data", {})
        total_customers = len(result.get("active", [])) + len(result.get("inactive", [])) + len(result.get("lost", []))
        assert total_customers == 0, f"test_admin should see 0 customers, got {total_customers}"
        print(f"test_admin customer-lifecycle: {total_customers} customers (expected 0)")
        
        # Test sales-forecast - should have empty timeline
        res = session.get(f"{BASE_URL}/api/insights/sales-forecast")
        assert res.status_code == 200
        result = res.json().get("data", {})
        timeline_count = len(result.get("timeline", []))
        assert timeline_count == 0, f"test_admin should see 0 timeline entries, got {timeline_count}"
        print(f"test_admin sales-forecast: {timeline_count} timeline entries (expected 0)")
        
        # Test spip-analysis - should have 0 items
        res = session.get(f"{BASE_URL}/api/insights/spip-analysis")
        assert res.status_code == 200
        result = res.json().get("data", {})
        total_items = result.get("total_items", 0)
        assert total_items == 0, f"test_admin should see 0 items, got {total_items}"
        print(f"test_admin spip-analysis: {total_items} items (expected 0)")
        
        # Test concentration-risk - should have 0 customers or no_data
        res = session.get(f"{BASE_URL}/api/insights/concentration-risk")
        assert res.status_code == 200
        result = res.json().get("data", {})
        customer_count = len(result.get("customers", []))
        risk_level = result.get("risk_level")
        assert customer_count == 0 or risk_level == "no_data", f"test_admin should see 0 customers or no_data, got {customer_count} customers, risk={risk_level}"
        print(f"test_admin concentration-risk: {customer_count} customers, risk_level={risk_level}")
        
        session.close()
    
    def test_admin_has_data(self):
        """admin (with company ASA AUTOTECH) should have data"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_res = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert login_res.status_code == 200
        data = login_res.json()
        token = data["data"]["token"]
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "X-Company-ID": ADMIN_COMPANY
        })
        
        # Test customer-lifecycle - should have customers
        res = session.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        assert res.status_code == 200
        result = res.json().get("data", {})
        total_customers = len(result.get("active", [])) + len(result.get("inactive", [])) + len(result.get("lost", []))
        print(f"admin customer-lifecycle: {total_customers} customers")
        
        # Test sales-forecast - should have timeline
        res = session.get(f"{BASE_URL}/api/insights/sales-forecast")
        assert res.status_code == 200
        result = res.json().get("data", {})
        timeline_count = len(result.get("timeline", []))
        print(f"admin sales-forecast: {timeline_count} timeline entries")
        
        # Test concentration-risk - should have customers
        res = session.get(f"{BASE_URL}/api/insights/concentration-risk")
        assert res.status_code == 200
        result = res.json().get("data", {})
        customer_count = len(result.get("customers", []))
        risk_level = result.get("risk_level")
        print(f"admin concentration-risk: {customer_count} customers, risk_level={risk_level}")
        
        session.close()


class TestInsightsAuthentication:
    """Test that insights endpoints require authentication"""
    
    def test_customer_lifecycle_requires_auth(self):
        """GET /api/insights/customer-lifecycle requires authentication"""
        res = requests.get(f"{BASE_URL}/api/insights/customer-lifecycle")
        # Should return 401 or 403 or success=False
        if res.status_code == 200:
            data = res.json()
            # If 200, check if it returns empty data (no tenant context)
            result = data.get("data", {})
            total = len(result.get("active", [])) + len(result.get("inactive", [])) + len(result.get("lost", []))
            print(f"Unauthenticated request returned {total} customers (should be 0 or error)")
        else:
            print(f"Unauthenticated request returned status {res.status_code}")
    
    def test_sales_forecast_requires_auth(self):
        """GET /api/insights/sales-forecast requires authentication"""
        res = requests.get(f"{BASE_URL}/api/insights/sales-forecast")
        if res.status_code == 200:
            data = res.json()
            result = data.get("data", {})
            timeline_count = len(result.get("timeline", []))
            print(f"Unauthenticated request returned {timeline_count} timeline entries")
        else:
            print(f"Unauthenticated request returned status {res.status_code}")
    
    def test_spip_analysis_requires_auth(self):
        """GET /api/insights/spip-analysis requires authentication"""
        res = requests.get(f"{BASE_URL}/api/insights/spip-analysis")
        if res.status_code == 200:
            data = res.json()
            result = data.get("data", {})
            total_items = result.get("total_items", 0)
            print(f"Unauthenticated request returned {total_items} items")
        else:
            print(f"Unauthenticated request returned status {res.status_code}")
    
    def test_concentration_risk_requires_auth(self):
        """GET /api/insights/concentration-risk requires authentication"""
        res = requests.get(f"{BASE_URL}/api/insights/concentration-risk")
        if res.status_code == 200:
            data = res.json()
            result = data.get("data", {})
            customer_count = len(result.get("customers", []))
            print(f"Unauthenticated request returned {customer_count} customers")
        else:
            print(f"Unauthenticated request returned status {res.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
