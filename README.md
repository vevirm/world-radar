# The Hindsight Files · European Foresight Radar

**Back then → What came next → How did the idea age?**

This is meant to be an enjoyable retrospective, not a giant machine-generated audit.
The website now leads with short, sourced stories and keeps the research catalogue
behind an expandable library. The Word download is a **four-page reader's digest**
with a timeline of what was said, what was measured, and what remains unknown.

**About the 1–100 numbers:** the current two policy stories show *target-level
snapshots*, not grades for researchers or predictions (59/100 and 68/100 using
explicitly dated 2024 measurements and stated EU 2030 goals). A true hindsight
rating is only shown when an original passage and a later comparable outcome
have been source-reviewed, plus an editor provides reasons and 1–100 scores for
clarity (25%), anticipation (50%), and usefulness (25%). At the moment, **zero**
such original forecasts are fully reviewed. Never assign an accuracy score from
a paper title, abstract, or merely related later study.

## Files that matter

- `index.html` — the reader-friendly website.
- `hindsight-stories.json` — the curated, reproducible website story feed.
- `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx` — the short Word digest.
- `outcome-observations.json` — editor-reviewed policy observations and target yardsticks.
- `verified-outcomes.json` — strictly reviewed actual forecast comparisons when available.
- `scripts/storybook.py` — generates digest and website stories from audited data.
- `retrospective-results.json`, `outcome-review-queue.json`, `scanner2-audit.json` — the detailed scanner/review logs, **not** part of the short digest.

### Refresh without live API access

Run `python scripts/retrospective_radar.py --provider evidence --offline --minutes 0`
for a fresh local digest from saved evidence. Regular GitHub Actions still run
Scanner 2 and automatically rebuild both the website story feed and Word file.
See the original setup notes below for deployment details.

---

# RADAR 2 UPDATE — OPENALEX RESEARCH IS THE DEFAULT

For the **scanner setup**, read [START-HERE-OPENALEX-RADAR-2.md](START-HERE-OPENALEX-RADAR-2.md). No OpenAI key is required for live OpenAlex research, which finds later studies; those study matches remain in the detailed JSON. The Word report is now deliberately short and story-led.

---

# European Foresight Radar

A simple EU foresight research observatory.

- **Scanner 1** discovers research leads and writes `research-leads.json` and `stuff/WORLD_RADAR_MASTER.xlsx`. A lead is enough to enter the library; it is not automatically a verified forecast.
- **Scanner 2** reads those leads, searches later scholarship via OpenAlex by default (or uses an explicitly selected OpenAI research route), and writes `retrospective-results.json`, `hindsight-stories.json`, `outlook-summary.json` and `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. The Radar 2 workflow now also uploads a downloadable `Radar-2-Word-and-Audit` artifact on every valid report-generation run.
- **Website** (`index.html`) presents the outlook, searchable research library, reality checks and downloads. It is a static GitHub Pages site.

## Start

1. Upload the entire extracted repository, including `.github/workflows`, to a GitHub repository on branch `main`.
2. Under **Settings → Secrets and variables → Actions**, add `OPENAI_API_KEY` for Scanner 2. Optional: `OPENALEX_API_KEY` for scholarly discovery.
3. Under **Settings → Actions → General**, allow workflows to read and write repository contents. Enable GitHub Pages with **GitHub Actions** as source.
4. Run **European Foresight Radar — Scholarly Discovery and Retrospective Verification** (Scanner 1), then **Radar 2 - outcomes and Word report** (Scanner 2). Run **Publish radar website (controlled)** if needed.

## Notes

GitHub's scheduled Actions are best effort. Scanner 1 targets ~25 minutes (14-minute discovery, 9-minute verification); Scanner 2 allows up to 18 minutes of evidence research, with a limit of 12 requests each run. Radar 2 runs at 04:17 and 16:17 UTC, and Radar 1 at 01:17 and 13:17 UTC. Radar 2 can generate the report without a key, but does no new independent outcome research in offline mode; GitHub Actions now marks these runs failed unless `allow_offline_report` is explicitly selected. The generated Word remains downloadable as an artifact even when a missing key triggers this warning/failure. Live APIs and GitHub deployment have not been tested here. Excel and Word contain saved results and will be refreshed when workflows succeed. GitHub Pages is public: the site and JSON source data are publicly accessible.

Some legacy supporting scripts/data remain deliberately because removing them without a live integration test could break scanning. They are not shown on the website.

**Current Word report:** `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx` is a four-page, visually checked hindsight digest: two dated policy observations, two approachable later-study conversations, and a scoring explanation. The 143 unverified possible forecast passages remain in `outcome-review-queue.json` instead of cluttering the Word file. Zero forecast comparisons have passed source review so far.
