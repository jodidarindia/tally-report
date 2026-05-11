"""Render /app/COMPLETE_DOCUMENTATION.md to a polished PDF.

Output: /app/docs/FLOWRA_COMPLETE_DOCUMENTATION.pdf

Run:
    python3 /app/docs/_render_complete_documentation.py
"""
from pathlib import Path
from datetime import datetime
import markdown
from weasyprint import HTML, CSS

ROOT = Path("/app")
SRC = ROOT / "COMPLETE_DOCUMENTATION.md"
OUT = ROOT / "docs" / "FLOWRA_COMPLETE_DOCUMENTATION.pdf"

CSS_STYLES = """
@page {
    size: A4;
    margin: 18mm 16mm 22mm 16mm;
    @top-left { content: "FLOWRA — Complete Application Documentation"; font-size: 9pt; color: #94a3b8; }
    @bottom-right { content: counter(page) " / " counter(pages); font-size: 9pt; color: #94a3b8; }
    @bottom-left { content: "v2026.02 · flowra.in"; font-size: 9pt; color: #94a3b8; }
}
@page :first { @top-left { content: ""; } @bottom-left { content: ""; } @bottom-right { content: ""; } }

body {
    font-family: -apple-system, "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1e293b;
}

h1 { font-size: 22pt; color: #0f172a; border-bottom: 3px solid #2563EB; padding-bottom: 6px; margin-top: 28px; page-break-after: avoid; }
h2 { font-size: 16pt; color: #0f172a; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-top: 26px; page-break-after: avoid; }
h3 { font-size: 13pt; color: #1e3a8a; margin-top: 20px; page-break-after: avoid; }
h4 { font-size: 11pt; color: #334155; margin-top: 14px; }

p { margin: 6px 0 10px; }
ul, ol { margin: 6px 0 10px; padding-left: 22px; }
li { margin: 2px 0; }

a { color: #2563EB; text-decoration: none; }

code {
    font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
    background: #f1f5f9;
    color: #0f172a;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9.5pt;
}

pre {
    font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
    background: #0f172a;
    color: #e2e8f0;
    padding: 12px 14px;
    border-radius: 6px;
    font-size: 8.6pt;
    line-height: 1.45;
    overflow-x: hidden;
    white-space: pre;
    page-break-inside: avoid;
    margin: 10px 0;
}
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }

blockquote {
    border-left: 4px solid #2563EB;
    background: #eff6ff;
    margin: 12px 0;
    padding: 8px 14px;
    color: #1e3a8a;
    border-radius: 0 4px 4px 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 16px;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
th, td {
    border: 1px solid #cbd5e1;
    padding: 6px 9px;
    text-align: left;
    vertical-align: top;
}
th { background: #1e3a8a; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #f8fafc; }

hr { border: none; border-top: 1px solid #e2e8f0; margin: 22px 0; }

.cover {
    page-break-after: always;
    text-align: center;
    padding-top: 70mm;
}
.cover .brand {
    font-size: 56pt;
    font-weight: 800;
    letter-spacing: -2px;
    color: #2563EB;
    margin: 0;
}
.cover .strap { font-size: 12pt; color: #64748b; margin: 8px 0 0; }
.cover .title { font-size: 22pt; font-weight: 700; color: #0f172a; margin: 60px auto 0; max-width: 14cm; }
.cover .sub   { font-size: 11pt; color: #475569; margin: 12px auto 0; max-width: 14cm; }
.cover .meta {
    margin: 40mm auto 0;
    font-size: 10pt;
    color: #64748b;
    max-width: 12cm;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 18px;
}
.cover .meta strong { color: #0f172a; }
"""


def build():
    md_text = SRC.read_text(encoding="utf-8")

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "attr_list"],
    )

    cover = f"""
    <section class="cover">
        <p class="brand">FLOWRA</p>
        <p class="strap">Tally* + Busy* Analytics Platform</p>
        <p class="title">Complete Application Documentation</p>
        <p class="sub">A plain-English reference covering every module, every flowchart,
        every data path — from Tally / Busy on the desk, through the Desktop Agent,
        all the way to the field salesman's phone.</p>
        <div class="meta">
            <strong>Version:</strong> FY 2026-27 release ·
            <strong>Generated:</strong> {datetime.now().strftime('%d %B %Y')}<br>
            <strong>Audience:</strong> business owners, accountants, sales managers,
            admins, and partners.<br>
            <strong>Pages include:</strong> 16 sections · 10 flowcharts ·
            role × feature matrix · data-model glossary.
        </div>
    </section>
    """

    full_html = f"<!doctype html><html><head><meta charset='utf-8'></head><body>{cover}{html_body}</body></html>"

    HTML(string=full_html, base_url=str(ROOT)).write_pdf(
        target=str(OUT),
        stylesheets=[CSS(string=CSS_STYLES)],
    )
    size_kb = OUT.stat().st_size // 1024
    print(f"✓ Wrote {OUT} ({size_kb} KB)")


if __name__ == "__main__":
    build()
