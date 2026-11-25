"""The demo's data (milestone 8): demo/public/data/soudai.json, from the committed derived tables. CI builds
the demo without running the pipeline, so the file is committed too.

It holds only what the demo's tabs need:
- `courts` and `codes`: the 86 courts and the 28 event codes, in the order of the network's rows, with each
  court's name and area, and each code's English gloss and stage on the journey map (null if it has none).
- `network`: the ensemble's weights (data/derived/network.json). Each matrix is stored as 16-bit integers
  with one scale, so a weight is its integer × the scale, in base64, little-endian. That's 96 KB against
  469 KB at 9 digits, and it moves no forecast of the demo's real cases by more than 0.0001.
- `cases`: the real past cases the Forecast tab carries (data/derived/demo_cases.csv), each with its
  events as the network reads them (`examples.build`), and those on the day it finished or its record ran
  out, which the network never reads. A forecast on day d reads the events up to the end of day d. Its
  filing date is in days after `split`, and `ended` is 1 or 0, to save space.
- `scores` and `calibration`: each model's scores on the test years (data/derived/model_scores.csv and
  model_calibration.csv), but for the ensemble's first network alone.
- `journey`: for the whole country ("all") and each court, the process map's numbers (data/derived/
  journey_*.csv), with each court's exact count of cases registered from intake.

    uv run soudai export
"""

import base64
import json

import numpy as np
import pandas as pd

from . import events, examples, journey, model, paths, reference

MAX_BYTES = 500_000  # the bundle's limit is 2 MB, for everything
LEVELS = 32767  # the largest 16-bit integer
ENDINGS = ["final", "closed", "open"]
PLACES = events.STAGES + ["closed"]  # where a move can go: a stage, or closed in the register
LEFT_OUT = {"gru"}  # the ensemble's first network alone: the demo runs the ensemble
METRICS = (
    ["concordance"] + [f"brier_{h}" for h in [1, 3, 6, 12, 24]] + [f"calibration_{h}" for h in [1, 3, 6, 12]]
)
DIGITS = 4  # significant digits for shares and scores
CURVE_DIGITS = 3  # decimal places for the time curves, which are only drawn


def encode(values):
    """A weight matrix as 16-bit integers with one scale: {shape, scale, values}, the values in base64."""
    values = np.asarray(values, dtype=float)
    scale = float(np.abs(values).max()) / LEVELS or 1.0
    ints = np.round(values / scale).astype("<i2")
    return {"shape": list(values.shape), "scale": scale, "values": base64.b64encode(ints.tobytes()).decode()}


def decode(encoded):
    """The weights `encode` stored, as the demo reads them."""
    ints = np.frombuffer(base64.b64decode(encoded["values"]), dtype="<i2")
    return (ints * encoded["scale"]).reshape(encoded["shape"])


def network(weights):
    """The network's weights as the export stores them."""
    members = [{name: encode(values) for name, values in member.items()} for member in weights["members"]]
    return {"horizon": weights["horizon"], "members": members}


def decoded(exported, weights):
    """The exported network as `forward.still_open` reads it, with its codes and courts."""
    members = [
        {name: decode(values).tolist() for name, values in member.items()} for member in exported["members"]
    ]
    return {
        "codes": weights["codes"],
        "courts": weights["courts"],
        "horizon": exported["horizon"],
        "members": members,
    }


def real_cases(cases, table, chosen, codes, courts):
    """The demo's real past cases, in `chosen`'s order: court (its row in `courts`), senate, number, year,
    filed (days after SPLIT), span (days from filing to its end, or to the day its record runs to), ended
    (1 or 0), and its events as [code (its row in `codes`), day after filing, ...], up to and including the
    day of its end."""
    chosen = chosen.reset_index(drop=True).assign(row=lambda frame: frame.index)
    subset = cases.merge(chosen[events.CASE], on=events.CASE)
    subset_table = table.merge(chosen[events.CASE], on=events.CASE)
    built = examples.build(subset, subset_table)
    histories = built.histories.merge(chosen[events.CASE + ["row"]], on=events.CASE)
    check = histories.merge(chosen, on=events.CASE + ["row"], suffixes=("", "_chosen"))
    check = check.assign(filed=check["filed"].astype(str))
    for column in ["filed", "span", "ended"]:
        if not (check[column] == check[f"{column}_chosen"]).all():
            raise AssertionError(f"the demo's cases have changed since `soudai model` chose them: {column}")
    if len(histories) != len(chosen):
        raise AssertionError(f"{len(chosen) - len(histories)} of the demo's cases have no history")

    # The events on the day the case ends or its record runs out: never read by the network.
    log = events.log(subset, subset_table).merge(
        histories[events.CASE + ["id", "filed", "span"]], on=events.CASE
    )
    log = log.assign(day=examples._days(log["date"], log["filed"]))
    last = log[log["day"] == log["span"]][["id", "code", "day"]]
    steps = pd.concat([built.steps[["id", "code", "day"]], last]).sort_values("id", kind="stable")

    code_row = {code: i for i, code in enumerate(codes)}
    court_row = {code: i for i, code in enumerate(courts)}
    pairs = {i: [] for i in histories["id"]}
    for i, code, day in zip(steps["id"], steps["code"], steps["day"], strict=True):
        pairs[i] += [code_row[code], int(day)]
    by_row = histories.sort_values("row")
    filed = examples._days(by_row["filed"], np.full(len(by_row), examples.SPLIT))
    return [
        [
            court_row[row.court],
            int(row.senate),
            int(row.number),
            int(row.year),
            int(day),
            int(row.span),
            int(row.ended),
            pairs[row.id],
        ]
        for row, day in zip(by_row.itertuples(), filed, strict=True)
    ]


def _number(value):
    return None if pd.isna(value) else float(f"{value:.{DIGITS}g}")


def _curve(value):
    return round(float(value), CURVE_DIGITS)


def _days(value):
    return None if pd.isna(value) else int(value)


def scores(table):
    """Each model's scores, for all courts and each court, over all landmarks and at each."""
    table = table[~table["model"].isin(LEFT_OUT)]
    columns = ["model", "court", "landmark", "cuts"] + METRICS
    rows = [
        [row["model"], row["court"], row["landmark"], int(row["cuts"])] + [_number(row[m]) for m in METRICS]
        for _, row in table.iterrows()
    ]
    return {"columns": columns, "rows": rows}


def calibration(table):
    """Each model's calibration tables: for each horizon and bin of 10 points, the share of the forecasts
    in the bin (weighted), the mean forecast and the share of cases that finished within the horizon."""
    table = table[~table["model"].isin(LEFT_OUT)]
    total = table.groupby(["model", "horizon"])["weight"].transform("sum")
    table = table.assign(share=table["weight"] / total)
    columns = ["model", "horizon", "bin", "share", "forecast", "observed"]
    rows = [
        [row["model"], int(row["horizon"]), int(row["bin"])] + [_number(row[c]) for c in columns[3:]]
        for _, row in table.iterrows()
    ]
    return {"columns": columns, "rows": rows}


def journeys(tables, registered):
    """{scope: the process map's numbers}, for "all" and each court's code."""
    stage_row = {stage: i for i, stage in enumerate(PLACES)}
    out = {}
    for scope, summary in tables["summary"].set_index("scope").iterrows():
        stages = tables["stages"][tables["stages"]["scope"] == scope].set_index("stage")["share"]
        moves = tables["moves"][tables["moves"]["scope"] == scope]
        curves = tables["curves"][tables["curves"]["scope"] == scope].sort_values("month")
        variants = tables["paths"][tables["paths"]["scope"] == scope]
        out[scope] = {
            "registered": int(registered[scope]),
            "sampled": int(summary["sampled"]),
            "decided": [_days(summary[f"decided_{q}"]) for q in ["p25", "median", "p75"]],
            "final": [_days(summary[f"final_{q}"]) for q in ["p25", "median", "p75"]],
            "open": _number(summary["open"]),
            "stages": [_number(stages.get(stage, 0.0)) for stage in events.STAGES],
            "moves": [
                [stage_row[row["from"]], stage_row[row["to"]], _number(row["share"]), int(row["sampled"])]
                + [_days(row[w]) for w in ["wait_p25", "wait_median", "wait_p75"]]
                for _, row in moves.iterrows()
            ],
            "notDecided": [_curve(v) for v in curves["not_decided"]],
            "notFinal": [_curve(v) for v in curves["not_final"]],
            "paths": [
                [
                    [stage_row[stage] for stage in row["path"].split(" > ")],
                    row["ending"],
                    _number(row["share"]),
                    int(row["sampled"]),
                ]
                for _, row in variants.iterrows()
            ],
        }
    return out


def build(weights, cases, table, chosen, scores_table, calibration_table, journey_tables, intake):
    """The demo's data, as a dict."""
    courts = {row["code"]: row for row in reference.courts()}
    glosses = {row["code"]: row["gloss_en"] for row in reference.events() if row["kind"] == "event"}
    registered = intake.groupby("court")["count"].sum()
    registered["all"] = intake["count"].sum()
    return {
        "snapshot": str(max(cases["valid_to"])),
        "recordsFrom": str(min(cases["valid_to"])),
        "split": examples.SPLIT.isoformat(),
        "registered": int(intake["count"].sum()),
        "sampled": len(cases),
        "horizons": [1, 3, 6, 12],
        "stages": PLACES,
        "endings": ENDINGS,
        "courts": [
            {"code": c, "name": courts[c]["name"], "area": courts[c]["area"]} for c in weights["courts"]
        ],
        "codes": [{"code": c, "gloss": glosses[c], "stage": events.STAGE.get(c)} for c in weights["codes"]],
        "network": network(weights),
        "cases": {
            "columns": ["court", "senate", "number", "year", "filed", "span", "ended", "events"],
            "rows": real_cases(cases, table, chosen, weights["codes"], weights["courts"]),
        },
        "scores": scores(scores_table),
        "calibration": calibration(calibration_table),
        "journey": journeys(journey_tables, registered),
    }


def dumps(data):
    """JSON with one record per line for the long lists, so a refresh shows up as a readable diff."""

    def compact(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def rows(items, indent):
        return "[\n" + ",\n".join(indent + compact(item) for item in items) + "\n" + indent[:-2] + "]"

    lines = []
    for key, value in data.items():
        if key in ("cases", "scores", "calibration"):
            body = f'{{"columns":{compact(value["columns"])},"rows":{rows(value["rows"], "    ")}}}'
        elif key == "network":
            members = rows(value["members"], "    ")
            body = f'{{"horizon":{value["horizon"]},"members":{members}}}'
        elif key in ("courts", "codes"):
            body = rows(value, "    ")
        elif key == "journey":
            body = "{\n" + ",\n".join(f"    {compact(k)}:{compact(v)}" for k, v in value.items()) + "\n  }"
        else:
            body = compact(value)
        lines.append(f"  {compact(key)}: {body}")
    return "{\n" + ",\n".join(lines) + "\n}\n"


def run():
    weights = json.loads(model.NETWORK.read_text(encoding="utf-8"))
    cases, table = journey.load()
    data = build(
        weights,
        cases,
        table,
        pd.read_csv(model.DEMO_CASES),
        pd.read_csv(model.SCORES),
        pd.read_csv(model.CALIBRATION),
        {name: pd.read_csv(path) for name, path in journey.OUT.items()},
        pd.read_csv(paths.DERIVED / "intake.csv"),
    )
    paths.EXPORT.parent.mkdir(parents=True, exist_ok=True)
    paths.EXPORT.write_text(dumps(data), encoding="utf-8", newline="\n")
    size = paths.EXPORT.stat().st_size
    print(f"Wrote {paths.EXPORT.relative_to(paths.ROOT)}: {size / 1000:.0f} KB")
    for key, value in data.items():
        print(f"  {key}: {len(json.dumps(value, ensure_ascii=False, separators=(',', ':'))) / 1000:.1f} KB")
    if size > MAX_BYTES:
        print(f"Over the budget of {MAX_BYTES / 1000:.0f} KB")
        return 1
    return 0
