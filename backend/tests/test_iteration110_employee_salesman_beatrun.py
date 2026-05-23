"""Iteration 110 — Employee active toggle + Salesman copy + Beat Run
order/payment + close-day + day-report.

Source-asserting tests — no live HTTP. We import the route modules and
verify the contract pieces that matter (presence of endpoints, correct
contract validation, business logic in pure helpers).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def auth_src():
    import inspect
    from routes import auth as auth_mod
    return inspect.getsource(auth_mod)


@pytest.fixture(scope="module")
def salesman_src():
    import inspect
    from routes import salesman as sm
    return inspect.getsource(sm)


@pytest.fixture(scope="module")
def orders_src():
    import inspect
    from routes import salesman_orders as so
    return inspect.getsource(so)


# ── Feature 1 — Employee toggle ──────────────────────────────────────────
def test_toggle_user_active_route_exists(auth_src):
    assert "/auth/users/{username}/toggle-active" in auth_src
    assert "async def toggle_user_active" in auth_src
    # Tenant isolation guard
    assert 'target.get("tenant_id") != user.get("tenant_id")' in auth_src
    # Block self-toggle
    assert "Cannot toggle your own account" in auth_src
    # Block toggling other admins
    assert "Cannot toggle this account type" in auth_src


def test_login_blocks_deactivated_employee(auth_src):
    assert 'role") in ("employee", "dispatch", "salesman") and not user.get("active", True)' in auth_src
    assert "Your account has been deactivated. Contact your admin." in auth_src


def test_login_friendly_expiry_message_for_employees(auth_src):
    # Admin gets renew-from-Profile message
    assert "Renew from Profile" in auth_src
    # Employee gets "Please ask your admin" message
    assert "Please ask your admin" in auth_src
    assert "Access will resume automatically once renewed" in auth_src


def test_create_user_sets_active_true(auth_src):
    # Find the new_user dict block and assert active is set.
    assert '"active": True,' in auth_src


# ── Feature 2 — Salesman copy ────────────────────────────────────────────
def test_salesman_copy_route_exists(salesman_src):
    assert "/salesman/copy-from" in salesman_src
    assert "async def copy_salesman_data" in salesman_src


def test_salesman_copy_validates_inputs(salesman_src):
    # Source/target both required
    assert "from_salesman and to_salesman are required" in salesman_src
    # Must differ
    assert "Source and target salesmen must differ" in salesman_src
    # At least one of customers/beats
    assert "Select at least one of: copy_customers, copy_beats" in salesman_src
    # Tenant isolation — uses _build_query(ctx)
    assert "_build_query(ctx, company_id)" in salesman_src
    # Beat copy generates fresh beat_ids
    assert 'f"BT-{uuid.uuid4().hex[:6].upper()}"' in salesman_src


def test_salesman_copy_handles_release_source(salesman_src):
    assert "release_source" in salesman_src
    assert "source_released" in salesman_src


# ── Feature 3 — Beat Run order/payment + close-day ───────────────────────
def test_check_in_requires_order_payment(orders_src):
    # When visited=True, both flags MUST be booleans.
    assert "order_collected (true/false) is required when marking visited" in orders_src
    assert "payment_collected (true/false) is required when marking visited" in orders_src


def test_check_in_blocked_when_day_closed(orders_src):
    assert "Today's run is closed. Ask your admin to re-open if needed." in orders_src


def test_add_unplanned_requires_order_payment(orders_src):
    assert "order_collected (true/false) is required" in orders_src
    assert "payment_collected (true/false) is required" in orders_src
    # Existing-customer flag
    assert "is_existing_customer" in orders_src


def test_close_day_and_reopen_routes_exist(orders_src):
    assert "/salesman-orders/beat-run/close-day" in orders_src
    assert "async def beat_run_close_day" in orders_src
    assert "/salesman-orders/beat-run/reopen-day" in orders_src
    assert "async def beat_run_reopen_day" in orders_src
    # Reopen is admin-only
    assert 'user.get("role") not in ("admin", "super_admin"):' in orders_src


# ── Feature 5 — Day report + monthly export new columns ─────────────────
def test_day_report_route_exists(orders_src):
    assert "/salesman-orders/beat-run/day-report/export" in orders_src
    assert "async def beat_run_day_report_export" in orders_src
    # Carries Insights branding + admin's company name
    assert "FLOWRA Insights" in orders_src
    assert "company_header" in orders_src
    # Salesman can only export their own; admin can export any
    assert 'user.get("role") in ("admin", "super_admin"):' in orders_src
    # PDF + Excel formats
    assert 'format.lower() == "excel"' in orders_src
    assert "reportlab.platypus" in orders_src


def test_monthly_report_has_order_payment_columns(orders_src):
    # Raw Runs sheet adds two new headers
    assert '"Order Collected":' in orders_src
    assert '"Payment Collected":' in orders_src
    # Per-Salesman roll-up adds 4 new columns
    assert "Orders Collected" in orders_src
    assert "Payments Collected" in orders_src
    assert "Order Conv %" in orders_src
    assert "Payment Conv %" in orders_src


def test_summarize_runs_new_metrics():
    """The pure helper must compute orders/payments + conversion %."""
    from routes.salesman_orders import _summarize_runs
    runs = [
        {
            "salesman": "X", "run_date": "2026-02-01",
            "planned": [
                {"customer_name": "A", "visited_at": "2026-02-01T05:00:00",
                 "order_collected": True, "payment_collected": True},
                {"customer_name": "B", "visited_at": "2026-02-01T06:00:00",
                 "order_collected": False, "payment_collected": True},
                {"customer_name": "C", "visited_at": None,
                 "order_collected": None, "payment_collected": None},
            ],
            "unplanned": [
                {"customer_name": "D", "added_at": "2026-02-01T07:00:00",
                 "order_collected": True, "payment_collected": False},
            ],
        }
    ]
    s = _summarize_runs(runs)
    assert s["planned"] == 3
    assert s["visited"] == 2
    assert s["unplanned"] == 1
    assert s["orders_collected"] == 2  # A + D
    assert s["payments_collected"] == 2  # A + B
    # 3 completed visits (A, B, D); 2 orders, 2 payments → 66.7%
    assert s["order_pct"] == 66.7
    assert s["payment_pct"] == 66.7


# ── Source-spot-check Feature 4 (frontend-only — UI test by playwright) ──
def test_my_customers_route_used_for_existing_dropdown():
    """Backend already exposes /salesman-orders/my-customers — confirm it
    still returns mapped customers (the dropdown source)."""
    import inspect
    from routes import salesman_orders as so
    src = inspect.getsource(so)
    assert "/salesman-orders/my-customers" in src
    assert 'master.get("fy_customers", {}).get(fy, master.get("customers", []))' in src
