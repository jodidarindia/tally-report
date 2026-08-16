"""/api/analytics/forecast/* — Inventory demand forecast (v1, iter-155).

Security:
  • Admin-only (rejects super_admin, employee, salesman, dispatch).
  • Every DB query scoped to (tenant_id, company_id) resolved via
    `services.tenant_context.get_tenant_context` — the same guard the
    Dashboard / Insights routers use.
  • No cross-tenant reads. No open filters. No `.find({})` calls.

Cache:
  • Per (tenant_id, company_id, horizon) in-process dict, TTL 12 h.
  • Refresh forced with `?fresh=1`.

Scope (per user Feb-16-2026 spec):
  • ONLY the tenant's own SKUs (inventory master is the source of truth).
  • ALL synced FYs contribute to the historical series.
  • Consolidated buy list + season heatmap + per-SKU deep dive + cohort
    demand + what-if multipliers + CSV export.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
import io
import csv
import time
import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from db import db
from models import APIResponse
from services.tenant_context import get_tenant_context
from services.forecast_engine import (
    build_monthly_series, forecast_sku, reorder_point,
    FESTIVAL_MONTHS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE: dict = {}
_TTL_SEC = 12 * 60 * 60


async def _admin_only(request: Request) -> dict:
    """Reject any caller that isn't the tenant's admin. `useradmin` in
    the user's spec = the tenant admin role."""
    ctx = await get_tenant_context(request)
    if not ctx.get("tenant_id"):
        raise HTTPException(status_code=401, detail="tenant context missing")
    role = ctx.get("role", "")
    if role != "admin":
        # Explicitly deny employee/salesman/dispatch/super_admin.
        raise HTTPException(status_code=403,
                            detail="forecast tab is admin-only")
    return ctx


def _cache_key(tenant_id: str, company_id: str, horizon: int,
               festival: bool, growth_pct: float) -> str:
    return f"{tenant_id}::{company_id}::h{horizon}::f{int(festival)}::g{growth_pct}"


async def _load_dataset(tenant_id: str, company_id: str) -> dict:
    """Pull inventory master + full sales history for the tenant/company.
    Sales history is scoped to the tenant's OWN inventory item_ids only —
    external references (party-side items, deleted master items) are
    dropped per user spec."""
    inv_cursor = db.inventory_items.find(
        {"tenant_id": tenant_id, "company_id": company_id},
        {"_id": 0, "item_id": 1, "item_name": 1, "stock_group": 1,
         "quantity": 1, "sale_price": 1, "cost_price": 1, "abc_category": 1,
         "opening_quantity": 1},
    )
    inv_items = await inv_cursor.to_list(50000)
    inv_by_id = {i["item_id"]: i for i in inv_items if i.get("item_id")}
    inv_by_name = {(i.get("item_name") or "").strip().lower(): i for i in inv_items if i.get("item_name")}

    sales_cursor = db.sales_vouchers.find(
        {"tenant_id": tenant_id, "company_id": company_id},
        {"_id": 0, "voucher_date": 1, "party_name": 1, "items": 1, "fy": 1},
    )
    per_item_lines: dict = {}
    fys_seen: set = set()
    for sv in await sales_cursor.to_list(200000):
        fys_seen.add(sv.get("fy") or "")
        vd = sv.get("voucher_date", "")
        for ln in sv.get("items", []):
            code = str(ln.get("item_code") or "").strip()
            name = (ln.get("item") or ln.get("item_name") or "").strip().lower()
            # Match ONLY to tenant's own inventory master (user spec: no
            # external inventory).
            match = inv_by_id.get(code) or inv_by_name.get(name)
            if not match:
                continue
            key = match["item_id"]
            per_item_lines.setdefault(key, []).append({
                "voucher_date": vd,
                "quantity": ln.get("quantity", 0),
                "rate": ln.get("rate", 0),
                "amount": ln.get("amount", 0),
                "party_name": sv.get("party_name", ""),
            })
    return {
        "inv_by_id": inv_by_id,
        "inv_by_name": inv_by_name,
        "per_item_lines": per_item_lines,
        "fys": sorted(f for f in fys_seen if f),
    }


def _series_window(all_fys: list) -> tuple:
    """Return (from_month, to_month) covering the earliest FY start
    through the current month."""
    today = date.today()
    if not all_fys:
        return date(today.year - 1, today.month, 1), date(today.year, today.month, 1)
    earliest = min(all_fys)
    try:
        yr = int(earliest.split("-")[0])
    except Exception:
        yr = today.year - 2
    return date(yr, 4, 1), date(today.year, today.month, 1)


async def _compute_snapshot(ctx: dict, horizon: int,
                            festival: bool, growth_pct: float,
                            lead_time_days: int) -> dict:
    ds = await _load_dataset(ctx["tenant_id"], ctx["company_id"])
    from_month, to_month = _series_window(ds["fys"])

    # Cohort peers by stock_group for cold-start SKUs.
    peers_by_group: dict = {}
    for iid, item in ds["inv_by_id"].items():
        sg = (item.get("stock_group") or "").strip()
        if not sg:
            continue
        peers_by_group.setdefault(sg, []).append(iid)

    growth_mult = 1.0 + (growth_pct / 100.0)

    per_sku = []
    for iid, item in ds["inv_by_id"].items():
        lines = ds["per_item_lines"].get(iid, [])
        series = build_monthly_series(lines, from_month, to_month)
        cohort_series = None
        if sum(1 for x in series if x > 0) < 6:
            sg = (item.get("stock_group") or "").strip()
            cohort_series = [
                build_monthly_series(ds["per_item_lines"].get(p, []),
                                     from_month, to_month)
                for p in peers_by_group.get(sg, [])[:20]
                if p != iid
            ]
        f = forecast_sku(series, horizon,
                         festival_lens=festival,
                         cohort_series=cohort_series)
        # Apply what-if growth multiplier
        if growth_mult != 1.0:
            f["forecast"] = [round(v * growth_mult, 2) for v in f["forecast"]]
            f["forecast_low"] = [round(v * growth_mult, 2) for v in f["forecast_low"]]
            f["forecast_high"] = [round(v * growth_mult, 2) for v in f["forecast_high"]]
        expected_units = round(sum(f["forecast"]), 2)
        expected_rev = round(expected_units * float(item.get("sale_price") or 0), 2)
        current_stock = float(item.get("quantity") or 0)
        # Stockout risk = forecast > current stock and ROP > current stock.
        stockout = (expected_units > current_stock) and (f["reorder_point"] > current_stock)
        # Excess = forecast horizon consumes < 25 % of current stock.
        excess = (expected_units < 0.25 * current_stock) and (current_stock > 5)
        buy_by = None
        if stockout and f["monthly_mean"] > 0:
            days_of_cover = (current_stock / (f["monthly_mean"] / 30.0)) if f["monthly_mean"] else 0
            days_left = max(0, int(days_of_cover) - lead_time_days)
            buy_by = (date.today() + __import__("datetime").timedelta(days=days_left)).isoformat()
        per_sku.append({
            "item_id": iid,
            "item_name": item.get("item_name", ""),
            "stock_group": item.get("stock_group", ""),
            "current_stock": current_stock,
            "sale_price": float(item.get("sale_price") or 0),
            "abc_category": item.get("abc_category") or None,
            "velocity_class": f["velocity_class"],
            "history_months": f["history_months"],
            "non_zero_months": f["non_zero_months"],
            "monthly_mean": f["monthly_mean"],
            "monthly_std": f["monthly_std"],
            "forecast_units": expected_units,
            "forecast_revenue": expected_rev,
            "forecast_low": round(sum(f["forecast_low"]), 2),
            "forecast_high": round(sum(f["forecast_high"]), 2),
            "reorder_point": f["reorder_point"],
            "safety_stock": f["safety_stock"],
            "stockout_risk": stockout,
            "excess_risk": excess,
            "buy_by": buy_by,
            # Confidence % — driven by history depth and non-zero density.
            "confidence_pct": min(95, max(35,
                int(40 + 5 * f["non_zero_months"] // max(1, f["history_months"])
                    + (10 if f["velocity_class"] == "A" else
                       5 if f["velocity_class"] == "B" else 0))
            )),
            "monthly_forecast": f["forecast"],
        })
    # Sort — highest projected revenue first
    per_sku.sort(key=lambda x: -x["forecast_revenue"])

    kpi = {
        "projected_units": round(sum(x["forecast_units"] for x in per_sku), 2),
        "projected_revenue": round(sum(x["forecast_revenue"] for x in per_sku), 2),
        "stockout_skus": sum(1 for x in per_sku if x["stockout_risk"]),
        "excess_skus": sum(1 for x in per_sku if x["excess_risk"]),
        "total_skus_analysed": len(per_sku),
        "fys_used": ds["fys"],
        "horizon_months": horizon,
        "festival_lens": festival,
        "growth_pct": growth_pct,
    }
    return {"kpi": kpi, "skus": per_sku, "computed_at": time.time(),
            "from_month": from_month.isoformat(), "to_month": to_month.isoformat()}


async def _get_or_compute(ctx: dict, horizon: int, festival: bool,
                          growth_pct: float, lead_time_days: int,
                          fresh: bool) -> dict:
    key = _cache_key(ctx["tenant_id"], ctx["company_id"], horizon,
                     festival, growth_pct)
    now = time.time()
    if not fresh:
        cached = _CACHE.get(key)
        if cached and (now - cached["computed_at"] < _TTL_SEC):
            return cached
    snap = await _compute_snapshot(ctx, horizon, festival, growth_pct, lead_time_days)
    _CACHE[key] = snap
    return snap


# ─── Endpoints ───────────────────────────────────────────────────────────

@router.get("/analytics/forecast/overview")
async def get_forecast_overview(
    request: Request,
    horizon_months: int = 3,
    festival_lens: bool = False,
    growth_pct: float = 0.0,
    lead_time_days: int = 15,
    fresh: bool = False,
    limit: int = 500,
):
    """KPI band + top consolidated buy list."""
    try:
        ctx = await _admin_only(request)
        horizon_months = max(1, min(12, int(horizon_months)))
        snap = await _get_or_compute(ctx, horizon_months, festival_lens,
                                     float(growth_pct), int(lead_time_days), fresh)
        buy_list = [s for s in snap["skus"] if s["stockout_risk"] or s["forecast_units"] > s["current_stock"] * 0.5]
        buy_list = sorted(buy_list, key=lambda x: -x["forecast_revenue"])[:limit]
        return APIResponse(success=True, data={
            "kpi": snap["kpi"],
            "buy_list": buy_list,
            "from_month": snap["from_month"],
            "to_month": snap["to_month"],
            "festival_calendar": {str(k): v[1] for k, v in FESTIVAL_MONTHS.items()},
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("forecast overview failed")
        return APIResponse(success=False, error=str(e))


@router.get("/analytics/forecast/sku/{item_id}")
async def get_sku_forecast(
    item_id: str, request: Request,
    horizon_months: int = 6, festival_lens: bool = False,
    growth_pct: float = 0.0, lead_time_days: int = 15, fresh: bool = False,
):
    try:
        ctx = await _admin_only(request)
        horizon_months = max(1, min(12, int(horizon_months)))
        snap = await _get_or_compute(ctx, horizon_months, festival_lens,
                                     float(growth_pct), int(lead_time_days), fresh)
        row = next((s for s in snap["skus"] if s["item_id"] == item_id), None)
        if not row:
            return APIResponse(success=False, error="item not found in this tenant/company")
        return APIResponse(success=True, data=row)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("forecast per-sku failed")
        return APIResponse(success=False, error=str(e))


@router.get("/analytics/forecast/season")
async def get_season_heatmap(request: Request,
                             top: int = 30, horizon_months: int = 3,
                             festival_lens: bool = False, growth_pct: float = 0.0):
    """Rows = top-N SKUs by projected revenue. Cols = past 12 months of
    actuals + horizon months forecast. UI paints heatmap."""
    try:
        ctx = await _admin_only(request)
        snap = await _get_or_compute(ctx, horizon_months, festival_lens,
                                     float(growth_pct), 15, False)
        # Load actuals for top SKUs (past 12 months)
        top_ids = [s["item_id"] for s in snap["skus"][:top]]
        ds = await _load_dataset(ctx["tenant_id"], ctx["company_id"])
        today = date.today()
        past_start = date(today.year - 1, today.month, 1)
        rows = []
        for iid in top_ids:
            item = ds["inv_by_id"].get(iid)
            if not item:
                continue
            actual = build_monthly_series(ds["per_item_lines"].get(iid, []),
                                          past_start, date(today.year, today.month, 1))
            sku_row = next((s for s in snap["skus"] if s["item_id"] == iid), None)
            fcst = sku_row.get("monthly_forecast", []) if sku_row else []
            rows.append({
                "item_id": iid,
                "item_name": item.get("item_name", ""),
                "stock_group": item.get("stock_group", ""),
                "past_12": [round(v, 2) for v in actual],
                "forecast": fcst,
            })
        return APIResponse(success=True, data={
            "rows": rows,
            "past_start": past_start.isoformat(),
            "horizon_months": horizon_months,
            "festival_calendar": {str(k): v[1] for k, v in FESTIVAL_MONTHS.items()},
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("forecast season heatmap failed")
        return APIResponse(success=False, error=str(e))


@router.get("/analytics/forecast/cohort")
async def get_cohort_demand(request: Request, top_customers: int = 20,
                            horizon_months: int = 3):
    """For the top-N customers, project next-horizon demand assuming
    they buy the same units they bought in the SAME MONTHS last year."""
    try:
        ctx = await _admin_only(request)
        tenant_id = ctx["tenant_id"]
        company_id = ctx["company_id"]
        top_customers = max(1, min(100, top_customers))
        horizon_months = max(1, min(12, horizon_months))
        # Aggregate: sum revenue per customer over full history
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "company_id": company_id}},
            {"$group": {"_id": "$party_name",
                        "total_rev": {"$sum": "$total_amount"},
                        "voucher_count": {"$sum": 1}}},
            {"$sort": {"total_rev": -1}},
            {"$limit": top_customers},
        ]
        top = [x async for x in db.sales_vouchers.aggregate(pipeline)]
        # For each, compute same-months-last-year units.
        today = date.today()
        target_months = []
        for i in range(horizon_months):
            m = today.month + 1 + i
            yr_off = (m - 1) // 12
            m = ((m - 1) % 12) + 1
            target_months.append((today.year - 1 + yr_off, m))
        rows = []
        for entry in top:
            party = entry["_id"] or "(unknown)"
            projected_units = 0.0
            projected_rev = 0.0
            async for sv in db.sales_vouchers.find({
                "tenant_id": tenant_id, "company_id": company_id, "party_name": party
            }, {"voucher_date": 1, "total_amount": 1, "items": 1}):
                d = (sv.get("voucher_date") or "")[:10]
                try:
                    y, m, _ = d.split("-")[:3]
                    if (int(y), int(m)) in target_months:
                        projected_rev += float(sv.get("total_amount") or 0)
                        for ln in sv.get("items", []):
                            projected_units += float(ln.get("quantity") or 0)
                except Exception:
                    continue
            rows.append({
                "party_name": party,
                "lifetime_revenue": round(entry["total_rev"], 2),
                "lifetime_vouchers": entry["voucher_count"],
                "projected_units_next_horizon": round(projected_units, 2),
                "projected_revenue_next_horizon": round(projected_rev, 2),
            })
        rows.sort(key=lambda x: -x["projected_revenue_next_horizon"])
        return APIResponse(success=True, data={"rows": rows,
                                                "target_months": [f"{y}-{m:02d}" for y, m in target_months]})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("forecast cohort failed")
        return APIResponse(success=False, error=str(e))


@router.get("/analytics/forecast/export")
async def export_forecast_csv(request: Request, horizon_months: int = 3,
                              festival_lens: bool = False, growth_pct: float = 0.0):
    try:
        ctx = await _admin_only(request)
        snap = await _get_or_compute(ctx, max(1, min(12, horizon_months)),
                                     festival_lens, float(growth_pct), 15, False)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "item_id", "item_name", "stock_group", "current_stock",
            "sale_price", "velocity_class", "forecast_units",
            "forecast_low", "forecast_high", "forecast_revenue",
            "reorder_point", "safety_stock", "confidence_pct",
            "stockout_risk", "excess_risk", "buy_by",
        ])
        for s in snap["skus"]:
            w.writerow([
                s["item_id"], s["item_name"], s["stock_group"],
                s["current_stock"], s["sale_price"], s["velocity_class"],
                s["forecast_units"], s["forecast_low"], s["forecast_high"],
                s["forecast_revenue"], s["reorder_point"], s["safety_stock"],
                s["confidence_pct"],
                "YES" if s["stockout_risk"] else "",
                "YES" if s["excess_risk"] else "",
                s["buy_by"] or "",
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="forecast_{date.today().isoformat()}.csv"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("forecast export failed")
        return APIResponse(success=False, error=str(e))
