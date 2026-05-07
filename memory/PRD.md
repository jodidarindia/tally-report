# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally for business analytics, inventory, CRM, dispatch, salesman ordering, and CA reporting.

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
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders

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

## Changelog — May 2026 (CA Corner Tally-Parity Phase)
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
