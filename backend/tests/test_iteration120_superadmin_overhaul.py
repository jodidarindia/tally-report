"""Iteration 120 — SuperAdmin overhaul (rich customer form, trial plan,
discount invoice, redesigned PDF, trial expiry lockout).

Tests the review_request items in order:
1. Create admin with plan=trial + rich fields → trial window stamped
2. Plan caps (starter 2, pro 5, ent 10 employees; all 1 company)
3. email_sent flag propagates (RESEND may be invalid → false)
4. Login for future-trial → success + is_trial + plan:trial
5. Login for past-trial → 14-day trial message + trial_expired flag
6. /auth/me for trial admin — is_trial + trial_end
7. /customers/search?q=busy → busydemo with plan_name/base_price/balance_due
8. /industries returns 31 items (Automotive...Other)
9. Invoice generate with discount_pct=15 for busydemo → 37990/5698.5/32291.5
   And discount_pct>20 gets capped
10. Invoice PDF /Title=inv_number, filename matches, contains brand text
"""
import io
import os
import re
import time
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")

SUPERADMIN_USER = "superadmin"
SUPERADMIN_PASS = "superadmin123"
BUSY_USERNAME = "busydemo@flowralive.in"


# ── Fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def sa_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={
        "username": SUPERADMIN_USER, "password": SUPERADMIN_PASS,
        "captcha_token": ""
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True, data
    tok = data["data"]["token"]
    return tok


@pytest.fixture(scope="module")
def sa_client(api, sa_token):
    api.headers.update({"Authorization": f"Bearer {sa_token}"})
    return api


@pytest.fixture(scope="module")
def trial_user(sa_client):
    """Create a fresh trial user, yield, then delete."""
    username = f"trialtest-{int(time.time())}@flowratest.io"
    password = "trial1234"
    payload = {
        "username": username,
        "password": password,
        "name": "Trial Test User",
        "plan": "trial",
        "billing_cycle": "annual",
        "mobile": "9999911111",
        "address": "12 Trial St",
        "city": "Indore",
        "company_name": "Trial Test Pvt Ltd",
        "gst": "23ABCDE1234F1Z5",
        "industry": "IT Services & Software",
        "sales_count": 3,
        "dispatch_count": 2,
    }
    r = sa_client.post(f"{BASE_URL}/api/super-admin/admins", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True, data
    yield {"username": username, "password": password, "resp": data}
    # cleanup
    sa_client.delete(f"{BASE_URL}/api/super-admin/admins/{username}")


# ── Tests ────────────────────────────────────────────────────────────────
class TestCreateAdminTrial:
    def test_trial_creates_with_rich_fields(self, trial_user):
        d = trial_user["resp"]["data"]
        assert d["is_trial"] is True
        assert d["trial_end"], "trial_end must be set"
        assert "email_sent" in d, "email_sent must always be present"
        assert isinstance(d["email_sent"], bool)

    def test_trial_end_approx_14_days(self, trial_user):
        te = trial_user["resp"]["data"]["trial_end"]
        end = datetime.fromisoformat(te.replace("Z", "+00:00"))
        delta_days = (end - datetime.now(timezone.utc)).days
        assert 12 <= delta_days <= 14, f"trial_end ≈ 14d, got {delta_days}"

    def test_trial_user_persisted_with_all_fields(self, sa_client, trial_user):
        # list admins and find our record
        r = sa_client.get(f"{BASE_URL}/api/super-admin/admins")
        assert r.status_code == 200
        admins = r.json()["data"]["admins"]
        me = next((a for a in admins if a["username"] == trial_user["username"]), None)
        assert me is not None, "trial user not found in listing"
        assert me["plan"] == "trial"
        assert me["max_companies"] == 1
        assert me["max_employees"] == 10  # trial cap per prospects.py
        assert me["subscription_months"] == 0


class TestPlanCaps:
    """Plan employee caps (iteration 120 change)."""

    @pytest.mark.parametrize("plan_id,exp_emp", [
        ("starter", 2),
        ("professional", 5),
        ("enterprise", 10),
    ])
    def test_plan_caps(self, sa_client, plan_id, exp_emp):
        uname = f"capstest-{plan_id}-{int(time.time())}@flowratest.io"
        r = sa_client.post(f"{BASE_URL}/api/super-admin/admins", json={
            "username": uname, "password": "captest1", "name": f"cap {plan_id}",
            "plan": plan_id, "billing_cycle": "annual",
        })
        assert r.status_code == 200, r.text
        assert r.json().get("success") is True, r.json()
        # verify caps via list
        rl = sa_client.get(f"{BASE_URL}/api/super-admin/admins")
        me = next(a for a in rl.json()["data"]["admins"] if a["username"] == uname)
        assert me["max_companies"] == 1, f"{plan_id} max_companies"
        assert me["max_employees"] == exp_emp, f"{plan_id} max_employees"
        # cleanup
        sa_client.delete(f"{BASE_URL}/api/super-admin/admins/{uname}")


class TestLoginTrial:
    def test_login_future_trial(self, api, trial_user):
        # unauth session
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/login", json={
            "username": trial_user["username"],
            "password": trial_user["password"],
            "captcha_token": ""
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True, data
        u = data["data"]
        assert u.get("is_trial") is True
        assert u.get("plan") == "trial"
        assert u.get("trial_end")

    def test_auth_me_trial(self, api, trial_user):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={
            "username": trial_user["username"],
            "password": trial_user["password"],
            "captcha_token": ""
        })
        tok = r.json()["data"]["token"]
        r2 = s.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r2.status_code == 200, r2.text
        me = r2.json()["data"]
        assert me.get("is_trial") is True
        assert me.get("trial_end")

    def test_login_expired_trial(self, sa_client):
        """Backdate trial_end to yesterday via DB update, then login should
        fail with the 14-day trial message + trial_expired:true."""
        uname = f"expiredtrial-{int(time.time())}@flowratest.io"
        pw = "expired1"
        r = sa_client.post(f"{BASE_URL}/api/super-admin/admins", json={
            "username": uname, "password": pw, "name": "Expired Trial",
            "plan": "trial", "billing_cycle": "annual",
        })
        assert r.status_code == 200
        # backdate via direct Mongo — use pymongo since we have backend access
        from pymongo import MongoClient
        from dotenv import dotenv_values
        env_map = dotenv_values("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL") or env_map.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or env_map.get("DB_NAME")
        assert mongo_url and db_name, "MONGO_URL/DB_NAME must be set"
        cli = MongoClient(mongo_url)
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        start_past = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        upd = cli[db_name].users.update_one(
            {"username": uname},
            {"$set": {"trial_end": past, "trial_start": start_past}}
        )
        assert upd.modified_count == 1

        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r2 = s.post(f"{BASE_URL}/api/auth/login", json={
            "username": uname, "password": pw, "captcha_token": ""
        })
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("success") is False, d
        assert "14-day FLOWRA free trial" in (d.get("error") or ""), d
        assert (d.get("data") or {}).get("trial_expired") is True, d
        # cleanup
        sa_client.delete(f"{BASE_URL}/api/super-admin/admins/{uname}")


class TestCustomerSearchIndustries:
    def test_customer_search_busy(self, sa_client):
        r = sa_client.get(f"{BASE_URL}/api/super-admin/customers/search?q=busy")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        rows = d["data"]["customers"]
        row = next((x for x in rows if x["username"] == BUSY_USERNAME), None)
        assert row is not None, "busydemo not found in search"
        assert "plan_name" in row
        assert "base_price" in row
        assert "balance_due" in row
        assert isinstance(row["base_price"], (int, float))

    def test_industries_31(self, sa_client):
        r = sa_client.get(f"{BASE_URL}/api/super-admin/industries")
        assert r.status_code == 200, r.text
        inds = r.json()["data"]["industries"]
        assert len(inds) == 31, f"expected 31, got {len(inds)}"
        assert inds[0] == "Automotive & Auto Parts"
        assert inds[-1] == "Other"


class TestInvoiceDiscount:
    def test_generate_invoice_with_discount(self, sa_client):
        r = sa_client.post(f"{BASE_URL}/api/super-admin/invoices/generate", json={
            "customer_username": BUSY_USERNAME,
            "description": "TEST invoice iter120",
            "discount_pct": 15,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("success") is True, d
        data = d["data"]
        assert data["base_amount"] == 37990
        assert data["discount_pct"] == 15
        assert abs(data["final_amount"] - 32291.5) < 0.01, data
        # busydemo is enterprise/annual → 37990 - 5698.5 = 32291.5
        return data["invoice_id"], data["invoice_number"]

    def test_discount_capped_at_20(self, sa_client):
        r = sa_client.post(f"{BASE_URL}/api/super-admin/invoices/generate", json={
            "customer_username": BUSY_USERNAME,
            "description": "TEST cap iter120",
            "discount_pct": 25,
        })
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["discount_pct"] == 20.0, d
        # final = 37990 * 0.80 = 30392
        assert abs(d["final_amount"] - 30392.0) < 0.01

    def test_invoice_pdf_metadata_and_content(self, sa_client):
        # create a fresh invoice for the PDF check
        r = sa_client.post(f"{BASE_URL}/api/super-admin/invoices/generate", json={
            "customer_username": BUSY_USERNAME,
            "description": "TEST pdf iter120",
            "discount_pct": 15,
        })
        assert r.status_code == 200
        d = r.json()["data"]
        invoice_id = d["invoice_id"]
        invoice_number = d["invoice_number"]

        r2 = sa_client.get(f"{BASE_URL}/api/super-admin/invoices/{invoice_id}/pdf")
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("content-type", "").startswith("application/pdf")
        cd = r2.headers.get("content-disposition", "")
        assert f"{invoice_number}.pdf" in cd, cd

        pdf_bytes = r2.content
        # Extract /Title metadata using pypdf
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        meta = reader.metadata or {}
        title = meta.get("/Title") or meta.get("Title") or ""
        assert invoice_number in str(title), f"Title '{title}' should contain {invoice_number}"

        # Extract text and check brand strings
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        for needle in ["FLOWRA", "JODIDAR INDIA", "TAX INVOICE", "Discount", "TOTAL PAYABLE"]:
            assert needle in text, f"PDF missing '{needle}'; extracted first 400: {text[:400]}"
        # brand sub-line
        assert "brand owned by JODIDAR INDIA" in text, "sub-line missing"

    def test_invoice_pdf_placeholder_env(self, sa_client):
        """When INVOICE_SELLER_GSTIN / _ADDRESS are unset, PDF should
        gracefully show placeholder text (not blow up)."""
        # Just ensure PDF renders — a placeholder string appears in text.
        r = sa_client.post(f"{BASE_URL}/api/super-admin/invoices/generate", json={
            "customer_username": BUSY_USERNAME, "description": "TEST placeholder"
        })
        inv_id = r.json()["data"]["invoice_id"]
        r2 = sa_client.get(f"{BASE_URL}/api/super-admin/invoices/{inv_id}/pdf")
        assert r2.status_code == 200
        # We don't strictly require the placeholder string since env may
        # be set locally; just verify PDF renders without error.
