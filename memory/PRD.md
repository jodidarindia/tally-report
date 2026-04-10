# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, and data isolation.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT + WebSockets
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests (v7.0 login-based auth)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key

## Multi-Tenant Architecture
- **Super Admin**: Manages all admin tenants, feature gating, password resets
- **Admin**: Owns a tenant with isolated data. Created with email-based username.
- **Employee**: Belongs to an admin's tenant, inherits features
- **Data Isolation**: All DB queries filter by `tenant_id` + `company_id`
- **Feature Gating**: 9 toggleable features per admin tenant
- **Desktop Agent**: Login-based auth (email + password) → auto-gets `tenant_id` + `sync_token`

## What's Been Implemented

### Core Features (Complete)
- JWT Authentication with super_admin/admin/employee roles
- Multi-FY support with FY selector in navbar
- Dashboard with stat cards, overdue digest, top customers, recent transactions
- Inventory page with sortable columns, multi-select stock group filter, search
- Sales page with sortable columns, party/month filters, chart, export (PDF/Excel)
- CRM Outstanding tab with sortable columns, Opening Balance, aging, Ledger PDF export
- CRM Payment Behavior (FY-independent): summary bar, credit notes, journal credits
- AI Reports (GPT-5.2 powered) with filters and sample queries
- AI Purchase Order generation
- Inventory Analytics: Movement Analysis, Below Cost Sales, Sales Frequency
- Sync History page
- Tally-format PDF Ledger export with opening balance, voucher numbers, running balance
- WebSocket live sync status
- Copyright: Jodidar India footer

### Multi-Tenant & Security (Apr 2026)
- Super Admin dashboard with admin management, feature toggles, stats
- Feature gating (9 features toggleable per admin tenant)
- Multi-tenant data isolation (tenant_id + company_id on all queries)
- Role-Based Access Control (RBAC) in frontend routing
- Email-based username for new admin accounts (prevents duplicates)
- Password change (self), password reset (admin→employee, super_admin→admin)
- Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
- Rate limiting on login (20 attempts per 60 seconds)
- ProfileModal with backdrop close and close button

### Desktop Sync Agent v7.0 (Apr 2026)
- Login-based auth: agent prompts email + password, authenticates with FLOWRA backend
- Auto-gets tenant_id, sync_token, and companies from login response
- Saved session file (flowra_auth.json) — auto-loads on restart, re-login if expired
- Incremental sync: MD5 hash comparison skips unchanged data types
- Multi-company detection and interactive company selection
- Lightweight Collection requests (1-5 sec each, no Tally freeze)
- XML sanitization: handles control chars, numeric refs, unescaped &
- Local cache with company-specific subdirectories
- --logout flag to clear saved credentials

## Key API Endpoints
- `POST /api/auth/login` - JWT login (returns tenant_id, companies, features)
- `GET /api/auth/me` - Current user with companies
- `GET /api/auth/sync-token` - Desktop agent sync token
- `POST /api/auth/change-password` - Change own password
- `POST /api/auth/reset-password` - Reset employee password (admin) or admin password (super_admin)
- `GET /api/super-admin/stats` - Platform stats
- `GET /api/super-admin/admins` - List all admin tenants
- `POST /api/super-admin/admins` - Create admin (requires email username)
- `PUT /api/super-admin/admins/{username}/features` - Toggle features
- `GET /api/inventory/items` - Inventory (tenant-isolated)
- `GET /api/sales/vouchers` - Sales (tenant-isolated)
- `GET /api/customers/outstanding` - Outstanding (tenant-isolated)
- `POST /api/ai/advanced-query` - AI report generation

## Known Limitations
- Inventory valuation shows Rs.0 (Tally sync doesn't populate qty/price fields)
- WebSocket reconnection on initial page load (auto-reconnects)

## Pending Tasks
### P1
- Compile Desktop Agent into one-click installable .exe with UI/CLI
- Verify Multi-company Data Switcher on Frontend (CompanySelector.js)

### P2
- Automated payment follow-up reminders via email/WhatsApp
- Customer Payment Behaviour detailed dropdown analytics
- Desktop Agent incremental sync — per-month hash tracking (currently per-data-type)

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt
- MongoDB
- OpenAI GPT-5.2 (Emergent LLM Key)
