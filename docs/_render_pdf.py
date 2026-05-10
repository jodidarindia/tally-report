"""Render PRODUCTION_PLAYBOOK.md → PRODUCTION_PLAYBOOK.pdf.

Uses `markdown` to convert MD → HTML, then `weasyprint` to render HTML → PDF
with a stylesheet tailored for an A4 study document.
"""
import re
from pathlib import Path
import markdown
from weasyprint import HTML, CSS

DOCS = Path(__file__).resolve().parent
SRC = DOCS / "PRODUCTION_PLAYBOOK.md"
OUT = DOCS / "PRODUCTION_PLAYBOOK.pdf"

CSS_TEXT = """
@page {
  size: A4;
  margin: 22mm 18mm 22mm 18mm;
  @top-left {
    content: "FLOWRA — Production Operations Playbook";
    font-size: 9pt;
    color: #64748B;
    font-family: 'Inter', 'Segoe UI', sans-serif;
  }
  @top-right {
    content: "v1.0 · Feb 2026";
    font-size: 9pt;
    color: #64748B;
    font-family: 'Inter', 'Segoe UI', sans-serif;
  }
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-size: 9pt;
    color: #94A3B8;
    font-family: 'Inter', 'Segoe UI', sans-serif;
  }
  @bottom-left {
    content: "Confidential · Internal study only";
    font-size: 9pt;
    color: #94A3B8;
    font-family: 'Inter', 'Segoe UI', sans-serif;
  }
}

@page :first {
  margin: 0;
  @top-left  { content: none; }
  @top-right { content: none; }
  @bottom-right { content: none; }
  @bottom-left  { content: none; }
}

html, body {
  font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
  color: #1E293B;
}

/* Cover page */
.cover {
  page-break-after: always;
  height: 100vh;
  background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
  color: #FFFFFF;
  padding: 70mm 22mm 22mm 22mm;
  position: relative;
}
.cover .brand {
  font-size: 11pt;
  letter-spacing: 6pt;
  color: #93C5FD;
  margin-bottom: 24mm;
  text-transform: uppercase;
}
.cover h1 {
  font-size: 38pt;
  font-weight: 800;
  line-height: 1.1;
  margin: 0 0 12mm 0;
  color: #FFFFFF;
  border-bottom: none;
  padding: 0;
}
.cover .subtitle {
  font-size: 14pt;
  color: #CBD5E1;
  font-weight: 400;
  margin-bottom: 24mm;
  max-width: 130mm;
}
.cover .meta {
  position: absolute;
  bottom: 22mm;
  left: 22mm;
  right: 22mm;
  border-top: 1px solid #334155;
  padding-top: 10mm;
  display: flex;
  justify-content: space-between;
  font-size: 9.5pt;
  color: #94A3B8;
}
.cover .meta strong { color: #FFFFFF; font-weight: 600; }

/* Headings */
h1 {
  font-size: 22pt;
  font-weight: 700;
  color: #0F172A;
  margin: 14mm 0 4mm 0;
  padding-bottom: 3mm;
  border-bottom: 2px solid #2563EB;
  page-break-before: always;
  page-break-after: avoid;
}
h1:first-of-type { page-break-before: auto; }

h2 {
  font-size: 14pt;
  font-weight: 700;
  color: #1E293B;
  margin: 9mm 0 3mm 0;
  page-break-after: avoid;
}

h3 {
  font-size: 11.5pt;
  font-weight: 600;
  color: #2563EB;
  margin: 6mm 0 2mm 0;
  page-break-after: avoid;
}

h4 { font-size: 10.5pt; font-weight: 600; color: #475569; margin: 5mm 0 2mm 0; }

/* Body */
p { margin: 0 0 3mm 0; orphans: 3; widows: 3; }
strong { color: #0F172A; font-weight: 600; }
em { color: #475569; }

/* Lists */
ul, ol { margin: 2mm 0 4mm 0; padding-left: 6mm; }
li { margin-bottom: 1.5mm; }

/* Code */
code {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 9pt;
  background: #F1F5F9;
  color: #0F172A;
  padding: 1pt 4pt;
  border-radius: 3pt;
}
pre {
  background: #0F172A;
  color: #E2E8F0;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 8.5pt;
  line-height: 1.5;
  padding: 4mm 5mm;
  border-radius: 4pt;
  margin: 3mm 0 5mm 0;
  overflow-x: auto;
  page-break-inside: avoid;
}
pre code { background: transparent; color: inherit; padding: 0; }

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 3mm 0 5mm 0;
  font-size: 9.5pt;
  page-break-inside: avoid;
}
th {
  background: #1E3A8A;
  color: #FFFFFF;
  font-weight: 600;
  text-align: left;
  padding: 2.5mm 3mm;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.3pt;
}
td {
  padding: 2.2mm 3mm;
  border-bottom: 1px solid #E2E8F0;
  vertical-align: top;
}
tr:nth-child(even) td { background: #F8FAFC; }

/* Blockquote */
blockquote {
  border-left: 3pt solid #2563EB;
  background: #F0F9FF;
  padding: 3mm 5mm;
  margin: 4mm 0;
  color: #1E40AF;
  font-style: italic;
}
blockquote p { margin: 0; }

/* Horizontal rule */
hr {
  border: none;
  border-top: 1px solid #CBD5E1;
  margin: 6mm 0;
}

/* Checklists (markdown-extension renders [ ] as <li>) */
li input[type="checkbox"] { margin-right: 4pt; }

/* Avoid awkward page breaks */
table, pre, blockquote { page-break-inside: avoid; }

/* Section number badges */
h1::first-letter { font-weight: 800; }
"""

COVER_HTML = """
<div class="cover">
  <div class="brand">FLOWRA · ENGINEERING</div>
  <h1>Production Operations Playbook</h1>
  <div class="subtitle">
    Going-live infrastructure, observability, deployment workflow,
    and on-call runbook for a multi-tenant Tally analytics SaaS.
  </div>
  <div class="meta">
    <div>
      <strong>Version 1.0</strong><br/>February 2026
    </div>
    <div style="text-align:right">
      Internal study document<br/>
      <strong>Read fully before go-live</strong>
    </div>
  </div>
</div>
"""


def main():
    md = SRC.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        md,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
            "attr_list",
        ],
    )
    # Render checkboxes (`- [ ]`) as actual unicode boxes for readability in PDF
    body_html = re.sub(r"\[\s\]", "☐", body_html)
    body_html = re.sub(r"\[x\]", "☑", body_html)

    full = (
        '<!doctype html><html><head><meta charset="utf-8"></head><body>'
        + COVER_HTML
        + body_html
        + "</body></html>"
    )
    HTML(string=full, base_url=str(DOCS)).write_pdf(
        str(OUT), stylesheets=[CSS(string=CSS_TEXT)],
    )
    print(f"Wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
