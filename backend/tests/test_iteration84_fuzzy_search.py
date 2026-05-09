"""Iteration 84 — Fuzzy / normalized search across all search boxes.

Verifies:
  - build_fuzzy_regex / fuzzy_normalize / fuzzy_match helpers
  - All major separator chars are ignored on BOTH sides
  - End-to-end Mongo regex matches across item_name / part_number /
    customer_name with a wide variety of formats.
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils import build_fuzzy_regex, fuzzy_normalize, fuzzy_match  # noqa: E402


def _matches(pattern: str, text: str) -> bool:
    """Run the built regex (case-insensitive substring) against text."""
    if not pattern:
        return True
    return re.search(pattern, text, re.IGNORECASE) is not None


# ── fuzzy_normalize ──────────────────────────────────────────────────────
def test_normalize_strips_all_separators():
    assert fuzzy_normalize("TVS-10") == "tvs10"
    assert fuzzy_normalize("TVS / 10") == "tvs10"
    assert fuzzy_normalize("TVS(10)") == "tvs10"
    assert fuzzy_normalize("TVS!10") == "tvs10"
    assert fuzzy_normalize("TVS:10") == "tvs10"
    assert fuzzy_normalize("TVS.10") == "tvs10"
    assert fuzzy_normalize("TVS,10") == "tvs10"
    assert fuzzy_normalize("TVS&10") == "tvs10"
    assert fuzzy_normalize("TVS_10") == "tvs10"
    assert fuzzy_normalize("TVS'10") == "tvs10"
    assert fuzzy_normalize('TVS"10') == "tvs10"
    assert fuzzy_normalize("  TVS  10  ") == "tvs10"


def test_normalize_handles_none_and_empty():
    assert fuzzy_normalize("") == ""
    assert fuzzy_normalize(None) == ""


# ── fuzzy_match (Python-side) ────────────────────────────────────────────
def test_fuzzy_match_basic_variations():
    # User types "tvs 10" — should match all variations
    for stored in ["TVS-10", "TVS / 10", "TVS(10)", "TVS:10", "TVS.10",
                   "TVS,10", "TVS&10", "TVS_10", "TVS'10", 'TVS"10', "tvs10"]:
        assert fuzzy_match(stored, "tvs 10"), f"failed for {stored!r}"


def test_fuzzy_match_substring():
    assert fuzzy_match("STEELGRIP TVS-10 ROD", "tvs10")
    assert fuzzy_match("ABC & Co. (Pvt) Ltd.", "abccopvtltd")


def test_fuzzy_match_empty_needle_matches_all():
    assert fuzzy_match("anything", "")
    assert fuzzy_match("", "")


def test_fuzzy_match_negative():
    assert not fuzzy_match("STEELGRIP TVS-10", "honda")
    assert not fuzzy_match("ABC & Co.", "xyz")


# ── build_fuzzy_regex (Mongo-side) ───────────────────────────────────────
def test_build_regex_matches_separator_variants():
    pattern = build_fuzzy_regex("tvs 10")
    assert pattern  # non-empty
    for stored in ["TVS-10", "TVS / 10", "TVS(10)", "TVS!10", "TVS:10",
                   "TVS.10", "TVS,10", "TVS&10", "TVS_10", "TVS'10", 'TVS"10',
                   "tvs10", "PRODUCT TVS-10 ROD"]:
        assert _matches(pattern, stored), f"failed for {stored!r}"


def test_build_regex_special_chars_in_input_are_escaped():
    # Input with metacharacters should NOT explode regex compilation
    pattern = build_fuzzy_regex("a.b")  # "." is in ignore list, gets stripped
    assert pattern  # 'a' + sep + 'b'
    assert _matches(pattern, "ab")
    assert _matches(pattern, "a-b")
    assert _matches(pattern, "a.b")
    # Literal regex metacharacters that aren't in ignore list should be escaped
    p2 = build_fuzzy_regex("a+b")
    assert _matches(p2, "a+b")
    assert not _matches(p2, "ab")  # '+' is not in ignore list, must match literally


def test_build_regex_empty_input():
    assert build_fuzzy_regex("") == ""
    assert build_fuzzy_regex("   ") == ""
    assert build_fuzzy_regex("---") == ""  # all chars stripped → empty
    assert build_fuzzy_regex(None) == ""


def test_build_regex_realworld_customer_names():
    # User searches "abc co" — should match formal company names
    pattern = build_fuzzy_regex("abc co")
    assert _matches(pattern, "ABC & Co.")
    assert _matches(pattern, "ABC Co. (Pvt) Ltd.")
    assert _matches(pattern, "ABC-CO")
    assert _matches(pattern, "ABC/CO/HYDERABAD")


def test_build_regex_realworld_part_numbers():
    pattern = build_fuzzy_regex("p123 4")
    assert _matches(pattern, "P123-4")
    assert _matches(pattern, "P-123/4")
    assert _matches(pattern, "P.123_4")
    assert _matches(pattern, "P123(4)")
