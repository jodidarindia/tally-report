from fastapi import FastAPI, APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from models import (
    TallyConnection, TallyConnectionCreate,
    InventoryItem, SalesVoucher,
    AIQuery, AIQueryRequest,
    ExportRequest, APIResponse
)
from services.tally_client import TallyClient
from services.ai_service import AIReportService
from services.export_service import ExportService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Tally SaaS Report Builder")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Global Tally client instance
tally_client_instance = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tally Connection Endpoints
@api_router.post("/tally/connect")
async def connect_tally(connection: TallyConnectionCreate):
    """Configure Tally connection settings"""
    try:
        global tally_client_instance
        
        # Create Tally client
        if connection.connection_type == "rest":
            tally_client_instance = TallyClient(
                connection_type="rest",
                api_key=connection.api_key
            )
        else:
            tally_client_instance = TallyClient(
                connection_type="xml",
                host=connection.host or "localhost",
                port=connection.port or 9000
            )
        
        # Test connection
        is_connected = tally_client_instance.test_connection()
        
        if not is_connected:
            return APIResponse(
                success=False,
                error="Unable to connect to Tally. Please check your settings."
            )
        
        # Save to database
        connection_obj = TallyConnection(**connection.model_dump())
        connection_obj.last_synced = datetime.utcnow()
        
        doc = connection_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc.get('last_synced'):
            doc['last_synced'] = doc['last_synced'].isoformat()
        
        await db.tally_connections.insert_one(doc)
        
        return APIResponse(
            success=True,
            message="Successfully connected to Tally",
            data={"connection_id": connection_obj.id}
        )
    
    except Exception as e:
        logger.error(f"Error connecting to Tally: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/tally/status")
async def get_tally_status():
    """Check Tally connection status"""
    try:
        global tally_client_instance
        
        if not tally_client_instance:
            return APIResponse(
                success=False,
                data={"is_connected": False, "message": "No connection configured"}
            )
        
        is_connected = tally_client_instance.test_connection()
        
        return APIResponse(
            success=True,
            data={
                "is_connected": is_connected,
                "message": "Connected" if is_connected else "Disconnected"
            }
        )
    
    except Exception as e:
        logger.error(f"Error checking Tally status: {e}")
        return APIResponse(success=False, error=str(e))

# Inventory Endpoints
@api_router.get("/inventory/items")
async def get_inventory_items(category: Optional[str] = None, min_quantity: Optional[float] = None):
    """Fetch inventory items from Tally"""
    try:
        global tally_client_instance
        
        if not tally_client_instance:
            # Initialize with default XML connection for demo
            tally_client_instance = TallyClient(connection_type="xml")
        
        filters = {}
        if category:
            filters["category"] = category
        if min_quantity is not None:
            filters["min_quantity"] = min_quantity
        
        items = tally_client_instance.fetch_inventory(filters)
        
        # Save to database
        for item in items:
            inventory_obj = InventoryItem(**item)
            doc = inventory_obj.model_dump()
            doc['last_updated'] = doc['last_updated'].isoformat()
            
            await db.inventory_items.update_one(
                {"item_id": item["item_id"]},
                {"$set": doc},
                upsert=True
            )
        
        return APIResponse(
            success=True,
            data={"items": items, "count": len(items)}
        )
    
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/inventory/summary")
async def get_inventory_summary():
    """Get inventory summary statistics"""
    try:
        items = await db.inventory_items.find({}, {"_id": 0}).to_list(1000)
        
        if not items:
            return APIResponse(
                success=True,
                data={
                    "total_items": 0,
                    "total_value": 0,
                    "low_stock_items": 0,
                    "categories": []
                }
            )
        
        total_items = len(items)
        total_value = sum(item.get("quantity", 0) * item.get("price", 0) for item in items)
        low_stock_items = sum(1 for item in items if item.get("quantity", 0) < item.get("reorder_level", 0))
        categories = list(set(item.get("category") for item in items if item.get("category")))
        
        return APIResponse(
            success=True,
            data={
                "total_items": total_items,
                "total_value": round(total_value, 2),
                "low_stock_items": low_stock_items,
                "categories": categories
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting inventory summary: {e}")
        return APIResponse(success=False, error=str(e))

# Sales Endpoints
@api_router.get("/sales/vouchers")
async def get_sales_vouchers(start_date: Optional[str] = None, end_date: Optional[str] = None, party_name: Optional[str] = None):
    """Fetch sales vouchers from Tally"""
    try:
        global tally_client_instance
        
        if not tally_client_instance:
            tally_client_instance = TallyClient(connection_type="xml")
        
        vouchers = tally_client_instance.fetch_sales_vouchers(start_date, end_date)
        
        # Apply party name filter if provided
        if party_name:
            vouchers = [v for v in vouchers if party_name.lower() in v.get("party_name", "").lower()]
        
        # Save to database
        for voucher in vouchers:
            sales_obj = SalesVoucher(**voucher)
            doc = sales_obj.model_dump()
            doc['last_updated'] = doc['last_updated'].isoformat()
            
            await db.sales_vouchers.update_one(
                {"voucher_id": voucher["voucher_id"]},
                {"$set": doc},
                upsert=True
            )
        
        return APIResponse(
            success=True,
            data={"vouchers": vouchers, "count": len(vouchers)}
        )
    
    except Exception as e:
        logger.error(f"Error fetching sales vouchers: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/sales/summary")
async def get_sales_summary():
    """Get sales summary statistics"""
    try:
        vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(1000)
        
        if not vouchers:
            return APIResponse(
                success=True,
                data={
                    "total_vouchers": 0,
                    "total_sales": 0,
                    "top_customers": [],
                    "recent_vouchers": []
                }
            )
        
        total_vouchers = len(vouchers)
        total_sales = sum(v.get("total_amount", 0) for v in vouchers)
        
        # Top customers
        customer_sales = {}
        for v in vouchers:
            party = v.get("party_name", "Unknown")
            customer_sales[party] = customer_sales.get(party, 0) + v.get("total_amount", 0)
        
        top_customers = sorted(
            [{"name": k, "total": v} for k, v in customer_sales.items()],
            key=lambda x: x["total"],
            reverse=True
        )[:5]
        
        # Recent vouchers
        recent_vouchers = sorted(
            vouchers,
            key=lambda x: x.get("voucher_date", ""),
            reverse=True
        )[:5]
        
        return APIResponse(
            success=True,
            data={
                "total_vouchers": total_vouchers,
                "total_sales": round(total_sales, 2),
                "top_customers": top_customers,
                "recent_vouchers": recent_vouchers
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting sales summary: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/sales/analytics")
async def get_sales_analytics():
    """Get sales analytics data for charts"""
    try:
        vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(1000)
        
        if not vouchers:
            return APIResponse(success=True, data={"daily_sales": [], "category_sales": []})
        
        # Group by date
        daily_sales = {}
        for v in vouchers:
            date = v.get("voucher_date", "Unknown")
            daily_sales[date] = daily_sales.get(date, 0) + v.get("total_amount", 0)
        
        daily_sales_data = sorted(
            [{"date": k, "amount": v} for k, v in daily_sales.items()],
            key=lambda x: x["date"]
        )
        
        return APIResponse(
            success=True,
            data={"daily_sales": daily_sales_data}
        )
    
    except Exception as e:
        logger.error(f"Error getting sales analytics: {e}")
        return APIResponse(success=False, error=str(e))

# AI Query Endpoint
@api_router.post("/ai/query")
async def ai_query(request: AIQueryRequest):
    """Process natural language query and generate AI report"""
    try:
        # Fetch data
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(1000)
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(1000)
        
        # Generate AI report
        ai_service = AIReportService()
        result = await ai_service.generate_report(
            query=request.query,
            inventory_data=inventory_items,
            sales_data=sales_vouchers
        )
        
        # Save query to database
        ai_query_obj = AIQuery(
            query_text=request.query,
            response=result.get("raw_response"),
            report_data=result.get("report")
        )
        doc = ai_query_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.ai_queries.insert_one(doc)
        
        return APIResponse(
            success=result.get("success", False),
            data=result.get("report"),
            error=result.get("error")
        )
    
    except Exception as e:
        logger.error(f"Error processing AI query: {e}")
        return APIResponse(success=False, error=str(e))

# Export Endpoints
@api_router.post("/reports/export")
async def export_report(request: ExportRequest):
    """Export report in specified format (PDF, Excel, CSV)"""
    try:
        # Fetch data based on report type
        if request.report_type == "inventory":
            data = await db.inventory_items.find({}, {"_id": 0}).to_list(1000)
            report_title = "Inventory Report"
        elif request.report_type == "sales":
            data = await db.sales_vouchers.find({}, {"_id": 0}).to_list(1000)
            report_title = "Sales Report"
        else:
            return APIResponse(success=False, error="Invalid report type")
        
        if not data:
            return APIResponse(success=False, error="No data available to export")
        
        # Clean data for export (remove timestamp fields that may cause issues)
        clean_data = []
        for item in data:
            clean_item = {k: v for k, v in item.items() if k not in ['last_updated', 'created_at']}
            clean_data.append(clean_item)
        
        export_service = ExportService()
        
        if request.format == "csv":
            output = export_service.export_to_csv(clean_data)
            media_type = "text/csv"
            filename = f"{request.report_type}_report.csv"
        elif request.format == "excel":
            output = export_service.export_to_excel(clean_data, request.report_type.title())
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{request.report_type}_report.xlsx"
        elif request.format == "pdf":
            output = export_service.export_to_pdf(clean_data, request.report_type.title(), report_title)
            media_type = "application/pdf"
            filename = f"{request.report_type}_report.pdf"
        else:
            return APIResponse(success=False, error="Invalid export format")
        
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/reports/history")
async def get_report_history():
    """Get AI query history"""
    try:
        queries = await db.ai_queries.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
        
        return APIResponse(
            success=True,
            data={"queries": queries, "count": len(queries)}
        )
    
    except Exception as e:
        logger.error(f"Error fetching report history: {e}")
        return APIResponse(success=False, error=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    if tally_client_instance:
        tally_client_instance.close()
