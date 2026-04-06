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
    ExportRequest, APIResponse,
    CustomerOutstanding, CustomerFollowup, CustomerFollowupCreate,
    CustomerTarget, SalesmanPerformance,
    InventoryMovement, BelowCostSale
)
from services.tally_client import TallyClient
from services.ai_service import AIReportService
from services.enhanced_ai_service import EnhancedAIReportService
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
            
            for item in data:
                inventory_obj = InventoryItem(**item)
                doc = inventory_obj.model_dump()
                doc['last_updated'] = doc['last_updated'].isoformat()
                await db.inventory_items.insert_one(doc)
            
            logger.info(f"Synced {len(data)} inventory items to database")
        
        elif data_type == 'sales':
            # Clear existing and insert new sales data
            await db.sales_vouchers.delete_many({})
            
            for voucher in data:
                sales_obj = SalesVoucher(**voucher)
                doc = sales_obj.model_dump()
                doc['last_updated'] = doc['last_updated'].isoformat()
                await db.sales_vouchers.insert_one(doc)
            
            logger.info(f"Synced {len(data)} sales vouchers to database")
        
        # Update last sync time
        await db.sync_status.update_one(
            {'type': 'agent_sync'},
            {'$set': {
                'last_sync': sync_time,
                'data_type': data_type,
                'count': len(data)
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
    """Get outstanding payments by customer"""
    try:
        # Calculate from sales data
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Group by customer
        customer_map = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            amount = voucher.get("total_amount", 0)
            
            if party not in customer_map:
                customer_map[party] = {
                    "customer_name": party,
                    "outstanding_amount": 0,
                    "total_sales": 0,
                    "voucher_count": 0,
                    "last_transaction": voucher.get("voucher_date")
                }
            
            customer_map[party]["total_sales"] += amount
            customer_map[party]["voucher_count"] += 1
            customer_map[party]["outstanding_amount"] += amount * 0.3  # Mock 30% outstanding
        
        customers = list(customer_map.values())
        
        # Filter if customer specified
        if customer:
            customers = [c for c in customers if customer.lower() in c["customer_name"].lower()]
        
        # Calculate aging
        for cust in customers:
            outstanding = cust["outstanding_amount"]
            cust["aging_30_days"] = outstanding * 0.4
            cust["aging_60_days"] = outstanding * 0.3
            cust["aging_90_days"] = outstanding * 0.2
            cust["aging_90_plus"] = outstanding * 0.1
            cust["overdue_amount"] = outstanding * 0.5
        
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
async def create_followup(followup: CustomerFollowupCreate):
    """Create a new customer follow-up"""
    try:
        followup_obj = CustomerFollowup(
            customer_name=followup.customer_name,
            followup_date=datetime.fromisoformat(followup.followup_date),
            followup_type=followup.followup_type,
            status="pending",
            notes=followup.notes
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
    """Get customer targets and achievement"""
    try:
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        
        # Calculate achievement by customer
        customer_sales = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            amount = voucher.get("total_amount", 0)
            customer_sales[party] = customer_sales.get(party, 0) + amount
        
        # Create targets (mock targets, in real scenario from database)
        targets = []
        for customer, achieved in customer_sales.items():
            target_amount = achieved * 1.2  # Target is 120% of current
            targets.append({
                "customer_name": customer,
                "target_amount": target_amount,
                "achieved_amount": achieved,
                "achievement_percentage": (achieved / target_amount * 100) if target_amount > 0 else 0,
                "remaining": target_amount - achieved
            })
        
        targets.sort(key=lambda x: x["achievement_percentage"], reverse=True)
        
        return APIResponse(
            success=True,
            data={"targets": targets}
        )
    
    except Exception as e:
        logger.error(f"Error fetching customer targets: {e}")
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


# ==================== INVENTORY ANALYTICS ENDPOINTS ====================

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
                "classification": "fast-moving" if movement_rate > 50 else "slow-moving" if movement_rate > 20 else "dead-stock"
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
                sale_price = item.get("rate", 0)
                quantity = item.get("quantity", 0)
                
                if item_name in item_costs:
                    purchase_price = item_costs[item_name]["purchase_price"]
                    
                    if sale_price < purchase_price:
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    if tally_client_instance:
        tally_client_instance.close()
