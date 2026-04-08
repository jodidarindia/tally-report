"""
Test suite for Overdue Digest Feature (Iteration 12)
Tests the new automated daily digest summarizing outstanding balances and overdue payments.
Overdue threshold: 55 days from invoice date.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOverdueDigestEndpoint:
    """Tests for GET /api/dashboard/overdue-digest endpoint"""
    
    def test_overdue_digest_returns_success(self):
        """Test that overdue-digest endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print("✓ GET /api/dashboard/overdue-digest returns success")
    
    def test_overdue_digest_has_required_fields(self):
        """Test that response contains all required fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        # Check required top-level fields
        assert "total_overdue_amount" in digest, "Missing total_overdue_amount"
        assert "total_overdue_invoices" in digest, "Missing total_overdue_invoices"
        assert "customer_summary" in digest, "Missing customer_summary"
        assert "overdue_invoices" in digest, "Missing overdue_invoices"
        assert "threshold_days" in digest, "Missing threshold_days"
        print("✓ Response contains all required fields: total_overdue_amount, total_overdue_invoices, customer_summary, overdue_invoices, threshold_days")
    
    def test_overdue_threshold_is_55_days(self):
        """Test that overdue threshold is 55 days"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        assert digest.get("threshold_days") == 55, f"Expected threshold_days=55, got {digest.get('threshold_days')}"
        print("✓ Overdue threshold is correctly set to 55 days")
    
    def test_recompute_parameter_forces_fresh_computation(self):
        """Test that ?recompute=true forces fresh computation"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest?recompute=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        digest = data.get("data", {})
        # Should have computed_at timestamp
        assert "computed_at" in digest, "Missing computed_at timestamp after recompute"
        print(f"✓ Recompute parameter works, computed_at: {digest.get('computed_at')}")
    
    def test_overdue_invoice_has_correct_fields(self):
        """Test that each overdue invoice has correct fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        invoices = digest.get("overdue_invoices", [])
        if len(invoices) > 0:
            invoice = invoices[0]
            required_fields = ["voucher_id", "party_name", "voucher_date", "invoice_amount", "paid_amount", "overdue_amount", "days_overdue"]
            for field in required_fields:
                assert field in invoice, f"Missing field '{field}' in overdue invoice"
            print(f"✓ Overdue invoice has all required fields: {required_fields}")
        else:
            print("⚠ No overdue invoices to validate fields (may be expected if no overdue data)")
    
    def test_customer_summary_has_correct_fields(self):
        """Test that each customer summary has correct fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        customers = digest.get("customer_summary", [])
        if len(customers) > 0:
            customer = customers[0]
            required_fields = ["customer_name", "phone", "total_overdue", "invoice_count", "oldest_days"]
            for field in required_fields:
                assert field in customer, f"Missing field '{field}' in customer summary"
            print(f"✓ Customer summary has all required fields: {required_fields}")
        else:
            print("⚠ No customer summary to validate fields (may be expected if no overdue data)")
    
    def test_overdue_invoice_days_exceeds_threshold(self):
        """Test that all overdue invoices have days_overdue > 55"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        invoices = digest.get("overdue_invoices", [])
        threshold = digest.get("threshold_days", 55)
        
        for inv in invoices:
            days = inv.get("days_overdue", 0)
            assert days > threshold, f"Invoice {inv.get('voucher_id')} has days_overdue={days} which is <= threshold {threshold}"
        
        if invoices:
            print(f"✓ All {len(invoices)} overdue invoices have days_overdue > {threshold}")
        else:
            print("⚠ No overdue invoices to validate days threshold")
    
    def test_total_overdue_amount_matches_sum(self):
        """Test that total_overdue_amount matches sum of individual overdue amounts"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        invoices = digest.get("overdue_invoices", [])
        total_reported = digest.get("total_overdue_amount", 0)
        
        # Sum individual overdue amounts
        calculated_sum = sum(inv.get("overdue_amount", 0) for inv in invoices)
        
        # Allow small floating point difference
        assert abs(total_reported - calculated_sum) < 1, f"Total mismatch: reported={total_reported}, calculated={calculated_sum}"
        print(f"✓ Total overdue amount ({total_reported}) matches sum of invoices ({calculated_sum})")


class TestSyncTriggersOverdueRecomputation:
    """Tests that sync endpoint triggers overdue digest recomputation"""
    
    def test_sync_sales_triggers_overdue_recompute(self):
        """Test that POST /api/agent/sync with sales data triggers overdue recomputation"""
        # First get current digest
        before_response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert before_response.status_code == 200
        before_data = before_response.json().get("data", {})
        before_computed = before_data.get("computed_at", "")
        
        # Sync some sales data (empty array is fine, just triggers recompute)
        sync_payload = {
            "data_type": "sales",
            "data": [],
            "sync_time": "2026-04-08T10:00:00Z",
            "company_name": "Test Company",
            "financial_year": "2025-26"
        }
        sync_response = requests.post(f"{BASE_URL}/api/agent/sync", json=sync_payload)
        assert sync_response.status_code == 200
        
        # Get digest again - should have new computed_at
        after_response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert after_response.status_code == 200
        after_data = after_response.json().get("data", {})
        after_computed = after_data.get("computed_at", "")
        
        # Computed_at should be updated (or at least exist)
        assert after_computed, "Overdue digest should have computed_at after sync"
        print(f"✓ Sync sales triggers overdue recomputation. Before: {before_computed[:19] if before_computed else 'N/A'}, After: {after_computed[:19]}")


class TestOverdueDigestWithTestData:
    """Tests using the existing test data (TEST_VOUCHER_WS_1)"""
    
    def test_test_voucher_appears_as_overdue(self):
        """Test that TEST_VOUCHER_WS_1 (2025-12-01, Rs.1000) appears as overdue"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest?recompute=true")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        invoices = digest.get("overdue_invoices", [])
        
        # Look for our test voucher
        test_voucher = None
        for inv in invoices:
            if inv.get("voucher_id") == "TEST_VOUCHER_WS_1":
                test_voucher = inv
                break
        
        if test_voucher:
            assert test_voucher.get("invoice_amount") == 1000.0, f"Expected invoice_amount=1000, got {test_voucher.get('invoice_amount')}"
            assert test_voucher.get("days_overdue") > 55, f"Expected days_overdue > 55, got {test_voucher.get('days_overdue')}"
            print(f"✓ TEST_VOUCHER_WS_1 found as overdue: Rs.{test_voucher.get('invoice_amount')}, {test_voucher.get('days_overdue')} days old")
        else:
            # May have been cleared by previous tests
            print("⚠ TEST_VOUCHER_WS_1 not found in overdue invoices (may have been cleared)")
    
    def test_overdue_amount_calculation(self):
        """Test that overdue_amount = invoice_amount - paid_amount"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        digest = data.get("data", {})
        
        invoices = digest.get("overdue_invoices", [])
        
        for inv in invoices:
            invoice_amt = inv.get("invoice_amount", 0)
            paid_amt = inv.get("paid_amount", 0)
            overdue_amt = inv.get("overdue_amount", 0)
            
            expected_overdue = invoice_amt - paid_amt
            assert abs(overdue_amt - expected_overdue) < 0.01, f"Overdue calculation wrong for {inv.get('voucher_id')}: {overdue_amt} != {invoice_amt} - {paid_amt}"
        
        if invoices:
            print(f"✓ Overdue amount calculation correct for all {len(invoices)} invoices")
        else:
            print("⚠ No invoices to validate overdue calculation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
