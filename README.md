# European Foresight Radar — Looking Back at the Future

The original static website, dark/amber design, password gate, Findings/Bibliography page, search, topic/actor/assessment filters and GitHub Pages deployment shape remain intact. All former World Radar “joke”/headline/test findings were erased. `findings.json` is **deliberately empty** until the new scanner qualifies historical, source-verified *full studies*. The site is not a daily news tracker.

## Core question

**What did EU institutions and independent futures researchers foresee about Europe, and how well do those claims hold up later?** The radar discovers source research, retains verified original wording and links, and distinguishes forecasts from projections, exploratory scenarios, aspirations and warnings. An unobserved scenario is **not** classified as an incorrect prediction.

## Precise rolling date range

The **original publication date** must satisfy:

```
2015-01-01 <= original_publication_date <= (today - 6 calendar months)
```

On **16 October 2026**, the newest permitted date is **16 April 2026**. Dates are recalculated **at every scan**; the upper bound advances automatically. Work from 2014 or earlier is excluded even if otherwise excellent. Older reports are prioritised in verification because retrospective comparison is the purpose; pre-2020 studies are particularly interesting. A website's update/discovery timestamp does not make a new paper old. Year-only dating is conservatively treated as 31 December of that year, and the UI displays just the year. Ambiguous or uncorroborated original publication dates are rejected.

## Sources — EU institutions **plus** external foresight creators

The `actors.json` registry is operational: **19 publisher/source groups**, official HTTPS host allowlists, archive pages and selected historical catalogue leads. These are *discovery sources*, **not a guaranteed admission whitelist for all their work**.

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

- **15 minutes scan:** repeatedly discover historical potential studies on EU institutional, independent think-tank, university, research-institute, OECD and consortium archives.
- **10 minutes verification:** fetch original source, resolve original date (2015 ↔ rolling cutoff), download/check full text, enforce quality, verify any separate retrospective evidence, then write qualifying source records. New rejections go to the audit.

The workflow has a 35-minute total ceiling including setup. GitHub cron is **best-effort** and may be delayed. Not a continuously running hosted worker.

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

Open `http://localhost:8000/` (the `file://` protocol can block the JSON loader). In GitHub Actions use the unchanged full-duration `--minutes 15` and `--minutes 10` stages. The audit artifacts are retained for 30 days; `findings.json` is committed only when it changes.

### Deployment and honesty notes

This project has **offline tested screening rules**, but the actual remote publishers were not exhaustively scanned or every report manually evaluated in this update. Individual domains may block automated downloads or lack extractable dates. The package starts with **zero source-verified findings**, not fabricated examples. GitHub Pages' visitor password is preserved as a cosmetic deterrent, **not real access control**: data and password hash remain visible in the static repository/site. The underlying page structure, dark/yellow styling, search, filters, bibliography, hosting and 15+10 cycle are preserved.
