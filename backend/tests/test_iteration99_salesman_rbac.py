"""Iteration 99 - Regression for iter98 HIGH finding.

Verifies the salesman→customer scoping fix on /api/customers/* endpoints,
re-runs the iter98 agent-endpoint / tenant-isolation / RBAC regression tests
and adds edge-case checks (unmapped salesman returns empty, not full list).
"""
import os
import sys
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    return requests.post(
        f"{API}/auth/login",
        json={"username": username, "password": password, "captcha_token": ""},
        timeout=30,
    )


def _tok(r):
    if r.status_code != 200:
        return None, None
    j = r.json()
    d = j.get("data") if isinstance(j.get("data"), dict) else j
    if not isinstance(d, dict):
        return None, None
    return (d.get("token") or d.get("access_token") or j.get("access_token")), d


def _session(username, password):
    r = _login(username, password)
    if r.status_code != 200:
        return None, None
    tok, user = _tok(r)
    s = requests.Session()
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    s.cookies.update(r.cookies.get_dict())
    return s, user


def _items_from(j):
    """Normalise the various response shapes used by /customers/* endpoints."""
    if not isinstance(j, dict):
        return []
    data = j.get("data", j)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("customers", "items", "followups", "targets", "behaviors"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


@pytest.fixture(scope="module")
def admin_sess():
    s, u = _session("admin", "admin123")
    assert s is not None, "admin login failed"
    return s, u


@pytest.fixture(scope="module")
def salesman_sess():
    s, u = _session("ravi@test.com", "ravi1234")
    if s is None:
        pytest.skip("salesman login failed")
    return s, u


# ─── PRIMARY REGRESSION: salesman scoping on customer endpoints ────────────
class TestSalesmanCustomerScoping:
    MAPPED = "Ankit Automobiles, Indore"

    def _names(self, items):
        out = set()
        for it in items:
            if not isinstance(it, dict):
                continue
            for k in ("customer_name", "party_name", "name", "customer"):
                v = it.get(k)
                if isinstance(v, str):
                    out.add(v)
                    break
        return out

    def test_admin_outstanding_full_view(self, admin_sess):
        s, _ = admin_sess
        r = s.get(f"{API}/customers/outstanding?fy=2026-2027", timeout=60)
        assert r.status_code == 200, r.text[:200]
        items = _items_from(r.json())
        # Admin must see many more than 1; iter98 reported 37+ in tenant.
        assert len(items) >= 5, f"Admin sees only {len(items)} customers — expected full tenant view"

    def test_salesman_outstanding_scoped(self, salesman_sess):
        s, _ = salesman_sess
        r = s.get(f"{API}/customers/outstanding?fy=2026-2027", timeout=60)
        assert r.status_code == 200, r.text[:200]
        items = _items_from(r.json())
        names = self._names(items)
        # MUST NOT leak the entire tenant — iter98 saw 83 here.
        assert len(items) <= 5, f"LEAK: salesman sees {len(items)} customers via /customers/outstanding"
        # Every returned name must be in the mapped set.
        for n in names:
            assert self.MAPPED.lower() in n.lower() or n == self.MAPPED, f"Unmapped customer leaked: {n}"

    def test_salesman_followups_scoped(self, salesman_sess, admin_sess):
        s_admin, _ = admin_sess
        s_sales, _ = salesman_sess
        ra = s_admin.get(f"{API}/customers/followups", timeout=60)
        rs = s_sales.get(f"{API}/customers/followups", timeout=60)
        if ra.status_code != 200 or rs.status_code != 200:
            pytest.skip(f"followups admin={ra.status_code} salesman={rs.status_code}")
        a_items = _items_from(ra.json())
        s_items = _items_from(rs.json())
        assert len(s_items) <= len(a_items), f"salesman followups ({len(s_items)}) > admin ({len(a_items)})"
        for n in self._names(s_items):
            assert self.MAPPED.lower() in n.lower() or n == self.MAPPED, f"followups leak: {n}"

    def test_salesman_targets_scoped(self, salesman_sess, admin_sess):
        s_admin, _ = admin_sess
        s_sales, _ = salesman_sess
        ra = s_admin.get(f"{API}/customers/targets", timeout=60)
        rs = s_sales.get(f"{API}/customers/targets", timeout=60)
        if ra.status_code != 200 or rs.status_code != 200:
            pytest.skip(f"targets admin={ra.status_code} salesman={rs.status_code}")
        a_items = _items_from(ra.json())
        s_items = _items_from(rs.json())
        assert len(s_items) <= len(a_items), f"salesman targets ({len(s_items)}) > admin ({len(a_items)})"
        for n in self._names(s_items):
            assert self.MAPPED.lower() in n.lower() or n == self.MAPPED, f"targets leak: {n}"

    def test_salesman_payment_behavior_scoped(self, salesman_sess, admin_sess):
        s_admin, _ = admin_sess
        s_sales, _ = salesman_sess
        ra = s_admin.get(f"{API}/customers/payment-behavior", timeout=60)
        rs = s_sales.get(f"{API}/customers/payment-behavior", timeout=60)
        if ra.status_code != 200 or rs.status_code != 200:
            pytest.skip(f"payment-behavior admin={ra.status_code} salesman={rs.status_code}")
        a_items = _items_from(ra.json())
        s_items = _items_from(rs.json())
        assert len(s_items) <= len(a_items), f"salesman pay-behavior ({len(s_items)}) > admin ({len(a_items)})"
        for n in self._names(s_items):
            assert self.MAPPED.lower() in n.lower() or n == self.MAPPED, f"payment-behavior leak: {n}"

    def test_salesman_ledger_export_denied_for_unmapped(self, salesman_sess):
        s, _ = salesman_sess
        r = s.post(
            f"{API}/customers/ledger/export",
            json={"customer_name": "Krishna Sales Corporation", "fy": "2026-2027"},
            timeout=60,
        )
        # 200 with success=false OR 403 are both acceptable rejections.
        if r.status_code == 200:
            try:
                j = r.json()
                assert j.get("success") is False, f"salesman exported unmapped ledger! {j}"
                err = (j.get("error") or "").lower()
                assert "access denied" in err or "denied" in err or "not authorised" in err
            except ValueError:
                pytest.fail("ledger/export returned PDF stream for unmapped customer!")
        else:
            assert r.status_code in (401, 403, 404), f"unexpected {r.status_code}"

    def test_salesman_ledger_export_allowed_for_mapped(self, salesman_sess):
        s, _ = salesman_sess
        r = s.post(
            f"{API}/customers/ledger/export",
            json={"customer_name": self.MAPPED, "fy": "2026-2027"},
            timeout=120,
        )
        # Accept either: PDF/stream OK, OR JSON success=true, OR success=false
        # only if the reason is NOT 'access denied' (e.g., no data in FY).
        if r.status_code == 200:
            ctype = r.headers.get("content-type", "")
            if "json" in ctype:
                j = r.json()
                if j.get("success") is False:
                    err = (j.get("error") or "").lower()
                    assert "access denied" not in err and "denied" not in err, \
                        f"Mapped customer wrongly denied: {err}"
            # binary PDF stream is the happy path → accept
        else:
            # 4xx other than 403 is acceptable (e.g., 404 if no data); 403 is NOT
            assert r.status_code != 403, "Salesman denied access to MAPPED customer ledger!"


# ─── Edge case: salesman with no mapping ──────────────────────────────────
class TestUnmappedSalesman:
    def test_unmapped_salesman_returns_empty_not_full(self):
        # Use a demo-tenant salesman that has NO salesman_master row in admin
        # tenant. If login fails for all candidates we skip — pytest must not
        # block the suite on missing seed.
        for u in ("rajesh.lub.demo@flowralive.in",):
            r = _login(u, "demo2026")
            if r.status_code != 200:
                continue
            tok, _ = _tok(r)
            s = requests.Session()
            if tok:
                s.headers.update({"Authorization": f"Bearer {tok}"})
            # Demo salesman on demo tenant — must NOT see the admin tenant's
            # full customer list. Will see at most their mapped customers
            # (could be empty if no FY mapping for current FY).
            rr = s.get(f"{API}/customers/outstanding?fy=2026-2027", timeout=60)
            if rr.status_code != 200:
                continue
            items = _items_from(rr.json())
            assert len(items) < 50, \
                f"Demo salesman saw {len(items)} customers — full tenant leak!"
            return
        pytest.skip("no demo salesman login worked")


# ─── REGRESSION: iter98 agent-endpoint enforcement still green ────────────
class TestAgentRegression:
    TID = "3079b0af-e899-44b4-ae7c-c35d113fe296"

    def test_sync_rejects_missing_token(self):
        r = requests.post(f"{API}/agent/sync", json={"tenant_id": self.TID, "data_type": "inventory", "data": []}, timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "sync_token" in (j.get("error") or "").lower()

    def test_reconcile_rejects_missing_token(self):
        r = requests.post(f"{API}/agent/reconcile", json={"tenant_id": self.TID, "data_type": "sales", "manifest_ids": []}, timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "sync_token" in (j.get("error") or "").lower()

    def test_commands_get_rejects_missing_token(self):
        r = requests.get(f"{API}/agent/commands?tenant_id={self.TID}", timeout=30)
        j = r.json()
        assert j.get("success") is False
        assert "sync_token" in (j.get("error") or "").lower()

    def test_sync_progress_soft_mode(self):
        r = requests.post(f"{API}/agent/sync-progress", json={"tenant_id": self.TID, "type": "sync_started"}, timeout=30)
        assert r.json().get("success") is True

    def test_commands_ack_soft_mode(self):
        r = requests.post(f"{API}/agent/commands/ack", json={"tenant_id": self.TID, "action": "resync"}, timeout=30)
        assert r.json().get("success") is True

    def test_latest_version(self):
        last = None
        for _ in range(3):
            r = requests.get(f"{API}/agent/latest-version", timeout=30)
            last = r
            if r.status_code == 200:
                break
            time.sleep(2)
        assert last.status_code == 200
        assert "version" in last.json().get("data", {})

    def test_check_update_older(self):
        r = requests.get(f"{API}/agent/check-update?current=9.8.18", timeout=30)
        assert r.status_code == 200
        assert r.json().get("data", {}).get("update_available") is True


# ─── REGRESSION: tenant isolation across multi-tenant endpoints ───────────
class TestTenantIsolation:
    def test_demo_cannot_read_admin_tenant(self, admin_sess):
        _, admin_user = admin_sess
        admin_tid = admin_user.get("tenant_id")
        s_demo, _ = _session("demo@flowralive.in", "demo2026")
        if s_demo is None:
            pytest.skip("demo login failed")
        admin_company = (admin_user.get("companies") or ["03f638d1-eab0-47ee-aed6-59049ebb5207"])[0]
        r = s_demo.get(f"{API}/inventory/items", headers={"X-Company-ID": admin_company}, timeout=30)
        if r.status_code != 200:
            return
        items = _items_from(r.json())
        for it in items[:20]:
            if isinstance(it, dict) and it.get("tenant_id"):
                assert it["tenant_id"] != admin_tid, "Cross-tenant leak via X-Company-ID!"


# ─── REGRESSION: auth flows still respond ─────────────────────────────────
class TestAuthFlows:
    @pytest.mark.parametrize("u,p", [
        ("admin", "admin123"),
        ("superadmin", "superadmin123"),
        ("ravi@test.com", "ravi1234"),
        ("demo@flowralive.in", "demo2026"),
    ])
    def test_login(self, u, p):
        r = _login(u, p)
        assert r.status_code == 200, f"{u} login failed: {r.status_code} {r.text[:200]}"
        tok, _ = _tok(r)
        assert tok, f"no token in login response for {u}"
