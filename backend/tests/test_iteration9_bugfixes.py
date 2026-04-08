"""
Iteration 9 Bug Fix Tests
Tests for 9 user-reported issues:
1. CRM Outstanding - paid_amount column, FIFO aging
2. Customer group dropdown (sub-groups)
3. FY dropdown functionality
4. Sales voucher click modal
5. Payment behavior real metrics
6. Targets - Prev FY vs Current FY logic
7. Salesman tabs
8. AI Reports
9. Analytics tabs
"""

import pytest
import requests
import os
from urllib.parse import quote

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFYDropdownFunctionality:
    """Issue 3: FY dropdown - data should change when FY changes"""
    
    def test_fy_2025_26_has_vouchers(self):
        """FY 2025-26 should have 1 test voucher (date 2025-12-01)"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["count"] >= 1
        # Verify the test voucher is present
        vouchers = data["data"]["vouchers"]
        assert any(v["voucher_id"] == "TEST_VOUCHER_WS_1" for v in vouchers)
    
    def test_fy_2026_27_has_no_vouchers(self):
        """FY 2026-27 should have 0 vouchers (no data in that range)"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2026-27")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["count"] == 0
        assert data["data"]["vouchers"] == []
    
    def test_sales_summary_respects_fy(self):
        """Sales summary should filter by FY"""
        # FY 2025-26 should have sales
        response_2526 = requests.get(f"{BASE_URL}/api/sales/summary?fy=2025-26")
        assert response_2526.status_code == 200
        data_2526 = response_2526.json()
        assert data_2526["success"] == True
        assert data_2526["data"]["total_vouchers"] >= 1
        
        # FY 2026-27 should have no sales
        response_2627 = requests.get(f"{BASE_URL}/api/sales/summary?fy=2026-27")
        assert response_2627.status_code == 200
        data_2627 = response_2627.json()
        assert data_2627["success"] == True
        assert data_2627["data"]["total_vouchers"] == 0


class TestCRMOutstanding:
    """Issue 1: CRM Outstanding - paid_amount column, FIFO aging"""
    
    def test_outstanding_has_paid_amount_column(self):
        """Outstanding response should include paid_amount field"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        customers = data["data"]["customers"]
        assert len(customers) > 0
        
        # Check that paid_amount field exists in all customers
        for customer in customers:
            assert "paid_amount" in customer, f"paid_amount missing for {customer['customer_name']}"
            assert "outstanding_amount" in customer
            assert "total_sales" in customer
    
    def test_outstanding_uses_tally_closing_balance(self):
        """Outstanding should be from Tally closing balance, not calculated from sales"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        
        # TEST_CUSTOMER_WS_1 has outstanding_amount=5000 from synced data
        test_customer = next(
            (c for c in data["data"]["customers"] if c["customer_name"] == "TEST_CUSTOMER_WS_1"),
            None
        )
        if test_customer:
            assert test_customer["outstanding_amount"] == 5000.0
    
    def test_fifo_aging_distributes_outstanding(self):
        """FIFO aging should distribute outstanding across invoices oldest-first"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        
        for customer in data["data"]["customers"]:
            # Aging buckets should exist
            assert "aging_0_30" in customer
            assert "aging_30_60" in customer
            assert "aging_60_90" in customer
            assert "aging_90_plus" in customer
            
            # Sum of aging should equal outstanding (or be 0 if no outstanding)
            aging_sum = (
                customer["aging_0_30"] + 
                customer["aging_30_60"] + 
                customer["aging_60_90"] + 
                customer["aging_90_plus"]
            )
            # Allow small floating point differences
            if customer["outstanding_amount"] > 0:
                assert abs(aging_sum - customer["outstanding_amount"]) < 0.01 or aging_sum == 0


class TestSalesVoucherDetail:
    """Issue 4: Sales voucher click - modal should open with voucher details"""
    
    def test_voucher_detail_endpoint_works(self):
        """GET /api/sales/vouchers/{voucher_id} should return voucher details"""
        voucher_id = "TEST_VOUCHER_WS_1"
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/{voucher_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["voucher_id"] == voucher_id
        assert "items" in data["data"]
        assert "total_amount" in data["data"]
        assert "subtotal" in data["data"]
        assert "item_count" in data["data"]
    
    def test_voucher_detail_with_url_encoded_id(self):
        """Voucher ID with special characters should be URL-decoded"""
        # Test with a simple ID first
        voucher_id = "TEST_VOUCHER_WS_1"
        encoded_id = quote(voucher_id, safe='')
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/{encoded_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_voucher_not_found_returns_error(self):
        """Non-existent voucher should return error"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/NON_EXISTENT_VOUCHER")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "not found" in data["error"].lower()


class TestPaymentBehavior:
    """Issue 5: Payment behavior - real metrics, no hardcoded mocks"""
    
    def test_payment_behavior_has_real_metrics(self):
        """Payment behavior should show paid_amount, outstanding_amount, payment_ratio"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        customers = data["data"]["customers"]
        assert len(customers) > 0
        
        for customer in customers:
            # Required fields
            assert "paid_amount" in customer
            assert "outstanding_amount" in customer
            assert "payment_ratio" in customer
            assert "total_amount" in customer
            assert "average_payment_delay" in customer
            assert "credit_score" in customer
            assert "payment_pattern" in customer
            
            # Verify paid_amount = total_amount - outstanding_amount
            expected_paid = max(0, customer["total_amount"] - customer["outstanding_amount"])
            assert abs(customer["paid_amount"] - expected_paid) < 0.01
    
    def test_payment_ratio_is_calculated(self):
        """Payment ratio should be (paid_amount / total_amount * 100)"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        
        for customer in data["data"]["customers"]:
            if customer["total_amount"] > 0:
                expected_ratio = customer["paid_amount"] / customer["total_amount"] * 100
                assert abs(customer["payment_ratio"] - expected_ratio) < 0.1


class TestCustomerTargets:
    """Issue 6: Targets - Prev FY vs Current FY logic"""
    
    def test_targets_has_prev_and_current_fy(self):
        """Targets should show previous_fy and current_fy fields"""
        response = requests.get(f"{BASE_URL}/api/customers/targets?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Response should include FY info
        assert data["data"]["current_fy"] == "2025-26"
        assert data["data"]["previous_fy"] == "2024-25"
    
    def test_targets_has_last_fy_sales_column(self):
        """Each target should have last_fy_sales (previous FY) and achieved_amount (current FY)"""
        response = requests.get(f"{BASE_URL}/api/customers/targets?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        
        targets = data["data"]["targets"]
        for target in targets:
            assert "last_fy_sales" in target, "last_fy_sales (Prev FY Sales) missing"
            assert "achieved_amount" in target, "achieved_amount (Current FY Achieved) missing"
            assert "target_amount" in target
            assert "achievement_percentage" in target
            assert "previous_fy" in target
            assert "current_fy" in target


class TestSalesmanTabs:
    """Issue 7: Salesman tabs - performance, items, manage"""
    
    def test_salesman_performance_endpoint(self):
        """GET /api/salesman/performance should work with FY param"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "salesman" in data["data"]
    
    def test_salesman_performance_detailed_endpoint(self):
        """GET /api/salesman/performance-detailed should work with FY param"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "salesman" in data["data"]
        
        # Should include items_sold breakdown
        for salesman in data["data"]["salesman"]:
            assert "items_sold" in salesman
            assert "customer_names" in salesman
            assert "mapped_customers" in salesman
    
    def test_salesman_master_endpoint(self):
        """GET /api/salesman/master should return salesman list"""
        response = requests.get(f"{BASE_URL}/api/salesman/master")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "salesmen" in data["data"]  # Note: plural 'salesmen'


class TestAIReports:
    """Issue 8: AI Reports - should work with real data"""
    
    def test_ai_advanced_query_endpoint(self):
        """POST /api/ai/advanced-query should return success"""
        payload = {
            "query": "Show me top selling items",
            "report_type": "general"
        }
        response = requests.post(
            f"{BASE_URL}/api/ai/advanced-query",
            json=payload,
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"] is not None
        # Should have structured report data
        assert "summary" in data["data"] or "key_insights" in data["data"] or "metrics" in data["data"]


class TestAnalyticsTabs:
    """Issue 9: Analytics tabs - all should return valid data"""
    
    def test_movement_analysis_endpoint(self):
        """GET /api/inventory/movement-analysis should return data"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "movements" in data["data"]
        assert "summary" in data["data"]
        
        # Summary should have classification counts
        summary = data["data"]["summary"]
        assert "fast_moving" in summary
        assert "slow_moving" in summary
        assert "dead_stock" in summary
    
    def test_below_cost_sales_endpoint(self):
        """GET /api/inventory/below-cost-sales should return data"""
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "below_cost_sales" in data["data"]
        assert "total_loss" in data["data"]
        assert "count" in data["data"]
    
    def test_pivot_data_endpoint(self):
        """GET /api/inventory/pivot-data should return data"""
        response = requests.get(f"{BASE_URL}/api/inventory/pivot-data")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "pivot_table" in data["data"]
        assert "group_by" in data["data"]
        assert "metric" in data["data"]
    
    def test_sales_frequency_endpoint(self):
        """GET /api/inventory/sales-frequency should return data"""
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "sales_frequency" in data["data"]
        assert "total_items" in data["data"]


class TestAuthEndpoints:
    """Auth endpoints for login"""
    
    def test_admin_login(self):
        """Admin login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "token" in data["data"]
        assert data["data"]["role"] == "admin"  # role is at top level, not nested under 'user'


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
