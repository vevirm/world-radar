# European Foresight Radar — Looking Back at the Future

The original static website, dark/amber design, password gate, Findings/Bibliography page, search, topic/actor/assessment filters and GitHub Pages deployment shape remain intact. All former World Radar “joke”/headline/test findings were erased. `findings.json` retains only source-linked studies which passed the automated full-study quality screen (3 in the supplied starting snapshot). The site is not a daily news tracker.

## Core question

**What did EU institutions and independent futures researchers foresee about Europe, and how well do those claims hold up later?** The radar discovers source research, records candidate original wording and links, and distinguishes forecasts from projections, exploratory scenarios, aspirations and warnings. An unobserved scenario is **not** classified as an incorrect prediction.

## Precise rolling date range

The **original publication date** must satisfy:

```
(today - 15 calendar years) <= original_publication_date <= (today - 6 calendar months)
```

On **19 October 2026**, the newest permitted date is **19 April 2026**. Dates are recalculated **at every scan**; the upper bound advances automatically. Work older than 15 calendar years is excluded; a 2014 study remains eligible in October 2026. Older reports are prioritised in verification because retrospective comparison is the purpose; pre-2020 studies are particularly interesting. A website's update/discovery timestamp does not make a new paper old. Year-only dating is conservatively treated as 31 December of that year, and the UI displays just the year. Ambiguous or uncorroborated original publication dates are rejected.

## Sources — EU institutions **plus** external foresight creators

The `actors.json` registry is operational: **22 publisher/source groups**, official HTTPS host allowlists, archive pages and selected historical catalogue leads. These are *discovery sources*, **not a guaranteed admission whitelist for all their work**.

| Category | Registered organisations and programmes |
|---|---|
| EU institutions / agencies | Commission Secretariat-General; JRC; ESPAS; Parliament EPRS; STOA; Council General Secretariat; EUISS/EEAS; EEA; Cedefop; European Commission externally commissioned studies |
| Independent think tanks | CEPS; European Policy Centre; European Council on Foreign Relations |
| International organisation | OECD Strategic Foresight Unit — **only EU/European-applicable work** |
| Universities and academic centres | University of Turku / Finland Futures Research Centre; Tampere University; European University Institute |
| Research institutes | Fraunhofer ISI |
| EU-contracted research consortium | Foresight on Demand (FoD), producing studies **for** EU policymakers through an external specialist network |

The external registry is deliberately extensible. Adding more universities, interdisciplinary institutes, research groups or non-European universities doing genuine EU-focused foresight means adding their source domains/archives in `actors.json`, then allowing them to pass the *same research eligibility check*. An organisation being headquartered in the EU is **not** necessary, while an EU policy / European future connection **is** necessary. Generic global forecasts with no EU/Europe-specific analysis do not qualify. The radar records publisher category and the relationship to the EU; external publications are **not passed off as EU institutional positions**. “EU-funded” or “commissioned for an EU institution” provenance is only applied when supported by explicit document text.

### Sources used to build the initial registry

Some published archives and examples (starting leads, **not** pre-approved findings):

- [European Commission strategic foresight reports](https://commission.europa.eu/strategy-and-policy/strategic-foresight_en) and [JRC competence centre](https://knowledge4policy.ec.europa.eu/foresight/strategic-foresight-reports_en)
- [ESPAS Global Trends](https://espas.eu/gtr.html)
- [STOA project types and externally contracted studies](https://www.europarl.europa.eu/stoa/en/about/projects)
- [CEPS, Alternative Futures of EU Integration](https://www.ceps.eu/ceps-publications/alternative-futures-of-eu-integration-after-the-covid-19-pandemic/)
- [European Policy Centre, Differentiated EUrope 2035](https://epc.eu/publication/Differentiated-EUrope-2035-Elaboration-and-Evaluation-of-Five-Potenti-425a54/)
- [ECFR, Rethinking European Futures](https://ecfr.eu/archive/page/-/170307_Rethinking_European_Futures.pdf)
- [University of Turku, Finland Futures Research Centre publications](https://www.utu.fi/en/university/turku-school-of-economics/finland-futures-research-centre/news/publications)
- [Tampere University research portal](https://researchportal.tuni.fi/en/)
- [OECD strategic foresight](https://www.oecd.org/en/about/programmes/strategic-foresight.html)
- [Foresight on Demand consortium reports](https://foresight-on-demand.eu/publications-and-reports/)

## **Substantive futures research** quality gate — no 2-pagers or hollow reports

A respected institution, scholarly-sounding title, keyword “foresight”, or a 10-page PDF **never guarantees acceptance**. The site is kept empty rather than filled with brochures, thin opinion briefs, meeting agendas, project summaries or recycled PR.

Before listing a finding, the verifier must retrieve **the real full study** (linked PDF or substantive full HTML) on an allowlisted publisher host. It screens for all of the following:

1. **Substantial original text:** at least **2,600 extractable words**, at least **8 PDF pages** when the full text is a PDF, and **190 distinct terms** to reject repetitive filler. Page count *alone* counts for nothing.
2. **Documented method and design:** clear methodological discussion **and** two distinct methodological signals such as Delphi, scenario development, expert interviews, workshop-based backcasting, model construction, trend analysis or evidence review. Just dropping a buzzword into an introduction is not enough by itself.
3. **Traceable foundation:** a genuine source/reference section with multiple bibliographic records or substantial formal citations. A 10-page slide deck with hardly any text or sources fails.
4. **Actual future exploration:** repeated identifiable future claims, pathways, foresight outputs or scenario analyses, not a retrospective assessment with “future” in the heading.
5. **Verified EU relevance:** for outside publishers, the document itself must connect meaningfully to EU policy or Europe's futures. No generic global futures report is accepted simply because the OECD or a European university published it.
6. **Authentic, attributable, dated source:** title and date checked against the original publisher, and a direct source passage extractable from the full paper; no invented findings.

Each published record stores `quality.checks`, estimated word count, PDF pages, method examples, citation signals and links to the full study. Failures are logged in `scan-report.json` (per-run audit artifact). The checks are **conservative automated proxies, not a claim of professional peer review or semantic quality certification**. Genuine reports with scanned/unextractable PDFs, unconventional methodology or source presentation can be missed; use the audit to review them rather than weaken the gate for everyone. No publisher is automatically trusted.

## Recurring schedule — exactly the same durations

The GitHub Actions scheduled run repeats at **:07 and :37 UTC** (nominally every **30 minutes**):

- **15-minute scanning budget:** rotate six publisher groups each run, discovering studies from different registered institutions, university collections, think tanks, research institutes, OECD and consortia. Never repeatedly fetch the same archive during a run.
- **10-minute verification budget:** process the next pending reports fairly across publishers, confirm dates and full studies, enforce research quality and evidence checks, and carry any remaining reports forward. New rejections go to the audit.

The workflow has a 35-minute total ceiling including setup. **These are maximum phase budgets, not enforced waiting periods:** when there is no due source or pending candidate, a phase finishes early instead of pretending to search. GitHub cron is **best-effort** and may be delayed. Not a continuously running hosted worker.

## Persistent source and study rotation — no repeated scan of the same 39 links

The tracked **`radar-state.json` is necessary**. Upload it to the repository **root**, together with `actors.json`, `findings.json`, `scripts/` and other files. The workflow commits it back to GitHub after every run **even if no findings qualified**. Keep the existing `.github/workflows/update-radar.yml` in its workflow directory.

- **Publisher fairness:** 19 registered source groups are interleaved by type (EU, think tank, university, institute, etc.). Each run works on the *next six groups*, rather than restarting from the Commission. The rotation position persists across all scheduled runs.
- **Archive material rotation:** newly encountered older/paginated archive pages and linked publisher research collections become a follow-up queue. Each selected source checks at most two archive pages in a run, choosing unvisited pages before repeats. Root landing pages are rechecked no more than once daily, deeper archive pages no more than once every 30 days.
- **Persistent verification backlog:** candidate URLs found in one run remain queued for later runs. The verifier interleaves work across publishers so a large single source cannot dominate the entire verification budget. Old original reports are prioritised *within* a publisher.
- **No endless rejections:** failed methodological-quality/date checks are recorded with a **45-day cooldown**; transient site/network failures wait **2 days**. Already accepted studies are not re-downloaded unless a new editorial retrospective assessment is added.
- **Useful action logs:** each publisher/page shows candidate links found and *new* reports queued; verification logs accepted/rejected studies and reasons. Logs and the per-run scan/rejection audit distinguish activity from substantive results.

This improves coverage and avoids repeated requests, but it does **not** automatically search the entire web or academic databases. Exploration remains limited to the curated domain allowlist and discoverable linked collection/archive pages. Expand `actors.json` with additional credible research organisations as needed; never weaken full-text quality screening just to increase counts.

**IMPORTANT:** Without the `git add findings.json radar-state.json` update to the workflow, the saved rotation will be lost on every scheduled job, and the scanner will start again at its first publisher. Do not delete `radar-state.json` after the first run.

## Retrospective / “did it actually happen?” rules

The software **does not hallucinate verdicts** or equate a scenario with a prediction. If later *independently verifiable* evidence is missing, a source remains **Not yet assessed**. The optional editorial `assessments.json` stores an exact quote from the original study, original page/section locator, separately dated evidence quote and source URL, assessment rationale and a cautious verdict. The verifier checks quotation, dates, links and original-before-evidence chronology (allowed primary evidence domains include EU sources and selected international official sources). The editor remains responsible for interpreting whether a testable claim truly matched later events.

Supported verdicts: `Observed`, `Partly observed`, `Not observed`, `Too early / unresolved`, `Scenario (not testable)`. Sources do not get any verdict merely because a target year has passed.

## Setup / testing

```bash
pip install -r requirements.txt
python -m pytest -q tests/
python scripts/radar.py discover --once   # Quick diagnostic pass, not production schedule
python scripts/radar.py verify --once     # Source checks; no prepopulated fake findings
python scripts/check_data.py
python -m http.server 8000
```

Open `http://localhost:8000/` (the `file://` protocol can block the JSON loader). In GitHub Actions use the unchanged `--minutes 15` and `--minutes 10` time budgets; stages end early if no distinct work remains. The audit artifacts are retained for 30 days; `findings.json` is committed only when it changes, and `radar-state.json` is committed whenever rotation or queue/history changes.

### Deployment and honesty notes

This project has **offline tested screening rules**, but the actual remote publishers were not exhaustively scanned or every report manually evaluated in this update. Individual domains may block automated downloads or lack extractable dates. A new installation can start with **zero source-verified findings**. The rotation update is an incremental patch and does **not** replace your live `findings.json`; pre-existing accepted records remain available. Older generic extracts are queued for one claim-extraction refresh. GitHub Pages' visitor password is preserved as a cosmetic deterrent, **not real access control**: data and password hash remain visible in the static repository/site. The underlying page structure, dark/yellow styling, search, filters, bibliography, hosting and 15+10 cycle are preserved.

## October 2026 patch — source rotation and better claim selection

The incremental update is supplied **without `findings.json` or `index.html`**, so uploading it will not wipe the existing site or the one currently accepted report. It includes `radar-state.json` only as a starting state; if a future repository already contains a populated state file, keep that one instead.

A report must remain substantial research with cited sources. The new verifier attempts to corroborate missing webpage dates using the original publisher-hosted full PDF before declaring the publication undated. It ranks original forward-looking passages rather than publishing the first vague sentence with the word "will". Existing records with an old extractor version are queued for review on a subsequent workflow run. This passage extraction remains an automated **candidate claim**, not a validated prediction or a statement that it came true.

The scan artifact now includes `rejection_reason_counts`, and Actions prints each rejection reason. If acceptance is still implausibly low, inspect the audit archive under the workflow run's **Artifacts** section; its per-document errors tell us whether the cause is genuine quality failure, missing publication metadata, download failures or overly restrictive parsing. Do not count candidate links as accepted academic studies.


## Rebuilt historical priority shortlist (October 2026)

- Publication window: rolling 15 years; the first ranking emphasises publications 5–10 years old (approximately 2016–2021).
- Each 15-minute discover run refreshes `priority-50.json` from original institutional reports (`priority-sources.json`) and relevant academic DOI records (`research-leads.json`).
- Each subsequent 10-minute checking run now consumes the academic shortlist: `scripts/check_priorities.py` cross-checks DOI/title/year with Crossref and records the outcome. Institutional publisher full-text screening continues separately through the existing registered-domain verifier.
- **A DOI metadata check is NOT full text verification** and does not indicate that a forecast came true. Distinguish `verification_status` from `accuracy_verdict`.
- The shortlist is prioritised for retrospective research, not an objectively validated top-50 ranking and not 50 completed outcome evaluations. For genuine 'landed' assessments, quote the dated original claim and record an independent post-publication observation in the workbook's **Retrospective Checks** tab before assigning a verdict. Scenarios must be treated as conditional possibilities.
- Downloadable workbook: `stuff/WORLD_RADAR_MASTER.xlsx`, with the shortlist, evidence worksheet, DOI check log and full raw library. It is regenerated on each scheduled run.
