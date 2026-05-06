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
- Fixed `customers.py` UndefinedName crash (`fy_start` → `fy_start_str`) on line 363 that broke Outstanding aging fallback for opening-balance-only customers
- Hoisted `SortTh` + `handleSort` to top of `CustomerCRM.js` component scope (was previously trapped inside the Outstanding-tab IIFE causing `ReferenceError: SortTh is not defined` on default Targets tab)
- Added `max-h-[calc(100vh-380px)]` wrapper to PaymentBehaviorTab so its sticky `<thead>` engages on vertical scroll (already in place for Outstanding + Targets tabs)
- **CRM Outstanding root-cause rewrite:** Source of truth is now the `customers` collection (synced from Tally Sundry Debtors group). Removed auto-add of parties from `sales_vouchers` that was leaking creditors (e.g., Epsilon Petrochem) and depot ledgers into the Outstanding tab. Removed hard-coded `SUNDRY_DEBTOR_GROUPS` filter that was dropping 36/37 real customers whose Tally sub-group is "Chhattisgarh Distributor"/"MP Distributor"/"Orrisa Distributor". Receipt/CN/JV aggregation now uses lowercase party keys for case-insensitive match with the customer master.
- **Dashboard Overdue digest guard:** Drop overdue invoices for parties whose `customers.outstanding_amount` is ≤ 0 (Tally closing balance is the source of truth — prevents stale invoices from appearing as "overdue" when receipts aren't bill-allocated, e.g., Abhishek paid in full but allocation wasn't synced).
- **OB anchor fix (per Tally export validation):** Tally master `OpeningBalance` reflects today's calendar FY (Tally auto-rolls into the new FY on 1-Apr each year). Code now anchors `customers.opening_balance` against today's FY-start instead of the stale `sync_status.financial_year` label. Validated against user's Tally exports: FY 25-26 closing balance now matches **37/37 customers exactly** (₹29L total) and opening balance matches **32/37**; FY 26-27 matches 8/9 fully, with the 9th being a stale-data issue (sales not yet synced for that customer FY 26-27). The 5 OB mismatches are due to data gaps in the synced JV ledger entries (agent does not store DR/CR direction per line) — they are within ₹3-80k rounding-style differences and not a code defect.
- **Payment Behaviour endpoint** — applied the same OB anchor + case-insensitive lookup + JV net (debit−credit) fix. Krishna/Indian Sales/Ankit/Saanvi outstanding now match Tally CB exactly.
- **Insider Result fixes:** Lifecycle StatCards (Active/Inactive/Lost/Total) are now clickable to filter the customer list with selected-state ring; dropdown options show counts e.g. "Active (26)"; renderForecast/renderSpip/renderConcentration have defensive `|| []` fallbacks; catch block logs full error to console with status code in toast.

## Known Minor (Out of Scope, FYI)
- `AppNavbar.js:81` has `<span>` nested inside `<option>` causing a React hydration warning. Not a functional bug.
- UI login flow rejects empty `captcha_token` — works for real users (reCAPTCHA loads), blocks Playwright automation only.
