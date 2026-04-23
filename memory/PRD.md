# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally for business analytics, inventory, CRM, dispatch, and salesman ordering.

## Salesman Order System (Complete — April 2026)
- **Salesman Role**: Dedicated `salesman` role — sees only order placement interface
- **Customer Mapping**: Salesman sees only their mapped customers (from salesman_master)
- **Product Catalog**: Real-time stock quantities and Tally sales prices from inventory_items
- **Order Creation**: Select customer → browse catalog → add items with per-item remark field → submit
- **Order Lifecycle**: Pending → Approved/Rejected/Hold → Billed (requires Tally invoice number)
- **Edit Lock**: Once approved, salesman cannot edit. Only pending orders editable.
- **Order History**: Full order history visible to salesman with status, timeline, invoice numbers
- **Admin Approval**: Admin sees all orders via Salesman > Orders tab with stats, date filters, search
- **Billed → Dispatch**: Billed orders with invoice numbers appear in Dispatch > Online Orders tab. Once invoice syncs from Tally, dispatch card auto-creates.
- **Beat Management**: Admin creates beat plans (customer/day/frequency), salesman marks visits
- **IST Timezone**: All timestamps in IST
- **Mobile Responsive**: All pages mobile-first
- Collections: `salesman_orders`, `salesman_beats`

## Dispatch Terminal Feature (Complete)
- Kanban Board, Date-based Card Creation, Porter/Transporter Settlement
- Document Uploads (Invoice/SO/LR), Close of Day PDF
- Online Orders tab showing salesman billed orders

## Other Key Features
- Dashboard with Updates changelog frame
- Sales, CRM (Outstanding, Targets, Payment Behavior)
- Inventory, Analytics (SPIP, Concentration Risk, Lifecycle, Forecast)
- CA Corner, SuperAdmin, Refer & Earn, Digital Questionnaire
- Desktop Agent v9 with reconciliation, command queue, dual-schedule sync

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
