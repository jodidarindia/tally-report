# /docs

Internal engineering documentation for FLOWRA.

## Files

| File | Purpose |
|------|---------|
| **PRODUCTION_PLAYBOOK.pdf** | Polished PDF for studying before go-live. Print, annotate, share with team. |
| **PRODUCTION_PLAYBOOK.md** | Markdown source of the playbook. Edit this, not the PDF. |
| **_render_pdf.py** | Regenerates the PDF from the markdown. Run after edits. |

## How to update the playbook

```bash
# 1. Edit the markdown
$EDITOR docs/PRODUCTION_PLAYBOOK.md

# 2. Re-render the PDF
cd docs && python3 _render_pdf.py

# 3. Commit both files
git add docs/PRODUCTION_PLAYBOOK.md docs/PRODUCTION_PLAYBOOK.pdf
git commit -m "docs: refresh production playbook"
```

The renderer needs `weasyprint` and `markdown`:

```bash
pip install weasyprint markdown
```

## What's in the playbook

A self-contained 18-page operations manual covering:

1. Environment topology (local / staging / production)
2. Branching & release workflow (feature → develop → main)
3. CI/CD pipeline (GitHub Actions)
4. Observability stack (Sentry, BetterStack, UptimeRobot)
5. Database operations (Atlas snapshots, migrations, restore drills)
6. Tally agent update channel (auto-update, code-signing, rollback)
7. Production debugging runbook
8. Security & compliance checklist
9. Cost breakdown (₹5k / month minimum, ₹13k / month recommended)
10. Four-week phased rollout plan
11. Decisions matrix + worksheet for the team

Read it once cover-to-cover before the first paying customer.
