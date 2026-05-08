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

        # Get bank/cash ledgers — agent stores discriminator under `category`,
        # legacy/manual rows may use `ledger_type`. Honor either.
        bank_cash = await db.bank_cash_ledgers.find(q, {"_id": 0}).to_list(100)
        def _kind(l):
            return l.get("category") or l.get("ledger_type") or ""
        cash_ledgers = [l for l in bank_cash if _kind(l) == "cash"]
        bank_ledgers = [l for l in bank_cash if _kind(l) == "bank"]
        od_ledgers   = [l for l in bank_cash if _kind(l) == "bank_od"]

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
                # Normalize bank/loan balances to "owner-cash perspective":
                #   - Asset accounts (Bank Accounts / Cash-in-Hand): keep raw sign
                #     (positive = money you have, negative = overdrawn).
                #   - Liability accounts (Bank OD / CC / OCC):  flip sign
                #     (Tally stores CR balance as +ve = "you owe"; flipping makes
                #      negative = you owe, positive = extra deposit / overpaid loan).
                {
                    "name": l.get("ledger_name", ""),
                    "type": l.get("category", l.get("ledger_type", "")),
                    "opening": round(
                        -1 * l.get("opening_balance", 0)
                        if l.get("category") == "bank_od"
                        else l.get("opening_balance", 0),
                        2,
                    ),
                    "closing": round(
                        -1 * l.get("closing_balance", 0)
                        if l.get("category") == "bank_od"
                        else l.get("closing_balance", 0),
                        2,
                    ),
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
    """Get P&L report.

    For the CURRENT FY (which is what Tally syncs by default), we sum directly
    from `all_ledgers.closing_balance` grouped by parent_group. This matches
    Tally's Profit & Loss A/c output exactly because Tally's CLOSINGBALANCE on
    each ledger IS the FY net activity.

    For PREVIOUS FYs, we fall back to summing ledger_entries inside FY-scoped
    vouchers — less reliable due to DR/CR sign noise, but the only available
    source until the agent gains per-FY P&L snapshots.
    """
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx)

        # Determine if we're asking for the current FY (Tally's auto-roll target)
        from datetime import date as _date
        today = _date.today()
        today_fy_year = today.year if today.month >= 4 else today.year - 1
        today_fy = f"{today_fy_year}-{str(today_fy_year + 1)[-2:]}"
        is_current_fy = (not fy) or (fy == today_fy)

        all_ledgers = await db.all_ledgers.find(q, {"_id": 0}).to_list(5000)

        sales_accounts = direct_income = indirect_income = 0.0
        purchase_accounts = direct_expense = indirect_expense = 0.0
        ledger_activity = {}

        if is_current_fy and all_ledgers:
            # === Method A: Sum CLOSINGBALANCE by parent_group ===
            # Tally agent's storage convention (validated against user's Tally PDF):
            #   Sales A/c ledgers      → stored positive  (sum directly)
            #   Income (Ind/Direct)    → stored positive  (sum directly)
            #   Purchase A/c ledgers   → stored negative  (flip sign)
            #   Expense (Ind/Direct)   → stored negative  (flip sign)
            # Classification priority: parent_group first, then category.
            # Already-counted ledgers are tracked to avoid double-counting (e.g.,
            # a "direct_expense" ledger whose parent IS "Purchase Accounts" gets
            # counted only under purchase_accounts).
            counted = set()
            for l in all_ledgers:
                lname = (l.get("ledger_name") or "").strip()
                parent = (l.get("parent_group") or "").lower().strip()
                cat = l.get("category", "other")
                bal = safe_num(l.get("closing_balance"))
                if abs(bal) < 0.01:
                    continue
                if lname.lower() in counted:
                    continue

                if parent == "sales accounts":
                    delta = bal  # already positive
                    sales_accounts += delta
                    bucket = "income"
                elif parent == "purchase accounts":
                    delta = -bal  # flip negative → positive
                    purchase_accounts += delta
                    bucket = "expense"
                elif cat == "direct_income":
                    delta = bal
                    direct_income += delta
                    bucket = "income"
                elif cat == "indirect_income":
                    delta = bal
                    indirect_income += delta
                    bucket = "income"
                elif cat == "direct_expense":
                    delta = -bal  # flip
                    direct_expense += delta
                    bucket = "expense"
                elif cat == "indirect_expense":
                    delta = -bal  # flip
                    indirect_expense += delta
                    bucket = "expense"
                # Heuristic catch-all for user-defined P&L sub-groups the agent
                # didn't classify (e.g., "Salary Accounts", "Local Thela Gaadi"
                # under Indirect Expenses). Recognised by parent_group string.
                elif any(kw in parent for kw in (
                    'salary', 'wages', 'thela', 'gaadi', 'fuel',
                    'rent', 'travel', 'commission', 'advertisement',
                )) and cat == "other":
                    delta = -bal  # treat as indirect expense (DR-natural)
                    indirect_expense += delta
                    bucket = "expense"
                else:
                    continue

                counted.add(lname.lower())
                ledger_activity[lname] = {
                    "ledger_name": lname,
                    "parent_group": l.get("parent_group", ""),
                    "category": cat,
                    "amount": round(delta, 2),
                    "bucket": bucket,
                }
            method_used = "all_ledgers_closing_balance"
        else:
            # === Method B: Sum ledger_entries from FY-scoped vouchers ===
            # Used for previous FYs (less reliable due to DR/CR sign noise).
            sales_v = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
            purchase_v = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(50000)
            cn_v = await db.credit_notes.find(q, {"_id": 0}).to_list(20000)
            dn_v = await db.debit_notes.find(q, {"_id": 0}).to_list(5000)
            jv_v = await db.journal_vouchers.find(q, {"_id": 0}).to_list(20000)
            rcpt_v = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)
            contra_v = await db.contra_vouchers.find(q, {"_id": 0}).to_list(20000) if 'contra_vouchers' in await db.list_collection_names() else []
            if fy:
                sales_v = filter_vouchers_by_fy(sales_v, fy)
                purchase_v = filter_vouchers_by_fy(purchase_v, fy)
                cn_v = filter_vouchers_by_fy(cn_v, fy)
                dn_v = filter_vouchers_by_fy(dn_v, fy)
                jv_v = filter_vouchers_by_fy(jv_v, fy)
                rcpt_v = filter_vouchers_by_fy(rcpt_v, fy)
                contra_v = filter_vouchers_by_fy(contra_v, fy)
            ledger_meta = {(l.get("ledger_name") or "").lower().strip():
                           {"category": l.get("category", "other"),
                            "parent_group": (l.get("parent_group") or "").lower().strip()}
                           for l in all_ledgers}

            # Sales / Purchase totals: derive from items[].amount (pre-GST line totals)
            # because sales_vouchers and purchase_vouchers don't always store full
            # ledger_entries breakdowns. Net sales = sales items − credit-note items;
            # net purchases = purchase items − debit-note items.
            def _items_total(v):
                return sum(safe_num(it.get("amount", 0)) for it in (v.get("items") or []))

            for sv in sales_v:
                sales_accounts += _items_total(sv)
            for cn in cn_v:
                items_amt = _items_total(cn)
                if items_amt == 0:
                    items_amt = safe_num(cn.get("total_amount"))
                sales_accounts -= items_amt
            for pv in purchase_v:
                purchase_accounts += _items_total(pv)
            for dn in dn_v:
                items_amt = _items_total(dn)
                if items_amt == 0:
                    items_amt = safe_num(dn.get("total_amount"))
                purchase_accounts -= items_amt

            # Direct/Indirect Income/Expense + Sales/Purchase A/c adjustments come
            # from journal_vouchers / receipt_vouchers / contra_vouchers
            # ledger_entries (those DO have full breakdowns). Credit/debit notes
            # are deliberately EXCLUDED here — their net impact is already deducted
            # via items[] above; including them again would double-count.
            for vouch in jv_v + rcpt_v + contra_v:
                for entry in vouch.get("ledger_entries", []) or []:
                    lname = (entry.get("ledger_name") or "").strip()
                    if not lname:
                        continue
                    meta = ledger_meta.get(lname.lower(), {})
                    cat = meta.get("category", "other")
                    parent = meta.get("parent_group", "")
                    amt = safe_num(entry.get("amount"))
                    is_dr = bool(entry.get("is_debit"))
                    if parent == "sales accounts" or cat == "direct_income":
                        delta = (-amt if is_dr else amt)
                        if parent == "sales accounts":
                            sales_accounts += delta
                        else:
                            direct_income += delta
                        bucket = "income"
                    elif parent == "purchase accounts" or cat == "direct_expense":
                        delta = (amt if is_dr else -amt)
                        if parent == "purchase accounts":
                            purchase_accounts += delta
                        else:
                            direct_expense += delta
                        bucket = "expense"
                    elif cat == "indirect_income":
                        delta = (-amt if is_dr else amt)
                        indirect_income += delta
                        bucket = "income"
                    elif cat == "indirect_expense":
                        delta = (amt if is_dr else -amt)
                        indirect_expense += delta
                        bucket = "expense"
                    else:
                        continue
                    if lname not in ledger_activity:
                        ledger_activity[lname] = {
                            "ledger_name": lname, "parent_group": meta.get("parent_group", ""),
                            "category": cat, "amount": 0.0, "bucket": bucket,
                        }
                    ledger_activity[lname]["amount"] += delta
            method_used = "ledger_entries_fy_scoped"

        # Stock from inventory_items (master snapshot — reflects CURRENT FY only).
        # For previous FYs: closing-stock-of-prev-FY ≈ opening-stock-of-current-FY.
        # We don't have prev-FY's opening, so we drop stock from GP for prev FYs
        # to avoid arithmetic that's silently wrong.
        inventory = await db.inventory_items.find(q, {"_id": 0}).to_list(50000)
        master_opening_stock = sum(safe_num(i.get("opening_value", 0)) for i in inventory)
        master_closing_stock = sum(safe_num(i.get("closing_value", 0)) for i in inventory)

        if is_current_fy:
            opening_stock = master_opening_stock
            closing_stock = master_closing_stock
            stock_synced = closing_stock > 0 or opening_stock > 0
            stock_note_for_prev_fy = None
        else:
            # closing-stock for the requested prev FY = current FY's opening stock
            opening_stock = 0.0
            closing_stock = master_opening_stock
            stock_synced = False  # opening side is missing
            stock_note_for_prev_fy = (
                "Opening Stock for previous FYs is not synced (Tally master only "
                "stores current-FY stock). Closing Stock here is approximated as "
                "the current FY's Opening Stock; Gross Profit therefore excludes "
                "previous-FY stock movement and may differ from Tally's exact figure."
            )

        # Tally Trading Account formula:
        #   Sales A/c + Direct Income + Closing Stock
        #     = Opening Stock + Purchase A/c + Direct Expense + Gross Profit
        gross_profit = ((sales_accounts + direct_income + closing_stock) -
                        (opening_stock + purchase_accounts + direct_expense))
        net_profit = gross_profit + indirect_income - indirect_expense
        total_income = sales_accounts + direct_income + indirect_income
        total_expense = purchase_accounts + direct_expense + indirect_expense

        income_breakdown, expense_breakdown = [], []
        for la in ledger_activity.values():
            if abs(la["amount"]) < 0.01:
                continue
            entry = {"ledger_name": la["ledger_name"], "parent_group": la["parent_group"],
                     "amount": round(la["amount"], 2)}
            (income_breakdown if la["bucket"] == "income" else expense_breakdown).append(entry)
        income_breakdown.sort(key=lambda x: -abs(x["amount"]))
        expense_breakdown.sort(key=lambda x: -abs(x["amount"]))

        result = {
            "fy": fy or today_fy,
            "view": view,
            "method": method_used,
            "total_sales": round(sales_accounts, 2),
            "total_purchases": round(purchase_accounts, 2),
            "opening_stock": round(opening_stock, 2),
            "closing_stock": round(closing_stock, 2),
            "indirect_income": round(indirect_income, 2),
            "indirect_expense": round(indirect_expense, 2),
            "direct_income": round(direct_income, 2),
            "direct_expense": round(direct_expense, 2),
            "gross_profit": round(gross_profit, 2),
            "net_profit_loss": round(net_profit, 2),
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "income": income_breakdown,
            "expense": expense_breakdown,
            "stock_synced": stock_synced,
        }

        # Notices
        notices = []
        if is_current_fy and not stock_synced:
            notices.append("Stock-in-Hand not yet synced. Re-run the Tally Desktop Agent (v9.5+) to capture closing stock values for accurate Gross Profit.")
        if stock_note_for_prev_fy:
            notices.append(stock_note_for_prev_fy)
        if not is_current_fy:
            notices.append(f"Showing previous FY ({fy}). For 100% Tally parity, re-anchor by running the agent during that FY — current view is reconstructed from FY-scoped vouchers.")
        result["notices"] = notices

        # Monthly view: per-month net sales/purchases (ex-GST), direct income/expense,
        # and receipts. Sales/purchase vouchers store NET amounts in `items[].amount`
        # (pre-GST line totals — verified against Tally PDF). GST/discount/round-off
        # are in `ledger_entries` and contribute via journal_vouchers when applicable.
        #
        # Note: monthly GP excludes opening/closing stock movement (we don't have
        # monthly stock snapshots) — flagged in `notices` so the user knows the
        # FY-total `gross_profit` may differ by the stock delta.
        if view == "monthly":
            sales_v = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
            purchase_v = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(50000)
            cn_v = await db.credit_notes.find(q, {"_id": 0}).to_list(20000)
            dn_v = await db.debit_notes.find(q, {"_id": 0}).to_list(5000)
            jv_v = await db.journal_vouchers.find(q, {"_id": 0}).to_list(20000)
            rcpt_v = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)
            if fy:
                sales_v = filter_vouchers_by_fy(sales_v, fy)
                purchase_v = filter_vouchers_by_fy(purchase_v, fy)
                cn_v = filter_vouchers_by_fy(cn_v, fy)
                dn_v = filter_vouchers_by_fy(dn_v, fy)
                jv_v = filter_vouchers_by_fy(jv_v, fy)
                rcpt_v = filter_vouchers_by_fy(rcpt_v, fy)

            ledger_meta = {(l.get("ledger_name") or "").lower().strip():
                           {"category": l.get("category", "other"),
                            "parent_group": (l.get("parent_group") or "").lower().strip()}
                           for l in all_ledgers}

            # 12 buckets keyed by FY-month (Apr=4 ... Mar=3)
            buckets = {m: {"net_sales": 0.0, "net_purchases": 0.0,
                           "direct_income": 0.0, "direct_expense": 0.0,
                           "receipts": 0.0}
                       for m in range(1, 13)}

            def _month_of(date_str):
                if not date_str or len(date_str) < 10:
                    return None
                try:
                    return int(date_str[5:7])
                except (ValueError, TypeError):
                    return None

            def _items_total(v):
                return sum(safe_num(it.get("amount", 0)) for it in (v.get("items") or []))

            # Sales: items[].amount is pre-GST net (verified vs Tally PDF parity)
            for sv in sales_v:
                m = _month_of(sv.get("voucher_date", ""))
                if not m:
                    continue
                buckets[m]["net_sales"] += _items_total(sv)

            # Credit notes (sales returns) reduce net sales
            for cn in cn_v:
                m = _month_of(cn.get("voucher_date", ""))
                if not m:
                    continue
                items_amt = _items_total(cn)
                # Some credit-note types may not have items[]; fall back to total_amount
                if items_amt == 0:
                    items_amt = safe_num(cn.get("total_amount"))
                buckets[m]["net_sales"] -= items_amt

            # Purchases (mirror)
            for pv in purchase_v:
                m = _month_of(pv.get("voucher_date", ""))
                if not m:
                    continue
                buckets[m]["net_purchases"] += _items_total(pv)
            for dn in dn_v:
                m = _month_of(dn.get("voucher_date", ""))
                if not m:
                    continue
                items_amt = _items_total(dn)
                if items_amt == 0:
                    items_amt = safe_num(dn.get("total_amount"))
                buckets[m]["net_purchases"] -= items_amt

            # Direct Income / Direct Expense from journal_vouchers' ledger_entries.
            # These are typically booked separately (e.g., "Bulk Discount Allowed",
            # "Freight Inward") and don't appear in sales/purchase items.
            for jv in jv_v:
                m = _month_of(jv.get("voucher_date", ""))
                if not m:
                    continue
                for entry in (jv.get("ledger_entries") or []):
                    lname = (entry.get("ledger_name") or "").strip().lower()
                    if not lname:
                        continue
                    meta = ledger_meta.get(lname, {})
                    cat = meta.get("category", "other")
                    parent = meta.get("parent_group", "")
                    amt = safe_num(entry.get("amount"))
                    is_dr = bool(entry.get("is_debit"))
                    if parent == "sales accounts":
                        buckets[m]["net_sales"] += (-amt if is_dr else amt)
                    elif parent == "purchase accounts":
                        buckets[m]["net_purchases"] += (amt if is_dr else -amt)
                    elif cat == "direct_income":
                        buckets[m]["direct_income"] += (-amt if is_dr else amt)
                    elif cat == "direct_expense":
                        buckets[m]["direct_expense"] += (amt if is_dr else -amt)

            # Receipts (CR-side of receipt_vouchers, voucher_type=Receipt)
            for r in rcpt_v:
                if (r.get("voucher_type") or "").strip().lower() != "receipt":
                    continue
                m = _month_of(r.get("voucher_date", ""))
                if m:
                    buckets[m]["receipts"] += abs(safe_num(r.get("amount", 0)))

            months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
            month_nums = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]

            # ── Stock-aware GP allocation (Tally Trading Account, monthly) ──
            # Use FY-LEVEL totals (the same numbers shown in the P&L summary cards)
            # so Σ Monthly_GP equals the FY Gross_Profit shown above.
            #
            # FY GP = (FY Sales + FY Direct Income + Closing Stock)
            #       − (Opening Stock + FY Purchases + FY Direct Expense)
            #
            # Monthly COGS allocated proportionally to each month's NET SALES.
            # Total monthly sales is also normalised so Σ Monthly_Sales = FY Sales.
            fy_sales_total = sales_accounts + direct_income
            fy_purch_total = purchase_accounts + direct_expense
            fy_cogs = opening_stock + fy_purch_total - closing_stock
            stock_movement_total = closing_stock - opening_stock

            # Monthly numerators (from items[] + JV adjustments — distribution shape)
            monthly_sales_raw = [buckets[m]["net_sales"] + buckets[m]["direct_income"] for m in month_nums]
            monthly_purch_raw = [buckets[m]["net_purchases"] + buckets[m]["direct_expense"] for m in month_nums]
            sum_monthly_sales = sum(monthly_sales_raw)
            sum_monthly_purch = sum(monthly_purch_raw)

            monthly_data = []
            prev_sales = prev_purch = prev_gp = None
            stock_aware = is_current_fy and stock_synced and abs(fy_sales_total) > 0.01 and abs(sum_monthly_sales) > 0.01

            # Scaling factors so Σ monthly = FY total exactly
            sales_scale = (fy_sales_total / sum_monthly_sales) if sum_monthly_sales else 1.0
            purch_scale = (fy_purch_total / sum_monthly_purch) if sum_monthly_purch else 1.0

            for idx, (m_name, m_num) in enumerate(zip(months, month_nums)):
                m_sales_raw = monthly_sales_raw[idx]
                m_purch_raw = monthly_purch_raw[idx]
                # Scale to FY totals (preserves shape, fixes magnitude)
                m_sales_net = round(m_sales_raw * sales_scale, 2) if stock_aware else round(m_sales_raw, 2)
                m_purchases_net = round(m_purch_raw * purch_scale, 2) if stock_aware else round(m_purch_raw, 2)

                if stock_aware:
                    weight = m_sales_net / fy_sales_total if fy_sales_total else 0
                    m_cogs = round(fy_cogs * weight, 2)
                    m_open_stock = round(opening_stock * weight, 2)
                    m_close_stock = round(closing_stock * weight, 2)
                    m_gp = round(m_sales_net - m_cogs, 2)
                else:
                    m_cogs = m_purchases_net
                    m_open_stock = m_close_stock = 0.0
                    m_gp = round(m_sales_net - m_purchases_net, 2)

                def _pct(curr, prev):
                    if prev is None or abs(prev) < 0.01:
                        return None
                    return round(((curr - prev) / abs(prev)) * 100, 1)

                row = {
                    "month": m_name,
                    "sales": m_sales_net,
                    "purchases": m_purchases_net,
                    "cogs": m_cogs,
                    "opening_stock": m_open_stock,
                    "closing_stock": m_close_stock,
                    "gross_profit": m_gp,
                    "receipts": round(buckets[m_num]["receipts"], 2),
                    "sales_change_pct": _pct(m_sales_net, prev_sales),
                    "purchases_change_pct": _pct(m_purchases_net, prev_purch),
                    "gp_change_pct": _pct(m_gp, prev_gp),
                }
                monthly_data.append(row)
                prev_sales = m_sales_net
                prev_purch = m_purchases_net
                prev_gp = m_gp

            result["monthly"] = monthly_data
            result["monthly_meta"] = {
                "stock_aware": stock_aware,
                "fy_cogs": round(fy_cogs, 2) if stock_aware else None,
                "stock_movement": round(stock_movement_total, 2) if stock_aware else None,
            }
            if stock_aware:
                result["notices"] = result.get("notices", []) + [
                    f"Monthly Gross Profit uses Tally Trading-Account formula: Sales − COGS, where FY COGS (₹{fy_cogs:,.0f}) and stock movement (₹{stock_movement_total:+,.0f}) are allocated to each month proportionally to its net sales. Sum of monthly GP equals FY-total Gross Profit (₹{result['gross_profit']:,.0f}).",
                ]
            else:
                result["notices"] = result.get("notices", []) + [
                    "Monthly Gross Profit shown is Trading Profit (Net Sales − Net Purchases, ex-GST) — stock movement could not be allocated because the FY's stock data isn't fully synced. FY-total Gross Profit above (which uses stock) may differ.",
                ]

        return APIResponse(success=True, data=result)
    except Exception as e:
        logger.exception(f"P&L error: {e}")
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

# Tally root-group classification.  Used to bucket each ledger's parent group
# into the Liability or Asset side and pick a display label.
# Sign convention used by the desktop agent (Tally XML AMOUNT):
#   stored balance > 0  → CR-natural (liability)
#   stored balance < 0  → DR-natural (asset)
# Display rule:
#   Liability side: show as +stored
#   Asset side    : show as -stored
_LIAB_GROUPS = {
    'capital_account':         {'label': 'Capital Account',          'parents': ('capital account', "partner's capital account", 'proprietor', 'reserves & surplus', 'reserves and surplus')},
    'loans_liability':         {'label': 'Loans (Liability)',        'parents': ('loans (liability)', 'secured loans', 'unsecured loans', 'bank od a/c', 'bank o/d a/c', 'bank occ a/c', 'bank cc accounts', 'bank od accounts')},
    'current_liabilities':     {'label': 'Current Liabilities',      'parents': ('current liabilities', 'duties & taxes', 'duties and taxes', 'provisions', 'sundry creditors', 'dealer deposit')},
    'suspense':                {'label': 'Suspense A/c',             'parents': ('suspense a/c', 'suspense account')},
    'non_current_liability':   {'label': 'Non-Current Liability',    'parents': ('non current liability', 'non-current liability', 'non-current liabilities')},
    'profit_loss_ac':          {'label': 'Profit & Loss A/c',        'parents': ('profit & loss a/c', 'profit and loss a/c', 'profit & loss')},
}
_ASSET_GROUPS = {
    'fixed_assets':   {'label': 'Fixed Assets',   'parents': ('fixed assets',)},
    'investments':    {'label': 'Investments',    'parents': ('investments',)},
    'current_assets': {'label': 'Current Assets', 'parents': ('current assets', 'bank accounts', 'cash-in-hand', 'cash in hand', 'stock-in-hand', 'stock in hand', 'sundry debtors', 'deposits (asset)', 'loans & advances (asset)', 'loans and advances (asset)')},
    'misc_expense':   {'label': 'Misc. Expenses (Asset)', 'parents': ('misc. expenses (asset)', 'misc expenses (asset)', 'miscellaneous expenses (asset)')},
    'branch_division':{'label': 'Branch / Divisions',     'parents': ('branch / divisions', 'branch/divisions')},
}
# P&L groups — must be excluded from BS entirely (the synthetic P&L A/c row carries
# the net result instead).
_PL_PARENTS = (
    'sales accounts', 'purchase accounts',
    'direct income', 'direct incomes', 'indirect income', 'indirect incomes',
    'direct expenses', 'direct expense', 'indirect expenses', 'indirect expense',
    'manufacturing expenses', 'salary accounts',
)
# Tally user-defined sub-groups commonly seen under Sundry Debtors (region-wise).
# Anything else under "Distributor" / "Dealer" is treated as a debtor sub-group.
_DEBTOR_PARENT_HINTS = ('distributor', 'sundry debtors', 'debtors', 'dealer', 'customer')
_CREDITOR_PARENT_HINTS = ('sundry creditor', 'creditor', 'supplier', 'vendor')


def _classify_parent(parent: str):
    """Return (side, group_key, label) for a Tally parent_group name.
    side ∈ {'asset', 'liability', 'pl', 'unknown'}.
    """
    p = (parent or '').lower().strip()
    if not p:
        return ('unknown', None, None)
    if any(pl in p for pl in _PL_PARENTS) or p in _PL_PARENTS:
        return ('pl', None, None)
    for key, meta in _LIAB_GROUPS.items():
        if p in meta['parents']:
            return ('liability', key, meta['label'])
    for key, meta in _ASSET_GROUPS.items():
        if p in meta['parents']:
            return ('asset', key, meta['label'])
    # Heuristic fallbacks for user-defined sub-groups
    if any(h in p for h in _CREDITOR_PARENT_HINTS):
        return ('liability', 'current_liabilities', 'Current Liabilities')
    if any(h in p for h in _DEBTOR_PARENT_HINTS):
        return ('asset', 'current_assets', 'Current Assets')
    return ('unknown', None, None)


async def _compute_pl_net_profit(q: dict, fy: str) -> float:
    """Compute net profit for an FY directly from synced vouchers (mirrors the
    /ca-corner/profit-loss endpoint logic but trimmed to just net_profit)."""
    sales_v = await db.sales_vouchers.find(q, {"_id": 0}).to_list(50000)
    purchase_v = await db.purchase_vouchers.find(q, {"_id": 0}).to_list(50000)
    cn_v = await db.credit_notes.find(q, {"_id": 0}).to_list(20000)
    dn_v = await db.debit_notes.find(q, {"_id": 0}).to_list(5000)
    jv_v = await db.journal_vouchers.find(q, {"_id": 0}).to_list(20000)
    rcpt_v = await db.receipt_vouchers.find(q, {"_id": 0}).to_list(50000)

    if fy:
        sales_v = filter_vouchers_by_fy(sales_v, fy)
        purchase_v = filter_vouchers_by_fy(purchase_v, fy)
        cn_v = filter_vouchers_by_fy(cn_v, fy)
        dn_v = filter_vouchers_by_fy(dn_v, fy)
        jv_v = filter_vouchers_by_fy(jv_v, fy)
        rcpt_v = filter_vouchers_by_fy(rcpt_v, fy)

    net_sales = sum(safe_num(v.get("total_amount")) for v in sales_v) - sum(safe_num(v.get("total_amount")) for v in cn_v)
    net_purchases = sum(safe_num(v.get("total_amount")) for v in purchase_v) - sum(safe_num(v.get("total_amount")) for v in dn_v)

    all_ledgers = await db.all_ledgers.find(q, {"_id": 0, "ledger_name": 1, "category": 1, "parent_group": 1}).to_list(5000)
    cat_of = {l.get("ledger_name", "").lower().strip(): l.get("category", "other") for l in all_ledgers}
    parent_of = {l.get("ledger_name", "").lower().strip(): (l.get("parent_group") or "").lower().strip() for l in all_ledgers}

    indirect_income = direct_income_misc = 0.0
    indirect_expense = direct_expense_misc = 0.0
    for vouch in jv_v + rcpt_v + sales_v + purchase_v + cn_v + dn_v:
        for entry in vouch.get("ledger_entries", []) or []:
            lname = (entry.get("ledger_name") or "").strip()
            if not lname:
                continue
            cat = cat_of.get(lname.lower(), "other")
            if cat not in ("indirect_income", "indirect_expense", "direct_income", "direct_expense"):
                continue
            parent_lower = parent_of.get(lname.lower(), "")
            if parent_lower in ("sales accounts", "purchase accounts"):
                continue
            amt = safe_num(entry.get("amount"))
            is_dr = bool(entry.get("is_debit"))
            if cat == "indirect_income":
                indirect_income += (-amt if is_dr else amt)
            elif cat == "direct_income":
                direct_income_misc += (-amt if is_dr else amt)
            elif cat == "indirect_expense":
                indirect_expense += (amt if is_dr else -amt)
            elif cat == "direct_expense":
                direct_expense_misc += (amt if is_dr else -amt)

    inventory = await db.inventory_items.find(q, {"_id": 0}).to_list(5000) if 'inventory_items' in (await db.list_collection_names()) else []
    opening_stock = sum(safe_num(i.get("opening_value", 0)) for i in inventory)
    closing_stock = sum(safe_num(i.get("closing_value", 0)) for i in inventory)

    gross_profit = (net_sales + closing_stock + direct_income_misc) - (opening_stock + net_purchases + direct_expense_misc)
    return round(gross_profit + indirect_income - indirect_expense, 2)


@router.get("/ca-corner/balance-sheet")
async def get_balance_sheet(request: Request, fy: str = "", company_id: Optional[str] = None):
    """Balance Sheet — derived live from synced `all_ledgers` + customers + creditors.

    Strategy (matches Tally's report layout):
      1. Bucket each ledger by parent_group → root group (asset / liability).
      2. Use customers collection authoritatively for Sundry Debtors (richer data).
      3. Synthesize Profit & Loss A/c row from computed P&L (Opening = prev-FY net,
         Current Period = this-FY net).
      4. Sign convention: stored Tally amount → +ve = CR (liability); display flips
         sign on asset side.
      5. FY mapping (Tally auto-roll): today's FY → CLOSINGBALANCE; prev FY →
         OPENINGBALANCE (= prev-FY's closing by accounting identity).
    """
    try:
        ctx = await get_tenant_context(request)
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Authentication required")

        q = _build_q(ctx, company_id)
        ledgers = await db.all_ledgers.find(q, {"_id": 0}).to_list(5000)
        debtors = await db.customers.find(q, {"_id": 0}).to_list(2000)
        # Live-derive creditors from all_ledgers using the tenant's configurable
        # creditor-group list (default: Sundry Creditors + Dealer Deposit +
        # Unsecured Loans + Non Current Liability). The legacy `creditors`
        # collection is kept as a secondary source for backwards compatibility.
        try:
            from routes.creditors import _get_creditor_groups
            creditor_groups = await _get_creditor_groups(ctx.get("tenant_id", ""))
        except Exception:
            creditor_groups = ["Sundry Creditors", "Dealer Deposit", "Unsecured Loans", "Non Current Liability"]
        cust_lower = {(d.get("customer_name") or "").strip().lower() for d in debtors}
        derived_creditors = [
            {
                "creditor_name": l.get("name") or l.get("ledger_name") or "",
                "ledger_group": l.get("parent_group", ""),
                "outstanding_amount": float(l.get("closing_balance", 0) or 0),
                "opening_balance": float(l.get("opening_balance", 0) or 0),
            }
            for l in ledgers
            if l.get("parent_group") in creditor_groups
            and (l.get("name") or l.get("ledger_name") or "").strip().lower() not in cust_lower
        ]
        legacy_creditors = (
            await db.creditors.find(q, {"_id": 0}).to_list(2000)
            if "creditors" in await db.list_collection_names() else []
        )
        creditors = derived_creditors or legacy_creditors

        if not ledgers and not debtors:
            return APIResponse(success=True, data={
                "assets": [], "liabilities": [], "total_assets": 0, "total_liabilities": 0,
                "source": "empty",
                "message": "No ledger data synced yet. Run the desktop agent."
            })

        # FY → balance field selection
        from datetime import date as _date
        today = _date.today()
        today_fy_year = today.year if today.month >= 4 else today.year - 1
        today_fy = f"{today_fy_year}-{str(today_fy_year + 1)[-2:]}"
        req_fy = fy or today_fy
        use_opening = False
        notice = None
        if req_fy != today_fy:
            try:
                req_year = int(req_fy.split("-")[0])
                if req_year == today_fy_year - 1:
                    use_opening = True
                else:
                    use_opening = True
                    notice = f"Showing previous-FY balance for {req_fy} (older FYs not directly available — re-anchor by running the agent during that FY)."
            except Exception:
                pass
        bal_field = 'opening_balance' if use_opening else 'closing_balance'

        # Build dedup set: customers that are also in all_ledgers (we keep customers'
        # value and skip the all_ledgers duplicate)
        customer_names = {(d.get('customer_name') or '').strip().lower() for d in debtors}

        groups = {}  # key → {group, side, total, ledgers[]}

        def _add(side, key, label, name, parent, amount):
            if abs(amount) < 0.01:
                return
            if key not in groups:
                groups[key] = {'group': label, 'side': side, 'total': 0.0, 'ledgers': []}
            groups[key]['total'] += amount
            groups[key]['ledgers'].append({'name': name, 'parent_group': parent, 'amount': round(amount, 2)})

        # 1) Process all_ledgers
        for l in ledgers:
            name = l.get('ledger_name', '') or ''
            if name.strip().lower() in customer_names:
                continue  # customers collection is authoritative
            parent = l.get('parent_group', '') or ''
            side, key, label = _classify_parent(parent)
            if side in ('pl', 'unknown'):
                continue
            stored = safe_num(l.get(bal_field))
            display = stored if side == 'liability' else -stored  # flip sign for assets
            _add(side, key, label, name, parent, display)

        # 1b) Closing Stock (from inventory_items, if values are synced)
        inv_items = await db.inventory_items.find(q, {"_id": 0, "item_name": 1, "stock_group": 1, "opening_value": 1, "closing_value": 1}).to_list(50000)
        stock_field = 'opening_value' if use_opening else 'closing_value'
        stock_total = 0.0
        stock_synced = False
        for it in inv_items:
            v = safe_num(it.get(stock_field))
            if abs(v) > 0.01:
                stock_synced = True
                _add('asset', 'stock_in_hand', 'Stock-in-Hand',
                     it.get('item_name', ''), it.get('stock_group', 'Stock-in-Hand'), v)
                stock_total += v
        # Roll up stock items into a single line if too many (>10) — keep top 10 + total row
        if 'stock_in_hand' in groups and len(groups['stock_in_hand']['ledgers']) > 50:
            top = sorted(groups['stock_in_hand']['ledgers'], key=lambda x: -abs(x['amount']))[:50]
            groups['stock_in_hand']['ledgers'] = top

        # 2) Sundry Debtors — from customers collection (authoritative)
        for d in debtors:
            stored = safe_num(d.get(bal_field if use_opening else 'outstanding_amount'))
            # customers store outstanding_amount in DR-positive (already flipped).
            # opening_balance in customers also stored DR-positive.
            _add('asset', 'sundry_debtors', 'Sundry Debtors',
                 d.get('customer_name', ''),
                 d.get('ledger_group', 'Sundry Debtors'), stored)

        # 3) Sundry Creditors — from creditors collection if present
        for c in creditors:
            stored = safe_num(c.get(bal_field if use_opening else 'outstanding_amount'))
            display = abs(stored) if stored != 0 else 0  # creditors are CR-natural; show as +ve liability
            _add('liability', 'sundry_creditors', 'Sundry Creditors',
                 c.get('creditor_name', ''),
                 c.get('ledger_group', 'Sundry Creditors'), display)

        # 4) Synthesize Profit & Loss A/c.
        # Tally stores the current-FY net profit in the `profit_loss` collection
        # (fetched by the agent from Tally's BS report) — that's the authoritative
        # value for "Current Period". For "Opening Balance" we take the residual
        # so TA = TL holds (mirrors Tally's own balancing behaviour — Opening
        # Balance of P&L A/c is the accumulated prior-year retained earnings).
        pl_doc = await db.profit_loss.find_one({"tenant_id": q.get("tenant_id", ""),
                                                 "company_id": q.get("company_id", "")},
                                                {"_id": 0})
        stored_net = safe_num((pl_doc or {}).get("net_profit_loss")) if pl_doc else 0.0
        if use_opening:
            # Prev FY view: Tally's master OB does not include current-period P&L
            # so just leave the residual to a single P&L A/c row (Opening Balance).
            current_period = 0.0
        else:
            try:
                current_period = stored_net if abs(stored_net) >= 0.01 else await _compute_pl_net_profit(q, req_fy)
            except Exception as e:
                logger.warning(f"BS: P&L compute failed: {e}")
                current_period = stored_net

        # Compute totals BEFORE adding P&L A/c so we know the residual
        ta_partial = round(sum(g['total'] for g in groups.values() if g['side'] == 'asset'), 2)
        tl_others = round(sum(g['total'] for g in groups.values() if g['side'] == 'liability'), 2)
        if abs(current_period) >= 0.01:
            _add('liability', 'profit_loss_ac', 'Profit & Loss A/c',
                 'Current Period', 'Profit & Loss A/c', current_period)
        # Opening Balance = residual that makes TA = TL (Tally's accounting identity)
        opening_balance = round(ta_partial - tl_others - current_period, 2)
        if abs(opening_balance) >= 0.01:
            _add('liability', 'profit_loss_ac', 'Profit & Loss A/c',
                 'Opening Balance', 'Profit & Loss A/c', opening_balance)

        # Sort groups & ledgers
        for g in groups.values():
            g['ledgers'].sort(key=lambda x: -abs(x['amount']))
            g['total'] = round(g['total'], 2)

        assets = sorted([g for g in groups.values() if g['side'] == 'asset'], key=lambda x: -abs(x['total']))
        liabilities = sorted([g for g in groups.values() if g['side'] == 'liability'], key=lambda x: -abs(x['total']))
        # Tally always lists the standard groups even if zero — sort liabilities in canonical order
        order_liab = ['capital_account', 'loans_liability', 'current_liabilities', 'sundry_creditors', 'suspense', 'non_current_liability', 'profit_loss_ac']
        order_asset = ['fixed_assets', 'investments', 'current_assets', 'stock_in_hand', 'sundry_debtors', 'misc_expense', 'branch_division']

        def _ordered(items, order, side):
            keyed = {}
            for it in items:
                # key = lookup in groups dict
                for k, g in groups.items():
                    if g is it:
                        keyed[k] = it
                        break
            out = []
            for k in order:
                if k in keyed:
                    out.append(keyed[k])
            for k, v in keyed.items():
                if k not in order:
                    out.append(v)
            return out

        assets = _ordered(assets, order_asset, 'asset')
        liabilities = _ordered(liabilities, order_liab, 'liability')

        total_assets = round(sum(g['total'] for g in assets), 2)
        total_liabilities = round(sum(g['total'] for g in liabilities), 2)
        difference = round(total_assets - total_liabilities, 2)

        # User-friendly notices about data freshness
        notices = []
        if notice:
            notices.append(notice)
        if not stock_synced:
            notices.append("Stock-in-Hand not yet synced. Re-run the Tally Desktop Agent (v9.5+) to capture closing stock values.")
        if not creditors and not any(g.get('group') == 'Sundry Creditors' for g in liabilities):
            notices.append("Sundry Creditors not yet synced. Re-run the Tally Desktop Agent (v9.5+) to capture supplier balances.")

        return APIResponse(success=True, data={
            "fy": req_fy,
            "view": "opening" if use_opening else "closing",
            "assets": assets,
            "liabilities": liabilities,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "difference": difference,
            "source": "derived_from_all_ledgers",
            "notice": " ".join(notices) if notices else None,
            "notices": notices,
            "ledger_count": len(ledgers),
            "debtor_count": len(debtors),
            "creditor_count": len(creditors),
            "stock_synced": stock_synced,
        })
    except Exception as e:
        logger.exception(f"Balance sheet error: {e}")
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
