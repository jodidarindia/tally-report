from fastapi import FastAPI, APIRouter, HTTPException, Response, Request
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta, timezone

from models import (
    TallyConnection, TallyConnectionCreate,
    InventoryItem, SalesVoucher,
    AIQuery, AIQueryRequest,
    ExportRequest, APIResponse,
    CustomerOutstanding, CustomerFollowup, CustomerFollowupCreate,
    CustomerTarget, SalesmanPerformance,
    InventoryMovement, BelowCostSale,
    LoginRequest, ChangePasswordRequest, CreateUserRequest, ResetPasswordRequest,
    PurchaseOrder, PurchaseOrderItem
)
from services.tally_client import TallyClient
from services.ai_service import AIReportService
from services.enhanced_ai_service import EnhancedAIReportService
from services.export_service import ExportService
from services.auth_service import (
    hash_password, verify_password, create_access_token,
    get_current_user, seed_admin
)
from services.purchase_order_ai import PurchaseOrderAI

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="FLOWRA - Organize. Automate. Accelerate.")

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
    """Check Tally connection status - based on last agent sync"""
    try:
        sync_status = await db.sync_status.find_one({'type': 'agent_sync'}, {'_id': 0})
        if sync_status and sync_status.get('last_sync'):
            last_sync = sync_status['last_sync']
            company = sync_status.get('company_name', '')
            return APIResponse(
                success=True,
                data={
                    "is_connected": True,
                    "message": f"Connected - {company}" if company else "Connected",
                    "last_sync": last_sync,
                    "company_name": company,
                    "agent_version": sync_status.get('agent_version', '')
                }
            )
        return APIResponse(
            success=True,
            data={"is_connected": False, "message": "No sync data yet. Run the desktop agent."}
        )
    except Exception as e:
        logger.error(f"Error checking Tally status: {e}")
        return APIResponse(success=False, error=str(e))

# Inventory Endpoints
@api_router.get("/inventory/items")
async def get_inventory_items(category: Optional[str] = None, stock_group: Optional[str] = None, min_quantity: Optional[float] = None):
    """Fetch inventory items with optional group/category filter"""
    try:
        query = {}
        if category and category != 'all':
            query["category"] = category
        if stock_group and stock_group != 'all':
            query["stock_group"] = stock_group
        if min_quantity is not None:
            query["quantity"] = {"$gte": min_quantity}
        
        items = await db.inventory_items.find(query, {"_id": 0}).to_list(5000)
        
        # If no data in DB, use TallyClient (demo/mock data)
        if not items:
            global tally_client_instance
            if not tally_client_instance:
                tally_client_instance = TallyClient(connection_type="xml")
            
            filters = {}
            if category:
                filters["category"] = category
            if min_quantity is not None:
                filters["min_quantity"] = min_quantity
            
            items = tally_client_instance.fetch_inventory(filters)
        
        # Get unique stock groups
        all_items = await db.inventory_items.find({}, {"_id": 0, "stock_group": 1}).to_list(5000)
        stock_groups = sorted(list(set(item.get("stock_group", "General") for item in all_items if item.get("stock_group"))))
        
        return APIResponse(
            success=True,
            data={"items": items, "count": len(items), "stock_groups": stock_groups}
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
    """Fetch sales vouchers - prefer real synced data from DB, fallback to TallyClient demo"""
    try:
        # First check DB for real synced data
        query = {}
        if party_name:
            query["party_name"] = {"$regex": party_name, "$options": "i"}
        
        vouchers = await db.sales_vouchers.find(query, {"_id": 0}).to_list(10000)
        
        # Apply date filters on DB data
        if vouchers and (start_date or end_date):
            filtered = []
            for v in vouchers:
                v_date = v.get("voucher_date", "")
                if start_date and v_date < start_date:
                    continue
                if end_date and v_date > end_date:
                    continue
                filtered.append(v)
            vouchers = filtered
        
        # If no data in DB, use TallyClient (demo/mock data)
        if not vouchers and not party_name:
            global tally_client_instance
            if not tally_client_instance:
                tally_client_instance = TallyClient(connection_type="xml")
            
            vouchers = tally_client_instance.fetch_sales_vouchers(start_date, end_date)
            
            # Save demo data to database
            if vouchers:
                from pymongo import UpdateOne
                operations = []
                for voucher in vouchers:
                    sales_obj = SalesVoucher(**voucher)
                    doc = sales_obj.model_dump()
                    doc['last_updated'] = doc['last_updated'].isoformat()
                    operations.append(
                        UpdateOne(
                            {"voucher_id": voucher["voucher_id"]},
                            {"$set": doc},
                            upsert=True
                        )
                    )
                if operations:
                    await db.sales_vouchers.bulk_write(operations)
        
        return APIResponse(
            success=True,
            data={"vouchers": vouchers, "count": len(vouchers)}
        )
    
    except Exception as e:
        logger.error(f"Error fetching sales vouchers: {e}")
        return APIResponse(success=False, error=str(e))


@api_router.get("/sales/vouchers/{voucher_id}")
async def get_voucher_detail(voucher_id: str):
    """Get full details of a single sales voucher (invoice view)"""
    try:
        voucher = await db.sales_vouchers.find_one({"voucher_id": voucher_id}, {"_id": 0})
        if not voucher:
            return APIResponse(success=False, error="Voucher not found")

        # Calculate line totals
        items = voucher.get("items", [])
        subtotal = sum(item.get("amount", item.get("quantity", 0) * item.get("rate", 0)) for item in items)
        total = voucher.get("total_amount", subtotal)

        voucher["subtotal"] = subtotal
        voucher["computed_total"] = total
        voucher["item_count"] = len(items)

        return APIResponse(success=True, data=voucher)

    except Exception as e:
        logger.error(f"Error fetching voucher detail: {e}")
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

# Agent Sync Endpoint (receives data from desktop agent)
@api_router.post("/agent/sync")
async def receive_agent_sync(request: dict):
    """Receive synced data from desktop agent"""
    try:
        data_type = request.get('data_type')
        data = request.get('data', [])
        sync_time = request.get('sync_time')
        
        logger.info(f"Received {data_type} sync from agent: {len(data)} items")
        
        if data_type == 'inventory':
            # Clear existing and insert new inventory data
            await db.inventory_items.delete_many({})
            
            if data:
                docs = []
                for item in data:
                    inventory_obj = InventoryItem(**item)
                    doc = inventory_obj.model_dump()
                    doc['last_updated'] = doc['last_updated'].isoformat()
                    docs.append(doc)
                
                if docs:
                    await db.inventory_items.insert_many(docs)
            
            logger.info(f"Synced {len(data)} inventory items to database")
        
        elif data_type == 'sales':
            # Clear existing and insert new sales data
            await db.sales_vouchers.delete_many({})
            
            if data:
                docs = []
                for voucher in data:
                    sales_obj = SalesVoucher(**voucher)
                    doc = sales_obj.model_dump()
                    doc['last_updated'] = doc['last_updated'].isoformat()
                    docs.append(doc)
                
                if docs:
                    await db.sales_vouchers.insert_many(docs)
            
            logger.info(f"Synced {len(data)} sales vouchers to database")
        
        elif data_type == 'customers':
            # Upsert customers from agent sync (don't delete - merge with existing)
            if data:
                from pymongo import UpdateOne
                operations = []
                for cust in data:
                    customer_name = cust.get('customer_name', '')
                    if not customer_name:
                        continue
                    operations.append(
                        UpdateOne(
                            {"customer_name": customer_name},
                            {"$set": {
                                "customer_name": customer_name,
                                "ledger_group": cust.get('ledger_group', 'Sundry Debtors'),
                                "outstanding_amount": cust.get('outstanding_amount', 0),
                                "total_purchases": cust.get('total_purchases', 0),
                                "transaction_count": cust.get('transaction_count', 0),
                                "phone": cust.get('phone', ''),
                                "contact_person": cust.get('contact_person', ''),
                                "state": cust.get('state', ''),
                                "last_synced": sync_time
                            }},
                            upsert=True
                        )
                    )
                if operations:
                    await db.customers.bulk_write(operations)
            
            logger.info(f"Synced {len(data)} customers to database")
        
        # Update last sync time
        company_name = request.get('company_name', '')
        financial_year = request.get('financial_year', '')
        await db.sync_status.update_one(
            {'type': 'agent_sync'},
            {'$set': {
                'last_sync': sync_time,
                'data_type': data_type,
                'count': len(data),
                'agent_version': request.get('agent_version', ''),
                'company_name': company_name,
                'financial_year': financial_year
            }},
            upsert=True
        )
        
        return APIResponse(
            success=True,
            message=f"Successfully synced {len(data)} {data_type} items"
        )
    
    except Exception as e:
        logger.error(f"Error receiving agent sync: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/sync/status")
async def get_sync_status():
    """Get last sync status from desktop agent"""
    try:
        sync_status = await db.sync_status.find_one({'type': 'agent_sync'}, {'_id': 0})
        
        if not sync_status:
            return APIResponse(
                success=True,
                data={
                    'last_sync': None,
                    'is_syncing': False,
                    'message': 'No sync data available'
                }
            )
        
        return APIResponse(
            success=True,
            data=sync_status
        )
    
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return APIResponse(success=False, error=str(e))




# ==================== AUTHENTICATION ENDPOINTS ====================

@api_router.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    """Login with username and password"""
    try:
        user = await db.users.find_one({"username": request.username}, {"_id": 0})
        if not user:
            return APIResponse(success=False, error="Invalid username or password")
        if not verify_password(request.password, user["password_hash"]):
            return APIResponse(success=False, error="Invalid username or password")

        token = create_access_token(user["username"], user["username"], user["role"])
        response.set_cookie(
            key="access_token", value=token,
            httponly=True, secure=False, samesite="lax",
            max_age=86400, path="/"
        )
        return APIResponse(
            success=True,
            message="Login successful",
            data={
                "username": user["username"],
                "name": user.get("name", ""),
                "role": user["role"],
                "token": token
            }
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        return APIResponse(success=False, error=str(e))


@api_router.get("/auth/me")
async def get_me(request: Request):
    """Get current user info"""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        return APIResponse(success=True, data={
            "username": user["username"],
            "name": user.get("name", ""),
            "role": user["role"]
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@api_router.post("/auth/logout")
async def logout(response: Response):
    """Logout by clearing cookie"""
    response.delete_cookie("access_token", path="/")
    return APIResponse(success=True, message="Logged out successfully")


@api_router.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    """Change own password"""
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        full_user = await db.users.find_one({"username": user["username"]})
        if not verify_password(req.current_password, full_user["password_hash"]):
            return APIResponse(success=False, error="Current password is incorrect")
        await db.users.update_one(
            {"username": user["username"]},
            {"$set": {"password_hash": hash_password(req.new_password)}}
        )
        return APIResponse(success=True, message="Password changed successfully")
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return APIResponse(success=False, error=str(e))


@api_router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest, request: Request):
    """Admin resets another user's password"""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        target = await db.users.find_one({"username": req.username})
        if not target:
            return APIResponse(success=False, error="User not found")
        await db.users.update_one(
            {"username": req.username},
            {"$set": {"password_hash": hash_password(req.new_password)}}
        )
        return APIResponse(success=True, message=f"Password reset for {req.username}")
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        return APIResponse(success=False, error=str(e))


@api_router.post("/auth/users")
async def create_user(req: CreateUserRequest, request: Request):
    """Admin creates a new user (employee)"""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        existing = await db.users.find_one({"username": req.username})
        if existing:
            return APIResponse(success=False, error="Username already exists")
        await db.users.insert_one({
            "username": req.username,
            "password_hash": hash_password(req.password),
            "name": req.name,
            "role": req.role,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return APIResponse(success=True, message=f"User '{req.username}' created", data={"username": req.username, "role": req.role})
    except Exception as e:
        logger.error(f"Create user error: {e}")
        return APIResponse(success=False, error=str(e))


@api_router.get("/auth/users")
async def list_users(request: Request):
    """Admin lists all users"""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
        return APIResponse(success=True, data={"users": users})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@api_router.delete("/auth/users/{username}")
async def delete_user(username: str, request: Request):
    """Admin deletes a user"""
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        if username == user["username"]:
            return APIResponse(success=False, error="Cannot delete yourself")
        result = await db.users.delete_one({"username": username})
        if result.deleted_count == 0:
            return APIResponse(success=False, error="User not found")
        return APIResponse(success=True, message=f"User '{username}' deleted")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


# ==================== PURCHASE ORDER AI ENDPOINTS ====================

@api_router.post("/inventory/generate-purchase-order")
async def generate_purchase_order():
    """Generate AI-powered purchase order recommendations"""
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        po_ai = PurchaseOrderAI()
        result = await po_ai.generate_purchase_order(inventory_items, sales_vouchers)
        
        if result.get("success"):
            # Save PO to database
            po_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            po_data = result.get("purchase_order", {})
            
            purchase_order = PurchaseOrder(
                po_number=po_number,
                items=[PurchaseOrderItem(**item) for item in po_data.get("urgent_items", [])],
                total_items=len(po_data.get("urgent_items", [])),
                total_cost=po_data.get("total_estimated_cost", 0),
                ai_analysis=po_data.get("analysis", ""),
                status="draft"
            )
            
            doc = purchase_order.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            
            await db.purchase_orders.insert_one(doc)
            
            return APIResponse(
                success=True,
                data=po_data,
                message=f"Purchase order {po_number} generated"
            )
        else:
            return APIResponse(success=False, error=result.get("error"))
    
    except Exception as e:
        logger.error(f"Error generating purchase order: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/inventory/purchase-orders")
async def get_purchase_orders(status: Optional[str] = None):
    """Get all purchase orders"""
    try:
        query = {}
        if status:
            query["status"] = status
        
        pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        
        return APIResponse(
            success=True,
            data={"purchase_orders": pos, "count": len(pos)}
        )
    
    except Exception as e:
        logger.error(f"Error fetching purchase orders: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== ENHANCED PIVOT TABLE ENDPOINTS ====================

@api_router.get("/inventory/sales-frequency")
async def get_sales_frequency(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get sales frequency and unique customers per item"""
    try:
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Apply date filter
        if start_date or end_date:
            filtered_vouchers = []
            for v in sales_vouchers:
                v_date = v.get("voucher_date", "")
                if start_date and v_date < start_date:
                    continue
                if end_date and v_date > end_date:
                    continue
                filtered_vouchers.append(v)
            sales_vouchers = filtered_vouchers
        
        # Calculate frequency and unique customers per item
        item_stats = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = item.get("quantity", 0)
                
                if item_name not in item_stats:
                    item_stats[item_name] = {
                        "item_name": item_name,
                        "total_quantity_sold": 0,
                        "transaction_count": 0,
                        "unique_customers": set(),
                        "total_revenue": 0
                    }
                
                item_stats[item_name]["total_quantity_sold"] += qty
                item_stats[item_name]["transaction_count"] += 1
                item_stats[item_name]["unique_customers"].add(party)
                item_stats[item_name]["total_revenue"] += qty * item.get("rate", 0)
        
        # Convert to list and add unique customer count
        frequency_data = []
        for item_name, stats in item_stats.items():
            frequency_data.append({
                "item_name": item_name,
                "total_quantity_sold": stats["total_quantity_sold"],
                "transaction_count": stats["transaction_count"],
                "unique_customers": len(stats["unique_customers"]),
                "customer_names": list(stats["unique_customers"]),
                "total_revenue": stats["total_revenue"],
                "avg_quantity_per_transaction": stats["total_quantity_sold"] / stats["transaction_count"] if stats["transaction_count"] > 0 else 0
            })
        
        # Sort by transaction count
        frequency_data.sort(key=lambda x: x["transaction_count"], reverse=True)
        
        return APIResponse(
            success=True,
            data={
                "sales_frequency": frequency_data,
                "date_range": {"start": start_date, "end": end_date},
                "total_items": len(frequency_data)
            }
        )
    
    except Exception as e:
        logger.error(f"Error calculating sales frequency: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== ENHANCED AI REPORT ENDPOINTS ====================

@api_router.post("/ai/advanced-query")
async def ai_advanced_query(request: AIQueryRequest):
    """Enhanced AI report generation with filters"""
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        customer_data = await db.customer_outstanding.find({}, {"_id": 0}).to_list(1000)
        
        ai_service = EnhancedAIReportService()
        result = await ai_service.generate_advanced_report(
            query=request.query,
            report_type=request.report_type or 'general',
            filters=request.filters or {},
            inventory_data=inventory_items,
            sales_data=sales_vouchers,
            customer_data=customer_data
        )
        
        if result.get("success"):
            # Save query
            ai_query_obj = AIQuery(
                query_text=request.query,
                response=result.get("raw_response"),
                report_data=result.get("report"),
                filters=request.filters
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
        logger.error(f"Error in advanced AI query: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== CUSTOMER & CRM ENDPOINTS ====================

@api_router.get("/customers/outstanding")
async def get_customer_outstanding(customer: Optional[str] = None):
    """Get outstanding payments by customer with proper aging based on invoice dates"""
    try:
        from datetime import date as date_type
        today = date_type.today()

        # Get synced customer data (has ledger_group, phone, outstanding from Tally closing balance)
        synced_customers = await db.customers.find({}, {"_id": 0}).to_list(5000)
        synced_map = {c["customer_name"].lower(): c for c in synced_customers}

        # Get all sales vouchers for aging calculation
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)

        customer_map = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            amount = voucher.get("total_amount", 0)
            v_date_str = voucher.get("voucher_date", "")

            if party not in customer_map:
                synced = synced_map.get(party.lower(), {})
                customer_map[party] = {
                    "customer_name": party,
                    "ledger_group": synced.get("ledger_group", "Sundry Debtors"),
                    "phone": synced.get("phone", ""),
                    "outstanding_amount": synced.get("outstanding_amount", 0),
                    "total_sales": 0,
                    "voucher_count": 0,
                    "last_transaction": v_date_str,
                    "aging_0_30": 0.0,
                    "aging_30_60": 0.0,
                    "aging_60_90": 0.0,
                    "aging_90_plus": 0.0,
                    "oldest_invoice_days": 0
                }

            customer_map[party]["total_sales"] += amount
            customer_map[party]["voucher_count"] += 1
            if v_date_str and v_date_str > (customer_map[party].get("last_transaction") or ""):
                customer_map[party]["last_transaction"] = v_date_str

            # Calculate aging bucket for this voucher
            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    if days_old > customer_map[party]["oldest_invoice_days"]:
                        customer_map[party]["oldest_invoice_days"] = days_old
                    if days_old <= 30:
                        customer_map[party]["aging_0_30"] += amount
                    elif days_old <= 60:
                        customer_map[party]["aging_30_60"] += amount
                    elif days_old <= 90:
                        customer_map[party]["aging_60_90"] += amount
                    else:
                        customer_map[party]["aging_90_plus"] += amount
            except (ValueError, TypeError):
                customer_map[party]["aging_0_30"] += amount

        # Add synced customers not in sales
        for sc in synced_customers:
            name = sc["customer_name"]
            if name not in customer_map:
                customer_map[name] = {
                    "customer_name": name,
                    "ledger_group": sc.get("ledger_group", "Sundry Debtors"),
                    "phone": sc.get("phone", ""),
                    "outstanding_amount": sc.get("outstanding_amount", 0),
                    "total_sales": sc.get("total_purchases", 0),
                    "voucher_count": sc.get("transaction_count", 0),
                    "last_transaction": None,
                    "aging_0_30": 0.0, "aging_30_60": 0.0,
                    "aging_60_90": 0.0, "aging_90_plus": 0.0,
                    "oldest_invoice_days": 0
                }

        customers = list(customer_map.values())

        if customer:
            customers = [c for c in customers if customer.lower() in c["customer_name"].lower()]

        # Finalize: outstanding = Tally closing balance, else total_sales as proxy
        for cust in customers:
            if cust["outstanding_amount"] == 0 and cust["total_sales"] > 0:
                cust["outstanding_amount"] = cust["total_sales"]

            outstanding = cust["outstanding_amount"]
            cust["overdue_amount"] = cust["aging_60_90"] + cust["aging_90_plus"]

            # Status based on oldest invoice days
            oldest = cust["oldest_invoice_days"]
            if oldest > 90:
                cust["status"] = "critical"
                cust["status_label"] = "Critical"
            elif oldest > 60:
                cust["status"] = "overdue"
                cust["status_label"] = "Overdue"
            elif oldest > 30:
                cust["status"] = "at_risk"
                cust["status_label"] = "At Risk"
            else:
                cust["status"] = "normal"
                cust["status_label"] = "Normal"

        customers.sort(key=lambda c: c["outstanding_amount"], reverse=True)

        return APIResponse(
            success=True,
            data={"customers": customers, "total_outstanding": sum(c["outstanding_amount"] for c in customers)}
        )

    except Exception as e:
        logger.error(f"Error fetching customer outstanding: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/customers/followups")
async def get_followups(status: Optional[str] = None):
    """Get customer follow-ups"""
    try:
        query = {}
        if status:
            query["status"] = status
        
        followups = await db.customer_followups.find(query, {"_id": 0}).sort("followup_date", -1).to_list(100)
        
        return APIResponse(
            success=True,
            data={"followups": followups, "count": len(followups)}
        )
    
    except Exception as e:
        logger.error(f"Error fetching followups: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.post("/customers/followups")
async def create_followup(followup: CustomerFollowupCreate, request: Request):
    """Create a new customer follow-up"""
    try:
        user = await get_current_user(request, db)
        followup_obj = CustomerFollowup(
            customer_name=followup.customer_name,
            followup_date=datetime.fromisoformat(followup.followup_date),
            followup_type=followup.followup_type,
            status="pending",
            notes=followup.notes,
            created_by=user["username"] if user else "unknown",
            created_by_name=user.get("name", "") if user else "Unknown"
        )
        
        doc = followup_obj.model_dump()
        doc['followup_date'] = doc['followup_date'].isoformat()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.customer_followups.insert_one(doc)
        
        return APIResponse(
            success=True,
            message="Follow-up created successfully",
            data={"id": followup_obj.id}
        )
    
    except Exception as e:
        logger.error(f"Error creating followup: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.patch("/customers/followups/{followup_id}")
async def update_followup_status(followup_id: str, status: str):
    """Update follow-up status"""
    try:
        result = await db.customer_followups.update_one(
            {"id": followup_id},
            {"$set": {"status": status}}
        )
        
        return APIResponse(
            success=result.modified_count > 0,
            message="Follow-up updated" if result.modified_count > 0 else "Follow-up not found"
        )
    
    except Exception as e:
        logger.error(f"Error updating followup: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/customers/targets")
async def get_customer_targets():
    """Get customer targets and achievement with monthly breakdown"""
    try:
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        custom_targets = await db.customer_targets.find({}, {"_id": 0}).to_list(100)
        custom_target_map = {t["customer_name"]: t for t in custom_targets}
        
        # Calculate achievement by customer (current FY and last FY)
        customer_sales = {}
        customer_monthly = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            amount = voucher.get("total_amount", 0)
            v_date = voucher.get("voucher_date", "")
            
            customer_sales[party] = customer_sales.get(party, 0) + amount
            
            # Monthly breakdown
            if v_date:
                month_key = v_date[:7]  # YYYY-MM
                if party not in customer_monthly:
                    customer_monthly[party] = {}
                customer_monthly[party][month_key] = customer_monthly[party].get(month_key, 0) + amount
        
        # Build targets list
        targets = []
        for customer, achieved in customer_sales.items():
            ct = custom_target_map.get(customer, {})
            target_amount = ct.get("target_amount", achieved * 1.2)
            
            monthly = customer_monthly.get(customer, {})
            monthly_data = [{"month": k, "amount": v} for k, v in sorted(monthly.items())]
            
            targets.append({
                "customer_name": customer,
                "target_amount": target_amount,
                "last_fy_sales": ct.get("last_fy_sales", achieved),
                "achieved_amount": achieved,
                "achievement_percentage": (achieved / target_amount * 100) if target_amount > 0 else 0,
                "remaining": max(0, target_amount - achieved),
                "monthly_sales": monthly_data,
                "has_custom_target": customer in custom_target_map
            })
        
        targets.sort(key=lambda x: x["achievement_percentage"], reverse=True)
        
        return APIResponse(
            success=True,
            data={"targets": targets}
        )
    
    except Exception as e:
        logger.error(f"Error fetching customer targets: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.post("/customers/targets/set")
async def set_customer_target(request: dict):
    """Set target for a customer based on last FY sales"""
    try:
        customer_name = request.get("customer_name", "").strip()
        target_amount = request.get("target_amount", 0)
        last_fy_sales = request.get("last_fy_sales", 0)
        
        if not customer_name:
            return APIResponse(success=False, error="Customer name is required")
        
        doc = {
            "customer_name": customer_name,
            "target_amount": float(target_amount),
            "last_fy_sales": float(last_fy_sales),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.customer_targets.update_one(
            {"customer_name": customer_name},
            {"$set": doc},
            upsert=True
        )
        
        return APIResponse(
            success=True,
            message=f"Target set for {customer_name}",
            data=doc
        )
    except Exception as e:
        logger.error(f"Error setting customer target: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.post("/customers/ledger/export")
async def export_customer_ledger(request: dict):
    """Export selected customer's ledger as Excel or PDF"""
    try:
        customer_name = request.get("customer_name", "")
        export_format = request.get("format", "excel")
        
        if not customer_name:
            return APIResponse(success=False, error="Customer name is required")
        
        sales_vouchers = await db.sales_vouchers.find(
            {"party_name": customer_name},
            {"_id": 0}
        ).to_list(10000)
        
        rows = []
        running_total = 0
        for v in sorted(sales_vouchers, key=lambda x: x.get("voucher_date", "")):
            amount = v.get("total_amount", 0)
            running_total += amount
            items_str = ", ".join([f"{i.get('item', '')} x{i.get('quantity', 0)}" for i in v.get("items", [])])
            rows.append({
                "Date": v.get("voucher_date", ""),
                "Voucher No": v.get("reference_number", v.get("voucher_id", "")),
                "Items": items_str,
                "Amount": amount,
                "Running Total": running_total,
                "Salesman": v.get("salesman", "")
            })
        
        if not rows:
            return APIResponse(success=False, error=f"No transactions found for {customer_name}")
        
        export_service = ExportService()
        
        if export_format == "excel":
            output = export_service.export_to_excel(rows, f"Ledger - {customer_name}")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"ledger_{customer_name.replace(' ', '_')}.xlsx"
        else:
            output = export_service.export_to_pdf(rows, f"Ledger - {customer_name}", f"Customer Ledger: {customer_name}")
            media_type = "application/pdf"
            filename = f"ledger_{customer_name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        logger.error(f"Error exporting customer ledger: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/dashboard/reminders")
async def get_dashboard_reminders():
    """Get upcoming follow-up reminders for the dashboard"""
    try:
        now = datetime.now(timezone.utc).isoformat()
        
        # Get pending followups
        followups = await db.customer_followups.find(
            {"status": "pending"},
            {"_id": 0}
        ).sort("followup_date", 1).to_list(50)
        
        overdue = []
        today = []
        upcoming = []
        now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        for f in followups:
            f_date = f.get("followup_date", "")[:10]
            if f_date < now_date:
                f["reminder_type"] = "overdue"
                overdue.append(f)
            elif f_date == now_date:
                f["reminder_type"] = "today"
                today.append(f)
            else:
                f["reminder_type"] = "upcoming"
                upcoming.append(f)
        
        return APIResponse(
            success=True,
            data={
                "overdue": overdue,
                "today": today,
                "upcoming": upcoming[:5],
                "total_pending": len(followups),
                "overdue_count": len(overdue),
                "today_count": len(today)
            }
        )
    
    except Exception as e:
        logger.error(f"Error fetching reminders: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/customers/payment-behavior")
async def get_payment_behavior(customer: Optional[str] = None):
    """Analyze customer payment behavior"""
    try:
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Group by customer and analyze behavior
        behavior_map = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            amount = voucher.get("total_amount", 0)
            date = voucher.get("voucher_date", "")
            
            if party not in behavior_map:
                behavior_map[party] = {
                    "customer_name": party,
                    "total_transactions": 0,
                    "total_amount": 0,
                    "average_transaction": 0,
                    "payment_pattern": "regular",  # regular, irregular, risky
                    "average_payment_delay": 15,  # mock days
                    "credit_score": 0
                }
            
            behavior_map[party]["total_transactions"] += 1
            behavior_map[party]["total_amount"] += amount
        
        # Calculate averages and scores
        for customer_name, data in behavior_map.items():
            data["average_transaction"] = data["total_amount"] / data["total_transactions"]
            
            # Mock credit score based on transaction count and amount
            data["credit_score"] = min(100, (data["total_transactions"] * 5) + (data["total_amount"] / 10000))
            
            # Classify payment pattern
            if data["average_payment_delay"] < 10:
                data["payment_pattern"] = "excellent"
            elif data["average_payment_delay"] < 30:
                data["payment_pattern"] = "regular"
            elif data["average_payment_delay"] < 60:
                data["payment_pattern"] = "irregular"
            else:
                data["payment_pattern"] = "risky"
        
        customers = list(behavior_map.values())
        
        # Filter if specified
        if customer:
            customers = [c for c in customers if customer.lower() in c["customer_name"].lower()]
        
        return APIResponse(
            success=True,
            data={"customers": customers}
        )
    
    except Exception as e:
        logger.error(f"Error analyzing payment behavior: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== SALESMAN PERFORMANCE ENDPOINTS ====================

@api_router.get("/salesman/performance")
async def get_salesman_performance():
    """Get salesman-wise performance"""
    try:
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Group by salesman
        salesman_map = {}
        for voucher in sales_vouchers:
            salesman = voucher.get("salesman", "Direct Sales")
            amount = voucher.get("total_amount", 0)
            customer = voucher.get("party_name", "")
            
            if salesman not in salesman_map:
                salesman_map[salesman] = {
                    "salesman_name": salesman,
                    "total_sales": 0,
                    "customers": set(),
                    "transactions": 0
                }
            
            salesman_map[salesman]["total_sales"] += amount
            salesman_map[salesman]["customers"].add(customer)
            salesman_map[salesman]["transactions"] += 1
        
        # Create performance list
        performance = []
        for salesman, data in salesman_map.items():
            target_amount = data["total_sales"] * 1.15  # Target 115% of current
            performance.append({
                "salesman_name": salesman,
                "target_amount": target_amount,
                "achieved_amount": data["total_sales"],
                "achievement_percentage": (data["total_sales"] / target_amount * 100),
                "total_customers": len(data["customers"]),
                "total_transactions": data["transactions"],
                "average_transaction": data["total_sales"] / data["transactions"] if data["transactions"] > 0 else 0
            })
        
        performance.sort(key=lambda x: x["achievement_percentage"], reverse=True)
        
        return APIResponse(
            success=True,
            data={"salesman": performance}
        )
    
    except Exception as e:
        logger.error(f"Error fetching salesman performance: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== SALESMAN MASTER CRUD ENDPOINTS ====================

@api_router.get("/salesman/master")
async def get_salesman_master():
    """Get all salesman master records"""
    try:
        salesmen = await db.salesman_master.find({}, {"_id": 0}).to_list(100)
        return APIResponse(success=True, data={"salesmen": salesmen})
    except Exception as e:
        logger.error(f"Error fetching salesman master: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.post("/salesman/master")
async def create_salesman(request: dict):
    """Create or update a salesman with customer mapping and targets"""
    try:
        import uuid
        salesman_name = request.get("salesman_name", "").strip()
        if not salesman_name:
            return APIResponse(success=False, error="Salesman name is required")
        
        customers = request.get("customers", [])
        monthly_target = request.get("monthly_target", 0)
        quarterly_target = request.get("quarterly_target", 0)
        phone = request.get("phone", "")
        email = request.get("email", "")
        
        doc = {
            "salesman_id": str(uuid.uuid4()),
            "salesman_name": salesman_name,
            "customers": customers,
            "monthly_target": monthly_target,
            "quarterly_target": quarterly_target,
            "phone": phone,
            "email": email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert by name
        result = await db.salesman_master.update_one(
            {"salesman_name": salesman_name},
            {"$set": doc},
            upsert=True
        )
        
        return APIResponse(
            success=True,
            message=f"Salesman '{salesman_name}' saved",
            data=doc
        )
    except Exception as e:
        logger.error(f"Error creating salesman: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.delete("/salesman/master/{salesman_name}")
async def delete_salesman(salesman_name: str):
    """Delete a salesman record"""
    try:
        result = await db.salesman_master.delete_one({"salesman_name": salesman_name})
        return APIResponse(
            success=result.deleted_count > 0,
            message="Deleted" if result.deleted_count > 0 else "Not found"
        )
    except Exception as e:
        logger.error(f"Error deleting salesman: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/salesman/performance-detailed")
async def get_salesman_performance_detailed():
    """Get salesman performance with master data (targets, customer mapping) and item-wise breakdown"""
    try:
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        master_list = await db.salesman_master.find({}, {"_id": 0}).to_list(100)
        master_map = {m["salesman_name"]: m for m in master_list}
        
        salesman_map = {}
        for voucher in sales_vouchers:
            salesman = voucher.get("salesman", "Direct Sales")
            amount = voucher.get("total_amount", 0)
            customer = voucher.get("party_name", "")
            
            if salesman not in salesman_map:
                salesman_map[salesman] = {
                    "salesman_name": salesman,
                    "total_sales": 0,
                    "customers": set(),
                    "transactions": 0,
                    "items_sold": {}
                }
            
            salesman_map[salesman]["total_sales"] += amount
            salesman_map[salesman]["customers"].add(customer)
            salesman_map[salesman]["transactions"] += 1
            
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = item.get("quantity", 0)
                rate = item.get("rate", 0)
                if item_name not in salesman_map[salesman]["items_sold"]:
                    salesman_map[salesman]["items_sold"][item_name] = {
                        "item_name": item_name,
                        "total_quantity": 0,
                        "total_revenue": 0,
                        "transaction_count": 0
                    }
                salesman_map[salesman]["items_sold"][item_name]["total_quantity"] += qty
                salesman_map[salesman]["items_sold"][item_name]["total_revenue"] += qty * rate
                salesman_map[salesman]["items_sold"][item_name]["transaction_count"] += 1
        
        performance = []
        for salesman, data in salesman_map.items():
            master = master_map.get(salesman, {})
            monthly_target = master.get("monthly_target", data["total_sales"] * 1.15)
            mapped_customers = master.get("customers", [])
            
            items_breakdown = sorted(
                list(data["items_sold"].values()),
                key=lambda x: x["total_revenue"],
                reverse=True
            )
            
            performance.append({
                "salesman_name": salesman,
                "phone": master.get("phone", ""),
                "email": master.get("email", ""),
                "monthly_target": monthly_target,
                "quarterly_target": master.get("quarterly_target", monthly_target * 3),
                "achieved_amount": data["total_sales"],
                "achievement_percentage": (data["total_sales"] / monthly_target * 100) if monthly_target > 0 else 0,
                "total_customers": len(data["customers"]),
                "customer_names": list(data["customers"]),
                "mapped_customers": mapped_customers,
                "total_transactions": data["transactions"],
                "average_transaction": data["total_sales"] / data["transactions"] if data["transactions"] > 0 else 0,
                "items_sold": items_breakdown,
                "has_master": salesman in master_map
            })
        
        performance.sort(key=lambda x: x["achievement_percentage"], reverse=True)
        
        return APIResponse(success=True, data={"salesman": performance})
    
    except Exception as e:
        logger.error(f"Error fetching detailed salesman performance: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== SALES FREQUENCY EXPORT ENDPOINT ====================

@api_router.post("/analytics/sales-frequency/export")
async def export_sales_frequency(request: dict):
    """Export sales frequency data as Excel or PDF"""
    try:
        export_format = request.get("format", "excel")
        start_date = request.get("start_date")
        end_date = request.get("end_date")
        
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        if start_date or end_date:
            filtered = []
            for v in sales_vouchers:
                v_date = v.get("voucher_date", "")
                if start_date and v_date < start_date:
                    continue
                if end_date and v_date > end_date:
                    continue
                filtered.append(v)
            sales_vouchers = filtered
        
        # Calculate frequency
        item_stats = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = item.get("quantity", 0)
                if item_name not in item_stats:
                    item_stats[item_name] = {
                        "item_name": item_name,
                        "total_quantity_sold": 0,
                        "transaction_count": 0,
                        "unique_customers": set(),
                        "total_revenue": 0
                    }
                item_stats[item_name]["total_quantity_sold"] += qty
                item_stats[item_name]["transaction_count"] += 1
                item_stats[item_name]["unique_customers"].add(party)
                item_stats[item_name]["total_revenue"] += qty * item.get("rate", 0)
        
        rows = []
        for name, stats in sorted(item_stats.items(), key=lambda x: x[1]["transaction_count"], reverse=True):
            rows.append({
                "Item Name": name,
                "Transaction Count": stats["transaction_count"],
                "Total Qty Sold": stats["total_quantity_sold"],
                "Unique Customers": len(stats["unique_customers"]),
                "Total Revenue": stats["total_revenue"],
                "Avg Qty/Transaction": round(stats["total_quantity_sold"] / stats["transaction_count"], 1) if stats["transaction_count"] > 0 else 0,
                "Customers": ", ".join(stats["unique_customers"])
            })
        
        export_service = ExportService()
        
        if export_format == "excel":
            output = export_service.export_to_excel(rows, "Sales Frequency")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "sales_frequency_report.xlsx"
        elif export_format == "pdf":
            output = export_service.export_to_pdf(rows, "Sales Frequency", "Sales Frequency Report")
            media_type = "application/pdf"
            filename = "sales_frequency_report.pdf"
        else:
            return APIResponse(success=False, error="Invalid format. Use 'excel' or 'pdf'")
        
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        logger.error(f"Error exporting sales frequency: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/inventory/movement-analysis")
async def get_inventory_movement():
    """Analyze inventory movement patterns"""
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Calculate movement for each item
        item_sales = {}
        for voucher in sales_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = item.get("quantity", 0)
                item_sales[item_name] = item_sales.get(item_name, 0) + qty
        
        movement_data = []
        for item in inventory_items:
            item_name = item["item_name"]
            current_stock = item["quantity"]
            sales_qty = item_sales.get(item_name, 0)
            
            # Mock opening stock (in real scenario, get from Tally)
            opening_stock = current_stock + sales_qty
            
            # Calculate movement rate
            avg_stock = (opening_stock + current_stock) / 2
            movement_rate = (sales_qty / avg_stock * 100) if avg_stock > 0 else 0
            days_to_sell = (current_stock / (sales_qty / 30)) if sales_qty > 0 else 999
            
            movement_data.append({
                "item_name": item_name,
                "category": item.get("category", "General"),
                "opening_stock": opening_stock,
                "purchases": 0,  # Would come from purchase data
                "sales": sales_qty,
                "closing_stock": current_stock,
                "movement_rate": round(movement_rate, 2),
                "days_to_sell": round(days_to_sell, 1),
                "classification": "fast-moving" if movement_rate > 30 else "slow-moving" if movement_rate > 10 else "dead-stock"
            })
        
        # Sort by movement rate
        movement_data.sort(key=lambda x: x["movement_rate"], reverse=True)
        
        return APIResponse(
            success=True,
            data={
                "movements": movement_data,
                "summary": {
                    "fast_moving": len([m for m in movement_data if m["classification"] == "fast-moving"]),
                    "slow_moving": len([m for m in movement_data if m["classification"] == "slow-moving"]),
                    "dead_stock": len([m for m in movement_data if m["classification"] == "dead-stock"])
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error analyzing inventory movement: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/inventory/below-cost-sales")
async def get_below_cost_sales():
    """Identify items sold below purchase cost"""
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Create item cost map
        item_costs = {}
        for item in inventory_items:
            item_costs[item["item_name"]] = {
                "purchase_price": item.get("purchase_price", item.get("price", 0) * 0.7),  # Mock 70% cost
                "selling_price": item.get("price", 0)
            }
        
        below_cost_sales = []
        for voucher in sales_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                sale_price = item.get("rate") or 0
                quantity = item.get("quantity") or 0
                
                if item_name in item_costs:
                    purchase_price = item_costs[item_name]["purchase_price"] or 0
                    
                    if sale_price and purchase_price and sale_price < purchase_price:
                        loss_per_unit = purchase_price - sale_price
                        total_loss = loss_per_unit * quantity
                        
                        below_cost_sales.append({
                            "item_name": item_name,
                            "sale_price": sale_price,
                            "purchase_price": purchase_price,
                            "loss_per_unit": loss_per_unit,
                            "quantity_sold": quantity,
                            "total_loss": total_loss,
                            "voucher_id": voucher.get("voucher_id"),
                            "sale_date": voucher.get("voucher_date"),
                            "customer": voucher.get("party_name")
                        })
        
        total_loss = sum(item["total_loss"] for item in below_cost_sales)
        
        return APIResponse(
            success=True,
            data={
                "below_cost_sales": below_cost_sales,
                "total_loss": total_loss,
                "count": len(below_cost_sales)
            }
        )
    
    except Exception as e:
        logger.error(f"Error finding below cost sales: {e}")
        return APIResponse(success=False, error=str(e))

@api_router.get("/inventory/pivot-data")
async def get_pivot_data(group_by: str = "category", metric: str = "value"):
    """Get pivot table data for inventory"""
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        
        # Group data
        pivot_data = {}
        for item in inventory_items:
            group_key = item.get(group_by, "Uncategorized")
            
            if group_key not in pivot_data:
                pivot_data[group_key] = {
                    "group": group_key,
                    "total_items": 0,
                    "total_quantity": 0,
                    "total_value": 0,
                    "items": []
                }
            
            pivot_data[group_key]["total_items"] += 1
            pivot_data[group_key]["total_quantity"] += item.get("quantity", 0)
            pivot_data[group_key]["total_value"] += item.get("quantity", 0) * item.get("price", 0)
            pivot_data[group_key]["items"].append(item)
        
        pivot_list = list(pivot_data.values())
        
        # Sort by metric
        if metric == "value":
            pivot_list.sort(key=lambda x: x["total_value"], reverse=True)
        elif metric == "quantity":
            pivot_list.sort(key=lambda x: x["total_quantity"], reverse=True)
        else:
            pivot_list.sort(key=lambda x: x["total_items"], reverse=True)
        
        return APIResponse(
            success=True,
            data={
                "pivot_table": pivot_list,
                "group_by": group_by,
                "metric": metric
            }
        )
    
    except Exception as e:
        logger.error(f"Error creating pivot table: {e}")
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

@app.on_event("startup")
async def startup_event():
    await seed_admin(db)
    logger.info("Admin user seeded")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    if tally_client_instance:
        tally_client_instance.close()
