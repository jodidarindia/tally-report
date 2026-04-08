# FLOWRA - Product Requirements Document

## Overview
**FLOWRA** — Organize. Automate. Accelerate.
SaaS web application connecting to TallyPrime for inventory and sales reports with AI analytics.

## Architecture
```
/app/backend/
  server.py          (slim entrypoint: CORS, router inclusion)
  db.py, utils.py    (shared modules)
  routes/            (auth, tally, inventory, sales, customers, dashboard, salesman, sync, ai_reports)
  services/          (tally_client, ai_service, enhanced_ai_service, export_service, auth_service, purchase_order_ai)
/app/frontend/       (React + Shadcn UI + Tailwind)
/app/desktop-agent/
  tally_sync_agent_v6.py  (v6: Lightweight Collection Requests, No Freeze)
  tally_sync_agent.py     (v5: HTTP Day Book, legacy backup)
```

## Desktop Agent v6 — Lightweight Collection Requests (Apr 8, 2026)
**Problem**: Tally Prime is single-threaded; heavy Day Book report requests (v5) freeze the UI for 30-120 sec.
**Solution**: Use Tally's Collection-type XML requests instead of Report requests.

**Why it doesn't freeze**:
- Collection requests fetch specific data types (stock items, ledgers, vouchers by month)
- Each request: 1-5 seconds vs 30-120 seconds for report requests
- 2-second configurable gap between requests
- Monthly batching for sales/receipts

**Data flow** (every 20 min):
1. Agent sends Collection XML request to Tally port 9000 (~1-5 sec)
2. Parse XML response
3. Cache to local JSON file (export_cache/*.json) — overwritten each cycle
4. POST to cloud backend (/api/agent/sync)
5. Dashboard updated via WebSocket

**Phases per cycle**:
- Phase 1: Stock Items (1 request, ~1-2 sec)
- Phase 2: Sales Vouchers (1 request per month in FY, ~2-5 sec each)
- Phase 3: Receipt/Payment Vouchers (1 request per month, ~2-5 sec each)
- Phase 4: Customer Ledgers (1 request, ~1-2 sec)

**Config** (.env):
- SYNC_INTERVAL_MINUTES=20
- REQUEST_TIMEOUT=15
- SLEEP_BETWEEN_REQUESTS=2
- TALLY_HOST=localhost, TALLY_PORT=9000

## Key Features
- JWT Role-Based Auth, FY filtering, Real-time sync (WebSocket)
- Receipt/Payment voucher tracking, Overdue Digest (55-day threshold)
- AI Purchase Orders (GPT-5.2), Customer CRM, Salesman Performance
- Export (Excel, PDF, CSV)

## Completed
- WebSocket Real-Time Sync
- Desktop agent v5 (HTTP Day Book — legacy)
- Fixed 21 CRM/outstanding/FY/filter bugs
- Docker Compose, Backend TypeError fix
- Overdue Digest feature, P3 Refactor (server.py → route modules)
- **Desktop Agent v6: Lightweight Collection Requests (no freeze)**

## Backlog
- (None currently)
