# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.

## User Personas
- **Super Admin**: FLOWRA operator managing all tenants, subscriptions, prospects
- **Admin (Tenant Owner)**: Business owner with Tally Prime, subscribes to a plan
- **Employee**: Staff added by Admin with restricted feature access

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python script syncing Tally → FLOWRA cloud
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth

## Subscription Plans (INR)
| Feature | Starter (Rs.999/mo) | Professional (Rs.2,499/mo) | Enterprise (Rs.3,799/mo) |
|---------|------|--------------|------------|
| Dashboard | Yes | Yes | Yes |
| Sales | Yes | Yes | Yes |
| Inventory | Yes | Yes | Yes |
| CRM | No | Yes | Yes |
| Analytics | No | Yes | Yes |
| Salesman | No | No | Yes |
| AI Reports | No | No | Yes |
| Insider BI | No | No | Yes |
| Max Companies | 1 | 3 | 10 |
| Max Employees | 2 | 5 | 20 |

## What's Been Implemented (Completed)

### Core Features
- Multi-tenant authentication (JWT + bcrypt) with role-based access
- Tally Prime sync via Desktop Agent (v7) with login-based auth
- Dashboard with real-time sales/inventory/overdue data
- Sales tracking with voucher details
- Customer CRM with payment behavior, followups, targets
- Inventory management with stock analytics
- Movement analytics with AI-powered insights
- Salesman performance tracking (Enterprise only)
- AI Reports (GPT-5.2 powered) (Enterprise only)
- Insider BI Result page (Enterprise only)
- Sync History with detailed cycle tracking
- Tally Setup page with connection config
- Activity/Audit logging
- Multi-company support with company selector
- Multi-FY support with FY selector

### Security (April 2026)
- AES-256 field-level encryption for all PII (names, phones, emails)
- SHA-256 email hashing for prospect data
- Complete audit trail
- **Global email uniqueness enforced** across users + prospects in all creation flows:
  - Prospect Signup: checks users + prospects
  - SuperAdmin Create Admin: checks users + prospects (with redirect to Convert flow)
  - Admin Create Employee: checks users + prospects + validates email format
  - Convert Prospect: checks users

### Marketing & Prospecting (April 2026)
- Public Landing Page with animated dashboard mockup
- Signup Page with demo request flow (Professional plan features)
- Prospect management in SuperAdmin (Enquiries tab)
- Convert Prospect to Admin with plan selection

### Subscription Management (April 2026)
- Plan enforcement (Starter/Professional/Enterprise) with feature gating
- Company and employee limits per plan
- Subscription start/expiry dates stored and displayed
- Profile Subscription tab with dates, plan info, renewal request
- SuperAdmin Renewals tab: near-expiry, expired, renewal requests
- Renewal popup on admin login if plan expires within 30 days
- Desktop Agent subscription validation (blocks sync if expired)
- Desktop Agent company limit enforcement per plan

### IST & FY Handling (April 2026)
- IST (Asia/Kolkata) formatting throughout the app
- Default FY set to latest synced FY from Tally on login
- Backend IST utility (ist_utils.py) for calculations

## Key API Endpoints
- POST /api/auth/login - Login with subscription data
- GET /api/auth/me - Current user with subscription info
- POST /api/auth/request-renewal - Admin requests renewal
- GET /api/sync/latest-fy - Latest synced FY
- POST /api/agent/sync - Tally sync (with subscription check)
- GET /api/super-admin/renewals - Renewal management
- PUT /api/super-admin/renewals/{username}/process - Approve/reject renewal
- POST /api/prospects/signup - New prospect signup
- POST /api/super-admin/convert-prospect - Convert to admin

## Tech Stack
- React 18, Shadcn UI, Lucide Icons, Sonner toasts
- FastAPI, Motor (MongoDB async), bcrypt, cryptography, PyJWT
- OpenAI GPT-5.2 (via Emergent LLM Key)
- MongoDB with AES-256 encryption at rest

## Upcoming Tasks
- P1: Compile Desktop Agent into .exe installer
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)
- P3: Refactor App.js into smaller routing/layout components
