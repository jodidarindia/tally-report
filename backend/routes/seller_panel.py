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
    "trial": {"monthly": 0, "annual": 0, "name": "Free Trial (14 days)"},
}

INDIAN_INDUSTRIES = [
    "Automotive & Auto Parts", "Agriculture & Agri-Tech",
    "Chemicals & Fertilizers", "Construction Materials",
    "Consumer Electronics", "Dairy & Food Processing",
    "E-Commerce & Retail", "Education & EdTech",
    "Electrical & Electronics", "FMCG",
    "Garments & Textiles", "Hardware & Tools",
    "Healthcare & Pharma", "Hospitality & Travel",
    "Iron & Steel", "IT Services & Software",
    "Jewellery & Bullion", "Logistics & Transportation",
    "Machinery & Industrial Goods", "Paints & Coatings",
    "Paper & Packaging", "Plastics & Polymers",
    "Printing & Publishing", "Real Estate & Infra",
    "Rubber & Tyres", "Solar & Renewable Energy",
    "Sports & Fitness", "Stationery",
    "Tiles & Sanitaryware", "Wholesale & Distribution",
    "Other",
]


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
    """Generate an invoice for a customer. Accepts an optional
    `discount_pct` (0-20). Final billed = base * (1 - discount_pct/100).
    Base amount MUST come from the customer's plan for consistency —
    the frontend disables the amount field."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        customer_username = body.get("customer_username", "")
        description = body.get("description", "")
        period_from = body.get("period_from", "")
        period_to = body.get("period_to", "")
        items = body.get("items", [])
        try:
            discount_pct = float(body.get("discount_pct", 0) or 0)
        except (TypeError, ValueError):
            discount_pct = 0.0
        # Cap at 20 % (business rule from SuperAdmin spec).
        discount_pct = max(0.0, min(20.0, discount_pct))

        if not customer_username:
            return APIResponse(success=False, error="Customer required")

        customer = await db.users.find_one(
            {"username": customer_username, "role": "admin"},
            {"_id": 0, "name": 1, "plan": 1, "tenant_id": 1, "billing_cycle": 1,
             "company_name": 1, "mobile": 1, "gst": 1, "address": 1, "city": 1}
        )
        if not customer:
            return APIResponse(success=False, error="Customer not found")

        # Base amount is derived from the customer's plan — SuperAdmin
        # doesn't type an amount anymore.
        plan_id = customer.get("plan", "starter")
        cycle = customer.get("billing_cycle", "annual")
        pricing = PLAN_PRICING.get(plan_id, PLAN_PRICING["starter"])
        base_amount = float(pricing[cycle] if cycle in ("monthly", "annual") else pricing["annual"])
        # A caller can still override for one-off items (e.g. onboarding
        # fees) via body["amount"], but the default is plan-driven.
        override = body.get("amount")
        if override is not None:
            try:
                base_amount = float(override)
            except (TypeError, ValueError):
                pass
        discount_amount = round(base_amount * discount_pct / 100.0, 2)
        final_amount = round(base_amount - discount_amount, 2)

        # Generate invoice number
        count = await db.invoices.count_documents({}) + 1
        invoice_number = f"FLW-{datetime.now().strftime('%Y%m')}-{count:04d}"

        default_desc = description or f"{pricing['name']} Plan Subscription ({cycle})"
        line_items = items if items else [{"description": default_desc, "amount": base_amount}]

        invoice = {
            "invoice_id": str(uuid.uuid4()),
            "invoice_number": invoice_number,
            "customer_username": customer_username,
            "customer_name": customer.get("name", customer_username),
            "customer_company": customer.get("company_name", ""),
            "customer_gst": customer.get("gst", ""),
            "customer_address": customer.get("address", ""),
            "customer_city": customer.get("city", ""),
            "customer_mobile": customer.get("mobile", ""),
            "tenant_id": customer.get("tenant_id", ""),
            "amount": final_amount,           # <-- what the customer owes
            "base_amount": base_amount,
            "discount_pct": discount_pct,
            "discount_amount": discount_amount,
            "description": default_desc,
            "period_from": period_from,
            "period_to": period_to,
            "items": line_items,
            "plan": plan_id,
            "billing_cycle": cycle,
            "invoice_date": now_ist_iso(),
            "status": "unpaid",
            "generated_by": sa["username"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.invoices.insert_one(invoice)

        await log_audit(
            "invoice_generated", sa["username"],
            target=customer_username,
            details=f"Invoice {invoice_number}, Base: Rs.{base_amount}, Discount: {discount_pct}%, Final: Rs.{final_amount}",
            ip_address=get_client_ip(request)
        )

        return APIResponse(success=True, message=f"Invoice {invoice_number} generated",
                           data={"invoice_id": invoice["invoice_id"],
                                 "invoice_number": invoice_number,
                                 "base_amount": base_amount,
                                 "discount_pct": discount_pct,
                                 "final_amount": final_amount})
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
    """Mark invoice as paid/unpaid/cancelled.

    Business rule (Feb 2026): flipping a status MUST be tied to a
    real payment record. On PAID → server checks the invoice's linked
    customer has a payment covering the invoice amount; if not, the
    caller must pass `link_payment_id` OR `create_payment: {...}` to
    record the payment in the same call. On UNPAID → we require a
    reason (audit trail) and, when a linked payment exists, we soft-
    delete that payment link (payment row itself is kept for audit).
    """
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        body = await request.json()
        status = body.get("status", "")
        if status not in ("paid", "unpaid", "cancelled"):
            return APIResponse(success=False, error="Status must be paid, unpaid, or cancelled")

        invoice = await db.invoices.find_one({"invoice_id": invoice_id})
        if not invoice:
            return APIResponse(success=False, error="Invoice not found")

        cust = invoice.get("customer_username", "")
        inv_amt = float(invoice.get("amount", 0) or 0)
        now = datetime.now(timezone.utc).isoformat()
        update = {"status": status, "updated_at": now}

        if status == "paid":
            link_payment_id = body.get("link_payment_id")
            create_payment = body.get("create_payment") or None
            if link_payment_id:
                # Verify linked payment exists and covers the invoice
                pay = await db.payments.find_one({"payment_id": link_payment_id})
                if not pay or pay.get("customer_username") != cust:
                    return APIResponse(success=False, error="Linked payment not found or belongs to another customer")
                update["linked_payment_id"] = link_payment_id
            elif create_payment:
                pay = {
                    "payment_id": str(uuid.uuid4()),
                    "customer_username": cust,
                    "amount": float(create_payment.get("amount") or inv_amt),
                    "payment_mode": create_payment.get("payment_mode", "bank_transfer"),
                    "reference_no": create_payment.get("reference_no", ""),
                    "notes": create_payment.get("notes", f"Auto-created for invoice {invoice.get('invoice_number')}"),
                    "period_description": create_payment.get("period_description", ""),
                    "created_at": now, "source": f"invoice-mark-paid:{sa['username']}",
                }
                await db.payments.insert_one(pay)
                update["linked_payment_id"] = pay["payment_id"]
            else:
                # Fallback — only allow if there's already enough payment on record.
                pay_rows = await db.payments.find({"customer_username": cust}, {"_id": 0, "amount": 1}).to_list(1000)
                total_paid = sum(float(p.get("amount", 0) or 0) for p in pay_rows)
                if total_paid + 1 < inv_amt:
                    return APIResponse(success=False, error=(
                        f"Cannot mark as paid without a payment record. "
                        f"Customer has paid Rs. {total_paid:,.0f} but invoice is Rs. {inv_amt:,.0f}. "
                        f"Please pass `create_payment` or `link_payment_id` in the request."))
        elif status == "unpaid":
            reason = (body.get("reason") or "").strip()
            if not reason:
                return APIResponse(success=False,
                    error="A reason is required when flipping an invoice back to unpaid (audit trail).")
            update["unpaid_reason"] = reason
            update["unpaid_at"] = now
            update["unpaid_by"] = sa["username"]

        result = await db.invoices.update_one({"invoice_id": invoice_id}, {"$set": update})
        if result.matched_count == 0:
            return APIResponse(success=False, error="Invoice not found")
        await log_audit("invoice_status_changed", sa["username"], target=invoice_id,
                        details=f"{invoice.get('invoice_number')} → {status}",
                        ip_address=get_client_ip(request))
        return APIResponse(success=True, message=f"Invoice marked as {status}")
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: str, request: Request):
    """Generate and download invoice PDF.

    Redesigned per SuperAdmin brief:
      - Header: "FLOWRA" in a large font with sub-line "(A brand owned
        by JODIDAR INDIA)".
      - Right-side seller block: registered GSTIN + registered address
        pulled from env (INVOICE_SELLER_GSTIN / INVOICE_SELLER_ADDRESS)
        with sensible placeholders — user configures once in prod.
      - Optional FLOWRA logo top-left (INVOICE_LOGO_URL env).
      - Discount row shown on the totals table when > 0.
      - PDF metadata /Title = invoice number → browser tab shows the
        invoice number instead of "anonymous".
      - Filename = "<invoice_number>.pdf".
    """
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        invoice = await db.invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not invoice:
            return APIResponse(success=False, error="Invoice not found")

        import os
        import urllib.request
        import tempfile
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        # Seller identity — configurable via env so JODIDAR INDIA GST /
        # address can be set once in prod without a redeploy.
        seller_name = os.environ.get("INVOICE_SELLER_NAME", "JODIDAR INDIA")
        seller_gstin = os.environ.get("INVOICE_SELLER_GSTIN", "GSTIN to be configured")
        seller_addr = os.environ.get("INVOICE_SELLER_ADDRESS",
                                     "Registered address to be configured — set INVOICE_SELLER_ADDRESS in env")
        seller_email = os.environ.get("INVOICE_SELLER_EMAIL", "support@flowralive.in")
        seller_phone = os.environ.get("INVOICE_SELLER_PHONE", "+91 81204 70018")
        logo_url = os.environ.get(
            "INVOICE_LOGO_URL",
            "https://customer-assets.emergentagent.com/job_tally-report-ai/artifacts/pk69kw8u_IMG-20260407-WA0022.jpg"
        )

        buffer = io.BytesIO()
        inv_num = invoice.get("invoice_number", "invoice")
        # `title` here becomes the PDF's /Title metadata so browser tabs
        # display the invoice number instead of "anonymous".
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=15 * mm, bottomMargin=18 * mm,
            leftMargin=18 * mm, rightMargin=18 * mm,
            title=inv_num,
            author=seller_name,
            subject=f"Tax Invoice {inv_num}",
        )
        styles = getSampleStyleSheet()
        brand_style = ParagraphStyle('Brand',   parent=styles['Heading1'], fontSize=34, textColor=colors.HexColor('#0f172a'), leading=36, spaceAfter=0)
        brand_sub_style = ParagraphStyle('BrandSub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#64748b'), spaceAfter=0)
        seller_style = ParagraphStyle('Seller', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#334155'), alignment=2, leading=12)  # 2 = right
        h2_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#1e293b'), spaceBefore=4 * mm, spaceAfter=2 * mm)
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#334155'), leading=13)
        muted_style = ParagraphStyle('Muted', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#94a3b8'))

        elements = []

        # ── Header row: logo + brand block on left, seller block on right ──
        logo_flowable = None
        try:
            if logo_url:
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                urllib.request.urlretrieve(logo_url, tmp.name)
                logo_flowable = Image(tmp.name, width=20 * mm, height=20 * mm)
        except Exception as le:
            logger.warning(f"invoice logo fetch failed: {le}")

        brand_block = [
            Paragraph("FLOWRA", brand_style),
            Paragraph("(A brand owned by JODIDAR INDIA)", brand_sub_style),
        ]
        left_cell = [logo_flowable, ""] if logo_flowable else brand_block
        # If logo present, put brand text below/right of it
        if logo_flowable:
            header_left = Table([[logo_flowable, brand_block]], colWidths=[24 * mm, None])
            header_left.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
        else:
            header_left = brand_block

        seller_html = (
            f"<b>{seller_name}</b><br/>"
            f"GSTIN: {seller_gstin}<br/>"
            f"{seller_addr}<br/>"
            f"{seller_email} · {seller_phone}"
        )
        header_right = Paragraph(seller_html, seller_style)

        header_table = Table(
            [[header_left, header_right]],
            colWidths=[100 * mm, 74 * mm],
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(header_table)
        # Divider
        divider = Table([[""]], colWidths=[174 * mm], rowHeights=[1])
        divider.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0'))]))
        elements.append(divider)
        elements.append(Spacer(1, 4 * mm))

        # ── TAX INVOICE title band ──
        title_band = ParagraphStyle('InvBand', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#1e40af'), alignment=1, spaceAfter=4 * mm)
        elements.append(Paragraph("TAX INVOICE", title_band))

        # ── Invoice meta table ──
        inv_date_iso = invoice.get("invoice_date", "")
        inv_date = inv_date_iso[:10] if inv_date_iso else ""
        meta_rows = [
            ["Invoice #", inv_num, "Date", inv_date],
            ["Plan", (invoice.get("plan") or "").title(), "Billing", (invoice.get("billing_cycle") or "").title()],
            ["Status", (invoice.get("status") or "unpaid").upper(), "Period",
             f"{invoice.get('period_from', '') or '—'} → {invoice.get('period_to', '') or '—'}"],
        ]
        meta_table = Table(meta_rows, colWidths=[22 * mm, 62 * mm, 22 * mm, 68 * mm])
        meta_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9.5),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748b')),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 6 * mm))

        # ── Bill To block ──
        elements.append(Paragraph("Bill To", h2_style))
        bt_lines = [
            f"<b>{invoice.get('customer_company') or invoice.get('customer_name') or ''}</b>",
        ]
        if invoice.get("customer_name") and invoice.get("customer_company"):
            bt_lines.append(f"Attn: {invoice['customer_name']}")
        addr_bits = [b for b in [invoice.get('customer_address', ''), invoice.get('customer_city', '')] if b]
        if addr_bits:
            bt_lines.append(", ".join(addr_bits))
        if invoice.get("customer_gst"):
            bt_lines.append(f"GSTIN: {invoice['customer_gst']}")
        bt_lines.append(invoice.get('customer_username', ''))
        if invoice.get("customer_mobile"):
            bt_lines.append(invoice['customer_mobile'])
        elements.append(Paragraph("<br/>".join(bt_lines), normal_style))
        elements.append(Spacer(1, 6 * mm))

        # ── Items table ──
        elements.append(Paragraph("Items", h2_style))
        table_data = [["#", "Description", "Amount (Rs.)"]]
        items = invoice.get("items", [])
        for idx, item in enumerate(items, 1):
            table_data.append([str(idx), item.get("description", ""), f"{item.get('amount', 0):,.2f}"])
        base_amount = float(invoice.get("base_amount", invoice.get("amount", 0)))
        discount_pct = float(invoice.get("discount_pct", 0))
        discount_amount = float(invoice.get("discount_amount", 0))
        final_amount = float(invoice.get("amount", 0))

        table_data.append(["", "Subtotal", f"{base_amount:,.2f}"])
        if discount_pct > 0:
            table_data.append(["", f"Discount ({discount_pct:.1f}%)", f"-{discount_amount:,.2f}"])
        table_data.append(["", "TOTAL PAYABLE", f"{final_amount:,.2f}"])

        item_table = Table(table_data, colWidths=[12 * mm, 128 * mm, 34 * mm])
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f9ff')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ]
        # Grey the discount row if present
        if discount_pct > 0:
            style_cmds.append(('TEXTCOLOR', (0, -2), (-1, -2), colors.HexColor('#dc2626')))
        item_table.setStyle(TableStyle(style_cmds))
        elements.append(item_table)
        elements.append(Spacer(1, 10 * mm))

        # ── Footer ──
        elements.append(Paragraph("Thank you for choosing FLOWRA.", normal_style))
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph(
            "Payment terms: Due on receipt. Reply to this invoice for bank details or UPI. "
            "This is a computer-generated invoice and does not require a signature.",
            muted_style))
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph(
            "FLOWRA is a brand owned and operated by JODIDAR INDIA. "
            "Tally and Busy are trademarks of their respective owners.",
            muted_style))

        doc.build(elements)
        buffer.seek(0)

        # File name = invoice number (spec).
        filename = f"{inv_num}.pdf"
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



@router.get("/super-admin/customers/search")
async def customer_search(request: Request, q: str = "", limit: int = 20):
    """Type-ahead customer picker for SuperAdmin's Record Payment and
    Generate Invoice modals. Also returns each customer's current
    balance / due (base contract value − total received) so the UI can
    render live pre-fill data without a second round-trip.

    Returns customers whose `username`, `name` or `company_name` contain
    the query (case-insensitive). Limited to 20 results by default."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    try:
        q = (q or "").strip()
        limit = max(1, min(50, int(limit or 20)))
        filt = {"role": "admin"}
        if q:
            import re as _re
            regex = _re.escape(q)
            filt["$or"] = [
                {"username":    {"$regex": regex, "$options": "i"}},
                {"name":        {"$regex": regex, "$options": "i"}},
                {"company_name":{"$regex": regex, "$options": "i"}},
            ]
        admins = await db.users.find(filt, {
            "_id": 0, "username": 1, "name": 1, "company_name": 1,
            "plan": 1, "billing_cycle": 1, "subscription_months": 1,
            "active": 1, "is_trial": 1, "trial_end": 1,
        }).limit(limit).to_list(limit)

        out = []
        for a in admins:
            plan = a.get("plan", "starter")
            cycle = a.get("billing_cycle", "annual")
            months = int(a.get("subscription_months", 12) or 12)
            pricing = PLAN_PRICING.get(plan, PLAN_PRICING["starter"])
            base_price = float(pricing[cycle] if cycle in ("monthly", "annual") else pricing["annual"])
            if cycle == "annual":
                total_billed = base_price * (months / 12.0)
            elif cycle == "monthly":
                total_billed = base_price * months
            else:
                total_billed = base_price
            # Sum payments — cheap because payments collection is small.
            payments = await db.payments.find(
                {"customer_username": a["username"]}, {"_id": 0, "amount": 1}
            ).to_list(1000)
            total_paid = sum(float(p.get("amount", 0) or 0) for p in payments)
            balance_due = round(max(0.0, total_billed - total_paid), 2)
            out.append({
                "username": a["username"],
                "name": a.get("name", ""),
                "company_name": a.get("company_name", ""),
                "plan": plan,
                "plan_name": pricing["name"],
                "billing_cycle": cycle,
                "active": a.get("active", True),
                "is_trial": bool(a.get("is_trial")),
                "trial_end": a.get("trial_end", ""),
                # base_price is the price PER cycle (monthly OR annual) —
                # the Generate Invoice modal uses this to render the
                # fixed amount that a super-admin can then discount.
                "base_price": round(base_price, 2),
                "total_billed": round(total_billed, 2),
                "total_paid": round(total_paid, 2),
                "balance_due": balance_due,
            })
        return APIResponse(success=True, data={"customers": out, "count": len(out)})
    except Exception as e:
        logger.error(f"customer search error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/industries")
async def list_industries(request: Request):
    """Static curated list of Indian-market industries for the New
    Customer form dropdown."""
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Super admin access required")
    return APIResponse(success=True, data={"industries": INDIAN_INDUSTRIES})
