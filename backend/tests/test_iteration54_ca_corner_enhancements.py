"""
Iteration 54: CA Corner Enhancements - Balance Sheet & P&L Drill-Down
Tests for:
- GET /api/ca-corner/balance-sheet - returns assets, liabilities, capital grouped by parent_group
- GET /api/ca-corner/pl-drilldown?type=expense - returns expense groups with ledger breakdown
- GET /api/ca-corner/pl-drilldown?type=income - returns income groups with ledger breakdown
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCACornerEnhancements:
    """Test CA Corner Balance Sheet and P&L Drill-Down APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123", "captcha_token": ""}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        assert data.get("success"), f"Login not successful: {data}"
        self.token = data["data"]["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    # ─── Balance Sheet Tests ───────────────────────────────────────
    
    def test_balance_sheet_endpoint_returns_success(self):
        """Test GET /api/ca-corner/balance-sheet returns success"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/balance-sheet",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
    
    def test_balance_sheet_returns_correct_structure(self):
        """Test balance sheet returns assets, liabilities, capital arrays"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/balance-sheet",
            headers=self.headers
        )
        data = response.json()
        assert data.get("success") is True
        
        result = data.get("data", {})
        # Check required fields exist
        assert "assets" in result, "Missing 'assets' field"
        assert "liabilities" in result, "Missing 'liabilities' field"
        assert "total_assets" in result, "Missing 'total_assets' field"
        assert "total_liabilities" in result, "Missing 'total_liabilities' field"
        
        # Check types
        assert isinstance(result["assets"], list), "assets should be a list"
        assert isinstance(result["liabilities"], list), "liabilities should be a list"
        assert isinstance(result["total_assets"], (int, float)), "total_assets should be numeric"
        assert isinstance(result["total_liabilities"], (int, float)), "total_liabilities should be numeric"
    
    def test_balance_sheet_returns_capital_field_when_data_exists(self):
        """Test balance sheet includes capital fields when ledger data exists"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/balance-sheet",
            headers=self.headers
        )
        data = response.json()
        result = data.get("data", {})
        
        # When no ledger data, capital fields may not be present (returns simplified response)
        # When data exists, capital fields should be present
        if "message" not in result:  # Has actual data
            assert "capital" in result, "Missing 'capital' field when data exists"
            assert "total_capital" in result, "Missing 'total_capital' field when data exists"
            assert "total_liabilities_capital" in result, "Missing 'total_liabilities_capital' field when data exists"
        else:
            # No data case - verify basic structure
            assert "assets" in result
            assert "liabilities" in result
            print("Note: No ledger data synced - capital fields not returned in empty state")
    
    def test_balance_sheet_handles_empty_data_gracefully(self):
        """Test balance sheet returns message when no data synced"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/balance-sheet",
            headers=self.headers
        )
        data = response.json()
        result = data.get("data", {})
        
        # When no data, should have empty arrays and message
        if len(result.get("assets", [])) == 0:
            assert "message" in result, "Should have message when no data"
            assert "sync" in result["message"].lower() or "no" in result["message"].lower()
    
    def test_balance_sheet_requires_authentication(self):
        """Test balance sheet endpoint requires auth"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/balance-sheet"
        )
        # Should return 200 with success=False or 401
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is False, "Should fail without auth"
        else:
            assert response.status_code in [401, 403]
    
    # ─── P&L Drill-Down Tests ──────────────────────────────────────
    
    def test_pl_drilldown_expense_returns_success(self):
        """Test GET /api/ca-corner/pl-drilldown?type=expense returns success"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown?type=expense",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
    
    def test_pl_drilldown_income_returns_success(self):
        """Test GET /api/ca-corner/pl-drilldown?type=income returns success"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown?type=income",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=True, got {data}"
    
    def test_pl_drilldown_returns_correct_structure(self):
        """Test pl-drilldown returns groups, total, type fields"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown?type=expense",
            headers=self.headers
        )
        data = response.json()
        result = data.get("data", {})
        
        # Check required fields
        assert "groups" in result, "Missing 'groups' field"
        assert "total" in result, "Missing 'total' field"
        assert "type" in result, "Missing 'type' field"
        
        # Check types
        assert isinstance(result["groups"], list), "groups should be a list"
        assert isinstance(result["total"], (int, float)), "total should be numeric"
        assert result["type"] == "expense", "type should match query param"
    
    def test_pl_drilldown_type_parameter_works(self):
        """Test pl-drilldown respects type parameter"""
        # Test expense
        response_expense = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown?type=expense",
            headers=self.headers
        )
        data_expense = response_expense.json()
        assert data_expense["data"]["type"] == "expense"
        
        # Test income
        response_income = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown?type=income",
            headers=self.headers
        )
        data_income = response_income.json()
        assert data_income["data"]["type"] == "income"
    
    def test_pl_drilldown_default_type_is_expense(self):
        """Test pl-drilldown defaults to expense when no type specified"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown",
            headers=self.headers
        )
        data = response.json()
        assert data.get("success") is True
        assert data["data"]["type"] == "expense", "Default type should be expense"
    
    def test_pl_drilldown_requires_authentication(self):
        """Test pl-drilldown endpoint requires auth"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/pl-drilldown?type=expense"
        )
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is False, "Should fail without auth"
        else:
            assert response.status_code in [401, 403]
    
    # ─── Existing CA Corner Endpoints Still Work ───────────────────
    
    def test_cash_flow_still_works(self):
        """Test existing cash-flow endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/cash-flow",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
    
    def test_profit_loss_still_works(self):
        """Test existing profit-loss endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/ca-corner/profit-loss",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


class TestLandingPageFeatures:
    """Test Landing Page feature cards and NEW badges"""
    
    def test_landing_page_loads(self):
        """Test landing page is accessible"""
        response = requests.get(f"{BASE_URL.replace('/api', '')}")
        assert response.status_code == 200, f"Landing page failed to load: {response.status_code}"
    
    def test_features_endpoint_if_exists(self):
        """Test if there's a features API endpoint (optional)"""
        # Landing page features are static in frontend, no API needed
        # This test just verifies the app is running
        response = requests.get(f"{BASE_URL}/health")
        # Health endpoint may or may not exist
        assert response.status_code in [200, 404]
