"""Insider Result routes — advanced analytics for customer lifecycle, forecasting, SPIP, and concentration risk."""
from fastapi import APIRouter, Request
from typing import Optional
from datetime import datetime, timezone, date as date_type, timedelta
from collections import defaultdict
import logging

from db import db
from models import APIResponse
from services.tenant_context import get_tenant_context
from utils import filter_vouchers_by_fy
from routes.branch_ledgers import get_branch_parties

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_query(ctx, company_id=None):
    """Build tenant+company filter."""
    if not ctx:
        return {}
    f = {}
    tid = ctx.get("tenant_id")
    if tid:
        f["tenant_id"] = tid
    cid = company_id or ctx.get("company_id")
    if cid:
        f["company_id"] = cid
    return f


async def _get_branch_exclusion(request, ctx):
    """Check header and return list of branch party names to exclude."""
    if request.headers.get("X-Exclude-Branches", "").lower() == "true":
        return await get_branch_parties(ctx.get("tenant_id", ""), ctx.get("company_id", ""))
    return []


def _exclude_branch_vouchers(vouchers, branch_parties):
    """Filter out vouchers belonging to branch parties."""
    if not branch_parties:
        return vouchers
    bp_set = set(branch_parties)
    return [v for v in vouchers if v.get("party_name") not in bp_set]


# ===================== 1. CUSTOMER LIFECYCLE =====================

@router.get("/insights/customer-lifecycle")
async def get_customer_lifecycle(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Classify customers as Active/Inactive/Lost based on last transaction date."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)
        today = date_type.today()

        vouchers = await db.sales_vouchers.find(q, {"_id": 0, "party_name": 1, "voucher_date": 1, "amount": 1, "total_amount": 1}).to_list(20000)
        bp = await _get_branch_exclusion(request, ctx)
        vouchers = _exclude_branch_vouchers(vouchers, bp)
        if fy:
            vouchers = filter_vouchers_by_fy(vouchers, fy)

        customer_data = defaultdict(lambda: {"dates": [], "total": 0, "count": 0})
        for v in vouchers:
            party = v.get("party_name", "")
            if not party:
                continue
            d = v.get("voucher_date", "")
            amt = v.get("total_amount") or v.get("amount") or 0
            customer_data[party]["dates"].append(d)
            customer_data[party]["total"] += abs(float(amt)) if amt else 0
            customer_data[party]["count"] += 1

        active, inactive, lost = [], [], []
        for name, data in customer_data.items():
            dates_sorted = sorted([d for d in data["dates"] if d], reverse=True)
            last_date = dates_sorted[0] if dates_sorted else ""
            first_date = dates_sorted[-1] if dates_sorted else ""

            days_since = 999
            if last_date:
                try:
                    # v1.5.7 — Busy agent stores voucher_date as
                    # "YYYY-MM-DD 00:00:00" (with time suffix). The old
                    # split('-') pattern turned "01 00:00:00" into a
                    # non-numeric third part → ValueError → days_since
                    # stayed 999 → every customer flipped to LOST for
                    # every Busy tenant. Normalise to the first 10 chars.
                    parts = last_date[:10].split("-")
                    ld = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_since = (today - ld).days
                except (ValueError, IndexError):
                    pass

            status = "lost" if days_since > 180 else ("inactive" if days_since > 90 else "active")
            entry = {
                "customer_name": name,
                "status": status,
                "last_transaction": last_date,
                "first_transaction": first_date,
                "days_since_last": days_since,
                "total_revenue": round(data["total"], 2),
                "transaction_count": data["count"],
            }

            if status == "active":
                active.append(entry)
            elif status == "inactive":
                inactive.append(entry)
            else:
                lost.append(entry)

        # Monthly trend (last 12 months)
        monthly_counts = defaultdict(lambda: {"active": 0, "inactive": 0, "lost": 0})
        for m_offset in range(12):
            d = today - timedelta(days=m_offset * 30)
            month_key = d.strftime("%Y-%m")
            for name, data in customer_data.items():
                month_dates = [dt for dt in data["dates"] if dt and dt.startswith(month_key)]
                if month_dates:
                    monthly_counts[month_key]["active"] += 1

        trend = [{"month": k, **v} for k, v in sorted(monthly_counts.items())]

        return APIResponse(success=True, data={
            "active": sorted(active, key=lambda x: x["total_revenue"], reverse=True),
            "inactive": sorted(inactive, key=lambda x: x["total_revenue"], reverse=True),
            "lost": sorted(lost, key=lambda x: x["total_revenue"], reverse=True),
            "summary": {
                "active_count": len(active),
                "inactive_count": len(inactive),
                "lost_count": len(lost),
                "active_revenue": round(sum(c["total_revenue"] for c in active), 2),
                "inactive_revenue": round(sum(c["total_revenue"] for c in inactive), 2),
                "lost_revenue": round(sum(c["total_revenue"] for c in lost), 2),
            },
            "trend": trend[-12:]
        })
    except Exception as e:
        logger.error(f"Customer lifecycle error: {e}")
        return APIResponse(success=False, error=str(e))


# ===================== 2. SALES FORECASTING =====================

@router.get("/insights/sales-forecast")
async def get_sales_forecast(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Sales trend with seasonality-aware forecast.

    Forecast philosophy (v2 — addresses user feedback "forecast has to
    project based on previous FY"):
      - For the selected FY, build a 12-month timeline (Apr…Mar).
      - For each FUTURE month within the selected FY (months after
        end-of-data), forecast = same-month-last-FY × growth_trend.
      - growth_trend = (current-FY-to-date revenue) / (same-period-last-FY
        revenue) — captures whether the user is up/down vs last year.
      - When same-month-last-FY data isn't available, fall back to
        weighted moving average (60% MA-3 + 40% MA-6) of recent months.
      - Forecast confidence: high if >= 12 months of data AND last-FY
        same-month exists; medium if MA-fallback; low if MA-3 only.
    """
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        # Pull ALL vouchers (no FY filter) — we need cross-FY data for
        # seasonality + multi-FY YoY summary.
        all_vouchers = await db.sales_vouchers.find(q, {"_id": 0, "voucher_date": 1, "amount": 1, "total_amount": 1, "party_name": 1}).to_list(80000)
        bp = await _get_branch_exclusion(request, ctx)
        all_vouchers = _exclude_branch_vouchers(all_vouchers, bp)

        # Helper: month_key "YYYY-MM" → FY label "YYYY-YY"
        def _fy_for_month(month_key: str) -> str:
            yyyy = int(month_key[:4])
            mm = int(month_key[5:7])
            fy_year = yyyy if mm >= 4 else yyyy - 1
            return f"{fy_year}-{str(fy_year + 1)[-2:]}"

        # ── 1. Build the all-time monthly aggregate (for seasonality lookup) ──
        all_monthly = defaultdict(lambda: {"revenue": 0, "count": 0, "customers": set()})
        for v in all_vouchers:
            d = v.get("voucher_date", "")
            if not d:
                continue
            month = d[:7]
            amt = v.get("total_amount") or v.get("amount") or 0
            all_monthly[month]["revenue"] += abs(float(amt)) if amt else 0
            all_monthly[month]["count"] += 1
            party = v.get("party_name", "")
            if party:
                all_monthly[month]["customers"].add(party)

        # ── 2. Filter to the selected FY for the timeline + forecast horizon ──
        if fy:
            sel_vouchers = filter_vouchers_by_fy(all_vouchers, fy)
        else:
            sel_vouchers = all_vouchers
        monthly_sales = defaultdict(lambda: {"revenue": 0, "count": 0, "customers": set()})
        for v in sel_vouchers:
            d = v.get("voucher_date", "")
            if not d:
                continue
            month = d[:7]
            amt = v.get("total_amount") or v.get("amount") or 0
            monthly_sales[month]["revenue"] += abs(float(amt)) if amt else 0
            monthly_sales[month]["count"] += 1
            party = v.get("party_name", "")
            if party:
                monthly_sales[month]["customers"].add(party)

        months_sorted = sorted(monthly_sales.keys())
        timeline = []
        for m in months_sorted:
            d = monthly_sales[m]
            timeline.append({
                "month": m,
                "revenue": round(d["revenue"], 2),
                "count": d["count"],
                "unique_customers": len(d["customers"]),
            })

        # ── 3. Seasonality-aware forecast for remaining months in selected FY ──
        revenues = [t["revenue"] for t in timeline]
        forecasts = []
        if revenues and fy:
            # Determine which months remain in the selected FY
            fy_year = int(fy.split("-")[0]) if "-" in fy else None
            if fy_year:
                fy_months = [f"{fy_year}-{m:02d}" for m in range(4, 13)] + \
                            [f"{fy_year + 1}-{m:02d}" for m in range(1, 4)]
                last_data_month = months_sorted[-1] if months_sorted else None
                future_months = [m for m in fy_months if m > (last_data_month or "0000-00")]

                # YoY growth trend across the FY-to-date
                ytd_curr = sum(all_monthly[m]["revenue"] for m in fy_months
                                if m in all_monthly and m <= (last_data_month or ""))
                prev_fy_year = fy_year - 1
                prev_fy_months = [f"{prev_fy_year}-{m:02d}" for m in range(4, 13)] + \
                                  [f"{prev_fy_year + 1}-{m:02d}" for m in range(1, 4)]
                # Same-period-last-FY = April through whatever the last data month's calendar month is
                if last_data_month:
                    n_months_so_far = len([m for m in fy_months if m <= last_data_month and m in all_monthly])
                    ytd_prev = sum(all_monthly[m]["revenue"] for m in prev_fy_months[:n_months_so_far]
                                    if m in all_monthly)
                else:
                    n_months_so_far = 0
                    ytd_prev = 0
                growth_trend = (ytd_curr / ytd_prev) if ytd_prev > 0 else 1.0
                # Cap trend in [0.5, 2.0] to avoid wild outlier amplification
                growth_trend = max(0.5, min(2.0, growth_trend))

                # MA fallback for months without prev-FY same-month data
                ma3 = sum(revenues[-3:]) / min(len(revenues), 3) if revenues else 0
                ma6 = sum(revenues[-6:]) / min(len(revenues), 6) if revenues else 0
                ma_blend = 0.6 * ma3 + 0.4 * ma6 if ma6 > 0 else ma3

                for fm in future_months:
                    # Same calendar month, previous FY: e.g. for "2026-04",
                    # look up "2025-04" (one year back).
                    prev_year_month = f"{int(fm[:4]) - 1}-{fm[5:]}"
                    prev_data = all_monthly.get(prev_year_month, {}).get("revenue", 0)
                    if prev_data > 0:
                        forecast_val = prev_data * growth_trend
                        confidence = "high" if len(revenues) >= 6 else "medium"
                    else:
                        forecast_val = ma_blend
                        confidence = "medium" if len(revenues) >= 6 else "low"
                    forecasts.append({
                        "month": fm,
                        "forecast_revenue": round(forecast_val, 2),
                        "confidence": confidence,
                        "based_on_prev_fy_month": prev_year_month if prev_data > 0 else None,
                        "growth_trend_pct": round((growth_trend - 1) * 100, 1) if prev_data > 0 else None,
                    })
        elif len(revenues) >= 3:
            # No FY selected — fall back to next-3-months forward MA forecast
            ma3 = sum(revenues[-3:]) / 3
            ma6 = sum(revenues[-6:]) / 6 if len(revenues) >= 6 else ma3
            base = 0.6 * ma3 + 0.4 * ma6
            today = date_type.today()
            for i in range(1, 4):
                fd = today.replace(day=1) + timedelta(days=32 * i)
                forecasts.append({
                    "month": fd.strftime("%Y-%m"),
                    "forecast_revenue": round(base, 2),
                    "confidence": "medium" if len(revenues) >= 6 else "low",
                    "based_on_prev_fy_month": None,
                    "growth_trend_pct": None,
                })

        # ── 4. Year-over-year — across ALL FYs (not just selected) ──
        # The previous code split by calendar year (2025 vs 2026), which
        # gave nonsensical "year" buckets when filtered to a single FY.
        # Now we group by Indian-FY label (2024-25, 2025-26, 2026-27).
        yoy_by_fy = defaultdict(lambda: {"revenue": 0, "count": 0})
        for m, d in all_monthly.items():
            fy_label = _fy_for_month(m)
            yoy_by_fy[fy_label]["revenue"] += d["revenue"]
            yoy_by_fy[fy_label]["count"] += d["count"]
        yoy_list = [{"year": k, "revenue": round(v["revenue"], 2), "count": v["count"]}
                     for k, v in sorted(yoy_by_fy.items())]

        # Month-vs-month cross-FY comparison (e.g. Apr 2025 vs Apr 2024 vs Apr 2023)
        # — uses the same `all_monthly` aggregate built above (no second DB
        # round-trip; the previous code re-fetched & re-aggregated needlessly).

        # Build comparison: group by month number (04=Apr, 05=May, etc.)
        month_comparison = defaultdict(list)  # {"04": [{"fy": "2024-25", "month": "2025-04", "revenue": ...}, ...]}
        for month_key, data in sorted(all_monthly.items()):
            mm = month_key[5:7]
            month_comparison[mm].append({
                "fy": _fy_for_month(month_key),
                "month": month_key,
                "revenue": round(data["revenue"], 2),
                "count": data["count"],
            })

        # Sort each month's entries by FY
        for mm in month_comparison:
            month_comparison[mm].sort(key=lambda x: x["fy"])

        month_names = {"04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec", "01": "Jan", "02": "Feb", "03": "Mar"}
        comparison_data = []
        for mm in ["04", "05", "06", "07", "08", "09", "10", "11", "12", "01", "02", "03"]:
            if mm in month_comparison:
                comparison_data.append({
                    "month_num": mm,
                    "month_name": month_names.get(mm, mm),
                    "data": month_comparison[mm]
                })

        return APIResponse(success=True, data={
            "timeline": timeline,
            "forecasts": forecasts,
            "yoy": yoy_list,
            "month_comparison": comparison_data,
            "summary": {
                "total_months": len(timeline),
                "avg_monthly_revenue": round(sum(revenues) / len(revenues), 2) if revenues else 0,
                "best_month": max(timeline, key=lambda t: t["revenue"])["month"] if timeline else "",
                "best_month_revenue": max(revenues) if revenues else 0,
            }
        })
    except Exception as e:
        logger.error(f"Sales forecast error: {e}")
        return APIResponse(success=False, error=str(e))


# ===================== 3. SPIP GAP ANALYSIS =====================

@router.get("/insights/spip-analysis")
async def get_spip_analysis(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None, window_months: int = 12):
    """SPIP (Stock-Performance / Inventory-Profile) analysis.

    Window selection (v3, addresses user feedback "perfect analysis"):
      - If `fy` is given AND has >= 6 months of data, use that FY.
      - Otherwise (FY too short or not given), use a rolling
        `window_months` window (default 12) anchored to the last synced
        voucher date — guarantees enough activity for monthly-average /
        months-of-stock math to be meaningful.

    Gap types:
      out_of_stock — sold > 0 in window AND stock_qty <= 0
      understocked — months_of_stock < 1 AND sold > 0
      dead_stock   — stock_qty > 0 AND sold == 0 in window (sitting)
      overstocked  — months_of_stock > 6
      balanced     — sold > 0, 1 <= months_of_stock <= 6
      no_movement  — stock_qty == 0 AND sold == 0 in window (item synced
                      but no transaction at all in the analysis window —
                      previously dumped into 'balanced' which confused
                      users)
    """
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        # Pull all sales (no FY filter yet) so we can detect the last
        # voucher date and pick the analysis window.
        all_sales = await db.sales_vouchers.find(q, {"_id": 0}).to_list(80000)
        bp = await _get_branch_exclusion(request, ctx)
        all_sales = _exclude_branch_vouchers(all_sales, bp)

        last_voucher_date = ""
        for v in all_sales:
            d = v.get("voucher_date", "")
            if d and d > last_voucher_date:
                last_voucher_date = d

        # Window selection
        window_meta = {"window_type": "fy", "window_label": fy or "all",
                        "window_start": "", "window_end": last_voucher_date}
        sales = all_sales
        if fy:
            sales = filter_vouchers_by_fy(all_sales, fy)
            distinct_months = {v.get("voucher_date", "")[:7] for v in sales if v.get("voucher_date")}
            if len(distinct_months) < 6 and last_voucher_date:
                from datetime import datetime as _dt
                end = _dt.strptime(last_voucher_date[:10], "%Y-%m-%d")
                wm = max(1, int(window_months))
                sy = end.year - (wm // 12); sm = end.month - (wm % 12)
                if sm <= 0:
                    sm += 12; sy -= 1
                start_date = end.replace(year=sy, month=sm, day=1)
                start_str = start_date.strftime("%Y-%m-%d")
                end_str = last_voucher_date[:10]
                sales = [v for v in all_sales if start_str <= (v.get("voucher_date") or "")[:10] <= end_str]
                window_meta = {
                    "window_type": "rolling",
                    "window_label": f"Last {wm} months (FY had only {len(distinct_months)} mo of data)",
                    "window_start": start_str, "window_end": end_str,
                }
        elif last_voucher_date:
            from datetime import datetime as _dt
            end = _dt.strptime(last_voucher_date[:10], "%Y-%m-%d")
            wm = max(1, int(window_months))
            sy = end.year - (wm // 12); sm = end.month - (wm % 12)
            if sm <= 0:
                sm += 12; sy -= 1
            start_date = end.replace(year=sy, month=sm, day=1)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = last_voucher_date[:10]
            sales = [v for v in all_sales if start_str <= (v.get("voucher_date") or "")[:10] <= end_str]
            window_meta = {
                "window_type": "rolling",
                "window_label": f"Last {wm} months",
                "window_start": start_str, "window_end": end_str,
            }

        # Get inventory items (no cap — KSC-size tenants have 7,500+ items;
        # the previous 5,000 cap silently dropped 2,500 items so they showed
        # as out_of_stock even when they had stock)
        inventory = await db.inventory_items.find(q, {"_id": 0}).to_list(None)

        # Build item-level analysis from sales (case/whitespace-normalised
        # so sales-voucher item names with stray spaces match inventory).
        item_sales = defaultdict(lambda: {"qty_sold": 0, "revenue": 0,
                                            "months_active": set(),
                                            "display_name": ""})
        for v in sales:
            items_list = v.get("items") or v.get("inventory_entries") or []
            date_str = v.get("voucher_date", "")
            month = date_str[:7] if date_str else ""
            for item in items_list:
                name = item.get("item_name") or item.get("stock_item_name") or item.get("item") or ""
                if not name:
                    continue
                key = name.strip().lower()
                qty = abs(float(item.get("quantity") or item.get("billed_qty") or 0))
                rate = float(item.get("rate", 0) or 0)
                amt = abs(float(item.get("amount") or 0)) or abs(rate * qty)
                item_sales[key]["qty_sold"] += qty
                item_sales[key]["revenue"] += amt
                if month:
                    item_sales[key]["months_active"].add(month)
                if not item_sales[key]["display_name"]:
                    item_sales[key]["display_name"] = name.strip()

        # Build inventory map keyed on the normalised name so cross-lookup
        # against sales works even when whitespace / case differs. Carry
        # part_number + aliases through so frontend can search globally.
        inv_map = {}
        for inv in inventory:
            name = inv.get("item_name", "")
            if name:
                key = name.strip().lower()
                inv_map[key] = {
                    "display_name": name.strip(),
                    "part_number": inv.get("part_number", "") or "",
                    "aliases": inv.get("aliases") or [],
                    "stock_qty": inv.get("quantity") or inv.get("closing_balance") or 0,
                    "stock_group": inv.get("stock_group", ""),
                    "purchase_price": inv.get("purchase_price") or inv.get("price") or 0,
                }

        # v1.5.7 — Only analyse items that exist in the inventory master.
        # The union with `item_sales.keys()` was inflating the total
        # count (14,061 vs 13,682 actual master items) whenever a
        # historic sales voucher referenced an item deleted from the
        # Busy master afterwards. Master-only keeps the SPIP tile's
        # total consistent with the Inventory menu total.
        analysis = []
        all_keys = set(inv_map.keys())
        for k in all_keys:
            s = item_sales.get(k, {"qty_sold": 0, "revenue": 0, "months_active": set(), "display_name": ""})
            inv = inv_map.get(k, {"stock_qty": 0, "stock_group": "", "purchase_price": 0, "display_name": "", "part_number": "", "aliases": []})
            display_name = inv.get("display_name") or s.get("display_name") or k

            stock_qty = float(inv["stock_qty"])
            qty_sold = s["qty_sold"]
            months = len(s["months_active"])
            monthly_avg = qty_sold / months if months > 0 else 0
            months_of_stock = stock_qty / monthly_avg if monthly_avg > 0 else (999 if stock_qty > 0 else 0)

            # Classify — order matters
            if stock_qty <= 0 and qty_sold == 0:
                # Item synced but ZERO transactions in the window AND no
                # current stock. Was previously bucketed into 'balanced'
                # which made the Balanced section misleading (1000s of
                # never-touched items diluted the actually-balanced ones).
                gap_type = "no_movement"
            elif stock_qty > 0 and qty_sold == 0:
                gap_type = "dead_stock"
            elif months_of_stock > 6:
                gap_type = "overstocked"
            elif 0 < months_of_stock < 1 and qty_sold > 0:
                gap_type = "understocked"
            elif qty_sold > 0 and stock_qty <= 0:
                gap_type = "out_of_stock"
            else:
                gap_type = "balanced"

            analysis.append({
                "item_name": display_name,
                "part_number": inv.get("part_number", ""),
                "aliases": inv.get("aliases") or [],
                "stock_group": inv.get("stock_group", ""),
                "stock_qty": round(stock_qty, 2),
                "qty_sold": round(qty_sold, 2),
                "revenue": round(s["revenue"], 2),
                "months_active": months,
                "monthly_avg_sales": round(monthly_avg, 2),
                "months_of_stock": round(min(months_of_stock, 999), 1),
                "gap_type": gap_type,
            })

        # Sort: problematic items first; no_movement at the bottom
        priority = {"out_of_stock": 0, "understocked": 1, "dead_stock": 2, "overstocked": 3, "balanced": 4, "no_movement": 5}
        analysis.sort(key=lambda x: (priority.get(x["gap_type"], 6), -x["revenue"]))

        gap_summary = defaultdict(int)
        for a in analysis:
            gap_summary[a["gap_type"]] += 1

        return APIResponse(success=True, data={
            "items": analysis,
            "summary": dict(gap_summary),
            "total_items": len(analysis),
            "window": window_meta,
        })
    except Exception as e:
        logger.error(f"SPIP analysis error: {e}")
        return APIResponse(success=False, error=str(e))


# ===================== 4. CONCENTRATION RISK (PARETO) =====================

@router.get("/insights/concentration-risk")
async def get_concentration_risk(request: Request, fy: Optional[str] = None, company_id: Optional[str] = None):
    """Pareto analysis — customer revenue concentration risk."""
    try:
        ctx = await get_tenant_context(request)
        q = _build_query(ctx, company_id)

        vouchers = await db.sales_vouchers.find(q, {"_id": 0, "party_name": 1, "voucher_date": 1, "amount": 1, "total_amount": 1}).to_list(20000)
        bp = await _get_branch_exclusion(request, ctx)
        vouchers = _exclude_branch_vouchers(vouchers, bp)
        if fy:
            vouchers = filter_vouchers_by_fy(vouchers, fy)

        customer_revenue = defaultdict(float)
        for v in vouchers:
            party = v.get("party_name", "")
            amt = v.get("total_amount") or v.get("amount") or 0
            if party:
                customer_revenue[party] += abs(float(amt)) if amt else 0

        if not customer_revenue:
            return APIResponse(success=True, data={
                "customers": [], "summary": {}, "risk_level": "no_data"
            })

        total_revenue = sum(customer_revenue.values())
        sorted_customers = sorted(customer_revenue.items(), key=lambda x: x[1], reverse=True)

        # Build Pareto curve
        cumulative = 0
        pareto = []
        for i, (name, rev) in enumerate(sorted_customers):
            cumulative += rev
            pct = round(rev / total_revenue * 100, 2)
            cum_pct = round(cumulative / total_revenue * 100, 2)
            pareto.append({
                "rank": i + 1,
                "customer_name": name,
                "revenue": round(rev, 2),
                "pct_of_total": pct,
                "cumulative_pct": cum_pct,
            })

        # Risk metrics
        total_customers = len(sorted_customers)
        top5_rev = sum(r for _, r in sorted_customers[:5])
        top10_rev = sum(r for _, r in sorted_customers[:10])
        top20pct_count = max(1, total_customers // 5)
        top20pct_rev = sum(r for _, r in sorted_customers[:top20pct_count])

        top5_pct = round(top5_rev / total_revenue * 100, 1) if total_revenue else 0
        top10_pct = round(top10_rev / total_revenue * 100, 1) if total_revenue else 0
        top20pct_pct = round(top20pct_rev / total_revenue * 100, 1) if total_revenue else 0

        # Risk level
        if top5_pct > 80:
            risk = "critical"
        elif top5_pct > 60:
            risk = "high"
        elif top10_pct > 80:
            risk = "moderate"
        else:
            risk = "healthy"

        return APIResponse(success=True, data={
            "customers": pareto[:50],
            "summary": {
                "total_customers": total_customers,
                "total_revenue": round(total_revenue, 2),
                "top5_pct": top5_pct,
                "top10_pct": top10_pct,
                "top20pct_pct": top20pct_pct,
                "top5_revenue": round(top5_rev, 2),
                "top10_revenue": round(top10_rev, 2),
            },
            "risk_level": risk,
        })
    except Exception as e:
        logger.error(f"Concentration risk error: {e}")
        return APIResponse(success=False, error=str(e))
