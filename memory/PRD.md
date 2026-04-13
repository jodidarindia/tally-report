# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## CA Corner (Apr 2026) — Enterprise Feature
### Cash Flow (Tally* Indirect Method):
- Opening/Closing Cash+Bank, Total Receipts, Total Payments, Net Cash Change
- 3 activity sections: Operating (Net Profit + Depreciation), Investing, Financing (OD/Loans)
- Bank & Cash account details table with type, opening, closing
- FY-filtered, branch-filtered

### AI Expense Insights (GPT-5.2):
- Analyzes Tally* expense data via Emergent LLM Key
- Identifies top overspending areas, suggests cost reductions
- Expense Health Score, Red Flags, Quick Wins
- Summary cards: Income, Expense, Net P&L, Expense Ratio

### P&L Report:
- Annual view: Income/Expense ledger tables (collapsible, sorted by amount)
- Monthly view: 12-column table (Apr-Mar) with Sales, Purchases, Gross Profit, Receipts
- Annual/Monthly toggle, sticky first column, mobile responsive

## Architecture
- Backend: `/app/backend/routes/ca_corner.py` (3 endpoints)
- Frontend: `/app/frontend/src/pages/CACorner.js`
- Feature gated: `ca_corner` in ALL_FEATURES (enterprise plan)
- Desktop Agent: v8 at `/app/desktop-agent/tally_sync_agent_v8.py`
- Collections: `contra_vouchers`, `bank_cash_ledgers`, `profit_loss`

## Key Fixes This Session
- reCAPTCHA v3: Removed React provider, load via script tag, 3s timeout on execute
- Login works reliably in all environments
- Desktop agent download link updated to `/flowra-desktop-agent.py`
- Onboarding tour updated with CA Corner step

## Upcoming
- P1: Compile Desktop Agent v8 to `.exe`
- P2: Export Audit Logs to CSV
