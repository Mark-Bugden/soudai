# Plan: Judging the Journey

This is the agreed plan for rebuilding this project from scratch as an interactive demo for mark-bugden.github.io. It was settled with Mark on 2026-11-22, after a feasibility check against the live data sources and before any new code was written. The site's requirements are in `site-contract-soudai.md`, which lives outside this repo (in Mark's `personal_website` folder), and in the [demo-kit README](https://github.com/Mark-Bugden/demo-kit#readme). This document covers what we're building on top of them.

It is also the handover document. Any agent should be able to read it, find the first unchecked box under "Milestones", and carry on from there. See "Working on this plan" first.

## The goal

The demo shows how civil cases move through Czech district courts, and how long they take. It has three tabs (settled with Mark on 2026-11-25):

1. **Forecast,** the opening tab. A model gives the chance that a case ends within 1, 3, 6 or 12 months, from its history so far (see "The remaining-time model"). The visitor tries it on a real past case, picked at random or by court and case number, or on a made-up case they describe. The tab also shows how well the model does against simpler methods.
2. **Process map.** The journey of a civil case from filing to a legally final decision: the routes cases take, how many take each one, and how long each step lasts. A visitor can compare one court with the whole country.
3. **Courts,** added after the demo goes live. A map of the district courts, coloured by cases registered per year, backlog or typical time to a decision. Beside it, how close an estimate of a court's caseload, made from its published decisions alone (the German tank method), gets to the exact count.

The project was first planned as purely descriptive. On 2026-11-23 Mark decided that it also predicts, and on 2026-11-25 that the model matters more than the backlog, so it comes first. The project makes no claims about why courts differ, and isn't legal advice.

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
| Sample: published decisions from rozhodnuti.justice.cz | A random sample of all registered cases, drawn from each senate's docket on infosoud | Published decisions only cover decided cases, and publication volume swings by year (797 in 2020, 181,861 in 2022, 61,203 in 2024). Published decisions are still used, for the German tank estimate and to find senates. |
| Infosoud's HTML pages (`infosoud.justice.cz/InfoSoud/public/search.do`) | Infosoud's JSON API at `infosoud.gov.cz/api/v1` | The old site redirects every URL to the new app's front page and drops the query, so the old scraper no longer works. |
| Target: days from filing to the published decision, capped at 5 years, open cases dropped | Each case's full timeline. Waits are estimated with censoring (Kaplan–Meier), with no cap | The cap and dropping open cases both bias durations downwards. |
| Features: keywords and cited statutes from the decision | Not used | They're written when the case ends, so they leak the outcome. |
| Model: a PyTorch embedding MLP predicting days | Exact intake counts, German tank estimates, Kaplan–Meier waits and Little's law, plus a recurrent network forecasting each case's remaining time from its history, with censoring, against simpler models (see "The remaining-time model") | Mark's scope decisions on 2026-11-22 (descriptive) and 2026-11-23 (the model). |
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

- **Scope.** District-level courts (okresní and obvodní soudy and Městský soud v Brně: 86, confirmed in step 2), register `C`, cases registered 2020–2025, i.e. with case numbers of those years (decided 2026-11-22). Městský soud v Praze is a regional-level court and is out of scope.
- **Intake is registrations** (decided with Mark, 2026-11-22). A case number's year is the year the case was entered in register C, which for about a quarter of sampled cases is the year after it was filed (see "Filing date and case year" under "Open questions"). Intake is the exact count of cases registered per senate-year, and the demo calls it "cases registered". The courts' official statistics count nearly the same thing. Step 4's counts match "zapsáno" (entered in the register), which runs about 0.5% above "nápad" (see "Official statistics" under "Open questions"). Waits are measured from `ZAHAJ_RIZ`, the filing date.
- **Pacing.** 1 request a second across the whole project (decided 2026-11-22). On a connection error, wait 30, 60, then 90 s and retry. On any 429, or more than 5 failures in a row, stop the run and record it here. If 1 s draws 429s or keeps resetting, go back to 3 s and tell Mark.
  - **Raised to 3 a second from step 5 on** (Mark, 2026-11-24). Over intake's 92,195 requests, infosoud answered in 0.15 s on average (found cases) with 4 failures, so one request at a time manages about 2.9 a second. The stop rules are unchanged. Spreading requests over several machines or addresses to go faster isn't done. For more than that, ask the Ministry of Justice, which runs infosoud.
- **Identification.** User-Agent `soudai/<version> (+https://github.com/Mark-Bugden/soudai)`.
- **Cache.** Every response, including not-found responses, goes into a SQLite cache at `data/raw/cache.sqlite`: request key, URL, body, status, the response gzipped, and the fetch time. Nothing that's cached is fetched again unless a stage asks to refresh it. The cache is the snapshot, so it's never deleted, and it's never committed.
- **Privacy.**
  - Infosoud responses hold no names.
  - rozhodnuti items name the judge (`autor`). The parse step drops it, so no derived table, export or demo holds judges' names.
  - rozhodnuti's subjects (`predmetRizeni`) sometimes name other people, with a date of birth or an address (step 3). So the decisions table isn't committed, and no export or demo shows a subject.
  - Full texts of decisions are never fetched.
- **Snapshot.** Each case keeps its `platneK`. The snapshot date, i.e. the end of the timeline scrape, goes into the export, "How this works" and the write-up. Censoring is at each case's `platneK`.
- **What's committed.** `reference/` (hand-checked tables) and `data/derived/` (tables from the parse steps, with no judges' names). Any derived file over about 10 MB stays out of git (see "Open questions").

### Stages

| Stage | Input | Output | Rough cost at 1 req/s |
| --- | --- | --- | --- |
| Courts | infosoud `organizace/*`, the old `references/court_map.yaml` in `Mark-Bugden/SOUDAI_data_scraping` as a seed | `reference/courts.csv` | < 100 requests |
| Events | infosoud's JS bundle | `reference/events.csv` | < 150 requests (static files) |
| Published decisions | rozhodnuti listing | `data/derived/decisions.parquet` | 7,517 requests, 6 h 20 min (step 3) |
| Senates | decisions, probes of number 1 | `data/derived/senates.csv` | 36,403 requests, 10 h 8 min (step 4) |
| Intake | senates, binary search | `data/derived/intake.csv` | 7,670 senate-years: 92,195 requests, 25 h 42 min (step 4) |
| Timelines | intake, stratified sample | `data/derived/cases.parquet`, `events.parquet` | 400 per court-year: 208,227 cases, 184,243 requests, 17 h 9 min at 3 a second (step 5) |
| Official statistics | InfoData's S_AS_40 report, intake | `data/derived/official.csv` | 13 requests (step 6) |
| Journey | cases, events | `data/derived/journey_*.csv` | No requests: about 45 s (step 6) |
| Model | cases, events | `data/derived/model_scores.csv`, `model_calibration.csv` | No requests: about 40 s for the two simplest methods (step 7) |

The estimates for the senate and intake stages come from step 3's table (see step 4). Replace them with real numbers as the stages run.

### Checks (pytest)

The tests never touch the network. They run on saved real responses in `tests/fixtures/`: a found case, a not-found 400 and a listing page.
- Case numbers parse, and the regex covers every case number in the decisions table.
- Every court in `decisions` maps to a row of `reference/courts.csv`.
- The binary search finds the top of a fake docket, including dockets of 0 and 1 cases.
- Every sampled case has `ZAHAJ_RIZ`, and its date falls in the case's year or before. Record the share filed in an earlier year, and the lag, by court.
- No judge's name appears anywhere in `data/derived/` or the export.
- The German tank estimator and its interval match a brute-force simulation.
- The stage model gives the right path and dates for real histories, including revivals, appeals, suspensions and odd dates.
- The official statistics parse from the real 2022 report, every court appears once, and the courts add up to the national totals.
- The weighted Kaplan–Meier and Aalen–Johansen estimates match hand-worked cases and lifelines, and the journey numbers match a few cases worked by hand.
- The forecasting examples cut real-looking histories on the right days, with the right features and outcomes, and the split cuts the training records off at 31 December 2023.
- Concordance matches lifelines unweighted, and a weight counts as that many copies. The Brier score, its censoring weights and calibration match cases worked by hand, and so do the court average and the process map.
- The export matches its schema and stays under its size budget.

## Methods

### Exact intake

For each court, senate and year, the highest existing number is the number of cases registered that year. Find it with an exponential search from a hint (the highest published number, or 16), then a binary search. Then probe the top + 1 to + 3 and the top + 10 and + 25, to catch islands above a gap. To check there are no gaps, probe 3 random numbers below the top in every senate-year. If any probe comes back missing, stop and investigate before trusting the counts. Step 4 found that infosoud hides a few numbers (see "Hidden case numbers" under "Open questions"). So when a probe above the top finds a number, the search carries on from it, and when case 1 is hidden, it starts from the highest published number. Every hidden number it meets is flagged.

A court's intake for a year is the sum over its senates. Finding the senates (revised after step 3): the candidates for a court and year are the senates seen in its published decisions (any year), plus 1 to the highest seen below 100, + 10. Senates above 100 come in series by the hundred, so each hundred with at least 3 senates seen is probed the same way, from its 1 to its highest + 10 (301–327 for 305–317, say). In a hundred with fewer, only the senates seen are probed, since those are strays such as 11297. A senate exists in a year if its case number 1 does. For a few courts, sweep senates 1–999 in one year to check that the rule misses nothing.

### The German tank estimate

From published decisions alone: for a senate-year with k distinct published case numbers and highest number m, estimate N̂ = m(1 + 1/k) − 1. Count distinct cases, not decisions, since one case can have several published documents.
- **Interval.** P(max ≤ m | N) = C(m, k) / C(N, k), inverted for a one-sided 95% upper bound. The lower bound is m.
- **Court totals.** Sum the senates' estimates, and get the court's interval by simulation.
- **Missed senates.** Senate-years with no published decisions contribute nothing, so court totals undercount. Report how much.
- **The point.** The estimate assumes published case numbers are a uniform random sample of 1..N. They aren't: only decided cases are published, so in recent years high numbers are under-represented. The comparison with the exact counts, by year, is the finding.

### The journey

- **Stage model** (settled with Mark on 2026-11-25, from all 208,227 sampled histories; in `events.py`). Seven stages, and the events that put a case in each. The share is of all cases registered, weighted:

  | Stage | Events | Cases reaching it |
  | --- | --- | --- |
  | Filed | `ZAHAJ_RIZ` | 100% |
  | Hearing | `NAR_JED` | 80.4% |
  | Decided | `VYD_ROZH`, `ST_VEC_VYR` | 98.4% |
  | Appeal | `POD_OP_PR`, `ODES_SPIS`, `ODVOLANI`, `NAD_RIZENI`, `DOVOL_RIZ`, `VYR_OP_PR`, `VRAC_SPIS` | 6.3% |
  | Revived | `ST_VEC_OBZ` | 4.8% |
  | Suspended | `ST_VEC_PRE` | 3.2% |
  | Legally final | `ST_VEC_PUK` | 97.4% |

  - **Order.** A case's events are read by date, then `poradi`, with the filing first on its day. Cancelled events are left off, and so are events dated before the filing or after the record's `platneK`.
  - **Visits.** A visit is a run of events in one stage, so repeated hearings are one visit, and each visit keeps its number of events.
  - **Going back.** Cases can return to a stage, from revived to hearing, say. 5.5% do, and the map draws those as edges going back.
  - **The end.** A path stops at the first "legally final". Later events are left off, such as an appeal about costs after the main decision became final.
  - **Not on the map:** cancelled events; "proceedings resumed" (`ST_VEC_UPR`), which only ends a suspension; "closed in the register" (`ST_VEC_ODS`), which is bookkeeping a median of 27 days after legal force; and the 11 codes the sample never uses.
  - **"Appeal"** is any challenge to a decision: an appeal to the regional court (Městský soud v Praze for Prague's courts), an objection handled by the district court itself, or a higher court ruling on a side question, such as which court hears the case (`NAD_RIZENI`, 0.5% of cases).
  - **"Decided"** reads the decision as well as the disposal, because infosoud overwrites a revived case's first disposal date (see step 6).
  - **An edge's wait** runs from the day a case enters one stage to the day it enters the next.
- **Finished means legally final** (Mark, 2026-11-25), both for the journey's end and for the model (`events.outcomes`).
  - A case finishes at its first `ST_VEC_PUK`. The 0.31% closed in the register without one finish at their closing. A case still open is censored at its `platneK`.
  - **Disposal** stays as the time-to-a-decision curve and the map's measure, since it's the district court's own time. It's a case's latest `ST_VEC_VYR`, unless the case was revived after it and is still open. It's never later than the case's end: 340 cases show a disposal after their legal force. A case that finished with no disposal date counts as disposed when it finished.
- **Weights.** The sample is stratified by court and year, so each case carries the weight intake / sample size. Every share and curve is weighted.
- **Events that haven't happened yet** are left off: those dated after the record's `platneK`, 532 in 528 cases, nearly all hearings booked ahead.
- **Moves** (the map's edges, `journey_moves.csv`). For each move from one stage to another:
  - **its share:** the weighted share of cases making it at least once;
  - **its wait:** the median and quartiles, in days, of the wait among the cases that make it. It comes from every visit to the starting stage, by the Aalen–Johansen estimate: each next stage is a way out, and a visit still going when the record runs out is censored at its `platneK`. That's a Kaplan–Meier curve shared out between the ways out, so cases still waiting count for as long as they're known to wait. The wait is only given where at least 20 sampled cases made the move.
  - A few cases were closed in the register and then carried on (7 moves). Their last visit leaves for "closed" on the day it began.
- **Curves** (`journey_curves.csv`). The weighted share of cases not yet decided, and not yet finished, each month after filing, from 0 to 72, by Kaplan–Meier. `journey_summary.csv` gives their quartiles in days.
- **Stages** (`journey_stages.csv`). The weighted share of cases reaching each stage.
- **Variants** (`journey_paths.csv`). The commonest full paths, with how they ended (legally final, closed or still open) and their shares: the top 30 nationally, and the top 10 for each court.
- `uv run soudai analyse` writes all five tables in about 45 s. The scope "all" is the whole country, and any other is a court's code.

### The remaining-time model

Decided with Mark on 2026-11-23. He wants the portfolio to show more machine learning, in particular deep learning and business value. Language models aren't needed. Any framing of the model is Mark's to write.

- **The question.** Given everything that has happened to a case so far, what's the chance it finishes in each of the next 36 months? From those come the chances it finishes within 1, 3, 6 or 12 months.
- **How it follows from the map.** The map gives averages: from each stage, what usually happens next and how long it takes. The model answers the same question for one case, from its whole history: every event, the gaps between them, and the court. That includes what the map simplifies away, such as repeated hearings. The map is the yardstick. The model only earns its place if it beats the map's averages.
- **The network.** A recurrent neural network of the GRU type (Cho et al. 2014), with a discrete-time survival output, also called "logistic hazard" (Gensheimer & Narasimhan 2019; Kvamme & Borgan 2021). The closest published model is Dynamic-DeepHit (Lee, Yoon & van der Schaar 2019). In process mining, the field is called predictive process monitoring (Tax, Verenich, La Rosa & Dumas 2017). The starting sizes, to be tuned:
  - **Each event is 10 numbers:** its type, one of 28, as 8 learned numbers (an 8 × 28 weight matrix applied to a one-hot vector); log(1 + days since the previous event); and log(1 + days since filing).
  - **The hidden state** is a vector of 32 numbers, starting at zeros. The GRU updates it once per event, with the same weights at every step.
  - **The output layers.** At the moment of a forecast they take 37 numbers: the last hidden state, the court (4 learned numbers, from a 4 × 86 matrix) and log(1 + days since the last event). They go through a fully connected layer of 32 with ReLU, then one of 36, each through a sigmoid.
  - **The outputs.** Output k, p_k, is the chance the case ends in month k, given that it's open at the start of that month. The chance it's still open after k months is (1 − p₁)…(1 − p_k).
  - **Size:** about 7,100 weights and biases, small enough to run in the demo.
- **The training data** is step 5's sample of timelines:
  1. Read the events as the stage model does (`events.log`): cancelled ones and those dated before the filing are dropped, and the rest are sorted by date, then by `poradi`. Mark confirmed on 2026-11-25 that cancellations stay out of the model.
  2. A case finishes when it becomes legally final, or at its closing if it's closed without that (settled 2026-11-25; see "The journey").
  3. Cut each case at the end of each day with events before the end, making each cut one example. A hearing and its decision usually share a date, so a cut between them would make the forecast trivial. And `NAR_JED` is dated the day the hearing is held, so the model only learns of a hearing when it happens, never ahead. An example is the events so far, plus either the month the case ended in or "still open after n months", counted to its `platneK`.
     - **Also cut every month after filing** (days 30, 61, 91, …, for 5 years), added in step 7. Cuts on event days alone would always have 0 days since the last event, so no model could learn what a quiet spell means, and none could forecast a case between its events, or at a fixed time after filing, which is how forecasts are scored.
  4. Weight each example by its case's sampling weight.
  5. Split by time: train on earlier registration years, and test on later ones.
     - **Settled in step 7: the split is 1 January 2024.** The models train on cases registered 2020–2023, as their records stood on 31 December 2023: anything dated later is cut off, and a case still open then is censored there. They're tested on cases registered 2024–2025, followed to the snapshot. So the scores are those of models built on 1 January 2024 and used on the cases that came after, with nothing seen from after that day. Two test years rather than one give twice the test cases, and 2024's have at least 22 months of follow-up.
     - **Validation.** A fixed random 10% of the training cases is held out, to stop training and to tune.
  6. In a batch, pad shorter cases to the same length, and mark which steps are real.

  `examples.py` builds them. Training: 138,815 cases (those still open at the end of their filing day), 551,117 events and 1,245,125 cuts. Test: 69,336 cases, 285,826 events and 603,472 cuts. A case has at most 49 events before its end.
- **Training.** One pass through a case gives a hidden state after every event, so all its cuts are scored together.
  - **The loss.** For a case that ended in month k, it's −[log(1 − p₁) + … + log(1 − p_{k−1}) + log p_k]. For a case still open after n months, it's −[log(1 − p₁) + … + log(1 − p_n)].
  - **Backpropagation through time.** The chain of steps is unrolled, and each shared weight's gradient is the sum of its contributions from all the steps. The GRU and the output layers are trained together.
- **Comparison models,** each knowing more about the case than the one before:
  1. **The court average:** a Kaplan–Meier curve per court.
     - As built (`baselines.py`): the court's curve from filing to the end, over its training cases, read from the day of the cut: S(day + t) / S(day). Where fewer than 20 of the court's sampled cases were still open on that day, it's read from the last day that had 20.
  2. **The process map:** per court, the stage reached and the time spent in it.
     - As built: the Kaplan–Meier curve of the time left, over the training cuts in the same court and stage, with about as long in it: 0 days, 1–30, 31–91, 92–182, 183–365 or more. Where the court has fewer than 50 such cuts, all courts' are used, and failing that, all courts' in the stage. It knows nothing of the time since filing, as the map doesn't.
  3. **A Cox proportional hazards model** on hand-made features.
  4. **Gradient-boosted trees** (XGBoost or LightGBM) on the same features, predicting the same 36 monthly chances.
  5. **The GRU network.**

  The hand-made features are the court, the current stage, the time since filing and since the last event, the number of hearings so far, whether there has been an appeal, and whether a decision has been issued. An optional extra is the network's output layers fed the hand-made features instead of the sequence. It separates "a neural network helps" from "reading the sequence helps". If the GRU doesn't clearly beat the trees, the write-up says so.
- **Scoring.** Every model is scored the same way, on the same held-out later years:
  - **concordance:** how often the model correctly ranks which of two cases finishes first;
  - **the Brier score** at 6, 12 and 24 months, corrected for censoring;
  - **calibration:** of the cases given a 70% chance of finishing within a year, about 70% should.

  The scores are also broken down by court, and by how far into a case the forecast is made.

  As built in step 7 (`scoring.py`):
  - **Where forecasts are scored.** Each test case at its filing, and 1, 3, 6 and 12 months after, while it's still open: 234,784 forecasts. Each case counts once at each of these landmarks, so cases with many events don't count for more. "By how far into a case" is by landmark.
  - **Concordance** is Harrell's C, weighted (a pair weighs the product of its cases' weights), comparing cases at the same landmark only, by the expected months left (the area under the forecast curve, to 36 months). It matches lifelines' `concordance_index` unweighted, ties included.
  - **The Brier score** at 1, 3, 6, 12 and 24 months: the weighted mean of (outcome − forecast)², where the outcome is whether the case finished within that time. A case censored before then is left out, and the others are weighted up to stand for it (inverse probability of censoring weights, Graf et al. 1999), with the censoring curve estimated at each landmark over all courts. 1, 3, 6 and 12 months are the demo's.
  - **Calibration** at 1, 3, 6 and 12 months: forecasts in bins of 10 points, against the share of those cases that finished within the time (by Kaplan–Meier). Its summary is the mean gap between the two, weighted by the cases in each bin.
  - `uv run soudai model` writes `data/derived/model_scores.csv` (each model's scores, for all courts and each court, and at each landmark) and `model_calibration.csv`.
- **Still open:**
  - step 5's sample size: settled with Mark on 2026-11-24 at 400 cases per court-year, 208k in all (see step 5). More can be added later by drawing further down each senate-year's order, if the learning curve says it would help;
  - whether intake's hole probes, which are 3 random cases per senate-year and come with their full timelines, can add to the training data, with the right weights. Settled in step 5: they're in the sample, 22,207 of its cases;
  - modelling the different endings (judgment, withdrawal) as competing risks;
  - a transformer as a further comparison.
- **In the demo** (settled with Mark on 2026-11-25). The model is the opening Forecast tab, and it's built before the backlog.
  - **Real past cases:** a few thousand from the test years, carried in the demo with their histories and what happened next. A visitor picks one at random or by court and case number.
  - **Made-up cases:** the visitor gives the court and the events so far, and the demo runs the network itself, so its forward pass is ported to JS and checked against the Python.
  - **How well it does:** the scores of the model and the simpler methods side by side, and its calibration.

### Backlog

Little's law: backlog L = λW, with λ the yearly intake (exact) and W the mean time from filing to disposal. Censoring makes W's mean hard. Use a restricted mean with the horizon stated, and lean on the early filing years, which are almost all closed.

As a check, count directly from the sample the weighted number of cases open on 31 December of each year. That count misses cases registered before 2020 that are still open, so it's a lower bound (see "Open questions").

Little's law also assumes a steady state, which 2020 wasn't. Say so wherever backlog is shown.

### External check

Compare national and court intake with the Ministry of Justice's official statistics. The source was found on 2026-11-22 by web research, without touching rozhodnuti or infosoud.

- **The report to compare against: S_AS_40, "Přehled o vyřizování agendy C u OS" (Tabulka č. 40).**
  - **Where:** InfoData's reports form at https://cslav.justice.cz/InfoData/prehledy-agend.html. POST `sestavaQry=S_AS_40`, `obdobiOdQry=01.01.YYYY`, `obdobiDoQry=31.12.YYYY` and `jenVykCeleObdQry=on` with a session cookie. The result links to `/InfoData/servlet/FileServlet`.
  - **Coverage:** one file per year for register C, with all 86 courts (Městský soud v Brně appears as "Brno"), kraj totals and a national total. The portal says the data go back to 2008.
  - **Format:** XML Spreadsheet 2003, PDF or HTML.
  - **Columns:** nápad, obživlo, vyřízeno, nevyřízeno by age, and pravomocně/nepravomocně.
  - **Editions used** (step 6): one per year, computed on 2021-01-25 (2020), 2022-01-18, 2023-01-15, 2024-01-08, 2025-01-09 and 2026-01-08 (2025). `reference/sources.json` records them.
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
| Tabs | Forecast (opening) and Process map, then Courts after the demo goes live (step 10). They're switched with buttons at the top of the controls rail, and the rail shows only the controls the current tab uses. |
| Forecast | Pick a real past case, at random or by court and case number, or describe a made-up one: its court and its events so far. It shows the case's history so far and the chances it ends within 1, 3, 6 and 12 months. For a real case, it also shows what happened next. |
| How well it does | Under the forecast: the scores of the model and the simpler methods side by side, and a calibration chart. |
| Process map | A flow diagram of the stages a civil case passes through, with the appeal loop as a side branch. Each edge's thickness is the share of cases that take it, and its label is the median wait. Hovering an edge gives its share, median and interquartile range. |
| Time to a decision | Beside the diagram: the share of cases not yet decided, and not yet legally final, t months after filing, for the selected court against all courts. |
| Court selector | All courts, or one court, with search by name. Search ignores diacritics, so "Decin" finds Děčín. The selection is shared by all the tabs. |
| Courts (step 10) | A map of the district courts (see "Open questions" for areas or seats), coloured by the chosen measure: cases registered per year, backlog, or median time to a decision. Clicking a court selects it. |
| Court panel (step 10) | For the selected court: exact intake by year beside the German tank estimate and its interval, and its backlog. |
| Tank explainer (step 10) | Stretch goal: reveal a court's published case numbers a few at a time and watch the estimate close in on the exact count. |
| Status line | What's selected, with its headline numbers. |
| How this works | Sources and snapshot date, what's counted (district courts, register C, registered 2020–2025), the methods and the model in brief, and that it isn't legal advice. |
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
  src/views/                   forecast, process map, courts
  src/forecast.js              the network's forward pass, ported from Python, for made-up cases
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
  survival.py                  weighted Kaplan–Meier and Aalen–Johansen
  examples.py                  the forecasting examples: histories cut into forecasts, and the time split
  scoring.py                   concordance, censoring-corrected Brier scores and calibration
  baselines.py                 the comparison models: court average, process map, Cox, trees
  official.py                  the Ministry's official statistics (S_AS_40), against intake
  journey.py                   the journey numbers: stages, moves, waits, curves and paths
  model.py                     fits and scores every model: `uv run soudai model`
  network.py                   the GRU network, in PyTorch (an optional dependency)
  backlog.py                   Little's law and the direct count
  export.py                    writes demo/public/data/ and the JS fixtures
  status.py                    progress of each stage, from the cache and derived tables
  cli.py                       `uv run soudai <stage>`: courts, events, decisions, senates, intake, sample, official, analyse, model, export, status
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
  - **For Mark:** the glosses are short labels for the demo, e.g. `ZAHAJ_RIZ` "Case filed", `ST_VEC_VYR` "Case disposed", `ST_VEC_PUK` "Legally final", `ST_VEC_ODS` "Case closed in the register". Edit them in the CSV: `soudai events` keeps them. Mark changed `NAR_JED` to "Hearing" on 2026-11-25 (see step 6). The rest are still to check.
- [x] `reference/sources.json`: endpoints, the date checked and the backend version.
- [x] `soudai status`, and the offline tests.
  - `uv run soudai <stage>` has `courts` (`--write`), `events` and `status`. `status` reports the cache, the last runs, the day pages cached against the cached month indexes, case lookups by the case number's year and by outcome (found, not found, error, or unexpected), the reference tables and the derived tables. It never creates the cache.
  - 98 tests, all offline. They run on real responses in `tests/fixtures/`: 7 cases (found, not found, open, cancelled hearing, suspended, disposed, legally final), the court lists, the env, the labels chunk (cut to its resource bundle), and rozhodnuti's indexes and a day page with every `autor` replaced by `REDACTED`. The client's tests use a fake session and clock, so none of them waits.
  - The Windows console's code page can't print č or ř, so the CLI switches stdout and stderr to UTF-8.
  - A review of the code turned up two minor bugs, both fixed: `status` lumped every 400 together, and a test of 5xx caching couldn't fail. It also turned up the edge cases above (cached outage pages, 403s and 408s, malformed JSON, numpy ints in a request body), and the filing-year finding.

### 3. Published decisions (run, then PR, 2026-11-22)
- [x] List every decision from 2020 to the snapshot date.
  - **Snapshot 2026-11-21:** 616,458 decisions on 1,805 days, the last on 2026-11-20.
  - **Three runs:**
    - Run 21 was a trial of 2020 only: 39 requests.
    - Run 22 made 5,462 requests in 4 h 41 min, until the computer restarted.
    - Run 24 resumed it: 2,016 requests, with 5,311 answered from the cache, in 1 h 40 min.
  - **In all:** 7,517 requests in 6 h 20 min, 311 failures, and no 429s or 403s. The estimate of 7–9k requests held, but the time didn't.
  - **rozhodnuti drops a connection about every 24 requests.** All 311 failures came singly: 273 connection errors and 38 read timeouts, each cleared by one 30 s wait. A failure costs 20–30 s before the wait, so the listing manages about 20 requests a minute at any pacing. Going back to 3 s, as "Pacing" says to do if 1 s keeps resetting, would only slow it, so it wasn't done, and Mark was told.
  - **The day pages aren't stable.** 15 decisions appear on two neighbouring pages of the same day. That day's count still matches its total, so for each repeat some other decision was skipped. About 15 of 616,458 are missing. The 5 other repeated case numbers have no document part: they're different documents on different days.
- [x] Parse to `data/derived/decisions.parquet`: court code, senate, register, number, case year, document number, decision date, publication date and `predmetRizeni`. Drop `autor`, keywords and statutes.
  - 10.9 MB, with the snapshot date and the source in its metadata. `--parse-only` rebuilds it from the cache in about 20 s.
  - **It isn't committed.** It's over 10 MB, and `predmetRizeni` isn't fully anonymised. Most subjects use placeholders (`[částka]` in 51,796, `[číslo]`, `[anonymizováno]` and others). But about 200 give someone's date of birth or address, such as a liquidator's, and about 385 have a name with a title. `.gitignore` lists the file, so nobody commits it by accident. See "Publishing the snapshot" under "Open questions".
  - **The judge check stopped the first parse.** Five `autor` fields hold a place, not a judge: "Hradci Králové" (twice), "Karlovy Vary", "Nový Jičín" and "Valašském Meziříčí". Each matched a court name or subject.
  - **How the check works now.** It takes each pair of adjacent words in `autor` and looks for it in the court names and subjects. Titles and role words ("předseda senátu", "samosoudce") are left out, and each word is capitalised. Pairs are needed because some fields hold two judges, a number or a name in lower case. The four places are listed in the code and skipped. Judges' names found: 0.
- [x] Record: total decisions, requests, run time, resets, the split by court level and register, case numbers that didn't parse, and courts that didn't map.
  - **By year of publication:**

    | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (to 21 Nov) |
    | --- | --- | --- | --- | --- | --- | --- |
    | 797 | 150,939 | 181,861 | 85,462 | 61,203 | 71,514 | 64,682 |

  - **By court level:**
    - district 589,465;
    - regional 17,950;
    - high 8,307;
    - supreme 9;
    - other 87: Ústavní soud, and three "Neznámý soud NN";
    - `(nezadán)` 640.
  - **Registers at district-level courts:** C 589,034, then T 198, EVC 84, EC 49, CO 32, Nc 22, Co 15, NC 6 and c 2. Another 23 have no register because their case number doesn't parse.
  - **Case numbers that don't parse:** 24, nearly all `0  0/0`.
  - **Courts:** all 86 appear, and every district-like name maps to one. Hodonín's name is confirmed as "Okresní soud v Hodoníně", with 4,887 decisions.
  - **Register C at district courts, by case year:**

    | | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
    | --- | --- | --- | --- | --- | --- | --- |
    | Decisions | 56,438 | 170,859 | 144,911 | 66,452 | 58,469 | 55,372 |
    | Distinct cases | 55,748 | 169,381 | 143,732 | 65,690 | 57,688 | 54,700 |

    7,262 senate-years have at least one, and so does every court-year.
  - **Senates above 100 are common.** They come in series at 22 courts, and step 4's candidate rule has to change to fit. See "Senates above 100" under "Open questions".

### 4. Senates and exact intake (run, then PR)
- [x] Find each court's senates for each filing year (see "Exact intake"), including the wide sweep for a few courts. Record the number of active senate-years and the requests used.
  - **Run 25, 2026-11-22 to 23:** 36,403 requests in 10 h 8 min, with no failures. That's the estimate to the request. infosoud ran at exactly 1 a second all night.
  - **7,544 senate-years have a case 1:**

    | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
    | --- | --- | --- | --- | --- | --- |
    | 1,256 | 1,268 | 1,273 | 1,265 | 1,252 | 1,230 |

    That's about 14.6 senates per court-year. 408 of them have no published decisions; the margin of 10 found them.
  - **The sweep of 1–999** at Karviná, Brno, Ústí nad Orlicí, Prague 1 and Jeseník in 2023 found nothing the rule missed.
  - **126 senate-years have published decisions but no case 1.** A follow-up run (26, 373 requests) asked infosoud for cases 2 and 3 and the highest published number in each:
    - In 78, the highest published number exists, so they're real senate-years whose case 1 is hidden. In 61 of them cases 2 and 3 exist too, in 7 neither does, and in 10 one of them does.
    - In 48, none exists. 44 have a single published decision, 3 have two and 1 has six, so they're probably typos in the case numbers.
  - **That's a gap, so it's recorded here to settle with Mark before step 5.** See "Hidden case numbers" under "Open questions".
  - `data/derived/senates.csv` has all 7,670 rows: 7,544 found and 126 not found.
- [x] Find each senate-year's highest number, with the probes above it and the 3 gap probes below it.
  - **Run 27, 2026-11-23 to 24:** 92,195 requests (7,808 more answered from the cache) in 25 h 42 min. The estimate was ~93k and ~26 h.
  - **4 failures,** between 00:32 and 00:40: two connection errors and two connect timeouts, one pair of them in a row. Each cleared after its wait.
  - **13.0 probes per senate-year,** cached ones included.
- [x] Write `data/derived/intake.csv` (court, senate, year, count, probes used, flags), and record totals by court-year and nationally. If any gap turned up, stop: record it here and settle it with Mark before step 5.
  - **Cases registered in register C at the 86 district-level courts:**

    | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | All |
    | --- | --- | --- | --- | --- | --- | --- |
    | 288,307 | 292,486 | 296,731 | 288,244 | 286,255 | 273,649 | 1,725,672 |

  - **Against the official statistics.** S_AS_40's national nápad is 286,801 in 2020, 295,311 in 2022 and 272,434 in 2025, so the counts run 0.53%, 0.48% and 0.45% above it. At Náchod in 2022 the count is 2,326, against V(MS)-114's "zapsáno" of 2,327 and "nápad" of 2,309. So the counts are registrations ("zapsáno"), as intended, and the small gap to nápad is the gap between the two measures. Step 6 compares every court.
  - **Court-years.** The median court-year registered 2,630 cases. The smallest was Pelhřimov in 2020 (755) and the largest Ostrava in 2023 (18,753).
  - **German tank, first look.** Step 4's estimate from published decisions alone came to 2.0% above these totals in 2020, and within 0.8% from 2021 on. Step 6 does this properly.
  - **Gaps did turn up.** 263 senate-years are flagged:
    - **48 `no case 1`:** neither case 1 nor the highest published number exists, so they count 0. These are the probable typos from the senates run.
    - **78 `hole:1`:** case 1 is hidden, so the count started from the highest published number.
    - **38 `island`:** the search stopped at a hidden number, found numbers above it, and carried on.
    - **108 holes from the random probes below the top,** in 106 senate-years.
  - **How often numbers are hidden.** 108 of the 22,315 random probes found nothing, 0.48%. Case 1 is hidden about twice as often, in 78 of the ~7,620 real senate-years (1.0%).
  - The counts are the highest numbers that exist, so they're short only where a senate-year's last numbers are hidden. That costs a case or two at most, against hundreds per senate-year. The gap is recorded under "Hidden case numbers" for Mark to settle before step 5.

Changed after the senates run (2026-11-23):
- **Intake counts the 126 too.** If case 1 is hidden but the highest published number exists, the search starts there, and the senate-year is flagged `hole:1`. If neither exists, it counts 0, flagged `no case 1`.
- **Intake carries on past hidden numbers.** If a probe above the top (+1, 2, 3, 10 or 25) finds a number, the search starts again from the highest one found, until none does. On fake dockets, this finds the true top past up to 7 hidden numbers in a row where the search stops. A run of 10 or more right there would go unnoticed.
- **Estimated cost,** simulated on the real 7,670 senate-years: about 93k requests, about 26 h, if the dockets are the size the German tank estimate gives. If they're 20% bigger, it's 115k requests and 32 h. The 408 senate-years with no published decisions are assumed to have 50 cases each, or 300 in the bigger case.

Built before the run (2026-11-22), with tests on fake dockets:
- **`soudai senates`** writes `data/derived/senates.csv`, with one row per senate-year whose case 1 exists. Senate-years that have published decisions but no case 1 get a row too, flagged. Each row carries what step 3's table says about the senate-year: how many of its cases were published, and the highest number among them.
- **`soudai intake`** writes `data/derived/intake.csv`, using that highest number as the search's hint. A lookup that keeps failing (`RIZENI_0001` three times) flags its senate-year and doesn't stop the run. `infosoud.exists` also checks that a found case is the one asked for.
- **Candidates, by series.** The first rule (1 to the highest seen + 10) would have cost 272,568 probes, because stray senates like 11297 at Náchod and 9249 at Liberec stretch the range. Step 3's table also showed a natural line between strays and series:
  - every hundred above the first with 1 or 2 senates seen has at most 3 published cases;
  - every one with 3 or more has at least 6 senates, and all but one (Brno-venkov, 7 senates and 9 cases) have 45 cases or more.
  - With the rule by series, the median court has 53 candidates, and Městský soud v Brně the most, 262.
- **The sweep** widens to 1–999 at Karviná, Brno, Ústí nad Orlicí, Prague 1 and Jeseník in 2023, to cover hundreds like 300 and 700.
- **Estimated cost of the senates stage:** 31,962 probes by the rule and 4,441 in the sweep, so 36,403 requests, about 10 h.
- **Estimated cost of intake,** simulated by running the search on dockets of the German tank size, hinted with the highest published number:
  - 13.1 probes per senate-year for the 7,262 with published decisions, about 1 of them case 1, which the senates stage has already cached;
  - with ~15% more senate-years that have no published decisions, about 100–110k requests, ~30 h.
- **A first look at the German tank estimate.** From the published decisions alone, it gives national register C totals of 294,192 (2020), 292,409, 294,591, 287,539, 286,718 and 274,013 (2025). The official nápad is 286,801 for 2020, 295,311 for 2022 and 272,434 for 2025. These are senate-years with published decisions only, before any exact count. Step 6 does this properly.

### 5. Timeline sample (run, then PR)
- [x] Draw 60 cases per court-year, uniformly over the court-year's docket (all its senates' numbers together), with a recorded seed. Each case's weight is the court-year's intake / 60.
  - **Changed with Mark on 2026-11-24, before the run:**
    - **400 cases per court-year** instead of 60, for the remaining-time model: 208,227 in all.
    - **Drawn by senate-year** (one senate's cases in one year) rather than over the whole court-year. Each court-year's 400 are split between its senates in proportion to their counts, by largest remainders, with at least 1 each.
    - **Intake's hole probes count in.** Those are 3 random numbers below each senate-year's top, 22,315 in all, already in the cache with their timelines.
    - **The order numbers are tried in.** A senate-year's numbers are tried in a fixed order: the probes first, then the rest of 1 to its count, shuffled with the seed `sample-<court>-<senate>-<year>`. A hidden number is skipped, and the next one is drawn.
    - **Weights.** Each case's weight is its senate-year's count / the cases sampled from it, so the weights add up to intake's counts.
    - **A small imperfection.** Numbers 1 and the top are slightly less likely to be drawn, since the probes never ask them. That's 2 numbers in a senate-year's median of 234.
  - **The cost:** 186,000 new requests at 3 a second, about 18 h. The run started on 2026-11-24 at 21:27.
  - **Run 28 stopped** on 2026-11-25 at 09:20, after 127,624 requests with no failures, on an unexpected answer. Asked for 5 C 294/2020 at Nymburk, infosoud gave that case's 7 events plus a stray "hearing scheduled" of 2018-10-26 stamped "5 C 294/20", whose year (20) became the record's, with no status.
    - `infosoud.find_case` now raises `WrongCase` for a record of another case. The sample skips it like a hidden number, and any other unexpected answer still stops a run.
    - The run was resumed from the cache as run 29.
  - **Runs 28 and 29.** Run 28 made 127,624 requests in 11 h 53 min before the stop, and run 29 made 56,619 in 5 h 16 min. That's 184,243 requests in all, at 2.97 a second, with no failures, no retries and no 429s. infosoud answered in 0.065 s on average.
  - **208,227 cases,** 22,207 of them from step 4's probes, about 34,700 per year. The weights add up exactly to intake's counts in every year (288,307 for 2020, and so on).
  - **Skipped:** 788 hidden numbers (0.38% of the numbers tried) and the 1 record for another case. No senate-year fell short of its target.
  - **Found before the run.** The probes' 22,000 timelines show nearly all cases registered 2020–2025 are already disposed:

    | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
    | --- | --- | --- | --- | --- | --- |
    | 100% | 99% | 99% | 98% | 98% | 97% |

    The share legally final is 99% for 2020 and 92% for 2025. The 2025 cases took a median of 126 days from filing to disposal, and 90% took 258 days or less. So unfinished cases are a small tail, not most of the recent years.
- [x] Parse to `data/derived/cases.parquet` (case, court, filing date, status, status date, `platneK`, weight) and `data/derived/events.parquet` (case, code, date, `poradi`, cancelled).
  - **A case's history includes its linked cases' events.** Of 173,486 cached records, 9,115 (5.3%) hold events stamped (`znackaId`) with another case's number:
    - 10,552 appeals (`ODVOLANI`), at the regional court's `Co` register;
    - about 1,100 other higher-court proceedings (`NAD_RIZENI`, registers `Nc`, `Ncp` and `Ncd`);
    - 2 Supreme Court reviews (`DOVOL_RIZ`);
    - and the one stray above.

    So `events.parquet` gains `linked_court` and `linked_case`: null for the case's own events, and the other case's court code and number for these. The appeal loop on the map comes from them.
  - **The tables.** `cases.parquet` is 0.98 MB and `events.parquet` 4.2 MB, with 1,391,808 events (a median of 6 per case, at most 89). `soudai sample --parse-only` rebuilds them from the cache in about 20 s. They hold codes, dates, numbers and infosoud's status labels, and no names.
  - **Linked-case events** are in 9,783 of the sampled cases (4.7%).
  - **Statuses (`stav`):**

    | Status | Meaning | Cases |
    | --- | --- | --- |
    | Odškrtnutá – evidenčně ukončená věc | closed in the register | 202,543 |
    | Přerušeno na dobu neurčitou | suspended indefinitely | 1,926 |
    | Vyřízená věc | disposed | 1,548 |
    | Nevyřízená věc | not yet disposed | 978 |
    | Pravomocná věc | legally final | 826 |
    | Obživlá věc | revived after its decision was quashed | 328 |
    | none | | 78 |

  - **The records' dates.** Each record is complete to its `platneK`, which is between 2026-11-20 and 2026-11-25. The snapshot spans the run.
- [x] Check that every case has a filing event in its case year and that events order sensibly, and record the share still open by filing year.
  - **Filing events.** 76 cases (0.04%) have none.
    - None was filed after its case year.
    - **20.0% were filed in an earlier year,** weighted. By court, that runs from 7.5% (Jeseník) to 35.4% (Ostrava), with a median of 18.9%. Those cases were filed a median of 61 days before 1 January, and 90% within 165 days. That fits the EPR transfers (see "Filing date and case year").
  - **Order.** The case's own first event is the filing in 208,024 of the 208,151 cases that have one. 127 have own events dated before the filing (73 of them hearings). 365 have "legally final" dated before "disposed".
  - **Odd dates.**
    - 542 hearings are dated after the snapshot, up to 2028-02-08. They're hearings scheduled ahead, so they're kept.
    - 3 dates are typos (years 0023, 1021 and 1023).
    - 13 events fall between 1990 and 2009.
  - **Still open,** weighted:

    | | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
    | --- | --- | --- | --- | --- | --- | --- |
    | No disposal event | 0.4% | 0.8% | 0.9% | 1.2% | 1.8% | 3.5% |
    | No legal-force event | 0.9% | 1.5% | 1.6% | 2.1% | 3.0% | 6.7% |

  - **Median days from filing to disposal,** weighted, among disposed cases: 159 (2020), 158, 148, 147, 146 and 131 (2025). The recent years are biased low by their open tail. Step 6's Kaplan–Meier corrects that.

### 6. Journey numbers (PR)
- [x] Settle the stage model (see "The journey") and write it here.
  - **Settled with Mark on 2026-11-25:** the seven stages and their rules (see "The journey"), and legally final as "finished". Cancelled events stay out of the model too. The gloss of `NAR_JED` is now "Hearing" instead of "Hearing scheduled", since its date is the hearing's own.
  - **In code:** `events.log` gives the events the journey reads. `events.journey` gives one row per stage visit: 832,772 for the 208,151 cases with a filing. `events.outcomes` gives each case's filing, disposal and end dates, with how it ended: 202,851 legally final, 650 closed in the register without that, and 4,650 still open. 25 tests run on real histories.
  - **What the histories show,** weighted:
    - **Two routes cover 87.4% of cases:** filed → hearing → decided → legally final (71.8%), and filed → decided → legally final (15.6%). There are 1,221 distinct paths, and the 10 commonest cover 93.8%.
    - **`NAR_JED` is dated the day the hearing is held,** not the day it was ordered. In 90% of cases the first decision comes the same day as the first hearing. Hearings are dated up to 2028, and cancellations a median of 6 days before the hearing they cancel.
    - **Hearings:** 19.6% of cases have none, 74.8% one, and 5.7% two or more.
    - **The decision and the disposal fall on the same day in 96% of cases.** Legal force follows a median of 30 days later with no appeal, and 123 days with one. Closing in the register follows a median of 27 days after legal force.
    - **infosoud overwrites a case's disposal date when it's disposed again.** A case can only be revived after a disposal. Yet only 11% of revived cases that were later decided again show a disposal before the revival, against 98.8% of the 328 still waiting for a new decision. Only 0.01% of cases show two disposal dates.
    - **Revivals:** 5.0% of cases. 87% of them involve no appeal court, and 78% have no hearing before them. The usual pattern is a decision a median of 7 weeks after filing, cancelled a median of 57 days later, then a hearing and a new decision. The first decision is probably a payment order the defendant objected to, but that's inferred.
    - **Appeals:** 5.7% of cases have a remedy filed, and 4.3% reach an appeal court (`ODVOLANI`). Of those, 61% next become legally final and 14% are revived. The rest are still open, or the appeal came after the case was final.
    - **Cancelled hearings:** 9.4% of cases. Each comes as a pair, both marked `zruseno`: the hearing at its planned date, and `ZRUS_JED` on the day it was called off.
    - **Suspensions:** 3.2% of cases, resumed after a median of 281 days. 29% of those are still suspended.
    - **11 of the 28 codes never appear:** the four `PNS_*` notes, `PREVD_SPIS`, `PR_VEC_NS`, `SPIS_K_SC`, `SPIS_K_SO`, `SPIS_OD_SC`, `SPIS_OD_SO` and `VR_SP_NS`.
    - **Odd dates.** 143 of the cases' own events, in 127 cases, are dated before the filing, including the three typos (years 0023, 1021 and 1023), and are left off. The 76 cases with no filing have no events and no status at all, and are left out (466 cases by weight, 0.03%). Filings long before the case year are kept: 387 cases were filed 2 or more years before their case year, the earliest in 1999. They were probably moved in from another court or register.
- [x] Journey: weighted transition shares, Kaplan–Meier waits and curves, and the top variants, per court and nationally.
  - **In code:** `survival.py` holds the weighted Kaplan–Meier and Aalen–Johansen estimates, written here because lifelines jitters tied days at random in Aalen–Johansen. They match lifelines (with weights, and with ties for Kaplan–Meier) and hand-worked cases. `journey.py` and `uv run soudai analyse` write the five tables (see "The journey"). There are 19 new tests.
  - **The whole country** (1,725,206 cases registered, 208,151 sampled):
    - **From filing to a decision:** median 149 days (quartiles 103 and 222).
    - **From filing to legally final:** median 184 days (quartiles 133 and 265).
    - **Still open:** 2.2% of cases.
  - **Share not yet decided, and not yet legally final, by months after filing:**

    | Months | 3 | 6 | 9 | 12 | 24 | 36 | 60 |
    | --- | --- | --- | --- | --- | --- | --- | --- |
    | Not decided | 80.1% | 36.0% | 16.7% | 9.7% | 3.3% | 2.0% | 0.9% |
    | Not legally final | 89.5% | 50.7% | 23.4% | 13.1% | 4.3% | 2.6% | 1.3% |

  - **The main moves,** with their share of cases and median wait:
    - filed → hearing: 76.1%, 148 days;
    - filed → decided: 19.8%, 79 days;
    - hearing → decided: 79.4%, the same day;
    - decided → appeal: 5.1%, 58 days;
    - decided → revived: 2.7%, 155 days;
    - appeal → revived: 1.7%, 45 days;
    - filed → suspended: 2.3%, 152 days;
    - suspended → decided: 1.2%, 656 days.
  - **Courts differ a lot.** The median from filing to a decision runs from 92 days (Jeseník) and 93 (Prague 5) to 238 (Prague 1 and Litoměřice); the median court takes 144. To legally final, it runs from 127 days (Jeseník) to 293 (Prague 1). Still open: from 0.9% to 5.0% (Městský soud v Brně). 1,087 of the 2,116 court-level moves have enough cases for a wait.
  - **Courts also differ in what their records show.**
    - Hradec Králové records a hearing in only 22% of cases, against 80% nationally: 14–24% in 2020–2024 and 41% in 2025. Chomutov records one in 92%.
    - At Prague 2, 26.5% of cases reach the appeal stage, against 6.3% nationally, and 23.1% go to the appeal court (Městský soud v Praze), against 4.3%.
    - Whether that's practice or record-keeping isn't known, and the project makes no claims about why.
- [x] Compare the exact intake with the official statistics, court by court and nationally (see "External check"). Every case's weight comes from those counts. It takes about 6 downloads from InfoData, one per year.
  - **In code:** `official.py` and `uv run soudai official` search InfoData's report form for S_AS_40, one year at a time, download each year's report as XML, and write `data/derived/official.csv`. That's our count beside the report's nápad, revived, disposed and pending, for every court-year and nationally. The client can now POST a web form, keyed in the cache apart from JSON. There are 7 new tests, on the real 2022 report.
  - **The runs:** 15 requests to cslav.justice.cz, with no failures. Runs 30–32 explored the form (4 requests), and run 33 did the rest (11). A run from scratch makes 13: the form page, then a search and a download per year. Each year's search lists exactly one report.
  - **The report's layout.** It has a block per region and a row per court, with 22 numbers under numbered columns. Nápad is the 2nd, and revived cases are split between the 1st and 3rd (by the rules before and after 2009). Náchod 2022 gives nápad 2,309 and 108 revived, as V(MS)-114 does. Every court appears once, and all four numbers add up to the national total in every year.
  - **Nationally, our counts run 0.43–0.53% above nápad every year:**

    | | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
    | --- | --- | --- | --- | --- | --- | --- |
    | Our count | 288,307 | 292,486 | 296,731 | 288,244 | 286,255 | 273,649 |
    | Nápad | 286,801 | 291,049 | 295,311 | 286,885 | 285,021 | 272,434 |
    | Gap | +0.53% | +0.49% | +0.48% | +0.47% | +0.43% | +0.45% |

  - **Court by court** (516 court-years), the median gap is +0.33% (8 cases). 95% are within +1.13%, and 24 match exactly. The largest is Šumperk in 2020, at +2.9% (52 cases). Only Pelhřimov in 2025 is below, by 5 cases (−0.6%), with no flag in intake. A small senate outside the searched range, or hidden numbers at the top of a senate's docket, could explain it; it isn't checked.
  - So the counts are registrations, a little above nápad everywhere, as step 4 found at Náchod ("zapsáno" against "nápad"), and the weights stand.
  - **Kept for step 10:** the report's cases disposed in the year, and pending at its end, nationally 130,342 at the end of 2020, falling to 96,558 at the end of 2025. That's an official backlog to set beside ours.
- [x] Record the headline figures here, and draft notes for the write-up in `docs/writeup.md`.
  - **Headline figures:**

    | | |
    | --- | --- |
    | Cases registered, 2020–2025 | 1,725,672, 0.43–0.53% above the official *nápad* each year |
    | Sampled case histories | 208,227, with 1,391,808 events |
    | Main routes | filed → hearing → decided → legally final 71.8%; the same with no hearing 15.6% |
    | Filing to a decision | median 149 days (quartiles 103 and 222) |
    | Filing to legally final | median 184 days (quartiles 133 and 265) |
    | Undecided after a year | 9.7% (not legally final: 13.1%) |
    | Courts' median to a decision | 92 days (Jeseník) to 238 (Prague 1, Litoměřice); the median court 144 |
    | Still open at the snapshot | 2.2% |

  - **`docs/writeup.md`** holds notes for Mark to write from: terms, the data, how it's counted, what it shows, and the caveats to keep. They're facts and figures, not copy.
  - **Fixed:** the journey tables were written with 6 significant digits, which rounded the national total to 1,725,210. They're written with 8 now.

Reordered with Mark on 2026-11-25: the model comes before the demo, and the Courts tab (German tank estimate, backlog and map) comes after the demo goes live.

### 7. The remaining-time model (PR)
- [ ] Build the comparison models and the GRU network (see "The remaining-time model"). Train and score them all on the same split: earlier registration years for training, later ones for testing.
  - **First PR (2026-11-25): the examples, the scores, and the two simplest methods.** `examples.py` cuts the histories, `scoring.py` scores forecasts, `baselines.py` has the court average and the process map, and `model.py` runs them as `uv run soudai model`, in about 40 s. 21 new tests. Decided here, and written into "The remaining-time model": the monthly cuts, the split on 1 January 2024, the validation share, and how each score is computed.
  - **Still to come:** Cox and gradient-boosted trees (LightGBM), then the GRU. PyTorch and LightGBM go in an optional dependency group, so CI's install stays light.
  - **Cases have got faster,** so every model trained on 2020–2023 expects the test cases to take longer than they did. The share of cases not yet finished 6 months after filing, by Kaplan–Meier with full follow-up, by year registered:

    | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
    | --- | --- | --- | --- | --- | --- |
    | 54.7% | 55.4% | 50.3% | 50.4% | 49.7% | 42.9% |

    The calibration tables show it: where the court average forecast a 45% chance of finishing within 6 months, 58% did. All the models train on the same years, so the comparison between them stays fair. Weighting recent years more, or correcting the forecasts afterwards, could reduce the gap. Neither is done yet.
- [ ] Record the scores here, model by model, by court and by how far into a case the forecast is made.
  - **The two simplest methods,** over all test forecasts (234,784, at filing and 1, 3, 6 and 12 months in). Higher concordance is better, and lower Brier and calibration error:

    | Model | Concordance | Brier 1 mo | 3 mo | 6 mo | 12 mo | 24 mo | Calibration error 6 mo | 12 mo |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | Court average | 0.602 | 0.069 | 0.174 | 0.203 | 0.094 | 0.043 | 5.8% | 2.2% |
    | Process map | 0.636 | 0.043 | 0.158 | 0.197 | 0.090 | 0.043 | 6.6% | 2.5% |

  - **By how far into a case.** At filing both know only the court, and score the same (concordance 0.604). Further in, the process map pulls ahead: concordance 0.625 against 0.604 at 1 month, 0.669 against 0.612 at 3, 0.720 against 0.547 at 6, and 0.733 against 0.540 at 12.
  - **By court.** Within one court, the court average gives every case at a landmark the same forecast, so its concordance there is 0.5, a coin toss: its 0.602 overall comes from ranking the courts. The process map's runs from 0.531 to 0.571 within a court. Its Brier score at 6 months is lower in 83 of the 86 courts.
- [ ] A Python reference and fixtures for what the demo recomputes: the network's forward pass, for made-up cases.
- [ ] Choose the real past cases the demo carries: a few thousand from the test years, with their histories and what happened next.

### 8. Forecast and process map: release status `in-progress`
- [ ] Move the demo to the latest demo-kit (see "Look") and bump `version`.
- [ ] Export `demo/public/data/soudai.json` (aim for under 500 KB; the bundle must stay under 2 MB).
- [ ] The frame, the tabs, the court selector, the status line and "How this works".
- [ ] The Forecast tab: real past cases (random, or by court and case number), made-up cases, and how well the model does (see "The experience"). Test the JS forward pass against the Python fixtures.
- [ ] The Process map tab and its time curves.
- [ ] The manifest, in Mark's copy, with `status: "in-progress"`. Render the stills. Fit the window.
- [ ] Tell Mark the release is out, so the project page can be listed once its write-up is out of draft.

### 9. Write-up: release status `live`
- [ ] Draft the write-up in `docs/writeup.md` for Mark, including a plain statement that nothing here is legal advice.
- [ ] Set `status: "live"` once Mark agrees, in a PR that bumps the version.

### 10. The Courts tab (after the demo is live)
- [ ] Settle the map geometry (see "Open questions") and record its source and licence.
- [ ] German tank estimates and intervals, compared with the exact counts by year, plus the undercount from senates with no published decisions.
  - `tank.py` was written ahead of this step, on 2026-11-22, with 61 tests against exact sums and brute-force simulation. The upper bound is the largest N with C(m, k)/C(N, k) ≥ 5%, found in floating point and settled exactly with whole numbers.
  - A court's upper bound is the 95th percentile of simulated totals. Each senate's N is drawn from its confidence distribution (P(draw ≥ n) = C(m, k)/C(n, k)), so for one senate the simulation gives back its exact bound.
  - In simulation the court bound covers the true total about 95% of the time when every senate has many published numbers. When some have only 1–3 it covers more often, with very wide bounds: sparse years such as 2020 will show that.
  - A senate with no published numbers can't be estimated, so `court_total` refuses it, and the undercount is reported separately.
- [ ] Backlog by Little's law, against the direct count.
- [ ] The Courts tab, the court panel and, as a stretch, the tank explainer, with a Python reference and fixtures for any maths the demo recomputes. Bump `version`.

## For Mark, on the site

- **The write-up.** `content/projects/soudai.md` is a draft with a TODO, which asks for a plain statement that the predictions aren't legal advice. The project makes predictions again, since 2026-11-23 (see "The remaining-time model"), so the statement matters.
- **The copy.** The tagline and summary ("Predicting how long court cases in the Czech Republic take") describe the old project. Mark rewrites them for the manifest and the site.
- **The README.** Reworded for the three tabs and the model on 2026-11-25, at Mark's request, keeping his wording where it still held. He edits it.
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
- **Filing date and case year** (settled with Mark, 2026-11-22). A case number's year is the year the case was entered in register C, not always the year it was filed. In the 54 Náchod cases fetched in step 2, 13 have a `ZAHAJ_RIZ` in the year before, mostly among a year's first numbers (11 of 2022's first 12). Likely causes are cases that began elsewhere and were moved into C, such as a payment order after an objection, a case from another register or court, or registration delays at the turn of the year. The official statistics point to the first: at Náchod in 2022, 1,757 of the 2,309 new register C cases were transferred from EPR, the electronic payment order register (see "External check"). So `ZAHAJ_RIZ` is probably the EPR filing date. That's inferred, not checked case by case. Settled: intake counts registrations and is labelled so, waits run from `ZAHAJ_RIZ`, and the check allows an earlier filing year (see "Decisions" and "Checks"). Still open: why it happens, which step 5's sample can show by court.
- **Hidden case numbers** (step 4; settle with Mark before step 5). infosoud doesn't show every case number. In 78 senate-years, case 1 is missing while later numbers exist, and in 17 of them case 2 or 3 is missing too. A senate's counter never skips, so the highest number still counts its registrations, and intake now searches past hidden numbers. What's open:
  - **Why.** Perhaps cases moved to another register or court, cases entered by mistake, or cases infosoud keeps private.
  - **How often** (measured in step 4). 108 of 22,315 random probes below a senate's top were hidden (0.48%), and case 1 in 78 of ~7,620 real senate-years (1.0%). In 38 senate-years the search met a hidden number where it would have stopped, and carried on past it.
  - **What it means for step 5** (settled with Mark, 2026-11-24). A sampled number that's hidden is skipped, and the next in the senate-year's order is drawn instead. Hidden numbers still count in the weights, since each senate-year's count includes them.
- **Older open cases.** The sample covers cases registered 2020–2025, so the direct backlog count misses older cases still open. A small extra sample of 2015–2019 registrations would close the gap if the numbers need it.
- **Senates above 100.** What are they (e.g. 112 at Okresní soud Ústí nad Orlicí)? Discovery has to cover them either way. A clue from step 2: one day's first page of decisions had senates 106, 112 and 117 at "Okresní soud v Karviné, pobočka Havířov" and 108 at Městský soud v Brně, so a branch's senates may be numbered from 100. Ústí nad Orlicí has no branch, though.
  - **Step 3's answer: they're common, and they come in series.** 22 courts have register C senates above 100 with cases of 2020–2025, usually the same endings under a new hundred.
    - Ústí nad Orlicí has 105–118, 205–218 and 305–317.
    - Kladno has 107–130, plus 207–233 with about 200 published cases each.
    - Karviná has 106–130, at about 400 each.
    - Brno has 104–119, 213–27x and 2104–2119.
    - Blansko has 702–715.
  - **Strays.** About a dozen single decisions sit far outside any series, such as 11297 at Náchod and 9249 at Liberec. They're probably typos.
  - **Still open:** what the hundreds mean.
  - **What step 4 needs.** Its rule probes every senate from 1 to the highest seen + 10, so one stray would cost thousands of probes, and the 1–250 sweep can't see the 300s or 2100s. The rule has to work by series instead, and since step 4 it does (see "Exact intake").
- **Official statistics.** Found: InfoData's S_AS_40 report, with V(MS)-114 for the breakdown (see "External check"). Step 4 answered which measure the counts match: "zapsáno". Náchod 2022 counts 2,326, against zapsáno 2,327 and nápad 2,309, and the national counts run about 0.5% above S_AS_40's nápad. Step 6 compared every court: settled, see step 6.
- **Publishing the snapshot.** The API can change or disappear, so it may be worth publishing the derived tables, for example as a release asset, if they're too large to commit. Step 3's decisions table (10.9 MB) stays local for now. Its subjects sometimes give a person's date of birth or address, so it can't be published as it is. Mark decided on 2026-11-22 to keep it private: nothing in the demo needs it.
- **Model card.** There's a model now (see "The remaining-time model"). Whether to add a model card for it is Mark's call. Its scores against the comparison models would be the figures in it.
- **Claim amounts.** `predmetRizeni` often gives the amount claimed, though 51,796 subjects have `[částka]` in its place (step 3). It's kept but not analysed. Splitting journeys by claim size would be a natural extension, if Mark wants it later.
- **Judges.** Discussed 2026-11-22: a judge-level aggregate (how much of the variation comes from the judge, with no names) was floated, and the scope Mark chose leaves judges out. The raw cache keeps `autor`; nothing derived does.
- **API stability.** If infosoud's API changes during a run, stop, record what changed here, and adapt the client. The cache keeps everything already fetched.
