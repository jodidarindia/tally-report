"""Generate FLOWRA marketing materials: Presentation PDF, Training Booklet, Social Media Kit"""
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
    c.drawRightString(w - 40, 18, "FLOWRA - Tally Prime Analytics")

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
        ("Professional", "2,499/mo", "3 Companies", "5 Users", "CRM + AI Reports"),
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
    draw_title_slide(c, W, H, "FLOWRA", "Unlock the Full Power of Your Tally Data")
    c.showPage()

    # Slide 2: The Problem
    draw_content_slide(c, W, H, "The Problem", [
        "Tally Prime data is locked on your desktop",
        "No mobile access to sales, inventory, or outstanding",
        "Manual Excel exports waste 3-4 hours every week",
        "No real-time visibility for business owners on the move",
        "Multi-branch transfers inflate actual sales figures",
        "No customer payment behavior tracking or CRM",
    ])
    c.showPage()

    # Slide 3: Solution
    draw_content_slide(c, W, H, "FLOWRA: Your Tally Analytics Cloud", [
        "Auto-syncs with Tally Prime in real-time",
        "Access sales, inventory, CRM from any device",
        "Bank-grade 256-bit AES encryption",
        "2-minute setup with Desktop Connector",
        "No data stored on cloud - only analytics",
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
        "Auto-refreshes with latest Tally data",
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
        "Alphabetical customer lists for easy lookup",
        "Monthly/Annual target setting",
    ], DEMO_SS["crm"])
    c.showPage()

    # Slide 7: Inventory
    draw_content_slide(c, W, H, "Inventory Intelligence", [
        "Real-time stock levels from Tally Prime",
        "Low stock and reorder alerts",
        "Movement analysis: Opening > Inward > Sales > Closing",
        "Below-cost sales detection (negative margin)",
        "Sales frequency analysis per item",
        "AI-powered Purchase Order generation",
    ], DEMO_SS["analytics"])
    c.showPage()

    # Slide 8: Security
    draw_content_slide(c, W, H, "Enterprise-Grade Security", [
        "256-bit AES encryption for all company data",
        "UUID-based tenant isolation",
        "JWT authentication with bcrypt password hashing",
        "No raw Tally data stored on cloud servers",
        "SOC2-ready architecture",
        "Role-based access control (Admin, Employee, Super Admin)",
    ])
    c.showPage()

    # Slide 9: Pricing
    draw_pricing_slide(c, W, H)
    c.showPage()

    # Slide 10: CTA
    draw_title_slide(c, W, H, "Start Your Free Trial", "14 days free | No credit card | Cancel anytime")
    c.setFont("Helvetica", 14)
    c.setFillColor(GRAY)
    c.drawCentredString(W/2, H/2 - 90, "support@flowralive.in  |  www.flowralive.in")
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
    c.drawCentredString(W/2, H/2 - 30, "Tally Prime Analytics Platform")
    c.drawCentredString(W/2, H/2 - 55, "www.flowralive.in")
    c.setFont("Helvetica", 10)
    c.drawCentredString(W/2, 60, "CONFIDENTIAL - For Internal Use Only")
    c.showPage()

    # Page 1: What is FLOWRA?
    y = H - 60
    y = heading("1. What is FLOWRA?", y)
    y = body("FLOWRA is a cloud-based analytics platform that connects to Tally Prime\nand gives business owners real-time access to their data from anywhere.\n\nThink of it as a smart dashboard that sits on top of Tally.", y)
    y -= 10
    y = heading("Key Value Proposition", y, 16)
    y = bullet_list([
        "Real-time Tally data on mobile/laptop - anywhere, anytime",
        "Zero manual effort - auto-syncs every few minutes",
        "Bank-grade 256-bit encryption - safer than email",
        "2-minute setup - download connector, login, done",
        "No data migration - Tally remains your source of truth",
    ], y)
    y -= 10
    y = heading("Who is it for?", y, 16)
    y = bullet_list([
        "Distributors and wholesalers using Tally Prime",
        "Business owners who travel and need remote access",
        "Companies with multiple branches/depots",
        "Accountants managing multiple company books",
    ], y)
    new_page()

    # Page 2: Product Features
    y = H - 60
    y = heading("2. Product Features (What You Demo)", y)
    features = [
        ("Dashboard", "Total sales, items, low stock alerts, overdue payments, top customers. Cross-FY totals. Branch toggle to exclude internal transfers."),
        ("Sales", "Sales trend chart, voucher list with drill-down, filter by customer/month/FY. PDF & Excel export."),
        ("CRM", "Customer targets with achievement %, outstanding tracking, follow-up scheduler, payment behavior analysis with credit scoring."),
        ("Inventory", "Real-time stock from Tally, low stock alerts, reorder levels. Search & filter by stock group/category."),
        ("Analytics", "Movement Analysis (Opening/Inward/Sales/Closing), Below Cost Sales detection, Sales Frequency, Customer-Item breakdown."),
        ("AI Reports", "AI-generated business insights. Purchase order recommendations."),
        ("Insider Result", "P&L style business intelligence dashboard."),
        ("Branch Toggle", "One-click filter to exclude branch/depot transfers from all figures. Shows actual customer sales vs internal transfers."),
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
        # Wrap description
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

    # Page 3: How Setup Works
    y = H - 60
    y = heading("3. How Setup Works (Explain to Customer)", y)
    steps = [
        "Step 1: Customer signs up at www.flowralive.in (free 14-day trial)",
        "Step 2: Download Desktop Connector from Setup page",
        "Step 3: Run the connector on the PC where Tally Prime is installed",
        "Step 4: Connector auto-detects Tally and starts syncing",
        "Step 5: Data appears in FLOWRA dashboard within 2 minutes",
        "",
        "Requirements: Tally Prime running on the PC, Internet connection",
        "Port: Tally uses port 9000 by default (configurable)",
        "The connector runs in background - no manual intervention needed",
    ]
    y = bullet_list(steps, y)
    y -= 20
    y = heading("Technical Points (if customer asks)", y, 16)
    y = bullet_list([
        "Data is encrypted with 256-bit AES before transmission",
        "Only analytics data is processed - raw vouchers are not stored",
        "Each company gets a unique encrypted UUID - no data leakage",
        "Multi-company support - one connector handles all Tally companies",
        "Sync happens every 5 minutes automatically",
    ], y)
    new_page()

    # Page 4: Pricing & Plans
    y = H - 60
    y = heading("4. Pricing (Memorize This)", y)
    y -= 5
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(DARK)
    plans = [
        ("Starter", "Rs.999/mo or Rs.9,990/yr", "1 Company, 2 Users", "Dashboard, Sales, Inventory, Basic Analytics"),
        ("Professional", "Rs.2,499/mo or Rs.24,990/yr", "3 Companies, 5 Users", "Everything in Starter + CRM, AI Reports, Advanced Analytics"),
        ("Enterprise", "Rs.3,799/mo or Rs.37,990/yr", "10 Companies, 20 Users", "Everything + Salesman Module, Priority Support"),
    ]
    for name, price, limits, features in plans:
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
        c.drawString(60, y, f"{limits} | {features}")
        y -= 28
    y -= 10
    y = heading("Objection Handling", y, 16)
    objections = [
        '"Too expensive" -> Calculate time saved: 3-4 hrs/week x Rs.500/hr = Rs.8,000/mo saved minimum',
        '"We already use Tally" -> FLOWRA does not replace Tally. It extends it to mobile/remote access',
        '"Is my data safe?" -> 256-bit encryption, same grade as banks. No raw data on cloud',
        '"Can I try before buying?" -> 14-day free trial, no credit card required',
        '"What if Tally is not running?" -> Connector syncs when Tally is open. Last synced data always available',
    ]
    y = bullet_list(objections, y)
    new_page()

    # Page 5: Demo Script
    y = H - 60
    y = heading("5. Demo Call Script (5-Minute Version)", y)
    script = [
        '1. "Let me show you how FLOWRA works with your Tally data..."',
        '2. Open Dashboard - Show total sales, top customers, overdue payments',
        '3. Click Sales - Show voucher list, click a voucher for item details',
        '4. Click CRM > Targets - Show customer achievement tracking',
        '5. Click CRM > Payment Behavior - Show credit scores',
        '6. Click Inventory - Show stock levels, low stock alerts',
        '7. Click Analytics > Movement - Show opening/inward/sales/closing',
        '8. Toggle Branch filter - Show how figures change (actual vs transfers)',
        '9. Click Setup - Show the one-click Desktop Connector download',
        '10. "All of this syncs automatically from your Tally. No manual work."',
    ]
    y = bullet_list(script, y)
    y -= 20
    y = heading("Closing Lines", y, 16)
    y = bullet_list([
        '"Would you like to start a free 14-day trial?"',
        '"I can help you set it up right now - it takes 2 minutes"',
        '"Which plan fits your number of companies and users?"',
    ], y)
    new_page()

    # Page 6: FAQ
    y = H - 60
    y = heading("6. Frequently Asked Questions", y)
    faqs = [
        ("Does FLOWRA work with all versions of Tally?", "FLOWRA works with Tally Prime (latest). Tally ERP 9 is not supported."),
        ("Can I access FLOWRA on my phone?", "Yes! FLOWRA is fully responsive - works on mobile, tablet, and desktop browsers."),
        ("What happens if my internet goes down?", "The Desktop Connector queues data and syncs when internet returns. FLOWRA shows last synced data."),
        ("Can multiple employees use FLOWRA?", "Yes, based on your plan. Starter=2, Professional=5, Enterprise=20 users."),
        ("How is FLOWRA different from Tally on Mobile?", "Tally Mobile is basic data view. FLOWRA provides analytics, CRM, AI reports, movement analysis, and branch filtering."),
        ("Can I manage multiple companies?", "Yes. Professional supports 3 companies, Enterprise supports 10."),
        ("What is the Branch Toggle?", "It filters out inter-branch transfers (depot/division) from sales figures, showing actual customer sales only."),
        ("Is there a mobile app?", "FLOWRA works as a web app on mobile browsers. A dedicated app is on the roadmap."),
        ("What if I cancel?", "You can cancel anytime. Data sync stops but your Tally data is untouched."),
        ("Do you offer custom pricing for large organizations?", "Yes, contact us at support@flowralive.in for enterprise custom plans."),
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

    # Page 7: Quick Reference Card
    y = H - 60
    y = heading("7. Quick Reference Card", y)
    y -= 5
    refs = [
        ("Website", "www.flowralive.in"),
        ("Support Email", "support@flowralive.in"),
        ("Free Trial", "14 days, no credit card"),
        ("Setup Time", "2 minutes"),
        ("Encryption", "256-bit AES (bank-grade)"),
        ("Sync Frequency", "Every 5 minutes (automatic)"),
        ("Tally Compatibility", "Tally Prime (latest version)"),
        ("Plans", "Starter Rs.999 | Pro Rs.2,499 | Enterprise Rs.3,799 per month"),
        ("Annual Discount", "17% off (2 months free)"),
    ]
    for label, val in refs:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DARK)
        c.drawString(60, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.setFillColor(BLUE)
        c.drawString(200, y, val)
        y -= 22
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
    c.showPage()

    # Page 1: Brand Guidelines
    y = H - 60
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(DARK)
    c.drawString(50, y, "Brand Guidelines")
    y -= 40
    guidelines = [
        ("Brand Name", "FLOWRA (always uppercase)"),
        ("Tagline", "Unlock the Full Power of Your Tally Data"),
        ("Primary Color", "#2563EB (Blue)"),
        ("Secondary", "#0f172a (Dark Navy)"),
        ("Accent", "#16a34a (Green for success/CTA)"),
        ("Font", "Clean sans-serif (Helvetica, Inter, or system font)"),
        ("Tone", "Professional, confident, helpful. Speak to business owners."),
        ("Target Audience", "Indian SME distributors/wholesalers using Tally Prime"),
        ("Hashtags", "#FLOWRA #TallyPrime #TallyAnalytics #BusinessIntelligence #IndianSME"),
        ("Website", "www.flowralive.in"),
        ("CTA", "Start your 14-day free trial at www.flowralive.in"),
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

    # Page 2-5: Social Media Posts
    posts = [
        {
            "platform": "LinkedIn / Facebook",
            "title": "Launch Announcement",
            "caption": """Tired of being chained to your office just to check Tally reports?

Introducing FLOWRA - the analytics platform that connects directly to your Tally Prime and gives you real-time business insights on any device.

> Dashboard with total sales, inventory alerts, and overdue payments
> Customer CRM with target tracking and payment behavior
> Movement analysis showing exactly how your stock flows
> Bank-grade 256-bit encryption

Your Tally data, everywhere you go. No manual exports. No Excel sheets.

Start your free 14-day trial: www.flowralive.in

#FLOWRA #TallyPrime #BusinessAnalytics #IndianBusiness #SME #InventoryManagement""",
            "image_desc": "Use: Dashboard screenshot showing Total Sales, Top Customers, and branch toggle"
        },
        {
            "platform": "LinkedIn / Facebook",
            "title": "Problem-Solution Post",
            "caption": """Every distributor knows this pain:

- You're at a client meeting but need to check their outstanding
- Your accountant is on leave and you need today's sales figures
- You suspect dead stock but can't run Tally reports from your phone
- Branch transfers inflate your actual sales numbers

FLOWRA solves all of this.

One Desktop Connector. 2-minute setup. Your entire Tally data on your phone.

With our Branch Toggle, you can instantly separate real customer sales from internal depot transfers.

Try it free for 14 days: www.flowralive.in

#DistributorLife #TallyPrime #FLOWRA #BusinessInsights #DataDriven""",
            "image_desc": "Use: Split image - Inventory page (stock levels) + CRM Targets page"
        },
        {
            "platform": "Instagram / Reels",
            "title": "Feature Highlight Series",
            "caption": """Post 1: Dashboard
"Your entire business in one screen."
Total sales. Top customers. Overdue alerts. Auto-synced from Tally.
www.flowralive.in

Post 2: Branch Toggle
"Are branch transfers inflating your sales?"
One toggle. Real numbers. Instantly.
www.flowralive.in

Post 3: CRM
"Know your customer before they call."
Targets. Outstanding. Payment history. All from Tally.
www.flowralive.in

Post 4: Movement Analysis
"Where is your stock going?"
Opening -> Inward -> Sales -> Closing. Track every unit.
www.flowralive.in

Post 5: Security
"Your Tally data, safer than your email."
256-bit AES encryption. UUID isolation. Zero raw data on cloud.
www.flowralive.in""",
            "image_desc": "Create carousel images from each app screenshot with brand overlay"
        },
        {
            "platform": "Twitter/X",
            "title": "Thread Series",
            "caption": """Tweet 1:
Tally Prime users - your data is trapped on your desktop.

FLOWRA fixes that. Real-time analytics from Tally, on any device.

Thread:

1/ Dashboard: Total sales, items, overdue alerts, top customers. Refreshes every 5 mins.

2/ CRM: Customer targets, payment behavior scores, follow-up scheduling. No more Excel tracking.

3/ Inventory: Real-time stock from Tally. Low stock alerts. Movement analysis with Opening > Inward > Sales > Closing.

4/ Branch Toggle: One click to exclude depot/branch transfers. See your REAL customer sales.

5/ Security: 256-bit AES encryption. Each company isolated with unique UUID. Bank-grade.

6/ Setup: 2 minutes. Download connector, run, done. Free 14-day trial.

www.flowralive.in

#TallyPrime #FLOWRA #Analytics""",
            "image_desc": "Pin Dashboard screenshot as thread header image"
        },
        {
            "platform": "WhatsApp Business Broadcast",
            "title": "Direct Outreach Messages",
            "caption": """Message 1 (Cold):
Hi [Name],

Do you use Tally Prime for your business?

We built FLOWRA - it connects to your Tally and shows real-time sales, inventory, and customer data on your phone.

2-minute setup. 14-day free trial. No risk.

Check it out: www.flowralive.in

---

Message 2 (Follow-up):
Hi [Name],

Quick question - how do you currently check outstanding amounts when you're away from office?

With FLOWRA, you can check any customer's outstanding, sales history, and payment behavior from your phone.

It auto-syncs from Tally. Free to try: www.flowralive.in

---

Message 3 (After Demo):
Hi [Name],

Thanks for checking out FLOWRA! Here's what you get:

> Dashboard with live sales data
> Customer CRM with targets
> Inventory with stock alerts
> Movement analysis
> Branch filter for accurate figures

Start free: www.flowralive.in
Plans from Rs.999/month""",
            "image_desc": "Attach Dashboard and CRM screenshots"
        },
        {
            "platform": "Google My Business / Local SEO",
            "title": "Business Description",
            "caption": """FLOWRA - Tally Prime Analytics Platform

FLOWRA connects to your Tally Prime software and provides real-time business analytics on any device. Access sales reports, inventory levels, customer CRM, and AI-powered insights from your phone or laptop.

Features:
- Real-time dashboard with sales, inventory, and overdue alerts
- Customer CRM with target tracking and payment behavior
- Movement analysis and below-cost sales detection
- Branch/Division filter for multi-location businesses
- 256-bit AES encryption (bank-grade security)

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
        # Render caption with word wrap
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
            # Wrap long lines
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
        ("Week 1: Launch", [
            "Mon: LinkedIn launch post + Dashboard screenshot",
            "Tue: Instagram carousel (5 feature highlights)",
            "Wed: Twitter/X thread (6 tweets)",
            "Thu: WhatsApp broadcast to existing contacts",
            "Fri: Facebook post + video demo link",
        ]),
        ("Week 2: Problem-Solution", [
            "Mon: LinkedIn - 'Distributor pain points' post",
            "Tue: Instagram Reel - 2-min setup walkthrough",
            "Wed: Twitter - Customer testimonial thread",
            "Thu: WhatsApp follow-up to Week 1 contacts",
            "Fri: LinkedIn - Branch Toggle feature deep-dive",
        ]),
        ("Week 3: Social Proof", [
            "Mon: Customer success story post (LinkedIn + FB)",
            "Tue: Instagram - Before/After (Excel vs FLOWRA)",
            "Wed: Twitter - Quick tip about inventory management",
            "Thu: WhatsApp - Free trial reminder",
            "Fri: LinkedIn - Security and encryption post",
        ]),
        ("Week 4: Conversion Push", [
            "Mon: LinkedIn - Pricing comparison post",
            "Tue: Instagram - 'Day in the life with FLOWRA' Reel",
            "Wed: Twitter - FAQ thread",
            "Thu: WhatsApp - Limited time offer (if applicable)",
            "Fri: All platforms - Month summary + CTA",
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
# MAIN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    generate_presentation()
    generate_training_booklet()
    generate_social_media_kit()
    print("\nAll materials generated!")
    print(f"  1. {OUT_DIR}/FLOWRA_Presentation.pdf")
    print(f"  2. {OUT_DIR}/FLOWRA_Training_Booklet.pdf")
    print(f"  3. {OUT_DIR}/FLOWRA_Social_Media_Kit.pdf")
