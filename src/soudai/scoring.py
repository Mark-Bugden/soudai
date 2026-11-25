"""How well a forecast does (milestone 7). Every model is scored the same way, on the same cuts.

A forecast is a case's chance of still being open 1, 2, ... HORIZON months after the cut: `still[:, k - 1]`
for month k. A case's outcome is the days `left` from the cut until it finished, or until its record ran
out if it hasn't (`ended` False: censored). Every case counts with its weight.

- **Concordance** (Harrell's C): of the pairs of cases where one is known to finish first, the share where
  the forecast expected it to, by the expected months left (up to HORIZON). 0.5 is guessing, 1 is perfect.
- **The Brier score** at a horizon of h months: the mean of (outcome − forecast)², where the outcome is 1
  if the case finished within h months and the forecast is the chance it would. 0 is perfect, and always
  forecasting 50% scores 0.25. A case censored before h months has no outcome, so the cases that do are
  weighted up to stand for it: each by 1 / the chance a case's record runs at least that long, from a
  Kaplan–Meier curve of the censoring (inverse probability of censoring weights, Graf et al. 1999).
- **Calibration** at h months: the forecasts in bins of 10 points (0–10%, 10–20%, ...), against the share
  of those cases that finished within h months, by Kaplan–Meier. A forecast of 70% should come true 70%
  of the time. Its summary is the mean gap between the two, weighted by the cases in each bin.
"""

import numpy as np
import pandas as pd

from . import survival
from .examples import MONTH

HORIZONS = [1, 3, 6, 12, 24]  # months, for the Brier score
CALIBRATION = [1, 3, 6, 12]  # months, for calibration: those the demo shows
BINS = 10


def expected_months(still):
    """The expected months left, counting only the first HORIZON: the area under the curve."""
    return 1 + still[:, :-1].sum(axis=1)


def concordance(score, left, ended, weights):
    """Harrell's C, weighted: a pair weighs the product of its cases' weights. Case i is known to finish
    before case j when it finished, after fewer days than j, or than j was censored after; a pair finishing
    on the same day doesn't count. It's right when i's score is the lower, and half right when they tie."""
    right, pairs = _pairs(score, left, ended, weights)
    return right / pairs if pairs else np.nan


def _pairs(score, left, ended, weights):
    """(the weight of the pairs Harrell's C gets right, counting ties as a half; the weight of all the
    pairs it compares), so the pairs of several groups can be pooled."""
    score, left = np.asarray(score, dtype=float), np.asarray(left)
    ended, weights = np.asarray(ended, dtype=bool), np.asarray(weights, dtype=float)
    ranks = np.unique(score, return_inverse=True)[1] + 1
    tree = np.zeros(ranks.max(initial=0) + 1)  # a Fenwick tree of weights by rank, for cases seen so far

    def below(at):  # weight seen with rank <= at, for each of an array of ranks
        total, at = np.zeros(len(at)), at.copy()
        while (at > 0).any():
            total += np.where(at > 0, tree[at], 0)
            at -= at & -at
        return total

    def add(at, weight):
        at = at.copy()
        while len(at):
            np.add.at(tree, at, weight)
            at = at + (at & -at)
            keep = at < len(tree)
            at, weight = at[keep], weight[keep]

    right = tied = pairs = seen = 0.0
    order = np.lexsort((ended, -left))  # latest first, and on a day, the censored before those that ended
    days, starts = np.unique(-left[order], return_index=True)
    for group in np.split(order, starts[1:]):
        out = group[~ended[group]]
        add(ranks[out], weights[out])
        seen += weights[out].sum()
        done = group[ended[group]]
        if len(done):
            w, r = weights[done], ranks[done]
            at_most, lower = below(r), below(r - 1)
            right += (w * (seen - at_most)).sum()
            tied += (w * (at_most - lower)).sum()
            pairs += w.sum() * seen
            add(r, w)
            seen += w.sum()
    return right + tied / 2, pairs


def censoring_weights(left, ended, weights, horizon):
    """Each case's weight for the Brier score at `horizon` months: 1 / G(its days left) if it finished by
    then, 1 / G(the horizon) if it was still open then, and 0 if it was censored before. G is the chance a
    record runs longer than a given time, by Kaplan–Meier on the censored cases, taken just before."""
    left, ended = np.asarray(left), np.asarray(ended, dtype=bool)
    times, kept = survival.kaplan_meier(left, ~ended, weights)
    days = horizon * MONTH
    by = survival.at(times, kept, np.minimum(left, days) - 0.5, before=1.0)
    by = np.where(left > days, survival.at(times, kept, np.array([days]), before=1.0)[0], by)
    known = (left > days) | ended
    return np.where(known, 1 / np.maximum(by, 1e-9), 0.0)


def brier(still, left, ended, weights, horizon, ipcw=None):
    """The censoring-corrected Brier score at `horizon` months. `ipcw` are the censoring weights, if the
    censoring is to be estimated on more cases than these (all courts, for one court's score, say)."""
    left, weights = np.asarray(left), np.asarray(weights, dtype=float)
    ipcw = censoring_weights(left, ended, weights, horizon) if ipcw is None else ipcw
    finished = (left <= horizon * MONTH) & np.asarray(ended, dtype=bool)
    forecast = 1 - still[:, horizon - 1]
    return (weights * ipcw * (finished - forecast) ** 2).sum() / weights.sum()


def calibration(still, left, ended, weights, horizon, bins=BINS):
    """The calibration table at `horizon` months: for each bin of forecasts, the cases' weight, how many
    were sampled, the mean forecast and the share that finished within the horizon."""
    forecast = 1 - still[:, horizon - 1]
    which = np.minimum((forecast * bins).astype(int), bins - 1)
    left, ended, weights = np.asarray(left), np.asarray(ended, dtype=bool), np.asarray(weights, dtype=float)
    rows = []
    for b in range(bins):
        mask = which == b
        if not mask.any():
            continue
        times, open_ = survival.kaplan_meier(left[mask], ended[mask], weights[mask])
        rows.append(
            {
                "bin": b,
                "weight": weights[mask].sum(),
                "sampled": int(mask.sum()),
                "forecast": np.average(forecast[mask], weights=weights[mask]),
                "observed": 1 - survival.at(times, open_, np.array([horizon * MONTH]), before=1.0)[0],
            }
        )
    return pd.DataFrame(rows)


def calibration_error(table):
    """The mean gap between forecast and observed, weighted by the cases in each bin."""
    return np.average((table["forecast"] - table["observed"]).abs(), weights=table["weight"])


def score(still, cuts, ipcw=None):
    """Concordance, and the Brier score and calibration error at each horizon, for one set of forecasts
    and the cuts they were made at ({name: value}). Concordance only compares cases at the same landmark,
    and `ipcw` gives the censoring weights by horizon, if they're estimated on more cases than these."""
    left, ended, weights = cuts["left"].to_numpy(), cuts["ended"].to_numpy(), cuts["weight"].to_numpy()
    out = {"cuts": len(cuts), "weight": weights.sum()}
    expected = expected_months(still)
    right = pairs = 0.0
    for rows in cuts.groupby("landmark").indices.values():
        r, n = _pairs(expected[rows], left[rows], ended[rows], weights[rows])
        right, pairs = right + r, pairs + n
    out["concordance"] = right / pairs if pairs else np.nan
    for h in HORIZONS:
        weight = None if ipcw is None else ipcw[h]
        out[f"brier_{h}"] = brier(still, left, ended, weights, h, weight)
    for h in CALIBRATION:
        out[f"calibration_{h}"] = calibration_error(calibration(still, left, ended, weights, h))
    return out
