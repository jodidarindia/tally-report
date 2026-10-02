"""iter-174 — Sticky-header coverage inside OrderForm + Add-new-item in
Edit Order modal.

Context: user complained the Salesman App's sticky freeze stopped at the
tab bar; they wanted the freeze to extend down to the item-search box
once a customer is picked. They also wanted to be able to add brand-new
SKUs when editing a pending order (previously edit-only touched existing
lines).

These tests are static source-level assertions on
`frontend/src/pages/SalesmanOrderApp.js`. They catch regressions that
would quietly re-break the UX if someone refactors the file (which is
likely — it's 1,750+ lines and already slated for a split).
"""
from pathlib import Path
import pytest

FRONT = Path("/app/frontend/src/pages/SalesmanOrderApp.js")


@pytest.fixture(scope="module")
def src() -> str:
    return FRONT.read_text(encoding="utf-8")


# ─── A — OrderForm sticky block ───────────────────────────────────────
def test_orderform_sticky_wrapper_exists(src: str):
    """The sticky wrapper must sit at top-14 (right under the global
    navbar h-14 = 56px) with the shared z-30 we use for sub-nav strips
    across the app. If this disappears the back/customer/pills scroll
    away mid-order which was the exact bug the user complained about."""
    assert 'data-testid="order-form-sticky"' in src
    assert 'sticky top-14 z-30' in src


def test_orderform_sticky_contains_search(src: str):
    """The sticky block must render the current section's search input.
    We implement it as a self-invoking function that maps section → state
    pair, so the single sticky input stays in sync with whichever section
    is active."""
    # The map covers all 4 sections.
    assert "repeat:  { val: histSearch" in src
    assert "city:    { val: citySearch" in src
    assert "suggest: { val: suggSearch" in src
    assert "browse:  { val: catSearch" in src


def test_old_in_section_search_boxes_removed(src: str):
    """Previously each section rendered its own search input. Keeping
    them around would stack two search bars (one sticky, one static)
    which is the hallmark of a broken refactor. Guard against that."""
    # The sticky search uses `rounded-lg bg-white` (added background). The
    # old per-section inputs used `rounded-lg"` without bg-white. We assert
    # the OLD exact JSX string no longer appears for each section's input
    # declaration (`setHistSearch`, `setCitySearch`, `setSuggSearch`,
    # `setCatSearch` must each appear exactly ONCE — inside the sticky map).
    for setter in ("setHistSearch", "setCitySearch", "setSuggSearch", "setCatSearch"):
        # 1 declaration + 1 use inside the map = exactly 2 occurrences.
        count = src.count(setter)
        assert count == 2, f"{setter} appears {count}× (expected 2 — declaration + sticky use)"


def test_salesmanview_sticky_hidden_in_orderform(src: str):
    """When we're inside OrderForm the SalesmanView's sticky header must
    collapse so the OrderForm's taller sticky can pin directly under the
    global navbar. Stacking two stickies hides the item list on mobile."""
    assert "const inOrderForm = tab==='new' && !!selCustomer" in src
    assert "{!inOrderForm && (" in src


# ─── B — Edit Order modal — add new item ───────────────────────────────
def test_edit_modal_add_item_search_present(src: str):
    """The modal must now expose a search box for new SKUs so salesmen
    don't have to abandon the edit and start a brand-new order just to
    append one line."""
    assert 'data-testid="edit-add-item-search"' in src
    assert "Add new item — search by name or part number" in src


def test_edit_modal_fetches_catalog(src: str):
    """The modal must fetch the catalog on mount via the same endpoint
    OrderForm uses — not duplicate the SKU master in the frontend."""
    assert "/api/salesman-orders/catalog?company_id=" in src
    # EditOrderModal must accept companyId prop (it's needed for the
    # tenant-scoped catalog call).
    assert "function EditOrderModal({ order, hdr, companyId, onClose, onSaved })" in src


def test_edit_modal_add_item_prevents_duplicates(src: str):
    """Adding a SKU already on the order would silently merge or ship
    duplicates; neither is OK. Reject with a toast."""
    assert "Already in this order" in src


def test_edit_modal_default_qty_is_one(src: str):
    """When adding from the edit modal we default qty to 1 (unlike the
    New Order flow where qty defaults to 0). Rationale: the salesman has
    already committed to the order and is actively appending — making
    them tap + after picking the item is friction."""
    # The newly-added line sets `quantity: 1`.
    assert "item_name: it.item_name," in src
    # Find the addItem function and ensure it sets quantity: 1.
    start = src.find("const addItem = (it) => {")
    end = src.find("};", start)
    assert start != -1 and end != -1
    chunk = src[start:end]
    assert "quantity: 1," in chunk


def test_edit_modal_passed_company_id(src: str):
    """SalesmanView must forward companyId to the modal so the catalog
    fetch is scoped to the right tenant/company."""
    # The modal invocation must now include companyId={companyId}.
    assert "<EditOrderModal order={editOrder} hdr={hdr} companyId={companyId}" in src
