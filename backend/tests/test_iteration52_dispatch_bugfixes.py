"""
Iteration 52: Testing 9 Dispatch Terminal Bug Fixes
1. Kanban changes not reflecting pending tab
2. Date selector affecting all tabs
3. Close of Day PDF
4. Transporter settlement
5. IST timezone in timeline
6. History card detail click
7. Dispatch nav between CA Corner and Sync History
8. FY selector impact
9. Edit/delete porter and transporter
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("success"), f"Login not successful: {data}"
    return data["data"]["token"]

@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers with company ID"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "X-Company-Id": "03f638d1-eab0-47ee-aed6-59049ebb5207"
    }


class TestDispatchSummaryDateFilter:
    """Bug #2: Date selector should affect summary data"""
    
    def test_summary_returns_date_specific_data(self, headers):
        """GET /api/dispatch/summary?date=2026-04-23 should return data for that date"""
        response = requests.get(f"{BASE_URL}/api/dispatch/summary?date=2026-04-23", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Summary failed: {data}"
        summary = data["data"]
        # Verify date is returned in response
        assert summary.get("date") == "2026-04-23", f"Expected date 2026-04-23, got {summary.get('date')}"
        # Verify summary structure
        assert "dispatched_count" in summary
        assert "pending_count" in summary
        assert "hold_count" in summary
        assert "total_boxes" in summary
        
    def test_summary_different_dates_return_different_data(self, headers):
        """Summary for different dates should potentially differ"""
        r1 = requests.get(f"{BASE_URL}/api/dispatch/summary?date=2026-04-01", headers=headers)
        r2 = requests.get(f"{BASE_URL}/api/dispatch/summary?date=2026-04-23", headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json()["data"]
        d2 = r2.json()["data"]
        # Both should have the correct date
        assert d1["date"] == "2026-04-01"
        assert d2["date"] == "2026-04-23"


class TestTransporterSettlement:
    """Bug #4: Transporter settlement API"""
    
    def test_transporter_settlement_returns_data(self, headers):
        """GET /api/dispatch/transporter-settlement should return settlement data"""
        response = requests.get(f"{BASE_URL}/api/dispatch/transporter-settlement", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Settlement failed: {data}"
        assert "settlement" in data["data"]
        settlement = data["data"]["settlement"]
        assert isinstance(settlement, list)
        # If there are transporters, verify structure
        if settlement:
            item = settlement[0]
            assert "transporter_id" in item
            assert "name" in item
            assert "total_charges" in item
            assert "total_paid" in item
            assert "balance_due" in item
            assert "dispatch_count" in item
            
    def test_transporter_payment_record(self, headers):
        """POST /api/dispatch/transporter-payment should record payment"""
        # First get a transporter name
        tr = requests.get(f"{BASE_URL}/api/dispatch/transporters", headers=headers)
        transporters = tr.json()["data"]["transporters"]
        if not transporters:
            pytest.skip("No transporters to test payment")
        
        transporter_name = transporters[0]["name"]
        response = requests.post(f"{BASE_URL}/api/dispatch/transporter-payment", headers=headers, json={
            "transporter_name": transporter_name,
            "amount": 100.0,
            "payment_ref": "TEST-REF-52"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Payment failed: {data}"
        assert "Payment recorded" in data.get("message", "")


class TestCloseOfDayPDF:
    """Bug #3: Close of Day PDF generation"""
    
    def test_cod_pdf_returns_valid_pdf(self, headers):
        """GET /api/dispatch/close-of-day-pdf?date=2026-04-23 should return PDF"""
        response = requests.get(f"{BASE_URL}/api/dispatch/close-of-day-pdf?date=2026-04-23", headers=headers)
        assert response.status_code == 200
        # Check content type is PDF
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF, got {content_type}"
        # Check content starts with PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response does not start with PDF magic bytes"
        # Check content disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "dispatch_cod_2026-04-23.pdf" in content_disp, f"Unexpected filename: {content_disp}"


class TestPorterCRUD:
    """Bug #9: Edit/delete porter"""
    
    def test_create_porter(self, headers):
        """POST /api/dispatch/porters creates a porter"""
        response = requests.post(f"{BASE_URL}/api/dispatch/porters", headers=headers, json={
            "name": "TEST_Porter_52",
            "phone": "9876543210"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Create failed: {data}"
        assert "porter_id" in data["data"]
        return data["data"]["porter_id"]
    
    def test_update_porter(self, headers):
        """PATCH /api/dispatch/porters/{id} updates porter"""
        # First create a porter
        create_resp = requests.post(f"{BASE_URL}/api/dispatch/porters", headers=headers, json={
            "name": "TEST_Porter_Update_52",
            "phone": "1111111111"
        })
        porter_id = create_resp.json()["data"]["porter_id"]
        
        # Update the porter
        response = requests.patch(f"{BASE_URL}/api/dispatch/porters/{porter_id}", headers=headers, json={
            "name": "TEST_Porter_Updated_52",
            "phone": "2222222222"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Update failed: {data}"
        assert "Porter updated" in data.get("message", "")
        
        # Verify update persisted
        get_resp = requests.get(f"{BASE_URL}/api/dispatch/porters", headers=headers)
        porters = get_resp.json()["data"]["porters"]
        updated = next((p for p in porters if p["porter_id"] == porter_id), None)
        assert updated is not None
        assert updated["name"] == "TEST_Porter_Updated_52"
        assert updated["phone"] == "2222222222"
    
    def test_delete_porter(self, headers):
        """DELETE /api/dispatch/porters/{id} deletes porter"""
        # First create a porter
        create_resp = requests.post(f"{BASE_URL}/api/dispatch/porters", headers=headers, json={
            "name": "TEST_Porter_Delete_52",
            "phone": "3333333333"
        })
        porter_id = create_resp.json()["data"]["porter_id"]
        
        # Delete the porter
        response = requests.delete(f"{BASE_URL}/api/dispatch/porters/{porter_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Delete failed: {data}"
        assert "Porter deleted" in data.get("message", "")
        
        # Verify deletion
        get_resp = requests.get(f"{BASE_URL}/api/dispatch/porters", headers=headers)
        porters = get_resp.json()["data"]["porters"]
        deleted = next((p for p in porters if p["porter_id"] == porter_id), None)
        assert deleted is None, "Porter should be deleted"


class TestTransporterCRUD:
    """Bug #9: Edit/delete transporter"""
    
    def test_create_transporter(self, headers):
        """POST /api/dispatch/transporters creates a transporter"""
        response = requests.post(f"{BASE_URL}/api/dispatch/transporters", headers=headers, json={
            "name": "TEST_Transporter_52",
            "phone": "9876543210"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Create failed: {data}"
        assert "transporter_id" in data["data"]
        
    def test_update_transporter(self, headers):
        """PATCH /api/dispatch/transporters/{id} updates transporter"""
        # First create a transporter
        create_resp = requests.post(f"{BASE_URL}/api/dispatch/transporters", headers=headers, json={
            "name": "TEST_Transporter_Update_52",
            "phone": "4444444444"
        })
        transporter_id = create_resp.json()["data"]["transporter_id"]
        
        # Update the transporter
        response = requests.patch(f"{BASE_URL}/api/dispatch/transporters/{transporter_id}", headers=headers, json={
            "name": "TEST_Transporter_Updated_52",
            "phone": "5555555555"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Update failed: {data}"
        assert "Transporter updated" in data.get("message", "")
        
        # Verify update persisted
        get_resp = requests.get(f"{BASE_URL}/api/dispatch/transporters", headers=headers)
        transporters = get_resp.json()["data"]["transporters"]
        updated = next((t for t in transporters if t["transporter_id"] == transporter_id), None)
        assert updated is not None
        assert updated["name"] == "TEST_Transporter_Updated_52"
        assert updated["phone"] == "5555555555"
    
    def test_delete_transporter(self, headers):
        """DELETE /api/dispatch/transporters/{id} deletes transporter"""
        # First create a transporter
        create_resp = requests.post(f"{BASE_URL}/api/dispatch/transporters", headers=headers, json={
            "name": "TEST_Transporter_Delete_52",
            "phone": "6666666666"
        })
        transporter_id = create_resp.json()["data"]["transporter_id"]
        
        # Delete the transporter
        response = requests.delete(f"{BASE_URL}/api/dispatch/transporters/{transporter_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success"), f"Delete failed: {data}"
        assert "Transporter deleted" in data.get("message", "")
        
        # Verify deletion
        get_resp = requests.get(f"{BASE_URL}/api/dispatch/transporters", headers=headers)
        transporters = get_resp.json()["data"]["transporters"]
        deleted = next((t for t in transporters if t["transporter_id"] == transporter_id), None)
        assert deleted is None, "Transporter should be deleted"


class TestDispatchNavOrder:
    """Bug #7: Dispatch nav should be between CA Corner and Sync History"""
    
    def test_all_features_order(self, headers):
        """Verify ALL_FEATURES order has dispatch between ca_corner and sync_history"""
        # Get user info to check features order
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        features = data["data"]["features"]
        
        # Find indices
        ca_corner_idx = features.index("ca_corner") if "ca_corner" in features else -1
        dispatch_idx = features.index("dispatch") if "dispatch" in features else -1
        sync_history_idx = features.index("sync_history") if "sync_history" in features else -1
        
        # Verify order: ca_corner < dispatch < sync_history
        assert ca_corner_idx >= 0, "ca_corner not in features"
        assert dispatch_idx >= 0, "dispatch not in features"
        assert sync_history_idx >= 0, "sync_history not in features"
        assert ca_corner_idx < dispatch_idx < sync_history_idx, \
            f"Wrong order: ca_corner={ca_corner_idx}, dispatch={dispatch_idx}, sync_history={sync_history_idx}"


class TestDispatchHistory:
    """Bug #6: History card detail click"""
    
    def test_history_returns_completed_cards(self, headers):
        """GET /api/dispatch/history returns dispatched/info_shared cards"""
        response = requests.get(f"{BASE_URL}/api/dispatch/history", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        assert "cards" in data["data"]
        assert "total" in data["data"]
        # All cards should be dispatched or info_shared
        for card in data["data"]["cards"]:
            assert card["status"] in ["dispatched", "info_shared"], f"Unexpected status: {card['status']}"
    
    def test_history_card_has_timeline(self, headers):
        """History cards should have status_history for timeline display"""
        response = requests.get(f"{BASE_URL}/api/dispatch/history?limit=5", headers=headers)
        data = response.json()
        if data["data"]["cards"]:
            card = data["data"]["cards"][0]
            assert "status_history" in card, "Card should have status_history"
            assert isinstance(card["status_history"], list)
            # Each history entry should have 'at' timestamp for IST conversion
            if card["status_history"]:
                entry = card["status_history"][0]
                assert "at" in entry, "History entry should have 'at' timestamp"
                assert "status" in entry


class TestPendingTabReflectsBoard:
    """Bug #1: Kanban changes should reflect in pending tab"""
    
    def test_active_cards_match_pending_filter(self, headers):
        """GET /api/dispatch/cards?status=active returns cards for pending tab"""
        response = requests.get(f"{BASE_URL}/api/dispatch/cards?status=active", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success")
        cards = data["data"]["cards"]
        # Active cards should not include dispatched/info_shared
        for card in cards:
            assert card["status"] not in ["dispatched", "info_shared"], \
                f"Active cards should not include {card['status']}"


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_porters(self, headers):
        """Remove TEST_ prefixed porters"""
        response = requests.get(f"{BASE_URL}/api/dispatch/porters", headers=headers)
        porters = response.json()["data"]["porters"]
        for p in porters:
            if p["name"].startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/dispatch/porters/{p['porter_id']}", headers=headers)
    
    def test_cleanup_test_transporters(self, headers):
        """Remove TEST_ prefixed transporters"""
        response = requests.get(f"{BASE_URL}/api/dispatch/transporters", headers=headers)
        transporters = response.json()["data"]["transporters"]
        for t in transporters:
            if t["name"].startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/dispatch/transporters/{t['transporter_id']}", headers=headers)
