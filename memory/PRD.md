# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.
Website: www.flowralive.in

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python v7.3 syncing Tally -> FLOWRA cloud
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth, UUID-format IDs

## What's Been Implemented

### Marketing Materials (April 11, 2026)
- **FLOWRA_Presentation.pdf**: 10-slide customer pitch deck with demo screenshots (fake data), problem/solution framing, feature walkthroughs, pricing, CTA
- **FLOWRA_Training_Booklet.pdf**: 7-page employee training guide with product features, setup instructions, pricing, objection handling, demo script, FAQs, quick reference card
- **FLOWRA_Social_Media_Kit.pdf**: Complete social media package — LinkedIn, Instagram, Twitter/X, WhatsApp, Google My Business posts + 30-day content calendar
- All materials use demo data (Sharma Auto Parts, Mehta Motors, etc.) — no real customer data
- Domain updated from flowra.in to flowralive.in across all frontend references

### Movement Analysis Corrections (April 11, 2026)
- Inward = Sundry Creditor purchases only (branch transfers auto-excluded)
- Opening Stock = Closing + AllSales - AllPurchases (uses full data for balance)
- Movement % = Sales / (Opening + Inward) * 100

### Branch/Division Exclusion Toggle — Full Coverage (April 11, 2026)
- All endpoints filtered: Dashboard, Sales, CRM, Inventory, Analytics
- Overdue digest: fresh computation when branches excluded

### CRM Tab Updates (April 11, 2026)
- Tab order: Targets, Outstanding, Follow-ups, Payment Behavior
- All customer lists sorted alphabetically

### Previous Completions
- SuperAdmin Seller Panel, Customer Item-wise Analytics, UUID IDs, Cross-FY totals
- Desktop Agent v7.3, Deployment Guide PDF, Setup page fix

## Upcoming Tasks
- P1: Desktop Agent — One-Click `.exe` Installer (PyInstaller/Inno Setup)
- P2: Salesman Order Management System (Enterprise only)
- P2: AI Expense Insights with GPT-5.2
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders
- P3: Refactor App.js into smaller components
