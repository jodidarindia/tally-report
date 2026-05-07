"""Backup & Data Export routes — Tier 1 (free, on current pod).

Permission split:
  - SuperAdmin → /super-admin/backups/*  (full DB dumps via `scripts/backup_mongo.sh`)
  - Tenant Admin → /admin/data-export    (own-tenant JSON snapshot for DPDP portability)

See /app/memory/DATABASE_STRATEGY.md for the migration plan to Atlas (Tier 2).
"""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from datetime import datetime, timezone
import os
import io
import json
import asyncio
import logging
import zipfile
import subprocess
from pathlib import Path

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context
from services.audit_service import log_audit, get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter()

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/app/backups"))
BACKUP_SCRIPT = "/app/scripts/backup_mongo.sh"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════
# SUPER ADMIN — full DB dumps
# ═══════════════════════════════════════════════════════

async def _require_super_admin(request: Request):
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return None
    return user


@router.get("/super-admin/backups")
async def list_backups(request: Request):
    """List all on-disk backups (newest first)."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        files = sorted(BACKUP_DIR.glob("flowra_backup_*.archive.gz"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        backups = [{
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
        } for p in files]
        return APIResponse(success=True, data={
            "backups": backups,
            "count": len(backups),
            "backup_dir": str(BACKUP_DIR),
            "script": BACKUP_SCRIPT,
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/super-admin/backups/run")
async def run_backup_now(request: Request):
    """Trigger an on-demand backup. Runs the same shell script as the cron."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    if not Path(BACKUP_SCRIPT).exists():
        return APIResponse(success=False, error=f"Backup script not found: {BACKUP_SCRIPT}")
    try:
        # Run script asynchronously (with a generous 5-min timeout)
        proc = await asyncio.create_subprocess_exec(
            "bash", BACKUP_SCRIPT,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            return APIResponse(success=False, error="Backup timed out after 5 minutes")
        if proc.returncode != 0:
            err = (stderr or b"").decode(errors="ignore")[-500:]
            return APIResponse(success=False, error=f"Backup script failed (exit {proc.returncode}): {err}")
        log = (stdout or b"").decode(errors="ignore")[-500:]
        await log_audit(
            "super_admin.backup_run",
            sa.get("username", ""),
            details=log,
            ip_address=get_client_ip(request),
        )
        return APIResponse(success=True, message="Backup completed", data={"log": log})
    except Exception as e:
        logger.exception("Backup run error")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/backups/download/{filename}")
async def download_backup(filename: str, request: Request):
    """Stream a backup archive to the SuperAdmin."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    # Path traversal guard
    if "/" in filename or ".." in filename or not filename.startswith("flowra_backup_"):
        return APIResponse(success=False, error="Invalid filename")
    fp = BACKUP_DIR / filename
    if not fp.exists():
        return APIResponse(success=False, error="Backup not found")
    await log_audit(
        "super_admin.backup_download",
        sa.get("username", ""),
        target=filename,
        ip_address=get_client_ip(request),
    )
    return FileResponse(fp, media_type="application/gzip", filename=filename)


@router.delete("/super-admin/backups/{filename}")
async def delete_backup(filename: str, request: Request):
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    if "/" in filename or ".." in filename or not filename.startswith("flowra_backup_"):
        return APIResponse(success=False, error="Invalid filename")
    fp = BACKUP_DIR / filename
    if not fp.exists():
        return APIResponse(success=False, error="Backup not found")
    fp.unlink()
    await log_audit(
        "super_admin.backup_delete",
        sa.get("username", ""),
        target=filename,
        ip_address=get_client_ip(request),
    )
    return APIResponse(success=True, message="Backup deleted")


# ═══════════════════════════════════════════════════════
# TENANT ADMIN — own-tenant data export (DPDP right-to-portability)
# ═══════════════════════════════════════════════════════

# Collections to include in tenant export.
# These are tenant-scoped (each doc has tenant_id) — we filter strictly to the
# requesting admin's tenant. SuperAdmin-only collections (e.g., users, audit_logs
# system-wide) are intentionally excluded.
TENANT_COLLECTIONS = [
    "customers", "creditors", "all_ledgers", "branch_ledgers",
    "sales_vouchers", "purchase_vouchers", "credit_notes", "debit_notes",
    "receipt_vouchers", "payment_vouchers", "journal_vouchers", "contra_vouchers",
    "inventory_items", "salesman_master", "salesman_beats", "beat_runs",
    "salesman_orders", "dispatch_cards", "dispatch_porters", "dispatch_transporters",
    "profit_loss", "ai_queries", "ai_reports", "questionnaires", "prospects",
]


@router.get("/admin/data-export")
async def export_tenant_data(request: Request):
    """Stream a ZIP containing one JSON file per collection for the admin's tenant.

    DPDP Act 2023 right-to-portability compliant: the admin can download all
    data their tenant owns. NO cross-tenant data is included (server enforces
    tenant_id filter on every collection). NO password hashes or tokens are
    included (the `users` collection is excluded entirely).
    """
    user = await get_current_user(request, db)
    if not user or user.get("role") not in ("admin", "super_admin"):
        return APIResponse(success=False, error="Admin access required")
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return APIResponse(success=False, error="No tenant context")

    # Collect data
    payload = {}
    counts = {}
    for col in TENANT_COLLECTIONS:
        try:
            cur = db[col].find({"tenant_id": tenant_id}, {"_id": 0})
            docs = await cur.to_list(100000)
            payload[col] = docs
            counts[col] = len(docs)
        except Exception as e:
            logger.warning(f"Export skipped {col}: {e}")
            payload[col] = []
            counts[col] = 0

    # Build ZIP in memory
    buf = io.BytesIO()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest
        manifest = {
            "tenant_id": tenant_id,
            "exported_by": user.get("username", ""),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "json-per-collection",
            "counts": counts,
            "total_documents": sum(counts.values()),
            "license": "Your data, your rights (DPDP 2023). Re-import via FLOWRA support.",
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        for col, docs in payload.items():
            zf.writestr(f"{col}.json", json.dumps(docs, indent=2, default=str))

    buf.seek(0)
    fname = f"flowra_data_export_{tenant_id[:8]}_{ts}.zip"
    await log_audit(
        "admin.data_export",
        user.get("username", ""),
        tenant_id=tenant_id,
        details=f"counts={counts}, filename={fname}",
        ip_address=get_client_ip(request),
    )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/admin/data-export/preview")
async def export_preview(request: Request):
    """Quick row-count summary so admin can see what's in their export
    BEFORE clicking Download. Doesn't actually generate the ZIP."""
    user = await get_current_user(request, db)
    if not user or user.get("role") not in ("admin", "super_admin"):
        return APIResponse(success=False, error="Admin access required")
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return APIResponse(success=False, error="No tenant context")
    counts = {}
    for col in TENANT_COLLECTIONS:
        try:
            counts[col] = await db[col].count_documents({"tenant_id": tenant_id})
        except Exception:
            counts[col] = 0
    return APIResponse(success=True, data={
        "counts": counts,
        "total_documents": sum(counts.values()),
        "tenant_id": tenant_id,
    })
