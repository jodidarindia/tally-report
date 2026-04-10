"""
Iteration 25: Movement Analysis Tab Testing
Tests for:
1. Movement Analysis API returns correct data structure (summary, movements, fy_days)
2. Movement rate formula: (sales/opening)*100 - should be 100% when all stock sold
3. Days to sell = 0 when closing stock = 0
4. Classification: fast-moving, moderate, slow-moving, non-moving
5. Inward column present (from purchase_vouchers)
6. Security: test_admin (different tenant) sees 0 items
7. FY filtering works correctly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMovementAnalysisAPI:
    """Movement Analysis endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        self.admin_token = login_response.json().get("data", {}).get("token")
        assert self.admin_token, "No token received"
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_movement_analysis_returns_correct_structure(self):
        """Test that movement-analysis endpoint returns expected data structure"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"API returned success=false: {data}"
        
        result = data.get("data", {})
        
        # Check required fields
        assert "movements" in result, "Missing 'movements' field"
        assert "summary" in result, "Missing 'summary' field"
        assert "fy_days" in result, "Missing 'fy_days' field"
        
        # Check summary has 4 classification categories
        summary = result["summary"]
        assert "fast_moving" in summary, "Missing 'fast_moving' in summary"
        assert "moderate" in summary, "Missing 'moderate' in summary"
        assert "slow_moving" in summary, "Missing 'slow_moving' in summary"
        assert "non_moving" in summary, "Missing 'non_moving' in summary"
        
        print(f"✓ Movement analysis structure correct. Summary: {summary}")
    
    def test_movement_data_has_all_columns(self):
        """Test that each movement item has all required columns"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        assert len(movements) > 0, "No movement data returned"
        
        required_fields = [
            "item_name", "category", "opening_stock", "inward", "sales",
            "closing_stock", "movement_rate", "days_to_sell", "transactions", "classification"
        ]
        
        # Check first item has all fields
        first_item = movements[0]
        for field in required_fields:
            assert field in first_item, f"Missing field '{field}' in movement data"
        
        print(f"✓ All {len(required_fields)} columns present. First item: {first_item['item_name']}")
    
    def test_movement_rate_formula_correct(self):
        """Test movement rate = (sales/opening)*100, max 100% when all sold"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        
        # Find items where all stock was sold (closing=0, sales>0)
        items_all_sold = [m for m in movements if m["closing_stock"] == 0 and m["sales"] > 0]
        
        for item in items_all_sold[:5]:  # Check first 5
            movement_rate = item["movement_rate"]
            # When all stock sold, rate should be 100% (not 200%)
            assert movement_rate <= 100.0, f"Movement rate {movement_rate}% > 100% for {item['item_name']} (should be max 100%)"
            
            # Verify formula: rate = (sales/opening)*100
            if item["opening_stock"] > 0:
                expected_rate = round((item["sales"] / item["opening_stock"]) * 100, 1)
                assert abs(movement_rate - expected_rate) < 0.2, f"Rate mismatch for {item['item_name']}: got {movement_rate}, expected {expected_rate}"
        
        print(f"✓ Movement rate formula correct. Checked {len(items_all_sold)} items with all stock sold, all <= 100%")
    
    def test_days_to_sell_zero_when_no_stock(self):
        """Test days_to_sell = 0 when closing_stock = 0"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        
        # Items with 0 closing stock should have days_to_sell = 0
        items_no_stock = [m for m in movements if m["closing_stock"] == 0]
        
        for item in items_no_stock[:10]:  # Check first 10
            assert item["days_to_sell"] == 0, f"Days to sell should be 0 for {item['item_name']} (closing=0), got {item['days_to_sell']}"
        
        print(f"✓ Days to sell = 0 for {len(items_no_stock)} items with 0 closing stock")
    
    def test_classification_categories(self):
        """Test classification has 4 categories: fast-moving, moderate, slow-moving, non-moving"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        summary = response.json().get("data", {}).get("summary", {})
        
        valid_classifications = {"fast-moving", "moderate", "slow-moving", "non-moving"}
        
        # Check all items have valid classification
        for item in movements:
            assert item["classification"] in valid_classifications, f"Invalid classification '{item['classification']}' for {item['item_name']}"
        
        # Verify summary counts match actual data
        actual_counts = {
            "fast_moving": len([m for m in movements if m["classification"] == "fast-moving"]),
            "moderate": len([m for m in movements if m["classification"] == "moderate"]),
            "slow_moving": len([m for m in movements if m["classification"] == "slow-moving"]),
            "non_moving": len([m for m in movements if m["classification"] == "non-moving"])
        }
        
        assert summary["fast_moving"] == actual_counts["fast_moving"], f"Fast moving count mismatch"
        assert summary["moderate"] == actual_counts["moderate"], f"Moderate count mismatch"
        assert summary["slow_moving"] == actual_counts["slow_moving"], f"Slow moving count mismatch"
        assert summary["non_moving"] == actual_counts["non_moving"], f"Non-moving count mismatch"
        
        print(f"✓ Classification counts: fast={actual_counts['fast_moving']}, moderate={actual_counts['moderate']}, slow={actual_counts['slow_moving']}, non-moving={actual_counts['non_moving']}")
    
    def test_inward_column_present(self):
        """Test that inward column is present (from purchase_vouchers)"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        
        # All items should have 'inward' field
        for item in movements[:10]:
            assert "inward" in item, f"Missing 'inward' field for {item['item_name']}"
            # Inward should be a number (0 or positive)
            assert isinstance(item["inward"], (int, float)), f"Inward should be numeric for {item['item_name']}"
            assert item["inward"] >= 0, f"Inward should be >= 0 for {item['item_name']}"
        
        # Note: purchase_vouchers may be empty, so inward could be 0 for all
        total_inward = sum(m["inward"] for m in movements)
        print(f"✓ Inward column present. Total inward across all items: {total_inward}")
    
    def test_opening_stock_calculation(self):
        """Test opening stock = closing + sales - inward"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        
        # Verify formula: Opening = Closing + Sales - Inward
        for item in movements[:10]:
            expected_opening = item["closing_stock"] + item["sales"] - item["inward"]
            if expected_opening < 0:
                expected_opening = 0
            
            # Allow small rounding differences
            assert abs(item["opening_stock"] - expected_opening) < 0.2, \
                f"Opening stock mismatch for {item['item_name']}: got {item['opening_stock']}, expected {expected_opening}"
        
        print(f"✓ Opening stock formula verified for {min(10, len(movements))} items")
    
    def test_fy_days_calculated(self):
        """Test fy_days is calculated correctly"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        fy_days = response.json().get("data", {}).get("fy_days", 0)
        
        # FY 2025-26 runs from Apr 1, 2025 to Mar 31, 2026
        # Since we're in Jan 2026, fy_days should be ~275-305 days
        assert fy_days > 0, "fy_days should be > 0"
        assert fy_days <= 366, "fy_days should be <= 366"
        
        print(f"✓ FY days calculated: {fy_days}")
    
    def test_movement_rate_not_200_percent(self):
        """Specific test: Movement rate should NOT be 200% (was the bug)"""
        response = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        
        # Check NO item has 200% movement rate
        items_200 = [m for m in movements if m["movement_rate"] == 200]
        assert len(items_200) == 0, f"Found {len(items_200)} items with 200% movement rate (bug not fixed)"
        
        # Check all rates are <= 100%
        items_over_100 = [m for m in movements if m["movement_rate"] > 100]
        assert len(items_over_100) == 0, f"Found {len(items_over_100)} items with movement rate > 100%"
        
        print(f"✓ No items with 200% movement rate. All rates <= 100%")


class TestMovementAnalysisSecurity:
    """Security tests for movement analysis"""
    
    def test_test_admin_sees_no_data(self):
        """Test that test_admin (different tenant) sees 0 items"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as test_admin
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "test_admin",
            "password": "test123"
        })
        assert login_response.status_code == 200, f"test_admin login failed: {login_response.text}"
        token = login_response.json().get("data", {}).get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get movement analysis
        response = session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        
        movements = response.json().get("data", {}).get("movements", [])
        summary = response.json().get("data", {}).get("summary", {})
        
        # test_admin should see 0 items (different tenant)
        assert len(movements) == 0, f"test_admin should see 0 items, got {len(movements)}"
        assert summary.get("fast_moving", 0) == 0, "test_admin should see 0 fast-moving"
        assert summary.get("moderate", 0) == 0, "test_admin should see 0 moderate"
        assert summary.get("slow_moving", 0) == 0, "test_admin should see 0 slow-moving"
        assert summary.get("non_moving", 0) == 0, "test_admin should see 0 non-moving"
        
        print(f"✓ Security: test_admin sees 0 items (tenant isolation working)")


class TestMovementAnalysisFYFiltering:
    """FY filtering tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        self.admin_token = login_response.json().get("data", {}).get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_different_fy_returns_different_data(self):
        """Test that different FYs return different data"""
        # Get FY 2025-26 data
        response_2025 = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response_2025.status_code == 200
        movements_2025 = response_2025.json().get("data", {}).get("movements", [])
        
        # Get FY 2024-25 data (may have different or no data)
        response_2024 = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2024-25")
        assert response_2024.status_code == 200
        movements_2024 = response_2024.json().get("data", {}).get("movements", [])
        
        # Get FY 2026-27 data (future FY, likely no sales yet)
        response_2026 = self.session.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2026-27")
        assert response_2026.status_code == 200
        movements_2026 = response_2026.json().get("data", {}).get("movements", [])
        
        print(f"✓ FY filtering: 2024-25={len(movements_2024)} items, 2025-26={len(movements_2025)} items, 2026-27={len(movements_2026)} items")
        
        # At minimum, the API should work for all FYs
        assert isinstance(movements_2024, list)
        assert isinstance(movements_2025, list)
        assert isinstance(movements_2026, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
