"""The journey numbers, on a few made-up cases worked by hand."""

from datetime import date, timedelta

import pandas as pd
import pytest

from soudai import events, journey

START = date(2022, 1, 3)
VALID_TO = START + timedelta(days=300)


def case(court, number, weight, *steps):
    """(cases row, event rows) for a case whose events are (code, days after START)."""
    key = {"court": court, "senate": 1, "number": number, "year": 2022}
    rows = [
        key | {"code": code, "date": START + timedelta(days=day), "poradi": i, "cancelled": False}
        for i, (code, day) in enumerate(steps, 1)
    ]
    return key | {"valid_to": VALID_TO, "weight": weight}, rows


def tables(monkeypatch, min_moves=1):
    """Court OSA: two cases heard and decided (on days 100 and 200), one decided with no hearing (day 50)
    and one still open, each weighing 2. Court OSB: one case decided with no hearing, weighing 4."""
    monkeypatch.setattr(journey, "MIN_MOVES", min_moves)
    made = [
        case(
            "OSA",
            1,
            2,
            ("ZAHAJ_RIZ", 0),
            ("NAR_JED", 100),
            ("VYD_ROZH", 100),
            ("ST_VEC_VYR", 100),
            ("ST_VEC_PUK", 130),
        ),
        case(
            "OSA",
            2,
            2,
            ("ZAHAJ_RIZ", 0),
            ("NAR_JED", 200),
            ("VYD_ROZH", 200),
            ("ST_VEC_VYR", 200),
            ("ST_VEC_PUK", 230),
        ),
        case("OSA", 3, 2, ("ZAHAJ_RIZ", 0), ("VYD_ROZH", 50), ("ST_VEC_VYR", 50), ("ST_VEC_PUK", 80)),
        case("OSA", 4, 2, ("ZAHAJ_RIZ", 0)),
        case("OSB", 5, 4, ("ZAHAJ_RIZ", 0), ("VYD_ROZH", 10), ("ST_VEC_VYR", 10), ("ST_VEC_PUK", 20)),
    ]
    cases = pd.DataFrame([row for row, _ in made])
    log = pd.DataFrame([event for _, rows in made for event in rows])
    return journey.analyse(cases, log)


def pick(table, **where):
    for column, value in where.items():
        table = table[table[column] == value]
    return table.iloc[0] if len(table) == 1 else table


def test_moves_end_at_the_next_stage_at_closing_or_when_the_record_runs_out():
    cases = pd.DataFrame(
        [
            {"court": "OSA", "senate": 1, "number": n, "year": 2022, "valid_to": VALID_TO, "weight": 1.0}
            for n in (1, 2)
        ]
    )
    log = pd.DataFrame(
        case("OSA", 1, 1, ("ZAHAJ_RIZ", 0), ("VYD_ROZH", 40), ("ST_VEC_ODS", 60))[1]
        + case("OSA", 2, 1, ("ZAHAJ_RIZ", 0), ("NAR_JED", 90))[1]
    )
    visits, outcomes = events.journey(cases, log), events.outcomes(cases, log)
    moves = journey.moves(cases, visits, outcomes)
    assert moves[["number", "stage", "next", "days"]].values.tolist() == [
        [1, "filed", "decided", 40],
        [1, "decided", "closed", 20],
        [2, "filed", "hearing", 90],
        [2, "hearing", None, 210],  # still waiting when the record runs out
    ]


def test_stage_shares_are_weighted_shares_of_cases(monkeypatch):
    stages = tables(monkeypatch)["stages"]
    court = stages[stages["scope"] == "OSA"].set_index("stage")["share"]
    assert court.to_dict() == pytest.approx(
        {
            "filed": 1,
            "hearing": 0.5,
            "decided": 0.75,
            "appeal": 0,
            "revived": 0,
            "suspended": 0,
            "final": 0.75,
        }
    )
    assert pick(stages, scope="all", stage="decided")["share"] == pytest.approx((6 + 4) / 12)


def test_move_shares_and_waits(monkeypatch):
    moves = tables(monkeypatch)["moves"]
    heard = pick(moves, scope="OSA", **{"from": "filed", "to": "hearing"})
    # Leaving "filed": day 50 to a decision (4 waiting, 1 leaves), day 100 to a hearing (3 waiting), day
    # 200 to a hearing (2 waiting), and one censored on day 300. Half of those heard were heard by day 100.
    assert heard["share"] == pytest.approx(0.5)
    assert (heard["wait_p25"], heard["wait_median"], heard["wait_p75"]) == (100, 100, 200)
    assert pick(moves, scope="OSA", **{"from": "filed", "to": "decided"})["wait_median"] == 50
    assert pick(moves, scope="all", **{"from": "filed", "to": "decided"})["share"] == pytest.approx(6 / 12)
    assert pick(moves, scope="OSA", **{"from": "hearing", "to": "decided"})["wait_median"] == 0


def test_becoming_legally_final_is_a_move(monkeypatch):
    moves = tables(monkeypatch)["moves"]
    final = pick(moves, scope="OSA", **{"from": "decided", "to": "final"})
    # Three of OSA's four cases (weighing 2 each) became legally final 30 days after their decision.
    assert final["share"] == pytest.approx(0.75)
    assert final["sampled"] == 3
    assert (final["wait_p25"], final["wait_median"], final["wait_p75"]) == (30, 30, 30)
    assert pick(moves, scope="all", **{"from": "decided", "to": "final"})["share"] == pytest.approx(10 / 12)


def test_a_wait_counts_the_other_ways_out_including_legally_final(monkeypatch):
    """Five visits to "decided": legally final on days 10, 20 and 40, appealed on days 30 and 50. By
    Aalen–Johansen, 1/5 of visits are appealed on day 30 (3 of 5 still waiting) and 1/5 on day 50, so the
    median wait to an appeal is 30 days. Counting the legally final visits as still waiting instead would
    put 1/3 on day 30 and 2/3 on day 50, and the median at 50."""
    monkeypatch.setattr(journey, "MIN_MOVES", 1)
    visits = pd.DataFrame(
        {
            "court": "OSA",
            "senate": 1,
            "number": range(5),
            "year": 2022,
            "weight": 1.0,
            "stage": "decided",
            "next": ["final", "final", "appeal", "final", "appeal"],
            "days": [10, 20, 30, 40, 50],
        }
    )
    rows = {row["to"]: row for row in journey.move_rows("all", visits, pd.Series([1.0] * 5))}
    assert rows["appeal"]["share"] == pytest.approx(0.4)
    assert (rows["appeal"]["wait_p25"], rows["appeal"]["wait_median"], rows["appeal"]["wait_p75"]) == (
        30,
        30,
        50,
    )
    assert rows["final"]["share"] == pytest.approx(0.6) and rows["final"]["wait_median"] == 20


def test_moves_with_too_few_cases_get_no_wait(monkeypatch):
    moves = tables(monkeypatch, min_moves=2)["moves"]
    decided = pick(moves, scope="OSA", **{"from": "filed", "to": "decided"})
    assert decided["sampled"] == 1 and pd.isna(decided["wait_median"])
    assert pick(moves, scope="OSA", **{"from": "filed", "to": "hearing"})["wait_median"] == 100


def test_curves_and_summary(monkeypatch):
    out = tables(monkeypatch)
    curves = out["curves"][out["curves"]["scope"] == "OSA"].set_index("month")
    # Decided on days 50, 100 and 200, and one still open on day 300.
    assert curves.loc[0, "not_decided"] == 1
    assert curves.loc[2, "not_decided"] == pytest.approx(0.75)  # day 61
    assert curves.loc[4, "not_decided"] == pytest.approx(0.5)  # day 122
    assert curves.loc[7, "not_decided"] == pytest.approx(0.25)  # day 213
    assert curves["not_final"].is_monotonic_decreasing
    summary = pick(out["summary"], scope="OSA")
    assert (summary["decided_p25"], summary["decided_median"], summary["decided_p75"]) == (50, 100, 200)
    assert summary["final_median"] == 130
    assert summary["open"] == pytest.approx(0.25)
    assert pick(out["summary"], scope="all")["registered"] == 12


def test_paths_are_ranked_by_share(monkeypatch):
    paths = tables(monkeypatch)["paths"]
    court = paths[paths["scope"] == "OSA"]
    shares = {(row.path, row.ending): row.share for row in court.itertuples()}
    assert shares == pytest.approx(
        {
            ("filed > hearing > decided > final", "final"): 0.5,
            ("filed > decided > final", "final"): 0.25,
            ("filed", "open"): 0.25,
        }
    )
    assert court["share"].is_monotonic_decreasing
    assert pick(paths, scope="all", path="filed > decided > final")["share"] == pytest.approx(6 / 12)
