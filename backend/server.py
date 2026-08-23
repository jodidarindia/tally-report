from fastapi import FastAPI, APIRouter, Request, Response
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import time
import re
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

from db import db, client
from services.auth_service import seed_admin

# Route modules
from routes.auth import router as auth_router
from routes.tally import router as tally_router
from routes.inventory import router as inventory_router
from routes.sales import router as sales_router
from routes.sync import router as sync_router
from routes.ai_reports import router as ai_reports_router
from routes.customers import router as customers_router
from routes.dashboard import router as dashboard_router
from routes.salesman import router as salesman_router
from routes.super_admin import router as super_admin_router
from routes.audit import router as audit_router
from routes.insights import router as insights_router
from routes.prospects import router as prospects_router
from routes.seller_panel import router as seller_panel_router
from routes.branch_ledgers import router as branch_ledgers_router
from routes.referrals import router as referrals_router
from routes.ca_corner import router as ca_corner_router
from routes.ca_reports import router as ca_reports_router
from routes.gdrive import router as gdrive_router
from routes.questionnaire import router as questionnaire_router
from routes.billing import router as billing_router
from routes.support_tickets import router as support_tickets_router
from routes.dispatch import router as dispatch_router
from routes.salesman_orders import router as salesman_orders_router
from routes.backups import router as backups_router
from routes.creditors import router as creditors_router
from routes.academy import router as academy_router
from routes.forecast import router as forecast_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

# Create the main app
app = FastAPI(title="FLOWRA - Organize. Automate. Accelerate.", docs_url=None, redoc_url=None)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Include all route modules
api_router.include_router(auth_router)
api_router.include_router(tally_router)
api_router.include_router(inventory_router)
api_router.include_router(sales_router)
api_router.include_router(sync_router)
api_router.include_router(ai_reports_router)
api_router.include_router(customers_router)
api_router.include_router(dashboard_router)
api_router.include_router(salesman_router)
api_router.include_router(super_admin_router)
api_router.include_router(seller_panel_router)
api_router.include_router(branch_ledgers_router)
api_router.include_router(audit_router)
api_router.include_router(insights_router)
api_router.include_router(prospects_router)
api_router.include_router(referrals_router)
api_router.include_router(ca_corner_router)
api_router.include_router(ca_reports_router)
api_router.include_router(gdrive_router)
api_router.include_router(questionnaire_router)
api_router.include_router(billing_router)
api_router.include_router(support_tickets_router)
api_router.include_router(dispatch_router)
api_router.include_router(salesman_orders_router)
api_router.include_router(backups_router)
api_router.include_router(creditors_router)
api_router.include_router(academy_router)
api_router.include_router(forecast_router)


# ── Health endpoint (k8s / Atlas liveness probe + uptime monitor) ──────
@api_router.get("/health")
async def health():
    """Lightweight ping that also pokes Mongo so we know the DB link is alive.

    Returns 200 + {ok: True, db: 'connected'} when the API is reachable AND
    can run a 1-document command against the configured Atlas cluster. If
    Mongo fails, returns ok=True (API alive) + db='disconnected' so a
    monitor can distinguish DB outages from app outages.
    """
    from db import db
    db_status = "connected"
    try:
        await db.command("ping")
    except Exception as e:  # noqa: BLE001
        db_status = f"disconnected: {type(e).__name__}"
    return {"ok": True, "db": db_status, "service": "flowra-backend"}


# Include the combined router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Company-ID", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# Rate limiting store
_rate_limit_store = defaultdict(list)
RATE_LIMIT_AUTH = 10  # max login attempts per window
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_API = 200  # max API calls per window
RATE_LIMIT_SIGNUP = 3  # max signup attempts per hour

# NoSQL injection patterns
NOSQL_PATTERNS = re.compile(r'(\$where|\$regex|\$gt|\$lt|\$ne|\$in|\$nin|\$or|\$and|\$not|\$exists|\$elemMatch)', re.IGNORECASE)


def _sanitize_input(value):
    """Prevent NoSQL injection by rejecting MongoDB operators in user input."""
    if isinstance(value, str) and NOSQL_PATTERNS.search(value):
        return None
    if isinstance(value, dict):
        for k in value:
            if k.startswith('$'):
                return None
    return value


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    path = request.url.path

    # Rate limiting on auth endpoints
    if path.startswith("/api/auth/login"):
        _rate_limit_store[f"auth:{client_ip}"] = [
            t for t in _rate_limit_store[f"auth:{client_ip}"] if now - t < RATE_LIMIT_WINDOW
        ]
        if len(_rate_limit_store[f"auth:{client_ip}"]) >= RATE_LIMIT_AUTH:
            return Response(
                content='{"success":false,"error":"Too many login attempts. Please wait 60 seconds."}',
                status_code=429,
                media_type="application/json"
            )
        _rate_limit_store[f"auth:{client_ip}"].append(now)

    # Rate limiting on signup
    if path.startswith("/api/public/signup"):
        _rate_limit_store[f"signup:{client_ip}"] = [
            t for t in _rate_limit_store[f"signup:{client_ip}"] if now - t < 3600
        ]
        if len(_rate_limit_store[f"signup:{client_ip}"]) >= RATE_LIMIT_SIGNUP:
            return Response(
                content='{"success":false,"error":"Too many signup attempts. Please try again later."}',
                status_code=429,
                media_type="application/json"
            )
        _rate_limit_store[f"signup:{client_ip}"].append(now)

    # General API rate limiting
    if path.startswith("/api/") and not path.startswith("/api/public/"):
        _rate_limit_store[f"api:{client_ip}"] = [
            t for t in _rate_limit_store[f"api:{client_ip}"] if now - t < RATE_LIMIT_WINDOW
        ]
        if len(_rate_limit_store[f"api:{client_ip}"]) >= RATE_LIMIT_API:
            return Response(
                content='{"success":false,"error":"Rate limit exceeded. Please slow down."}',
                status_code=429,
                media_type="application/json"
            )
        _rate_limit_store[f"api:{client_ip}"].append(now)

    # Block oversized payloads. 100 MB is enough for the largest full-sync
    # batch we have seen from production agents (Krishna Sales ~7,500 stock
    # items + 4,500 sales vouchers ≈ 30 MB JSON). The matching nginx
    # `client_max_body_size 100M` on the droplet vhost completes the chain.
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 100 * 1024 * 1024:
        return Response(
            content='{"success":false,"error":"Request too large (>100MB)"}',
            status_code=413,
            media_type="application/json"
        )

    response = await call_next(request)

    # Comprehensive security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https: wss:"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"

    return response


@app.on_event("startup")
async def startup_event():
    await seed_admin(db)
    logger.info("Admin user seeded")
    await ensure_indexes(db)
    logger.info("MongoDB indexes ensured")
    # v135 — background sweep for CMA annual reminders. Runs every 24h;
    # each sweep is idempotent (marks reminder_sent_at so a second run
    # in the same cycle doesn't duplicate emails).
    import asyncio as _asyncio
    from routes.ca_reports import sweep_cma_reminders

    async def _cma_reminder_loop():
        # Small stagger so we don't hit Resend hard on server boot.
        await _asyncio.sleep(60)
        while True:
            try:
                await sweep_cma_reminders()
            except Exception as e:
                logger.warning(f"CMA reminder sweep errored: {e}")
            await _asyncio.sleep(24 * 60 * 60)   # 24 hours

    _asyncio.create_task(_cma_reminder_loop())

    # Phase A.6 — Nightly trial reminder sweep. Every 6h we check for
    # trial users hitting day 5/8/12/14 and fire the appropriate email
    # (dedup via `trial_reminders_sent` on the user doc). We also mark
    # accounts inactive on day 14+ so the /auth/me endpoint stops
    # renewing their session.
    from services.trial_service import (
        get_users_due_for_reminder, mark_reminder_sent,
        trial_days_remaining, parse_iso,
    )
    from services.email_service import (
        send_trial_reminder_day5, send_trial_reminder_day8,
        send_trial_reminder_day12, send_trial_reminder_day14,
    )

    _TRIAL_SENDERS = {
        5: send_trial_reminder_day5,
        8: send_trial_reminder_day8,
        12: send_trial_reminder_day12,
        14: send_trial_reminder_day14,
    }

    async def _trial_reminder_loop():
        # Small stagger so we don't collide with the CMA sweep on boot.
        await _asyncio.sleep(90)
        while True:
            try:
                due = await get_users_due_for_reminder()
                for user, day in due:
                    sender = _TRIAL_SENDERS.get(day)
                    if not sender:
                        continue
                    days_left = trial_days_remaining(user) or 0
                    trial_end_disp = ""
                    end_dt = parse_iso(user.get("trial_end", ""))
                    if end_dt:
                        trial_end_disp = end_dt.strftime("%d %b %Y")
                    try:
                        if day == 14:
                            ok = await sender(user["username"], user.get("name", ""), trial_end_disp)
                        else:
                            ok = await sender(user["username"], user.get("name", ""), days_left, trial_end_disp)
                        if ok:
                            await mark_reminder_sent(user["username"], day)
                            logger.info(f"trial reminder day-{day} sent to {user['username']}")
                    except Exception as e:
                        logger.warning(f"trial reminder day-{day} failed for {user.get('username')}: {e}")
            except Exception as e:
                logger.warning(f"trial reminder sweep errored: {e}")
            await _asyncio.sleep(6 * 60 * 60)   # every 6h

    _asyncio.create_task(_trial_reminder_loop())


async def ensure_indexes(db):
    """Idempotent — safe to call on every startup. MongoDB will skip if already
    present. These speed up the most common BS / P&L / CRM / Inventory queries
    by 5-20× once the DB grows past 100K vouchers per tenant."""
    try:
        # Tenant + company scoped reads (covers every multi-tenant route)
        for coll in ('sales_vouchers', 'purchase_vouchers', 'receipt_vouchers',
                     'credit_notes', 'debit_notes', 'journal_vouchers',
                     'stock_journals', 'contra_vouchers'):
            await db[coll].create_index([('tenant_id', 1), ('company_id', 1), ('voucher_date', 1)],
                                          name='tcid_vdate', background=True)
            await db[coll].create_index([('tenant_id', 1), ('company_id', 1), ('voucher_number', 1)],
                                          name='tcid_vnum', background=True)
        # v1.5.6 — Migrate legacy `tcid_iname` UNIQUE index (on
        # tenant+company+item_name) to `tcid_iid` UNIQUE (on
        # tenant+company+item_id). Busy legitimately ships multiple SKUs
        # sharing an Alias/PrintName ("Widget A" vs "Widget A" with
        # different codes), and the v1.5.5 sync upserts by item_id — so
        # the old name-based unique constraint drops rows every tick.
        try:
            await db.inventory_items.drop_index('tcid_iname')
        except Exception:
            pass  # index may not exist on fresh DBs / already dropped
        await db.inventory_items.create_index([('tenant_id', 1), ('company_id', 1), ('item_id', 1)],
                                                name='tcid_iid', background=True, unique=True)
        # Keep the item_name index for search — NON-unique.
        await db.inventory_items.create_index([('tenant_id', 1), ('company_id', 1), ('item_name', 1)],
                                                name='tcid_iname', background=True)
        await db.inventory_items.create_index([('tenant_id', 1), ('company_id', 1), ('stock_group', 1)],
                                                name='tcid_sgrp', background=True)
        await db.customers.create_index([('tenant_id', 1), ('company_id', 1), ('customer_name', 1)],
                                          name='tcid_cname', background=True)
        await db.all_ledgers.create_index([('tenant_id', 1), ('company_id', 1), ('parent_group', 1)],
                                            name='tcid_pgrp', background=True)
        await db.all_ledgers.create_index([('tenant_id', 1), ('company_id', 1), ('ledger_name', 1)],
                                            name='tcid_lname', background=True)
        await db.sundry_creditors.create_index([('tenant_id', 1), ('company_id', 1)],
                                                 name='tcid', background=True)
        await db.beat_runs.create_index([('tenant_id', 1), ('company_id', 1), ('run_date', 1), ('salesman', 1)],
                                          name='tcid_rdate_sm', background=True)
        await db.salesman_orders.create_index([('tenant_id', 1), ('company_id', 1), ('status', 1), ('created_at', 1)],
                                                name='tcid_status', background=True)
        await db.audit_logs.create_index([('tenant_id', 1), ('timestamp', -1)],
                                           name='tid_ts_desc', background=True)
        await db.dispatch_cards.create_index([('tenant_id', 1), ('company_id', 1), ('dispatch_date', 1)],
                                                name='tcid_ddate', background=True)
    except Exception as e:
        logger.warning(f"ensure_indexes: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
