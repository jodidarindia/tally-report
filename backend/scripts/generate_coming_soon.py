"""Generate FLOWRA Coming Soon PDF — Dispatch Terminal & Salesman Order System"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
import os

BLUE = HexColor("#2563EB")
DARK = HexColor("#0f172a")
LIGHT_BG = HexColor("#f8fafc")
GRAY = HexColor("#64748b")
GREEN = HexColor("#16a34a")
AMBER = HexColor("#d97706")
RED = HexColor("#dc2626")
TEAL = HexColor("#0d9488")
VIOLET = HexColor("#7c3aed")
WHITE = white

OUT_DIR = "/app/frontend/public"


def draw_bg(c, w, h, footer_text=""):
    c.setFillColor(DARK)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.rect(0, h - 5, w, 5, fill=1, stroke=0)
    if footer_text:
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#475569"))
        c.drawString(40, 15, footer_text)
        c.drawRightString(w - 40, 15, "www.flowralive.in | JODIDAR INDIA")


def draw_title_page(c, w, h, title, subtitle, badge="COMING SOON"):
    c.setFillColor(DARK)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    # Accent line
    c.setFillColor(BLUE)
    c.rect(0, h/2 + 80, w, 4, fill=1, stroke=0)
    # Badge
    badge_w = len(badge) * 10 + 30
    c.setFillColor(BLUE)
    c.roundRect(w/2 - badge_w/2, h/2 + 95, badge_w, 28, 14, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(WHITE)
    c.drawCentredString(w/2, h/2 + 102, badge)
    # Title
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(WHITE)
    c.drawCentredString(w/2, h/2 + 35, title)
    # Subtitle
    c.setFont("Helvetica", 16)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(w/2, h/2 - 5, subtitle)
    # Bottom
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(BLUE)
    c.drawCentredString(w/2, h/2 - 55, "FLOWRA")
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#64748b"))
    c.drawCentredString(w/2, h/2 - 75, "www.flowralive.in")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#475569"))
    c.drawCentredString(w/2, 40, "Tally* is the trademark of its respective owner and is not affiliated with FLOWRA or Jodidar India.")


def slide_heading(c, w, h, title, subtitle=""):
    draw_bg(c, w, h, "FLOWRA — Coming Soon Features")
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(WHITE)
    c.drawString(50, h - 55, title)
    c.setStrokeColor(BLUE)
    c.setLineWidth(3)
    c.line(50, h - 63, 50 + len(title) * 14, h - 63)
    if subtitle:
        c.setFont("Helvetica", 12)
        c.setFillColor(HexColor("#94a3b8"))
        c.drawString(50, h - 82, subtitle)


def bullet(c, x, y, text, color=BLUE, font_size=12):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(x, y, ">")
    c.setFillColor(HexColor("#e2e8f0"))
    c.setFont("Helvetica", font_size)
    c.drawString(x + 18, y, text)
    return y - 24


def highlight_bullet(c, x, y, text, accent=BLUE, font_size=12):
    c.setFillColor(accent)
    c.roundRect(x - 2, y - 4, 8, 16, 2, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(x + 14, y, text)
    return y - 26


def section_label(c, x, y, text, color=BLUE):
    c.setFillColor(color)
    c.roundRect(x, y - 3, len(text) * 6.5 + 16, 20, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawString(x + 8, y + 2, text)
    return y - 30


def draw_card_mockup(c, x, y, w_card, inv, party, items, city, transport, status, status_color, timer="12m"):
    """Draw a dispatch card mockup."""
    h_card = 115
    c.setFillColor(HexColor("#1e293b"))
    c.roundRect(x, y - h_card, w_card, h_card, 6, fill=1, stroke=0)
    c.setStrokeColor(status_color)
    c.setLineWidth(2.5)
    c.line(x + 3, y - 8, x + 3, y - h_card + 8)
    # Invoice
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(WHITE)
    c.drawString(x + 14, y - 18, inv)
    # Status badge
    c.setFillColor(status_color)
    c.roundRect(x + w_card - 70, y - 22, 58, 16, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(WHITE)
    c.drawCentredString(x + w_card - 41, y - 17, status)
    # Party
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#cbd5e1"))
    c.drawString(x + 14, y - 36, party)
    # Items + boxes
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawString(x + 14, y - 52, f"{items} items")
    c.drawString(x + 85, y - 52, f"{city}")
    # Transport
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#64748b"))
    c.drawString(x + 14, y - 68, transport)
    # Timer
    c.setFont("Helvetica-Bold", 9)
    timer_color = GREEN if "m" in timer and int(timer.replace("m", "").replace("h", "")) < 30 else AMBER
    c.setFillColor(timer_color)
    c.drawString(x + 14, y - 88, f"T {timer}")
    # Porter/By
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#475569"))
    c.drawString(x + 14, y - 103, "Porter: Sunil K.")
    c.drawString(x + w_card - 80, y - 103, "By: Ramesh")


def generate_coming_soon():
    W, H = landscape(A4)
    path = os.path.join(OUT_DIR, "FLOWRA_Coming_Soon.pdf")
    c = canvas.Canvas(path, pagesize=(W, H))

    # ════════════════════════════════════════════
    # SLIDE 1: Cover
    # ════════════════════════════════════════════
    draw_title_page(c, W, H,
                    "FLOWRA — Upcoming Features",
                    "Dispatch Terminal  |  Salesman Order System")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 2: Dispatch Terminal — Overview
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Dispatch Terminal", "Real-time warehouse dispatch management — like McDonald's KDS for your godown")
    y = H - 105
    y = section_label(c, 55, y, "THE VISION")
    y = bullet(c, 60, y, "Live dispatch board synced with Tally* invoices in real-time")
    y = bullet(c, 60, y, "Employee-operated touchscreen terminal in the dispatch area")
    y = bullet(c, 60, y, "Every invoice becomes a dispatch card with full tracking lifecycle")
    y = bullet(c, 60, y, "Physical verification checkpoint — nothing leaves without confirmation")
    y = bullet(c, 60, y, "End-of-day dispatch summary with complete audit trail")
    y -= 8
    y = section_label(c, 55, y, "KEY DIFFERENTIATOR")
    y = highlight_bullet(c, 60, y, "Turns FLOWRA from a reporting tool into an operational warehouse tool", TEAL)
    y = highlight_bullet(c, 60, y, "No Tally* analytics product in India offers dispatch terminal today", TEAL)
    y = highlight_bullet(c, 60, y, "Built for distributor warehouses — touchscreen-first, dark theme, large fonts", TEAL)
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 3: Dispatch Card — What's Inside
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Invoice Dispatch Card", "Every detail captured at the dispatch point")
    y = H - 100
    # Left: details
    y = section_label(c, 55, y, "CARD DATA FIELDS")
    fields = [
        ("Invoice Number", "Auto-synced from Tally* sales invoice"),
        ("Party Name", "Customer / buyer name from Tally*"),
        ("Total Boxes", "Number of boxes/cartons in consignment"),
        ("Items Billed", "Complete item list — each physically verified"),
        ("Transport Name", "Which logistics company / self delivery"),
        ("Destination City", "Where the consignment is going"),
        ("Paid Charges", "Transport charges + porter charges recorded"),
        ("Porter Name", "Who carries consignment to the transport vehicle"),
        ("Dispatched By", "Employee name who processed this card"),
        ("Status", "Hold > Queued > Processing > Packed > Dispatched"),
        ("Physical Check", "Mandatory confirmation — all items in bill verified"),
    ]
    for label, desc in fields:
        if y < 55:
            break
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(BLUE)
        c.drawString(60, y, label)
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#94a3b8"))
        c.drawString(210, y, desc)
        y -= 20

    # Right: card mockup
    draw_card_mockup(c, W - 250, H - 130, 210,
                     "INV-4521", "ABC Auto Parts", "15", "Raipur",
                     "VRL Logistics", "PACKED", GREEN, "28m")
    draw_card_mockup(c, W - 250, H - 260, 210,
                     "INV-4523", "National Eng Works", "8", "Indore",
                     "Delhivery", "PROCESSING", AMBER, "45m")
    draw_card_mockup(c, W - 250, H - 390, 210,
                     "INV-4498", "XYZ Trading Co", "3", "Bhopal",
                     "Self Delivery", "HOLD", RED, "2h")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 4: Status Flow & Queue System
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Dispatch Workflow", "Queue-based assignment with mandatory physical verification")
    y = H - 100

    y = section_label(c, 55, y, "STATUS LIFECYCLE")
    statuses = [
        ("NEW", "Invoice synced from Tally* — auto-created", BLUE),
        ("QUEUED", "Assigned to dispatch employee in rotation", VIOLET),
        ("PROCESSING", "Employee picking & verifying items against bill", AMBER),
        ("PACKED", "All items physically checked, boxes counted, sealed", TEAL),
        ("DISPATCHED", "Handed to transport, porter recorded, charges logged", GREEN),
        ("INFO SHARED", "Invoice & dispatch details shared with customer", HexColor("#06b6d4")),
    ]
    for label, desc, color in statuses:
        c.setFillColor(color)
        c.roundRect(60, y - 3, 100, 18, 3, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(WHITE)
        c.drawCentredString(110, y + 1, label)
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#cbd5e1"))
        c.drawString(175, y, desc)
        y -= 28

    y -= 10
    y = section_label(c, 55, y, "QUEUE SYSTEM")
    y = bullet(c, 60, y, "Cards auto-assigned to available dispatch employees in round-robin")
    y = bullet(c, 60, y, "Employee sees only their queued cards — focused workflow")
    y = bullet(c, 60, y, "Mandatory checkbox: 'All items in bill are physically verified'")
    y = bullet(c, 60, y, "Cannot move to PACKED without physical verification confirmation")

    # Flow arrow diagram on right
    cx = W - 180
    arrow_y = H - 115
    flow_items = [
        ("TALLY* INVOICE", BLUE), ("NEW CARD", BLUE), ("QUEUE TO EMPLOYEE", VIOLET),
        ("PICK & VERIFY", AMBER), ("PACK & COUNT", TEAL), ("DISPATCH + LOG", GREEN),
        ("NOTIFY CUSTOMER", HexColor("#06b6d4"))
    ]
    for label, color in flow_items:
        c.setFillColor(color)
        c.roundRect(cx - 60, arrow_y - 5, 120, 22, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(WHITE)
        c.drawCentredString(cx, arrow_y + 3, label)
        arrow_y -= 30
        if arrow_y > 60:
            c.setFillColor(HexColor("#475569"))
            c.drawCentredString(cx, arrow_y + 22, "|")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 5: Manual Cards & Expense Tracking
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Manual Cards & Expense Tracking", "Handle non-invoice dispatches and track every rupee spent")
    y = H - 100

    y = section_label(c, 55, y, "MANUAL DISPATCH CARDS")
    y = bullet(c, 60, y, "Create dispatch card without a Tally* invoice — for returns, samples, etc.")
    y = bullet(c, 60, y, "Mandatory reason field: Sample / Return / Replacement / Internal Transfer / Other")
    y = bullet(c, 60, y, "Same tracking lifecycle as invoice cards — full audit trail")
    y = bullet(c, 60, y, "Clearly tagged as 'MANUAL' in terminal and reports")
    y -= 10

    y = section_label(c, 55, y, "PORTER EXPENSE TRACKING")
    y = highlight_bullet(c, 60, y, "Every dispatch logs porter name + service charge", AMBER)
    y = highlight_bullet(c, 60, y, "Running account per porter — all jobs tracked automatically", AMBER)
    y = highlight_bullet(c, 60, y, "Weekly settlement report: total owed per porter", AMBER)
    y = highlight_bullet(c, 60, y, "Admin can mark 'Paid' with reference — clean ledger", AMBER)
    y -= 10

    y = section_label(c, 55, y, "TRANSPORT CHARGES")
    y = bullet(c, 60, y, "Record transport charges per dispatch (freight, handling, insurance)")
    y = bullet(c, 60, y, "Track paid vs unpaid per transporter")
    y = bullet(c, 60, y, "City-wise freight analysis over time")

    # Right side: expense summary mockup
    cx = W - 260
    ey = H - 110
    c.setFillColor(HexColor("#1e293b"))
    c.roundRect(cx, ey - 180, 230, 180, 8, fill=1, stroke=0)
    c.setStrokeColor(AMBER)
    c.setLineWidth(2)
    c.line(cx + 3, ey - 5, cx + 3, ey - 175)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(AMBER)
    c.drawString(cx + 15, ey - 22, "Porter Weekly Settlement")
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#cbd5e1"))
    porters = [
        ("Sunil Kumar", "47 jobs", "Rs.4,700"),
        ("Raju Yadav", "32 jobs", "Rs.3,200"),
        ("Mohan Singh", "28 jobs", "Rs.2,800"),
        ("Deepak Sahu", "19 jobs", "Rs.1,900"),
    ]
    py = ey - 48
    for name, jobs, amt in porters:
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#e2e8f0"))
        c.drawString(cx + 15, py, name)
        c.setFillColor(HexColor("#94a3b8"))
        c.drawString(cx + 110, py, jobs)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(GREEN)
        c.drawString(cx + 165, py, amt)
        py -= 22
    c.setFillColor(HexColor("#475569"))
    c.line(cx + 15, py + 12, cx + 215, py + 12)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(WHITE)
    c.drawString(cx + 15, py - 5, "Total:")
    c.setFillColor(GREEN)
    c.drawString(cx + 155, py - 5, "Rs.12,600")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 6: Close of Day Summary
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Close of Day — Dispatch Summary", "One-click daily report with complete audit trail")
    y = H - 100

    y = section_label(c, 55, y, "SUMMARY INCLUDES FOR EACH DISPATCH")
    fields_cod = [
        "Invoice Number (or 'MANUAL' tag with reason)",
        "Party Name (customer / buyer)",
        "Total Boxes in Consignment",
        "Transport / Porter Charges Paid",
        "Porter Name (who carried to transport)",
        "Dispatched By (employee name)",
        "Consignment Status (Dispatched / Pending / Hold)",
        "Physical Verification Timestamp",
    ]
    for f in fields_cod:
        y = highlight_bullet(c, 60, y, f, BLUE, 11)
    y -= 8
    y = section_label(c, 55, y, "ADDITIONAL TOTALS")
    y = bullet(c, 60, y, "Total invoices dispatched today + pending carry-forward count")
    y = bullet(c, 60, y, "Total value dispatched (Rs.) + total boxes shipped")
    y = bullet(c, 60, y, "Transport-wise breakdown + city-wise count")
    y = bullet(c, 60, y, "Porter expenses for the day + weekly running total")

    # Right: summary mockup
    cx = W - 280
    sy = H - 105
    c.setFillColor(HexColor("#1e293b"))
    c.roundRect(cx, sy - 290, 250, 290, 8, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(WHITE)
    c.drawString(cx + 15, sy - 22, "Dispatch Summary — 13 Apr 2026")
    c.setStrokeColor(BLUE)
    c.setLineWidth(1)
    c.line(cx + 15, sy - 30, cx + 235, sy - 30)
    summary_items = [
        ("Total Invoices", "42", WHITE),
        ("Dispatched", "35", GREEN),
        ("Pending", "4", AMBER),
        ("On Hold", "3", RED),
        ("", "", WHITE),
        ("Items Shipped", "1,247", WHITE),
        ("Value Dispatched", "Rs.8.4L", GREEN),
        ("Boxes Shipped", "186", WHITE),
        ("", "", WHITE),
        ("Porter Charges", "Rs.2,100", AMBER),
        ("Transport Charges", "Rs.4,800", AMBER),
    ]
    iy = sy - 50
    for label, val, color in summary_items:
        if not label:
            iy -= 8
            continue
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#94a3b8"))
        c.drawString(cx + 20, iy, label)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(color)
        c.drawRightString(cx + 230, iy, val)
        iy -= 18
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 7: Admin View
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Admin Dashboard View", "Summary-only access with drill-down for pending dispatches")
    y = H - 100

    y = section_label(c, 55, y, "ADMIN GETS")
    y = bullet(c, 60, y, "Daily/weekly/monthly dispatch summary — total dispatched, pending, value")
    y = bullet(c, 60, y, "Export to Excel — full dispatch log with all card fields")
    y = bullet(c, 60, y, "Porter settlement report — weekly payable per porter")
    y = bullet(c, 60, y, "Transport expense analysis — city-wise, transporter-wise")
    y -= 8
    y = section_label(c, 55, y, "DRILL-DOWN RULES")
    y = highlight_bullet(c, 60, y, "ONLY pending dispatches can be drilled down to card details", RED)
    y = highlight_bullet(c, 60, y, "Admin sees notes, remarks, hold reasons for stuck invoices", RED)
    y = highlight_bullet(c, 60, y, "Completed dispatches show summary row only — no clutter", RED)
    y -= 8
    y = section_label(c, 55, y, "SECURITY & ISOLATION")
    y = bullet(c, 60, y, "FY-scoped — dispatch data isolated per financial year")
    y = bullet(c, 60, y, "Tenant ID + Company ID isolation — multi-company safe")
    y = bullet(c, 60, y, "256-bit AES encryption for all dispatch records")
    y = bullet(c, 60, y, "reCAPTCHA v3 on dispatch terminal login")
    y = bullet(c, 60, y, "Mobile-responsive — admin can check from phone")
    y = bullet(c, 60, y, "Employee role 'dispatch' — limited access, terminal only")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 8: Terminal Visual Design
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Terminal Display Design", "Dark theme, touch-optimized, wall-mountable on 43\" or 55\" screen")
    y = H - 100

    # Draw a mini terminal mockup
    tx = 50
    ty = y
    tw = W - 100
    th = 280
    # Terminal outer frame
    c.setFillColor(HexColor("#0f172a"))
    c.roundRect(tx, ty - th, tw, th, 10, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#334155"))
    c.setLineWidth(1)
    c.roundRect(tx, ty - th, tw, th, 10, fill=0, stroke=1)

    # Header bar
    c.setFillColor(HexColor("#1e293b"))
    c.roundRect(tx + 5, ty - 30, tw - 10, 28, 5, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BLUE)
    c.drawString(tx + 15, ty - 22, "FLOWRA DISPATCH")
    c.setFillColor(HexColor("#94a3b8"))
    c.setFont("Helvetica", 8)
    c.drawString(tx + 140, ty - 22, "ASA Autotech Pvt Ltd  |  Ramesh K.  |  14:32")
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(tx + tw - 100, ty - 22, "LIVE SYNC")

    # Lane headers
    lanes = [
        ("NEW (6)", BLUE), ("QUEUED (4)", VIOLET),
        ("PROCESSING (3)", AMBER), ("PACKED (5)", GREEN), ("DISPATCHED (12)", HexColor("#475569"))
    ]
    lane_w = (tw - 30) / len(lanes)
    lx = tx + 10
    ly = ty - 52
    for label, color in lanes:
        c.setFillColor(color)
        c.roundRect(lx, ly - 2, lane_w - 5, 16, 3, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(WHITE)
        c.drawCentredString(lx + (lane_w - 5) / 2, ly + 2, label)
        # Mini cards under each
        for j in range(2):
            cy = ly - 25 - j * 52
            if cy < ty - th + 40:
                break
            c.setFillColor(HexColor("#1e293b"))
            c.roundRect(lx, cy - 42, lane_w - 8, 42, 4, fill=1, stroke=0)
            c.setStrokeColor(color)
            c.setLineWidth(1.5)
            c.line(lx + 2, cy - 5, lx + 2, cy - 38)
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(HexColor("#e2e8f0"))
            c.drawString(lx + 8, cy - 13, f"INV-45{10 + j}")
            c.setFont("Helvetica", 6)
            c.setFillColor(HexColor("#94a3b8"))
            c.drawString(lx + 8, cy - 24, f"Customer {j+1}")
            c.drawString(lx + 8, cy - 34, f"{5+j*3} items | City")
        lx += lane_w

    # Bottom bar
    c.setFillColor(HexColor("#1e293b"))
    c.roundRect(tx + 5, ty - th + 5, tw - 10, 22, 5, fill=1, stroke=0)
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawString(tx + 15, ty - th + 12, "Today: 42 invoices | 35 dispatched | 4 processing | 3 hold | Avg: 28 min")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(tx + tw - 120, ty - th + 12, "CLOSE FOR DAY")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 9: Salesman Order System — Overview
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Salesman Order System", "Enterprise feature — field sales ordering with admin approval workflow")
    y = H - 100

    y = section_label(c, 55, y, "FOR SALESMAN (FIELD APP)")
    y = bullet(c, 60, y, "Login with mapped customer ledgers and outstanding from Tally*")
    y = bullet(c, 60, y, "See real-time inventory availability before placing order")
    y = bullet(c, 60, y, "Browse product catalog with stock levels and pricing")
    y = bullet(c, 60, y, "Create orders against mapped customers — item + qty + rate")
    y = bullet(c, 60, y, "View own order history and pending approval status")
    y -= 8

    y = section_label(c, 55, y, "ORDER WORKFLOW")
    flow = [
        ("Salesman creates order", BLUE),
        ("Order enters approval queue", VIOLET),
        ("Admin reviews — Approve / Reject / Modify", AMBER),
        ("Approved order syncs to dispatch terminal", GREEN),
        ("Dispatch processes and ships", TEAL),
    ]
    for text, color in flow:
        c.setFillColor(color)
        c.roundRect(70, y - 3, 6, 16, 2, fill=1, stroke=0)
        c.setFillColor(HexColor("#e2e8f0"))
        c.setFont("Helvetica", 11)
        c.drawString(85, y, text)
        y -= 24
    y -= 8
    y = section_label(c, 55, y, "FOR ADMIN")
    y = bullet(c, 60, y, "Order approval dashboard — approve, reject, modify quantities/rates")
    y = bullet(c, 60, y, "Salesman performance: orders placed vs targets, beat coverage")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 10: Salesman Features Detail
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Salesman Module — Features", "Beat plans, customer mapping, performance analytics")
    y = H - 100

    y = section_label(c, 55, y, "BEAT MANAGEMENT")
    y = bullet(c, 60, y, "Define daily/weekly beat plans — which customers to visit on which day")
    y = bullet(c, 60, y, "GPS check-in at customer location (optional)")
    y = bullet(c, 60, y, "Beat compliance tracking — planned vs actual visits")
    y = bullet(c, 60, y, "Beat working analysis reports — coverage, frequency, gaps")
    y -= 8

    y = section_label(c, 55, y, "CUSTOMER MAPPING")
    y = bullet(c, 60, y, "Each salesman mapped to specific customer ledgers from Tally*")
    y = bullet(c, 60, y, "Salesman sees only their customers — isolated view")
    y = bullet(c, 60, y, "Outstanding visibility — can collect payments against invoices")
    y = bullet(c, 60, y, "Customer-wise order history and ledger balance")
    y -= 8

    y = section_label(c, 55, y, "ANALYTICS")
    y = bullet(c, 60, y, "Orders per salesman — daily, weekly, monthly totals")
    y = bullet(c, 60, y, "Target vs achievement (value and quantity)")
    y = bullet(c, 60, y, "Product mix analysis — which salesman sells what most")
    y = bullet(c, 60, y, "Pending orders aging — how long orders sit in queue")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 11: Security & Technical
    # ════════════════════════════════════════════
    slide_heading(c, W, H, "Security & Technical Architecture", "Enterprise-grade isolation for all new modules")
    y = H - 100

    y = section_label(c, 55, y, "DATA ISOLATION")
    y = bullet(c, 60, y, "All dispatch records scoped by Tenant ID + Company ID + Financial Year")
    y = bullet(c, 60, y, "Employee dispatch role — cannot access CRM, analytics, or admin features")
    y = bullet(c, 60, y, "Salesman role — sees only mapped customers and own orders")
    y -= 8

    y = section_label(c, 55, y, "SECURITY LAYERS")
    y = bullet(c, 60, y, "Google reCAPTCHA v3 on terminal login and salesman login")
    y = bullet(c, 60, y, "256-bit AES encryption for dispatch data at rest and in transit")
    y = bullet(c, 60, y, "JWT authentication with session idle timeout (15 minutes)")
    y = bullet(c, 60, y, "Audit trail — every status change logged with employee + timestamp")
    y -= 8

    y = section_label(c, 55, y, "MOBILE & DISPLAY")
    y = bullet(c, 60, y, "Dispatch Terminal: optimized for 43\" / 55\" wall-mounted displays")
    y = bullet(c, 60, y, "Full kiosk mode (F11) — no browser chrome, dedicated dispatch view")
    y = bullet(c, 60, y, "Salesman module: fully mobile-responsive for phone use in the field")
    y = bullet(c, 60, y, "Admin views: responsive — works on desktop, tablet, and mobile")
    y -= 8

    y = section_label(c, 55, y, "SYNC ARCHITECTURE")
    y = bullet(c, 60, y, "Desktop Agent v8 syncs invoices -> WebSocket push to terminal in real-time")
    y = bullet(c, 60, y, "Salesman orders flow back to admin -> approved orders push to dispatch")
    y = bullet(c, 60, y, "End-to-end: Tally* Invoice > Dispatch Terminal > Customer Notification")
    c.showPage()

    # ════════════════════════════════════════════
    # SLIDE 12: Closing
    # ════════════════════════════════════════════
    draw_title_page(c, W, H,
                    "Launching Soon",
                    "Dispatch Terminal  +  Salesman Order System")
    # Override bottom text
    c.setFont("Helvetica", 13)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(W/2, H/2 - 110, "Register your interest at support@flowralive.in")
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#475569"))
    c.drawCentredString(W/2, H/2 - 135, "Early adopters get priority access + 30-day extended trial")
    c.showPage()

    c.save()
    print(f"Coming Soon PDF: {path}")
    return path


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    generate_coming_soon()
