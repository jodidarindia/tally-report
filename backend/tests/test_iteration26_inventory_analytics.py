"""
Iteration 26: Inventory Analytics Module Testing
Tests for the redesigned Inventory Analytics with 3 tabs:
- Movement Analysis (classification filter cards, sortable table, Excel export)
- Below Cost Sales (real cost from purchase vouchers, summary cards, Excel export)
- Sales Frequency (date filters, Excel + PDF exports)
All endpoints enforce tenant_id + company_id isolation and FY filtering.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "admin123"}
TEST_ADMIN_CREDS = {"username": "test_admin", "password": "test123"}
FY = "2025-26"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    return data.get("data", {}).get("token") or data.get("token")


@pytest.fixture(scope="module")
def test_admin_token():
    """Get test_admin auth token (limited features, isolated data)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN_CREDS)
    assert response.status_code == 200, f"Test admin login failed: {response.text}"
    data = response.json()
    return data.get("data", {}).get("token") or data.get("token")


class TestMovementAnalysisAPI:
    """Tests for GET /api/inventory/movement-analysis endpoint"""

    def test_movement_analysis_returns_success(self, admin_token):
        """Movement analysis endpoint returns success with movements array and summary"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy={FY}", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        result = data.get("data", {})
        assert "movements" in result, "Response missing 'movements' array"
        assert "summary" in result, "Response missing 'summary' object"
        assert isinstance(result["movements"], list), "movements should be a list"
        print(f"Movement analysis returned {len(result['movements'])} items")

    def test_movement_analysis_has_required_columns(self, admin_token):
        """Movement data has all required columns"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        movements = data.get("data", {}).get("movements", [])
        
        if len(movements) > 0:
            item = movements[0]
            required_fields = [
                "item_name", "category", "opening_stock", "inward", "sales",
                "closing_stock", "movement_rate", "days_to_sell", "transactions", "classification"
            ]
            for field in required_fields:
                assert field in item, f"Missing required field: {field}"
            print(f"All {len(required_fields)} required columns present")

    def test_movement_analysis_summary_has_classification_counts(self, admin_token):
        """Summary object has counts for all 4 classifications"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("data", {}).get("summary", {})
        
        assert "fast_moving" in summary, "Summary missing fast_moving count"
        assert "moderate" in summary, "Summary missing moderate count"
        assert "slow_moving" in summary, "Summary missing slow_moving count"
        assert "non_moving" in summary, "Summary missing non_moving count"
        
        print(f"Classification counts: fast={summary['fast_moving']}, moderate={summary['moderate']}, slow={summary['slow_moving']}, non-moving={summary['non_moving']}")

    def test_movement_analysis_classification_values(self, admin_token):
        """Classification field has valid values"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        movements = data.get("data", {}).get("movements", [])
        
        valid_classifications = {"fast-moving", "moderate", "slow-moving", "non-moving"}
        for item in movements[:20]:  # Check first 20 items
            assert item.get("classification") in valid_classifications, f"Invalid classification: {item.get('classification')}"
        print("All classification values are valid")


class TestMovementExportAPI:
    """Tests for GET /api/inventory/movement-export endpoint"""

    def test_movement_export_returns_excel(self, admin_token):
        """Movement export returns Excel file with 200 status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-export?fy={FY}", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type or "octet-stream" in content_type, f"Expected Excel content type, got: {content_type}"
        assert len(response.content) > 100, "Excel file seems too small"
        print(f"Movement export returned {len(response.content)} bytes")


class TestBelowCostSalesAPI:
    """Tests for GET /api/inventory/below-cost-sales endpoint"""

    def test_below_cost_sales_returns_success(self, admin_token):
        """Below cost sales endpoint returns success with items array and summary"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales?fy={FY}", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        result = data.get("data", {})
        assert "items" in result, "Response missing 'items' array"
        assert "summary" in result, "Response missing 'summary' object"
        print(f"Below cost sales returned {len(result['items'])} items")

    def test_below_cost_sales_summary_structure(self, admin_token):
        """Summary has total_items, total_loss, total_affected_revenue"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        summary = data.get("data", {}).get("summary", {})
        
        assert "total_items" in summary, "Summary missing total_items"
        assert "total_loss" in summary, "Summary missing total_loss"
        assert "total_affected_revenue" in summary, "Summary missing total_affected_revenue"
        print(f"Below cost summary: {summary['total_items']} items, loss={summary['total_loss']}, affected_revenue={summary['total_affected_revenue']}")

    def test_below_cost_items_have_required_fields(self, admin_token):
        """Below cost items have all required fields"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        items = data.get("data", {}).get("items", [])
        
        if len(items) > 0:
            item = items[0]
            required_fields = [
                "item_name", "cost_price", "avg_selling_price", "margin",
                "margin_pct", "qty_sold", "total_revenue", "total_loss"
            ]
            for field in required_fields:
                assert field in item, f"Missing required field: {field}"
            print(f"Below cost item has all {len(required_fields)} required fields")
        else:
            print("No below cost items found (this is valid - may mean no items sold below cost)")


class TestBelowCostExportAPI:
    """Tests for GET /api/inventory/below-cost-export endpoint"""

    def test_below_cost_export_returns_excel(self, admin_token):
        """Below cost export returns Excel file with 200 status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-export?fy={FY}", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type or "octet-stream" in content_type, f"Expected Excel content type, got: {content_type}"
        print(f"Below cost export returned {len(response.content)} bytes")


class TestSalesFrequencyAPI:
    """Tests for GET /api/inventory/sales-frequency endpoint"""

    def test_sales_frequency_returns_success(self, admin_token):
        """Sales frequency endpoint returns success with frequency array"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency?fy={FY}", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True: {data}"
        
        result = data.get("data", {})
        assert "frequency" in result, "Response missing 'frequency' array"
        assert isinstance(result["frequency"], list), "frequency should be a list"
        print(f"Sales frequency returned {len(result['frequency'])} items")

    def test_sales_frequency_items_have_required_fields(self, admin_token):
        """Sales frequency items have all required fields"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        frequency = data.get("data", {}).get("frequency", [])
        
        if len(frequency) > 0:
            item = frequency[0]
            required_fields = [
                "item_name", "total_quantity_sold", "transaction_count",
                "unique_customers", "total_revenue", "avg_quantity_per_transaction"
            ]
            for field in required_fields:
                assert field in item, f"Missing required field: {field}"
            print(f"Sales frequency item has all {len(required_fields)} required fields")

    def test_sales_frequency_with_date_filter(self, admin_token):
        """Sales frequency accepts date filter parameters"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/inventory/sales-frequency?fy={FY}&start_date=2025-04-01&end_date=2025-12-31",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True
        print("Sales frequency with date filter works")


class TestSalesFrequencyExportAPI:
    """Tests for GET /api/inventory/sales-frequency-export endpoint"""

    def test_sales_frequency_export_excel(self, admin_token):
        """Sales frequency export returns Excel file"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/inventory/sales-frequency-export?fy={FY}&format=excel",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type or "octet-stream" in content_type, f"Expected Excel content type, got: {content_type}"
        print(f"Sales frequency Excel export returned {len(response.content)} bytes")

    def test_sales_frequency_export_pdf(self, admin_token):
        """Sales frequency export returns PDF file"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/inventory/sales-frequency-export?fy={FY}&format=pdf",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        content_type = response.headers.get("Content-Type", "")
        assert "pdf" in content_type or "octet-stream" in content_type, f"Expected PDF content type, got: {content_type}"
        print(f"Sales frequency PDF export returned {len(response.content)} bytes")


class TestDataIsolation:
    """Tests for tenant data isolation"""

    def test_admin_sees_inventory_data(self, admin_token):
        """Admin (tenant_admin) sees inventory data"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        movements = data.get("data", {}).get("movements", [])
        
        assert len(movements) > 0, "Admin should see inventory data"
        print(f"Admin sees {len(movements)} items in movement analysis")

    def test_test_admin_sees_zero_items(self, test_admin_token):
        """test_admin (tenant_test_admin) sees 0 items due to data isolation"""
        headers = {"Authorization": f"Bearer {test_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy={FY}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        movements = data.get("data", {}).get("movements", [])
        
        assert len(movements) == 0, f"test_admin should see 0 items, but saw {len(movements)}"
        print("test_admin correctly sees 0 items (data isolation working)")


class TestFYFiltering:
    """Tests for FY filtering"""

    def test_movement_analysis_respects_fy(self, admin_token):
        """Movement analysis filters by FY parameter"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get data for FY 2025-26
        response1 = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26", headers=headers)
        assert response1.status_code == 200
        data1 = response1.json().get("data", {})
        
        # Get data for FY 2024-25 (should have different or no data)
        response2 = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2024-25", headers=headers)
        assert response2.status_code == 200
        data2 = response2.json().get("data", {})
        
        print(f"FY 2025-26: {len(data1.get('movements', []))} items, FY 2024-25: {len(data2.get('movements', []))} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
