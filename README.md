# VV Futures · European foresight observatory

**Purpose:** Gather future-oriented claims published **2011–2022** about Europe or relevant developments, find *plausible* later research addressing the same claims, and leave interpretation to a person assisted by an LLM.

## What the site provides

- `index.html`: simple visitor entrance (courtesy password `VVfutures2026.`), download links, historical-claims library. This is not real security; GitHub Pages serves documents directly.
- `VV-FUTURES-REVIEWED-FINDINGS.docx`: editorial accounts **only**. Generated from `reviewed-findings.json`, initially empty. Scanner 2 cannot add final conclusions.
- `VV-FUTURES-POSSIBLE-CONNECTIONS.docx`: candidate later publications, clearly **unchecked**.
- `VV-FUTURES-ALL-CLAIMS-AND-SOURCES.xlsx`: cumulative claims and provisional connections.

## Daily automation

The pre-existing `update-radar.yml` runs Scanner 1 twice daily, at 01:17 and 13:17 UTC. The new `eu-observatory-twice-daily.yml` follows at 02:45 and 14:45 UTC, and can also be started manually. Both cron schedules are best effort; GitHub can delay scheduled actions. The Scanner 2 job searches a rotating set of original claims rather than repeatedly covering four fixed cases. It commits `observatory-data.json` and the document outputs to `main`. It requires Actions write permission.

## Claim matching

Passages are taken from Scanner 1's `research-leads.json` `radar2_seed.original_passage`; original years are restricted to 2011–2022. Claim-specific terms are extracted from the passage. OpenAlex searches later works. A candidate requires multiple distinguishing overlapping terms or recognisable object vocabulary; wrong periods are rejected and scope mismatch is labelled. Matching is heuristic **and not proof of relevance**. No incorrect claim–paper linkage may be published as a reviewed conclusion without editorial checking. Abstracts are not full-text reads. Retained connections store reason, search query, publication URL, abstract, and unchecked status.

## Manual editorial updates

To add a reviewed finding, edit `reviewed-findings.json` by adding a record to `findings` with `title`, `original_claim`, `interpretation`, and `sources` (URL strings). Run `python scripts/eu_observatory.py build`, commit the generated documents. This avoids allowing subsequent scanners to overwrite human-approved accounts. For an LLM review, upload `observatory-data.json` and the existing reviewed Word to the LLM, require source checking and approval before updating `reviewed-findings.json`.

## Tests and limitations

`python -m unittest discover -s tests -p 'test_eu_observatory.py'` checks filtering and deterministic claim/source matching without internet. Earlier repository tests do not establish that historical claims are confirmed, that abstracts equal reading whole papers, or that candidate connections are true. First full live run and website publishing still need verification. The CSV-like Excel OOXML workbook is valid but has minimal formatting. A large library may require a pagination/size optimisation over time.

**Legacy workflow:** `foresight-observatory.yml` is disabled to prevent duplicate, conflicting twice-daily Scanner 2 runs. Use the new `eu-observatory-twice-daily.yml` workflow.
