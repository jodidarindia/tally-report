# FLOWRA - Product Requirements Document

## Overview
FLOWRA is a React + FastAPI + MongoDB SaaS synced with Tally* for business analytics, inventory management, CRM, and reporting. Owned by JODIDAR INDIA.

## Key Bug Fixes (Apr 13, 2026)
1. **Inventory FY filtering**: Items API now accepts `?fy=` param, computes closing stock per FY using post-FY voucher adjustment
2. **Sort on Quantity/Value**: SortHeader components on Quantity and Value columns (sorts entire rows)
3. **Idle auto-logout fixed**: Used `handleLogoutRef.current` pattern to avoid stale closure in setTimeout
4. **AI PO crash fixed**: All PO modal fields null-safe (`|| 0`, `?? '-'`)
5. **Auto reorder fixed**: Changed `date` → `voucher_date` field lookup in sales_vouchers; fixed NoneType in audit logging

## Architecture Note
- `sales_vouchers.voucher_date` (not `.date`) is the correct date field
- Inventory closing stock for past FYs = current_stock + post_fy_sales - post_fy_purchases

## Upcoming Tasks
- P1: Compile Desktop Agent into `.exe` installer
- P2: Export Audit Logs to CSV
