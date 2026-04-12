# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally Prime for business analytics, inventory management, CRM, and reporting.

## Domain
`www.flowralive.in`

## Ownership
- **Brand**: FLOWRA is owned by **JODIDAR INDIA**
- **Contact**: support@flowralive.in | +91 81204 70018
- **Registered Address**: KK Road, Raipur, Chhattisgarh (used only in legal pages)

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn UI, Recharts
- **Backend**: FastAPI, MongoDB
- **Integration**: Tally Prime (desktop sync agent), OpenAI GPT-5.2 (AI features via Emergent LLM Key)

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

## Public Pages (Implemented - Apr 2026)
- **Privacy Policy** — DPDP Act 2023, IT Act 2000 compliant. Grievance Officer details with address.
- **Terms of Service** — 12 sections covering eligibility, payments, IP, data ownership, governing law (Raipur, CG jurisdiction).
- **Refund & Cancellation Policy** — 7-day refund window, 15 days for annual, 7-10 business days processing.
- **Contact Us** — Email, WhatsApp, Phone cards. Registered office details.
- **Social Media** — Placeholder pages for Instagram, Facebook, LinkedIn, X (Twitter), YouTube. "Coming Soon" with WhatsApp notification CTA.
- **WhatsApp Floating Button** — On all public pages, links to +918120470018. NOT on authenticated app pages.
- **Footer** — Every public page footer shows "FLOWRA is a brand owned by JODIDAR INDIA" with legal links.

## Mobile Responsiveness (Implemented - Apr 2026)
- All data tables horizontally scrollable on mobile (375px viewport)
- Sticky/frozen first column (Item Name / Customer Name) stays visible while scrolling
- Tab labels wrap into two lines on mobile for readability
- CSS: `border-collapse: separate` required for `position: sticky` on table cells

## Architecture
```
/app/
├── backend/
│   ├── routes/ (auth.py, super_admin.py, sales.py, inventory.py, customers.py, dashboard.py, sync.py)
│   ├── utils.py (compute_overdue_digest)
│   └── scripts/ (generate_materials.py)
├── frontend/
│   ├── public/ (demo/, screenshots/, FLOWRA_*.pdf)
│   └── src/
│       ├── App.js (main layout, routing, auth, nav, public page routing)
│       ├── App.css (.data-table styles, sticky columns, loading states)
│       ├── components/ (SearchableSelect, SyncStatusBar, RenewalPopup, ui/)
│       └── pages/
│           ├── PublicPages.js (PrivacyPolicy, TermsOfService, RefundPolicy, ContactPage, SocialMediaPage)
│           ├── LandingPage.js, SignupPage.js
│           ├── Dashboard.js, CustomerCRM.js, InventoryAnalytics.js, Inventory.js
│           └── ... (other app pages)
```

## Key Technical Notes
- **App.css must be imported in App.js** — contains .data-table styling including sticky columns
- **Naive timestamps**: Always append 'Z' before `new Date()` in frontend
- **Accounting**: Opening = Closing + AllSales - AllPurchases; Inward display = Sundry Creditor purchases only
- **MongoDB**: Always exclude `_id` from responses
- **Public page routing**: `publicView` state in App.js controls which public page shows (landing, login, signup, privacy, terms, refund, contact, social)

## Upcoming Tasks
- P1: Compile Desktop Agent into one-click `.exe` installer (PyInstaller/Inno Setup)
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)

## Future/Backlog
- Salesman Order System (Enterprise): Login, customer mapping, order workflow, beat plans
- AI Expense Insights (GPT-5.2): Analyze Tally expense data for reduction suggestions
- P3: Refactor App.js (extract routing, auth, layout into separate modules)
