IMPORTANT OCTOBER 2026: The latest OpenAlex-first Radar 2 update supersedes older OpenAI-key instructions below. Read START-HERE-OPENALEX-RADAR-2.md. OPENAI_API_KEY is NOT needed for the default workflow.

# World Radar — runtime and deployment

This repository is the complete uploaded current state, with the six-file realization/evidence redesign applied.

## Radar running times

Radar 1 is scheduled 01:17 and 13:17 UTC and targets a 25-minute job (14 minutes discovery, 9 minutes validation, then housekeeping and waiting if short). Radar 2 is scheduled 04:17 and 16:17 UTC (only two scheduled triggers; its old `workflow_run` trigger was removed). It has an 18-minute **maximum research window**, up to 12 paid web-search assessments when an `OPENAI_API_KEY` secret is provided, and report generation/commit overhead. It does **not** waste time sleeping to 25 minutes or claim research happened when it did not. GitHub-hosted schedules and queued runners may be delayed; a 27-minute job timeout applies to both workflows.

## How to upload

Extract the archive and upload the **contents of the `world-radar-main` directory** to the root of `vevirm/world-radar`, preserving `.github/workflows`, `scripts`, and `stuff`. Replace existing files. GitHub's browser upload may not preserve hidden directories in every workflow; Git CLI or GitHub Desktop is more reliable for full repository replacement. Do not upload the wrapping folder itself. Commit to `main`. Run Radar 2, then Publish radar website (controlled). In Settings → Pages set Source to GitHub Actions.

## Evidence

The Radar 2 report uses realization status and supporting/counter-evidence rather than a 1–100 accuracy score. Existing unassessed claims remain unassessed until research verifies them. A 25-minute job does not guarantee 25 minutes of productive research when no sources or API calls are available.
