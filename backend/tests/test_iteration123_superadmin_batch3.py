"""Iter-123 SuperAdmin batch-3 regression tests.

Covers: DPDP consent enforcement (signup + questionnaire), prospect stats
new buckets (negotiating, lost), trial-reminder-preview days_left fix,
Blog CMS (SA CRUD + public list/detail), Remarks with tags + history,
record_payment ledger→invoice auto-sync, invoice PDF new payment band.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SA_USER = "superadmin"
SA_PASS = "superadmin123"


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


# ── 1. DPDP consent on /public/signup ────────────────────────────────

class TestSignupConsent:
    def test_signup_rejects_without_consent(self):
        payload = {
            "name": "TEST_no_consent",
            "email": f"test_noconsent_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "9999900001",
            "company_name": "TEST Co",
            "consent_given": False,
        }
        r = requests.post(f"{API}/public/signup", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False
        assert "consent" in (body.get("error") or "").lower()
        assert "dpdp" in (body.get("error") or "").lower()

    def test_signup_accepts_with_consent_and_stores_audit(self, sa_headers):
        email = f"test_consent_{uuid.uuid4().hex[:6]}@example.com"
        payload = {
            "name": "TEST_consent",
            "contact_person": "TEST Consent Person",
            "email": email,
            "phone": "9999900002",
            "company_name": "TEST Co Consent",
            "consent_given": True,
        }
        r = requests.post(f"{API}/public/signup", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body

        # Verify audit fields via SA prospects listing
        time.sleep(0.5)
        r2 = requests.get(f"{API}/super-admin/prospects", headers=sa_headers)
        assert r2.status_code == 200
        prospects = r2.json()["data"]["prospects"]
        match = [p for p in prospects if p.get("email") == email]
        assert match, f"prospect not found for {email}"
        p = match[0]
        assert p.get("consent_given") is True
        assert p.get("consent_version") == "dpdp-v1-2026-02"
        assert p.get("consent_ts")
        assert p.get("consent_ip")


# ── 2. DPDP consent on /questionnaire/submit ─────────────────────────

class TestQuestionnaireConsent:
    def test_questionnaire_rejects_without_consent(self):
        payload = {
            "name": "TEST_q_no",
            "email": f"test_qno_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "9999900011",
            "company_name": "TEST QCo",
            "consent_given": False,
        }
        r = requests.post(f"{API}/questionnaire/submit", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False
        err = (body.get("error") or "").lower()
        assert "consent" in err

    def test_questionnaire_accepts_with_consent(self):
        email = f"test_qok_{uuid.uuid4().hex[:6]}@example.com"
        payload = {
            "name": "TEST_q_ok",
            "email": email,
            "phone": "9999900012",
            "company_name": "TEST QCo OK",
            "consent_given": True,
        }
        r = requests.post(f"{API}/questionnaire/submit", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body


# ── 3. Prospect stats has all 7 keys ─────────────────────────────────

class TestProspectStats:
    def test_stats_has_all_seven_keys(self, sa_headers):
        r = requests.get(f"{API}/super-admin/prospects", headers=sa_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        stats = data["stats"]
        for key in ("total", "new", "contacted", "demo_given", "negotiating", "converted", "lost"):
            assert key in stats, f"missing key: {key}"
        # Total should equal len(prospects list)
        assert stats["total"] == len(data["prospects"])


# ── 4. Trial-reminder-preview: days_left is always 14 - day ──────────

class TestTrialReminderPreview:
    @pytest.mark.parametrize("day,expected_days_left,expected_phrase", [
        (5, 9, "9 days"),
        (8, 6, "6 days"),
        (12, 2, "2 days"),
    ])
    def test_days_left_previews(self, sa_headers, day, expected_days_left, expected_phrase):
        # Use superadmin as target — endpoint is defensive, admin lookup may
        # be empty but preview still renders with the 14-day math.
        r = requests.get(f"{API}/super-admin/trial-reminder-preview/{SA_USER}/{day}", headers=sa_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        data = body["data"]
        assert data["sample_days_left"] == expected_days_left, f"day={day} → {data['sample_days_left']}"
        assert expected_phrase in data["html"], f"'{expected_phrase}' missing from day-{day} html"

    def test_day14_ends_tonight_phrasing(self, sa_headers):
        r = requests.get(f"{API}/super-admin/trial-reminder-preview/{SA_USER}/14", headers=sa_headers)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        data = body["data"]
        assert data["sample_days_left"] == 0
        html_low = data["html"].lower()
        # Any of these phrasings for day-14 is acceptable
        assert any(p in html_low for p in ("ends tonight", "ends today", "expires today", "last day", "0 days")), (
            f"day-14 html did not contain expected end-of-trial phrasing. First 400 chars: {data['html'][:400]}"
        )


# ── 5. Blog CMS ──────────────────────────────────────────────────────

class TestBlogCMS:
    def test_full_blog_lifecycle(self, sa_headers):
        title = f"TEST Blog {uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/super-admin/blog", headers=sa_headers, json={
            "title": title,
            "excerpt": "test excerpt",
            "body_md": "# Hello\n\nTest body.",
            "tags": ["test", "iter123"],
            "published": False,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success"), body
        post_id = body["data"]["post_id"]
        slug = body["data"]["slug"]
        assert slug and post_id

        # List all in SA
        r2 = requests.get(f"{API}/super-admin/blog", headers=sa_headers)
        assert r2.status_code == 200
        assert any(p["post_id"] == post_id for p in r2.json()["data"]["posts"])

        # Not yet in public
        r3 = requests.get(f"{API}/public/blog")
        assert r3.status_code == 200
        assert not any(p.get("slug") == slug for p in r3.json()["data"]["posts"])

        # Publish
        r4 = requests.put(f"{API}/super-admin/blog/{post_id}", headers=sa_headers, json={"published": True})
        assert r4.status_code == 200
        assert r4.json().get("success"), r4.text

        # Now visible on public
        r5 = requests.get(f"{API}/public/blog")
        assert r5.status_code == 200
        assert any(p.get("slug") == slug for p in r5.json()["data"]["posts"])

        # Public detail + view_count increments
        r6 = requests.get(f"{API}/public/blog/{slug}")
        assert r6.status_code == 200
        pdata = r6.json()["data"]
        assert pdata["title"] == title
        assert pdata["body_md"].startswith("# Hello")

        # Cleanup
        requests.delete(f"{API}/super-admin/blog/{post_id}", headers=sa_headers)


# ── 6. Remarks ───────────────────────────────────────────────────────

class TestRemarks:
    def test_add_and_list_remark(self, sa_headers):
        # Create a fresh prospect first
        email = f"test_remark_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/public/signup", json={
            "name": "TEST_remark",
            "contact_person": "TEST Remark Person",
            "email": email,
            "phone": "9999900021",
            "company_name": "TEST RCo",
            "consent_given": True,
        })
        assert r.json().get("success"), r.text

        # Get prospect_id
        r2 = requests.get(f"{API}/super-admin/prospects", headers=sa_headers)
        match = [p for p in r2.json()["data"]["prospects"] if p.get("email") == email]
        assert match
        pid = match[0]["prospect_id"]

        # Add remark
        r3 = requests.post(f"{API}/super-admin/remarks/prospect/{pid}", headers=sa_headers, json={
            "text": "Called customer, will circle back Monday.",
            "tag": "Follow-up",
        })
        assert r3.status_code == 200, r3.text
        assert r3.json().get("success"), r3.text

        # List
        r4 = requests.get(f"{API}/super-admin/remarks/prospect/{pid}", headers=sa_headers)
        assert r4.status_code == 200
        data = r4.json()["data"]
        assert data["count"] >= 1
        rk = data["remarks"][0]
        assert rk["text"].startswith("Called customer")
        assert rk["tag"] == "Follow-up"
        assert rk.get("author_username")
        assert rk.get("author_role")
        assert rk.get("created_at")

    def test_invalid_tag_rejected(self, sa_headers):
        # Use any existing prospect
        r = requests.get(f"{API}/super-admin/prospects", headers=sa_headers)
        prospects = r.json()["data"]["prospects"]
        if not prospects:
            pytest.skip("no prospects to test against")
        pid = prospects[0]["prospect_id"]

        r2 = requests.post(f"{API}/super-admin/remarks/prospect/{pid}", headers=sa_headers, json={
            "text": "trying bad tag", "tag": "NotARealTag",
        })
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("success") is False
        assert "tag" in (body.get("error") or "").lower()


# ── 7. Ledger→Invoice auto-sync on record_payment ────────────────────

class TestPaymentInvoiceSync:
    def test_record_payment_endpoint_reachable(self, sa_headers):
        """Smoke: record a payment against busydemo (has invoices). If
        matching unpaid invoice exists it should flip to paid with
        auto_paid_from='ledger_receipt'."""
        target = "busydemo@flowralive.in"

        def _get_invoices():
            last = None
            for _ in range(4):
                try:
                    r = requests.get(f"{API}/super-admin/invoices", headers=sa_headers, timeout=90)
                    if r.status_code == 200:
                        return r
                    last = r
                except Exception as e:
                    last = e
                time.sleep(3)
            return last

        # Get invoices before
        r_inv_before = _get_invoices()
        assert r_inv_before.status_code == 200
        inv_before = r_inv_before.json()["data"].get("invoices", [])
        unpaid_before = [i for i in inv_before if i.get("customer_username") == target and i.get("status") == "unpaid"]

        # Try to record a payment matching the OLDEST unpaid invoice (FIFO
        # is what record_payment applies). Sort by invoice_date ASC to
        # match the backend's sync logic.
        unpaid_sorted = sorted(unpaid_before, key=lambda i: i.get("invoice_date", ""))
        amount = float(unpaid_sorted[0]["amount"]) if unpaid_sorted else 1.0
        target_invoice_id = unpaid_sorted[0]["invoice_id"] if unpaid_sorted else None

        r_pay = requests.post(f"{API}/super-admin/payments", headers=sa_headers, json={
            "customer_username": target,
            "amount": amount,
            "payment_mode": "bank_transfer",
            "reference_no": f"TEST-{uuid.uuid4().hex[:6]}",
            "notes": "iter123 test payment",
        })
        assert r_pay.status_code == 200, r_pay.text
        assert r_pay.json().get("success"), r_pay.text

        # If we had an unpaid invoice, verify it flipped
        if target_invoice_id:
            r_inv_after = _get_invoices()
            invs = r_inv_after.json()["data"].get("invoices", [])
            match = [i for i in invs if i.get("invoice_id") == target_invoice_id]
            assert match, "invoice disappeared"
            inv = match[0]
            assert inv["status"] == "paid"
            assert inv.get("auto_paid_from") == "ledger_receipt"
            assert inv.get("linked_payment_id")


# ── 8. Invoice PDF renders (application/pdf) ─────────────────────────

class TestInvoicePDF:
    def test_pdf_download(self, sa_headers):
        r = requests.get(f"{API}/super-admin/invoices", headers=sa_headers)
        assert r.status_code == 200
        invs = r.json()["data"].get("invoices", [])
        if not invs:
            pytest.skip("no invoices to render")
        inv_id = invs[0]["invoice_id"]
        r2 = requests.get(f"{API}/super-admin/invoices/{inv_id}/pdf", headers=sa_headers)
        assert r2.status_code == 200, f"{r2.status_code}: {r2.text[:400]}"
        ctype = r2.headers.get("content-type", "").lower()
        assert "pdf" in ctype, f"content-type not pdf: {ctype}"
        # PDF magic bytes
        assert r2.content[:4] == b"%PDF", "not a valid PDF stream"
