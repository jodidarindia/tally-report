# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database to prepare inventory and sales reports. Features: JWT Auth, FY filtering, AI Purchase Orders (GPT-5.2), WebSockets for live sync, CRM with customer outstanding/payment tracking, PDF ledger exports.

## Architecture
- **Frontend**: React + Shadcn UI
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT + WebSockets
- **Desktop Agent**: Python script syncing Tally Prime data via XML HTTP requests
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key

## What's Been Implemented
### Core Features (Complete)
- JWT Authentication with admin/staff roles, user management
- Multi-FY support with FY selector in navbar
- Dashboard with stat cards, overdue digest (55+ day threshold), top customers, recent transactions
- Inventory page with sortable columns, multi-select stock group filter, search, category filter
- Sales page with sortable columns, party/month filters, chart, export (PDF/Excel)
- CRM Outstanding tab with sortable columns, Opening Balance, aging buckets, Ledger PDF export
- CRM Payment Behavior (FY-independent): summary bar, credit notes, journal credits, score, pattern
- CRM Follow-ups and Targets tabs
- AI Reports (GPT-5.2 powered) with filters and sample queries
- AI Purchase Order generation
- Inventory Analytics: Movement Analysis (sortable), Below Cost Sales, Sales Frequency
- Sync History page
- Desktop Sync Agent v6: syncs Inventory, Sales, Receipts, Customers, Credit Notes, Journal Vouchers
- Tally-format PDF Ledger export with opening balance, voucher numbers, running balance
- WebSocket live sync status
- Copyright: Jodidar India footer

### Recent Changes (Apr 9, 2026)
- Fixed CRM Outstanding: added Opening Balance column, sortable columns
- Refactored Payment Behavior: FY-independent, summary bar with pattern counts, credit notes column
- Fixed Dashboard low stock: movement-based logic (172 vs 202 previously)
- Added sorting to Inventory, Sales, and Analytics tables
- Added multi-select checkbox dropdown for stock groups in Inventory
- Removed Pivot Table tab from Analytics
- Fixed Sales Frequency key mismatch (frequency vs sales_frequency)
- Fixed PDF Ledger export: now accepts opening_balance parameter
- Fixed Dashboard reminders API endpoint path

### Desktop Agent XML Sanitization (Complete)
- Handles invalid control characters via regex
- Handles Tally's `&#x4;` type numeric references
- Handles unescaped `&` in party names
- Two-pass parsing: standard → aggressive fallback

## Key API Endpoints
- `POST /api/auth/login` - JWT login
- `GET /api/inventory/summary` - Inventory stats with movement-based low stock
- `GET /api/inventory/items` - All inventory items
- `GET /api/inventory/sales-frequency` - Returns `frequency` array
- `GET /api/inventory/movement-analysis` - Movement analysis
- `GET /api/sales/vouchers` - Sales with filters
- `GET /api/sales/analytics` - Sales analytics
- `GET /api/customers/outstanding` - Outstanding with opening balance, aging
- `GET /api/customers/payment-behavior` - FY-independent payment behavior with summary
- `POST /api/customers/ledger/export` - Tally-format PDF ledger
- `GET /api/dashboard/overdue-digest` - Overdue invoice digest
- `GET /api/dashboard/reminders` - Follow-up reminders
- `POST /api/ai/advanced-query` - AI report generation

## Known Limitations
- Inventory valuation shows Rs.0 because Tally sync doesn't populate qty/price fields (data sync issue)
- WebSocket reconnection on initial page load (auto-reconnects)

## Pending Tasks
### P1 - Desktop Agent Incremental Sync
- Prevent redundant API upserts when Tally data hasn't changed
- Track last modified dates or hash checks

### P2 - Customer Payment Behaviour Analytics
- Add dropdown to show details for a selected customer (partially done)

### P2 - Desktop Agent Executable
- Compile into one-click installable .exe with UI/CLI for company/FY selection

### P3 - Multi-tenant Support

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL
- MongoDB
- OpenAI GPT-5.2 (Emergent LLM Key)
