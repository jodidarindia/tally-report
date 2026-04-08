# FLOWRA - Product Requirements Document

## Overview
**FLOWRA** — Organize. Automate. Accelerate.
SaaS-based web application connecting to TallyPrime for inventory and sales reports with AI-powered analytics.

## Brand Identity
- **Name**: FLOWRA
- **Tagline**: Organize. Automate. Accelerate.
- **Logo**: `/app/frontend/public/flowra-logo.png`
- **Color Scheme**: Primary Blue (#2563EB), Accent Purple (#7C3AED), Cyan (#06B6D4), Background (#F0F4FF)
- **Typography**: Outfit (headings), Work Sans (body)

## Architecture
- **Frontend**: React (Node 20), port 3000
- **Backend**: FastAPI + Motor (Async MongoDB), port 8001
- **Database**: MongoDB
- **Desktop Agent**: Python script connecting to local TallyPrime ODBC (port 9000)

## Core Features

### Authentication (JWT + Role-Based)
- Admin and Employee roles with JWT
- Default admin: admin/admin123
- Admin: create/delete employees, reset passwords
- Employee access: Sales, Inventory, CRM only

### Financial Year Filtering (Fixed Apr 2026)
- FY dropdown in navigation (April-March, Indian standard)
- ALL data endpoints accept `?fy=` parameter
- Sales, CRM, Targets, Analytics, Salesman pages re-fetch on FY change
- Default: current Indian FY on login
- `fy_to_date_range()`, `filter_vouchers_by_fy()`, `get_previous_fy()` utility functions

### Inventory Management
- Stock items with stock groups from Tally
- Stock group dropdown filter + Category filter + Search
- AI-powered Purchase Order generation

### Sales (Fixed Apr 2026)
- Sales vouchers with FY-based filtering
- Clickable voucher numbers open invoice detail modal (URL-decoded voucher_id with `:path` route)
- Sales trend chart, export (PDF/Excel/CSV with FLOWRA branding)

### Customer CRM (Fixed Apr 2026)
- **Outstanding**: Uses Tally closing balance as real outstanding (accounts for payments)
- **FIFO Aging**: Distributes outstanding across invoices oldest-first (0-30, 30-60, 60-90, 90+ days)
- **Paid Amount column**: Shows `total_sales - outstanding`
- Status: Normal / At Risk / Overdue / Critical (based on outstanding + oldest invoice)
- Groups + States available as filter dropdowns
- Follow-ups, Targets, Payment Behavior tabs all FY-filtered

### Payment Behavior (Fixed Apr 2026)
- Real metrics: paid_amount, payment_ratio, average_payment_delay (estimated from outstanding ratio)
- Credit score formula: 70% payment_ratio + volume_bonus - delay_penalty
- Payment pattern: excellent/regular/irregular/risky based on actual data
- No hardcoded mock values

### Targets (Fixed Apr 2026)
- Column 1: Previous FY sales (`get_previous_fy()`)
- Column 2: Target (custom or auto 15% growth)
- Column 3: Current FY achieved (from current FY vouchers)

### Salesman Performance (Fixed Apr 2026)
- Customer-to-salesman mapping from master data
- Performance, Item-wise Sales, Manage Salesmen tabs all functional
- FY-filtered sales data
- When no salesman master exists, shows "Unassigned"

### Analytics (Fixed Apr 2026)
- Movement Analysis: Case-insensitive item matching, includes items sold but not in inventory
- Below Cost Sales: FY-filtered
- Sales Frequency: FY-filtered
- Pivot Table: Working

### AI Reports (Fixed Apr 2026)
- GPT-5.2 via Emergent LLM Key
- Fixed collection reference (was `customer_outstanding`, now `customers`)
- Advanced query with filters, report types

### Desktop Sync Agent (v4 - Batch Mode)
- Monthly batch fetching for sales (prevents Tally from freezing)
- Configurable BATCH_SLEEP_SECONDS (default 3s)
- Real-time progress reporting to cloud backend via WebSocket
- Auto-start scripts: `run_agent.bat`, `start_with_tally.bat`

### WebSocket Real-Time Sync
- Backend: `/api/ws/sync-status` endpoint
- Frontend: SyncStatusBar + SyncConnectionBadge
- Live progress during desktop sync

## Key API Endpoints
- POST /api/auth/login
- GET /api/inventory/items, /api/inventory/summary
- GET /api/sales/vouchers?fy=, GET /api/sales/vouchers/{id:path}
- GET /api/sales/summary?fy=, /api/sales/analytics?fy=
- GET /api/customers/outstanding?fy=
- GET /api/customers/targets?fy=
- GET /api/customers/payment-behavior?fy=
- GET /api/salesman/performance?fy=, /api/salesman/performance-detailed?fy=
- GET /api/inventory/movement-analysis?fy=, /api/inventory/below-cost-sales?fy=
- GET /api/inventory/sales-frequency?fy=, /api/inventory/pivot-data
- POST /api/ai/advanced-query
- POST /api/agent/sync, /api/agent/sync-progress
- WebSocket /api/ws/sync-status

## Backlog
- P2: Multi-tenant support
- P2: Receipt/Payment voucher sync from Tally (for precise per-invoice aging)
