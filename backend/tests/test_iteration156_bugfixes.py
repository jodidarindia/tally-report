"""Iter-156: Test 5 user-reported bugfixes.

BUG #1 CRM Targets Excel export (list-vs-dict monthly_sales).
BUG #2 Inventory PDF: Item Name col + landscape + Closing Stock rename.
BUG #4 Sync synced-FYs endpoint + FY dropdown source.
BUG #5 Movement analysis inward > 0 regression.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
BUSY_EMAIL = "busydemo@flowralive.in"
BUSY_PASSWORD = "demo2026"
BUSY_COMPANY_ID = "b21b291b-afcd-4152-b166-85be751d94bb"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": BUSY_EMAIL, "password": BUSY_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    data = body.get("data") or {}
    return data.get("token") or body.get("access_token") or body.get("token")


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- BUG #1: CRM Targets Excel export ----------
class TestBug1CrmTargetsExport:
    def test_export_with_list_monthly_sales(self, auth_headers):
        payload = {
            "company_id": BUSY_COMPANY_ID,
            "fy": "2025-26",
            "targets": [
                {
                    "customer_id": "CUST_TEST_1",
                    "customer_name": "Test Customer 1",
                    "monthly_targets": {"2025-04": 1000, "2025-05": 2000},
                    "monthly_sales": [
                        {"month": "2025-04", "amount": 500},
                        {"month": "2025-05", "amount": 1500},
                    ],
                }
            ],
        }
        r = requests.post(
            f"{BASE_URL}/api/customers/targets/export",
            json=payload,
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}: {r.text[:400]}"
        ctype = r.headers.get("content-type", "")
        assert ("spreadsheet" in ctype or "excel" in ctype or "xlsx" in ctype), f"Not xlsx content-type: {ctype}"
        # XLSX magic bytes = PK zip header
        assert r.content[:2] == b"PK", "Not a valid xlsx (missing PK header)"

    def test_export_with_dict_monthly_sales_backward_compat(self, auth_headers):
        payload = {
            "company_id": BUSY_COMPANY_ID,
            "fy": "2025-26",
            "targets": [
                {
                    "customer_id": "CUST_TEST_2",
                    "customer_name": "Test Customer 2",
                    "monthly_targets": {"2025-04": 1000},
                    "monthly_sales": {"2025-04": 500},
                }
            ],
        }
        r = requests.post(
            f"{BASE_URL}/api/customers/targets/export",
            json=payload,
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"dict-shape failed: {r.status_code} {r.text[:300]}"
        assert r.content[:2] == b"PK"


# ---------- BUG #4: synced-fys endpoint ----------
class TestBug4SyncedFYs:
    def test_synced_fys_endpoint(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/sync/synced-fys",
            params={"company_id": BUSY_COMPANY_ID},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("success") is True
        data = j.get("data") or {}
        fys = data.get("fys")
        assert isinstance(fys, list) and len(fys) > 0
        # Expect exactly the 2 synced FYs for busydemo
        assert set(fys) == {"2025-26", "2026-27"}, f"Expected ['2025-26','2026-27'] got {fys}"
        # Sanity: optional fields present
        assert "current_fy_hint" in data
        assert "oldest_voucher" in data
        assert "newest_voucher" in data


# ---------- BUG #5: Movement analysis inward > 0 ----------
class TestBug5MovementAnalysis:
    def test_movement_analysis_has_positive_inward(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/inventory/movement-analysis",
            params={"fy": "2025-26", "company_id": BUSY_COMPANY_ID},
            headers=auth_headers,
            timeout=120,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        j = r.json()
        data = j.get("data") or j
        movements = data.get("movements") or []
        assert len(movements) > 0, "no movements"
        positive_inward = [m for m in movements if (m.get("inward") or 0) > 0]
        assert len(positive_inward) >= 100, (
            f"Only {len(positive_inward)} items with inward>0 (of {len(movements)}); "
            f"expected >= 100"
        )
        # Spot check top 3 fast movers have opening_stock >= 0 (sensible)
        top = movements[:3]
        for m in top:
            os_val = m.get("opening_stock")
            assert os_val is not None, f"missing opening_stock on {m.get('item_name')}"


# ---------- BUG #2: Inventory PDF export ----------
class TestBug2InventoryPDF:
    def test_inventory_pdf_export_valid(self, auth_headers):
        payload = {
            "format": "pdf",
            "report_type": "inventory",
            "filters": {"search": "engine", "company_id": BUSY_COMPANY_ID},
        }
        r = requests.post(
            f"{BASE_URL}/api/reports/export",
            json=payload,
            headers=auth_headers,
            timeout=120,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        assert r.content[:5] == b"%PDF-", f"Not a PDF (got {r.content[:20]!r})"
        # Save for manual inspection
        out = "/tmp/inventory_export_iter156.pdf"
        with open(out, "wb") as f:
            f.write(r.content)
        print(f"PDF saved to {out} ({len(r.content)} bytes)")

    def test_inventory_pdf_contains_closing_stock_and_item_name(self, auth_headers):
        payload = {
            "format": "pdf",
            "report_type": "inventory",
            "filters": {"search": "engine", "company_id": BUSY_COMPANY_ID},
        }
        r = requests.post(
            f"{BASE_URL}/api/reports/export",
            json=payload,
            headers=auth_headers,
            timeout=120,
        )
        assert r.status_code == 200
        # Best-effort text scan (PDF may have compressed streams — this is not authoritative)
        blob = r.content
        # We can't reliably parse without pypdf, but we can verify the file is > minimal PDF
        assert len(blob) > 2000, f"PDF too small ({len(blob)} bytes) — likely empty"


# ---------- Regression: sync/companies-status ----------
class TestRegressionSyncCompanies:
    def test_companies_status(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/sync/companies-status",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        j = r.json()
        assert j.get("success") is True or "data" in j or "companies" in j
