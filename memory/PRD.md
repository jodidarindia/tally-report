# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally Prime for business analytics, inventory management, CRM, and reporting.

## Domain
`www.flowralive.in`

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

## Recent Enhancements (Completed)
### Mobile Responsiveness (Apr 2026)
- All data tables horizontally scrollable on mobile (375px viewport)
- **Sticky/frozen first column** (Item Name / Customer Name) stays visible while scrolling
- Tab labels wrap into two lines on mobile for readability
- Filter controls, buttons, and forms stack vertically on small screens
- Responsive padding: 0.75rem mobile, 1rem desktop
- CSS: `border-collapse: separate` required for `position: sticky` on table cells

### Branch Exclusion (Apr 2026)
- Global `X-Exclude-Branches` header filtering internal transfers
- Applied to Dashboard, Analytics, CRM, and all report endpoints

### Inventory Movement Analysis Fix (Apr 2026)
- Opening stock = Closing + All Sales - All Purchases (accounting equation)
- Inward display column isolates Sundry Creditor purchases only

### Timestamp Fix (Apr 2026)
- Backend stores naive UTC timestamps; frontend appends 'Z' suffix before JS Date parsing
- All dates displayed in IST via `toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })`

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
│       ├── App.js (main layout, routing, auth, nav)
│       ├── App.css (.data-table styles, sticky columns, loading states)
│       ├── components/ (SearchableSelect, ui/)
│       └── pages/ (Dashboard, CustomerCRM, InventoryAnalytics, Inventory, TallySetup, etc.)
```

## Key Technical Notes
- **App.css must be imported in App.js** — contains .data-table styling including sticky columns
- **Naive timestamps**: Always append 'Z' before `new Date()` in frontend
- **Accounting**: Opening = Closing + AllSales - AllPurchases; Inward display = Sundry Creditor purchases only
- **MongoDB**: Always exclude `_id` from responses

## Upcoming Tasks
- P1: Compile Desktop Agent into one-click `.exe` installer (PyInstaller/Inno Setup)
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)

## Future/Backlog
- Salesman Order System (Enterprise): Login, customer mapping, order workflow, beat plans
- AI Expense Insights (GPT-5.2): Analyze Tally expense data for reduction suggestions
- P3: Refactor App.js (extract routing, auth, layout into separate modules)
