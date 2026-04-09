from fastapi import APIRouter
from typing import Optional
from datetime import datetime
import logging

from db import db
from models import (
    InventoryItem, SalesVoucher, APIResponse,
    PurchaseOrder, PurchaseOrderItem
)
from utils import safe_num, filter_vouchers_by_fy
from services.purchase_order_ai import PurchaseOrderAI

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/inventory/items")
async def get_inventory_items(category: Optional[str] = None, stock_group: Optional[str] = None, min_quantity: Optional[float] = None):
    try:
        query = {}
        if category and category != 'all':
            query["category"] = category
        if stock_group and stock_group != 'all':
            query["stock_group"] = stock_group
        if min_quantity is not None:
            query["quantity"] = {"$gte": min_quantity}

        items = await db.inventory_items.find(query, {"_id": 0}).to_list(5000)

        all_items = await db.inventory_items.find({}, {"_id": 0, "stock_group": 1}).to_list(5000)
        stock_groups = sorted(list(set(item.get("stock_group", "General") for item in all_items if item.get("stock_group"))))

        return APIResponse(
            success=True,
            data={"items": items, "count": len(items), "stock_groups": stock_groups}
        )
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/summary")
async def get_inventory_summary(fy: Optional[str] = None):
    try:
        items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)

        if not items:
            return APIResponse(
                success=True,
                data={"total_items": 0, "total_value": 0, "low_stock_items": 0, "categories": []}
            )

        total_items = len(items)
        total_value = sum(safe_num(item.get("quantity")) * safe_num(item.get("price")) for item in items)
        low_stock_items = sum(1 for item in items if safe_num(item.get("quantity")) < safe_num(item.get("reorder_level")))
        categories = list(set(item.get("category") for item in items if item.get("category")))

        fy_sales_value = 0
        if fy:
            all_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
            fy_vouchers = filter_vouchers_by_fy(all_vouchers, fy)
            fy_sales_value = sum(safe_num(v.get("total_amount")) for v in fy_vouchers)

        return APIResponse(
            success=True,
            data={
                "total_items": total_items,
                "total_value": round(total_value, 2),
                "low_stock_items": low_stock_items,
                "categories": categories,
                "fy_sales_value": round(fy_sales_value, 2)
            }
        )
    except Exception as e:
        logger.error(f"Error getting inventory summary: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/inventory/generate-purchase-order")
async def generate_purchase_order():
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)

        po_ai = PurchaseOrderAI()
        result = await po_ai.generate_purchase_order(inventory_items, sales_vouchers)

        if result.get("success"):
            po_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            po_data = result.get("purchase_order", {})

            po_items = []
            for item in po_data.get("urgent_items", po_data.get("items", [])):
                try:
                    po_items.append(PurchaseOrderItem(**item))
                except Exception:
                    po_items.append(PurchaseOrderItem(
                        item_name=str(item.get("item_name", item.get("name", "Unknown"))),
                        current_stock=safe_num(item.get("current_stock")),
                        recommended_quantity=safe_num(item.get("recommended_quantity", item.get("quantity", 0))),
                        priority=str(item.get("priority", "medium")),
                        reason=str(item.get("reason", "")),
                        estimated_cost=safe_num(item.get("estimated_cost", item.get("cost", 0)))
                    ))

            purchase_order = PurchaseOrder(
                po_number=po_number,
                items=po_items,
                total_items=len(po_items),
                total_cost=po_data.get("total_estimated_cost", sum(i.estimated_cost for i in po_items)),
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


@router.get("/inventory/purchase-orders")
async def get_purchase_orders(status: Optional[str] = None):
    try:
        query = {}
        if status:
            query["status"] = status
        pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return APIResponse(success=True, data={"purchase_orders": pos, "count": len(pos)})
    except Exception as e:
        logger.error(f"Error fetching purchase orders: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/sales-frequency")
async def get_sales_frequency(start_date: Optional[str] = None, end_date: Optional[str] = None, fy: Optional[str] = None):
    try:
        all_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

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

        item_stats = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                qty = safe_num(item.get("quantity"))

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
                item_stats[item_name]["total_revenue"] += qty * safe_num(item.get("rate"))

        frequency_data = []
        for item_name, stats in item_stats.items():
            frequency_data.append({
                "item_name": item_name,
                "total_quantity_sold": stats["total_quantity_sold"],
                "transaction_count": stats["transaction_count"],
                "unique_customers": len(stats["unique_customers"]),
                "total_revenue": round(stats["total_revenue"], 2),
                "avg_quantity_per_transaction": round(
                    stats["total_quantity_sold"] / stats["transaction_count"], 1
                ) if stats["transaction_count"] > 0 else 0,
                "customer_list": list(stats["unique_customers"])
            })

        frequency_data.sort(key=lambda x: x["transaction_count"], reverse=True)

        return APIResponse(success=True, data={"frequency": frequency_data, "total_items": len(frequency_data)})
    except Exception as e:
        logger.error(f"Error getting sales frequency: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/movement-analysis")
async def get_inventory_movement(fy: Optional[str] = None):
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

        item_sales = {}
        for voucher in sales_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                if item_name:
                    item_sales[item_name.lower()] = item_sales.get(item_name.lower(), 0) + qty

        movement_data = []
        seen_items = set()
        for item in inventory_items:
            item_name = item.get("item_name", "")
            current_stock = safe_num(item.get("quantity"))
            sales_qty = item_sales.get(item_name.lower(), 0)
            seen_items.add(item_name.lower())

            opening_stock = current_stock + sales_qty
            avg_stock = (opening_stock + current_stock) / 2
            movement_rate = (sales_qty / avg_stock * 100) if avg_stock > 0 else 0
            days_to_sell = (current_stock / (sales_qty / 30)) if sales_qty > 0 else 999

            movement_data.append({
                "item_name": item_name,
                "category": item.get("category", item.get("stock_group", "General")),
                "opening_stock": round(opening_stock, 2),
                "purchases": 0,
                "sales": round(sales_qty, 2),
                "closing_stock": round(current_stock, 2),
                "movement_rate": round(movement_rate, 2),
                "days_to_sell": round(min(days_to_sell, 999), 1),
                "classification": "fast-moving" if movement_rate > 30 else "slow-moving" if movement_rate > 10 else "dead-stock"
            })

        for item_key, qty in item_sales.items():
            if item_key not in seen_items and qty > 0:
                movement_data.append({
                    "item_name": item_key.title(),
                    "category": "General",
                    "opening_stock": qty,
                    "purchases": 0,
                    "sales": round(qty, 2),
                    "closing_stock": 0,
                    "movement_rate": 100.0,
                    "days_to_sell": 0,
                    "classification": "fast-moving"
                })

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


@router.get("/inventory/below-cost-sales")
async def get_below_cost_sales(fy: Optional[str] = None):
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

        item_costs = {}
        for item in inventory_items:
            name = item.get("item_name", "")
            if not name:
                continue
            item_costs[name] = {
                "purchase_price": safe_num(item.get("purchase_price"), safe_num(item.get("price")) * 0.7),
                "selling_price": safe_num(item.get("price"))
            }

        below_cost_sales = []
        for voucher in sales_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "")
                sale_price = safe_num(item.get("rate"))
                quantity = safe_num(item.get("quantity"))

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

        below_cost_sales.sort(key=lambda x: x["total_loss"], reverse=True)

        return APIResponse(
            success=True,
            data={
                "below_cost_sales": below_cost_sales,
                "total_loss": round(sum(b["total_loss"] for b in below_cost_sales), 2),
                "count": len(below_cost_sales)
            }
        )
    except Exception as e:
        logger.error(f"Error analyzing below-cost sales: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/pivot-data")
async def get_pivot_data(group_by: str = "category", metric: str = "value"):
    try:
        inventory_items = await db.inventory_items.find({}, {"_id": 0}).to_list(10000)

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
            pivot_data[group_key]["total_quantity"] += safe_num(item.get("quantity"))
            pivot_data[group_key]["total_value"] += safe_num(item.get("quantity")) * safe_num(item.get("price"))
            pivot_data[group_key]["items"].append(item)

        pivot_list = list(pivot_data.values())

        if metric == "value":
            pivot_list.sort(key=lambda x: x["total_value"], reverse=True)
        elif metric == "quantity":
            pivot_list.sort(key=lambda x: x["total_quantity"], reverse=True)
        else:
            pivot_list.sort(key=lambda x: x["total_items"], reverse=True)

        return APIResponse(
            success=True,
            data={"pivot_table": pivot_list, "group_by": group_by, "metric": metric}
        )
    except Exception as e:
        logger.error(f"Error creating pivot table: {e}")
        return APIResponse(success=False, error=str(e))
