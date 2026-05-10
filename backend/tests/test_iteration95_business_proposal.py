"""Iteration 95 — Business Proposal doc completeness.

Asserts:
  - Markdown source has all 16 sections
  - PDF builds, ≥60 KB, valid header
  - PPTX builds, has 16 slides, valid OOXML
  - Renderer script is reproducible (idempotent re-run)
"""
import os
import subprocess
import zipfile

DOCS = "/app/docs"
MD = f"{DOCS}/FLOWRA_BUSINESS_PROPOSAL.md"
PDF = f"{DOCS}/FLOWRA_BUSINESS_PROPOSAL.pdf"
PPTX = f"{DOCS}/FLOWRA_BUSINESS_PROPOSAL.pptx"
SCRIPT = f"{DOCS}/_render_business_proposal.py"

REQUIRED_SECTIONS = [
    "1 · Executive Summary",
    "2 · The Problem",
    "3 · The Product",
    "4 · Target Market",
    "5 · Competitive Landscape",
    "6 · Business Model",
    "7 · Go-to-Market Strategy",
    "8 · Manpower & Org Plan",
    "9 · Technical Scalability",
    "10 · Financial Projections",
    "11 · Two-Year Plan",
    "12 · Risks & Mitigations",
    "13 · Why Now",
    "14 · Why Us",
    "15 · The Ask",
    "16 · Closing",
]


def test_md_has_all_sections():
    src = open(MD, encoding="utf-8").read()
    for s in REQUIRED_SECTIONS:
        assert s in src, f"Markdown missing section: {s!r}"
    # Substantive doc
    assert len(src) > 17000, "Proposal markdown is too short"


def test_pdf_built_and_valid():
    assert os.path.exists(PDF), f"PDF not built: {PDF}"
    assert os.path.getsize(PDF) > 60 * 1024, "PDF suspiciously small"
    with open(PDF, "rb") as fh:
        assert fh.read(5) == b"%PDF-"


def test_pptx_built_and_has_16_slides():
    """PPTX is OOXML (zip). Count slide XML files."""
    assert os.path.exists(PPTX), f"PPTX not built: {PPTX}"
    assert os.path.getsize(PPTX) > 30 * 1024, "PPTX suspiciously small"
    with zipfile.ZipFile(PPTX) as z:
        slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide")
                  and n.endswith(".xml")]
        assert len(slides) == 16, f"Expected 16 slides, got {len(slides)}"


def test_renderer_is_reproducible():
    result = subprocess.run(["python3", SCRIPT],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (
        f"Renderer failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "Wrote" in result.stdout
    # Both files must still exist & be valid after re-run
    with open(PDF, "rb") as fh:
        assert fh.read(5) == b"%PDF-"
    with zipfile.ZipFile(PPTX) as z:
        assert any("ppt/presentation.xml" == n for n in z.namelist())


def test_pptx_contains_key_phrases():
    """Sanity: all 16 slide XMLs collectively must reference the headline numbers
    and themes investors expect to see."""
    with zipfile.ZipFile(PPTX) as z:
        joined = "\n".join(
            z.read(n).decode("utf-8", errors="ignore")
            for n in z.namelist() if n.startswith("ppt/slides/slide")
        )
    for must in [
        "FLOWRA",
        "₹4 Cr",                    # the ask
        "₹2,499",                   # ARPU / Professional plan
        "2,500",                    # M24 tenants
        "11.5",                     # addressable lakhs
        "78%",                      # gross margin
        "Tally",
    ]:
        assert must in joined, f"PPTX missing key phrase: {must!r}"
