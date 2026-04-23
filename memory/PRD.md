# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting.

## Dispatch Terminal Feature (Complete)
- **Kanban Board**: 5 swim lanes (New/Queued/Processing/Packed/Dispatched) + Hold
- **Date-based Card Creation**: Admin selects start date; old invoices assumed dispatched
- **View Date Filter**: Affects all tabs (Overview summary, Kanban board)
- **Close of Day PDF**: Downloadable PDF on Overview tab based on selected date
- **Transport/Porter Management**: Dropdown selection + inline create by employees, edit/delete from admin master list
- **Porter Settlement**: Running account, payment recording, balance tracking
- **Transporter Settlement**: Running account, payment recording, balance tracking
- **LR Tracking**: Transport receipt number per card
- **Document Uploads**: Invoice doc, Sales order, LR receipt
- **Dispatch History**: Searchable archive with read-only detail modal (HistoryDetailModal)
- **Timeline**: All timestamps displayed in IST (Asia/Kolkata)
- **Nav Position**: Between CA Corner and Sync History
- **`dispatch` Role**: Terminal-only access
- **Mobile Responsive**: All pages use sm: breakpoints
- Collections: `dispatch_cards`, `dispatch_porters`, `dispatch_transporters`, `dispatch_porter_payments`, `dispatch_transporter_payments`, `dispatch_settings`

## Dashboard Updates Frame
- Scrollable changelog at bottom of Dashboard only
- NEW/FIX tagged entries with dates

## Critical Technical Notes
### Opening Balance Logic
Tally's `opening_balance` = balance at START of `sync_status.financial_year`. Earlier FYs: reverse-compute. Non-customer parties: pure voucher sum.
### JV Party Amounts
Use `ledger_entries` array to extract party-specific amount, not total `credit_amount`/`debit_amount`.

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P2: Salesman Order System
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
