"""Wave 2 forecast API tests (iter-155+): per-SKU deep-dive endpoint,
buy-list bands, regression on overview/season/cohort."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
COMPANY_ID = "b21b291b-afcd-4152-b166-85be751d94bb"
USERNAME = "busydemo@flowralive.in"
PASSWORD = "demo2026"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": USERNAME, "password": PASSWORD, "captcha_token": ""},
                      timeout=30)
    assert r.status_code == 200, f"login http {r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("success"), f"login failed: {body}"
    token = body["data"]["token"]
    return {"Authorization": f"Bearer {token}", "X-Company-ID": COMPANY_ID}


@pytest.fixture(scope="module")
def overview(auth_headers):
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/overview",
                     headers=auth_headers,
                     params={"horizon_months": 3, "fresh": 0},
                     timeout=120)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("success") is True, body
    return body["data"]


# ─── Wave 2: buy-list bands + past_12 ───────────────────────────────
def test_buy_list_has_bands_and_past_12(overview):
    buy_list = overview.get("buy_list", [])
    assert isinstance(buy_list, list)
    if not buy_list:
        pytest.skip("no buy_list rows for this tenant")
    row = buy_list[0]
    for k in ("monthly_forecast", "monthly_forecast_low", "monthly_forecast_high", "past_12"):
        assert k in row, f"buy_list row missing key {k}: {list(row.keys())}"
    h = len(row["monthly_forecast"])
    assert h > 0 and h == 3
    assert len(row["monthly_forecast_low"]) == h
    assert len(row["monthly_forecast_high"]) == h
    assert len(row["past_12"]) == 12
    # High >= mean >= low (loose check on aggregate — engine may equal at edges)
    for lo, mid, hi in zip(row["monthly_forecast_low"], row["monthly_forecast"], row["monthly_forecast_high"]):
        assert lo <= mid + 1e-6
        assert mid <= hi + 1e-6


# ─── Wave 2: /sku/{item_id} valid ───────────────────────────────────
def test_sku_endpoint_valid(auth_headers, overview):
    buy_list = overview.get("buy_list", [])
    if not buy_list:
        pytest.skip("no buy_list rows")
    item_id = buy_list[0]["item_id"]
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/sku/{item_id}",
                     headers=auth_headers, params={"horizon_months": 3}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("success") is True, body
    data = body["data"]
    assert "sku" in data and "past_month_labels" in data and "forecast_month_labels" in data
    assert "festival_calendar" in data
    # past labels: exactly 12, each with y/m/label/festival_tag (tag may be None)
    plabels = data["past_month_labels"]
    assert len(plabels) == 12
    for lab in plabels:
        for k in ("y", "m", "label"):
            assert k in lab
        assert "festival_tag" in lab  # key present, value may be None
    # forecast labels: horizon_months (3)
    flabels = data["forecast_month_labels"]
    assert len(flabels) == 3
    for lab in flabels:
        assert {"y", "m", "label"}.issubset(lab.keys())
    # sku payload arrays
    sku = data["sku"]
    assert len(sku["monthly_forecast"]) == 3
    assert len(sku["monthly_forecast_low"]) == 3
    assert len(sku["monthly_forecast_high"]) == 3
    assert len(sku["past_12"]) == 12
    # Regression fix (iter-118 → iter-119): past_12 length must equal past_month_labels length
    assert len(sku["past_12"]) == len(plabels) == 12


# ─── Wave 2: /sku/UNKNOWN_ID ───────────────────────────────────────
def test_sku_endpoint_unknown(auth_headers):
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/sku/UNKNOWN_ID_XXXX",
                     headers=auth_headers, params={"horizon_months": 3}, timeout=120)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False
    assert "not found" in (body.get("error") or "").lower()


# ─── Wave 2: /sku no auth → 401 ─────────────────────────────────────
def test_sku_endpoint_no_auth():
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/sku/anything",
                     timeout=30)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


# ─── Regression: overview / season / cohort still work ──────────────
def test_overview_regression(overview):
    assert "kpi" in overview and "buy_list" in overview
    assert "festival_calendar" in overview


def test_season_regression(auth_headers):
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/season",
                     headers=auth_headers, params={"top": 5, "horizon_months": 3}, timeout=120)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True, body
    assert "rows" in body["data"]
    assert "festival_calendar" in body["data"]


def test_cohort_regression(auth_headers):
    r = requests.get(f"{BASE_URL}/api/analytics/forecast/cohort",
                     headers=auth_headers, params={"top_customers": 5, "horizon_months": 3}, timeout=120)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True, body
    assert "rows" in body["data"]
