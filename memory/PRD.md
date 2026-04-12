# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally* for business analytics, inventory management, CRM, and reporting.

## Domain & Ownership
- **Domain**: `www.flowralive.in`
- **Brand**: FLOWRA is owned by **JODIDAR INDIA**
- **Contact**: support@flowralive.in | +91 81204 70018

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn UI, Recharts, react-google-recaptcha-v3
- Backend: FastAPI, MongoDB
- Integrations: Tally* (desktop sync), OpenAI GPT-5.2, Google reCAPTCHA v3

## Implemented Features
- Dashboard, Inventory (auto/manual reorder), Inventory Analytics, CRM (Excel export), Sales, AI Reports
- Salesman Performance, Tally* Sync, Branch/Division exclusion, PDF Ledger export
- Refer & Earn system (3% commission), Multi-company, Super Admin panel
- Public pages (Privacy, Terms, Refund, Contact, Social), WhatsApp button
- reCAPTCHA v3 on login/signup, 15-min idle auto-logout
- Onboarding tour for first-time users (7 steps, persisted via DB flag)
- Mobile responsive with sticky first columns and text wrapping

## Onboarding Tour (Apr 2026)
- Custom-built spotlight tour (no external library dependency)
- 7 steps: Dashboard, Inventory, CRM, Analytics, Refer & Earn, Setup, FY Selector
- Shows on first login when `onboarding_completed: false` in user record
- Skip/Back/Next navigation with progress dots
- Backend: `POST /api/auth/complete-onboarding` sets flag to true
- Won't show again once completed or skipped

## Upcoming Tasks
- P1: Compile Desktop Agent into `.exe` installer
- P2: Export Audit Logs to CSV
- P2: Automated payment follow-up reminders (email/WhatsApp)

## Future/Backlog
- Salesman Order System (Enterprise)
- AI Expense Insights (GPT-5.2)
- Refactor App.js
