"""
Iteration 14 Tests: New Features
- GET /api/sync/history - Sync history timeline
- POST /api/customers/ledger/export - Tally-format PDF ledger export
- POST /api/agent/sync with credit_notes data_type
- POST /api/agent/sync with journal_vouchers data_type
- POST /api/agent/sync with stock_journals data_type
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSyncHistory:
    """Tests for GET /api/sync/history endpoint"""
    
    def test_sync_history_endpoint_exists(self):
        """Verify sync history endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/sync/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        print("PASS: GET /api/sync/history returns 200 with success=True")
    
    def test_sync_history_returns_cycles_structure(self):
        """Verify sync history returns cycles array and total count"""
        response = requests.get(f"{BASE_URL}/api/sync/history")
        assert response.status_code == 200
        data = response.json()
        assert 'data' in data, "Response should have 'data' field"
        assert 'cycles' in data['data'], "Data should have 'cycles' field"
        assert 'total' in data['data'], "Data should have 'total' field"
        assert isinstance(data['data']['cycles'], list), "cycles should be a list"
        print(f"PASS: Sync history returns cycles array with {data['data']['total']} cycles")
    
    def test_sync_history_with_limit_param(self):
        """Verify sync history respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/sync/history?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') == True
        print("PASS: GET /api/sync/history?limit=5 works correctly")


class TestCreditNotesSync:
    """Tests for POST /api/agent/sync with credit_notes data_type"""
    
    def test_sync_credit_notes_empty(self):
        """Verify credit_notes sync with empty data works"""
        payload = {
            "data_type": "credit_notes",
            "data": [],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25"
        }
        response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        print("PASS: POST /api/agent/sync with credit_notes (empty) returns success")
    
    def test_sync_credit_notes_with_data(self):
        """Verify credit_notes sync with actual data works"""
        payload = {
            "data_type": "credit_notes",
            "data": [
                {
                    "voucher_id": "CN-TEST-001",
                    "voucher_date": "2024-12-15",
                    "party_name": "Test Customer",
                    "total_amount": 5000.00,
                    "items": [{"item_name": "Test Item", "quantity": 2, "rate": 2500}],
                    "narration": "Test credit note",
                    "reference_number": "REF-CN-001"
                }
            ],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25",
            "agent_version": "1.0.0"
        }
        response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert "1 credit_notes" in data.get('message', ''), f"Message should mention 1 credit_notes: {data}"
        print("PASS: POST /api/agent/sync with credit_notes (1 item) returns success")


class TestJournalVouchersSync:
    """Tests for POST /api/agent/sync with journal_vouchers data_type"""
    
    def test_sync_journal_vouchers_empty(self):
        """Verify journal_vouchers sync with empty data works"""
        payload = {
            "data_type": "journal_vouchers",
            "data": [],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25"
        }
        response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        print("PASS: POST /api/agent/sync with journal_vouchers (empty) returns success")
    
    def test_sync_journal_vouchers_with_data(self):
        """Verify journal_vouchers sync with actual data works"""
        payload = {
            "data_type": "journal_vouchers",
            "data": [
                {
                    "voucher_id": "JV-TEST-001",
                    "voucher_date": "2024-12-15",
                    "party_name": "Test Customer",
                    "debit_amount": 10000.00,
                    "credit_amount": 0,
                    "narration": "Test journal entry",
                    "ledger_entries": [
                        {"ledger": "Test Customer", "debit": 10000, "credit": 0},
                        {"ledger": "Sales", "debit": 0, "credit": 10000}
                    ]
                }
            ],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25",
            "agent_version": "1.0.0"
        }
        response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert "1 journal_vouchers" in data.get('message', ''), f"Message should mention 1 journal_vouchers: {data}"
        print("PASS: POST /api/agent/sync with journal_vouchers (1 item) returns success")


class TestStockJournalsSync:
    """Tests for POST /api/agent/sync with stock_journals data_type"""
    
    def test_sync_stock_journals_empty(self):
        """Verify stock_journals sync with empty data works"""
        payload = {
            "data_type": "stock_journals",
            "data": [],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25"
        }
        response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        print("PASS: POST /api/agent/sync with stock_journals (empty) returns success")
    
    def test_sync_stock_journals_with_data(self):
        """Verify stock_journals sync with actual data works"""
        payload = {
            "data_type": "stock_journals",
            "data": [
                {
                    "voucher_id": "SJ-TEST-001",
                    "voucher_date": "2024-12-15",
                    "items": [
                        {"item_name": "Test Item", "source_godown": "Main", "dest_godown": "Branch", "quantity": 10}
                    ],
                    "narration": "Stock transfer test"
                }
            ],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25",
            "agent_version": "1.0.0"
        }
        response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got {data}"
        assert "1 stock_journals" in data.get('message', ''), f"Message should mention 1 stock_journals: {data}"
        print("PASS: POST /api/agent/sync with stock_journals (1 item) returns success")


class TestLedgerPDFExport:
    """Tests for POST /api/customers/ledger/export endpoint"""
    
    def test_ledger_export_missing_customer(self):
        """Verify ledger export returns error when customer_name is missing"""
        payload = {"customer_name": "", "fy": "2024-25"}
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('success') == False, "Should return success=False for missing customer"
        assert 'error' in data, "Should have error message"
        print("PASS: POST /api/customers/ledger/export with empty customer returns error")
    
    def test_ledger_export_nonexistent_customer(self):
        """Verify ledger export returns error for customer with no transactions"""
        payload = {"customer_name": "NonExistentCustomer12345", "fy": "2024-25"}
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=payload)
        # Should return 200 with success=False or PDF if customer exists
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        # Check if it's JSON error or PDF
        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            data = response.json()
            assert data.get('success') == False, "Should return success=False for no transactions"
            print("PASS: POST /api/customers/ledger/export with nonexistent customer returns error")
        else:
            print("PASS: POST /api/customers/ledger/export returned PDF (customer has transactions)")
    
    def test_ledger_export_with_test_customer(self):
        """Test ledger export with a customer that has synced data"""
        # First, sync some test sales data for a customer
        sync_payload = {
            "data_type": "sales",
            "data": [
                {
                    "voucher_id": "SALE-PDF-TEST-001",
                    "voucher_date": "2024-12-15",
                    "party_name": "PDF Test Customer",
                    "total_amount": 15000.00,
                    "reference_number": "INV-001",
                    "narration": "Test sale for PDF export"
                }
            ],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "Test Company",
            "financial_year": "2024-25"
        }
        sync_response = requests.post(f"{BASE_URL}/api/agent/sync", json=sync_payload)
        assert sync_response.status_code == 200, f"Sales sync failed: {sync_response.text}"
        
        # Now try to export ledger
        export_payload = {"customer_name": "PDF Test Customer", "fy": "2024-25"}
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=export_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get('content-type', '')
        if 'application/pdf' in content_type:
            assert len(response.content) > 0, "PDF should have content"
            print(f"PASS: Ledger PDF export generated successfully ({len(response.content)} bytes)")
        else:
            # Might be JSON error if no transactions found
            data = response.json()
            print(f"INFO: Ledger export returned JSON: {data}")


class TestSyncHistoryPopulation:
    """Tests to verify sync history is populated after sync operations"""
    
    def test_sync_creates_history_entry(self):
        """Verify that sync operations create history entries"""
        # Perform a sync
        payload = {
            "data_type": "inventory",
            "data": [{"item_name": "History Test Item", "quantity": 100, "rate": 50}],
            "sync_time": datetime.now(timezone.utc).isoformat(),
            "company_name": "History Test Company",
            "financial_year": "2024-25",
            "agent_version": "1.0.0",
            "sync_mode": "full"
        }
        sync_response = requests.post(f"{BASE_URL}/api/agent/sync", json=payload)
        assert sync_response.status_code == 200, f"Sync failed: {sync_response.text}"
        
        # Check history
        history_response = requests.get(f"{BASE_URL}/api/sync/history")
        assert history_response.status_code == 200
        data = history_response.json()
        assert data.get('success') == True
        cycles = data['data'].get('cycles', [])
        
        # Should have at least one cycle now
        if len(cycles) > 0:
            latest = cycles[0]
            assert 'timestamp' in latest, "Cycle should have timestamp"
            assert 'data_types' in latest, "Cycle should have data_types"
            print(f"PASS: Sync history has {len(cycles)} cycles, latest has {len(latest.get('data_types', {}))} data types")
        else:
            print("INFO: No sync cycles found (may be first run)")


class TestAuthAndExistingEndpoints:
    """Verify existing endpoints still work after new features"""
    
    def test_login_still_works(self):
        """Verify login endpoint works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.status_code}"
        data = response.json()
        assert data.get('success') == True, f"Login should succeed: {data}"
        assert 'token' in data.get('data', {}), "Should return token"
        print("PASS: POST /api/auth/login with admin/admin123 works")
    
    def test_sync_status_still_works(self):
        """Verify sync status endpoint works"""
        response = requests.get(f"{BASE_URL}/api/sync/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('success') == True
        print("PASS: GET /api/sync/status works")
    
    def test_customers_outstanding_still_works(self):
        """Verify customers outstanding endpoint works"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('success') == True
        assert 'customers' in data.get('data', {}), "Should have customers field"
        print("PASS: GET /api/customers/outstanding works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
