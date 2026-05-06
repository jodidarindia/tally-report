"""
Iteration 55: CRM bug fixes verification
- Outstanding endpoint with JV per-line DR/CR math
- Days Overdue / oldest_invoice_days populating (FY bypass for invoices)
- Sundry Debtors filter (no creditors)
- UndefinedName fix on line 363 (fy_start_str)
- payment-behavior, targets endpoints sanity
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123", "captcha_token": ""},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    token = r.json()["data"]["token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Id": COMPANY_ID,
        "Content-Type": "application/json",
    }


# --- Outstanding endpoint (no FY) ---
class TestOutstandingNoFY:
    def test_returns_success_no_crash(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True
        assert "data" in body
        assert "customers" in body["data"]
        assert isinstance(body["data"]["customers"], list)

    def test_only_sundry_debtors(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=auth_headers, timeout=60)
        assert r.status_code == 200
        customers = r.json()["data"]["customers"]
        # Verify no creditor groups (sundry creditors)
        for c in customers:
            grp = (c.get("parent_group") or c.get("group") or "").lower()
            assert "creditor" not in grp, f"Creditor leaked: {c.get('customer_name')} group={grp}"

    def test_oldest_invoice_days_populates(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=auth_headers, timeout=60)
        assert r.status_code == 200
        customers = r.json()["data"]["customers"]
        if not customers:
            pytest.skip("No customers in outstanding")
        # At least one customer should have oldest_invoice_days populated (>0)
        any_populated = any(
            (c.get("oldest_invoice_days") or 0) > 0 for c in customers
        )
        assert any_populated, "No customer has oldest_invoice_days populated"


# --- Outstanding endpoint with FY ---
class TestOutstandingWithFY:
    def test_returns_success(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True

    def test_has_required_fields(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers, timeout=60,
        )
        customers = r.json()["data"]["customers"]
        if not customers:
            pytest.skip("No customers")
        first = customers[0]
        # Verify the expected fields exist (may be 0 but must be present)
        for field in ["opening_balance", "total_sales", "paid_amount", "journal_credit", "outstanding_amount"]:
            assert field in first, f"Missing field: {field} in {list(first.keys())}"

    def test_jv_per_line_math_krishna(self, auth_headers):
        """Krishna Sales Corporation, RAIPUR should show small jv credit (~-4243), not full voucher total"""
        r = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers, timeout=60,
        )
        customers = r.json()["data"]["customers"]
        krishna = next(
            (c for c in customers if "krishna" in (c.get("customer_name") or "").lower()
             and "raipur" in (c.get("customer_name") or "").lower()),
            None,
        )
        if not krishna:
            pytest.skip("Krishna Sales Corporation, RAIPUR not in dataset")
        jv_credit = krishna.get("journal_credit", 0) or krishna.get("customer_jv_adjustment", 0)
        # Should be a small magnitude (per-line), not millions
        assert abs(jv_credit) < 100000, (
            f"Krishna JV credit too large ({jv_credit}); "
            f"per-line DR/CR parsing may not be working"
        )


# --- payment-behavior ---
class TestPaymentBehavior:
    def test_returns_success(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True
        assert "customers" in body.get("data", {})
        assert isinstance(body["data"]["customers"], list)


# --- targets ---
class TestTargets:
    def test_returns_success(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/customers/targets?fy=2025-26",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True
        # Targets may be array directly or under data.targets
        data = body.get("data", {})
        targets = data.get("targets") if isinstance(data, dict) else data
        assert targets is not None
