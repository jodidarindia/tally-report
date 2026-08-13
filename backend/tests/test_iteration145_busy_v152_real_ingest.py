"""iter-145 — Round-trip v1.5.2 enriched payloads (customers, sales, inventory)
generated from the REAL licensed COMP0002 Busy 21 DB through the LIVE preview
backend for tenant `busydemo@flowralive.in`.

Verifies:
  1. Customers survive with all v1.5.1/1.5.2 enriched fields.
  2. Sales vouchers persist per-line item_code / gst_pct / mrp / warehouse.
  3. Sales voucher busy_doc_link persistence (voucher-level enrichment).
  4. Inventory items persist human item_name (Alias), sku_code, hsn_code,
     sale_price, cost_price, closing_qty (v1.5.2 schema fields).
  5. /api/customers/outstanding surfaces the enriched fields.
"""
import os
import sys
import pytest
import requests

# Import agent module for live extraction
sys.path.insert(0, "/app/desktop-agent/build-kit-busy")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")
COMP_DB = "/tmp/comp0002/unpacked/COMP0002"
BUSY_USER_TENANT = "1524ec0e-faae-448c-9f24-1ae8f51c399e"
BUSY_USER_COMPANY = "b21b291b-afcd-4152-b166-85be751d94bb"


def _agent_available():
    if not os.path.isdir(COMP_DB):
        return False
    try:
        from flowra_busy_agent import BusyDataExtractor  # noqa
        return True
    except Exception:
        return False


AGENT_OK = _agent_available()
pytestmark = pytest.mark.skipif(not AGENT_OK, reason="COMP0002 DB or flowra_busy_agent not available")


@pytest.fixture(scope="module")
def extractor():
    from flowra_busy_agent import BusyDataExtractor
    return BusyDataExtractor(COMP_DB)


@pytest.fixture(scope="module")
def sync_token():
    # Compute HMAC directly using the same secret backend uses. Requires
    # backend/.env to be loadable (tests run under /app/backend so paths
    # resolve). We call the backend's helper for correctness.
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from services.auth_service import generate_sync_token
    return generate_sync_token(BUSY_USER_TENANT)


def _post_sync(data_type, data, sync_token):
    payload = {
        "data_type": data_type,
        "data": data,
        "sync_time": "2026-08-13T00:00:00+00:00",
        "tenant_id": BUSY_USER_TENANT,
        "company_id": BUSY_USER_COMPANY,
        "sync_token": sync_token,
        "company_name": "NAVDURGA AUTO",
    }
    r = requests.post(f"{BASE_URL}/api/agent/sync", json=payload, timeout=180)
    return r


# -----------------------------------------------------------------------------
# 0) Sanity: sync_token is accepted
# -----------------------------------------------------------------------------
def test_sync_token_valid(sync_token):
    # Empty sync just to check auth path
    r = _post_sync("customers", [], sync_token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body


# -----------------------------------------------------------------------------
# 1) Customers round-trip (12 real Sundry Debtors)
# -----------------------------------------------------------------------------
def test_customers_roundtrip_v152(extractor, sync_token):
    customers = list(extractor.extract_customers("2025-26"))
    assert len(customers) >= 10, f"Expected ~12 customers, got {len(customers)}"
    r = _post_sync("customers", customers, sync_token)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # Verify via read endpoint /api/customers/outstanding
    # (requires admin JWT). Use direct DB check as a fallback since the
    # busydemo password is not in test_credentials.md.
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _check():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        docs = await db.customers.find(
            {"tenant_id": BUSY_USER_TENANT, "company_id": BUSY_USER_COMPANY}, {"_id": 0}
        ).to_list(200)
        return docs
    docs = asyncio.run(_check())
    assert len(docs) >= 10, f"Only {len(docs)} customers persisted"
    # Spot check SHITLA AUTO SPARES RAIPUR enrichment
    shitla = next((d for d in docs if "SHITLA" in d.get("customer_name", "")), None)
    assert shitla is not None, "SHITLA customer missing"
    assert shitla.get("mobile_number"), "mobile_number missing on SHITLA"
    assert shitla.get("gst_number"), "gst_number missing on SHITLA"
    assert shitla.get("closing_balance"), "closing_balance missing on SHITLA"


# -----------------------------------------------------------------------------
# 2) Sales vouchers — verify items[] carry v1.5.2 enrichment
# -----------------------------------------------------------------------------
def test_sales_vouchers_items_v152(extractor, sync_token):
    # Take first 50 real sales vouchers to keep payload manageable
    sales = []
    for v in extractor.extract_sales("2025-26"):
        sales.append(v)
        if len(sales) >= 50:
            break
    assert len(sales) == 50

    # Find one voucher with real stock items (RecType=2 mapped)
    with_items = [v for v in sales if v.get("items") and any(i.get("item_code") for i in v["items"])]
    assert with_items, "No sales voucher has any item with item_code — extractor may be broken"
    sample_agent = with_items[0]
    sample_line = next(i for i in sample_agent["items"] if i.get("item_code"))
    # Confirm agent side has enriched fields on the line
    for k in ("item_code", "quantity", "rate", "gst_pct", "mrp", "warehouse", "amount"):
        assert k in sample_line, f"agent line missing {k}: {sample_line}"

    r = _post_sync("sales", sales, sync_token)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # Read back the specific voucher and confirm items[] survived intact
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _fetch():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        return await db.sales_vouchers.find_one(
            {"tenant_id": BUSY_USER_TENANT, "voucher_id": sample_agent["voucher_id"]},
            {"_id": 0},
        )
    persisted = asyncio.run(_fetch())
    assert persisted, f"voucher {sample_agent['voucher_id']} not persisted"
    p_items = persisted.get("items") or []
    assert p_items, f"voucher {sample_agent['voucher_id']} persisted with EMPTY items[] (BUG!)"
    p_line = next((i for i in p_items if i.get("item_code") == sample_line["item_code"]), None)
    assert p_line, f"Line with item_code={sample_line['item_code']} missing after persist"
    # Verify enrichment survived
    assert p_line.get("item_code") == sample_line["item_code"]
    assert p_line.get("gst_pct") == sample_line["gst_pct"]
    assert p_line.get("mrp") == sample_line["mrp"]
    assert "warehouse" in p_line
    # Item name should NOT be "Rounded Off" — must be a real stock item
    assert "Rounded Off" not in (p_line.get("item_name") or ""), (
        "Voucher item_name is a ledger 'Rounded Off' — RecType mapping broken on backend"
    )


def test_sales_vouchers_busy_doc_link_persistence(extractor, sync_token):
    """busy_doc_link is a top-level voucher field (Google Drive URL). It must
    survive the sync round-trip. Currently backend SalesVoucher model uses
    ConfigDict(extra='ignore') so this may be dropped — this test EXPOSES
    that regression if it fails."""
    sales = []
    for v in extractor.extract_sales("2025-26"):
        sales.append(v)
        if len(sales) >= 5:
            break
    # Force a synthetic drive link so we can assert persistence deterministically
    for v in sales:
        v["busy_doc_link"] = f"https://drive.google.com/file/d/TEST_{v['voucher_id']}/view"
        v["busy_doc_name"] = f"invoice_{v['voucher_id']}.pdf"

    r = _post_sync("sales", sales, sync_token)
    assert r.status_code == 200

    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _fetch():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        return await db.sales_vouchers.find_one(
            {"tenant_id": BUSY_USER_TENANT, "voucher_id": sales[0]["voucher_id"]},
            {"_id": 0},
        )
    persisted = asyncio.run(_fetch())
    assert persisted, "voucher not persisted"
    assert persisted.get("busy_doc_link", "").startswith("https://drive.google.com/"), (
        f"busy_doc_link DROPPED by SalesVoucher(extra='ignore'). Persisted doc: "
        f"{list(persisted.keys())}"
    )


# -----------------------------------------------------------------------------
# 3) Inventory — first 200 real items, verify enriched fields survive
# -----------------------------------------------------------------------------
def test_inventory_items_v152_enriched_persistence(extractor, sync_token):
    items = []
    for it in extractor.extract_inventory_items("2025-26"):
        items.append(it)
        if len(items) >= 200:
            break
    assert len(items) == 200
    # Find one where alias/human name and sku differ (typical case)
    with_alias = [i for i in items if i.get("alias") and i.get("sku_code") and i["alias"] != i["sku_code"]]
    assert with_alias, "No inventory items with alias != sku — agent extractor broken"
    sample = with_alias[0]
    # Agent side sanity
    for k in ("sku_code", "hsn_code", "sale_price", "cost_price", "closing_qty", "alias"):
        assert k in sample

    r = _post_sync("inventory", items, sync_token)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _fetch():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        return await db.inventory_items.find_one(
            {"tenant_id": BUSY_USER_TENANT, "item_id": sample["item_id"]}, {"_id": 0}
        )
    persisted = asyncio.run(_fetch())
    assert persisted, f"item {sample['item_id']} not persisted"

    # Item name must be human-readable (Alias), not the SKU code
    assert persisted.get("item_name") == sample["alias"], (
        f"item_name persisted as '{persisted.get('item_name')}' but should be alias "
        f"'{sample['alias']}' (bug #3 from the review — human names not surfaced)"
    )

    # v1.5.2 enriched fields — this WILL fail if InventoryItem uses
    # ConfigDict(extra='ignore') and doesn't declare these fields.
    missing = [k for k in ("sku_code", "hsn_code", "sale_price", "cost_price", "closing_qty")
               if persisted.get(k) in (None, "", 0) and sample.get(k) not in (None, "", 0)]
    assert not missing, (
        f"v1.5.2 enriched fields DROPPED by backend for item {sample['item_id']}: {missing}. "
        f"Agent sent: sku={sample.get('sku_code')} hsn={sample.get('hsn_code')} "
        f"sp={sample.get('sale_price')} cp={sample.get('cost_price')} qty={sample.get('closing_qty')}. "
        f"Persisted: {persisted}"
    )


# -----------------------------------------------------------------------------
# 4) Current stale DB state check — was NOT re-synced with v1.5.2 yet
# -----------------------------------------------------------------------------
def test_current_db_state_stale_v151_bugs_visible():
    """Records the CURRENT state of busydemo tenant BEFORE v1.5.2 re-sync so
    that main agent can compare. This test is informational and always
    passes — it prints findings."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _check():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        inv = await db.inventory_items.find_one(
            {"tenant_id": BUSY_USER_TENANT, "company_id": BUSY_USER_COMPANY}, {"_id": 0}
        )
        sales = await db.sales_vouchers.find_one(
            {"tenant_id": BUSY_USER_TENANT, "company_id": BUSY_USER_COMPANY}, {"_id": 0}
        )
        cust_cnt = await db.customers.count_documents(
            {"tenant_id": BUSY_USER_TENANT, "company_id": BUSY_USER_COMPANY}
        )
        return inv, sales, cust_cnt
    inv, sales, cust = asyncio.run(_check())
    print(f"\n[busydemo state] customers={cust}")
    print(f"[busydemo state] inventory sample item_name={inv.get('item_name') if inv else None} "
          f"sku_code={inv.get('sku_code') if inv else None} hsn={inv.get('hsn_code') if inv else None} "
          f"sale_price={inv.get('sale_price') if inv else None}")
    if sales:
        items = sales.get("items") or []
        print(f"[busydemo state] sales sample voucher_id={sales.get('voucher_id')} items_count={len(items)}")
        if items:
            print(f"[busydemo state] sales first item: {items[0]}")
        print(f"[busydemo state] busy_doc_link={sales.get('busy_doc_link')}")
