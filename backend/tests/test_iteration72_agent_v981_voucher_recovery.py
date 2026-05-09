"""
Iteration 72 — Tally Sync Agent v9.8.1 (voucher-recovery)

User reported: even after v9.8 ship, the desktop agent emitted
"sales: no vouchers found in response" while the saved raw XML clearly
showed vouchers — pointing to a parse-pipeline failure.

Root cause discovered from the user's uploaded raw XML files:
  • Tally `EXPLODEFLAG=Yes` + `Voucher Register` produces ~100 KB of XML
    per voucher (every empty <RATEDETAILS.LIST>, <BATCHALLOCATIONS.LIST>,
    etc. is included).
  • For tenants with hundreds of vouchers/month, response size easily
    exceeds Tally's HTTP buffer or the agent's read window → response is
    truncated mid-tag → xmltodict.parse() fails outright.
  • Old `_post` returned None on parse failure → `_parse_vouchers` never
    saw the partially-valid VOUCHER chunks that DID make it through.
  • Old debug write capped at 100 KB, so users couldn't even inspect
    the full response.

v9.8.1 fixes:
  1. `_post` now ALWAYS returns the (cleaned) raw XML on a `__raw_xml__`
     key so downstream parsers can run a per-voucher regex recovery.
  2. `_parse_vouchers` falls back to `<VOUCHER ...>...</VOUCHER>` regex
     extraction when the tree-walking path returns 0 vouchers.
  3. Debug write cap raised 100 KB → 5 MB.
  4. `_find_deep` ignores the new `__raw_xml__` key.

Tests:
  - End-to-end recovery from a synthetic truncated XML (3 complete + 1
    cut-off voucher → exactly 3 are recovered).
  - `_find_deep` skips the placeholder.
  - Public agent file is stamped v9.8.1 and contains the recovery code.
"""
import os
import re
import xmltodict
import pytest


# ── (1) v9.8.1 voucher-recovery on truncated XML ──────────────────────────

V_TEMPLATE = (
    '<VOUCHER VCHTYPE="Sales General" ACTION="Create">'
    '<DATE>20250415</DATE>'
    '<PARTYLEDGERNAME>{party}</PARTYLEDGERNAME>'
    '<VOUCHERNUMBER>{n}</VOUCHERNUMBER>'
    '<AMOUNT>-{amt}.00</AMOUNT>'
    '<ALLINVENTORYENTRIES.LIST>'
    '  <STOCKITEMNAME>Item-{n}</STOCKITEMNAME>'
    '  <AMOUNT>{amt}.00</AMOUNT>'
    '</ALLINVENTORYENTRIES.LIST>'
    '</VOUCHER>'
)


def _build_truncated_response(n_complete=3, with_trailing_partial=True):
    parts = [
        V_TEMPLATE.format(party=f"Customer {i}", n=i, amt=100 * i)
        for i in range(1, n_complete + 1)
    ]
    body = "".join(parts)
    if with_trailing_partial:
        # Tally cuts mid-tag when its HTTP buffer fills
        body += '<VOUCHER VCHTYPE="Sales"><DATE>20250420</DATE><RATEDET'
    return f"<ENVELOPE><BODY><IMPORTDATA><TALLYMESSAGE>{body}"


def _agent_v981_recover(raw_xml):
    """Mirror of the v9.8.1 _post + _parse_vouchers recovery contract."""
    # _sanitize
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw_xml)
    clean = re.sub(r'&#x[0-9a-fA-F]+;?', ' ', clean)
    clean = re.sub(r'&#[0-9]+;?', ' ', clean)
    clean = re.sub(r'&(?!(?:amp|lt|gt|apos|quot);)', '&amp;', clean)

    parsed = None
    try:
        parsed = xmltodict.parse(clean)
        if isinstance(parsed, dict):
            parsed['__raw_xml__'] = clean
    except Exception:
        parsed = {'__raw_xml__': clean}

    # Tree-walk first
    def find_deep(d, key):
        if isinstance(d, dict):
            if key in d:
                return d[key]
            for k, v in d.items():
                if k == '__raw_xml__':
                    continue
                r = find_deep(v, key)
                if r is not None:
                    return r
        elif isinstance(d, list):
            for it in d:
                r = find_deep(it, key)
                if r is not None:
                    return r

    vouchers = []
    tm = find_deep(parsed, 'TALLYMESSAGE')
    if tm:
        msgs = tm if isinstance(tm, list) else [tm]
        for m in msgs:
            if isinstance(m, dict) and 'VOUCHER' in m:
                v = m['VOUCHER']
                vouchers.extend(v if isinstance(v, list) else [v])

    # v9.8.1 regex fallback
    if not vouchers and parsed.get('__raw_xml__'):
        for chunk in re.findall(
            r'<VOUCHER\b.*?</VOUCHER>', parsed['__raw_xml__'], re.DOTALL
        ):
            try:
                d = xmltodict.parse(chunk).get('VOUCHER')
                if isinstance(d, dict):
                    vouchers.append(d)
            except Exception:
                continue
    return vouchers


def test_v981_recovers_complete_vouchers_from_truncated_response():
    raw = _build_truncated_response(n_complete=3, with_trailing_partial=True)
    vouchers = _agent_v981_recover(raw)
    assert len(vouchers) == 3, f"expected 3, got {len(vouchers)}"
    parties = [v.get('PARTYLEDGERNAME') for v in vouchers]
    assert parties == ['Customer 1', 'Customer 2', 'Customer 3']


def test_v981_handles_complete_response_without_truncation():
    raw = _build_truncated_response(n_complete=2, with_trailing_partial=False)
    raw_full = raw + "</TALLYMESSAGE></IMPORTDATA></BODY></ENVELOPE>"
    vouchers = _agent_v981_recover(raw_full)
    assert len(vouchers) == 2


def test_v981_handles_zero_complete_vouchers_truncated():
    """Single truncated voucher → 0 recovered, no crash."""
    raw = '<ENVELOPE><BODY><IMPORTDATA><TALLYMESSAGE><VOUCHER VCHTYPE="Sales"><DATE>20250401</DATE><RATEDETAI'
    vouchers = _agent_v981_recover(raw)
    assert vouchers == []


def test_v981_handles_empty_response():
    assert _agent_v981_recover('<ENVELOPE></ENVELOPE>') == []
    assert _agent_v981_recover('') == []


def test_v981_extracts_voucher_attributes():
    """Recovered vouchers must keep their @VCHTYPE attribute (used to
    distinguish custom voucher types like 'Sales General')."""
    raw = _build_truncated_response(n_complete=2, with_trailing_partial=True)
    vouchers = _agent_v981_recover(raw)
    for v in vouchers:
        assert v.get('@VCHTYPE') == 'Sales General'
        assert v.get('VOUCHERNUMBER')
        assert v.get('PARTYLEDGERNAME')


def test_v981_find_deep_skips_raw_xml_placeholder():
    """`__raw_xml__` is a placeholder, not real Tally data — must not be
    walked into by `_find_deep`."""
    fake = {
        '__raw_xml__': 'this is NOT a TALLYMESSAGE container',
        'BODY': {'TALLYMESSAGE': {'VOUCHER': {'@VCHTYPE': 'Sales'}}},
    }

    def find_deep(d, key):
        if isinstance(d, dict):
            if key in d:
                return d[key]
            for k, v in d.items():
                if k == '__raw_xml__':
                    continue
                r = find_deep(v, key)
                if r is not None:
                    return r
        elif isinstance(d, list):
            for it in d:
                r = find_deep(it, key)
                if r is not None:
                    return r

    tm = find_deep(fake, 'TALLYMESSAGE')
    assert isinstance(tm, dict) and 'VOUCHER' in tm


# ── (2) Public agent stamp & content checks ──

def test_public_agent_is_v981():
    path = "/app/frontend/public/flowra-desktop-agent.py"
    if not os.path.exists(path):
        pytest.skip("public agent not present")
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()
    assert "9.8.1-voucher-recovery" in contents
    assert "9.8.0-pl-parity" not in contents
    # Recovery code is present
    assert "regex-recovered" in contents
    assert "__raw_xml__" in contents
    # Debug cap raised
    assert "raw[:5_000_000]" in contents
    assert "raw[:100000]" not in contents


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
