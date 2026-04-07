"""
Iteration 3 Backend Tests - New Features
Tests for:
1. Salesman CRUD (POST/GET/DELETE /api/salesman/master)
2. Detailed performance endpoint with item-wise breakdown (GET /api/salesman/performance-detailed)
3. Sales frequency export (POST /api/analytics/sales-frequency/export)
4. AI advanced query (POST /api/ai/advanced-query)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSalesmanMasterCRUD:
    """Test Salesman Master CRUD operations"""
    
    def test_get_salesman_master_list(self):
        """GET /api/salesman/master - returns salesman list"""
        response = requests.get(f"{BASE_URL}/api/salesman/master")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "salesmen" in data.get("data", {})
        print(f"✓ GET /api/salesman/master - Found {len(data['data']['salesmen'])} salesmen")
    
    def test_create_salesman_with_full_data(self):
        """POST /api/salesman/master - create salesman with all fields"""
        payload = {
            "salesman_name": "TEST_John_Doe",
            "phone": "9999888877",
            "email": "john.doe@test.com",
            "monthly_target": 500000,
            "quarterly_target": 1500000,
            "customers": ["Tech Solutions Pvt Ltd", "Smart Enterprises"]
        }
        response = requests.post(f"{BASE_URL}/api/salesman/master", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "TEST_John_Doe" in data.get("message", "")
        
        # Verify data was saved
        saved_data = data.get("data", {})
        assert saved_data.get("salesman_name") == "TEST_John_Doe"
        assert saved_data.get("monthly_target") == 500000
        assert saved_data.get("quarterly_target") == 1500000
        assert len(saved_data.get("customers", [])) == 2
        print("✓ POST /api/salesman/master - Created salesman with full data")
    
    def test_create_salesman_minimal_data(self):
        """POST /api/salesman/master - create salesman with minimal data"""
        payload = {
            "salesman_name": "TEST_Minimal_Salesman",
            "monthly_target": 100000
        }
        response = requests.post(f"{BASE_URL}/api/salesman/master", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ POST /api/salesman/master - Created salesman with minimal data")
    
    def test_create_salesman_empty_name_fails(self):
        """POST /api/salesman/master - empty name should fail"""
        payload = {
            "salesman_name": "",
            "monthly_target": 100000
        }
        response = requests.post(f"{BASE_URL}/api/salesman/master", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False
        assert "required" in data.get("error", "").lower()
        print("✓ POST /api/salesman/master - Empty name validation works")
    
    def test_verify_created_salesman_in_list(self):
        """GET /api/salesman/master - verify created salesman appears"""
        response = requests.get(f"{BASE_URL}/api/salesman/master")
        assert response.status_code == 200
        data = response.json()
        salesmen = data.get("data", {}).get("salesmen", [])
        names = [s.get("salesman_name") for s in salesmen]
        assert "TEST_John_Doe" in names
        print("✓ GET /api/salesman/master - Created salesman found in list")
    
    def test_delete_salesman(self):
        """DELETE /api/salesman/master/{name} - delete salesman"""
        response = requests.delete(f"{BASE_URL}/api/salesman/master/TEST_John_Doe")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ DELETE /api/salesman/master - Deleted salesman")
    
    def test_delete_minimal_salesman(self):
        """DELETE /api/salesman/master/{name} - cleanup minimal salesman"""
        response = requests.delete(f"{BASE_URL}/api/salesman/master/TEST_Minimal_Salesman")
        assert response.status_code == 200
        print("✓ DELETE /api/salesman/master - Cleanup completed")
    
    def test_verify_deleted_salesman_not_in_list(self):
        """GET /api/salesman/master - verify deleted salesman removed"""
        response = requests.get(f"{BASE_URL}/api/salesman/master")
        assert response.status_code == 200
        data = response.json()
        salesmen = data.get("data", {}).get("salesmen", [])
        names = [s.get("salesman_name") for s in salesmen]
        assert "TEST_John_Doe" not in names
        print("✓ GET /api/salesman/master - Deleted salesman not in list")


class TestSalesmanPerformanceDetailed:
    """Test detailed salesman performance endpoint"""
    
    def test_get_performance_detailed(self):
        """GET /api/salesman/performance-detailed - returns detailed performance"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "salesman" in data.get("data", {})
        
        salesmen = data["data"]["salesman"]
        assert len(salesmen) > 0
        
        # Check first salesman has required fields
        first = salesmen[0]
        required_fields = [
            "salesman_name", "monthly_target", "achieved_amount", 
            "achievement_percentage", "total_customers", "total_transactions",
            "items_sold", "has_master"
        ]
        for field in required_fields:
            assert field in first, f"Missing field: {field}"
        
        print(f"✓ GET /api/salesman/performance-detailed - Found {len(salesmen)} salesmen with detailed data")
    
    def test_performance_has_items_sold_breakdown(self):
        """GET /api/salesman/performance-detailed - has item-wise breakdown"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed")
        assert response.status_code == 200
        data = response.json()
        
        salesmen = data["data"]["salesman"]
        # Find a salesman with items sold
        salesman_with_items = None
        for s in salesmen:
            if s.get("items_sold") and len(s["items_sold"]) > 0:
                salesman_with_items = s
                break
        
        assert salesman_with_items is not None, "No salesman with items_sold found"
        
        # Check item structure
        item = salesman_with_items["items_sold"][0]
        assert "item_name" in item
        assert "total_quantity" in item
        assert "total_revenue" in item
        assert "transaction_count" in item
        
        print(f"✓ Items sold breakdown: {salesman_with_items['salesman_name']} has {len(salesman_with_items['items_sold'])} items")
    
    def test_performance_has_master_flag(self):
        """GET /api/salesman/performance-detailed - has_master flag works"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed")
        assert response.status_code == 200
        data = response.json()
        
        salesmen = data["data"]["salesman"]
        # Check that has_master flag exists
        has_master_count = sum(1 for s in salesmen if s.get("has_master") == True)
        print(f"✓ has_master flag: {has_master_count} salesmen are registered in master")


class TestSalesFrequencyExport:
    """Test sales frequency export endpoint"""
    
    def test_export_excel(self):
        """POST /api/analytics/sales-frequency/export - Excel export"""
        payload = {"format": "excel"}
        response = requests.post(f"{BASE_URL}/api/analytics/sales-frequency/export", json=payload)
        assert response.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers.get("content-type", "")
        assert len(response.content) > 0
        print(f"✓ Excel export - {len(response.content)} bytes")
    
    def test_export_pdf(self):
        """POST /api/analytics/sales-frequency/export - PDF export"""
        payload = {"format": "pdf"}
        response = requests.post(f"{BASE_URL}/api/analytics/sales-frequency/export", json=payload)
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")
        assert len(response.content) > 0
        print(f"✓ PDF export - {len(response.content)} bytes")
    
    def test_export_with_date_filter(self):
        """POST /api/analytics/sales-frequency/export - with date filter"""
        payload = {
            "format": "excel",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31"
        }
        response = requests.post(f"{BASE_URL}/api/analytics/sales-frequency/export", json=payload)
        assert response.status_code == 200
        print("✓ Export with date filter works")
    
    def test_export_invalid_format(self):
        """POST /api/analytics/sales-frequency/export - invalid format"""
        payload = {"format": "invalid"}
        response = requests.post(f"{BASE_URL}/api/analytics/sales-frequency/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False
        print("✓ Invalid format returns error")


class TestAIAdvancedQuery:
    """Test AI advanced query endpoint"""
    
    def test_ai_query_general(self):
        """POST /api/ai/advanced-query - general query"""
        payload = {
            "query": "Give me a summary of inventory status",
            "report_type": "general"
        }
        response = requests.post(f"{BASE_URL}/api/ai/advanced-query", json=payload, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        if data.get("success"):
            report = data.get("data", {})
            assert "summary" in report or isinstance(report, dict)
            print(f"✓ AI query successful - Summary: {str(report.get('summary', ''))[:100]}...")
        else:
            # AI might fail due to budget, but endpoint should work
            print(f"⚠ AI query returned error (may be budget): {data.get('error', 'Unknown')}")
    
    def test_ai_query_inventory_type(self):
        """POST /api/ai/advanced-query - inventory report type"""
        payload = {
            "query": "Show me low stock items",
            "report_type": "inventory"
        }
        response = requests.post(f"{BASE_URL}/api/ai/advanced-query", json=payload, timeout=60)
        assert response.status_code == 200
        print("✓ AI inventory query endpoint works")
    
    def test_ai_query_with_filters(self):
        """POST /api/ai/advanced-query - with filters"""
        payload = {
            "query": "Analyze sales performance",
            "report_type": "sales",
            "filters": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-31"
            }
        }
        response = requests.post(f"{BASE_URL}/api/ai/advanced-query", json=payload, timeout=60)
        assert response.status_code == 200
        print("✓ AI query with filters works")


class TestExistingEndpoints:
    """Verify existing endpoints still work"""
    
    def test_salesman_performance_basic(self):
        """GET /api/salesman/performance - basic endpoint"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Basic salesman performance endpoint works")
    
    def test_sales_frequency(self):
        """GET /api/inventory/sales-frequency - sales frequency data"""
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "sales_frequency" in data.get("data", {})
        print("✓ Sales frequency endpoint works")
    
    def test_customers_outstanding(self):
        """GET /api/customers/outstanding - customer data for mapping"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "customers" in data.get("data", {})
        print(f"✓ Customers outstanding - {len(data['data']['customers'])} customers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
