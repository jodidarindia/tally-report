"""Insider Result routes — advanced analytics for customer lifecycle, forecasting, SPIP, and concentration risk."""
from fastapi import APIRouter, Request
from typing import Optional
from datetime import datetime, timezone, date as date_type, timedelta
from collections import defaultdict
import logging

from db import db
from models import APIResponse
from services.tenant_context import get_tenant_context
from utils import filter_vouchers_by_fy

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_query(ctx, company_id=None):
    """Build tenant+company filter."""
    if not ctx:
        return {}
    f = {}
    tid = ctx.get("tenant_id")
    if tid:
        f["tenant_id"] = tid
    cid = company_id or ctx.get("company_id")
    if cid:
        f["company_id"] = cid
    return f


# ===================== 1. CUSTOMER LIFECYCLE =====================

@router.get("/insights/customer-lifecycle")
async def get_customer_lifecycle(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Classify customers as Active/Inactive/Lost based on last transaction date."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        today = date_type.today()

        vouchers = await db.sales_vouchers.find(q, {"_id": 0, "party_name": 1, "voucher_date": 1, "amount": 1, "total_amount": 1}).to_list(20000)
        if fy:
            vouchers = filter_vouchers_by_fy(vouchers, fy)

        customer_data = defaultdict(lambda: {"dates": [], "total": 0, "count": 0})
        for v in vouchers:
            party = v.get("party_name", "")
            if not party:
                continue
            d = v.get("voucher_date", "")
            amt = v.get("total_amount") or v.get("amount") or 0
            customer_data[party]["dates"].append(d)
            customer_data[party]["total"] += abs(float(amt)) if amt else 0
            customer_data[party]["count"] += 1

        active, inactive, lost = [], [], []
        for name, data in customer_data.items():
            dates_sorted = sorted([d for d in data["dates"] if d], reverse=True)
            last_date = dates_sorted[0] if dates_sorted else ""
            first_date = dates_sorted[-1] if dates_sorted else ""

            days_since = 999
            if last_date:
                try:
                    parts = last_date.split("-")
                    ld = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_since = (today - ld).days
                except (ValueError, IndexError):
                    pass

            status = "lost" if days_since > 180 else ("inactive" if days_since > 90 else "active")
            entry = {
                "customer_name": name,
                "status": status,
                "last_transaction": last_date,
                "first_transaction": first_date,
                "days_since_last": days_since,
                "total_revenue": round(data["total"], 2),
                "transaction_count": data["count"],
            }

            if status == "active":
                active.append(entry)
            elif status == "inactive":
                inactive.append(entry)
            else:
                lost.append(entry)

        # Monthly trend (last 12 months)
        monthly_counts = defaultdict(lambda: {"active": 0, "inactive": 0, "lost": 0})
        for m_offset in range(12):
            d = today - timedelta(days=m_offset * 30)
            month_key = d.strftime("%Y-%m")
            for name, data in customer_data.items():
                month_dates = [dt for dt in data["dates"] if dt and dt.startswith(month_key)]
                if month_dates:
                    monthly_counts[month_key]["active"] += 1

        trend = [{"month": k, **v} for k, v in sorted(monthly_counts.items())]

        return APIResponse(success=True, data={
            "active": sorted(active, key=lambda x: x["total_revenue"], reverse=True),
            "inactive": sorted(inactive, key=lambda x: x["total_revenue"], reverse=True),
            "lost": sorted(lost, key=lambda x: x["total_revenue"], reverse=True),
            "summary": {
                "active_count": len(active),
                "inactive_count": len(inactive),
                "lost_count": len(lost),
                "active_revenue": round(sum(c["total_revenue"] for c in active), 2),
                "inactive_revenue": round(sum(c["total_revenue"] for c in inactive), 2),
                "lost_revenue": round(sum(c["total_revenue"] for c in lost), 2),
            },
            "trend": trend[-12:]
        })
    except Exception as e:
        logger.error(f"Customer lifecycle error: {e}")
        return APIResponse(success=False, error=str(e))


# ===================== 2. SALES FORECASTING =====================

@router.get("/insights/sales-forecast")
async def get_sales_forecast(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Sales trend with moving average forecast for next 3 months."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        vouchers = await db.sales_vouchers.find(q, {"_id": 0, "voucher_date": 1, "amount": 1, "total_amount": 1, "party_name": 1}).to_list(20000)
        if fy:
            vouchers = filter_vouchers_by_fy(vouchers, fy)

        monthly_sales = defaultdict(lambda: {"revenue": 0, "count": 0, "customers": set()})
        for v in vouchers:
            d = v.get("voucher_date", "")
            if not d:
                continue
            month = d[:7]
            amt = v.get("total_amount") or v.get("amount") or 0
            monthly_sales[month]["revenue"] += abs(float(amt)) if amt else 0
            monthly_sales[month]["count"] += 1
            party = v.get("party_name", "")
            if party:
                monthly_sales[month]["customers"].add(party)

        # Build sorted timeline
        months_sorted = sorted(monthly_sales.keys())
        timeline = []
        for m in months_sorted:
            d = monthly_sales[m]
            timeline.append({
                "month": m,
                "revenue": round(d["revenue"], 2),
                "count": d["count"],
                "unique_customers": len(d["customers"]),
            })

        # Calculate 3-month moving average for forecast
        revenues = [t["revenue"] for t in timeline]
        forecasts = []
        if len(revenues) >= 3:
            ma3 = sum(revenues[-3:]) / 3
            ma6 = sum(revenues[-6:]) / 6 if len(revenues) >= 6 else ma3
            # Simple weighted forecast: 60% recent MA + 40% longer MA
            base_forecast = 0.6 * ma3 + 0.4 * ma6

            today = date_type.today()
            for i in range(1, 4):
                fd = today.replace(day=1) + timedelta(days=32 * i)
                forecast_month = fd.strftime("%Y-%m")
                # Add slight trend adjustment
                trend_factor = 1.0
                if len(revenues) >= 6:
                    recent_avg = sum(revenues[-3:]) / 3
                    older_avg = sum(revenues[-6:-3]) / 3
                    if older_avg > 0:
                        trend_factor = min(1.3, max(0.7, recent_avg / older_avg))

                forecasts.append({
                    "month": forecast_month,
                    "forecast_revenue": round(base_forecast * (trend_factor ** i), 2),
                    "confidence": "high" if len(revenues) >= 12 else ("medium" if len(revenues) >= 6 else "low"),
                })

        # Year-over-year comparison
        yoy = {}
        for t in timeline:
            y = t["month"][:4]
            yoy.setdefault(y, {"revenue": 0, "count": 0})
            yoy[y]["revenue"] += t["revenue"]
            yoy[y]["count"] += t["count"]

        return APIResponse(success=True, data={
            "timeline": timeline,
            "forecasts": forecasts,
            "yoy": [{"year": k, **v} for k, v in sorted(yoy.items())],
            "summary": {
                "total_months": len(timeline),
                "avg_monthly_revenue": round(sum(revenues) / len(revenues), 2) if revenues else 0,
                "best_month": max(timeline, key=lambda t: t["revenue"])["month"] if timeline else "",
                "best_month_revenue": max(revenues) if revenues else 0,
            }
        })
    except Exception as e:
        logger.error(f"Sales forecast error: {e}")
        return APIResponse(success=False, error=str(e))


# ===================== 3. SPIP GAP ANALYSIS =====================

@router.get("/insights/spip-analysis")
async def get_spip_analysis(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Sales vs Purchase vs Inventory gap analysis."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        # Get sales vouchers with items
        sales = await db.sales_vouchers.find(q, {"_id": 0}).to_list(20000)
        if fy:
            sales = filter_vouchers_by_fy(sales, fy)

        # Get inventory items
        inventory = await db.inventory_items.find(q, {"_id": 0}).to_list(5000)

        # Build item-level analysis from sales
        item_sales = defaultdict(lambda: {"qty_sold": 0, "revenue": 0, "months_active": set()})
        for v in sales:
            items_list = v.get("items") or v.get("inventory_entries") or []
            date_str = v.get("voucher_date", "")
            month = date_str[:7] if date_str else ""
            for item in items_list:
                name = item.get("item_name") or item.get("stock_item_name") or ""
                if not name:
                    continue
                qty = abs(float(item.get("quantity") or item.get("billed_qty") or 0))
                amt = abs(float(item.get("amount") or item.get("rate", 0) * qty))
                item_sales[name]["qty_sold"] += qty
                item_sales[name]["revenue"] += amt
                if month:
                    item_sales[name]["months_active"].add(month)

        # Build inventory map
        inv_map = {}
        for inv in inventory:
            name = inv.get("item_name", "")
            if name:
                inv_map[name] = {
                    "stock_qty": inv.get("quantity") or inv.get("closing_balance") or 0,
                    "stock_group": inv.get("stock_group", ""),
                    "purchase_price": inv.get("purchase_price") or inv.get("price") or 0,
                }

        # Cross-reference: items in stock but not selling, items selling but low stock
        analysis = []
        all_items = set(list(item_sales.keys()) + list(inv_map.keys()))
        for item_name in all_items:
            s = item_sales.get(item_name, {"qty_sold": 0, "revenue": 0, "months_active": set()})
            inv = inv_map.get(item_name, {"stock_qty": 0, "stock_group": "", "purchase_price": 0})

            stock_qty = float(inv["stock_qty"])
            qty_sold = s["qty_sold"]
            months = len(s["months_active"])
            monthly_avg = qty_sold / months if months > 0 else 0
            months_of_stock = stock_qty / monthly_avg if monthly_avg > 0 else (999 if stock_qty > 0 else 0)

            # Classify
            if stock_qty > 0 and qty_sold == 0:
                gap_type = "dead_stock"
            elif months_of_stock > 6:
                gap_type = "overstocked"
            elif 0 < months_of_stock < 1 and qty_sold > 0:
                gap_type = "understocked"
            elif qty_sold > 0 and stock_qty <= 0:
                gap_type = "out_of_stock"
            else:
                gap_type = "balanced"

            analysis.append({
                "item_name": item_name,
                "stock_group": inv.get("stock_group", ""),
                "stock_qty": round(stock_qty, 2),
                "qty_sold": round(qty_sold, 2),
                "revenue": round(s["revenue"], 2),
                "months_active": months,
                "monthly_avg_sales": round(monthly_avg, 2),
                "months_of_stock": round(min(months_of_stock, 999), 1),
                "gap_type": gap_type,
            })

        # Sort: problematic items first
        priority = {"out_of_stock": 0, "understocked": 1, "dead_stock": 2, "overstocked": 3, "balanced": 4}
        analysis.sort(key=lambda x: (priority.get(x["gap_type"], 5), -x["revenue"]))

        gap_summary = defaultdict(int)
        for a in analysis:
            gap_summary[a["gap_type"]] += 1

        return APIResponse(success=True, data={
            "items": analysis[:200],
            "summary": dict(gap_summary),
            "total_items": len(analysis),
        })
    except Exception as e:
        logger.error(f"SPIP analysis error: {e}")
        return APIResponse(success=False, error=str(e))


# ===================== 4. CONCENTRATION RISK (PARETO) =====================

@router.get("/insights/concentration-risk")
async def get_concentration_risk(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Pareto analysis — customer revenue concentration risk."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        vouchers = await db.sales_vouchers.find(q, {"_id": 0, "party_name": 1, "voucher_date": 1, "amount": 1, "total_amount": 1}).to_list(20000)
        if fy:
            vouchers = filter_vouchers_by_fy(vouchers, fy)

        customer_revenue = defaultdict(float)
        for v in vouchers:
            party = v.get("party_name", "")
            amt = v.get("total_amount") or v.get("amount") or 0
            if party:
                customer_revenue[party] += abs(float(amt)) if amt else 0

        if not customer_revenue:
            return APIResponse(success=True, data={
                "customers": [], "summary": {}, "risk_level": "no_data"
            })

        total_revenue = sum(customer_revenue.values())
        sorted_customers = sorted(customer_revenue.items(), key=lambda x: x[1], reverse=True)

        # Build Pareto curve
        cumulative = 0
        pareto = []
        for i, (name, rev) in enumerate(sorted_customers):
            cumulative += rev
            pct = round(rev / total_revenue * 100, 2)
            cum_pct = round(cumulative / total_revenue * 100, 2)
            pareto.append({
                "rank": i + 1,
                "customer_name": name,
                "revenue": round(rev, 2),
                "pct_of_total": pct,
                "cumulative_pct": cum_pct,
            })

        # Risk metrics
        total_customers = len(sorted_customers)
        top5_rev = sum(r for _, r in sorted_customers[:5])
        top10_rev = sum(r for _, r in sorted_customers[:10])
        top20pct_count = max(1, total_customers // 5)
        top20pct_rev = sum(r for _, r in sorted_customers[:top20pct_count])

        top5_pct = round(top5_rev / total_revenue * 100, 1) if total_revenue else 0
        top10_pct = round(top10_rev / total_revenue * 100, 1) if total_revenue else 0
        top20pct_pct = round(top20pct_rev / total_revenue * 100, 1) if total_revenue else 0

        # Risk level
        if top5_pct > 80:
            risk = "critical"
        elif top5_pct > 60:
            risk = "high"
        elif top10_pct > 80:
            risk = "moderate"
        else:
            risk = "healthy"

        return APIResponse(success=True, data={
            "customers": pareto[:50],
            "summary": {
                "total_customers": total_customers,
                "total_revenue": round(total_revenue, 2),
                "top5_pct": top5_pct,
                "top10_pct": top10_pct,
                "top20pct_pct": top20pct_pct,
                "top5_revenue": round(top5_rev, 2),
                "top10_revenue": round(top10_rev, 2),
            },
            "risk_level": risk,
        })
    except Exception as e:
        logger.error(f"Concentration risk error: {e}")
        return APIResponse(success=False, error=str(e))
