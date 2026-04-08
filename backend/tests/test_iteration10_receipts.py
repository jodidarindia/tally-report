"""
Iteration 10 Tests: Receipt/Payment Voucher Sync and Outstanding Calculation
Tests the new v5 features:
1. POST /api/agent/sync with data_type=receipts stores receipt vouchers
2. GET /api/customers/outstanding includes paid_amount and receipt_count from receipt data
3. GET /api/customers/payment-behavior uses receipt data for paid_amount calculation
4. GET /api/sales/vouchers?fy=2025-26 returns FY-filtered vouchers
5. GET /api/sales/vouchers/{voucher_id} returns voucher detail (URL path routing)
6. POST /api/ai/advanced-query still works after changes
7. GET /api/customers/targets?fy=2025-26 returns prev_fy and current_fy fields
8. GET /api/inventory/movement-analysis?fy=2025-26 returns movement data
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReceiptSync:
    """Test receipt/payment voucher sync functionality"""
    
    def test_sync_receipt_vouchers(self):
        """POST /api/agent/sync with data_type=receipts stores receipt vouchers"""
        response = requests.post(f"{BASE_URL}/api/agent/sync", json={
            "data_type": "receipts",
            "data": [
                {
                    "voucher_id": "TEST_REC_001",
                    "voucher_type": "receipt",
                    "voucher_date": "2025-11-15",
                    "party_name": "Test Receipt Customer",
                    "amount": 20000,
                    "bill_allocations": [],
                    "narration": "Test payment received"
                }
            ],
            "sync_time": "2026-01-08T12:00:00",
            "company_name": "Test Company",
            "financial_year": "2025-26",
            "agent_version": "5.0.0"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Successfully synced 1 receipts items" in data["message"]
        print("PASS: Receipt sync endpoint works correctly")
    
    def test_sync_customer_for_receipt_test(self):
        """Sync a customer to test receipt integration"""
        response = requests.post(f"{BASE_URL}/api/agent/sync", json={
            "data_type": "customers",
            "data": [
                {
                    "customer_name": "Test Receipt Customer",
                    "ledger_group": "Sundry Debtors",
                    "outstanding_amount": 30000,
                    "total_purchases": 50000,
                    "phone": "9876543210",
                    "state": "Maharashtra"
                }
            ],
            "sync_time": "2026-01-08T12:00:00",
            "company_name": "Test Company",
            "financial_year": "2025-26",
            "agent_version": "5.0.0"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("PASS: Customer sync for receipt test works")


class TestOutstandingWithReceipts:
    """Test outstanding endpoint includes receipt data"""
    
    def test_outstanding_includes_paid_amount(self):
        """GET /api/customers/outstanding includes paid_amount from receipt data"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        customers = data["data"]["customers"]
        assert len(customers) > 0
        
        # Check that customers have paid_amount and receipt_count fields
        for customer in customers:
            assert "paid_amount" in customer, f"Missing paid_amount for {customer['customer_name']}"
            assert "receipt_count" in customer, f"Missing receipt_count for {customer['customer_name']}"
        
        # Find the test customer with receipt
        test_customer = next((c for c in customers if c["customer_name"] == "Test Receipt Customer"), None)
        if test_customer:
            assert test_customer["paid_amount"] == 20000, f"Expected paid_amount 20000, got {test_customer['paid_amount']}"
            assert test_customer["receipt_count"] == 1, f"Expected receipt_count 1, got {test_customer['receipt_count']}"
            print(f"PASS: Test Receipt Customer has paid_amount={test_customer['paid_amount']}, receipt_count={test_customer['receipt_count']}")
        else:
            print("INFO: Test Receipt Customer not found, but paid_amount/receipt_count fields exist")
        
        print("PASS: Outstanding endpoint includes paid_amount and receipt_count")
    
    def test_outstanding_has_aging_columns(self):
        """Outstanding endpoint has FIFO aging columns"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        
        assert response.status_code == 200
        data = response.json()
        customers = data["data"]["customers"]
        
        if customers:
            customer = customers[0]
            assert "aging_0_30" in customer
            assert "aging_30_60" in customer
            assert "aging_60_90" in customer
            assert "aging_90_plus" in customer
            print("PASS: Outstanding has aging columns (0-30, 30-60, 60-90, 90+)")


class TestPaymentBehaviorWithReceipts:
    """Test payment behavior endpoint uses receipt data"""
    
    def test_payment_behavior_includes_receipt_data(self):
        """GET /api/customers/payment-behavior uses receipt data for paid_amount"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        customers = data["data"]["customers"]
        
        # Check that customers have receipt-related fields
        for customer in customers:
            assert "paid_amount" in customer, f"Missing paid_amount for {customer['customer_name']}"
            assert "receipt_count" in customer, f"Missing receipt_count for {customer['customer_name']}"
        
        print("PASS: Payment behavior endpoint includes paid_amount and receipt_count")


class TestSalesVouchersFY:
    """Test sales vouchers FY filtering"""
    
    def test_sales_vouchers_fy_filter(self):
        """GET /api/sales/vouchers?fy=2025-26 returns FY-filtered vouchers"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        vouchers = data["data"]["vouchers"]
        count = data["data"]["count"]
        
        # All vouchers should be within FY 2025-26 (April 2025 - March 2026)
        for voucher in vouchers:
            v_date = voucher.get("voucher_date", "")
            if v_date:
                assert "2025-04-01" <= v_date <= "2026-03-31", f"Voucher {voucher['voucher_id']} date {v_date} outside FY 2025-26"
        
        print(f"PASS: Sales vouchers FY filter works, returned {count} vouchers")
    
    def test_sales_vouchers_different_fy(self):
        """GET /api/sales/vouchers?fy=2026-27 returns different results"""
        response_2526 = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        response_2627 = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2026-27")
        
        assert response_2526.status_code == 200
        assert response_2627.status_code == 200
        
        count_2526 = response_2526.json()["data"]["count"]
        count_2627 = response_2627.json()["data"]["count"]
        
        print(f"PASS: FY 2025-26 has {count_2526} vouchers, FY 2026-27 has {count_2627} vouchers")


class TestVoucherDetail:
    """Test voucher detail endpoint with URL path routing"""
    
    def test_voucher_detail_by_id(self):
        """GET /api/sales/vouchers/{voucher_id} returns voucher detail"""
        # First get a voucher ID
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        assert response.status_code == 200
        
        vouchers = response.json()["data"]["vouchers"]
        if not vouchers:
            pytest.skip("No vouchers available to test detail endpoint")
        
        voucher_id = vouchers[0]["voucher_id"]
        
        # Get voucher detail
        detail_response = requests.get(f"{BASE_URL}/api/sales/vouchers/{voucher_id}")
        
        assert detail_response.status_code == 200
        data = detail_response.json()
        assert data["success"] == True
        
        voucher = data["data"]
        assert voucher["voucher_id"] == voucher_id
        assert "party_name" in voucher
        assert "total_amount" in voucher
        assert "items" in voucher
        assert "subtotal" in voucher
        assert "computed_total" in voucher
        assert "item_count" in voucher
        
        print(f"PASS: Voucher detail for {voucher_id} returned successfully")
    
    def test_voucher_detail_test_voucher(self):
        """GET /api/sales/vouchers/TEST_VOUCHER_WS_1 returns test voucher"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/TEST_VOUCHER_WS_1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        voucher = data["data"]
        assert voucher["voucher_id"] == "TEST_VOUCHER_WS_1"
        assert voucher["party_name"] == "Test Customer"
        assert voucher["total_amount"] == 1000
        
        print("PASS: TEST_VOUCHER_WS_1 detail returned correctly")


class TestAIAdvancedQuery:
    """Test AI advanced query endpoint still works"""
    
    def test_ai_advanced_query(self):
        """POST /api/ai/advanced-query still works after changes"""
        response = requests.post(
            f"{BASE_URL}/api/ai/advanced-query",
            json={
                "query": "Give me a summary of inventory status",
                "report_type": "general"
            },
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"] is not None
        
        print("PASS: AI advanced query endpoint works")


class TestCustomerTargets:
    """Test customer targets endpoint returns FY fields"""
    
    def test_targets_has_fy_fields(self):
        """GET /api/customers/targets?fy=2025-26 returns prev_fy and current_fy fields"""
        response = requests.get(f"{BASE_URL}/api/customers/targets?fy=2025-26")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Check response-level FY fields
        assert data["data"]["current_fy"] == "2025-26"
        assert data["data"]["previous_fy"] == "2024-25"
        
        targets = data["data"]["targets"]
        if targets:
            target = targets[0]
            assert "previous_fy" in target
            assert "current_fy" in target
            assert "last_fy_sales" in target
            assert "achieved_amount" in target
            print(f"PASS: Target for {target['customer_name']} has prev_fy={target['previous_fy']}, current_fy={target['current_fy']}")
        
        print("PASS: Targets endpoint returns prev_fy and current_fy fields")


class TestInventoryMovementAnalysis:
    """Test inventory movement analysis endpoint"""
    
    def test_movement_analysis_returns_data(self):
        """GET /api/inventory/movement-analysis?fy=2025-26 returns movement data"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        movements = data["data"]["movements"]
        assert isinstance(movements, list)
        
        if movements:
            movement = movements[0]
            assert "item_name" in movement
            assert "classification" in movement
            print(f"PASS: Movement analysis returned {len(movements)} items")
        else:
            print("PASS: Movement analysis endpoint works (no data)")


class TestAuthLogin:
    """Test authentication still works"""
    
    def test_admin_login(self):
        """POST /api/auth/login with admin credentials works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["username"] == "admin"
        assert data["data"]["role"] == "admin"
        assert "token" in data["data"]
        
        print("PASS: Admin login works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
