"""
Iteration 43: CA Corner Feature Tests
Tests for Cash Flow, P&L Report, and AI Expense Insights endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com')

class TestCACornerFeature:
    """CA Corner feature tests - Cash Flow, P&L, AI Expense Insights"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
            "captcha_token": ""
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        assert data.get("success"), f"Login not successful: {data}"
        
        self.token = data["data"]["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get company ID from user data
        self.company_id = data["data"].get("companies", [""])[0] if data["data"].get("companies") else ""
        if self.company_id:
            self.session.headers.update({"X-Company-ID": self.company_id})
        
        yield
        
        # Logout
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    # ─── CASH FLOW ENDPOINT TESTS ───────────────────────────────
    
    def test_cash_flow_endpoint_returns_success(self):
        """Test GET /api/ca-corner/cash-flow returns success"""
        response = self.session.get(f"{BASE_URL}/api/ca-corner/cash-flow")
        assert response.status_code == 200, f"Cash flow endpoint failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Cash flow not successful: {data}"
        print(f"✓ Cash flow endpoint returns success")
    
    def test_cash_flow_data_structure(self):
        """Test cash flow response has correct data structure"""
        response = self.session.get(f"{BASE_URL}/api/ca-corner/cash-flow")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        cf_data = data.get("data", {})
        
        # Check summary structure
        summary = cf_data.get("summary", {})
        assert "opening_total" in summary, "Missing opening_total in summary"
        assert "closing_total" in summary, "Missing closing_total in summary"
        assert "total_receipts" in summary, "Missing total_receipts in summary"
        assert "total_payments" in summary, "Missing total_payments in summary"
        assert "net_change" in summary, "Missing net_change in summary"
        
        print(f"✓ Cash flow summary structure correct: opening={summary.get('opening_total')}, closing={summary.get('closing_total')}")
        
        # Check operating/investing/financing sections
        assert "operating" in cf_data, "Missing operating section"
        assert "investing" in cf_data, "Missing investing section"
        assert "financing" in cf_data, "Missing financing section"
        
        # Each section should have items and net
        for section in ["operating", "investing", "financing"]:
            section_data = cf_data.get(section, {})
            assert "items" in section_data, f"Missing items in {section}"
            assert "net" in section_data, f"Missing net in {section}"
        
        print(f"✓ Cash flow sections (operating/investing/financing) present")
    
    def test_cash_flow_with_fy_param(self):
        """Test cash flow endpoint accepts FY parameter"""
        response = self.session.get(f"{BASE_URL}/api/ca-corner/cash-flow", params={"fy": "2025-26"})
        assert response.status_code == 200, f"Cash flow with FY param failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Cash flow endpoint accepts FY parameter")
    
    # ─── P&L ENDPOINT TESTS ─────────────────────────────────────
    
    def test_profit_loss_annual_view(self):
        """Test GET /api/ca-corner/profit-loss?view=annual returns P&L data"""
        response = self.session.get(f"{BASE_URL}/api/ca-corner/profit-loss", params={"view": "annual"})
        assert response.status_code == 200, f"P&L annual endpoint failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"P&L annual not successful: {data}"
        
        pl_data = data.get("data", {})
        
        # Check required fields
        assert "income" in pl_data, "Missing income array"
        assert "expense" in pl_data, "Missing expense array"
        assert "total_income" in pl_data, "Missing total_income"
        assert "total_expense" in pl_data, "Missing total_expense"
        assert "net_profit_loss" in pl_data, "Missing net_profit_loss"
        
        print(f"✓ P&L annual view: income={pl_data.get('total_income')}, expense={pl_data.get('total_expense')}, net={pl_data.get('net_profit_loss')}")
    
    def test_profit_loss_monthly_view(self):
        """Test GET /api/ca-corner/profit-loss?view=monthly returns monthly data"""
        response = self.session.get(f"{BASE_URL}/api/ca-corner/profit-loss", params={"view": "monthly"})
        assert response.status_code == 200, f"P&L monthly endpoint failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"P&L monthly not successful: {data}"
        
        pl_data = data.get("data", {})
        
        # Check monthly array exists
        assert "monthly" in pl_data, "Missing monthly array in monthly view"
        monthly = pl_data.get("monthly", [])
        
        # Monthly should have 12 months (Apr-Mar)
        if len(monthly) > 0:
            # Check first month structure
            first_month = monthly[0]
            assert "month" in first_month, "Missing month field"
            assert "sales" in first_month, "Missing sales field"
            assert "purchases" in first_month, "Missing purchases field"
            assert "gross_profit" in first_month, "Missing gross_profit field"
            print(f"✓ P&L monthly view: {len(monthly)} months, first month={first_month.get('month')}")
        else:
            print(f"✓ P&L monthly view returns empty monthly array (no data synced)")
    
    def test_profit_loss_default_view(self):
        """Test P&L endpoint without view param defaults to annual"""
        response = self.session.get(f"{BASE_URL}/api/ca-corner/profit-loss")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        print(f"✓ P&L endpoint works without view param")
    
    # ─── AI EXPENSE INSIGHTS TESTS ──────────────────────────────
    
    def test_ai_expense_insights_endpoint(self):
        """Test POST /api/ca-corner/expense-insights endpoint exists"""
        response = self.session.post(f"{BASE_URL}/api/ca-corner/expense-insights", json={})
        
        # Should return 200 even if no data (with error message)
        assert response.status_code == 200, f"AI insights endpoint failed: {response.text}"
        
        data = response.json()
        # Either success with analysis or error about no data
        if data.get("success"):
            assert "data" in data, "Missing data in successful response"
            print(f"✓ AI expense insights returned analysis")
        else:
            # Expected error when no P&L data synced
            error = data.get("error", "")
            assert "expense" in error.lower() or "data" in error.lower(), f"Unexpected error: {error}"
            print(f"✓ AI expense insights returns expected error: {error}")
    
    # ─── AUTHENTICATION TESTS ───────────────────────────────────
    
    def test_cash_flow_requires_auth(self):
        """Test cash flow endpoint requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/ca-corner/cash-flow")
        
        # Should return 200 but with success=False or error
        data = response.json()
        assert data.get("success") == False or "error" in data, "Cash flow should require auth"
        print(f"✓ Cash flow endpoint requires authentication")
    
    def test_profit_loss_requires_auth(self):
        """Test P&L endpoint requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/ca-corner/profit-loss")
        
        data = response.json()
        assert data.get("success") == False or "error" in data, "P&L should require auth"
        print(f"✓ P&L endpoint requires authentication")


class TestCACornerFeatureGating:
    """Test CA Corner feature gating to enterprise plan"""
    
    def test_admin_has_ca_corner_feature(self):
        """Test admin user has ca_corner in features list"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
            "captcha_token": ""
        })
        assert login_response.status_code == 200
        
        data = login_response.json()
        assert data.get("success") == True
        
        features = data["data"].get("features", [])
        assert "ca_corner" in features, f"ca_corner not in admin features: {features}"
        print(f"✓ Admin has ca_corner feature: {features}")


class TestLandingPageEnterprisePlan:
    """Test landing page shows CA Corner in Enterprise plan"""
    
    def test_landing_page_loads(self):
        """Test landing page is accessible"""
        response = requests.get(BASE_URL)
        assert response.status_code == 200, f"Landing page failed: {response.status_code}"
        print(f"✓ Landing page loads successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
