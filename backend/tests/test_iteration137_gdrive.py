"""Iteration 137 — Google Drive integration for Dispatch uploads.

Covers:
  1. OAuth service builds a valid Google authorization URL with correct
     scope, offline access, forced consent, and state carrying
     tenant_id:company_id.
  2. `_require_useradmin` guard rejects non-admin roles with 403.
  3. Dispatch upload endpoint enforces hard-mode: rejects with a clear
     error if no gdrive_tenant_connections row exists.
  4. Encrypted refresh_token round-trip via _hydrate_credentials.
  5. Server wires the new gdrive_router.
  6. Frontend has Integrations tab + Connect / Disconnect buttons +
     OAuth callback hash handling.
"""
import ast
import sys
from pathlib import Path

SERVICE = Path("/app/backend/services/gdrive_service.py")
ROUTE = Path("/app/backend/routes/gdrive.py")
DISPATCH = Path("/app/backend/routes/dispatch.py")
SERVER = Path("/app/backend/server.py")
UI = Path("/app/frontend/src/pages/ProfileModal.js")

sys.path.insert(0, "/app/backend")


def test_oauth_url_contains_expected_params():
    """The `build_authorization_url` helper must produce a valid Google
    consent URL with the safest defaults."""
    import os
    os.environ.setdefault(
        "GOOGLE_CLIENT_ID", "537491921642-test.apps.googleusercontent.com")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "GOCSPX-test")
    os.environ.setdefault(
        "GOOGLE_DRIVE_REDIRECT_URI",
        "https://example.test/api/gdrive/oauth/callback")
    from services.gdrive_service import build_authorization_url
    url = build_authorization_url("tenant-abc:company-xyz")
    from urllib.parse import urlparse, parse_qs
    p = urlparse(url)
    assert p.netloc == "accounts.google.com"
    q = parse_qs(p.query)
    assert "https://www.googleapis.com/auth/drive.file" in q.get("scope", [""])[0]
    assert q.get("access_type") == ["offline"]
    assert q.get("prompt") == ["consent"]
    assert q.get("state") == ["tenant-abc:company-xyz"]
    assert "537491921642" in q.get("client_id", [""])[0]


def test_encrypted_credentials_roundtrip():
    from services.gdrive_service import (
        credentials_to_persist, _hydrate_credentials,
    )
    class _Fake:
        refresh_token = "1//0gTESTVALUE"
        token = None
        scopes = ["https://www.googleapis.com/auth/drive.file"]
    doc = credentials_to_persist(_Fake(), "user@example.com")
    assert doc["google_email"] == "user@example.com"
    assert doc["refresh_token_encrypted"] != "1//0gTESTVALUE"
    # Round-trip
    creds = _hydrate_credentials(doc)
    assert creds.refresh_token == "1//0gTESTVALUE"


def test_route_guard_admin_only():
    """Only role='admin' can hit connect/disconnect. Status is open to
    all roles (dispatch employees need to know if uploads will work)."""
    src = ROUTE.read_text()
    tree = ast.parse(src)
    for name in ("start_connect", "disconnect"):
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
                body = ast.unparse(node)
                assert "_require_useradmin(request)" in body, \
                    f"{name} missing admin guard"
                break
    # status endpoint should NOT gate on admin (dispatch needs it too)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_status":
            body = ast.unparse(node)
            assert "_require_useradmin" not in body, \
                "status must be readable by non-admin roles"


def test_dispatch_hard_mode_no_local_disk():
    """After migration, dispatch upload must:
       (a) reject if gdrive_tenant_connections is missing (HARD MODE),
       (b) never write to UPLOAD_DIR on new uploads."""
    src = DISPATCH.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "upload_document":
            body = ast.unparse(node)
            # HARD MODE — checks for the connection row
            assert "gdrive_tenant_connections" in body
            assert "refresh_token_encrypted" in body
            assert "Ask your useradmin" in body or "not connected" in body.lower()
            # No open(local_path, 'wb') / os.path.join(UPLOAD_DIR, ...)
            assert "open(os.path.join(UPLOAD_DIR" not in body, \
                "upload_document must not write to local disk anymore"
            # Uses the Drive upload service
            assert "upload_stream" in body
            return
    raise AssertionError("upload_document not found")


def test_dispatch_stores_drive_metadata_not_local_url():
    """The document record on the card must carry drive_file_id +
    drive_view_link (not a local /api/dispatch/files/... url)."""
    src = DISPATCH.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "upload_document":
            body = ast.unparse(node)
            for key in ("drive_file_id", "drive_view_link", "'gdrive'"):
                assert key in body, f"upload_document missing {key}"
            return


def test_server_wires_gdrive_router():
    src = SERVER.read_text()
    assert "from routes.gdrive import router as gdrive_router" in src
    assert "api_router.include_router(gdrive_router)" in src


def test_frontend_integrations_tab_present():
    src = UI.read_text()
    for testid in ("profile-tab-integrations", "integrations-section",
                    "gdrive-card", "btn-gdrive-connect",
                    "btn-gdrive-disconnect"):
        assert testid in src, f"missing testid: {testid}"
    # OAuth callback hash-handling
    assert "#gdrive-connected=" in src
    assert "#gdrive-error=" in src
    # Confirm-before-disconnect (irreversible for pending uploads)
    assert "window.confirm" in src


def test_frontend_uses_drive_view_link_not_local_url():
    from pathlib import Path
    dt = Path("/app/frontend/src/pages/DispatchTerminal.js").read_text()
    # Every place that renders the "Uploaded" link now falls back through
    # drive_view_link first
    assert "drive_view_link" in dt, \
        "DispatchTerminal must prefer doc.drive_view_link"


if __name__ == "__main__":
    for fn in [
        test_oauth_url_contains_expected_params,
        test_encrypted_credentials_roundtrip,
        test_route_guard_admin_only,
        test_dispatch_hard_mode_no_local_disk,
        test_dispatch_stores_drive_metadata_not_local_url,
        test_server_wires_gdrive_router,
        test_frontend_integrations_tab_present,
        test_frontend_uses_drive_view_link_not_local_url,
    ]:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            sys.exit(1)
    print("\nAll iter-137 gdrive tests passed.")
