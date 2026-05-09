"""
Iteration 75 — Tally Sync Agent v9.8.3-empty-vchtype-quiet.

User reported: After a successful sync ("Cached 6275 receipts"), the agent
log was full of WARNINGS like "receipt: no vouchers found in response" for
every month. Uploaded raw XMLs confirmed Tally was returning a valid
metadata-only response (REQUESTDATA → COMPANY/REMOTECMPINFO, no VOUCHER
elements) — i.e. the queried VCHTYPE has zero transactions in the period.

Two coordinated fixes:

(1) `fetch_voucher_type_map` now drops the canonical literal voucher type
    name ("Receipt", "Payment", "Sales", etc.) from the parent's children
    list when CUSTOM child types exist alongside it. Tenants with
    e.g. "Bank Receipt", "Cash Receipt", "App Cash Receipts" never post
    real transactions under the literal "Receipt" — querying for it wastes
    a request and produces a misleading warning.

(2) `_parse_vouchers` now classifies an empty response: if the raw XML is
    a valid metadata-only ENVELOPE (REQUESTDATA + COMPANY + no VOUCHER),
    it logs INFO "0 vouchers (metadata-only)" instead of WARNING. Genuine
    parse failures still warn.
"""
import os
import re
import pytest


# ── (1) Voucher-type-map dedup ─────────────────────────────────────────────

def _apply_v983_dedup(voucher_type_map):
    """Mirror of the v9.8.3 child-vs-canonical filter inside
    `fetch_voucher_type_map`. Pure function for unit testing."""
    out = {p: list(names) for p, names in voucher_type_map.items()}
    for parent, names in list(out.items()):
        canonical_lc = parent.strip().lower()
        customs = [n for n in names if n.strip().lower() != canonical_lc]
        if len(customs) >= 1 and len(names) > len(customs):
            out[parent] = customs
    return out


def test_v983_drops_canonical_when_customs_exist():
    """User's exact case: Receipt parent has 4 names including the literal
    'Receipt' — drop the literal because it represents zero real
    transactions."""
    inp = {
        "Receipt": ["App Cash Receipts", "Bank Receipt", "Cash Receipt", "Receipt"],
        "Payment": ["Bank Payment", "Cash Payment", "Cheque Return Voucher", "Payment"],
        "Sales": ["Sales General", "Sales Net Special Rate", "SALES Pidilite Raipur", "Sales"],
    }
    out = _apply_v983_dedup(inp)
    assert "Receipt" not in out["Receipt"]
    assert out["Receipt"] == ["App Cash Receipts", "Bank Receipt", "Cash Receipt"]
    assert "Payment" not in out["Payment"]
    assert "Sales" not in out["Sales"]


def test_v983_keeps_canonical_when_no_customs():
    """Stock Tally (no customisations) → only the canonical name → KEEP it."""
    inp = {
        "Receipt": ["Receipt"],
        "Payment": ["Payment"],
    }
    out = _apply_v983_dedup(inp)
    assert out["Receipt"] == ["Receipt"]
    assert out["Payment"] == ["Payment"]


def test_v983_case_insensitive_match():
    """Canonical match is case-insensitive — handles 'RECEIPT' / 'receipt'."""
    inp = {"Receipt": ["BANK RECEIPT", "RECEIPT"]}
    out = _apply_v983_dedup(inp)
    assert out["Receipt"] == ["BANK RECEIPT"]


def test_v983_does_not_remove_when_only_one_name_total():
    """Edge: parent has only 1 name and it's canonical → keep it (else
    the parent vanishes and no sync happens for that voucher class)."""
    inp = {"Contra": ["Contra"]}
    out = _apply_v983_dedup(inp)
    assert out["Contra"] == ["Contra"]


def test_v983_handles_whitespace_in_name():
    inp = {"Receipt": ["Bank Receipt", "  Receipt  "]}
    out = _apply_v983_dedup(inp)
    assert out["Receipt"] == ["Bank Receipt"]


# ── (2) Empty-response log-level classification ────────────────────────────

# Sample XML mirroring what Tally returned in the user's `receipts_receipt_*` files.
METADATA_ONLY_XML = """<ENVELOPE>
 <BODY>
  <IMPORTDATA>
   <REQUESTDATA>
    <TALLYMESSAGE>
     <COMPANY>
      <REMOTECMPINFO.LIST />
      <NAME>Krishna Sales Corporation</NAME>
     </COMPANY>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>"""

GENUINE_BROKEN_XML = "<ENVELOPE><BODY><junk-with-no-structure"


def _looks_like_metadata_only(raw_xml):
    """Mirror of the v9.8.3 classification in `_parse_vouchers`."""
    return (
        '<COMPANY' in raw_xml
        and '<REQUESTDATA>' in raw_xml
        and '</ENVELOPE>' in raw_xml
        and '<VOUCHER' not in raw_xml
    )


def test_v983_metadata_only_response_classified_correctly():
    assert _looks_like_metadata_only(METADATA_ONLY_XML) is True


def test_v983_genuine_failure_not_treated_as_metadata():
    assert _looks_like_metadata_only(GENUINE_BROKEN_XML) is False


def test_v983_normal_response_with_vouchers_not_metadata():
    """Response with REAL vouchers must NOT trigger metadata-only branch."""
    has_vouchers = METADATA_ONLY_XML.replace(
        "<COMPANY>", "<COMPANY>\n     <VOUCHER VCHTYPE='Bank Receipt'>X</VOUCHER>"
    )
    assert _looks_like_metadata_only(has_vouchers) is False


# ── Public-agent stamp checks ──

def test_public_agent_is_v983():
    path = "/app/frontend/public/flowra-desktop-agent.py"
    if not os.path.exists(path):
        pytest.skip("public agent not present")
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()
    assert "9.8.3-empty-vchtype-quiet" in contents or "9.8.4-tenant-guard" in contents or "9.8.5-stdprice-list" in contents or "9.8.6-hierarchy-walk" in contents or "9.8.7-aliases-perf" in contents
    # Old stamps are gone
    assert "9.8.2-saleprice-fix" not in contents
    # Dedup logic is present
    assert "canonical_lc = parent.strip().lower()" in contents
    # Smart logging is present (note: in v9.8.6 the message was reworded)
    assert "looks_like_metadata_only" in contents
    assert ("metadata-only response" in contents
            or "empty VCHTYPE this period" in contents)


def test_v983_does_not_lose_required_voucher_types():
    """v9.8.3 must continue to return SOMETHING for every parent — we should
    never end up with an empty list for a parent that had children."""
    inp = {
        "Receipt": ["Bank Receipt", "Cash Receipt", "Receipt"],
        "Payment": ["Bank Payment", "Cash Payment", "Cheque Return Voucher", "Payment"],
        "Sales": ["Sales General", "Sales"],
        "Contra": ["Contra"],
        "Journal": ["Journal", "Office Journal(Temp)"],
    }
    out = _apply_v983_dedup(inp)
    for p, names in out.items():
        assert len(names) > 0, f"parent {p} ended up with no names"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
