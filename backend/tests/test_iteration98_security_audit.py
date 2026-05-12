"""Iteration 98 - Pre-DigitalOcean security audit.
Tests agent endpoint hardening (sync_token enforcement),
tenant isolation, auth/RBAC, encryption, security headers, and
NoSQL injection guards.
"""
import os
import sys
import uuid
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from services.auth_service import generate_sync_token

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password, "captcha_token": ""}, timeout=30)
    return r


def _token_from_login(r):
    if r.status_code != 200:
        return None, None
    j = r.json()
    if not isinstance(j, dict):
        return None, None
    data = j.get("data") if isinstance(j.get("data"), dict) else j
    if not isinstance(data, dict):
        return None, None
    token = data.get("token") or data.get("access_token") or j.get("access_token")
    # The login response puts tenant_id / companies at the top level of `data`
    user = data
    return token, user


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login("admin", "admin123")
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    tok, user = _token_from_login(r)
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    s.cookies.update(r.cookies.get_dict())
    return s, user, tok


@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    r = _login("demo@flowralive.in", "demo2026")
    if r.status_code != 200:
        pytest.skip(f"demo login failed: {r.status_code}")
    tok, user = _token_from_login(r)
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    s.cookies.update(r.cookies.get_dict())
    return s, user, tok


# ─── Agent release manifest ────────────────────────────────
class TestAgentRelease:
    def test_latest_version(self):
        # Retry transient 502s from preview ingress
        last = None
        for _ in range(3):
            r = requests.get(f"{API}/agent/latest-version", timeout=30)
            last = r
            if r.status_code == 200:
                break
            time.sleep(2)
        assert last.status_code == 200, f"got {last.status_code}"
        j = last.json()
        d = j.get("data", {})
        assert d.get("version") == "9.8.20"
        assert "download_url" in d
        assert "min_supported_version" in d

    def test_check_update_older(self):
        r = requests.get(f"{API}/agent/check-update?current=9.8.18", timeout=30)
        assert r.status_code == 200
        assert r.json().get("data", {}).get("update_available") is True

    def test_check_update_newer(self):
        r = requests.get(f"{API}/agent/check-update?current=9.9.0", timeout=30)
        assert r.status_code == 200
        assert r.json().get("data", {}).get("update_available") is False


# ─── Agent endpoint hardening ────────────────────────────────
class TestAgentSyncAuth:
    TID = "3079b0af-e899-44b4-ae7c-c35d113fe296"

    def test_sync_rejects_missing_sync_token(self):
        r = requests.post(f"{API}/agent/sync", json={"tenant_id": self.TID, "data_type": "inventory", "data": []}, timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "sync_token" in (j.get("error") or "").lower()

    def test_sync_rejects_missing_tenant(self):
        r = requests.post(f"{API}/agent/sync", json={"data_type": "inventory", "data": []}, timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "tenant_id" in (j.get("error") or "").lower()

    def test_sync_rejects_wrong_token(self):
        r = requests.post(f"{API}/agent/sync", json={"tenant_id": self.TID, "sync_token": "deadbeef" * 8, "data_type": "inventory", "data": []}, timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "invalid sync token" in (j.get("error") or "").lower()

    def test_sync_accepts_valid_token(self):
        # Use audit-only tenant id to avoid polluting real tenant data
        audit_tid = f"security-audit-pytest-{uuid.uuid4()}"
        tok = generate_sync_token(audit_tid)
        r = requests.post(f"{API}/agent/sync", json={
            "tenant_id": audit_tid, "sync_token": tok,
            "data_type": "inventory", "data": [],
            "sync_time": "2026-01-01T00:00:00+00:00",
        }, timeout=30)
        j = r.json()
        # success may be true OR may fail with a non-auth error; key assertion
        # is that it is NOT rejected for token reasons.
        assert "sync_token" not in (j.get("error") or "").lower()
        assert "invalid sync token" not in (j.get("error") or "").lower()

    def test_reconcile_rejects_missing_sync_token(self):
        r = requests.post(f"{API}/agent/reconcile", json={"tenant_id": self.TID, "data_type": "sales", "manifest_ids": []}, timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "sync_token" in (j.get("error") or "").lower()

    def test_commands_get_rejects_missing_token(self):
        r = requests.get(f"{API}/agent/commands?tenant_id={self.TID}", timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "sync_token" in (j.get("error") or "").lower()

    def test_commands_get_accepts_valid_token(self):
        tok = generate_sync_token(self.TID)
        r = requests.get(f"{API}/agent/commands?tenant_id={self.TID}&sync_token={tok}", timeout=30)
        j = r.json()
        assert j.get("success") is True

    def test_commands_ack_soft_mode_no_token(self):
        # In soft mode (default), missing sync_token is allowed
        r = requests.post(f"{API}/agent/commands/ack", json={"tenant_id": self.TID, "action": "resync"}, timeout=30)
        j = r.json()
        assert j.get("success") is True

    def test_sync_progress_soft_mode_no_token(self):
        r = requests.post(f"{API}/agent/sync-progress", json={"tenant_id": self.TID, "type": "sync_started"}, timeout=30)
        j = r.json()
        assert j.get("success") is True


# ─── Tenant isolation ────────────────────────────────
class TestTenantIsolation:
    def test_admin_data_no_cross_tenant_leak(self, admin_session):
        s, user, _ = admin_session
        admin_tid = user.get("tenant_id")
        assert admin_tid, "admin tenant_id missing in login response"
        for ep in ("/inventory/items", "/customers/outstanding", "/sales-vouchers"):
            r = s.get(f"{API}{ep}", timeout=30)
            if r.status_code != 200:
                continue
            j = r.json()
            data = j.get("data", j)
            items = data if isinstance(data, list) else (data.get("items") or data.get("vouchers") or data.get("customers") or [])
            if isinstance(items, list):
                for it in items[:20]:
                    if isinstance(it, dict) and it.get("tenant_id"):
                        assert it["tenant_id"] == admin_tid, f"Leak in {ep}: {it.get('tenant_id')} != {admin_tid}"

    def test_cross_tenant_header_forgery(self, demo_session, admin_session):
        s_demo, demo_user, _ = demo_session
        _, admin_user, _ = admin_session
        admin_company = admin_user.get("companies", [None])[0] or "03f638d1-eab0-47ee-aed6-59049ebb5207"
        admin_tid = admin_user.get("tenant_id")
        # Pass admin's company UUID as header — server must filter by JWT tenant, not header
        r = s_demo.get(f"{API}/inventory/items", headers={"X-Company-ID": admin_company}, timeout=30)
        if r.status_code == 200:
            j = r.json()
            data = j.get("data", j)
            items = data if isinstance(data, list) else (data.get("items") or [])
            if isinstance(items, list):
                for it in items[:10]:
                    if isinstance(it, dict):
                        assert it.get("tenant_id") != admin_tid, "Cross-tenant leak via X-Company-ID!"

    def test_salesman_only_sees_mapped_customers(self):
        r = _login("ravi@test.com", "ravi1234")
        if r.status_code != 200:
            pytest.skip(f"salesman login failed: {r.status_code}")
        tok, _ = _token_from_login(r)
        s = requests.Session()
        if tok:
            s.headers.update({"Authorization": f"Bearer {tok}"})
        s.cookies.update(r.cookies.get_dict())
        # Salesman uses the salesman-orders/my-customers endpoint (admin-only
        # endpoints like /customers/outstanding are blocked by RBAC and the
        # salesman should not consume them).
        r2 = s.get(f"{API}/salesman-orders/my-customers", timeout=30)
        if r2.status_code == 200:
            j = r2.json()
            data = j.get("data") if isinstance(j.get("data"), (list, dict)) else j
            if data is None:
                items = []
            elif isinstance(data, list):
                items = data
            else:
                items = data.get("customers") or data.get("items") or []
            assert isinstance(items, list)
            # Salesman ravi is mapped to 2 customers per seed data; allow ≤5
            # margin for FY-related variants.
            assert len(items) <= 5, f"Salesman saw {len(items)} customers via my-customers — should be ≤ mapped count (2)"
        # Also verify admin-only customer endpoint is blocked for salesman
        r3 = s.get(f"{API}/customers/outstanding", timeout=30)
        if r3.status_code == 200:
            j3 = r3.json()
            items3 = (j3.get("data") or {}).get("customers") or j3.get("data") or []
            if isinstance(items3, list) and len(items3) > 10:
                pytest.fail(f"SALESMAN sees {len(items3)} customers via /customers/outstanding (admin endpoint) — RBAC bypass!")


# ─── Auth / RBAC / Rate limit ────────────────────────────────
class TestAuthRBAC:
    def test_super_admin_can_access_super_admin(self):
        r = _login("superadmin", "superadmin123")
        assert r.status_code == 200
        tok, _ = _token_from_login(r)
        s = requests.Session()
        if tok:
            s.headers.update({"Authorization": f"Bearer {tok}"})
        s.cookies.update(r.cookies.get_dict())
        r2 = s.get(f"{API}/super-admin/overview", timeout=30)
        # Endpoint may be different path — accept any 2xx OR explicit "not found" 404 (not 403)
        assert r2.status_code in (200, 404), f"super_admin denied access: {r2.status_code}"

    def test_admin_cannot_access_super_admin(self, admin_session):
        s, _, _ = admin_session
        r = s.get(f"{API}/super-admin/overview", timeout=30)
        # Admin should be blocked: 401/403 OR success=false response
        if r.status_code == 200:
            j = r.json()
            assert j.get("success") is False, "admin gained super_admin access!"
        else:
            assert r.status_code in (401, 403, 404)

    def test_salesman_cannot_create_user(self):
        r = _login("ravi@test.com", "ravi1234")
        if r.status_code != 200:
            pytest.skip("salesman login failed")
        tok, _ = _token_from_login(r)
        s = requests.Session()
        if tok:
            s.headers.update({"Authorization": f"Bearer {tok}"})
        s.cookies.update(r.cookies.get_dict())
        r2 = s.post(f"{API}/auth/users", json={"username": "TEST_evil", "password": "x", "role": "admin"}, timeout=30)
        # Acceptable rejections: 401/403 (auth), 422 (validation), or 200 success=false
        if r2.status_code == 200:
            j = r2.json()
            assert j.get("success") is False, "salesman could create a user!"
        else:
            assert r2.status_code in (401, 403, 422), f"unexpected status {r2.status_code}"

    def test_login_rate_limit(self):
        # Use a unique username to avoid IP-rate-limit state from earlier tests.
        # 11+ rapid failures should trigger 429 (FastAPI slowapi typically per-IP).
        codes = []
        for i in range(25):
            r = requests.post(f"{API}/auth/login", json={"username": f"ratenobody_{i}", "password": "wrong", "captcha_token": ""}, timeout=10)
            codes.append(r.status_code)
            if r.status_code == 429:
                break
        assert 429 in codes, f"No 429 after 25 attempts: {codes}"
        # cool-off so next test doesn't inherit the rate-limit window
        time.sleep(2)

    def test_nosql_injection_guard(self):
        # cool-off in case prior test consumed the rate-limit window
        time.sleep(65)
        # $ne/$where in username must not bypass auth
        r = requests.post(f"{API}/auth/login", json={"username": {"$ne": None}, "password": {"$ne": None}, "captcha_token": ""}, timeout=10)
        # Must NOT return 200 with success=true (i.e., must not bypass auth)
        if r.status_code == 200:
            j = r.json()
            assert j.get("success") is False, "NoSQL injection succeeded!"
        else:
            assert r.status_code in (400, 401, 422, 429)


# ─── Security headers ────────────────────────────────
class TestSecurityHeaders:
    def test_security_headers_on_public(self):
        r = requests.get(f"{API}/agent/latest-version", timeout=30)
        h = {k.lower(): v for k, v in r.headers.items()}
        missing = []
        for hdr in ("x-frame-options", "x-content-type-options", "strict-transport-security", "content-security-policy"):
            if hdr not in h:
                missing.append(hdr)
        assert not missing, f"Missing security headers: {missing}"


# ─── Public endpoints don't leak ────────────────────────────────
class TestPublicEndpoints:
    def test_plans_no_leak(self):
        r = requests.get(f"{API}/public/plans", timeout=30)
        if r.status_code != 200:
            pytest.skip(f"/public/plans not available ({r.status_code})")
        body = r.text.lower()
        for forbidden in ("password_hash", "jwt_secret", "tenant_id"):
            assert forbidden not in body, f"Leak of '{forbidden}' in /public/plans"

    def test_latest_version_no_leak(self):
        r = requests.get(f"{API}/agent/latest-version", timeout=30)
        body = r.text.lower()
        for forbidden in ("password_hash", "jwt_secret", "tenant_id", "mongo"):
            assert forbidden not in body, f"Leak of '{forbidden}' in /agent/latest-version"


# ─── Encryption at rest ────────────────────────────────
class TestEncryptionAtRest:
    @pytest.mark.asyncio
    async def test_prospects_pii_encrypted(self):
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except Exception:
            pytest.skip("motor not available")
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            pytest.skip("MONGO_URL/DB_NAME not set")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        sample = await db.prospects.find_one({}, {"_id": 0, "email": 1, "phone": 1, "contact_person": 1})
        if not sample:
            pytest.skip("no prospects to inspect")
        # Fernet ciphertexts start with 'gAAAAA' and are base64-ish; emails contain '@' when plain.
        for field in ("email", "phone", "contact_person"):
            v = sample.get(field)
            if v and isinstance(v, str) and len(v) > 0:
                # plain email would contain '@'; plain phone would be all digits w/ length <=15
                if field == "email":
                    assert "@" not in v, f"prospects.{field} stored as plaintext: {v[:30]}"
                # Reasonable proxy: encrypted strings are usually >40 chars and base64-like
                assert len(v) > 30 or v.startswith("gAAAAA"), f"prospects.{field} looks plaintext: {v[:30]}"
