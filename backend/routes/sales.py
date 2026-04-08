from fastapi import APIRouter
from typing import Optional
import logging

from db import db
from models import SalesVoucher, APIResponse
from utils import safe_num, filter_vouchers_by_fy
from services.tally_client import TallyClient

logger = logging.getLogger(__name__)
router = APIRouter()

tally_client_instance = None


@router.get("/sales/vouchers")
async def get_sales_vouchers(start_date: Optional[str] = None, end_date: Optional[str] = None, party_name: Optional[str] = None, fy: Optional[str] = None, month: Optional[str] = None):
    try:
        query = {}
        if party_name:
            query["party_name"] = {"$regex": party_name, "$options": "i"}

        vouchers = await db.sales_vouchers.find(query, {"_id": 0}).to_list(10000)

        if fy:
            vouchers = filter_vouchers_by_fy(vouchers, fy)

        if month:
            if len(month) <= 2:
                vouchers = [v for v in vouchers if v.get("voucher_date", "")[5:7] == month.zfill(2)]
            else:
                vouchers = [v for v in vouchers if v.get("voucher_date", "").startswith(month)]

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

        all_vouchers_for_meta = await db.sales_vouchers.find({}, {"_id": 0, "party_name": 1, "voucher_date": 1}).to_list(10000)
        if fy:
            all_vouchers_for_meta = filter_vouchers_by_fy(all_vouchers_for_meta, fy)

        unique_parties = sorted(list(set(v.get("party_name", "") for v in all_vouchers_for_meta if v.get("party_name"))))
        unique_months = sorted(list(set(v.get("voucher_date", "")[:7] for v in all_vouchers_for_meta if v.get("voucher_date", "")[:7])))

        if not vouchers and not party_name and not fy and not month:
            global tally_client_instance
            if not tally_client_instance:
                tally_client_instance = TallyClient(connection_type="xml")

            vouchers = tally_client_instance.fetch_sales_vouchers(start_date, end_date)

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
            data={
                "vouchers": vouchers,
                "count": len(vouchers),
                "unique_parties": unique_parties,
                "unique_months": unique_months
            }
        )
    except Exception as e:
        logger.error(f"Error fetching sales vouchers: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/sales/vouchers/{voucher_id:path}")
async def get_voucher_detail(voucher_id: str):
    try:
        from urllib.parse import unquote
        decoded_id = unquote(voucher_id)

        voucher = await db.sales_vouchers.find_one({"voucher_id": decoded_id}, {"_id": 0})
        if not voucher:
            voucher = await db.sales_vouchers.find_one(
                {"voucher_id": {"$regex": f"^{decoded_id}$", "$options": "i"}},
                {"_id": 0}
            )
        if not voucher:
            return APIResponse(success=False, error="Voucher not found")

        items = voucher.get("items", [])
        subtotal = sum(safe_num(item.get("amount"), safe_num(item.get("quantity")) * safe_num(item.get("rate"))) for item in items)
        total = safe_num(voucher.get("total_amount"), subtotal)

        discount_amount = 0
        gst_details = []
        dispatch_details = {}

        ledger_entries = voucher.get("ledger_entries", [])
        for entry in ledger_entries:
            if isinstance(entry, dict):
                ledger_name = str(entry.get("ledger_name", "")).lower()
                amount = entry.get("amount", 0)
                if "discount" in ledger_name:
                    discount_amount += abs(safe_num(amount))
                elif "gst" in ledger_name or "cgst" in ledger_name or "sgst" in ledger_name or "igst" in ledger_name or "tax" in ledger_name:
                    gst_details.append({
                        "tax_name": entry.get("ledger_name", ""),
                        "amount": abs(safe_num(amount))
                    })

        dispatch_details = {
            "delivery_note": voucher.get("delivery_note", voucher.get("reference_number", "")),
            "dispatch_through": voucher.get("dispatch_through", ""),
            "destination": voucher.get("destination", ""),
            "carrier_name": voucher.get("carrier_name", ""),
            "bill_of_lading": voucher.get("bill_of_lading", ""),
            "dispatch_date": voucher.get("dispatch_date", voucher.get("voucher_date", ""))
        }

        gst_total = sum(g.get("amount", 0) for g in gst_details)

        voucher["subtotal"] = round(subtotal, 2)
        voucher["discount_amount"] = round(discount_amount, 2)
        voucher["gst_details"] = gst_details
        voucher["gst_total"] = round(gst_total, 2)
        voucher["dispatch_details"] = dispatch_details
        voucher["computed_total"] = round(total, 2)
        voucher["item_count"] = len(items)

        return APIResponse(success=True, data=voucher)
    except Exception as e:
        logger.error(f"Error fetching voucher detail: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/sales/summary")
async def get_sales_summary(fy: Optional[str] = None):
    try:
        vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        vouchers = filter_vouchers_by_fy(vouchers, fy)

        if not vouchers:
            return APIResponse(
                success=True,
                data={"total_vouchers": 0, "total_sales": 0, "top_customers": [], "recent_vouchers": []}
            )

        total_vouchers = len(vouchers)
        total_sales = sum(safe_num(v.get("total_amount")) for v in vouchers)

        customer_sales = {}
        for v in vouchers:
            party = v.get("party_name", "Unknown")
            customer_sales[party] = customer_sales.get(party, 0) + safe_num(v.get("total_amount"))

        top_customers = sorted(
            [{"name": k, "total": round(v, 2)} for k, v in customer_sales.items()],
            key=lambda x: x["total"],
            reverse=True
        )[:10]

        recent_vouchers = sorted(
            vouchers,
            key=lambda x: x.get("voucher_date", ""),
            reverse=True
        )[:10]

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


@router.get("/sales/analytics")
async def get_sales_analytics(fy: Optional[str] = None, party_name: Optional[str] = None, month: Optional[str] = None):
    try:
        query = {}
        if party_name:
            query["party_name"] = {"$regex": party_name, "$options": "i"}

        vouchers = await db.sales_vouchers.find(query, {"_id": 0}).to_list(10000)
        vouchers = filter_vouchers_by_fy(vouchers, fy)

        if month:
            if len(month) <= 2:
                vouchers = [v for v in vouchers if v.get("voucher_date", "")[5:7] == month.zfill(2)]
            else:
                vouchers = [v for v in vouchers if v.get("voucher_date", "").startswith(month)]

        if not vouchers:
            return APIResponse(success=True, data={"daily_sales": [], "category_sales": []})

        daily_sales = {}
        for v in vouchers:
            date = v.get("voucher_date", "Unknown")
            daily_sales[date] = daily_sales.get(date, 0) + safe_num(v.get("total_amount"))

        daily_sales_data = sorted(
            [{"date": k, "amount": v} for k, v in daily_sales.items()],
            key=lambda x: x["date"]
        )

        return APIResponse(success=True, data={"daily_sales": daily_sales_data})
    except Exception as e:
        logger.error(f"Error getting sales analytics: {e}")
        return APIResponse(success=False, error=str(e))
