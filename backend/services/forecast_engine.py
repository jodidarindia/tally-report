"""Inventory demand-forecast engine — v1 (iteration 155).

Fits a small ensemble tailored to the SKU's demand velocity:
  • A-class  (steady, weekly+ sales)      → Holt-Winters (add trend + add season).
  • B-class  (monthly, some gaps)         → simple exponential smoothing on
                                           monthly series with linear trend.
  • C-class  (long-tail, sparse demand)   → Croston + SBA correction.
  • New SKU  (< 6 non-zero months)        → cohort average of same
                                           stock_group's B-class median.

Every output carries a 3-band confidence interval (P25 · P50 · P75) so
the UI never presents a single point estimate. Reorder point uses the
95 % service level normal-approx heuristic, but the tenant already has
richer ABC-tuned ROP logic in `routes/inventory.py` — we surface OUR
forecast alongside it so users can compare.

Zero external ML dependencies (statsmodels + numpy already vetted).
Zero LLM calls on the hot path.

Security: tenant_id + company_id ALWAYS included in every Mongo query.
Admin-only exposure is enforced at the router level.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import math
import statistics

import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.holtwinters import SimpleExpSmoothing


# ─── Curated Indian festival + seasonal calendar (auto-parts biased) ────
# Month → (bump factor, tag). Applied only when user turns on the lens.
FESTIVAL_MONTHS: Dict[int, Tuple[float, str]] = {
    3:  (1.10, "Holi + FY close"),
    6:  (1.15, "Monsoon on-set (oils/wipers)"),
    7:  (1.20, "Monsoon peak"),
    8:  (1.10, "Monsoon"),
    10: (1.25, "Dussehra + Diwali build-up"),
    11: (1.35, "Diwali + wedding season"),
    12: (1.05, "Year-end"),
}


# ─── Velocity classification ─────────────────────────────────────────────
def classify_velocity(monthly_units: List[float]) -> str:
    """Returns 'A', 'B', 'C' or 'new'.

    A — ≥ 24 months history AND ≥ 90 % months non-zero
    B — ≥ 12 months history AND ≥ 50 % months non-zero
    C — otherwise, with ≥ 6 months history
    new — < 6 months of non-zero data
    """
    nz = sum(1 for x in monthly_units if x > 0)
    n = len(monthly_units)
    if nz < 6:
        return "new"
    if n >= 24 and nz / n >= 0.90:
        return "A"
    if n >= 12 and nz / n >= 0.50:
        return "B"
    return "C"


# ─── Time-series builder ─────────────────────────────────────────────────
def build_monthly_series(
    sales_lines: List[dict],
    from_month: date,
    to_month: date,
) -> List[float]:
    """Aggregate daily voucher lines into a dense month-indexed series."""
    buckets: Dict[Tuple[int, int], float] = defaultdict(float)
    for ln in sales_lines:
        d = ln.get("voucher_date", "")[:10]
        qty = ln.get("quantity", 0) or 0
        if not d or qty <= 0:
            continue
        try:
            y, m, _ = d.split("-")[:3]
            buckets[(int(y), int(m))] += float(qty)
        except (ValueError, IndexError):
            continue
    series: List[float] = []
    cur = date(from_month.year, from_month.month, 1)
    stop = date(to_month.year, to_month.month, 1)
    while cur <= stop:
        series.append(buckets.get((cur.year, cur.month), 0.0))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return series


# ─── Forecast fitters ────────────────────────────────────────────────────
def _fit_holt_winters(series: List[float], horizon: int) -> List[float]:
    """A-class: additive trend + additive seasonality (period=12)."""
    if len(series) < 24 or all(v == 0 for v in series):
        return _fit_naive_mean(series, horizon)
    try:
        model = ExponentialSmoothing(
            series, trend="add", seasonal="add", seasonal_periods=12,
            initialization_method="estimated",
        ).fit(optimized=True)
        return [max(0.0, float(v)) for v in model.forecast(horizon)]
    except Exception:
        return _fit_ses(series, horizon)


def _fit_ses(series: List[float], horizon: int) -> List[float]:
    """B-class: SES on the raw series."""
    try:
        model = SimpleExpSmoothing(series,
                                    initialization_method="estimated").fit(optimized=True)
        return [max(0.0, float(v)) for v in model.forecast(horizon)]
    except Exception:
        return _fit_naive_mean(series, horizon)


def _fit_croston(series: List[float], horizon: int, alpha: float = 0.4) -> List[float]:
    """C-class: Croston + Syntetos-Boylan correction.

    Standard Croston overestimates by α/2; SBA multiplies by (1 - α/2).
    """
    if not any(v > 0 for v in series):
        return [0.0] * horizon
    Z = series[0] if series[0] > 0 else 1.0  # nonzero demand estimate
    P = 1.0                                   # inter-arrival estimate
    q = 1                                     # periods since last nonzero
    for x in series[1:]:
        if x > 0:
            Z = alpha * x + (1 - alpha) * Z
            P = alpha * q + (1 - alpha) * P
            q = 1
        else:
            q += 1
    base = (Z / P) * (1 - alpha / 2)
    return [max(0.0, base)] * horizon


def _fit_naive_mean(series: List[float], horizon: int) -> List[float]:
    if not series:
        return [0.0] * horizon
    m = float(np.mean(series))
    return [max(0.0, m)] * horizon


def _fit_cold_start(sku_group_series: Optional[List[List[float]]], horizon: int) -> List[float]:
    """new-SKU: median month across cohort peers of the same stock group."""
    if not sku_group_series:
        return [0.0] * horizon
    max_n = max(len(s) for s in sku_group_series) or 1
    padded = [(s + [0.0] * max_n)[:max_n] for s in sku_group_series]
    per_month = np.median(np.array(padded), axis=0)
    return [max(0.0, float(np.mean(per_month)))] * horizon


# ─── Confidence bands ────────────────────────────────────────────────────
def _confidence_band(series: List[float], forecast: List[float]) -> Tuple[List[float], List[float]]:
    """Return (p25_low, p75_high) using residual std from the historical mean."""
    if not series or not forecast:
        return forecast, forecast
    residual_std = float(np.std(series)) if len(series) > 1 else 0.0
    lo = [max(0.0, f - 0.674 * residual_std) for f in forecast]
    hi = [max(0.0, f + 0.674 * residual_std) for f in forecast]
    return lo, hi


# ─── Reorder point + safety stock ────────────────────────────────────────
def reorder_point(monthly_mean: float, monthly_std: float,
                  lead_time_days: int = 15, service_level: float = 0.95) -> Tuple[float, float]:
    """Return (safety_stock, reorder_point) both in units.

    Z-scores at 90/95/99 % service level = 1.28, 1.645, 2.33. Uses
    normal approximation — acceptable for A/B-class; C-class SKUs
    already carry huge intrinsic variance so ROP is only advisory."""
    z = {0.90: 1.28, 0.95: 1.645, 0.99: 2.33}.get(round(service_level, 2), 1.645)
    daily_mean = monthly_mean / 30.0
    daily_std = monthly_std / math.sqrt(30.0)
    ss = z * daily_std * math.sqrt(max(lead_time_days, 1))
    rop = daily_mean * lead_time_days + ss
    return round(ss, 2), round(rop, 2)


# ─── Top-level forecast for one SKU ──────────────────────────────────────
def forecast_sku(
    monthly_series: List[float],
    horizon_months: int,
    festival_lens: bool = False,
    cohort_series: Optional[List[List[float]]] = None,
) -> Dict:
    """Return forecast payload for a single SKU."""
    klass = classify_velocity(monthly_series)
    if klass == "A":
        fcst = _fit_holt_winters(monthly_series, horizon_months)
    elif klass == "B":
        fcst = _fit_ses(monthly_series, horizon_months)
    elif klass == "C":
        fcst = _fit_croston(monthly_series, horizon_months)
    else:  # new
        fcst = _fit_cold_start(cohort_series, horizon_months)

    if festival_lens and fcst:
        # Apply the calendar bump. We assume forecast months start next month.
        today = date.today()
        adjusted = []
        for i, val in enumerate(fcst):
            m = today.month + 1 + i
            m = ((m - 1) % 12) + 1
            factor, _tag = FESTIVAL_MONTHS.get(m, (1.0, ""))
            adjusted.append(round(val * factor, 2))
        fcst = adjusted

    lo, hi = _confidence_band(monthly_series, fcst)
    monthly_std = float(np.std(monthly_series)) if len(monthly_series) > 1 else 0.0
    monthly_mean = float(np.mean(monthly_series)) if monthly_series else 0.0
    ss, rop = reorder_point(monthly_mean, monthly_std)
    return {
        "velocity_class": klass,
        "forecast": [round(v, 2) for v in fcst],
        "forecast_low": [round(v, 2) for v in lo],
        "forecast_high": [round(v, 2) for v in hi],
        "monthly_mean": round(monthly_mean, 2),
        "monthly_std": round(monthly_std, 2),
        "reorder_point": rop,
        "safety_stock": ss,
        "history_months": len(monthly_series),
        "non_zero_months": sum(1 for x in monthly_series if x > 0),
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
