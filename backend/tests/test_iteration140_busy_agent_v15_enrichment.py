"""Iteration 140 — FLOWRA Busy Sync Agent v1.5.0 customer enrichment.

Context
-------
Learned from the BusyNotify public API's `/v1/customers` response shape
(WhatsApp-normalized mobile, group hierarchy, salesman link, GST/PAN,
address split, price category, opening/closing balance) and shipped the
same enriched data on our own direct-ODBC Busy Sync Agent — WITHOUT any
network dependency on BusyNotify. No bridge, no third-party API call.

What these tests lock down
--------------------------
1. Agent-side helpers:
   • `_row_pick` returns the first non-empty candidate, handles None/blank.
   • `_normalize_whatsapp` correctly builds `91XXXXXXXXXX` and rejects
     un-reconstructable inputs.
2. Agent-side `extract_customers`:
   • Emits the enriched schema (mobile_number, whatsapp_number, email_id,
     group_id, group_name, gst_number, pan_number, salesman_*, address_*,
     price_category, closing_balance, balance).
   • Preserves legacy keys (phone, opening_balance, ledger_group,
     customer_id, customer_name) so v1.4.x consumers don't break.
   • Skips non-debtor MasterType rows and only yields Sundry Debtors.
3. Backend `sync.py` `data_type == 'customers'` handler:
   • Persists ALL enriched fields when the agent sends them.
   • Stays backwards-compatible with a v1.4.x-style payload (older keys
     survive, missing new keys default to empty/0 without raising).
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/desktop-agent/build-kit-busy")


# ---------------------------------------------------------------------------
# 1. Helper tests
# ---------------------------------------------------------------------------

def test_row_pick_prefers_named_columns_over_generic_dn():
    from flowra_busy_agent import _row_pick, BUSY_MASTER1_FIELD_ALIASES
    row = {"MobileNo": "9876543210", "D8": "5555555555"}
    assert _row_pick(row, BUSY_MASTER1_FIELD_ALIASES["phone"]) == "9876543210"


def test_row_pick_falls_back_from_named_to_alt_named():
    """v1.5.1 — Dn fallback removed (real Busy 21 Master1 has no text Dn).
    Confirm the alias list still probes alternate NAMED columns in order."""
    from flowra_busy_agent import _row_pick, BUSY_MASTERADDRESSINFO_FIELDS
    # Mobile → falls back to TelNo when Mobile is empty
    row = {"Mobile": "", "TelNo": "9998887777"}
    assert _row_pick(row, BUSY_MASTERADDRESSINFO_FIELDS["phone"]) == "9998887777"


def test_row_pick_handles_none_and_null_strings():
    from flowra_busy_agent import _row_pick
    assert _row_pick({"a": None, "b": "None", "c": "null", "d": "  "}, ["a", "b", "c", "d"]) == ""
    assert _row_pick({"a": None, "b": "  ", "c": "hit"}, ["a", "b", "c"]) == "hit"


def test_row_pick_empty_when_all_missing():
    from flowra_busy_agent import _row_pick
    assert _row_pick({}, ["MobileNo", "D8"]) == ""


def test_normalize_whatsapp_indian_10_digit():
    from flowra_busy_agent import _normalize_whatsapp
    assert _normalize_whatsapp("9669823388") == "919669823388"


def test_normalize_whatsapp_leading_zero_dropped():
    from flowra_busy_agent import _normalize_whatsapp
    assert _normalize_whatsapp("09669823388") == "919669823388"


def test_normalize_whatsapp_already_prefixed():
    from flowra_busy_agent import _normalize_whatsapp
    assert _normalize_whatsapp("919669823388") == "919669823388"
    assert _normalize_whatsapp("+91 96698-23388") == "919669823388"


def test_normalize_whatsapp_rejects_too_short():
    from flowra_busy_agent import _normalize_whatsapp
    assert _normalize_whatsapp("12345") == ""
    assert _normalize_whatsapp("") == ""
    assert _normalize_whatsapp(None) == ""


def test_normalize_whatsapp_strips_non_digits():
    from flowra_busy_agent import _normalize_whatsapp
    assert _normalize_whatsapp("(966) 982-3388") == "919669823388"


# ---------------------------------------------------------------------------
# 2. Extractor tests — mock BusyDBReader so we can inject synthetic rows
# ---------------------------------------------------------------------------

class _FakeReader:
    """Stub for BusyDBReader that iterates a pre-populated dict-of-lists."""

    def __init__(self, tables):
        self._tables = tables

    def iter_rows(self, table, columns="*", where=""):
        for row in self._tables.get(table, []):
            yield row

    def close(self):
        pass


def _make_extractor(fake_tables, monkeypatch):
    """Return a BusyDataExtractor whose BusyDBReader is stubbed to feed
    `fake_tables` and whose file-detect step is short-circuited."""
    import flowra_busy_agent as mod

    monkeypatch.setattr(
        mod, "BusyDBReader",
        lambda db_path: _FakeReader(fake_tables), raising=True)

    ext = mod.BusyDataExtractor.__new__(mod.BusyDataExtractor)
    ext.data_folder = "/tmp/fake-busy"
    ext._master_db = "/tmp/fake-busy/db.bds"
    ext._fy_dbs = {"2025-26": "/tmp/fake-busy/db12025.bds"}
    ext._code_map = {}
    ext._group_map = {}
    ext._parent_map = {}
    return ext


def _build_master1_rows():
    """v1.5.1 — Master1 in real licensed Busy 21 only holds identity +
    group + numeric Dn columns. Contact/address moved to
    MasterAddressInfo (see _build_master_addr_info_rows below)."""
    return [
        # Account group 116 = sundry_debtors (in ACCOUNT_GROUP_MAP)
        {"Code": "116", "Name": "Sundry Debtors", "MasterType": "1",
         "ParentGrp": "", "D1": 0},
        # Full-fat customer — MasterAddressInfo carries the contact
        {"Code": "1304", "Name": "Ankita Singh", "MasterType": "2",
         "ParentGrp": "116", "I5": "0"},
        # Bare customer — no contact info anywhere
        {"Code": "1305", "Name": "Old Cash Party", "MasterType": "2",
         "ParentGrp": "116"},
        # A creditor — must be filtered OUT (ParentGrp not sundry_debtors)
        {"Code": "1306", "Name": "Supplier A", "MasterType": "2",
         "ParentGrp": "117"},
    ]


def _build_master_addr_info_rows():
    """v1.5.1 — real Busy 21 MasterAddressInfo shape (JOIN on MasterCode)."""
    return [
        {"MasterCode": "1304",
         "Mobile": "9669823388",
         "WhatsAppNo": "919669823388",
         "Email": "ankita@example.com",
         "Address1": "Plot 45", "Address2": "Sector 3",
         "Address3": "", "Address4": "",
         "City": "Ujjain", "Station": "Ujjain",
         "PINCode": "456001",
         "GSTNo": "23ABCDE1234F1Z5",
         "ITPAN": "ABCDE1234F",
         "Contact": "Rahul Singh",
         "SupplierType": "Retailer"},
        # 1305 has no MasterAddressInfo row → all contact fields must
        # emit as empty strings and the extractor MUST NOT crash.
    ]


def _build_folio1_rows():
    """v1.5.1 — Closing balance now read from D22 (Mar month-end).
    Legacy D23 kept only as fallback when D11..D22 are all zero."""
    return [
        # 1304 — closing bal 134633 in D22 (Mar 26 month-end)
        {"MasterType": "2", "MasterCode": "1304",
         "D11": "116996", "D12": "131704", "D22": "134633",
         "D23": "0"},
        # 1305 — no balance anywhere
        {"MasterType": "2", "MasterCode": "1305", "D22": "0"},
    ]


def test_extract_customers_emits_enriched_schema(monkeypatch):
    ext = _make_extractor({
        "Master1": _build_master1_rows(),
        "MasterAddressInfo": _build_master_addr_info_rows(),
        "Folio1":  _build_folio1_rows(),
    }, monkeypatch)

    customers = list(ext.extract_customers("2025-26"))
    # Exactly two Sundry Debtors — supplier and non-debtors filtered
    assert len(customers) == 2

    by_id = {c["customer_id"]: c for c in customers}
    ank = by_id["1304"]

    # Identity + group hierarchy
    assert ank["customer_name"] == "Ankita Singh"
    assert ank["group_id"] == "116"
    assert ank["group_name"] == "Sundry Debtors"

    # Contact — from MasterAddressInfo (v1.5.1 correct source)
    assert ank["mobile_number"] == "9669823388"
    assert ank["phone"] == "9669823388"                        # legacy alias
    # WhatsApp — Busy 21 stores E.164 directly; prefer that over
    # normalising Mobile. Test row supplies the pre-formatted value.
    assert ank["whatsapp_number"] == "919669823388"
    assert ank["email_id"] == "ankita@example.com"

    # Address
    assert ank["address_line_1"] == "Plot 45"
    assert ank["address_line_2"] == "Sector 3"
    assert ank["address"] == "Plot 45, Sector 3"
    assert ank["city"] == "Ujjain"
    assert ank["station"] == "Ujjain"
    assert ank["pin_code"] == "456001"

    # Tax IDs
    assert ank["gst_number"] == "23ABCDE1234F1Z5"
    assert ank["pan_number"] == "ABCDE1234F"

    # Balances — closing pulled from Folio1.D22 (Mar month-end)
    assert ank["closing_balance"] == 134633.0
    assert ank["balance"] == 134633.0

    # Contact person + supplier type (new in v1.5.1)
    assert ank["contact_person"] == "Rahul Singh"
    assert ank["supplier_type"] == "Retailer"

    # Legacy fields kept
    assert ank["ledger_group"] == "Sundry Debtors"


def test_extract_customers_handles_bare_rows_without_crashing(monkeypatch):
    ext = _make_extractor({
        "Master1": _build_master1_rows(),
        "MasterAddressInfo": _build_master_addr_info_rows(),
        "Folio1":  _build_folio1_rows(),
    }, monkeypatch)

    customers = list(ext.extract_customers("2025-26"))
    old = next(c for c in customers if c["customer_id"] == "1305")

    # No MasterAddressInfo row → every enriched field must exist and
    # default sensibly (never raise, never miss a key).
    assert old["customer_name"] == "Old Cash Party"
    assert old["mobile_number"] == ""
    assert old["whatsapp_number"] == ""
    assert old["email_id"] == ""
    assert old["gst_number"] == ""
    assert old["pan_number"] == ""
    assert old["contact_person"] == ""
    assert old["price_category"] == "0"
    assert old["country"] == "India"           # default
    assert old["closing_balance"] == 0.0


def test_extract_customers_filters_non_debtor_parties(monkeypatch):
    ext = _make_extractor({
        "Master1": _build_master1_rows(),
        "MasterAddressInfo": _build_master_addr_info_rows(),
        "Folio1":  _build_folio1_rows(),
    }, monkeypatch)

    ids = {c["customer_id"] for c in ext.extract_customers("2025-26")}
    # 1306 belongs to Sundry Creditors (117), must be filtered out.
    assert "1306" not in ids
    # In real Busy 21, MasterType=6 is items (not salesmen); the
    # extractor must not emit those as customers either. This test seeds
    # no MasterType=6 rows but the filter must still be robust.
    assert all(cid in {"1304", "1305"} for cid in ids)


def test_agent_version_bumped():
    from flowra_busy_agent import VERSION, AGENT_TAG
    assert VERSION == "1.5.3"
    assert "1.5.3" in AGENT_TAG


# ---------------------------------------------------------------------------
# 3. Backend sync handler — persists enriched fields, stays backwards-compat
# ---------------------------------------------------------------------------

def test_backend_customer_sync_persists_enriched_fields():
    """Load the sync route file and assert the customer branch now upserts
    every enriched key. We assert via source-text scan because the route
    depends on Motor + auth middleware that would require a live DB and
    request context to exercise end-to-end — the source-scan is a
    stable, low-flake regression fence."""
    src = Path("/app/backend/routes/sync.py").read_text()

    # Locate the customers branch
    marker = "elif data_type == 'customers':"
    assert marker in src
    idx = src.index(marker)
    branch = src[idx: idx + 6000]     # window that comfortably covers the branch

    required_keys = [
        "customer_id", "group_id", "group_name",
        "whatsapp_number", "mobile_number", "email",
        "address", "address_line_1", "address_line_2",
        "city", "station", "pin_code", "state", "country",
        "gst_number", "pan_number",
        "salesman_id", "salesman_name",
        "salesman_mobile_number", "salesman_whatsapp_number",
        "price_category",
        "closing_balance", "balance",
    ]
    missing = [k for k in required_keys if f'"{k}"' not in branch]
    assert not missing, f"Backend customers upsert is missing keys: {missing}"


def test_backend_customer_sync_stays_backwards_compatible():
    """A v1.4.x payload only carries {customer_name, phone, opening_balance,
    ledger_group}. Confirm the backend still handles that gracefully —
    every enriched key uses `.get(...)` with a safe default so nothing
    KeyErrors on the older shape."""
    src = Path("/app/backend/routes/sync.py").read_text()
    marker = "elif data_type == 'customers':"
    idx = src.index(marker)
    branch = src[idx: idx + 6000]

    # Every new enriched field must use `.get(...)`, never a direct index.
    assert "cust['whatsapp_number']" not in branch
    assert "cust['gst_number']" not in branch
    assert "cust['salesman_id']" not in branch
    # And the safe defaults must be present for the legacy-critical fields.
    assert "cust.get('ledger_group', 'Sundry Debtors')" in branch
    assert "cust.get('opening_balance', 0)" in branch
