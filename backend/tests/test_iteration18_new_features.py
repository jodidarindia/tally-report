"""
Iteration 18 Tests: New Features
- PUT /api/super-admin/admins/{username}/subscription endpoint
- GET /api/sync/connection-status endpoint
- Login and authentication
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Test login endpoints for all user types"""
    
    def test_superadmin_login(self):
        """Super admin login with superadmin/superadmin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "token" in data.get("data", {})
        assert data["data"]["user"]["role"] == "super_admin"
        return data["data"]["token"]
    
    def test_admin_login(self):
        """Admin login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "token" in data.get("data", {})
        assert data["data"]["user"]["role"] == "admin"
        return data["data"]["token"]
    
    def test_test_admin_login(self):
        """Test admin login with test_admin/test123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "test_admin",
            "password": "test123"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "token" in data.get("data", {})


class TestSubscriptionEndpoint:
    """Test PUT /api/super-admin/admins/{username}/subscription"""
    
    @pytest.fixture
    def superadmin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        return response.json()["data"]["token"]
    
    def test_update_subscription_name(self, superadmin_token):
        """Update admin name via subscription endpoint"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.put(
            f"{BASE_URL}/api/super-admin/admins/admin/subscription",
            json={"name": "Test Admin Name"},
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Revert name
        requests.put(
            f"{BASE_URL}/api/super-admin/admins/admin/subscription",
            json={"name": "Admin"},
            headers=headers
        )
    
    def test_update_subscription_months(self, superadmin_token):
        """Update admin subscription months"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.put(
            f"{BASE_URL}/api/super-admin/admins/admin/subscription",
            json={"subscription_months": 24},
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Revert to 12 months
        requests.put(
            f"{BASE_URL}/api/super-admin/admins/admin/subscription",
            json={"subscription_months": 12},
            headers=headers
        )
    
    def test_update_subscription_nonexistent_admin(self, superadmin_token):
        """Update subscription for non-existent admin should fail"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.put(
            f"{BASE_URL}/api/super-admin/admins/nonexistent_admin_xyz/subscription",
            json={"name": "Test"},
            headers=headers
        )
        assert response.status_code == 200  # API returns 200 with success=False
        data = response.json()
        assert data.get("success") == False
        assert "not found" in data.get("error", "").lower()
    
    def test_update_subscription_without_auth(self):
        """Update subscription without auth should fail"""
        response = requests.put(
            f"{BASE_URL}/api/super-admin/admins/admin/subscription",
            json={"name": "Test"}
        )
        # Should fail without auth
        data = response.json()
        assert data.get("success") == False


class TestConnectionStatusEndpoint:
    """Test GET /api/sync/connection-status"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        return response.json()["data"]["token"]
    
    def test_connection_status_returns_data(self, admin_token):
        """Connection status endpoint returns expected structure"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/sync/connection-status",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        # Check data structure if data exists
        if data.get("data"):
            result = data["data"]
            # Should have these keys (values may be null/empty)
            assert "last_sync" in result or result is None
            assert "agent_version" in result or result is None
            assert "companies" in result or result is None
            assert "sync_counts" in result or result is None
    
    def test_connection_status_with_company_header(self, admin_token):
        """Connection status with X-Company-ID header"""
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-Company-ID": "test_company"
        }
        response = requests.get(
            f"{BASE_URL}/api/sync/connection-status",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True


class TestSuperAdminStats:
    """Test super admin stats endpoint refreshes correctly"""
    
    @pytest.fixture
    def superadmin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        return response.json()["data"]["token"]
    
    def test_stats_endpoint(self, superadmin_token):
        """Stats endpoint returns admin counts"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/super-admin/stats",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "total_admins" in data.get("data", {})
        assert "active_admins" in data.get("data", {})
    
    def test_admins_list_endpoint(self, superadmin_token):
        """Admins list endpoint returns admin data with subscription info"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/super-admin/admins",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        admins = data.get("data", {}).get("admins", [])
        assert len(admins) > 0, "Should have at least one admin"
        
        # Check admin has expected fields
        admin = admins[0]
        assert "username" in admin
        assert "features" in admin
        assert "active" in admin


class TestToggleActiveRefresh:
    """Test that toggle active triggers data refresh"""
    
    @pytest.fixture
    def superadmin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        return response.json()["data"]["token"]
    
    def test_toggle_active_endpoint(self, superadmin_token):
        """Toggle active endpoint works and returns success"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        # Get current state
        admins_res = requests.get(f"{BASE_URL}/api/super-admin/admins", headers=headers)
        admins = admins_res.json().get("data", {}).get("admins", [])
        test_admin = next((a for a in admins if a["username"] == "test_admin"), None)
        
        if test_admin:
            original_state = test_admin.get("active", True)
            
            # Toggle
            response = requests.put(
                f"{BASE_URL}/api/super-admin/admins/test_admin/toggle-active",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") == True
            
            # Verify state changed
            admins_res2 = requests.get(f"{BASE_URL}/api/super-admin/admins", headers=headers)
            admins2 = admins_res2.json().get("data", {}).get("admins", [])
            test_admin2 = next((a for a in admins2 if a["username"] == "test_admin"), None)
            assert test_admin2["active"] != original_state
            
            # Toggle back
            requests.put(
                f"{BASE_URL}/api/super-admin/admins/test_admin/toggle-active",
                headers=headers
            )


class TestCreateAdminDefaults:
    """Test that new admin creation has correct defaults"""
    
    @pytest.fixture
    def superadmin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        return response.json()["data"]["token"]
    
    def test_create_admin_with_subscription(self, superadmin_token):
        """Create admin with subscription_months parameter"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        test_email = "test_iter18@example.com"
        
        # Create admin with subscription
        response = requests.post(
            f"{BASE_URL}/api/super-admin/admins",
            json={
                "username": test_email,
                "password": "test123",
                "name": "Test Iter18",
                "features": ["sync_history", "setup", "dashboard"],
                "subscription_months": 6
            },
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Cleanup - delete the test admin
        requests.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}", headers=headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
