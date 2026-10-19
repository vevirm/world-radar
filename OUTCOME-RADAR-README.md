# Radar 2: independent real-world outcome discovery

Radar 2 is **not limited to already collected material**. It searches independently
for **real-world developments and measured outcomes from June 2026 onward**, and
uses keywords drawn from Radar 1 findings, priority reports, and scholarly-index
leads to guide the search. It does **not** search for new old predictions. Research leads are search vocabulary,
not proof of an original prediction. Source dates of evidence must be on or after
2026-06-01. Discovered results remain labelled *unverified leads*.

GitHub Actions workflow: `.github/workflows/update-outcomes.yml`.
Run locally: `python scripts/outcome_discovery.py --minutes 19 --max-queries 500`.
GitHub Actions timeout is 22 minutes, allowing setup and saving time.
The 19 minutes is a network-search **budget**, not a forced sleep: it may finish
sooner if all queued searches finish or feeds are inaccessible. Inaccessible feeds
are logged and retained history is not erased. Never describe the workflow duration
as evidence of better verification.

Outputs:
* `outcome-history.json`: cumulative (up to 12,000 discovery leads plus up to 800
  evidence links per tracked idea); includes query execution totals and failures.
* `outcome-ideas-auto.json`: extracted and source-linked candidate original claims.
* `stuff/FUTURE_IDEAS_WHAT_HAPPENED.docx`: short idea/result/score/source entries.

The existing manually configured predictions remain in `future-ideas.json`.
The scanner uses Radar 1 as historical comparison material and additionally imports forecast-like statements from
`findings.json`, and creates search queries for them. This *does not* prove they
are definite, measurable predictions. It reads Google News RSS **headlines**, not
full documents or live statistical datasets. Only configured support/refute phrases
count toward score changes; others appropriately stay at **50 (unresolved)**.
Scores are provisional and must not be mistaken for independent fact-checking.

This is a growing *discovery* engine, not a finished automated historian. Improving
real falsification would require full-text extraction and claim-specific comparisons
with authoritative official datasets and dated measurement periods.
