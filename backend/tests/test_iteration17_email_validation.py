"""
Iteration 17 Tests: Email-based username validation for new admins
Tests:
1. Login page label change (frontend only)
2. Existing accounts still work (superadmin, admin, test_admin)
3. POST /api/super-admin/admins rejects non-email username
4. POST /api/super-admin/admins accepts valid email username
5. ProfileModal close functionality (frontend only)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN = {"username": "superadmin", "password": "superadmin123"}
ADMIN = {"username": "admin", "password": "admin123"}
TEST_ADMIN = {"username": "test_admin", "password": "test123"}


class TestExistingAccountsStillWork:
    """Verify existing accounts with non-email usernames still work"""
    
    def test_superadmin_login(self):
        """Super admin login should still work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("role") == "super_admin"
        print("✓ Super admin login works")
    
    def test_admin_login(self):
        """Admin login should still work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("role") == "admin"
        print("✓ Admin login works")
    
    def test_test_admin_login(self):
        """Test admin login should still work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("role") == "admin"
        print("✓ Test admin login works")


class TestEmailValidationForNewAdmins:
    """Test email validation when creating new admins via Super Admin"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("Super admin login failed")
    
    def test_reject_non_email_username_plain_text(self, super_admin_token):
        """Creating admin with plain text username should fail"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        payload = {
            "username": "newadmin",  # Not an email
            "password": "test1234",
            "name": "Test Admin"
        }
        response = requests.post(f"{BASE_URL}/api/super-admin/admins", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False
        assert "email" in data.get("error", "").lower() or "valid" in data.get("error", "").lower()
        print(f"✓ Rejected non-email username 'newadmin': {data.get('error')}")
    
    def test_reject_non_email_username_missing_domain(self, super_admin_token):
        """Creating admin with username missing domain should fail"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        payload = {
            "username": "admin@",  # Missing domain
            "password": "test1234",
            "name": "Test Admin"
        }
        response = requests.post(f"{BASE_URL}/api/super-admin/admins", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False
        print(f"✓ Rejected invalid email 'admin@': {data.get('error')}")
    
    def test_reject_non_email_username_missing_at(self, super_admin_token):
        """Creating admin with username missing @ should fail"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        payload = {
            "username": "admin.example.com",  # Missing @
            "password": "test1234",
            "name": "Test Admin"
        }
        response = requests.post(f"{BASE_URL}/api/super-admin/admins", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False
        print(f"✓ Rejected invalid email 'admin.example.com': {data.get('error')}")
    
    def test_accept_valid_email_username(self, super_admin_token):
        """Creating admin with valid email should succeed"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"testuser_{unique_id}@example.com"
        payload = {
            "username": test_email,
            "password": "test1234",
            "name": "Test User Email",
            "features": ["dashboard", "inventory"]
        }
        response = requests.post(f"{BASE_URL}/api/super-admin/admins", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True, f"Failed to create admin: {data.get('error')}"
        assert data.get("data", {}).get("username") == test_email
        
        # Verify tenant_id is generated from email prefix
        tenant_id = data.get("data", {}).get("tenant_id", "")
        assert tenant_id.startswith("tenant_testuser_")
        print(f"✓ Created admin with email '{test_email}', tenant_id: {tenant_id}")
        
        # Cleanup: Delete the test admin
        delete_response = requests.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}", headers=headers)
        assert delete_response.status_code == 200
        print(f"✓ Cleaned up test admin '{test_email}'")
    
    def test_new_admin_can_login(self, super_admin_token):
        """Newly created admin with email username can login"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"logintest_{unique_id}@example.com"
        test_password = "testpass123"
        
        # Create admin
        payload = {
            "username": test_email,
            "password": test_password,
            "name": "Login Test Admin",
            "features": ["dashboard"]
        }
        create_response = requests.post(f"{BASE_URL}/api/super-admin/admins", json=payload, headers=headers)
        assert create_response.status_code == 200
        assert create_response.json().get("success") is True
        
        # Try to login with new admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": test_email,
            "password": test_password
        })
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data.get("success") is True
        assert login_data.get("data", {}).get("role") == "admin"
        print(f"✓ New admin '{test_email}' can login successfully")
        
        # Cleanup
        delete_response = requests.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}", headers=headers)
        assert delete_response.status_code == 200
        print(f"✓ Cleaned up test admin '{test_email}'")


class TestSuperAdminDashboardAccess:
    """Test Super Admin dashboard loads correctly"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("Super admin login failed")
    
    def test_super_admin_stats(self, super_admin_token):
        """Super admin can access stats endpoint"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        stats = data.get("data", {})
        assert "total_admins" in stats
        assert "active_admins" in stats
        print(f"✓ Super admin stats: {stats.get('total_admins')} admins, {stats.get('active_admins')} active")
    
    def test_super_admin_list_admins(self, super_admin_token):
        """Super admin can list all admins"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/admins", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        admins = data.get("data", {}).get("admins", [])
        assert len(admins) >= 2  # At least admin and test_admin
        print(f"✓ Super admin can list {len(admins)} admins")


class TestFeatureGatingStillWorks:
    """Verify feature gating still works correctly"""
    
    def test_test_admin_limited_features(self):
        """test_admin should only have 3 features"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        features = data.get("data", {}).get("features", [])
        assert len(features) == 3
        assert "dashboard" in features
        assert "inventory" in features
        assert "sales" in features
        assert "crm" not in features
        assert "analytics" not in features
        print(f"✓ test_admin has correct limited features: {features}")
    
    def test_admin_full_features(self):
        """admin should have all 9 features"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        features = data.get("data", {}).get("features", [])
        assert len(features) == 9
        print(f"✓ admin has all 9 features")


class TestDataIsolationStillWorks:
    """Verify data isolation by tenant_id still works"""
    
    @pytest.fixture
    def test_admin_token(self):
        """Get test_admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN)
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("test_admin login failed")
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        if response.status_code == 200 and response.json().get("success"):
            return response.json()["data"]["token"]
        pytest.skip("admin login failed")
    
    def test_test_admin_sees_zero_items(self, test_admin_token):
        """test_admin should see 0 inventory items (different tenant)"""
        headers = {"Authorization": f"Bearer {test_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory", headers=headers)
        assert response.status_code == 200
        data = response.json()
        items = data.get("data", {}).get("items", [])
        assert len(items) == 0
        print(f"✓ test_admin sees 0 inventory items (data isolation working)")
    
    def test_admin_sees_items(self, admin_token):
        """admin should see inventory items"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory", headers=headers)
        assert response.status_code == 200
        data = response.json()
        total = data.get("data", {}).get("total", 0)
        assert total > 0
        print(f"✓ admin sees {total} inventory items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
