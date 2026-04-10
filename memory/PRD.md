# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, and data isolation.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests (v7.0 login-based auth)
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
- **Endpoints**: `/api/insights/customer-lifecycle`, `/api/insights/sales-forecast`, `/api/insights/spip-analysis`, `/api/insights/concentration-risk`

### Movement Analysis Fix (Apr 10 2026)
- **Movement Rate**: Fixed from 200% to 100% — formula changed from `sales/avg_stock` to `sales/opening_stock`
- **Inward column**: Added to table, sourced from `purchase_vouchers` (currently 0 as no purchase data synced)
- **Days to Sell**: Correctly shows 0 when closing stock = 0
- **Classification**: Now frequency-based — fast-moving (>2 txns/month), moderate (0.5-2/month), slow-moving (<0.5/month), non-moving (0 sales)
- **Opening Stock**: Estimated as `closing + sales - inward`

### Salesman FY-Specific Targets & Performance (Apr 10 2026)
- **FY-based targets**: Monthly/quarterly targets stored per FY in `fy_targets` nested dict
- **FY-based customer mapping**: Customer-to-salesman mapping stored per FY in `fy_customers`, inherits from previous FY
- **FY locking**: Once FY ends (past Mar 31), targets and mappings are frozen. Only current/future FY editable
- **Performance breakdown**: Monthly/Quarterly/Annual toggle with customer-wise tabulated comparison per salesman
- **Excel export**: Per salesman per duration — `GET /api/salesman/export?salesman_name=X&fy=Y&duration=monthly|quarterly|annual`
- **Best Performer tag**: Weighted average (achieved/target) determines top performer
- **Endpoints**: `/api/salesman/master`, `/api/salesman/performance`, `/api/salesman/performance-detailed`, `/api/salesman/export`

### Sorted & Searchable Dropdowns (Apr 10 2026)
- **SearchableSelect component**: Reusable component with type-to-search, sorted alphabetically, multiple selection support
- **Applied to**: Sales page (party filter), CRM page (followup customer), Salesman page (customer mapping)
- **Sorted dropdowns**: Inventory categories, stock groups, CRM customer groups, CRM states — all sorted alphabetically

### Audit Logging System (Apr 10 2026)
- **Actions logged**: login, login_failed, password_change, password_reset, admin_created, admin_deleted, admin_toggled, features_updated, data_export
- **Data captured**: actor, action, target, details, IP address (x-forwarded-for aware), timestamp
- **Super Admin view**: Activity Log tab in dashboard → sees ALL tenants' activity
- **Admin view**: Activity nav item → sees only own tenant's activity
- **Filter**: Dropdown to filter by action type
- **Tenant isolation**: Admin cannot see superadmin's or other tenants' logs

### Desktop Sync Agent v7.0
- Login-based auth, incremental sync with hash detection, multi-company support

## Key API Endpoints
- Auth: login, me, sync-token, change-password, reset-password
- Super Admin: stats, admins CRUD, features, subscription, toggle-active
- Audit: `/api/audit/logs`, `/api/audit/actions`
- Salesman: `/api/salesman/master`, `/api/salesman/performance`, `/api/salesman/performance-detailed`, `/api/salesman/export`
- Insights: `/api/insights/customer-lifecycle`, `/api/insights/sales-forecast`, `/api/insights/spip-analysis`, `/api/insights/concentration-risk`
- Sync: companies-status, connection-status
- Data: inventory/items, sales/vouchers, customers/outstanding, inventory/sales-frequency
- AI: advanced-query

## Pending Tasks
### P1
- Compile Desktop Agent into one-click installable .exe with UI/CLI

### P2
- Automated payment follow-up reminders via email/WhatsApp
- Customer Payment Behaviour detailed dropdown analytics

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt
- MongoDB, OpenAI GPT-5.2 (Emergent LLM Key)
