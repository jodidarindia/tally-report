# Tally Reports - Complete Application Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation Guide (Windows 11)](#installation-guide-windows-11)
4. [App Features & User Guide](#app-features--user-guide)
5. [Tally Connection Setup](#tally-connection-setup)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Tally Reports is a web application that connects to your local Tally Prime database and provides:
- Inventory & Sales Reports
- AI-powered Report Builder (GPT-5.2)
- Customer CRM with Targets & Follow-ups
- Salesman Performance Tracking
- Advanced Analytics (Pivot Tables, Sales Frequency)
- AI Purchase Order Generation

**Architecture:**
```
[Tally Prime on your PC] 
    --> [Desktop Sync Agent (Python script)] 
    --> [Cloud/Local Backend (FastAPI + MongoDB)] 
    --> [Web Frontend (React)]
```

---

## System Requirements

| Component | Requirement |
|-----------|------------|
| OS | Windows 10/11 (64-bit) |
| RAM | 4 GB minimum, 8 GB recommended |
| Disk | 10 GB free space |
| Software | Docker Desktop, Python 3.8+, Git |
| Tally | Tally Prime with ODBC Server enabled |
| Browser | Chrome, Edge, or Firefox (latest) |

---

## Installation Guide (Windows 11)

### Step 1: Install Docker Desktop

1. Open your browser and go to:
   **https://www.docker.com/products/docker-desktop/**

2. Click **"Download for Windows"**

3. Run the installer (`Docker Desktop Installer.exe`)

4. During installation:
   - Check **"Use WSL 2 instead of Hyper-V"** (recommended)
   - Click **Install**

5. **Restart your PC** when prompted

6. After restart, open **Docker Desktop** from Start Menu
   - Wait until you see **"Docker Desktop is running"** (green icon in system tray)
   - This may take 2-3 minutes on first launch

### Step 2: Install Git (if not already installed)

1. Go to: **https://git-scm.com/download/win**
2. Download and install with default settings

### Step 3: Install Python (if not already installed)

1. Go to: **https://www.python.org/downloads/**
2. Download Python 3.11 or later
3. During install: **CHECK "Add Python to PATH"** (important!)

### Step 4: Get the Code

**Option A: From GitHub (if you saved to GitHub)**
Open Command Prompt (Win+R, type `cmd`, press Enter):
```
cd C:\Users\YourName\Desktop
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

**Option B: Download from Emergent**
If you can access the VS Code view in Emergent, you can download files manually.

### Step 5: Get Your Emergent LLM Key

1. On the Emergent platform (where you're chatting with me)
2. Click your **Profile** icon (top-right corner)
3. Go to **"Universal Key"**
4. Click **"Copy Key"**
5. Save this key - you'll need it in the next step

**Note:** If your Universal Key balance is low, go to Profile -> Universal Key -> Add Balance.

### Step 6: Configure the App

In Command Prompt, navigate to your project folder:
```
cd C:\Users\YourName\Desktop\YOUR_REPO
copy .env.example .env
notepad .env
```

In Notepad, update the file:
```
EMERGENT_LLM_KEY=paste_your_key_here
RESEND_API_KEY=
SENDER_EMAIL=onboarding@resend.dev
APP_URL=http://localhost
```

Save (Ctrl+S) and close Notepad.

### Step 7: Deploy the App

**Simply double-click `deploy.bat`** in your project folder.

OR run in Command Prompt:
```
deploy.bat
```

Wait 3-5 minutes for Docker to build and start all services.

When you see:
```
=========================================
  Deployment Complete!
=========================================
  Web App:     http://localhost
  Backend API: http://localhost:8001
=========================================
```

### Step 8: Access the App

1. Open your browser
2. Go to: **http://localhost**
3. You'll see the Login page
4. Enter any email address (e.g., your email)
5. Click **"Send OTP"**
6. Enter OTP: **123456** (development mode)
7. Click **"Verify & Login"**
8. You're in!

**Note on Login:** Since no Resend email API key is configured, the app runs in dev mode with a static OTP `123456`. To enable real email OTP, get a free API key from https://resend.com and add it to your `.env` file.

---

## App Features & User Guide

### 1. Dashboard
**What it shows:**
- Total inventory items and value
- Low stock alerts
- Total sales amount
- Top customers by revenue
- Recent transactions
- **Follow-up Reminders** (overdue in red, today in amber, upcoming)

### 2. Inventory
**What it shows:**
- Complete inventory list from Tally (item name, quantity, rate, value)
- Search and filter inventory
- Export to PDF, Excel, or CSV

**AI Purchase Order:**
- Click the **"AI Purchase Order"** button
- AI analyzes your stock levels and sales patterns
- Generates a prioritized purchase order (Critical/High/Medium/Low priority items)

### 3. Sales
**What it shows:**
- All sales vouchers from Tally
- Date range filter
- Sales analytics charts (monthly trends, top items)

### 4. Customer CRM

**Outstanding Tab:**
- Shows all customers with pending payments
- Aging analysis (0-30, 30-60, 60-90, 90+ days)
- **Export Ledger:** Click XLS or PDF button on any customer row to download their complete transaction ledger

**Follow-ups Tab:**
- Create follow-ups by selecting customer from **dropdown list**
- Set follow-up date, type (Call/Email/Visit/Meeting), and notes
- Mark follow-ups as complete
- Overdue follow-ups highlighted in red with "OVERDUE" badge
- **Reminders appear on Dashboard** based on follow-up dates

**Targets Tab:**
- View all customers with their sales targets and achievement %
- **Set Target:** Click "Set Target" on any customer
  - Enter **Last Financial Year Sales** amount
  - App auto-suggests **15% growth** as target
  - Adjust target as needed, click Save
  - Customers with custom targets show a green "Custom" badge
- **Monthly Sales:** Click "Monthly" button to expand a customer's month-by-month sales chart

**Payment Behavior Tab:**
- Credit scoring per customer
- Payment pattern classification (Excellent/Regular/Irregular/Risky)
- Average payment delay analysis

### 5. Analytics

**Inventory Movement:**
- Classifies items as Fast-moving, Slow-moving, or Dead-stock
- Based on sales velocity vs stock levels

**Below Cost Sales:**
- Identifies items potentially sold below cost price

**Pivot Table:**
- Group inventory data by category
- Select metric (value, quantity, rate)
- Drill down by expanding groups

**Sales Frequency:**
- Shows how often each item is sold
- Unique customer count per item
- **Export:** Click **"Excel"** or **"PDF"** button to download the report
- Date filter for custom range

### 6. AI Reports
- Enter any question in natural language, e.g.:
  - "Show me items with low stock"
  - "Which customers have the highest outstanding?"
  - "Compare monthly sales trends"
- Select report type (General, Inventory, Sales, Customer)
- AI generates a structured report with Summary, Key Insights, Metrics, and Recommendations
- Report history saved for reference

### 7. Salesman Performance

**Performance Tab:**
- Top performer card
- Target vs Achievement bar chart
- Performance table with rank, target, achieved, status

**Item-wise Sales Tab:**
- Click any salesman to expand
- Shows every item they sold: quantity, revenue, transaction count

**Manage Salesmen Tab:**
- **Add Salesman:** Click "Add Salesman" button
  - Enter name, phone, email
  - Set monthly and quarterly targets
  - **Map customers** to the salesman using checkboxes
- Edit or delete existing salesmen

### 8. Tally Setup
- Connection configuration for your Tally Prime instance
- Sync status monitoring

---

## Tally Connection Setup

### Enable Tally ODBC Server

1. Open **Tally Prime**
2. Go to: **Gateway of Tally → F12: Configure → Connectivity**
3. Set these options:
   ```
   Enable ODBC Server: Yes
   Port: 9000
   ```
4. Save and restart Tally

### Run the Desktop Sync Agent

The Desktop Sync Agent is a Python script that runs on your PC (where Tally is installed) and pushes data to the web app.

1. Open Command Prompt:
```
cd C:\Users\YourName\Desktop\YOUR_REPO\desktop-agent
pip install -r requirements.txt
```

2. Edit the sync agent configuration:
```
notepad tally_sync_agent.py
```

3. Update the `CLOUD_API_URL` at the top of the file:
```python
CLOUD_API_URL = "http://localhost:8001"  # For local deployment
```

4. Run the agent:
```
python tally_sync_agent.py
```

The agent will:
- Connect to your local Tally Prime via XML/ODBC
- Fetch inventory, sales vouchers, customer data
- Push it to the web app's database
- Repeat every 10 minutes (configurable)

**Keep this running** in the background while using the app.

### Run Agent on Windows Startup (Optional)

To auto-start the sync agent:
1. Press Win+R, type `shell:startup`, press Enter
2. Create a shortcut to `run_agent.bat` in the desktop-agent folder
3. The agent will now start automatically when you log in

---

## API Reference

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/send-otp` | POST | Send OTP to email. Body: `{"email": "..."}` |
| `/api/auth/verify-otp` | POST | Verify OTP. Body: `{"email": "...", "otp": "..."}` |
| `/api/auth/verify-session` | POST | Check session. Query: `?session_token=...` |
| `/api/auth/logout` | POST | Logout. Query: `?session_token=...` |

### Inventory
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/inventory/items` | GET | List all inventory items |
| `/api/inventory/summary` | GET | Inventory stats |
| `/api/inventory/generate-purchase-order` | POST | AI purchase order |
| `/api/inventory/movement-analysis` | GET | Stock movement |
| `/api/inventory/below-cost-sales` | GET | Below cost items |
| `/api/inventory/pivot-data` | GET | Pivot table data |
| `/api/inventory/sales-frequency` | GET | Sales frequency |

### Sales
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sales/vouchers` | GET | All sales vouchers |
| `/api/sales/summary` | GET | Sales summary |
| `/api/sales/analytics` | GET | Sales chart data |

### CRM
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/customers/outstanding` | GET | Customer outstandings |
| `/api/customers/targets` | GET | Targets with monthly sales |
| `/api/customers/targets/set` | POST | Set target. Body: `{"customer_name", "target_amount", "last_fy_sales"}` |
| `/api/customers/ledger/export` | POST | Export ledger. Body: `{"customer_name", "format": "excel/pdf"}` |
| `/api/customers/followups` | GET | List follow-ups |
| `/api/customers/followups` | POST | Create follow-up |
| `/api/customers/followups/{id}` | PATCH | Update status |
| `/api/customers/payment-behavior` | GET | Payment analysis |
| `/api/dashboard/reminders` | GET | Follow-up reminders |

### Salesman
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/salesman/master` | GET | List all salesmen |
| `/api/salesman/master` | POST | Create/update salesman |
| `/api/salesman/master/{name}` | DELETE | Delete salesman |
| `/api/salesman/performance` | GET | Basic performance |
| `/api/salesman/performance-detailed` | GET | With item-wise breakdown |

### AI & Reports
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai/query` | POST | Simple AI query |
| `/api/ai/advanced-query` | POST | Enhanced AI report |
| `/api/reports/history` | GET | Query history |
| `/api/reports/export` | POST | Export report |

### Analytics Export
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/sales-frequency/export` | POST | Export sales frequency. Body: `{"format": "excel/pdf"}` |

### Sync
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agent/sync` | POST | Push data from desktop agent |
| `/api/sync/status` | GET | Last sync timestamp |

---

## Troubleshooting

### Docker won't start
- Ensure **Virtualization** is enabled in BIOS (usually under CPU settings)
- Ensure **WSL 2** is installed: Open PowerShell as Admin → `wsl --install`
- Restart PC after Docker installation

### App not loading at http://localhost
- Check Docker Desktop — all 3 containers (tally-mongodb, tally-backend, tally-frontend) should be **green/running**
- In Command Prompt: `docker compose logs -f` to see errors
- Wait 2-3 minutes after `deploy.bat` for all services to start

### Tally Sync Agent can't connect
- Ensure Tally Prime is running with ODBC Server enabled on port 9000
- Check firewall isn't blocking port 9000
- In `tally_sync_agent.py`, verify `TALLY_HOST = "localhost"` and `TALLY_PORT = 9000`

### AI features not working
- Ensure `EMERGENT_LLM_KEY` is set in `.env` file
- If key balance is low: Emergent Profile → Universal Key → Add Balance
- AI queries take 10-20 seconds to generate — wait for the response

### OTP not received by email
- By default, app runs in **dev mode** — use OTP `123456`
- For real emails: Get a free API key from https://resend.com → add to `.env` as `RESEND_API_KEY`

### Data not showing after Tally sync
- Click **"Sync Now"** button on Dashboard
- Check the Desktop Sync Agent terminal for errors
- Verify the sync agent's `CLOUD_API_URL` points to `http://localhost:8001`

### How to stop the app
```
docker compose down
```

### How to update the app
```
git pull
docker compose up -d --build
```

### How to backup data
```
docker exec tally-mongodb mongodump --out /data/backup
docker cp tally-mongodb:/data/backup ./my_backup
```

---

## File Structure

```
project/
├── .env.example          # Environment template
├── docker-compose.yml    # Docker orchestration
├── deploy.sh             # Linux/Mac deploy script
├── deploy.bat            # Windows deploy script
├── SELF_HOSTING_GUIDE.md # Quick hosting guide
├── backend/
│   ├── Dockerfile
│   ├── server.py          # Main API server
│   ├── models.py          # Data models
│   ├── requirements.txt
│   └── services/
│       ├── ai_service.py           # AI report builder
│       ├── enhanced_ai_service.py  # Advanced AI reports
│       ├── purchase_order_ai.py    # AI purchase orders
│       ├── auth_service.py         # OTP authentication
│       ├── export_service.py       # PDF/Excel export
│       └── tally_client.py         # Tally data connector
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── App.js
│       └── pages/
│           ├── Dashboard.js
│           ├── Inventory.js
│           ├── Sales.js
│           ├── CustomerCRM.js
│           ├── InventoryAnalytics.js
│           ├── SalesmanPerformance.js
│           ├── EnhancedAIReports.js
│           ├── ReportHistory.js
│           ├── Login.js
│           └── TallySetup.js
└── desktop-agent/
    ├── tally_sync_agent.py  # Tally-to-cloud sync
    ├── run_agent.bat        # Windows launcher
    ├── requirements.txt
    └── QUICK_START.txt
```

---

## Support

For issues with the Emergent platform or LLM key, contact Emergent support through the platform.

For Tally-specific issues (ODBC connection, data format), refer to Tally Prime documentation or support.
