"""FLOWRA — "What's New" PDF regenerator (Feb 2026 edition).

Rewrites /app/frontend/public/FLOWRA_Whats_New.pdf with a fresh, brand-
consistent snapshot of everything shipped through Jul 11, 2026. Mirrors the
same 12-entry list used in the User-Admin Dashboard's "What's New" panel
so the two sources never drift.

Uses DejaVuSans for ₹/… glyph support.
"""
from pathlib import Path
from reportlab.lib import colors as rc
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# Register DejaVu (handles ₹ and other Unicode)
_FDIR = "/root/.venv/lib/python3.11/site-packages/matplotlib/mpl-data/fonts/ttf"
try:
    pdfmetrics.registerFont(TTFont("Sans",   f"{_FDIR}/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("SansB",  f"{_FDIR}/DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("SansO",  f"{_FDIR}/DejaVuSans-Oblique.ttf"))
    registerFontFamily("Sans", normal="Sans", bold="SansB", italic="SansO")
    F, FB, FI = "Sans", "SansB", "SansO"
except Exception:
    F, FB, FI = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

NAVY  = rc.HexColor("#0F1B4C")
BLUE  = rc.HexColor("#2563EB")
AMBER = rc.HexColor("#F59E0B")
GREEN = rc.HexColor("#10B981")
RED   = rc.HexColor("#EF4444")
CYAN  = rc.HexColor("#0891B2")
PURPLE = rc.HexColor("#8B5CF6")
GREY  = rc.HexColor("#64748B")
LIGHT = rc.HexColor("#F1F5F9")
INK   = rc.HexColor("#0F172A")

TAG_COLORS = {"NEW": PURPLE, "FIX": RED, "IMPROVE": CYAN}

UPDATES = [
    ("2026-07-11", "FIX",     "Busy Sync Agent v1.3.1",
     "pyodbc bundled + Busy DB password fallback chain (Busy 21/18/older) + BUSY_DB_PASSWORD override field in Settings."),
    ("2026-07-08", "FIX",     "Tally Agent v9.8.30 — Forward-Dated Voucher Fix",
     "Quick-sync window now extends to today, not stops at stored LVD. Reconcile is date-scoped — prevents mass deletions when a voucher is added with a future date."),
    ("2026-07-08", "NEW",     "Busy Sync Agent v1.2 — Full Tally Parity",
     "Complete 1:1 Tally clone GUI: 4 connectivity cards, Sync Status panel, Subscription block with Request Renewal, auto-detect companies + FYs on folder pick."),
    ("2026-07-08", "NEW",     "Investor Pitch Kit",
     "16-page pitch PDF + 10-page cold-email teaser + editable Excel projection model. Auto-generated from a single source of truth."),
    ("2026-07-05", "NEW",     "Tally Agent v9.8.29 — LVD & AlterID Persist",
     "Per-company LVD + AlterID + timestamp saved to disk. 7-day full-sync skip window if AlterID unchanged."),
    ("2026-07-02", "NEW",     "Marketing Kit",
     "Auto-generated pitch decks (detailed + pointers), print-ready visiting cards (front/back QR), Tally-vs-Busy-vs-FLOWRA comparison charts."),
    ("2026-06-30", "FIX",     "Inventory Export Bugs",
     "CSV/Excel list→string coercion, PDF payload updates, multi-group filter fix. All export formats now handle nested product data correctly."),
    ("2026-06-25", "NEW",     "Beat Run — Mandatory Order/Payment + Close Day",
     "Yes/No flags on every stop. Unplanned existing-customer dropdown. End-of-Day PDF & Excel with breakdown by salesman."),
    ("2026-06-20", "NEW",     "Salesman Copy-From",
     "One-click copy of another salesman's customer mapping + beat plan. Speeds up new-hire onboarding by ~90%."),
    ("2026-06-15", "NEW",     "Employee Active/Deactivate Toggle",
     "Deactivate a user without deleting audit history. Deactivated users lose login but their data + reports remain intact."),
    ("2026-06-01", "NEW",     "Tally Agent v9.8.28 — SVCurrentCompany Fix",
     "Fixed XML header format that some Tally builds rejected. Zero errors on 5,000+ voucher syncs after fix."),
    ("2026-05-10", "NEW",     "Cancel Dispatch Cards",
     "Cancel a card up to the Packed lane with a reason; cancelled cards strikethrough until end-of-day, then auto-archive."),
    ("2026-05-10", "NEW",     "Tally Invoice Drift Detection",
     "Cards now auto-flag (amber/red badge) when the source Tally invoice is modified or deleted after sync — no silent drift."),
    ("2026-05-09", "NEW",     "Fuzzy Search Everywhere",
     "\"tvs 10\" now finds \"TVS-10\", \"TVS(10)\", \"TVS/10\". Spaces and separators (- / ( ) ! : . , & _) ignored across all search boxes."),
    ("2026-05-08", "IMPROVE", "SPIP — 12-Month Rolling Window",
     "Added rolling 12-month fallback and a \"No Movement\" bucket for idle items. Aliases included in global search."),
    ("2026-05-07", "FIX",     "SPIP & YoY Limits Removed",
     "Lifted the 5,000-row cap so all items surface in SPIP. Cross-FY YoY sales comparison + forecast tables added."),
    ("2026-05-05", "IMPROVE", "Mobile Performance",
     "Server-side pagination + render caps for Inventory and Customer CRM. Tally API delay 2s → 0.5s. New compound DB indexes."),
    ("2026-04-23", "NEW",     "Dispatch Terminal",
     "Kanban board, LR tracking, document uploads, porter settlement."),
]

OUT = Path("/app/frontend/public/FLOWRA_Whats_New.pdf")


def _frame(canv, doc):
    canv.setFillColor(NAVY)
    canv.rect(0, A4[1] - 22 * mm, A4[0], 22 * mm, fill=1, stroke=0)
    canv.setFillColor(AMBER)
    canv.circle(20 * mm, A4[1] - 11 * mm, 5 * mm, fill=1, stroke=0)
    canv.setFillColor(NAVY)
    canv.setFont(FB, 13)
    canv.drawCentredString(20 * mm, A4[1] - 12.6 * mm, "F")
    canv.setFillColor(rc.HexColor("#FFFFFF"))
    canv.setFont(FB, 12)
    canv.drawString(30 * mm, A4[1] - 10 * mm, "FLOWRA · What's New")
    canv.setFont(F, 9)
    canv.setFillColor(rc.HexColor("#94A3B8"))
    canv.drawString(30 * mm, A4[1] - 14.5 * mm, "Refreshed 11-Jul-2026 · Feb 2026 edition")
    canv.setStrokeColor(rc.HexColor("#E2E8F0"))
    canv.setLineWidth(0.4)
    canv.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
    canv.setFont(F, 8)
    canv.setFillColor(GREY)
    canv.drawString(15 * mm, 7 * mm, "FLOWRA · JODIDAR INDIA")
    canv.drawRightString(A4[0] - 15 * mm, 7 * mm,
                          "Organize. Automate. Accelerate.")


def build():
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=28 * mm, bottomMargin=15 * mm,
        title="FLOWRA · What's New · Feb 2026",
        author="JODIDAR INDIA",
    )
    styles_h1 = ParagraphStyle(name="h1", fontName=FB, fontSize=22,
                                 textColor=NAVY, leading=26, spaceAfter=4)
    styles_h2 = ParagraphStyle(name="h2", fontName=FB, fontSize=13,
                                 textColor=BLUE, leading=17, spaceAfter=10)
    styles_body = ParagraphStyle(name="b", fontName=F, fontSize=10,
                                   textColor=INK, leading=14)
    styles_date = ParagraphStyle(name="d", fontName=FB, fontSize=9,
                                   textColor=GREY, leading=12)
    styles_title = ParagraphStyle(name="t", fontName=FB, fontSize=11,
                                    textColor=NAVY, leading=15, spaceAfter=2)
    styles_desc = ParagraphStyle(name="dsc", fontName=F, fontSize=10,
                                   textColor=INK, leading=14)

    story = [
        Paragraph("What's New in FLOWRA", styles_h1),
        Paragraph("Everything shipped between April 2026 and July 2026, "
                    "grouped newest first.", styles_h2),
    ]

    rows = []
    for date, tag, title, desc in UPDATES:
        tag_color = TAG_COLORS.get(tag, GREY)
        tag_para = Paragraph(f"<b>{tag}</b>", ParagraphStyle(
            name=f"tg{date}", fontName=FB, fontSize=8,
            textColor=rc.HexColor("#FFFFFF"), leading=10, alignment=1))
        # Wrap tag in a coloured box using a nested Table
        tag_cell = Table([[tag_para]], colWidths=[18 * mm], rowHeights=[7 * mm])
        tag_cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), tag_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        cell_right = [
            Paragraph(title, styles_title),
            Paragraph(desc, styles_desc),
        ]
        rows.append([Paragraph(date, styles_date), tag_cell, cell_right])

    tbl = Table(rows, colWidths=[22 * mm, 22 * mm, 136 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, rc.HexColor("#E2E8F0")),
        ("BOX", (0, 0), (-1, -1), 0.4, rc.HexColor("#CBD5E1")),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Tally* and Busy* are trademarks of their respective owners. "
        "FLOWRA is an independent product and is not affiliated with any of them.",
        ParagraphStyle(name="ft", fontName=FI, fontSize=8,
                        textColor=GREY, leading=11)))
    doc.build(story, onFirstPage=_frame, onLaterPages=_frame)
    print(f"✓ Wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB, {len(UPDATES)} entries)")


if __name__ == "__main__":
    build()
