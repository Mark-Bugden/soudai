"""The forecasting examples (milestone 7): each case's history cut at the moments a forecast is made, with
what happened next. Every model is trained and scored on these, so they all see the same thing.

- **Histories.** A case's events are read as the stage model reads them (`events.log`): cancelled events,
  and events dated before the filing or after the record runs out, are left off. A case finishes when it
  becomes legally final, or at its closing in the register if it's closed without that (`events.outcomes`).
- **Cuts.** A forecast is made at the end of a day: every day with events before the case's end, and every
  month after filing (day 30, 61, 91 and so on, for MONTHLY months). Cutting at the end of a day keeps a
  hearing and its decision together, since they usually share a date, and `NAR_JED` is dated the day the
  hearing is held, so a forecast never knows of a hearing ahead. The monthly cuts are where nothing has
  happened for a while: how long a case has sat quiet is something a forecast has to read.
- **What happened next.** From each cut: the days `left` until the case finished, or until its record runs
  out if it hasn't (`ended` is then False, and the case is censored there).
- **The split.** Cases registered before SPLIT train the models, as their records stood the day before it.
  Cases registered from SPLIT on test them, followed to the snapshot. So the scores are those of models
  built on 1 January 2024 and used on the cases that came after, with nothing seen from after that day.
"""

from datetime import date, timedelta
from typing import NamedTuple

import numpy as np
import pandas as pd

from . import events

MONTH = 365.25 / 12  # days
HORIZON = 36  # months a forecast covers
MONTHLY = 60  # months after filing with a monthly cut
SPLIT = date(2024, 1, 1)
HALF_LIFE = 1  # years over which a training example's weight halves, the further it is before SPLIT
LANDMARKS = [0, 1, 3, 6, 12]  # months after filing at which forecasts are scored
VALIDATION = 0.1  # the share of training cases held out to stop training and tune
SEED = 20261125
DEMO_PER_COURT = 35  # real past cases the demo carries, per court

APPEAL = {code for code, stage in events.STAGE.items() if stage == "appeal"}
DECISION = {"VYD_ROZH", "ST_VEC_VYR"}
SHIFT = 1 << 20  # case id * SHIFT + day sorts a case's days within the case


def months_day(months):
    """The day after filing of the cut `months` months in: 0, 30, 61, 91, ..."""
    return int(round(months * MONTH))


def as_of(cases, day):
    """The cases' records as they stood at the end of `day`: they run to it at the latest."""
    return cases.assign(valid_to=[min(valid_to, day) for valid_to in cases["valid_to"]])


def split(cases, on=SPLIT):
    """(training cases, those registered before `on` as they stood the day before it; test cases, those
    registered from `on`'s year on, followed to the snapshot)."""
    train = cases[cases["year"] < on.year]
    return as_of(train, on - timedelta(days=1)), cases[cases["year"] >= on.year]


def recent(train, half_life=HALF_LIFE, until=SPLIT):
    """Training examples weighted for recency: each cut's weight halves for every `half_life` years
    between the day it was made and `until`, and so does each case's in `histories`, from its filing date.
    Cases got faster over the years (see docs/plan.md, step 7), so recent cuts are the better guide to
    the cases that come after. `half_life` None leaves the weights as they are."""
    if half_life is None:
        return train
    histories, cuts = train.histories, train.cuts
    filed = _days(np.full(len(histories), until), histories["filed"])  # days from filing to `until`
    before = filed[cuts["id"].to_numpy()] - cuts["day"].to_numpy()  # days from each cut to `until`
    years = 365.25 * half_life
    return Examples(
        histories.assign(weight=histories["weight"] * 0.5 ** (filed / years)),
        train.steps,
        cuts.assign(weight=cuts["weight"] * 0.5 ** (before / years)),
    )


def _days(later, earlier):
    return (np.array(later, dtype="datetime64[D]") - np.array(earlier, dtype="datetime64[D]")).astype(int)


class Examples(NamedTuple):
    histories: pd.DataFrame
    steps: pd.DataFrame
    cuts: pd.DataFrame


def build(cases, table):
    """Examples(histories, steps, cuts) for the cases, from their event table:
    - `histories`: one row per case with a filing that's still open at the end of its filing day: `id`
      (its row), the case, its weight, `filed`, `span` (days from filing to its end or censoring) and
      `ended`;
    - `steps`: its events in order, before the day of its end or censoring: `id`, `code`, `day` (days
      after filing) and `gap` (days since its previous event);
    - `cuts`: one row per forecast: `id`, `day`, `step` (the row of `steps` with the last event so far),
      `left` and `ended`, the case's `court` and `weight`, and the hand-made features: `stage` (on the
      journey map), `in_stage` (days since the case entered it), `since_last` (days since the last event),
      `events`, `hearings`, and whether it has been `decided`, `appealed` or `revived` so far.
    """
    log = events.log(cases, table)
    histories = events.outcomes(cases, table).merge(cases[events.CASE + ["weight"]], on=events.CASE)
    histories = histories.assign(span=_days(histories["until"], histories["filed"]))
    histories = histories[histories["span"] > 0].sort_values(events.CASE).reset_index(drop=True)
    histories = histories.assign(id=histories.index, ended=histories["end"].notna())
    histories = histories[["id"] + events.CASE + ["weight", "filed", "span", "ended"]]

    steps = log.merge(histories[events.CASE + ["id", "filed", "span"]], on=events.CASE)
    steps = steps.assign(day=_days(steps["date"], steps["filed"]))
    steps = steps[steps["day"] < steps["span"]].sort_values("id", kind="stable").reset_index(drop=True)
    by_case = steps.groupby("id")
    steps["gap"] = (steps["day"] - by_case["day"].shift()).fillna(0).astype(int)

    offsets = np.array([months_day(m) for m in range(1, MONTHLY + 1)])
    monthly = pd.DataFrame(
        {"id": np.repeat(histories["id"], len(offsets)), "day": np.tile(offsets, len(histories))}
    )
    monthly = monthly[monthly["day"] < histories["span"].to_numpy()[monthly["id"]]]
    cuts = pd.concat([steps[["id", "day"]], monthly]).drop_duplicates()
    cuts = cuts.sort_values(["id", "day"]).reset_index(drop=True)
    step_keys = steps["id"].to_numpy(np.int64) * SHIFT + steps["day"].to_numpy()
    step = np.searchsorted(step_keys, cuts["id"].to_numpy(np.int64) * SHIFT + cuts["day"].to_numpy(), "right")
    cuts["step"] = step - 1

    def so_far(mask):
        return mask.astype(int).groupby(steps["id"]).cumsum().to_numpy()[cuts["step"]]

    stage = steps["code"].map(events.STAGE).groupby(steps["id"]).ffill()
    entered = steps["day"].where(stage.ne(stage.groupby(steps["id"]).shift())).groupby(steps["id"]).ffill()
    case = cuts["id"].to_numpy()  # a case's id is its row in `histories`
    return Examples(
        histories,
        steps[["id", "code", "day", "gap"]],
        cuts.assign(
            left=histories["span"].to_numpy()[case] - cuts["day"],
            ended=histories["ended"].to_numpy()[case],
            court=histories["court"].to_numpy()[case],
            weight=histories["weight"].to_numpy()[case],
            stage=stage.to_numpy()[cuts["step"]],
            in_stage=cuts["day"] - entered.to_numpy()[cuts["step"]].astype(int),
            since_last=cuts["day"] - steps["day"].to_numpy()[cuts["step"]],
            events=so_far(pd.Series(True, index=steps.index)),
            hearings=so_far(steps["code"] == "NAR_JED"),
            decided=so_far(steps["code"].isin(DECISION)) > 0,
            appealed=so_far(steps["code"].isin(APPEAL)) > 0,
            revived=so_far(steps["code"] == events.REVIVED) > 0,
        ),
    )


def held_out(histories, share=VALIDATION, seed=SEED):
    """Whether each case is held out of training, to stop training and to tune: a fixed random share."""
    return np.random.default_rng(seed).random(len(histories)) < share


def scored(cuts):
    """The cuts at which forecasts are scored: each case at filing and 1, 3, 6 and 12 months after, while
    it's still open, with `landmark` the months."""
    days = {months_day(m): m for m in LANDMARKS}
    at = cuts[cuts["day"].isin(days)]
    return at.assign(landmark=at["day"].map(days))


def demo_cases(test, per_court=DEMO_PER_COURT, seed=SEED):
    """The real past cases the demo carries: `per_court` test cases from each court, drawn at random with
    chances in proportion to their weights, so they stand for all the court's registered cases rather than
    the sample. One row per case: the case, its filing date, the days to its end or censoring, and whether
    it finished."""
    rng = np.random.default_rng(seed)
    histories = test.histories
    chosen = []
    for _, rows in sorted(histories.groupby("court").indices.items()):
        weight = histories["weight"].to_numpy()[rows]
        n = min(per_court, len(rows))
        chosen.append(np.sort(rng.choice(rows, n, replace=False, p=weight / weight.sum())))
    return histories.iloc[np.concatenate(chosen)][events.CASE + ["filed", "span", "ended"]]
