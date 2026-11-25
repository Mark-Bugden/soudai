"""The remaining-time model (milestone 7): the forecasts are fitted on the training cases and scored on the
test cases (see `examples` for the split, and `scoring` for the scores).

Writes data/derived/model_scores.csv, with each model's scores for all courts and for each court, over
all the landmarks and at each (`court` and `landmark` are "all" for all of them), and
data/derived/model_calibration.csv, with each model's calibration tables over all of them. For the demo,
the network's weights go to data/derived/network.json, and the real past cases it carries to
data/derived/demo_cases.csv.

The trees and the networks need the optional `model` dependency group: `uv sync --group model`.

    uv run soudai model
"""

import json
import time

import numpy as np
import pandas as pd

from . import baselines, examples, forward, journey, paths, scoring

SCORES = paths.DERIVED / "model_scores.csv"
CALIBRATION = paths.DERIVED / "model_calibration.csv"
NETWORK = paths.DERIVED / "network.json"
DEMO_CASES = paths.DERIVED / "demo_cases.csv"
CHECKED = 500  # test forecasts on which the numpy forward pass is checked against PyTorch


def features_network(train, test, at):
    """The network's output layers, fed the hand-made features instead of the GRU's hidden state."""
    from . import network

    model, _ = network.fit(train, sequence=False)
    return network.still_open(model, network.Data(test, at))


def gru(train, test, at):
    """The GRU network. Its weights are written for the demo, and the numpy forward pass checked on them."""
    from . import network

    model, _ = network.fit(train)
    weights = network.weights(model)
    NETWORK.write_text(json.dumps(weights, separators=(",", ":")) + "\n", encoding="utf-8")
    still = network.still_open(model, network.Data(test, at))
    gap = check_forward(weights, test, at, still)
    print(f"  the numpy forward pass matches PyTorch on {CHECKED} test forecasts, to {gap:.1e}")
    return still


MODELS = {
    "court average": lambda train, test, at: baselines.court_average(train, at),
    "process map": lambda train, test, at: baselines.process_map(train, at),
    "cox": lambda train, test, at: baselines.cox(train, at),
    "trees": lambda train, test, at: baselines.trees(train, at),
    "features network": features_network,
    "gru": gru,
}


def check_forward(weights, test, at, still, n=CHECKED):
    """The largest gap between `forward` and PyTorch's forecasts, on n of the scored cuts drawn at random.
    Raises if it's over 1e-5."""
    rows = np.random.default_rng(examples.SEED).choice(len(at), min(n, len(at)), replace=False)
    first = np.searchsorted(test.steps["id"].to_numpy(), at["id"].to_numpy()[rows])
    gap = 0.0
    for row, start in zip(rows, first, strict=True):
        cut = at.iloc[row]
        steps = test.steps.iloc[start : cut["step"] + 1]
        events = list(zip(steps["code"], steps["day"], strict=True))
        ours = forward.still_open(weights, cut["court"], events, cut["day"])
        gap = max(gap, np.abs(ours - still[row]).max())
    if gap > 1e-5:
        raise AssertionError(f"the numpy forward pass is {gap:.1e} off PyTorch's")
    return gap


def prepare():
    """(training examples, weighted for recency; test examples)."""
    cases, table = journey.load()
    train, test = examples.split(cases)
    return examples.recent(examples.build(train, table)), examples.build(test, table)


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
    chosen = examples.demo_cases(test)
    chosen.to_csv(DEMO_CASES, index=False, lineterminator="\n")
    print(f"Wrote the demo's {len(chosen):,} real past cases to {DEMO_CASES}")
    forecasts = {}
    for name, fit in MODELS.items():
        forecasts[name] = fit(train, test, at)
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
