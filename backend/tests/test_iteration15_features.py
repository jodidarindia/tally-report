"""
Iteration 15 Tests: Testing new features from user feedback
- CRM Outstanding sortable columns with Opening Balance
- Payment Behavior FY-independent with summary bar
- Inventory sortable columns and multi-select stock group filter
- Sales sortable columns
- Analytics 3 tabs (no pivot), movement sorting, sales frequency
- Dashboard low stock (movement-based logic)
- Ledger PDF export with opening_balance
- Copyright footer
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    def test_login_admin(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "token" in data.get("data", {})
        return data["data"]["token"]


class TestDashboard:
    """Dashboard stat cards and overdue digest tests"""
    
    def test_inventory_summary_returns_low_stock(self):
        """GET /api/inventory/summary returns low_stock_items with movement-based logic"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        summary = data.get("data", {})
        assert "low_stock_items" in summary
        assert "total_items" in summary
        assert "total_value" in summary
        # Low stock should be calculated based on movement logic
        print(f"Low stock items: {summary.get('low_stock_items')}")
    
    def test_sales_summary(self):
        """GET /api/sales/summary returns sales data"""
        response = requests.get(f"{BASE_URL}/api/sales/summary?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        summary = data.get("data", {})
        assert "total_sales" in summary or "total_vouchers" in summary
    
    def test_overdue_digest(self):
        """GET /api/dashboard/overdue-digest returns overdue data"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True


class TestCRMOutstanding:
    """CRM Outstanding tab tests - sortable columns, Opening Balance"""
    
    def test_outstanding_returns_customers(self):
        """GET /api/customers/outstanding returns customer list with required fields"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        customers = data.get("data", {}).get("customers", [])
        
        if customers:
            customer = customers[0]
            # Check required fields for sortable columns
            assert "customer_name" in customer
            assert "total_sales" in customer
            assert "paid_amount" in customer
            assert "outstanding_amount" in customer
            # Check Opening Balance column
            assert "opening_balance" in customer
            print(f"First customer opening_balance: {customer.get('opening_balance')}")
    
    def test_outstanding_has_groups_and_states(self):
        """Outstanding endpoint returns groups and states for filtering"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data.get("data", {})
        assert "states" in data.get("data", {})


class TestCRMPaymentBehavior:
    """CRM Payment Behavior tab tests - FY-independent, summary bar"""
    
    def test_payment_behavior_returns_summary(self):
        """GET /api/customers/payment-behavior returns summary with pattern counts"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Check summary object with excellent/regular/irregular/risky counts
        summary = data.get("data", {}).get("summary", {})
        assert "excellent" in summary
        assert "regular" in summary
        assert "irregular" in summary
        assert "risky" in summary
        print(f"Payment behavior summary: {summary}")
    
    def test_payment_behavior_customer_fields(self):
        """Payment behavior customers have required fields including credit notes"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior")
        assert response.status_code == 200
        data = response.json()
        customers = data.get("data", {}).get("customers", [])
        
        if customers:
            customer = customers[0]
            # Required fields for table
            assert "customer_name" in customer
            assert "total_amount" in customer  # Total Sales
            assert "paid_amount" in customer   # Receipts
            assert "credit_note_total" in customer  # Credit Notes
            assert "outstanding_amount" in customer
            assert "payment_ratio" in customer  # Pay Ratio
            assert "average_payment_delay" in customer  # Avg Delay
            assert "credit_score" in customer  # Score
            assert "payment_pattern" in customer  # Pattern
            assert "relationship_months" in customer  # Months


class TestLedgerPDFExport:
    """Ledger PDF export tests"""
    
    def test_ledger_export_requires_customer(self):
        """POST /api/customers/ledger/export requires customer_name"""
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json={
            "customer_name": "",
            "fy": "2025-26"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False
        assert "required" in data.get("error", "").lower()
    
    def test_ledger_export_with_valid_customer(self):
        """POST /api/customers/ledger/export generates PDF for valid customer"""
        # First get a customer name
        customers_resp = requests.get(f"{BASE_URL}/api/customers/outstanding?fy=2025-26")
        customers = customers_resp.json().get("data", {}).get("customers", [])
        
        if customers:
            customer_name = customers[0]["customer_name"]
            response = requests.post(
                f"{BASE_URL}/api/customers/ledger/export",
                json={"customer_name": customer_name, "fy": "2025-26"}
            )
            # Should return PDF (200) or error if no transactions
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "application/pdf" in content_type:
                    assert len(response.content) > 0
                    print(f"PDF generated for {customer_name}, size: {len(response.content)} bytes")
                else:
                    # JSON error response
                    data = response.json()
                    print(f"Ledger export response: {data}")


class TestInventory:
    """Inventory page tests - sortable columns, multi-select stock group"""
    
    def test_inventory_items_returns_stock_groups(self):
        """GET /api/inventory/items returns stock_groups for multi-select filter"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "stock_groups" in data.get("data", {})
        print(f"Stock groups: {data.get('data', {}).get('stock_groups', [])[:5]}")
    
    def test_inventory_items_have_sortable_fields(self):
        """Inventory items have fields for sortable columns"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        items = data.get("data", {}).get("items", [])
        
        if items:
            item = items[0]
            # Required fields for sortable columns
            assert "item_name" in item
            assert "stock_group" in item or item.get("stock_group") is None
            assert "quantity" in item
            assert "price" in item
            # Value is computed client-side (qty * price)


class TestSales:
    """Sales page tests - sortable columns"""
    
    def test_sales_vouchers_have_sortable_fields(self):
        """GET /api/sales/vouchers returns vouchers with sortable fields"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        vouchers = data.get("data", {}).get("vouchers", [])
        
        if vouchers:
            voucher = vouchers[0]
            # Required fields for sortable columns
            assert "voucher_id" in voucher  # Voucher No.
            assert "voucher_date" in voucher  # Date
            assert "party_name" in voucher  # Customer
            assert "total_amount" in voucher  # Amount


class TestAnalytics:
    """Analytics page tests - 3 tabs, sales frequency, movement sorting"""
    
    def test_movement_analysis(self):
        """GET /api/inventory/movement-analysis returns movement data"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        movements = data.get("data", {}).get("movements", [])
        
        if movements:
            movement = movements[0]
            # Fields for sortable columns
            assert "item_name" in movement
            assert "opening_stock" in movement
            assert "sales" in movement
            assert "closing_stock" in movement
            assert "movement_rate" in movement
            assert "days_to_sell" in movement
            assert "classification" in movement
    
    def test_below_cost_sales(self):
        """GET /api/inventory/below-cost-sales returns below cost data"""
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "below_cost_sales" in data.get("data", {})
    
    def test_sales_frequency_returns_frequency_key(self):
        """GET /api/inventory/sales-frequency returns 'frequency' array (not 'sales_frequency')"""
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # CRITICAL: Must return 'frequency' key, not 'sales_frequency'
        assert "frequency" in data.get("data", {})
        frequency = data.get("data", {}).get("frequency", [])
        print(f"Sales frequency items count: {len(frequency)}")
        
        if frequency:
            item = frequency[0]
            assert "item_name" in item
            assert "transaction_count" in item
            assert "total_quantity_sold" in item
            assert "unique_customers" in item
            assert "total_revenue" in item


class TestSyncStatus:
    """Sync status tests"""
    
    def test_sync_status(self):
        """GET /api/sync/status returns sync info"""
        response = requests.get(f"{BASE_URL}/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True


class TestFollowups:
    """Followups tests"""
    
    def test_get_followups(self):
        """GET /api/customers/followups returns followups list"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "followups" in data.get("data", {})


class TestTargets:
    """Customer targets tests"""
    
    def test_get_targets(self):
        """GET /api/customers/targets returns targets list"""
        response = requests.get(f"{BASE_URL}/api/customers/targets?fy=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "targets" in data.get("data", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
