# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally Prime for business analytics, inventory management, CRM, and reporting.

## Domain & Ownership
- **Domain**: `www.flowralive.in`
- **Brand**: FLOWRA is owned by **JODIDAR INDIA**
- **Contact**: support@flowralive.in | +91 81204 70018
- **Registered Address**: KK Road, Raipur, Chhattisgarh (used only in legal pages)

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn UI, Recharts, react-google-recaptcha-v3
- **Backend**: FastAPI, MongoDB
- **Integration**: Tally Prime (desktop sync), OpenAI GPT-5.2 (AI features via Emergent LLM Key), Google reCAPTCHA v3

## Core Features (Implemented)
- Dashboard with overdue digest, sales analytics
- Inventory management with stock tracking, reorder alerts
- Inventory Analytics: Movement Analysis, Below Cost Sales, Sales Frequency, Customer Items
- Customer CRM: Outstanding/Aging, Targets, Follow-ups, Payment Behavior (credit scoring)
- Sales reports and AI-powered reports
- Salesman Performance tracking
- Tally Sync with status monitoring
- Branch/Division exclusion toggle (global)
- PDF Ledger export, Marketing PDFs
- Multi-company support, Super Admin panel

## Refer & Earn System (Apr 2026)
- **Auto-generated referral codes** (REF-XXXXXX format) for admin and employee users
- **Referral Code field** on signup/enquiry form (optional)
- **3% commission** on subscription amount when referred prospect subscribes
- **User Panel**: Referral code card, stats (Total Referrals, Earned, Balance, Redeemed), referral history table, earnings ledger with credit/debit entries
- **Super Admin Panel**: Referrals tab with overview stats, referrers table, recent referrals, Credit Commission action, Redeem/Payout action, per-user ledger view
- **Collections**: `referral_codes`, `referrals`, `referral_ledger`
- **Commission flow**: Prospect signs up with code → Referral record created (pending) → SA credits commission when prospect subscribes → Commission appears in referrer's ledger → SA processes payout when requested

## Security Features (Apr 2026)
- **Google reCAPTCHA v3**: Invisible bot protection on Login and Signup (score threshold 0.3)
- **Idle Auto-Logout**: 15-minute inactivity timeout with warning at 14 min
- **JWT-based Auth**: Token-based with role-based access control

## Public Pages (Apr 2026)
- Privacy Policy, Terms of Service, Refund Policy, Contact Us, Social Media
- WhatsApp floating button on public pages (+91 81204 70018)
- JODIDAR INDIA branding in all footers

## Mobile Responsiveness (Apr 2026)
- Horizontally scrollable tables with sticky first column
- Tab labels wrap on mobile, responsive layouts

## Architecture
```
/app/
├── backend/
│   ├── routes/ (auth.py, referrals.py, prospects.py, super_admin.py, sales.py, inventory.py, customers.py, dashboard.py, sync.py, ...)
│   ├── services/ (auth_service.py, recaptcha.py, audit_service.py, encryption_service.py, ist_utils.py)
│   └── models.py, server.py, db.py
├── frontend/
│   └── src/
│       ├── App.js (routing, auth, idle timeout, reCAPTCHA provider)
│       ├── App.css (.data-table, sticky columns)
│       └── pages/ (ReferAndEarn.js, PublicPages.js, LandingPage.js, SignupPage.js, SuperAdminDashboard.js, Dashboard.js, ...)
```

## Upcoming Tasks
- P1: Compile Desktop Agent into one-click `.exe` installer
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)

## Future/Backlog
- Salesman Order System (Enterprise)
- AI Expense Insights (GPT-5.2)
- Refactor App.js
