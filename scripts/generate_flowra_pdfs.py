"""
FLOWRA — Master PDF Documentation Generator (April 2026)
Generates all customer-facing PDFs from a single source of truth so they stay in sync.

Outputs:
  - FLOWRA_Presentation.pdf            (sales / pitch deck)
  - FLOWRA_Customer_Questionnaire.pdf  (pre-onboarding needs assessment)
  - FLOWRA_Training_Booklet.pdf        (end-user training)
  - FLOWRA_Deployment_Guide.pdf        (admin / IT setup)
  - FLOWRA_Whats_New.pdf               (latest features changelog)
  - FLOWRA_Coming_Soon.pdf             (public roadmap)
  - FLOWRA_Social_Media_Kit.pdf        (brand asset reference)
"""
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    ListFlowable, ListItem, KeepTogether
)


OUT_DIR = "/app/frontend/public"
BUILD_DATE = datetime.now().strftime("%d %B %Y")
VERSION = "v3.1 (May 2026)"

# ── Brand palette ────────────────────────────────────────
PRIMARY   = colors.HexColor("#0052FF")
ACCENT    = colors.HexColor("#7C3AED")
SUCCESS   = colors.HexColor("#10B981")
INK       = colors.HexColor("#0F172A")
TEXT      = colors.HexColor("#1E293B")
MUTED     = colors.HexColor("#64748B")
BG_SOFT   = colors.HexColor("#F8FAFC")
BORDER    = colors.HexColor("#E2E8F0")


# ── Reusable styles ──────────────────────────────────────
def make_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("FlowraTitle",     fontName="Helvetica-Bold", fontSize=28, leading=34, textColor=INK,    spaceAfter=14))
    s.add(ParagraphStyle("FlowraSubtitle",  fontName="Helvetica",      fontSize=14, leading=20, textColor=MUTED,  spaceAfter=22))
    s.add(ParagraphStyle("FlowraH1",        fontName="Helvetica-Bold", fontSize=20, leading=26, textColor=INK,    spaceBefore=18, spaceAfter=10))
    s.add(ParagraphStyle("FlowraH2",        fontName="Helvetica-Bold", fontSize=14, leading=20, textColor=PRIMARY,spaceBefore=14, spaceAfter=6))
    s.add(ParagraphStyle("FlowraEyebrow",   fontName="Helvetica-Bold", fontSize=8.5, leading=12, textColor=PRIMARY, spaceAfter=6))
    s.add(ParagraphStyle("FlowraBody",      fontName="Helvetica",      fontSize=10.5,leading=16, textColor=TEXT,   spaceAfter=8, alignment=TA_JUSTIFY))
    s.add(ParagraphStyle("FlowraBodyTight", fontName="Helvetica",      fontSize=10,  leading=14, textColor=TEXT,   spaceAfter=4))
    s.add(ParagraphStyle("FlowraBullet",    fontName="Helvetica",      fontSize=10,  leading=15, textColor=TEXT,   leftIndent=14, spaceAfter=3))
    s.add(ParagraphStyle("FlowraSmall",     fontName="Helvetica",      fontSize=8.5, leading=12, textColor=MUTED))
    s.add(ParagraphStyle("FlowraBadge",     fontName="Helvetica-Bold", fontSize=8,   leading=10, textColor=colors.white))
    return s


def header_footer(canvas, doc):
    """Brand header bar + footer page numbers."""
    canvas.saveState()
    # Top brand bar
    canvas.setFillColor(INK)
    canvas.rect(0, A4[1] - 0.55 * inch, A4[0], 0.55 * inch, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(0.6 * inch, A4[1] - 0.36 * inch, "FLOWRA")
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(A4[0] - 0.6 * inch, A4[1] - 0.36 * inch,
                           f"flowralive.in   ·   {BUILD_DATE}   ·   {VERSION}")
    # Footer
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawCentredString(A4[0] / 2, 0.4 * inch,
                             f"Page {doc.page}   ·   © FLOWRA {datetime.now().year}   ·   Built in India")
    canvas.restoreState()


def doc_template(path):
    return SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.95 * inch, bottomMargin=0.65 * inch,
        title="FLOWRA", author="FLOWRA",
    )


def bullets(items, styles):
    return ListFlowable(
        [ListItem(Paragraph(t, styles["FlowraBullet"]), leftIndent=8, bulletColor=PRIMARY) for t in items],
        bulletType="bullet", start="•", bulletFontSize=10, leftIndent=12,
    )


def callout_table(title, body, styles, color=PRIMARY):
    """Branded callout block."""
    t = Table([
        [Paragraph(f"<b>{title}</b>", styles["FlowraBodyTight"])],
        [Paragraph(body, styles["FlowraBodyTight"])],
    ], colWidths=[6.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",      (0, 0), (-1, -1), BG_SOFT),
        ("LEFTPADDING",     (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",    (0, 0), (-1, -1), 12),
        ("TOPPADDING",      (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",   (0, 0), (-1, -1), 8),
        ("LINEBEFORE",      (0, 0), (0, -1), 3, color),
    ]))
    return t


def feature_table(rows, styles):
    """Two-column feature spec table."""
    data = [[Paragraph(f"<b>{r[0]}</b>", styles["FlowraBodyTight"]),
             Paragraph(r[1], styles["FlowraBodyTight"])] for r in rows]
    t = Table(data, colWidths=[2.0 * inch, 4.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",      (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS",  (0, 0), (-1, -1), [colors.white, BG_SOFT]),
        ("LINEBELOW",       (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN",          (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",     (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",    (0, 0), (-1, -1), 8),
        ("TOPPADDING",      (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",   (0, 0), (-1, -1), 7),
    ]))
    return t


# ─────────────────────────────────────────────────────────
# 1. WHAT'S NEW (changelog) — most important: showcase all latest features
# ─────────────────────────────────────────────────────────
def build_whats_new():
    s = make_styles()
    elems = []
    elems += [
        Paragraph("WHAT'S NEW", s["FlowraEyebrow"]),
        Paragraph("FLOWRA Insights — Latest Features", s["FlowraTitle"]),
        Paragraph("Everything we've shipped through May 2026. Each update builds toward FLOWRA's promise: software that runs your business, quietly.", s["FlowraSubtitle"]),
        Spacer(1, 8),
    ]

    sections = [
        # ── May 2026 — newest first ───────────────────────────────
        ("Beat Run Today — Field Coverage Tracking", "NEW",
         "Salesmen now have a one-tap daily beat sheet auto-derived from their plan. They tap a customer to mark visited, "
         "log unplanned (NEW) visits, and see real-time coverage %. Day-end auto-locks past dates so the audit trail stays clean. "
         "Admins audit any salesman's beat run from the useradmin Salesman → Beat Runs tab.",
         [
             "Auto-built from each salesman's beat plan filtered by today's day-of-week (IST)",
             "Tap-to-toggle visited check-ins with IST timestamp",
             "NEW chip for unplanned visits until that customer appears in synced Tally data",
             "Read-only Beat History — past runs locked, click any row for detail view",
             "Server-side day-end lock — the API itself rejects stale run_date params",
             "Single-salesman-per-customer enforcement — prevents cross-mapping conflicts",
         ]),
        ("Inventory A/B/C/D Categorisation", "NEW",
         "The old free-text Category field is replaced with proper Pareto A/B/C/D tiers. Tag manually with one click, or "
         "run Auto-ABC to apply the 80-15-4-1 distribution across the FY revenue. Filters and a new Category Sales Analytics "
         "tab let you slice the entire catalog by tier with drill-downs.",
         [
             "Manual: one-click A/B/C/D pill on every row",
             "Bulk: Auto-ABC button runs Pareto 80-15-4-1 on FY revenue",
             "Filter: dropdown to slice by A/B/C/D/Untagged",
             "Preserved across re-syncs — sync.py snapshots assignments before delete-and-reinsert",
             "Standard Sale Price column (Tally STDPRICE) added to Inventory table",
             "Category Sales Analytics tab — top customers, qty, revenue, frequency per item, CSV export per category",
         ]),
        ("CA Corner — 100% Tally Parity", "ENHANCED",
         "Balance Sheet and Profit & Loss now match Tally exactly. Built directly from synced ledgers with proper sign convention, "
         "auto-balanced via P&L A/c residual. Validated against real customer FY26-27 exports — Sales, Purchases, Indirect Income, "
         "Direct Expense match to the rupee.",
         [
             "Balance Sheet derived from all_ledgers + customers + creditors with correct asset/liability sign flips",
             "P&L Method A — sums all_ledgers.closing_balance by parent_group for current FY (matches Tally exactly)",
             "Heuristic catch-all for user-defined sub-groups (Salary Accounts, Local Thela Gaadi, Wages, Rent, Travel, etc.)",
             "Automatic notices when Stock-in-Hand or Sundry Creditors aren't yet synced",
             "Tally Verified ✓ green badge in CRM Outstanding when computed OS reconciles to Tally master",
         ]),
        ("Dispatch Employee Mirror View", "ENHANCED",
         "Dispatch employees now see the SAME admin Dispatch Terminal — Kanban board, online orders, pending billing, porters, "
         "transporters, date selector, create-cards — with only the Employees tab hidden. Logout no longer flashes a "
         "'Feature Not Activated' toast (root-cause fix in PageRenderer).",
         [
             "Full feature parity with admin view (only Employees tab hidden)",
             "Online Order tab cards now clickable → detail modal with line items, part numbers, notes",
             "Tenant-wide visibility fix — /api/dispatch/employees now scopes by tenant, not company",
             "Logout flash bug fixed — PageRenderer returns null when token cleared",
         ]),
        ("Backups & Tenant Data Export", "NEW",
         "A two-tier data-protection layer. SuperAdmin can run on-demand or scheduled MongoDB dumps and download them anytime. "
         "Every tenant admin can export their entire dataset as a ZIP for DPDP Act 2023 compliance — your data, your rights.",
         [
             "SuperAdmin → Backups tab: Run Now, list, download, delete",
             "Daily 02:00 IST cron retains last 30 backups (gzipped mongodump archives)",
             "Tenant admin → user menu → Export Your Data: ZIP with one JSON per collection + manifest",
             "Strict tenant isolation — cross-tenant data, password hashes, system audit logs are never included",
             "Every export and backup logged to the audit trail",
         ]),
        ("Salesman Dashboard & Performance", "NEW",
         "Salesmen now land on a personal dashboard showing Achieved, Expected YTD, Monthly Target and Achievement %, "
         "with customer-wise drill-downs and top items sold. Activity feed scoped to own audit logs only. "
         "Achievement % bug fixed — now compares against YTD-prorated target, not full annual.",
         [
             "KPI cards: Achieved, Expected YTD, Monthly Target, Achievement % (FY-aware)",
             "Customer-wise breakdown drill-down + top items sold",
             "New Order: catalog search matches item_name OR part_number; part numbers in cart and order detail",
             "Activity feed scoped to own logs (admin still sees everything for the tenant)",
             "Beat Plans tab in admin Salesman page — visualise 6-day weekly grid + editable rows",
         ]),
        ("Tally Sync Agent v9.6.0", "ENHANCED",
         "Captures STANDARDPRICE per stock item so the Salesman catalog and Inventory table show the right Tally master price. "
         "Falls back to closing rate until first re-sync. Earlier v9.1/v9.5 fixes for JV direction, creditor filtering, "
         "and signed P&L summary all rolled in.",
         [
             "STANDARDPRICE / STDPRICE captured per stock item → standard_price field",
             "Per-line DR/CR direction in ledger_entries (ISDEEMEDPOSITIVE + signed AMOUNT fallback)",
             "Creditor sub-group string-match (creditor/supplier/vendor) for user-defined groups",
             "Salary, Wages, Rent, Travel, Commission, Advertisement auto-mapped to Indirect Expenses",
             "Re-served at /flowra-desktop-agent.py — re-run Full Sync to refresh master prices",
         ]),

        # ── April 2026 ───────────────────────────────────────────
        ("Dispatch Terminal", "NEW",
         "A complete warehouse-floor companion. Convert approved orders into dispatch cards, "
         "track them through a Kanban swim-lane (Pending → Packed → Loaded → Out → Delivered), "
         "settle transporter & porter charges, and generate a one-click Close-of-Day PDF summarising everything sent out today.",
         [
             "Kanban swim-lane board with drag-and-drop status changes",
             "Mobile-responsive — works on warehouse-floor tablets and phones",
             "Document upload per dispatch (LR copy, packing list, photo proof)",
             "Transporter and Porter settlement screens with running balance",
             "Pending Billing tab — verify which approved orders haven't been billed in Tally yet",
             "Close-of-Day PDF report, downloadable / WhatsApp-shareable",
             "Online Orders tab merges dispatch with e-commerce orders",
         ]),
        ("Salesman Order System", "NEW",
         "A mobile-first order collection app for field salesmen. Real-time stock view, customer-isolated catalog, "
         "and an admin approval workflow. Approved orders flow into the Dispatch Terminal for fulfillment.",
         [
             "Salesman role unified inside Profile → Employees (no separate setup)",
             "Customer mapping per salesman — they only see their assigned customers",
             "Real-time inventory visibility while drafting an order",
             "Order lifecycle: Pending → Approved / Rejected / Hold → Billed",
             "Pending Billing verification against Tally invoice numbers",
             "Mobile-first UI — built for phones first, desktop second",
             "Customer targets & follow-ups in one place",
         ]),
        ("CA Corner — Balance Sheet & P&L Drill-Down", "NEW",
         "A dedicated workspace for Chartered Accountants. Cash Flow (Tally indirect method), monthly/annual P&L, "
         "Balance Sheet grouped by parent group with expandable ledger drill-down, and AI-powered expense insights.",
         [
             "Cash Flow statement (Operating, Investing, Financing) — Tally indirect method",
             "P&L Report with monthly + annual views and ledger drill-down",
             "Balance Sheet — Assets vs Liabilities + Capital, expandable per ledger",
             "Income/Expense toggle with per-ledger percentage bars",
             "AI-powered expense analysis — GPT-5.2 suggests cost-reduction insights",
             "Powered by `all_ledgers`, `profit_loss`, `bank_cash_ledgers` (synced by Desktop Agent)",
         ]),
        ("Busy Accounting Sync Agent", "NEW",
         "FLOWRA now supports Busy Accounting Software in addition to Tally. A new lightweight Windows agent reads "
         "Busy `.bds` (MS Access) files, syncs all voucher types, and uses cursor-based row streaming so it never spikes RAM.",
         [
             "Light-themed Tkinter GUI — no command prompt",
             "Sub-100 MB RAM ceiling even on 100K+ voucher datasets",
             "Auto-discovers FYs from `db{year}.bds` filenames",
             "Multi-company support, full + quick-sales sync modes",
             "Live sync-progress events mirror the Tally agent (visible in web UI)",
             "Tally v9 agent + Busy v1 agent both maintained in parallel",
         ]),
        ("Multi-Company Auto-Discovery",
         "ENHANCED",
         "Sync more than one company without configuring each one. The desktop agent reports every Tally/Busy company found, "
         "FLOWRA registers a UUID mapping, and the web UI shows a clean Company Switcher in the navbar.",
         [
             "Plan-based company limits (Starter 1 / Professional 3 / Enterprise unlimited)",
             "Last-sync timestamp and agent badge per company in switcher",
             "Per-company subscription expiry & sync gating",
             "Branch-ledger toggle in CRM Outstanding (include/exclude branch transfers)",
         ]),
        ("Agent Version Badges", "NEW",
         "Every synced company shows a badge (blue Tally vX or amber Busy vX) so admins immediately see which agent "
         "is responsible for that company's data — useful when you run mixed Tally/Busy operations.",
         []),
        ("Refreshed Onboarding Tour", "ENHANCED",
         "A 19-step interactive tour that now covers every new menu (Salesman, Dispatch, CA Corner, Sync History, Activity), "
         "auto-skips any feature your plan doesn't include, and can be replayed anytime from the user menu.",
         []),
        ("CRM Outstanding — FY-aware reverse-computation", "FIX",
         "The historic FY opening-balance calculation is now correct across all financial years. We reverse-compute "
         "earlier-FY opening balances from Tally's current-FY closing, eliminating the double-counting bugs from earlier versions.",
         []),
        ("Customer Targets & Follow-ups",
         "ENHANCED",
         "Set monthly targets per customer, add follow-up notes with reminders, and export the entire CRM as Excel.",
         []),
        ("Insider Result + AI Reports", "AI",
         "GPT-5.2 powered narrative reports — slow movers, customer-shift anomalies, payment-behaviour deviation, "
         "all written in plain English. Insider Result shows the most pressing patterns as quick cards on the dashboard.",
         []),
        ("Brand Suite Foundation",
         "FOUNDATION",
         "The FLOWRA brand kit (`@flowra/brand-kit`) and the parent suite landing at flowralive.in have been built — "
         "preparing the path for FLOWRA Tasks and FLOWRA Loyalty as independent companion products.",
         []),
    ]

    badge_color = {"NEW": SUCCESS, "ENHANCED": PRIMARY, "FIX": colors.HexColor("#F59E0B"),
                   "AI": ACCENT, "FOUNDATION": colors.HexColor("#0EA5E9")}

    for sec in sections:
        title, badge, desc, items = sec[0], sec[1], sec[2], sec[3] if len(sec) > 3 else []
        # Title row with badge
        bg = badge_color.get(badge, MUTED)
        head = Table([[
            Paragraph(f"<b>{title}</b>", s["FlowraH1"]),
            Paragraph(f"<para alignment='right'><font color='{bg.hexval()}'><b>{badge}</b></font></para>", s["FlowraBodyTight"]),
        ]], colWidths=[5.2 * inch, 1.2 * inch])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        elems.append(head)
        elems.append(Paragraph(desc, s["FlowraBody"]))
        if items:
            elems.append(bullets(items, s))
        elems.append(Spacer(1, 6))

    elems += [
        Spacer(1, 14),
        callout_table(
            "How to enable any of these for your tenant",
            "Most of these features are available out-of-the-box on Professional and Enterprise plans. "
            "If a tile isn't showing up in your menu, it's a feature-gating choice — write to "
            "<font color='#0052FF'>hello@flowralive.in</font> with your tenant ID and we'll enable it. ",
            s
        )
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Whats_New.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# 2. PRODUCT PRESENTATION (sales pitch deck)
# ─────────────────────────────────────────────────────────
def build_presentation():
    s = make_styles()
    elems = []

    # COVER
    elems += [
        Spacer(1, 0.6 * inch),
        Paragraph("FLOWRA INSIGHTS", s["FlowraEyebrow"]),
        Paragraph("Tally & Busy data,<br/>finally working for you.", s["FlowraTitle"]),
        Spacer(1, 14),
        Paragraph("Real-time analytics, CRM, dispatch, salesman orders and CA reports — synced directly from Tally Prime or Busy Accounting. Built for Indian SMEs.",
                  s["FlowraSubtitle"]),
        Spacer(1, 30),
        callout_table(
            "Who this deck is for",
            "Indian business owners, CFOs, accountants, and CAs who use Tally or Busy "
            "and want their data to do more than sit in a backup file.",
            s
        ),
        PageBreak(),
    ]

    # WHY FLOWRA
    elems += [
        Paragraph("WHY", s["FlowraEyebrow"]),
        Paragraph("Tally and Busy run the back office. FLOWRA runs the dashboard.", s["FlowraH1"]),
        Paragraph("Indian SMEs already trust Tally / Busy with their accounting. The problem isn't the data — it's the access. "
                  "Reports live on one Windows desktop. Salesmen can't see stock. CAs can't drill into a ledger. Owners can't see overdue payments without calling someone.",
                  s["FlowraBody"]),
        Paragraph("FLOWRA Insights is a thin, secure, real-time layer on top of your existing accounting — no migration, no data import, no risk.",
                  s["FlowraBody"]),
        Spacer(1, 16),
        feature_table([
            ("Sync source",      "Tally Prime (Agent v9) and Busy Accounting (Agent v1)"),
            ("Data residency",   "MongoDB Atlas, Mumbai (ap-south-1) — DPDP-compliant"),
            ("Encryption",       "256-bit at rest and in transit"),
            ("Sync frequency",   "Every 5 minutes (sales) / 20 minutes (full)"),
            ("Tenant isolation", "Every record tagged with tenant_id; cross-tenant access impossible"),
            ("Multi-company",    "Up to ~25 companies under one admin (plan-dependent)"),
        ], s),
        PageBreak(),
    ]

    # FEATURE OVERVIEW (mapped to current menus)
    elems += [
        Paragraph("WHAT'S INSIDE", s["FlowraEyebrow"]),
        Paragraph("11 modules, all working from the same synced data.", s["FlowraH1"]),
    ]
    modules = [
        ("Dashboard",          "Total Sales, Inventory Items, Low Stock, FY Sales Value, Overdue Payments, Recent Transactions, Top Customers."),
        ("Sales",              "All sales vouchers with filters, search, drill-down, and Excel export."),
        ("CRM",                "Customer outstanding (FY-aware), targets, follow-ups, branch toggle, ageing buckets, payment behaviour."),
        ("Inventory",          "Stock items with auto-reorder based on 2-month sales velocity, movement analysis, low-stock alerts."),
        ("Analytics",          "Inventory movement, below-cost sales, sales frequency, customer-item breakdown, SPIP analysis."),
        ("Salesman Orders",    "Mobile-first order collection, customer mapping, approval workflow, billing verification."),
        ("Dispatch Terminal",  "Kanban board, transporter/porter settlement, Close-of-Day PDF, document uploads, online orders."),
        ("CA Corner",          "Cash Flow, P&L (monthly/annual), Balance Sheet, ledger drill-down, AI expense insights."),
        ("AI Reports",         "GPT-5.2 narrative reports — sales trends, customer insights, inventory movement."),
        ("Insider Result",     "AI cards on the dashboard surfacing slow movers, customer drift, anomalies."),
        ("Sync History",       "Per-cycle log of every sync — agent version (Tally / Busy), counts, FY, mode."),
    ]
    elems.append(feature_table(modules, s))
    elems.append(PageBreak())

    # PRICING
    elems += [
        Paragraph("PRICING", s["FlowraEyebrow"]),
        Paragraph("Three plans. Pay annually for two months free.", s["FlowraH1"]),
    ]
    pricing = [
        ("Starter — ₹999 / month",
         "1 company, 2 employees. Dashboard, Sales, Inventory, Tally* sync. Perfect for small businesses getting started."),
        ("Professional — ₹2,499 / month",
         "3 companies, 5 employees. Adds CRM, Outstanding tracking, Movement analytics, Excel/PDF exports."),
        ("Enterprise — ₹3,799 / month",
         "Unlimited companies & employees. Adds CA Corner, Dispatch Terminal, Salesman Orders, AI Reports, Insider Result, priority support."),
    ]
    for title, body in pricing:
        elems.append(Paragraph(f"<b>{title}</b>", s["FlowraH2"]))
        elems.append(Paragraph(body, s["FlowraBody"]))
    elems.append(Spacer(1, 12))
    elems.append(callout_table(
        "Free 14-day trial",
        "All plans include a 14-day no-credit-card trial. Connect your Tally or Busy in <2 minutes and start seeing data immediately. "
        "Cancel anytime — your data exports as Excel/JSON in one click.",
        s
    ))
    elems.append(PageBreak())

    # CONTACT
    elems += [
        Paragraph("NEXT STEP", s["FlowraEyebrow"]),
        Paragraph("Try FLOWRA Insights today.", s["FlowraH1"]),
        Paragraph("Sign up at <b>insights.flowralive.in</b>, install the desktop sync agent (5 min), pick your plan when ready.", s["FlowraBody"]),
        Spacer(1, 12),
        feature_table([
            ("Sign up",      "https://insights.flowralive.in"),
            ("Suite home",   "https://flowralive.in"),
            ("Sales / Demo", "hello@flowralive.in"),
            ("WhatsApp",     "On request — shared after signup"),
        ], s),
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Presentation.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# 3. CUSTOMER QUESTIONNAIRE
# ─────────────────────────────────────────────────────────
def build_questionnaire():
    s = make_styles()
    elems = []

    elems += [
        Paragraph("PRE-ONBOARDING", s["FlowraEyebrow"]),
        Paragraph("FLOWRA Customer Needs Assessment", s["FlowraTitle"]),
        Paragraph("This questionnaire helps us configure FLOWRA for your business correctly the first time. "
                  "Please complete it before your onboarding call (or fill the online version at "
                  "<b>insights.flowralive.in/questionnaire</b>).",
                  s["FlowraSubtitle"]),
    ]

    sections = [
        ("Company Profile", [
            "Legal name and trade name of the business",
            "Industry / sector (e.g., Auto Parts, FMCG distribution, Retail, Pharma, Steel)",
            "City / state of operation",
            "Number of employees / users who will use FLOWRA",
            "Annual turnover band (≤1Cr / 1-5Cr / 5-25Cr / 25Cr+)",
            "Number of branches and warehouses",
        ]),
        ("Accounting Software (CRITICAL — picks the right Sync Agent)", [
            "Are you on Tally Prime or Busy Accounting? (or both)",
            "Tally version (release 2.x / 3.x / 4.x / Tally.ERP 9 — older version may need upgrade)",
            "Busy version, if applicable (Busy 21 / Busy 18 / older)",
            "How many companies in your accounting software?",
            "What is your current Financial Year start (e.g., 1-Apr-2025)?",
            "Approximate vouchers per month (sales + receipts + journals + purchase)",
        ]),
        ("CRM & Outstanding Tracking", [
            "Number of debtor (customer) ledgers",
            "Average outstanding amount and number of overdue invoices",
            "Do you set monthly targets per customer? (yes/no)",
            "Branch ledgers — should they appear in CRM Outstanding? (yes/no)",
            "Who manages collections (owner / accountant / dedicated team)?",
        ]),
        ("Salesman Order System (Enterprise plan)", [
            "Do you have field salesmen taking orders? Approximately how many?",
            "Do they currently use a mobile app, paper, or just phone calls?",
            "Should salesmen see your live stock, or only their mapped customers?",
            "Who approves orders before they go to dispatch?",
        ]),
        ("Dispatch Terminal (Enterprise plan)", [
            "Number of dispatches per day from your warehouse",
            "Do you use transporters? How many regular ones?",
            "Do you settle porter / hamali charges separately? (yes/no)",
            "Do you generate any Close-of-Day report today? In what format?",
            "Do you upload LR copies / dispatch documents currently?",
        ]),
        ("CA Corner — Reports for your Chartered Accountant", [
            "Does your CA need monthly P&L? (yes/no)",
            "Does your CA need a Balance Sheet view with ledger drill-down? (yes/no)",
            "Do you generate Cash Flow Statements today?",
            "Would AI-powered expense insights be useful?",
            "Is your CA in-house or external? Should they get a separate login?",
        ]),
        ("GST & Compliance", [
            "Is your GSTIN active and verified? Provide GSTIN.",
            "Do you file GSTR-1 / GSTR-3B / GSTR-2B reconciliation manually today?",
            "Would you like FLOWRA to support GSTR JSON upload + reconciliation? (planned feature)",
            "DPDP Act 2023 compliance / data residency in India — required? (yes/no)",
        ]),
        ("Subscription & Plan", [
            "Preferred plan: Starter / Professional / Enterprise",
            "Annual or monthly billing?",
            "Special requirements for the Enterprise plan? (white-label, custom report, integrations)",
            "Decision-maker email + WhatsApp number for invoice delivery",
        ]),
    ]

    for title, qs in sections:
        elems.append(Paragraph(title, s["FlowraH1"]))
        elems.append(bullets(qs, s))
        elems.append(Spacer(1, 8))

    elems += [
        Spacer(1, 12),
        callout_table(
            "How to submit",
            "Complete the online version at <b>insights.flowralive.in/questionnaire</b> "
            "(saves your responses against your tenant), or email this PDF filled-in to "
            "<font color='#0052FF'>hello@flowralive.in</font>. Your onboarding manager will reach out within 1 business day.",
            s
        ),
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Customer_Questionnaire.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# 4. TRAINING BOOKLET
# ─────────────────────────────────────────────────────────
def build_training():
    s = make_styles()
    elems = []

    elems += [
        Paragraph("END-USER TRAINING", s["FlowraEyebrow"]),
        Paragraph("FLOWRA Insights — Training Booklet", s["FlowraTitle"]),
        Paragraph("A short, screen-by-screen guide for the people who will use FLOWRA every day. "
                  "Read once, refer back when needed.", s["FlowraSubtitle"]),
        Spacer(1, 8),
    ]

    chapters = [
        ("1. Logging In",
         "Open https://insights.flowralive.in. Use the email and password sent by your admin. "
         "On first login, an interactive tour walks you through every menu. You can replay it anytime from the user menu (top right) → Replay Tour."),
        ("2. The Navbar",
         "Top of every page. From left: FLOWRA logo, current company switcher (click to change companies if you have access to more than one), the menu items your plan unlocks, financial-year selector, branch toggle, sync status indicator (green = connected), and your profile menu."),
        ("3. Dashboard",
         "Your business at a glance — Total Sales (all FYs), Inventory Items, Low Stock count, FY Sales Value, Overdue Payments banner, Recent Transactions, and Top Customers. Click any number to drill in."),
        ("4. Sales",
         "Every sales voucher synced from Tally / Busy. Filters: date range, customer, salesman, FY. Click a row to see line items. Export the filtered list as Excel."),
        ("5. CRM",
         "Customer Outstanding tab: ageing buckets (0–30, 31–60, 61–90, 90+), branch toggle (include/exclude branch transfers), search by name. "
         "Targets tab: set monthly targets per customer. Follow-ups tab: add notes with reminders."),
        ("6. Inventory",
         "All stock items with quantity, value, and Sale Price (Tally STDPRICE master). Auto-Reorder: click the button to set smart reorder levels based on the last 2 months' sales velocity. Low-stock items are highlighted in red. "
         "**A/B/C/D categorisation** — click any pill in the row to tag a single item, or click 'Auto-ABC' to apply Pareto 80-15-4-1 across the whole catalog. Filter the table by tier from the dropdown."),
        ("7. Analytics",
         "Inventory movement (slow / fast movers), Below-cost sales, Sales frequency, Customer-item matrix, SPIP, and the new **Category Sales** tab — pick A/B/C/D and drill into each item's top customers, frequency, and current stock. CSV export per category."),
        ("8. Salesman Orders (if your plan includes it)",
         "Salesmen log in on their phone, see only their mapped customers and live stock, place an order, and submit. "
         "Admins approve / reject / hold from the Salesman Orders → Approval Queue. Approved orders appear on the Dispatch Terminal automatically. "
         "Salesmen also get a personal **Dashboard** with Achieved / Expected YTD / Monthly Target / Achievement %, plus customer-wise drill-down."),
        ("8a. Beat Run Today (Salesman)",
         "Auto-derived from your beat plan filtered by today's day-of-week. Tap a customer to mark visited (IST timestamp). "
         "Add unplanned visits in the NEW box — they're tagged NEW until the customer appears in synced Tally data. "
         "**Beat History** is read-only — past dates are locked, click any row for the detail view. Admins audit any salesman's runs from useradmin Salesman → Beat Runs."),
        ("9. Dispatch Terminal (if your plan includes it)",
         "Kanban board with swim-lanes: Pending → Packed → Loaded → Out → Delivered. Drag cards across lanes as they progress. "
         "Each card has: customer, items, transporter, LR number, document uploads. End-of-day: click 'Close of Day' for a PDF summary you can share on WhatsApp. "
         "Dispatch employees see the SAME admin view — only the Employees tab is hidden."),
        ("10. CA Corner",
         "Cash Flow: 3-section indirect method (Operating, Investing, Financing). "
         "P&L: monthly + annual; click any ledger to drill into transactions — **matches Tally exactly to the rupee**. "
         "Balance Sheet: Assets vs Liabilities + Capital, expandable, auto-balanced via P&L A/c residual. "
         "AI Expense Insights: ask GPT-5.2 to find your largest cost-saving opportunities."),
        ("11. AI Reports & Insider Result",
         "Both use GPT-5.2 to write narrative reports in plain English. AI Reports gives you long-form analysis on demand; Insider Result surfaces the most pressing patterns as quick cards."),
        ("12. Sync History",
         "Timeline of every sync from your desktop agent. Each row shows date/time, FY, items synced, and which agent ran it (blue 'Tally vX' or amber 'Busy vX')."),
        ("13. Setup",
         "First-time setup: download the Tally or Busy desktop agent, log in inside the agent with your FLOWRA credentials, point it at your Tally/Busy data folder, click Full Sync. Repeat for each company. "
         "**Re-run Full Sync after upgrading to Tally agent v9.6.0** to capture STANDARDPRICE for every stock item."),
        ("14. Profile & User Menu (top-right)",
         "Profile & Security: change password, manage employees, manage salesmen. **Export Your Data**: download a ZIP of every record FLOWRA stores for your tenant (DPDP Act 2023 right-to-portability — manifest + one JSON per collection). Replay Tour: re-watch the onboarding tour. Switch Company: jump between synced companies. Logout."),
        ("15. Mobile Use",
         "FLOWRA is fully responsive — Dashboard, Sales, CRM, Salesman Orders and Dispatch all work on phones. The full menu collapses into a hamburger button (top-left). "
         "Salesmen are expected to work mainly on phones."),
    ]

    for title, body in chapters:
        elems.append(Paragraph(title, s["FlowraH2"]))
        elems.append(Paragraph(body, s["FlowraBody"]))

    elems += [
        Spacer(1, 16),
        callout_table(
            "Need help?",
            "Email <b>hello@flowralive.in</b> with your tenant ID (visible in Profile). Our team responds within 1 business day. "
            "For urgent issues during dispatch hours, your account manager will share a WhatsApp number after onboarding.",
            s
        ),
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Training_Booklet.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# 5. DEPLOYMENT GUIDE (admin/IT setup)
# ─────────────────────────────────────────────────────────
def build_deployment_guide():
    s = make_styles()
    elems = []

    elems += [
        Paragraph("ADMIN / IT SETUP", s["FlowraEyebrow"]),
        Paragraph("FLOWRA Insights — Deployment Guide", s["FlowraTitle"]),
        Paragraph("Step-by-step setup for IT admins and accountants. Get your Tally or Busy connected to FLOWRA in under 30 minutes.", s["FlowraSubtitle"]),
        Spacer(1, 8),

        Paragraph("1. Decide the Sync Source", s["FlowraH1"]),
        Paragraph("FLOWRA supports two accounting systems. You'll install ONE of these on the same Windows machine where Tally / Busy runs.", s["FlowraBody"]),
        feature_table([
            ("Tally Sync Agent v9",
             "For Tally Prime (Release 2 and above). Reads via Tally's HTTP/XML port (default 9000). No file access required — Tally must be running."),
            ("Busy Sync Agent v1",
             "For Busy Accounting (Busy 21+). Reads `.bds` files (MS Access / Jet 4.0) directly. Busy can be running or closed. "
             "Requires the Microsoft Access Database Engine 64-bit redistributable."),
        ], s),
        Spacer(1, 12),

        Paragraph("2. Pre-requisites", s["FlowraH1"]),
        bullets([
            "A Windows 10 / 11 PC where Tally or Busy lives. Admin rights to install Python.",
            "Stable internet connection (the agent uploads in 500-record chunks; can pause/resume on flaky links).",
            "Your FLOWRA admin login (the email/password used to register at insights.flowralive.in).",
            "For Tally: TallyPrime configured to allow API access (Gateway → F1 Help → Settings → Connectivity → Client/Server → Action: Both, Port: 9000).",
            "For Busy: Microsoft Access Database Engine 2016 64-bit redistributable installed (free download from Microsoft).",
        ], s),
        Spacer(1, 12),

        Paragraph("3. Install the Agent", s["FlowraH1"]),
        Paragraph("Each agent ships as a single Python file. A one-click `.exe` installer is on our roadmap (Q2 2026).", s["FlowraBody"]),
        bullets([
            "Install Python 3.9+ from python.org (tick 'Add to PATH' during install).",
            "For Tally: <font face='Courier'>pip install requests pywin32</font>",
            "For Busy: <font face='Courier'>pip install pyodbc requests cryptography</font>",
            "Download the agent file from your FLOWRA admin → Setup → Download Agent.",
            "Double-click the agent file. The light-themed GUI opens.",
            "Enter Server URL (https://insights.flowralive.in), your username, and password.",
            "For Busy: click Browse and select your Busy data folder (the one containing `db.bds` and `db{year}.bds`).",
            "Pick a company from the list, pick the FY, click Full Sync. First sync may take 5–20 minutes depending on data volume.",
        ], s),
        Spacer(1, 12),

        Paragraph("4. Multi-Company Setup", s["FlowraH1"]),
        Paragraph("Repeat the Full Sync step for each company in your accounting software. FLOWRA auto-discovers the companies and "
                  "creates a UUID mapping per company. Plan limits: Starter = 1 company, Professional = 3, Enterprise = unlimited.", s["FlowraBody"]),

        Paragraph("5. Setting up Roles", s["FlowraH1"]),
        feature_table([
            ("Admin",      "Full access. The first signup automatically becomes the admin. Configure features for employees in Profile → Employees."),
            ("Employee",   "Restricted access — admin chooses which menus they see. Cannot change tenant settings."),
            ("Salesman",   "A specialised employee role. Created in Profile → Employees with role 'salesman'. Maps customers via Salesman → Manage."),
            ("Dispatch",   "Restricted to Dispatch Terminal only. Cannot see CRM or financials. For warehouse-floor users."),
            ("Super Admin","FLOWRA platform team only. Manages cross-tenant operations, plan changes, billing."),
        ], s),
        Spacer(1, 12),

        Paragraph("6. Sync Schedule", s["FlowraH1"]),
        Paragraph("The agent runs two cycles automatically once started:", s["FlowraBody"]),
        bullets([
            "Quick Sales Sync — every 5 minutes (sales vouchers only, fast)",
            "Full Sync — every 20 minutes (all data types: sales, receipts, journals, customers, inventory, ledgers, P&L)",
            "Manual Resync — triggerable from FLOWRA web UI; agent picks it up within seconds",
        ], s),

        Paragraph("7. Security Considerations", s["FlowraH1"]),
        bullets([
            "All agent ↔ FLOWRA communication is HTTPS (TLS 1.3)",
            "HMAC-signed sync tokens prevent stolen-credential replay attacks",
            "Subscription expiry gates sync — expired tenants get a clear error",
            "Local agent config stored on the Windows machine (no plain-text credentials)",
            "FLOWRA never accesses your Tally / Busy directly — the agent always pushes; nothing pulls",
        ], s),

        Paragraph("8. Troubleshooting", s["FlowraH1"]),
        feature_table([
            ("Tally agent: 'Cannot connect to Tally'", "Tally must be running and Action set to Both in Connectivity Settings. Check port 9000 isn't blocked by firewall."),
            ("Busy agent: pyodbc error",               "Install Microsoft Access Database Engine 2016 64-bit (matches Python's bit-ness)."),
            ("Sync silently stops",                    "Check Sync History page in the web UI. Most common cause: subscription expired or password changed since agent was started."),
            ("Wrong company appears",                  "Multi-company mapping issue — go to Setup → Reset Company Mapping (admin only) and re-sync."),
            ("Outstanding doesn't match Tally",        "Toggle the Branch filter in CRM. Branch ledgers can double-count if not excluded."),
        ], s),

        Paragraph("9. Backups & Data Portability", s["FlowraH1"]),
        Paragraph("FLOWRA runs Tier-1 backups on the host pod and gives every tenant a self-service data export.", s["FlowraBody"]),
        bullets([
            "Daily automated MongoDB dump at 02:00 IST — last 30 backups retained, gzipped archives",
            "SuperAdmin → Backups tab: Run Now, list, download, delete on demand",
            "Tier-2 (MongoDB Atlas point-in-time recovery, region: Mumbai) is the next migration step — see DATABASE_STRATEGY.md",
            "Tenant Admin → user menu → Export Your Data: ZIP with one JSON per collection + manifest (DPDP Act 2023 right-to-portability)",
            "Strict tenant isolation enforced server-side — your data is never mixed with another tenant's; password hashes and system audit logs are never included in your export",
            "Every export and backup logged to the audit trail for compliance",
        ], s),
        Spacer(1, 12),

        Paragraph("10. Going to Production", s["FlowraH1"]),
        bullets([
            "Set the agent to Auto-Start with Windows (right-click → Run on startup)",
            "Subscribe to FLOWRA Status (status.flowralive.in) for sync health alerts",
            "Enable WhatsApp digest in Profile to receive a daily sync-health summary",
            "Add 'Sync Failed' email alert in Notifications → Email triggers (Resend integration required)",
        ], s),

        Spacer(1, 14),
        callout_table(
            "Need help with deployment?",
            "Book a free 30-minute video call with our deployment manager: <b>hello@flowralive.in</b>. "
            "We'll set up your agent, do the first sync together, and stay on the call until everything works.",
            s
        ),
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Deployment_Guide.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# 6. COMING SOON (public roadmap)
# ─────────────────────────────────────────────────────────
def build_coming_soon():
    s = make_styles()
    elems = []

    elems += [
        Paragraph("PUBLIC ROADMAP", s["FlowraEyebrow"]),
        Paragraph("FLOWRA — What's Coming Next", s["FlowraTitle"]),
        Paragraph("We don't ship surprises. Here's what's on our list for the next 12 months. Dates are intentions, not promises.", s["FlowraSubtitle"]),
        Spacer(1, 8),

        Paragraph("Quarter Ahead (Q2 2026)", s["FlowraH1"]),
        feature_table([
            ("PyInstaller `.exe` installers",   "One-click setup for both Tally v9 and Busy v1 desktop agents. No Python install needed."),
            ("GSTR JSON Reconciliation",       "Upload GSTR-1 / 2B / 3B JSON inside CA Corner; auto-reconcile against your Tally / Busy vouchers, surface mismatches."),
            ("MongoDB Atlas Migration (Tier-2)", "Production move to Atlas M10 in Mumbai (ap-south-1) with point-in-time recovery on top of today's daily Tier-1 dumps."),
            ("DigitalOcean Phase-1 Deployment", "Sub-domain architecture (insights / tasks / loyalty) live on production droplets."),
            ("Audit Logs CSV Export",          "Full audit trail downloadable from SuperAdmin."),
        ], s),

        Paragraph("Mid-term (Q3-Q4 2026)", s["FlowraH1"]),
        feature_table([
            ("FLOWRA Tasks (suite app)",       "Team execution platform — assign, chase, close. tasks.flowralive.in"),
            ("FLOWRA Loyalty (suite app)",     "Loyalty engine for Indian retail — points, tiers, referrals, WhatsApp-native. loyalty.flowralive.in"),
            ("Payment Follow-up Automation",   "Email + WhatsApp reminders triggered on overdue invoices. Resend + WhatsApp Business API."),
            ("Sync Health Email Digest",       "Weekly summary email — per-company sync health, errors, missing days."),
            ("In-app New Feature Spotlight",   "Auto-show modal on login when major features ship. Re-uses tour infra."),
        ], s),

        Paragraph("Long-term Wishlist (2027+)", s["FlowraH1"]),
        feature_table([
            ("Mobile native apps (iOS + Android)", "React Native build of Salesman + Dispatch flows."),
            ("Embedded Stripe + Razorpay payments", "Send a payment link from CRM → auto-mark invoice as paid on receipt."),
            ("Direct GST API via GSP partnership",  "Real-time GSTN data instead of upload-based reconciliation. Requires GSP licensing."),
            ("FLOWRA Pulse",                       "AI assistant inside every screen — ask 'why is this customer overdue?' and get a one-paragraph explanation."),
            ("Marketplace integrations",            "Amazon, Flipkart, Meesho order auto-ingestion into Dispatch Terminal."),
        ], s),

        Spacer(1, 14),
        callout_table(
            "Tell us what to build",
            "We add a feature only when 2+ Indian business owners ask for it. If you'd like something on this list — or off it — write to "
            "<font color='#0052FF'>hello@flowralive.in</font> with your business context. The most-requested features get built first.",
            s
        ),
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Coming_Soon.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# 7. SOCIAL MEDIA KIT
# ─────────────────────────────────────────────────────────
def build_social_kit():
    s = make_styles()
    elems = []

    elems += [
        Paragraph("BRAND ASSETS", s["FlowraEyebrow"]),
        Paragraph("FLOWRA — Social Media Kit", s["FlowraTitle"]),
        Paragraph("Pre-approved copy and asset references for partners, resellers, and our own social channels.", s["FlowraSubtitle"]),
        Spacer(1, 8),

        Paragraph("Brand Voice Cheat-sheet", s["FlowraH1"]),
        bullets([
            "Indian English (favour 'organisation', 'cheque'; avoid Americanisms)",
            "Active voice; second-person ('You can…' not 'Users can…')",
            "₹ prefix, Indian comma system (1,67,17,990)",
            "Dates DD-MMM-YYYY (24-Apr-2026)",
            "No jargon a CA wouldn't say in a meeting",
            "Anti-patterns: 'Get started today!', 'Unleash', 'Revolutionary', 'Game-changing'",
        ], s),

        Paragraph("One-line Pitches", s["FlowraH1"]),
        feature_table([
            ("Long",    "FLOWRA is a family of focused SaaS tools for Indian SMEs — real-time analytics from Tally and Busy, CRM, dispatch, salesman ordering, CA reports, customer loyalty and team tasks."),
            ("Medium",  "Tally and Busy data, finally working for you. Real-time analytics, CRM, dispatch and CA reports."),
            ("Short",   "Software that runs your business — quietly."),
            ("Tagline", "One brand. Many tools. No lock-in."),
        ], s),

        Paragraph("Suggested Posts", s["FlowraH1"]),
        bullets([
            "Carousel — '11 modules inside FLOWRA Insights' (one slide per module)",
            "Reel — Tally → FLOWRA sync timeline (15s screen recording)",
            "Carousel — '3 outstanding-tracking mistakes Indian SMEs make' (CRM angle)",
            "Reel — Salesman placing an order on phone, admin approving, dispatch fulfilling",
            "Static — 'Built in India for Indian businesses' brand poster",
        ], s),

        Paragraph("Hashtag Stack", s["FlowraH1"]),
        Paragraph("#TallyAnalytics  #BusyAccounting  #IndianSME  #IndiaSaaS  #DigitalBharat  #IndianBusinessSoftware  "
                  "#CAtools  #GSTcompliance  #FLOWRA  #FLOWRAlive  #BuiltInIndia  #DPDP", s["FlowraBody"]),

        Paragraph("Brand Assets to Request", s["FlowraH1"]),
        bullets([
            "Logo (PNG 256/512/1024, SVG, light + dark)",
            "Brand colors: Primary #0052FF (apps) / #2563EB (suite). Accent #7C3AED.",
            "Fonts: Inter for everything. Cabinet Grotesk for hero headlines on apps.",
            "Screenshots: Dashboard, CRM Outstanding, Dispatch Kanban, CA Corner Balance Sheet (request via hello@flowralive.in)",
            "OG cover (1200×630) — for social link previews",
        ], s),

        Paragraph("Legal", s["FlowraH1"]),
        Paragraph("FLOWRA, FLOWRA Insights, FLOWRA Tasks, FLOWRA Loyalty are trademarks of FLOWRA. "
                  "Tally and Busy are trademarks of their respective owners and are used here for "
                  "interoperability description only — FLOWRA is not affiliated with or endorsed by them.",
                  s["FlowraSmall"]),

        Spacer(1, 14),
        callout_table(
            "Asset requests",
            "Email <b>hello@flowralive.in</b> with subject 'Brand assets — &lt;your channel&gt;'. "
            "Approved partners receive a link to a Drive folder with high-resolution PNG/SVG/MP4 assets.",
            s
        ),
    ]

    doc = doc_template(os.path.join(OUT_DIR, "FLOWRA_Social_Media_Kit.pdf"))
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    # NOTE: "What's New" is intentionally excluded here — it's owned by
    # scripts/generate_whats_new_pdf.py which reads /app/frontend/public/
    # whats_new.json (the single source of truth also consumed by the
    # user-admin Dashboard "What's New" panel). Running build_whats_new()
    # below would clobber the JSON-driven PDF with stale hardcoded content.
    builders = [
        ("Presentation",          build_presentation),
        ("Customer Questionnaire", build_questionnaire),
        ("Training Booklet",      build_training),
        ("Deployment Guide",      build_deployment_guide),
        ("Coming Soon",           build_coming_soon),
        ("Social Media Kit",      build_social_kit),
    ]
    for name, fn in builders:
        try:
            fn()
            print(f"  [OK]   {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            raise
    print("\nAll PDFs generated in:", OUT_DIR)
