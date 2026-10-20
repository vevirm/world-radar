# Scanner 2 — verification contract

This project has **515 discovery leads**, not 515 established predictions. The
provided metadata screening identifies **28 potential forecast passages** that
still need original-document checks; more may be found when full texts become
available. The previous automatic OpenAlex matching was only bibliographic.
It cannot reliably tell whether a forecast happened.

The new default `--provider evidence` makes no charged OpenAlex requests and
always creates:

- `outcome-review-queue.json`: 28 original-source candidate passages requiring
  original text validation and independently dated outcomes.
- `verified-outcomes.json`: explicit, source-reviewed comparison cases.
- `scanner2-audit.json`: counts and the `outcome_verification_complete` flag.
- `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`: reviewed verdicts if any exist,
  separate from official-policy observations and unverified candidates.

The Word report will not claim that 515 forecasts were checked. The workflow
emits a GitHub warning while the validation register has zero verified cases.

## How to record actual comparisons

Add a case to `verified-outcomes.json` only after reading the original and
subsequent official sources. Each must include `lead_id`, `source_reviewed_by`,
`reviewed_on`, `verdict`, `limitations`, `original` (`url`,
`verbatim_passage`, `published_on`, `geography`, `observable`, `target_date`),
and `observation` (`what_happened`, `measured_on`,
`same_metric_and_geography_explained`, `sources` with `url`, `date`, `finding`).
The code rejects missing links, missing originals, unsupported verdicts and
future observations. These structural checks **do not verify what a webpage
actually says**; the source reviewer remains responsible for truthfulness.

A genuinely automatic, trustworthy outcome verifier would need full-text
licensing and retrieval, extraction of comparable claims and measurements,
source search beyond OpenAlex, and factual checking. This revision is a strict,
auditable foundation, **not** a completed autonomous verifier.
