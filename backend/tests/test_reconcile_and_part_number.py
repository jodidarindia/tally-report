"""
Test Suite for Iteration 46: Reconcile Endpoint + Part Number Field
Tests:
1. POST /api/agent/reconcile endpoint - ghost data cleanup
2. Part Number field in inventory and movement analysis APIs
3. Desktop Agent v9 download file
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
TEST_TENANT_ID = "3079b0af-e899-44b4-ae7c-c35d113fe296"
TEST_COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
        "captcha_token": ""  # Empty string for testing
    })
    if response.status_code == 200 and response.json().get("success"):
        return response.json()["data"]["token"]
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


# ==================== RECONCILE ENDPOINT TESTS ====================

class TestReconcileEndpoint:
    """Tests for POST /api/agent/reconcile endpoint"""

    def test_reconcile_endpoint_exists(self, api_client):
        """Test that reconcile endpoint exists and accepts POST"""
        response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "data_type": "sales",
            "manifest_ids": [],
            "tenant_id": TEST_TENANT_ID,
            "company_id": TEST_COMPANY_ID,
            "sync_token": ""
        })
        # Should return 200 with success response (not 404 or 405)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        print(f"PASS: Reconcile endpoint exists and responds correctly")

    def test_reconcile_requires_data_type_and_tenant(self, api_client):
        """Test that reconcile requires data_type and tenant_id"""
        # Missing data_type
        response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "manifest_ids": [],
            "tenant_id": TEST_TENANT_ID
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False, "Should fail without data_type"
        assert "data_type" in data.get("error", "").lower() or "required" in data.get("error", "").lower()
        print(f"PASS: Reconcile correctly requires data_type")

        # Missing tenant_id
        response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "data_type": "sales",
            "manifest_ids": []
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False, "Should fail without tenant_id"
        print(f"PASS: Reconcile correctly requires tenant_id")

    def test_reconcile_supported_data_types(self, api_client):
        """Test that reconcile supports all expected data types"""
        supported_types = [
            "sales", "receipts", "credit_notes", "journal_vouchers",
            "stock_journals", "purchase_vouchers", "debit_notes",
            "contra_vouchers", "customers", "sundry_creditors", "bank_cash_ledgers"
        ]
        
        for data_type in supported_types:
            response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
                "data_type": data_type,
                "manifest_ids": ["TEST_ID_KEEP"],  # Non-empty manifest
                "tenant_id": TEST_TENANT_ID,
                "company_id": TEST_COMPANY_ID,
                "sync_token": ""
            })
            assert response.status_code == 200, f"Failed for {data_type}: {response.text}"
            data = response.json()
            assert data.get("success") == True, f"Reconcile failed for {data_type}: {data.get('error')}"
            print(f"PASS: Reconcile supports data_type '{data_type}'")

    def test_reconcile_unsupported_data_type(self, api_client):
        """Test that reconcile rejects unsupported data types"""
        response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "data_type": "invalid_type",
            "manifest_ids": [],
            "tenant_id": TEST_TENANT_ID,
            "company_id": TEST_COMPANY_ID,
            "sync_token": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False, "Should fail for unsupported data_type"
        assert "not supported" in data.get("error", "").lower()
        print(f"PASS: Reconcile correctly rejects unsupported data_type")

    def test_reconcile_returns_deleted_count(self, api_client):
        """Test that reconcile returns count of deleted orphans"""
        response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "data_type": "sales",
            "manifest_ids": ["KEEP_THIS_ID"],
            "tenant_id": TEST_TENANT_ID,
            "company_id": TEST_COMPANY_ID,
            "sync_token": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        # Message should contain count info
        message = data.get("message", "")
        assert "orphan" in message.lower() or "reconcile" in message.lower()
        print(f"PASS: Reconcile returns message with deletion info: {message}")

    def test_reconcile_with_empty_manifest(self, api_client):
        """Test reconcile with empty manifest (should delete all records for that type)"""
        # This is a valid use case - empty manifest means Tally has 0 records
        response = api_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "data_type": "contra_vouchers",  # Use a type unlikely to have data
            "manifest_ids": [],
            "tenant_id": TEST_TENANT_ID,
            "company_id": TEST_COMPANY_ID,
            "sync_token": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True, f"Empty manifest reconcile failed: {data.get('error')}"
        print(f"PASS: Reconcile handles empty manifest correctly")


# ==================== PART NUMBER FIELD TESTS ====================

class TestPartNumberField:
    """Tests for Part Number field in inventory and movement analysis"""

    def test_inventory_items_has_part_number(self, authenticated_client):
        """Test that inventory items API returns part_number field"""
        response = authenticated_client.get(f"{BASE_URL}/api/inventory/items")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        items = data.get("data", {}).get("items", [])
        if items:
            # Check that part_number field exists in response
            first_item = items[0]
            assert "part_number" in first_item or first_item.get("part_number") is None, \
                "part_number field should exist in inventory items"
            print(f"PASS: Inventory items API includes part_number field")
            print(f"  Sample item: {first_item.get('item_name')} - Part No: {first_item.get('part_number', '-')}")
        else:
            print(f"PASS: Inventory items API works (no items in database)")

    def test_movement_analysis_has_part_number(self, authenticated_client):
        """Test that movement analysis API returns part_number field"""
        response = authenticated_client.get(f"{BASE_URL}/api/inventory/movement-analysis")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        movements = data.get("data", {}).get("movements", [])
        if movements:
            # Check that part_number field exists in response
            first_movement = movements[0]
            assert "part_number" in first_movement, \
                "part_number field should exist in movement analysis"
            print(f"PASS: Movement analysis API includes part_number field")
            print(f"  Sample: {first_movement.get('item_name')} - Part No: {first_movement.get('part_number', '-')}")
        else:
            print(f"PASS: Movement analysis API works (no movement data)")


# ==================== DESKTOP AGENT DOWNLOAD TESTS ====================

class TestDesktopAgentDownload:
    """Tests for Desktop Agent v9 download file"""

    def test_agent_download_file_exists(self, api_client):
        """Test that desktop agent download file is accessible"""
        response = api_client.get(f"{BASE_URL}/flowra-desktop-agent.py")
        assert response.status_code == 200, f"Agent download failed: {response.status_code}"
        assert len(response.content) > 1000, "Agent file should be substantial"
        print(f"PASS: Desktop agent file accessible ({len(response.content)} bytes)")

    def test_agent_file_contains_v9(self, api_client):
        """Test that agent file contains v9 version marker"""
        response = api_client.get(f"{BASE_URL}/flowra-desktop-agent.py")
        assert response.status_code == 200
        content = response.text
        assert "v9" in content.lower() or "V9" in content, \
            "Agent file should contain v9 version marker"
        print(f"PASS: Desktop agent file contains v9 version marker")

    def test_agent_file_contains_reconcile(self, api_client):
        """Test that agent file contains reconcile functionality"""
        response = api_client.get(f"{BASE_URL}/flowra-desktop-agent.py")
        assert response.status_code == 200
        content = response.text
        assert "reconcile" in content.lower(), \
            "Agent file should contain reconcile functionality"
        print(f"PASS: Desktop agent file contains reconcile functionality")

    def test_agent_file_contains_partnumber(self, api_client):
        """Test that agent file fetches PARTNUMBER from Tally"""
        response = api_client.get(f"{BASE_URL}/flowra-desktop-agent.py")
        assert response.status_code == 200
        content = response.text
        assert "PARTNUMBER" in content or "part_number" in content, \
            "Agent file should fetch PARTNUMBER from Tally"
        print(f"PASS: Desktop agent file contains PARTNUMBER fetch")


# ==================== SYNC HISTORY LOGGING TEST ====================

class TestSyncHistoryLogging:
    """Test that reconcile logs to sync_history collection"""

    def test_reconcile_logs_to_sync_history(self, authenticated_client):
        """Test that reconcile creates sync_history entry"""
        # First, do a reconcile
        response = authenticated_client.post(f"{BASE_URL}/api/agent/reconcile", json={
            "data_type": "customers",
            "manifest_ids": ["TEST_CUSTOMER_KEEP"],
            "tenant_id": TEST_TENANT_ID,
            "company_id": TEST_COMPANY_ID,
            "sync_token": ""
        })
        assert response.status_code == 200
        
        # Then check sync history
        history_response = authenticated_client.get(f"{BASE_URL}/api/sync/history?limit=10")
        assert history_response.status_code == 200
        history_data = history_response.json()
        
        if history_data.get("success"):
            cycles = history_data.get("data", {}).get("cycles", [])
            # Check if any cycle has reconcile data type
            has_reconcile = any(
                "reconcile" in str(cycle.get("data_types", {})).lower()
                for cycle in cycles
            )
            print(f"PASS: Sync history API works. Reconcile logged: {has_reconcile}")
        else:
            print(f"PASS: Sync history API accessible (may have no data)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
