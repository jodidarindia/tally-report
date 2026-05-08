"""Super Admin Seller Panel — Business dashboard, payments, invoices, customer health."""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import logging
import io
import uuid

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.audit_service import log_audit, get_client_ip
from services.ist_utils import now_ist_iso, subscription_expires_at, days_until_expiry
from services.id_mapping_service import resolve_company_names

logger = logging.getLogger(__name__)
router = APIRouter()

PLAN_PRICING = {
    "starter": {"monthly": 999, "annual": 9990, "name": "Starter"},
    "professional": {"monthly": 2499, "annual": 24990, "name": "Professional"},
    "enterprise": {"monthly": 3799, "annual": 37990, "name": "Enterprise"},
}


async def _require_super_admin(request: Request):
    user = await get_current_user(request, db)
    if not user or user.get("role") != "super_admin":
        return None
    return user


@router.get("/super-admin/business-dashboard")
async def business_dashboard(request: Request):
    """Revenue metrics, MRR, plan distribution, collections summary."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admins = await db.users.find(
            {"role": "admin"}, {"_id": 0, "password_hash": 0}
        ).to_list(1000)

        total_customers = len(admins)
        active_customers = sum(1 for a in admins if a.get("active", True))
        churned_customers = total_customers - active_customers

        # Calculate MRR and plan distribution
        mrr = 0.0
        plan_distribution = {"starter": 0, "professional": 0, "enterprise": 0}
        billing_distribution = {"monthly": 0, "annual": 0}
        total_contract_value = 0.0

        for admin in admins:
            if not admin.get("active", True):
                continue
            plan = admin.get("plan", "enterprise")
            cycle = admin.get("billing_cycle", "annual")
            months = admin.get("subscription_months", 12)
            pricing = PLAN_PRICING.get(plan, PLAN_PRICING["enterprise"])

            plan_distribution[plan] = plan_distribution.get(plan, 0) + 1
            billing_distribution[cycle] = billing_distribution.get(cycle, 0) + 1

            if cycle == "annual":
                monthly_rate = pricing["annual"] / 12
                contract_val = pricing["annual"] * (months / 12)
            else:
                monthly_rate = pricing["monthly"]
                contract_val = pricing["monthly"] * months

            mrr += monthly_rate
            total_contract_value += contract_val

        arr = mrr * 12
        arpu = mrr / active_customers if active_customers > 0 else 0

        # Payment summary
        total_received = 0.0
        total_payments = 0
        payments = await db.payments.find({}, {"_id": 0}).to_list(10000)
        for p in payments:
            total_received += p.get("amount", 0)
            total_payments += 1

        # Calculate total billed (sum of all active subscription values)
        total_billed = total_contract_value
        outstanding = max(0, total_billed - total_received)

        # Recent payments (last 5)
        recent_payments = await db.payments.find(
            {}, {"_id": 0}
        ).sort("payment_date", -1).to_list(5)

        return APIResponse(success=True, data={
            "total_customers": total_customers,
            "active_customers": active_customers,
            "churned_customers": churned_customers,
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "arpu": round(arpu, 2),
            "total_contract_value": round(total_contract_value, 2),
            "total_received": round(total_received, 2),
            "outstanding": round(outstanding, 2),
            "collection_rate": round((total_received / total_billed * 100) if total_billed > 0 else 0, 1),
            "plan_distribution": plan_distribution,
            "billing_distribution": billing_distribution,
            "total_payments": total_payments,
            "recent_payments": recent_payments,
        })
    except Exception as e:
        logger.error(f"Business dashboard error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/payments")
async def get_payments(request: Request):
    """Get full payment ledger."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        payments = await db.payments.find(
            {}, {"_id": 0}
        ).sort("payment_date", -1).to_list(5000)

        # Summary
        total = sum(p.get("amount", 0) for p in payments)
        by_mode = {}
        for p in payments:
            mode = p.get("payment_mode", "other")
            by_mode[mode] = by_mode.get(mode, 0) + p.get("amount", 0)

        return APIResponse(success=True, data={
            "payments": payments,
            "total": len(payments),
            "total_amount": round(total, 2),
            "by_mode": {k: round(v, 2) for k, v in by_mode.items()},
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/super-admin/payments")
async def record_payment(request: Request):
    """Record a payment received from a customer."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        customer_username = body.get("customer_username", "")
        amount = float(body.get("amount", 0))
        payment_date = body.get("payment_date", now_ist_iso())
        payment_mode = body.get("payment_mode", "bank_transfer")
        reference_no = body.get("reference_no", "")
        notes = body.get("notes", "")
        period_description = body.get("period_description", "")

        if not customer_username or amount <= 0:
            return APIResponse(success=False, error="Customer username and valid amount required")

        # Verify customer exists
        customer = await db.users.find_one(
            {"username": customer_username, "role": "admin"},
            {"_id": 0, "name": 1, "plan": 1, "tenant_id": 1}
        )
        if not customer:
            return APIResponse(success=False, error=f"Admin '{customer_username}' not found")

        payment = {
            "payment_id": str(uuid.uuid4()),
            "customer_username": customer_username,
            "customer_name": customer.get("name", customer_username),
            "tenant_id": customer.get("tenant_id", ""),
            "amount": amount,
            "payment_date": payment_date,
            "payment_mode": payment_mode,
            "reference_no": reference_no,
            "notes": notes,
            "period_description": period_description,
            "plan": customer.get("plan", ""),
            "recorded_by": sa["username"],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payments.insert_one(payment)

        await log_audit(
            "payment_recorded", sa["username"],
            target=customer_username,
            details=f"Amount: Rs.{amount}, Mode: {payment_mode}",
            ip_address=get_client_ip(request)
        )

        return APIResponse(success=True, message=f"Payment of Rs.{amount:,.2f} recorded for {customer_username}")
    except Exception as e:
        logger.error(f"Record payment error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/customer-ledger/{username}")
async def customer_ledger(username: str, request: Request):
    """Get payment history and subscription details for a customer."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        customer = await db.users.find_one(
            {"username": username, "role": "admin"},
            {"_id": 0, "password_hash": 0}
        )
        if not customer:
            return APIResponse(success=False, error="Customer not found")

        # Get payments
        payments = await db.payments.find(
            {"customer_username": username}, {"_id": 0}
        ).sort("payment_date", -1).to_list(1000)

        total_paid = sum(p.get("amount", 0) for p in payments)

        # Calculate total billed
        plan = customer.get("plan", "enterprise")
        cycle = customer.get("billing_cycle", "annual")
        months = customer.get("subscription_months", 12)
        pricing = PLAN_PRICING.get(plan, PLAN_PRICING["enterprise"])
        if cycle == "annual":
            total_billed = pricing["annual"] * (months / 12)
        else:
            total_billed = pricing["monthly"] * months

        # Resolve companies
        tid = customer.get("tenant_id", "")
        company_uuids = customer.get("companies", [])
        name_map = await resolve_company_names(tid, company_uuids)
        companies_display = [name_map.get(c, c) for c in company_uuids]

        # Get invoices
        invoices = await db.invoices.find(
            {"customer_username": username}, {"_id": 0}
        ).sort("invoice_date", -1).to_list(100)

        return APIResponse(success=True, data={
            "customer": {
                "username": customer["username"],
                "name": customer.get("name", ""),
                "plan": plan,
                "billing_cycle": cycle,
                "subscription_start": customer.get("subscription_start", ""),
                "subscription_months": months,
                "subscription_expires": subscription_expires_at(customer.get("subscription_start", ""), months),
                "days_left": days_until_expiry(customer.get("subscription_start", ""), months),
                "active": customer.get("active", True),
                "companies": companies_display,
                "created_at": customer.get("created_at", ""),
            },
            "payments": payments,
            "total_paid": round(total_paid, 2),
            "total_billed": round(total_billed, 2),
            "balance_due": round(max(0, total_billed - total_paid), 2),
            "invoices": invoices,
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/super-admin/invoices/generate")
async def generate_invoice(request: Request):
    """Generate an invoice for a customer."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        customer_username = body.get("customer_username", "")
        amount = float(body.get("amount", 0))
        description = body.get("description", "")
        period_from = body.get("period_from", "")
        period_to = body.get("period_to", "")
        items = body.get("items", [])

        if not customer_username or amount <= 0:
            return APIResponse(success=False, error="Customer and valid amount required")

        customer = await db.users.find_one(
            {"username": customer_username, "role": "admin"},
            {"_id": 0, "name": 1, "plan": 1, "tenant_id": 1, "billing_cycle": 1}
        )
        if not customer:
            return APIResponse(success=False, error="Customer not found")

        # Generate invoice number
        count = await db.invoices.count_documents({}) + 1
        invoice_number = f"FLW-{datetime.now().strftime('%Y%m')}-{count:04d}"

        invoice = {
            "invoice_id": str(uuid.uuid4()),
            "invoice_number": invoice_number,
            "customer_username": customer_username,
            "customer_name": customer.get("name", customer_username),
            "tenant_id": customer.get("tenant_id", ""),
            "amount": amount,
            "description": description,
            "period_from": period_from,
            "period_to": period_to,
            "items": items if items else [{"description": description or f"{PLAN_PRICING.get(customer.get('plan','enterprise'),{}).get('name','Enterprise')} Plan Subscription", "amount": amount}],
            "plan": customer.get("plan", ""),
            "billing_cycle": customer.get("billing_cycle", "annual"),
            "invoice_date": now_ist_iso(),
            "status": "unpaid",
            "generated_by": sa["username"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.invoices.insert_one(invoice)

        await log_audit(
            "invoice_generated", sa["username"],
            target=customer_username,
            details=f"Invoice {invoice_number}, Amount: Rs.{amount}",
            ip_address=get_client_ip(request)
        )

        return APIResponse(success=True, message=f"Invoice {invoice_number} generated", data={"invoice_id": invoice["invoice_id"], "invoice_number": invoice_number})
    except Exception as e:
        logger.error(f"Generate invoice error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/invoices")
async def list_invoices(request: Request):
    """List all invoices."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        invoices = await db.invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
        total_invoiced = sum(i.get("amount", 0) for i in invoices)
        paid_count = sum(1 for i in invoices if i.get("status") == "paid")
        unpaid_count = sum(1 for i in invoices if i.get("status") == "unpaid")

        return APIResponse(success=True, data={
            "invoices": invoices,
            "total": len(invoices),
            "total_invoiced": round(total_invoiced, 2),
            "paid_count": paid_count,
            "unpaid_count": unpaid_count,
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.put("/super-admin/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: str, request: Request):
    """Mark invoice as paid/unpaid."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        status = body.get("status", "")
        if status not in ("paid", "unpaid", "cancelled"):
            return APIResponse(success=False, error="Status must be paid, unpaid, or cancelled")

        result = await db.invoices.update_one(
            {"invoice_id": invoice_id},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.modified_count == 0:
            return APIResponse(success=False, error="Invoice not found")

        return APIResponse(success=True, message=f"Invoice marked as {status}")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: str, request: Request):
    """Generate and download invoice PDF."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        invoice = await db.invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not invoice:
            return APIResponse(success=False, error="Invoice not found")

        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm, leftMargin=20*mm, rightMargin=20*mm)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('InvoiceTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1e40af'), spaceAfter=4*mm)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=8*mm)
        heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1e293b'), spaceBefore=6*mm, spaceAfter=3*mm)
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#334155'))

        elements = []

        # Header
        elements.append(Paragraph("FLOWRA", title_style))
        elements.append(Paragraph("Tally Prime Analytics Platform | Jodidar India", subtitle_style))

        # Invoice details table
        inv_date = invoice.get("invoice_date", "")[:10] if invoice.get("invoice_date") else ""
        inv_data = [
            ["Invoice Number:", invoice.get("invoice_number", ""), "Date:", inv_date],
            ["Status:", invoice.get("status", "unpaid").upper(), "Plan:", invoice.get("plan", "").capitalize()],
        ]
        inv_table = Table(inv_data, colWidths=[80, 160, 50, 160])
        inv_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748b')),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(inv_table)
        elements.append(Spacer(1, 6*mm))

        # Bill To
        elements.append(Paragraph("Bill To", heading_style))
        elements.append(Paragraph(f"<b>{invoice.get('customer_name', '')}</b>", normal_style))
        elements.append(Paragraph(f"{invoice.get('customer_username', '')}", normal_style))
        if invoice.get("period_from") or invoice.get("period_to"):
            elements.append(Paragraph(f"Period: {invoice.get('period_from', '')} to {invoice.get('period_to', '')}", normal_style))
        elements.append(Spacer(1, 6*mm))

        # Items table
        elements.append(Paragraph("Items", heading_style))
        table_data = [["#", "Description", "Amount (Rs.)"]]
        items = invoice.get("items", [])
        for idx, item in enumerate(items, 1):
            table_data.append([str(idx), item.get("description", ""), f"Rs.{item.get('amount', 0):,.2f}"])
        table_data.append(["", "TOTAL", f"Rs.{invoice.get('amount', 0):,.2f}"])

        item_table = Table(table_data, colWidths=[30, 330, 100])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f9ff')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 10*mm))

        # Footer
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#94a3b8'), alignment=1)
        elements.append(Paragraph("Thank you for your business!", normal_style))
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph("FLOWRA by Jodidar India | Tally is the trademark of its respective owner", footer_style))

        doc.build(elements)
        buffer.seek(0)

        filename = f"Invoice_{invoice.get('invoice_number', 'draft')}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Invoice PDF error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/customer-health")
async def customer_health(request: Request):
    """Get usage/sync health for all tenants."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        admins = await db.users.find(
            {"role": "admin"},
            {"_id": 0, "password_hash": 0}
        ).to_list(500)

        health_data = []
        for admin in admins:
            tid = admin.get("tenant_id", "")
            company_uuids = admin.get("companies", [])
            name_map = await resolve_company_names(tid, company_uuids)
            companies_display = [name_map.get(c, c) for c in company_uuids]

            # Get last sync
            last_sync = await db.sync_status.find_one(
                {"tenant_id": tid, "type": "agent_sync"},
                {"_id": 0}
            )

            # Data counts — extended to cover all current modules
            inv_count = await db.inventory_items.count_documents({"tenant_id": tid})
            sales_count = await db.sales_vouchers.count_documents({"tenant_id": tid})
            cust_count = await db.customers.count_documents({"tenant_id": tid})
            purchase_count = await db.purchase_vouchers.count_documents({"tenant_id": tid})
            receipt_count = await db.receipt_vouchers.count_documents({"tenant_id": tid})
            credit_note_count = await db.credit_notes.count_documents({"tenant_id": tid})
            beat_run_count = await db.beat_runs.count_documents({"tenant_id": tid})
            salesman_order_count = await db.salesman_orders.count_documents({"tenant_id": tid})
            dispatch_card_count = await db.dispatch_cards.count_documents({"tenant_id": tid})
            # Count all non-admin staff (employee + dispatch + salesman roles).
            # The legacy `role:"employee"` filter under-counted modern multi-role
            # tenants — a tenant with 3 salesmen + 2 dispatch users showed 0.
            emp_count = await db.users.count_documents({
                "tenant_id": tid,
                "role": {"$in": ["employee", "dispatch", "salesman"]},
            })
            staff_breakdown = {}
            async for s in db.users.aggregate([
                {"$match": {"tenant_id": tid, "role": {"$ne": "admin"}}},
                {"$group": {"_id": "$role", "n": {"$sum": 1}}},
            ]):
                staff_breakdown[s["_id"]] = s["n"]

            # Days since last sync
            days_since_sync = None
            if last_sync and last_sync.get("last_sync"):
                try:
                    from dateutil.parser import parse as parse_dt
                    last_dt = parse_dt(last_sync["last_sync"])
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    diff = (datetime.now(timezone.utc) - last_dt).days
                    days_since_sync = diff
                except Exception:
                    pass

            # Determine health status
            if days_since_sync is None:
                status = "never_synced"
            elif days_since_sync <= 1:
                status = "active"
            elif days_since_sync <= 7:
                status = "moderate"
            else:
                status = "inactive"

            # Total paid
            total_paid = 0.0
            payments = await db.payments.find({"customer_username": admin["username"]}, {"_id": 0, "amount": 1}).to_list(1000)
            for p in payments:
                total_paid += p.get("amount", 0)

            health_data.append({
                "username": admin["username"],
                "name": admin.get("name", ""),
                "plan": admin.get("plan", ""),
                "active": admin.get("active", True),
                "companies": companies_display,
                "employee_count": emp_count,
                "staff_breakdown": staff_breakdown,
                "last_sync": last_sync.get("last_sync") if last_sync else None,
                "agent_version": last_sync.get("agent_version", "") if last_sync else "",
                "days_since_sync": days_since_sync,
                "health_status": status,
                "inventory_items": inv_count,
                "sales_vouchers": sales_count,
                "purchase_vouchers": purchase_count,
                "receipts": receipt_count,
                "credit_notes": credit_note_count,
                "customers": cust_count,
                "beat_runs": beat_run_count,
                "salesman_orders": salesman_order_count,
                "dispatch_cards": dispatch_card_count,
                "total_paid": round(total_paid, 2),
                "subscription_expires": subscription_expires_at(admin.get("subscription_start", ""), admin.get("subscription_months", 12)),
                "days_left": days_until_expiry(admin.get("subscription_start", ""), admin.get("subscription_months", 12)),
            })

        health_data.sort(key=lambda x: (0 if x["health_status"] == "inactive" else 1 if x["health_status"] == "never_synced" else 2 if x["health_status"] == "moderate" else 3))

        return APIResponse(success=True, data={"customers": health_data, "total": len(health_data)})
    except Exception as e:
        logger.error(f"Customer health error: {e}")
        return APIResponse(success=False, error=str(e))
