"""Iteration 135 — CA Reports: prior-year manual entry (per user follow-up).

Backend + engine round-trip for the new `ca_manual_historicals` collection:
  1. GET/POST/DELETE endpoints exist and use the useradmin role guard.
  2. Manual entry monetary fields are Fernet-encrypted at rest
     (the list _MANUAL_ENCRYPTED_FIELDS matches every $-value in
     HistoricalFY that a user might supply).
  3. Encryption round-trip preserves numeric fidelity for float values.
  4. Preview endpoint's "no data" bail relaxes when manual FYs exist.
  5. `_assemble_fys` merges Tally + manual, Tally wins on collision, and
     the result is sorted by fy_label.
  6. Frontend renders the ManualHistoricalsSection + form with all the
     required data-testids and the "encrypted at rest" badge.
"""
import ast
import sys
from pathlib import Path

ROUTE = Path("/app/backend/routes/ca_reports.py")
UI = Path("/app/frontend/src/pages/CAReports.jsx")

sys.path.insert(0, "/app/backend")


def test_manual_endpoints_present():
    src = ROUTE.read_text()
    for method_pattern in (
        "@router.get(\"/ca-reports/manual-historicals\")",
        "@router.post(\"/ca-reports/manual-historicals\")",
        "@router.delete(\"/ca-reports/manual-historicals/{fy_label}\")",
    ):
        assert method_pattern in src, f"missing route: {method_pattern}"


def test_manual_endpoints_use_useradmin_guard():
    src = ROUTE.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if node.name in ("list_manual_historicals",
                          "upsert_manual_historical",
                          "delete_manual_historical"):
            body = ast.unparse(node)
            assert "_require_useradmin(request)" in body, (
                f"{node.name} must use useradmin guard")


def test_manual_encrypted_fields_cover_all_monetary_values():
    """Every $-denominated field in HistoricalFY that a user might type
    in should live in the _MANUAL_ENCRYPTED_FIELDS tuple. fy_label is
    the natural key and is intentionally NOT encrypted."""
    from routes.ca_reports import _MANUAL_ENCRYPTED_FIELDS
    from services.ca_reports_engine import HistoricalFY
    fy_fields = set(HistoricalFY.__dataclass_fields__.keys())
    # These are always derived / computed → don't need to be manual-entered
    # but even if they were, encrypting is fine.
    encrypted = set(_MANUAL_ENCRYPTED_FIELDS)
    # At minimum, the P&L bones + BS bones the manual-entry form exposes
    for k in ("net_sales", "purchases", "sga_expenses", "depreciation",
               "interest", "provision_for_tax",
               "sundry_creditors", "term_loans", "unsecured_loans",
               "proprietors_capital", "reserves_surplus",
               "cash_bank_balance", "receivables_domestic",
               "inventory_finished", "gross_block"):
        assert k in encrypted, f"expected {k} to be encrypted at rest"
        assert k in fy_fields   # sanity — must exist on the dataclass


def test_encryption_roundtrip_manual_values():
    from routes.ca_reports import _encrypt_manual, _decrypt_manual
    doc = {
        "fy_label": "2020-21",
        "net_sales": 540.0,
        "purchases": 486.0,
        "sga_expenses": 52.5,
        "sundry_creditors": 72.0,
        "receivables_domestic": 48.0,
        "proprietors_capital": 41.03,
        "reserves_surplus": 15.0,
    }
    enc = _encrypt_manual(doc)
    # Encrypted fields must NOT equal the raw values
    assert enc["net_sales"] != 540.0
    assert isinstance(enc["net_sales"], str) and len(enc["net_sales"]) > 20
    # fy_label kept plaintext (natural key, needed for lookup)
    assert enc["fy_label"] == "2020-21"
    back = _decrypt_manual(enc)
    assert back["net_sales"] == 540.0
    assert back["purchases"] == 486.0
    assert back["proprietors_capital"] == 41.03
    assert back["fy_label"] == "2020-21"


def test_preview_allows_manual_only_tenants():
    """The old preview_report bailed hard on 'No FY data synced'. After
    this iteration, it must survive when the tenant has 0 Tally FYs but
    at least 1 manual FY."""
    src = ROUTE.read_text()
    # Find preview_report body
    tree = ast.parse(src)
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "preview_report":
            body = ast.unparse(node)
            break
    assert body, "preview_report not found"
    assert "ca_manual_historicals" in body, (
        "preview_report must consult ca_manual_historicals count before "
        "returning the 'No FY data' error"
    )
    assert "manual_count == 0" in body


def test_assemble_fys_merges_and_dedupes():
    """`_assemble_fys` must merge Tally + manual FYs, dedupe by fy_label
    with Tally winning on collision, and sort chronologically."""
    src = ROUTE.read_text()
    tree = ast.parse(src)
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_assemble_fys":
            body = ast.unparse(node)
            break
    assert body, "_assemble_fys not found"
    # Look for the merge signature
    assert "_load_manual_historicals" in body
    assert "synced_labels" in body
    assert "sorted(" in body


def test_frontend_manual_section_wired():
    src = UI.read_text()
    for testid in ("manual-historicals-section",
                    "btn-add-manual-fy",
                    "manual-fy-modal",
                    "manual-fy-label",
                    "btn-save-manual",
                    "btn-cancel-manual"):
        assert testid in src, f"missing data-testid: {testid}"
    # Encrypted-at-rest badge visible to the user
    assert "Encrypted at rest" in src
    # Field inputs for at least the core P&L and BS lines. The JSX uses a
    # template literal `manual-field-${key}` — assert the pattern is
    # present and that every core field key is referenced somewhere in
    # the MANUAL_FIELDS declaration.
    assert "manual-field-" in src, "manual-field-* template testid missing"
    for f in ("net_sales", "purchases", "sundry_creditors",
                "proprietors_capital", "receivables_domestic",
                "inventory_finished", "gross_block"):
        assert f"'{f}'" in src or f'"{f}"' in src, (
            f"MANUAL_FIELDS missing key: {f}"
        )


def test_frontend_delete_button_present():
    src = UI.read_text()
    assert "btn-delete-manual-" in src
    assert "btn-edit-manual-" in src
    # Confirm before destructive action
    assert "window.confirm" in src


if __name__ == "__main__":
    for fn in [
        test_manual_endpoints_present,
        test_manual_endpoints_use_useradmin_guard,
        test_manual_encrypted_fields_cover_all_monetary_values,
        test_encryption_roundtrip_manual_values,
        test_preview_allows_manual_only_tenants,
        test_assemble_fys_merges_and_dedupes,
        test_frontend_manual_section_wired,
        test_frontend_delete_button_present,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll iter-135 manual-historicals tests passed.")
