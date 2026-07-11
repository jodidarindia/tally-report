from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import logging

from db import db
from models import (
    AIQuery, AIQueryRequest, ExportRequest, APIResponse
)
from utils import safe_num
from services.ai_service import AIReportService
from services.enhanced_ai_service import EnhancedAIReportService
from services.export_service import ExportService
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


def _fmt_num(x, dp: int = 2):
    """Format a number for exports; empty string if not a valid number."""
    try:
        if x is None or x == "":
            return ""
        return round(float(x), dp)
    except (TypeError, ValueError):
        return ""


def _summarise_items(items) -> str:
    """Collapse a list of voucher line items into a single readable cell:
    "POWER 20W40 CF4 5LT (4PC) x4 @1412; ATF DEXRON x2 @980"."""
    if not isinstance(items, list) or not items:
        return ""
    parts = []
    for it in items[:5]:  # cap noise in the cell
        if not isinstance(it, dict):
            continue
        name = str(it.get("item") or it.get("item_name") or "").strip()
        qty = it.get("quantity") or it.get("qty") or 0
        rate = it.get("rate") or it.get("price") or 0
        try:
            qty_str = f"x{int(qty)}" if float(qty).is_integer() else f"x{qty}"
        except (TypeError, ValueError):
            qty_str = f"x{qty}"
        try:
            rate_str = f" @{int(rate)}" if float(rate).is_integer() else f" @{rate}"
        except (TypeError, ValueError):
            rate_str = f" @{rate}" if rate else ""
        parts.append(f"{name} {qty_str}{rate_str}".strip())
    if len(items) > 5:
        parts.append(f"+{len(items) - 5} more")
    return "; ".join(parts)


def _project_export_rows(report_type: str, rows: list) -> list:
    """Return a list of dicts with clean, business-user-friendly columns
    matching the on-screen table (Sales / Inventory tabs). Drops internal
    fields like tenant_id / company_id / last_updated / _id etc."""
    if report_type == "sales":
        out = []
        for v in rows:
            out.append({
                "Date": v.get("voucher_date", ""),
                "Voucher #": v.get("voucher_id", ""),
                "Reference #": v.get("reference_number", "") or "",
                "Customer": v.get("party_name", ""),
                "Salesman": v.get("salesman") or "",
                "Voucher Type": (v.get("voucher_type") or "").title(),
                "Destination": v.get("destination", "") or "",
                "Dispatch Through": v.get("dispatch_through", "") or "",
                "Items": _summarise_items(v.get("items", [])),
                "Amount (Rs)": _fmt_num(v.get("total_amount"), 2),
            })
        return out
    if report_type == "inventory":
        out = []
        for it in rows:
            aliases = it.get("aliases")
            if isinstance(aliases, list):
                aliases_str = ", ".join(str(a) for a in aliases if a)
            else:
                aliases_str = str(aliases or "")
            out.append({
                "Item Name": it.get("item_name", ""),
                "Part #": it.get("part_number", "") or "",
                "ABC": it.get("abc_category", "") or "",
                "Category": it.get("category", "") or "",
                "Stock Group": it.get("stock_group", "") or "",
                "Unit": it.get("unit", "") or "",
                "Quantity": _fmt_num(it.get("quantity"), 2),
                "Reorder Level": _fmt_num(it.get("reorder_level"), 2),
                "Sale Price (Rs)": _fmt_num(
                    it.get("effective_sale_price") or it.get("standard_price") or it.get("price"), 2,
                ),
                "Purchase Price (Rs)": _fmt_num(it.get("purchase_price"), 2),
                "Stock Value (Rs)": _fmt_num(it.get("closing_value"), 2),
                "Aliases": aliases_str,
            })
        return out
    # Unknown type — fall back to the old "drop internal keys" behaviour.
    _INTERNAL = {"_id", "tenant_id", "company_id", "last_updated", "created_at"}
    return [{k: v for k, v in r.items() if k not in _INTERNAL} for r in rows]



@router.post("/ai/query")
async def ai_query(request: Request):
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, body.get("company_id"))
        query_text = body.get("query", "")

        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(1000)
        sales_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(1000)

        ai_service = AIReportService()
        result = await ai_service.generate_report(
            query=query_text,
            inventory_data=inventory_items,
            sales_data=sales_vouchers
        )

        ai_query_obj = AIQuery(
            query_text=query_text,
            response=result.get("raw_response"),
            report_data=result.get("report")
        )
        doc = ai_query_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if ctx and ctx.get("tenant_id"):
            doc["tenant_id"] = ctx["tenant_id"]
        if ctx and ctx.get("company_id"):
            doc["company_id"] = ctx["company_id"]
        await db.ai_queries.insert_one(doc)

        return APIResponse(
            success=result.get("success", False),
            data=result.get("report"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error processing AI query: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/ai/advanced-query")
async def ai_advanced_query(request: Request):
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, body.get("company_id"))

        inventory_items = await db.inventory_items.find(q, {"_id": 0}).to_list(10000)
        sales_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        customer_data = await db.customers.find(q, {"_id": 0}).to_list(1000)

        ai_service = EnhancedAIReportService()
        result = await ai_service.generate_advanced_report(
            query=body.get("query", ""),
            report_type=body.get("report_type", "general"),
            filters=body.get("filters", {}),
            inventory_data=inventory_items,
            sales_data=sales_vouchers,
            customer_data=customer_data
        )

        if result.get("success"):
            ai_query_obj = AIQuery(
                query_text=body.get("query", ""),
                response=result.get("raw_response"),
                report_data=result.get("report"),
                filters=body.get("filters")
            )
            doc = ai_query_obj.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            if ctx and ctx.get("tenant_id"):
                doc["tenant_id"] = ctx["tenant_id"]
            if ctx and ctx.get("company_id"):
                doc["company_id"] = ctx["company_id"]
            await db.ai_queries.insert_one(doc)

        return APIResponse(
            success=result.get("success", False),
            data=result.get("report"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error in advanced AI query: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/reports/export")
async def export_report(request: Request):
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, body.get("company_id"))
        report_type = body.get("report_type", "")
        export_format = body.get("format", "pdf")

        # iter-111: apply the same UI filters as /inventory/items so the
        # downloaded file matches what the user sees on screen.
        filters = body.get("filters") or {}

        if report_type == "inventory":
            extra = dict(q)
            cat = (filters.get("category") or "").strip()
            if cat and cat != "all":
                extra["category"] = cat

            # stock_group can be a CSV string (multi-select) or a single string.
            sg = filters.get("stock_group")
            if isinstance(sg, list):
                groups = [str(g).strip() for g in sg if str(g).strip()]
            elif isinstance(sg, str) and sg.strip() and sg.strip() != "all":
                groups = [g.strip() for g in sg.split(",") if g.strip()]
            else:
                groups = []
            if len(groups) == 1:
                extra["stock_group"] = groups[0]
            elif len(groups) > 1:
                extra["stock_group"] = {"$in": groups}

            rsg = (filters.get("root_stock_group") or "").strip()
            if rsg and rsg != "all":
                extra["root_stock_group"] = rsg.lower()

            abc = (filters.get("abc") or "").strip().upper()
            if abc in ("A", "B", "C", "D"):
                extra["abc_category"] = abc

            search = (filters.get("search") or "").strip()
            if search:
                try:
                    from utils import build_fuzzy_regex
                    fuzzy = build_fuzzy_regex(search)
                except Exception:
                    fuzzy = None
                if fuzzy:
                    extra["$or"] = [
                        {"item_name": {"$regex": fuzzy, "$options": "i"}},
                        {"part_number": {"$regex": fuzzy, "$options": "i"}},
                        {"aliases": {"$regex": fuzzy, "$options": "i"}},
                    ]

            data = await db.inventory_items.find(extra, {"_id": 0}).to_list(10000)
            report_title = "Inventory Report"
        elif report_type == "sales":
            # iter-121: FY isn't stored on sales_vouchers as a scalar field —
            # it's derived from voucher_date via filter_vouchers_by_fy.
            # Previous code did `extra["fy"] = fy_filter` which never matched
            # → always "No data available". Load, then post-filter.
            fy_filter = (filters.get("fy") or body.get("fy") or "").strip()
            data = await db.sales_vouchers.find(q, {"_id": 0}).to_list(100000)
            if fy_filter:
                try:
                    from utils import filter_vouchers_by_fy
                    data = filter_vouchers_by_fy(data, fy_filter)
                except Exception as fe:
                    logger.warning(f"filter_vouchers_by_fy failed for {fy_filter}: {fe}")
            report_title = "Sales Report"
        else:
            return APIResponse(success=False, error="Invalid report type")

        if not data:
            return APIResponse(success=False, error="No data available to export")

        # iter-122: project raw DB documents into human-readable columns
        # matching what the useradmin sees on the Sales / Inventory tabs.
        # Previous exports dumped tenant_id / company_id / raw items list /
        # ledger_entries as-is, producing an unusable file for customers.
        clean_data = _project_export_rows(report_type, data)

        # iter-121: resolve the tenant's synced company name so every
        # PDF/Excel/CSV export shows the useradmin's actual business name
        # instead of "Anonymous" / hardcoded "FLOWRA Report".
        company_name = ""
        try:
            tenant_id = ctx.get("tenant_id") if ctx else ""
            company_id = body.get("company_id") or (ctx.get("company_id") if ctx else "")
            if tenant_id and company_id:
                from services.id_mapping_service import get_company_name
                company_name = (await get_company_name(tenant_id, company_id) or "").strip()
            if not company_name and tenant_id:
                # Fallback: pick the most recently synced company for this tenant.
                sync_doc = await db.sync_status.find_one(
                    {"tenant_id": tenant_id, "type": "agent_sync"},
                    {"_id": 0, "company_name": 1},
                    sort=[("last_sync", -1)],
                )
                if sync_doc:
                    company_name = (sync_doc.get("company_name") or "").strip()
        except Exception as ce:
            logger.warning(f"Could not resolve company_name for export: {ce}")

        export_service = ExportService()

        if export_format == "csv":
            output = export_service.export_to_csv(clean_data, company_name=company_name)
            media_type = "text/csv"
            filename = f"{report_type}_report.csv"
        elif export_format == "excel":
            output = export_service.export_to_excel(clean_data, report_type.title(),
                                                    company_name=company_name)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{report_type}_report.xlsx"
        elif export_format == "pdf":
            output = export_service.export_to_pdf(clean_data, report_type.title(),
                                                   report_title, company_name=company_name)
            media_type = "application/pdf"
            filename = f"{report_type}_report.pdf"
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


@router.get("/reports/history")
async def get_report_history(request: Request):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx)
        queries = await db.ai_queries.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
        return APIResponse(success=True, data={"queries": queries, "count": len(queries)})
    except Exception as e:
        logger.error(f"Error fetching report history: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/analytics/sales-frequency/export")
async def export_sales_frequency(request: dict):
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
