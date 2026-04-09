# FLOWRA - Tally Prime Cloud Reports SaaS

## Original Problem Statement
Build a SaaS-based web application (FLOWRA) connecting to a local Tally Prime database to prepare inventory and sales reports. Features include JWT Auth, FY filtering, AI Purchase Orders, WebSockets for live sync, and an offline deployable Docker setup.

## Architecture
- Frontend: React + Shadcn UI
- Backend: FastAPI (modular routes in /app/backend/routes/)
- Database: MongoDB (Motor async)
- Desktop Agent: Python (tally_sync_agent_v6.py) - HTTP Collection XML requests to Tally Prime port 9000
- AI: OpenAI GPT-5.2 via Emergent LLM Key (Purchase Orders & Queries)

## Completed Features
- JWT Authentication (admin/admin123)
- FY-based filtering across all endpoints (12 filtering bugs fixed)
- Dashboard with Overdue Digest (>55 days)
- Inventory management with stock groups
- Sales vouchers with party/month filters, Sales Trend chart
- Customer CRM with outstanding tracking
- Receipt/Payment voucher tracking
- Salesman Performance reports
- AI Purchase Order generation
- WebSocket live sync updates
- PDF/Excel export
- Desktop Sync Agent v6 with:
  - Lightweight TDL Collection requests (no Tally freeze)
  - COMPUTE directives for closing balances
  - TALLYMESSAGE multi-voucher parsing
  - XML sanitization (& escaping, invalid character references)
  - Multi-FY sync (configured + current FY)
  - Incremental sync (after first full sync, only recent 2 months)
  - Upsert-based data sync (no data loss on re-sync)
  - BELONGSTO recursive customer fetch (sub-groups under Sundry Debtors)
  - FY auto-detect on frontend

## Pending/User Verification
- Desktop Agent v6: Stock item COMPUTE fields (CLBAL, CLRATE, CLVAL) — awaiting user test
- Desktop Agent v6: Incremental sync mode — awaiting user test

## Backlog
- P2: Multi-tenant support
