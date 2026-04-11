"""
Iteration 35: SuperAdmin Seller Panel Backend Tests
Tests for business dashboard, payments, invoices, customer health, and customer ledger APIs.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
SUPERADMIN_USERNAME = "superadmin"
SUPERADMIN_PASSWORD = "superadmin123"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Known test data from main agent context
EXISTING_INVOICE_ID = "c8f580ed-b2d5-45e6-9604-e943a8009177"
ADMIN_TENANT_ID = "3079b0af-e899-44b4-ae7c-c35d113fe296"


class TestSuperAdminAuth:
    """Test SuperAdmin authentication"""
    
    def test_superadmin_login_success(self):
        """SuperAdmin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": SUPERADMIN_USERNAME,
            "password": SUPERADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["role"] == "super_admin"
        assert data["data"]["username"] == SUPERADMIN_USERNAME
        print(f"✓ SuperAdmin login successful: {data['data']['username']}")
    
    def test_admin_login_success(self):
        """Admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["role"] == "admin"
        print(f"✓ Admin login successful: {data['data']['username']}")


@pytest.fixture(scope="class")
def superadmin_token():
    """Get SuperAdmin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": SUPERADMIN_USERNAME,
        "password": SUPERADMIN_PASSWORD
    })
    if response.status_code == 200 and response.json().get("success"):
        return response.json()["data"]["token"]
    pytest.skip("SuperAdmin authentication failed")


@pytest.fixture(scope="class")
def admin_token():
    """Get Admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200 and response.json().get("success"):
        return response.json()["data"]["token"]
    pytest.skip("Admin authentication failed")


class TestBusinessDashboard:
    """Test GET /api/super-admin/business-dashboard"""
    
    def test_business_dashboard_returns_metrics(self, superadmin_token):
        """Business dashboard returns MRR, ARR, outstanding, plan_distribution"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/business-dashboard", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        dashboard = data["data"]
        # Check required fields
        assert "mrr" in dashboard
        assert "arr" in dashboard
        assert "outstanding" in dashboard
        assert "plan_distribution" in dashboard
        assert "total_customers" in dashboard
        assert "active_customers" in dashboard
        assert "total_received" in dashboard
        assert "collection_rate" in dashboard
        
        # Validate types
        assert isinstance(dashboard["mrr"], (int, float))
        assert isinstance(dashboard["arr"], (int, float))
        assert isinstance(dashboard["plan_distribution"], dict)
        
        print(f"✓ Business Dashboard: MRR={dashboard['mrr']}, ARR={dashboard['arr']}, Outstanding={dashboard['outstanding']}")
        print(f"  Plan Distribution: {dashboard['plan_distribution']}")
    
    def test_business_dashboard_requires_superadmin(self, admin_token):
        """Business dashboard requires super_admin role"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/business-dashboard", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "super admin" in data["error"].lower()
        print("✓ Business dashboard correctly rejects non-superadmin")


class TestPaymentsAPI:
    """Test payment ledger APIs"""
    
    def test_get_payments_returns_ledger(self, superadmin_token):
        """GET /api/super-admin/payments returns payment ledger with totals"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/payments", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        payments_data = data["data"]
        assert "payments" in payments_data
        assert "total_amount" in payments_data
        assert "by_mode" in payments_data
        assert isinstance(payments_data["payments"], list)
        
        print(f"✓ Payments ledger: {len(payments_data['payments'])} payments, Total: Rs.{payments_data['total_amount']}")
        print(f"  By mode: {payments_data['by_mode']}")
    
    def test_record_payment_success(self, superadmin_token):
        """POST /api/super-admin/payments records a payment correctly"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        payment_data = {
            "customer_username": ADMIN_USERNAME,
            "amount": 1000,
            "payment_mode": "upi",
            "reference_no": "TEST-UPI-12345",
            "notes": "Test payment from iteration 35",
            "period_description": "Test Period Q1 2026"
        }
        
        response = requests.post(f"{BASE_URL}/api/super-admin/payments", json=payment_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recorded" in data["message"].lower()
        
        print(f"✓ Payment recorded: {data['message']}")
    
    def test_record_payment_invalid_customer(self, superadmin_token):
        """POST /api/super-admin/payments rejects invalid customer"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        payment_data = {
            "customer_username": "nonexistent_user_xyz",
            "amount": 1000,
            "payment_mode": "bank_transfer"
        }
        
        response = requests.post(f"{BASE_URL}/api/super-admin/payments", json=payment_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()
        
        print("✓ Payment correctly rejected for invalid customer")
    
    def test_record_payment_invalid_amount(self, superadmin_token):
        """POST /api/super-admin/payments rejects zero/negative amount"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        payment_data = {
            "customer_username": ADMIN_USERNAME,
            "amount": 0,
            "payment_mode": "cash"
        }
        
        response = requests.post(f"{BASE_URL}/api/super-admin/payments", json=payment_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        
        print("✓ Payment correctly rejected for invalid amount")


class TestInvoicesAPI:
    """Test invoice generation and management APIs"""
    
    def test_generate_invoice_success(self, superadmin_token):
        """POST /api/super-admin/invoices/generate creates invoice with FLW-YYYYMM-NNNN format"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        invoice_data = {
            "customer_username": ADMIN_USERNAME,
            "amount": 9990,
            "description": "Enterprise Plan - Annual Subscription (Test)",
            "period_from": "2026-04-01",
            "period_to": "2027-03-31"
        }
        
        response = requests.post(f"{BASE_URL}/api/super-admin/invoices/generate", json=invoice_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Check invoice number format FLW-YYYYMM-NNNN
        invoice_number = data["data"]["invoice_number"]
        assert invoice_number.startswith("FLW-")
        # Format: FLW-YYYYMM-NNNN = 15 chars (FLW-202604-0002)
        assert len(invoice_number) >= 15
        assert "-" in invoice_number[4:]  # Has separator after FLW-
        
        print(f"✓ Invoice generated: {invoice_number}, ID: {data['data']['invoice_id']}")
        return data["data"]["invoice_id"]
    
    def test_list_invoices_returns_counts(self, superadmin_token):
        """GET /api/super-admin/invoices returns invoice list with paid/unpaid counts"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/invoices", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        invoices_data = data["data"]
        assert "invoices" in invoices_data
        assert "total_invoiced" in invoices_data
        assert "paid_count" in invoices_data
        assert "unpaid_count" in invoices_data
        
        print(f"✓ Invoices list: {len(invoices_data['invoices'])} invoices")
        print(f"  Total invoiced: Rs.{invoices_data['total_invoiced']}, Paid: {invoices_data['paid_count']}, Unpaid: {invoices_data['unpaid_count']}")
    
    def test_mark_invoice_paid(self, superadmin_token):
        """PUT /api/super-admin/invoices/{id}/status marks invoice as paid"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        # First get an unpaid invoice
        response = requests.get(f"{BASE_URL}/api/super-admin/invoices", headers=headers)
        invoices = response.json()["data"]["invoices"]
        
        unpaid_invoice = next((inv for inv in invoices if inv.get("status") == "unpaid"), None)
        if not unpaid_invoice:
            pytest.skip("No unpaid invoice available for testing")
        
        invoice_id = unpaid_invoice["invoice_id"]
        
        # Mark as paid
        response = requests.put(
            f"{BASE_URL}/api/super-admin/invoices/{invoice_id}/status",
            json={"status": "paid"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "paid" in data["message"].lower()
        
        print(f"✓ Invoice {invoice_id} marked as paid")
        
        # Mark back as unpaid for future tests
        requests.put(
            f"{BASE_URL}/api/super-admin/invoices/{invoice_id}/status",
            json={"status": "unpaid"},
            headers=headers
        )
    
    def test_download_invoice_pdf(self, superadmin_token):
        """GET /api/super-admin/invoices/{id}/pdf returns valid PDF file"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        # Use the known existing invoice ID
        response = requests.get(
            f"{BASE_URL}/api/super-admin/invoices/{EXISTING_INVOICE_ID}/pdf",
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        
        # Check PDF signature (starts with %PDF)
        content = response.content
        assert content[:4] == b'%PDF', "Response is not a valid PDF"
        
        print(f"✓ Invoice PDF downloaded: {len(content)} bytes")
    
    def test_download_invoice_pdf_not_found(self, superadmin_token):
        """GET /api/super-admin/invoices/{id}/pdf returns error for invalid ID"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/super-admin/invoices/invalid-uuid-12345/pdf",
            headers=headers
        )
        
        # Should return JSON error, not PDF
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()
        
        print("✓ Invoice PDF correctly returns error for invalid ID")


class TestCustomerLedger:
    """Test customer ledger API"""
    
    def test_customer_ledger_returns_full_history(self, superadmin_token):
        """GET /api/super-admin/customer-ledger/{username} returns full payment and invoice history"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/super-admin/customer-ledger/{ADMIN_USERNAME}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        ledger = data["data"]
        assert "customer" in ledger
        assert "payments" in ledger
        assert "invoices" in ledger
        assert "total_paid" in ledger
        assert "total_billed" in ledger
        assert "balance_due" in ledger
        
        # Validate customer info
        customer = ledger["customer"]
        assert customer["username"] == ADMIN_USERNAME
        assert "plan" in customer
        assert "billing_cycle" in customer
        
        print(f"✓ Customer ledger for {ADMIN_USERNAME}:")
        print(f"  Total Paid: Rs.{ledger['total_paid']}, Total Billed: Rs.{ledger['total_billed']}, Balance Due: Rs.{ledger['balance_due']}")
        print(f"  Payments: {len(ledger['payments'])}, Invoices: {len(ledger['invoices'])}")
    
    def test_customer_ledger_not_found(self, superadmin_token):
        """GET /api/super-admin/customer-ledger/{username} returns error for invalid customer"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/super-admin/customer-ledger/nonexistent_user_xyz",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()
        
        print("✓ Customer ledger correctly returns error for invalid customer")


class TestCustomerHealth:
    """Test customer health monitoring API"""
    
    def test_customer_health_returns_all_tenants(self, superadmin_token):
        """GET /api/super-admin/customer-health returns all tenants with health status"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/super-admin/customer-health", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        health_data = data["data"]
        assert "customers" in health_data
        assert "total" in health_data
        
        customers = health_data["customers"]
        assert isinstance(customers, list)
        
        if len(customers) > 0:
            customer = customers[0]
            # Check required fields
            assert "username" in customer
            assert "health_status" in customer
            assert "last_sync" in customer or customer.get("health_status") == "never_synced"
            assert "inventory_items" in customer
            assert "sales_vouchers" in customer
            assert "total_paid" in customer
            assert "subscription_expires" in customer
            assert "days_left" in customer
            
            # Validate health_status values
            valid_statuses = ["active", "moderate", "inactive", "never_synced"]
            assert customer["health_status"] in valid_statuses
        
        print(f"✓ Customer health: {health_data['total']} customers")
        for c in customers[:3]:  # Show first 3
            print(f"  - {c['username']}: {c['health_status']}, Items: {c['inventory_items']}, Sales: {c['sales_vouchers']}")


class TestExistingAPIs:
    """Test existing SuperAdmin APIs still work"""
    
    def test_superadmin_stats(self, superadmin_token):
        """GET /api/super-admin/stats returns stats"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        print(f"✓ SuperAdmin stats: {data['data']}")
    
    def test_superadmin_admins_list(self, superadmin_token):
        """GET /api/super-admin/admins returns admin list"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        response = requests.get(f"{BASE_URL}/api/super-admin/admins", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "admins" in data["data"]
        
        print(f"✓ Admin list: {len(data['data']['admins'])} admins")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
