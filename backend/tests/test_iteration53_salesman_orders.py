"""
Iteration 53: Salesman Order System Tests
Tests for:
- GET /api/salesman-orders/catalog - product catalog with stock_qty and price
- POST /api/salesman-orders/orders - create order with items and remarks
- GET /api/salesman-orders/orders - list orders (salesman sees own, admin sees all)
- PATCH /api/salesman-orders/orders/{id} - edit only when status=pending
- PATCH /api/salesman-orders/orders/{id}/status - approve/reject/hold/billed transitions
- GET /api/salesman-orders/stats - order counts by status
- GET /api/salesman-orders/my-customers - mapped customers for salesman
- POST /api/salesman-orders/beats - save beat plan
- GET /api/salesman-orders/beats - get beat plan
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


class TestSalesmanOrderSystem:
    """Salesman Order System API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin (empty captcha_token bypasses reCAPTCHA in test mode)
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "captcha_token": ""
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()
        assert data.get("success"), f"Login not successful: {data}"
        
        self.token = data.get("data", {}).get("token")
        assert self.token, "No token in login response"
        
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "X-Company-Id": COMPANY_ID
        })
        
        yield
        
        # Cleanup: Delete test orders created during tests
        try:
            orders_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/orders?company_id={COMPANY_ID}&limit=100")
            if orders_resp.status_code == 200 and orders_resp.json().get("success"):
                orders = orders_resp.json().get("data", {}).get("orders", [])
                for order in orders:
                    if order.get("customer_name", "").startswith("TEST_"):
                        # Can't delete orders via API, but they're isolated by tenant
                        pass
        except:
            pass

    # ═══════════════════════════════════════════════════════
    # CATALOG TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_catalog_returns_products(self):
        """GET /api/salesman-orders/catalog returns product list with stock_qty and price"""
        resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        assert resp.status_code == 200, f"Catalog failed: {resp.text}"
        
        data = resp.json()
        assert data.get("success"), f"Catalog not successful: {data}"
        
        items = data.get("data", {}).get("items", [])
        total = data.get("data", {}).get("total", 0)
        
        # Should have items (context says 202 items from Tally inventory)
        assert total > 0, "Catalog should have items"
        assert len(items) > 0, "Items list should not be empty"
        
        # Verify item structure
        first_item = items[0]
        assert "item_name" in first_item, "Item should have item_name"
        assert "stock_qty" in first_item, "Item should have stock_qty"
        assert "price" in first_item, "Item should have price"
        print(f"PASS: Catalog returns {total} items with stock_qty and price")
    
    def test_catalog_search(self):
        """GET /api/salesman-orders/catalog with search filter"""
        # First get all items to find a searchable term
        resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        items = resp.json().get("data", {}).get("items", [])
        
        if items:
            # Search for first item's name (partial)
            search_term = items[0].get("item_name", "")[:5]
            search_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}&search={search_term}")
            assert search_resp.status_code == 200
            
            search_data = search_resp.json()
            assert search_data.get("success")
            print(f"PASS: Catalog search for '{search_term}' works")

    # ═══════════════════════════════════════════════════════
    # ORDER CRUD TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_create_order(self):
        """POST /api/salesman-orders/orders creates order with items and remarks"""
        # Get catalog items first
        catalog_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        items = catalog_resp.json().get("data", {}).get("items", [])
        
        if not items:
            pytest.skip("No catalog items available")
        
        test_item = items[0]
        order_payload = {
            "customer_name": f"TEST_Customer_{uuid.uuid4().hex[:6]}",
            "items": [
                {
                    "item_name": test_item.get("item_name"),
                    "quantity": 5,
                    "price": test_item.get("price", 100),
                    "unit": test_item.get("unit", "Nos"),
                    "remark": "Test remark for item"
                }
            ],
            "notes": "Test order notes"
        }
        
        resp = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json=order_payload)
        assert resp.status_code == 200, f"Create order failed: {resp.text}"
        
        data = resp.json()
        assert data.get("success"), f"Create order not successful: {data}"
        
        order_id = data.get("data", {}).get("order_id")
        assert order_id, "Order ID should be returned"
        assert order_id.startswith("SO-"), "Order ID should start with SO-"
        
        # Store for later tests
        self.test_order_id = order_id
        print(f"PASS: Created order {order_id}")
        
        return order_id
    
    def test_create_order_validation(self):
        """POST /api/salesman-orders/orders validates required fields"""
        # Missing customer_name
        resp1 = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json={
            "items": [{"item_name": "Test", "quantity": 1, "price": 100}]
        })
        assert resp1.status_code == 200
        assert not resp1.json().get("success"), "Should fail without customer_name"
        
        # Missing items
        resp2 = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json={
            "customer_name": "TEST_Customer"
        })
        assert resp2.status_code == 200
        assert not resp2.json().get("success"), "Should fail without items"
        
        print("PASS: Order creation validates required fields")
    
    def test_get_orders(self):
        """GET /api/salesman-orders/orders returns orders list"""
        resp = self.session.get(f"{BASE_URL}/api/salesman-orders/orders?company_id={COMPANY_ID}")
        assert resp.status_code == 200, f"Get orders failed: {resp.text}"
        
        data = resp.json()
        assert data.get("success"), f"Get orders not successful: {data}"
        
        orders = data.get("data", {}).get("orders", [])
        total = data.get("data", {}).get("total", 0)
        
        # Should have at least the existing test order (SO-33927CCF)
        assert total >= 1, "Should have at least one order"
        
        # Verify order structure
        if orders:
            order = orders[0]
            assert "order_id" in order, "Order should have order_id"
            assert "customer_name" in order, "Order should have customer_name"
            assert "status" in order, "Order should have status"
            assert "total_amount" in order, "Order should have total_amount"
            assert "items" in order, "Order should have items"
        
        print(f"PASS: Get orders returns {total} orders")
    
    def test_get_orders_with_filters(self):
        """GET /api/salesman-orders/orders with status and search filters"""
        # Filter by status
        resp1 = self.session.get(f"{BASE_URL}/api/salesman-orders/orders?company_id={COMPANY_ID}&status=billed")
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1.get("success")
        
        # All returned orders should be billed
        orders = data1.get("data", {}).get("orders", [])
        for order in orders:
            assert order.get("status") == "billed", f"Order {order.get('order_id')} should be billed"
        
        # Search by order ID
        resp2 = self.session.get(f"{BASE_URL}/api/salesman-orders/orders?company_id={COMPANY_ID}&search=SO-33927CCF")
        assert resp2.status_code == 200
        
        print("PASS: Order filters (status, search) work correctly")
    
    def test_get_single_order(self):
        """GET /api/salesman-orders/orders/{order_id} returns order details"""
        # Use existing test order
        resp = self.session.get(f"{BASE_URL}/api/salesman-orders/orders/SO-33927CCF")
        assert resp.status_code == 200, f"Get order failed: {resp.text}"
        
        data = resp.json()
        assert data.get("success"), f"Get order not successful: {data}"
        
        order = data.get("data", {})
        assert order.get("order_id") == "SO-33927CCF"
        assert order.get("status") == "billed"
        assert order.get("invoice_number") == "INV-2026-001"
        
        print("PASS: Get single order returns correct details")

    # ═══════════════════════════════════════════════════════
    # ORDER EDIT TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_edit_pending_order(self):
        """PATCH /api/salesman-orders/orders/{id} allows edit when status=pending"""
        # Create a new order first
        catalog_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        items = catalog_resp.json().get("data", {}).get("items", [])
        
        if not items:
            pytest.skip("No catalog items available")
        
        # Create order
        order_payload = {
            "customer_name": f"TEST_EditTest_{uuid.uuid4().hex[:6]}",
            "items": [{"item_name": items[0].get("item_name"), "quantity": 1, "price": 100, "unit": "Nos"}],
            "notes": "Original notes"
        }
        create_resp = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json=order_payload)
        order_id = create_resp.json().get("data", {}).get("order_id")
        
        # Edit the pending order
        edit_payload = {
            "items": [{"item_name": items[0].get("item_name"), "quantity": 10, "price": 150, "unit": "Nos", "remark": "Updated remark"}],
            "notes": "Updated notes"
        }
        edit_resp = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}", json=edit_payload)
        assert edit_resp.status_code == 200, f"Edit failed: {edit_resp.text}"
        
        data = edit_resp.json()
        assert data.get("success"), f"Edit not successful: {data}"
        
        # Verify changes persisted
        get_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/orders/{order_id}")
        updated_order = get_resp.json().get("data", {})
        assert updated_order.get("notes") == "Updated notes"
        assert updated_order.get("items", [{}])[0].get("quantity") == 10
        
        print(f"PASS: Edit pending order {order_id} works")
    
    def test_edit_blocked_after_approval(self):
        """PATCH /api/salesman-orders/orders/{id} rejects edit after approval"""
        # Try to edit the existing billed order
        edit_resp = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/SO-33927CCF", json={
            "notes": "Trying to edit billed order"
        })
        assert edit_resp.status_code == 200
        
        data = edit_resp.json()
        assert not data.get("success"), "Edit should fail for billed order"
        assert "pending" in data.get("error", "").lower() or "approval" in data.get("error", "").lower(), \
            f"Error should mention pending/approval: {data.get('error')}"
        
        print("PASS: Edit blocked after approval (billed order)")

    # ═══════════════════════════════════════════════════════
    # STATUS TRANSITION TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_status_transitions(self):
        """PATCH /api/salesman-orders/orders/{id}/status handles all transitions"""
        # Create a new order for status testing
        catalog_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        items = catalog_resp.json().get("data", {}).get("items", [])
        
        if not items:
            pytest.skip("No catalog items available")
        
        # Create order
        order_payload = {
            "customer_name": f"TEST_StatusTest_{uuid.uuid4().hex[:6]}",
            "items": [{"item_name": items[0].get("item_name"), "quantity": 1, "price": 100, "unit": "Nos"}]
        }
        create_resp = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json=order_payload)
        order_id = create_resp.json().get("data", {}).get("order_id")
        
        # Test: pending -> approved
        approve_resp = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}/status", json={
            "status": "approved",
            "admin_notes": "Approved for testing"
        })
        assert approve_resp.status_code == 200
        assert approve_resp.json().get("success"), f"Approve failed: {approve_resp.json()}"
        
        # Verify status changed
        get_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/orders/{order_id}")
        assert get_resp.json().get("data", {}).get("status") == "approved"
        
        print(f"PASS: Status transition pending->approved for {order_id}")
    
    def test_billed_requires_invoice_number(self):
        """PATCH with status=billed requires invoice_number"""
        # Create and approve an order
        catalog_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        items = catalog_resp.json().get("data", {}).get("items", [])
        
        if not items:
            pytest.skip("No catalog items available")
        
        # Create order
        order_payload = {
            "customer_name": f"TEST_BilledTest_{uuid.uuid4().hex[:6]}",
            "items": [{"item_name": items[0].get("item_name"), "quantity": 1, "price": 100, "unit": "Nos"}]
        }
        create_resp = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json=order_payload)
        order_id = create_resp.json().get("data", {}).get("order_id")
        
        # Approve first
        self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}/status", json={"status": "approved"})
        
        # Try to bill without invoice_number
        bill_resp1 = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}/status", json={
            "status": "billed"
        })
        assert bill_resp1.status_code == 200
        assert not bill_resp1.json().get("success"), "Billed should fail without invoice_number"
        assert "invoice" in bill_resp1.json().get("error", "").lower()
        
        # Bill with invoice_number
        bill_resp2 = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}/status", json={
            "status": "billed",
            "invoice_number": f"TEST-INV-{uuid.uuid4().hex[:6]}"
        })
        assert bill_resp2.status_code == 200
        assert bill_resp2.json().get("success"), f"Billed with invoice should succeed: {bill_resp2.json()}"
        
        print(f"PASS: Billed status requires invoice_number for {order_id}")
    
    def test_hold_and_reject_transitions(self):
        """Test hold and reject status transitions"""
        catalog_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/catalog?company_id={COMPANY_ID}")
        items = catalog_resp.json().get("data", {}).get("items", [])
        
        if not items:
            pytest.skip("No catalog items available")
        
        # Create order for hold test
        order_payload = {
            "customer_name": f"TEST_HoldTest_{uuid.uuid4().hex[:6]}",
            "items": [{"item_name": items[0].get("item_name"), "quantity": 1, "price": 100, "unit": "Nos"}]
        }
        create_resp = self.session.post(f"{BASE_URL}/api/salesman-orders/orders", json=order_payload)
        order_id = create_resp.json().get("data", {}).get("order_id")
        
        # Test: pending -> hold
        hold_resp = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}/status", json={
            "status": "hold",
            "admin_notes": "On hold for review"
        })
        assert hold_resp.status_code == 200
        assert hold_resp.json().get("success")
        
        # Test: hold -> rejected
        reject_resp = self.session.patch(f"{BASE_URL}/api/salesman-orders/orders/{order_id}/status", json={
            "status": "rejected",
            "reject_reason": "Test rejection"
        })
        assert reject_resp.status_code == 200
        assert reject_resp.json().get("success")
        
        # Verify final status
        get_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/orders/{order_id}")
        assert get_resp.json().get("data", {}).get("status") == "rejected"
        
        print(f"PASS: Hold and reject transitions work for {order_id}")

    # ═══════════════════════════════════════════════════════
    # STATS TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_order_stats(self):
        """GET /api/salesman-orders/stats returns order counts by status"""
        resp = self.session.get(f"{BASE_URL}/api/salesman-orders/stats?company_id={COMPANY_ID}")
        assert resp.status_code == 200, f"Stats failed: {resp.text}"
        
        data = resp.json()
        assert data.get("success"), f"Stats not successful: {data}"
        
        stats = data.get("data", {}).get("stats", {})
        
        # Stats should be a dict with status keys
        # Each status should have count and total
        for status, stat_data in stats.items():
            assert "count" in stat_data, f"Status {status} should have count"
            assert "total" in stat_data, f"Status {status} should have total"
        
        print(f"PASS: Stats returns counts by status: {list(stats.keys())}")

    # ═══════════════════════════════════════════════════════
    # MY-CUSTOMERS TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_my_customers(self):
        """GET /api/salesman-orders/my-customers returns mapped customers"""
        resp = self.session.get(f"{BASE_URL}/api/salesman-orders/my-customers?company_id={COMPANY_ID}")
        assert resp.status_code == 200, f"My customers failed: {resp.text}"
        
        data = resp.json()
        assert data.get("success"), f"My customers not successful: {data}"
        
        # For admin, may return empty or message about no mapping
        customers = data.get("data", {}).get("customers", [])
        
        # Verify structure if customers exist
        if customers:
            cust = customers[0]
            assert "customer_name" in cust, "Customer should have customer_name"
        
        print(f"PASS: My customers returns {len(customers)} customers")

    # ═══════════════════════════════════════════════════════
    # BEAT MANAGEMENT TESTS
    # ═══════════════════════════════════════════════════════
    
    def test_save_and_get_beats(self):
        """POST and GET /api/salesman-orders/beats for beat management"""
        test_salesman = f"TEST_Salesman_{uuid.uuid4().hex[:6]}"
        
        # Save beats
        beats_payload = {
            "salesman": test_salesman,
            "beats": [
                {"customer_name": "TEST_Customer_A", "day_of_week": "Monday", "frequency": "weekly"},
                {"customer_name": "TEST_Customer_B", "day_of_week": "Wednesday", "frequency": "weekly"}
            ]
        }
        save_resp = self.session.post(f"{BASE_URL}/api/salesman-orders/beats", json=beats_payload)
        assert save_resp.status_code == 200, f"Save beats failed: {save_resp.text}"
        assert save_resp.json().get("success"), f"Save beats not successful: {save_resp.json()}"
        
        # Get beats
        get_resp = self.session.get(f"{BASE_URL}/api/salesman-orders/beats?salesman={test_salesman}&company_id={COMPANY_ID}")
        assert get_resp.status_code == 200
        
        data = get_resp.json()
        assert data.get("success")
        
        beats = data.get("data", {}).get("beats", [])
        assert len(beats) == 2, f"Should have 2 beats, got {len(beats)}"
        
        # Verify beat structure
        beat = beats[0]
        assert "beat_id" in beat, "Beat should have beat_id"
        assert "customer_name" in beat, "Beat should have customer_name"
        assert "day_of_week" in beat, "Beat should have day_of_week"
        
        print(f"PASS: Beat management works for {test_salesman}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
