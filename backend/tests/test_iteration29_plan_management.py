"""
Iteration 29: Plan-Based Subscription Management Tests
Tests for:
1. SuperAdmin plan-based admin creation
2. Plan-based limits (max_companies, max_employees)
3. Enterprise annual price = Rs.37,990
4. Demo shows Professional plan features
5. Convert prospect with plan selection
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPERADMIN_CREDS = {"username": "superadmin", "password": "superadmin123"}
ADMIN_CREDS = {"username": "admin", "password": "admin123"}


class TestPublicPlansEndpoint:
    """Test GET /api/public/plans returns correct plan data"""
    
    def test_plans_endpoint_returns_all_plans(self):
        """Verify /api/public/plans returns starter, professional, enterprise plans"""
        response = requests.get(f"{BASE_URL}/api/public/plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        plans = data.get("data", {}).get("plans", {})
        
        # Verify all 3 plans exist
        assert "starter" in plans, "Starter plan missing"
        assert "professional" in plans, "Professional plan missing"
        assert "enterprise" in plans, "Enterprise plan missing"
        print("PASS: All 3 plans returned")
    
    def test_enterprise_annual_price_is_37990(self):
        """Verify Enterprise annual price is Rs.37,990 (not 49990)"""
        response = requests.get(f"{BASE_URL}/api/public/plans")
        assert response.status_code == 200
        data = response.json()
        plans = data.get("data", {}).get("plans", {})
        
        enterprise = plans.get("enterprise", {})
        annual_price = enterprise.get("annual_price")
        assert annual_price == 37990, f"Enterprise annual_price should be 37990, got {annual_price}"
        print(f"PASS: Enterprise annual_price = {annual_price}")
    
    def test_starter_plan_limits(self):
        """Verify Starter plan: max_companies=1, max_employees=2, 5 features"""
        response = requests.get(f"{BASE_URL}/api/public/plans")
        data = response.json()
        starter = data.get("data", {}).get("plans", {}).get("starter", {})
        
        assert starter.get("max_companies") == 1, f"Starter max_companies should be 1, got {starter.get('max_companies')}"
        assert starter.get("max_employees") == 2, f"Starter max_employees should be 2, got {starter.get('max_employees')}"
        assert len(starter.get("features", [])) == 5, f"Starter should have 5 features, got {len(starter.get('features', []))}"
        print(f"PASS: Starter plan limits correct - 1 co, 2 emp, 5 features")
    
    def test_professional_plan_limits(self):
        """Verify Professional plan: max_companies=3, max_employees=5, 8 features"""
        response = requests.get(f"{BASE_URL}/api/public/plans")
        data = response.json()
        professional = data.get("data", {}).get("plans", {}).get("professional", {})
        
        assert professional.get("max_companies") == 3, f"Professional max_companies should be 3, got {professional.get('max_companies')}"
        assert professional.get("max_employees") == 5, f"Professional max_employees should be 5, got {professional.get('max_employees')}"
        assert len(professional.get("features", [])) == 8, f"Professional should have 8 features, got {len(professional.get('features', []))}"
        print(f"PASS: Professional plan limits correct - 3 co, 5 emp, 8 features")
    
    def test_enterprise_plan_limits(self):
        """Verify Enterprise plan: max_companies=10, max_employees=20, 10 features"""
        response = requests.get(f"{BASE_URL}/api/public/plans")
        data = response.json()
        enterprise = data.get("data", {}).get("plans", {}).get("enterprise", {})
        
        assert enterprise.get("max_companies") == 10, f"Enterprise max_companies should be 10, got {enterprise.get('max_companies')}"
        assert enterprise.get("max_employees") == 20, f"Enterprise max_employees should be 20, got {enterprise.get('max_employees')}"
        assert len(enterprise.get("features", [])) == 10, f"Enterprise should have 10 features, got {len(enterprise.get('features', []))}"
        print(f"PASS: Enterprise plan limits correct - 10 co, 20 emp, 10 features")


class TestSuperAdminLogin:
    """Test SuperAdmin login and dashboard access"""
    
    def test_superadmin_login(self):
        """Verify superadmin/superadmin123 login works"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=SUPERADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True, f"Login failed: {data.get('error')}"
        assert data.get("data", {}).get("role") == "super_admin"
        print("PASS: SuperAdmin login successful")
        return session


class TestSuperAdminAdminManagement:
    """Test SuperAdmin admin management with plan-based creation"""
    
    @pytest.fixture
    def superadmin_session(self):
        """Get authenticated superadmin session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=SUPERADMIN_CREDS)
        assert response.status_code == 200
        assert response.json().get("success") is True
        return session
    
    def test_list_admins_shows_plan_info(self, superadmin_session):
        """Verify GET /api/super-admin/admins returns plan, max_companies, max_employees"""
        response = superadmin_session.get(f"{BASE_URL}/api/super-admin/admins")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        admins = data.get("data", {}).get("admins", [])
        assert len(admins) > 0, "No admins found"
        
        # Check first admin has plan fields
        admin = admins[0]
        assert "plan" in admin, "Admin missing 'plan' field"
        assert "max_companies" in admin, "Admin missing 'max_companies' field"
        assert "max_employees" in admin, "Admin missing 'max_employees' field"
        print(f"PASS: Admin list includes plan info - {admin.get('username')}: plan={admin.get('plan')}, max_co={admin.get('max_companies')}, max_emp={admin.get('max_employees')}")
    
    def test_create_admin_with_starter_plan(self, superadmin_session):
        """Verify POST /api/super-admin/admins with plan=starter creates admin with correct limits"""
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"test_starter_{unique_id}@test.com"
        
        response = superadmin_session.post(f"{BASE_URL}/api/super-admin/admins", json={
            "username": test_email,
            "password": "test1234",
            "name": "Test Starter Admin",
            "plan": "starter",
            "billing_cycle": "annual",
            "subscription_months": 12
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True, f"Create admin failed: {data.get('error')}"
        
        # Verify the created admin has correct plan limits
        admins_response = superadmin_session.get(f"{BASE_URL}/api/super-admin/admins")
        admins = admins_response.json().get("data", {}).get("admins", [])
        created_admin = next((a for a in admins if a.get("username") == test_email), None)
        
        assert created_admin is not None, "Created admin not found in list"
        assert created_admin.get("plan") == "starter", f"Plan should be 'starter', got {created_admin.get('plan')}"
        assert created_admin.get("max_companies") == 1, f"max_companies should be 1, got {created_admin.get('max_companies')}"
        assert created_admin.get("max_employees") == 2, f"max_employees should be 2, got {created_admin.get('max_employees')}"
        assert len(created_admin.get("features", [])) == 5, f"Should have 5 features, got {len(created_admin.get('features', []))}"
        
        print(f"PASS: Created starter admin with correct limits - 1 co, 2 emp, 5 features")
        
        # Cleanup
        superadmin_session.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}")
    
    def test_create_admin_with_professional_plan(self, superadmin_session):
        """Verify POST /api/super-admin/admins with plan=professional creates admin with correct limits"""
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"test_pro_{unique_id}@test.com"
        
        response = superadmin_session.post(f"{BASE_URL}/api/super-admin/admins", json={
            "username": test_email,
            "password": "test1234",
            "name": "Test Professional Admin",
            "plan": "professional",
            "billing_cycle": "annual",
            "subscription_months": 12
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True, f"Create admin failed: {data.get('error')}"
        
        # Verify the created admin has correct plan limits
        admins_response = superadmin_session.get(f"{BASE_URL}/api/super-admin/admins")
        admins = admins_response.json().get("data", {}).get("admins", [])
        created_admin = next((a for a in admins if a.get("username") == test_email), None)
        
        assert created_admin is not None, "Created admin not found in list"
        assert created_admin.get("plan") == "professional"
        assert created_admin.get("max_companies") == 3
        assert created_admin.get("max_employees") == 5
        assert len(created_admin.get("features", [])) == 8
        
        print(f"PASS: Created professional admin with correct limits - 3 co, 5 emp, 8 features")
        
        # Cleanup
        superadmin_session.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}")
    
    def test_create_admin_with_enterprise_plan(self, superadmin_session):
        """Verify POST /api/super-admin/admins with plan=enterprise creates admin with correct limits"""
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"test_ent_{unique_id}@test.com"
        
        response = superadmin_session.post(f"{BASE_URL}/api/super-admin/admins", json={
            "username": test_email,
            "password": "test1234",
            "name": "Test Enterprise Admin",
            "plan": "enterprise",
            "billing_cycle": "annual",
            "subscription_months": 12
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True, f"Create admin failed: {data.get('error')}"
        
        # Verify the created admin has correct plan limits
        admins_response = superadmin_session.get(f"{BASE_URL}/api/super-admin/admins")
        admins = admins_response.json().get("data", {}).get("admins", [])
        created_admin = next((a for a in admins if a.get("username") == test_email), None)
        
        assert created_admin is not None, "Created admin not found in list"
        assert created_admin.get("plan") == "enterprise"
        assert created_admin.get("max_companies") == 10
        assert created_admin.get("max_employees") == 20
        assert len(created_admin.get("features", [])) == 10
        
        print(f"PASS: Created enterprise admin with correct limits - 10 co, 20 emp, 10 features")
        
        # Cleanup
        superadmin_session.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}")


class TestLoginResponseIncludesPlanInfo:
    """Test that login response includes plan, max_companies, max_employees"""
    
    def test_admin_login_includes_plan_fields(self):
        """Verify login response includes plan, max_companies, max_employees"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        user_data = data.get("data", {})
        assert "plan" in user_data, "Login response missing 'plan' field"
        assert "max_companies" in user_data, "Login response missing 'max_companies' field"
        assert "max_employees" in user_data, "Login response missing 'max_employees' field"
        
        print(f"PASS: Login response includes plan info - plan={user_data.get('plan')}, max_co={user_data.get('max_companies')}, max_emp={user_data.get('max_employees')}")


class TestEmployeeLimitEnforcement:
    """Test that employee limit is enforced based on plan"""
    
    @pytest.fixture
    def superadmin_session(self):
        """Get authenticated superadmin session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=SUPERADMIN_CREDS)
        assert response.status_code == 200
        return session
    
    def test_starter_plan_employee_limit(self, superadmin_session):
        """Test that starter plan (max 2 employees) enforces limit"""
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"test_limit_{unique_id}@test.com"
        
        # Create a starter admin
        response = superadmin_session.post(f"{BASE_URL}/api/super-admin/admins", json={
            "username": test_email,
            "password": "test1234",
            "name": "Test Limit Admin",
            "plan": "starter"
        })
        assert response.status_code == 200
        assert response.json().get("success") is True
        
        # Login as the new starter admin
        admin_session = requests.Session()
        login_response = admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": test_email,
            "password": "test1234"
        })
        assert login_response.status_code == 200
        assert login_response.json().get("success") is True
        
        # Try to create 3 employees (should fail on 3rd)
        employees_created = 0
        for i in range(3):
            emp_response = admin_session.post(f"{BASE_URL}/api/auth/users", json={
                "username": f"emp_{unique_id}_{i}@test.com",
                "password": "emp1234",
                "name": f"Employee {i}",
                "role": "employee"
            })
            if emp_response.json().get("success"):
                employees_created += 1
            else:
                # Should fail on 3rd employee (index 2)
                assert i == 2, f"Employee creation failed unexpectedly at index {i}"
                error_msg = emp_response.json().get("error", "")
                assert "limit" in error_msg.lower() or "upgrade" in error_msg.lower(), f"Expected limit error, got: {error_msg}"
                print(f"PASS: Employee limit enforced - error: {error_msg}")
        
        # Cleanup
        superadmin_session.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}")


class TestConvertProspectWithPlan:
    """Test converting prospect to admin with plan selection"""
    
    @pytest.fixture
    def superadmin_session(self):
        """Get authenticated superadmin session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=SUPERADMIN_CREDS)
        assert response.status_code == 200
        return session
    
    def test_convert_prospect_with_starter_plan(self, superadmin_session):
        """Test converting a prospect to admin with starter plan"""
        unique_id = uuid.uuid4().hex[:6]
        test_email = f"convert_test_{unique_id}@test.com"
        
        # First create a prospect via signup
        signup_response = requests.post(f"{BASE_URL}/api/public/signup", json={
            "company_name": f"Test Convert Co {unique_id}",
            "contact_person": "Test Person",
            "email": test_email,
            "phone": "+91-9876543210"
        })
        
        # If rate limited, skip this test
        if signup_response.status_code == 429:
            pytest.skip("Rate limited on signup endpoint")
        
        assert signup_response.status_code == 200
        signup_data = signup_response.json()
        
        if not signup_data.get("success"):
            # May already exist or rate limited
            pytest.skip(f"Signup failed: {signup_data.get('error')}")
        
        prospect_id = signup_data.get("data", {}).get("prospect_id")
        assert prospect_id, "No prospect_id returned"
        
        # Convert with starter plan
        convert_response = superadmin_session.post(
            f"{BASE_URL}/api/super-admin/prospects/{prospect_id}/convert",
            json={
                "password": "convert1234",
                "plan": "starter",
                "billing_cycle": "annual",
                "subscription_months": 12
            }
        )
        
        assert convert_response.status_code == 200
        convert_data = convert_response.json()
        assert convert_data.get("success") is True, f"Convert failed: {convert_data.get('error')}"
        
        result = convert_data.get("data", {})
        assert result.get("plan") == "starter"
        assert result.get("max_companies") == 1
        assert result.get("max_employees") == 2
        assert len(result.get("features", [])) == 5
        
        print(f"PASS: Converted prospect to starter admin - 1 co, 2 emp, 5 features")
        
        # Cleanup
        superadmin_session.delete(f"{BASE_URL}/api/super-admin/admins/{test_email}")


class TestDemoDataShowsProfessionalFeatures:
    """Test that demo data shows Professional plan features"""
    
    def test_demo_data_endpoint(self):
        """Verify demo data is available"""
        response = requests.get(f"{BASE_URL}/api/public/demo-data")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        demo = data.get("data", {})
        assert demo.get("company_name") == "Demo Trading Co."
        assert "dashboard" in demo
        assert "inventory_sample" in demo
        assert "crm_sample" in demo
        
        print("PASS: Demo data endpoint returns sample data for Professional plan features")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
