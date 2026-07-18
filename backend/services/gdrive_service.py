"""
Google Drive service — per-tenant OAuth 2.0 integration.

Design contract:
  * ONE Google Cloud OAuth app owned by FLOWRA; every tenant's useradmin
    consents to it once. Scope = `drive.file` (sandboxed — FLOWRA can
    ONLY see files it creates; the user's other Drive contents remain
    invisible to us).
  * refresh_token stored per (tenant_id, company_id) — Fernet-AES-128
    encrypted at rest via services.encryption_service. access_token is
    NEVER persisted; it's derived on demand and expires in ~1h.
  * File uploads stream from the FastAPI UploadFile directly into Drive
    with NO local disk write. FLOWRA never holds a copy.
  * Folder tree in the user's Drive:
        My Drive
         └─ FLOWRA Documents            ← root, created on first upload
             └─ <Company Name>          ← one per company_id
                 └─ Dispatch
                     └─ <YYYY-MM>       ← auto-partitioned monthly
                         └─ <files>
    Folder IDs are cached in the connection doc so we don't scan Drive
    on every upload.
  * Strict tenant + company isolation — every operation queries
    `{tenant_id, company_id}`. Even if two tenants share a Google
    account (unusual), they'd upload to different sub-folders.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from services.encryption_service import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"
FLOWRA_ROOT_FOLDER_NAME = "FLOWRA Documents"


class GDriveNotConnected(Exception):
    """Raised when the tenant's useradmin has not connected a Drive yet.
    Route layer surfaces this as HTTP 400."""


class GDriveRevoked(Exception):
    """The stored refresh_token no longer works — user revoked us in
    Google Account settings, or their account was disabled."""


def _oauth_config() -> Dict[str, Any]:
    """Assemble the client_config dict for google-auth-oauthlib."""
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect = os.environ.get("GOOGLE_DRIVE_REDIRECT_URI")
    if not (cid and csec and redirect):
        raise RuntimeError(
            "Google Drive integration is not configured. Set "
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and "
            "GOOGLE_DRIVE_REDIRECT_URI in backend/.env.")
    return {
        "web": {
            "client_id": cid,
            "client_secret": csec,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [redirect],
        }
    }


def build_authorization_url(state: str) -> str:
    """Return the Google consent URL to redirect the user to.
    `state` carries `<tenant_id>:<company_id>` so the callback can
    scope the credential correctly."""
    flow = Flow.from_client_config(
        _oauth_config(),
        scopes=DRIVE_SCOPES,
        redirect_uri=os.environ["GOOGLE_DRIVE_REDIRECT_URI"],
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",            # forces refresh_token every time
        state=state,
    )
    return auth_url


def exchange_code_for_credentials(code: str) -> Credentials:
    """Second half of the OAuth dance: swap the authorization code for
    a Credentials object."""
    flow = Flow.from_client_config(
        _oauth_config(),
        scopes=None,   # accept whatever scopes Google granted (userinfo etc.)
        redirect_uri=os.environ["GOOGLE_DRIVE_REDIRECT_URI"],
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    granted = set(creds.scopes or [])
    if "https://www.googleapis.com/auth/drive.file" not in granted:
        raise GDriveRevoked(
            "The `drive.file` scope was not granted — cannot upload files.")
    return creds


def _hydrate_credentials(doc: Dict[str, Any]) -> Credentials:
    """Recreate a Credentials object from an encrypted connection doc."""
    try:
        refresh = decrypt_field(doc["refresh_token_encrypted"])
    except Exception as e:
        raise GDriveRevoked(f"Stored refresh_token corrupted: {e}")
    return Credentials(
        token=None,   # will be refreshed on first request
        refresh_token=refresh,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=DRIVE_SCOPES,
    )


def _refresh(creds: Credentials) -> Credentials:
    try:
        creds.refresh(GoogleRequest())
    except Exception as e:
        # invalid_grant → user revoked or changed password w/ session tied
        msg = str(e).lower()
        if "invalid_grant" in msg or "token has been expired" in msg:
            raise GDriveRevoked(
                "Google refresh_token is invalid — the user probably "
                "revoked FLOWRA in Google Account settings.")
        raise
    return creds


def _get_service(doc: Dict[str, Any]):
    creds = _hydrate_credentials(doc)
    creds = _refresh(creds)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def revoke_credentials(doc: Dict[str, Any]) -> None:
    """Tell Google to revoke the stored refresh_token upstream. Safe to
    call even if the token is already invalid."""
    import requests
    try:
        refresh = decrypt_field(doc["refresh_token_encrypted"])
    except Exception:
        return
    try:
        requests.post(GOOGLE_REVOKE_URI, params={"token": refresh},
                        headers={"Content-Type":
                                    "application/x-www-form-urlencoded"},
                        timeout=10)
    except Exception as e:
        logger.warning(f"Upstream revoke call failed (non-fatal): {e}")


# ─── Folder helpers ──────────────────────────────────────────────────────

def _find_folder(service, name: str, parent_id: Optional[str]) -> Optional[str]:
    """Return the ID of an existing folder that FLOWRA created, or None."""
    parent_clause = (f"and '{parent_id}' in parents"
                      if parent_id else "and 'root' in parents")
    q = (f"name = '{name.replace(chr(39), chr(92) + chr(39))}' "
          f"and mimeType = 'application/vnd.google-apps.folder' "
          f"and trashed = false "
          f"{parent_clause}")
    try:
        resp = service.files().list(
            q=q, fields="files(id,name)", pageSize=5,
            spaces="drive").execute()
    except HttpError as e:
        logger.warning(f"folder lookup failed: {e}")
        return None
    files = resp.get("files") or []
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: Optional[str]) -> str:
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    resp = service.files().create(body=body, fields="id").execute()
    return resp["id"]


def _ensure_folder_path(service, path_parts: list[str],
                          cache: Dict[str, str]) -> str:
    """Walk / create the folder chain; return the final folder ID.
    `cache` keeps ID lookups from previous calls (mutated in place)."""
    parent = None
    running_key = ""
    for part in path_parts:
        running_key = f"{running_key}/{part}" if running_key else part
        fid = cache.get(running_key)
        if not fid:
            fid = _find_folder(service, part, parent) or \
                    _create_folder(service, part, parent)
            cache[running_key] = fid
        parent = fid
    return parent   # last-created folder


# ─── The one function that dispatch.py actually calls ────────────────────

def upload_stream(connection_doc: Dict[str, Any],
                    file_bytes: bytes,
                    filename: str,
                    mime_type: str,
                    company_display_name: str,
                    subfolder_path: str = "Dispatch") -> Dict[str, Any]:
    """Stream one file into the useradmin's Drive.

    :param connection_doc: the `gdrive_tenant_connections` row for the
        active (tenant, company) — already scoped by the route layer.
    :param file_bytes: raw file content read from FastAPI UploadFile.
        (We read to memory before uploading — the OAuth library needs a
        seekable stream. Never touches local disk.)
    :param filename: display name inside Drive (spaces are OK).
    :param mime_type: e.g. "image/jpeg", "application/pdf".
    :param company_display_name: goes into the folder path so files are
        neatly grouped in the user's Drive.
    :param subfolder_path: additional path inside the company folder,
        e.g. "Dispatch/2026-02".

    :returns: {
        drive_file_id, web_view_link, web_content_link,
        folder_path, folder_id, size_bytes, uploaded_at
    }
    """
    service = _get_service(connection_doc)
    # Cache folder IDs on the connection doc so we don't hit Drive every
    # single upload. Structure:
    # {"FLOWRA Documents": "abc", "FLOWRA Documents/ACME": "def", ...}
    cache: Dict[str, str] = dict(connection_doc.get("folder_cache") or {})

    path_parts = [FLOWRA_ROOT_FOLDER_NAME, company_display_name]
    path_parts.extend([p for p in subfolder_path.split("/") if p])
    folder_id = _ensure_folder_path(service, path_parts, cache)

    stream = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(stream, mimetype=mime_type,
                               chunksize=-1, resumable=False)
    body = {"name": filename, "parents": [folder_id]}
    try:
        resp = service.files().create(
            body=body, media_body=media,
            fields="id,webViewLink,webContentLink,size,mimeType"
        ).execute()
    except HttpError as e:
        # Detect quota / storage errors so the route layer can surface
        # a helpful message
        msg = str(e)
        if "storageQuotaExceeded" in msg or "quotaExceeded" in msg:
            raise RuntimeError(
                "Your Google Drive is full. Free up space or upgrade "
                "your Google storage plan, then retry.")
        raise

    now = datetime.now(timezone.utc).isoformat()
    return {
        "drive_file_id": resp["id"],
        "web_view_link": resp.get("webViewLink"),
        "web_content_link": resp.get("webContentLink"),
        "folder_id": folder_id,
        "folder_path": "/".join(path_parts),
        "size_bytes": int(resp.get("size") or len(file_bytes)),
        "mime_type": resp.get("mimeType", mime_type),
        "uploaded_at": now,
        # returned so the route layer can persist updated cache
        "folder_cache": cache,
    }


def get_email_from_creds(creds: Credentials) -> str:
    """Fetch the email address of the account that just consented.
    Requires the `userinfo.email` scope that Google auto-adds."""
    try:
        service = build("oauth2", "v2", credentials=creds,
                         cache_discovery=False)
        info = service.userinfo().get().execute()
        return info.get("email", "")
    except Exception as e:
        logger.warning(f"userinfo fetch failed: {e}")
        return ""


def credentials_to_persist(creds: Credentials, google_email: str
                             ) -> Dict[str, Any]:
    """Return the dict shape we upsert into `gdrive_tenant_connections`.
    Only refresh_token is encrypted — everything else is safe/plaintext."""
    return {
        "refresh_token_encrypted": encrypt_field(creds.refresh_token or ""),
        "google_email": google_email or "",
        "scope": " ".join(DRIVE_SCOPES),
        "status": "active",
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": datetime.now(timezone.utc).isoformat(),
        "folder_cache": {},   # populated on first upload
    }


# ─── Reusable backup helper (fire-and-forget) ────────────────────────────

async def try_backup_to_drive(db, tenant_id: str, company_id: str,
                                file_bytes: bytes, filename: str,
                                mime_type: str, subfolder: str,
                                company_display_name: str) -> Optional[Dict[str, Any]]:
    """Silently upload a generated file to the tenant's Drive if
    connected. Returns the Drive metadata on success or None if there's
    no connection or the upload fails.

    Callers use this after building an artefact (CMA PDF, XLSX, reports
    export) so users get a Drive copy without blocking the direct
    download response. Fire-and-forget — errors are logged, never raised.
    Strict tenant + company isolation — only the connection scoped to
    (tenant_id, company_id) is used."""
    try:
        conn = await db.gdrive_tenant_connections.find_one(
            {"tenant_id": tenant_id, "company_id": company_id})
        if not conn or not conn.get("refresh_token_encrypted"):
            return None
        result = upload_stream(
            conn, file_bytes, filename, mime_type,
            company_display_name=company_display_name,
            subfolder_path=subfolder)
        await db.gdrive_tenant_connections.update_one(
            {"tenant_id": tenant_id, "company_id": company_id},
            {"$set": {
                "folder_cache": result.get("folder_cache"),
                "last_used_at": result.get("uploaded_at"),
            }})
        return {
            "drive_file_id": result["drive_file_id"],
            "drive_view_link": result["web_view_link"],
            "folder_path": result["folder_path"],
        }
    except GDriveRevoked:
        # Mark connection revoked — dispatch employee's next upload
        # will get a clean error and the UI will prompt reconnect.
        try:
            await db.gdrive_tenant_connections.update_one(
                {"tenant_id": tenant_id, "company_id": company_id},
                {"$set": {"status": "revoked"}})
        except Exception:
            pass
        logger.warning(
            f"Drive backup: refresh_token revoked for tenant={tenant_id}")
        return None
    except Exception as e:
        logger.warning(f"Drive backup failed (non-fatal): {e}")
        return None


async def download_file_bytes(db, tenant_id: str, company_id: str,
                                drive_file_id: str) -> Optional[bytes]:
    """Fetch a file's raw bytes from the tenant's Drive by drive_file_id.
    Returns None on any failure. Used by bulk-download endpoints."""
    from googleapiclient.http import MediaIoBaseDownload
    try:
        conn = await db.gdrive_tenant_connections.find_one(
            {"tenant_id": tenant_id, "company_id": company_id})
        if not conn:
            return None
        service = _get_service(conn)
        req = service.files().get_media(fileId=drive_file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Drive download failed for {drive_file_id}: {e}")
        return None
