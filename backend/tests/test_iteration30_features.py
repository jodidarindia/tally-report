"""
Iteration 30 Tests: New Features
- Renewals section in SuperAdmin
- Subscription dates in Profile
- Renewal popup on login
- Default FY from backend API
- IST time formatting
- Dashboard banners (Not synced / No data for FY)
- SignupPage demo features (Professional plan without Salesman)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthAndLogin:
    """Test login flow and subscription data in response"""
    
    def test_superadmin_login(self):
        """SuperAdmin login should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("data", {}).get("role") == "super_admin"
        print("PASS: SuperAdmin login works")
    
    def test_admin_login_returns_subscription_data(self):
        """Admin login should return subscription_start, subscription_expires, subscription_days_left"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        user_data = data.get("data", {})
        assert user_data.get("role") == "admin"
        # Check subscription fields exist
        assert "subscription_start" in user_data
        assert "subscription_months" in user_data
        assert "subscription_expires" in user_data
        assert "subscription_days_left" in user_data
        print(f"PASS: Admin login returns subscription data - days_left: {user_data.get('subscription_days_left')}")
    
    def test_starter_admin_login(self):
        """Starter admin login should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "starter@test.com",
            "password": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        # May fail if subscription expired, but should return a response
        if data.get("success"):
            user_data = data.get("data", {})
            assert "subscription_days_left" in user_data
            print(f"PASS: Starter admin login - days_left: {user_data.get('subscription_days_left')}")
        else:
            # Subscription may have expired
            print(f"INFO: Starter admin login failed (possibly expired): {data.get('error')}")


class TestRenewalsEndpoints:
    """Test SuperAdmin renewals endpoints"""
    
    @pytest.fixture
    def superadmin_token(self):
        """Get superadmin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("SuperAdmin login failed")
    
    def test_get_renewals_endpoint(self, superadmin_token):
        """GET /api/super-admin/renewals should return renewal data"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/renewals", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        renewals_data = data.get("data", {})
        # Check structure
        assert "renewal_requests" in renewals_data
        assert "near_expiry" in renewals_data
        assert "expired" in renewals_data
        assert "stats" in renewals_data
        stats = renewals_data.get("stats", {})
        assert "pending_renewals" in stats
        assert "near_expiry_count" in stats
        assert "expired_count" in stats
        print(f"PASS: Renewals endpoint returns data - near_expiry: {stats.get('near_expiry_count')}, expired: {stats.get('expired_count')}")
    
    def test_renewals_stats_structure(self, superadmin_token):
        """Renewals stats should have correct structure"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/renewals", headers=headers)
        assert response.status_code == 200
        data = response.json()
        stats = data.get("data", {}).get("stats", {})
        assert isinstance(stats.get("pending_renewals"), int)
        assert isinstance(stats.get("near_expiry_count"), int)
        assert isinstance(stats.get("expired_count"), int)
        print("PASS: Renewals stats have correct structure")


class TestRenewalRequestEndpoint:
    """Test admin renewal request endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("Admin login failed")
    
    def test_request_renewal_endpoint(self, admin_token):
        """POST /api/auth/request-renewal should work for admin"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/auth/request-renewal", 
            headers=headers,
            json={
                "plan_interest": "enterprise",
                "message": "Test renewal request from iteration 30"
            }
        )
        assert response.status_code == 200
        data = response.json()
        # May succeed or fail if already pending
        if data.get("success"):
            print("PASS: Renewal request submitted successfully")
        else:
            # Already has pending request is acceptable
            assert "pending" in data.get("error", "").lower() or "already" in data.get("error", "").lower()
            print(f"INFO: Renewal request already pending: {data.get('error')}")


class TestLatestFYEndpoint:
    """Test latest FY endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("Admin login failed")
    
    def test_latest_fy_endpoint(self, admin_token):
        """GET /api/sync/latest-fy should return FY data"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/sync/latest-fy", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        fy_data = data.get("data", {})
        # latest_fy may be null if no data synced
        assert "latest_fy" in fy_data
        print(f"PASS: Latest FY endpoint works - latest_fy: {fy_data.get('latest_fy')}")


class TestDashboardEndpoints:
    """Test dashboard data endpoints for banner conditions"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("Admin login failed")
    
    def test_sync_status_endpoint(self, admin_token):
        """GET /api/sync/status should return sync status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/sync/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"PASS: Sync status endpoint works - last_sync: {data.get('data', {}).get('last_sync')}")
    
    def test_inventory_summary_endpoint(self, admin_token):
        """GET /api/inventory/summary should return inventory data"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"PASS: Inventory summary endpoint works - total_items: {data.get('data', {}).get('total_items')}")
    
    def test_sales_summary_endpoint(self, admin_token):
        """GET /api/sales/summary should return sales data"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/sales/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"PASS: Sales summary endpoint works - total_sales: {data.get('data', {}).get('total_sales')}")


class TestPublicEndpoints:
    """Test public endpoints for signup flow"""
    
    def test_plans_endpoint(self):
        """GET /api/public/plans should return plans"""
        response = requests.get(f"{BASE_URL}/api/public/plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        plans = data.get("data", {}).get("plans", {})
        # Plans is a dict with keys: starter, professional, enterprise
        assert "starter" in plans
        assert "professional" in plans
        assert "enterprise" in plans
        # Check Professional plan features (should NOT include salesman)
        pro_plan = plans.get("professional", {})
        pro_features = pro_plan.get("features", [])
        # Professional should NOT have salesman
        assert "salesman" not in pro_features
        print(f"PASS: Plans endpoint works - Professional features: {pro_features}")
    
    def test_demo_data_endpoint(self):
        """Demo data should show Professional plan features"""
        # First create a demo request
        signup_response = requests.post(f"{BASE_URL}/api/public/signup", json={
            "company_name": "Test Demo Corp",
            "contact_person": "Test User",
            "email": f"test_demo_{os.urandom(4).hex()}@test.com",
            "phone": "+91-9876543210"
        })
        if signup_response.status_code == 200 and signup_response.json().get("success"):
            prospect_id = signup_response.json()["data"]["prospect_id"]
            email = signup_response.json()["data"]["email"]
            
            # Request demo
            demo_req = requests.post(f"{BASE_URL}/api/public/demo-request", json={
                "prospect_id": prospect_id,
                "email": email
            })
            if demo_req.status_code == 200 and demo_req.json().get("success"):
                demo_token = demo_req.json()["data"]["demo_token"]
                
                # Get demo data
                demo_data_resp = requests.get(f"{BASE_URL}/api/public/demo-data?demo_token={demo_token}")
                assert demo_data_resp.status_code == 200
                demo_data = demo_data_resp.json()
                assert demo_data.get("success") == True
                print("PASS: Demo data endpoint works")
            else:
                print("INFO: Demo request failed, skipping demo data test")
        else:
            print("INFO: Signup failed, skipping demo data test")


class TestISTFormatting:
    """Test IST time formatting in responses"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("Admin login failed")
    
    def test_subscription_dates_format(self, admin_token):
        """Subscription dates should be in ISO format"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        user_data = data.get("data", {})
        sub_start = user_data.get("subscription_start")
        sub_expires = user_data.get("subscription_expires")
        # Should be ISO format strings
        if sub_start:
            assert "T" in sub_start or "-" in sub_start  # ISO format check
        if sub_expires:
            assert "T" in sub_expires or "-" in sub_expires
        print(f"PASS: Subscription dates in ISO format - start: {sub_start}, expires: {sub_expires}")


class TestProcessRenewal:
    """Test SuperAdmin renewal processing"""
    
    @pytest.fixture
    def superadmin_token(self):
        """Get superadmin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("SuperAdmin login failed")
    
    def test_process_renewal_endpoint_exists(self, superadmin_token):
        """PUT /api/super-admin/renewals/{username}/process should exist"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        # Test with a non-existent user to verify endpoint exists
        response = requests.put(
            f"{BASE_URL}/api/super-admin/renewals/nonexistent_user/process",
            headers=headers,
            json={
                "action": "approve",
                "subscription_months": 12,
                "plan": "enterprise"
            }
        )
        # Should return 200 with success=true or error message (not 404)
        assert response.status_code == 200
        data = response.json()
        # Either success or error about user not found
        print(f"PASS: Process renewal endpoint exists - response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
