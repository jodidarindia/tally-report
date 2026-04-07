# Tally Reports - Product Requirements Document

## Problem Statement
Build a SaaS-based web application that connects to a Tally database (Tally Prime local version) to prepare inventory and sales reports. Includes AI-based report builder, CRM, salesman performance tracking, inventory analytics, and a self-hosting deployment package.

## Architecture
- **Frontend**: React + Tailwind CSS + Recharts + Shadcn/UI
- **Backend**: FastAPI + Motor (Async MongoDB)
- **Database**: MongoDB
- **AI**: GPT-5.2 via Emergent LLM Key
- **Auth**: Email OTP via Resend (with dev mode bypass)
- **Desktop Agent**: Python script that syncs Tally data to the cloud

## Implemented Features (All Complete)

### Core
- [x] Dashboard with summary stats + follow-up reminders
- [x] Inventory management with search, filter, export (PDF/Excel/CSV)
- [x] Sales vouchers view with date filtering and analytics charts
- [x] Tally connection setup page

### AI Features
- [x] AI Report Builder (GPT-5.2) with natural language queries
- [x] Enhanced AI Reports with report type selection and filters
- [x] AI Purchase Order generation with priority classification
- [x] Report history tracking

### CRM & Customer Management (Enhanced Apr 7, 2026)
- [x] Customer outstanding with aging analysis
- [x] **Customer Targets** — Set targets based on last FY sales, auto-suggest 15% growth
- [x] **Monthly Sales View** — Expandable per-customer monthly sales chart
- [x] **Customer Ledger Export** — XLS/PDF export per customer from Outstanding tab
- [x] **Follow-up Dropdown** — Customer selection from dropdown list (not free text)
- [x] **Dashboard Reminders** — Overdue (red), Today (amber), Upcoming follow-ups on Dashboard
- [x] Customer follow-ups (create, track, complete)
- [x] Payment behavior analysis and credit scoring

### Salesman Management
- [x] Salesman Master CRUD with customer mapping
- [x] Target setting (monthly + quarterly)
- [x] Performance tracking (target vs achievement chart)
- [x] Item-wise sales report per salesman

### Analytics
- [x] Inventory pivot tables (group by category)
- [x] Sales frequency with XLS/PDF export
- [x] Inventory movement analysis (fast/slow/dead-stock)
- [x] Below-cost sales identification

### Auth & Deployment
- [x] Email OTP authentication (Resend + dev mode bypass)
- [x] Docker Compose self-hosting package with deploy scripts

## Key API Endpoints
### CRM (New/Enhanced)
- `GET /api/customers/targets` — With monthly_sales, has_custom_target
- `POST /api/customers/targets/set` — Set target with last_fy_sales
- `POST /api/customers/ledger/export` — Export customer ledger (excel/pdf)
- `GET /api/dashboard/reminders` — Overdue/today/upcoming follow-ups

## Backlog
- P2: Real-time WebSocket sync between Desktop Agent and cloud
- P2: Multi-tenant support with organization management
- P3: WhatsApp/SMS OTP alternative
