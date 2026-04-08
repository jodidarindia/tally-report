"""
Iteration 11: Testing 12 bug fixes related to FY-filtered logic, Sales filters, 
invoice modal details, AI Purchase order validation, and salesman item-wise UI.

Tests cover:
1. Inventory summary with FY filter
2. Sales summary with FY filter (top_customers, recent_vouchers)
3. Sales vouchers with FY filter (unique_parties, unique_months)
4. Sales vouchers with party_name and month filters
5. Customers outstanding with FY filter (customers, groups, states)
6. Customers payment-behavior with FY filter (credit_score, payment_pattern)
7. Customers targets with FY filter (targets array)
8. Salesman performance-detailed with FY filter (items_sold breakdown)
9. Inventory movement-analysis with FY filter
10. Inventory below-cost-sales with FY filter
11. Auth login endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test login with valid admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Login not successful: {data}"
        assert "token" in data.get("data", {}), "Token not in response"
        # API returns username/name/role directly in data, not nested under 'user'
        assert "username" in data.get("data", {}) or "name" in data.get("data", {}), "User info not in response"
        print(f"✓ Login successful, token received")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        # Should return 401 or success=false
        assert response.status_code in [401, 200], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == False, "Should fail with invalid credentials"
        print(f"✓ Invalid login correctly rejected")


class TestInventoryEndpoints:
    """Inventory endpoint tests with FY filter"""
    
    def test_inventory_summary_with_fy(self):
        """Test GET /api/inventory/summary?fy=2024-2025"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "total_items" in result, "Missing total_items"
        assert "total_value" in result, "Missing total_value"
        assert "low_stock_items" in result, "Missing low_stock_items"
        assert "categories" in result, "Missing categories"
        assert "fy_sales_value" in result, "Missing fy_sales_value (FY-specific)"
        print(f"✓ Inventory summary: {result['total_items']} items, FY sales value: {result['fy_sales_value']}")
    
    def test_inventory_summary_without_fy(self):
        """Test GET /api/inventory/summary without FY filter"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        print(f"✓ Inventory summary without FY works")
    
    def test_inventory_movement_analysis_with_fy(self):
        """Test GET /api/inventory/movement-analysis?fy=2024-2025"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "movements" in result, "Missing movements array"
        assert "summary" in result, "Missing summary"
        
        summary = result.get("summary", {})
        assert "fast_moving" in summary, "Missing fast_moving count"
        assert "slow_moving" in summary, "Missing slow_moving count"
        assert "dead_stock" in summary, "Missing dead_stock count"
        
        # Check movement item structure if any exist
        movements = result.get("movements", [])
        if movements:
            item = movements[0]
            assert "item_name" in item, "Missing item_name"
            assert "classification" in item, "Missing classification"
            assert "movement_rate" in item, "Missing movement_rate"
        print(f"✓ Movement analysis: {len(movements)} items, summary: {summary}")
    
    def test_inventory_below_cost_sales_with_fy(self):
        """Test GET /api/inventory/below-cost-sales?fy=2024-2025"""
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "below_cost_sales" in result, "Missing below_cost_sales array"
        assert "total_loss" in result, "Missing total_loss"
        assert "count" in result, "Missing count"
        print(f"✓ Below cost sales: {result['count']} items, total loss: {result['total_loss']}")


class TestSalesEndpoints:
    """Sales endpoint tests with FY filter and new filters"""
    
    def test_sales_summary_with_fy(self):
        """Test GET /api/sales/summary?fy=2024-2025 returns top_customers and recent_vouchers"""
        response = requests.get(f"{BASE_URL}/api/sales/summary?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "total_vouchers" in result, "Missing total_vouchers"
        assert "total_sales" in result, "Missing total_sales"
        assert "top_customers" in result, "Missing top_customers array"
        assert "recent_vouchers" in result, "Missing recent_vouchers array"
        
        # Verify top_customers structure if any exist
        top_customers = result.get("top_customers", [])
        if top_customers:
            cust = top_customers[0]
            assert "name" in cust, "Missing name in top_customer"
            assert "total" in cust, "Missing total in top_customer"
        print(f"✓ Sales summary: {result['total_vouchers']} vouchers, {len(top_customers)} top customers")
    
    def test_sales_vouchers_with_fy(self):
        """Test GET /api/sales/vouchers?fy=2024-2025 returns unique_parties and unique_months"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "vouchers" in result, "Missing vouchers array"
        assert "count" in result, "Missing count"
        assert "unique_parties" in result, "Missing unique_parties array (new filter)"
        assert "unique_months" in result, "Missing unique_months array (new filter)"
        
        print(f"✓ Sales vouchers: {result['count']} vouchers, {len(result['unique_parties'])} parties, {len(result['unique_months'])} months")
    
    def test_sales_vouchers_with_fy_2025_26(self):
        """Test GET /api/sales/vouchers?fy=2025-26 (alternate FY format)"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        print(f"✓ Sales vouchers with FY 2025-26: {data.get('data', {}).get('count', 0)} vouchers")
    
    def test_sales_vouchers_with_party_filter(self):
        """Test GET /api/sales/vouchers with party_name filter"""
        # First get list of parties
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        data = response.json()
        parties = data.get("data", {}).get("unique_parties", [])
        
        if parties:
            party = parties[0]
            response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26&party_name={party}")
            assert response.status_code == 200, f"Failed: {response.text}"
            data = response.json()
            assert data.get("success") == True, f"Not successful: {data}"
            print(f"✓ Sales vouchers filtered by party '{party}': {data.get('data', {}).get('count', 0)} vouchers")
        else:
            print("⚠ No parties available to test party filter")
    
    def test_sales_vouchers_with_month_filter(self):
        """Test GET /api/sales/vouchers with month filter"""
        # First get list of months
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        data = response.json()
        months = data.get("data", {}).get("unique_months", [])
        
        if months:
            month = months[0]
            response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26&month={month}")
            assert response.status_code == 200, f"Failed: {response.text}"
            data = response.json()
            assert data.get("success") == True, f"Not successful: {data}"
            print(f"✓ Sales vouchers filtered by month '{month}': {data.get('data', {}).get('count', 0)} vouchers")
        else:
            print("⚠ No months available to test month filter")


class TestCustomerEndpoints:
    """Customer CRM endpoint tests with FY filter"""
    
    def test_customers_outstanding_with_fy(self):
        """Test GET /api/customers/outstanding?fy=2024-2025 returns customers, groups, states"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "customers" in result, "Missing customers array"
        assert "total_outstanding" in result, "Missing total_outstanding"
        assert "groups" in result, "Missing groups array (for dropdown)"
        assert "states" in result, "Missing states array (for dropdown)"
        
        # Check customer structure if any exist
        customers = result.get("customers", [])
        if customers:
            cust = customers[0]
            # Check for aging columns
            assert "aging_0_30" in cust, "Missing aging_0_30"
            assert "aging_30_60" in cust, "Missing aging_30_60"
            assert "aging_60_90" in cust, "Missing aging_60_90"
            assert "aging_90_plus" in cust, "Missing aging_90_plus"
            # Check for paid_amount (from receipts)
            assert "paid_amount" in cust, "Missing paid_amount"
            assert "receipt_count" in cust, "Missing receipt_count"
        
        print(f"✓ Outstanding: {len(customers)} customers, {len(result['groups'])} groups, {len(result['states'])} states")
    
    def test_customers_payment_behavior_with_fy(self):
        """Test GET /api/customers/payment-behavior?fy=2024-2025 returns credit_score, payment_pattern"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "customers" in result, "Missing customers array"
        
        customers = result.get("customers", [])
        if customers:
            cust = customers[0]
            assert "credit_score" in cust, "Missing credit_score"
            assert "payment_pattern" in cust, "Missing payment_pattern"
            assert "payment_ratio" in cust, "Missing payment_ratio"
            assert "paid_amount" in cust, "Missing paid_amount"
            assert "outstanding_amount" in cust, "Missing outstanding_amount"
        
        print(f"✓ Payment behavior: {len(customers)} customers analyzed")
    
    def test_customers_targets_with_fy(self):
        """Test GET /api/customers/targets?fy=2024-2025 returns targets array"""
        response = requests.get(f"{BASE_URL}/api/customers/targets?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "targets" in result, "Missing targets array"
        assert "current_fy" in result, "Missing current_fy"
        assert "previous_fy" in result, "Missing previous_fy"
        
        targets = result.get("targets", [])
        if targets:
            target = targets[0]
            assert "customer_name" in target, "Missing customer_name"
            assert "target_amount" in target, "Missing target_amount"
            assert "last_fy_sales" in target, "Missing last_fy_sales (prev FY)"
            assert "achieved_amount" in target, "Missing achieved_amount (current FY)"
            assert "achievement_percentage" in target, "Missing achievement_percentage"
        
        print(f"✓ Targets: {len(targets)} customers, current_fy={result['current_fy']}, previous_fy={result['previous_fy']}")


class TestSalesmanEndpoints:
    """Salesman performance endpoint tests"""
    
    def test_salesman_performance_with_fy(self):
        """Test GET /api/salesman/performance?fy=2024-2025"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "salesman" in result, "Missing salesman array"
        print(f"✓ Salesman performance: {len(result.get('salesman', []))} salesmen")
    
    def test_salesman_performance_detailed_with_fy(self):
        """Test GET /api/salesman/performance-detailed?fy=2024-2025 returns items_sold breakdown"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance-detailed?fy=2024-2025")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Not successful: {data}"
        
        result = data.get("data", {})
        assert "salesman" in result, "Missing salesman array"
        
        salesmen = result.get("salesman", [])
        if salesmen:
            sm = salesmen[0]
            assert "salesman_name" in sm, "Missing salesman_name"
            assert "items_sold" in sm, "Missing items_sold breakdown"
            # API returns achieved_amount instead of total_sales
            assert "achieved_amount" in sm, "Missing achieved_amount"
            assert "total_customers" in sm, "Missing total_customers"
            
            # Check items_sold structure if any
            items_sold = sm.get("items_sold", [])
            if items_sold:
                item = items_sold[0]
                assert "item_name" in item, "Missing item_name in items_sold"
                assert "total_quantity" in item, "Missing total_quantity"
                assert "total_revenue" in item, "Missing total_revenue"
        
        print(f"✓ Salesman detailed: {len(salesmen)} salesmen with items_sold breakdown")


class TestVoucherDetailEndpoint:
    """Test voucher detail endpoint for discount/GST/dispatch fields"""
    
    def test_voucher_detail_structure(self):
        """Test GET /api/sales/vouchers/{voucher_id} returns discount, GST, dispatch details"""
        # First get a voucher ID
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        data = response.json()
        vouchers = data.get("data", {}).get("vouchers", [])
        
        if vouchers:
            voucher_id = vouchers[0].get("voucher_id", "")
            if voucher_id:
                # URL encode the voucher_id
                from urllib.parse import quote
                encoded_id = quote(voucher_id, safe='')
                
                response = requests.get(f"{BASE_URL}/api/sales/vouchers/{encoded_id}")
                assert response.status_code == 200, f"Failed: {response.text}"
                data = response.json()
                assert data.get("success") == True, f"Not successful: {data}"
                
                voucher = data.get("data", {})
                # Check for new invoice modal fields
                assert "subtotal" in voucher, "Missing subtotal"
                assert "discount_amount" in voucher, "Missing discount_amount"
                assert "gst_details" in voucher, "Missing gst_details"
                assert "gst_total" in voucher, "Missing gst_total"
                assert "dispatch_details" in voucher, "Missing dispatch_details"
                assert "computed_total" in voucher, "Missing computed_total"
                
                # Check dispatch_details structure
                dispatch = voucher.get("dispatch_details", {})
                assert "delivery_note" in dispatch, "Missing delivery_note in dispatch"
                assert "dispatch_through" in dispatch, "Missing dispatch_through"
                
                print(f"✓ Voucher detail: subtotal={voucher['subtotal']}, discount={voucher['discount_amount']}, gst_total={voucher['gst_total']}")
        else:
            print("⚠ No vouchers available to test voucher detail")


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_check(self):
        """Test basic API health via tally status endpoint"""
        response = requests.get(f"{BASE_URL}/api/tally/status")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✓ Health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
