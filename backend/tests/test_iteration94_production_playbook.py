"""Iteration 94 — Production Playbook doc completeness.

Asserts:
  - /app/docs/PRODUCTION_PLAYBOOK.md exists with all 16 sections
  - /app/docs/PRODUCTION_PLAYBOOK.pdf is rendered, ≥80 KB
  - The renderer script is committable and runs cleanly
"""
import os
import re
import subprocess

DOCS = "/app/docs"
MD = f"{DOCS}/PRODUCTION_PLAYBOOK.md"
PDF = f"{DOCS}/PRODUCTION_PLAYBOOK.pdf"
SCRIPT = f"{DOCS}/_render_pdf.py"

REQUIRED_SECTIONS = [
    "1 · Executive Summary",
    "2 · Why This Matters",
    "3 · Environment Topology",
    "4 · Branching & Release Flow",
    "5 · Continuous Integration & Deployment",
    "6 · Observability",
    "7 · Database Operations",
    "8 · Tally Agent Updates",
    "9 · Production Runbook",
    "10 · Security & Compliance",
    "11 · Cost Breakdown",
    "12 · Phased Rollout",
    "13 · Decisions Matrix",
    "14 · Appendix A",
    "15 · Appendix B",
    "16 · Closing Note",
]


def test_md_exists_and_has_all_sections():
    assert os.path.exists(MD), f"Missing markdown source: {MD}"
    src = open(MD, encoding="utf-8").read()
    for s in REQUIRED_SECTIONS:
        assert s in src, f"Markdown is missing section: '{s}'"
    # Sanity: minimum content size — playbook should be substantive
    assert len(src) > 18000, "Playbook markdown is suspiciously short"


def test_pdf_exists_and_is_valid():
    assert os.path.exists(PDF), f"PDF was not built: {PDF}"
    assert os.path.getsize(PDF) > 80 * 1024, "PDF too small — render likely failed"
    # PDF magic header
    with open(PDF, "rb") as fh:
        header = fh.read(5)
    assert header == b"%PDF-", f"File is not a valid PDF (header: {header})"


def test_renderer_script_is_runnable():
    """Re-running the renderer should regenerate a valid PDF without errors."""
    assert os.path.exists(SCRIPT)
    result = subprocess.run(
        ["python3", SCRIPT], capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"Renderer script failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "Wrote" in result.stdout
    # Re-validate the freshly-rendered PDF
    with open(PDF, "rb") as fh:
        header = fh.read(5)
    assert header == b"%PDF-"


def test_md_avoids_environment_specific_secrets():
    """Quick guard so the doc itself doesn't accidentally contain credentials.
    Allows known placeholder/example strings."""
    src = open(MD, encoding="utf-8").read()
    # Real secret markers (NOT placeholders)
    danger_patterns = [
        r"AKIA[A-Z0-9]{16}",                # AWS access key
        r"-----BEGIN [A-Z]+ PRIVATE KEY-----",
        r"sk_live_[A-Za-z0-9]{16,}",        # Stripe live key
        r"AIza[0-9A-Za-z_-]{35}",            # Google API key
    ]
    for pat in danger_patterns:
        assert not re.search(pat, src), f"Possible secret leak matching: {pat}"


def test_recommended_table_of_contents_visible():
    """Ensure the markdown still uses numbered section headings so the
    rendered PDF table-of-contents-by-eye works."""
    src = open(MD, encoding="utf-8").read()
    # Each section uses `## N · ` pattern
    headings = re.findall(r"^## (\d+) · ", src, flags=re.MULTILINE)
    assert len(headings) >= 16, f"Expected ≥16 numbered sections, got {len(headings)}"
    # Sections should be sequential 1..N
    nums = [int(h) for h in headings]
    assert nums == sorted(nums), "Section numbers are out of order"
