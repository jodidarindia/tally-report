# /docs

Internal engineering & business documentation for FLOWRA.

## Files

| File | Purpose |
|------|---------|
| **PRODUCTION_PLAYBOOK.pdf** | 18-page operations playbook — read before go-live. |
| **PRODUCTION_PLAYBOOK.md** | Markdown source of the playbook. |
| **FLOWRA_BUSINESS_PROPOSAL.pdf** | 17-page investor/partner business proposal (CONFIDENTIAL). |
| **FLOWRA_BUSINESS_PROPOSAL.pptx** | 16-slide pitch deck for live presentations. |
| **FLOWRA_BUSINESS_PROPOSAL.md** | Markdown source of the proposal. |
| `_render_pdf.py` | Regenerates the production-playbook PDF. |
| `_render_business_proposal.py` | Regenerates the proposal PDF + pitch deck PPTX. |

## How to update

```bash
# Edit the markdown
$EDITOR docs/FLOWRA_BUSINESS_PROPOSAL.md
# Re-render both PDF and PPTX
cd docs && python3 _render_business_proposal.py
# Or for the production playbook:
cd docs && python3 _render_pdf.py
# Commit everything
git add docs/
git commit -m "docs: refresh proposal & deck"
```

Renderers need: `pip install weasyprint markdown python-pptx`.

## Pitch deck — when to use which

| Situation | Use |
|---|---|
| First investor meeting (live) | `FLOWRA_BUSINESS_PROPOSAL.pptx` (16 slides, 20 min) |
| Send-after-meeting / data-room | `FLOWRA_BUSINESS_PROPOSAL.pdf` (17 pages, full detail) |
| Internal team / engineering | `PRODUCTION_PLAYBOOK.pdf` |

## Before sending the proposal externally

Edit `FLOWRA_BUSINESS_PROPOSAL.md` and:
1. Fill in the **Founder bio** in Section 14 (currently a placeholder)
2. Adjust the funding ask in Section 15 if your terms have changed
3. Confirm pricing in Section 3.3 / 6.1 still matches your live pricing page
4. Re-run `python3 _render_business_proposal.py` and commit
