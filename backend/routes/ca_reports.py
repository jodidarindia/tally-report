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

    # Voucher aggregates for the FY (iter-139: filter by voucher_date
    # range — sales_vouchers/purchase_vouchers do NOT persist a scalar
    # `fy` field, so the previous `{fy: fy_label}` filter always returned
    # zero and every historical FY looked like a blank company. Also the
    # amount field is `total_amount`, not `amount` — the older code was
    # summing a non-existent key on both collections).
    from utils import fy_to_date_range
    sales_amt = 0.0
    purchase_amt = 0.0
    if fy_label:
        fy_start, fy_end = fy_to_date_range(fy_label)
        if fy_start and fy_end:
            sv = await db.sales_vouchers.find(
                {**q, "voucher_date": {"$gte": fy_start, "$lte": fy_end}},
                {"amount": 1, "total_amount": 1}
            ).to_list(200000)
            sales_amt = sum(
                abs(safe_num(v.get("total_amount") or v.get("amount") or 0))
                for v in sv
            )
            pv = await db.purchase_vouchers.find(
                {**q, "voucher_date": {"$gte": fy_start, "$lte": fy_end}},
                {"amount": 1, "total_amount": 1}
            ).to_list(200000)
            purchase_amt = sum(
                abs(safe_num(v.get("total_amount") or v.get("amount") or 0))
                for v in pv
            )

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
    """Return the list of FY tags actually present in the tenant's data.

    iter-139 bugfix: `sales_vouchers` and `profit_loss` do NOT persist an
    `fy` scalar field (see ai_reports.py iter-121 note). Deriving FY via
    `distinct('fy', ...)` therefore always returned [], which surfaced as
    a false "No FY data synced yet" error even when 2+ FYs were live.
    Fix: enumerate FYs from the actual `voucher_date` range in
    sales_vouchers (Tally's most authoritative FY signal).
    """
    from utils import fy_to_date_range
    q = {"tenant_id": tenant_id, "company_id": company_id}

    # 1) Any explicitly-tagged FYs (defensive — supports future schemas
    #    that DO persist the scalar `fy` field).
    tagged: set[str] = set()
    for col in ("sales_vouchers", "profit_loss", "purchase_vouchers"):
        try:
            for f in (await db[col].distinct("fy", q)) or []:
                if f:
                    tagged.add(str(f))
        except Exception:
            pass

    # 2) Derive FYs from the sales_vouchers.voucher_date range — this is
    #    the source of truth today (see filter_vouchers_by_fy usage).
    date_derived: set[str] = set()
    try:
        oldest = await db.sales_vouchers.find(
            q, {"_id": 0, "voucher_date": 1}
        ).sort("voucher_date", 1).limit(1).to_list(1)
        newest = await db.sales_vouchers.find(
            q, {"_id": 0, "voucher_date": 1}
        ).sort("voucher_date", -1).limit(1).to_list(1)
        if oldest and newest:
            def _fy_of(iso_date: str) -> str:
                # 'YYYY-MM-DD' → Indian FY tag 'YYYY-YY' (Apr–Mar).
                y, m = int(iso_date[:4]), int(iso_date[5:7])
                start = y if m >= 4 else y - 1
                return f"{start}-{str(start + 1)[-2:]}"
            start_fy = _fy_of(oldest[0]["voucher_date"])
            end_fy = _fy_of(newest[0]["voucher_date"])
            sy = int(start_fy.split("-")[0])
            ey = int(end_fy.split("-")[0])
            for y in range(sy, ey + 1):
                fy = f"{y}-{str(y + 1)[-2:]}"
                # Confirm the FY has ≥1 voucher (guards against gaps).
                fs, fe = fy_to_date_range(fy)
                if fs and await db.sales_vouchers.count_documents(
                        {**q, "voucher_date": {"$gte": fs, "$lte": fe}},
                        limit=1):
                    date_derived.add(fy)
    except Exception:
        pass

    fys = sorted(tagged | date_derived)
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
    # Also check for manual prior-year entries — a tenant with zero
    # synced FYs can still preview a CMA if the CA has typed in prior
    # audited numbers manually.
    manual_count = await db.ca_manual_historicals.count_documents(
        _tenant_company_query(ctx))
    if len(fys) == 0 and manual_count == 0:
        return APIResponse(success=False,
                             error=("No FY data synced yet for this company, "
                                     "and no prior-year figures entered "
                                     "manually. Either sync at least one FY "
                                     "via the Tally / Busy agent, OR use "
                                     "the 'Prior-Year Manual Entry' form "
                                     "below to type in the audited numbers "
                                     "for at least one prior year."))
    # Limit historicals to what's actually synced (min 1, max body.n_hist)
    hist_fys = fys[-body.n_hist:] if len(fys) >= body.n_hist else fys
    hist = []
    for fy in hist_fys:
        h = await _build_historical_fy(tid, cid, fy)
        hist.append(h)

    # Merge in manually-entered prior-year historicals (Tally always wins
    # on collision — that way re-syncing later doesn't overwrite user
    # audited numbers with Tally's fresher-but-different figures.)
    manual = await _load_manual_historicals(ctx)
    synced_labels = {h.fy_label for h in hist}
    manual_extras = [m for m in manual if m.fy_label not in synced_labels]
    hist = sorted(hist + manual_extras, key=lambda h: h.fy_label)
    # Keep at most body.n_hist most recent
    hist = hist[-body.n_hist:] if len(hist) > body.n_hist else hist

    warn = None
    if len(hist) < 2:
        warn = (f"Only {len(hist)} historical FY available (synced + "
                 "manual). Add another prior year in the 'Prior-Year "
                 "Manual Entry' section for a bank-quality CMA with "
                 "2 historicals.")

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
        "manual_fy_labels": [m.fy_label for m in manual],
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



# ─── Route: MANUAL PRIOR-YEAR HISTORICALS ────────────────────────────────
#
# When a tenant has < 2 FYs synced from Tally, the CMA still needs 2
# historical columns for a bank-quality submission. This route lets the
# useradmin type in the audited numbers for one or more prior FYs. The
# preview / generate endpoints merge these with Tally-synced FYs (Tally
# wins on collision so re-syncing later doesn't get overridden).
#
# Sensitive financial values are Fernet-AES-128 encrypted at rest for
# the same reason we encrypt the assumption fields.

_MANUAL_ENCRYPTED_FIELDS = (
    # Every monetary value in a manual FY is treated as sensitive PII
    # (it's the company's audited P&L / BS that hasn't been synced yet).
    "gross_sales", "net_sales", "purchases", "sga_expenses",
    "depreciation", "interest", "provision_for_tax",
    "opening_stock_fg", "closing_stock_fg",
    "bank_st_borrowings", "sundry_creditors", "term_loans",
    "unsecured_loans", "proprietors_capital", "reserves_surplus",
    "withdrawals", "cash_bank_balance", "receivables_domestic",
    "inventory_raw", "inventory_wip", "inventory_finished",
    "gross_block", "accumulated_depreciation",
)


def _encrypt_manual(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in doc.items():
        if k in _MANUAL_ENCRYPTED_FIELDS:
            out[k] = encrypt_field(str(v)) if v not in (None, "", 0) else ""
        else:
            out[k] = v
    return out


def _decrypt_manual(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in doc.items():
        if k in _MANUAL_ENCRYPTED_FIELDS and v:
            try:
                out[k] = float(decrypt_field(v))
            except (TypeError, ValueError):
                out[k] = 0.0
        else:
            out[k] = v
    return out


def _manual_doc_to_historical_fy(doc: Dict[str, Any]) -> HistoricalFY:
    """Convert a decrypted `ca_manual_historicals` row into a
    HistoricalFY dataclass — coerces every value to float and only keeps
    keys that the dataclass declares."""
    d = _decrypt_manual(doc)
    allowed = set(HistoricalFY.__dataclass_fields__.keys())
    clean: Dict[str, Any] = {}
    for k, v in d.items():
        if k not in allowed:
            continue
        if k == "fy_label":
            clean[k] = str(v or "-")
        else:
            try:
                clean[k] = float(v) if v not in (None, "") else 0.0
            except (TypeError, ValueError):
                clean[k] = 0.0
    return HistoricalFY(**clean)


@router.get("/ca-reports/manual-historicals")
async def list_manual_historicals(request: Request):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    rows = await db.ca_manual_historicals.find(
        _tenant_company_query(ctx), {"_id": 0}
    ).sort("fy_label", 1).to_list(20)
    decrypted = [_decrypt_manual(r) for r in rows]
    return APIResponse(success=True, data={"historicals": decrypted})


@router.post("/ca-reports/manual-historicals")
async def upsert_manual_historical(request: Request,
                                     body: Dict[str, Any] = Body(...)):
    """Save one manual prior-year FY. Payload = a HistoricalFY dict; the
    fy_label is the natural primary key per (tenant, company)."""
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx, user = guard["ctx"], guard["user"]
    fy_label = str(body.get("fy_label") or "").strip()
    if not fy_label:
        return APIResponse(success=False,
                             error="fy_label is required (e.g. '2020-21').")
    # Sanity-check the FY label — 'YYYY-YY'
    if len(fy_label) != 7 or fy_label[4] != "-":
        return APIResponse(
            success=False,
            error="fy_label must be in the form 'YYYY-YY' (e.g. '2020-21').")
    # Only allow fields the dataclass knows about
    allowed = set(HistoricalFY.__dataclass_fields__.keys())
    clean = {k: v for k, v in body.items() if k in allowed}
    clean["fy_label"] = fy_label
    # Coerce numerics
    for k, v in list(clean.items()):
        if k == "fy_label":
            continue
        try:
            clean[k] = float(v) if v not in (None, "") else 0.0
        except (TypeError, ValueError):
            clean[k] = 0.0
    payload = _encrypt_manual(clean)
    payload.update({
        **_tenant_company_query(ctx),
        "fy_label": fy_label,   # kept in cleartext — safe & needed for lookup
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user.get("id") or user.get("_id"),
    })
    await db.ca_manual_historicals.update_one(
        {**_tenant_company_query(ctx), "fy_label": fy_label},
        {"$set": payload}, upsert=True,
    )
    return APIResponse(success=True, data={"saved": True,
                                              "fy_label": fy_label})


@router.delete("/ca-reports/manual-historicals/{fy_label}")
async def delete_manual_historical(request: Request, fy_label: str):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    res = await db.ca_manual_historicals.delete_one(
        {**_tenant_company_query(ctx), "fy_label": fy_label})
    return APIResponse(success=True, data={"deleted": res.deleted_count})


async def _load_manual_historicals(ctx: Dict[str, Any]) -> List[HistoricalFY]:
    rows = await db.ca_manual_historicals.find(
        _tenant_company_query(ctx), {"_id": 0}
    ).to_list(20)
    return [_manual_doc_to_historical_fy(r) for r in rows]



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
    # merged with any manually-entered prior-year audited numbers.
    if body.edited_historicals:
        hist = [HistoricalFY(**_coerce_hist(h))
                for h in body.edited_historicals]
    else:
        fys = await _detect_synced_fys(tid, cid)
        hist_fys = fys[-body.n_hist:] if len(fys) >= body.n_hist else fys
        hist = []
        for fy in hist_fys:
            hist.append(await _build_historical_fy(tid, cid, fy))
        # Merge in manually-entered FYs (Tally always wins on collision).
        manual = await _load_manual_historicals(ctx)
        synced_labels = {h.fy_label for h in hist}
        hist = sorted(hist + [m for m in manual
                                if m.fy_label not in synced_labels],
                       key=lambda h: h.fy_label)
        hist = hist[-body.n_hist:] if len(hist) > body.n_hist else hist

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


async def _track_cma_generation(ctx: Dict[str, Any], user: Dict[str, Any],
                                  artifact: str) -> None:
    """Record every CMA artefact generation so the reminder sweep knows
    when the tenant's last CMA rolled out. Fire-and-forget — a DB blip
    must never block a successful download."""
    try:
        await db.ca_report_generations.update_one(
            {**_tenant_company_query(ctx), "artifact": "cma"},
            {"$set": {
                **_tenant_company_query(ctx),
                "artifact": "cma",
                "last_generated_at": datetime.now(timezone.utc).isoformat(),
                "last_generated_by": user.get("email")
                                        or user.get("username")
                                        or user.get("id"),
                "last_artifact_kind": artifact,
                "reminder_sent_at": None,   # reset when a fresh CMA ships
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"CMA generation tracking failed (non-fatal): {e}")


async def _backup_ca_artifact(ctx, meta, blob: bytes, filename: str,
                                mime_type: str, subfolder: str) -> None:
    """Fire-and-forget Drive backup for a CA-Corner artefact. Non-fatal —
    if Drive isn't connected or the upload fails, the download response
    still succeeds."""
    from services.gdrive_service import try_backup_to_drive
    try:
        await try_backup_to_drive(
            db, ctx["tenant_id"], ctx["company_id"],
            blob, filename, mime_type, subfolder,
            company_display_name=meta.company_name)
    except Exception as e:
        logger.warning(f"CA artefact Drive backup non-fatal error: {e}")


@router.post("/ca-reports/cma/pdf")
async def gen_cma_pdf(request: Request, body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    pdf = build_cma_pdf(meta, hist, proj, a)
    await _track_cma_generation(guard["ctx"], guard["user"], "pdf")
    fname = f"CMA_{_sanitize(meta.company_name)}.pdf"
    # v137 — mirror to useradmin's Drive if connected (silent, fire-and-
    # forget). "CA Reports/CMA/YYYY-MM/" folder tree.
    from datetime import datetime as _dt
    await _backup_ca_artifact(
        guard["ctx"], meta, pdf, fname, "application/pdf",
        f"CA Reports/CMA/{_dt.now().strftime('%Y-%m')}")
    return _stream(pdf, fname, "application/pdf")


@router.post("/ca-reports/cma/xlsx")
async def gen_cma_xlsx(request: Request, body: GenerateRequest = Body(...)):
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    meta, hist, proj, a = await _assemble_fys(guard, body)
    xlsx = build_cma_xlsx(meta, hist, proj, a)
    await _track_cma_generation(guard["ctx"], guard["user"], "xlsx")
    fname = f"CMA_{_sanitize(meta.company_name)}.xlsx"
    from datetime import datetime as _dt
    await _backup_ca_artifact(
        guard["ctx"], meta, xlsx, fname,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"CA Reports/CMA/{_dt.now().strftime('%Y-%m')}")
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
    from datetime import datetime as _dt
    await _backup_ca_artifact(
        guard["ctx"], meta, pdf, fname, "application/pdf",
        f"CA Reports/Pitch/{_dt.now().strftime('%Y-%m')}")
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



# ─── CMA ANNUAL REMINDER ────────────────────────────────────────────────
#
# Whenever a CMA PDF/XLSX ships, `_track_cma_generation` writes a row into
# `ca_report_generations`. A background sweep (see
# `services.ca_reminders`) runs daily on the server, finds tenants where
# a CMA was generated ~305 days ago (365 − 60), has not yet had a
# reminder email sent, and emails the useradmin a nudge to regenerate.

REMINDER_LEAD_DAYS = 60         # send 60 days before the 1-year anniversary
CMA_ANNIVERSARY_DAYS = 365


@router.get("/ca-reports/reminders/status")
async def get_reminder_status(request: Request):
    """UI helper — surfaces the last CMA generation date + next reminder
    date + whether a reminder was already sent for this cycle."""
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx = guard["ctx"]
    doc = await db.ca_report_generations.find_one(
        {**_tenant_company_query(ctx), "artifact": "cma"},
        {"_id": 0}) or {}
    from datetime import timedelta
    last_iso = doc.get("last_generated_at")
    next_reminder = None
    days_until = None
    if last_iso:
        try:
            last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
            due_dt = last_dt + timedelta(
                days=CMA_ANNIVERSARY_DAYS - REMINDER_LEAD_DAYS)
            next_reminder = due_dt.isoformat()
            days_until = (due_dt - datetime.now(timezone.utc)).days
        except Exception:
            pass
    return APIResponse(success=True, data={
        "last_generated_at": last_iso,
        "last_artifact_kind": doc.get("last_artifact_kind"),
        "next_reminder_at": next_reminder,
        "days_until_reminder": days_until,
        "reminder_sent_at": doc.get("reminder_sent_at"),
        "reminder_lead_days": REMINDER_LEAD_DAYS,
    })


# ─── CSV BULK IMPORT for manual historicals ─────────────────────────────

@router.get("/ca-reports/manual-historicals/csv-template")
async def download_manual_csv_template(request: Request):
    """Return an empty CSV with the exact column headers users should
    populate. Downloaded by the 'Import CSV' flow's info link."""
    try:
        await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)

    from services.ca_reports_engine import HistoricalFY
    cols = list(HistoricalFY.__dataclass_fields__.keys())
    header = ",".join(cols)
    example = ",".join(["2020-21"] + ["0"] * (len(cols) - 1))
    csv_text = header + "\n" + example + "\n"
    return _stream(csv_text.encode("utf-8"),
                     "manual_historicals_template.csv", "text/csv")


class CSVImportRequest(BaseModel):
    """Accepts either a raw CSV string OR a list of parsed row dicts.
    Front-end can send either — we pick whichever is present."""
    csv_text: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None


@router.post("/ca-reports/manual-historicals/import-csv")
async def import_manual_csv(request: Request,
                              body: CSVImportRequest = Body(...)):
    """Bulk-upsert manual historicals from a CSV. First column MUST be
    fy_label. Every other column is coerced to float (blank → 0). Rows
    with a duplicate fy_label overwrite the earlier row (last wins)."""
    try:
        guard = await _require_useradmin(request)
    except HTTPException as e:
        return APIResponse(success=False, error=e.detail)
    ctx, user = guard["ctx"], guard["user"]

    # Parse CSV → list of dicts
    import csv as _csv
    from io import StringIO
    rows: List[Dict[str, Any]] = []
    if body.rows:
        rows = body.rows
    elif body.csv_text:
        try:
            reader = _csv.DictReader(StringIO(body.csv_text))
            rows = list(reader)
        except Exception as e:
            return APIResponse(success=False,
                                 error=f"CSV parse error: {e}")
    if not rows:
        return APIResponse(success=False,
                             error="No rows in the uploaded CSV.")
    # Validate + upsert
    allowed = set(HistoricalFY.__dataclass_fields__.keys())
    written, errors = 0, []
    for i, row in enumerate(rows, start=1):
        fy_label = str(row.get("fy_label") or "").strip()
        if not fy_label:
            errors.append(f"Row {i}: fy_label missing.")
            continue
        if len(fy_label) != 7 or fy_label[4] != "-":
            errors.append(
                f"Row {i}: fy_label '{fy_label}' invalid — expected 'YYYY-YY'.")
            continue
        clean = {"fy_label": fy_label}
        for k, v in row.items():
            if k == "fy_label" or k not in allowed:
                continue
            try:
                clean[k] = float(v) if v not in (None, "") else 0.0
            except (TypeError, ValueError):
                errors.append(
                    f"Row {i} ({fy_label}): field '{k}' non-numeric ('{v}').")
                clean[k] = 0.0
        payload = _encrypt_manual(clean)
        payload.update({
            **_tenant_company_query(ctx),
            "fy_label": fy_label,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": user.get("id") or user.get("_id"),
            "imported_via": "csv",
        })
        await db.ca_manual_historicals.update_one(
            {**_tenant_company_query(ctx), "fy_label": fy_label},
            {"$set": payload}, upsert=True,
        )
        written += 1
    return APIResponse(success=True, data={
        "written": written,
        "total_rows": len(rows),
        "errors": errors[:20],   # cap noise
        "errors_truncated": len(errors) > 20,
    })


# ─── Background sweep (called from server startup) ──────────────────────

async def sweep_cma_reminders() -> Dict[str, Any]:
    """Find every ca_report_generations row where:
       (last_generated_at + 305 days) ≤ now   AND
       reminder_sent_at is null OR older than last_generated_at
    Sends an email to the useradmin and marks reminder_sent_at.
    Idempotent — safe to call daily. Returns a summary dict."""
    from datetime import timedelta
    from services.email_service import send_email
    from services.id_mapping_service import get_company_name

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(
        days=CMA_ANNIVERSARY_DAYS - REMINDER_LEAD_DAYS)
    summary = {"checked": 0, "sent": 0, "errors": 0}

    async for gen in db.ca_report_generations.find(
        {"artifact": "cma"}, {"_id": 0}
    ):
        summary["checked"] += 1
        last_iso = gen.get("last_generated_at")
        if not last_iso:
            continue
        try:
            last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
        except Exception:
            continue
        if last_dt > threshold:
            continue  # not yet due
        # Skip if a reminder was already sent for THIS generation cycle
        r_iso = gen.get("reminder_sent_at")
        if r_iso:
            try:
                r_dt = datetime.fromisoformat(r_iso.replace("Z", "+00:00"))
                if r_dt >= last_dt:
                    continue
            except Exception:
                pass

        # Fetch useradmin email
        useradmin = await db.users.find_one(
            {"tenant_id": gen["tenant_id"], "role": "admin"},
            {"_id": 0, "email": 1, "username": 1, "name": 1})
        to = (useradmin or {}).get("email") or (useradmin or {}).get("username")
        if not to:
            summary["errors"] += 1
            continue
        try:
            company_name = await get_company_name(
                gen["tenant_id"], gen["company_id"]) or "your company"
        except Exception:
            company_name = "your company"

        # Days remaining until the CMA anniversary (60 → 0)
        due_dt = last_dt + timedelta(days=CMA_ANNIVERSARY_DAYS)
        days_left = max((due_dt - now).days, 0)

        subject = (f"Time to renew your working-capital limit "
                    f"— {company_name}")
        html = _reminder_html(company_name, days_left, last_dt.date().isoformat())
        try:
            ok = await send_email(to, subject, html,
                                    tag="cma-reminder", cc="auto")
            if ok:
                await db.ca_report_generations.update_one(
                    {**_tenant_company_query(gen), "artifact": "cma"},
                    {"$set": {"reminder_sent_at": now.isoformat()}})
                summary["sent"] += 1
            else:
                summary["errors"] += 1
        except Exception as e:
            logger.error(f"reminder send failed: {e}")
            summary["errors"] += 1
    if summary["sent"] or summary["errors"]:
        logger.info(f"CMA reminder sweep: {summary}")
    return summary


def _reminder_html(company_name: str, days_left: int, last_generated_date: str
                    ) -> str:
    return f"""
      <div style="font-family: -apple-system,'Segoe UI',Roboto,sans-serif;
                    color:#0F172A;max-width:600px;margin:0 auto;padding:32px;
                    background:#F8FAFC;border-radius:12px;">
        <img src="https://flowralive.in/assets/flowra-logo.png"
              alt="FLOWRA" style="height:36px;margin-bottom:24px;">
        <h1 style="font-size:22px;font-weight:700;margin:0 0 8px;
                    color:#0F1B4C;">
          Time to renew your working-capital limit
        </h1>
        <div style="color:#475569;line-height:1.6;margin-bottom:20px;">
          Hi there — this is a friendly nudge that <b>{company_name}</b>'s
          bank CMA is coming up for annual renewal.
        </div>
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;
                     border-radius:10px;padding:16px 20px;
                     margin-bottom:20px;">
          <div style="font-size:13px;color:#64748B;">Last CMA generated on</div>
          <div style="font-size:16px;font-weight:600;">
            {last_generated_date}
          </div>
          <div style="font-size:13px;color:#64748B;margin-top:12px;">
            Renewal window opens in
          </div>
          <div style="font-size:22px;font-weight:700;color:#2563EB;">
            {days_left} days
          </div>
        </div>
        <div style="color:#475569;line-height:1.6;margin-bottom:20px;">
          Your Tally / Busy sync has a full year of fresh data now — the
          projections in your last submission are stale by ~11 months.
          Bankers routinely reject renewals built on outdated financials.
        </div>
        <a href="https://insights.flowralive.in/ca-corner"
            style="display:inline-block;background:#2563EB;color:#FFFFFF;
                   padding:12px 22px;border-radius:8px;text-decoration:none;
                   font-weight:600;font-size:14px;">
          → Regenerate CMA in one click
        </a>
        <div style="color:#94A3B8;font-size:11px;margin-top:32px;">
          You're receiving this because <b>{company_name}</b> generated a
          CMA through FLOWRA. To turn off these reminders, ask your
          useradmin to delete the CMA generation record from CA Corner →
          Bank &amp; Investor Reports.
        </div>
      </div>
    """
