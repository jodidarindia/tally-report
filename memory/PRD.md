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
    auth.py, tally.py, inventory.py, sales.py, customers.py,
    dashboard.py, salesman.py, sync.py, ai_reports.py
  services/          (tally_client, ai_service, enhanced_ai_service, export_service, auth_service, purchase_order_ai)
/app/frontend/       (React + Shadcn UI + Tailwind)
/app/desktop-agent/
  tally_sync_agent_v6.py  (NEW: File-based, zero-freeze)
  tally_sync_agent.py     (v5: HTTP-based, legacy)
  flowra_export.tdl       (NEW: TDL for TallyPrime auto-export)
  run_agent.bat, schedule_export.bat
  QUICK_START.txt
```

## Stack
- Frontend: React, Shadcn UI, Tailwind, WebSockets
- Backend: FastAPI, Motor (Async MongoDB), PyJWT
- Desktop Agent v6: Python, file-based (watchdog), zero HTTP to Tally
- AI: GPT-5.2 via Emergent LLM Key

## Desktop Agent v6 — File-Based (Apr 8, 2026)
**Problem**: Tally Prime is single-threaded; any HTTP request freezes the UI.
**Solution**: TDL-based file export + file watcher agent.

**How it works**:
1. `flowra_export.tdl` loaded in TallyPrime adds "FLOWRA Auto Export" to Gateway menu
2. User presses 'F' (or schedules via Task Scheduler) → Tally exports XML files to `C:\FlowraExport\`
3. `tally_sync_agent_v6.py` watches that folder using `watchdog`
4. When files change, agent parses XML → syncs to cloud backend via POST /api/agent/sync
5. Zero HTTP requests to Tally = Zero freezing

**Exported files**: stock_items.xml, sales_vouchers.xml, receipt_vouchers.xml, customers.xml
**Dependencies**: requests, xmltodict, python-dotenv, schedule, watchdog, websockets

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
- Desktop agent v5 (HTTP-based, standard XML, receipts, batching)
- Fixed 9+12 CRM/outstanding/FY/filter bugs
- Docker Compose configuration
- Backend TypeError fix (safe_num/safe_str)
- Overdue Digest feature (55-day, receipt matching, dashboard widget)
- P3 Refactor: server.py 2609 → 66 lines, 9 route modules
- **Desktop Agent v6: File-based sync with TDL auto-export (zero freeze)**

## Backlog
- (None currently — all priorities completed)
