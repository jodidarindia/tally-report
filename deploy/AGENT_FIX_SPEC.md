# Agent-Side Fix Spec — Multi-Company Safety (iter-126)

**Context.** On 26 Feb 2026 a client had two Tally companies open on the same machine. The agent couldn't reliably identify which company to sync and — worst-case — corrupted one company's data file. The FLOWRA server-side is already patched (see below). This document is the **companion patch that must land inside the FlowraTallyAgent .exe** (the desktop Python/PyInstaller codebase which lives outside this repo).

## Server-side defences already shipped (iter-126)

| Guard | Endpoint | Behaviour |
|---|---|---|
| Hard `company_id` + `company_name` requirement | `POST /api/agent/sync` | Rejects with 400 if either is blank — no more ambiguous "current company" pushes |
| Per-(tenant, company) advisory lock | `POST /api/agent/sync` | Two overlapping syncs for same company → 2nd gets `Another sync is already in progress`. 60-second TTL auto-clears stale locks |
| Preflight endpoint | **NEW** `POST /api/agent/preflight` | Agent asks server for permission before every cycle. Server refuses when multiple companies are open without explicit intent |

## What the agent MUST do — checklist

### 1. Never issue a `POST … LOAD COMPANY` XML action

This is the single most likely cause of the .tsf/.mgr corruption. If a `LOAD COMPANY` action runs while a voucher-export request is streaming, Tally's data-server can leave the company files in a half-written state → **"Damaged data file"** on next open.

**Rule:** only read-shaped XML requests (`EXPORT DATA`, `LIST OF LEDGERS`, `VOUCHER REGISTER`, …). Never `IMPORT DATA`, never `LOAD COMPANY`, never `ALTER`. If your codebase has any `envelope.Header.Type = "Function"` with an action verb, remove it.

### 2. Detect multi-company state at every cycle start

Before every sync cycle, ask Tally which companies are loaded:

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>ListOfCompanies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="ListOfCompanies" ISMODIFY="No">
            <TYPE>Company</TYPE>
            <FETCH>NAME</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

Parse the `<NAME>` nodes. That's your `loaded_companies` array.

### 3. Call the FLOWRA preflight before every sync

```python
resp = requests.post(
    f"{server}/api/agent/preflight",
    json={
        "tenant_id":            tenant_id,
        "sync_token":           sync_token,
        "active_company":       svcurrentcompany,     # from SVCURRENTCOMPANY
        "loaded_companies":     loaded_companies,     # from step 2
        "intended_company_id":  intended_company_id,  # your local mapping
    },
    timeout=10,
)
data = resp.json().get("data", {})
if not data.get("allow"):
    log.warning("preflight blocked: %s", data.get("reason"))
    return   # skip this cycle entirely
for w in data.get("warnings", []):
    log.info("preflight warning: %s", w)
```

**Do not** proceed if `allow=false`. Retry on the next scheduled cycle — the block auto-clears once the user closes the extra company.

### 4. Wrap every XML call in an in-process mutex

```python
import threading
_TALLY_LOCK = threading.Lock()

def tally_call(xml_payload: str) -> str:
    with _TALLY_LOCK:
        return requests.post("http://localhost:9000", data=xml_payload, timeout=90).text
```

This is CRITICAL. Even a single agent instance can race itself if two data-type sync workers run concurrently (e.g. sales_worker + purchase_worker). The lock serialises XML calls so Tally never sees overlapping requests.

### 5. Verify `SVCURRENTCOMPANY` immediately before AND after each export

```python
before = tally_svcurrentcompany()
if before != intended_company_name:
    log.warning("Active company drift before request: expected %s got %s — skipping", intended_company_name, before)
    return

vouchers = tally_export_sales(from_dt, to_dt)

after = tally_svcurrentcompany()
if after != intended_company_name:
    log.error("Active company drift MID-REQUEST: was %s now %s — discarding batch", before, after)
    return   # do NOT push to FLOWRA
```

The double-check catches the exact "user tabbed to another company mid-sync" scenario that caused the incident.

### 6. Every push must carry BOTH `company_id` and `company_name`

Server now enforces this. Payload template:

```json
{
  "tenant_id":     "krishnaSalesCorp",
  "sync_token":    "<HMAC>",
  "company_id":    "9C6E5E70-4D0A-42FE-B0DD-…",       // stable UUID mapped locally
  "company_name":  "Krishna Sales Corporation",         // display name from Tally
  "data_type":     "sales",
  "data":          [ … ],
  "voucher_date_from": "2026-04-01",                    // v9.8.30 window scoping
  "voucher_date_to":   "2026-04-30"
}
```

If your local mapping doesn't have a `company_id` for a company yet, generate one on first sight (`uuid4()`) and persist it — never reuse the display name, because Tally names can be renamed.

### 7. Handle the new 409-style responses gracefully

If FLOWRA returns any of:

- `"company_id is required …"` → your payload is malformed, don't retry blindly, log and alert.
- `"Another sync is already in progress …"` → back off exponentially (2 s, 4 s, 8 s, max 60 s). Do not spam-retry.
- `"Invalid sync token"` → your token has been rotated. Fetch a fresh one from the agent config endpoint.

## Recovery for the current incident

For the client whose company file is already damaged:

1. **Do not touch the affected `.tsf`/`.mgr` files** in the Tally data folder.
2. Restore from the most recent Tally backup (Tally itself auto-backs up on close; look for `TallyBAK` in the same folder).
3. If no Tally backup, ask the client to open the last daily encrypted FLOWRA backup (SuperAdmin → Backups tab → download → import into a fresh company).
4. Uninstall the current agent, wait for the patched build.
5. Ship the patched agent as **v9.8.31**, bump `agent_release.json` here, and force-update via the Setup page.

## Test cases the patched agent must pass

- [ ] Single company open → sync succeeds, no warnings.
- [ ] Two companies open, no `intended_company_id` sent → agent receives `allow:false`, skips cycle, logs it.
- [ ] Two companies open, `intended_company_id` sent, `active_company` matches → agent receives 1 warning, proceeds, sync succeeds.
- [ ] User tabs to Company B mid-sync (SVCURRENTCOMPANY drift) → agent detects, discards the batch, does NOT push.
- [ ] Two agent workers race for the same company → 2nd gets 409, backs off, does not corrupt cache.
- [ ] Payload without `company_id` → server rejects, agent logs and alerts.
- [ ] Payload with a `company_id` never seen before → server auto-registers, returns warning, agent honours it.
