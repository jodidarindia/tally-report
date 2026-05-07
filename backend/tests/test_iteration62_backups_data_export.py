"""Regression tests for Tier-1 Backup System & Tenant Data Export.

Covers /api/super-admin/backups* (full DB dumps) and
/api/admin/data-export* (DPDP right-to-portability ZIP).
"""
import io
import os
import json
import zipfile
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


def _login(u, p):
    r = requests.post(
        f"{API_URL}/api/auth/login",
        json={"username": u, "password": p, "captcha_token": ""},
    )
    r.raise_for_status()
    return r.json()["data"]["token"]


# ─────────────────────────────  SuperAdmin Backups  ─────────────────────────────

def test_list_backups_requires_super_admin():
    """Tenant admin must be denied; superadmin must succeed."""
    admin_h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/super-admin/backups", headers=admin_h)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "super admin" in (body.get("error") or "").lower()

    sa_h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    r = requests.get(f"{API_URL}/api/super-admin/backups", headers=sa_h)
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True
    assert "backups" in d["data"]
    assert isinstance(d["data"]["backups"], list)
    assert d["data"]["backup_dir"]


def test_run_backup_creates_archive_and_lists_it():
    sa_h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}

    # Run
    r = requests.post(f"{API_URL}/api/super-admin/backups/run", headers=sa_h, timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    assert "Backup" in (body.get("message") or "")

    # List
    r = requests.get(f"{API_URL}/api/super-admin/backups", headers=sa_h)
    backups = r.json()["data"]["backups"]
    assert len(backups) >= 1
    fn = backups[0]["filename"]
    assert fn.startswith("flowra_backup_") and fn.endswith(".archive.gz")
    assert backups[0]["size_bytes"] > 0


def test_download_backup_returns_gzip_stream():
    sa_h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    backups = requests.get(f"{API_URL}/api/super-admin/backups", headers=sa_h).json()["data"]["backups"]
    assert backups, "Expected at least one backup from prior test"
    fn = backups[0]["filename"]
    r = requests.get(
        f"{API_URL}/api/super-admin/backups/download/{fn}",
        headers=sa_h, stream=True,
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/gzip"
    # Magic header for gzip = 0x1f 0x8b
    chunk = next(r.iter_content(2))
    assert chunk[:2] == b"\x1f\x8b"


def test_download_path_traversal_blocked():
    sa_h = {"Authorization": f"Bearer {_login('superadmin', 'superadmin123')}"}
    # Should NOT match the regex / prefix guard
    r = requests.get(
        f"{API_URL}/api/super-admin/backups/download/etc-passwd",
        headers=sa_h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "Invalid filename" in (body.get("error") or "") or "Backup not found" in (body.get("error") or "")


# ─────────────────────────────  Tenant Data Export  ─────────────────────────────

def test_data_export_preview_returns_counts():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/admin/data-export/preview", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    d = body["data"]
    assert "counts" in d and isinstance(d["counts"], dict)
    assert d["total_documents"] >= 0
    assert d["tenant_id"]
    # A few collections we expect non-zero on the seeded tenant
    assert d["counts"]["customers"] > 0
    assert d["counts"]["sales_vouchers"] > 0


def test_data_export_zip_is_valid_and_tenant_scoped():
    h = {"Authorization": f"Bearer {_login('admin', 'admin123')}"}
    r = requests.get(f"{API_URL}/api/admin/data-export", headers=h, timeout=180)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in (r.headers.get("content-disposition") or "")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "manifest.json" in names
    assert "customers.json" in names
    assert "sales_vouchers.json" in names
    # No password collection should ever leak
    assert "users.json" not in names
    assert "audit_logs.json" not in names

    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["tenant_id"]
    assert manifest["total_documents"] > 0
    assert manifest["counts"]["customers"] > 0
    assert manifest["exported_by"]


def test_data_export_denied_for_salesman():
    """Salesman role must NOT be able to export tenant data."""
    h = {"Authorization": f"Bearer {_login('ravi@test.com', 'ravi1234')}"}
    r = requests.get(f"{API_URL}/api/admin/data-export/preview", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "Admin access required" in (body.get("error") or "")
