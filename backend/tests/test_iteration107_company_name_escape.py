"""Iteration 107 — v9.8.27 escape company name in SVCURRENTCOMPANY.

Built directly from the real customer (Krishna Sales Corp) agent log:
every Tally call failed with:

  Tally error: Could not set 'SVCurrentCompany' to
    'Krishna Sales Corporation (from 1-Apr-24)'

…because the agent emitted the raw company name into the SVCURRENTCOMPANY
XML element. Tally's TDL parser treats raw `(`, `)`, `&`, `<`, `>` as
expression delimiters, so the company-switch fails and every subsequent
query returns 0 results — including the AlterID detection itself.

These tests pin the fix: company names containing each special character
must be HTML/XML-escaped before being embedded in the XML envelope.
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


def test_real_krishna_sales_company_name_is_escaped(Cls):
    """The exact failing name from the agent log."""
    inst = _make(Cls, "Krishna Sales Corporation (from 1-Apr-24)")
    tag = inst._company_tag()
    # Parens must be escaped to numeric entities.
    assert "&#40;" in tag
    assert "&#41;" in tag
    # The raw form (which Tally rejects) must NOT appear.
    assert "(from" not in tag
    assert "1-Apr-24)" not in tag
    # The textual content (with raw chars) must NOT survive untransformed
    # inside the SVCURRENTCOMPANY element.
    assert "(from 1-Apr-24)" not in tag
    # The encoded form should reproduce the original on the Tally side.
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    assert inner == "Krishna Sales Corporation &#40;from 1-Apr-24&#41;"


def test_company_name_with_ampersand_is_escaped(Cls):
    """Common pattern: 'M/s. Patel & Sons' — the bare & breaks XML."""
    inst = _make(Cls, "M/s. Patel & Sons")
    tag = inst._company_tag()
    assert "&amp;" in tag
    # No raw "&" outside of a complete entity reference.
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    # The only "&" left should be the leading "&" of "&amp;".
    import re
    bare_amps = re.findall(r"&(?!(?:amp|lt|gt|quot|apos|#\d+);)", inner)
    assert bare_amps == []


def test_company_name_with_lt_gt_is_escaped(Cls):
    inst = _make(Cls, "Acme <Trading> Co.")
    tag = inst._company_tag()
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    assert "&lt;Trading&gt;" in inner
    # Critically, raw <Trading> must not survive — that would break the XML envelope.
    assert "<Trading>" not in inner


def test_company_name_with_apostrophe_is_escaped(Cls):
    inst = _make(Cls, "O'Connor's Hardware")
    tag = inst._company_tag()
    assert "&apos;" in tag
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    assert "O&apos;Connor&apos;s" in inner


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


def test_escape_round_trip_unescape_recovers_original(Cls):
    """Sanity: the escaped value, when passed through an XML parser,
    decodes back to the original string. Mimics how Tally consumes it."""
    import xml.sax.saxutils as saxutils
    original = "Krishna Sales Corporation (from 1-Apr-24)"
    inst = _make(Cls, original)
    tag = inst._company_tag()
    inner = tag.replace("<SVCURRENTCOMPANY>", "").replace("</SVCURRENTCOMPANY>", "")
    decoded = saxutils.unescape(inner, {"&apos;": "'", "&quot;": '"', "&#40;": "(", "&#41;": ")"})
    assert decoded == original


def test_all_xml_tag_emitters_inherit_the_fix(Cls):
    """Spot-check that `_company_tag` is used in actual XML payload
    construction (not bypassed). We look for `_company_tag()` calls in
    the source so a regression that inlines the raw name is caught."""
    import inspect
    mod = __import__("tally_sync_agent_v9")
    src = inspect.getsource(mod)
    # Strip Python single-line comments before counting so a documentation
    # mention of `<SVCURRENTCOMPANY>` doesn't fail the test.
    import re
    code_only = re.sub(r"#.*", "", src)
    occurrences = code_only.count("<SVCURRENTCOMPANY>")
    # The helper has ONE literal (the return template). Anything more means
    # a bypass.
    assert occurrences <= 1, (
        f"Found {occurrences} raw <SVCURRENTCOMPANY> occurrences in code "
        "(comments stripped) — only the helper should embed it. Use "
        "_company_tag() everywhere else."
    )
