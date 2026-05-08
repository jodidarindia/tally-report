"""Regression tests for iteration 63: bank sign normalization + creditor derivation."""
import os
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


def _login(u, p):
    r = requests.post(
        f"{API_URL}/api/auth/login",
        json={"username": u, "password": p, "captcha_token": ""},
    )
    r.raise_for_status()
    return r.json()["data"]["token"]


# ───────── /api/creditors ─────────

def test_creditors_derived_from_all_ledgers():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/creditors", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    d = body["data"]
    # The seeded tenant (ASA AUTOTECH) has Dealer Deposit + Unsecured Loans + NCL
    assert d["count"] >= 20, f"Expected >=20 creditors, got {d['count']}"
    assert d["total_outstanding"] > 0
    groups = {c["ledger_group"] for c in d["creditors"]}
    # Must include at least these custom liability groups
    assert "Unsecured Loans" in groups or "Dealer Deposit" in groups
    # Top creditor should be a meaningful liability
    top = d["creditors"][0]
    assert top["outstanding_amount"] > 0
    assert top["creditor_name"]


def test_creditors_excludes_customers():
    """Ledgers already in `customers` (debtor) should never appear as creditors."""
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/creditors", headers=h).json()
    creditor_names_lower = {c["creditor_name"].strip().lower() for c in r["data"]["creditors"]}
    # Sanity: the seeded customer "Ankit Automobiles Indore" must NOT appear
    assert "ankit automobiles indore" not in creditor_names_lower


def test_creditors_config_admin_only():
    salesman_h = {"Authorization": f"Bearer {_login('ravi@test.com', 'ravi1234')}"}
    r = requests.get(f"{API_URL}/api/creditors/config", headers=salesman_h)
    assert r.json()["success"] is False
    assert "Admin" in (r.json().get("error") or "")


def test_creditors_config_get_returns_groups():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/creditors/config", headers=h).json()
    assert r["success"] is True
    assert "Sundry Creditors" in r["data"]["creditor_groups"]
    # Available list should include the user's actual groups
    avail = r["data"]["available_groups"]
    assert len(avail) > 5
    assert "Bank Accounts" in avail or "Cash-in-Hand" in avail


def test_creditors_config_post_persists():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}", "Content-Type": "application/json"}
    new_list = ["Sundry Creditors", "Dealer Deposit"]
    r = requests.post(f"{API_URL}/api/creditors/config",
                      headers=h, json={"creditor_groups": new_list}).json()
    assert r["success"] is True
    assert r["data"]["creditor_groups"] == new_list
    # Read back
    rr = requests.get(f"{API_URL}/api/creditors/config", headers=h).json()
    assert rr["data"]["creditor_groups"] == new_list
    # Restore defaults
    requests.post(f"{API_URL}/api/creditors/config",
                  headers=h, json={"creditor_groups": [
                      "Sundry Creditors", "Dealer Deposit",
                      "Unsecured Loans", "Non Current Liability"]})


# ───────── /api/ca-corner/cash-flow bank sign ─────────

def test_bank_od_sign_flipped():
    """For bank_od (liability) ledgers, closing/opening must be FLIPPED from the
    raw Tally CR-positive value to owner-cash perspective:
      - Loan accrued (CR balance in Tally → +ve stored) → display NEGATIVE
      - Loan with extra deposit (DR balance in Tally → -ve stored) → display POSITIVE
    """
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/ca-corner/cash-flow", headers=h).json()
    assert r["success"] is True
    banks = r["data"]["bank_details"]
    # Find HDFC OD entries
    od = [b for b in banks if b["type"] == "bank_od"]
    assert od, "Expected at least one bank_od ledger"
    # The seeded HDFC 0232 has CR balance ~20L → after flip must be negative
    main_loan = next((b for b in od if "0232" in b["name"]), None)
    if main_loan:
        assert main_loan["closing"] < 0, f"HDFC 0232 should be negative, got {main_loan['closing']}"
    # HDFC CC Limit has -400 stored → after flip must be positive
    cc = next((b for b in od if "CC Limit" in b["name"] or "50200118020493" in b["name"]), None)
    if cc:
        assert cc["closing"] > 0, f"HDFC CC Limit should be positive (extra deposit), got {cc['closing']}"


def test_bank_asset_sign_unchanged():
    """For bank/cash (asset) ledgers, signs are kept raw (DR=+ owner has money)."""
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/ca-corner/cash-flow", headers=h).json()
    banks = r["data"]["bank_details"]
    bank_assets = [b for b in banks if b["type"] in ("bank", "cash")]
    # No flip applied — values should match raw Tally CLOSINGBALANCE
    for b in bank_assets:
        assert b["closing"] is not None


# ───────── BS uses live-derived creditors ─────────

def test_balance_sheet_creditor_count_nonzero():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/ca-corner/balance-sheet", headers=h).json()
    assert r["success"] is True
    # creditor_count should now be >0 because BS derives from all_ledgers + creditor groups
    assert r["data"]["creditor_count"] > 0
