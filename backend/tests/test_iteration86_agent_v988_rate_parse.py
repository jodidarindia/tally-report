"""Iteration 86 — v9.8.8 _num() rate-per-unit parser fix.

Bug: Tally exports rate-typed XML values as "<amount>/<unit>"
     (e.g., "1495.00/Nos", "3646.00/Pcs"). The pre-v9.8.8 parser called
     `float("1495.00/Nos")` directly, which raises ValueError → returned
     0. Result: every Indian Tally user with "Standard Selling Rate"
     configured saw standard_price = 0 for ALL items.

Fix: Strip everything from the first '/' before float()-parsing.

This module re-implements `_num()` and `_signed_num()` locally so we can
test them without booting the full agent (which requires PyWin32).
"""
import re


# Mirror of the v9.8.8 _num() implementation in
# /app/desktop-agent/tally_sync_agent_v9.py
def _num(val):
    if val is None:
        return 0.0
    if isinstance(val, dict):
        val = val.get('#text', val.get('$', '0'))
    s = str(val).replace(',', '').strip()
    if not s or s in ('None', 'null'):
        return 0.0
    if '/' in s:
        s = s.split('/', 1)[0].strip()
    try:
        return abs(float(s.split()[0]))
    except Exception:
        return 0.0


def _signed_num(val):
    if val is None:
        return 0.0
    if isinstance(val, dict):
        val = val.get('#text', val.get('$', '0'))
    s = str(val).replace(',', '').strip()
    if not s or s in ('None', 'null'):
        return 0.0
    if '/' in s:
        s = s.split('/', 1)[0].strip()
    try:
        return float(s.split()[0])
    except Exception:
        return 0.0


# ── _num — rate-per-unit parsing (the v9.8.8 fix) ───────────────────────
def test_num_strips_unit_suffix():
    assert _num("1495.00/Nos") == 1495.0
    assert _num("3646.00/Pcs") == 3646.0
    assert _num("52788.00/Ltr") == 52788.0


def test_num_handles_xmltodict_dict_with_rate_string():
    # xmltodict surfaces <STANDARDPRICE TYPE="Rate">1495.00/Nos</STANDARDPRICE>
    # as {'@TYPE': 'Rate', '#text': '1495.00/Nos'}
    assert _num({'@TYPE': 'Rate', '#text': '1495.00/Nos'}) == 1495.0


def test_num_clean_numbers_unaffected():
    assert _num("38") == 38.0
    assert _num(" 38 ") == 38.0
    assert _num("1234.56") == 1234.56
    assert _num("1,23,456") == 123456.0  # Indian comma format
    assert _num(0) == 0.0


def test_num_empty_or_none():
    assert _num("") == 0.0
    assert _num(None) == 0.0
    assert _num("None") == 0.0
    assert _num("null") == 0.0


def test_num_quantity_with_unit_label():
    # OPENINGBALANCE format: " 30 Nos =  371.00 Lt." → split()[0] = "30"
    assert _num(" 30 Nos =  371.00 Lt.") == 30.0


def test_num_negative_becomes_positive():
    # _num returns abs() — used for stock quantities & rates which are
    # always non-negative magnitudes
    assert _num("-100") == 100.0
    assert _num("-1495.00/Nos") == 1495.0


# ── _signed_num — preserves sign (used for ledger DR/CR) ─────────────────
def test_signed_num_preserves_negative():
    assert _signed_num("-1234.56") == -1234.56
    assert _signed_num("1234.56") == 1234.56


def test_signed_num_strips_unit_suffix():
    # Defensive — if any signed amount ever has a unit suffix
    assert _signed_num("-1495.00/Nos") == -1495.0


# ── End-to-end XML parse (proves the bug is gone for the user's data) ────
def test_user_xml_extraction_works():
    """Sanity check using a fixture mirroring the ASA AUTOTECH stock_items_raw.xml"""
    import xmltodict
    sample = """<ENVELOPE><BODY><DATA><COLLECTION>
    <STOCKITEM NAME="AXLE 85W140 GL5 12Ltr Bucket">
      <PARENT TYPE="String">Gear Oils All</PARENT>
      <BASEUNITS TYPE="String">Nos</BASEUNITS>
      <STANDARDPRICE TYPE="Rate">3646.00/Nos</STANDARDPRICE>
      <CLBAL TYPE="Number"> 38</CLBAL>
      <STANDARDPRICELIST.LIST>
        <DATE>20240401</DATE>
        <RATE>2963.00/Nos</RATE>
      </STANDARDPRICELIST.LIST>
      <STANDARDPRICELIST.LIST>
        <DATE>20260401</DATE>
        <RATE>3646.00/Nos</RATE>
      </STANDARDPRICELIST.LIST>
    </STOCKITEM>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    parsed = xmltodict.parse(sample)
    si = parsed['ENVELOPE']['BODY']['DATA']['COLLECTION']['STOCKITEM']
    # Direct STANDARDPRICE
    assert _num(si.get('STANDARDPRICE')) == 3646.0
    # STANDARDPRICELIST.LIST — list of dicts
    spl = si.get('STANDARDPRICELIST.LIST')
    assert isinstance(spl, list)
    today = '20260510'
    applicable = [e for e in spl if str(e.get('DATE', '0')) <= today]
    applicable.sort(key=lambda e: str(e.get('DATE', '0')), reverse=True)
    assert _num(applicable[0]['RATE']) == 3646.0  # most recent applicable
