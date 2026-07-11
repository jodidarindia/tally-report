"""Iteration 119 · What's New — single source of truth.

Locks in that both the User Admin Dashboard's What's New panel AND the
FLOWRA_Whats_New.pdf are wired to `/app/frontend/public/whats_new.json`.

If a future refactor accidentally hardcodes one surface again, this test
breaks at the seam — not in front of investors reading a stale PDF while
customers see fresh entries on their dashboard.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "frontend" / "public" / "whats_new.json"
DASHBOARD_JS = ROOT / "frontend" / "src" / "pages" / "Dashboard.js"
PDF_SCRIPT = ROOT / "scripts" / "generate_whats_new_pdf.py"
PDF_OUT = ROOT / "frontend" / "public" / "FLOWRA_Whats_New.pdf"


def _load():
    with open(JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_source_json_exists_and_has_required_shape():
    d = _load()
    assert "updated_at" in d
    assert "entries" in d
    assert isinstance(d["entries"], list) and len(d["entries"]) > 0
    for i, e in enumerate(d["entries"]):
        for key in ("date", "tag", "title", "desc"):
            assert key in e, f"entry #{i} missing '{key}': {e!r}"
        assert e["tag"] in ("NEW", "FIX", "IMPROVE"), (
            f"entry #{i} has unknown tag {e['tag']!r}"
        )


def test_entries_are_sorted_newest_first():
    d = _load()
    dates = [e["date"] for e in d["entries"]]
    assert dates == sorted(dates, reverse=True), (
        "entries must be newest-first — dashboard shows them in JSON order"
    )


def test_latest_entry_is_the_most_recent_iteration():
    d = _load()
    latest = d["entries"][0]
    assert latest["date"] >= "2026-07-11", (
        f"latest entry {latest['date']} is older than expected — bump it "
        "in whats_new.json before shipping a new iteration"
    )


def test_dashboard_no_longer_hardcodes_the_list():
    """Dashboard.js must fetch /whats_new.json — no inline array of 20+ items."""
    src = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "fetch('/whats_new.json'" in src or 'fetch("/whats_new.json"' in src, (
        "Dashboard.js must fetch /whats_new.json (single source of truth)"
    )
    # Belt & braces — the old inline mega-array must be gone.
    assert "'2026-07-11', tag: 'FIX'" not in src, (
        "Legacy inline array leaked back — the JSON is now the only source"
    )


def test_pdf_generator_reads_from_json_not_hardcoded():
    src = PDF_SCRIPT.read_text(encoding="utf-8")
    assert "whats_new.json" in src, (
        "PDF generator must read from whats_new.json, not the removed UPDATES list"
    )
    # The old module-level UPDATES tuple must be gone.
    assert "UPDATES = [" not in src, (
        "generate_whats_new_pdf.py still has the legacy UPDATES = [...] "
        "constant — the whole point is to read from JSON now"
    )


def test_regenerating_pdf_produces_output_matching_json_size():
    """Sanity — regenerate the PDF and confirm it opens + is nontrivial."""
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, str(PDF_SCRIPT)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, f"PDF regen failed:\n{r.stdout}\n{r.stderr}"
    assert PDF_OUT.exists()
    assert PDF_OUT.stat().st_size > 30_000, "PDF suspiciously small"

    d = _load()
    # The stdout should mention the same entry count as the JSON
    assert f"{len(d['entries'])} entries" in r.stdout, r.stdout
