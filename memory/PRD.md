# FLOWRA - Tally Prime Report & Analytics SaaS

## Problem Statement
Build a SaaS web application connecting to local Tally Prime database for inventory and sales analytics. Multi-tenant with Super Admin, feature gating, RBAC, marketing website with subscription plans in INR, prospect management, and demo experience.

## Architecture
- **Frontend**: React + Shadcn UI + Tailwind CSS + Outfit font
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT + Fernet AES-256
- **Desktop Agent**: Python v7.0 (tally_sync_agent_v7.py)
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key
- **Video**: Sora 2 generated feature walkthrough

## Subscription Plans (INR)
| Plan | Monthly | Annual | Features | Companies | Employees |
|------|---------|--------|----------|-----------|-----------|
| Starter | Rs.999 | Rs.9,990 | 5 | 1 | 2 |
| Professional | Rs.2,499 | Rs.24,990 | 8 | 3 | 5 |
| Enterprise | Rs.4,999 | Rs.37,990 | 10 | 10 | 20 |

## Security Architecture
- AES-256 Fernet field-level encryption for prospect PII
- bcrypt password hashing, HS256 JWT
- Rate limiting: Auth 10/60s, Signup 3/hr, API 200/60s
- HSTS, CSP, X-Frame-Options, XSS protection, Referrer-Policy
- NoSQL injection protection, 10MB payload limit
- Multi-tenant data isolation (tenant_id + company_id)
- Audit logging with IP tracking

## What's Been Implemented (All Tested)

### Core App Features
- JWT Auth (super_admin/admin/employee), Multi-FY, Dashboard, Inventory, Sales, CRM
- PDF Ledger export, WebSocket live sync, AI Purchase Orders (GPT-5.2)
- Multi-Company Data Switcher, Security Audit (9 routes fixed)
- Insider Result BI (4 tabs), Salesman FY Performance, SearchableSelect
- Audit Logging, Inventory Analytics Redesign, Payment Behavior FY+Opening Balance

### Marketing Website (Apr 10 2026) — TESTED
- Landing page: Hero, features, pricing (3 tiers INR), testimonials, security, footer
- Monthly/Annual billing toggle with 17% savings
- Professional plan features shown in demo

### Prospect Signup Flow (Apr 10 2026) — TESTED
- 4-step: Details → Demo (with Professional features + video) → Requirements → Complete
- Demo uses hardcoded sample data only — no real customer data
- PII encrypted with AES-256 in database
- Video walkthrough generated via Sora 2

### SuperAdmin Plan-Based Management (Apr 11 2026) — TESTED
- Plan selection (Starter/Professional/Enterprise) when creating admin or converting prospect
- Plan auto-sets: features, max_companies, max_employees
- Billing cycle toggle (Monthly/Annual)
- Admin cards show: plan badge, employee limits, company limits, feature counts
- Enquiry management: status tracking, convert to admin with plan

### Plan Enforcement (Apr 11 2026) — TESTED
- Employee creation blocked when max_employees reached
- Company sync blocked when max_companies reached
- Error messages reference the plan name for upgrade guidance

### Desktop Agent v7.0
- Fetches: inventory_items, sales_vouchers, purchase_vouchers, debit_notes, sundry_creditors, customers (with opening_balance)

## Pending Tasks
### P1
- Compile Desktop Agent v7 into one-click installable .exe

### P2
- Export Audit Logs to CSV
- Automated payment follow-up reminders via email/WhatsApp
- Razorpay payment gateway for self-checkout

## Tech Stack
- React 18, Tailwind CSS, Shadcn UI, Recharts, Lucide React, Outfit
- FastAPI, Motor, PyJWT, ReportLab, OpenPyXL, bcrypt, cryptography
- MongoDB, OpenAI GPT-5.2, Sora 2
