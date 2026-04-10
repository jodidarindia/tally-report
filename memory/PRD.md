# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, and data isolation.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests (v7.0 login-based auth)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key

## Multi-Tenant Architecture
- **Super Admin**: Manages all admin tenants, feature gating, password resets, subscription management
- **Admin**: Owns a tenant with isolated data. Created with email-based username.
- **Employee**: Belongs to an admin's tenant, inherits features
- **Data Isolation**: All DB queries filter by `tenant_id` + `company_id`
- **Feature Gating**: 9 toggleable features per admin tenant (sync_history + setup ON by default)
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
- Security headers, rate limiting on login

### Super Admin Enhancements (Apr 10 2026)
- FLOWRA logo on login page and all navbars
- Admin cards show subscription details: joining date, plan duration (months), active/expired status
- Edit Admin modal (pencil icon) for changing name, features, subscription period
- Subscription period dropdown (1/3/6/12/24/36 months) on create and edit
- sync_history and setup features default to ON in create admin form
- Page refreshes (stats + admin list) after activate/deactivate toggle
- ProfileModal backdrop click-to-close fix
- Connection Status card on Setup page: last sync time, agent version, linked companies, synced data counts

### Desktop Sync Agent v7.0 (Apr 2026)
- Login-based auth: agent prompts email + password, authenticates with FLOWRA backend
- Auto-gets tenant_id, sync_token, and companies from login response
- Saved session file (flowra_auth.json) — auto-loads on restart, re-login if expired
- Incremental sync: MD5 hash comparison skips unchanged data types
- Multi-company detection and interactive company selection
- --logout flag to clear saved credentials

## Key API Endpoints
- `POST /api/auth/login` - JWT login (returns tenant_id, companies, features)
- `GET /api/auth/me` - Current user with companies
- `GET /api/auth/sync-token` - Desktop agent sync token
- `POST /api/auth/change-password` - Change own password
- `POST /api/auth/reset-password` - Reset employee/admin password
- `GET /api/super-admin/stats` - Platform stats
- `GET /api/super-admin/admins` - List all admin tenants (includes subscription data)
- `POST /api/super-admin/admins` - Create admin (requires email, includes subscription_months)
- `PUT /api/super-admin/admins/{username}/features` - Toggle features
- `PUT /api/super-admin/admins/{username}/subscription` - Update name, subscription period
- `PUT /api/super-admin/admins/{username}/toggle-active` - Activate/deactivate admin
- `GET /api/sync/connection-status` - Desktop agent sync status for Setup page
- `GET /api/inventory/items` - Inventory (tenant-isolated)
- `GET /api/sales/vouchers` - Sales (tenant-isolated)
- `GET /api/customers/outstanding` - Outstanding (tenant-isolated)
- `POST /api/ai/advanced-query` - AI report generation

## DB Schema Updates
- `users` collection: added `subscription_months` (int), `subscription_start` (ISO datetime)

## Pending Tasks
### P1
- Compile Desktop Agent into one-click installable .exe with UI/CLI
- Verify Multi-company Data Switcher on Frontend (CompanySelector.js)

### P2
- Automated payment follow-up reminders via email/WhatsApp
- Customer Payment Behaviour detailed dropdown analytics

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt
- MongoDB
- OpenAI GPT-5.2 (Emergent LLM Key)
