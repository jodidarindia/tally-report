"""FLOWRA Academy — per-lesson storyboard PDF generator.

Produces a single PDF with 30 pages (one per lesson). Each page contains:
  • Header — Lesson N + title + duration + audio file link
  • Left column — full Hinglish voiceover broken into SRT-timed caption blocks
  • Right column — shot direction (what to click / show / hover) per block
  • Footer — filename + FLOWRA copyright

Designed for a solo creator to record clean screencasts alongside the
Onyx voiceover in one take.

Output:
    /app/frontend/public/tutorials/FLOWRA_Academy_Storyboard.pdf
"""
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, Image)

sys.path.insert(0, str(Path(__file__).parent))
from lessons_manifest import LESSONS

SRT_DIR = Path("/app/tutorials/subtitles")
OUT_PDF = Path("/app/frontend/public/tutorials/FLOWRA_Academy_Storyboard.pdf")
LOGO_PATH = Path("/app/frontend/public/flowra-logo.png")

NAVY = colors.HexColor("#0F1B4C")
BLUE = colors.HexColor("#2563EB")
SKY = colors.HexColor("#38BDF8")
LIGHT = colors.HexColor("#F1F5F9")
MUTED = colors.HexColor("#64748B")

# ─────────────────── SHOT DIRECTIONS ──────────────────────
# One list per lesson — each entry is a "what to show on screen while
# the corresponding caption plays". Kept short & imperative — one line
# per major beat, so it fits in the right column of the storyboard.

SHOT_DIRECTIONS = {
    1: [
        "Open landing page (flowralive.in) — hero visible",
        "Cut to Tally desktop screenshot side-by-side with mobile",
        "Show mobile dashboard KPI cards populating",
        "Slow pan across 4 top tabs: Sales, CRM, Inventory, Analytics",
        "Zoom Dashboard 'What's New' panel briefly",
        "End card — FLOWRA logo + 'Agla video →' arrow",
    ],
    2: [
        "Landing page — mouse hovers Login button (top-right)",
        "Click Login → login screen opens",
        "Highlight email + password fields with a circle overlay",
        "Cursor demo — type 'demo@flowralive.in' slowly",
        "Enter password (hide behind dots)",
        "Click Sign In → Dashboard fade-in",
        "Show first-login coach-mark if present",
    ],
    3: [
        "Dashboard hero — 4 stat cards annotated (Sales / Orders / Outstanding / Beat)",
        "Timer: '30 sec auto-refresh' overlay",
        "Click Refresh button manually — cards flash",
        "Scroll down — 'What's New' panel closeup",
        "Point at Reminders + Overdue digest sections",
        "Hover top-nav — Sales, CRM, Inventory, Analytics, CA Corner one by one",
        "Right-side FY selector — click to open dropdown",
    ],
    4: [
        "Top nav — click Company selector (name-with-dropdown)",
        "List opens showing 3 companies of demo tenant",
        "Click a different company — data reloads",
        "Zoom into FY selector — switch 2026-27 → 2025-26",
        "Show numbers change between FYs",
        "End on 'Chalo agle video mein…' teaser",
    ],
    5: [
        "Dashboard — zoom on Sales card (₹39L)",
        "Reveal comparison line under card (previous FY delta)",
        "Zoom Orders card — voucher count highlighted",
        "Zoom Outstanding — annotate red '90+ days' bucket",
        "Zoom Beat Coverage — 62% donut chart focus",
        "Split-screen: 4 cards + 'daily 30-sec habit' text overlay",
    ],
    6: [
        "Dashboard scroll to 'What's New' panel",
        "Point at 3 tag styles: NEW (purple), FIX (red), IMPROVE (blue)",
        "Hover an entry — show date + description",
        "Cut to landing page Resources section",
        "Click 'FLOWRA Whats New PDF' → PDF opens in new tab",
        "Show sharing intent: WhatsApp send screenshot",
    ],
    7: [
        "Landing page — scroll to Resources section",
        "Highlight 4 PDF thumbnails with FLOWRA branding",
        "Click Presentation → PDF preview opens",
        "Cut back → click Deployment Guide",
        "Cut back → click Training Booklet",
        "Cut back → click Customer Questionnaire",
        "End on 'WhatsApp forward' animation",
    ],
    8: [
        "Owner Console → Financial Pitch section",
        "Click 'Generate Pitch Deck' button",
        "Progress bar animation",
        "PDF opens — flip through 16 pages",
        "Show revenue chart, gross margin trend, cash flow",
        "Cut to teaser PDF (10 pages)",
        "Cut to Excel projections — highlight editable cells",
    ],
    9: [
        "Super-admin nav — click to open",
        "Users tab — show list with roles",
        "Click Add User → modal opens with role dropdown",
        "Branches tab — show include/exclude toggles",
        "License tab — usage bar + Upgrade CTA",
        "Warning callout: 'Delete kabhi mat karna — Disable safe hai'",
    ],
    10: [
        "Sales tab open",
        "Show filter row — date range, salesman, customer, category",
        "Change salesman filter — list updates",
        "Click a voucher row — detail modal with items table",
        "Click PDF export → download progress",
        "Click Excel export → download progress",
        "Show company-name banner on downloaded file",
    ],
    11: [
        "Inventory tab open",
        "Zoom on ABC category chips (A / B / C / D)",
        "Filter by category = A — table filters",
        "Filter by stock group = Engine Oil",
        "Show reorder alerts row (red highlighted)",
        "Click PDF export → open file preview",
    ],
    12: [
        "CRM tab → Outstanding subtab",
        "Show full table with aging buckets colored",
        "Highlight red 90+ days column",
        "Change group filter dropdown — table refreshes",
        "Click Excel Export → download progress",
        "Zoom on downloaded file preview",
    ],
    13: [
        "CRM → Targets subtab",
        "Manual target set — click one row, edit target amount",
        "Click 'Bulk % Target' → modal with % input",
        "Type 20% → apply → all targets update",
        "Scroll right showing monthly split April → March",
        "Excel export button demo",
    ],
    14: [
        "CRM → Payment Behaviour subtab",
        "Zoom on Pay Ratio column (bar + %)",
        "Show green/yellow/red thresholds",
        "Zoom on Avg Delay column",
        "Zoom on Score column (0-100)",
        "End with 'Reliable customer → credit badhaao' overlay",
    ],
    15: [
        "CA Corner nav — click to open",
        "Show sub-sections: Sync, Reconciliation, Ledger PDF",
        "Click a customer → ledger PDF preview appears",
        "Reconciliation tab — pick start/end date",
        "GST-ready format teaser (coming soon banner)",
    ],
    16: [
        "Owner Console → Backups section",
        "List of last 30 days of nightly backups",
        "Point at 2 AM timestamp pattern",
        "Click Manual Backup → progress → success toast",
        "Click Restore on an older backup → confirmation modal",
        "Warning callout: 'Pehle current snapshot lo, fir restore karo'",
    ],
    17: [
        "Sales tab → open Dispatch column toggle",
        "Show dispatch fields: dispatch_through, destination, LR",
        "Filter by truck or destination — table filters",
        "Cut to Google Drive integration teaser",
        "Show linked bilty + invoice PDFs on a voucher",
    ],
    18: [
        "Login as salesman role (different from admin)",
        "Show minimal salesman dashboard with 4 sections",
        "Zoom on My Sales card",
        "Zoom on My Target progress bar",
        "Zoom on My Customers list",
        "Zoom on My Beat list for this week",
    ],
    19: [
        "Salesman phone view (rotate to portrait if mobile emulation)",
        "Tap a customer → Record Visit button",
        "GPS location auto-captured (map thumbnail)",
        "Tap Create Order → item picker",
        "Add qty for 3 items → Submit",
        "Success toast: 'Order recorded, will sync to Tally at night'",
    ],
    20: [
        "Salesman dashboard → Recommendations panel scroll",
        "Show 'Missed Customer' recommendation (30+ days no order)",
        "Show 'Cross-sell' recommendation (bought Engine Oil, offer Gear Oil)",
        "Show 'High-value prospect' recommendation",
        "Tap a recommendation → customer profile opens",
    ],
    21: [
        "Salesman dashboard → Personal Target card",
        "Circular progress bar with % achievement",
        "Green/yellow/red state examples (3-second flash each)",
        "Scroll to month-wise breakdown",
        "Callout: 'remaining amount / remaining days = daily target'",
    ],
    22: [
        "CRM → click any customer",
        "Ledger button highlighted",
        "PDF opens showing company header + customer details",
        "Scroll through transactions to closing balance",
        "Highlight GST-ready format elements",
        "Print preview demo",
    ],
    23: [
        "CA Corner → Reconciliation section",
        "Select start_date + end_date pickers",
        "Click Reconcile — show progress bar",
        "Highlight scoped-deletion warning: only within window",
        "Show summary: N vouchers matched, M added, K adjusted",
    ],
    24: [
        "CA Corner → Sync History tab",
        "Table with per-sync rows: timestamp, vouchers, status",
        "Green tick vs red exclamation examples",
        "Click a failed sync → error detail modal",
        "Show Retry button → progress → success",
        "End with WhatsApp support CTA",
    ],
    25: [
        "CA Corner → GST-ready reports section (banner: coming soon)",
        "Mock up: upload GSTR JSON portal",
        "System reconcile: matched vs mismatched invoice list",
        "Callout: 'Monthly filing tension-free'",
        "'Notify me when live' button demo",
    ],
    26: [
        "Downloads section on landing page",
        "Download Tally Agent installer — .exe",
        "Windows explorer — double click installer",
        "Install wizard: Next → Install → Finish",
        "System tray icon appears — right click → Open",
        "Login window — enter FLOWRA credentials",
        "Green 'Connected' state",
    ],
    27: [
        "Tally Agent → Companies tab",
        "List of local Tally companies detected",
        "Dropdown next to each — assign FLOWRA company",
        "Warning: 'Multi-company mapping mein carefully match karo'",
        "Click Save Mapping → success toast",
    ],
    28: [
        "Tally Agent Home tab",
        "Sync Health indicator: green light",
        "Show details panel: last sync time, next sync, pending count",
        "Toggle indicator to yellow (screenshot)",
        "Toggle to red (screenshot)",
        "Click 'Sync Now' → success animation",
    ],
    29: [
        "Tally Agent showing red state",
        "Checklist overlay:",
        "1. Tally band hai? → Open Tally",
        "2. Network issue? → Check internet",
        "3. ODBC not enabled? → Tally F1 config",
        "4. Password mismatch? → Update Agent",
        "5. Company path changed? → Agent settings",
        "End with WhatsApp support QR code",
    ],
    30: [
        "Landing page → Busy Agent download link",
        "Download + install (installer wizard)",
        "Login window — same as Tally",
        "Companies tab — Busy .bds files detected",
        "Mapping demo",
        "Warning banner: 'Demo Busy version supported nahi hai'",
        "WhatsApp support QR for licensed setup",
    ],
}


# ─────────────────── Helpers ──────────────────────

def _parse_srt(path: Path):
    """Return [(index, timing_str, text)]"""
    if not path.exists():
        return []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    out = []
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0])
        except ValueError:
            continue
        timing = lines[1]
        text = " ".join(lines[2:])
        # Compress timing: "00:00:01,399 --> 00:00:04,676" → "0:01 → 0:04"
        m = re.match(r"(\d+):(\d+):([\d,]+)\s*-->\s*(\d+):(\d+):([\d,]+)", timing)
        if m:
            def fmt(h, mnt, s):
                return f"{int(mnt) + int(h) * 60}:{int(s.split(',')[0]):02d}"
            start = fmt(m.group(1), m.group(2), m.group(3))
            end = fmt(m.group(4), m.group(5), m.group(6))
            timing = f"{start} → {end}"
        out.append((idx, timing, text))
    return out


def _build_lesson_page(story, styles, n, slug, title, length_hint):
    """Build the flowables for one lesson page."""
    # ── Header ───────────────────────────────────────
    header_style = ParagraphStyle(
        "H", parent=styles["Heading1"], fontSize=18, textColor=NAVY,
        spaceAfter=2, leading=22
    )
    sub_style = ParagraphStyle(
        "S", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=8
    )
    story.append(Paragraph(f"<b>Lesson {n:02d}</b> · {title}", header_style))
    story.append(Paragraph(
        f"Duration: {length_hint} &nbsp;·&nbsp; Voice: Onyx &nbsp;·&nbsp; "
        f"Audio: <font color='#2563EB'>lesson-{n:02d}.mp3</font> &nbsp;·&nbsp; "
        f"Captions: <font color='#2563EB'>lesson-{n:02d}.srt</font>",
        sub_style
    ))

    # ── Caption × Shot Direction table ──────────────
    cues = _parse_srt(SRT_DIR / f"lesson-{n:02d}.srt")
    shots = SHOT_DIRECTIONS.get(n, [])

    header_row = [
        Paragraph("<b>Time</b>", styles["Normal"]),
        Paragraph("<b>Voiceover (Hinglish)</b>", styles["Normal"]),
        Paragraph("<b>Shot direction (what to record)</b>", styles["Normal"]),
    ]
    rows = [header_row]

    # Interleave: caption chunks come from SRT, shot directions distributed
    # proportionally across the cues.
    n_cues = len(cues) or 1
    for i, (idx, timing, text) in enumerate(cues):
        # Map this cue to a shot direction based on relative position
        shot_i = int(i * len(shots) / n_cues) if shots else 0
        shot = shots[shot_i] if shots else ""
        rows.append([
            Paragraph(timing, ParagraphStyle("T", parent=styles["Normal"],
                                              fontSize=8, textColor=MUTED)),
            Paragraph(text, ParagraphStyle("V", parent=styles["Normal"],
                                            fontSize=9, leading=12)),
            Paragraph(shot, ParagraphStyle("D", parent=styles["Normal"],
                                            fontSize=9, textColor=NAVY,
                                            leading=12, fontName="Helvetica-Bold")),
        ])

    tbl = Table(rows, colWidths=[22 * mm, 75 * mm, 78 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)

    # ── Footer callout ──────────────────────────────
    footer = ParagraphStyle(
        "F", parent=styles["Normal"], fontSize=8, textColor=MUTED,
        spaceBefore=12, alignment=1
    )
    story.append(Paragraph(
        "© 2026 FLOWRA. All rights reserved. Internal storyboard — do not distribute externally.",
        footer
    ))
    story.append(PageBreak())


def build():
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PDF), pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=15 * mm, bottomMargin=12 * mm,
        title="FLOWRA Academy Storyboard",
        author="FLOWRA",
    )
    styles = getSampleStyleSheet()
    story = []

    # ── Cover page ─────────────────────────────────
    if LOGO_PATH.exists():
        try:
            story.append(Image(str(LOGO_PATH), width=55 * mm, height=18 * mm))
        except Exception:
            pass
    story.append(Spacer(1, 25 * mm))
    cover_title = ParagraphStyle(
        "CT", parent=styles["Title"], fontSize=32, textColor=NAVY,
        alignment=1, leading=38
    )
    story.append(Paragraph("FLOWRA Academy", cover_title))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Storyboard — 30 Lessons", ParagraphStyle(
        "CS", parent=styles["Heading2"], fontSize=18, textColor=BLUE,
        alignment=1, leading=22)))
    story.append(Spacer(1, 15 * mm))
    intro = ParagraphStyle("IN", parent=styles["Normal"], fontSize=11,
                           textColor=colors.HexColor("#334155"),
                           alignment=1, leading=15)
    story.append(Paragraph(
        "This storyboard is your teleprompter + shot-list for recording each "
        "Academy lesson. Each page contains the exact Hinglish voiceover text "
        "(matched to <b>lesson-NN.srt</b> timing), and a shot direction column "
        "telling you what to click / show / hover on screen while that segment "
        "plays.<br/><br/>"
        "Voice: <b>Onyx</b> (male, deep, authoritative)<br/>"
        "Total lessons: <b>30</b> across 6 tracks<br/>"
        "Total runtime: ~<b>55 minutes</b>",
        intro
    ))
    story.append(PageBreak())

    # ── Track-of-contents page ─────────────────────
    toc_title = ParagraphStyle("TT", parent=styles["Heading1"], fontSize=16,
                               textColor=NAVY, spaceAfter=8)
    story.append(Paragraph("Track index", toc_title))
    toc_rows = [[Paragraph("<b>#</b>", styles["Normal"]),
                 Paragraph("<b>Track</b>", styles["Normal"]),
                 Paragraph("<b>Lesson</b>", styles["Normal"]),
                 Paragraph("<b>Length</b>", styles["Normal"])]]

    def _track_for(n):
        if 1 <= n <= 4: return "Getting Started"
        if 5 <= n <= 9: return "Owner"
        if 10 <= n <= 17: return "Ops Manager"
        if 18 <= n <= 21: return "Salesman"
        if 22 <= n <= 25: return "CA / Accountant"
        return "Desktop Agent"

    for n, slug, title, _text, length_hint in LESSONS:
        toc_rows.append([
            Paragraph(f"{n:02d}", ParagraphStyle("X", parent=styles["Normal"], fontSize=9, alignment=1)),
            Paragraph(_track_for(n), ParagraphStyle("X", parent=styles["Normal"], fontSize=9, textColor=MUTED)),
            Paragraph(title, ParagraphStyle("X", parent=styles["Normal"], fontSize=9)),
            Paragraph(length_hint, ParagraphStyle("X", parent=styles["Normal"], fontSize=9, alignment=1, textColor=MUTED)),
        ])
    toc = Table(toc_rows, colWidths=[12 * mm, 42 * mm, 105 * mm, 18 * mm], repeatRows=1)
    toc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(toc)
    story.append(PageBreak())

    # ── Per-lesson pages ───────────────────────────
    for n, slug, title, _text, length_hint in LESSONS:
        _build_lesson_page(story, styles, n, slug, title, length_hint)

    doc.build(story)
    print(f"✅ Wrote {OUT_PDF}  ({OUT_PDF.stat().st_size // 1024} KB, "
          f"{2 + len(LESSONS)} pages)")


if __name__ == "__main__":
    build()
