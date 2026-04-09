from fastapi import FastAPI, APIRouter, Request, Response
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import time
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

# Create the main app
app = FastAPI(title="FLOWRA - Organize. Automate. Accelerate.")

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

# Include the combined router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Rate limiting store
_rate_limit_store = defaultdict(list)
RATE_LIMIT_AUTH = 20  # max attempts per window
RATE_LIMIT_WINDOW = 60  # seconds


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Rate limiting on auth endpoints
    if request.url.path.startswith("/api/auth/login"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Clean old entries
        _rate_limit_store[client_ip] = [
            t for t in _rate_limit_store[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]
        if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_AUTH:
            return Response(
                content='{"success":false,"error":"Too many login attempts. Please wait."}',
                status_code=429,
                media_type="application/json"
            )
        _rate_limit_store[client_ip].append(now)

    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    return response


@app.on_event("startup")
async def startup_event():
    await seed_admin(db)
    logger.info("Admin user seeded")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
