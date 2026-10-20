IMPORTANT OCTOBER 2026: The latest OpenAlex-first Radar 2 update supersedes older OpenAI-key instructions below. Read START-HERE-OPENALEX-RADAR-2.md. OPENAI_API_KEY is NOT needed for the default workflow.

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


## Fix for GitHub Actions run #15: green check, no report download, no research

GitHub Actions run #15 completed in ~20 seconds but showed `Artifacts –` and a warning
that `OPENAI_API_KEY` was missing. That is **not** a completed evidence-research run:
the workflow refreshed the saved-data Word audit only and did not upload any file
for downloading from the run. The old workflow had no `actions/upload-artifact`
step.

The new workflow always generates and validates a fresh Word document, attaches
`Radar-2-Word-and-Audit` as an Actions artifact, and continues to commit the active
report to `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. If the API secret is
missing or all research requests fail, the final status step **fails** (red) after
the artifact has been uploaded. This avoids misleading green success results.

To intentionally perform an offline-only report refresh with a green status,
run the workflow manually with **allow_offline_report** enabled; no new research
will be performed. You do NOT have to enable this input to download the report.

With `OPENAI_API_KEY` configured, the Word now includes a separate, clearly
**unreviewed automated-research** field for observed developments backed by
potentially relevant dated sources. Automated findings are not automatically
upgraded to source-verified forecast verdicts. The report is still an honest
audit, not a substitute for original-document review.

### Exact GitHub setup

1. Replace the `.github/workflows/update-outcomes.yml` file and the entire
   `scripts/` directory with this package; upload all changed tests and docs.
2. In your GitHub repo, choose **Settings → Secrets and variables → Actions →
   New repository secret** and create **`OPENAI_API_KEY`** containing your own
   API key (never put the key in a source file).
3. Under **Settings → Actions → General → Workflow permissions**, select
   **Read and write permissions** so the bot can commit the generated Word file.
4. Go to **Actions → Radar 2 - outcomes and Word report → Run workflow**. Leave
   *allow_offline_report* OFF for real API-assisted research.
5. When the run ends, download **Radar-2-Word-and-Audit** from the **Artifacts**
   section on the run summary page and open `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`
   inside the downloaded ZIP. The report is also stored in the repository's
   `stuff/` folder. If live API research fails, the job now shows a red X and
   explains why, while the valid generated report remains downloadable.

A free ChatGPT subscription/plan does not itself add credit to the separate
OpenAI API billing account. Successful AI-assisted checks require an API key
with active billing and access to the Responses API web search tool.
