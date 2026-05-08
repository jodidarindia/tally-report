"""Regression tests for iteration 65: SuperAdmin parity with modern UserAdmin.

Covers:
- Customer Health endpoint counts ALL non-admin staff (employee + dispatch + salesman)
  — was under-counting tenants without legacy `role:employee` users.
- Health endpoint exposes per-module counts for parity with current features
  (purchases, receipts, credit notes, beat_runs, salesman_orders, dispatch_cards).
- /super-admin/admins employee_count uses the same broadened roles.
- /super-admin/stats total_employees uses the same broadened roles.
"""
import os
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


def _login(u, p):
    r = requests.post(f"{API_URL}/api/auth/login",
                      json={"username": u, "password": p, "captcha_token": ""})
    r.raise_for_status()
    return r.json()["data"]["token"]


def test_customer_health_counts_all_staff_roles():
    h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    r = requests.get(f"{API_URL}/api/super-admin/customer-health", headers=h).json()
    assert r["success"] is True
    customers = r["data"]["customers"]
    asa = next((c for c in customers if c["username"] == "admin"), None)
    assert asa is not None, "Expected to find seeded admin tenant"
    # ASA tenant has 3 salesmen + 2 dispatch staff
    assert asa["employee_count"] >= 5, f"Expected >=5 staff, got {asa['employee_count']}"
    sb = asa.get("staff_breakdown", {})
    # Breakdown must surface salesman + dispatch separately
    assert sb.get("salesman", 0) >= 1
    assert sb.get("dispatch", 0) >= 1


def test_customer_health_module_coverage_fields():
    """Every modern UserAdmin module count is exposed."""
    h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    r = requests.get(f"{API_URL}/api/super-admin/customer-health", headers=h).json()
    customers = r["data"]["customers"]
    assert customers, "Expected at least one tenant"
    sample = customers[0]
    expected_fields = [
        "inventory_items", "sales_vouchers", "purchase_vouchers", "receipts",
        "credit_notes", "customers", "beat_runs", "salesman_orders",
        "dispatch_cards", "staff_breakdown", "agent_version",
    ]
    for f in expected_fields:
        assert f in sample, f"Missing parity field `{f}` on health row"


def test_admins_endpoint_employee_count_includes_all_roles():
    h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    r = requests.get(f"{API_URL}/api/super-admin/admins", headers=h).json()
    asa = next((a for a in r["data"]["admins"] if a["username"] == "admin"), None)
    assert asa is not None
    assert asa["employee_count"] >= 5, \
        f"admins.employee_count should include salesman+dispatch, got {asa['employee_count']}"


def test_stats_total_employees_includes_all_roles():
    h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    r = requests.get(f"{API_URL}/api/super-admin/stats", headers=h).json()
    assert r["success"] is True
    # 5 staff in ASA tenant should at least be counted here
    assert r["data"]["total_employees"] >= 5
