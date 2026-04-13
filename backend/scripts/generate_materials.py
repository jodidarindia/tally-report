"""Generate FLOWRA marketing materials: Presentation PDF, Training Booklet, Social Media Kit, Customer Questionnaire"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import os

BLUE = HexColor("#2563EB")
DARK = HexColor("#0f172a")
LIGHT_BG = HexColor("#f8fafc")
GRAY = HexColor("#64748b")
GREEN = HexColor("#16a34a")
AMBER = HexColor("#d97706")
RED = HexColor("#dc2626")
WHITE = white

SS_DIR = "/app/frontend/public/screenshots"
OUT_DIR = "/app/frontend/public"
DEMO_SS = {
    "dashboard": "/app/frontend/public/screenshots/demo_dashboard.png",
    "sales": "/app/frontend/public/screenshots/demo_sales.png",
    "crm": "/app/frontend/public/screenshots/demo_crm.png",
    "analytics": "/app/frontend/public/screenshots/demo_analytics.png",
    "inventory": "/app/frontend/public/screenshots/demo_inventory.png",
    "landing": "/app/frontend/public/screenshots/demo_landing.png",
}

# ─── Helpers ───────────────────────────────────────────
def draw_slide_bg(c, w, h):
    c.setFillColor(WHITE)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#e2e8f0"))
    c.setLineWidth(0.5)
    c.line(0, 40, w, 40)
    c.setFont("Helvetica", 7)
    c.setFillColor(GRAY)
    c.drawString(40, 18, "www.flowralive.in")
    c.drawRightString(w - 40, 18, "FLOWRA - Tally* Analytics Platform")

def draw_title_slide(c, w, h, title, subtitle=""):
    draw_slide_bg(c, w, h)
    c.setFillColor(BLUE)
    c.rect(0, h - 8, w, 8, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 42)
    c.setFillColor(DARK)
    c.drawCentredString(w/2, h/2 + 40, title)
    if subtitle:
        c.setFont("Helvetica", 18)
        c.setFillColor(GRAY)
        c.drawCentredString(w/2, h/2 - 10, subtitle)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(BLUE)
    c.drawCentredString(w/2, h/2 - 50, "www.flowralive.in")

def draw_content_slide(c, w, h, title, bullets, screenshot=None):
    draw_slide_bg(c, w, h)
    c.setFillColor(BLUE)
    c.rect(0, h - 6, w, 6, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(DARK)
    c.drawString(50, h - 55, title)
    c.setStrokeColor(BLUE)
    c.setLineWidth(2)
    c.line(50, h - 62, 250, h - 62)
    y = h - 100
    c.setFont("Helvetica", 13)
    for bullet in bullets:
        if y < 80:
            break
        c.setFillColor(BLUE)
        c.drawString(60, y, ">")
        c.setFillColor(DARK)
        c.drawString(80, y, bullet)
        y -= 28
    if screenshot and os.path.exists(screenshot):
        try:
            img_w = 420
            img_h = 240
            c.drawImage(screenshot, w - img_w - 40, 60, width=img_w, height=img_h, preserveAspectRatio=True)
            c.setStrokeColor(HexColor("#e2e8f0"))
            c.setLineWidth(1)
            c.rect(w - img_w - 40, 60, img_w, img_h, fill=0, stroke=1)
        except:
            pass

def draw_pricing_slide(c, w, h):
    draw_slide_bg(c, w, h)
    c.setFillColor(BLUE)
    c.rect(0, h - 6, w, 6, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(DARK)
    c.drawString(50, h - 55, "Simple, Transparent Pricing")
    plans = [
        ("Starter", "999/mo", "1 Company", "2 Users", "Core Analytics"),
        ("Professional", "2,499/mo", "3 Companies", "5 Users", "CRM + AI + CA Corner"),
        ("Enterprise", "3,799/mo", "10 Companies", "20 Users", "Full Suite + Salesman"),
    ]
    x_start = 80
    box_w = 230
    for i, (name, price, comp, users, feat) in enumerate(plans):
        x = x_start + i * (box_w + 30)
        y_top = h - 100
        box_h = 280
        is_pro = (i == 1)
        if is_pro:
            c.setFillColor(BLUE)
            c.roundRect(x, y_top - box_h, box_w, box_h, 10, fill=1, stroke=0)
            c.setFillColor(WHITE)
        else:
            c.setFillColor(LIGHT_BG)
            c.roundRect(x, y_top - box_h, box_w, box_h, 10, fill=1, stroke=0)
            c.setStrokeColor(HexColor("#e2e8f0"))
            c.roundRect(x, y_top - box_h, box_w, box_h, 10, fill=0, stroke=1)
            c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(x + box_w/2, y_top - 35, name)
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(x + box_w/2, y_top - 70, f"Rs.{price}")
        c.setFont("Helvetica", 12)
        for j, item in enumerate([comp, users, feat]):
            c.drawCentredString(x + box_w/2, y_top - 110 - j*28, item)
    c.setFont("Helvetica", 11)
    c.setFillColor(GRAY)
    c.drawCentredString(w/2, 70, "Annual plans save 17% | 14-day free trial | No credit card required")


# ═══════════════════════════════════════════════════════
# 1. PRESENTATION PDF (16:9 landscape slides)
# ═══════════════════════════════════════════════════════
def generate_presentation():
    W, H = landscape(A4)
    path = os.path.join(OUT_DIR, "FLOWRA_Presentation.pdf")
    c = canvas.Canvas(path, pagesize=(W, H))

    # Slide 1: Title
    draw_title_slide(c, W, H, "FLOWRA", "Unlock the Full Power of Your Tally* Data")
    c.showPage()

    # Slide 2: The Problem
    draw_content_slide(c, W, H, "The Problem", [
        "Tally* data is locked on your desktop",
        "No mobile access to sales, inventory, or outstanding",
        "Manual Excel exports waste 3-4 hours every week",
        "No real-time visibility for business owners on the move",
        "Multi-branch transfers inflate actual sales figures",
        "No Cash Flow or P&L view outside Tally*",
    ])
    c.showPage()

    # Slide 3: Solution
    draw_content_slide(c, W, H, "FLOWRA: Your Tally* Analytics Cloud", [
        "Auto-syncs with Tally* in real-time via Desktop Connector v8",
        "Access sales, inventory, CRM, P&L from any device",
        "Bank-grade 256-bit AES + Fernet encrypted local auth",
        "2-minute setup with guided onboarding tour",
        "reCAPTCHA v3 security + 15-min idle auto-logout",
        "Built specifically for Indian SMEs",
    ], DEMO_SS["landing"])
    c.showPage()

    # Slide 4: Dashboard
    draw_content_slide(c, W, H, "Live Business Dashboard", [
        "Total Sales, Items, Low Stock at a glance",
        "FY-wise and cross-FY sales tracking",
        "Top customers ranked by revenue",
        "Overdue payment alerts with aging",
        "Branch/Division toggle for accurate figures",
        "Auto-refreshes with latest Tally* data",
    ], DEMO_SS["dashboard"])
    c.showPage()

    # Slide 5: Sales
    draw_content_slide(c, W, H, "Sales Analytics", [
        "Sales trend charts with daily breakdown",
        "Filter by customer, month, financial year",
        "Voucher-level drill-down with item details",
        "Export to PDF and Excel in one click",
        "Branch sales can be excluded for accuracy",
        "Customer-wise item sales breakdown",
    ], DEMO_SS["sales"])
    c.showPage()

    # Slide 6: CRM
    draw_content_slide(c, W, H, "Customer CRM", [
        "Customer targets with achievement tracking",
        "Outstanding and overdue management",
        "Follow-up scheduling and reminders",
        "Payment behavior scoring and analysis",
        "One-click Excel export of outstanding & targets",
        "Monthly/Annual target setting",
    ], DEMO_SS["crm"])
    c.showPage()

    # Slide 7: Inventory
    draw_content_slide(c, W, H, "Inventory Intelligence", [
        "Real-time stock levels from Tally*",
        "Smart auto-reorder levels (2-month avg sales)",
        "Movement analysis: Opening > Inward > Sales > Closing",
        "Below-cost sales detection (negative margin)",
        "Sales frequency analysis per item",
        "AI-powered Purchase Order generation",
    ], DEMO_SS["analytics"])
    c.showPage()

    # Slide 8: CA Corner (NEW)
    draw_content_slide(c, W, H, "CA Corner - Your Digital Accountant", [
        "Cash Flow Statement (Tally* Indirect Method)",
        "Operating, Investing & Financing activity breakdown",
        "P&L Report: Annual view + Monthly 12-column toggle",
        "AI Expense Insights powered by GPT (cost reduction tips)",
        "Expense Health Score, Red Flags & Quick Wins",
        "Bank & Cash account details with opening/closing",
    ])
    c.showPage()

    # Slide 9: Refer & Earn (NEW)
    draw_content_slide(c, W, H, "Refer & Earn Program", [
        "Every user gets a unique referral code",
        "Earn 3% commission when your referral subscribes",
        "Track referral status in real-time (pending/subscribed)",
        "Redeem commission via simple approval flow",
        "No cap on earnings - refer unlimited businesses",
        "Commission auto-calculated on subscription amount",
    ])
    c.showPage()

    # Slide 10: Security
    draw_content_slide(c, W, H, "Enterprise-Grade Security", [
        "256-bit AES encryption for all company data",
        "Fernet-encrypted local auth in Desktop Connector",
        "Google reCAPTCHA v3 on login & signup",
        "15-minute idle session auto-logout",
        "UUID-based tenant isolation",
        "Role-based access control (Admin, Employee, Super Admin)",
    ])
    c.showPage()

    # Slide 11: Pricing
    draw_pricing_slide(c, W, H)
    c.showPage()

    # Slide 12: CTA
    draw_title_slide(c, W, H, "Start Your Free Trial", "14 days free | No credit card | Cancel anytime")
    c.setFont("Helvetica", 14)
    c.setFillColor(GRAY)
    c.drawCentredString(W/2, H/2 - 90, "support@flowralive.in  |  www.flowralive.in")
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(W/2, 50, "Tally* is the trademark of its respective owner and is not affiliated with FLOWRA or Jodidar India.")
    c.showPage()

    c.save()
    print(f"Presentation: {path}")


# ═══════════════════════════════════════════════════════
# 2. TRAINING BOOKLET PDF
# ═══════════════════════════════════════════════════════
def generate_training_booklet():
    W, H = A4
    path = os.path.join(OUT_DIR, "FLOWRA_Training_Booklet.pdf")
    c = canvas.Canvas(path, pagesize=A4)

    def new_page():
        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY)
        c.drawString(40, 20, "FLOWRA Employee Training Booklet | Confidential")
        c.drawRightString(W - 40, 20, "www.flowralive.in")
        c.showPage()

    def heading(text, y, size=20):
        c.setFont("Helvetica-Bold", size)
        c.setFillColor(DARK)
        c.drawString(50, y, text)
        c.setStrokeColor(BLUE)
        c.setLineWidth(2)
        c.line(50, y - 5, 50 + len(text) * size * 0.45, y - 5)
        return y - 30

    def body(text, y, indent=50):
        c.setFont("Helvetica", 11)
        c.setFillColor(DARK)
        lines = text.split('\n')
        for line in lines:
            if y < 50:
                new_page()
                y = H - 60
            c.drawString(indent, y, line)
            y -= 16
        return y

    def bullet_list(items, y, indent=60):
        for item in items:
            if y < 50:
                new_page()
                y = H - 60
            c.setFillColor(BLUE)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(indent, y, ">")
            c.setFillColor(DARK)
            c.setFont("Helvetica", 11)
            c.drawString(indent + 15, y, item)
            y -= 20
        return y

    # Cover
    c.setFillColor(BLUE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(W/2, H/2 + 60, "FLOWRA")
    c.setFont("Helvetica", 20)
    c.drawCentredString(W/2, H/2 + 20, "Employee Training Booklet")
    c.setFont("Helvetica", 14)
    c.drawCentredString(W/2, H/2 - 30, "Tally* Analytics Platform")
    c.drawCentredString(W/2, H/2 - 55, "www.flowralive.in")
    c.setFont("Helvetica", 10)
    c.drawCentredString(W/2, 60, "CONFIDENTIAL - For Internal Use Only")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#93c5fd"))
    c.drawCentredString(W/2, 40, "Updated: April 2026 | Includes CA Corner, Refer & Earn, Desktop Agent v8")
    c.showPage()

    # ── Page 1: What is FLOWRA? ──
    y = H - 60
    y = heading("1. What is FLOWRA?", y)
    y = body("FLOWRA is a cloud-based analytics platform that connects to Tally*\nand gives business owners real-time access to their data from anywhere.\n\nThink of it as a smart dashboard + CA assistant that sits on top of Tally*.", y)
    y -= 10
    y = heading("Key Value Proposition", y, 16)
    y = bullet_list([
        "Real-time Tally* data on mobile/laptop - anywhere, anytime",
        "Zero manual effort - auto-syncs every few minutes",
        "Bank-grade 256-bit encryption + reCAPTCHA v3 security",
        "2-minute setup with guided onboarding tour",
        "No data migration - Tally* remains your source of truth",
        "CA Corner: Cash Flow, P&L, AI Expense analysis",
    ], y)
    y -= 10
    y = heading("Who is it for?", y, 16)
    y = bullet_list([
        "Distributors and wholesalers using Tally*",
        "Business owners who travel and need remote access",
        "Companies with multiple branches/depots",
        "Accountants and CAs managing multiple company books",
        "Anyone who wants Cash Flow and P&L insights from Tally*",
    ], y)
    new_page()

    # ── Page 2: Product Features ──
    y = H - 60
    y = heading("2. Product Features (What You Demo)", y)
    features = [
        ("Dashboard", "Total sales, items, low stock alerts, overdue payments, top customers. Cross-FY totals. Branch toggle to exclude internal transfers."),
        ("Sales", "Sales trend chart, voucher list with drill-down, filter by customer/month/FY. PDF & Excel export."),
        ("CRM", "Customer targets with achievement %, outstanding tracking with Excel export, follow-up scheduler, payment behavior analysis with credit scoring."),
        ("Inventory", "Real-time stock from Tally*, low stock alerts, smart auto-reorder levels (2-month average). Search & filter by stock group/category."),
        ("Analytics", "Movement Analysis (Opening/Inward/Sales/Closing), Below Cost Sales detection, Sales Frequency, Customer-Item breakdown."),
        ("AI Reports", "AI-generated business insights. Smart Purchase Order recommendations."),
        ("CA Corner", "Cash Flow statement (indirect method), P&L report (annual + 12-month view), AI Expense Insights with cost-reduction tips and health scoring. Enterprise feature."),
        ("Refer & Earn", "Unique referral code per user. 3% commission on subscriber referrals. Real-time tracking and admin-approved redemption."),
        ("Branch Toggle", "One-click global filter to exclude branch/depot transfers from ALL figures."),
        ("Onboarding Tour", "Guided 7-step walkthrough for first-time users - highlights every key feature."),
    ]
    for name, desc in features:
        if y < 80:
            new_page()
            y = H - 60
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(BLUE)
        c.drawString(60, y, name)
        c.setFont("Helvetica", 10)
        c.setFillColor(DARK)
        words = desc.split()
        line = ""
        dy = y - 16
        for w in words:
            if len(line + w) > 85:
                c.drawString(60, dy, line)
                dy -= 14
                line = w + " "
            else:
                line += w + " "
        if line:
            c.drawString(60, dy, line)
            dy -= 14
        y = dy - 8
    new_page()

    # ── Page 3: How Setup Works ──
    y = H - 60
    y = heading("3. How Setup Works (Explain to Customer)", y)
    steps = [
        "Step 1: Customer signs up at www.flowralive.in (free 14-day trial)",
        "Step 2: Guided onboarding tour highlights all features automatically",
        "Step 3: Download Desktop Connector v8 from Setup page",
        "Step 4: Run the connector on the PC where Tally* is installed",
        "Step 5: Connector auto-detects Tally* and starts syncing",
        "Step 6: Data appears in FLOWRA dashboard within 2 minutes",
        "",
        "Requirements: Tally* running on the PC, Internet connection",
        "Port: Tally* uses port 9000 by default (configurable)",
        "The connector runs in background - no manual intervention needed",
    ]
    y = bullet_list(steps, y)
    y -= 20
    y = heading("Desktop Connector v8 Highlights", y, 16)
    y = bullet_list([
        "Fernet-encrypted local credential storage (no plain-text passwords)",
        "Automatic FY discovery from Tally*",
        "Fetches Bank, Cash & Contra ledgers for Cash Flow",
        "Fetches P&L data for CA Corner reports",
        "256-bit AES encryption for all data in transit",
        "Multi-company support - one connector handles all Tally* companies",
    ], y)
    new_page()

    # ── Page 4: Pricing & Plans ──
    y = H - 60
    y = heading("4. Pricing (Memorize This)", y)
    y -= 5
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(DARK)
    plans = [
        ("Starter", "Rs.999/mo or Rs.9,990/yr", "1 Company, 2 Users", "Dashboard, Sales, Inventory, Basic Analytics"),
        ("Professional", "Rs.2,499/mo or Rs.24,990/yr", "3 Companies, 5 Users", "+ CRM, AI Reports, CA Corner, Excel Exports"),
        ("Enterprise", "Rs.3,799/mo or Rs.37,990/yr", "10 Companies, 20 Users", "+ Salesman Module, Priority Support, Full CA Corner"),
    ]
    for name, price, limits, feat in plans:
        if y < 100:
            new_page()
            y = H - 60
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(BLUE)
        c.drawString(60, y, name)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(DARK)
        c.drawString(200, y, price)
        y -= 18
        c.setFont("Helvetica", 10)
        c.setFillColor(GRAY)
        c.drawString(60, y, f"{limits} | {feat}")
        y -= 28
    y -= 10
    y = heading("Objection Handling", y, 16)
    objections = [
        '"Too expensive" -> Calculate time saved: 3-4 hrs/week x Rs.500/hr = Rs.8,000/mo saved minimum',
        '"We already use Tally" -> FLOWRA does not replace Tally*. It extends it to mobile/remote access + CA Corner',
        '"Is my data safe?" -> 256-bit encryption + reCAPTCHA + idle timeout. Same grade as banks',
        '"Can I try before buying?" -> 14-day free trial, no credit card required',
        '"What if Tally is not running?" -> Connector syncs when Tally* is open. Last synced data always available',
        '"We already have a CA" -> CA Corner supplements your CA with instant P&L and Cash Flow visibility',
    ]
    y = bullet_list(objections, y)
    new_page()

    # ── Page 5: Demo Script ──
    y = H - 60
    y = heading("5. Demo Call Script (7-Minute Version)", y)
    script = [
        '1. "Let me show you how FLOWRA works with your Tally* data..."',
        '2. Open Dashboard - Show total sales, top customers, overdue payments',
        '3. Click Sales - Show voucher list, click a voucher for item details',
        '4. Click CRM > Targets - Show customer achievement tracking',
        '5. Click CRM > Outstanding - Show export to Excel button',
        '6. Click Inventory - Show stock levels, auto-reorder alerts',
        '7. Click Analytics > Movement - Show opening/inward/sales/closing',
        '8. Toggle Branch filter - Show how figures change',
        '9. Click CA Corner > Cash Flow - Show indirect method cash flow',
        '10. Click CA Corner > P&L - Toggle annual vs monthly view',
        '11. Click CA Corner > AI Insights - Show expense analysis',
        '12. Click Refer & Earn - Show 3% commission program',
        '13. Click Setup - Show one-click Desktop Connector v8 download',
        '14. "All of this syncs automatically. No manual work."',
    ]
    y = bullet_list(script, y)
    y -= 15
    y = heading("Closing Lines", y, 16)
    y = bullet_list([
        '"Would you like to start a free 14-day trial?"',
        '"I can help you set it up right now - it takes 2 minutes"',
        '"Which plan fits your number of companies and users?"',
        '"You can also earn by referring other businesses - 3% commission!"',
    ], y)
    new_page()

    # ── Page 6: FAQ ──
    y = H - 60
    y = heading("6. Frequently Asked Questions", y)
    faqs = [
        ("Does FLOWRA work with all versions of Tally?", "FLOWRA works with Tally Prime (latest). Tally ERP 9 is not supported."),
        ("Can I access FLOWRA on my phone?", "Yes! FLOWRA is fully responsive - works on mobile, tablet, and desktop browsers."),
        ("What happens if my internet goes down?", "The Desktop Connector queues data and syncs when internet returns. FLOWRA shows last synced data."),
        ("Can multiple employees use FLOWRA?", "Yes, based on your plan. Starter=2, Professional=5, Enterprise=20 users."),
        ("How is FLOWRA different from Tally on Mobile?", "Tally Mobile is basic data view. FLOWRA provides analytics, CRM, AI reports, CA Corner, movement analysis, referrals, and branch filtering."),
        ("What is CA Corner?", "It gives you instant Cash Flow (indirect method), P&L reports (annual + monthly), and AI-powered expense insights - all from your Tally* data."),
        ("How does Refer & Earn work?", "Share your unique referral code. When someone signs up and subscribes, you earn 3% commission on their subscription amount. Redeemable via admin approval."),
        ("What is the Branch Toggle?", "It filters out inter-branch transfers (depot/division) from ALL sales figures globally, showing actual customer sales only."),
        ("Is there auto-reorder for inventory?", "Yes. FLOWRA calculates reorder levels based on 2-month average sales and rounds up using smart logic. You can also set manual overrides."),
        ("Can I export data to Excel?", "Yes. CRM Outstanding, CRM Targets, and several other reports have one-click Excel export."),
        ("What if I cancel?", "You can cancel anytime. Data sync stops but your Tally data is untouched."),
        ("How secure is my login?", "Google reCAPTCHA v3, bcrypt passwords, JWT tokens, and 15-minute idle auto-logout protect every session."),
    ]
    for q, a in faqs:
        if y < 80:
            new_page()
            y = H - 60
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DARK)
        c.drawString(60, y, f"Q: {q}")
        y -= 16
        c.setFont("Helvetica", 10)
        c.setFillColor(GRAY)
        words = a.split()
        line = "A: "
        for w in words:
            if len(line + w) > 90:
                c.drawString(60, y, line)
                y -= 14
                line = "   " + w + " "
            else:
                line += w + " "
        if line:
            c.drawString(60, y, line)
            y -= 14
        y -= 12
    new_page()

    # ── Page 7: Quick Reference Card ──
    y = H - 60
    y = heading("7. Quick Reference Card", y)
    y -= 5
    refs = [
        ("Website", "www.flowralive.in"),
        ("Support Email", "support@flowralive.in"),
        ("Free Trial", "14 days, no credit card"),
        ("Setup Time", "2 minutes with guided tour"),
        ("Encryption", "256-bit AES + Fernet (bank-grade)"),
        ("Sync Frequency", "Every 5 minutes (automatic)"),
        ("Tally* Compat.", "Tally Prime (latest version)"),
        ("Desktop Agent", "v8 (FY discovery, encrypted auth, P&L + Cash Flow sync)"),
        ("Plans", "Starter Rs.999 | Pro Rs.2,499 | Enterprise Rs.3,799/mo"),
        ("Annual Discount", "17% off (2 months free)"),
        ("Refer & Earn", "3% commission on each successful referral"),
        ("Key New Feature", "CA Corner: Cash Flow, P&L, AI Expense Insights"),
    ]
    for label, val in refs:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DARK)
        c.drawString(60, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.setFillColor(BLUE)
        c.drawString(210, y, val)
        y -= 22

    y -= 10
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawString(50, y, "Tally* is the trademark of its respective owner and is not affiliated with FLOWRA or Jodidar India.")

    c.setFont("Helvetica", 7)
    c.setFillColor(GRAY)
    c.drawString(40, 20, "FLOWRA Employee Training Booklet | Confidential")
    c.drawRightString(W - 40, 20, "www.flowralive.in")
    c.showPage()
    c.save()
    print(f"Training Booklet: {path}")


# ═══════════════════════════════════════════════════════
# 3. SOCIAL MEDIA KIT PDF
# ═══════════════════════════════════════════════════════
def generate_social_media_kit():
    W, H = A4
    path = os.path.join(OUT_DIR, "FLOWRA_Social_Media_Kit.pdf")
    c = canvas.Canvas(path, pagesize=A4)

    def footer():
        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY)
        c.drawString(40, 20, "FLOWRA Social Media Promotion Kit")
        c.drawRightString(W - 40, 20, "www.flowralive.in")

    # Cover
    c.setFillColor(DARK)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.rect(0, H/2 - 2, W, 4, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(W/2, H/2 + 60, "FLOWRA")
    c.setFont("Helvetica", 18)
    c.drawCentredString(W/2, H/2 + 25, "Social Media Promotion Kit")
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(W/2, H/2 - 40, "Instagram | LinkedIn | Facebook | Twitter/X | WhatsApp")
    c.setFont("Helvetica", 10)
    c.drawCentredString(W/2, H/2 - 65, "Updated April 2026 - Now featuring CA Corner & Refer & Earn")
    c.showPage()

    # Page 1: Brand Guidelines
    y = H - 60
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(DARK)
    c.drawString(50, y, "Brand Guidelines")
    y -= 40
    guidelines = [
        ("Brand Name", "FLOWRA (always uppercase)"),
        ("Tagline", "Unlock the Full Power of Your Tally* Data"),
        ("Primary Color", "#2563EB (Blue)"),
        ("Secondary", "#0f172a (Dark Navy)"),
        ("Accent", "#16a34a (Green for success/CTA)"),
        ("Font", "Clean sans-serif (Helvetica, Inter, or system font)"),
        ("Tone", "Professional, confident, helpful. Speak to business owners."),
        ("Target Audience", "Indian SME distributors/wholesalers using Tally*"),
        ("Hashtags", "#FLOWRA #TallyPrime #TallyAnalytics #CashFlow #ProfitAndLoss #CACorner"),
        ("Website", "www.flowralive.in"),
        ("CTA", "Start your 14-day free trial at www.flowralive.in"),
        ("Trademark", "Always write Tally* with asterisk in copy"),
    ]
    for label, val in guidelines:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DARK)
        c.drawString(60, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.setFillColor(GRAY)
        c.drawString(200, y, val)
        y -= 22
    footer()
    c.showPage()

    # Social Media Posts
    posts = [
        {
            "platform": "LinkedIn / Facebook",
            "title": "Launch Announcement (Updated)",
            "caption": """Tired of being chained to your office just to check Tally* reports?

Introducing FLOWRA - the analytics platform that connects directly to your Tally* and gives you real-time business insights on any device.

> Live Dashboard with total sales, inventory alerts, and overdue payments
> Customer CRM with target tracking, payment behavior & Excel export
> CA Corner: Cash Flow, P&L reports, AI Expense Insights
> Smart Auto-Reorder levels based on 2-month sales data
> Bank-grade 256-bit encryption + reCAPTCHA v3 protection

Your Tally* data, everywhere you go. No manual exports. No Excel sheets.

Plus: Earn 3% commission with our Refer & Earn program!

Start your free 14-day trial: www.flowralive.in

#FLOWRA #TallyPrime #BusinessAnalytics #CashFlow #ProfitAndLoss #CACorner #IndianSME""",
            "image_desc": "Use: Dashboard screenshot showing Total Sales, Top Customers, and branch toggle"
        },
        {
            "platform": "LinkedIn / Facebook",
            "title": "CA Corner Feature Launch",
            "caption": """Your CA doesn't need to send you P&L reports anymore.

FLOWRA's new CA Corner gives you instant access to:

> Cash Flow Statement (Tally* Indirect Method) - Operating, Investing, Financing
> Profit & Loss - Annual view + 12-month breakdown (Apr to Mar)
> AI Expense Insights - Identifies overspending, suggests cost reductions
> Expense Health Score with Red Flags and Quick Wins

All auto-synced from your Tally*. No manual data entry. No waiting.

Your accountant will thank you. Your CA will be impressed.

Try it free: www.flowralive.in

#CACorner #CashFlow #ProfitAndLoss #TallyPrime #FLOWRA #BusinessIntelligence""",
            "image_desc": "Use: CA Corner screenshots - Cash Flow + P&L Monthly view"
        },
        {
            "platform": "LinkedIn / Facebook",
            "title": "Refer & Earn Campaign",
            "caption": """Know a business owner who uses Tally*?

Refer them to FLOWRA and earn 3% commission on every subscription they pay.

How it works:
1. Share your unique referral code (available in your FLOWRA dashboard)
2. Your referral signs up and subscribes
3. You earn 3% commission - tracked and paid automatically

No cap. No limit. The more you refer, the more you earn.

Start referring: www.flowralive.in

#ReferAndEarn #FLOWRA #PassiveIncome #TallyPrime #BusinessGrowth""",
            "image_desc": "Use: Refer & Earn page screenshot showing commission tracking"
        },
        {
            "platform": "Instagram / Reels",
            "title": "Feature Highlight Series (Updated)",
            "caption": """Post 1: Dashboard
"Your entire business in one screen."
Total sales. Top customers. Overdue alerts. Auto-synced from Tally*.

Post 2: CA Corner
"Cash Flow + P&L - instantly."
No more waiting for your CA. Indirect method. AI insights.

Post 3: CRM
"Know your customer before they call."
Targets. Outstanding. Payment history. Excel export.

Post 4: Smart Reorder
"Never run out of stock again."
Auto-calculated reorder levels from 2-month sales average.

Post 5: Refer & Earn
"Share FLOWRA. Earn 3%."
Unlimited referrals. Real commission. Auto-tracked.

Post 6: Security
"Your Tally* data, safer than your email."
256-bit AES + reCAPTCHA + idle timeout + encrypted local auth.

www.flowralive.in""",
            "image_desc": "Create carousel images from each app screenshot with brand overlay"
        },
        {
            "platform": "Twitter/X",
            "title": "Thread Series (Updated)",
            "caption": """Tweet 1:
Tally* users - your data is trapped on your desktop.

FLOWRA fixes that. Real-time analytics + CA reports from Tally*, on any device.

Thread:

1/ Dashboard: Total sales, items, overdue alerts, top customers. Refreshes every 5 mins.

2/ CA Corner: Cash Flow (indirect method), P&L (annual + monthly), AI Expense Insights.

3/ CRM: Customer targets, payment behavior scores, Excel export. No more manual tracking.

4/ Inventory: Real-time stock from Tally*. Smart auto-reorder levels (2-month avg).

5/ Refer & Earn: Share your code. Earn 3% commission. No cap.

6/ Security: 256-bit AES + reCAPTCHA v3 + 15-min idle timeout + Fernet encrypted auth.

7/ Setup: 2 minutes. Guided onboarding tour. Download connector v8, run, done.

www.flowralive.in

#TallyPrime #FLOWRA #CashFlow #Analytics""",
            "image_desc": "Pin Dashboard screenshot as thread header image"
        },
        {
            "platform": "WhatsApp Business Broadcast",
            "title": "Direct Outreach Messages (Updated)",
            "caption": """Message 1 (Cold):
Hi [Name],

Do you use Tally* for your business?

FLOWRA connects to your Tally* and gives you real-time sales, inventory, Cash Flow, and P&L on your phone.

New: AI Expense Insights that find where you're overspending.

2-minute setup. 14-day free trial. www.flowralive.in

---

Message 2 (CA Corner Focus):
Hi [Name],

Quick question - how do you get your Cash Flow or P&L report today?

With FLOWRA's new CA Corner, you get instant Cash Flow (indirect method), P&L (monthly + annual), and AI cost-reduction tips - all synced from Tally*.

No manual work. Free to try: www.flowralive.in

---

Message 3 (Refer & Earn):
Hi [Name],

Already using FLOWRA? You can now earn 3% commission by referring other businesses!

Share your referral code > They subscribe > You earn.

Check your code in the Refer & Earn section: www.flowralive.in""",
            "image_desc": "Attach Dashboard, CA Corner, and Refer & Earn screenshots"
        },
        {
            "platform": "Google My Business / Local SEO",
            "title": "Business Description (Updated)",
            "caption": """FLOWRA - Tally* Analytics Platform

FLOWRA connects to your Tally* software and provides real-time business analytics on any device. Access sales reports, inventory levels, customer CRM, Cash Flow, P&L reports, and AI-powered insights from your phone or laptop.

Features:
- Live dashboard with sales, inventory, and overdue alerts
- Customer CRM with target tracking, payment behavior & Excel export
- CA Corner: Cash Flow (indirect method), P&L, AI Expense Insights
- Movement analysis, below-cost sales detection, auto-reorder levels
- Branch/Division filter for multi-location businesses
- Refer & Earn: 3% commission on referrals
- 256-bit AES encryption + reCAPTCHA v3 (bank-grade security)

Plans starting at Rs.999/month. 14-day free trial.

Website: www.flowralive.in
Email: support@flowralive.in""",
            "image_desc": "Use Landing page screenshot as primary business image"
        },
    ]

    for post in posts:
        y = H - 50
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(BLUE)
        c.drawString(50, y, post["platform"].upper())
        y -= 22
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(DARK)
        c.drawString(50, y, post["title"])
        y -= 25
        c.setFillColor(HexColor("#e2e8f0"))
        c.rect(45, y, W - 90, 1, fill=1, stroke=0)
        y -= 15
        c.setFont("Helvetica", 9)
        c.setFillColor(DARK)
        for line in post["caption"].split('\n'):
            if y < 80:
                footer()
                c.showPage()
                y = H - 50
            if line.startswith('>') or line.startswith('-') or line.startswith('#'):
                c.setFillColor(BLUE)
            elif line.startswith('"') or line.startswith("'"):
                c.setFillColor(HexColor("#374151"))
                c.setFont("Helvetica-Oblique", 9)
            else:
                c.setFillColor(DARK)
                c.setFont("Helvetica", 9)
            if len(line) > 95:
                words = line.split()
                buf = ""
                for w in words:
                    if len(buf + w) > 95:
                        c.drawString(55, y, buf)
                        y -= 13
                        buf = w + " "
                    else:
                        buf += w + " "
                if buf:
                    c.drawString(55, y, buf)
                    y -= 13
            else:
                c.drawString(55, y, line)
                y -= 13
        y -= 8
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(AMBER)
        c.drawString(55, y, f"Image: {post['image_desc']}")
        footer()
        c.showPage()

    # Content Calendar
    y = H - 50
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(DARK)
    c.drawString(50, y, "30-Day Content Calendar")
    y -= 35
    weeks = [
        ("Week 1: CA Corner Launch", [
            "Mon: LinkedIn - CA Corner announcement + Cash Flow screenshot",
            "Tue: Instagram carousel (CA Corner: Cash Flow / P&L / AI Insights)",
            "Wed: Twitter/X thread (7 tweets - full feature walkthrough)",
            "Thu: WhatsApp broadcast - CA Corner to existing contacts",
            "Fri: Facebook post + video demo of P&L monthly toggle",
        ]),
        ("Week 2: Refer & Earn Push", [
            "Mon: LinkedIn - Refer & Earn announcement (3% commission)",
            "Tue: Instagram Reel - 'How to earn from FLOWRA referrals'",
            "Wed: Twitter - Refer & Earn tips thread",
            "Thu: WhatsApp - Referral code reminder to active users",
            "Fri: LinkedIn - Success story: 'How I earned Rs.X from referrals'",
        ]),
        ("Week 3: Problem-Solution", [
            "Mon: LinkedIn - 'Why your CA needs FLOWRA too'",
            "Tue: Instagram - Before/After (Excel vs FLOWRA CA Corner)",
            "Wed: Twitter - Quick tip: auto-reorder levels",
            "Thu: WhatsApp - Free trial reminder with CA Corner angle",
            "Fri: LinkedIn - Security deep-dive (reCAPTCHA + idle timeout)",
        ]),
        ("Week 4: Conversion Push", [
            "Mon: LinkedIn - Pricing comparison with ROI calculation",
            "Tue: Instagram - 'Day in the life with FLOWRA' Reel",
            "Wed: Twitter - FAQ thread (CA Corner + Refer & Earn)",
            "Thu: WhatsApp - Limited time offer (if applicable)",
            "Fri: All platforms - Month summary + CTA + referral push",
        ]),
    ]
    for week_title, days in weeks:
        if y < 160:
            footer()
            c.showPage()
            y = H - 50
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(BLUE)
        c.drawString(55, y, week_title)
        y -= 20
        for day in days:
            c.setFont("Helvetica", 9)
            c.setFillColor(DARK)
            c.drawString(70, y, day)
            y -= 15
        y -= 12
    footer()
    c.showPage()
    c.save()
    print(f"Social Media Kit: {path}")


# ═══════════════════════════════════════════════════════
# 4. CUSTOMER NEEDS QUESTIONNAIRE PDF (NEW)
# ═══════════════════════════════════════════════════════
def generate_customer_questionnaire():
    W, H = A4
    path = os.path.join(OUT_DIR, "FLOWRA_Customer_Questionnaire.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    page_num = [0]

    def page_footer():
        page_num[0] += 1
        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY)
        c.drawString(40, 20, f"FLOWRA Customer Needs Assessment | Page {page_num[0]}")
        c.drawRightString(W - 40, 20, "www.flowralive.in | Confidential")

    def section_heading(text, y):
        c.setFillColor(BLUE)
        c.roundRect(45, y - 8, W - 90, 28, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(WHITE)
        c.drawString(60, y, text)
        return y - 38

    def field_line(label, y, width=350):
        if y < 60:
            page_footer()
            c.showPage()
            y = H - 60
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(DARK)
        c.drawString(60, y, label)
        c.setStrokeColor(HexColor("#cbd5e1"))
        c.setLineWidth(0.5)
        label_end = 60 + len(label) * 5.5 + 10
        c.line(label_end, y - 2, label_end + width - len(label)*5, y - 2)
        return y - 26

    def checkbox_group(question, options, y, cols=1):
        if y < 60 + len(options) * 20:
            page_footer()
            c.showPage()
            y = H - 60
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(DARK)
        c.drawString(60, y, question)
        y -= 22
        if cols == 1:
            for opt in options:
                c.setStrokeColor(HexColor("#94a3b8"))
                c.setLineWidth(0.8)
                c.rect(68, y - 2, 10, 10, fill=0, stroke=1)
                c.setFont("Helvetica", 10)
                c.setFillColor(DARK)
                c.drawString(84, y, opt)
                y -= 20
        else:
            col_w = (W - 120) / cols
            for i, opt in enumerate(options):
                col = i % cols
                row = i // cols
                x = 68 + col * col_w
                oy = y - row * 20
                c.setStrokeColor(HexColor("#94a3b8"))
                c.setLineWidth(0.8)
                c.rect(x, oy - 2, 10, 10, fill=0, stroke=1)
                c.setFont("Helvetica", 10)
                c.setFillColor(DARK)
                c.drawString(x + 16, oy, opt)
            total_rows = (len(options) + cols - 1) // cols
            y -= total_rows * 20
        return y - 8

    def rating_scale(question, y):
        if y < 60:
            page_footer()
            c.showPage()
            y = H - 60
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(DARK)
        c.drawString(60, y, question)
        y -= 22
        labels = ["1 - Not Important", "2", "3 - Neutral", "4", "5 - Very Important"]
        x_start = 68
        gap = 85
        for i, lbl in enumerate(labels):
            x = x_start + i * gap
            c.setStrokeColor(HexColor("#94a3b8"))
            c.setLineWidth(0.8)
            c.circle(x + 5, y + 4, 5, fill=0, stroke=1)
            c.setFont("Helvetica", 8)
            c.setFillColor(GRAY)
            c.drawString(x + 14, y + 1, lbl)
        return y - 24

    def notes_box(label, y, height=60):
        if y < 60 + height:
            page_footer()
            c.showPage()
            y = H - 60
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(DARK)
        c.drawString(60, y, label)
        y -= 12
        c.setStrokeColor(HexColor("#cbd5e1"))
        c.setLineWidth(0.5)
        c.rect(60, y - height, W - 120, height, fill=0, stroke=1)
        return y - height - 12

    # ── COVER PAGE ──
    c.setFillColor(DARK)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    # Blue accent strip
    c.setFillColor(BLUE)
    c.rect(0, H/2 + 30, W, 6, fill=1, stroke=0)
    # Title
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(W/2, H/2 + 70, "FLOWRA")
    c.setFont("Helvetica", 20)
    c.drawCentredString(W/2, H/2 + 10, "Customer Needs Assessment")
    c.setFont("Helvetica", 14)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawCentredString(W/2, H/2 - 25, "Understanding Your Requirements")
    c.drawCentredString(W/2, H/2 - 50, "to Recommend the Best FLOWRA Plan")
    # Bottom info
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#64748b"))
    c.drawCentredString(W/2, 80, "www.flowralive.in  |  support@flowralive.in")
    c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, 60, "Jodidar India  |  Confidential")
    c.showPage()

    # ── SECTION A: COMPANY INFORMATION ──
    y = H - 50
    y = section_heading("A. Company Information", y)
    y -= 5
    y = field_line("Company Name:", y)
    y = field_line("Contact Person:", y)
    y = field_line("Designation:", y)
    y = field_line("Phone:", y)
    y = field_line("Email:", y)
    y = field_line("City / Location:", y)
    y -= 5
    y = checkbox_group("Industry / Business Type:", [
        "Distributor / Wholesaler",
        "Manufacturer",
        "Retailer",
        "Trader / Commission Agent",
        "Service Provider",
        "Other: ___________________",
    ], y)
    y = checkbox_group("Number of Employees:", [
        "1-5", "6-15", "16-50", "51-200", "200+",
    ], y, cols=3)
    y = checkbox_group("Annual Turnover (approx.):", [
        "Below Rs.50 Lakh",
        "Rs.50 Lakh - 2 Crore",
        "Rs.2 Crore - 10 Crore",
        "Rs.10 Crore - 50 Crore",
        "Above Rs.50 Crore",
    ], y, cols=2)
    page_footer()
    c.showPage()

    # ── SECTION B: CURRENT TALLY USAGE ──
    y = H - 50
    y = section_heading("B. Current Tally* Usage", y)
    y -= 5
    y = checkbox_group("Which Tally* version are you using?", [
        "Tally Prime (Latest)",
        "Tally Prime (Older release)",
        "Tally ERP 9 (Not supported by FLOWRA)",
        "Not sure",
    ], y)
    y = field_line("How many companies in Tally*?", y)
    y = field_line("How many Tally* users / terminals?", y)
    y = checkbox_group("Do you have multiple branches / depots?", [
        "Yes - Number of branches: ________",
        "No - Single location",
    ], y)
    y = checkbox_group("How do you currently access Tally* data remotely?", [
        "We don't - office only",
        "Tally on Mobile app",
        "Remote Desktop / TeamViewer",
        "WhatsApp photos from accountant",
        "Manual Excel exports emailed",
        "Other: ___________________",
    ], y)
    y = checkbox_group("Who uses Tally* in your organization?", [
        "Accountant / Bookkeeper",
        "Business Owner / Director",
        "Sales Team",
        "Warehouse / Inventory Team",
        "CA / External Auditor",
    ], y, cols=2)
    page_footer()
    c.showPage()

    # ── SECTION C: PAIN POINTS ──
    y = H - 50
    y = section_heading("C. Current Pain Points (Check All That Apply)", y)
    y -= 5
    y = checkbox_group("What frustrates you most about your current setup?", [
        "Cannot check sales / outstanding from phone when traveling",
        "Manual Excel exports take too much time (3-4 hrs/week)",
        "Branch transfers inflate my actual sales figures",
        "No visibility into customer payment behavior",
        "Dead stock / slow-moving items pile up unnoticed",
        "Cannot get Cash Flow or P&L without waiting for accountant",
        "No way to set and track customer-wise sales targets",
        "Reorder levels are guesswork - no data-driven suggestions",
        "Multiple Tally companies but no unified view",
        "Security concern - employees share Tally login",
        "No audit trail of who accessed what data",
        "Other: ___________________",
    ], y)
    y -= 5
    y = notes_box("Describe your biggest daily challenge with Tally* data:", y, 70)
    page_footer()
    c.showPage()

    # ── SECTION D: FEATURE INTEREST ──
    y = H - 50
    y = section_heading("D. Feature Interest & Priority (Rate 1-5)", y)
    y -= 5
    c.setFont("Helvetica", 8)
    c.setFillColor(GRAY)
    c.drawString(60, y, "(1 = Not Important, 3 = Nice to Have, 5 = Must Have)")
    y -= 20
    features = [
        "Live Dashboard (sales, inventory, outstanding overview)",
        "Sales Analytics (trends, voucher drill-down, customer breakdown)",
        "Customer CRM (targets, follow-ups, payment behavior scoring)",
        "Outstanding & Overdue Management with Excel Export",
        "Inventory with Stock Alerts & Smart Auto-Reorder",
        "Movement Analysis (Opening > Inward > Sales > Closing)",
        "Below Cost Sales Detection (negative margin alerts)",
        "AI-Powered Purchase Order Recommendations",
        "CA Corner: Cash Flow Statement (Indirect Method)",
        "CA Corner: P&L Report (Annual + Monthly Toggle)",
        "CA Corner: AI Expense Insights & Health Score",
        "Branch Toggle (exclude internal transfers from all figures)",
        "Refer & Earn (3% commission on referrals)",
        "Mobile Access (phone & tablet)",
        "Multi-Company Support (single login, multiple Tally companies)",
    ]
    for feat in features:
        y = rating_scale(feat, y)
    page_footer()
    c.showPage()

    # ── SECTION E: DECISION CRITERIA ──
    y = H - 50
    y = section_heading("E. Decision Criteria & Timeline", y)
    y -= 5
    y = checkbox_group("What is most important to you in choosing a solution?", [
        "Price / Value for money",
        "Ease of setup (no IT team needed)",
        "Data security & encryption",
        "Mobile access / anywhere availability",
        "Specific features (mention below)",
        "Customer support quality",
        "Integration with existing Tally* without changes",
    ], y)
    y = checkbox_group("When are you looking to implement?", [
        "Immediately (this week)",
        "Within 1 month",
        "Within 3 months",
        "Just exploring / no timeline",
    ], y, cols=2)
    y = checkbox_group("Who will make the final purchase decision?", [
        "I am the decision maker",
        "Need to consult with partner / director",
        "IT team will evaluate",
        "CA / Auditor recommendation needed",
    ], y, cols=2)
    y = checkbox_group("Budget range for analytics tool (per month)?", [
        "Below Rs.500",
        "Rs.500 - Rs.1,000",
        "Rs.1,000 - Rs.2,500",
        "Rs.2,500 - Rs.4,000",
        "Above Rs.4,000 (need custom features)",
    ], y, cols=2)
    y -= 5
    y = notes_box("Any specific features you need that were not mentioned?", y, 55)
    page_footer()
    c.showPage()

    # ── SECTION F: REFERRAL & NEXT STEPS ──
    y = H - 50
    y = section_heading("F. Referral & Next Steps", y)
    y -= 5
    y = checkbox_group("How did you hear about FLOWRA?", [
        "Google Search",
        "LinkedIn / Social Media",
        "Referral from another business",
        "WhatsApp message",
        "Trade show / event",
        "CA / Accountant recommendation",
        "Other: ___________________",
    ], y)
    y = checkbox_group("Would you like to:", [
        "Start a 14-day free trial right now",
        "Schedule a live demo with screen share",
        "Receive pricing details via email",
        "Get a call back at a convenient time",
        "Share this with my team / partner first",
    ], y)
    y = field_line("Preferred call-back time:", y)
    y -= 10
    y = notes_box("Additional notes / special requirements:", y, 60)

    y -= 10
    # Recommendation box
    c.setFillColor(LIGHT_BG)
    c.roundRect(50, y - 85, W - 100, 85, 6, fill=1, stroke=0)
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.5)
    c.roundRect(50, y - 85, W - 100, 85, 6, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(BLUE)
    c.drawString(65, y - 18, "FOR SALES REP - Recommended Plan:")
    c.setStrokeColor(HexColor("#94a3b8"))
    c.setLineWidth(0.8)
    recs = ["Starter (Rs.999)", "Professional (Rs.2,499)", "Enterprise (Rs.3,799)", "Custom"]
    for i, rec in enumerate(recs):
        x = 70 + i * 120
        c.rect(x, y - 45, 10, 10, fill=0, stroke=1)
        c.setFont("Helvetica", 9)
        c.setFillColor(DARK)
        c.drawString(x + 14, y - 43, rec)
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawString(65, y - 68, "Key selling points for this customer: ____________________________________________________")

    page_footer()
    c.showPage()

    # ── BACK COVER ──
    c.setFillColor(BLUE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(W/2, H/2 + 40, "Thank You")
    c.setFont("Helvetica", 16)
    c.drawCentredString(W/2, H/2, "We appreciate your time and interest in FLOWRA")
    c.setFont("Helvetica", 12)
    c.drawCentredString(W/2, H/2 - 40, "www.flowralive.in  |  support@flowralive.in")
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#93c5fd"))
    c.drawCentredString(W/2, H/2 - 75, "14-day Free Trial  |  No Credit Card  |  2-Minute Setup")
    c.setFont("Helvetica", 8)
    c.drawCentredString(W/2, 50, "Tally* is the trademark of its respective owner and is not affiliated with FLOWRA or Jodidar India.")
    c.showPage()

    c.save()
    print(f"Customer Questionnaire: {path}")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    generate_presentation()
    generate_training_booklet()
    generate_social_media_kit()
    generate_customer_questionnaire()
    print("\nAll materials generated!")
    print(f"  1. {OUT_DIR}/FLOWRA_Presentation.pdf")
    print(f"  2. {OUT_DIR}/FLOWRA_Training_Booklet.pdf")
    print(f"  3. {OUT_DIR}/FLOWRA_Social_Media_Kit.pdf")
    print(f"  4. {OUT_DIR}/FLOWRA_Customer_Questionnaire.pdf")
