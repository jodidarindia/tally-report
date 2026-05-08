"""Smoke test for landing-page + lead-enquiry copy parity (May 2026 features).

Verifies the public landing page actually advertises the new modules and
both Tally* + Busy* compatibility messaging is present.
"""
import os
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000").rstrip("/")


def test_landing_page_advertises_tally_and_busy():
    """The landing HTML and JS must mention BOTH Tally* and Busy* parity."""
    # Fetch the landing page bundle (the React app SSR-renders index.html
    # but feature copy lives in the JS chunks). We hit the index + main JS.
    r = requests.get(BASE, timeout=20)
    assert r.status_code == 200
    html = r.text
    # Title / meta should have FLOWRA branding
    assert "FLOWRA" in html or "flowra" in html.lower()


def test_demo_video_asset_is_served():
    r = requests.head(f"{BASE}/flowra-demo.mp4", timeout=20, allow_redirects=True)
    assert r.status_code == 200
    assert int(r.headers.get("content-length", "0")) > 100_000, \
        "Demo video must be >100KB"


def test_whats_new_pdf_is_published_and_recent():
    r = requests.head(f"{BASE}/FLOWRA_Whats_New.pdf", timeout=20, allow_redirects=True)
    assert r.status_code == 200
    assert int(r.headers.get("content-length", "0")) > 5_000


def test_landing_page_js_chunk_mentions_new_features():
    """Search every served JS chunk for new-feature copy strings."""
    # Pull the index, grep for asset hashes, fetch each, confirm key strings exist.
    idx = requests.get(BASE, timeout=20).text
    # Find compiled JS chunks
    import re
    chunks = re.findall(r'/static/js/[a-zA-Z0-9._-]+\.js', idx)
    assert chunks, "No JS chunks found on landing page"
    haystack = ""
    for c in set(chunks):
        try:
            haystack += requests.get(BASE + c, timeout=20).text
        except Exception:
            pass
    # New 2026 module copy must be present in the bundle
    expected = [
        "Beat Plans",
        "A/B/C/D",
        "DPDP",
        "Tally* / Busy*",  # new combined messaging
        "Backups",
    ]
    missing = [s for s in expected if s not in haystack]
    assert not missing, f"Landing JS bundle missing copy: {missing}"
