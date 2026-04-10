from fastapi import APIRouter, Request
from typing import Optional
from datetime import datetime
import logging

from db import db
from models import (
    InventoryItem, SalesVoucher, APIResponse,
    PurchaseOrder, PurchaseOrderItem
)
from utils import safe_num, filter_vouchers_by_fy, fy_to_date_range
from services.purchase_order_ai import PurchaseOrderAI
from services.tenant_context import get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_query(ctx, company_id=None, extra=None):
    """Build a tenant-filtered query dict."""
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    cid = company_id or (ctx.get("company_id") if ctx else None)
    if cid:
        q["company_id"] = cid
    if extra:
        q.update(extra)
    return q


@router.get("/inventory/items")
async def get_inventory_items(request: Request, category: Optional[str] = None, stock_group: Optional[str] = None, min_quantity: Optional[float] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        extra = {}
        if category and category != 'all':
            extra["category"] = category
        if stock_group and stock_group != 'all':
            extra["stock_group"] = stock_group
        if min_quantity is not None:
            extra["quantity"] = {"$gte": min_quantity}

        query = _build_query(ctx, company_id, extra)
        items = await db.inventory_items.find(query, {"_id": 0}).to_list(5000)

        base_q = _build_query(ctx, company_id)
        all_items = await db.inventory_items.find(base_q, {"_id": 0, "stock_group": 1}).to_list(5000)
        stock_groups = sorted(list(set(item.get("stock_group", "General") for item in all_items if item.get("stock_group"))))

        return APIResponse(
            success=True,
            data={"items": items, "count": len(items), "stock_groups": stock_groups}
        )
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/summary")
async def get_inventory_summary(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)

        if not items:
            return APIResponse(
                success=True,
                data={"total_items": 0, "total_value": 0, "low_stock_items": 0, "categories": []}
            )

        total_items = len(items)

        # Compute total value: prefer closing_value, then qty*price
        total_value = 0.0
        for item in items:
            cv = safe_num(item.get("closing_value"))
            if cv > 0:
                total_value += cv
            else:
                total_value += safe_num(item.get("quantity")) * safe_num(item.get("price"))

        # Low stock: use movement-based analysis
        # Items with qty=0 but that had sales activity are out-of-stock (genuinely low)
        # Items with qty=0 and no sales data: skip (master data only)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        fy_vouchers = filter_vouchers_by_fy(all_vouchers, fy) if fy else all_vouchers

        # Build set of items that had sales (i.e. actively traded)
        active_items = set()
        for v in fy_vouchers:
            for vi in v.get("items", []):
                iname = vi.get("item", "").strip()
                if iname:
                    active_items.add(iname.lower())

        low_stock_items = 0
        for item in items:
            qty = safe_num(item.get("quantity"))
            name = (item.get("item_name") or "").lower()
            reorder = safe_num(item.get("reorder_level"))
            if qty > 0 and reorder > 0 and qty < reorder:
                low_stock_items += 1
            elif qty == 0 and name in active_items:
                # Out of stock but actively sold — flag as low stock
                low_stock_items += 1

        categories = list(set(item.get("category") for item in items if item.get("category")))

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
async def generate_purchase_order(request: Request, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)

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
async def get_purchase_orders(request: Request, status: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        extra = {}
        if status:
            extra["status"] = status
        query = _build_query(ctx, company_id, extra)
        pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return APIResponse(success=True, data={"purchase_orders": pos, "count": len(pos)})
    except Exception as e:
        logger.error(f"Error fetching purchase orders: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/sales-frequency")
async def get_sales_frequency(request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
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
async def get_inventory_movement(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

        # Try to get purchase data (if synced)
        purchase_vouchers_raw = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(10000)
        purchase_vouchers = filter_vouchers_by_fy(purchase_vouchers_raw, fy) if purchase_vouchers_raw else []

        # Calculate FY duration in days for rate calculations
        from datetime import date as date_type
        if fy:
            fy_start_str, fy_end_str = fy_to_date_range(fy)
            try:
                fy_start_parts = fy_start_str.split('-')
                fy_end_parts = fy_end_str.split('-')
                fy_start = date_type(int(fy_start_parts[0]), int(fy_start_parts[1]), int(fy_start_parts[2]))
                fy_end = date_type(int(fy_end_parts[0]), int(fy_end_parts[1]), int(fy_end_parts[2]))
                today = date_type.today()
                # If FY is still running, use today as end date
                effective_end = min(fy_end, today)
                fy_days = max((effective_end - fy_start).days, 1)
            except (ValueError, TypeError):
                fy_days = 365
        else:
            fy_days = 365

        # Aggregate item-wise sales: qty, revenue, txn count, first/last date
        item_sales = {}
        for voucher in sales_vouchers:
            vdate = voucher.get("voucher_date", "")
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                amount = safe_num(item.get("amount"))
                if item_name:
                    key = item_name.lower()
                    if key not in item_sales:
                        item_sales[key] = {"qty": 0, "revenue": 0, "txns": 0, "first_date": vdate, "last_date": vdate}
                    item_sales[key]["qty"] += qty
                    item_sales[key]["revenue"] += amount
                    item_sales[key]["txns"] += 1
                    if vdate < item_sales[key]["first_date"]:
                        item_sales[key]["first_date"] = vdate
                    if vdate > item_sales[key]["last_date"]:
                        item_sales[key]["last_date"] = vdate

        # Aggregate item-wise purchases (inward)
        item_purchases = {}
        for voucher in purchase_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                if item_name:
                    key = item_name.lower()
                    item_purchases[key] = item_purchases.get(key, 0) + qty

        movement_data = []
        seen_items = set()
        for item in inventory_items:
            item_name = item.get("item_name", "")
            closing_stock = safe_num(item.get("quantity"))
            opening_from_tally = safe_num(item.get("opening_quantity"))
            cost_price = safe_num(item.get("price", item.get("rate", 0)))
            key = item_name.lower()
            seen_items.add(key)

            sales_info = item_sales.get(key, {"qty": 0, "revenue": 0, "txns": 0})
            sales_qty = sales_info["qty"]
            purchase_qty = item_purchases.get(key, 0)

            # Opening stock: use Tally opening_quantity if available, else estimate
            if opening_from_tally > 0:
                opening_stock = opening_from_tally
            else:
                # Estimate: Closing + Outward - Inward
                opening_stock = closing_stock + sales_qty - purchase_qty
                if opening_stock < 0:
                    opening_stock = 0

            # Inward from purchases
            inward = purchase_qty

            # Movement Rate = (Outward / Opening) * 100
            # Represents what percentage of opening stock was sold
            if opening_stock > 0:
                movement_rate = round((sales_qty / opening_stock) * 100, 1)
            elif sales_qty > 0:
                movement_rate = 100.0  # All stock sold (opening was approx = sales)
            else:
                movement_rate = 0.0

            # Days to sell remaining stock at current rate
            daily_sales = sales_qty / fy_days if fy_days > 0 else 0
            if closing_stock > 0 and daily_sales > 0:
                days_to_sell = round(closing_stock / daily_sales, 1)
            elif closing_stock > 0 and sales_qty == 0:
                days_to_sell = 999  # Stock exists but no sales
            else:
                days_to_sell = 0  # No stock remaining

            # Monthly average sales
            fy_months = max(fy_days / 30, 1)
            monthly_avg = round(sales_qty / fy_months, 1) if sales_qty > 0 else 0

            # Classification based on sales frequency and movement
            if sales_qty == 0:
                classification = "non-moving"
            elif sales_info["txns"] >= fy_months * 2:  # Sells twice+ per month
                classification = "fast-moving"
            elif sales_info["txns"] >= fy_months * 0.5:  # Sells at least every 2 months
                classification = "moderate"
            elif sales_info["txns"] > 0:
                classification = "slow-moving"
            else:
                classification = "non-moving"

            movement_data.append({
                "item_name": item_name,
                "category": item.get("category", item.get("stock_group", "General")),
                "opening_stock": round(opening_stock, 1),
                "inward": round(inward, 1),
                "sales": round(sales_qty, 1),
                "closing_stock": round(closing_stock, 1),
                "movement_rate": movement_rate,
                "days_to_sell": min(days_to_sell, 999),
                "monthly_avg_sales": monthly_avg,
                "transactions": sales_info.get("txns", 0),
                "revenue": round(sales_info.get("revenue", 0), 2),
                "cost_price": round(cost_price, 2),
                "classification": classification,
            })

        # Items sold but not in inventory master
        for item_key, info in item_sales.items():
            if item_key not in seen_items and info["qty"] > 0:
                purchase_qty = item_purchases.get(item_key, 0)
                opening_est = info["qty"] - purchase_qty
                if opening_est < 0:
                    opening_est = 0
                fy_months = max(fy_days / 30, 1)
                monthly_avg = round(info["qty"] / fy_months, 1)
                classification = "fast-moving" if info["txns"] >= fy_months * 2 else "moderate" if info["txns"] >= fy_months * 0.5 else "slow-moving"
                movement_data.append({
                    "item_name": item_key.title(),
                    "category": "General",
                    "opening_stock": round(max(opening_est, info["qty"]), 1),
                    "inward": round(purchase_qty, 1),
                    "sales": round(info["qty"], 1),
                    "closing_stock": 0,
                    "movement_rate": 100.0,
                    "days_to_sell": 0,
                    "monthly_avg_sales": monthly_avg,
                    "transactions": info["txns"],
                    "revenue": round(info["revenue"], 2),
                    "classification": classification,
                })

        movement_data.sort(key=lambda x: x["transactions"], reverse=True)

        return APIResponse(
            success=True,
            data={
                "movements": movement_data,
                "summary": {
                    "fast_moving": len([m for m in movement_data if m["classification"] == "fast-moving"]),
                    "moderate": len([m for m in movement_data if m["classification"] == "moderate"]),
                    "slow_moving": len([m for m in movement_data if m["classification"] == "slow-moving"]),
                    "non_moving": len([m for m in movement_data if m["classification"] == "non-moving"]),
                },
                "fy_days": fy_days,
            }
        )
    except Exception as e:
        logger.error(f"Error analyzing inventory movement: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/inventory/pivot-data")
async def get_pivot_data(request: Request, group_by: str = "category", metric: str = "value", company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)

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


# ==================== BELOW COST SALES ====================

@router.get("/inventory/below-cost-sales")
async def get_below_cost_sales(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Find items where sales price < purchase cost price (negative margin)."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)

        # Also get purchase vouchers for cost price
        purchase_vouchers_raw = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(10000)
        purchase_vouchers = filter_vouchers_by_fy(purchase_vouchers_raw, fy) if purchase_vouchers_raw else []

        # Build cost price map from inventory (Tally's rate/price field) and purchases
        cost_map = {}
        for item in inventory_items:
            name = item.get("item_name", "").lower()
            price = safe_num(item.get("price", item.get("rate", 0)))
            if price > 0:
                cost_map[name] = price

        # Override with purchase price if available (more accurate for FY)
        purchase_price_map = {}
        for pv in purchase_vouchers:
            for item in pv.get("items", []):
                iname = item.get("item", "").strip().lower()
                rate = safe_num(item.get("rate", 0))
                qty = safe_num(item.get("quantity", 0))
                if iname and rate > 0:
                    if iname not in purchase_price_map:
                        purchase_price_map[iname] = {"total_cost": 0, "total_qty": 0}
                    purchase_price_map[iname]["total_cost"] += abs(rate * qty)
                    purchase_price_map[iname]["total_qty"] += abs(qty)

        for iname, pdata in purchase_price_map.items():
            if pdata["total_qty"] > 0:
                cost_map[iname] = pdata["total_cost"] / pdata["total_qty"]

        # Build sales price map
        sales_price_map = {}
        for sv in sales_vouchers:
            for item in sv.get("items", []):
                iname = item.get("item", "").strip().lower()
                rate = safe_num(item.get("rate", 0))
                qty = safe_num(item.get("quantity", 0))
                amt = safe_num(item.get("amount", 0))
                if iname and (rate > 0 or (qty > 0 and amt != 0)):
                    if iname not in sales_price_map:
                        sales_price_map[iname] = {"total_revenue": 0, "total_qty": 0, "txns": 0}
                    sales_price_map[iname]["total_revenue"] += abs(amt) if amt else abs(rate * qty)
                    sales_price_map[iname]["total_qty"] += abs(qty)
                    sales_price_map[iname]["txns"] += 1

        below_cost_items = []
        for iname, sdata in sales_price_map.items():
            cost = cost_map.get(iname, 0)
            if cost <= 0 or sdata["total_qty"] <= 0:
                continue

            avg_selling_price = sdata["total_revenue"] / sdata["total_qty"]
            margin = avg_selling_price - cost
            margin_pct = (margin / cost) * 100

            if margin < 0:
                # Find display name
                display_name = iname
                for inv in inventory_items:
                    if inv.get("item_name", "").lower() == iname:
                        display_name = inv["item_name"]
                        break

                below_cost_items.append({
                    "item_name": display_name,
                    "cost_price": round(cost, 2),
                    "avg_selling_price": round(avg_selling_price, 2),
                    "margin": round(margin, 2),
                    "margin_pct": round(margin_pct, 1),
                    "qty_sold": round(sdata["total_qty"], 1),
                    "total_revenue": round(sdata["total_revenue"], 2),
                    "total_loss": round(abs(margin) * sdata["total_qty"], 2),
                    "transactions": sdata["txns"],
                })

        below_cost_items.sort(key=lambda x: x["total_loss"], reverse=True)

        return APIResponse(
            success=True,
            data={
                "items": below_cost_items,
                "summary": {
                    "total_items": len(below_cost_items),
                    "total_loss": round(sum(i["total_loss"] for i in below_cost_items), 2),
                    "total_affected_revenue": round(sum(i["total_revenue"] for i in below_cost_items), 2),
                },
            }
        )
    except Exception as e:
        logger.error(f"Error analyzing below-cost sales: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== MOVEMENT ANALYSIS EXCEL EXPORT ====================

@router.get("/inventory/movement-export")
async def export_movement_analysis(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Export movement analysis to Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from fastapi.responses import StreamingResponse
        import io

        # Reuse the movement-analysis logic
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        inventory_items_raw = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)
        purchase_vouchers_raw = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(10000)
        purchase_vouchers = filter_vouchers_by_fy(purchase_vouchers_raw, fy) if purchase_vouchers_raw else []

        # Build item sales and purchases maps
        item_sales = {}
        for voucher in sales_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                if item_name:
                    key = item_name.lower()
                    item_sales[key] = item_sales.get(key, 0) + qty

        item_purchases = {}
        for voucher in purchase_vouchers:
            for item in voucher.get("items", []):
                item_name = item.get("item", "").strip()
                qty = safe_num(item.get("quantity"))
                if item_name:
                    key = item_name.lower()
                    item_purchases[key] = item_purchases.get(key, 0) + qty

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Movement Analysis FY {fy or 'All'}"

        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        ws.merge_cells('A1:J1')
        ws['A1'] = f"Movement Analysis | FY: {fy or 'All'}"
        ws['A1'].font = Font(bold=True, size=12)
        ws.append([])

        headers = ["Item Name", "Category", "Opening Qty", "Inward (Purchases)", "Outward (Sales)", "Closing Qty", "Movement %", "Days to Sell", "Transactions", "Classification"]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

        for inv_item in inventory_items_raw:
            name = inv_item.get("item_name", "")
            key = name.lower()
            closing = safe_num(inv_item.get("quantity"))
            opening_tally = safe_num(inv_item.get("opening_quantity"))
            s_qty = item_sales.get(key, 0)
            p_qty = item_purchases.get(key, 0)
            opening = opening_tally if opening_tally > 0 else max(closing + s_qty - p_qty, 0)
            rate = round((s_qty / opening * 100), 1) if opening > 0 else (100.0 if s_qty > 0 else 0.0)
            daily = s_qty / 365 if s_qty > 0 else 0
            dts = round(closing / daily, 1) if closing > 0 and daily > 0 else (999 if closing > 0 else 0)
            cls_tag = "fast-moving" if s_qty > 0 and rate >= 50 else "moderate" if rate >= 20 else "slow-moving" if s_qty > 0 else "non-moving"

            ws.append([name, inv_item.get("category", ""), round(opening, 1), round(p_qty, 1), round(s_qty, 1), round(closing, 1), rate, dts if dts < 999 else "N/A", 0, cls_tag])

        for col_cells in ws.columns:
            valid_cells = [c for c in col_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)]
            if not valid_cells:
                continue
            max_len = max((len(str(cell.value or "")) for cell in valid_cells), default=10)
            ws.column_dimensions[valid_cells[0].column_letter].width = min(max_len + 4, 35)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"movement_analysis_{fy or 'all'}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error exporting movement analysis: {e}")
        return APIResponse(success=False, error=str(e))


# ==================== BELOW COST SALES EXCEL EXPORT ====================

@router.get("/inventory/below-cost-export")
async def export_below_cost_sales(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Export below-cost sales items to Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from fastapi.responses import StreamingResponse
        import io

        # Get the below-cost data
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        inventory_items_list = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_vouchers, fy)
        purchase_vouchers_raw = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(10000)
        purchase_vouchers = filter_vouchers_by_fy(purchase_vouchers_raw, fy) if purchase_vouchers_raw else []

        cost_map = {}
        for item in inventory_items_list:
            name = item.get("item_name", "").lower()
            price = safe_num(item.get("price", item.get("rate", 0)))
            if price > 0:
                cost_map[name] = price

        for pv in purchase_vouchers:
            for item in pv.get("items", []):
                iname = item.get("item", "").strip().lower()
                rate = safe_num(item.get("rate", 0))
                if iname and rate > 0:
                    cost_map[iname] = rate

        sales_map = {}
        for sv in sales_vouchers:
            for item in sv.get("items", []):
                iname = item.get("item", "").strip().lower()
                rate = safe_num(item.get("rate", 0))
                qty = safe_num(item.get("quantity", 0))
                amt = safe_num(item.get("amount", 0))
                if iname and qty > 0:
                    if iname not in sales_map:
                        sales_map[iname] = {"revenue": 0, "qty": 0}
                    sales_map[iname]["revenue"] += abs(amt) if amt else abs(rate * qty)
                    sales_map[iname]["qty"] += abs(qty)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Below Cost Sales FY {fy or 'All'}"

        header_fill = PatternFill(start_color="EF4444", end_color="EF4444", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)

        ws.merge_cells('A1:H1')
        ws['A1'] = f"Below Cost Sales | FY: {fy or 'All'}"
        ws['A1'].font = Font(bold=True, size=12, color="EF4444")
        ws.append([])

        headers = ["Item Name", "Cost Price", "Avg Selling Price", "Margin", "Margin %", "Qty Sold", "Revenue", "Total Loss"]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

        for iname, sdata in sorted(sales_map.items()):
            cost = cost_map.get(iname, 0)
            if cost <= 0 or sdata["qty"] <= 0:
                continue
            avg_sell = sdata["revenue"] / sdata["qty"]
            margin = avg_sell - cost
            if margin >= 0:
                continue
            ws.append([iname.title(), round(cost, 2), round(avg_sell, 2), round(margin, 2), round(margin / cost * 100, 1), round(sdata["qty"], 1), round(sdata["revenue"], 2), round(abs(margin) * sdata["qty"], 2)])

        for col_cells in ws.columns:
            valid_cells = [c for c in col_cells if not isinstance(c, openpyxl.cell.cell.MergedCell)]
            if not valid_cells:
                continue
            max_len = max((len(str(cell.value or "")) for cell in valid_cells), default=10)
            ws.column_dimensions[valid_cells[0].column_letter].width = min(max_len + 4, 35)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"below_cost_sales_{fy or 'all'}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error exporting below-cost sales: {e}")
        return APIResponse(success=False, error=str(e))
