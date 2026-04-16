# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## Architecture
- Frontend: React + Tailwind CSS, modular components
- Backend: FastAPI + MongoDB
- Desktop Agent: v9 at `/app/desktop-agent/tally_sync_agent_v9.py`

## Key Features
- Dashboard, Sales, CRM, Inventory, Analytics, CA Corner
- SuperAdmin, Refer & Earn, Onboarding Tour
- reCAPTCHA v3, idle timeout, Excel exports
- Branch toggle, auto-reorder levels, public pages
- Digital Questionnaire + SuperAdmin Leads tab
- Deletion reconciliation (agent v9)
- Part Number sync for stock items
- Company resync/delete with command queue
- 5-min sales quick sync + 20-min full sync
- Per-company FY selection + last voucher date cap
- Sync-in-progress banner on frontend
- CRM target customer removal/reactivation per FY
- Bulk percentage target setting
- Branch exclusion for overdue, concentration risk, SPIP, forecast
- Month-vs-month cross-FY comparison in sales forecast

## API Endpoints (Recent)
- `POST /api/customers/targets/bulk-percentage` — Bulk set targets as % of prev FY
- `POST /api/customers/targets/remove` — Remove customers from target reports
- `POST /api/customers/targets/reactivate` — Reactivate removed customers
- `GET /api/customers/targets/removed` — List removed customers per FY
- `GET /api/insights/spip-analysis` — Sales vs Purchase vs Inventory gap analysis

## Bug Fixes (April 16, 2026)
- Fixed CRM Outstanding journal voucher double-counting: now computes net_credit = credit - debit
- Fixed SPIP Analysis item name extraction: sales voucher items use `item` key (not `item_name`)
- Verified CRM Targets (bulk %, removal, reactivation) all functional
- Verified Dashboard company isolation via X-Company-Id header

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P1: Dispatch Terminal (spec at `/app/memory/DISPATCH_TERMINAL_SPEC.md`)
- P2: Salesman Order System
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders via email/WhatsApp
