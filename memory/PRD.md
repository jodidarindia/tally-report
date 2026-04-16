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

## Critical Technical Notes

### Opening Balance Logic (customers.py)
Tally's `opening_balance` on a customer = balance at START of `sync_status.financial_year` (the base FY).
- **Base FY** (e.g., 2026-27): Use Tally OB directly
- **Earlier FYs** (e.g., 2025-26): Reverse-compute: `OB = Tally_OB - FY_activity` (subtract sales, add receipts/CNs/JV credits)
- **Later FYs**: Forward-compute: `OB = Tally_OB + intervening_activity`
- **Non-customer parties** (depots, etc.): Use pure pre-FY voucher sum (no Tally OB)

### Journal Voucher Party Amounts (utils.py: get_jv_party_amount)
JV `credit_amount`/`debit_amount` = TOTAL across ALL ledger entries (e.g., 35284 for 2-entry JV). 
Use `ledger_entries` array to extract the party-specific amount (e.g., 17642).

## Bug Fixes (April 16, 2026)
- **Fixed FY-specific Opening Balance**: Tally OB is for base FY only; earlier FYs reverse-computed via voucher activity
- **Fixed JV double-counting**: Extract party-specific amounts from ledger_entries array
- **Fixed SPIP Analysis**: Sales voucher items use `item` key (not `item_name`)

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P1: Dispatch Terminal (spec at `/app/memory/DISPATCH_TERMINAL_SPEC.md`)
- P2: Salesman Order System
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders via email/WhatsApp
