# 🔔 USER REMINDERS — read at start of every new session

> The user has explicitly parked these reminders. Surface them in the
> FIRST message back to the user when a new session opens, BEFORE
> jumping into any plan or implementation work.

---

## ⏰ Pending — raised on Jun 20 2026

### 🐞 Super-admin bugs — user to share details
- **User said**: *"I have found lot of bugs in superadmin. Please remind me tomorrow for the same."* (Jun 20 2026 session)
- **Next agent action**: Greet the user and explicitly say:
  > *"Welcome back 👋 — yesterday you mentioned you'd found bugs in the super-admin section. Whenever you're ready, please share the list (a screenshot, a video, or just a written list of what's misbehaving). I'll triage and fix in priority order."*
- **What to do once user shares the bugs**:
  1. Reproduce each on the live preview using the `superadmin` / `superadmin123` credentials from `/app/memory/test_credentials.md`.
  2. Group into P0 / P1 / P2 and propose a fix plan via `ask_human` before coding.
  3. Hot files: `/app/backend/routes/super_admin.py`, `/app/frontend/src/pages/SuperAdminDashboard.js`, `/app/frontend/src/pages/super-admin/*`.
- **Status**: WAITING_USER_INPUT (only the user has the bug details).

---

## ✅ Reminder removal protocol
When a reminder above is fully resolved, move its block to a new
`### Resolved` section at the bottom of THIS file (do NOT delete — keep
the audit trail). Add the date and the iteration number that fixed it.
