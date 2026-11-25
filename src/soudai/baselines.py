"""The simpler forecasts the network is compared with (milestone 7), each knowing more about a case than
the one before. Each is fitted on the training examples, and gives for each cut the chance the case is
still open 1, 2, ... HORIZON months later, as an array of shape (cuts, HORIZON).

1. **The court average** knows the court and how long ago the case was filed: the court's Kaplan–Meier
   curve from filing to the end, read from the day of the cut on.
2. **The process map** knows the court, the stage the case is in and how long it has been there: the
   Kaplan–Meier curve of the time left, over the training cuts in the same court and stage, with about
   as long in it.
3. **A Cox model** knows the hand-made features (`features`): the stage and the days in it, the days since
   filing and since the last event, the hearings so far, and whether the case has been decided, appealed
   or revived. Each court has its own baseline curve (the model is stratified by court), and the features
   scale its hazard up or down by the same factor at every time.
4. **Gradient-boosted trees** (LightGBM) know the same, and the court, and forecast each month's chance
   of finishing, given that the case is still open at its start (a discrete-time hazard, as the network
   does). Each training cut becomes one row per month it's known to be open, up to the month it finished.
   They need the optional `model` dependency group: `uv sync --group model`.
"""

import warnings

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter

from . import events, examples, survival
from .examples import HORIZON, MONTH

GRID = np.arange(1, HORIZON + 1) * MONTH  # days after a cut, for each month of a forecast
MIN_AT_RISK = 20  # sampled cases still open, to read a court's curve from a given day
MIN_CUTS = 50  # sampled cuts, for a court's own curve in a stage
STAGE_DAYS = [0, 1, 31, 92, 183, 366]  # the process map's bins of days in the stage: 0, 1–30, ..., 366+
COX_CUTS = 200_000  # training cuts the Cox model is fitted on, drawn at random
TREES = {  # LightGBM's settings
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.9,
    "verbose": -1,
    "seed": examples.SEED,
}
FEATURES = ["since_filing", "since_last", "in_stage", "hearings", "decided", "appealed", "revived"]
FEATURES += [f"in_{stage}" for stage in events.STAGES[1:-1]]  # the stage, but "filed" (and "final")
TREE_ROUNDS, TREE_PATIENCE = 2000, 50  # at most, and stopping when the held-out loss stalls this long


def court_average(train, cuts):
    """The court's curve from filing, from the cut's day: S(day + t) / S(day). Where fewer than MIN_AT_RISK
    of the court's training cases were still open on that day, it's read from the last day that had them."""
    histories = train.histories
    out = np.empty((len(cuts), HORIZON))
    for court, rows in cuts.groupby("court").indices.items():
        own = histories[histories["court"] == court]
        times, still = survival.kaplan_meier(own["span"], own["ended"], own["weight"])
        spans = np.sort(own["span"].to_numpy())[::-1]
        last = spans[MIN_AT_RISK - 1] - 1 if len(spans) >= MIN_AT_RISK else 0
        day = np.minimum(cuts["day"].to_numpy()[rows], last)
        now = survival.at(times, still, day, before=1.0)
        later = survival.at(times, still, day[:, None] + GRID[None, :], before=1.0)
        out[rows] = later / np.maximum(now, 1e-12)[:, None]
    return out


def stage_bins(in_stage):
    return np.searchsorted(STAGE_DAYS, in_stage, side="right") - 1


def process_map(train, cuts):
    """The time left over the training cuts in the same court, stage and bin of days in the stage. Where
    the court has fewer than MIN_CUTS of them, all courts' are used, and failing that, all courts' in the
    stage."""
    pool = train.cuts.assign(bin=stage_bins(train.cuts["in_stage"]))
    curves = {}
    for keys in (["court", "stage", "bin"], ["stage", "bin"], "stage"):
        for key, rows in pool.groupby(keys).indices.items():
            if len(rows) >= MIN_CUTS:
                left, ended, weight = (pool[c].to_numpy()[rows] for c in ["left", "ended", "weight"])
                times, still = survival.kaplan_meier(left, ended, weight)
                curves[key] = survival.at(times, still, GRID, before=1.0)
    cuts = cuts.assign(bin=stage_bins(cuts["in_stage"]))
    out = np.empty((len(cuts), HORIZON))
    for (court, stage, b), rows in cuts.groupby(["court", "stage", "bin"]).indices.items():
        out[rows] = next(curves[k] for k in [(court, stage, b), (stage, b), stage] if k in curves)
    return out


def features(cuts):
    """The hand-made features of each cut, as numbers. Days are on a log scale, log(1 + days), and the
    stage is one column per stage but "filed", such as `in_hearing`."""
    out = pd.DataFrame(
        {
            "since_filing": np.log1p(cuts["day"].to_numpy()),
            "since_last": np.log1p(cuts["since_last"].to_numpy()),
            "in_stage": np.log1p(cuts["in_stage"].to_numpy()),
            "hearings": np.minimum(cuts["hearings"].to_numpy(), 5),
            "decided": cuts["decided"].to_numpy(dtype=float),
            "appealed": cuts["appealed"].to_numpy(dtype=float),
            "revived": cuts["revived"].to_numpy(dtype=float),
        }
    )
    for stage in events.STAGES[1:-1]:
        out[f"in_{stage}"] = (cuts["stage"].to_numpy() == stage).astype(float)
    return out[FEATURES]


def _draw(cuts, n):
    """Up to n of the cuts, drawn at random. The draw is uniform, so the weights stand as they are."""
    if len(cuts) <= n:
        return cuts
    rows = np.random.default_rng(examples.SEED).choice(len(cuts), n, replace=False)
    return cuts.iloc[np.sort(rows)]


def cox(train, cuts):
    """A Cox model stratified by court, fitted on COX_CUTS training cuts."""
    sample = _draw(train.cuts, COX_CUTS)
    x = features(sample)
    x = x.loc[:, x.std() > 0]  # a feature that never varies can't be fitted
    data = x.assign(
        court=sample["court"].to_numpy(),
        left=sample["left"].to_numpy(),
        ended=sample["ended"].to_numpy(),
        weight=sample["weight"].to_numpy(),
    )
    fitter = CoxPHFitter()
    with warnings.catch_warnings():  # lifelines warns that non-integer weights need robust errors
        warnings.simplefilter("ignore")
        fitter.fit(data, "left", "ended", weights_col="weight", strata=["court"])
    at = features(cuts)[x.columns].assign(court=cuts["court"].to_numpy())
    return fitter.predict_survival_function(at, times=GRID).to_numpy().T


def months(cuts):
    """The rows the trees learn from: one per month each cut is known to be open at the start of, up to
    HORIZON. (row's cut, month, whether the case finished that month)."""
    left, ended = cuts["left"].to_numpy(), cuts["ended"].to_numpy()
    finished = np.ceil(left / MONTH).astype(int)  # the month it finished in, if it did
    ended = ended & (finished <= HORIZON)
    known = np.where(ended, finished, np.minimum(np.floor(left / MONTH).astype(int), HORIZON))
    cut = np.repeat(np.arange(len(cuts)), known)
    month = np.arange(len(cut)) - np.repeat(np.cumsum(known) - known, known) + 1
    return cut, month, ended[cut] & (month == finished[cut])


def _tree_data(cuts, courts, month):
    data = features(cuts)
    data["court"] = pd.Categorical(cuts["court"].to_numpy(), categories=courts).codes
    return data.assign(month=month)


def trees(train, cuts):
    """Gradient-boosted trees, fitted on the training cuts and stopped on the held-out cases' cuts."""
    import lightgbm

    courts = sorted(train.cuts["court"].unique())
    held = examples.held_out(train.histories)[train.cuts["id"].to_numpy()]
    sets = []
    for part in (train.cuts[~held], train.cuts[held]):
        cut, month, finished = months(part)
        rows = part.iloc[cut]
        sets.append((_tree_data(rows, courts, month), finished, rows["weight"].to_numpy()))
    (x, y, w), (vx, vy, vw) = sets
    data = lightgbm.Dataset(x, y, weight=w, categorical_feature=["court"])
    valid = lightgbm.Dataset(vx, vy, weight=vw, reference=data)
    booster = lightgbm.train(
        TREES,
        data,
        TREE_ROUNDS,
        valid_sets=[valid],
        callbacks=[lightgbm.early_stopping(TREE_PATIENCE, verbose=False)],
    )
    every = cuts.iloc[np.repeat(np.arange(len(cuts)), HORIZON)]
    month = np.tile(np.arange(1, HORIZON + 1), len(cuts))
    hazard = booster.predict(_tree_data(every, courts, month), num_iteration=booster.best_iteration)
    return np.cumprod(1 - hazard.reshape(len(cuts), HORIZON), axis=1)
