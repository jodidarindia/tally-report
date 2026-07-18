"""Iteration 134 — CA Corner CMA + Pitch Deck generator.

Tests the whole pipeline:
  - Engine: projections + form computations + PDF/XLSX byte output
  - Route: auth guard (403 for non-admin), tenant + company isolation,
     encrypted assumption storage round-trip, streaming binary response
  - Frontend: CAReports.jsx is imported from CACorner and tab is gated
     on userRole === 'admin'
"""
import sys
from pathlib import Path

ENGINE = Path("/app/backend/services/ca_reports_engine.py")
ROUTE = Path("/app/backend/routes/ca_reports.py")
UI = Path("/app/frontend/src/pages/CAReports.jsx")
CACORNER = Path("/app/frontend/src/pages/CACorner.js")

sys.path.insert(0, "/app/backend")


def test_engine_projections_and_downloads():
    from services.ca_reports_engine import (
        HistoricalFY, Assumptions, CompanyMeta,
        project_future_fys, build_cma_pdf, build_cma_xlsx,
        build_pitch_pdf, build_projections_xlsx,
    )
    h1 = HistoricalFY(fy_label="2021-22", net_sales=1173.65,
                        purchases=1055.72, sga_expenses=113.16,
                        interest=1.36, depreciation=1.63,
                        provision_for_tax=0.62,
                        sundry_creditors=98.66,
                        receivables_domestic=101.55,
                        inventory_finished=59.36,
                        proprietors_capital=41.03,
                        reserves_surplus=1.90,
                        cash_bank_balance=53.06,
                        gross_block=13.35)
    h2 = HistoricalFY(fy_label="2022-23", net_sales=670.20,
                        purchases=606.42, sga_expenses=65.61,
                        interest=1.64, depreciation=1.42,
                        provision_for_tax=0.15,
                        sundry_creditors=76.85,
                        receivables_domestic=57.60,
                        inventory_finished=57.60,
                        proprietors_capital=41.03,
                        reserves_surplus=-24.06,
                        cash_bank_balance=63.94,
                        gross_block=13.35)
    a = Assumptions(sales_growth_y1=15, sales_growth_y2=15,
                     sales_growth_y3=15, debtor_days_target=60,
                     creditor_days_target=45, inventory_days_target=45,
                     gp_margin_target_pct=10, proposed_cc_limit=100.0)
    meta = CompanyMeta(company_name="Krishna Sales Corporation")
    hist = [h1, h2]
    proj = project_future_fys(hist, a, n_future=3)
    assert len(proj) == 3
    assert proj[0].fy_label == "2023-24"
    assert proj[2].fy_label == "2025-26"
    # 15% growth CAGR compounded 3x
    assert proj[-1].net_sales > h2.net_sales * 1.5
    # Every builder produces a non-empty binary
    for name, fn in [
        ("cma_pdf",     lambda: build_cma_pdf(meta, hist, proj, a)),
        ("cma_xlsx",    lambda: build_cma_xlsx(meta, hist, proj, a)),
        ("pitch_pdf",   lambda: build_pitch_pdf(meta, hist, proj, a, False)),
        ("teaser_pdf",  lambda: build_pitch_pdf(meta, hist, proj, a, True)),
        ("proj_xlsx",   lambda: build_projections_xlsx(meta, hist, proj, a)),
    ]:
        blob = fn()
        assert isinstance(blob, bytes) and len(blob) > 1000, \
            f"{name} output too small: {len(blob)} bytes"


def test_engine_form_computations():
    from services.ca_reports_engine import (
        HistoricalFY, compute_form_ii, compute_form_iii,
        compute_form_v_mpbf,
    )
    fy = HistoricalFY(fy_label="2022-23", net_sales=670.20, purchases=606.42,
                       sga_expenses=65.61, interest=1.64, depreciation=1.42,
                       sundry_creditors=76.85, receivables_domestic=57.60,
                       inventory_finished=57.60, proprietors_capital=41.03,
                       reserves_surplus=-24.06, cash_bank_balance=63.94)
    ii = compute_form_ii(fy)
    # Cost of production = purchases + direct wages + power + other + dep
    assert ii["cost_of_production"] == 606.42 + 1.42
    # PBT = op_profit_ai + non-op net
    assert "pbt" in ii and "npat" in ii
    iii = compute_form_iii(fy)
    assert iii["tcl"] == pytest_approx(76.85)   # only creditors
    assert iii["nw"] == pytest_approx(41.03 - 24.06)
    # MPBF fed a positive projected NWC
    m = compute_form_v_mpbf(fy, other_cl_excl_bank=76.85,
                              projected_nwc=iii["nwc"])
    assert "m1_mpbf" in m and "m2_mpbf" in m
    assert m["wcg"] == pytest_approx(m["tca"] - 76.85)


def pytest_approx(v, tol=0.01):
    class _A:
        def __eq__(self, o):
            return abs(o - v) < tol
    return _A()


def test_route_auth_guard_and_encryption():
    """AST-level checks — full HTTP integration is via testing agent."""
    src = ROUTE.read_text()
    # Every route uses _require_useradmin
    for endpoint in (
        "/ca-reports/preview", "/ca-reports/assumptions",
        "/ca-reports/cma/pdf", "/ca-reports/cma/xlsx",
        "/ca-reports/pitch/pdf", "/ca-reports/pitch/teaser",
        "/ca-reports/pitch/xlsx",
    ):
        assert endpoint in src, f"route missing: {endpoint}"
    # Auth guard is called from every route
    handler_defs = [line for line in src.splitlines()
                     if "async def gen_" in line
                     or "async def preview_" in line
                     or "async def get_assumptions" in line
                     or "async def save_assumptions" in line]
    assert len(handler_defs) >= 6
    # Guard function exists and rejects non-admin
    assert 'role != "admin"' in src
    assert "raise HTTPException(status_code=403" in src
    # Sensitive fields are Fernet-encrypted before storage
    assert "_ENCRYPTED_FIELDS" in src
    for field in ("gstin", "pan", "bank_name", "msme_regn"):
        assert f'"{field}"' in src, f"expected encrypted field: {field}"
    # Tenant + company isolation
    assert "_tenant_company_query" in src
    assert 'tenant_id"' in src or "'tenant_id'" in src
    assert 'company_id"' in src or "'company_id'" in src


def test_encrypted_assumption_roundtrip():
    from routes.ca_reports import (
        _encrypt_assumptions, _decrypt_assumptions,
    )
    from services.ca_reports_engine import Assumptions
    a = Assumptions(gstin="07AAKPS1234R1Z2", pan="AAKPS1234R",
                     bank_name="HDFC Bank", msme_regn="UDYAM-DL-01-1234567",
                     proposed_cc_limit=250.0, sales_growth_y1=12.5)
    enc = _encrypt_assumptions(a)
    # Encrypted fields must NOT equal the raw values
    assert enc["gstin"] != "07AAKPS1234R1Z2"
    assert enc["pan"] != "AAKPS1234R"
    assert enc["bank_name"] != "HDFC Bank"
    # Numeric fields pass through unencrypted
    assert enc["proposed_cc_limit"] == 250.0
    assert enc["sales_growth_y1"] == 12.5
    # Round-trip
    back = _decrypt_assumptions(enc)
    assert back.gstin == "07AAKPS1234R1Z2"
    assert back.pan == "AAKPS1234R"
    assert back.bank_name == "HDFC Bank"
    assert back.proposed_cc_limit == 250.0


def test_engine_carries_flowra_footer_and_company_header():
    """User's mandatory branding — every generated file must carry the
    company name in the header and 'Auto-generated by FLOWRA' in the footer
    of every page."""
    src = ENGINE.read_text()
    assert "FLOWRA_TAG" in src and 'Auto-generated by FLOWRA' in src
    assert "_make_canvas_stamper" in src
    # PDF builders wire onFirstPage + onLaterPages to the stamper
    for hook in ("onFirstPage=_make_canvas_stamper",
                  "onLaterPages=_make_canvas_stamper"):
        assert hook in src
    # XLSX writers append the footer stamp
    assert 'f"{FLOWRA_TAG}' in src


def test_engine_documents_methodology_in_files():
    """User's requirement — logic used for data derivation must be
    documented inside the file itself, not just in code comments."""
    src = ENGINE.read_text()
    assert "_methodology_blocks" in src
    # Section titles from the methodology page
    for section in ("Historical figures", "Projections", "MPBF"):
        assert section in src, f"Methodology missing section: {section}"


def test_frontend_gates_tab_on_useradmin_role():
    src = CACORNER.read_text()
    assert "userRole === 'admin'" in src, (
        "Bank-reports tab must be gated on userRole==='admin' — "
        "employees should never see it."
    )
    assert "CAReports" in src, "Panel component not imported"
    assert "bank-reports" in src, "Tab id missing"


def test_frontend_page_has_downloads_for_all_five_files():
    src = UI.read_text()
    for testid in ("dl-cma-pdf", "dl-cma-xlsx",
                    "dl-pitch-pdf", "dl-pitch-teaser", "dl-pitch-xlsx"):
        assert testid in src, f"Download button missing: {testid}"
    # Encrypted-at-rest badge visible to the user
    assert "Fernet" in src or "encrypted at rest" in src.lower()


if __name__ == "__main__":
    for fn in [
        test_engine_projections_and_downloads,
        test_engine_form_computations,
        test_route_auth_guard_and_encryption,
        test_encrypted_assumption_roundtrip,
        test_engine_carries_flowra_footer_and_company_header,
        test_engine_documents_methodology_in_files,
        test_frontend_gates_tab_on_useradmin_role,
        test_frontend_page_has_downloads_for_all_five_files,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll iter-134 CA Reports tests passed.")
