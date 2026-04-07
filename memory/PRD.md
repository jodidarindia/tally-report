# Tally Reports - Product Requirements Document

## Problem Statement
Build a SaaS-based web application that connects to a Tally database (Tally Prime local version) to prepare inventory and sales reports. Includes AI-based report builder, CRM, salesman performance tracking, inventory analytics, and a self-hosting deployment package.

## Architecture
- **Frontend**: React + Tailwind CSS + Recharts + Shadcn/UI
- **Backend**: FastAPI + Motor (Async MongoDB)
- **Database**: MongoDB
- **AI**: GPT-5.2 via Emergent LLM Key
- **Auth**: Email OTP via Resend (with dev mode bypass)
- **Desktop Agent**: Python script that syncs Tally data to the cloud

## Implemented Features (All Complete)

### Core
- [x] Dashboard with summary stats
- [x] Inventory management with search, filter, export (PDF/Excel/CSV)
- [x] Sales vouchers view with date filtering and analytics charts
- [x] Tally connection setup page

### AI Features
- [x] AI Report Builder (GPT-5.2) with natural language queries
- [x] Enhanced AI Reports with report type selection and filters
- [x] AI Purchase Order generation with priority classification
- [x] Report history tracking
- [x] Robust JSON parsing for markdown-wrapped GPT responses
- [x] Object-safe rendering of AI responses in UI

### CRM & Sales
- [x] Customer CRM with outstanding balances and aging analysis
- [x] Customer follow-ups (create, track, update status)
- [x] Customer targets and achievement tracking
- [x] Payment behavior analysis and credit scoring

### Salesman Management (NEW - Apr 7, 2026)
- [x] **Salesman Master CRUD** — Add/Edit/Delete salesman records
- [x] **Customer Mapping** — Map customers to salesmen via checkbox UI
- [x] **Target Setting** — Monthly and quarterly targets per salesman
- [x] **Performance Tracking** — Target vs achievement with chart and table
- [x] **Item-wise Sales Report** — Per-salesman item breakdown (qty, revenue, transactions)
- [x] **3 Tabs**: Performance | Item-wise Sales | Manage Salesmen

### Analytics
- [x] Inventory pivot tables (group by category, metric selection)
- [x] Sales frequency analysis (transaction count, unique customers)
- [x] **Sales Frequency Export** — XLS and PDF download (NEW - Apr 7, 2026)
- [x] Inventory movement analysis (fast/slow/dead-stock classification)
- [x] Below-cost sales identification

### Auth & Security
- [x] Email OTP authentication (Resend SDK)
- [x] Dev mode with static OTP (123456) for testing
- [x] Session management (create, verify, logout)

### Deployment & Sync
- [x] Desktop Sync Agent (Python) for pushing Tally data to cloud
- [x] Docker Compose self-hosting package
- [x] Deploy scripts (Linux/Mac + Windows)
- [x] Self-hosting guide documentation

## API Endpoints
### Auth
- `POST /api/auth/send-otp` | `POST /api/auth/verify-otp` | `POST /api/auth/verify-session` | `POST /api/auth/logout`

### Inventory
- `GET /api/inventory/items` | `GET /api/inventory/summary` | `POST /api/inventory/generate-purchase-order`
- `GET /api/inventory/movement-analysis` | `GET /api/inventory/below-cost-sales` | `GET /api/inventory/pivot-data`
- `GET /api/inventory/sales-frequency`

### Sales
- `GET /api/sales/vouchers` | `GET /api/sales/summary` | `GET /api/sales/analytics`

### AI
- `POST /api/ai/query` | `POST /api/ai/advanced-query`

### CRM
- `GET /api/customers/outstanding` | `GET/POST /api/customers/followups` | `GET /api/customers/targets` | `GET /api/customers/payment-behavior`

### Salesman (NEW)
- `GET /api/salesman/master` | `POST /api/salesman/master` | `DELETE /api/salesman/master/{name}`
- `GET /api/salesman/performance` | `GET /api/salesman/performance-detailed`

### Export
- `POST /api/reports/export` | `POST /api/analytics/sales-frequency/export` (excel/pdf)

### Sync
- `POST /api/agent/sync` | `GET /api/sync/status`

## Backlog
- P2: Real-time WebSocket sync between Desktop Agent and cloud
- P2: Multi-tenant support with organization management
- P3: WhatsApp/SMS OTP alternative
