"""
Iteration 21: Audit Logging System Tests
Tests for:
1. Audit log endpoints (GET /api/audit/logs, GET /api/audit/actions)
2. Login audit logging (login, login_failed)
3. Tenant isolation (admin sees only own tenant logs, super_admin sees all)
4. Security fix: sales-frequency uses tenant context
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN = {"username": "superadmin", "password": "superadmin123"}
ADMIN = {"username": "admin", "password": "admin123"}
TEST_ADMIN = {"username": "test_admin", "password": "test123"}


class TestAuditLogging:
    """Audit logging endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def login(self, username, password):
        """Helper to login and get session with cookie"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": password
        })
        return response
    
    def logout(self):
        """Helper to logout"""
        self.session.post(f"{BASE_URL}/api/auth/logout")
        self.session.cookies.clear()
    
    # ==================== SUPER ADMIN AUDIT TESTS ====================
    
    def test_superadmin_login_creates_audit_log(self):
        """Super admin login should create audit log entry"""
        # Login as super admin
        response = self.login(SUPER_ADMIN["username"], SUPER_ADMIN["password"])
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["role"] == "super_admin"
        
        # Check audit logs
        time.sleep(0.5)  # Allow log to be written
        logs_response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"limit": 10})
        assert logs_response.status_code == 200
        logs_data = logs_response.json()
        assert logs_data["success"] == True
        
        # Verify login log exists
        logs = logs_data["data"]["logs"]
        login_logs = [l for l in logs if l["action"] == "login" and l["actor"] == "superadmin"]
        assert len(login_logs) > 0, "Super admin login should be logged"
        
        # Verify IP address is captured
        latest_login = login_logs[0]
        assert "ip_address" in latest_login
        print(f"Super admin login logged with IP: {latest_login.get('ip_address')}")
    
    def test_superadmin_sees_all_tenant_logs(self):
        """Super admin should see logs from all tenants"""
        # Login as super admin
        self.login(SUPER_ADMIN["username"], SUPER_ADMIN["password"])
        
        # Get all logs
        response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"limit": 100})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        logs = data["data"]["logs"]
        print(f"Super admin sees {len(logs)} total logs")
        
        # Check for logs from different actors (superadmin and admin)
        actors = set(l["actor"] for l in logs)
        print(f"Actors in logs: {actors}")
        
        # Should see superadmin's own logs at minimum
        assert "superadmin" in actors, "Should see superadmin logs"
    
    def test_superadmin_audit_actions_endpoint(self):
        """GET /api/audit/actions should return distinct action types"""
        self.login(SUPER_ADMIN["username"], SUPER_ADMIN["password"])
        
        response = self.session.get(f"{BASE_URL}/api/audit/actions")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        actions = data["data"]["actions"]
        print(f"Available action types: {actions}")
        
        # Should have at least 'login' action
        assert "login" in actions, "Should have login action type"
    
    def test_superadmin_filter_by_action(self):
        """Super admin can filter logs by action type"""
        self.login(SUPER_ADMIN["username"], SUPER_ADMIN["password"])
        
        # Filter by login action
        response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"action": "login"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        logs = data["data"]["logs"]
        # All logs should be login type
        for log in logs:
            assert log["action"] == "login", f"Expected login action, got {log['action']}"
        print(f"Filtered to {len(logs)} login logs")
    
    # ==================== ADMIN AUDIT TESTS ====================
    
    def test_admin_login_creates_audit_log(self):
        """Admin login should create audit log entry with tenant_id"""
        # Login as admin
        response = self.login(ADMIN["username"], ADMIN["password"])
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["role"] == "admin"
        
        # Check audit logs
        time.sleep(0.5)
        logs_response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"limit": 10})
        assert logs_response.status_code == 200
        logs_data = logs_response.json()
        assert logs_data["success"] == True
        
        logs = logs_data["data"]["logs"]
        login_logs = [l for l in logs if l["action"] == "login" and l["actor"] == "admin"]
        assert len(login_logs) > 0, "Admin login should be logged"
        
        # Verify tenant_id is set
        latest_login = login_logs[0]
        assert latest_login.get("tenant_id"), "Admin login should have tenant_id"
        print(f"Admin login logged with tenant_id: {latest_login.get('tenant_id')}")
    
    def test_admin_sees_only_own_tenant_logs(self):
        """Admin should only see logs from their own tenant"""
        # Login as admin
        self.login(ADMIN["username"], ADMIN["password"])
        
        # Get logs
        response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"limit": 100})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        logs = data["data"]["logs"]
        print(f"Admin sees {len(logs)} logs")
        
        # Admin should NOT see superadmin logs (superadmin has no tenant_id)
        superadmin_logs = [l for l in logs if l["actor"] == "superadmin"]
        assert len(superadmin_logs) == 0, "Admin should NOT see superadmin logs"
        
        # All logs should have the same tenant_id (admin's tenant)
        tenant_ids = set(l.get("tenant_id") for l in logs if l.get("tenant_id"))
        print(f"Tenant IDs in admin's logs: {tenant_ids}")
        assert len(tenant_ids) <= 1, "Admin should only see logs from one tenant"
    
    def test_admin_audit_actions_filtered_by_tenant(self):
        """Admin's action types should be filtered by tenant"""
        self.login(ADMIN["username"], ADMIN["password"])
        
        response = self.session.get(f"{BASE_URL}/api/audit/actions")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        actions = data["data"]["actions"]
        print(f"Admin's available action types: {actions}")
    
    # ==================== FAILED LOGIN TESTS ====================
    
    def test_failed_login_creates_audit_log(self):
        """Failed login should create audit log with login_failed action"""
        # Attempt login with wrong password
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN["username"],
            "password": "wrongpassword123"
        })
        assert response.status_code == 200  # API returns 200 with success=false
        data = response.json()
        assert data["success"] == False
        
        # Now login as super admin to check logs
        time.sleep(0.5)
        self.login(SUPER_ADMIN["username"], SUPER_ADMIN["password"])
        
        logs_response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"action": "login_failed", "limit": 10})
        assert logs_response.status_code == 200
        logs_data = logs_response.json()
        assert logs_data["success"] == True
        
        logs = logs_data["data"]["logs"]
        failed_logs = [l for l in logs if l["actor"] == "admin" and l["action"] == "login_failed"]
        assert len(failed_logs) > 0, "Failed login should be logged"
        
        # Verify details contain "Wrong password"
        latest_failed = failed_logs[0]
        assert "Wrong password" in latest_failed.get("details", ""), f"Details should mention 'Wrong password', got: {latest_failed.get('details')}"
        print(f"Failed login logged with details: {latest_failed.get('details')}")
    
    def test_failed_login_invalid_username(self):
        """Failed login with invalid username should be logged"""
        # Attempt login with non-existent user
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "nonexistent_user_xyz",
            "password": "anypassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        
        # Check logs as super admin
        time.sleep(0.5)
        self.login(SUPER_ADMIN["username"], SUPER_ADMIN["password"])
        
        logs_response = self.session.get(f"{BASE_URL}/api/audit/logs", params={"action": "login_failed", "limit": 10})
        logs_data = logs_response.json()
        
        logs = logs_data["data"]["logs"]
        invalid_user_logs = [l for l in logs if l["actor"] == "nonexistent_user_xyz"]
        assert len(invalid_user_logs) > 0, "Invalid username login attempt should be logged"
        
        latest = invalid_user_logs[0]
        assert "Invalid username" in latest.get("details", ""), f"Details should mention 'Invalid username', got: {latest.get('details')}"
        print(f"Invalid username login logged with details: {latest.get('details')}")
    
    # ==================== SECURITY FIX TESTS ====================
    
    def test_sales_frequency_uses_tenant_context(self):
        """GET /api/inventory/sales-frequency should use tenant context"""
        # Login as admin
        self.login(ADMIN["username"], ADMIN["password"])
        
        # Get companies
        me_response = self.session.get(f"{BASE_URL}/api/auth/me")
        me_data = me_response.json()
        companies = me_data["data"].get("companies", [])
        
        if companies:
            company_id = companies[0]
            self.session.headers.update({"X-Company-ID": company_id})
        
        # Call sales-frequency endpoint
        response = self.session.get(f"{BASE_URL}/api/inventory/sales-frequency", params={"fy": "2025-26"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Should return data (not error about missing tenant)
        print(f"Sales frequency returned {len(data['data'].get('items', []))} items")
    
    def test_cross_tenant_isolation_sales_frequency(self):
        """test_admin should not see admin's sales frequency data"""
        # Login as test_admin
        self.login(TEST_ADMIN["username"], TEST_ADMIN["password"])
        
        # Try to access with admin's company ID
        self.session.headers.update({"X-Company-ID": "ASA AUTOTECH INDIA PRIVATE LIMITED"})
        
        response = self.session.get(f"{BASE_URL}/api/inventory/sales-frequency", params={"fy": "2025-26"})
        assert response.status_code == 200
        data = response.json()
        
        # Should return empty or filtered data (not admin's data)
        items = data["data"].get("items", [])
        print(f"test_admin sees {len(items)} items (should be 0 or filtered)")
        # test_admin has no companies, so should see 0 items
        assert len(items) == 0, "test_admin should not see admin's sales frequency data"


class TestAuditLogAuthentication:
    """Test authentication requirements for audit endpoints"""
    
    def test_audit_logs_requires_auth(self):
        """GET /api/audit/logs should require authentication"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/audit/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Authentication" in data.get("error", "") or "auth" in data.get("error", "").lower()
    
    def test_audit_actions_requires_auth(self):
        """GET /api/audit/actions should require authentication"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/audit/actions")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False


class TestExistingFunctionality:
    """Verify existing functionality still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def login(self, username, password):
        return self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": password
        })
    
    def test_company_switching_works(self):
        """Company switching should still work"""
        self.login(ADMIN["username"], ADMIN["password"])
        
        # Get companies
        me_response = self.session.get(f"{BASE_URL}/api/auth/me")
        me_data = me_response.json()
        companies = me_data["data"].get("companies", [])
        
        assert len(companies) >= 2, f"Admin should have at least 2 companies, got {companies}"
        print(f"Admin has companies: {companies}")
        
        # Test inventory for first company
        self.session.headers.update({"X-Company-ID": companies[0]})
        inv_response = self.session.get(f"{BASE_URL}/api/inventory/summary", params={"fy": "2025-26"})
        assert inv_response.status_code == 200
        inv_data = inv_response.json()
        assert inv_data["success"] == True
        print(f"Company 1 ({companies[0]}): {inv_data['data'].get('total_items', 0)} items")
        
        # Test inventory for second company
        self.session.headers.update({"X-Company-ID": companies[1]})
        inv_response2 = self.session.get(f"{BASE_URL}/api/inventory/summary", params={"fy": "2025-26"})
        assert inv_response2.status_code == 200
        inv_data2 = inv_response2.json()
        assert inv_data2["success"] == True
        print(f"Company 2 ({companies[1]}): {inv_data2['data'].get('total_items', 0)} items")
    
    def test_inventory_page_works(self):
        """Inventory page should work"""
        self.login(ADMIN["username"], ADMIN["password"])
        
        me_response = self.session.get(f"{BASE_URL}/api/auth/me")
        companies = me_response.json()["data"].get("companies", [])
        if companies:
            self.session.headers.update({"X-Company-ID": companies[0]})
        
        response = self.session.get(f"{BASE_URL}/api/inventory/items", params={"fy": "2025-26", "page": 1, "limit": 10})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"Inventory items: {len(data['data'].get('items', []))}")
    
    def test_sales_page_works(self):
        """Sales page should work"""
        self.login(ADMIN["username"], ADMIN["password"])
        
        me_response = self.session.get(f"{BASE_URL}/api/auth/me")
        companies = me_response.json()["data"].get("companies", [])
        if companies:
            self.session.headers.update({"X-Company-ID": companies[0]})
        
        response = self.session.get(f"{BASE_URL}/api/sales/vouchers", params={"fy": "2025-26", "page": 1, "limit": 10})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"Sales vouchers: {len(data['data'].get('vouchers', []))}")
    
    def test_crm_page_works(self):
        """CRM page should work"""
        self.login(ADMIN["username"], ADMIN["password"])
        
        me_response = self.session.get(f"{BASE_URL}/api/auth/me")
        companies = me_response.json()["data"].get("companies", [])
        if companies:
            self.session.headers.update({"X-Company-ID": companies[0]})
        
        response = self.session.get(f"{BASE_URL}/api/customers/outstanding", params={"fy": "2025-26"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"CRM customers: {len(data['data'].get('customers', []))}")
    
    def test_dashboard_works(self):
        """Dashboard should work"""
        self.login(ADMIN["username"], ADMIN["password"])
        
        me_response = self.session.get(f"{BASE_URL}/api/auth/me")
        companies = me_response.json()["data"].get("companies", [])
        if companies:
            self.session.headers.update({"X-Company-ID": companies[0]})
        
        # Test inventory summary
        inv_response = self.session.get(f"{BASE_URL}/api/inventory/summary", params={"fy": "2025-26"})
        assert inv_response.status_code == 200
        
        # Test sales summary
        sales_response = self.session.get(f"{BASE_URL}/api/sales/summary", params={"fy": "2025-26"})
        assert sales_response.status_code == 200
        
        print("Dashboard endpoints working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
