"""Iteration 107 (revised in iter-109 / v9.8.28) — SVCURRENTCOMPANY
minimal-escape contract.

History:
  iter-107 (v9.8.27): aggressive HTML/XML escape of company name —
    parens → `&#40;`/`&#41;`, apostrophe → `&apos;`, double-quote →
    `&quot;`, plus the mandatory `&`/`<`/`>`. This was a misdiagnosis.

  Field report from Krishna Sales Corporation (v9.8.27 in production):
    Tally Prime 7.0 rejected `Krishna Sales Corporation &#40;from
    1-Apr-24&#41;` with `Could not set 'SVCurrentCompany' to
    'Krishna Sales Corporation (from 1-Apr-24)'`. Same raw name had
    worked in v9.8.25.

  iter-109 (v9.8.28) — this test: REVERT the iter-107 over-escape.
    Tally's TDL matching layer does NOT decode `&#40;`, `&apos;`,
    `&quot;` back to literal characters before matching the loaded-
    company catalog — so the escaped string never matches. We keep
    ONLY the three strictly XML-mandated escapes for element content:
    `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. These ARE decoded by
    Tally's XML parser, so the round-trip is lossless.

These tests pin the new contract.
"""
import os
import sys
import threading
import types

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "desktop-agent", "build-kit")
)
for missing in ("websockets", "watchdog", "ttkthemes"):
    sys.modules.setdefault(missing, types.ModuleType(missing))


@pytest.fixture(scope="module")
def Cls():
    mod = __import__("tally_sync_agent_v9")
    return mod.TallyCollectionClient


def _make(Cls, company_name):
    inst = Cls.__new__(Cls)
    inst.url = "http://127.0.0.1:9000"
    inst.timeout = 5
    inst.company = company_name
    inst._active_company = company_name
    inst.debug_dir = None
    inst._request_lock = threading.Lock()
    return inst


def test_krishna_sales_company_name_keeps_raw_parens(Cls):
    """v9.8.28 contract: parens MUST be sent RAW (Tally 7.0 rejects &#40;)."""
    inst = _make(Cls, "Krishna Sales Corporation (from 1-Apr-24)")
    tag = inst._company_tag()
    # Raw parens preserved — matches what v9.8.25 used to send.
    assert "(from 1-Apr-24)" in tag
    # Numeric character references MUST NOT appear (regression guard).
    assert "&#40;" not in tag
    assert "&#41;" not in tag
    assert tag == "<SVCURRENTCOMPANY>Krishna Sales Corporation (from 1-Apr-24)</SVCURRENTCOMPANY>"


def test_company_name_with_ampersand_is_xml_escaped(Cls):
    """Ampersand IS escaped — it's mandatory for XML well-formedness, and
    Tally's XML parser DOES decode `&amp;` back to `&` before matching."""
    inst = _make(Cls, "M/s. Patel & Sons")
    tag = inst._company_tag()
    assert "&amp;" in tag
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    # No bare ampersands (would break the XML envelope itself).
    import re
    bare_amps = re.findall(r"&(?!(?:amp|lt|gt);)", inner)
    assert bare_amps == []


def test_company_name_with_lt_gt_is_xml_escaped(Cls):
    """`<` and `>` MUST be escaped — Tally's XML parser would otherwise
    treat them as element delimiters and break the envelope."""
    inst = _make(Cls, "Acme <Trading> Co.")
    tag = inst._company_tag()
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    assert "&lt;Trading&gt;" in inner
    # Critically, raw <Trading> must not survive — that would break the XML envelope.
    assert "<Trading>" not in inner


def test_company_name_with_apostrophe_kept_raw(Cls):
    """Apostrophe is LEGAL inside XML element content (only attribute
    values need escaping). Tally 7.0 doesn't decode `&apos;`, so we
    leave it raw."""
    inst = _make(Cls, "O'Connor's Hardware")
    tag = inst._company_tag()
    assert "&apos;" not in tag
    assert "O'Connor's Hardware" in tag


def test_company_name_with_double_quote_kept_raw(Cls):
    """Same reasoning as apostrophe — legal in element content, not
    decoded by Tally's matching layer."""
    inst = _make(Cls, 'The "Best" Trading Co.')
    tag = inst._company_tag()
    assert "&quot;" not in tag
    assert 'The "Best" Trading Co.' in tag


def test_plain_company_name_unchanged(Cls):
    """Companies without special chars must round-trip identically."""
    inst = _make(Cls, "ASA Autotech India Private Limited")
    tag = inst._company_tag()
    assert tag == "<SVCURRENTCOMPANY>ASA Autotech India Private Limited</SVCURRENTCOMPANY>"


def test_default_company_still_returns_empty(Cls):
    """Don't break the existing 'use active company' fallback."""
    for c in ("", "default", "##default", "Default Company"):
        inst = _make(Cls, c)
        assert inst._company_tag() == ""


def test_xml_envelope_remains_wellformed_with_all_specials(Cls):
    """Sanity: the SVCURRENTCOMPANY element must parse as valid XML
    even for companies with `&`, `<`, `>` AND parens/quotes."""
    import xml.etree.ElementTree as ET
    inst = _make(Cls, "Patel & Sons <Pvt> Ltd. (from 1-Apr-24) \"Krishna's\"")
    tag = inst._company_tag()
    # Should be parseable as XML.
    root = ET.fromstring(tag)
    assert root.tag == "SVCURRENTCOMPANY"
    # Round-trip: text content matches the original.
    assert root.text == "Patel & Sons <Pvt> Ltd. (from 1-Apr-24) \"Krishna's\""


def test_only_one_svcurrentcompany_emitter_in_source(Cls):
    """Spot-check that `_company_tag` is the ONLY place that constructs
    `<SVCURRENTCOMPANY>` — so the escape policy is enforced everywhere."""
    import inspect
    mod = __import__("tally_sync_agent_v9")
    src = inspect.getsource(mod)
    import re
    code_only = re.sub(r"#.*", "", src)
    occurrences = code_only.count("<SVCURRENTCOMPANY>")
    assert occurrences <= 1, (
        f"Found {occurrences} raw <SVCURRENTCOMPANY> occurrences in code "
        "(comments stripped) — only _company_tag() should emit it."
    )
