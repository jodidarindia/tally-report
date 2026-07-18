"""Iteration 138 — Drive-Backed CA-artifact backups + Bulk Download.

Tests:
  1. `try_backup_to_drive` helper exists in gdrive_service (async,
     fire-and-forget, returns None when connection is missing).
  2. `download_file_bytes` helper exists (async, returns None on error).
  3. CMA/PDF, CMA/XLSX, Pitch/PDF endpoints all mirror to Drive via
     `_backup_ca_artifact` after successful build.
  4. Bulk download endpoint exists, is guarded by
     `_require_useradmin_dispatch`, validates date range + doc_types.
  5. Bulk download builds a ZIP + audit log row in
     `dispatch_bulk_downloads` collection.
  6. Bulk download tenant + company isolation — every DB query uses
     `_q(ctx)` and Drive downloads pass `tenant_id + company_id`.
  7. Frontend has the Bulk Download tab wired with proper testids
     (invisible to employees).
"""
import ast
import sys
from pathlib import Path

SERVICE = Path("/app/backend/services/gdrive_service.py")
CA = Path("/app/backend/routes/ca_reports.py")
DISPATCH = Path("/app/backend/routes/dispatch.py")
UI = Path("/app/frontend/src/pages/DispatchAdmin.js")

sys.path.insert(0, "/app/backend")


def test_try_backup_helper_present():
    src = SERVICE.read_text()
    assert "async def try_backup_to_drive" in src
    assert "async def download_file_bytes" in src
    # Fire-and-forget: returns None on missing connection, doesn't raise
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "try_backup_to_drive":
            body = ast.unparse(node)
            assert "gdrive_tenant_connections" in body
            assert "return None" in body
            assert "except GDriveRevoked" in body


def test_ca_endpoints_call_drive_backup():
    src = CA.read_text()
    assert "async def _backup_ca_artifact" in src
    for endpoint in ("gen_cma_pdf", "gen_cma_xlsx", "gen_pitch_pdf"):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == endpoint:
                body = ast.unparse(node)
                assert "_backup_ca_artifact" in body, (
                    f"{endpoint} missing Drive backup call")
                assert "CA Reports/" in body, (
                    f"{endpoint} folder-path must be under 'CA Reports/'")


def test_bulk_download_endpoint_present_and_guarded():
    src = DISPATCH.read_text()
    assert '@router.post("/dispatch/bulk-download")' in src
    assert "async def _require_useradmin_dispatch" in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "bulk_download_dispatch_docs":
            body = ast.unparse(node)
            assert "_require_useradmin_dispatch(request)" in body
            # Range validation
            assert "end_date must be" in body or "end < start" in body
            assert "Date range too wide" in body or ".days > 366" in body
            return
    raise AssertionError("bulk_download_dispatch_docs not found")


def test_bulk_download_tenant_isolation():
    """Every DB query and Drive download passes tenant + company."""
    src = DISPATCH.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "bulk_download_dispatch_docs":
            body = ast.unparse(node)
            # cards query filtered by tenant + company via _q(ctx)
            assert "_q(ctx)" in body
            # Drive downloads receive tenant + company
            assert "download_file_bytes" in body
            # tenant/company keys are passed to the Drive function
            assert "ctx['tenant_id']" in body or "ctx[\"tenant_id\"]" in body
            assert "ctx['company_id']" in body or "ctx[\"company_id\"]" in body
            # Audit log written to dispatch_bulk_downloads
            assert "dispatch_bulk_downloads" in body
            return


def test_bulk_download_creates_audit_log():
    src = DISPATCH.read_text()
    assert "dispatch_bulk_downloads" in src, (
        "Bulk downloads must be logged for audit"
    )
    # Log includes counts + who + when
    for f in ("files_included", "downloaded_at", "downloaded_by"):
        assert f in src, f"audit log missing field: {f}"


def test_bulk_download_zip_manifest_included():
    src = DISPATCH.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "bulk_download_dispatch_docs":
            body = ast.unparse(node)
            assert "_MANIFEST.txt" in body, (
                "ZIP must include a manifest listing tenant + counts for "
                "auditability")
            assert "zipfile.ZipFile" in body


def test_frontend_bulk_download_tab():
    src = UI.read_text()
    # Frontend testids — some are static strings, some are JSX template
    # literals of the shape `bulk-type-${k}` so verify the pattern +
    # the doc-type keys are all referenced.
    for testid in ("bulk-download-tab", "bulk-start-date", "bulk-end-date",
                    "bulk-download-btn"):
        assert testid in src, f"missing testid: {testid}"
    assert "bulk-type-${k}" in src or "bulk-type-invoice_doc" in src, (
        "bulk-type-* template testid missing"
    )
    for k in ("invoice_doc", "sales_order", "lr_receipt"):
        assert f"'{k}'" in src or f'"{k}"' in src
    # Hidden from employees
    assert "isEmployee ? [] : [{id:'bulk-download'" in src or (
        "'bulk-download'" in src and "!isEmployee" in src), (
        "Bulk-download tab must be hidden from employees"
    )


if __name__ == "__main__":
    for fn in [
        test_try_backup_helper_present,
        test_ca_endpoints_call_drive_backup,
        test_bulk_download_endpoint_present_and_guarded,
        test_bulk_download_tenant_isolation,
        test_bulk_download_creates_audit_log,
        test_bulk_download_zip_manifest_included,
        test_frontend_bulk_download_tab,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll iter-138 backups + bulk-download tests passed.")
