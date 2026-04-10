from fastapi import APIRouter, Request
from typing import Optional
from datetime import datetime, timezone
import uuid
import logging

from db import db
from models import APIResponse
from utils import safe_num, filter_vouchers_by_fy
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_query(ctx, company_id=None, extra=None):
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    cid = company_id or (ctx.get("company_id") if ctx else None)
    if cid:
        q["company_id"] = cid
    if extra:
        q.update(extra)
    return q


@router.get("/salesman/performance")
async def get_salesman_performance(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        vouchers = filter_vouchers_by_fy(all_vouchers, fy)
        master_list = await db.salesman_master.find(q, {"_id": 0}).to_list(100)
        master_map = {m["salesman_name"]: m for m in master_list if m.get("salesman_name")}

        customer_to_salesman = {}
        for m in master_list:
            sname = m.get("salesman_name")
            if not sname:
                continue
            for cust in m.get("customers", []):
                customer_to_salesman[cust.lower()] = sname

        salesman_map = {}
        for voucher in vouchers:
            customer = voucher.get("party_name", "")
            salesman = customer_to_salesman.get(customer.lower(), voucher.get("salesman", "Unassigned"))
            amount = safe_num(voucher.get("total_amount"))

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

        for m in master_list:
            name = m.get("salesman_name")
            if not name or name in salesman_map:
                continue
            salesman_map[name] = {
                "salesman_name": name,
                "total_sales": 0,
                "customers": set(m.get("customers", [])),
                "transactions": 0
            }

        performance = []
        for salesman, data in salesman_map.items():
            master = master_map.get(salesman, {})
            monthly_target = safe_num(master.get("monthly_target"))
            performance.append({
                "salesman_name": salesman,
                "target_amount": monthly_target * 12 if monthly_target else 0,
                "achieved_amount": data["total_sales"],
                "achievement_percentage": (data["total_sales"] / (monthly_target * 12) * 100) if monthly_target > 0 else 0,
                "total_customers": len(data["customers"]),
                "total_transactions": data["transactions"],
                "average_transaction": data["total_sales"] / data["transactions"] if data["transactions"] > 0 else 0,
                "has_master": salesman in master_map
            })

        performance.sort(key=lambda x: x["achieved_amount"], reverse=True)

        return APIResponse(success=True, data={"salesman": performance})

    except Exception as e:
        logger.error(f"Error fetching salesman performance: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/salesman/master")
async def get_salesman_master(request: Request, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        salesmen = await db.salesman_master.find(q, {"_id": 0}).to_list(100)
        return APIResponse(success=True, data={"salesmen": salesmen})
    except Exception as e:
        logger.error(f"Error fetching salesman master: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/salesman/master")
async def create_salesman(request: Request):
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        salesman_name = body.get("salesman_name", "").strip()
        if not salesman_name:
            return APIResponse(success=False, error="Salesman name is required")

        customers = body.get("customers", [])
        monthly_target = body.get("monthly_target", 0)
        quarterly_target = body.get("quarterly_target", 0)
        phone = body.get("phone", "")
        email = body.get("email", "")

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
        if ctx and ctx.get("tenant_id"):
            doc["tenant_id"] = ctx["tenant_id"]
        if ctx and ctx.get("company_id"):
            doc["company_id"] = ctx["company_id"]

        tq = _build_query(ctx)
        await db.salesman_master.update_one(
            {**tq, "salesman_name": salesman_name},
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


@router.delete("/salesman/master/{salesman_name}")
async def delete_salesman(salesman_name: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)
        result = await db.salesman_master.delete_one({**tq, "salesman_name": salesman_name})
        return APIResponse(
            success=result.deleted_count > 0,
            message="Deleted" if result.deleted_count > 0 else "Not found"
        )
    except Exception as e:
        logger.error(f"Error deleting salesman: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/salesman/performance-detailed")
async def get_salesman_performance_detailed(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        vouchers = filter_vouchers_by_fy(all_vouchers, fy)
        master_list = await db.salesman_master.find(q, {"_id": 0}).to_list(100)
        master_map = {m["salesman_name"]: m for m in master_list if m.get("salesman_name")}

        customer_to_salesman = {}
        for m in master_list:
            sname = m.get("salesman_name")
            if not sname:
                continue
            for cust in m.get("customers", []):
                customer_to_salesman[cust.lower()] = sname

        salesman_map = {}
        for voucher in vouchers:
            customer = voucher.get("party_name", "")
            salesman = customer_to_salesman.get(customer.lower(), voucher.get("salesman", "Unassigned"))
            amount = safe_num(voucher.get("total_amount"))

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
                qty = safe_num(item.get("quantity"))
                rate = safe_num(item.get("rate"))
                item_amount = safe_num(item.get("amount"), qty * rate)
                if item_name:
                    if item_name not in salesman_map[salesman]["items_sold"]:
                        salesman_map[salesman]["items_sold"][item_name] = {
                            "item_name": item_name,
                            "total_quantity": 0,
                            "total_revenue": 0,
                            "transaction_count": 0
                        }
                    salesman_map[salesman]["items_sold"][item_name]["total_quantity"] += qty
                    salesman_map[salesman]["items_sold"][item_name]["total_revenue"] += item_amount
                    salesman_map[salesman]["items_sold"][item_name]["transaction_count"] += 1

        for m in master_list:
            name = m.get("salesman_name")
            if not name or name in salesman_map:
                continue
            salesman_map[name] = {
                "salesman_name": name,
                "total_sales": 0,
                "customers": set(m.get("customers", [])),
                "transactions": 0,
                "items_sold": {}
            }

        performance = []
        for salesman, data in salesman_map.items():
            master = master_map.get(salesman, {})
            monthly_target = safe_num(master.get("monthly_target"))

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
                "quarterly_target": safe_num(master.get("quarterly_target"), monthly_target * 3),
                "achieved_amount": data["total_sales"],
                "achievement_percentage": (data["total_sales"] / (monthly_target * 12) * 100) if monthly_target > 0 else 0,
                "total_customers": len(data["customers"]),
                "customer_names": list(data["customers"]),
                "mapped_customers": master.get("customers", []),
                "total_transactions": data["transactions"],
                "average_transaction": data["total_sales"] / data["transactions"] if data["transactions"] > 0 else 0,
                "items_sold": items_breakdown,
                "has_master": salesman in master_map
            })

        performance.sort(key=lambda x: x["achieved_amount"], reverse=True)

        return APIResponse(success=True, data={"salesman": performance})

    except Exception as e:
        logger.error(f"Error fetching detailed salesman performance: {e}")
        return APIResponse(success=False, error=str(e))
