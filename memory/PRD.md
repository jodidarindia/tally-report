# FLOWRA - Product Requirements Document

## Overview
**FLOWRA** — Organize. Automate. Accelerate.
SaaS-based web application connecting to TallyPrime for inventory and sales reports with AI-powered analytics.

## Architecture
- Frontend: React + Shadcn UI + Tailwind (port 3000)
- Backend: FastAPI + Motor (Async MongoDB) (port 8001)
- Desktop Agent: Python (connects to TallyPrime ODBC port 9000)
- Docker Compose for self-hosting

## Desktop Sync Agent v5 (Apr 2026)
- **Standard Tally report exports** (Day Book) instead of heavy TDL collections
- **HTTP keep-alive session** with connection pooling
- **120s timeout** with 2 retries per request (configurable via .env)
- **Receipt/Payment voucher sync** — captures Receipt, Payment, Contra, Journal from Day Book
- Monthly batch fetching with configurable sleep (BATCH_SLEEP_SECONDS)
- Real-time progress via WebSocket + HTTP to cloud backend
- Auto-start scripts: `run_agent.bat`, `start_with_tally.bat`

## Backend Receipt Handling
- POST /api/agent/sync accepts `data_type: "receipts"` -> stores in `receipt_vouchers` collection
- Outstanding calculation uses receipt data: `paid_amount` from actual receipts
- Payment behavior analysis uses receipt amounts + receipt dates
- Bill allocations from receipts tracked for per-invoice matching

## FY Filtering (Apr 2026)
- All data endpoints accept `?fy=` parameter
- `fy_to_date_range()`, `filter_vouchers_by_fy()`, `get_previous_fy()` utilities
- Frontend re-fetches on FY dropdown change
- safe_num() / safe_str() utilities handle None values from MongoDB

## Key API Endpoints
- POST /api/agent/sync (inventory, sales, customers, receipts)
- POST /api/agent/sync-progress, WebSocket /api/ws/sync-status
- GET /api/sales/vouchers?fy=, GET /api/sales/vouchers/{id:path}
- GET /api/customers/outstanding?fy= (with receipt-based paid_amount)
- GET /api/customers/targets?fy=, /api/customers/payment-behavior?fy=
- GET /api/salesman/performance-detailed?fy=
- GET /api/inventory/movement-analysis?fy=, /api/inventory/below-cost-sales?fy=
- POST /api/ai/advanced-query (GPT-5.2 via Emergent LLM Key)

## DB Collections
- users, sales_vouchers, inventory_items, customers
- receipt_vouchers, customer_targets, salesman_master
- customer_followups, sync_status, report_history

## Completed (Apr 8, 2026)
- WebSocket Real-Time Sync (Desktop + Backend + Frontend SyncStatusBar.js)
- Desktop script tally_sync_agent.py overhauled (standard XML, receipts, batching)
- Fixed 9 initial CRM/outstanding/voucher bugs
- Docker Compose configuration updated
- Fixed backend TypeError (safe_num/safe_str utilities) for None MongoDB values
- All 12 user-reported FY/filter/UI fixes verified (18/18 backend tests, 100% frontend)

## Backlog
- P3: Refactor server.py (2400+ lines) into /routes and /controllers
