# FLOWRA — Complete Application Documentation

> **What is this document?**
> A single, plain-English reference that explains *everything* about FLOWRA — what
> it does, how it works, where your data lives, how the Tally and Busy agents
> talk to the cloud, and how each screen is meant to be used. Written so a
> business owner, accountant, salesman, or first-day employee can read it cover
> to cover without a technical background.
>
> **Last updated:** February 2026 · **App version:** FY 2026-27 release
> **For:** end-users, accountants, sales managers, admins, and partners.

---

## Table of contents

1. [What is FLOWRA?](#1-what-is-flowra)
2. [Who is it for?](#2-who-is-it-for)
3. [The big picture — how the pieces fit together](#3-the-big-picture)
4. [How data flows from Tally / Busy → your dashboard](#4-data-flow)
5. [User roles & what each role can see](#5-user-roles)
6. [The modules, one by one](#6-modules)
    - 6.1 [Dashboard](#61-dashboard)
    - 6.2 [Sales](#62-sales)
    - 6.3 [CRM (Customers)](#63-crm-customers)
    - 6.4 [Inventory](#64-inventory)
    - 6.5 [Inventory Analytics](#65-inventory-analytics)
    - 6.6 [Salesman](#66-salesman)
    - 6.7 [Salesman Order App (mobile-first)](#67-salesman-order-app)
    - 6.8 [AI Reports & AI Query Builder](#68-ai-reports)
    - 6.9 [Insider Result (deep analytics)](#69-insider-result)
    - 6.10 [CA Corner](#610-ca-corner)
    - 6.11 [Dispatch Terminal](#611-dispatch-terminal)
    - 6.12 [Sync History](#612-sync-history)
    - 6.13 [Setup / Settings](#613-setup-settings)
    - 6.14 [Refer & Earn](#614-refer-and-earn)
    - 6.15 [SuperAdmin Command Center](#615-superadmin)
7. [The Tally Sync Agent — what it is and how to run it](#7-tally-agent)
8. [The Busy Sync Agent — what it is and how to run it](#8-busy-agent)
9. [Background jobs, schedules and triggers](#9-jobs-triggers)
10. [AI features and the Universal LLM Key](#10-ai-features)
11. [Where your data lives (collections in plain English)](#11-data-model)
12. [Security, privacy and the "no data on cloud" claim](#12-security)
13. [Plans, subscriptions, and the demo account](#13-plans)
14. [Recent changes (changelog)](#14-changelog)
15. [Troubleshooting — common situations](#15-troubleshooting)
16. [Glossary](#16-glossary)

---

<a id="1-what-is-flowra"></a>
## 1. What is FLOWRA?

FLOWRA is a **web application built on top of Tally Prime and Busy Accounting
Software**. It does not replace your accounting software — it *unlocks* the data
already sitting inside it.

If you run your books in Tally or Busy, you already have a goldmine of
information: sales, purchases, stock, customers, receipts, GST. The problem is
that getting that data out — for daily reporting, sales follow-ups, dispatch,
salesman tracking, or showing it to your CA — is painful and manual.

FLOWRA solves that by:

1. Running a small **Desktop Agent** on the Windows machine where Tally or Busy
   lives.
2. The agent **reads** vouchers, masters, ledgers and stock — and uploads only
   the structured rows (no PDFs, no Tally backup files) to your private
   FLOWRA cloud space.
3. You and your team open a **web app** in any browser, log in, pick the
   company, and see live reports, dashboards, analytics and tools.

The phrase you'll see on the marketing site — *"No Data on Cloud\*"* — is
explained in [Security](#12-security). Short version: business names and
sensitive identifiers are encrypted at rest, only authenticated users in your
tenant can ever query them, and you can wipe everything with a single
"Disconnect" toggle.

### Three things FLOWRA gives you that your accounting software doesn't

| | Plain Tally / Busy | With FLOWRA on top |
|---|---|---|
| **Live dashboards** | One PC, one user at a time | Whole team, any device, in real time |
| **Beyond accounting** | Vouchers and ledgers only | Dispatch board, salesman mobile app, CRM follow-ups, AI insights, CA reports |
| **Sharable answers** | "Send me the screenshot" | "Open the dashboard" |

---

<a id="2-who-is-it-for"></a>
## 2. Who is it for?

FLOWRA is built for **Indian SMEs** running on Tally Prime or Busy 18+. The
sweet spot is:

- ₹2 Cr – ₹50 Cr annual turnover
- 1–5 GSTINs / companies
- 1–25 employees who need access to numbers (sales, dispatch, accounts)
- A field salesman team of 2–20 people taking orders on the road
- A CA / accountant who wants clean P&L, Balance Sheet, cash flow

Five real-world users you'll find in every customer:

| Role | Daily question they need answered |
|---|---|
| **Owner / Director** | *"How are we doing today vs last month?"* |
| **Sales Manager** | *"Who is buying less than usual? Which customer is overdue?"* |
| **Salesman in field** | *"What did this customer buy last 10 months? What should I cross-sell?"* |
| **Dispatch in-charge** | *"Which invoices are ready to pack? Who has paid the porter?"* |
| **CA / Accountant** | *"Show me P&L, Balance Sheet, and a breakup of expenses for review."* |

Each of those questions has a dedicated FLOWRA module — see [§6](#6-modules).

---

<a id="3-the-big-picture"></a>
## 3. The big picture — how the pieces fit together

```
   ┌─────────────────────┐         ┌─────────────────────────┐
   │  Tally Prime (PC)   │         │  Busy Accounting (PC)   │
   │  Or:                │         │  Or both at the same    │
   │  Browser-based ERP  │         │  time across companies  │
   └──────────┬──────────┘         └────────────┬────────────┘
              │                                  │
              │  reads vouchers, items,          │
              │  customers, ledgers, P&L         │
              ▼                                  ▼
   ┌───────────────────────────────────────────────────────┐
   │   FLOWRA Desktop Agent  (small Python program)        │
   │   • Tally Agent v9.8.9   (talks to Tally over ODBC/XML)│
   │   • Busy Agent v1.0      (reads Busy .bds via ODBC)    │
   │                                                       │
   │   Runs every 5 min (quick sales) and 20 min (full).   │
   │   Sends only structured rows — never your Tally       │
   │   backup file — over HTTPS.                           │
   └───────────────────────┬───────────────────────────────┘
                           │  HTTPS + JWT token
                           ▼
   ┌───────────────────────────────────────────────────────┐
   │   FLOWRA Cloud Backend  (FastAPI + MongoDB)           │
   │   • Stores rows under your tenant_id + company_id     │
   │   • Encrypts sensitive names with Fernet              │
   │   • Serves the web app, mobile salesman app, CA panel │
   │   • Sends AI requests via Universal LLM Key           │
   └───────────────────────┬───────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
   ┌─────────┐       ┌──────────────┐   ┌────────────────┐
   │  Web    │       │  Salesman    │   │  Dispatch      │
   │ browser │       │  mobile app  │   │  terminal /    │
   │ (any    │       │  (PWA)       │   │  warehouse UI  │
   │  user)  │       │              │   │                │
   └─────────┘       └──────────────┘   └────────────────┘
```

### Two simple rules to remember
1. **The agent only reads — never writes — back into Tally/Busy.**
   Your accounting software stays the source of truth.
2. **Everything is scoped by `tenant_id` + `company_id`.**
   That is FLOWRA's data wall: salesman A on company X can never see company Y,
   even by accident.

---

<a id="4-data-flow"></a>
## 4. How data flows from Tally / Busy → your dashboard

Here is what actually happens between "I made a sale in Tally" and "It shows on
my phone".

### Step 1 — You record a voucher in Tally / Busy

A Sales voucher (or Receipt, Credit Note, Journal, Purchase, Debit Note, Contra,
Stock Journal) is saved in Tally Prime or Busy as you would normally.

### Step 2 — The Desktop Agent picks it up

The agent is a small program running on the same PC. It wakes up on a schedule:

- **Every 5 minutes** → quick sales sync (only new Sales + Receipts of today)
- **Every 20 minutes** → full sync (all voucher types + masters + ledgers)
- You can also click **"Sync Now"** in the agent window any time.

The agent uses each ERP's native protocol:

- **Tally:** XML over ODBC port 9000 (configured in Tally Gateway → F1 → ODBC)
- **Busy:** Microsoft Access ODBC against the active financial-year `.bds` file

### Step 3 — Data is shipped to FLOWRA over HTTPS

The agent:
1. Authenticates with your FLOWRA login (the same email/password the office team
   uses to open the web app).
2. Gets back a JWT (a temporary key valid 24 hours).
3. Sends structured JSON rows in chunks of 500 to the backend's `/api/sync/*`
   endpoints.

Every row carries:
- `tenant_id` (your business — assigned at signup)
- `company_id` (specific GSTIN / company inside your business)
- `voucher_date`, `party_name`, `items[]`, `ledger_entries[]`, etc.

No screenshots, no PDFs, no Tally backup file is ever transmitted.

### Step 4 — Deletion reconciliation

After each sync the agent also sends a **manifest** — the list of voucher IDs it
just saw in Tally/Busy. The backend compares this to what it already has and
**deletes any rows that are no longer in your ERP**. That is how FLOWRA fixes
the classic "I deleted this invoice but it still shows up" problem.

### Step 5 — The web app shows it

The web app polls and listens via WebSocket. The moment a sync finishes, a toast
notification appears ("Sales: 23 items synced") and the dashboard refreshes.

### Step 6 — Background jobs work on the data

After ingestion, FLOWRA's backend computes derived numbers in the background:
overdue digests, sales forecasts, salesman targets, recommendations. See
[§9 Background jobs](#9-jobs-triggers).

---

<a id="5-user-roles"></a>
## 5. User roles & what each role can see

When the **admin** of an account adds a teammate (Setup → Manage Employees),
they pick a role. The role decides which left-menu tabs that person sees the
moment they log in.

| Role | What they see / can do |
|---|---|
| `admin` | Everything — all 12 feature tabs of their tenant, all companies |
| `employee` | A subset of admin's features (chosen by admin per employee) |
| `salesman` | Mobile-first **Salesman Order App** only (no dashboard) |
| `dispatch` | **Dispatch Terminal** only — pick / pack / dispatch / hold |
| `flowra_staff` | FLOWRA's internal staff with limited SuperAdmin tabs |
| `super_admin` | FLOWRA founders / control-panel — sees every tenant |

**Important:** an admin can also be a salesman (in some shops the owner *is* the
sales lead). Salesman role for that admin is set via Setup → Manage Salesmen.

---

<a id="6-modules"></a>
## 6. The modules, one by one

This is the meat of the document. For every module the doc covers:

- **What it does (plain English)**
- **Who uses it**
- **Key screens or buttons**
- **Where the data comes from**

<a id="61-dashboard"></a>
### 6.1 Dashboard

**Plain English:** the daily front-page of the business.

**Used by:** owner, manager, accountant.

**What you see:**

- **Total Sales** for the selected financial year (₹ figure, voucher count).
- **Inventory Items** (how many SKUs you stock and total stock value).
- **Low Stock** count (items below their reorder level).
- **FY Sales Value** card for the active FY chosen in the top-bar FY picker.
- **Overdue Payments** card — invoices older than your "overdue threshold"
  setting (default 55 days), with one-click drill-down.
- **Recent Transactions** (last 10 sales).
- **Top Customers** for the FY by revenue.
- Quick links to "Refresh now" or toggle Auto-refresh.

**Data source:**
`sales_vouchers`, `inventory_items`, `customers`, `dashboard/overdue-digest`.

**Tip:** flip the **FY dropdown** in the top bar to instantly recalculate
everything for FY 2025-26, 2024-25, etc. FLOWRA stores 6 years of FY data.

<a id="62-sales"></a>
### 6.2 Sales

**Plain English:** every invoice your business has raised, searchable.

**Used by:** owner, accountant, sales manager.

**Key views:**

- **Voucher list** — filter by date, party, salesman, voucher type
  (Sales / Sales General / branch-specific sub-types).
- **Voucher detail** — opens the invoice with all line items, ledger entries
  (CGST, SGST, freight, round-off), and the salesman's tagged name.
- **Customer-Item Sales** — pivot of what each customer bought across months
  (the classic "what does this customer always order?" question).
- **Sales summary** — month-on-month chart + top-customer leaderboard.
- **CSV / Excel export** for any of the above.

**Data source:** `sales_vouchers` + `credit_notes` for returns.

<a id="63-crm-customers"></a>
### 6.3 CRM (Customers)

**Plain English:** the address book + collection workbench.

**Used by:** sales manager, accounts team.

**Key features:**

- **All customers** with city, phone, opening balance, transaction count, total
  purchases, outstanding amount.
- **Outstanding ageing** — 0-30 / 31-60 / 61-90 / 90+ buckets.
- **Follow-ups** — set a reminder ("call Patel Motor Works on 15th about
  overdue 50K") and the dashboard rings on the day.
- **Payment Behaviour** score per customer — pays-on-time, slow-payer, chronic.
- **Customer Targets** — set a quarterly target per customer and track variance.
- **Concentration risk** — see what % of your revenue depends on the top 5 or
  top 10 customers (under Insider Result, see §6.9).

**Data source:** `customers`, `sales_vouchers`, `receipt_vouchers`,
`customer_followups`, `customer_targets`.

<a id="64-inventory"></a>
### 6.4 Inventory

**Plain English:** stock list with values and reorder alerts.

**Used by:** purchase officer, store keeper.

**Key features:**

- All SKUs with current quantity, unit, last sale price, purchase price,
  standard price (the rate Tally / Busy treats as "default"), and stock group.
- **ABC categorisation** (A / B / C / D) — automatically by velocity × value.
- **Reorder level** — editable per item, defaults to 25 % of opening qty.
- **Below-cost sales** — finds invoices where you sold a SKU under its
  purchase rate. Great for spotting pricing leaks.
- **Auto Reorder Suggestions** — AI looks at last 90-day movement and tells
  you what to reorder and how much.

**Data source:** `inventory_items`, `sales_vouchers`, `purchase_vouchers`.

<a id="65-inventory-analytics"></a>
### 6.5 Inventory Analytics

**Plain English:** the *"why is this SKU not moving"* tab.

**Used by:** category manager, owner.

**Six views inside one screen:**

1. **Pareto / ABC chart** — 80/20 of your revenue by SKU.
2. **Category Sales** — drill into a stock group and see what's hot.
3. **Sales Frequency** — every SKU's number of sale events per month with
   "Dead / Slow / Steady / Fast" tags.
4. **Movement Analysis** — opening qty + purchases − sales = closing qty (and
   highlights variance vs Tally).
5. **Pivot Table** — month × SKU × quantity grid you can export.
6. **Below-cost Sales** report (already mentioned above).

All views have CSV export.

<a id="66-salesman"></a>
### 6.6 Salesman

**Plain English:** the leaderboard + customer ownership for your field team.

**Used by:** sales head, owner.

**Key features:**

- **Salesman Master** — list of all salesmen with monthly + quarterly target,
  contact, mapped customers.
- **Performance dashboard** — % of target, growth vs last month, last-visited
  customer.
- **Customer ownership map** — which salesman "owns" which customer (used by
  the mobile order app and for commission calc).
- **Beat plans** — geo-cluster customers into a daily route, mark check-ins.
- **Export** the whole salesman performance table for monthly review.

**Data source:** `salesman_master`, `sales_vouchers` (using the
`salesman` field stamped by Tally / Busy or by salesman order app),
`salesman_beats`, `beat_runs`.

<a id="67-salesman-order-app"></a>
### 6.7 Salesman Order App (mobile-first)

**Plain English:** WhatsApp-fast order taking for the salesman in the field.

**Used by:** salesman role only (the user logs in on phone).

**What the salesman sees:**

- **My Customers** — only customers mapped to them. Search and tap.
- **New Order** — pick items, qty, rate, save as Draft / Pending Approval.
- **Repeat last order** — one tap re-creates the previous order.
- **Customer purchase history** — last 10 months of purchases for a customer,
  so they can confidently recommend ("you usually take 5L pack, want 6 this
  time?").
- **Cross-sell suggestions** — AI-driven "related items" using velocity +
  affinity (items A and B bought together often).
- **Beat run today** — check-in / check-out at each customer's location.
- **Pending billing** — orders the admin marked "approved" but not yet billed
  in Tally.
- **My Stats** — own monthly target, achievement %, growth %.

**Admin side** (under the regular FLOWRA web app):
Sales → *Salesman Orders* tab shows all incoming orders. Admin approves /
rejects / holds them, and the dispatch terminal billing step closes the loop.

<a id="68-ai-reports"></a>
### 6.8 AI Reports & AI Query Builder

**Plain English:** *"Type your question, get the answer."*

**Used by:** owner, sales head, accountant.

**Two surfaces:**

1. **Enhanced AI Reports** — pre-built one-click reports:
   - "Top 10 slow-moving SKUs this quarter"
   - "Customers with falling order frequency"
   - "GST input vs output mismatch"
   - "Sales forecast for next month"
2. **AI Query Builder** — open chat box. Ask in English or Hindi:
   *"Mujhe pichle 3 mahine ke top 5 customers chahiye jinka order kam ho gaya
   hai."* GPT-5.2 reads the question, picks the right data, returns a chart +
   table. The answer is saved in `ai_queries` so you can re-open it later.

**Powered by:** Universal LLM Key (Emergent-managed) calling GPT-5.2 for text.
See [§10](#10-ai-features).

<a id="69-insider-result"></a>
### 6.9 Insider Result (deep analytics)

**Plain English:** the *"what is really going on"* tab for owners.

**Used by:** owner only (sensitive numbers).

**Sections:**

- **Customer Lifecycle** — for every customer: first-bought-date, days-since-last-purchase, repeat frequency, churn risk score.
- **Concentration Risk** — % of revenue coming from top 1 / top 5 / top 10
  customers. Red flag if any single customer crosses 25 %.
- **SPIP Analysis** — Sales-Per-Inventory-Position. Are you sitting on stock
  that nobody is buying?
- **Sales Forecast** — next 3 months projected using a simple ARIMA-style
  model (no AI required).

<a id="610-ca-corner"></a>
### 6.10 CA Corner

**Plain English:** what you'd hand to your Chartered Accountant.

**Used by:** the CA (read-only sub-user is supported), the in-house accountant.

**Reports:**

- **Profit & Loss** — annual P&L with income / expense / direct expense /
  indirect expense rollup, exactly the way Tally / Busy compute it.
- **Cash Flow** — Tally indirect method: Operating, Investing, Financing.
- **Balance Sheet** *(new April 2026)* — Assets vs Liabilities & Capital,
  grouped by parent group, expandable to the ledger.
- **Ledger Drill-Down** *(new April 2026)* — Income/Expense toggle, parent
  group bars, % share.
- **AI Expense Insights** — GPT highlights where you can save: "Freight inward
  is up 18 % in 3 months — investigate the new transporter."

**Data source:** `all_ledgers`, `bank_cash_ledgers`, `profit_loss`,
`contra_vouchers`, `journal_vouchers`, `purchase_vouchers`, `receipt_vouchers`,
`stock_journals`.

<a id="611-dispatch-terminal"></a>
### 6.11 Dispatch Terminal

**Plain English:** the warehouse Kanban board.

**Used by:** dispatch role + admin.

**Daily flow:**

1. New invoice from Tally lands → appears as a card in the **"New"** column.
2. Warehouse moves it: **Queued → Processing → Packed → Dispatched → Info
   Shared.**
3. Each move stamps `status_history` (who changed it, when).
4. Additional cards can be created **without an invoice** for "online orders"
   or pre-billing pickups.
5. **Hold** column to flag a card with a reason ("waiting on payment").
6. **Settlements:** porter and transporter payments tracked per LR. Close-of-Day
   PDF generated and emailed.
7. **Document uploads** per card — picture of the loaded truck, LR copy,
   E-way bill PDF.
8. **Pending billing** column shows salesman orders ready for invoicing.

**Data source:** `dispatch_cards`, `dispatch_porters`, `dispatch_transporters`,
`dispatch_porter_payments`, `dispatch_transporter_payments`, `dispatch_settings`.

<a id="612-sync-history"></a>
### 6.12 Sync History

**Plain English:** the agent's running diary.

Every sync writes a row: when it started, when it finished, how many vouchers /
items / customers came in, whether it failed and why. This is the first place to
look when someone says "today's sale isn't showing yet". Sort by company, see
the latest agent version (`v9.8.9` for Tally, `v1.0` for Busy).

<a id="613-setup-settings"></a>
### 6.13 Setup / Settings

**Plain English:** everything an admin configures once and forgets about.

**Sub-tabs:**

- **Manage Employees** — add/edit/disable employees, pick which feature tabs
  they see, reset password.
- **Manage Salesmen** — salesman master, map customers, set targets.
- **Tally Connection** — download the agent zip, copy the sync token, see
  "Last sync 2 min ago".
- **Company Setup** — add additional companies (up to your plan's
  `max_companies` limit).
- **Overdue Threshold** — change the default 55-day overdue cutoff per
  business.
- **Tenant Settings** — creditor groups, expense groups, dispatch defaults.
- **Dispatch Settings** — porter rates, default transporter, packaging types.
- **Audit Log** — every meaningful action on this tenant (login, password
  changes, employee created, prospect converted, etc.).
- **Data Export** — owner can download a full ZIP of every row this tenant
  holds — vouchers, masters, ledgers — in CSV/JSON.
- **Disconnect / Wipe Tenant** — a single-button kill switch (see
  [Security §12](#12-security)).

<a id="614-refer-and-earn"></a>
### 6.14 Refer & Earn

A built-in referral programme. Every admin gets a **referral code** they can
share. When a new tenant subscribes using that code, FLOWRA credits the
referrer with commission, visible in **My Dashboard**. SuperAdmin sees the
master ledger and pays out monthly.

<a id="615-superadmin"></a>
### 6.15 SuperAdmin Command Center

Internal-only screen for FLOWRA's founders + staff. Nine modular tabs:

1. **Overview** — MRR, ARR, active tenants, churn.
2. **Subscriptions** — every paying customer, plan, renewal date, manual
   extend / pause.
3. **Payments** — incoming payments and Stripe/manual reconciliation.
4. **Invoices** — FLOWRA's own invoicing for tenants.
5. **Prospects** — leads pipeline.
6. **Health** — agent uptime, last sync per company, error rate.
7. **Admins** — view-only list of tenants and their admins.
8. **Renewals** — renewal requests, send reminder emails.
9. **Referrals** — referral leaderboards and payouts.
10. **Questionnaires** — onboarding feedback.
11. **Backups** — download per-tenant MongoDB backup zips.
12. **Activity** — global audit log across all tenants.
13. **Staff** — give FLOWRA team members `flowra_staff` role with
    fine-grained tab access.

---

<a id="7-tally-agent"></a>
## 7. The Tally Sync Agent — what it is and how to run it

### 7.1 What it is, in one line

A Python program (`tally_sync_agent_v9.py`) you run on the same Windows PC
where Tally Prime is open. It reads vouchers and masters from Tally and uploads
them to your private FLOWRA cloud.

### 7.2 What it fetches (current v9.8.9 capabilities)

| Tally data | Sync frequency |
|---|---|
| Sales vouchers (all sub-types) | Every 5 min (quick) + 20 min (full) |
| Receipt vouchers | Every 5 min (quick) + 20 min (full) |
| Credit Notes | Every 20 min |
| Purchase vouchers (goods + expense) | Every 20 min |
| Debit Notes | Every 20 min |
| Journal vouchers | Every 20 min |
| Contra vouchers (bank-to-bank) | Every 20 min |
| Stock journals (transfers, mfg) | Every 20 min |
| Customers (party masters under Sundry Debtors) | Every 20 min |
| Sundry Creditors | Every 20 min |
| Inventory masters (stock items + groups) | Every 20 min |
| Bank & Cash ledger balances | Every 20 min |
| All ledgers (for P&L / Balance Sheet) | Every 20 min |
| Profit & Loss group balances | Every 20 min |

### 7.3 How the user actually runs it (Windows GUI Build Kit)

We ship a **Windows Build Kit** at
`/app/desktop-agent/build-kit/`. Inside:

- `flowra_gui.py` — a small Tkinter window (Start / Stop / View Logs).
- `tally_sync_agent_v9.py` — the engine.
- `agent.spec` + `build.bat` — PyInstaller recipe to produce a single `.exe`.
- `requirements.txt` — pinned dependencies.

On the customer's Windows PC, the one-time install is:

```cmd
# 1. Install Python 3.10+ from python.org (check "Add to PATH")
# 2. Unzip the build kit somewhere like C:\FLOWRA-Agent
# 3. Double-click build.bat — produces FLOWRA-Agent.exe
# 4. Double-click FLOWRA-Agent.exe — a small window appears.
```

In the window:

1. Type the FLOWRA login email + password (same as the web app).
2. Click **Connect to Tally** — the agent runs a one-time diagnostic against
   Tally ODBC port 9000.
3. Pick the **starting financial year** (e.g. 2024-25) — first sync will go
   back to 1 April of that year.
4. Click **Start**. The agent now:
   - Sits in the system tray (right-click for Pause / Resume / Quit).
   - Optionally launches at Windows startup (toggle in Settings).
   - Logs to `tally_sync_agent.log` next to the exe.

### 7.4 What Tally needs configured

Inside Tally Prime, on the same PC:

1. Open the company you want to sync.
2. Press **F1 → Settings → Connectivity → ODBC Server**.
3. Set **Enable ODBC Server: Yes**.
4. Port: **9000** (default; the agent expects this).
5. Save and keep Tally open while syncing.

### 7.5 What changed in v9.8.9

- **DayBook fallback for "Last Voucher Date"** — when Tally's
  `$$LastVoucherDate` TDL function returns empty (common with older
  builds), the agent falls back to a 730-day Day-Book scan to find the
  most recent voucher date.
- Cleaner debug logs — separate messages for "TDL returned empty" vs
  "Day-Book scan failed", so users can tell *why* the agent decided to
  "default to today".

### 7.6 Encrypted local config

The agent encrypts your `tenant_id`, `company_id`, and auth token to disk using
Fernet (AES-128) with a per-machine key. If the laptop is stolen, the file
alone cannot be used to log in.

### 7.7 Deletion reconciliation (Option B)

After each sync the agent posts a manifest of voucher IDs to
`/api/sync/reconcile/{type}`. The backend deletes any row whose ID is not in
the manifest, scoped to `tenant_id + company_id + financial_year`. Net result:
when a voucher is deleted inside Tally, it disappears from FLOWRA at the next
sync. No more ghost data.

---

<a id="8-busy-agent"></a>
## 8. The Busy Sync Agent — what it is and how to run it

### 8.1 What it is, in one line

A Python program (`flowra_busy_agent_v1.py`) that reads Busy Accounting
Software's `.bds` (Microsoft Access) databases over ODBC and uploads structured
rows to FLOWRA.

### 8.2 What it fetches (v1.0)

| Busy data | Notes |
|---|---|
| Sales vouchers | All types (Tax Invoice, Bill of Supply, etc.) |
| Receipts | With bill-allocation breakdown |
| Credit Notes | Returns + rate-difference notes |
| Journals | Adjustment entries |
| Purchase vouchers | Goods + expense |
| Debit Notes | |
| Contra | Bank ↔ Bank, Cash ↔ Bank |
| Stock journals | Transfers + manufacturing |
| Customers / Sundry Debtors masters | |
| Creditors masters | |
| Inventory items + groups | |
| All ledgers, account groups | For P&L computation |
| P&L (computed from ledger groups) | |

### 8.3 How the user actually runs it

Build kit lives at `/app/busy-agent-build/`:

- `src/flowra_busy_agent_v1.py` — engine.
- `flowra-busy-agent.spec` — PyInstaller recipe.
- `build.bat` — produces `FLOWRA_Busy_Agent.exe`.
- `installer.iss` — Inno Setup script for a full Windows installer with Start
  Menu shortcut + auto-update path.

Inside the GUI:

1. **Login** with FLOWRA email + password.
2. **Pick Busy data folder** — the agent auto-detects the active `.bds`
   filename (e.g. `db2526.bds`).
3. **Pick starting FY** — same as Tally, FY 2024-25 backfill is the typical
   default for prospect demos.
4. **Start** — same dual-schedule (5-min quick + 20-min full), same tray
   support, same encrypted config, same deletion reconciliation.

### 8.4 What Busy needs configured

Busy ships with ODBC built-in. The only requirement:

- Install **Microsoft Access Database Engine 2016 Redistributable (64-bit)** on
  the same PC (free download from Microsoft).
- Make sure the user running the agent has read access to the Busy data folder
  (`C:\BusyWin\Data` is the default).

### 8.5 Difference vs the Tally agent (today)

| | Tally Agent v9.8.9 | Busy Agent v1.0 |
|---|---|---|
| Transport | XML over ODBC port 9000 | Microsoft Access ODBC against `.bds` |
| `standard_price` per item | Yes (from STANDARDPRICE) | **Planned** in v1.1 parity update |
| Per-line DR/CR direction | Yes (Dr/Cr explicit) | **Planned** in v1.1 parity update |
| GUI build kit | Tkinter + tray + auto-start ✓ | Tkinter + tray + auto-start ✓ |
| Deletion reconciliation | ✓ | ✓ |
| Encrypted local config | ✓ | ✓ |

The two pending parity items above are on the [§14 roadmap](#14-changelog).

---

<a id="9-jobs-triggers"></a>
## 9. Background jobs, schedules and triggers

FLOWRA quietly does work in the background. Here is the full list — in plain
English — so nothing feels like a "black box".

### 9.1 Sync schedules (run on the customer's PC)

| Job | Where it runs | How often |
|---|---|---|
| **Quick sales sync** (Sales + Receipts only) | Desktop Agent | Every **5 minutes** |
| **Full sync** (everything else) | Desktop Agent | Every **20 minutes** |
| **Agent command poll** (admin clicks "Re-sync this month" in the web app, agent picks it up) | Desktop Agent | Every **30 seconds** |
| **Sync history heartbeat** | Desktop Agent | At the end of each sync |

### 9.2 Cloud-side background jobs

| Job | What it does | Trigger |
|---|---|---|
| **Deletion reconciliation** | Removes rows that Tally / Busy no longer has | After every sync manifest is posted |
| **Subscription expiry email** | Warns admin 30 / 14 / 7 / 1 days before expiry | Daily, at admin's first login of the day |
| **Overdue digest** | Re-computes overdue invoices per ageing bucket | After every receipt voucher sync |
| **Salesman target rollup** | Recalculates achievement % per salesman | After every sales voucher sync |
| **Customer payment behaviour score** | Recomputes pays-on-time / slow / chronic per customer | Daily |
| **AI Expense Insights** | GPT call to summarise expense ledgers | Triggered by user clicking "Generate Insights" in CA Corner |
| **Salesman cross-sell affinity** | Pre-computes "customers who bought A also bought B" velocity table | After every sales voucher sync (planned for background-job migration) |
| **Audit log** | Writes every login / mutation / failed login | Real-time, on every relevant endpoint |
| **WebSocket fan-out** | Pushes "sync_started", "data_synced", "sync_complete" to the open browsers | Real-time |

### 9.3 Email triggers

| Email | When |
|---|---|
| Subscription started | Right after first payment / signup |
| Subscription renewed | After successful renewal |
| Subscription expiry warning | 30/14/7/1 days before expiry (at most once a day) |
| Employee created (to employee) | When admin creates an employee, with first-time password |
| Employee created (to admin) | Confirmation copy |
| Renewal requested | When admin clicks "Request Renewal" |
| Referral commission credited | When a referred customer pays |

(All email triggers can be muted per-tenant from Setup → Tenant Settings.)

### 9.4 Manual one-click triggers from the web app

- **Refresh Now** — re-fetches dashboard cards.
- **Resync This Month** — pushes a command to the Desktop Agent to re-fetch
  the current month's vouchers (used to fix a missing voucher).
- **Delete Company Data** — wipes one company in your tenant (kept for the
  case where the admin connects a wrong Tally company by mistake).
- **Disconnect Tenant** — kill-switch; wipes everything for this tenant.

---

<a id="10-ai-features"></a>
## 10. AI features and the Universal LLM Key

FLOWRA uses Large Language Models in three places:

1. **AI Query Builder** — open chat that turns a plain-English (or Hindi /
   Hinglish) question into a SQL-like query against your data.
2. **AI Expense Insights** in CA Corner — summarises your expense ledgers and
   flags anomalies.
3. **Auto Reorder Suggestions** in Inventory — proposes purchase orders based
   on velocity.

All three currently use **GPT-5.2** (OpenAI) via the **Emergent Universal LLM
Key**. The customer doesn't need to bring their own OpenAI key — Emergent
manages and bills it. Admin can see the balance under Profile → Universal Key.

If the balance ever runs out, the AI features show "AI temporarily
unavailable — please top up". Non-AI modules keep working normally.

The Universal Key also supports:
- Google Gemini 3 (text + Nano Banana image generation)
- Anthropic Claude (Sonnet 4.5, Opus 4.5, Haiku 4.5)
- OpenAI image (GPT Image 1)
- Sora 2 (video)
- OpenAI Whisper (speech-to-text)

These are wired into the codebase via the `emergentintegrations` Python
library but not all are exposed in the UI yet. See [§14](#14-changelog) for
what's live today.

---

<a id="11-data-model"></a>
## 11. Where your data lives (collections in plain English)

FLOWRA stores everything in MongoDB. There are ~50 collections. Here are the
ones you'll hear about most, with what they hold:

| Collection | Plain-English content |
|---|---|
| `users` | Every login (admins, employees, salesman, dispatch, super_admin, flowra_staff) |
| `tenant_settings` | Per-business config (overdue threshold, expense groups, etc.) |
| `company_mappings` | Encrypted name + UUID for each company under a tenant |
| `sales_vouchers` | Every sales invoice (header + items[] + ledger_entries[]) |
| `purchase_vouchers` | Every purchase (goods + expense) |
| `receipt_vouchers` | Every receipt with bill allocations |
| `credit_notes` | Sales returns + rate-difference notes |
| `debit_notes` | Purchase returns |
| `journal_vouchers` | Adjustment entries |
| `contra_vouchers` | Bank-to-bank, cash-to-bank transfers |
| `stock_journals` | Stock transfers + manufacturing entries |
| `customers` | Sundry-debtor party masters + outstanding + transaction count |
| `sundry_creditors` | Supplier masters |
| `inventory_items` | Every SKU + qty + rate + reorder level + ABC tag |
| `all_ledgers` | Flat list of every ledger with balance + parent group (for CA Corner) |
| `bank_cash_ledgers` | Subset of `all_ledgers` filtered to bank + cash |
| `profit_loss` | Pre-aggregated P&L group totals |
| `dispatch_cards` | One row per Kanban card |
| `dispatch_porters` / `dispatch_transporters` | Vendor masters for dispatch |
| `dispatch_porter_payments` / `dispatch_transporter_payments` | Settlements |
| `dispatch_settings` | Per-tenant dispatch defaults |
| `salesman_master` | Salesman list + mapped customers + targets |
| `salesman_beats` / `beat_runs` | Daily beat plans + check-ins |
| `salesman_orders` | Orders raised from the mobile app (pre-billing) |
| `customer_targets` / `customer_target_removals` | Per-customer quarterly targets |
| `customer_followups` | "Call X on Y" reminders |
| `overdue_digest` | Pre-computed overdue table |
| `audit_logs` | Every meaningful action |
| `sync_history` | Agent run log |
| `sync_status` | "Is a sync running right now?" |
| `agent_commands` | Queued commands for the desktop agent to pick up |
| `tally_connections` | Saved Tally / Busy connection details per company |
| `ai_queries` | Saved AI Query Builder sessions |
| `prospects` | Lead pipeline (SuperAdmin) |
| `questionnaires` | Onboarding feedback |
| `referral_codes` / `referrals_dashboard_views` | Refer & Earn |
| `archived_tenant_data` | Holding area when a tenant is disconnected |

> **Why split into so many?** It's how MongoDB stays fast. Each collection is
> indexed by `tenant_id + company_id` (and often `voucher_date`), so even with
> millions of vouchers across all customers, a single query for one tenant is
> milliseconds.

---

<a id="12-security"></a>
## 12. Security, privacy and the "no data on cloud" claim

The marketing site says *No Data on Cloud\**. Here's exactly what that means:

### What we DO send to the cloud
- Structured business rows: vouchers, masters, ledgers.
- Encrypted company names (Fernet AES-128).
- Encrypted login credentials inside the agent's local config.

### What we NEVER send
- Your Tally backup file (`.tcp`, `.txt`, `.bak`).
- Your Busy `.bds` file.
- Tally screenshots or PDFs.
- Anything from outside the financial year you authorise.

### How a single tenant is sealed off
- **`tenant_id`** is added to every row, every query, every API call.
- The web app and agent both carry it inside a signed JWT.
- A salesman of tenant A literally cannot construct an API call that returns
  tenant B's data — the backend checks the JWT's `tenant_id` against the
  query's `tenant_id` on every single endpoint.

### Encryption at rest
- Company names: Fernet (symmetric AES-128) using `JWT_SECRET` as the key
  derivation seed. Lookups happen via deterministic HMAC-SHA256 hash so two
  syncs of the same name still resolve to the same UUID.

### Authentication
- Email + bcrypt password hash (cost factor 12).
- JWT (HS256) with a 24-hour expiry stored in `httpOnly` cookie + bearer
  token.
- Optional reCAPTCHA v3 on login (currently fail-open if score >= 0.3 or
  missing token, for prospect demos).

### Idle timeout
- 30 minutes of no activity → automatic logout in the browser.

### Audit trail
- Every login (success + failure), password change, employee created, prospect
  converted, referral payout, data export, etc. lands in `audit_logs` with the
  client IP. Available from Setup → Audit Log.

### "Disconnect" kill switch
- Setup → Tenant Settings → **Disconnect** moves all your rows to
  `archived_tenant_data`, then schedules a hard delete in 7 days. Your data is
  gone, your login still works (in case you want to re-onboard).

### Server-side protections
- All `/api/*` traffic over HTTPS (TLS 1.2+).
- CORS limited to FLOWRA's hosted domains.
- Rate-limit on `/api/auth/login` (5 failed attempts → 15-min cooldown).
- MongoDB instance is private (not exposed to the internet); only the FastAPI
  layer can reach it.

---

<a id="13-plans"></a>
## 13. Plans, subscriptions, and the demo account

### 13.1 Subscription plan defaults

| Field on a user document | Default |
|---|---|
| `plan` | `enterprise` |
| `max_companies` | `10` |
| `max_employees` | `20` |
| `subscription_months` | `12` |

When `max_employees` is hit, the admin sees a clear error and a CTA to
upgrade. Renewal requests can be raised from Profile → Subscription.

### 13.2 The pre-loaded demo account

For prospect demos, FLOWRA ships a self-contained demo:

| | |
|---|---|
| **Login** | `demo@flowralive.in` |
| **Password** | `demo2026` |
| **Subscription** | 24 months (won't expire during a sales cycle) |
| **Companies** | 3 — Sharma Lubricants & Distribution Pvt Ltd (FMCG/auto), Bharat Electricals & Hardware Pvt Ltd, Krishna Textiles & Garments LLP |
| **Per-company data** | 35 inventory items, 12-16 customers, 3-5 salesmen, 70 sales vouchers, ~30 receipts, 20 purchase/expense vouchers, 10 dispatch cards |
| **Vouchers (total)** | 210 sales + 60 receipts + 60 purchases across 10 months |
| **Revenue (seeded)** | ~₹68 lakh |
| **Reseed any time** | `cd /app/backend && python3 scripts/seed_demo_account.py` |

All seeded dates are **relative to today**, so the dashboard charts and
"recent transactions" always look fresh, no matter which week the demo is
shown.

Twelve **demo salesman logins** (`rajesh.lub.demo@flowralive.in`,
`amit.lub.demo@flowralive.in`, etc.) all use the same `demo2026` password, so
the same demo can showcase the field salesman mobile app too. Full list lives
in `/app/memory/test_credentials.md`.

### 13.3 Adding / removing companies and employees

- **New company:** Setup → Company Setup → "Add company". After save, the
  agent picks up the new `company_id` on its next 30-second command poll.
- **New employee:** Setup → Manage Employees → "Create". A password is
  generated and emailed to them; they're forced to change it on first login
  (`must_change_password` flag).
- **Pause an employee:** toggle Active off. Their JWT is invalidated within
  one minute.

---

<a id="14-changelog"></a>
## 14. Recent changes (changelog)

### Feb 2026

**Demo account seeding**
- New script `/app/backend/scripts/seed_demo_account.py` creates a single
  admin user (`demo@flowralive.in` / `demo2026`) with 3 companies fully
  populated — see [§13.2](#13-plans).

**Tally Sync Agent v9.8.9-daybook-lvd**
- DayBook fallback for `$$LastVoucherDate` when TDL returns empty.
- Cleaner debug logs distinguishing TDL empty vs Day-Book scan failure.

**Tally Windows Build Kit shipped**
- Tkinter GUI wrapper (`flowra_gui.py`) over the CLI agent.
- PyInstaller spec + `build.bat` produce a single `.exe`.
- `pystray` system tray + Windows startup registry hook.
- Zip available at `/app/frontend/public/flowra-agent-buildkit.zip`.

**Salesman Order Recommendations**
- `/api/salesman-orders/customer-history/{customer_name}` returns the
  customer's last 10 months of purchases.
- `/api/salesman-orders/related-items/{customer_name}` returns AI-driven
  cross-sell suggestions via velocity + affinity.
- UI redesigned with "Repeat last order" + "Suggestions" tabs.

**SuperAdmin Dashboard refactor**
- `SuperAdminDashboard.js` split into 9 modular tab components in
  `pages/super-admin/tabs/`.

**Flowra Staff role**
- New `flowra_staff` role for FLOWRA's internal team with fine-grained tab
  access. Endpoints under `/api/super-admin/staff`.

**Sales & marketing collateral**
- `PRODUCTION_PLAYBOOK.pdf`, `FLOWRA_BUSINESS_PROPOSAL.pdf/pptx` generated
  via `weasyprint`, `python-pptx`, `matplotlib`.

### April 2026

**CA Corner enhanced**
- New **Balance Sheet** view — Assets vs Liabilities & Capital, grouped by
  parent_group with expandable ledger drill-down.
- New **Ledger Drill-Down** — Income/Expense toggle, parent-group bars, per
  ledger % share.
- AI Expense Insights powered by GPT-5.2.

**Tally Sync Agent v9**
- Deletion reconciliation (Option B) added.
- Contra vouchers, bank/cash ledger balances, full P&L group sync added in
  v8 → carried into v9.
- FY auto-discovery, encrypted local config, memory-optimised chunked
  uploads.

**Busy Sync Agent v1.0**
- Initial release — feature parity with Tally agent except `standard_price`
  + per-line DR/CR direction (on the roadmap).

### Earlier

- Dispatch Terminal Kanban + porter/transporter settlements.
- Salesman Order System (admin + mobile-first PWA).
- Refer & Earn programme with commission ledger.
- Inventory Analytics (Pareto, Pivot, Sales Frequency, Movement,
  Below-cost).
- AI Query Builder.

### On the roadmap (next 60 days)

- WhatsApp Automation (overdue reminders) — pending route decision
  (AiSensy + Meta Lead Ads vs direct Meta Cloud API).
- GST Portal integration — manual GSTR JSON upload + reconciliation in CA
  Corner.
- Busy Agent v1.1 parity: `standard_price` + per-line DR/CR direction.
- Export Audit Logs to CSV.
- Weekly "Sync Health" digest email to admins.
- Move salesman cross-sell affinity calculation to a background job to
  drop API latency.

---

<a id="15-troubleshooting"></a>
## 15. Troubleshooting — common situations

### "Today's sale isn't showing yet."
1. Open Sync History → check the latest row. If it's >10 min old, the agent
   is paused. Right-click the tray icon → Resume.
2. If the agent log shows "Tally ODBC connection refused", reopen Tally and
   make sure F1 → Connectivity → ODBC Server = Yes, port 9000.
3. Last resort: from the web app, Setup → Tally Connection → **Resync this
   month**. The command lands on the agent within 30 seconds.

### "I deleted a voucher in Tally but it still shows in FLOWRA."
- Wait for the next sync (max 20 min). Deletion reconciliation will catch
  it. If you want it gone immediately, click **Resync this month** in
  Setup → Tally Connection.

### "Salesman can't see his customers."
- Setup → Manage Salesmen → open the salesman → ensure customers are in his
  **mapped_customers** list. Save and ask him to pull-to-refresh on the
  mobile app.

### "My CA wants only read-only access."
- Setup → Manage Employees → Create. Pick role `employee`, untick everything
  except `ca_corner` and `dashboard`. Send the credentials.

### "Login says 'Subscription expired'."
- Visit Profile → Subscription → Request Renewal. SuperAdmin or your account
  manager will respond within 24 h.

### "I want to download all my data."
- Setup → Data Export → "Download Full Tenant ZIP". Includes every collection
  scoped to your tenant in CSV + JSON.

### "I want to wipe everything and disconnect."
- Setup → Tenant Settings → Disconnect. A 7-day grace window starts; we hard
  delete after that. You can cancel the disconnect from the same screen
  during the window.

### "Agent log says: `STANDARDPRICE 0` for every item."
- A Tally TDL quirk — the agent strips the trailing `/unit` (e.g.
  `1495.00/Nos`). If it still happens, the company has no rate set at all on
  the items. Fix in Tally → Inventory Info → Stock Items → set Standard Cost
  / Standard Selling Price.

### "Busy agent crashes with `IM002 — Data source not found`."
- Microsoft Access Database Engine 2016 (64-bit) is not installed. Download
  from microsoft.com/en-us/download/details.aspx?id=54920 and rerun.

---

<a id="16-glossary"></a>
## 16. Glossary

| Term | What it means in FLOWRA |
|---|---|
| **Tenant** | One business signed up with FLOWRA. Has 1+ companies. |
| **Company** | One Tally / Busy company (typically one GSTIN). |
| **`tenant_id` / `company_id`** | UUIDs that wall off your data from every other tenant. |
| **JWT** | The 24-hour login token issued at sign-in. |
| **Universal LLM Key** | Emergent-managed AI credit shared across GPT, Gemini, Claude. |
| **Voucher** | A single transaction in Tally / Busy — invoice, receipt, journal, etc. |
| **Stock group** | The Tally / Busy parent category an item belongs to. |
| **ABC category** | A=top 20 % of revenue, B=next 30 %, C=remaining, D=dead stock. |
| **Beat** | A daily field-route for a salesman covering a cluster of customers. |
| **Kanban card** | A row in the Dispatch Terminal that tracks one invoice's pack & ship status. |
| **Reconciliation manifest** | The list of IDs the agent says still exist in Tally / Busy — used by the backend to delete orphans. |
| **Disconnect** | The user-initiated kill switch that schedules a hard wipe in 7 days. |

---

### Where to ask for help

- In-app: bottom-right chat bubble.
- Email: support@flowra.in
- Self-help: Setup → Help & Resources (links to Training Booklet, What's New
  PDF, Customer Questionnaire, Production Playbook).

---

*FLOWRA is a JODIDAR INDIA product. Tally\* and Busy\* are trademarks of their
respective owners and are not affiliated, endorsed, connected or sponsored in
any way to this website. They are referenced here solely to describe
compatibility.*
