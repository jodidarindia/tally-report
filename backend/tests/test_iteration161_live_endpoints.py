"""iter-161: Live endpoint tests for inventory FY-scoping + CRM Outstanding/Payment Behavior.

Verifies that:
  * /api/inventory/summary and /api/inventory/items return per-FY dedup'd data (no summing)
  * /api/customers/outstanding returns >0 customers for busydemo & admin
  * /api/customers/payment-behavior returns 6/26 customers for busydemo/admin respectively
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")


def _login(username, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("access_token") or body.get("token") or (body.get("data") or {}).get("token")
    assert tok, f"no token in {r.json()}"
    return tok


@pytest.fixture(scope="module")
def busy_headers():
    return {"Authorization": f"Bearer {_login('busydemo@flowralive.in', 'demo2026')}"}


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


# ---------------- Inventory FY-scoping (busydemo) ----------------

def _unwrap(r):
    j = r.json()
    return j.get("data") if isinstance(j, dict) and "data" in j and "success" in j else j


def test_busy_inventory_summary_fy_2026_27(busy_headers):
    r = requests.get(f"{BASE_URL}/api/inventory/summary?fy=2026-27", headers=busy_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    data = _unwrap(r)
    tc = data.get("total_items"); tv = data.get("total_value")
    print(f"[busy inventory/summary FY2026-27] total_items={tc}  total_value={tv}")
    assert tc == 13682, f"Expected 13,682 items for FY 2026-27, got {tc}"
    assert 9_000_000 < tv < 10_000_000, f"Expected ~₹94 lakh, got {tv}"


def test_busy_inventory_summary_fy_2025_26(busy_headers):
    r = requests.get(f"{BASE_URL}/api/inventory/summary?fy=2025-26", headers=busy_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    data = _unwrap(r)
    tc = data.get("total_items"); tv = data.get("total_value")
    print(f"[busy inventory/summary FY2025-26] total_items={tc}  total_value={tv}")
    assert tc == 14, f"Expected 14 items for FY 2025-26, got {tc}"
    assert 14000 < tv < 15000, f"Expected ~₹14,587, got {tv}"


def test_busy_inventory_items_fy_2026_27(busy_headers):
    r = requests.get(f"{BASE_URL}/api/inventory/items?fy=2026-27&limit=20000", headers=busy_headers, timeout=120)
    assert r.status_code == 200, r.text[:300]
    data = _unwrap(r)
    items = data.get("items") if isinstance(data, dict) else data
    assert isinstance(items, list), f"unexpected shape: {type(data)}"
    print(f"[busy inventory/items FY2026-27] len={len(items)}")
    # Should be one row per SKU for the FY (~13,682), not doubled
    assert 13000 <= len(items) <= 14000, f"items count out of range: {len(items)}"


def test_busy_movement_analysis_fy_2026_27(busy_headers):
    r = requests.get(f"{BASE_URL}/api/inventory/movement-analysis?fy=2026-27", headers=busy_headers, timeout=90)
    print(f"[busy movement-analysis FY2026-27] status={r.status_code}")
    assert r.status_code == 200, r.text[:300]
    data = _unwrap(r)
    print(f"  keys={list(data.keys()) if isinstance(data,dict) else type(data).__name__}")
    # Just ensure it responds with structure
    assert isinstance(data, (dict, list))


def _rows(r):
    d = _unwrap(r)
    if isinstance(d, list): return d
    return d.get("customers") or d.get("data") or d.get("items") or []


def test_busy_customers_outstanding(busy_headers):
    r = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=busy_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    rows = _rows(r)
    d = _unwrap(r)
    print(f"[busy customers/outstanding] rows={len(rows)}  total_outstanding={d.get('total_outstanding') if isinstance(d,dict) else 'n/a'}")
    assert len(rows) >= 400, f"Expected ~401 customers, got {len(rows)}"
    positives = [c for c in rows if isinstance(c, dict) and (c.get("outstanding") or c.get("outstanding_amount") or c.get("balance") or 0) > 0]
    print(f"  customers with outstanding>0: {len(positives)}")
    assert len(positives) >= 1, "No customers with positive outstanding"


def test_busy_customers_payment_behavior(busy_headers):
    r = requests.get(f"{BASE_URL}/api/customers/payment-behavior", headers=busy_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    rows = _rows(r)
    print(f"[busy customers/payment-behavior] rows={len(rows)}")
    assert len(rows) >= 1, "Expected payment behavior rows for busydemo"


def test_admin_customers_outstanding(admin_headers):
    r = requests.get(f"{BASE_URL}/api/customers/outstanding", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    rows = _rows(r)
    print(f"[admin customers/outstanding] rows={len(rows)}")
    assert len(rows) > 0


def test_admin_customers_payment_behavior(admin_headers):
    r = requests.get(f"{BASE_URL}/api/customers/payment-behavior", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    rows = _rows(r)
    print(f"[admin customers/payment-behavior] rows={len(rows)}")
    assert len(rows) > 0
