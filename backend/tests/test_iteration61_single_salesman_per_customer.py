"""Regression tests for single-salesman-per-customer enforcement (Manage Salesmen)."""
import os
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


def _login(u, p):
    r = requests.post(f"{API_URL}/api/auth/login",
                      json={"username": u, "password": p, "captcha_token": ""})
    r.raise_for_status()
    return r.json()["data"]["token"]


def test_customer_ownership_endpoint():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/salesman/customer-ownership?fy=2026-27", headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    assert "ownership" in d and isinstance(d["ownership"], dict)
    assert d["fy"] == "2026-27"
    # All keys are lower-cased customer names; values are owner salesman names
    for k, v in d["ownership"].items():
        assert k == k.lower()
        assert isinstance(v, str) and v


def test_cannot_map_already_owned_customer():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}",
         "Content-Type": "application/json"}
    own = requests.get(f"{API_URL}/api/salesman/customer-ownership?fy=2026-27", headers=h).json()["data"]["ownership"]
    if not own:
        # Skip if no current mappings — environment-dependent
        return
    mapped_customer = next(iter(own))
    current_owner = own[mapped_customer]
    # Attempt to map this customer to a brand-new salesman
    r = requests.post(f"{API_URL}/api/salesman/master", headers=h, json={
        "salesman_name": "PYTEST_CONFLICT_TARGET",
        "phone": "", "email": "",
        "monthly_target": 0, "quarterly_target": 0,
        "customers": [mapped_customer],
        "fy": "2026-27",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "already assigned" in body["error"].lower()
    assert body["data"]["conflicts"][0]["owner"] == current_owner


def test_can_re_save_same_salesman_with_existing_customers():
    """Editing the same salesman with their already-mapped customers must succeed."""
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}",
         "Content-Type": "application/json"}
    # Find Ravi Kumar's current customer (Ankit Automobiles Indore)
    own = requests.get(f"{API_URL}/api/salesman/customer-ownership?fy=2026-27", headers=h).json()["data"]["ownership"]
    ravis = [c for c, o in own.items() if o == "Ravi Kumar"]
    if not ravis:
        return  # nothing to test against
    cust = ravis[0]
    # Re-save Ravi Kumar with the SAME customer — should succeed
    r = requests.post(f"{API_URL}/api/salesman/master", headers=h, json={
        "salesman_name": "Ravi Kumar",
        "phone": "", "email": "",
        "monthly_target": 100000, "quarterly_target": 300000,
        "customers": [cust.title()],  # title-case to test case-insensitive match
        "fy": "2026-27",
    })
    body = r.json()
    assert body["success"] is True, f"Expected success, got: {body}"
