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
- Customer CRM with targets, follow-ups, payment behavior scoring
- Inventory Analytics with movement analysis, below-cost sales detection
- SuperAdmin controls with user/subscription management
- Refer & Earn (3% commission, auto-generated codes, redemption approvals)
- Resend email triggers (subscription start, renew, expiring)
- 7-step onboarding tour for first-time users
- reCAPTCHA v3 on login/signup + 15-minute idle auto-logout
- Excel exports for CRM Outstanding and Targets
- 2-month auto-reorder levels with math.ceil rounding
- Public pages (Privacy, Terms, Refund, Contact, Social Media)
- Branch toggle for excluding internal transfers
- CA Corner (Cash Flow, P&L, AI Expense Insights) — Enterprise
- **Digital Questionnaire Form** — 6-step public needs assessment (Company Info, Tally Usage, Pain Points, Feature Priority 1-5, Decision & Budget, Next Steps)
- **Resources Menu** on landing page (Needs Assessment Form, Product Presentation PDF, Questionnaire PDF download)
- **SuperAdmin Leads Tab** — view/manage questionnaire submissions, status tracking (New/Contacted/Qualified/Closed), Excel export

## Marketing Materials (Updated Apr 2026)
All PDFs served from `/app/frontend/public/`:
1. FLOWRA_Presentation.pdf — 12-slide deck
2. FLOWRA_Training_Booklet.pdf — Employee training guide
3. FLOWRA_Social_Media_Kit.pdf — Social posts + 30-day calendar
4. FLOWRA_Customer_Questionnaire.pdf — 6-section printable questionnaire

## API Endpoints (New)
- `POST /api/questionnaire/submit` — Public, submits questionnaire
- `GET /api/super-admin/questionnaires` — Lists all submissions
- `GET /api/super-admin/questionnaires/export` — Excel download
- `PUT /api/super-admin/questionnaires/{idx}/status` — Update lead status

## Collections
- `referrals`, `contra_vouchers`, `bank_cash_ledgers`, `profit_loss`
- `users` (includes `onboarding_completed` flag)
- `questionnaires` — Stores all needs assessment submissions

## Upcoming
- P1: Compile Desktop Agent v8 to `.exe`
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders via email/WhatsApp
- P2: Salesman Order System (Enterprise Plan Only)
