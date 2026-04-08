"""
Test WebSocket Real-Time Sync Features (Iteration 8)
Tests for:
- POST /api/agent/sync-progress endpoint
- WebSocket /api/ws/sync-status endpoint
- POST /api/agent/sync endpoint (existing)
- GET /api/sync/status endpoint
"""

import pytest
import requests
import os
import json
import asyncio
import websockets
from datetime import datetime

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSyncProgressEndpoint:
    """Tests for POST /api/agent/sync-progress endpoint"""
    
    def test_sync_progress_sync_started(self):
        """Test sync_started event is received and returns success"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={"type": "sync_started", "is_first_sync": True},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "Progress received"
        print("✓ sync_started event accepted")
    
    def test_sync_progress_phase_start(self):
        """Test phase_start event for inventory phase"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={"type": "phase_start", "phase": "inventory"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ phase_start event accepted")
    
    def test_sync_progress_sales_batch_start(self):
        """Test sales_batch_start event with batch info"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={
                "type": "sales_batch_start",
                "total_batches": 12,
                "start_date": "2025-04-01",
                "end_date": "2026-03-31"
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ sales_batch_start event accepted")
    
    def test_sync_progress_sales_batch_progress(self):
        """Test sales_batch_progress event with batch details"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={
                "type": "sales_batch_progress",
                "batch": 3,
                "total_batches": 12,
                "month": "Jun 2025",
                "vouchers_so_far": 150
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ sales_batch_progress event accepted")
    
    def test_sync_progress_sales_batch_complete(self):
        """Test sales_batch_complete event"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={
                "type": "sales_batch_complete",
                "total_vouchers": 500
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ sales_batch_complete event accepted")
    
    def test_sync_progress_phase_complete(self):
        """Test phase_complete event"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={
                "type": "phase_complete",
                "phase": "sales",
                "count": 500
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ phase_complete event accepted")
    
    def test_sync_progress_sync_complete(self):
        """Test sync_complete event"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={
                "type": "sync_complete",
                "inventory_count": 100,
                "sales_count": 500,
                "customer_count": 50
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ sync_complete event accepted")
    
    def test_sync_progress_sync_error(self):
        """Test sync_error event"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync-progress",
            json={
                "type": "sync_error",
                "error": "Connection timeout to Tally"
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ sync_error event accepted")


class TestSyncStatusEndpoint:
    """Tests for GET /api/sync/status endpoint"""
    
    def test_get_sync_status(self):
        """Test GET /api/sync/status returns last sync info"""
        response = requests.get(f"{BASE_URL}/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        # Should have sync status info
        sync_data = data["data"]
        assert sync_data is not None
        print(f"✓ Sync status returned: {sync_data.get('last_sync', 'N/A')}")


class TestAgentSyncEndpoint:
    """Tests for POST /api/agent/sync endpoint (existing functionality)"""
    
    def test_agent_sync_inventory(self):
        """Test syncing inventory data"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync",
            json={
                "data_type": "inventory",
                "data": [
                    {
                        "item_id": "TEST_ITEM_WS_1",
                        "item_name": "Test Item WS 1",
                        "quantity": 100,
                        "price": 50.0,
                        "unit": "Nos",
                        "stock_group": "Test Group"
                    }
                ],
                "sync_time": datetime.utcnow().isoformat(),
                "company_name": "Test Company",
                "agent_version": "4.0.0"
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Successfully synced" in data["message"]
        print("✓ Inventory sync accepted")
    
    def test_agent_sync_sales(self):
        """Test syncing sales data"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync",
            json={
                "data_type": "sales",
                "data": [
                    {
                        "voucher_id": "TEST_VOUCHER_WS_1",
                        "voucher_date": "2025-12-01",
                        "party_name": "Test Customer",
                        "total_amount": 1000.0,
                        "items": [
                            {"item": "Test Item", "quantity": 10, "rate": 100}
                        ]
                    }
                ],
                "sync_time": datetime.utcnow().isoformat(),
                "company_name": "Test Company",
                "agent_version": "4.0.0"
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ Sales sync accepted")
    
    def test_agent_sync_customers(self):
        """Test syncing customer data"""
        response = requests.post(
            f"{BASE_URL}/api/agent/sync",
            json={
                "data_type": "customers",
                "data": [
                    {
                        "customer_name": "TEST_CUSTOMER_WS_1",
                        "ledger_group": "Sundry Debtors",
                        "outstanding_amount": 5000.0,
                        "phone": "1234567890"
                    }
                ],
                "sync_time": datetime.utcnow().isoformat(),
                "company_name": "Test Company",
                "agent_version": "4.0.0"
            },
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ Customers sync accepted")


class TestWebSocketConnection:
    """Tests for WebSocket /api/ws/sync-status endpoint"""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_websocket_connects(self):
        """Test WebSocket connection can be established"""
        ws_url = BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/ws/sync-status'
        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                # Connection successful
                print(f"✓ WebSocket connected to {ws_url}")
                
                # Send get_status action
                await ws.send(json.dumps({"action": "get_status"}))
                
                # Wait for response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                assert "event" in data
                print(f"✓ WebSocket received response: {data.get('event')}")
                
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_websocket_receives_broadcast(self):
        """Test WebSocket receives broadcast when sync-progress is posted"""
        ws_url = BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/ws/sync-status'
        
        try:
            async with websockets.connect(ws_url, close_timeout=10) as ws:
                print("✓ WebSocket connected for broadcast test")
                
                # First, drain any initial messages (like last_progress on connect)
                try:
                    initial = await asyncio.wait_for(ws.recv(), timeout=2)
                    print(f"  Initial message received: {json.loads(initial).get('event', 'unknown')}")
                except asyncio.TimeoutError:
                    pass
                
                # Post a sync progress event via HTTP
                test_event = {
                    "type": "test_broadcast",
                    "message": "Testing WebSocket broadcast",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                response = requests.post(
                    f"{BASE_URL}/api/agent/sync-progress",
                    json=test_event,
                    headers={"Content-Type": "application/json"}
                )
                assert response.status_code == 200
                
                # Wait for broadcast on WebSocket
                try:
                    broadcast = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(broadcast)
                    
                    assert "event" in data
                    assert data["event"] == "test_broadcast"
                    print(f"✓ WebSocket received broadcast: {data['event']}")
                    
                except asyncio.TimeoutError:
                    pytest.fail("WebSocket did not receive broadcast within timeout")
                    
        except Exception as e:
            pytest.fail(f"WebSocket broadcast test failed: {e}")


class TestAuthLogin:
    """Test login still works (required for frontend testing)"""
    
    def test_admin_login(self):
        """Test admin login with admin/admin123"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["role"] == "admin"
        assert "token" in data["data"]
        print("✓ Admin login successful")
    
    def test_employee_login(self):
        """Test employee login with emp1/emp123"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "emp1", "password": "emp123"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["role"] == "employee"
        print("✓ Employee login successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
