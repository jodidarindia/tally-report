"""Generate the FLOWRA Insights vs Tally / Busy pain-point comparison chart.

Deliverables (saved to /app/frontend/public/charts/):
  flowra_vs_tally_busy_comparison.pdf  — Landscape A4, brand-styled, print-ready
  flowra_vs_tally_busy_comparison.png  — Portrait, mobile / WhatsApp shareable
"""
from pathlib import Path

from reportlab.lib import colors as rc
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

OUT = Path("/app/frontend/public/charts")
OUT.mkdir(parents=True, exist_ok=True)

# ───── BRAND ──────────────────────────────────────────────────────────────
NAVY = "#0F1B4C"
BLUE = "#2563EB"
AMBER = "#f59e0b"
RED = "#DC2626"
GREEN = "#10B981"
SOFT = "#F0F4FF"
STRIPE = "#F8FAFC"
GREY = "#64748B"

# ───── COMPARISON DATA (grouped by module) ────────────────────────────────
# Each dict = one row: {module, category, tally, busy, flowra}
ROWS = [
    # ── Access & Cloud ──
    {"module": "Access & Cloud",
     "category": "Mobile / anywhere access",
     "tally": "Desktop-only. Owner must sit at the office machine to see today's numbers.",
     "busy":  "Desktop-only. No first-party mobile app.",
     "flowra":"100% cloud + mobile-first UI. Owner, Salesman, Dispatch & CA each get their own dashboard on phone or laptop."},
    {"module": "Access & Cloud",
     "category": "Live data sync",
     "tally": "Data refreshes only when someone hits F12 / synchronises companies.",
     "busy":  "No auto-cloud push. SQL data locked to the office LAN.",
     "flowra":"Windows Sync Agent (v9.8.28) reads Tally / Busy every 60 s and pushes to encrypted Mumbai-region MongoDB."},
    {"module": "Access & Cloud",
     "category": "Multi-company / multi-branch view",
     "tally": "Only one open company at a time. Consolidation is manual.",
     "busy":  "Same one-company-at-a-time UX.",
     "flowra":"Single dashboard aggregates ALL companies + branches. Exclude-branch toggle for consolidated P&L."},

    # ── Analytics & Dashboards ──
    {"module": "Analytics",
     "category": "Owner dashboards",
     "tally": "Reports are tabular text. No visual analytics layer.",
     "busy":  "Very basic charts, none role-tuned.",
     "flowra":"Interactive dashboards with 11-month rolling trends, drill-downs, & AI narratives."},
    {"module": "Analytics",
     "category": "AI insights",
     "tally": "Zero AI layer.",
     "busy":  "Zero AI layer.",
     "flowra":"GPT-5 + Gemini powered \"Ask FLOWRA\" — natural-language Q&A on your own books, in English or Hindi."},
    {"module": "Analytics",
     "category": "Custom AI reports",
     "tally": "Requires TDL programming or Excel gymnastics.",
     "busy":  "Requires macros / external tools.",
     "flowra":"Type a question, get a structured chart + narrative in seconds. Saved to a shareable report history."},

    # ── Sales & Receivables ──
    {"module": "Sales & Receivables",
     "category": "Aging & follow-up",
     "tally": "Aging report is static — no thresholds, reminders, or external sharing.",
     "busy":  "Similar — reports run on-demand only.",
     "flowra":"Live receivables aging with thresholds, auto-email reminders, WhatsApp nudges, & top-defaulter panel."},
    {"module": "Sales & Receivables",
     "category": "Recovery workflow",
     "tally": "No native recovery workflow.",
     "busy":  "No native recovery workflow.",
     "flowra":"AI Calling Bot (rolling out) + WhatsApp templates + task-based follow-ups per customer."},

    # ── Inventory ──
    {"module": "Inventory",
     "category": "ABC classification",
     "tally": "No native ABC classification.",
     "busy":  "No native ABC classification.",
     "flowra":"Auto ABC classification based on rolling revenue + editable per item."},
    {"module": "Inventory",
     "category": "Movement analysis",
     "tally": "Manual filter reports; no fast-mover / slow-mover view.",
     "busy":  "Manual filter reports.",
     "flowra":"Movement analysis on a rolling 11-month window with valuation, velocity & fast/slow-mover tags."},
    {"module": "Inventory",
     "category": "Purchase Order generation",
     "tally": "Manual — accountant creates each PO from scratch.",
     "busy":  "Manual.",
     "flowra":"One-click AI-suggested PO from ABC + reorder level + last purchase price."},
    {"module": "Inventory",
     "category": "Group filters & exports",
     "tally": "Single-group filter; exports lose selected filters.",
     "busy":  "Basic filters; PDFs pre-set templates only.",
     "flowra":"Multi-group filter, filter-aware CSV / Excel / PDF exports with correct extensions & data."},

    # ── Salesman Field ──
    {"module": "Salesman App",
     "category": "Field ordering",
     "tally": "No native salesman app. Orders arrive on paper / WhatsApp; re-typed manually.",
     "busy":  "No first-party field-sales module.",
     "flowra":"Mobile Salesman App: beat plans, daily check-ins, order + payment Yes/No capture, close-day PDF report."},
    {"module": "Salesman App",
     "category": "Beat / route planning",
     "tally": "Doesn't exist.",
     "busy":  "Doesn't exist.",
     "flowra":"Weekly beat plans per salesman + auto-generated daily route + visited / unplanned distinction."},
    {"module": "Salesman App",
     "category": "Handover on attrition",
     "tally": "Manual — new salesman starts from scratch.",
     "busy":  "Manual.",
     "flowra":"One-click \"Copy customer mapping + beat plan\" from outgoing to incoming salesman."},

    # ── Dispatch & Logistics ──
    {"module": "Dispatch",
     "category": "Warehouse workflow",
     "tally": "No dispatch module — pickers use paper slips.",
     "busy":  "No dispatch module.",
     "flowra":"Kanban terminal: NEW → QUEUED → PACKED → DISPATCHED, plus porter assignment."},
    {"module": "Dispatch",
     "category": "LR / Bilty documents",
     "tally": "No place to attach LR / bilty photos to an invoice.",
     "busy":  "No document store.",
     "flowra":"Photo upload from dispatch phone → attached to invoice → visible to Owner & CA (Google Drive integration planned)."},

    # ── CA / Compliance ──
    {"module": "CA / Compliance",
     "category": "CA remote review",
     "tally": "CA takes a backup and opens Tally locally to review.",
     "busy":  "Similar — CA opens the client's file.",
     "flowra":"CA Corner: read-only tenant-scoped view of vouchers, GST, TDS, balance sheet — accessible from any laptop."},
    {"module": "CA / Compliance",
     "category": "GST reconciliation",
     "tally": "Manual GSTR JSON downloads + Excel reconciliation.",
     "busy":  "Manual.",
     "flowra":"GST Portal integration (roadmap) — auto reconciliation & discrepancy list inside CA Corner."},

    # ── Notifications ──
    {"module": "Notifications",
     "category": "Alerts / triggers",
     "tally": "No email / WhatsApp alerts. Owner must check manually.",
     "busy":  "Same — no push notifications.",
     "flowra":"Auto-triggered emails for insights, high-risk receivables, dispatch bottlenecks. Global CCs & branded templates."},

    # ── Multi-FY & Roles ──
    {"module": "Multi-FY & Roles",
     "category": "Financial-year handling",
     "tally": "Every new FY often means a fresh company file / heavy re-open cycle.",
     "busy":  "New-year re-configuration.",
     "flowra":"Multi-FY built-in. Owner toggles FY at top; salesman FY-scoped mappings; auto-rollover."},
    {"module": "Multi-FY & Roles",
     "category": "Role-based access",
     "tally": "Only Admin + limited Data Entry. No dispatch-only or salesman-only role.",
     "busy":  "Multi-user but complex to configure.",
     "flowra":"Admin / Employee / Salesman / Dispatch / CA out of the box. Employee activate-deactivate toggle."},

    # ── Data safety ──
    {"module": "Data Safety",
     "category": "Tenant isolation",
     "tally": "N/A — single-tenant local install; backup restores are risky.",
     "busy":  "N/A.",
     "flowra":"Multi-tenant SaaS with query-level tenant isolation. Two customers can never see each other's data."},
    {"module": "Data Safety",
     "category": "Backups & DR",
     "tally": "Manual .tsb file, often on the same machine.",
     "busy":  "Manual .bkp file — often local.",
     "flowra":"Continuous MongoDB Atlas backups (Mumbai region) + on-demand encrypted download."},

    # ── Value-adds ──
    {"module": "Value-adds",
     "category": "Loyalty program",
     "tally": "Not offered. SME has to buy Capillary / LoyaltyXpert separately.",
     "busy":  "Not offered.",
     "flowra":"Built-in FLOWRA Loyalty: points on every Tally sales voucher; Silver / Gold / Platinum tiers; redemption on next invoice."},
    {"module": "Value-adds",
     "category": "Task & workflow engine",
     "tally": "No native task or reminder engine.",
     "busy":  "No native task engine.",
     "flowra":"Built-in FLOWRA Tasks: assign to salesman / dispatch / CA. Tally-data-aware triggers auto-create tasks."},
    {"module": "Value-adds",
     "category": "Referral / growth",
     "tally": "Not offered.",
     "busy":  "Not offered.",
     "flowra":"Built-in referral code system with rewards ledger for existing users."},
    {"module": "Value-adds",
     "category": "Bilingual UI",
     "tally": "English only.",
     "busy":  "English only.",
     "flowra":"English + Hindi bilingual UI — rolling out module by module."},

    # ── Ops & Pricing ──
    {"module": "Ops & Pricing",
     "category": "Auto-update",
     "tally": "Manual .exe patch each year — customer downloads & installs.",
     "busy":  "Manual patch downloads.",
     "flowra":"Zero-touch auto-updating agent (v9.8.28 in prod). Backend hot-reloads without downtime."},
    {"module": "Ops & Pricing",
     "category": "Pricing model",
     "tally": "Perpetual license + AMC — high upfront cost.",
     "busy":  "Perpetual license + AMC.",
     "flowra":"Subscription SaaS — currently in pilot; commercial rollout post-pilot with per-user add-ons."},
    {"module": "Ops & Pricing",
     "category": "Vendor lock-in / integrations",
     "tally": "Tally-only. SME stitches 4-5 third-party apps to fill gaps.",
     "busy":  "Busy-only.",
     "flowra":"One integrated suite — Sales, Inventory, Salesman, Dispatch, CA, AI, Tasks, Loyalty, Referral."},
]

# ───── STYLES ─────────────────────────────────────────────────────────────
title_style = ParagraphStyle(
    "title", fontName="Helvetica-Bold", fontSize=22, textColor=rc.HexColor(NAVY),
    leading=26, spaceAfter=2,
)
sub_style = ParagraphStyle(
    "sub", fontName="Helvetica-Oblique", fontSize=11, textColor=rc.HexColor(BLUE),
    leading=14, spaceAfter=10,
)
mod_style = ParagraphStyle(
    "mod", fontName="Helvetica-Bold", fontSize=9.5, textColor=rc.HexColor(BLUE),
    leading=11, alignment=0,
)
cat_style = ParagraphStyle(
    "cat", fontName="Helvetica-Bold", fontSize=9.5, textColor=rc.HexColor(NAVY),
    leading=11,
)
pain_style = ParagraphStyle(
    "pain", fontName="Helvetica", fontSize=8.5, textColor=rc.HexColor("#334155"),
    leading=11, spaceAfter=0,
)
flowra_style = ParagraphStyle(
    "flowra", fontName="Helvetica", fontSize=8.5, textColor=rc.HexColor(NAVY),
    leading=11,
)
header_style = ParagraphStyle(
    "hdr", fontName="Helvetica-Bold", fontSize=11, textColor=rc.white,
    leading=13, alignment=1,
)
header_sub_style = ParagraphStyle(
    "hdr_sub", fontName="Helvetica-Oblique", fontSize=8.5,
    textColor=rc.HexColor(SOFT), leading=10, alignment=1,
)


# ────────────────────────────────────────────────────────────────────────────
def _draw_chrome(canvas, doc):
    canvas.saveState()
    # Top accent bar
    canvas.setFillColor(rc.HexColor(BLUE))
    canvas.rect(0, doc.pagesize[1] - 6 * mm, doc.pagesize[0], 6 * mm, fill=1, stroke=0)
    # Footer
    canvas.setFillColor(rc.HexColor(GREY))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        15 * mm, 8 * mm,
        "Jodidar India · FLOWRA Insights · Organize. Automate. Accelerate. · flowralive.in",
    )
    canvas.drawRightString(
        doc.pagesize[0] - 15 * mm, 8 * mm,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def _make_row(r):
    """Convert one data dict → a rendered [cat, tally, busy, flowra] row."""
    cat_cell = [
        Paragraph(f"<font color='#2563EB'>{r['module']}</font>", mod_style),
        Paragraph(r["category"], cat_style),
    ]
    tally_cell = Paragraph("× " + r["tally"], pain_style)
    busy_cell = Paragraph("× " + r["busy"], pain_style)
    flowra_cell = Paragraph("✓ " + r["flowra"], flowra_style)
    return [cat_cell, tally_cell, busy_cell, flowra_cell]


def _build_table_style(nrows):
    """Table style — dark navy header, alternating stripes, pain-column tint."""
    # nrows counts data rows only; header is row 0
    ts = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), rc.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), rc.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        # Body cells
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 1), (-1, -1), 5),
        ("RIGHTPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        # Column tints
        ("BACKGROUND", (0, 1), (0, -1), rc.HexColor("#EEF3FF")),   # Category tint
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.35, rc.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, rc.HexColor(AMBER)),
    ]
    # Alternate stripes on the pain/solution columns
    for i in range(1, nrows + 1):
        if i % 2 == 0:
            ts.append(("BACKGROUND", (1, i), (2, i), rc.HexColor("#FFF7ED")))
            ts.append(("BACKGROUND", (3, i), (3, i), rc.HexColor("#F0FDF4")))
        else:
            ts.append(("BACKGROUND", (1, i), (2, i), rc.HexColor("#FEF2F2")))
            ts.append(("BACKGROUND", (3, i), (3, i), rc.HexColor("#ECFDF5")))
    return TableStyle(ts)


def render_pdf(out_path):
    doc = SimpleDocTemplate(
        out_path,
        pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=18 * mm, bottomMargin=15 * mm,
        title="FLOWRA vs Tally / Busy — Pain-point Comparison",
        author="Jodidar India",
    )
    story = []

    # Title block
    story.append(Paragraph(
        "FLOWRA <font color='#2563EB'>Insights</font> vs Tally &amp; Busy",
        title_style,
    ))
    story.append(Paragraph(
        "Column-by-column mapping of the pain points that Indian SMEs live with today — "
        "and exactly what FLOWRA Insights ships to solve each one.",
        sub_style,
    ))

    # Legend
    legend_data = [[
        Paragraph("<font color='#DC2626'><b>×</b></font> pain / limitation", pain_style),
        Paragraph("<font color='#10B981'><b>✓</b></font> FLOWRA solution", flowra_style),
        Paragraph("<font color='#2563EB'><b>Module</b></font> = FLOWRA area", pain_style),
    ]]
    legend = Table(legend_data, colWidths=[85 * mm, 90 * mm, 85 * mm])
    legend.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rc.HexColor(SOFT)),
        ("BOX", (0, 0), (-1, -1), 0.4, rc.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(legend)
    story.append(Spacer(1, 4 * mm))

    # Header row (repeats on every page — via repeatRows=1)
    header = [
        Paragraph("Module &amp; Area", header_style),
        Paragraph("Tally Pain", header_style),
        Paragraph("Busy Pain", header_style),
        Paragraph("FLOWRA Insights Solution", header_style),
    ]

    # Landscape A4 usable width ≈ 273 mm
    col_widths = [50 * mm, 74 * mm, 74 * mm, 75 * mm]

    # Chunk rows into pages (~ 8 rows per landscape A4 fit comfortably)
    rows_per_page = 8
    chunks = [ROWS[i:i + rows_per_page] for i in range(0, len(ROWS), rows_per_page)]

    for idx, chunk in enumerate(chunks):
        data = [header] + [_make_row(r) for r in chunk]
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(_build_table_style(len(chunk)))
        story.append(tbl)
        if idx < len(chunks) - 1:
            story.append(PageBreak())
            story.append(Paragraph(
                "FLOWRA <font color='#2563EB'>Insights</font> vs Tally &amp; Busy "
                "<font color='#64748B' size='11'>(continued)</font>",
                title_style,
            ))
            story.append(Spacer(1, 3 * mm))

    # Closing note
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "<b>Bottom line —</b> FLOWRA is not a replacement for Tally or Busy. It sits ON TOP of them, "
        "reads their data every 60 seconds, and adds the cloud + mobile + AI + workflow layer that "
        "Indian SMEs need in 2026. Zero workflow change for the accountant. Zero disruption during "
        "install. One integrated suite instead of five disjointed tools.",
        pain_style,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<i>Prepared by Jodidar India, Raipur · flowralive.in · support@flowralive.in · +91 81204 70018</i>",
        ParagraphStyle("foot", parent=pain_style, alignment=1, fontSize=8,
                       textColor=rc.HexColor(GREY)),
    ))

    doc.build(story, onFirstPage=_draw_chrome, onLaterPages=_draw_chrome)


# ────────────────────────────────────────────────────────────────────────────
def render_png(out_path, pdf_path):
    """Rasterise the PDF pages into a single tall PNG for mobile sharing."""
    import pypdfium2 as pdfium
    from PIL import Image

    pdf = pdfium.PdfDocument(pdf_path)
    pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        # 150 DPI = scale 150/72 ≈ 2.083
        pil = page.render(scale=150 / 72).to_pil()
        pages.append(pil.convert("RGB"))

    if not pages:
        raise RuntimeError("PDF has no pages")
    w = pages[0].width
    gap = 24
    total_h = sum(p.height for p in pages) + (len(pages) - 1) * gap
    combined = Image.new("RGB", (w, total_h), (248, 250, 252))
    y = 0
    for i, im in enumerate(pages):
        combined.paste(im, (0, y))
        y += im.height + (gap if i < len(pages) - 1 else 0)
    combined.save(out_path, quality=88, optimize=True)


def main():
    pdf = OUT / "flowra_vs_tally_busy_comparison.pdf"
    png = OUT / "flowra_vs_tally_busy_comparison.png"
    render_pdf(str(pdf))
    print(f"✓ {pdf}  ({pdf.stat().st_size:,} bytes)")
    render_png(str(png), str(pdf))
    print(f"✓ {png}  ({png.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
