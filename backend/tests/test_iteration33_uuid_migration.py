"""
Iteration 33: UUID Migration Tests
Tests for UUID-format tenant_id and company_id migration.
Verifies:
- Login returns UUID-format tenant_id
- Login response includes company_mappings array
- Auth/me endpoint returns same UUID tenant_id and company_mappings
- Sync status endpoint works with UUID company_id
- SuperAdmin dashboard lists admins with resolved company names
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com')

# UUID regex pattern
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


class TestAdminLogin:
    """Test admin login returns UUID-format IDs and company_mappings"""
    
    def test_admin_login_returns_uuid_tenant_id(self):
        """Login should return UUID-format tenant_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify tenant_id is UUID format
        tenant_id = data["data"]["tenant_id"]
        assert tenant_id is not None, "tenant_id should not be None"
        assert UUID_PATTERN.match(tenant_id), f"tenant_id '{tenant_id}' should be UUID format"
        print(f"✓ Admin login returns UUID tenant_id: {tenant_id}")
    
    def test_admin_login_returns_company_mappings(self):
        """Login response should include company_mappings array"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify company_mappings exists and has correct structure
        company_mappings = data["data"].get("company_mappings", [])
        assert isinstance(company_mappings, list), "company_mappings should be a list"
        
        if len(company_mappings) > 0:
            mapping = company_mappings[0]
            assert "company_id" in mapping, "company_mappings should have company_id"
            assert "company_name" in mapping, "company_mappings should have company_name"
            
            # Verify company_id is UUID format
            assert UUID_PATTERN.match(mapping["company_id"]), f"company_id should be UUID format"
            
            # Verify company_name is readable (not UUID)
            assert not UUID_PATTERN.match(mapping["company_name"]), "company_name should be readable, not UUID"
            print(f"✓ company_mappings: {mapping['company_id']} -> {mapping['company_name']}")
        else:
            print("⚠ No company_mappings found (admin may have no companies)")
    
    def test_admin_login_companies_are_uuids(self):
        """Login response companies array should contain UUIDs"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        
        companies = data["data"].get("companies", [])
        for company_id in companies:
            assert UUID_PATTERN.match(company_id), f"Company ID '{company_id}' should be UUID format"
        print(f"✓ All {len(companies)} company IDs are UUID format")


class TestAuthMe:
    """Test /auth/me endpoint returns UUID tenant_id and company_mappings"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        return response.json()["data"]["token"]
    
    def test_auth_me_returns_uuid_tenant_id(self, admin_token):
        """Auth/me should return same UUID tenant_id"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        tenant_id = data["data"]["tenant_id"]
        assert UUID_PATTERN.match(tenant_id), f"tenant_id '{tenant_id}' should be UUID format"
        print(f"✓ /auth/me returns UUID tenant_id: {tenant_id}")
    
    def test_auth_me_returns_company_mappings(self, admin_token):
        """Auth/me should return company_mappings"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        
        company_mappings = data["data"].get("company_mappings", [])
        assert isinstance(company_mappings, list), "company_mappings should be a list"
        
        if len(company_mappings) > 0:
            mapping = company_mappings[0]
            assert "company_id" in mapping
            assert "company_name" in mapping
            assert UUID_PATTERN.match(mapping["company_id"])
            print(f"✓ /auth/me returns company_mappings with UUID company_id")


class TestSyncStatus:
    """Test sync status endpoint works with UUID company_id"""
    
    @pytest.fixture
    def admin_session(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        data = response.json()["data"]
        return {
            "token": data["token"],
            "company_id": data["companies"][0] if data["companies"] else None
        }
    
    def test_sync_status_with_uuid_company_id(self, admin_session):
        """Sync status endpoint should work with UUID company_id"""
        if not admin_session["company_id"]:
            pytest.skip("No company_id available")
        
        company_id = admin_session["company_id"]
        assert UUID_PATTERN.match(company_id), "company_id should be UUID format"
        
        response = requests.get(
            f"{BASE_URL}/api/sync/status",
            params={"company_id": company_id},
            headers={
                "Authorization": f"Bearer {admin_session['token']}",
                "X-Company-ID": company_id
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        print(f"✓ Sync status works with UUID company_id: {company_id}")
        
        # Verify response contains company_id
        if data["data"]:
            assert data["data"].get("company_id") == company_id
            print(f"✓ Sync status response contains correct company_id")


class TestSuperAdminDashboard:
    """Test SuperAdmin dashboard lists admins with resolved company names"""
    
    @pytest.fixture
    def superadmin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        return response.json()["data"]["token"]
    
    def test_superadmin_admins_list_has_resolved_company_names(self, superadmin_token):
        """SuperAdmin /admins endpoint should return resolved company names, not UUIDs"""
        response = requests.get(f"{BASE_URL}/api/super-admin/admins", headers={
            "Authorization": f"Bearer {superadmin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        admins = data["data"]["admins"]
        assert len(admins) > 0, "Should have at least one admin"
        
        # Find admin with companies
        admin_with_companies = None
        for admin in admins:
            if admin.get("companies") and len(admin["companies"]) > 0:
                admin_with_companies = admin
                break
        
        if admin_with_companies:
            # Verify companies are display names, not UUIDs
            for company_name in admin_with_companies["companies"]:
                is_uuid = UUID_PATTERN.match(company_name) if company_name else False
                assert not is_uuid, f"Company '{company_name}' should be display name, not UUID"
            print(f"✓ SuperAdmin sees resolved company names: {admin_with_companies['companies']}")
        else:
            print("⚠ No admin with companies found to verify name resolution")
    
    def test_superadmin_admins_have_uuid_tenant_ids(self, superadmin_token):
        """SuperAdmin /admins endpoint should return UUID tenant_ids"""
        response = requests.get(f"{BASE_URL}/api/super-admin/admins", headers={
            "Authorization": f"Bearer {superadmin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        
        admins = data["data"]["admins"]
        for admin in admins:
            tenant_id = admin.get("tenant_id")
            if tenant_id:
                assert UUID_PATTERN.match(tenant_id), f"tenant_id '{tenant_id}' should be UUID format"
        print(f"✓ All {len(admins)} admins have UUID tenant_ids")


class TestSyncHistory:
    """Test sync history endpoint"""
    
    @pytest.fixture
    def admin_session(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        data = response.json()["data"]
        return {
            "token": data["token"],
            "company_id": data["companies"][0] if data["companies"] else None
        }
    
    def test_sync_history_endpoint(self, admin_session):
        """Sync history endpoint should work"""
        response = requests.get(
            f"{BASE_URL}/api/sync/history",
            headers={
                "Authorization": f"Bearer {admin_session['token']}",
                "X-Company-ID": admin_session["company_id"] or ""
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        print(f"✓ Sync history endpoint works, {len(data['data'].get('cycles', []))} cycles found")


class TestSuperAdminRenewals:
    """Test SuperAdmin renewals endpoint resolves company names"""
    
    @pytest.fixture
    def superadmin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "superadmin123"
        })
        return response.json()["data"]["token"]
    
    def test_renewals_endpoint_works(self, superadmin_token):
        """SuperAdmin renewals endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/super-admin/renewals", headers={
            "Authorization": f"Bearer {superadmin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify structure
        assert "stats" in data["data"]
        assert "near_expiry" in data["data"]
        assert "expired" in data["data"]
        print(f"✓ Renewals endpoint works: {data['data']['stats']}")


class TestCompaniesStatus:
    """Test companies status endpoint for company selector"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        return response.json()["data"]["token"]
    
    def test_companies_status_returns_names(self, admin_token):
        """Companies status should return company names for selector"""
        response = requests.get(f"{BASE_URL}/api/sync/companies-status", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        companies = data["data"]
        if len(companies) > 0:
            company = companies[0]
            assert "company_id" in company
            assert "company_name" in company
            assert UUID_PATTERN.match(company["company_id"]), "company_id should be UUID"
            print(f"✓ Companies status returns: {company['company_id']} -> {company['company_name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
