# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## Architecture
- Frontend: React + Tailwind CSS, modular components
- Backend: FastAPI + MongoDB
- Desktop Agent: v9 at `/app/desktop-agent/tally_sync_agent_v9.py`

## Dispatch Terminal Feature (P1 — Complete)
- **Kanban Board**: 5 swim lane columns (New/Queued/Processing/Packed/Dispatched) + Hold lane
- **Date-based Card Creation**: Admin selects start date; only invoices from that date get cards. Old invoices assumed already dispatched.
- **Only Sales Invoices**: No sales orders connected
- **Transport/Porter Management**: Dropdown selection with inline create by employees. Master lists for both.
- **LR Tracking**: Transport LR receipt number field per dispatch card
- **Document Uploads**: Invoice doc, Sales order, LR receipt (image/PDF)
- **Dispatch History**: Permanent searchable archive for any invoice — accessible to both admin and employee
- **Admin View**: Tabs — Kanban Board, Overview, Pending (reassign), Porters (settlement), Employees
- **Employee View**: Same Kanban board, works on assigned cards, sees all active cards
- **Porter Settlement**: Running account, payment recording, balance tracking
- **`dispatch` Role**: Terminal-only access, created via employee management with role selector
- **Enterprise Feature**: Gated via ALL_FEATURES in enterprise subscription plan
- **Mobile Responsive**: All pages use responsive breakpoints
- Collections: `dispatch_cards`, `dispatch_porters`, `dispatch_transporters`, `dispatch_porter_payments`, `dispatch_settings`

## Dashboard Updates Frame
- Scrollable changelog at bottom of Dashboard (not in Dispatch section)
- Shows NEW/FIX tagged entries with dates

## Other Key Features
- Dashboard, Sales, CRM, Inventory, Analytics, CA Corner, SuperAdmin
- Refer & Earn, Onboarding Tour, reCAPTCHA v3, idle timeout
- Branch exclusion, auto-reorder levels, Digital Questionnaire
- Desktop Agent v9 with reconciliation, command queue, dual-schedule sync
- CRM Targets with bulk %, removal/reactivation, read-only past FYs

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P2: Salesman Order System
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
