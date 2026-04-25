# Database & Backup Strategy (decided April 2026)

## Current State
- MongoDB single instance inside Emergent preview pod (`MONGO_URL` in `/app/backend/.env`, DB name `test_database`)
- No automated backups, no replica set, no PITR
- TLS in transit ✅, encryption at rest ❌, tenant isolation via `tenant_id` ✅, JWT+HMAC auth ✅

## Migration Target (when ready for production)
**MongoDB Atlas M10 — AWS Mumbai (ap-south-1)** (~₹1,800/mo)

Reasons preferred over DO Managed MongoDB:
1. Atlas Search — needed for full-text search on customers/vouchers/ledgers
2. Atlas Charts — embedded dashboards for CA-facing reports
3. Atlas Triggers — replace cron jobs (overdue reminders, sync-stalled alerts)
4. Better migration tooling (zero-downtime mongomirror)
5. India region = DPDP compliance built-in
6. 3-year stable pricing

DigitalOcean Managed MongoDB is the alternative (Blr/Mumbai, ~₹1,300/mo) if cost-sensitive and Atlas-specific features aren't required.

## Backup Plan (3 tiers)

### Tier 1 — Implement Now (free, on current pod)
- `scripts/backup_mongo.sh` — gzipped `mongodump` with rotation
- Cron entry: 2:00 AM IST daily, 30-day retention
- SuperAdmin → "Backups" page: list, download, trigger-now, restore (admin-only)
- UserAdmin → Profile → "Data Export": per-tenant JSON snapshot for DPDP right-to-portability
- **PERMISSION SPLIT**: Full DB dumps live ONLY in SuperAdmin. Each tenant's admin gets own-data-export only.

### Tier 2 — Production Hardening
- Move to Atlas M10 (Mumbai) — zero code change, just swap MONGO_URL
- Atlas continuous backups + PITR (default included)
- Off-site copy → S3/B2 with 90-day lifecycle (~₹200/mo)

### Tier 3 — SOC-2 / Enterprise
- Atlas Dedicated cluster, ap-south-1
- 4-hour recovery window, tenant-level KMS keys
- Quarterly restore drills, DPDP Act 2023 audit

## Implementation Priority
1. Tier 1 SuperAdmin Backups page + UserAdmin Data Export
2. Atlas migration playbook (documented but not executed until paying customer)
3. Atlas migration when MRR justifies the ₹1,800/mo cost

## Key Decision Notes
- MongoDB Atlas does NOT run on DigitalOcean (only AWS/GCP/Azure)
- DigitalOcean has its own "DO Managed MongoDB" product (different from Atlas, but uses MongoDB Enterprise underneath)
- Both options support Indian data residency
