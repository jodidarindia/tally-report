"""FLOWRA — "What's New" PDF regenerator (Feb 2026 edition).

Reads /app/frontend/public/whats_new.json (SINGLE SOURCE OF TRUTH — also
consumed by User Admin Dashboard "What's New" panel) and rewrites
/app/frontend/public/FLOWRA_Whats_New.pdf.

Uses DejaVuSans for ₹/… glyph support.
"""
import json
from pathlib import Path

from reportlab.lib import colors as rc
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
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
CYAN  = rc.HexColor("#0891B2")
PURPLE = rc.HexColor("#8B5CF6")
RED   = rc.HexColor("#EF4444")
GREY  = rc.HexColor("#64748B")
INK   = rc.HexColor("#0F172A")

TAG_COLORS = {"NEW": PURPLE, "FIX": RED, "IMPROVE": CYAN}

JSON_PATH = Path("/app/frontend/public/whats_new.json")
OUT       = Path("/app/frontend/public/FLOWRA_Whats_New.pdf")


def load_updates():
    if not JSON_PATH.exists():
        raise SystemExit(f"Source file missing: {JSON_PATH}")
    d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    entries = d.get("entries", [])
    if not entries:
        raise SystemExit("whats_new.json has no entries")
    return d.get("updated_at", ""), entries


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
    updated_at, entries = load_updates()
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=28 * mm, bottomMargin=15 * mm,
        title="FLOWRA · What's New · Feb 2026",
        author="JODIDAR INDIA",
    )
    global _UPDATED_AT
    _UPDATED_AT = updated_at
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
    for entry in entries:
        date  = entry.get("date", "")
        tag   = entry.get("tag", "NEW")
        title = entry.get("title", "")
        desc  = entry.get("desc", "")
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
    print(f"✓ Wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB, {len(entries)} entries · source: whats_new.json updated_at={updated_at})")


if __name__ == "__main__":
    build()
