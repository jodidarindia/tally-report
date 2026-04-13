# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## Architecture
- **Frontend**: React + Tailwind CSS, modular component architecture
- **Backend**: FastAPI + MongoDB
- **Desktop Agent**: v8 at `/app/desktop-agent/tally_sync_agent_v8.py`

### Frontend Architecture (Refactored Apr 2026)
App.js (~160 lines) — Clean orchestrator composing hooks + components:
- **Hooks**: `useAuth` (auth lifecycle), `useIdleTimeout` (15-min idle), `useCompany` (company/FY/branch state)
- **Components**: `LoginPage`, `PublicRouter`, `AppNavbar`, `SuperAdminLayout`, `PageRenderer`, `IdleWarningModal`
- **Pages**: Dashboard, Sales, CRM, Inventory, InventoryAnalytics, EnhancedAIReports, CACorner, ReferAndEarn, etc.
- **Backend Routes**: `/app/backend/routes/` (auth, super_admin, sales, inventory, customers, dashboard, sync, referrals, ca_corner)

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

## Key Features Implemented
- Customer CRM with targets, follow-ups, payment behavior scoring
- Inventory Analytics with movement analysis, below-cost sales detection
- SuperAdmin controls with user/subscription management
- Refer & Earn (3% commission, auto-generated codes, redemption approvals)
- Resend email triggers (subscription start, renew, expiring)
- 7-step onboarding tour for first-time users
- reCAPTCHA v3 on login/signup
- 15-minute idle session auto-logout
- Excel exports for CRM Outstanding and Targets
- 2-month auto-reorder levels with math.ceil rounding
- Public pages (Privacy, Terms, Refund, Contact, Social Media)
- Branch toggle for excluding internal transfers

## Collections
- `referrals`, `contra_vouchers`, `bank_cash_ledgers`, `profit_loss`
- `users` (includes `onboarding_completed` flag)

## Key Fixes
- reCAPTCHA v3: Removed React provider, load via script tag, 3s timeout on execute
- Login works reliably in all environments
- Desktop agent download link updated to `/flowra-desktop-agent.py`
- Onboarding tour updated with CA Corner step

## Upcoming
- P0: Update PDF Marketing Materials (Presentation, Training Booklet, Social Media Kit) with new features
- P1: Compile Desktop Agent v8 to `.exe`
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders via email/WhatsApp
- P2: Salesman Order System (Enterprise Plan Only)
