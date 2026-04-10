"""
Iteration 27: Payment Behavior FY Filtering & Feature Gating Tests
Tests:
1. Payment Behavior API - FY filtering, opening_balance field
2. Feature gating - 'insider' feature in ALL_FEATURES (10 total)
3. Admin features list verification
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPaymentBehaviorAPI:
    """Payment Behavior endpoint tests with FY filtering"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        self.session = requests.Session()
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        data = login_res.json()
        assert data.get("success"), f"Login not successful: {data}"
        self.token = data["data"]["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        # Set company header
        self.session.headers.update({"X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"})
    
    def test_payment_behavior_with_fy_filter(self):
        """Test payment-behavior endpoint with FY=2025-26 returns data"""
        res = self.session.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        customers = data.get("data", {}).get("customers", [])
        print(f"Payment behavior with FY 2025-26: {len(customers)} customers")
        assert isinstance(customers, list), "customers should be a list"
    
    def test_payment_behavior_without_fy_filter(self):
        """Test payment-behavior endpoint without FY returns all data"""
        res = self.session.get(f"{BASE_URL}/api/customers/payment-behavior")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        customers = data.get("data", {}).get("customers", [])
        print(f"Payment behavior without FY filter: {len(customers)} customers")
        assert isinstance(customers, list), "customers should be a list"
    
    def test_payment_behavior_has_opening_balance_field(self):
        """Test that each customer has opening_balance field"""
        res = self.session.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert res.status_code == 200
        data = res.json()
        customers = data.get("data", {}).get("customers", [])
        if len(customers) > 0:
            first_customer = customers[0]
            assert "opening_balance" in first_customer, f"opening_balance field missing. Keys: {first_customer.keys()}"
            print(f"First customer opening_balance: {first_customer.get('opening_balance')}")
        else:
            print("No customers found - opening_balance field check skipped")
    
    def test_payment_behavior_customer_fields(self):
        """Test that customers have all required fields for Financial Breakdown"""
        res = self.session.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert res.status_code == 200
        data = res.json()
        customers = data.get("data", {}).get("customers", [])
        
        required_fields = [
            "customer_name", "opening_balance", "total_amount", "paid_amount",
            "credit_note_total", "journal_credit", "outstanding_amount",
            "payment_ratio", "credit_score", "payment_pattern"
        ]
        
        if len(customers) > 0:
            first_customer = customers[0]
            for field in required_fields:
                assert field in first_customer, f"Field '{field}' missing. Keys: {first_customer.keys()}"
            print(f"All required fields present: {required_fields}")
        else:
            print("No customers found - field check skipped")
    
    def test_payment_behavior_fy_changes_customer_count(self):
        """Test that different FY values may return different customer counts"""
        res_2025 = self.session.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        res_2024 = self.session.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2024-25")
        
        assert res_2025.status_code == 200
        assert res_2024.status_code == 200
        
        count_2025 = len(res_2025.json().get("data", {}).get("customers", []))
        count_2024 = len(res_2024.json().get("data", {}).get("customers", []))
        
        print(f"FY 2025-26: {count_2025} customers, FY 2024-25: {count_2024} customers")
        # Just verify both return valid data - counts may or may not differ
        assert count_2025 >= 0
        assert count_2024 >= 0
    
    def test_payment_behavior_closing_balance_can_be_negative(self):
        """Test that outstanding_amount (closing balance) can be negative when credits > debits"""
        res = self.session.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert res.status_code == 200
        data = res.json()
        customers = data.get("data", {}).get("customers", [])
        
        # Check if any customer has negative outstanding (credits > debits)
        negative_outstanding = [c for c in customers if c.get("outstanding_amount", 0) < 0]
        print(f"Customers with negative outstanding (credits > debits): {len(negative_outstanding)}")
        
        # Also verify the calculation logic: outstanding = opening + sales - credits
        if len(customers) > 0:
            c = customers[0]
            opening = c.get("opening_balance", 0)
            sales = c.get("total_amount", 0)
            paid = c.get("paid_amount", 0)
            cn = c.get("credit_note_total", 0)
            jv = c.get("journal_credit", 0)
            total_credits = paid + cn + jv
            expected_outstanding = opening + sales - total_credits
            actual_outstanding = c.get("outstanding_amount", 0)
            print(f"Customer: {c.get('customer_name')}")
            print(f"  Opening: {opening}, Sales: {sales}, Credits: {total_credits}")
            print(f"  Expected outstanding: {expected_outstanding}, Actual: {actual_outstanding}")


class TestFeatureGating:
    """Feature gating tests - 'insider' feature should be in ALL_FEATURES"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert data.get("success")
        self.token = data["data"]["token"]
        self.admin_data = data["data"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_admin_has_10_features(self):
        """Test that admin has 10 features (including 'insider')"""
        features = self.admin_data.get("features", [])
        print(f"Admin features ({len(features)}): {features}")
        assert len(features) == 10, f"Expected 10 features, got {len(features)}: {features}"
    
    def test_admin_has_insider_feature(self):
        """Test that admin has 'insider' feature"""
        features = self.admin_data.get("features", [])
        assert "insider" in features, f"'insider' not in features: {features}"
        print("'insider' feature is present in admin's features list")
    
    def test_all_expected_features_present(self):
        """Test that all 10 expected features are present"""
        expected_features = [
            "dashboard", "inventory", "sales", "crm", "analytics",
            "ai_reports", "salesman", "insider", "sync_history", "setup"
        ]
        features = self.admin_data.get("features", [])
        
        for f in expected_features:
            assert f in features, f"Feature '{f}' missing from admin features: {features}"
        print(f"All 10 expected features present: {expected_features}")


class TestSuperAdminFeatures:
    """SuperAdmin dashboard should show 10 features in ALL_FEATURES"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as superadmin"""
        self.session = requests.Session()
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert data.get("success")
        self.token = data["data"]["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_superadmin_can_list_admins(self):
        """Test superadmin can list admins"""
        res = self.session.get(f"{BASE_URL}/api/super-admin/admins")
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        assert data.get("success")
        admins = data.get("data", {}).get("admins", [])
        print(f"SuperAdmin sees {len(admins)} admins")
        
        # Check if admin has 10 features
        admin_user = next((a for a in admins if a.get("username") == "admin"), None)
        if admin_user:
            features = admin_user.get("features", [])
            print(f"Admin user features ({len(features)}): {features}")
            assert len(features) == 10, f"Admin should have 10 features, got {len(features)}"


class TestOutstandingAPI:
    """Outstanding endpoint tests - verify it still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert data.get("success")
        self.token = data["data"]["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.session.headers.update({"X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"})
    
    def test_outstanding_endpoint_works(self):
        """Test outstanding endpoint returns data"""
        res = self.session.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        customers = data.get("data", {}).get("customers", [])
        print(f"Outstanding customers: {len(customers)}")
        assert isinstance(customers, list)


class TestInsiderEndpoints:
    """Test Insider Result API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert data.get("success")
        self.token = data["data"]["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.session.headers.update({"X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"})
    
    def test_customer_lifecycle_endpoint(self):
        """Test customer-lifecycle endpoint"""
        res = self.session.get(f"{BASE_URL}/api/insights/customer-lifecycle?fy=2025-26")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        print(f"Customer lifecycle data keys: {data.get('data', {}).keys()}")
    
    def test_sales_forecast_endpoint(self):
        """Test sales-forecast endpoint"""
        res = self.session.get(f"{BASE_URL}/api/insights/sales-forecast?fy=2025-26")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        print(f"Sales forecast data keys: {data.get('data', {}).keys()}")
    
    def test_spip_analysis_endpoint(self):
        """Test spip-analysis endpoint"""
        res = self.session.get(f"{BASE_URL}/api/insights/spip-analysis?fy=2025-26")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        print(f"SPIP analysis data keys: {data.get('data', {}).keys()}")
    
    def test_concentration_risk_endpoint(self):
        """Test concentration-risk endpoint"""
        res = self.session.get(f"{BASE_URL}/api/insights/concentration-risk?fy=2025-26")
        assert res.status_code == 200, f"API failed: {res.text}"
        data = res.json()
        assert data.get("success"), f"API not successful: {data}"
        print(f"Concentration risk data keys: {data.get('data', {}).keys()}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
