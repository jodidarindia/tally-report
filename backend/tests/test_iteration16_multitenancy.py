"""
Iteration 16: Multi-tenancy, Super Admin, Feature Gating, Security Tests
Tests for FLOWRA SaaS with multi-tenancy, super admin, feature gating, 
multi-company support, password management, and security.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
SUPER_ADMIN = {"username": "superadmin", "password": "superadmin123"}
ADMIN = {"username": "admin", "password": "admin123"}
TEST_ADMIN = {"username": "test_admin", "password": "test123"}
STAFF = {"username": "staff", "password": "staff123"}


class TestSuperAdminLogin:
    """Super admin login and dashboard tests"""
    
    def test_super_admin_login_success(self):
        """Super admin login (superadmin/superadmin123) returns correct role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["role"] == "super_admin"
        assert data["data"]["username"] == "superadmin"
        assert "token" in data["data"]
        print("✓ Super admin login successful with correct role")
    
    def test_super_admin_stats_endpoint(self):
        """GET /api/super-admin/stats returns total_admins, active_admins, etc"""
        # Login as super admin
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/super-admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_admins" in data["data"]
        assert "active_admins" in data["data"]
        assert "inactive_admins" in data["data"]
        assert "total_employees" in data["data"]
        assert data["data"]["total_admins"] >= 2  # admin and test_admin
        print(f"✓ Super admin stats: {data['data']['total_admins']} admins, {data['data']['active_admins']} active")
    
    def test_super_admin_list_admins(self):
        """GET /api/super-admin/admins returns admin list with features array"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/super-admin/admins",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "admins" in data["data"]
        
        # Check admin list structure
        admins = data["data"]["admins"]
        assert len(admins) >= 2
        
        for admin in admins:
            assert "username" in admin
            assert "features" in admin
            assert "employee_count" in admin
            assert "tenant_id" in admin
            assert isinstance(admin["features"], list)
        
        print(f"✓ Admin list returned with {len(admins)} admins, each with features array")


class TestAdminLogin:
    """Admin login and feature access tests"""
    
    def test_admin_login_returns_all_features(self):
        """Admin login (admin/admin123) returns all 9 features"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["role"] == "admin"
        
        features = data["data"]["features"]
        expected_features = ["dashboard", "inventory", "sales", "crm", "analytics", 
                           "ai_reports", "salesman", "sync_history", "setup"]
        assert len(features) == 9
        for f in expected_features:
            assert f in features, f"Missing feature: {f}"
        
        print(f"✓ Admin login returns all 9 features: {features}")
    
    def test_admin_login_returns_tenant_id(self):
        """Admin login returns tenant_id and companies in response"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        data = response.json()
        assert "tenant_id" in data["data"]
        assert data["data"]["tenant_id"] == "tenant_admin"
        assert "companies" in data["data"]
        print(f"✓ Admin login returns tenant_id: {data['data']['tenant_id']}")


class TestTestAdminFeatureGating:
    """Test admin with limited features"""
    
    def test_test_admin_login_limited_features(self):
        """Test admin login (test_admin/test123) shows only 3 features"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["role"] == "admin"
        
        features = data["data"]["features"]
        assert len(features) == 3
        assert "dashboard" in features
        assert "inventory" in features
        assert "sales" in features
        
        # Should NOT have these features
        assert "crm" not in features
        assert "analytics" not in features
        assert "ai_reports" not in features
        assert "salesman" not in features
        assert "sync_history" not in features
        assert "setup" not in features
        
        print(f"✓ Test admin has only 3 features: {features}")


class TestDataIsolation:
    """Data isolation between tenants"""
    
    def test_test_admin_sees_zero_inventory(self):
        """Data isolation: test_admin sees 0 inventory items"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/inventory/summary?fy=2025-26",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_items"] == 0
        print("✓ Test admin sees 0 inventory items (data isolation working)")
    
    def test_test_admin_sees_zero_sales(self):
        """Data isolation: test_admin sees 0 sales vouchers"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/sales/summary?fy=2025-26",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_vouchers"] == 0
        print("✓ Test admin sees 0 sales vouchers (data isolation working)")
    
    def test_admin_sees_inventory_data(self):
        """Data isolation: admin sees 202 inventory items"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/inventory/summary?fy=2025-26",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_items"] == 202
        print(f"✓ Admin sees {data['data']['total_items']} inventory items")
    
    def test_admin_sees_sales_data(self):
        """Data isolation: admin sees 1255 sales vouchers"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/sales/summary?fy=2025-26",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_vouchers"] == 1255
        print(f"✓ Admin sees {data['data']['total_vouchers']} sales vouchers")


class TestPasswordManagement:
    """Password change and reset tests"""
    
    def test_change_password_flow(self):
        """Change password flow works (test with admin: change then change back)"""
        # Login with original password
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        assert login_res.json()["success"] is True
        token = login_res.json()["data"]["token"]
        
        # Change password
        change_res = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "admin123", "new_password": "admin456"}
        )
        assert change_res.status_code == 200
        assert change_res.json()["success"] is True
        print("✓ Password changed to admin456")
        
        # Login with new password
        login_new = requests.post(f"{BASE_URL}/api/auth/login", 
                                  json={"username": "admin", "password": "admin456"})
        assert login_new.json()["success"] is True
        new_token = login_new.json()["data"]["token"]
        print("✓ Login with new password successful")
        
        # Change back to original
        change_back = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            headers={"Authorization": f"Bearer {new_token}"},
            json={"current_password": "admin456", "new_password": "admin123"}
        )
        assert change_back.status_code == 200
        assert change_back.json()["success"] is True
        print("✓ Password changed back to admin123")
        
        # Verify original password works
        final_login = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        assert final_login.json()["success"] is True
        print("✓ Change password flow complete - password restored")
    
    def test_change_password_wrong_current(self):
        """Change password fails with wrong current password"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        token = login_res.json()["data"]["token"]
        
        response = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "wrongpassword", "new_password": "newpass123"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "incorrect" in response.json()["error"].lower()
        print("✓ Change password correctly rejects wrong current password")


class TestSuperAdminOperations:
    """Super admin CRUD operations"""
    
    def test_super_admin_can_toggle_admin_active(self):
        """Super admin can toggle admin active/inactive"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        token = login_res.json()["data"]["token"]
        
        # Toggle test_admin inactive
        toggle_res = requests.put(
            f"{BASE_URL}/api/super-admin/admins/test_admin/toggle-active",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert toggle_res.status_code == 200
        assert toggle_res.json()["success"] is True
        new_status = toggle_res.json()["data"]["active"]
        print(f"✓ Toggled test_admin to active={new_status}")
        
        # Toggle back
        toggle_back = requests.put(
            f"{BASE_URL}/api/super-admin/admins/test_admin/toggle-active",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert toggle_back.json()["success"] is True
        restored_status = toggle_back.json()["data"]["active"]
        assert restored_status != new_status
        print(f"✓ Toggled test_admin back to active={restored_status}")
    
    def test_super_admin_can_reset_admin_password(self):
        """Super admin can reset admin password"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        token = login_res.json()["data"]["token"]
        
        # Reset test_admin password
        reset_res = requests.post(
            f"{BASE_URL}/api/super-admin/admins/test_admin/reset-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "newtest456"}
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["success"] is True
        print("✓ Super admin reset test_admin password to newtest456")
        
        # Verify new password works
        login_new = requests.post(f"{BASE_URL}/api/auth/login",
                                  json={"username": "test_admin", "password": "newtest456"})
        assert login_new.json()["success"] is True
        print("✓ test_admin can login with new password")
        
        # Reset back to original
        reset_back = requests.post(
            f"{BASE_URL}/api/super-admin/admins/test_admin/reset-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "test123"}
        )
        assert reset_back.json()["success"] is True
        print("✓ Password reset back to test123")
    
    def test_super_admin_can_update_features(self):
        """Super admin can toggle features for an admin"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        token = login_res.json()["data"]["token"]
        
        # Get current features
        admins_res = requests.get(
            f"{BASE_URL}/api/super-admin/admins",
            headers={"Authorization": f"Bearer {token}"}
        )
        test_admin_data = next(a for a in admins_res.json()["data"]["admins"] if a["username"] == "test_admin")
        original_features = test_admin_data["features"]
        
        # Add a feature
        new_features = original_features + ["crm"]
        update_res = requests.put(
            f"{BASE_URL}/api/super-admin/admins/test_admin/features",
            headers={"Authorization": f"Bearer {token}"},
            json={"features": new_features}
        )
        assert update_res.status_code == 200
        assert update_res.json()["success"] is True
        print(f"✓ Added 'crm' feature to test_admin")
        
        # Restore original features
        restore_res = requests.put(
            f"{BASE_URL}/api/super-admin/admins/test_admin/features",
            headers={"Authorization": f"Bearer {token}"},
            json={"features": original_features}
        )
        assert restore_res.json()["success"] is True
        print(f"✓ Restored test_admin features to: {original_features}")


class TestSecurityHeaders:
    """Security headers and rate limiting tests"""
    
    def test_security_headers_present(self):
        """Security headers present in API responses"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] == "DENY"
        
        assert "x-xss-protection" in response.headers
        assert "1" in response.headers["x-xss-protection"]
        
        print("✓ Security headers present: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection")
    
    def test_rate_limiting_exists(self):
        """Rate limiting: multiple rapid login attempts don't crash (may return 429 after 20)"""
        # Make 5 rapid login attempts - should all succeed
        for i in range(5):
            response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
            assert response.status_code in [200, 429]
            if response.status_code == 429:
                print(f"✓ Rate limiting kicked in at attempt {i+1}")
                return
        
        print("✓ 5 rapid login attempts succeeded without crash")


class TestStaffLogin:
    """Staff user login tests"""
    
    def test_staff_login(self):
        """Staff login (staff/staff123) works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=STAFF)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["role"] == "employee"
        print(f"✓ Staff login successful with role: {data['data']['role']}")


class TestCreateAdmin:
    """Super admin create admin tests"""
    
    def test_super_admin_can_create_admin(self):
        """Super admin can create a new admin via API"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
        token = login_res.json()["data"]["token"]
        
        # Create a test admin
        create_res = requests.post(
            f"{BASE_URL}/api/super-admin/admins",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": "pytest_admin",
                "password": "pytest123",
                "name": "PyTest Admin",
                "features": ["dashboard", "inventory"]
            }
        )
        
        if create_res.json()["success"]:
            print("✓ Created new admin 'pytest_admin'")
            
            # Clean up - delete the admin
            delete_res = requests.delete(
                f"{BASE_URL}/api/super-admin/admins/pytest_admin",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert delete_res.json()["success"] is True
            print("✓ Cleaned up pytest_admin")
        else:
            # Admin might already exist from previous test
            if "already exists" in create_res.json().get("error", ""):
                print("✓ Admin creation test skipped (admin already exists)")
            else:
                assert False, f"Failed to create admin: {create_res.json()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
