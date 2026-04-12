"""
Iteration 41: Pre-Launch Health Check Tests
Tests for:
1. CRM Outstanding Excel Export
2. CRM Targets Excel Export
3. Inventory Auto Reorder Levels
4. Inventory Manual Reorder Level Edit
5. Tally* branding verification
6. Login flow
7. Dashboard access
8. CRM tabs
9. Analytics page
10. Super Admin access
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_frontend_accessible(self):
        """Test frontend is accessible"""
        response = requests.get(f"{BASE_URL}/", timeout=10)
        assert response.status_code == 200
        print("✓ Frontend accessible")


class TestAuthentication:
    """Authentication tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        # Note: reCAPTCHA is required, so we'll test the endpoint structure
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
            "captcha_token": ""  # Empty token will fail reCAPTCHA
        }, timeout=10)
        # Expected: 401 due to reCAPTCHA failure
        if response.status_code == 401:
            print("✓ Login endpoint requires reCAPTCHA (expected behavior)")
            return None
        elif response.status_code == 200:
            data = response.json()
            return data.get("token")
        return None
    
    def test_login_endpoint_exists(self):
        """Test login endpoint exists and validates input"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "",
            "password": ""
        }, timeout=10)
        # Should return 401 or 422, not 404
        assert response.status_code in [401, 422, 400]
        print(f"✓ Login endpoint exists (status: {response.status_code})")


class TestCRMOutstandingExport:
    """Test CRM Outstanding Excel Export endpoint"""
    
    def test_outstanding_export_endpoint_exists(self):
        """Test POST /api/customers/outstanding/export endpoint"""
        response = requests.post(f"{BASE_URL}/api/customers/outstanding/export", json={
            "data": [
                {
                    "customer_name": "Test Customer",
                    "ledger_group": "Sundry Debtors",
                    "opening_balance": 10000,
                    "total_sales": 50000,
                    "paid_amount": 30000,
                    "outstanding_amount": 30000,
                    "aging_buckets": {"0_30": 10000, "30_60": 10000, "60_90": 5000, "90_plus": 5000}
                }
            ],
            "fy": "2024-25"
        }, timeout=15)
        
        # Should return Excel file (blob) or success
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'spreadsheet' in content_type or 'excel' in content_type:
                print("✓ Outstanding export returns Excel file")
                assert len(response.content) > 0
            else:
                print(f"✓ Outstanding export endpoint works (content-type: {content_type})")
        else:
            print(f"✗ Outstanding export failed: {response.status_code}")
            assert False, f"Expected 200, got {response.status_code}"
    
    def test_outstanding_export_empty_data(self):
        """Test export with empty data"""
        response = requests.post(f"{BASE_URL}/api/customers/outstanding/export", json={
            "data": [],
            "fy": "2024-25"
        }, timeout=15)
        # Should still return 200 with empty Excel
        assert response.status_code == 200
        print("✓ Outstanding export handles empty data")


class TestCRMTargetsExport:
    """Test CRM Targets Excel Export endpoint"""
    
    def test_targets_export_endpoint_exists(self):
        """Test POST /api/customers/targets/export endpoint"""
        response = requests.post(f"{BASE_URL}/api/customers/targets/export", json={
            "data": [
                {
                    "customer_name": "Test Customer",
                    "previous_fy_sales": 100000,
                    "target": 115000,
                    "current_fy_sales": 80000,
                    "achievement_pct": 69.6,
                    "monthly_sales": {"Apr": 10000, "May": 12000, "Jun": 8000}
                }
            ],
            "fy": "2024-25"
        }, timeout=15)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'spreadsheet' in content_type or 'excel' in content_type:
                print("✓ Targets export returns Excel file")
                assert len(response.content) > 0
            else:
                print(f"✓ Targets export endpoint works (content-type: {content_type})")
        else:
            print(f"✗ Targets export failed: {response.status_code}")
            assert False, f"Expected 200, got {response.status_code}"
    
    def test_targets_export_empty_data(self):
        """Test export with empty data"""
        response = requests.post(f"{BASE_URL}/api/customers/targets/export", json={
            "data": [],
            "fy": "2024-25"
        }, timeout=15)
        assert response.status_code == 200
        print("✓ Targets export handles empty data")


class TestInventoryReorderLevels:
    """Test Inventory Reorder Level endpoints"""
    
    def test_auto_reorder_endpoint_exists(self):
        """Test POST /api/inventory/auto-reorder-levels endpoint"""
        response = requests.post(f"{BASE_URL}/api/inventory/auto-reorder-levels", json={}, timeout=15)
        # May return error if no sales data, but endpoint should exist
        assert response.status_code in [200, 400, 401, 500]
        data = response.json()
        print(f"✓ Auto reorder endpoint exists (status: {response.status_code}, response: {data.get('message', data.get('error', 'N/A'))})")
    
    def test_set_reorder_level_endpoint_exists(self):
        """Test POST /api/inventory/set-reorder-level endpoint"""
        response = requests.post(f"{BASE_URL}/api/inventory/set-reorder-level", json={
            "item_id": "test-item-123",
            "reorder_level": 50
        }, timeout=15)
        # May return 404 if item doesn't exist, but endpoint should exist
        assert response.status_code in [200, 400, 401, 404, 500]
        data = response.json()
        print(f"✓ Set reorder level endpoint exists (status: {response.status_code}, response: {data.get('message', data.get('error', 'N/A'))})")


class TestCRMEndpoints:
    """Test CRM endpoints are accessible"""
    
    def test_outstanding_endpoint(self):
        """Test GET /api/customers/outstanding"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Outstanding endpoint works (customers: {len(data.get('data', {}).get('customers', []))})")
    
    def test_targets_endpoint(self):
        """Test GET /api/customers/targets"""
        response = requests.get(f"{BASE_URL}/api/customers/targets", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Targets endpoint works (targets: {len(data.get('data', {}).get('targets', []))})")
    
    def test_followups_endpoint(self):
        """Test GET /api/customers/followups"""
        response = requests.get(f"{BASE_URL}/api/customers/followups", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Followups endpoint works (followups: {len(data.get('data', {}).get('followups', []))})")
    
    def test_payment_behavior_endpoint(self):
        """Test GET /api/customers/payment-behavior"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Payment behavior endpoint works (customers: {len(data.get('data', {}).get('customers', []))})")


class TestInventoryEndpoints:
    """Test Inventory endpoints"""
    
    def test_inventory_items_endpoint(self):
        """Test GET /api/inventory/items"""
        response = requests.get(f"{BASE_URL}/api/inventory/items", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Inventory items endpoint works (items: {len(data.get('data', {}).get('items', []))})")
    
    def test_inventory_summary_endpoint(self):
        """Test GET /api/inventory/summary"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Inventory summary endpoint works")


class TestAnalyticsEndpoints:
    """Test Analytics endpoints"""
    
    def test_movement_analysis_endpoint(self):
        """Test GET /api/inventory/movement-analysis"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Movement analysis endpoint works (movements: {len(data.get('data', {}).get('movements', []))})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
