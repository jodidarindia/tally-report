# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB Atlas SaaS synced with Tally / Busy for business analytics, inventory, CRM, dispatch, salesman ordering, and CA reporting.

## Production Posture (Feb 2026, post iter99)
- **Hosting target**: DigitalOcean (Droplet 2GB) + MongoDB Atlas (Mumbai)
- **Atlas DBs**: `Flowra-Insights` (prod) / `Flowra-Insights-Dev` (Emergent sandbox)
- **Backend**: FastAPI behind nginx, /api/health probe live
- **Desktop agent**: v9.8.20-secure-sync, .exe published at `/FlowraTallyAgent.exe`

## Iteration 99 — Security & Tenant-Isolation Audit (Feb 2026)
### Security hardening (production blockers)
- **HARD-ENFORCE** `sync_token` on `/api/agent/sync`, `/api/agent/reconcile`, `/api/agent/commands` GET.
- **SOFT-ENFORCE** (env-gated `STRICT_AGENT_AUTH=true`) on `/api/agent/sync-progress` and `/api/agent/commands/ack` — keeps in-field v9.8.19 agents working during the 24-h rollout window.
- `tenant_id` is now mandatory on `/agent/sync`; the old "first admin in DB" fallback removed (cross-tenant injection vector closed).
- `JWT_SECRET` now fail-fasts at startup if missing.
- WebSocket `/ws/sync-status` rejects subscribe without valid `sync_token` when strict mode is on.

### Salesman RBAC fix (iter98 HIGH → iter99 RESOLVED)
- New `_salesman_customer_filter(ctx)` helper in `routes/customers.py` returns the mapped customer list for the salesman; otherwise returns None.
- Chained on: `GET /customers/outstanding`, `/followups`, `/targets`, `/payment-behavior`, and `POST /customers/ledger/export`.
- Verified: salesman `ravi@test.com` sees 1 mapped customer (was 83). Admin still sees full 37-row tenant.
- Regression: `/app/backend/tests/test_iteration99_salesman_rbac.py` (20/20 PASS).

### Agent auto-update (v9.8.20)
- New `GET /api/agent/latest-version` and `GET /api/agent/check-update?current=X` (public, read-only, no DB writes).
- Source manifest: `/app/backend/agent_release.json` (mirrored to `/app/frontend/public/agent-latest.json`).
- Frontend Setup page (`TallySetup.js`) polls every 24 h; shows amber "update available" pill on the agent-version row and a banner on the download card.
- Desktop GUI (`flowra_gui.py` v9.8.20) checks on startup + every 24 h. When a new release is found:
  1. Reveals a flashing amber/red "Update Available" button on the bottom action bar.
  2. On click: stops the sync subprocess, downloads the new `.exe` (size guard ≥ 5 MB), writes an updater `.bat` that waits for PID exit → backs up old `.exe` to `.bak` → moves new `.exe` → relaunches → self-deletes.
- Safe by construction: never touches MongoDB on the server or Tally on the customer machine. `.bak` preserved for rollback.

### Verified by tests / curl
- /api/agent/sync without token → 'sync_token is required'
- /api/agent/sync without tenant_id → 'tenant_id is required'
- /api/agent/sync with valid HMAC token → 200 + 'Successfully synced 0 items'
- /api/agent/reconcile without token → 'sync_token is required'
- /api/agent/commands GET without token → 'sync_token is required'
- /api/agent/latest-version returns v9.8.20 manifest

## Shipped — May 19 2026 (this session)
### Email — Global Admin CC + FLOWRA Insights branding
- Added `GLOBAL_ADMIN_CC = "jodidarindiaoffice@gmail.com"` in `services/email_service.py`. All non-sensitive admin/business emails carry it.
- New helpers: `send_lead_signup_notification`, `send_lead_demo_requested_notification`, `send_lead_requirements_notification` — TO=`support@flowralive.in`, CC=global admin, Insights-branded HTML.
- Wired into `routes/prospects.py` for `/api/public/signup`, `/api/public/demo-request`, `/api/public/submit-requirements` as fire-and-forget tasks.
- Existing emails updated:
  - `send_subscription_renewed` → Insights subject + global CC
  - `send_subscription_expiry_warning` → Insights subject + global CC
  - `send_employee_created_to_admin` → Insights subject + global CC
  - `send_subscription_started`, `send_employee_created_to_employee` → NO CC (contain credentials)
- Email template now embeds the FLOWRA logo (`https://flowralive.in/assets/flowra-logo.png`) and an "FLOWRA INSIGHTS" sub-band when `insights=True`.
- De-duplication guard: CC is auto-dropped when it would equal the TO address.
- Tests: `backend/tests/test_iteration100_email_cc_and_insights.py` — 9/9 passing (monkeypatch on `resend.Emails.send`, no real network calls).

## Already shipped (April–May 2026)
- MongoDB Atlas migration + DB isolation (Prod vs Dev)
- Demo Account seeding (`demo@flowralive.in`)
- Tally Sync Agent v9.8.x line with visual GUI, subscription card, system tray, multi-company picker
- CA Corner Tally-parity (Balance Sheet + P&L)
- Beat Run Today / Beat Plans
- Salesman Dashboard + Order System
- Dispatch Terminal
- Inventory A/B/C/D categorisation + Auto-ABC + Sale Price column
- SuperAdmin: Backups (Tier-1) + Customer Health module-coverage
- DPDP-compliant tenant Data Export
- Marketing landing site
- Brand kit + DPDP legal templates
- Complete documentation + DigitalOcean deploy guide (PDF + Markdown)

## Outstanding Backlog
- P1: WhatsApp Automation (AiSensy + Meta Lead Ads OR Direct Meta Cloud API)
- P1: GST Portal integration (manual GSTR JSON upload + reconciliation)
- P2: Busy Agent v1.1 parity (`standard_price` + per-line DR/CR direction)
- P2: Export Audit Logs to CSV
- P2: "Sync Health" weekly email digest to admins
- P2: Move Salesman recommendation calc to background job
- P3: Video Engagement Tracking endpoint
- P3: Regenerate Sora 2 Lead-Enquiry Video (blocked: Emergent key budget)

## Database Strategy
See `/app/memory/DATABASE_STRATEGY.md`. Tier-1 dumps live; Tier-2 Atlas PITR available on M10.

## Test Reports
- `/app/test_reports/iteration_98.json` — initial security audit (22/24 pass, 1 HIGH finding)
- `/app/test_reports/iteration_99.json` — RBAC fix retest (20/20 pass; HIGH resolved)
- `/app/test_reports/iteration_97.json` — Atlas cut-over regression (19/19 pass)
