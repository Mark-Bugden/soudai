"""The simpler forecasts the network is compared with (milestone 7), each knowing more about a case than
the one before. Each is fitted on the training examples, and gives for each cut the chance the case is
still open 1, 2, ... HORIZON months later, as an array of shape (cuts, HORIZON).

1. **The court average** knows the court and how long ago the case was filed: the court's Kaplan–Meier
   curve from filing to the end, read from the day of the cut on.
2. **The process map** knows the court, the stage the case is in and how long it has been there: the
   Kaplan–Meier curve of the time left, over the training cuts in the same court and stage, with about
   as long in it.
"""

import numpy as np

from . import survival
from .examples import HORIZON, MONTH

GRID = np.arange(1, HORIZON + 1) * MONTH  # days after a cut, for each month of a forecast
MIN_AT_RISK = 20  # sampled cases still open, to read a court's curve from a given day
MIN_CUTS = 50  # sampled cuts, for a court's own curve in a stage
STAGE_DAYS = [0, 1, 31, 92, 183, 366]  # the process map's bins of days in the stage: 0, 1–30, ..., 366+


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
