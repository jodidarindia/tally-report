from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import logging

from db import db
from models import (
    CustomerFollowup, CustomerFollowupCreate, APIResponse
)
from utils import safe_num, safe_str, filter_vouchers_by_fy, fy_to_date_range, get_previous_fy
from services.auth_service import get_current_user
from services.export_service import ExportService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/customers/outstanding")
async def get_customer_outstanding(customer: Optional[str] = None, fy: Optional[str] = None):
    """Get outstanding payments by customer with proper aging, opening balance, credit notes, and journals."""
    try:
        from datetime import date as date_type
        today = date_type.today()

        synced_customers = await db.customers.find({}, {"_id": 0}).to_list(5000)
        # Filter out Branch/Divisions
        synced_customers = [c for c in synced_customers if 'branch' not in (c.get('ledger_group', '') or '').lower() and 'division' not in (c.get('ledger_group', '') or '').lower()]
        synced_map = {safe_str(c.get("customer_name")).lower(): c for c in synced_customers if c.get("customer_name")}

        # Fetch ALL vouchers (not FY filtered) for opening balance calculation
        all_sales = await db.sales_vouchers.find({}, {"_id": 0}).to_list(20000)
        all_receipts = await db.receipt_vouchers.find({}, {"_id": 0}).to_list(20000)
        all_credit_notes = await db.credit_notes.find({}, {"_id": 0}).to_list(20000)
        all_journals = await db.journal_vouchers.find({}, {"_id": 0}).to_list(20000)

        # Compute FY boundaries
        fy_start_str = None
        if fy:
            try:
                parts = fy.split('-')
                start_year = int(parts[0])
                fy_start_str = f"{start_year}-04-01"
            except:
                pass

        # Split vouchers into pre-FY (opening) and current FY
        def split_by_fy(vouchers, date_field='voucher_date'):
            pre_fy = []
            current_fy = []
            for v in vouchers:
                d = v.get(date_field, '')
                if fy_start_str and d < fy_start_str:
                    pre_fy.append(v)
                else:
                    current_fy.append(v)
            return pre_fy, current_fy

        pre_sales, fy_sales = split_by_fy(all_sales)
        pre_receipts, fy_receipts = split_by_fy(all_receipts)
        pre_cns, fy_cns = split_by_fy(all_credit_notes)
        pre_jvs, fy_jvs = split_by_fy(all_journals)

        # FY-filter the current period
        if fy:
            fy_sales = filter_vouchers_by_fy(fy_sales, fy)
            fy_receipts = filter_vouchers_by_fy([{**r, 'voucher_date': r.get('voucher_date','')} for r in fy_receipts], fy)
            fy_cns = filter_vouchers_by_fy(fy_cns, fy)
            fy_jvs = filter_vouchers_by_fy(fy_jvs, fy)

        # Compute opening balance per customer (pre-FY: sales - receipts - credit notes - journal credits)
        opening_balance = {}
        if fy_start_str:
            for v in pre_sales:
                p = v.get('party_name', '')
                if p:
                    opening_balance[p] = opening_balance.get(p, 0) + safe_num(v.get('total_amount'))
            for r in pre_receipts:
                p = r.get('party_name', '')
                if p:
                    opening_balance[p] = opening_balance.get(p, 0) - safe_num(r.get('amount'))
            for cn in pre_cns:
                p = cn.get('party_name', '')
                if p:
                    opening_balance[p] = opening_balance.get(p, 0) - safe_num(cn.get('total_amount'))
            for jv in pre_jvs:
                p = jv.get('party_name', '')
                if p:
                    opening_balance[p] = opening_balance.get(p, 0) + safe_num(jv.get('debit_amount')) - safe_num(jv.get('credit_amount'))

        # Compute current FY credits per customer
        customer_receipts = {}
        customer_cn_total = {}
        customer_jv_credit = {}
        for r in fy_receipts:
            p = safe_str(r.get("party_name")).strip()
            if p:
                customer_receipts[p] = customer_receipts.get(p, 0) + safe_num(r.get("amount"))
        for cn in fy_cns:
            p = safe_str(cn.get("party_name")).strip()
            if p:
                customer_cn_total[p] = customer_cn_total.get(p, 0) + safe_num(cn.get("total_amount"))
        for jv in fy_jvs:
            p = safe_str(jv.get("party_name")).strip()
            if p:
                customer_jv_credit[p] = customer_jv_credit.get(p, 0) + safe_num(jv.get("credit_amount"))

        customer_map = {}
        customer_vouchers = {}

        for voucher in fy_sales:
            party = voucher.get("party_name", "Unknown")
            amount = safe_num(voucher.get("total_amount"))
            v_date_str = voucher.get("voucher_date", "")

            if party not in customer_map:
                synced = synced_map.get(party.lower(), {})
                ob = round(opening_balance.get(party, 0), 2)
                customer_map[party] = {
                    "customer_name": party,
                    "ledger_group": synced.get("ledger_group", "Sundry Debtors"),
                    "phone": synced.get("phone", ""),
                    "contact_person": synced.get("contact_person", ""),
                    "state": synced.get("state", ""),
                    "opening_balance": ob,
                    "outstanding_amount": 0,
                    "total_sales": 0,
                    "voucher_count": 0,
                    "last_transaction": v_date_str,
                    "aging_0_30": 0.0, "aging_30_60": 0.0,
                    "aging_60_90": 0.0, "aging_90_plus": 0.0,
                    "oldest_invoice_days": 0
                }
                customer_vouchers[party] = []

            customer_map[party]["total_sales"] += amount
            customer_map[party]["voucher_count"] += 1
            if v_date_str and v_date_str > (customer_map[party].get("last_transaction") or ""):
                customer_map[party]["last_transaction"] = v_date_str

            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    customer_vouchers.setdefault(party, []).append({"amount": amount, "days_old": days_old})
                    if days_old > customer_map[party]["oldest_invoice_days"]:
                        customer_map[party]["oldest_invoice_days"] = days_old
            except (ValueError, TypeError):
                customer_vouchers.setdefault(party, []).append({"amount": amount, "days_old": 0})

        # Add synced customers not in FY sales
        for sc in synced_customers:
            name = sc.get("customer_name")
            if not name or name in customer_map:
                continue
            ob = round(opening_balance.get(name, 0), 2)
            customer_map[name] = {
                "customer_name": name,
                "ledger_group": sc.get("ledger_group", "Sundry Debtors"),
                "phone": sc.get("phone", ""),
                "contact_person": sc.get("contact_person", ""),
                "state": sc.get("state", ""),
                "opening_balance": ob,
                "outstanding_amount": safe_num(sc.get("outstanding_amount")),
                "total_sales": 0,
                "voucher_count": 0,
                "last_transaction": None,
                "aging_0_30": 0.0, "aging_30_60": 0.0,
                "aging_60_90": 0.0, "aging_90_plus": 0.0,
                "oldest_invoice_days": 0
            }

        customers = list(customer_map.values())

        if customer:
            customers = [c for c in customers if customer.lower() in safe_str(c.get("customer_name")).lower()]

        # Calculate outstanding, paid, aging for each customer
        for cust in customers:
            party = cust["customer_name"]
            ob = cust.get("opening_balance", 0)
            total_sales = cust["total_sales"]
            receipt_paid = customer_receipts.get(party, 0)
            cn_credit = customer_cn_total.get(party, 0)
            jv_credit = customer_jv_credit.get(party, 0)
            total_credits = receipt_paid + cn_credit + jv_credit

            # Outstanding = Opening + Sales - Receipts - Credit Notes - Journal Credits
            outstanding = ob + total_sales - total_credits
            cust["outstanding_amount"] = round(max(0, outstanding), 2)
            cust["paid_amount"] = round(total_credits, 2)
            cust["receipt_count"] = len([r for r in fy_receipts if r.get("party_name") == party])
            cust["credit_note_total"] = round(cn_credit, 2)
            cust["journal_credit"] = round(jv_credit, 2)

            # FIFO aging on outstanding
            voucher_list = customer_vouchers.get(party, [])
            if cust["outstanding_amount"] > 0 and voucher_list:
                voucher_list.sort(key=lambda x: x["days_old"], reverse=True)
                remaining = cust["outstanding_amount"]
                for v in voucher_list:
                    if remaining <= 0:
                        break
                    alloc = min(v["amount"], remaining)
                    days = v["days_old"]
                    if days > 90:
                        cust["aging_90_plus"] += alloc
                    elif days > 60:
                        cust["aging_60_90"] += alloc
                    elif days > 30:
                        cust["aging_30_60"] += alloc
                    else:
                        cust["aging_0_30"] += alloc
                    remaining -= alloc
                if remaining > 0:
                    cust["aging_0_30"] += remaining

            cust["overdue_amount"] = round(cust["aging_60_90"] + cust["aging_90_plus"], 2)

            oldest = cust["oldest_invoice_days"]
            if cust["outstanding_amount"] <= 0:
                cust["status"] = "normal"
                cust["status_label"] = "Normal"
            elif oldest > 90:
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

        all_groups = list(set(c.get("ledger_group", "") for c in customers if c.get("ledger_group")))
        all_states = list(set(c.get("state", "") for c in customers if c.get("state")))

        return APIResponse(
            success=True,
            data={
                "customers": customers,
                "total_outstanding": round(sum(c["outstanding_amount"] for c in customers), 2),
                "total_paid": round(sum(c.get("paid_amount", 0) for c in customers), 2),
                "groups": sorted(all_groups),
                "states": sorted(all_states)
            }
        )

    except Exception as e:
        logger.error(f"Error fetching customer outstanding: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/customers/followups")
async def get_followups(status: Optional[str] = None):
    try:
        query = {}
        if status:
            query["status"] = status
        followups = await db.customer_followups.find(query, {"_id": 0}).sort("followup_date", -1).to_list(100)
        return APIResponse(success=True, data={"followups": followups, "count": len(followups)})
    except Exception as e:
        logger.error(f"Error fetching followups: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/followups")
async def create_followup(followup: CustomerFollowupCreate, request: Request):
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


@router.patch("/customers/followups/{followup_id}")
async def update_followup_status(followup_id: str, status: str):
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


@router.get("/customers/targets")
async def get_customer_targets(fy: Optional[str] = None):
    try:
        all_vouchers = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        custom_targets = await db.customer_targets.find({}, {"_id": 0}).to_list(100)
        custom_target_map = {t["customer_name"]: t for t in custom_targets}

        current_fy_vouchers = filter_vouchers_by_fy(all_vouchers, fy) if fy else all_vouchers

        prev_fy = get_previous_fy(fy) if fy else None
        prev_fy_vouchers = filter_vouchers_by_fy(all_vouchers, prev_fy) if prev_fy else []

        current_sales = {}
        current_monthly = {}
        for v in current_fy_vouchers:
            party = v.get("party_name", "Unknown")
            amount = safe_num(v.get("total_amount"))
            v_date = v.get("voucher_date", "")
            current_sales[party] = current_sales.get(party, 0) + amount
            if v_date:
                month_key = v_date[:7]
                if party not in current_monthly:
                    current_monthly[party] = {}
                current_monthly[party][month_key] = current_monthly[party].get(month_key, 0) + amount

        prev_sales = {}
        for v in prev_fy_vouchers:
            party = v.get("party_name", "Unknown")
            amount = safe_num(v.get("total_amount"))
            prev_sales[party] = prev_sales.get(party, 0) + amount

        all_customers = set(list(current_sales.keys()) + list(prev_sales.keys()))
        targets = []
        for cust in all_customers:
            ct = custom_target_map.get(cust, {})
            last_fy = prev_sales.get(cust, 0)
            achieved = current_sales.get(cust, 0)

            if cust in custom_target_map:
                target_amount = ct.get("target_amount", last_fy * 1.15)
                last_fy_override = ct.get("last_fy_sales", last_fy)
                if last_fy_override > 0:
                    last_fy = last_fy_override
            else:
                target_amount = last_fy * 1.15 if last_fy > 0 else achieved * 1.2 if achieved > 0 else 0

            monthly = current_monthly.get(cust, {})
            monthly_data = [{"month": k, "amount": v} for k, v in sorted(monthly.items())]

            targets.append({
                "customer_name": cust,
                "target_amount": round(target_amount, 2),
                "last_fy_sales": round(last_fy, 2),
                "achieved_amount": round(achieved, 2),
                "achievement_percentage": round((achieved / target_amount * 100), 1) if target_amount > 0 else 0,
                "remaining": round(max(0, target_amount - achieved), 2),
                "monthly_sales": monthly_data,
                "has_custom_target": cust in custom_target_map,
                "previous_fy": prev_fy or "",
                "current_fy": fy or ""
            })

        targets.sort(key=lambda x: x["achievement_percentage"], reverse=True)

        return APIResponse(
            success=True,
            data={"targets": targets, "current_fy": fy, "previous_fy": prev_fy}
        )

    except Exception as e:
        logger.error(f"Error fetching customer targets: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/targets/set")
async def set_customer_target(request: dict):
    try:
        from datetime import date as date_type
        customer_name = request.get("customer_name", "").strip()
        target_amount = request.get("target_amount", 0)
        last_fy_sales = request.get("last_fy_sales", 0)
        target_fy = request.get("fy", "")

        if not customer_name:
            return APIResponse(success=False, error="Customer name is required")

        if target_fy:
            fy_start, fy_end = fy_to_date_range(target_fy)
            if fy_end:
                end_parts = fy_end.split('-')
                fy_end_date = date_type(int(end_parts[0]), int(end_parts[1]), int(end_parts[2]))
                if date_type.today() > fy_end_date:
                    return APIResponse(success=False, error=f"FY {target_fy} has ended. Targets cannot be modified for completed financial years.")

        doc = {
            "customer_name": customer_name,
            "target_amount": float(target_amount),
            "last_fy_sales": float(last_fy_sales),
            "fy": target_fy,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        await db.customer_targets.update_one(
            {"customer_name": customer_name, "fy": target_fy},
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


@router.post("/customers/ledger/export")
async def export_customer_ledger(request: dict):
    """Export complete customer ledger in Tally-style PDF format.
    Includes: Sales, Receipts, Credit Notes, and Journal entries."""
    try:
        customer_name = request.get("customer_name", "")
        fy = request.get("fy", "")

        if not customer_name:
            return APIResponse(success=False, error="Customer name is required")

        # Fetch all voucher types for this customer
        sales = await db.sales_vouchers.find(
            {"party_name": customer_name}, {"_id": 0}
        ).to_list(10000)
        receipts = await db.receipt_vouchers.find(
            {"party_name": customer_name}, {"_id": 0}
        ).to_list(10000)
        credit_notes = await db.credit_notes.find(
            {"party_name": customer_name}, {"_id": 0}
        ).to_list(10000)
        journals = await db.journal_vouchers.find(
            {"party_name": customer_name}, {"_id": 0}
        ).to_list(10000)

        # FY filter if provided
        if fy:
            sales = filter_vouchers_by_fy(sales, fy)
            receipts = filter_vouchers_by_fy(
                [{"voucher_date": r.get("voucher_date", ""), **r} for r in receipts], fy
            )
            credit_notes = filter_vouchers_by_fy(credit_notes, fy)
            journals = filter_vouchers_by_fy(journals, fy)

        # Build unified ledger entries (Tally format: Date | Particulars | Vch Type | Vch No. | Debit | Credit)
        entries = []
        for v in sales:
            entries.append({
                'date': v.get('voucher_date', ''),
                'particulars': f"Sales - {v.get('reference_number', v.get('voucher_id', ''))}",
                'vch_type': 'Sales',
                'vch_no': v.get('reference_number', v.get('voucher_id', '')),
                'debit': safe_num(v.get('total_amount')),
                'credit': 0.0,
                'narration': v.get('narration', '')
            })
        for r in receipts:
            entries.append({
                'date': r.get('voucher_date', ''),
                'particulars': f"Receipt - {r.get('voucher_id', '')}",
                'vch_type': r.get('voucher_type', 'Receipt').capitalize(),
                'vch_no': r.get('voucher_id', ''),
                'debit': 0.0,
                'credit': safe_num(r.get('amount')),
                'narration': r.get('narration', '')
            })
        for cn in credit_notes:
            entries.append({
                'date': cn.get('voucher_date', ''),
                'particulars': f"Credit Note - {cn.get('reference_number', cn.get('voucher_id', ''))}",
                'vch_type': 'Credit Note',
                'vch_no': cn.get('reference_number', cn.get('voucher_id', '')),
                'debit': 0.0,
                'credit': safe_num(cn.get('total_amount')),
                'narration': cn.get('narration', '')
            })
        for jv in journals:
            entries.append({
                'date': jv.get('voucher_date', ''),
                'particulars': f"Journal - {jv.get('voucher_id', '')}",
                'vch_type': 'Journal',
                'vch_no': jv.get('voucher_id', ''),
                'debit': safe_num(jv.get('debit_amount')),
                'credit': safe_num(jv.get('credit_amount')),
                'narration': jv.get('narration', '')
            })

        if not entries and not fy:
            return APIResponse(success=False, error=f"No transactions found for {customer_name}")

        # Compute opening balance for this customer if FY is specified
        opening_balance = 0.0
        if fy:
            try:
                fy_parts = fy.split('-')
                start_year = int(fy_parts[0])
                fy_start = f"{start_year}-04-01"

                all_sales_pre = await db.sales_vouchers.find(
                    {"party_name": customer_name, "voucher_date": {"$lt": fy_start}}, {"_id": 0, "total_amount": 1}
                ).to_list(10000)
                all_receipts_pre = await db.receipt_vouchers.find(
                    {"party_name": customer_name, "voucher_date": {"$lt": fy_start}}, {"_id": 0, "amount": 1}
                ).to_list(10000)
                all_cn_pre = await db.credit_notes.find(
                    {"party_name": customer_name, "voucher_date": {"$lt": fy_start}}, {"_id": 0, "total_amount": 1}
                ).to_list(10000)
                all_jv_pre = await db.journal_vouchers.find(
                    {"party_name": customer_name, "voucher_date": {"$lt": fy_start}}, {"_id": 0, "debit_amount": 1, "credit_amount": 1}
                ).to_list(10000)

                opening_balance += sum(safe_num(v.get('total_amount')) for v in all_sales_pre)
                opening_balance -= sum(safe_num(r.get('amount')) for r in all_receipts_pre)
                opening_balance -= sum(safe_num(cn.get('total_amount')) for cn in all_cn_pre)
                for jv in all_jv_pre:
                    opening_balance += safe_num(jv.get('debit_amount')) - safe_num(jv.get('credit_amount'))
            except Exception:
                pass

        # Sort by date
        entries.sort(key=lambda e: e['date'])

        # Get customer info
        cust_info = await db.customers.find_one({"customer_name": customer_name}, {"_id": 0})
        company_info = await db.sync_status.find_one({"type": "agent_sync"}, {"_id": 0})
        company_name_str = company_info.get('company_name', 'FLOWRA') if company_info else 'FLOWRA'

        from services.ledger_pdf_service import generate_tally_ledger_pdf
        output = generate_tally_ledger_pdf(
            customer_name=customer_name,
            company_name=company_name_str,
            entries=entries,
            fy=fy,
            customer_info=cust_info or {}
        )

        filename = f"ledger_{customer_name.replace(' ', '_')}_{fy or 'all'}.pdf"
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting customer ledger: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/customers/payment-behavior")
async def get_payment_behavior(customer: Optional[str] = None, fy: Optional[str] = None):
    try:
        from datetime import date as date_type
        today = date_type.today()

        all_sales = await db.sales_vouchers.find({}, {"_id": 0}).to_list(10000)
        sales_vouchers = filter_vouchers_by_fy(all_sales, fy)

        synced_customers = await db.customers.find({}, {"_id": 0}).to_list(5000)
        synced_map = {safe_str(c.get("customer_name")).lower(): c for c in synced_customers if c.get("customer_name")}

        all_receipts = await db.receipt_vouchers.find({}, {"_id": 0}).to_list(10000)
        receipt_vouchers = filter_vouchers_by_fy(
            [{"voucher_date": r.get("voucher_date", ""), **r} for r in all_receipts], fy
        )
        customer_payments = {}
        customer_receipt_dates = {}
        for r in receipt_vouchers:
            party = safe_str(r.get("party_name")).strip()
            if not party or party == "Unknown":
                continue
            customer_payments[party] = customer_payments.get(party, 0) + safe_num(r.get("amount"))
            if party not in customer_receipt_dates:
                customer_receipt_dates[party] = []
            customer_receipt_dates[party].append(r.get("voucher_date", ""))

        behavior_map = {}
        for voucher in sales_vouchers:
            party = voucher.get("party_name", "Unknown")
            amount = safe_num(voucher.get("total_amount"))
            v_date_str = voucher.get("voucher_date", "")

            if party not in behavior_map:
                synced = synced_map.get(party.lower(), {})
                behavior_map[party] = {
                    "customer_name": party,
                    "total_transactions": 0,
                    "total_amount": 0,
                    "average_transaction": 0,
                    "outstanding_amount": safe_num(synced.get("outstanding_amount")),
                    "paid_amount": 0,
                    "payment_ratio": 0,
                    "payment_pattern": "regular",
                    "average_payment_delay": 0,
                    "credit_score": 0,
                    "oldest_invoice_days": 0,
                    "invoices": []
                }

            behavior_map[party]["total_transactions"] += 1
            behavior_map[party]["total_amount"] += amount

            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    behavior_map[party]["invoices"].append({"amount": amount, "days_old": days_old})
                    if days_old > behavior_map[party]["oldest_invoice_days"]:
                        behavior_map[party]["oldest_invoice_days"] = days_old
            except (ValueError, TypeError):
                pass

        for sc in synced_customers:
            name = sc.get("customer_name")
            if not name:
                continue
            if name not in behavior_map and safe_num(sc.get("outstanding_amount")) > 0:
                behavior_map[name] = {
                    "customer_name": name,
                    "total_transactions": 0,
                    "total_amount": 0,
                    "average_transaction": 0,
                    "outstanding_amount": safe_num(sc.get("outstanding_amount")),
                    "paid_amount": customer_payments.get(name, 0),
                    "receipt_count": len(customer_receipt_dates.get(name, [])),
                    "payment_ratio": 0,
                    "payment_pattern": "no_transactions",
                    "average_payment_delay": 0,
                    "credit_score": 0,
                    "oldest_invoice_days": 0,
                    "invoices": []
                }

        for party, data in behavior_map.items():
            total = data["total_amount"]
            outstanding = data["outstanding_amount"]
            receipt_paid = customer_payments.get(party, 0)

            if receipt_paid > 0:
                data["paid_amount"] = receipt_paid
                data["receipt_count"] = len(customer_receipt_dates.get(party, []))
            else:
                data["paid_amount"] = max(0, total - outstanding)
                data["receipt_count"] = 0

            data["average_transaction"] = round(total / data["total_transactions"], 2) if data["total_transactions"] > 0 else 0
            data["payment_ratio"] = round((data["paid_amount"] / total * 100), 1) if total > 0 else 100

            if receipt_paid > 0 and data["invoices"]:
                invoice_dates = sorted([i["days_old"] for i in data["invoices"]])
                if outstanding > 0:
                    data["average_payment_delay"] = round(sum(invoice_dates) / len(invoice_dates) * (outstanding / total), 0) if invoice_dates else 0
                else:
                    data["average_payment_delay"] = 0
            elif total > 0 and outstanding > 0 and data["invoices"]:
                outstanding_ratio = outstanding / total
                avg_invoice_age = sum(i["days_old"] for i in data["invoices"]) / len(data["invoices"])
                data["average_payment_delay"] = round(avg_invoice_age * outstanding_ratio, 0)
            else:
                data["average_payment_delay"] = 0

            payment_score = data["payment_ratio"]
            volume_score = min(20, data["total_transactions"] * 2)
            delay_penalty = min(20, data["average_payment_delay"] / 3)
            data["credit_score"] = round(max(0, min(100, payment_score * 0.7 + volume_score - delay_penalty)), 1)

            if data["payment_ratio"] >= 90 and data["average_payment_delay"] < 15:
                data["payment_pattern"] = "excellent"
            elif data["payment_ratio"] >= 70 and data["average_payment_delay"] < 30:
                data["payment_pattern"] = "regular"
            elif data["payment_ratio"] >= 50:
                data["payment_pattern"] = "irregular"
            else:
                data["payment_pattern"] = "risky"

            del data["invoices"]

        customers = list(behavior_map.values())

        if customer:
            customers = [c for c in customers if customer.lower() in safe_str(c.get("customer_name")).lower()]

        customers.sort(key=lambda c: c["credit_score"], reverse=True)

        return APIResponse(success=True, data={"customers": customers})

    except Exception as e:
        logger.error(f"Error analyzing payment behavior: {e}")
        return APIResponse(success=False, error=str(e))
