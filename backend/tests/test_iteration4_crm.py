"""
Iteration 4 CRM Enhancement Tests
Tests for: Customer Targets, Ledger Export, Follow-up Dropdown, Dashboard Reminders
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCustomerTargets:
    """Tests for customer targets with last FY sales and monthly breakdown"""
    
    def test_get_targets_returns_required_fields(self):
        """GET /api/customers/targets returns targets with all required fields"""
        response = requests.get(f"{BASE_URL}/api/customers/targets")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "targets" in data["data"]
        
        targets = data["data"]["targets"]
        assert len(targets) > 0
        
        # Check first target has all required fields
        target = targets[0]
        assert "customer_name" in target
        assert "last_fy_sales" in target
        assert "target_amount" in target
        assert "achieved_amount" in target
        assert "achievement_percentage" in target
        assert "remaining" in target
        assert "monthly_sales" in target
        assert "has_custom_target" in target
        print(f"PASS: Targets endpoint returns all required fields")
    
    def test_targets_has_monthly_sales_array(self):
        """Targets include monthly_sales array with month and amount"""
        response = requests.get(f"{BASE_URL}/api/customers/targets")
        data = response.json()
        
        targets = data["data"]["targets"]
        for target in targets:
            monthly = target.get("monthly_sales", [])
            if len(monthly) > 0:
                assert "month" in monthly[0]
                assert "amount" in monthly[0]
                print(f"PASS: {target['customer_name']} has monthly_sales with month/amount")
                return
        
        print("PASS: Monthly sales structure verified")
    
    def test_set_target_saves_correctly(self):
        """POST /api/customers/targets/set saves target with last_fy_sales"""
        payload = {
            "customer_name": "Tech Solutions Pvt Ltd",
            "target_amount": 600000,
            "last_fy_sales": 500000
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/targets/set", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["data"]["target_amount"] == 600000
        assert data["data"]["last_fy_sales"] == 500000
        print(f"PASS: Target set for Tech Solutions Pvt Ltd")
    
    def test_custom_target_shows_has_custom_target_flag(self):
        """After setting target, has_custom_target flag is True"""
        # First set a target
        payload = {
            "customer_name": "Tech Solutions Pvt Ltd",
            "target_amount": 600000,
            "last_fy_sales": 500000
        }
        requests.post(f"{BASE_URL}/api/customers/targets/set", json=payload)
        
        # Then verify flag
        response = requests.get(f"{BASE_URL}/api/customers/targets")
        data = response.json()
        
        tech_target = next((t for t in data["data"]["targets"] if t["customer_name"] == "Tech Solutions Pvt Ltd"), None)
        assert tech_target is not None
        assert tech_target["has_custom_target"] == True
        print(f"PASS: Tech Solutions Pvt Ltd has has_custom_target=True")
    
    def test_set_target_empty_name_fails(self):
        """POST /api/customers/targets/set with empty name returns error"""
        payload = {
            "customer_name": "",
            "target_amount": 100000
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/targets/set", json=payload)
        data = response.json()
        assert data["success"] == False
        assert "required" in data["error"].lower()
        print(f"PASS: Empty customer name validation works")


class TestLedgerExport:
    """Tests for customer ledger export (XLS/PDF)"""
    
    def test_export_ledger_excel_returns_xlsx(self):
        """POST /api/customers/ledger/export with format=excel returns xlsx file"""
        payload = {
            "customer_name": "Tech Solutions Pvt Ltd",
            "format": "excel"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=payload)
        assert response.status_code == 200
        
        content_type = response.headers.get("content-type", "")
        assert "spreadsheet" in content_type or "excel" in content_type or "octet-stream" in content_type
        
        content_disp = response.headers.get("content-disposition", "")
        assert ".xlsx" in content_disp
        print(f"PASS: Excel ledger export returns xlsx file")
    
    def test_export_ledger_pdf_returns_pdf(self):
        """POST /api/customers/ledger/export with format=pdf returns pdf file"""
        payload = {
            "customer_name": "Tech Solutions Pvt Ltd",
            "format": "pdf"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=payload)
        assert response.status_code == 200
        
        content_type = response.headers.get("content-type", "")
        assert "pdf" in content_type
        
        content_disp = response.headers.get("content-disposition", "")
        assert ".pdf" in content_disp
        print(f"PASS: PDF ledger export returns pdf file")
    
    def test_export_ledger_missing_customer_fails(self):
        """POST /api/customers/ledger/export with empty customer returns error"""
        payload = {
            "customer_name": "",
            "format": "excel"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=payload)
        data = response.json()
        assert data["success"] == False
        assert "required" in data["error"].lower()
        print(f"PASS: Empty customer name validation works for ledger export")
    
    def test_export_ledger_nonexistent_customer(self):
        """POST /api/customers/ledger/export with nonexistent customer returns error"""
        payload = {
            "customer_name": "Nonexistent Customer XYZ",
            "format": "excel"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/ledger/export", json=payload)
        data = response.json()
        assert data["success"] == False
        assert "no transactions" in data["error"].lower()
        print(f"PASS: Nonexistent customer returns appropriate error")


class TestFollowups:
    """Tests for follow-ups with customer dropdown"""
    
    def test_get_followups_returns_list(self):
        """GET /api/customers/followups returns followups list"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "followups" in data["data"]
        assert "count" in data["data"]
        print(f"PASS: Followups endpoint returns list with count={data['data']['count']}")
    
    def test_followup_has_required_fields(self):
        """Followups have customer_name, followup_date, followup_type, status"""
        response = requests.get(f"{BASE_URL}/api/customers/followups")
        data = response.json()
        
        followups = data["data"]["followups"]
        if len(followups) > 0:
            f = followups[0]
            assert "customer_name" in f
            assert "followup_date" in f
            assert "followup_type" in f
            assert "status" in f
            print(f"PASS: Followup has all required fields")
        else:
            print("SKIP: No followups to verify fields")
    
    def test_create_followup_with_customer_name(self):
        """POST /api/customers/followups creates followup with customer from dropdown"""
        # Get a customer name from outstanding list (simulating dropdown)
        outstanding_res = requests.get(f"{BASE_URL}/api/customers/outstanding")
        customers = outstanding_res.json()["data"]["customers"]
        customer_name = customers[0]["customer_name"] if customers else "Test Customer"
        
        payload = {
            "customer_name": customer_name,
            "followup_date": (datetime.now() + timedelta(days=3)).isoformat(),
            "followup_type": "call",
            "notes": "Test followup from iteration 4"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/followups", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "id" in data["data"]
        print(f"PASS: Created followup for {customer_name}")
    
    def test_outstanding_provides_customer_names_for_dropdown(self):
        """GET /api/customers/outstanding provides customer names for dropdown"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        
        data = response.json()
        customers = data["data"]["customers"]
        assert len(customers) > 0
        
        # All customers have customer_name field
        for c in customers:
            assert "customer_name" in c
            assert len(c["customer_name"]) > 0
        
        print(f"PASS: Outstanding endpoint provides {len(customers)} customer names for dropdown")


class TestDashboardReminders:
    """Tests for dashboard follow-up reminders"""
    
    def test_reminders_endpoint_returns_categories(self):
        """GET /api/dashboard/reminders returns overdue, today, upcoming"""
        response = requests.get(f"{BASE_URL}/api/dashboard/reminders")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        
        reminders = data["data"]
        assert "overdue" in reminders
        assert "today" in reminders
        assert "upcoming" in reminders
        assert "total_pending" in reminders
        assert "overdue_count" in reminders
        assert "today_count" in reminders
        print(f"PASS: Reminders endpoint returns all categories")
    
    def test_reminders_have_customer_and_date(self):
        """Reminders include customer_name, followup_date, followup_type"""
        response = requests.get(f"{BASE_URL}/api/dashboard/reminders")
        data = response.json()
        
        reminders = data["data"]
        
        # Check any non-empty category
        for category in ["overdue", "today", "upcoming"]:
            items = reminders.get(category, [])
            if len(items) > 0:
                item = items[0]
                assert "customer_name" in item
                assert "followup_date" in item
                assert "followup_type" in item
                print(f"PASS: {category} reminders have customer_name, date, type")
                return
        
        print("PASS: Reminder structure verified (no items to check)")
    
    def test_overdue_reminders_are_past_dates(self):
        """Overdue reminders have dates before today"""
        response = requests.get(f"{BASE_URL}/api/dashboard/reminders")
        data = response.json()
        
        overdue = data["data"].get("overdue", [])
        today = datetime.now().strftime("%Y-%m-%d")
        
        for item in overdue:
            f_date = item["followup_date"][:10]
            assert f_date < today, f"Overdue item {item['customer_name']} has future date {f_date}"
        
        print(f"PASS: All {len(overdue)} overdue items have past dates")
    
    def test_today_reminders_are_today(self):
        """Today reminders have today's date"""
        response = requests.get(f"{BASE_URL}/api/dashboard/reminders")
        data = response.json()
        
        today_items = data["data"].get("today", [])
        today = datetime.now().strftime("%Y-%m-%d")
        
        for item in today_items:
            f_date = item["followup_date"][:10]
            assert f_date == today, f"Today item {item['customer_name']} has wrong date {f_date}"
        
        print(f"PASS: All {len(today_items)} today items have today's date")


class TestOutstandingWithExport:
    """Tests for outstanding tab with ledger export buttons"""
    
    def test_outstanding_returns_customer_list(self):
        """GET /api/customers/outstanding returns customer list with amounts"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        
        customers = data["data"]["customers"]
        assert len(customers) > 0
        
        # Check required fields for export
        c = customers[0]
        assert "customer_name" in c
        assert "outstanding_amount" in c
        assert "overdue_amount" in c
        print(f"PASS: Outstanding returns {len(customers)} customers with amounts")
    
    def test_outstanding_has_aging_breakdown(self):
        """Outstanding includes aging breakdown (30/60/90/90+ days)"""
        response = requests.get(f"{BASE_URL}/api/customers/outstanding")
        data = response.json()
        
        c = data["data"]["customers"][0]
        assert "aging_30_days" in c
        assert "aging_60_days" in c
        assert "aging_90_days" in c
        assert "aging_90_plus" in c
        print(f"PASS: Outstanding has aging breakdown")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
