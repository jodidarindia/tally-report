"""
Backend API Tests for Tally SaaS Report Builder
Tests: Auth, Inventory, Sales, CRM, Analytics, Salesman, AI Purchase Order
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com')

class TestAuthEndpoints:
    """Authentication endpoint tests - OTP based login"""
    
    def test_send_otp_success(self):
        """Test sending OTP to valid email"""
        response = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["email"] == "test@example.com"
        assert data["data"]["dev_mode"] == True  # Dev mode uses static OTP
        print("✓ Send OTP endpoint working")
    
    def test_verify_otp_success(self):
        """Test verifying OTP with correct code"""
        # First send OTP
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"email": "test@example.com"}
        )
        
        # Verify with dev mode OTP
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"email": "test@example.com", "otp": "123456"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "session_token" in data["data"]
        assert data["data"]["email"] == "test@example.com"
        print("✓ Verify OTP endpoint working")
    
    def test_verify_otp_invalid(self):
        """Test verifying OTP with wrong code"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"email": "test@example.com", "otp": "000000"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Invalid OTP" in data.get("error", "")
        print("✓ Invalid OTP rejection working")
    
    def test_verify_session(self):
        """Test session verification"""
        # Get a valid session token
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"email": "test@example.com"}
        )
        verify_res = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"email": "test@example.com", "otp": "123456"}
        )
        token = verify_res.json()["data"]["session_token"]
        
        # Verify session
        response = requests.post(f"{BASE_URL}/api/auth/verify-session?session_token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["valid"] == True
        print("✓ Session verification working")
    
    def test_logout(self):
        """Test logout endpoint"""
        # Get a valid session token
        requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"email": "test@example.com"}
        )
        verify_res = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"email": "test@example.com", "otp": "123456"}
        )
        token = verify_res.json()["data"]["session_token"]
        
        # Logout
        response = requests.post(f"{BASE_URL}/api/auth/logout?session_token={token}")
        assert response.status_code == 200
        print("✓ Logout endpoint working")


class TestInventoryEndpoints:
    """Inventory management endpoint tests"""
    
    def test_get_inventory_items(self):
        """Test fetching inventory items"""
        response = requests.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "items" in data["data"]
        assert "count" in data["data"]
        
        # Verify item structure
        if data["data"]["items"]:
            item = data["data"]["items"][0]
            assert "item_id" in item
            assert "item_name" in item
            assert "quantity" in item
            assert "price" in item
        print(f"✓ Inventory items endpoint working - {data['data']['count']} items")
    
    def test_get_inventory_summary(self):
        """Test inventory summary statistics"""
        response = requests.get(f"{BASE_URL}/api/inventory/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "total_items" in data["data"]
        assert "total_value" in data["data"]
        assert "low_stock_items" in data["data"]
        print("✓ Inventory summary endpoint working")
    
    def test_get_inventory_movement(self):
        """Test inventory movement analysis"""
        response = requests.get(f"{BASE_URL}/api/inventory/movement-analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "movements" in data["data"]
        assert "summary" in data["data"]
        print("✓ Inventory movement analysis working")
    
    def test_get_below_cost_sales(self):
        """Test below cost sales detection"""
        response = requests.get(f"{BASE_URL}/api/inventory/below-cost-sales")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "below_cost_sales" in data["data"]
        print("✓ Below cost sales endpoint working")
    
    def test_get_pivot_data(self):
        """Test pivot table data"""
        response = requests.get(f"{BASE_URL}/api/inventory/pivot-data?group_by=category&metric=value")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "pivot_table" in data["data"]
        print("✓ Pivot table endpoint working")
    
    def test_get_sales_frequency(self):
        """Test sales frequency report"""
        response = requests.get(f"{BASE_URL}/api/inventory/sales-frequency")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "sales_frequency" in data["data"]
        
        # Verify structure
        if data["data"]["sales_frequency"]:
            item = data["data"]["sales_frequency"][0]
            assert "item_name" in item
            assert "transaction_count" in item
            assert "unique_customers" in item
        print("✓ Sales frequency endpoint working")


class TestSalesEndpoints:
    """Sales voucher endpoint tests"""
    
    def test_get_sales_vouchers(self):
        """Test fetching sales vouchers"""
        response = requests.get(f"{BASE_URL}/api/sales/vouchers")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "vouchers" in data["data"]
        assert "count" in data["data"]
        
        # Verify voucher structure
        if data["data"]["vouchers"]:
            voucher = data["data"]["vouchers"][0]
            assert "voucher_id" in voucher
            assert "party_name" in voucher
            assert "total_amount" in voucher
        print(f"✓ Sales vouchers endpoint working - {data['data']['count']} vouchers")
    
    def test_get_sales_summary(self):
        """Test sales summary statistics"""
        response = requests.get(f"{BASE_URL}/api/sales/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "total_vouchers" in data["data"]
        assert "total_sales" in data["data"]
        print("✓ Sales summary endpoint working")
    
    def test_get_sales_analytics(self):
        """Test sales analytics data"""
        response = requests.get(f"{BASE_URL}/api/sales/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "daily_sales" in data["data"]
        print("✓ Sales analytics endpoint working")


class TestCRMEndpoints:
    """Customer CRM endpoint tests"""
    
    def test_get_customer_outstanding(self):
        """Test customer outstanding payments"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "customers" in data["data"]
        assert "total_outstanding" in data["data"]
        
        # Verify customer structure
        if data["data"]["customers"]:
            customer = data["data"]["customers"][0]
            assert "customer_name" in customer
            assert "outstanding_amount" in customer
            assert "aging_30_days" in customer
        print("✓ Customer outstanding endpoint working")
    
    def test_get_customer_targets(self):
        """Test customer targets and achievement"""
        response = requests.get(f"{BASE_URL}/api/customers/targets")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "targets" in data["data"]
        print("✓ Customer targets endpoint working")
    
    def test_get_payment_behavior(self):
        """Test customer payment behavior analysis"""
        response = requests.get(f"{BASE_URL}/api/customers/payment-behavior")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "customers" in data["data"]
        print("✓ Payment behavior endpoint working")
    
    def test_get_followups(self):
        """Test customer follow-ups"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "followups" in data["data"]
        print("✓ Customer followups endpoint working")


class TestSalesmanEndpoints:
    """Salesman performance endpoint tests"""
    
    def test_get_salesman_performance(self):
        """Test salesman performance data"""
        response = requests.get(f"{BASE_URL}/api/salesman/performance")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "salesman" in data["data"]
        
        # Verify structure
        if data["data"]["salesman"]:
            person = data["data"]["salesman"][0]
            assert "salesman_name" in person
            assert "achieved_amount" in person
            assert "achievement_percentage" in person
        print("✓ Salesman performance endpoint working")


class TestAIPurchaseOrderEndpoint:
    """AI Purchase Order generation tests"""
    
    def test_generate_purchase_order(self):
        """Test AI-powered purchase order generation"""
        response = requests.post(f"{BASE_URL}/api/inventory/generate-purchase-order")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "analysis" in data["data"]
        assert "recommendations" in data["data"]
        print("✓ AI Purchase Order generation working")
    
    def test_get_purchase_orders(self):
        """Test fetching purchase orders"""
        response = requests.get(f"{BASE_URL}/api/inventory/purchase-orders")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "purchase_orders" in data["data"]
        print("✓ Purchase orders list endpoint working")


class TestTallyEndpoints:
    """Tally connection endpoint tests"""
    
    def test_get_tally_status(self):
        """Test Tally connection status"""
        response = requests.get(f"{BASE_URL}/api/tally/status")
        assert response.status_code == 200
        data = response.json()
        # Status can be connected or disconnected
        assert "is_connected" in data["data"]
        print("✓ Tally status endpoint working")
    
    def test_get_sync_status(self):
        """Test sync status from desktop agent"""
        response = requests.get(f"{BASE_URL}/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ Sync status endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
