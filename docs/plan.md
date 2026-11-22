# Plan: Judging the Journey

This is the agreed plan for rebuilding this project from scratch as an interactive demo for mark-bugden.github.io. It was settled with Mark on 2026-11-22, after a feasibility check against the live data sources and before any new code was written. The site's requirements are in `site-contract-soudai.md`, which lives outside this repo (in Mark's `personal_website` folder), and in the [demo-kit README](https://github.com/Mark-Bugden/demo-kit#readme). This document covers what we're building on top of them.

It is also the handover document. Any agent should be able to read it, find the first unchecked box under "Milestones", and carry on from there. See "Working on this plan" first.

## The goal

The demo shows how civil cases move through Czech district courts, and where they pile up. A visitor:

1. opens on the journey of a civil case, from filing to a final decision: the routes cases take, how many take each one, and how long each step lasts
2. picks a court and compares its journey with the national one
3. switches to a map of the district courts, coloured by cases filed per year, backlog or typical time to a decision
4. sees how close an estimate of a court's caseload, made from its published decisions alone (the German tank method), gets to the exact count.

The project is descriptive. It makes no predictions about individual cases, makes no claims about why courts differ, and isn't legal advice.

## Working on this plan

`CLAUDE.md` holds the standing rules for agents in this repo, and they win if they ever disagree with this section.

1. **Read this plan to the end**, then check the state of the repo and of other sessions: `git status`, `git log --oneline -10`, `gh pr list`, and the site's `scripts/status.sh` (in the site clone, `Mark-Bugden.github.io`). Other sessions work in this repo, the site, demo-kit and the other project repos at the same time. An open PR, or a branch with commits that aren't in main, usually means someone is working there.
2. **Find where things stand.** The first milestone with an unchecked box is the current one. The notes under each checked box say what was done and found. For the data stages, `uv run soudai status` (built in step 2) reports each stage's progress from the cache, and every stage resumes where it stopped.
3. **Record as you go.** When you finish something, tick its box and add sub-bullets with the result: counts, dates, sizes, decisions, surprises. Put decisions made with Mark here with their date. Settle or add items under "Open questions". Do this in the same PR as the work.
4. **One PR per change, and merging it puts it live.** Never push to `main` and never create tags. A PR that changes anything in `demo/` (other than tests and Markdown) bumps `version` in `demo/package.json`, or CI fails. Before opening a PR, run CI's checks locally, because every failed run emails Mark. `CLAUDE.md` lists them: today `npm run build` and `npx demo-kit validate dist/` in `demo/`; from step 1 also `uv run pytest`, and `npm test` once the demo has tests.
5. **Long runs** (the scrapes in steps 3–5) run in the background and log to `data/raw/logs/`. Never delete the cache. Never run two scrapers at once: the 1 request per second limit is for the whole project, not per process.
6. **Copy.** Mark writes the English copy himself: the manifest's tagline, summary and `about`, and the write-up. Agents may draft it in `docs/writeup.md` for him to edit. Don't write new prose about Mark or his work.
7. **Other repos.** Read the sibling repos and the site freely, but don't change them. Tell Mark what the site needs (see "For Mark, on the site").

## What changes from the old project

| Old | New | Why |
| --- | --- | --- |
| Two repos: `SOUDAI_data_scraping` and this one | One repo, `soudai`, written from scratch | The old code is a reference only. It stays in this repo's history and in the public scraping repo. |
| Poetry | uv | The same as the other project repos. |
| Sample: published decisions from rozhodnuti.justice.cz | A random sample of all filed cases, drawn from each senate's docket on infosoud | Published decisions only cover decided cases, and publication volume swings by year (797 in 2020, 181,861 in 2022, 61,203 in 2024). Published decisions are still used, for the German tank estimate and to find senates. |
| Infosoud's HTML pages (`infosoud.justice.cz/InfoSoud/public/search.do`) | Infosoud's JSON API at `infosoud.gov.cz/api/v1` | The old site redirects every URL to the new app's front page and drops the query, so the old scraper no longer works. |
| Target: days from filing to the published decision, capped at 5 years, open cases dropped | Each case's full timeline. Waits are estimated with censoring (Kaplan–Meier), with no cap | The cap and dropping open cases both bias durations downwards. |
| Features: keywords and cited statutes from the decision | Not used | They're written when the case ends, so they leak the outcome. The project is descriptive now anyway. |
| Model: a PyTorch embedding MLP predicting days | No predictive model. Exact intake counts, German tank estimates, Kaplan–Meier waits and Little's law | Mark's scope decision on 2026-11-22. |
| Judges as a feature (`autor`) | Not analysed. Judges' names never leave the raw cache | See "Data". |
| Title "Judging the Journey" | Kept, with the slug `soudai` | The journey is now literally what the demo shows. |

## Data

### Sources (verified 2026-11-22)

The feasibility check used throwaway scripts outside the repo. Everything it established is recorded here.

**rozhodnuti.justice.cz open data.** Anonymised published decisions, as JSON with no key and no captcha.
- `GET https://rozhodnuti.justice.cz/api/opendata` lists the years, `/{year}` the months, `/{year}/{month}` the days (each with `pocet`, its count), and `/{year}/{month}/{day}?page={n}` the decisions, 100 to a page, from page 0. Each page carries `totalPages` and `totalElements`.
- Published so far, by year of publication: 2020: 797, 2021: 150,939, 2022: 181,861, 2023: 85,462, 2024: 61,203, 2025: 71,514, 2026: 64,682 (to 2026-11-22). That's 616,458 in all. A full listing takes about 7–9k requests, counting the day index, which is 2–3 hours at 1 request a second.
- Each item has `jednaciCislo` (e.g. `15 C 384/2022-15`), `soud` (e.g. `Okresní soud v Náchodě`), `autor` (the judge), `ecli`, `predmetRizeni` (the subject, often with the amount claimed, e.g. `O zaplacení 25 455 Kč s příslušenstvím`), `datumVydani`, `datumZverejneni`, `klicovaSlova`, `zminenaUstanoveni` and `odkaz` (a link to the full text, which we never fetch).
- In a sample of six whole days (2,849 decisions), 96.8% were civil first-instance cases at district-level courts, register `C`. All 2,849 case numbers parsed with `^(\d+)\s+([A-Za-z]+)\s+(\d+)/(\d{4})(?:-(\d+))?$`.

**infosoud.gov.cz.** The courts' public case-tracking service, now an Angular app. Its API is undocumented and can change without notice.
- Base: `https://infosoud.gov.cz/api/v1`. No captcha. Responses took about 50 ms. They hold no party names.
- `GET organizace/lov` lists the regional, municipal and high courts with codes, e.g. `KSVYCHK` (Krajský soud Hradec Králové) and `MSPHAAB` (Městský soud Praha). `GET organizace/podrizene/lov?idOrganizace=KSVYCHK` lists its district courts, e.g. `OSVYCNA` (Okresní soud Náchod). `GET spisova-znacka/druh/lovkod?typ=rizeni` lists the registers.
- **Case lookup:** `POST rizeni/vyhledej` with the JSON body `{"druhOrganizace": "KSVYCHK", "okresniSoud": "OSVYCNA", "druhVeci": "C", "cisloSenatu": 15, "bcVec": 384, "rocnik": 2022}`.
  - Found: HTTP 200 with `cislo`, `druh`, `rocnik`, `bcVec`, `organizace`, `nadrizenaOrganizace`, `typOrganizace`, `stav` (status), `stavDatum`, `udalosti` (events), `navazneVeci` (linked cases) and `platneK` (data valid as of).
  - Each event has `udalost` (a code), `datum`, `poradi`, `zruseno` (cancelled) and `jednani` (hearings). The list isn't in date order, so sort by `datum`, then `poradi`.
  - Not found: HTTP 400 with `message` starting `RIZENI_0000`, e.g. `RIZENI_0000#15 C 9999 / 2022#Okresní soud Náchod`. Any other 400 (the app's validation codes are `RIZENI_VALIDATION_000x`) means our request is wrong.
- `POST udalost/vyhledej` exists, but returns less than `rizeni/vyhledej`. Don't use it.
- The app calls `GET env` for the backend version (`backendVerze`). Every run that uses infosoud records it (2.0.0.10 on 2026-11-22), so an API change can be spotted. It also returns `prostredi` (`MSP_PROD`).
- **Event codes seen:** `ZAHAJ_RIZ`, `NAR_JED`, `VYD_ROZH`, `ST_VEC_VYR`, `ST_VEC_PUK`, `ST_VEC_ODS`, `ODVOLANI`, `ODES_SPIS`, `VRAC_SPIS`, `POD_OP_PR` and `VYR_OP_PR`.
  - The English glosses are in `reference/events.csv` (step 2), with the app's Czech labels for all 28 codes it knows.
  - The app's JS bundle holds the Czech labels and tooltips. One set is for the Supreme Court (`ns`), where `ZAHAJ_RIZ` reads "Došlo Nejvyššímu soudu", and one is for the other courts. Take the glosses from the latter.
- **Statuses seen:** `nevyřízená věc` (open), `Vyřízená věc - po vyhlášení konečného rozhodnutí`, `Pravomocná věc - stav věci se změnil na pravomocnou po nabytí právní moci všech výroků či vůči všem osobám, o nichž bylo meritorně rozhodováno` (whose `stavDatum` is null) and `Odškrtnutá - evidenčně ukončená věc`. They're in `reference/events.csv` too.

**Case numbers.** A case number is `senát rejstřík pořadové-číslo/ročník`, with `-n` added for a document within the case.
- The sequence number restarts each year **for each senate**, not for the whole court. The six-day sample had 70 (court, year, number) triples used by more than one senate.
- In the one senate tested, the docket had no gaps: 12 random numbers below the top all existed, and the numbers just above it didn't. Okresní soud Náchod, senate 15, register C had 396 cases in 2022, 423 in 2025 and 308 in 2026 (to 2026-11-22). So a binary search of about 10 requests gives a senate's exact yearly intake. Step 4 checks this everywhere.
- Open cases are listed: 4 of 12 sampled 2026 cases in that senate were `nevyřízená věc`.
- Some senate numbers are above 100 (112 was seen at Okresní soud Ústí nad Orlicí, 2022).

**Pacing.** About 230 requests, spaced 1.5–3 s apart, drew two connection resets (each cleared by a 30 s pause) and no 429s. Faster rates are untested.

### Decisions

- **Scope.** District-level courts (okresní and obvodní soudy and Městský soud v Brně: 86, confirmed in step 2), register `C`, cases filed 2020–2025 (decided 2026-11-22). Městský soud v Praze is a regional-level court and is out of scope.
- **Pacing.** 1 request a second across the whole project (decided 2026-11-22). On a connection error, wait 30, 60, then 90 s and retry. On any 429, or more than 5 failures in a row, stop the run and record it here. If 1 s draws 429s or keeps resetting, go back to 3 s and tell Mark.
- **Identification.** User-Agent `soudai/<version> (+https://github.com/Mark-Bugden/soudai)`.
- **Cache.** Every response, including not-found responses, goes into a SQLite cache at `data/raw/cache.sqlite`: request key, URL, body, status, the response gzipped, and the fetch time. Nothing that's cached is fetched again unless a stage asks to refresh it. The cache is the snapshot, so it's never deleted, and it's never committed.
- **Privacy.**
  - Infosoud responses hold no names.
  - rozhodnuti items name the judge (`autor`). The parse step drops it, so no derived table, export or demo holds judges' names.
  - Full texts of decisions are never fetched.
- **Snapshot.** Each case keeps its `platneK`. The snapshot date, i.e. the end of the timeline scrape, goes into the export, "How this works" and the write-up. Censoring is at each case's `platneK`.
- **What's committed.** `reference/` (hand-checked tables) and `data/derived/` (tables from the parse steps, with no judges' names). Any derived file over about 10 MB stays out of git (see "Open questions").

### Stages

| Stage | Input | Output | Rough cost at 1 req/s |
| --- | --- | --- | --- |
| Courts | infosoud `organizace/*`, the old `references/court_map.yaml` in `Mark-Bugden/SOUDAI_data_scraping` as a seed | `reference/courts.csv` | < 100 requests |
| Events | infosoud's JS bundle | `reference/events.csv` | < 150 requests (static files) |
| Published decisions | rozhodnuti listing | `data/derived/decisions.parquet` | 7–9k requests, 2–3 h |
| Senates | decisions, probes of number 1 | `data/derived/senates.csv` | ~20k requests, ~6 h (estimate) |
| Intake | senates, binary search | `data/derived/intake.csv` | ~10–15 requests per senate-year; ~6k senate-years if courts average 12 civil senates: ~75k requests, ~21 h |
| Timelines | intake, stratified sample | `data/derived/cases.parquet`, `events.parquet` | 60 per court-year: ~31k requests, ~9 h |

The estimates for the senate and intake stages rest on a guess of about 12 civil senates per court. Replace them with real numbers as the stages run.

### Checks (pytest)

The tests never touch the network. They run on saved real responses in `tests/fixtures/`: a found case, a not-found 400 and a listing page.
- Case numbers parse, and the regex covers every case number in the decisions table.
- Every court in `decisions` maps to a row of `reference/courts.csv`.
- The binary search finds the top of a fake docket, including dockets of 0 and 1 cases.
- Every sampled case has `ZAHAJ_RIZ`, and its date falls in the case's year. (This won't hold as written: see "Filing date and case year" under "Open questions".)
- No judge's name appears anywhere in `data/derived/` or the export.
- The German tank estimator and its interval match a brute-force simulation.
- The weighted Kaplan–Meier matches hand-worked cases.
- The export matches its schema and stays under its size budget.

## Methods

### Exact intake

For each court, senate and filing year, the highest existing number is the number of cases filed. Find it with an exponential search from a hint (the highest published number, or 16), then a binary search. Then probe the top + 1 to + 3 and the top + 10 and + 25, to catch islands above a gap. To check there are no gaps, probe 3 random numbers below the top in every senate-year. If any probe comes back missing, stop and investigate before trusting the counts.

A court's intake for a year is the sum over its senates. Finding the senates: the candidates for a court and year are the senates seen in its published decisions (any year), plus 1 to the highest seen + 10. A senate exists in a year if its case number 1 does. For a few courts, sweep senates 1–250 to check that the rule misses nothing.

### The German tank estimate

From published decisions alone: for a senate-year with k distinct published case numbers and highest number m, estimate N̂ = m(1 + 1/k) − 1. Count distinct cases, not decisions, since one case can have several published documents.
- **Interval.** P(max ≤ m | N) = C(m, k) / C(N, k), inverted for a one-sided 95% upper bound. The lower bound is m.
- **Court totals.** Sum the senates' estimates, and get the court's interval by simulation.
- **Missed senates.** Senate-years with no published decisions contribute nothing, so court totals undercount. Report how much.
- **The point.** The estimate assumes published case numbers are a uniform random sample of 1..N. They aren't: only decided cases are published, so in recent years high numbers are under-represented. The comparison with the exact counts, by filing year, is the finding.

### The journey

- **Stage model.** Define it from `reference/events.csv` and about 200 sampled timelines, and write it down here before computing anything. The working model: filing → hearing scheduled → decision → disposed → legally final, with the appeal loop as a branch. Cancelled events (`zruseno`) are dropped. Repeated hearings count once on the map, and their number is kept.
- **Weights.** The sample is stratified by court and year, so each case carries the weight intake / sample size. Every share and curve is weighted.
- **Edges.** The weighted share of cases taking each transition, and the wait on it from a weighted Kaplan–Meier fit (median and interquartile range). A case that hasn't reached its next event is censored at its `platneK`.
- **Curves.** Time from filing to disposal, and to legal force, as "share still open after t months", per court and nationally.
- **Variants.** The most common full paths, with their shares.

### Backlog

Little's law: backlog L = λW, with λ the yearly intake (exact) and W the mean time from filing to disposal. Censoring makes W's mean hard. Use a restricted mean with the horizon stated, and lean on the early filing years, which are almost all closed.

As a check, count directly from the sample the weighted number of cases open on 31 December of each year. That count misses cases filed before 2020 that are still open, so it's a lower bound (see "Open questions").

Little's law also assumes a steady state, which 2020 wasn't. Say so wherever backlog is shown.

### External check

Compare national and court intake with the Ministry of Justice's official statistics. The source was found on 2026-11-22 by web research, without touching rozhodnuti or infosoud.

- **The report to compare against: S_AS_40, "Přehled o vyřizování agendy C u OS" (Tabulka č. 40).**
  - **Where:** InfoData's reports form at https://cslav.justice.cz/InfoData/prehledy-agend.html. POST `sestavaQry=S_AS_40`, `obdobiOdQry=01.01.YYYY`, `obdobiDoQry=31.12.YYYY` and `jenVykCeleObdQry=on` with a session cookie. The result links to `/InfoData/servlet/FileServlet`.
  - **Coverage:** one file per year for register C, with all 86 courts (Městský soud v Brně appears as "Brno"), kraj totals and a national total. The portal says the data go back to 2008.
  - **Format:** XML Spreadsheet 2003, PDF or HTML.
  - **Columns:** nápad, obživlo, vyřízeno, nevyřízeno by age, and pravomocně/nepravomocně.
  - **Editions seen:** the 2020, 2022 and 2025 files, computed on 2021-01-25, 2023-01-15 and 2026-01-08.
  - **National nápad, register C:** 286,801 in 2020, 295,311 in 2022 and 272,434 in 2025.
- **The breakdown: V(MS)-114, "Výkaz o pohybu agendy rejstříku C u okresních soudů".**
  - At https://cslav.justice.cz/InfoData/vykazy-soudu-a-statnich-zastupitelstvi.html, one file per court and period, keyed by infosoud's own court codes.
  - At Náchod in 2022 it gives "celkem zapsáno do rejstříku" 2,327 and "celkem nový nápad" 2,309 (S_AS_40's figure). Of those, 1,757 were transferred from EPR (electronic payment orders) and 0 from Ro/ERo. 108 cases revived (obživlo).
  - Nobody has explained the 18 between "zapsáno" and "nápad" yet. A senate's top number may match "zapsáno" rather than "nápad", so compare with both.
- **Only as a cross-check: the annual report's appendix, `Data_soudy_YYYY.xlsm`.** These run from 2018 to 2025 and are listed at https://msp.gov.cz/web/msp/statisticke-udaje-z-oblasti-justice. Their civil sheet gives only "Obživa+nápad" (Náchod 2022: 2,417 = 2,309 + 108).
- **Not suitable:** the Ministry's Power BI dashboards, which count finished cases. statistika.justice.cz didn't resolve, and data.gov.cz has no dataset.
- **Definitions,** from the Ministry's glossary (https://msp.gov.cz/web/msp/statisticke-udaje-z-oblasti-justice/-/clanek/slovnik-pojmu):
  - nápad is "počet nově zapsaných věcí do rejstříku za určité období", the cases newly entered in the register in the period, which is what our counts are.
  - Cases transferred in from EPR, Ro or ERo count as nápad.
  - obživa is a disposed case whose proceedings resume, mostly after an appeal court quashes the decision. It keeps its number, so it isn't intake.
- **Licence:** none is stated on either site. Cite "Ministerstvo spravedlnosti ČR, InfoData".

## The experience

| | |
| --- | --- |
| Views | Journey (opening) and Courts, switched with buttons at the top of the controls rail. The rail shows only the controls the current view uses. |
| Journey | A flow diagram of the stages a civil case passes through, with the appeal loop as a side branch. Each edge's thickness is the share of cases that take it, and its label is the median wait. Hovering an edge gives its share, median and interquartile range. |
| Time to disposal | Beside the diagram: the share of cases still open t months after filing, for the selected court against all courts. |
| Court selector | All courts, or one court, with search by name. Search ignores diacritics, so "Decin" finds Děčín. The selection is shared by both views. |
| Courts | A map of the district courts (see "Open questions" for areas or seats), coloured by the chosen measure: cases filed per year, backlog, or median time to disposal. Clicking a court selects it. |
| Court panel | For the selected court: exact intake by year beside the German tank estimate and its interval, and its backlog. |
| Tank explainer | Stretch goal: reveal a court's published case numbers a few at a time and watch the estimate close in on the exact count. |
| Status line | What's selected, with its headline numbers. |
| How this works | Sources and snapshot date, what's counted (district courts, register C, filed 2020–2025), the methods in brief, and that it isn't legal advice. |
| Language | The interface is in English. Court names stay in Czech. Event names use the English glosses from `reference/events.csv`. |

## Look

- **Kit.** Use the latest demo-kit release when demo work starts (v0.5.0 on 2026-11-22; check with `git ls-remote --tags https://github.com/Mark-Bugden/demo-kit.git`). Change the tag in `demo/package.json` and `kitVersion` in the manifest together.
- **Colours.** Use the kit's tokens, as doctor-who-ratings does (its `docs/plan.md`, "Look", gives the contrast figures):
  - the spectrum (`--chart-spectrum-1` to `-4`, through the kit's `ramp()`) for the map's sequential measures
  - the accent for the selected court and its journey
  - the curve colour for context, such as the national comparison
  - no local colours.
- **Fit the window.** Size the stage with `var(--dk-fit-height, 100dvh)`, as doctor-who-ratings and zombie-outbreak do.
- **Motion.** None under `prefers-reduced-motion`.
- **Stills.** `scripts/stills.py` renders them from the built demo with Playwright, in both themes, like doctor-who-ratings' script. Don't reuse the stub's stills.

## Repo layout (target)

```
demo/                          the site bundle, built with demo-kit (see the site contract)
  src/main.js                  frame, controls, view switching and shared state
  src/views/                   journey, courts
  src/tank.js                  German tank estimator, ported from Python (only if the demo recomputes it)
  public/data/soudai.json      written by the export, and committed
  test/                        node:test, including fixtures from the Python reference
src/soudai/
  http.py                      cached, paced client (SQLite cache, 1 req/s, backoff, User-Agent)
  rozhodnuti.py                open-data listing
  infosoud.py                  courts and case lookup
  courts.py                    court table and name mapping
  senates.py                   senate discovery
  intake.py                    binary search and gap checks
  sample.py                    the stratified timeline sample
  events.py                    event log and stage model
  tank.py                      German tank estimates and intervals
  survival.py                  weighted Kaplan–Meier
  backlog.py                   Little's law and the direct count
  export.py                    writes demo/public/data/ and the JS fixtures
  status.py                    progress of each stage, from the cache and derived tables
  cli.py                       `uv run soudai <stage>`: courts, events, decisions, senates, intake, sample, analyse, export, status
reference/                     courts.csv, events.csv, sources.json (hand-checked, committed)
data/raw/                      cache.sqlite and logs (gitignored)
data/derived/                  parsed tables, no judges' names (committed while small)
tests/                         pytest, offline, with saved responses in tests/fixtures/
scripts/stills.py              renders the stills
docs/                          this plan and the draft write-up
pyproject.toml, uv.lock        a uv project
```

- **CI.** The site contract's `.github/workflows/demo.yml` stays exactly as it is. The tests (pytest, node:test, and the check of the JS against the Python) go in a separate `tests.yml`, as in doctor-who-ratings.

## Milestones

### 0. Feasibility check (done 2026-11-22)
- [x] rozhodnuti's open-data API works as before. Listing is cheap, and the published set is almost all district-court `C` cases (see "Sources").
- [x] Infosoud moved to infosoud.gov.cz, and its JSON API returns a case's full timeline in one call, with a clean not-found response.
- [x] Case numbers run per senate. One senate's docket had no gaps, so exact intake counts are possible, and open cases are listed.
- [x] Decisions with Mark: the scope above, filing years 2020–2025, and 1 request a second.

### 1. Fresh start (PR, 2026-11-22)
- [x] Delete the old `src/`, `scripts/`, `notebooks/` and Poetry `pyproject.toml`. They stay in git history.
- [x] Create the uv project: Python ≥ 3.12, package `src/soudai`, with pandas, pyarrow, numpy, scipy, requests and lifelines (or justify another survival library), plus pytest and ruff for development. Commit `uv.lock`.
  - Built with `uv_build`, like the sibling repos. The lock resolved pandas 2.3.3, numpy 2.5.5, scipy 1.18.1, pyarrow 26.0.1, requests 2.34.2 and lifelines 0.30.3.
  - lifelines it is. Its `KaplanMeierFitter` takes `weights`, and a fit on six hand-worked weighted cases gave the expected curve. It caps pandas below 3.0, which is why pandas is on 2.3.
  - Ruff is configured in `pyproject.toml` (line length 110, rules E, F, W, I, B, UP) but isn't in CI: run `uv run ruff check` and `uv run ruff format --check` before a PR.
  - `src/soudai/paths.py` holds where the pipeline reads and writes, as in doctor-who-ratings.
- [x] `.gitignore`: ignore `data/raw/`, but not `data/derived/` or `reference/`.
  - The old rule was a bare `data/`, which would also have ignored `demo/public/data/`. The new one is anchored, `/data/raw/`. `tests/test_repo.py` checks it with `git check-ignore`, using the paths in `paths.py`. It's the only test so far, and pytest fails a run that collects no tests.
- [x] Extend `CLAUDE.md` (added in #3): point it to this plan, and add `uv run pytest` to its list of CI checks (and `npm test` once the demo has tests).
- [x] Rewrite `README.md`: what the project is, its status, how to run each stage, and the data sources. Mark edits the wording.
  - The stages are listed with the milestone that builds each one, since none runs yet.
- [x] Add `tests.yml` running pytest. node:test joins it when the demo has tests.
- [x] Commit this plan (its own PR, 2026-11-22).
- The demo isn't touched, so the stub stays live and no version bump is needed.

### 2. Scraper foundations (PR, 2026-11-22)
- [x] `http.py`: the SQLite cache, the project-wide 1 request a second, the backoff and stop rules, the User-Agent and a run log.
  - The cache has three tables: `responses` (key, method, URL, canonical JSON body, status, gzipped response, content type, fetch time, run), `runs` (stage, version, start and end, outcome, backend version, requests, cache hits, failures) and `pacing`. It's in WAL mode, so `soudai status` can read during a run.
  - Every response except a 5xx, a 408, a 429 or a 403 is cached, including not-found 400s. The key is a hash of the method, URL and body, with the body's keys sorted.
  - A cached response that doesn't parse (an outage page cached by mistake, say) isn't trusted. `http.parsed` fetches it again, once, so a bad answer can't block every later run. The same goes for a cached lookup that came back `RIZENI_0001`.
  - **Pacing is project-wide.** The time of the last request lives in the cache and is claimed inside `BEGIN IMMEDIATE`, so a second process queues behind the first instead of doubling the rate. Checked with two processes sharing a cache: all 9 gaps between their 10 requests were 1.000–1.001 s. Cached responses skip the pacing.
  - **Backoff, as read here:** a connection error, a timeout, a reset partway through a response, a 408 or a 5xx counts as a failure. The waits after the 1st, 2nd and 3rd failure in a row are 30, 60 and 90 s, and then 90 s again. The 6th failure in a row raises `StopRun`, and so does any 429. A success resets the count. A 403 stops the run too: it's the likeliest sign of being blocked.
  - Each run logs every request to `data/raw/logs/<stage>-<start>.log`, and progress to the console.
  - **Live pacing so far:** 237 requests at 1 a second on 2026-11-22, with 2 connection resets (both on rozhodnuti, each cleared by one 30 s wait) and no 429s.
- [x] `infosoud.py`: court lists and case lookup, returning found / not found / error, with anything else raising. Record `GET env`'s backend version with each run.
  - The app's messages settle what "error" means: `RIZENI_0000` is not found, and `RIZENI_0001` is "an unexpected error occurred while loading the case, repeat the query". That's the error. An error is never trusted from the cache: `lookup` fetches it again once. The `RIZENI_VALIDATION_000x` codes, `ORGANIZACE_0000`, other statuses, HTML and found cases missing fields raise `UnexpectedResponse`.
  - It also finds the bundle chunk with the event labels (breadth-first from `main-*.js`, stopping at the first hit) and parses the labels and messages out of the JS object literal.
  - In 54 cases at Náchod, senate 15, `jednani` was always empty, and cancelled events (`zruseno`) came in pairs: a hearing scheduled and its cancellation.
  - **13 of those 54 cases were filed before their case number's year.** Their `ZAHAJ_RIZ` falls in the year before: 11 of the first 12 numbers of 2022 were filed between 2021-09-01 and 2021-12-16, and 2 of the 14 sampled 2025 cases were filed in 2024. See "Filing date and case year" under "Open questions".
- [x] `rozhodnuti.py`: the year/month/day index and the day pages.
  - The month index lists only the days with decisions, weekends included when there are any. The case-number regex is here too, as `parse_case_number`. It also matched `11 CO 310/2022-195` (the register in capitals) and numbers with no document part, `17 C 291/2022`.
  - Six whole days (3,403 decisions) included 13 whose `soud` is `(nezadán)`, "not given". Step 3 has to count them and leave them out.
- [x] `reference/courts.csv`: every district-level court with its infosoud code, regional code, rozhodnuti name (they differ: "Okresní soud v Náchodě" against "Okresní soud Náchod") and the area it serves. Seed it from the old court map, and check it by hand. Record the count.
  - **86 courts**: 75 okresní soudy, the 10 obvodní soudy and Městský soud v Brně. Krajský soud Brno has 14, České Budějovice 8, Hradec Králové 11, Ostrava 11, Plzeň 10, Praha 12, Ústí nad Labem 10, Městský soud Praha 10, and the high courts none.
  - The court map is read at a fixed commit. Three courts have a second rozhodnuti name, for a branch: Bruntál (Krnov), Karviná (Havířov) and Vsetín (Valašské Meziřičí). So `rozhodnuti_names` holds several, separated by `; `, 89 in all.
  - Hand-checked: the areas against the 76 okresy and Prague's 10 districts. Every district-level name in six whole days of decisions maps to one court, and 85 of 86 courts appeared. Hodonín's name is unconfirmed until step 3. `reference/README.md` has the details.
- [x] `reference/events.csv`: each event code with its Czech label and tooltip from the app's bundle (the non-Supreme-Court set) and an English gloss. Add the status values. Mark checks the glosses.
  - 28 event codes from `chunk-KZJVN2ZT.js`, each with label, tooltip and description, and 4 statuses. The 54 timelines fetched in this step used 9 of them: `ZAHAJ_RIZ`, `NAR_JED`, `ZRUS_JED`, `VYD_ROZH`, `ST_VEC_VYR`, `ST_VEC_PUK`, `ST_VEC_ODS`, `ST_VEC_PRE` and `ST_VEC_UPR`. The feasibility check's other codes (`ODVOLANI`, `ODES_SPIS`, `VRAC_SPIS`, `POD_OP_PR`, `VYR_OP_PR`) are all in the bundle.
  - **For Mark:** the glosses are short labels for the demo, e.g. `ZAHAJ_RIZ` "Case filed", `ST_VEC_VYR` "Case disposed", `ST_VEC_PUK` "Legally final", `ST_VEC_ODS` "Case closed in the register". Edit them in the CSV: `soudai events` keeps them.
- [x] `reference/sources.json`: endpoints, the date checked and the backend version.
- [x] `soudai status`, and the offline tests.
  - `uv run soudai <stage>` has `courts` (`--write`), `events` and `status`. `status` reports the cache, the last runs, the day pages cached against the cached month indexes, case lookups by the case number's year and by outcome (found, not found, error, or unexpected), the reference tables and the derived tables. It never creates the cache.
  - 98 tests, all offline. They run on real responses in `tests/fixtures/`: 7 cases (found, not found, open, cancelled hearing, suspended, disposed, legally final), the court lists, the env, the labels chunk (cut to its resource bundle), and rozhodnuti's indexes and a day page with every `autor` replaced by `REDACTED`. The client's tests use a fake session and clock, so none of them waits.
  - The Windows console's code page can't print č or ř, so the CLI switches stdout and stderr to UTF-8.
  - A review of the code turned up two minor bugs, both fixed: `status` lumped every 400 together, and a test of 5xx caching couldn't fail. It also turned up the edge cases above (cached outage pages, 403s and 408s, malformed JSON, numpy ints in a request body), and the filing-year finding.

### 3. Published decisions (run, then PR)
- [ ] List every decision from 2020 to the snapshot date.
- [ ] Parse to `data/derived/decisions.parquet`: court code, senate, register, number, case year, document number, decision date, publication date and `predmetRizeni`. Drop `autor`, keywords and statutes.
- [ ] Record: total decisions, requests, run time, resets, the split by court level and register, case numbers that didn't parse, and courts that didn't map.

### 4. Senates and exact intake (run, then PR)
- [ ] Find each court's senates for each filing year (see "Exact intake"), including the wide sweep for a few courts. Record the number of active senate-years and the requests used.
- [ ] Find each senate-year's highest number, with the probes above it and the 3 gap probes below it.
- [ ] Write `data/derived/intake.csv` (court, senate, year, count, probes used, flags), and record totals by court-year and nationally. If any gap turned up, stop: record it here and settle it with Mark before step 5.

### 5. Timeline sample (run, then PR)
- [ ] Draw 60 cases per court-year, uniformly over the court-year's docket (all its senates' numbers together), with a recorded seed. Each case's weight is the court-year's intake / 60.
- [ ] Parse to `data/derived/cases.parquet` (case, court, filing date, status, status date, `platneK`, weight) and `data/derived/events.parquet` (case, code, date, `poradi`, cancelled).
- [ ] Check that every case has a filing event in its case year and that events order sensibly, and record the share still open by filing year.

### 6. Analysis (PR)
- [ ] Settle the stage model (see "The journey") and write it here.
- [ ] Journey: weighted transition shares, Kaplan–Meier waits and curves, and the top variants, per court and nationally.
- [ ] Exact intake by court-year and nationally, and the external check.
- [ ] German tank estimates and intervals, compared with the exact counts by filing year, plus the undercount from senates with no published decisions.
- [ ] Backlog by Little's law, against the direct count.
- [ ] A Python reference and fixtures for any maths the demo recomputes.
- [ ] Record the headline figures here, and draft notes for the write-up in `docs/writeup.md`.

### 7. Courts view: release status `in-progress`
- [ ] Move the demo to the latest demo-kit (see "Look") and bump `version`.
- [ ] Settle the map geometry (see "Open questions") and record its source and licence.
- [ ] Export `demo/public/data/soudai.json` (aim for under 500 KB; the bundle must stay under 2 MB).
- [ ] The frame, the court selector, the Courts view and the court panel, the status line and "How this works". Test the JS against the Python fixtures.
- [ ] The manifest, in Mark's copy, with `status: "in-progress"`. Render the stills. Fit the window.
- [ ] Tell Mark the release is out, so the project page can be listed once its write-up is out of draft.

### 8. Journey view and write-up: release status `live`
- [ ] The Journey view and the time-to-disposal curve, sharing the court selection. Journey becomes the opening view, and the stills are redone.
- [ ] Draft the write-up in `docs/writeup.md` for Mark, including a plain statement that nothing here is legal advice.
- [ ] Set `status: "live"` once Mark agrees, in a PR that bumps the version.

## For Mark, on the site

- **The write-up.** `content/projects/soudai.md` is a draft with a TODO, which asks for a plain statement that the predictions aren't legal advice. There are no predictions now, but the statement still belongs there.
- **The copy.** The tagline and summary ("Predicting how long court cases in the Czech Republic take") describe the old project. Mark rewrites them for the manifest and the site.
- **Status.** The site lists the project once a release is `in-progress` or `live` and the write-up is out of draft.

## Open questions

- **Map geometry.** Court areas or court seats? Researched on 2026-11-22: **court districts don't follow the current okresy**, and the clean way to draw them is from municipalities.
  - **What the law says.** The districts are set by zákon č. 6/2002 Sb. (https://www.zakonyprolidi.cz/cs/2002-6). Příloha 3 lists each of the 75 okresní soudy with the obce it serves, not an okres.
  - **Ostrava and Plzeň.** Okresní soud v Ostravě covers the city of Ostrava only; the rest of okres Ostrava-město goes to Opava, Frýdek-Místek and Nový Jičín. Okresní soud Plzeň-město covers the city of Plzeň only; the rest of its okres goes to Plzeň-jih and Plzeň-sever.
  - **Brno.** § 9(2) gives the city of Brno to Městský soud v Brně.
  - **Prague.** Příloha 4 defines Prague's 10 courts by městské části as they stood in 2002. These match RÚIAN's 10 MOP districts, Praha 1–10.
  - **Mismatches with today's okresy.** About 117 obce sit under a court other than their current okres's. Examples are the 9 obce moved from okres Domažlice to Plzeň-jih in 2021, which stayed with Okresní soud Domažlice, and 21 Brno-venkov obce under Žďár. Another ~65 annex names are ambiguous or renamed.
  - **Recommended source: ČÚZK RÚIAN, under CC BY 4.0** ("ČÚZK, <year>", saying what was changed). The whole country, with obce and okresy, is https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip (253 MB, S-JTSK). Prague's `OP_P` layer, with the 10 obvody, is in https://services.cuzk.gov.cz/shp/obec/epsg-5514/554782.zip (17 MB).
  - **How to build it.** Merge obec polygons by the annex's lists, using a hand-checked crosswalk for the ~65 awkward names. Add the city of Brno and Prague's 10 MOP polygons, then simplify. The result should be about 100–300 KB, which is an estimate.
  - **Alternatives:** ArcČR 4.3, which has no Prague obvody and whose licence is unconfirmed; Eurostat GISCO LAU, which is municipalities only and non-commercial; and OpenStreetMap, which is ODbL, share-alike. Points at the court seats remain the fallback.
- **Appeals.** An appeal at the regional court has its own case number (register `Co`), listed in `navazneVeci`. Following these links would give appeal durations. That's out of scope for now: the district case's own events (`ODVOLANI`, `ODES_SPIS`, `VRAC_SPIS`) give the loop.
- **Filing date and case year.** A case number's year is the year the case was entered in register C, not always the year it was filed. In the 54 Náchod cases fetched in step 2, 13 have a `ZAHAJ_RIZ` in the year before, mostly among a year's first numbers (11 of 2022's first 12). Likely causes are cases that began elsewhere and were moved into C, such as a payment order after an objection, a case from another register or court, or registration delays at the turn of the year. That's unconfirmed. It matters in three places, and needs a decision with Mark before steps 4–6:
  - **Intake.** A senate-year's top number counts cases *registered* in C that year. The demo should call it that, or count by filing year from the sample.
  - **Waits.** Measure from `ZAHAJ_RIZ`, the real filing date, not from 1 January of the case year.
  - **The check.** Replace "falls in the case's year" with "falls in the case's year or before", and record the share and the lag by court.
- **Older open cases.** The sample covers cases filed 2020–2025, so the direct backlog count misses older cases still open. A small extra sample of 2015–2019 filings would close the gap if the numbers need it.
- **Senates above 100.** What are they (e.g. 112 at Okresní soud Ústí nad Orlicí)? Discovery has to cover them either way. A clue from step 2: one day's first page of decisions had senates 106, 112 and 117 at "Okresní soud v Karviné, pobočka Havířov" and 108 at Městský soud v Brně, so a branch's senates may be numbered from 100. Ústí nad Orlicí has no branch, though.
- **Official statistics.** Found: InfoData's S_AS_40 report, with V(MS)-114 for the breakdown (see "External check"). Still open: whether a senate's top number matches "zapsáno" or "nápad". Step 6 compares both.
- **Publishing the snapshot.** The API can change or disappear, so it may be worth publishing the derived tables, for example as a release asset, if they're too large to commit.
- **Model card.** There's no model. Add a model card only if Mark wants one and there's a real figure for it, such as the German tank estimate's error against the exact counts.
- **Claim amounts.** `predmetRizeni` often gives the amount claimed. It's kept but not analysed. Splitting journeys by claim size would be a natural extension, if Mark wants it later.
- **Judges.** Discussed 2026-11-22: a judge-level aggregate (how much of the variation comes from the judge, with no names) was floated, and the scope Mark chose leaves judges out. The raw cache keeps `autor`; nothing derived does.
- **API stability.** If infosoud's API changes during a run, stop, record what changed here, and adapt the client. The cache keeps everything already fetched.
