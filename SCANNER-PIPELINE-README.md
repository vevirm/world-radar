# Scanner 1 → Scanner 2 → Word (free default)

Scanner 1 writes `research-leads.json` and the Excel workbook. A successful Scanner 1 run automatically triggers Scanner 2 via GitHub Actions `workflow_run`. Scanner 2 reads the latest committed lead file from `main`, checks later scholarly research with OpenAlex, saves `retrospective-results.json`, writes `outlook-summary.json`, and regenerates `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. GitHub Pages then updates on the data commit.

To run it manually: Actions → Radar 2 - outcomes and Word report → Run workflow. No paid OpenAI key is required. Optional GitHub Actions secret `MAILTO` provides the email for OpenAlex polite-pool access. `MAILTO` must be a valid email address.

**Important**: Free OpenAlex can find related subsequent *papers*, not verify physical-world prediction outcomes. The Word report separates follow-up publications from verified outcomes. It will not fabricate realization claims. Source availability and network access determine what results are returned.

For local tests (no network): `python scripts/retrospective_radar.py --offline` regenerates the summary and Word from saved data. For live free checks: `python scripts/retrospective_radar.py --provider free --minutes 4 --max-claims 100`.
