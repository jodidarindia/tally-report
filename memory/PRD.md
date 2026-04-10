# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports. Multi-tenant architecture with Super Admin, feature gating, RBAC, data isolation, and marketing website.

## Architecture
- **Frontend**: React + Shadcn UI + Tailwind CSS
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT
- **Desktop Agent**: Python v7.0 (login-based auth, tally_sync_agent_v7.py)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key
- **Encryption**: Fernet AES-256 for PII fields

## Security Architecture
- **Auth**: bcrypt password hashing, HS256 JWT (256-bit secret from .env)
- **Encryption**: AES-256 Fernet field-level encryption for prospect PII (company, email, phone, GST, address)
- **Tenant Isolation**: Every DB query includes `tenant_id` + `company_id` via `_build_query()`
- **Rate Limiting**: Auth: 10/60s, Signup: 3/hr, API: 200/60s
- **Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, Cache-Control
- **NoSQL Injection**: Pattern detection blocks MongoDB operators in user input
- **Payload Limit**: 10MB max request body
- **Audit Logging**: All admin actions logged with actor, action, target, details, IP, timestamp
- **API Docs**: Disabled (docs_url=None, redoc_url=None)

## Feature Gating (10 Features)
dashboard, sales, crm, inventory, analytics, salesman, ai_reports, insider, sync_history, setup

## What's Been Implemented

### Core Features (Complete)
- JWT Auth with super_admin/admin/employee roles
- Multi-FY support, Dashboard, Inventory, Sales, CRM, AI Reports, Sync History
- PDF Ledger export, WebSocket live sync, AI Purchase Orders (GPT-5.2)

### Multi-Tenant & RBAC (Apr 2026)
- Super Admin dashboard: admin CRUD, feature toggles, stats, subscriptions
- Email-based usernames, password change/reset, security headers, rate limiting

### Multi-Company Data Switcher (Apr 10)
- CompanySelector, X-Company-ID header, per-company data isolation

### Security Audit — 9 Routes Fixed (Apr 10)

### Insider Result Analytics (Apr 10) — Feature-gated
- Customer Lifecycle, Sales Forecast, SPIP Analysis, Concentration Risk

### Salesman FY Performance (Apr 10)
- FY-locked targets/mapping, performance breakdown, Excel export

### SearchableSelect Dropdowns (Apr 10) — Applied globally

### Audit Logging System (Apr 10)

### Inventory Analytics Redesign (Apr 10) — TESTED ✅
- Movement Analysis (5 clickable filters), Below Cost Sales (real cost), Sales Frequency (Excel+PDF)
- Desktop Agent fetches purchase_vouchers, debit_notes, sundry_creditors

### Payment Behavior FY Filtering + Opening Balance (Apr 10) — TESTED ✅
- FY-filtered with opening balance (pre-FY vouchers + Tally opening_balance fallback)
- Outstanding = OB + FY Sales - FY Credits (can be negative)

### Database Security Hardening (Apr 10) — TESTED ✅
- AES-256 Fernet field-level encryption for prospect PII
- Comprehensive security headers (HSTS, CSP, CORS, XSS, etc.)
- Rate limiting: auth 10/60s, signup 3/hr, API 200/60s
- NoSQL injection protection, payload size limits
- MongoDB indexes for security and performance
- API docs disabled in production

### Marketing Website (Apr 10) — TESTED ✅
- **Landing Page**: Hero section, 6 feature cards, pricing (3 tiers INR), testimonials, security section, footer
- **Pricing**: Starter ₹999/mo, Professional ₹2,499/mo, Enterprise ₹4,999/mo with Monthly/Annual toggle (17% annual savings)
- **Signup Flow**: 4-step process (Business Details → Demo → Requirements → Complete)
- **Demo Experience**: Hardcoded sample data (Demo Trading Co.) — NO real data exposed
- **Feature Requirements**: Optional feature selection after demo
- **Navigation**: Landing → Login / Signup, with cross-links

### SuperAdmin Enquiry Management (Apr 10) — TESTED ✅
- **Enquiries Tab**: Stats cards (Total, New, Contacted, Demo Given, Converted)
- **Prospect Cards**: Company, email, phone, status, contact, plan, demo status, date, requirements
- **Status Tracking**: new → contacted → demo_given → negotiating → converted / lost
- **Convert to Admin**: Creates admin account with email as username, selected features, subscription period
- **Audit Trail**: All status changes and conversions logged

### Desktop Agent v7.0 (Apr 10)
- Login-based auth, incremental sync, multi-company
- Fetches: inventory_items, sales_vouchers, purchase_vouchers, debit_notes, sundry_creditors, customers (with opening_balance)

## Key API Endpoints
- **Public**: /api/public/plans, /api/public/signup, /api/public/demo-request, /api/public/demo-data, /api/public/submit-requirements
- **Auth**: login, me, sync-token, change-password, reset-password
- **Super Admin**: stats, admins CRUD, features, subscription, toggle-active, prospects, prospects/{id}/status, prospects/{id}/convert
- **Audit**: logs, actions
- **Salesman**: master, performance, export
- **Insights**: customer-lifecycle, sales-forecast, spip-analysis, concentration-risk
- **Inventory**: movement-analysis, below-cost-sales, movement-export, below-cost-export, sales-frequency-export
- **CRM**: outstanding, payment-behavior, followups, targets
- **Sync**: companies-status, connection-status, vouchers
- **AI**: advanced-query

## Pending Tasks
### P1
- Compile Desktop Agent v7 into one-click installable .exe with UI/CLI

### P2
- Export Audit Logs to CSV
- Automated payment follow-up reminders via email/WhatsApp

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React, Outfit font
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt, cryptography (Fernet)
- MongoDB, OpenAI GPT-5.2 (Emergent LLM Key)
