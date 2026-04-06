# Tally Reports - Product Requirements Document

## Problem Statement
Build a SaaS-based web application that connects to a Tally database (Tally Prime local version) to prepare inventory and sales reports. Include an AI-based report builder, CRM, salesman tracking, and a self-hosting deployment package.

## Architecture
- **Frontend**: React + Tailwind CSS + Recharts + Shadcn/UI
- **Backend**: FastAPI + Motor (Async MongoDB)
- **Database**: MongoDB
- **AI**: GPT-5.2 via Emergent LLM Key
- **Auth**: Email OTP via Resend (with dev mode bypass)
- **Desktop Agent**: Python script that syncs Tally data to the cloud

## Implemented Features (All Complete)

### Core
- [x] Dashboard with summary stats (inventory value, sales, items, connections)
- [x] Inventory management with search, filter, export (PDF/Excel/CSV)
- [x] Sales vouchers view with date filtering and analytics charts
- [x] Tally connection setup page

### AI Features
- [x] AI Report Builder (GPT-5.2) with natural language queries
- [x] Enhanced AI Reports with report type selection and filters
- [x] AI Purchase Order generation with priority classification
- [x] Report history tracking

### CRM & Sales
- [x] Customer CRM with outstanding balances and aging analysis
- [x] Customer follow-ups (create, track, update status)
- [x] Customer targets and achievement tracking
- [x] Payment behavior analysis and credit scoring
- [x] Salesman performance tracking with targets

### Analytics
- [x] Inventory pivot tables (group by category, metric selection)
- [x] Sales frequency analysis (transaction count, unique customers)
- [x] Inventory movement analysis (fast/slow/dead-stock classification)
- [x] Below-cost sales identification

### Auth & Security
- [x] Email OTP authentication (Resend SDK)
- [x] Dev mode with static OTP (123456) for testing
- [x] Session management (create, verify, logout)
- [x] Protected routes (login wall)

### Deployment & Sync
- [x] Desktop Sync Agent (Python) for pushing Tally data to cloud
- [x] Docker Compose self-hosting package
- [x] Deploy scripts (Linux/Mac + Windows)
- [x] Nginx reverse proxy configuration
- [x] Self-hosting guide documentation

## API Endpoints
- `POST /api/auth/send-otp` - Send OTP email
- `POST /api/auth/verify-otp` - Verify OTP and create session
- `POST /api/auth/verify-session` - Validate session token
- `POST /api/auth/logout` - Invalidate session
- `GET /api/inventory/items` - List inventory items
- `GET /api/inventory/summary` - Inventory stats
- `POST /api/inventory/generate-purchase-order` - AI purchase order
- `GET /api/inventory/movement-analysis` - Stock movement analysis
- `GET /api/inventory/below-cost-sales` - Below cost items
- `GET /api/inventory/pivot-data` - Pivot table data
- `GET /api/inventory/sales-frequency` - Sales frequency report
- `GET /api/sales/vouchers` - Sales vouchers
- `GET /api/sales/summary` - Sales stats
- `GET /api/sales/analytics` - Sales charts data
- `POST /api/ai/query` - AI report query
- `POST /api/ai/advanced-query` - Enhanced AI report
- `GET /api/reports/history` - Query history
- `POST /api/reports/export` - Export reports
- `GET /api/customers/outstanding` - Customer outstandings
- `GET /api/customers/followups` - Follow-ups
- `POST /api/customers/followups` - Create follow-up
- `GET /api/customers/targets` - Targets
- `GET /api/customers/payment-behavior` - Payment analysis
- `GET /api/salesman/performance` - Salesman performance
- `POST /api/agent/sync` - Desktop agent data push
- `GET /api/sync/status` - Sync status

## Backlog
- P2: Real-time WebSocket sync between Desktop Agent and cloud
- P2: Multi-tenant support with organization management
- P3: WhatsApp/SMS OTP alternative
