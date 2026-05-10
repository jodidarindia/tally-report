# /docs

Internal engineering & business documentation for FLOWRA.

## 📥 Download links (publicly served by the deployed app)

| Document | Format | Direct link |
|---|---|---|
| **FLOWRA Insights Business Proposal** | **PDF (17 pages)** | [Download PDF](https://tally-report-ai.preview.emergentagent.com/docs/FLOWRA_BUSINESS_PROPOSAL.pdf) |
| **FLOWRA Insights Pitch Deck** | **PPTX (19 slides, 3 charts)** | [Download PPTX](https://tally-report-ai.preview.emergentagent.com/docs/FLOWRA_BUSINESS_PROPOSAL.pptx) |
| Production Operations Playbook | PDF (18 pages) | [Download PDF](https://tally-report-ai.preview.emergentagent.com/docs/PRODUCTION_PLAYBOOK.pdf) |

> The links above point at the staging preview. After production deploy
> they'll be at `https://app.flowra.in/docs/<filename>`.

## Files in this folder

| File | Purpose |
|------|---------|
| `FLOWRA_BUSINESS_PROPOSAL.pdf` | Investor/partner business proposal (CONFIDENTIAL). |
| `FLOWRA_BUSINESS_PROPOSAL.pptx` | 19-slide pitch deck for live presentations. |
| `FLOWRA_BUSINESS_PROPOSAL.md` | Markdown source of the proposal. |
| `PRODUCTION_PLAYBOOK.pdf` | 18-page operations playbook — read before go-live. |
| `PRODUCTION_PLAYBOOK.md` | Markdown source of the playbook. |
| `_render_pdf.py` | Regenerates the production-playbook PDF. |
| `_render_business_proposal.py` | Regenerates proposal PDF + 19-slide PPTX with charts. Also auto-mirrors copies into `/app/frontend/public/docs/` so the live app serves them. |
| `_charts/` | matplotlib-rendered chart PNGs that get embedded into the PPTX. |

## How to update

```bash
# Edit the markdown
$EDITOR docs/FLOWRA_BUSINESS_PROPOSAL.md

# Re-render PDF + PPTX + republish to /public/docs/
cd docs && python3 _render_business_proposal.py

# Commit everything (md, pdf, pptx, charts, public copies)
git add docs/ frontend/public/docs/
git commit -m "docs: refresh proposal & deck"
```

Renderers need: `pip install weasyprint markdown python-pptx matplotlib`.

## When to use which artifact

| Situation | Use |
|---|---|
| First investor meeting (live, 20-min pitch) | `FLOWRA_BUSINESS_PROPOSAL.pptx` (19 slides, 3 charts) |
| Send-after-meeting / data-room | `FLOWRA_BUSINESS_PROPOSAL.pdf` (17 pages, full detail) |
| Internal team / engineering | `PRODUCTION_PLAYBOOK.pdf` |

## Pitch deck structure (19 slides)

```
 1  Cover                                     (brand)
 2  The Problem                               (questions Tally can't answer)
 3  The Product                               (18 modules + agent)
 4  Market Size                               (₹3,450 Cr TAM)
 5  Competitive Landscape                     (zero-migration moat)
 6  Pricing & Unit Economics                  (₹2,499 ARPU, 13× LTV/CAC)
 7  Unit Economics 📊                         (CAC payback bar + LTV/CAC chart)
 8  Go-to-Market                              (channel mix table)
 9  Acquisition Funnel 📊                     (10k → 22 paying funnel chart)
10  Traction & Roadmap
11  Team & Hiring Plan
12  Technical Scalability
13  Tenant Growth Curve 📊                    (M1 → M24 with bear/bull bands)
14  24-Month Projections
15  Two-Year Roadmap
16  Risks & Mitigations
17  Why Now
18  The Ask                                   (₹4 Cr seed)
19  Closing                                   ("turn on the lights")
```

## Before sending the proposal externally

Edit `FLOWRA_BUSINESS_PROPOSAL.md` and:
1. Fill in the **Founder bio** in Section 14 (currently a placeholder)
2. Adjust the funding ask in Section 15 if your terms have changed
3. Confirm pricing in Section 3.3 / 6.1 still matches your live pricing page
4. Re-run `python3 _render_business_proposal.py` (it will auto-mirror the
   freshly-rendered files to `/app/frontend/public/docs/`)
5. Commit & push so the public download links serve the new version
