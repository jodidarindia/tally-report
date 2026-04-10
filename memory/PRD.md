# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, and data isolation.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests (v7.0 login-based auth)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key

## Security Architecture
- **Auth**: bcrypt password hashing, HS256 JWT (secret from .env, 256-bit random key)
- **Tenant Isolation**: Every DB query includes `tenant_id` + `company_id` via `_build_query()` / `tenant_context.py`
- **Headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Rate Limiting**: 20 login attempts per 60 seconds
- **Desktop Agent**: Login-based auth with token auto-refresh, session file (not plain .env secrets)

## Multi-Tenant Architecture
- **Super Admin**: Manages admin tenants, feature gating, password resets, subscriptions
- **Admin**: Email-based username, owns tenant with isolated data
- **Employee**: Belongs to admin's tenant, inherits features
- **Data Isolation**: `tenant_id` + `company_id` required on ALL DB operations (reads, writes, deletes)
- **Feature Gating**: 9 toggleable features (sync_history + setup ON by default)
- **Multi-Company**: CompanySelector on login, X-Company-ID header on all API calls, per-company sync info shown

## What's Been Implemented

### Core Features (Complete)
- JWT Auth with super_admin/admin/employee roles
- Multi-FY support, Dashboard, Inventory, Sales, CRM, AI Reports, Sync History
- PDF Ledger export, WebSocket live sync, AI Purchase Orders (GPT-5.2)

### Multi-Tenant & Security (Apr 2026)
- Super Admin dashboard with admin management, feature toggles, stats, subscriptions
- Role-Based Access Control (RBAC) in frontend routing
- Email-based username, password change/reset
- Security headers, rate limiting

### Multi-Company Data Switcher (Apr 10 2026) — VERIFIED
- CompanySelector with real-time sync info (last sync time, item count, voucher count per company)
- X-Company-ID header on every API request
- Data isolation verified across all pages

### Security Audit (Apr 10 2026) — 8 ROUTES FIXED
Routes that had missing tenant/company isolation:
1. `GET /api/sales/vouchers/{id}` — now includes tenant/company filter
2. `GET /api/salesman/master` — now requires tenant context
3. `GET /api/salesman/performance` — salesman_master filtered by tenant
4. `GET /api/salesman/performance-detailed` — requires tenant context
5. `POST /api/salesman/master` — includes tenant_id/company_id on insert
6. `DELETE /api/salesman/master/{name}` — requires tenant context on delete
7. `POST /api/customers/targets/set` — includes tenant_id/company_id
8. `PATCH /api/customers/followups/{id}` — includes tenant filter
Cross-tenant isolation verified (test_admin cannot see admin's data).

### Desktop Sync Agent v7.0
- Login-based auth, incremental sync with hash detection, multi-company support

## Key API Endpoints
- Auth: `/api/auth/login`, `/api/auth/me`, `/api/auth/sync-token`, `/api/auth/change-password`, `/api/auth/reset-password`
- Super Admin: `/api/super-admin/stats`, `/api/super-admin/admins`, `PUT .../features`, `PUT .../subscription`, `PUT .../toggle-active`
- Sync: `/api/sync/companies-status`, `/api/sync/connection-status`, `/api/sync/status`
- Data: `/api/inventory/items`, `/api/sales/vouchers`, `/api/customers/outstanding`
- AI: `/api/ai/advanced-query`

## Test Data
- Admin (admin/admin123): 2 companies
  - "ASA AUTOTECH INDIA PRIVATE LIMITED": 202 inv, 1258 sales, 38+ customers
  - "Demo Trading Co": 3 inv, 2 sales, 2 customers

## Pending Tasks
### P1
- Compile Desktop Agent into one-click installable .exe with UI/CLI

### P2
- Automated payment follow-up reminders via email/WhatsApp
- Customer Payment Behaviour detailed dropdown analytics

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt
- MongoDB
- OpenAI GPT-5.2 (Emergent LLM Key)
