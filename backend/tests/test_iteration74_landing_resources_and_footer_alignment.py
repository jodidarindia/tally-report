"""
Iteration 74 — Two small UX cleanups:

(1) Landing page Resources menu — REMOVE "Coming Soon" and "What's New"
    links. Now only Forms (Needs Assessment, Customer Questionnaire) and
    Documents (Product Presentation, Deployment Guide).

(2) Useradmin / login footer disclaimer aligned with landing page —
    "JODIDAR INDIA. All rights reserved. FLOWRA is a brand owned by
    JODIDAR INDIA." + the full Tally*/Busy* trademark notice.
"""
import os
import re


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def test_landing_resources_menu_no_coming_soon_or_whats_new():
    src = _read("/app/frontend/src/pages/LandingPage.js")
    # Both PDFs / labels must be gone
    forbidden = (
        "FLOWRA_Whats_New.pdf",
        "FLOWRA_Coming_Soon.pdf",
        '"resources-whats-new"',
        '"resources-coming-soon"',
        ">What's New (Latest Features)<",
        ">Coming Soon<",
    )
    for needle in forbidden:
        assert needle not in src, f"{needle!r} should be removed from LandingPage.js"

    # The remaining resources stay (path variation tolerated)
    expected = (
        "Customer_Questionnaire.pdf",
        "FLOWRA_Deployment_Guide.pdf",
        "Needs Assessment",
    )
    for kept in expected:
        assert kept in src, f"{kept!r} unexpectedly missing"


def test_useradmin_footer_matches_landing_in_app_js():
    src = _read("/app/frontend/src/App.js")
    # Brand line
    assert "JODIDAR INDIA. All rights reserved" in src
    assert "FLOWRA is a brand owned by JODIDAR INDIA" in src
    # Full disclaimer (Tally* AND Busy*)
    assert "Tally* and Busy* are trademarks" in src
    # Old short copy is gone
    assert "FLOWRA by Jodidar India" not in src
    # data-testid for testing/observability
    assert 'data-testid="tally-disclaimer"' in src


def test_super_admin_layout_footer_matches_landing():
    src = _read("/app/frontend/src/components/SuperAdminLayout.js")
    assert "JODIDAR INDIA. All rights reserved" in src
    assert "FLOWRA is a brand owned by JODIDAR INDIA" in src
    assert "Tally* and Busy* are trademarks" in src
    assert 'data-testid="tally-disclaimer"' in src


def test_login_page_footer_matches_landing():
    src = _read("/app/frontend/src/components/LoginPage.js")
    assert "JODIDAR INDIA" in src
    assert "FLOWRA is a brand owned by JODIDAR INDIA" in src
    assert "Tally* and Busy* are trademarks" in src
    assert "FLOWRA by Jodidar India" not in src


def test_only_one_canonical_disclaimer_template():
    """Sanity: each useradmin footer must use the same disclaimer phrasing
    so future copy changes only need a single update path."""
    files = [
        "/app/frontend/src/App.js",
        "/app/frontend/src/components/SuperAdminLayout.js",
        "/app/frontend/src/components/LoginPage.js",
        "/app/frontend/src/pages/LandingPage.js",
    ]
    canonical_phrase = "Tally* and Busy* are trademarks of their respective owners"
    misses = [f for f in files if canonical_phrase not in _read(f)]
    assert not misses, f"these files don't carry the canonical disclaimer: {misses}"


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
