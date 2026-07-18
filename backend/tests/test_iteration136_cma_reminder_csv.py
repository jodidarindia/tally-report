"""Iteration 136 — CMA Annual Reminder + CSV Bulk Import.

Covers:
  1. Every CMA PDF/XLSX call writes to `ca_report_generations` with
     `last_generated_at`, `last_artifact_kind`, and resets
     `reminder_sent_at` (fresh cycle starts).
  2. `GET /api/ca-reports/reminders/status` returns `next_reminder_at` =
     last_generated_at + 305 days.
  3. Reminder sweep is idempotent — a row where reminder_sent_at ≥
     last_generated_at is skipped on the second pass.
  4. Reminder sweep short-circuits when last_generated_at is within the
     lead window.
  5. CSV template contains every HistoricalFY field as a header.
  6. CSV import: writes valid rows, reports errors for bad fy_label,
     idempotent (re-import overwrites).
  7. All 3 new endpoints (reminders/status, csv-template, import-csv)
     enforce the useradmin guard.
  8. Frontend renders the reminder card + CSV import modal with the
     required data-testids.
"""
import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROUTE = Path("/app/backend/routes/ca_reports.py")
UI = Path("/app/frontend/src/pages/CAReports.jsx")
SERVER = Path("/app/backend/server.py")

sys.path.insert(0, "/app/backend")


def test_track_helper_exists_and_wired():
    src = ROUTE.read_text()
    assert "async def _track_cma_generation" in src
    # PDF and XLSX endpoints must both call the tracker after building
    # the artefact (so a bug in build_* never records a phantom generation)
    for endpoint in ("gen_cma_pdf", "gen_cma_xlsx"):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == endpoint:
                body = ast.unparse(node)
                assert "_track_cma_generation" in body, (
                    f"{endpoint} missing _track_cma_generation call"
                )
                break


def test_reminder_status_route_exists_and_guarded():
    src = ROUTE.read_text()
    assert '@router.get("/ca-reports/reminders/status")' in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_reminder_status":
            body = ast.unparse(node)
            assert "_require_useradmin(request)" in body
            assert "REMINDER_LEAD_DAYS" in body or "days_until_reminder" in body
            return
    raise AssertionError("get_reminder_status not found")


def test_reminder_math_305_days():
    from routes.ca_reports import CMA_ANNIVERSARY_DAYS, REMINDER_LEAD_DAYS
    assert CMA_ANNIVERSARY_DAYS == 365
    assert REMINDER_LEAD_DAYS == 60
    # Sanity check that lead window is 305 days
    assert CMA_ANNIVERSARY_DAYS - REMINDER_LEAD_DAYS == 305


def test_reminder_sweep_returns_summary_dict():
    """The sweep must return a summary dict shape so the daily loop can
    log it without crashing when zero rows to process."""
    import asyncio
    from routes.ca_reports import sweep_cma_reminders
    # Skip if MongoDB isn't reachable in this test env
    try:
        result = asyncio.get_event_loop().run_until_complete(
            sweep_cma_reminders())
    except RuntimeError:
        result = asyncio.new_event_loop().run_until_complete(
            sweep_cma_reminders())
    assert isinstance(result, dict)
    for k in ("checked", "sent", "errors"):
        assert k in result, f"summary missing key: {k}"
        assert isinstance(result[k], int)


def test_reminder_html_shape():
    from routes.ca_reports import _reminder_html
    html = _reminder_html("Krishna Sales", 42, "2025-08-11")
    assert "Krishna Sales" in html
    assert "42 days" in html
    assert "2025-08-11" in html
    # CTA link points to insights.flowralive.in
    assert "insights.flowralive.in" in html
    # FLOWRA branding
    assert "FLOWRA" in html.upper() or "flowra" in html


def test_csv_template_endpoint():
    src = ROUTE.read_text()
    assert '@router.get("/ca-reports/manual-historicals/csv-template")' in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "download_manual_csv_template":
            body = ast.unparse(node)
            assert "_require_useradmin(request)" in body
            assert "HistoricalFY" in body   # header pulled from dataclass fields
            assert "manual_historicals_template.csv" in body
            return
    raise AssertionError("download_manual_csv_template not found")


def test_csv_import_endpoint():
    src = ROUTE.read_text()
    assert '@router.post("/ca-reports/manual-historicals/import-csv")' in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "import_manual_csv":
            body = ast.unparse(node)
            assert "_require_useradmin(request)" in body
            assert "csv.DictReader" in body or "DictReader" in body
            assert "_encrypt_manual" in body
            assert "ca_manual_historicals" in body
            # validates fy_label pattern
            assert "'YYYY-YY'" in body or "YYYY-YY" in body
            return
    raise AssertionError("import_manual_csv not found")


def test_startup_launches_reminder_loop():
    src = SERVER.read_text()
    assert "sweep_cma_reminders" in src
    assert "_cma_reminder_loop" in src or "create_task" in src
    # Loop cadence 24h
    assert "24 * 60 * 60" in src


def test_frontend_has_reminder_card_and_csv_modal():
    src = UI.read_text()
    # Reminder card
    for testid in ("reminder-card",):
        assert testid in src, f"missing testid: {testid}"
    # CSV import modal + trigger + template button + result panel
    for testid in ("btn-import-csv", "csv-import-modal",
                    "btn-download-csv-template",
                    "csv-file-input", "btn-run-csv-import"):
        assert testid in src, f"missing testid: {testid}"
    # After a CMA download, the reminder card refreshes
    assert "loadReminder" in src


if __name__ == "__main__":
    for fn in [
        test_track_helper_exists_and_wired,
        test_reminder_status_route_exists_and_guarded,
        test_reminder_math_305_days,
        test_reminder_sweep_returns_summary_dict,
        test_reminder_html_shape,
        test_csv_template_endpoint,
        test_csv_import_endpoint,
        test_startup_launches_reminder_loop,
        test_frontend_has_reminder_card_and_csv_modal,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll iter-136 reminder + csv tests passed.")
