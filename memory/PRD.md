# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python script syncing Tally -> FLOWRA cloud (v7.3)
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth, UUID-format tenant/company IDs

## Key DB Collections
- `users`: tenant users with UUID tenant_id and UUID company list
- `company_mappings`: UUID company_id -> encrypted company name mapping per tenant
- `sales_vouchers`, `inventory_items`, `customers`, etc.: all use UUID tenant_id + company_id
- `deleted_users`: archived user data for audit trails
- `prospects`: signup requests with returning_user flag
- `migration_log`: tracks completed data migrations

## What's Been Implemented

### Core Features
- Multi-tenant authentication (JWT + bcrypt) with role-based access
- Tally Prime sync via Desktop Agent (v7.3) with login-based auth
- Dashboard with real-time sales/inventory/overdue data
- Sales, CRM, Inventory, Analytics, Salesman, AI Reports, Insider BI
- Sync History with detailed cycle tracking
- Multi-company & Multi-FY support

### Security (April 2026)
- AES-256 field-level encryption for all PII
- UUID-format tenant_id and company_id (migrated from plain-text)
- Company name -> UUID mapping stored encrypted in `company_mappings` collection
- Global email uniqueness across users + prospects
- Soft-delete with archive to `deleted_users`

### Customer Item-wise Sales Analytics (April 11, 2026)
- New "Customer Items" tab in Analytics page
- Searchable combobox to select customer from synced customer list
- Item-wise sales breakdown: Item Name, Quantity, Avg Rate, Amount, Invoice Count
- Summary cards: Unique Items, Total Quantity, Total Amount, Total Invoices
- Excel export with formatted headers, data rows, and totals
- Backend APIs: `/api/sales/customer-names`, `/api/sales/customer-item-sales`, `/api/sales/customer-item-sales-export`
- Proper FY, tenant_id and company_id filtering

### UUID ID System (April 11, 2026)
- All tenant_id and company_id values are UUID format
- `company_mappings` collection maps UUID -> encrypted actual company name
- Desktop Agent v7.3 resolves company names to UUIDs
- Backend auto-resolves company names to UUIDs if agent sends plain name
- Frontend receives company_mappings on login and displays readable names
- Seed function uses UUID for new tenants

### IST Timezone Fix (April 11, 2026)
- Agent sends timestamps with UTC timezone marker
- Frontend normalizes naive timestamps as UTC before IST conversion

### Desktop Agent (v7.3)
- Full sync every cycle (no incremental — Tally has no change-detection API)
- Hash-based skip on upload prevents unnecessary DB writes
- SVCurrentCompany "Default" fix
- UUID company mapping resolution
- Subscription enforcement

## Upcoming Tasks
- P1: Update Desktop Agent URL to production domain (after deployment)
- P1: Desktop Agent — One-Click `.exe` Installer (PyInstaller/Inno Setup)
- P2: Extended Tally Sync (sale/cost prices, expenses)
- P2: Salesman Order Management System (Enterprise only)
- P2: AI Expense Insights in Insider Result page
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
- P3: Refactor App.js into smaller routing/layout components
