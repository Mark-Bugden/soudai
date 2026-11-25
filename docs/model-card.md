# Model card: the facts

The facts for the demo's model card, gathered for Mark to write it from, as `docs/writeup.md` is for the write-up. They aren't copy. The headings follow Mitchell et al. (2019), "Model Cards for Model Reporting". The plan (`docs/plan.md`, "The remaining-time model" and step 7) has the details behind each item. The figures are from `uv run soudai model` on 2026-11-25.

## The model

- **What it forecasts:** for a civil case at a Czech district court, the chance it finishes in each of the next 36 months, given its court and its history so far. The demo shows the chances it finishes within 1, 3, 6 and 12 months.
- **Finished** means legally final, or closed in the register without becoming legally final (0.3% of cases).
- **Type:** an ensemble of 5 recurrent neural networks of the GRU type (Cho et al. 2014), each with a discrete-time survival output, also called "logistic hazard" (Gensheimer & Narasimhan 2019; Kvamme & Borgan 2021). The forecast is the mean of the five networks' forecasts.
- **What it reads:**
  - each event so far: its type (one of the 28 codes infosoud uses), the days since the previous event, and the days since filing;
  - at the moment of the forecast: the court, the days since the last event, and the days since filing.

  Nothing else: nothing about the parties, the claim, the judge or the contents of the case.
- **Size:** 7,228 weights per network, 36,140 in all.
- **Training:** PyTorch 2.15 on a CPU. Adam, with a learning rate of 0.0005. The loss is the likelihood of what happened next, with cases still open counted for as long as they're known to be open (censoring). Training stops when the loss on held-out training cases stops improving. The five networks differ only in their random start.
- **Date:** trained on 2026-11-25, on records fetched from infosoud between 20 and 25 November 2026.
- **Code:** https://github.com/Mark-Bugden/soudai, under the MIT License.

## Intended use

For Mark to write. Facts that bear on it:

- The project makes no claims about why courts differ, and isn't legal advice (the plan's "The goal").
- The model knows only a case's court and the dates and types of its events on infosoud.
- It learned from cases registered 2020–2023 at the 86 district-level courts, in register C (ordinary civil cases at first instance).

## Factors

The scores are broken down by:

- **court:** the 86 district-level courts;
- **how far into a case the forecast is made:** at filing, and 1, 3, 6 and 12 months after.

## Metrics

- **Concordance:** take two cases where one is known to have finished first. How often does the model expect that one to finish first? 0.5 is a coin toss and 1 is always right.
- **Brier score** at 1, 3, 6, 12 and 24 months: the mean of (outcome − forecast)², where the outcome is 1 if the case finished within that time and 0 if not, and the forecast is the chance the model gave. 0 is perfect, and always saying 50% scores 0.25. It's corrected for cases whose records ran out before then (inverse probability of censoring weights, Graf et al. 1999).
- **Calibration:** of the cases given, say, a 70% chance of finishing within 6 months, how many did? The forecasts are put in bins of 10 points, and the calibration error is the mean gap between forecast and outcome, weighted by the cases in each bin.

## Training data

- **Source:** infosoud.gov.cz, the courts' public case-tracking service. Its records hold no names.
- **Cases:** 138,815 civil cases registered 2020–2023, drawn at random (400 per court and year) and weighted to stand for all the cases registered in those years. That's 1,245,125 moments at which a forecast is made: every day with events, and every month after filing.
- **As of 31 December 2023:** anything dated after it is left out, so the model is the one that could have been built on 1 January 2024.
- **Recent cases count more:** a training example's weight halves for every year before 1 January 2024, because cases got faster over the years.
- **Held out:** a random 10% of the training cases, to decide when to stop training and to tune.

## Evaluation data

- **Cases:** 69,336 cases registered 2024–2025, none of them seen in training, followed to November 2026.
- **Forecasts scored:** each case at filing, and 1, 3, 6 and 12 months in while it's still open: 234,784 forecasts.

## Results

Higher concordance is better, and lower Brier score and calibration error. The other rows are the simpler methods it's compared with, trained and scored the same way:

| Method | Concordance | Brier 1 mo | 3 mo | 6 mo | 12 mo | Calibration error 6 mo |
| --- | --- | --- | --- | --- | --- | --- |
| Court average: the court's typical time, from the time since filing | 0.606 | 0.069 | 0.172 | 0.199 | 0.093 | 3.2% |
| Process map: the court, the stage the case is in and how long it's been there | 0.640 | 0.043 | 0.156 | 0.192 | 0.089 | 4.2% |
| Cox model on hand-made features | 0.607 | 0.058 | 0.179 | 0.199 | 0.095 | 4.5% |
| Gradient-boosted trees on the same features | 0.643 | 0.040 | 0.151 | 0.189 | 0.088 | 2.6% |
| The network on the same features | 0.640 | 0.042 | 0.154 | 0.190 | 0.089 | 2.0% |
| **The ensemble of 5 GRU networks** | **0.647** | **0.038** | **0.149** | **0.189** | **0.088** | **2.5%** |

- **Against the trees,** the strongest of the simpler methods: the ensemble ranks cases better and forecasts better 1 and 3 months ahead, the same 6 months ahead, and slightly worse 12 and 24 months ahead. A bootstrap over the test cases bears out each of these. So it doesn't clearly beat the trees.
- **Reading the events is what helps:** the same network fed hand-made features instead of the events does worse than the trees.
- **By how far into a case:** concordance is 0.610 at filing, then 0.635, 0.684, 0.742 and 0.757 at 1, 3, 6 and 12 months in. At filing the model knows only the court.
- **By court:** within a single court, concordance runs from 0.534 to 0.577. The Brier score at 6 months runs from 0.100 (Okresní soud Karlovy Vary) to 0.253 (Obvodní soud Praha 7), with a median of 0.189.

## Ethical considerations

- **Privacy:** infosoud's records hold no names. The judge's name, which the published decisions data includes, is dropped when it's read, and nothing in the model or the demo holds it.
- **Real cases:** the demo shows 3,010 real past cases by their case numbers, which are public on infosoud. Their records hold dates and event types only.
- **Courts' records differ:** some courts record far fewer hearings than others (Okresní soud Hradec Králové records a hearing in 22% of cases, against 80% nationally). So a forecast for a court reflects its record-keeping as well as its pace. Which it is isn't known, and the project makes no claims about it.

## Caveats

- **Cases got faster.** The share of cases unfinished 6 months after filing fell from 55% (registered 2020–2021) to 43% (2025). Even with recent cases weighted up, where the ensemble forecasts under a 60% chance of finishing within 6 months, 3 to 8 points more cases finish than it says.
- **At filing it can do little:** a case is then only its court, and every method but Cox ranks about 61% of pairs right (Cox 56%).
- **Filing dates:** for about 20% of cases, the filing date is in the year before the case was registered. That fits cases moved in from the electronic payment-order register, but it's inferred.
- **The newest cases are followed for less time:** cases registered in 2025 for 11 to 23 months. Scores correct for that, but long horizons rest on fewer cases.
- **infosoud keeps only a case's latest disposal date,** so a revived case's first disposal is lost.
- **The snapshot is November 2026.** infosoud's API is undocumented and can change.
