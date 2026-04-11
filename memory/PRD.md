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

### Movement Analysis Corrections (April 11, 2026)
- **Inward = Sundry Creditor purchases only**: Branch-like parties in purchase vouchers (e.g., "ASA AUTOTECH INDIA PVT LTD-BENGALURU") auto-detected via company name token matching and excluded from inward. This is independent of the branch toggle — inward always shows real supplier purchases only.
- **Opening Stock computed**: `Opening = Closing + AllSales - SundryCreditorPurchases` using UNFILTERED sales data. Fixed historical value that doesn't change with branch toggle.
- **Movement % fixed**: Now `Sales / (Opening + Inward) * 100` — represents % of available stock that was sold. Previously was `Sales/Opening * 100` which gave absurd 10000%+ values.
- Export endpoint uses identical logic.

### Branch/Division Exclusion Toggle — Full Coverage (April 11, 2026)
- Global navbar toggle with label ("Branch Included" green / "Branch Excluded" amber)
- Filters applied to ALL endpoints: Dashboard (sales, overdue, top-customers), Sales, CRM (outstanding, targets, followups, payment-behavior), Inventory, Analytics (movement, below-cost, sales-frequency, customer-items)
- Overdue digest: fresh computation when branches excluded (not cached)

### CRM Tab Updates (April 11, 2026)
- Tab order: Targets, Outstanding, Follow-ups, Payment Behavior
- All customer lists sorted alphabetically by default
- Branch filtering on all 4 tabs

### Previous Completions
- SuperAdmin Seller Panel (subscriptions, invoices, MRR, revenue)
- Customer Item-wise Sales Analytics with combobox and Excel export
- UUID-based tenant/company IDs with AES-256 encryption
- Cross-FY combined dashboard sales totals
- Desktop Agent v7.3 with "Default" company fix and UTC timestamps

## Key Technical Concepts
- `_get_purchase_branch_set(ctx)`: Auto-detects branch parties in purchase vouchers using company name token matching (same logic as sales branch detection). Always applied to inward calculations regardless of toggle state.
- `_get_branch_set(request, ctx)`: Returns branch parties from `branch_ledgers` collection only when `X-Exclude-Branches: true` header is set.

## Upcoming Tasks
- P1: Desktop Agent — One-Click `.exe` Installer (PyInstaller/Inno Setup)
- P2: Salesman Order Management System (Enterprise only)
- P2: AI Expense Insights with GPT-5.2
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
- P3: Refactor App.js into smaller components
