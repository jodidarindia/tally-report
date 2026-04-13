# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory, CRM, and reporting. Owned by JODIDAR INDIA.

## Desktop Agent v8 (Apr 2026)
### New Features:
1. **FY Discovery & Selection**: On first connection, agent queries Tally* for all available FYs, presents list to user, who selects starting FY. Syncs from that FY to current. Saved in encrypted state file.
2. **Contra Vouchers**: Bank-to-bank, cash-to-bank transfers synced per FY per month.
3. **Bank & Cash Ledger Balances**: All Bank, Cash-in-Hand, Bank OD accounts with opening/closing balances, bank details (name, account no, IFSC).
4. **Profit & Loss Data**: All Income and Expense group ledgers with balances. Totals computed.
5. **Encrypted Config**: Auth token, tenant_id, company_id stored in Fernet-encrypted file (AES-128-CBC). Machine-specific key in hidden file.
6. **Memory Optimization**: `gc.collect()` after sync phases, chunked processing.

### Sync Phases (11 total):
1. Stock Items, 2. Sales, 3. Receipts/Payments, 4. Credit Notes, 5a. Journals, 5b. Stock Journals, 6. Purchases, 7. Debit Notes, 8. Sundry Creditors, 9. Contra Vouchers, 10. Bank/Cash Ledgers, 11. P&L Data + Customer Ledgers

### Backend Collections Added:
- `contra_vouchers`, `bank_cash_ledgers`, `profit_loss`

### Files:
- `/app/desktop-agent/tally_sync_agent_v8.py` (main agent)
- `/app/frontend/public/flowra-desktop-agent.py` (download copy)
- `/app/backend/routes/sync.py` (sync handlers for new data types)

## Recent Bug Fixes (Apr 13)
- Inventory FY closing stock calculation (correct: current + post_fy_sales - post_fy_purchases)
- Reorder levels rounded up to whole numbers (math.ceil)
- AI PO crash fixed (null-safe toLocaleString)
- Auto-reorder using voucher_date field
- Idle timeout using handleLogoutRef pattern

## Upcoming Tasks
- P1: Build Cash Flow dashboard (uses contra, bank/cash, receipts data)
- P1: Build P&L report page (uses profit_loss data)
- P2: Compile Desktop Agent v8 into `.exe` installer
- P2: Export Audit Logs to CSV
