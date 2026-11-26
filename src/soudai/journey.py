"""The journey numbers (milestone 6): for the whole country and for each court, how many cases reach each
stage and take each move between stages, how long each move takes, and how long cases take to be decided
and to become legally final. Every figure is weighted, so it's a share of all cases registered.

Each case's path comes from the stage model (`events.journey`), and its dates from `events.outcomes`.

- **Moves.** A case's visit to a stage ends when it moves to the next stage. A visit that's still going
  when the case's record runs to is censored there. A case closed in the register without becoming
  legally final leaves its last stage for "closed".
- **Waits.** A move's wait is the Aalen–Johansen estimate over every visit to its starting stage, with
  each next stage as a way out: the median and quartiles of the wait among the cases that make that move.
  It's only given where at least MIN_MOVES sampled cases made it.
- **Curves.** The share of cases not yet decided, and not yet finished (legally final, or closed without
  that), each month after filing, by Kaplan–Meier.

Writes data/derived/journey_stages.csv, journey_moves.csv, journey_curves.csv, journey_paths.csv and
journey_summary.csv. The scope "all" is the whole country, and any other scope is a court's code.

    uv run soudai analyse
"""

import numpy as np
import pandas as pd
import pyarrow.parquet

from . import events, paths, sample, survival

MONTH = 365.25 / 12  # days
MONTHS = 72
MIN_MOVES = 20  # sampled moves needed for a move's wait
TOP_PATHS = {"all": 30, "court": 10}
OUT = {
    name: paths.DERIVED / f"journey_{name}.csv" for name in ["stages", "moves", "curves", "paths", "summary"]
}
ENDS = events.STAGES[1:] + ["closed"]  # the ways out of a stage: a later stage (never "filed"), or closing


def load():
    cases = pyarrow.parquet.read_table(sample.CASES).to_pandas()
    log = pyarrow.parquet.read_table(sample.EVENTS).to_pandas()
    return cases, log


def moves(cases, visits, outcomes):
    """One row per stage visit, except to "final": the case, its weight, the stage, the next stage (None
    if the visit is still going), and the days until the next stage or until the case's record runs to.
    A few cases were closed in the register and then carried on: their last visit leaves for "closed"
    on the day it began, since the closing came first."""
    visits = visits.merge(cases[events.CASE + ["weight"]], on=events.CASE)
    visits = visits.merge(outcomes[events.CASE + ["how", "until"]], on=events.CASE)
    grouped = visits.groupby(events.CASE)
    visits["next"] = grouped["stage"].shift(-1)
    visits["left"] = grouped["date"].shift(-1)
    last = visits["next"].isna()
    closed = last & (visits["how"] == "closed")
    visits.loc[closed, "next"] = "closed"
    visits.loc[closed, "left"] = visits.loc[closed, "until"]
    visits.loc[last & ~closed, "left"] = visits.loc[last & ~closed, "until"]
    visits = visits[visits["stage"] != "final"]
    days = [
        max((left - entered).days, 0) for left, entered in zip(visits["left"], visits["date"], strict=True)
    ]
    columns = events.CASE + ["weight", "stage", "next"]
    visits = visits[columns].assign(days=days).astype({"next": object})
    return visits.assign(next=visits["next"].where(visits["next"].notna(), None)).reset_index(drop=True)


def within(frame, scope):
    """A table's rows for one scope: all of them, or one court's."""
    return frame if scope == "all" else frame[frame["court"] == scope]


def stage_shares(visits, weights):
    """The share of cases reaching each stage, from one scope's visits and {case: weight}."""
    reached = visits[events.CASE + ["stage"]].drop_duplicates()
    weight = reached.join(weights, on=events.CASE).groupby("stage")["weight"].sum()
    return {stage: weight.get(stage, 0.0) / weights.sum() for stage in events.STAGES}


def move_rows(scope, scope_moves, weights):
    """journey_moves.csv's rows for one scope: each move from one stage to another, with the share of
    cases making it at least once, the sampled cases making it, and its wait's median and quartiles."""
    rows = []
    taken = scope_moves.dropna(subset=["next"]).drop_duplicates(events.CASE + ["stage", "next"])
    for stage, stage_moves in scope_moves.groupby("stage", sort=False):
        causes = stage_moves["next"].map({end: i + 1 for i, end in enumerate(ENDS)}).fillna(0)
        times, incidence = survival.cumulative_incidence(stage_moves["days"], causes, stage_moves["weight"])
        for i, end in enumerate(ENDS):
            made = taken[(taken["stage"] == stage) & (taken["next"] == end)]
            if made.empty:
                continue
            row = {
                "scope": scope,
                "from": stage,
                "to": end,
                "share": made["weight"].sum() / weights.sum(),
                "sampled": len(made),
            }
            if len(made) >= MIN_MOVES:
                reached = incidence[:, i] / incidence[-1, i]
                for name, q in [("wait_p25", 0.25), ("wait_median", 0.5), ("wait_p75", 0.75)]:
                    row[name] = survival.quantile(times, reached, q)
            rows.append(row)
    return rows


def curve(durations, ended, weights):
    """Kaplan–Meier: the share not yet there each month after filing, and the quartiles of the wait."""
    times, still = survival.kaplan_meier(durations, ended, weights)
    months = survival.at(times, still, np.arange(MONTHS + 1) * MONTH, before=1.0)
    quartiles = [survival.quantile(times, 1 - still, q) for q in (0.25, 0.5, 0.75)]
    return months, quartiles


def case_table(cases, visits, outcomes):
    """One row per case with a filing: its weight, dates, path, how it ended ("final", "closed" or
    "open"), and its days from filing to a decision and to its end, or to censoring."""
    per_case = outcomes.merge(cases[events.CASE + ["weight"]], on=events.CASE)
    path = visits.groupby(events.CASE)["stage"].agg(" > ".join).rename("path")
    per_case = per_case.join(path, on=events.CASE).assign(ending=per_case["how"].fillna("open"))
    rows = zip(per_case["filed"], per_case["disposed"], per_case["until"], strict=True)
    per_case["decided_days"] = [((decided or until) - filed).days for filed, decided, until in rows]
    per_case["final_days"] = [
        (until - filed).days for filed, until in zip(per_case["filed"], per_case["until"], strict=True)
    ]
    return per_case


def analyse(cases, log):
    """The five tables, as {name: DataFrame}."""
    visits = events.journey(cases, log)
    outcomes = events.outcomes(cases, log)
    all_moves = moves(cases, visits, outcomes)
    per_case = case_table(cases, visits, outcomes)
    tables = {name: [] for name in OUT}
    for scope in ["all"] + sorted(per_case["court"].unique()):
        scope_cases = within(per_case, scope)
        weights = scope_cases.set_index(events.CASE)["weight"]
        shares = stage_shares(within(visits, scope), weights)
        tables["stages"] += [
            {"scope": scope, "stage": stage, "share": share} for stage, share in shares.items()
        ]
        tables["moves"] += move_rows(scope, within(all_moves, scope), weights)
        decided, decided_q = curve(scope_cases["decided_days"], scope_cases["disposed"].notna(), weights)
        final, final_q = curve(scope_cases["final_days"], scope_cases["end"].notna(), weights)
        tables["curves"] += [
            {"scope": scope, "month": month, "not_decided": d, "not_final": f}
            for month, (d, f) in enumerate(zip(decided, final, strict=True))
        ]
        by_path = scope_cases.groupby(["path", "ending"])["weight"].agg(["sum", "size"])
        top = by_path.sort_values("sum", ascending=False).head(
            TOP_PATHS["all" if scope == "all" else "court"]
        )
        tables["paths"] += [
            {
                "scope": scope,
                "path": path,
                "ending": ending,
                "share": row["sum"] / weights.sum(),
                "sampled": int(row["size"]),
            }
            for (path, ending), row in top.iterrows()
        ]
        tables["summary"].append(
            {
                "scope": scope,
                "sampled": len(scope_cases),
                "registered": weights.sum(),
                "decided_p25": decided_q[0],
                "decided_median": decided_q[1],
                "decided_p75": decided_q[2],
                "final_p25": final_q[0],
                "final_median": final_q[1],
                "final_p75": final_q[2],
                "open": scope_cases.loc[scope_cases["end"].isna(), "weight"].sum() / weights.sum(),
            }
        )
    return {name: pd.DataFrame(rows) for name, rows in tables.items()}


def run():
    cases, log = load()
    tables = analyse(cases, log)
    for name, table in tables.items():
        table.to_csv(OUT[name], index=False, float_format="%.8g", lineterminator="\n")
        print(f"Wrote {len(table):,} rows to {OUT[name]}")
    summary = tables["summary"].set_index("scope").loc["all"]
    print(
        f"All courts: {summary['registered']:,.0f} cases registered, {int(summary['sampled']):,} sampled. "
        f"Median days from filing to a decision {summary['decided_median']:.0f}, "
        f"to legally final {summary['final_median']:.0f}. Still open: {summary['open']:.1%}."
    )
    return 0
