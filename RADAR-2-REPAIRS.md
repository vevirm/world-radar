IMPORTANT OCTOBER 2026: The latest OpenAlex-first Radar 2 update supersedes older OpenAI-key instructions below. Read START-HERE-OPENALEX-RADAR-2.md. OPENAI_API_KEY is NOT needed for the default workflow.

# Radar 2 Word generation — verified repair

## What was broken

1. `update-outcomes.yml` called the default `--provider evidence`, a deliberate audit-only mode that runs **zero new research requests**. The workflow did not expose the `OPENAI_API_KEY` secret to Python, so even a configured key could not have enabled web research in that run.
2. Radar 2 had **both** two cron schedules and `workflow_run` after each Radar 1 completion, yielding up to **four** normal triggers daily although documentation said twice daily.
3. The Word output contained only brief source observations and unverified excerpts; it lacked the consistently labeled **WHAT WAS EXPECTED / WHAT ACTUALLY HAPPENED** pairing, and its run summary did not reveal zero research requests or API failures. 515 leads were incorrectly easy to confuse with 515 outcome comparisons.
4. Four old tests asserted superseded scanner run times and legacy website HTML rather than the current, deployed scanner protocol. `python-docx` was also missing from the shared requirements file.

## Fixed behavior

- `.github/workflows/update-outcomes.yml` runs **twice daily**, at 04:17 and 16:17 UTC, with `OPENAI_API_KEY` passed from Actions secrets.
- Radar 2 `--provider auto` uses the OpenAI Responses API with web search if the key is present; otherwise it rebuilds the report from saved evidence without invented findings. Maximum 12 API assessment requests/run and an 18-minute research window, to limit unexpected cost. The API request uses the supported `web_search` tool.
- Only **candidate forecast excerpts** are eligible for paid automated research, rather than all 515 research leads including title-only bibliography entries. A candidate or AI-suggested source is still *not* a human-reviewed prediction or verdict.
- The Word file `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx` includes counts, provider mode, requests/failures, reviewed verdicts, two manually recorded observations, and 28 excerpt candidates with expected/actual and source references. Absence of validated outcome is explicitly disclosed.
- Rate limits and other research failures are written to JSON/Word; the Word audit can still be committed. `scanner2-audit.json` records the mode, attempts, failures and generation time.
- The website identifies evidence-linked leads without misleadingly calling them verified outcomes and displays title-only bibliographic caveats.

## What we actually checked

`python -m pytest -q`: **72 passed**. `python scripts/retrospective_radar.py --offline --minutes 0`: Word rebuilt successfully. The DOCX was rendered to **12 pages** and visually inspected. Live GitHub Actions and billable API research were **not** executed, and there are **zero** human source-reviewed forecast verdicts in the existing data. Two existing policy observations are documented but should not be treated as forecast accuracy measurements.

## Deploy

Extract the archive, copy the contents of `world-radar-main/` to the GitHub `main` root including the `.github` directory, and set Actions contents permissions to **read/write**. In **Secrets and variables → Actions** add `OPENAI_API_KEY` to enable fresh evidence searches (separately billed, subject to API access and quotas). In **Pages** set publishing to GitHub Actions if deploying the static site. Use **Actions → Radar 2 - outcomes and Word report → Run workflow** to generate a new saved Word version. The report is committed in `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx` and published as a download on the website when Pages deploys.
