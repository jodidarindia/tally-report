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
- Deletion reconciliation (agent v9), Part Number sync
- Company resync/delete with command queue
- 5-min sales quick sync + 20-min full sync
- CRM target customer removal/reactivation per FY
- Bulk percentage target setting
- Branch exclusion for overdue, concentration risk, SPIP, forecast
- **Dispatch Terminal** (NEW — April 2026)

## Dispatch Terminal Feature
- **Kanban Board**: Status lanes (New, Queued, Processing, Packed, Dispatched) + Hold
- **Auto-create**: Cards generated from synced Tally sales invoices
- **Manual Cards**: For samples, returns, replacements, internal transfers
- **Document Uploads**: Invoice doc, Sales order, LR receipt (image/PDF)
- **LR Tracking**: Transport LR receipt number per dispatch card
- **Porter Management**: Master list, per-dispatch charges, settlement reports, payment recording
- **Employee Role**: `dispatch` role — terminal access only, sees all active cards, works on assigned
- **Admin View**: Overview, Pending (with reassign), Porter Settlement, Employees, Updates/Changelog tabs
- **Dispatch History**: Permanent searchable archive with all documents for any invoice
- **Round-robin Assignment**: Auto-assign cards to dispatch employees
- Collections: `dispatch_cards`, `dispatch_porters`, `dispatch_porter_payments`

## Critical Technical Notes

### Opening Balance Logic (customers.py)
Tally's `opening_balance` = balance at START of `sync_status.financial_year` (base FY).
- **Base FY** (e.g., 2026-27): Use Tally OB directly
- **Earlier FYs** (e.g., 2025-26): Reverse-compute: subtract FY activity
- **Non-customer parties**: Use pure pre-FY voucher sum

### Journal Voucher Party Amounts (utils.py: get_jv_party_amount)
JV `credit_amount`/`debit_amount` = TOTAL across ALL ledger entries. Use `ledger_entries` array to extract party-specific amount.

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P2: Salesman Order System
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders via email/WhatsApp
