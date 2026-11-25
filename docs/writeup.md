# Notes for the write-up

Facts and figures from steps 1–6, gathered for Mark to write the write-up from. They aren't copy. The plan (`docs/plan.md`) has the details behind each one, and the milestone it comes from is given in brackets.

## Terms

- **Register C:** the courts' register of ordinary civil cases at first instance. A case number such as `15 C 384/2022` is senate 15, register C, case 384 of 2022.
- **Senate:** a judge or panel of judges at a court, with its own numbering. Case numbers restart at 1 each year for each senate.
- **Registered:** entered in register C. A case's number gives the year it was registered, which for about one case in five is the year after it was filed.
- **Disposed** (*vyřízená*): the district court has issued the decision that ends its part of the case.
- **Legally final** (*pravomocná*): that decision can no longer be appealed.
- **Revived** (*obživlá*): a disposed case reopened because its decision was cancelled, after an objection or an appeal.
- **Censored:** a case still waiting when its record was fetched. It took at least that long, but how much longer isn't known.
- **Weight:** how many registered cases a sampled case stands for.

## The data

- **Sources:**
  - [rozhodnuti.justice.cz](https://rozhodnuti.justice.cz/), the public database of anonymised court decisions;
  - [infosoud.gov.cz](https://infosoud.gov.cz/), the courts' public case-tracking service;
  - the Ministry of Justice's InfoData statistics, cited as "Ministerstvo spravedlnosti ČR, InfoData".
- **Scope:** the 86 district-level courts, register C, cases registered 2020–2025.
- **Published decisions:** 616,458, all those published from 2020 to 21 November 2026 (step 3). Publication swings a lot by year (797 in 2020, 181,861 in 2022), so published decisions can't stand in for all cases.
- **Exact counts:** 1,725,672 cases registered in 2020–2025 (step 4):

  | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
  | --- | --- | --- | --- | --- | --- |
  | 288,307 | 292,486 | 296,731 | 288,244 | 286,255 | 273,649 |

- **Case histories:** 208,227 cases drawn at random, 400 per court and year, with 1,391,808 events between them (step 5). The records run to between 20 and 25 November 2026.
- **The scrape:** about 320,000 requests in all, every one cached and logged. That was at most 1 a second until step 5, then 3 a second.
- **Privacy:** infosoud's records hold no names. The judge's name in the decisions data is dropped when it's read, so no table, export or demo holds it. The decisions table stays private, because some decision subjects name people. Full texts were never fetched.

## How it's counted

- **Exact counts.** Within a senate and year, case numbers run 1, 2, 3… So the highest number that exists is the number of cases registered, and a binary search finds it in about 13 requests (step 4).
- **Hidden numbers.** infosoud doesn't show about 0.5% of case numbers. The count still holds, because the highest number counts every registration (step 4).
- **Check against the official statistics.** The counts run 0.43–0.53% above the Ministry's intake figure (*nápad*, report S_AS_40) every year. Court by court the median is +0.33%. The counts include every case entered in the register, which runs slightly above *nápad* (step 6).
- **The sample.** Cases are drawn by senate and year, and each carries a weight, so every share and time stands for all 1.73M registered cases (step 5).
- **Stages.** Each case's history becomes a path through seven stages: filed, hearing, decided, appeal, revived, suspended and legally final. Cancelled hearings, record-keeping events and events that haven't happened yet are left out. A case is finished when it becomes legally final (step 6, settled with Mark).
- **Waits.** Times are estimated so that cases still open count for as long as they're known to have waited. Dropping them would make the waits look shorter. The methods are Kaplan–Meier, and Aalen–Johansen where a stage has several ways out (step 6).

## What it shows (step 6)

- **Two routes cover 87% of cases:** filed → hearing → decided → legally final (71.8%), and the same with no hearing (15.6%).
- **The decision usually comes at the hearing:** in 90% of cases the first decision is on the day of the first hearing. A decision and its disposal fall on the same day in 96% of cases.
- **Time from filing,** for all courts:

  | | 25% of cases by | Median | 75% of cases by |
  | --- | --- | --- | --- |
  | To a decision | 103 days | 149 days | 222 days |
  | To legally final | 133 days | 184 days | 265 days |

- **Still waiting:** after 6 months, 36% of cases are undecided and 51% aren't yet legally final. After a year, it's 9.7% and 13.1%, and after two years 3.3% and 4.3%.
- **Appeals and revivals:** 4.3% of cases go to an appeal court, and 4.8% are revived. Most revivals involve no appeal court. They're probably payment orders that the defendant objected to, but that's inferred, not checked.
- **Courts differ:** the median time to a decision runs from 92 days (Jeseník) to 238 days (Prague 1 and Litoměřice), and the median court takes 144 days.
- **Courts also differ in what their records show.** Hradec Králové records a hearing in 22% of cases, against 80% nationally. At Prague 2, 23% of cases go to the appeal court, against 4.3%. Whether that's practice or record-keeping isn't known.

## The model (step 7, in progress)

- **The split.** The models learn from cases registered 2020–2023, as their records stood on 31 December 2023, and are tested on cases registered 2024–2025, followed to November 2026. So they're scored as if built on 1 January 2024 and used on the cases that came after.
- **Where forecasts are scored:** each test case at its filing, and 1, 3, 6 and 12 months after, while it's still open.
- **Cases have got faster.** The share not yet finished 6 months after filing, by year registered, is 54.7% (2020), 55.4%, 50.3%, 50.4%, 49.7% and 42.9% (2025). So models that learn from the earlier years expect later cases to take longer than they do.
- **The comparison methods so far.** Concordance is the share of pairs of cases ranked right: which of the two finishes first.
  - The court average (the court's typical curve, from the time since filing) ranks 60% right, and only by ranking courts: within one court it's a coin toss.
  - The process map (the court, the stage a case is in, and how long it has been there) ranks 64% right overall, and 72–73% for cases 6 or 12 months in.
  - A Cox model on hand-made features ranks 61% right. It assumes each feature scales the chance of finishing by the same factor at every time, which the stages break.
  - Gradient-boosted trees on the same features rank 64% right overall, and 74–75% for cases 6 or 12 months in.
  - At filing, a case has only its court, and every method ranks about 60% right.
- **The GRU network** reads a case's events one by one. It has 7,228 weights and trains in about 90 seconds on one CPU thread.
  - It ranks 64.2% right, against the trees' 63.8%, and 76% for cases 12 months in, against 75%.
  - **It doesn't clearly beat the trees.** It's better at ranking cases and at forecasts 3 months ahead. At 6 and 12 months its forecasts are about as good as the trees': a second network, trained the same way from another random start, does slightly worse than the trees at 6 months.
  - The same network fed the hand-made features instead of the events does worse than the trees. So what helps is reading the sequence of events, not a neural network as such.
  - Its calibration is the best of the methods: where it forecast a given chance of finishing within 6 months, the share that did was 4.0 points off on average, against 5.3 for the trees. Where it forecast under 70%, more cases finished than it said, by 3 to 10 points, which fits cases having got faster after the training years.

- **Recent cases count more in training.** A training example's weight halves for every year before 1 January 2024. The half-life was chosen on the training years alone: fitted on 2020–2022, checked on 2023. It makes every model's forecasts better calibrated: the trees' gap between forecast and outcome at 6 months falls from 5.3 to 2.6 points.
- **The demo's real past cases:** 3,010 cases registered in 2024–2025, 35 from each court, none of them seen in training.

## Caveats to keep

- The project makes no claims about why courts differ.
- Nothing here is legal advice. The write-up needs a plain statement of that, now that there's a model (the site's draft has a TODO for it).
- Times run from the filing date, which for 20% of cases is in the year before registration. That fits payment orders moved in from the electronic payment-order register, but it's inferred.
- infosoud keeps only a case's latest disposal date, so a revived case's first disposal is lost once it's decided again.
- 2.2% of cases were still open at the snapshot, mostly from 2024–2025. Their waits are censored, not dropped.
- The snapshot is the end of November 2026. infosoud's API is undocumented and can change.
