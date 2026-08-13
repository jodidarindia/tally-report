"""Iteration 142 — Licensed Busy 21 support (v1.5.1 JET4 pure-Python read).

Trigger
-------
User provided a real, licensed Busy 21 company DB (COMP0002 – NAVDURGA
AUTO, 12 Sundry Debtors, 10,287 MasterAddressInfo rows, 11,832 Master1
rows) and shipped the following runtime error from the Windows agent:

    pyodbc.Error: ('HY000',
      "[HY000] [Microsoft][ODBC Microsoft Access Driver] General error
       Unable to open registry key Temporary (volatile) Ace DSN for
       process 0x55c ... Not a valid password. (-1905)")

RCA (two independent problems, both fixed in v1.5.1):
  1. The Access ODBC driver on Windows Server / restricted accounts
     can't write its temp DSN under HKLM, so even a correct password
     would still fail. Fix: added `Exclusive=1` to the ODBC connection
     string.
  2. Licensed Busy 21 uses a proprietary per-install `.bds` password
     that isn't in any known fallback chain. Fix: dropped in
     `access_parser` (pure-Python JET4 reader), which reads the file
     directly — no driver, no password prompt, no OS-level requirements.

Additional finding (verified against the real DB):
  • Party contact / address / GST / PAN / mobile / WhatsApp / station /
    PIN all live in `MasterAddressInfo`, NOT on Master1.
  • Busy 21's `MasterType=6` is items (not salesmen as in older builds).
  • Party closing balance for the FY is at `Folio1.D22` (Mar month-end),
    not `Folio1.D23`.

These tests protect all three findings and are the first in the suite to
run against the AGENT ITSELF end-to-end via `access_parser`, so any
regression in the reader path shows up here.
"""
import asyncio
import sys
from pathlib import Path

import pytest

# Point at the agent so `from flowra_busy_agent import …` works.
sys.path.insert(0, "/app/desktop-agent/build-kit-busy")


# ---------------------------------------------------------------------------
# 1. BusyDBReader now prefers access_parser + fixes the ODBC temp-DSN error
# ---------------------------------------------------------------------------

AGENT_SRC = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()


def test_odbc_conn_string_now_uses_exclusive_flag():
    """Regression fence for the -1905 / 'Temporary Ace DSN' registry
    error. Windows Server + service accounts can't create HKLM temp
    DSNs; Exclusive=1 bypasses that path in the ACE driver."""
    assert '"Exclusive=1;"' in AGENT_SRC or "'Exclusive=1;'" in AGENT_SRC, \
        "Exclusive=1 must be part of the ODBC connection string"


def test_access_parser_is_primary_strategy():
    """access_parser must be attempted BEFORE OLE DB / ODBC — this is
    what unblocks licensed Busy 21 without a driver install."""
    idx_ap = AGENT_SRC.find("_try_access_parser")
    idx_oledb = AGENT_SRC.find("_try_oledb(")
    # We're only interested in the FIRST call site inside _get_connection.
    body_start = AGENT_SRC.find("def _get_connection")
    body = AGENT_SRC[body_start: body_start + 2000]
    assert body.find("_try_access_parser") != -1, \
        "_try_access_parser must be called from _get_connection"
    assert body.find("_try_access_parser") < body.find("_try_oledb("), \
        "access_parser must be tried BEFORE OLE DB in _get_connection"


def test_requirements_bundles_access_parser():
    """Version-fence: the built EXE must ship access_parser."""
    req = Path("/app/desktop-agent/build-kit-busy/requirements.txt").read_text()
    assert "access-parser" in req, "requirements.txt must include access-parser"


# ---------------------------------------------------------------------------
# 2. Schema fix — MasterAddressInfo JOIN + D22 closing balance
# ---------------------------------------------------------------------------

def test_master_address_info_field_map_present():
    """The new alias map for MasterAddressInfo must expose all fields
    the enriched customer payload needs. Legacy Master1 aliases must
    have been superseded (no 'D8 for phone' bogus entries)."""
    from flowra_busy_agent import BUSY_MASTERADDRESSINFO_FIELDS
    for key in ("phone", "email", "gstin", "pan",
                "address_1", "address_2", "address_3", "address_4",
                "city", "station", "pincode", "contact", "whatsapp"):
        assert key in BUSY_MASTERADDRESSINFO_FIELDS, f"missing key: {key}"
    # No numeric-Dn fallback poisoning the phone alias any more.
    assert "D8" not in BUSY_MASTERADDRESSINFO_FIELDS["phone"]


def test_closing_balance_prefers_d22_over_d23():
    """Real licensed Busy 21 stores March month-end in D22, and D23 is
    typically zero. Legacy code read D23 → every party's closing_balance
    came out as 0. Regression fence: closing balance is now driven from
    the last non-zero of D11..D22, with D23 only as a final fallback."""
    src = AGENT_SRC
    assert "D22" in src, "D22 must appear in the folio balance loader"
    # Verify D22 comes before D23 in the fallback chain
    folio_fn_start = src.find("def _load_folio_closing_bal")
    folio_fn = src[folio_fn_start: folio_fn_start + 3000]
    idx_d22 = folio_fn.find("D22")
    idx_d23 = folio_fn.find("D23")
    assert 0 <= idx_d22 < idx_d23, \
        "D22 must be tried BEFORE D23 in the fallback chain"


# ---------------------------------------------------------------------------
# 3. End-to-end with real licensed Busy 21 data (if uploaded to /tmp)
# ---------------------------------------------------------------------------

REAL_DB_ROOT = Path("/tmp/comp0002/unpacked/COMP0002")


@pytest.mark.skipif(
    not (REAL_DB_ROOT / "db12025.bds").exists(),
    reason="Real Busy 21 sample DB not present — skip live-data e2e"
)
def test_end_to_end_extract_from_real_busy21_db():
    """Live-data test — exercises the FULL agent path against the actual
    licensed Busy 21 DB the user provided. Locks in that we extract:
      • non-zero Sundry Debtor count
      • real GSTs (must start with 2-digit state + PAN pattern)
      • real WhatsApp numbers in E.164 shape (91XXXXXXXXXX)
      • real closing balance from Folio1.D22 (non-zero for the flagship
        party 6003 SHITLA AUTO SPARES)."""
    from flowra_busy_agent import BusyDataExtractor
    ext = BusyDataExtractor(str(REAL_DB_ROOT))
    assert "2025-26" in ext.get_available_fys()

    customers = list(ext.extract_customers("2025-26"))
    assert len(customers) > 0, "No customers extracted from real DB"

    # The flagship party the user data has 12 debtors; at least ONE must
    # have a non-empty GST that matches the 15-char GSTIN pattern.
    import re
    # Actual GSTIN structure: 2-digit state + 10-char PAN + entity num
    # + 'Z' + alphanumeric check char. 15 chars total.
    gst_pat = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z][0-9A-Z]$")
    with_gst = [c for c in customers if c["gst_number"]]
    assert with_gst, "No customers have GST populated — schema JOIN broken"
    for c in with_gst:
        assert gst_pat.match(c["gst_number"]), \
            f"Malformed GST for {c['customer_name']}: {c['gst_number']!r}"

    # WhatsApp — Busy 21 stores 91-prefixed E.164; verify at least one.
    with_whatsapp = [c for c in customers if c["whatsapp_number"]]
    assert with_whatsapp, "No customers have WhatsApp — WhatsAppNo not joined"
    for c in with_whatsapp:
        wa = c["whatsapp_number"]
        assert wa.startswith("91") and len(wa) == 12, \
            f"WhatsApp not in E.164 for {c['customer_name']}: {wa!r}"

    # SHITLA AUTO SPARES (code 6003) — the party whose closing balance we
    # hand-verified via mdb-tools = ₹1,34,633 at Folio1.D22.
    shitla = next((c for c in customers
                   if c["customer_id"] == "6003"), None)
    if shitla:                # tolerate if user provides a different DB later
        assert shitla["closing_balance"] == pytest.approx(134633.0), \
            f"D22 closing balance mismatch: got {shitla['closing_balance']}"
        assert shitla["gst_number"] == "22ACOFS7545J1ZN"
        assert shitla["pan_number"] == "ACOFS7545J"
        assert shitla["whatsapp_number"] == "919820074085"
        assert shitla["mobile_number"] == "9300029026"
        assert shitla["email_id"] == "shitlaauto26@gmail.com"


@pytest.mark.skipif(
    not (REAL_DB_ROOT / "db12025.bds").exists(),
    reason="Real Busy 21 sample DB not present"
)
def test_access_parser_opens_licensed_busy_without_password():
    """Direct read of the reader class — confirms zero-password works."""
    from flowra_busy_agent import BusyDBReader
    r = BusyDBReader(str(REAL_DB_ROOT / "db12025.bds"))
    try:
        rows = list(r.iter_rows("Master1"))
        assert len(rows) == 11832, \
            f"Expected 11,832 Master1 rows in licensed Busy 21 sample, got {len(rows)}"
        assert r._connection_method == "AccessParser"
    finally:
        r.close()


@pytest.mark.skipif(
    not (REAL_DB_ROOT / "db12025.bds").exists(),
    reason="Real Busy 21 sample DB not present"
)
def test_masteraddressinfo_read_from_real_db():
    """Prove MasterAddressInfo is readable and contact fields survive
    the access_parser → row-dict conversion untouched."""
    from flowra_busy_agent import BusyDBReader
    r = BusyDBReader(str(REAL_DB_ROOT / "db12025.bds"))
    try:
        # Find the row for party 6003 (SHITLA AUTO SPARES)
        for row in r.iter_rows("MasterAddressInfo"):
            if str(row.get("MasterCode") or "") == "6003":
                assert row["Mobile"] == "9300029026"
                assert row["Email"] == "shitlaauto26@gmail.com"
                assert row["GSTNo"] == "22ACOFS7545J1ZN"
                assert row["ITPAN"] == "ACOFS7545J"
                assert row["WhatsAppNo"] == "919820074085"
                assert row["Contact"] == "SUDHIR"
                return
        pytest.fail("Party 6003 not found in MasterAddressInfo")
    finally:
        r.close()
