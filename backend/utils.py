from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import WebSocket
import json
import logging
import re

logger = logging.getLogger(__name__)


# ── Fuzzy / normalized search helpers ──────────────────────────────────────
# Tally records (and user input) inconsistently use spaces, dashes, slashes,
# parens, dots, ampersands, underscores, quotes. Searches must match
# regardless of these separators so e.g. "tvs 10" matches "TVS-10",
# "TVS(10)", "TVS/10", "TVS.10", etc.
FUZZY_IGNORE_CHARS = r" \t\-\/\(\)!:\.\,\&\_\'\""
_FUZZY_STRIP_RE = re.compile(f"[{FUZZY_IGNORE_CHARS}]+")


def fuzzy_normalize(s: str) -> str:
    """Strip ignorable separator characters and lowercase the string."""
    if not s:
        return ""
    return _FUZZY_STRIP_RE.sub("", str(s)).lower()


def build_fuzzy_regex(term: str) -> str:
    """Build a Mongo-compatible $regex pattern that matches `term` while
    ignoring spaces and separator characters in BOTH the search input
    and the stored value.

    Example: 'tvs 10' → 'tvs[ \\-\\/\\(\\)!:\\.\\,\\&\\_\\\'\\"]*1[ \\-…]*0'
    Match is anchored as substring (no ^/$) and is case-insensitive when
    used with Mongo's `$options: "i"`.
    """
    if not term or not str(term).strip():
        return ""
    clean = _FUZZY_STRIP_RE.sub("", str(term))
    if not clean:
        return ""
    sep = f"[{FUZZY_IGNORE_CHARS}]*"
    # Escape each char (regex metachars in the input become literals) and
    # join with the optional separator pattern.
    return sep.join(re.escape(ch) for ch in clean)


def fuzzy_match(haystack: str, needle: str) -> bool:
    """Python-side fuzzy substring match (used when filtering already-loaded
    Python lists). Both sides are normalized before substring check."""
    if not needle:
        return True
    return fuzzy_normalize(needle) in fuzzy_normalize(haystack)


def safe_num(val, default=0):
    """Return numeric value or default if None/non-numeric."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def get_jv_party_amount(jv):
    """Extract the party-specific debit/credit from a journal voucher.

    JV documents store total voucher amounts in debit_amount/credit_amount,
    but for outstanding calculations we need only the amount belonging to
    the specific party_name. This is found inside ledger_entries.

    Returns (debit, credit) tuple for the party.

    Logic priority:
      1. If a ledger_entry has explicit `dr_or_cr` / `is_debit` / signed `amount`,
         honour it (post-agent-update behaviour).
      2. Else, infer from the OTHER ledger entries — for a Sundry Debtor party,
         if the other side is an income/charge ledger, customer is debited
         (interest charged), if it's a bank/cash ledger, customer is credited
         (refund/payment).
      3. Final fallback: assume Sundry Debtor JVs DEBIT the customer
         (increase outstanding) — this matches typical Indian SME practice
         where JVs against debtors are mostly interest charges or late fees.
    """
    party = (jv.get('party_name') or '').lower().strip()
    entries = jv.get('ledger_entries') or []
    party_amt = 0.0
    party_entry = None
    other_entries = []

    for e in entries:
        ln = (e.get('ledger_name') or '').lower().strip()
        if ln == party:
            party_amt = float(e.get('amount') or 0)
            party_entry = e
        else:
            other_entries.append(e)

    # Fallback amount if party not found in entries
    if party_amt == 0 and entries:
        total = float(jv.get('credit_amount') or jv.get('debit_amount') or 0)
        party_amt = total / max(len(entries), 1)

    # Priority 1: explicit per-entry direction (post-agent-update)
    if party_entry is not None:
        dc = (party_entry.get('dr_or_cr') or party_entry.get('drCr') or '').lower().strip()
        if dc in ('dr', 'debit'):
            return party_amt, 0.0
        if dc in ('cr', 'credit'):
            return 0.0, party_amt
        # Signed-amount convention: positive=DR, negative=CR
        raw_amt = e_raw = party_entry.get('amount')
        try:
            if isinstance(raw_amt, (int, float)) and raw_amt < 0:
                return 0.0, abs(float(raw_amt))
            if 'is_debit' in party_entry:
                if party_entry['is_debit'] is True:
                    return party_amt, 0.0
                if party_entry['is_debit'] is False:
                    return 0.0, party_amt
        except Exception:
            pass

    # Priority 2: heuristic from other entry's ledger group/name
    INCOME_KEYS = {'interest', 'penalty', 'late', 'charge', 'fees', 'discount allowed'}
    PAYMENT_KEYS = {'bank', 'cash', 'hdfc', 'sbi', 'icici', 'axis', 'kotak', 'payable'}
    if other_entries:
        other_name = (other_entries[0].get('ledger_name') or '').lower()
        if any(k in other_name for k in INCOME_KEYS):
            return party_amt, 0.0  # Interest charged → DR customer
        if any(k in other_name for k in PAYMENT_KEYS):
            return 0.0, party_amt  # Bank to customer → CR customer (refund)

    # Priority 3: final fallback — assume DR (most JVs against debtors increase balance)
    return party_amt, 0.0


def safe_str(val, default=""):
    """Return string value or default if None."""
    return str(val) if val is not None else default


def fy_to_date_range(fy: str):
    """Convert '2025-26' to ('2025-04-01', '2026-03-31')"""
    if not fy or '-' not in fy:
        return None, None
    parts = fy.split('-')
    start_year = int(parts[0])
    end_year_short = int(parts[1])
    end_year = start_year // 100 * 100 + end_year_short if end_year_short < 100 else end_year_short
    return f"{start_year}-04-01", f"{end_year}-03-31"


def filter_vouchers_by_fy(vouchers, fy):
    """Filter vouchers by financial year date range"""
    if not fy:
        return vouchers
    fy_start, fy_end = fy_to_date_range(fy)
    if not fy_start:
        return vouchers
    return [v for v in vouchers if fy_start <= v.get('voucher_date', '') <= fy_end]


def get_previous_fy(fy: str):
    """Given '2025-26', returns '2024-25'"""
    if not fy or '-' not in fy:
        return None
    parts = fy.split('-')
    start_year = int(parts[0])
    end_short = int(parts[1])
    prev_start = start_year - 1
    prev_end = end_short - 1 if end_short > 0 else 99
    return f"{prev_start}-{str(prev_end).zfill(2)}"


def get_current_fy():
    """Return current FY string e.g. '2025-26'. FY runs Apr-Mar."""
    from datetime import date as date_type
    today = date_type.today()
    if today.month >= 4:
        return f"{today.year}-{str(today.year + 1)[-2:]}"
    else:
        return f"{today.year - 1}-{str(today.year)[-2:]}"


def is_fy_completed(fy: str):
    """Check if a given FY has ended (past Mar 31 of end year)."""
    from datetime import date as date_type
    if not fy or '-' not in fy:
        return False
    _, fy_end = fy_to_date_range(fy)
    if not fy_end:
        return False
    try:
        parts = fy_end.split('-')
        end_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        return date_type.today() > end_date
    except (ValueError, IndexError):
        return False


OVERDUE_THRESHOLD_DAYS = 55


async def compute_overdue_digest(db_ref, tenant_id=None, company_id=None, branch_parties=None):
    """Compute overdue invoices (>55 days from invoice date) considering receipts,
    credit notes, and journal vouchers. Stores result in overdue_digest collection."""
    from datetime import date as date_type

    today = date_type.today()

    q = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if company_id:
        q["company_id"] = company_id

    sales = await db_ref.sales_vouchers.find(q, {"_id": 0}).to_list(20000)
    receipts_raw = await db_ref.receipt_vouchers.find(q, {"_id": 0}).to_list(20000)
    # The receipt_vouchers collection actually contains ALL bank/cash movements
    # for a party — receipts (CR party, reduce outstanding) AND payments
    # (DR party, e.g., refunds, bounce-cheque returns, commissions paid).
    # Tally voucher types we've observed:
    #   • app cash receipts / bank receipt / cash receipt / receipt → RECEIPT
    #   • bank payment / cash payment / payment → PAYMENT (we paid the party — must NOT reduce overdue)
    #   • cheque return voucher / dishonour → already reverses a prior receipt — exclude
    # Pre-fix bug: only `voucher_type == "payment"` was excluded, so ~2.7k
    # `bank payment` entries (₹7+ crore) were silently subtracted from the
    # customer's overdue balance — driving most overdue customers to zero.
    def _is_real_receipt(v):
        t = (v.get("voucher_type") or "").strip().lower()
        if not t:
            # Empty type → trust it as a receipt (legacy behaviour)
            return True
        if "payment" in t:
            return False                       # any *payment voucher
        if "return" in t or "dishonour" in t or "bounce" in t:
            return False                       # cheque return / dishonour
        return True                             # everything else (incl. *receipt)
    receipts = [v for v in receipts_raw if _is_real_receipt(v)]
    credit_notes = await db_ref.credit_notes.find(q, {"_id": 0}).to_list(20000)
    journals = await db_ref.journal_vouchers.find(q, {"_id": 0}).to_list(20000)
    synced_customers = await db_ref.customers.find(q, {"_id": 0}).to_list(5000)

    # Apply branch exclusion if provided
    if branch_parties:
        bp_lower = set(p.lower().strip() for p in branch_parties)
        sales = [v for v in sales if (v.get("party_name") or "").lower().strip() not in bp_lower]
        receipts = [v for v in receipts if (v.get("party_name") or "").lower().strip() not in bp_lower]
        credit_notes = [v for v in credit_notes if (v.get("party_name") or "").lower().strip() not in bp_lower]
        journals = [v for v in journals if (v.get("party_name") or "").lower().strip() not in bp_lower]
        synced_customers = [c for c in synced_customers if safe_str(c.get("customer_name")).lower().strip() not in bp_lower]

    synced_map = {safe_str(c.get("customer_name")).lower(): c for c in synced_customers if c.get("customer_name")}

    # Build per-customer credit totals (receipts + credit notes + journal credits)
    customer_credits = {}
    receipt_bill_allocs = {}

    for r in receipts:
        party = safe_str(r.get("party_name")).strip()
        if not party:
            continue
        amt = safe_num(r.get("amount"))
        customer_credits[party] = customer_credits.get(party, 0) + amt
        for alloc in r.get("bill_allocations", []):
            bill_ref = safe_str(alloc.get("bill_ref", alloc.get("name", ""))).strip()
            alloc_amt = safe_num(alloc.get("amount"))
            key = party.lower()
            if key not in receipt_bill_allocs:
                receipt_bill_allocs[key] = {}
            receipt_bill_allocs[key][bill_ref] = receipt_bill_allocs[key].get(bill_ref, 0) + alloc_amt

    for cn in credit_notes:
        party = safe_str(cn.get("party_name")).strip()
        if not party:
            continue
        customer_credits[party] = customer_credits.get(party, 0) + safe_num(cn.get("total_amount"))

    for jv in journals:
        party = safe_str(jv.get("party_name")).strip()
        if not party:
            continue
        _, credit_amt = get_jv_party_amount(jv)
        if credit_amt > 0:
            customer_credits[party] = customer_credits.get(party, 0) + credit_amt

    overdue_invoices = []
    customer_overdue = {}

    for v in sales:
        v_date_str = v.get("voucher_date", "")
        if not v_date_str:
            continue
        try:
            parts = v_date_str.split("-")
            if len(parts) != 3:
                continue
            v_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, TypeError):
            continue

        days_old = (today - v_date).days
        if days_old <= OVERDUE_THRESHOLD_DAYS:
            continue

        party = v.get("party_name", "Unknown")
        invoice_amt = safe_num(v.get("total_amount"))
        voucher_id = v.get("voucher_id", "")
        ref_number = v.get("reference_number", voucher_id)

        # Check bill-level allocation first
        paid_for_invoice = 0
        allocs = receipt_bill_allocs.get(party.lower(), {})
        if ref_number and ref_number in allocs:
            paid_for_invoice = allocs[ref_number]
        elif voucher_id and voucher_id in allocs:
            paid_for_invoice = allocs[voucher_id]

        remaining = invoice_amt - paid_for_invoice
        if remaining <= 0:
            continue

        overdue_invoices.append({
            "voucher_id": voucher_id,
            "reference_number": ref_number,
            "party_name": party,
            "voucher_date": v_date_str,
            "invoice_amount": round(invoice_amt, 2),
            "paid_amount": round(paid_for_invoice, 2),
            "overdue_amount": round(remaining, 2),
            "days_overdue": days_old,
        })

        if party not in customer_overdue:
            synced = synced_map.get(party.lower(), {})
            customer_overdue[party] = {
                "customer_name": party,
                "phone": synced.get("phone", ""),
                "total_overdue": 0,
                "invoice_count": 0,
                "oldest_days": 0,
            }
        customer_overdue[party]["total_overdue"] += remaining
        customer_overdue[party]["invoice_count"] += 1
        if days_old > customer_overdue[party]["oldest_days"]:
            customer_overdue[party]["oldest_days"] = days_old

    # Apply remaining credits (not bill-allocated) — FIFO by oldest invoice
    customer_invoices_map = {}
    for inv in overdue_invoices:
        customer_invoices_map.setdefault(inv["party_name"], []).append(inv)

    for party, invoices in customer_invoices_map.items():
        total_credits = customer_credits.get(party, 0)
        # Subtract already-allocated bill amounts
        already_allocated = sum(inv["paid_amount"] for inv in invoices)
        remaining_credits = total_credits - already_allocated
        if remaining_credits <= 0:
            continue
        invoices.sort(key=lambda x: x["days_overdue"], reverse=True)
        for inv in invoices:
            if remaining_credits <= 0:
                break
            payoff = min(inv["overdue_amount"], remaining_credits)
            inv["paid_amount"] += payoff
            inv["overdue_amount"] -= payoff
            remaining_credits -= payoff

    overdue_invoices = [inv for inv in overdue_invoices if inv["overdue_amount"] > 0.5]

    # ── SOURCE OF TRUTH GUARD: drop overdue records for customers whose actual
    # Tally closing balance shows zero/negative outstanding. This prevents stale
    # invoices from appearing as "overdue" when receipts/JVs aren't bill-allocated
    # but the books are square (e.g., Abhishek Auto Parts paid in full but the
    # voucher-level allocation isn't synced).
    sundry_balance_map = {}
    for sc in synced_customers:
        nm = (sc.get("customer_name") or "").strip().lower()
        if nm:
            sundry_balance_map[nm] = safe_num(sc.get("outstanding_amount"))
    overdue_invoices = [
        inv for inv in overdue_invoices
        if sundry_balance_map.get((inv["party_name"] or "").strip().lower(), 0) > 0.5
    ]

    # Rebuild customer summary after credit adjustments
    customer_overdue = {}
    for inv in overdue_invoices:
        party = inv["party_name"]
        if party not in customer_overdue:
            synced = synced_map.get(party.lower(), {})
            customer_overdue[party] = {
                "customer_name": party,
                "phone": synced.get("phone", ""),
                "total_overdue": 0,
                "invoice_count": 0,
                "oldest_days": 0,
            }
        customer_overdue[party]["total_overdue"] += inv["overdue_amount"]
        customer_overdue[party]["invoice_count"] += 1
        if inv["days_overdue"] > customer_overdue[party]["oldest_days"]:
            customer_overdue[party]["oldest_days"] = inv["days_overdue"]

    for c in customer_overdue.values():
        c["total_overdue"] = round(c["total_overdue"], 2)

    overdue_invoices.sort(key=lambda x: x["days_overdue"], reverse=True)

    # ── TALLY-ALIGNED AGING (Feb 2026 fix) ──────────────────────────────
    # The voucher-by-voucher reconstruction above misses any unpaid
    # invoices from PRIOR financial years (those exist as
    # `customers.opening_balance` in the synced master, not as raw vouchers
    # in our DB). Tally's aging report covers BOTH — that's why the
    # screenshot shows ₹65 lakh / 199 customers when our app showed only
    # ₹1.7L / 15 customers.
    #
    # Tally-aligned algorithm using `customers.outstanding_amount` as the
    # source of truth, with FIFO assumption (receipts pay oldest first):
    #   recent_unpaid_cap = Σ sales_vouchers ≤ 55 days for this customer
    #   overdue           = max(0, outstanding_amount - recent_unpaid_cap)
    # If the customer has no recent sales, ALL of their outstanding (incl.
    # opening balance) is overdue — exactly what Tally's aging shows.
    cutoff_date = today - timedelta(days=OVERDUE_THRESHOLD_DAYS)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    recent_invoice_sum = {}   # party_lower → Σ sales within 55d
    recent_receipt_sum = {}   # party_lower → Σ receipts within 55d (real-receipts filter)
    customer_oldest_inv = {}  # party_lower → oldest sales date (any age)
    for v in sales:
        party = safe_str(v.get("party_name")).strip()
        if not party:
            continue
        v_date_str = v.get("voucher_date") or v.get("date") or ""
        amt = safe_num(v.get("total_amount"))
        if amt <= 0:
            continue
        if v_date_str and v_date_str >= cutoff_str:
            recent_invoice_sum[party.lower()] = recent_invoice_sum.get(party.lower(), 0) + amt
        if v_date_str:
            cur_oldest = customer_oldest_inv.get(party.lower())
            if cur_oldest is None or v_date_str < cur_oldest:
                customer_oldest_inv[party.lower()] = v_date_str
    for r in receipts:  # already filtered by _is_real_receipt above
        party = safe_str(r.get("party_name")).strip()
        if not party:
            continue
        v_date_str = r.get("voucher_date") or r.get("date") or ""
        if v_date_str and v_date_str >= cutoff_str:
            recent_receipt_sum[party.lower()] = recent_receipt_sum.get(party.lower(), 0) + safe_num(r.get("amount"))

    customer_summary = []
    for sc in synced_customers:
        name = (sc.get("customer_name") or "").strip()
        if not name:
            continue
        outstanding = safe_num(sc.get("outstanding_amount"))
        if outstanding <= 0.5:
            continue
        # FIFO assumption: receipts pay oldest first. So the "still recent
        # and possibly unpaid" cap = recent_invoices − recent_receipts
        # (lower bound when no bill allocations are available).
        recent_inv = recent_invoice_sum.get(name.lower(), 0)
        recent_recpt = recent_receipt_sum.get(name.lower(), 0)
        recent_unpaid_cap = max(0, recent_inv - recent_recpt)
        overdue_amt = outstanding - recent_unpaid_cap
        if overdue_amt <= 0.5:
            continue

        # Oldest-days: prefer the actual oldest unpaid invoice date in DB.
        # If no current-FY invoices exist (entire dues = opening balance),
        # mark as 365+ days (proxy for "previous FY balance").
        oldest_days = 365
        oldest_date_str = customer_oldest_inv.get(name.lower())
        if oldest_date_str:
            try:
                parts = oldest_date_str.split("-")
                if len(parts) == 3:
                    od = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    oldest_days = max(oldest_days if recent_unpaid_cap >= outstanding else 0,
                                       (today - od).days)
            except Exception:
                pass

        customer_summary.append({
            "customer_name": name,
            "phone": sc.get("phone", ""),
            "total_overdue": round(overdue_amt, 2),
            "invoice_count": 0,  # bill-level reconstruction unavailable here
            "oldest_days": oldest_days,
        })

    customer_summary.sort(key=lambda c: c["total_overdue"], reverse=True)

    # Total overdue from the Tally-aligned customer-level aging — this is
    # the headline number the dashboard surfaces. The voucher-level list
    # below is kept for drill-down when bill-allocations ARE available.
    total_overdue = round(sum(c["total_overdue"] for c in customer_summary), 2)

    digest = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "threshold_days": OVERDUE_THRESHOLD_DAYS,
        "total_overdue_amount": total_overdue,
        "total_overdue_invoices": len(overdue_invoices),
        "total_customers_overdue": len(customer_summary),
        "customer_summary": customer_summary[:20],
        "overdue_invoices": overdue_invoices[:50],
    }

    digest_filter = {"_type": "latest"}
    if tenant_id:
        digest["tenant_id"] = tenant_id
        digest_filter["tenant_id"] = tenant_id
    if company_id:
        digest["company_id"] = company_id
        digest_filter["company_id"] = company_id

    # Only cache the unfiltered (no branch exclusion) result
    if not branch_parties:
        await db_ref.overdue_digest.update_one(
            digest_filter,
            {"$set": {**digest, "_type": "latest"}},
            upsert=True
        )

    return digest


class SyncWebSocketManager:
    """Manages WebSocket connections for real-time sync status updates.

    Each connected client is associated with a tenant_id (sent by the client
    on connect via {action:'subscribe', tenant_id:...}). Broadcasts honour
    that scope so a sync running on tenant A never leaks to tenant B's UI.
    """

    def __init__(self):
        # connection -> tenant_id (None = unscoped, used only for super-admin tools)
        self.active_connections: dict = {}
        # last progress payload per tenant_id (so a freshly-connected client
        # gets the current state without waiting for the next broadcast)
        self.last_progress_by_tenant: dict = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = None
        logger.info(f"WebSocket client connected ({len(self.active_connections)} total)")

    def set_tenant(self, websocket: WebSocket, tenant_id: str):
        if websocket in self.active_connections:
            self.active_connections[websocket] = tenant_id
            # Replay last known progress for this tenant
            last = self.last_progress_by_tenant.get(tenant_id)
            if last:
                try:
                    import asyncio
                    asyncio.create_task(websocket.send_text(json.dumps(last)))
                except Exception:
                    pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.pop(websocket, None)
        logger.info(f"WebSocket client disconnected ({len(self.active_connections)} total)")

    async def broadcast(self, message: dict, tenant_id: str = None):
        """Send to clients matching tenant_id. If tenant_id is falsy, the
        broadcast is treated as un-scoped (legacy callers — kept for
        backwards-compat but discouraged). Caller SHOULD always pass tenant_id.
        """
        if tenant_id:
            self.last_progress_by_tenant[tenant_id] = message
        disconnected = []
        for connection, conn_tenant in list(self.active_connections.items()):
            # Only deliver to clients that have subscribed to this tenant.
            # Clients whose tenant is unknown (null) get nothing — prevents
            # leaks during the brief window before the client subscribes.
            if tenant_id and conn_tenant and conn_tenant != tenant_id:
                continue
            if tenant_id and not conn_tenant:
                # client hasn't subscribed yet — don't leak across tenants
                continue
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = SyncWebSocketManager()
