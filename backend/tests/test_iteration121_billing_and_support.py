"""Iteration 121: SuperAdmin follow-up ship — Razorpay billing + Support tickets +
Invoice paid/unpaid enforcement + list-admins enrichment + SuperAdmin convert-trial +
edit_admin billing_delta.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_USER = "superadmin"
SUPER_PASS = "superadmin123"
BUSY_USER = "busydemo@flowralive.in"
BUSY_PASS = "demo2026"


# ─── Fixtures ────────────────────────────────────────────────────────
def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert data.get("success"), data
    tok = data["data"]["token"]
    return tok


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_USER, SUPER_PASS)


@pytest.fixture(scope="module")
def busy_token():
    return _login(BUSY_USER, BUSY_PASS)


@pytest.fixture(scope="module")
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}"}


@pytest.fixture(scope="module")
def busy_headers(busy_token):
    return {"Authorization": f"Bearer {busy_token}"}


# ─── Trial user for upgrade path (created + deleted) ────────────────
@pytest.fixture(scope="module")
def trial_user(super_headers):
    """Create a trial admin, yield the credentials + login token; delete at end."""
    uname = f"trial_test_{uuid.uuid4().hex[:8]}@flowratest.in"
    pwd = "trial12345"
    payload = {
        "username": uname, "password": pwd, "name": "Trial Test User",
        "plan": "trial", "billing_cycle": "monthly", "subscription_months": 0,
        "features": [], "mobile": "9999999999", "company_name": "Trial Co",
        "sales_count": 1, "dispatch_count": 1, "industry": "Other",
    }
    r = requests.post(f"{API}/super-admin/admins", headers=super_headers, json=payload, timeout=20)
    assert r.status_code == 200 and r.json().get("success"), f"trial create failed: {r.text[:300]}"
    # login
    login = _login(uname, pwd)
    yield {"username": uname, "password": pwd, "token": login}
    # cleanup
    try:
        requests.delete(f"{API}/super-admin/admins/{uname}", headers=super_headers, timeout=15)
    except Exception:
        pass


# ─── /api/billing/config ─────────────────────────────────────────────
class TestBillingConfig:
    def test_billing_config_returns_key_and_plans(self, busy_headers):
        r = requests.get(f"{API}/billing/config", headers=busy_headers, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is True, j
        d = j["data"]
        assert d["key_id"].startswith("rzp_test_"), d["key_id"]
        assert d["configured"] is True
        plans = d["plans"]
        for k in ("starter", "professional", "enterprise"):
            assert k in plans, f"missing plan {k}"
        assert "trial" not in plans, "trial should not be a purchasable plan"


# ─── /api/billing/create-order ───────────────────────────────────────
class TestBillingCreateOrder:
    def test_upgrade_starter_monthly_1m(self, trial_user):
        h = {"Authorization": f"Bearer {trial_user['token']}"}
        payload = {"intent": "upgrade", "plan": "starter", "cycle": "monthly", "months": 1}
        r = requests.post(f"{API}/billing/create-order", headers=h, json=payload, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is True, j
        d = j["data"]
        assert d["order_id"].startswith("order_"), d
        assert d["amount_rupees"] == 999, d
        assert d["breakdown"]["new_total"] == 999

    def test_invalid_plan_trial_rejected(self, busy_headers):
        r = requests.post(f"{API}/billing/create-order", headers=busy_headers,
                          json={"intent": "upgrade", "plan": "trial", "cycle": "monthly", "months": 1}, timeout=15)
        j = r.json()
        assert j.get("success") is False
        assert "Invalid plan" in (j.get("error") or ""), j

    def test_change_midcycle_yields_credit(self, super_headers, busy_headers):
        # Force busydemo to enterprise so a change→starter shows a positive credit.
        # Only touch if not already enterprise (avoid disturbing data — restore at end).
        me = requests.get(f"{API}/auth/me", headers=busy_headers, timeout=15).json()["data"]
        orig_plan = me.get("plan", "starter")
        orig_cycle = me.get("billing_cycle", "annual")
        orig_months = int(me.get("subscription_months", 12) or 12)
        try:
            # bump to enterprise annual 12m so unused_days > 0
            requests.put(f"{API}/super-admin/admins/{BUSY_USER}/edit", headers=super_headers,
                         json={"plan": "enterprise", "billing_cycle": "annual",
                               "subscription_months": 12}, timeout=15)
            r = requests.post(f"{API}/billing/create-order", headers=busy_headers,
                              json={"intent": "change", "plan": "starter",
                                    "cycle": "annual", "months": 12}, timeout=20)
            j = r.json()
            assert j.get("success") is True, j
            bd = j["data"]["breakdown"]
            assert bd["credit"] > 0, f"expected positive credit, got {bd}"
            # net = max(1, new_total - credit) — Razorpay minimum 1 rupee.
            expected_net = max(1.0, round(bd["new_total"] - bd["credit"], 2))
            assert abs(bd["net"] - expected_net) < 1.5, bd
        finally:
            # restore original plan (do NOT wipe busydemo)
            requests.put(f"{API}/super-admin/admins/{BUSY_USER}/edit", headers=super_headers,
                         json={"plan": orig_plan, "billing_cycle": orig_cycle,
                               "subscription_months": orig_months}, timeout=15)


# ─── /api/billing/verify ─────────────────────────────────────────────
class TestBillingVerify:
    def test_bogus_signature_rejected(self, busy_headers):
        r = requests.post(f"{API}/billing/verify", headers=busy_headers, json={
            "razorpay_payment_id": "pay_FAKEXYZ",
            "razorpay_order_id": "order_FAKEXYZ",
            "razorpay_signature": "deadbeef",
        }, timeout=15)
        j = r.json()
        assert j.get("success") is False
        assert "Signature verification failed" in (j.get("error") or ""), j


# ─── Super convert-trial ─────────────────────────────────────────────
class TestSuperConvertTrial:
    def test_convert_trial_flips_is_trial_and_creates_payment(self, super_headers):
        uname = f"trialconv_{uuid.uuid4().hex[:8]}@flowratest.in"
        pwd = "trial12345"
        requests.post(f"{API}/super-admin/admins", headers=super_headers, json={
            "username": uname, "password": pwd, "name": "TC User",
            "plan": "trial", "billing_cycle": "monthly", "subscription_months": 0,
            "features": [], "mobile": "1", "company_name": "TC",
            "sales_count": 1, "dispatch_count": 1, "industry": "Other",
        }, timeout=15)
        try:
            ref = f"conv-{uuid.uuid4().hex[:6]}"
            r = requests.post(f"{API}/super-admin/admins/{uname}/convert-trial",
                              headers=super_headers, json={
                                  "plan": "starter", "billing_cycle": "monthly",
                                  "subscription_months": 3, "amount": 999*3,
                                  "payment_mode": "bank_transfer", "reference_no": ref,
                              }, timeout=20)
            assert r.status_code == 200
            j = r.json()
            assert j.get("success") is True, j
            # verify state
            admins = requests.get(f"{API}/super-admin/admins", headers=super_headers, timeout=15).json()["data"]["admins"]
            row = next((a for a in admins if a["username"] == uname), None)
            assert row is not None
            assert row["is_trial"] is False, row
            assert row["plan"] == "starter"
            # payment created?
            pays = requests.get(f"{API}/super-admin/payments", headers=super_headers, timeout=15)
            if pays.status_code == 200 and pays.json().get("success"):
                arr = pays.json()["data"].get("payments") or pays.json()["data"].get("data") or []
                assert any(p.get("customer_username") == uname for p in arr), "no payment row for converted trial"
        finally:
            requests.delete(f"{API}/super-admin/admins/{uname}", headers=super_headers, timeout=15)


# ─── /super-admin/admins/{username}/edit billing_delta ───────────────
class TestEditAdminBillingDelta:
    def test_plan_downgrade_returns_billing_delta(self, super_headers):
        # Create a throwaway admin at enterprise annual, then downgrade to starter monthly.
        uname = f"delta_{uuid.uuid4().hex[:8]}@flowratest.in"
        requests.post(f"{API}/super-admin/admins", headers=super_headers, json={
            "username": uname, "password": "delta12345", "name": "Delta",
            "plan": "enterprise", "billing_cycle": "annual", "subscription_months": 12,
            "features": [], "mobile": "1", "company_name": "D",
            "sales_count": 1, "dispatch_count": 1, "industry": "Other",
        }, timeout=15)
        try:
            r = requests.put(f"{API}/super-admin/admins/{uname}/edit", headers=super_headers, json={
                "plan": "starter", "billing_cycle": "annual", "subscription_months": 12,
            }, timeout=15)
            assert r.status_code == 200
            j = r.json()
            assert j.get("success") is True, j
            bd = j["data"]["billing_delta"]
            for k in ("direction", "amount", "old_total", "new_total", "refund_credit", "narrative"):
                assert k in bd, f"missing {k} in billing_delta: {bd}"
            assert bd["direction"] in ("charge", "refund", "none")
            assert bd["old_total"] == 37990
            assert bd["new_total"] == 9990
        finally:
            requests.delete(f"{API}/super-admin/admins/{uname}", headers=super_headers, timeout=15)


# ─── Invoice paid/unpaid enforcement ─────────────────────────────────
class TestInvoicePaidUnpaidEnforcement:
    @pytest.fixture(scope="class")
    def scratch_admin(self, super_headers):
        uname = f"invtest_{uuid.uuid4().hex[:8]}@flowratest.in"
        requests.post(f"{API}/super-admin/admins", headers=super_headers, json={
            "username": uname, "password": "inv12345", "name": "Inv",
            "plan": "starter", "billing_cycle": "monthly", "subscription_months": 1,
            "features": [], "mobile": "1", "company_name": "IX",
            "sales_count": 1, "dispatch_count": 1, "industry": "Other",
        }, timeout=15)
        yield uname
        requests.delete(f"{API}/super-admin/admins/{uname}", headers=super_headers, timeout=15)

    def _generate_invoice(self, super_headers, uname):
        r = requests.post(f"{API}/super-admin/invoices/generate", headers=super_headers, json={
            "customer_username": uname, "billing_cycle": "monthly",
            "subscription_months": 1, "discount_pct": 0,
            "period_description": "Test invoice",
        }, timeout=20)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert j.get("success") is True, j
        return {"invoice_id": j["data"]["invoice_id"],
                "invoice_number": j["data"]["invoice_number"],
                "amount": j["data"]["final_amount"]}

    def test_paid_without_payment_rejected(self, super_headers, scratch_admin):
        inv = self._generate_invoice(super_headers, scratch_admin)
        r = requests.put(f"{API}/super-admin/invoices/{inv['invoice_id']}/status",
                         headers=super_headers, json={"status": "paid"}, timeout=15)
        j = r.json()
        assert j.get("success") is False
        assert "payment" in (j.get("error") or "").lower(), j

    def test_paid_with_create_payment_succeeds(self, super_headers, scratch_admin):
        inv = self._generate_invoice(super_headers, scratch_admin)
        r = requests.put(f"{API}/super-admin/invoices/{inv['invoice_id']}/status",
                         headers=super_headers, json={
                             "status": "paid",
                             "create_payment": {
                                 "amount": inv["amount"], "payment_mode": "upi",
                                 "reference_no": "TEST-REF-1", "notes": "unit test",
                             },
                         }, timeout=15)
        j = r.json()
        assert j.get("success") is True, j
        # Verify invoice reads as paid & has linked_payment_id
        invs = requests.get(f"{API}/super-admin/invoices", headers=super_headers, timeout=15).json()["data"]["invoices"]
        me = next((i for i in invs if i["invoice_id"] == inv["invoice_id"]), None)
        assert me and me["status"] == "paid"
        assert me.get("linked_payment_id"), me

    def test_unpaid_without_reason_rejected(self, super_headers, scratch_admin):
        inv = self._generate_invoice(super_headers, scratch_admin)
        # first make it paid
        requests.put(f"{API}/super-admin/invoices/{inv['invoice_id']}/status", headers=super_headers, json={
            "status": "paid", "create_payment": {"amount": inv["amount"], "payment_mode": "cash", "reference_no": "X"}
        }, timeout=15)
        r = requests.put(f"{API}/super-admin/invoices/{inv['invoice_id']}/status",
                         headers=super_headers, json={"status": "unpaid"}, timeout=15)
        j = r.json()
        assert j.get("success") is False
        assert "reason" in (j.get("error") or "").lower(), j


# ─── Support tickets ─────────────────────────────────────────────────
class TestSupportTickets:
    @pytest.fixture(scope="class")
    def ticket_id(self, busy_headers):
        r = requests.post(f"{API}/support/tickets", headers=busy_headers, json={
            "subject": f"TEST_ticket_{uuid.uuid4().hex[:6]}",
            "message": "Testing from pytest",
            "priority": "high",
        }, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is True, j
        assert j["data"]["status"] == "open"
        assert j["data"]["priority"] == "high"
        return j["data"]["ticket_id"]

    def test_create_ticket_returns_open(self, ticket_id):
        assert ticket_id

    def test_super_reply_flips_pending_tenant_reply_reopens(self, super_headers, busy_headers, ticket_id):
        # super_admin reply → pending
        r = requests.post(f"{API}/support/tickets/{ticket_id}/messages",
                          headers=super_headers, json={"message": "SA reply"}, timeout=15)
        j = r.json()
        assert j.get("success") is True, j
        assert j["data"]["status"] == "pending", j["data"]
        # tenant reply → open
        r = requests.post(f"{API}/support/tickets/{ticket_id}/messages",
                          headers=busy_headers, json={"message": "tenant reply"}, timeout=15)
        j = r.json()
        assert j.get("success") is True
        assert j["data"]["status"] == "open", j["data"]

    def test_status_change_forbidden_for_non_super(self, busy_headers, ticket_id):
        r = requests.put(f"{API}/support/tickets/{ticket_id}/status",
                         headers=busy_headers, json={"status": "resolved"}, timeout=15)
        j = r.json()
        assert j.get("success") is False
        assert "super" in (j.get("error") or "").lower(), j

    def test_super_list_tickets_has_counts(self, super_headers):
        r = requests.get(f"{API}/super-admin/support/tickets", headers=super_headers, timeout=15)
        j = r.json()
        assert j.get("success") is True, j
        for k in ("total", "open", "pending", "resolved"):
            assert k in j["data"]["counts"], j["data"]["counts"]


# ─── Support webhooks ────────────────────────────────────────────────
class TestSupportWebhooks:
    def test_webhook_upsert_and_invalid_url(self, super_headers):
        # bad URL
        r = requests.post(f"{API}/super-admin/support/webhooks", headers=super_headers, json={
            "name": "bad", "url": "notaurl", "events": ["ticket.created"],
        }, timeout=15)
        j = r.json()
        assert j.get("success") is False
        assert "http" in (j.get("error") or "").lower(), j
        # valid URL
        r = requests.post(f"{API}/super-admin/support/webhooks", headers=super_headers, json={
            "name": "TEST_hook", "url": "https://example.com/hook",
            "events": ["ticket.created", "ticket.replied"],
        }, timeout=15)
        j = r.json()
        assert j.get("success") is True, j
        wid = j["data"]["webhook_id"]
        # cleanup
        requests.delete(f"{API}/super-admin/support/webhooks/{wid}", headers=super_headers, timeout=15)


# ─── list_admins enrichment ──────────────────────────────────────────
class TestListAdminsEnrichment:
    def test_admins_row_has_trial_and_billing_fields(self, super_headers):
        r = requests.get(f"{API}/super-admin/admins", headers=super_headers, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is True
        admins = j["data"]["admins"]
        assert len(admins) > 0
        row = admins[0]
        for k in ("is_trial", "trial_end", "total_billed", "total_paid", "balance_due"):
            assert k in row, f"missing {k} in list_admins row: {row.keys()}"
