# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB Atlas SaaS synced with Tally / Busy for business analytics, inventory, CRM, dispatch, salesman ordering, and CA reporting.

## Production Posture (Feb 2026, post iter99)
- **Hosting target**: DigitalOcean (Droplet 2GB) + MongoDB Atlas (Mumbai)
- **Atlas DBs**: `Flowra-Insights` (prod) / `Flowra-Insights-Dev` (Emergent sandbox)
- **Backend**: FastAPI behind nginx, /api/health probe live
- **Desktop agent**: v9.8.28-company-raw-parens, .exe published at `/FlowraTallyAgent.exe`

## Shipped — May 22 2026 (iteration 109) — v9.8.28 REVERT iter-107 over-escape (P0 regression)
**Field report** (Krishna Sales Corporation, live customer): agent log on v9.8.27 showed every Tally call failing with `Tally error: Could not set 'SVCurrentCompany' to 'Krishna Sales Corporation (from 1-Apr-24)'`. User explicitly noted: "the agent was getting correct company till version 9.8.25, why this error has started?".

**Root cause** (from comparing iter-105 → iter-107 diffs): iter-107 (v9.8.27) escaped `(` → `&#40;`, `)` → `&#41;`, `'` → `&apos;`, `"` → `&quot;` in `_company_tag()` on the assumption that Tally's TDL parser treated them as expression delimiters. Wrong direction. The reality is that Tally Prime 7.0's XML/TDL layer does NOT decode numeric character references (`&#40;`) or `&apos;`/`&quot;` back to literal chars when matching SVCURRENTCOMPANY against the loaded-company catalog. So `Krishna Sales Corporation &#40;from 1-Apr-24&#41;` was being compared LITERALLY against the actual company name `Krishna Sales Corporation (from 1-Apr-24)` and failing. v9.8.25 worked precisely because it sent raw parens (which are legal in XML element content).

**Fix** in `tally_sync_agent_v9.py:_company_tag()`: keep ONLY the three mandatory XML-element-content escapes — `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;` (every conformant XML parser including Tally's DOES decode these). Parens, single-quote, double-quote are sent RAW — they are legal inside XML element content per the spec and match v9.8.25's behaviour.

**Tests** (`test_iteration107_company_name_escape.py` rewritten): 9/9 pass — pins raw parens, raw single-quote, raw double-quote, mandatory escape of `&`/`<`/`>`, plus a regression guard that `<SVCURRENTCOMPANY>` is only emitted from `_company_tag()`.

**Version bumped**: `APP_VERSION=v9.8.28` (flowra_gui), `agent_version='9.8.28-company-raw-parens'` (4 sites in tally_sync_agent_v9), `backend/agent_release.json`, `frontend/public/agent-latest.json`.

**Total green suite: 62/62 across iter-100..108 (iter-107 grew from 8 → 9 tests).**

**User action**: rebuild Windows .exe from current source (clear `__pycache__` first), drop into `frontend/public/FlowraTallyAgent.exe`, update `sha256` + `size_bytes` in both manifests, push to droplet, restart uvicorn so manifest cache rebuilds.

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

## Shipped — May 22 2026 (iteration 108b) — Inner-banner version drift fix
**Bug** (caught by customer screenshot — full credit): The outer GUI showed v9.8.27 correctly in the title bar, but the inner `tally_sync_agent_v9.py` startup banner was still printing `FLOWRA TALLY SYNC AGENT v9.8.9-daybook-lvd` because two hardcoded string literals were never updated when `APP_VERSION` was bumped across iter 107.

The functional code WAS already at v9.8.27 — only the printed identification was stale. But this was misleading enough to mask real diagnostics ("am I actually running the fix or not?"). Fixed at lines 3346, 3347, 4729, 4730 of `tally_sync_agent_v9.py`. Customer rebuild + .exe re-upload required to take effect.

**Additionally**: confirmed via grep that `_company_tag()` is the ONLY place that emits `<SVCURRENTCOMPANY>` and the escape logic (parens, `&`, `<`, `>`, quotes) is correct. The customer's previous .exe was a stale build from before iter 107 — needs a fresh PyInstaller build with `__pycache__` cleared.

## Shipped — May 22 2026 (iteration 108) — AI Insights renderer fix
**Bug** (frontend-only): on the AI Insights page, asking "Show items with low stock that need immediate reordering" returned a perfectly correct LLM response, but the UI displayed each insight / recommendation as a raw JSON blob like `{"insight":"Zero immediate reorder triggers","detail":"Across all 35 inventory items...","risk":"..."}`. The LLM returns structured `{insight, detail, risk}` and `{priority, action, expected_impact}` objects inside the response arrays — the old code only handled string inputs and fell back to `JSON.stringify()`.

**Fix**:
- New shared module `frontend/src/components/AIInsightRenderers.jsx` exports `renderStructuredInsight`, `renderStructuredRecommendation`, `renderMetricValue`, `renderDetailedAnalysis`. Each gracefully handles strings, JSON-encoded strings, arrays of records, and the common LLM object shapes — emitting properly styled blocks (title + detail + risk pill, priority badge + action + impact, key-value tables for metric objects, nested sections for detailed_analysis).
- Both `EnhancedAIReports.js` AND `AIQueryBuilder.js` now import these renderers — no surface still calls `JSON.stringify()` as a fallback.
- Tests: `test_iteration108_ai_insights_render.py` — 6/6 pass (source-asserting tests that lock in the contract).

**Total green suite: 61/61 across iter 100-108.**

## Shipped — May 22 2026 (iteration 107) — v9.8.27 CRITICAL company-name escape
**Root cause (from customer agent log)**: Krishna Sales Corp's Tally company is named `Krishna Sales Corporation (from 1-Apr-24)`. The agent emitted that name **raw** into `<SVCURRENTCOMPANY>`. Tally's TDL parser treats raw `(` and `)` as expression delimiters → every company switch failed with `Could not set 'SVCurrentCompany'` → every voucher / AlterID / receipt query returned 0 results silently. Every single sync attempt for this customer (and any other with parens / `&` / `<` / `>` / quotes in the company name) was broken.

**Fix** in `tally_sync_agent_v9.py:_company_tag()`: HTML/XML-escape the company name before embedding in the XML envelope. Parens → `&#40;`/`&#41;`, ampersand → `&amp;`, etc. Standard XML entities for `<`, `>`, `"`, `'`. Round-trip-safe (Tally unescapes back to the original name).

**Tests** (`test_iteration107_company_name_escape.py`): 8/8 pass — covers the real customer name, ampersand, `<` / `>`, apostrophe, plain-name no-op, Default-Company fallback, round-trip safety, and a meta-test that asserts no other code path bypasses `_company_tag()`.

**Total green suite: 55/55 across iter 100-107.**

Version bumped: `APP_VERSION=v9.8.27`, `agent_version='9.8.27-alter-id'` (4 sites), both manifests.

## Shipped — May 22 2026 (iteration 106) — Dispatch kanban sort consistency
**Issue**: 
- "New" lane was client-side-sorted by digit-stripped `invoice_number` DESC, which mis-ranked multi-series shops (Krishna Sales' `CGSA2627/0013` outranked today's `KTG/0030/2526`). 
- All other lanes were sorted by `created_at` DESC on the backend → moving a card from New → Queued caused it to jump position relative to siblings.

**Fix**:
- `backend/routes/dispatch.py`: `GET /api/dispatch/cards` now sorts `(voucher_date DESC, voucher_id DESC, created_at DESC)` for every lane. `voucher_id` tiebreak uses Tally's running serial — highest serial of the day wins, predictable across multi-series shops.
- `frontend/src/pages/DispatchTerminal.js`: removed the special-case New-lane client-side sort; cards now render in backend order.
- Tests: `test_iteration106_dispatch_kanban_sort.py` — 5/5 pass (latest date wins, same-date voucher_id tiebreak, cross-lane consistency, multi-series predictability, legacy-card fallback).
- **47/47 tests pass across iter 100-106.**

## Shipped — May 22 2026 (iteration 105) — v9.8.26 AlterID Prime 7.0 hot-fix
**Root cause analysis (from a real ASA Autotech daybook XML the user uploaded)**: three distinct bugs blocked v9.8.25's "universal iteration" path on Tally Prime 7.0:
- Tally Prime 7.0 **lowercases every response tag**, so `<FlowraIterVchAID_F>` came back as `<flowraitervchaid_f>` — case-sensitive regex missed everything.
- Voucher collections in Tally Prime 7.0 return **EMPTY without SVFROMDATE/SVTODATE** static variables. v9.8.25 had no date variables.
- 1- and 2-digit AlterIDs were still being filtered upstream in some code paths.

**Fix (v9.8.26)** in `tally_sync_agent_v9.py`:
- Path-3 query now includes `<SVFROMDATE>20140401</SVFROMDATE><SVTODATE>20991231</SVTODATE>` (wide enough to capture every customer's books).
- All Path-3 regex matches now use `re.IGNORECASE`.
- INFO-level diagnostics report response size on each path's failure so the agent log clearly shows where things stand.
- **NEW Path-4 side-channel**: `_fetch_max_alter_id_from_cached_exports()` walks `debug_dir` for `<alterid>NUMBER</alterid>` across the 8 most recent XML files. Stream-scans in 2 MB chunks for memory safety. Guaranteed to work on every Tally build because Tally writes `<alterid>` on every voucher in every export.
- Version bumped: `APP_VERSION=v9.8.26`, `agent_version='9.8.26-alter-id'`, both manifests.

**Tests**: `test_iteration105_alterid_prime7_real_xml.py` — 8/8 pass, built against the **actual customer XML** (correctly extracts max AlterID = 12880 from the daybook). Total green suite: **42/42 across iter 100-105**.

## Shipped — May 22 2026 (iteration 104) — v9.8.25 AlterID robust detection
- **Root cause of v9.8.24 "still unsupported" report**: two distinct bugs
  1. Tally Prime 7.0 commonly returns blank/empty for `$$Max:Collection:CollName:$AlterID` SET expressions, so all aggregation paths silently failed.
  2. `_extract_text_deep` had `len(val) > 2` filtering which silently DISCARDED 1- and 2-digit AlterIDs, so even when Path-1 worked it'd mis-report "unsupported" on fresh installs.
- **Fix in `tally_sync_agent_v9.py`** (`fetch_last_alter_id` completely rewritten):
  - Path 1: `$$LastAlterIdMaster + $$LastAlterIdVouchers` system function.
  - Path 2: `$$Max:Collection` aggregation.
  - **Path 3 (NEW)**: universal client-side iteration — Tally is asked to REPEAT one line per object in the Voucher / Ledger collection emitting just `$AlterID`. Python `re.findall` grabs every integer and `max()`s. Uses only the most basic TDL primitives that work on every Tally build from Tally.ERP 9 → Prime 7.0.
  - New helpers `_first_int_in_raw()` + `_first_int_via_deep_walk()` accept 1- and 2-digit numbers (legacy length-guard bypassed).
  - **INFO-level logging** so the user can see from `agent.log` which path actually fired: `AlterID via Path-N (...) = …`.
- **Manifests bumped**: `APP_VERSION=v9.8.25`, `agent_version='9.8.25-alter-id'` (4 call sites), `backend/agent_release.json`, `frontend/public/agent-latest.json`.
- **Tests**: `test_iteration104_alterid_robust_detection.py` — 11/11 pass (covers length-guard bypass, iteration max, FCCFIELD fallback, truly-unsupported branch, sum vouchers+ledgers).
- **Total green suite**: 34/34 across iter 100-104.
- **User action**: rebuild Windows .exe from current source, drop into `frontend/public/FlowraTallyAgent.exe`, update `sha256` + `size_bytes` in both manifests, push to droplet.

## Shipped — May 21 2026 (iteration 103) — v9.8.24 agent + Sync Incomplete badge
- **Desktop agent v9.8.24** (`tally_sync_agent_v9.py`, `flowra_gui.py`):
  - POST timeout 30 s → **120 s** for `/api/agent/sync` and `/api/agent/reconcile` — fixes the read-timeout chain that left FY 25-26 with only 4 data types for Krishna Sales Corp.
  - `fetch_last_alter_id()` now has a 3-tier fallback chain: `$$LastAlterIdMaster + $$LastAlterIdVouchers` → MAX(`$AlterID`) on Voucher collection → MAX(`$Alterid`) on Ledger collection. Restores true incremental sync on Tally Prime 7.0 (Krishna Sales' install).
  - Per-cycle failure tracker: every `sync_to_backend` failure appends `{phase, reason, count}` to `self._failed_phases`, posted at cycle end via new `/api/agent/cycle-summary` endpoint.
  - Version bump everywhere: `APP_VERSION = v9.8.24`, `agent_version = 9.8.24-alter-id`, `backend/agent_release.json`, `frontend/public/agent-latest.json`.
- **Backend** (`routes/sync.py`):
  - New `POST /api/agent/cycle-summary` (HMAC `sync_token` auth, tenant-scoped).
  - `GET /api/sync/history` now joins `sync_cycle_summaries` and exposes `had_errors` + `failed_phases` per cycle.
  - Rolling cap of 200 summaries per (tenant, company) to keep collection bounded.
- **Frontend Sync History** (`SyncHistory.js`):
  - Red **"SYNC INCOMPLETE"** badge appears next to a cycle's mode pill when any phase failed.
  - Cycle card border turns red with a soft red ring for instant scanability.
  - Expanded view shows the list of failed phases with their reasons + a hint that re-syncing will skip already-successful types via hash match.
- **Frontend Setup page** (`TallySetup.js`):
  - Download .exe button now opens a confirmation modal explaining the 3 critical steps:
    (1) quit running agent → (2) save new .exe over old one (Replace) → (3) double-click to launch with preserved settings.
  - Prevents the two-versions-side-by-side situation the user reported.
- **Tests**: `test_iteration103_cycle_summary.py` (4/4) — endpoint persists payload, rejects bad sync_token, requires tenant, and the history endpoint correctly surfaces `had_errors` + `failed_phases`. **All 23 tests across iter 100–103 pass green.**
- **Next step for the user**: rebuild the Windows .exe with the bumped source (`pyinstaller` on the existing build kit), drop the new file into `frontend/public/FlowraTallyAgent.exe` and update `sha256` / `size_bytes` in `agent-latest.json`.

## Shipped — May 21 2026 (this session)
### Bugfix — Sync History header showed another tenant's agent version
- `GET /api/tally/status` previously did `find_one({type:'agent_sync'})` with NO tenant filter — leaked an old `9.8.7-aliases-perf` row from another shop onto every customer's Sync History header.
- Fix in `backend/routes/tally.py`: tenant_id is taken from the JWT, company_id from `X-Company-ID` header. Without a tenant ⇒ no row returned. Falls back to the latest sync row under the same tenant when the specific company has none. Tests: `backend/tests/test_iteration102_tally_status_tenant_scoped.py` — 5/5 pass.

### Bugfix — Dispatch Terminal card UX
- Invoice cards now show the **invoice date** (eg "15 Apr") next to the invoice number.
- "Unassigned" relabelled to "No employee assigned" with explanatory tooltip; rendered in amber so it stands out (signals dispatch ops to allocate someone).
- File: `frontend/src/pages/DispatchTerminal.js`.

### Bugfix — Dashboard "Recent Transactions" ordering (iteration 101)
- See earlier entry. 5/5 tests pass.

## Shipped — May 19 2026 (this session)
### Bugfix — Pages stale after switching company
- `App.js` now passes `key={`pg-${selectedCompany || 'none'}`}` to `<PageRenderer>`. Switching companies via the navbar forces a remount of the active page → mount-time `useEffect`s re-fire with the updated `X-Company-ID` axios header. Tenant isolation (JWT) untouched. Filters/pagination intentionally reset on switch because they are company-scoped.
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
