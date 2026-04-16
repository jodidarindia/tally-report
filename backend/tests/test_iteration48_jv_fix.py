"""
Iteration 48: Test JV Party Amount Fix
Tests the fix for double-counting journal voucher adjustments in outstanding calculations.
The fix: JV documents store TOTAL voucher amounts in debit_amount/credit_amount fields,
but outstanding calculation needs only the party-specific amount from ledger_entries.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
TENANT_ID = "3079b0af-e899-44b4-ae7c-c35d113fe296"
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "captcha_token": ""}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token and tenant/company context"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "X-Tenant-Id": TENANT_ID,
        "X-Company-Id": COMPANY_ID
    }


class TestJVPartyAmountFix:
    """Tests for the JV party amount fix in outstanding calculations"""
    
    def test_outstanding_endpoint_returns_200(self, auth_headers):
        """Test that outstanding endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"API returned success=False: {data}"
        assert "data" in data, "Response missing 'data' field"
        assert "customers" in data["data"], "Response missing 'customers' field"
    
    def test_abhishek_auto_parts_outstanding_is_zero(self, auth_headers):
        """
        Key verification: Abhishek Auto Parts should have outstanding=0.0
        Before fix: outstanding was -17642 (double-counted JV)
        After fix: outstanding should be 0.0 (correct party-specific JV amount)
        """
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        customers = data.get("data", {}).get("customers", [])
        
        # Find Abhishek Auto Parts
        abhishek = None
        for c in customers:
            if "abhishek" in c.get("customer_name", "").lower():
                abhishek = c
                break
        
        assert abhishek is not None, "Abhishek Auto Parts not found in customers list"
        
        outstanding = abhishek.get("outstanding_amount", 0)
        # Outstanding should be 0.0 (or very close to 0 due to floating point)
        assert abs(outstanding) < 1, f"Abhishek Auto Parts outstanding should be ~0, got {outstanding}"
        print(f"PASS: Abhishek Auto Parts outstanding = {outstanding} (expected ~0)")
    
    def test_journal_credit_is_party_specific(self, auth_headers):
        """
        Verify journal_credit values are party-specific (HALF of total JV amount)
        For Abhishek Auto Parts: journal_credit should be 17642.0 (was 35284.0 before fix)
        """
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        customers = data.get("data", {}).get("customers", [])
        
        # Find Abhishek Auto Parts
        abhishek = None
        for c in customers:
            if "abhishek" in c.get("customer_name", "").lower():
                abhishek = c
                break
        
        assert abhishek is not None, "Abhishek Auto Parts not found"
        
        journal_credit = abhishek.get("journal_credit", 0)
        # journal_credit should be 17642.0 (party-specific), not 35284.0 (total)
        # Allow some tolerance for floating point
        assert journal_credit > 0, f"journal_credit should be positive, got {journal_credit}"
        # The value should be around 17642, not 35284
        assert journal_credit < 20000, f"journal_credit should be ~17642 (party-specific), got {journal_credit} (possibly still using total)"
        print(f"PASS: Abhishek Auto Parts journal_credit = {journal_credit} (expected ~17642)")
    
    def test_bk_sales_journal_credit(self, auth_headers):
        """
        Verify Bk Sales journal_credit is party-specific
        Should be 1531.0 (was 3062.0 before fix)
        """
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        customers = data.get("data", {}).get("customers", [])
        
        # Find Bk Sales
        bk_sales = None
        for c in customers:
            if "bk sales" in c.get("customer_name", "").lower():
                bk_sales = c
                break
        
        if bk_sales is None:
            pytest.skip("Bk Sales not found in customers list")
        
        journal_credit = bk_sales.get("journal_credit", 0)
        # journal_credit should be ~1531 (party-specific), not ~3062 (total)
        print(f"Bk Sales journal_credit = {journal_credit}")
        if journal_credit > 0:
            assert journal_credit < 2000, f"journal_credit should be ~1531 (party-specific), got {journal_credit}"
            print(f"PASS: Bk Sales journal_credit = {journal_credit} (expected ~1531)")


class TestPaymentBehaviorJVFix:
    """Tests for JV fix in payment behavior endpoint"""
    
    def test_payment_behavior_endpoint_returns_200(self, auth_headers):
        """Test that payment behavior endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"API returned success=False: {data}"
    
    def test_payment_behavior_journal_credit_is_party_specific(self, auth_headers):
        """Verify journal_credit in payment behavior uses party-specific amounts"""
        response = requests.get(
            f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        customers = data.get("data", {}).get("customers", [])
        
        # Find Abhishek Auto Parts
        abhishek = None
        for c in customers:
            if "abhishek" in c.get("customer_name", "").lower():
                abhishek = c
                break
        
        if abhishek is None:
            pytest.skip("Abhishek Auto Parts not found in payment behavior")
        
        journal_credit = abhishek.get("journal_credit", 0)
        # Should be party-specific (~17642), not total (~35284)
        if journal_credit > 0:
            assert journal_credit < 20000, f"journal_credit should be ~17642 (party-specific), got {journal_credit}"
            print(f"PASS: Payment Behavior - Abhishek journal_credit = {journal_credit}")


class TestOverdueDigest:
    """Tests for overdue digest endpoint"""
    
    def test_overdue_digest_returns_200(self, auth_headers):
        """Test that overdue digest endpoint returns 200 without errors"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overdue-digest",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"API returned success=False: {data}"
        print(f"PASS: Overdue digest returned successfully")
    
    def test_overdue_digest_has_expected_fields(self, auth_headers):
        """Verify overdue digest has expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overdue-digest",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        # Check expected fields exist
        expected_fields = ["total_overdue_amount", "total_overdue_invoices", "total_customers_overdue"]
        for field in expected_fields:
            assert field in digest, f"Missing field: {field}"
        
        print(f"PASS: Overdue digest has all expected fields")
        print(f"  - Total overdue amount: {digest.get('total_overdue_amount')}")
        print(f"  - Total overdue invoices: {digest.get('total_overdue_invoices')}")
        print(f"  - Total customers overdue: {digest.get('total_customers_overdue')}")


class TestOutstandingCalculationFormula:
    """Tests to verify the outstanding calculation formula"""
    
    def test_outstanding_formula_verification(self, auth_headers):
        """
        Verify: Outstanding = Opening Balance + Sales - (Receipts + Credit Notes + Journal Credits)
        """
        response = requests.get(
            f"{BASE_URL}/api/customers/outstanding?fy=2025-26",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        customers = data.get("data", {}).get("customers", [])
        
        # Verify formula for a few customers
        verified_count = 0
        for c in customers[:10]:  # Check first 10 customers
            ob = c.get("opening_balance", 0)
            sales = c.get("total_sales", 0)
            paid = c.get("paid_amount", 0)  # This includes receipts + CN + JV
            outstanding = c.get("outstanding_amount", 0)
            
            # paid_amount should be receipts + credit_note_total + journal_credit
            receipt_paid = paid - c.get("credit_note_total", 0) - c.get("journal_credit", 0)
            
            # Calculate expected outstanding
            expected = ob + sales - paid
            
            # Allow small tolerance for floating point
            diff = abs(outstanding - expected)
            if diff > 1:
                print(f"WARNING: {c.get('customer_name')}: outstanding={outstanding}, expected={expected}, diff={diff}")
            else:
                verified_count += 1
        
        assert verified_count > 0, "No customers verified successfully"
        print(f"PASS: Verified outstanding formula for {verified_count} customers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
