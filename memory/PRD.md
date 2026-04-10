# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, and data isolation.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests (v7.0 login-based auth, files: tally_sync_agent_v7.py)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key

## Security Architecture
- **Auth**: bcrypt password hashing, HS256 JWT (256-bit secret from .env)
- **Tenant Isolation**: Every DB query includes `tenant_id` + `company_id` via `_build_query()` / `tenant_context.py`
- **Audit Logging**: All admin actions logged with actor, action, target, details, IP address, timestamp
- **Headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Rate Limiting**: 20 login attempts per 60 seconds

## Feature Gating (10 Features)
1. dashboard, 2. inventory, 3. sales, 4. crm, 5. analytics, 6. ai_reports, 7. salesman, 8. insider, 9. sync_history, 10. setup

## What's Been Implemented

### Core Features (Complete)
- JWT Auth with super_admin/admin/employee roles
- Multi-FY support, Dashboard, Inventory, Sales, CRM, AI Reports, Sync History
- PDF Ledger export, WebSocket live sync, AI Purchase Orders (GPT-5.2)

### Multi-Tenant & Security (Apr 2026)
- Super Admin dashboard with admin management, feature toggles, stats, subscriptions
- RBAC, email-based usernames, password change/reset, security headers, rate limiting

### Multi-Company Data Switcher (Apr 10 2026)
- CompanySelector with real-time sync info per company, X-Company-ID header

### Security Audit — 9 Routes Fixed (Apr 10 2026)

### Insider Result Analytics (Apr 10 2026)
- Customer Lifecycle, Sales Forecast, SPIP Analysis, Concentration Risk — all feature-gated

### Salesman FY-Specific Targets & Performance (Apr 10 2026)
- FY-based targets/mapping, locking, performance breakdown, Excel export

### Sorted & Searchable Dropdowns (Apr 10 2026)
- SearchableSelect component applied across app

### Audit Logging System (Apr 10 2026)

### Inventory Analytics Redesign (Apr 10 2026) — TESTED ✅
- Movement Analysis (5 clickable filters), Below Cost Sales (real cost), Sales Frequency (Excel+PDF exports)
- Desktop Agent fetches purchase_vouchers, debit_notes, sundry_creditors

### Payment Behavior FY Filtering + Opening Balance (Apr 10 2026) — TESTED ✅
- Payment Behavior now filters by FY (was ignoring FY before)
- Opening Balance calculated from pre-FY vouchers or Tally's opening_balance field
- Outstanding = Opening Balance + FY Sales - FY Credits (can be negative for overpayments)
- Customer expand card shows: Opening Balance, Total Sales (FY), Total Debits, Receipts, Credit Notes, Journal Credits, Total Credits, Closing Balance

### Feature Gating Updated to 10 Features (Apr 10 2026) — TESTED ✅
- Added 'insider' to ALL_FEATURES in backend (auth_service.py) and frontend (SuperAdminDashboard.js, App.js)
- Insider Result page properly feature-gated via renderFeatureGated()
- Seed script auto-adds new features to existing admins
- Fixed duplicate nav entries (analytics, insider)

### Desktop Agent v7.0 (Apr 10 2026)
- Renamed to tally_sync_agent_v7.py
- Fetches: inventory_items, sales_vouchers, purchase_vouchers, debit_notes, sundry_creditors, customers (with opening_balance), ledgers
- Login-based auth, incremental sync with hash detection, multi-company support

## Key API Endpoints
- Auth: login, me, sync-token, change-password, reset-password
- Super Admin: stats, admins CRUD, features, subscription, toggle-active
- Audit: logs, actions
- Salesman: master, performance, export
- Insights: customer-lifecycle, sales-forecast, spip-analysis, concentration-risk
- Inventory: movement-analysis, below-cost-sales, movement-export, below-cost-export, sales-frequency-export
- CRM: outstanding, payment-behavior, followups, targets
- Sync: companies-status, connection-status, vouchers
- AI: advanced-query

## Pending Tasks
### P1
- Compile Desktop Agent into one-click installable .exe with UI/CLI

### P2
- Export Audit Logs to CSV
- Automated payment follow-up reminders via email/WhatsApp

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt
- MongoDB, OpenAI GPT-5.2 (Emergent LLM Key)
