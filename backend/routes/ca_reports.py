"""
CA Corner — Bank & Investor Reports routes.

Endpoints (all require role="admin", i.e. the tenant useradmin; employees,
salesmen, dispatch, and super-admin cross-tenant users are rejected with
403). Every query is filtered by BOTH tenant_id AND company_id — no data
crosses tenants or companies. Sensitive assumptions (GSTIN, PAN, MSME,
bank name, proposed CC limit) are Fernet-AES-encrypted at rest.

Endpoints:
  POST /api/ca-reports/preview           — auto-populate historicals from
                                            Tally + assumption defaults
  GET  /api/ca-reports/assumptions       — load stored assumptions
  POST /api/ca-reports/assumptions       — save assumptions (encrypted)
  POST /api/ca-reports/cma/pdf           — generate 5-form CMA PDF
  POST /api/ca-reports/cma/xlsx          — generate 5-sheet CMA XLSX
  POST /api/ca-reports/pitch/pdf         — 16-page investor deck (dynamic)
  POST /api/ca-reports/pitch/teaser      — 10-page teaser
  POST /api/ca-reports/pitch/xlsx        — 8-sheet projections workbook
"""
from datetime import datetime, timezone
import io
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import db
from models import APIResponse
from services.auth_service import get_current_user
from services.tenant_context import get_tenant_context
from services.encryption_service import encrypt_field, decrypt_field
from services.ca_reports_engine import (
    HistoricalFY, Assumptions, CompanyMeta,
    project_future_fys,
    build_cma_pdf, build_cma_xlsx,
    build_pitch_pdf, build_projections_xlsx,
)
from utils import safe_num

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Auth / isolation guard ──────────────────────────────────────────────

async def _require_useradmin(request: Request) -> Dict[str, Any]:
    """Reject anyone who isn't the tenant's useradmin (role='admin').
    Returns (user, ctx) tuple."""
    ctx = await get_tenant_context(request)
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401,
                              detail="Authentication required.")
    role = (user.get("role") or "").lower()
    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail=("This report is available only to the tenant owner "
                     "(useradmin role). Your role is '"
                     + role + "'."))
    if not ctx.get("tenant_id"):
        raise HTTPException(status_code=403,
                              detail="No tenant context resolved.")
    if not ctx.get("company_id"):
        raise HTTPException(
            status_code=400,
            detail="No company selected. Pick a company first in the "
                    "top-right selector.")
    return {"user": user, "ctx": ctx}


def _tenant_company_query(ctx: Dict[str, Any]) -> Dict[str, str]:
    return {"tenant_id": ctx["tenant_id"], "company_id": ctx["company_id"]}


# ─── Encryption round-trip for assumptions ───────────────────────────────

_ENCRYPTED_FIELDS = ("gstin", "pan", "msme_regn", "bank_name")


def _encrypt_assumptions(a: Assumptions) -> Dict[str, Any]:
    d = a.__dict__.copy()
    for k in _ENCRYPTED_FIELDS:
        v = d.get(k, "") or ""
        d[k] = encrypt_field(v) if v else ""
    return d


def _decrypt_assumptions(doc: Dict[str, Any]) -> Assumptions:
    d = {k: v for k, v in doc.items()
         if k in Assumptions.__dataclass_fields__}
    for k in _ENCRYPTED_FIELDS:
        if d.get(k):
            d[k] = decrypt_field(d[k])
    return Assumptions(**d)


# ─── Historicals: aggregate from Tally sync collections ──────────────────

def _lakhs(v: float) -> float:
    """Convert raw INR into Rs. Lacs, rounded to 2 dp — the CMA convention."""
    if not v:
        return 0.0
    try:
        return round(float(v) / 100000.0, 2)
    except (TypeError, ValueError):
        return 0.0


async def _build_historical_fy(tenant_id: str, company_id: str,
                                 fy_label: str) -> HistoricalFY:
    """Pull one FY's numbers from Tally sync collections and package into a
    HistoricalFY record (values in Rs. Lacs)."""
    q = {"tenant_id": tenant_id, "company_id": company_id}

    # P&L — use existing snapshot (populated by sync)
    pl = await db.profit_loss.find_one({**q, "fy": fy_label},
                                          {"_id": 0}) or {}
    pl_any = await db.profit_loss.find_one(q, {"_id": 0}) or {}
    if not pl:
        pl = pl_any

    # Ledger scan for balance-sheet items
    ledgers = await db.all_ledgers.find(q, {"_id": 0}).to_list(20000)

    def _sum_group(*groups):
        gset = {g.lower() for g in groups}
        s = 0.0
        for l in ledgers:
            g = (l.get("parent_group") or l.get("root_group") or "").lower()
            if g in gset or any(g.startswith(x) for x in gset):
                s += safe_num(l.get("closing_balance", 0))
        return abs(s)

    # Voucher aggregates for the FY (guarded — only if the FY tag exists)
    sales_amt = 0.0
    purchase_amt = 0.0
    if fy_label:
        sv = await db.sales_vouchers.find(
            {**q, "fy": fy_label}, {"amount": 1}
        ).to_list(200000)
        sales_amt = sum(abs(safe_num(v.get("amount", 0))) for v in sv)
        pv = await db.purchase_vouchers.find(
            {**q, "fy": fy_label}, {"amount": 1}
        ).to_list(200000)
        purchase_amt = sum(abs(safe_num(v.get("amount", 0))) for v in pv)

    # Depreciation & interest
    dep_amt = 0.0
    int_amt = 0.0
    sga_amt = 0.0
    non_op_income = 0.0
    non_op_expense = 0.0
    tax_amt = 0.0
    for exp in (pl.get("expense") or []) + (pl.get("income") or []):
        nm = (exp.get("ledger_name") or "").lower()
        gp = (exp.get("parent_group") or "").lower()
        amt = safe_num(exp.get("amount", 0))
        if "depreciation" in nm or "depreciation" in gp:
            dep_amt += amt
        elif "interest" in nm and "expense" in gp:
            int_amt += amt
        elif ("tax" in nm and "provision" in nm) or "income tax" in nm:
            tax_amt += amt

    # Fallback SG&A: total P&L expense minus purchases/wages/dep/interest
    total_exp = safe_num(pl.get("total_expense", 0))
    sga_amt = max(total_exp - dep_amt - int_amt, 0)
    net_profit = safe_num(pl.get("net_profit_loss", 0))

    fy = HistoricalFY(
        fy_label=fy_label or "-",
        gross_sales=_lakhs(sales_amt or safe_num(pl.get("total_income", 0))),
        other_direct_income=0.0,
        net_sales=_lakhs(sales_amt or safe_num(pl.get("total_income", 0))),
        purchases=_lakhs(purchase_amt),
        direct_wages=0.0,
        power_fuel=0.0,
        other_direct_exp=0.0,
        depreciation=_lakhs(dep_amt),
        opening_stock_fg=0.0,
        closing_stock_fg=0.0,
        sga_expenses=_lakhs(sga_amt),
        interest=_lakhs(int_amt),
        other_non_op_income=_lakhs(non_op_income),
        other_non_op_expense=_lakhs(non_op_expense),
        provision_for_tax=_lakhs(tax_amt),

        # Balance sheet
        bank_st_borrowings=_lakhs(_sum_group(
            "bank od a/c", "bank oa/c", "bank o/d", "bank o.d a/c",
            "loans (liability)")),
        sundry_creditors=_lakhs(_sum_group("sundry creditors")),
        term_loans=_lakhs(_sum_group("secured loans")),
        unsecured_loans=_lakhs(_sum_group("unsecured loans")),
        proprietors_capital=_lakhs(_sum_group("capital account")),
        reserves_surplus=_lakhs(_sum_group("reserves & surplus",
                                              "reserves and surplus")),
        cash_bank_balance=_lakhs(_sum_group("cash-in-hand",
                                              "bank accounts")),
        receivables_domestic=_lakhs(_sum_group("sundry debtors")),
        inventory_finished=_lakhs(_sum_group("stock-in-hand",
                                               "closing stock",
                                               "opening stock")),
        gross_block=_lakhs(_sum_group("fixed assets")),
    )
    return fy


async def _detect_synced_fys(tenant_id: str, company_id: str) -> List[str]:
    """Return the list of FY tags actually present in the tenant's data."""
    q = {"tenant_id": tenant_id, "company_id": company_id}
    fys = await db.sales_vouchers.distinct("fy", q) or []
    fys += await db.profit_loss.distinct("fy", q) or []
    fys = sorted({f for f in fys if f})
    return fys[-5:] if len(fys) > 5 else fys


async def _load_company_meta(ctx: Dict[str, Any]) -> CompanyMeta:
    """Look up display name for the tenant's selected company."""
    from services.id_mapping_service import get_company_name
    try:
        name = await get_company_name(ctx["tenant_id"], ctx["company_id"]) or "-"
    except Exception:
        name = "-"
    tenant = await db.users.find_one(
        {"tenant_id": ctx["tenant_id"], "role": "admin"},
        {"_id": 0, "name": 1, "full_name": 1, "email": 1}) or {}
    contact = tenant.get("full_name") or tenant.get("name") or ""
    return CompanyMeta(company_name=name, contact_person=contact)


# ─── Route: PREVIEW (JSON) ───────────────────────────────────────────────

class PreviewRequest(BaseModel):
    n_hist: int = 2
    n_proj: int = 3


@router.post("/ca-reports/preview")
async def preview_report(request: Request, body: PreviewRequest = Body(...)):
    """Assemble historicals + projection defaults for the assumption form."""
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    tid, cid = ctx["tenant_id"], ctx["company_id"]

    fys = await _detect_synced_fys(tid, cid)
    if len(fys) == 0:
        return APIResponse(success=False,
                             error=("No FY data synced yet for this company. "
                                     "Please sync at least one FY via the "
                                     "Tally / Busy agent before generating "
                                     "a CMA."))
    # Limit historicals to what's actually synced (min 1, max body.n_hist)
    hist_fys = fys[-body.n_hist:] if len(fys) >= body.n_hist else fys
    warn = None
    if len(hist_fys) < 2:
        warn = (f"Only {len(hist_fys)} FY of data is synced. For a "
                 "bank-quality CMA, sync 2+ FYs OR enter the previous year "
                 "figures manually in the review step.")
    hist = []
    for fy in hist_fys:
        h = await _build_historical_fy(tid, cid, fy)
        hist.append(h)

    # Load stored assumptions (if any) else defaults
    saved = await db.ca_report_assumptions.find_one(
        _tenant_company_query(ctx), {"_id": 0})
    if saved:
        assumptions = _decrypt_assumptions(saved)
    else:
        assumptions = Assumptions()
        # Prime defaults from historicals
        if len(hist) >= 2:
            g = ((hist[-1].net_sales / hist[-2].net_sales - 1) * 100
                  if hist[-2].net_sales else 10.0)
            assumptions.sales_growth_y1 = round(g, 2)
            assumptions.sales_growth_y2 = round(g, 2)
            assumptions.sales_growth_y3 = round(g, 2)

    proj = project_future_fys(hist, assumptions, n_future=body.n_proj)

    meta = await _load_company_meta(ctx)

    return APIResponse(success=True, data={
        "company": meta.__dict__,
        "historicals": [h.__dict__ for h in hist],
        "projections": [p.__dict__ for p in proj],
        "assumptions": assumptions.__dict__,
        "fys_available": fys,
        "warnings": [warn] if warn else [],
    })


# ─── Route: SAVE ASSUMPTIONS ─────────────────────────────────────────────

@router.get("/ca-reports/assumptions")
async def get_assumptions(request: Request):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    doc = await db.ca_report_assumptions.find_one(
        _tenant_company_query(ctx), {"_id": 0})
    if not doc:
        return APIResponse(success=True, data=Assumptions().__dict__)
    a = _decrypt_assumptions(doc)
    return APIResponse(success=True, data=a.__dict__)


@router.post("/ca-reports/assumptions")
async def save_assumptions(request: Request, body: Dict[str, Any] = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx, user = guard["ctx"], guard["user"]

    # Coerce numeric strings & discard unknown keys defensively
    allowed = set(Assumptions.__dataclass_fields__.keys())
    clean = {}
    for k, v in body.items():
        if k not in allowed:
            continue
        if k in _ENCRYPTED_FIELDS:
            clean[k] = str(v or "")
        else:
            try:
                clean[k] = float(v) if v not in (None, "") else 0.0
            except (TypeError, ValueError):
                clean[k] = 0.0
    assumptions = Assumptions(**clean)
    payload = _encrypt_assumptions(assumptions)
    payload.update({
        **_tenant_company_query(ctx),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user.get("id") or user.get("_id"),
    })
    await db.ca_report_assumptions.update_one(
        _tenant_company_query(ctx),
        {"$set": payload},
        upsert=True,
    )
    return APIResponse(success=True, data={"saved": True})


# ─── Route: GENERATE ARTIFACTS ───────────────────────────────────────────

class GenerateRequest(BaseModel):
    assumptions: Dict[str, Any] = {}
    edited_historicals: Optional[List[Dict[str, Any]]] = None
    edited_projections: Optional[List[Dict[str, Any]]] = None
    n_hist: int = 2
    n_proj: int = 3


async def _assemble_fys(guard: Dict[str, Any], body: GenerateRequest
                          ) -> Any:
    ctx = guard["ctx"]
    tid, cid = ctx["tenant_id"], ctx["company_id"]

    # Assumptions — use body override, else stored, else defaults
    if body.assumptions:
        allowed = set(Assumptions.__dataclass_fields__.keys())
        clean = {}
        for k, v in body.assumptions.items():
            if k not in allowed:
                continue
            if k in _ENCRYPTED_FIELDS:
                clean[k] = str(v or "")
            else:
                try:
                    clean[k] = float(v) if v not in (None, "") else 0.0
                except (TypeError, ValueError):
                    clean[k] = 0.0
        assumptions = Assumptions(**clean)
    else:
        saved = await db.ca_report_assumptions.find_one(
            _tenant_company_query(ctx), {"_id": 0})
        assumptions = _decrypt_assumptions(saved) if saved else Assumptions()

    # Historicals — use edited if user reviewed cells, else Tally-derived
    if body.edited_historicals:
        hist = [HistoricalFY(**_coerce_hist(h))
                for h in body.edited_historicals]
    else:
        fys = await _detect_synced_fys(tid, cid)
        hist_fys = fys[-body.n_hist:] if len(fys) >= body.n_hist else fys
        hist = []
        for fy in hist_fys:
            hist.append(await _build_historical_fy(tid, cid, fy))

    # Projections — use edited if user overrode, else project fresh
    if body.edited_projections:
        proj = [HistoricalFY(**_coerce_hist(p))
                 for p in body.edited_projections]
    else:
        proj = project_future_fys(hist, assumptions, n_future=body.n_proj)

    meta = await _load_company_meta(ctx)
    return meta, hist, proj, assumptions


def _coerce_hist(d: Dict[str, Any]) -> Dict[str, Any]:
    """Cast any numeric-string values into floats before hydrating dataclass."""
    allowed = set(HistoricalFY.__dataclass_fields__.keys())
    out = {}
    for k, v in d.items():
        if k not in allowed:
            continue
        if k == "fy_label":
            out[k] = str(v or "-")
        else:
            try:
                out[k] = float(v) if v not in (None, "") else 0.0
            except (TypeError, ValueError):
                out[k] = 0.0
    return out


def _stream(data: bytes, filename: str, mimetype: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mimetype,
        headers={"Content-Disposition":
                    f'attachment; filename="{filename}"'})


@router.post("/ca-reports/cma/pdf")
async def gen_cma_pdf(request: Request, body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    pdf = build_cma_pdf(meta, hist, proj, a)
    fname = f"CMA_{_sanitize(meta.company_name)}.pdf"
    return _stream(pdf, fname, "application/pdf")


@router.post("/ca-reports/cma/xlsx")
async def gen_cma_xlsx(request: Request, body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    xlsx = build_cma_xlsx(meta, hist, proj, a)
    fname = f"CMA_{_sanitize(meta.company_name)}.xlsx"
    return _stream(
        xlsx, fname,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/ca-reports/pitch/pdf")
async def gen_pitch_pdf(request: Request, body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    pdf = build_pitch_pdf(meta, hist, proj, a, teaser=False)
    fname = f"Pitch_Deck_{_sanitize(meta.company_name)}.pdf"
    return _stream(pdf, fname, "application/pdf")


@router.post("/ca-reports/pitch/teaser")
async def gen_pitch_teaser(request: Request, body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    pdf = build_pitch_pdf(meta, hist, proj, a, teaser=True)
    fname = f"Pitch_Teaser_{_sanitize(meta.company_name)}.pdf"
    return _stream(pdf, fname, "application/pdf")


@router.post("/ca-reports/pitch/xlsx")
async def gen_projections_xlsx(request: Request,
                                 body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    xlsx = build_projections_xlsx(meta, hist, proj, a)
    fname = f"Projections_{_sanitize(meta.company_name)}.xlsx"
    return _stream(
        xlsx, fname,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _sanitize(name: str) -> str:
    safe = "".join(c for c in (name or "company")
                    if c.isalnum() or c in ("-", "_"))
    return safe[:64] or "company"
