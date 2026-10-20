# Radar 2 repair — October 2026

## Which Word file actually updates?

The active `.github/workflows/update-outcomes.yml` runs `scripts/retrospective_radar.py --provider auto --minutes 18 --max-claims 12` and commits `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. Other similarly named Word files in `stuff/` are legacy outputs from different scripts. They are **not** automatically updated by this workflow.

## What changed

- Word has clear expected/actual fields for forecast candidates, source-linked policy observations and verified comparisons (if any); it also shows research attempts, failures and last evidence-search date and carefully distinguishes unreviewed candidates from source-reviewed results.
- Removes outdated/orphaned records from the active JSON snapshot, and filters certain obvious fictional scenarios and recommendations out of predictions.
- Includes manually curated predictions *only* if they have a source URL, without repeating the EU 2040 working-age example.
- Rebuilds a Word report in offline mode without pretending this is new verification.

## Activation

Replace repository files (including hidden `.github` directory), configure Actions workflow write permission, and set repository `OPENAI_API_KEY` secret. Run **Radar 1** first and **Radar 2** afterward in GitHub Actions. Review the Actions logs for `Assessed:` lines and failures. If a run says 0 research attempts, the Word was rebuilt but no new evidence search took place. The API key must have access to Responses API web search; quota and external network access are required.

## Limitations

A source URL and model-generated summary are *not* independent human verification. The current source corpus contains few extractable time-bounded predictions; better source/claim extraction and authoritative statistic-specific connectors are necessary for comprehensive automated expected-vs-actual comparisons. The report deliberately does not manufacture actual outcomes.
