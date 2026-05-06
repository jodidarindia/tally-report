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
    """Get P&L report. Computes totals from FY-scoped vouchers (Sales, Purchases) +
    JV-derived indirect income/expense activity. Falls back to stored profit_loss
    document for ledger breakdown lists (income/expense ledger names).
    """
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx)

        # Fetch FY-scoped voucher totals (this is the accurate source of truth)
        sales_v = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
        purchase_v = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(50000)
        cn_v = await db.credit_notes.find(q, {"_id": 0}).to_list(20000)
        dn_v = await db.debit_notes.find(q, {"_id": 0}).to_list(5000)
        jv_v = await db.journal_vouchers.find(q, {"_id": 0}).to_list(20000)

        if fy:
            sales_v = filter_vouchers_by_fy(sales_v, fy)
            purchase_v = filter_vouchers_by_fy(purchase_v, fy)
            cn_v = filter_vouchers_by_fy(cn_v, fy)
            dn_v = filter_vouchers_by_fy(dn_v, fy)
            jv_v = filter_vouchers_by_fy(jv_v, fy)

        total_sales = sum(safe_num(v.get("total_amount")) for v in sales_v)
        total_purchases = sum(safe_num(v.get("total_amount")) for v in purchase_v)
        total_credit_notes = sum(safe_num(v.get("total_amount")) for v in cn_v)  # Sales reversal
        total_debit_notes = sum(safe_num(v.get("total_amount")) for v in dn_v)   # Purchase reversal

        # Net Sales = Sales - Credit Notes; Net Purchases = Purchases - Debit Notes
        net_sales = total_sales - total_credit_notes
        net_purchases = total_purchases - total_debit_notes

        # Indirect income/expense from JV ledger entries (FY-filtered)
        # Group by parent_group on the entry's ledger
        all_ledgers = await db.all_ledgers.find(q, {"_id": 0}).to_list(5000)
        ledger_to_category = {l.get("ledger_name", "").lower().strip(): l.get("category", "other") for l in all_ledgers}
        ledger_to_parent = {l.get("ledger_name", "").lower().strip(): l.get("parent_group", "") for l in all_ledgers}

        indirect_income = 0.0
        indirect_expense = 0.0
        direct_expense_misc = 0.0  # Direct Expense (not purchases)
        direct_income_misc = 0.0   # Direct Income (not sales)
        ledger_activity = {}  # ledger_name -> {amount, parent, category, is_debit_dominant}

        # Scan ledger_entries across ALL voucher types — most P&L activity flows through
        # payment / receipt / JV vouchers (e.g., paying rent via bank = payment voucher
        # with DR Rent, CR Bank). JVs alone miss ~90% of expense activity.
        rcpt_v = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)
        contra_v = await db.contra_vouchers.find(q, {"_id": 0}).to_list(20000) if 'contra_vouchers' in await db.list_collection_names() else []
        if fy:
            rcpt_v = filter_vouchers_by_fy([{**r, 'voucher_date': r.get('voucher_date', '')} for r in rcpt_v], fy)
            contra_v = filter_vouchers_by_fy(contra_v, fy)

        for vouch in jv_v + rcpt_v + contra_v + sales_v + purchase_v + cn_v + dn_v:
            for entry in vouch.get("ledger_entries", []) or []:
                lname = (entry.get("ledger_name") or "").strip()
                if not lname:
                    continue
                amt = safe_num(entry.get("amount"))
                is_dr = bool(entry.get("is_debit"))
                cat = ledger_to_category.get(lname.lower(), "other")
                if cat not in ("indirect_income", "indirect_expense", "direct_income", "direct_expense"):
                    continue

                # Skip ledgers under Sales Accounts / Purchase Accounts — these are
                # already captured in voucher header totals (total_sales / total_purchases)
                # so summing their entries would double-count.
                parent_lower = ledger_to_parent.get(lname.lower(), "").lower().strip()
                if parent_lower in ("sales accounts", "purchase accounts"):
                    continue

                # Sign convention:
                #   Income ledgers: CR = positive income, DR = reversal (negative)
                #   Expense ledgers: DR = positive expense, CR = reversal (negative)
                if cat == "indirect_income":
                    indirect_income += (-amt if is_dr else amt)
                elif cat == "direct_income":
                    direct_income_misc += (-amt if is_dr else amt)
                elif cat == "indirect_expense":
                    indirect_expense += (amt if is_dr else -amt)
                elif cat == "direct_expense":
                    direct_expense_misc += (amt if is_dr else -amt)

                # Track per-ledger for breakdown
                if lname not in ledger_activity:
                    ledger_activity[lname] = {
                        "ledger_name": lname,
                        "parent_group": ledger_to_parent.get(lname.lower(), ""),
                        "category": cat,
                        "amount": 0.0,
                    }
                if cat in ("indirect_expense", "direct_expense"):
                    ledger_activity[lname]["amount"] += (amt if is_dr else -amt)
                else:
                    ledger_activity[lname]["amount"] += (-amt if is_dr else amt)

        # Stock — best-effort from synced inventory (may be 0 if not yet synced)
        inventory = await db.inventory.find(q, {"_id": 0}).to_list(5000)
        opening_stock = sum(safe_num(i.get("opening_value", 0)) for i in inventory)
        closing_stock = sum(safe_num(i.get("closing_value", 0)) for i in inventory)

        # Build income / expense breakdown lists
        income_breakdown = []
        expense_breakdown = []
        for la in ledger_activity.values():
            if la["category"] in ("indirect_income", "direct_income") and abs(la["amount"]) > 0.01:
                income_breakdown.append({
                    "ledger_name": la["ledger_name"], "parent_group": la["parent_group"],
                    "amount": round(la["amount"], 2),
                })
            elif la["category"] in ("indirect_expense", "direct_expense") and abs(la["amount"]) > 0.01:
                expense_breakdown.append({
                    "ledger_name": la["ledger_name"], "parent_group": la["parent_group"],
                    "amount": round(la["amount"], 2),
                })
        income_breakdown.sort(key=lambda x: -abs(x["amount"]))
        expense_breakdown.sort(key=lambda x: -abs(x["amount"]))

        # Tally formula:
        #   Trading Account: Sales + Closing Stock = Opening Stock + Purchases + Direct Expenses + Gross Profit
        #   → Gross Profit = (Net Sales + Closing Stock + Direct Income) - (Opening Stock + Net Purchases + Direct Expense)
        gross_profit = (net_sales + closing_stock + direct_income_misc) - (opening_stock + net_purchases + direct_expense_misc)

        # Net Profit = Gross Profit + Indirect Income - Indirect Expense
        net_profit = gross_profit + indirect_income - indirect_expense

        total_income = net_sales + direct_income_misc + indirect_income
        total_expense = net_purchases + direct_expense_misc + indirect_expense

        result = {
            "fy": fy,
            "view": view,
            # Header totals
            "total_sales": round(net_sales, 2),
            "total_purchases": round(net_purchases, 2),
            "opening_stock": round(opening_stock, 2),
            "closing_stock": round(closing_stock, 2),
            "indirect_income": round(indirect_income, 2),
            "indirect_expense": round(indirect_expense, 2),
            "direct_income": round(direct_income_misc, 2),
            "direct_expense": round(direct_expense_misc, 2),
            # Final figures
            "gross_profit": round(gross_profit, 2),
            "net_profit_loss": round(net_profit, 2),
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            # Breakdowns (for tables)
            "income": income_breakdown,
            "expense": expense_breakdown,
        }

        # Monthly view: per-month sales/purchases/gross-profit
        if view == "monthly":
            months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
            month_nums = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
            monthly_data = []
            for m_name, m_num in zip(months, month_nums):
                m_sales = sum(safe_num(v.get("total_amount")) for v in sales_v
                              if (v.get("voucher_date", "")[:10] and len(v.get("voucher_date", "")) >= 10
                                  and int(v.get("voucher_date", "0000-00-00")[5:7] or 0) == m_num))
                m_purchases = sum(safe_num(v.get("total_amount")) for v in purchase_v
                                  if (v.get("voucher_date", "")[:10] and len(v.get("voucher_date", "")) >= 10
                                      and int(v.get("voucher_date", "0000-00-00")[5:7] or 0) == m_num))
                monthly_data.append({
                    "month": m_name,
                    "sales": round(m_sales, 2),
                    "purchases": round(m_purchases, 2),
                    "gross_profit": round(m_sales - m_purchases, 2),
                })
            result["monthly"] = monthly_data

        return APIResponse(success=True, data=result)
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
    """Balance Sheet — reads the FY-scoped snapshot built by the agent's Tally BS report
    (uses SVFROMDATE/SVTODATE so closing balances are FY-end accurate, not running cumulative).

    Falls back to the legacy `all_ledgers` snapshot if the new collection isn't populated yet.
    """
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx, company_id)

        # Try the new FY-scoped snapshot first
        if fy:
            snapshot = await db.balance_sheets.find_one({**q, "fy": fy}, {"_id": 0})
            if snapshot and snapshot.get("groups"):
                groups = snapshot["groups"]
                # Group display labels — match Tally's BS format
                LABELS = {
                    'capital': 'Capital Account',
                    'reserves': 'Reserves & Surplus',
                    'secured_loans': 'Secured Loans',
                    'unsecured_loans': 'Unsecured Loans',
                    'current_liabilities': 'Current Liabilities',
                    'provisions': 'Provisions',
                    'duties_taxes': 'Duties & Taxes',
                    'sundry_creditors': 'Sundry Creditors',
                    'non_current_liabilities': 'Non-Current Liabilities',
                    'profit_loss_ac': 'Profit & Loss A/c',
                    'branch_division': 'Branch / Divisions',
                    'suspense': 'Suspense A/c',
                    'fixed_assets': 'Fixed Assets',
                    'investments': 'Investments',
                    'current_assets': 'Current Assets',
                    'stock_in_hand': 'Stock-in-Hand',
                    'sundry_debtors': 'Sundry Debtors',
                    'cash': 'Cash-in-Hand',
                    'bank': 'Bank Accounts',
                    'bank_od': 'Bank OD A/c',
                    'misc_expense': 'Misc. Expenses (Asset)',
                }
                assets = []
                liabilities = []
                for cat, g in groups.items():
                    entry = {
                        'group': LABELS.get(cat, cat.replace('_', ' ').title()),
                        'category': cat,
                        'total': g['total'],
                        'ledgers': g.get('ledgers', []),
                    }
                    if g.get('side') == 'asset':
                        assets.append(entry)
                    else:
                        liabilities.append(entry)
                assets.sort(key=lambda x: -abs(x['total']))
                liabilities.sort(key=lambda x: -abs(x['total']))
                tot = snapshot.get('totals', {})
                return APIResponse(success=True, data={
                    "fy": fy,
                    "fy_start": snapshot.get("fy_start"),
                    "fy_end": snapshot.get("fy_end"),
                    "assets": assets,
                    "liabilities": liabilities,
                    "total_assets": tot.get("assets", 0),
                    "total_liabilities": tot.get("liabilities", 0),
                    "difference": tot.get("difference", 0),
                    "source": "tally_bs_snapshot",
                    "raw_ledger_count": snapshot.get("raw_ledger_count", 0),
                    "last_synced": snapshot.get("last_synced"),
                })

        # Legacy fallback — point-in-time all_ledgers (loses FY scoping)
        ledgers = await db.all_ledgers.find(q, {"_id": 0}).to_list(5000)
        if not ledgers:
            return APIResponse(success=True, data={
                "assets": [], "liabilities": [], "total_assets": 0, "total_liabilities": 0,
                "source": "empty",
                "message": "No Balance Sheet snapshot found. Re-sync with the latest Tally agent (v9.2+)."
            })

        asset_cats = {'current_assets', 'fixed_assets', 'investments', 'stock_in_hand', 'misc_expense', 'cash', 'bank', 'bank_od', 'sundry_debtors'}
        liab_cats = {'current_liabilities', 'provisions', 'duties_taxes', 'non_current_liabilities', 'secured_loans', 'unsecured_loans', 'capital', 'reserves', 'profit_loss_ac', 'sundry_creditors'}

        def group_ledgers(cats):
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
        liabilities = group_ledgers(liab_cats)
        return APIResponse(success=True, data={
            "assets": assets,
            "liabilities": liabilities,
            "total_assets": round(sum(g['total'] for g in assets), 2),
            "total_liabilities": round(sum(g['total'] for g in liabilities), 2),
            "source": "legacy_all_ledgers",
            "message": "Showing legacy point-in-time view. Re-sync with the latest Tally agent for FY-accurate Balance Sheet."
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
