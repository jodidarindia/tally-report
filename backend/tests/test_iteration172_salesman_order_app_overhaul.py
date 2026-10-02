"""Regression tests for iter-172 — Salesman Order App overhaul.

Scope (10 user asks):
  1. Freeze cart panel (sticky positioning on desktop).
  2. Align cart with customer list top (grid uses `lg:items-start`).
  3. Mapped customers alphabetically sorted + search bar.
  4. On +, cart quantity defaults to zero.
  5. Qty +/- control appears INLINE on each item row.
  6. Pending orders are editable by the submitting salesman via a
     new PATCH /salesman-orders/orders/{order_id} endpoint; blocked
     once status != 'pending'.
  7. Per-salesman `order_notify_email` input in the salesman manage
     form AND persisted on the salesman_master document AND added to
     the admin-notify email CC list.
  8. Logout flashes a brief "features no longer available" screen.
  9. Submit button triggers a 2-3s customer-outstanding popup before
     the actual POST.
  10. All item lists (repeat / city / suggestions / browse) sort by
      ABCD class (A first) and have a search bar.

These are static assertions — the running backend (and its Atlas
database) are the subject of a separate infrastructure concern. They
verify the SHAPE of the implementation so a future refactor can't
silently regress any of the 10 asks.
"""
import os
import re
import pytest

FRONT = "/app/frontend/src/pages/SalesmanOrderApp.js"
PERF = "/app/frontend/src/pages/SalesmanPerformance.js"
APP = "/app/frontend/src/App.js"
BACK_ORDERS = "/app/backend/routes/salesman_orders.py"
BACK_MASTER = "/app/backend/routes/salesman.py"


def _read(p: str) -> str:
    assert os.path.isfile(p), f"missing: {p}"
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def front(): return _read(FRONT)
@pytest.fixture(scope="module")
def perf(): return _read(PERF)
@pytest.fixture(scope="module")
def appjs(): return _read(APP)
@pytest.fixture(scope="module")
def back_orders(): return _read(BACK_ORDERS)
@pytest.fixture(scope="module")
def back_master(): return _read(BACK_MASTER)


# ─── 1 & 2 — Cart freeze + alignment ────────────────────────────────────
def test_cart_panel_is_sticky_on_desktop(front):
    assert "lg:sticky lg:top-3" in front
    # Grid parent must align children to top so cart lines up with the
    # section-pills row, not the viewport middle.
    assert "lg:items-start" in front


# ─── 3 — Customer list: alphabetical + search ───────────────────────────
def test_customer_search_and_sort(front):
    assert "customer-search" in front
    assert "custSearch" in front
    assert "localeCompare" in front
    # The sort is piped through filter() → sort() so an empty search still
    # produces a sorted list.
    assert ".sort((a,b) => (a.customer_name" in front


# ─── 4 — Add defaults qty to 0 ──────────────────────────────────────────
def test_add_to_cart_defaults_qty_zero(front):
    # addToCart signature changed from qty=1 to qty=0 (user explicitly asked).
    assert "const addToCart = (item, qty = 0)" in front
    assert "quantity: Math.max(0, Math.round(qty || 0))" in front


# ─── 5 — Inline +/− stepper on every row ────────────────────────────────
def test_inline_qty_stepper_on_rows(front):
    assert "function QtyStepper(" in front
    assert "cartQty={cartQtyFor(" in front
    assert "onBump={(d)=>bumpItem(" in front
    # All three row types delegate qty controls to the shared stepper.
    for comp in ("RepeatRow", "SuggestRow", "CatalogRow"):
        m = re.search(rf"function {comp}\(.*?\n\s+return \(.*?<QtyStepper", front, re.S)
        assert m, f"{comp} is not using <QtyStepper>"


# ─── 6 — Salesman edit of pending orders ────────────────────────────────
def test_backend_patch_endpoint_exists(back_orders):
    assert '@router.patch("/salesman-orders/orders/{order_id}")' in back_orders
    assert "salesman_edit_pending_order" in back_orders
    # Ownership + status gate must be present.
    assert "Not your order" in back_orders
    assert "edit no longer allowed" in back_orders
    assert '(order.get("status") or "").lower() != "pending"' in back_orders


def test_frontend_edit_flow_wired_up(front):
    assert "EditOrderModal" in front
    assert "editOrder" in front
    # Edit button is conditionally rendered only for pending orders.
    assert "(o.status||'').toLowerCase() === 'pending'" in front
    # PATCH call targets the new endpoint.
    assert "/api/salesman-orders/orders/${order.order_id}" in front


# ─── 7 — Order-notify email (admin UI + backend persistence + email CC) ─
def test_notify_email_persisted_on_master(back_master):
    # Field is parsed from body, written on insert AND update, surfaced in GET.
    assert 'body.get("order_notify_email")' in back_master
    assert '"order_notify_email": order_notify_email,' in back_master
    assert '"order_notify_email": m.get("order_notify_email", "")' in back_master


def test_admin_email_cc_includes_notify_email(back_orders):
    # Lookup in salesman_master → cc list → attached to resend params.
    assert "db.salesman_master.find_one" in back_orders
    assert "order_notify_email" in back_orders
    assert 'params["cc"] = cc_list' in back_orders


def test_admin_ui_has_notify_email_input(perf):
    assert "salesman-notify-email-input" in perf
    assert "order_notify_email" in perf
    assert "Order Notification Email" in perf


# ─── 8 — Logout flash splash ────────────────────────────────────────────
def test_logout_flash_present(appjs):
    assert "showLogoutFlash" in appjs
    assert "logout-flash" in appjs
    assert "features are no longer available" in appjs
    # Must flip the flag back off so a re-login screen is clean.
    assert "setShowLogoutFlash(false)" in appjs


# ─── 9 — Outstanding popup on submit, auto-closes after ~2.5s ──────────
def test_outstanding_popup_on_submit(front):
    assert "outstandingPopup" in front
    assert "outstanding-popup" in front
    # Pre-submit fetch to /customers/outstanding.
    assert "/api/customers/outstanding?search=" in front
    # Explicit 2.5s wait before the actual POST.
    assert "setTimeout(r => r, 2500)" in front or "setTimeout(r, 2500)" in front


# ─── 10 — ABCD sort + per-section search ────────────────────────────────
def test_abcd_sort_helper_present(front):
    assert "const abcRank" in front
    assert "{A:0, B:1, C:2, D:3}" in front
    assert "const sortByAbc" in front
    # histItems / suggItems / city render / filtered all go through sortByAbc.
    assert "const histItems = sortByAbc(" in front
    assert "const suggItems = sortByAbc(" in front
    assert "const filtered = sortByAbc(" in front
    assert "sortByAbc(citySearch" in front  # city section does it inline


def test_search_box_per_section(front):
    for tid in ("hist-search", "city-search", "sugg-search", "cat-search"):
        assert f'data-testid="{tid}"' in front, f"missing search input {tid}"
