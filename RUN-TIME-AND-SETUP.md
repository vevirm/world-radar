# World Radar — runtime and deployment

This repository is the complete uploaded current state, with the six-file realization/evidence redesign applied.

## Radar running times

Both radar workflows have a **target of 25 minutes** measured from a clock started after checkout and dependency installation. If research finishes sooner, the final step waits until 1,500 seconds have elapsed. Radar 1 budgets 14 minutes for discovery and 9 for verification; Radar 2 budgets up to 23 minutes for research. The remaining time is for validation, report updates, and commits. There is a 27-minute GitHub Actions job timeout as a safety stop, not an exact 25-minute cap. Setup, platform delays, and GitHub Actions overhead mean the GitHub-reported total run can be slightly over 25 minutes. Failures, cancellation, external outages, and jobs queued before starting cannot be guaranteed exactly 25 minutes. Do not interpret waiting as additional research.

## How to upload

Extract the archive and upload the **contents of the `world-radar-main` directory** to the root of `vevirm/world-radar`, preserving `.github/workflows`, `scripts`, and `stuff`. Replace existing files. GitHub's browser upload may not preserve hidden directories in every workflow; Git CLI or GitHub Desktop is more reliable for full repository replacement. Do not upload the wrapping folder itself. Commit to `main`. Run Radar 2, then Publish radar website (controlled). In Settings → Pages set Source to GitHub Actions.

## Evidence

The Radar 2 report uses realization status and supporting/counter-evidence rather than a 1–100 accuracy score. Existing unassessed claims remain unassessed until research verifies them. A 25-minute job does not guarantee 25 minutes of productive research when no sources or API calls are available.
