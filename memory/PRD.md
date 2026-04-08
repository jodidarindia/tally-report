# FLOWRA - Product Requirements Document

## Overview
**FLOWRA** — Organize. Automate. Accelerate.
SaaS web application connecting to TallyPrime for inventory and sales reports with AI analytics.

## Architecture (Refactored Apr 8, 2026)
```
/app/backend/
  server.py          (66 lines - app entrypoint, CORS, router inclusion)
  db.py              (shared MongoDB connection)
  utils.py           (safe_num, safe_str, FY utilities, compute_overdue_digest, SyncWebSocketManager)
  models.py          (Pydantic models)
  routes/
    auth.py          (8 endpoints: login, logout, me, change-password, reset-password, users CRUD)
    tally.py         (2 endpoints: connect, status)
    inventory.py     (8 endpoints: items, summary, PO generation, PO list, sales-frequency, movement, below-cost, pivot)
    sales.py         (4 endpoints: vouchers, voucher detail, summary, analytics)
    customers.py     (8 endpoints: outstanding, followups CRUD, targets, target-set, ledger export, payment-behavior)
    dashboard.py     (2 endpoints: reminders, overdue-digest)
    salesman.py      (5 endpoints: performance, performance-detailed, master CRUD)
    sync.py          (4 endpoints: agent/sync, sync-progress, ws/sync-status, sync/status)
    ai_reports.py    (5 endpoints: ai/query, ai/advanced-query, reports/export, reports/history, sales-frequency/export)
  services/          (tally_client, ai_service, enhanced_ai_service, export_service, auth_service, purchase_order_ai)
/app/frontend/       (React + Shadcn UI + Tailwind)
/app/desktop-agent/  (Python sync agent for TallyPrime)
```

## Stack
- Frontend: React, Shadcn UI, Tailwind, WebSockets
- Backend: FastAPI, Motor (Async MongoDB), PyJWT
- Desktop Agent: Python, HTTP sessions, 120s timeouts
- AI: GPT-5.2 via Emergent LLM Key

## Key Features
- JWT Role-Based Auth (admin/employee)
- Financial Year filtering across all endpoints
- Real-time sync via WebSocket + desktop agent
- Receipt/Payment voucher tracking
- Overdue Digest (55-day threshold, auto-recompute on sync)
- AI Purchase Orders, Advanced AI Queries
- Customer CRM (outstanding, aging FIFO, targets, payment behavior, followups)
- Salesman Performance (master mapping, item-wise breakdown)
- Export (Excel, PDF, CSV)

## DB Collections
users, sales_vouchers, inventory_items, customers, receipt_vouchers,
customer_targets, salesman_master, customer_followups, sync_status,
report_history, ai_queries, purchase_orders, overdue_digest, tally_connections

## Completed
- WebSocket Real-Time Sync
- Desktop agent overhaul (standard XML, receipts, batching)
- Fixed 9+12 CRM/outstanding/FY/filter bugs
- Docker Compose configuration
- Backend TypeError fix (safe_num/safe_str)
- Overdue Digest feature (55-day, receipt matching, dashboard widget)
- **P3 Refactor: server.py 2609 -> 66 lines, 9 route modules, 2 shared modules**

## Backlog
- (None currently — all priorities completed)
