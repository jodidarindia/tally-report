# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python v7.3 syncing Tally -> FLOWRA cloud
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth, UUID-format IDs

## What's Been Implemented

### Branch/Division Exclusion Toggle — Full Coverage (April 11, 2026)
- Global navbar toggle with label ("Branch Included" / "Branch Excluded")
- Green/amber color scheme indicates toggle state clearly
- Filters applied to ALL endpoints: Dashboard (sales, overdue, top-customers), Sales, CRM (outstanding, targets, followups, payment-behavior), Inventory, Analytics (movement, below-cost, sales-frequency, customer-items)
- Overdue digest: fresh computation when branches excluded (not cached), unfiltered result cached normally
- Toggle state persists via localStorage

### CRM Tab Updates (April 11, 2026)
- Tab order: Targets, Outstanding, Follow-ups, Payment Behavior
- Default tab: Targets
- All customer lists sorted alphabetically by default across all 4 tabs
- Branch filtering active on all 4 tabs when toggle is on

### Previous Completions
- SuperAdmin Seller Panel (subscriptions, invoices, MRR, revenue)
- Customer Item-wise Sales Analytics with combobox and Excel export
- UUID-based tenant/company IDs with AES-256 encryption
- Cross-FY combined dashboard sales totals
- Desktop Agent v7.3 with "Default" company fix and UTC timestamps
- Digital Ocean Deployment Guide PDF

## Upcoming Tasks
- P1: Desktop Agent — One-Click `.exe` Installer (PyInstaller/Inno Setup)
- P2: Salesman Order Management System (Enterprise only)
- P2: AI Expense Insights with GPT-5.2
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
- P3: Refactor App.js into smaller components
