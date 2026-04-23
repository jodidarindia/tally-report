"""
Iteration 50: Dispatch Terminal Feature Tests
Tests for Kanban board, porter management, card lifecycle, document uploads, and admin dashboard APIs.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"

# Test data prefixes for cleanup
TEST_PREFIX = "TEST_DISPATCH_"


class TestDispatchAuth:
    """Authentication for dispatch tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
            "captcha_token": ""
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data.get("success"), f"Login not successful: {data}"
        token = data.get("data", {}).get("token") or data.get("token")
        assert token, f"No token in response: {data}"
        return token
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with auth token and company ID"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "X-Company-Id": COMPANY_ID,
            "Content-Type": "application/json"
        }


class TestDispatchCards(TestDispatchAuth):
    """Dispatch cards CRUD and lifecycle tests"""
    
    def test_get_dispatch_cards_active(self, headers):
        """GET /api/dispatch/cards?status=active - returns dispatch cards list"""
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?status=active&company_id={COMPANY_ID}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "cards" in data.get("data", {}), "Missing cards in response"
        assert "total" in data.get("data", {}), "Missing total count"
        cards = data["data"]["cards"]
        assert isinstance(cards, list), "Cards should be a list"
        print(f"Found {len(cards)} active dispatch cards, total: {data['data']['total']}")
    
    def test_get_dispatch_cards_with_search(self, headers):
        """GET /api/dispatch/cards with search parameter"""
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?search=MAN&company_id={COMPANY_ID}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        print(f"Search 'MAN' returned {len(data['data'].get('cards', []))} cards")
    
    def test_create_manual_dispatch_card(self, headers):
        """POST /api/dispatch/cards - creates manual dispatch card"""
        unique_id = uuid.uuid4().hex[:6].upper()
        payload = {
            "reason": "sample",
            "party_name": f"{TEST_PREFIX}Party_{unique_id}",
            "destination_city": "Mumbai",
            "notes": "Test manual card creation"
        }
        response = requests.post(f"{BASE_URL}/api/dispatch/cards", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Create failed: {data}"
        assert "card_id" in data.get("data", {}), "Missing card_id in response"
        card_id = data["data"]["card_id"]
        assert card_id.startswith("MAN-"), f"Manual card should start with MAN-: {card_id}"
        print(f"Created manual card: {card_id}")
        
        # Verify card was created by fetching it
        get_response = requests.get(f"{BASE_URL}/api/dispatch/cards/{card_id}", headers=headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("success"), f"Get card failed: {get_data}"
        assert get_data["data"]["party_name"] == payload["party_name"]
        assert get_data["data"]["card_type"] == "manual"
        assert get_data["data"]["manual_reason"] == "sample"
        return card_id
    
    def test_create_manual_card_invalid_reason(self, headers):
        """POST /api/dispatch/cards with invalid reason should fail"""
        payload = {
            "reason": "invalid_reason",
            "party_name": "Test Party"
        }
        response = requests.post(f"{BASE_URL}/api/dispatch/cards", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert not data.get("success"), "Should fail with invalid reason"
        assert "Invalid reason" in data.get("error", "")
    
    def test_update_card_fields(self, headers):
        """PATCH /api/dispatch/cards/{card_id} - updates card fields"""
        # First create a card
        create_response = requests.post(f"{BASE_URL}/api/dispatch/cards", json={
            "reason": "other",
            "party_name": f"{TEST_PREFIX}Update_Test_{uuid.uuid4().hex[:4]}"
        }, headers=headers)
        card_id = create_response.json()["data"]["card_id"]
        
        # Update fields
        update_payload = {
            "total_boxes": 5,
            "transport_name": "Blue Dart",
            "transport_charges": 250.50,
            "porter_name": "Raju Porter",
            "porter_charges": 100,
            "lr_number": "LR-TEST-12345",
            "destination_city": "Delhi",
            "notes": "Updated notes"
        }
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}", json=update_payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Update failed: {data}"
        
        # Verify updates persisted
        get_response = requests.get(f"{BASE_URL}/api/dispatch/cards/{card_id}", headers=headers)
        get_data = get_response.json()["data"]
        assert get_data["total_boxes"] == 5
        assert get_data["transport_name"] == "Blue Dart"
        assert get_data["lr_number"] == "LR-TEST-12345"
        print(f"Card {card_id} updated successfully with LR: {get_data['lr_number']}")
    
    def test_card_status_transition(self, headers):
        """PATCH /api/dispatch/cards/{card_id}/status - transitions card status"""
        # Create a card
        create_response = requests.post(f"{BASE_URL}/api/dispatch/cards", json={
            "reason": "sample",
            "party_name": f"{TEST_PREFIX}Status_Test_{uuid.uuid4().hex[:4]}"
        }, headers=headers)
        card_id = create_response.json()["data"]["card_id"]
        
        # Get initial status
        get_response = requests.get(f"{BASE_URL}/api/dispatch/cards/{card_id}", headers=headers)
        initial_status = get_response.json()["data"]["status"]
        print(f"Card {card_id} initial status: {initial_status}")
        
        # Transition to processing
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
                                  json={"status": "processing"}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Status transition failed: {data}"
        
        # Verify status changed
        get_response = requests.get(f"{BASE_URL}/api/dispatch/cards/{card_id}", headers=headers)
        new_status = get_response.json()["data"]["status"]
        assert new_status == "processing", f"Expected processing, got {new_status}"
        print(f"Card {card_id} transitioned to: {new_status}")
    
    def test_card_status_packed_requires_physical_check(self, headers):
        """PATCH status to packed should require physical_check"""
        # Create a card
        create_response = requests.post(f"{BASE_URL}/api/dispatch/cards", json={
            "reason": "sample",
            "party_name": f"{TEST_PREFIX}PhysCheck_Test_{uuid.uuid4().hex[:4]}"
        }, headers=headers)
        card_id = create_response.json()["data"]["card_id"]
        
        # Try to move to packed without physical check
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
                                  json={"status": "packed"}, headers=headers)
        data = response.json()
        assert not data.get("success"), "Should fail without physical check"
        assert "physical" in data.get("error", "").lower()
        
        # Set physical check and try again
        requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}", 
                       json={"physical_check": True}, headers=headers)
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
                                  json={"status": "packed"}, headers=headers)
        assert response.json().get("success"), "Should succeed with physical check"
        print(f"Card {card_id} moved to packed after physical check")
    
    def test_card_hold_status(self, headers):
        """Test putting card on hold with reason"""
        # Create a card
        create_response = requests.post(f"{BASE_URL}/api/dispatch/cards", json={
            "reason": "sample",
            "party_name": f"{TEST_PREFIX}Hold_Test_{uuid.uuid4().hex[:4]}"
        }, headers=headers)
        card_id = create_response.json()["data"]["card_id"]
        
        # Put on hold
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
                                  json={"status": "hold", "hold_reason": "Waiting for payment"}, headers=headers)
        assert response.status_code == 200
        assert response.json().get("success")
        
        # Verify hold status and reason in history
        get_response = requests.get(f"{BASE_URL}/api/dispatch/cards/{card_id}", headers=headers)
        card_data = get_response.json()["data"]
        assert card_data["status"] == "hold"
        hold_entry = [h for h in card_data["status_history"] if h.get("status") == "hold"]
        assert len(hold_entry) > 0
        assert hold_entry[-1].get("reason") == "Waiting for payment"
        print(f"Card {card_id} on hold with reason: {hold_entry[-1].get('reason')}")
    
    def test_invalid_status_transition(self, headers):
        """Test invalid status value"""
        # Create a card
        create_response = requests.post(f"{BASE_URL}/api/dispatch/cards", json={
            "reason": "sample",
            "party_name": f"{TEST_PREFIX}Invalid_Status_{uuid.uuid4().hex[:4]}"
        }, headers=headers)
        card_id = create_response.json()["data"]["card_id"]
        
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
                                  json={"status": "invalid_status"}, headers=headers)
        data = response.json()
        assert not data.get("success"), "Should fail with invalid status"
        assert "Invalid status" in data.get("error", "")


class TestAutoCreate(TestDispatchAuth):
    """Auto-create cards from sales invoices"""
    
    def test_auto_create_from_invoices(self, headers):
        """POST /api/dispatch/auto-create - creates cards from sales invoices"""
        response = requests.post(f"{BASE_URL}/api/dispatch/auto-create", json={}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Auto-create failed: {data}"
        assert "created" in data.get("data", {}), "Missing created count"
        print(f"Auto-create result: {data.get('message')} - Created: {data['data']['created']}")


class TestPorterManagement(TestDispatchAuth):
    """Porter CRUD and settlement tests"""
    
    def test_get_porters(self, headers):
        """GET /api/dispatch/porters - list porters"""
        response = requests.get(f"{BASE_URL}/api/dispatch/porters", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "porters" in data.get("data", {}), "Missing porters in response"
        porters = data["data"]["porters"]
        print(f"Found {len(porters)} porters")
        if porters:
            print(f"First porter: {porters[0].get('name')}")
    
    def test_create_porter(self, headers):
        """POST /api/dispatch/porters - create porter"""
        unique_id = uuid.uuid4().hex[:4]
        payload = {
            "name": f"{TEST_PREFIX}Porter_{unique_id}",
            "phone": "9876543210"
        }
        response = requests.post(f"{BASE_URL}/api/dispatch/porters", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Create porter failed: {data}"
        assert "porter_id" in data.get("data", {}), "Missing porter_id"
        porter_id = data["data"]["porter_id"]
        assert porter_id.startswith("PRT-"), f"Porter ID should start with PRT-: {porter_id}"
        print(f"Created porter: {porter_id} - {payload['name']}")
        return porter_id
    
    def test_create_porter_without_name_fails(self, headers):
        """POST /api/dispatch/porters without name should fail"""
        response = requests.post(f"{BASE_URL}/api/dispatch/porters", json={"phone": "1234567890"}, headers=headers)
        data = response.json()
        assert not data.get("success"), "Should fail without name"
        assert "name required" in data.get("error", "").lower()
    
    def test_update_porter(self, headers):
        """PATCH /api/dispatch/porters/{porter_id} - update porter"""
        # Create a porter first
        create_response = requests.post(f"{BASE_URL}/api/dispatch/porters", json={
            "name": f"{TEST_PREFIX}UpdatePorter_{uuid.uuid4().hex[:4]}",
            "phone": "1111111111"
        }, headers=headers)
        porter_id = create_response.json()["data"]["porter_id"]
        
        # Update porter
        response = requests.patch(f"{BASE_URL}/api/dispatch/porters/{porter_id}", 
                                  json={"phone": "2222222222", "is_active": False}, headers=headers)
        assert response.status_code == 200
        assert response.json().get("success")
        print(f"Porter {porter_id} updated")
    
    def test_porter_settlement(self, headers):
        """GET /api/dispatch/porter-settlement - porter settlement summary"""
        response = requests.get(f"{BASE_URL}/api/dispatch/porter-settlement", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "settlement" in data.get("data", {}), "Missing settlement in response"
        settlement = data["data"]["settlement"]
        print(f"Porter settlement entries: {len(settlement)}")
        if settlement:
            s = settlement[0]
            print(f"First porter: {s.get('name')} - Charges: {s.get('total_charges')}, Paid: {s.get('total_paid')}, Due: {s.get('balance_due')}")
    
    def test_record_porter_payment(self, headers):
        """POST /api/dispatch/porter-payment - record porter payment"""
        # Get existing porter or create one
        porters_response = requests.get(f"{BASE_URL}/api/dispatch/porters", headers=headers)
        porters = porters_response.json()["data"]["porters"]
        
        if porters:
            porter_name = porters[0]["name"]
        else:
            # Create a porter
            create_response = requests.post(f"{BASE_URL}/api/dispatch/porters", json={
                "name": f"{TEST_PREFIX}PaymentPorter_{uuid.uuid4().hex[:4]}"
            }, headers=headers)
            porter_name = f"{TEST_PREFIX}PaymentPorter_{uuid.uuid4().hex[:4]}"
        
        payload = {
            "porter_name": porter_name,
            "amount": 500.00,
            "payment_ref": "UPI-TEST-123",
            "notes": "Test payment"
        }
        response = requests.post(f"{BASE_URL}/api/dispatch/porter-payment", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Payment recording failed: {data}"
        print(f"Recorded payment of Rs.{payload['amount']} to {porter_name}")


class TestDispatchEmployees(TestDispatchAuth):
    """Dispatch employees tests"""
    
    def test_get_dispatch_employees(self, headers):
        """GET /api/dispatch/employees - list dispatch employees"""
        response = requests.get(f"{BASE_URL}/api/dispatch/employees", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "employees" in data.get("data", {}), "Missing employees in response"
        employees = data["data"]["employees"]
        print(f"Found {len(employees)} dispatch employees")
        for emp in employees[:3]:
            print(f"  - {emp.get('username')} ({emp.get('name', 'N/A')})")


class TestDispatchSummary(TestDispatchAuth):
    """Dispatch summary and history tests"""
    
    def test_get_dispatch_summary(self, headers):
        """GET /api/dispatch/summary - daily dispatch summary"""
        response = requests.get(f"{BASE_URL}/api/dispatch/summary?company_id={COMPANY_ID}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        summary = data.get("data", {})
        assert "dispatched_count" in summary, "Missing dispatched_count"
        assert "pending_count" in summary, "Missing pending_count"
        assert "hold_count" in summary, "Missing hold_count"
        print(f"Summary - Dispatched: {summary['dispatched_count']}, Pending: {summary['pending_count']}, Hold: {summary['hold_count']}")
        print(f"Total boxes: {summary.get('total_boxes')}, Transport charges: {summary.get('total_transport_charges')}")
    
    def test_get_dispatch_history(self, headers):
        """GET /api/dispatch/history - searchable dispatch archive"""
        response = requests.get(f"{BASE_URL}/api/dispatch/history?company_id={COMPANY_ID}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        assert "cards" in data.get("data", {}), "Missing cards in response"
        assert "total" in data.get("data", {}), "Missing total count"
        assert "total_pages" in data.get("data", {}), "Missing total_pages"
        print(f"History - Total: {data['data']['total']}, Page: {data['data']['page']}, Total Pages: {data['data']['total_pages']}")
    
    def test_dispatch_history_search(self, headers):
        """GET /api/dispatch/history with search"""
        response = requests.get(f"{BASE_URL}/api/dispatch/history?search=MAN&company_id={COMPANY_ID}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"API failed: {data}"
        print(f"History search 'MAN' returned {data['data']['total']} results")


class TestDispatchRoleInAuth(TestDispatchAuth):
    """Test dispatch role in user creation"""
    
    def test_dispatch_role_available_in_user_creation(self, headers):
        """Verify dispatch role can be used when creating users"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "username": f"test_dispatch_{unique_id}@test.com",
            "password": "TestPass123!",
            "name": f"Test Dispatch User {unique_id}",
            "role": "dispatch"
        }
        response = requests.post(f"{BASE_URL}/api/auth/users", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        # May fail due to employee limit, but should not fail due to invalid role
        if not data.get("success"):
            # Check it's not a role error
            error = data.get("error", "")
            assert "role" not in error.lower() or "dispatch" not in error.lower(), f"Dispatch role should be valid: {error}"
            print(f"User creation failed (expected if limit reached): {error}")
        else:
            assert data["data"]["role"] == "dispatch", f"Role should be dispatch: {data}"
            print(f"Created dispatch user: {payload['username']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
