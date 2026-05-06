from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import logging

from db import db
from models import (
    CustomerFollowup, CustomerFollowupCreate, APIResponse
)
from utils import safe_num, safe_str, filter_vouchers_by_fy, fy_to_date_range, get_previous_fy, get_jv_party_amount
from services.auth_service import get_current_user
from services.export_service import ExportService
from services.tenant_context import get_tenant_context

from services.audit_service import log_audit, get_client_ip
from routes.branch_ledgers import get_branch_parties

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


@router.get("/customers/outstanding")
async def get_customer_outstanding(request: Request, customer: Optional[str] = None, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Get outstanding payments by customer with proper aging, opening balance, credit notes, and journals."""
    try:
        from datetime import date as date_type
        today = date_type.today()
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        synced_customers = await db.customers.find(q, {"_id": 0}).to_list(5000)

        # Determine branch exclusion from header
        exclude_branches = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        branch_parties = []
        if exclude_branches:
            branch_parties = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))

        # Filter branch customers from synced list
        if branch_parties:
            branch_set = set(p.lower() for p in branch_parties)
            synced_customers = [c for c in synced_customers if safe_str(c.get("customer_name")).lower() not in branch_set]

        # Fetch ALL vouchers (not FY filtered) for opening balance calculation
        all_sales = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
        all_receipts_raw = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)
        all_credit_notes = await db.credit_notes.find(q, {"_id": 0}).to_list(50000)
        all_journals = await db.journal_vouchers.find(q, {"_id": 0}).to_list(50000)

        # The receipt_vouchers collection actually contains BOTH receipts (CR party = reduces OS)
        # and payment vouchers (DR party = increases OS, e.g., cheque-bounce refund). Split by
        # voucher_type so they affect the customer balance with the correct sign.
        def _is_payment(v):
            return (v.get("voucher_type") or "").strip().lower() == "payment"
        all_receipts = [v for v in all_receipts_raw if not _is_payment(v)]
        all_payments = [v for v in all_receipts_raw if _is_payment(v)]

        # Filter branch parties from vouchers
        if branch_parties:
            bp_lower = set(p.lower().strip() for p in branch_parties)
            all_sales = [v for v in all_sales if (v.get("party_name") or "").lower().strip() not in bp_lower]
            all_receipts = [v for v in all_receipts if (v.get("party_name") or "").lower().strip() not in bp_lower]
            all_payments = [v for v in all_payments if (v.get("party_name") or "").lower().strip() not in bp_lower]
            all_credit_notes = [v for v in all_credit_notes if (v.get("party_name") or "").lower().strip() not in bp_lower]
            all_journals = [v for v in all_journals if (v.get("party_name") or "").lower().strip() not in bp_lower]

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

        _, fy_sales = split_by_fy(all_sales)
        _, fy_receipts = split_by_fy(all_receipts)
        _, fy_payments = split_by_fy(all_payments)
        _, fy_cns = split_by_fy(all_credit_notes)
        _, fy_jvs = split_by_fy(all_journals)

        # FY-filter the current period
        if fy:
            fy_sales = filter_vouchers_by_fy(fy_sales, fy)
            fy_receipts = filter_vouchers_by_fy([{**r, 'voucher_date': r.get('voucher_date','')} for r in fy_receipts], fy)
            fy_payments = filter_vouchers_by_fy([{**p, 'voucher_date': p.get('voucher_date','')} for p in fy_payments], fy)
            fy_cns = filter_vouchers_by_fy(fy_cns, fy)
            fy_jvs = filter_vouchers_by_fy(fy_jvs, fy)

        # Compute opening balance per customer
        # Tally's opening_balance = balance as of the START of Tally's selected FY (base FY).
        # For the base FY: use Tally OB directly.
        # For earlier FYs: reverse-compute by subtracting activity between requested and base FY.
        # For later FYs: forward-compute by adding activity between base and requested FY.
        # For non-customer parties (not in customers collection): use pure voucher sum.
        opening_balance = {}
        if fy_start_str:
            # Tally's customer-master "OpeningBalance" attribute always reflects the
            # OB at the start of whatever FY is currently active in Tally. Tally
            # auto-rolls into the new FY on 1-Apr each year, so we anchor the
            # synced opening_balance against TODAY's calendar FY (not against the
            # potentially-stale sync_status.financial_year label).
            today_fy_year = today.year if today.month >= 4 else today.year - 1
            base_fy_start = f"{today_fy_year}-04-01"

            synced_names = set()
            synced_lower_to_canonical = {}
            for sc in synced_customers:
                name = sc.get("customer_name")
                if name:
                    synced_names.add(name)
                    synced_lower_to_canonical[name.lower().strip()] = name
                    opening_balance[name] = safe_num(sc.get("opening_balance", 0))

            def _resolve(p):
                """Map any voucher party_name spelling to the canonical synced name."""
                return synced_lower_to_canonical.get((p or "").lower().strip())

            # Adjust Tally OB for customers if viewing a different FY
            if fy_start_str != base_fy_start:
                if fy_start_str < base_fy_start:
                    # Backward: undo activity between req_fy_start and base_fy_start
                    lo, hi = fy_start_str, base_fy_start
                    for v in all_sales:
                        p = _resolve(v.get('party_name'))
                        if p and lo <= v.get('voucher_date', '') < hi:
                            opening_balance[p] -= safe_num(v.get('total_amount'))
                    for r in all_receipts:
                        p = _resolve(r.get('party_name'))
                        if p and lo <= r.get('voucher_date', '') < hi:
                            opening_balance[p] += safe_num(r.get('amount'))
                    for pmt in all_payments:
                        p = _resolve(pmt.get('party_name'))
                        if p and lo <= pmt.get('voucher_date', '') < hi:
                            # Payment voucher DRs the customer (e.g., cheque-bounce refund)
                            # → undoing means subtract DR
                            opening_balance[p] -= safe_num(pmt.get('amount'))
                    for cn in all_credit_notes:
                        p = _resolve(cn.get('party_name'))
                        if p and lo <= cn.get('voucher_date', '') < hi:
                            opening_balance[p] += safe_num(cn.get('total_amount'))
                    for jv in all_journals:
                        p = _resolve(jv.get('party_name'))
                        if p and lo <= jv.get('voucher_date', '') < hi:
                            debit, credit = get_jv_party_amount(jv)
                            # JV DR on customer increases their balance (we're undoing → subtract DR, add CR)
                            opening_balance[p] += credit - debit
                else:
                    # Forward: add activity between base_fy_start and req_fy_start
                    lo, hi = base_fy_start, fy_start_str
                    for v in all_sales:
                        p = _resolve(v.get('party_name'))
                        if p and lo <= v.get('voucher_date', '') < hi:
                            opening_balance[p] += safe_num(v.get('total_amount'))
                    for r in all_receipts:
                        p = _resolve(r.get('party_name'))
                        if p and lo <= r.get('voucher_date', '') < hi:
                            opening_balance[p] -= safe_num(r.get('amount'))
                    for pmt in all_payments:
                        p = _resolve(pmt.get('party_name'))
                        if p and lo <= pmt.get('voucher_date', '') < hi:
                            opening_balance[p] += safe_num(pmt.get('amount'))
                    for cn in all_credit_notes:
                        p = _resolve(cn.get('party_name'))
                        if p and lo <= cn.get('voucher_date', '') < hi:
                            opening_balance[p] -= safe_num(cn.get('total_amount'))
                    for jv in all_journals:
                        p = _resolve(jv.get('party_name'))
                        if p and lo <= jv.get('voucher_date', '') < hi:
                            debit, credit = get_jv_party_amount(jv)
                            opening_balance[p] += debit - credit

        # Compute current FY credits per customer (case-insensitive party keys)
        customer_receipts = {}
        customer_cn_total = {}
        customer_payments_dr = {}  # Payment vouchers paid TO party → DR (increases OS)
        for r in fy_receipts:
            p = safe_str(r.get("party_name")).strip().lower()
            if p:
                customer_receipts[p] = customer_receipts.get(p, 0) + safe_num(r.get("amount"))
        for pmt in fy_payments:
            p = safe_str(pmt.get("party_name")).strip().lower()
            if p:
                customer_payments_dr[p] = customer_payments_dr.get(p, 0) + safe_num(pmt.get("amount"))
        for cn in fy_cns:
            p = safe_str(cn.get("party_name")).strip().lower()
            if p:
                customer_cn_total[p] = customer_cn_total.get(p, 0) + safe_num(cn.get("total_amount"))
        customer_jv_adjustment = {}
        for jv in fy_jvs:
            p = safe_str(jv.get("party_name")).strip().lower()
            if p:
                # Use party-specific amount from ledger_entries (not total voucher amount)
                debit, credit = get_jv_party_amount(jv)
                net_credit = credit - debit  # Positive = reduces outstanding
                customer_jv_adjustment[p] = customer_jv_adjustment.get(p, 0) + net_credit

        customer_map = {}
        customer_vouchers = {}

        # ── SOURCE OF TRUTH = customers collection (synced from Tally Sundry Debtors group)
        # Build customer_map ONLY from synced_customers. Do NOT auto-add parties
        # from sales_vouchers (those can leak creditors / non-customer ledgers).
        synced_name_lower_to_canonical = {}
        for sc in synced_customers:
            name = sc.get("customer_name")
            if not name:
                continue
            ob = round(opening_balance.get(name, 0), 2)
            customer_map[name] = {
                "customer_name": name,
                "ledger_group": sc.get("ledger_group", ""),
                "phone": sc.get("phone", ""),
                "contact_person": sc.get("contact_person", ""),
                "state": sc.get("state", ""),
                "opening_balance": ob,
                "tally_outstanding": safe_num(sc.get("outstanding_amount")),  # Tally closing balance
                "outstanding_amount": 0,
                "total_sales": 0,
                "voucher_count": 0,
                "last_transaction": None,
                "aging_0_30": 0.0, "aging_30_60": 0.0,
                "aging_60_90": 0.0, "aging_90_plus": 0.0,
                "oldest_invoice_days": 0
            }
            customer_vouchers[name] = []
            synced_name_lower_to_canonical[name.lower().strip()] = name

        # Enrich synced customers with FY sales activity. Skip parties not in synced list.
        for voucher in fy_sales:
            party_raw = (voucher.get("party_name") or "").strip()
            if not party_raw:
                continue
            party = synced_name_lower_to_canonical.get(party_raw.lower())
            if not party:
                continue  # Not a synced customer → ignore (creditors, depots, etc.)
            amount = safe_num(voucher.get("total_amount"))
            v_date_str = voucher.get("voucher_date", "")

            customer_map[party]["total_sales"] += amount
            customer_map[party]["voucher_count"] += 1
            if v_date_str and v_date_str > (customer_map[party].get("last_transaction") or ""):
                customer_map[party]["last_transaction"] = v_date_str

            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    customer_vouchers[party].append({"amount": amount, "days_old": days_old})
                    if days_old > customer_map[party]["oldest_invoice_days"]:
                        customer_map[party]["oldest_invoice_days"] = days_old
            except (ValueError, TypeError):
                customer_vouchers[party].append({"amount": amount, "days_old": 0})

        # Enrich synced customers with FY payment-voucher activity (DR party — e.g.,
        # cheque-bounce refund, expense advance, debit-side adjustment). The Tally Sync
        # Agent stores these inside receipt_vouchers with voucher_type='payment'.
        for pmt in fy_payments:
            party_raw = (pmt.get("party_name") or "").strip()
            if not party_raw:
                continue
            party = synced_name_lower_to_canonical.get(party_raw.lower())
            if not party:
                continue
            amount = safe_num(pmt.get("amount"))
            v_date_str = pmt.get("voucher_date", "")
            customer_map[party]["total_sales"] += amount  # DR side (treated like sales for math)
            customer_map[party]["voucher_count"] += 1
            if v_date_str and v_date_str > (customer_map[party].get("last_transaction") or ""):
                customer_map[party]["last_transaction"] = v_date_str
            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    customer_vouchers[party].append({"amount": amount, "days_old": days_old})
                    if days_old > customer_map[party]["oldest_invoice_days"]:
                        customer_map[party]["oldest_invoice_days"] = days_old
            except (ValueError, TypeError):
                customer_vouchers[party].append({"amount": amount, "days_old": 0})

        customers = list(customer_map.values())

        # Source list is the customers collection (synced from Tally Sundry Debtors group)
        # No additional group filter needed — sync already handled it.

        if customer:
            customers = [c for c in customers if customer.lower() in safe_str(c.get("customer_name")).lower()]

        # Calculate outstanding, paid, aging for each customer
        for cust in customers:
            party = cust["customer_name"]
            party_key = party.lower().strip()
            ob = cust.get("opening_balance", 0)
            total_sales = cust["total_sales"]
            receipt_paid = customer_receipts.get(party_key, 0)
            cn_credit = customer_cn_total.get(party_key, 0)
            jv_adjustment = customer_jv_adjustment.get(party_key, 0)  # Net: positive = reduces outstanding
            total_credits = receipt_paid + cn_credit + jv_adjustment

            # Outstanding = Opening + Sales - Receipts - Credit Notes - Net Journal Adjustments
            outstanding = ob + total_sales - total_credits
            cust["outstanding_amount"] = round(outstanding, 2)  # Allow negative (advance payments)
            cust["paid_amount"] = round(total_credits, 2)
            cust["receipt_count"] = len([r for r in fy_receipts if (r.get("party_name") or "").lower().strip() == party_key])
            cust["credit_note_total"] = round(cn_credit, 2)
            cust["journal_credit"] = round(jv_adjustment, 2)

            # FIFO aging on outstanding
            voucher_list = customer_vouchers.get(party, [])
            if cust["outstanding_amount"] > 0:
                if voucher_list:
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
                else:
                    # No FY invoices but outstanding exists → it's all from opening balance
                    # Use FY-start as reference for aging
                    try:
                        if not fy_start_str:
                            raise ValueError("no fy_start_str")
                        fy_start_date = date_type(*[int(x) for x in fy_start_str.split("-")])
                        days_from_fy_start = (today - fy_start_date).days
                        cust["oldest_invoice_days"] = max(cust.get("oldest_invoice_days", 0), days_from_fy_start)
                        if days_from_fy_start > 90:
                            cust["aging_90_plus"] = cust["outstanding_amount"]
                        elif days_from_fy_start > 60:
                            cust["aging_60_90"] = cust["outstanding_amount"]
                        elif days_from_fy_start > 30:
                            cust["aging_30_60"] = cust["outstanding_amount"]
                        else:
                            cust["aging_0_30"] = cust["outstanding_amount"]
                    except Exception:
                        cust["aging_0_30"] = cust["outstanding_amount"]

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

        customers.sort(key=lambda c: c.get("customer_name", "").lower())

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
async def get_followups(request: Request, status: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        extra = {}
        if status:
            extra["status"] = status
        query = _build_query(ctx, company_id, extra)
        followups = await db.customer_followups.find(query, {"_id": 0}).sort("followup_date", -1).to_list(100)

        # Apply branch exclusion
        exclude_branches = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        if exclude_branches:
            branch_parties = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
            if branch_parties:
                branch_set = set(p.lower() for p in branch_parties)
                followups = [f for f in followups if f.get("customer_name", "").lower() not in branch_set]

        return APIResponse(success=True, data={"followups": followups, "count": len(followups)})
    except Exception as e:
        logger.error(f"Error fetching followups: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/followups")
async def create_followup(followup: CustomerFollowupCreate, request: Request):
    try:
        user = await get_current_user(request, db)
        ctx = await get_tenant_context(request)
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
        if ctx and ctx.get("tenant_id"):
            doc['tenant_id'] = ctx["tenant_id"]
        if ctx and ctx.get("company_id"):
            doc['company_id'] = ctx["company_id"]

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
async def update_followup_status(followup_id: str, status: str, request: Request):
    try:
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)
        result = await db.customer_followups.update_one(
            {**tq, "id": followup_id},
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
async def get_customer_targets(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0}).to_list(10000)
        custom_targets = await db.customer_targets.find(q, {"_id": 0}).to_list(100)
        custom_target_map = {t["customer_name"]: t for t in custom_targets}

        # Get removed customers for this FY
        removed_docs = await db.customer_target_removals.find({**q, "fy": fy} if fy else q, {"_id": 0, "customer_name": 1}).to_list(5000)
        removed_set = {d["customer_name"] for d in removed_docs}

        # Apply branch exclusion
        exclude_branches = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        branch_parties = []
        if exclude_branches:
            branch_parties = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
        if branch_parties:
            all_vouchers = [v for v in all_vouchers if v.get("party_name") not in branch_parties]

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
        # Filter out removed customers + sentinel "Unknown" / blank parties
        all_customers = {
            c for c in all_customers
            if c and c.strip().lower() not in {"unknown", "n/a", "none", ""} and c not in removed_set
        }
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

        targets.sort(key=lambda x: x["customer_name"].lower())

        return APIResponse(
            success=True,
            data={"targets": targets, "current_fy": fy, "previous_fy": prev_fy, "removed_count": len(removed_set)}
        )

    except Exception as e:
        logger.error(f"Error fetching customer targets: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/targets/set")
async def set_customer_target(request: Request):
    try:
        from datetime import date as date_type
        body = await request.json()
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)

        customer_name = body.get("customer_name", "").strip()
        target_amount = body.get("target_amount", 0)
        last_fy_sales = body.get("last_fy_sales", 0)
        target_fy = body.get("fy", "")

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
        if ctx and ctx.get("tenant_id"):
            doc["tenant_id"] = ctx["tenant_id"]
        if ctx and ctx.get("company_id"):
            doc["company_id"] = ctx["company_id"]

        await db.customer_targets.update_one(
            {**tq, "customer_name": customer_name, "fy": target_fy},
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


@router.post("/customers/targets/bulk-percentage")
async def bulk_set_target_percentage(request: Request):
    """Set target as a percentage of previous FY sales for multiple customers at once."""
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)
        fy = body.get("fy", "")
        percentage = float(body.get("percentage", 115))  # default 115%
        customer_names = body.get("customer_names", [])  # empty = all

        if not fy:
            return APIResponse(success=False, error="FY is required")

        # Verify FY is current or future
        from datetime import date as date_type
        fy_start, fy_end = fy_to_date_range(fy)
        if fy_end:
            end_parts = fy_end.split('-')
            fy_end_date = date_type(int(end_parts[0]), int(end_parts[1]), int(end_parts[2]))
            if date_type.today() > fy_end_date:
                return APIResponse(success=False, error=f"FY {fy} has ended. Cannot modify targets.")

        # Get previous FY sales
        prev_fy = get_previous_fy(fy)
        all_vouchers = await db.sales_vouchers.find(tq, {"_id": 0}).to_list(10000)
        exclude_branches = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        if exclude_branches:
            branch_parties = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
            if branch_parties:
                all_vouchers = [v for v in all_vouchers if v.get("party_name") not in branch_parties]

        prev_vouchers = filter_vouchers_by_fy(all_vouchers, prev_fy) if prev_fy else []
        prev_sales = {}
        for v in prev_vouchers:
            party = v.get("party_name", "")
            amt = safe_num(v.get("total_amount"))
            prev_sales[party] = prev_sales.get(party, 0) + amt

        # Check for removed customers
        removed_docs = await db.customer_target_removals.find({**tq, "fy": fy}, {"_id": 0, "customer_name": 1}).to_list(5000)
        removed_set = {d["customer_name"] for d in removed_docs}

        updated = 0
        targets_to_process = customer_names if customer_names else list(prev_sales.keys())
        for cust in targets_to_process:
            if cust in removed_set:
                continue
            last_fy = prev_sales.get(cust, 0)
            if last_fy <= 0:
                continue
            target_amount = last_fy * (percentage / 100)
            doc = {
                "customer_name": cust,
                "target_amount": round(target_amount, 2),
                "last_fy_sales": round(last_fy, 2),
                "fy": fy,
                "target_percentage": percentage,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if ctx and ctx.get("tenant_id"):
                doc["tenant_id"] = ctx["tenant_id"]
            if ctx and ctx.get("company_id"):
                doc["company_id"] = ctx["company_id"]
            await db.customer_targets.update_one(
                {**tq, "customer_name": cust, "fy": fy},
                {"$set": doc},
                upsert=True
            )
            updated += 1

        return APIResponse(success=True, data={"updated": updated, "percentage": percentage, "message": f"Updated {updated} customer targets to {percentage}% of previous FY"})
    except Exception as e:
        logger.error(f"Bulk target error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/targets/remove")
async def remove_customers_from_targets(request: Request):
    """Remove selected customers from target reports for current FY. Does not affect Tally data."""
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)
        fy = body.get("fy", "")
        customer_names = body.get("customer_names", [])

        if not fy or not customer_names:
            return APIResponse(success=False, error="FY and customer_names required")

        count = 0
        for cust in customer_names:
            doc = {
                "customer_name": cust,
                "fy": fy,
                "removed_at": datetime.now(timezone.utc).isoformat(),
            }
            if ctx and ctx.get("tenant_id"):
                doc["tenant_id"] = ctx["tenant_id"]
            if ctx and ctx.get("company_id"):
                doc["company_id"] = ctx["company_id"]
            await db.customer_target_removals.update_one(
                {**tq, "customer_name": cust, "fy": fy},
                {"$set": doc},
                upsert=True
            )
            count += 1

        return APIResponse(success=True, data={"removed": count, "message": f"{count} customers removed from targets"})
    except Exception as e:
        logger.error(f"Remove targets error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/targets/reactivate")
async def reactivate_customers_in_targets(request: Request):
    """Reactivate previously removed customers in target reports."""
    try:
        body = await request.json()
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)
        fy = body.get("fy", "")
        customer_names = body.get("customer_names", [])

        if not fy or not customer_names:
            return APIResponse(success=False, error="FY and customer_names required")

        result = await db.customer_target_removals.delete_many(
            {**tq, "fy": fy, "customer_name": {"$in": customer_names}}
        )

        return APIResponse(success=True, data={"reactivated": result.deleted_count})
    except Exception as e:
        logger.error(f"Reactivate targets error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/customers/targets/removed")
async def get_removed_customers(request: Request, fy: Optional[str] = None):
    """Get list of customers removed from targets for a given FY."""
    try:
        ctx = await get_tenant_context(request)
        tq = _build_query(ctx)
        q = {**tq}
        if fy:
            q["fy"] = fy
        docs = await db.customer_target_removals.find(q, {"_id": 0}).to_list(5000)
        return APIResponse(success=True, data={"removed": docs})
    except Exception as e:
        logger.error(f"Get removed customers error: {e}")
        return APIResponse(success=False, error=str(e))



@router.post("/customers/ledger/export")
async def export_customer_ledger(request: Request):
    """Export complete customer ledger in Tally-style PDF format.
    Includes: Sales, Receipts, Credit Notes, and Journal entries."""
    try:
        body = await request.json()
        customer_name = body.get("customer_name", "")
        fy = body.get("fy", "")

        if not customer_name:
            return APIResponse(success=False, error="Customer name is required")

        ctx = await get_tenant_context(request)
        tq = _build_query(ctx, body.get("company_id"))

        # Fetch all voucher types for this customer
        cust_q = {**tq, "party_name": customer_name}
        sales = await db.sales_vouchers.find(cust_q, {"_id": 0}).to_list(10000)
        receipts = await db.receipt_vouchers.find(cust_q, {"_id": 0}).to_list(10000)
        credit_notes = await db.credit_notes.find(cust_q, {"_id": 0}).to_list(10000)
        journals = await db.journal_vouchers.find(cust_q, {"_id": 0}).to_list(10000)

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
            debit, credit = get_jv_party_amount(jv)
            entries.append({
                'date': jv.get('voucher_date', ''),
                'particulars': f"Journal - {jv.get('voucher_id', '')}",
                'vch_type': 'Journal',
                'vch_no': jv.get('voucher_id', ''),
                'debit': debit,
                'credit': credit,
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

                # Get Tally OB and base FY
                cust_doc = await db.customers.find_one({**tq, "customer_name": customer_name}, {"_id": 0, "opening_balance": 1})
                sync_doc = await db.sync_status.find_one({**tq, "type": "agent_sync"}, {"_id": 0, "financial_year": 1})
                base_fy = sync_doc.get("financial_year") if sync_doc else None
                base_fy_start = None
                if base_fy:
                    try:
                        base_fy_start = f"{int(base_fy.split('-')[0])}-04-01"
                    except Exception:
                        pass

                if cust_doc and base_fy_start:
                    opening_balance = safe_num(cust_doc.get("opening_balance", 0))
                    if fy_start != base_fy_start:
                        lo = min(fy_start, base_fy_start)
                        hi = max(fy_start, base_fy_start)
                        adj_sales = await db.sales_vouchers.find(
                            {**tq, "party_name": customer_name, "voucher_date": {"$gte": lo, "$lt": hi}}, {"_id": 0, "total_amount": 1}
                        ).to_list(10000)
                        adj_receipts = await db.receipt_vouchers.find(
                            {**tq, "party_name": customer_name, "voucher_date": {"$gte": lo, "$lt": hi}}, {"_id": 0, "amount": 1}
                        ).to_list(10000)
                        adj_cns = await db.credit_notes.find(
                            {**tq, "party_name": customer_name, "voucher_date": {"$gte": lo, "$lt": hi}}, {"_id": 0, "total_amount": 1}
                        ).to_list(10000)
                        adj_jvs = await db.journal_vouchers.find(
                            {**tq, "party_name": customer_name, "voucher_date": {"$gte": lo, "$lt": hi}},
                            {"_id": 0, "debit_amount": 1, "credit_amount": 1, "party_name": 1, "ledger_entries": 1}
                        ).to_list(10000)
                        if fy_start < base_fy_start:
                            opening_balance -= sum(safe_num(v.get('total_amount')) for v in adj_sales)
                            opening_balance += sum(safe_num(r.get('amount')) for r in adj_receipts)
                            opening_balance += sum(safe_num(cn.get('total_amount')) for cn in adj_cns)
                            for jv in adj_jvs:
                                d, c = get_jv_party_amount(jv)
                                opening_balance += c - d
                        else:
                            opening_balance += sum(safe_num(v.get('total_amount')) for v in adj_sales)
                            opening_balance -= sum(safe_num(r.get('amount')) for r in adj_receipts)
                            opening_balance -= sum(safe_num(cn.get('total_amount')) for cn in adj_cns)
                            for jv in adj_jvs:
                                d, c = get_jv_party_amount(jv)
                                opening_balance += d - c
            except Exception:
                pass

        # Sort by date
        entries.sort(key=lambda e: e['date'])

        # Get customer info
        cust_info = await db.customers.find_one({**tq, "customer_name": customer_name}, {"_id": 0})
        company_info = await db.sync_status.find_one({**tq, "type": "agent_sync"}, {"_id": 0})
        company_name_str = company_info.get('company_name', 'FLOWRA') if company_info else 'FLOWRA'

        from services.ledger_pdf_service import generate_tally_ledger_pdf
        output = generate_tally_ledger_pdf(
            customer_name=customer_name,
            company_name=company_name_str,
            entries=entries,
            fy=fy,
            customer_info=cust_info or {},
            opening_balance=opening_balance
        )

        filename = f"ledger_{customer_name.replace(' ', '_')}_{fy or 'all'}.pdf"
        user = await get_current_user(request, db)
        if user:
            await log_audit("data_export", user.get("username", ""), tenant_id=ctx.get("tenant_id", "") if ctx else "", company_id=ctx.get("company_id", "") if ctx else "", target=f"Ledger PDF: {customer_name}", ip_address=get_client_ip(request))
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting customer ledger: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/customers/payment-behavior")
async def get_payment_behavior(request: Request, customer: Optional[str] = None, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Payment behavior analysis — filters by FY when provided. Includes opening balance."""
    try:
        from datetime import date as date_type
        today = date_type.today()
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        # Fetch ALL vouchers first
        all_sales_raw = await db.sales_vouchers.find(q, {"_id": 0}).to_list(20000)
        all_receipts_raw_all = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(20000)
        all_credit_notes_raw = await db.credit_notes.find(q, {"_id": 0}).to_list(20000)
        all_journals_raw = await db.journal_vouchers.find(q, {"_id": 0}).to_list(20000)

        # Split receipt_vouchers into actual receipts (CR party) vs payment vouchers (DR party)
        def _is_pmt(v):
            return (v.get("voucher_type") or "").strip().lower() == "payment"
        all_receipts_raw = [v for v in all_receipts_raw_all if not _is_pmt(v)]
        all_payments_raw = [v for v in all_receipts_raw_all if _is_pmt(v)]

        # Apply branch exclusion
        exclude_branches = request.headers.get("X-Exclude-Branches", "").lower() == "true"
        branch_parties = []
        if exclude_branches:
            branch_parties = await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
        if branch_parties:
            all_sales_raw = [v for v in all_sales_raw if v.get("party_name") not in branch_parties]
            all_receipts_raw = [v for v in all_receipts_raw if v.get("party_name") not in branch_parties]
            all_payments_raw = [v for v in all_payments_raw if v.get("party_name") not in branch_parties]
            all_credit_notes_raw = [v for v in all_credit_notes_raw if v.get("party_name") not in branch_parties]
            all_journals_raw = [v for v in all_journals_raw if v.get("party_name") not in branch_parties]

        synced_customers = await db.customers.find(q, {"_id": 0}).to_list(5000)
        if branch_parties:
            branch_set = set(p.lower() for p in branch_parties)
            synced_customers = [c for c in synced_customers if safe_str(c.get("customer_name")).lower() not in branch_set]
        synced_map = {safe_str(c.get("customer_name")).lower(): c for c in synced_customers if c.get("customer_name")}

        # FY boundary for opening balance calculation
        fy_start_str = None
        if fy:
            try:
                parts = fy.split('-')
                start_year = int(parts[0])
                fy_start_str = f"{start_year}-04-01"
            except:
                pass

        # Split vouchers into pre-FY (for opening balance) and current FY
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

        if fy:
            pre_sales, fy_sales_raw = split_by_fy(all_sales_raw)
            _, fy_receipts_raw = split_by_fy(all_receipts_raw)
            _, fy_payments_raw = split_by_fy(all_payments_raw)
            _, fy_cns_raw = split_by_fy(all_credit_notes_raw)
            _, fy_jvs_raw = split_by_fy(all_journals_raw)

            all_sales = filter_vouchers_by_fy(fy_sales_raw, fy)
            all_receipts = filter_vouchers_by_fy([{**r, 'voucher_date': r.get('voucher_date', '')} for r in fy_receipts_raw], fy)
            all_payments = filter_vouchers_by_fy([{**p, 'voucher_date': p.get('voucher_date', '')} for p in fy_payments_raw], fy)
            all_credit_notes = filter_vouchers_by_fy(fy_cns_raw, fy)
            all_journals = filter_vouchers_by_fy(fy_jvs_raw, fy)
        else:
            pre_sales = []
            all_sales = all_sales_raw
            all_receipts = all_receipts_raw
            all_payments = all_payments_raw
            all_credit_notes = all_credit_notes_raw
            all_journals = all_journals_raw

        # Compute opening balance per customer (anchored to TODAY's FY where Tally master OB lives)
        opening_balance_map = {}
        if fy_start_str:
            today_fy_year = today.year if today.month >= 4 else today.year - 1
            base_fy_start = f"{today_fy_year}-04-01"

            synced_lower_to_canonical = {}
            for sc in synced_customers:
                name = sc.get("customer_name")
                if name:
                    synced_lower_to_canonical[name.lower().strip()] = name
                    opening_balance_map[name] = safe_num(sc.get("opening_balance", 0))

            def _resolve(p):
                return synced_lower_to_canonical.get((p or "").lower().strip())

            if fy_start_str != base_fy_start:
                if fy_start_str < base_fy_start:
                    lo, hi = fy_start_str, base_fy_start
                    for v in all_sales_raw:
                        p = _resolve(v.get('party_name'))
                        if p and lo <= v.get('voucher_date', '') < hi:
                            opening_balance_map[p] -= safe_num(v.get('total_amount'))
                    for r in all_receipts_raw:
                        p = _resolve(r.get('party_name'))
                        if p and lo <= r.get('voucher_date', '') < hi:
                            opening_balance_map[p] += safe_num(r.get('amount'))
                    for pmt in all_payments_raw:
                        p = _resolve(pmt.get('party_name'))
                        if p and lo <= pmt.get('voucher_date', '') < hi:
                            opening_balance_map[p] -= safe_num(pmt.get('amount'))
                    for cn in all_credit_notes_raw:
                        p = _resolve(cn.get('party_name'))
                        if p and lo <= cn.get('voucher_date', '') < hi:
                            opening_balance_map[p] += safe_num(cn.get('total_amount'))
                    for jv in all_journals_raw:
                        p = _resolve(jv.get('party_name'))
                        if p and lo <= jv.get('voucher_date', '') < hi:
                            debit, credit = get_jv_party_amount(jv)
                            opening_balance_map[p] += credit - debit
                else:
                    lo, hi = base_fy_start, fy_start_str
                    for v in all_sales_raw:
                        p = _resolve(v.get('party_name'))
                        if p and lo <= v.get('voucher_date', '') < hi:
                            opening_balance_map[p] += safe_num(v.get('total_amount'))
                    for r in all_receipts_raw:
                        p = _resolve(r.get('party_name'))
                        if p and lo <= r.get('voucher_date', '') < hi:
                            opening_balance_map[p] -= safe_num(r.get('amount'))
                    for pmt in all_payments_raw:
                        p = _resolve(pmt.get('party_name'))
                        if p and lo <= pmt.get('voucher_date', '') < hi:
                            opening_balance_map[p] += safe_num(pmt.get('amount'))
                    for cn in all_credit_notes_raw:
                        p = _resolve(cn.get('party_name'))
                        if p and lo <= cn.get('voucher_date', '') < hi:
                            opening_balance_map[p] -= safe_num(cn.get('total_amount'))
                    for jv in all_journals_raw:
                        p = _resolve(jv.get('party_name'))
                        if p and lo <= jv.get('voucher_date', '') < hi:
                            debit, credit = get_jv_party_amount(jv)
                            opening_balance_map[p] += debit - credit

        # Build per-customer receipt totals (FY-filtered) — case-insensitive party keys
        customer_payments = {}
        customer_receipt_dates = {}
        for r in all_receipts:
            party = safe_str(r.get("party_name")).strip().lower()
            if not party or party == "unknown":
                continue
            customer_payments[party] = customer_payments.get(party, 0) + safe_num(r.get("amount"))
            customer_receipt_dates.setdefault(party, []).append(r.get("voucher_date", ""))

        # Build per-customer credit note totals (FY-filtered)
        customer_cn = {}
        for cn in all_credit_notes:
            party = safe_str(cn.get("party_name")).strip().lower()
            if party:
                customer_cn[party] = customer_cn.get(party, 0) + safe_num(cn.get("total_amount"))

        # Build per-customer journal NET adjustment (FY-filtered): positive = reduces outstanding
        customer_jv = {}
        for jv in all_journals:
            party = safe_str(jv.get("party_name")).strip().lower()
            if party:
                debit, credit = get_jv_party_amount(jv)
                net_credit = credit - debit  # positive reduces customer OS
                customer_jv[party] = customer_jv.get(party, 0) + net_credit

        behavior_map = {}
        for voucher in all_sales:
            party = voucher.get("party_name", "Unknown")
            if not party or party.strip().lower() in {"unknown", "n/a", "none", ""}:
                continue
            amount = safe_num(voucher.get("total_amount"))
            v_date_str = voucher.get("voucher_date", "")

            if party not in behavior_map:
                synced = synced_map.get(party.lower(), {})
                ob = round(opening_balance_map.get(party, 0), 2)
                behavior_map[party] = {
                    "customer_name": party,
                    "phone": synced.get("phone", ""),
                    "state": synced.get("state", ""),
                    "total_transactions": 0,
                    "total_amount": 0,
                    "opening_balance": ob,
                    "average_transaction": 0,
                    "outstanding_amount": 0,
                    "paid_amount": 0,
                    "credit_note_total": 0,
                    "journal_credit": 0,
                    "receipt_count": 0,
                    "payment_ratio": 0,
                    "payment_pattern": "regular",
                    "average_payment_delay": 0,
                    "credit_score": 0,
                    "oldest_invoice_days": 0,
                    "first_transaction": v_date_str,
                    "last_transaction": v_date_str,
                    "invoices": []
                }

            behavior_map[party]["total_transactions"] += 1
            behavior_map[party]["total_amount"] += amount

            if v_date_str:
                if v_date_str < (behavior_map[party].get("first_transaction") or "9999"):
                    behavior_map[party]["first_transaction"] = v_date_str
                if v_date_str > (behavior_map[party].get("last_transaction") or ""):
                    behavior_map[party]["last_transaction"] = v_date_str

            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    behavior_map[party]["invoices"].append({"amount": amount, "days_old": days_old, "date": v_date_str})
                    if days_old > behavior_map[party]["oldest_invoice_days"]:
                        behavior_map[party]["oldest_invoice_days"] = days_old
            except (ValueError, TypeError):
                pass

        # Add payment vouchers (DR party — e.g., cheque-bounce refunds) as DR-side activity
        for pmt in all_payments:
            party = (pmt.get("party_name") or "").strip()
            if not party:
                continue
            amount = safe_num(pmt.get("amount"))
            v_date_str = pmt.get("voucher_date", "")
            if party not in behavior_map:
                synced = synced_map.get(party.lower(), {})
                ob = round(opening_balance_map.get(party, 0), 2)
                behavior_map[party] = {
                    "customer_name": party, "phone": synced.get("phone", ""), "state": synced.get("state", ""),
                    "total_transactions": 0, "total_amount": 0, "opening_balance": ob,
                    "average_transaction": 0, "outstanding_amount": 0, "paid_amount": 0,
                    "credit_note_total": 0, "journal_credit": 0, "receipt_count": 0,
                    "payment_ratio": 0, "payment_pattern": "regular", "average_payment_delay": 0,
                    "credit_score": 0, "oldest_invoice_days": 0,
                    "first_transaction": v_date_str, "last_transaction": v_date_str, "invoices": []
                }
            behavior_map[party]["total_transactions"] += 1
            behavior_map[party]["total_amount"] += amount
            if v_date_str:
                if v_date_str < (behavior_map[party].get("first_transaction") or "9999"):
                    behavior_map[party]["first_transaction"] = v_date_str
                if v_date_str > (behavior_map[party].get("last_transaction") or ""):
                    behavior_map[party]["last_transaction"] = v_date_str

        # Item #5 fix: also include PRE-FY sales for invoice ageing (dates only, not amounts)
        # This way customers whose outstanding is entirely from previous FYs still get correct
        # oldest_invoice_days, average_payment_delay, etc.
        for voucher in pre_sales:
            party = voucher.get("party_name", "Unknown")
            if not party or party.strip().lower() in {"unknown", "n/a", "none", ""}:
                continue
            if party not in behavior_map:
                continue  # only enrich existing entries
            v_date_str = voucher.get("voucher_date", "")
            if not v_date_str:
                continue
            try:
                parts = v_date_str.split("-")
                if len(parts) == 3:
                    v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_old = (today - v_date).days
                    behavior_map[party]["invoices"].append({
                        "amount": safe_num(voucher.get("total_amount")),
                        "days_old": days_old, "date": v_date_str, "is_pre_fy": True,
                    })
                    if days_old > behavior_map[party]["oldest_invoice_days"]:
                        behavior_map[party]["oldest_invoice_days"] = days_old
                    if v_date_str < (behavior_map[party].get("first_transaction") or "9999"):
                        behavior_map[party]["first_transaction"] = v_date_str
            except (ValueError, TypeError):
                pass

        # Also add customers with only receipt activity (no sales in data)
        for sc in synced_customers:
            name = sc.get("customer_name")
            if not name or name in behavior_map:
                continue
            if customer_payments.get(name.lower().strip(), 0) > 0 or safe_num(sc.get("outstanding_amount")) > 0 or opening_balance_map.get(name, 0) != 0:
                ob = round(opening_balance_map.get(name, 0), 2)
                behavior_map[name] = {
                    "customer_name": name,
                    "phone": sc.get("phone", ""),
                    "state": sc.get("state", ""),
                    "total_transactions": 0,
                    "total_amount": 0,
                    "opening_balance": ob,
                    "average_transaction": 0,
                    "outstanding_amount": safe_num(sc.get("outstanding_amount")),
                    "paid_amount": 0,
                    "credit_note_total": 0,
                    "journal_credit": 0,
                    "receipt_count": 0,
                    "payment_ratio": 0,
                    "payment_pattern": "no_transactions",
                    "average_payment_delay": 0,
                    "credit_score": 0,
                    "oldest_invoice_days": 0,
                    "first_transaction": None,
                    "last_transaction": None,
                    "invoices": []
                }

        for party, data in behavior_map.items():
            party_key = party.lower().strip()
            total = data["total_amount"]
            ob = data.get("opening_balance", 0)
            receipt_paid = customer_payments.get(party_key, 0)
            cn_credit = customer_cn.get(party_key, 0)
            jv_credit = customer_jv.get(party_key, 0)
            total_credits = receipt_paid + cn_credit + jv_credit

            data["paid_amount"] = round(receipt_paid, 2)
            data["credit_note_total"] = round(cn_credit, 2)
            data["journal_credit"] = round(jv_credit, 2)
            data["receipt_count"] = len(customer_receipt_dates.get(party_key, []))
            # Outstanding = Opening Balance + Sales - Total Credits
            data["outstanding_amount"] = round(ob + total - total_credits, 2)

            # Total debits for ratio calculation = opening + sales
            total_debits = ob + total
            data["average_transaction"] = round(total / data["total_transactions"], 2) if data["total_transactions"] > 0 else 0
            data["payment_ratio"] = round((total_credits / total_debits * 100), 1) if total_debits > 0 else 100

            # Compute average payment delay using receipt-to-invoice matching
            if receipt_paid > 0 and data["invoices"]:
                receipt_dates = sorted([d for d in customer_receipt_dates.get(party_key, []) if d])
                invoice_dates = sorted([i["date"] for i in data["invoices"] if i.get("date")])
                # Estimate delay: avg gap between invoice dates and receipt dates
                if receipt_dates and invoice_dates:
                    delays = []
                    for rd in receipt_dates:
                        # Find closest preceding invoice
                        closest = None
                        for inv_d in invoice_dates:
                            if inv_d <= rd:
                                closest = inv_d
                        if closest:
                            try:
                                rd_parts = rd.split("-")
                                ci_parts = closest.split("-")
                                r_date = date_type(int(rd_parts[0]), int(rd_parts[1]), int(rd_parts[2]))
                                i_date = date_type(int(ci_parts[0]), int(ci_parts[1]), int(ci_parts[2]))
                                delays.append((r_date - i_date).days)
                            except:
                                pass
                    data["average_payment_delay"] = round(sum(delays) / len(delays), 0) if delays else 0
                else:
                    data["average_payment_delay"] = 0
            elif total > 0 and data["outstanding_amount"] > 0 and data["invoices"]:
                outstanding_ratio = data["outstanding_amount"] / total
                avg_invoice_age = sum(i["days_old"] for i in data["invoices"]) / len(data["invoices"])
                data["average_payment_delay"] = round(avg_invoice_age * outstanding_ratio, 0)
            else:
                data["average_payment_delay"] = 0

            # Item #5 fallback: if outstanding > 0 but no invoices found at all (pre-FY or FY),
            # use FY-start as ageing reference so the column isn't 0
            if data["outstanding_amount"] > 0 and data["oldest_invoice_days"] == 0 and fy_start_str:
                try:
                    fy_start_date = date_type(*[int(x) for x in fy_start_str.split("-")])
                    days_from_fy_start = (today - fy_start_date).days
                    data["oldest_invoice_days"] = days_from_fy_start
                except Exception:
                    pass

            # Credit score — cap payment_ratio input at 100
            capped_ratio = min(data["payment_ratio"], 100)
            payment_score = capped_ratio
            volume_score = min(20, data["total_transactions"] * 2)
            delay_penalty = min(20, data["average_payment_delay"] / 3) if data["outstanding_amount"] > 0 else 0
            data["credit_score"] = round(max(0, min(100, payment_score * 0.7 + volume_score - delay_penalty)), 1)

            # Pattern classification
            if data["payment_ratio"] >= 100:
                data["payment_pattern"] = "excellent"
            elif data["payment_ratio"] >= 90 and data["average_payment_delay"] < 15:
                data["payment_pattern"] = "excellent"
            elif data["payment_ratio"] >= 70 and data["average_payment_delay"] < 30:
                data["payment_pattern"] = "regular"
            elif data["payment_ratio"] >= 50:
                data["payment_pattern"] = "irregular"
            elif data["total_transactions"] == 0:
                data["payment_pattern"] = "no_transactions"
            else:
                data["payment_pattern"] = "risky"

            # Relationship duration
            if data.get("first_transaction") and data.get("last_transaction"):
                try:
                    ft = data["first_transaction"].split("-")
                    lt = data["last_transaction"].split("-")
                    f_date = date_type(int(ft[0]), int(ft[1]), int(ft[2]))
                    l_date = date_type(int(lt[0]), int(lt[1]), int(lt[2]))
                    data["relationship_months"] = max(1, round((l_date - f_date).days / 30))
                except:
                    data["relationship_months"] = 0
            else:
                data["relationship_months"] = 0

            # Build monthly payment timeline for the detail dropdown
            monthly_map = {}
            for inv in data.get("invoices", []):
                m = inv.get("date", "")[:7]  # YYYY-MM
                if m:
                    monthly_map.setdefault(m, {"invoiced": 0, "month": m})
                    monthly_map[m]["invoiced"] += inv["amount"]
            for rd in customer_receipt_dates.get(party_key, []):
                m = rd[:7] if rd else ""
                if m:
                    monthly_map.setdefault(m, {"invoiced": 0, "month": m})
                    # Distribute receipts proportionally — simple approach: total receipt / months
            # Add receipt amounts to monthly timeline
            if receipt_paid > 0 and monthly_map:
                receipt_months = sorted(set(rd[:7] for rd in customer_receipt_dates.get(party_key, []) if rd))
                per_month_receipt = receipt_paid / len(receipt_months) if receipt_months else 0
                for rm in receipt_months:
                    if rm in monthly_map:
                        monthly_map[rm]["received"] = monthly_map[rm].get("received", 0) + per_month_receipt
                    else:
                        monthly_map[rm] = {"invoiced": 0, "received": per_month_receipt, "month": rm}

            data["monthly_timeline"] = sorted(monthly_map.values(), key=lambda x: x["month"])[-12:]  # Last 12 months

            # Top invoices (largest, most overdue)
            top_invoices = sorted(data.get("invoices", []), key=lambda i: i.get("days_old", 0), reverse=True)[:5]
            data["top_overdue_invoices"] = top_invoices

            del data["invoices"]

        customers = list(behavior_map.values())

        if customer:
            customers = [c for c in customers if customer.lower() in safe_str(c.get("customer_name")).lower()]

        customers.sort(key=lambda c: c.get("customer_name", "").lower())

        return APIResponse(success=True, data={
            "customers": customers,
            "summary": {
                "total_customers": len(customers),
                "excellent": len([c for c in customers if c["payment_pattern"] == "excellent"]),
                "regular": len([c for c in customers if c["payment_pattern"] == "regular"]),
                "irregular": len([c for c in customers if c["payment_pattern"] == "irregular"]),
                "risky": len([c for c in customers if c["payment_pattern"] == "risky"]),
                "avg_credit_score": round(sum(c["credit_score"] for c in customers) / len(customers), 1) if customers else 0
            }
        })

    except Exception as e:
        logger.error(f"Error analyzing payment behavior: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/outstanding/export")
async def export_outstanding_excel(request: Request):
    """Export outstanding data to Excel."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    try:
        body = await request.json()
        data = body.get("data", [])
        fy = body.get("fy", "")

        wb = Workbook()
        ws = wb.active
        ws.title = "Outstanding"

        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill("solid", fgColor="2563EB")
        headers = ["Customer Name", "Group", "Opening Bal", "Total Sales", "Paid", "Outstanding", "0-30d", "30-60d", "60-90d", "90+d"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for i, row in enumerate(data, 2):
            ws.cell(row=i, column=1, value=row.get("customer_name", ""))
            ws.cell(row=i, column=2, value=row.get("ledger_group", ""))
            ws.cell(row=i, column=3, value=round(row.get("opening_balance", 0), 2))
            ws.cell(row=i, column=4, value=round(row.get("total_sales", 0), 2))
            ws.cell(row=i, column=5, value=round(row.get("paid_amount", 0), 2))
            ws.cell(row=i, column=6, value=round(row.get("outstanding_amount", 0), 2))
            aging = row.get("aging_buckets", {})
            ws.cell(row=i, column=7, value=round(aging.get("0_30", 0), 2))
            ws.cell(row=i, column=8, value=round(aging.get("30_60", 0), 2))
            ws.cell(row=i, column=9, value=round(aging.get("60_90", 0), 2))
            ws.cell(row=i, column=10, value=round(aging.get("90_plus", 0), 2))

        for col in range(1, 11):
            ws.column_dimensions[chr(64 + col)].width = 16
        ws.column_dimensions['A'].width = 30

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"outstanding_{fy or 'all'}.xlsx"
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        logger.error(f"Error exporting outstanding: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/customers/targets/export")
async def export_targets_excel(request: Request):
    """Export targets data to Excel."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    try:
        body = await request.json()
        data = body.get("data", [])
        fy = body.get("fy", "")

        wb = Workbook()
        ws = wb.active
        ws.title = "Targets"

        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill("solid", fgColor="2563EB")
        headers = ["Customer Name", "Prev FY Sales", "Target", "Current FY Achieved", "Achievement %"]
        # Add monthly columns
        months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
        headers.extend(months)

        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for i, row in enumerate(data, 2):
            ws.cell(row=i, column=1, value=row.get("customer_name", ""))
            ws.cell(row=i, column=2, value=round(row.get("previous_fy_sales", 0), 2))
            ws.cell(row=i, column=3, value=round(row.get("target", 0), 2))
            ws.cell(row=i, column=4, value=round(row.get("current_fy_sales", 0), 2))
            pct = row.get("achievement_pct", 0)
            ws.cell(row=i, column=5, value=f"{round(pct, 1)}%")
            monthly = row.get("monthly_sales", {})
            for j, m in enumerate(months):
                ws.cell(row=i, column=6 + j, value=round(monthly.get(m, 0), 2))

        for col in range(1, len(headers) + 1):
            ws.column_dimensions[chr(64 + col) if col <= 26 else 'A' + chr(64 + col - 26)].width = 14
        ws.column_dimensions['A'].width = 30

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"targets_{fy or 'all'}.xlsx"
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        logger.error(f"Error exporting targets: {e}")
        return APIResponse(success=False, error=str(e))
