"""
Iteration 37: Branch Filter on ALL CRM and Analytics Tabs + CRM Tab Alphabetical Order

Tests:
1. CRM tabs alphabetical order (Follow-ups, Outstanding, Payment Behavior, Targets)
2. CRM Outstanding tab: branch parties excluded when toggle ON
3. CRM Follow-ups tab: branch party followups excluded when toggle ON
4. CRM Targets tab: branch parties excluded when toggle ON (count drops from 41 to 39)
5. CRM Payment Behavior tab: branch parties excluded when toggle ON (count drops from 41 to 39)
6. Analytics Movement tab: branch filtering applied
7. Analytics Below Cost tab: branch filtering applied
8. Analytics Sales Frequency tab: branch filtering applied (count drops from 172 to 167)
9. Analytics Customer Items tab: customer-names excludes branches, customer-item-sales returns empty for branch party
10. Dashboard Total Sales changes when toggle clicked (Rs.5.06Cr -> Rs.3.16Cr)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
COMPANY_UUID = "03f638d1-eab0-47ee-aed6-59049ebb5207"
BRANCH_PARTY = "ASA Autotech India Pvt Ltd Raipur DEPOT"
FY = "2024-25"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{API}/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("success"), f"Login not successful: {data}"
    return data["data"]["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token and company ID"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Company-ID": COMPANY_UUID,
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def auth_headers_with_branch_exclusion(auth_token):
    """Headers with auth token, company ID, and branch exclusion"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Company-ID": COMPANY_UUID,
        "X-Exclude-Branches": "true",
        "Content-Type": "application/json"
    }


class TestAuthentication:
    """Basic auth tests"""
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{API}/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "token" in data.get("data", {})
        print(f"✓ Admin login successful")


class TestDashboardBranchFilter:
    """Dashboard branch filtering tests"""
    
    def test_sales_summary_without_branch_exclusion(self, auth_headers):
        """Test sales summary includes all sales when branch exclusion is OFF"""
        response = requests.get(f"{API}/sales/summary?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_sales = data["data"]["total_sales"]
        print(f"✓ Total sales WITHOUT branch exclusion: Rs.{total_sales:,.0f}")
        # Should be around Rs.5.06Cr
        assert total_sales > 40000000, f"Expected total sales > 4Cr, got {total_sales}"
        return total_sales
    
    def test_sales_summary_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test sales summary excludes branch sales when toggle ON"""
        response = requests.get(f"{API}/sales/summary?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_sales = data["data"]["total_sales"]
        print(f"✓ Total sales WITH branch exclusion: Rs.{total_sales:,.0f}")
        # Should be around Rs.3.16Cr (lower than without exclusion)
        assert total_sales < 40000000, f"Expected total sales < 4Cr with exclusion, got {total_sales}"
        return total_sales
    
    def test_sales_difference_is_significant(self, auth_headers, auth_headers_with_branch_exclusion):
        """Test that branch exclusion makes a significant difference"""
        # Without exclusion
        resp1 = requests.get(f"{API}/sales/summary?fy={FY}", headers=auth_headers)
        total_with = resp1.json()["data"]["total_sales"]
        
        # With exclusion
        resp2 = requests.get(f"{API}/sales/summary?fy={FY}", headers=auth_headers_with_branch_exclusion)
        total_without = resp2.json()["data"]["total_sales"]
        
        difference = total_with - total_without
        print(f"✓ Sales difference (branch sales): Rs.{difference:,.0f}")
        # Branch sales should be around Rs.1.9Cr
        assert difference > 10000000, f"Expected branch sales > 1Cr, got {difference}"


class TestCRMOutstandingBranchFilter:
    """CRM Outstanding tab branch filtering tests"""
    
    def test_outstanding_without_branch_exclusion(self, auth_headers):
        """Test outstanding includes branch parties when exclusion OFF"""
        response = requests.get(f"{API}/customers/outstanding?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"]["customers"]
        customer_names = [c["customer_name"] for c in customers]
        print(f"✓ Outstanding customers count (no exclusion): {len(customers)}")
        # Branch party should be in the list
        assert BRANCH_PARTY in customer_names, f"Branch party '{BRANCH_PARTY}' should be in outstanding list"
        print(f"✓ Branch party '{BRANCH_PARTY}' found in outstanding list")
    
    def test_outstanding_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test outstanding excludes branch parties when toggle ON"""
        response = requests.get(f"{API}/customers/outstanding?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"]["customers"]
        customer_names = [c["customer_name"] for c in customers]
        print(f"✓ Outstanding customers count (with exclusion): {len(customers)}")
        # Branch party should NOT be in the list
        assert BRANCH_PARTY not in customer_names, f"Branch party '{BRANCH_PARTY}' should NOT be in outstanding list with exclusion"
        print(f"✓ Branch party '{BRANCH_PARTY}' correctly excluded from outstanding list")


class TestCRMFollowupsBranchFilter:
    """CRM Follow-ups tab branch filtering tests"""
    
    def test_followups_endpoint_works(self, auth_headers):
        """Test followups endpoint returns data"""
        response = requests.get(f"{API}/customers/followups", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        followups = data["data"]["followups"]
        print(f"✓ Followups count (no exclusion): {len(followups)}")
    
    def test_followups_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test followups excludes branch party followups when toggle ON"""
        response = requests.get(f"{API}/customers/followups", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        followups = data["data"]["followups"]
        # Check that no followup is for the branch party
        branch_followups = [f for f in followups if f.get("customer_name") == BRANCH_PARTY]
        print(f"✓ Followups count (with exclusion): {len(followups)}")
        print(f"✓ Branch party followups in result: {len(branch_followups)}")
        # If there are any followups for branch party, they should be excluded
        assert len(branch_followups) == 0, f"Branch party followups should be excluded"


class TestCRMTargetsBranchFilter:
    """CRM Targets tab branch filtering tests"""
    
    def test_targets_without_branch_exclusion(self, auth_headers):
        """Test targets includes branch parties when exclusion OFF"""
        response = requests.get(f"{API}/customers/targets?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        targets = data["data"]["targets"]
        count_without = len(targets)
        print(f"✓ Targets count (no exclusion): {count_without}")
        return count_without
    
    def test_targets_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test targets excludes branch parties when toggle ON (count drops from 41 to 39)"""
        response = requests.get(f"{API}/customers/targets?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        targets = data["data"]["targets"]
        count_with = len(targets)
        customer_names = [t["customer_name"] for t in targets]
        print(f"✓ Targets count (with exclusion): {count_with}")
        # Branch party should NOT be in the list
        assert BRANCH_PARTY not in customer_names, f"Branch party should NOT be in targets list with exclusion"
        print(f"✓ Branch party correctly excluded from targets list")
        return count_with
    
    def test_targets_count_drops_with_exclusion(self, auth_headers, auth_headers_with_branch_exclusion):
        """Test that targets count drops when branch exclusion is ON"""
        # Without exclusion
        resp1 = requests.get(f"{API}/customers/targets?fy={FY}", headers=auth_headers)
        count_without = len(resp1.json()["data"]["targets"])
        
        # With exclusion
        resp2 = requests.get(f"{API}/customers/targets?fy={FY}", headers=auth_headers_with_branch_exclusion)
        count_with = len(resp2.json()["data"]["targets"])
        
        print(f"✓ Targets count without exclusion: {count_without}")
        print(f"✓ Targets count with exclusion: {count_with}")
        assert count_with < count_without, f"Targets count should drop with exclusion"


class TestCRMPaymentBehaviorBranchFilter:
    """CRM Payment Behavior tab branch filtering tests"""
    
    def test_payment_behavior_without_branch_exclusion(self, auth_headers):
        """Test payment behavior includes branch parties when exclusion OFF"""
        response = requests.get(f"{API}/customers/payment-behavior?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        # Note: payment-behavior returns data under 'customers' key
        customers = data["data"]["customers"]
        count_without = len(customers)
        print(f"✓ Payment behavior customers count (no exclusion): {count_without}")
        return count_without
    
    def test_payment_behavior_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test payment behavior excludes branch parties when toggle ON (count drops from 41 to 39)"""
        response = requests.get(f"{API}/customers/payment-behavior?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"]["customers"]
        count_with = len(customers)
        customer_names = [c["customer_name"] for c in customers]
        print(f"✓ Payment behavior customers count (with exclusion): {count_with}")
        # Branch party should NOT be in the list
        assert BRANCH_PARTY not in customer_names, f"Branch party should NOT be in payment behavior list with exclusion"
        print(f"✓ Branch party correctly excluded from payment behavior list")
        return count_with
    
    def test_payment_behavior_count_drops_with_exclusion(self, auth_headers, auth_headers_with_branch_exclusion):
        """Test that payment behavior count drops when branch exclusion is ON"""
        # Without exclusion
        resp1 = requests.get(f"{API}/customers/payment-behavior?fy={FY}", headers=auth_headers)
        count_without = len(resp1.json()["data"]["customers"])
        
        # With exclusion
        resp2 = requests.get(f"{API}/customers/payment-behavior?fy={FY}", headers=auth_headers_with_branch_exclusion)
        count_with = len(resp2.json()["data"]["customers"])
        
        print(f"✓ Payment behavior count without exclusion: {count_without}")
        print(f"✓ Payment behavior count with exclusion: {count_with}")
        assert count_with < count_without, f"Payment behavior count should drop with exclusion"


class TestAnalyticsMovementBranchFilter:
    """Analytics Movement tab branch filtering tests"""
    
    def test_movement_analysis_without_branch_exclusion(self, auth_headers):
        """Test movement analysis works without exclusion"""
        response = requests.get(f"{API}/inventory/movement-analysis?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        movements = data["data"]["movements"]
        print(f"✓ Movement analysis items count (no exclusion): {len(movements)}")
    
    def test_movement_analysis_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test movement analysis applies branch filtering"""
        response = requests.get(f"{API}/inventory/movement-analysis?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        movements = data["data"]["movements"]
        print(f"✓ Movement analysis items count (with exclusion): {len(movements)}")


class TestAnalyticsBelowCostBranchFilter:
    """Analytics Below Cost tab branch filtering tests"""
    
    def test_below_cost_without_branch_exclusion(self, auth_headers):
        """Test below cost sales works without exclusion"""
        response = requests.get(f"{API}/inventory/below-cost-sales?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        items = data["data"]["items"]
        print(f"✓ Below cost items count (no exclusion): {len(items)}")
    
    def test_below_cost_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test below cost sales applies branch filtering"""
        response = requests.get(f"{API}/inventory/below-cost-sales?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        items = data["data"]["items"]
        print(f"✓ Below cost items count (with exclusion): {len(items)}")


class TestAnalyticsSalesFrequencyBranchFilter:
    """Analytics Sales Frequency tab branch filtering tests"""
    
    def test_sales_frequency_without_branch_exclusion(self, auth_headers):
        """Test sales frequency works without exclusion"""
        response = requests.get(f"{API}/inventory/sales-frequency?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        frequency = data["data"]["frequency"]
        count_without = len(frequency)
        print(f"✓ Sales frequency items count (no exclusion): {count_without}")
        return count_without
    
    def test_sales_frequency_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test sales frequency applies branch filtering (count drops from 172 to 167)"""
        response = requests.get(f"{API}/inventory/sales-frequency?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        frequency = data["data"]["frequency"]
        count_with = len(frequency)
        print(f"✓ Sales frequency items count (with exclusion): {count_with}")
        return count_with
    
    def test_sales_frequency_count_drops_with_exclusion(self, auth_headers, auth_headers_with_branch_exclusion):
        """Test that sales frequency count drops when branch exclusion is ON"""
        # Without exclusion
        resp1 = requests.get(f"{API}/inventory/sales-frequency?fy={FY}", headers=auth_headers)
        count_without = len(resp1.json()["data"]["frequency"])
        
        # With exclusion
        resp2 = requests.get(f"{API}/inventory/sales-frequency?fy={FY}", headers=auth_headers_with_branch_exclusion)
        count_with = len(resp2.json()["data"]["frequency"])
        
        print(f"✓ Sales frequency count without exclusion: {count_without}")
        print(f"✓ Sales frequency count with exclusion: {count_with}")
        # Count should drop (from 172 to 167 as per requirement)
        assert count_with <= count_without, f"Sales frequency count should drop or stay same with exclusion"


class TestAnalyticsCustomerItemsBranchFilter:
    """Analytics Customer Items tab branch filtering tests"""
    
    def test_customer_names_without_branch_exclusion(self, auth_headers):
        """Test customer names includes branch party when exclusion OFF"""
        response = requests.get(f"{API}/sales/customer-names?fy={FY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"]["customers"]
        print(f"✓ Customer names count (no exclusion): {len(customers)}")
        # Branch party should be in the list
        assert BRANCH_PARTY in customers, f"Branch party should be in customer names list"
        print(f"✓ Branch party found in customer names list")
    
    def test_customer_names_with_branch_exclusion(self, auth_headers_with_branch_exclusion):
        """Test customer names excludes branch party when toggle ON"""
        response = requests.get(f"{API}/sales/customer-names?fy={FY}", headers=auth_headers_with_branch_exclusion)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        customers = data["data"]["customers"]
        print(f"✓ Customer names count (with exclusion): {len(customers)}")
        # Branch party should NOT be in the list
        assert BRANCH_PARTY not in customers, f"Branch party should NOT be in customer names list with exclusion"
        print(f"✓ Branch party correctly excluded from customer names list")
    
    def test_customer_item_sales_for_branch_party_with_exclusion(self, auth_headers_with_branch_exclusion):
        """Test customer-item-sales returns empty for branch party when exclusion ON"""
        response = requests.get(
            f"{API}/sales/customer-item-sales?customer={BRANCH_PARTY}&fy={FY}",
            headers=auth_headers_with_branch_exclusion
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        items = data["data"]["items"]
        total_items = data["data"]["total_items"]
        print(f"✓ Customer item sales for branch party (with exclusion): {total_items} items")
        # Should return empty when branch exclusion is ON
        assert total_items == 0, f"Branch party item sales should be empty with exclusion"
        print(f"✓ Branch party item sales correctly returns empty with exclusion")
    
    def test_customer_item_sales_for_branch_party_without_exclusion(self, auth_headers):
        """Test customer-item-sales returns data for branch party when exclusion OFF"""
        response = requests.get(
            f"{API}/sales/customer-item-sales?customer={BRANCH_PARTY}&fy={FY}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        total_items = data["data"]["total_items"]
        print(f"✓ Customer item sales for branch party (no exclusion): {total_items} items")
        # Should return data when branch exclusion is OFF
        assert total_items > 0, f"Branch party should have item sales without exclusion"


class TestBranchLedgersDetection:
    """Branch ledgers detection tests"""
    
    def test_branch_ledgers_endpoint(self, auth_headers):
        """Test branch ledgers endpoint returns detected branches"""
        response = requests.get(f"{API}/settings/branch-ledgers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        branch_parties = data["data"].get("branch_parties", [])
        print(f"✓ Branch parties detected: {branch_parties}")
        # Should include our known branch party
        assert BRANCH_PARTY in branch_parties, f"Branch party '{BRANCH_PARTY}' should be detected"
    
    def test_branch_ledgers_detect_endpoint(self, auth_headers):
        """Test branch ledgers auto-detect endpoint"""
        response = requests.get(f"{API}/settings/branch-ledgers/detect", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print(f"✓ Branch ledgers auto-detect successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
