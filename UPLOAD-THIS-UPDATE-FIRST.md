# 6 November 2026 follow-up to the existing VV Futures research archive

Replace the corresponding files in the root of the GitHub repository with the files in this complete ZIP. Keep all other files and the `.github` workflows. This is a **cumulative research update**, not a reset of the scanner and not an assertion that each older future came true or false.

The main Word investigation now contains the preserved 12 cases plus a new **T13**, with deep T04/T05 rechecks; reviewed findings and methodology have dated addenda. The existing Excel register was **expanded** with all original rows kept, a new 2026-11-06 review sheet, and source-linked evidence. A 6 November JSON increment and restored 5 November source/event records allow the homepage to show accurate cumulative research counters.

**As of 6 November 2026:** 13 trajectories; 54 dated milestones; 49 source records; 18 carefully qualified links. The previous 63 LLM-assisted editorial accounts remain draft research interpretations. For the full sources, comparison limitations and methodological notes, read `research-updates/README.md` and `RESEARCH-UPDATE-2026-11-06.md`.

**Do not regenerate the manually reviewed Word and Excel outputs** with the older optional `scripts/present_outputs.py` without integrating the dated follow-ups, because that tool does not yet reproduce all manually appended material. Automated scanner workflows were not altered. Run `python scripts/check_trajectory_update.py` after copying the update.

---

# VV FUTURES — upload-ready update (2 November 2026)

## What this is

This is a **small replacement/update pack**, not a new repository and not a second
archive of duplicate report names. It was built against the supplied
`world-radar-main (16).zip` snapshot. It replaces two files **at exactly their
existing paths**, adds one accessible new narrative report, and records the
research as structured data for future rebuilding.

The original historical claims, 63 already-checked LLM-reviewed accounts, and all
14 original Excel worksheets are retained. The 12 additional forward-history
cases are distinct; some have stable historical catalogue IDs, others are
explicitly labelled broader institutional originals.

## Upload to the existing GitHub repository

1. **Make a backup first:** in GitHub, download the current repository ZIP (Code
   > Download ZIP), or create an update branch. Your current repository could
   have changed since the supplied snapshot.
2. Download and **extract** the ZIP containing this guide. Do **not** upload the
   ZIP itself. Inside are the two canonically named replacement documents, a new
   report, `index.html`, and folders `scripts/` and `research-updates/`.
3. In the existing `world-radar-main` repository root (not inside a new
   `world-radar-main/` directory), use **Add file > Upload files**. Drag the
   extracted **contents** (including both folders) onto GitHub. File paths must
   stay exactly as shown in the manifest below. Same-named files are changes to
   tracked files, not new duplicate names.
4. Review the proposed changes and commit to a **new branch / pull request**
   first if possible, especially if your live project has moved on since the
   November 2 snapshot. Merge only after checking the filenames and diff.
5. If your browser does not preserve subfolders, upload the four top-level
   files from the root, then navigate to `scripts/` and upload its two Python
   files, then to `research-updates/` and upload the JSON. **Do not flatten the
   Python files into the repository root.**
6. GitHub Pages should redeploy on a committed `index.html`/document change
   through the project's existing `publish-website.yml` workflow. Verify that
   the homepage shows the new long-report download and existing download links
   still work. GitHub web uploads are limited to 25 MiB per file; all files in
   this update are smaller.

## Files and exact destinations

| Repository path | Effect |
| --- | --- |
| `VV-FUTURES-REVIEWED-FINDINGS.docx` | **REPLACES** the old Word output with the longer 83-page version; original paragraphs are an identical prefix. |
| `VV-FUTURES-ALL-CLAIMS-AND-SOURCES.xlsx` | **REPLACES** old Excel output with the enriched 22-sheet version; every cell on the original 14 tabs is identical. |
| `VV-FUTURES-WHAT-BECAME-OF-THE-FUTURE.docx` | **ADDS** the long narrative investigation. |
| `index.html` | **UPDATES** existing homepage to link to the long report. |
| `research-updates/trajectory-research-2026-11-02.json` | **ADDS** reusable case descriptions, 40 milestones, 37 source records and 16 qualified relationships. |
| `scripts/trajectory_extension.py` | **ADDS** functions to reconstruct the research additions when rebuilding the Word and Excel outputs. |
| `scripts/present_outputs.py` | **UPDATES** the existing manual generator to load the compressed historical database, retain older custom Excel tabs, and append the research extension. |
| `scripts/check_trajectory_update.py` | **ADDS** a standard-library consistency check for the installed update. |

## Homepage numbers (index.html)

The homepage now explicitly displays the *separate* 2 November 2026 research extension:
**12 new trajectories, 40 dated milestones, 37 source records, 16 qualified connections**.
These counts are initially shown as static fallbacks and then read from
`research-updates/trajectory-research-2026-11-02.json` in the browser.

The existing headline numbers **507 historical claims / 63 checked LLM accounts /
12 older research notes** are not changed, because they describe different
source datasets. The browser continues to update these older numbers from
`observatory-data.json`, `reviewed-findings.json`, and
`radar2-research-notes.json`, respectively. The 12 new trajectories are
**not** automatically included in these existing research-account totals.

For the upload, keep `index.html` and the three Word/Excel deliverables
at the repository root. Put the three `.py` files under `scripts/`
and the JSON under `research-updates/`. Do not merge the research JSON
into the unrelated `reviewed-findings.json` file.

## Important safeguards

- This is not a file containing a command that automatically uploads to GitHub;
  you must commit it in your own repository.
- It does **not** change `reviewed-findings.json`, `radar2-research-notes.json`,
  historical source excerpts, scanner schedules, or automatic research policies.
- The existing Scanner workflows do **not** currently call `present_outputs.py`;
  these revised canonical files remain committed unless a separate process
  replaces them. A future **manual** call to `scripts/present_outputs.py` will
  regenerate 12 trajectories from the committed JSON instead of losing them.
- Manual regeneration requires `python-docx` and the existing `artifact_tool`
  environment. The scheduled GitHub workflows have **not** been changed to run
  that generator, because the project's current Actions requirements do not
  provide `artifact_tool`. Do not run the generator inside Actions without
  arranging that dependency.
- The manual generator reconstructs the new eight research tabs from JSON and
  keeps older supplementary research tab **values** from the previous Excel
  file, although it may not retain every custom style/layout on those older
  supplementary tabs when rebuilding. The shipped updated Excel retains their
  original styles; no regeneration is needed for installation.
- Always inspect the `VV-FUTURES-REVIEWED-FINDINGS.docx` and Excel output after a
  future rebuild before committing it. A rebuild changes file bytes and may
  change presentation even when the research data is the same.
- If the repository has new editorial reviews since the supplied snapshot,
  replacing the output document could hide newer work. Incorporate those new
  reviews first or use the source-of-truth JSON plus generator on an up-to-date
  working copy, rather than overwriting someone else's subsequent additions.

## Optional local checks

From the root of the repository after upload:

```sh
python scripts/check_trajectory_update.py
```

The checker only reads files. It reports whether the research JSON is present,
the 12/40/37/16 records are consistent, the expected documents and workbook
exist, and the long report is linked from the homepage.

**Research cut-off:** 2 November 2026. Source URLs are recorded in the JSON,
Word report and Excel. The 63 existing LLM-reviewed accounts are treated as
completed checks, with their original wording and metadata preserved.
