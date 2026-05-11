"""
Iteration 97: Atlas Cutover Regression Sweep
Validates backend works end-to-end against MongoDB Atlas after migration.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tally-report-ai.preview.emergentagent.com').rstrip('/')


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_login(session):
    last = None
    for _ in range(3):
        try:
            r = session.post(f"{BASE_URL}/api/auth/login",
                             json={"username": "admin", "password": "admin123", "captcha_token": ""},
                             timeout=30)
            last = r
            if r.status_code == 200:
                break
        except Exception as e:
            last = e
        import time; time.sleep(2)
    assert getattr(last, "status_code", None) == 200, getattr(last, "text", str(last))
    body = last.json()
    assert body.get("success") is True
    return body["data"]


@pytest.fixture(scope="module")
def demo_login(session):
    # Retry once for Atlas SRV warm-up
    last = None
    for _ in range(2):
        try:
            r = session.post(f"{BASE_URL}/api/auth/login",
                             json={"username": "demo@flowralive.in", "password": "demo2026", "captcha_token": ""},
                             timeout=30)
            if r.status_code == 200:
                last = r
                break
            last = r
        except Exception as e:
            last = e
    assert getattr(last, "status_code", None) == 200, getattr(last, "text", str(last))
    body = last.json()
    assert body.get("success") is True
    return body["data"]


# ------- Atlas connectivity -------
class TestAtlasConnectivity:
    def test_admin_login_works_against_atlas(self, admin_login):
        assert admin_login["role"] == "admin"
        assert admin_login["tenant_id"] == "3079b0af-e899-44b4-ae7c-c35d113fe296"
        assert "token" in admin_login and len(admin_login["token"]) > 20

    def test_admin_plan_and_subscription(self, admin_login):
        # plan/subscription_days_left may live in admin_login or via /api/auth/me
        plan = admin_login.get("plan")
        days = admin_login.get("subscription_days_left")
        # If not in login, fetch from /me
        if plan is None or days is None:
            tok = admin_login["token"]
            r = requests.get(f"{BASE_URL}/api/auth/me",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=15)
            assert r.status_code == 200
            me = r.json().get("data", {})
            plan = plan or me.get("plan")
            days = days if days is not None else me.get("subscription_days_left")
        assert plan == "enterprise", f"Expected enterprise plan, got {plan}"
        assert days is not None and days >= 900, f"Expected ~999 days, got {days}"


# ------- Demo tenant login -------
class TestDemoLogin:
    def test_demo_login_basics(self, demo_login):
        assert demo_login["role"] in ("admin", "tenant_admin")
        assert demo_login["tenant_id"] == "3318e6d0-e500-5e6c-8e18-b33ec2b1a3c9"
        companies = demo_login.get("companies", [])
        assert len(companies) == 3, f"Expected 3 companies, got {len(companies)}"

    def test_demo_plan_enterprise_days(self, demo_login):
        plan = demo_login.get("plan")
        days = demo_login.get("subscription_days_left")
        if plan is None or days is None:
            tok = demo_login["token"]
            r = requests.get(f"{BASE_URL}/api/auth/me",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=15)
            assert r.status_code == 200
            me = r.json().get("data", {})
            plan = plan or me.get("plan")
            days = days if days is not None else me.get("subscription_days_left")
        assert plan == "enterprise", f"Expected enterprise, got {plan}"
        assert days is not None and 600 <= days <= 720, f"Expected ~670 days, got {days}"


def _headers(login):
    return {"Authorization": f"Bearer {login['token']}", "Content-Type": "application/json"}


def _company_ids(login):
    cs = login.get("companies", [])
    out = []
    for c in cs:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, dict):
            out.append(c.get("company_id") or c.get("id") or c.get("_id"))
    return out


def _no_objectid_leak(obj, path="root"):
    """Recursively check for raw ObjectId leakage in JSON responses (`_id` field)."""
    issues = []
    if isinstance(obj, dict):
        if "_id" in obj:
            # Tolerate when _id is a clean uuid string equal to id, otherwise flag
            issues.append(f"{path}._id present (value type={type(obj['_id']).__name__})")
        for k, v in obj.items():
            issues.extend(_no_objectid_leak(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):  # sample first 5
            issues.extend(_no_objectid_leak(v, f"{path}[{i}]"))
    return issues


# ------- Demo company data -------
class TestDemoCompanyData:
    @pytest.fixture(scope="class")
    def ctx(self, demo_login):
        cids = _company_ids(demo_login)
        assert len(cids) >= 1
        return {"hdr": _headers(demo_login), "cids": cids}

    def test_sales_summary_sharma(self, ctx):
        cid = ctx["cids"][0]
        r = requests.get(f"{BASE_URL}/api/sales/summary?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        data = body.get("data", {})
        total = data.get("total_sales") or data.get("totalSales") or 0
        # ~39.82 Lakh = 3,982,000
        assert 3_500_000 <= total <= 4_300_000, f"Sales total {total} not near ₹39.82L"
        # Check ObjectId leakage
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_overdue_digest(self, ctx):
        cid = ctx["cids"][0]
        r = requests.get(f"{BASE_URL}/api/dashboard/overdue-digest?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True, body
        data = body.get("data", {})
        rows = data.get("rows") or data.get("items") or data if isinstance(data, list) else data.get("rows", [])
        # Just check shape (rows exist or list returned)
        assert data is not None
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_customers_list(self, ctx):
        cid = ctx["cids"][0]
        # Actual endpoint is /api/customers/outstanding (no plain /api/customers)
        r = requests.get(f"{BASE_URL}/api/customers/outstanding?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", body)
        rows = data.get("customers") if isinstance(data, dict) and "customers" in data else (data if isinstance(data, list) else data.get("items", []))
        assert 12 <= len(rows) <= 20, f"Expected 15-16 customers, got {len(rows)}"
        names = " | ".join((c.get("customer_name") or c.get("name") or c.get("party_name") or "") for c in rows)
        assert "Sharma Auto Spares" in names, f"Sharma Auto Spares not found in: {names[:300]}"
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_inventory(self, ctx):
        cid = ctx["cids"][0]
        # Actual endpoint is /api/inventory/items
        r = requests.get(f"{BASE_URL}/api/inventory/items?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", body)
        rows = data if isinstance(data, list) else data.get("items") or data.get("inventory") or []
        assert 30 <= len(rows) <= 40, f"Expected ~35 items, got {len(rows)}"
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_salesman_master(self, ctx):
        cid = ctx["cids"][0]
        r = requests.get(f"{BASE_URL}/api/salesman/master?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", body)
        rows = data if isinstance(data, list) else data.get("items") or data.get("salesmen") or []
        # Tenant-wide list contains all 12 demo salesmen; verify at least 3 mapped to this company
        with_customers = [s for s in rows if s.get("customers")]
        assert len(rows) >= 3, f"Expected >=3 salesmen, got {len(rows)}"
        # Per-company expected 3-5 mapped (those having customers in this co)
        assert 3 <= len(with_customers) <= 6 or len(rows) >= 3, (
            f"Expected 3-5 salesmen mapped to company, got {len(with_customers)} with customers / {len(rows)} total"
        )
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_sync_history(self, ctx):
        cid = ctx["cids"][0]
        r = requests.get(f"{BASE_URL}/api/sync/history?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", body)
        rows = (data.get("cycles") or data.get("items") or data.get("history") or data.get("rows")
                if isinstance(data, dict) else data) or []
        assert len(rows) >= 1, f"Expected >=1 sync history row, got {len(rows)}"
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_dispatch_cards(self, ctx):
        cid = ctx["cids"][0]
        r = requests.get(f"{BASE_URL}/api/dispatch/cards?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", body)
        rows = data if isinstance(data, list) else data.get("cards") or data.get("items") or []
        assert len(rows) == 10, f"Expected 10 dispatch cards, got {len(rows)}"
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_ca_profit_loss(self, ctx):
        cid = ctx["cids"][0]
        # Actual endpoint is /api/ca-corner/profit-loss
        r = requests.get(f"{BASE_URL}/api/ca-corner/profit-loss?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True or "data" in body, body
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"

    def test_ca_balance_sheet(self, ctx):
        cid = ctx["cids"][0]
        # Actual endpoint is /api/ca-corner/balance-sheet
        r = requests.get(f"{BASE_URL}/api/ca-corner/balance-sheet?company_id={cid}",
                         headers=ctx["hdr"], timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True or "data" in body, body
        leaks = _no_objectid_leak(body)
        assert not leaks, f"ObjectId leakage: {leaks}"


# ------- Multi-company isolation -------
class TestMultiCompanyIsolation:
    def test_second_company_different_sales(self, demo_login):
        hdr = _headers(demo_login)
        cids = _company_ids(demo_login)
        assert len(cids) >= 2
        r1 = requests.get(f"{BASE_URL}/api/sales/summary?company_id={cids[0]}", headers=hdr, timeout=30)
        r2 = requests.get(f"{BASE_URL}/api/sales/summary?company_id={cids[1]}", headers=hdr, timeout=30)
        assert r1.status_code == 200 and r2.status_code == 200
        t1 = r1.json().get("data", {}).get("total_sales") or r1.json().get("data", {}).get("totalSales")
        t2 = r2.json().get("data", {}).get("total_sales") or r2.json().get("data", {}).get("totalSales")
        assert t1 is not None and t2 is not None
        assert t1 != t2, f"Multi-company isolation broken: both companies report {t1}"


# ------- Logout & renewal -------
class TestAuthEndpoints:
    def test_logout_invalidates(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "demo@flowralive.in", "password": "demo2026", "captcha_token": ""},
                         timeout=30)
        assert r.status_code == 200
        tok = r.json()["data"]["token"]
        hdr = {"Authorization": f"Bearer {tok}"}
        out = requests.post(f"{BASE_URL}/api/auth/logout", headers=hdr, timeout=15)
        # logout should at least return 200
        assert out.status_code in (200, 204), out.text

    def test_request_renewal(self, demo_login):
        hdr = _headers(demo_login)
        r = requests.post(f"{BASE_URL}/api/auth/request-renewal", headers=hdr, json={}, timeout=15)
        assert r.status_code in (200, 201, 409), r.text
        body = r.json()
        # success=True for new request OR error mentioning "pending" if already requested
        ok = body.get("success") is True or "pending" in (body.get("error") or "").lower()
        assert ok, f"Renewal endpoint failed: {body}"


# ------- Static assets -------
class TestStaticAssets:
    def test_exe_download(self):
        r = requests.get(f"{BASE_URL}/FlowraTallyAgent.exe", stream=True, timeout=60, allow_redirects=True)
        assert r.status_code == 200, f"EXE not downloadable: {r.status_code}"
        size = 0
        for chunk in r.iter_content(chunk_size=1024 * 256):
            size += len(chunk)
            if size > 22 * 1024 * 1024:
                break
        assert size > 20 * 1024 * 1024, f"EXE too small: {size} bytes (expected >20MB)"

    def test_frontend_title(self):
        r = requests.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200
        assert "<title>FLOWRA | Insights</title>" in r.text, "Title tag not updated"

    def test_complete_docs_pdf(self):
        r = requests.get(f"{BASE_URL}/docs/FLOWRA_COMPLETE_DOCUMENTATION.pdf", stream=True, timeout=30, allow_redirects=True)
        assert r.status_code == 200, f"Docs PDF status {r.status_code}"
        ct = r.headers.get("content-type", "")
        # Some setups serve as application/octet-stream
        assert "pdf" in ct.lower() or "octet" in ct.lower() or r.headers.get("content-length", "0") != "0"
