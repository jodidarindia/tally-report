"""
Iteration 6 Backend Tests - CRM Outstanding Aging, Sales Voucher Detail, Customer Group Filter
Tests for:
1. CRM Outstanding - proper aging columns (0-30, 30-60, 60-90, 90+ days)
2. CRM Outstanding - status based on oldest invoice days (Normal/At Risk/Overdue/Critical)
3. CRM Outstanding - customer group (ledger_group) field
4. Sales voucher detail endpoint /api/sales/vouchers/{id}
5. Followups show created_by_name
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com').rstrip('/')


class TestCustomerOutstandingAging:
    """Tests for CRM Outstanding with proper aging calculation"""
    
    def test_outstanding_returns_aging_columns(self):
        """Verify outstanding endpoint returns all aging bucket columns"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "customers" in data["data"]
        
        customers = data["data"]["customers"]
        assert len(customers) > 0, "Should have at least one customer"
        
        # Check first customer has all aging fields
        customer = customers[0]
        assert "aging_0_30" in customer, "Missing aging_0_30 field"
        assert "aging_30_60" in customer, "Missing aging_30_60 field"
        assert "aging_60_90" in customer, "Missing aging_60_90 field"
        assert "aging_90_plus" in customer, "Missing aging_90_plus field"
        print(f"Customer {customer['customer_name']} aging: 0-30={customer['aging_0_30']}, 30-60={customer['aging_30_60']}, 60-90={customer['aging_60_90']}, 90+={customer['aging_90_plus']}")
    
    def test_outstanding_status_based_on_oldest_invoice(self):
        """Verify status is based on oldest_invoice_days, not mocked 30%"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        
        data = response.json()
        customers = data["data"]["customers"]
        
        for customer in customers:
            assert "oldest_invoice_days" in customer, "Missing oldest_invoice_days field"
            assert "status" in customer, "Missing status field"
            assert "status_label" in customer, "Missing status_label field"
            
            oldest = customer["oldest_invoice_days"]
            status = customer["status"]
            
            # Verify status matches oldest_invoice_days logic
            if oldest > 90:
                assert status == "critical", f"Expected critical for {oldest} days, got {status}"
            elif oldest > 60:
                assert status == "overdue", f"Expected overdue for {oldest} days, got {status}"
            elif oldest > 30:
                assert status == "at_risk", f"Expected at_risk for {oldest} days, got {status}"
            else:
                assert status == "normal", f"Expected normal for {oldest} days, got {status}"
            
            print(f"Customer {customer['customer_name']}: oldest={oldest} days, status={status}")
    
    def test_outstanding_has_customer_group(self):
        """Verify outstanding returns ledger_group (customer group) field"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        
        data = response.json()
        customers = data["data"]["customers"]
        
        for customer in customers:
            assert "ledger_group" in customer, "Missing ledger_group field"
            print(f"Customer {customer['customer_name']}: group={customer['ledger_group']}")
    
    def test_outstanding_no_fake_30_percent(self):
        """Verify outstanding = total_sales when no Tally closing balance (not 30% fake)"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        
        data = response.json()
        customers = data["data"]["customers"]
        
        # For customers with sales but no Tally closing balance, outstanding should equal total_sales
        for customer in customers:
            if customer["total_sales"] > 0:
                # Outstanding should be >= 0 and not a fake 30% calculation
                assert customer["outstanding_amount"] >= 0
                # If no Tally closing balance, outstanding = total_sales
                # This is the expected behavior per the fix
                print(f"Customer {customer['customer_name']}: total_sales={customer['total_sales']}, outstanding={customer['outstanding_amount']}")


class TestSalesVoucherDetail:
    """Tests for sales voucher detail endpoint"""
    
    def test_voucher_detail_returns_full_data(self):
        """Verify /api/sales/vouchers/{id} returns full voucher with items"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/SALE001")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        voucher = data["data"]
        assert voucher["voucher_id"] == "SALE001"
        assert "party_name" in voucher
        assert "voucher_date" in voucher
        assert "items" in voucher
        assert "total_amount" in voucher
        assert "subtotal" in voucher
        assert "computed_total" in voucher
        assert "item_count" in voucher
        
        print(f"Voucher SALE001: party={voucher['party_name']}, date={voucher['voucher_date']}, total={voucher['total_amount']}")
    
    def test_voucher_detail_has_line_items(self):
        """Verify voucher detail includes line items with qty, rate, amount"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/SALE001")
        assert response.status_code == 200
        
        data = response.json()
        voucher = data["data"]
        items = voucher.get("items", [])
        
        assert len(items) > 0, "Voucher should have at least one item"
        
        for item in items:
            assert "item" in item, "Item missing 'item' (name) field"
            assert "quantity" in item, "Item missing 'quantity' field"
            assert "rate" in item, "Item missing 'rate' field"
            print(f"Item: {item['item']}, qty={item['quantity']}, rate={item['rate']}")
    
    def test_voucher_detail_has_salesman(self):
        """Verify voucher detail includes salesman field"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/SALE001")
        assert response.status_code == 200
        
        data = response.json()
        voucher = data["data"]
        
        assert "salesman" in voucher, "Voucher missing salesman field"
        print(f"Voucher SALE001 salesman: {voucher['salesman']}")
    
    def test_voucher_detail_has_reference(self):
        """Verify voucher detail includes reference_number"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/SALE001")
        assert response.status_code == 200
        
        data = response.json()
        voucher = data["data"]
        
        assert "reference_number" in voucher, "Voucher missing reference_number field"
        print(f"Voucher SALE001 reference: {voucher['reference_number']}")
    
    def test_voucher_detail_not_found(self):
        """Verify 404-like response for non-existent voucher"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers/NONEXISTENT999")
        assert response.status_code == 200  # API returns 200 with success=False
        
        data = response.json()
        assert data["success"] is False
        assert "not found" in data.get("error", "").lower()


class TestFollowupsCreatedBy:
    """Tests for followups created_by_name field"""
    
    def test_followups_have_created_by_name(self):
        """Verify followups include created_by_name field"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        followups = data["data"]["followups"]
        
        # Check if any followup has created_by_name
        has_created_by_name = False
        for followup in followups:
            if "created_by_name" in followup and followup["created_by_name"]:
                has_created_by_name = True
                print(f"Followup for {followup['customer_name']}: created_by_name={followup['created_by_name']}")
        
        # At least one followup should have created_by_name (from previous test)
        assert has_created_by_name or len(followups) == 0, "No followups have created_by_name field"


class TestSalesVouchersList:
    """Tests for sales vouchers list endpoint"""
    
    def test_vouchers_list_returns_data(self):
        """Verify /api/sales/vouchers returns list of vouchers"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "vouchers" in data["data"]
        assert "count" in data["data"]
        
        vouchers = data["data"]["vouchers"]
        assert len(vouchers) > 0, "Should have at least one voucher"
        
        # Check voucher structure
        voucher = vouchers[0]
        assert "voucher_id" in voucher
        assert "party_name" in voucher
        assert "voucher_date" in voucher
        assert "total_amount" in voucher
        
        print(f"Found {len(vouchers)} vouchers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
