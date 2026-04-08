from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
import os
import logging
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

# Include the combined router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await seed_admin(db)
    logger.info("Admin user seeded")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
