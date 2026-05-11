# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally for business analytics, inventory, CRM, dispatch, salesman ordering, and CA reporting.

## Latest Release Notes — Feb 2026
- **Demo Account for Prospect Demos** (`/app/backend/scripts/seed_demo_account.py`):
  - Single login `demo@flowralive.in` / `demo2026` (admin role, 24-month subscription).
  - 3 companies pre-loaded under one user — Sharma Lubricants (FMCG/auto trading),
    Bharat Electricals (electrical/hardware), Krishna Textiles (garments).
  - Each company has 35 inventory items, 12-16 customers, 3-5 salesmen + login users,
    70 sales vouchers, ~30 receipts, 20 purchase/expense vouchers, 10 dispatch cards
    spread over the last 10 months with relative dates (so dashboards stay fresh).
  - Idempotent — re-run any time with `python3 backend/scripts/seed_demo_account.py`.
  - Total seeded revenue across companies: ~₹68L; 12 demo salesman logins included.
- **Tally Sync Agent v9.8.9-daybook-lvd** (`/app/desktop-agent/tally_sync_agent_v9.py`,
  also at `/app/frontend/public/flowra-desktop-agent.py`):
  - `fetch_last_voucher_date()` now falls back to a Day-Book scan over the last
    730 days when `$$LastVoucherDate` returns empty.
  - Improved debug logging — separate messages for empty TDL vs failed Day-Book scan
    so users can see *why* "defaulting to today" fired.
- **Flowra Staff (`flowra_staff` role)** — SuperAdmin can delegate
  command-center access through a checkbox-gated employee account:
  - Tabs that can be granted: overview, subscriptions, payments, invoices,
    prospects, health, admins (view-only), renewals, referrals, questionnaires,
    backups, activity.
  - Endpoints: `GET/POST /api/super-admin/staff`,
    `PUT /api/super-admin/staff/{u}/features`,
    `PUT /api/super-admin/staff/{u}/toggle-active`,
    `POST /api/super-admin/staff/{u}/reset-password`,
    `DELETE /api/super-admin/staff/{u}`.
  - Regression: `/app/backend/tests/test_iteration90_staff_and_v989.py` (4/4 passing).

## CA Corner (Enhanced — April 2026)
- **Cash Flow**: Tally indirect method (Operating/Investing/Financing activities)
- **P&L Report**: Annual view with income/expense summaries
- **Balance Sheet** (NEW): Assets vs Liabilities + Capital, grouped by parent_group with expandable ledger drill-down
- **Ledger Drill-Down** (NEW): Income/Expense toggle, grouped by parent with per-ledger percentage bars
- **AI Expense Insights**: GPT-powered expense analysis and cost reduction suggestions
- Data sources: `all_ledgers`, `profit_loss`, `bank_cash_ledgers` collections (synced by Desktop Agent v9)

## Salesman Order System (Complete)
- Salesman role, auto-discovery in Manage Salesmen, customer mapping, product catalog
- Order lifecycle: Pending → Approved/Rejected/Hold → Billed (with invoice number)
- Pending Billing tab in Dispatch, billed order verification vs Tally invoice

## Dispatch Terminal (Complete)
- Kanban Board, Date-based Card Creation, Porter/Transporter Settlement
- Document Uploads, Close of Day PDF, Online Orders tab

## Landing Page
- Dispatch Terminal, Salesman Orders, CA Corner feature cards with NEW badges
- Enterprise plan updated with Dispatch and Salesman features

## Upcoming
- P0: Ship `.exe` installer for Busy Agent (validate on a real Windows + Busy install with customer data)
- P1: Compile Desktop Agent v9 (Tally) to `.exe`
- P1: GST Portal integration (manual GSTR JSON upload + reconciliation in CA Corner)
- P1: WhatsApp Automation (overdue payment reminders) — BLOCKED on user (AiSensy vs Meta Cloud API)
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (Resend email + WhatsApp)
- P2: "Sync Health" weekly email digest to admins
- P2: MongoDB Atlas migration (Tier-2 — point-in-time recovery on top of today's Tier-1 dumps)
- P2: Busy Agent v1.1 parity catch-up with Tally v9.6:
  - Populate `standard_price` from Busy's Sale Rate master (currently only `price` from `Master1.D1`)
  - Capture per-line DR/CR direction (`is_debit` / `dr_or_cr`) on `ledger_entries` so CA Corner Adjustment column + CN-reversal honouring work for Busy customers
  - Bump `agent_version` to `1.1.0-parity` and re-serve at `/flowra-busy-agent.py`
  - Regression test file: `/app/backend/tests/test_busy_agent_parity.py`

## Desktop Sync Agents
- **Tally (v9)** — `/app/desktop-agent/tally_sync_agent_v9.py` (mature, production)
- **Busy (v1)** — `/app/desktop-agent/flowra_busy_agent_v1.py` (Feb 2026)
  - Light-themed tkinter GUI, `pyodbc` cursor streaming from `.bds` (MS Access Jet 4.0)
  - Chunked uploads (500/chunk), generator extraction, gc.collect() per phase
  - Login + FY dropdown + company picker + Full Sync + Quick Sales Sync
  - Sync progress events mirror Tally v9 (sync_started, phase_start, phase_complete, sync_complete/error)
  - Validated end-to-end against `/api/agent/sync`, `/api/agent/reconcile`, `/api/agent/commands*`, `/api/agent/sync-progress`
  - Docs: `/app/desktop-agent/BUSY_README.md`

## Onboarding Tour (Refreshed — Apr 2026)
- 19-step interactive tour covering every menu and feature control
- Covers NEW: Salesman Orders, Dispatch Terminal, CA Corner, AI Reports, Insider Result, Sync History, Activity Feed
- Auto-filters steps whose DOM targets don't exist (handles feature gating per plan)
- "NEW" badge displayed on tooltip for recently-added features
- "Replay Tour" button added to user dropdown menu for rewatching anytime

## UI Polish (Apr 2026)
- `<AgentBadge>` component (`/app/frontend/src/components/AgentBadge.js`) — Tally = blue, Busy = amber
- Rendered in Sync History header + per-cycle detail, and in Company Selector modal

## Suite Architecture (Decided April 2026)

### Domain layout
- **flowralive.in** — static marketing landing page (`/app/marketing/`)
- **insights.flowralive.in** — current FLOWRA Insights SaaS (Tally/Busy)
- **tasks.flowralive.in** — future Tasks app (existing code from another platform — to be brought in)
- **loyalty.flowralive.in** — future Loyalty app (existing code from another platform — to be brought in)
- **api-X.flowralive.in** — per-app FastAPI backends

### Federation, NOT integration
- Each app: own DB, own users, own admin/superadmin, own subscription
- Shared: brand kit (`@flowra/brand-kit`), security baseline, design tokens, legal templates
- No SSO; users log in independently to each tool

### Hosting plan
- Marketing landing → Cloudflare Pages (FREE)
- React frontends → Vercel/Cloudflare Pages (FREE per app)
- FastAPI backends → single DO Droplet 2GB (~₹900/mo, all 3 backends via nginx vhosts)
- Database → MongoDB Atlas M10 Mumbai (~₹1,800/mo, separate db names per app)
- **Total ~₹2,700/mo for full suite**

## Brand Kit (`/app/brand-kit/`)
- `tokens.css` — CSS variables (colors, fonts, spacing, radius, shadows, motion)
- `tailwind-preset.js` — Tailwind config preset for any FLOWRA app
- `docs/security-checklist.md` — mandatory security baseline (35+ items)
- `docs/design-principles.md` — design rules, anti-patterns, voice guidelines
- `legal/` — privacy + terms templates (DPDP Act 2023 ready)
- `components/` — shared React components (to be built when first integrated)

## Marketing Site (`/app/marketing/`)
- `index.html` — single-file static landing (~30 KB, Tailwind CDN, premium dark aesthetic)
- Hero with gradient mesh + grain texture + animated rise-in sections
- 4-card tool grid (Insights LIVE, Tasks coming, Loyalty coming, future placeholder)
- "Why FLOWRA" 3-column trust strip
- "Our Approach" asymmetric two-column with numbered principles
- Footer with all tool links, company links, legal links, status indicator
- `vercel.json` + `_headers` + `_redirects` configured for security headers + tool subdomain redirects
- Deploy-ready for Cloudflare Pages, Vercel, or DO App Platform Static
- Smoke-tested: HTTP 200, all assets load, Lighthouse-ready

## Database Strategy
See `/app/memory/DATABASE_STRATEGY.md` for the full plan (current state, Atlas migration target, 3-tier backup plan, DO vs Atlas comparison).

## Changelog — Feb 2026 (CRM Stability)
- Fixed `customers.py` UndefinedName crash, hoisted `SortTh` in `CustomerCRM.js`, added sticky-header wrappers
- **CRM Outstanding rewrite:** Source of truth = `customers` collection; removed creditor leak (Epsilon Petrochem) and group-name filter false-negatives
- **Dashboard Overdue digest:** Skip parties with `customers.outstanding_amount ≤ 0`
- **OB anchor fix:** Anchored against today's calendar FY (Tally master OB = today's open FY due to auto-roll)
- **Payment-voucher classification fix:** Tally agent stores payment vouchers (DR party) in `receipt_vouchers` with `voucher_type='payment'`. API now splits the collection and treats payments as DR-side activity (sales math) instead of CR
- **Adjustment column added** to Outstanding tab — separates pure sales (`sales_only`) from non-sales DR (`adjustment_dr` = payment vouchers + JV debits like interest charges). Validated against user's Tally export: Indian Sales FY 26-27 shows Sales=₹0, Adjustment=₹85,293 (76,076 cheque-bounce payment + 9,217 interest JV) — exactly matching Tally
- **CRM Outstanding column overlap fix:** Customer Name cell now has `min-width:220px max-width:260px`, `whitespace-normal break-words`, and the Tally Verified badge sits below the name (not inline) — no more clipping into the Group column
- **Tally Verified ✓ green badge** added next to customer name when computed OS reconciles to Tally's master CB. Now works for **both today's FY (vs `outstanding_amount`) AND previous FY (vs `opening_balance` = closing of prev FY by accounting identity)**. FY 25-26: 37/37 badges; FY 26-27: 25/26 badges (1 outlier from CN-reversal data not yet synced)
- **Adjustment column** in Outstanding tab: Sales = sales-vouchers only; Adjustment = payment vouchers + JV debits + CN reversals (when ledger_entries.is_debit=true on CN party-row). Indian Sales FY 26-27: Sales=₹0, Adjustment=₹85,293 (76,076 cheque-bounce + 9,217 interest) — exact match to Tally
- **CN reversal honoring** — when a Credit Note's party ledger-entry is `is_debit=True` (post-agent-v9.1 sync), it's treated as a DR-side adjustment (subtracts from CR, adds to adjustment_dr). User-reported Saanvi case (3075+4090) will auto-resolve after the next desktop-agent re-sync
- **Tally Sync Agent v9.1.0-jv-direction:**
  - Added missing `_safe_float` method (was crashing fallback ledger fetch)
  - Fixed `income_count`/`expense_count` undefined error at end of sync
  - **Per-line DR/CR direction now captured in `ledger_entries`** using `ISDEEMEDPOSITIVE` attribute + signed AMOUNT fallback. Each entry now has `is_debit: bool` and `dr_or_cr: 'Dr'/'Cr'` fields. Backend `get_jv_party_amount()` already honors these (priority 1) — next user sync will close the remaining 5 OB mismatches automatically
  - Added `_signed_num()` helper that preserves sign (the old `_num()` always returned `abs()`, which broke JV debit detection)
  - Bumped `agent_version` to `9.1.0-jv-direction`
- **Insider Result fixes:** Lifecycle StatCards clickable to filter; dropdown shows counts; defensive guards on Forecast/SPIP/Concentration tabs; verbose error logging

## Changelog — May 2026 (Landing Page + Lead-Enquiry Refresh)

### Public-facing pages — full Tally + Busy parity messaging
- **LandingPage.js**:
  - Hero kicker: `Tally* Analytics Platform` → `Tally* + Busy* Analytics Platform`
  - Headline: `Tally* Data` → `Tally* / Busy* Data`
  - Subline rewritten to mention A/B/C/D Pareto, beat plans, dispatch terminal
  - 9 Feature cards (was 8): added **Backups & DPDP Data Export** card; Inventory now shows A/B/C/D + Auto-ABC; Salesman+Beat Plans card; CA Corner promotes Tally/Busy parity to-the-rupee
  - 3 NEW badges (Inventory, Salesman, Backups)
  - Pricing tiers refreshed:
    - Starter adds Tally*/Busy* sync + Daily Backups
    - Professional adds A/B/C/D Pareto + DPDP Export
    - Enterprise adds Beat Plans + Salesman Dashboard + Tally/Busy Parity
  - Footer trademark line: "Tally* and Busy* are trademarks of their respective owners…"
- **QuestionnaireForm.js**:
  - Step title `Tally* Usage` → `Tally* / Busy* Usage`
  - Version dropdown adds Busy 21/22, Busy 18/17, "Both Tally and Busy"
  - Decision factors mention "Integration with Tally* / Busy* without changes"
- **SignupPage.js** demo mockup: nav adds `Beat Plan` tab, 4 KPIs updated to A-Items%, Beat Coverage, Outstanding; sync line "Tally* + Busy* connected"; Pro plan features list refreshed (A/B/C/D, Beat Plan + Beat Run, Daily Backups)

### Lead-enquiry Thank You page now plays the demo video
- Previously the post-submit page was a static Check-icon card. Now embeds the existing `/flowra-demo.mp4` autoplay+loop+muted in a 16:9 frame with a "FLOWRA · 30-second tour" badge.
- Adds two CTAs: "Back to Home" and "See What's New (PDF)" linking to `/FLOWRA_Whats_New.pdf`.
- File `flowra-demo.mp4` was previously orphaned in `/public` with NO frontend reference — wired up.

### Sora 2 video regeneration — BLOCKED 🚫
- `generate_video.py` updated with new May-2026 prompt (4-sec, 1280x720, FLOWRA branding, A/B/C/D pills, Tally + Busy synced badge).
- `EMERGENT_LLM_KEY` budget exhausted on first 12-sec attempt — second 4-sec attempt returned `insufficient_balance`.
- **Action required**: top up the universal key (Profile → Universal Key → Add Balance) then run `cd /app/backend && python3 generate_video.py` to swap in the fresh video.

### Tests
- `test_iteration66_landing_parity.py` — 4/4 PASS (landing serves; demo video > 100 KB; What's New PDF served; JS bundle mentions all 5 expected feature strings)

## Changelog — May 2026 (SuperAdmin parity catch-up)

### SuperAdmin pages — feature parity with modern UserAdmin
- **Bug fix — Customer Health "0 emp"** when a tenant only has salesman/dispatch users (no legacy `role:employee` users). Root cause: 4 endpoints were filtering by `role:"employee"` only — a stale assumption. Multi-role tenants (salesman + dispatch + employee) showed phantom 0 counts.
- Fixed in `routes/seller_panel.py` (`/customer-health`) + `routes/super_admin.py` (`/admins`, `/stats`, `/admins/{username}` delete-archive).
- **Critical**: admin-deletion archiver was orphaning dispatch + salesman users. Now archives & deletes ALL non-admin roles.
- **Customer Health table** now exposes per-module counts: purchase_vouchers, receipts, credit_notes, beat_runs, salesman_orders, dispatch_cards. Also shows staff_breakdown (`5 (3 sm · 2 dp)` style) and the desktop agent version each tenant last connected with.
- **UI: module-coverage chips** on each health row — Beat / Orders / Dispatch with live counts → instant read on which tenants actually use which modules.

### Tests
- `test_iteration65_super_admin_parity.py` — 4/4 PASS (staff roles broadened, module coverage fields present, admins.employee_count, stats.total_employees).

## Changelog — May 2026 (Multi-tenant data integrity + Custom Voucher Types)

### Tally Agent v9.7.1 — `9.7.1-custom-vchtypes` (CRITICAL)
- **Custom voucher type support** — agents previously sent `<VOUCHERTYPENAME>Sales/Purchase/Receipt/...</VOUCHERTYPENAME>` which only matched literal Tally type names. For tenants with renamed voucher types (e.g., "Goods Purchase" / "Sales General" / "Bank Receipt" / "Cash Payment"), this returned ZERO vouchers despite stock journals + contra working fine.
- New `fetch_voucher_type_map()` method pre-fetches all voucher type masters per company → builds `parent → [display_names]` map.
- Sales / Purchase / Receipt / Payment / Journal / Credit Note / Debit Note fetchers now iterate every matching display name. De-dups by voucher_id.
- Cache invalidates on company switch.
- Re-served at `/flowra-desktop-agent.py`.

### Backend — Duplicate Company Map fix
- Root cause: `register_company_mapping()` looked up by `Fernet.encrypt(name)` which uses a random IV → `find_one` never matched → fresh UUID per sync request. With ~9 data types × 2 FYs × N retries, 9–19 dupes per company were the norm.
- Fix: deterministic HMAC-SHA256 hash for lookups (`company_name_hash` field). Display name still Fernet-encrypted at rest.
- Migration endpoint `POST /api/super-admin/dedup-companies` re-points all docs to the canonical UUID and de-dupes `users.companies`. Idempotent. Ran on production: removed 19 dupes, re-pointed 4,598 docs across 1 user.

### Backend — WebSocket tenant scoping
- `SyncWebSocketManager` was broadcasting every event to every connected client → tenants saw each other's sync progress.
- Fix: client must send `{action:'subscribe', tenant_id}` on connect; server only delivers events whose `tenant_id` matches the subscriber.
- `useSyncWebSocket(tenantId)` hook now requires tenant. Dashboard.js passes `user.tenant_id`.

### Setup — Creditor Groups admin UI
- New `CreditorGroupsPanel` mounted at the bottom of `Tally Setup`.
- Dual-list (selected ↔ available with search) + "Restore defaults".
- Saves via existing `POST /api/creditors/config`. Live, no re-sync needed.

### Tests
- `test_iteration64_dedup_companies.py` — 5/5 PASS (idempotent register, super-admin only, idempotent dedup, no dupe in user.companies, no dupe in /auth/me)

## Changelog — May 2026 (Tier-1 Backups + DPDP Data Export)

### SuperAdmin
- **MongoDB backup system (Tier-1)** — `/app/scripts/backup_mongo.sh` runs `mongodump --gzip --archive` to `/app/backups/`, retention 30, daily 02:00 IST cron-ready.
- **`/api/super-admin/backups*`** endpoints: list, run-now, download (gzip stream), delete (with path-traversal guard). All actions audit-logged.
- **SuperAdmin → Backups tab** (new) in `SuperAdminDashboard.js` — Run Now button, list with size+timestamp, per-row download/delete, callout to Tier-2 (Atlas) plan.

### Tenant Admin (DPDP right-to-portability)
- **`/api/admin/data-export`** — streams a ZIP with one JSON file per tenant collection (25 collections) + `manifest.json`. Strict tenant isolation: server filters every query by `tenant_id`. `users.json` and `audit_logs.json` are never included.
- **`/api/admin/data-export/preview`** — quick row-counts so admin sees what's in their export before downloading.
- **User dropdown → "Export Your Data"** link added to `AppNavbar.js`, gated to `role === 'admin'`. Salesman/dispatch never see the link.
- **`UserAdminDataExport.js`** — grouped preview (Sales/Purchases/Inventory/Salesman/Dispatch/Tally/AI) with one-click ZIP download.

### Documentation refresh
- `scripts/generate_flowra_pdfs.py` bumped to v3.1 (May 2026):
  - **What's New** PDF — added 7 May-2026 sections (Beat Run Today, A/B/C/D Inventory, CA Corner Tally Parity, Dispatch Mirror View, Backups & Data Export, Salesman Dashboard, Tally Agent v9.6.0)
  - **Training Booklet** — Inventory chapter now covers A/B/C/D pills + Auto-ABC; new chapter 8a "Beat Run Today"; Profile/User-Menu chapter mentions Export Your Data; CA Corner mentions "matches Tally exactly to the rupee"
  - **Deployment Guide** — new chapter 9 "Backups & Data Portability" describing Tier-1 + DPDP export
  - **Coming Soon** — removed "Backups + Per-tenant Data Export" (shipped); reframed Atlas migration as "Tier-2 on top of today's Tier-1 dumps"
- All 7 PDFs regenerated under `/app/frontend/public/FLOWRA_*.pdf`.

### Tests
- `/app/backend/tests/test_iteration62_backups_data_export.py` — 7/7 PASS (super_admin gating, run-now writes archive, download streams gzip, path-traversal blocked, preview counts, ZIP validity + tenant isolation + no `users.json` leak, salesman role denied).
- Frontend E2E (testing agent iter 60): 9/9 PASS (Backups tab Run Now → Download → Delete; admin Export ZIP download; salesman correctly hides Export Your Data link).

### Files touched / created
- `/app/scripts/backup_mongo.sh` (NEW, executable)
- `/app/backend/routes/backups.py` (NEW, registered in server.py)
- `/app/frontend/src/pages/SuperAdminBackups.js` (NEW, sonner toast)
- `/app/frontend/src/pages/UserAdminDataExport.js` (NEW, sonner toast)
- `/app/frontend/src/pages/SuperAdminDashboard.js` (added Backups tab)
- `/app/frontend/src/components/PageRenderer.js` (added `data-export` route)
- `/app/frontend/src/components/AppNavbar.js` (added Export Your Data link)
- `/app/scripts/generate_flowra_pdfs.py` (May 2026 sections)
- `/app/backend/tests/test_iteration62_backups_data_export.py` (NEW)

## Changelog — May 2026 (CA Corner Tally-Parity Phase)
- **Balance Sheet rewrite (`/api/ca-corner/balance-sheet`):**
  - Now derived from synced `all_ledgers` + customers + creditors with proper Tally sign convention.
  - Auto-balances via Profit & Loss A/c residual (TA = TL).
  - Validated against user's BSheet26-27.pdf: Capital, Loans, Fixed Assets, Investments, Branch/Divisions, Non-Current Liability — all match exactly.
- **P&L rewrite (`/api/ca-corner/profit-loss`):**
  - Sums `all_ledgers.closing_balance` by parent_group for current FY — perfectly matches Tally output.
  - Heuristic catch-all for Salary Accounts, Local Thela Gaadi, etc. under Indirect Expenses.
  - Validated FY26-27: Sales 35,36,521.28, Purchase 32,49,829.94, Indirect Income 3,959, Direct Expense 88,110 — all exact.
- **Tally Agent v9.5.0-creditor-fix**: fixed `skip_excludes` bug; added Salary/Wages/Rent/Travel mappings; signed-balance P&L summary.
- **Inventory model**: added stock value fields (was being silently dropped by Pydantic).
- **Tests**: `/app/backend/tests/test_ca_corner_bs_pl.py` (4/4 pass).

## Changelog — May 2026 (Beat Run Today — Field Coverage Tracking)

### Salesman dashboard
- **"Beat Run Today" tab** added (default after dashboard) — auto-derived from the salesman's beat plan filtered by today's day-of-week (IST).
- Tap any planned customer to **toggle visited** (timestamp captured in IST).
- **NEW unplanned visits** — text-box for customer name + details. Tagged `NEW` chip until that customer appears in synced Tally data (no CRM/sales impact until then).
- **"Beat History" tab** — read-only list of past runs with coverage % per day. Click any row → detail view (locked, can't edit).

### Useradmin Salesman page
- **"Beat Runs" sub-tab** (next to Beat Plans) — pick a salesman from dropdown → see their Today panel + paginated history of past runs (last 90). Click any past run for detail.
- Read-only viewer (BeatRunReadOnlyView) — admin can audit but not check-in retroactively.

### Day-end lock
- Server-side: `_is_locked(run_date) == run_date < _ist_today()` enforced on read.
- Check-in endpoint always writes to **today's** date — past dates are unreachable from the UI (LOCKED badge + disabled controls) and the API itself ignores any older `run_date` body param.

### New backend collection: `beat_runs`
- One doc per `(tenant_id, company_id, salesman, run_date)`.
- Auto-built on first read from `salesman_beats` (day-of-week match — supports both short "Mon" and full "Monday" labels).

### New endpoints
- `GET  /api/salesman-orders/beat-run/today?run_date=&salesman=&company_id=` — auto-builds from plan if missing.
- `POST /api/salesman-orders/beat-run/check-in` — toggle visited (today only, server-enforced).
- `POST /api/salesman-orders/beat-run/add-unplanned` — add NEW-tagged unplanned visit (today only).
- `GET  /api/salesman-orders/beat-run/history?salesman=&from_date=&to_date=&limit=` — admin sees any salesman, salesman scoped to own.

### Tests
- `/app/backend/tests/test_iteration60_beat_run.py` — 5/5 pass.
- Validates auto-build, check-in persistence, NEW tagging, past-date lock, role-scoped history.

## Changelog — May 2026 (Salesman / Dispatch / Inventory Phase)

### Salesman (Useradmin side)
- **Achievement % bug fixed**: `/api/salesman/performance` now compares against YTD-prorated target (`monthly_target × months_elapsed_in_FY`) instead of full annual. Ankit (and any over-achiever) now reflects correct >100% achievement when monthly target is met.
- **Beat Plans tab** added to Salesman Performance page — admin can pick a salesman, add day-of-week customer beats with weekly/biweekly/monthly frequency, and save. Visualises a 6-day weekly grid + editable rows.

### Salesman (Salesman login)
- **Activity feed scoping**: salesman/dispatch/employee roles now see ONLY their own audit logs. Admin/super_admin still see everything for the tenant. (`/api/audit/logs`, `/api/audit/actions`)
- **Salesman menu routing fix**: clicking "Salesman" while logged in as a salesman now correctly opens `SalesmanOrderApp` (not the useradmin's `SalesmanPerformance`). Bug was reproducible on Activity → Salesman menu transition.
- **Branch toggle hidden** for salesman & dispatch roles (admin-only filter).
- **FY selector active** for salesman (was always wired — confirmed working with `selectedFY` prop drilling into `my-stats`).
- **Salesman Dashboard** with KPI cards (Achieved, Expected YTD, Monthly Target, Achievement %) + customer-wise breakdown drill-down + top items sold. Endpoint: `GET /api/salesman-orders/my-stats?fy=...`
- **New Order — global search**: catalog search now matches against item_name OR part_number. Part numbers shown in catalog rows, cart rows, and order detail modal.
- **Standard Sale Price**: catalog returns `standard_price` field (Tally STDPRICE master) — falls back to `price` (closing rate) until v9.6 sync. Zero-stock items still show their standard price.

### Dispatch
- **Dispatch employees not appearing**: `/api/dispatch/employees` was filtering by `company_id` but users are tenant-wide → returned 0. Now filters by `tenant_id` only.
- **Dispatch employee parity**: dispatch role now renders the SAME `DispatchAdmin` page as useradmin with `isEmployee={true}` — only the **Employees tab is hidden**. All other tabs (Kanban, Online Orders, Pending Billing, Overview, Pending, Porters, Transporters), date selector, and Create Cards button remain available.
- **Online Order details modal**: Online Order tab cards are now clickable → opens detail modal with order metadata, line-items (with part numbers), notes, and admin notes.
- **Logout flash fix** (CRITICAL): "Feature Not Activated" toast no longer flashes on dispatch logout. Root cause: `PageRenderer` was rendering `<FeatureLocked>` for the post-logout transition. Fix: PageRenderer returns `null` when `!user || !token`.

### Inventory
- **A/B/C/D ABC categorisation** replaces the old Category column.
  - Manual: click any A/B/C/D pill in the row to assign.
  - Bulk: "Auto ABC" button runs Pareto 80-15-4-1 across the FY's revenue.
  - Filter: dropdown to slice by A/B/C/D/Untagged.
  - Preserved across re-syncs (sync.py snapshots `abc_category` before delete-and-reinsert).
- **Sales Price column** (Tally STDPRICE) added to Inventory table.
- **Inventory Analytics → Category Sales** new tab:
  - 4 large A/B/C/D pill cards.
  - Drill-down: items in selected category with FY revenue, qty, order frequency, current stock, sale price.
  - Per-item: top customers (qty + revenue + transaction count).
  - CSV export per category.

### Tally Agent (v9.6.0-stdprice)
- Fetches `STANDARDPRICE` (and `STDPRICE` fallback) per stock item.
- Stores `standard_price` on each `inventory_items` row.
- Re-served at `/flowra-desktop-agent.py`. **User must re-sync to see real STDPRICE**; until then, `standard_price` falls back to closing rate.

### Models / Sync
- `InventoryItem` model: added `standard_price`, `abc_category`, `opening_quantity`, `opening_rate`, `opening_value`, `closing_value`.
- `salesman_orders.py`: order POST now stores `part_number` per item.
- `sync.py`: inventory sync preserves user-assigned `abc_category` across delete-and-reinsert.

### New Backend Endpoints
- `GET  /api/salesman-orders/my-stats?fy=...` (logged-in salesman dashboard)
- `PATCH /api/inventory/items/{id}/abc` (single ABC set/clear)
- `POST /api/inventory/abc/auto-assign` (Pareto bulk classification)
- `GET  /api/inventory/category-sales?abc=A&fy=...` (drill-down)

### Tests
- `/app/backend/tests/test_iteration59_salesman_dispatch_inventory.py` — 13/13 pass (audit scoping, dispatch employees visibility, my-stats, catalog global search, ABC manual + auto + drill-down, beat plan CRUD, order POST stores part_number).
- **Balance Sheet rewrite (`/api/ca-corner/balance-sheet`):**
  - Now derived from synced `all_ledgers` + customers + creditors with proper Tally sign convention (asset side flips, liability side keeps).
  - Auto-balances via Profit & Loss A/c residual (Opening Balance computed so TA = TL).
  - Validated against user's BSheet26-27.pdf: Capital, Loans, Fixed Assets, Investments, Branch/Divisions, Non-Current Liability — all match exactly. Sundry Debtors within ~₹16K of Tally master (cleared on next re-sync).
  - User-facing notices when Stock-in-Hand or Sundry Creditors aren't yet synced.
- **P&L rewrite (`/api/ca-corner/profit-loss`):**
  - Sums `all_ledgers.closing_balance` by parent_group (Method A) for current FY — perfectly matches Tally output.
  - Falls back to ledger_entries scan (Method B) for previous FYs.
  - Heuristic catch-all for user-defined sub-groups (Salary Accounts, Local Thela Gaadi, etc.) under Indirect Expenses.
  - Validated against user's PandL26-27.pdf: Sales A/c (35,36,521.28), Purchase A/c (32,49,829.94), Indirect Income (3,959), Direct Expense (88,110) — all match exactly.
- **Inventory model fix (`backend/models.py`):** Added `opening_quantity`, `opening_rate`, `opening_value`, `closing_value` to `InventoryItem` so Stock-in-Hand values flow through on next sync (was being silently dropped by Pydantic `extra=ignore`).
- **Tally Agent v9.5.0-creditor-fix:**
  - Fixed `fetch_creditors_from_all_ledgers` bug (was passing `skip_excludes=False` which filtered creditors out — corrected to `True`).
  - Added defensive parent_group string match (creditor/supplier/vendor) for user-defined creditor sub-groups.
  - Added Salary Accounts, Local Thela Gaadi, Wages, Rent, Travel, Commission, Advertisement to GROUP_CATEGORY map (auto-classifies user-defined sub-groups under Indirect Expenses).
  - Rewrote `compute_pl_summary` to use signed CLOSINGBALANCE (drops the abs() that lost cash-discount signs) and stop using voucher header totals (which include GST output).
  - Bumped agent_version → `9.5.0-creditor-fix`. Re-served at `/flowra-desktop-agent.py`.
- **Regression tests:** `/app/backend/tests/test_ca_corner_bs_pl.py` validates BS balance + Sales/Purchase totals against Tally truth.

## Known Minor (Out of Scope, FYI)
- `AppNavbar.js:81` has `<span>` nested inside `<option>` causing a React hydration warning. Not a functional bug.
- UI login flow rejects empty `captcha_token` — works for real users (reCAPTCHA loads), blocks Playwright automation only.
- BS/P&L will reach 100% Tally parity only AFTER user re-syncs with v9.5 agent (captures stock + creditors + salary accounts). Until then the BS auto-balances via P&L A/c residual and notices flag what's missing.


## Iteration 83 — SPIP rolling-window + no_movement bucket + global search (Feb 2026)

**3 user-reported issues** in `/insider-result` SPIP tab:

**1. Use rolling 12-month window or previous available FY**:
Current FY 26-27 has only 2 months of data; user wants the analysis to fall back to a 12-month window anchored at the last synced voucher date when the selected FY is too short. Otherwise monthly-average / months-of-stock math is meaningless.
**Fix**: New `window_months=12` query param. Logic:
- If `fy` selected AND has ≥ 6 months of data → use selected FY
- Else (FY too short, or no FY) → rolling 12-month window from last voucher date
- Response carries `window` metadata: `{window_type, window_label, window_start, window_end}` so frontend can banner which window was used.

**2. New `no_movement` gap_type**:
User: "in balanced section many stock items are given with no transaction, on what basis are they balanced". Items with `stock_qty == 0 AND qty_sold == 0` were silently dumped into 'balanced'. KSC: 4,342 of 7,710 items had no transactions at all in the rolling 12m window, diluting Balanced from a useful 1,200-row list to a 5,500-row noise list.
**Fix**: New gap_type `no_movement` for items with zero stock + zero sales in window. Sorted last by priority. Frontend filter dropdown adds "No Movement (12m)" option. Verified live: Balanced now 1,231 (real items with 1-6 mo of stock); No Movement is 4,342.

**3. Global search across name + part_number + aliases**:
User: "search of stock items in spip is not using global parameters, no part no, alias. So make it global search".
**Fix**: Backend SPIP response now includes `part_number` and `aliases[]` per item. Frontend search input matches all three fields case-insensitively (mirrors Inventory page). Placeholder updated to "Search name / part-no / alias".

**Tests** — `tests/test_iteration83_spip_window_no_movement.py` (10/10 PASS):
- Window metadata returned
- no_movement gap_type defined + sort priority correct
- Response carries part_number + aliases per item
- Balanced section has only items with qty_sold > 0
- Short FY falls back to rolling window
- Full FY does NOT fall back
- Frontend search hits name + part_no + aliases
- Frontend filter dropdown has no_movement option
- Window banner rendered
- Search placeholder updated

Combined regression iter72-iter83: **97 passed, 2 skipped**.



## Iteration 82 — Batch B + 3 user-reported follow-ups (Feb 2026)

**1. SPIP zero-stock false positive** (Steelgrip 6.5mtr BLK had 899 stock but showed 0):
Root cause — `inventory_items.find().to_list(5000)` capped at 5,000 items; KSC has 7,510. Items past index 5,000 silently dropped from `inv_map`. Fix: `to_list(None)` (unbounded). Also bumped sales fetch 20K → 50K. Live KSC verification: out_of_stock count dropped 1942 → 1083; Steelgrip 6.5mtr now correctly shows stock=899 + gap=understocked.

**2. Sales Forecast — multi-FY YoY + prev-FY-based projection**:
- YoY now keys on Indian-FY label (2024-25, 2025-26, 2026-27) — was splitting by calendar year (2025/2026), giving nonsense buckets when filtered to a single FY.
- Forecast horizon = remaining months in selected FY (was: next 3 calendar months from `today`, often outside the selected FY → invisible on chart).
- Forecast = same-month-previous-FY × growth_trend (clamped 0.5–2.0). MA-blend fallback (60% MA-3 + 40% MA-6) when prev-FY data missing. Each forecast row carries `based_on_prev_fy_month` + `growth_trend_pct` + `confidence` for UI provenance.
- Frontend bridges actual → forecast line with a synthetic boundary point so Recharts renders a continuous dashed line. Method caption shown ("Forecast = same-month previous FY × growth trend ▼ 33%"). YoY chart label "FY 2025-26".

**3. Tally Sync Agent v9.8.7-aliases-perf**:
Fetches Tally `LANGUAGENAME.LIST` per stock item and stores as `aliases` array. Customer SKUs / brand short-names / part-number variants are now searchable. Falls back to `ALIAS` / `ALIAS.LIST` for older Tally builds. TDL FETCH list extended.

**4. Mobile responsiveness — server-side pagination + render-cap**:
- `/api/inventory/items` accepts `page`, `page_size`, `search`. Returns paged results + total count when `page_size > 0`; legacy full-list otherwise.
- `/api/customers/outstanding` accepts same params. Tenant-wide totals (`total_outstanding`, `total_paid`) stay full-tenant accurate; the `customers` array is paged.
- Backend search now matches `aliases` (regex array element-wise on Mongo).
- `Inventory.js`: render-cap of 200 rows + "Load 200 more" button. Reset cap on filter / search / sort change. Aliases shown as small chip below item_name.
- `CustomerCRM.js` Outstanding tab: same 200-row render-cap with debounced search input (name / phone / group). Same "Load more" pattern.

**Known limitation**: render-cap is client-side. For 7,500-item KSC tenant the full JSON still ships from server (~5 MB). Future P2: switch the table render to true server-side paging (page/page_size hits backend, debounced search). Render-cap alone is enough to fix mobile freezes today.

**Tests** — `tests/test_iteration82_batch_b.py` (16 tests covering all 4 fix areas). Combined regression iter72-iter82: **87 passed, 2 skipped**.



## Insider Result — Batch A Bug Fixes (Feb 2026)

**Bug #1 — SPIP "out of stock" rows showed zero stock when stock existed**
Sales-voucher item names had stray whitespace / case differences from inventory_items names (e.g. "TVS Item " vs "tvs item"). The cross-lookup in `routes/insights.py` `spip-analysis` endpoint used exact-match keys, so items showed `qty_sold > 0` AND `stock_qty = 0` → mis-classified as out_of_stock.
**Fix**: keys built on `name.strip().lower()` for both item_sales and inv_map. Display uses original casing via `display_name` field.

**Bug #2 — SPIP categories empty after dropdown selection**
Backend returned only `analysis[:200]` (top-200 by priority — out_of_stock + understocked first). Overstocked / Balanced / Dead Stock categories live in tail-end of the list and got truncated. KSC has 6,370 items; only 200 reached frontend.
**Fix**: removed slice — backend returns all items. Frontend pages 50/page.

**Bug #3 — Sales Forecast missing prev-FY comparison (April 25 vs April 26)**
Backend `month_comparison` was already populated for years (Apr-25 ₹65.5L vs Apr-26 ₹89.9L for KSC) but the Forecast tab never rendered it.
**Fix**: New "Month-over-Month FY Comparison" section in `InsiderResult.js` Forecast tab. Includes:
- Bar chart: one bar per FY per calendar month (auto-detects FY keys)
- Compact table: revenue per FY × month with %-delta vs previous FY (▲37.4% / ▼12.1% style)

**Bug #4 — Customer Lifecycle table capped at 100 rows**
Frontend hard-coded `filtered.slice(0, 100)` — KSC has 1,844 customers, only 100 reachable.
**Fix**: New `Pager` component (50/page, First / Prev / Next / Last + "Page X of Y" + "Showing N–M of T"). Reset-to-page-1 effect on filter / search / tab changes. Same pager wired to SPIP table.

**Tests** — `tests/test_iteration81_insider_batch_a.py` (7/7 PASS): SPIP returns all items, source no longer slices, case-insensitive matching present, lifecycle/SPIP pagination wired, page resets on filter change, month-comparison chart + table rendered, backend month_comparison shape stable. Combined regression iter72-iter81: 70 passed, 1 skipped.



## Tally Sync Agent v9.8.6-hierarchy-walk (Phase 2 of BS/PL parity, Feb 2026)

**Root cause**: Tally has multi-level stock-group nesting (Primary → Sub → Sub-sub → leaf items). The agent only stored each item's IMMEDIATE parent as `stock_group`. So an item like "TVS 10x1.25x110 A(50)" was stored with `stock_group="10mm & 12mm 1.25 Thread"` — completely losing the user's Primary-level grouping ("TVS Sundaram Fasteners"). Same problem hit the BS/P&L on the ledger side.

**Fix shipped (v9.8.6)**:
- New `fetch_stock_group_parent_map()` method on `TallyCollectionClient` — fetches `<STOCKGROUP>` collection from Tally and builds {sg_name → parent_sg_name} hierarchy.
- `fetch_stock_items()` now walks the hierarchy via `_resolve_root_group()` and stamps **`root_stock_group`** on every inventory item (the user-visible Primary group).
- `_resolve_root_group()` upgraded to short-circuit at Tally's reserved "Primary" anchor — returns the LAST level before "primary" (the user-visible root), not "primary" itself.
- `fetch_all_ledgers_via_groups()` and `_fetch_ledgers_fallback()` now STORE the walked `root_group` on every ledger result (was being computed but discarded).
- Backend `InventoryItem` model accepts `root_stock_group`.
- `/api/inventory/items` accepts `root_stock_group` query filter and returns `root_stock_groups` list (powers the new "All Primary Groups" dropdown).
- CA Corner BS endpoint: when `_classify_parent` doesn't recognise an immediate `parent_group`, falls back to the agent-walked `root_group` field (exact Tally-mapping replaces substring heuristics from Phase 1).
- New "Primary Group" filter dropdown on the Inventory page (`Inventory.js`).

**Distribution**: stamped `9.8.6-hierarchy-walk` at `/app/desktop-agent/tally_sync_agent_v9.py` + `/app/frontend/public/flowra-desktop-agent.py`. **User must re-download and re-sync** to populate `root_stock_group` and `root_group` for all inventory items + ledgers.

**Tests** — `tests/test_iteration80_agent_v986_hierarchy_walk.py` (12/12 PASS):
- Agent version stamp v9.8.6
- `fetch_stock_group_parent_map()` exists
- Walker chases multi-level chain (TVS Thread → Fastener → Sundaram Fasteners)
- Walker terminates on self-loop
- Walker stops at "primary" anchor (returns last user-visible level)
- `InventoryItem` model accepts `root_stock_group`
- `/inventory/items` accepts root filter + returns dropdown list
- CA Corner BS uses `root_group` fallback
- Ledger payload carries `root_group`
- Inventory payload carries `root_stock_group`
- End-to-end: stub agent run → items get correct root_stock_group

Combined regression iter72-iter80: 63 passed, 1 skipped.



## KSC BS/PL Parity — Phase 1 + Speed-ups (Feb 2026)

**Voucher parity** (verified before any fix): all 9 voucher types exact match — Sales 4,952, Purchase 2,051, Receipt+Payment+ChqRet 6,851, CN 411, DN 183, JV 605, SJ 90, Contra 17 — all line up with Tally PDF.

**Phase 1 server-side fixes** (no re-sync needed):
1. **Fixed Assets sub-group classifier**: User-defined sub-groups ("Construction Choubey A/c" ₹1.36 Cr, Vehicles ₹4.4L, Aircondition Machine ₹2.27L, Computer, CCTV, Biometric, etc.) were being silently dropped by `_classify_parent` because they don't match standard Tally root names. Added `_FIXED_ASSET_HINTS` / `_INVESTMENT_HINTS` / `_LOAN_LIAB_HINTS` substring lists. Result: Fixed Assets ₹30L → ₹1.70 Cr (exact match).
2. **Stock double-counting**: STOCK IN HAND ledger value (₹60.31L) AND inventory_items per-item closing-value sum (₹99.30L) were both being added to BS/P&L Closing Stock. Now ledger value wins when present (matches Tally exactly).
3. **Stock CR-natural sign**: Tally stores Stock-in-Hand ledger with negative closing_balance — added `abs()` to surface as positive opening/closing stock.
4. **Sundry Creditors double-counting**: `creditors` collection second pass was adding ledgers already classified by `_classify_parent` under Current Liabilities. Now only runs if all_ledgers has no creditor data.

**Combined live result on KSC**:
- FY 2025-26 Total Assets:  Tally ₹4,21,15,722 vs FLOWRA ₹4,22,35,512 (Δ ₹1.20L = **0.3% gap, was 24%**)
- FY 2026-27 Total Assets:  Tally ₹4,24,93,969 vs FLOWRA ₹4,16,97,053 (Δ ₹7.97L = **1.9% gap**)
- FY 2026-27 Closing Stock / Opening Stock: **exact match** ₹60.31L (was ₹99.30L)
- ✓ Capital, Loans, Suspense, Fixed Assets, Investments, Cash, Bank, Stock, Sundry Debtors, Indirect Income — all match within ₹100.
- Remaining ~2% gap traces to prev-FY indirect-expense breakdown (Method-B sums limited journal/receipt entries).

**Speed-ups shipped**:
- `server.py`: idempotent `ensure_indexes()` runs on every startup. 11 compound indexes covering tenant_id+company_id+date/name on sales/purchase/receipt/credit/debit/journal/contra vouchers, inventory, customers, all_ledgers, sundry_creditors, beat_runs, salesman_orders, audit_logs, dispatch_cards. Speeds up CA Corner / Inventory / CRM page loads 5-20× under load.
- Agent `SLEEP_BETWEEN_REQUESTS`: default lowered 2.0s → 0.5s. Saves ~4 minutes on a full sync (Tally TDL handles back-to-back requests fine).
- Agent log noise: empty-VCHTYPE message demoted INFO → DEBUG so log doesn't show "0 vouchers" spam for normal empty-period subtypes.

**Phase 2 (future, agent v9.8.6)**: ship Tally `groups_hier` (173 group records) as a sync payload + persist `root_group` on every ledger so future BS queries don't need substring heuristics. Pending user's STDPRICE diagnostic log.

**Tests** — `tests/test_iteration79_ksc_parity_phase1.py` (7/7 PASS). Combined regression iter72-iter79: 51 passed, 1 skipped.



## Tally Sync Agent v9.8.5-stdprice-list (Feb 2026 — DATA EXTRACTION FIX)

**Root cause** — verified live (0 / 7,712 items had `standard_price > 0` even though user has set Standard Selling Rate on every stock item):

The agent's `<STANDARDPRICELIST.LIST>` walker was reading the WRONG key. xmltodict surfaces repeated `<STANDARDPRICELIST.LIST>` elements **directly** at `si['STANDARDPRICELIST.LIST']` under each stock item — NOT nested inside a `<STANDARDPRICELIST>` parent. The previous code did `si.get('STANDARDPRICELIST', ...)` and never entered the loop. Result: every item fell through to the v9.8.2 "no fallback to cost" path → `standard_price=0` for everyone.

**Fix shipped in v9.8.5**:
- Reads `STANDARDPRICELIST.LIST` and `STANDARDPRICEDETAILS.LIST` (Tally Prime 3+) directly at the stock-item level
- Generic scan for any `*PRICELIST.LIST` / `*PRICEDETAILS.LIST` key (catches Tally builds with renamed sub-collections)
- Picks the most-recent applicable entry: filters `APPLICABLEFROM <= today` (skips future-dated rates), sorts by date desc
- Reads `RATE`, `STDPRICE`, `STANDARDPRICE`, `SELLINGRATE`, `SALERATE`, `PRICE` in priority order from each entry
- TDL FETCH list adds `STANDARDPRICEDETAILS`
- One-shot diagnostic log on first item shows price-related keys; end-of-loop summary logs `STDPRICE extracted: N/M items (X%)` so users can see the agent worked
- v9.8.2 "never quote cost" invariant preserved — when no master is set, `standard_price=0` (UI then falls back to last-sale via iter77)

**Distribution**: stamped `9.8.5-stdprice-list` at `/app/desktop-agent/tally_sync_agent_v9.py` + `/app/frontend/public/flowra-desktop-agent.py`. **User must re-download and re-sync** to populate STANDARDPRICE for all stock items.

**Tests** — `tests/test_iteration78_agent_v985_stdprice_list.py` (8/8 PASS): direct-key list read, single-entry dict, future-dated skip, most-recent applicable, Tally Prime 3+ details key, no-master returns 0 (cost not leaked), COMPUTE wins over .LIST walker, public-agent stamp v9.8.5. Combined regression iter72/73/75/76/77/78 — 44 passed, 1 skipped.



## Inventory Sale Price — Last-Sale Fallback (Feb 2026 — UX FIX)

**Fix — derive sale price from last sales voucher**:
- New helper `_last_sale_price_map()` in `routes/inventory.py` aggregates `sales_vouchers.items[].rate` (or `amount/quantity` if rate missing) per item, picking the most recent voucher per item.
- `/api/inventory/items` now returns `last_sale_price`, `last_sale_date`, `last_sale_invoice`, `effective_sale_price`, `sale_price_source` ∈ {`tally_master`, `last_sale`, `unset`} per row.
- `/api/salesman-orders/catalog`: `price` (the quoted price) = Tally master STANDARDPRICE if >0, else last sale rate, else 0. **Cost is NEVER quoted** (closing rate = average cost, would torch margins).
- `/api/inventory/category-sales`: also surfaces `last_sale_price` + `last_sale_date` per item drill-down.
- **Frontend `Inventory.js`**: Sale Price cell shows emerald `₹X` for tally_master, slate `₹X / Last sold YYYY-MM-DD` for last_sale, amber "Set in Tally" only when both are 0. Sort uses effective price.
- **Frontend `InventoryAnalytics.js`**: drill-down rows show `₹X last` chip when only last-sale is available.

**Live impact (ASA Autotech)**: Inventory rows with a usable price went from **0/202 (0%)** → **172/202 (85%)**. Only 30 items remain unset (truly never sold + no Tally master).

**Priority preserved**: Tally master STANDARDPRICE always wins when set — last-sale only fills gaps. Auto-updates as new bills sync.

**Tests** — `tests/test_iteration77_last_sale_price_fallback.py` (6/6 PASS): inventory schema, effective-price priority, salesman quotes-last-sale, never-quote-cost regression guard, helper picks-most-recent, helper amount/qty fallback. iter73 contract updated to recognise the new last-sale source. iter73/76/77 regression — 19 passed, 1 skipped.



## Tally Sync Agent v9.8.4-tenant-guard (May 2026 — DATA-LEAK FIX)

(1) **Cross-tenant company drift**: User logged into agent as ASA Autotech admin, then opened Krishna Sales Corp in Tally on the same machine. Agent's `_pick_company` blindly picked the new company (because `len(companies)==1` after Tally's switch) and synced KSC under admin's tenant → data leak.

(2) **Stale "is_syncing" lock**: After agent was killed/logged-out and re-logged in as a different user, the previous tenant's frontend kept polling `/sync/status` and saw `is_syncing=True` forever (the dead agent never sent `sync_complete`).

**4 coordinated fixes**:

- **A. Agent `_pick_company`** — persists previously-synced company name to `last_company.txt`. Each cycle, if Tally's active company differs, **interrupts with a confirmation prompt**. Default = NO.
- **B. Agent `--logout`** — sends `sync_aborted` POST to `/agent/sync-progress` BEFORE clearing creds, so frontend `is_syncing` clears immediately. Also deletes `last_company.txt` so next login starts fresh.
- **C. Backend `/sync/status`** — auto-clears stale `is_syncing=True` rows where `sync_started_at > 10 min ago` AND no `sync_progress` event in last 5 min. Safety net for OS reboot / Ctrl+C / network drop.
- **D. Backend `/agent/sync-progress`** — new event `sync_aborted` immediately clears `is_syncing` for the tenant.

**Distribution**: stamped `9.8.4-tenant-guard` at `/app/desktop-agent/tally_sync_agent_v9.py` + `/app/frontend/public/flowra-desktop-agent.py`. **Users on prior versions must re-download to get the data-leak guard.**

**Tests** — `tests/test_iteration76_agent_v984_tenant_guard.py` (6/6 PASS): stale-sync auto-clear, fresh-sync NOT cleared, sync_aborted clears is_syncing, public-agent stamp v9.8.4, no silent company switch, no-data status response unchanged. iter72/73/75/76 regression — 30 passed, 1 skipped.



## Tally Sync Agent v9.8.3-empty-vchtype-quiet (May 2026 — UX FIX)

**User reported (after re-running v9.8.2)**: "Voucher sync numbers are showing (6275 receipts cached), but for each month warning 'no vouchers found' is showing. Similar for all vouchers." Uploaded 4 raw XMLs.

**Diagnosis** (verified against the user's raw XML files):
- Tally returned a **valid metadata-only response** (`<REQUESTDATA><TALLYMESSAGE><COMPANY><REMOTECMPINFO.LIST/></COMPANY></TALLYMESSAGE></REQUESTDATA>`) with **zero `<VOUCHER>` elements** when queried for the **literal** "Receipt" / "Payment" voucher type names.
- Krishna Sales Corp's Tally has 4 child voucher types per parent (e.g. "Bank Receipt", "Cash Receipt", "App Cash Receipts" + the literal "Receipt") and posts no real transactions under the literal canonical name.
- The agent was correctly detecting "0 vouchers" but logging it as a `WARNING`, alarming the user.

**Two coordinated fixes**:

1. **`fetch_voucher_type_map()` smart dedup**: When a parent has CUSTOM child voucher types alongside the literal canonical name (e.g. `[App Cash Receipts, Bank Receipt, Cash Receipt, Receipt]`), drop the literal — it represents zero real transactions. Preserves the canonical name only when it's the only entry (stock Tally setups).
2. **`_parse_vouchers()` smart logging**: Distinguish metadata-only responses (`<COMPANY>` + `<REQUESTDATA>` + no `<VOUCHER>`) from genuine parse failures. Metadata-only logs as `INFO` (`"0 vouchers (Tally returned metadata-only response — VCHTYPE has no entries this period)"`), genuine failures still log `WARNING`.

**Net effect for users with custom Tally voucher types**: ~6 fewer redundant requests per month (1 per parent × 6 parents) AND no more alarming "no vouchers found" warning chain.

**Verified**: 9 new tests in `tests/test_iteration75_agent_v983_empty_vchtype_quiet.py` covering dedup logic + smart-logging classification + edge cases (case-insensitive match, single-name parents, stock Tally setups). All 86 tests pass across 9 iteration suites.

**Distribution**: stamped `9.8.3-empty-vchtype-quiet` at `/app/desktop-agent/tally_sync_agent_v9.py` + `/app/frontend/public/flowra-desktop-agent.py`. **User must re-download to get the cleaner logs**.

## Tally Sync Agent v9.8.2-saleprice-fix (May 2026 — BUG FIX)

**User reported (with ASA Autotech screenshot)**: "Inventory page still showing cost price in sale price column. Even after new sync."

**Diagnosis** (verified against live data — 2308/2308 ASA items showed `standard_price == price`):
- Agent's stock-item parser had a buggy fallback at line 830:
  ```python
  if std_price == 0 and rate > 0:
      std_price = rate  # ← rate IS THE COST RATE, not a sale price
  ```
- `rate` is `closing_value / closing_quantity` = average cost per unit (Tally's `$ClosingRate`). When Tally master had no STANDARDPRICE set, the agent silently substituted COST. Backend (`/inventory/movement-analysis`, `/salesman-orders/catalog`) and frontend (`Inventory.js`, `InventoryAnalytics.js`) had matching fallbacks `standard_price || price` — so cost showed up everywhere a "sale price" was expected.
- For salesman quoting screens this was particularly dangerous (would have quoted at cost = torched margins).

**Three coordinated fixes**:

1. **Agent v9.8.2** (`/app/desktop-agent/tally_sync_agent_v9.py`):
   - Cost-rate fallback removed entirely.
   - New diagnostic field `standard_price_source`: `'tally_master'` | `'unset'`.
   - Stamped `9.8.2-saleprice-fix`.
2. **Backend** (`/app/backend/routes/sync.py`, `inventory.py`, `salesman_orders.py`):
   - `/sync/upload` now detects `std_price == price` on incoming inventory docs and resets to 0 (catches stale agents).
   - `/inventory/movement-analysis` and `/salesman-orders/catalog` no longer fall back to `price`.
   - `InventoryItem` model has new `standard_price_source` field.
3. **Frontend** (`/app/frontend/src/pages/Inventory.js`, `InventoryAnalytics.js`):
   - Sale-price cell shows amber **"Set in Tally"** badge with tooltip explaining how to set STANDARDPRICE in Tally master, instead of misleading cost number.

**One-shot DB cleanup ran during deploy**: 2308 polluted items reset to `standard_price=0` so users see the corrected UI immediately (no need to wait for re-sync).

**Verified**: 11 new tests in `tests/test_iteration73_agent_v982_saleprice_fix.py`. All 71 tests across 7 iteration suites pass. UI screenshot confirms all rows now show "Set in Tally" with cost data still correctly displayed in the Cost column.

## Tally Sync Agent v9.8.1-voucher-recovery (May 2026 — BUG FIX)

**User reported**: Even with v9.8 deployed, agent emitted `"sales: no vouchers found in response"` while the saved raw XML clearly contained vouchers. Uploaded 5 raw XML samples confirmed the issue.

**Root cause**:
- Tally `EXPLODEFLAG=Yes` + `Voucher Register` produces ~100 KB XML **per voucher** (every empty `<RATEDETAILS.LIST>`, `<BATCHALLOCATIONS.LIST>`, `<BANKALLOCATIONS.LIST>` etc. is included).
- For tenants with hundreds of vouchers/month, response easily exceeds Tally's HTTP buffer or the agent's read window → response truncated mid-tag → `xmltodict.parse()` fails outright.
- Old `_post()` returned `None` on parse failure → `_parse_vouchers` never saw the partially-valid VOUCHER chunks that DID make it through.
- Old debug write capped at 100 KB so the saved file was useless for debugging.

**Fixes shipped in v9.8.1**:
1. `_post()` now ALWAYS returns the cleaned raw XML on a `__raw_xml__` key — even on parse failure. Downstream parsers can salvage what's there.
2. `_parse_vouchers()` falls back to `<VOUCHER ...>...</VOUCHER>` regex extraction when tree-walking returns 0 vouchers; each chunk parsed individually so one bad voucher doesn't kill the rest.
3. Debug XML write cap raised 100 KB → 5 MB.
4. `_find_deep()` ignores the new `__raw_xml__` placeholder key.
5. Logger now reports `"regex-recovered N vouchers from raw XML"` so users can see recovery in action.

**Verified**: 7 new tests in `tests/test_iteration72_agent_v981_voucher_recovery.py` simulate the user's exact failure pattern (3 complete vouchers + 1 truncated mid-tag → exactly 3 recovered, truncated one cleanly skipped). All 40 tests pass across iter69/70/71/72.

**Distribution**: agent stamped `9.8.1-voucher-recovery` at `/app/desktop-agent/` and `/app/frontend/public/flowra-desktop-agent.py`. **Users who saw the original bug must re-download the agent and re-run.**

## Tally Sync Agent v9.8.0-pl-parity (May 2026 — NEW)

**Goal**: Close the gap user found between our prev-FY P&L and Tally PDF (FY 25-26 was missing ~₹26L indirect expenses + ~₹10L sales-discount adjustments → GP under by ₹7.74L, NP over by ₹16.86L).

**3 ships in this version**:

### 1. Receipt/Payment vouchers now ship `ledger_entries`
- **Bug**: Agent's receipt-voucher payload (`results.append({...})` in `_fetch_receipts_and_payments`) didn't include `ledger_entries`. Backend `/api/sync/upload` for `receipts` also stripped them. Result: 0/1354 receipt_vouchers had ledger entries in production.
- **Fix**: Agent now ships `'ledger_entries': ledger_entries`; backend now `$set`s them on upsert.
- **Impact**: Salary, rent, marketing, freight, interest expense — all booked through payment/receipt vouchers — now flow into the prev-FY P&L's `indirect_expense` aggregation.

### 2. Sales vouchers no longer drop `ledger_entries` & `voucher_type`
- **Bug**: `models.SalesVoucher` had `extra="ignore"` and didn't declare `ledger_entries` / `voucher_type` / `dispatch_through` fields. Pydantic silently dropped them on validation. Result: 0/1312 sales_vouchers had ledger entries in production.
- **Fix**: Added the missing fields to the model. Agent already shipped them — model was the bottleneck.
- **Impact**: Sales-side discount sub-ledgers ("Cash Discount with GST", "Scheme Discount", etc.) and GST-sales sub-groups now reach prev-FY reconstruction.

### 3. Ledger classifier — keyword fallback for user-defined parent groups
- **Bug**: User-defined Indirect Expense sub-groups ("Salary Accounts MP", "Local Thela Bhada", "Petrol Expenses") fell through as `category='other'` because they're not in the `GROUP_CATEGORY` dict and Tally's parent-walk doesn't always reach a standard root.
- **Fix**: After the standard classifier, walk a curated keyword list (salary, thela, bhada, petrol, rent, marketing, freight outward, bank charges, interest paid, etc.) with **word-boundary regex** to avoid false positives like "rent" matching "current liabilities".
- **Test coverage**: 13 parametrised classifier tests including positive + negative cases.

**Distribution**:
- Updated `/app/desktop-agent/tally_sync_agent_v9.py` (≈3601 lines)
- Mirrored to `/app/frontend/public/flowra-desktop-agent.py` (download URL for users)
- Version stamped `9.8.0-pl-parity` in 4 places (logger, agent_version field × 2, CLI banner)

**Verified**: 16/17 tests in `tests/test_iteration71_agent_v98_pl_parity.py` pass (1 skipped for sync-upload integration that requires company_id header). All earlier 57 regression tests still pass.

**User action required**: Users on existing tenants must **re-run the Tally Desktop Agent** with v9.8 to backfill ledger_entries on historical data. Once re-synced, FY 25-26 P&L should match Tally PDF within ₹1,000.

## P&L Prev-FY Opening Stock + Movement Analysis Sync-Gate (May 2026 — BUG FIX)

User reported (with screenshot from ASA Autotech, where sync started in FY 25-26):

### Issue A — FY 25-26 P&L showed Opening Stock = 0
- The previous fix had hard-coded `opening_stock = 0` for any prev FY because Tally's master inventory snapshot only persists CURRENT-FY values.
- **Fix**: For any prev FY that has its own voucher data synced, opening stock is now **reconstructed** by:
  1. Replaying per-item quantities backwards through the FY's vouchers (sales / credit-notes / purchases / debit-notes)
  2. Valuing at the master opening rate (`opening_value / opening_quantity` per item) — best proxy for FY-end cost
- Live result for ASA-style tenant: `opening_stock` went from ₹0 → **₹10.71L**, GP from ₹42.15L → ₹31.44L (more conservative, accurate).
- Notice explains the reconstruction.

### Issue B — Movement Analysis displayed fake stock for unsynced FYs (e.g. 24-25)
- The endpoint looped over today's master `inventory_items` regardless of FY → for FYs with no voucher activity (24-25 and earlier for ASA), it leaked today's master quantities.
- **Fix**: Detect earliest synced voucher across sales+purchases. If requested FY ends BEFORE that date, return an empty payload (`fy_synced=false, items=[], summary=zeros, notices=["FY X was not synced..."]`).
- Same gating applied to `/api/ca-corner/profit-loss` for unsynced prev FYs (sets stocks to 0 with a "not synced" notice).

**Verified**: 15 tests pass in `tests/test_iteration70_prev_fy_stock_and_unsynced_movement.py` + iter69 regression suite.

## P&L Annual + Monthly Gross Profit — Major Correctness Fix (May 2026 — BUG FIX)

**Two real bugs the user reported (with screenshot)**:

### Bug 1 — Negative Sales for previous FYs (FY 25-26 showed Sales = ₹-19.44L)
- **Root cause**: For previous FYs, `routes/ca_corner.py` falls back to "Method B" — which scans `ledger_entries` from sales/purchase/CN/DN/JV vouchers. **Sales vouchers don't store `ledger_entries`** (0 of 1312 in the live tenant) — only `items[]`. So the only Sales-Account ledger entries that surfaced were credit notes (sales returns) → **net sales went negative**. Same bug for purchases (net sign right by accident, but magnitude wrong).
- **Fix**: For prev-FY Method B, sales/purchases now derived from `items[].amount` (pre-GST line totals, verified vs Tally PDF parity) — credit-notes / debit-notes deduct from items totals; journal/receipt/contra entries layer adjustments on top via `ledger_entries`. CN/DN explicitly excluded from the inner JV loop to prevent double-counting.
- **Result**: FY 25-26 went from `Sales −₹19.44L · GP −₹38.45L` (clearly wrong) to `Sales ₹4.04 Cr · Purchases ₹3.81 Cr · GP ₹42.15L · Net Profit ₹29.50L` (sensible 10.4% margin).

### Bug 2 — Stock for prev-FY was wrong (master snapshot leaked across FYs)
- **Fix**: Tally master `inventory_items` only stores current-FY stock. For prev FYs we now set `opening_stock=0` (we don't have it) and `closing_stock = current_FY's_opening_stock` (mathematically correct). Notice clearly explains the gap.

### Enhancement — Monthly Gross Profit now stock-aware (Tally Trading Account)
- **Before**: Monthly GP = Sales − Purchases (Trading Profit, ignores stock movement).
- **After**: Monthly GP = Sales − COGS, where `FY_COGS = Opening_Stock + FY_Purchases + Direct_Expense − Closing_Stock` is **allocated to each month proportionally to its net sales**. Sales/Purchases also scaled to FY totals so Σ monthly equals FY exactly.
- **Σ Monthly GP = FY Gross Profit** ← guaranteed (asserted in tests).
- New `cogs`, `opening_stock`, `closing_stock` fields per monthly row + `monthly_meta { stock_aware, fy_cogs, stock_movement }`.
- **Frontend**: New amber "Cost of Goods Sold" row appears in monthly table when stock-aware. GP label says *"Gross Profit"* (with stock) or *"Gross Profit (Trading)"* (fallback, no stock).
- For prev FYs without stock data → graceful fallback to Trading Profit with notice.

**Verified**: 10/10 tests pass in `tests/test_iteration69_pl_monthly_gp_fix.py`. Live numbers:
  - FY 26-27: ΣmonthlyGP = ₹3,86,051 = FY GP ✓
  - FY 25-26: Sales ₹4.04 Cr (was −₹19.44L), GP ₹42.15L (was −₹38.45L) ✓

## P&L Monthly Gross Profit Fix (May 2026 — BUG FIX)
- **Bug**: Monthly P&L computed `gross_profit = m_sales − m_purchases` using voucher-header `total_amount` which **includes GST** → noisy & wrong; also missed Direct Income / Direct Expense entirely.
- **Fix** (in `routes/ca_corner.py` monthly view branch):
  - Net sales/purchases per month derived from `items[].amount` (pre-GST line totals, verified vs Tally PDF).
  - Credit notes / debit notes deduct from monthly net sales / purchases respectively.
  - Direct Income / Direct Expense + Sales-Account / Purchase-Account adjustments picked up from `journal_vouchers.ledger_entries` using `all_ledgers` parent-group / category metadata.
  - Receipts surfaced from `receipt_vouchers` (voucher_type=Receipt only).
- **New M-o-M change fields** on every monthly row: `sales_change_pct`, `purchases_change_pct`, `gp_change_pct` (1st month is null; rest is `round((curr − prev)/abs(prev) × 100, 1)`).
- **New `notices[]`** flags monthly GP as **Trading Profit** (excl. stock movement) and explains why it may differ from the FY-total GP.
- **Frontend** (`pages/CACorner.js`) — Monthly P&L table now shows three M-o-M sub-rows (Sales / Purchases / GP) with a tiny `MoMCell` (▲▼ + colour: green=good direction, red=bad). Notice rendered as italic footer below the table.
- Test file: `/app/backend/tests/test_iteration69_pl_monthly_gp_fix.py` (6 tests, all pass).

## Beat Run Monthly Report (May 2026 — NEW)
- New admin/super_admin reporting tab inside **Salesman Performance → Beat Runs**
- Toggle: **Daily History** (existing) | **Monthly Report** (NEW)
- Endpoints (admin-only — salesman role gets `Admin access required`):
  - `GET /api/salesman-orders/beat-run/monthly-report?month=YYYY-MM&salesman=X&trend_months=N`
    - Returns: `summary` (planned/visited/unplanned/coverage_pct/run_days/salesmen_count),
      `per_salesman[]`, `per_customer[]`, `daily_breakdown[]`, `trend[]` (last 6 months)
  - `GET /api/salesman-orders/beat-run/monthly-report/export?month=YYYY-MM&format=excel|csv`
    - **Excel**: 4-sheet `.xlsx` (Summary · By Salesman · By Customer · Raw Runs)
    - **CSV**: flat raw visit rows (one per planned + one per unplanned)
- UI features:
  - Month picker (max = current month)
  - 4 KPI cards (Coverage / Run Days / Planned / Unplanned)
  - 6-month coverage trend with inline SVG sparkline + per-month percentages
  - Per-salesman roll-up table (visited/planned/unplanned/coverage %)
  - Per-customer visit-frequency table (top 20, expandable to all, with planned/unplanned badge)
  - Daily breakdown table (date / day / planned / visited / unplanned / coverage %)
  - CSV + Excel export buttons
- Test file: `/app/backend/tests/test_iteration68_beat_run_monthly_report.py` (9 tests, all pass)

## Marketing Kit (May 2026 — NEW)
- **15 Square Posters + 4 Carousels** — full HTML/CSS source at `/app/marketing-kit/posters.html`
- Posters cover Hero, Beat Run, A/B/C/D Pareto, CA Corner parity, Backups+DPDP, Salesman Dashboard,
  Dispatch Terminal, AI Reports, Outstanding CRM, Security/5-min setup, Made in India, Pricing ROI,
  Testimonial, Try-Free CTA, WhatsApp Direct
- Carousels: 5 Ways FLOWRA Pays Back · Beat Run 60-sec · Tally se data, FLOWRA se decisions (bilingual) · A/B/C/D Explained
- All assets exported as 2160×2160 PNG (2× retina) via `/app/scripts/export_posters.py` (Playwright headless)
- 38 PNGs in `/app/marketing-kit/exports/{posters,carousels}/`, bundled to `/app/marketing-kit/flowra-social-kit.zip` (~48 MB)
- Captions ready-to-paste at `/app/marketing-kit/captions.md`
- **Lead-Gen Strategy** at `/app/marketing-kit/strategy.md`: 30-day rolling content grid, WhatsApp-first deeplinks,
  Meta Ads budget split (50% CTC / 25% Lead Form / 15% Reach / 10% Retarget), KPIs, qualification scripts

## Customers Refactor (May 2026)
- Extracted shared math from `routes/customers.py` (1554 → 1317 LOC) into pure-python module
  `services/customer_metrics.py` (292 LOC, 0 DB / 0 FastAPI deps).
- Functions: `fy_start_iso`, `base_fy_start_iso`, `split_by_fy`, `split_receipts_and_payments`,
  `filter_branch_parties`, `compute_opening_balance_map`, `aggregate_party_credits`,
  `apply_fifo_aging`, `aging_status`.
- Eliminated the ~150-line duplicate Opening-Balance replay between `get_customer_outstanding`
  and `get_payment_behavior`; behaviour preserved (regression tests pass).
- Test files: `/app/backend/tests/test_iteration67_customer_metrics_refactor.py` (17 unit tests).

## Fuzzy / Normalized Search Across All Search Boxes (Feb 2026 — NEW)
**P0 feature** — User reported that Tally records have inconsistent formatting (spaces, dashes, slashes, parens, dots, etc.) which made search unreliable. Now ALL search boxes ignore separator characters in BOTH the search input AND the stored value, so `tvs 10` matches `TVS-10`, `TVS(10)`, `TVS/10`, `TVS.10`, etc.

**Ignored characters** (per user choice "1b, 2b"):
`<space> \t - / ( ) ! : . , & _ ' "`

**Backend** — `/app/backend/utils.py` (new helpers):
- `fuzzy_normalize(s)` → strips ignorable chars, lowercases.
- `build_fuzzy_regex(term)` → produces a Mongo-compatible `$regex` that matches the term while permitting any separator chars between letters in stored values.
- `fuzzy_match(haystack, needle)` → Python-side substring check on already-loaded lists.

**Endpoints upgraded**:
- `GET /api/inventory/items` — search across `item_name`, `part_number`, `aliases`.
- `GET /api/customers/outstanding` — search across `customer_name`, `phone`, `ledger_group`, `contact_person`, `state`. The `customer` filter param also fuzzy.
- `GET /api/customers/payment-behavior` — same fields.
- `GET /api/salesman-orders/catalog` — fuzzy on items + part_number + aliases.
- `GET /api/salesman-orders/orders` — fuzzy on order_id, customer_name, invoice_number.
- `GET /api/dispatch/cards` & `GET /api/dispatch/history` — fuzzy on invoice/party/card-id/lr/transport.

**Frontend** — `/app/frontend/src/utils/fuzzySearch.js` (new):
- `fuzzyNormalize`, `fuzzyMatch`, `fuzzyMatchAny` — mirror the backend helpers for client-side filtering.

**Pages upgraded** (client-side filtering replaced):
- `Inventory.js`, `CustomerCRM.js` (Outstanding + Payment Behaviour), `InsiderResult.js` (Lifecycle + SPIP), `InventoryAnalytics.js` (ABC table + customer dropdown), `DispatchTerminal.js`, `SalesmanOrderApp.js` (catalog), `SearchableSelect.js` (used by all customer/item dropdowns).

**End-to-end verified** with admin `axle 85w140` ↔ `axle85w140` ↔ `V12-GO/851` ↔ `compressor.oil` and customer `krishna sales` ↔ `krishnasales` — all returned identical result sets.

**Tests**: `/app/backend/tests/test_iteration84_fuzzy_search.py` — 11/11 passing.

## Dispatch Card Cancellation + Tally Invoice-Change Detection (Feb 2026 — NEW)
**P0 feature** — User can now cancel a dispatch card if the underlying order is cancelled, and the system flags cards whose Tally invoice was modified after sync.

### Card Cancellation
- New endpoint: `POST /api/dispatch/cards/{card_id}/cancel` body: `{reason, notes}`.
- Allowed only when card status ∈ `{new, queued, processing, packed}`. Once `dispatched` or `info_shared` (truck has left), cancellation is blocked. Cancelled is **terminal** — cannot be reopened.
- Records `cancelled_at`, `cancelled_by`, `cancel_reason`, `cancel_notes`, `cancelled_from_status` + `status_history` entry.
- Cancel reasons: `customer_request`, `payment_issue`, `stock_unavailable`, `duplicate`, `invoice_modified`, `other`.
- Open to **all dispatch users** (no special role required).
- **Strikethrough until end-of-day**: cancelled cards remain visible in their pre-cancel lane with line-through + grey "CANCELLED" badge until midnight IST, then auto-hide from active board (still visible in History).

### History view enhancements
- `GET /api/dispatch/history?include=` accepts `completed | cancelled | all` (default `completed`).
- Frontend has 3-tab pill filter: **Completed / Cancelled / All**.

### Option B — Invoice Change Detection (flag-only, no auto-update)
- New helper `_detect_invoice_changes()` runs after every sales sync (`routes/sync.py`).
- Compares each non-cancelled card's snapshotted `items / total_amount / party_name` against the live `sales_voucher`:
  - Active card + diff → `invoice_changed_flag = True` + `detected_changes` array (🟡 amber badge in UI).
  - Active card + voucher missing → `invoice_missing_flag = True` (🔴 red badge "MISSING").
  - Already-shipped card + diff → `post_dispatch_invoice_changed = True` (🔴 red banner "modified AFTER dispatch").
- **Snapshots are NEVER mutated** — operator manually reconciles. Stale flags auto-clear if invoice is restored.
- Cancelled cards skipped entirely.

### Files
- Backend: `/app/backend/routes/dispatch.py` (cancel endpoint, status guard, _detect_invoice_changes, history filter), `/app/backend/routes/sync.py` (post-sync hook).
- Frontend: `/app/frontend/src/pages/DispatchTerminal.js` (CancelModal, banners, strikethrough lane card, History tabs).
- Tests: `/app/backend/tests/test_iteration85_dispatch_cancel.py` — 3/3 passing (constants + full DB integration of detect helper).
- E2E curl verified: create → cancel → re-cancel blocked → status move blocked → active view shows today-cancelled → history `?include=cancelled` filters correctly.

## Tally Sync Agent v9.8.8 — Rate-Parse Fix (Feb 2026 — CRITICAL FIX)
**P0 bug** — Standard Price was 0 for **every single inventory item across all tenants** despite v9.8.7 shipping STANDARDPRICELIST extraction. Root cause was NOT the extraction — it was the `_num()` parser.

**Bug**: Tally exports rate-typed XML values as `<amount>/<unit>` (e.g. `<STANDARDPRICE TYPE="Rate">1495.00/Nos</STANDARDPRICE>`). The pre-v9.8.8 `_num()` called `float("1495.00/Nos")` directly → `ValueError` → returned 0.

**Fix**: In `_num()` and `_signed_num()` — strip everything from the first `/` before float-parsing.
```python
if '/' in s:
    s = s.split('/', 1)[0].strip()
```

**Diagnosis**: User shared `stock_items_raw.xml` for ASA AUTOTECH. Confirmed every `<STANDARDPRICE>` and `<STANDARDPRICELIST.LIST>→<RATE>` value uses the `nnn.nn/Nos` rate-per-unit format. Verified the new parser extracts ₹3,646 / ₹4,422 / ₹52,788 etc. correctly across all 202 items in the user's XML.

**Files**:
- `/app/desktop-agent/tally_sync_agent_v9.py` — version bumped to v9.8.8-rate-parse-fix.
- `/app/frontend/public/flowra-desktop-agent.py` — synced from source (live distributable).
- `/app/backend/tests/test_iteration86_agent_v988_rate_parse.py` — 9/9 passing (unit + end-to-end XML fixture mirroring the user's data).

**User action required**: Re-download `flowra-desktop-agent.py` from the agent download link, replace the existing copy on the Tally machine, and run a fresh sync. After sync, the Inventory page "Sale Price" column should switch from slate **"Last sold ₹X"** to green **"Tally master ₹X"** for every item that has a Standard Selling Rate set in Tally.

## CRITICAL — Salesman Role Privilege Escalation (Feb 2026 — FIXED)
**P0 security regression** — A user logged in as `salesman` role and clicking the "Salesman" sidebar item was shown the **admin-only Salesman Performance page** revealing every other salesman's targets, customer mapping, achieved revenue, and contact details.

### Root cause
In `/app/frontend/src/components/PageRenderer.js`, the switch statement had **two `case 'salesman':` branches**. JavaScript switches match the first case — the early case unconditionally rendered `<SalesmanPerformance>`, making the role guard in the second case dead code.

### Fix — defense in depth (2 layers)
1. **Frontend**: Removed the duplicate case. The single remaining `case 'salesman'` checks `user.role === 'salesman'` and routes to `<SalesmanOrderApp>` instead.
2. **Backend** (NEW): Added `_require_admin()` helper in `/app/backend/routes/salesman.py` and applied it to ALL admin-only endpoints:
   - `GET /api/salesman/master` (auto-create + listing)
   - `POST /api/salesman/master`
   - `DELETE /api/salesman/master/{name}`
   - `GET /api/salesman/performance`
   - `GET /api/salesman/performance-detailed`
   - `GET /api/salesman/customer-ownership`
   - `GET /api/salesman/export`
   Salesman role now gets `Forbidden: admin role required` on all of these regardless of how they reach the API.

### Tests
- `/app/backend/tests/test_iteration87_salesman_role_security.py` — passing. Verifies salesman is blocked from all 4 admin GETs + POST + DELETE, AND that admin can still use them, AND that salesman's own ordering app endpoints still work.

### Last sync stamp for Salesman & Dispatch logins (Feb 2026 — NEW)
Salesmen and dispatch employees don't have a Dashboard. Upgraded the navbar (`/app/frontend/src/components/AppNavbar.js`) sync indicator from a static "Synced/No sync" label to a relative-time stamp ("Synced 5m ago" / "Synced 2h ago" / "Synced 3d ago") with full IST timestamp on hover. Visible on every page for every authenticated role.

### Sync progress UI gate (Feb 2026 — NEW)
`<SyncStatusBar>` (live progress) on Dashboard now renders ONLY for `user.role === 'admin'`. Non-admin roles see only the static last-sync stamp in the navbar. Also skipped the WS subscription itself for non-admins (saves one backend connection per shop-floor login).
