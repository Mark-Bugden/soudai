"""The forecasting examples: where each case's history is cut, and what each cut knows and has ahead of it."""

from datetime import date, timedelta

import pandas as pd
import pytest

from soudai import examples

START = date(2022, 1, 3)
VALID_TO = date(2026, 11, 23)


def case(number, *steps, year=2022, valid_to=VALID_TO, weight=1.0, start=START):
    """(cases row, event rows) for a case at court OSA whose events are (code, days after `start`), or
    (code, days, "cancelled") or (code, days, a linked case)."""
    key = {"court": "OSA", "senate": 1, "number": number, "year": year}
    rows = []
    for poradi, (code, day, *extra) in enumerate(steps, 1):
        linked = extra[0] if extra and extra[0] != "cancelled" else None
        rows.append(
            key
            | {
                "code": code,
                "date": start + timedelta(days=day),
                "poradi": poradi,
                "cancelled": extra == ["cancelled"],
                "linked_court": "KSA" if linked else None,
                "linked_case": linked,
            }
        )
    return key | {"valid_to": valid_to, "weight": weight}, rows


def build(*made):
    cases = pd.DataFrame([row for row, _ in made])
    table = pd.DataFrame([event for _, rows in made for event in rows])
    return examples.build(cases, table)


HEARD = case(  # heard and decided on day 100, legally final on day 130, closed on day 140
    1,
    ("ZAHAJ_RIZ", 0),
    ("NAR_JED", 60, "cancelled"),
    ("NAR_JED", 100),
    ("VYD_ROZH", 100),
    ("ST_VEC_VYR", 100),
    ("ST_VEC_PUK", 130),
    ("ST_VEC_ODS", 140),
)


def test_a_case_is_cut_at_each_day_with_events_and_each_month_before_its_end():
    built = build(HEARD)
    cuts = built.cuts
    assert cuts["day"].tolist() == [0, 30, 61, 91, 100, 122]
    assert cuts["left"].tolist() == [130, 100, 69, 39, 30, 8]
    assert cuts["ended"].all()
    assert cuts["stage"].tolist() == ["filed"] * 4 + ["decided"] * 2
    assert cuts["in_stage"].tolist() == [0, 30, 61, 91, 0, 22]
    assert cuts["since_last"].tolist() == [0, 30, 61, 91, 0, 22]
    assert cuts["events"].tolist() == [1, 1, 1, 1, 4, 4]
    assert cuts["hearings"].tolist() == [0, 0, 0, 0, 1, 1]
    assert cuts["decided"].tolist() == [False] * 4 + [True] * 2
    assert not cuts["appealed"].any() and not cuts["revived"].any()
    # the cancelled hearing, and the events on or after the day the case ended, aren't steps
    assert built.steps["code"].tolist() == ["ZAHAJ_RIZ", "NAR_JED", "VYD_ROZH", "ST_VEC_VYR"]
    assert built.steps["gap"].tolist() == [0, 100, 0, 0]
    assert built.steps["day"].tolist() == [0, 100, 100, 100]
    # a cut's step is the last event so far, and that day's events are all in
    assert built.steps.loc[cuts["step"], "code"].tolist() == ["ZAHAJ_RIZ"] * 4 + ["ST_VEC_VYR"] * 2
    history = built.histories.iloc[0]
    assert (history["span"], history["ended"], history["filed"]) == (130, True, START)


def test_an_open_case_is_censored_when_its_record_runs_out():
    built = build(case(1, ("ZAHAJ_RIZ", 0), ("NAR_JED", 45), valid_to=START + timedelta(days=70)))
    assert built.cuts["day"].tolist() == [0, 30, 45, 61]
    assert built.cuts["left"].tolist() == [70, 40, 25, 9]
    assert not built.cuts["ended"].any()
    assert built.cuts["stage"].tolist() == ["filed", "filed", "hearing", "hearing"]
    assert built.cuts["in_stage"].tolist() == [0, 30, 0, 16]


def test_appeals_revivals_and_repeated_stages():
    built = build(
        case(
            1,
            ("ZAHAJ_RIZ", 0),
            ("VYD_ROZH", 20),
            ("ST_VEC_VYR", 20),
            ("POD_OP_PR", 25),
            ("ODVOLANI", 40, "12 Co 5/2022"),
            ("ST_VEC_OBZ", 50),
            ("NAR_JED", 70),
            ("NAR_JED", 80),
            ("ST_VEC_PRE", 85),
            ("ST_VEC_UPR", 88),
            ("VYD_ROZH", 95),
            ("ST_VEC_VYR", 95),
            ("ST_VEC_PUK", 125),
        )
    )
    cuts = built.cuts.set_index("day")
    assert cuts.index.tolist() == [0, 20, 25, 30, 40, 50, 61, 70, 80, 85, 88, 91, 95, 122]
    assert cuts.loc[30, ["stage", "in_stage", "appealed", "revived"]].tolist() == ["appeal", 5, True, False]
    assert cuts.loc[61, ["stage", "in_stage", "revived"]].tolist() == ["revived", 11, True]
    # two hearings are one visit to the stage; "proceedings resumed" doesn't end a suspension on the map
    assert cuts.loc[80, ["stage", "in_stage", "hearings"]].tolist() == ["hearing", 10, 2]
    assert cuts.loc[88, ["stage", "in_stage", "since_last"]].tolist() == ["suspended", 3, 0]
    assert cuts.loc[91, ["stage", "in_stage", "since_last"]].tolist() == ["suspended", 6, 3]
    assert cuts.loc[122, ["stage", "decided", "events"]].tolist() == ["decided", True, 12]


def test_a_case_finished_on_its_filing_day_gives_no_forecast():
    built = build(HEARD, case(2, ("ZAHAJ_RIZ", 0), ("ST_VEC_PUK", 0)))
    assert built.histories["number"].tolist() == [1]
    assert len(built.cuts) == 6


def test_the_split_trains_on_records_as_they_stood_the_day_before_it():
    late = case(  # registered in 2023, legally final in 2024
        2,
        ("ZAHAJ_RIZ", 0),
        ("VYD_ROZH", 200),
        ("ST_VEC_VYR", 200),
        ("ST_VEC_PUK", 300),
        year=2023,
        start=date(2023, 9, 1),
    )
    test = case(3, ("ZAHAJ_RIZ", 0), ("ST_VEC_PUK", 50), year=2024, start=date(2023, 12, 1))
    cases = pd.DataFrame([row for row, _ in (HEARD, late, test)])
    table = pd.DataFrame([event for _, rows in (HEARD, late, test) for event in rows])
    train_cases, test_cases = examples.split(cases)
    assert test_cases["number"].tolist() == [3]
    assert train_cases["valid_to"].tolist() == [date(2023, 12, 31)] * 2
    train = examples.build(train_cases, table)
    history = train.histories.set_index("number")
    assert history.loc[2, ["span", "ended"]].tolist() == [(date(2023, 12, 31) - date(2023, 9, 1)).days, False]
    assert history.loc[1, "ended"]  # finished long before the split
    # a test case keeps what happened after the split, even though it was filed before it
    assert examples.build(test_cases, table).histories["span"].tolist() == [50]


def test_forecasts_are_scored_at_filing_and_1_3_6_and_12_months():
    built = build(HEARD, case(2, ("ZAHAJ_RIZ", 0), valid_to=START + timedelta(days=400)))
    at = examples.scored(built.cuts)
    assert at[["id", "day", "landmark"]].values.tolist() == [
        [0, 0, 0],
        [0, 30, 1],
        [0, 91, 3],
        [1, 0, 0],
        [1, 30, 1],
        [1, 91, 3],
        [1, 183, 6],
        [1, 365, 12],
    ]


def test_held_out_cases_are_a_fixed_random_share():
    histories = pd.DataFrame({"id": range(10_000)})
    held = examples.held_out(histories)
    assert held.mean() == pytest.approx(examples.VALIDATION, abs=0.01)
    assert (held == examples.held_out(histories)).all()


def test_the_demos_cases_are_drawn_per_court_by_weight():
    rows = []
    for court, n in [("A", 200), ("B", 3)]:
        for number in range(n):
            rows.append(
                {"id": len(rows), "court": court, "senate": 1, "number": number, "year": 2024}
                | {"weight": 100.0 if number < 20 else 1.0, "filed": START, "span": 10, "ended": True}
            )
    test = examples.Examples(pd.DataFrame(rows), None, None)
    chosen = examples.demo_cases(test, per_court=10)
    assert chosen["court"].value_counts().to_dict() == {"A": 10, "B": 3}  # B has only 3
    # A's first 20 cases weigh 100 each and the other 180 weigh 1, so nearly all the draws are among them
    assert (chosen.loc[chosen["court"] == "A", "number"] < 20).sum() >= 8
    assert chosen.equals(examples.demo_cases(test, per_court=10))
    assert chosen.columns.tolist() == ["court", "senate", "number", "year", "filed", "span", "ended"]
