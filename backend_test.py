#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class TallyAPITester:
    def __init__(self, base_url="https://tally-report-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - {name}")
                try:
                    response_data = response.json()
                    if response_data.get('success'):
                        print(f"   Response: Success")
                    else:
                        print(f"   Response: {response_data.get('error', 'Unknown error')}")
                except:
                    print(f"   Response: Non-JSON response")
            else:
                self.tests_passed += 0
                self.failed_tests.append({
                    'name': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'url': url
                })
                print(f"❌ FAILED - {name}")
                print(f"   Expected: {expected_status}, Got: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Raw response: {response.text[:200]}")

            return success, response.json() if response.headers.get('content-type', '').startswith('application/json') else {}

        except requests.exceptions.Timeout:
            print(f"❌ FAILED - {name} (Timeout after {timeout}s)")
            self.failed_tests.append({
                'name': name,
                'error': 'Timeout',
                'url': url
            })
            return False, {}
        except Exception as e:
            print(f"❌ FAILED - {name} (Error: {str(e)})")
            self.failed_tests.append({
                'name': name,
                'error': str(e),
                'url': url
            })
            return False, {}

    def test_tally_connection(self):
        """Test Tally connection endpoints"""
        print("\n" + "="*50)
        print("TESTING TALLY CONNECTION ENDPOINTS")
        print("="*50)
        
        # Test connection status
        self.run_test(
            "Get Tally Status",
            "GET",
            "tally/status",
            200
        )
        
        # Test XML connection
        self.run_test(
            "Connect Tally XML",
            "POST",
            "tally/connect",
            200,
            data={
                "connection_type": "xml",
                "host": "localhost",
                "port": 9000
            }
        )

    def test_inventory_endpoints(self):
        """Test inventory-related endpoints"""
        print("\n" + "="*50)
        print("TESTING INVENTORY ENDPOINTS")
        print("="*50)
        
        # Test get inventory items
        self.run_test(
            "Get Inventory Items",
            "GET",
            "inventory/items",
            200
        )
        
        # Test inventory summary
        self.run_test(
            "Get Inventory Summary",
            "GET",
            "inventory/summary",
            200
        )
        
        # Test inventory with category filter
        self.run_test(
            "Get Inventory Items with Category Filter",
            "GET",
            "inventory/items?category=Electronics",
            200
        )

    def test_sales_endpoints(self):
        """Test sales-related endpoints"""
        print("\n" + "="*50)
        print("TESTING SALES ENDPOINTS")
        print("="*50)
        
        # Test get sales vouchers
        self.run_test(
            "Get Sales Vouchers",
            "GET",
            "sales/vouchers",
            200
        )
        
        # Test sales summary
        self.run_test(
            "Get Sales Summary",
            "GET",
            "sales/summary",
            200
        )
        
        # Test sales analytics
        self.run_test(
            "Get Sales Analytics",
            "GET",
            "sales/analytics",
            200
        )
        
        # Test sales with party filter
        self.run_test(
            "Get Sales Vouchers with Party Filter",
            "GET",
            "sales/vouchers?party_name=Tech",
            200
        )

    def test_ai_endpoints(self):
        """Test AI query endpoints"""
        print("\n" + "="*50)
        print("TESTING AI ENDPOINTS")
        print("="*50)
        
        # Test AI query
        success, response = self.run_test(
            "AI Query Processing",
            "POST",
            "ai/query",
            200,
            data={"query": "What are the top selling items?"},
            timeout=60  # AI queries may take longer
        )
        
        if success:
            print("   AI query processed successfully")
        else:
            print("   AI query failed - this may indicate LLM integration issues")

    def test_export_endpoints(self):
        """Test export functionality"""
        print("\n" + "="*50)
        print("TESTING EXPORT ENDPOINTS")
        print("="*50)
        
        # Test CSV export
        self.run_test(
            "Export Inventory CSV",
            "POST",
            "reports/export",
            200,
            data={"report_type": "inventory", "format": "csv"}
        )
        
        # Test Excel export
        self.run_test(
            "Export Sales Excel",
            "POST",
            "reports/export",
            200,
            data={"report_type": "sales", "format": "excel"}
        )
        
        # Test PDF export
        self.run_test(
            "Export Inventory PDF",
            "POST",
            "reports/export",
            200,
            data={"report_type": "inventory", "format": "pdf"}
        )

    def test_history_endpoints(self):
        """Test report history endpoints"""
        print("\n" + "="*50)
        print("TESTING HISTORY ENDPOINTS")
        print("="*50)
        
        # Test get report history
        self.run_test(
            "Get Report History",
            "GET",
            "reports/history",
            200
        )

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Tally SaaS Report Builder API Tests")
        print(f"📍 Base URL: {self.base_url}")
        print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all test suites
        self.test_tally_connection()
        self.test_inventory_endpoints()
        self.test_sales_endpoints()
        self.test_ai_endpoints()
        self.test_export_endpoints()
        self.test_history_endpoints()
        
        # Print final results
        print("\n" + "="*60)
        print("FINAL TEST RESULTS")
        print("="*60)
        print(f"📊 Tests Run: {self.tests_run}")
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ FAILED TESTS:")
            for test in self.failed_tests:
                print(f"   • {test['name']}")
                if 'expected' in test:
                    print(f"     Expected: {test['expected']}, Got: {test['actual']}")
                if 'error' in test:
                    print(f"     Error: {test['error']}")
                print(f"     URL: {test['url']}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = TallyAPITester()
    success = tester.run_all_tests()
    
    print(f"\n🏁 Testing completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())