# Radar 2 | Reality-check edition

## Why the previous 89-page report failed
It treated bibliographic title similarity as evidence of a prediction's outcome. The 515 indexed items are research leads, not 515 testable predictions. Matching publications are NOT outcome verification.

## What this version now does
1. Screens original indexed abstracts for passages that might contain a dated measurable forecast. Titles alone never qualify. The phrase is explicitly labelled **candidate**, pending comparison against the full original paper.
2. Limits the automated OpenAlex later-publication search to candidates (and identifies all remaining leads as requiring original/full-text review or lacking an explicit forecast). This reduces paid OpenAlex requests; the key remains `OPENALEX_API_KEY`.
3. Produces a short Word evidence-review report with distinct sections: verified outcome comparisons (only where supported), documented real-world *policy-target progress* observations, and pending forecast candidates.
4. Keeps the full machine-readable register in retrospective-results.json, rather than generating 89 pages of false empty verdicts.
5. Uses `outcome-observations.json` for carefully reviewed, official-source progress checks. These are not automatically interpreted as original-study predictions. Its two supplied observations are EU renewable energy and EU net emissions progress.
6. Keeps existing transport retries/checkpoints/API authentication.

## Important limitations
- This is NOT yet a fully autonomous original-paper-reading and official-source outcome verifier. OpenAlex is a scholarly metadata service, not a database of observed real-world events. A subscription does not itself provide full-text forecast extraction or verified outcome evidence.
- It cannot honestly produce a valid verdict for 515 titles. The relevant original full texts and matched independent follow-up observations are required.
- The 28 candidates from the current snapshot are **screening heuristics**, not verified predictions. The 217 metadata-only leads need original full texts. Metadata screening can miss predictions inside long papers.
- The two official-source observations were curated from EU/Eurostat/EEA; they concern progress toward policy targets and are NOT scientific forecast realizations.
- Live authenticated OpenAlex access was not available during local testing. The GitHub run is still required to verify real usage/quota.

## How to run
Use GitHub Actions > Radar 2 - outcomes and Word report > Run workflow. Keep your existing `OPENALEX_API_KEY` repository secret. Do not send secrets in chat.

## Testing
Run: `python -m pytest -q tests/test_forecast_screening.py tests/test_incomplete_openalex.py tests/test_scanner_handoff.py`.
The previous repo also contains some unrelated pre-existing tests expecting an outdated Scanner 1 workflow and obsolete HTML IDs. Those tests are not made to pass by modifying unrelated features.
