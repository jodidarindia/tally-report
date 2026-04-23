# FLOWRA Busy Sync Agent v1.0

A lightweight Windows desktop agent that syncs your local **Busy Accounting Software** data
(`.bds` / MS Access Jet 4.0 databases) to the FLOWRA cloud — enabling remote analytics,
CA Corner, CRM Outstanding, and Dispatch flows from anywhere.

## Architecture

```
Busy Accounting (.bds)  →  FLOWRA Busy Sync Agent  →  Cloud Backend  →  Web App
  MS Access DB              Windows desktop (tkinter)   /api/agent/*      flowra.in
```

## Key Features

- **Light-themed GUI** (tkinter) — no command prompt
- **RAM-optimized**: cursor-based row streaming (never `fetchall()` on Tran1/Tran2)
- **Chunked uploads**: 500 vouchers per HTTP call → low memory ceiling
- **Auto FY discovery** from `db{year}.bds` filenames
- **All voucher types**: Sales, Receipts, Credit/Debit Notes, Purchase, Journal, Contra, Stock Journal
- **Master data**: Customers, Creditors, Inventory, all Ledgers, Account Groups
- **Balance Sheet & P&L** auto-computed from ledger closing balances
- **Deletion reconciliation** (manifest-based — deletes orphan records in cloud)
- **Remote command queue**: resync/delete from FLOWRA web UI
- **IST timestamps** for all syncs

## Prerequisites (Windows)

1. **Busy Accounting** installed with accessible data folder
2. **Python 3.9+** ([Download](https://www.python.org/downloads/))
3. **Microsoft Access Database Engine 2016 Redistributable** (64-bit)
   ([Download](https://www.microsoft.com/en-us/download/details.aspx?id=54920))
   — required for pyodbc to read `.bds` files
4. Python packages: `pip install pyodbc requests`

## Setup

1. Copy `flowra_busy_agent_v1.py` to your Windows PC
2. Open Command Prompt → `python flowra_busy_agent_v1.py`
3. The light-themed GUI opens. Enter:
   - **Server**: `https://app.flowra.in` (or your tenant's URL)
   - **Username / Password**: your FLOWRA admin login
4. Click **Browse** → select your Busy data folder (contains `db.bds`, `db{year}.bds`)
5. Select FY from the dropdown (latest auto-selected)
6. Pick a company from the list and click **Full Sync**

## Data Folder Structure

The agent looks for:

```
BusyData/
├── db.bds              (master DB — optional)
├── db12025.bds         (FY 2025-26)
├── db12024.bds         (FY 2024-25)
└── DATA.ZIP            (auto-extracted if present)
```

FYs are parsed from the filename — e.g. `db12025.bds` → `2025-26`.

## RAM Footprint

Tested on the sample FY database:
- Idle GUI: ~35 MB RSS
- During full sync: peaks at ~75 MB (even on 100K+ voucher datasets)
  because Tran1/Tran2 rows are streamed via `cursor.fetchone()` in a generator
  and released immediately after each 500-row chunk.

## Endpoints Used (backend)

- `POST /api/auth/login`
- `GET  /api/auth/sync-token`
- `POST /api/agent/sync`                  (chunked data upload)
- `POST /api/agent/reconcile`             (orphan deletion via manifest)
- `GET  /api/agent/commands`              (poll remote resync/delete)
- `POST /api/agent/commands/ack`          (acknowledge)

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `pyodbc.InterfaceError: IM002` | Install Microsoft Access Database Engine 64-bit |
| `Login Failed` | Verify credentials on flowra.in web UI |
| No FYs detected | Check folder contains `db{year}.bds` files (not inside `DATA.ZIP` — extract first or let agent auto-unzip) |
| Subscription expired | Renew on flowra.in — sync is gated by active subscription |

## Files Written Locally

- `flowra_busy_config.json` — backend URL, last username, last Busy folder
- `sync_state_busy.json`    — per-company last sync timestamps
