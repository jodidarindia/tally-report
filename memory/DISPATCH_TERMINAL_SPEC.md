# FLOWRA Dispatch Terminal — Detailed Specification
**Status**: FUTURE DEVELOPMENT  
**Priority**: P1  
**Plan**: Enterprise  

---

## 1. Dispatch Card — Data Fields

Every Tally* sales invoice automatically creates a dispatch card with:

| Field | Source | Input By |
|---|---|---|
| Invoice Number | Auto from Tally* sync | System |
| Party Name | Auto from Tally* | System |
| Items Billed (list) | Auto from Tally* | System |
| Total Boxes in Consignment | Manual | Dispatch Employee |
| Transport Name | Manual | Dispatch Employee |
| Destination City | Auto from Tally* (or manual) | System/Employee |
| Transport Charges Paid | Manual | Dispatch Employee |
| Porter Charges Paid | Manual | Dispatch Employee |
| Porter Name | Manual (from porter list) | Dispatch Employee |
| Dispatched By | Auto (logged-in employee) | System |
| Status | Workflow-driven | Employee |
| Physical Check Confirmation | Mandatory checkbox | Employee |
| Notes / Remarks | Optional | Employee |

## 2. Status Lifecycle

```
NEW → QUEUED → PROCESSING → PACKED → DISPATCHED → INFO SHARED
         ↓                      ↑
       HOLD ────────────────────┘
```

- **NEW**: Invoice synced from Tally*, card auto-created
- **QUEUED**: Assigned to dispatch employee (round-robin)
- **PROCESSING**: Employee picking & verifying items against bill
- **PACKED**: All items physically checked, boxes counted, sealed
- **DISPATCHED**: Handed to transport, porter+charges logged
- **INFO SHARED**: Invoice & dispatch details shared with customer
- **HOLD**: Paused (credit issue, stock shortage, verification needed)

### Physical Verification Rule
Cannot move from PROCESSING → PACKED without checking:
"I confirm all items in the bill are physically verified and present"

## 3. Queue System

- Cards auto-assigned to dispatch employees in round-robin rotation
- Each employee sees only their queued cards
- Employee picks next card, updates all fields, confirms physical check
- Admin can reassign cards between employees

## 4. Manual Dispatch Cards

For dispatches without Tally* invoice (returns, samples, replacements):
- Employee clicks "Create Manual Card"
- Must select reason: Sample / Return / Replacement / Internal Transfer / Other
- Fills same fields as invoice card (minus invoice number — gets "MAN-XXXX" ID)
- Same status lifecycle, same tracking, tagged as "MANUAL" in all views

## 5. Porter Expense Tracking

- Dispatch terminal has a Porter Master (list of porters)
- Every dispatch logs: porter name + service charge
- Running account maintained per porter
- Weekly settlement report: total owed per porter
- Admin marks "Paid" with payment reference
- Porter-wise monthly/yearly analysis

## 6. Transport Charges

- Record per-dispatch: freight, handling, insurance
- Transporter-wise summary
- City-wise freight analysis over time

## 7. Close of Day Summary

One-click generates daily summary containing:
- Each dispatched invoice: Invoice No, Party Name, Boxes, Transport/Porter charges, Porter name, Employee name, Status
- Totals: invoices dispatched, pending, on-hold
- Value dispatched (Rs.), total boxes
- Transport-wise breakdown, city-wise count
- Porter charges for the day + weekly running total
- Pending carry-forward list with hold reasons

## 8. Admin View (User Admin)

- Summary only — totals and metrics
- Export to Excel — full dispatch log with all card fields
- ONLY pending dispatches can be drilled down to card details/notes/remarks
- Completed dispatches show summary row only
- Porter settlement report — weekly payable
- Transport expense analysis

## 9. Security

- FY-scoped: all dispatch data isolated per financial year
- Tenant ID + Company ID isolation — multi-company safe
- 256-bit AES encryption for all dispatch records
- reCAPTCHA v3 on dispatch terminal login
- JWT auth with 15-minute idle timeout
- New employee role: `dispatch` (terminal access only)
- Audit trail: every status change logged with employee + timestamp

## 10. Technical Architecture

```
Tally* → Desktop Agent v8 → POST /api/sync/invoices
                                    ↓
                              MongoDB: invoices + dispatch_status
                                    ↓
                        WebSocket push to Dispatch Terminal
                                    ↓
                    /dispatch-terminal (employee login, dark theme)
                                    ↓
                    Status updates → PATCH /api/dispatch/{id}/status
                    Close-of-day → POST /api/dispatch/close-day
```

**New collections**: `dispatch_status`, `dispatch_porters`, `dispatch_expenses`  
**New role**: `dispatch` (limited access — only terminal)  
**Display**: 43"/55" wall-mounted, dark theme, touch-first, kiosk mode (F11)  
**Mobile**: Admin summary view responsive on phone
