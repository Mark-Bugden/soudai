"""The remaining-time model (milestone 7): the forecasts are fitted on the training cases and scored on the
test cases (see `examples` for the split, and `scoring` for the scores).

Writes data/derived/model_scores.csv, with each model's scores for all courts and for each court, over
all the landmarks and at each (`court` and `landmark` are "all" for all of them), and
data/derived/model_calibration.csv, with each model's calibration tables over all of them.

    uv run soudai model
"""

import time

import numpy as np
import pandas as pd

from . import baselines, examples, journey, paths, scoring

MODELS = {
    "court average": baselines.court_average,
    "process map": baselines.process_map,
}
SCORES = paths.DERIVED / "model_scores.csv"
CALIBRATION = paths.DERIVED / "model_calibration.csv"


def prepare():
    """(training examples, test examples)."""
    cases, table = journey.load()
    train, test = examples.split(cases)
    return examples.build(train, table), examples.build(test, table)


def censoring_weights(at):
    """{horizon: each scored cut's censoring weight}, estimated at each landmark over all courts."""
    out = {h: np.zeros(len(at)) for h in scoring.HORIZONS}
    for rows in at.groupby("landmark").indices.values():
        left, ended, weights = (at[c].to_numpy()[rows] for c in ["left", "ended", "weight"])
        for h in scoring.HORIZONS:
            out[h][rows] = scoring.censoring_weights(left, ended, weights, h)
    return out


def score_tables(forecasts, at):
    """(scores, calibration) as DataFrames, for {model: forecasts at the scored cuts `at`}."""
    ipcw = censoring_weights(at)
    groups = [("all", "all", np.arange(len(at)))]
    groups += [(court, "all", rows) for court, rows in sorted(at.groupby("court").indices.items())]
    groups += [("all", m, rows) for m, rows in sorted(at.groupby("landmark").indices.items())]
    scores, calibration = [], []
    for name, still in forecasts.items():
        for court, landmark, rows in groups:
            weights = {h: w[rows] for h, w in ipcw.items()}
            row = scoring.score(still[rows], at.iloc[rows], weights)
            scores.append({"model": name, "court": court, "landmark": landmark} | row)
        for h in scoring.CALIBRATION:
            table = scoring.calibration(still, at["left"], at["ended"], at["weight"], h)
            calibration.append(table.assign(model=name, horizon=h))
    columns = ["model", "horizon", "bin", "weight", "sampled", "forecast", "observed"]
    return pd.DataFrame(scores), pd.concat(calibration)[columns]


def run():
    start = time.time()
    train, test = prepare()
    at = examples.scored(test.cuts)
    print(
        f"Training: {len(train.histories):,} cases, {len(train.cuts):,} cuts. Test: {len(test.histories):,} "
        f"cases, {len(at):,} scored cuts ({time.time() - start:.0f} s)"
    )
    forecasts = {}
    for name, fit in MODELS.items():
        forecasts[name] = fit(train, at)
        print(f"Fitted {name} ({time.time() - start:.0f} s)")
    scores, calibration = score_tables(forecasts, at)
    scores.to_csv(SCORES, index=False, float_format="%.6g", lineterminator="\n")
    calibration.to_csv(CALIBRATION, index=False, float_format="%.6g", lineterminator="\n")
    print(f"Wrote {len(scores):,} rows to {SCORES} and {len(calibration):,} to {CALIBRATION}")
    overall = scores[(scores["court"] == "all") & (scores["landmark"] == "all")].set_index("model")
    columns = ["concordance"] + [f"brier_{h}" for h in scoring.HORIZONS]
    columns += [f"calibration_{h}" for h in scoring.CALIBRATION]
    print(overall[columns].round(4).to_string())
    return 0
