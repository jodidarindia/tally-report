# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS application synced with Tally* for business analytics, inventory management, CRM, and reporting.

## Domain & Ownership
- **Domain**: `www.flowralive.in`
- **Brand**: FLOWRA is owned by **JODIDAR INDIA**
- **Contact**: support@flowralive.in | +91 81204 70018

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn UI, Recharts, react-google-recaptcha-v3
- Backend: FastAPI, MongoDB, Resend (email)
- Integrations: Tally* (desktop sync), OpenAI GPT-5.2, Google reCAPTCHA v3, Resend Email API

## Implemented Features
- Dashboard, Inventory (auto/manual reorder), Inventory Analytics, CRM (Excel export), Sales, AI Reports
- Salesman Performance, Tally* Sync, Branch/Division exclusion, PDF Ledger export
- Refer & Earn (3% commission), Multi-company, Super Admin panel
- Public pages (Privacy, Terms, Refund, Contact, Social), WhatsApp button
- reCAPTCHA v3, 15-min idle auto-logout, Onboarding tour
- Mobile responsive with sticky columns and text wrapping

## Email Communication (Apr 2026)
- **Subscription Started**: Welcome email with plan details, 3-step getting started guide, login CTA
- **Subscription Renewed**: Confirmation with new expiry date, green "RENEWED" badge
- **Expiry Warning**: Sent on login when <=30 days left (max once/day). Urgency levels: amber (8-30d), red (<=7d). Lists consequences + renew CTA
- **Service**: Resend API, sender: support@flowralive.in
- **Backend env**: `RESEND_API_KEY`, `SENDER_EMAIL`
- **Trigger points**: Admin creation (SA panel), Renewal approval (SA panel), Login (auth/login)

## Upcoming Tasks
- P1: Compile Desktop Agent into `.exe` installer
- P2: Export Audit Logs to CSV

## Future/Backlog
- Salesman Order System (Enterprise)
- AI Expense Insights (GPT-5.2)
- Refactor App.js
