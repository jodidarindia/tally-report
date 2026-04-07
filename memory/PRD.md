# Tally Reports - Product Requirements Document

## Overview
SaaS-based web application connecting to TallyPrime for inventory and sales reports with AI-powered analytics.

## Architecture
- **Frontend**: React (Node 20), served on port 3000
- **Backend**: FastAPI + Motor (Async MongoDB), port 8001
- **Database**: MongoDB
- **Desktop Agent**: Python script connecting to local TallyPrime ODBC (port 9000)
- **Deployment**: Docker Compose for self-hosting

## Core Features

### Authentication (UserID + Password)
- Admin and Employee roles
- JWT-based session (httpOnly cookies + Bearer tokens)
- Default admin: admin/admin123 (from .env)
- Admin can create/delete employees, reset passwords
- Change password for all users
- Employee access: Sales, Inventory, CRM only
- Admin access: All tabs + User Management

### Inventory Management
- Stock items with stock groups from Tally
- Stock group dropdown filter
- Category filter, search
- AI-powered Purchase Order generation

### Sales
- Sales vouchers with FY-based filtering
- Clickable voucher numbers open invoice detail modal
- Invoice modal shows: customer, date, reference, salesman, line items, totals
- Sales trend chart, export (PDF/Excel/CSV)

### Customer CRM
- Outstanding with proper aging (0-30, 30-60, 60-90, 90+ days)
- Status: Normal / At Risk / Overdue / Critical (based on oldest invoice days)
- Customer group filter dropdown
- Follow-ups with created_by tracking (visible to all)
- Targets with monthly achievement
- Payment behavior analysis
- Ledger export (XLS/PDF)

### Financial Year Selection
- FY dropdown in navigation (April-March, Indian standard)
- Last 5 FY options generated dynamically

### Desktop Sync Agent (v3)
- Connects to local TallyPrime ODBC server
- Fetches stock items with groups (TDL collection, fallback to Stock Summary)
- Fetches sales vouchers (structured VOUCHER export)
- Fetches customer ledgers with groups
- FY-based date filtering
- Syncs to cloud/local backend every N minutes
- Debug mode saves raw XML to files

### AI Features
- AI Query Builder (GPT-5.2)
- Enhanced AI Reports
- AI Purchase Order generation

### Other
- Salesman Performance tracking
- Inventory Analytics
- Email OTP (Resend) — replaced by UserID/Password auth
- Docker Compose self-hosting

## Tech Stack
- React, FastAPI, MongoDB (Motor), Docker
- OpenAI GPT-5.2 via Emergent LLM Key
- Resend (Email OTP — legacy, not active)
- bcrypt + PyJWT for auth

## Key API Endpoints
- POST /api/auth/login — UserID/Password login
- GET /api/auth/me — Current user info
- POST /api/auth/users — Create user (admin)
- GET /api/auth/users — List users (admin)
- POST /api/auth/change-password — Change own password
- POST /api/auth/reset-password — Reset user password (admin)
- GET /api/tally/status — Tally sync connection status
- GET /api/inventory/items?stock_group= — Inventory with group filter
- GET /api/sales/vouchers — Sales vouchers
- GET /api/sales/vouchers/{id} — Single voucher detail (invoice)
- GET /api/customers/outstanding — Customer outstanding with aging
- POST /api/customers/followups — Create followup (stores created_by)
- POST /api/agent/sync — Receive data from desktop agent

## Data Models
- users: {username, password_hash, name, role, created_at}
- inventory_items: {item_id, item_name, quantity, unit, price, category, stock_group, reorder_level}
- sales_vouchers: {voucher_id, voucher_date, party_name, total_amount, items[], reference_number, salesman}
- customers: {customer_name, ledger_group, outstanding_amount, total_purchases, phone, state}
- customer_followups: {customer_name, followup_date, followup_type, status, notes, created_by, created_by_name}
- sync_status: {type, last_sync, company_name, financial_year, agent_version}

## Backlog
- P2: Real-time WebSocket sync
- P2: Multi-tenant support
- P3: WhatsApp/SMS OTP alternative
