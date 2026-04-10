# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, and data isolation.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests (v7.0 login-based auth, file: tally_sync_agent_v6.py)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key

## Security Architecture
- **Auth**: bcrypt password hashing, HS256 JWT (256-bit secret from .env)
- **Tenant Isolation**: Every DB query includes `tenant_id` + `company_id` via `_build_query()` / `tenant_context.py`
- **Audit Logging**: All admin actions logged with actor, action, target, details, IP address, timestamp
- **Headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Rate Limiting**: 20 login attempts per 60 seconds

## Multi-Tenant Architecture
- **Super Admin**: Manages admin tenants, feature gating, subscriptions, sees all audit logs
- **Admin**: Email-based username, owns tenant with isolated data, sees own audit logs
- **Employee**: Belongs to admin's tenant, inherits features
- **Data Isolation**: `tenant_id` + `company_id` on ALL DB operations
- **Feature Gating**: 9 toggleable features (sync_history + setup ON by default)
- **Multi-Company**: CompanySelector with per-company sync info, X-Company-ID header

## What's Been Implemented

### Core Features (Complete)
- JWT Auth with super_admin/admin/employee roles
- Multi-FY support, Dashboard, Inventory, Sales, CRM, AI Reports, Sync History
- PDF Ledger export, WebSocket live sync, AI Purchase Orders (GPT-5.2)

### Multi-Tenant & Security (Apr 2026)
- Super Admin dashboard with admin management, feature toggles, stats, subscriptions
- RBAC, email-based usernames, password change/reset
- Security headers, rate limiting

### Multi-Company Data Switcher (Apr 10 2026)
- CompanySelector with real-time sync info per company
- X-Company-ID header on every API request
- Data isolation verified across all pages

### Security Audit — 9 Routes Fixed (Apr 10 2026)
1. `GET /api/sales/vouchers/{id}` — tenant/company filter added
2. `GET /api/salesman/master` — tenant context added
3. `GET /api/salesman/performance` — tenant filter on salesman_master
4. `GET /api/salesman/performance-detailed` — tenant context added
5. `POST /api/salesman/master` — tenant_id/company_id on insert
6. `DELETE /api/salesman/master/{name}` — tenant context on delete
7. `POST /api/customers/targets/set` — tenant_id/company_id on insert
8. `PATCH /api/customers/followups/{id}` — tenant filter on update
9. `GET /api/inventory/sales-frequency` — tenant context added

### Insider Result Analytics (Apr 10 2026)
- **Customer Lifecycle**: Active/Inactive/Lost classification (90d/180d thresholds), pie chart, monthly trend, searchable table
- **Sales Forecast**: Moving average forecast (3-month), YoY comparison, revenue trend with forecast line
- **SPIP Analysis**: Sales vs Purchase gap detection (out_of_stock, understocked, dead_stock, overstocked, balanced), horizontal bar chart, filterable table
- **Concentration Risk**: Pareto analysis with cumulative % line, 80% reference line, risk level banner (critical/high/moderate/healthy)
- **Data Isolation**: All 4 endpoints use `_build_query(ctx, company_id)` — verified test_admin sees zero data

### Salesman FY-Specific Targets & Performance (Apr 10 2026)
- **FY-based targets**: Monthly/quarterly targets stored per FY in `fy_targets` nested dict
- **FY-based customer mapping**: Customer-to-salesman mapping stored per FY in `fy_customers`, inherits from previous FY
- **FY locking**: Once FY ends (past Mar 31), targets and mappings are frozen. Only current/future FY editable
- **Performance breakdown**: Monthly/Quarterly/Annual toggle with customer-wise tabulated comparison per salesman
- **Excel export**: Per salesman per duration
- **Best Performer tag**: Weighted average (achieved/target) determines top performer

### Sorted & Searchable Dropdowns (Apr 10 2026)
- **SearchableSelect component**: Reusable with type-to-search, sorted alphabetically, multiple selection support
- **Applied to**: Sales page (party filter), CRM page (followup customer), Salesman page (customer mapping)

### Audit Logging System (Apr 10 2026)
- **Actions logged**: login, login_failed, password_change, password_reset, admin_created, admin_deleted, admin_toggled, features_updated, data_export
- **Data captured**: actor, action, target, details, IP address, timestamp
- **Super Admin view**: Activity Log tab → sees ALL tenants' activity
- **Admin view**: Activity nav item → sees only own tenant's activity

### Inventory Analytics Redesign (Apr 10 2026) — TESTED ✅
- **Movement Analysis Tab**: 5 clickable classification filter cards (All/Fast/Moderate/Slow/Non-Moving) with live counts, sortable 10-column table (Item Name, Category, Opening, Inward, Outward, Closing, Movement %, Days to Sell, Txns, Classification), Excel export
- **Below Cost Sales Tab**: Real cost prices from purchase vouchers (weighted avg), negative-margin detection with summary cards (Items Below Cost, Total Loss, Affected Revenue), Excel export
- **Sales Frequency Tab**: Transaction frequency analysis with date filters, Excel + PDF exports, summary cards
- **Desktop Agent Updated**: Fetches `purchase_vouchers`, `debit_notes`, `sundry_creditors` from Tally. Opening stock from `opening_quantity`
- **Data Isolation**: Verified admin sees 202 items, test_admin sees 0 items
- **Test Report**: iteration_26.json — 100% pass (17/17 backend, all frontend verified)

### Desktop Sync Agent v7.0
- Login-based auth, incremental sync with hash detection, multi-company support
- Fetches: inventory_items, sales_vouchers, purchase_vouchers, debit_notes, sundry_creditors, ledgers

## Key API Endpoints
- Auth: login, me, sync-token, change-password, reset-password
- Super Admin: stats, admins CRUD, features, subscription, toggle-active
- Audit: `/api/audit/logs`, `/api/audit/actions`
- Salesman: `/api/salesman/master`, `/api/salesman/performance`, `/api/salesman/performance-detailed`, `/api/salesman/export`
- Insights: `/api/insights/customer-lifecycle`, `/api/insights/sales-forecast`, `/api/insights/spip-analysis`, `/api/insights/concentration-risk`
- Inventory Analytics: `/api/inventory/movement-analysis`, `/api/inventory/below-cost-sales`, `/api/inventory/movement-export`, `/api/inventory/below-cost-export`, `/api/inventory/sales-frequency-export`
- Sync: companies-status, connection-status, vouchers
- Data: inventory/items, sales/vouchers, customers/outstanding, inventory/sales-frequency
- AI: advanced-query

## Pending Tasks
### P1
- Compile Desktop Agent into one-click installable .exe with UI/CLI

### P2
- Export Audit Logs to CSV
- Automated payment follow-up reminders via email/WhatsApp
- Customer Payment Behaviour detailed dropdown analytics

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt
- MongoDB, OpenAI GPT-5.2 (Emergent LLM Key)
