# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB Atlas SaaS synced with Tally / Busy for business analytics, inventory, CRM, dispatch, salesman ordering, and CA reporting.

## Production Posture (Feb 2026, post iter99)
- **Hosting target**: DigitalOcean (Droplet 2GB) + MongoDB Atlas (Mumbai)
- **Atlas DBs**: `Flowra-Insights` (prod) / `Flowra-Insights-Dev` (Emergent sandbox)
- **Backend**: FastAPI behind nginx, /api/health probe live
- **Desktop agent**: v9.8.28-company-raw-parens, .exe published at `/FlowraTallyAgent.exe`


## Shipped — Feb 16 2026 (iteration 148) — Busy Agent v1.5.4: display name + retry
Two shipping fixes for the live Busy customer whose CRM, Dashboard, CA Corner
and Target tab were showing `COMP0002` instead of `NAVDURGA AUTO SPARES JABALPUR`:

1. **Real company name resolution** — added `BusyDataExtractor.get_company_display_name()`
   which probes the master `db.bds` file for `Cmpny.BDEPName`, `Company1.Name`,
   `BDept.BDEPName` etc, returning the first non-empty value (folder id
   fallback if all probes miss). `run_daemon()` now passes this as
   `company_name` while keeping the stable folder id (`COMP0002`) as
   `company_id`. `BUSY_COMPANY_DISPLAY_NAME` env var overrides for edge cases.

2. **Folder-keyed company mapping (backend)** — new
   `services.id_mapping_service.register_company_by_folder(tenant_id, folder_id, display_name)`
   keys the mapping on `folder_id_hash` (stable) instead of the display name
   hash. Same folder id → same UUID even if the user renames the company in
   Busy. **Legacy v1.5.3 mappings** (whose `company_name_hash` accidentally
   equals the folder id) get auto-migrated on the next sync: stamp the
   `folder_id_hash`, update the encrypted display name, same UUID — no
   orphan data, no re-sync required. `/api/agent/sync` uses the new resolver
   when `company_name` is provided and differs from `company_id`.

3. **`_post_chunk()` 3-tier retry with backoff** (5s / 30s / 60s) on any
   4xx or 5xx that isn't `success:false`. Silent 502/503 data-loss is now
   loud: `[SYNC-LOST]` dead-letter log with data_type + FY + company on
   permanent failure. Next full-sync tick will re-post the same records
   (idempotent voucher_id upsert already guaranteed).

Tests: `test_iteration148_busy_v154_display_name.py` (8/8 green) — locks
fresh-create, in-place rename, legacy migration, sync_token guard,
end-to-end folder-keyed sync, extractor fallback, VERSION bump, retry
backoff source anchor.

## Shipped — Feb 16 2026 (iteration 155) — Inventory Demand Forecast tab
New Analytics-menu tab. Admin-only, tenant + company isolated, uses all
synced FYs, considers **only the tenant's own inventory master** (no
external SKU references from voucher lines).

Backend (`/api/analytics/forecast/*` — 5 endpoints):
1. **`/overview`** — KPI band + consolidated buy list (up to 500 SKUs
   ranked by projected revenue, stockout risk, and forecast-vs-stock
   ratio).
2. **`/sku/{item_id}`** — per-SKU deep dive with confidence bands +
   ROP / safety-stock.
3. **`/season`** — top-N SKUs × 12-month past × horizon future for the
   demand heatmap.
4. **`/cohort`** — top customers' projected same-month-last-year demand.
5. **`/export`** — CSV export of the full analysis (PO-ready shape).

Engine (`services/forecast_engine.py` — no LLM, no heavy deps):
- **Velocity classifier** partitions each SKU into A/B/C/new based on
  history depth + non-zero density.
- **Holt-Winters triple-exp** (add trend + add season, p=12) for
  A-class steady sellers.
- **Simple exponential smoothing** for B-class.
- **Croston + SBA correction** for C-class intermittent demand (the
  purpose-built method — normal forecasts wildly over-predict on
  sparse series).
- **Cold-start** for new SKUs = median month across cohort peers of
  the same `stock_group`.
- **Reorder point + safety stock** via z-score × lead-time (default
  15 days, 95 % service level).
- **Confidence bands** (P25/P75) from residual std.
- **Curated Indian festival + monsoon calendar** — optional lens
  applies month-specific multipliers to auto-parts demand.

Security:
- Admin-only guard at every endpoint (rejects employee / salesman /
  dispatch / super_admin with 403).
- Every DB query scoped to `(tenant_id, company_id)` from
  `get_tenant_context` — no cross-tenant leaks.
- Analysis restricted to inventory master items — voucher lines that
  reference items deleted from Busy master are dropped (per user spec).
- 12 h in-process cache per (tenant, company, horizon, festival,
  growth) so re-opening the tab returns in ms.

Frontend (`/app/frontend/src/pages/analytics/DemandForecast.js` +
tab wired into `InventoryAnalytics.js`):
- Controls: horizon selector (1-12 months), what-if growth-% slider,
  festival-lens toggle, refresh, CSV export.
- 5-tile KPI band (SKUs analysed, projected units, projected revenue,
  stockout SKUs, excess SKUs).
- Consolidated buy-list table with velocity pill, confidence chip,
  "Buy by" date, and hi/lo range.
- Season heatmap (past 12 months + forecast months) — shading
  intensity encodes demand density.
- Top-customers cohort table with projected next-horizon revenue.

Dependencies added: `statsmodels==0.14.6` + `scipy==1.17.1` +
`patsy==1.0.2` (installed + `pip freeze` appended to
`requirements.txt`).

Verified on live `busydemo@flowralive.in` (NAV Busy tenant):
- 13 696 SKUs analysed in ~8 s
- ₹57.74 L projected revenue (3-month horizon)
- 226 stockout-risk + 650 excess-stock SKUs flagged
- Both FYs (2025-26 + 2026-27) contribute to the historical series

Tests: `test_iteration155_demand_forecast.py` — 8/8 green
(classifier boundaries, Croston non-negative on sparse, HW fallback,
ROP math, `forecast_sku` payload shape, admin-only 403 for salesman,
NAV overview e2e, NAV season heatmap e2e). Full iter 148-152 + 154 +
155 combined batch: 33/33 green.


## Shipped — Feb 16 2026 (iteration 154) — Per-source release manifests + Setup label polish
Followup on Setup-page usability feedback for Busy tenants.

1. **Per-source release manifest**: new `/app/backend/agent_release_busy.json`
   (v1.5.7 → `/FlowraBusyAgent.exe`) alongside the existing Tally
   manifest. `/api/agent/latest-version` and `/api/agent/check-update`
   now accept `?source=tally|busy` and route to the matching manifest.
   Backwards-compat: no `source` param → Tally.
2. **In-process cache** slotted per-source (`data_tally` / `data_busy`)
   so both manifests stay hot for 5 min.
3. **Setup page fetches with `source`**: `TallySetup.js` now calls
   `axios.get('/api/agent/latest-version', { params: { source }})` and
   re-fetches whenever `syncStatus.agent_version` changes so first-paint
   Busy tenants never see a Tally v9.8.28 chip.
4. **Removed two "pure-Python access_parser" blurbs** per user request —
   the details are now hidden from the customer-facing Setup page. Kept
   the friendly "Direct file access — no extra setup" panel.
5. **CreditorGroupsPanel** label reads "Tally/Busy parent groups" (was
   Tally-only).

Tests: `tests/test_iteration154_per_source_release_manifest.py` — 6/6
green — locks the manifest files on disk, the per-source routing on
`/api/agent/latest-version` + `/api/agent/check-update`, the removal
of the two info blurbs, and the source-driven re-fetch on the Setup
page.


## Shipped — Feb 16 2026 (iteration 153) — App-side ERP-label + count fixes
Followup on user feedback from the live NAV Busy tenant.

1. **Dashboard inventory count 10K → 13.6K**. `get_inventory_summary`
   was doing `.to_list(10000)` then `len(items)` — capped the tile at
   10 k for tenants with 13.6 k items. Replaced with `count_documents(q)`
   (fast, exact).
2. **Inventory "Set in Tally" pill → "Set in ERP"**. Now uses the new
   `getErpLabel()` helper so the label reads "Set in ERP" for both
   tenants but the tooltip mentions the actual ERP name.
3. **CRM Outstanding "Tally ✓" tag → dynamic "Tally ✓" or "Busy ✓"**.
   Reads the cached agent source (fetched from `sync-status.agent_version`
   on Dashboard/Setup mount).
4. **SPIP Analysis total 14 061 → 13 682**. The `analysis` list was
   built off `union(inventory master keys, sales-voucher item keys)`,
   inflating the count by ~379 items that were sold historically then
   deleted from Busy master. Switched to `set(inv_map.keys())` — master
   is the source of truth. Count now matches Inventory menu exactly.
5. **Customer Lifecycle "all lost" bug**. `voucher_date` from the Busy
   agent is `"YYYY-MM-DD 00:00:00"` (with time). The old
   `last_date.split("-")` fed `int("01 00:00:00")` → ValueError →
   `days_since = 999` → every customer bucketed as LOST. Fixed by
   normalising to `last_date[:10]` before parsing.
6. **Sync History header** — `"Timeline of all data sync cycles from
   Tally*"` → dynamic `"…from ERP name*"`.
7. **Setup page (`TallySetup.js`) split by agent source**:
   - Page title "Tally* Setup" → dynamic ("Tally* Setup" or "Busy* Setup").
   - Download card shows "FLOWRA {Tally|Busy} Sync Agent" dynamically.
   - Busy branch replaces the XML/HTTP + REST connection form with a
     data-folder info panel (no ODBC, no REST — pure-Python
     `access_parser`).
   - Busy branch renders 8-step ordered instructions (download →
     SmartScreen bypass → point at data folder → login → pick starting
     FY → Start Sync → retry backoff behaviour → log file location).
   - Tally branch untouched (existing XML port 9000 / REST API key
     form + 4-line instruction block, but "Tally" → `getErpLabelMarked()`).
   - Footer disclaimer and `<CreditorGroupsPanel />` UNTOUCHED per user
     instruction.

**Helper**: `/app/frontend/src/utils/agentSource.js` — tiny module.
Reads `agent_version` (e.g. `busy-1.5.7-invoice-fields`) from
sync-status responses, caches "busy" | "tally" in localStorage, exposes
`getErpLabel()` / `getErpLabelMarked()` / `getAgentSource()` for any
component that needs the current ERP name. Dashboard.js and
TallySetup.js both call `setAgentSourceFromVersion` on load.

Tests: iter-148..152 (36/36) still green — no regression on Busy/Tally
data extraction, model validation, or per-FY ingest.


## Shipped — Feb 16 2026 (iteration 150) — Busy Agent v1.5.6: data parity
Full root-cause fix set for the live `COMP0002 → NAVDURGA AUTO SPARES
JABALPUR` sync where 24 k inventory items shrank to 182, P&L stored 0
net profit, and CA-Corner rendered blank.

Backend (helps Tally too):
1. **`data_type=='inventory'`** — chunked `UpdateOne+upsert` by `item_id`
   replaces the old `delete_many(t_filter) + insert_many` per-chunk
   pattern that wiped every prior chunk. 22 k+ items now persist.
   User-managed `abc_category` still preserved via a snapshot done ONCE
   before the chunks start (not per-chunk).
2. **`data_type=='profit_loss'`** — key expanded to
   `(tenant_id, company_id, fy)` so multi-FY P&L rows coexist. Backend
   also accepts either `net_profit_loss` or legacy `net_profit`.
3. **`data_type=='all_ledgers'`** — key expanded to include `fy` for
   the same reason (opening/closing balances stay per-FY).
4. **Cross-tenant leak fixed** — `/api/analytics/sales-frequency/export`
   was running `db.sales_vouchers.find({})` (empty filter → EVERY
   tenant's data as Excel). Now scoped to the caller's context via
   `get_tenant_context`.

Busy agent (`flowra_busy_agent.py` v1.5.6):
5. **`extract_inventory_items`** — now emits `opening_quantity`,
   `opening_rate`, `opening_value`, `closing_value` sourced from the
   new `_load_item_opening_map()` (reads `Folio1` MasterType=6, D1/D2/D3).
6. **Sale/cost price fallback ladder** — when the txn-derived rate map
   has 0 for an item, we probe `Master1.SPrice/SalePrice/SaleRate/MRP/
   PrintPrice/D3/D4` for sale and `Master1.PPrice/PurchasePrice/
   PurchaseRate/CostRate/D2` for cost.
7. **`compute_profit_loss`** — payload now carries `net_profit_loss`
   (backend read key) in addition to legacy `net_profit`, and stamps
   `fy` on the doc for the new FY-scoped key.
8. **Extractor cache invalidated per FY** — added `_item_opening_cache`
   alongside the existing qty/price caches.

Busy GUI (`flowra_busy_gui.py`):
9. **Removed unused Busy Username / Login-Password / DB-Password
   entries** — `access_parser` bypasses ODBC / OLE DB entirely since
   v1.5.1, those three fields have been decorative. `self.entries`
   still carries the keys as invisible `StringVar`s so old configs
   don't KeyError on save.
10. **Stop-Sync button hidden in maximized frame** — bottom bar had a
    hard-coded `height=56` + `pack_propagate(False)` which clipped
    the ~68 px tall Start/Stop buttons. Removed both — frame now
    auto-sizes to fit its children.

Data cleanup:
11. **Purged stale COMP0002 mapping** in the live `1524ec0e-…` tenant
    (v1.5.3 leftover mapping keyed on `name_hash("COMP0002")` with no
    `folder_id_hash`; the correct `NAVDURGA…` mapping already owns
    every data row).

Tests: `test_iteration150_busy_v156_data_parity.py` (9 new tests,
25/25 green across iter-148/149/150). Locks the inventory chunk
upsert, abc_category preservation, per-FY P&L, per-FY ledgers, and
extractor opening-balance ladder against future regressions.


## Shipped — Feb 16 2026 (iteration 149) — Busy Agent v1.5.5: BusyDBReader pool
Kills the ~25× file-parse overhead the extractor carried since v1.5.1
(each of ~14 helpers opened + closed the same `.bds` file, and
`access_parser` re-parses the whole file into memory on every open).

Changes:
1. **`_PooledReader` proxy** — thin no-op-close wrapper over
   `BusyDBReader`. Every extractor helper now grabs its reader via
   `self._get_reader(db_path)` instead of `BusyDBReader(db_path)`.
   Legacy `finally: reader.close()` blocks stay valid — the proxy
   ignores close so the pool owns the underlying lifecycle.
2. **`BusyDataExtractor._reader_pool`** — one `BusyDBReader` per
   `.bds` path per sync tick, torn down via `close_readers()` from
   both `run_full_sync` and `run_quick_sales_sync` finally blocks
   (also frees ~50–200 MB of `access_parser` cached rows between ticks).
3. **CI anchor test** — `test_iteration149_busy_v155_reader_pool.py`
   asserts exactly ONE `BusyDBReader(...)` construction site exists
   in the whole file (inside `_get_reader`) — any future helper that
   sneaks in a direct construction fails the suite loudly.

Tests: 6/6 in iter-149 + 8/8 iter-148 still green (14/14 total).
Expected impact: a full sync tick on the live COMP0002 DB should now
open the `.bds` file ~1 time per FY per tick (down from ~14), roughly
halving CPU time and eliminating the "AccessParser reopen jank" from
the log.



## Shipped — Jul 8 2026 (iteration 116) — FLOWRA Financial Pitch (Feb 2026 raise)

Founder locked pricing (Starter ₹833 / Professional ₹2,083 / Enterprise ₹3,166 per company/mo), 1 current paid customer, Y5 ARR target ₹5 Cr, team plan 12→25 by Y5, two-tranche fundraise. Built two deliverables in `/app/scripts/generate_financial_pitch.py`:

**`/pitch/financial_pitch_flowra.pdf`** (128 KB, 16 pages, DejaVuSans for ₹ glyph support):
Cover · Executive Summary · Problem · Solution · Product Snapshot · Market (TAM ₹14,000 Cr) · Traction (Krishna Sales case) · Business Model · Competitive Moat · Unit Economics · 5-Year Projections + chart · Product Roadmap (Q1 FY26 → Q4 FY27) · Team · Investment Ask + Use of Funds · Risks & Mitigations · Exit Scenarios + Contact.

**`/pitch/financial_projections_flowra.xlsx`** (16 KB, 8 sheets, all yellow cells editable):
Read Me · Assumptions · P&L Summary (with bar chart) · Revenue Build · Cash Flow & Fundraise · Unit Economics · Cap Table (Founders/ESOP/Seed/Series A dilution) · Exit & Returns (3 scenarios × money-multiples).

**Key numbers locked**:
- Base case ARR: Y1 ₹20 L → Y5 ₹5.10 Cr → Y6 ₹7.30 Cr
- EBITDA flips positive Y5 (₹0.26 Cr) · positive Y6 (₹1.15 Cr)
- Cumulative Y1-Y5 burn: ₹4.19 Cr (comfortably inside ₹8.5 Cr total raise)
- Blended ARPU ₹1,683/mo · LTV/CAC 7.9× · Payback 5.1 mo · Gross margin 82%
- Seed ₹2.5 Cr @ ₹11.4 Cr pre-money · Series A ₹6.0 Cr @ ₹27 Cr pre-money
- Founder equity after both rounds: 60.5%

**Tests (9/9 green)**: `backend/tests/test_iteration116_financial_pitch.py` — locks pricing, customers, EBITDA flip, cumulative burn ≤ raise, LTV/CAC ≥ 3×, payback ≤ 18 mo, gross margin 78–85%, both files exist + nonzero, XLSX has 8 sheets.

Files publicly downloadable at `<preview>/pitch/financial_pitch_flowra.pdf`, `<preview>/pitch/financial_teaser_flowra.pdf`, and `<preview>/pitch/financial_projections_flowra.xlsx`.

**Teaser PDF (v1.1, added Feb 8 2026 same day)** — 10-page 86 KB cold-outreach opener: Cover · Problem · Solution · Traction (Krishna Sales) · Market · Business Model (4-plan price cards) · Unit Economics (6 hero KPIs) · 5-Year Trajectory (compact table + chart) · The Ask (Seed + Series A cards + Use of Funds) · Team + Contact CTA. Same DejaVuSans font, auto-shrinking hero KPI cards, reuses the exact projection numbers from the full pitch so the two documents can never drift.


## Shipped — Jul 11 2026 (iteration 119) — "What's New" single source of truth

Enhancement: bound both the User Admin Dashboard "What's New" panel AND `FLOWRA_Whats_New.pdf` to a single JSON file at `/app/frontend/public/whats_new.json`. Kills the drift problem permanently — one edit updates both surfaces.

**Files touched:**
- `/app/frontend/public/whats_new.json` (new) — 25 entries covering Apr–Jul 2026, `{updated_at, entries[]}` shape with `date/tag/title/desc` per entry.
- `/app/frontend/src/pages/Dashboard.js` — new `updates` state + `useEffect` fetch of `/whats_new.json` on mount. Removed the 25-entry inline hardcoded array (~50 lines gone). Loading fallback shows "Loading updates…" data-testid.
- `/app/scripts/generate_whats_new_pdf.py` — removed the module-level `UPDATES` tuple, now calls `load_updates()` which reads the JSON. Log line now includes `source: whats_new.json updated_at=…` for auditability.

**Workflow going forward:** when we ship a new feature, edit `whats_new.json` (one file) → next Dashboard visit shows it immediately (fetch has `no-cache`) → running `python scripts/generate_whats_new_pdf.py` regenerates the PDF with the same data.

**Tests (6/6 green)**: `backend/tests/test_iteration119_whats_new_single_source.py` — JSON shape/keys/tags, newest-first sort, latest entry ≥ 2026-07-11, Dashboard.js fetches the JSON (not hardcoded), PDF generator reads from JSON (no legacy UPDATES constant), regeneration produces a nontrivial file matching the JSON entry count.

**Verified**: `curl <preview>/whats_new.json` → 6 KB, 25 entries · `curl <preview>/FLOWRA_Whats_New.pdf` → 72 KB, latest entry "Busy Sync Agent v1.3.1". Frontend + backend lint clean.


## Shipped — Jul 11 2026 (iteration 118) — Busy Sync Agent v1.3.1 · DB password fallback

Customer log 07:50:55 after the v1.3 rebuild:
```
pyodbc.ProgrammingError: (42000) [Microsoft][ODBC Microsoft Access Driver]
Not a valid password. (-1905)
```
Root cause: Busy encrypts every `.bds` file with a proprietary password. v1.3 attempted a passwordless connection so the Access ODBC driver rejected it. Fix: try a fallback chain of the standard Busy passwords per generation (Busy 21 → 18 → older → blank), and honour a `BUSY_DB_PASSWORD` env var override.

**Fixes (in `/app/desktop-agent/build-kit-busy/`):**
- `flowra_busy_agent.py::_get_connection` — new `_KNOWN_BUSY_PASSWORDS` tuple + fallback loop:
  1. Env var `BUSY_DB_PASSWORD` (if set) wins, tried alone.
  2. Otherwise iterate `bs21DBFile → Bus1Wor$1D → busyww → busy → ""`.
  3. Only `pyodbc.ProgrammingError` containing `-1905` is retried; other pyodbc errors bubble up.
  4. Successful password is info-logged (first 2 chars only).
  5. All-fail case raises a friendly `RuntimeError` telling the user to set the env var or fill the Settings field.
- `flowra_busy_gui.py` — new "Busy DB password" input in Settings § 2 (masked, saves to `busy_db_password` config key). GUI daemon spawn now propagates `BUSY_DB_PASSWORD` env var.
- Version bumped agent `1.3 → 1.3.1`, GUI `v1.3 → v1.3.1`, `version_info.txt` file/prod `(1,3,1,0)`, agent_tag `busy-1.3.1-db-password-fallback`.

**Tests (31/31 green)**: new `test_iteration118_busy_agent_v131_password.py` (7 tests) covers: known-password list, env override wins, fallback chain iterates in order, all-fail raises friendly error mentioning `BUSY_DB_PASSWORD`, GUI propagates env var, Settings tab has the password field, version bumped. Iteration 113/114/117 tests updated to v1.3.1.

**GUI smoke-boot verified** via Xvfb — password entry widget renders in Settings § 2 without breaking any previous layout.

**Next**: user rebuilds `FlowraBusyAgent_v1.3.1.exe` via `build.bat` on Windows and reinstalls. Should sync on first attempt for standard Busy installs; the ~5% of customers with custom passwords fill the Settings field once.


## Shipped — Jul 11 2026 (iteration 117) — Busy Sync Agent v1.3 · pyodbc bundling fix

Customer log (`busy_agent_20260711.log`) crashed at Phase 1 (Customers):
```
ModuleNotFoundError: No module named 'pyodbc'
  File "flowra_busy_agent.py", line 157, in _get_connection
    import pyodbc
```

Root cause: `pyodbc` is imported LAZILY inside `_get_connection()`. PyInstaller's static-import scanner missed it in the v1.2 build, so the .exe shipped without the pyodbc wheel bundled. Everything else worked — login, folder detection, FY scan — until the first .bds read attempt.

**Fixes (in `/app/desktop-agent/build-kit-busy/`)**:
- `requirements.txt` — added `pyodbc>=5.1.0` so `build.bat`'s venv has it → PyInstaller sees it.
- `agent.spec` — added `'pyodbc'` to `hiddenimports` (belt & braces).
- `flowra_busy_agent.py::_get_connection()` — wrapped `import pyodbc` and `pyodbc.connect(...)` with friendly `RuntimeError`s that tell the customer either "rebuild via build.bat" (ImportError) or "install the Microsoft Access ODBC driver" (InterfaceError) with a direct download link.
- Version bumped: agent `1.2 → 1.3`, GUI `v1.2 → v1.3`, `version_info.txt` file/prod version `(1,3,0,0)`, agent_tag `busy-1.3-pyodbc-bundled`.
- `README.txt` — new "What changed in v1.3" section.

**Tests (24/24 green)**: new `test_iteration117_busy_agent_v13_pyodbc.py` (5 tests) covers: pyodbc in requirements, pyodbc in agent.spec hiddenimports, friendly-error wrapper present, version bumped in all 3 files, no stale v1.2 leftovers. Existing iteration 113/114 tests updated to expect v1.3 and pass.

**Next**: User rebuilds `FlowraBusyAgent_v1.3.exe` via `build.bat` on Windows (build.bat auto-detects the new pyodbc line in requirements.txt), then re-installs on the customer machine. First-time customers may also need the Microsoft Access Database Engine 2016 Redistributable — the new friendly error message links straight to the download page.


## Shipped — Jul 8 2026 (iteration 114) — Busy Sync Agent v1.2 · full Tally clone



Rebuilt `/app/desktop-agent/build-kit-busy/flowra_busy_gui.py` as a 1:1 clone of the Tally Sync Agent GUI (v9.8.29):
Tabs: Status · Settings · Logs · About; 4 connectivity cards; Sync Status panel with progress bar; Subscription card with Request Renewal button; login lock/unlock; auto-detect companies + FYs on folder pick; daemon mode with `flowra_busy_agent.py --daemon`; build kit (build.bat, agent.spec, version_info.txt, requirements.txt, README.txt, flowra.ico, flowra_logo.png). 14+6 regression tests green.


## Shipped — Jul 8 2026 (iteration 115) — Tally Sync Agent v9.8.30 · Forward-dated voucher fix

User reported: LVD captured on 08-Jul → added invoice dated 10-Jul → no sync → moved the same invoice back to 08-Jul → synced. Diagnosed 3 issues in `/app/desktop-agent/build-kit-2/tally_sync_agent_v9.py` from the customer log dump. All 3 fixed and locked with 10 regression tests.

**a) Quick-sync date window now extends to today, not stops at LVD**

Old: `for m_start, m_end in months_in_fy(fy, cap_date=lvd):` — capped SVTODATE at the stored LVD, so any voucher dated *after* LVD was outside the query window and Tally never returned it. Even though AlterID correctly detected a change (628983 → 628984), the delta-sweep missed the new voucher.

New: computes `window_end = max(lvd, date.today())` per cycle and passes that as `cap_date`. Also injects today's month + window_end's month into `affected_months`. A voucher dated 10-Jul now falls inside SVTODATE=10-Jul and comes back in the XML.

**b) Reconcile is now scoped to the fetched voucher_date window**

`FlowraSyncAgent.reconcile_with_backend(..., window_start=None, window_end=None)` — quick-sync callers pass ISO dates and the backend `/api/agent/reconcile` adds `{voucher_date: {$gte: window_start, $lte: window_end}}` to the delete filter. Fixes the destructive "5229 orphan records removed" line in the customer log — quick-sync was previously sending a manifest containing only the ~500 vouchers from its narrow window and the backend was deleting every FY voucher not in that list. Unscoped legacy calls (from the full-sync path) still delete everything, so backwards-compat is preserved.

**c) Day-Book LVD fallback no longer crashes on dict input**

`_fetch_last_voucher_date_via_daybook()` was calling `re.finditer(pattern, data)` where `data` came from `_post()`, which has returned the parsed-dict shape (with a `__raw_xml__` sidecar) since v9.8.x. This raised `TypeError: expected string or bytes-like object, got 'dict'` on every cycle, killing the LVD auto-detect and forcing the default-to-today branch. Now we `data.get('__raw_xml__') or ''` before regex.

**Version bumped**: `v9.8.29-lvd-persist` → `v9.8.30-window-scoped-reconcile`, GUI title `v9.8.30`, banner subtitle "AlterID Prime 7.0 + Window-Scoped Reconcile + Forward-Dated Voucher Fix".

**Tests (10/10 green)**:
- `backend/tests/test_iteration115_tally_v9830_forward_dated_fix.py` — 8 unit tests:
  - `months_in_fy` cap semantics under old (buggy) LVD-cap AND new max(lvd, today) cap
  - reconcile signature accepts `window_start`/`window_end` kwargs
  - Day-Book fallback survives dict from `_post`, None input, dict-without-raw input
  - agent_version string bumped
  - GUI `APP_VERSION` bumped
- `backend/tests/test_iteration115_reconcile_window_e2e.py` — 2 integration tests (live Mongo + FastAPI):
  - **window_scoped**: seeds 3 vouchers (Jun/Jul/Aug), reconcile with window=Jul + manifest=[], verifies only the Jul voucher is deleted and the Jun/Aug survive (this is what would have saved the customer's 5229 vouchers)
  - **unscoped_backwards_compat**: reconcile without window kwargs still deletes all — full-sync path unchanged

**Backend routes touched**: `/app/backend/routes/sync.py` — `POST /api/agent/reconcile` accepts `window_start` + `window_end`, filters `voucher_date` when both present, adds `window=…` scope tag to the info log.

**Next**: User rebuilds `FlowraTallyAgent_v9.8.30.exe` via `build.bat`, updates sha256 + size_bytes in `backend/agent_release.json` + `frontend/public/agent-latest.json` (tally channel), then ships.



User feedback on the v1.1 build flagged 8 bugs against the Tally reference screenshots. All 8 fixed by rebuilding the GUI as a 1:1 clone of `flowra_gui.py` (Tally v9.8.29):

1. **Tab order** now matches Tally exactly: `Status · Settings · Logs · About` (was Dashboard · Sync · Logs · Settings).
2. **Status tab** now shows 4 connectivity cards (Internet · Busy Data · FLOWRA Cloud · Sync Service) with coloured dots, plus a live Sync Status panel with progress bar and last-sync timestamp.
3. **Subscription card** with Plan · Account · Expires on · Days remaining fields, `🔄 Refresh` and `📨 Request Renewal` buttons — hits `POST /api/auth/request-renewal` just like the Tally agent.
4. **Data folder → auto-detect**: entering a folder path (or clicking Browse) auto-detects companies AND FYs in the same background thread. No manual chaining.
5. **FY chip picker** driven by scanning `db{year}.bds` filenames, with the current FY badge-highlighted.
6. **Login success**: shows a "welcome, {email}" banner + locks `email` + `password` entries (`instate=['disabled']`). Fields re-enable on Sign-out only.
7. **Build kit files added**: `build.bat`, `agent.spec`, `version_info.txt`, `requirements.txt`, `README.txt`, plus `flowra.ico` and `flowra_logo.png` copied from Tally kit. `build.bat` produces `FlowraBusyAgent_v1.2.exe` ready to upload.
8. **Auto-sync**: after Save & Start Sync (or after settings load), the GUI spawns `flowra_busy_agent.py --daemon` which reads env vars (`BACKEND_URL`, `FLOWRA_EMAIL`, `FLOWRA_PASSWORD`, `BUSY_DATA_FOLDER`, `BUSY_COMPANY`, `BUSY_STARTING_FY`, `SYNC_INTERVAL_MINUTES`) and runs a full/quick sync loop every 5 min / N min. No manual trigger needed.

**Also matches Tally:**
- Navy header with FLOWRA logo, versioned subtitle, "● Running/Stopped" pill, logged-in user email + Logout button (top right).
- Bottom bar with blue "▶ Start Sync Service", "■ Stop", "✕ Hide to Tray", "📁 Open Logs Folder".
- System tray icon with Show / Sync Now / Open Logs / Auto-start / Quit menu.
- Windows autostart via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FlowraBusyAgent`.
- Single-instance guard on port 38766 (Tally uses 38765).
- Start Menu + Desktop shortcut installer (first launch of the frozen .exe).

**Tests**: `backend/tests/test_iteration114_busy_agent_tally_parity.py` — 14 contracts (all green): build kit inventory, versioning, backend URL default, folder/company/FY detection helpers, daemon entry point, registry key naming, distinct single-instance port. Plus iteration 113 tests (6) still passing.

**Smoke boot**: Xvfb-verified. Status + Settings screenshots captured — visually identical to the Tally reference the user shared.

**Next**: User needs to PyInstaller-build `FlowraBusyAgent_v1.2.exe` on Windows (`build.bat` handles everything), then update `sha256` + `size_bytes` in `backend/agent_release.json` + `frontend/public/agent-latest.json` under the busy channel.



## Shipped — Jul 7 2026 (iteration 112) — Agent v9.8.29 LVD persistence + Full-sync short-circuit

Field report from Ankit Sarawgi's 07-Jul-2026 agent log surfaced two pending issues:
1. `Last voucher date: not detected via $$LastVoucherDate or Day-Book scan — defaulting to today` — repeated on both Krishna Sales Corp and ASA Autotech.
2. Full sync repeats on every agent restart — no AlterID short-circuit on the full-sync path.

**Root cause of Issue 1**: LVD regex only matched `<DATE>` tags, but Tally Prime 7.0 Day Book *report* export emits `<VCHDATE>` / `<VOUCHERDATE>`. Regex scanned the 1+ MB Day Book XML and found 0 candidates → returned `None` → fell to `date.today()`. All diagnostic logs were at DEBUG level so the user could never see WHY it failed.

**Root cause of Issue 2**: `run_sales_quick_sync()` had an AlterID short-circuit; `run_full_sync()` did not. Every startup ran a full 16-month scan regardless of Tally state.

**Fix bundle (5 parts) — shipped to a NEW folder `desktop-agent/build-kit-2/` to keep the v9.8.28 build folder pristine**:
1. LVD regex now matches `VCHDATE | VOUCHERDATE | VOUCHDATE | DATE` (case-insensitive) and accepts 6 date formats (`%Y%m%d`, `%d-%m-%Y`, `%d-%b-%Y`, `%Y-%m-%d`, `%d.%m.%Y`, `%d/%m/%Y`).
2. LVD diagnostic logs promoted from `debug` → `info`. Success line reads `Day-Book scan: 42 voucher dates parsed · tag hits: {'VCHDATE': 42} · latest = 07-Jul-2026`. Failure line surfaces the tag histogram so the NEXT log the user shares tells us the exact tag Tally is emitting.
3. New sync-state banner at the top of every full-sync cycle:
   `Sync state: AlterID=628,980 · LVD=07-Jul-2026 · Last full sync = 6.2 h ago`
4. AlterID short-circuit on `run_full_sync()` — when `stored_alter_id == current_alter_id` AND `last_full_sync < 7 days`, log `[FULL-SKIP] Krishna Sales Corp: AlterID unchanged (628980). Skipping full sync — quick-sync will handle deltas.` and heartbeat the cloud. Zero Tally over-fetch on unchanged data.
5. Persist `alter_id::{company}`, `lvd::{company}`, `last_full_sync::{company}` in `sync_state_v9.json` at end of every successful full sync. Live-LVD-None now falls back to the cached LVD from sync_state, then `today` only as the last resort.

**Version**: `v9.8.29-lvd-persist` — bumped in `APP_VERSION`, banners, and all 5 agent_version tags. `flowra_gui.py` shows `v9.8.29`. Manifests (`backend/agent_release.json`, `frontend/public/agent-latest.json`) are DELIBERATELY LEFT AT v9.8.28 — user must PyInstaller-rebuild the .exe from `build-kit-2/` first, compute new sha256 + size, THEN bump the manifests.

**Isolation guarantee**: `desktop-agent/build-kit/` (v9.8.28) is byte-identical to production. New test `test_build_kit_v9_8_28_untouched` fails CI if anyone edits the old folder.

**Tests**: `test_iteration112_agent_lvd_persist.py` — 11 tests covering all 5 fixes + build-kit isolation guard + v9.8.28 SVCURRENTCOMPANY raw-parens contract still upheld in v9.8.29. Total green suite: **112/112 across iter-100..112**.

**Expected impact**:
- Cold restart, unchanged Tally → previously ~10 min / 200 MB XML per company. **Now ~5 s (one AlterID query, skip).**
- Restart with 3 new vouchers today → **~30 s** (only current month fetched using cached LVD as window start).
- First-run / no cached state → full sync as before (unchanged behaviour).

## Shipped — May 31 2026 (iteration 111-A) — Inventory export 3-bug pack

Three field-reported bugs on the Inventory page, all root-caused and shipped together. Plus a small UX enhancement (exports now respect the active filter).

**Bug 1 — Multi-group filter did nothing for >1 group.**
`Inventory.js:46` was sending only `selectedGroups[0]` to `/inventory/items` despite the multi-select checkboxes. Backend `/inventory/items` accepted a single `stock_group` string only.
- Backend: `stock_group` query param now accepts a CSV (`stock_group=A,B,C`) → built as `{"$in": [...]}` when 2+ groups. Single-value behaviour preserved.
- Frontend: `selectedGroups.join(',')`.

**Bug 2 — CSV export returned an empty file.**
`services/export_service.export_to_csv()` wrapped a `BytesIO` in `TextIOWrapper`. On function return, GC closed the underlying `BytesIO` before FastAPI could stream the bytes. Wrote a deterministic version: build the CSV as a `StringIO`, then `getvalue().encode('utf-8-sig')` into a fresh `BytesIO`. The BOM also helps Excel auto-detect UTF-8.

**Bug 3 — Excel button saved file with `.excel` extension.**
`Inventory.js` was using `inventory_report.${format}` — `format='excel'` produced `inventory_report.excel`. Also surfaced a latent backend crash: `openpyxl` rejected the `aliases` field (a list) with *"Cannot convert [] to Excel"*, so the XLSX byte stream was actually the JSON error blob renamed.
- Frontend: `extMap = { csv: 'csv', excel: 'xlsx', pdf: 'pdf' }` → correct file extension on save.
- Backend: `export_to_excel` now coerces lists/tuples → comma-joined strings, dicts → `str(value)`. Numeric alignment preserved.

**Enhancement — exports honour the current filter.**
`/reports/export` now accepts a `filters` body block with `category / stock_group (CSV) / root_stock_group / abc / search`. The same Mongo query that drives the on-screen list is applied to the export. Filename no longer claims `_FY` since the rolling-window work hasn't landed yet, but the data shown ⇆ data exported invariant now holds.

**End-to-end smoke** (live preview backend, demo tenant):
- `/api/inventory/items?stock_group=Belts` → 1 item, group=Belts ✓
- `?stock_group=Belts,Batteries` → 3 items, groups={Belts,Batteries} ✓
- `?stock_group=Belts,Batteries,Bearings` → 4 items, 3 distinct groups ✓
- `/reports/export?format=excel` filtered → 3-row XLSX, header row + 2 group values ✓
- `/reports/export?format=csv` filtered → 1-row CSV with BOM ✓
- `/reports/export?format=pdf` → 93 KB, starts with `%PDF` ✓

**Tests**: `test_iteration111_inventory_export.py` — 8 source + integration tests, all pass. Total green suite: **101/101 across iter-100..111**.

## Shipped — May 23 2026 (iteration 110) — Employee toggle + Salesman copy + Beat-Run order/payment + Close-Day + Day report
Five new user-facing features:

### Feature 1 — Employee Activate/Deactivate toggle
- `PUT /api/auth/users/{username}/toggle-active` (admin-scoped, tenant-isolated, blocks self-toggle, blocks toggling admins).
- Deactivated employees / salesmen / dispatch are blocked from logging in with *"Your account has been deactivated. Contact your admin."*. Their email stays reserved in `users` collection so admin cannot recreate the same email.
- ProfileModal → Employees tab: per-row Deactivate/Reactivate button + DEACTIVATED pill on inactive rows.
- BONUS: when admin's subscription expires, employees now see *"Your organization's FLOWRA subscription has expired. Please ask your admin (NAME) to renew. Access will resume automatically once renewed."* instead of the old generic "Please renew" message intended for admins.

### Feature 2 — Salesman Copy-from-another
- `POST /api/salesman/copy-from` — admin can copy customer mapping (per FY) and/or beat plan from one salesman to another with optional `release_source` flag (clears the FY mapping on the source — used when a salesman leaves).
- Single-salesman-per-customer invariant is preserved by the `release_source` flag (avoids the conflict guard in `save_salesman`).
- UI: "Copy from…" button on every Manage Salesmen row → modal with source dropdown + 3 checkboxes (Customers / Beats / Release source) + FY selector.

### Feature 3 — Beat Run order/payment + Close Day
- Each `beat_runs.planned[]` and `unplanned[]` entry now carries `order_collected: bool|null` and `payment_collected: bool|null`. Run docs carry `closed_at` and `closed_by`.
- `POST /beat-run/check-in` and `/beat-run/add-unplanned` REJECT (with structured error) any visited check-in that doesn't include both booleans.
- New `POST /beat-run/close-day` — salesman locks today's run (server-enforced). New `POST /beat-run/reopen-day` (admin-only with audit log) — admin can undo a premature close.
- UI rewrite of BeatRunView: per-row "Mark Visited" expands an inline form with Order/Payment Yes-No buttons + optional notes + Confirm Visit. Sticky red "Close Day" button at the bottom.

### Feature 4 — Unplanned visit with existing-customer dropdown
- BeatRunView Unplanned section now has TWO modes — "New prospect" (free-text) and "Existing customer" (HTML5 `<datalist>` combobox populated from `/api/salesman-orders/my-customers`, scoped to the salesman's mapped customers for the current FY).
- Unplanned visits carry `is_existing_customer: bool` flag so the reports can distinguish EXISTING from NEW prospects.

### Feature 5 — Per-day PDF/Excel report + Monthly export new columns
- New `GET /beat-run/day-report/export?run_date=YYYY-MM-DD&format=pdf|excel` — PDF uses FLOWRA Insights branding + tenant admin's company name as title. Columns: Party Name · Visit Time · Order Collected · Payment Collected · Type.
- Salesman BeatHistoryView: date-range filter + per-row PDF + Excel buttons + same buttons in the run-detail view.
- Existing `/beat-run/monthly-report/export` Excel extended: Raw Runs sheet gains 2 columns (Order Collected, Payment Collected); By-Salesman sheet gains 4 columns (Orders Collected, Payments Collected, Order Conv %, Payment Conv %); Summary sheet gains 4 new metrics. `_summarize_runs()` helper now computes the order/payment conversion rates.

### Tests
- `test_iteration110_employee_salesman_beatrun.py` — 15 source-asserting tests, all pass.
- Testing agent ran 16 live integration tests against the public preview backend: **31/31 pass, zero bugs found**. Tenant isolation verified end-to-end. Frontend UI walkthrough was blocked only by the preview-pod reCAPTCHA (not a code issue); all data-testids present in the rendered DOM.
- **Total green suite: 77/77 across iter-100..110.**

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

## Iteration 120 (11 July 2026)
- **P0 FIX — Dashboard top-panel flicker on auto-refresh** (`/app/frontend/src/pages/Dashboard.js`)
  * Root causes: `StatCard` was defined *inside* Dashboard (new component type per render → unmount+remount) AND `fetchData()` unconditionally set `loading=true`, which combined with `{!loading && <StatCards>}` guards made the entire top panel vanish for every 30-s refresh cycle.
  * Fix (a): Hoisted `StatCard` above `Dashboard` for stable identity.
  * Fix (b): `fetchData({ silent })` — auto-refresh interval and manual Refresh button both pass `silent:true`; `loading` only toggles on initial mount.
  * Regression locked in: `/app/backend/tests/test_iteration120_dashboard_flicker_fix.py` (static source assertions).
  * Verified live: 4 stat cards remained mounted at 50/100/200/400/800 ms after Refresh click.
- **P1 — Resource PDFs regenerated** from `scripts/generate_flowra_pdfs.py`:
  * `FLOWRA_Presentation.pdf`, `FLOWRA_Customer_Questionnaire.pdf`, `FLOWRA_Training_Booklet.pdf`, `FLOWRA_Deployment_Guide.pdf`, `FLOWRA_Coming_Soon.pdf`, `FLOWRA_Social_Media_Kit.pdf` — all rebuilt with May 2026 content (Beat Run, A/B/C/D, CA Corner Tally-parity, Dispatch mirror view, Backups, Salesman Dashboard, Tally Sync v9.6.0).
  * **Guard-rail:** removed the What's-New builder from the master generator's `__main__` (with a clear comment) — the JSON-driven `generate_whats_new_pdf.py` (fed by `whats_new.json`, the single source of truth) is the sole owner of `FLOWRA_Whats_New.pdf`. Prevents recurrence of the July 11 accidental clobber.



## Iteration 121 (11 July 2026) — Export Bugs Sweep
Fixed 5 reported export/UI bugs on the useradmin dashboard:

1. **Sales PDF/Excel export → "Not Found"** — `Sales.js` was hitting a non-existent `GET /api/export/sales`. Switched to `POST /api/reports/export` (same endpoint Inventory uses) with `report_type: 'sales'`. Also corrected the FY filter — `sales_vouchers` doesn't store `fy` as a scalar; we now post-filter via `filter_vouchers_by_fy()`.
2. **CRM Targets Excel refused to open** — payload field-name mismatch + JSON error body served as blob. Frontend now remaps `last_fy_sales/target_amount/achieved_amount/achievement_percentage` → the backend's expected keys; both Sales and Targets exports now sniff `content-type` and toast on JSON error responses instead of writing garbage to `.xlsx`.
3. **CRM Targets "All Customers" dropdown filter ignored** — the outstanding tab honoured `selectedGroup`, but the targets block never applied it. Wrapped the targets block in an IIFE that computes `filteredTargets` (group / state / fuzzy search) and passes those to both the table AND the Excel export. Added a "X of Y" visible-count badge.
4. **CRM Payment Behavior column mis-alignment** — root cause: `.data-table td.numeric { text-align: right }` existed but no matching `.data-table th.numeric` rule → headers stayed left-aligned above right-aligned cells. Added the missing CSS rule. Also fixed the Pay Ratio flex to use `justify-end`.
5. **Inventory PDF header showed "Anonymous" / "FLOWRA Report"** — `ExportService.export_to_pdf/excel/csv` now accept a `company_name` param; `routes/ai_reports.py` and CRM Outstanding/Targets endpoints resolve the useradmin's synced company name from `db.sync_status` (fallback via `id_mapping_service.get_company_name`) and pass it, so PDF/Excel/CSV all show `ASA AUTOTECH INDIA PRIVATE LIMITED` as the banner.

Regression: `/app/backend/tests/test_iteration121_export_bugs.py` — 11/11 pass.

## Iteration 122 (11 July 2026) — Readable Export Columns
Follow-up enhancement to iter-121. `/api/reports/export` (Sales + Inventory, all three formats — PDF/Excel/CSV) previously dumped raw MongoDB documents including `tenant_id`, `company_id`, `last_updated`, serialised `items` list and `ledger_entries` list — an unusable file to hand a customer.

Added a projector `_project_export_rows(report_type, rows)` in `routes/ai_reports.py` that maps DB documents to business-user columns matching what shows on-screen:

- **Sales**: `Date | Voucher # | Reference # | Customer | Salesman | Voucher Type | Destination | Dispatch Through | Items | Amount (Rs)`. Multi-line items collapse into a single readable cell: `"POWER 20W40 CF4 5LT (4PC) x4 @1412; SHAKTI GL4 20L x10 @5381"` (top 5 + `+N more`).
- **Inventory**: `Item Name | Part # | ABC | Category | Stock Group | Unit | Quantity | Reorder Level | Sale Price (Rs) | Purchase Price (Rs) | Stock Value (Rs) | Aliases`.

Company-name banner from iter-121 preserved on all three formats. Regression: `test_iteration121_export_bugs.py` now covers 15 checks (11 iter-121 + 4 iter-122) — all green. Internal fields (`tenant_id`, `company_id`, `_id`) explicitly asserted to NOT leak into export headers.


## Iteration 123 (14 July 2026) — FLOWRA Academy kickoff
User approved 30-lesson tutorial programme: Hinglish (business-owner tone), Indian-English female voice, FLOWRA branding, user uploads finished MP4s to their own YouTube channel.

**Shipped today:**
- Integration playbook obtained for OpenAI TTS via Emergent LLM key (`emergentintegrations.llm.openai.OpenAITextToSpeech`, `tts-1-hd` for production quality).
- Voice-sample generator: `/app/tutorials/pipeline/generate_voice_samples.py` produces the same Hinglish sample in 3 female voices (**coral / nova / shimmer**). MP3s deployed at `/app/frontend/public/tutorials/voice-samples/*.mp3`.
- Lesson-01 Hinglish script drafted: `/app/tutorials/scripts/lesson-01-flowra-kya-hai.md` (voiceover text, on-screen captions, shot list, thumbnail brief, YouTube metadata, cheat-sheet brief).
- In-app **FLOWRA Academy** page at `pages/Tutorials.js`, wired into nav under `Academy` (GraduationCap icon) and `PageRenderer` (`case 'tutorials'`). Displays:
  * FLOWRA-branded hero (navy → blue gradient)
  * Voice-sample chooser — 3 Play buttons, mutually exclusive audio playback
  * Full 30-lesson roadmap across 6 tracks (Getting Started / Owner / Ops Manager / Salesman / CA / Desktop Agent), each row tagged status (Live / In Progress / Planned) with lesson length, YouTube link stub, chevron.
- Folder scaffolding created for the pipeline:
  * `/app/tutorials/{scripts,voiceover,voice-samples,recordings,final,reels,cheat-sheets,youtube-metadata,pipeline}`

**Awaiting from user:** voice pick (Coral / Nova / Shimmer). Once received we lock the voice and mass-produce all 30 lessons.

**Next steps (post-approval):**
1. Build screencast recorder using Playwright — `/app/tutorials/pipeline/record_screencast.py`.
2. Build FFmpeg composer that muxes screencast + voiceover + subtitles + FLOWRA intro/outro.
3. Ship Lesson-01 end-to-end as pilot; iterate on tone feedback.
4. Batch remaining 29 lessons (3/day cadence, 10 batches).
5. Ship first-login coach-mark tour and "?" deep-linked help drawer.


## Iteration 124 (14 July 2026) — Male voice switch + Lesson 01 audio produced
User switched from female → male voice pool and asked to start production.

**Delivered:**
- Regenerated 3 voice samples in the male pool: `echo / onyx / ash` (retired coral/nova/shimmer files).
- New pipeline script `/app/tutorials/pipeline/produce_lesson_voiceover.py` reads any lesson MD, extracts the `## VOICEOVER SCRIPT` block, and renders full voiceover via OpenAI `tts-1-hd`. Voice controlled by env var `FLOWRA_ACADEMY_VOICE` (default `echo`).
- **Lesson 01 full voiceover produced** (`echo`, HD MP3, ~75 sec, 1.1 MB) — deployed at `/app/frontend/public/tutorials/lessons/lesson-01.mp3`.
- Academy page updated: voice cards now show `echo / onyx / ash`; Lesson 01 row shows a blue **AUDIO READY** pill + inline `▶ Voiceover` link that opens the MP3 in a new tab. Copy tells the user we've defaulted to Echo and invites a swap.

**Awaiting from user:** listen to Lesson 01 in Echo, either confirm to keep Echo for all 30 lessons or reply with `onyx` / `ash` to swap. Once confirmed, next steps: Playwright screencast recorder + FFmpeg composer + Lesson 01 final MP4.


## Iteration 125 (14 July 2026) — FLOWRA Academy: audio + video for all 30 lessons + completion tracking

**User approved:** Onyx voice locked, per-user completion tracking (green tick at ≥ 60% watch), full audio + video production for all 30 lessons.

### Shipped end-to-end

**Content — all 30 lessons produced:**
- Canonical manifest at `/app/tutorials/pipeline/lessons_manifest.py` — 30 Hinglish voiceover scripts (business-owner tone, 100-180 words each) across 6 tracks: Getting Started (4), Owner (5), Ops Manager (8), Salesman (4), CA (4), Desktop Agent (5).
- **30 voiceover MP3s** (Onyx, `tts-1-hd`) at `/app/tutorials/voiceover/lesson-{01..30}.mp3` — public copies at `/app/frontend/public/tutorials/lessons/*.mp3`.
- **30 branded MP4 videos** (1920×1080 h264+aac) at `/app/tutorials/final/lesson-{01..30}.mp4` — public copies at `/app/frontend/public/tutorials/lessons/*.mp4`. Total 47 MB.
- Each video: FLOWRA navy→blue gradient slide, lesson number badge, wrapped title, subtle 2% Ken-Burns zoom, embedded Onyx voiceover, aac 192kbps.
- **YouTube upload pack** at `/app/tutorials/youtube-metadata/` — 30 per-lesson `.txt` files + one aggregated `all-lessons.md` (also served publicly at `/tutorials/youtube-upload-pack.md`). Titles, descriptions, tags all copy-paste ready.
- Public manifest at `/tutorials/manifest.json` — voice=onyx, 30 lessons with audio_url + duration_hint.

**Pipeline scripts (repeatable for future updates):**
- `generate_voice_samples.py` — regenerates the 3 male samples (echo/onyx/ash).
- `produce_lesson_voiceover.py` — renders a single lesson from its MD script.
- `generate_all_voiceovers.py` — batch renders all 30 → MP3 + manifest.json.
- `compose_all_videos.py` — batch renders all 30 → MP4 with Ken-Burns.
- `build_youtube_metadata.py` — builds copy-paste pack.

**Completion tracking (backend + frontend):**
- New route `/app/backend/routes/academy.py` — `POST /api/academy/progress` (upsert; keeps max()), `GET /api/academy/progress` (returns `{lessons, completed_count, threshold_pct: 60}`). Mongo collection: `academy_progress`. `completed_at` timestamp set only on first threshold crossing and preserved on scrub-back.
- Registered in `server.py` include-router list.
- Frontend `/app/frontend/src/pages/Tutorials.js` fully rewritten:
  * Hero now shows a live `X / 30 lessons completed` counter + green progress bar (from `/api/academy/progress`).
  * Voice sample chooser shows Onyx card with blue ring + "LOCKED" pill.
  * Every lesson row has a green tick + "COMPLETED" pill once threshold crossed.
  * `▶ Watch` button opens a full-screen modal video player (autoplay, native controls).
  * `🔊` audio-only button for quick preview.
  * Modal video sends progress every 5 sec to backend + on ended. Same for audio-only playback.

**Regression:** `/app/backend/tests/test_iteration125_academy.py` — 60 parametrised + 5 focused tests. All green.
  * 30/30 MP3s > 100 KB
  * 30/30 MP4s > 300 KB, all 1920×1080 h264+aac
  * Manifest.json = onyx + 30 lessons
  * POST progress with 30% → 75% → 20% keeps `completed=True, progress_pct=75.0`, `completed_at` preserved
  * GET returns `threshold_pct=60.0, completed_count >= 1`
  * Public MP4s HTTP 200 with content-length > 300 KB (lessons 1 / 15 / 30 spot-checked)

**Voice sample public URLs (for reference / final QA):**
- `/tutorials/voice-samples/{echo,onyx,ash}.mp3`
- `/tutorials/lessons/lesson-{01..30}.mp3`
- `/tutorials/lessons/lesson-{01..30}.mp4`
- `/tutorials/manifest.json`
- `/tutorials/youtube-upload-pack.md`

**v2 backlog (Playwright screencast replacement):** current 30 videos are branded slide-with-voiceover (podcast style). v2 can replace individual slides with recorded UI screencasts of the actual app — the Onyx audio track stays identical, so no re-narration needed. Pipeline placeholder is in `compose_all_videos.py` (Ken-Burns rendering approach; screencast recorder can be a drop-in replacement that emits webm→mp4 clips).


## Iteration 126 (14 July 2026) — Academy hardening: role-based visibility, IP protection, burned captions, Instagram Shorts

Addressed 5 user questions:

1. **Per-user isolation** confirmed. `academy_progress` collection uses `user_id = str(user.id or _id or username)` as the compound key. Admin's completion state on Lesson 5 does NOT bleed into any other user's view. Verified in `test_iteration125_academy.py`.

2. **Role-based track visibility.** `pages/Tutorials.js` now imports `useAuth()`. If `user.role` is not `admin/super_admin/useradmin`, only these tracks render: Getting Started (4 lessons) + Salesman (4) + Desktop Agent (5) + one Dispatch card (Lesson 17). Admin/owner sees full 30. A `Lock` badge tells restricted users why they see fewer lessons.

3. **Instagram / YouTube Shorts (9:16 vertical)** — `pipeline/render_shorts.py` produces 1080×1920 MP4s with the same Onyx audio + burned Hinglish captions + persistent watermark. First Shorts published at `/tutorials/lessons/lesson-01-shorts.mp4`. `render_shorts.py all` batch-produces all 30 whenever needed.

4. **IP protection for YouTube.** Every re-rendered video now includes:
   * Top-right corner watermark: `© FLOWRA · flowralive.in` (0.65 alpha, on every frame)
   * Bottom footer: `© 2026 FLOWRA. All rights reserved. Unauthorised re-upload prohibited.`
   * Only public information in the YouTube upload pack (grep audit of `/app/tutorials/youtube-metadata/*` confirms no preview URLs, no admin creds, no `/api` paths, no LLM keys leak).

5. **Text captions with every lesson.**
   * `pipeline/generate_hinglish_subtitles.py` splits the source Hinglish text into ~10–13 caption lines per lesson, distributed proportionally across the known audio duration. Whisper was tried but transcribes into Devanagari; we chose Hinglish source-splitting for accurate spelling.
   * `pipeline/srt_to_ass.py` converts each SRT into a proper ASS file with `PlayResX/Y`, `Alignment=2`, `MarginV`, `BorderStyle=3`. This fixed a libass bug where SRTs with default PlayRes rendered captions at the wrong position.
   * `compose_all_videos.py` now prefers the ASS file (2 variants: `-horizontal.ass` for 16:9, `-vertical.ass` for Shorts). Videos re-rendered — verified caption at bottom of frame for Lesson 01 (`"Mobile se sales dekhni ho outstanding check karna ho..."`).
   * All 30 `.srt` files also served publicly at `/tutorials/lessons/lesson-NN.srt` — user can upload them alongside videos to YouTube for the CC (closed-captions) toggle.

### New pipeline files
- `/app/tutorials/pipeline/generate_hinglish_subtitles.py`
- `/app/tutorials/pipeline/srt_to_ass.py`
- `/app/tutorials/pipeline/render_shorts.py`

### Regenerated content (all in `/app/frontend/public/tutorials/lessons/`)
- `lesson-{01..30}.mp3` (Onyx voiceover)
- `lesson-{01..30}.mp4` (16:9 with baked captions + IP watermark)
- `lesson-{01..30}.srt` + `lesson-{01..30}-horizontal.ass` + `lesson-{01..30}-vertical.ass`
- `lesson-01-shorts.mp4` (9:16 pilot; can batch all 30 via `render_shorts.py all`)
- `/tutorials/youtube-upload-pack.md` — 30 title/desc/tag sets, copyright-safe


## Iteration 127 (15 July 2026) — Real Playwright screencasts (pilot Lessons 1 & 2)

User challenged the earlier "slide-with-voiceover" v1 videos and asked for actual FLOWRA UI screencasts using demo data. Delivered:

**New pipeline:**
- `pipeline/record_screencast.py` — Playwright records 1920×1080 WebM using demo credentials (`demo@flowralive.in / demo2026`). Login bypasses reCAPTCHA by hitting `/api/auth/login` directly and injecting the JWT into `localStorage`. Videos land at `/app/tutorials/recordings/lesson-NN.webm`.
- `pipeline/screencast_playbooks.py` — Per-lesson async playbooks defining the exact click / hover / scroll timeline. Currently: `PLAYBOOKS = {1: lesson_1, 2: lesson_2}`.
- `pipeline/compose_screencast.py` — Muxes WebM + `voiceover/lesson-NN.mp3` + `subtitles/lesson-NN-horizontal.ass` + persistent `© FLOWRA · flowralive.in` watermark. Uses `tpad=stop_mode=clone` to freeze the last frame when video is shorter than audio (Lesson 1: 35s recorded → freeze 15s to match 50s audio).

**Deliverables:**
- `/app/tutorials/final/lesson-01.mp4` — 1902 KB, 50.3 s, **real Sharma Lubricants Dashboard** (39L sales, 35 items, 29 overdue invoices, top customers, FLOWRA Updates panel). Tour: Select Company modal → Dashboard KPI cards → Sales/CRM/Inventory/Analytics tab hovers → scroll to What's New.
- `/app/tutorials/final/lesson-02.mp4` — 1443 KB, 55.5 s, real landing page → Login screen → Select Company modal.
- Both files re-deployed under `/app/frontend/public/tutorials/lessons/lesson-{01,02}.mp4` (bytes-in-place replacement, same URLs).

**All safety-nets in place:** demo tenant with 3 fake companies (no real customer names), FLOWRA copyright watermark on every frame, ASS captions synced to Onyx voiceover, footer copyright strip.

**Remaining work when user approves style:**
- Write 28 more Playwright playbooks (Lessons 3-30), one per feature area.
- Estimated 20-40 min per playbook × 28 lessons = 10-18 hrs across multiple sessions.
- Pipeline is production-ready — each new lesson is just a playbook file + one `record` + `compose` invocation.


## Iteration 130 (15 July 2026) — Busy Agent v1.4 — OLE DB primary + ODBC fallback

Unblocked the -1905 ODBC password issue by wiring Busy Solutions' official OLE DB provider (BSSData) as the preferred connection path.

**Code changes:**
- `desktop-agent/build-kit-busy/flowra_busy_agent.py`
  * `VERSION → "1.4.0"`
  * New `_OLEDBConnectionAdapter` + `_OLEDBCursor` classes — pyodbc-shaped facade over `ADODB.Connection` so downstream `iter_rows()` / `count_rows()` need zero branching
  * New `_try_oledb()` method — walks `BSSData.6.0 → 5.0 → 4.0` provider IDs, connects with the user's regular Busy login (username + password + company). Returns `None` on non-Windows or when provider isn't registered.
  * `_get_connection()` refactored: **OLE DB first**, gracefully falls back to the v1.3 ODBC password chain when provider unavailable (Basic edition, Demo build, missing Data Connectivity add-on)
  * Records `_connection_method` (`"OLE DB"` or `"ODBC"`) so the GUI can show a status pill
- `desktop-agent/build-kit-busy/flowra_busy_gui.py`
  * Settings → Busy Data Folder section adds 3 new inputs: **Busy login username**, **Busy login password**, **Busy company name** (blue "preferred" style)
  * Legacy encryption-password field kept below as fallback
  * All 3 new fields exported as env vars (`BUSY_USER`, `BUSY_LOGIN_PASSWORD`, `BUSY_COMPANY`) to the agent process
- `desktop-agent/build-kit-busy/requirements.txt` — adds `pywin32>=306; sys_platform == "win32"`
- `desktop-agent/build-kit-busy/agent.spec` — hiddenimports += `win32com`, `win32com.client`, `pywintypes`, `pythoncom`

**Regression:** `/app/backend/tests/test_iteration130_busy_agent_v14_oledb.py` — 8/8 green (structural checks; the OLE DB runtime path requires a licensed Windows Busy install for validation).

**Still pending (Enterprise validation):**
1. User to test v1.4 on Krishna Sales licensed Busy 21 Enterprise (with Data Connectivity module).
2. If OLE DB path fails, capture the exact `com_error` text so we can iterate on the connection-string variants.

**Not yet done (Phase-3 backlog per user's proposal):**
- Option 2 (Advanced XML export) — user picked (b), so XML path is deferred. Can be revisited later as a universal-compatibility layer.



## Shipped — Feb 16 2026 (iteration 131) — Busy Agent v1.4.1 daemon-crash fix

**Root cause of the v1.4.0 crash reported by user:**
The GUI's `subprocess.Popen(env=…)` dict declared the key `BUSY_COMPANY` twice — once from the auto-detected `company_name` and again from the new v1.4 user-typed OLE DB field `busy_company`. Python dict literals silently drop the first entry, so the empty OLE DB field always won and the daemon booted with `BUSY_COMPANY=""`, tripping the required-vars validator with:

    [daemon] Missing required env vars — cannot start.

**Fixes shipped:**
1. **Daemon env-var collision resolved** — the OLE DB provider's Company= param moved to its own env var `BUSY_OLEDB_COMPANY`. `_try_oledb()` reads it first (falls back to `BUSY_COMPANY` for backward-compat).
2. **Removed the manual "Busy company name" text field** in Settings → Section 2. The company name is now always the auto-detected value from `Detect Company` (same UX as Tally Agent — user's request #3).
3. **Pre-flight validation in `start_agent()`** — instead of spawning the daemon blindly, the GUI now checks each required field (email / password / folder / detected company / starting FY) and pops a warning listing exactly what's missing before Popen fires.
4. **Daemon's own error message is specific** — "Missing: BUSY_COMPANY, BUSY_STARTING_FY" instead of the flat "Missing required env vars".
5. **Windows taskbar icon fixed (user's request #2)** — the "leaf" icon was Tk's default fallback showing up when `iconbitmap` silently failed on some Tk builds. Added `iconphoto()` fallback (loads `flowra_logo.png` → `PhotoImage`) plus `SetCurrentProcessExplicitAppUserModelID("Flowra.BusySyncAgent.1")` so Windows doesn't group under `python.exe`.
6. **Version marker** — VERSION `1.4.1`, AGENT_TAG `busy-1.4.1-oledb-envfix`, GUI APP_VERSION `v1.4.1`.

**Files touched:**
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` — VERSION, AGENT_TAG, `_try_oledb` env read, daemon error message.
- `desktop-agent/build-kit-busy/flowra_busy_gui.py` — APP_VERSION, taskbar icon (iconphoto + AppUserModelID), removed `busy_company_entry` widget, fixed `env.update({…})` duplicate-key bug, per-field pre-flight validation in `start_agent()`.

**Regression tests (16/16 green):**
- `backend/tests/test_iteration130_busy_agent_v14_oledb.py` — refreshed for v1.4.1 config schema (8 tests).
- `backend/tests/test_iteration131_busy_agent_env_fix.py` — new (8 tests): AST-parses the env dict to guarantee no duplicate keys, asserts `BUSY_COMPANY` resolves to `company_name`, checks daemon error specificity, verifies iconphoto + AppUserModelID hardening, verifies the manual company text-field is fully removed.

**Live smoke test:** spawned the daemon in Linux dev mode with a valid env — it now logs `company=ACME Traders` and proceeds to the login step (fails only on the dummy password, as expected). Old build died before login.

**User next steps:** rebuild `FlowraBusyAgent.exe` via `build.bat` on Windows and re-test on the licensed Busy 21 Enterprise install. The v1.4.1 daemon should no longer refuse to start once the user has clicked Detect Company + Detect FYs.

## Shipped — Feb 16 2026 (iteration 132) — Busy Agent v1.4.2 connection diagnostic

**Context:** after the v1.4.1 daemon-crash fix landed, the user's licensed Busy 21 Enterprise install still couldn't sync — both drivers were missing on the target Windows PC. The daemon reported the driver error in the log tail but it was buried behind stack traces, and users had no way to preflight the environment before spending time on a full sync.

**Shipped in v1.4.2:**
1. **`probe_busy_drivers()` module-level helper** (`flowra_busy_gui.py`) — three-section diagnostic:
   - **OLE DB (BSSData)** — tries each provider (`BSSData.6.0/5.0/4.0`) with the user's Busy login credentials. Reports which one registered (or the exact COM error if none).
   - **ODBC (Microsoft Access Database Engine)** — lists `pyodbc.drivers()` and picks any driver containing "Access Driver".
   - **Live `.bds` open test** — if the OLE DB path didn't already succeed, tries the ODBC path against the auto-picked `db.bds` file, iterating through the standard Busy password chain (`bs21DBFile`, `Bus1Wor$1D`, `busyww`, `busy`, `""`) or the user's explicit override. Reports which method + which password worked.
2. **"🧪 Test Busy Connection" button** — sits at the bottom of Settings → Section 2 (green accent, next to the fallback password field). Runs in a background thread with an indeterminate progress spinner modal so the UI stays responsive.
3. **Diagnostic results modal** — three white cards with green ✓ / red ✗ icons per capability, plain-English subtitles, and an inline `⬇ Download Access Driver (Microsoft)` button that opens https://www.microsoft.com/en-us/download/details.aspx?id=54920 via `webbrowser.open()`. Cross-platform stdlib only — no new deps.
4. **Linux dev-mode graceful fallback** — the probe returns a well-formed stub dict on non-Windows so the module can be imported and unit-tested on CI without crashing.
5. **Version markers** — VERSION `1.4.2`, AGENT_TAG `busy-1.4.2-conn-diagnostic`, GUI APP_VERSION `v1.4.2`.

**Files touched:**
- `desktop-agent/build-kit-busy/flowra_busy_gui.py` — new `_pick_test_bds_file()`, `probe_busy_drivers()`, `_test_busy_connection()` handler, `_show_busy_test_results()` modal renderer, "Test Busy Connection" button in Section 2.
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` — VERSION + AGENT_TAG bump.

**Regression tests (21/21 green, 1 skipped for missing libtk on CI):**
- `test_iteration132_busy_conn_diagnostic.py` (new, 6 tests):
  - probe helper exists
  - runtime probe returns stub schema on Linux (importorskip guarded)
  - AST parse verifies probe result-dict schema matches what the modal reads
  - GUI wires the button, handler, and modal
  - Modal links to Microsoft's official Access Driver download page via `webbrowser`
  - Version markers rolled forward to v1.4.2

**User next step:** rebuild `FlowraBusyAgent.exe` and click "🧪 Test Busy Connection" on Section 2 of Settings. The modal will show *exactly* which driver is missing and offer a one-click download. Once both cards go green, click "Save & Start Sync".


## Shipped — Feb 16 2026 (iteration 133) — Daemon-side driver pre-flight banner

**Context:** even after v1.4.2 shipped the "🧪 Test Busy Connection" button, the user's daemon still crashed at Phase 1 with a raw Python stack trace because both Windows drivers were missing on the target PC. The user hadn't clicked the Test button — they hit Start Sync directly. The failure mode looked broken even though the underlying issue was purely environmental (drivers not installed).

**Shipped:**
1. **`_check_busy_drivers_or_banner(folder)` helper** in `flowra_busy_agent.py` — probes both OLE DB (BSSData COM provider registration) and ODBC (`pyodbc.drivers()` for "Access Driver") right after login, before entering the sync loop.
2. **`run_daemon` now bails cleanly on missing drivers** — instead of grinding through a 5-minute retry loop with cryptic stack traces, the daemon returns exit code **2** (distinct from code 1 = missing env vars, code 0 = clean shutdown).
3. **Full-screen install banner** logged with step-by-step instructions:
   - Option A: direct link to Microsoft's Access DB Engine 54920 download page + "run it, accept defaults, no reboot needed"
   - Option B: enable Busy's paid Data Connectivity module inside BusyWin
   - Reference to the "🧪 Test Busy Connection" button for re-checking
4. **Non-Windows dev safety** — the helper short-circuits to `True` on Linux/Mac so the mdb-export dev path stays working.

**Files touched:**
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` — new `_check_busy_drivers_or_banner()` helper; `run_daemon()` calls it after login and returns 2 on failure.

**Regression tests (25/25 green + 1 skipped):**
- `test_iteration133_daemon_driver_preflight.py` (new, 4 tests):
  - Helper exists and is called by `run_daemon`
  - Banner lists both install options (54920 URL + Data Connectivity path)
  - Bail path uses `return 2` (distinct from env-var-missing code 1)
  - Non-Windows short-circuits to `True` (preserves Linux dev mode)

**User next step:** the daemon-side code is complete. The only remaining action is to **install ONE driver on the Windows PC** — 90-second free Microsoft download → https://www.microsoft.com/en-us/download/details.aspx?id=54920. No agent rebuild strictly required (the v1.4.2 exe you already tested handles this once the driver appears), but a rebuild will pick up the new pre-flight banner so future users see a clean install message instead of a stack trace.


## Shipped — Feb 16 2026 (iteration 134) — CA Corner: CMA + Investor Pitch Deck generator

**Context:** Academy Lesson 8 promised a "Generate Pitch Deck" button that never existed in the UI. Additionally, the user attached a real CMA (Credit Monitoring Arrangement) — a bank submission document — for Krishna Sales Corporation and asked whether FLOWRA could auto-generate CMA from Tally data. Analysis confirmed **~70% of every CMA is mechanical accounting derivable directly from Tally**, with only ~10 assumption inputs needed for projections. This unlocks a recurring revenue lever (CAs traditionally charge ₹15–50k per CMA per year per company).

**Shipped:**

1. **Backend engine** (`backend/services/ca_reports_engine.py`, ~1000 lines) — pure, DB-free business logic:
   - `HistoricalFY` / `Assumptions` / `CompanyMeta` dataclasses.
   - `project_future_fys(hist, assumptions, n_future=3)` — Y1/Y2/Y3 projections built by compounding user growth % against historical ratios (purchase/sales, wages/COGS, dep/sales, SG&A/sales, interest/sales). Working-capital lines re-sized from user's target days.
   - `compute_form_ii` / `compute_form_iii` / `compute_form_v_mpbf` — pure formula computations per RBI Tandon Committee guidelines.
   - `build_cma_pdf` — 5-form ReportLab PDF (cover + Form II P&L + Form III BS + Form IV CA/CL + Form V MPBF Method 1 & 2 + Form VI Funds Flow + Methodology page).
   - `build_cma_xlsx` — 5-sheet OpenPyXL workbook (one form per sheet + Methodology sheet + Assumptions sheet).
   - `build_pitch_pdf(teaser=False|True)` — 16-page investor deck OR 10-page teaser, dynamically populated from tenant's real Tally numbers (revenue journey, margin trend, BS strength, cash flow health, ratios summary, use of proceeds, management/market/growth-levers/risks, methodology).
   - `build_projections_xlsx` — 8-sheet editable model (Revenue, Purchases, SG&A, Depreciation, Working Capital, MPBF, Assumptions, Methodology).
   - **Every PDF page carries the company name in the header and "Auto-generated by FLOWRA · <ISO timestamp> · Page X of Y" in the footer.** Every XLSX sheet appends the same footer stamp on the final row. Enforced via `_make_canvas_stamper` canvas hook wired into every `doc.build()` call.
   - **Methodology page is inside every generated file** — 6 sections explaining exactly which Tally collection populates each historical row, which formula computes each projected cell, how MPBF Methods 1 & 2 work, and audit provenance ("Every historical cell in this report can be reconciled row-by-row against the corresponding Tally report inside your accounting software").

2. **Backend routes** (`backend/routes/ca_reports.py`, 7 endpoints) — with strict security:
   - `_require_useradmin(request)` — 401 without JWT, **403 with `"role != 'admin'"`** message. Verified via live curl that `salesman` gets `"This report is available only to the tenant owner (useradmin role). Your role is 'salesman'."`.
   - Every DB query filtered by both `tenant_id` AND `company_id` via `_tenant_company_query()`.
   - Sensitive assumption fields (`gstin`, `pan`, `msme_regn`, `bank_name`) are **Fernet-AES-128 encrypted** at rest (`_encrypt_assumptions()` / `_decrypt_assumptions()` — reuses the existing `services.encryption_service` cipher).
   - Endpoints: `POST /api/ca-reports/preview`, `GET|POST /api/ca-reports/assumptions`, `POST /api/ca-reports/cma/pdf`, `.../cma/xlsx`, `.../pitch/pdf`, `.../pitch/teaser`, `.../pitch/xlsx`.
   - Streams binary responses with `Content-Disposition: attachment; filename="CMA_<Company>.pdf"` etc.

3. **Frontend** (`frontend/src/pages/CAReports.jsx`) — new panel mounted as a sub-tab **"Bank & Investor Reports"** inside CA Corner:
   - Tab visibility gated on `userRole === 'admin'` (employees/salesmen/dispatch never see it — enforced at both tab-render and API level).
   - 14 assumption inputs + 5 bank/regulatory inputs (Fernet-encrypted at rest badge shown to user).
   - Live preview table (10 key metrics × all FYs) — expandable, drilling shows historicals from Tally alongside projected values.
   - 5 download buttons: CMA PDF, CMA XLSX, Pitch PDF (16-page), Teaser PDF (10-page), Projections XLSX (8-sheet). All `data-testid` tagged.
   - Save-assumptions button (writes encrypted doc to `ca_report_assumptions` MongoDB collection).

4. **New MongoDB collection**: `ca_report_assumptions` — one document per (tenant_id, company_id). Encrypted sensitive fields at rest.

**Files touched/created:**
- NEW `backend/services/ca_reports_engine.py` (1000+ lines)
- NEW `backend/routes/ca_reports.py` (350 lines)
- NEW `frontend/src/pages/CAReports.jsx` (~400 lines)
- MODIFIED `backend/server.py` — routed the new module
- MODIFIED `frontend/src/pages/CACorner.js` — added the sub-tab, gated on userRole
- MODIFIED `frontend/src/components/PageRenderer.js` — passes userRole prop to CACorner
- NEW `backend/tests/test_iteration134_ca_reports.py` (8 tests, all green)

**Regression tests (8/8 green):**
- Projections engine produces expected FY labels (2023-24 → 2025-26) + net-sales CAGR compounds correctly
- Form II / III / V computations return dict-shaped totals with correct field names
- All 5 downloadable artifacts produce non-empty binaries (>1000 bytes each)
- Route file has all 7 endpoints, uses `_require_useradmin`, returns 403 on non-admin
- Encrypted assumptions round-trip: encrypt then decrypt returns the original strings; numeric fields pass through unencrypted
- Every generated file carries the FLOWRA footer + company header (`_make_canvas_stamper` wired in)
- Methodology blocks embedded verbatim inside every output file
- Frontend gates the tab on `userRole === 'admin'` and exposes all 5 download-button testids

**Live verification via curl:**
- Admin JWT + preview → returns `"No FY data synced yet"` (correct — the ASA test tenant has no FY data)
- Salesman JWT + preview → returns **`"This report is available only to the tenant owner (useradmin role). Your role is 'salesman'."`** — 403 role guard confirmed end-to-end.


## Shipped — Feb 16 2026 (iteration 135) — CA Reports: Prior-Year Manual Entry

**Context:** After v134, if a tenant only had 1 (or 0) FYs synced from Tally the CMA still couldn't produce 2 historicals — the RBI submission format requires 2 audited FYs. User asked for a form to manually type in prior-year audited numbers so the CMA still ships with 2 historicals even for new deployments.

**Shipped:**
1. **New MongoDB collection `ca_manual_historicals`** — one document per (tenant_id, company_id, fy_label). Sensitive monetary fields (net_sales, purchases, sga_expenses, depreciation, interest, provision_for_tax, sundry_creditors, term_loans, unsecured_loans, proprietors_capital, reserves_surplus, cash_bank_balance, receivables_domestic, inventory_finished, gross_block, etc. — 23 fields) are **Fernet-AES-128 encrypted at rest** via `_encrypt_manual` / `_decrypt_manual`. `fy_label` remains cleartext (natural key needed for lookup).
2. **3 new endpoints**, all guarded by `_require_useradmin` (verified 403 for salesman on all three methods):
   - `GET /api/ca-reports/manual-historicals` — lists all manual FYs for the selected company
   - `POST /api/ca-reports/manual-historicals` — upsert one FY (validates `fy_label` matches `YYYY-YY` pattern, coerces numerics, encrypts before storage)
   - `DELETE /api/ca-reports/manual-historicals/{fy_label}` — soft delete
3. **Merge logic in `preview_report` + `_assemble_fys`** — Tally-synced FYs and manual FYs are combined, deduped by `fy_label` (Tally wins on collision so re-syncing later doesn't overwrite user-audited numbers), sorted chronologically, and capped at `n_hist`. `preview_report`'s "No FY data" early return now checks BOTH synced FYs AND manual FY count before bailing.
4. **Frontend UI** (`CAReports.jsx`) — new `<ManualHistoricalsSection>` card:
   - Table of existing manual entries with FY / Net Sales / Purchases / Debtors / Creditors / Capital columns + per-row Edit and Delete buttons
   - "Add prior year" button opens a full-screen modal `<ManualHistoricalForm>` with 17 fields split into two sections: P&L (6 fields) and Balance Sheet (10 fields) + FY label
   - Empty-state fallback: when preview fails because tenant has 0 data anywhere, the section still renders so the user can add their first manual FY without needing Tally sync
   - "Encrypted at rest" badge visible to the user
   - Confirm-before-delete dialog via `window.confirm`
5. **Data flow update**: on save/delete, both `loadManual()` AND `loadPreview()` refetch in parallel so the historicals-preview table + projection engine + download buttons all reflect the change immediately.

**Live curl verification:**
- Admin POST 2 manual FYs (2019-20, 2020-21 with real Krishna-style numbers) → preview now returns 2 historicals + 3 projections (2021-22 → 2023-24 auto-projected at 25% CAGR from the manual data alone) — with **zero synced Tally FYs**.
- CMA PDF download works end-to-end from manual-only historicals (23,481-byte `%PDF-1.4` streamed).
- Salesman role gets 403 on all three methods (GET/POST/DELETE) with the exact "This report is available only to the tenant owner" message.
- Cleanup DELETE calls return `{"deleted": 1}` on success.

**Files touched:**
- `backend/routes/ca_reports.py` — added 3 endpoints, encryption helpers, merge logic in preview + `_assemble_fys`.
- `frontend/src/pages/CAReports.jsx` — added `ManualHistoricalsSection`, `ManualHistoricalForm` components + state.

**Regression tests (16/16 green combining iter-134 + iter-135):**
- Manual endpoints exist and all use `_require_useradmin`
- `_MANUAL_ENCRYPTED_FIELDS` covers every monetary field the manual-entry form exposes
- Encryption round-trip preserves float fidelity (540.0 → encrypted string → 540.0)
- Preview endpoint's "no data" bail relaxes when `ca_manual_historicals` count > 0
- `_assemble_fys` merges Tally + manual with Tally winning on collision, sorted by fy_label
- Frontend has all 6 core testids (section, add button, modal, fy-label input, save, cancel) + delete/edit buttons + confirm-before-delete


## Shipped — Feb 16 2026 (iteration 136) — CMA Annual Reminder + CSV Bulk Import

### 1. CMA Annual Reminder (email 60 days before anniversary)

**Why:** CMAs get submitted to banks once a year for working-capital renewal. Without a nudge, tenants forget and let the reminder pass, then scramble to pull one together at the last minute (or worse, resubmit last year's numbers). This closes that loop.

**Data flow:**
1. Every call to `/api/ca-reports/cma/pdf` or `/api/ca-reports/cma/xlsx` upserts a row in the new `ca_report_generations` collection: `{tenant_id, company_id, artifact:"cma", last_generated_at, last_artifact_kind, last_generated_by, reminder_sent_at:null}`. Reminder flag resets on each fresh generation.
2. Background sweep `sweep_cma_reminders()` runs every 24h from an `asyncio.create_task(...)` spawned in `server.py`'s `startup_event`. Cadence + idempotency:
   - Finds rows where `last_generated_at + 305 days ≤ now` AND `reminder_sent_at` is either null or older than `last_generated_at`.
   - Loads the tenant's useradmin (`role="admin"`), computes `days_left = anniversary - now`.
   - Sends an HTML email via existing Resend integration (`services.email_service.send_email`) tagged `"cma-reminder"`. Subject: "Time to renew your working-capital limit — <Company Name>". Body carries FLOWRA branding + last-generated date + days-until countdown + a CTA that deep-links to `/ca-corner`.
   - Marks `reminder_sent_at = now` only on send-success (so a Resend outage → retry on next sweep).
3. New endpoint `GET /api/ca-reports/reminders/status` returns `{last_generated_at, next_reminder_at, days_until_reminder, reminder_sent_at, reminder_lead_days=60}` for the UI card.

**UI:**
- New `<ReminderStatusCard>` at top of the Bank & Investor Reports panel:
  - Grey neutral state ("not yet armed") when no CMA has ever been generated
  - Blue armed state showing `next reminder in N days`
  - Red DUE state when `days_until_reminder ≤ 0`
  - Muted "already sent" state when `reminder_sent_at` is set
- After every successful CMA download, `loadReminder()` refetches automatically so the countdown resets in real time without a page reload.

**Constants** (`REMINDER_LEAD_DAYS=60`, `CMA_ANNIVERSARY_DAYS=365`) live at module scope in `routes/ca_reports.py` so a single tweak changes both the API contract and the UI copy in one place.

### 2. CSV Bulk Import (potential improvement — shipped)

**Why:** For CAs onboarding an existing client with 3-5 years of audited history, typing each year's 15+ fields into the modal takes ~15 min. Pasting from Excel is 30 seconds.

**Two new endpoints:**
- `GET /api/ca-reports/manual-historicals/csv-template` — streams an empty CSV with every `HistoricalFY.__dataclass_fields__` key as headers + one example row (`2020-21,0,0,…`). The CA opens it in Excel, fills the rows, saves back to CSV, and uploads.
- `POST /api/ca-reports/manual-historicals/import-csv` — accepts `{csv_text: "..."}` OR `{rows: [...]}`. Parses with `csv.DictReader`, validates each `fy_label` matches `YYYY-YY`, coerces every other column to float (blank → 0), Fernet-encrypts and upserts through the same path as the manual-form endpoint. Returns `{written, total_rows, errors: [row-level messages], errors_truncated: bool}` — first 20 errors surfaced verbatim.

**UI:**
- New `<CsvImportModal>` triggered by an "Import CSV" button in the manual-historicals section header.
- Info panel with a "Download blank template" link (triggers the template endpoint).
- File-picker + Import button + inline result panel showing written count and per-row error list (first 5 shown; more collapsed with an italic "…more errors truncated").
- On zero errors, modal auto-closes 800ms after success and both `loadManual()` + `loadPreview()` refetch so the projection engine + table + downloads all reflect the new rows immediately.

### Files touched
- `backend/routes/ca_reports.py` — `_track_cma_generation` helper wired into both CMA endpoints; `GET /reminders/status`; `sweep_cma_reminders()` + `_reminder_html()`; `GET /manual-historicals/csv-template`; `POST /manual-historicals/import-csv`.
- `backend/server.py` — startup event spawns `_cma_reminder_loop` as an `asyncio.create_task` (60s stagger on boot then 24h cadence).
- `frontend/src/pages/CAReports.jsx` — `<ReminderStatusCard>`, `<CsvImportModal>`, wired into both the normal and empty-state renders. `loadReminder()` refreshes after each CMA download.
- NEW `backend/tests/test_iteration136_cma_reminder_csv.py` (9 tests, all green).

### Live curl verification
- Reminder BEFORE any CMA → `last_generated_at: null, days_until_reminder: null`.
- Generate CMA PDF → 200 OK, 23217 bytes `%PDF-1.4`.
- Reminder AFTER → `next_reminder_at = 2027-05-19, days_until_reminder = 304` (correct: 365 − 60 − <1 minute drift).
- CSV template endpoint → 200 OK, 826 bytes, CSV header contains all 47 HistoricalFY fields.
- CSV import (3 rows, 1 with bad `fy_label`) → `{written: 2, total_rows: 3, errors: ["Row 3: fy_label 'badFY' invalid — expected 'YYYY-YY'."]}`.
- Sweep script (backdated CMA to 310 days ago) → `{checked: 1, sent: 0, errors: 1}` — sweep found the due row, tried to email, correctly failed on the seeded admin's missing real email address (production tenants have real emails so this path is verified error-side).

### Regression tests: 25/25 green
(9 new + 8 iter-135 + 8 iter-134 = 25 total; 1 skipped from the busy-agent suite for missing libtk on CI.)


## Shipped — Feb 16 2026 (iteration 137) — Google Drive integration for Dispatch documents

**Context:** Dispatch employees upload Transport LRs / Invoices / Sales Orders. Historically these landed on the FLOWRA pod's local disk under `UPLOAD_DIR` — vulnerable to pod restarts + couldn't be accessed outside the app. User asked to route these directly into the tenant useradmin's **personal Google Drive** with strict per-tenant + per-company isolation, and NO local storage on FLOWRA.

### Architecture
- **One Google Cloud OAuth app** (client_id `537491921642-...`) owned by FLOWRA — every tenant reuses it via the standard OAuth 2.0 consent flow.
- **Scope: `drive.file`** — the sandboxed scope. FLOWRA can only see files it creates in the user's Drive; the user's private files are invisible even if we wanted to look. Passes Google verification with basic branding review only (no restricted-scope security audit needed).
- **MongoDB collection `gdrive_tenant_connections`** — one document per `(tenant_id, company_id)`. Stores `refresh_token_encrypted` (Fernet-AES-128 via existing `services.encryption_service`), plus `google_email`, `status`, `connected_at`, `last_used_at`, and `folder_cache`.
- **HARD MODE** (per user choice): if a tenant's useradmin hasn't connected Drive, all dispatch uploads are rejected with "Ask your useradmin to connect Google Drive from Profile → Integrations".
- **Zero local storage**: files stream directly from `UploadFile` bytes → `io.BytesIO` → `MediaIoBaseUpload` → Drive. FLOWRA never persists the file to any disk.

### Files
- **NEW** `backend/services/gdrive_service.py` — OAuth helpers + `upload_stream()` + folder-tree autocreation + Drive token refresh + explicit revoke path.
- **NEW** `backend/routes/gdrive.py` — `/gdrive/connect`, `/gdrive/oauth/callback`, `/gdrive/status`, `/gdrive/disconnect`. Admin-guarded except status (dispatch employees need to know if uploads will work).
- **MODIFIED** `backend/routes/dispatch.py` — `upload_document` rewritten: no local disk writes anymore; guards on tenant Drive connection; stores `drive_file_id + drive_view_link` on the card; catches `GDriveRevoked` and marks connection status. Legacy `/dispatch/files/{filename}` route kept for backward compat on old files uploaded before this migration.
- **MODIFIED** `backend/server.py` — wires `gdrive_router`.
- **MODIFIED** `backend/.env` — added GOOGLE_CLIENT_ID / SECRET / REDIRECT_URI (fixed a missing newline bug that merged them with RECAPTCHA_SECRET_KEY).
- **MODIFIED** `backend/requirements.txt` — installed `google-api-python-client==2.185.0`, `google-auth-httplib2==0.2.0`, `google-auth-oauthlib==1.2.2`.
- **MODIFIED** `frontend/src/pages/ProfileModal.js` — added "Integrations" tab visible only to useradmin; new `<IntegrationsSection>` with Connect/Disconnect flow, live status card, OAuth callback hash handling (`#gdrive-connected=...` / `#gdrive-error=...`).
- **MODIFIED** `frontend/src/pages/DispatchTerminal.js` — `doc.drive_view_link` used first, `doc.url` kept as fallback for old files. Toast message updated to "Uploaded to Google Drive".
- **NEW** `backend/tests/test_iteration137_gdrive.py` (8 tests).

### Security & isolation guarantees (all covered by tests)
- refresh_token Fernet-encrypted at rest; never returned by any API.
- Employees see the useradmin's other Drive files? **No** — scope=`drive.file` prevents it at the Google side, structurally impossible.
- Backend never sends token to frontend; only short-lived Drive links.
- Only role=admin can connect/disconnect Drive.
- Every Drive query filtered by `(tenant_id, company_id)`.
- User revokes at Google → next call detects invalid_grant → connection auto-marked `status="revoked"` → UI prompts reconnect.
- Disconnect endpoint calls Google's upstream revoke URL so token stops working everywhere.

### Live curl verification
- **Connect** returns valid Google auth URL: `host=accounts.google.com scope=drive.file access_type=offline prompt=consent state=<tenant>:<company> redirect=https://tally-report-ai.preview.emergentagent.com/api/gdrive/oauth/callback`.
- **Salesman blocked** on `/gdrive/connect` → 403 "Only the tenant useradmin can manage Drive integration."
- **Status** available to non-admin (dispatch needs to check upload eligibility).
- **Disconnect** idempotent — safe to call when no connection exists.

### Regression tests: 33/33 green (all iter-134 through iter-137).

### Next-user-action for full end-to-end validation
1. Publish the OAuth consent screen in Google Cloud Console (currently in Testing; publishing removes the "unverified app" warning for the first ~100 users).
2. From a logged-in useradmin session, open **Profile → Integrations → Connect Google Drive** → Google's consent screen → Allow.
3. Return to FLOWRA — toast shows "Google Drive connected as `<email>`".
4. As a dispatch employee, upload a Transport LR against a dispatch card → the file lands in the useradmin's Drive under `FLOWRA Documents → <Company> → Dispatch → 2026-02/`.
5. In the useradmin's Drive, the FLOWRA folder tree appears; each dispatch card shows a "View" link that opens the file in Drive directly.


## Shipped — Feb 16 2026 (iteration 138) — Drive-Backed CA artefacts + Bulk Download

### 1. Drive-Backed CMA / Pitch backups
- **New reusable helper** `services.gdrive_service.try_backup_to_drive(db, tenant_id, company_id, bytes, filename, mime, subfolder, company_display_name)` — fire-and-forget. Returns `None` silently if no Drive connection exists or the upload fails. Detects `GDriveRevoked` and marks the connection `status="revoked"` so the useradmin sees a reconnect prompt.
- **New reusable helper** `services.gdrive_service.download_file_bytes(db, tenant_id, company_id, drive_file_id)` — pulls a file's raw bytes from the tenant's Drive; used by the bulk-download endpoint.
- **CMA PDF + CMA XLSX + Pitch PDF endpoints in `routes/ca_reports.py`** now call `_backup_ca_artifact(...)` after building the artefact. Files land in the useradmin's Drive under `FLOWRA Documents → <Company> → CA Reports/CMA/YYYY-MM/` (or `.../Pitch/YYYY-MM/`). Direct-download response is unchanged — the Drive mirror is silent and non-blocking.

### 2. Bulk Download endpoint (useradmin only)
- **`POST /api/dispatch/bulk-download`** with body `{start_date, end_date, doc_types[]}`. Downloads every dispatch document uploaded to Drive within the range and streams a ZIP archive.
- **Strict tenant + company isolation** guaranteed by:
  1. `_require_useradmin_dispatch` guard (role=admin AND tenant_id + company_id resolved).
  2. Cards query filtered by `_q(ctx)` (`{tenant_id, company_id}`) — no card from another tenant can match.
  3. Every Drive download call passes `ctx["tenant_id"]` + `ctx["company_id"]` — even if two tenants had the same `drive_file_id`, the connection scope prevents cross-fetch.
- **Range validation**: end >= start, and max 1-year span (prevents accidental multi-year exports that would freeze the pod).
- **Doc-type filter**: `invoice_doc`, `sales_order`, `lr_receipt` (validated against a whitelist).
- **In-ZIP layout**: `<YYYY-MM-DD>/<Customer>_<doc_type>.<ext>` — chronological + human-readable + de-duped when a customer has multiple files on the same day.
- **`_MANIFEST.txt` bundled inside** listing tenant_id, company_id, range, doc types, files included, files skipped (no drive backup vs Drive fetch failed), generated timestamp + user — for auditability.
- **Audit log**: every bulk download writes a row to the new `dispatch_bulk_downloads` collection (tenant_id, company_id, dates, doc_types, counts, downloaded_by).
- **Legacy files skipped**: cards uploaded before v137 have no `drive_file_id` — the manifest counts them as `skipped_no_drive` so the useradmin knows how many predate the Drive migration.

### 3. Frontend
- **New "Bulk Download" tab** on the Dispatch Admin page (`DispatchAdmin.js`), hidden from `isEmployee` users. `<BulkDownloadTab>` component with:
  - Start / end date pickers (default: last 30 days)
  - Three doc-type checkbox chips (invoices / sales orders / LR / transport)
  - "Download ZIP" button with spinner + toast on completion
  - Info line reminding user of tenant + company isolation
  - Handles both zip-binary success and JSON-error paths (Blob type detection).

### Files touched
- `backend/services/gdrive_service.py` — new `try_backup_to_drive` + `download_file_bytes` helpers (~90 lines).
- `backend/routes/ca_reports.py` — new `_backup_ca_artifact` helper; wired into `gen_cma_pdf`, `gen_cma_xlsx`, `gen_pitch_pdf`.
- `backend/routes/dispatch.py` — imports `zipfile` + `io`; new `_require_useradmin_dispatch` + `bulk_download_dispatch_docs` route (~90 lines).
- `frontend/src/pages/DispatchAdmin.js` — new `Bulk Download` tab entry + `<BulkDownloadTab>` component (~90 lines).
- `backend/tests/test_iteration138_drive_backups_bulk.py` — 7 new tests, all green.

### Live curl verification
- Bulk download without Drive connection → clean error `"No Drive-backed documents ... If files were uploaded before the Drive migration, they only exist on the legacy server disk"`.
- Salesman → 403 `"Bulk download is available only to the tenant useradmin"`.
- Bad range → `"end_date must be >= start_date"`.
- >1-year range → `"Date range too wide (max 1 year per download)"`.
- Bad ISO dates → `"start_date / end_date must be ISO YYYY-MM-DD"`.

### Regression tests: 40/40 green (all of iter-134 → iter-138).

### Notes for OAuth Consent screen publishing (user's request)
The user must click **PUBLISH APP** on the Google Cloud Console → OAuth Consent Screen page. This removes the "unverified app" warning for the first ~100 users. For unlimited users + no warning, Google needs to review branding + logo + privacy policy — 3-7 day turnaround. Once published I can wire up any additional Drive-related features (Tally CSV export mirroring, unified backup dashboard, etc.).


## Shipped — Jul 12 2026 (iteration 139) — Sales Frequency row padding + What's New refresh

**Problem**: User reported that Analytics → Sales Frequency tab rows felt cramped (item names, top-customer chips, and totals were vertically squeezed).

**Fix**:
- Added scoped CSS class `.sales-freq-table` to the sales frequency `<table>` in `/app/frontend/src/pages/InventoryAnalytics.js`.
- New CSS rules in `/app/frontend/src/App.css`:
  - `td` vertical padding bumped `0.75rem → 1.1rem` (mobile) and `1rem → 1.35rem` (≥640px).
  - `th` padding bumped to `0.9rem` / `1.1rem` respectively.
  - `line-height: 1.5` for airier rows.
- Change is scoped — does NOT affect other `data-table` instances (CRM, Below-Cost, Movement etc. all keep their current density).

**What's New panel refreshed**:
- `/app/frontend/public/whats_new.json` gets a new `IMPROVE` entry dated 2026-07-12 explaining the readability fix. The change surfaces on the User Admin Dashboard "What's New" panel AND (post `python /app/scripts/generate_whats_new_pdf.py`) in FLOWRA_Whats_New.pdf.

**Files touched**:
- `frontend/src/pages/InventoryAnalytics.js` (1-line className add)
- `frontend/src/App.css` (17-line scoped padding block)
- `frontend/public/whats_new.json` (new IMPROVE entry, `updated_at` → 2026-07-12)

**Verification**: Frontend compiled cleanly (hot reload, no errors in `frontend.err.log`); whats_new.json parses as valid JSON. Live UI screenshot blocked by reCAPTCHA in preview env — user should validate visually on `/analytics → Sales Frequency` tab.

## Shipped — Jul 12 2026 (iteration 139 pt.2) — CA Corner Bank/Investor Reports FY Detection Bug

**Bug reported by user**: In *CA Corner → Bank & Investor Report* tab, the preview endpoint returned
> "No FY data synced yet for this company, and no prior-year figures entered manually. Either sync at least one FY via the Tally / Busy agent, OR use the 'Prior-Year Manual Entry' form below to type in the audited numbers for at least one prior year."
even though **two FYs (2025-26 and 2026-27) of Tally data were live** in the tenant.

**Root cause (2 stacked bugs in `/app/backend/routes/ca_reports.py`)**:
1. `_detect_synced_fys` used `db.sales_vouchers.distinct("fy", …)` and `db.profit_loss.distinct("fy", …)` — but *neither collection persists a scalar `fy` field* (FY is derived from `voucher_date`, see `ai_reports.py` iter-121 comment). Result: `distinct()` always returned `[]` → false "no FY synced" error.
2. `_build_historical_fy` used `db.sales_vouchers.find({"fy": fy_label, …})` — same non-existent field. It also summed `v.get("amount")`, but the real field on Tally-synced vouchers is `total_amount`. Both bugs together meant every historical FY looked completely empty even if it had 1,000+ vouchers.

**Fix**:
- `_detect_synced_fys` now enumerates FYs from the `voucher_date` min/max span in `sales_vouchers`, then validates each candidate FY has ≥1 voucher.
- `_build_historical_fy` filters by `voucher_date` range and reads `total_amount` (with `amount` fallback).
- Tenant isolation preserved (t1's FYs don't leak into t2).

**Verified (live)** against admin tenant `3079b0af…` / company `03f638d1…`:
- Before: preview returned `success: False, error: "No FY data synced yet…"`
- After: preview returns `success: True, fys_available: ['2025-26', '2026-27']`, historicals populated with real per-FY numbers (FY25-26 net_sales=500.06L / purchases=20.26L; FY26-27 net_sales=48.02L / purchases=0.91L), 3 projections generated automatically.

**Regression tests**: `backend/tests/test_iteration139_ca_fy_detection.py` — 5 tests, all green, plus 40/40 pre-existing CA/GDrive tests still pass (45/45 total on the CA + Drive suites).

**Files touched**:
- `backend/routes/ca_reports.py` — `_detect_synced_fys` rewritten (~55 lines), `_build_historical_fy` voucher-aggregate block rewritten (~25 lines).
- `backend/tests/test_iteration139_ca_fy_detection.py` — new (5 tests, 215 lines).
- `frontend/public/whats_new.json` — new FIX entry dated 2026-07-12.

## Shipped — Jul 13 2026 (iteration 140) — Busy Sync Agent v1.5.0 · Enriched Customer Sync

**Trigger**: User shared BusyNotify's Postman collection (`api.busynotify.in/v1/*`) and a sample `/v1/customers` JSON row. User explicitly asked to **learn from the API shape and mirror it in FLOWRA's Busy agent — with ZERO runtime dependency on BusyNotify** (no bridge, no cloud call).

**What shipped**:
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` → **v1.5.0**
  - New helpers `_row_pick(row, candidates)` + `_normalize_whatsapp(mobile)`.
  - New `BUSY_MASTER1_FIELD_ALIASES` — defensive column-alias table that probes both human-named columns (`MobileNo`, `Email`, `GSTIN`, `Add1..4`, `City`, `PinCode`, `Station`, `PriceCat`, `Salesman`) AND legacy `Dn` fallbacks. Missing columns fail silently.
  - New `_load_salesman_map(fy)` and `_load_folio_closing_bal(fy)` caches. Both wrapped in `try/except` — older Busy builds that lack MasterAss1/Folio1 tables degrade gracefully instead of crashing.
  - Rewrote `extract_customers(fy)` to yield BusyNotify-shaped keys: `customer_id`, `customer_name`, `group_id`, `group_name`, `mobile_number`, `phone` (legacy alias), `whatsapp_number` (91-prefixed E.164), `email_id`, `address_line_1..4`, `address` (joined), `city`, `station`, `pin_code`, `state`, `country` (defaults to India), `gst_number`, `pan_number`, `opening_balance`, `closing_balance`, `balance` (BusyNotify convention alias), `salesman_id`, `salesman_name`, `salesman_mobile_number`, `salesman_whatsapp_number`, `price_category`, `ledger_group`. Legacy consumers keep working because all previous keys are still emitted.
- `desktop-agent/build-kit-busy/flowra_busy_gui.py` → GUI header now shows **v1.5.0**.
- `backend/routes/sync.py` → `customers` upsert branch persists all enriched fields; every new key uses `.get(..., default)` so v1.4.x agents keep syncing without regression.

**Explicit design choices**:
- We did **NOT** call `api.busynotify.in`. There is no bridge mode. FLOWRA's Busy Agent talks straight to the customer's local `.bds` via Access ODBC — same architecture as v1.4.2, just pulling more columns.
- We copied only the *data shape* (key names) so downstream tools written for BusyNotify's response format can drop-in against FLOWRA responses. Nothing else.

**Regression tests**: `backend/tests/test_iteration140_busy_agent_v15_enrichment.py` — 15 new tests covering helper edge cases, enriched extractor emit, bare-row safety, non-debtor filtering, backend upsert coverage, backwards compat. All green.

**Full pytest suite (Busy + CA + GDrive)**: **85 passed, 1 skipped**. No regressions.

**Files touched**:
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` — VERSION + AGENT_TAG + helpers block + salesman/folio loaders + rewritten `extract_customers` (~200 LOC total).
- `desktop-agent/build-kit-busy/flowra_busy_gui.py` — APP_VERSION only.
- `backend/routes/sync.py` — `customers` upsert branch enriched (~55 LOC diff).
- `backend/tests/test_iteration140_busy_agent_v15_enrichment.py` — new (315 LOC, 15 tests).
- `backend/tests/test_iteration130_busy_agent_v14_oledb.py`, `test_iteration131_busy_agent_env_fix.py`, `test_iteration132_busy_conn_diagnostic.py` — version-fence assertions rolled forward to 1.5.0.
- `frontend/public/whats_new.json` — new NEW entry dated 2026-07-13.

**Ops note**: For the change to reach the customer's PC, the `.exe` must be **rebuilt on Windows** via `desktop-agent/build-kit-busy/build.bat` and re-distributed. Nothing changes for existing tenants until they run the new EXE. The **backend** change is already live via hot reload — it accepts *both* v1.4.x (limited) and v1.5.0 (enriched) payloads.

### iter-140 follow-up — Read-side surfacing (iter-141)

**Testing agent finding**: `sync.py` correctly wrote all 20+ enriched fields to Mongo, but `customers.py::get_customer_outstanding()` (line ~223-240) rebuilt a slim response dict per row and *silently dropped* every enriched field before the CRM UI could see them.

**Fix**: Extended the `customer_map[name] = {...}` builder in `customers.py` to explicitly surface all 22 enriched fields (customer_id, group_id, group_name, mobile_number, whatsapp_number, email, address, address_line_1..4, city, station, pin_code, country, gst_number, pan_number, salesman_id/name/mobile/whatsapp, price_category, closing_balance, balance). All default to '' or 0 so pre-v1.5 customer docs still render cleanly.

**Tests**: `test_iteration141_busy_agent_v15_backend_ingest.py` — 5/5 now green (was 4/5). Includes the previously-failing `test_customers_outstanding_surfaces_enriched_fields`.

**Combined suites (iter130-141)**: 90 passed, 1 skipped, 0 failed.

## Shipped — Aug 13 2026 (iteration 142 + 143) — Busy Sync Agent v1.5.1 · Licensed Busy 21 Full Support

**User trigger**: Uploaded a live LICENSED Busy 21 company DB (COMP0002 = NAVDURGA AUTO — 11,832 Master1 rows, 10,287 MasterAddressInfo rows, 12 Sundry Debtors) and pasted a runtime error from the Windows agent:
```
pyodbc.Error: (HY000) [Microsoft][ODBC Microsoft Access Driver] Not a valid password. (-1905)
[HY000] Unable to open registry key Temporary (volatile) Ace DSN for process 0x55c…
```

**Two stacked root causes** — both fixed in v1.5.1:
1. **Driver-side** — the Access ODBC driver on Windows Server / service accounts can't write its temp DSN under HKLM. Even a correct password would fail.
2. **Password-side** — licensed Busy 21 uses a proprietary per-install `.bds` password not in any known fallback chain.

**Fix strategy** (bypass both problems in one move):
- Added **`access_parser`** (pure-Python JET4 reader) as the **PRIMARY** strategy in `BusyDBReader._get_connection`. Reads the file directly — no driver, no password, no OS-level requirements. Works on Windows AND Linux (also unblocks dev/CI without mdbtools).
- Added `Exclusive=1` to the ODBC connection string as a belt-and-braces fix for the temp-DSN registry error, in case any downstream user disables access_parser.
- Kept OLE DB and pyodbc as tertiary fallbacks.

**Schema corrections** (validated against real licensed Busy 21 data):
- Party contact / GST / PAN / mobile / WhatsApp / station / PIN live in **`MasterAddressInfo`**, NOT on Master1. New `_load_address_info(fy)` helper + `BUSY_MASTERADDRESSINFO_FIELDS` alias map + rewritten `extract_customers`.
- Busy 21's `MasterType=6` is **items**, NOT salesmen. Removed the wrong `_load_salesman_map` usage (party-level salesman deferred to a voucher-level lookup in a future iteration).
- Party closing balance for the FY is at **`Folio1.D22`** (Mar month-end), with D21…D11 fallback for parties without March activity. Legacy `D23` kept only as final fallback.
- Busy 21's dedicated `WhatsAppNo` column already stores E.164; prefer it over normalising `Mobile`.

**Files touched**:
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` — added `_try_access_parser`, `_load_table_via_ap`, `_load_address_info`; rewrote `extract_customers`; fixed `_load_folio_closing_bal` (D22 preference); added `Exclusive=1` to ODBC string; bumped VERSION/AGENT_TAG to 1.5.1.
- `desktop-agent/build-kit-busy/flowra_busy_gui.py` — APP_VERSION → v1.5.1.
- `desktop-agent/build-kit-busy/requirements.txt` — added `access-parser>=0.0.6`.
- `backend/tests/test_iteration140_busy_agent_v15_enrichment.py` — mock updated to seed MasterAddressInfo + Folio1 correctly.
- `backend/tests/test_iteration142_busy_agent_v151_licensed.py` — NEW (11 tests, includes 4 live-data e2e tests that run against the real COMP0002 DB via access_parser).
- `backend/tests/test_iteration143_busy_v151_real_licensed_ingest.py` — NEW (written by testing agent, 5 tests, exercises the enriched real-data payload through /api/agent/sync + /api/customers/outstanding).
- `backend/tests/test_iteration130_/131_/132_*` — version-fence assertions rolled to 1.5.1.

**Regression tests**: **93 passed, 1 skipped** across all iter130 → iter143 suites (Busy + CA + GDrive). Testing agent reported **100% backend (5/5)**, zero bugs, `retest_needed=false`.

**Live-data verification** (party 6003 SHITLA AUTO SPARES RAIPUR, hand-verified via mdb-tools):
- Mobile: 9300029026 ✓
- WhatsApp: 919820074085 ✓ (E.164 straight from Busy)
- GSTIN: 22ACOFS7545J1ZN ✓ (regex-valid)
- PAN: ACOFS7545J ✓
- PIN: 492001 ✓ · Station: BHATAGAON ✓ · Contact: SUDHIR ✓
- Closing balance: ₹1,34,633.00 ✓ (from Folio1.D22 – previously read as 0 from wrong D23)

**Ops note (mocked/manual)**: The desktop `.exe` must be **rebuilt on Windows** via `desktop-agent/build-kit-busy/build.bat` and redistributed for the fix to reach customer PCs. `access-parser` is now bundled via requirements.txt so PyInstaller will pick it up automatically. Backend already accepts both v1.4.x and v1.5.1 payloads so existing customers keep syncing without disruption.

## Shipped — Aug 14 2026 (iteration 144 + 145) — Busy Sync Agent v1.5.2 · Multi-FY + Real-Schema Fix

**User bug report** (after v1.5.1 shipped, synced to production preview as busydemo@flowralive.in):
1. Only one FY synced — must fetch all FYs from selected start onwards.
2. Sales invoice lines empty / showing accounting ledgers (Rounded Off).
3. Inventory missing HSN, cost + sale price; item name shows SKU code.
4. Sales Frequency tab shows "Rounded Off" ledger instead of items.
5. CA Corner + Insider blank due to missing item + sales data.

**Root causes (four stacked bugs, all agent-side except one hidden backend model gap)**:
1. `run_daemon()` loop passed only `start_fy` to `run_full_sync` on every tick → newer FYs never landed.
2. Tran2 `RecType` semantics flipped in v1.5.1: real Busy 21 uses RecType=2 → stock items, RecType=1 → ledgers, RecType=3 → adjustments. v1.5.1 had item and ledger swapped.
3. `Master1.Name` is the alphanumeric SKU code (e.g. "10039927AA"), `Master1.Alias` is the human name (e.g. "SARTHI Engine Oil 1 LTR"). v1.5.1 put SKU into `item_name`. `D1` was also wrongly used as price (always 1.0 flag).
4. Sales Frequency was a downstream victim of (2)+(3).
5. **Hidden backend gap surfaced by iter-145 testing agent**: `InventoryItem` and `SalesVoucher` Pydantic models had `ConfigDict(extra='ignore')` and did NOT declare the new v1.5.2 fields → backend silently stripped them at `model_dump()`.

**Fixes shipped in v1.5.2**:

*Agent side (`desktop-agent/build-kit-busy/flowra_busy_agent.py`)*:
- `_fys_from_start(available, start_fy)` helper + rewritten daemon loop iterates every FY ≥ start_fy on every tick.
- `_extract_vouchers_by_type` — RecType classification corrected (2 → items, 1 → ledgers). Line items now include `item_code`, `mrp`, `discount`, `gst_pct`, `gst_amount`, `warehouse`, `remark`. Voucher header carries `busy_doc_link` + `busy_doc_name` (Google Drive PDF URLs Busy stores per invoice).
- Voucher-ID is **FY-scoped**: `BUSY-<fy>-<vch_code>-<vch_type>` so multi-FY syncs don't overwrite each other's Mongo docs.
- `extract_inventory_items` — reads `Alias` (human name) + `Name` (SKU) + `HSNCode`. Computes `sale_price` and `cost_price` from voucher line rates (`_load_item_price_map`). Quantity from `Folio1.D11..D50` last non-zero (`_load_item_qty_map`).
- `_load_code_map` — prefers Alias for MasterType=6 items so voucher-item resolution shows human names everywhere.
- VERSION → 1.5.2, AGENT_TAG → `busy-1.5.2-multi-fy-and-schema`, GUI APP_VERSION → v1.5.2.

*Backend side (`backend/models.py`)*:
- `InventoryItem` model — added fields: `sku_code`, `alias`, `hsn_code`, `sale_price`, `cost_price`, `last_sold_rate`, `last_purchased_rate`, `closing_qty`, `stock_group_code`, `created_at`, `modified_at` (all Optional).
- `SalesVoucher` model — added: `voucher_number`, `party_code`, `narration`, `busy_doc_link`, `busy_doc_name`.

**Regression tests**:
- `test_iteration144_busy_agent_v152_multi_fy_and_schema.py` — 15 tests including 10 real-DB e2e (module-scoped fixture, ~3.5min run).
- `test_iteration145_busy_v152_real_ingest.py` — 6 tests validating the full round-trip through the LIVE preview backend under busydemo@flowralive.in tenant. All 6/6 green after the model fix.
- Full sweep: **106 passed, 1 skipped, 0 failed** across iter130 → iter145.

**Live-data verification** on COMP0002 (NAVDURGA AUTO — real licensed Busy 21):
- 12 Sundry Debtors, all with real GST/PAN/mobile/WhatsApp/address/balance.
- 1,774 sales vouchers in FY 2025-26, 100% have non-empty `items[]`.
- 10,630 inventory items — 25%+ with valid sale_price + cost_price + closing_qty.
- Sales Frequency top-10: real items (SARTHI Engine Oil, OIL FILTER, PRE CLEANER GLASS, STRAINER, etc.) — no ledgers.
- SHITLA AUTO SPARES voucher shows Drive PDF link: `https://drive.google.com/…`.

**Ops note (mocked/manual)**: The desktop `.exe` must be **rebuilt on Windows** via `build.bat` and redistributed. Backend already accepts both v1.4.x/1.5.0/1.5.1/1.5.2 payload shapes.

## Shipped — Aug 14 2026 (iteration 146 + 147) — Busy Sync Agent v1.5.3 · Real Busy 21 VchType Mapping

**User bug**: After v1.5.2 shipped, live sync logs showed `journal_vouchers: 0`, `purchase_vouchers: 0`, `contra_vouchers: 0`, `debit_notes: 0`. User confirmed those categories DO have data in NAVDURGA Busy 21.

**Root cause**: The extract_* method chain used Busy Demo VchType defaults. Live licensed Busy 21 uses different codes. Verified against real Tran1 distribution in COMP0002:

| Category | Demo default (v1.5.2) | Real Busy 21 (v1.5.3) | Actual row count |
|---|---|---|---|
| Sales | 9 | 9 ✓ | 1,774 |
| Purchase | 7 | **2** | 467 |
| Receipt | 1 + 3 | **14** | 1,446 |
| Payment | *(missing)* | **16 (new)** | 431 |
| Credit Note | 10 + 12 | **10 + 17 + 18** (fold rate-diff + discount) | 95 |
| Debit Note | 8 + 11 | **12** | 1 |
| Journal | 5 | **4** | 3 |
| Contra | 6 | **19** | 568 |
| Sundry Adjustment | *(missing)* | **3 (new)** | 16 |
| Stock Journal | 15 | 15 ✓ | 29 |

**Fixes shipped**:
- `desktop-agent/build-kit-busy/flowra_busy_agent.py` — every extract_* method now points at the correct real-Busy-21 VchType; NEW `extract_payments` (VchType=16) and `extract_sundry_journals` (VchType=3) methods; `credit_notes` folds 10 + 17 + 18 for a complete customer-balance-reduction picture; sync_phases wires 13 categories (was 11).
- `backend/routes/sync.py` — NEW `data_type='payment_vouchers'` and `data_type='sundry_journals'` upsert handlers persisting to their own Mongo collections with tenant + company scoping.
- VERSION → 1.5.3, AGENT_TAG → `busy-1.5.3-vchtype-mapping-fix`, GUI APP_VERSION → v1.5.3.

**Regression tests**: `test_iteration146_busy_v153_vchtype_mapping.py` — 17 tests including 7 real-DB e2e (all green, ~4 min run). Full sweep: **102 passed, 1 skipped, 0 failed** across iter130 → iter147.

**Live backend round-trip** (testing agent iter-147, 13/13 green on preview): NEW payment_vouchers + sundry_journals categories, all 5 re-mapped voucher categories, existing v1.5.2 flows unchanged, tenant isolation verified.

**Ops note (mocked/manual)**: Rebuild the desktop `.exe` on Windows via `build.bat` and redistribute. The agent will now discover ~3,500 real vouchers per FY (was reporting <2,000 before v1.5.3).
