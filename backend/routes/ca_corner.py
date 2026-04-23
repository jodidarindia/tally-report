"""
CA Corner routes — Cash Flow, P&L Report, AI Expense Insights.
Cash Flow follows Tally's Indirect Method:
  Operating Activities: Net P&L + non-cash adjustments + working capital changes
  Investing Activities: Fixed asset purchases/sales
  Financing Activities: Loans, equity, dividends
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import logging
import os

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context
from utils import safe_num, filter_vouchers_by_fy

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_q(ctx, company_id=None, extra=None):
    q = {}
    if ctx and ctx.get("tenant_id"):
        q["tenant_id"] = ctx["tenant_id"]
    if company_id:
        q["company_id"] = company_id
    elif ctx and ctx.get("company_id"):
        q["company_id"] = ctx["company_id"]
    if extra:
        q.update(extra)
    return q


# ─── CASH FLOW (Tally Indirect Method) ───────────────────

@router.get("/ca-corner/cash-flow")
async def get_cash_flow(request: Request, fy: str = ""):
    """Generate Cash Flow Statement following Tally's indirect method."""
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx)
        company_id = q.get("company_id", "")

        # Get P&L data
        pl = await db.profit_loss.find_one(
            {"tenant_id": q.get("tenant_id", ""), "company_id": company_id}, {"_id": 0}
        )
        net_profit = pl.get("net_profit_loss", 0) if pl else 0
        total_income = pl.get("total_income", 0) if pl else 0
        total_expense = pl.get("total_expense", 0) if pl else 0

        # Get bank/cash ledgers
        bank_cash = await db.bank_cash_ledgers.find(q, {"_id": 0}).to_list(100)
        cash_ledgers = [l for l in bank_cash if l.get("ledger_type") == "cash"]
        bank_ledgers = [l for l in bank_cash if l.get("ledger_type") == "bank"]
        od_ledgers = [l for l in bank_cash if l.get("ledger_type") == "bank_od"]

        cash_opening = sum(abs(l.get("opening_balance", 0)) for l in cash_ledgers)
        cash_closing = sum(abs(l.get("closing_balance", 0)) for l in cash_ledgers)
        bank_opening = sum(abs(l.get("opening_balance", 0)) for l in bank_ledgers)
        bank_closing = sum(abs(l.get("closing_balance", 0)) for l in bank_ledgers)
        od_balance = sum(l.get("closing_balance", 0) for l in od_ledgers)

        # Get voucher data for the FY
        receipts = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)
        payments = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)
        contras = await db.contra_vouchers.find(q, {"_id": 0}).to_list(10000)
        journals = await db.journal_vouchers.find(q, {"_id": 0}).to_list(10000)

        if fy:
            receipts = filter_vouchers_by_fy(receipts, fy)
            payments = filter_vouchers_by_fy(payments, fy)
            contras = filter_vouchers_by_fy(contras, fy)
            journals = filter_vouchers_by_fy(journals, fy)

        # Classify receipts and payments
        receipt_total = sum(abs(safe_num(v.get("amount", 0))) for v in receipts if v.get("voucher_type", "").lower() == "receipt")
        payment_total = sum(abs(safe_num(v.get("amount", 0))) for v in payments if v.get("voucher_type", "").lower() == "payment")

        # Separate depreciation from expenses (non-cash)
        depreciation = 0
        if pl:
            for exp in pl.get("expense", []):
                if "depreciation" in exp.get("ledger_name", "").lower() or "depreciation" in exp.get("parent_group", "").lower():
                    depreciation += exp.get("amount", 0)

        # Operating Activities (Indirect Method)
        # Start with Net Profit, add back non-cash items
        operating_items = [
            {"label": "Net Profit / (Loss)", "amount": round(net_profit, 2)},
            {"label": "Add: Depreciation", "amount": round(depreciation, 2)},
        ]
        cash_from_operations = net_profit + depreciation

        # Working capital changes (simplified using receipt/payment data)
        # Positive = cash inflow, Negative = cash outflow
        net_operating = round(cash_from_operations, 2)

        # Investing Activities
        # Fixed asset transactions from journals/contras
        investing_items = []
        investing_total = 0

        # Financing Activities
        # Loans, equity changes from journals
        financing_items = []
        od_change = round(od_balance, 2)
        if od_change != 0:
            financing_items.append({"label": "Bank OD / Loan Movement", "amount": od_change})
        financing_total = sum(f["amount"] for f in financing_items)

        # Net cash change
        opening_cash_bank = round(cash_opening + bank_opening, 2)
        closing_cash_bank = round(cash_closing + bank_closing, 2)
        net_change = round(closing_cash_bank - opening_cash_bank, 2)

        return APIResponse(success=True, data={
            "operating": {
                "items": operating_items,
                "net": net_operating,
            },
            "investing": {
                "items": investing_items,
                "net": investing_total,
            },
            "financing": {
                "items": financing_items,
                "net": financing_total,
            },
            "summary": {
                "opening_cash": round(cash_opening, 2),
                "opening_bank": round(bank_opening, 2),
                "opening_total": opening_cash_bank,
                "closing_cash": round(cash_closing, 2),
                "closing_bank": round(bank_closing, 2),
                "closing_total": closing_cash_bank,
                "net_change": net_change,
                "total_receipts": round(receipt_total, 2),
                "total_payments": round(payment_total, 2),
                "od_balance": round(od_balance, 2),
            },
            "bank_details": [
                {
                    "name": l.get("ledger_name", ""),
                    "type": l.get("ledger_type", ""),
                    "opening": round(l.get("opening_balance", 0), 2),
                    "closing": round(l.get("closing_balance", 0), 2),
                    "bank_name": l.get("bank_name", ""),
                    "account_number": l.get("account_number", ""),
                }
                for l in bank_cash
            ],
        })
    except Exception as e:
        logger.error(f"Cash flow error: {e}")
        return APIResponse(success=False, error=str(e))


# ─── P&L REPORT (Monthly + Annual) ───────────────────────

@router.get("/ca-corner/profit-loss")
async def get_profit_loss(request: Request, fy: str = "", view: str = "annual"):
    """Get P&L report. view=annual or monthly."""
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx)
        company_id = q.get("company_id", "")

        # Get stored P&L data
        pl = await db.profit_loss.find_one(
            {"tenant_id": q.get("tenant_id", ""), "company_id": company_id}, {"_id": 0}
        )
        if not pl:
            return APIResponse(success=True, data={
                "income": [], "expense": [],
                "total_income": 0, "total_expense": 0, "net_profit_loss": 0,
                "view": view, "monthly": []
            })

        if view == "annual":
            return APIResponse(success=True, data={
                "income": pl.get("income", []),
                "expense": pl.get("expense", []),
                "total_income": pl.get("total_income", 0),
                "total_expense": pl.get("total_expense", 0),
                "net_profit_loss": pl.get("net_profit_loss", 0),
                "view": "annual",
            })

        # Monthly view: compute from vouchers
        months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
        month_nums = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]

        sales_v = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
        purchase_v = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(50000)
        receipt_v = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)

        if fy:
            sales_v = filter_vouchers_by_fy(sales_v, fy)
            purchase_v = filter_vouchers_by_fy(purchase_v, fy)
            receipt_v = filter_vouchers_by_fy(receipt_v, fy)

        # Build monthly totals
        monthly_data = []
        for i, (m_name, m_num) in enumerate(zip(months, month_nums)):
            month_sales = 0
            month_purchases = 0
            month_receipts = 0

            for v in sales_v:
                vd = v.get("voucher_date", v.get("date", ""))
                if vd:
                    try:
                        d = datetime.fromisoformat(vd.replace("Z", ""))
                        if d.month == m_num:
                            month_sales += abs(safe_num(v.get("amount", 0)))
                    except Exception:
                        pass

            for v in purchase_v:
                vd = v.get("voucher_date", v.get("date", ""))
                if vd:
                    try:
                        d = datetime.fromisoformat(vd.replace("Z", ""))
                        if d.month == m_num:
                            month_purchases += abs(safe_num(v.get("amount", 0)))
                    except Exception:
                        pass

            for v in receipt_v:
                vd = v.get("voucher_date", v.get("date", ""))
                if vd:
                    try:
                        d = datetime.fromisoformat(vd.replace("Z", ""))
                        if d.month == m_num:
                            month_receipts += abs(safe_num(v.get("amount", 0)))
                    except Exception:
                        pass

            gross_profit = month_sales - month_purchases
            monthly_data.append({
                "month": m_name,
                "sales": round(month_sales, 2),
                "purchases": round(month_purchases, 2),
                "receipts": round(month_receipts, 2),
                "gross_profit": round(gross_profit, 2),
            })

        return APIResponse(success=True, data={
            "income": pl.get("income", []),
            "expense": pl.get("expense", []),
            "total_income": pl.get("total_income", 0),
            "total_expense": pl.get("total_expense", 0),
            "net_profit_loss": pl.get("net_profit_loss", 0),
            "view": "monthly",
            "monthly": monthly_data,
        })
    except Exception as e:
        logger.error(f"P&L error: {e}")
        return APIResponse(success=False, error=str(e))


# ─── AI EXPENSE INSIGHTS ─────────────────────────────────

@router.post("/ca-corner/expense-insights")
async def get_expense_insights(request: Request):
    """AI-powered expense analysis using GPT-5.2."""
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx)
        company_id = q.get("company_id", "")

        pl = await db.profit_loss.find_one(
            {"tenant_id": q.get("tenant_id", ""), "company_id": company_id}, {"_id": 0}
        )
        if not pl or not pl.get("expense"):
            return APIResponse(success=False, error="No expense data available. Please sync your Tally* data first.")

        # Prepare expense summary for AI
        expenses = pl.get("expense", [])
        total_expense = pl.get("total_expense", 0)
        total_income = pl.get("total_income", 0)
        net_pl = pl.get("net_profit_loss", 0)

        expense_summary = "\n".join([
            f"- {e['ledger_name']} ({e['parent_group']}): Rs.{e['amount']:,.2f}"
            for e in sorted(expenses, key=lambda x: x.get('amount', 0), reverse=True)
        ])

        prompt = f"""Analyze the following business expense data from Tally* accounting software and provide actionable insights:

FINANCIAL SUMMARY:
- Total Income: Rs.{total_income:,.2f}
- Total Expenses: Rs.{total_expense:,.2f}
- Net Profit/Loss: Rs.{net_pl:,.2f}
- Expense-to-Income Ratio: {(total_expense/total_income*100) if total_income > 0 else 0:.1f}%

EXPENSE BREAKDOWN:
{expense_summary}

Please provide:
1. TOP OVERSPENDING AREAS: Identify 3-5 expense categories where spending seems high relative to industry norms for Indian SMEs
2. COST REDUCTION SUGGESTIONS: Specific, actionable ways to reduce each overspending area (with estimated savings %)
3. EXPENSE HEALTH SCORE: Rate overall expense management on a scale of 1-10
4. RED FLAGS: Any unusual or concerning expense patterns
5. QUICK WINS: 2-3 immediate actions that could save money this month

Keep the language simple and practical for a business owner. Use Indian Rupee amounts. Be specific with numbers and percentages."""

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return APIResponse(success=False, error="AI service not configured")

        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid

        chat = LlmChat(
            api_key=api_key,
            session_id=f"expense-{uuid.uuid4().hex[:8]}",
            system_message="You are a chartered accountant and financial advisor for Indian SMEs. Analyze expense data and provide clear, actionable insights to reduce costs and improve profitability. Format your response with clear headers and bullet points."
        )
        chat.with_model("openai", "gpt-5.2")

        user_msg = UserMessage(text=prompt)
        response = await chat.send_message(user_msg)

        return APIResponse(success=True, data={
            "analysis": response,
            "expense_summary": {
                "total_income": round(total_income, 2),
                "total_expense": round(total_expense, 2),
                "net_profit_loss": round(net_pl, 2),
                "expense_ratio": round(total_expense / total_income * 100, 1) if total_income > 0 else 0,
                "top_expenses": [
                    {"name": e["ledger_name"], "amount": e["amount"], "group": e["parent_group"]}
                    for e in sorted(expenses, key=lambda x: x.get("amount", 0), reverse=True)[:10]
                ],
            },
        })
    except Exception as e:
        logger.error(f"AI Expense insights error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# BALANCE SHEET
# ═══════════════════════════════════════════════════════

@router.get("/ca-corner/balance-sheet")
async def get_balance_sheet(request: Request, fy: str = "", company_id: Optional[str] = None):
    """Balance Sheet from all_ledgers: Assets vs Liabilities + Capital."""
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx, company_id)
        ledgers = await db.all_ledgers.find(q, {"_id": 0}).to_list(5000)

        if not ledgers:
            return APIResponse(success=True, data={
                "assets": [], "liabilities": [], "total_assets": 0, "total_liabilities": 0,
                "message": "No ledger data synced yet. Please run the desktop agent to sync."
            })

        # Classify
        asset_cats = {'current_assets', 'fixed_assets', 'investments', 'stock_in_hand', 'misc_expense', 'cash', 'bank', 'bank_od'}
        liability_cats = {'current_liabilities', 'provisions', 'duties_taxes', 'non_current_liabilities', 'secured_loans', 'unsecured_loans'}
        capital_cats = {'capital', 'reserves', 'profit_loss_ac'}

        def group_ledgers(cats, sign=1):
            groups = {}
            for l in ledgers:
                if l.get('category') in cats:
                    grp = l.get('parent_group', 'Other')
                    groups.setdefault(grp, {"group": grp, "ledgers": [], "total": 0})
                    amt = round(abs(l.get('closing_balance', 0)), 2)
                    groups[grp]["ledgers"].append({"name": l.get('ledger_name', ''), "amount": amt})
                    groups[grp]["total"] += amt
            return sorted(groups.values(), key=lambda x: x['total'], reverse=True)

        assets = group_ledgers(asset_cats)
        liabilities = group_ledgers(liability_cats)
        capital = group_ledgers(capital_cats)

        total_assets = sum(g['total'] for g in assets)
        total_liabilities = sum(g['total'] for g in liabilities)
        total_capital = sum(g['total'] for g in capital)

        return APIResponse(success=True, data={
            "assets": assets,
            "liabilities": liabilities,
            "capital": capital,
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "total_capital": round(total_capital, 2),
            "total_liabilities_capital": round(total_liabilities + total_capital, 2),
        })
    except Exception as e:
        logger.error(f"Balance sheet error: {e}")
        return APIResponse(success=False, error=str(e))


# ═══════════════════════════════════════════════════════
# P&L DRILL-DOWN — Ledger-wise breakdown by group
# ═══════════════════════════════════════════════════════

@router.get("/ca-corner/pl-drilldown")
async def get_pl_drilldown(request: Request, type: str = "expense", company_id: Optional[str] = None):
    """Get ledger-wise P&L drill-down grouped by parent. type=income or expense."""
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx, company_id)

        # From stored P&L data
        pl = await db.profit_loss.find_one(
            {"tenant_id": q.get("tenant_id", ""), "company_id": q.get("company_id", "")}, {"_id": 0}
        )
        if not pl:
            return APIResponse(success=True, data={"groups": [], "total": 0, "type": type})

        items = pl.get(type, [])  # income or expense array
        total = pl.get(f"total_{type}", 0)

        # Group by parent_group
        groups = {}
        for item in items:
            grp = item.get("parent_group", "Other")
            groups.setdefault(grp, {"group": grp, "ledgers": [], "total": 0})
            amt = round(abs(item.get("amount", 0)), 2)
            groups[grp]["ledgers"].append({
                "name": item.get("ledger_name", ""),
                "amount": amt,
                "pct": round(amt / total * 100, 1) if total > 0 else 0,
            })
            groups[grp]["total"] += amt

        # Sort groups and ledgers
        for g in groups.values():
            g["ledgers"] = sorted(g["ledgers"], key=lambda x: x["amount"], reverse=True)
            g["pct"] = round(g["total"] / total * 100, 1) if total > 0 else 0

        result = sorted(groups.values(), key=lambda x: x['total'], reverse=True)

        return APIResponse(success=True, data={
            "groups": result,
            "total": round(total, 2),
            "type": type,
        })
    except Exception as e:
        logger.error(f"P&L drilldown error: {e}")
        return APIResponse(success=False, error=str(e))
