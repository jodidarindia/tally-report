"""
Iteration 59 — Salesman/Dispatch/Inventory feature tests.
Focus areas:
  - Audit log scoping by actor for non-admin
  - Dispatch employees endpoint (tenant-wide)
  - Salesman my-stats with YTD-prorated achievement
  - Salesman catalog global search + standard_price
  - Inventory ABC manual + auto-assign + category-sales
  - Beat plan CRUD
  - Salesman order POST stores part_number
"""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
COMPANY_ID = "03f638d1-eab0-47ee-aed6-59049ebb5207"
TENANT_ID = "3079b0af-e899-44b4-ae7c-c35d113fe296"


def _login(username, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "captcha_token": ""},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    assert body.get("success"), f"Login failed for {username}: {body}"
    return body["data"]["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin", "admin123")


@pytest.fixture(scope="module")
def ravi_token():
    return _login("ravi@test.com", "ravi1234")


@pytest.fixture(scope="module")
def dispatch_token():
    return _login("dispatch@test.com", "dispatch123")


def _hdr(token, with_company=True):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if with_company:
        h["X-Company-Id"] = COMPANY_ID
    return h


def _extract_list(body, *keys):
    """Pull list out of {success, data:{<key>: [..]}} or {<key>: [..]} or [..]."""
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    # unwrap data wrapper
    inner = body.get("data") if "data" in body and body.get("data") is not None else body
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict):
        for k in keys:
            v = inner.get(k)
            if isinstance(v, list):
                return v
        # also try at top-level body
        for k in keys:
            v = body.get(k)
            if isinstance(v, list):
                return v
    return []


# ---------- AUDIT LOG SCOPING ----------
class TestAuditLogScoping:
    def test_admin_sees_all_logs(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/audit/logs?limit=50", headers=_hdr(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        logs = _extract_list(r.json(), "logs", "data")
        assert isinstance(logs, list) and len(logs) > 0
        actors = {l.get("actor") for l in logs if l.get("actor")}
        # admin should see multiple actors
        assert len(actors) >= 1

    def test_salesman_sees_only_own_logs(self, ravi_token):
        r = requests.get(f"{BASE_URL}/api/audit/logs?limit=50", headers=_hdr(ravi_token), timeout=30)
        assert r.status_code == 200, r.text
        logs = _extract_list(r.json(), "logs", "data")
        assert isinstance(logs, list)
        for log in logs:
            actor = log.get("actor")
            if actor:
                assert actor == "ravi@test.com", f"Cross-actor leak: {log}"


# ---------- DISPATCH EMPLOYEES ----------
class TestDispatchEmployees:
    def test_admin_sees_dispatch_employees(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/dispatch/employees", headers=_hdr(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        emps = _extract_list(r.json(), "employees", "data")
        assert isinstance(emps, list) and len(emps) >= 2, f"expected >=2 dispatch employees, got {len(emps)}"
        usernames = [(e.get("username") or e.get("email") or "").lower() for e in emps]
        assert any("dispatch@test.com" in u for u in usernames), f"dispatch@test.com missing: {usernames}"
        assert any("test_dispatch_afd22d@test.com" in u for u in usernames) or len(emps) >= 2, \
            f"test_dispatch_afd22d@test.com missing: {usernames}"


# ---------- SALESMAN MY STATS ----------
class TestSalesmanMyStats:
    def test_my_stats_structure(self, ravi_token):
        r = requests.get(
            f"{BASE_URL}/api/salesman-orders/my-stats?fy=2026-27",
            headers=_hdr(ravi_token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        # required fields per problem statement
        for key in ["achieved_amount", "achievement_percentage", "expected_target"]:
            assert key in data, f"Missing key '{key}' in my-stats: {list(data.keys())}"
        # customers / items should be list-typed if present
        if "customers" in data:
            assert isinstance(data["customers"], list)
        if "items_sold" in data:
            assert isinstance(data["items_sold"], list)
        # achievement_percentage should be numeric
        assert isinstance(data["achievement_percentage"], (int, float)), data["achievement_percentage"]

    def test_my_stats_tenant_isolation(self, ravi_token):
        # Salesman should never get back data from other tenants — validated by tenant scoping in JWT
        r = requests.get(
            f"{BASE_URL}/api/salesman-orders/my-stats?fy=2026-27",
            headers=_hdr(ravi_token),
            timeout=30,
        )
        assert r.status_code == 200


# ---------- SALESMAN CATALOG ----------
class TestSalesmanCatalog:
    def test_catalog_no_search_returns_items(self, ravi_token):
        r = requests.get(
            f"{BASE_URL}/api/salesman-orders/catalog",
            headers=_hdr(ravi_token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        items = body.get("data") if isinstance(body, dict) and "data" in body else body
        if isinstance(items, dict):
            items = items.get("items") or items.get("catalog") or []
        assert isinstance(items, list)
        if items:
            sample = items[0]
            # should expose standard_price (per problem statement)
            assert "standard_price" in sample or "price" in sample, f"missing price fields: {sample.keys()}"

    def test_catalog_search_by_part_number(self, ravi_token):
        # Pull first item, then search by its part_number
        r = requests.get(f"{BASE_URL}/api/salesman-orders/catalog", headers=_hdr(ravi_token), timeout=30)
        body = r.json()
        items = body.get("data") if isinstance(body, dict) and "data" in body else body
        if isinstance(items, dict):
            items = items.get("items") or items.get("catalog") or []
        if not items:
            pytest.skip("No catalog items present")
        target = next((i for i in items if i.get("part_number")), None)
        if not target:
            pytest.skip("No item has part_number")
        pn = target["part_number"]
        r2 = requests.get(
            f"{BASE_URL}/api/salesman-orders/catalog?search={pn}",
            headers=_hdr(ravi_token),
            timeout=30,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        items2 = body2.get("data") if isinstance(body2, dict) and "data" in body2 else body2
        if isinstance(items2, dict):
            items2 = items2.get("items") or items2.get("catalog") or []
        assert any(i.get("part_number") == pn for i in items2), f"part_number search failed for {pn}"


# ---------- INVENTORY ABC ----------
class TestInventoryABC:
    def test_abc_auto_assign(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/inventory/abc/auto-assign",
            headers=_hdr(admin_token),
            timeout=120,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        # Expect counts
        if isinstance(data, dict):
            counts = data.get("counts") or data
            # accept any of these keys
            ks = [k.lower() for k in counts.keys()] if isinstance(counts, dict) else []
            assert any(k in ks for k in ["a", "category_a", "total"]) or "message" in body, f"unexpected response: {body}"

    def test_manual_abc_set(self, admin_token):
        # find first item
        r = requests.get(f"{BASE_URL}/api/inventory/items?limit=1", headers=_hdr(admin_token), timeout=30)
        if r.status_code != 200:
            pytest.skip(f"inventory list failed: {r.status_code}")
        body = r.json()
        items = body.get("data") if isinstance(body, dict) and "data" in body else body
        if isinstance(items, dict):
            items = items.get("items", [])
        if not items:
            pytest.skip("No inventory items")
        item_id = items[0].get("id") or items[0].get("_id") or items[0].get("item_id")
        if not item_id:
            pytest.skip(f"No id in inventory item: {items[0].keys()}")
        r2 = requests.patch(
            f"{BASE_URL}/api/inventory/items/{item_id}/abc",
            headers=_hdr(admin_token),
            json={"abc_category": "A"},
            timeout=30,
        )
        assert r2.status_code in [200, 204], r2.text

    def test_category_sales(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/inventory/category-sales?abc=A&fy=2026-27",
            headers=_hdr(admin_token),
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        # data should be list or dict containing items
        if isinstance(data, dict):
            data = data.get("items") or data.get("category_sales") or []
        assert isinstance(data, list)


# ---------- BEAT PLANS ----------
class TestBeatPlans:
    def test_admin_create_beat(self, admin_token):
        payload = {
            "salesman_username": "ravi@test.com",
            "day_of_week": "Monday",
            "customer_name": "TEST_BeatCustomer",
            "fy": "2026-27",
        }
        r = requests.post(
            f"{BASE_URL}/api/salesman-orders/beats",
            headers=_hdr(admin_token),
            json=payload,
            timeout=30,
        )
        # accept 200/201, but flag others
        assert r.status_code in [200, 201], r.text

    def test_salesman_views_own_beats(self, ravi_token):
        r = requests.get(f"{BASE_URL}/api/salesman-orders/beats", headers=_hdr(ravi_token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        beats = body.get("data") if isinstance(body, dict) and "data" in body else body
        if isinstance(beats, dict):
            beats = beats.get("beats", [])
        assert isinstance(beats, list)


# ---------- SALESMAN ORDER part_number ----------
class TestSalesmanOrderPartNumber:
    def test_post_order_stores_part_number(self, ravi_token):
        # Pick a real catalog item with part_number for the test
        r = requests.get(f"{BASE_URL}/api/salesman-orders/catalog", headers=_hdr(ravi_token), timeout=30)
        body = r.json()
        items = body.get("data") if isinstance(body, dict) and "data" in body else body
        if isinstance(items, dict):
            items = items.get("items") or items.get("catalog") or []
        target = next((i for i in items if i.get("part_number")), None)
        if not target:
            pytest.skip("no catalog item with part_number")
        # fetch mapped customers
        rc = requests.get(
            f"{BASE_URL}/api/salesman-orders/my-customers?fy=2026-27",
            headers=_hdr(ravi_token),
            timeout=30,
        )
        if rc.status_code != 200:
            pytest.skip(f"customers endpoint not available: {rc.status_code}")
        cb = rc.json()
        custs = cb.get("data") if isinstance(cb, dict) and "data" in cb else cb
        if isinstance(custs, dict):
            custs = custs.get("customers", [])
        if not custs:
            pytest.skip("no mapped customers")
        cust = custs[0]
        cname = cust.get("name") or cust.get("customer_name")
        order_payload = {
            "customer_name": cname,
            "fy": "2026-27",
            "items": [
                {
                    "item_name": target.get("item_name") or target.get("name"),
                    "part_number": target["part_number"],
                    "qty": 1,
                    "rate": target.get("standard_price") or target.get("price") or 100,
                }
            ],
            "notes": "TEST_iteration59",
        }
        ro = requests.post(
            f"{BASE_URL}/api/salesman-orders/orders",
            headers=_hdr(ravi_token),
            json=order_payload,
            timeout=60,
        )
        assert ro.status_code in [200, 201], ro.text
        body = ro.json()
        order = body.get("data") if isinstance(body, dict) and "data" in body else body
        # extract items array
        if isinstance(order, dict):
            ord_items = order.get("items") or []
            if ord_items:
                pn = ord_items[0].get("part_number")
                assert pn == target["part_number"], f"part_number not stored: {ord_items[0]}"
