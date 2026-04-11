# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.

## User Personas
- **Super Admin**: FLOWRA operator managing all tenants, subscriptions, prospects
- **Admin (Tenant Owner)**: Business owner with Tally Prime, subscribes to a plan
- **Employee**: Staff added by Admin with restricted feature access

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python script syncing Tally → FLOWRA cloud
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth

## Subscription Plans (INR)
| Feature | Starter (Rs.999/mo) | Professional (Rs.2,499/mo) | Enterprise (Rs.3,799/mo) |
|---------|------|--------------|------------|
| Dashboard | Yes | Yes | Yes |
| Sales | Yes | Yes | Yes |
| Inventory | Yes | Yes | Yes |
| CRM | No | Yes | Yes |
| Analytics | No | Yes | Yes |
| Salesman | No | No | Yes |
| AI Reports | No | No | Yes |
| Insider BI | No | No | Yes |
| Max Companies | 1 | 3 | 10 |
| Max Employees | 2 | 5 | 20 |

## What's Been Implemented (Completed)

### Core Features
- Multi-tenant authentication (JWT + bcrypt) with role-based access
- Tally Prime sync via Desktop Agent (v7) with login-based auth
- Dashboard with real-time sales/inventory/overdue data
- Sales tracking with voucher details
- Customer CRM with payment behavior, followups, targets
- Inventory management with stock analytics
- Movement analytics with AI-powered insights
- Salesman performance tracking (Enterprise only)
- AI Reports (GPT-5.2 powered) (Enterprise only)
- Insider BI Result page (Enterprise only)
- Sync History with detailed cycle tracking
- Tally Setup page with connection config
- Activity/Audit logging
- Multi-company support with company selector
- Multi-FY support with FY selector

### Security (April 2026)
- AES-256 field-level encryption for all PII (names, phones, emails)
- SHA-256 email hashing for prospect data
- Complete audit trail
- **Global email uniqueness enforced** across users + prospects in all creation flows:
  - Prospect Signup: checks users + prospects
  - SuperAdmin Create Admin: checks users + prospects (with redirect to Convert flow)
  - Admin Create Employee: checks users + prospects + validates email format
  - Convert Prospect: checks users
- **Employee tenant isolation**: Employees inherit parent admin's tenant_id, can only see data within their own tenant

### User Lifecycle & Data Integrity (April 2026)
- **Soft-delete with archive**: Deleting any user/employee archives their full record to `deleted_users` collection (minus password_hash) with `deleted_at`, `deleted_by`, `deletion_reason`, `original_tenant_id`, `original_role`
- **Admin deletion archives tenant data**: When SuperAdmin deletes an admin, all employees are archived to `deleted_users` and tenant data is summarized in `archived_tenant_data` before removal from active collections
- **Re-signup detection**: If a previously-deleted email signs up again, the prospect is flagged `returning_user: true` with `previous_tenant_id` for SuperAdmin awareness
- **SuperAdmin audit view**: `/api/super-admin/deleted-users` endpoint returns all archived user records and tenant data summaries
- **Clean tenant isolation**: New signups always get a fresh `tenant_id` — zero data leakage from old tenants
- Admin Profile > Employees tab: Add/Delete employees with plan-based limits
- Email format validation required for all new employees
- Employee count display with max limit and slots available
- Plan-based max_employees enforcement (Starter: 2, Professional: 5, Enterprise: 20)

### Marketing & Prospecting (April 2026)
- Public Landing Page with animated dashboard mockup
- Signup Page with demo request flow (Professional plan features)
- Prospect management in SuperAdmin (Enquiries tab)
- Convert Prospect to Admin with plan selection

### Subscription Management (April 2026)
- Plan enforcement (Starter/Professional/Enterprise) with feature gating
- Company and employee limits per plan
- Subscription start/expiry dates stored and displayed
- Profile Subscription tab with dates, plan info, renewal request
- SuperAdmin Renewals tab: near-expiry, expired, renewal requests
- Renewal popup on admin login if plan expires within 30 days
- Desktop Agent subscription validation (blocks sync if expired)
- Desktop Agent company limit enforcement per plan

### IST & FY Handling (April 2026)
- IST (Asia/Kolkata) formatting throughout the app
- Default FY set to latest synced FY from Tally on login
- Backend IST utility (ist_utils.py) for calculations

## Key API Endpoints
- POST /api/auth/login - Login with subscription data
- GET /api/auth/me - Current user with subscription info
- POST /api/auth/request-renewal - Admin requests renewal
- GET /api/sync/latest-fy - Latest synced FY
- POST /api/agent/sync - Tally sync (with subscription check)
- GET /api/super-admin/renewals - Renewal management
- PUT /api/super-admin/renewals/{username}/process - Approve/reject renewal
- POST /api/prospects/signup - New prospect signup
- POST /api/super-admin/convert-prospect - Convert to admin

## Tech Stack
- React 18, Shadcn UI, Lucide Icons, Sonner toasts
- FastAPI, Motor (MongoDB async), bcrypt, cryptography, PyJWT
- OpenAI GPT-5.2 (via Emergent LLM Key)
- MongoDB with AES-256 encryption at rest

## Upcoming Tasks
- P1: Desktop Agent — One-Click Installer (see details below)
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)
- P3: Refactor App.js into smaller routing/layout components

### Desktop Agent Installer — Detailed Requirements (P1)
**Goal:** Non-technical user downloads one file, double-clicks, and everything works.

**Package Requirements:**
- Single `.exe` installer (PyInstaller/Nuitka compiled) — no Python installation needed
- All dependencies bundled inside (requests, xmltodict, schedule, websockets, python-dotenv)
- Auto-detects if Tally Prime is running on localhost:9000 (or prompts for custom port)
- First-run wizard: Login with email/password → auto-configures everything → starts syncing
- System tray icon for background operation (start/stop/status)
- Auto-start on Windows boot (optional, user can toggle)
- Logs saved to `%APPDATA%/FLOWRA/` for troubleshooting

**User Experience (zero technical knowledge):**
1. Download `FLOWRA-Setup.exe` from the Setup page
2. Double-click to install (standard Windows installer with Next/Next/Finish)
3. App opens → Login screen (email + password)
4. Auto-detects Tally → selects companies → starts syncing
5. Minimizes to system tray — runs silently in background
6. Tray icon shows sync status (green = connected, yellow = syncing, red = error)

**Build Process:**
- Use PyInstaller `--onefile` with `--windowed` flag for no console window
- Wrap in Inno Setup or NSIS for proper Windows installer (Start Menu shortcut, uninstall support)
- Batch file alternative: `install.bat` that checks Python, installs if missing via embedded portable Python, then runs agent
- Sign the exe if possible (to avoid Windows SmartScreen warnings)

## Future Roadmap (User's Vision — April 2026)

### F1: Extended Tally Sync — Sale Price, Cost Price & Expenses (P1)
- Desktop Agent to sync **standard sale price** and **standard cost price** per item from Tally
- Sync **indirect & direct expense accounts** with their vouchers from Tally
- New collections: `expense_accounts`, `expense_vouchers` with tenant_id, company_id, FY scoping
- Sale/cost price fields to be added to `inventory_items` for margin analysis

### F2: Salesman Order Management System — Enterprise Only (P1)
**Salesman Login & Role:**
- New role: `salesman` (follows all existing user creation rules — unique email, tenant_id from parent admin, plan limits)
- Salesman can view: mapped customers (outstanding, ledger), warehouse inventory with sale prices
- Salesman CANNOT see other salesmen's customers or admin-level reports

**Order Workflow:**
- Salesman browses available inventory (with sale price) → selects customer → adds items + quantities → submits Sales Order
- Submitted order appears in **User Admin's Sales Order menu tab** for review/approval/dispatch
- Full order lifecycle: Draft → Submitted → Approved → Dispatched → Completed/Cancelled
- Order history with status tracking on both salesman and admin side

**Beat Plan System:**
- Admin creates beat plans (daily/weekly route schedule for salesman visits)
- Customers assigned to beat plans and mapped to specific salesmen
- Salesman sees daily beat plan with customer list, address, contact
- Salesman marks visit status (visited/skipped/rescheduled) with notes

**Beat Working Analysis:**
- End-of-day report: planned visits vs actual visits, orders placed, order value
- Weekly/monthly performance: beat adherence %, order conversion rate, average order value
- Admin dashboard view of all salesmen's beat performance

**Rules:**
- Enterprise plan only (feature-gated)
- All salesman user creation follows existing rules: unique email, email format validation, tenant_id from parent admin, max_employees limit applies
- Data isolation: salesman sees only their mapped customers and inventory within their tenant

### F3: AI Expense Insights — Part of Insider Result (P2)
- Expense accounts and vouchers imported from Tally analyzed by AI (GPT-5.2)
- AI generates insights on: spending patterns, expense reduction opportunities, category-wise trends, YoY comparison
- Displayed as a new section within the existing **Insider Result** page
- Covers: direct expenses, indirect expenses, category breakdown, anomaly detection
- Actionable suggestions for cost optimization
