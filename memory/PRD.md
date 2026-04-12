# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally Prime for business analytics, inventory management, CRM, and reporting.

## Domain & Ownership
- **Domain**: `www.flowralive.in`
- **Brand**: FLOWRA is owned by **JODIDAR INDIA**
- **Contact**: support@flowralive.in | +91 81204 70018
- **Registered Address**: KK Road, Raipur, Chhattisgarh (used only in legal pages)

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn UI, Recharts, react-google-recaptcha-v3
- **Backend**: FastAPI, MongoDB
- **Integration**: Tally Prime (desktop sync), OpenAI GPT-5.2 (AI features via Emergent LLM Key), Google reCAPTCHA v3

## Core Features (Implemented)
- Dashboard with overdue digest, sales analytics
- Inventory management with stock tracking, reorder alerts
- Inventory Analytics: Movement Analysis, Below Cost Sales, Sales Frequency, Customer Items
- Customer CRM: Outstanding/Aging, Targets, Follow-ups, Payment Behavior (credit scoring)
- Sales reports and AI-powered reports
- Salesman Performance tracking
- Tally Sync with status monitoring
- Branch/Division exclusion toggle (global across all modules)
- PDF Ledger export (Tally-format)
- Marketing PDFs (Presentation, Training Booklet, Social Media Kit) with demo data
- Multi-company support with company switching
- Super Admin panel

## Security Features (Apr 2026)
- **Google reCAPTCHA v3**: Invisible bot protection on Login and Signup forms. Backend verifies token with Google API, rejects scores below 0.3.
- **Idle Auto-Logout**: 15-minute inactivity timeout. Warning popup at 14 min with "Stay Logged In" button. Auto-logout at 15 min. Tracks mouse, keyboard, scroll, touch activity.
- **JWT-based Auth**: Token-based authentication with role-based access control.

## Public Pages (Apr 2026)
- Privacy Policy (DPDP Act 2023, IT Act 2000), Terms of Service, Refund Policy, Contact Us, Social Media
- WhatsApp floating button on public pages only (+91 81204 70018)
- Footer: "FLOWRA is a brand owned by JODIDAR INDIA"

## Mobile Responsiveness (Apr 2026)
- Horizontally scrollable data tables with sticky first column (Item Name / Customer Name)
- Tab labels wrap into two lines on mobile
- CSS: `border-collapse: separate` for `position: sticky` support

## Architecture
```
/app/
├── backend/
│   ├── routes/ (auth.py, super_admin.py, sales.py, inventory.py, customers.py, dashboard.py, sync.py, prospects.py)
│   ├── services/ (auth_service.py, recaptcha.py, audit_service.py, encryption_service.py, ist_utils.py)
│   ├── utils.py
│   └── scripts/ (generate_materials.py)
├── frontend/
│   ├── public/ (demo/, screenshots/, FLOWRA_*.pdf)
│   └── src/
│       ├── App.js (routing, auth, idle timeout, reCAPTCHA provider)
│       ├── App.css (.data-table, sticky columns, reCAPTCHA badge hidden)
│       ├── components/ (SearchableSelect, SyncStatusBar, RenewalPopup, ui/)
│       └── pages/ (PublicPages.js, LandingPage.js, SignupPage.js, Dashboard.js, etc.)
```

## Upcoming Tasks
- P1: Compile Desktop Agent into one-click `.exe` installer (PyInstaller/Inno Setup)
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)

## Future/Backlog
- Salesman Order System (Enterprise): Login, customer mapping, order workflow, beat plans
- AI Expense Insights (GPT-5.2): Analyze Tally expense data for reduction suggestions
- P3: Refactor App.js (extract routing, auth, layout into separate modules)
