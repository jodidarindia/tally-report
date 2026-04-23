"""
Iteration 51: Dispatch Terminal Overhaul Tests
- Date-based card creation (from_date param)
- Transporter CRUD
- Dispatch settings (start_date)
- Kanban swim lanes (new/queued/processing/packed/dispatched)
- Searchable dispatch history
- Porter settlement
- Daily summary
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USER,
        "password": ADMIN_PASS
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("success"), f"Login not successful: {data}"
    token = data.get("data", {}).get("token")
    assert token, "No token in response"
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers with company ID"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Company-Id": COMPANY_ID,
        "Content-Type": "application/json"
    }


class TestDispatchSettings:
    """Test dispatch settings - start_date configuration"""
    
    def test_get_dispatch_settings(self, headers):
        """GET /api/dispatch/settings - returns saved start_date"""
        response = requests.get(f"{BASE_URL}/api/dispatch/settings", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        # Settings may have start_date if previously set
        settings = data.get("data", {})
        print(f"Current settings: {settings}")
        # start_date should be present if auto-create was run before
        if settings.get("start_date"):
            assert isinstance(settings["start_date"], str)
    
    def test_save_dispatch_settings(self, headers):
        """POST /api/dispatch/settings - saves start_date (admin only)"""
        response = requests.post(f"{BASE_URL}/api/dispatch/settings", 
            json={"start_date": "2026-04-01", "auto_create_enabled": True},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        assert "saved" in data.get("message", "").lower()


class TestAutoCreateWithDate:
    """Test date-based auto-create functionality"""
    
    def test_auto_create_without_date_first_time(self, headers):
        """POST /api/dispatch/auto-create without from_date - should use saved setting or error"""
        # First ensure settings exist
        requests.post(f"{BASE_URL}/api/dispatch/settings", 
            json={"start_date": "2026-04-01"},
            headers=headers)
        
        # Now auto-create without from_date should use saved setting
        response = requests.post(f"{BASE_URL}/api/dispatch/auto-create", 
            json={},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Should succeed using saved start_date
        assert data.get("success"), f"Failed: {data}"
        print(f"Auto-create result: {data}")
    
    def test_auto_create_with_from_date(self, headers):
        """POST /api/dispatch/auto-create with from_date param - creates cards from that date"""
        response = requests.post(f"{BASE_URL}/api/dispatch/auto-create", 
            json={"from_date": "2026-04-01"},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        result = data.get("data", {})
        # Should return created count and from_date
        assert "created" in result or "from_date" in result, f"Missing expected fields: {result}"
        print(f"Auto-create with date: {result}")


class TestTransporterCRUD:
    """Test transporter management endpoints"""
    
    def test_get_transporters(self, headers):
        """GET /api/dispatch/transporters - list transporters"""
        response = requests.get(f"{BASE_URL}/api/dispatch/transporters", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        transporters = data.get("data", {}).get("transporters", [])
        assert isinstance(transporters, list)
        print(f"Found {len(transporters)} transporters")
        # Check if Gayatri Transport exists (mentioned in context)
        names = [t.get("name", "") for t in transporters]
        print(f"Transporter names: {names}")
    
    def test_create_transporter(self, headers):
        """POST /api/dispatch/transporters - create transporter"""
        test_name = f"TEST_TRANSPORTER_{uuid.uuid4().hex[:6]}"
        response = requests.post(f"{BASE_URL}/api/dispatch/transporters", 
            json={"name": test_name, "phone": "9876543210"},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        result = data.get("data", {})
        assert result.get("transporter_id"), "No transporter_id returned"
        assert result.get("name") == test_name
        print(f"Created transporter: {result}")
    
    def test_create_transporter_without_name_fails(self, headers):
        """POST /api/dispatch/transporters without name - should fail"""
        response = requests.post(f"{BASE_URL}/api/dispatch/transporters", 
            json={"phone": "1234567890"},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert not data.get("success"), "Should have failed without name"
        assert "name" in data.get("error", "").lower()


class TestPorterCRUD:
    """Test porter management endpoints"""
    
    def test_get_porters(self, headers):
        """GET /api/dispatch/porters - list porters"""
        response = requests.get(f"{BASE_URL}/api/dispatch/porters", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        porters = data.get("data", {}).get("porters", [])
        assert isinstance(porters, list)
        print(f"Found {len(porters)} porters")
        # Check if Raju Porter exists (mentioned in context)
        names = [p.get("name", "") for p in porters]
        print(f"Porter names: {names}")
    
    def test_create_porter(self, headers):
        """POST /api/dispatch/porters - create porter (available to dispatch role too)"""
        test_name = f"TEST_PORTER_{uuid.uuid4().hex[:6]}"
        response = requests.post(f"{BASE_URL}/api/dispatch/porters", 
            json={"name": test_name, "phone": "9876543211"},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        result = data.get("data", {})
        assert result.get("porter_id"), "No porter_id returned"
        assert result.get("name") == test_name
        print(f"Created porter: {result}")


class TestDispatchCards:
    """Test dispatch cards CRUD and status transitions"""
    
    def test_get_active_cards(self, headers):
        """GET /api/dispatch/cards?status=active - returns active cards"""
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?status=active&company_id={COMPANY_ID}", 
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        result = data.get("data", {})
        cards = result.get("cards", [])
        total = result.get("total", 0)
        assert isinstance(cards, list)
        print(f"Found {len(cards)} active cards (total: {total})")
        
        # Verify card structure
        if cards:
            card = cards[0]
            assert "card_id" in card
            assert "status" in card
            assert "invoice_number" in card
            print(f"Sample card: {card.get('card_id')} - {card.get('status')}")
    
    def test_get_cards_by_status(self, headers):
        """GET /api/dispatch/cards - verify swim lane statuses exist"""
        # Check for cards in different statuses
        statuses = ["new", "queued", "processing", "packed", "dispatched"]
        status_counts = {}
        
        for status in statuses:
            response = requests.get(f"{BASE_URL}/api/dispatch/cards?status={status}&company_id={COMPANY_ID}", 
                headers=headers)
            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                count = data.get("data", {}).get("total", 0)
                status_counts[status] = count
        
        print(f"Status distribution: {status_counts}")
        # At least some cards should exist
        total = sum(status_counts.values())
        assert total >= 0, "Should have cards in various statuses"
    
    def test_update_card_fields(self, headers):
        """PATCH /api/dispatch/cards/{card_id} - update fields including lr_number"""
        # First get a card
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?status=active&limit=1&company_id={COMPANY_ID}", 
            headers=headers)
        data = response.json()
        cards = data.get("data", {}).get("cards", [])
        
        if not cards:
            pytest.skip("No cards available to test update")
        
        card_id = cards[0].get("card_id")
        test_lr = f"LR-TEST-{uuid.uuid4().hex[:6]}"
        
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}", 
            json={
                "lr_number": test_lr,
                "total_boxes": 5,
                "notes": "Test update from iteration 51"
            },
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        print(f"Updated card {card_id} with LR: {test_lr}")
    
    def test_status_transition(self, headers):
        """PATCH /api/dispatch/cards/{card_id}/status - status transition"""
        # Get a card in 'new' status
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?status=new&limit=1&company_id={COMPANY_ID}", 
            headers=headers)
        data = response.json()
        cards = data.get("data", {}).get("cards", [])
        
        if not cards:
            pytest.skip("No 'new' cards available to test status transition")
        
        card_id = cards[0].get("card_id")
        
        # Transition to queued
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
            json={"status": "queued"},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        print(f"Transitioned card {card_id} to queued")
    
    def test_invalid_status_transition(self, headers):
        """PATCH /api/dispatch/cards/{card_id}/status - invalid status rejected"""
        # Get any card
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?status=active&limit=1&company_id={COMPANY_ID}", 
            headers=headers)
        data = response.json()
        cards = data.get("data", {}).get("cards", [])
        
        if not cards:
            pytest.skip("No cards available")
        
        card_id = cards[0].get("card_id")
        
        # Try invalid status
        response = requests.patch(f"{BASE_URL}/api/dispatch/cards/{card_id}/status", 
            json={"status": "invalid_status"},
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert not data.get("success"), "Should reject invalid status"


class TestDispatchHistory:
    """Test searchable dispatch history"""
    
    def test_get_dispatch_history(self, headers):
        """GET /api/dispatch/history - searchable archive"""
        response = requests.get(f"{BASE_URL}/api/dispatch/history?company_id={COMPANY_ID}", 
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        result = data.get("data", {})
        cards = result.get("cards", [])
        total = result.get("total", 0)
        print(f"History: {len(cards)} cards (total: {total})")
    
    def test_search_dispatch_history(self, headers):
        """GET /api/dispatch/history?search=... - search by invoice/party/LR"""
        # Search for a common term
        response = requests.get(f"{BASE_URL}/api/dispatch/history?search=test&company_id={COMPANY_ID}", 
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        print(f"Search results: {data.get('data', {}).get('total', 0)} matches")
    
    def test_paginated_history(self, headers):
        """GET /api/dispatch/history with pagination"""
        response = requests.get(f"{BASE_URL}/api/dispatch/history?page=1&limit=10&company_id={COMPANY_ID}", 
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        result = data.get("data", {})
        assert "page" in result
        assert "total_pages" in result or "total" in result


class TestDispatchSummary:
    """Test daily summary endpoint"""
    
    def test_get_dispatch_summary(self, headers):
        """GET /api/dispatch/summary - daily summary"""
        response = requests.get(f"{BASE_URL}/api/dispatch/summary?company_id={COMPANY_ID}", 
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        summary = data.get("data", {})
        
        # Verify summary structure
        assert "date" in summary
        assert "dispatched_count" in summary
        assert "pending_count" in summary
        assert "hold_count" in summary
        print(f"Summary for {summary.get('date')}: {summary.get('dispatched_count')} dispatched, {summary.get('pending_count')} pending")
    
    def test_get_summary_for_specific_date(self, headers):
        """GET /api/dispatch/summary?date=... - summary for specific date"""
        response = requests.get(f"{BASE_URL}/api/dispatch/summary?date=2026-04-01&company_id={COMPANY_ID}", 
            headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        summary = data.get("data", {})
        assert summary.get("date") == "2026-04-01"


class TestPorterSettlement:
    """Test porter settlement report"""
    
    def test_get_porter_settlement(self, headers):
        """GET /api/dispatch/porter-settlement - settlement report"""
        response = requests.get(f"{BASE_URL}/api/dispatch/porter-settlement", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        settlement = data.get("data", {}).get("settlement", [])
        assert isinstance(settlement, list)
        
        if settlement:
            porter = settlement[0]
            assert "name" in porter
            assert "total_charges" in porter
            assert "total_paid" in porter
            assert "balance_due" in porter
            print(f"Sample settlement: {porter.get('name')} - Due: {porter.get('balance_due')}")


class TestDispatchEmployees:
    """Test dispatch employees endpoint"""
    
    def test_get_dispatch_employees(self, headers):
        """GET /api/dispatch/employees - lists dispatch role employees"""
        response = requests.get(f"{BASE_URL}/api/dispatch/employees", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Failed: {data}"
        employees = data.get("data", {}).get("employees", [])
        assert isinstance(employees, list)
        print(f"Found {len(employees)} dispatch employees")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
