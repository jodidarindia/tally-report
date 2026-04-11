# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python v7.3 syncing Tally -> FLOWRA cloud
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth, UUID-format IDs

## Subscription Plans (INR)
| Plan | Monthly | Annual | Companies | Employees |
|------|---------|--------|-----------|-----------|
| Starter | Rs.999 | Rs.9,990 | 1 | 2 |
| Professional | Rs.2,499 | Rs.24,990 | 3 | 5 |
| Enterprise | Rs.3,799 | Rs.37,990 | 10 | 20 |

## What's Been Implemented

### SuperAdmin Seller Panel (April 11, 2026)
**Business backbone for FLOWRA operations:**
- **Overview Dashboard**: MRR, ARR, ARPU, Collections, Outstanding, Plan Distribution, Recent Payments
- **Subscription Management**: All customer subscriptions with plan, billing cycle, value, status, expiry tracking
- **Payment Ledger**: Manual payment recording (bank_transfer, UPI, cash, cheque), per-customer totals, mode-wise breakdown
- **Invoice System**: Generate invoices (FLW-YYYYMM-NNNN format), PDF download (reportlab), mark paid/unpaid/cancelled
- **Customer Ledger**: Per-customer view — total billed vs paid vs balance due, payment history, invoice history
- **Customer Health Monitor**: Sync status (active/moderate/inactive/never_synced), data volume, payment totals, subscription expiry
- **Prospect Management**: Lead funnel, status tracking, prospect-to-admin conversion
- **Admin CRUD**: Create/edit/toggle/delete admins, password reset, plan management
- **Renewals**: Expired & near-expiry tracking, renewal processing
- **Activity Log**: Audit trail of all operations

### Customer Item-wise Sales Analytics (April 11, 2026)
- "Customer Items" tab in Analytics: searchable combobox, item-wise table, summary cards, Excel export
- APIs: `/api/sales/customer-names`, `/api/sales/customer-item-sales`, `/api/sales/customer-item-sales-export`

### UUID ID System (April 11, 2026)
- All tenant_id and company_id use UUID format
- `company_mappings` collection: UUID -> AES-256 encrypted company name
- Desktop Agent v7.3 resolves company names to UUIDs
- Seed function uses UUID for new tenants

### Core Features (Prior)
- Multi-tenant auth (JWT + bcrypt) with role-based access
- Tally Prime sync via Desktop Agent with login-based auth
- Dashboard, Sales, CRM, Inventory, Analytics, Salesman, AI Reports, Insider BI
- Plan enforcement, feature gating, multi-company & multi-FY support
- Soft-delete archival, global email uniqueness, IST timezone normalization
- Landing page, demo signup flow, SEO meta tags

## Key Collections
- `users`, `company_mappings`, `payments`, `invoices`, `migration_log`
- `sales_vouchers`, `inventory_items`, `customers`, `receipt_vouchers`, `credit_notes`
- `journal_vouchers`, `purchase_vouchers`, `debit_notes`, `stock_journals`, `sundry_creditors`
- `sync_status`, `sync_history`, `audit_logs`, `prospects`, `deleted_users`

## Upcoming Tasks
- P1: Update Desktop Agent URL to production domain (after deployment)
- P1: Desktop Agent — One-Click `.exe` Installer (PyInstaller/Inno Setup)
- P2: Extended Tally Sync (sale/cost prices, expenses)
- P2: Salesman Order Management System (Enterprise only)
- P2: AI Expense Insights in Insider Result page
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
- P3: Refactor App.js into smaller routing/layout components
