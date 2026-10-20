# World Radar 2: incremental OpenAlex assessments (no OpenAI subscription needed)

**Purpose:** Slowly assemble a defensible picture of European/EU-related foresight by looking at what an earlier study said, finding later related research, and comparing the abstracts' reported findings. The system makes *tentative literature assessments*, **not automatic verified forecasts** or an EU Commission foresight accuracy score. The corpus contains diverse studies **about Europe**; do not attribute all of them to EU institutions.

## To install

1. Replace your GitHub repository with the contents of this package, including `.github/workflows/update-outcomes.yml` and the `scripts` directory. Upload files into the root of `main` (not an extra nested `world-radar-main/` directory).
2. The scheduled Radar 2 Action (`17 4,16 * * *`, UTC) now uses **OpenAlex by default**. **OPENAI_API_KEY is not required.** Set `OPENALEX_API_KEY` in **Settings → Secrets and variables → Actions** if your OpenAlex plan requires an API key (supported automatically). Optionally set `MAILTO` to an email contact for API etiquette. Never commit secrets into code.
3. Give GitHub Actions **Read and write** workflow permissions if you want the bot to commit its output to `main`.
4. Go to **Actions → Radar 2 - outcomes and Word report → Run workflow**, leave **allow_offline_report** unchecked for new OpenAlex searches.
5. Open the run summary, then download **Artifacts → Radar-2-Word-and-Audit**. The active document is `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. It is also committed in the repo.

## What it does on each scheduled run

- Begins with **515 existing indexed European foresight-related research leads** (the corpus can grow when Radar 1 updates `research-leads.json`).
- Gives initial priority to **potential forecast passages** and then rotates across the whole corpus on future runs. It does not endlessly recheck the same 12 papers.
- Calls **OpenAlex `works`** with distinctive study/topic terms, requiring later publication dates. Records URLs, titles, years, relevant abstract result passages, topical matches and whether Europe is mentioned. It supplements with already-indexed papers as explicitly labelled catalogue sources.
- Writes, for each checked record, **WHAT WAS SAID**, **WHAT LATER STUDIES REPORT**, a **tentative assessment**, limitations and links. It retains the original study and later citations in `retrospective-results.json` and summarizes up to 40 of the strongest comparisons in the Word report.
- The report distinguishes source-reviewed outcomes, human-recorded policy developments, potential forecasts, and unreviewed later scholarly evidence. It never treats simply finding a similar paper as proof that the original forecast happened.
- Continues accumulating comparisons in `retrospective-results.json`, uploads a fresh Word file as a GitHub artifact, commits the report, and exposes progress counts in `scanner2-audit.json` and `outlook-summary.json`.
- If **all** live OpenAlex requests fail, the run fails **after** the report and saved audit have been uploaded. A green run now means live research requests succeeded, **not** that the EU foresight predictions were all correct.

## Run without API/network, using only the indexed research corpus

```bash
pip install -r requirements.txt
python scripts/retrospective_radar.py --provider catalogue --minutes 6 --max-claims 515
python scripts/validate_radar2_report.py
```

This compares saved paper metadata already in `research-leads.json` (some originally indexed by OpenAlex or Crossref). It does **not** contact OpenAlex and must not be described as newly retrieved evidence. The included Word file is generated using this mode; the downloaded ZIP contains these saved comparison records.

To force live study searches on a computer with Internet and OpenAlex API access:

```bash
python scripts/retrospective_radar.py --provider openalex --minutes 18 --max-claims 12
```

## What results mean

- **Abstract reports results:** a later paper's abstract contains language such as "we found" or "results show". The finding **could be from simulations, models or empirical datasets**; this automatic classification cannot tell which reliably.
- **Related studies without comparable results:** an academic follow-up exists, but no clearly applicable outcome can be extracted.
- **No matching study in this search:** only a coverage gap; not evidence of failure.
- **Source-reviewed forecast verdicts:** a separate, stricter human source/metric/date check. Only these can support an eventual formal foresight accuracy calculation.

The whole effort is exploratory. Some matches will be irrelevant or too broad; reviewers should check links, methods, measurements and original forecasts. More accurate assessments can be added incrementally, and future runs must not overwrite independently verified judgments with tentative metadata matches.

## Files that matter

- `.github/workflows/update-outcomes.yml`: scheduling, API configuration, Word artifact and commits.
- `scripts/openalex_comparison.py`: literature lookup, source filters and tentative comparison logic.
- `scripts/retrospective_radar.py`: incremental queue, saving results and generating Word.
- `scripts/check_radar2_live_status.py`: ensures the success badge reflects a real live research attempt.
- `retrospective-results.json`: accumulated individual assessments and citations.
- `outlook-summary.json`: trend and coverage summary for readers and website.
- `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`: the **only actively generated expected-versus-actual** Word report. Similarly named files elsewhere in `stuff/` are legacy files.
