# FLOWRA - Tally Prime Analytics SaaS Platform

## Product Overview
Multi-tenant SaaS platform that syncs with Tally Prime to provide real-time inventory analytics, sales tracking, CRM, AI reports, and business intelligence.

## User Personas
- **Super Admin**: FLOWRA operator managing all tenants, subscriptions, prospects
- **Admin (Tenant Owner)**: Business owner with Tally Prime, subscribes to a plan
- **Employee**: Staff added by Admin with restricted feature access

## Core Architecture
- Frontend: React + Shadcn UI (port 3000)
- Backend: FastAPI + Motor (port 8001)
- Database: MongoDB
- Desktop Agent: Python script syncing Tally -> FLOWRA cloud
- Security: AES-256 PII encryption, bcrypt passwords, JWT auth

## Subscription Plans (INR)
| Feature | Starter (Rs.999/mo) | Professional (Rs.2,499/mo) | Enterprise (Rs.3,799/mo) |
|---------|------|--------------|------------|
| Dashboard | Yes | Yes | Yes |
| Sales | Yes | Yes | Yes |
| Inventory | Yes | Yes | Yes |
| CRM | No | Yes | Yes |
| Analytics | No | Yes | Yes |
| Salesman | No | No | Yes |
| AI Reports | No | No | Yes |
| Insider BI | No | No | Yes |
| Max Companies | 1 | 3 | 10 |
| Max Employees | 2 | 5 | 20 |

## What's Been Implemented (Completed)

### Core Features
- Multi-tenant authentication (JWT + bcrypt) with role-based access
- Tally Prime sync via Desktop Agent (v7) with login-based auth
- Dashboard with real-time sales/inventory/overdue data
- Sales tracking with voucher details
- Customer CRM with payment behavior, followups, targets
- Inventory management with stock analytics
- Movement analytics with AI-powered insights
- Salesman performance tracking (Enterprise only)
- AI Reports (GPT-5.2 powered) (Enterprise only)
- Insider BI Result page (Enterprise only)
- Sync History with detailed cycle tracking
- Tally Setup page with connection config
- Activity/Audit logging
- Multi-company support with company selector
- Multi-FY support with FY selector

### Security (April 2026)
- AES-256 field-level encryption for all PII (names, phones, emails)
- SHA-256 email hashing for prospect data
- Complete audit trail
- Global email uniqueness enforced across users + prospects
- Employee tenant isolation

### User Lifecycle & Data Integrity (April 2026)
- Soft-delete with archive to `deleted_users` collection
- Admin deletion archives tenant data
- Re-signup detection (returning_user flag)
- SuperAdmin audit view for deleted users
- Employee management with plan-based limits

### Marketing & Prospecting (April 2026)
- Public Landing Page with animated dashboard mockup
- Signup Page with demo request flow
- Prospect management in SuperAdmin
- Convert Prospect to Admin with plan selection

### Subscription Management (April 2026)
- Plan enforcement with feature gating
- Company and employee limits per plan
- Subscription dates stored and displayed
- Renewal popup, SuperAdmin renewals tab
- Desktop Agent subscription & company limit enforcement

### Documentation (April 2026)
- Digital Ocean Production Deployment Guide (43-page PDF) — covers domain, server, MongoDB, Nginx, SSL, PM2, backups, monitoring, troubleshooting

## Upcoming Tasks
- P1: Update Desktop Agent URL to production domain (after user deploys)
- P1: Desktop Agent — One-Click `.exe` Installer (PyInstaller/Inno Setup)
- P2: Extended Tally Sync (sale/cost prices, expenses)
- P2: Salesman Order Management System (Enterprise only)
- P2: AI Expense Insights in Insider Result page
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)
- P3: Refactor App.js into smaller routing/layout components

## Tech Stack
- React 18, Shadcn UI, Lucide Icons, Sonner toasts
- FastAPI, Motor (MongoDB async), bcrypt, cryptography, PyJWT
- OpenAI GPT-5.2 (via Emergent LLM Key)
- MongoDB with AES-256 encryption at rest
