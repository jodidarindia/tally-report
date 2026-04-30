# FLOWRA Security Checklist (Mandatory for every product)

Every app under `*.flowralive.in` must satisfy **all** items below before going live.
Anything you can't tick belongs on the public roadmap with a target date.

## Authentication
- [ ] Passwords stored with **bcrypt cost ≥ 12**
- [ ] Login throttled: max 5 failed attempts per username per 15 minutes
- [ ] JWT lifetime ≤ 24h, refresh-token rotation if longer sessions needed
- [ ] HTTPS-only, SameSite=Lax cookies for any session state
- [ ] No password ever logged (server-side or client-side)
- [ ] Forced logout on email/password change

## Authorization
- [ ] Role-based access control (RBAC) — admin, user, super_admin minimum
- [ ] **Tenant isolation** — every DB query filtered by `tenant_id`/`workspace_id`
- [ ] Server-side permission checks on every mutation; client-side flags are UX-only
- [ ] No cross-tenant data leakage in shared collections (verify with multi-tenant test)

## Transport & API
- [ ] HTTPS enforced (HSTS header, 1-year + preload)
- [ ] CORS allowlist explicit — never `*` in production
- [ ] API rate limiting per IP and per user (e.g., 60 req/min default)
- [ ] CSRF protection if cookies are used for auth (double-submit token or origin check)
- [ ] All inputs validated with Pydantic / Zod / equivalent schema
- [ ] No `_id` (ObjectId) leaked in MongoDB responses — use Pydantic response models

## Secrets
- [ ] All secrets in `.env` files, never committed
- [ ] `.env.example` shows variable names with no values
- [ ] Secrets rotated yearly minimum, immediately on staff offboarding
- [ ] LLM keys tied to per-tenant usage caps to prevent abuse
- [ ] No fallback/default values for secrets in code (fail-fast)

## Data
- [ ] MongoDB Atlas (or DO Managed) with encryption at rest
- [ ] **Daily automated backups** with ≥ 30-day retention
- [ ] Point-in-time recovery enabled for paid tiers
- [ ] User data export endpoint (DPDP Act 2023 right-to-portability)
- [ ] User data delete endpoint (DPDP Act 2023 right-to-erasure) — soft-delete + 30-day grace
- [ ] PII fields enumerated and minimized

## Infra
- [ ] Firewall: only ports 80/443 public; SSH on non-default port + key auth only
- [ ] OS auto-updates enabled (unattended-upgrades)
- [ ] Sentry / Logtail / equivalent for error tracking
- [ ] Status page (status.flowralive.in)
- [ ] Health-check endpoint `/api/health` returning 200 in <500ms

## Frontend
- [ ] Content-Security-Policy header (no `unsafe-inline` in production)
- [ ] X-Frame-Options: DENY (or CSP frame-ancestors 'none')
- [ ] X-Content-Type-Options: nosniff
- [ ] All user-rendered content escaped — never `dangerouslySetInnerHTML` from user input
- [ ] No PII in URLs or query strings

## Compliance (India)
- [ ] DPDP Act 2023: privacy policy published, consent captured at signup
- [ ] Data residency: Mumbai region (ap-south-1) for primary DB
- [ ] Reasonable security practices documented (DPDP Section 8(5))
- [ ] DPO contact published (or nominated person if no DPO yet)

## Testing
- [ ] Auth flows have automated tests
- [ ] Tenant-isolation test: try to read another tenant's data → must 403
- [ ] At least one chaos test: kill DB during write — graceful degradation

## Monitoring (post-launch)
- [ ] Failed-login alerts: > 50/min spike → notify
- [ ] Error rate alert: > 1% 5xx → notify
- [ ] Backup-failure alert: any backup that doesn't complete → notify
- [ ] Subscription-expiry alert: 7 days before → notify customer + admin

---

## Reviewer signoff template

```
App: insights.flowralive.in
Version: 1.4.2
Reviewer: <name>
Date: <yyyy-mm-dd>
Items unmet: <list with target dates>
Decision: [PASS / PASS-WITH-RISK / BLOCK]
```
