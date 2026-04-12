# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally* for business analytics, inventory management, CRM, and reporting.

## Domain & Ownership
- **Domain**: `www.flowralive.in`
- **Brand**: FLOWRA is owned by **JODIDAR INDIA**
- **Contact**: support@flowralive.in | +91 81204 70018
- **Registered Address**: KK Road, Raipur, Chhattisgarh (legal pages only)

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn UI, Recharts, react-google-recaptcha-v3
- Backend: FastAPI, MongoDB
- Integrations: Tally* (desktop sync), OpenAI GPT-5.2 (Emergent LLM Key), Google reCAPTCHA v3

## Core Features
- Dashboard with overdue digest, sales analytics
- Inventory: stock tracking, reorder alerts, AI Purchase Orders, auto/manual reorder levels (2-month stock)
- Inventory Analytics: Movement Analysis, Below Cost Sales, Sales Frequency, Customer Items
- Customer CRM: Outstanding/Aging (Excel export), Targets (Excel export), Follow-ups, Payment Behavior
- Sales reports, AI-powered reports, Insider Result
- Salesman Performance tracking
- Tally* Sync with status monitoring, Sync History
- Branch/Division exclusion toggle (global)
- PDF Ledger export
- Refer & Earn: auto-generated codes, 3% commission, user dashboard, SA management
- Multi-company support, Super Admin panel
- Marketing PDFs (Presentation, Training Booklet, Social Media Kit)

## Security
- Google reCAPTCHA v3 on Login and Signup (score threshold 0.3)
- 15-minute idle auto-logout with warning
- JWT auth with role-based access control
- Field-level encryption (AES) for PII

## Public Pages
- Privacy Policy, Terms of Service, Refund Policy, Contact Us, Social Media
- WhatsApp floating button on public pages (+91 81204 70018)
- JODIDAR INDIA branding in all footers

## Mobile Responsiveness
- Horizontally scrollable tables with sticky first column (max-width:180px, text wrapping)
- Tab labels wrap on mobile, responsive layouts

## Branding
- All "Tally" / "Tally Prime" references display as "Tally*" throughout the app

## Architecture
```
/app/backend/routes/ — auth, referrals, prospects, super_admin, sales, inventory, customers, dashboard, sync
/app/backend/services/ — auth_service, recaptcha, audit_service, encryption_service, export_service, tenant_context
/app/frontend/src/pages/ — ReferAndEarn, PublicPages, LandingPage, SignupPage, SuperAdminDashboard, Dashboard, CustomerCRM, InventoryAnalytics, Inventory, TallySetup, etc.
```

## Upcoming Tasks
- P1: Compile Desktop Agent into `.exe` installer
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)

## Future/Backlog
- Salesman Order System (Enterprise)
- AI Expense Insights (GPT-5.2)
- Refactor App.js
