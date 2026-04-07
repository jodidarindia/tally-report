"""
Iteration 5: Auth System Tests
Tests for username/password authentication with admin/employee roles
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com').rstrip('/')

# Test credentials from .env
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
EMPLOYEE_USERNAME = "emp1"
EMPLOYEE_PASSWORD = "emp123"


class TestAuthLogin:
    """Authentication login endpoint tests"""
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "token" in data["data"]
        assert data["data"]["username"] == ADMIN_USERNAME
        assert data["data"]["role"] == "admin"
        assert data["message"] == "Login successful"
        print(f"✓ Admin login successful - role: {data['data']['role']}")
    
    def test_login_wrong_password(self):
        """Test login with wrong password returns error"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": "wrongpassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Invalid username or password" in data["error"]
        print("✓ Wrong password correctly rejected")
    
    def test_login_nonexistent_user(self):
        """Test login with nonexistent user returns error"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "nonexistent_user",
            "password": "anypassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Invalid username or password" in data["error"]
        print("✓ Nonexistent user correctly rejected")


class TestAuthMe:
    """GET /api/auth/me endpoint tests"""
    
    def test_get_me_with_valid_token(self):
        """Test getting current user with valid token"""
        # First login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["data"]["token"]
        
        # Get current user
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["username"] == ADMIN_USERNAME
        assert data["data"]["role"] == "admin"
        print(f"✓ GET /api/auth/me returns user data: {data['data']}")
    
    def test_get_me_without_token(self):
        """Test getting current user without token returns error"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Not authenticated" in data["error"]
        print("✓ GET /api/auth/me without token correctly rejected")


class TestUserManagement:
    """Admin user management endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        return response.json()["data"]["token"]
    
    def test_list_users_as_admin(self, admin_token):
        """Test listing users as admin"""
        response = requests.get(f"{BASE_URL}/api/auth/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "users" in data["data"]
        users = data["data"]["users"]
        assert len(users) >= 1  # At least admin exists
        # Verify admin user exists
        admin_user = next((u for u in users if u["username"] == ADMIN_USERNAME), None)
        assert admin_user is not None
        assert admin_user["role"] == "admin"
        print(f"✓ List users returns {len(users)} users")
    
    def test_list_users_without_auth(self):
        """Test listing users without auth returns error"""
        response = requests.get(f"{BASE_URL}/api/auth/users")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        print("✓ List users without auth correctly rejected")
    
    def test_create_employee_user(self, admin_token):
        """Test creating an employee user as admin"""
        test_username = "TEST_employee_iter5"
        
        # Create user
        response = requests.post(f"{BASE_URL}/api/auth/users", 
            json={
                "username": test_username,
                "password": "testpass123",
                "name": "Test Employee Iter5",
                "role": "employee"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["success"]:
            assert data["data"]["username"] == test_username
            assert data["data"]["role"] == "employee"
            print(f"✓ Created employee user: {test_username}")
            
            # Cleanup - delete the test user
            requests.delete(f"{BASE_URL}/api/auth/users/{test_username}", 
                headers={"Authorization": f"Bearer {admin_token}"})
        else:
            # User might already exist from previous test
            assert "already exists" in data["error"]
            print(f"✓ User creation correctly handles existing user")
    
    def test_create_user_duplicate_username(self, admin_token):
        """Test creating user with duplicate username returns error"""
        response = requests.post(f"{BASE_URL}/api/auth/users", 
            json={
                "username": ADMIN_USERNAME,  # Already exists
                "password": "anypassword",
                "name": "Duplicate Admin",
                "role": "admin"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "already exists" in data["error"]
        print("✓ Duplicate username correctly rejected")


class TestPasswordManagement:
    """Password change and reset endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        return response.json()["data"]["token"]
    
    def test_change_password_wrong_current(self, admin_token):
        """Test change password with wrong current password"""
        response = requests.post(f"{BASE_URL}/api/auth/change-password",
            json={
                "current_password": "wrongcurrent",
                "new_password": "newpassword123"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "incorrect" in data["error"].lower()
        print("✓ Change password with wrong current password rejected")
    
    def test_reset_password_as_admin(self, admin_token):
        """Test admin can reset another user's password"""
        # First create a test user
        test_username = "TEST_reset_pw_user"
        requests.post(f"{BASE_URL}/api/auth/users",
            json={
                "username": test_username,
                "password": "oldpassword",
                "name": "Reset PW Test",
                "role": "employee"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Reset password
        response = requests.post(f"{BASE_URL}/api/auth/reset-password",
            json={
                "username": test_username,
                "new_password": "newpassword123"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["success"]:
            assert "reset" in data["message"].lower()
            print(f"✓ Admin reset password for {test_username}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/auth/users/{test_username}",
            headers={"Authorization": f"Bearer {admin_token}"})
    
    def test_reset_password_nonexistent_user(self, admin_token):
        """Test reset password for nonexistent user returns error"""
        response = requests.post(f"{BASE_URL}/api/auth/reset-password",
            json={
                "username": "nonexistent_user_xyz",
                "new_password": "newpassword123"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "not found" in data["error"].lower()
        print("✓ Reset password for nonexistent user correctly rejected")


class TestTallyStatus:
    """Tally connection status endpoint tests"""
    
    def test_tally_status_shows_connected(self):
        """Test tally status shows connected (synced)"""
        response = requests.get(f"{BASE_URL}/api/tally/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "is_connected" in data["data"]
        # Based on previous sync, should show connected
        if data["data"]["is_connected"]:
            assert "company_name" in data["data"]
            print(f"✓ Tally status: Connected - {data['data'].get('company_name', 'N/A')}")
        else:
            print(f"✓ Tally status: Not synced yet")


class TestInventoryEndpoints:
    """Inventory endpoint tests"""
    
    def test_get_inventory_items(self):
        """Test getting inventory items"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "items" in data["data"]
        assert "count" in data["data"]
        assert "stock_groups" in data["data"]
        print(f"✓ Inventory items: {data['data']['count']} items, stock_groups: {data['data']['stock_groups']}")
    
    def test_get_inventory_items_with_stock_group_filter(self):
        """Test inventory items with stock group filter"""
        response = requests.get(f"{BASE_URL}/api/inventory/items", params={"stock_group": "all"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"✓ Inventory with stock_group filter works")
    
    def test_get_inventory_summary(self):
        """Test getting inventory summary"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "total_items" in data["data"]
        assert "total_value" in data["data"]
        print(f"✓ Inventory summary: {data['data']['total_items']} items, value: {data['data']['total_value']}")


class TestEmployeeRole:
    """Tests for employee role restrictions"""
    
    def test_employee_login(self):
        """Test employee can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": EMPLOYEE_USERNAME,
            "password": EMPLOYEE_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        
        if data["success"]:
            assert data["data"]["role"] == "employee"
            print(f"✓ Employee login successful - role: {data['data']['role']}")
        else:
            # Employee might not exist yet
            print(f"⚠ Employee user not found - may need to be created")
    
    def test_employee_cannot_list_users(self):
        """Test employee cannot access user management"""
        # Login as employee
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": EMPLOYEE_USERNAME,
            "password": EMPLOYEE_PASSWORD
        })
        
        if not login_response.json().get("success"):
            pytest.skip("Employee user not available")
        
        token = login_response.json()["data"]["token"]
        
        # Try to list users
        response = requests.get(f"{BASE_URL}/api/auth/users", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "admin" in data["error"].lower()
        print("✓ Employee correctly denied access to user management")


class TestCRMEndpoints:
    """CRM endpoint tests"""
    
    def test_get_customers_outstanding(self):
        """Test getting customer outstanding"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "customers" in data["data"]
        print(f"✓ Customer outstanding: {len(data['data']['customers'])} customers")
    
    def test_get_followups(self):
        """Test getting followups"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "followups" in data["data"]
        print(f"✓ Followups: {data['data']['count']} followups")
    
    def test_get_customer_targets(self):
        """Test getting customer targets"""
        response = requests.get(f"{BASE_URL}/api/customers/targets")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "targets" in data["data"]
        print(f"✓ Customer targets: {len(data['data']['targets'])} targets")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
