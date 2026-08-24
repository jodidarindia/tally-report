"""
Iteration 122 — SuperAdmin batch 2 tests

Covers:
 - Admin reset-password auto-generates + emails (no plaintext in response)
 - Delete admin OTP request/confirm (wrong OTP path)
 - Renewals: active_trials bucket + stats.active_trials_count (Kritika fix)
 - Staff GET returns departments list
 - Staff POST with department/mobile creates flowra_staff (+ delete teardown)
 - Prospect status=demo_given stamps demo_given_at + demo_completed=true
 - Employee login inherits admin features (not empty)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ── Session fixtures ──────────────────────────────────────────────────
def _login(session, username, password):
    r = session.post(f"{API}/auth/login", json={"username": username, "password": password, "captcha_token": ""}, timeout=30)
    return r


@pytest.fixture(scope="module")
def sa_session():
    s = requests.Session()
    r = _login(s, "superadmin", "superadmin123")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login(s, "busydemo@flowralive.in", "demo2026")
    assert r.status_code == 200, r.text
    body = r.json()
    if not body.get("success"):
        pytest.skip(f"busydemo login unavailable: {body}")
    return s


# ── Helpers to create ephemeral admin for reset/OTP/renewal tests ─────
def _create_test_admin(sa_session, is_trial=False):
    uname = f"test_iter122_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "username": uname,
        "password": "TempPass123!",
        "name": "Iter122 Test Admin",
        "plan": "trial" if is_trial else "starter",
        "billing_cycle": "monthly",
        "subscription_months": 0 if is_trial else 12,
    }
    r = sa_session.post(f"{API}/super-admin/admins", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("success"), r.json()
    return uname


def _delete_test_admin(sa_session, username):
    try:
        sa_session.delete(f"{API}/super-admin/admins/{username}", timeout=30)
    except Exception:
        pass


# ── 1. SuperAdmin login ──────────────────────────────────────────────
class TestSuperAdminLogin:
    def test_login(self, sa_session):
        r = sa_session.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("success") is True
        assert d["data"]["role"] == "super_admin"


# ── 2. Reset-password endpoint ───────────────────────────────────────
class TestResetPassword:
    def test_reset_password_auto_generates(self, sa_session):
        u = _create_test_admin(sa_session)
        try:
            r = sa_session.post(f"{API}/super-admin/admins/{u}/reset-password", json={}, timeout=30)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("success") is True, body
            assert "email_sent" in (body.get("data") or {}), body
            # Must NOT leak plaintext password in response
            flat = str(body).lower()
            assert "password" not in (body.get("data") or {}), body
            # Verify old password no longer works
            s2 = requests.Session()
            r2 = _login(s2, u, "TempPass123!")
            assert r2.json().get("success") is False
        finally:
            _delete_test_admin(sa_session, u)


# ── 3. Delete admin OTP flow ─────────────────────────────────────────
class TestDeleteAdminOTP:
    def test_request_otp_and_wrong_confirm(self, sa_session):
        u = _create_test_admin(sa_session)
        try:
            r = sa_session.post(f"{API}/super-admin/admins/{u}/request-delete-otp", json={}, timeout=30)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("success") is True, body
            data = body.get("data") or {}
            assert "sent_to" in data and data["sent_to"], data
            assert "expires_at" in data and data["expires_at"], data
            assert "email_sent" in data, data

            # Wrong OTP
            r2 = sa_session.post(f"{API}/super-admin/admins/{u}/confirm-delete-otp", json={"otp": "000000"}, timeout=30)
            assert r2.status_code == 200
            b2 = r2.json()
            assert b2.get("success") is False, b2
            assert "incorrect" in (b2.get("error") or "").lower(), b2
        finally:
            _delete_test_admin(sa_session, u)


# ── 4. Renewals: active_trials bucket ────────────────────────────────
class TestRenewals:
    def test_active_trial_not_in_expired(self, sa_session):
        u = _create_test_admin(sa_session, is_trial=True)
        try:
            r = sa_session.get(f"{API}/super-admin/renewals", timeout=30)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("success") is True
            data = body["data"]
            assert "active_trials" in data
            assert isinstance(data["active_trials"], list)
            assert "active_trials_count" in data["stats"]

            trial_usernames = [x["username"] for x in data["active_trials"]]
            expired_usernames = [x["username"] for x in data["expired"]]
            assert u in trial_usernames, f"{u} should be in active_trials, got {trial_usernames}"
            assert u not in expired_usernames, f"{u} should NOT be in expired bucket"
        finally:
            _delete_test_admin(sa_session, u)


# ── 5. Staff GET returns departments ─────────────────────────────────
class TestStaffDepartments:
    def test_departments_present(self, sa_session):
        r = sa_session.get(f"{API}/super-admin/staff", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        depts = body["data"]["departments"]
        expected = {"Support", "Sales", "Finance", "Onboarding", "Product", "Engineering", "Operations"}
        assert expected.issubset(set(depts)), depts


# ── 6. Staff POST with department + mobile ───────────────────────────
class TestStaffCRUD:
    def test_create_list_delete_staff(self, sa_session):
        uname = f"test_staff_{uuid.uuid4().hex[:6]}@flowra.in"
        payload = {
            "username": uname,
            "password": "secret123",
            "name": "Test Staff Iter122",
            "features": ["overview", "subscriptions"],
            "department": "Support",
            "mobile": "9876543210",
        }
        r = sa_session.post(f"{API}/super-admin/staff", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        assert "email_sent" in (body.get("data") or {}), body

        # GET should list this staff with department + mobile
        r2 = sa_session.get(f"{API}/super-admin/staff", timeout=30)
        rows = r2.json()["data"]["staff"]
        match = [x for x in rows if x.get("username") == uname]
        assert match, f"created staff {uname} not in list"
        assert match[0].get("department") == "Support"
        assert match[0].get("mobile") == "9876543210"

        # DELETE
        r3 = sa_session.delete(f"{API}/super-admin/staff/{uname}", timeout=30)
        assert r3.status_code == 200
        assert r3.json().get("success") is True


# ── 7. Prospect status demo_given ───────────────────────────────────
class TestProspectDemoGiven:
    def test_demo_given_stamps_date(self, sa_session):
        # Create a prospect via public signup
        email = f"test_prospect_{uuid.uuid4().hex[:6]}@example.com"
        prospect_payload = {
            "company_name": f"TEST_Prospect_Iter122_{uuid.uuid4().hex[:4]}",
            "contact_person": "Test Contact",
            "email": email,
            "phone": "9999999999",
            "selected_plan": "starter",
            "captcha_token": "",
        }
        r = requests.post(f"{API}/public/signup", json=prospect_payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success"), body
        pid = (body.get("data") or {}).get("prospect_id")
        assert pid, f"could not resolve prospect id: {body}"

        try:
            r2 = sa_session.put(
                f"{API}/super-admin/prospects/{pid}/status",
                json={"status": "demo_given", "demo_given_at": "2026-02-20"},
                timeout=30,
            )
            assert r2.status_code == 200, r2.text
            assert r2.json().get("success"), r2.json()

            # Verify persistence via list
            lst = sa_session.get(f"{API}/super-admin/prospects", timeout=30).json()
            plist = lst["data"].get("prospects") if isinstance(lst.get("data"), dict) else lst["data"]
            row = next((p for p in plist if p.get("prospect_id") == pid), None)
            assert row is not None, "prospect missing after update"
            assert row.get("status") == "demo_given"
            assert row.get("demo_given_at") == "2026-02-20"
            assert row.get("demo_completed") is True
        finally:
            try:
                sa_session.delete(f"{API}/super-admin/prospects/{pid}", timeout=30)
            except Exception:
                pass


# ── 8. Employee login inherits admin features ────────────────────────
class TestEmployeeFeatureInheritance:
    def test_employee_inherits_features(self, admin_session):
        # Admin's features
        me = admin_session.get(f"{API}/auth/me", timeout=30).json()
        admin_features = me["data"].get("features") or []
        assert admin_features, f"admin has no features: {me}"

        emp_email = f"TEST_emp_{uuid.uuid4().hex[:6]}@example.com"
        emp_pass = "EmpPass123!"
        r = admin_session.post(
            f"{API}/auth/users",
            json={"username": emp_email, "password": emp_pass, "name": "Test Emp", "role": "employee"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("success"), r.json()

        try:
            # Employee login
            s2 = requests.Session()
            r2 = _login(s2, emp_email, emp_pass)
            assert r2.status_code == 200, r2.text
            body = r2.json()
            assert body.get("success"), body
            emp_features = body["data"].get("features") or []
            assert emp_features, f"employee features are empty (bug): {body}"
            # Should mirror admin's list
            assert set(emp_features) == set(admin_features), (emp_features, admin_features)
        finally:
            try:
                admin_session.delete(f"{API}/auth/users/{emp_email}", timeout=30)
            except Exception:
                pass
