"""Iter-131 SuperAdmin sweep + Blog fixes regression tests.

Covers (backend surface):
 - Email OTP verification for new admin creation
 - Consented delete OTP (recipient == userAdmin's own email)
 - Forced delete OTP (recipient == ceo@flowralive.in)
 - toggle-active endpoint URL and behaviour
 - Payment enforcement (invoice-first) + reconciliation toggle
 - Billing /config and /create-order for userAdmin (Razorpay)
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SA_USER = "superadmin"
SA_PASS = "superadmin123"
USER_ADMIN = "busydemo@flowralive.in"
USER_ADMIN_PASS = "demo2026"


# ── Fixtures ─────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def sa_token():
    r = requests.post(f"{API}/auth/login", json={"username": SA_USER, "password": SA_PASS, "captcha_token": ""})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success"), body
    return body["data"]["token"]


@pytest.fixture(scope="session")
def sa_headers(sa_token):
    return {"Authorization": f"Bearer {sa_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def ua_token():
    r = requests.post(f"{API}/auth/login", json={"username": USER_ADMIN, "password": USER_ADMIN_PASS, "captcha_token": ""})
    if r.status_code != 200 or not r.json().get("success"):
        pytest.skip(f"UserAdmin login failed: {r.text[:150]}")
    return r.json()["data"]["token"]


@pytest.fixture(scope="session")
def ua_headers(ua_token):
    return {"Authorization": f"Bearer {ua_token}", "Content-Type": "application/json"}


# ── 1. Email OTP verification for admin creation ─────────────────────
class TestAdminCreateEmailOTP:
    def test_request_otp_returns_fallback_when_resend_invalid(self, sa_headers):
        email = f"test_otp_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/super-admin/admins/verify-email/request-otp",
                          json={"email": email}, headers=sa_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"], body
        data = body["data"]
        assert data["sent_to"] == email
        # RESEND_API_KEY invalid in preview — expect fallback_code
        if not data.get("email_sent"):
            assert "fallback_code" in data
            assert len(data["fallback_code"]) == 6
        # persist for other tests
        pytest.otp_email = email
        pytest.otp_code = data.get("fallback_code") or ""

    def test_verify_otp_wrong_code_rejected(self, sa_headers):
        r = requests.post(f"{API}/super-admin/admins/verify-email/verify-otp",
                          json={"email": pytest.otp_email, "otp": "000000"}, headers=sa_headers)
        body = r.json()
        assert body["success"] is False
        assert "incorrect" in (body.get("error") or "").lower() or "code" in (body.get("error") or "").lower()

    def test_verify_otp_correct_returns_token(self, sa_headers):
        if not pytest.otp_code:
            pytest.skip("no fallback code (email actually delivered)")
        r = requests.post(f"{API}/super-admin/admins/verify-email/verify-otp",
                          json={"email": pytest.otp_email, "otp": pytest.otp_code}, headers=sa_headers)
        body = r.json()
        assert body["success"], body
        assert body["data"]["verification_token"]
        pytest.verification_token = body["data"]["verification_token"]

    def test_create_admin_without_token_rejected(self, sa_headers):
        email = f"test_notoken_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/super-admin/admins", json={
            "username": email, "password": "test1234",
            "name": "TEST NoToken", "plan": "starter",
        }, headers=sa_headers)
        body = r.json()
        assert body["success"] is False
        assert "not verified" in (body.get("error") or "").lower() or "email" in (body.get("error") or "").lower()

    def test_create_admin_with_token_succeeds_and_burns(self, sa_headers):
        if not getattr(pytest, "verification_token", None):
            pytest.skip("no verification token")
        r = requests.post(f"{API}/super-admin/admins", json={
            "username": pytest.otp_email, "password": "test1234",
            "name": "TEST WithToken", "plan": "starter",
            "email_verification_token": pytest.verification_token,
        }, headers=sa_headers)
        body = r.json()
        assert body["success"], body
        pytest.created_username = pytest.otp_email

        # Token should be burnt: second use fails
        email2 = f"test_burnt_{uuid.uuid4().hex[:8]}@example.com"
        r2 = requests.post(f"{API}/super-admin/admins", json={
            "username": email2, "password": "test1234",
            "name": "TEST Burnt", "plan": "starter",
            "email_verification_token": pytest.verification_token,
        }, headers=sa_headers)
        assert r2.json()["success"] is False


# ── 2. toggle-active URL + behaviour ─────────────────────────────────
class TestToggleActive:
    def test_toggle_active_flips_flag(self, sa_headers):
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        u = pytest.created_username
        r = requests.put(f"{API}/super-admin/admins/{u}/toggle-active", headers=sa_headers)
        assert r.status_code == 200, r.text
        b1 = r.json()
        assert b1["success"], b1
        first_state = b1["data"]["active"]

        r2 = requests.put(f"{API}/super-admin/admins/{u}/toggle-active", headers=sa_headers)
        b2 = r2.json()
        assert b2["success"], b2
        assert b2["data"]["active"] == (not first_state)

    def test_old_toggle_url_returns_404(self, sa_headers):
        """The frontend used to hit /toggle (without -active). Should not exist."""
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        r = requests.put(f"{API}/super-admin/admins/{pytest.created_username}/toggle", headers=sa_headers)
        # Either 404 or method not allowed — but not a silent 200
        assert r.status_code in (404, 405)


# ── 3. Consented delete OTP goes to userAdmin's own email ───────────
class TestConsentedDeleteOTP:
    def test_recipient_is_user_admin_email(self, sa_headers):
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        u = pytest.created_username
        r = requests.post(f"{API}/super-admin/admins/{u}/request-delete-otp", headers=sa_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["success"], b
        assert b["data"]["sent_to"] == u, f"expected recipient={u} got {b['data']['sent_to']}"
        assert b["data"]["flow"] == "consented"


# ── 4. Forced delete OTP goes to ceo@flowralive.in ──────────────────
class TestForcedDeleteOTP:
    def test_recipient_is_ceo(self, sa_headers):
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        u = pytest.created_username
        r = requests.post(f"{API}/super-admin/admins/{u}/request-force-delete-otp",
                          json={"reason": "test unreachable customer"}, headers=sa_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["success"], b
        assert b["data"]["sent_to"] == "ceo@flowralive.in"
        assert b["data"]["flow"] == "forced"

    def test_admin_not_found_returns_error(self, sa_headers):
        r = requests.post(f"{API}/super-admin/admins/nonexistent_{uuid.uuid4().hex}@x.com/request-force-delete-otp",
                          json={"reason": "test"}, headers=sa_headers)
        assert r.json()["success"] is False


# ── 5. Payment enforcement + reconciliation ─────────────────────────
class TestPaymentEnforcement:
    def test_payment_without_invoice_rejected(self, sa_headers):
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        r = requests.post(f"{API}/super-admin/payments", json={
            "customer_username": pytest.created_username,
            "amount": 1000, "payment_mode": "bank_transfer",
        }, headers=sa_headers)
        b = r.json()
        assert b["success"] is False
        assert "unpaid invoice" in (b.get("error") or "").lower()

    def test_generate_invoice_then_payment_succeeds(self, sa_headers):
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        # First create a service reference for this customer (iter-122 requirement)
        r_ref = requests.post(f"{API}/super-admin/service-references", json={
            "customer_username": pytest.created_username,
            "event": "manual", "plan": "starter", "cycle": "annual", "months": 12,
        }, headers=sa_headers)
        assert r_ref.status_code == 200 and r_ref.json()["success"], r_ref.text
        ref_no = r_ref.json()["data"]["reference_no"]

        # Generate invoice
        r_inv = requests.post(f"{API}/super-admin/invoices/generate", json={
            "customer_username": pytest.created_username,
            "amount": 1000,
            "description": "TEST invoice",
            "service_reference": ref_no,
        }, headers=sa_headers)
        assert r_inv.status_code == 200, r_inv.text
        assert r_inv.json()["success"], r_inv.text

        # Record payment now succeeds
        r_pay = requests.post(f"{API}/super-admin/payments", json={
            "customer_username": pytest.created_username,
            "amount": 1000, "payment_mode": "bank_transfer",
        }, headers=sa_headers)
        assert r_pay.status_code == 200, r_pay.text
        b = r_pay.json()
        assert b["success"], b

    def test_reconcile_toggle(self, sa_headers):
        if not getattr(pytest, "created_username", None):
            pytest.skip("no admin created")
        # Fetch a payment
        r = requests.get(f"{API}/super-admin/payments?customer_username={pytest.created_username}", headers=sa_headers)
        assert r.status_code == 200, r.text
        payments = r.json().get("data", {}).get("payments", []) or r.json().get("data", [])
        if isinstance(payments, dict):
            payments = payments.get("payments", [])
        assert payments, "no payments found"
        pid = payments[0].get("payment_id")
        assert pid

        # Reconcile true
        r1 = requests.put(f"{API}/super-admin/payments/{pid}/reconcile",
                          json={"reconciled": True, "note": "HDFC line #TEST"}, headers=sa_headers)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["success"], b1
        assert b1["data"]["reconciled"] is True
        assert b1["data"]["reconciliation_note"] == "HDFC line #TEST"

        # Reconcile false
        r2 = requests.put(f"{API}/super-admin/payments/{pid}/reconcile",
                          json={"reconciled": False}, headers=sa_headers)
        b2 = r2.json()
        assert b2["success"], b2
        assert b2["data"]["reconciled"] is False


# ── 6. Billing config + create-order for real userAdmin ────────────
class TestBillingRazorpay:
    def test_billing_config(self, ua_headers):
        r = requests.get(f"{API}/billing/config", headers=ua_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["success"], b
        assert b["data"]["key_id"].startswith("rzp_"), b["data"]
        assert b["data"]["plans"], "plans dict empty"

    def test_create_order_upgrade(self, ua_headers):
        r = requests.post(f"{API}/billing/create-order", json={
            "intent": "upgrade", "plan": "professional", "cycle": "annual", "months": 12,
        }, headers=ua_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["success"], b
        assert b["data"]["order_id"].startswith("order_"), b["data"]
        assert b["data"]["key_id"].startswith("rzp_")
        assert b["data"]["amount"] > 0


# ── Cleanup ─────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _cleanup(sa_headers):
    yield
    # Best-effort delete of test admin (may fail silently — OK)
    u = getattr(pytest, "created_username", None)
    if u:
        try:
            requests.delete(f"{API}/super-admin/admins/{u}", headers=sa_headers, timeout=10)
        except Exception:
            pass
