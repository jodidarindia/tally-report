# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## Architecture
- **Frontend**: React + Tailwind CSS, modular component architecture
- **Backend**: FastAPI + MongoDB
- **Desktop Agent**: v8 at `/app/desktop-agent/tally_sync_agent_v8.py`

### Frontend Architecture (Refactored Apr 2026)
App.js (~160 lines) — Clean orchestrator composing hooks + components:
- **Hooks**: `useAuth`, `useIdleTimeout`, `useCompany`
- **Components**: `LoginPage`, `PublicRouter`, `AppNavbar`, `SuperAdminLayout`, `PageRenderer`, `IdleWarningModal`
- **Pages**: Dashboard, Sales, CRM, Inventory, InventoryAnalytics, EnhancedAIReports, CACorner, ReferAndEarn, QuestionnaireForm, etc.

## Key Features Implemented
- Customer CRM, Inventory Analytics, SuperAdmin controls
- Refer & Earn (3%), Resend emails, Onboarding tour
- reCAPTCHA v3, 15-min idle logout, Excel exports
- Auto-reorder levels, Branch toggle, Public pages
- CA Corner (Cash Flow, P&L, AI Expense Insights) — Enterprise
- Digital Questionnaire Form (6-step) + SuperAdmin Leads tab with Excel export
- Resources menu on landing page (Presentation, Questionnaire PDF, Needs Assessment form)

## Marketing Materials
1. FLOWRA_Presentation.pdf (12 slides)
2. FLOWRA_Training_Booklet.pdf
3. FLOWRA_Social_Media_Kit.pdf (7 posts + 30-day calendar)
4. FLOWRA_Customer_Questionnaire.pdf (6-section printable)
5. **FLOWRA_Coming_Soon.pdf** (12 slides — Dispatch Terminal + Salesman Order System)

## Collections
- `referrals`, `contra_vouchers`, `bank_cash_ledgers`, `profit_loss`
- `users`, `questionnaires`

## Upcoming — P1 Priority
- **Dispatch Terminal** (Enterprise) — see `/app/memory/DISPATCH_TERMINAL_SPEC.md`
  - McDonald's KDS-style real-time dispatch board
  - Invoice cards with full tracking (boxes, porter, transport, employee)
  - Queue system, manual cards, physical verification
  - Porter expense tracking with weekly settlement
  - Close-of-day summary, admin drill-down for pending only
- Compile Desktop Agent v8 to `.exe`

## Upcoming — P2
- **Salesman Order System** (Enterprise)
  - Salesman login, mapped customers, inventory visibility
  - Order creation → admin approval → dispatch
  - Beat plans, performance analytics
- Export Audit Logs to CSV
- Automated payment follow-up reminders via email/WhatsApp
