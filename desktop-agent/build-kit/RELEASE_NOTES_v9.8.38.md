# FLOWRA Tally Sync Agent — v9.8.38

Release date: **5-Feb-2026**

## What's new

### 🔴 Critical fix: silent month-drop regression ("Krishna Sales Corp" bug)

Before v9.8.38, when a Tally **Export Data** call for a single month took
longer than 30 s to complete, the agent silently returned zero vouchers
for that month and **advanced its AlterID baseline anyway**. The next
quick-sync cycle short-circuited (because AlterID hadn't moved), so the
missed months were **permanently absent** from the dashboard until a
user manually hit **Resync**.

Field impact: Krishna Sales Corporation's FY 2026-27 dashboard showed
440 vouchers instead of ~2000 — Apr-Aug 2026 (heavier months) all timed
out, while Sep + Oct (lighter) completed and were visible.

### Fix A — Fail-loud month tracking

Every per-month fetch is now wrapped by `_tracked_month_fetch`, which:

1. Flips an `_in_month_fetch` flag on the `TallyConnector`.
2. Watches for the `requests.exceptions.Timeout` branch inside `_do_post`.
3. If a timeout fires while the flag is set, records
   `(fy, year, month, phase)` in a per-cycle `failed_months` set.

The sync cycle (quick AND full) now:

- Reports every failed `(fy, month, phase)` tuple to the backend via
  `/agent/sync-progress` with event `months_failed`.
- **Skips AlterID / LVD state persistence** if `failed_months` is
  non-empty, so the next scheduled cycle automatically retries the
  missed months without any user action.
- Logs the hint `Set EXPORT_TIMEOUT=180 in agent .env or trigger a full
  Resync.` so admins know what to do when the problem is persistent.

Backend-side: `sync_status.months_failed[]` + `.months_failed_count`
fields are now populated on the agent's `agent_sync` document. Dashboard
can read these for an at-a-glance "N months pending retry" badge.

### Fix B — Default `EXPORT_TIMEOUT` 30 s → 120 s

The old `v9.8.36` default of `0` (which meant "use `REQUEST_TIMEOUT=30`
for everything") was comfortable for 50-100 vouchers/month tenants but
tight for distributors with 150-200 vouchers/month like Krishna. The new
default of **120 s** has safety margin for the heaviest month we've
tested (Krishna's Aug 2026 — 193 vouchers × 30-row item arrays, roughly
48 s on their machine). Light-ledger users feel no change because Tally
returns as soon as the data is ready.

Admins with REALLY heavy ledgers can still bump via:

```
# in the agent's .env file (next to the .exe)
EXPORT_TIMEOUT=180
```

## Upgrading

1. Download `FlowraTallyAgent.exe` v9.8.38 from the FLOWRA Deploy page.
2. Overwrite your current executable (same filename).
3. On first launch after upgrade: the agent reads existing
   `sync_state_v9.json` so no re-selection of FY is required.
4. If you have missing months from a prior v9.8.37 session: trigger
   **Resync** on the dashboard — the agent will now surface any still-
   timing-out months in the sync status row instead of silently
   dropping them.

## EXPORT_TIMEOUT workaround (immediate relief, pre-v9.8.38)

If you cannot upgrade right now and are seeing missing months in your
dashboard:

### Step 1 — Create or edit `.env` next to `FlowraTallyAgent.exe`

```
EXPORT_TIMEOUT=180
```

(Or 240 / 300 if 180 isn't enough — the number is in seconds, applied
only to the Export Data calls, not to lightweight pings.)

### Step 2 — Restart the agent

Right-click the tray icon → **Quit**, then launch again.

### Step 3 — Trigger a full Resync from the dashboard

Dashboard → Sync Status card → **Resync** on your company.

This clears the local AlterID baseline and forces the agent to re-pull
every FY-month from Tally with the extended timeout. The quick-sync
scheduler will then take over and keep the dashboard current.

### Step 4 — Verify

Open the Dashboard. The **"Total Sales Vouchers (All FYs)"** subtitle
should now match your Tally count. On Krishna's deployment this went
from `440 vouchers (All FYs)` → `2048 vouchers (All FYs)`.

If any months still time out, the agent's `sync_status.months_failed`
field will list them explicitly — bump `EXPORT_TIMEOUT` higher and
re-run.

## Build notes

* `version_info.txt` → `9.8.38.0`
* `flowra_gui.py` → `APP_VERSION = "v9.8.38"`
* All `agent_version` strings in `tally_sync_agent_v9.py` →
  `9.8.38-fail-loud-month-timeout`
* Backend tolerates the new `months_failed` sync-progress event in
  `routes/sync.py::receive_sync_progress`.
