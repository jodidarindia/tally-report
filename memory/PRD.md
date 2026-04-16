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

## Critical Helper: get_jv_party_amount()
Located in `/app/backend/utils.py`. Journal voucher documents store TOTAL voucher amounts in debit_amount/credit_amount (sum of all ledger entries). This helper extracts the party-specific amount from the `ledger_entries` array. Used in:
- customers.py (outstanding, payment behavior, ledger export opening balance)
- utils.py (overdue digest)

## Bug Fixes (April 16, 2026)
- **Fixed CRM Outstanding JV double-counting (ROOT CAUSE)**: JV credit_amount is total across all ledger entries (e.g., 35284 for 2-entry JV). Party-specific amount (17642) extracted from ledger_entries array via get_jv_party_amount() helper.
- Fixed SPIP Analysis item name extraction: sales voucher items use `item` key (not `item_name`)
- Verified CRM Targets (bulk %, removal, reactivation) all functional
- Verified Dashboard company isolation via X-Company-Id header

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P1: Dispatch Terminal (spec at `/app/memory/DISPATCH_TERMINAL_SPEC.md`)
- P2: Salesman Order System
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders via email/WhatsApp
