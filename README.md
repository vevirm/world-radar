# RADAR 2 UPDATE — OPENALEX RESEARCH IS THE DEFAULT

Read **[START-HERE-OPENALEX-RADAR-2.md](START-HERE-OPENALEX-RADAR-2.md)** first. No OpenAI key is required. Live OpenAlex API searches compare later scholarly studies with older foresight claims; the Word report includes cautious thematic assessments and original source links, not invented accuracy statistics. Existing OpenAlex indexed studies have also been compared offline to seed the report.

---

# European Foresight Radar

A simple EU foresight research observatory.

- **Scanner 1** discovers research leads and writes `research-leads.json` and `stuff/WORLD_RADAR_MASTER.xlsx`. A lead is enough to enter the library; it is not automatically a verified forecast.
- **Scanner 2** reads those leads, uses AI-assisted web research when OPENAI_API_KEY is configured (otherwise an honest offline audit), and writes `retrospective-results.json`, `outlook-summary.json` and `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. The Radar 2 workflow now also uploads a downloadable `Radar-2-Word-and-Audit` artifact on every valid report-generation run.
- **Website** (`index.html`) presents the outlook, searchable research library, reality checks and downloads. It is a static GitHub Pages site.

## Start

1. Upload the entire extracted repository, including `.github/workflows`, to a GitHub repository on branch `main`.
2. Under **Settings → Secrets and variables → Actions**, add `OPENAI_API_KEY` for Scanner 2. Optional: `OPENALEX_API_KEY` for scholarly discovery.
3. Under **Settings → Actions → General**, allow workflows to read and write repository contents. Enable GitHub Pages with **GitHub Actions** as source.
4. Run **European Foresight Radar — Scholarly Discovery and Retrospective Verification** (Scanner 1), then **Radar 2 - outcomes and Word report** (Scanner 2). Run **Publish radar website (controlled)** if needed.

## Notes

GitHub's scheduled Actions are best effort. Scanner 1 targets ~25 minutes (14-minute discovery, 9-minute verification); Scanner 2 allows up to 18 minutes of evidence research, with a limit of 12 requests each run. Radar 2 runs at 04:17 and 16:17 UTC, and Radar 1 at 01:17 and 13:17 UTC. Radar 2 can generate the report without a key, but does no new independent outcome research in offline mode; GitHub Actions now marks these runs failed unless `allow_offline_report` is explicitly selected. The generated Word remains downloadable as an artifact even when a missing key triggers this warning/failure. Live APIs and GitHub deployment have not been tested here. Excel and Word contain saved results and will be refreshed when workflows succeed. GitHub Pages is public: the site and JSON source data are publicly accessible.

Some legacy supporting scripts/data remain deliberately because removing them without a live integration test could break scanning. They are not shown on the website.

**Current Word report:** `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx` was rebuilt and visually checked offline in this package. It contains 28 unverified abstract forecast candidates and 2 source-linked, editorial policy observations, with explicit expected/actual fields. Zero forecast comparisons have passed source review so far. See `RADAR-2-REPAIRS.md`.
