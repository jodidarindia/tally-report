# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## Architecture
- **Frontend**: React + Tailwind CSS, modular component architecture
- **Backend**: FastAPI + MongoDB
- **Desktop Agent**: v9 at `/app/desktop-agent/tally_sync_agent_v9.py`

### Frontend Architecture (Refactored Apr 2026)
App.js (~160 lines) — Orchestrator with hooks + components.

## Key Features Implemented
- Customer CRM, Inventory Analytics, SuperAdmin controls
- Refer & Earn (3%), Resend emails, Onboarding tour
- reCAPTCHA v3, 15-min idle logout, Excel exports
- Auto-reorder levels, Branch toggle, Public pages
- CA Corner (Cash Flow, P&L, AI Expense Insights) — Enterprise
- Digital Questionnaire Form (6-step) + SuperAdmin Leads tab
- Resources menu on landing page
- **Deletion Reconciliation (v9)**: Agent sends manifest of all IDs per data type; backend deletes orphans not in manifest. Fixes ghost data from Tally* deletions.
- **Part Number**: Stock items now fetch PARTNUMBER from Tally*. Displayed in Inventory table and Movement Analysis.

## Desktop Agent v9 Changes
- Deletion reconciliation (Option B) for 11 data types: sales, receipts, credit_notes, journal_vouchers, stock_journals, purchase_vouchers, debit_notes, contra_vouchers, customers, sundry_creditors, bank_cash_ledgers
- PARTNUMBER fetch from Tally* TDL Collection
- All v8 features retained (FY discovery, encrypted auth, P&L, Cash Flow sync)

## API Endpoints (New)
- `POST /api/agent/reconcile` — Receives manifest_ids from agent, deletes orphan DB records

## Collections
- `referrals`, `contra_vouchers`, `bank_cash_ledgers`, `profit_loss`
- `users`, `questionnaires`
- `sync_history` — Now logs reconcile events

## Upcoming — P1
- **Dispatch Terminal** (Enterprise) — see `/app/memory/DISPATCH_TERMINAL_SPEC.md`
- Compile Desktop Agent v9 to `.exe`

## Upcoming — P2
- **Salesman Order System** (Enterprise)
- Export Audit Logs to CSV
- Automated payment follow-up reminders
