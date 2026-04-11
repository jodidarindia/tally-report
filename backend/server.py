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
api_router.include_router(audit_router)
api_router.include_router(insights_router)
api_router.include_router(prospects_router)

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

    # Block oversized payloads (10MB max)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        return Response(
            content='{"success":false,"error":"Request too large"}',
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
