# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally for business analytics, inventory, CRM, dispatch, and salesman ordering.

## Salesman Order System (Complete)
- Salesman role, customer mapping, product catalog with Tally stock/prices
- Order lifecycle: Pending → Approved/Rejected/Hold → Billed (requires invoice number)
- Reject requires mandatory reason. Rejected orders hidden from Dispatch Online Orders tab.
- Edit lock after approval. Full order history visible to salesman.
- Beat management with visit tracking.
- **Pending Billing tab** in Dispatch: Per-customer item aggregation for approved orders pending billing.
- **Billed Order Verification**: Compares order items vs Tally invoice items, shows MATCHED/DISCREPANCY/NOT_SYNCED.

## Dispatch Terminal (Complete)
- Kanban Board, Date-based Card Creation, Porter/Transporter Settlement
- Document Uploads, Close of Day PDF, Online Orders tab (excludes rejected)
- Pending Billing tab with item-level verification

## Upcoming
- P1: Compile Desktop Agent v9 to `.exe`
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
